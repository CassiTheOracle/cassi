from __future__ import annotations

import hashlib
import json
from dataclasses import replace
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from typing import Any, Mapping

import torch

from cassi_field_atlas import (
    AffineConstraint,
    AtlasState,
    FieldAtlas,
    FieldIntelligenceError,
    FieldProgram,
    PrimitiveStep,
    RelationChart,
    SupportContribution,
    VariableSpec,
    canonical_json_bytes,
    sha256_value,
)
from cassi_field_cognition import (
    ActionReadout,
    FieldCognition,
    InquiryOperation,
    Survivor,
    adjoint_readout_certificate,
    choose_inquiry,
    consequence_partition,
    directed_macro_margin,
    model_uncertainty_bound,
    prequential_radius,
)
from cassi_field_owner import (
    AuthorityGrant,
    CapacityLimits,
    DeterministicWorldAdapter,
    FieldIntelligenceOwner,
    FieldIntelligenceSurface,
    RPC_SCHEMA,
    SourceInput,
    WorldAcknowledgment,
)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _base_atlas() -> tuple[FieldAtlas, AtlasState, list[str], list[str]]:
    atlas = FieldAtlas()
    state = atlas.initial_state()
    variables = (
        VariableSpec("bias", kind="constant", constant=1.0),
        VariableSpec("source", lower=-20.0, upper=20.0),
        VariableSpec("destination", lower=-20.0, upper=20.0),
        VariableSpec("displacement", lower=-40.0, upper=40.0),
        VariableSpec("left_score", lower=-40.0, upper=40.0),
        VariableSpec("right_score", lower=-40.0, upper=40.0),
    )
    for variable in variables:
        state = atlas.add_variable(state, variable)
    state = atlas.add_chart(
        state,
        RelationChart.empty(
            chart_id="geometry",
            scope=("bias", "source", "destination", "displacement"),
            ridge=1e-5,
            observation_norm_bound=64.0,
            prior_mass=1e-3,
        ),
    )
    state = atlas.add_chart(
        state,
        RelationChart.empty(
            chart_id="policy",
            scope=("bias", "displacement", "left_score", "right_score"),
            ridge=1e-5,
            observation_norm_bound=96.0,
            prior_mass=1e-3,
        ),
    )
    events: list[str] = []
    sources: list[str] = []
    pairs = (
        (-4.0, -1.0),
        (-3.0, 2.0),
        (-2.0, -5.0),
        (-1.0, 4.0),
        (0.0, 3.0),
        (1.0, -3.0),
        (2.0, 5.0),
        (3.0, 0.0),
    )
    for index, (source, destination) in enumerate(pairs):
        displacement = destination - source
        event_id = _digest(f"event:{index}")
        source_id = _digest(f"source:{index}")
        state, _ = atlas.admit_observation(
            state,
            event_id=event_id,
            source_revision_id=source_id,
            values={
                "bias": 1.0,
                "destination": destination,
                "displacement": displacement,
                "left_score": -displacement,
                "right_score": displacement,
                "source": source,
            },
            context={"domain": "line"},
        )
        events.append(event_id)
        sources.append(source_id)
    return atlas, state, events, sources


def _source(name: str, values: Mapping[str, float]) -> SourceInput:
    return SourceInput(
        source_id=name,
        content=canonical_json_bytes(dict(values)),
        media_type="application/json",
        codec="utf-8",
        observed_timestamp=name,
        scope="test",
        claim_category="controlled-observation",
        fidelity="exact-record",
        labels=("test",),
    )


class FieldAtlasBehaviorTests(unittest.TestCase):
    def test_one_relation_drives_recall_prediction_action_and_counterfactual(self) -> None:
        atlas, state, _, _ = _base_atlas()
        cognition = FieldCognition(atlas)
        before = tuple(chart.as_dict() for chart in state.charts)
        state, query, _ = atlas.think(
            state,
            observed={"destination": 6.0, "source": 2.0},
            requested=("displacement", "left_score", "right_score"),
            context={"domain": "line"},
        )
        self.assertEqual(query.status, "supported")
        self.assertEqual(tuple(chart.as_dict() for chart in state.charts), before)
        self.assertTrue(query.memory_unchanged)
        branch = query.branches[0]
        self.assertAlmostEqual(branch.values["displacement"], 4.0, places=3)
        self.assertGreater(branch.values["right_score"], branch.values["left_score"])

        readout = ActionReadout(
            readout_id="direction",
            version=1,
            labels=("left", "right"),
            coefficients=({"left_score": 1.0}, {"right_score": 1.0}),
            observed_error_radius=0.01,
        )
        decision = cognition.certify_action(
            state,
            observed={"destination": 6.0, "source": 2.0},
            readout=readout,
            context={"domain": "line"},
            authority_current=True,
            prepared_query=query,
        )
        self.assertEqual(decision.committed_action, "right")
        self.assertGreater(min(decision.certificates[0].combined_worst_margins), 0)
        counterfactual = cognition.counterfactual_without_chart(
            state,
            chart_id="geometry",
            observed={"destination": 6.0, "source": 2.0},
            requested=("displacement", "left_score", "right_score"),
            context={"domain": "line"},
        )
        self.assertNotEqual(
            counterfactual["control"]["branches"],
            counterfactual["counterfactual"]["branches"],
        )

    def test_resonant_settlement_preserves_relation_and_reports_exhaustion(self) -> None:
        atlas, state, _, _ = _base_atlas()
        arguments = {
            "observed": {"destination": 6.0, "source": 2.0},
            "requested": ("displacement", "left_score", "right_score"),
            "context": {"domain": "line"},
        }
        settled_state, settled, _ = atlas.think(state, **arguments)
        self.assertEqual(settled.status, "supported")
        self.assertAlmostEqual(settled.branches[0].values["displacement"], 4.0, places=3)
        self.assertLess(settled.branches[0].values["left_score"], 0.0)
        self.assertGreater(settled.branches[0].values["right_score"], 0.0)
        self.assertEqual(
            tuple(chart.as_dict() for chart in settled_state.charts),
            tuple(chart.as_dict() for chart in state.charts),
        )
        _, exhausted, _ = atlas.think(
            state,
            **arguments,
            tolerance=1e-30,
            max_iterations=1,
            ticks=1,
        )
        self.assertEqual(exhausted.status, "unresolved")
        self.assertFalse(exhausted.branches[0].numerical_settled)

    def test_guarded_modes_survive_as_alternatives_instead_of_blending(self) -> None:
        atlas = FieldAtlas()
        state = atlas.initial_state()
        for variable in (
            VariableSpec("bias", kind="constant", constant=1.0),
            VariableSpec("x"),
            VariableSpec("y"),
        ):
            state = atlas.add_variable(state, variable)
        for mode in ("positive", "negative"):
            state = atlas.add_chart(
                state,
                RelationChart.empty(
                    chart_id=f"mode:{mode}",
                    scope=("bias", "x", "y"),
                    mode_group="sign-relation",
                    mode=mode,
                    ridge=1e-5,
                    observation_norm_bound=20.0,
                    prior_mass=1e-3,
                ),
            )
        for index, x in enumerate((-3.0, -1.0, 1.0, 3.0)):
            for mode, sign in (("positive", 1.0), ("negative", -1.0)):
                state, _ = atlas.admit_observation(
                    state,
                    event_id=_digest(f"mode:{mode}:{index}"),
                    source_revision_id=_digest(f"source:{mode}:{index}"),
                    values={"bias": 1.0, "x": x, "y": sign * x},
                    context={},
                    target_chart_ids=(f"mode:{mode}",),
                )
        state, result, _ = atlas.think(state, observed={"x": 2.0}, requested=("y",))
        self.assertEqual(result.status, "alternatives")
        predictions = sorted(round(row.values["y"], 3) for row in result.branches)
        self.assertEqual(predictions, [-2.0, 2.0])

    def test_partial_and_hypothetical_values_cannot_teach_memory(self) -> None:
        atlas, state, _, _ = _base_atlas()
        with self.assertRaises(FieldIntelligenceError) as partial:
            atlas.admit_observation(
                state,
                event_id=_digest("partial"),
                source_revision_id=_digest("partial-source"),
                values={"source": 1.0},
                context={"domain": "line"},
                target_chart_ids=("geometry",),
            )
        self.assertEqual(partial.exception.code, "PARTIAL_OBSERVATION")
        with self.assertRaises(FieldIntelligenceError) as hypothetical:
            atlas.admit_observation(
                state,
                event_id=_digest("hypothesis"),
                source_revision_id=_digest("hypothesis-source"),
                values={"bias": 1.0, "source": 1.0, "destination": 2.0, "displacement": 1.0},
                context={"domain": "line"},
                epistemic_type="hypothetical",
            )
        self.assertEqual(hypothetical.exception.code, "EPISTEMIC_BOUNDARY")

    def test_contextual_chart_adapts_with_explicit_field_owned_recency(self) -> None:
        atlas = FieldAtlas()
        state = atlas.initial_state()
        for variable in (
            VariableSpec("bias", kind="constant", constant=1.0),
            VariableSpec("x"),
            VariableSpec("y"),
        ):
            state = atlas.add_variable(state, variable)
        state = atlas.add_chart(
            state,
            RelationChart.empty(
                chart_id="contextual",
                scope=("bias", "x", "y"),
                ridge=1e-5,
                observation_norm_bound=20.0,
                prior_mass=1e-3,
                learning_mode="contextual",
                recency_half_life=1.0,
            ),
        )
        for index, x in enumerate((-3.0, -1.0, 1.0, 3.0)):
            state, _ = atlas.admit_observation(
                state,
                event_id=_digest(f"old:{index}"),
                source_revision_id=_digest(f"old-source:{index}"),
                values={"bias": 1.0, "x": x, "y": x},
                context={},
            )
        for index, x in enumerate((-3.0, -1.0, 1.0, 3.0)):
            state, _ = atlas.admit_observation(
                state,
                event_id=_digest(f"new:{index}"),
                source_revision_id=_digest(f"new-source:{index}"),
                values={"bias": 1.0, "x": x, "y": -x},
                context={},
            )
        state, result, _ = atlas.think(state, observed={"x": 2.0}, requested=("y",))
        self.assertEqual(result.status, "supported")
        self.assertLess(result.branches[0].values["y"], -1.0)
        restored = AtlasState.decode_bundle(state.encode_bundle())
        self.assertEqual(restored.encode(), state.encode())
        self.assertEqual(
            restored.chart("contextual").learning_mode,
            "contextual",
        )

    def test_constraints_reject_inconsistent_commitment(self) -> None:
        atlas, state, _, _ = _base_atlas()
        state, result, _ = atlas.think(
            state,
            observed={"source": 2.0},
            requested=("destination",),
            constraints=(
                AffineConstraint({"destination": 1.0}, 4.0),
                AffineConstraint({"destination": 1.0}, 5.0),
            ),
        )
        self.assertEqual(result.status, "unresolved")
        self.assertEqual(result.branches[0].status, "infeasible")
        self.assertIn("inconsistent-constraints", result.branches[0].obligations)

    def test_exact_schur_reduction_matches_full_energy(self) -> None:
        atlas, state, _, _ = _base_atlas()
        reduced = atlas.derive_schur_reduction(
            state,
            macro_id="direction-macro",
            boundary=("bias", "source", "destination", "left_score", "right_score"),
            interior=("displacement",),
        )
        macro = reduced.macros[0]
        order = (*macro.boundary, *macro.interior)
        charts = tuple(state.charts)
        hessian = atlas._assemble_precision(order, charts)
        boundary = torch.tensor((1.0, 2.0, 6.0, -4.0, 4.0), dtype=torch.float64)
        h_bb = torch.tensor(macro.hessian, dtype=torch.float64)
        h_bi = hessian[: len(boundary), len(boundary) :]
        h_ii = hessian[len(boundary) :, len(boundary) :]
        interior = -torch.linalg.solve(h_ii, h_bi.T @ boundary)
        full = torch.cat((boundary, interior))
        full_energy = 0.5 * float(full @ hessian @ full)
        macro_energy = 0.5 * float(boundary @ h_bb @ boundary) + macro.constant
        self.assertAlmostEqual(full_energy, macro_energy, places=8)
        replace_chart = state.chart("geometry").rebuild(
            at_tick=state.logical_tick + 1,
            contributions=state.chart("geometry").contributions,
        )
        stale_state = atlas.replace_chart(reduced, replace_chart)
        self.assertFalse(stale_state.macros[0].valid_for(stale_state, {}))


    def test_relation_chart_tensor_is_defensively_owned(self) -> None:
        atlas, state, _, _ = _base_atlas()
        before = state.encode()
        _, expected, _ = atlas.think(
            state,
            observed={"source": 2.0, "destination": 6.0},
            requested=("displacement",),
        )
        exposed = state.chart("geometry").numeric_field
        exposed.zero_()
        self.assertEqual(state.encode(), before)
        _, actual, _ = atlas.think(
            state,
            observed={"source": 2.0, "destination": 6.0},
            requested=("displacement",),
        )
        self.assertEqual(
            actual.branches[0].values,
            expected.branches[0].values,
        )

    def test_incomplete_resonant_response_cannot_certify_settlement(self) -> None:
        atlas = FieldAtlas()
        state = atlas.initial_state()
        for variable in (
            VariableSpec("bias", kind="constant", constant=1.0),
            VariableSpec("x"),
            VariableSpec("y"),
            VariableSpec("z"),
        ):
            state = atlas.add_variable(state, variable)
        chart = RelationChart.empty(
            chart_id="ill-conditioned",
            scope=("bias", "x", "y", "z"),
            ridge=1e-6,
            observation_norm_bound=100.0,
        )
        precision = torch.tensor(
            (
                (1.0, 0.0, 0.0, 0.0),
                (0.0, 100.0, 1.0, 0.0),
                (0.0, 1.0, 1.0, 0.99),
                (0.0, 0.0, 0.99, 1.0),
            ),
            dtype=torch.float64,
        )
        covariance = torch.linalg.inv(precision)
        numeric_field = chart.numeric_field
        chart.engine._put_covariance(
            chart.engine._parts(numeric_field), 0, covariance
        )
        contribution = SupportContribution(
            event_id=_digest("matrix:event"),
            source_revision_id=_digest("matrix:source"),
            values=(1.0, 0.0, 0.0, 0.0),
            weight=1.0,
            logical_tick=1,
            epistemic_type="observed",
            context_sha256=sha256_value({}),
        )
        state = atlas.add_chart(
            state,
            replace(
                chart,
                _numeric_field=numeric_field,
                contributions=(contribution,),
            ),
        )
        state, result, _ = atlas.think(
            state,
            observed={"x": 0.0},
            requested=("y", "z"),
            max_iterations=1,
            ticks=1,
            tolerance=1e-30,
        )
        self.assertEqual(result.status, "unresolved")
        self.assertFalse(result.branches[0].numerical_settled)

    def test_inferred_values_must_remain_inside_declared_domains(self) -> None:
        atlas = FieldAtlas()
        state = atlas.initial_state()
        state = atlas.add_variable(state, VariableSpec("x", lower=0.0, upper=1.0))
        state = atlas.add_variable(state, VariableSpec("y", lower=0.0, upper=100.0))
        state = atlas.add_chart(
            state,
            RelationChart.empty(
                chart_id="bounded",
                scope=("x", "y"),
                ridge=1e-5,
                observation_norm_bound=100.0,
            ),
        )
        for index, x in enumerate((0.2, 0.4, 0.6, 0.8)):
            state, _ = atlas.admit_observation(
                state,
                event_id=_digest(f"bounded:event:{index}"),
                source_revision_id=_digest(f"bounded:source:{index}"),
                values={"x": x, "y": 10.0 * x},
                context={},
            )
        state, result, _ = atlas.think(state, observed={"y": 20.0}, requested=("x",))
        self.assertEqual(result.status, "unresolved")
        self.assertEqual(result.branches[0].status, "infeasible")

    def test_retraction_follows_derived_evidence_roots(self) -> None:
        atlas = FieldAtlas()
        state = atlas.initial_state()
        state = atlas.add_variable(state, VariableSpec("x"))
        state = atlas.add_variable(state, VariableSpec("y"))
        state = atlas.add_chart(
            state,
            RelationChart.empty(
                chart_id="derived",
                scope=("x", "y"),
                observation_norm_bound=20.0,
            ),
        )
        parent_event = _digest("parent:event")
        parent_source = _digest("parent:source")
        derived_event = _digest("derived:event")
        state, _ = atlas.admit_observation(
            state,
            event_id=parent_event,
            source_revision_id=parent_source,
            values={"x": 1.0, "y": 1.0},
            context={},
        )
        state, _ = atlas.admit_observation(
            state,
            event_id=derived_event,
            source_revision_id=_digest("derived:source"),
            values={"x": 2.0, "y": 2.0},
            context={},
            epistemic_type="derived",
            derivation_roots=(parent_source, parent_event),
        )
        retracted, _ = atlas.retract_sources(
            state,
            (parent_source,),
            revocation_generation=1,
        )
        retained = {
            row.event_id for row in retracted.chart("derived").contributions
        }
        self.assertNotIn(parent_event, retained)
        self.assertNotIn(derived_event, retained)

class StructureAndDecisionTests(unittest.TestCase):
    def test_prequential_program_search_promotes_future_predictive_difference(self) -> None:
        atlas, state, events, _ = _base_atlas()
        cognition = FieldCognition(atlas)
        state, candidate_ids = cognition.propose_relational_structure(
            state,
            problem_id="relative-position",
            input_roles=("source", "destination"),
            output_role="displacement",
            support_event_ids=events[:2],
            max_candidates=9,
        )
        future = ((1.0, 4.0), (2.0, 6.0), (-2.0, 3.0))
        for episode, (source, destination) in enumerate(future):
            predictions: dict[str, str] = {}
            for candidate_id in candidate_ids:
                state, prediction = cognition.begin_program_assessment(
                    state,
                    program_id=candidate_id,
                    bindings={"source": source, "destination": destination},
                    authority_generation=0,
                )
                predictions[candidate_id] = prediction.prediction_id
            for candidate_id in candidate_ids:
                state, _ = cognition.resolve_program_assessment(
                    state,
                    program_id=candidate_id,
                    prediction_id=predictions[candidate_id],
                    outcome={"displacement": destination - source},
                    event_id=_digest(f"future:{episode}:{candidate_id}"),
                    loss_scale=10.0,
                )
        state, promoted = cognition.promote_program(
            state,
            candidate_ids=candidate_ids,
            minimum_assessments=3,
            maximum_average_loss=1e-12,
            bit_penalty=1e-6,
        )
        self.assertEqual(
            promoted.execute({"source": 10.0, "destination": 14.5}),
            {"displacement": 4.5},
        )

    def test_prediction_is_single_use_and_revoked_program_stays_stale(self) -> None:
        atlas, state, events, sources = _base_atlas()
        cognition = FieldCognition(atlas)
        state, candidate_ids = cognition.propose_relational_structure(
            state,
            problem_id="single-use",
            input_roles=("source", "destination"),
            output_role="displacement",
            support_event_ids=events[:2],
            max_candidates=9,
        )
        program_id = candidate_ids[-1]
        state, prediction = cognition.begin_program_assessment(
            state,
            program_id=program_id,
            bindings={"source": 1.0, "destination": 4.0},
            authority_generation=0,
        )
        state, _ = cognition.resolve_program_assessment(
            state,
            program_id=program_id,
            prediction_id=prediction.prediction_id,
            outcome={"displacement": 3.0},
            event_id=_digest("single-use:future"),
            loss_scale=10.0,
        )
        with self.assertRaises(FieldIntelligenceError) as repeated:
            cognition.resolve_program_assessment(
                state,
                program_id=program_id,
                prediction_id=prediction.prediction_id,
                outcome={"displacement": 3.0},
                event_id=_digest("single-use:other-future"),
                loss_scale=10.0,
            )
        self.assertEqual(repeated.exception.code, "ASSESSMENT_CONFLICT")
        state, _ = cognition.promote_program(
            state,
            candidate_ids=(program_id,),
            minimum_assessments=1,
            maximum_average_loss=0.0,
            bit_penalty=0.0,
        )
        state, _ = atlas.retract_sources(
            state,
            (sources[0],),
            revocation_generation=1,
        )
        self.assertEqual(state.program(program_id).status, "stale")
        with self.assertRaises(FieldIntelligenceError) as stale:
            cognition.promote_program(
                state,
                candidate_ids=(program_id,),
                minimum_assessments=1,
                maximum_average_loss=0.0,
                bit_penalty=0.0,
            )
        self.assertEqual(stale.exception.code, "PROMOTION_UNSUPPORTED")

    def test_learned_construction_is_productive_and_bidirectional(self) -> None:
        atlas = FieldAtlas()
        cognition = FieldCognition(atlas)
        state = atlas.initial_state()
        semantic = FieldProgram(
            program_id="relocation-semantics",
            version=1,
            roles=("destination", "source"),
            steps=(
                PrimitiveStep("identity", "destination_value", ("destination",)),
                PrimitiveStep("identity", "source_value", ("source",)),
            ),
            outputs=("source_value", "destination_value"),
            status="promoted",
        )
        state = atlas.add_program(state, semantic)
        examples = (
            {"event_id": _digest("language:1"), "text": "move from 1 to 4.", "roles": {"source": "1", "destination": "4"}},
            {"event_id": _digest("language:2"), "text": "move from 2 to 7.", "roles": {"source": "2", "destination": "7"}},
        )
        state, _ = cognition.propose_language_construction(
            state,
            construction_id="relocation-construction",
            examples=examples,
            semantic_program_id=semantic.program_id,
        )
        with self.assertRaises(FieldIntelligenceError) as unsupported:
            cognition.promote_language_construction(
                state,
                construction_id="relocation-construction",
                minimum_assessments=0,
            )
        self.assertEqual(unsupported.exception.code, "INVALID_PROMOTION")
        state, assessment = cognition.assess_language_construction(
            state,
            construction_id="relocation-construction",
            text="move from 8 to 13.",
            expected_roles={"destination": "13", "source": "8"},
            event_id=_digest("language:3"),
        )
        self.assertEqual(assessment.normalized_loss, 0)
        state, _ = cognition.promote_language_construction(
            state, construction_id="relocation-construction"
        )
        understood = cognition.interpret_utterance(
            state, text="move from 21 to 34."
        )
        expressed = cognition.express_meaning(
            state,
            semantic_program_id=semantic.program_id,
            bindings={"destination": "34", "source": "21"},
        )
        self.assertEqual(understood["status"], "understood")
        self.assertEqual(
            understood["branches"][0]["semantic"],
            {"destination_value": "34", "source_value": "21"},
        )
        self.assertEqual(expressed["text"], "move from 21 to 34.")
        self.assertTrue(expressed["target_blind_stop"])
        replacement = replace(semantic, version=2)
        stale_language = atlas.replace_program(state, replacement)
        self.assertEqual(
            stale_language.construction("relocation-construction").status,
            "stale",
        )

    def test_minimax_inquiry_selects_guaranteed_action_resolver(self) -> None:
        survivors = (
            Survivor("left-mode", ("left",), {"cheap": ((-1.0, 1.0),), "sense": ((-5.0, -0.1),)}),
            Survivor("right-mode", ("right",), {"cheap": ((-1.0, 1.0),), "sense": ((0.1, 5.0),)}),
        )
        decision = choose_inquiry(
            survivors,
            (
                InquiryOperation("cheap", cost=0.1, risk=0.0, authorized=True, feasible=True),
                InquiryOperation("sense", cost=1.0, risk=0.0, authorized=True, feasible=True),
            ),
        )
        self.assertEqual(decision.status, "resolving")
        self.assertEqual(decision.selected_query_id, "sense")
        self.assertEqual(decision.k_by_query["sense"], 1)

    def test_bounds_cover_actual_errors_and_quotient_consequence(self) -> None:
        model = model_uncertainty_bound(
            free_hessian=((3.0, 0.2), (0.2, 2.0)),
            boundary_block=((1.0,), (0.5,)),
            observed=(2.0,),
            free_readout=(1.0, -0.5),
            observed_readout=(0.25,),
            hessian_error=0.05,
            boundary_error=0.03,
            observation_radius=0.1,
        )
        self.assertGreater(model["total_bound"], 0)
        adjoint = adjoint_readout_certificate(
            system=((3.0, 0.2), (0.2, 2.0)),
            rhs=(1.0, -0.5),
            approximate_state=(0.34, -0.28),
            readout=(1.0, -2.0),
        )
        self.assertLessEqual(abs(adjoint["actual_readout_error"]), adjoint["bound"] + 1e-14)
        directed = directed_macro_margin(
            operators=(((1.0, 0.1), (0.0, 0.9)), ((0.8, 0.0), (0.1, 1.0))),
            center=(2.0, -1.0),
            score_direction=(1.0, -0.5),
            initial_radius=0.1,
            disturbance_radii=(0.02, 0.03),
        )
        self.assertLess(directed["lower_margin"], directed["nominal_score"])
        quotient = consequence_partition(
            {
                "h1": {"t": {"a": 0.1, "b": 0.5}},
                "h2": {"t": {"a": 0.15, "b": 0.54}},
            },
            epsilon=0.06,
        )
        self.assertTrue(quotient["admitted"])
        self.assertLessEqual(quotient["maximum_excess"], quotient["two_epsilon_bound"])
        self.assertGreater(prequential_radius(count=100, prefix_code_bits=8, delta=0.05), 0)


class OwnerPersistenceTests(unittest.TestCase):
    def _owner(self, root: Path, *, limits: CapacityLimits | None = None) -> FieldIntelligenceOwner:
        owner = FieldIntelligenceOwner(root, limits=limits)
        for index, variable in enumerate(
            (
                VariableSpec("bias", kind="constant", constant=1.0),
                VariableSpec("x", lower=-10.0, upper=10.0),
                VariableSpec("y", lower=-10.0, upper=10.0),
            )
        ):
            owner.configure_variable(f"variable:{index}", variable)
        owner.configure_chart(
            "chart:xy",
            RelationChart.empty(
                chart_id="xy",
                scope=("bias", "x", "y"),
                ridge=1e-5,
                observation_norm_bound=20.0,
                prior_mass=1e-3,
            ),
        )
        return owner

    def test_exact_restart_effect_acknowledgment_and_revocation_fence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            revision_ids: list[str] = []
            for index, x in enumerate((-3.0, -1.0, 1.0, 3.0)):
                values = {"bias": 1.0, "x": x, "y": x}
                admitted = owner.admit_observation(
                    operation_id=f"observe:{index}",
                    source=_source(f"source:{index}", values),
                    values=values,
                    context={},
                )
                revision_ids.append(admitted["source"]["revision_id"])
            prepared = owner.think(operation_id="think:identity", observed={"x": 2.0}, requested=("y",))
            query = owner.query(query_id=prepared["query_id"])
            self.assertEqual(query["status"], "supported")
            self.assertTrue(query["memory_unchanged"])
            readout = ActionReadout(
                readout_id="sign",
                version=1,
                labels=("negative", "positive"),
                coefficients=({"y": -1.0}, {"y": 1.0}),
                observed_error_radius=0.01,
            )
            proposal = owner.propose_effect(
                operation_id="effect:1",
                observed={"x": 2.0},
                readout=readout,
                target="test-world",
                scope="test",
                payload={"amount": 1},
            )
            self.assertEqual(proposal["status"], "proposed")

            def transition(action: str, target: str, payload: Mapping[str, Any]) -> WorldAcknowledgment:
                return WorldAcknowledgment(
                    acknowledgment_id="ack:1",
                    operation_id="effect:1",
                    status="succeeded",
                    observed_values={"x": 2.0, "y": 2.0},
                    context={},
                    source_content=canonical_json_bytes(
                        {"action": action, "payload": dict(payload), "target": target}
                    ),
                )

            adapter = DeterministicWorldAdapter(transition)
            dispatched = owner.dispatch_effect(
                prediction_id=proposal["prediction"]["prediction_id"],
                grant=AuthorityGrant(
                    grant_id="grant:effect",
                    issuer="test-host",
                    generation=0,
                    operation="effect",
                    target="test-world",
                    scope="test",
                ),
                adapter=adapter,
            )
            self.assertEqual(dispatched["status"], "acknowledged")
            self.assertEqual(adapter.execute_count, 1)
            exact = owner.state.encode()
            old_manifest = owner.checkpoints.current_manifest_sha256
            owner.close()
            restarted = FieldIntelligenceOwner(root)
            self.assertEqual(restarted.state.encode(), exact)
            think_replay = restarted.think(
                operation_id="think:identity",
                observed={"x": 2.0},
                requested=("y",),
            )
            self.assertTrue(think_replay["checkpoint_receipt"]["replayed"])
            self.assertEqual(
                canonical_json_bytes(
                    {
                        key: value
                        for key, value in think_replay.items()
                        if key != "checkpoint_receipt"
                    }
                ),
                canonical_json_bytes(
                    {
                        key: value
                        for key, value in prepared.items()
                        if key != "checkpoint_receipt"
                    }
                ),
            )
            self.assertEqual(restarted.state.encode(), exact)
            with self.assertRaises(
                FieldIntelligenceError
            ) as source_conflict:
                restarted.think(
                    operation_id="think:identity",
                    observed={"x": 2.0},
                    requested=("y",),
                    valid_source_revision_ids=(revision_ids[0],),
                )
            self.assertEqual(
                source_conflict.exception.code,
                "OPERATION_CONFLICT",
            )
            self.assertEqual(restarted.state.encode(), exact)
            with self.assertRaises(
                FieldIntelligenceError
            ) as think_conflict:
                restarted.think(
                    operation_id="think:identity",
                    observed={"x": 3.0},
                    requested=("y",),
                )
            self.assertEqual(
                think_conflict.exception.code,
                "OPERATION_CONFLICT",
            )
            self.assertEqual(restarted.state.encode(), exact)
            replay = restarted.dispatch_effect(
                prediction_id=proposal["prediction"]["prediction_id"],
                grant=AuthorityGrant(
                    grant_id="grant:unused-replay",
                    issuer="test-host",
                    generation=0,
                    operation="effect",
                    target="test-world",
                    scope="test",
                ),
                adapter=adapter,
            )
            self.assertEqual(replay["status"], "already-acknowledged")
            self.assertEqual(adapter.execute_count, 1)

            preview = restarted.preview_forget((revision_ids[0],))
            target = sha256_value(sorted((revision_ids[0],)))
            result = restarted.forget(
                operation_id="forget:1",
                preview_id=preview["preview_id"],
                revision_ids=(revision_ids[0],),
                grant=AuthorityGrant(
                    grant_id="grant:forget",
                    issuer="test-host",
                    generation=0,
                    operation="forget",
                    target=target,
                    scope="test",
                ),
                scope="test",
            )
            self.assertTrue(result["adaptive_forgetting"])
            with self.assertRaises(FieldIntelligenceError) as stale:
                restarted.checkpoints.load_version(old_manifest)
            self.assertEqual(stale.exception.code, "STALE_REVOCATION")
            with self.assertRaises(FieldIntelligenceError) as stale_export:
                restarted.export_bundle(old_manifest)
            self.assertEqual(stale_export.exception.code, "STALE_REVOCATION")
            with self.assertRaises(FieldIntelligenceError):
                restarted.exact_recall(
                    revision_id=revision_ids[0],
                    allowed_labels=frozenset({"test"}),
                )
            remaining = restarted.think(operation_id="think:after-forget", observed={"x": 2.0}, requested=("y",))
            self.assertEqual(remaining["status"], "supported")
            restarted.close()

    def test_pending_observation_is_completed_after_owner_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            values = {"bias": 1.0, "x": 2.0, "y": 2.0}
            source = _source("pending-source", values)
            owner._stage_pending(
                operation_id="pending:observation",
                kind="observation",
                payload={
                    "context": {},
                    "derivation_roots": [],
                    "epistemic_type": "observed",
                    "event_kind": "observation",
                    "source": source.as_dict(),
                    "target_chart_ids": None,
                    "values": values,
                    "weight": 1.0,
                },
            )
            owner.close()
            recovered = FieldIntelligenceOwner(root)
            self.assertEqual(
                recovered.think(operation_id="think:recovered", observed={"x": 3.0}, requested=("y",))["status"],
                "supported",
            )
            self.assertEqual(recovered.evidence.event_count, 1)
            self.assertEqual(list(recovered.pending_path.iterdir()), [])
            recovered.close()

    def test_pending_retry_rejects_altered_request_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            values = {"bias": 1.0, "x": 2.0, "y": 2.0}
            source = _source("stale-client-source", values)
            committed_state = owner.state.state_sha256

            def interrupt(*_args: Any, **_kwargs: Any) -> None:
                raise OSError("simulated interruption after pending staging")

            try:
                with patch.object(owner.evidence, "append_event", interrupt):
                    with self.assertRaises(OSError):
                        owner.admit_observation(
                            operation_id="pending:stale-client",
                            source=source,
                            values=values,
                            context={},
                        )
                pending_path = next(owner.pending_path.iterdir())
                pending_bytes = pending_path.read_bytes()
                evidence_index_bytes = owner.evidence.index_path.read_bytes()

                with self.assertRaises(FieldIntelligenceError) as conflict:
                    owner.admit_observation(
                        operation_id="pending:stale-client",
                        source=source,
                        values={**values, "y": 3.0},
                        context={},
                    )
                self.assertEqual(conflict.exception.code, "OPERATION_CONFLICT")
                self.assertEqual(owner.state.state_sha256, committed_state)
                self.assertEqual(owner.evidence.event_count, 0)
                self.assertEqual(pending_path.read_bytes(), pending_bytes)
                self.assertEqual(
                    owner.evidence.index_path.read_bytes(),
                    evidence_index_bytes,
                )
                owner.close()

                recovered = FieldIntelligenceOwner(root)
                self.assertEqual(recovered.evidence.event_count, 1)
                self.assertEqual(list(recovered.pending_path.iterdir()), [])
                recovered.close()
            finally:
                owner.close()

    def test_canonical_malformed_pending_payload_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            values = {"bias": 1.0, "x": 2.0, "y": 2.0}
            source = _source("malformed-pending-source", values)
            try:
                owner._stage_pending(
                    operation_id="pending:malformed",
                    kind="observation",
                    payload={
                        "context": {},
                        "derivation_roots": [],
                        "epistemic_type": "observed",
                        "event_kind": "observation",
                        "source": source.as_dict(),
                        "target_chart_ids": None,
                        "values": values,
                        "weight": 1.0,
                    },
                )
                pending_path = next(owner.pending_path.iterdir())
                envelope = dict(owner._read_pending(pending_path))
                malformed_payload = dict(envelope["payload"])
                malformed_payload.pop("values")
                envelope["payload"] = malformed_payload
                pending_path.write_bytes(canonical_json_bytes(envelope))
                malformed_bytes = pending_path.read_bytes()
                owner.close()

                with self.assertRaises(FieldIntelligenceError) as corrupt:
                    FieldIntelligenceOwner(root)
                self.assertEqual(
                    corrupt.exception.code,
                    "PENDING_OPERATION_CORRUPT",
                )
                self.assertEqual(pending_path.read_bytes(), malformed_bytes)
                self.assertEqual(
                    list((root / "pending-failures").iterdir()),
                    [],
                )
            finally:
                owner.close()

    def test_canonical_malformed_pending_predecessor_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            values = {"bias": 1.0, "x": 2.0, "y": 2.0}
            source = _source("malformed-predecessor-source", values)
            try:
                owner._stage_pending(
                    operation_id="pending:malformed-predecessor",
                    kind="observation",
                    payload={
                        "context": {},
                        "derivation_roots": [],
                        "epistemic_type": "observed",
                        "event_kind": "observation",
                        "source": source.as_dict(),
                        "target_chart_ids": None,
                        "values": values,
                        "weight": 1.0,
                    },
                )
                pending_path = next(owner.pending_path.iterdir())
                envelope = dict(owner._read_pending(pending_path))
                malformed_predecessor = dict(envelope["predecessor"])
                malformed_predecessor["generation"] = "0"
                envelope["predecessor"] = malformed_predecessor
                pending_path.write_bytes(canonical_json_bytes(envelope))
                malformed_bytes = pending_path.read_bytes()
                owner.close()

                with self.assertRaises(FieldIntelligenceError) as corrupt:
                    FieldIntelligenceOwner(root)
                self.assertEqual(
                    corrupt.exception.code,
                    "PENDING_OPERATION_CORRUPT",
                )
                self.assertEqual(pending_path.read_bytes(), malformed_bytes)
                self.assertEqual(
                    list((root / "pending-failures").iterdir()),
                    [],
                )
            finally:
                owner.close()

    def test_committed_observation_retry_binds_weight_and_target_charts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            values = {"bias": 1.0, "x": 2.0, "y": 2.0}
            source = _source("exact-observation-request", values)

            def interrupt(_operation_id: str) -> None:
                raise OSError("simulated interruption after checkpoint commit")

            try:
                with patch.object(owner, "_finish_pending", interrupt):
                    with self.assertRaises(OSError):
                        owner.admit_observation(
                            operation_id="observation:exact-request",
                            source=source,
                            values=values,
                            context={},
                            weight=1,
                            target_chart_ids=("xy",),
                        )
                committed_state = owner.state.state_sha256
                pending_path = next(owner.pending_path.iterdir())
                pending_bytes = pending_path.read_bytes()
                self.assertEqual(owner.evidence.event_count, 1)

                with self.assertRaises(FieldIntelligenceError) as weight_conflict:
                    owner.admit_observation(
                        operation_id="observation:exact-request",
                        source=source,
                        values=values,
                        context={},
                        weight=0.75,
                        target_chart_ids=("xy",),
                    )
                self.assertEqual(
                    weight_conflict.exception.code,
                    "OPERATION_CONFLICT",
                )
                self.assertEqual(owner.state.state_sha256, committed_state)
                self.assertEqual(pending_path.read_bytes(), pending_bytes)
                operation_path = owner.checkpoints._operation_path(
                    "observation:exact-request"
                )
                committed = owner.checkpoints._committed_operation(
                    "observation:exact-request"
                )
                assert committed is not None
                operation_record = dict(committed[0])
                operation_bytes = operation_path.read_bytes()
                owner.close()

                operation_path.write_bytes(
                    canonical_json_bytes(
                        {
                            **operation_record,
                            "semantic_sha256": "0" * 64,
                        }
                    )
                )
                corrupted_operation_bytes = operation_path.read_bytes()
                with self.assertRaises(FieldIntelligenceError) as corrupt:
                    FieldIntelligenceOwner(root)
                self.assertEqual(
                    corrupt.exception.code,
                    "CHECKPOINT_CORRUPT",
                )
                self.assertEqual(
                    operation_path.read_bytes(),
                    corrupted_operation_bytes,
                )
                self.assertEqual(pending_path.read_bytes(), pending_bytes)
                operation_path.write_bytes(operation_bytes)

                recovered = FieldIntelligenceOwner(root)
                self.assertEqual(recovered.state.state_sha256, committed_state)
                self.assertEqual(recovered.evidence.event_count, 1)
                self.assertEqual(list(recovered.pending_path.iterdir()), [])

                with self.assertRaises(FieldIntelligenceError) as target_conflict:
                    recovered.admit_observation(
                        operation_id="observation:exact-request",
                        source=source,
                        values=values,
                        context={},
                        weight=1.0,
                        target_chart_ids=None,
                    )
                self.assertEqual(
                    target_conflict.exception.code,
                    "OPERATION_CONFLICT",
                )
                replay = recovered.admit_observation(
                    operation_id="observation:exact-request",
                    source=source,
                    values=values,
                    context={},
                    weight=1.0,
                    target_chart_ids=("xy",),
                )
                self.assertTrue(replay["receipt"]["replayed"])
                self.assertEqual(recovered.state.state_sha256, committed_state)
                self.assertEqual(recovered.evidence.event_count, 1)
                recovered.close()
            finally:
                owner.close()

    def test_committed_operation_pointer_integrity_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            try:
                first = owner.advance(
                    "operation-pointer-integrity",
                    ticks=1,
                )
                committed_state = owner.state.state_sha256
                event_count = owner.evidence.event_count
                operation_path = owner.checkpoints._operation_path(
                    "operation-pointer-integrity"
                )
                committed = owner.checkpoints._committed_operation(
                    "operation-pointer-integrity"
                )
                assert committed is not None
                record = dict(committed[0])
                original_bytes = operation_path.read_bytes()
                corruptions = {
                    "extra-field": {**record, "unexpected": True},
                    "manifest": {
                        **record,
                        "manifest_sha256": "0" * 64,
                    },
                    "operation": {
                        **record,
                        "operation_id": "another-operation",
                    },
                    "parent": {
                        **record,
                        "parent_manifest_sha256": "0" * 64,
                    },
                    "semantic": {
                        **record,
                        "semantic_sha256": "0" * 64,
                    },
                }
                for label, corrupted in corruptions.items():
                    with self.subTest(label=label):
                        operation_path.write_bytes(
                            canonical_json_bytes(corrupted)
                        )
                        corrupted_bytes = operation_path.read_bytes()
                        with self.assertRaises(
                            FieldIntelligenceError
                        ) as failure:
                            owner.advance(
                                "operation-pointer-integrity",
                                ticks=1,
                            )
                        self.assertEqual(
                            failure.exception.code,
                            "CHECKPOINT_CORRUPT",
                        )
                        self.assertEqual(
                            operation_path.read_bytes(),
                            corrupted_bytes,
                        )
                        self.assertEqual(
                            owner.state.state_sha256,
                            committed_state,
                        )
                        self.assertEqual(
                            owner.evidence.event_count,
                            event_count,
                        )
                        operation_path.write_bytes(original_bytes)

                replay = owner.advance(
                    "operation-pointer-integrity",
                    ticks=1,
                )
                self.assertTrue(
                    replay["checkpoint_receipt"]["replayed"]
                )
                self.assertEqual(
                    replay["resonance_receipt"],
                    first["resonance_receipt"],
                )
            finally:
                owner.close()

    def test_restart_validates_operation_records_and_manifest_lineage(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            owner.advance("history:1", ticks=1)
            owner.advance("history:2", ticks=1)
            committed_state = owner.state.state_sha256
            current_manifest = dict(owner.checkpoints.current_manifest)
            parent_manifest = owner.checkpoints._manifest(
                current_manifest["parent_manifest_sha256"]
            )
            root_manifest_sha = parent_manifest[
                "parent_manifest_sha256"
            ]
            assert root_manifest_sha is not None
            current_path = owner.checkpoints.current_path
            current_bytes = current_path.read_bytes()
            operation_path = owner.checkpoints._operation_path(
                "history:2"
            )
            committed = owner.checkpoints._committed_operation(
                "history:2"
            )
            assert committed is not None
            operation_record = dict(committed[0])
            operation_bytes = operation_path.read_bytes()
            owner.close()

            corrupted_operation = canonical_json_bytes(
                {**operation_record, "semantic_sha256": "0" * 64}
            )
            operation_path.write_bytes(corrupted_operation)
            with self.assertRaises(FieldIntelligenceError) as operation:
                FieldIntelligenceOwner(root)
            self.assertEqual(
                operation.exception.code,
                "CHECKPOINT_CORRUPT",
            )
            self.assertEqual(
                operation_path.read_bytes(),
                corrupted_operation,
            )
            operation_path.write_bytes(operation_bytes)

            forged_manifest = {
                **current_manifest,
                "parent_manifest_sha256": root_manifest_sha,
            }
            forged_bytes = canonical_json_bytes(forged_manifest)
            forged_sha = hashlib.sha256(forged_bytes).hexdigest()
            forged_path = owner.checkpoints.manifests / forged_sha
            forged_path.write_bytes(forged_bytes)
            forged_current = (forged_sha + "\n").encode("ascii")
            current_path.write_bytes(forged_current)
            with self.assertRaises(FieldIntelligenceError) as lineage:
                FieldIntelligenceOwner(root)
            self.assertEqual(lineage.exception.code, "HISTORY_CORRUPT")
            self.assertEqual(current_path.read_bytes(), forged_current)
            current_path.write_bytes(current_bytes)
            forged_path.unlink()

            recovered = FieldIntelligenceOwner(root)
            try:
                self.assertEqual(
                    recovered.state.state_sha256,
                    committed_state,
                )
            finally:
                recovered.close()

    def test_control_records_reject_type_confusion_without_rewrite(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            authority_path = owner.authority_path
            authority = owner._authority_control()
            authority_bytes = authority_path.read_bytes()
            revocation_path = owner.checkpoints.revocation_path
            revocation = owner.checkpoints.revocation_fence()
            revocation_bytes = revocation_path.read_bytes()
            history_path = owner.checkpoints.history_floor_path
            history = owner.checkpoints._history_floor()
            history_bytes = history_path.read_bytes()
            committed_state = owner.state.state_sha256
            owner.close()

            corruptions = {
                "authority": (
                    authority_path,
                    canonical_json_bytes(
                        {**authority, "used_grant_ids": "grant"}
                    ),
                    authority_bytes,
                    "PERSISTENCE_CORRUPT",
                ),
                "revocation": (
                    revocation_path,
                    canonical_json_bytes(
                        {**revocation, "operation_id": []}
                    ),
                    revocation_bytes,
                    "PERSISTENCE_CORRUPT",
                ),
                "history": (
                    history_path,
                    canonical_json_bytes(
                        {
                            **history,
                            "discarded_operation_ids": "old",
                        }
                    ),
                    history_bytes,
                    "HISTORY_CORRUPT",
                ),
            }
            for label, (
                path,
                corrupted_bytes,
                original_bytes,
                expected_code,
            ) in corruptions.items():
                with self.subTest(label=label):
                    path.write_bytes(corrupted_bytes)
                    with self.assertRaises(
                        FieldIntelligenceError
                    ) as failure:
                        FieldIntelligenceOwner(root)
                    self.assertEqual(
                        failure.exception.code,
                        expected_code,
                    )
                    self.assertEqual(
                        path.read_bytes(),
                        corrupted_bytes,
                    )
                    path.write_bytes(original_bytes)

            recovered = FieldIntelligenceOwner(root)
            try:
                self.assertEqual(
                    recovered.state.state_sha256,
                    committed_state,
                )
            finally:
                recovered.close()

    def test_pending_capacity_refuses_new_admission_but_allows_completion(self) -> None:
        import cassi_field_owner as persistence

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root, limits=CapacityLimits(max_pending_operations=1))
            values = {"bias": 1.0, "x": 2.0, "y": 2.0}
            source = _source("interrupted-source", values)
            committed = owner.state.state_sha256
            original_write = persistence._atomic_write

            def interrupted(path: Path, payload: bytes) -> None:
                if path.parent == owner.evidence.blobs:
                    raise OSError("simulated evidence interruption")
                original_write(path, payload)

            try:
                with patch.object(persistence, "_atomic_write", interrupted):
                    with self.assertRaises(OSError):
                        owner.admit_observation(operation_id="pending:first", source=source, values=values, context={})
                with self.assertRaises(FieldIntelligenceError) as capacity:
                    owner.admit_observation(operation_id="pending:second", source=_source("new-source", values),
                                            values=values, context={})
                self.assertEqual(capacity.exception.code, "FIELD_CAPACITY")
                self.assertEqual(owner.state.state_sha256, committed)
                self.assertEqual(owner.evidence.event_count, 0)
                owner.admit_observation(operation_id="pending:first", source=source, values=values, context={})
                self.assertEqual(owner.evidence.event_count, 1)
                result = owner.think(operation_id="pending:query", observed={"x": 3.0}, requested=("y",))
                self.assertEqual(result["status"], "supported")
            finally:
                owner.close()

    def test_closed_surface_exposes_query_and_rejects_protocol_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            owner = self._owner(Path(directory))
            values = {"bias": 1.0, "x": 2.0, "y": 2.0}
            owner.admit_observation(
                operation_id="surface:observe",
                source=_source("surface-source", values),
                values=values,
                context={},
            )
            surface = FieldIntelligenceSurface(owner)
            response = surface.handle(
                {
                    "operation": "think",
                    "params": {"operation_id": "surface:think", "observed": {"x": 3.0}, "requested": ["y"]},
                    "request_id": "surface:think",
                    "schema": RPC_SCHEMA,
                }
            )
            self.assertTrue(response["ok"])
            self.assertEqual(response["result"]["status"], "supported")
            state_before_read = owner.state.state_sha256
            projected = surface.handle(
                {
                    "operation": "query",
                    "params": {"query_id": response["result"]["query_id"]},
                    "request_id": "surface:query",
                    "schema": RPC_SCHEMA,
                }
            )
            self.assertEqual(projected["result"]["branches"], response["result"]["branches"])
            self.assertEqual(owner.state.state_sha256, state_before_read)
            with self.assertRaises(FieldIntelligenceError) as protocol:
                surface.handle(
                    {
                        "operation": "query",
                        "params": {
                            "observed": {"x": 3.0},
                            "requested": ["y"],
                            "surprise": True,
                        },
                        "request_id": "surface:drift",
                        "schema": RPC_SCHEMA,
                    }
                )
            self.assertEqual(protocol.exception.code, "INVALID_REQUEST")
            owner.close()

    def test_capacity_fails_closed_without_publishing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            limits = CapacityLimits(max_variables=1)
            with FieldIntelligenceOwner(Path(directory), limits=limits) as owner:
                owner.configure_variable("variable:1", VariableSpec("x"))
                with self.assertRaises(FieldIntelligenceError) as active:
                    FieldIntelligenceOwner(Path(directory), limits=limits)
                self.assertEqual(active.exception.code, "OWNER_ACTIVE")
                committed = owner.state.state_sha256
                with self.assertRaises(FieldIntelligenceError) as capacity:
                    owner.configure_variable("variable:2", VariableSpec("y"))
                self.assertEqual(capacity.exception.code, "FIELD_CAPACITY")
                self.assertEqual(owner.state.state_sha256, committed)
            with FieldIntelligenceOwner(Path(directory), limits=limits) as restarted:
                self.assertEqual(restarted.state.state_sha256, committed)

    def test_retained_query_workspaces_obey_publication_limits(self) -> None:
        for resource in ("workspace_bytes", "ports", "prepared_branches"):
            with self.subTest(resource=resource), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                owner = self._owner(root)
                try:
                    self._train_identity(owner)
                    prepared = owner.think(
                        operation_id="capacity:prepared",
                        observed={"x": 2.0},
                        requested=("y",),
                        ticks=4,
                    )
                    retained = owner.query(query_id=prepared["query_id"])
                    usage = owner.inspect()["capacity"]["usage"]
                    limits = replace(owner.limits, **{f"max_{resource}": usage[resource]})
                    committed = owner.state.state_sha256
                    manifest = owner.checkpoints.current_manifest_sha256
                finally:
                    owner.close()

                bounded = FieldIntelligenceOwner(root, limits=limits)
                try:
                    with self.assertRaises(FieldIntelligenceError) as capacity:
                        bounded.think(
                            operation_id="capacity:overflow",
                            observed={"x": -2.0},
                            requested=("y",),
                            ticks=4,
                        )
                    self.assertEqual(capacity.exception.code, "FIELD_CAPACITY")
                    self.assertGreater(
                        capacity.exception.details[resource]["actual"], usage[resource]
                    )
                    self.assertEqual(bounded.state.state_sha256, committed)
                    self.assertEqual(bounded.checkpoints.current_manifest_sha256, manifest)
                    self.assertEqual(bounded.query(query_id=prepared["query_id"]), retained)
                finally:
                    bounded.close()

                restarted = FieldIntelligenceOwner(root, limits=limits)
                try:
                    self.assertEqual(restarted.state.state_sha256, committed)
                    self.assertEqual(restarted.query(query_id=prepared["query_id"]), retained)
                finally:
                    restarted.close()

    @staticmethod
    def _train_identity(owner: FieldIntelligenceOwner) -> list[Mapping[str, Any]]:
        admitted: list[Mapping[str, Any]] = []
        for index, value in enumerate((-3.0, -1.0, 1.0, 3.0)):
            observation = {"bias": 1.0, "x": value, "y": value}
            admitted.append(
                owner.admit_observation(
                    operation_id=f"train:{index}",
                    source=_source(f"train-source:{index}", observation),
                    values=observation,
                    context={},
                )
            )
        return admitted

    def test_proposed_effect_response_does_not_alias_committed_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            owner = self._owner(Path(directory))
            self._train_identity(owner)
            readout = ActionReadout(
                readout_id="alias-readout",
                version=1,
                labels=("negative", "positive"),
                coefficients=({"y": -1.0}, {"y": 1.0}),
                observed_error_radius=0.01,
            )
            proposal = owner.propose_effect(
                operation_id="effect:alias",
                observed={"x": 2.0},
                readout=readout,
                target="test-world",
                scope="test",
                payload={"amount": 1},
            )
            before = owner.state.state_sha256
            proposal["prediction"]["query"]["payload"]["amount"] = 999
            self.assertEqual(
                owner.state.predictions[-1].query["payload"]["amount"],
                1,
            )
            self.assertEqual(owner.state.state_sha256, before)
            with self.assertRaises(TypeError):
                owner.state.predictions[-1].query["payload"]["amount"] = 999
            owner.close()

    def test_rejected_pending_observation_does_not_block_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            limits = CapacityLimits(max_source_bytes=8)
            source = SourceInput(
                source_id="oversized",
                content=b"123456789",
                media_type="application/octet-stream",
                codec="binary",
                observed_timestamp="oversized",
                scope="test",
                claim_category="measurement",
                fidelity="exact",
                labels=("test",),
            )
            owner = FieldIntelligenceOwner(root, limits=limits)
            with self.assertRaises(FieldIntelligenceError) as rejected:
                owner.admit_observation(
                    operation_id="oversized:direct",
                    source=source,
                    values={},
                    context={},
                )
            self.assertEqual(rejected.exception.code, "SOURCE_CAPACITY")
            self.assertEqual(list(owner.pending_path.iterdir()), [])
            owner._stage_pending(
                operation_id="oversized:legacy-pending",
                kind="observation",
                payload={
                    "context": {},
                    "derivation_roots": [],
                    "epistemic_type": "observed",
                    "event_kind": "observation",
                    "source": source.as_dict(),
                    "target_chart_ids": None,
                    "values": {},
                    "weight": 1.0,
                },
            )
            owner.close()
            restarted = FieldIntelligenceOwner(root, limits=limits)
            self.assertEqual(list(restarted.pending_path.iterdir()), [])
            failures = list((root / "pending-failures").iterdir())
            self.assertEqual(len(failures), 1)
            restarted.close()

    def test_owner_binds_assessment_to_active_future_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            owner = self._owner(Path(directory))
            historical = self._train_identity(owner)[0]
            program = FieldProgram(
                program_id="identity-program",
                version=1,
                roles=("x",),
                steps=(PrimitiveStep("identity", "y", ("x",)),),
                outputs=("y",),
            )
            owner.configure_program("program:identity", program)
            prediction = owner.begin_program_assessment(
                operation_id="assessment:begin",
                program_id=program.program_id,
                bindings={"x": 2.0},
            )["prediction"]
            historical_event_id = historical["event"]["event_id"]
            with self.assertRaises(FieldIntelligenceError) as falsified:
                owner.resolve_program_assessment(
                    operation_id="assessment:falsified",
                    program_id=program.program_id,
                    prediction_id=prediction["prediction_id"],
                    outcome={"y": 2.0},
                    event_id=historical_event_id,
                    loss_scale=10.0,
                )
            self.assertEqual(falsified.exception.code, "EVIDENCE_MISMATCH")
            with self.assertRaises(FieldIntelligenceError) as historical_error:
                owner.resolve_program_assessment(
                    operation_id="assessment:historical",
                    program_id=program.program_id,
                    prediction_id=prediction["prediction_id"],
                    outcome={"y": -3.0},
                    event_id=historical_event_id,
                    loss_scale=10.0,
                )
            self.assertEqual(historical_error.exception.code, "EVIDENCE_SEQUENCE")
            future_values = {"bias": 1.0, "x": 2.0, "y": 2.0}
            future = owner.admit_observation(
                operation_id="assessment:future",
                source=_source("assessment-future", future_values),
                values=future_values,
                context={},
            )
            owner.resolve_program_assessment(
                operation_id="assessment:resolve",
                program_id=program.program_id,
                prediction_id=prediction["prediction_id"],
                outcome={"y": 2.0},
                event_id=future["event"]["event_id"],
                loss_scale=10.0,
            )
            second = owner.admit_observation(
                operation_id="assessment:second-future",
                source=_source("assessment-second", future_values),
                values=future_values,
                context={},
            )
            with self.assertRaises(FieldIntelligenceError) as repeated:
                owner.resolve_program_assessment(
                    operation_id="assessment:repeat",
                    program_id=program.program_id,
                    prediction_id=prediction["prediction_id"],
                    outcome={"y": 2.0},
                    event_id=second["event"]["event_id"],
                    loss_scale=10.0,
                )
            self.assertEqual(repeated.exception.code, "ASSESSMENT_CONFLICT")
            owner.close()

    def test_fresh_adapter_recovers_acknowledged_effect_without_reexecution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            self._train_identity(owner)
            readout = ActionReadout(
                readout_id="restart-readout",
                version=1,
                labels=("negative", "positive"),
                coefficients=({"y": -1.0}, {"y": 1.0}),
                observed_error_radius=0.01,
            )
            proposal = owner.propose_effect(
                operation_id="effect:interrupted",
                observed={"x": 2.0},
                readout=readout,
                target="test-world",
                scope="test",
                payload={"amount": 1},
            )
            effects: list[Mapping[str, Any]] = []

            def transition(
                action: str, target: str, payload: Mapping[str, Any]
            ) -> WorldAcknowledgment:
                effects.append(
                    {"action": action, "payload": dict(payload), "target": target}
                )
                return WorldAcknowledgment(
                    acknowledgment_id="ack:interrupted",
                    operation_id="effect:interrupted",
                    status="succeeded",
                    observed_values={"x": 2.0, "y": 2.0},
                    context={},
                    source_content=b"acknowledged",
                )

            adapter = DeterministicWorldAdapter(transition)
            with patch.object(
                owner,
                "admit_acknowledgment",
                side_effect=RuntimeError("simulated owner crash"),
            ):
                with self.assertRaises(RuntimeError):
                    owner.dispatch_effect(
                        prediction_id=proposal["prediction"]["prediction_id"],
                        grant=AuthorityGrant(
                            grant_id="grant:interrupted",
                            issuer="test-host",
                            generation=0,
                            operation="effect",
                            target="test-world",
                            scope="test",
                        ),
                        adapter=adapter,
                    )
            self.assertEqual(len(effects), 1)
            owner.close()
            restarted = FieldIntelligenceOwner(root)
            fresh_adapter = DeterministicWorldAdapter(transition)
            recovered = restarted.dispatch_effect(
                prediction_id=proposal["prediction"]["prediction_id"],
                grant=AuthorityGrant(
                    grant_id="grant:interrupted",
                    issuer="test-host",
                    generation=0,
                    operation="effect",
                    target="test-world",
                    scope="test",
                ),
                adapter=fresh_adapter,
            )
            self.assertEqual(len(effects), 1)
            self.assertEqual(fresh_adapter.execute_count, 0)
            self.assertEqual(recovered["status"], "acknowledged")
            self.assertEqual(
                restarted.state.predictions[-1].status,
                "acknowledged",
            )
            restarted.close()

    def test_one_use_effect_retry_uses_binding_with_empty_adapter_journal(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            self._train_identity(owner)
            readout = ActionReadout(
                readout_id="empty-journal-readout",
                version=1,
                labels=("negative", "positive"),
                coefficients=({"y": -1.0}, {"y": 1.0}),
                observed_error_radius=0.01,
            )
            proposal = owner.propose_effect(
                operation_id="effect:empty-journal",
                observed={"x": 2.0},
                readout=readout,
                target="test-world",
                scope="test",
                payload={"amount": 7},
            )
            grant = AuthorityGrant(
                grant_id="grant:empty-journal",
                issuer="test-host",
                generation=0,
                operation="effect",
                target="test-world",
                scope="test",
            )
            effects: list[Mapping[str, Any]] = []

            def transition(
                action: str,
                target: str,
                payload: Mapping[str, Any],
            ) -> WorldAcknowledgment:
                effects.append(
                    {
                        "action": action,
                        "payload": dict(payload),
                        "target": target,
                    }
                )
                return WorldAcknowledgment(
                    acknowledgment_id="ack:empty-journal",
                    operation_id="effect:empty-journal",
                    status="succeeded",
                    observed_values={"x": 2.0, "y": 2.0},
                    context={},
                    source_content=b"empty-journal-acknowledgment",
                )

            interrupted_adapter = DeterministicWorldAdapter(transition)
            with patch.object(
                interrupted_adapter,
                "execute_once",
                side_effect=RuntimeError("crash before adapter execution"),
            ):
                with self.assertRaises(RuntimeError):
                    owner.dispatch_effect(
                        prediction_id=proposal["prediction"][
                            "prediction_id"
                        ],
                        grant=grant,
                        adapter=interrupted_adapter,
                    )
            self.assertEqual(owner.state.predictions[-1].status, "pending")
            self.assertIsNone(
                interrupted_adapter.resolve("effect:empty-journal")
            )
            owner.close()

            restarted = FieldIntelligenceOwner(root)
            fresh_adapter = DeterministicWorldAdapter(transition)
            recovered = restarted.dispatch_effect(
                prediction_id=proposal["prediction"]["prediction_id"],
                grant=grant,
                adapter=fresh_adapter,
            )
            self.assertEqual(recovered["status"], "acknowledged")
            self.assertEqual(fresh_adapter.execute_count, 1)
            self.assertEqual(len(effects), 1)
            control = json.loads(
                (root / "authority-control.json").read_bytes()
            )
            self.assertEqual(control["used_grant_bindings"], {})
            self.assertEqual(
                control["used_grant_ids"],
                ["grant:empty-journal"],
            )

            unrelated = restarted.propose_effect(
                operation_id="effect:unrelated",
                observed={"x": 2.0},
                readout=readout,
                target="test-world",
                scope="test",
                payload={"amount": 9},
            )
            with self.assertRaises(
                FieldIntelligenceError
            ) as consumed:
                restarted.dispatch_effect(
                    prediction_id=unrelated["prediction"][
                        "prediction_id"
                    ],
                    grant=grant,
                    adapter=fresh_adapter,
                )
            self.assertEqual(
                consumed.exception.code,
                "AUTHORITY_CONSUMED",
            )
            self.assertEqual(fresh_adapter.execute_count, 1)
            restarted.close()

    def test_reservation_before_pending_is_finalized_on_restart(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            self._train_identity(owner)
            readout = ActionReadout(
                readout_id="reserved-proposal-readout",
                version=1,
                labels=("negative", "positive"),
                coefficients=({"y": -1.0}, {"y": 1.0}),
                observed_error_radius=0.01,
            )
            proposal = owner.propose_effect(
                operation_id="effect:reserved-proposal",
                observed={"x": 2.0},
                readout=readout,
                target="test-world",
                scope="test",
                payload={"amount": 11},
            )
            grant = AuthorityGrant(
                grant_id="grant:reserved-proposal",
                issuer="test-host",
                generation=0,
                operation="effect",
                target="test-world",
                scope="test",
            )
            effects: list[Mapping[str, Any]] = []

            def transition(
                action: str,
                target: str,
                payload: Mapping[str, Any],
            ) -> WorldAcknowledgment:
                effects.append(
                    {
                        "action": action,
                        "payload": dict(payload),
                        "target": target,
                    }
                )
                return WorldAcknowledgment(
                    acknowledgment_id="ack:reserved-proposal",
                    operation_id="effect:reserved-proposal",
                    status="succeeded",
                    observed_values={"x": 2.0, "y": 2.0},
                    context={},
                    source_content=b"reserved-proposal-acknowledgment",
                )

            adapter = DeterministicWorldAdapter(transition)
            with patch.object(
                owner,
                "_publish_effect_pending",
                side_effect=RuntimeError("crash before pending publication"),
            ):
                with self.assertRaises(RuntimeError):
                    owner.dispatch_effect(
                        prediction_id=proposal["prediction"][
                            "prediction_id"
                        ],
                        grant=grant,
                        adapter=adapter,
                    )
            self.assertEqual(owner.state.predictions[-1].status, "proposed")
            self.assertEqual(adapter.execute_count, 0)
            owner.close()

            restarted = FieldIntelligenceOwner(root)
            self.assertEqual(
                restarted.state.predictions[-1].status,
                "pending",
            )
            fresh_adapter = DeterministicWorldAdapter(transition)
            recovered = restarted.recover_pending_effects(fresh_adapter)
            self.assertEqual(len(recovered), 1)
            self.assertEqual(recovered[0]["status"], "acknowledged")
            self.assertEqual(fresh_adapter.execute_count, 1)
            self.assertEqual(len(effects), 1)
            restarted.close()

    def test_effect_grant_binding_tampering_fails_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            self._train_identity(owner)
            readout = ActionReadout(
                readout_id="binding-tamper-readout",
                version=1,
                labels=("negative", "positive"),
                coefficients=({"y": -1.0}, {"y": 1.0}),
                observed_error_radius=0.01,
            )
            proposal = owner.propose_effect(
                operation_id="effect:binding-tamper",
                observed={"x": 2.0},
                readout=readout,
                target="test-world",
                scope="test",
                payload={"amount": 13},
            )
            adapter = DeterministicWorldAdapter(
                lambda action, target, payload: WorldAcknowledgment(
                    acknowledgment_id="ack:binding-tamper",
                    operation_id="effect:binding-tamper",
                    status="succeeded",
                    observed_values={"x": 2.0, "y": 2.0},
                    context={},
                    source_content=b"binding-tamper-acknowledgment",
                )
            )
            with patch.object(
                adapter,
                "execute_once",
                side_effect=RuntimeError("leave a bound pending effect"),
            ):
                with self.assertRaises(RuntimeError):
                    owner.dispatch_effect(
                        prediction_id=proposal["prediction"][
                            "prediction_id"
                        ],
                        grant=AuthorityGrant(
                            grant_id="grant:binding-tamper",
                            issuer="test-host",
                            generation=0,
                            operation="effect",
                            target="test-world",
                            scope="test",
                        ),
                        adapter=adapter,
                    )
            owner.close()

            authority_path = root / "authority-control.json"
            original = authority_path.read_bytes()
            for tamper in ("request", "grant-and-request"):
                with self.subTest(tamper=tamper):
                    control = json.loads(original)
                    binding = next(
                        iter(control["used_grant_bindings"].values())
                    )
                    if tamper == "request":
                        binding["request"]["payload"]["amount"] = 99
                    else:
                        binding["grant"]["scope"] = "altered"
                        binding["request"]["scope"] = "altered"
                    binding["request_sha256"] = sha256_value(
                        binding["request"]
                    )
                    authority_path.write_bytes(
                        canonical_json_bytes(control)
                    )
                    with self.assertRaises(
                        FieldIntelligenceError
                    ) as corrupt:
                        FieldIntelligenceOwner(root)
                    self.assertEqual(
                        corrupt.exception.code,
                        "PERSISTENCE_CORRUPT",
                    )
                    authority_path.write_bytes(original)
            recovered = FieldIntelligenceOwner(root)
            recovered.close()

    def test_legacy_authority_control_migrates_without_new_binding(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            owner.close()
            authority_path = root / "authority-control.json"
            authority_path.write_bytes(
                canonical_json_bytes(
                    {
                        "generation": 0,
                        "schema": "cassifi.authority-control.v1",
                        "used_grant_ids": ["grant:legacy-consumed"],
                    }
                )
            )
            migrated = FieldIntelligenceOwner(root)
            control = json.loads(authority_path.read_bytes())
            self.assertEqual(
                control,
                {
                    "generation": 0,
                    "schema": "cassifi.authority-control.v2",
                    "used_grant_bindings": {},
                    "used_grant_ids": ["grant:legacy-consumed"],
                },
            )
            migrated.close()

    def test_world_adapter_journal_and_operation_identity_fail_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrong_calls: list[Mapping[str, Any]] = []

            def wrong_transition(
                action: str,
                target: str,
                payload: Mapping[str, Any],
            ) -> WorldAcknowledgment:
                wrong_calls.append(
                    {
                        "action": action,
                        "payload": dict(payload),
                        "target": target,
                    }
                )
                return WorldAcknowledgment(
                    acknowledgment_id="ack:wrong-operation",
                    operation_id="another-effect",
                    status="succeeded",
                    observed_values={"result": 1.0},
                    context={},
                    source_content=b"wrong operation",
                )

            wrong = DeterministicWorldAdapter(wrong_transition)
            wrong.bind_durable_journal(root / "wrong-journal")
            with self.assertRaises(FieldIntelligenceError) as mismatch:
                wrong.execute_once(
                    operation_id="effect:expected",
                    action="open",
                    target="test-world",
                    payload={"amount": 1},
                )
            self.assertEqual(
                mismatch.exception.code,
                "INVALID_ACKNOWLEDGMENT",
            )
            self.assertEqual(len(wrong_calls), 1)
            self.assertEqual(wrong.execute_count, 0)
            with self.assertRaises(FieldIntelligenceError) as unknown:
                wrong.execute_once(
                    operation_id="effect:expected",
                    action="open",
                    target="test-world",
                    payload={"amount": 1},
                )
            self.assertEqual(
                unknown.exception.code,
                "EFFECT_OUTCOME_UNKNOWN",
            )
            self.assertEqual(len(wrong_calls), 1)

            seen: list[Mapping[str, Any]] = []

            def transition(
                action: str,
                target: str,
                payload: Mapping[str, Any],
            ) -> WorldAcknowledgment:
                seen.append(
                    {
                        "action": action,
                        "payload": dict(payload),
                        "target": target,
                    }
                )
                return WorldAcknowledgment(
                    acknowledgment_id="ack:journal-integrity",
                    operation_id="effect:journal-integrity",
                    status="succeeded",
                    observed_values={"result": 1.0},
                    context={"surface": "test"},
                    source_content=b"acknowledged",
                )

            adapter = DeterministicWorldAdapter(transition)
            adapter.bind_durable_journal(root / "journal")
            first = adapter.execute_once(
                operation_id="effect:journal-integrity",
                action="open",
                target="test-world",
                payload={"amount": 1},
            )
            operation_path = adapter._operation_path(
                "effect:journal-integrity"
            )
            loaded = adapter._read_record("effect:journal-integrity")
            assert loaded is not None
            record = dict(loaded[0])
            original_bytes = operation_path.read_bytes()
            wrong_acknowledgment = dict(record["acknowledgment"])
            wrong_acknowledgment["operation_id"] = "another-effect"
            corruptions = {
                "extra-field": {**record, "unexpected": True},
                "request-digest": {
                    **record,
                    "request_sha256": "0" * 64,
                },
                "acknowledgment-digest": {
                    **record,
                    "acknowledgment_sha256": "0" * 64,
                },
                "acknowledgment-operation": {
                    **record,
                    "acknowledgment": wrong_acknowledgment,
                    "acknowledgment_sha256": sha256_value(
                        wrong_acknowledgment
                    ),
                },
            }
            for label, corrupted in corruptions.items():
                with self.subTest(label=label):
                    operation_path.write_bytes(
                        canonical_json_bytes(corrupted)
                    )
                    corrupted_bytes = operation_path.read_bytes()
                    with self.assertRaises(
                        FieldIntelligenceError
                    ) as invalid:
                        adapter.resolve("effect:journal-integrity")
                    self.assertEqual(
                        invalid.exception.code,
                        "PERSISTENCE_CORRUPT",
                    )
                    self.assertEqual(
                        operation_path.read_bytes(),
                        corrupted_bytes,
                    )
                    self.assertEqual(adapter.execute_count, 1)
                    self.assertEqual(len(seen), 1)
                    fresh = DeterministicWorldAdapter(transition)
                    with self.assertRaises(
                        FieldIntelligenceError
                    ) as startup_invalid:
                        fresh.bind_durable_journal(root / "journal")
                    self.assertEqual(
                        startup_invalid.exception.code,
                        "PERSISTENCE_CORRUPT",
                    )
                    self.assertEqual(fresh.execute_count, 0)
                    self.assertEqual(len(seen), 1)
                    operation_path.write_bytes(original_bytes)

            replay = adapter.execute_once(
                operation_id="effect:journal-integrity",
                action="open",
                target="test-world",
                payload={"amount": 1},
            )
            self.assertEqual(replay, first)
            self.assertEqual(adapter.execute_count, 1)
            self.assertEqual(len(seen), 1)
            with self.assertRaises(FieldIntelligenceError) as conflict:
                adapter.execute_once(
                    operation_id="effect:journal-integrity",
                    action="open",
                    target="test-world",
                    payload={"amount": 2},
                )
            self.assertEqual(
                conflict.exception.code,
                "OPERATION_CONFLICT",
            )

    def test_committed_result_schema_fails_closed_before_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            owner = self._owner(Path(directory))
            try:
                request = {
                    "expected_state_sha256": None,
                    "source_enabled": True,
                    "ticks": 1,
                }
                successor, resonance_receipt = owner.atlas.advance(
                    owner.state,
                    ticks=1,
                    source_enabled=True,
                )
                owner._publish(
                    operation_id="advance:malformed-result",
                    successor=successor,
                    event_id=None,
                    transition={
                        "expected_state_sha256": None,
                        "kind": "advance",
                        "request": request,
                        "request_sha256": sha256_value(request),
                        "resonance_receipt": dict(resonance_receipt),
                        "result": {
                            "resonance_receipt": "not-an-object"
                        },
                        "source_enabled": True,
                        "ticks": 1,
                    },
                )
                committed_state = owner.state.state_sha256
                with self.assertRaises(
                    FieldIntelligenceError
                ) as malformed:
                    owner.advance(
                        "advance:malformed-result",
                        ticks=1,
                        source_enabled=True,
                    )
                self.assertEqual(
                    malformed.exception.code,
                    "CHECKPOINT_CORRUPT",
                )
                self.assertEqual(
                    owner.state.state_sha256,
                    committed_state,
                )
            finally:
                owner.close()

    def test_replay_rejects_missing_request_digest_and_tampered_results(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            owner = self._owner(Path(directory))
            try:
                self._train_identity(owner)
                readout = ActionReadout(
                    readout_id="replay-integrity-readout",
                    version=1,
                    labels=("negative", "positive"),
                    coefficients=({"y": -1.0}, {"y": 1.0}),
                    observed_error_radius=0.01,
                )

                publish = owner._publish

                def drop_request_digest(**kwargs: Any) -> Any:
                    transition = dict(kwargs["transition"])
                    transition.pop("request_sha256")
                    kwargs["transition"] = transition
                    return publish(**kwargs)

                with patch.object(
                    owner,
                    "_publish",
                    side_effect=drop_request_digest,
                ):
                    owner.think(
                        operation_id="think:missing-request-digest",
                        observed={"x": 2.0},
                        requested=("y",),
                    )
                committed = owner.state.state_sha256
                with self.assertRaises(FieldIntelligenceError) as missing_digest:
                    owner.think(
                        operation_id="think:missing-request-digest",
                        observed={"x": 2.0},
                        requested=("y",),
                    )
                self.assertEqual(
                    missing_digest.exception.code,
                    "CHECKPOINT_CORRUPT",
                )
                self.assertEqual(owner.state.state_sha256, committed)

                def corrupt_proposal_status(**kwargs: Any) -> Any:
                    transition = dict(kwargs["transition"])
                    if transition.get("kind") == "effect-proposed":
                        result = dict(transition["result"])
                        result["status"] = "acknowledged"
                        transition["result"] = result
                    kwargs["transition"] = transition
                    return publish(**kwargs)

                proposal_arguments = {
                    "operation_id": "effect:tampered-proposal-result",
                    "observed": {"x": 2.0},
                    "readout": readout,
                    "target": "test-world",
                    "scope": "test",
                    "payload": {"amount": 1},
                }
                with patch.object(
                    owner,
                    "_publish",
                    side_effect=corrupt_proposal_status,
                ):
                    owner.propose_effect(**proposal_arguments)
                committed = owner.state.state_sha256
                with self.assertRaises(
                    FieldIntelligenceError
                ) as corrupt_proposal:
                    owner.propose_effect(**proposal_arguments)
                self.assertEqual(
                    corrupt_proposal.exception.code,
                    "CHECKPOINT_CORRUPT",
                )
                self.assertEqual(owner.state.state_sha256, committed)

                proposal = owner.propose_effect(
                    operation_id="effect:tampered-acknowledgment-result",
                    observed={"x": 2.0},
                    readout=readout,
                    target="test-world",
                    scope="test",
                    payload={"amount": 1},
                )
                acknowledgment = WorldAcknowledgment(
                    acknowledgment_id="ack:tampered-result",
                    operation_id="effect:tampered-acknowledgment-result",
                    status="succeeded",
                    observed_values={"x": 2.0, "y": 2.0},
                    context={},
                    source_content=b"acknowledged",
                )

                def corrupt_acknowledgment_id(**kwargs: Any) -> Any:
                    transition = dict(kwargs["transition"])
                    if transition.get("kind") == "action-outcome":
                        result = dict(transition["result"])
                        result["acknowledgment_id"] = "ack:forged"
                        transition["result"] = result
                    kwargs["transition"] = transition
                    return publish(**kwargs)

                with patch.object(
                    owner,
                    "_publish",
                    side_effect=corrupt_acknowledgment_id,
                ):
                    owner.admit_acknowledgment(
                        prediction_id=proposal["prediction"]["prediction_id"],
                        acknowledgment=acknowledgment,
                    )
                committed = owner.state.state_sha256
                with self.assertRaises(
                    FieldIntelligenceError
                ) as corrupt_acknowledgment:
                    owner.admit_acknowledgment(
                        prediction_id=proposal["prediction"]["prediction_id"],
                        acknowledgment=acknowledgment,
                    )
                self.assertEqual(
                    corrupt_acknowledgment.exception.code,
                    "CHECKPOINT_CORRUPT",
                )
                self.assertEqual(owner.state.state_sha256, committed)
            finally:
                owner.close()
    def test_acknowledgment_replay_binds_event_and_learning_semantics(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            owner = self._owner(Path(directory))
            try:
                self._train_identity(owner)
                prior_event_id = owner.evidence.all_event_ids()[0]
                readout = ActionReadout(
                    readout_id="outcome-semantics-readout",
                    version=1,
                    labels=("negative", "positive"),
                    coefficients=({"y": -1.0}, {"y": 1.0}),
                    observed_error_radius=0.01,
                )
                publish = owner._publish
                for label in (
                    "event-id",
                    "learning",
                    "attribution-candidates",
                ):
                    with self.subTest(label=label):
                        operation_id = f"effect:tampered-{label}"
                        proposal = owner.propose_effect(
                            operation_id=operation_id,
                            observed={"x": 2.0},
                            readout=readout,
                            target="test-world",
                            scope="test",
                            payload={"label": label},
                        )
                        acknowledgment = WorldAcknowledgment(
                            acknowledgment_id=f"ack:tampered-{label}",
                            operation_id=operation_id,
                            status="succeeded",
                            observed_values={"x": 2.0, "y": 2.0},
                            context={},
                            source_content=label.encode("utf-8"),
                        )

                        def corrupt_outcome(**kwargs: Any) -> Any:
                            transition = dict(kwargs["transition"])
                            if label == "event-id":
                                kwargs["event_id"] = prior_event_id
                            elif label == "learning":
                                transition["learning"] = {
                                    "forged": True
                                }
                            else:
                                transition["attribution_candidates"] = [
                                    "sensor-error"
                                ]
                            kwargs["transition"] = transition
                            return publish(**kwargs)

                        with patch.object(
                            owner,
                            "_publish",
                            side_effect=corrupt_outcome,
                        ):
                            owner.admit_acknowledgment(
                                prediction_id=proposal["prediction"][
                                    "prediction_id"
                                ],
                                acknowledgment=acknowledgment,
                            )
                        committed = owner.state.state_sha256
                        with self.assertRaises(
                            FieldIntelligenceError
                        ) as rejected:
                            owner.admit_acknowledgment(
                                prediction_id=proposal["prediction"][
                                    "prediction_id"
                                ],
                                acknowledgment=acknowledgment,
                            )
                        self.assertEqual(
                            rejected.exception.code,
                            "CHECKPOINT_CORRUPT",
                        )
                        self.assertEqual(
                            owner.state.state_sha256,
                            committed,
                        )
            finally:
                owner.close()

    def test_acknowledgment_replay_rejects_missing_tampered_and_rebound_events(
        self,
    ) -> None:
        for label in ("missing", "identity", "rebound"):
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as directory:
                    owner = self._owner(Path(directory))
                    try:
                        self._train_identity(owner)
                        prior_event_id = owner.evidence.all_event_ids()[0]
                        readout = ActionReadout(
                            readout_id=f"event-closure-{label}",
                            version=1,
                            labels=("negative", "positive"),
                            coefficients=({"y": -1.0}, {"y": 1.0}),
                            observed_error_radius=0.01,
                        )
                        operation_id = f"effect:event-closure-{label}"
                        proposal = owner.propose_effect(
                            operation_id=operation_id,
                            observed={"x": 2.0},
                            readout=readout,
                            target="test-world",
                            scope="test",
                            payload={"label": label},
                        )
                        acknowledgment = WorldAcknowledgment(
                            acknowledgment_id=f"ack:event-closure-{label}",
                            operation_id=operation_id,
                            status="succeeded",
                            observed_values={"x": 2.0, "y": 2.0},
                            context={},
                            source_content=label.encode("utf-8"),
                        )
                        owner.admit_acknowledgment(
                            prediction_id=proposal["prediction"][
                                "prediction_id"
                            ],
                            acknowledgment=acknowledgment,
                        )
                        committed = owner.state.state_sha256
                        journal_operation_id = f"ack:{operation_id}"
                        outcome_event = owner.evidence.event_for_operation(
                            journal_operation_id
                        )
                        if outcome_event is None:
                            self.fail("acknowledgment event was not persisted")
                        event_path = (
                            owner.evidence.events / outcome_event.event_id
                        )
                        if label == "missing":
                            event_path.unlink()
                        elif label == "identity":
                            event = json.loads(event_path.read_bytes())
                            event["logical_sequence"] += 1
                            event_path.write_bytes(
                                canonical_json_bytes(event)
                            )
                        else:
                            prior_event = owner.evidence.event(
                                prior_event_id
                            )
                            index = json.loads(
                                owner.evidence.index_path.read_bytes()
                            )
                            index["operation_events"][
                                journal_operation_id
                            ] = prior_event.event_id
                            index["operation_events"][
                                prior_event.operation_id
                            ] = outcome_event.event_id
                            owner.evidence._save_index(index)
                        with self.assertRaises(
                            FieldIntelligenceError
                        ) as rejected:
                            owner.admit_acknowledgment(
                                prediction_id=proposal["prediction"][
                                    "prediction_id"
                                ],
                                acknowledgment=acknowledgment,
                            )
                        self.assertEqual(
                            rejected.exception.code,
                            "CHECKPOINT_CORRUPT",
                        )
                        self.assertEqual(
                            owner.state.state_sha256,
                            committed,
                        )
                    finally:
                        owner.close()

    def test_effect_replays_bind_complete_requests_and_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            owner = self._owner(Path(directory))
            try:
                self._train_identity(owner)
                readout = ActionReadout(
                    readout_id="replay-readout",
                    version=1,
                    labels=("negative", "positive"),
                    coefficients=({"y": -1.0}, {"y": 1.0}),
                    observed_error_radius=0.01,
                )
                arguments = {
                    "operation_id": "effect:exact-replay",
                    "observed": {"x": 2.0},
                    "readout": readout,
                    "target": "test-world",
                    "scope": "test",
                    "payload": {"amount": 1},
                }
                proposal = owner.propose_effect(**arguments)
                proposed_state = owner.state.state_sha256
                proposal_replay = owner.propose_effect(**arguments)
                self.assertTrue(
                    proposal_replay["receipt"]["replayed"]
                )
                self.assertEqual(
                    proposal_replay["decision"],
                    proposal["decision"],
                )
                self.assertEqual(
                    proposal_replay["prediction"],
                    proposal["prediction"],
                )
                self.assertEqual(
                    owner.state.state_sha256,
                    proposed_state,
                )
                with self.assertRaises(
                    FieldIntelligenceError
                ) as proposal_conflict:
                    owner.propose_effect(
                        **arguments,
                        task_feasible=False,
                    )
                self.assertEqual(
                    proposal_conflict.exception.code,
                    "OPERATION_CONFLICT",
                )
                acknowledgment = WorldAcknowledgment(
                    acknowledgment_id="ack:exact-replay",
                    operation_id="effect:exact-replay",
                    status="succeeded",
                    observed_values={"x": 2.0, "y": 2.0},
                    context={},
                    source_content=canonical_json_bytes(
                        {
                            "action": "positive",
                            "payload": {"amount": 1},
                            "target": "test-world",
                        }
                    ),
                )
                admitted = owner.admit_acknowledgment(
                    prediction_id=proposal["prediction"][
                        "prediction_id"
                    ],
                    acknowledgment=acknowledgment,
                )
                acknowledged_state = owner.state.state_sha256
                acknowledgment_replay = owner.admit_acknowledgment(
                    prediction_id=proposal["prediction"][
                        "prediction_id"
                    ],
                    acknowledgment=acknowledgment,
                )
                self.assertEqual(
                    acknowledgment_replay["status"],
                    "replayed",
                )
                self.assertTrue(
                    acknowledgment_replay["receipt"]["replayed"]
                )
                self.assertEqual(
                    acknowledgment_replay["prediction"],
                    admitted["prediction"],
                )
                self.assertEqual(
                    owner.state.state_sha256,
                    acknowledged_state,
                )
                with self.assertRaises(
                    FieldIntelligenceError
                ) as acknowledgment_conflict:
                    owner.admit_acknowledgment(
                        prediction_id=proposal["prediction"][
                            "prediction_id"
                        ],
                        acknowledgment=acknowledgment,
                        attribution_candidates=("sensor-error",),
                    )
                self.assertEqual(
                    acknowledgment_conflict.exception.code,
                    "OPERATION_CONFLICT",
                )
                proposal_after_outcome = owner.propose_effect(
                    **arguments
                )
                self.assertEqual(
                    proposal_after_outcome["status"],
                    "acknowledged",
                )
                self.assertTrue(
                    proposal_after_outcome["receipt"]["replayed"]
                )
                self.assertEqual(
                    proposal_after_outcome["prediction"],
                    admitted["prediction"],
                )
            finally:
                owner.close()

    def test_forget_replay_binds_preview_and_normalized_targets(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            owner = self._owner(Path(directory))
            try:
                self._train_identity(owner)
                revision_id = sorted(
                    owner.evidence.active_revision_ids()
                )[0]
                preview = owner.preview_forget((revision_id,))
                target = sha256_value([revision_id])
                grant = AuthorityGrant(
                    grant_id="grant:forget-replay",
                    issuer="test-host",
                    generation=0,
                    operation="forget",
                    target=target,
                    scope="test",
                )
                forgotten = owner.forget(
                    operation_id="forget:exact-replay",
                    preview_id=preview["preview_id"],
                    revision_ids=(revision_id,),
                    grant=grant,
                    scope="test",
                )
                committed_state = owner.state.state_sha256
                replay = owner.forget(
                    operation_id="forget:exact-replay",
                    preview_id=preview["preview_id"],
                    revision_ids=(revision_id, revision_id),
                    grant=grant,
                    scope="test",
                )
                self.assertTrue(replay["receipt"]["replayed"])
                self.assertEqual(
                    {
                        key: value
                        for key, value in replay.items()
                        if key != "receipt"
                    },
                    {
                        key: value
                        for key, value in forgotten.items()
                        if key != "receipt"
                    },
                )
                self.assertEqual(
                    owner.state.state_sha256,
                    committed_state,
                )
                with self.assertRaises(
                    FieldIntelligenceError
                ) as conflict:
                    owner.forget(
                        operation_id="forget:exact-replay",
                        preview_id="0" * 64,
                        revision_ids=(revision_id,),
                        grant=grant,
                        scope="test",
                    )
                self.assertEqual(
                    conflict.exception.code,
                    "OPERATION_CONFLICT",
                )
                self.assertEqual(
                    owner.state.state_sha256,
                    committed_state,
                )
            finally:
                owner.close()

    def test_existing_event_identity_tampering_cannot_publish(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            values = {"bias": 1.0, "x": 2.0, "y": 2.0}
            source = _source("existing-event-tamper", values)
            try:
                with patch.object(
                    owner,
                    "_publish",
                    side_effect=OSError(
                        "simulated interruption before checkpoint"
                    ),
                ):
                    with self.assertRaises(OSError):
                        owner.admit_observation(
                            operation_id="observation:event-tamper",
                            source=source,
                            values=values,
                            context={},
                        )
                event = owner.evidence.event_for_operation(
                    "observation:event-tamper"
                )
                self.assertIsNotNone(event)
                assert event is not None
                event_path = owner.evidence.events / event.event_id
                event_record = event.as_dict()
                tampered_identity = {
                    key: value
                    for key, value in event_record.items()
                    if key not in {"event_id", "schema"}
                }
                tampered_identity["logical_sequence"] = (
                    event.logical_sequence + 1
                )
                tampered_record = {
                    **event_record,
                    "event_id": sha256_value(tampered_identity),
                    "logical_sequence": event.logical_sequence + 1,
                }
                event_path.write_bytes(
                    canonical_json_bytes(tampered_record)
                )
                tampered_bytes = event_path.read_bytes()
                committed_state = owner.state.state_sha256
                current_bytes = owner.checkpoints.current_path.read_bytes()
                pending_path = next(owner.pending_path.iterdir())
                pending_bytes = pending_path.read_bytes()
                with self.assertRaises(
                    FieldIntelligenceError
                ) as corrupt:
                    owner.admit_observation(
                        operation_id="observation:event-tamper",
                        source=source,
                        values=values,
                        context={},
                    )
                self.assertEqual(
                    corrupt.exception.code,
                    "PERSISTENCE_CORRUPT",
                )
                self.assertEqual(
                    owner.state.state_sha256,
                    committed_state,
                )
                self.assertEqual(
                    owner.checkpoints.current_path.read_bytes(),
                    current_bytes,
                )
                self.assertEqual(
                    pending_path.read_bytes(),
                    pending_bytes,
                )
                self.assertEqual(
                    event_path.read_bytes(),
                    tampered_bytes,
                )
            finally:
                owner.close()

    def test_evidence_index_source_and_event_corruption_fail_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner = self._owner(root)
            values = {"bias": 1.0, "x": 2.0, "y": 2.0}
            admitted = owner.admit_observation(
                operation_id="evidence:integrity",
                source=_source("evidence-integrity-source", values),
                values=values,
                context={},
            )
            committed_state = owner.state.state_sha256
            revision_id = admitted["source"]["revision_id"]
            event_id = admitted["event"]["event_id"]
            expected_recall = owner.exact_recall(
                revision_id=revision_id,
                allowed_labels=frozenset({"test"}),
            )

            source_path = owner.evidence.sources / revision_id
            source_record = owner.evidence.source(revision_id).as_dict()
            source_bytes = source_path.read_bytes()
            blob_path = (
                owner.evidence.blobs
                / source_record["object_sha256"]
            )
            blob_bytes = blob_path.read_bytes()
            event_path = owner.evidence.events / event_id
            event_record = owner.evidence.event(event_id).as_dict()
            event_bytes = event_path.read_bytes()
            index_path = owner.evidence.index_path
            index = owner.evidence._index()
            index_bytes = index_path.read_bytes()
            owner.close()

            corruptions = {
                "source-record": (
                    source_path,
                    canonical_json_bytes(
                        {**source_record, "scope": "altered-scope"}
                    ),
                    source_bytes,
                ),
                "source-content": (
                    blob_path,
                    bytes([blob_bytes[0] ^ 1]) + blob_bytes[1:],
                    blob_bytes,
                ),
                "event-record": (
                    event_path,
                    canonical_json_bytes(
                        {
                            **event_record,
                            "logical_sequence": (
                                event_record["logical_sequence"] + 1
                            ),
                        }
                    ),
                    event_bytes,
                ),
                "evidence-index": (
                    index_path,
                    canonical_json_bytes(
                        {**index, "active_revision_ids": []}
                    ),
                    index_bytes,
                ),
            }
            expected_codes = {
                "source-record": "PERSISTENCE_CORRUPT",
                "source-content": "SOURCE_CORRUPT",
                "event-record": "PERSISTENCE_CORRUPT",
                "evidence-index": "PERSISTENCE_CORRUPT",
            }
            for label, (
                path,
                corrupted_bytes,
                original_bytes,
            ) in corruptions.items():
                with self.subTest(label=label):
                    path.write_bytes(corrupted_bytes)
                    with self.assertRaises(
                        FieldIntelligenceError
                    ) as failure:
                        FieldIntelligenceOwner(root)
                    self.assertEqual(
                        failure.exception.code,
                        expected_codes[label],
                    )
                    self.assertEqual(
                        path.read_bytes(),
                        corrupted_bytes,
                    )
                    path.write_bytes(original_bytes)

            missing_records = (
                ("source-missing", source_path, source_bytes, "SOURCE_MISSING"),
                ("event-missing", event_path, event_bytes, "EVENT_NOT_FOUND"),
            )
            for label, path, original_bytes, expected_code in missing_records:
                with self.subTest(label=label):
                    path.unlink()
                    with self.assertRaises(
                        FieldIntelligenceError
                    ) as failure:
                        FieldIntelligenceOwner(root)
                    self.assertEqual(failure.exception.code, expected_code)
                    self.assertFalse(path.exists())
                    path.write_bytes(original_bytes)

            recovered = FieldIntelligenceOwner(root)
            try:
                self.assertEqual(
                    recovered.state.state_sha256,
                    committed_state,
                )
                self.assertEqual(
                    recovered.exact_recall(
                        revision_id=revision_id,
                        allowed_labels=frozenset({"test"}),
                    ),
                    expected_recall,
                )
            finally:
                recovered.close()

    def test_total_evidence_capacity_covers_events_on_existing_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            limits = CapacityLimits(
                max_source_bytes=512,
                max_total_evidence_bytes=2_500,
            )
            owner = self._owner(Path(directory), limits=limits)
            source = _source(
                "shared-capacity",
                {"bias": 1.0, "x": 1.0, "y": 1.0},
            )
            rejected = False
            for index in range(32):
                try:
                    owner.admit_observation(
                        operation_id=f"capacity:event:{index}",
                        source=source,
                        values={"bias": 1.0, "x": 1.0, "y": 1.0},
                        context={},
                    )
                except FieldIntelligenceError as exc:
                    self.assertEqual(exc.code, "EVIDENCE_CAPACITY")
                    rejected = True
                    break
            self.assertTrue(rejected)
            self.assertLessEqual(
                owner.evidence.physical_bytes(),
                limits.max_total_evidence_bytes,
            )
            self.assertEqual(list(owner.pending_path.iterdir()), [])
            owner.close()


if __name__ == "__main__":
    unittest.main()
