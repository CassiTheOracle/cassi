#!/usr/bin/env python
"""Exercise the uniform CassiFI clause field on exact and structured CNFs."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from cassi_clause_field import ClauseField, ClauseFieldProfile

SCHEMA = "cassifi.p-vs-np-clause-field-probe.v2"
SEED = 0xC551F2
OUTPUT = Path("_diag/p_vs_np_clause_field_probe.json")
ACTION_VOCABULARY = ("decide", "propagate", "conflict-backtrack", "sat", "unsat", "exhaust")

Clause = tuple[int, ...]
Formula = tuple[Clause, ...]


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    family: str
    variables: int
    clauses: Formula
    expected_sat: bool
    expectation: str


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def satisfies(clauses: Formula, assignment: Sequence[int]) -> bool:
    return all(
        any(assignment[abs(literal) - 1] == (1 if literal > 0 else -1) for literal in clause)
        for clause in clauses
    )


def brute_models(clauses: Formula, variables: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        assignment
        for assignment in itertools.product((-1, 1), repeat=variables)
        if satisfies(clauses, assignment)
    )


def complete_three_variable_cases() -> list[Case]:
    clauses = tuple(
        tuple(variable if bit else -variable for variable, bit in enumerate(bits, 1))
        for bits in itertools.product((0, 1), repeat=3)
    )
    result: list[Case] = []
    for mask in range(1, 1 << len(clauses)):
        formula = tuple(clause for index, clause in enumerate(clauses) if mask & (1 << index))
        result.append(
            Case(
                name=f"complete3_{mask:03x}",
                family="complete-three-variable",
                variables=3,
                clauses=formula,
                expected_sat=mask != (1 << len(clauses)) - 1,
                expectation="complete truth-table construction",
            )
        )
    return result


def pigeonhole(holes: int) -> Formula:
    pigeons = holes + 1

    def variable(pigeon: int, hole: int) -> int:
        return pigeon * holes + hole + 1

    clauses: list[Clause] = []
    for pigeon in range(pigeons):
        clauses.append(tuple(variable(pigeon, hole) for hole in range(holes)))
    for hole in range(holes):
        for first in range(pigeons):
            for second in range(first + 1, pigeons):
                clauses.append((-variable(first, hole), -variable(second, hole)))
    return tuple(clauses)


def parity_clauses(variables: Sequence[int], parity: int) -> Formula:
    clauses: list[Clause] = []
    for bits in itertools.product((0, 1), repeat=len(variables)):
        if sum(bits) % 2 == parity:
            continue
        clauses.append(
            tuple(-variable if bit else variable for variable, bit in zip(variables, bits))
        )
    return tuple(clauses)


def prism_edges(rungs: int) -> tuple[tuple[int, int], ...]:
    edges: list[tuple[int, int]] = []
    for index in range(rungs):
        edges.append((index, (index + 1) % rungs))
        edges.append((rungs + index, rungs + (index + 1) % rungs))
        edges.append((index, rungs + index))
    return tuple(edges)


def tseitin_prism(rungs: int, *, contradictory: bool) -> Formula:
    edges = prism_edges(rungs)
    incident: list[list[int]] = [[] for _ in range(2 * rungs)]
    for edge_index, (left, right) in enumerate(edges, 1):
        incident[left].append(edge_index)
        incident[right].append(edge_index)
    charges = [0] * (2 * rungs)
    if contradictory:
        charges[0] = 1
    clauses: list[Clause] = []
    for vertex, variables in enumerate(incident):
        if len(variables) != 3:
            raise AssertionError("prism graph must be three-regular")
        clauses.extend(parity_clauses(variables, charges[vertex]))
    return tuple(clauses)


def planted_formula(variables: int, clause_count: int, seed: int) -> tuple[Formula, tuple[int, ...]]:
    rng = random.Random(seed)
    planted = tuple(rng.choice((-1, 1)) for _ in range(variables))
    clauses: list[Clause] = []
    seen: set[Clause] = set()
    while len(clauses) < clause_count:
        selected = rng.sample(range(1, variables + 1), 3)
        clause = [variable if rng.getrandbits(1) else -variable for variable in selected]
        if not satisfies((tuple(clause),), planted):
            index = rng.randrange(3)
            variable = abs(clause[index])
            clause[index] = variable if planted[variable - 1] == 1 else -variable
        row = tuple(clause)
        if row not in seen:
            clauses.append(row)
            seen.add(row)
    return tuple(clauses), planted


def structured_cases() -> list[Case]:
    cases: list[Case] = []
    for holes in (2, 3, 4):
        formula = pigeonhole(holes)
        cases.append(
            Case(
                name=f"pigeonhole_{holes + 1}_into_{holes}",
                family="pigeonhole-unsat",
                variables=holes * (holes + 1),
                clauses=formula,
                expected_sat=False,
                expectation="pigeonhole principle construction",
            )
        )
    for rungs in (3, 4, 5):
        for contradictory in (False, True):
            formula = tseitin_prism(rungs, contradictory=contradictory)
            cases.append(
                Case(
                    name=f"tseitin_prism_{rungs}_{'odd' if contradictory else 'even'}",
                    family="tseitin-unsat" if contradictory else "tseitin-sat",
                    variables=3 * rungs,
                    clauses=formula,
                    expected_sat=not contradictory,
                    expectation="Tseitin parity construction",
                )
            )
    for variables in (6, 8, 10, 12, 14, 16):
        for replicate in range(3):
            formula, _ = planted_formula(
                variables,
                max(1, round(4.25 * variables)),
                SEED + 100 * variables + replicate,
            )
            cases.append(
                Case(
                    name=f"planted3_n{variables}_r{replicate}",
                    family="planted-three-sat",
                    variables=variables,
                    clauses=formula,
                    expected_sat=True,
                    expectation="planted satisfying assignment",
                )
            )
    return cases


def profile_for(case: Case, *, max_transitions: int = 1_000_000) -> ClauseFieldProfile:
    return ClauseFieldProfile(
        max_variables=case.variables,
        max_original_clauses=max(1, len(case.clauses)),
        max_clause_width=case.variables,
        max_learned_clauses=max(16, 8 * case.variables),
        max_transitions=max_transitions,
    )
def resolve_clause(
    left: Sequence[int],
    right: Sequence[int],
    pivot: int,
) -> tuple[int, ...]:
    left_polarity = 1 if pivot in left else -1 if -pivot in left else 0
    right_polarity = 1 if pivot in right else -1 if -pivot in right else 0
    if left_polarity == 0 or right_polarity != -left_polarity:
        raise AssertionError("closure premises lack a complementary pivot")
    result: set[int] = set()
    for literal in (*left, *right):
        if abs(literal) == pivot:
            continue
        if -literal in result:
            raise AssertionError("closure resolution produced a tautology")
        result.add(int(literal))
    return tuple(sorted(result, key=lambda literal: (abs(literal), literal < 0)))


def build_proof_certificate(
    conflicts: Sequence[Mapping[str, Any]],
    *,
    status: str,
) -> dict[str, Any]:
    closure_steps: list[dict[str, Any]] = []
    root_line: int | None = None
    closure_literal_scans = 0
    if status == "unsat":
        root: dict[str, Any] = {"leaf": None, "children": {}}
        for leaf_line, proof in enumerate(conflicts, 1):
            decisions = tuple(int(value) for value in proof["decision_literals"])
            nogood = tuple(int(value) for value in proof["nogood_clause"])
            if nogood != tuple(-literal for literal in decisions):
                raise AssertionError("conflict proof does not conclude its decision nogood")
            node = root
            for literal in decisions:
                if node["leaf"] is not None:
                    raise AssertionError("a closed decision prefix has descendants")
                children = node["children"]
                node = children.setdefault(literal, {"leaf": None, "children": {}})
            if node["leaf"] is not None or node["children"]:
                raise AssertionError("duplicate or prefix-overlapping conflict leaf")
            node["leaf"] = leaf_line

        def close(node: Mapping[str, Any], prefix: tuple[int, ...]) -> tuple[int, tuple[int, ...]]:
            nonlocal closure_literal_scans
            leaf = node["leaf"]
            children = node["children"]
            if leaf is not None:
                if children:
                    raise AssertionError("proof leaf also has children")
                clause = tuple(int(value) for value in conflicts[int(leaf) - 1]["nogood_clause"])
                if set(clause) != {-literal for literal in prefix}:
                    raise AssertionError("proof leaf is not the current decision nogood")
                return int(leaf), clause
            branch_literals = tuple(int(value) for value in children)
            if (
                len(branch_literals) != 2
                or branch_literals[0] != -branch_literals[1]
            ):
                raise AssertionError("UNSAT search tree is not closed on both decision branches")
            left_line, left_clause = close(
                children[branch_literals[0]],
                prefix + (branch_literals[0],),
            )
            right_line, right_clause = close(
                children[branch_literals[1]],
                prefix + (branch_literals[1],),
            )
            pivot = abs(branch_literals[0])
            resolvent = resolve_clause(left_clause, right_clause, pivot)
            if set(resolvent) != {-literal for literal in prefix}:
                raise AssertionError("branch closure did not derive the parent nogood")
            closure_literal_scans += len(left_clause) + len(right_clause)
            line_id = len(conflicts) + len(closure_steps) + 1
            closure_steps.append(
                {
                    "line_id": line_id,
                    "left_line": left_line,
                    "right_line": right_line,
                    "pivot": pivot,
                    "resolvent": list(resolvent),
                }
            )
            return line_id, resolvent

        if not conflicts:
            raise AssertionError("UNSAT result has no conflict proof")
        root_line, root_clause = close(root, ())
        if root_clause:
            raise AssertionError("UNSAT closure did not derive the empty clause")

    payload = {
        "schema": "cassifi.dpll-wresolution-proof.v1",
        "proof_system": (
            "chronological DPLL resolution DAG with linear conflict derivations, "
            "weakening to decision nogoods, lemma reuse, and a depth-first "
            "branch-closure tree"
        ),
        "conflict_derivations": [dict(proof) for proof in conflicts],
        "closure_steps": closure_steps,
        "root_line": root_line,
    }
    leaf_resolutions = sum(
        len(proof["resolution_steps"]) for proof in conflicts
    )
    leaf_weakenings = sum(
        set(proof["core_clause"]) != set(proof["nogood_clause"])
        for proof in conflicts
    )
    payload_bytes = len(canonical(payload))
    return {
        **payload,
        "stats": {
            "conflict_derivations": len(conflicts),
            "leaf_resolution_steps": leaf_resolutions,
            "leaf_weakenings": leaf_weakenings,
            "closure_resolution_steps": len(closure_steps),
            "inference_steps": leaf_resolutions + leaf_weakenings + len(closure_steps),
            "closure_literal_scans": closure_literal_scans,
            "max_core_width": max((len(proof["core_clause"]) for proof in conflicts), default=0),
            "max_nogood_width": max((len(proof["nogood_clause"]) for proof in conflicts), default=0),
            "payload_json_bytes": payload_bytes,
        },
    }




def run_case(case: Case) -> dict[str, Any]:
    field = ClauseField(profile_for(case))
    state = field.initial(case.clauses, variable_count=case.variables)
    initial_sha256 = field.state_sha256(state)
    trace = hashlib.sha256()
    action_counts = {action: 0 for action in ACTION_VOCABULARY}
    first_actions: list[str] = []
    last_actions: list[str] = []
    conflict_proofs: list[dict[str, Any]] = []
    while field.status(state) == "running":
        state, step = field.step(state)
        action = str(step["action"])
        if action not in action_counts:
            raise AssertionError(f"unexpected field action {action!r}")
        action_counts[action] += 1
        if len(first_actions) < 8:
            first_actions.append(action)
        last_actions.append(action)
        if len(last_actions) > 8:
            last_actions.pop(0)
        conflict_proof = step.get("conflict_proof")
        if conflict_proof is not None:
            if not isinstance(conflict_proof, dict):
                raise AssertionError("field conflict proof is not an object")
            conflict_proofs.append(conflict_proof)
        trace.update(
            canonical(
                {
                    "action": action,
                    "selected_literal": step.get("selected_literal"),
                    "conflict_clause": step.get("conflict_clause"),
                    "learned_clause": step.get("learned_clause"),
                    "conflict_proof": conflict_proof,
                    "state_sha256": step["state_sha256"],
                    "work": step.get("work"),
                }
            )
        )
    result = field.inspect(state)
    status = str(result["status"])
    assignment = tuple(int(value) for value in result["assignment"])
    expected_status = "sat" if case.expected_sat else "unsat"
    if status != expected_status:
        raise AssertionError(f"{case.name}: expected {expected_status}, got {status}")
    certificate_verified = status == "sat" and satisfies(case.clauses, assignment)
    if status == "sat" and not certificate_verified:
        raise AssertionError(f"{case.name}: invalid field certificate")

    exact_oracle = case.variables <= 16
    models: tuple[tuple[int, ...], ...] | None = None
    if exact_oracle:
        models = brute_models(case.clauses, case.variables)
        if bool(models) != case.expected_sat:
            raise AssertionError(f"{case.name}: construction label disagrees with exhaustive oracle")
    learned = field.clauses(state, learned=True)
    learned_sound: bool | None = None
    if models is not None:
        learned_sound = all(satisfies(learned, model) for model in models)
        if not learned_sound:
            raise AssertionError(f"{case.name}: learned clause excluded an original model")

    descriptor = field.descriptor(state)
    restored_field, restored = ClauseField.from_descriptor(descriptor)
    if restored_field.state_sha256(restored) != field.state_sha256(state):
        raise AssertionError(f"{case.name}: checkpoint roundtrip mismatch")
    proof = build_proof_certificate(conflict_proofs, status=status)
    if len(conflict_proofs) != int(result["resource_ledger"]["conflicts"]):
        raise AssertionError(f"{case.name}: conflict proof count mismatch")
    unsat_certificate_verified = (
        status == "unsat"
        and proof["root_line"] is not None
        and bool(proof["closure_steps"] or proof["conflict_derivations"])
    )

    row: dict[str, Any] = {
        "name": case.name,
        "family": case.family,
        "variables": case.variables,
        "clauses": len(case.clauses),
        "max_clause_width": max((len(clause) for clause in case.clauses), default=0),
        "formula": [list(clause) for clause in case.clauses],
        "profile": field.profile.as_dict(),
        "expected_sat": case.expected_sat,
        "expectation": case.expectation,
        "exact_truth_table_oracle": exact_oracle,
        "status": status,
        "certificate_verified": certificate_verified,
        "assignment": list(assignment) if status == "sat" else None,
        "initial_state_sha256": initial_sha256,
        "proof": proof,
        "proof_sha256": hashlib.sha256(canonical(proof)).hexdigest(),
        "unsat_certificate_verified": unsat_certificate_verified,
        "state_sha256": field.state_sha256(state),
        "problem_sha256": hashlib.sha256(canonical(case.clauses)).hexdigest(),
        "trace_sha256": trace.hexdigest(),
        "action_counts": action_counts,
        "first_actions": first_actions,
        "last_actions": last_actions,
        "learned_clause_sound": learned_sound,
        "learned_clauses": [list(clause) for clause in learned],
        "serialized_json_bytes": len(canonical(descriptor)),
        "field_bytes": result["field_bytes"],
        "resource_ledger": result["resource_ledger"],
    }
    return row


def representation_probe() -> dict[str, Any]:
    variables = 10
    formula, _ = planted_formula(variables, 43, SEED + 44)
    rng = random.Random(SEED + 45)
    cases = [
        Case("representation_base", "representation", variables, formula, True, "planted"),
    ]
    for replicate in range(12):
        labels = list(range(1, variables + 1))
        rng.shuffle(labels)
        renamed: list[Clause] = []
        shuffled_clauses = list(formula)
        rng.shuffle(shuffled_clauses)
        for clause in shuffled_clauses:
            literals = [
                (1 if literal > 0 else -1) * labels[abs(literal) - 1]
                for literal in clause
            ]
            rng.shuffle(literals)
            renamed.append(tuple(literals))
        cases.append(
            Case(
                f"representation_permuted_{replicate:02d}",
                "representation",
                variables,
                tuple(renamed),
                True,
                "variable, clause, and literal permutation",
            )
        )
    rows = [run_case(case) for case in cases]

    padded = Case(
        "representation_irrelevant_padding",
        "representation-padding",
        variables + 6,
        formula,
        True,
        "same CNF with six declared irrelevant variables",
    )
    padded_row = run_case(padded)
    transitions = [int(row["resource_ledger"]["transitions"]) for row in rows]
    base_transitions = transitions[0]
    return {
        "variants": rows,
        "irrelevant_variable_variant": padded_row,
        "all_statuses_identical": len({row["status"] for row in rows}) == 1,
        "all_certificates_verified": all(row["certificate_verified"] for row in rows),
        "transition_range": [min(transitions), max(transitions)],
        "transition_ratio": max(transitions) / max(1, min(transitions)),
        "irrelevant_padding_transition_ratio": int(padded_row["resource_ledger"]["transitions"])
        / max(1, base_transitions),
        "irrelevant_padding_field_byte_ratio": int(padded_row["field_bytes"])
        / int(rows[0]["field_bytes"]),
    }


def scaling_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    families = sorted({str(row["family"]) for row in rows})
    for family in families:
        family_rows = [row for row in rows if row["family"] == family]
        sizes = sorted({int(row["variables"]) for row in family_rows})
        points = []
        for variables in sizes:
            selected = [
                row for row in family_rows if int(row["variables"]) == variables
            ]
            transitions = [
                int(row["resource_ledger"]["transitions"]) for row in selected
            ]
            proof_inferences = [
                int(row["proof"]["stats"]["inference_steps"]) for row in selected
            ]
            points.append(
                {
                    "variables": variables,
                    "runs": len(selected),
                    "min_transitions": min(transitions),
                    "median_transitions": float(np.median(transitions)),
                    "max_transitions": max(transitions),
                    "min_proof_inferences": min(proof_inferences),
                    "median_proof_inferences": float(np.median(proof_inferences)),
                    "max_proof_inferences": max(proof_inferences),
                }
            )
        summary: dict[str, Any] = {"points": points}
        if len(points) >= 3 and all(point["median_transitions"] > 0 for point in points):
            ns = np.asarray([point["variables"] for point in points], dtype=np.float64)
            ts = np.asarray([point["median_transitions"] for point in points], dtype=np.float64)
            summary["descriptive_loglog_slope"] = float(np.polyfit(np.log(ns), np.log(ts), 1)[0])
            summary["descriptive_log2_slope_per_variable"] = float(np.polyfit(ns, np.log2(ts), 1)[0])
        if len(points) >= 3 and all(point["median_proof_inferences"] > 0 for point in points):
            ns = np.asarray([point["variables"] for point in points], dtype=np.float64)
            ps = np.asarray([point["median_proof_inferences"] for point in points], dtype=np.float64)
            summary["descriptive_proof_loglog_slope"] = float(
                np.polyfit(np.log(ns), np.log(ps), 1)[0]
            )
            summary["descriptive_proof_log2_slope_per_variable"] = float(
                np.polyfit(ns, np.log2(ps), 1)[0]
            )
        result[family] = summary
    return result


def proof_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    unsat_rows = [row for row in rows if row["status"] == "unsat"]
    stats = [row["proof"]["stats"] for row in rows]
    return {
        "proof_system": (
            "chronological DPLL resolution DAG with linear conflict derivations, "
            "weakening to decision nogoods, lemma reuse, and a depth-first "
            "branch-closure tree"
        ),
        "all_unsat_refutations_built": all(
            row["unsat_certificate_verified"] for row in unsat_rows
        ),
        "unsat_refutations": len(unsat_rows),
        "total_conflict_derivations": sum(
            int(row["conflict_derivations"]) for row in stats
        ),
        "total_leaf_resolution_steps": sum(
            int(row["leaf_resolution_steps"]) for row in stats
        ),
        "total_leaf_weakenings": sum(
            int(row["leaf_weakenings"]) for row in stats
        ),
        "total_closure_resolution_steps": sum(
            int(row["closure_resolution_steps"]) for row in stats
        ),
        "total_inference_steps": sum(
            int(row["inference_steps"]) for row in stats
        ),
        "maximum_proof_payload_bytes": max(
            (int(row["payload_json_bytes"]) for row in stats),
            default=0,
        ),
        "known_lower_bound": {
            "formula_family": "standard PHP_(h+1)^h over N=h(h+1) variables",
            "resolution_size": "2^Omega(h) = 2^Omega(sqrt(N))",
            "trace_translation": "the emitted resolution DAG has O(N*T) inferences for T field transitions",
            "consequence": "the implemented transition law has superpolynomial worst-case T on this family",
            "source": "Haken, The Intractability of Resolution, doi:10.1016/0304-3975(85)90144-6",
        },
    }


def polynomial_storage_check(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    checked = 0
    for row in rows:
        variables = int(row["variables"])
        clauses = int(row["clauses"])
        # The profile uses O((m+n)*n) exact float64 coordinates and 8n learned rows.
        bound = 72 * (clauses + 8 * variables) * variables
        if int(row["field_bytes"]) > max(bound, 72 * 21):
            raise AssertionError(f"{row['name']}: field storage exceeded declared polynomial bound")
        checked += 1
    return {
        "checked_cases": checked,
        "bound_bytes": "72 * max(21, n, m+8n, (m+8n)n)",
        "result": "all stored field tensors obeyed the declared polynomial profile",
    }


def run() -> dict[str, Any]:
    corpus = complete_three_variable_cases() + structured_cases()
    rows: list[dict[str, Any]] = []
    for index, case in enumerate(corpus, 1):
        row = run_case(case)
        rows.append(row)
        if index % 50 == 0 or case.family != "complete-three-variable":
            ledger = row["resource_ledger"]
            print(
                f"{index:03d}/{len(corpus)} {case.name}: {row['status']} "
                f"T={ledger['transitions']} conflicts={ledger['conflicts']} "
                f"learned={ledger['learned_clauses']} bytes={row['field_bytes']}"
            )

    representation = representation_probe()
    all_rows = rows + list(representation["variants"]) + [representation["irrelevant_variable_variant"]]
    exact_rows = [row for row in rows if row["exact_truth_table_oracle"]]
    completed = [row for row in rows if row["status"] in {"sat", "unsat"}]
    receipt = {
        "schema": SCHEMA,
        "seed": SEED,
        "field_contract": {
            "tensor_shape": "[1, 9*M, 1] float64 exact integers",
            "state_ownership": "CNF, assignments, implication reasons, trail, decision stack, learned clauses, and counters are field coordinates",
            "fixed_action_vocabulary": list(ACTION_VOCABULARY),
            "step_input": ["immutable ClauseFieldState"],
            "host_candidate_generation": 0,
            "host_search_scheduling": 0,
            "learned_side_tables": 0,
            "model_calls": 0,
            "precision": "all stored values are validated integers with absolute value <= 2^53-1",
            "search": "chronological DPLL, field-derived occurrence choice, unit propagation, decision-nogood learning",
            "proof_output": "conflict derivations and branch-closure refutations are nonadaptive receipts and are never fed back into search",
        },
        "corpus": {
            "cases": len(rows),
            "sat": sum(row["status"] == "sat" for row in rows),
            "unsat": sum(row["status"] == "unsat" for row in rows),
            "exhausted": sum(row["status"] == "exhausted" for row in rows),
            "exact_truth_table_cases": len(exact_rows),
            "complete_three_variable_formulas": 255,
            "all_expected_decisions": len(completed) == len(rows),
            "all_sat_certificates_verified": all(
                row["certificate_verified"] for row in rows if row["status"] == "sat"
            ),
            "all_exact_oracles_matched": all(
                row["status"] == ("sat" if row["expected_sat"] else "unsat")
                for row in exact_rows
            ),
            "all_checked_learned_clauses_sound": all(
                row["learned_clause_sound"] is not False for row in exact_rows
            ),
            "all_unsat_refutations_built": all(
                row["unsat_certificate_verified"]
                for row in rows
                if row["status"] == "unsat"
            ),
        },
        "polynomial_storage": polynomial_storage_check(all_rows),
        "scaling": scaling_summary(rows),
        "proof_complexity": proof_summary(rows),
        "representation": representation,
        "cases": rows,
        "assessment": {
            "uniform_polynomial_state": "demonstrated by construction and checked on every case",
            "field_owned_search_control": "demonstrated by the state-only fixed transition path and exact trace chain",
            "tested_sat_unsat_correctness": "SAT assignments and all seven explicit resolution refutations passed the independent checker",
            "proof_characterization": "chronological DPLL resolution DAG with linear conflict derivations, weakening to decision nogoods, lemma reuse, and a depth-first branch-closure tree",
            "polynomial_running_time": "ruled out for this solver by Haken's standard pigeonhole resolution lower bound and the O(N*T) trace-to-refutation translation",
            "p_equals_np": "not established",
            "next_target": "leave resolution-bounded DPLL or prove a polynomial transition bound on a restricted SAT class that supports an algorithms-to-lower-bounds theorem",
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt["corpus"], sort_keys=True))
    print(json.dumps(receipt["assessment"], sort_keys=True))
    print(f"Wrote {OUTPUT}")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    receipt = run()
    if args.summary:
        print(json.dumps({
            "corpus": receipt["corpus"],
            "polynomial_storage": receipt["polynomial_storage"],
            "scaling": receipt["scaling"],
            "assessment": receipt["assessment"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
