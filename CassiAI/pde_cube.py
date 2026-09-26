#!/usr/bin/env python3
"""PDECube — 3D PDE engine for [B, H, W, D, d, 2] field.

Dimension-agnostic PDE: the physics (diffusion, dispersion, quantum potential,
advection, nonlinear coupling) is the same regardless of spatial dimensions.
The spatial derivative kernels are generalized to 3D.

Architecture:
    Source [B,H,W,D,d,2] → Strang-split integration
    → nonlinear (advection + QP + NL coupling + breath)
    → linear step (diffusion + dispersion in 3D)
    → normalization
    → [B,H,W,D,d,2] field state
"""

from __future__ import annotations

import math
from typing import Dict

import torch
import torch.nn as nn
import torch.nn.functional as F

from _chakra_utils import PHI, PHI_INV


class PDECube(nn.Module):
    """3D PDE with shared coefficients, operating on [B,H,W,D,d,2].

    All PDE operations are dimension-agnostic — gradient and laplacian
    are computed independently along each spatial axis and combined.

    Args:
        d: Field dimension per voxel (channels).
    """

    def __init__(self, d: int):
        super().__init__()
        self.d = d

        # ── PDE coefficients (same 10 params as 1D) ──
        self.nu_logit = nn.Parameter(torch.tensor(0.0))
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

    def get_params(self) -> Dict[str, torch.Tensor]:
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

    # ── 3D spatial ops (generalized from 1D) ──

    def _grad_h(self, psi: torch.Tensor) -> torch.Tensor:
        """∂ψ/∂h — central difference along height axis (dim=1)."""
        grad = torch.zeros_like(psi)
        grad[:, 1:-1] = (psi[:, 2:] - psi[:, :-2]) * 0.5
        # Boundary: forward/backward difference
        grad[:, 0] = psi[:, 1] - psi[:, 0]
        grad[:, -1] = psi[:, -1] - psi[:, -2]
        return grad

    def _grad_w(self, psi: torch.Tensor) -> torch.Tensor:
        """∂ψ/∂w — central difference along width axis (dim=2)."""
        grad = torch.zeros_like(psi)
        grad[:, :, 1:-1] = (psi[:, :, 2:] - psi[:, :, :-2]) * 0.5
        grad[:, :, 0] = psi[:, :, 1] - psi[:, :, 0]
        grad[:, :, -1] = psi[:, :, -1] - psi[:, :, -2]
        return grad

    def _grad_d(self, psi: torch.Tensor) -> torch.Tensor:
        """∂ψ/∂d — central difference along depth axis (dim=3)."""
        grad = torch.zeros_like(psi)
        grad[:, :, :, 1:-1] = (psi[:, :, :, 2:] - psi[:, :, :, :-2]) * 0.5
        grad[:, :, :, 0] = psi[:, :, :, 1] - psi[:, :, :, 0]
        grad[:, :, :, -1] = psi[:, :, :, -1] - psi[:, :, :, -2]
        return grad

    def _gradient(self, psi: torch.Tensor) -> Dict[str, torch.Tensor]:
        """Return all 3 gradient components."""
        return {
            "h": self._grad_h(psi),
            "w": self._grad_w(psi),
            "d": self._grad_d(psi),
        }

    def _laplacian(self, psi: torch.Tensor) -> torch.Tensor:
        """∇²ψ = ∂²ψ/∂h² + ∂²ψ/∂w² + ∂²ψ/∂d²."""
        # Second derivatives via central differences
        lap = torch.zeros_like(psi)
        # ∂²ψ/∂h²
        lap[:, 1:-1] += psi[:, 2:] + psi[:, :-2] - 2.0 * psi[:, 1:-1]
        lap[:, 0] += psi[:, 1] - psi[:, 0]
        lap[:, -1] += psi[:, -2] - psi[:, -1]
        # ∂²ψ/∂w²
        lap[:, :, 1:-1] += psi[:, :, 2:] + psi[:, :, :-2] - 2.0 * psi[:, :, 1:-1]
        lap[:, :, 0] += psi[:, :, 1] - psi[:, :, 0]
        lap[:, :, -1] += psi[:, :, -2] - psi[:, :, -1]
        # ∂²ψ/∂d²
        lap[:, :, :, 1:-1] += psi[:, :, :, 2:] + psi[:, :, :, :-2] - 2.0 * psi[:, :, :, 1:-1]
        lap[:, :, :, 0] += psi[:, :, :, 1] - psi[:, :, :, 0]
        lap[:, :, :, -1] += psi[:, :, :, -2] - psi[:, :, :, -1]
        return lap

    def _magnitude(self, psi: torch.Tensor) -> torch.Tensor:
        """|ψ|² = psi[...,0]² + psi[...,1]² across last dim."""
        return psi.pow(2).sum(dim=-1)

    def _advection(self, psi: torch.Tensor,
                   grad: Dict[str, torch.Tensor],
                   adv_strength: float) -> torch.Tensor:
        """v · ∇ψ = adv_h * ∂ψ/∂h + adv_w * ∂ψ/∂w + adv_d * ∂ψ/∂d.

        Paired-real: (real*∇real - imag*∇imag, real*∇imag + imag*∇real)
        per component, summed across dimensions.
        """
        s = adv_strength * PHI_INV
        result = torch.zeros_like(psi)

        for axis in ['h', 'w', 'd']:
            g = grad[axis]
            re = psi[..., 0] * g[..., 0] - psi[..., 1] * g[..., 1]
            im = psi[..., 0] * g[..., 1] + psi[..., 1] * g[..., 0]
            result[..., 0] += re
            result[..., 1] += im

        return -s * result

    def _quantum_potential(self, rho: torch.Tensor,
                           hbar: float, mass: float) -> torch.Tensor:
        """Q = -(ħ²/2m²) ∇²|ψ|ᵝ / |ψ|ᵝ, where β = φ⁻¹/2."""
        beta = PHI_INV / 2.0
        amp = rho ** beta
        lap = self._laplacian(amp.unsqueeze(-1)).squeeze(-1)
        q = -(hbar ** 2) / (2.0 * mass ** 2) * lap / amp.clamp_min(1e-2)
        return q  # [B, H, W, D, d]

    def _linear_step(self, psi: torch.Tensor,
                     nu: float, chi: float, dt: float) -> torch.Tensor:
        """Diffusion + dispersion in 3D."""
        # Diffusion
        lap = self._laplacian(psi)
        psi = psi + nu * dt * lap

        # Dispersion (symplectic Euler in 3D)
        lap_1 = self._laplacian(psi[..., 1:]).squeeze(-1)  # ∇²ψ₁, [B,H,W,D,d]
        new_0 = psi[..., 0] - chi * dt * lap_1

        lap_new_0 = self._laplacian(new_0.unsqueeze(-1)).squeeze(-1)  # ∇²ψ₀new
        new_1 = psi[..., 1] + chi * dt * lap_new_0

        return torch.stack([new_0, new_1], dim=-1)

    def _normalize(self, psi: torch.Tensor) -> torch.Tensor:
        """Normalize by global max amplitude across all spatial dims."""
        rho = self._magnitude(psi)
        max_amp = rho.sqrt().amax(dim=[1, 2, 3], keepdim=True)
        return psi / max_amp.unsqueeze(-1).clamp_min(1e-4)

    # ── Integration ──

    def forward(self,
                source: torch.Tensor,
                params: Dict | None = None,
                T: float = 1.0,
                dt: float = 0.2,
                breath_phase: float = 0.0) -> torch.Tensor:
        """Integrate 3D PDE from source initial condition.

        Args:
            source: [B, H, W, D, d, 2] initial field.
            params: Pre-computed PDE params (or call get_params).
            T: Total integration time.
            dt: Time step size.
            breath_phase: Scalar phase for breath modulation.

        Returns:
            psi: [B, H, W, D, d, 2] final field state.
        """
        if params is None:
            params = self.get_params()
        psi = source
        n_steps = max(int(T / dt), 1)

        for step in range(n_steps):
            t = torch.tensor(step / n_steps + breath_phase, device=source.device)
            breath_t = 0.5 * (torch.sin(2 * math.pi * t)
                              + torch.sin(2 * math.pi * t * PHI_INV))

            # ── Half-step A: nonlinear ──
            rho = self._magnitude(psi)
            grad = self._gradient(psi)
            adv = self._advection(psi, grad, params["advection_strength"])
            qp = self._quantum_potential(rho, params["hbar"], params["mass"])
            nl = params["g"] * rho.unsqueeze(-1) * psi
            bf = params["A_B"] * breath_t * psi

            dpsi = adv + qp.unsqueeze(-1) * psi + nl + bf
            psi = psi + 0.5 * dt * dpsi
            psi = psi.clamp(-1e3, 1e3)

            # ── Linear step ──
            psi = self._linear_step(psi, params["nu"], params["chi"], dt)

            # ── Half-step B: nonlinear ──
            rho = self._magnitude(psi)
            grad = self._gradient(psi)
            adv = self._advection(psi, grad, params["advection_strength"])
            qp = self._quantum_potential(rho, params["hbar"], params["mass"])
            nl = params["g"] * rho.unsqueeze(-1) * psi
            bf = params["A_B"] * breath_t * psi

            dpsi = adv + qp.unsqueeze(-1) * psi + nl + bf
            psi = psi + 0.5 * dt * dpsi
            psi = psi.clamp(-1e3, 1e3)

            # ── Normalize ──
            psi = self._normalize(psi)
            # ROCm NaN guard: replace NaN/inf with zeros
            psi = torch.where(torch.isfinite(psi), psi,
                              torch.zeros_like(psi))
