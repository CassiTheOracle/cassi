"""Measure persistence and decay of a native promote field state."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from cassi_market_contracts import digest_value
from cassi_trading_foundry import MarketBar
from cassi_transfer import TransferConfig
from cassi_transfer_reach import run_transfer_reach_matrix


PERSISTENCE_SWEEP_SCHEMA = "cassi.native-promote-persistence.v1"


def _lesson_outcome(admitted: Mapping[str, Any]) -> str:
    attribution = admitted.get("attribution", {})
    if attribution.get("status") != "resolved":
        return "uncertain"
    if attribution.get("risk_breach") is True or attribution.get("direction_correct") is False:
        return "reject"
    error = attribution.get("return_error")
    if isinstance(error, (int, float)) and error < 0.0:
        return "reject"
    if attribution.get("direction_correct") is True:
        return "promote"
    return "uncertain"

def run_promote_persistence_sweep(
    bars_by_instrument: Mapping[str, Sequence[MarketBar]],
    *,
    source_instrument: str,
    target_instruments: Sequence[str],
    source_window_counts: Sequence[int] = (1, 2, 3, 4, 5, 6, 7, 8),
    target_starts: Sequence[int] = (32, 64, 96),
    step_bars: int = 32,
    source_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    counts = tuple(source_window_counts)
    targets = tuple(sorted(target_instruments))
    if not counts or tuple(sorted(set(counts))) != counts or any(
        isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 8 for count in counts
    ):
        raise ValueError("source_window_counts must be strictly increasing integers in [1, 8]")
    if not targets or source_instrument in targets:
        raise ValueError("source and target instruments must be disjoint and targets nonempty")
    results: list[dict[str, Any]] = []
    for source_windows in counts:
        receipt = run_transfer_reach_matrix(
            bars_by_instrument,
            config=TransferConfig(
                step_bars=step_bars,
                source_windows=source_windows,
                target_start=target_starts[0],
                target_windows=1,
                target_starts=tuple(target_starts),
            ),
            source_instruments=(source_instrument,),
            target_instruments=targets,
            record_source_field_vectors=True,
        )
        target_rows = [
            row
            for cell in receipt["cells"]
            for row in cell["target_arms"]["native"]
        ]
        support_rows = [
            row
            for cell in receipt["cells"]
            for row in cell["target_arms"]["supported-control"]
        ]
        lesion_rows = [
            row
            for cell in receipt["cells"]
            for row in cell["target_arms"]["lesion"]
        ]
        starts = tuple(target_starts)
        native_by_start = {
            str(start): sum(
                row["strict_promote_authority"]
                for row in target_rows
                if row["start_index"] == start
            )
            for start in starts
        }
        lesion_by_start = {
            str(start): sum(
                row["strict_promote_authority"]
                for row in lesion_rows
                if row["start_index"] == start
            )
            for start in starts
        }
        results.append(
            {
                "source_state_trace": [
                    {
                        "start_index": row["start_index"],
                        "pre_update_outcome": row["field_prediction"].get("outcome"),
                        "lesson_outcome": _lesson_outcome(row["admitted"]),
                        "admitted": row["admitted"],
                        "field_after_sha256": row["field_after_sha256"],
                        "field_l2": sum(value * value for value in row["field_state_vector"]) ** 0.5,
                        "field_state_vector": row["field_state_vector"],
                    }
                    for row in receipt["cells"][0]["source_training"]
                ],
                "source_pre_update_outcomes": [
                    row["field_prediction"].get("outcome")
                    for row in receipt["cells"][0]["source_training"]
                ],
                "source_lesson_outcomes": [
                    _lesson_outcome(row["admitted"])
                    for row in receipt["cells"][0]["source_training"]
                ],
                "source_windows": source_windows,
                "source_field_sha256": receipt["cells"][0]["source_field_sha256"],
                "prospective_readout": receipt["cells"][0]["source_field_readout"],
                "prospective_strict_promote_authority": receipt["cells"][0]["source_strict_promote_authority"],
                "native_authority_count": sum(row["strict_promote_authority"] for row in target_rows),
                "native_authority_rate": sum(row["strict_promote_authority"] for row in target_rows) / len(target_rows),
                "native_authority_by_target_start": native_by_start,
                "authority_horizon": max(
                    (start for start in starts if native_by_start[str(start)] == len(targets)),
                    default=None,
                ),
                "lesion_authority_count": sum(row["strict_promote_authority"] for row in lesion_rows),
                "lesion_authority_by_target_start": lesion_by_start,
                "supported_control_authority_count": sum(row["strict_promote_authority"] for row in support_rows),
                "target_row_count": len(target_rows),
                "native_readouts": [row["field_readout"] for row in target_rows],
            }
        )
    body: dict[str, Any] = {
        "schema": PERSISTENCE_SWEEP_SCHEMA,
        "source_instrument": source_instrument,
        "target_instruments": list(targets),
        "target_starts": list(target_starts),
        "step_bars": step_bars,
        "decision_rule": "status=supported AND outcome=promote",
        "results": results,
        "controls": {
            "lesion_authority_must_be_zero": True,
            "supported_control_must_fire": True,
            "source_window_bound": 8,
        },
    }
    if source_manifest is not None:
        body["source_manifest"] = dict(source_manifest)
    body["content_sha256"] = digest_value(body)
    return body


__all__ = ["PERSISTENCE_SWEEP_SCHEMA", "run_promote_persistence_sweep"]
