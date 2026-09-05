"""Quadrature-aware readout over the frozen L31 cyclic chromatic field."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Sequence

import torch
from torch import Tensor

from cassi_cyclic_chromatic_field import (
    CYCLIC_CHROMATIC_CHANNEL_NAMES,
    CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID,
    CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID,
    CyclicChromaticFieldConfig,
    CyclicChromaticFieldController,
    PsychedelicProjection,
    WhiteChromaticHeartbeatReceipt,
    WhiteChromaticReadout,
    WhiteChromaticTick,
)
from cassi_qi_field import QiFieldState

QUADRATURE_CHROMATIC_LAYOUT_PROFILE_ID = CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID
QUADRATURE_CHROMATIC_OPERATOR_PROFILE_ID = "cassi.qi-quadrature-chromatic-recall.v1"
QUADRATURE_CHROMATIC_PROJECTION_PROFILE_ID = CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID
QUADRATURE_CHROMATIC_CHANNEL_NAMES = CYCLIC_CHROMATIC_CHANNEL_NAMES
_CHANNEL_COUNT = len(QUADRATURE_CHROMATIC_CHANNEL_NAMES)


@dataclass(frozen=True)
class QuadratureChromaticFieldConfig(CyclicChromaticFieldConfig):
    """Frozen L32 constants with a distinct readout fingerprint."""

    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        encoded = json.dumps(
            {
                "layout_profile_id": QUADRATURE_CHROMATIC_LAYOUT_PROFILE_ID,
                "operator_profile_id": QUADRATURE_CHROMATIC_OPERATOR_PROFILE_ID,
                "projection_profile_id": QUADRATURE_CHROMATIC_PROJECTION_PROFILE_ID,
                "shared_codebook_fingerprint": codebook_fingerprint,
                "config": self.to_dict(),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class QuadratureChromaticReadout(WhiteChromaticReadout):
    normalized_differential_velocity: Tensor


class QuadratureChromaticFieldController(CyclicChromaticFieldController):
    """L31 dynamics read from both differential phase-space quadratures."""

    def _normalized_differential_velocity_unchecked(
        self, state: QiFieldState, differential_velocity: Tensor | None = None
    ) -> Tensor:
        if differential_velocity is None:
            _, _, _, differential_velocity = self._active_coordinates(state)
        constants = self._constants(state)
        omega = torch.sqrt(
            constants["omega2"]
            + 4.0
            * constants["edge_weight"][0:1]
            * math.sin(math.pi / _CHANNEL_COUNT) ** 2
        )
        return differential_velocity / omega

    def normalized_differential_velocity(self, state: QiFieldState) -> Tensor:
        self._validate_state(state)
        return self._normalized_differential_velocity_unchecked(state)

    def _white_readout_unchecked(
        self,
        state: QiFieldState,
        allowed_symbols: Sequence[int] | None,
    ) -> QuadratureChromaticReadout:
        _, differential, _, differential_velocity = self._active_coordinates(state)
        normalized_velocity = self._normalized_differential_velocity_unchecked(
            state, differential_velocity
        )
        phase_parts = self._codebook_source.codebook(
            0, device=state.field.device, dtype=state.field.dtype
        )
        codebook = torch.complex(phase_parts[..., 0], phase_parts[..., 1])
        coefficients_d = torch.einsum(
            "aw,swb->sab", codebook.conj(), differential
        ) / float(self.config.wave_mode_count)
        coefficients_v = torch.einsum(
            "aw,swb->sab", codebook.conj(), normalized_velocity
        ) / float(self.config.wave_mode_count)
        compensation = self._constants(state)["channel_phase"].conj()[:, None, None]
        aligned_d = compensation * coefficients_d
        aligned_v = compensation * coefficients_v
        global_d = aligned_d.sum(dim=0) / math.sqrt(_CHANNEL_COUNT)
        global_v = aligned_v.sum(dim=0) / math.sqrt(_CHANNEL_COUNT)
        scores = (
            global_d.abs().square() + global_v.abs().square()
        ).transpose(0, 1)
        bank_scores = (
            coefficients_d.abs().square() + coefficients_v.abs().square()
        ).permute(0, 2, 1)
        phase_energy = differential.abs().square() + normalized_velocity.abs().square()
        differential_rms = torch.sqrt(phase_energy.mean(dim=1))
        bank_energy = differential_rms.square()
        active = differential_rms >= self.config.readout_energy_floor
        active_bank_count = active.sum(dim=0)
        available = (
            (phase_energy.mean(dim=(0, 1)) >= self.config.readout_energy_floor)
            & (active_bank_count >= 2)
        )
        allowed = self._allowed_symbols(allowed_symbols)
        if allowed is None:
            symbols = torch.argmax(scores, dim=1)
        else:
            allowed = allowed.to(device=state.field.device)
            local = torch.argmax(scores.index_select(1, allowed), dim=1)
            symbols = allowed.index_select(0, local)
        gather = symbols[:, None, None].expand(state.batch_size, _CHANNEL_COUNT, 1)
        winning_d = aligned_d.permute(2, 0, 1).gather(2, gather)[:, :, 0]
        winning_v = aligned_v.permute(2, 0, 1).gather(2, gather)[:, :, 0]
        coherence = (
            winning_d.sum(dim=1).abs().square()
            + winning_v.sum(dim=1).abs().square()
        ) / (
            active_bank_count.to(dtype=state.field.dtype)
            * (
                winning_d.abs().square().sum(dim=1)
                + winning_v.abs().square().sum(dim=1)
            )
            + 1.0e-12
        )
        coherence = torch.where(available, coherence, torch.zeros_like(coherence))
        return QuadratureChromaticReadout(
            bank_scores=bank_scores,
            scores=scores,
            symbols=symbols,
            available=available,
            contributions=(aligned_d + 1j * aligned_v).permute(0, 2, 1),
            differential_rms=differential_rms,
            bank_energy=bank_energy,
            active_bank_count=active_bank_count,
            white_coherence=coherence,
            normalized_differential_velocity=normalized_velocity,
        )

    def white_readout(
        self,
        state: QiFieldState,
        *,
        allowed_symbols: Sequence[int] | None = None,
    ) -> QuadratureChromaticReadout:
        self._validate_state(state)
        return self._white_readout_unchecked(state, allowed_symbols)


__all__ = [
    "PsychedelicProjection",
    "QUADRATURE_CHROMATIC_CHANNEL_NAMES",
    "QUADRATURE_CHROMATIC_LAYOUT_PROFILE_ID",
    "QUADRATURE_CHROMATIC_OPERATOR_PROFILE_ID",
    "QUADRATURE_CHROMATIC_PROJECTION_PROFILE_ID",
    "QuadratureChromaticFieldConfig",
    "QuadratureChromaticFieldController",
    "QuadratureChromaticReadout",
    "WhiteChromaticHeartbeatReceipt",
    "WhiteChromaticTick",
]
