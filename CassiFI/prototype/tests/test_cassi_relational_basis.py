from copy import deepcopy

import pytest

from cassi_counterflow_runtime import DerivedCounterflowRuntime
from cassi_qi_field import QiFieldError
from cassi_relational_basis import (
    RELATION_ATOM_SCHEMA,
    RelationAtoms,
    RelationEntity,
)
from run_learned_relational_basis import run_field_selected_relational_basis
from run_relational_stress_tests import run_relational_stress_tests


def test_field_selects_relative_basis_and_composes_renamed_holdouts() -> None:
    result = run_field_selected_relational_basis()

    assert result["result"] == "FIELD_SELECTED_RELATIONAL_BASIS_OK"
    assert result["claim"] == "field-selected relational basis discovery"
    assert result["selected_basis"] == "target_minus_self"
    assert result["selection_margin"] > 0.4
    assert result["selection_evidence_field_owned"] is True
    assert result["caller_supplied_verdicts"] is False
    assert result["training_executions"] == 16
    assert result["training_identity_count"] == 16
    assert result["selection_identity_count"] == 8

    holdouts = result["holdouts"]
    assert holdouts["successes"] == holdouts["count"] == 32
    assert holdouts["renamed_identities"] == 32
    assert holdouts["permuted_entity_orders"] == 16
    assert holdouts["role_binding_successes"] == 32
    assert holdouts["role_margin_min"] > 0.13
    assert holdouts["constraint_residual_max"] < 0.005
    assert len(holdouts["first_exact_revision"]) == 64
    assert len(holdouts["last_exact_revision"]) == 64

    assert result["checkpoint_restart_exact"] is True
    assert result["field_memory_frozen_during_inference"] is True
    assert result["evidence_ablation_status"] == "no_eligible_basis"
    assert result["operator_ablation_status"] == "exhausted"
    assert result["boundary_case_count"] == 4
    assert result["boundary_mean_residual"] > 0.04
    assert result["boundary_supported"] is False
    assert result["live_provider_fallback"] is False
    assert result["teacher_or_model_calls"] == 0


def test_relation_atom_schema_is_exact_and_hash_bound() -> None:
    atoms = RelationAtoms(
        world_id="world.schema-test",
        episode_id="episode.schema-test",
        state_sha256="a" * 64,
        regime="interior",
        entities=(
            RelationEntity("renamed-self", -0.25, 0.125),
            RelationEntity("renamed-target", 0.5, -0.375),
        ),
    )
    payload = atoms.payload()

    assert payload["schema"] == RELATION_ATOM_SCHEMA
    assert RelationAtoms.from_payload(payload) == atoms

    tampered = deepcopy(payload)
    tampered["entities"][0]["x"] += 0.125
    with pytest.raises(QiFieldError, match="hash mismatch"):
        RelationAtoms.from_payload(tampered)

    caller_verdict = deepcopy(payload)
    caller_verdict["verdict"] = "selected"
    with pytest.raises(QiFieldError, match="fields mismatch"):
        RelationAtoms.from_payload(caller_verdict)

    with pytest.raises(QiFieldError, match="finite numbers"):
        RelationEntity("bad-coordinate", True, 0.0)

    with pytest.raises(QiFieldError, match="counterflow request keys are invalid"):
        DerivedCounterflowRuntime().plan(
            {"mode": "plan", **payload},
            primary_field_sha256="b" * 64,
        )


def test_relational_stress_controls_expose_the_generative_gap() -> None:
    result = run_relational_stress_tests()

    assert result["result"] == "RELATIONAL_STRESS_TESTS_OK"
    assert result["claim"] == "defined relational stress testing"
    assert result["selected_basis"] == "target_minus_self"

    moving = result["moving_targets"]
    assert moving["velocity_max"] == 0.018
    assert moving["with_two_intermediate_constraints"]["exact_revisions"] == 24
    assert moving["with_one_intermediate_constraint"]["exact_revisions"] == 0
    assert moving["endpoint_only"]["exact_revisions"] == 0
    assert moving["stationary_endpoint_control"]["exact_revisions"] == 0

    noise = result["coordinate_noise"]
    assert [item["amplitude"] for item in noise] == [
        0.0,
        0.002,
        0.01,
        0.015,
        0.02,
        0.025,
        0.03,
        0.06,
    ]
    assert [item["exact_revisions"] for item in noise] == [
        16,
        16,
        16,
        13,
        9,
        4,
        1,
        0,
    ]
    assert [item["settled"] for item in noise] == [
        16,
        16,
        16,
        13,
        9,
        4,
        1,
        0,
    ]

    distractors = result["distractors"]
    assert distractors["diagnostic_target_selections"] == 24
    assert distractors["indistinguishable_correct"] == 6
    assert distractors["indistinguishable_false_confidence"] == 10
    assert distractors["indistinguishable_abstentions"] == 0
    assert distractors["hidden_relevance_observable"] is False

    passive = result["passive_roles"]
    assert passive["passive_correct"] == 8
    assert passive["passive_wrong"] == 8
    assert passive["passive_abstentions"] == 16
    assert passive["interventional_correct"] == 24
    assert passive["by_quadrant"]["northeast"]["interventional_correct"] == 8
    assert passive["by_quadrant"]["southwest"]["interventional_correct"] == 0

    candidates = result["experimental_candidates"]
    assert candidates["candidate_count"] == 3
    assert candidates["selected_basis"] == "distance_bearing"
    assert candidates["selection_margin"] > 0.001
    assert candidates["checkpoint_restart_exact"] is True
    for outcome in candidates["boundary_composition"].values():
        assert outcome["exact_revisions"] == 0
        assert outcome["action_sequences_exact"] == 0
    assert candidates["boundary_composition"]["distance_bearing"][
        "false_settlements"
    ] == 12

    assert result["operator_ablation"]["status"] == "exhausted"
    assert result["operator_ablation"]["exact_revision"] is False
    assert result["checkpoint_restart_exact"] is True
    assert result["field_memory_frozen"] is True
    assert result["teacher_or_model_calls"] == 0
    assert result["provider_integration"] is False
