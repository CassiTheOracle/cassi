"""QiDynamics — Qi field evolution via source, sink, and advection.

Encapsulates the qi_step and _advect computations from QiField.
Does NOT import from cassi.qi_field.
"""

from typing import Dict, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.cord import PHI_INV


class QiDynamics(nn.Module):
    """Qi dynamics: source, sink, advection.

    Qi obeys the continuity equation: persistent memory, saturating source,
    super-linear sink, and pressure-gradient advection.  Structural calm/arousal
    around PHI_INV is hard-coded; the controller learns small deltas.

    Parameters:
        qi_eps0_log: log-softplus offset for the source's error saturation.
        sink_gamma:   super-linear sink strength.
        qi_rho:       Qi persistence (recurrence weight).
    """

    def __init__(self, d: int, qi_rho: float = PHI_INV, sink_gamma: float = PHI_INV):
        super().__init__()
        self.d = d

        # Source scale: learnable log-softplus offset
        self.qi_eps0_log = nn.Parameter(torch.zeros(1))
        # Sink strength (learnable, init to constructor arg)
        self.sink_gamma = nn.Parameter(torch.tensor(sink_gamma))
        # Qi persistence / recurrence weight (learnable, init to constructor arg)
        self.qi_rho = nn.Parameter(torch.tensor(qi_rho))

    # ── Utility ──────────────────────────────────────────────────────────

    @staticmethod
    def _complex_norm2(
        a_real: torch.Tensor,
        a_imag: torch.Tensor,
    ) -> torch.Tensor:
        """Squared magnitude of a complex tensor."""
        return a_real ** 2 + a_imag ** 2

    # ── Advection ────────────────────────────────────────────────────────

    @staticmethod
    def _advect(
        Q_transport: torch.Tensor,
        p: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Pressure-gradient advection on the spatial Qi field.

        Uses the forward-difference pressure gradient and an upwind flux
        consistent with the continuity equation ∂Q/∂t + ∇·(Q·v_Q) = ... .

        Returns:
            advection:  the advective increment [B, N, 1] (subtract from Q).
            v_Q:        advection velocity [B, N].
        """
        grad_p = torch.roll(p, shifts=-1, dims=1) - p
        v_Q = -PHI_INV * grad_p
        v_Q = v_Q.clamp(-1.0, 1.0)

        Q_spatial = Q_transport.mean(dim=-1, keepdim=True)  # [B, N, 1]
        v_Q = v_Q.unsqueeze(-1)                               # [B, N, 1]

        Q_left = torch.roll(Q_spatial, shifts=1, dims=1)
        Q_right = torch.roll(Q_spatial, shifts=-1, dims=1)
        upwind = torch.where(v_Q > 0, Q_spatial - Q_left, Q_right - Q_spatial)
        advection = v_Q * upwind
        return advection, v_Q.squeeze(-1)

    # ── Forward (Qi update) ─────────────────────────────────────────────

    def forward(
        self,
        psi_real: torch.Tensor,
        psi_imag: torch.Tensor,
        Q_field: torch.Tensor,
        P_re: torch.Tensor,
        P_im: torch.Tensor,
        eps2: torch.Tensor = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, torch.Tensor]]:
        """Qi dynamics: source, sink, advection, and diagnostics.

        Args:
            psi_real, psi_imag:  [B, N, d] field.
            Q_field:             [B, N, d] current Qi field.
            P_re, P_im:         [B, N, d] predictions.
            eps2:               optional pre-computed prediction error
                                [B, N, d]; computed internally when None.

        Returns:
            Q_new:   [B, N, d] updated Qi field (clamped ≥ 0).
            p_mean:  scalar mean pressure.
            diag:    dict with diagnostic tensors.
        """
        if eps2 is None:
            eps2 = self._complex_norm2(psi_real - P_re, psi_imag - P_im)

        psi2 = self._complex_norm2(psi_real, psi_imag)

        # Saturation scale for the prediction-error source
        eps0_sq = F.softplus(self.qi_eps0_log) + 1e-6

        # Source: self-surprise drives Qi growth
        source = (PHI_INV ** 2) * torch.tanh(eps2 / eps0_sq) * psi2

        # Sink: super-linear dissipation
        sink = self.sink_gamma * Q_field

        # Pressure = mean prediction error per position
        p = eps2.mean(dim=-1, keepdim=True).squeeze(-1)  # [B, N]

        # Pressure-gradient advection
        advection, v_Q = self._advect(Q_field, p)

        # Recurrence
        Q_new = self.qi_rho * Q_field + source - sink - advection
        Q_new = Q_new.clamp(min=0.0)

        diag = {
            'eps2_mean': eps2.mean().detach(),
            'source_mean': source.mean().detach(),
            'sink_mean': sink.mean().detach(),
            'advection_mean': advection.mean().detach(),
            'v_Q_mean': v_Q.mean().detach(),
            'psi2_mean': psi2.mean().detach(),
            'qi_rho_value': self.qi_rho.detach(),
            'sink_gamma_value': self.sink_gamma.detach(),
        }

        return Q_new, p.mean(), diag

