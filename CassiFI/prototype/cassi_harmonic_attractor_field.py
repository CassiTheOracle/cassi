"""Field-local phase locking for harmonic working memory."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

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
)
from cassi_qi_field import QiFieldState

HARMONIC_ATTRACTOR_LAYOUT_PROFILE_ID = HARMONIC_AGE_LAYOUT_PROFILE_ID
HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID = "cassi.qi-harmonic-attractor.v1"
HARMONIC_ATTRACTOR_PROJECTION_PROFILE_ID = HARMONIC_AGE_PROJECTION_PROFILE_ID
HARMONIC_ATTRACTOR_CHANNEL_NAMES = HARMONIC_AGE_CHANNEL_NAMES
_CHANNEL_COUNT = len(HARMONIC_ATTRACTOR_CHANNEL_NAMES)


@dataclass(frozen=True)
class HarmonicAttractorFieldConfig(HarmonicAgeFieldConfig):
    """Harmonic geometry with an energy-preserving codebook attractor."""

    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        encoded = json.dumps(
            {
                "layout_profile_id": HARMONIC_ATTRACTOR_LAYOUT_PROFILE_ID,
                "operator_profile_id": HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID,
                "projection_profile_id": HARMONIC_ATTRACTOR_PROJECTION_PROFILE_ID,
                "shared_codebook_fingerprint": codebook_fingerprint,
                "config": self.to_dict(),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class HarmonicAttractorFieldController(HarmonicAgeFieldController):
    """Rephase the write carrier and available harmonic codebook orbits."""

    def _constants(self, state: QiFieldState) -> dict[str, Tensor]:
        constants = super()._constants(state)
        if "harmonic_forward" not in constants:
            phase = constants["channel_phase"]
            harmonics = torch.arange(
                _CHANNEL_COUNT, device=state.field.device, dtype=torch.int64
            )
            constants["harmonic_forward"] = (
                phase.conj()[None, :].pow(harmonics[:, None])
                / math.sqrt(_CHANNEL_COUNT)
            )
            constants["harmonic_inverse"] = (
                phase[:, None].pow(harmonics[None, :])
                / math.sqrt(_CHANNEL_COUNT)
            )
            parts = self.codebook(
                0, device=state.field.device, dtype=state.field.dtype
            )
            constants["complex_codebook"] = torch.complex(
                parts[..., 0], parts[..., 1]
            )
        return constants

    def _lock_field_unchecked(self, state: QiFieldState) -> QiFieldState:
        common, differential, common_velocity, differential_velocity = (
            self._active_coordinates(state)
        )
        constants = self._constants(state)
        epsilon = torch.finfo(state.field.dtype).eps
        white = constants["white"]

        carrier = (white[:, None, None] * common).sum(dim=0)
        carrier_velocity = (white[:, None, None] * common_velocity).sum(dim=0)

        def flat_orbit(
            value: Tensor, fallback: Tensor
        ) -> tuple[Tensor, Tensor]:
            coefficient = value.mean(dim=0)
            coefficient_abs = coefficient.abs()
            phase = torch.where(
                coefficient_abs > epsilon,
                coefficient / coefficient_abs.clamp_min(epsilon),
                fallback,
            )
            amplitude = value.abs().square().mean(dim=0).sqrt()
            return amplitude[None, :] * phase[None, :], phase

        locked_carrier, carrier_phase = flat_orbit(
            carrier, torch.ones_like(carrier[0])
        )
        locked_carrier_velocity, _ = flat_orbit(
            carrier_velocity, carrier_phase
        )
        common = common + white[:, None, None] * (
            locked_carrier - carrier
        )[None]
        common_velocity = common_velocity + white[:, None, None] * (
            locked_carrier_velocity - carrier_velocity
        )[None]

        forward = constants["harmonic_forward"]
        inverse = constants["harmonic_inverse"]
        codebook = constants["complex_codebook"]
        harmonic = torch.einsum("kc,cwb->kwb", forward, differential)
        harmonic_velocity = torch.einsum(
            "kc,cwb->kwb", forward, differential_velocity
        )
        coefficients = torch.einsum(
            "sw,kwb->kbs", codebook.conj(), harmonic
        ) / float(self.config.wave_mode_count)
        scores = coefficients.abs().square()
        winners = scores.argmax(dim=2)
        winner_codes = codebook[winners].permute(0, 2, 1)
        winner_coefficients = coefficients.gather(
            2, winners[:, :, None]
        ).squeeze(2)
        coefficient_abs = winner_coefficients.abs()
        phase = torch.where(
            coefficient_abs > epsilon,
            winner_coefficients / coefficient_abs.clamp_min(epsilon),
            torch.ones_like(winner_coefficients),
        )

        velocity_coefficients = torch.einsum(
            "sw,kwb->kbs", codebook.conj(), harmonic_velocity
        ) / float(self.config.wave_mode_count)
        winner_velocity = velocity_coefficients.gather(
            2, winners[:, :, None]
        ).squeeze(2)
        velocity_abs = winner_velocity.abs()
        velocity_phase = torch.where(
            velocity_abs > epsilon,
            winner_velocity / velocity_abs.clamp_min(epsilon),
            phase,
        )

        locked = winner_codes * (
            harmonic.abs().square().mean(dim=1).sqrt() * phase
        )[:, None, :]
        locked_velocity = winner_codes * (
            harmonic_velocity.abs().square().mean(dim=1).sqrt()
            * velocity_phase
        )[:, None, :]

        differential_rms = differential.abs().square().mean(dim=1).sqrt()
        ordinary_available = (
            differential.abs().square().mean(dim=(0, 1))
            >= self.config.readout_energy_floor
        ) & (
            (differential_rms >= self.config.readout_energy_floor).sum(dim=0)
            >= 2
        )
        available = ordinary_available[None, :] & (
            scores.amax(dim=2) >= self.config.readout_energy_floor
        )
        harmonic = torch.where(available[:, None, :], locked, harmonic)
        harmonic_velocity = torch.where(
            available[:, None, :], locked_velocity, harmonic_velocity
        )
        return self._replace_coordinates(
            state,
            common,
            torch.einsum("ck,kwb->cwb", inverse, harmonic),
            common_velocity,
            torch.einsum("ck,kwb->cwb", inverse, harmonic_velocity),
        )

    def lock_field(self, state: QiFieldState) -> QiFieldState:
        self._validate_state(state)
        result = self._lock_field_unchecked(state)
        return self._bound(result)[0]

    def _evolve_unchecked(
        self, state: QiFieldState, steps: int
    ) -> tuple[QiFieldState, int]:
        evolved, clamp_count = super()._evolve_unchecked(state, steps)
        locked, lock_clamps = self._bound(self._lock_field_unchecked(evolved))
        return locked, clamp_count + lock_clamps


__all__ = [
    "HARMONIC_ATTRACTOR_CHANNEL_NAMES",
    "HARMONIC_ATTRACTOR_LAYOUT_PROFILE_ID",
    "HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID",
    "HARMONIC_ATTRACTOR_PROJECTION_PROFILE_ID",
    "HarmonicAttractorFieldConfig",
    "HarmonicAttractorFieldController",
    "HARMONIC_AGE_INDICES",
    "HarmonicAgeReadout",
]
