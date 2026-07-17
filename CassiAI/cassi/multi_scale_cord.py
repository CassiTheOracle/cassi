#!/usr/bin/env python3
"""
MultiScaleCord — φ-delayed temporal memory for the resonant field.

Stores delayed field states at Fibonacci distances {1,2,3,5,8} and combines
them with learned scalar weights and structural φ-scaled phase rotations.

Each step: delay line shifts, the current ψ is stored at delay-0, and a
weighted combination of all delayed states is returned as a "memory
contribution" to the current field.
"""

import math
from typing import Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi._chakra_utils import PHI, PHI_INV


class MultiScaleCord(nn.Module):
    """φ-delayed field memory with Fibonacci-spaced delays.

    Maintains K = 5 delay-line buffers at depths {1,2,3,5,8}.  Each buffer
    holds the complex field state from that many steps ago.  The return value
    is a weighted combination, where each delayed state is rotated by a
    structural φ-scaled phase offset: θ_k = 2π · φ^{−k}.

    Args:
        d: Field dimension (per-position).
        N: Number of spatial positions.
        max_batch_size: Maximum batch size for persistent buffers.
    """

    def __init__(self, d: int, N: int, max_batch_size: int = 256):
        super().__init__()
        self.d = d
        self.N = N
        self.delays = [1, 2, 3, 5, 8]  # Fibonacci subset
        self.K = len(self.delays)

        # ── Learnable combination weights ──
        self.w_logit = nn.Parameter(torch.zeros(self.K))

        # ── Structural phase offsets: θ_k = 2π · φ^{−k} ──
        self.theta_k = [2.0 * math.pi * (PHI ** (-k - 1))
                        for k in range(self.K)]

        # ── Delay-line buffers: K × 2 × [max_bs, N, d] ──
        for k in range(self.K):
            self.register_buffer(
                f'h_re_{k}', torch.zeros(max_batch_size, N, d))
            self.register_buffer(
                f'h_im_{k}', torch.zeros(max_batch_size, N, d))

    def get_checkpoint_buffer_names(self) -> tuple:
        """Names of all persistent buffers for checkpoint saving."""
        names = []
        for k in range(self.K):
            names.append(f'h_re_{k}')
            names.append(f'h_im_{k}')
        return tuple(names)

    def reset_state(self) -> None:
        """Zero all delay-line buffers."""
        for k in range(self.K):
            getattr(self, f'h_re_{k}').zero_()
            getattr(self, f'h_im_{k}').zero_()

    def resize_buffers(self, batch_size: int, device: torch.device,
                       dtype: torch.dtype) -> None:
        """Resize all delay-line buffers to new batch size."""
        for k in range(self.K):
            for comp in ('re', 'im'):
                name = f'h_{comp}_{k}'
                old = getattr(self, name)
                if old.shape[0] == batch_size:
                    continue
                new = torch.zeros(batch_size, self.N, self.d,
                                  device=device, dtype=dtype)
                n_copy = min(old.shape[0], batch_size)
                new[:n_copy] = old[:n_copy]
                self.register_buffer(name, new)

    def forward(self, psi_real: torch.Tensor, psi_imag: torch.Tensor,
                B: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """Retrieve multi-scale cord contribution.

        Args:
            psi_real: [B, N, d] current field real part.
            psi_imag: [B, N, d] current field imaginary part.
            B: Actual batch size (may be < max_batch_size).

        Returns:
            cord_re, cord_im: [B, N, d] multi-scale memory contribution.
        """
        w = F.softmax(self.w_logit, dim=0)  # [K]

        cord_re = torch.zeros_like(psi_real)
        cord_im = torch.zeros_like(psi_imag)

        for k in range(self.K):
            h_re = getattr(self, f'h_re_{k}')[:B]
            h_im = getattr(self, f'h_im_{k}')[:B]

            # Structural phase rotation: h · exp(i·θ_k)
            c = math.cos(self.theta_k[k])
            s = math.sin(self.theta_k[k])
            h_rot_re = h_re * c - h_im * s
            h_rot_im = h_re * s + h_im * c

            cord_re += w[k] * h_rot_re
            cord_im += w[k] * h_rot_im

        # ── Update delay line (shift by 1 each step) ──
        with torch.no_grad():
            for k in range(self.K - 1, 0, -1):
                src_re = getattr(self, f'h_re_{k - 1}')[:B]
                dst_re = getattr(self, f'h_re_{k}')
                dst_re[:B].copy_(src_re)
                src_im = getattr(self, f'h_im_{k - 1}')[:B]
                dst_im = getattr(self, f'h_im_{k}')
                dst_im[:B].copy_(src_im)
            # Store current ψ at delay-0
            getattr(self, 'h_re_0')[:B].copy_(psi_real.detach())
            getattr(self, 'h_im_0')[:B].copy_(psi_imag.detach())

        return cord_re, cord_im
