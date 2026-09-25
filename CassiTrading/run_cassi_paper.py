from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from cassi_paper import CoinbaseClosedCandleSource, PaperConfig, PaperSession
from cassi_trading_foundry import StrategyProgram, load_bars_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Cassi in local paper-only mode")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", type=Path, help="closed OHLCV bars for deterministic paper replay")
    source.add_argument("--coinbase-product", help="public Coinbase product, e.g. BTC-USD")
    parser.add_argument("--granularity", type=int, default=3600)
    parser.add_argument("--poll-seconds", type=float, default=60.0)
    parser.add_argument("--once", action="store_true", help="fetch one public candle snapshot and exit")
    parser.add_argument("--state", type=Path, default=Path("_diag/paper-state.json"))
    parser.add_argument("--out", type=Path, default=Path("_diag/paper-latest.json"))
    parser.add_argument("--initial-cash", type=float, default=10_000.0)
    parser.add_argument("--fee-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--max-drawdown", type=float, default=0.20)
    parser.add_argument("--max-bars", type=int, default=0)
    args = parser.parse_args()
    if args.poll_seconds <= 0.0:
        raise SystemExit("--poll-seconds must be positive")
    if args.max_bars < 0:
        raise SystemExit("--max-bars cannot be negative")
    program = StrategyProgram.seed()
    config = PaperConfig(
        venue="coinbase-public-paper" if args.coinbase_product else "csv-paper",
        initial_cash=args.initial_cash,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        max_drawdown=args.max_drawdown,
        timeframe_seconds=args.granularity,
    )
    if args.state.is_file():
        session = PaperSession.load_state(args.state, program)
        if session.config != config:
            raise SystemExit("paper state configuration mismatch")
    else:
        session = PaperSession(program, config=config)
    processed = 0

    def consume(bars) -> None:
        nonlocal processed
        for bar in bars:
            receipt = session.process_bar(bar)
            session.save_state(args.state)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            processed += 1
            if args.max_bars and processed >= args.max_bars:
                return

    if args.csv is not None:
        consume(load_bars_csv(args.csv))
    else:
        feed = CoinbaseClosedCandleSource(args.coinbase_product, granularity=args.granularity)
        while True:
            consume(feed.fetch_closed())
            if args.once or (args.max_bars and processed >= args.max_bars):
                break
            time.sleep(args.poll_seconds)
    print(
        json.dumps(
            {
                "status": "PASS",
                "paper_only": True,
                "processed_bars": processed,
                "state": str(args.state),
                "latest": str(args.out),
                "equity": session.account.equity,
                "cash": session.account.cash,
                "positions": session.account.positions,
                "frozen": session.account.frozen,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
