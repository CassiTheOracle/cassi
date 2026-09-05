from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cassi_discourse_language import (
    DISCOURSE_ABSTAIN_CLARIFICATIONS,
    DISCOURSE_ROUTE_TRAINING_PROMPTS,
    parse_action_clause,
    parse_binding,
    parse_reference_query,
    parse_relation_family,
    select_discourse_frame,
    select_action_alias,
    semantic_frame_target,
)
from cassi_field_agent import CassiFieldAgent
from cassi_field_language import FIELD_LIVE_REGISTER_SIZE


class CassiDiscourseLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config_path = _ROOT / "configs" / "cassi-qi-corpus-language.json"
        cls.checkpoint_path = (
            _ROOT / "artifacts" / "cassi-qi-discourse-language" / "field-state.pt"
        )

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def _open(self, name: str, *, seed: int = 159) -> CassiFieldAgent:
        return CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=self.root / name,
            session_id=name,
            seed=seed,
            device="cpu",
        )


    def test_all_training_prompts_resolve_exact_atomic_frames(self) -> None:
        agent = self._open("frame-development")
        try:
            for route_id, route_prompts in DISCOURSE_ROUTE_TRAINING_PROMPTS.items():
                for prompt in route_prompts:
                    with self.subTest(route=route_id, prompt=prompt):
                        expected = semantic_frame_target(
                            prompt,
                            route_id,
                            clarification=DISCOURSE_ABSTAIN_CLARIFICATIONS.get(
                                prompt
                            ),
                        )
                        decision = select_discourse_frame(
                            agent.controller,
                            agent.engine.law,
                            agent.discourse_codec,
                            agent._route_state,
                            prompt,
                        )
                        self.assertEqual(decision.target, expected)
                        self.assertGreater(
                            min(slot.margin for slot in decision.slots),
                            0.0,
                        )
        finally:
            agent.close()

    def test_parser_covers_generic_binding_reference_action_and_family_forms(self) -> None:
        binding_cases = (
            ("let Aster refer to the red", ("Aster", "reference.red")),
            ("Bramble means blue", ("Bramble", "reference.blue")),
            ("record Cinder as the name for green", ("Cinder", "reference.green")),
            ("from now on use Dune to mean red", ("Dune", "reference.red")),

            (
                "associate the name Ember with the blue object",
                ("Ember", "reference.blue"),
            ),
            ("make Fable refer to green", ("Fable", "reference.green")),
            ("correct the reference: Grove means red", ("Grove", "reference.red")),
            (
                "revise the name binding so Hallow denotes blue",
                ("Hallow", "reference.blue"),
            ),
            (
                "update the association and use Indigo for green",
                ("Indigo", "reference.green"),
            ),
            (
                "replace the old reference for Jade with red",
                ("Jade", "reference.red"),
            ),
        )
        for text, expected in binding_cases:
            with self.subTest(kind="binding", text=text):
                self.assertEqual(parse_binding(text), expected)

        reference_cases = (
            ("place Kite horizontally against Linden", ("Kite", "Linden")),
            ("resolve the relation from Morrow to Nacre", ("Morrow", "Nacre")),
            (
                "which side is Oxbow compared with Pollen",
                ("Oxbow", "Pollen"),
            ),
            ("settle the question involving Quartz and Rowan", ("Quartz", "Rowan")),
            (
                "measure the separation of Saffron from Thistle",
                ("Saffron", "Thistle"),
            ),
            ("Umber versus Vale", ("Umber", "Vale")),
            ("how far is Willow from Xylo", ("Willow", "Xylo")),
            ("compare Yarrow and Zephyr", ("Yarrow", "Zephyr")),
        )
        for text, expected in reference_cases:
            with self.subTest(kind="reference", text=text):
                self.assertEqual(parse_reference_query(text), expected)

        action_cases = (
            ("turn leftward", "action.gaze-left"),
            ("look rightward", "action.gaze-right"),
            ("move upward", "action.gaze-up"),
            ("look downward", "action.gaze-down"),
            ("remain still", "action.hold"),
            ("make no gaze movement", "action.hold"),
            ("use the current gaze position", "action.hold"),
            ("forecast holding the gaze", "action.hold"),
            ("state the no-movement outcome", "action.hold"),
        )
        for text, expected in action_cases:
            with self.subTest(kind="action", text=text):
                self.assertEqual(parse_action_clause(text), expected)

        family_cases = (
            ("which side is left", "horizontal"),
            ("is the object at the top", "vertical"),
            ("measure the separation", "distance"),
        )
        for text, expected in family_cases:
            with self.subTest(kind="family", text=text):
                self.assertEqual(parse_relation_family(text), expected)

    def test_frame_training_respects_minimum_history_scale(self) -> None:

        agent = self._open("frame-history")
        try:
            law = agent.engine.law
            memory_before = law._coordinates(agent.state)[0].clone()
            learned = law.learn_sequence(
                agent.state,
                (247, 246, 245, 244, 243, 242),
                minimum_history=32,
            )
            memory_after = law._coordinates(learned)[0]
            self.assertTrue(
                (memory_after[0] == memory_before[0]).all().item()
            )
            self.assertTrue(
                any(
                    (memory_after[scale] != memory_before[scale]).any().item()
                    for scale in range(1, law.config.scale_count)
                )
            )
            with self.assertRaisesRegex(
                Exception,
                "minimum trajectory history",
            ):
                law.learn_sequence(agent.state, (1, 2), minimum_history=-1)
        finally:
            agent.close()

    def test_consecutive_bindings_keep_frame_reference_slots_independent(self) -> None:
        agent = self._open("consecutive-bindings")
        try:
            first = agent.turn("use Juniper to mean red")
            self.assertFalse(first.abstained, first.receipt_dict())
            self.assertEqual(first.reference, "reference.red")
            static_frame = select_discourse_frame(
                agent.controller,
                agent.engine.law,
                agent.discourse_codec,
                agent._route_state,
                "make Kestrel refer to blue",
            )
            current_frame = select_discourse_frame(
                agent.controller,
                agent.engine.law,
                agent.discourse_codec,
                agent.state,
                "make Kestrel refer to blue",
            )
            self.assertEqual(
                static_frame.target.binding_reference,
                "reference.blue",
                {
                    "static": static_frame.receipt_dict(),
                    "current": current_frame.receipt_dict(),
                },
            )
            second = agent.turn("make Kestrel refer to blue")
            self.assertFalse(second.abstained, second.receipt_dict())
            self.assertEqual(
                second.reference,
                "reference.blue",
                second.receipt_dict(),
            )
            static_frame = select_discourse_frame(
                agent.controller,
                agent.engine.law,
                agent.discourse_codec,
                agent._route_state,
                "use Lumen to mean green",
            )
            current_frame = select_discourse_frame(
                agent.controller,
                agent.engine.law,
                agent.discourse_codec,
                agent.state,
                "use Lumen to mean green",
            )
            self.assertEqual(
                static_frame.target.binding_reference,
                "reference.green",
                {
                    "static": static_frame.receipt_dict(),
                    "current": current_frame.receipt_dict(),
                },
            )
            third = agent.turn("use Lumen to mean green")
            self.assertFalse(third.abstained, third.receipt_dict())
            self.assertEqual(third.reference, "reference.green", third.receipt_dict())
        finally:
            agent.close()


    def test_raw_prediction_uses_fixed_slots_after_field_route(self) -> None:
        agent = self._open("raw-fixed-slot")
        try:
            memory_before = agent.engine.law.memory_sha256(agent.state)
            world_before = agent.world.snapshot()["snapshot_sha256"]
            for prompt, expected_action in (
                ("without moving forecast a left view", "action.gaze-left"),
                (
                    "predict what follows if the gaze is directed up",
                    "action.gaze-up",
                ),
            ):
                with self.subTest(prompt=prompt):
                    result = agent.turn(prompt)
                    self.assertFalse(result.abstained)
                    self.assertEqual(result.route_id, "route.prediction")
                    self.assertEqual(result.action, expected_action)
                    self.assertEqual(result.memory_after_sha256, memory_before)
                    self.assertEqual(result.world_after_sha256, world_before)
            action_frame = select_discourse_frame(
                agent.controller,
                agent.engine.law,
                agent.discourse_codec,
                agent._route_state,
                "move your looking direction up",
            )
            self.assertEqual(action_frame.target.route_id, "route.action")
            self.assertEqual(action_frame.target.action_id, "action.gaze-up")
            explanation_frame = select_discourse_frame(
                agent.controller,
                agent.engine.law,
                agent.discourse_codec,
                agent._route_state,
                "state the change just observed",
            )
            self.assertEqual(
                explanation_frame.target.route_id,
                "route.explanation",
            )
            frame = select_discourse_frame(
                agent.controller,
                agent.engine.law,
                agent.discourse_codec,
                agent._route_state,
                "resolve the distance relation from it to red",
            )
            self.assertEqual(frame.target.route_id, "route.reference")
            self.assertEqual(frame.target.family_id, "distance")
            self.assertEqual(frame.target.subject_slot, "surface.active")
            self.assertEqual(frame.target.comparison_slot, "surface.red")
        finally:
            agent.close()
    def test_structural_ambiguities_abstain_with_typed_reasons(self) -> None:
        agent = self._open("structural-ambiguities")
        cases = (
            ("shift your gaze left or right", "ambiguous_action"),
            (
                "settle the relation between red and blue",
                "ambiguous_relation_family",
            ),
            (
                "which state came first after the gaze was held still",
                "temporal_states_indistinguishable",
            ),
            ("compare the unnamed object with blue", "missing_referent"),
            ("is it near blue", "missing_active_referent"),
        )
        try:
            for prompt, expected_reason in cases:
                with self.subTest(prompt=prompt):
                    result = agent.turn(prompt)
                    self.assertTrue(result.abstained)
                    self.assertEqual(result.reason, expected_reason)
        finally:
            agent.close()


    def test_missing_active_reference_is_route_independent(self) -> None:
        agent = self._open("missing-active-postmortem")
        try:
            for statement in (
                "use Juniper to mean red",
                "make Kestrel refer to blue",
                "use Lumen to mean green",
                "record Nix as the name for red",
                "make Opal refer to blue",
                "record Quill as the name for green",
            ):
                self.assertFalse(agent.turn(statement).abstained)
            state_before = agent.state.field.detach().clone()
            memory_before = agent.engine.law.memory_sha256(agent.state)
            world_before = agent.world.snapshot()["snapshot_sha256"]

            result = agent.turn("is it near blue")

            self.assertTrue(result.abstained)
            self.assertEqual(result.reason, "missing_active_referent")
            self.assertTrue(agent.state.field.equal(state_before))
            self.assertEqual(agent.engine.law.memory_sha256(agent.state), memory_before)
            self.assertEqual(
                agent.world.snapshot()["snapshot_sha256"],
                world_before,
            )
        finally:
            agent.close()

    def test_exact_retirement_preserves_other_memory_and_all_live_registers(self) -> None:
        agent = self._open("exact-retirement")
        try:
            law = agent.engine.law
            target = agent.codec.reference_episode_symbols(
                "Aster", "subject", "reference.red"
            )
            other = agent.codec.reference_episode_symbols(
                "Bramble", "subject", "reference.blue"
            )
            state = law.learn_sequence(agent.state, target)
            state = law.learn_sequence(state, other)
            registers = tuple(
                (index + 1) / (FIELD_LIVE_REGISTER_SIZE + 1)
                for index in range(FIELD_LIVE_REGISTER_SIZE)
            )
            state = law.write_live_boundary_values(state, registers)
            before_count = law.memory_event_count(state)
            before_other_accuracy = law.sequence_accuracy(state, other)

            retired, removed = law.forget_exact_sequences(state, (target,))
            self.assertEqual(removed, len(target))
            self.assertEqual(
                law.memory_event_count(retired),
                before_count - len(target),
            )
            self.assertEqual(law.sequence_accuracy(retired, other), before_other_accuracy)
            restored_registers = law.read_live_boundary_values(
                retired, FIELD_LIVE_REGISTER_SIZE
            )
            for actual, expected in zip(restored_registers, registers, strict=True):
                self.assertAlmostEqual(actual, expected, places=6)

            unchanged, removed_again = law.forget_exact_sequences(retired, (target,))
            self.assertEqual(removed_again, 0)
            self.assertEqual(law.memory_sha256(unchanged), law.memory_sha256(retired))
            unchanged_registers = law.read_live_boundary_values(
                unchanged, FIELD_LIVE_REGISTER_SIZE
            )
            for actual, expected in zip(unchanged_registers, registers, strict=True):
                self.assertAlmostEqual(actual, expected, places=6)
        finally:
            agent.close()

    def test_learning_reuses_a_forgotten_episode_span(self) -> None:
        agent = self._open("episode-span-reuse")
        try:
            law = agent.engine.law
            episode_length = (law.width - 3) // 2
            episodes = tuple(
                (20 + index,) * episode_length
                for index in range(2 * law.config.scale_count)
            )
            state = law.initial_state(device="cpu")
            for episode in episodes:
                state = law.learn_sequence(state, episode)
            full_count = law.memory_event_count(state)

            retired, removed = law.forget_exact_sequences(state, (episodes[0],))
            self.assertEqual(removed, episode_length)
            replacement = (200,) * episode_length
            restored = law.learn_sequence(retired, replacement)

            self.assertEqual(law.memory_event_count(restored), full_count)
            self.assertEqual(
                law.sequence_accuracy(restored, replacement),
                (episode_length - 1, episode_length - 1),
            )
        finally:
            agent.close()

    def test_deferred_goal_order_survives_session_roundtrip(self) -> None:
        state_dir = self.root / "deferred-goal"
        session_id = "deferred-goal"
        declaration_text = DISCOURSE_ROUTE_TRAINING_PROMPTS["route.goal-declaration"][0]
        expected_actions = (
            "action.gaze-up",
            "action.gaze-right",
            "action.gaze-down",
        )
        first = CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=state_dir,
            session_id=session_id,
            seed=802,
            device="cpu",
        )
        try:
            declaration = first.turn(declaration_text)
            declaration_receipt = declaration.receipt_dict()
            self.assertEqual(declaration_receipt["route_id"], "route.goal-declaration")
            self.assertEqual(
                tuple(declaration_receipt["goal"]["actions"]), expected_actions
            )
            self.assertEqual(declaration_receipt["goal"]["status"], "stored")
            self.assertTrue(declaration_receipt["effective_consolidate"])
            self.assertEqual(first.step_count, 0)
        finally:
            first.close()

        reopened = CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=state_dir,
            session_id=session_id,
            seed=802,
            device="cpu",
        )
        try:
            self.assertEqual(
                reopened.engine.law.memory_sha256(reopened.state),
                declaration_receipt["memory_after_sha256"],
            )
            trigger = reopened.turn(
                DISCOURSE_ROUTE_TRAINING_PROMPTS["route.goal-trigger"][0]
            )
            receipt = trigger.receipt_dict()
            self.assertEqual(receipt["route_id"], "route.goal-trigger")
            self.assertEqual(tuple(receipt["goal"]["actions"]), expected_actions)
            self.assertEqual(receipt["goal"]["status"], "completed")
            self.assertEqual(receipt["goal"]["step_count"], 3)
            self.assertEqual(reopened.step_count, 3)
            self.assertFalse(receipt["effective_consolidate"])
        finally:
            reopened.close()


    def test_action_alias_binding_survives_session_roundtrip(self) -> None:
        state_dir = self.root / "action-alias"
        session_id = "action-alias"
        first = CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=state_dir,
            session_id=session_id,
            seed=811,
            device="cpu",
        )
        try:
            world_before = first.world.snapshot()["snapshot_sha256"]
            correction = first.turn("starboard means look right")
            self.assertFalse(correction.abstained, correction.receipt_dict())
            self.assertEqual(
                correction.route_id,
                "route.action-alias-binding",
            )
            self.assertEqual(correction.action, "action.gaze-right")
            self.assertTrue(correction.effective_consolidate)
            self.assertEqual(correction.world_after_sha256, world_before)
            correction_memory = correction.memory_after_sha256
        finally:
            first.close()

        reopened = CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=state_dir,
            session_id=session_id,
            seed=811,
            device="cpu",
        )
        try:
            self.assertEqual(
                reopened.engine.law.memory_sha256(reopened.state),
                correction_memory,
            )
            self.assertIsNone(
                select_action_alias(
                    reopened.engine.law,
                    reopened.discourse_codec,
                    reopened.state,
                    "look comet",
                )
            )
            self.assertIsNone(
                select_action_alias(
                    reopened.engine.law,
                    reopened.discourse_codec,
                    reopened.state,
                    (
                        "which state came first or second. "
                        "State A=tick=0;x=+0.0;y=+0.0; "
                        "State B=tick=1;x=-0.08;y=+0.0."
                    ),
                )
            )
            action = reopened.turn("look starboard")
            self.assertFalse(action.abstained, action.receipt_dict())
            self.assertEqual(action.route_id, "route.action")
            self.assertEqual(action.action, "action.gaze-right")
            alias_receipt = action.semantic_frame["online_action_alias"]
            self.assertEqual(alias_receipt["alias"], "starboard")
            self.assertEqual(
                alias_receipt["cue_correct"],
                alias_receipt["cue_total"],
            )
            self.assertEqual(alias_receipt["cue_accuracy"], 1.0)
            replacement = reopened.turn("starboard means look left")
            self.assertFalse(replacement.abstained, replacement.receipt_dict())
            self.assertEqual(
                replacement.route_id,
                "route.action-alias-binding",
            )
            self.assertEqual(replacement.action, "action.gaze-left")
            self.assertGreater(
                replacement.detail["operation"]["retired_event_count"],
                0,
            )
            replacement_memory = replacement.memory_after_sha256
        finally:
            reopened.close()

        corrected = CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=state_dir,
            session_id=session_id,
            seed=811,
            device="cpu",
        )
        try:
            self.assertEqual(
                corrected.engine.law.memory_sha256(corrected.state),
                replacement_memory,
            )
            action = corrected.turn("look starboard")
            self.assertFalse(action.abstained, action.receipt_dict())
            self.assertEqual(action.action, "action.gaze-left")
        finally:
            corrected.close()


if __name__ == "__main__":
    unittest.main()
