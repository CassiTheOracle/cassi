from __future__ import annotations

import unittest

from cassi_market_contracts import Authority
from cassi_policy import (
    PolicyError,
    PortfolioController,
    PortfolioPolicyConfig,
    PortfolioState,
    ProgramSignal,
)


class PortfolioPolicyTests(unittest.TestCase):
    def _authority(self, mode: str = "research") -> Authority:
        return Authority(
            mode=mode,
            objective_id="policy-test",
            permission_generation="permission-1",
            revocation_generation="revocation-1",
        )

    def _signals(self) -> tuple[ProgramSignal, ...]:
        return (
            ProgramSignal(
                signal_id="btc-signal",
                program_id="program-btc",
                instrument="BTCUSD",
                regime_id="regime:trend-up",
                direction=1.0,
                expected_edge=0.10,
                expected_risk=0.01,
                applicability_status="evaluated",
                event_id="event-btc",
                observation_id="observation-btc",
                available_at="2025-01-01T01:00:00Z",
                support_roots=("program-root",),
            ),
            ProgramSignal(
                signal_id="eth-signal",
                program_id="program-eth",
                instrument="ETHUSD",
                regime_id="regime:trend-down",
                direction=-1.0,
                expected_edge=0.08,
                expected_risk=0.02,
                applicability_status="evaluated",
                event_id="event-eth",
                observation_id="observation-eth",
                available_at="2025-01-01T01:00:00Z",
            ),
            ProgramSignal(
                signal_id="xrp-signal",
                program_id="program-xrp",
                instrument="XRPUSD",
                regime_id="regime:warming",
                direction=1.0,
                expected_edge=0.04,
                expected_risk=0.02,
                applicability_status="inapplicable",
                event_id="event-xrp",
                observation_id="observation-xrp",
                available_at="2025-01-01T01:00:00Z",
            ),
        )

    def test_policy_respects_gross_net_and_turnover_constraints(self) -> None:
        controller = PortfolioController(
            policy_id="policy-1",
            config=PortfolioPolicyConfig(
                max_position=0.6,
                max_net_exposure=0.3,
                max_turnover=0.2,
                risk_budget_per_position=0.4,
            ),
        )
        state = PortfolioState(equity=1.0, positions={"BTCUSD": 0.2, "ETHUSD": -0.2})
        decision = controller.decide(
            state,
            self._signals(),
            authority=self._authority(),
            operation_id="operation-1",
        )
        targets = decision["target_exposures"]
        self.assertLessEqual(sum(abs(value) for value in targets.values()), 0.7 + 1.0e-12)
        self.assertLessEqual(abs(sum(targets.values())), 0.3 + 1.0e-12)
        turnover = sum(abs(targets[key] - state.positions.get(key, 0.0)) for key in targets)
        self.assertLessEqual(turnover, 0.2 + 1.0e-12)
        self.assertIn("max-turnover", decision["constraints_applied"])
        self.assertEqual(decision["external_effect"], "none; intent-only")
        self.assertTrue(all(order["status"] == "hypothetical" for order in decision["orders"]))

    def test_inapplicable_signal_abstains_and_authority_mode_is_visible(self) -> None:
        controller = PortfolioController(policy_id="policy-2")
        decision = controller.decide(
            PortfolioState(equity=1.0, positions={"XRPUSD": 0.1}),
            (self._signals()[-1],),
            authority=self._authority("shadow"),
            operation_id="operation-2",
        )
        self.assertEqual(decision["orders"], [])
        self.assertTrue(any(row["reason"] == "program-inapplicable" for row in decision["abstentions"]))
        self.assertEqual(decision["target_exposures"]["XRPUSD"], 0.1)

    def test_authorized_mode_still_only_emits_pending_intents(self) -> None:
        controller = PortfolioController(policy_id="policy-3")
        decision = controller.decide(
            PortfolioState(equity=1.0),
            (self._signals()[0],),
            authority=self._authority("authorized"),
            operation_id="operation-3",
        )
        self.assertTrue(decision["orders"])
        self.assertEqual(decision["orders"][0]["status"], "authorized-pending-execution")
        self.assertEqual(decision["external_effect"], "none; intent-only")

    def test_evaluated_signal_requires_positive_risk(self) -> None:
        with self.assertRaises(PolicyError):
            ProgramSignal(
                signal_id="invalid",
                program_id="program",
                instrument="BTCUSD",
                regime_id="regime:range",
                direction=1.0,
                expected_edge=0.1,
                expected_risk=0.0,
                applicability_status="evaluated",
                event_id="event",
                observation_id="observation",
                available_at="2025-01-01T00:00:00Z",
            )

    def test_decisions_are_deterministic(self) -> None:
        controller = PortfolioController(policy_id="policy-4")
        state = PortfolioState(equity=1.0)
        first = controller.decide(state, self._signals(), authority=self._authority(), operation_id="operation-4")
        second = controller.decide(state, self._signals(), authority=self._authority(), operation_id="operation-4")
        self.assertEqual(first, second)
        self.assertEqual(len(first["content_sha256"]), 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
