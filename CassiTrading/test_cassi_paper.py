from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cassi_market_scenarios import SCENARIO_PROFILES, generate_scenario_bars
from cassi_paper import PaperAccount, PaperConfig, PaperExecutionEngine, PaperSession, PaperTradingError
from cassi_trading_foundry import StrategyProgram


class PaperRuntimeTests(unittest.TestCase):
    def _bars(self):
        return generate_scenario_bars(96, symbol="PAPER", profile=SCENARIO_PROFILES["positive_jump"])

    def test_closed_bar_session_emits_shadow_policy_and_paper_fills(self) -> None:
        session = PaperSession(
            StrategyProgram.seed(),
            config=PaperConfig(initial_cash=10_000.0, fee_bps=10.0, slippage_bps=5.0),
        )
        receipts = [session.process_bar(bar) for bar in self._bars()]
        self.assertTrue(all(receipt["paper_only"] for receipt in receipts))
        self.assertTrue(all(receipt["external_effect"] == "none" for receipt in receipts))
        self.assertTrue(all(receipt["policy_decision"]["authority"]["mode"] == "shadow" for receipt in receipts))
        self.assertTrue(any(receipt["fill"] is not None for receipt in receipts))
        self.assertGreater(session.account.equity, 0.0)

    def test_duplicate_bar_is_idempotent_and_restart_preserves_state(self) -> None:
        bars = self._bars()
        session = PaperSession(StrategyProgram.seed())
        for bar in bars[:40]:
            session.process_bar(bar)
        duplicate = session.process_bar(bars[39])
        self.assertEqual(duplicate, session.receipts[bars[39].as_event(source_id="paper:coinbase-public-paper", source_revision="closed-bar-v1").event_id])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper-state.json"
            session.save_state(path)
            restored = PaperSession.load_state(path, StrategyProgram.seed())
            self.assertEqual(restored.snapshot(), session.snapshot())
            restored.process_bar(bars[40])
            session.process_bar(bars[40])
            self.assertEqual(restored.snapshot(), session.snapshot())

    def test_short_target_is_fail_closed(self) -> None:
        config = PaperConfig(allow_short=False)
        engine = PaperExecutionEngine(config)
        account = PaperAccount.create(config.initial_cash)
        with self.assertRaises(PaperTradingError):
            engine.execute_target(
                account,
                self._bars()[0],
                target_exposure=-0.5,
                operation_id="paper:test:short",
                event_id="event:short",
            )

    def test_non_monotonic_bar_is_rejected(self) -> None:
        bars = self._bars()
        session = PaperSession(StrategyProgram.seed())
        session.process_bar(bars[1])
        with self.assertRaises(PaperTradingError):
            session.process_bar(bars[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
