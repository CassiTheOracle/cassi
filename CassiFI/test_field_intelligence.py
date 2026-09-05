from __future__ import annotations

import hashlib
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
        before = state.encode()
        query = atlas.query(
            state,
            observed={"destination": 6.0, "source": 2.0},
            requested=("displacement", "left_score", "right_score"),
            context={"domain": "line"},
            method="direct",
        )
        self.assertEqual(query.status, "supported")
        self.assertEqual(state.encode(), before)
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

    def test_matrix_free_matches_reference_and_respects_iteration_failure(self) -> None:
        atlas, state, _, _ = _base_atlas()
        arguments = {
            "observed": {"destination": 6.0, "source": 2.0},
            "requested": ("displacement", "left_score", "right_score"),
            "context": {"domain": "line"},
        }
        direct = atlas.query(state, **arguments, method="direct")
        implicit = atlas.query(
            state, **arguments, method="matrix-free", tolerance=1e-11, max_iterations=64
        )
        self.assertEqual(implicit.status, "supported")
        for variable in arguments["requested"]:
            self.assertAlmostEqual(
                direct.branches[0].values[variable],
                implicit.branches[0].values[variable],
                places=7,
            )
        exhausted = atlas.query(
            state,
            **arguments,
            method="matrix-free",
            tolerance=1e-30,
            max_iterations=1,
        )
        self.assertEqual(exhausted.status, "unresolved")
        self.assertIn("search-exhausted", exhausted.branches[0].obligations)

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
        result = atlas.query(state, observed={"x": 2.0}, requested=("y",))
        self.assertEqual(result.status, "alternatives")
        predictions = sorted(round(row.values["y"], 3) for row in result.branches)
        self.assertEqual(predictions, [-2.0, 2.0])

    def test_partial_and_hypothetical_values_cannot_teach_memory(self) -> None:
        atlas, state, _, _ = _base_atlas()
        with self.assertRaisesRegex(FieldIntelligenceError, "fully observed") as partial:
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
        result = atlas.query(state, observed={"x": 2.0}, requested=("y",))
        self.assertEqual(result.status, "supported")
        self.assertLess(result.branches[0].values["y"], -1.0)
        restored = AtlasState.decode(state.encode())
        self.assertEqual(restored.encode(), state.encode())
        self.assertEqual(
            restored.chart("contextual").learning_mode,
            "contextual",
        )

    def test_constraints_reject_inconsistent_commitment(self) -> None:
        atlas, state, _, _ = _base_atlas()
        result = atlas.query(
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
        expected = atlas.query(
            state,
            observed={"source": 2.0, "destination": 6.0},
            requested=("displacement",),
        ).as_dict()
        exposed = state.chart("geometry").numeric_field
        exposed.zero_()
        self.assertEqual(state.encode(), before)
        self.assertEqual(
            atlas.query(
                state,
                observed={"source": 2.0, "destination": 6.0},
                requested=("displacement",),
            ).as_dict(),
            expected,
        )

    def test_matrix_free_response_must_converge_with_primal(self) -> None:
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
        result = atlas.query(
            state,
            observed={"x": 0.0},
            requested=("y", "z"),
            method="matrix-free",
            max_iterations=1,
        )
        self.assertEqual(result.status, "unresolved")
        self.assertFalse(result.branches[0].numerical_settled)
        self.assertIn("response-residual", result.branches[0].obligations)

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
        result = atlas.query(state, observed={"y": 20.0}, requested=("x",))
        self.assertEqual(result.status, "unresolved")
        self.assertEqual(result.branches[0].status, "infeasible")
        self.assertIn("inferred-domain", result.branches[0].obligations)

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
        self.assertEqual(promoted.steps[0].operation, "subtract")
        self.assertEqual(promoted.steps[0].inputs, ("destination", "source"))
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
            query = owner.query(observed={"x": 2.0}, requested=("y",))
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
            with self.assertRaises(FieldIntelligenceError):
                restarted.exact_recall(
                    revision_id=revision_ids[0],
                    allowed_labels=frozenset({"test"}),
                )
            remaining = restarted.query(observed={"x": 2.0}, requested=("y",))
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
                recovered.query(observed={"x": 3.0}, requested=("y",))["status"],
                "supported",
            )
            self.assertEqual(recovered.evidence.event_count, 1)
            self.assertEqual(list(recovered.pending_path.iterdir()), [])
            recovered.close()

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
                    "operation": "query",
                    "params": {"observed": {"x": 3.0}, "requested": ["y"]},
                    "request_id": "surface:query",
                    "schema": RPC_SCHEMA,
                }
            )
            self.assertTrue(response["ok"])
            self.assertEqual(response["result"]["status"], "supported")
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
            owner = FieldIntelligenceOwner(Path(directory), limits=limits)
            owner.configure_variable("variable:1", VariableSpec("x"))
            with self.assertRaises(FieldIntelligenceError) as active:
                FieldIntelligenceOwner(Path(directory), limits=limits)
            self.assertEqual(active.exception.code, "OWNER_ACTIVE")
            committed = owner.state.state_sha256
            with self.assertRaises(FieldIntelligenceError) as capacity:
                owner.configure_variable("variable:2", VariableSpec("y"))
            self.assertEqual(capacity.exception.code, "FIELD_CAPACITY")
            self.assertEqual(owner.state.state_sha256, committed)
            owner.close()
            restarted = FieldIntelligenceOwner(Path(directory), limits=limits)
            self.assertEqual(restarted.state.state_sha256, committed)

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
            recovered = restarted.recover_pending_effects(fresh_adapter)
            self.assertEqual(len(effects), 1)
            self.assertEqual(recovered[0]["status"], "acknowledged")
            self.assertEqual(
                restarted.state.predictions[-1].status,
                "acknowledged",
            )
            restarted.close()

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
