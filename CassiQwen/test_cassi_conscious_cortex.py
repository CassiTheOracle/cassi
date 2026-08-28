"""Focused CPU tests for the field-only conscious candidate scorer."""

from __future__ import annotations

import hashlib
import json
import unittest
from unittest.mock import patch

import torch

from cassi_conscious_cortex import (
    CORTEX_PROFILE_ID,
    CassiConsciousCortex,
    CassiConsciousCortexError,
)
from cassi_conscious_field import (
    CONSCIOUS_FIELD_PROFILE_ID,
    CassiConsciousField,
    ConsciousFieldConfig,
)
from cassi_conscious_protocol import ActorClass, EventKind, RealityStatus
from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldState


SOURCE_ID = "cassi-field-source"
SOURCE_SHA256 = "0123456789abcdef" * 4
PARENT_EVENT_ID = "abcdef0123456789" * 4


class CassiConsciousCortexTests(unittest.TestCase):
    def setUp(self) -> None:
        controller = QiFieldController(
            QiFieldConfig(
                scale_count=3,
                mode_count=16,
                alphabet_size=260,
                read_threshold=1.0e-9,
                emission_floor=1.0e-9,
            )
        )
        field = CassiConsciousField(
            controller,
            ConsciousFieldConfig(
                access_threshold=0.0,
                minimum_cross_scale_coherence=0.1,
                maximum_access_uncertainty=1.0,
            ),
        )
        self.field = field
        self.state = field.initial_state(dtype=torch.float64)
        self.cortex = CassiConsciousCortex(
            field,
            source_id=SOURCE_ID,
            source_sha256=SOURCE_SHA256,
        )

    def test_exact_provenance_tags_and_sequence_allocation(self) -> None:
        ranking = self.cortex.rank_candidates(
            self.state,
            ["zeta", b"alpha"],
            sequence_start=17,
            parent_event_id=PARENT_EVENT_ID,
        )
        self.assertEqual(ranking.sequence_start, 17)
        self.assertEqual(ranking.next_sequence, 19)
        self.assertEqual(ranking.source_id, SOURCE_ID)
        self.assertEqual(ranking.source_sha256, SOURCE_SHA256)
        # Event construction is canonical byte order, regardless of caller order.
        by_payload = {result.payload: result for result in ranking.ranked}
        self.assertEqual(by_payload[b"alpha"].event.sequence, 17)
        self.assertEqual(by_payload[b"zeta"].event.sequence, 18)
        for result in ranking.ranked:
            self.assertEqual(result.event.kind, EventKind.TEACHER_PROPOSAL)
            self.assertEqual(result.event.reality_status, RealityStatus.EXTERNAL_PROPOSAL)
            self.assertEqual(result.event.actor, ActorClass.TEACHER)
            self.assertEqual(result.event.source_id, SOURCE_ID)
            self.assertEqual(result.event.parent_event_id, PARENT_EVENT_ID)
            self.assertNotEqual(result.event.kind, EventKind.PERCEPTION)
            self.assertNotEqual(result.event.reality_status, RealityStatus.OBSERVED_REALITY)
            self.assertTrue(result.branch.branch_id)

    def test_root_is_bit_identical_and_branches_are_separate(self) -> None:
        before = self.state.field.detach().clone()
        ranking = self.cortex.rank_candidates(
            self.state,
            [b"first", b"second", b"third"],
            sequence_start=3,
            parent_event_id=PARENT_EVENT_ID,
        )
        self.assertTrue(torch.equal(before, self.state.field))
        self.assertEqual(ranking.root_field_sha256, hashlib.sha256(before.numpy().tobytes()).hexdigest())
        self.assertEqual(len({result.branch_id for result in ranking.ranked}), 3)
        self.assertEqual(
            {result.branch.root_field_sha256 for result in ranking.ranked},
            {ranking.root_field_sha256},
        )
        self.assertTrue(all(result.branch.state is not self.state for result in ranking.ranked))

    def test_canonical_order_makes_winner_and_scores_order_independent(self) -> None:
        forward = self.cortex.rank_candidates(
            self.state,
            ["gamma", "alpha", "beta"],
            sequence_start=10,
            parent_event_id=PARENT_EVENT_ID,
        )
        reverse = self.cortex.rank_candidates(
            self.state,
            ["beta", b"gamma", b"alpha"],
            sequence_start=10,
            parent_event_id=PARENT_EVENT_ID,
        )
        self.assertEqual(forward.winning_payload, reverse.winning_payload)
        self.assertEqual(
            [(item.payload, item.score, item.event.event_id) for item in forward.ranked],
            [(item.payload, item.score, item.event.event_id) for item in reverse.ranked],
        )
        self.assertEqual(forward.next_sequence, reverse.next_sequence)

    def test_render_context_is_deterministic_finite_and_json_serializable(self) -> None:
        before = self.state.field.detach().clone()
        first = self.cortex.render_context(self.state)
        second = self.cortex.render_context(self.state)
        self.assertEqual(first, second)
        self.assertTrue(torch.equal(before, self.state.field))
        json_text = json.dumps(first, sort_keys=True, allow_nan=False)
        self.assertTrue(json_text)
        self.assertEqual(first["schema"], "cassi.conscious.cortex.v2")
        self.assertEqual(first["profile_id"], CORTEX_PROFILE_ID)
        self.assertEqual(first["source_id"], SOURCE_ID)
        self.assertEqual(first["source_sha256"], SOURCE_SHA256)
        self.assertEqual(first["field"]["conscious_profile_id"], CONSCIOUS_FIELD_PROFILE_ID)
        # The context carries generic source identity and field readouts only:
        # no model/checkpoint blocks are present at any top-level key.
        self.assertEqual(
            sorted(first.keys()),
            [
                "access",
                "field",
                "interoception",
                "metacognition",
                "profile_id",
                "schema",
                "self_condensate",
                "source_id",
                "source_sha256",
            ],
        )

    def test_constructor_source_identity_is_validated(self) -> None:
        for bad_source_id in ("", 1, None):
            with self.subTest(bad_source_id=bad_source_id):
                with self.assertRaises(CassiConsciousCortexError):
                    CassiConsciousCortex(
                        self.field,
                        bad_source_id,  # type: ignore[arg-type]
                        source_sha256=SOURCE_SHA256,
                    )
        for bad_sha in ("", "A" * 64, "g" * 64, SOURCE_SHA256.upper(), "0" * 63):
            with self.subTest(bad_sha=bad_sha):
                with self.assertRaises(CassiConsciousCortexError):
                    CassiConsciousCortex(
                        self.field,
                        source_id=SOURCE_ID,
                        source_sha256=bad_sha,
                    )

    def test_malformed_candidates_source_parent_and_sequence_are_rejected(self) -> None:
        for candidate in (b"", "", b"\xff", b"x" * 4097):
            with self.subTest(candidate=repr(candidate)):
                with self.assertRaises(CassiConsciousCortexError):
                    self.cortex.rank_candidates(self.state, [candidate], sequence_start=1)
        with self.assertRaises(CassiConsciousCortexError):
            self.cortex.rank_candidates(self.state, [b"same", "same"], sequence_start=1)
        for sequence_start in (-1, True, 1.5):
            with self.subTest(sequence_start=sequence_start):
                with self.assertRaises(CassiConsciousCortexError):
                    self.cortex.rank_candidates(self.state, [b"valid"], sequence_start=sequence_start)  # type: ignore[arg-type]
        with self.assertRaises(CassiConsciousCortexError):
            self.cortex.rank_candidates(self.state, [b"valid"], sequence_start=1, parent_event_id="bad")

    def test_non_single_lane_state_is_rejected(self) -> None:
        multi_lane = QiFieldState(self.state.field.expand(-1, -1, 2).clone())
        with self.assertRaises(CassiConsciousCortexError):
            self.cortex.render_context(multi_lane)
        with self.assertRaises(CassiConsciousCortexError):
            self.cortex.rank_candidates(multi_lane, [b"valid"], sequence_start=1)

    def test_hard_bounds_reject_before_field_calls(self) -> None:
        candidates = tuple(f"candidate-{index}" for index in range(self.cortex.max_candidate_count + 1))
        for supplied, steps in (
            (candidates, 1),
            (("x" * (self.cortex.max_candidate_bytes + 1),), 1),
            (("valid",), 65),
        ):
            with self.subTest(candidate_count=len(supplied), steps=steps):
                with patch.object(self.field, "access_gate") as access_gate:
                    with self.assertRaises(CassiConsciousCortexError):
                        self.cortex.rank_candidates(
                            self.state,
                            supplied,
                            sequence_start=1,
                            steps=steps,
                        )
                    access_gate.assert_not_called()
        with self.assertRaises(CassiConsciousCortexError):
            CassiConsciousCortex(
                self.field,
                source_id=SOURCE_ID,
                source_sha256=SOURCE_SHA256,
                max_candidate_count=33,
            )

    def test_only_teacher_proposals_are_emitted_and_no_state_commit_api_exists(self) -> None:
        ranking = self.cortex.rank_candidates(
            self.state,
            [b"proposal"],
            sequence_start=2,
            parent_event_id=PARENT_EVENT_ID,
        )
        event = ranking.winner.event
        self.assertEqual(
            (event.kind, event.reality_status, event.actor),
            (EventKind.TEACHER_PROPOSAL, RealityStatus.EXTERNAL_PROPOSAL, ActorClass.TEACHER),
        )
        public_methods = {
            name
            for name in dir(self.cortex)
            if not name.startswith("_") and callable(getattr(self.cortex, name))
        }
        # The offline proposal adapter exposes only read-only ranking and context
        # methods; its source identity and bounds are immutable properties.
        self.assertEqual(public_methods, {"rank_candidates", "render_context"})
        self.assertNotEqual(event.reality_status, RealityStatus.OBSERVED_REALITY)
    def test_ranking_is_deterministic_and_exported_symbols_are_generic(self) -> None:
        first = self.cortex.rank_candidates(
            self.state,
            ("gamma", "alpha", "beta"),
            sequence_start=6,
        )
        second = self.cortex.rank_candidates(
            self.state,
            ("gamma", "alpha", "beta"),
            sequence_start=6,
        )
        self.assertEqual(
            [(item.payload, item.score, item.event.event_id) for item in first.ranked],
            [(item.payload, item.score, item.event.event_id) for item in second.ranked],
        )
        # Results expose only the generic candidate fields; no model-link field.
        self.assertEqual(
            sorted(field.name for field in first.ranked[0].__dataclass_fields__.values()),
            [
                "branch",
                "event",
                "interoception",
                "metacognition",
                "payload",
                "score",
                "text",
            ],
        )
        public_attrs = {
            name
            for name in dir(self.cortex)
            if not name.startswith("_")
        }
        for legacy in ("model_id", "model_sha256", "checkpoint_sha256"):
            self.assertNotIn(legacy, public_attrs)
        self.assertIn("source_id", public_attrs)
        self.assertIn("source_sha256", public_attrs)


if __name__ == "__main__":
    unittest.main()
