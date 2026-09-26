from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_market_scenarios import SCENARIO_PROFILES, build_scenario_manifest, generate_scenario_bars
from cassi_transfer import CrossInstrumentTransferCampaign, TransferConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Run heterogeneous scenario transfer across distinct market dynamics")
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-heterogeneous-transfer-v1.json"))
    parser.add_argument("--bars", type=int, default=160)
    parser.add_argument("--step-bars", type=int, default=32)
    parser.add_argument("--source-windows", type=int, default=4)
    parser.add_argument("--target-starts", default="32,64,96")
    args = parser.parse_args()
    try:
        target_starts = tuple(int(part.strip()) for part in args.target_starts.split(",") if part.strip())
    except ValueError as exc:
        raise SystemExit("--target-starts must be comma-separated positive integers") from exc
    if not target_starts:
        raise SystemExit("--target-starts must contain at least one integer")
    assignments = {
        "TREND": SCENARIO_PROFILES["trend"],
        "REVERSAL": SCENARIO_PROFILES["reversal"],
        "VOLATILE": SCENARIO_PROFILES["volatile"],
    }
    bars = {
        instrument: generate_scenario_bars(args.bars, symbol=instrument, profile=profile)
        for instrument, profile in assignments.items()
    }
    receipt = CrossInstrumentTransferCampaign(
        TransferConfig(
            step_bars=args.step_bars,
            source_windows=args.source_windows,
            target_start=target_starts[0],
            target_windows=1,
            target_starts=target_starts,
        )
    ).run(
        bars,
        source_manifest=build_scenario_manifest(assignments, bar_count=args.bars),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "content_sha256": receipt["content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
