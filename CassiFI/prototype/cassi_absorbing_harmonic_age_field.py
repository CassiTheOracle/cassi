"""Absorbing harmonic age writes over the frozen L42 field."""

from __future__ import annotations

import hashlib
import json
from typing import Sequence

from torch import Tensor

from cassi_harmonic_age_field import (
    HARMONIC_AGE_LAYOUT_PROFILE_ID,
    HARMONIC_AGE_PROJECTION_PROFILE_ID,
    HarmonicAgeFieldConfig,
    HarmonicAgeFieldController,
)
from cassi_qi_field import QiFieldState
from cassi_white_chromatic_field import WhiteChromaticFieldController


ABSORBING_HARMONIC_AGE_LAYOUT_PROFILE_ID = HARMONIC_AGE_LAYOUT_PROFILE_ID
ABSORBING_HARMONIC_AGE_OPERATOR_PROFILE_ID = "cassi.qi-absorbing-harmonic-age-write.v2"
ABSORBING_HARMONIC_AGE_PROJECTION_PROFILE_ID = HARMONIC_AGE_PROJECTION_PROFILE_ID


class AbsorbingHarmonicAgeFieldConfig(HarmonicAgeFieldConfig):
    """L47 constants with an absorbing-write operator fingerprint."""

    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        encoded = json.dumps(
            {
                "layout_profile_id": ABSORBING_HARMONIC_AGE_LAYOUT_PROFILE_ID,
                "operator_profile_id": ABSORBING_HARMONIC_AGE_OPERATOR_PROFILE_ID,
                "projection_profile_id": ABSORBING_HARMONIC_AGE_PROJECTION_PROFILE_ID,
                "shared_codebook_fingerprint": codebook_fingerprint,
                "config": self.to_dict(),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class AbsorbingHarmonicAgeFieldController(HarmonicAgeFieldController):
    """L42 harmonic age field whose symbol writes retire the oldest slot."""

    def _absorb_harmonics_unchecked(self, state: QiFieldState) -> QiFieldState:
        _, differential, _, differential_velocity = self._active_coordinates(state)
        phase = self._constants(state)["channel_phase"][:, None, None]
        projected_differential = phase * (
            differential - differential.mean(dim=0, keepdim=True)
        )
        projected_differential_velocity = phase * (
            differential_velocity - differential_velocity.mean(dim=0, keepdim=True)
        )

        width = self.config.wave_mode_count
        parts = [component.clone() for component in self._parts(state)]
        replacements = (
            projected_differential.real,
            projected_differential.imag,
            projected_differential_velocity.real,
            projected_differential_velocity.imag,
        )
        for index, value in zip((2, 3, 6, 7), replacements):
            parts[index][:, :width] = value
        return self._pack(parts)

    def absorb_harmonics(self, state: QiFieldState) -> QiFieldState:
        self._validate_state(state)
        return self._absorb_harmonics_unchecked(state)

    def _modulate_unchecked(
        self,
        state: QiFieldState,
        symbols: Tensor | Sequence[int],
        source_trust: float | Tensor,
    ) -> tuple[QiFieldState, Tensor, int]:
        shifted = self._absorb_harmonics_unchecked(state)
        return WhiteChromaticFieldController._modulate_unchecked(
            self, shifted, symbols, source_trust
        )


__all__ = [
    "ABSORBING_HARMONIC_AGE_LAYOUT_PROFILE_ID",
    "ABSORBING_HARMONIC_AGE_OPERATOR_PROFILE_ID",
    "ABSORBING_HARMONIC_AGE_PROJECTION_PROFILE_ID",
    "AbsorbingHarmonicAgeFieldConfig",
    "AbsorbingHarmonicAgeFieldController",
]
