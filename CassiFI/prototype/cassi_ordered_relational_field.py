"""Categorical current-then-predecessor recall over the frozen L31 field."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Sequence

import torch
from torch import Tensor

from cassi_cyclic_chromatic_field import (
    CYCLIC_CHROMATIC_CHANNEL_NAMES,
    CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID,
    CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID,
    CyclicChromaticFieldController,
    PsychedelicProjection,
    WhiteChromaticHeartbeatReceipt,
    WhiteChromaticReadout,
    WhiteChromaticTick,
)
from cassi_qi_field import QiFieldState
from cassi_relational_chromatic_field import (
    RelationalChromaticFieldConfig,
    RelationalChromaticFieldController,
)

ORDERED_RELATIONAL_LAYOUT_PROFILE_ID = CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID
ORDERED_RELATIONAL_OPERATOR_PROFILE_ID = (
    "cassi.qi-ordered-relational-chromatic-recall.v1"
)
ORDERED_RELATIONAL_PROJECTION_PROFILE_ID = CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID
ORDERED_RELATIONAL_CHANNEL_NAMES = CYCLIC_CHROMATIC_CHANNEL_NAMES


@dataclass(frozen=True)
class OrderedRelationalChromaticFieldConfig(RelationalChromaticFieldConfig):
    """Frozen L39 constants with a distinct readout fingerprint."""

    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        encoded = json.dumps(
            {
                "layout_profile_id": ORDERED_RELATIONAL_LAYOUT_PROFILE_ID,
                "operator_profile_id": ORDERED_RELATIONAL_OPERATOR_PROFILE_ID,
                "projection_profile_id": ORDERED_RELATIONAL_PROJECTION_PROFILE_ID,
                "shared_codebook_fingerprint": codebook_fingerprint,
                "config": self.to_dict(),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class OrderedRelationalChromaticReadout(WhiteChromaticReadout):
    current_scores: Tensor
    current_symbols: Tensor
    relational_scores: Tensor
    relational_symbols: Tensor
    relational_available: Tensor


class OrderedRelationalChromaticFieldController(RelationalChromaticFieldController):
    """L31 dynamics with categorical current and predecessor recall slots."""

    def _white_readout_unchecked(
        self,
        state: QiFieldState,
        allowed_symbols: Sequence[int] | None,
    ) -> OrderedRelationalChromaticReadout:
        current = CyclicChromaticFieldController._white_readout_unchecked(
            self, state, allowed_symbols
        )
        phase_parts = self._codebook_source.codebook(
            0, device=state.field.device, dtype=state.field.dtype
        )
        codebook = torch.complex(phase_parts[..., 0], phase_parts[..., 1])
        relational_coefficients = torch.einsum(
            "aw,wb->ab",
            codebook.conj(),
            self._relational_trace_unchecked(state),
        ) / float(self.config.wave_mode_count)
        relational_scores = relational_coefficients.abs().square().transpose(0, 1)

        allowed = self._allowed_symbols(allowed_symbols)
        if allowed is None:
            relational_symbols = torch.argmax(relational_scores, dim=1)
        else:
            allowed = allowed.to(device=state.field.device)
            local = torch.argmax(relational_scores.index_select(1, allowed), dim=1)
            relational_symbols = allowed.index_select(0, local)

        floor = self.config.readout_energy_floor
        current_scale = current.scores.amax(dim=1, keepdim=True).clamp_min(floor)
        relational_max = relational_scores.amax(dim=1, keepdim=True)
        relational_scale = relational_max.clamp_min(floor)
        ordered_scores = torch.maximum(
            current.scores / current_scale,
            relational_scores / relational_scale,
        )
        relational_available = current.available & (relational_max[:, 0] >= floor)
        candidates = torch.arange(
            self.config.alphabet_size, device=state.field.device
        )[None, :]
        predecessor_slot = (
            relational_available[:, None]
            & (relational_symbols != current.symbols)[:, None]
            & (candidates == relational_symbols[:, None])
        )
        current_slot = current.available[:, None] & (
            candidates == current.symbols[:, None]
        )
        ordered_scores = torch.where(
            predecessor_slot,
            torch.full_like(ordered_scores, 2.0),
            ordered_scores,
        )
        ordered_scores = torch.where(
            current_slot,
            torch.full_like(ordered_scores, 3.0),
            ordered_scores,
        )
        ordered_scores = torch.where(
            current.available[:, None], ordered_scores, current.scores
        )

        return OrderedRelationalChromaticReadout(
            bank_scores=current.bank_scores,
            scores=ordered_scores,
            symbols=current.symbols,
            available=current.available,
            contributions=current.contributions,
            differential_rms=current.differential_rms,
            bank_energy=current.bank_energy,
            active_bank_count=current.active_bank_count,
            white_coherence=current.white_coherence,
            current_scores=current.scores,
            current_symbols=current.symbols,
            relational_scores=relational_scores,
            relational_symbols=relational_symbols,
            relational_available=relational_available,
        )
    def white_readout(
        self,
        state: QiFieldState,
        *,
        allowed_symbols: Sequence[int] | None = None,
    ) -> OrderedRelationalChromaticReadout:
        self._validate_state(state)
        return self._white_readout_unchecked(state, allowed_symbols)



__all__ = [
    "ORDERED_RELATIONAL_CHANNEL_NAMES",
    "ORDERED_RELATIONAL_LAYOUT_PROFILE_ID",
    "ORDERED_RELATIONAL_OPERATOR_PROFILE_ID",
    "ORDERED_RELATIONAL_PROJECTION_PROFILE_ID",
    "OrderedRelationalChromaticFieldConfig",
    "OrderedRelationalChromaticFieldController",
    "OrderedRelationalChromaticReadout",
    "PsychedelicProjection",
    "WhiteChromaticHeartbeatReceipt",
    "WhiteChromaticTick",
]
