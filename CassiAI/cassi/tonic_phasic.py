#!/usr/bin/env python3
"""
TonicPhasic — slow/fast field channels.

Biological neurons have two activity modes:
  - Tonic:  slow baseline accumulation at breath rate.  Carries the
    "mood" or baseline arousal of the field.
  - Phasic: fast, event-driven bursts triggered by high Qi (surprise).

The tonic channel is an EMA: ψ_tonic[t] = (1−φ⁻¹)·ψ_tonic[t−1] + φ⁻¹·ψ[t].
The phasic channel is ψ[t] scaled by a sigmoid-gated Qi spike.
The combined output is ψ_combined = ψ_tonic + ψ_phasic.
"""

from typing import Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi._chakra_utils import PHI, PHI_INV


class TonicPhasic(nn.Module):
    """Tonic (slow EMA) and phasic (Qi-triggered) field channels.

    Args:
        max_batch_size: Maximum batch size for persistent buffers.
    """

    def __init__(self, max_batch_size: int = 256):
        super().__init__()
        self.theta_Q_logit = nn.Parameter(torch.tensor(1.0))
        self.register_buffer('psi_tonic_re', torch.zeros(max_batch_size, 1, 1))
        self.register_buffer('psi_tonic_im', torch.zeros(max_batch_size, 1, 1))

    def reset_state(self) -> None:
        """Zero the tonic EMA buffers."""
        self.psi_tonic_re.zero_()
        self.psi_tonic_im.zero_()

    def resize_buffers(self, batch_size: int) -> None:
        """Resize persistent buffers."""
        for name in ('psi_tonic_re', 'psi_tonic_im'):
            old = getattr(self, name)
            if old.shape[0] == batch_size:
                continue
            new = torch.zeros(batch_size, 1, 1, device=old.device, dtype=old.dtype)
            n_copy = min(old.shape[0], batch_size)
            new[:n_copy] = old[:n_copy]
            self.register_buffer(name, new)

    def forward(self, psi_real: torch.Tensor, psi_imag: torch.Tensor,
                Q: torch.Tensor, B: int
                ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Combine tonic and phasic channels.

        Args:
            psi_real: [B, N, d] field real.
            psi_imag: [B, N, d] field imag.
            Q: [B, N, d] pointwise Qi.
            B: Actual batch size.

        Returns:
            psi_out_re, psi_out_im: [B, N, d] combined field.
        """
        # ── Tonic EMA (use .data to avoid in-place autograd version conflict) ──
        psi_m_re = psi_real.mean(dim=(1, 2))  # [B]
        psi_m_im = psi_imag.mean(dim=(1, 2))  # [B]
        tonic_new_re = ((1.0 - PHI_INV) * self.psi_tonic_re.data[:B, 0, 0]
                        + PHI_INV * psi_m_re)  # [B]
        tonic_new_im = ((1.0 - PHI_INV) * self.psi_tonic_im.data[:B, 0, 0]
                        + PHI_INV * psi_m_im)  # [B]
        self.psi_tonic_re.data[:B, 0, 0] = tonic_new_re
        self.psi_tonic_im.data[:B, 0, 0] = tonic_new_im

        # ── Phasic: Qi-triggered burst ──
        Q_mean = Q.mean(dim=-1, keepdim=True)  # [B, N, 1]
        theta_Q = F.softplus(self.theta_Q_logit)
        Q_spike = torch.sigmoid((Q_mean - theta_Q) / 0.1)

        psi_phasic_re = psi_real * Q_spike
        psi_phasic_im = psi_imag * Q_spike

        # ── Combine ──
        tonic_val = self.psi_tonic_re.data[:B, 0, 0]  # [B], .data avoids version conflict
        tonic_scale = tonic_val.unsqueeze(1).unsqueeze(-1)  # [B, 1, 1]
        gain = (tonic_scale * Q_spike).clamp(max=PHI)
        psi_out_re = psi_real * (1.0 + gain)
        psi_out_im = psi_imag * (1.0 + gain)
        return psi_out_re, psi_out_im
