from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_market_scenarios import SCENARIO_PROFILES, build_scenario_manifest, generate_scenario_bars
from cassi_repeat_sweep import run_promote_repeat_sweep


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure native promote phase versus repeated field writes")
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-promote-repeat-sweep-v1.json"))
    parser.add_argument("--bars", type=int, default=352)
    parser.add_argument("--source-windows", type=int, default=4)
    parser.add_argument("--repeat-counts", default="1,2,3,4")
    parser.add_argument("--target-starts", default="32,64,96")
    args = parser.parse_args()
    try:
        repeat_counts = tuple(int(part.strip()) for part in args.repeat_counts.split(",") if part.strip())
        target_starts = tuple(int(part.strip()) for part in args.target_starts.split(",") if part.strip())
    except ValueError as exc:
        raise SystemExit("repeat and target options must be comma-separated integers") from exc
    assignments = {
        "JUMP": SCENARIO_PROFILES["positive_jump"],
        "TREND": SCENARIO_PROFILES["trend"],
        "REVERSAL": SCENARIO_PROFILES["reversal"],
        "VOLATILE": SCENARIO_PROFILES["volatile"],
    }
    bars = {
        instrument: generate_scenario_bars(args.bars, symbol=instrument, profile=profile)
        for instrument, profile in assignments.items()
    }
    receipt = run_promote_repeat_sweep(
        bars,
        source_instrument="JUMP",
        target_instruments=("TREND", "REVERSAL", "VOLATILE"),
        source_windows=args.source_windows,
        source_repeat_counts=repeat_counts,
        target_starts=target_starts,
        source_manifest=build_scenario_manifest(assignments, bar_count=args.bars),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "content_sha256": receipt["content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
