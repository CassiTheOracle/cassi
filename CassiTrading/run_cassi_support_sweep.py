from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_market_scenarios import SCENARIO_PROFILES, build_scenario_manifest, generate_scenario_bars
from cassi_support_sweep import run_support_sweep
from cassi_transfer import TransferConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep bounded source-learning support acquisition")
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-support-sweep-v1.json"))
    parser.add_argument("--bars", type=int, default=352)
    parser.add_argument("--max-source-windows", type=int, default=8)
    args = parser.parse_args()
    assignments = {
        "TREND": SCENARIO_PROFILES["trend"],
        "REVERSAL": SCENARIO_PROFILES["reversal"],
        "VOLATILE": SCENARIO_PROFILES["volatile"],
        "JUMP": SCENARIO_PROFILES["positive_jump"],
    }
    bars = {
        instrument: generate_scenario_bars(args.bars, symbol=instrument, profile=profile)
        for instrument, profile in assignments.items()
    }
    receipt = run_support_sweep(
        bars,
        base_config=TransferConfig(step_bars=32, target_start=32, target_windows=1),
        max_source_windows=args.max_source_windows,
        source_manifest=build_scenario_manifest(assignments, bar_count=args.bars),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "content_sha256": receipt["content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
