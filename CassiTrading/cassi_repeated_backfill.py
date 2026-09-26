#!/usr/bin/env python3
"""Expose one canonical trading field to the same history repeatedly."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from cassi_historical_backfill import run_backfill
from cassi_trading_foundry import StrategyProgram, content_digest_matches, digest_value


SCHEMA = "cassi.trading-repeated-backfill.v1"


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


def _pass_summary(
    *,
    index: int,
    receipt: dict[str, Any],
    receipt_path: Path,
    input_checkpoint_sha256: str,
    previous_program_sha256: str,
) -> dict[str, Any]:
    windows = receipt["windows"]
    return {
        "pass_index": index,
        "status": receipt["status"],
        "input_checkpoint_sha256": input_checkpoint_sha256,
        "input_field_sha256": receipt["initial"]["field_sha256"],
        "output_checkpoint_sha256": receipt["final"]["checkpoint_sha256"],
        "output_field_sha256": receipt["final"]["field_sha256"],
        "field_changed": receipt["initial"]["field_sha256"] != receipt["final"]["field_sha256"],
        "input_program_sha256": receipt["initial"]["program"]["program_sha256"],
        "previous_program_sha256": previous_program_sha256,
        "output_program_sha256": receipt["final"]["program"]["program_sha256"],
        "strategy_id": receipt["final"]["program"]["strategy_id"],
        "window_count": len(windows),
        "adaptive_windows": sum(1 for row in windows if row["field_learning"] == "adaptive"),
        "frozen_windows": sum(1 for row in windows if row["field_learning"] == "frozen-after-capacity"),
        "field_changed_windows": sum(1 for row in windows if row["field_changed"]),
        "capacity_event": receipt["capacity_event"],
        "data_sha256": receipt["data"]["data_sha256"],
        "bars": receipt["data"]["bars"],
        "receipt_path": str(receipt_path),
        "receipt_sha256": _sha256(receipt_path.read_bytes()),
    }


def run_repeated(
    *,
    history_paths: tuple[Path, ...],
    output_root: Path,
    initial_checkpoint_path: Path,
    initial_receipt_path: Path,
    passes: int,
    window_bars: int,
) -> dict[str, Any]:
    if passes < 1:
        raise ValueError("passes must be at least 1")
    initial_receipt = json.loads(initial_receipt_path.read_text(encoding="utf-8"))
    if not content_digest_matches(initial_receipt):
        raise ValueError("initial receipt content digest mismatch")
    expected_checkpoint = Path(initial_receipt["final"]["checkpoint_path"])
    if _sha256(initial_checkpoint_path.read_bytes()) != initial_receipt["final"]["checkpoint_sha256"]:
        raise ValueError("initial checkpoint does not match initial receipt")
    if expected_checkpoint.read_bytes() != initial_checkpoint_path.read_bytes():
        raise ValueError("initial checkpoint path does not match initial receipt path")

    output_root.mkdir(parents=True, exist_ok=True)
    checkpoint_path = initial_checkpoint_path
    program = _program_from_document(initial_receipt["final"]["program"])
    previous_program_sha256 = program.program_sha256
    pass_rows: list[dict[str, Any]] = []
    stopped_on_capacity = False

    for index in range(1, passes + 1):
        pass_root = output_root / f"pass-{index:03d}"
        input_checkpoint_sha256 = _sha256(checkpoint_path.read_bytes())
        receipt = run_backfill(
            history_paths=history_paths,
            output_root=pass_root,
            window_bars=window_bars,
            initial_checkpoint_path=checkpoint_path,
            initial_program=program,
        )
        receipt_path = pass_root / "backfill_receipt.json"
        if not content_digest_matches(receipt):
            raise ValueError(f"repeated pass {index} receipt digest mismatch")
        row = _pass_summary(
            index=index,
            receipt=receipt,
            receipt_path=receipt_path,
            input_checkpoint_sha256=input_checkpoint_sha256,
            previous_program_sha256=previous_program_sha256,
        )
        pass_rows.append(row)
        checkpoint_path = Path(receipt["final"]["checkpoint_path"])
        program = _program_from_document(receipt["final"]["program"])
        previous_program_sha256 = program.program_sha256
        if receipt["capacity_event"] is not None:
            stopped_on_capacity = True
            break

    final_receipt = pass_rows[-1]
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "PASS_WITH_CAPACITY_LIMIT" if stopped_on_capacity else "PASS",
        "protocol": {
            "description": "same completed history replayed chronologically through one carried field",
            "one_field_lineage": True,
            "chronological_each_pass": True,
            "passes_requested": passes,
            "passes_completed": len(pass_rows),
            "window_bars": window_bars,
        },
        "history": {
            "source_files": [str(path) for path in history_paths],
            "bars": final_receipt["bars"],
            "data_sha256": final_receipt["data_sha256"],
        },
        "initial": {
            "receipt_path": str(initial_receipt_path),
            "receipt_sha256": _sha256(initial_receipt_path.read_bytes()),
            "checkpoint_path": str(initial_checkpoint_path),
            "checkpoint_sha256": _sha256(initial_checkpoint_path.read_bytes()),
            "field_sha256": initial_receipt["final"]["field_sha256"],
            "program_sha256": initial_receipt["final"]["program"]["program_sha256"],
        },
        "passes": pass_rows,
        "final": {
            "checkpoint_path": final_receipt["receipt_path"].replace("backfill_receipt.json", "final_refinement_field.chk"),
            "checkpoint_sha256": final_receipt["output_checkpoint_sha256"],
            "field_sha256": final_receipt["output_field_sha256"],
            "program_sha256": final_receipt["output_program_sha256"],
            "strategy_id": final_receipt["strategy_id"],
        },
    }
    body["content_sha256"] = digest_value(body)
    receipt_path = output_root / "repeated_receipt.json"
    receipt_path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, nargs="+", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--initial-receipt", type=Path, required=True)
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--window-bars", type=int, default=720)
    args = parser.parse_args()
    print(
        json.dumps(
            run_repeated(
                history_paths=tuple(args.history),
                output_root=args.output_root,
                initial_checkpoint_path=args.initial_checkpoint,
                initial_receipt_path=args.initial_receipt,
                passes=args.passes,
                window_bars=args.window_bars,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
