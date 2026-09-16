"""Tests for the constraint implication engine.

Every expectation here is computed twice: once through the implication engine
and once through a local enumeration whose semantics are written out for the
family under test, so a passing run means two independent readings agree. The
certificate audits reuse the independent auditors of the earlier probes.

The tests are also where the outcome vocabulary is pinned: a rule that holds
because a declared boundary already forbids its premise reports ``vacuous``,
never ``holds``, and a bound-stopped run reports ``unresolved`` with no
certificate and no witness.
"""

from __future__ import annotations
import json
import itertools
import random
from typing import Any, cast

import pytest

import cassi_constraint_implication as implication
import run_implication_screen as implication_screen
import verify_hybrid_inference
import verify_p_vs_np_clause_field_probe
from cassi_constraint_field import (
    CircuitSpec,
    ConstraintFieldError,
    ConstraintFieldProfile,
    TransitionProblem,
)


def _assignments(inputs):
    for bits in itertools.product((0, 1), repeat=len(inputs)):
        yield dict(zip(inputs, bits))


def _circuit_holds(spec, assignment, gates):
    """Family-local circuit semantics: gates, assertions, clause rows."""

    values = dict(assignment)
    for name, op, arguments in gates:
        if op == "not":
            values[name] = 1 - values[arguments[0]]
        elif op == "and":
            values[name] = values[arguments[0]] & values[arguments[1]]
        elif op == "or":
            values[name] = values[arguments[0]] | values[arguments[1]]
        elif op == "xor":
            values[name] = values[arguments[0]] ^ values[arguments[1]]
        else:  # pragma: no cover - unsupported family
            raise AssertionError(op)
    for name, value in spec.get("assertions", ()):
        if values[name] != int(value):
            return False
    for row in spec.get("clauses", ()):
        if not any(values[name] == int(value) for name, value in row):
            return False
    return True


def _rule_counterexample(spec, gates, consequences, assumptions):
    """First satisfying assignment that refutes the rule, by enumeration."""

    for assignment in _assignments(spec["inputs"]):
        if not _circuit_holds(spec, assignment, gates):
            continue
        if any(assignment[name] != value for name, value in assumptions):
            continue
        name, value = consequences
        if assignment[name] != value:
            return assignment
    return None


def _xor_chain_source():
    gates = ({"op": "xor", "out": "c", "args": ("a", "b")},)
    return CircuitSpec(
        inputs=("a", "b"),
        gates=gates,
        assertions=(("c", 1),),
    ).as_dict(), gates


def test_xor_chain_implication_holds_with_audited_certificate():
    source, _ = _xor_chain_source()
    query = implication.ImplicationQuery(
        source=source,
        consequence=("a", 1),
        assumptions=(("b", 0),),
    )
    result = implication.imply(query)

    assert result["outcome"] == "holds"
    assert result["witness"] is None
    assert result["counterexample_verified"] is False
    certificate = result["certificate"]
    assert certificate["kind"] in ("resolution", "hybrid")
    assert certificate["resolution_proof"] is not None or certificate["hybrid_proof"] is not None

    if certificate["resolution_proof"] is not None:
        verify_p_vs_np_clause_field_probe.audit_proof(
            certificate["backend_clauses"],
            certificate["learned_clauses"],
            certificate["resolution_proof"],
            variables=certificate["variables"],
            status="unsat",
            expected_conflicts=len(certificate["resolution_proof"]["conflict_derivations"]),
            max_learned_clauses=256,
        )
    if certificate["hybrid_proof"] is not None:
        verify_hybrid_inference.audit_proof(
            certificate["source_clauses"],
            certificate["hybrid_proof"],
            variables=certificate["variables"],
        )


def test_unasserted_circuit_implication_is_refuted_by_a_replayed_counterexample():
    gates = ({"op": "and", "out": "g", "args": ("a", "b")},)
    family = (("g", "and", ("a", "b")),)
    source = CircuitSpec(inputs=("a", "b"), gates=gates).as_dict()
    result = implication.imply(
        implication.ImplicationQuery(source=source, consequence=("a", 1))
    )

    assert result["outcome"] == "refuted"
    assert result["counterexample_verified"] is True
    assert result["consequence_value"] == 0
    witness = result["witness"]
    assert _circuit_holds(source, witness, family)
    assert witness["a"] == 0


def test_gate_output_consequence_is_refuted_with_its_own_witness():
    gates = ({"op": "or", "out": "g", "args": ("a", "b")},)
    source = CircuitSpec(inputs=("a", "b"), gates=gates).as_dict()
    result = implication.imply(
        implication.ImplicationQuery(
            source=source,
            consequence=("g", 1),
            assumptions=(("a", 0),),
        )
    )

    assert result["outcome"] == "refuted"
    assert result["literals"]["consequence_route"] == "clause"
    assert result["literals"]["unit_rows"] == [["g", 0]]
    assert result["consequence_value"] == 0
    assert result["witness"]["b"] == 0 and result["witness"]["a"] == 0


def test_truth_table_agreement_over_random_circuits():
    rng = random.Random(20260910)
    inputs = ("a", "b", "c")

    for _ in range(6):
        gates: list[dict[str, object]] = []
        available = list(inputs)
        for index in range(3):
            out = f"g{index}"
            op = rng.choice(("and", "or", "xor", "not"))
            if op == "not":
                arguments = (rng.choice(available),)
            else:
                left, right = rng.sample(available, 2)
                arguments = (left, right)
            gates.append({"op": op, "out": out, "args": arguments})
            available.append(out)
        spec = CircuitSpec(inputs=inputs, gates=tuple(gates)).as_dict()
        if rng.random() < 0.5:
            name = rng.choice(available)
            spec = CircuitSpec(
                inputs=inputs,
                gates=tuple(gates),
                assertions=((name, rng.randrange(2)),),
            ).as_dict()
        family = tuple((gate["out"], gate["op"], gate["args"]) for gate in gates)

        rules = [((name, 1), ()) for name in inputs]
        rules.extend(
            ((name, 1), ((other, rng.randrange(2)),))
            for name in inputs
            for other in inputs
            if other != name
        )
        for consequence, assumptions in rules:
            expected = _rule_counterexample(spec, family, consequence, assumptions)
            result = implication.imply(
                implication.ImplicationQuery(
                    source=spec,
                    consequence=consequence,
                    assumptions=assumptions,
                ),
                max_transitions=5000,
            )
            if expected is None:
                assert result["outcome"] in ("holds", "vacuous"), (
                    spec,
                    consequence,
                    assumptions,
                    result,
                )
                if result["outcome"] == "vacuous":
                    # A vacuous verdict is checkable: some query literal must be
                    # the opposite of a unit the source itself already declares.
                    compiled = implication.compile_source(spec)
                    declared = dict(compiled.witness_signals)
                    units = {clause[0] for clause in compiled.clauses if len(clause) == 1}

                    def literal(name, value):
                        return declared[name] if value == 1 else -declared[name]

                    query_literals = [literal(name, value) for name, value in assumptions]
                    query_literals.append(literal(consequence[0], 1 - consequence[1]))
                    assert any(-item in units for item in query_literals)
            else:
                assert result["outcome"] == "refuted", (spec, consequence, assumptions, result)
                witness = result["witness"]
                assert _circuit_holds(spec, witness, family)
                assert all(witness[name] == value for name, value in assumptions)
                assert witness[consequence[0]] != consequence[1]


def _transition_source(invert: bool, initial: int = 0):
    gates = (
        ({"op": "not", "out": "n", "args": ("u",)},) if invert else ()
    )
    origin = "n" if invert else "u"
    return TransitionProblem(
        state=("p",),
        inputs=("u",),
        gates=gates,
        next_state=(("p", origin),),
        horizon=2,
        initial=(("p", initial),),
    ).as_dict()


def _transition_rule_counterexample(spec, invert, consequence, assumptions):
    initial = int(spec["initial"][0][1])
    name, _, index = consequence[0].partition("@")
    assert name == "p"
    time = int(index)
    for bits in itertools.product((0, 1), repeat=spec["horizon"]):
        values = {"p@0": initial}
        for step, bit in enumerate(bits):
            values[f"u@{step}"] = bit
        state = initial
        for step, bit in enumerate(bits):
            state = (1 - bit) if invert else bit
        values["p@1"] = (1 - bits[0]) if invert else bits[0]
        values["p@2"] = state
        if any(values[label] != value for label, value in assumptions):
            continue
        if values[consequence[0]] != consequence[1]:
            return values
    return None


@pytest.mark.parametrize("invert", (False, True))
def test_transition_state_consequences_match_simulation(invert):
    spec = _transition_source(invert)
    rules = [
        (("p@1", 1), (("u@0", 1),)),
        (("p@1", 0), (("u@0", 0),)),
        (("p@2", 1), (("u@0", 1), ("u@1", 1))),
        (("p@2", 0), ()),
        (("p@2", 1), (("u@1", 0),)),
    ]
    for consequence, assumptions in rules:
        expected = _transition_rule_counterexample(spec, invert, consequence, assumptions)
        result = implication.imply(
            implication.ImplicationQuery(
                source=spec,
                consequence=consequence,
                assumptions=assumptions,
            )
        )
        if expected is None:
            assert result["outcome"] == "holds", (consequence, assumptions, result)
        else:
            assert result["outcome"] == "refuted", (consequence, assumptions, result)
            witness = result["witness"]
            assert all(witness[label] == value for label, value in assumptions)
            assert result["consequence_value"] == 1 - consequence[1]



def test_transition_gate_output_consequence_uses_clause_route():
    source = TransitionProblem(
        state=("p",),
        inputs=("u",),
        gates=({"op": "not", "out": "n", "args": ("u",)},),
        next_state=(("p", "u"),),
        horizon=1,
    ).as_dict()
    holds = implication.imply(
        implication.ImplicationQuery(
            source=source,
            consequence=("n@0", 1),
            assumptions=(("u@0", 0),),
        )
    )
    assert holds["outcome"] == "holds"
    assert holds["literals"]["consequence_route"] == "clause"

    refuted = implication.imply(
        implication.ImplicationQuery(source=source, consequence=("n@0", 1))
    )
    assert refuted["outcome"] == "refuted"
    assert refuted["witness"]["u@0"] == 1

def test_independent_screen_resolves_unused_transition_gate_output():
    source = TransitionProblem(
        state=("p",),
        inputs=("u",),
        gates=({"op": "not", "out": "n", "args": ("u",)},),
        next_state=(("p", "u"),),
        horizon=1,
    ).as_dict()
    assignment = {"p@0": 0, "u@0": 0}
    assert implication_screen._own_holds(source, assignment)
    assert implication_screen._own_signal(source, assignment, "n@0") == 1

def test_implication_can_request_binary_augmentation():
    """The toggle is usable from the rule API and its effect is observable."""

    source = CircuitSpec(
        inputs=("a", "b", "c"),
        relations=({"kind": "xor", "args": ("a", "b"), "rhs": 1},),
        assertions=(("c", 1),),
    ).as_dict()
    open_query = implication.ImplicationQuery(source=source, consequence=("a", 1))
    narrow = implication.imply(open_query, augmentation_arity=1)
    wide = implication.imply(open_query, augmentation_arity=2)

    assert narrow["augmentation_arity"] == 1 and wide["augmentation_arity"] == 2
    assert (narrow["outcome"], narrow["reason"]) == (wide["outcome"], wide["reason"])
    assert narrow["work"]["augmentations"] == 0
    assert wide["work"]["augmentations"] > 0
    assert len(wide["compiled"]["clauses"]) == len(narrow["compiled"]["clauses"])

    forced = implication.ImplicationQuery(
        source=source,
        consequence=("a", 1),
        assumptions=(("b", 0),),
    )
    for arity in (1, 2):
        result = implication.imply(forced, augmentation_arity=arity)
        assert result["outcome"] == "holds"
        verify_hybrid_inference.audit_proof(
            result["certificate"]["source_clauses"],
            result["certificate"]["hybrid_proof"],
            variables=result["certificate"]["variables"],
        )



def test_vacuous_outcome_distinguishes_boundary_clashes():
    source = CircuitSpec(inputs=("a",), assertions=(("a", 1),)).as_dict()
    result = implication.imply(
        implication.ImplicationQuery(
            source=source,
            consequence=("a", 1),
            assumptions=(("a", 0),),
        )
    )
    assert result["outcome"] == "vacuous"
    assert result["clash"] == "a=0"
    assert result["certificate"] is None and result["witness"] is None

def test_boundary_consequence_is_holds_not_vacuous():
    source = CircuitSpec(inputs=("a",), assertions=(("a", 1),)).as_dict()
    result = implication.imply(
        implication.ImplicationQuery(source=source, consequence=("a", 1))
    )
    assert result["outcome"] == "holds"
    assert result["reason"] != "declared-boundary-clash"
    assert result["certificate"] is not None



def test_relation_derived_unit_is_not_mislabeled_vacuous():
    """A relation-derived unit is a real entailment, not a boundary clash."""

    source = CircuitSpec(
        inputs=("a", "b"),
        relations=({"kind": "xor", "args": ("a", "a", "b"), "rhs": 1},),
    ).as_dict()
    result = implication.imply(
        implication.ImplicationQuery(source=source, consequence=("b", 1))
    )

    assert result["outcome"] == "holds"
    assert result["reason"] != "declared-boundary-clash"
    assert result["certificate"] is not None


def test_final_boundary_clash_is_vacuous_for_derived_signals():
    source = TransitionProblem(
        state=("p",),
        inputs=("u",),
        gates=(),
        next_state=(("p", "u"),),
        horizon=1,
        final=(("p", 1),),
    ).as_dict()
    result = implication.imply(
        implication.ImplicationQuery(
            source=source,
            consequence=("u@0", 0),
            assumptions=(("p@1", 0),),
        )
    )

    assert result["outcome"] == "vacuous"
    assert result["clash"] == "p@1=0"

def test_deep_premise_unsatisfiability_reports_holds():
    """A premise that is unsatisfiable without any syntactic clash still holds."""

    gates = ({"op": "and", "out": "c", "args": ("a", "b")},)
    source = CircuitSpec(
        inputs=("a", "b"),
        gates=gates,
        assertions=(("c", 1),),
    ).as_dict()
    result = implication.imply(
        implication.ImplicationQuery(
            source=source,
            consequence=("b", 1),
            assumptions=(("a", 0),),
        )
    )
    assert result["outcome"] == "holds"
    assert result["reason"] != "declared-boundary-clash"


def test_exhaustion_reports_unresolved_without_certificate():
    source = CircuitSpec(
        inputs=("a", "b", "c"),
        clauses=(
            (("a", 1), ("b", 1)),
            (("b", 1), ("c", 1)),
            (("a", 1), ("c", 1)),
            (("a", 0), ("b", 0)),
            (("b", 0), ("c", 0)),
            (("a", 0), ("c", 0)),
        ),
    ).as_dict()
    result = implication.imply(
        implication.ImplicationQuery(source=source, consequence=("a", 1)),
        mode="local",
        max_transitions=1,
    )
    assert result["outcome"] == "unresolved"
    assert result["reason"] == "transition-budget"
    assert result["certificate"] is None and result["witness"] is None
    assert result["work"] is not None


def test_unknown_or_malformed_query_literals_are_refused():
    source, _ = _xor_chain_source()
    with pytest.raises(ConstraintFieldError):
        implication.imply(
            implication.ImplicationQuery(source=source, consequence=("missing", 1))
        )
    with pytest.raises(ConstraintFieldError):
        implication.imply(
            implication.ImplicationQuery(
                source=source,
                consequence=("a", 1),
                assumptions=(("missing", 0),),
            )
        )
    with pytest.raises(ConstraintFieldError):
        implication.imply(
            implication.ImplicationQuery(source=source, consequence=("a", 2))
        )
    with pytest.raises(ConstraintFieldError):
        implication.imply(
            implication.ImplicationQuery(source=source, consequence=("a", True))
        )
    with pytest.raises(ConstraintFieldError):
        implication.imply(
            implication.ImplicationQuery(
                source={"kind": "graph"},
                consequence=("a", 1),
            )
        )


def test_transition_query_rejects_illegal_signal_times():
    source = TransitionProblem(
        state=("p",),
        inputs=("u",),
        gates=({"op": "not", "out": "n", "args": ("u",)},),
        next_state=(("p", "u"),),
        horizon=1,
    ).as_dict()
    for consequence in (("u@1", 0), ("n@1", 0), ("p@2", 0), ("p@-1", 0)):
        with pytest.raises(ConstraintFieldError):
            implication.imply(
                implication.ImplicationQuery(
                    source=source,
                    consequence=consequence,
                )
            )

def test_independent_transition_evaluator_rejects_negative_input_assertion_time():
    source = TransitionProblem(
        state=("p",),
        inputs=("u",),
        gates=(),
        next_state=(("p", "u"),),
        horizon=1,
        input_assertions=((-1, "u", 0),),
    ).as_dict()
    with pytest.raises(ConstraintFieldError):
        implication.evaluate_source(source, {"p@0": 0, "u@0": 0})



def test_implication_rejects_invalid_augmentation_arity():
    source, _ = _xor_chain_source()
    for arity in (0, 3, True, False, 1.0, "1"):
        with pytest.raises(ConstraintFieldError):
            implication.imply(
                implication.ImplicationQuery(
                    source=source,
                    consequence=("a", 1),
                ),
                augmentation_arity=cast(Any, arity),
            )

def test_supplied_profile_controls_augmentation_arity():
    source, _ = _xor_chain_source()
    compiled = implication.compile_source(source)
    profile = ConstraintFieldProfile(
        max_variables=compiled.variables,
        max_clauses=len(compiled.clauses) + 64,
        mode="algebraic",
        max_augmentation_arity=2,
    )
    query = implication.ImplicationQuery(source=source, consequence=("a", 1))
    result = implication.imply(query, profile=profile)
    assert result["augmentation_arity"] == 2
    with pytest.raises(ConstraintFieldError):
        implication.imply(query, profile=profile, augmentation_arity=1)

def test_imply_does_not_mutate_the_source():
    source, _ = _xor_chain_source()
    before = repr(source)
    implication.imply(
        implication.ImplicationQuery(
            source=source,
            consequence=("a", 1),
            assumptions=(("b", 0),),
        )
    )
    implication.imply(
        implication.ImplicationQuery(source=source, consequence=("a", 0))
    )
    assert repr(source) == before

def test_regional_implication_quantum_one_round_trips_and_preserves_verdict_evidence():
    source = CircuitSpec(
        inputs=("a", "b", "c"),
        clauses=(
            (("a", 1), ("b", 1)),
            (("b", 1), ("c", 1)),
            (("a", 1), ("c", 1)),
            (("a", 0), ("b", 0)),
            (("b", 0), ("c", 0)),
            (("a", 0), ("c", 0)),
        ),
    ).as_dict()
    query = implication.ImplicationQuery(source=source, consequence=("a", 1))
    baseline = implication.imply(query, mode="local", max_transitions=64)
    state = json.loads(
        json.dumps(
            implication.regional_state(query, mode="local", max_transitions=64),
            sort_keys=True,
        )
    )
    first = implication.regional_kernel(state, {}, 1)
    assert first.status == "yield"
    assert first.work == 1
    assert first.state["continuation"]["cursor"] == 1
    assert first.state["ledger"]["counters"]["candidates"] == 1

    checkpoint = json.loads(json.dumps(first.state, sort_keys=True))
    receipt = implication.regional_kernel(checkpoint, {}, 1)
    while receipt.status == "yield":
        checkpoint = json.loads(json.dumps(receipt.state, sort_keys=True))
        receipt = implication.regional_kernel(checkpoint, {}, 1)
    uninterrupted = implication.regional_kernel(
        implication.regional_state(query, mode="local", max_transitions=64),
        {},
        implication.REGIONAL_KERNEL_MAX_WORK,
    )
    assert uninterrupted.status == "done"
    assert uninterrupted.output == receipt.output
    assert uninterrupted.state["result"] == receipt.state["result"]
    assert uninterrupted.state["ledger"]["cumulative_work"] == receipt.state["ledger"]["cumulative_work"]
    regional = receipt.output
    assert regional["outcome"] == baseline["outcome"] == "holds"
    assert regional["reason"] == "exhaustive-enumeration"
    assert regional["witness"] is None
    assert regional["certificate"] is not None
    assert regional["evidence"]["class"] == baseline["outcome"]
    assert regional["counterexample_verified"] is False
