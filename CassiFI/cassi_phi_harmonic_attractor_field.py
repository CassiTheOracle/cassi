"""Seven-pool harmonic attractor with phi-spaced time multipliers."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import cast

import torch
from torch import Tensor

from cassi_absorbing_harmonic_attractor_field import (
    ABSORBING_HARMONIC_ATTRACTOR_LAYOUT_PROFILE_ID,
    ABSORBING_HARMONIC_ATTRACTOR_PROJECTION_PROFILE_ID,
    AbsorbingHarmonicAttractorFieldConfig,
    AbsorbingHarmonicAttractorFieldController,
)
from cassi_prismatic_field import PHI
from cassi_qi_field import QiFieldError, QiFieldState

PHI_HARMONIC_ATTRACTOR_LAYOUT_PROFILE_ID = (
    ABSORBING_HARMONIC_ATTRACTOR_LAYOUT_PROFILE_ID
)
PHI_HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID = (
    "cassi.qi-phi-harmonic-attractor.v1"
)
PHI_HARMONIC_ATTRACTOR_PROJECTION_PROFILE_ID = (
    ABSORBING_HARMONIC_ATTRACTOR_PROJECTION_PROFILE_ID
)


@dataclass(frozen=True)
class PhiHarmonicAttractorFieldConfig(AbsorbingHarmonicAttractorFieldConfig):
    """Seven fixed pools with root-to-crown dimensionless time multipliers."""

    root_timescale: float = 1.0

    def __post_init__(self) -> None:
        super().__post_init__()
        if (
            isinstance(self.root_timescale, bool)
            or not isinstance(self.root_timescale, (int, float))
            or not math.isfinite(float(self.root_timescale))
            or float(self.root_timescale) <= 0.0
        ):
            raise QiFieldError("root_timescale must be a finite positive real number")
        object.__setattr__(self, "root_timescale", float(self.root_timescale))

    @property
    def bank_timescales(self) -> tuple[float, ...]:
        return tuple(self.root_timescale * PHI**index for index in range(7))

    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        encoded = json.dumps(
            {
                "bank_timescales": self.bank_timescales,
                "config": self.to_dict(),
                "layout_profile_id": PHI_HARMONIC_ATTRACTOR_LAYOUT_PROFILE_ID,
                "operator_profile_id": PHI_HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID,
                "projection_profile_id": PHI_HARMONIC_ATTRACTOR_PROJECTION_PROFILE_ID,
                "shared_codebook_fingerprint": codebook_fingerprint,
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class PhiHarmonicAttractorFieldController(
    AbsorbingHarmonicAttractorFieldController
):
    """Apply phi-spaced pool dynamics to the absorbing harmonic field."""

    def __init__(self, config: PhiHarmonicAttractorFieldConfig) -> None:
        if not isinstance(config, PhiHarmonicAttractorFieldConfig):
            raise QiFieldError("config must be a PhiHarmonicAttractorFieldConfig")
        self._phi_constant_cache: dict[
            tuple[torch.device, torch.dtype], dict[str, Tensor]
        ] = {}
        super().__init__(config)

    def _constants(self, state: QiFieldState) -> dict[str, Tensor]:
        key = (state.field.device, state.field.dtype)
        cached = self._phi_constant_cache.get(key)
        if cached is not None:
            return cached

        constants = dict(super()._constants(state))
        config = cast(PhiHarmonicAttractorFieldConfig, self.config)
        bank_timescale = torch.tensor(
            config.bank_timescales,
            device=state.field.device,
            dtype=state.field.dtype,
        ).reshape(7, 1, 1)
        timescale = bank_timescale * constants["timescale"]
        inverse_tau2 = timescale.square().reciprocal()
        constants.update(
            timescale=timescale,
            omega2=config.base_omega2 * inverse_tau2,
            damping_decay=torch.exp(
                -config.base_damping * config.dt / timescale
            ),
            nonlinear=config.nonlinear_gain * inverse_tau2,
            epsilon_alpha=1.0
            - torch.pow(
                torch.full_like(timescale, 1.0 - config.epsilon_tau),
                timescale.reciprocal(),
            ),
            edge_weight=config.coupling_omega2
            / (timescale[:-1] * timescale[1:]),
        )
        self._phi_constant_cache[key] = constants
        return constants


__all__ = [
    "PHI_HARMONIC_ATTRACTOR_LAYOUT_PROFILE_ID",
    "PHI_HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID",
    "PHI_HARMONIC_ATTRACTOR_PROJECTION_PROFILE_ID",
    "PhiHarmonicAttractorFieldConfig",
    "PhiHarmonicAttractorFieldController",
]
