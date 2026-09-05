"""Protected two-lane chromatic memory over the frozen L31 field."""

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

PROTECTED_CHROMATIC_LAYOUT_PROFILE_ID = "cassi.qi-protected-chromatic-memory-lane.v1"
PROTECTED_CHROMATIC_OPERATOR_PROFILE_ID = "cassi.qi-protected-chromatic-heartbeat.v1"
PROTECTED_CHROMATIC_PROJECTION_PROFILE_ID = CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID
PROTECTED_CHROMATIC_CHANNEL_NAMES = CYCLIC_CHROMATIC_CHANNEL_NAMES
_MEMORY_GAIN = 0.5


@dataclass(frozen=True)
class ProtectedChromaticFieldConfig(CyclicChromaticFieldConfig):
    """Frozen L33 constants with protected-lane checkpoint identity."""

    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        encoded = json.dumps(
            {
                "layout_profile_id": PROTECTED_CHROMATIC_LAYOUT_PROFILE_ID,
                "operator_profile_id": PROTECTED_CHROMATIC_OPERATOR_PROFILE_ID,
                "projection_profile_id": PROTECTED_CHROMATIC_PROJECTION_PROFILE_ID,
                "shared_codebook_fingerprint": codebook_fingerprint,
                "config": self.to_dict(),
                "memory_gain": _MEMORY_GAIN,
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ProtectedChromaticReadout(WhiteChromaticReadout):
    effective_differential: Tensor


class ProtectedChromaticFieldController(CyclicChromaticFieldController):
    """Current/retained chromatic lanes inside the existing field tensor."""

    def _modulate_unchecked(
        self,
        state: QiFieldState,
        symbols: Tensor | Sequence[int],
        source_trust: float | Tensor,
    ) -> tuple[QiFieldState, Tensor, int]:
        trust = self._trust_tensor(source_trust, state)
        before = self._total_energy_unchecked(state)
        common, current_lane, common_velocity, memory_lane = (
            self._active_coordinates(state)
        )
        angle = (0.5 * math.pi * trust).reshape(1, 1, -1)
        cosine, sine = torch.cos(angle), torch.sin(angle)
        rotated_current = cosine * current_lane + sine * memory_lane
        rotated_memory = cosine * memory_lane - sine * current_lane
        rotated = self._replace_coordinates(
            state,
            common,
            rotated_current,
            common_velocity,
            rotated_memory,
        )
        result, _, clamp_count = super()._modulate_unchecked(
            rotated, symbols, source_trust
        )
        after = self._total_energy_unchecked(result)
        denominator = torch.clamp_min(before.abs(), torch.finfo(before.dtype).eps)
        drift = torch.where(
            (before == 0.0) & (after == 0.0),
            torch.zeros_like(before),
            (after - before) / denominator,
        )
        return result, drift, clamp_count

    def _evolve_unchecked(
        self, state: QiFieldState, steps: int
    ) -> tuple[QiFieldState, int]:
        constants = self._constants(state)
        current = state
        clamp_count = 0
        for _ in range(steps):
            common, current_lane, common_velocity, memory_lane = (
                self._active_coordinates(current)
            )
            radius2 = common.abs().square() + current_lane.abs().square()
            common_force = self._coupling_force(
                common, constants["edge_weight"]
            )
            common_velocity = (
                constants["damping_decay"] * common_velocity
                + self.config.dt
                * (
                    -constants["omega2"] * common
                    - constants["nonlinear"] * radius2 * common
                    + common_force
                )
            )
            common = common + self.config.dt * common_velocity
            denominator = 1.0 + PHI * PHI
            yang = (current_lane + PHI * common) / denominator
            yin = (common - PHI * current_lane) / denominator
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
                current_lane,
                common_velocity,
                memory_lane,
                epsilon=epsilon,
            )
            current, step_clamps = self._bound(current)
            clamp_count += step_clamps
        return current, clamp_count

    def _effective_differential_unchecked(self, state: QiFieldState) -> Tensor:
        _, current_lane, _, memory_lane = self._active_coordinates(state)
        return current_lane - _MEMORY_GAIN * memory_lane

    def effective_differential(self, state: QiFieldState) -> Tensor:
        self._validate_state(state)
        return self._effective_differential_unchecked(state)

    def _white_readout_unchecked(
        self,
        state: QiFieldState,
        allowed_symbols: Sequence[int] | None,
    ) -> ProtectedChromaticReadout:
        common, _, common_velocity, memory_lane = self._active_coordinates(state)
        effective = self._effective_differential_unchecked(state)
        readout_state = self._replace_coordinates(
            state,
            common,
            effective,
            common_velocity,
            memory_lane,
        )
        base = super()._white_readout_unchecked(readout_state, allowed_symbols)
        return ProtectedChromaticReadout(
            bank_scores=base.bank_scores,
            scores=base.scores,
            symbols=base.symbols,
            available=base.available,
            contributions=base.contributions,
            differential_rms=base.differential_rms,
            bank_energy=base.bank_energy,
            active_bank_count=base.active_bank_count,
            white_coherence=base.white_coherence,
            effective_differential=effective,
        )

    def white_readout(
        self,
        state: QiFieldState,
        *,
        allowed_symbols: Sequence[int] | None = None,
    ) -> ProtectedChromaticReadout:
        self._validate_state(state)
        return self._white_readout_unchecked(state, allowed_symbols)


__all__ = [
    "PROTECTED_CHROMATIC_CHANNEL_NAMES",
    "PROTECTED_CHROMATIC_LAYOUT_PROFILE_ID",
    "PROTECTED_CHROMATIC_OPERATOR_PROFILE_ID",
    "PROTECTED_CHROMATIC_PROJECTION_PROFILE_ID",
    "ProtectedChromaticFieldConfig",
    "ProtectedChromaticFieldController",
    "ProtectedChromaticReadout",
    "PsychedelicProjection",
    "WhiteChromaticHeartbeatReceipt",
    "WhiteChromaticTick",
]
