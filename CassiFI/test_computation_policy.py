"""Focused semantic, budget, and persistence checks for the computation policy."""

from __future__ import annotations

import base64
import copy
import json
import numpy as np

import pytest
import cassi_computation_policy as computation_policy

from cassi_computation_policy import (
    LEGACY_SCHEMA,
    METHODS,
    PREVIOUS_SCHEMA,
    V3_SCHEMA,
    PolicyError,
    PolicyState,
    SolverContinuation,
    _EXPLORATION_INTERVAL,
    _LEGACY_LAYOUT,
    _LONG_LIMIT,
    _OBSERVED_ELAPSED_CAP_NS,
    _OBSERVED_WORK_CAP,
    _PREVIOUS_LAYOUT,
    _V3_LAYOUT,
    _RECENT_DECAY_PERIOD,
    _RECENT_LIMIT,
    _digest_field,
    _record_observation,
    audit_result,
    compile_source,
    continue_solver_continuation,
    context_features,
    initial_policy,
    inspect_policy,
    migrate_policy,
    select_method,
    solve_and_learn,
    start_solver_continuation,
    REGIONAL_KERNEL_MAX_WORK,
    REGIONAL_KERNEL_NAME,
    REGIONAL_STATE_SCHEMA,
    regional_kernel,
    regional_state,
)
from cassi_field_atlas import AtlasState
from cassi_learning_computer import (
    PREVIOUS_SCHEMA as PREVIOUS_COMPUTER_SCHEMA,
    SCHEMA as COMPUTER_SCHEMA,
    LearningComputer,
)


def sat_source(signal: str = "input") -> dict[str, object]:
    return {
        "kind": "circuit",
        "inputs": [signal],
        "gates": [],
        "assertions": [[signal, 1]],
        "relations": [],
        "clauses": [],
    }


def unsat_source() -> dict[str, object]:
    return {
        "kind": "circuit",
        "inputs": ["input"],
        "gates": [],
        "assertions": [["input", 1], ["input", 0]],
        "relations": [],
        "clauses": [],
    }



def continuation_source() -> dict[str, object]:
    return {
        "kind": "circuit",
        "inputs": ["a", "b", "c", "d", "e", "f"],
        "gates": [],
        "assertions": [],
        "relations": [
            {
                "kind": "xor",
                "args": ["a", "b", "c", "d", "e", "f"],
                "rhs": 1,
            }
        ],
        "clauses": [],
    }

def legacy_policy() -> tuple[PolicyState, int]:
    compiled = compile_source(sat_source())
    structural = int(context_features(compiled)["structural_context_key"])
    field = np.zeros((7, 64, len(METHODS)), dtype=np.float64)
    field[0, structural, 0] = 2
    field[1, structural, 0] = 1
    field[2, structural, 0] = 200
    field[3, structural, 0] = 10
    field[4, structural, 0] = 1
    field[5, structural, 0] = 1
    field[6, structural, 0] = 2
    descriptor = {
        "schema": LEGACY_SCHEMA,
        "layout": _LEGACY_LAYOUT,
        "shape": [7, 64, len(METHODS)],
        "dtype": "float64",
        "field_b64": base64.b64encode(field.tobytes(order="C")).decode("ascii"),
        "state_sha256": _digest_field(field, layout=_LEGACY_LAYOUT),
    }
    return PolicyState.from_dict(descriptor), structural

def test_context_is_structural_and_bounded() -> None:
    left = context_features(compile_source(sat_source("left")))
    right = context_features(compile_source(sat_source("renamed")))
    assert left["context_key"] == right["context_key"]
    assert left["feature_vector"] == right["feature_vector"]
    assert 0 <= left["structural_context_key"] < 64
    assert 0 <= left["context_key"] < 320
    assert left["budget_class"] in (1, 2, 3, 4)
    assert not any("sha" in key or "name" in key or "label" in key for key in left)



def test_context_key_reuses_structural_bucket_across_source_scale() -> None:
    larger = {
        "kind": "circuit",
        "inputs": ["a", "b"],
        "gates": [],
        "assertions": [["a", 1], ["b", 1]],
        "relations": [],
        "clauses": [],
    }
    assert context_features(compile_source(larger))["context_key"] == context_features(
        compile_source(sat_source())
    )["context_key"]



def test_complexity_refinement_splits_one_coarse_structural_context() -> None:
    small = context_features(compile_source(sat_source()), budget=16)
    names = ["a", "b", "c", "d", "e"]
    large_source = {
        "kind": "circuit",
        "inputs": names,
        "gates": [],
        "assertions": [[name, 1] for name in names],
        "relations": [],
        "clauses": [],
    }
    large = context_features(compile_source(large_source), budget=16)
    assert small["features"]["complexity_refinement"] == 0
    assert large["features"]["complexity_refinement"] == 1
    assert large["structural_context_key"] == (
        small["structural_context_key"] ^ 1
    )
    method, receipt = select_method(
        initial_policy(), compile_source(large_source), budget=16
    )
    assert method in METHODS
    assert receipt["observation_context_key"] == large["context_key"]
    assert 0 <= large["structural_context_key"] < 64
    assert 0 <= large["context_key"] < 320


def test_refined_context_uses_sibling_evidence_only_until_locally_observed() -> None:
    compiled = compile_source(sat_source())
    context = context_features(compiled, budget=16)
    local = int(context["context_key"])
    sibling = (
        (int(context["structural_context_key"]) ^ 1) * 5
        + int(context["budget_class"])
    )
    field = initial_policy().field.copy()
    chosen = 2
    field[0, sibling, chosen] = 1
    field[1, sibling, chosen] = 1
    field[2, sibling, chosen] = 1
    field[3, sibling, chosen] = 1
    field[4, sibling, chosen] = 1
    field[5, sibling, chosen] = 1
    field[6, sibling, chosen] = 1
    field[7, sibling, 0] = 1
    field[8, sibling, chosen] = 1
    method, receipt = select_method(
        PolicyState(field), compiled, budget=16, explore=False
    )
    assert method == METHODS[chosen]
    assert receipt["phase"] == "refined-sibling-prior"
    assert receipt["observation_context_key"] == local
    assert receipt["evidence_context_key"] == sibling


def test_related_evidence_guides_unseen_exploration_completion_first() -> None:
    compiled = compile_source(sat_source())
    context = context_features(compiled, budget=16)
    local = int(context["context_key"])
    sibling = (
        (int(context["structural_context_key"]) ^ 1) * 5
        + int(context["budget_class"])
    )
    field = initial_policy().field.copy()
    field[0, local, 0] = 1
    field[1, local, 0] = 1
    field[2, local, 0] = 1
    field[3, local, 0] = 1
    field[4, local, 0] = 1
    field[5, local, 0] = 1
    field[6, local, 0] = 1
    field[7, local, 0] = 1
    field[8, local, 0] = 1
    for method, completion, elapsed, work in (
        (1, 0, 2, 2),
        (2, 2, 200, 20),
    ):
        field[0, sibling, method] = 2
        field[1, sibling, method] = completion
        field[2, sibling, method] = elapsed
        field[3, sibling, method] = work
        field[4, sibling, method] = 2
        field[5, sibling, method] = completion
        field[6, sibling, method] = elapsed
        field[8, sibling, method] = 4
    field[7, sibling, 0] = 4
    method, receipt = select_method(
        PolicyState(field), compiled, budget=16
    )
    assert method == METHODS[2]
    assert receipt["phase"] == "explore"
    assert receipt["exploration_reason"] == "related-evidence-completion-cost"
    assert receipt["evidence_context_key"] == sibling

def test_budget_classes_isolate_evidence_for_the_same_structure() -> None:
    compiled = compile_source(sat_source())
    low = context_features(compiled, budget=64)
    high = context_features(compiled, budget=65)
    assert low["structural_context_key"] == high["structural_context_key"]
    assert low["budget_class"] != high["budget_class"]
    assert low["context_key"] != high["context_key"]

    learned, receipt = solve_and_learn(
        initial_policy(), compiled, budget=16, method="conflict"
    )
    assert receipt["observation"]["context_key"] == low["context_key"]
    low_method, low_selection = select_method(learned, compiled, budget=16)
    high_method, high_selection = select_method(learned, compiled, budget=65)
    assert low_method == "conflict-controller"
    assert high_method == "conflict"
    assert low_selection["observed_support"][0] == 1
    assert high_selection["observed_support"] == [0] * len(METHODS)

def test_selection_interleaves_structural_incumbent_challengers_and_empirical_use() -> None:
    compiled = compile_source(sat_source())
    policy = initial_policy()
    chosen: list[str] = []
    phases: list[str] = []
    exploration_epochs: list[int] = []
    for _ in range(17):
        method, receipt = select_method(policy, compiled, budget=16)
        chosen.append(method)
        phases.append(receipt["phase"])
        if receipt["phase"] == "explore":
            exploration_epochs.append(receipt["context_epoch"])
        policy, _ = _record_observation(
            policy,
            int(receipt["context"]["context_key"]),
            METHODS.index(method),
            elapsed_ns=10,
            work=10,
            status="sat",
        )
    assert chosen[0] == "conflict"
    assert phases[0] == "cold-start"
    assert exploration_epochs == [1, 4, 8, 12, 16]
    assert set(chosen) == set(METHODS)
    assert phases.count("empirical") == 11
    _, complete = select_method(policy, compiled, budget=16)
    assert complete["exploration_complete"] is True
    assert complete["unseen_methods"] == []
    assert complete["exploration_interval"] == _EXPLORATION_INTERVAL

    # Checked completion evidence outranks raw elapsed time and support.
    context = int(context_features(compiled, budget=16)["context_key"])
    field = initial_policy().field.copy()
    field[0, context, 0] = 4
    field[1, context, 0] = 4
    field[2, context, 0] = 4
    field[3, context, 0] = 4
    field[4, context, 0] = 4
    field[5, context, 0] = 4
    field[6, context, 0] = 4
    field[0, context, 1] = 1
    field[1, context, 1] = 0
    field[2, context, 1] = 10_000
    field[3, context, 1] = 1
    field[4, context, 1] = 1
    field[5, context, 1] = 0
    field[6, context, 1] = 10_000
    field[7, context, 0] = 5
    field[8, context, 0] = 4
    field[8, context, 1] = 5
    method, receipt = select_method(
        PolicyState(field), compiled, budget=16
    )
    assert method == METHODS[0]
    assert receipt["phase"] == "empirical"


def test_stale_method_reevaluation_and_field_counterfactual_are_deterministic() -> None:
    compiled = compile_source(sat_source())
    context = int(context_features(compiled, budget=16)["context_key"])
    field = initial_policy().field.copy()
    for method in range(len(METHODS)):
        field[0, context, method] = 4
        field[1, context, method] = 4
        field[2, context, method] = 4
        field[3, context, method] = 4
        recent = 1 if method == 3 else 4
        field[4, context, method] = recent
        field[5, context, method] = recent
        field[6, context, method] = recent
        field[8, context, method] = 20 if method != 3 else 1
    field[7, context, 0] = 24
    method, receipt = select_method(
        PolicyState(field), compiled, budget=16
    )
    assert method == METHODS[3]
    assert receipt["phase"] == "reevaluate"
    assert receipt["exploration_reason"] == "stale-method-reevaluation"
    assert receipt["method_age"][3] == 23

    def preference(winner: int) -> PolicyState:
        values = initial_policy().field.copy()
        for candidate in range(len(METHODS)):
            values[0, context, candidate] = 2
            values[1, context, candidate] = 2
            values[2, context, candidate] = (
                2 if candidate == winner else 200
            )
            values[3, context, candidate] = 20
            values[4, context, candidate] = 2
            values[5, context, candidate] = 2
            values[6, context, candidate] = (
                2 if candidate == winner else 200
            )
            values[8, context, candidate] = 12
        values[7, context, 0] = 12
        return PolicyState(values)

    first, _ = select_method(
        preference(0), compiled, budget=16, explore=False
    )
    second, _ = select_method(
        preference(1), compiled, budget=16, explore=False
    )
    assert first == METHODS[0]
    assert second == METHODS[1]


def test_policy_inspection_is_a_read_only_context_projection() -> None:
    policy = initial_policy()
    before = policy.state_sha256
    projected = inspect_policy(policy, sat_source(), budget=16)
    assert projected["policy_state_sha256"] == before
    assert projected["selected_method"] == "conflict"
    assert projected["selection"]["phase"] == "cold-start"
    assert projected["selection"]["context_epoch"] == 0
    assert projected["adaptive_state"] == "field-only"
    assert policy.state_sha256 == before


def test_policy_field_is_immutable_and_round_trips() -> None:
    state = initial_policy()
    detached = state.field
    assert detached.dtype.name == "float64"
    assert detached.flags.writeable is False
    with pytest.raises(ValueError):
        detached[0, 0, 0] = 1
    descriptor = state.as_dict()
    assert json.loads(json.dumps(descriptor)) == descriptor
    restored = PolicyState.from_dict(descriptor)
    assert restored == state
    assert restored.state_sha256 == state.state_sha256

    broken = dict(descriptor)
    broken["state_sha256"] = "0" * 64
    with pytest.raises(PolicyError):
        PolicyState.from_dict(broken)

    mutations = (
        ((1, 0, 0), 1),
        ((5, 0, 0), 1),
        ((0, 0, 0), _LONG_LIMIT + 1),
        ((4, 0, 0), _RECENT_LIMIT + 1),
    )
    for coordinate, value in mutations:
        poisoned = state.field.copy()
        poisoned[coordinate] = value
        if coordinate[0] == 0:
            poisoned[2, 0, 0] = value
        if coordinate[0] == 4:
            poisoned[6, 0, 0] = value
        poisoned_descriptor = dict(descriptor)
        poisoned_descriptor["field_b64"] = base64.b64encode(
            poisoned.tobytes(order="C")
        ).decode("ascii")
        poisoned_descriptor["state_sha256"] = _digest_field(poisoned)
        with pytest.raises(PolicyError):
            PolicyState.from_dict(poisoned_descriptor)

    invalid_totals = (
        (2, 0),
        (2, _OBSERVED_ELAPSED_CAP_NS + 1),
        (3, _OBSERVED_WORK_CAP + 1),
        (6, 0),
        (6, _OBSERVED_ELAPSED_CAP_NS + 1),
    )
    for plane, value in invalid_totals:
        poisoned = state.field.copy()
        poisoned[0, 0, 0] = 1
        poisoned[2, 0, 0] = 1
        poisoned[4, 0, 0] = 1
        poisoned[6, 0, 0] = 1
        poisoned[7, 0, 0] = 1
        poisoned[8, 0, 0] = 1
        poisoned[plane, 0, 0] = value
        poisoned_descriptor = dict(descriptor)
        poisoned_descriptor["field_b64"] = base64.b64encode(
            poisoned.tobytes(order="C")
        ).decode("ascii")
        poisoned_descriptor["state_sha256"] = _digest_field(poisoned)
        with pytest.raises(PolicyError):
            PolicyState.from_dict(poisoned_descriptor)


def test_recent_and_long_windows_decay_and_clip_at_exact_bounds() -> None:
    context = int(context_features(compile_source(sat_source()), budget=16)["context_key"])
    field = initial_policy().field.copy()
    field[0, context, 0] = _LONG_LIMIT
    field[1, context, 0] = _LONG_LIMIT
    field[2, context, 0] = _LONG_LIMIT
    field[3, context, 0] = _LONG_LIMIT
    field[4, context, 0] = _RECENT_LIMIT
    field[5, context, 0] = _RECENT_LIMIT
    field[6, context, 0] = _RECENT_LIMIT
    field[7, context, 0] = _RECENT_DECAY_PERIOD - 1
    field[8, context, 0] = _RECENT_DECAY_PERIOD - 1
    field[0, context, 1] = 1
    field[1, context, 1] = 1
    field[2, context, 1] = 9
    field[3, context, 1] = 1
    field[4, context, 1] = 1
    field[5, context, 1] = 1
    field[6, context, 1] = 9
    field[8, context, 1] = 1
    updated, observation = _record_observation(
        PolicyState(field),
        context,
        0,
        elapsed_ns=_OBSERVED_ELAPSED_CAP_NS + 7,
        work=_OBSERVED_WORK_CAP + 9,
        status="exhausted",
    )
    assert observation["long_decayed"] is True
    assert observation["recent_synchronized_decay"] is True
    assert observation["recent_decay_period"] == _RECENT_DECAY_PERIOD
    assert observation["context_epoch_before"] == _RECENT_DECAY_PERIOD - 1
    assert observation["context_epoch_after"] == _RECENT_DECAY_PERIOD
    assert observation["elapsed_clipped"] is True
    assert observation["work_clipped"] is True
    assert observation["before"]["long_support"] == _LONG_LIMIT // 2
    assert observation["before"]["recent_support"] == _RECENT_LIMIT // 2
    assert observation["after"]["long_support"] == _LONG_LIMIT // 2 + 1
    assert observation["after"]["long_completion"] == _LONG_LIMIT // 2
    assert observation["after"]["recent_support"] == _RECENT_LIMIT // 2 + 1
    assert observation["after"]["recent_completion"] == _RECENT_LIMIT // 2
    assert observation["after"]["last_observed_epoch"] == _RECENT_DECAY_PERIOD
    assert updated.field[4, context, 1] == 0
    assert updated.field[5, context, 1] == 0
    assert updated.field[6, context, 1] == 0
    assert PolicyState.from_dict(updated.as_dict()) == updated



def test_v2_policy_round_trips_losslessly_then_migrates_evidence_and_epochs() -> None:

    context = int(
        context_features(compile_source(sat_source()), budget=16)[
            "context_key"
        ]
    )
    field = np.zeros((7, 320, len(METHODS)), dtype=np.float64)
    field[:, context, 0] = (2, 1, 200, 10, 1, 1, 100)
    previous = PolicyState(
        field,
        _schema=PREVIOUS_SCHEMA,

        _layout=_PREVIOUS_LAYOUT,
    )
    descriptor = previous.as_dict()
    assert PolicyState.from_dict(descriptor).as_dict() == descriptor
    migrated = migrate_policy(previous)
    assert migrated.field[:7, context, 0].tolist() == field[:, context, 0].tolist()
    assert migrated.field[7, context, 0] == 2
    assert migrated.field[8, context, 0] == 2

    frozen, frozen_receipt = solve_and_learn(
        previous,
        sat_source(),
        budget=16,
        learn=False,
        method="conflict",
    )
    assert frozen.as_dict() == descriptor
    assert frozen_receipt["migration"]["applied"] is False
    learned, learned_receipt = solve_and_learn(
        previous,
        sat_source(),
        budget=16,
        learn=True,
        method="conflict",
    )
    assert learned.is_legacy is False
    assert learned_receipt["migration"]["applied"] is True
    assert learned_receipt["migration"]["recent_evidence_preserved"] is True
    assert learned.field[7, context, 0] == 3
def test_v3_policy_round_trips_and_migrates_losslessly_to_v4() -> None:
    field = initial_policy().field.copy()
    context = int(
        context_features(compile_source(sat_source()), budget=16)[
            "context_key"
        ]
    )
    field[0, context, 0] = 1
    field[1, context, 0] = 1
    field[2, context, 0] = 10
    field[3, context, 0] = 2
    field[4, context, 0] = 1
    field[5, context, 0] = 1
    field[6, context, 0] = 10
    field[7, context, 0] = 1
    field[8, context, 0] = 1
    previous = PolicyState(
        field, _schema=V3_SCHEMA, _layout=_V3_LAYOUT
    )
    restored = PolicyState.from_dict(previous.as_dict())
    assert restored.as_dict() == previous.as_dict()
    migrated = migrate_policy(restored)
    assert migrated.is_legacy is False
    assert migrated.field.tolist() == field.tolist()

def test_legacy_policy_round_trips_then_migrates_only_on_learning() -> None:
    legacy, structural = legacy_policy()
    descriptor = legacy.as_dict()
    assert descriptor["schema"] == LEGACY_SCHEMA
    assert PolicyState.from_dict(descriptor).as_dict() == descriptor
    migrated = migrate_policy(legacy)
    prior = structural * 5
    assert migrated.as_dict()["schema"] != LEGACY_SCHEMA
    assert migrated.field[0, prior, 0] == 2
    assert migrated.field[1, prior, 0] == 1
    assert migrated.field[2, prior, 0] == 200
    assert migrated.field[4, prior, 0] == 0

    frozen, frozen_receipt = solve_and_learn(
        legacy, sat_source(), budget=16, learn=False, method="conflict"
    )
    assert frozen.as_dict() == descriptor
    assert frozen_receipt["policy_migrated"] is False
    assert frozen_receipt["migration"]["applied"] is False
    learned, learned_receipt = solve_and_learn(
        legacy, sat_source(), budget=16, learn=True, method="conflict"
    )
    assert learned.is_legacy is False
    assert learned_receipt["policy_migrated"] is True
    assert learned_receipt["migration"]["applied"] is True
    assert learned.field[0, prior, 0] == 2
    assert learned.field[0, learned_receipt["context"]["context_key"], 0] == 1

    previous_computer = {
        "schema": PREVIOUS_COMPUTER_SCHEMA,
        "computer_id": "legacy",
        "profile": {
            "program_capacity": 8,
            "stack_capacity": 8,
            "max_steps": 20,
        },
        "policy": descriptor,
        "machine": None,
        "continuation": None,
    }
    with pytest.raises(ValueError, match="explicit migrate_legacy"):
        LearningComputer.from_dict(previous_computer)
    migrated_computer = LearningComputer.migrate_legacy(previous_computer)
    assert migrated_computer.as_dict()["schema"] == COMPUTER_SCHEMA
    atlas = AtlasState(computers=(migrated_computer,))
    restored = AtlasState.decode_bundle(atlas.encode_bundle())
    assert restored.state_sha256 == atlas.state_sha256
    restored_policy = restored.computers[0]._value("policy")
    assert restored_policy["planes"] == [
        [
            [int(value) for value in method_row]
            for method_row in context_rows
        ]
        for context_rows in migrate_policy(legacy)._field
    ]
    successor, receipt = restored.computers[0].solve(
        sat_source(), budget=16, method="conflict"
    )
    assert receipt["status"] == "sat"
    reloaded = AtlasState.decode_bundle(
        AtlasState(computers=(successor,)).encode_bundle()
    )
    assert reloaded.computers[0].state_sha256 == successor.state_sha256


def test_compiled_and_raw_envelope_sources_are_equivalent() -> None:
    raw = sat_source()
    compiled = compile_source(raw)
    envelope = {"kind": "circuit", "source": raw}
    assert compile_source(envelope).as_dict() == compiled.as_dict()
    assert compile_source(compiled.as_dict()).as_dict() == compiled.as_dict()


def test_invalid_methods_and_workspace_refusals_are_policy_errors() -> None:
    policy = initial_policy()
    with pytest.raises(PolicyError):
        solve_and_learn(policy, sat_source(), method="local")
    with pytest.raises(PolicyError):
        solve_and_learn(policy, sat_source(), budget=0)
    with pytest.raises(PolicyError):
        solve_and_learn(policy, sat_source(), max_field_bytes=1, method="conflict")


def test_solve_receipt_is_json_and_witness_is_audited_against_source() -> None:
    policy, receipt = solve_and_learn(initial_policy(), sat_source(), method="conflict", budget=16)
    assert receipt["status"] == "sat"
    assert receipt["audit"]["checked"] is True
    assert receipt["audit"]["auditor"] == "original-source-evaluator"
    json.dumps(receipt)
    assert policy.state_sha256 != initial_policy().state_sha256

    tampered = copy.deepcopy(receipt["result"])
    tampered["assignment"] = [-1]
    with pytest.raises(PolicyError):
        audit_result(compile_source(sat_source()), tampered)


def test_shared_budget_and_exhaustion_carry_no_decided_evidence() -> None:
    _, receipt = solve_and_learn(initial_policy(), unsat_source(), budget=1)
    assert receipt["status"] == "exhausted"
    assert receipt["budget_used"] <= receipt["budget"]["declared"]
    assert receipt["budget_used"] + receipt["budget_remaining"] == receipt["budget"]["declared"]
    assert receipt["witness"] is None
    assert receipt["proof"] is None
    assert receipt["result"]["witness"] is None
    assert receipt["result"]["resolution_proof"] is None
    assert receipt["result"]["hybrid_proof"] is None
    assert receipt["audit"]["status"] == "exhausted"

def test_learn_false_preserves_policy_field_bytes_and_freezes_selection() -> None:
    policy = initial_policy()
    learned, first = solve_and_learn(policy, sat_source(), budget=16)
    assert first["selection"]["phase"] == "cold-start"
    frozen, second = solve_and_learn(learned, sat_source(), budget=16, learn=False)
    assert frozen.state_sha256 == learned.state_sha256
    assert frozen.field.tobytes() == learned.field.tobytes()
    assert second["method"] == first["method"] == "conflict"
    assert second["selection"]["phase"] == "empirical"
    assert second["status"] == first["status"] == "sat"


def test_no_unsat_claim_from_unverified_synthetic_evidence() -> None:
    compiled = compile_source(unsat_source())
    _, receipt = solve_and_learn(initial_policy(), compiled, method="conflict", budget=16)
    assert receipt["status"] == "unsat"
    tampered = copy.deepcopy(receipt["result"])
    tampered["resolution_proof"] = {"schema": "fake"}
    with pytest.raises(PolicyError):
        audit_result(compiled, tampered)


def test_solver_continuation_restores_the_exact_running_field() -> None:
    source = continuation_source()
    initial = initial_policy()
    whole_policy, whole, whole_continuation = (
        start_solver_continuation(
            initial,
            source,
            budget=64,
            lifetime_budget=512,
            learn=False,
            method="conflict",
        )
    )
    paused_policy, paused, continuation = (
        start_solver_continuation(
            initial,
            source,
            budget=1,
            lifetime_budget=512,
            learn=False,
            method="conflict",
        )
    )
    assert whole_continuation is None
    assert continuation is not None
    assert paused["status"] == "exhausted"
    assert paused["context"] == context_features(
        compile_source(source), budget=512
    )
    assert paused["context"] != context_features(
        compile_source(source), budget=1
    )
    assert paused["reason"] == "episode-budget"
    assert paused["continuation"]["continuable"] is True
    assert paused_policy.state_sha256 == initial.state_sha256

    restored = SolverContinuation.from_dict(
        json.loads(json.dumps(continuation.as_dict()))
    )
    assert restored.as_dict() == continuation.as_dict()
    assert restored.state_sha256 == continuation.state_sha256
    split_policy, split, remaining = (
        continue_solver_continuation(
            paused_policy,
            restored,
            source,
            budget=63,
        )
    )
    assert remaining is None
    assert split["continuation"]["final"] is True
    assert split["result"] == whole["result"]
    assert (
        split["cumulative_resource_ledger"]
        == whole["cumulative_resource_ledger"]
    )
    assert split_policy.state_sha256 == whole_policy.state_sha256
    assert split_policy.state_sha256 == initial.state_sha256



def test_continuation_rejects_unpayable_atomic_episode() -> None:
    source = continuation_source()
    initial = initial_policy()
    paused_policy, paused, continuation = (
        start_solver_continuation(
            initial,
            source,
            budget=2,
            lifetime_budget=512,
            learn=False,
            method="algebraic-1-controller",
        )
    )
    assert continuation is not None
    required = continuation.minimum_resume_budget
    assert required > 1
    assert paused["budget"]["minimum_next_episode"] == required
    assert (
        paused["continuation"]["minimum_resume_budget"]
        == required
    )
    retained = continuation.as_dict()
    with pytest.raises(PolicyError, match=f"requires at least {required}"):
        continue_solver_continuation(
            paused_policy,
            continuation,
            source,
            budget=required - 1,
        )
    assert continuation.as_dict() == retained
    resumed_policy, resumed, next_continuation = (
        continue_solver_continuation(
            paused_policy,
            continuation,
            source,
            budget=required,
        )
    )
    assert resumed["budget"]["used"] > 0
    assert (
        resumed["continuation"]["state_sha256_after"]
        != continuation.state_sha256
    )
    assert resumed_policy.state_sha256 == initial.state_sha256
    assert next_continuation is not None

    corrupted = copy.deepcopy(next_continuation.as_dict())
    corrupted["minimum_resume_budget"] -= 1
    with pytest.raises(
        PolicyError, match="atomic resume budget is inconsistent"
    ):
        SolverContinuation.from_dict(corrupted)

def test_continuation_defers_learning_and_rejects_source_changes() -> None:
    source = continuation_source()
    initial = initial_policy()
    paused_policy, paused, continuation = (
        start_solver_continuation(
            initial,
            source,
            budget=1,
            lifetime_budget=512,
            learn=True,
            method="conflict",
        )
    )
    assert continuation is not None
    assert paused["continuation"]["learning_deferred"] is True
    assert paused["continuation"]["learning_applied"] is False
    assert paused_policy.state_sha256 == initial.state_sha256
    with pytest.raises(PolicyError, match="source differs"):
        continue_solver_continuation(
            paused_policy,
            continuation,
            sat_source("different"),
            budget=63,
        )

    learned, final, remaining = continue_solver_continuation(
        paused_policy,
        continuation,
        source,
        budget=63,
    )
    assert remaining is None
    assert final["status"] == "sat"
    assert final["continuation"]["learning_applied"] is True
    assert final["observation"]["after"]["long_support"] == 1
    assert learned.state_sha256 != initial.state_sha256


def test_regional_policy_selects_and_learns_from_typed_field_data(monkeypatch) -> None:
    source = sat_source()
    policy = initial_policy()
    compiled = compile_source(source)
    expected_method, expected_selection = select_method(
        policy, compiled, budget=64
    )
    state = regional_state(
        source,
        policy=policy,
        lifetime_budget=64,
        feedback={
            "id": "feedback-1",
            "method": expected_method,
            "status": "sat",
            "elapsed_ns": 25,
            "work": 7,
        },
    )
    assert REGIONAL_KERNEL_NAME == "learning.computation-policy"
    assert REGIONAL_KERNEL_MAX_WORK > 0
    assert state["schema"] == REGIONAL_STATE_SCHEMA
    assert "field_b64" not in json.dumps(state, sort_keys=True)

    def reject_legacy(*_args, **_kwargs):
        raise AssertionError("regional policy reached a legacy state or solver")

    monkeypatch.setattr(PolicyState, "from_dict", reject_legacy)
    monkeypatch.setattr(SolverContinuation, "from_dict", reject_legacy)
    monkeypatch.setattr(
        computation_policy, "start_solver_continuation", reject_legacy
    )
    monkeypatch.setattr(
        computation_policy, "continue_solver_continuation", reject_legacy
    )
    transition = regional_kernel(
        json.loads(json.dumps(state, sort_keys=True)), {}, 1
    )
    assert transition.status == "done"
    assert transition.work == 1
    assert transition.output["method"] == expected_method
    assert transition.output["selection"] == expected_selection
    context = int(expected_selection["observation_context_key"])
    expected_policy, expected_observation = _record_observation(
        policy,
        context,
        METHODS.index(expected_method),
        elapsed_ns=25,
        work=7,
        status="sat",
    )
    assert transition.output["observation"] == expected_observation
    assert transition.state["continuation"]["policy"]["planes"] == [
        [
            [int(value) for value in method_row]
            for method_row in context_rows
        ]
        for context_rows in expected_policy._field
    ]
    repeated = regional_kernel(transition.state, {}, 1)
    assert repeated.work == 0
    assert repeated.output == transition.output
