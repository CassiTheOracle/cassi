#!/usr/bin/env python3
"""
ResonantField — per-element IIR resonator bank (replaces PredictionOperator).

Every one of the d field dimensions is its own resonator with chakra-structured
damping ρ_c and frequency θ_c.  Self-prediction P[ψ] emerges from the field's
natural resonant dynamics — no separate "prediction operator".

BrainTuner modulations (delta_rho, delta_theta, delta_gamma) flow through
forward() as tensors, preserving the gradient path.
"""

import math
from typing import List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi._chakra_utils import PHI, PHI_INV, phi_chakra_widths


class ResonantField(nn.Module):
    """Per-element IIR resonator bank with chakra-structured coefficients."""

    def __init__(self, d: int, C: int = 13, N: int = 128,
                 widths: Optional[List[int]] = None,
                 max_batch_size: int = 256):
        super().__init__()
        self.d, self.C, self.N = d, C, N
        self.widths = widths if widths is not None else phi_chakra_widths(d, C)
        assert len(self.widths) == C and sum(self.widths) == d
        self.offsets = [sum(self.widths[:c]) for c in range(C)]

        # Structural chakra coefficients
        self.rho_base = [PHI ** (-c / C) for c in range(C)]
        self.theta_base = [2.0 * math.pi * (PHI ** (c % 8)) / (PHI ** 8) for c in range(C)]

        # Learned per-element feed/feedback
        self.b0_logit = nn.Parameter(torch.zeros(d))
        self.b1_logit = nn.Parameter(torch.zeros(d))

        # Cross-chakra diffusion rate
        self.gamma_logit = nn.Parameter(torch.tensor(0.1))

        # Persistent IIR buffers: 6 × [max_bs, N, d]
        for name in ('h_real', 'h_imag', 'h_prev_real', 'h_prev_imag',
                     'x_prev_real', 'x_prev_imag'):
            self.register_buffer(name, torch.zeros(max_batch_size, N, d))

    # ── State Management ──

    def reset_state(self) -> None:
        for b in ('h_real', 'h_imag', 'h_prev_real', 'h_prev_imag',
                  'x_prev_real', 'x_prev_imag'):
            getattr(self, b).zero_()

    def resize_buffers(self, bs: int, device: torch.device, dtype: torch.dtype) -> None:
        for name in ('h_real', 'h_imag', 'h_prev_real', 'h_prev_imag',
                     'x_prev_real', 'x_prev_imag'):
            old = getattr(self, name)
            if old.shape[0] == bs:
                continue
            new = torch.zeros(bs, self.N, self.d, device=device, dtype=dtype)
            n = min(old.shape[0], bs)
            new[:n] = old[:n]
            self.register_buffer(name, new)

    def get_checkpoint_buffer_names(self) -> Tuple[str, ...]:
        return ('h_real', 'h_imag', 'h_prev_real', 'h_prev_imag',
                'x_prev_real', 'x_prev_imag')

    # ── Forward ──

    def forward(self, psi_real: torch.Tensor, psi_imag: torch.Tensor,
                B: int,
                delta_rho: Optional[torch.Tensor] = None,
                delta_theta: Optional[torch.Tensor] = None,
                delta_gamma: Optional[torch.Tensor] = None
                ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """One resonant prediction step.

        Returns (P_re, P_im, eps2) all [B, N, d].
        """
        b0 = torch.sigmoid(self.b0_logit)
        b1 = torch.sigmoid(self.b1_logit)
        gamma = torch.sigmoid(self.gamma_logit)

        P_re, P_im = self._chakra_iir(psi_real, psi_imag, b0, b1, B,
                                       delta_rho, delta_theta)
        P_re, P_im = self._chakra_diffusion(P_re, P_im, gamma, B, delta_gamma)

        with torch.no_grad():
            self.h_prev_real[:B].copy_(self.h_real[:B])
            self.h_prev_imag[:B].copy_(self.h_imag[:B])
            self.x_prev_real[:B].copy_(psi_real.detach())
            self.x_prev_imag[:B].copy_(psi_imag.detach())
            self.h_real[:B].copy_(P_re.detach())
            self.h_imag[:B].copy_(P_im.detach())

        eps2 = (psi_real - P_re) ** 2 + (psi_imag - P_im) ** 2
        return P_re, P_im, eps2

    # ── Per-element IIR ──

    def _chakra_iir(self, psi_real: torch.Tensor, psi_imag: torch.Tensor,
                    b0: torch.Tensor, b1: torch.Tensor, B: int,
                    delta_rho: Optional[torch.Tensor] = None,
                    delta_theta: Optional[torch.Tensor] = None
                    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Per-element IIR.  When modulation tensors are provided, applies
        ρ_c_eff = ρ_c·(1+tanh(δ_ρ)), θ_c_eff = θ_c + δ_θ.

        All `a1`/`a2` tensors are broadcast to [B, N, dc] via unsqueeze.
        """
        h_re = self.h_real[:B].detach().clone()
        h_im = self.h_imag[:B].detach().clone()
        h_pr = self.h_prev_real[:B].detach().clone()
        h_pi = self.h_prev_imag[:B].detach().clone()
        x_pr = self.x_prev_real[:B].detach().clone()
        x_pi = self.x_prev_imag[:B].detach().clone()

        P_re = torch.zeros_like(psi_real)
        P_im = torch.zeros_like(psi_imag)

        for c in range(self.C):
            off = self.offsets[c]
            dc = self.widths[c]
            sl = slice(off, off + dc)

            # Compute effective ρ, θ (modulated tensors or base scalars)
            if delta_rho is not None:
                rho_c = self.rho_base[c] * (1.0 + torch.tanh(delta_rho[:, c]))
            else:
                rho_c = self.rho_base[c]

            if delta_theta is not None:
                theta_c = self.theta_base[c] + delta_theta[:, c]
            else:
                theta_c = self.theta_base[c]

            # IIR coefficients
            if isinstance(rho_c, torch.Tensor):
                # [B] → [B, 1, 1] to broadcast with [B, N, dc]
                cos_t = torch.cos(theta_c if isinstance(theta_c, torch.Tensor)
                                  else torch.tensor(theta_c, device=psi_real.device))
                a1 = (2.0 * rho_c * cos_t).view(B, 1, 1)
                a2 = (-(rho_c ** 2)).view(B, 1, 1)
            else:
                cos_t = math.cos(theta_c)
                a1 = 2.0 * rho_c * cos_t
                a2 = -(rho_c ** 2)

            P_re[:, :, sl] = (a1 * h_re[:, :, sl]
                              + a2 * h_pr[:, :, sl]
                              + b0[sl] * psi_real[:, :, sl]
                              + b1[sl] * x_pr[:, :, sl])
            P_im[:, :, sl] = (a1 * h_im[:, :, sl]
                              + a2 * h_pi[:, :, sl]
                              + b0[sl] * psi_imag[:, :, sl]
                              + b1[sl] * x_pi[:, :, sl])

        return P_re, P_im

    # ── Cross-chakra diffusion ──

    def _chakra_diffusion(self, P_re: torch.Tensor, P_im: torch.Tensor,
                          gamma_base: torch.Tensor, B: int,
                          delta_gamma: Optional[torch.Tensor] = None
                          ) -> Tuple[torch.Tensor, torch.Tensor]:
        """φ-scaled cross-chakra diffusion (replaces Linear(13,13))."""
        gamma = (gamma_base * (1.0 + torch.tanh(delta_gamma.mean()))
                 if delta_gamma is not None else gamma_base)

        chakra_mean_re = []
        chakra_mean_im = []
        for c in range(self.C):
            off = self.offsets[c]
            dc = self.widths[c]
            chakra_mean_re.append(P_re[:, :, off:off + dc].mean(dim=(1, 2)))
            chakra_mean_im.append(P_im[:, :, off:off + dc].mean(dim=(1, 2)))

        for c in range(self.C):
            off = self.offsets[c]
            dc = self.widths[c]
            sl = slice(off, off + dc)
            delta_re, delta_im = 0.0, 0.0
            denom = 0.0

            for c2 in range(max(0, c - 2), min(self.C, c + 3)):
                if c2 == c:
                    continue
                w = PHI ** (-abs(c - c2))
                denom += w
                delta_re = delta_re + w * (chakra_mean_re[c2] - chakra_mean_re[c]) if isinstance(delta_re, torch.Tensor) else w * (chakra_mean_re[c2] - chakra_mean_re[c])
                delta_im = delta_im + w * (chakra_mean_im[c2] - chakra_mean_im[c]) if isinstance(delta_im, torch.Tensor) else w * (chakra_mean_im[c2] - chakra_mean_im[c])

            scale = gamma / (denom + 1e-8)
            P_re[:, :, sl] += (scale * delta_re).unsqueeze(1).unsqueeze(-1)
            P_im[:, :, sl] += (scale * delta_im).unsqueeze(1).unsqueeze(-1)

        return P_re, P_im
