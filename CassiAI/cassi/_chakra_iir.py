#!/usr/bin/env python3
"""
ChakraIIRBank — one canonical φ-damped IIR for the Cassi resonant field.

Implements the second-order recurrence:
    h1[t] = a1 · h1[t−1] + a2 · h2[t−1] + input
    h2[t] = h1[t−1]
    y[t]  = input + h1[t]

where a1 = 2·ρ·cos(θ), a2 = −ρ², ρ = φ⁻¹ (0.618), and θ is a per-chakra
frequency stored as a logit parameter.

This matches the IIR used in QiField._field_step_pre_ctrl (lines 616–627).
"""

import math
from typing import List, Tuple

import torch
import torch.nn as nn

from cassi._chakra_utils import PHI_INV, phi_chakra_widths, chakra_id_tensor


class ChakraIIRBank(nn.Module):
    """Canonical φ-damped second-order IIR bank.

    The bank owns C chakras, each operating on a slice of the field of width
    w_c.  Frequencies θ_c are stored as logits (so θ = sigmoid(logit)·π) and
    are φ-spaced at init: θ_c ∝ φ⁻ᶜ.

    Modes:
        vectorized : theta is broadcast over chakra dimensions (QiField style).
                      h1/h2: [B, N, d] with per-dimension frequency from
                      chakra_id lookups.
        per_chakra : theta is applied per-chakra, h1/h2: [B, C, max_W] with
                      padding beyond each chakra's width zeroed.
        step       : sequential per-position recurrence (legacy compatibility).

    Args:
        d: field dimension.
        C: number of chakras (default 13).
        widths: list of C integer widths.  If None, computed from d and C.
        mode: one of 'vectorized', 'per_chakra', 'step'.
    """

    def __init__(
        self,
        d: int,
        C: int = 13,
        widths: List[int] | None = None,
        mode: str = "vectorized",
    ):
        super().__init__()
        self.d = d
        self.C = C
        self.mode = mode
        self.widths = widths if widths is not None else phi_chakra_widths(d, C)

        # Register chakra id mapping for vectorized mode
        self.register_buffer(
            "chakra_id",
            chakra_id_tensor(self.widths),
            persistent=False,
        )

        # ── Per-chakra frequencies as logits ──
        # Spiritual mapping: crown (c=0, widest, violet) → fast IIR (high θ),
        #                    root  (c=C-1, narrowest, red) → slow IIR (low θ).
        # theta[c=0]  = log(0.999 / 0.001) ≈ 6.9  → sigmoid≈0.999 → θ≈π   (fastest)
        # theta[c=12] = log(0.003 / 0.997) ≈ -5.8 → sigmoid≈0.003 → θ≈0.01 (slowest)
        # With PHI_INV^c, crown gets PHI_INV^0 = 1.0 → fast, root gets PHI_INV^12 ≈ 0.003 → slow.
        theta_init = torch.zeros(C)
        for c in range(C):
            ratio = max(0.001, min(0.999, PHI_INV ** c))
            theta_init[c] = math.log(ratio / (1.0 - ratio))
        self.theta = nn.Parameter(theta_init)
        
        # ── Per-chakra rho (pole radius) ──
        # Narrow chakras with slow IIR need tighter damping to prevent DC
        # accumulation. Wide chakras with fast IIR can handle looser damping.
        # Range: root (c=C-1) → 0.50 (tight, fast decay)
        #        crown (c=0)  → 0.75 (loose, sustained oscillation)
        rho_per_c = torch.tensor([
            0.75 - 0.25 * (c / (C - 1)) for c in range(C)
        ], dtype=torch.float32)
        # Broadcast to per-dimension rho via chakra_id mapping
        per_dim_rho = rho_per_c[self.chakra_id]  # [d]
        self.register_buffer('default_rho', per_dim_rho, persistent=False)


    def compute_coefficients(
        self,
        batch_shape: torch.Size,
        rho: float | None = None,
        device: torch.device | None = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Return a1, a2 coefficient tensors broadcast to batch_shape.

        Useful when the caller wants to manage h1/h2 state externally
        (e.g. QiField which applies the IIR to real and imag separately
        with shared state).

        Returns:
            a1: [*batch_shape, d]  with torch.cos(theta) factored in.
            a2: [*batch_shape, d]  scalar broadcast.
        """
        # Per-chakra rho: uses self.default_rho (tight on root/narrow, loose on crown/wide)
        # when no explicit rho is passed. Supports both scalar and per-dimension rho.
        if rho is None:
            rho = self.default_rho  # [d], or scalar in legacy mode
            if rho is None:
                rho = PHI_INV  # fallback if buffer not registered
        theta_sig = torch.sigmoid(self.theta)  # [C]
        theta_full = theta_sig[self.chakra_id]  # [d]
        a1 = 2.0 * rho * torch.cos(theta_full)      # [d]
        a2 = -(rho ** 2)                               # scalar or [d]
        # Broadcast to [*batch_shape, d]
        view_shape = [1] * len(batch_shape) + [-1]
        a1 = a1.view(*view_shape).expand(*batch_shape, -1)
        a2 = a2.view(*view_shape).expand(*batch_shape, -1)
        return a1, a2

    def forward(
        self,
        x: torch.Tensor,
        h1: torch.Tensor,
        h2: torch.Tensor,
        rho: float | None = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Apply one IIR step.

        Args:
            x: input [B, N, d].
            h1: first-order state [B, N, d] (vectorized) or [B, C, W] (per_chakra).
            h2: second-order state, same shape as h1.
            rho: damping factor (default PHI_INV ≈ 0.618).

        Returns:
            (y, h1_new, h2_new) where y is the IIR output (same shape as x),
            and h1_new, h2_new are the updated states.
        """
        if self.mode == "vectorized":
            return self._forward_vectorized(x, h1, h2, rho)
        elif self.mode == "per_chakra":
            return self._forward_per_chakra(x, h1, h2, rho)
        else:
            return self._forward_step(x, h1, h2, rho)

    def _forward_vectorized(
        self,
        x: torch.Tensor,
        h1: torch.Tensor,
        h2: torch.Tensor,
        rho: float | None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Vectorized mode: frequency per field dimension via chakra_id lookup."""
        rho = PHI_INV if rho is None else rho
        theta_sig = torch.sigmoid(self.theta)  # [C]
        # Expand to full dimension
        theta_full = theta_sig[self.chakra_id]  # [d]

        a1 = 2.0 * rho * torch.cos(theta_full)
        a2 = -(rho ** 2)

        # Per-sample input mean for state tracking
        inp = x.mean(dim=1, keepdim=True)  # [B, 1, d]

        h1_new = a1 * h1 + a2 * h2 + inp
        y = x + h1_new
        h2_new = h1

        return y, h1_new, h2_new

    def _forward_per_chakra(
        self,
        x: torch.Tensor,
        h1: torch.Tensor,
        h2: torch.Tensor,
        rho: float | None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Per-chakra mode: independent IIR per chakra with padding."""
        rho = PHI_INV if rho is None else rho
        theta_sig = torch.sigmoid(self.theta).view(1, self.C, 1)  # [1, C, 1]

        a1 = 2.0 * rho * torch.cos(theta_sig)
        a2 = -(rho ** 2)

        inp = x.mean(dim=1, keepdim=True)  # aggregate over positions

        h1_new = a1 * h1 + a2 * h2 + inp
        y = x + h1_new
        h2_new = h1

        return y, h1_new, h2_new

    def _forward_step(
        self,
        x: torch.Tensor,
        h1: torch.Tensor,
        h2: torch.Tensor,
        rho: float | None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Sequential (step) mode — identical recurrence, alias for vectorized."""
        return self._forward_vectorized(x, h1, h2, rho)

    def extra_state_keys(self) -> List[str]:
        return ["iir_h1", "iir_h2"]

    def __repr__(self):
        return (
            f"ChakraIIRBank(d={self.d}, C={self.C}, mode={self.mode}, "
            f"widths={self.widths})"
        )
