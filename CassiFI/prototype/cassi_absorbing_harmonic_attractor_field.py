"""Absorbing harmonic writes with field-local attractor evolution."""

from __future__ import annotations

import hashlib
import json

from cassi_absorbing_harmonic_age_field import (
    ABSORBING_HARMONIC_AGE_LAYOUT_PROFILE_ID,
    ABSORBING_HARMONIC_AGE_PROJECTION_PROFILE_ID,
    AbsorbingHarmonicAgeFieldConfig,
    AbsorbingHarmonicAgeFieldController,
)
from cassi_harmonic_attractor_field import HarmonicAttractorFieldController

ABSORBING_HARMONIC_ATTRACTOR_LAYOUT_PROFILE_ID = (
    ABSORBING_HARMONIC_AGE_LAYOUT_PROFILE_ID
)
ABSORBING_HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID = (
    "cassi.qi-absorbing-harmonic-attractor.v1"
)
ABSORBING_HARMONIC_ATTRACTOR_PROJECTION_PROFILE_ID = (
    ABSORBING_HARMONIC_AGE_PROJECTION_PROFILE_ID
)


class AbsorbingHarmonicAttractorFieldConfig(AbsorbingHarmonicAgeFieldConfig):
    """Absorbing writes with field-local harmonic locking after evolution."""

    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        encoded = json.dumps(
            {
                "layout_profile_id": ABSORBING_HARMONIC_ATTRACTOR_LAYOUT_PROFILE_ID,
                "operator_profile_id": ABSORBING_HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID,
                "projection_profile_id": ABSORBING_HARMONIC_ATTRACTOR_PROJECTION_PROFILE_ID,
                "shared_codebook_fingerprint": codebook_fingerprint,
                "config": self.to_dict(),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class AbsorbingHarmonicAttractorFieldController(
    AbsorbingHarmonicAgeFieldController,
    HarmonicAttractorFieldController,
):
    """Retire the oldest write and lock retained harmonics after evolution."""


__all__ = [
    "ABSORBING_HARMONIC_ATTRACTOR_LAYOUT_PROFILE_ID",
    "ABSORBING_HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID",
    "ABSORBING_HARMONIC_ATTRACTOR_PROJECTION_PROFILE_ID",
    "AbsorbingHarmonicAttractorFieldConfig",
    "AbsorbingHarmonicAttractorFieldController",
]
