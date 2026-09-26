"""Measure how repeated writes change native promote phase."""

from __future__ import annotations
from typing import Any, Mapping, Sequence

from cassi_market_contracts import digest_value
from cassi_raw_event_field import CapacityError
from cassi_trading_foundry import MarketBar
from cassi_transfer import TransferConfig
from cassi_transfer_reach import run_transfer_reach_matrix


REPEAT_SWEEP_SCHEMA = "cassi.native-promote-repeat-sweep.v1"


def run_promote_repeat_sweep(
    bars_by_instrument: Mapping[str, Sequence[MarketBar]],
    *,
    source_instrument: str,
    target_instruments: Sequence[str],
    source_windows: int = 4,
    source_repeat_counts: Sequence[int] = (1, 2, 3, 4),
    target_starts: Sequence[int] = (32, 64, 96),
    step_bars: int = 32,
    source_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repeats = tuple(source_repeat_counts)
    targets = tuple(sorted(target_instruments))
    if isinstance(source_windows, bool) or not isinstance(source_windows, int) or not 1 <= source_windows <= 8:
        raise ValueError("source_windows must be an integer in [1, 8]")
    if not repeats or tuple(sorted(set(repeats))) != repeats or any(
        isinstance(repeat, bool) or not isinstance(repeat, int) or not 1 <= repeat <= 4
        for repeat in repeats
    ):
        raise ValueError("source_repeat_counts must be strictly increasing integers in [1, 4]")
    if not targets or source_instrument in targets:
        raise ValueError("source and target instruments must be disjoint and targets nonempty")
    results: list[dict[str, Any]] = []
    for source_repeats in repeats:
        try:
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
                source_repeats=source_repeats,
            )
        except CapacityError as exc:
            results.append(
                {
                    "source_repeats": source_repeats,
                    "status": "capacity_rejected",
                    "error": str(exc),
                }
            )
            continue
        target_rows = [
            row
            for cell in receipt["cells"]
            for row in cell["target_arms"]["native"]
        ]
        lesion_rows = [
            row
            for cell in receipt["cells"]
            for row in cell["target_arms"]["lesion"]
        ]
        support_rows = [
            row
            for cell in receipt["cells"]
            for row in cell["target_arms"]["supported-control"]
        ]
        source_trace = receipt["cells"][0]["source_training"]
        native_by_start = {
            str(start): sum(
                row["strict_promote_authority"]
                for row in target_rows
                if row["start_index"] == start
            )
            for start in target_starts
        }
        results.append(
            {
                "source_repeats": source_repeats,
                "source_field_sha256": receipt["cells"][0]["source_field_sha256"],
                "source_pre_update_outcomes": [
                    row["field_prediction"].get("outcome") for row in source_trace
                ],
                "source_field_l2": [
                    sum(value * value for value in row["field_state_vector"]) ** 0.5
                    for row in source_trace
                ],
                "native_authority_count": sum(row["strict_promote_authority"] for row in target_rows),
                "native_authority_rate": sum(row["strict_promote_authority"] for row in target_rows) / len(target_rows),
                "native_authority_by_target_start": native_by_start,
                "authority_horizon": max(
                    (start for start in target_starts if native_by_start[str(start)] == len(targets)),
                    default=None,
                ),
                "lesion_authority_count": sum(row["strict_promote_authority"] for row in lesion_rows),
                "supported_control_authority_count": sum(row["strict_promote_authority"] for row in support_rows),
                "target_row_count": len(target_rows),
            }
        )
    body: dict[str, Any] = {
        "schema": REPEAT_SWEEP_SCHEMA,
        "source_instrument": source_instrument,
        "target_instruments": list(targets),
        "source_windows": source_windows,
        "source_repeat_counts": list(repeats),
        "target_starts": list(target_starts),
        "step_bars": step_bars,
        "decision_rule": "status=supported AND outcome=promote",
        "results": results,
        "controls": {
            "lesion_authority_must_be_zero": True,
            "supported_control_must_fire": True,
            "source_repeat_bound": 4,
        },
    }
    if source_manifest is not None:
        body["source_manifest"] = dict(source_manifest)
    body["content_sha256"] = digest_value(body)
    return body


__all__ = ["REPEAT_SWEEP_SCHEMA", "run_promote_repeat_sweep"]
