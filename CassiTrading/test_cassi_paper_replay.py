from __future__ import annotations

import copy
import unittest

from cassi_market_scenarios import SCENARIO_PROFILES, generate_scenario_bars
from cassi_paper import PaperSession
from cassi_paper_replay import compare_paper_to_replay
from cassi_trading_foundry import StrategyProgram


class PaperReplayParityTests(unittest.TestCase):
    def test_paper_signals_and_fill_count_match_historical_replay(self) -> None:
        bars = generate_scenario_bars(96, symbol="PAPER", profile=SCENARIO_PROFILES["positive_jump"])
        session = PaperSession(StrategyProgram.seed())
        for bar in bars:
            session.process_bar(bar)
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
        self.assertTrue(receipt["signal_parity"])
        self.assertTrue(receipt["fill_comparison"]["fill_count_matches"])
        self.assertEqual(receipt["mismatches"], [])
        self.assertEqual(len(receipt["content_sha256"]), 64)

    def test_signal_mutation_is_visible_to_parity_receipt(self) -> None:
        bars = generate_scenario_bars(96, symbol="PAPER", profile=SCENARIO_PROFILES["positive_jump"])
        session = PaperSession(StrategyProgram.seed())
        for bar in bars:
            session.process_bar(bar)
        receipts = copy.deepcopy(session.receipts)
        event_id = bars[40].as_event(
            source_id="paper:coinbase-public-paper", source_revision="closed-bar-v1"
        ).event_id
        receipts[event_id]["signal"]["direction"] = 0.0
        receipt = compare_paper_to_replay(
            session.history,
            receipts,
            session.program,
            venue=session.config.venue,
            fee_bps=session.config.fee_bps,
            slippage_bps=session.config.slippage_bps,
            initial_equity=session.config.initial_cash,
            timeframe_hours=session.config.timeframe_seconds / 3600.0,
        )
        self.assertFalse(receipt["signal_parity"])
        self.assertTrue(any(row["reason"] == "signal-mismatch" for row in receipt["mismatches"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
