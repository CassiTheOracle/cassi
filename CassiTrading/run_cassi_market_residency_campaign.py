#!/usr/bin/env python3
"""Run Cassi's chronological multi-window market residency campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_trading_foundry import MarketBar, digest_value, load_bars_csv
from run_cassi_market_residency import (
    ResidencyConfig,
    run_market_residency_campaign,
    verify_market_residency_campaign,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, help="closed historical OHLCV CSV")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--external-windows", type=int, default=5)
    parser.add_argument("--calibration-bars", type=int, default=768)
    parser.add_argument("--external-bars", type=int, default=1536)
    parser.add_argument("--warmup-bars", type=int, default=48)
    parser.add_argument("--review-interval", type=int, default=24)
    parser.add_argument("--fee-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--field-component-limit", type=float, default=4.0)
    parser.add_argument("--field-wave-width", type=int, default=512)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("_diag/market-residency-campaign.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = ResidencyConfig(
        calibration_bars=args.calibration_bars,
        external_bars=args.external_bars,
        warmup_bars=args.warmup_bars,
        review_interval=args.review_interval,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        field_component_limit=args.field_component_limit,
        field_wave_width=args.field_wave_width,
    )
    total_bars = config.external_bars * args.external_windows
    external_bars: tuple[MarketBar, ...] | None
    if args.csv is None:
        external_bars = None
        external_source = {"kind": "synthetic", "source_bars": total_bars}
    else:
        source = load_bars_csv(args.csv, symbol=args.symbol)
        if len(source) < total_bars:
            raise SystemExit(
                f"historical CSV is shorter than the requested {total_bars} external bars"
            )
        external_bars = tuple(source[:total_bars])
        external_source = {
            "kind": "historical_csv",
            "path": str(args.csv),
            "symbol": args.symbol or source[0].symbol,
            "source_bars": len(source),
            "source_data_sha256": digest_value([bar.as_dict() for bar in source]),
        }
    receipt = run_market_residency_campaign(
        config=config,
        external_bars=external_bars,
        window_count=args.external_windows,
        external_source=external_source,
    )
    verification = verify_market_residency_campaign(receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    carried = verification["arms"]["carried_field"]
    frozen = verification["arms"]["frozen_transfer"]
    fresh = verification["arms"]["fresh_field"]
    static = verification["arms"]["static_baseline"]
    print(
        json.dumps(
            {
                "status": verification["status"],
                "out": str(args.out),
                "content_sha256": verification["content_sha256"],
                "windows": verification["windows"],
                "carried_compound_final_equity": carried["compound_final_equity"],
                "frozen_compound_final_equity": frozen["compound_final_equity"],
                "fresh_compound_final_equity": fresh["compound_final_equity"],
                "static_compound_final_equity": static["compound_final_equity"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
