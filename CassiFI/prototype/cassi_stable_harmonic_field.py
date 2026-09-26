"""Precision-stable availability masking for the frozen L42 age ladder."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Sequence

import torch
from torch import Tensor

from cassi_harmonic_age_field import (
    HARMONIC_AGE_CHANNEL_NAMES,
    HARMONIC_AGE_INDICES,
    HARMONIC_AGE_LAYOUT_PROFILE_ID,
    HARMONIC_AGE_PROJECTION_PROFILE_ID,
    HarmonicAgeFieldConfig,
    HarmonicAgeFieldController,
    HarmonicAgeReadout,
    PsychedelicProjection,
    WhiteChromaticHeartbeatReceipt,
    WhiteChromaticTick,
)
from cassi_qi_field import QiFieldState

STABLE_HARMONIC_LAYOUT_PROFILE_ID = HARMONIC_AGE_LAYOUT_PROFILE_ID
STABLE_HARMONIC_OPERATOR_PROFILE_ID = "cassi.qi-stable-harmonic-age-ladder.v1"
STABLE_HARMONIC_PROJECTION_PROFILE_ID = HARMONIC_AGE_PROJECTION_PROFILE_ID
STABLE_HARMONIC_CHANNEL_NAMES = HARMONIC_AGE_CHANNEL_NAMES
ROUND_OFF_MULTIPLIER = 128.0
_CHANNEL_COUNT = len(STABLE_HARMONIC_CHANNEL_NAMES)


@dataclass(frozen=True)
class StableHarmonicFieldConfig(HarmonicAgeFieldConfig):
    """Frozen L43 constants with a distinct readout fingerprint."""

    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        encoded = json.dumps(
            {
                "layout_profile_id": STABLE_HARMONIC_LAYOUT_PROFILE_ID,
                "operator_profile_id": STABLE_HARMONIC_OPERATOR_PROFILE_ID,
                "projection_profile_id": STABLE_HARMONIC_PROJECTION_PROFILE_ID,
                "shared_codebook_fingerprint": codebook_fingerprint,
                "config": self.to_dict(),
                "round_off_multiplier": ROUND_OFF_MULTIPLIER,
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class StableHarmonicReadout(HarmonicAgeReadout):
    age_numerical_floor: Tensor


class StableHarmonicFieldController(HarmonicAgeFieldController):
    """L42 dynamics with dtype-grounded age availability and aggregation."""

    def _white_readout_unchecked(
        self,
        state: QiFieldState,
        allowed_symbols: Sequence[int] | None,
    ) -> StableHarmonicReadout:
        current = super()._white_readout_unchecked(state, allowed_symbols)
        age_scores = current.age_scores
        age_max = age_scores.amax(dim=2)
        row_peak = age_max.amax(dim=1)
        epsilon = torch.finfo(state.field.real.dtype).eps
        numerical_floor = torch.maximum(
            torch.full_like(row_peak, self.config.readout_energy_floor),
            row_peak * (ROUND_OFF_MULTIPLIER * epsilon),
        )
        age_available = current.available[:, None] & (
            age_max >= numerical_floor[:, None]
        )
        normalized = torch.where(
            age_available[:, :, None],
            age_scores / age_max.clamp_min(numerical_floor[:, None])[:, :, None],
            torch.zeros_like(age_scores),
        )
        scores = normalized.amax(dim=1)
        candidates = torch.arange(
            self.config.alphabet_size, device=state.field.device
        )[None, :]
        for age in range(_CHANNEL_COUNT - 1, -1, -1):
            slot = age_available[:, age, None] & (
                candidates == current.age_symbols[:, age, None]
            )
            scores = torch.where(slot, torch.full_like(scores, 8.0 - age), scores)
        scores = torch.where(current.available[:, None], scores, current.scores)

        return StableHarmonicReadout(
            bank_scores=current.bank_scores,
            scores=scores,
            symbols=current.age_symbols[:, 0],
            available=current.available,
            contributions=current.contributions,
            differential_rms=current.differential_rms,
            bank_energy=current.bank_energy,
            active_bank_count=current.active_bank_count,
            white_coherence=current.white_coherence,
            age_scores=age_scores,
            age_symbols=current.age_symbols,
            age_available=age_available,
            age_harmonics=HARMONIC_AGE_INDICES,
            age_numerical_floor=numerical_floor,
        )

    def white_readout(
        self,
        state: QiFieldState,
        *,
        allowed_symbols: Sequence[int] | None = None,
    ) -> StableHarmonicReadout:
        self._validate_state(state)
        return self._white_readout_unchecked(state, allowed_symbols)


__all__ = [
    "ROUND_OFF_MULTIPLIER",
    "STABLE_HARMONIC_CHANNEL_NAMES",
    "STABLE_HARMONIC_LAYOUT_PROFILE_ID",
    "STABLE_HARMONIC_OPERATOR_PROFILE_ID",
    "STABLE_HARMONIC_PROJECTION_PROFILE_ID",
    "StableHarmonicFieldConfig",
    "StableHarmonicFieldController",
    "StableHarmonicReadout",
    "PsychedelicProjection",
    "WhiteChromaticHeartbeatReceipt",
    "WhiteChromaticTick",
]
