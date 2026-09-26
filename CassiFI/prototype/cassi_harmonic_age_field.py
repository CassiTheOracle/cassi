"""Unitary harmonic age routing over the frozen L31 cyclic field."""

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

HARMONIC_AGE_LAYOUT_PROFILE_ID = CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID
HARMONIC_AGE_OPERATOR_PROFILE_ID = "cassi.qi-harmonic-age-ladder.v1"
HARMONIC_AGE_PROJECTION_PROFILE_ID = CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID
HARMONIC_AGE_CHANNEL_NAMES = CYCLIC_CHROMATIC_CHANNEL_NAMES
HARMONIC_AGE_INDICES = (1, 2, 3, 4, 5, 6, 0)
_CHANNEL_COUNT = len(HARMONIC_AGE_CHANNEL_NAMES)


@dataclass(frozen=True)
class HarmonicAgeFieldConfig(CyclicChromaticFieldConfig):
    """Frozen L42 constants with a distinct modulation/readout fingerprint."""

    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        encoded = json.dumps(
            {
                "layout_profile_id": HARMONIC_AGE_LAYOUT_PROFILE_ID,
                "operator_profile_id": HARMONIC_AGE_OPERATOR_PROFILE_ID,
                "projection_profile_id": HARMONIC_AGE_PROJECTION_PROFILE_ID,
                "shared_codebook_fingerprint": codebook_fingerprint,
                "config": self.to_dict(),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class HarmonicAgeReadout(WhiteChromaticReadout):
    age_scores: Tensor
    age_symbols: Tensor
    age_available: Tensor
    age_harmonics: tuple[int, ...]


class HarmonicAgeFieldController(CyclicChromaticFieldController):
    """L31 field whose channel harmonics encode symbol age."""

    def _lift_harmonics_unchecked(self, state: QiFieldState) -> QiFieldState:
        common, differential, common_velocity, differential_velocity = (
            self._active_coordinates(state)
        )
        phase = self._constants(state)["channel_phase"][:, None, None]
        return self._replace_coordinates(
            state,
            common,
            phase * differential,
            common_velocity,
            phase * differential_velocity,
        )

    def lift_harmonics(self, state: QiFieldState) -> QiFieldState:
        self._validate_state(state)
        return self._lift_harmonics_unchecked(state)

    def _modulate_unchecked(
        self,
        state: QiFieldState,
        symbols: Tensor | Sequence[int],
        source_trust: float | Tensor,
    ) -> tuple[QiFieldState, Tensor, int]:
        return super()._modulate_unchecked(
            self._lift_harmonics_unchecked(state), symbols, source_trust
        )

    def _white_readout_unchecked(
        self,
        state: QiFieldState,
        allowed_symbols: Sequence[int] | None,
    ) -> HarmonicAgeReadout:
        current = CyclicChromaticFieldController._white_readout_unchecked(
            self, state, allowed_symbols
        )
        _, differential, _, _ = self._active_coordinates(state)
        phase_parts = self._codebook_source.codebook(
            0, device=state.field.device, dtype=state.field.dtype
        )
        codebook = torch.complex(phase_parts[..., 0], phase_parts[..., 1])
        channel_phase = self._constants(state)["channel_phase"]
        harmonics = torch.tensor(
            HARMONIC_AGE_INDICES, device=state.field.device, dtype=torch.int64
        )
        basis = channel_phase.conj()[None, :].pow(harmonics[:, None]) / math.sqrt(
            _CHANNEL_COUNT
        )
        collapsed = torch.einsum("hc,cwb->hwb", basis, differential)
        coefficients = torch.einsum(
            "aw,hwb->hba", codebook.conj(), collapsed
        ) / float(self.config.wave_mode_count)
        age_scores = coefficients.abs().square().permute(1, 0, 2)

        allowed = self._allowed_symbols(allowed_symbols)
        if allowed is None:
            age_symbols = torch.argmax(age_scores, dim=2)
        else:
            allowed = allowed.to(device=state.field.device)
            local = torch.argmax(age_scores.index_select(2, allowed), dim=2)
            age_symbols = allowed.index_select(0, local.reshape(-1)).reshape_as(local)

        floor = self.config.readout_energy_floor
        age_max = age_scores.amax(dim=2)
        age_available = current.available[:, None] & (age_max >= floor)
        normalized = age_scores / age_max.clamp_min(floor)[:, :, None]
        scores = normalized.amax(dim=1)
        candidates = torch.arange(
            self.config.alphabet_size, device=state.field.device
        )[None, :]
        for age in range(_CHANNEL_COUNT - 1, -1, -1):
            slot = age_available[:, age, None] & (
                candidates == age_symbols[:, age, None]
            )
            scores = torch.where(slot, torch.full_like(scores, 8.0 - age), scores)
        scores = torch.where(current.available[:, None], scores, current.scores)

        return HarmonicAgeReadout(
            bank_scores=current.bank_scores,
            scores=scores,
            symbols=age_symbols[:, 0],
            available=current.available,
            contributions=current.contributions,
            differential_rms=current.differential_rms,
            bank_energy=current.bank_energy,
            active_bank_count=current.active_bank_count,
            white_coherence=current.white_coherence,
            age_scores=age_scores,
            age_symbols=age_symbols,
            age_available=age_available,
            age_harmonics=HARMONIC_AGE_INDICES,
        )

    def white_readout(
        self,
        state: QiFieldState,
        *,
        allowed_symbols: Sequence[int] | None = None,
    ) -> HarmonicAgeReadout:
        self._validate_state(state)
        return self._white_readout_unchecked(state, allowed_symbols)


__all__ = [
    "HARMONIC_AGE_CHANNEL_NAMES",
    "HARMONIC_AGE_INDICES",
    "HARMONIC_AGE_LAYOUT_PROFILE_ID",
    "HARMONIC_AGE_OPERATOR_PROFILE_ID",
    "HARMONIC_AGE_PROJECTION_PROFILE_ID",
    "HarmonicAgeFieldConfig",
    "HarmonicAgeFieldController",
    "HarmonicAgeReadout",
    "PsychedelicProjection",
    "WhiteChromaticHeartbeatReceipt",
    "WhiteChromaticTick",
]
