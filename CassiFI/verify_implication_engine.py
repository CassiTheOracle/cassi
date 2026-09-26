#!/usr/bin/env python
"""Enumerate declared CassiFI implication sources and audit their receipts.

The verifier measures agreement between an independent source-level evaluator and
``cassi_constraint_implication.imply``.  It also audits every certificate used by
the agreed holding rules and checks that binary algebraic augmentations preserve
the compiled clause models.
"""

from __future__ import annotations

import itertools
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import cassi_constraint_implication as implication
import verify_hybrid_inference as hybrid_audit
import verify_p_vs_np_clause_field_probe as clause_audit
from cassi_constraint_field import (
    ConstraintField,
    ConstraintFieldError,
    ConstraintFieldProfile,
    compile_circuit,
    compile_transition_problem,
)

RECEIPT = Path("_diag/implication_engine_verify.json")


def gate_value(op: str, args: Sequence[int], value: Any = None) -> int:
    if op == "const":
        return int(value)
    if op == "buf":
        return int(args[0])
    if op == "not":
        return 1 - int(args[0])
    if op == "and":
        return int(args[0] & args[1])
    if op == "or":
        return int(args[0] | args[1])
    if op == "xor":
        return int(args[0] ^ args[1])
    if op == "nand":
        return 1 - int(args[0] & args[1])
    if op == "nor":
        return 1 - int(args[0] | args[1])
    if op == "xnor":
        return 1 - int(args[0] ^ args[1])
    if op == "mux":
        return int(args[1] if args[0] else args[2])
    raise AssertionError(f"unsupported gate {op!r}")


def resolve_circuit(source: Mapping[str, Any], assignment: Mapping[str, int]) -> dict[str, int]:
    values = {str(name): int(assignment[str(name)]) for name in source["inputs"]}
    pending = [dict(gate) for gate in source.get("gates", ())]
    while pending:
        progressed = False
        remaining: list[dict[str, Any]] = []
        for gate in pending:
            args = [str(arg) for arg in gate["args"]]
            if all(arg in values for arg in args):
                values[str(gate["out"])] = gate_value(
                    str(gate["op"]), [values[arg] for arg in args], gate.get("value")
                )
                progressed = True
            else:
                remaining.append(gate)
        if not progressed:
            raise AssertionError("independent circuit evaluator found a cycle")
        pending = remaining
    return values


def relation_holds(relation: Mapping[str, Any], values: Mapping[str, int]) -> bool:
    bits = [int(values[str(name)]) for name in relation["args"]]
    if relation["kind"] == "xor":
        parity = 0
        for bit in bits:
            parity ^= bit
        return parity == int(relation["rhs"])
    total = sum(bits)
    return int(relation["min"]) <= total <= int(relation["max"])


def row_holds(row: Sequence[Any], lookup) -> bool:
    return any(int(lookup(str(literal[0]), int(literal[2]) if len(literal) == 3 else 0)) == int(literal[1]) for literal in row)


def circuit_values(source: Mapping[str, Any], assignment: Mapping[str, int]) -> dict[str, int]:
    return resolve_circuit(source, assignment)


def circuit_holds(source: Mapping[str, Any], assignment: Mapping[str, int]) -> bool:
    values = circuit_values(source, assignment)
    if any(values[str(name)] != int(bit) for name, bit in source.get("assertions", ())):
        return False
    if any(not relation_holds(relation, values) for relation in source.get("relations", ())):
        return False
    return all(row_holds(row, lambda name, _time: values[name]) for row in source.get("clauses", ()))


def transition_values(source: Mapping[str, Any], assignment: Mapping[str, int]) -> dict[tuple[str, int], int]:
    state = {str(name) for name in source["state"]}
    inputs = {str(name) for name in source["inputs"]}
    horizon = int(source["horizon"])
    values: dict[tuple[str, int], int] = {}
    for name in state:
        values[(name, 0)] = int(assignment[f"{name}@0"])
    for name in inputs:
        for time_index in range(horizon):
            values[(name, time_index)] = int(assignment[f"{name}@{time_index}"])
    gates = [dict(gate) for gate in source.get("gates", ())]
    for time_index in range(horizon):
        pending = list(gates)
        computed: dict[str, int] = {}
        while pending:
            progressed = False
            remaining: list[dict[str, Any]] = []
            for gate in pending:
                arguments: list[int] = []
                ready = True
                for argument in gate["args"]:
                    stem = str(argument)
                    if stem in computed:
                        arguments.append(computed[stem])
                    elif stem in state or stem in inputs:
                        arguments.append(values[(stem, time_index)])
                    else:
                        ready = False
                        break
                if ready:
                    computed[str(gate["out"])] = gate_value(
                        str(gate["op"]), arguments, gate.get("value")
                    )
                    values[(str(gate["out"]), time_index)] = computed[str(gate["out"])]
                    progressed = True
                else:
                    remaining.append(gate)
            if not progressed:
                raise AssertionError("independent transition evaluator found a cycle")
            pending = remaining
        for target, origin in source.get("next_state", ()):
            origin_name = str(origin)
            values[(str(target), time_index + 1)] = values[(origin_name, time_index)]
    return values


def transition_holds(source: Mapping[str, Any], assignment: Mapping[str, int]) -> bool:
    values = transition_values(source, assignment)
    state = {str(name) for name in source["state"]}
    inputs = {str(name) for name in source["inputs"]}
    horizon = int(source["horizon"])

    def lookup(name: str, time_index: int) -> int:
        if name not in state and name not in inputs and not any(str(g["out"]) == name for g in source.get("gates", ())):
            raise AssertionError(f"independent evaluator cannot resolve {name!r}")
        return int(values[(name, time_index)])

    for name, bit in source.get("initial", ()):
        if lookup(str(name), 0) != int(bit):
            return False
    for time_index, name, bit in source.get("input_assertions", ()):
        if lookup(str(name), int(time_index)) != int(bit):
            return False
    for name, bit in source.get("final", ()):
        if lookup(str(name), horizon) != int(bit):
            return False
    for time_index in range(horizon):
        for relation in source.get("relations", ()):
            relation_values = {str(name): lookup(str(name), time_index) for name in relation["args"]}
            if not relation_holds(relation, relation_values):
                return False
    return all(row_holds(row, lookup) for row in source.get("clauses", ()))


def source_holds(source: Mapping[str, Any], assignment: Mapping[str, int]) -> bool:
    if source.get("kind") == "circuit":
        return circuit_holds(source, assignment)
    if source.get("kind") == "transition":
        return transition_holds(source, assignment)
    raise AssertionError("unsupported source kind")


def reference_signal(source: Mapping[str, Any], assignment: Mapping[str, int], label: str) -> int:
    if source.get("kind") == "circuit":
        return int(circuit_values(source, assignment)[label])
    stem, _, index = label.rpartition("@")
    if not stem or not index.isdigit():
        raise AssertionError(f"bad transition label {label!r}")
    return int(transition_values(source, assignment)[(stem, int(index))])


def witness_labels(source: Mapping[str, Any]) -> list[str]:
    if source["kind"] == "circuit":
        return [str(name) for name in source["inputs"]]
    horizon = int(source["horizon"])
    labels = [f"{name}@0" for name in source["state"]]
    labels.extend(f"{name}@{time_index}" for time_index in range(horizon) for name in source["inputs"])
    return labels


def signal_labels(source: Mapping[str, Any]) -> list[str]:
    if source["kind"] == "circuit":
        return [str(name) for name in source["inputs"]] + [str(gate["out"]) for gate in source.get("gates", ())]
    horizon = int(source["horizon"])
    labels = [f"{name}@{time_index}" for time_index in range(horizon + 1) for name in source["state"]]
    labels.extend(f"{name}@{time_index}" for time_index in range(horizon) for name in source["inputs"])
    labels.extend(f"{gate['out']}@{time_index}" for time_index in range(horizon) for gate in source.get("gates", ()))
    return labels


def enumerate_witness_models(source: Mapping[str, Any]) -> list[dict[str, int]]:
    labels = witness_labels(source)
    models: list[dict[str, int]] = []
    for bits in itertools.product((0, 1), repeat=len(labels)):
        assignment = dict(zip(labels, bits))
        if source_holds(source, assignment):
            models.append(assignment)
    return models


def cnf_models(clauses: Sequence[Sequence[int]], variables: int) -> list[tuple[int, ...]]:
    models: list[tuple[int, ...]] = []
    for bits in itertools.product((0, 1), repeat=variables):
        if all(any((bits[abs(literal) - 1] == 1) == (literal > 0) for literal in clause) for clause in clauses):
            models.append(bits)
    return models


def assumptions_hold(assignment: Mapping[str, int], assumptions: Sequence[Sequence[Any]]) -> bool:
    return all(int(assignment[str(name)]) == int(bit) for name, bit in assumptions)


def query_ground_truth(source: Mapping[str, Any], models: Sequence[Mapping[str, int]], assumptions: Sequence[Sequence[Any]], consequence: Sequence[Any]) -> tuple[list[dict[str, int]], bool, bool]:
    premise_models = [model for model in models if assumptions_hold(model, assumptions)]
    counterexamples = [model for model in premise_models if reference_signal(source, model, str(consequence[0])) != int(consequence[1])]
    return counterexamples, bool(premise_models), bool(premise_models) and not counterexamples


def source_boundary_literals(source: Mapping[str, Any]) -> set[tuple[str, int]]:
    boundaries: set[tuple[str, int]] = set()
    if source["kind"] == "circuit":
        for name, bit in source.get("assertions", ()):
            boundaries.add((str(name), int(bit)))
        for row in source.get("clauses", ()):
            if len(row) == 1:
                boundaries.add((str(row[0][0]), int(row[0][1])))
    else:
        horizon = int(source["horizon"])
        for name, bit in source.get("initial", ()):
            boundaries.add((f"{name}@0", int(bit)))
        for name, bit in source.get("final", ()):
            boundaries.add((f"{name}@{horizon}", int(bit)))
        for time_index, name, bit in source.get("input_assertions", ()):
            boundaries.add((f"{name}@{time_index}", int(bit)))
        for row in source.get("clauses", ()):
            if len(row) == 1:
                literal = row[0]
                time_index = int(literal[2]) if len(literal) == 3 else 0
                boundaries.add((f"{literal[0]}@{time_index}", int(literal[1])))
    return boundaries


def vacuity_boundary_hit(
    source: Mapping[str, Any], assumptions: Sequence[Sequence[Any]]
) -> bool:
    boundaries = source_boundary_literals(source)
    return any(
        (str(name), 1 - int(bit)) in boundaries for name, bit in assumptions
    )


def check_compiled_projection(result: Mapping[str, Any], source: Mapping[str, Any], models: Sequence[Mapping[str, int]], assumptions: Sequence[Sequence[Any]], consequence: Sequence[Any]) -> str | None:
    compiled = result.get("compiled")
    if not isinstance(compiled, Mapping):
        return "holds result has no compiled query payload"
    variables = int(compiled["variables"])
    if variables > 20:
        return None
    query_models = cnf_models(compiled["clauses"], variables)
    witness_map = {str(label): int(identifier) for label, identifier in compiled["witness_signals"]}
    projected = {
        tuple(1 if bits[witness_map[label] - 1] else 0 for label in witness_labels(source))
        for bits in query_models
    }
    expected = {
        tuple(int(model[label]) for label in witness_labels(source))
        for model in models
        if assumptions_hold(model, assumptions)
        and reference_signal(source, model, str(consequence[0])) != int(consequence[1])
    }
    if projected != expected:
        return f"compiled query projection mismatch: projected={len(projected)} expected={len(expected)}"
    return None


def make_sources() -> list[tuple[str, dict[str, Any]]]:
    return [
        ("and_asserted", {"kind": "circuit", "inputs": ("a", "b"), "gates": ({"op": "and", "out": "g", "args": ("a", "b")},), "assertions": (("g", 1),), "relations": (), "clauses": ()}),
        ("or_asserted", {"kind": "circuit", "inputs": ("a", "b"), "gates": ({"op": "or", "out": "g", "args": ("a", "b")},), "assertions": (("g", 0),), "relations": (), "clauses": ()}),
        ("not_asserted", {"kind": "circuit", "inputs": ("a",), "gates": ({"op": "not", "out": "n", "args": ("a",)},), "assertions": (("n", 1),), "relations": (), "clauses": ()}),
        ("xor_chain", {"kind": "circuit", "inputs": ("a", "b", "c"), "gates": ({"op": "xor", "out": "x", "args": ("a", "b")}, {"op": "xnor", "out": "y", "args": ("x", "c")}), "assertions": (), "relations": ({"kind": "xor", "args": ("a", "b"), "rhs": 1}, {"kind": "xor", "args": ("b", "c"), "rhs": 0}, {"kind": "xor", "args": ("a", "b", "c"), "rhs": 1}), "clauses": ((("a", 1),), (("b", 0),))}),
        ("nand_clause", {"kind": "circuit", "inputs": ("a", "b", "c"), "gates": ({"op": "nand", "out": "n", "args": ("a", "b")},), "assertions": (), "relations": ({"kind": "cardinality", "args": ("a", "b", "c"), "min": 1, "max": 2},), "clauses": ((("n", 1),), (("a", 0), ("c", 1)))}),
        ("cardinality_exact", {"kind": "circuit", "inputs": ("p", "q", "r"), "gates": (), "assertions": (), "relations": ({"kind": "cardinality", "args": ("p", "q", "r"), "min": 1, "max": 1},), "clauses": ((("p", 1), ("q", 1)),)}),
        ("cardinality_range", {"kind": "circuit", "inputs": ("p", "q", "r", "s"), "gates": ({"op": "or", "out": "o", "args": ("p", "q")},), "assertions": (), "relations": ({"kind": "cardinality", "args": ("p", "q", "r", "s"), "min": 1, "max": 3},), "clauses": ((("o", 1),), (("r", 1), ("s", 0)))}),
        ("xnor_mux", {"kind": "circuit", "inputs": ("a", "b", "sel"), "gates": ({"op": "xnor", "out": "x", "args": ("a", "b")}, {"op": "mux", "out": "m", "args": ("sel", "x", "a")}), "assertions": (("m", 1),), "relations": (), "clauses": ((("x", 1), ("b", 0)),)}),
        ("transition_copy", {"kind": "transition", "state": ("p",), "inputs": ("u",), "gates": ({"op": "buf", "out": "b", "args": ("u",)},), "next_state": (("p", "b"),), "horizon": 2, "initial": (("p", 0),), "input_assertions": ((0, "u", 1),), "final": (), "relations": (), "clauses": ()}),
        ("transition_invert", {"kind": "transition", "state": ("p",), "inputs": ("u",), "gates": ({"op": "not", "out": "n", "args": ("u",)},), "next_state": (("p", "n"),), "horizon": 2, "initial": (("p", 1),), "input_assertions": ((0, "u", 0),), "final": (), "relations": (), "clauses": ((("p", 1, 1),),)}),
        ("transition_relation", {"kind": "transition", "state": ("p", "q"), "inputs": ("u",), "gates": ({"op": "xor", "out": "x", "args": ("p", "u")},), "next_state": (("p", "x"), ("q", "p")), "horizon": 1, "initial": (("p", 0), ("q", 1)), "input_assertions": ((0, "u", 1),), "final": (), "relations": ({"kind": "cardinality", "args": ("p", "q", "u"), "min": 1, "max": 2},), "clauses": ((("x", 1, 0),),)}),
    ]


def add_failure(failures: list[str], message: str) -> None:
    failures.append(message)


def main() -> int:
    started = time.perf_counter()
    sources = make_sources()
    checks: list[dict[str, Any]] = []
    global_failures: list[str] = []
    notes: list[str] = []
    counts = {"rules": 0, "holds": 0, "refuted": 0, "vacuous": 0, "unresolved": 0, "certificates_audited": 0, "augmentation_rows_checked": 0, "refusal_cases": 0}

    # Outcome agreement and certificate checks share one independent model table.
    outcome_failures: list[str] = []
    certificate_failures: list[str] = []
    certificate_cases = 0
    rule_cases = 0
    evaluator_agreement_failures: list[str] = []
    for source_name, source in sources:
        try:
            models = enumerate_witness_models(source)
        except Exception as exc:  # pragma: no cover - source construction guard
            add_failure(outcome_failures, f"{source_name}: independent enumeration failed: {exc}")
            continue
        labels = signal_labels(source)
        witness = witness_labels(source)
        rules: list[tuple[tuple[str, int], tuple[tuple[str, int], ...]]] = []
        # Ten consequences with no assumptions and six one-assumption rules per source.
        for index, label in enumerate(labels[:5]):
            rules.append(((label, index & 1), ()))
            rules.append(((label, 1 - (index & 1)), ()))
        for index, assumption_label in enumerate(witness[:3]):
            for consequence_label in labels[:2]:
                rules.append(((consequence_label, (index + 1) & 1), ((assumption_label, index & 1),)))
        deduped: list[tuple[tuple[str, int], tuple[tuple[str, int], ...]]] = []
        seen_rules: set[tuple[Any, ...]] = set()
        for consequence, assumptions in rules:
            key = (consequence, assumptions)
            if key not in seen_rules:
                seen_rules.add(key)
                deduped.append((consequence, assumptions))
        for consequence, assumptions in deduped:
            rule_cases += 1
            counterexamples, premise_sat, _ = query_ground_truth(source, models, assumptions, consequence)
            try:
                # Public evaluator agreement is supplementary; ground truth above never calls it.
                for assignment in models:
                    if bool(implication.evaluate_source(source, assignment)) is not True:
                        add_failure(evaluator_agreement_failures, f"{source_name}: module evaluator rejected independent model {assignment}")
                        break
                    for label in (list(witness)[:1] + [consequence[0]]):
                        if implication.signal_value(source, assignment, label) != reference_signal(source, assignment, label):
                            add_failure(evaluator_agreement_failures, f"{source_name}: signal evaluator disagreed for {label}")
                            raise AssertionError("signal evaluator disagreement")
            except Exception as exc:
                add_failure(evaluator_agreement_failures, f"{source_name} {consequence}: evaluator agreement error: {exc}")
            query = implication.ImplicationQuery(source=source, consequence=consequence, assumptions=assumptions)
            try:
                result = implication.imply(query, max_transitions=20_000)
            except Exception as exc:
                add_failure(outcome_failures, f"{source_name} {query.label()}: imply raised {type(exc).__name__}: {exc}")
                continue
            outcome = str(result.get("outcome"))
            counts["rules"] += 1
            counts[outcome] = counts.get(outcome, 0) + 1
            if outcome == "unresolved":
                add_failure(outcome_failures, f"{source_name} {query.label()}: unresolved")
                continue
            if counterexamples and outcome != "refuted":
                add_failure(outcome_failures, f"{source_name} {query.label()}: counterexample exists but outcome={outcome}")
            if not counterexamples and outcome == "refuted":
                add_failure(outcome_failures, f"{source_name} {query.label()}: refuted without counterexample")
            if outcome == "refuted":
                witness_result = result.get("witness")
                if not isinstance(witness_result, Mapping) or not source_holds(source, witness_result):
                    add_failure(outcome_failures, f"{source_name} {query.label()}: invalid returned witness")
                elif not assumptions_hold(witness_result, assumptions):
                    add_failure(outcome_failures, f"{source_name} {query.label()}: witness misses assumption")
                elif reference_signal(source, witness_result, str(consequence[0])) == int(consequence[1]):
                    add_failure(outcome_failures, f"{source_name} {query.label()}: witness does not falsify consequence")
                elif int(result.get("consequence_value", -1)) != 1 - int(consequence[1]):
                    add_failure(outcome_failures, f"{source_name} {query.label()}: consequence_value mismatch")
                elif dict(witness_result) not in counterexamples:
                    add_failure(outcome_failures, f"{source_name} {query.label()}: witness not in independent counterexample set")
            if outcome == "vacuous":
                if counterexamples or not vacuity_boundary_hit(source, assumptions):
                    add_failure(outcome_failures, f"{source_name} {query.label()}: vacuity lacks an independently visible boundary clash")
            if outcome == "holds":
                certificate_cases += 1
                certificate = result.get("certificate")
                if not isinstance(certificate, Mapping):
                    add_failure(certificate_failures, f"{source_name} {query.label()}: holds has no certificate")
                else:
                    try:
                        audited = False
                        resolution = certificate.get("resolution_proof")
                        if resolution is not None:
                            backend = certificate.get("backend_clauses")
                            if backend is None:
                                raise AssertionError("resolution certificate has no backend clauses")
                            clause_audit.audit_proof(
                                backend,
                                certificate.get("learned_clauses", []),
                                resolution,
                                variables=int(certificate["variables"]),
                                status="unsat",
                                expected_conflicts=len(resolution["conflict_derivations"]),
                                max_learned_clauses=256,
                            )
                            audited = True
                        hybrid = certificate.get("hybrid_proof")
                        if hybrid is not None:
                            hybrid_audit.audit_proof(
                                certificate["source_clauses"], hybrid, variables=int(certificate["variables"])
                            )
                            audited = True
                        if not audited:
                            raise AssertionError("holds certificate contains no auditable proof")
                        counts["certificates_audited"] += 1
                        projection_failure = check_compiled_projection(result, source, models, assumptions, consequence)
                        if projection_failure:
                            add_failure(certificate_failures, f"{source_name} {query.label()}: {projection_failure}")
                    except Exception as exc:
                        add_failure(certificate_failures, f"{source_name} {query.label()}: certificate audit failed: {exc}")
                if not premise_sat and not vacuity_boundary_hit(source, assumptions):
                    notes.append(f"{source_name} {query.label()}: holds because the premise is unsatisfiable beyond a declared unit boundary")
        
    checks.append({"name": "outcome_agreement", "cases": rule_cases, "failures": outcome_failures})
    checks.append({"name": "certificate_audit", "cases": certificate_cases, "failures": certificate_failures})
    evaluator_cases = len(sources)
    checks.append({"name": "evaluator_agreement", "cases": evaluator_cases, "failures": evaluator_agreement_failures})

    # Arity-two augmentation and compiled-model entailment.
    augmentation_failures: list[str] = []
    augmentation_instances = [sources[3], sources[5], sources[8], sources[10]]
    augmentation_case_count = 0
    for source_name, source in augmentation_instances:
        augmentation_case_count += 1
        try:
            compiled = compile_circuit(source) if source["kind"] == "circuit" else compile_transition_problem(source)
            models = cnf_models(compiled.clauses, compiled.variables)
            results: dict[int, Mapping[str, Any]] = {}
            for arity in (1, 2):
                profile = ConstraintFieldProfile(
                    max_variables=compiled.variables,
                    max_clauses=len(compiled.clauses) + 128,
                    mode="algebraic",
                    max_augmentation_arity=arity,
                )
                field = ConstraintField(profile)
                state, _ = field.solve(field.initial(compiled))
                result = field.result(state)
                results[arity] = result
                rows = result["augmentations"]
                if len(result["backend_clauses"]) != len(compiled.clauses) + len(rows):
                    add_failure(augmentation_failures, f"{source_name} arity={arity}: backend clause count mismatch")
                for row in rows:
                    clause = [int(literal) for literal in row["clause"]]
                    counts["augmentation_rows_checked"] += 1
                    if len(clause) > arity or len(clause) == 0:
                        add_failure(augmentation_failures, f"{source_name} arity={arity}: row width {len(clause)}")
                    if any(abs(literal) > compiled.variables or literal == 0 for literal in clause):
                        add_failure(augmentation_failures, f"{source_name} arity={arity}: row literal outside compiled variables")
                    if not all(any((bits[abs(literal) - 1] == 1) == (literal > 0) for literal in clause) for bits in models):
                        add_failure(augmentation_failures, f"{source_name} arity={arity}: admitted row is not entailed")
            narrow = {tuple(sorted(int(value) for value in row["clause"])) for row in results[1]["augmentations"]}
            wide = {tuple(sorted(int(value) for value in row["clause"])) for row in results[2]["augmentations"]}
            if not narrow <= wide:
                add_failure(augmentation_failures, f"{source_name}: arity-two rows are not a superset")
            if source_name == "xor_chain" and not narrow < wide:
                add_failure(augmentation_failures, f"{source_name}: arity-two rows are not a strict superset")
        except Exception as exc:
            add_failure(augmentation_failures, f"{source_name}: augmentation check raised {type(exc).__name__}: {exc}")
    checks.append({"name": "augmentation_entailment", "cases": augmentation_case_count, "failures": augmentation_failures})

    # Optional transition time entries are part of the source grammar.
    grammar_failures: list[str] = []
    grammar_source = {"kind": "transition", "state": ("p",), "inputs": ("u",), "gates": (), "next_state": (("p", "u"),), "horizon": 1, "initial": (), "input_assertions": (), "final": (), "relations": ()}
    try:
        with_time = dict(grammar_source, clauses=((("p", 1, 0),),))
        without_time = dict(grammar_source, clauses=((("p", 1),),))
        first = compile_transition_problem(with_time)
        second = compile_transition_problem(without_time)
        if first.clauses != second.clauses:
            add_failure(grammar_failures, "zero-time clause with and without explicit time differs")
        timed = compile_transition_problem(dict(grammar_source, clauses=((("p", 1, 1),),)))
        identifiers = {str(name): int(identifier) for name, identifier in timed.payload["signals"]}
        expected = identifiers["s:p:1"]
        if (expected,) not in timed.clauses:
            add_failure(grammar_failures, "non-zero state time clause did not target s:p:1")
        try:
            compile_transition_problem(dict(grammar_source, clauses=((("p", 1, 2),),)))
        except ConstraintFieldError:
            pass
        else:
            add_failure(grammar_failures, "past-horizon clause was accepted")
    except Exception as exc:
        add_failure(grammar_failures, f"time grammar check raised {type(exc).__name__}: {exc}")
    checks.append({"name": "transition_clause_time_grammar", "cases": 4, "failures": grammar_failures})

    # Refusal boundaries.
    refusal_failures: list[str] = []
    refusal_cases: list[tuple[str, Any]] = []
    base_source = sources[0][1]
    refusal_cases.extend([
        ("unknown consequence", lambda: implication.imply(implication.ImplicationQuery(source=base_source, consequence=("missing", 1)))),
        ("unknown assumption", lambda: implication.imply(implication.ImplicationQuery(source=base_source, consequence=("a", 1), assumptions=(("missing", 0),)))),
        ("consequence bit 2", lambda: implication.ImplicationQuery(source=base_source, consequence=("a", 2))),
        ("consequence bit -1", lambda: implication.ImplicationQuery(source=base_source, consequence=("a", -1))),
        ("consequence bool", lambda: implication.ImplicationQuery(source=base_source, consequence=("a", True))),
        ("invalid kind", lambda: implication.imply(implication.ImplicationQuery(source={"kind": "other"}, consequence=("a", 1)))),
        ("assumption bit 2", lambda: implication.ImplicationQuery(source=base_source, consequence=("a", 1), assumptions=(("a", 2),))),
        ("assumption bit -1", lambda: implication.ImplicationQuery(source=base_source, consequence=("a", 1), assumptions=(("a", -1),))),
        ("assumption bool", lambda: implication.ImplicationQuery(source=base_source, consequence=("a", 1), assumptions=(("a", True),))),
        ("arity zero", lambda: ConstraintFieldProfile(max_variables=2, max_clauses=2, max_augmentation_arity=0)),
        ("arity three", lambda: ConstraintFieldProfile(max_variables=2, max_clauses=2, max_augmentation_arity=3)),
        ("arity bool", lambda: ConstraintFieldProfile(max_variables=2, max_clauses=2, max_augmentation_arity=True)),
        ("explicit arity three", lambda: implication.imply(
            implication.ImplicationQuery(source=base_source, consequence=("a", 1)),
            augmentation_arity=3,
        )),
        ("profile arity conflict", lambda: implication.imply(
            implication.ImplicationQuery(source=base_source, consequence=("a", 1)),
            profile=ConstraintFieldProfile(max_variables=2, max_clauses=2, max_augmentation_arity=2),
            augmentation_arity=1,
        )),
    ])
    for name, operation in refusal_cases:
        counts["refusal_cases"] += 1
        try:
            operation()
        except ConstraintFieldError:
            continue
        except (TypeError, ValueError) as exc:
            add_failure(refusal_failures, f"{name}: wrong exception type {type(exc).__name__}: {exc}")
        else:
            add_failure(refusal_failures, f"{name}: accepted invalid input")
    checks.append({"name": "refusals", "cases": len(refusal_cases), "failures": refusal_failures})

    for check in checks:
        global_failures.extend(f"{check['name']}: {failure}" for failure in check["failures"])
    verdict = "PASS" if not global_failures and counts["rules"] >= 120 and counts["certificates_audited"] >= 10 and augmentation_case_count >= 3 else "FAIL"
    if counts["rules"] < 120:
        global_failures.append(f"only {counts['rules']} implication rules were decided")
    if counts["certificates_audited"] < 10:
        global_failures.append(f"only {counts['certificates_audited']} certificates were audited")
    if augmentation_case_count < 3:
        global_failures.append("fewer than three augmentation instances were checked")
    if evaluator_agreement_failures:
        notes.append("The production evaluator was called only as a supplementary agreement check; independent enumeration decided every rule.")
    receipt = {
        "schema": "cassifi.implication-engine-verify.v1",
        "python": sys.version,
        "platform": platform.platform(),
        "checks": checks,
        "counts": counts,
        "notes": notes,
        "failures": global_failures,
        "verdict": verdict,
        "wall_clock_seconds": float(time.perf_counter() - started),
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    for check in checks:
        print(f"{check['name']}: cases={check['cases']} failures={len(check['failures'])}")
    print(f"counts: rules={counts['rules']} holds={counts['holds']} refuted={counts['refuted']} vacuous={counts['vacuous']} unresolved={counts['unresolved']} certificates_audited={counts['certificates_audited']} augmentation_rows_checked={counts['augmentation_rows_checked']} refusal_cases={counts['refusal_cases']}")
    print(f"verdict: {verdict}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
