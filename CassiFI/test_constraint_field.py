"""Contract tests for the field-owned constraint subsystem.

Each test defends an observable contract of ``cassi_constraint_field``: the
compiled encoding, the verdict classes, the certificates, the checkpoint codec,
and the controller coupling.  Independent evaluators below are written from the
source vocabulary, not from the module's internals.
"""

from __future__ import annotations

import json
from itertools import product

import pytest

from cassi_constraint_field import (
    CircuitSpec,
    CompiledConstraintProblem,
    ConstraintField,
    ConstraintFieldError,
    ConstraintFieldProfile,
    REGIONAL_KERNEL_MAX_WORK,
    REGIONAL_KERNEL_NAME,
    REGIONAL_STATE_SCHEMA,
    TransitionProblem,
    compile_circuit,
    compile_transition_problem,
    regional_kernel,
    regional_state,
)
import verify_hybrid_inference as hybrid_audit
import verify_p_vs_np_clause_field_probe as clause_audit


# -- independent reference semantics ------------------------------------------


def evaluate_gate(op: str, arguments: list[int], value: int | None = None) -> int:
    if op == "const":
        return int(value)
    if op == "buf":
        return arguments[0]
    if op == "not":
        return 1 - arguments[0]
    if op == "and":
        return int(arguments[0] == 1 and arguments[1] == 1)
    if op == "or":
        return int(arguments[0] == 1 or arguments[1] == 1)
    if op == "xor":
        return arguments[0] ^ arguments[1]
    if op == "nand":
        return 1 - int(arguments[0] == 1 and arguments[1] == 1)
    if op == "nor":
        return 1 - int(arguments[0] == 1 or arguments[1] == 1)
    if op == "xnor":
        return 1 - (arguments[0] ^ arguments[1])
    if op == "mux":
        return arguments[1] if arguments[0] == 1 else arguments[2]
    raise AssertionError(op)


def simulate_circuit(spec: dict) -> list[dict[str, int]]:
    """Every input assignment, evaluated through the declared gate graph."""

    inputs = list(spec["inputs"])
    remaining = [dict(gate) for gate in spec["gates"]]
    models: list[dict[str, int]] = []
    for bits in product((0, 1), repeat=len(inputs)):
        environment = dict(zip(inputs, bits))
        pending = list(remaining)
        while pending:
            progressed = False
            for gate in list(pending):
                if all(name in environment for name in gate["args"]):
                    environment[gate["out"]] = evaluate_gate(
                        gate["op"], [environment[name] for name in gate["args"]], gate.get("value")
                    )
                    pending.remove(gate)
                    progressed = True
            if not progressed:
                raise AssertionError("cyclic circuit")
        if not all(environment[name] == bit for name, bit in spec["assertions"]):
            continue
        if not all(
            any(environment[name] == polarity for name, polarity in clause)
            for clause in spec.get("clauses", [])
        ):
            continue
        if not all(relation_holds(relation, environment) for relation in spec.get("relations", [])):
            continue
        models.append(environment)
    return models


def relation_holds(relation: dict, environment: dict[str, int]) -> bool:
    values = [environment[name] for name in relation["args"]]
    if relation["kind"] == "xor":
        return sum(values) % 2 == relation["rhs"]
    return relation["min"] <= sum(values) <= relation["max"]


def simulate_transition(spec: dict) -> list[tuple[dict[int, dict[str, int]], dict[str, int]]]:
    """Every boundary-consistent trajectory as (states by time, input trace)."""

    state = list(spec["state"])
    inputs = list(spec["inputs"])
    horizon = spec["horizon"]
    known = {name: bit for name, bit in spec["initial"]}
    free_state = [name for name in state if name not in known]
    free_inputs = [(time, name) for time in range(horizon) for name in inputs]
    trajectories = []
    for bits in product((0, 1), repeat=len(free_state) + len(free_inputs)):
        environment = dict(known)
        for name, bit in zip(free_state, bits[: len(free_state)]):
            environment[name] = bit
        trace = dict(zip(free_inputs, bits[len(free_state) :]))
        if any(
            trace[(time, name)] != bit
            for time, name, bit in spec["input_assertions"]
        ):
            continue
        states: dict[int, dict[str, int]] = {0: {name: environment[name] for name in state}}
        ok = True
        for time in range(horizon):
            local = {name: environment[name] for name in state}
            local.update({name: trace[(time, name)] for name in inputs})
            pending = [dict(gate) for gate in spec["gates"]]
            while pending:
                progressed = False
                for gate in list(pending):
                    if all(name in local for name in gate["args"]):
                        local[gate["out"]] = evaluate_gate(
                            gate["op"], [local[name] for name in gate["args"]], gate.get("value")
                        )
                        pending.remove(gate)
                        progressed = True
                if not progressed:
                    raise AssertionError("cyclic transition")
            environment = {}
            for target, origin in spec["next_state"]:
                environment[target] = local[origin]
            states[time + 1] = {name: environment[name] for name in state}
        if all(environment[name] == bit for name, bit in spec["final"]):
            trajectories.append((states, trace))
        _ = ok
    return trajectories


def cnf_models(clauses: list[list[int]], variable_ids: list[int]) -> set[tuple[int, ...]]:
    """Model set of the compiled CNF restricted to the listed variables."""

    models: set[tuple[int, ...]] = set()
    width = max(abs(literal) for clause in clauses for literal in clause) if clauses else 0
    if variable_ids:
        width = max(width, max(variable_ids))
    for bits in product((0, 1), repeat=width):
        assignment = {index + 1: bit for index, bit in enumerate(bits)}
        if all(
            any(assignment[abs(literal)] == (1 if literal > 0 else 0) for literal in clause)
            for clause in clauses
        ):
            models.add(tuple(assignment[identifier] for identifier in variable_ids))
    return models


def signal_ids(compiled: CompiledConstraintProblem) -> dict[str, int]:
    return {str(name): int(identifier) for name, identifier in compiled.payload["signals"]}


def run_to_completion(field: ConstraintField, state):
    steps = 0
    while field.status(state) == "running":
        state, _ = field.step(state)
        steps += 1
        assert steps < 20000
    return state


def solve(compiled, *, mode="conflict", controller=False, reserve=64, **overrides):
    settings = {
        "max_variables": compiled.variables,
        "max_clauses": len(compiled.clauses) + reserve,
        "max_transitions": 20000,
        "max_learned_clauses": 64,
        "mode": mode,
        "controller": controller,
        "controller_size": 8,
    }
    settings.update(overrides)
    profile = ConstraintFieldProfile(**settings)
    field = ConstraintField(profile)
    state = run_to_completion(field, field.initial(compiled))
    return field, state, field.result(state)


def and_circuit() -> dict:
    return CircuitSpec(
        inputs=("a", "b"),
        gates=({"op": "and", "out": "g", "args": ("a", "b")},),
        assertions=(("g", 1),),
    ).as_dict()


def contradiction_circuit() -> dict:
    return CircuitSpec(
        inputs=("a",),
        gates=({"op": "not", "out": "n", "args": ("a",)},),
        assertions=(("a", 1), ("n", 1)),
    ).as_dict()


def toggle_transition(horizon: int = 2) -> dict:
    return TransitionProblem(
        state=("x",),
        inputs=("i",),
        gates=({"op": "xor", "out": "nx", "args": ("x", "i")},),
        next_state=(("x", "nx"),),
        horizon=horizon,
        initial=(("x", 0),),
        final=(("x", 1),),
    ).as_dict()


# -- compiler contracts -------------------------------------------------------


def test_payload_shape_and_digest_are_exact() -> None:
    spec = and_circuit()
    compiled = compile_circuit(spec)
    assert set(compiled.payload) == {
        "schema",
        "kind",
        "source",
        "variables",
        "signals",
        "witness_signals",
        "clauses",
        "native_relations",
        "work",
    }
    assert compiled.payload["schema"] == "cassifi.constraint-problem.v1"
    assert compiled.as_dict()["sha256"] == compiled.sha256
    clauses = compiled.clauses
    assert len(set(clauses)) == len(clauses)
    assert clauses == tuple(sorted(clauses, key=lambda clause: (len(clause), clause)))
    assert dict(compiled.witness_signals) == {"a": 1, "b": 2}
    assert CompiledConstraintProblem(dict(compiled.payload), compiled.sha256).sha256 == compiled.sha256
    with pytest.raises(ConstraintFieldError):
        CompiledConstraintProblem(dict(compiled.payload), "0" * 64)


def test_transition_timed_clause_targets_declared_time() -> None:
    source = TransitionProblem(
        state=("p",),
        inputs=("u",),
        gates=(),
        next_state=(("p", "u"),),
        horizon=2,
        clauses=((("p", 1, 1),),),
    ).as_dict()
    compiled = compile_transition_problem(source)
    identifiers = signal_ids(compiled)
    assert (identifiers["s:p:1"],) in compiled.clauses
    assert (identifiers["s:p:0"],) not in compiled.clauses
    for time in (-1, 3):
        invalid = dict(source, clauses=((("p", 1, time),),))
        with pytest.raises(ConstraintFieldError):
            compile_transition_problem(invalid)

def test_compile_is_deterministic_and_order_insensitive() -> None:
    first = compile_circuit(
        CircuitSpec(
            inputs=("a", "b", "c"),
            clauses=((("a", 1), ("b", 1)), (("b", 0), ("c", 1))),
        ).as_dict()
    )
    second = compile_circuit(
        CircuitSpec(
            inputs=("a", "b", "c"),
            clauses=((("b", 0), ("c", 1)), (("a", 1), ("b", 1))),
        ).as_dict()
    )
    reordered = compile_circuit(
        CircuitSpec(
            inputs=("a", "b", "c"),
            clauses=((("a", 1), ("b", 1)), (("b", 0), ("c", 1)), (("a", 1), ("b", 1))),
        ).as_dict()
    )
    assert first.sha256 == second.sha256 == reordered.sha256


@pytest.mark.parametrize(
    "op,arity",
    [
        ("const", 0),
        ("buf", 1),
        ("not", 1),
        ("and", 2),
        ("or", 2),
        ("xor", 2),
        ("nand", 2),
        ("nor", 2),
        ("xnor", 2),
        ("mux", 3),
    ],
)
def test_single_gate_encoding_matches_the_operation(op: str, arity: int) -> None:
    names = [f"v{index}" for index in range(arity)]
    gates = []
    for value in (0, 1) if op == "const" else (None,):
        gate: dict = {"op": op, "out": "z", "args": tuple(names)}
        if value is not None:
            gate["value"] = value
        gates.append(gate)
    for gate in gates:
        compiled = compile_circuit(CircuitSpec(inputs=tuple(names), gates=(gate,)).as_dict())
        identifiers = signal_ids(compiled)
        rows = cnf_models([list(clause) for clause in compiled.clauses], [identifiers[name] for name in names] + [identifiers["z"]])
        expected = {
            tuple(values) + (evaluate_gate(op, list(values), gate.get("value")),)
            for values in product((0, 1), repeat=arity)
        }
        assert rows == expected, (op, gate.get("value"))


def test_relation_encodings_match_parity_and_bounds() -> None:
    duplicate = compile_circuit(
        CircuitSpec(
            inputs=("a", "b"),
            relations=({"kind": "xor", "args": ("a", "b", "b"), "rhs": 1},),
        ).as_dict()
    )
    identifiers = signal_ids(duplicate)
    rows = cnf_models(
        [list(clause) for clause in duplicate.clauses],
        [identifiers["a"], identifiers["b"]],
    )
    assert rows == {(1, 0), (1, 1)}
    assert duplicate.payload["native_relations"] == [
        {"kind": "xor", "source_index": 0, "args": [identifiers["a"], identifiers["b"], identifiers["b"]], "rhs": 1}
    ]

    bounded = compile_circuit(
        CircuitSpec(
            inputs=("a", "b", "c"),
            relations=({"kind": "cardinality", "args": ("a", "b", "c"), "min": 1, "max": 2},),
        ).as_dict()
    )
    identifiers = signal_ids(bounded)
    rows = cnf_models(
        [list(clause) for clause in bounded.clauses],
        [identifiers["a"], identifiers["b"], identifiers["c"]],
    )
    assert rows == {
        (1, 0, 0),
        (0, 1, 0),
        (0, 0, 1),
        (1, 1, 0),
        (1, 0, 1),
        (0, 1, 1),
    }


def test_compiled_clauses_are_canonical_and_auditable() -> None:
    """Relation auxiliaries must not leak template literal order into the CNF.

    The XOR and cardinality encoders emit literals in chain position order, so a
    source whose auxiliary numbering is not monotone in those positions used to
    produce clauses that were neither de-duplicated against their sorted twins
    nor accepted by the independent hybrid auditor.
    """

    spec = CircuitSpec(
        inputs=("v0", "v1", "v2", "v3"),
        relations=(
            {"kind": "xor", "args": ("v0", "v1", "v2", "v3"), "rhs": 1},
            {"kind": "xor", "args": ("v0", "v1", "v2", "v3"), "rhs": 0},
        ),
    ).as_dict()
    compiled = compile_circuit(spec)
    assert hybrid_audit.canonical_formula(
        [list(clause) for clause in compiled.clauses], compiled.variables
    ) == compiled.clauses

    contradiction = CircuitSpec(
        inputs=("a", "b"),
        gates=({"op": "xor", "out": "c", "args": ("a", "b")},),
        assertions=(("a", 1), ("b", 1), ("c", 1)),
    ).as_dict()
    field = ConstraintField(
        ConstraintFieldProfile(max_variables=3, max_clauses=16, mode="algebraic")
    )
    source = compile_circuit(contradiction)
    state = field.initial(source)
    while field.status(state) == "running":
        state, _ = field.step(state)
    result = field.result(state)
    assert (result["status"], result["reason"]) == ("unsat", "hybrid-refutation")
    hybrid_audit.audit_proof(
        [list(clause) for clause in source.clauses],
        result["hybrid_proof"],
        variables=source.variables,
    )


def test_transition_encoding_matches_the_reference_simulator() -> None:
    spec = TransitionProblem(
        state=("x", "y"),
        inputs=("i",),
        gates=(
            {"op": "xor", "out": "nx", "args": ("x", "i")},
            {"op": "mux", "out": "ny", "args": ("i", "y", "x")},
        ),
        next_state=(("x", "nx"), ("y", "ny")),
        horizon=2,
        initial=(("x", 0),),
        final=(("y", 1),),
    ).as_dict()
    compiled = compile_transition_problem(spec)
    identifiers = signal_ids(compiled)
    reference = simulate_transition(spec)
    assert reference, "reference found no trajectory"
    labels = {label: identifier for label, identifier in compiled.witness_signals}
    probe = [labels["x@0"], labels["y@0"], labels["i@0"], labels["i@1"]]
    models = cnf_models([list(clause) for clause in compiled.clauses], probe)
    expected = {
        (states[0]["x"], states[0]["y"], trace[(0, "i")], trace[(1, "i")])
        for states, trace in reference
    }
    assert models == expected
    assert set(labels) == {"x@0", "y@0", "i@0", "i@1"}


def test_horizon_zero_transition_is_boundary_only() -> None:
    compiled = compile_transition_problem(
        TransitionProblem(
            state=("x",),
            inputs=("i",),
            gates=(),
            next_state=(("x", "x"),),
            horizon=0,
            initial=(("x", 1),),
            final=(("x", 1),),
        ).as_dict()
    )
    sat = solve(compiled, mode="conflict")[2]
    assert sat["status"] == "sat"
    assert sat["witness"] == {"x@0": 1}
    unsat = solve(
        compile_transition_problem(
            TransitionProblem(
                state=("x",),
                inputs=("i",),
                gates=(),
                next_state=(("x", "x"),),
                horizon=0,
                initial=(("x", 0),),
                final=(("x", 1),),
            ).as_dict()
        ),
        mode="conflict",
    )[2]
    assert unsat["status"] == "unsat"


# -- verdict classes ----------------------------------------------------------


def test_local_mode_stalls_instead_of_branching() -> None:
    compiled = compile_circuit(
        CircuitSpec(inputs=("a", "b"), clauses=((("a", 1), ("b", 1)),)).as_dict()
    )
    local = solve(compiled, mode="local")[2]
    assert (local["status"], local["reason"]) == ("exhausted", "local-stall")
    assert local["witness"] is None and local["resolution_proof"] is None
    search = solve(compiled, mode="conflict")[2]
    assert search["status"] == "sat"
    assert search["witness"]["a"] == 1 or search["witness"]["b"] == 1


def test_propagation_only_refutes_root_conflicts() -> None:
    compiled = compile_circuit(contradiction_circuit())
    result = solve(compiled, mode="local")[2]
    assert (result["status"], result["reason"]) == ("unsat", "propagation-refutation")
    assert result["backend_clauses"] is not None


def test_algebraic_prepass_refutes_without_a_backend() -> None:
    compiled = compile_circuit(contradiction_circuit())
    field, state, result = solve(compiled, mode="algebraic")
    assert (result["status"], result["reason"]) == ("unsat", "hybrid-refutation")
    assert result["backend_clauses"] is None
    hybrid_audit.audit_proof(
        [list(clause) for clause in compiled.clauses],
        result["hybrid_proof"],
        variables=compiled.variables,
    )
    assert result["checkpoint"]["state_sha256"] == result["state_sha256"]


def test_sat_witnesses_satisfy_the_source() -> None:
    for mode in ("local", "conflict", "algebraic"):
        field, state, result = solve(compile_circuit(and_circuit()), mode=mode)
        assert result["status"] == "sat"
        environment = dict(result["witness"])
        for gate in and_circuit()["gates"]:
            environment[gate["out"]] = evaluate_gate(
                gate["op"], [environment[name] for name in gate["args"]]
            )
        assert environment["g"] == 1
        assert all(environment[name] == bit for name, bit in and_circuit()["assertions"])


def test_unsat_certificates_pass_the_independent_audit() -> None:
    compiled = compile_circuit(contradiction_circuit())
    for mode in ("conflict", "algebraic"):
        field, state, result = solve(compiled, mode=mode)
        assert result["status"] == "unsat"
        if result["resolution_proof"] is None:
            assert result["hybrid_proof"]["root_line"] is not None
            hybrid_audit.audit_proof(
                [list(clause) for clause in compiled.clauses],
                result["hybrid_proof"],
                variables=compiled.variables,
            )
            continue
        stats = clause_audit.audit_proof(
            [tuple(clause) for clause in result["backend_clauses"]],
            result["learned_clauses"],
            result["resolution_proof"],
            variables=compiled.variables,
            status="unsat",
            expected_conflicts=len(result["resolution_proof"]["conflict_derivations"]),
            max_learned_clauses=64,
        )
        assert stats["conflict_derivations"] >= 1


def test_admitted_augmentations_are_entailed_by_the_source() -> None:
    instances = {
        "parity_block": CircuitSpec(
            inputs=("a", "b", "c"),
            clauses=(
                (("a", 1), ("b", 1)),
                (("a", 0), ("b", 0)),
                (("b", 1), ("c", 1)),
                (("b", 0), ("c", 0)),
            ),
            assertions=(("a", 0),),
        ).as_dict(),
        "exactly_one_chain": CircuitSpec(
            inputs=("a", "b", "c", "d"),
            relations=(
                {"kind": "xor", "args": ("a", "b"), "rhs": 1},
                {"kind": "xor", "args": ("b", "c"), "rhs": 1},
                {"kind": "xor", "args": ("c", "d"), "rhs": 1},
                {"kind": "cardinality", "args": ("a", "b", "c", "d"), "min": 2, "max": 2},
            ),
        ).as_dict(),
        "atmostone_four": CircuitSpec(
            inputs=("p", "q", "r", "s"),
            relations=(
                {"kind": "cardinality", "args": ("p", "q", "r", "s"), "min": 0, "max": 1},
                {"kind": "cardinality", "args": ("p", "q", "r", "s"), "min": 1, "max": 4},
                {"kind": "cardinality", "args": ("p", "q"), "min": 1, "max": 1},
            ),
        ).as_dict(),
        "asserted_and": CircuitSpec(
            inputs=("a", "b"),
            gates=({"op": "and", "out": "g", "args": ("a", "b")},),
            assertions=(("g", 1),),
        ).as_dict(),
    }
    admitted = 0
    for name, spec in instances.items():
        compiled = compile_circuit(spec)
        result = solve(compiled, mode="algebraic")[2]
        models = cnf_models(
            [list(clause) for clause in compiled.clauses],
            list(range(1, compiled.variables + 1)),
        )
        assert result["status"] == ("sat" if models else "unsat"), (name, result["reason"])
        for row in result["augmentations"]:
            admitted += 1
            literal = int(row["clause"][0])
            assert abs(literal) <= compiled.variables
            assert all(
                (assignment[abs(literal) - 1] == 1) == (literal > 0) for assignment in models
            ), (name, literal, row)
            assert row["via"] in ("clause", "xor", "pb")
    assert admitted >= 1, "prepass admitted no facts across the family"


# -- augmentation arity ------------------------------------------------------


def test_augmentation_arity_is_declared_and_bounded() -> None:
    with pytest.raises(ConstraintFieldError):
        ConstraintFieldProfile(max_variables=2, max_clauses=2, max_augmentation_arity=0)
    with pytest.raises(ConstraintFieldError):
        ConstraintFieldProfile(max_variables=2, max_clauses=2, max_augmentation_arity=3)
    with pytest.raises(ConstraintFieldError):
        ConstraintFieldProfile(max_variables=2, max_clauses=2, max_augmentation_arity=True)
    assert ConstraintFieldProfile(max_variables=2, max_clauses=2).max_augmentation_arity == 1
    assert (
        ConstraintFieldProfile(max_variables=2, max_clauses=2, max_augmentation_arity=2).max_augmentation_arity
        == 2
    )


def test_binary_augmentation_rows_are_entailed_and_reach_the_backend() -> None:
    spec = CircuitSpec(
        inputs=("a", "b", "c"),
        relations=({"kind": "xor", "args": ("a", "b"), "rhs": 1},),
        assertions=(("c", 1),),
    ).as_dict()
    compiled = compile_circuit(spec)
    models = cnf_models(
        [list(clause) for clause in compiled.clauses],
        list(range(1, compiled.variables + 1)),
    )
    results = {}
    for arity in (1, 2):
        _, _, result = solve(compiled, mode="algebraic", max_augmentation_arity=arity)
        for row in result["augmentations"]:
            clause = [int(literal) for literal in row["clause"]]
            assert len(clause) <= arity
            assert all(abs(value) <= compiled.variables for value in clause)
            assert all(
                any((assignment[abs(value) - 1] == 1) == (value > 0) for value in clause)
                for assignment in models
            ), (clause, row)
            assert row["via"] in ("clause", "xor", "pb")
        assert len(result["backend_clauses"]) == len(compiled.clauses) + len(result["augmentations"])
        results[arity] = result

    narrow = {tuple(sorted(row["clause"])) for row in results[1]["augmentations"]}
    wide = {tuple(sorted(row["clause"])) for row in results[2]["augmentations"]}
    assert narrow < wide, "arity two must strictly extend the admitted rows"
    assert (results[1]["status"], results[1]["reason"]) == (
        results[2]["status"],
        results[2]["reason"],
    ), "the extra clauses are consequences, so the verdict is unchanged"


def test_augmentation_arity_is_inert_without_a_prepass() -> None:
    compiled = compile_circuit(and_circuit())
    for mode in ("local", "conflict"):
        _, _, narrow = solve(compiled, mode=mode, max_augmentation_arity=1)
        _, _, wide = solve(compiled, mode=mode, max_augmentation_arity=2)
        assert narrow["augmentations"] == wide["augmentations"] == []
        assert (narrow["status"], narrow["reason"]) == (wide["status"], wide["reason"])
        assert narrow["backend_clauses"] == wide["backend_clauses"]


def test_exhausted_claims_nothing() -> None:
    compiled = compile_circuit(and_circuit())
    field, state, result = solve(compiled, mode="conflict", max_transitions=1)
    assert (result["status"], result["reason"]) == ("exhausted", "transition-budget")
    assert result["witness"] is None
    assert result["resolution_proof"] is None
    assert result["assignment"] is not None


# -- transition laws ----------------------------------------------------------


def test_terminal_steps_are_idempotent() -> None:
    compiled = compile_circuit(and_circuit())
    field, state, result = solve(compiled, mode="conflict")
    digest = field.state_sha256(state)
    successor, event = field.step(state)
    assert event["action"] == "terminal"
    assert event["state_unchanged"] is True
    assert field.state_sha256(successor) == digest


def test_solve_matches_repeated_steps() -> None:
    compiled = compile_transition_problem(toggle_transition())
    field, state, result = solve(compiled, mode="conflict")
    stepping = ConstraintField(field.profile)
    current = stepping.initial(compiled)
    while stepping.status(current) == "running":
        current, event = stepping.step(current)
        assert event["state_sha256"] == stepping.state_sha256(current)
    assert stepping.state_sha256(current) == field.state_sha256(state)
    assert stepping.result(current)["witness"] == result["witness"]


def test_deterministic_replays_agree() -> None:
    compiled = compile_transition_problem(toggle_transition(horizon=3))
    first = solve(compiled, mode="conflict", controller=True)[2]
    second = solve(compiled, mode="conflict", controller=True)[2]
    assert first["state_sha256"] == second["state_sha256"]
    assert first["witness"] == second["witness"]
    assert first["work"]["controller"] == second["work"]["controller"]


# -- checkpoint codec ---------------------------------------------------------


def test_checkpoint_roundtrip_resumes_identically() -> None:
    compiled = compile_transition_problem(toggle_transition(horizon=3))
    field = ConstraintField(
        ConstraintFieldProfile(
            max_variables=compiled.variables,
            max_clauses=len(compiled.clauses) + 16,
            max_transitions=20000,
            max_learned_clauses=64,
            mode="algebraic",
        )
    )
    state = field.initial(compiled)
    for interrupt in (1, 2, 3):
        probe = state
        probe_field = field
        for _ in range(interrupt):
            if probe_field.status(probe) != "running":
                break
            probe, _ = probe_field.step(probe)
        descriptor = field.descriptor(probe)
        restored_field, restored = ConstraintField.from_descriptor(descriptor)
        assert restored_field.state_sha256(restored) == field.state_sha256(probe)
        final_reference = run_to_completion(field, state)
        final_restored = run_to_completion(restored_field, restored)
        assert restored_field.state_sha256(final_restored) == field.state_sha256(final_reference)
        assert restored_field.result(final_restored)["status"] == field.result(final_reference)["status"]


def test_descriptor_tampering_is_rejected() -> None:
    compiled = compile_circuit(contradiction_circuit())
    field = ConstraintField(
        ConstraintFieldProfile(
            max_variables=compiled.variables,
            max_clauses=len(compiled.clauses) + 8,
            max_transitions=20000,
            max_learned_clauses=32,
            mode="conflict",
        )
    )
    state = field.initial(compiled)
    state, _ = field.step(state)
    descriptor = field.descriptor(state)
    mutations = {
        "journal_b64": lambda value: {**value, "journal_b64": "!!!!"},
        "status": lambda value: {**value, "status": "sat"},
        "state_sha256": lambda value: {**value, "state_sha256": "0" * 64},
        "profile_sha256": lambda value: {**value, "profile_sha256": "0" * 64},
        "profile": lambda value: {**value, "profile": {**value["profile"], "max_clauses": 1}},
        "compiled": lambda value: {**value, "compiled": {**value["compiled"], "variables": 1}},
        "backend": lambda value: {**value, "backend": {**value["backend"], "field_b64": "AAAA"}},
        "unknown_key": lambda value: {**value, "extra": 1},
    }
    for name, mutate in mutations.items():
        with pytest.raises(ConstraintFieldError):
            ConstraintField.from_descriptor(mutate(descriptor))
            _ = name


def test_descriptor_codec_keeps_its_own_geometry() -> None:
    compiled = compile_circuit(and_circuit())
    field, state, _ = solve(compiled, mode="conflict")
    descriptor = field.descriptor(state)
    restored_field, restored = ConstraintField.from_descriptor(descriptor)
    assert restored_field.profile.as_dict() == field.profile.as_dict()
    assert restored_field.profile.fingerprint == field.profile.fingerprint
    foreign = ConstraintField(
        ConstraintFieldProfile(
            max_variables=compiled.variables,
            max_clauses=len(compiled.clauses) + 64,
            max_transitions=20000,
            max_learned_clauses=64,
            mode="local",
        )
    )
    with pytest.raises(ConstraintFieldError):
        foreign.validate(restored)


# -- controller coupling ------------------------------------------------------


def test_controller_drives_decisions_and_keeps_verdicts() -> None:
    compiled = compile_transition_problem(toggle_transition())
    plain = solve(compiled, mode="conflict", controller=False)[2]
    driven = solve(compiled, mode="conflict", controller=True)[2]
    assert plain["status"] == driven["status"] == "sat"
    assert driven["work"]["controller"]["enabled"] is True
    assert driven["work"]["controller"]["selections"] >= 1
    assert driven["work"]["controller"]["ticks"] > 0
    assert driven["work"]["search"]["decisions"] >= 1


def test_intervention_is_journaled_and_keeps_the_verdict() -> None:
    compiled = compile_transition_problem(toggle_transition(horizon=3))
    field = ConstraintField(
        ConstraintFieldProfile(
            max_variables=compiled.variables,
            max_clauses=len(compiled.clauses) + 16,
            max_transitions=20000,
            max_learned_clauses=64,
            mode="conflict",
            controller=True,
            controller_size=4,
        )
    )
    state = field.initial(compiled)
    baseline = field.state_sha256(state)
    state, event = field.intervene(state, variable=4, excitation=1024)
    assert event["action"] == "intervention"
    assert field.state_sha256(state) != baseline
    final = run_to_completion(field, state)
    result = field.result(final)
    assert result["status"] == "sat"
    assert result["work"]["controller"]["interventions"] == 1
    environment = dict(result["witness"])
    assert environment["x@0"] == 0
    value = environment["x@0"]
    for time in range(3):
        value ^= environment[f"i@{time}"]
    assert value == 1


def test_intervention_requires_a_controller_and_a_running_field() -> None:
    compiled = compile_circuit(and_circuit())
    without = ConstraintField(
        ConstraintFieldProfile(
            max_variables=compiled.variables,
            max_clauses=len(compiled.clauses) + 8,
            max_transitions=20000,
            mode="conflict",
        )
    )
    state = without.initial(compiled)
    with pytest.raises(ConstraintFieldError):
        without.intervene(state, variable=1, excitation=1)
    with_controller = ConstraintField(
        ConstraintFieldProfile(
            max_variables=compiled.variables,
            max_clauses=len(compiled.clauses) + 8,
            max_transitions=20000,
            mode="conflict",
            controller=True,
            controller_size=4,
        )
    )
    running = with_controller.initial(compiled)
    terminal = run_to_completion(with_controller, running)
    with pytest.raises(ConstraintFieldError):
        with_controller.intervene(terminal, variable=1, excitation=1)


# -- capacity and schema negatives -------------------------------------------


def test_compile_rejects_sources_outside_the_vocabulary() -> None:
    with pytest.raises(ConstraintFieldError):
        compile_circuit(CircuitSpec(inputs=("a",), assertions=(("missing", 1),)).as_dict())
    with pytest.raises(ConstraintFieldError):
        compile_circuit(
            CircuitSpec(inputs=("a",), gates=({"op": "and", "out": "g", "args": ("a",)},)).as_dict()
        )
    with pytest.raises(ConstraintFieldError):
        compile_circuit(
            CircuitSpec(
                inputs=("a", "b"),
                gates=(
                    {"op": "xor", "out": "g", "args": ("a", "b")},
                    {"op": "buf", "out": "g", "args": ("a",)},
                ),
            ).as_dict()
        )
    with pytest.raises(ConstraintFieldError):
        compile_circuit(
            CircuitSpec(
                inputs=("a",),
                gates=(
                    {"op": "buf", "out": "g1", "args": ("g2",)},
                    {"op": "buf", "out": "g2", "args": ("g1",)},
                ),
            ).as_dict()
        )
    with pytest.raises(ConstraintFieldError):
        compile_circuit(CircuitSpec(inputs=("a",), clauses=((("a", 2),),)).as_dict())
    with pytest.raises(ConstraintFieldError):
        compile_circuit(
            CircuitSpec(inputs=("a", "b"), relations=({"kind": "xor", "args": ("a", "b"), "rhs": 2},)).as_dict()
        )
    with pytest.raises(ConstraintFieldError):
        compile_circuit(
            CircuitSpec(
                inputs=("a", "b"),
                relations=({"kind": "cardinality", "args": ("a", "b", "c"), "min": 0, "max": 3},),
            ).as_dict()
        )
    with pytest.raises(ConstraintFieldError):
        compile_circuit(CircuitSpec(inputs=("1a",)).as_dict())
    with pytest.raises(ConstraintFieldError):
        compile_transition_problem(
            TransitionProblem(
                state=("x", "y"),
                inputs=("i",),
                gates=(),
                next_state=(("x", "x"),),
                horizon=1,
            ).as_dict()
        )
    with pytest.raises(ConstraintFieldError):
        compile_transition_problem(
            TransitionProblem(
                state=("x",),
                inputs=("i",),
                gates=({"op": "xor", "out": "g", "args": ("x", "i", "i")},),
                next_state=(("x", "g"),),
                horizon=1,
            ).as_dict()
        )
    with pytest.raises(ConstraintFieldError):
        compile_transition_problem(
            TransitionProblem(
                state=("x",),
                inputs=("i",),
                gates=(),
                next_state=(("x", "x"),),
                horizon=1,
                input_assertions=((4, "i", 1),),
            ).as_dict()
        )


def test_profile_and_capacity_limits_fail_closed() -> None:
    with pytest.raises(ConstraintFieldError):
        ConstraintFieldProfile(max_variables=2, max_clauses=2, mode="unknown")
    with pytest.raises(ConstraintFieldError):
        ConstraintFieldProfile(max_variables=2, max_clauses=2, mode="local", controller=True)
    with pytest.raises(ConstraintFieldError):
        ConstraintFieldProfile(max_variables=0, max_clauses=2)
    compiled = compile_circuit(and_circuit())
    with pytest.raises(ConstraintFieldError):
        compile_circuit(and_circuit(), profile=ConstraintFieldProfile(max_variables=1, max_clauses=64))
    field = ConstraintField(ConstraintFieldProfile(max_variables=compiled.variables, max_clauses=1))
    with pytest.raises(ConstraintFieldError):
        field.initial(compiled)
    bounded = ConstraintField(
        ConstraintFieldProfile(
            max_variables=compiled.variables,
            max_clauses=len(compiled.clauses) + 8,
            max_transitions=20000,
            mode="algebraic",
            max_augmentations=0,
        )
    )
    state = run_to_completion(bounded, bounded.initial(compiled))
    assert bounded.result(state)["augmentations"] == []


def contradictory_relation_circuit() -> dict:
    """A zero-argument parity relation demanding an odd charge on nothing."""

    return CircuitSpec(
        inputs=("a",),
        relations=({"kind": "xor", "args": (), "rhs": 1},),
    ).as_dict()


def test_already_contradictory_sources_refute_in_every_configuration() -> None:
    """A compiled empty clause must refute, not crash the parity/counting field.

    The hybrid field refuses to store a contradiction as an input line, so the
    algebraic configuration must reach the same verdict as the other two.
    """

    for spec, label in (
        (contradictory_relation_circuit(), "zero-argument xor"),
        (CircuitSpec(inputs=("a",), clauses=((),)).as_dict(), "empty source clause"),
    ):
        compiled = compile_circuit(spec)
        assert compiled.clauses == ((),), label
        for mode in ("local", "conflict", "algebraic"):
            field = ConstraintField(
                ConstraintFieldProfile(max_variables=64, max_clauses=4096, mode=mode)
            )
            state = run_to_completion(field, field.initial(compiled))
            result = field.result(state)
            assert result["status"] == "unsat", (label, mode)
            assert result["witness"] is None, (label, mode)
            assert result["reason"] == (
                "propagation-refutation" if mode == "local" else "resolution-refutation"
            ), (label, mode)
            assert result["work"]["prepass"] == (
                {"status": "skipped", "reason": "compiled-contradiction"}
                if mode == "algebraic"
                else None
            ), (label, mode)
            clause_audit.audit_proof(
                [list(clause) for clause in result["backend_clauses"]],
                result["learned_clauses"],
                result["resolution_proof"],
                variables=compiled.variables,
                status="unsat",
                expected_conflicts=len(result["resolution_proof"]["conflict_derivations"]),
                max_learned_clauses=64,
            )


def test_unknown_gate_arguments_are_refused_by_compilation() -> None:
    with pytest.raises(ConstraintFieldError):
        compile_circuit(
            CircuitSpec(
                inputs=("a",),
                gates=({"op": "not", "out": "n", "args": ("zz",)},),
            ).as_dict()
        )
    with pytest.raises(ConstraintFieldError):
        compile_transition_problem(
            TransitionProblem(
                state=("x",),
                inputs=("i",),
                gates=({"op": "not", "out": "g", "args": ("zz",)},),
                next_state=(("x", "g"),),
                horizon=1,
            ).as_dict()
        )


def test_regional_constraint_kernel_quantum_one_json_resume_and_parity() -> None:
    compiled = compile_circuit(and_circuit())
    assert REGIONAL_KERNEL_NAME == "exact.constraint"
    assert REGIONAL_KERNEL_MAX_WORK > 0
    assert REGIONAL_STATE_SCHEMA == "cassifi.regional-constraint-state.v1"
    cases = (
        (
            compiled,
            ConstraintFieldProfile(
                max_variables=compiled.variables,
                max_clauses=len(compiled.clauses) + 16,
                max_transitions=20_000,
                max_learned_clauses=64,
                mode="conflict",
            ),
        ),
        (
            compile_circuit(contradiction_circuit()),
            ConstraintFieldProfile(
                max_variables=2,
                max_clauses=32,
                max_transitions=20_000,
                max_learned_clauses=64,
                mode="conflict",
            ),
        ),
        (
            compile_circuit(contradiction_circuit()),
            ConstraintFieldProfile(
                max_variables=2,
                max_clauses=32,
                max_transitions=20_000,
                max_learned_clauses=64,
                mode="algebraic",
            ),
        ),
        (
            compiled,
            ConstraintFieldProfile(
                max_variables=compiled.variables,
                max_clauses=len(compiled.clauses) + 16,
                max_transitions=1,
                max_learned_clauses=64,
                mode="conflict",
            ),
        ),
    )
    for source, profile in cases:
        expected = solve(
            source,
            mode=profile.mode,
            max_transitions=profile.max_transitions,
            max_learned_clauses=profile.max_learned_clauses,
        )[2]
        current = regional_state(source, profile)
        yielded = False
        terminal = None
        for _ in range(20_000):
            round_tripped = json.loads(json.dumps(current, sort_keys=True))
            receipt = regional_kernel(round_tripped, {}, quantum=1)
            assert 0 <= receipt.work <= 1
            successor = json.loads(json.dumps(receipt.state, sort_keys=True))
            assert successor == json.loads(json.dumps(successor, sort_keys=True))
            if receipt.status == "yield":
                yielded = True
                assert successor != current
                current = successor
                continue
            assert receipt.status == "done"
            terminal = receipt.output
            current = successor
            break
        assert terminal is not None
        assert yielded
        assert terminal["status"] == expected["status"]
        assert terminal["reason"] == expected["reason"]
        assert terminal["witness"] == expected["witness"]
        assert (terminal["resolution_proof"] is None) == (
            expected["resolution_proof"] is None
        )
        assert (terminal["hybrid_proof"] is None) == (expected["hybrid_proof"] is None)
        repeated = regional_kernel(current, {}, quantum=1)
        assert repeated.status == "done"
        assert repeated.output == terminal
