from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_market_scenarios import SCENARIO_PROFILES, build_scenario_manifest, generate_scenario_bars
from cassi_source_order_match import run_source_order_match


def main() -> int:
    parser = argparse.ArgumentParser(description="Match market lesson order to isolated field replay")
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-source-order-match-v1.json"))
    parser.add_argument("--bars", type=int, default=352)
    args = parser.parse_args()
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
    receipt = run_source_order_match(
        bars,
        source_instrument="JUMP",
        target_instruments=("TREND", "REVERSAL", "VOLATILE"),
    )
    receipt["source_manifest"] = build_scenario_manifest(assignments, bar_count=args.bars)
    from cassi_market_contracts import digest_value
    receipt["content_sha256"] = digest_value({key: value for key, value in receipt.items() if key != "content_sha256"})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "content_sha256": receipt["content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
