"""Audited solver verdicts through the owner, and the invariants that carry them.

These tests pin the behaviour that made every terminal regional solve fail:
verdicts must come back audited against the original compiled source, the
decision stack must agree with the live assignment across backtracking, and
stored conflict nogoods must be exactly the evidence the independent proof
auditor replays.  The audit checks are exercised against mutated artifacts as
well, so a passing verdict cannot be vacuous.
"""

from __future__ import annotations

import itertools
import json
from typing import Any, Mapping, Sequence

import pytest

import verify_p_vs_np_clause_field_probe as auditor
from cassi_computation_policy import PolicyError, audit_result, compile_source
from cassi_constraint_field import ConstraintFieldError, regional_kernel, regional_state
from cassi_field_owner import FieldIntelligenceOwner, FieldIntelligenceSurface, RPC_SCHEMA

PROFILE = {"program_capacity": 2048, "stack_capacity": 16, "max_steps": 4096}

# 3 pigeons into 2 holes: refuted only after branching, and it stores nogoods.
PIGEONHOLE_THREE_INTO_TWO = (
    ("p0_0", "p0_1", "p1_0", "p1_1", "p2_0", "p2_1"),
    ((1, 2), (3, 4), (5, 6), (-1, -3), (-1, -5), (-3, -5), (-2, -4), (-2, -6), (-4, -6)),
)

# 4 pigeons into 3 holes: the same shape at a size that exercises more learning.
PIGEONHOLE_FOUR_INTO_THREE = (
    tuple(f"q{p}_{h}" for p in range(4) for h in range(3)),
    tuple(
        [tuple(p * 3 + h + 1 for h in range(3)) for p in range(4)]
        + [
            (-(left * 3 + h + 1), -(right * 3 + h + 1))
            for h in range(3)
            for left in range(4)
            for right in range(left + 1, 4)
        ]
    ),
)


def declared_circuit(
    inputs: Sequence[str],
    clauses: Sequence[Sequence[int]],
    relations: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "kind": "circuit",
        "inputs": list(inputs),
        "gates": [],
        "assertions": [],
        "relations": [dict(relation) for relation in relations],
        "clauses": [
            [[inputs[abs(literal) - 1], 1 if literal > 0 else 0] for literal in clause] for clause in clauses
        ],
    }


def circuit_source(
    inputs: Sequence[str],
    clauses: Sequence[Sequence[int]],
    relations: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {"kind": "circuit", "source": declared_circuit(inputs, clauses, relations)}


def brute_force_models(inputs: Sequence[str], clauses: Sequence[Sequence[int]]) -> list[list[int]]:
    models = []
    for bits in itertools.product((0, 1), repeat=len(inputs)):
        if all(any(bits[abs(literal) - 1] == (1 if literal > 0 else 0) for literal in clause) for clause in clauses):
            models.append(list(bits))
    return models


_operations = itertools.count(1)


def call(owner: FieldIntelligenceOwner, action: str, **arguments: Any) -> Mapping[str, Any]:
    op = f"solver-{next(_operations)}"
    return FieldIntelligenceSurface(owner).handle(
        {
            "schema": RPC_SCHEMA,
            "request_id": op,
            "operation": "computer",
            "params": {"operation_id": op, "computer_id": "solver", "action": action, "arguments": arguments},
        }
    )["result"]


def solve(
    owner: FieldIntelligenceOwner,
    inputs: Sequence[str],
    clauses: Sequence[Sequence[int]],
    *,
    budget: int = 512,
    method: str = "conflict",
    relations: Sequence[Mapping[str, Any]] = (),
) -> Mapping[str, Any]:
    return call(
        owner,
        "solve",
        source=circuit_source(inputs, clauses, relations),
        budget=budget,
        method=method,
        learn=False,
    )["receipt"]


def regional_verdict(
    inputs: Sequence[str],
    clauses: Sequence[Sequence[int]],
    *,
    quantum: int = 4096,
) -> dict[str, Any]:
    """Drive the JSON regional kernel directly and return its terminal state."""

    state = json.loads(json.dumps(regional_state(declared_circuit(inputs, clauses))))
    for _ in range(512):
        step = regional_kernel(state, {}, quantum)
        assert step.work <= quantum
        state = step.state
        if step.status == "done":
            assert step.output == state["result"]
            return state
    raise AssertionError("regional search did not terminate")


def test_owner_returns_audited_verdicts_with_bound_evidence(tmp_path):
    root = tmp_path / "field"
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "configure", profile=PROFILE)

        assert brute_force_models(*PIGEONHOLE_THREE_INTO_TWO) == []
        refuted = solve(owner, *PIGEONHOLE_THREE_INTO_TWO)
        assert refuted["status"] == "unsat"
        evidence = refuted["result"]
        audit = refuted["audit"]
        assert audit["checked"] is True and audit["status"] == "unsat"
        assert audit["auditor"] == "verify_p_vs_np_clause_field_probe.audit_proof"
        assert audit["conflict_derivations"] == evidence["work"]["search"]["conflicts"]
        assert evidence["reason"] == "resolution-refutation"

        # The stored nogoods are real work: they are the tail the auditor replays.
        learned = evidence["learned_clauses"]
        assert learned, "the refutation stored no nogood, so learning never engaged"
        # The reported backend is the compiled source without the learned tail.
        assert evidence["backend_clauses"] == evidence["compiled"]["clauses"]
        assert evidence["profile"]["max_learned_clauses"] >= len(learned)
        proof = evidence["resolution_proof"]
        assert [row["learning_status"] for row in proof["conflict_derivations"]].count("added") >= 1
        # Replaying the auditor here instead of trusting the runtime's own audit.
        auditor.audit_proof(
            evidence["backend_clauses"],
            learned,
            proof,
            variables=len(PIGEONHOLE_THREE_INTO_TWO[0]),
            status="unsat",
            expected_conflicts=evidence["work"]["search"]["conflicts"],
            max_learned_clauses=evidence["profile"]["max_learned_clauses"],
        )

        satisfiable = solve(owner, ("a", "b"), ((1, 2), (-1, 2)))
        assert satisfiable["status"] == "sat"
        assert satisfiable["audit"]["auditor"] == "original-source-evaluator"
        witness = satisfiable["result"]["witness"]
        assert all(
            any(witness[name] == value for name, value in clause)
            for clause in circuit_source(("a", "b"), ((1, 2), (-1, 2)))["source"]["clauses"]
        )

        algebraic = solve(
            owner,
            ("a", "b"),
            ((1,), (2,)),
            method="algebraic-2",
            relations=({"kind": "xor", "args": ("a", "b"), "rhs": 1},),
        )
        assert algebraic["status"] == "unsat"
        assert algebraic["result"]["augmentations"]
        assert algebraic["audit"]["checked"] is True


def test_binding_accepts_json_transport_and_rejects_mutation():
    inputs, clauses = PIGEONHOLE_FOUR_INTO_THREE
    assert brute_force_models(inputs, clauses) == []
    compiled = compile_source(circuit_source(inputs, clauses))
    result = regional_verdict(inputs, clauses)["result"]
    assert result["status"] == "unsat"

    # Positive control: the descriptor survives the JSON transport it always
    # takes through the field, and both shapes bind to the same source.
    assert audit_result(compiled, result)["status"] == "unsat"
    assert audit_result(compiled, json.loads(json.dumps(result)))["status"] == "unsat"

    def refuses(mutate):
        candidate = json.loads(json.dumps(result))
        mutate(candidate)
        with pytest.raises(PolicyError, match="not bound to the original compiled source"):
            audit_result(compiled, candidate)

    def flip_first_clause(candidate):
        candidate["compiled"]["clauses"][0][0] = -candidate["compiled"]["clauses"][0][0]

    refuses(flip_first_clause)
    refuses(lambda candidate: candidate["compiled"].pop("sha256"))
    refuses(lambda candidate: candidate["compiled"].update({"schema": "cassifi.constraint-problem.v2"}))
    refuses(lambda candidate: candidate.update({"compiled": compile_source(circuit_source(("a",), ((1,),))).as_dict()}))


def test_proof_and_learning_evidence_cannot_be_tampered():
    inputs, clauses = PIGEONHOLE_FOUR_INTO_THREE
    compiled = compile_source(circuit_source(inputs, clauses))
    result = regional_verdict(inputs, clauses)["result"]
    assert result["learned_clauses"], "no nogood was stored, so the tamper checks are vacuous"
    audit_result(compiled, result)

    tampered_learned = json.loads(json.dumps(result))
    tampered_learned["learned_clauses"][0][0] = -tampered_learned["learned_clauses"][0][0]
    with pytest.raises(PolicyError, match="independent clause proof audit failed"):
        audit_result(compiled, tampered_learned)

    tampered_status = json.loads(json.dumps(result))
    row = tampered_status["resolution_proof"]["conflict_derivations"][0]
    assert row["learning_status"] in {"added", "duplicate", "capacity", "root"}
    row["learning_status"] = "capacity" if row["learning_status"] != "capacity" else "added"
    with pytest.raises(PolicyError, match="independent clause proof audit failed"):
        audit_result(compiled, tampered_status)

    truncated_backend = json.loads(json.dumps(result))
    truncated_backend["backend_clauses"].pop()
    with pytest.raises(PolicyError, match="UNSAT backend clauses do not preserve original source"):
        audit_result(compiled, truncated_backend)


def test_decision_frames_track_assignments_across_backtracking():
    inputs, clauses = PIGEONHOLE_THREE_INTO_TWO
    state = json.loads(json.dumps(regional_state(declared_circuit(inputs, clauses))))
    saw_flip = False
    steps = 0
    while state["phase"] != "terminal":
        step = regional_kernel(state, {}, 1)
        state = step.state
        steps += 1
        continuation = state["continuation"]
        for depth, frame in enumerate(continuation["decisions"], 1):
            variable = abs(frame["literal"])
            assert continuation["assignments"][variable - 1] == (1 if frame["literal"] > 0 else -1)
            assert continuation["levels"][variable - 1] == depth
            assert continuation["reasons"][variable - 1] == 0
            saw_flip = saw_flip or frame["phase"] == 2
        if step.status == "done":
            assert state["phase"] == "terminal"
        assert steps < 4096
    assert saw_flip, "the search never backtracked, so the frame invariant was not stressed"
    # A terminal state is admitted again, which is where the original guard fired.
    replay = regional_kernel(state, {}, 1)
    assert replay.status == "done"
    assert replay.output["status"] == "unsat"


def test_learned_tail_invariant_is_enforced():
    inputs, clauses = PIGEONHOLE_THREE_INTO_TWO
    state = json.loads(json.dumps(regional_state(declared_circuit(inputs, clauses))))
    while state["phase"] != "terminal":
        state = regional_kernel(state, {}, 1).state
    continuation = state["continuation"]
    assert continuation["learned_clauses"]
    continuation["learned_clauses"].append(list(continuation["learned_clauses"][0]))
    with pytest.raises(ConstraintFieldError, match="learned clauses are not the backend tail"):
        regional_kernel(state, {}, 1)
