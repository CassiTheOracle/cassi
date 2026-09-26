#!/usr/bin/env python3
"""DualFluidField — Container for 13 independent per-chakra PDE fields.

Each chakra gets its own `ChakraDynamics` instance with independent PDE
coefficients, state buffers, and predictor. No cross-chakra coupling.

All tensor shapes follow [B, N, d, 2] convention at the container level.
Internally, operations are [B, N, w_c, 2] per chakra.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import torch
import torch.nn as nn
from _chakra_utils import PHI, PHI_INV
from chakra_dynamics import ChakraDynamics


class DualFluidField(nn.Module):
    """Container for 13 independent per-chakra PDE fields.

    Splits input by chakra bandwidth, runs independent PDE integration,
    then merges outputs. No cross-chakra coupling.
    """

    def __init__(
        self, d: int, C: int = 13, N: int = 128, max_batch_size: int = 64,
    ):
        super().__init__()
        self.d = d
        self.C = C
        self.N = N

        # ── Equal-width chakra allocation ──
        base = d // C
        rem = d - base * C
        widths = [base + 1 if c < rem else base for c in range(C)]
        self.widths = widths

        offsets = [sum(widths[:c]) for c in range(C)]
        self._chakra_start_end = [
            (offsets[c], offsets[c] + widths[c]) for c in range(C)
        ]

        # ── One independent field per chakra ──
        self.chakras = nn.ModuleList([
            ChakraDynamics(w, N, max_batch_size) for w in widths
        ])

        # ── Shared breath phase ──
        self.register_buffer("breath_phase", torch.zeros(1))

    # ─── Public API ───────────────────────────────────────────────

    def integrate(
        self,
        source_L: torch.Tensor,
        source_R: torch.Tensor,
        T: float = 1.0,
        dt: float = 0.2,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Integrate PDE for all chakras independently.

        DIFFERENTIABLE — no torch.no_grad(). Gradients flow through.

        Args:
            source_L: [B, N, d, 2] left hemisphere source.
            source_R: [B, N, d, 2] right hemisphere source.
            T: Total integration time.
            dt: Time step size.

        Returns:
            (psi_L, psi_R): [B, N, d, 2] — concatenated field.
        """
        B = source_L.shape[0]
        device = source_L.device
        bp = self.breath_phase.item()

        psi_L_parts: List[torch.Tensor] = []
        psi_R_parts: List[torch.Tensor] = []

        for c, field in enumerate(self.chakras):
            start, end = self._chakra_start_end[c]
            src_L_c = source_L[:, :, start:end].contiguous()
            src_R_c = source_R[:, :, start:end].contiguous()

            psi_L_c, psi_R_c = field.integrate(
                src_L_c, src_R_c, T=T, dt=dt, breath_phase=bp,
            )
            psi_L_parts.append(psi_L_c)
            psi_R_parts.append(psi_R_c)

        return torch.cat(psi_L_parts, dim=2), torch.cat(psi_R_parts, dim=2)

    def get_params(self) -> Dict[str, torch.Tensor]:
        """Average coefficients across chakras (for diagnostics/loss)."""
        all_p = [c.get_params() for c in self.chakras]
        avg = {
            k: sum(p[k] for p in all_p) / len(all_p)
            for k in all_p[0]
        }
        avg["per_chakra"] = all_p
        return avg
    def get_qi(
        self, psi_L: torch.Tensor, psi_R: torch.Tensor,
    ) -> Dict[str, float]:
        """Qi diagnostic aggregated across chakras."""
        M_L = psi_L.pow(2).sum(dim=-1)
        M_R = psi_R.pow(2).sum(dim=-1)
        phi_inv_sq = PHI_INV ** 2
        E_L = M_L ** 2 / (M_L + phi_inv_sq)
        E_R = M_R ** 2 / (M_R + phi_inv_sq)
        E_focal = E_L * E_R / (E_L + E_R + phi_inv_sq)

        # Compute J via _gradient — use chakra 0's method (same for all)
        with torch.no_grad():
            grad = torch.zeros_like(psi_L)
            grad[:, 1:-1] = (psi_L[:, 2:] - psi_L[:, :-2]) / 2.0
            J = psi_L[..., 0] * grad[..., 1] - psi_L[..., 1] * grad[..., 0]

        return {
            "E_L_mean": float(E_L.mean()),
            "E_R_mean": float(E_R.mean()),
            "E_focal_mean": float(E_focal.mean()),
            "J_L_mean": float(J.mean()),
        }

    def reset_state(self) -> None:
        self.breath_phase.zero_()
        for c in self.chakras:
            c.reset_state()

    def advance_breath(self) -> None:  # noqa: PLW3201
        self.breath_phase.copy_(
            (self.breath_phase + PHI_INV * 0.1) % 1.0
        )

    def extra_repr(self) -> str:
        return (
            f"N={self.N}, d={self.d}, C={self.C}, "
            f"chakra_widths={self.widths}"
        )
