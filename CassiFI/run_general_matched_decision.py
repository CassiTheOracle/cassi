"""Generate exhaustive and scaling evidence for the general matching theorem."""

from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path
from typing import Sequence

from cassi_general_matched_field import (
    GeneralMatchedDecisionError,
    GeneralMatchedDecisionField,
    matched_formula_from_topology,
    recognize_connected_matched_exact_one,
)

OUTPUT = Path("_diag/general_matched_decision.json")
K4 = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
PARALLEL_K4 = ((0, 1), (0, 1), (2, 3), (2, 3), (0, 2), (1, 3))
PRISM6 = (
    (0, 1),
    (1, 2),
    (2, 0),
    (3, 4),
    (4, 5),
    (5, 3),
    (0, 3),
    (1, 4),
    (2, 5),
)
K33 = tuple((left, right) for left in range(3) for right in range(3, 6))
PETERSEN = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (4, 0),
    (5, 7),
    (7, 9),
    (9, 6),
    (6, 8),
    (8, 5),
    (0, 5),
    (1, 6),
    (2, 7),
    (3, 8),
    (4, 9),
)



def prism(blocks: int) -> tuple[tuple[int, int], ...]:
    if blocks < 6 or blocks % 2:
        raise ValueError("prism needs an even block count of at least six")
    half = blocks // 2
    return tuple(
        [(index, (index + 1) % half) for index in range(half)]
        + [
            (half + index, half + (index + 1) % half)
            for index in range(half)
        ]
        + [(index, half + index) for index in range(half)]
    )


def satisfies(formula: Sequence[Sequence[int]], assignment: Sequence[int]) -> bool:
    return all(
        any(
            assignment[abs(literal) - 1] == (1 if literal > 0 else 0)
            for literal in clause
        )
        for clause in formula
    )


def exact_one_model_exists(formula: Sequence[Sequence[int]], variables: int) -> bool:
    recognized = recognize_connected_matched_exact_one(
        formula,
        variable_count=variables,
    )
    assignment = [0] * variables
    for choices in itertools.product(range(3), repeat=len(recognized.blocks)):
        assignment[:] = [0] * variables
        for block, choice in zip(recognized.blocks, choices):
            assignment[block[choice] - 1] = 1
        if satisfies(recognized.formula, assignment):
            return True
    return False


def label_patterns(count: int) -> tuple[tuple[str, tuple[int, ...]], ...]:
    return (
        ("zero", (0,) * count),
        ("one", (1,) * count),
        ("alternating", tuple(index % 2 for index in range(count))),
        (
            "hashed",
            tuple(
                ((index * index + 3 * index + count) ^ (index >> 1)) & 1
                for index in range(count)
            ),
        ),
    )


def run_case(
    name: str,
    blocks: int,
    topology: Sequence[Sequence[int]],
    labels: Sequence[int],
    *,
    enumerate_expected: bool,
    replay_steps: bool,
) -> dict:
    formula = matched_formula_from_topology(blocks, topology, labels)
    field, initial = GeneralMatchedDecisionField.initialize(
        formula,
        variable_count=3 * blocks,
    )
    final, certificate = field.solve(initial)
    if enumerate_expected:
        expected = "sat" if exact_one_model_exists(formula, 3 * blocks) else "unsat"
        if certificate["status"] != expected:
            raise AssertionError(f"{name}: matching/enumeration disagreement")
    if replay_steps:
        stepped = initial
        transitions = []
        while field.inspect(stepped)["status"] == "running":
            stepped, transition = field.step(stepped)
            transitions.append(transition)
        if field.state_sha256(stepped) != field.state_sha256(final):
            raise AssertionError(f"{name}: bulk/public-step digest mismatch")
        if len(transitions) != field.profile.auxiliary_vertices:
            raise AssertionError(f"{name}: public-step count mismatch")
    descriptor = field.descriptor(final)
    restored_field, restored = GeneralMatchedDecisionField.from_descriptor(descriptor)
    if restored_field.certificate(restored) != certificate:
        raise AssertionError(f"{name}: checkpoint decision mismatch")
    return {
        "name": name,
        "blocks": blocks,
        "labels": [edge["parity"] for edge in certificate["formula_edges"]],
        "formula": [list(clause) for clause in formula],
        "certificate": certificate,
        "state": descriptor,
        "enumerated": enumerate_expected,
        "public_steps_replayed": replay_steps,
    }


def controls() -> list[dict]:
    base = matched_formula_from_topology(4, K4, (0, 0, 0, 0, 0, 0))
    rows = []
    malformed = (
        ("duplicate-clause", tuple(base) + (base[0],), 12, "duplicate clauses"),
        ("wrong-variable-count", base, 13, "do not partition"),
        (
            "disconnected-quotient",
            matched_formula_from_topology(
                4,
                ((0, 1), (0, 1), (0, 1), (2, 3), (2, 3), (2, 3)),
                (0, 0, 0, 0, 0, 0),
            ),
            12,
            "disconnected",
        ),
    )
    for name, formula, variables, expected in malformed:
        try:
            GeneralMatchedDecisionField.initialize(formula, variable_count=variables)
        except GeneralMatchedDecisionError as exc:
            if expected not in str(exc):
                raise AssertionError(f"{name}: unexpected failure: {exc}") from exc
            rows.append({"name": name, "status": "rejected", "error": str(exc)})
        else:
            raise AssertionError(f"{name}: malformed source accepted")

    field, initial = GeneralMatchedDecisionField.initialize(base, variable_count=12)
    damaged = copy.deepcopy(field.descriptor(initial))
    damaged["state_sha256"] = "0" * 64
    try:
        GeneralMatchedDecisionField.from_descriptor(damaged)
    except GeneralMatchedDecisionError as exc:
        if "state digest mismatch" not in str(exc):
            raise
        rows.append({"name": "damaged-checkpoint", "status": "rejected", "error": str(exc)})
    else:
        raise AssertionError("damaged checkpoint accepted")
    return rows


def run(output: Path = OUTPUT) -> dict:
    cases = []
    for topology_name, topology in (("k4", K4), ("parallel-k4", PARALLEL_K4)):
        for index, labels in enumerate(itertools.product((0, 1), repeat=6)):
            cases.append(
                run_case(
                    f"exhaustive-{topology_name}-{index:02d}",
                    4,
                    topology,
                    labels,
                    enumerate_expected=True,
                    replay_steps=index in (0, 1, 21, 63),
                )
            )
    for index, labels in enumerate(itertools.product((0, 1), repeat=9)):
        cases.append(
            run_case(
                f"exhaustive-prism6-{index:03d}",
                6,
                PRISM6,
                labels,
                enumerate_expected=True,
                replay_steps=index in (0, 1, 170, 341, 511),
            )
        )
    for topology_name, blocks, topology, enumerate_expected in (
        ("k33", 6, K33, False),
        ("petersen", 10, PETERSEN, False),
    ):
        for pattern_name, labels in label_patterns(len(topology)):
            cases.append(
                run_case(
                    f"topology-{topology_name}-{pattern_name}",
                    blocks,
                    topology,
                    labels,
                    enumerate_expected=enumerate_expected,
                    replay_steps=True,
                )
            )
    for blocks in (8, 12, 24, 48, 96, 192):
        topology = prism(blocks)
        for pattern_name, labels in label_patterns(len(topology)):
            cases.append(
                run_case(
                    f"scaling-prism{blocks}-{pattern_name}",
                    blocks,
                    topology,
                    labels,
                    enumerate_expected=False,
                    replay_steps=True,
                )
            )
    sat = sum(row["certificate"]["status"] == "sat" for row in cases)
    unsat = len(cases) - sat
    parity_consistent_unsat = sum(
        row["certificate"]["status"] == "unsat"
        and sum(row["labels"]) % 2 == 0
        for row in cases
    )
    receipt = {
        "schema": "cassifi.general-matched-decision-receipt.v1",
        "assessment": {
            "result": "total polynomial-time decision on recognized class",
            "p_equals_np": "not established",
            "unrestricted_sat": "not established",
            "theorem": (
                "connected variable-disjoint exact-one triples with one labeled "
                "XOR matching over all variables reduce iff to perfect matching"
            ),
        },
        "field_contract": {
            "tensor": "one immutable float64 [1, 12 + 17b + 5m1, 1] field",
            "owned_state": "source incidence, auxiliary graph, matching, barrier, assignment, counters",
            "persistent_adaptive_side_tables": 0,
            "host_search_hints": 0,
            "model_calls": 0,
        },
        "complexity": {
            "recognition": "O(b log b) canonicalization",
            "matching": "O(N^3) conservative Edmonds bound, N=b+m1<=5b/2",
            "sat_check": "O(b)",
            "unsat_barrier_extraction": "O(N^4) conservative for even N; O(N) odd-N fast path",
            "unsat_certificate_check": "O(N+E)",
            "live_state": "O(b)",
            "certificate_entries": "O(b)",
            "serialized_certificate_bits": "O(b log b)",
        },
        "cases": cases,
        "controls": controls(),
        "summary": {
            "cases": len(cases),
            "exhaustive_cases": sum(row["enumerated"] for row in cases),
            "step_replays": sum(row["public_steps_replayed"] for row in cases),
            "sat": sat,
            "unsat": unsat,
            "parity_consistent_unsat": parity_consistent_unsat,
            "maximum_blocks": max(row["blocks"] for row in cases),
            "maximum_variables": max(3 * row["blocks"] for row in cases),
            "maximum_auxiliary_vertices": max(
                row["certificate"]["auxiliary_vertices"] for row in cases
            ),
            "maximum_field_bytes": max(
                row["certificate"]["field_bytes"] for row in cases
            ),
            "maximum_edge_scans": max(
                row["certificate"]["edge_scans"] for row in cases
            ),
            "maximum_blossom_contractions": max(
                row["certificate"]["blossom_contractions"] for row in cases
            ),
            "all_checkpoints_exact": True,
            "all_enumerated_decisions_agree": True,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt["summary"], sort_keys=True))
    return receipt


if __name__ == "__main__":
    run()
