from __future__ import annotations

import copy
import unittest

from cassi_aggressive_residency import (
    AccountState,
    AggressiveResidencyConfig,
    _market_context,
    _sha256,
)
from cassi_temporal_promotion import TEMPORAL_PROMOTION_SCHEMA, TEMPORAL_RUNTIME_SCHEMA
from cassi_temporal_tail_audit import run_temporal_tail_audit, verify_temporal_tail_audit
from cassi_trading_foundry import AcquisitionProfile, RefinementField, StrategyProgram, digest_value
from run_cassi_trading_benchmark import _bar_series


class TemporalTailAuditTests(unittest.TestCase):
    @staticmethod
    def _field() -> RefinementField:
        return RefinementField(
            profile=AcquisitionProfile(
                wave_width=2048,
                energy_limit=512.0,
                component_limit=4.0,
            )
        )

    @staticmethod
    def _config() -> AggressiveResidencyConfig:
        return AggressiveResidencyConfig(
            warmup_bars=36,
            decision_interval=4,
            lesson_interval=12,
            outcome_horizon=4,
            max_hold_bars=48,
            cooldown_bars=24,
            purposeful_replay_episodes=2,
            stress_episodes=2,
        )

    def _fixture(self):
        bars = _bar_series(
            "mixed",
            count=100,
            symbol="TAIL-AUDIT",
            phase_offset=0.91,
        )
        config = self._config()
        program = StrategyProgram.seed()
        tail_start = 60
        context_start = tail_start - (config.warmup_bars - 1)
        account = AccountState(equity=1.1, peak_equity=1.2)
        starting = self._field().checkpoint_bytes()
        promoted_field = RefinementField.restore(starting)
        context = _market_context(
            bars[context_start:],
            config.warmup_bars - 1,
            program=program,
            account=account,
            fine_context={},
            config=config,
        )
        promoted_field.learn_market_action(
            context["learning_context_ids"],
            "target:+0.50",
            "promote",
            repeats=2,
        )
        promoted = promoted_field.checkpoint_bytes()
        data_sha256 = digest_value([bar.as_dict() for bar in bars])
        campaign = {
            "schema": TEMPORAL_PROMOTION_SCHEMA,
            "status": "PASS",
            "protocol": {
                "promotion_config": {
                    "minimum_objective_delta": 0.0,
                    "maximum_drawdown_increase": 0.25,
                },
                "residency_config": config.as_dict(),
            },
            "data": {"data_sha256": data_sha256},
            "initial_field": {"checkpoint_sha256": _sha256(starting)},
            "final_field": {"checkpoint_sha256": _sha256(promoted)},
        }
        campaign["content_sha256"] = digest_value(campaign)
        runtime = {
            "schema": TEMPORAL_RUNTIME_SCHEMA,
            "field_checkpoint_sha256": _sha256(promoted),
            "field_sha256": promoted_field.fingerprint(),
            "program": program.document(),
            "account": account.document(),
            "completed_cycles": 1,
            "promotion_count": 1,
            "reset_count": 0,
            "observed_until": bars[tail_start - 1].timestamp,
            "next_bar_index": tail_start,
            "receipt_content_sha256": campaign["content_sha256"],
        }
        runtime["content_sha256"] = digest_value(runtime)
        return bars, config, program, starting, promoted, campaign, runtime

    def test_reserved_tail_is_matched_frozen_and_independently_verifiable(self) -> None:
        bars, config, program, starting, promoted, campaign, runtime = self._fixture()
        promoted_before = bytes(promoted)
        starting_before = bytes(starting)

        receipt = run_temporal_tail_audit(
            bars,
            promoted_checkpoint=promoted,
            starting_checkpoint=starting,
            program=program,
            residency_config=config,
            runtime_state=runtime,
            promotion_receipt=campaign,
        )
        verification = verify_temporal_tail_audit(
            receipt,
            promoted_checkpoint=promoted,
            starting_checkpoint=starting,
        )

        self.assertEqual(verification["status"], "PASS")
        self.assertEqual(receipt["tail"]["start_index"], runtime["next_bar_index"])
        self.assertEqual(receipt["tail"]["reserved_bars"], 40)
        self.assertEqual(
            len(receipt["arms"]["promoted_field"]["decisions"]),
            len(receipt["arms"]["starting_field_control"]["decisions"]),
        )
        self.assertFalse(receipt["arms"]["promoted_field"]["field"]["changed"])
        self.assertFalse(receipt["arms"]["starting_field_control"]["field"]["changed"])
        self.assertEqual(promoted, promoted_before)
        self.assertEqual(starting, starting_before)

        tampered = copy.deepcopy(receipt)
        tampered["comparison"]["changed_targets"] += 1
        tampered["content_sha256"] = digest_value(
            {key: value for key, value in tampered.items() if key != "content_sha256"}
        )
        with self.assertRaises(ValueError):
            verify_temporal_tail_audit(
                tampered,
                promoted_checkpoint=promoted,
                starting_checkpoint=starting,
            )

    def test_source_mutation_is_rejected_before_tail_is_spent(self) -> None:
        bars, config, program, starting, promoted, campaign, runtime = self._fixture()
        mutated = copy.deepcopy(campaign)
        mutated["data"]["data_sha256"] = "0" * 64
        mutated["content_sha256"] = digest_value(
            {key: value for key, value in mutated.items() if key != "content_sha256"}
        )
        runtime = copy.deepcopy(runtime)
        runtime["receipt_content_sha256"] = mutated["content_sha256"]
        runtime["content_sha256"] = digest_value(
            {key: value for key, value in runtime.items() if key != "content_sha256"}
        )

        with self.assertRaisesRegex(ValueError, "history differs"):
            run_temporal_tail_audit(
                bars,
                promoted_checkpoint=promoted,
                starting_checkpoint=starting,
                program=program,
                residency_config=config,
                runtime_state=runtime,
                promotion_receipt=mutated,
            )


if __name__ == "__main__":
    unittest.main()
