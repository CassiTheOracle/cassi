"""Independent per-chakra PDE dynamics.

Each chakra gets its own `ChakraDynamics` — a self-contained PDE engine
operating on `[B, N, w_c, 2]`. 13 chakras × independent coefficients
enable specialization: narrow chakras evolve fast (detail), wide chakras
smooth (global structure).

Integration is DIFFERENTIABLE (no torch.no_grad, no FFT ops).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn

from _chakra_utils import PHI, PHI_INV


class ChakraDynamics(nn.Module):
    """Self-contained PDE dynamics for one chakra of width w.

    Operates on [B, N, w, 2] tensors. All PDE operations use finite
    differences (no torch.fft) for ROCm compatibility. Integration is
    fully differentiable — gradients flow through PDE coefficients.

    Architecture:
        Source [B,N,w,2] → 5-step Strang-split integration
        → nonlinear (advection + QP + NL coupling + breath + source)
        → linear step (diffusion + dispersion)
        → normalization

    Loss terms (computed externally, gradient flows through here):
        Self-prediction: ||predictor(psi[:,i]) - psi[:,i+1]||²
        Focal coherence: ||psi_L[0] - psi_R[0]||²
        Token CE: gradients flow through to PDE coefficients and embedder
    """

    def __init__(self, w: int, N: int, max_batch_size: int):
        super().__init__()
        self.w = w
        self.N = N

        # ── Per-chakra PDE coefficients (10 total) ──
        self.nu_logit = nn.Parameter(torch.tensor(-2.3))
        self.hbar_logit = nn.Parameter(torch.tensor(-2.3))
        self.mass_logit = nn.Parameter(torch.tensor(2.3))
        self.g_logit = nn.Parameter(torch.tensor(-2.2))
        self.chi_logit = nn.Parameter(torch.tensor(-2.9))
        self.A_B_logit = nn.Parameter(torch.tensor(-2.3))
        self.advection_logit = nn.Parameter(torch.tensor(-2.3))
        self.alpha_logit = nn.Parameter(torch.tensor(-2.3))
        self.gamma_logit = nn.Parameter(torch.tensor(-3.0))
        self.kappa_logit = nn.Parameter(torch.zeros(4))

        # ── Predictors (one per hemisphere) ──
        self.predictor = nn.Linear(w, w)
        nn.init.normal_(self.predictor.weight, std=0.01)
        nn.init.zeros_(self.predictor.bias)
        self.predictor_rev = nn.Linear(w, w)
        nn.init.normal_(self.predictor_rev.weight, std=0.01)
        nn.init.zeros_(self.predictor_rev.bias)

        # ── Persistent state buffers ──
        self.register_buffer(
            "psi_left", torch.zeros(max_batch_size, N, w, 2)
        )
        self.register_buffer(
            "psi_right", torch.zeros(max_batch_size, N, w, 2)
        )

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
        return {
            "nu": nu, "hbar": hbar, "mass": mass,
            "g": g, "chi": chi, "A_B": A_B,
            "advection_strength": adv,
            "alpha": alpha, "gamma": gamma, "kappa": kappa,
        }

    def _magnitude(self, psi: torch.Tensor) -> torch.Tensor:
        """rho = psi_0² + psi_1², shape [B,N,w]."""
        return psi.pow(2).sum(dim=-1)

    def _gradient(self, psi: torch.Tensor) -> torch.Tensor:
        """Central finite-difference gradient, shape [B,N,w,2].
        Zero-gradient boundaries."""
        grad = torch.zeros_like(psi)
        grad[:, 1:-1] = (psi[:, 2:] - psi[:, :-2]) / 2.0
        grad[:, 0] = psi[:, 1] - psi[:, 0]
        grad[:, -1] = psi[:, -1] - psi[:, -2]
        return grad
    def _current(self, psi: torch.Tensor, grad: torch.Tensor) -> torch.Tensor:
        """J = psi_0·grad_1 − psi_1·grad_0, shape [B,N,w]."""
        return psi[..., 0] * grad[..., 1] - psi[..., 1] * grad[..., 0]

    def _advection(
        self, psi: torch.Tensor, grad: torch.Tensor,
    ) -> torch.Tensor:
        """Complex ψ·∇ψ in paired-real form (quadratic), shape [B,N,w,2].

        adv = -PHI_INV · s(ch) · [adv_0, adv_1]
        where adv_0 = psi_0·∇psi_0 − psi_1·∇psi_1
              adv_1 = psi_0·∇psi_1 + psi_1·∇psi_0
        """  # noqa: RUF002
        s = torch.sigmoid(self.advection_logit)
        psi_0, psi_1 = psi[..., 0], psi[..., 1]
        g_0, g_1 = grad[..., 0], grad[..., 1]
        adv_0 = psi_0 * g_0 - psi_1 * g_1
        adv_1 = psi_0 * g_1 + psi_1 * g_0
        adv = torch.stack([adv_0, adv_1], dim=-1)
        return -PHI_INV * s * adv

    def _quantum_potential(
        self, rho: torch.Tensor, hbar: float, mass: float,
    ) -> torch.Tensor:
        """Bohm QP: q = -(ℏ²/2m²)·∇²(M^β)/M^β, shape [B,N,w].

        β = φ⁻¹/2, finite-difference Laplacian.
        """
        beta = PHI_INV / 2.0
        phi_amp = rho ** beta
        lap = torch.zeros_like(phi_amp)
        lap[:, 1:-1] = phi_amp[:, 2:] + phi_amp[:, :-2] - 2.0 * phi_amp[:, 1:-1]
        lap[:, 0] = phi_amp[:, 1] - phi_amp[:, 0]
        lap[:, -1] = phi_amp[:, -2] - phi_amp[:, -1]
        q = -(hbar ** 2) / (2.0 * mass ** 2) * lap / phi_amp.clamp_min(1e-2)
        return q

    def _nonlinear_coupling(
        self, rho: torch.Tensor, g: float, psi: torch.Tensor,
    ) -> torch.Tensor:
        """nl = g · M · psi, shape [B,N,w,2]."""
        return g * rho.unsqueeze(-1) * psi

    def _breath_force(
        self, breath_val: float, A_B: float, psi: torch.Tensor,
    ) -> torch.Tensor:
        """b = A_B · breath_val · psi, shape [B,N,w,2]."""
        return A_B * breath_val * psi

    def _linear_step(
        self, psi: torch.Tensor, nu: float, chi: float, dt: float,
    ) -> torch.Tensor:
        """Finite-difference diffusion + dispersion, shape [B,N,w,2]."""
        # Diffusion
        lap = torch.zeros_like(psi)
        lap[:, 1:-1] = psi[:, 2:] + psi[:, :-2] - 2.0 * psi[:, 1:-1]
        lap[:, 0] = psi[:, 1] - psi[:, 0]
        lap[:, -1] = psi[:, -2] - psi[:, -1]
        psi = psi + nu * dt * lap
        # Dispersion (symplectic Euler)
        grad_1 = torch.zeros_like(psi[..., 0])
        grad_1[:, 1:-1] = (psi[:, 2:, :, 1] - psi[:, :-2, :, 1]) / 2.0
        new_0 = psi[..., 0] - chi * dt * grad_1

        grad_new_0 = torch.zeros_like(new_0)
        grad_new_0[:, 1:-1] = (new_0[:, 2:] - new_0[:, :-2]) / 2.0

        new_1 = psi[..., 1] + chi * dt * grad_new_0
        return torch.stack([new_0, new_1], dim=-1)

    def _normalize(self, psi: torch.Tensor) -> torch.Tensor:
        """Per-position normalization by max channel magnitude, [B,N,w,2]."""
        rho = self._magnitude(psi)
        max_amp = rho.sqrt().max(dim=-1, keepdim=True).values
        return psi / max_amp.unsqueeze(-1).clamp_min(1e-8)

    # ─── Integration (DIFFERENTIABLE — no no_grad) ────────────────

    def integrate(
        self,
        source_L: torch.Tensor,
        source_R: torch.Tensor,
        T: float = 1.0,
        dt: float = 0.2,
        breath_phase: float = 0.0,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Split-step Strang integration for this chakra.

        DIFFERENTIABLE — no torch.no_grad(). Gradients flow through
        PDE coefficients to loss terms.

        Args:
            source_L: [B, N, w, 2] — left hemisphere forcing.
            source_R: [B, N, w, 2] — right hemisphere forcing.
            T: Total integration time.
            dt: Time step size.
            breath_phase: Scalar phase for breath modulation.

        Returns:
            (psi_L, psi_R): [B, N, w, 2] — final field states.
        """
        B = source_L.shape[0]
        device = source_L.device

        # Clone persistent state (distinct from buffer, grad-compatible)
        psi_L = self.psi_left[:B].clone().to(device)
        psi_R = self.psi_right[:B].clone().to(device)

        params = self.get_params()
        n_steps = max(int(T / dt), 1)

        for step in range(n_steps):
            t = torch.tensor(step / n_steps + breath_phase, device=device)
            breath_t = 0.5 * (
                torch.sin(2 * math.pi * t)
                + torch.sin(2 * math.pi * t * PHI_INV)
            )

            # ── Half-step A: nonlinear ──
            rho_L = self._magnitude(psi_L)
            rho_R = self._magnitude(psi_R)
            grad_L = self._gradient(psi_L)
            grad_R = self._gradient(psi_R)

            adv_L = self._advection(psi_L, grad_L)
            adv_R = self._advection(psi_R, grad_R)
            qp_L = self._quantum_potential(rho_L, params["hbar"], params["mass"])
            qp_R = self._quantum_potential(rho_R, params["hbar"], params["mass"])
            nl_L = self._nonlinear_coupling(rho_L, params["g"], psi_L)
            nl_R = self._nonlinear_coupling(rho_R, params["g"], psi_R)
            b_L = self._breath_force(breath_t, params["A_B"], psi_L)
            b_R = self._breath_force(breath_t, params["A_B"], psi_R)

            dpsi_L = adv_L + qp_L.unsqueeze(-1) * psi_L + nl_L + b_L + source_L
            dpsi_R = adv_R + qp_R.unsqueeze(-1) * psi_R + nl_R + b_R + source_R

            psi_L = psi_L + 0.5 * dt * dpsi_L
            psi_R = psi_R + 0.5 * dt * dpsi_R
            psi_L = psi_L.clamp(-1e3, 1e3)
            psi_R = psi_R.clamp(-1e3, 1e3)

            # ── Linear step ──
            psi_L = self._linear_step(psi_L, params["nu"], params["chi"], dt)
            psi_R = self._linear_step(psi_R, params["nu"], params["chi"], dt)

            # ── Half-step B: nonlinear ──
            rho_L = self._magnitude(psi_L)
            rho_R = self._magnitude(psi_R)
            grad_L = self._gradient(psi_L)
            grad_R = self._gradient(psi_R)

            adv_L = self._advection(psi_L, grad_L)
            adv_R = self._advection(psi_R, grad_R)
            qp_L = self._quantum_potential(rho_L, params["hbar"], params["mass"])
            qp_R = self._quantum_potential(rho_R, params["hbar"], params["mass"])
            nl_L = self._nonlinear_coupling(rho_L, params["g"], psi_L)
            nl_R = self._nonlinear_coupling(rho_R, params["g"], psi_R)
            b_L = self._breath_force(breath_t, params["A_B"], psi_L)
            b_R = self._breath_force(breath_t, params["A_B"], psi_R)

            dpsi_L = adv_L + qp_L.unsqueeze(-1) * psi_L + nl_L + b_L + source_L
            dpsi_R = adv_R + qp_R.unsqueeze(-1) * psi_R + nl_R + b_R + source_R

            psi_L = psi_L + 0.5 * dt * dpsi_L
            psi_R = psi_R + 0.5 * dt * dpsi_R
            psi_L = psi_L.clamp(-1e3, 1e3)
            psi_R = psi_R.clamp(-1e3, 1e3)

            # ── Normalize ──
            psi_L = self._normalize(psi_L)
            psi_R = self._normalize(psi_R)

        # Store back to persistent buffers (detached — no autograd through state)
        self.psi_left[:B] = psi_L.detach()
        self.psi_right[:B] = psi_R.detach()
        return psi_L, psi_R

    # ─── State management ─────────────────────────────────────────

    def reset_state(self) -> None:
        self.psi_left.zero_()
        self.psi_right.zero_()

    def advance_breath(self) -> None:  # noqa: PLW3201
        """Advance breath phase by φ⁻¹·dt (called externally)."""
        # breath_phase is on DualFluidField, not per chakra
        pass

    # ─── Qi diagnostic ────────────────────────────────────────────

    @torch.no_grad()
    def get_qi(self, psi_L: torch.Tensor, psi_R: torch.Tensor) -> Dict[str, float]:
        """Direct Qi as (E, J) 2-vector, shape scalars.

        E = M²/(M+φ⁻²), J = psi_0·∇psi_1 − psi_1·∇psi_0
        """
        M_L = psi_L.pow(2).sum(dim=-1)
        M_R = psi_R.pow(2).sum(dim=-1)

        grad_L = self._gradient(psi_L)
        grad_R = self._gradient(psi_R)
        J_L = self._current(psi_L, grad_L)
        J_R = self._current(psi_R, grad_R)

        phi_inv_sq = PHI_INV ** 2
        E_L = M_L ** 2 / (M_L + phi_inv_sq)
        E_R = M_R ** 2 / (M_R + phi_inv_sq)
        E_focal = E_L * E_R / (E_L + E_R + phi_inv_sq)
        J_focal = J_L - J_R

        return {
            "E_L_mean": float(E_L.mean()),
            "E_R_mean": float(E_R.mean()),
            "J_L_mean": float(J_L.mean()),
            "J_R_mean": float(J_R.mean()),
            "E_focal_mean": float(E_focal.mean()),
            "J_focal_mean": float(J_focal.mean()),
        }
