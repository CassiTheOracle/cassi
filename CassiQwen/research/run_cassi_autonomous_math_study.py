#!/usr/bin/env python3
"""Run or inspect the complete autonomous Cassi mathematics course."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_CASSIQWEN = _ROOT / "CassiQwen"
if str(_CASSIQWEN) not in sys.path:
    sys.path.insert(0, str(_CASSIQWEN))

from cassi_autonomous_math_study import (  # noqa: E402
    COURSE,
    COURSE_BY_ID,
    AutonomousMathStudy,
    LocalQwenClient,
    StudyError,
    atomic_json,
    content_digest_matches,
    course_manifest,
    digest_value,
)

DEFAULT_ROOT = _CASSIQWEN / "_diag" / "autonomous-math"
DEFAULT_MODEL = _CASSIQWEN / "Qwen3.8-27B-UD-IQ1_S.gguf"


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))

def _completed_checkpoint(
    controller: AutonomousMathStudy, unit_id: str, output: Path
) -> dict[str, Any] | None:
    if not output.is_file():
        return None
    value = json.loads(output.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not content_digest_matches(value):
        raise StudyError(f"invalid checkpoint receipt: {output}")
    if value.get("course", {}).get("content_sha256") != course_manifest()["content_sha256"]:
        raise StudyError(f"checkpoint course identity mismatch: {output}")
    if not value.get("ready_to_continue"):
        return None
    active_program = controller.promoted_program_sha256(unit_id)
    examination = value.get("protected_examination")
    if (
        active_program is None
        or not isinstance(examination, dict)
        or examination.get("status") != "passed"
        or examination.get("program_sha256") != active_program
        or value.get("regression", {}).get("status") != "passed"
    ):
        raise StudyError(f"checkpoint no longer matches the promoted field program: {output}")
    return {
        "unit_id": unit_id,
        "receipt": str(output),
        "ready_to_continue": True,
        "content_sha256": value["content_sha256"],
        "resumed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Autonomous field-owned M0-M26 mathematics study with an offline Qwen teacher"
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--teacher-url", default="http://127.0.0.1:8084")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--unit", default="m8-determinant-2x2")
    parser.add_argument("--start-level", type=int, default=0)
    parser.add_argument("--end-level", type=int, default=26)
    parser.add_argument("--max-units", type=int, help="maximum new units to study; valid checkpoints are skipped")
    parser.add_argument("--plan", action="store_true", help="print the complete course without invoking Qwen")
    parser.add_argument("--run-all", action="store_true", help="continue sequentially through the requested level range")
    args = parser.parse_args()

    if args.plan:
        _print(course_manifest())
        return 0
    if args.unit not in COURSE_BY_ID:
        parser.error(f"unknown --unit: {args.unit}")
    if not 0 <= args.start_level <= args.end_level <= 26:
        parser.error("level range must satisfy 0 <= start <= end <= 26")
    if args.max_units is not None and args.max_units < 1:
        parser.error("--max-units must be positive")

    args.root.mkdir(parents=True, exist_ok=True)
    teacher = LocalQwenClient(args.teacher_url, model_path=args.model)
    controller = AutonomousMathStudy(
        args.root / "field",
        args.root / "audit-state.json",
        teacher=teacher,
    )

    if not args.run_all:
        receipt = controller.run_unit(args.unit)
        output = args.root / f"{args.unit}-receipt.json"
        atomic_json(output, receipt)
        _print(
            {
                "receipt": str(output),
                "unit": args.unit,
                "ready_to_continue": receipt["ready_to_continue"],
                "content_sha256": receipt["content_sha256"],
                "resources": receipt["resource_accounting"],
            }
        )
        return 0 if receipt["ready_to_continue"] else 1

    selected = [
        unit for unit in COURSE if args.start_level <= unit.level <= args.end_level
    ]
    receipts = []
    new_runs = 0
    stopped_at = None
    for unit in selected:
        output = args.root / f"{unit.unit_id}-receipt.json"
        checkpoint = _completed_checkpoint(controller, unit.unit_id, output)
        if checkpoint is not None:
            receipts.append(checkpoint)
            continue
        if args.max_units is not None and new_runs >= args.max_units:
            break
        receipt = controller.run_unit(unit.unit_id)
        atomic_json(output, receipt)
        row = {
            "unit_id": unit.unit_id,
            "receipt": str(output),
            "ready_to_continue": receipt["ready_to_continue"],
            "content_sha256": receipt["content_sha256"],
            "resumed": False,
        }
        receipts.append(row)
        new_runs += 1
        if not receipt["ready_to_continue"]:
            stopped_at = unit.unit_id
            break
    completed_ids = {row["unit_id"] for row in receipts if row["ready_to_continue"]}
    next_unit = next(
        (unit.unit_id for unit in selected if unit.unit_id not in completed_ids),
        None,
    )
    campaign = {
        "course": course_manifest(),
        "requested_levels": [args.start_level, args.end_level],
        "units": receipts,
        "completed": len(completed_ids),
        "newly_studied": new_runs,
        "stopped_at": stopped_at,
        "next_unit": next_unit,
    }
    campaign["content_sha256"] = digest_value(campaign)
    output = args.root / "campaign-receipt.json"
    atomic_json(output, campaign)
    _print(
        {
            "receipt": str(output),
            "completed": len(completed_ids),
            "newly_studied": new_runs,
            "next_unit": next_unit,
            "units": receipts,
        }
    )
    return 1 if stopped_at is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
