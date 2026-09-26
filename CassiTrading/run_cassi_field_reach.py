from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_field_reach import FieldReachConfig, run_field_reach_arms
from cassi_trading_foundry import RefinementField


def main() -> int:
    parser = argparse.ArgumentParser(description="Run controlled Cassi field-readout reach arms")
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-field-readout-reach-v1.json"))
    parser.add_argument("--lessons", default="promote", help="Comma-separated native field lessons")
    parser.add_argument("--support-repeats", type=int, default=1)
    args = parser.parse_args()
    lessons = tuple(part.strip() for part in args.lessons.split(",") if part.strip())
    if not lessons or any(lesson not in {"promote", "reject", "uncertain"} for lesson in lessons):
        raise SystemExit("--lessons must contain promote, reject, or uncertain")
    field = RefinementField()
    for lesson in lessons:
        field.learn_program("edge", "synthesized-transfer-program", lesson, repeats=1)
    receipt = run_field_reach_arms(
        field,
        FieldReachConfig(support_repeats=args.support_repeats),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "content_sha256": receipt["content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
