#!/usr/bin/env python3
"""Behavioral contracts for field-native raw-event acquisition."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cassi_raw_event_field import (
    AcquisitionProfile,
    CapacityError,
    CheckpointError,
    EventError,
    RawEvent,
    RawEventLearner,
    canonical_packet,
    decode_packet,
    encode_packet,
)
from cassi_raw_event_store import RawEventStore
from run_cassi_raw_event_scenario import (
    ambiguity_case,
    capacity_and_horizon_case,
    ordinary_case,
    restart_case,
    revocation_case,
    temporal_case,
    promotion_control_case,
)


class PacketContractTests(unittest.TestCase):
    def test_unordered_semantics_preserve_wire_order(self) -> None:
        first = encode_packet((b"entity", b"c"))
        second = encode_packet((b"c", b"entity"))
        self.assertNotEqual(first, second)
        self.assertEqual(decode_packet(first), (b"entity", b"c"))
        self.assertEqual(canonical_packet(first), canonical_packet(second))


class FieldAcquisitionTests(unittest.TestCase):
    def test_withheld_entity_and_two_step_composition(self) -> None:
        result = ordinary_case(101)
        self.assertEqual(result["withheld_plan"]["status"], "supported")
        self.assertEqual(len(result["withheld_plan"]["plan_hex"]), 2)
        self.assertEqual(result["unsupported_prediction"]["status"], "unresolved")
        self.assertEqual(result["erased_prediction"]["status"], "unresolved")

    def test_temporal_history_changes_same_current_decision(self) -> None:
        result = temporal_case(202)
        self.assertEqual(result["prediction_a"]["status"], "supported")
        self.assertEqual(result["prediction_b"]["status"], "supported")
        self.assertNotEqual(
            result["prediction_a"]["payload_hex"],
            result["prediction_b"]["payload_hex"],
        )
        self.assertEqual(result["without_history"]["status"], "unresolved")
        self.assertTrue(
            all(row["status"] == "unresolved" for row in result["after_history_erase"])
        )

    def test_symmetric_conflict_is_not_guessed(self) -> None:
        result = ambiguity_case(303)
        self.assertEqual(result["prediction"]["status"], "unresolved")
        self.assertEqual(result["prediction"]["reason"], "field-emission-is-ambiguous")

    def test_targeted_relation_intervention_is_causal_and_selective(self) -> None:
        learner = RawEventLearner()
        observation = encode_packet((b"A", b"c"))
        action = encode_packet((b"x",))
        outcome = encode_packet((b"A", b"r"))
        unrelated_observation = encode_packet((b"B", b"d"))
        unrelated_action = encode_packet((b"z",))
        unrelated_outcome = encode_packet((b"B", b"s"))
        sequence = 1
        for _ in range(2):
            for event in (
                RawEvent(sequence, "reset"),
                RawEvent(sequence + 1, "observation", observation),
                RawEvent(sequence + 2, "action", action),
                RawEvent(sequence + 3, "observation", outcome),
            ):
                learner.apply(event)
            sequence += 4
        for _ in range(2):
            for event in (
                RawEvent(sequence, "reset"),
                RawEvent(sequence + 1, "observation", unrelated_observation),
                RawEvent(sequence + 2, "action", unrelated_action),
                RawEvent(sequence + 3, "observation", unrelated_outcome),
            ):
                learner.apply(event)
            sequence += 4
        before = learner.predict(action, observation=observation, history=None)
        erased, receipt = learner.intervene(
            "relation", action=action, observation=observation, history=None
        )
        unrelated_before = learner.predict(
            unrelated_action, observation=unrelated_observation, history=None
        )
        self.assertEqual(before["status"], "supported")
        self.assertTrue(receipt["changed"])
        self.assertEqual(
            erased.predict(action, observation=observation, history=None)["status"],
            "unresolved",
        )
        unrelated_after = erased.predict(
            unrelated_action, observation=unrelated_observation, history=None
        )
        self.assertEqual(unrelated_before["status"], "supported")
        self.assertEqual(unrelated_after["status"], "supported")
        self.assertEqual(
            unrelated_after["payload_hex"], unrelated_before["payload_hex"]
        )

    def test_promotion_flag_controls_consolidated_survival(self) -> None:
        result = promotion_control_case(101)
        self.assertTrue(
            all(not row["promoted"] for row in result["provisional_receipts"])
        )
        self.assertFalse(result["consolidated_intervention"]["changed"])
        self.assertEqual(
            result["after_provisional_intervention"]["status"], "unresolved"
        )
        self.assertTrue(all(row["promoted"] for row in result["promoted_receipts"]))
        self.assertEqual(
            result["promoted_after_provisional_intervention"]["status"],
            "supported",
        )
        self.assertEqual(
            result["static_prediction"]["payload_hex"],
            result["dynamic_prediction"]["payload_hex"],
        )
        self.assertTrue(result["inference_preserved_state"])

    def test_checkpoint_is_exact_and_tamper_rejected(self) -> None:
        learner = RawEventLearner()
        observation = encode_packet((b"c",))
        action = encode_packet((b"x",))
        outcome = encode_packet((b"r",))
        learner.apply(RawEvent(1, "observation", observation))
        learner.apply(RawEvent(2, "action", action))
        learner.apply(RawEvent(3, "observation", outcome))
        checkpoint = learner.checkpoint_bytes()
        restored = RawEventLearner.restore(checkpoint)
        self.assertEqual(restored.fingerprint(), learner.fingerprint())
        damaged = bytearray(checkpoint)
        damaged[-1] ^= 1
        with self.assertRaises(CheckpointError):
            RawEventLearner.restore(damaged)

    def test_capacity_rejection_retries_through_consolidation(self) -> None:
        learner = RawEventLearner(AcquisitionProfile(component_limit=4.0))
        contexts = (b"FDD", b"FCO", b"FED", b"FFL", b"FST")
        mutations = (
            b"Me+",
            b"Me-",
            b"Mx+",
            b"Mx-",
            b"Mf+",
            b"Mf-",
            b"Ms+",
            b"Ms-",
            b"Mh+",
            b"Mh-",
            b"Mmr",
            b"Mbr",
            b"Mtf",
            b"Mmc",
            b"Mve",
            b"Mrr",
        )
        consolidation_receipts: list[dict[str, object]] = []
        capacity_rejections = 0
        sequence = 1
        for context in contexts:
            for mutation in mutations:
                for _ in range(4):
                    try:
                        learner.apply(RawEvent(sequence, "reset"))
                        learner.apply(
                            RawEvent(sequence + 1, "observation", encode_packet((context,)))
                        )
                        learner.apply(
                            RawEvent(sequence + 2, "action", encode_packet((mutation,)))
                        )
                        receipt = learner.apply(
                            RawEvent(sequence + 3, "observation", encode_packet((b"O+",)))
                        )
                    except CapacityError:
                        capacity_rejections += 1
                    else:
                        if receipt["consolidation_attempted"]:
                            consolidation_receipts.append(receipt)
                    sequence += 10

        self.assertTrue(consolidation_receipts)
        receipt = consolidation_receipts[0]
        self.assertGreaterEqual(receipt["consolidation_steps"], 1)
        self.assertEqual(len(receipt["consolidations"]), 1)
        self.assertEqual(
            receipt["consolidations"][0]["mode"],
            "controller-multiscale-reprojection",
        )
        self.assertGreater(capacity_rejections, 0)
        self.assertTrue(learner.snapshot()["all_finite"])

    def test_component_capacity_profile_extends_admission_horizon(self) -> None:
        observation = encode_packet((b"o",))
        action = encode_packet((b"a",))
        outcome = encode_packet((b"x",))

        def admissions(component_limit: float) -> tuple[int, RawEventLearner]:
            learner = RawEventLearner(AcquisitionProfile(component_limit=component_limit))
            count = 0
            for index in range(1, 100):
                sequence = index * 10
                try:
                    learner.apply(RawEvent(sequence, "reset"))
                    learner.apply(RawEvent(sequence + 1, "observation", observation))
                    learner.apply(RawEvent(sequence + 2, "action", action))
                    learner.apply(RawEvent(sequence + 3, "observation", outcome))
                except CapacityError:
                    break
                count += 1
            return count, learner

        default_count, default = admissions(0.5)
        expanded_count, expanded = admissions(1.0)
        self.assertGreater(expanded_count, default_count)
        self.assertLessEqual(float(expanded.snapshot()["max_abs"]), 1.0 + 1.0e-10)
        self.assertNotEqual(default.profile.fingerprint, expanded.profile.fingerprint)
        restored = RawEventLearner.restore(expanded.checkpoint_bytes())
        self.assertEqual(restored.profile.component_limit, 1.0)
        self.assertEqual(restored.fingerprint(), expanded.fingerprint())


class DurableStoreTests(unittest.TestCase):
    def test_mid_action_restart_and_exact_once_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = restart_case(101, Path(directory))
        self.assertEqual(result["duplicate_receipt"]["status"], "duplicate")
        self.assertEqual(result["post_restart_prediction"]["status"], "supported")

    def test_conflicting_retry_is_rejected_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event = RawEvent(1, "observation", encode_packet((b"a",)))
            with RawEventStore(root) as store:
                store.admit(event)
                before = store.learner.fingerprint()
                with self.assertRaises(EventError):
                    store.admit(
                        RawEvent(1, "observation", encode_packet((b"b",)))
                    )
                self.assertEqual(store.learner.fingerprint(), before)

    def test_episode_revocation_rebuilds_corrected_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = revocation_case(202, Path(directory))
        self.assertEqual(result["after"]["status"], "supported")
        self.assertTrue(
            all(
                row["scope"] == "entire-reset-bounded-episode"
                for row in result["revocations"]
            )
        )

    def test_capacity_rejection_and_long_inference_horizon(self) -> None:
        result = capacity_and_horizon_case(303)
        self.assertTrue(result["capacity_rejected"])
        self.assertTrue(result["capacity_predecessor_preserved"])
        self.assertEqual(result["inference_queries"], 1024)
        self.assertTrue(result["snapshot"]["all_finite"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
