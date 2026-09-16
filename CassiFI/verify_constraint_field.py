"""Independent verification suite for ``cassi_constraint_field.py``.

The suite re-implements the documented constraint-source semantics from the
vocabulary alone: its own gate truth tables, its own clause/relation/assertion
evaluation, its own exhaustive enumerator, and its own bounded transition
simulator.  Nothing is taken from the field module's internals; the module is
used only through its public API, plus the two independent certificate checkers
already audited in this repository (``verify_p_vs_np_clause_field_probe`` and
``verify_hybrid_inference``).

Every check is reported as ``{name, passed, detail}``; the process exits
nonzero if any check fails.  Truth-table claims are made only where
``2 ** free_variables <= 2 ** 16``; anything larger is reported as outside
enumeration scope.

Checks
------
``gate_equivalence``        single-gate CNF model sets versus the own truth table of
                            const/buf/not/and/or/xor/nand/nor/xnor/mux
``circuit_equivalence``     every input assignment of 32 mixed sources versus the field
                            verdict, plus witness replay through the own evaluator
``transition_equivalence``  every initial state and input trace of 15 bounded systems
                            versus the field verdict, plus witness replay through the own simulator
``mode_agreement``          local/conflict/algebraic verdicts, intermediate status
                            vocabulary, and the exhausted claim discipline
``certificate_audit``       every UNSAT resolution certificate and every algebraic hybrid
                            proof audited with the two independent checkers
``checkpoint_fidelity``     descriptor round-trip and resume equality at every intermediate step
``tamper_matrix``           each descriptor field mutated independently must be refused
``negative_capacity``       capacity, boundary, arity, relation, and enumeration-limit refusals
``exhausted_honesty``       bounded runs report exhausted without claiming any artefact
``controller_integration``  controller selections, determinism, and journaled interventions

Usage:  python verify_constraint_field.py [--json PATH]
"""

from __future__ import annotations

import argparse
import base64
import copy
import itertools
import json
import sys
import time
from typing import Any, Callable, Mapping, Sequence

from cassi_constraint_field import (
    ConstraintField,
    ConstraintFieldError,
    ConstraintFieldProfile,
    compile_circuit,
    compile_transition_problem,
)
from verify_hybrid_inference import audit_proof as audit_hybrid_proof
from verify_p_vs_np_clause_field_probe import audit_proof as audit_resolution_proof

# --------------------------------------------------------------------------
# vocabulary (frozen contract)
# --------------------------------------------------------------------------

MODE_NAMES = ("local", "conflict", "algebraic")
REASON_VOCABULARY: dict[str, tuple[str, ...]] = {
    "running": ("prepass", "search"),
    "sat": ("model",),
    "unsat": ("hybrid-refutation", "resolution-refutation", "propagation-refutation"),
    "exhausted": (
        "transition-budget",
        "backend-exhausted",
        "local-stall",
        "proof-journal-capacity",
    ),
}
ENUMERATION_EXPONENT_LIMIT = 16
BASE_PROFILE: dict[str, int] = {
    "max_variables": 64,
    "max_clauses": 4096,
    "max_learned_clauses": 128,
    "max_transitions": 10_000,
}


class ReferenceError_(Exception):
    """A source is outside what the independent reference semantics define."""


# --------------------------------------------------------------------------
# independent reference semantics
# --------------------------------------------------------------------------

GATE_ARITY: dict[str, int] = {
    "const": 0,
    "buf": 1,
    "not": 1,
    "and": 2,
    "or": 2,
    "xor": 2,
    "nand": 2,
    "nor": 2,
    "xnor": 2,
    "mux": 3,
}
GATE_OPS: tuple[str, ...] = tuple(GATE_ARITY)


def gate_value(op: str, bits: Sequence[int], value: int | None = None) -> int:
    """Own truth table, written from the operation names only."""

    if op == "const":
        if value not in (0, 1):
            raise ReferenceError_(f"const gate needs a 0/1 value, got {value!r}")
        return int(value)
    if op == "buf":
        return bits[0]
    if op == "not":
        return 1 - bits[0]
    first, second = bits[0], bits[1]
    if op == "and":
        return 1 if (first and second) else 0
    if op == "or":
        return 1 if (first or second) else 0
    if op == "xor":
        return first ^ second
    if op == "nand":
        return 0 if (first and second) else 1
    if op == "nor":
        return 0 if (first or second) else 1
    if op == "xnor":
        return 0 if (first ^ second) else 1
    if op == "mux":
        select, when_true, when_false = bits
        return when_true if select else when_false
    raise ReferenceError_(f"unsupported gate operation {op!r}")


def gate_truth_table(op: str, value: int | None = None) -> dict[tuple[int, ...], int]:
    arity = GATE_ARITY[op]
    return {
        tuple(bits): gate_value(op, bits, value)
        for bits in itertools.product((0, 1), repeat=arity)
    }


def topological_gates(
    gates: Sequence[Mapping[str, Any]],
    known: Sequence[str] = (),
) -> list[Mapping[str, Any]]:
    """Own topological sort of a gate DAG (raises on cycles)."""

    by_out = {str(gate["out"]): gate for gate in gates}
    order: list[Mapping[str, Any]] = []
    resolved: set[str] = {str(name) for name in known}
    pending = dict(by_out)
    while pending:
        progressed = False
        for name in sorted(pending):
            if all(str(argument) in resolved for argument in pending[name]["args"]):
                order.append(pending.pop(name))
                resolved.add(name)
                progressed = True
        if not progressed:
            raise ReferenceError_(f"cyclic gate graph over {sorted(pending)}")
    return order


def evaluate_gates(
    gates: Sequence[Mapping[str, Any]],
    values: Mapping[str, int],
) -> dict[str, int]:
    """Evaluate every gate over a mapping that already holds its inputs."""

    resolved = dict(values)
    for gate in topological_gates(gates, list(values)):
        out = str(gate["out"])
        op = str(gate["op"])
        if op == "const":
            resolved[out] = gate_value(op, (), int(gate["value"]))
            continue
        arguments = [str(argument) for argument in gate["args"]]
        bits = []
        for argument in arguments:
            if argument not in resolved:
                raise ReferenceError_(f"gate {out!r} uses unresolved signal {argument!r}")
            bits.append(resolved[argument])
        resolved[out] = gate_value(op, bits)
    return resolved


def literal_holds(values: Mapping[str, int], literal: Sequence[Any]) -> bool:
    """Source literal ``(signal, polarity)`` holds iff the signal equals polarity."""

    return values[str(literal[0])] == int(literal[1])


def clause_holds(values: Mapping[str, int], clause: Sequence[Any]) -> bool:
    return any(literal_holds(values, literal) for literal in clause)


def relation_holds(values: Mapping[str, int], relation: Mapping[str, Any]) -> bool:
    arguments = [str(name) for name in relation["args"]]
    missing = [name for name in arguments if name not in values]
    if missing:
        raise ReferenceError_(f"relation uses unknown signals {missing}")
    total = sum(int(values[name]) for name in arguments)
    kind = str(relation["kind"])
    if kind == "xor":
        # duplicates cancel in pairs: only the parity of the multiset counts
        return total % 2 == int(relation["rhs"])
    if kind == "cardinality":
        return int(relation["min"]) <= total <= int(relation["max"])
    raise ReferenceError_(f"unsupported relation kind {kind!r}")


def assertions_hold(
    values: Mapping[str, int],
    rows: Sequence[Sequence[Any]],
) -> bool:
    for row in rows:
        name, bit = str(row[0]), int(row[1])
        if name not in values or int(values[name]) != bit:
            return False
    return True


def circuit_accepts(spec: Mapping[str, Any], scope: Mapping[str, int]) -> bool:
    """True iff one complete input assignment satisfies the whole source."""

    values = evaluate_gates(spec["gates"], scope)
    if not assertions_hold(values, spec["assertions"]):
        return False
    for clause in spec["clauses"]:
        if not clause_holds(values, clause):
            return False
    for relation in spec["relations"]:
        if not relation_holds(values, relation):
            return False
    return True


def reference_circuit(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Exhaustive reference verdict for a combinational circuit."""

    inputs = [str(name) for name in spec["inputs"]]
    free = len(inputs)
    summary: dict[str, Any] = {"free_variables": free, "enumerated": 2**free <= 2**ENUMERATION_EXPONENT_LIMIT}
    if not summary["enumerated"]:
        summary.update({"satisfiable": None, "models": None, "sample": None})
        return summary
    models = 0
    sample: dict[str, Any] | None = None
    for bits in itertools.product((0, 1), repeat=free):
        scope = dict(zip(inputs, bits))
        if circuit_accepts(spec, scope):
            models += 1
            if sample is None:
                sample = dict(scope)
    summary.update({"satisfiable": models > 0, "models": models, "sample": sample})
    return summary


def reference_transition(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Exhaustive reference verdict for a bounded synchronous system."""

    states = [str(name) for name in spec["state"]]
    inputs = [str(name) for name in spec["inputs"]]
    horizon = int(spec["horizon"])
    free = len(states) + len(inputs) * horizon
    summary: dict[str, Any] = {"free_variables": free, "enumerated": 2**free <= 2**ENUMERATION_EXPONENT_LIMIT}
    if not summary["enumerated"]:
        summary.update({"satisfiable": None, "models": None, "sample": None})
        return summary
    models = 0
    sample: dict[str, Any] | None = None
    for bits in itertools.product((0, 1), repeat=free):
        initial = dict(zip(states, bits[: len(states)]))
        flat = bits[len(states) :]
        trace = [
            dict(zip(inputs, flat[time * len(inputs) : (time + 1) * len(inputs)]))
            for time in range(horizon)
        ]
        problems = simulate_transition(spec, initial, trace)
        if not problems:
            models += 1
            if sample is None:
                sample = {"initial": initial, "trace": trace}
    summary.update({"satisfiable": models > 0, "models": models, "sample": sample})
    return summary


def simulate_transition(
    spec: Mapping[str, Any],
    initial: Mapping[str, int],
    trace: Sequence[Mapping[str, int]],
) -> list[str]:
    """Own replay of one initial state plus one complete input trace."""

    inputs = [str(name) for name in spec["inputs"]]
    horizon = int(spec["horizon"])
    problems: list[str] = []
    if len(trace) != horizon:
        raise ReferenceError_(f"trace of {len(trace)} steps does not match horizon {horizon}")

    scopes: list[dict[str, int]] = []
    state_values = [dict(initial)]
    for time in range(horizon):
        scope = dict(state_values[time])
        for name in inputs:
            if name not in trace[time]:
                raise ReferenceError_(f"trace step {time} misses input {name!r}")
            scope[name] = int(trace[time][name])
        scope = evaluate_gates(spec["gates"], scope)
        scopes.append(scope)
        successor: dict[str, int] = {}
        for target, origin in assertable_next(spec):
            if target not in state_values[time]:
                raise ReferenceError_(f"next_state writes unknown state {target!r}")
            if origin not in scope:
                raise ReferenceError_(f"next_state {target!r} reads unresolved {origin!r} at step {time}")
            successor[target] = scope[origin]
        state_values.append(successor)

    if not assertions_hold(state_values[0], spec["initial"]):
        problems.append("initial row violated")
    for row in spec["input_assertions"]:
        time, name, bit = int(row[0]), str(row[1]), int(row[2])
        if time >= horizon:
            raise ReferenceError_(f"input assertion at time {time} lies past the horizon")
        if int(trace[time][name]) != bit:
            problems.append(f"input assertion at time {time} on {name!r} violated")
    if scopes:
        for clause in spec["clauses"]:
            if not clause_holds(scopes[0], clause):
                problems.append("source clause violated at time 0")
        for time, scope in enumerate(scopes):
            for relation in spec["relations"]:
                if not relation_holds(scope, relation):
                    problems.append(f"relation at time {time} violated")
    elif spec["clauses"] or spec["relations"]:
        raise ReferenceError_("horizon 0 cannot resolve gate, input, or relational scopes")

    final_values = state_values[horizon]
    if not assertions_hold(final_values, spec["final"]):
        problems.append("final row violated")
    return problems


def assertable_next(spec: Mapping[str, Any]) -> list[tuple[str, str]]:
    return [(str(row[0]), str(row[1])) for row in spec["next_state"]]


# --------------------------------------------------------------------------
# sources under test
# --------------------------------------------------------------------------


def c(
    inputs: Sequence[str],
    gates: Sequence[Mapping[str, Any]] = (),
    assertions: Sequence[Sequence[Any]] = (),
    relations: Sequence[Mapping[str, Any]] = (),
    clauses: Sequence[Sequence[Sequence[Any]]] = (),
) -> dict[str, Any]:
    return {
        "kind": "circuit",
        "inputs": [str(name) for name in inputs],
        "gates": [dict(gate) for gate in gates],
        "assertions": [[str(row[0]), int(row[1])] for row in assertions],
        "relations": [dict(row) for row in relations],
        "clauses": [[[str(literal[0]), int(literal[1])] for literal in clause] for clause in clauses],
    }


def t(
    state: Sequence[str],
    inputs: Sequence[str],
    gates: Sequence[Mapping[str, Any]],
    next_state: Sequence[Sequence[str]],
    horizon: int,
    initial: Sequence[Sequence[Any]] = (),
    input_assertions: Sequence[Sequence[Any]] = (),
    final: Sequence[Sequence[Any]] = (),
    relations: Sequence[Mapping[str, Any]] = (),
    clauses: Sequence[Sequence[Sequence[Any]]] = (),
) -> dict[str, Any]:
    return {
        "kind": "transition",
        "state": [str(name) for name in state],
        "inputs": [str(name) for name in inputs],
        "gates": [dict(gate) for gate in gates],
        "next_state": [[str(row[0]), str(row[1])] for row in next_state],
        "horizon": int(horizon),
        "initial": [[str(row[0]), int(row[1])] for row in initial],
        "input_assertions": [[int(row[0]), str(row[1]), int(row[2])] for row in input_assertions],
        "final": [[str(row[0]), int(row[1])] for row in final],
        "relations": [dict(row) for row in relations],
        "clauses": [[[str(literal[0]), int(literal[1])] for literal in clause] for clause in clauses],
    }


def parity_block(names: Sequence[str], rhs: int) -> list[list[list[Any]]]:
    """Source clauses encoding ``xor(names) == rhs`` (forbidding the other parity)."""

    rows = []
    for bits in itertools.product((0, 1), repeat=len(names)):
        if sum(bits) % 2 != rhs:
            rows.append([[name, 1 - bit] for name, bit in zip(names, bits)])
    return rows


def by_name(instances: Sequence[tuple[str, dict[str, Any], str]], name: str) -> tuple[str, dict[str, Any], str]:
    for entry in instances:
        if entry[0] == name:
            return entry
    raise KeyError(f"no instance named {name!r}")


def circuit_named(name: str) -> dict[str, Any]:
    return copy.deepcopy(by_name(circuit_instances(), name)[1])


def transition_named(name: str) -> dict[str, Any]:
    return copy.deepcopy(by_name(transition_instances(), name)[1])


def pigeonhole_clauses(pigeons: int, holes: int) -> list[list[list[Any]]]:
    """Own pigeonhole CNF: every pigeon in a hole, no hole with two pigeons."""

    rows: list[list[list[Any]]] = []
    for pigeon in range(1, pigeons + 1):
        rows.append([[f"p{pigeon}h{hole}", 1] for hole in range(1, holes + 1)])
    for hole in range(1, holes + 1):
        for first in range(1, pigeons + 1):
            for second in range(first + 1, pigeons + 1):
                rows.append([[f"p{first}h{hole}", 0], [f"p{second}h{hole}", 0]])
    return rows


def circuit_instances() -> list[tuple[str, dict[str, Any], str]]:
    return [
        (
            "and_assertion_sat",
            c(["a", "b"], [{"op": "and", "out": "g", "args": ["a", "b"]}], [["g", 1]]),
            "single and gate forced true",
        ),
        (
            "and_assertion_unsat",
            c(["a", "b"], [{"op": "and", "out": "g", "args": ["a", "b"]}], [["a", 0], ["g", 1]]),
            "and gate forced true while an input is false",
        ),
        (
            "or_chain_sat",
            c(
                ["a", "b", "c"],
                [
                    {"op": "or", "out": "g", "args": ["a", "b"]},
                    {"op": "and", "out": "h", "args": ["g", "c"]},
                ],
                [["h", 1], ["a", 0]],
            ),
            "mixed or/and chain",
        ),
        (
            "nand_nor_xnor_sat",
            c(
                ["a", "b", "c"],
                [
                    {"op": "nand", "out": "n", "args": ["a", "b"]},
                    {"op": "nor", "out": "o", "args": ["b", "c"]},
                    {"op": "xnor", "out": "z", "args": ["n", "o"]},
                ],
                [["z", 1], ["a", 1], ["b", 0]],
            ),
            "nand/nor/xnor composition",
        ),
        (
            "mux_select_sat",
            c(
                ["s", "t", "f"],
                [{"op": "mux", "out": "m", "args": ["s", "t", "f"]}],
                [["s", 1], ["t", 1], ["f", 0], ["m", 1]],
            ),
            "mux selects the true branch",
        ),
        (
            "mux_select_unsat",
            c(
                ["s", "t", "f"],
                [{"op": "mux", "out": "m", "args": ["s", "t", "f"]}],
                [["s", 0], ["t", 1], ["f", 0], ["m", 1]],
            ),
            "mux selects the false branch but m is forced true",
        ),
        (
            "const_gates_sat",
            c(
                ["a", "d"],
                [
                    {"op": "const", "out": "one", "args": [], "value": 1},
                    {"op": "const", "out": "zero", "args": [], "value": 0},
                    {"op": "and", "out": "g", "args": ["one", "a"]},
                    {"op": "or", "out": "h", "args": ["g", "zero"]},
                    {"op": "buf", "out": "k", "args": ["d"]},
                ],
                [["h", 1], ["a", 1], ["k", 0], ["d", 0]],
            ),
            "const gates plus buf",
        ),
        (
            "const_contradiction_unsat",
            c(
                ["a"],
                [{"op": "const", "out": "one", "args": [], "value": 1}],
                [["one", 0]],
            ),
            "const one contradicted by an assertion",
        ),
        (
            "not_gate_sat",
            c(["a"], [{"op": "not", "out": "n", "args": ["a"]}], [["n", 1]]),
            "not gate",
        ),
        (
            "xor_relation_sat",
            c(
                ["a", "b", "c"],
                [{"op": "xor", "out": "p", "args": ["a", "b"]}],
                [["p", 0]],
                [{"kind": "xor", "args": ["p", "c"], "rhs": 1}],
            ),
            "xor relation over a gate output",
        ),
        (
            "xor_relation_unsat",
            c(
                ["a", "b", "c"],
                [],
                [["a", 0], ["b", 0], ["c", 0]],
                [{"kind": "xor", "args": ["a", "b", "c"], "rhs": 1}],
            ),
            "three-way parity contradicted by all-zero assertions",
        ),
        (
            "xor_duplicate_cancel_sat",
            c(
                ["a", "b", "c"],
                [],
                [["b", 1], ["c", 1]],
                [{"kind": "xor", "args": ["a", "a", "b", "c"], "rhs": 0}],
            ),
            "duplicate xor argument cancels in pairs",
        ),
        (
            "xor_duplicate_cancel_unsat",
            c(
                ["a", "b", "c"],
                [],
                [["b", 1], ["c", 0]],
                [{"kind": "xor", "args": ["a", "a", "b", "c"], "rhs": 0}],
            ),
            "duplicate xor argument cancels, remaining parity is violated",
        ),
        (
            "xor_zero_argument_sat",
            c(["a"], [], [], [{"kind": "xor", "args": [], "rhs": 0}]),
            "empty xor relation with rhs 0",
        ),
        (
            "xor_zero_argument_unsat",
            c(["a"], [], [], [{"kind": "xor", "args": [], "rhs": 1}]),
            "empty xor relation with rhs 1",
        ),
        (
            "xor_single_argument_sat",
            c(["a", "b"], [], [["a", 1]], [{"kind": "xor", "args": ["a"], "rhs": 1}]),
            "one-argument xor relation",
        ),
        (
            "xor_single_argument_unsat",
            c(["a", "b"], [], [["a", 0]], [{"kind": "xor", "args": ["a"], "rhs": 1}]),
            "one-argument xor relation contradicted",
        ),
        (
            "xor_wide_parity_12",
            c(
                [f"v{index}" for index in range(12)],
                [],
                [["v0", 1], ["v1", 0], ["v2", 1]],
                [{"kind": "xor", "args": [f"v{index}" for index in range(12)], "rhs": 1}],
            ),
            "twelve-way parity (4096 free assignments, still inside enumeration scope)",
        ),
        (
            "cardinality_mid_sat",
            c(["a", "b", "c", "d"], [], [], [{"kind": "cardinality", "args": ["a", "b", "c", "d"], "min": 2, "max": 3}]),
            "cardinality window",
        ),
        (
            "cardinality_boundary_sat",
            c(
                ["a", "b", "c", "d"],
                [],
                [["a", 0], ["b", 0], ["c", 1], ["d", 1]],
                [{"kind": "cardinality", "args": ["a", "b", "c", "d"], "min": 2, "max": 3}],
            ),
            "cardinality window at its lower bound",
        ),
        (
            "cardinality_boundary_unsat",
            c(
                ["a", "b", "c", "d"],
                [],
                [["a", 0], ["b", 0], ["c", 1], ["d", 0]],
                [{"kind": "cardinality", "args": ["a", "b", "c", "d"], "min": 2, "max": 3}],
            ),
            "cardinality window violated below its bound",
        ),
        (
            "cardinality_exact_unsat",
            c(
                ["a", "b"],
                [],
                [["a", 0]],
                [{"kind": "cardinality", "args": ["a", "b"], "min": 2, "max": 2}],
            ),
            "exact cardinality contradicted",
        ),
        (
            "cardinality_zero_argument_sat",
            c([], [], [], [{"kind": "cardinality", "args": [], "min": 0, "max": 0}]),
            "empty cardinality relation",
        ),
        (
            "source_clause_tautology_sat",
            c(
                ["a", "b"],
                [{"op": "buf", "out": "g", "args": ["a"]}],
                [["b", 0]],
                [],
                [[["a", 1], ["a", 0]], [["g", 1], ["b", 1]]],
            ),
            "tautological source clause plus a real clause",
        ),
        (
            "source_clause_contradiction_unsat",
            c(["a"], [], [], [], [[["a", 1]], [["a", 0]]]),
            "two contradictory unit source clauses",
        ),
        (
            "parity_clause_cluster_augment",
            c(
                ["a", "b", "c"],
                [],
                [],
                [],
                parity_block(["a", "b"], 0) + parity_block(["a", "b", "c"], 1),
            ),
            "parity clause cluster whose prepass admits a singleton fact",
        ),
        (
            "parity_clause_cluster_contradiction_unsat",
            c(
                ["a", "b", "c"],
                [],
                [["a", 1]],
                [],
                parity_block(["a", "b"], 0) + parity_block(["b", "c"], 0) + parity_block(["a", "c"], 1),
            ),
            "inconsistent parity cluster (algebraic prepass refutes)",
        ),
        (
            "mixed_circuit_sat",
            c(
                ["a", "b", "c", "d", "e", "f"],
                [
                    {"op": "xor", "out": "p", "args": ["a", "b"]},
                    {"op": "or", "out": "q", "args": ["c", "d"]},
                    {"op": "and", "out": "r", "args": ["p", "e"]},
                    {"op": "mux", "out": "m", "args": ["r", "q", "f"]},
                    {"op": "not", "out": "n", "args": ["d"]},
                    {"op": "nand", "out": "k", "args": ["n", "c"]},
                ],
                [["m", 1], ["r", 1], ["k", 0]],
                [{"kind": "cardinality", "args": ["c", "d", "f"], "min": 1, "max": 2}],
                [[["q", 1], ["f", 0]]],
            ),
            "six-input mixed gate, relation, and clause circuit",
        ),
        (
            "mixed_circuit_unsat",
            c(
                ["a", "b", "c", "d"],
                [
                    {"op": "xor", "out": "p", "args": ["a", "b"]},
                    {"op": "xor", "out": "q", "args": ["c", "d"]},
                    {"op": "and", "out": "r", "args": ["p", "q"]},
                ],
                [["a", 1], ["a", 0]],
                [{"kind": "xor", "args": ["p", "q"], "rhs": 1}],
            ),
            "assertion contradiction over a parity pair",
        ),
        (
            "empty_circuit_sat",
            c([], [], [], [], []),
            "no inputs, no gates, no requirements",
        ),
        (
            "pigeonhole_three_into_two_unsat",
            c(
                [f"p{pigeon}h{hole}" for pigeon in range(1, 4) for hole in range(1, 3)],
                [],
                [],
                [],
                pigeonhole_clauses(3, 2),
            ),
            "pigeonhole 3 into 2: no unit propagation at the root, real decisions required",
        ),
        (
            "empty_circuit_const_unsat",
            c([], [{"op": "const", "out": "z", "args": [], "value": 0}], [["z", 1]]),
            "internal constant contradicted",
        ),
    ]


def transition_instances() -> list[tuple[str, dict[str, Any], str]]:
    return [
        (
            "h0_hold_sat",
            t(["s"], [], [], [["s", "s"]], 0, initial=[["s", 1]], final=[["s", 1]]),
            "horizon 0 with a satisfied boundary",
        ),
        (
            "h0_hold_unsat",
            t(["s"], [], [], [["s", "s"]], 0, initial=[["s", 1]], final=[["s", 0]]),
            "horizon 0 with contradictory boundaries",
        ),
        (
            "h1_xor_sat",
            t(
                ["s"],
                ["x"],
                [{"op": "xor", "out": "g", "args": ["x", "s"]}],
                [["s", "g"]],
                1,
                initial=[["s", 0]],
                input_assertions=[[0, "x", 1]],
                final=[["s", 1]],
            ),
            "one step of an xor transition",
        ),
        (
            "h1_xor_unsat",
            t(
                ["s"],
                ["x"],
                [{"op": "xor", "out": "g", "args": ["x", "s"]}],
                [["s", "g"]],
                1,
                initial=[["s", 0]],
                input_assertions=[[0, "x", 1]],
                final=[["s", 0]],
            ),
            "one step of an xor transition with a wrong final boundary",
        ),
        (
            "h2_mux_sat",
            t(
                ["s"],
                ["x", "y"],
                [
                    {"op": "mux", "out": "m", "args": ["x", "y", "s"]},
                    {"op": "or", "out": "o", "args": ["x", "y"]},
                ],
                [["s", "m"]],
                2,
                initial=[["s", 1]],
                input_assertions=[[1, "x", 0]],
                final=[["s", 0]],
            ),
            "two steps with a mux transition and two inputs",
        ),
        (
            "h2_mux_unsat",
            t(
                ["s"],
                ["x"],
                [
                    {"op": "not", "out": "n", "args": ["x"]},
                    {"op": "mux", "out": "m", "args": ["x", "n", "s"]},
                ],
                [["s", "m"]],
                2,
                initial=[["s", 0]],
                input_assertions=[[0, "x", 1], [1, "x", 1]],
                final=[["s", 1]],
            ),
            "mux into not(x) never reaches one",
        ),
        (
            "h2_state_only_sat",
            t(
                ["s"],
                [],
                [{"op": "not", "out": "n", "args": ["s"]}],
                [["s", "n"]],
                2,
                initial=[["s", 1]],
                final=[["s", 1]],
            ),
            "unclocked two-step oscillator",
        ),
        (
            "h2_state_only_unsat",
            t(
                ["s"],
                [],
                [{"op": "not", "out": "n", "args": ["s"]}],
                [["s", "n"]],
                2,
                initial=[["s", 1]],
                final=[["s", 0]],
            ),
            "oscillator with a wrong final boundary",
        ),
        (
            "h3_two_state_hold_sat",
            t(
                ["p", "q"],
                ["x"],
                [
                    {"op": "xor", "out": "d", "args": ["p", "q"]},
                    {"op": "and", "out": "e", "args": ["d", "x"]},
                ],
                [["p", "e"], ["q", "p"]],
                3,
                initial=[["p", 0], ["q", 1]],
                input_assertions=[[0, "x", 1], [1, "x", 1], [2, "x", 1]],
                final=[["p", 0]],
            ),
            "three steps over two state names",
        ),
        (
            "h3_two_state_hold_unsat",
            t(
                ["p", "q"],
                ["x"],
                [
                    {"op": "xor", "out": "d", "args": ["p", "q"]},
                    {"op": "and", "out": "e", "args": ["d", "x"]},
                ],
                [["p", "e"], ["q", "p"]],
                3,
                initial=[["p", 0], ["q", 1]],
                input_assertions=[[0, "x", 1], [1, "x", 1], [2, "x", 1]],
                final=[["q", 0]],
            ),
            "three steps with an unreachable final boundary",
        ),
        (
            "h3_three_state_sat",
            t(
                ["a", "b", "c"],
                ["x"],
                [
                    {"op": "and", "out": "g1", "args": ["a", "b"]},
                    {"op": "or", "out": "g2", "args": ["b", "c"]},
                    {"op": "xor", "out": "g3", "args": ["g1", "x"]},
                ],
                [["a", "g3"], ["b", "g2"], ["c", "g1"]],
                3,
                initial=[["a", 1], ["b", 1], ["c", 0]],
                input_assertions=[[2, "x", 1]],
                final=[["b", 1]],
            ),
            "three state names and a mixed gate layer",
        ),
        (
            "h2_relation_sat",
            t(
                ["s"],
                ["x"],
                [],
                [["s", "s"]],
                2,
                initial=[["s", 0]],
                input_assertions=[[0, "x", 1]],
                final=[["s", 0]],
                relations=[{"kind": "xor", "args": ["s", "x"], "rhs": 1}],
            ),
            "parity relation imposed at every time step",
        ),
        (
            "h2_cardinality_unsat",
            t(
                ["s"],
                ["x"],
                [],
                [["s", "s"]],
                2,
                initial=[["s", 1]],
                final=[["s", 1]],
                relations=[{"kind": "cardinality", "args": ["s", "x"], "min": 1, "max": 1}],
            ),
            "exactly-one relation with a held state",
        ),
        (
            "h1_clause_sat",
            t(
                ["s"],
                ["x"],
                [{"op": "buf", "out": "g", "args": ["x"]}],
                [["s", "g"]],
                1,
                initial=[["s", 0]],
                final=[["s", 0]],
                clauses=[[["s", 1], ["x", 0]]],
            ),
            "source clause over the initial state and input",
        ),
        (
            "h1_clause_unsat",
            t(
                ["s"],
                ["x"],
                [{"op": "buf", "out": "g", "args": ["x"]}],
                [["s", "g"]],
                1,
                initial=[["s", 0]],
                final=[["s", 1]],
                clauses=[[["s", 1], ["x", 0]]],
            ),
            "source clause forcing x0 false with a final boundary needing it true",
        ),
    ]


# --------------------------------------------------------------------------
# report plumbing
# --------------------------------------------------------------------------


class Report:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []
        self.observations: list[dict[str, str]] = []
        self.scope_lines: list[str] = []

    def add(self, name: str, failures: Sequence[str], detail: dict[str, Any]) -> None:
        payload = dict(detail)
        payload["failures"] = list(failures)
        self.checks.append({"name": name, "passed": not failures, "detail": payload})

    def observe(self, name: str, detail: str) -> None:
        self.observations.append({"observation": name, "detail": detail})

    def scope(self, line: str) -> None:
        self.scope_lines.append(line)


def make_profile(mode: str, **overrides: Any) -> ConstraintFieldProfile:
    values: dict[str, Any] = dict(BASE_PROFILE)
    values["mode"] = mode
    values.update(overrides)
    return ConstraintFieldProfile(**values)


def solve_instance(
    compiled: Any,
    mode: str,
    **overrides: Any,
) -> tuple[ConstraintField, Any, dict[str, Any]]:
    field = ConstraintField(make_profile(mode, **overrides))
    state = field.initial(compiled)
    final, result = field.solve(state)
    return field, final, dict(result)


def collect_run(
    compiled: Any,
    mode: str,
    **overrides: Any,
) -> dict[str, Any]:
    """Solve one instance, turning any raised exception into a reportable record."""

    try:
        _field, _state, result = solve_instance(compiled, mode, **overrides)
    except Exception as exc:  # noqa: BLE001 - a raised exception is itself a finding
        return {"crash": f"{type(exc).__name__}: {exc}"}
    result["crash"] = None
    return result


def vocabulary_ok(status: str, reason: str) -> bool:
    return status in REASON_VOCABULARY and reason in REASON_VOCABULARY[status]


STEP_SCHEMA = "cassifi.constraint-step.v1"

# the documented members of result['work']; the container itself may gain keys
WORK_KEYS = ("compile", "prepass", "hybrid", "search", "controller", "journal_bytes", "augmentations")


def compiled_contradiction(clauses: Sequence[Sequence[int]]) -> bool:
    """True iff the compiled clause list already carries the empty clause."""

    return any(len(clause) == 0 for clause in clauses)


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------


def check_gate_equivalence(report: Report) -> None:
    failures: list[str] = []
    cases = 0
    for op in GATE_OPS:
        arguments = [f"x{index}" for index in range(GATE_ARITY[op])]
        values = (0, 1) if op == "const" else (None,)
        for value in values:
            gate: dict[str, Any] = {"op": op, "out": "y", "args": list(arguments)}
            if op == "const":
                gate["value"] = value
            spec = c(arguments, [gate])
            compiled = compile_circuit(spec)
            out_id = dict((str(name), int(identifier)) for name, identifier in compiled.payload["signals"])["y"]
            argument_ids = [
                dict((str(name), int(identifier)) for name, identifier in compiled.payload["signals"])[name]
                for name in arguments
            ]
            compiled_clauses = compiled.payload["clauses"]
            models: set[tuple[int, ...]] = set()
            for assignment in itertools.product((0, 1), repeat=compiled.variables):
                if all(
                    any(assignment[abs(literal) - 1] == (1 if literal > 0 else 0) for literal in clause)
                    for clause in compiled_clauses
                ):
                    models.add(
                        tuple(assignment[identifier - 1] for identifier in argument_ids)
                        + (assignment[out_id - 1],)
                    )
            table = {
                bits + (result,)
                for bits, result in gate_truth_table(op, value).items()
            }
            cases += 1
            if models != table:
                failures.append(
                    f"{op}{'' if value is None else f'(value={value})'}: "
                    f"compiled models {sorted(models)} != own truth table {sorted(table)}"
                )
    report.add(
        "gate_equivalence",
        failures,
        {
            "gate_cases": cases,
            "operations": list(GATE_OPS),
            "scope": "single-gate CNF enumerated over all variables; projection onto (args, out)",
        },
    )


def check_circuit_equivalence(report: Report, runs: dict[tuple[str, str], dict[str, Any]]) -> None:
    failures: list[str] = []
    in_scope = 0
    out_of_scope: list[str] = []
    sat_instances = 0
    unsat_instances = 0
    witnesses_checked = 0
    for name, spec, _note in circuit_instances():
        reference = reference_circuit(spec)
        if not reference["enumerated"]:
            out_of_scope.append(name)
            report.scope(
                f"OUTSIDE ENUMERATION SCOPE: circuit {name} has {reference['free_variables']} free "
                f"variables (2**{reference['free_variables']} > 2**{ENUMERATION_EXPONENT_LIMIT}); "
                "no truth-table claim is made for it."
            )
            continue
        in_scope += 1
        report.scope(
            f"enumeration scope ok: circuit {name} free={reference['free_variables']} "
            f"models={reference['models']}"
        )
        if reference["satisfiable"]:
            sat_instances += 1
        else:
            unsat_instances += 1
        for mode in MODE_NAMES:
            result = runs[(name, mode)]
            if result["crash"] is not None:
                failures.append(f"{name}/{mode}: raised {result['crash']}")
                continue
            if result["status"] == "sat":
                witness = result["witness"]
                if not isinstance(witness, Mapping):
                    failures.append(f"{name}/{mode}: sat without a witness mapping")
                    continue
                missing = [name_ for name_ in spec["inputs"] if name_ not in witness]
                if missing:
                    failures.append(f"{name}/{mode}: witness misses inputs {missing}")
                    continue
                scope = {input_name: int(witness[input_name]) for input_name in spec["inputs"]}
                try:
                    accepted = circuit_accepts(spec, scope)
                except ReferenceError_ as exc:
                    failures.append(f"{name}/{mode}: reference could not evaluate the witness: {exc}")
                    continue
                witnesses_checked += 1
                if not accepted:
                    failures.append(
                        f"{name}/{mode}: reported sat witness {scope} violates the source"
                    )
                if mode == "conflict" and not reference["satisfiable"]:
                    failures.append(f"{name}/conflict: reported sat for an unsatisfiable circuit")
            elif result["status"] == "unsat":
                if mode == "conflict" and reference["satisfiable"]:
                    failures.append(f"{name}/conflict: reported unsat for a satisfiable circuit")
            else:
                if mode == "conflict":
                    failures.append(
                        f"{name}/conflict: expected a terminal verdict, got "
                        f"{result['status']}/{result['reason']}"
                    )
    report.add(
        "circuit_equivalence",
        failures,
        {
            "instances": len(circuit_instances()),
            "in_scope": in_scope,
            "out_of_scope": out_of_scope,
            "reference_sat": sat_instances,
            "reference_unsat": unsat_instances,
            "witnesses_replayed": witnesses_checked,
        },
    )


def check_transition_equivalence(report: Report, runs: dict[tuple[str, str], dict[str, Any]]) -> None:
    failures: list[str] = []
    in_scope = 0
    out_of_scope: list[str] = []
    sat_instances = 0
    unsat_instances = 0
    replays = 0
    for name, spec, _note in transition_instances():
        reference = reference_transition(spec)
        if not reference["enumerated"]:
            out_of_scope.append(name)
            report.scope(
                f"OUTSIDE ENUMERATION SCOPE: transition {name} has {reference['free_variables']} free "
                f"variables; no truth-table claim is made for it."
            )
            continue
        in_scope += 1
        report.scope(
            f"enumeration scope ok: transition {name} free={reference['free_variables']} "
            f"models={reference['models']}"
        )
        if reference["satisfiable"]:
            sat_instances += 1
        else:
            unsat_instances += 1
        for mode in MODE_NAMES:
            result = runs[(name, mode)]
            if result["crash"] is not None:
                failures.append(f"{name}/{mode}: raised {result['crash']}")
                continue
            if result["status"] == "sat":
                witness = result["witness"]
                if not isinstance(witness, Mapping):
                    failures.append(f"{name}/{mode}: sat without a witness mapping")
                    continue
                expected_labels = [f"{state}@0" for state in spec["state"]] + [
                    f"{input_name}@{time}"
                    for time in range(int(spec["horizon"]))
                    for input_name in spec["inputs"]
                ]
                missing = [label for label in expected_labels if label not in witness]
                if missing:
                    failures.append(f"{name}/{mode}: witness misses labels {missing}")
                    continue
                initial = {state: int(witness[f"{state}@0"]) for state in spec["state"]}
                trace = [
                    {input_name: int(witness[f"{input_name}@{time}"]) for input_name in spec["inputs"]}
                    for time in range(int(spec["horizon"]))
                ]
                try:
                    problems = simulate_transition(spec, initial, trace)
                except ReferenceError_ as exc:
                    failures.append(f"{name}/{mode}: reference could not replay the witness: {exc}")
                    continue
                replays += 1
                if problems:
                    failures.append(
                        f"{name}/{mode}: replayed witness {initial} / {trace} violates {problems}"
                    )
                if mode == "conflict" and not reference["satisfiable"]:
                    failures.append(f"{name}/conflict: reported sat for an unsatisfiable system")
            elif result["status"] == "unsat":
                if mode == "conflict" and reference["satisfiable"]:
                    failures.append(f"{name}/conflict: reported unsat for a satisfiable system")
            elif mode == "conflict":
                failures.append(
                    f"{name}/conflict: expected a terminal verdict, got {result['status']}/{result['reason']}"
                )
    report.add(
        "transition_equivalence",
        failures,
        {
            "instances": len(transition_instances()),
            "in_scope": in_scope,
            "out_of_scope": out_of_scope,
            "reference_sat": sat_instances,
            "reference_unsat": unsat_instances,
            "witnesses_replayed": replays,
        },
    )


def check_mode_agreement(report: Report, runs: dict[tuple[str, str], dict[str, Any]], reference_of: dict[str, dict[str, Any]]) -> None:
    failures: list[str] = []
    counts = {mode: {"sat": 0, "unsat": 0, "exhausted": 0} for mode in MODE_NAMES}
    exhausted_runs = 0
    local_claims = 0
    intermediate: dict[str, str] = {}
    event_actions: list[str] = []
    probe = compile_circuit(circuit_named("mixed_circuit_sat"))
    for mode in MODE_NAMES:
        field = ConstraintField(make_profile(mode))
        state = field.initial(probe)
        pair = (field.status(state), str(field.result(state)["reason"]))
        intermediate[f"initial/{mode}"] = f"{pair[0]}/{pair[1]}"
        if not vocabulary_ok(*pair):
            failures.append(f"initial state in {mode} mode is outside the vocabulary: {pair[0]}/{pair[1]}")
        successor, event = field.step(state)
        if not isinstance(event, Mapping) or event.get("schema") != STEP_SCHEMA:
            seen = event.get("schema") if isinstance(event, Mapping) else type(event).__name__
            failures.append(f"{mode} mode: step event schema is {seen!r}, expected {STEP_SCHEMA!r}")
        elif not isinstance(event.get("action"), str):
            failures.append(f"{mode} mode: step event carries no action")
        else:
            event_actions.append(f"{mode}:{event['action']}")
        pair = (field.status(successor), str(field.result(successor)["reason"]))
        intermediate[f"after_one_step/{mode}"] = f"{pair[0]}/{pair[1]}"
        if not vocabulary_ok(*pair):
            failures.append(
                f"state after one step in {mode} mode is outside the vocabulary: {pair[0]}/{pair[1]}"
            )
    for (instance, mode), result in sorted(runs.items()):
        if result["crash"] is not None:
            failures.append(f"{instance}/{mode}: raised {result['crash']}")
            continue
        status, reason = str(result["status"]), str(result["reason"])
        if not vocabulary_ok(status, reason):
            failures.append(f"{instance}/{mode}: status/reason pair outside the vocabulary: {status}/{reason}")
            continue
        counts[mode][status] += 1
        if status == "exhausted":
            exhausted_runs += 1
            if result["witness"] is not None:
                failures.append(f"{instance}/{mode}: exhausted run claims a witness")
            if result["resolution_proof"] is not None:
                failures.append(f"{instance}/{mode}: exhausted run claims a resolution proof")
            if mode != "local":
                failures.append(
                    f"{instance}/{mode}: exhausted run in a complete mode ({reason}) on a tiny instance"
                )
            continue
        reference = reference_of[instance]
        if reference["satisfiable"] is None:
            continue
        expected = "sat" if reference["satisfiable"] else "unsat"
        if status != expected:
            failures.append(f"{instance}/{mode}: field says {status}, reference says {expected}")
        if mode == "local":
            local_claims += 1
    report.add(
        "mode_agreement",
        failures,
        {
            "runs": len(runs),
            "status_by_mode": counts,
            "intermediate_pairs": intermediate,
            "step_event_actions": event_actions,
            "exhausted_runs": exhausted_runs,
            "local_terminal_claims_checked": local_claims,
            "note": "local may report exhausted; any sat/unsat it does report must match the reference",
        },
    )


def check_certificate_audit(report: Report, runs: dict[tuple[str, str], dict[str, Any]]) -> None:
    failures: list[str] = []
    resolution_audits = 0
    hybrid_audits = 0
    hybrid_refutations = 0
    augmentation_instances: list[str] = []
    conflict_certificates = 0
    skipped_prepass: list[str] = []
    prepass_telemetry: dict[str, list[str]] = {}
    refuted_runs: list[str] = []
    for (instance, mode), result in sorted(runs.items()):
        if result["crash"] is not None:
            failures.append(f"{instance}/{mode}: raised {result['crash']}")
            continue
        status = str(result["status"])
        if status == "unsat" and result["resolution_proof"] is None and result["hybrid_proof"] is None:
            failures.append(f"{instance}/{mode}: unsat without any certificate")
        if result["resolution_proof"] is not None:
            clauses = result["backend_clauses"]
            if clauses is None:
                failures.append(f"{instance}/{mode}: resolution proof without a backend clause database")
                continue
            try:
                audit_resolution_proof(
                    clauses,
                    result["learned_clauses"],
                    result["resolution_proof"],
                    variables=int(result["compiled"]["variables"]),
                    status="unsat",
                    expected_conflicts=len(result["resolution_proof"]["conflict_derivations"]),
                    max_learned_clauses=int(result["profile"]["max_learned_clauses"]),
                )
            except Exception as exc:  # noqa: BLE001 - any audit failure is a failure
                failures.append(f"{instance}/{mode}: resolution audit failed: {exc}")
                continue
            resolution_audits += 1
            if mode == "conflict":
                conflict_certificates += 1
        if mode == "algebraic":
            proof = result["hybrid_proof"]
            telemetry = result["work"].get("prepass") if isinstance(result["work"], Mapping) else None
            telemetry_status = str(telemetry.get("status")) if isinstance(telemetry, Mapping) else "absent"
            prepass_telemetry.setdefault(telemetry_status, []).append(instance)
            if proof is None:
                if compiled_contradiction(result["compiled"]["clauses"]):
                    # a source already refuted at load time has no prepass to audit; the
                    # ruling is that all three configurations still report unsat
                    skipped_prepass.append(instance)
                    if status != "unsat":
                        failures.append(
                            f"{instance}/algebraic: contradictory source reported {status} instead of unsat"
                        )
                    continue
                failures.append(f"{instance}/algebraic: missing hybrid proof for a non-contradictory source")
                continue
            try:
                audit_hybrid_proof(
                    result["compiled"]["clauses"],
                    proof,
                    variables=int(result["compiled"]["variables"]),
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{instance}/algebraic: hybrid audit failed: {exc}")
                continue
            hybrid_audits += 1
            if status == "unsat" and result["reason"] == "hybrid-refutation":
                hybrid_refutations += 1
                refuted_runs.append(instance)
            if result["augmentations"]:
                augmentation_instances.append(f"{instance}/{mode}")
    if hybrid_refutations < 1:
        failures.append("no algebraic run refuted the source in its prepass (reason hybrid-refutation)")
    if not augmentation_instances:
        failures.append("no algebraic run admitted prepass augmentations")
    if hybrid_audits == 0:
        failures.append("no algebraic run carried an auditable hybrid proof")
    if resolution_audits == 0:
        failures.append("no UNSAT run carried an auditable resolution certificate")
    if "running" in prepass_telemetry or "complete" in prepass_telemetry:
        # the prepass hands over to the search once it is complete; a run refuted by the
        # prepass itself never hands over, so the two sets must line up exactly
        if sorted(prepass_telemetry.get("running", [])) != sorted(refuted_runs):
            failures.append(
                "work['prepass'] runs still marked running do not match the hybrid-refutation set: "
                f"{sorted(prepass_telemetry.get('running', []))} vs {sorted(refuted_runs)}"
            )
    report.add(
        "certificate_audit",
        failures,
        {
            "resolution_certificates_audited": resolution_audits,
            "conflict_mode_certificates": conflict_certificates,
            "hybrid_proofs_audited": hybrid_audits,
            "prepass_refutations": hybrid_refutations,
            "augmentation_runs": augmentation_instances,
            "compiled_contradiction_runs": sorted(skipped_prepass),
            "prepass_telemetry_counts": {key: len(names) for key, names in prepass_telemetry.items()},
            "prepass_refuted_runs": sorted(refuted_runs),
            "prepass_skipped_runs": sorted(prepass_telemetry.get("skipped", [])),
        },
    )


def journal_rows(descriptor: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = base64.b64decode(str(descriptor["journal_b64"]))
    rows: list[dict[str, Any]] = []
    for line in raw.split(b"\n"):
        if line:
            rows.append(json.loads(line))
    return rows


def check_checkpoint_fidelity(report: Report) -> None:
    failures: list[str] = []
    interrupted_steps = 0
    mid_conflict = 0
    after_augmentation = 0
    instances_used: list[str] = []
    observed_work_keys: set[str] = set()
    cases: list[tuple[str, dict[str, Any], str]] = [
        ("checkpoint_conflict_unsat", circuit_named("pigeonhole_three_into_two_unsat"), "conflict"),
        ("checkpoint_conflict_sat", circuit_named("mixed_circuit_sat"), "conflict"),
        ("checkpoint_algebraic_augment", circuit_named("parity_clause_cluster_augment"), "algebraic"),
        ("checkpoint_transition", transition_named("h2_mux_sat"), "algebraic"),
    ]
    for label, spec, mode in cases:
        instances_used.append(label)
        compiled = compile_circuit(spec) if spec["kind"] == "circuit" else compile_transition_problem(spec)
        field = ConstraintField(make_profile(mode))
        uninterrupted, reference_result = field.solve(field.initial(compiled))
        state = field.initial(compiled)
        step_index = 0
        while field.status(state) == "running":
            state, _event = field.step(state)
            descriptor = field.descriptor(state)
            rows = journal_rows(descriptor)
            if any(row.get("type") == "conflict" for row in rows):
                mid_conflict += 1
            if any(row.get("type") == "augmentations" for row in rows):
                after_augmentation += 1
            interrupted_steps += 1
            if descriptor["state_sha256"] != field.state_sha256(state):
                failures.append(f"{label}/step{step_index}: descriptor digest disagrees with the field")
            try:
                restored_field, restored = ConstraintField.from_descriptor(descriptor)
            except ConstraintFieldError as exc:
                failures.append(f"{label}/step{step_index}: descriptor rejected: {exc}")
                step_index += 1
                continue
            if restored_field.state_sha256(restored) != field.state_sha256(state):
                failures.append(f"{label}/step{step_index}: restored digest differs")
            if restored_field.profile.fingerprint != field.profile.fingerprint:
                failures.append(f"{label}/step{step_index}: restored profile differs")
            final, result = restored_field.solve(restored)
            if final.status != uninterrupted.status:
                failures.append(f"{label}/step{step_index}: restored status {final.status} != {uninterrupted.status}")
            for key in ("status", "reason", "state_sha256", "witness", "backend_clauses", "learned_clauses"):
                if result[key] != reference_result[key]:
                    failures.append(f"{label}/step{step_index}: restored result key {key!r} differs")
                    break
            # work is derived from the state; the documented keys must be present, and the
            # whole mapping is compared for equality as well (a resume inside one revision
            # sees any added key on both sides, so this is strictly stronger)
            observed_work_keys.update(result["work"])
            for key in WORK_KEYS:
                if key not in result["work"]:
                    failures.append(f"{label}/step{step_index}: work is missing the documented key {key!r}")
                    break
            if result["work"] != reference_result["work"]:
                failures.append(f"{label}/step{step_index}: restored work differs")
            step_index += 1
        if step_index == 0:
            failures.append(f"{label}: no intermediate state was available to interrupt")
    if mid_conflict < 1:
        failures.append("no interruption happened with a conflict already in the journal")
    if after_augmentation < 1:
        failures.append("no interruption happened after an augmentation")
    report.add(
        "checkpoint_fidelity",
        failures,
        {
            "instances": instances_used,
            "interrupted_states": interrupted_steps,
            "with_conflict_in_journal": mid_conflict,
            "after_augmentation": after_augmentation,
            "work_keys_compared": list(WORK_KEYS),
            "work_keys_observed": sorted(observed_work_keys),
            "work_comparison": "documented keys asserted present; the whole work mapping compared for equality",
        },
    )


def tamper_value(descriptor: Mapping[str, Any], key: str) -> dict[str, Any]:
    value: dict[str, Any] = copy.deepcopy(dict(descriptor))
    if key == "unknown_key":
        value["unexpected"] = 1
    elif key == "missing_key":
        value.pop("reason")
    elif key == "journal_b64":
        raw = bytearray(base64.b64decode(str(value["journal_b64"])))
        if raw:
            raw[0] ^= 0xFF
        else:
            raw = bytearray(b'{"type":"tampered"}\n')
        value["journal_b64"] = base64.b64encode(bytes(raw)).decode("ascii")
    elif key == "compiled":
        value["compiled"]["variables"] = int(value["compiled"]["variables"]) + 1
    elif key == "profile":
        value["profile"]["max_clauses"] = int(value["profile"]["max_clauses"]) + 1
    elif key == "profile_sha256":
        value["profile_sha256"] = "0" * 64
    elif key == "state_sha256":
        value["state_sha256"] = "0" * 64
    elif key == "backend_field_bytes":
        encoded = str(value["backend"]["field_b64"])
        raw = bytearray(base64.b64decode(encoded))
        raw[0] ^= 0xFF
        value["backend"]["field_b64"] = base64.b64encode(bytes(raw)).decode("ascii")
    elif key == "hybrid_field_bytes":
        encoded = str(value["hybrid"]["field_b64"])
        raw = bytearray(base64.b64decode(encoded))
        raw[0] ^= 0xFF
        value["hybrid"]["field_b64"] = base64.b64encode(bytes(raw)).decode("ascii")
    else:
        raise KeyError(key)
    return value


def check_tamper_matrix(report: Report) -> None:
    failures: list[str] = []
    spec = circuit_named("parity_clause_cluster_augment")
    compiled = compile_circuit(spec)
    field = ConstraintField(make_profile("algebraic"))
    state = field.initial(compiled)
    state, _event = field.step(state)
    descriptor = field.descriptor(state)
    if descriptor["backend"] is None or descriptor["hybrid"] is None:
        failures.append("tamper fixture lacks a backend or hybrid block")
    outcomes: dict[str, str] = {}
    try:
        restored_field, restored = ConstraintField.from_descriptor(copy.deepcopy(descriptor))
        if restored_field.state_sha256(restored) != field.state_sha256(state):
            failures.append("clean descriptor did not reproduce the state digest")
        outcomes["clean_control"] = "accepted"
    except ConstraintFieldError as exc:
        failures.append(f"clean descriptor rejected: {exc}")
        outcomes["clean_control"] = f"rejected: {exc}"
    for key in (
        "journal_b64",
        "compiled",
        "profile",
        "profile_sha256",
        "backend_field_bytes",
        "hybrid_field_bytes",
        "state_sha256",
        "unknown_key",
        "missing_key",
    ):
        value = tamper_value(descriptor, key)
        try:
            ConstraintField.from_descriptor(value)
        except ConstraintFieldError as exc:
            outcomes[key] = f"ConstraintFieldError: {exc}"
        except Exception as exc:  # noqa: BLE001
            outcomes[key] = f"{type(exc).__name__}: {exc}"
            failures.append(f"tampered {key}: raised {type(exc).__name__}, not ConstraintFieldError")
        else:
            outcomes[key] = "accepted (no error)"
            failures.append(f"tampered {key}: accepted without error")
    report.add("tamper_matrix", failures, {"field_outcomes": outcomes})


def expect_error(call: Callable[[], Any]) -> str:
    try:
        call()
    except ConstraintFieldError as exc:
        return f"ConstraintFieldError: {exc}"
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"
    return ""


def check_negative_capacity(report: Report) -> None:
    failures: list[str] = []
    outcomes: dict[str, str] = {}
    base = c(["a", "b"], [{"op": "and", "out": "g", "args": ["a", "b"]}], [["g", 1]])
    wide = [f"v{index}" for index in range(20)]

    def circuit(**changes: Any) -> dict[str, Any]:
        spec = copy.deepcopy(base)
        spec.update(changes)
        return spec

    transition_base = transition_named("h1_xor_sat")

    def transition(**changes: Any) -> dict[str, Any]:
        spec = copy.deepcopy(transition_base)
        spec.update(changes)
        return spec

    cases: list[tuple[str, Callable[[], Any]]] = [
        ("unknown_assertion_signal", lambda: compile_circuit(circuit(assertions=[["zz", 1]]))),
        ("unknown_clause_signal", lambda: compile_circuit(circuit(clauses=[[["zz", 1]]]))),
        ("unknown_relation_signal", lambda: compile_circuit(circuit(relations=[{"kind": "xor", "args": ["zz", "a"], "rhs": 0}]))),
        ("non_binary_assertion_bit", lambda: compile_circuit(circuit(assertions=[["g", 2]]))),
        ("non_binary_clause_polarity", lambda: compile_circuit(circuit(clauses=[[["a", 3]]]))),
        ("duplicate_gate_output", lambda: compile_circuit(circuit(gates=[{"op": "and", "out": "g", "args": ["a", "b"]}, {"op": "or", "out": "g", "args": ["a", "b"]}]))),
        ("cyclic_gates", lambda: compile_circuit(circuit(gates=[{"op": "and", "out": "g", "args": ["a", "h"]}, {"op": "or", "out": "h", "args": ["b", "g"]}]))),
        ("wrong_gate_arity", lambda: compile_circuit(circuit(gates=[{"op": "and", "out": "g", "args": ["a"]}]))),
        ("unknown_gate_operation", lambda: compile_circuit(circuit(gates=[{"op": "implies", "out": "g", "args": ["a", "b"]}]))),
        ("const_value_not_binary", lambda: compile_circuit(circuit(gates=[{"op": "const", "out": "g", "args": [], "value": 2}]))),
        ("gate_value_on_non_const", lambda: compile_circuit(circuit(gates=[{"op": "buf", "out": "g", "args": ["a"], "value": 1}]))),
        ("input_also_gate", lambda: compile_circuit(circuit(inputs=["a", "g"]))),
        ("duplicate_inputs", lambda: compile_circuit(circuit(inputs=["a", "a"]))),
        ("invalid_relation_kind", lambda: compile_circuit(circuit(relations=[{"kind": "atmost", "args": ["a", "b"], "min": 0, "max": 1}]))),
        ("xor_rhs_not_binary", lambda: compile_circuit(circuit(relations=[{"kind": "xor", "args": ["a", "b"], "rhs": 2}]))),
        ("cardinality_max_beyond_arity", lambda: compile_circuit(circuit(relations=[{"kind": "cardinality", "args": ["a", "b"], "min": 0, "max": 3}]))),
        ("cardinality_min_above_max", lambda: compile_circuit(circuit(relations=[{"kind": "cardinality", "args": ["a", "b"], "min": 2, "max": 1}]))),
        ("cardinality_negative_min", lambda: compile_circuit(circuit(relations=[{"kind": "cardinality", "args": ["a", "b"], "min": -1, "max": 1}]))),
        ("cardinality_repeated_argument", lambda: compile_circuit(circuit(relations=[{"kind": "cardinality", "args": ["a", "a"], "min": 0, "max": 2}]))),
        (
            "cardinality_enumeration_overflow",
            lambda: compile_circuit(
                c(
                    wide,
                    [],
                    [],
                    [{"kind": "cardinality", "args": wide, "min": 0, "max": 9}],
                )
            ),
        ),
        ("profile_variable_capacity", lambda: compile_circuit(base, profile=ConstraintFieldProfile(max_variables=2, max_clauses=64))),
        ("profile_clause_capacity", lambda: compile_circuit(base, profile=ConstraintFieldProfile(max_variables=16, max_clauses=2))),
        ("profile_initial_capacity", lambda: ConstraintField(make_profile("conflict", max_variables=2)).initial(compile_circuit(base))),
        ("transition_initial_unknown_state", lambda: compile_transition_problem(transition(initial=[["zz", 1]]))),
        ("transition_final_unknown_state", lambda: compile_transition_problem(transition(final=[["zz", 1]]))),
        ("transition_next_state_unknown_signal", lambda: compile_transition_problem(transition(next_state=[["s", "zz"]]))),
        ("transition_next_state_incomplete", lambda: compile_transition_problem(transition(state=["s", "u"]))),
        ("transition_state_input_overlap", lambda: compile_transition_problem(transition(inputs=["s"]))),
        ("transition_gate_named_like_state", lambda: compile_transition_problem(transition(gates=[{"op": "buf", "out": "s", "args": ["s"]}]))),
        ("transition_horizon_over_compiler_bound", lambda: compile_transition_problem(transition(horizon=4097))),
        ("transition_horizon_negative", lambda: compile_transition_problem(transition(horizon=-1))),
        ("transition_input_assertion_past_horizon", lambda: compile_transition_problem(transition(input_assertions=[[9, "x", 1]]))),
        ("transition_input_assertion_unknown_input", lambda: compile_transition_problem(transition(input_assertions=[[0, "zz", 1]]))),
        ("transition_input_assertion_time_negative", lambda: compile_transition_problem(transition(input_assertions=[[-1, "x", 1]]))),
        ("profile_invalid_mode", lambda: ConstraintFieldProfile(max_variables=8, max_clauses=16, mode="dpll")),
        ("profile_boolean_integer_field", lambda: ConstraintFieldProfile(max_variables=True, max_clauses=16)),
        # profile-level contract: a controller schedules decisions, which local mode never does
        (
            "profile_local_with_controller",
            lambda: ConstraintFieldProfile(max_variables=8, max_clauses=16, mode="local", controller=True),
        ),
        (
            "unknown_gate_argument_circuit",
            lambda: compile_circuit(circuit(gates=[{"op": "and", "out": "g", "args": ["a", "zz"]}])),
        ),
        (
            "unknown_gate_argument_transition",
            lambda: compile_transition_problem(
                transition(
                    gates=[
                        {"op": "xor", "out": "g", "args": ["x", "s"]},
                        {"op": "buf", "out": "w", "args": ["zz"]},
                    ]
                )
            ),
        ),
    ]
    for name, call in cases:
        message = expect_error(call)
        if not message:
            outcomes[name] = "accepted (no error)"
            failures.append(f"{name}: no ConstraintFieldError was raised")
        else:
            outcomes[name] = message
            if not message.startswith("ConstraintFieldError"):
                failures.append(f"{name}: raised {message.split(':', 1)[0]}, not ConstraintFieldError")

    # no silent truncation: a parity wider than the hybrid parity-width bound must stay exact
    wide_spec = c(
        [f"v{index}" for index in range(12)],
        [],
        [["v0", 1], ["v1", 0]],
        [{"kind": "xor", "args": [f"v{index}" for index in range(12)], "rhs": 1}],
    )
    compiled_wide = compile_circuit(wide_spec)
    reference = reference_circuit(wide_spec)
    expected = "sat" if reference["satisfiable"] else "unsat"
    verdicts: dict[str, str] = {}
    for mode in MODE_NAMES:
        result = collect_run(compiled_wide, mode, max_parity_width=4)
        if result["crash"] is not None:
            failures.append(f"wide_parity_not_truncated/{mode}: raised {result['crash']}")
            verdicts[mode] = result["crash"]
            continue
        verdicts[mode] = f"{result['status']}/{result['reason']}"
        if mode == "local":
            # propagation-only may stall honestly; any claim it does make must be right
            if result["status"] in ("sat", "unsat") and result["status"] != expected:
                failures.append(
                    f"wide_parity_not_truncated/local: claimed {result['status']} but the reference says {expected}"
                )
            continue
        if result["status"] != expected:
            failures.append(
                f"wide_parity_not_truncated/{mode}: verdict {result['status']} != reference {expected}"
            )
    report.add(
        "negative_capacity",
        failures,
        {
            "cases": len(cases),
            "outcomes": outcomes,
            "wide_parity_with_narrow_hybrid_bound": verdicts,
            "enumeration_scope_note": (
                "cardinality_enumeration_overflow needs C(20,10)=184756 clauses for a 20-argument "
                "window, which is outside the 2**16 relation-clause capacity and outside enumeration "
                "scope; the compiler must refuse it rather than truncate"
            ),
        },
    )


def check_exhausted_honesty(report: Report) -> None:
    failures: list[str] = []
    cases: dict[str, dict[str, Any]] = {}
    unsat_spec = circuit_named("mixed_circuit_unsat")
    compiled = compile_circuit(unsat_spec)
    budget_case = collect_run(compiled, "conflict", max_transitions=1)
    baseline = collect_run(compiled, "conflict")
    cases["max_transitions_1"] = {
        "status": budget_case["crash"] or budget_case["status"],
        "reason": budget_case["crash"] or budget_case["reason"],
        "resolution_proof": budget_case["crash"] is None and budget_case["resolution_proof"] is not None,
        "witness": budget_case["crash"] is None and budget_case["witness"] is not None,
    }
    cases["unbounded_baseline"] = {
        "status": baseline["crash"] or baseline["status"],
        "reason": baseline["crash"] or baseline["reason"],
    }
    if budget_case["crash"] is not None:
        failures.append(f"max_transitions_1: raised {budget_case['crash']}")
    else:
        if budget_case["status"] != "exhausted":
            failures.append(
                f"max_transitions_1: expected exhausted, got {budget_case['status']}/{budget_case['reason']}"
            )
        if budget_case["reason"] != "transition-budget":
            failures.append(
                f"max_transitions_1: expected reason 'transition-budget', got {budget_case['reason']!r}"
            )
        if budget_case["resolution_proof"] is not None or budget_case["witness"] is not None:
            failures.append("max_transitions_1: exhausted run claims an artefact")
    if baseline["crash"] is not None or baseline["status"] != "unsat":
        failures.append(
            "unbounded_baseline: the same source did not reach a terminal verdict without the bound"
        )

    tiny_journal = collect_run(compiled, "conflict", max_proof_bytes=8)
    cases["max_proof_bytes_8"] = {
        "status": tiny_journal["crash"] or tiny_journal["status"],
        "reason": tiny_journal["crash"] or tiny_journal["reason"],
        "resolution_proof": tiny_journal["crash"] is None and tiny_journal["resolution_proof"] is not None,
        "witness": tiny_journal["crash"] is None and tiny_journal["witness"] is not None,
    }
    if tiny_journal["crash"] is not None:
        failures.append(f"max_proof_bytes_8: raised {tiny_journal['crash']}")
    else:
        if tiny_journal["status"] != "exhausted" or tiny_journal["reason"] != "proof-journal-capacity":
            failures.append(
                f"max_proof_bytes_8: expected exhausted/proof-journal-capacity, got "
                f"{tiny_journal['status']}/{tiny_journal['reason']}"
            )
        if tiny_journal["resolution_proof"] is not None or tiny_journal["witness"] is not None:
            failures.append("max_proof_bytes_8: exhausted run claims an artefact")

    stalled_spec = c(["a", "b"], [{"op": "or", "out": "g", "args": ["a", "b"]}])
    compiled_stall = compile_circuit(stalled_spec)
    for label, overrides in (("local_stall_bound_1", {"max_transitions": 1}), ("local_stall_unbounded", {})):
        result = collect_run(compiled_stall, "local", **overrides)
        cases[label] = {
            "status": result["crash"] or result["status"],
            "reason": result["crash"] or result["reason"],
            "resolution_proof": result["crash"] is None and result["resolution_proof"] is not None,
            "witness": result["crash"] is None and result["witness"] is not None,
        }
        if result["crash"] is not None:
            failures.append(f"{label}: raised {result['crash']}")
            continue
        if result["status"] != "exhausted" or result["reason"] != "local-stall":
            failures.append(
                f"{label}: expected exhausted/local-stall, got {result['status']}/{result['reason']}"
            )
        if result["resolution_proof"] is not None or result["witness"] is not None:
            failures.append(f"{label}: exhausted run claims an artefact")
    for label, row in cases.items():
        if row["status"] == "exhausted" and row["reason"] not in REASON_VOCABULARY["exhausted"]:
            failures.append(f"{label}: reason {row['reason']!r} outside the exhausted vocabulary")
    report.add("exhausted_honesty", failures, {"cases": cases})


def check_controller_integration(report: Report) -> None:
    failures: list[str] = []
    detail: dict[str, Any] = {}
    unsat_spec = circuit_named("pigeonhole_three_into_two_unsat")
    sat_spec = circuit_named("mixed_circuit_sat")

    def controlled(spec: dict[str, Any], mode: str = "conflict") -> dict[str, Any]:
        compiled = compile_circuit(spec)
        field = ConstraintField(make_profile(mode, controller=True))
        state = field.initial(compiled)
        final, result = field.solve(state)
        return {"field": field, "state": final, "result": result, "compiled": compiled}

    run_a = controlled(unsat_spec)
    run_b = controlled(unsat_spec)
    work_a = run_a["result"]["work"]["controller"]
    work_b = run_b["result"]["work"]["controller"]
    detail["unsat_run"] = {
        "status": run_a["result"]["status"],
        "reason": run_a["result"]["reason"],
        "controller": work_a,
    }
    if not work_a["enabled"]:
        failures.append("controller flag not reported as enabled")
    for key in ("ticks", "selections", "interventions"):
        for label, work in (("a", work_a), ("b", work_b)):
            value = work[key]
            if isinstance(value, bool) or not isinstance(value, int):
                failures.append(f"controller {key} in run {label} is not an exact integer: {value!r}")
    if work_a["selections"] < 1:
        failures.append("controller made no selection on an instance that needs decisions")
    if run_a["result"]["state_sha256"] != run_b["result"]["state_sha256"]:
        failures.append("two identical controlled runs produced different final digests")
    if run_a["result"]["witness"] != run_b["result"]["witness"]:
        failures.append("two identical controlled runs produced different witnesses")
    if run_a["result"]["status"] != "unsat":
        failures.append(f"controlled unsat instance returned {run_a['result']['status']}")
    elif run_a["result"]["resolution_proof"] is None:
        failures.append("controlled unsat run carries no resolution certificate")
    else:
        try:
            audit_resolution_proof(
                run_a["result"]["backend_clauses"],
                run_a["result"]["learned_clauses"],
                run_a["result"]["resolution_proof"],
                variables=int(run_a["result"]["compiled"]["variables"]),
                status="unsat",
                expected_conflicts=len(run_a["result"]["resolution_proof"]["conflict_derivations"]),
                max_learned_clauses=int(run_a["result"]["profile"]["max_learned_clauses"]),
            )
        except Exception as exc:  # noqa: BLE001
            failures.append(f"controlled unsat certificate failed its audit: {exc}")

    run_sat = controlled(sat_spec)
    if run_sat["result"]["status"] != "sat":
        failures.append(f"controlled satisfiable instance returned {run_sat['result']['status']}")
    else:
        witness = run_sat["result"]["witness"]
        if not isinstance(witness, Mapping):
            failures.append("controlled sat run carries no witness")
        else:
            scope = {name: int(witness[name]) for name in sat_spec["inputs"] if name in witness}
            if len(scope) != len(sat_spec["inputs"]):
                failures.append("controlled sat witness misses an input")
            elif not circuit_accepts(sat_spec, scope):
                failures.append(f"controlled sat witness {scope} violates the source")

    compiled = compile_circuit(unsat_spec)
    field = ConstraintField(make_profile("conflict", controller=True))
    start = field.initial(compiled)
    before = field.state_sha256(start)
    successor, event = field.intervene(start, variable=1, excitation=1)
    after = field.state_sha256(successor)
    detail["intervention"] = {"before": before[:16], "after": after[:16], "changed": before != after}
    if before == after:
        failures.append("intervention did not change the controller digest")
    if not isinstance(event, Mapping):
        failures.append("intervention returned no event")
    else:
        detail["intervention_event"] = {
            "schema": event.get("schema"),
            "action": event.get("action"),
            "variable": event.get("variable"),
            "excitation": event.get("excitation"),
        }
        if event.get("schema") != STEP_SCHEMA or event.get("action") != "intervention":
            failures.append(
                f"intervention event is {event.get('schema')!r}/{event.get('action')!r}, "
                "expected the step schema with the intervention action"
            )
        if event.get("variable") != 1 or event.get("excitation") != 1:
            failures.append("intervention event does not report the requested variable and excitation")
        if event.get("previous_state_sha256") != before or event.get("state_sha256") != after:
            failures.append("intervention event digests do not match the state transition")
    rows = journal_rows(field.descriptor(successor))
    if sum(1 for row in rows if row.get("type") == "intervention") != 1:
        failures.append("intervention was not journaled exactly once")
    _final, result = field.solve(successor)
    interventions = result["work"]["controller"]["interventions"]
    detail["intervention"]["interventions"] = interventions
    if interventions != 1:
        failures.append(f"intervened run reports {interventions} interventions")
    if result["status"] != "unsat":
        failures.append(f"intervened unsat run returned {result['status']}")
    elif result["resolution_proof"] is None:
        failures.append("intervened unsat run carries no certificate")
    else:
        try:
            audit_resolution_proof(
                result["backend_clauses"],
                result["learned_clauses"],
                result["resolution_proof"],
                variables=int(result["compiled"]["variables"]),
                status="unsat",
                expected_conflicts=len(result["resolution_proof"]["conflict_derivations"]),
                max_learned_clauses=int(result["profile"]["max_learned_clauses"]),
            )
            detail["intervention"]["certificate"] = "audited"
        except Exception as exc:  # noqa: BLE001
            failures.append(f"intervened unsat certificate failed its audit: {exc}")

    sat_field = ConstraintField(make_profile("conflict", controller=True))
    sat_start = sat_field.initial(compile_circuit(sat_spec))
    sat_successor, _event = sat_field.intervene(sat_start, variable=1, excitation=1)
    _final2, sat_result = sat_field.solve(sat_successor)
    if sat_result["status"] != "sat":
        failures.append(f"intervened satisfiable run returned {sat_result['status']}")
    else:
        witness = sat_result["witness"]
        if not isinstance(witness, Mapping):
            failures.append("intervened sat run carries no witness")
        else:
            scope = {name: int(witness[name]) for name in sat_spec["inputs"] if name in witness}
            if len(scope) != len(sat_spec["inputs"]) or not circuit_accepts(sat_spec, scope):
                failures.append(f"intervened sat witness {scope} does not satisfy the source")
    repeat_field = ConstraintField(make_profile("conflict", controller=True))
    repeat_start = repeat_field.initial(compile_circuit(sat_spec))
    repeat_successor, _event = repeat_field.intervene(repeat_start, variable=1, excitation=1)
    _final3, repeat_result = repeat_field.solve(repeat_successor)
    if repeat_result["state_sha256"] != sat_result["state_sha256"]:
        failures.append("intervened runs are not deterministic")
    detail["intervened_sat"] = {
        "status": sat_result["status"],
        "reason": sat_result["reason"],
        "interventions": sat_result["work"]["controller"]["interventions"],
    }
    plain = ConstraintField(make_profile("conflict"))
    try:
        plain.intervene(plain.initial(compiled), variable=1, excitation=1)
    except ConstraintFieldError:
        detail["intervention_without_controller"] = "rejected"
    except Exception as exc:  # noqa: BLE001
        failures.append(f"intervention without a controller raised {type(exc).__name__}")
    else:
        failures.append("intervention without a controller was accepted")
    report.add("controller_integration", failures, detail)


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def run_suite() -> tuple[Report, dict[str, Any]]:
    report = Report()
    runs: dict[tuple[str, str], dict[str, Any]] = {}
    reference_of: dict[str, dict[str, Any]] = {}
    crashes: dict[str, str] = {}

    for name, spec, _note in circuit_instances():
        reference_of[name] = reference_circuit(spec)
        compiled = compile_circuit(spec)
        for mode in MODE_NAMES:
            runs[(name, mode)] = collect_run(compiled, mode)
    for name, spec, _note in transition_instances():
        reference_of[name] = reference_transition(spec)
        compiled = compile_transition_problem(spec)
        for mode in MODE_NAMES:
            runs[(name, mode)] = collect_run(compiled, mode)
    for (name, mode), result in runs.items():
        if result["crash"] is not None:
            crashes[f"{name}/{mode}"] = result["crash"]

    steps: list[tuple[str, Callable[[], None]]] = [
        ("gate_equivalence", lambda: check_gate_equivalence(report)),
        ("circuit_equivalence", lambda: check_circuit_equivalence(report, runs)),
        ("transition_equivalence", lambda: check_transition_equivalence(report, runs)),
        ("mode_agreement", lambda: check_mode_agreement(report, runs, reference_of)),
        ("certificate_audit", lambda: check_certificate_audit(report, runs)),
        ("checkpoint_fidelity", lambda: check_checkpoint_fidelity(report)),
        ("tamper_matrix", lambda: check_tamper_matrix(report)),
        ("negative_capacity", lambda: check_negative_capacity(report)),
        ("exhausted_honesty", lambda: check_exhausted_honesty(report)),
        ("controller_integration", lambda: check_controller_integration(report)),
    ]
    for name, step in steps:
        try:
            step()
        except Exception as exc:  # noqa: BLE001 - a crashing check is itself a finding
            report.add(name, [f"harness crash: {type(exc).__name__}: {exc}"], {"crashed": True})

    report.observe(
        "xor_arity",
        "the compiler defines no XOR arity error: duplicate arguments cancel in pairs "
        "(checked in circuit_equivalence) and a parity wider than the profile's "
        "max_parity_width is not truncated (check_negative_capacity).  There is no "
        "ConstraintFieldError to trigger for an 'XOR argument limit'.",
    )
    failed = [check["name"] for check in report.checks if not check["passed"]]
    summary = {
        "suite": "verify_constraint_field",
        "subject": "cassi_constraint_field.py",
        "checks": report.checks,
        "check_count": len(report.checks),
        "failed_checks": failed,
        "passed": not failed,
        "enumeration_scope": {
            "exponent_limit": ENUMERATION_EXPONENT_LIMIT,
            "lines": report.scope_lines,
        },
        "instances": {
            "circuits": len(circuit_instances()),
            "transitions": len(transition_instances()),
            "solves": len(runs),
        },
        "raising_runs": crashes,
        "observations": report.observations,
    }
    return report, summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent verification suite for cassi_constraint_field.py")
    parser.add_argument("--json", dest="json_path", default=None, help="write the JSON summary to PATH")
    args = parser.parse_args(list(argv) if argv is not None else None)

    started = time.time()
    report, summary = run_suite()
    summary["elapsed_seconds"] = round(time.time() - started, 3)

    for check in report.checks:
        marker = "PASS" if check["passed"] else "FAIL"
        print(f"[{marker}] {check['name']}: {json.dumps(check['detail'], sort_keys=True)}")
    for line in report.scope_lines:
        print(f"[SCOPE] {line}")
    for observation in report.observations:
        print(f"[NOTE] {observation['observation']}: {observation['detail']}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)
    if summary["passed"]:
        print("ALL CHECKS PASSED")
        return 0
    print("CHECKS FAILED: " + ", ".join(summary["failed_checks"]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
