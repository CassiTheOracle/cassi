#!/usr/bin/env python3
"""Behavioral contracts for grounded causal language acquisition."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cassi_causal_language import (
    CausalLanguageError,
    CausalLanguageWorld,
    decode_ordered_expression,
    lexical_command,
    ordered_expression,
    text_packet,
)
from cassi_raw_event_field import encode_packet
from run_cassi_causal_language import (
    ambiguity_clarification_case,
    corruption_case,
    lexical_online_case,
    ordered_language_case,
    restart_intervention_case,
    run,
)


class CausalLanguageBoundaryTests(unittest.TestCase):
    def test_utf8_boundaries_are_strict_bounded_and_ordered(self) -> None:
        forward = ordered_expression("a", "b", "c")
        reverse = ordered_expression("c", "b", "a")
        self.assertNotEqual(forward, reverse)
        self.assertEqual(decode_ordered_expression(forward), ("a", "b", "c"))
        self.assertEqual(decode_ordered_expression(reverse), ("c", "b", "a"))
        with self.assertRaises(CausalLanguageError):
            decode_ordered_expression(encode_packet((b"<a|b|c?",)))
        self.assertEqual(text_packet("é"), text_packet("é"))
        with self.assertRaises(CausalLanguageError):
            text_packet(b"not text")  # type: ignore[arg-type]
        with self.assertRaises(CausalLanguageError):
            text_packet("x" * 9)
        with self.assertRaises(CausalLanguageError):
            lexical_command("é", "a")

    def test_task_goal_does_not_reveal_construction(self) -> None:
        world = CausalLanguageWorld.randomized(301)
        expected_goal = world.task_goal(world.entity_seen)
        self.assertEqual(
            world.consequence(
                world.move_word,
                world.entity_seen,
                world.correct_action(world.move_word),
            ),
            expected_goal,
        )
        self.assertEqual(
            world.consequence(
                world.inspect_word,
                world.entity_seen,
                world.correct_action(world.inspect_word),
            ),
            expected_goal,
        )
        self.assertNotEqual(
            world.command(world.move_word, world.entity_seen),
            world.command(world.inspect_word, world.entity_seen),
        )
        revealed = world.command(world.move_word, world.entity_seen)
        self.assertEqual(
            world.clarification_consequence(
                revealed, world.correct_action(world.move_word)
            ),
            world.ordered_target,
        )
        self.assertEqual(
            world.clarification_consequence(
                revealed, world.correct_action(world.inspect_word)
            ),
            world.ordered_failure,
        )
        ordered_forward = world.ordered_observation(reversed_arguments=False)
        self.assertEqual(
            world.ordered_consequence(
                ordered_forward,
                world.ordered_correct_action(reversed_arguments=False),
            ),
            world.ordered_target,
        )
        self.assertEqual(
            world.ordered_consequence(
                ordered_forward,
                world.ordered_correct_action(reversed_arguments=True),
            ),
            world.ordered_failure,
        )

class CausalLanguageBehaviorTests(unittest.TestCase):
    def test_online_memory_recombination_normalization_and_unknowns(self) -> None:
        case = lexical_online_case(304)
        self.assertTrue(case["true_recombination"]["goal_reached"])
        self.assertEqual(case["paraphrase_transfer"]["supported"], 1)
        self.assertEqual(case["status"], "FAIL")
        self.assertFalse(
            case["capability_checks"]["all_seen_relations_retained"]
        )
        self.assertFalse(
            case["normalization"]["unseen_decomposed"]["decision"]["field_owned"]
        )
        self.assertFalse(case["unknown"]["decision"]["field_owned"])
        self.assertEqual(
            case["unknown"]["world_path"],
            "deterministic-unknown-failure-after-commit",
        )
        self.assertEqual(
            case["unknown"]["consequence_hex"],
            case["unknown"]["expected_consequence_hex"],
        )

    def test_order_ambiguity_restart_corruption_and_receipt(self) -> None:
        ordered = ordered_language_case(302)
        self.assertFalse(
            ordered["held_reverse_before_exposure"]["decision"]["field_owned"]
        )
        ambiguity = ambiguity_clarification_case(302)
        self.assertTrue(ambiguity["restart"]["history_non_null"])
        self.assertTrue(ambiguity["restart"]["continued_byte_exact"])
        self.assertTrue(ambiguity["history_a_continuation"]["followup_correct"])
        self.assertTrue(ambiguity["history_a_continuation"]["goal_reached"])
        self.assertTrue(
            all(
                row["goal_reached"]
                for row in ambiguity["restart"]["continuation"]
            )
        )
        self.assertFalse(
            ambiguity["without_clarification_candidate"]["field_owned"]
        )
        self.assertTrue(
            ambiguity["without_discourse_history_generic_inquiry"]["field_owned"]
        )
        self.assertEqual(
            ambiguity["without_discourse_history_generic_inquiry"]["decision_kind"],
            "field-supported-inquiry",
        )
        corrupted = corruption_case(302)
        self.assertEqual(corrupted["correct_grounding_rate"], 0.0)
        self.assertEqual(corrupted["status"], "EXPECTED_NEGATIVE")
        self.assertTrue(corrupted["measured_failure"])
        restarted = restart_intervention_case(302)
        self.assertTrue(restarted["restart"]["continued_checkpoint_identical"])
        self.assertFalse(
            restarted["removed_construction"]["field_supported_correct"]
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.json"
            receipt = run((303,), output)
            self.assertEqual(receipt["status"], "PASS")
            self.assertTrue(output.is_file())
            self.assertEqual(
                receipt["aggregate"]["metric_buckets"][
                    "commutative_two_component_composition"
                ]["rate"],
                1.0,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
