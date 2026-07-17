#!/usr/bin/env python3
"""SingleFieldPDE — a monolithic PDE engine for the full [B,N,d,2] field.

Unlike the per-chakra ChakraDynamics, this operates on the entire field
dimension in one call — no Python loop over 13 chakras. All PDE coefficients
are shared across all positions. No predictor modules, no persistent state.

Integration is designed for no_grad usage (reservoir computing pattern),
matching the generation pass exactly: embed → integrate → readout next token.

Architecture:
    Source [B,N,d,2] → Strang-split integration (5 steps)
    → nonlinear (advection + QP + NL coupling + breath + source)
    → linear step (diffusion + dispersion)
    → normalization
    → [B,N,d,2] field state
"""

from __future__ import annotations

import math
from typing import Tuple

import torch
import torch.nn as nn

from _chakra_utils import PHI, PHI_INV


class SingleFieldPDE(nn.Module):
    """Monolithic PDE for [B,N,d,2] with shared coefficients.

    Pure functional: source → integrated state. No persistent buffers,
    no per-position modules. Intended for no_grad reservoir usage.

    Args:
        d: Total field dimension.
    """

    def __init__(self, d: int):
        super().__init__()
        self.d = d

        # ── PDE coefficients (10 shared params) ──
        self.nu_logit = nn.Parameter(torch.tensor(0.0))  # sigmoid=0.5, strong diffusion
        self.hbar_logit = nn.Parameter(torch.tensor(-2.3))
        self.mass_logit = nn.Parameter(torch.tensor(2.3))
        self.g_logit = nn.Parameter(torch.tensor(-2.2))
        self.chi_logit = nn.Parameter(torch.tensor(-2.9))
        self.A_B_logit = nn.Parameter(torch.tensor(-2.3))
        self.advection_logit = nn.Parameter(torch.tensor(-2.3))
        self.alpha_logit = nn.Parameter(torch.tensor(-2.3))
        self.gamma_logit = nn.Parameter(torch.tensor(-3.0))
        self.kappa_logit = nn.Parameter(torch.zeros(4))

    # ── Activations ──

    def get_params(self):
        nu = torch.sigmoid(self.nu_logit) * 0.3
        hbar = torch.sigmoid(self.hbar_logit) * 0.8 + 0.2
        mass = torch.sigmoid(self.mass_logit) * 99.0 + 1.0
        g = torch.tanh(self.g_logit) * 0.3 + 0.3
        chi = torch.sigmoid(self.chi_logit) * 0.15 + 0.05
        A_B = torch.sigmoid(self.A_B_logit) * 0.5
        adv = torch.sigmoid(self.advection_logit) * 1.0
        alpha = torch.sigmoid(self.alpha_logit)
        gamma = torch.sigmoid(self.gamma_logit) * 0.3
        kappa = torch.sigmoid(self.kappa_logit)
        return {"nu": nu, "hbar": hbar, "mass": mass, "g": g,
                "chi": chi, "A_B": A_B, "advection_strength": adv,
                "alpha": alpha, "gamma": gamma, "kappa": kappa}

    # ── PDE helper ops ──

    def _gradient(self, psi: torch.Tensor) -> torch.Tensor:
        grad = torch.zeros_like(psi)
        grad[:, 1:-1] = (psi[:, 2:] - psi[:, :-2]) / 2.0
        grad[:, 0] = psi[:, 1] - psi[:, 0]
        grad[:, -1] = psi[:, -1] - psi[:, -2]
        return grad

    def _laplacian(self, psi: torch.Tensor) -> torch.Tensor:
        lap = torch.zeros_like(psi)
        lap[:, 1:-1] = psi[:, 2:] + psi[:, :-2] - 2.0 * psi[:, 1:-1]
        lap[:, 0] = psi[:, 1] - psi[:, 0]
        lap[:, -1] = psi[:, -2] - psi[:, -1]
        return lap

    def _magnitude(self, psi: torch.Tensor) -> torch.Tensor:
        return psi.pow(2).sum(dim=-1)

    def _current(self, psi: torch.Tensor, grad: torch.Tensor) -> torch.Tensor:
        return psi[..., 0] * grad[..., 1] - psi[..., 1] * grad[..., 0]

    def _advection(self, psi: torch.Tensor, grad: torch.Tensor) -> torch.Tensor:
        s = torch.sigmoid(self.advection_logit)
        adv_0 = psi[..., 0] * grad[..., 0] - psi[..., 1] * grad[..., 1]
        adv_1 = psi[..., 0] * grad[..., 1] + psi[..., 1] * grad[..., 0]
        return -PHI_INV * s * torch.stack([adv_0, adv_1], dim=-1)

    def _quantum_potential(self, rho: torch.Tensor,
                           hbar: float, mass: float) -> torch.Tensor:
        beta = PHI_INV / 2.0
        amp = rho ** beta
        lap = self._laplacian(amp)
        q = -(hbar ** 2) / (2.0 * mass ** 2) * lap / amp.clamp_min(1e-2)
        return q  # [B, N, d]

    def _linear_step(self, psi: torch.Tensor,
                     nu: float, chi: float, dt: float) -> torch.Tensor:
        # Diffusion
        lap = self._laplacian(psi)
        psi = psi + nu * dt * lap
        # Dispersion (symplectic Euler)
        grad_1 = torch.zeros_like(psi[..., 0])
        grad_1[:, 1:-1] = (psi[:, 2:,:, 1] - psi[:, :-2,:, 1]) / 2.0
        new_0 = psi[..., 0] - chi * dt * grad_1

        grad_new_0 = torch.zeros_like(new_0)
        grad_new_0[:, 1:-1] = (new_0[:, 2:] - new_0[:, :-2]) / 2.0
        new_1 = psi[..., 1] + chi * dt * grad_new_0
        return torch.stack([new_0, new_1], dim=-1)

    def _normalize(self, psi: torch.Tensor) -> torch.Tensor:
        rho = self._magnitude(psi)
        max_amp = rho.sqrt().max(dim=-1, keepdim=True).values
        return psi / max_amp.unsqueeze(-1).clamp_min(1e-4)

    # ── Integration ──

    def forward(self,
                source: torch.Tensor,
                T: float = 1.0,
                dt: float = 0.2,
                breath_phase: float = 0.0) -> torch.Tensor:
        """Integrate PDE from source initial condition.

        DIFFERENTIABLE — but typically called inside no_grad for speed.

        Args:
            source: [B, N, d, 2] — initial field state + forcing.
            T: Total integration time.
            dt: Time step size.
            breath_phase: Scalar phase for breath modulation.

        Returns:
            psi: [B, N, d, 2] — final field state.
        """
        params = self.get_params()
        psi = source  # [B, N, d, 2]
        n_steps = max(int(T / dt), 1)

        for step in range(n_steps):
            t = torch.tensor(step / n_steps + breath_phase, device=source.device)
            breath_t = 0.5 * (torch.sin(2 * math.pi * t)
                              + torch.sin(2 * math.pi * t * PHI_INV))

            # ── Half-step A: nonlinear ──
            rho = self._magnitude(psi)
            grad = self._gradient(psi)
            adv = self._advection(psi, grad)
            qp = self._quantum_potential(rho, params["hbar"], params["mass"])
            nl = params["g"] * rho.unsqueeze(-1) * psi
            bf = params["A_B"] * breath_t * psi

            dpsi = adv + qp.unsqueeze(-1) * psi + nl + bf  # + source (already in psi)
            psi = psi + 0.5 * dt * dpsi
            psi = psi.clamp(-1e3, 1e3)

            # ── Linear step ──
            psi = self._linear_step(psi, params["nu"], params["chi"], dt)

            # ── Half-step B: nonlinear ──
            rho = self._magnitude(psi)
            grad = self._gradient(psi)
            adv = self._advection(psi, grad)
            qp = self._quantum_potential(rho, params["hbar"], params["mass"])
            nl = params["g"] * rho.unsqueeze(-1) * psi
            bf = params["A_B"] * breath_t * psi

            dpsi = adv + qp.unsqueeze(-1) * psi + nl + bf
            psi = psi + 0.5 * dt * dpsi
            psi = psi.clamp(-1e3, 1e3)

            # ── Normalize ──
            psi = self._normalize(psi)

        return psi
