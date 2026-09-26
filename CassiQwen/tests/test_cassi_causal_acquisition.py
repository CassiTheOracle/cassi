#!/usr/bin/env python3
"""Behavioral contracts for online causal acquisition in the Cassi field."""

from __future__ import annotations

import json
import struct
import unittest

import cassi_causal_event_field as _causal
from cassi_causal_event_field import CausalEventLearner, CausalProfile
from cassi_raw_event_field import (
    AcquisitionProfile,
    CapacityError,
    CheckpointError,
)
from run_cassi_causal_acquisition import (
    capacity_profile_sweep,
    closed_loop_case,
    collision_and_intervention_case,
    composition_and_transfer_case,
    continual_restart_capacity_case,
    corrupted_pairing_case,
    expose,
    high_capacity_profile,
    inquiry_case,
    policy_comparison_case,
    randomized_symbols,
)


class OnlineCausalAcquisitionTests(unittest.TestCase):
    def test_online_learning_improves_within_session_against_frozen_control(self) -> None:
        result = closed_loop_case(101)
        online = result["online"]
        frozen = result["frozen"]
        self.assertGreater(
            online["last_window_goal_rate"], online["first_window_goal_rate"]
        )
        self.assertGreater(
            online["last_window_goal_rate"], frozen["last_window_goal_rate"]
        )
        self.assertGreater(online["field_owned_decisions"], 0)
        self.assertEqual(online["field_mutations_during_decision"], 0)
        self.assertEqual(frozen["field_mutations_during_decision"], 0)

    def test_prediction_error_gates_conditional_memory_without_compounding_retry(self) -> None:
        result = policy_comparison_case(101)
        gated = result["arms"]["mismatch-gated"]
        always = result["arms"]["always-conditional"]
        unconditional = result["arms"]["unconditional-only"]
        self.assertTrue(gated["branch_a_correct"])
        self.assertTrue(gated["branch_b_correct"])
        self.assertLess(gated["conditional_writes"], always["conditional_writes"])
        self.assertEqual(unconditional["conditional_writes"], 0)
        self.assertEqual(
            result["exact_once"]["first_admission"]["admission_scale"], 2
        )
        self.assertFalse(result["exact_once"]["retry_admission"]["learned"])

    def test_promotion_moves_one_relation_instead_of_doubling_it(self) -> None:
        observation, action, outcome = randomized_symbols(0xA551, 3)
        learner = CausalEventLearner(high_capacity_profile())
        first = expose(
            learner,
            observation=observation,
            action=action,
            outcome=outcome,
        )
        second = expose(
            learner,
            observation=observation,
            action=action,
            outcome=outcome,
        )
        scales = learner.snapshot()["scales"]
        self.assertEqual(first["admission"]["admission_scale"], 0)
        self.assertEqual(second["admission"]["admission_scale"], 1)
        self.assertEqual(
            second["admission"]["promotion_operation"],
            "move-provisional-to-consolidated",
        )
        self.assertLess(scales[0]["mean_square"], 1.0e-24)
        self.assertGreater(scales[1]["mean_square"], 0.0)

    def test_promotion_requires_reset_bounded_provisional_witness(self) -> None:
        observation, action, outcome = randomized_symbols(0xB7A1, 3)
        learner = CausalEventLearner(high_capacity_profile())

        learner.reset()
        learner.observe(observation, learn=False)
        learner.decide((action,), outcome)
        first = learner.observe(outcome)
        provisional_sha256 = learner.scale_sha256(0)
        consolidated_sha256 = learner.scale_sha256(1)
        first_episode = learner.episode_index

        learner.observe(observation, learn=False)
        same_episode = learner.decide((action,), outcome)
        self.assertEqual(same_episode["decision_kind"], "field-supported")
        self.assertEqual(same_episode["action_hex"], action.hex())
        duplicate = learner.observe(outcome)
        self.assertFalse(duplicate["promoted"])
        self.assertEqual(
            duplicate["reason"],
            "confirmation-did-not-start-from-episode-entry-field",
        )
        self.assertFalse(duplicate["learned"])
        self.assertEqual(learner.scale_sha256(0), provisional_sha256)
        self.assertEqual(learner.scale_sha256(1), consolidated_sha256)

        learner.reset()
        confirmation_episode = learner.episode_index
        learner.observe(observation, learn=False)
        learner.decide((action,), outcome)
        checkpoint = learner.checkpoint_bytes()
        restored = CausalEventLearner.restore(
            checkpoint, expected_profile=learner.profile
        )
        uninterrupted_receipt = learner.observe(outcome)
        restored_receipt = restored.observe(outcome)

        self.assertEqual(first["admission_scale"], 0)
        self.assertGreater(confirmation_episode, first_episode)
        self.assertEqual(uninterrupted_receipt, restored_receipt)
        self.assertTrue(restored_receipt["promoted"])
        self.assertTrue(
            restored_receipt[
                "confirmation_from_new_reset_bounded_episode"
            ]
        )
        self.assertEqual(
            restored_receipt["confirmation_episode_index"],
            confirmation_episode,
        )
        self.assertEqual(
            restored_receipt["provisional_witness_bank"],
            "ordinary-provisional",
        )
        self.assertEqual(
            restored_receipt["provisional_witness_state_sha256"],
            restored_receipt["pre_consequence_state_sha256"],
        )
        self.assertTrue(
            restored_receipt[
                "provisional_present_at_confirmation_episode_entry"
            ]
        )
        self.assertEqual(learner.checkpoint_bytes(), restored.checkpoint_bytes())

        promoted_state = restored.fingerprint()
        replay = restored.observe(outcome)
        self.assertFalse(replay["learned"])
        self.assertEqual(restored.fingerprint(), promoted_state)

    def test_failed_outcome_admission_is_checkpoint_atomic(self) -> None:
        observation, action, outcome = randomized_symbols(0xFA17, 3)
        profile = CausalProfile(
            acquisition=AcquisitionProfile(energy_limit=1.0e-9)
        )
        learner = CausalEventLearner(profile)
        learner.reset()
        learner.observe(observation, learn=False)
        learner.decide((action,), outcome)
        checkpoint = learner.checkpoint_bytes()

        with self.assertRaises(CapacityError):
            learner.observe(outcome)

        self.assertTrue(learner.pending)
        self.assertEqual(learner.checkpoint_bytes(), checkpoint)

    def test_public_state_snapshot_cannot_bypass_causal_policy(self) -> None:
        observation, action, outcome = randomized_symbols(0x57A7E, 3)
        learner = CausalEventLearner(high_capacity_profile())
        self.assertFalse(hasattr(learner, "apply"))
        self.assertFalse(hasattr(learner, "choose"))
        self.assertFalse(hasattr(learner, "field_learner"))

        learner.reset()
        learner.observe(observation, learn=False)
        learner.decide((action,), outcome)
        pending_checkpoint = learner.checkpoint_bytes()
        exposed_pending = learner.state
        exposed_pending.field.fill_(0.25)
        self.assertEqual(learner.checkpoint_bytes(), pending_checkpoint)

        admission = learner.observe(outcome)
        self.assertTrue(admission["learned"])
        learned_checkpoint = learner.checkpoint_bytes()
        exposed_learned = learner.state
        exposed_learned.field.zero_()
        self.assertEqual(learner.checkpoint_bytes(), learned_checkpoint)

    def test_checkpoint_binds_header_policy_history_and_pending_replay(self) -> None:
        history, observation, action, outcome = randomized_symbols(
            0xC4EC, 4
        )
        profile = high_capacity_profile(policy="always-conditional")
        learner = CausalEventLearner(profile)
        learner.reset()
        learner.observe(history, learn=False)
        learner.observe(observation, learn=False)
        learner.decide((action,), outcome)
        checkpoint = learner.checkpoint_bytes()

        restored = CausalEventLearner.restore(
            checkpoint, expected_profile=profile
        )
        self.assertEqual(restored.eligible_history, history)
        self.assertEqual(restored.current_observation, observation)
        self.assertTrue(restored.pending)
        self.assertEqual(restored.checkpoint_bytes(), checkpoint)
        self.assertEqual(learner.observe(outcome), restored.observe(outcome))
        magic_size = len(_causal._CHECKPOINT_MAGIC)
        header_start = magic_size + 8

        wrong_policy = high_capacity_profile(policy="mismatch-gated")
        with self.assertRaises(CheckpointError):
            CausalEventLearner.restore(
                checkpoint, expected_profile=wrong_policy
            )

        length_start = magic_size
        header_size = struct.unpack(
            ">Q", checkpoint[length_start:header_start]
        )[0]
        header_end = header_start + header_size
        header = json.loads(checkpoint[header_start:header_end])
        header["protocol_context_adaptive"] = True
        encoded_header = json.dumps(
            header,
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        tampered = (
            checkpoint[:length_start]
            + struct.pack(">Q", len(encoded_header))
            + encoded_header
            + checkpoint[header_end:]
        )
        with self.assertRaisesRegex(
            CheckpointError, "header digest mismatch"
        ):
            CausalEventLearner.restore(tampered)

        mismatched_header = json.loads(
            checkpoint[header_start:header_end]
        )
        mismatched_header["profile"]["acquisition"][
            "minimum_score"
        ] = 0.57
        mismatched_header["profile_sha256"] = _causal._sha256(
            _causal._canonical_json(mismatched_header["profile"])
        )
        mismatched_header.pop("header_sha256")
        mismatched_header["header_sha256"] = _causal._sha256(
            _causal._canonical_json(mismatched_header)
        )
        encoded_mismatch = _causal._canonical_json(mismatched_header)
        profile_mismatch = (
            checkpoint[:length_start]
            + struct.pack(">Q", len(encoded_mismatch))
            + encoded_mismatch
            + checkpoint[header_end:]
        )
        with self.assertRaisesRegex(
            CheckpointError,
            "causal and raw-field checkpoint profiles differ",
        ):
            CausalEventLearner.restore(profile_mismatch)

        null_pending_header = json.loads(
            checkpoint[header_start:header_end]
        )
        null_pending_header["context"]["pending"][
            "observation_hex"
        ] = None
        null_pending_header["context_sha256"] = _causal._sha256(
            _causal._canonical_json(null_pending_header["context"])
        )
        null_pending_header.pop("header_sha256")
        null_pending_header["header_sha256"] = _causal._sha256(
            _causal._canonical_json(null_pending_header)
        )
        encoded_null_pending = _causal._canonical_json(
            null_pending_header
        )
        null_pending_checkpoint = (
            checkpoint[:length_start]
            + struct.pack(">Q", len(encoded_null_pending))
            + encoded_null_pending
            + checkpoint[header_end:]
        )
        with self.assertRaisesRegex(
            CheckpointError, "pending observation cannot be null"
        ):
            CausalEventLearner.restore(null_pending_checkpoint)

    def test_action_outcome_pairing_is_causal_not_frequency_replay(self) -> None:
        result = corrupted_pairing_case(101)
        self.assertEqual(result["true_world_accuracy"], 1.0)
        self.assertLess(
            result["corrupted_pairing_accuracy_against_true_world"],
            result["true_world_accuracy"],
        )
        self.assertNotEqual(
            result["true_state_sha256"], result["corrupt_state_sha256"]
        )

    def test_predictive_split_and_fixed_gain_intervention_are_selective(self) -> None:
        result = collision_and_intervention_case(112)
        target = result["target_intervention"]
        receipt = target["receipt"]
        self.assertTrue(result["pre_split_collision"])
        self.assertTrue(result["post_split"]["branch_a_correct"])
        self.assertTrue(result["post_split"]["branch_b_correct"])
        self.assertTrue(target["target_lost"])
        self.assertTrue(target["branch_a_retained"])
        self.assertEqual(
            receipt["removal_basis"],
            "fixed-admission-gain-on-readable-target-scale",
        )
        self.assertGreater(sum(receipt["projection_coefficients"]), 0.0)
        self.assertTrue(result["unrelated_intervention"]["target_retained"])
        self.assertTrue(result["exact_restoration"]["execution_checkpoint_bytes"])

    def test_field_composes_routes_transfers_structure_and_refuses_aliases(self) -> None:
        result = composition_and_transfer_case(101)
        self.assertEqual(len(result["three_step_plan"]["plan_hex"]), 3)
        self.assertEqual(len(result["withheld_reordered_subtask"]["plan_hex"]), 2)
        self.assertEqual(len(result["renamed_entity_transfer"]["plan_hex"]), 2)
        self.assertEqual(
            result["renamed_action_without_grounding"]["status"], "unresolved"
        )

    def test_field_seeks_information_only_when_hidden_state_requires_it(self) -> None:
        result = inquiry_case(101)
        self.assertEqual(
            result["inquiry_decision"]["decision_kind"], "field-supported-inquiry"
        )
        self.assertTrue(result["inquiry_decision"]["field_owned"])
        self.assertTrue(result["post_inquiry_decision"]["field_owned"])
        self.assertTrue(result["goal_completed"])
        self.assertFalse(result["without_inquiry"]["field_owned"])
        self.assertTrue(result["field_state_unchanged_during_execution"])

    def test_continual_memory_survives_correction_restart_and_inference(self) -> None:
        result = continual_restart_capacity_case(101)
        self.assertEqual(
            result["retention_curve"][-1]["relations_retained"],
            result["retention_curve"][-1]["relations_acquired"],
        )
        self.assertEqual(
            result["correction"]["corrected_branch"]["status"], "supported"
        )
        self.assertEqual(
            result["correction"]["original_branch"]["status"], "supported"
        )
        self.assertTrue(result["restart"]["restored_before_outcome_identical"])
        self.assertTrue(result["restart"]["successor_identical"])
        self.assertTrue(result["restart"]["tamper_rejected"])
        self.assertEqual(result["inference_queries"], 256)
        self.assertTrue(result["inference_preserved_state"])
        self.assertTrue(result["capacity"]["rejected"])
        self.assertTrue(result["capacity"]["predecessor_preserved"])
        self.assertTrue(result["snapshot"]["field"]["all_finite"])
        self.assertEqual(result["snapshot"]["qwen_calls"], 0)
        self.assertEqual(result["snapshot"]["teacher_calls"], 0)

    def test_selected_capacity_profile_retains_more_than_narrow_profiles(self) -> None:
        result = capacity_profile_sweep((101, 102, 103))
        by_name = {row["name"]: row for row in result["profiles"]}
        selected = by_name[result["selected_profile"]]
        self.assertEqual(selected["all_steps_seed_count"], 3)
        self.assertEqual(selected["final_exact"], 36)
        self.assertEqual(selected["final_wrong_supported"], 0)
        self.assertGreater(
            selected["final_exact"], by_name["wide-2048-c8"]["final_exact"]
        )
        self.assertGreater(
            selected["all_steps_seed_count"],
            by_name["medium-1024-c4"]["all_steps_seed_count"],
        )

    def test_profile_round_trip_preserves_fixed_geometry(self) -> None:
        profile = high_capacity_profile()
        restored = CausalProfile.from_dict(profile.as_dict())
        self.assertEqual(restored, profile)
        self.assertEqual(restored.fingerprint, profile.fingerprint)
        self.assertEqual(restored.acquisition.wave_width, 4096)
        self.assertEqual(restored.key_channels, 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
