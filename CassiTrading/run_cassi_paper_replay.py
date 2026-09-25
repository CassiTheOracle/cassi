from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_paper import PaperSession
from cassi_paper_replay import compare_paper_to_replay
from cassi_trading_foundry import StrategyProgram


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare paper-bar signals with historical replay")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("_diag/paper-replay-parity.json"))
    args = parser.parse_args()
    session = PaperSession.load_state(args.state, StrategyProgram.seed())
    receipt = compare_paper_to_replay(
        session.history,
        session.receipts,
        session.program,
        venue=session.config.venue,
        fee_bps=session.config.fee_bps,
        slippage_bps=session.config.slippage_bps,
        initial_equity=session.config.initial_cash,
        timeframe_hours=session.config.timeframe_seconds / 3600.0,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(args.out), "signal_parity": receipt["signal_parity"], "content_sha256": receipt["content_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
