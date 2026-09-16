#!/usr/bin/env python3
"""Deterministic measurement matrix for the field-owned exact constraint subsystem.

The script builds finite Boolean constraint instances from a fixed seed, compiles
them, solves each configuration with the field's three solver modes (``local``,
``conflict``, ``algebraic``), and records what happened: verdict, reason,
resource ledgers, controller work, checkpoint geometry, certificate audits, and
independent witness/trajectory checks against the source specification.

Scope and honesty notes:

* Labels come from exhaustive enumeration with an independent evaluator (own
  gate/relation/clause semantics) whenever ``2**free_variables <= 2**16``.
  Instances whose label comes from their construction (pigeonhole, planted
  parity boundary) record ``label_source='construction'`` and are additionally
  checked against enumeration whenever that is in capacity.
* Every UNSAT verdict must carry at least one independently audited certificate
  (resolution DAG audit and/or hybrid CP/GF(2) audit).  A verdict with no
  certificate, a failed audit, a wrong verdict, a bad witness, or a
  non-deterministic repeat is reported and makes the process exit non-zero.
* Wall-clock numbers are single host-side ``time.perf_counter`` measurements on
  one machine.  They are not a benchmark and no complexity claim is made.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_constraint_field import (
    CompiledConstraintProblem,
    ConstraintField,
    ConstraintFieldProfile,
    compile_circuit,
    compile_transition_problem,
)

from verify_hybrid_inference import audit_proof as audit_hybrid_proof
from verify_p_vs_np_clause_field_probe import audit_proof as audit_resolution_proof

SEED = 20260910
ENUMERATION_BIT_LIMIT = 16
MODES = ("local", "conflict", "algebraic")
REPEATS = 2
AUGMENTATION_HEADROOM = 64
DEFAULT_OUTPUT = "_diag/constraint_field_results.json"

BINARY_OPS = ("and", "or", "xor", "nand", "nor", "xnor")
GATE_OPS = BINARY_OPS + ("not", "buf", "mux", "const")


# ---------------------------------------------------------------------------
# independent evaluator (own semantics; never imports field internals)
# ---------------------------------------------------------------------------


def gate_value(op: str, args: Sequence[int], value: int | None = None) -> int:
    if op == "const":
        assert value in (0, 1), "const gate needs a 0/1 value"
        return int(value)
    if op == "buf":
        return args[0]
    if op == "not":
        return 1 - args[0]
    if op == "and":
        return args[0] & args[1]
    if op == "or":
        return args[0] | args[1]
    if op == "xor":
        return args[0] ^ args[1]
    if op == "nand":
        return 1 - (args[0] & args[1])
    if op == "nor":
        return 1 - (args[0] | args[1])
    if op == "xnor":
        return 1 - (args[0] ^ args[1])
    if op == "mux":
        return args[1] if args[0] else args[2]
    raise AssertionError(f"unsupported gate operation {op!r}")


def topological_gate_order(gates: Sequence[Mapping[str, Any]]) -> list[str]:
    by_name = {str(gate["out"]): gate for gate in gates}
    ordered: list[str] = []
    placed: set[str] = set()
    while len(ordered) < len(by_name):
        progressed = False
        for name, gate in by_name.items():
            if name in placed:
                continue
            if all(argument not in by_name or argument in placed for argument in gate.get("args", ())):
                ordered.append(name)
                placed.add(name)
                progressed = True
        if not progressed:
            raise AssertionError("gate graph is not acyclic")
    return ordered


def signal_values_from_assignment(
    compiled: Mapping[str, Any], assignment: Sequence[int]
) -> tuple[dict[str, int], list[str]]:
    values: dict[str, int] = {}
    unassigned: list[str] = []
    for name, identifier in compiled["signals"]:
        literal = int(assignment[int(identifier) - 1])
        if literal == 0:
            unassigned.append(str(name))
        else:
            values[str(name)] = 1 if literal > 0 else 0
    return values, unassigned


def relation_satisfied(relation: Mapping[str, Any], values: Sequence[int]) -> bool:
    kind = relation["kind"]
    if kind == "xor":
        parity = 0
        for value in values:
            parity ^= value
        return parity == int(relation["rhs"])
    if kind == "cardinality":
        total = sum(values)
        return int(relation["min"]) <= total <= int(relation["max"])
    raise AssertionError(f"unsupported relation kind {kind!r}")


def parse_clause_literals(row: Sequence[Any]) -> list[tuple[str, int, int]]:
    """Circuit clauses are ``(signal, polarity)``; transition clauses add a time."""

    literals: list[tuple[str, int, int]] = []
    for literal in row:
        literals.append(
            (str(literal[0]), int(literal[1]), int(literal[2]) if len(literal) == 3 else 0)
        )
    return literals


def evaluate_circuit(
    spec: Mapping[str, Any], inputs: Mapping[str, int]
) -> tuple[dict[str, int], list[str]]:
    values = {str(name): int(inputs[str(name)]) for name in spec["inputs"]}
    by_name = {str(gate["out"]): gate for gate in spec["gates"]}
    problems: list[str] = []
    for name in topological_gate_order(spec["gates"]):
        gate = by_name[name]
        arguments = [str(argument) for argument in gate.get("args", ())]
        if any(argument not in values for argument in arguments):
            problems.append(f"gate {name} reads an undefined signal")
            continue
        values[name] = gate_value(str(gate["op"]), [values[argument] for argument in arguments], gate.get("value"))
    return values, problems


def circuit_constraint_problems(spec: Mapping[str, Any], values: Mapping[str, int]) -> list[str]:
    problems: list[str] = []
    for signal, bit in spec["assertions"]:
        name = str(signal)
        if name not in values:
            problems.append(f"assertion refers to undefined signal {name}")
        elif values[name] != int(bit):
            problems.append(f"assertion {name}={bit} violated")
    for index, relation in enumerate(spec["relations"]):
        names = [str(name) for name in relation["args"]]
        if any(name not in values for name in names):
            problems.append(f"relation {index} reads an undefined signal")
            continue
        if not relation_satisfied(relation, [values[name] for name in names]):
            problems.append(f"relation {index} ({relation['kind']}) violated")
    for index, row in enumerate(spec["clauses"]):
        satisfied = False
        for signal, polarity, _ in parse_clause_literals(row):
            if signal not in values:
                problems.append(f"clause {index} reads an undefined signal {signal}")
                satisfied = True
                break
            if values[signal] == polarity:
                satisfied = True
                break
        if not satisfied:
            problems.append(f"clause {index} violated")
    return problems


def simulate_transition(
    spec: Mapping[str, Any],
    initial_state: Mapping[str, int],
    inputs: Mapping[tuple[int, str], int],
) -> tuple[dict[str, list[dict[str, int]]], list[str]]:
    horizon = int(spec["horizon"])
    state_names = [str(name) for name in spec["state"]]
    input_names = [str(name) for name in spec["inputs"]]
    order = topological_gate_order(spec["gates"])
    by_name = {str(gate["out"]): gate for gate in spec["gates"]}
    trace: dict[str, list[dict[str, int]]] = {
        "state": [{name: int(initial_state[name]) for name in state_names}],
        "inputs": [],
        "gates": [],
    }
    problems: list[str] = []
    for moment in range(horizon):
        scoped: dict[str, int] = dict(trace["state"][moment])
        for name in input_names:
            scoped[name] = int(inputs[(moment, name)])
        trace["inputs"].append({name: scoped[name] for name in input_names})
        gate_values: dict[str, int] = {}
        for name in order:
            gate = by_name[name]
            arguments = [str(argument) for argument in gate.get("args", ())]
            if any(argument not in scoped for argument in arguments):
                problems.append(f"gate {name} reads an undefined signal at time {moment}")
                gate_values[name] = 0
            else:
                gate_values[name] = gate_value(
                    str(gate["op"]), [scoped[argument] for argument in arguments], gate.get("value")
                )
            scoped[name] = gate_values[name]
        trace["gates"].append(gate_values)
        successors: dict[str, int] = {}
        for target, origin in spec["next_state"]:
            origin_name = str(origin)
            if origin_name not in scoped:
                problems.append(f"next_state origin {origin!r} is undefined at time {moment}")
                successors[str(target)] = 0
            else:
                successors[str(target)] = scoped[origin_name]
        trace["state"].append(successors)
    return trace, problems


def transition_constraint_problems(
    spec: Mapping[str, Any], trace: Mapping[str, list[dict[str, int]]]
) -> list[str]:
    horizon = int(spec["horizon"])
    problems: list[str] = []

    def read(signal: str, moment: int) -> int | None:
        if signal in spec["state"]:
            return trace["state"][moment][signal]
        if signal in spec["inputs"]:
            return None if moment >= horizon else trace["inputs"][moment][signal]
        return None if moment >= horizon else trace["gates"][moment].get(signal)

    for signal, bit in spec["initial"]:
        value = read(str(signal), 0)
        if value != int(bit):
            problems.append(f"initial {signal}={bit} violated (value {value})")
    for moment, name, bit in spec["input_assertions"]:
        value = read(str(name), int(moment))
        if value != int(bit):
            problems.append(f"input assertion ({moment}, {name})={bit} violated (value {value})")
    for signal, bit in spec["final"]:
        value = read(str(signal), horizon)
        if value != int(bit):
            problems.append(f"final {signal}={bit} violated (value {value})")
    for index, relation in enumerate(spec["relations"]):
        for moment in range(horizon):
            names = [str(name) for name in relation["args"]]
            raw_values = [read(name, moment) for name in names]
            if any(value is None for value in raw_values):
                problems.append(f"relation {index} reads an undefined signal at time {moment}")
                continue
            concrete = [int(value) for value in raw_values if value is not None]
            if not relation_satisfied(relation, concrete):
                problems.append(f"relation {index} ({relation['kind']}) violated at time {moment}")
    for index, row in enumerate(spec["clauses"]):
        satisfied = False
        for signal, polarity, moment in parse_clause_literals(row):
            value = read(signal, moment)
            if value is None:
                problems.append(f"clause {index} reads an undefined signal {signal} at time {moment}")
                satisfied = True
                break
            if value == polarity:
                satisfied = True
                break
        if not satisfied:
            problems.append(f"clause {index} violated")
    return problems


def free_primary_names(spec: Mapping[str, Any]) -> list[str]:
    """Primary signals: circuit inputs, or transition state@0 and every input time."""

    if spec["kind"] == "circuit":
        return [str(name) for name in spec["inputs"]]
    names = [str(name) for name in spec["state"]]
    for moment in range(int(spec["horizon"])):
        names.extend(f"{name}@{moment}" for name in spec["inputs"])
    return names


def split_primary(spec: Mapping[str, Any], bits: Mapping[str, int]) -> tuple[dict[str, int], dict[tuple[int, str], int], Any]:
    if spec["kind"] == "circuit":
        return {name: int(bits[name]) for name in spec["inputs"]}, {}, None
    initial_state = {str(name): int(bits[str(name)]) for name in spec["state"]}
    inputs = {
        (moment, str(name)): int(bits[f"{name}@{moment}"])
        for moment in range(int(spec["horizon"]))
        for name in spec["inputs"]
    }
    return {}, inputs, initial_state


def source_expected_values(spec: Mapping[str, Any], bits: Mapping[str, int]) -> tuple[dict[str, int], list[str]]:
    """Complete source-defined signal values for one primary assignment."""

    if spec["kind"] == "circuit":
        return evaluate_circuit(spec, bits)
    _, inputs, initial_state = split_primary(spec, bits)
    trace, problems = simulate_transition(spec, initial_state, inputs)
    horizon = int(spec["horizon"])
    expected: dict[str, int] = {}
    for moment in range(horizon + 1):
        for name in spec["state"]:
            expected[f"s:{name}:{moment}"] = trace["state"][moment][str(name)]
    for moment in range(horizon):
        for name in spec["inputs"]:
            expected[f"i:{name}:{moment}"] = trace["inputs"][moment][str(name)]
        for gate in spec["gates"]:
            expected[f"g:{gate['out']}:{moment}"] = trace["gates"][moment][str(gate["out"])]
    return expected, problems


def source_constraint_problems(
    spec: Mapping[str, Any], bits: Mapping[str, int], expected: Mapping[str, int]
) -> list[str]:
    if spec["kind"] == "circuit":
        return circuit_constraint_problems(spec, expected)
    _, inputs, initial_state = split_primary(spec, bits)
    trace, problems = simulate_transition(spec, initial_state, inputs)
    return problems + transition_constraint_problems(spec, trace)


def enumerate_label(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Exhaustive truth-table label over the primary signals, from the source spec."""

    names = free_primary_names(spec)
    free = len(names)
    if 2**free > 2**ENUMERATION_BIT_LIMIT:
        return {
            "label": None,
            "free_variables": free,
            "models": None,
            "in_capacity": False,
            "note": f"2**{free} exceeds the 2**{ENUMERATION_BIT_LIMIT} enumeration capacity",
        }
    models = 0
    for mask in range(1 << free):
        bits = {name: (mask >> position) & 1 for position, name in enumerate(names)}
        expected, problems = source_expected_values(spec, bits)
        if not problems and not source_constraint_problems(spec, bits, expected):
            models += 1
    return {
        "label": "sat" if models else "unsat",
        "free_variables": free,
        "models": models,
        "in_capacity": True,
        "note": "exhaustive enumeration over the primary signals",
    }


# ---------------------------------------------------------------------------
# instance families
# ---------------------------------------------------------------------------


def pick(rng: random.Random, pool: Sequence[str], recent: int = 8) -> str:
    if len(pool) > recent and rng.random() < 0.7:
        return pool[-recent + rng.randrange(recent)]
    return pool[rng.randrange(len(pool))]


def pick_arguments(rng: random.Random, pool: Sequence[str], arity: int) -> list[str]:
    """Gate arguments, always distinct signals.

    Repeated arguments are legal for the compiler but make a gate's Tseitin
    definition degenerate (duplicate literals, sometimes a tautology); that
    boundary is measured separately in ``degenerate_sources``.
    """

    if len(pool) >= arity:
        return rng.sample(list(pool), arity)
    return [pick(rng, pool) for _ in range(arity)]


def random_clause(rng: random.Random, pool: Sequence[str], width: int) -> list[list[Any]]:
    return [[pick(rng, pool), rng.randrange(2)] for _ in range(width)]


def build_circuit_instance(rng: random.Random) -> dict[str, Any]:
    input_count = 3 + rng.randrange(4)
    inputs = [f"i{k}" for k in range(input_count)]
    gate_count = 8 + rng.randrange(73)
    gates: list[dict[str, Any]] = []
    pool = list(inputs)
    for position in range(gate_count):
        op = GATE_OPS[rng.randrange(len(GATE_OPS))]
        out = f"g{position}"
        if op == "const":
            gates.append({"op": op, "out": out, "args": [], "value": rng.randrange(2)})
        elif op in ("not", "buf"):
            gates.append({"op": op, "out": out, "args": pick_arguments(rng, pool, 1)})
        elif op == "mux":
            gates.append({"op": op, "out": out, "args": pick_arguments(rng, pool, 3)})
        else:
            gates.append({"op": op, "out": out, "args": pick_arguments(rng, pool, 2)})
        pool.append(out)

    assertion_count = rng.choice([0, 1, 2, 3, 3])
    targets = sorted(pool[input_count:], key=lambda _gate_name: rng.random())[:assertion_count]
    assertions = [[name, rng.randrange(2)] for name in targets]
    clauses: list[list[list[Any]]] = []
    for _ in range(rng.choice([0, 1, 2, 2, 3])):
        clauses.append(random_clause(rng, pool, rng.choice([1, 2, 2, 3, 3, 4])))

    return {
        "kind": "circuit",
        "inputs": inputs,
        "gates": gates,
        "assertions": assertions,
        "relations": [],
        "clauses": clauses,
    }


def build_mix_instance(rng: random.Random, index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    signal_count = 4 + (index % 5)
    signals = [f"s{k}" for k in range(signal_count)]
    pattern = ("random", "unit_fix", "parity_conflict")[index % 3]
    relations: list[dict[str, Any]] = []
    clauses: list[list[list[Any]]] = []

    for _ in range(1 + rng.randrange(2)):
        width = 2 + rng.randrange(min(3, signal_count - 1))
        relations.append({"kind": "xor", "args": rng.sample(signals, width), "rhs": rng.randrange(2)})
    for _ in range(1 + rng.randrange(2)):
        width = 2 + rng.randrange(min(3, signal_count - 1))
        bounds = sorted([rng.randrange(width + 1), rng.randrange(width + 1)])
        relations.append(
            {"kind": "cardinality", "args": rng.sample(signals, width), "min": bounds[0], "max": bounds[1]}
        )

    detail: dict[str, Any] = {"pattern": pattern, "signals": signal_count}
    if pattern == "unit_fix":
        # Two unit facts plus a parity relation entail the third argument: the shape
        # the algebraic prepass can admit as an augmentation before search starts.
        args = rng.sample(signals, 3)
        relations.append({"kind": "xor", "args": args, "rhs": 0})
        clauses.append([[args[0], 1]])
        clauses.append([[args[1], 1]])
        detail["unit_fix_args"] = args
    elif pattern == "parity_conflict":
        # Parity relation plus all-ones units: inconsistent by construction, and
        # squarely inside the GF(2) elimination the algebraic prepass runs.
        args = rng.sample(signals, 3)
        relations.append({"kind": "xor", "args": args, "rhs": 0})
        for name in args:
            clauses.append([[name, 1]])
        detail["conflict_args"] = args
    else:
        for _ in range(2 + rng.randrange(4)):
            clauses.append(random_clause(rng, signals, min(rng.choice([1, 2, 2, 3, 3, 4]), signal_count)))

    detail["relations"] = len(relations)
    detail["clauses"] = len(clauses)
    return {
        "kind": "circuit",
        "inputs": signals,
        "gates": [],
        "assertions": [],
        "relations": relations,
        "clauses": clauses,
    }, detail


def build_pigeonhole(k: int) -> tuple[dict[str, Any], dict[str, Any]]:
    holes = k - 1
    signals = [f"p{i}_{j}" for i in range(k) for j in range(holes)]
    relations: list[dict[str, Any]] = [
        {"kind": "cardinality", "args": [f"p{i}_{j}" for j in range(holes)], "min": 1, "max": 1}
        for i in range(k)
    ]
    relations.extend(
        {"kind": "cardinality", "args": [f"p{i}_{j}" for i in range(k)], "min": 0, "max": 1}
        for j in range(holes)
    )
    spec = {
        "kind": "circuit",
        "inputs": signals,
        "gates": [],
        "assertions": [],
        "relations": relations,
        "clauses": [],
    }
    detail = {
        "construction": f"{k} pigeons into {holes} holes: exactly-one per pigeon, at-most-one per hole",
        "pigeons": k,
        "holes": holes,
        "pigeon_variables": len(signals),
    }
    return spec, detail


def build_parity(flipped: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = {
        "kind": "circuit",
        "inputs": ["x0", "x1", "x2", "x3", "x4"],
        "gates": [],
        "assertions": [["x2", 0], ["x3", 0], ["x4", 1 if flipped else 0]],
        "relations": [
            {"kind": "xor", "args": ["x0", "x1", "x2"], "rhs": 0},
            {"kind": "xor", "args": ["x2", "x3", "x4"], "rhs": 0},
        ],
        "clauses": [],
    }
    detail = {
        "construction": (
            "planted XOR chain x2 = x0^x1, x4 = x2^x3 with boundary x2=0, x3=0 and "
            + ("a flipped boundary x4=1 (inconsistent)" if flipped else "a consistent boundary x4=0")
        ),
        "flipped_boundary": flipped,
    }
    return spec, detail


def build_reachability(rng: random.Random, index: int) -> dict[str, Any]:
    horizon = 1 + (index % 4)
    state_names = [f"s{k}" for k in range(2 + (index % 2))]
    input_names = [f"u{k}" for k in range(1 + (index % 2))]

    gates: list[dict[str, Any]] = [
        {"op": "mux", "out": "gmux", "args": [state_names[0], input_names[0], state_names[-1]]},
        {"op": "xor", "out": "gxor", "args": [state_names[-1], input_names[-1]]},
    ]
    pool = list(state_names) + list(input_names) + ["gmux", "gxor"]
    for position in range(rng.randrange(3)):
        out = f"g{position}"
        op = ("and", "or", "nand", "not", "xor")[rng.randrange(5)]
        gates.append({"op": op, "out": out, "args": pick_arguments(rng, pool, 1 if op == "not" else 2)})
        pool.append(out)

    next_state: list[list[str]] = []
    for name in state_names:
        roll = rng.random()
        if roll < 0.6:
            origin = pool[rng.randrange(len(pool))]
        elif roll < 0.8:
            origin = input_names[rng.randrange(len(input_names))]
        else:
            origin = state_names[rng.randrange(len(state_names))]
        next_state.append([name, origin])

    initial = [[name, rng.randrange(2)] for name in state_names if rng.random() < 0.8]
    input_assertions = [
        [rng.randrange(horizon), input_names[rng.randrange(len(input_names))], rng.randrange(2)]
        for _ in range(rng.randrange(3))
    ]
    final = [[name, rng.randrange(2)] for name in state_names if rng.random() < 0.6]
    clauses: list[list[list[Any]]] = []
    if rng.random() < 0.5:
        # Source clauses are (signal, polarity) pairs for both kinds; the compiler's
        # pair validator rejects the optional third ``time`` entry even for
        # transitions, so a clause always applies at time 0.
        clauses.append(
            [
                [state_names[rng.randrange(len(state_names))], rng.randrange(2)],
                [input_names[rng.randrange(len(input_names))], rng.randrange(2)],
            ]
        )

    return {
        "kind": "transition",
        "state": state_names,
        "inputs": input_names,
        "gates": gates,
        "next_state": next_state,
        "horizon": horizon,
        "initial": initial,
        "input_assertions": input_assertions,
        "final": final,
        "relations": [],
        "clauses": clauses,
    }


def build_matrix(quick: bool) -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    instances: list[dict[str, Any]] = []

    for index in range(10):
        spec = build_circuit_instance(rng)
        instances.append(
            {
                "name": f"circuit-{index:02d}",
                "family": "circuits",
                "spec": spec,
                "label_source": "enumeration",
                "construction": None,
                "parameters": {
                    "inputs": len(spec["inputs"]),
                    "gates": len(spec["gates"]),
                    "assertions": len(spec["assertions"]),
                    "clauses": len(spec["clauses"]),
                },
            }
        )

    for index in range(10):
        spec, detail = build_mix_instance(rng, index)
        instances.append(
            {
                "name": f"mix-{index:02d}",
                "family": "clause-parity-cardinality",
                "spec": spec,
                "label_source": "enumeration",
                "construction": detail["pattern"],
                "parameters": detail,
            }
        )

    for k in (3, 4, 5):
        spec, detail = build_pigeonhole(k)
        instances.append(
            {
                "name": f"pigeonhole-{k}",
                "family": "pigeonhole",
                "spec": spec,
                "label_source": "construction",
                "construction": detail["construction"],
                "parameters": detail,
                "expected_label": "unsat",
            }
        )

    for flipped in (False, True):
        spec, detail = build_parity(flipped)
        instances.append(
            {
                "name": "parity-flipped" if flipped else "parity-consistent",
                "family": "parity",
                "spec": spec,
                "label_source": "construction",
                "construction": detail["construction"],
                "parameters": detail,
                "expected_label": "unsat" if flipped else "sat",
            }
        )

    for index in range(6):
        spec = build_reachability(rng, index)
        instances.append(
            {
                "name": f"reachability-{index:02d}",
                "family": "reachability",
                "spec": spec,
                "label_source": "enumeration",
                "construction": None,
                "parameters": {
                    "states": len(spec["state"]),
                    "inputs": len(spec["inputs"]),
                    "gates": len(spec["gates"]),
                    "horizon": spec["horizon"],
                    "initial_assertions": len(spec["initial"]),
                    "input_assertions": len(spec["input_assertions"]),
                    "final_assertions": len(spec["final"]),
                },
            }
        )

    if not quick:
        return instances
    firsts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for instance in instances:
        if instance["family"] not in seen:
            seen.add(instance["family"])
            firsts.append(instance)
    return firsts


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------


def literal_key(literal: int) -> tuple[int, bool]:
    return abs(literal), literal < 0


def hybrid_audit_formula(result: Mapping[str, Any]) -> tuple[list[list[int]], int]:
    """The compiled clause database plus a count of rows needing literal reordering.

    The compiled payload is the clause database handed to both backends, and the
    compiler canonicalizes every clause (literals sorted by ``(abs, sign)``,
    duplicate literals removed, tautologies dropped).  The count is reported as
    evidence that the payload is already in the hybrid auditor's canonical form.
    """

    rows = [[int(literal) for literal in clause] for clause in result["compiled"]["clauses"]]
    reordered = sum(1 for row in rows if row != sorted(row, key=literal_key))
    return rows, reordered


def make_profile(
    compiled: CompiledConstraintProblem,
    mode: str,
    controller: bool,
    arity: int = 1,
) -> ConstraintFieldProfile:
    clause_count = len(compiled.clauses)
    return ConstraintFieldProfile(
        max_variables=max(1, compiled.variables),
        max_clauses=clause_count + AUGMENTATION_HEADROOM,
        mode=mode,
        controller=controller,
        max_augmentations=AUGMENTATION_HEADROOM,
        max_augmentation_arity=arity,
    )


def run_configuration(
    compiled: CompiledConstraintProblem,
    mode: str,
    controller: bool,
    arity: int = 1,
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    profile = make_profile(compiled, mode, controller, arity)
    field = ConstraintField(profile)
    state = field.initial(compiled)
    started = time.perf_counter()
    state, result = field.solve(state)
    seconds = time.perf_counter() - started
    receipt = {
        "mode": mode,
        "controller": controller,
        "seconds": seconds,
        "status": result["status"],
        "reason": result["reason"],
        "profile": profile.as_dict(),
        "profile_sha256": result["profile_sha256"],
        "search": result["work"]["search"],
        "hybrid_work": result["work"]["hybrid"],
        "controller_work": result["work"]["controller"],
        "compile_work": result["work"]["compile"],
        "augmentation_count": result["work"]["augmentations"],
        "augmentations": result["augmentations"],
        "journal_bytes": result["work"]["journal_bytes"],
        "prepass": result["work"].get("prepass"),
        "learned_clauses": len(result["learned_clauses"]),
        "backend_clause_count": None if result["backend_clauses"] is None else len(result["backend_clauses"]),
        "checkpoint": result["checkpoint"],
        "state_sha256": result["state_sha256"],
        "has_resolution_proof": result["resolution_proof"] is not None,
        "has_hybrid_proof": result["hybrid_proof"] is not None,
    }
    return receipt, result


def audit_result(result: Mapping[str, Any], profile: Mapping[str, Any]) -> dict[str, Any]:
    """Audit every certificate the result carries; an UNSAT verdict needs one."""

    receipts: list[dict[str, Any]] = []
    variables = int(result["compiled"]["variables"])
    if result["resolution_proof"] is not None:
        search = result["work"]["search"]
        started = time.perf_counter()
        summary = audit_resolution_proof(
            formula=result["backend_clauses"],
            learned=result["learned_clauses"],
            value=result["resolution_proof"],
            variables=variables,
            status="unsat",
            expected_conflicts=int(search["conflicts"]),
            max_learned_clauses=int(profile["max_learned_clauses"]),
        )
        receipts.append({"kind": "resolution", "seconds": time.perf_counter() - started, "summary": summary})
    if result["hybrid_proof"] is not None:
        formula, reordered_clauses = hybrid_audit_formula(result)
        started = time.perf_counter()
        summary = audit_hybrid_proof(
            formula,
            result["hybrid_proof"],
            variables=variables,
        )
        receipts.append(
            {
                "kind": "hybrid",
                "seconds": time.perf_counter() - started,
                "clauses_needing_literal_reorder": reordered_clauses,
                "summary": summary,
            }
        )
    if result["status"] == "unsat" and not receipts:
        raise AssertionError("unsat verdict carries no certificate to audit")
    return {"receipts": receipts, "seconds": sum(float(row["seconds"]) for row in receipts)}


def check_witness(instance: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    """Independently evaluate a SAT witness and its full source assignment."""

    spec = instance["spec"]
    values, unassigned = signal_values_from_assignment(result["compiled"], result["assignment"])
    witness = {str(label): int(bit) for label, bit in result["witness"].items()}

    bits: dict[str, int] = {}
    if spec["kind"] == "circuit":
        bits.update({str(name): witness[str(name)] for name in spec["inputs"]})
        expected, problems = evaluate_circuit(spec, bits)
        expected_label_keys = {name: str(name) for name in spec["inputs"]}
    else:
        horizon = int(spec["horizon"])
        bits.update({str(name): witness[f"{name}@0"] for name in spec["state"]})
        bits.update(
            {
                f"{name}@{moment}": witness[f"{name}@{moment}"]
                for moment in range(horizon)
                for name in spec["inputs"]
            }
        )
        expected, problems = source_expected_values(spec, bits)
        expected_label_keys = {f"{name}@0": f"s:{name}:0" for name in spec["state"]}
        expected_label_keys.update(
            {
                f"{name}@{moment}": f"i:{name}:{moment}"
                for moment in range(horizon)
                for name in spec["inputs"]
            }
        )

    constraint_problems = problems + source_constraint_problems(spec, bits, expected)
    mismatch = sorted(name for name, value in expected.items() if values.get(name) != value)
    witness_mismatch = sorted(
        label
        for label, bit in witness.items()
        if expected.get(expected_label_keys.get(label, "")) != bit
    )
    return {
        "signal_values_checked": len(expected),
        "witness_labels_checked": len(witness),
        "unassigned_variables": len(unassigned),
        "assignment_complete": not unassigned,
        "source_constraint_problems": constraint_problems,
        "assignment_mismatch": mismatch,
        "witness_mismatch": witness_mismatch,
        "ok": not constraint_problems and not mismatch and not witness_mismatch and not unassigned,
    }


def perform_run(
    instance_name: str,
    spec: Mapping[str, Any],
    compiled: CompiledConstraintProblem,
    mode: str,
    controller: bool,
    repeat: int,
    arity: int = 1,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Run one configuration, audit its certificates, check its witness.

    Returns the run receipt and the failures observed for it; a solver error is
    returned as an error receipt so callers can classify it.
    """

    problems: list[dict[str, str]] = []

    def failed(kind: str, detail: str) -> None:
        problems.append({"instance": instance_name, "kind": kind, "detail": detail})

    try:
        receipt, result = run_configuration(compiled, mode, controller, arity)
    except Exception as exc:  # noqa: BLE001 - a measured availability boundary
        detail = f"{type(exc).__name__}: {exc}"
        failed("solver-error", f"mode={mode} controller={controller}: {detail}")
        return {"mode": mode, "controller": controller, "repeat": repeat, "error": detail}, problems

    receipt["repeat"] = repeat
    if result["status"] == "unsat" or result["hybrid_proof"] is not None:
        try:
            receipt["audit"] = audit_result(result, receipt["profile"])
        except Exception as exc:  # noqa: BLE001 - an audit mismatch is terminal
            failed(
                "certificate-audit-mismatch",
                f"mode={mode} controller={controller}: {type(exc).__name__}: {exc}",
            )
    if result["status"] == "unsat" and "audit" not in receipt:
        failed("missing-certificate-audit", f"mode={mode} controller={controller}")
    if result["status"] == "sat":
        try:
            witness = check_witness({"spec": spec}, result)
            receipt["witness_check"] = witness
            if not witness["ok"]:
                failed(
                    "witness-mismatch",
                    f"mode={mode} controller={controller}: {json.dumps(witness)[:400]}",
                )
        except Exception as exc:  # noqa: BLE001
            failed(
                "witness-check-error",
                f"mode={mode} controller={controller}: {type(exc).__name__}: {exc}",
            )
    return receipt, problems


def build_edge_sources() -> list[dict[str, Any]]:
    """Sources whose gates repeat an argument, so their Tseitin definitions are degenerate.

    ``xor(x, x)`` and ``nand(x, x)`` emit clauses with duplicate literals and, for
    some operations, tautologies.  The compiler now canonicalizes each clause
    (duplicate literals removed, tautologies dropped) before de-duplication, so
    these sources measure whether that canonicalization actually makes the
    degenerate case solvable in every mode.
    """

    return [
        {
            "name": "repeated-arg-xor",
            "detail": "xor gate with a repeated argument (x^x = 0); its raw Tseitin definition repeats literals",
            "spec": {
                "kind": "circuit",
                "inputs": ["a"],
                "gates": [{"op": "xor", "out": "g", "args": ["a", "a"]}],
                "assertions": [["g", 1]],
                "relations": [],
                "clauses": [],
            },
        },
        {
            "name": "repeated-arg-nand",
            "detail": "nand gate with a repeated argument (x nand x); its raw Tseitin definition contains tautologies",
            "spec": {
                "kind": "circuit",
                "inputs": ["a", "b"],
                "gates": [{"op": "nand", "out": "g", "args": ["a", "a"]}],
                "assertions": [["g", 1]],
                "relations": [],
                "clauses": [],
            },
        },
    ]


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--json", default=DEFAULT_OUTPUT, help="receipt output path")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="reduced matrix: only the first instance of each family",
    )
    args = parser.parse_args(argv)

    started = time.perf_counter()
    instances = build_matrix(args.quick)
    failures: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    for instance in instances:
        spec = instance["spec"]
        compiler = compile_circuit if spec["kind"] == "circuit" else compile_transition_problem
        compiled = compiler(spec)
        record: dict[str, Any] = {
            "name": instance["name"],
            "family": instance["family"],
            "label_source": instance["label_source"],
            "construction": instance["construction"],
            "parameters": instance["parameters"],
            "spec": spec,
            "compiled": compiled.as_dict(),
            "compiled_sha256": compiled.sha256,
            "variables": compiled.variables,
            "clause_count": len(compiled.clauses),
        }

        enumeration = enumerate_label(spec)
        record["enumeration"] = enumeration
        record["label_in_capacity"] = enumeration["in_capacity"]
        if instance["label_source"] == "construction":
            record["label"] = instance["expected_label"]
            if enumeration["in_capacity"] and enumeration["label"] != record["label"]:
                failures.append(
                    {
                        "instance": instance["name"],
                        "kind": "label-conflict",
                        "detail": f"construction {record['label']} vs enumeration {enumeration['label']}",
                    }
                )
        else:
            record["label"] = enumeration["label"]
            if not enumeration["in_capacity"]:
                failures.append(
                    {"instance": instance["name"], "kind": "label-out-of-capacity", "detail": enumeration["note"]}
                )

        configurations = [(mode, False) for mode in MODES]
        runs: list[dict[str, Any]] = []

        def record_configuration(mode: str, controller: bool) -> None:
            for repeat in range(REPEATS):
                receipt, problems = perform_run(instance["name"], spec, compiled, mode, controller, repeat)
                failures.extend(problems)
                runs.append(receipt)

        for mode, controller in configurations:
            record_configuration(mode, controller)

        conflict_off = [
            run
            for run in runs
            if run["mode"] == "conflict" and not run["controller"] and run.get("search")
        ]
        needs_decision = any(int(run["search"]["decisions"]) > 0 for run in conflict_off)
        record["needs_decision"] = needs_decision
        if needs_decision:
            for mode in ("conflict", "algebraic"):
                record_configuration(mode, True)

        for key in sorted({(run["mode"], run["controller"]) for run in runs}):
            group = [
                run for run in runs if (run["mode"], run["controller"]) == key and "status" in run
            ]
            if not group:
                continue
            digests = sorted({run["state_sha256"] for run in group})
            verdicts = sorted({(run["status"], run["reason"]) for run in group})
            identical = len(digests) == 1 and len(verdicts) == 1
            for run in group:
                run["deterministic"] = identical
                run["repeat_state_sha256"] = digests
            if not identical:
                failures.append(
                    {
                        "instance": instance["name"],
                        "kind": "non-determinism",
                        "detail": f"mode={key[0]} controller={key[1]} digests={digests} verdicts={verdicts}",
                    }
                )

        for run in runs:
            if "status" not in run:
                run["agreement"] = None
                continue
            run["agreement"] = None if run["status"] == "exhausted" else run["status"] == record["label"]
            if run["agreement"] is False:
                failures.append(
                    {
                        "instance": instance["name"],
                        "kind": "verdict-mismatch",
                        "detail": f"mode={run['mode']} controller={run['controller']} "
                        f"verdict={run['status']} label={record['label']}",
                    }
                )

        record["runs"] = runs
        receipts.append(record)
        for run in runs:
            if "status" not in run:
                continue
            rows.append(
                {
                    "family": instance["family"],
                    "instance": instance["name"],
                    "mode": run["mode"],
                    "controller": run["controller"],
                    "label": record["label"],
                    "status": run["status"],
                    "reason": run["reason"],
                    "agreement": run["agreement"],
                    "seconds": run["seconds"],
                    "decisions": None if run["search"] is None else run["search"]["decisions"],
                    "conflicts": None if run["search"] is None else run["search"]["conflicts"],
                    "learned": run["learned_clauses"],
                    "augmentations": run["augmentation_count"],
                    "hybrid": None if run["hybrid_work"] is None else run["hybrid_work"]["status"],
                    "journal_bytes": run["journal_bytes"],
                    "field_bytes": run["checkpoint"]["field_bytes"],
                    "controller_ticks": run["controller_work"]["ticks"],
                    "controller_selections": run["controller_work"]["selections"],
                    "controller_interventions": run["controller_work"]["interventions"],
                    "deterministic": run["deterministic"],
                }
            )

    observations: list[dict[str, Any]] = [
        {
            "instance": "compiler-interface",
            "kind": "interface-note",
            "detail": (
                "source clauses are validated as (signal, polarity) pairs for both source kinds, "
                "so the optional third 'time' entry handled by _time_literals is unreachable and "
                "every transition source clause applies at time 0"
            ),
        }
    ]
    degenerate: list[dict[str, Any]] = []
    for source in build_edge_sources():
        spec = source["spec"]
        compiled = compile_circuit(spec)
        enumeration = enumerate_label(spec)
        entry: dict[str, Any] = {
            "name": source["name"],
            "detail": source["detail"],
            "spec": spec,
            "compiled_sha256": compiled.sha256,
            "variables": compiled.variables,
            "clause_count": len(compiled.clauses),
            "label": enumeration["label"],
            "label_source": "enumeration",
            "free_variables": enumeration["free_variables"],
            "modes": {},
        }
        for mode in MODES:
            receipt, problems = perform_run(source["name"], spec, compiled, mode, False, 0)
            for problem in problems:
                if problem["kind"] == "solver-error":
                    observations.append(problem)
                else:
                    failures.append(problem)
            entry["modes"][mode] = receipt
            if "status" in receipt and receipt["status"] != "exhausted" and receipt["status"] != enumeration["label"]:
                failures.append(
                    {
                        "instance": source["name"],
                        "kind": "verdict-mismatch",
                        "detail": f"mode={mode} verdict={receipt['status']} label={enumeration['label']}",
                    }
                )
        degenerate.append(entry)

    total_seconds = time.perf_counter() - started
    summary, table = summarise(receipts, rows, failures, observations, degenerate, total_seconds)
    document = {
        "schema": "cassifi.constraint-field-experiment-receipt.v1",
        "seed": SEED,
        "quick": bool(args.quick),
        "modes": list(MODES),
        "repeats": REPEATS,
        "enumeration_bit_limit": ENUMERATION_BIT_LIMIT,
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "instances": receipts,
        "degenerate_sources": degenerate,
        "summary": summary,
        "failures": failures,
    }

    output = Path(args.json)
    if not output.is_absolute():
        output = Path(__file__).resolve().parent / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=1, sort_keys=True), encoding="utf-8")

    print(table)
    print()
    print("edge sources (gates with a repeated argument):")
    for entry in degenerate:
        modes = " ".join(
            f"{mode}=" + (receipt.get("error", receipt.get("status", "?")) if isinstance(receipt, Mapping) else "?")
            for mode, receipt in entry["modes"].items()
        )
        print(f"  {entry['name']:<18} label={entry['label']:<6} {modes}")
    print()
    for failure in failures:
        print(f"case {failure['instance']}: {failure['kind']}: {failure['detail']}")
    if failures:
        print()
    print("summary:")
    print(json.dumps(summary, indent=1, sort_keys=True))
    print()
    print(f"receipt: {output}")
    return 1 if failures else 0


def _ledger_totals(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "runs": len(rows),
        "decisions": sum(int(row["decisions"] or 0) for row in rows),
        "conflicts": sum(int(row["conflicts"] or 0) for row in rows),
        "learned_clauses": sum(int(row["learned"]) for row in rows),
        "augmentations": sum(int(row["augmentations"]) for row in rows),
        "controller_ticks": sum(int(row["controller_ticks"]) for row in rows),
        "controller_selections": sum(int(row["controller_selections"]) for row in rows),
        "controller_interventions": sum(int(row["controller_interventions"]) for row in rows),
    }


def _prepass_counts(receipts: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in receipts:
        for run in record["runs"]:
            prepass = run.get("prepass")
            key = "none" if prepass is None else f"{prepass['status']}"
            if isinstance(prepass, Mapping) and prepass.get("reason"):
                key = f"{prepass['status']}:{prepass['reason']}"
            counts[key] = counts.get(key, 0) + 1
    return counts


def summarise(
    receipts: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    degenerate: Sequence[Mapping[str, Any]],
    total_seconds: float,
) -> tuple[dict[str, Any], str]:
    family_counts: dict[str, int] = {}
    for record in receipts:
        family_counts[record["family"]] = family_counts.get(record["family"], 0) + 1

    by_mode: dict[str, dict[str, int]] = {
        mode: {"decided": 0, "agreed": 0, "exhausted": 0} for mode in MODES
    }
    by_family: dict[str, dict[str, int]] = {}
    for row in rows:
        buckets = [by_mode[row["mode"]], by_family.setdefault(row["family"], {"decided": 0, "agreed": 0, "exhausted": 0})]
        for bucket in buckets:
            if row["status"] == "exhausted":
                bucket["exhausted"] += 1
            else:
                bucket["decided"] += 1
                if row["agreement"]:
                    bucket["agreed"] += 1

    local_stalls = sorted(
        {row["instance"] for row in rows if row["mode"] == "local" and row["status"] == "exhausted"}
    )
    local_decided = sorted(
        {row["instance"] for row in rows if row["mode"] == "local" and row["status"] != "exhausted"}
    )
    hybrid_refuted = sorted(
        {
            row["instance"]
            for row in rows
            if row["mode"] == "algebraic" and not row["controller"] and row["reason"] == "hybrid-refutation"
        }
    )
    augmented = sorted(
        {row["instance"] for row in rows if row["mode"] == "algebraic" and row["augmentations"] > 0}
    )

    controller_compare: dict[str, Any] = {}
    for mode in ("conflict", "algebraic"):
        on = [row for row in rows if row["mode"] == mode and row["controller"]]
        compared = sorted({row["instance"] for row in on})
        off = [
            row
            for row in rows
            if row["mode"] == mode and not row["controller"] and row["instance"] in set(compared)
        ]
        controller_compare[mode] = {
            "instances": compared,
            "off": _ledger_totals(off),
            "on": _ledger_totals(on),
            "verdict_disagreements": sorted(
                {
                    row["instance"]
                    for row in on
                    for other in off
                    if other["instance"] == row["instance"]
                    and other["status"] != "exhausted"
                    and row["status"] != "exhausted"
                    and other["status"] != row["status"]
                }
            ),
        }

    resolution_audits = 0
    hybrid_audits = 0
    hybrid_unsat_roots = 0
    audit_seconds = 0.0
    for record in receipts:
        for run in record["runs"]:
            audit = run.get("audit")
            if not audit:
                continue
            audit_seconds += float(audit["seconds"])
            for receipt in audit["receipts"]:
                if receipt["kind"] == "resolution":
                    resolution_audits += 1
                else:
                    hybrid_audits += 1
                    if receipt["summary"].get("status") == "unsat":
                        hybrid_unsat_roots += 1

    witness_checks = [run for record in receipts for run in record["runs"] if "witness_check" in run]
    deterministic_rows = [row for row in rows if row["deterministic"]]

    mode_disagreements: list[dict[str, Any]] = []
    for record in receipts:
        verdicts: dict[str, list[str]] = {}
        for run in record["runs"]:
            verdicts.setdefault(run["mode"], [])
            if run["status"] not in verdicts[run["mode"]]:
                verdicts[run["mode"]].append(run["status"])
        sets = {tuple(sorted(values)) for values in verdicts.values()}
        if len(sets) > 1:
            mode_disagreements.append({"instance": record["name"], "by_mode": verdicts})

    largest = max(rows, key=lambda row: float(row["seconds"])) if rows else None
    configurations = sum(len({(run["mode"], run["controller"]) for run in record["runs"]}) for record in receipts)

    summary = {
        "instances_per_family": family_counts,
        "instance_count": len(receipts),
        "run_count": len(rows),
        "labels": {
            "from_enumeration": sum(1 for record in receipts if record["label_source"] == "enumeration"),
            "from_construction": sum(1 for record in receipts if record["label_source"] == "construction"),
            "construction_checked_by_enumeration": sum(
                1
                for record in receipts
                if record["label_source"] == "construction" and record["label_in_capacity"]
            ),
            "sat": sum(1 for record in receipts if record["label"] == "sat"),
            "unsat": sum(1 for record in receipts if record["label"] == "unsat"),
        },
        "verdict_agreement": {"by_mode": by_mode, "by_family": by_family},
        "local_mode": {"stall_instances": local_stalls, "propagation_only_decisions": local_decided},
        "algebraic_prepass": {
            "unaided_refutation_instances": hybrid_refuted,
            "augmentation_instances": augmented,
            "augmentation_runs": sum(
                1
                for record in receipts
                for run in record["runs"]
                if run["mode"] == "algebraic" and run["augmentation_count"] > 0
            ),
            "prepass_status_counts": _prepass_counts(receipts),
        },
        "controller_on_vs_off": controller_compare,
        "certificates": {
            "unsat_runs": sum(1 for record in receipts for run in record["runs"] if run["status"] == "unsat"),
            "resolution_audits": resolution_audits,
            "hybrid_audits": hybrid_audits,
            "hybrid_audits_with_unsat_root": hybrid_unsat_roots,
            "failed_audits": sum(1 for row in failures if "audit" in row["kind"]),
            "audit_seconds": audit_seconds,
        },
        "witnesses": {
            "sat_runs": sum(1 for record in receipts for run in record["runs"] if run["status"] == "sat"),
            "checked": len(witness_checks),
            "ok": sum(1 for run in witness_checks if run["witness_check"]["ok"]),
        },
        "determinism": {
            "configurations": configurations,
            "runs": len(rows),
            "runs_with_identical_repeat": len(deterministic_rows),
            "violations": [
                {
                    "instance": row["instance"],
                    "mode": row["mode"],
                    "controller": row["controller"],
                }
                for row in rows
                if not row["deterministic"]
            ],
        },
        "mode_disagreements": mode_disagreements,
        "degenerate_sources": {
            "count": len(degenerate),
            "entries": [
                {
                    "name": entry["name"],
                    "label": entry["label"],
                    "free_variables": entry["free_variables"],
                    "modes": {
                        mode: (
                            receipt.get("error", receipt.get("status"))
                            if isinstance(receipt, Mapping)
                            else None
                        )
                        for mode, receipt in entry["modes"].items()
                    },
                }
                for entry in degenerate
            ],
            "note": (
                "gates that repeat an argument make a degenerate Tseitin definition (duplicate "
                "literals, tautologies); these entries record what each mode does with such a "
                "source after the compiler's clause canonicalization"
            ),
        },
        "observations": [dict(row) for row in observations],
        "wall_clock_seconds": {
            "matrix_total": total_seconds,
            "largest_case": None
            if largest is None
            else {
                "instance": largest["instance"],
                "mode": largest["mode"],
                "controller": largest["controller"],
                "seconds": largest["seconds"],
            },
        },
        "measurement_note": (
            "single host-side time.perf_counter measurement on one machine; not a benchmark "
            "and no complexity claim"
        ),
        "failures": [dict(row) for row in failures],
    }

    header = (
        f"{'family':<24} {'instance':<16} {'mode':<9} {'ctrl':<4} {'status':<10} {'reason':<24}"
        f"{'label':<6} {'agree':<6} {'secs':>8} {'dec':>5} {'cfl':>5} {'lrn':>5} {'aug':>4} {'hybrid':<10}"
    )
    lines = [header, "-" * len(header)]
    for row in rows:
        agreement = "-" if row["agreement"] is None else ("yes" if row["agreement"] else "no")
        decisions = "-" if row["decisions"] is None else str(row["decisions"])
        conflicts = "-" if row["conflicts"] is None else str(row["conflicts"])
        lines.append(
            f"{row['family']:<24} {row['instance']:<16} {row['mode']:<9} "
            f"{('on' if row['controller'] else 'off'):<4} {row['status']:<10} {row['reason']:<24}"
            f"{row['label']:<6} {agreement:<6} {row['seconds']:>8.4f} {decisions:>5} {conflicts:>5}"
            f" {row['learned']:>5} {row['augmentations']:>4} "
            f"{('-' if row['hybrid'] is None else row['hybrid']):<10}"
        )
    return summary, "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
