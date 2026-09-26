#!/usr/bin/env python3
"""Run the Cassi Trading Foundry on synthetic or local CSV market data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_trading_foundry import (
    FoundryConfig,
    RefinementField,
    ReplayConfig,
    generate_demo_bars,
    load_bars_csv,
    run_foundry,
    verify_foundry_receipt,
    write_foundry_receipt,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, help="timestamp/OHLCV CSV; omit for deterministic demo data")
    parser.add_argument("--symbol", default=None, help="symbol to select when the CSV has a symbol column")
    parser.add_argument("--demo-bars", type=int, default=240)
    parser.add_argument("--out-dir", type=Path, default=Path("_diag/trading-foundry"))
    parser.add_argument("--field-in", type=Path, help="restore a prior RefinementField checkpoint")
    parser.add_argument("--field-out", type=Path, help="write the updated field checkpoint here")
    parser.add_argument("--frozen-field", action="store_true", help="reuse field predictions without adding new lessons")
    parser.add_argument("--max-rounds", type=int, default=4)
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--fee-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bars = (
        load_bars_csv(args.csv, symbol=args.symbol)
        if args.csv is not None
        else generate_demo_bars(args.demo_bars, symbol=args.symbol or "BTCUSDT")
    )
    config = FoundryConfig(
        max_rounds=args.max_rounds,
        max_candidates_per_round=args.max_candidates,
        learn_field=not args.frozen_field,
        replay=ReplayConfig(fee_bps=args.fee_bps, slippage_bps=args.slippage_bps),
    )
    field = (
        RefinementField.restore(args.field_in.read_bytes())
        if args.field_in is not None
        else RefinementField()
    )
    receipt = run_foundry(bars, config=config, field_memory=field)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = args.out_dir / "foundry_receipt.json"
    field_path = args.field_out or args.out_dir / "refinement_field.chk"
    field_path.parent.mkdir(parents=True, exist_ok=True)
    write_foundry_receipt(receipt_path, receipt)
    field_path.write_bytes(field.checkpoint_bytes())
    verification = verify_foundry_receipt(receipt)
    print(
        json.dumps(
            {
                "status": verification["status"],
                "receipt": str(receipt_path),
                "selected_program_sha256": verification["selected_program_sha256"],
                "field_before_sha256": receipt["field"]["before_sha256"],
                "field_after_sha256": receipt["field"]["after_sha256"],
                "field_checkpoint": str(field_path),
                "holdout_metrics": receipt["holdout"]["metrics"],
                "refinement_rounds": len(receipt["development"]["rounds"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
