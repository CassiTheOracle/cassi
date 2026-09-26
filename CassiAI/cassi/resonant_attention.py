#!/usr/bin/env python3
"""
ResonantAttention — φ-scaled structural + content-based attention.

No learned QKV matrices.  The attention weights are a product of:

  1. Structural bias:  sin(π·φ·|i−j|/N)  — nearby positions resonate more
     at a φ-scaled wavelength.
  2. Content gate:  cos_sim(h[i], h[j])  — similarity of the combined IIR
     state (psi + multi-scale memory).

The result is softmax-normalised over j for each i (not self-attention:
diagonal is set to zero).
"""

import math
from typing import Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi._chakra_utils import PHI, PHI_INV


class ResonantAttention(nn.Module):
    """φ-scaled resonant attention — zero learned parameters.

    Args:
        N: Number of positions in the sequence.
        d: Field dimension (for softmax scaling).
    """

    def __init__(self, N: int, d: int):
        super().__init__()
        self.N = N
        self.d = d

        # ── Structural bias: sin(π·φ·|i−j|/N) ──
        dist = (torch.arange(N, dtype=torch.float32).unsqueeze(1)
                - torch.arange(N, dtype=torch.float32).unsqueeze(0))
        structural = torch.sin(math.pi * PHI * torch.abs(dist) / N)
        structural.fill_diagonal_(0.0)  # no self-attention
        self.register_buffer('structural', structural)  # [N, N]

    def forward(self, psi_real: torch.Tensor, psi_imag: torch.Tensor,
                h_combined_re: torch.Tensor, h_combined_im: torch.Tensor
                ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Apply resonant attention.

        Args:
            psi_real: [B, N, d] field real.
            psi_imag: [B, N, d] field imag.
            h_combined_re: [B, N, d] combined IIR state real (psi + memory).
            h_combined_im: [B, N, d] combined IIR state imag.

        Returns:
            psi_out_re, psi_out_im: [B, N, d] attention-enhanced field.
        """
        # ── Content similarity ──
        # Cosine similarity over the d dimension
        h_norm_re = F.normalize(h_combined_re, dim=-1)   # [B, N, d]
        h_norm_im = F.normalize(h_combined_im, dim=-1)
        # cos_sim = Re(h_conj[i] · h[j]) = real[i]·real[j] + imag[i]·imag[j]
        cos_sim = (torch.matmul(h_norm_re, h_norm_re.transpose(1, 2))
                   + torch.matmul(h_norm_im, h_norm_im.transpose(1, 2)))
        is_nan = torch.isnan(cos_sim)
        if is_nan.any():
            cos_sim = torch.nan_to_num(cos_sim, nan=0.0)

        # ── Combined attention ──
        # Scale by 1/√d for stable softmax (standard attention convention)
        attn = (self.structural.unsqueeze(0) * cos_sim
                / math.sqrt(self.d))  # [B, N, N]
        attn = F.softmax(attn, dim=-1)

        # ── Apply to field ──
        psi_out_re = torch.matmul(attn, psi_real)  # [B, N, d]
        psi_out_im = torch.matmul(attn, psi_imag)

        return psi_out_re, psi_out_im
