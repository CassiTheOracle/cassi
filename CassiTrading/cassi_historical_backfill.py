"""Replay older market history in strict chronological field order."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from cassi_trading_foundry import (  # noqa: E402
    FoundryConfig,
    RefinementField,
    ReplayConfig,
    StrategyProgram,
    content_digest_matches,
    digest_value,
    load_bars_csv,
    run_backtest,
    run_foundry,
    write_foundry_receipt,
)
from cassi_raw_event_field import AcquisitionProfile, CapacityError  # noqa: E402


BACKFILL_SCHEMA = "cassi.trading-historical-backfill.v1"


def _sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _merge_history(paths: Iterable[Path]) -> tuple[Any, ...]:
    by_timestamp: dict[str, Any] = {}
    for path in paths:
        loaded = load_bars_csv(path, symbol="BTC-USD")
        for bar in loaded:
            previous = by_timestamp.get(bar.timestamp)
            if previous is not None and previous.as_dict() != bar.as_dict():
                raise ValueError(f"conflicting duplicate bar at {bar.timestamp}")
            by_timestamp[bar.timestamp] = bar
    ordered = tuple(by_timestamp[key] for key in sorted(by_timestamp))
    if len(ordered) < 12:
        raise ValueError("merged history is too short")
    for earlier, later in zip(ordered, ordered[1:]):
        if earlier.symbol != later.symbol:
            raise ValueError("merged history contains multiple symbols")
        if later.timestamp <= earlier.timestamp:
            raise ValueError("merged history is not strictly chronological")
    return ordered


def _config() -> FoundryConfig:
    return FoundryConfig(
        train_fraction=0.60,
        validation_fraction=0.20,
        validation_slices=3,
        max_rounds=2,
        max_candidates_per_round=16,
        minimum_improvement=0.0005,
        minimum_trades=3,
        maximum_drawdown=0.35,
        learn_field=True,
        replay=ReplayConfig(
            fee_bps=10.0,
            slippage_bps=5.0,
            initial_equity=1.0,
            max_position=1.0,
            timeframe_hours=1.0,
        ),
    )


def _field_profile() -> AcquisitionProfile:
    return AcquisitionProfile(
        wave_width=2048,
        component_limit=4.0,
        provisional_gain=0.02,
        consolidation_gain=0.02,
    )


def _window_summary(
    *,
    index: int,
    start: int,
    segment: tuple[Any, ...],
    before_field: str,
    parent_program: dict[str, Any],
    selected_program: dict[str, Any],
    receipt: dict[str, Any],
    seed_program: StrategyProgram,
    config: FoundryConfig,
    field: RefinementField,
    checkpoint_path: Path,
    checkpoint_bytes: bytes,
    field_learning: str,
) -> dict[str, Any]:
    holdout_start = int(receipt["data"]["holdout_start"])
    seed_holdout = run_backtest(
        segment,
        seed_program,
        config.replay,
        start_index=holdout_start,
        end_index=len(segment) - 1,
    )
    selected_metrics = receipt["holdout"]["metrics"]
    seed_metrics = seed_holdout.metrics
    return {
        "status": "PASS",
        "window_index": index,
        "start_index": start,
        "end_index": start + len(segment) - 1,
        "bars": len(segment),
        "timestamp_start": segment[0].timestamp,
        "timestamp_end": segment[-1].timestamp,
        "data_sha256": receipt["data"]["data_sha256"],
        "field_before_sha256": before_field,
        "field_after_sha256": field.fingerprint(),
        "field_changed": before_field != field.fingerprint(),
        "field_learning": field_learning,
        "parent_program": parent_program,
        "selected_program": selected_program,
        "selected_mutations": [
            row["selected_mutation"]
            for row in receipt["development"]["rounds"]
            if row["selected_mutation"] is not None
        ],
        "holdout_metrics": receipt["holdout"]["metrics"],
        "seed_holdout_metrics": dict(seed_metrics),
        "objective_delta_vs_seed": float(selected_metrics["objective"])
        - float(seed_metrics["objective"]),
        "foundry_receipt_path": str(receipt_path := checkpoint_path.parent / "foundry_receipt.json"),
        "foundry_receipt_sha256": receipt["content_sha256"],
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": _sha256(checkpoint_bytes),
        "checkpoint_bytes": len(checkpoint_bytes),
        "receipt_verification": "PASS",
    }


def run_backfill(
    *,
    history_paths: tuple[Path, ...],
    output_root: Path,
    window_bars: int,
    initial_checkpoint_path: Path | None = None,
    initial_program: StrategyProgram | None = None,
) -> dict[str, Any]:
    bars = _merge_history(history_paths)
    if window_bars < 32:
        raise ValueError("window bars must be at least 32")
    starts_list = list(range(0, len(bars) - window_bars + 1, window_bars))
    if starts_list:
        tail_start = starts_list[-1] + window_bars
        if len(bars) - tail_start >= 32:
            starts_list.append(tail_start)
    starts = tuple(starts_list)
    if not starts:
        raise ValueError("merged history has no complete windows")
    output_root.mkdir(parents=True, exist_ok=True)
    initial_checkpoint = (
        initial_checkpoint_path.read_bytes() if initial_checkpoint_path is not None else None
    )
    field = (
        RefinementField.restore(initial_checkpoint)
        if initial_checkpoint is not None
        else RefinementField(profile=_field_profile())
    )
    seed_program = initial_program or StrategyProgram.seed()
    program = seed_program
    config = _config()
    learning_enabled = True
    windows: list[dict[str, Any]] = []
    capacity_event: dict[str, Any] | None = None

    for index, start in enumerate(starts):
        segment = bars[start : start + window_bars]
        window_root = output_root / f"window-{index:03d}"
        window_root.mkdir(parents=True, exist_ok=True)
        before_checkpoint = field.learner.checkpoint_bytes()
        before_field = field.fingerprint()
        parent_program = program.document()
        active_config = config if learning_enabled else replace(config, learn_field=False)
        field_learning = "adaptive" if learning_enabled else "frozen-after-capacity"
        try:
            receipt = run_foundry(
                segment,
                seed=program,
                config=active_config,
                field_memory=field,
            )
        except CapacityError as exc:
            if not learning_enabled:
                raise
            field = RefinementField.restore(before_checkpoint)
            learning_enabled = False
            capacity_event = {
                "schema": "cassi.trading-capacity-event.v1",
                "status": "CAPACITY_LIMIT",
                "window_index": index,
                "start_index": start,
                "end_index": start + len(segment) - 1,
                "bars": len(segment),
                "timestamp_start": segment[0].timestamp,
                "timestamp_end": segment[-1].timestamp,
                "data_sha256": digest_value([bar.as_dict() for bar in segment]),
                "error": str(exc),
                "field_sha256": before_field,
                "program_sha256": program.program_sha256,
            }
            capacity_event["content_sha256"] = digest_value(capacity_event)
            (window_root / "capacity_event.json").write_text(
                json.dumps(capacity_event, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            receipt = run_foundry(
                segment,
                seed=program,
                config=replace(config, learn_field=False),
                field_memory=field,
            )
            field_learning = "frozen-after-capacity"
        if not content_digest_matches(receipt):
            raise ValueError(f"foundry digest mismatch at window {index}")
        foundry_path = window_root / "foundry_receipt.json"
        write_foundry_receipt(foundry_path, receipt)
        program = StrategyProgram(
            strategy_id=str(receipt["selected"]["strategy_id"]),
            source=str(receipt["selected"]["source"]),
            parameters=dict(receipt["selected"]["parameters"]),
            family=str(receipt["selected"]["family"]),
            parent_id=receipt["selected"].get("parent_id"),
            mutation=str(receipt["selected"].get("mutation", "seed")),
        )
        checkpoint = field.learner.checkpoint_bytes()
        checkpoint_path = window_root / "refinement_field.chk"
        checkpoint_path.write_bytes(checkpoint)
        summary = _window_summary(
            index=index,
            start=start,
            segment=segment,
            before_field=before_field,
            parent_program=parent_program,
            selected_program=program.document(),
            receipt=receipt,
            seed_program=seed_program,
            config=config,
            field=field,
            checkpoint_path=checkpoint_path,
            checkpoint_bytes=checkpoint,
            field_learning=field_learning,
        )
        summary["foundry_receipt_path"] = str(foundry_path)
        windows.append(summary)

    final_checkpoint = field.learner.checkpoint_bytes()
    final_path = output_root / "final_refinement_field.chk"
    final_path.write_bytes(final_checkpoint)
    body: dict[str, Any] = {
        "schema": BACKFILL_SCHEMA,
        "status": "PASS_WITH_CAPACITY_LIMIT" if capacity_event else "PASS",
        "data": {
            "source_files": [str(path) for path in history_paths],
            "source_file_sha256": {
                str(path): _sha256(path.read_bytes()) for path in history_paths
            },
            "symbol": bars[0].symbol,
            "bars": len(bars),
            "first_timestamp": bars[0].timestamp,
            "last_timestamp": bars[-1].timestamp,
            "data_sha256": digest_value([bar.as_dict() for bar in bars]),
            "deduplicated": True,
            "window_bars": window_bars,
            "window_count": len(windows),
            "unused_tail_bars": max(0, len(bars) - (starts[-1] + window_bars)),
        },
        "protocol": {
            "description": (
                "strict chronological replay from a blank v6 headroom field"
                if initial_checkpoint is None
                else "strict chronological replay continuing from a prior pass checkpoint"
            ),
            "chronological": True,
            "overlap": False,
            "config": config.as_dict(),
            "field_profile": field.learner.profile.as_dict(),
            "seed_program_sha256": seed_program.program_sha256,
            "initial_checkpoint_sha256": (
                None if initial_checkpoint is None else _sha256(initial_checkpoint)
            ),
        },
        "initial": {
            "field_sha256": windows[0]["field_before_sha256"],
            "checkpoint_sha256": (
                None if initial_checkpoint is None else _sha256(initial_checkpoint)
            ),
            "program_source": "seed" if initial_program is None else "prior-pass-final",
            "program": seed_program.document(),
        },
        "final": {
            "field_sha256": field.fingerprint(),
            "checkpoint_path": str(final_path),
            "checkpoint_sha256": _sha256(final_checkpoint),
            "program": program.document(),
        },
        "capacity_event": capacity_event,
        "windows": windows,
    }
    body["content_sha256"] = digest_value(body)
    (output_root / "backfill_receipt.json").write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, nargs="+", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--window-bars", type=int, default=720)
    args = parser.parse_args()
    receipt = run_backfill(
        history_paths=tuple(args.history),
        output_root=args.output_root,
        window_bars=args.window_bars,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
