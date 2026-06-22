#!/usr/bin/env python3
"""
ResonantField — per-element IIR resonator bank (replaces PredictionOperator).

Every one of the d field dimensions is its own resonator with chakra-structured
damping (ρ, θ, γ).  13 chakras partition the d dimensions; each chakra has its
own resonant frequency spacing.

Precomputed unmodulated coefficients (a1_unmod, a2_unmod) enable a fused
batched path when BrainTuner modulation is inactive (generation/eval).
"""

import math
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


PHI = (1 + 5 ** 0.5) / 2
PHI_INV = 1 / PHI


def phi_chakra_widths(d: int, C: int = 13) -> list:
    """Fibonacci-based chakra partition of d dimensions."""
    fib = [1, 2]
    while len(fib) < C:
        fib.append(fib[-1] + fib[-2])
    fib = fib[:C]
    total = sum(fib)
    widths = [max(1, int(d * f / total)) for f in fib]
    # Ensure sum equals d
    diff = d - sum(widths)
    for i in range(abs(diff)):
        widths[i % C] += 1 if diff > 0 else -1
    return widths


class ResonantField(nn.Module):
    """Per-element φ-damped IIR prediction field."""

    def __init__(self, d: int, C: int = 13, N: int = 128,
                 widths: list = None, max_batch_size: int = 64):
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

        # Precompute unmodulated IIR coefficients as [d] vectors
        # Used for fast fused path when BrainTuner modulation is inactive
        a1_vec = torch.zeros(d)
        a2_vec = torch.zeros(d)
        for c in range(C):
            sl = slice(self.offsets[c], self.offsets[c] + self.widths[c])
            rho = self.rho_base[c]
            theta = self.theta_base[c]
            a1_vec[sl] = 2.0 * rho * math.cos(theta)
            a2_vec[sl] = -(rho ** 2)
        self.register_buffer('a1_unmod', a1_vec)
        self.register_buffer('a2_unmod', a2_vec)

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
        """Per-element IIR prediction.

        When BrainTuner modulation is inactive (delta_rho is None), uses
        a fused batched path — one kernel launch vs 13 loop iterations.
        """
        h_re = self.h_real[:B].detach().clone()
        h_im = self.h_imag[:B].detach().clone()
        h_pr = self.h_prev_real[:B].detach().clone()
        h_pi = self.h_prev_imag[:B].detach().clone()
        x_pr = self.x_prev_real[:B].detach().clone()
        x_pi = self.x_prev_imag[:B].detach().clone()

        # ── Fused unmodulated path (generation/eval) ──
        # One batched operation instead of 13 per-chakra kernel launches.
        if delta_rho is None:
            P_re = (self.a1_unmod * h_re + self.a2_unmod * h_pr
                    + b0 * psi_real + b1 * x_pr)
            P_im = (self.a1_unmod * h_im + self.a2_unmod * h_pi
                    + b0 * psi_imag + b1 * x_pi)
            return P_re, P_im

        # ── Modulated path (per-chakra loop, during training) ──
        P_re = torch.zeros_like(psi_real)
        P_im = torch.zeros_like(psi_imag)

        for c in range(self.C):
            off = self.offsets[c]
            dc = self.widths[c]
            sl = slice(off, off + dc)

            rho_c = self.rho_base[c] * (1.0 + torch.tanh(delta_rho[:, c]))
            theta_c = self.theta_base[c] + delta_theta[:, c]

            # IIR coefficients — batch-broadcast
            cos_t = torch.cos(theta_c if theta_c.dim() > 0
                              else torch.tensor(theta_c, device=psi_real.device))
            a1 = (2.0 * rho_c * cos_t).view(B, 1, 1)
            a2 = (-(rho_c ** 2)).view(B, 1, 1)

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
                          gamma: torch.Tensor, B: int,
                          delta_gamma: Optional[torch.Tensor] = None
                          ) -> Tuple[torch.Tensor, torch.Tensor]:
        """φ-scaled cross-chakra diffusion (scalar-per-chakra means)."""
        gamma = (gamma * (1.0 + torch.tanh(delta_gamma.mean()))
                 if delta_gamma is not None else gamma)

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
            delta_re = 0.0
            delta_im = 0.0
            denom = 0.0

            for c2 in range(max(0, c - 2), min(self.C, c + 3)):
                if c2 == c:
                    continue
                w = PHI ** (-abs(c - c2))
                denom += w
                delta_re = delta_re + w * (chakra_mean_re[c2] - chakra_mean_re[c])
                delta_im = delta_im + w * (chakra_mean_im[c2] - chakra_mean_im[c])

            scale = gamma / (denom + 1e-8)
            P_re[:, :, sl] += (scale * delta_re).unsqueeze(1).unsqueeze(-1)
            P_im[:, :, sl] += (scale * delta_im).unsqueeze(1).unsqueeze(-1)

        return P_re, P_im
