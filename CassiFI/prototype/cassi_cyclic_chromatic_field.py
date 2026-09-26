"""Native-coordinate cyclic refinement of the white-chromatic Qi field."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


import torch
from torch import Tensor

from cassi_prismatic_field import PHI
from cassi_qi_field import QiFieldState
from cassi_white_chromatic_field import (
    PsychedelicProjection,
    WHITE_CHROMATIC_CHANNEL_NAMES,
    WhiteChromaticFieldConfig,
    WhiteChromaticFieldController,
    WhiteChromaticHeartbeatReceipt,
    WhiteChromaticReadout,
    WhiteChromaticTick,
)

CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID = "cassi.qi-cyclic-chromatic-coordinate-native.v1"
CYCLIC_CHROMATIC_OPERATOR_PROFILE_ID = "cassi.qi-cyclic-chromatic-heartbeat.v1"
CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID = "cassi.qi-cyclic-chromatic-projection.v1"
CYCLIC_CHROMATIC_CHANNEL_NAMES = WHITE_CHROMATIC_CHANNEL_NAMES
_DENOMINATOR = 1.0 + PHI * PHI


@dataclass(frozen=True)
class CyclicChromaticFieldConfig(WhiteChromaticFieldConfig):
    """The frozen L31 constants with a distinct layout/operator fingerprint."""

    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        encoded = json.dumps(
            {
                "layout_profile_id": CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID,
                "operator_profile_id": CYCLIC_CHROMATIC_OPERATOR_PROFILE_ID,
                "projection_profile_id": CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID,
                "shared_codebook_fingerprint": codebook_fingerprint,
                "config": self.to_dict(),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class CyclicChromaticFieldController(WhiteChromaticFieldController):
    """Seven-color field with native C/D storage and periodic coupling."""


    def _active_coordinates(
        self, state: QiFieldState
    ) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        width = self.config.wave_mode_count
        c_re, c_im, d_re, d_im, vc_re, vc_im, vd_re, vd_im, _ = self._parts(
            state
        )
        return (
            torch.complex(c_re[:, :width], c_im[:, :width]),
            torch.complex(d_re[:, :width], d_im[:, :width]),
            torch.complex(vc_re[:, :width], vc_im[:, :width]),
            torch.complex(vd_re[:, :width], vd_im[:, :width]),
        )

    def _replace_coordinates(
        self,
        state: QiFieldState,
        common: Tensor,
        differential: Tensor,
        common_velocity: Tensor,
        differential_velocity: Tensor,
        *,
        epsilon: Tensor | None = None,
    ) -> QiFieldState:
        width = self.config.wave_mode_count
        parts = [component.clone() for component in self._parts(state)]
        replacements = (
            common.real,
            common.imag,
            differential.real,
            differential.imag,
            common_velocity.real,
            common_velocity.imag,
            differential_velocity.real,
            differential_velocity.imag,
        )
        for index, value in enumerate(replacements):
            parts[index][:, :width] = value
            parts[index][:, width:] = 0.0
        if epsilon is not None:
            parts[8][:, :width] = epsilon
        parts[8][:, width:] = 0.0
        return self._pack(parts)

    def _dynamic_energy_unchecked(self, state: QiFieldState) -> Tensor:
        width = self.config.wave_mode_count
        packed = state.field.reshape(
            self.config.bank_count, 9, self.config.mode_count, state.batch_size
        )
        return (
            packed[:, :8, :width].square().sum(dim=1).mean(dim=1)
            / _DENOMINATOR
        )

    def _bound(self, state: QiFieldState) -> tuple[QiFieldState, int]:
        packed = state.field.reshape(
            self.config.bank_count, 9, self.config.mode_count, state.batch_size
        ).clone()
        width = self.config.wave_mode_count
        active = packed[:, :8, :width]
        clamped = active.clamp(
            min=-self.config.max_mode_amplitude,
            max=self.config.max_mode_amplitude,
        )
        clamp_count = int(torch.count_nonzero(active != clamped).item())
        packed[:, :8, :width] = clamped
        energy = clamped.square().sum(dim=1).mean(dim=1) / _DENOMINATOR
        excessive = energy > self.config.max_mean_energy
        factor = torch.where(
            excessive,
            torch.sqrt(
                self.config.max_mean_energy / torch.clamp_min(energy, 1.0e-30)
            ),
            torch.ones_like(energy),
        )
        packed[:, :8, :width] *= factor[:, None, None, :]
        clamp_count += int(torch.count_nonzero(excessive).item())
        epsilon = packed[:, 8, :width]
        bounded_epsilon = epsilon.clamp(
            min=0.0, max=self.config.max_mode_amplitude**4
        )
        clamp_count += int(torch.count_nonzero(epsilon != bounded_epsilon).item())
        packed[:, 8, :width] = bounded_epsilon
        packed[:, :, width:] = 0.0
        return QiFieldState(
            packed.reshape(
                self.config.bank_count,
                9 * self.config.mode_count,
                state.batch_size,
            ).contiguous()
        ), clamp_count

    @staticmethod
    def _coupling_force(position: Tensor, edge_weight: Tensor) -> Tensor:
        weight = edge_weight[0]
        return weight * (
            torch.roll(position, shifts=1, dims=0)
            + torch.roll(position, shifts=-1, dims=0)
            - 2.0 * position
        )



    def _hamiltonian_unchecked(self, state: QiFieldState) -> Tensor:
        common, differential, _, _ = self._active_coordinates(state)
        closing_edge = (
            0.5
            * self._constants(state)["edge_weight"][0]
            * (
                (common[0] - common[-1]).abs().square()
                + (differential[0] - differential[-1]).abs().square()
            )
        ).mean(dim=0) / _DENOMINATOR
        return super()._hamiltonian_unchecked(state) + closing_edge


__all__ = [
    "CYCLIC_CHROMATIC_CHANNEL_NAMES",
    "CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID",
    "CYCLIC_CHROMATIC_OPERATOR_PROFILE_ID",
    "CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID",
    "CyclicChromaticFieldConfig",
    "CyclicChromaticFieldController",
    "PsychedelicProjection",
    "WhiteChromaticHeartbeatReceipt",
    "WhiteChromaticReadout",
    "WhiteChromaticTick",
]
