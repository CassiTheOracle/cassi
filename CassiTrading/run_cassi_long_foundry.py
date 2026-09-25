from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_long_foundry import run_long_foundry, verify_long_foundry_receipt
from cassi_trading_foundry import generate_demo_bars, load_bars_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Run chronological field-guided strategy evolution")
    parser.add_argument("--csv", type=Path, help="timestamp/OHLCV CSV")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--demo-bars", type=int, default=240)
    parser.add_argument("--window-bars", type=int, default=720)
    parser.add_argument("--step-bars", type=int, default=720)
    parser.add_argument("--max-windows", type=int, default=None)
    parser.add_argument("--max-rounds", type=int, default=4)
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--validation-slices", type=int, default=2)
    parser.add_argument("--minimum-improvement", type=float, default=0.0005)
    parser.add_argument("--seed-mutation", default=None, help="optional fixed mutation applied to the seed before evolution")
    parser.add_argument("--timeframe-hours", type=float, default=1.0, help="bar duration used for annualized replay metrics")
    parser.add_argument("--fee-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--component-limit", type=float, default=0.5)
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-long-foundry.json"))
    args = parser.parse_args()
    bars = (
        load_bars_csv(args.csv, symbol=args.symbol)
        if args.csv is not None
        else generate_demo_bars(args.demo_bars, symbol=args.symbol or "BTCUSDT")
    )
    receipt = run_long_foundry(
        bars,
        window_bars=args.window_bars,
        step_bars=args.step_bars,
        max_rounds=args.max_rounds,
        max_candidates=args.max_candidates,
        validation_slices=args.validation_slices,
        minimum_improvement=args.minimum_improvement,
        seed_mutation=args.seed_mutation,
        timeframe_hours=args.timeframe_hours,
        fee_bps=args.fee_bps,
        component_limit=args.component_limit,
        slippage_bps=args.slippage_bps,
    )
    verification = verify_long_foundry_receipt(receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": verification["status"],
                "out": str(args.out),
                "content_sha256": verification["content_sha256"],
                "bars": receipt["data"]["bars"],
                "windows": verification["window_count"],
                "program_changed": verification["program_changed"],
                "field_changed": verification["field_changed"],
                "final_program_sha256": verification["final_program_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
