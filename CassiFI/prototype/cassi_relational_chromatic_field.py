"""Common–differential relational recall over the frozen L31 field."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
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

RELATIONAL_CHROMATIC_LAYOUT_PROFILE_ID = CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID
RELATIONAL_CHROMATIC_OPERATOR_PROFILE_ID = "cassi.qi-relational-chromatic-recall.v1"
RELATIONAL_CHROMATIC_PROJECTION_PROFILE_ID = CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID
RELATIONAL_CHROMATIC_CHANNEL_NAMES = CYCLIC_CHROMATIC_CHANNEL_NAMES
_CHANNEL_COUNT = len(RELATIONAL_CHROMATIC_CHANNEL_NAMES)


@dataclass(frozen=True)
class RelationalChromaticFieldConfig(CyclicChromaticFieldConfig):
    """Frozen L38 constants with a distinct readout fingerprint."""

    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        encoded = json.dumps(
            {
                "layout_profile_id": RELATIONAL_CHROMATIC_LAYOUT_PROFILE_ID,
                "operator_profile_id": RELATIONAL_CHROMATIC_OPERATOR_PROFILE_ID,
                "projection_profile_id": RELATIONAL_CHROMATIC_PROJECTION_PROFILE_ID,
                "shared_codebook_fingerprint": codebook_fingerprint,
                "config": self.to_dict(),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class RelationalChromaticFieldController(CyclicChromaticFieldController):
    """L31 dynamics read through current and relational codeword traces."""

    def _relational_trace_unchecked(self, state: QiFieldState) -> Tensor:
        common, differential, _, _ = self._active_coordinates(state)
        constants = self._constants(state)
        common_carrier = (
            constants["white"][:, None, None] * common
        ).sum(dim=0)
        differential_carrier = (
            constants["channel_phase"].conj()[:, None, None] * differential
        ).sum(dim=0) / math.sqrt(_CHANNEL_COUNT)
        return -common_carrier * differential_carrier

    def relational_trace(self, state: QiFieldState) -> Tensor:
        self._validate_state(state)
        return self._relational_trace_unchecked(state)

    def _white_readout_unchecked(
        self,
        state: QiFieldState,
        allowed_symbols: Sequence[int] | None,
    ) -> WhiteChromaticReadout:
        base = super()._white_readout_unchecked(state, allowed_symbols)
        phase_parts = self._codebook_source.codebook(
            0, device=state.field.device, dtype=state.field.dtype
        )
        codebook = torch.complex(phase_parts[..., 0], phase_parts[..., 1])
        relational_coefficients = torch.einsum(
            "aw,wb->ab",
            codebook.conj(),
            self._relational_trace_unchecked(state),
        ) / float(self.config.wave_mode_count)
        scores = base.scores + relational_coefficients.abs().square().transpose(0, 1)
        allowed = self._allowed_symbols(allowed_symbols)
        if allowed is None:
            symbols = torch.argmax(scores, dim=1)
        else:
            allowed = allowed.to(device=state.field.device)
            local = torch.argmax(scores.index_select(1, allowed), dim=1)
            symbols = allowed.index_select(0, local)
        winning = base.contributions.permute(1, 0, 2).gather(
            2,
            symbols[:, None, None].expand(state.batch_size, _CHANNEL_COUNT, 1),
        )[:, :, 0]
        coherence = winning.sum(dim=1).abs().square() / (
            base.active_bank_count.to(dtype=state.field.dtype)
            * winning.abs().square().sum(dim=1)
            + 1.0e-12
        )
        coherence = torch.where(
            base.available, coherence, torch.zeros_like(coherence)
        )
        return replace(
            base,
            scores=scores,
            symbols=symbols,
            white_coherence=coherence,
        )


__all__ = [
    "RELATIONAL_CHROMATIC_CHANNEL_NAMES",
    "RELATIONAL_CHROMATIC_LAYOUT_PROFILE_ID",
    "RELATIONAL_CHROMATIC_OPERATOR_PROFILE_ID",
    "RELATIONAL_CHROMATIC_PROJECTION_PROFILE_ID",
    "RelationalChromaticFieldConfig",
    "RelationalChromaticFieldController",
    "PsychedelicProjection",
    "WhiteChromaticHeartbeatReceipt",
    "WhiteChromaticReadout",
    "WhiteChromaticTick",
]
