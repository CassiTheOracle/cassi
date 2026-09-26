#!/usr/bin/env python
"""Exercise all implemented CassiFI proof-system upgrades and freeze evidence."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from cassi_hybrid_inference import HybridInferenceField, HybridInferenceProfile
from verify_hybrid_inference import (
    audit_proof,
    recognize_connected_matched_exact_one,
)
SCHEMA = "cassifi.hybrid-inference-probe.v1"
OUTPUT = Path("_diag/p_vs_np_hybrid_inference.json")

Clause = tuple[int, ...]
Formula = tuple[Clause, ...]


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    family: str
    variables: int
    formula: Formula
    expected_status: str
    required_rules: tuple[str, ...]
    max_lines: int | None = None
    max_extensions: int = 0
    max_resolution_inferences: int = 0
    max_transitions: int = 100_000
    expected_model: bool | None = None


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_formula(formula: Formula) -> Formula:
    return tuple(
        sorted(
            {
                tuple(sorted(clause, key=lambda literal: (abs(literal), literal < 0)))
                for clause in formula
            },
            key=lambda clause: (len(clause), clause),
        )
    )


def satisfies(formula: Formula, assignment: Sequence[int]) -> bool:
    return all(
        any(assignment[abs(literal) - 1] == (1 if literal > 0 else 0) for literal in clause)
        for clause in formula
    )


def has_model(formula: Formula, variables: int) -> bool:
    return any(satisfies(formula, assignment) for assignment in itertools.product((0, 1), repeat=variables))


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


def tseitin_prism(rungs: int, *, odd_charge: bool) -> Formula:
    edges = prism_edges(rungs)
    incident: list[list[int]] = [[] for _ in range(2 * rungs)]
    for edge_index, (left, right) in enumerate(edges, 1):
        incident[left].append(edge_index)
        incident[right].append(edge_index)
    charges = [0] * (2 * rungs)
    if odd_charge:
        charges[0] = 1
    return tuple(
        clause
        for vertex, variables in enumerate(incident)
        for clause in parity_clauses(variables, charges[vertex])
    )


def mixed_exact_one_even_parity() -> Formula:
    variables = (1, 2, 3)
    return parity_clauses(variables, 0) + (
        variables,
        (-1, -2),
        (-1, -3),
        (-2, -3),
    )


def extension_unsat() -> Formula:
    return ((1, 2, 3), (1, 2, -3), (-1,), (-2,))


def extension_sat() -> Formula:
    return ((1, 2, 3), (1, 2, -3), (-1,))

def connected_matched_exact_one_labeled(
    blocks: int,
    labels: Sequence[int],
) -> Formula:
    """Build the canonical connected exact-one incidence graph with edge labels."""
    if blocks < 4 or blocks % 2:
        raise ValueError("blocks must be an even integer of at least four")
    if len(labels) != 3 * blocks // 2 or any(
        label not in (0, 1) for label in labels
    ):
        raise ValueError("labels must contain one bit per matching edge")

    def variable(block: int, port: int) -> int:
        return 3 * block + port + 1

    clauses: list[Clause] = []
    for block in range(blocks):
        a, b, c = (variable(block, port) for port in range(3))
        clauses.extend(((a, b, c), (-a, -b), (-a, -c), (-b, -c)))

    matching: list[tuple[int, int]] = [
        (variable(block, 1), variable((block + 1) % blocks, 0))
        for block in range(blocks)
    ]
    matching.extend(
        (variable(block, 2), variable(block + 1, 2))
        for block in range(0, blocks, 2)
    )
    for pair, parity in zip(matching, labels):
        clauses.extend(parity_clauses(pair, parity))
    return tuple(clauses)


def connected_matched_exact_one(
    blocks: int,
    *,
    inconsistent: bool,
) -> Formula:
    """Build the one-odd-edge member used by the exact scaling theorem."""
    labels = [0] * (3 * blocks // 2)
    if inconsistent:
        labels[0] = 1
    return connected_matched_exact_one_labeled(blocks, labels)

def maximally_odd_labels(blocks: int) -> tuple[int, ...]:
    """Return the densest odd-weight label vector for an even block count."""
    count = 3 * blocks // 2
    return tuple(1 if count % 2 or index < count - 1 else 0 for index in range(count))


def cases() -> list[Case]:
    result: list[Case] = []
    for holes in (2, 3, 4, 6, 8, 10, 12):
        formula = pigeonhole(holes)
        result.append(
            Case(
                name=f"counting_php_{holes + 1}_into_{holes}",
                family="cutting-plane-pigeonhole",
                variables=holes * (holes + 1),
                formula=formula,
                expected_status="unsat",
                required_rules=("clause-pb", "pb-add", "pb-divide"),
                expected_model=False if holes <= 3 else None,
            )
        )
    for rungs in (3, 4, 5, 8, 12, 16):
        result.append(
            Case(
                name=f"parity_prism_{rungs}_odd",
                family="gf2-tseitin",
                variables=3 * rungs,
                formula=tseitin_prism(rungs, odd_charge=True),
                expected_status="unsat",
                required_rules=("parity-import", "xor-add"),
                expected_model=False if rungs <= 5 else None,
            )
        )
    for blocks in (4, 6, 8, 12, 16, 24):
        result.append(
            Case(
                name=f"mixed_connected_blocks_{blocks}_odd",
                family="connected-matched-exact-one",
                variables=3 * blocks,
                formula=connected_matched_exact_one(
                    blocks,
                    inconsistent=True,
                ),
                expected_status="unsat",
                required_rules=(
                    "pb-add",
                    "pb-divide",
                    "parity-import",
                    "cardinality-parity",
                    "xor-add",
                ),
                expected_model=False if blocks <= 6 else None,
            )
        )
    for blocks in (4, 6, 8, 12):
        result.append(
            Case(
                name=f"mixed_labeled_blocks_{blocks}_max_odd",
                family="connected-matched-exact-one-labeled",
                variables=3 * blocks,
                formula=connected_matched_exact_one_labeled(
                    blocks,
                    maximally_odd_labels(blocks),
                ),
                expected_status="unsat",
                required_rules=(
                    "pb-add",
                    "pb-divide",
                    "parity-import",
                    "cardinality-parity",
                    "xor-add",
                ),
                max_lines=40 * blocks * blocks + 32 * blocks + 256,
                expected_model=False if blocks <= 4 else None,
            )
        )
    result.extend(
        [
            Case(
                name="mixed_exact_one_even_parity",
                family="cardinality-parity-crossing",
                variables=3,
                formula=mixed_exact_one_even_parity(),
                expected_status="unsat",
                required_rules=("pb-divide", "cardinality-parity", "xor-add"),
                max_extensions=4,
                expected_model=False,
            ),
            Case(
                name="named_disjunction_unsat",
                family="extended-resolution",
                variables=3,
                formula=extension_unsat(),
                expected_status="unsat",
                required_rules=("extension-define", "extension-clause", "resolve"),
                max_extensions=2,
                max_resolution_inferences=128,
                expected_model=False,
            ),
            Case(
                name="control_even_tseitin",
                family="satisfiable-control",
                variables=12,
                formula=tseitin_prism(4, odd_charge=False),
                expected_status="exhausted",
                required_rules=("parity-import", "xor-add"),
                expected_model=True,
            ),
            Case(
                name="control_incomplete_parity",
                family="incomplete-import-control",
                variables=6,
                formula=parity_clauses((1, 2, 3), 0)[:-1] + parity_clauses((4, 5, 6), 1),
                expected_status="exhausted",
                required_rules=("parity-import",),
                expected_model=True,
            ),
            Case(
                name="control_missing_capacity_edge",
                family="incomplete-counting-control",
                variables=6,
                formula=pigeonhole(2)[:-1],
                expected_status="exhausted",
                required_rules=("clause-pb",),
                expected_model=True,
            ),
            Case(
                name="control_named_disjunction_sat",
                family="extension-satisfiable-control",
                variables=3,
                formula=extension_sat(),
                expected_status="exhausted",
                required_rules=("extension-define", "extension-clause", "resolve"),
                max_extensions=2,
                max_resolution_inferences=128,
                expected_model=True,
            ),
            Case(
                name="control_transition_exhaustion",
                family="resource-control",
                variables=6,
                formula=pigeonhole(2),
                expected_status="exhausted",
                required_rules=(),
                max_transitions=1,
                expected_model=False,
            ),
            Case(
                name="control_mixed_connected_blocks_4_even",
                family="connected-matched-exact-one-control",
                variables=12,
                formula=connected_matched_exact_one(
                    4,
                    inconsistent=False,
                ),
                expected_status="exhausted",
                required_rules=(
                    "parity-import",
                    "cardinality-parity",
                    "xor-add",
                ),
                expected_model=True,
            ),
        ]
    )
    return result


def profile_for(case: Case) -> HybridInferenceProfile:
    clauses = len(canonical_formula(case.formula))
    max_lines = (
        case.max_lines
        if case.max_lines is not None
        else max(512, 5 * clauses + 16 * case.variables + 256)
    )
    return HybridInferenceProfile(
        max_variables=case.variables,
        max_original_clauses=max(1, clauses),
        max_lines=max_lines,
        max_extensions=case.max_extensions,
        max_parity_width=8,
        max_resolution_inferences=case.max_resolution_inferences,
        max_transitions=case.max_transitions,
    )


def run_case(case: Case) -> dict[str, Any]:
    formula = canonical_formula(case.formula)
    profile = profile_for(case)
    field = HybridInferenceField(profile)
    initial = field.initial(formula, variable_count=case.variables)
    initial_bytes = initial.field.tobytes()
    final, result = field.solve(initial)
    if initial.field.tobytes() != initial_bytes:
        raise AssertionError(f"{case.name}: solve mutated its input state")
    if result["status"] != case.expected_status:
        raise AssertionError(f"{case.name}: expected {case.expected_status}, got {result['status']}")
    proof = field.proof(final)
    audit = audit_proof(formula, proof, variables=case.variables)
    rules = set(audit["rule_counts"])
    missing = set(case.required_rules) - rules
    if missing:
        raise AssertionError(f"{case.name}: missing required rules {sorted(missing)}")
    if case.expected_model is not None:
        observed_model = has_model(formula, case.variables)
        if observed_model != case.expected_model:
            raise AssertionError(f"{case.name}: exhaustive model control mismatch")

    descriptor = field.descriptor(final)
    restored_field, restored = HybridInferenceField.from_descriptor(descriptor)
    if restored_field.state_sha256(restored) != field.state_sha256(final):
        raise AssertionError(f"{case.name}: checkpoint roundtrip mismatch")
    replay_field = HybridInferenceField(profile)
    replay_final, replay_result = replay_field.solve(
        replay_field.initial(formula, variable_count=case.variables)
    )
    if replay_field.state_sha256(replay_final) != field.state_sha256(final):
        raise AssertionError(f"{case.name}: deterministic state replay mismatch")
    if replay_field.proof(replay_final)["proof_sha256"] != proof["proof_sha256"]:
        raise AssertionError(f"{case.name}: deterministic proof replay mismatch")
    if replay_result["resource_ledger"] != result["resource_ledger"]:
        raise AssertionError(f"{case.name}: deterministic ledger replay mismatch")

    expected_bytes = 72 * max(16, profile.max_lines * profile.max_total_variables)
    if final.nbytes != expected_bytes:
        raise AssertionError(f"{case.name}: field storage formula mismatch")
    return {
        "name": case.name,
        "family": case.family,
        "variables": case.variables,
        "formula": [list(clause) for clause in formula],
        "problem_sha256": hashlib.sha256(canonical(formula)).hexdigest(),
        "expected_status": case.expected_status,
        "status": result["status"],
        "expected_model": case.expected_model,
        "required_rules": list(case.required_rules),
        "profile": profile.as_dict(),
        "field_bytes": final.nbytes,
        "initial_state_sha256": field.state_sha256(initial),
        "state_sha256": field.state_sha256(final),
        "checkpoint_roundtrip_exact": True,
        "deterministic_replay_exact": True,
        "proof": proof,
        "audit": audit,
        "resource_ledger": result["resource_ledger"],
    }


def representation_controls() -> dict[str, Any]:
    # The redundant asymmetric clause makes variable renaming a genuine
    # representation change rather than an automorphism of the base formula.
    base = mixed_exact_one_even_parity() + ((1, 2),)
    permutation = {1: 3, 2: 1, 3: 2}
    permuted = tuple(
        tuple(
            (1 if literal > 0 else -1) * permutation[abs(literal)]
            for literal in reversed(clause)
        )
        for clause in reversed(base)
    )
    rows = []
    for name, formula in (("base", base), ("reordered", tuple(reversed(base))), ("renamed", permuted)):
        case = Case(
            name=name,
            family="representation-control",
            variables=3,
            formula=formula,
            expected_status="unsat",
            required_rules=("cardinality-parity", "xor-add"),
            max_extensions=4,
        )
        row = run_case(case)
        rows.append(
            {
                "name": name,
                "problem_sha256": row["problem_sha256"],
                "status": row["status"],
                "proof_lines": row["audit"]["proof_lines"],
                "state_sha256": row["state_sha256"],
                "proof_sha256": row["proof"]["proof_sha256"],
            }
        )
    if rows[0]["state_sha256"] != rows[1]["state_sha256"]:
        raise AssertionError("clause/literal reorder changed the canonical field")
    if rows[0]["proof_sha256"] != rows[1]["proof_sha256"]:
        raise AssertionError("clause/literal reorder changed the canonical proof")
    if len({row["status"] for row in rows}) != 1:
        raise AssertionError("variable renaming changed the mixed proof status")
    if rows[0]["problem_sha256"] == rows[2]["problem_sha256"]:
        raise AssertionError("renaming control did not change the asymmetric formula")
    return {
        "variants": rows,
        "reorder_state_identical": True,
        "reorder_proof_identical": True,
        "renaming_status_invariant": True,
        "renaming_problem_digest_changed": True,
    }


def scaling(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for family in (
        "cutting-plane-pigeonhole",
        "gf2-tseitin",
        "connected-matched-exact-one",
        "connected-matched-exact-one-labeled",
    ):
        points = [row for row in rows if row["family"] == family]
        result[family] = [
            {
                "variables": row["variables"],
                "input_clauses": len(row["formula"]),
                "proof_lines": row["audit"]["proof_lines"],
                "derived_lines": row["audit"]["derived_lines"],
                "transitions": row["resource_ledger"]["transitions"],
                "field_bytes": row["field_bytes"],
                "maximum_integer_magnitude": row["audit"]["maximum_integer_magnitude"],
            }
            for row in points
        ]
    return result

def restricted_class_evidence(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    measured: list[dict[str, Any]] = []
    for row in rows:
        if row["family"] != "connected-matched-exact-one":
            continue
        recognized = recognize_connected_matched_exact_one(
            row["formula"],
            row["variables"],
        )
        blocks = recognized["blocks"]
        expected_rules = {
            "input": 7 * blocks,
            "clause-pb": 7 * blocks,
            "parity-import": 3 * blocks // 2,
            "pb-add": 4 * blocks - 1,
            "pb-divide": blocks,
            "cardinality-parity": 2 * blocks + 1,
            "xor-add": 5 * blocks // 2,
        }
        if not recognized["contradiction"]:
            raise AssertionError(f"{row['name']}: mixed class is not contradictory")
        if row["audit"]["rule_counts"] != expected_rules:
            raise AssertionError(f"{row['name']}: mixed proof rule formula mismatch")
        if (
            row["audit"]["proof_lines"] != 25 * blocks
            or row["audit"]["derived_lines"] != 18 * blocks
            or row["resource_ledger"]["transitions"] != 18 * blocks
            or row["audit"]["maximum_integer_magnitude"] != blocks
        ):
            raise AssertionError(f"{row['name']}: mixed proof bound mismatch")
        measured.append(
            {
                "blocks": blocks,
                "variables": row["variables"],
                "input_clauses": len(row["formula"]),
                "proof_lines": row["audit"]["proof_lines"],
                "derived_lines": row["audit"]["derived_lines"],
                "transitions": row["resource_ledger"]["transitions"],
                "maximum_integer_magnitude": row["audit"][
                    "maximum_integer_magnitude"
                ],
                "field_bytes": row["field_bytes"],
                "problem_sha256": row["problem_sha256"],
                "proof_sha256": row["proof"]["proof_sha256"],
            }
        )
    measured_labeled: list[dict[str, Any]] = []
    for row in rows:
        if row["family"] != "connected-matched-exact-one-labeled":
            continue
        recognized = recognize_connected_matched_exact_one(
            row["formula"],
            row["variables"],
        )
        blocks = recognized["blocks"]
        line_limit = 40 * blocks * blocks + 32 * blocks + 256
        if (
            not recognized["contradiction"]
            or row["status"] != "unsat"
            or row["audit"]["proof_lines"] > line_limit
            or row["audit"]["maximum_integer_magnitude"] > 3 * blocks
            or row["profile"]["max_lines"] != line_limit
            or row["resource_ledger"]["extension_definitions"] != 0
            or row["resource_ledger"]["resolution_lines"] != 0
        ):
            raise AssertionError(f"{row['name']}: labeled mixed bound mismatch")
        measured_labeled.append(
            {
                "blocks": blocks,
                "odd_labels": sum(
                    edge["rhs"] for edge in recognized["matching"]
                ),
                "proof_lines": row["audit"]["proof_lines"],
                "derived_lines": row["audit"]["derived_lines"],
                "transitions": row["resource_ledger"]["transitions"],
                "maximum_integer_magnitude": row["audit"][
                    "maximum_integer_magnitude"
                ],
                "field_bytes": row["field_bytes"],
                "problem_sha256": row["problem_sha256"],
                "proof_sha256": row["proof"]["proof_sha256"],
            }
        )
    control = next(
        row
        for row in rows
        if row["name"] == "control_mixed_connected_blocks_4_even"
    )
    control_recognition = recognize_connected_matched_exact_one(
        control["formula"],
        control["variables"],
    )
    if control_recognition["contradiction"] or control["status"] != "exhausted":
        raise AssertionError("consistent mixed-class control failed")
    return {
        "schema": "cassifi.connected-matched-exact-one.v2",
        "syntax": {
            "block": "a positive three-literal clause plus all three negative pairs",
            "coupling": "complete binary parity CNFs form a cross-block perfect matching",
            "globality": "the quotient graph on exact-one blocks is connected",
            "contradiction": "block-count parity XOR matching-label parity equals one",
        },
        "semantic_identity": (
            "XORing every exact-one parity and matching equation cancels "
            "every variable exactly twice"
        ),
        "canonical_subfamily_bounds": {
            "blocks": "even b >= 4",
            "variables": "3b",
            "input_clauses": "7b",
            "derived_proof_lines": "18b",
            "total_proof_lines": "25b",
            "maximum_integer_magnitude": "b",
            "profile_max_lines": "83b + 256",
            "field_bytes": "17928b^2 + 55296b",
            "bulk_controller_work": "O(b^3) conservative loop bound",
            "stepwise_controller_work": "O(b^4) conservative loop bound",
            "temporary_space": "O(b^2)",
        },
        "labeled_subfamily_bounds": {
            "labels": "arbitrary with XOR_e ell_e = 1",
            "proof_lines": "<= 40b^2 + 32b + 256",
            "maximum_integer_magnitude": "<= 3b",
            "profile_max_lines": "40b^2 + 32b + 256",
            "field_bytes": "216b(40b^2 + 32b + 256)",
            "bulk_controller_work": "O(b^3) conservative loop bound",
            "stepwise_controller_work": "O(b^5) conservative loop bound",
            "temporary_space": "O(b^3)",
        },
        "measured": measured,
        "measured_labeled": measured_labeled,
        "consistent_control": {
            "blocks": control_recognition["blocks"],
            "global_rhs": control_recognition["global_rhs"],
            "truth_table_model_exists": control["expected_model"],
            "status": control["status"],
            "root_line": control["proof"]["root_line"],
        },
    }


def run(output: Path = OUTPUT) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    corpus = cases()
    for index, case in enumerate(corpus, 1):
        row = run_case(case)
        rows.append(row)
        print(
            f"{index:02d}/{len(corpus)} {case.name}: {row['status']} "
            f"lines={row['audit']['proof_lines']} "
            f"rules={','.join(row['audit']['rule_counts'])}"
        )
    representation = representation_controls()
    summary = {
        "cases": len(rows),
        "unsat": sum(row["status"] == "unsat" for row in rows),
        "exhausted_controls": sum(row["status"] == "exhausted" for row in rows),
        "all_proofs_independently_verified": True,
        "total_proof_lines": sum(row["audit"]["proof_lines"] for row in rows),
        "maximum_integer_magnitude": max(row["audit"]["maximum_integer_magnitude"] for row in rows),
    }
    receipt = {
        "schema": SCHEMA,
        "field_contract": {
            "tensor_shape": "[1, 9*M, 1] float64 exact integers",
            "state_ownership": "source CNF, clauses, inequalities, parity equations, extension definitions, premise pointers, rules, status, and counters are field coordinates",
            "persistent_adaptive_side_tables": 0,
            "family_labels_used_by_controller": 0,
            "host_proof_hints": 0,
            "model_calls": 0,
            "arithmetic": "all stored integers have magnitude at most 2^53-1; overflow and capacity limits exhaust without UNSAT",
            "transition": "one checked proof line per step; solve fast-forwards the same deterministic line sequence",
        },
        "summary": summary,
        "representation": representation,
        "scaling": scaling(rows),
        "restricted_class": restricted_class_evidence(rows),
        "cases": rows,
        "assessment": {
            "resolution_obstruction": "bypassed on the tested standard pigeonhole formulas by cutting-plane addition and integer rounding",
            "parity": "complete local parity blocks are recovered from CNF and cancelled by GF(2) elimination",
            "mixed_inference": "exact cardinality derived by cutting planes is bridged into parity and used in the final contradiction",
            "named_concepts": "fresh disjunction variables and their defining clauses participate in checked resolution refutations",
            "universal_polynomial_proof_search": "not established",
            "p_equals_np": "not established",
            "next_target": "extend the proved connected matched exact-one class or establish automatizability bounds for a broader syntactic class",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    print(f"Wrote {output}")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
