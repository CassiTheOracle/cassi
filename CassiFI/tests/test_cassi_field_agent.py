from __future__ import annotations

import json
import math
import struct
import tempfile
import unittest
from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
for _path in (
    _CASSI_FI_ROOT,
    _CASSI_FI_ROOT / "training",
    _CASSI_FI_ROOT / "verification",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
from unittest import mock

from cassi_field_agent import CassiFieldAgent, CassiFieldAgentError
from cassi_field_language import qi_state_sha256
from cassi_grounded_language import (
    CassiGroundedEventCodec,
    CassiGroundedLanguageError,
    GROUND_ACTIONS,
    GROUND_CAUSE_QUESTION,
    GROUND_HELDOUT_UTTERANCES,
    GROUND_OBSERVED_CHANGE_QUESTION,
    GROUND_PREDICTION_HELDOUT_QUESTION,
    GROUND_TIME_HELDOUT_QUESTIONS,
    GROUND_REFERENCE_HELDOUT_QUESTIONS,
    GROUND_SPATIAL_HELDOUT_QUESTIONS,
    commit_grounded_action,
    decode_colored_objects,
    observe_colored_objects,
    observe_proprioception,
    read_active_reference,
    select_grounded_action,
    select_grounded_reference,
    select_spatial_relation,
    sense_grounded_symbols,
    sense_reference_cue,
    sense_spatial_query,
    set_active_reference,
)
from cassi_temporal_language import (
    commit_temporal_decision,
    select_cause,
    select_observed_change,
    select_order_position,
    select_predicted_change,
    select_time_target,
    sense_order_question,
    sense_prediction_prompt,
    sense_temporal_prompt,
    write_transition_register,
)
from train_cassi_field_language import train_corpus
from train_cassi_grounded_language import train_grounded_language
from train_cassi_spatial_language import train_spatial_language
from train_cassi_reference_language import train_reference_language
from train_cassi_temporal_language import train_temporal_language

ROOT = _CASSI_FI_ROOT


class CassiFieldAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.config_path = ROOT / "configs" / "cassi-qi-corpus-language.json"
        corpus = cls.root / "surface.txt"
        corpus.write_text(
            "The small field watches the quiet world.\n"
            "Light moves left and right across the room.\n"
            "A careful observer looks up and down.\n"
            "The agent remains still until instructed.\n"
            "The world changes after every action.\n"
            "Language and consequence share one field.\n"
            "The small field watches the quiet world.\n"
            "Light moves left and right across the room.\n",
            encoding="utf-8",
        )
        base_dir = cls.root / "base"
        train_corpus(
            corpus,
            cls.config_path,
            base_dir,
            holdout_bytes=64,
            episodes_per_source=4,
            heldout_episodes_per_source=1,
            max_episode_bytes=80,
        )
        cls.grounded_dir = cls.root / "grounded"
        cls.training_receipt = train_grounded_language(
            config_path=cls.config_path,
            base_checkpoint_path=base_dir / "field-state.pt",
            output_dir=cls.grounded_dir,
        )
        cls.spatial_dir = cls.root / "spatial"
        cls.spatial_receipt = train_spatial_language(
            config_path=cls.config_path,
            base_checkpoint_path=cls.grounded_dir / "field-state.pt",
            output_dir=cls.spatial_dir,
        )
        cls.reference_dir = cls.root / "reference"
        cls.reference_receipt = train_reference_language(
            config_path=cls.config_path,
            base_checkpoint_path=cls.spatial_dir / "field-state.pt",
            output_dir=cls.reference_dir,
        )
        cls.temporal_dir = cls.root / "temporal"
        cls.temporal_receipt = train_temporal_language(
            config_path=cls.config_path,
            base_checkpoint_path=cls.reference_dir / "field-state.pt",
            output_dir=cls.temporal_dir,
        )
        cls.checkpoint_path = cls.temporal_dir / "field-state.pt"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def _open(
        self,
        name: str,
        *,
        seed: int,
    ) -> CassiFieldAgent:
        return CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=self.root / name,
            session_id=name,
            seed=seed,
        )

    @staticmethod
    def _world_position(agent: CassiFieldAgent) -> tuple[float, float]:
        x, y = struct.unpack("<ff", observe_proprioception(agent.world))
        return float(x), float(y)

    def test_typed_boundary_preserves_ordered_world_bytes(self) -> None:
        codec = CassiGroundedEventCodec()
        observation = bytes(range(8))
        symbols = codec.instruction_symbols(observation, "look left")
        self.assertEqual(symbols[0], codec.text.system_symbol)
        self.assertIn(tuple(observation), tuple(symbols[index : index + 8] for index in range(len(symbols) - 7)))
        self.assertEqual(symbols[-1], codec.text.assistant_symbol)
        self.assertNotEqual(
            codec.action_symbols("action.gaze-left"),
            codec.action_symbols("action.gaze-right"),
        )
        world = self._open("typed-objects", seed=101)
        try:
            object_observation = observe_colored_objects(world.world)
            self.assertEqual(
                decode_colored_objects(object_observation),
                (("red", 1, 4), ("blue", 3, 3), ("green", 1, 4)),
            )
            spatial_symbols = codec.spatial_query_symbols(
                object_observation,
                GROUND_SPATIAL_HELDOUT_QUESTIONS["horizontal"],
            )
            self.assertIn(
                tuple(object_observation),
                tuple(
                    spatial_symbols[index : index + len(object_observation)]
                    for index in range(len(spatial_symbols) - len(object_observation) + 1)
                ),
            )
            self.assertNotEqual(
                codec.relation_symbols("relation.left"),
                codec.relation_symbols("relation.right"),
            )
        finally:
            world.close()


    def test_curriculum_transfers_all_heldout_compositions(self) -> None:
        heldout = self.training_receipt["heldout"]
        self.assertEqual(heldout["correct"], len(GROUND_ACTIONS))
        self.assertEqual(heldout["accuracy"], 1.0)
        self.assertEqual(heldout["successor_accuracy"], 1.0)
        self.assertEqual(heldout["shuffled_accuracy"], 0.0)
        self.assertGreater(heldout["minimum_margin"], 0.1)
        self.assertTrue(all(row["memory_unchanged"] for row in heldout["episodes"]))

    def test_spatial_curriculum_transfers_and_follows_layout(self) -> None:
        heldout = self.spatial_receipt["heldout"]
        self.assertEqual(heldout["correct"], 6)
        self.assertEqual(heldout["accuracy"], 1.0)
        self.assertEqual(heldout["substituted_layout_accuracy"], 1.0)
        self.assertEqual(heldout["substituted_original_label_accuracy"], 0.0)
        self.assertTrue(all(row["answers_reverse"] for row in heldout["reversals"]))
        self.assertTrue(all(row["memory_unchanged"] for row in heldout["episodes"]))
        self.assertEqual(self.spatial_receipt["action_retention"]["accuracy"], 1.0)

    def test_spatial_answers_reverse_with_world_state(self) -> None:
        expected = {
            101: {
                "horizontal": "relation.left",
                "vertical": "relation.above",
                "distance": "relation.far",
            },
            159: {
                "horizontal": "relation.right",
                "vertical": "relation.below",
                "distance": "relation.near",
            },
        }
        for seed, relations in expected.items():
            agent = self._open(f"spatial-{seed}", seed=seed)
            try:
                world_sha256 = agent.world.snapshot()["snapshot_sha256"]
                for family, relation_id in relations.items():
                    query = agent.query(GROUND_SPATIAL_HELDOUT_QUESTIONS[family])
                    self.assertEqual(query.family_id, family)
                    self.assertEqual(query.relation_id, relation_id)
                    self.assertEqual(
                        query.memory_before_sha256,
                        query.memory_after_sha256,
                    )
                    self.assertEqual(
                        agent.world.snapshot()["snapshot_sha256"],
                        world_sha256,
                    )
                self.assertEqual(agent.query_count, 3)
                self.assertEqual(agent.step_count, 0)
            finally:
                agent.close()

    def test_agent_executes_every_heldout_instruction(self) -> None:
        expected_positions = {
            "action.gaze-left": (-0.08, 0.0),
            "action.gaze-right": (0.08, 0.0),
            "action.gaze-up": (0.0, 0.08),
            "action.gaze-down": (0.0, -0.08),
            "action.hold": (0.0, 0.0),
        }
        for index, action_id in enumerate(GROUND_ACTIONS):
            with self.subTest(action_id=action_id):
                agent = self._open(f"heldout-{index}", seed=101 + index)
                try:
                    step = agent.step(
                        GROUND_HELDOUT_UTTERANCES[action_id],
                        consolidate=False,
                    )
                    self.assertEqual(step.action_id, action_id)
                    self.assertEqual(
                        step.memory_before_sha256,
                        step.memory_after_sha256,
                    )
                    self.assertFalse(step.consolidated)
                    self.assertEqual(
                        step.acknowledgment_status,
                        "hold" if action_id == "action.hold" else "applied",
                    )
                    expected_x, expected_y = expected_positions[action_id]
                    actual_x, actual_y = self._world_position(agent)
                    self.assertAlmostEqual(actual_x, expected_x, places=6)
                    self.assertAlmostEqual(actual_y, expected_y, places=6)
                finally:
                    agent.close()

    def test_session_round_trip_preserves_field_world_and_next_turn(self) -> None:
        state_dir = self.root / "roundtrip"
        first = CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=state_dir,
            session_id="roundtrip",
            seed=301,
        )
        first_step = first.step("turn your gaze left", consolidate=False)
        field_sha256 = qi_state_sha256(first.controller, first.state)
        world_sha256 = first.world.snapshot()["snapshot_sha256"]
        first.close()

        reopened = CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=state_dir,
            session_id="roundtrip",
            seed=301,
        )
        try:
            self.assertEqual(qi_state_sha256(reopened.controller, reopened.state), field_sha256)
            self.assertEqual(reopened.world.snapshot()["snapshot_sha256"], world_sha256)
            self.assertEqual(reopened.step_count, 1)
            self.assertAlmostEqual(self._world_position(reopened)[0], -0.08, places=6)
            second_step = reopened.step("turn your gaze right", consolidate=False)
            self.assertEqual(second_step.action_id, "action.gaze-right")
            self.assertEqual(second_step.tick, 2)
            self.assertAlmostEqual(self._world_position(reopened)[0], 0.0, places=6)
            self.assertEqual(first_step.memory_after_sha256, second_step.memory_after_sha256)
        finally:
            reopened.close()

    def test_spatial_query_round_trip_preserves_field_world_and_next_answer(self) -> None:
        state_dir = self.root / "spatial-roundtrip"
        first = CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=state_dir,
            session_id="spatial-roundtrip",
            seed=101,
        )
        first_query = first.query(GROUND_SPATIAL_HELDOUT_QUESTIONS["horizontal"])
        self.assertEqual(first_query.relation_id, "relation.left")
        field_sha256 = qi_state_sha256(first.controller, first.state)
        world_sha256 = first.world.snapshot()["snapshot_sha256"]
        memory_sha256 = first_query.memory_after_sha256
        first.close()

        reopened = CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=state_dir,
            session_id="spatial-roundtrip",
            seed=101,
        )
        try:
            self.assertEqual(
                qi_state_sha256(reopened.controller, reopened.state),
                field_sha256,
            )
            self.assertEqual(reopened.world.snapshot()["snapshot_sha256"], world_sha256)
            self.assertEqual(reopened.query_count, 1)
            self.assertEqual(reopened.step_count, 0)
            second_query = reopened.query(
                GROUND_SPATIAL_HELDOUT_QUESTIONS["vertical"]
            )
            self.assertEqual(second_query.relation_id, "relation.above")
            self.assertEqual(second_query.memory_after_sha256, memory_sha256)
            self.assertEqual(reopened.query_count, 2)
        finally:
            reopened.close()

    def test_reference_curriculum_holds_out_names_and_fails_unknown_closed(self) -> None:
        self.assertEqual(self.reference_receipt["binding"]["accuracy"], 1.0)
        self.assertTrue(
            self.reference_receipt["binding"]["unknown_name_failed_closed"]
        )
        self.assertEqual(self.reference_receipt["literal_reference"]["accuracy"], 1.0)
        self.assertEqual(self.reference_receipt["relation_family"]["accuracy"], 1.0)
        self.assertEqual(self.reference_receipt["action_retention"]["accuracy"], 1.0)
        self.assertEqual(self.reference_receipt["spatial_retention"]["accuracy"], 1.0)

        agent = self._open("unknown-reference", seed=159)
        try:
            with self.assertRaisesRegex(
                CassiFieldAgentError,
                "reference port did not resolve",
            ):
                agent.query_reference(
                    "Quill",
                    "blue",
                    GROUND_REFERENCE_HELDOUT_QUESTIONS["distance"],
                )
        finally:
            agent.close()

    def test_unseen_names_and_pronouns_follow_active_referent(self) -> None:
        agent = self._open("reference-transfer", seed=159)
        try:
            memory_before = agent.engine.law.memory_sha256(agent.state)
            mira = agent.bind_reference("Mira", "let Mira refer to red")
            self.assertEqual(mira.reference_id, "reference.red")
            self.assertNotEqual(mira.memory_after_sha256, memory_before)
            orin = agent.bind_reference("Orin", "let Orin refer to green")
            self.assertEqual(orin.reference_id, "reference.green")
            self.assertEqual(agent.binding_count, 2)

            mira_query = agent.query_reference(
                "Mira",
                "blue",
                GROUND_REFERENCE_HELDOUT_QUESTIONS["distance"],
            )
            self.assertEqual(mira_query.subject_reference, "reference.red")
            self.assertEqual(mira_query.relation_id, "relation.near")
            self.assertEqual(
                mira_query.memory_before_sha256,
                mira_query.memory_after_sha256,
            )
            mira_pronoun = agent.query_reference(
                "it",
                "blue",
                GROUND_REFERENCE_HELDOUT_QUESTIONS["distance"],
            )
            self.assertTrue(mira_pronoun.subject_used_active_register)
            self.assertEqual(mira_pronoun.subject_reference, "reference.red")
            self.assertEqual(mira_pronoun.relation_id, "relation.near")

            orin_query = agent.query_reference(
                "Orin",
                "blue",
                GROUND_REFERENCE_HELDOUT_QUESTIONS["distance"],
            )
            self.assertEqual(orin_query.subject_reference, "reference.green")
            self.assertEqual(orin_query.relation_id, "relation.far")
            orin_pronoun = agent.query_reference(
                "it",
                "blue",
                GROUND_REFERENCE_HELDOUT_QUESTIONS["distance"],
            )
            self.assertEqual(orin_pronoun.subject_reference, "reference.green")
            self.assertEqual(orin_pronoun.relation_id, "relation.far")
            self.assertEqual(
                read_active_reference(agent.engine.law, agent.state),
                "reference.green",
            )
        finally:
            agent.close()

    def test_active_referent_counterfactual_changes_pronoun_without_memory(self) -> None:
        agent = self._open("reference-counterfactual", seed=159)
        try:
            memory_sha256 = agent.engine.law.memory_sha256(agent.state)
            decisions = {}
            for reference_id in ("reference.red", "reference.green"):
                state = set_active_reference(
                    agent.engine.law,
                    agent.state,
                    reference_id,
                )
                cue = sense_reference_cue(
                    agent.engine.law,
                    state,
                    agent.codec,
                    "it",
                    "subject",
                )
                decision = select_grounded_reference(
                    agent.controller,
                    agent.engine.law,
                    agent.codec,
                    cue,
                    use_active_register=True,
                )
                decisions[reference_id] = decision.reference_id
                self.assertEqual(agent.engine.law.memory_sha256(cue), memory_sha256)
            self.assertEqual(
                decisions,
                {
                    "reference.red": "reference.red",
                    "reference.green": "reference.green",
                },
            )
        finally:
            agent.close()

    def test_reference_binding_and_pronoun_persist_without_metadata_map(self) -> None:
        state_dir = self.root / "reference-roundtrip"
        first = CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=state_dir,
            session_id="reference-roundtrip",
            seed=159,
        )
        first.bind_reference("Mira", "let Mira refer to red")
        first.bind_reference("Orin", "let Orin refer to green")
        first.query_reference(
            "Orin",
            "blue",
            GROUND_REFERENCE_HELDOUT_QUESTIONS["distance"],
        )
        state_sha256 = qi_state_sha256(first.controller, first.state)
        memory_sha256 = first.engine.law.memory_sha256(first.state)
        world_sha256 = first.world.snapshot()["snapshot_sha256"]
        loaded = first.store.load("reference-roundtrip")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        metadata = loaded[1]
        self.assertEqual(
            set(metadata),
            {
                "binding_count",
                "boundary_fingerprint",
                "query_count",
                "schema",
                "step_count",
                "world_snapshot",
            },
        )
        metadata_text = json.dumps(metadata, sort_keys=True)
        self.assertNotIn("Mira", metadata_text)
        self.assertNotIn("Orin", metadata_text)
        first.close()

        reopened = CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=state_dir,
            session_id="reference-roundtrip",
            seed=159,
        )
        try:
            self.assertEqual(
                qi_state_sha256(reopened.controller, reopened.state),
                state_sha256,
            )
            self.assertEqual(
                reopened.engine.law.memory_sha256(reopened.state),
                memory_sha256,
            )
            self.assertEqual(reopened.world.snapshot()["snapshot_sha256"], world_sha256)
            self.assertEqual(reopened.binding_count, 2)
            self.assertEqual(
                reopened.query_reference(
                    "Orin",
                    "blue",
                    GROUND_REFERENCE_HELDOUT_QUESTIONS["distance"],
                ).relation_id,
                "relation.far",
            )
            self.assertEqual(
                reopened.query_reference(
                    "it",
                    "blue",
                    GROUND_REFERENCE_HELDOUT_QUESTIONS["distance"],
                ).relation_id,
                "relation.far",
            )
        finally:
            reopened.close()

    def test_delayed_consolidation_updates_and_persists_memory(self) -> None:
        state_dir = self.root / "consolidated"
        agent = CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=state_dir,
            session_id="consolidated",
            seed=401,
        )
        step = agent.step("turn your gaze left", consolidate=True)
        memory_sha256 = step.memory_after_sha256
        self.assertTrue(step.consolidated)
        self.assertIsNotNone(step.consolidation_residual)
        self.assertNotEqual(step.memory_before_sha256, memory_sha256)
        agent.close()

        reopened = CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=state_dir,
            session_id="consolidated",
            seed=401,
        )
        try:
            self.assertEqual(reopened.engine.law.memory_sha256(reopened.state), memory_sha256)
            self.assertEqual(reopened.step_count, 1)
        finally:
            reopened.close()

    def test_live_phase_intervention_can_change_action_without_memory_change(self) -> None:
        agent = self._open("phase-intervention", seed=501)
        try:
            observation = observe_proprioception(agent.world)
            cue = sense_grounded_symbols(
                agent.engine.law,
                agent.state,
                agent.codec.instruction_symbols(observation, "turn your gaze left"),
            )
            live = select_grounded_action(
                agent.controller,
                agent.engine.law,
                agent.codec,
                cue,
            )
            memory_sha256 = agent.engine.law.memory_sha256(cue)
            changed = False
            for angle in (math.pi / 2.0, math.pi, 3.0 * math.pi / 2.0):
                rotated = agent.engine.law.rotate_live_context(cue, angle)
                self.assertEqual(agent.engine.law.memory_sha256(rotated), memory_sha256)
                try:
                    counterfactual = select_grounded_action(
                        agent.controller,
                        agent.engine.law,
                        agent.codec,
                        rotated,
                    )
                except CassiGroundedLanguageError:
                    changed = True
                    break
                changed = changed or counterfactual.action_id != live.action_id
            self.assertTrue(changed)
        finally:
            agent.close()

    def test_live_phase_intervention_can_change_spatial_answer(self) -> None:
        agent = self._open("spatial-phase-intervention", seed=101)
        try:
            object_observation = observe_colored_objects(agent.world)
            cue = sense_spatial_query(
                agent.engine.law,
                agent.state,
                agent.codec,
                object_observation,
                GROUND_SPATIAL_HELDOUT_QUESTIONS["horizontal"],
            )
            live = select_spatial_relation(
                agent.controller,
                agent.engine.law,
                agent.codec,
                cue,
            )
            self.assertEqual(live.relation_id, "relation.left")
            memory_sha256 = agent.engine.law.memory_sha256(cue)
            changed = False
            for angle in (math.pi / 2.0, math.pi, 3.0 * math.pi / 2.0):
                rotated = agent.engine.law.rotate_live_context(cue, angle)
                self.assertEqual(agent.engine.law.memory_sha256(rotated), memory_sha256)
                try:
                    counterfactual = select_spatial_relation(
                        agent.controller,
                        agent.engine.law,
                        agent.codec,
                        rotated,
                    )
                except CassiGroundedLanguageError:
                    changed = True
                    break
                changed = changed or counterfactual.relation_id != live.relation_id
            self.assertTrue(changed)
        finally:
            agent.close()

    def test_temporal_checkpoint_and_heldout_predictions(self) -> None:
        self.assertEqual(self.temporal_receipt["status"], "PASS")
        self.assertEqual(self.temporal_receipt["prediction"]["correct"], 5)
        self.assertEqual(self.temporal_receipt["prediction"]["shuffled_correct"], 0)
        self.assertEqual(self.temporal_receipt["counterfactual"]["correct"], 5)
        self.assertEqual(self.temporal_receipt["explanation"]["correct"], 5)
        self.assertEqual(self.temporal_receipt["ordering"]["correct"], 4)
        self.assertTrue(self.temporal_receipt["roundtrip"]["memory_verified"])
        expected_changes = {
            "action.gaze-left": "change.x-decrease",
            "action.gaze-right": "change.x-increase",
            "action.gaze-up": "change.y-increase",
            "action.gaze-down": "change.y-decrease",
            "action.hold": "change.none",
        }
        predecessor_hashes: set[str] = set()
        for index, action_id in enumerate(GROUND_ACTIONS):
            agent = CassiFieldAgent.open(
                config_path=self.config_path,
                checkpoint_path=self.checkpoint_path,
                state_dir=self.root / f"temporal-counterfactual-{index}",
                session_id="temporal-counterfactual",
                seed=777,
            )
            try:
                world_before = agent.world.snapshot()["snapshot_sha256"]
                position_before = self._world_position(agent)
                memory_before = agent.engine.law.memory_sha256(agent.state)
                predecessor_hashes.add(str(world_before))
                result = agent.predict_action(GROUND_HELDOUT_UTTERANCES[action_id])
                self.assertEqual(result.action_id, action_id)
                self.assertEqual(result.predicted_change, expected_changes[action_id])
                self.assertGreaterEqual(result.prediction_margin, 0.5)
                self.assertTrue(result.world_unchanged)
                self.assertTrue(result.memory_unchanged)
                self.assertEqual(self._world_position(agent), position_before)
                self.assertEqual(agent.world.logical_tick, 0)
                self.assertEqual(
                    agent.engine.law.memory_sha256(agent.state),
                    memory_before,
                )
            finally:
                agent.close()
        self.assertEqual(len(predecessor_hashes), 1)

    def test_temporal_explanation_and_forward_reverse_ordering(self) -> None:
        agent = self._open("temporal-ordering", seed=801)
        try:
            step = agent.step("turn your gaze right", consolidate=False)
            memory_after_step = step.memory_after_sha256
            world_after_step = step.world_after_sha256
            explanation = agent.explain_last_transition()
            self.assertEqual(explanation.action_id, "action.gaze-right")
            self.assertEqual(explanation.change_id, "change.x-increase")
            self.assertEqual(explanation.cause_id, "cause.gaze-right")
            self.assertEqual(
                explanation.explanation,
                "gaze-right caused x to increase",
            )
            self.assertGreater(explanation.after[0], explanation.before[0])
            self.assertTrue(explanation.memory_unchanged)
            self.assertEqual(explanation.world_after_sha256, world_after_step)

            for target, question in GROUND_TIME_HELDOUT_QUESTIONS.items():
                for presentation in ("forward", "reverse"):
                    with self.subTest(target=target, presentation=presentation):
                        result = agent.order_last_transition(
                            question,
                            presentation=presentation,
                        )
                        expected_position = (
                            "position.first"
                            if (target == "time.before")
                            == (presentation == "forward")
                            else "position.second"
                        )
                        self.assertEqual(result.target_id, target)
                        self.assertEqual(result.position_id, expected_position)
                        self.assertGreaterEqual(result.target_margin, 0.5)
                        self.assertTrue(result.memory_unchanged)
                        self.assertEqual(result.world_after_sha256, world_after_step)
            self.assertEqual(
                agent.engine.law.memory_sha256(agent.state),
                memory_after_step,
            )
            self.assertEqual(agent.world.logical_tick, 1)
        finally:
            agent.close()

    def test_temporal_transition_persists_across_reopen(self) -> None:
        state_dir = self.root / "temporal-roundtrip"
        first = CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=state_dir,
            session_id="temporal-roundtrip",
            seed=802,
        )
        step = first.step("lower your gaze down", consolidate=False)
        first.close()

        reopened = CassiFieldAgent.open(
            config_path=self.config_path,
            checkpoint_path=self.checkpoint_path,
            state_dir=state_dir,
            session_id="temporal-roundtrip",
            seed=802,
        )
        try:
            explanation = reopened.explain_last_transition()
            ordering = reopened.order_last_transition(
                GROUND_TIME_HELDOUT_QUESTIONS["time.after"],
                presentation="reverse",
            )
            self.assertEqual(explanation.schema, "cassi.grounded-field-agent.v6")
            self.assertEqual(explanation.action_id, "action.gaze-down")
            self.assertEqual(explanation.change_id, "change.y-decrease")
            self.assertEqual(explanation.before[1], 0.0)
            self.assertLess(explanation.after[1], explanation.before[1])
            self.assertEqual(ordering.target_id, "time.after")
            self.assertEqual(ordering.position_id, "position.first")
            self.assertEqual(reopened.step_count, 1)
            self.assertEqual(reopened.query_count, 2)
            self.assertEqual(
                reopened.engine.law.memory_sha256(reopened.state),
                step.memory_after_sha256,
            )
        finally:
            reopened.close()

    def test_live_phase_intervention_can_change_temporal_prediction(self) -> None:
        agent = self._open("temporal-phase-intervention", seed=803)
        try:
            observation = observe_proprioception(agent.world)
            action_cue = sense_grounded_symbols(
                agent.engine.law,
                agent.state,
                agent.codec.instruction_symbols(
                    observation,
                    GROUND_HELDOUT_UTTERANCES["action.gaze-left"],
                ),
            )
            action = select_grounded_action(
                agent.controller,
                agent.engine.law,
                agent.codec,
                action_cue,
            )
            action_committed = commit_grounded_action(
                agent.engine.law,
                agent.codec,
                action_cue,
                action,
            )
            prediction_cue = sense_prediction_prompt(
                agent.engine.law,
                action_committed,
                agent.codec,
                GROUND_PREDICTION_HELDOUT_QUESTION,
                action.action_id,
            )
            live = select_predicted_change(
                agent.controller,
                agent.engine.law,
                agent.codec,
                prediction_cue,
            )
            memory_sha256 = agent.engine.law.memory_sha256(prediction_cue)
            changed = False
            for angle in (math.pi / 2.0, math.pi, 3.0 * math.pi / 2.0):
                rotated = agent.engine.law.rotate_live_context(
                    prediction_cue,
                    angle,
                )
                self.assertEqual(
                    agent.engine.law.memory_sha256(rotated),
                    memory_sha256,
                )
                try:
                    counterfactual = select_predicted_change(
                        agent.controller,
                        agent.engine.law,
                        agent.codec,
                        rotated,
                    )
                except CassiGroundedLanguageError:
                    changed = True
                    break
                changed = changed or counterfactual.answer_id != live.answer_id
            self.assertTrue(changed)
        finally:
            agent.close()

    def test_live_transition_register_controls_causal_answers(self) -> None:
        agent = self._open("temporal-register-intervention", seed=805)
        try:
            law = agent.engine.law
            before = struct.pack("<ff", 0.0, 0.0)
            left_after = struct.pack("<ff", -0.08, 0.0)
            up_after = struct.pack("<ff", 0.0, 0.08)
            memory_sha256 = law.memory_sha256(agent.state)
            left_state = write_transition_register(
                law,
                agent.state,
                before_observation=before,
                after_observation=left_after,
                action_id="action.gaze-left",
            )
            up_state = write_transition_register(
                law,
                agent.state,
                before_observation=before,
                after_observation=up_after,
                action_id="action.gaze-up",
            )

            def causal_answers(state):
                change_cue = sense_temporal_prompt(
                    law,
                    state,
                    agent.codec,
                    "observed-change",
                    GROUND_OBSERVED_CHANGE_QUESTION,
                )
                change = select_observed_change(
                    agent.controller,
                    law,
                    agent.codec,
                    change_cue,
                )
                change_committed = commit_temporal_decision(
                    law,
                    agent.codec,
                    change_cue,
                    change,
                )
                cause_cue = sense_temporal_prompt(
                    law,
                    change_committed,
                    agent.codec,
                    "cause",
                    GROUND_CAUSE_QUESTION,
                )
                cause = select_cause(
                    agent.controller,
                    law,
                    agent.codec,
                    cause_cue,
                )
                return change.answer_id, cause.answer_id

            self.assertEqual(
                causal_answers(left_state),
                ("change.x-decrease", "cause.gaze-left"),
            )
            self.assertEqual(
                causal_answers(up_state),
                ("change.y-increase", "cause.gaze-up"),
            )

            presentation = ((0.0, 0.0), (-0.08, 0.0))
            swapped_state = write_transition_register(
                law,
                agent.state,
                before_observation=left_after,
                after_observation=before,
                action_id="action.gaze-right",
            )

            def before_position(state):
                cue = sense_order_question(
                    law,
                    state,
                    agent.codec,
                    *presentation,
                    GROUND_TIME_HELDOUT_QUESTIONS["time.before"],
                )
                target = select_time_target(
                    agent.controller,
                    law,
                    agent.codec,
                    cue,
                )
                committed = commit_temporal_decision(
                    law,
                    agent.codec,
                    cue,
                    target,
                )
                position = select_order_position(
                    agent.controller,
                    law,
                    agent.codec,
                    committed,
                    target.answer_id,
                )
                return target.answer_id, position.answer_id

            self.assertEqual(
                before_position(left_state),
                ("time.before", "position.first"),
            )
            self.assertEqual(
                before_position(swapped_state),
                ("time.before", "position.second"),
            )
            for state in (left_state, up_state, swapped_state):
                self.assertEqual(law.memory_sha256(state), memory_sha256)
        finally:
            agent.close()

    def test_temporal_save_failures_roll_back_field_and_world(self) -> None:
        agent = self._open("temporal-rollback", seed=804)
        try:
            agent.step("turn your gaze right", consolidate=False)
            state_before = qi_state_sha256(agent.controller, agent.state)
            world_before = agent.world.snapshot()["snapshot_sha256"]
            query_count = agent.query_count
            operations = {
                "predict": lambda: agent.predict_action("turn your gaze left"),
                "explain": agent.explain_last_transition,
                "order": lambda: agent.order_last_transition(
                    GROUND_TIME_HELDOUT_QUESTIONS["time.before"]
                ),
            }
            for name, operation in operations.items():
                with self.subTest(operation=name):
                    with mock.patch.object(
                        agent.store,
                        "save",
                        side_effect=OSError("disk full"),
                    ):
                        with self.assertRaisesRegex(CassiFieldAgentError, "disk full"):
                            operation()
                    self.assertEqual(
                        qi_state_sha256(agent.controller, agent.state),
                        state_before,
                    )
                    self.assertEqual(
                        agent.world.snapshot()["snapshot_sha256"],
                        world_before,
                    )
                    self.assertEqual(agent.query_count, query_count)
        finally:
            agent.close()

    def test_save_failure_rolls_back_world_and_field(self) -> None:
        agent = self._open("rollback", seed=601)
        try:
            state_before = qi_state_sha256(agent.controller, agent.state)
            world_before = agent.world.snapshot()["snapshot_sha256"]
            with mock.patch.object(
                agent.store,
                "save",
                side_effect=OSError("disk full"),
            ):
                with self.assertRaisesRegex(CassiFieldAgentError, "disk full"):
                    agent.step("turn your gaze left", consolidate=False)
            self.assertEqual(qi_state_sha256(agent.controller, agent.state), state_before)
            self.assertEqual(agent.world.snapshot()["snapshot_sha256"], world_before)
            self.assertEqual(agent.step_count, 0)
            with mock.patch.object(
                agent.store,
                "save",
                side_effect=OSError("disk full"),
            ):
                with self.assertRaisesRegex(CassiFieldAgentError, "disk full"):
                    agent.query(GROUND_SPATIAL_HELDOUT_QUESTIONS["horizontal"])
            self.assertEqual(qi_state_sha256(agent.controller, agent.state), state_before)
            self.assertEqual(agent.world.snapshot()["snapshot_sha256"], world_before)
            self.assertEqual(agent.query_count, 0)
            with mock.patch.object(
                agent.store,
                "save",
                side_effect=OSError("disk full"),
            ):
                with self.assertRaisesRegex(CassiFieldAgentError, "disk full"):
                    agent.bind_reference("Mira", "let Mira refer to red")
            self.assertEqual(qi_state_sha256(agent.controller, agent.state), state_before)
            self.assertEqual(agent.world.snapshot()["snapshot_sha256"], world_before)
            self.assertEqual(agent.binding_count, 0)
        finally:
            agent.close()

    def test_state_directory_lock_prevents_second_owner(self) -> None:
        agent = self._open("lock", seed=701)
        try:
            with self.assertRaises(RuntimeError):
                self._open("lock", seed=701)
        finally:
            agent.close()


if __name__ == "__main__":
    unittest.main()
