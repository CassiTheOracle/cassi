from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_market_sources import HistoricalSource, load_historical_sources
from cassi_transfer import CrossInstrumentTransferCampaign, TransferConfig
from cassi_trading_foundry import generate_demo_bars


def _load_bars(args: argparse.Namespace):
    if not args.source:
        return {
            "BTCUSD": generate_demo_bars(args.bars, symbol="BTCUSD"),
            "ETHUSD": generate_demo_bars(args.bars, symbol="ETHUSD"),
        }, None
    sources: list[HistoricalSource] = []
    for source_spec in args.source:
        if "=" not in source_spec:
            raise SystemExit(f"--source must have SYMBOL=CSV form: {source_spec}")
        symbol, raw_path = source_spec.split("=", 1)
        symbol = symbol.strip()
        if not symbol or not raw_path.strip():
            raise SystemExit(f"--source must have SYMBOL=CSV form: {source_spec}")
        sources.append(
            HistoricalSource(
                source_id=f"csv:{symbol}",
                path=Path(raw_path),
                symbol=symbol,
                source_revision=args.source_revision,
                availability_lag_seconds=args.availability_lag_seconds,
            )
        )
    dataset = load_historical_sources(sources)
    return dataset.bars_by_instrument, dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Cassi cross-instrument transfer matrix")
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-transfer-matrix-v1.json"))
    parser.add_argument("--bars", type=int, default=128)
    parser.add_argument("--source", action="append", help="Historical source as SYMBOL=CSV; repeat per instrument")
    parser.add_argument("--availability-lag-seconds", type=int, default=0)
    parser.add_argument("--step-bars", type=int, default=8)
    parser.add_argument("--target-starts", help="Comma-separated target window starts, e.g. 32,64,96")
    parser.add_argument("--source-windows", type=int, default=4)
    parser.add_argument("--target-windows", type=int, default=4)
    args = parser.parse_args()
    target_starts = ()
    if args.target_starts:
        try:
            target_starts = tuple(int(part.strip()) for part in args.target_starts.split(",") if part.strip())
        except ValueError as exc:
            raise SystemExit("--target-starts must be comma-separated positive integers") from exc
        if not target_starts:
            raise SystemExit("--target-starts must contain at least one integer")
    bars, dataset = _load_bars(args)
    campaign = CrossInstrumentTransferCampaign(
        TransferConfig(
            step_bars=args.step_bars,
            source_windows=args.source_windows,
            target_start=target_starts[0] if target_starts else 64,
            target_windows=args.target_windows,
            target_starts=target_starts,
        ),
    )
    receipt = campaign.run_dataset(dataset) if dataset is not None else campaign.run(bars)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "content_sha256": receipt["content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
