"""Exact linear cyclic dynamics with a frozen nonlinear Strang split."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

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
from cassi_prismatic_field import PHI
from cassi_qi_field import QiFieldState

EXACT_CYCLIC_LAYOUT_PROFILE_ID = CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID
EXACT_CYCLIC_OPERATOR_PROFILE_ID = "cassi.qi-exact-cyclic-strang.v1"
EXACT_CYCLIC_PROJECTION_PROFILE_ID = CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID
EXACT_CYCLIC_CHANNEL_NAMES = CYCLIC_CHROMATIC_CHANNEL_NAMES
_CHANNEL_COUNT = len(EXACT_CYCLIC_CHANNEL_NAMES)


@dataclass(frozen=True)
class ExactCyclicFieldConfig(CyclicChromaticFieldConfig):
    """Frozen L34 constants with exact-integrator identity."""

    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        encoded = json.dumps(
            {
                "layout_profile_id": EXACT_CYCLIC_LAYOUT_PROFILE_ID,
                "operator_profile_id": EXACT_CYCLIC_OPERATOR_PROFILE_ID,
                "projection_profile_id": EXACT_CYCLIC_PROJECTION_PROFILE_ID,
                "shared_codebook_fingerprint": codebook_fingerprint,
                "config": self.to_dict(),
                "integrator": "linear-exact-nonlinear-strang",
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class ExactCyclicFieldController(CyclicChromaticFieldController):
    """L31 field with exact damped cyclic linear substeps."""

    def __init__(self, config: ExactCyclicFieldConfig) -> None:
        super().__init__(config)
        self._exact_constant_cache: dict[
            tuple[torch.device, torch.dtype], tuple[Tensor, Tensor, Tensor, Tensor, Tensor]
        ] = {}

    def _exact_constants(
        self, state: QiFieldState
    ) -> tuple[Tensor, Tensor, Tensor, Tensor, Tensor]:
        key = (state.field.device, state.field.dtype)
        cached = self._exact_constant_cache.get(key)
        if cached is not None:
            return cached
        constants = self._constants(state)
        harmonic = torch.arange(
            _CHANNEL_COUNT, device=state.field.device, dtype=state.field.dtype
        ).reshape(_CHANNEL_COUNT, 1, 1)
        omega2 = constants["omega2"] + 4.0 * constants["edge_weight"][0:1] * (
            torch.sin(math.pi * harmonic / _CHANNEL_COUNT).square()
        )
        gamma = -torch.log(constants["damping_decay"]) / self.config.dt
        alpha = 0.5 * gamma
        nu = torch.sqrt(torch.clamp_min(omega2 - alpha.square(), 0.0))
        angle = nu * self.config.dt
        cosine = torch.cos(angle)
        sine_over_nu = self.config.dt * torch.sinc(angle / math.pi)
        decay = torch.exp(-alpha * self.config.dt)
        cached = omega2, alpha, cosine, sine_over_nu, decay
        self._exact_constant_cache[key] = cached
        return cached

    @staticmethod
    def _linear_exact_step(
        position: Tensor,
        velocity: Tensor,
        exact: tuple[Tensor, Tensor, Tensor, Tensor, Tensor],
    ) -> tuple[Tensor, Tensor]:
        omega2, alpha, cosine, sine_over_nu, decay = exact
        position_hat = torch.fft.fft(position, dim=0, norm="ortho")
        velocity_hat = torch.fft.fft(velocity, dim=0, norm="ortho")
        next_position_hat = decay * (
            (cosine + alpha * sine_over_nu) * position_hat
            + sine_over_nu * velocity_hat
        )
        next_velocity_hat = decay * (
            -omega2 * sine_over_nu * position_hat
            + (cosine - alpha * sine_over_nu) * velocity_hat
        )
        return (
            torch.fft.ifft(next_position_hat, dim=0, norm="ortho"),
            torch.fft.ifft(next_velocity_hat, dim=0, norm="ortho"),
        )

    def _evolve_unchecked(
        self, state: QiFieldState, steps: int
    ) -> tuple[QiFieldState, int]:
        constants = self._constants(state)
        exact = self._exact_constants(state)
        current = state
        clamp_count = 0
        half_dt = 0.5 * self.config.dt
        for _ in range(steps):
            common, differential, common_velocity, differential_velocity = (
                self._active_coordinates(current)
            )
            radius2 = common.abs().square() + differential.abs().square()
            common_velocity = (
                common_velocity
                - half_dt * constants["nonlinear"] * radius2 * common
            )
            differential_velocity = (
                differential_velocity
                - half_dt * constants["nonlinear"] * radius2 * differential
            )
            common, common_velocity = self._linear_exact_step(
                common, common_velocity, exact
            )
            differential, differential_velocity = self._linear_exact_step(
                differential, differential_velocity, exact
            )
            radius2 = common.abs().square() + differential.abs().square()
            common_velocity = (
                common_velocity
                - half_dt * constants["nonlinear"] * radius2 * common
            )
            differential_velocity = (
                differential_velocity
                - half_dt * constants["nonlinear"] * radius2 * differential
            )
            denominator = 1.0 + PHI * PHI
            yang = (differential + PHI * common) / denominator
            yin = (common - PHI * differential) / denominator
            epsilon_target = (
                yang.abs().square() - PHI * yin.abs().square()
            ).square()
            epsilon = self._parts(current)[8][:, : self.config.wave_mode_count]
            epsilon = epsilon + constants["epsilon_alpha"] * (
                epsilon_target - epsilon
            )
            current = self._replace_coordinates(
                current,
                common,
                differential,
                common_velocity,
                differential_velocity,
                epsilon=epsilon,
            )
            current, step_clamps = self._bound(current)
            clamp_count += step_clamps
        return current, clamp_count


__all__ = [
    "EXACT_CYCLIC_CHANNEL_NAMES",
    "EXACT_CYCLIC_LAYOUT_PROFILE_ID",
    "EXACT_CYCLIC_OPERATOR_PROFILE_ID",
    "EXACT_CYCLIC_PROJECTION_PROFILE_ID",
    "ExactCyclicFieldConfig",
    "ExactCyclicFieldController",
    "PsychedelicProjection",
    "WhiteChromaticHeartbeatReceipt",
    "WhiteChromaticReadout",
    "WhiteChromaticTick",
]
