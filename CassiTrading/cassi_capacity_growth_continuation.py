"""Continue chronological field learning after an explicit capacity migration."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from cassi_trading_foundry import (  # noqa: E402
    FoundryConfig,
    RefinementField,
    ReplayConfig,
    StrategyProgram,
    content_digest_matches,
    digest_value,
    load_bars_csv,
    run_foundry,
    write_foundry_receipt,
)
from cassi_raw_event_field import CapacityError  # noqa: E402


CONTINUATION_SCHEMA = "cassi.trading-capacity-growth-continuation.v1"


def _sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _program_from_document(document: dict[str, Any]) -> StrategyProgram:
    return StrategyProgram(
        strategy_id=str(document["strategy_id"]),
        source=str(document["source"]),
        parameters=dict(document["parameters"]),
        family=str(document["family"]),
        parent_id=document.get("parent_id"),
        mutation=str(document.get("mutation", "seed")),
    )


def _config_from_document(document: dict[str, Any]) -> FoundryConfig:
    replay = document["replay"]
    return FoundryConfig(
        train_fraction=float(document["train_fraction"]),
        validation_fraction=float(document["validation_fraction"]),
        validation_slices=int(document["validation_slices"]),
        max_rounds=int(document["max_rounds"]),
        max_candidates_per_round=int(document["max_candidates_per_round"]),
        minimum_improvement=float(document["minimum_improvement"]),
        minimum_trades=int(document["minimum_trades"]),
        maximum_drawdown=float(document["maximum_drawdown"]),
        learn_field=bool(document["learn_field"]),
        replay=ReplayConfig(
            fee_bps=float(replay["fee_bps"]),
            slippage_bps=float(replay["slippage_bps"]),
            initial_equity=float(replay["initial_equity"]),
            max_position=float(replay["max_position"]),
            timeframe_hours=float(replay["timeframe_hours"]),
        ),
    )


def continue_after_migration(
    *,
    data_path: Path,
    source_checkpoint: Path,
    predecessor_receipt: Path,
    migration_receipt: Path,
    output_root: Path,
    start_index: int,
    window_count: int,
    window_bars: int,
    scenario_id: str,
) -> dict[str, Any]:
    parent = json.loads(predecessor_receipt.read_text(encoding="utf-8"))
    migration = json.loads(migration_receipt.read_text(encoding="utf-8"))
    if not content_digest_matches(parent):
        raise ValueError("predecessor continuation receipt digest mismatch")
    if not content_digest_matches(migration):
        raise ValueError("migration receipt digest mismatch")
    bars = load_bars_csv(data_path, symbol="BTC-USD")
    if start_index < 0 or start_index >= len(bars):
        raise ValueError("start index is outside the market history")
    if window_count < 1 or window_bars < 1:
        raise ValueError("window count and width must be positive")

    field = RefinementField.restore(source_checkpoint.read_bytes())
    program = _program_from_document(parent["final"]["program"])
    protocol_config = _config_from_document(parent["protocol"]["config"])
    output_root.mkdir(parents=True, exist_ok=True)
    windows: list[dict[str, Any]] = []
    learning_enabled = True

    for window_index in range(window_count):
        begin = start_index + window_index * window_bars
        if begin >= len(bars):
            break
        end = min(begin + window_bars, len(bars))
        segment = bars[begin:end]
        if len(segment) < 12:
            break
        window_root = output_root / f"window-{window_index:02d}"
        window_root.mkdir(parents=True, exist_ok=True)
        before_checkpoint = field.learner.checkpoint_bytes()
        before_field_sha256 = field.fingerprint()
        before_program = program.document()
        config = FoundryConfig(
            train_fraction=protocol_config.train_fraction,
            validation_fraction=protocol_config.validation_fraction,
            validation_slices=protocol_config.validation_slices,
            max_rounds=protocol_config.max_rounds,
            max_candidates_per_round=protocol_config.max_candidates_per_round,
            minimum_improvement=protocol_config.minimum_improvement,
            minimum_trades=protocol_config.minimum_trades,
            maximum_drawdown=protocol_config.maximum_drawdown,
            learn_field=protocol_config.learn_field and learning_enabled,
            replay=protocol_config.replay,
        )
        try:
            foundry = run_foundry(
                segment,
                seed=program,
                config=config,
                field_memory=field,
            )
        except CapacityError as exc:
            field = RefinementField.restore(before_checkpoint)
            learning_enabled = False
            capacity = {
                "schema": "cassi.trading-capacity-event.v1",
                "status": "CAPACITY_LIMIT",
                "window_index": window_index,
                "start_index": begin,
                "end_index": end - 1,
                "bars": len(segment),
                "data_sha256": digest_value([bar.as_dict() for bar in segment]),
                "timestamp_start": segment[0].timestamp,
                "timestamp_end": segment[-1].timestamp,
                "error": str(exc),
                "field_sha256": before_field_sha256,
                "field_before_sha256": before_field_sha256,
                "field_after_sha256": before_field_sha256,
                "field_changed": False,
                "field_learning": "capacity-rejected",
                "program_sha256": program.program_sha256,
                "parent_program": before_program,
                "selected_program": before_program,
            }
            (window_root / "capacity_event.json").write_text(
                json.dumps(capacity, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            windows.append(capacity)
            continue

        if not content_digest_matches(foundry):
            raise ValueError(f"foundry receipt digest mismatch at window {window_index}")
        foundry_path = window_root / "foundry_receipt.json"
        write_foundry_receipt(foundry_path, foundry)
        after_checkpoint = field.learner.checkpoint_bytes()
        checkpoint_path = window_root / "refinement_field.chk"
        checkpoint_path.write_bytes(after_checkpoint)
        selected = foundry["selected"]
        program = _program_from_document(selected)
        windows.append(
            {
                "status": "PASS",
                "window_index": window_index,
                "start_index": begin,
                "end_index": end - 1,
                "timestamp_start": segment[0].timestamp,
                "timestamp_end": segment[-1].timestamp,
                "bars": len(segment),
                "data_sha256": foundry["data"]["data_sha256"],
                "field_before_sha256": before_field_sha256,
                "field_after_sha256": field.fingerprint(),
                "field_changed": before_field_sha256 != field.fingerprint(),
                "field_learning": "adaptive" if config.learn_field else "frozen-after-capacity",
                "checkpoint_path": str(checkpoint_path),
                "checkpoint_sha256": _sha256(after_checkpoint),
                "checkpoint_bytes": len(after_checkpoint),
                "foundry_receipt_path": str(foundry_path),
                "foundry_receipt_sha256": foundry["content_sha256"],
                "holdout_metrics": foundry["holdout"]["metrics"],
                "selected_program": selected,
                "parent_program": before_program,
                "receipt_verification": "PASS",
            }
        )

    if not windows:
        raise ValueError("no continuation windows were produced")
    final_checkpoint = field.learner.checkpoint_bytes()
    final_program = program.document()
    body: dict[str, Any] = {
        "schema": CONTINUATION_SCHEMA,
        "status": (
            "PASS"
            if learning_enabled
            else "PASS_WITH_CAPACITY_LIMIT"
        ),
        "scenario_id": scenario_id,
        "data": {
            "source_file": str(data_path),
            "symbol": bars[0].symbol,
            "bars": len(bars),
            "first_timestamp": bars[0].timestamp,
            "last_timestamp": bars[-1].timestamp,
            "data_sha256": digest_value([bar.as_dict() for bar in bars]),
            "start_index": start_index,
            "used_bars": sum(row.get("bars", 0) for row in windows),
            "unused_tail_bars": max(0, len(bars) - (windows[-1]["end_index"] + 1)),
        },
        "protocol": {
            "description": "chronological adaptive continuation after explicit wave-width migration",
            "online_learning_only": False,
            "window_bars": window_bars,
            "window_count": len(windows),
            "predecessor_receipt": str(predecessor_receipt),
            "migration_receipt": str(migration_receipt),
            "migration_receipt_sha256": migration["content_sha256"],
            "predecessor_field_sha256": parent["final"]["field_sha256"],
            "predecessor_program_sha256": parent["final"]["program"]["program_sha256"],
            "config": protocol_config.as_dict(),
        },
        "initial": {
            "field_sha256": windows[0]["field_before_sha256"],
            "program": windows[0]["parent_program"],
        },
        "final": {
            "field_sha256": field.fingerprint(),
            "checkpoint_path": str(output_root / "final_refinement_field.chk"),
            "checkpoint_sha256": _sha256(final_checkpoint),
            "program": final_program,
        },
        "windows": windows,
    }
    body["content_sha256"] = digest_value(body)
    (output_root / "final_refinement_field.chk").write_bytes(final_checkpoint)
    (output_root / "continuation_receipt.json").write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--source-checkpoint", type=Path, required=True)
    parser.add_argument("--predecessor-receipt", type=Path, required=True)
    parser.add_argument("--migration-receipt", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--start-index", type=int, required=True)
    parser.add_argument("--window-count", type=int, required=True)
    parser.add_argument("--window-bars", type=int, required=True)
    parser.add_argument("--scenario-id", required=True)
    args = parser.parse_args()
    receipt = continue_after_migration(
        data_path=args.data,
        source_checkpoint=args.source_checkpoint,
        predecessor_receipt=args.predecessor_receipt,
        migration_receipt=args.migration_receipt,
        output_root=args.output_root,
        start_index=args.start_index,
        window_count=args.window_count,
        window_bars=args.window_bars,
        scenario_id=args.scenario_id,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
