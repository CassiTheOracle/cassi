#!/usr/bin/env python3
"""
SpatialCoupling — φ-scaled lateral diffusion across positions.

Real neural tissue has horizontal connections.  Adjacent positions in the
field exchange energy through a φ-scaled decay kernel:

    ψ[i] += α · Σ_{j ≠ i} φ^{−|i−j|/λ} · (ψ[j] − ψ[i])

where λ = φ·N is the characteristic decay length.
"""

from typing import Tuple

import torch
import torch.nn as nn

from cassi._chakra_utils import PHI, PHI_INV


class SpatialCoupling(nn.Module):
    """φ-scaled spatial diffusion across N positions.

    A learnable scalar α (sigmoid-gated to [0,1]) controls diffusion strength.
    The coupling kernel is purely structural (φ-scaled, not learned).

    Args:
        N: Number of positions in the sequence.
    """

    def __init__(self, N: int):
        super().__init__()
        self.N = N

        # ── Learnable diffusion strength ──
        self.alpha_logit = nn.Parameter(torch.tensor(-3.0))

        # ── Structural coupling kernel (φ-scaled, precomputed) ──
        dist = (torch.arange(N, dtype=torch.float32).unsqueeze(1)
                - torch.arange(N, dtype=torch.float32).unsqueeze(0))
        decay_length = PHI * N
        kernel = PHI ** (-torch.abs(dist) / decay_length)
        kernel = kernel / kernel.sum(dim=1, keepdim=True).clamp_min(1e-12)
        kernel.fill_diagonal_(0.0)  # no self-coupling via kernel
        self.register_buffer('kernel', kernel)  # [N, N]

    def forward(self, psi_real: torch.Tensor, psi_imag: torch.Tensor
                ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Apply spatial diffusion to the field.

        Args:
            psi_real: [B, N, d] field real part.
            psi_imag: [B, N, d] field imaginary part.

        Returns:
            psi_real_out, psi_imag_out: [B, N, d] diffused field.
        """
        alpha = torch.sigmoid(self.alpha_logit)  # [0, 1]

        # Mean over d for the coupling signal (scalar per position)
        re_mean = psi_real.mean(dim=-1, keepdim=True)  # [B, N, 1]
        im_mean = psi_imag.mean(dim=-1, keepdim=True)

        # kernel[i,j] · (mean[j] − mean[i]) summed over j
        # ψ[i] ← ψ[i] + α · Σ_j K[i,j] · (ψ̅[j] − ψ̅[i])
        diff_re = (self.kernel.unsqueeze(0).unsqueeze(-1)   # [1, N, N, 1]
                   * (re_mean.unsqueeze(2) - re_mean.unsqueeze(1))
                   ).sum(dim=2)  # [B, N, 1]
        diff_im = (self.kernel.unsqueeze(0).unsqueeze(-1)
                   * (im_mean.unsqueeze(2) - im_mean.unsqueeze(1))
                   ).sum(dim=2)  # [B, N, 1]

        return psi_real + alpha * diff_re, psi_imag + alpha * diff_im
