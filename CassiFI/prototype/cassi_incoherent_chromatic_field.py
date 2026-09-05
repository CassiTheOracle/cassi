"""Phase-insensitive channel-energy recall over the frozen L31 field."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Sequence

import torch

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

INCOHERENT_CHROMATIC_LAYOUT_PROFILE_ID = CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID
INCOHERENT_CHROMATIC_OPERATOR_PROFILE_ID = "cassi.qi-incoherent-chromatic-recall.v1"
INCOHERENT_CHROMATIC_PROJECTION_PROFILE_ID = CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID
INCOHERENT_CHROMATIC_CHANNEL_NAMES = CYCLIC_CHROMATIC_CHANNEL_NAMES
_CHANNEL_COUNT = len(INCOHERENT_CHROMATIC_CHANNEL_NAMES)


@dataclass(frozen=True)
class IncoherentChromaticFieldConfig(CyclicChromaticFieldConfig):
    """Frozen L37 constants with a distinct readout fingerprint."""

    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        encoded = json.dumps(
            {
                "layout_profile_id": INCOHERENT_CHROMATIC_LAYOUT_PROFILE_ID,
                "operator_profile_id": INCOHERENT_CHROMATIC_OPERATOR_PROFILE_ID,
                "projection_profile_id": INCOHERENT_CHROMATIC_PROJECTION_PROFILE_ID,
                "shared_codebook_fingerprint": codebook_fingerprint,
                "config": self.to_dict(),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class IncoherentChromaticFieldController(CyclicChromaticFieldController):
    """L31 dynamics read through phase-insensitive channel energy."""

    def _white_readout_unchecked(
        self,
        state: QiFieldState,
        allowed_symbols: Sequence[int] | None,
    ) -> WhiteChromaticReadout:
        base = super()._white_readout_unchecked(state, allowed_symbols)
        scores = base.bank_scores.mean(dim=0)
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
    "INCOHERENT_CHROMATIC_CHANNEL_NAMES",
    "INCOHERENT_CHROMATIC_LAYOUT_PROFILE_ID",
    "INCOHERENT_CHROMATIC_OPERATOR_PROFILE_ID",
    "INCOHERENT_CHROMATIC_PROJECTION_PROFILE_ID",
    "IncoherentChromaticFieldConfig",
    "IncoherentChromaticFieldController",
    "PsychedelicProjection",
    "WhiteChromaticHeartbeatReceipt",
    "WhiteChromaticReadout",
    "WhiteChromaticTick",
]
