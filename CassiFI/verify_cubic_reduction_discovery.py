#!/usr/bin/env python3
"""Independent verifier for the cubic reduction discovery receipt.

This file imports neither the runner nor either production implementation.  It
reconstructs the deterministic corpus, exact affine guards, sparse witnesses,
substitutions, component splits, bounded terminals, progress chain,
invocation-local policy field, proof hashes, exhaustive bounded truth,
minimization, and aggregates using only the Python standard library.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import itertools
import json
import math
import random
import struct
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from functools import cmp_to_key
from pathlib import Path
from typing import Any, Iterable, Mapping, NoReturn, Sequence

RECEIPT = Path("_diag/cubic_reduction_discovery.json")
SCHEMA = "cassifi.cubic-reduction-discovery.v1"
RESULT_SCHEMA = "cassifi.cubic-reduction-result.v1"
ALGORITHM_SCHEMA = "cassifi.cubic-reduction-algorithm.v1"
SYSTEM_SCHEMA = "cassifi.affine-boolean-system.v1"
FIELD_SCHEMA = "cassifi.transient-reduction-preference-field.v1"
FIELD_MAGIC = 0xC552
ROW_BOUND_SUPPORT_CAP = 4
STRATEGIES = (
    "sparse_witness",
    "bounded_nullity",
    "forced_variable",
    "functional_pair",
    "literal_probe",
    "nonnegative_row_bound",
    "bounded_separator_relation",
)
FIELD_MODES = 8
FIELD_SHAPE = (1, 9 * FIELD_MODES, 1)
WORK_UNIT_FIELDS = (
    "fraction_updates",
    "projection_states_checked",
    "projection_vector_entries_checked",
    "variable_guards_checked",
    "pair_guards_checked",
    "candidate_assignments",
    "sparse_witness_candidates",
    "literal_probe_trials",
    "propagation_rows_checked",
    "propagation_bound_checks",
    "propagation_assignments",
    "row_bound_combinations",
    "row_bound_coefficient_updates",
    "equation_evaluations",
    "separator_candidates_checked",
    "separator_components_checked",
    "separator_relations_enumerated",
    "substitutions",
)

SUPPORT_THREE_SAT = (
    (1, 6, 3), (1, 3, 5), (1, 8, 2), (4, 6, 8), (4, 8, 5),
    (4, 3, 2), (7, 9, 5), (7, 9, 2), (7, 9, 6),
)
SUPPORT_THREE_UNSAT = (
    (1, 14, 11), (2, 1, 15), (3, 10, 5), (4, 8, 14), (5, 11, 7),
    (6, 12, 1), (7, 9, 2), (8, 15, 12), (9, 5, 6), (10, 13, 3),
    (11, 4, 8), (12, 3, 10), (13, 6, 4), (14, 7, 13), (15, 2, 9),
)
ALL_BASES_TERNARY_SAT = (
    (1, 2, 7), (1, 4, 10), (1, 6, 10), (2, 7, 9), (2, 11, 12),
    (3, 4, 11), (3, 6, 7), (3, 8, 12), (4, 9, 10), (5, 6, 11),
    (5, 8, 9), (5, 8, 12),
)
ALL_BASES_TERNARY_UNSAT = (
    (1, 3, 7), (1, 6, 12), (1, 7, 8), (2, 3, 6), (2, 10, 13),
    (2, 13, 15), (3, 4, 12), (4, 7, 9), (4, 11, 12), (5, 8, 10),
    (5, 11, 15), (5, 13, 14), (6, 9, 14), (8, 11, 14), (9, 10, 15),
)
SINGULAR_ALPHABET_UNSAT = (
    (1, 7, 9), (2, 5, 3), (3, 1, 7), (4, 8, 2), (5, 4, 8),
    (6, 9, 5), (7, 6, 1), (8, 2, 6), (9, 3, 4),
)
FULL_SUPPORT_ALPHABET_UNSAT = (
    (1, 5, 9), (2, 4, 5), (3, 2, 1), (4, 9, 3), (5, 3, 8),
    (6, 8, 2), (7, 1, 4), (8, 7, 6), (9, 6, 7),
)
GREEDY_EXCHANGE_TRAP_SAT = (
    (1, 2, 6), (1, 3, 5), (1, 3, 7), (2, 4, 6), (2, 4, 9),
    (3, 4, 5), (5, 8, 9), (6, 7, 8), (7, 8, 9),
)

Formula = tuple[tuple[int, int, int], ...]
System = tuple[int, tuple[tuple[int, ...], ...], tuple[int, ...]]


class VerificationError(ValueError):
    """Receipt content failed an independent reconstruction."""


def fail(message: str) -> NoReturn:
    raise VerificationError(message)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def canonical_formula(formula: Sequence[Sequence[int]]) -> Formula:
    size = len(formula)
    if size < 1:
        fail("formula must be nonempty")
    rows: list[tuple[int, int, int]] = []
    for raw in formula:
        if len(raw) != 3 or any(isinstance(value, bool) or not isinstance(value, int) for value in raw):
            fail("formula clause is not an integer triple")
        row = tuple(sorted(raw))
        if len(set(row)) != 3 or any(not 1 <= value <= size for value in row):
            fail("formula clause is not simple and in range")
        rows.append((row[0], row[1], row[2]))
    counts = Counter(value for row in rows for value in row)
    if counts != Counter({value: 3 for value in range(1, size + 1)}):
        fail("formula is not cubic")
    return tuple(sorted(rows))


def formula_digest(formula: Sequence[Sequence[int]]) -> str:
    return digest([list(row) for row in canonical_formula(formula)])


def connected(formula: Sequence[Sequence[int]]) -> bool:
    canonical = canonical_formula(formula)
    size = len(canonical)
    adjacency = [set() for _ in range(2 * size)]
    for row_index, row in enumerate(canonical):
        for value in row:
            variable = size + value - 1
            adjacency[row_index].add(variable)
            adjacency[variable].add(row_index)
    reached = {0}
    stack = [0]
    while stack:
        stack.extend(adjacency[stack.pop()] - reached)
        reached.update(stack)
    return len(reached) == 2 * size


def direct_sum(left: Sequence[Sequence[int]], right: Sequence[Sequence[int]]) -> Formula:
    left_c = canonical_formula(left)
    right_c = canonical_formula(right)
    offset = len(left_c)
    return canonical_formula(
        (*left_c, *(tuple(value + offset for value in row) for row in right_c))
    )


def switched_family(blocks: int) -> Formula:
    rows: list[set[int]] = []
    components: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    offset = 0
    for _ in range(blocks):
        variables = tuple(range(offset + 1, offset + 4))
        row_indices = tuple(range(len(rows), len(rows) + 3))
        rows.extend(set(variables) for _ in range(3))
        components.append((row_indices, variables))
        offset += 3
    for left, right in zip(components, components[1:]):
        left_rows, left_variables = left
        right_rows, right_variables = right
        left_row, right_row = left_rows[-1], right_rows[0]
        left_variable, right_variable = left_variables[1], right_variables[1]
        rows[left_row].remove(left_variable)
        rows[left_row].add(right_variable)
        rows[right_row].remove(right_variable)
        rows[right_row].add(left_variable)
    return canonical_formula(tuple(tuple(sorted(row)) for row in rows))


def connected_chain(
    blocks: Sequence[Sequence[Sequence[int]]],
    links: Sequence[tuple[int, int]],
) -> Formula:
    clauses: list[list[int]] = []
    offsets: list[tuple[int, int]] = []
    variable_offset = 0
    for block in blocks:
        canonical = canonical_formula(block)
        offsets.append((len(clauses), variable_offset))
        clauses.extend(
            [[value + variable_offset for value in row] for row in canonical]
        )
        variable_offset += len(canonical)
    for link_index, (left, right) in enumerate(links):
        left_row = offsets[left][0] + link_index % 3
        right_row = offsets[right][0] + link_index % 3
        left_clause, right_clause = clauses[left_row], clauses[right_row]
        left_variable = next(value for value in left_clause if value not in right_clause)
        right_variable = next(value for value in right_clause if value not in left_clause)
        left_clause[left_clause.index(left_variable)] = right_variable
        right_clause[right_clause.index(right_variable)] = left_variable
        clauses[left_row] = sorted(left_clause)
        clauses[right_row] = sorted(right_clause)
    result = canonical_formula(clauses)
    if not connected(result):
        fail("independent deterministic chain is not connected")
    return result


def connected_two_lift(
    base: Sequence[Sequence[int]],
    seed: int,
) -> Formula:
    canonical = canonical_formula(base)
    rng = random.Random(seed)
    signs = {
        (row_index, variable): rng.randrange(2)
        for row_index, row in enumerate(canonical)
        for variable in row
    }
    lifted = canonical_formula(
        tuple(
            tuple(
                sorted(
                    2 * (variable - 1)
                    + (sheet ^ signs[row_index, variable])
                    + 1
                    for variable in row
                )
            )
            for row_index, row in enumerate(canonical)
            for sheet in range(2)
        )
    )
    if not connected(lifted):
        fail("independent two-lift seed is not connected")
    return lifted
def deterministic_relabel(
    formula: Sequence[Sequence[int]],
    seed: int,
) -> Formula:
    canonical = canonical_formula(formula)
    labels = list(range(1, len(canonical) + 1))
    random.Random(seed).shuffle(labels)
    return canonical_formula(
        tuple(
            tuple(labels[variable - 1] for variable in clause)
            for clause in canonical
        )
    )


def two_switch_candidates(
    formula: Sequence[Sequence[int]],
) -> tuple[tuple[Formula, dict[str, int]], ...]:
    canonical = canonical_formula(formula)
    candidates: dict[str, tuple[Formula, tuple[int, int, int, int]]] = {}
    for left_index, right_index in itertools.combinations(range(len(canonical)), 2):
        left_clause = canonical[left_index]
        right_clause = canonical[right_index]
        for left_variable in left_clause:
            if left_variable in right_clause:
                continue
            for right_variable in right_clause:
                if right_variable in left_clause:
                    continue
                rows = [list(clause) for clause in canonical]
                rows[left_index][rows[left_index].index(left_variable)] = right_variable
                rows[right_index][rows[right_index].index(right_variable)] = left_variable
                candidate = canonical_formula(rows)
                if candidate == canonical:
                    continue
                sha256 = formula_digest(candidate)
                operation = (
                    left_index + 1,
                    right_index + 1,
                    left_variable,
                    right_variable,
                )
                previous = candidates.get(sha256)
                if previous is None or operation < previous[1]:
                    candidates[sha256] = (candidate, operation)
    return tuple(
        (
            candidates[sha256][0],
            {
                "left_clause": candidates[sha256][1][0],
                "right_clause": candidates[sha256][1][1],
                "left_variable": candidates[sha256][1][2],
                "right_variable": candidates[sha256][1][3],
            },
        )
        for sha256 in sorted(candidates)
    )


def connected_two_switch_walk(
    formula: Sequence[Sequence[int]],
    *,
    seed: int,
    steps: int,
) -> tuple[Formula, dict[str, Any]]:
    current = canonical_formula(formula)
    trace = []
    for step in range(steps):
        candidates = tuple(
            (candidate, operation)
            for candidate, operation in two_switch_candidates(current)
            if connected(candidate)
        )
        if not candidates:
            fail("independent connected two-switch walk has no successor")
        identities = [
            {
                "formula_sha256": formula_digest(candidate),
                "operation": operation,
            }
            for candidate, operation in candidates
        ]
        selector = hashlib.sha256(
            f"{seed}:{step}:{formula_digest(current)}".encode("ascii")
        ).digest()
        selected_index = int.from_bytes(selector[:8], "big") % len(candidates)
        selected, operation = candidates[selected_index]
        trace.append(
            {
                "step": step + 1,
                "source_formula_sha256": formula_digest(current),
                "connected_candidate_count": len(candidates),
                "candidate_stream_sha256": digest(identities),
                "selected_index": selected_index,
                "operation": operation,
                "target_formula_sha256": formula_digest(selected),
            }
        )
        current = selected
    return current, {
        "seed": seed,
        "steps": steps,
        "trace": trace,
        "trace_sha256": digest(trace),
    }


def structured_specs() -> tuple[
    list[tuple[str, str, Formula]],
    dict[str, Any],
]:
    cases: list[tuple[str, str, Formula]] = []
    provenance: list[dict[str, Any]] = []

    def add(
        name: str,
        group: str,
        family: str,
        formula: Formula,
        construction: dict[str, Any],
    ) -> None:
        canonical = canonical_formula(formula)
        if not connected(canonical):
            fail("independent structured held-out formula is disconnected")
        cases.append((name, group, canonical))
        provenance.append(
            {
                "name": name,
                "group": group,
                "family": family,
                "construction": construction,
                "variables": len(canonical),
                "formula_sha256": formula_digest(canonical),
            }
        )

    for steps in (1, 3, 5):
        formula, trace = connected_two_switch_walk(
            ALL_BASES_TERNARY_SAT,
            seed=17,
            steps=steps,
        )
        add(
            f"heldout-all-bases-switch-seed17-step{steps:02d}",
            "heldout_switch_walk",
            "connected_two_switch_walk",
            formula,
            {
                "base": "all-bases-ternary-sat",
                **trace,
            },
        )

    for name, base_name, base, seed in (
        (
            "heldout-support-sat-two-lift-seed0",
            "support-three-sat",
            SUPPORT_THREE_SAT,
            0,
        ),
        (
            "heldout-support-sat-two-lift-seed11",
            "support-three-sat",
            SUPPORT_THREE_SAT,
            11,
        ),
        (
            "heldout-greedy-trap-two-lift-seed1",
            "greedy-exchange-trap-sat",
            GREEDY_EXCHANGE_TRAP_SAT,
            1,
        ),
        (
            "heldout-all-bases-sat-two-lift-seed15",
            "all-bases-ternary-sat",
            ALL_BASES_TERNARY_SAT,
            15,
        ),
    ):
        add(
            name,
            "heldout_two_lift",
            "connected_two_lift",
            connected_two_lift(base, seed),
            {"base": base_name, "seed": seed},
        )

    for name, base_name, base, seed in (
        (
            "heldout-switched-k33-five-relabel-seed29",
            "switched-k33-five",
            switched_family(5),
            29,
        ),
        (
            "heldout-all-bases-unsat-relabel-seed9182",
            "all-bases-ternary-unsat",
            ALL_BASES_TERNARY_UNSAT,
            9182,
        ),
    ):
        add(
            name,
            "heldout_relabeling",
            "variable_relabeling",
            deterministic_relabel(base, seed),
            {"base": base_name, "seed": seed},
        )

    add(
        "heldout-support-greedy-connected-chain",
        "heldout_connected_chain",
        "heterogeneous_two_switch_chain",
        connected_chain(
            (SUPPORT_THREE_SAT, GREEDY_EXCHANGE_TRAP_SAT),
            ((0, 1),),
        ),
        {
            "blocks": ["support-three-sat", "greedy-exchange-trap-sat"],
            "links": [[0, 1]],
        },
    )
    add(
        "heldout-switched-k33-six",
        "heldout_growing_nullity",
        "growing_switched_family",
        switched_family(6),
        {"blocks": 6, "crown_core": False},
    )
    hashes = [row["formula_sha256"] for row in provenance]
    if len(set(hashes)) != len(hashes):
        fail("independent structured held-out corpus contains a duplicate")
    return cases, {
        "kind": "frozen_structurally_held_out_connected_cubic",
        "cases": provenance,
        "accepted_formulas": len(cases),
        "family_counts": dict(
            sorted(Counter(row["family"] for row in provenance).items())
        ),
        "case_stream_sha256": digest(provenance),
    }




def fixed_specs() -> list[tuple[str, str, Formula]]:
    return [
        ("support-three-sat", "frozen_control", canonical_formula(SUPPORT_THREE_SAT)),
        ("support-three-unsat", "frozen_control", canonical_formula(SUPPORT_THREE_UNSAT)),
        ("all-bases-ternary-sat", "frozen_control", canonical_formula(ALL_BASES_TERNARY_SAT)),
        ("all-bases-ternary-unsat", "frozen_control", canonical_formula(ALL_BASES_TERNARY_UNSAT)),
        ("singular-alphabet-unsat", "frozen_control", canonical_formula(SINGULAR_ALPHABET_UNSAT)),
        ("full-support-alphabet-unsat", "frozen_control", canonical_formula(FULL_SUPPORT_ALPHABET_UNSAT)),
        ("greedy-exchange-trap-sat", "frozen_control", canonical_formula(GREEDY_EXCHANGE_TRAP_SAT)),
        ("duplicate-support-direct-sum", "cache_control", direct_sum(SUPPORT_THREE_SAT, SUPPORT_THREE_SAT)),
        ("switched-k33-three", "growing_nullity", switched_family(3)),
        ("switched-k33-four", "growing_nullity", switched_family(4)),
        ("switched-k33-five", "growing_nullity", switched_family(5)),
        (
            "width-three-sat-chain-two",
            "refinement_hard_core",
            connected_chain(
                (ALL_BASES_TERNARY_SAT, ALL_BASES_TERNARY_SAT),
                ((0, 1),),
            ),
        ),
        (
            "bounded-separator-sat-chain",
            "bounded_separator_control",
            connected_chain(
                (SUPPORT_THREE_SAT, ALL_BASES_TERNARY_SAT),
                ((0, 1),),
            ),
        ),
        (
            "nullity-five-connected-unsat",
            "nullity_five_control",
            connected_chain(
                (SUPPORT_THREE_UNSAT, SUPPORT_THREE_SAT),
                ((0, 1),),
            ),
        ),
    ]


def random_connected_formula(rng: random.Random, size: int) -> tuple[Formula, int]:
    labels = list(range(1, size + 1))
    attempts = 0
    while attempts < 1_000_000:
        attempts += 1
        permutations = []
        for _ in range(3):
            row = labels.copy()
            rng.shuffle(row)
            permutations.append(row)
        rows = tuple(
            sorted(tuple(sorted(permutations[layer][index] for layer in range(3))) for index in range(size))
        )
        if any(len(set(row)) != 3 for row in rows) or len(set(rows)) != size:
            continue
        formula = canonical_formula(rows)
        if connected(formula):
            return formula, attempts
    fail("independent random generator exceeded the attempt bound")


def random_specs(generation: Mapping[str, Any]) -> tuple[list[tuple[str, str, Formula]], dict[str, Any]]:
    seed = generation["seed"]
    sizes = generation["sizes"]
    draws = generation["draws_per_size"]
    if isinstance(seed, bool) or not isinstance(seed, int):
        fail("generation seed is invalid")
    if not isinstance(sizes, list) or any(isinstance(value, bool) or not isinstance(value, int) for value in sizes):
        fail("generation sizes are invalid")
    if isinstance(draws, bool) or not isinstance(draws, int) or draws < 1:
        fail("generation draw count is invalid")
    rng = random.Random(seed)
    seen: set[str] = set()
    result: list[tuple[str, str, Formula]] = []
    attempts = 0
    stream = hashlib.sha256()
    for size in sizes:
        accepted = 0
        draw_index = 0
        while accepted < draws:
            formula, consumed = random_connected_formula(rng, size)
            attempts += consumed
            sha256 = formula_digest(formula)
            stream.update(f"{size}:{draw_index}:{consumed}:{sha256}\n".encode("ascii"))
            draw_index += 1
            if sha256 in seen:
                continue
            seen.add(sha256)
            result.append((f"random-n{size}-{accepted:02d}", "adversarial_random", formula))
            accepted += 1
    rebuilt = {
        "kind": "seeded_three_permutation_simple_connected_cubic",
        "seed": seed,
        "sizes": sizes,
        "draws_per_size": draws,
        "accepted_formulas": len(result),
        "configuration_attempts": attempts,
        "draw_stream_sha256": stream.hexdigest(),
        "draw_stream_record": "size:draw_index:configuration_attempts:formula_sha256\\n",
    }
    return result, rebuilt


def canonical_system(variable_count: int, rows: Sequence[Sequence[int]], rhs: Sequence[int]) -> System:
    if isinstance(variable_count, bool) or not isinstance(variable_count, int) or variable_count < 0:
        fail("system variable count is invalid")
    if len(rows) != len(rhs):
        fail("system row and rhs counts disagree")
    normalized: list[tuple[tuple[int, ...], int]] = []
    for raw_row, raw_target in zip(rows, rhs, strict=True):
        if len(raw_row) != variable_count:
            fail("system row width is invalid")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in (*raw_row, raw_target)):
            fail("system is not integral")
        row = tuple(raw_row)
        target = raw_target
        divisor = 0
        for value in (*row, target):
            divisor = math.gcd(divisor, abs(value))
        divisor = max(1, divisor)
        row = tuple(value // divisor for value in row)
        target //= divisor
        first = next((value for value in (*row, target) if value), 0)
        if first < 0:
            row = tuple(-value for value in row)
            target = -target
        if not any(row) and target == 0:
            continue
        normalized.append((row, target))
    unique = sorted(set(normalized))
    return variable_count, tuple(row for row, _ in unique), tuple(value for _, value in unique)


def system_dict(system: System) -> dict[str, Any]:
    n, rows, rhs = system
    return {
        "schema": SYSTEM_SCHEMA,
        "variable_count": n,
        "coefficients": [list(row) for row in rows],
        "rhs": list(rhs),
    }


def parse_system(value: Mapping[str, Any]) -> System:
    if set(value) != {"schema", "variable_count", "coefficients", "rhs"} or value["schema"] != SYSTEM_SCHEMA:
        fail("proof system schema is invalid")
    system = canonical_system(value["variable_count"], value["coefficients"], value["rhs"])
    if system_dict(system) != value:
        fail("proof system is not canonical")
    return system


def system_digest(system: System) -> str:
    return digest(system_dict(system))


def system_from_formula(formula: Formula) -> System:
    size = len(formula)
    return canonical_system(
        size,
        tuple(tuple(int(value in row) for value in range(1, size + 1)) for row in formula),
        (1,) * size,
    )


@dataclass(frozen=True)
class Affine:
    consistent: bool
    rank: int
    nullity: int
    pivots: tuple[int, ...]
    free: tuple[int, ...]
    particular: tuple[Fraction, ...]
    vectors: tuple[tuple[Fraction, ...], ...]


@dataclass
class AuditLedger:
    proof_nodes: int = 0
    hashes_checked: int = 0
    rref_calls: int = 0
    fraction_updates: int = 0
    projection_states_checked: int = 0
    candidate_assignments: int = 0
    equation_evaluations: int = 0
    sparse_witness_candidates: int = 0
    literal_probe_trials: int = 0
    propagation_rows_checked: int = 0
    propagation_bound_checks: int = 0
    propagation_assignments: int = 0
    row_bound_combinations: int = 0
    row_bound_coefficient_updates: int = 0
    separator_candidates_checked: int = 0
    separator_components_checked: int = 0
    separator_relations_enumerated: int = 0
    separator_assignments_checked: int = 0
    exhaustive_assignments: int = 0
    receipt_cases: int = 0
    cache_references: int = 0

    def as_dict(self) -> dict[str, int]:
        return {name: int(getattr(self, name)) for name in self.__dataclass_fields__}


def rref(matrix: Sequence[Sequence[Fraction]], columns: int, ledger: AuditLedger) -> tuple[list[list[Fraction]], tuple[int, ...]]:
    ledger.rref_calls += 1
    values = [list(row) for row in matrix]
    if any(len(row) != columns for row in values):
        fail("independent RREF width mismatch")

    pivot_row = 0
    pivots: list[int] = []
    num_rows = len(values)

    for column in range(columns):
        # Find the pivot row for this column starting from pivot_row
        selected = None
        for r in range(pivot_row, num_rows):
            if values[r][column]:
                selected = r
                break

        if selected is None:
            continue

        # Swap rows
        values[pivot_row], values[selected] = values[selected], values[pivot_row]

        # Normalize the pivot row
        pivot = values[pivot_row][column]
        pivot_row_vals = values[pivot_row]

        # In-place division for the pivot row from 'column' to 'columns'
        for index in range(column, columns):
            pivot_row_vals[index] /= pivot
            ledger.fraction_updates += 1

        # Eliminate other rows
        for row in range(num_rows):
            if row == pivot_row:
                continue
            factor = values[row][column]
            if factor == 0:
                continue

            row_vals = values[row]
            # Subtract factor * pivot_row_vals from row_vals
            # We only need to update from 'column' onwards because columns before 'column' are already 0 in this row
            # (due to previous elimination steps)
            for index in range(column, columns):
                row_vals[index] -= factor * pivot_row_vals[index]
                ledger.fraction_updates += 2

        pivots.append(column)
        pivot_row += 1
        if pivot_row == num_rows:
            break

    return values, tuple(pivots)


def affine_profile(system: System, ledger: AuditLedger) -> Affine:
    n, rows, rhs = system
    augmented = [[Fraction(value) for value in row] + [Fraction(target)] for row, target in zip(rows, rhs, strict=True)]
    reduced, pivots = rref(augmented, n + 1, ledger)
    if n in pivots:
        return Affine(False, len(pivots) - 1, 0, (), (), (), ())
    coefficient_pivots = tuple(value for value in pivots if value < n)
    free = tuple(value for value in range(n) if value not in coefficient_pivots)
    pivot_rows = {value: row for row, value in enumerate(coefficient_pivots)}
    positions = {value: index for index, value in enumerate(free)}
    particular: list[Fraction] = []
    vectors: list[tuple[Fraction, ...]] = []
    for column in range(n):
        if column in positions:
            index = positions[column]
            particular.append(Fraction(0))
            vectors.append(tuple(Fraction(int(item == index)) for item in range(len(free))))
        else:
            row = pivot_rows[column]
            particular.append(reduced[row][-1])
            vectors.append(tuple(-reduced[row][free_column] for free_column in free))
    return Affine(True, len(coefficient_pivots), len(free), coefficient_pivots, free, tuple(particular), tuple(vectors))


def rank(rows: Sequence[Sequence[Fraction]], columns: int, ledger: AuditLedger) -> int:
    return len(rref(rows, columns, ledger)[1])


def projection_fast_entry_count(
    profile: Affine,
    ports: Sequence[int],
) -> int:
    vectors = tuple(profile.vectors[index] for index in ports)
    entries = len(vectors) * profile.nullity
    if len(vectors) == 2 and any(vectors[0]) and any(vectors[1]):
        entries += profile.nullity
    return entries


def allowed_states(profile: Affine, ports: Sequence[int], ledger: AuditLedger) -> tuple[tuple[int, ...], ...]:
    allowed = []
    for state in itertools.product((0, 1), repeat=len(ports)):
        ledger.projection_states_checked += 1
        equations = tuple(profile.vectors[index] for index in ports)
        targets = tuple(Fraction(value) - profile.particular[index] for index, value in zip(ports, state, strict=True))
        coefficient_rank = rank(equations, profile.nullity, ledger)
        augmented_rank = rank(
            tuple((*row, target) for row, target in zip(equations, targets, strict=True)),
            profile.nullity + 1,
            ledger,
        )
        if coefficient_rank == augmented_rank:
            allowed.append(tuple(state))
    return tuple(allowed)


def satisfied(system: System, assignment: Sequence[int], ledger: AuditLedger) -> bool:
    n, rows, rhs = system
    if len(assignment) != n or any(value not in (0, 1) for value in assignment):
        return False
    for row, target in zip(rows, rhs, strict=True):
        ledger.equation_evaluations += 1
        if sum(value * bit for value, bit in zip(row, assignment, strict=True)) != target:
            return False
    return True


def propagate_literal(
    system: System,
    column: int,
    value: int,
    ledger: AuditLedger,
) -> dict[str, Any]:
    """Independently replay exact integer-bound propagation."""

    n, rows, rhs = system
    if (
        isinstance(column, bool)
        or not isinstance(column, int)
        or not 0 <= column < n
        or isinstance(value, bool)
        or not isinstance(value, int)
        or value not in (0, 1)
    ):
        fail("literal-propagation assumption is invalid")
    assignments: list[int | None] = [None] * n
    assignments[column] = value
    column_rows: list[list[int]] = [[] for _ in range(n)]
    for row_index, row in enumerate(rows):
        for candidate, coefficient in enumerate(row):
            if coefficient:
                column_rows[candidate].append(row_index)

    queue = list(range(len(rows)))
    heapq.heapify(queue)
    queued = [True] * len(rows)
    deductions: list[dict[str, Any]] = []
    while queue:
        row_index = heapq.heappop(queue)
        queued[row_index] = False
        ledger.propagation_rows_checked += 1
        row = rows[row_index]
        target = rhs[row_index]
        premises = [
            {
                "column": candidate + 1,
                "coefficient": coefficient,
                "value": assignments[candidate],
            }
            for candidate, coefficient in enumerate(row)
            if coefficient and assignments[candidate] is not None
        ]
        assigned_sum = 0
        for candidate, coefficient in enumerate(row):
            assigned_value = assignments[candidate]
            if coefficient and assigned_value is not None:
                assigned_sum += coefficient * assigned_value
        residual_rhs = target - assigned_sum
        unknown = [
            candidate
            for candidate, coefficient in enumerate(row)
            if coefficient and assignments[candidate] is None
        ]
        minimum = sum(min(0, row[candidate]) for candidate in unknown)
        maximum = sum(max(0, row[candidate]) for candidate in unknown)
        ledger.propagation_bound_checks += 1
        if not minimum <= residual_rhs <= maximum:
            return {
                "assumption": {"column": column + 1, "value": value},
                "outcome": "conflict",
                "assignment": assignments,
                "deductions": deductions,
                "conflict": {
                    "kind": "equation_interval_empty",
                    "row": row_index + 1,
                    "equation_rhs": target,
                    "premises": premises,
                    "residual_rhs": residual_rhs,
                    "remaining_minimum": minimum,
                    "remaining_maximum": maximum,
                },
            }
        for candidate in unknown:
            coefficient = row[candidate]
            other_minimum = minimum - min(0, coefficient)
            other_maximum = maximum - max(0, coefficient)
            zero_residual = residual_rhs
            one_residual = residual_rhs - coefficient
            ledger.propagation_bound_checks += 2
            zero_possible = other_minimum <= zero_residual <= other_maximum
            one_possible = other_minimum <= one_residual <= other_maximum
            if not zero_possible and not one_possible:
                return {
                    "assumption": {"column": column + 1, "value": value},
                    "outcome": "conflict",
                    "assignment": assignments,
                    "deductions": deductions,
                    "conflict": {
                        "kind": "Boolean_domain_empty",
                        "row": row_index + 1,
                        "column": candidate + 1,
                        "equation_rhs": target,
                        "premises": premises,
                        "residual_rhs": residual_rhs,
                        "other_minimum": other_minimum,
                        "other_maximum": other_maximum,
                        "zero_residual_rhs": zero_residual,
                        "one_residual_rhs": one_residual,
                    },
                }
            if zero_possible == one_possible:
                continue
            forced_value = int(one_possible)
            rejected_value = 1 - forced_value
            rejected_residual = (
                zero_residual if rejected_value == 0 else one_residual
            )
            assignments[candidate] = forced_value
            ledger.propagation_assignments += 1
            deductions.append(
                {
                    "row": row_index + 1,
                    "column": candidate + 1,
                    "value": forced_value,
                    "rejected_value": rejected_value,
                    "equation_rhs": target,
                    "premises": premises,
                    "residual_rhs": residual_rhs,
                    "other_minimum": other_minimum,
                    "other_maximum": other_maximum,
                    "rejected_residual_rhs": rejected_residual,
                }
            )
            for affected in column_rows[candidate]:
                if not queued[affected]:
                    heapq.heappush(queue, affected)
                    queued[affected] = True
            break

    complete_assignment = tuple(
        item for item in assignments if item is not None
    )
    outcome = "complete" if len(complete_assignment) == n else "partial"
    if outcome == "complete" and not satisfied(system, complete_assignment, AuditLedger()):
        fail("complete propagation assignment is invalid")
    return {
        "assumption": {"column": column + 1, "value": value},
        "outcome": outcome,
        "assignment": assignments,
        "deductions": deductions,
        "conflict": None,
    }


def bounded_literal_probe(
    system: System,
    ledger: AuditLedger,
) -> dict[str, Any] | None:
    """Independently enumerate bounded nonrecursive single-literal trials."""

    n = system[0]
    checked = 0
    for column in range(n):
        for value in (0, 1):
            checked += 1
            ledger.literal_probe_trials += 1
            trace = propagate_literal(system, column, value, ledger)
            if trace["outcome"] == "complete":
                assignment = tuple(int(item) for item in trace["assignment"])
                return {
                    "terminal": True,
                    "status": "sat",
                    "assignment": assignment,
                    "certificate": {
                        "kind": "literal_probe_witness",
                        "trials_checked": checked,
                        "trial_bound": 2 * n,
                        "selected_trial": trace,
                        "selected_columns": [
                            index + 1
                            for index, bit in enumerate(assignment)
                            if bit
                        ],
                    },
                }
            if trace["outcome"] == "conflict":
                return {
                    "terminal": False,
                    "column": column,
                    "certificate": {
                        "kind": "literal_probe_forcing",
                        "trials_checked": checked,
                        "trial_bound": 2 * n,
                        "selected_trial": trace,
                        "forced_column": column + 1,
                        "forced_value": 1 - value,
                    },
                }
    return None




def sparse_boolean_witness(
    system: System,
    ledger: AuditLedger,
) -> tuple[tuple[int, ...], dict[str, Any]] | None:
    n, rows, rhs = system
    candidates: list[tuple[str, tuple[int, ...]]] = [
        ("zero", (0,) * n),
        ("all_one", (1,) * n),
    ]
    candidates.extend(
        (
            "unit",
            tuple(int(index == column) for index in range(n)),
        )
        for column in range(n)
    )
    supports = tuple(sum(row[column] != 0 for row in rows) for column in range(n))
    private_assignment = [0] * n
    private_columns: list[int] = []
    for row, target in zip(rows, rhs, strict=True):
        if target == 0:
            continue
        column = next(
            (
                index
                for index, coefficient in enumerate(row)
                if supports[index] == 1 and coefficient == target
            ),
            None,
        )
        if column is None:
            break
        private_assignment[column] = 1
        private_columns.append(column + 1)
    else:
        candidates.append(("private_row_cover", tuple(private_assignment)))

    for checked, (witness_kind, assignment) in enumerate(candidates, start=1):
        ledger.sparse_witness_candidates += 1
        if not satisfied(system, assignment, ledger):
            continue
        return assignment, {
            "kind": "sparse_boolean_witness",
            "witness_kind": witness_kind,
            "selected_columns": [
                index + 1 for index, value in enumerate(assignment) if value
            ],
            "private_cover_columns": (
                private_columns if witness_kind == "private_row_cover" else None
            ),
            "candidates_checked": checked,
        }
    return None


def nonnegative_row_bound(
    system: System,
    ledger: AuditLedger,
) -> tuple[int, dict[str, Any]] | None:
    n, rows, rhs = system
    checked = 0

    # Pre-extract rows and rhs for faster access
    # rows is tuple of tuples, rhs is tuple
    # We will iterate combinations

    max_support = min(ROW_BOUND_SUPPORT_CAP, len(rows))

    # Cache row data to avoid repeated tuple indexing if possible, 
    # though tuple indexing is fast. The main cost is the nested loops.

    for support_size in range(1, max_support + 1):
        # itertools.combinations(range(len(rows)), support_size)
        # We can optimize the inner loops

        # Generate all sign combinations
        # itertools.product((-1, 1), repeat=support_size)

        # To speed up, we can use a single loop over combinations and signs
        # and compute the required values efficiently.

        # Optimization: Pre-calculate the rows as lists for mutable operations?
        # No, we just need to sum them.

        # Let's try to minimize the inner loop overhead.

        for selected_rows in itertools.combinations(range(len(rows)), support_size):
            # selected_rows is a tuple of indices

            # We need to iterate over all sign combinations
            # Instead of nested product, we can iterate and compute

            # To avoid creating many small lists, we can compute on the fly.

            # Let's pre-fetch the rows for this combination
            selected_row_data = [rows[idx] for idx in selected_rows]
            selected_rhs_vals = [rhs[idx] for idx in selected_rows]

            # Iterate over signs
            for signs in itertools.product((-1, 1), repeat=support_size):
                checked += 1
                ledger.row_bound_combinations += 1

                # Compute target and combined vector
                # Using a list comprehension or loop

                # Initialize combined
                combined = [0] * n
                target = 0

                # Unroll the zip loop for speed
                for i in range(support_size):
                    row_index = selected_rows[i]
                    multiplier = signs[i]

                    # Update target
                    target += multiplier * selected_rhs_vals[i]
                    ledger.row_bound_coefficient_updates += 1

                    # Update combined
                    row_data = selected_row_data[i]
                    for col_idx in range(n):
                        combined[col_idx] += multiplier * row_data[col_idx]
                        ledger.row_bound_coefficient_updates += 1

                # Check if target < 0 or any coefficient < 0
                if target < 0:
                    continue

                # Check for negative coefficients
                # Using any() is fast, but we can optimize by checking during sum?
                # No, we need the full sum first.

                has_negative = False
                for coeff in combined:
                    if coeff < 0:
                        has_negative = True
                        break

                if has_negative:
                    continue

                # Find forced column: first column where coefficient > target
                forced_column = None
                for col_idx, coeff in enumerate(combined):
                    if coeff > target:
                        forced_column = col_idx
                        break

                if forced_column is None:
                    continue

                # Found a valid bound
                multipliers = [0] * len(rows)
                for i in range(support_size):
                    multipliers[selected_rows[i]] = signs[i]

                return forced_column, {
                    "kind": "nonnegative_row_bound",
                    "support_cap": ROW_BOUND_SUPPORT_CAP,
                    "combinations_checked": checked,
                    "row_multipliers": multipliers,
                    "combined_coefficients": combined,
                    "combined_rhs": target,
                    "forced_column": forced_column + 1,
                    "forced_value": 0,
                }

    return None


def separator_components(
    system: System,
    ports: Sequence[int],
) -> tuple[tuple[int, ...], ...]:
    n, rows, _ = system
    excluded = set(ports)
    neighbors = [set() for _ in range(n)]
    for row in rows:
        active = [column for column, coefficient in enumerate(row) if coefficient]
        for column in active:
            neighbors[column].update(other for other in active if other != column)
    remaining = set(range(n)) - excluded
    result: list[tuple[int, ...]] = []
    while remaining:
        start = min(remaining)
        stack = [start]
        component: set[int] = set()
        while stack:
            column = stack.pop()
            if column not in remaining:
                continue
            remaining.remove(column)
            component.add(column)
            stack.extend(neighbors[column] & remaining)
        result.append(tuple(sorted(component)))
    return tuple(result)


def separator_relation_equations(
    width: int,
    states: Sequence[Sequence[int]],
) -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...]] | None:
    canonical_states = tuple(sorted(set(tuple(state) for state in states)))
    if any(
        len(state) != width or any(value not in (0, 1) for value in state)
        for state in canonical_states
    ):
        fail("separator relation contains a non-Boolean state")
    if not canonical_states:
        relation = canonical_system(width, ((0,) * width,), (1,))
    elif len(canonical_states) == 1:
        relation = canonical_system(
            width,
            tuple(
                tuple(int(column == fixed) for column in range(width))
                for fixed in range(width)
            ),
            canonical_states[0],
        )
    elif len(canonical_states) == 2:
        left, right = canonical_states
        if width == 1:
            relation = canonical_system(width, (), ())
        else:
            delta = (right[0] - left[0], right[1] - left[1])
            normal = (delta[1], -delta[0])
            relation = canonical_system(
                width,
                (normal,),
                (normal[0] * left[0] + normal[1] * left[1],),
            )
    elif width == 2 and len(canonical_states) == 3:
        return None
    elif len(canonical_states) == 1 << width:
        relation = canonical_system(width, (), ())
    else:
        fail("separator relation cardinality is unsupported")
    return relation[1], relation[2]


def bounded_boolean_relation(
    system: System,
    affine: Affine,
    port_width: int,
    ledger: AuditLedger,
) -> tuple[tuple[tuple[int, ...], ...], dict[tuple[int, ...], tuple[int, ...]], int]:
    if not affine.consistent:
        return (), {}, 0
    witnesses: dict[tuple[int, ...], tuple[int, ...]] = {}
    checked = 0
    for free_values in itertools.product((0, 1), repeat=affine.nullity):
        checked += 1
        ledger.candidate_assignments += 1
        ledger.separator_assignments_checked += 1
        candidate = tuple(
            particular
            + sum(
                coefficient * value
                for coefficient, value in zip(vector, free_values, strict=True)
            )
            for particular, vector in zip(
                affine.particular,
                affine.vectors,
                strict=True,
            )
        )
        if any(value not in (0, 1) for value in candidate):
            continue
        integer_candidate = tuple(int(value) for value in candidate)
        if not satisfied(system, integer_candidate, ledger):
            continue
        state = integer_candidate[:port_width]
        witnesses.setdefault(state, integer_candidate)
    states = tuple(sorted(witnesses))
    return states, witnesses, checked


def bounded_separator_relation(
    system: System,
    cap: int,
    ledger: AuditLedger,
) -> dict[str, Any] | None:
    n, rows, rhs = system
    for width in (1, 2):
        for ports in itertools.combinations(range(n), width):
            ledger.separator_candidates_checked += 1
            components = separator_components(system, ports)
            if len(components) < 2:
                continue
            for interior in components:
                ledger.separator_components_checked += 1
                interior_set = set(interior)
                local_order = (*ports, *interior)
                local_set = set(local_order)
                local_rows: list[tuple[int, ...]] = []
                local_rhs: list[int] = []
                retained_rows: list[tuple[int, ...]] = []
                retained_rhs: list[int] = []
                retained = tuple(column for column in range(n) if column not in interior_set)
                for row, target in zip(rows, rhs, strict=True):
                    active = {column for column, coefficient in enumerate(row) if coefficient}
                    if active & interior_set:
                        if not active <= local_set:
                            fail("separator failed to isolate its component")
                        local_rows.append(tuple(row[column] for column in local_order))
                        local_rhs.append(target)
                    else:
                        retained_rows.append(tuple(row[column] for column in retained))
                        retained_rhs.append(target)
                local = canonical_system(
                    len(local_order),
                    local_rows,
                    local_rhs,
                )
                local_affine = affine_profile(local, ledger)
                if local_affine.consistent and local_affine.nullity > cap:
                    continue
                ledger.separator_relations_enumerated += 1
                states, witnesses, checked = bounded_boolean_relation(
                    local,
                    local_affine,
                    width,
                    ledger,
                )
                relation = separator_relation_equations(width, states)
                if relation is None:
                    continue
                relation_rows, relation_rhs = relation
                positions = {column: index for index, column in enumerate(retained)}
                for row, target in zip(relation_rows, relation_rhs, strict=True):
                    expanded = [0] * len(retained)
                    for port, coefficient in zip(ports, row, strict=True):
                        expanded[positions[port]] = coefficient
                    retained_rows.append(tuple(expanded))
                    retained_rhs.append(target)
                target = canonical_system(
                    len(retained),
                    retained_rows,
                    retained_rhs,
                )
                return {
                    "target": target,
                    "certificate": {
                        "kind": "bounded_separator_relation",
                        "separator_width_cap": 2,
                        "terminal_nullity_cap": cap,
                        "separator_variables": [column + 1 for column in ports],
                        "eliminated_variables": [column + 1 for column in interior],
                        "retained_columns": [column + 1 for column in retained],
                        "local_variable_order": [column + 1 for column in local_order],
                        "local_system": system_dict(local),
                        "local_rank": local_affine.rank,
                        "local_nullity": local_affine.nullity,
                        "candidates_checked": checked,
                        "candidate_bound": (
                            0
                            if not local_affine.consistent
                            else 1 << local_affine.nullity
                        ),
                        "feasible_separator_states": [
                            list(state) for state in states
                        ],
                        "state_witnesses": [
                            {
                                "state": list(state),
                                "assignment": list(witnesses[state]),
                            }
                            for state in states
                        ],
                        "relation_coefficients": [list(row) for row in relation_rows],
                        "relation_rhs": list(relation_rhs),
                    },
                }
    return None


def transform_system(system: System, offset: Sequence[int], transform: Sequence[Sequence[int]]) -> System:
    n, rows, rhs = system
    if len(offset) != n or len(transform) != n:
        fail("certificate transform source dimension is invalid")
    target_n = len(transform[0]) if transform else 0
    if any(len(row) != target_n for row in transform):
        fail("certificate transform target dimension is invalid")
    if any(value not in (-1, 0, 1) for value in offset) or any(
        value not in (-1, 0, 1) for row in transform for value in row
    ):
        fail("certificate transform is not a Boolean affine template")
    target_rows = tuple(
        tuple(sum(row[old] * transform[old][new] for old in range(n)) for new in range(target_n))
        for row in rows
    )
    target_rhs = tuple(
        target - sum(row[old] * offset[old] for old in range(n))
        for row, target in zip(rows, rhs, strict=True)
    )
    return canonical_system(target_n, target_rows, target_rhs)


def lift(offset: Sequence[int], transform: Sequence[Sequence[int]], assignment: Sequence[int]) -> tuple[int, ...]:
    return tuple(
        int(base + sum(value * bit for value, bit in zip(row, assignment, strict=True)))
        for base, row in zip(offset, transform, strict=True)
    )


def lift_separator(
    variable_count: int,
    certificate: Mapping[str, Any],
    child_assignment: Sequence[int],
) -> tuple[int, ...]:
    retained = tuple(int(value) - 1 for value in certificate["retained_columns"])
    separator = tuple(int(value) - 1 for value in certificate["separator_variables"])
    local_order = tuple(int(value) - 1 for value in certificate["local_variable_order"])
    if len(retained) != len(child_assignment):
        fail("separator child assignment has the wrong dimension")
    assignment = [0] * variable_count
    for column, value in zip(retained, child_assignment, strict=True):
        assignment[column] = int(value)
    state = tuple(assignment[column] for column in separator)
    witness = next(
        (
            tuple(int(value) for value in row["assignment"])
            for row in certificate["state_witnesses"]
            if tuple(row["state"]) == state
        ),
        None,
    )
    if witness is None or len(witness) != len(local_order):
        fail("separator relation lacks a lifting witness")
    for column, value in zip(local_order, witness, strict=True):
        if column in separator and assignment[column] != value:
            fail("separator witness disagrees with its state")
        assignment[column] = value
    return tuple(assignment)


def system_components(system: System) -> tuple[tuple[tuple[int, ...], System], ...]:
    n, rows, rhs = system
    variable_rows = [set() for _ in range(n)]
    row_variables = []
    for row_index, row in enumerate(rows):
        active = {index for index, value in enumerate(row) if value}
        row_variables.append(active)
        for index in active:
            variable_rows[index].add(row_index)
    visited: set[int] = set()
    result = []
    for start in range(n):
        if start in visited:
            continue
        variables: set[int] = set()
        selected_rows: set[int] = set()
        stack = [start]
        while stack:
            variable = stack.pop()
            if variable in variables:
                continue
            variables.add(variable)
            visited.add(variable)
            for row_index in variable_rows[variable]:
                if row_index in selected_rows:
                    continue
                selected_rows.add(row_index)
                stack.extend(row_variables[row_index] - variables)
        columns = tuple(sorted(variables))
        row_indices = tuple(sorted(selected_rows))
        child = canonical_system(
            len(columns),
            tuple(tuple(rows[row][column] for column in columns) for row in row_indices),
            tuple(rhs[row] for row in row_indices),
        )
        result.append((columns, child))
    return tuple(result)


def bounded_terminal(system: System, profile: Affine, cap: int, ledger: AuditLedger) -> tuple[str, tuple[int, ...] | None, int]:
    if profile.nullity > cap:
        fail("bounded terminal exceeds fixed nullity cap")
    checked = 0
    for free_values in itertools.product((0, 1), repeat=profile.nullity):
        checked += 1
        ledger.candidate_assignments += 1
        candidate = tuple(
            particular + sum(value * bit for value, bit in zip(vector, free_values, strict=True))
            for particular, vector in zip(profile.particular, profile.vectors, strict=True)
        )
        if any(value not in (0, 1) for value in candidate):
            continue
        integer = tuple(int(value) for value in candidate)
        if satisfied(system, integer, ledger):
            return "sat", integer, checked
    return "unsat", None, checked


class FieldAudit:
    def __init__(self) -> None:
        self.support = [0] * len(STRATEGIES)
        self.applicable = [0] * len(STRATEGIES)
        self.terminal = [0] * len(STRATEGIES)
        self.removed = [0] * len(STRATEGIES)
        self.work = [0] * len(STRATEGIES)
        self.projections = [0] * len(STRATEGIES)
        self.last_epoch = [0] * len(STRATEGIES)
        self.first_choices = [0] * len(STRATEGIES)
        self.epoch = 0

    def order(
        self,
        nullity: int,
        cap: int,
        schedule_mode: str,
        literal_probing: bool,
    ) -> tuple[str, ...]:
        def compare(left: int, right: int) -> int:
            if self.support[left] == 0 or self.support[right] == 0:
                if self.support[left] == 0 and self.support[right] != 0:
                    return -1
                if self.support[right] == 0 and self.support[left] != 0:
                    return 1
            comparison = (
                (self.removed[left] + self.terminal[left]) * max(1, self.work[right])
                - (self.removed[right] + self.terminal[right]) * max(1, self.work[left])
            )
            if comparison:
                return -1 if comparison > 0 else 1
            comparison = (
                self.applicable[left] * max(1, self.support[right])
                - self.applicable[right] * max(1, self.support[left])
            )
            if comparison:
                return -1 if comparison > 0 else 1
            return -1 if left < right else (1 if left > right else 0)

        indices = [
            index
            for index, strategy in enumerate(STRATEGIES)
            if literal_probing or strategy != "literal_probe"
        ]
        if schedule_mode == "adaptive":
            indices.sort(key=cmp_to_key(compare))
        elif schedule_mode != "fixed":
            fail("algorithm schedule mode is invalid")
        if nullity <= cap:
            bounded = STRATEGIES.index("bounded_nullity")
            indices.remove(bounded)
            indices.insert(0, bounded)
        return tuple(STRATEGIES[index] for index in indices)

    def observe(
        self,
        strategy: str,
        *,
        applicable: bool,
        terminal: bool,
        removed: int,
        work: int,
        projections: int,
        first: bool,
    ) -> None:
        index = STRATEGIES.index(strategy)
        self.epoch += 1
        self.support[index] += 1
        self.applicable[index] += int(applicable)
        self.terminal[index] += int(terminal)
        self.removed[index] += removed
        self.work[index] += max(1, work)
        self.projections[index] += projections
        self.last_epoch[index] = self.epoch
        self.first_choices[index] += int(first)

    def expected_inspection(
        self,
        cap: int,
        schedule_mode: str,
        literal_probing: bool,
    ) -> dict[str, Any]:
        rows = []
        for index, strategy in enumerate(STRATEGIES):
            rows.append(
                {
                    "strategy": strategy,
                    "support": self.support[index],
                    "applicable": self.applicable[index],
                    "terminal": self.terminal[index],
                    "variables_removed": self.removed[index],
                    "work": self.work[index],
                    "projection_states_checked": self.projections[index],
                    "last_epoch": self.last_epoch[index],
                    "first_choices": self.first_choices[index],
                }
            )
        return {
            "schema": FIELD_SCHEMA,
            "persistence": "invocation_local_only",
            "shape": list(FIELD_SHAPE),
            "field_bytes": FIELD_SHAPE[1] * 8,
            "state_sha256": self.state_sha256(),
            "epoch": self.epoch,
            "schedule_mode": schedule_mode,
            "literal_probing": literal_probing,
            "observations": sum(self.support),
            "evidence": rows,
            "preferred_order_at_large_nullity": list(
                self.order(cap + 1, cap, schedule_mode, literal_probing)
            ),
        }

    def state_sha256(self) -> str:
        values = [0.0] * (9 * FIELD_MODES)
        planes = [values[index * FIELD_MODES : (index + 1) * FIELD_MODES] for index in range(9)]
        for index in range(len(STRATEGIES)):
            planes[0][index] = float(self.support[index])
            planes[1][index] = float(self.applicable[index])
            planes[2][index] = float(self.terminal[index])
            planes[3][index] = float(self.removed[index])
            planes[4][index] = float(self.work[index])
            planes[5][index] = float(self.projections[index])
            planes[6][index] = float(self.last_epoch[index])
            planes[7][index] = float(self.first_choices[index])
        planes[8][0] = float(FIELD_MAGIC)
        planes[8][1] = float(self.epoch)
        planes[8][2] = float(sum(self.support))
        flattened = [value for plane in planes for value in plane]
        header = canonical_json(
            {"schema": FIELD_SCHEMA, "shape": list(FIELD_SHAPE), "dtype": "float64"}
        ).encode("utf-8")
        sha = hashlib.sha256(header)
        sha.update(struct.pack("<" + "d" * len(flattened), *flattened))
        return sha.hexdigest()


@dataclass
class ProofContext:
    events: list[dict[str, Any]]
    cap: int
    field: FieldAudit
    ledger: AuditLedger
    schedule_mode: str
    known: dict[str, tuple[str, str, tuple[int, ...] | None]]
    used_events: list[int]
    variable_guards: int = 0
    pair_guards: int = 0
    sparse_witness_candidates: int = 0
    literal_probe_trials: int = 0
    propagation_rows_checked: int = 0
    propagation_bound_checks: int = 0
    propagation_assignments: int = 0
    row_bound_combinations: int = 0
    row_bound_coefficient_updates: int = 0
    projection_fast_queries: int = 0
    projection_vector_entries_checked: int = 0
    separator_candidates_checked: int = 0
    separator_components_checked: int = 0
    separator_relations_enumerated: int = 0
    separator_assignments_checked: int = 0
    literal_probing: bool = False


def check_event(
    context: ProofContext,
    index: Any,
    *,
    kind: str,
    source: System,
    after: int,
    target_sha256: str | None,
) -> None:
    if index is None and len(source[1]) == 0 and source[0] == 0:
        return
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(context.events):
        fail("proof event index is invalid")
    event = context.events[index]
    expected = {
        "index": index,
        "kind": kind,
        "source_system_sha256": system_digest(source),
        "target_system_sha256": target_sha256,
        "component_before": source[0] ** 2,
        "component_after": after,
    }
    for key, value in expected.items():
        if event.get(key) != value:
            fail(f"progress event {index} disagrees on {key}")
    context.used_events.append(index)


def strategy_scan(
    strategy: str,
    system: System,
    affine: Affine,
    context: ProofContext,
) -> tuple[bool, int, tuple[int, ...] | None, tuple[tuple[int, ...], ...] | None]:
    n = system[0]
    if strategy == "sparse_witness":
        before = context.ledger.sparse_witness_candidates
        witness = sparse_boolean_witness(system, context.ledger)
        context.sparse_witness_candidates += (
            context.ledger.sparse_witness_candidates - before
        )
        return witness is not None, 0, None, None
    if strategy == "bounded_nullity":
        return affine.nullity <= context.cap, 0, None, None
    if strategy == "forced_variable":
        for column in range(n):
            context.variable_guards += 1
            context.projection_fast_queries += 1
            context.projection_vector_entries_checked += projection_fast_entry_count(
                affine,
                (column,),
            )
            states = allowed_states(affine, (column,), context.ledger)
            if len(states) <= 1:
                return True, 2 * (column + 1), (column,), states
        return False, 2 * n, None, None
    if strategy == "functional_pair":
        scanned = 0
        for left, right in itertools.combinations(range(n), 2):
            scanned += 1
            context.pair_guards += 1
            context.projection_fast_queries += 1
            context.projection_vector_entries_checked += projection_fast_entry_count(
                affine,
                (left, right),
            )
            states = allowed_states(affine, (left, right), context.ledger)
            if len(states) <= 2:
                return True, 4 * scanned, (left, right), states
        return False, 4 * scanned, None, None
    if strategy == "literal_probe":
        before_trials = context.ledger.literal_probe_trials
        before_rows = context.ledger.propagation_rows_checked
        before_bounds = context.ledger.propagation_bound_checks
        before_assignments = context.ledger.propagation_assignments
        probe = bounded_literal_probe(system, context.ledger)
        context.literal_probe_trials += (
            context.ledger.literal_probe_trials - before_trials
        )
        context.propagation_rows_checked += (
            context.ledger.propagation_rows_checked - before_rows
        )
        context.propagation_bound_checks += (
            context.ledger.propagation_bound_checks - before_bounds
        )
        context.propagation_assignments += (
            context.ledger.propagation_assignments - before_assignments
        )
        if probe is None:
            return False, 0, None, None
        if probe["terminal"]:
            return True, 0, None, None
        column = int(probe["column"])
        value = int(probe["certificate"]["forced_value"])
        return True, 0, (column,), ((value,),)
    if strategy == "nonnegative_row_bound":
        before_combinations = context.ledger.row_bound_combinations
        before_updates = context.ledger.row_bound_coefficient_updates
        bound = nonnegative_row_bound(system, context.ledger)
        context.row_bound_combinations += (
            context.ledger.row_bound_combinations - before_combinations
        )
        context.row_bound_coefficient_updates += (
            context.ledger.row_bound_coefficient_updates - before_updates
        )
        if bound is None:
            return False, 0, None, None
        column, _ = bound
        return True, 0, (column,), ((0,),)
    if strategy == "bounded_separator_relation":
        before_candidates = context.ledger.separator_candidates_checked
        before_components = context.ledger.separator_components_checked
        before_relations = context.ledger.separator_relations_enumerated
        before_assignments = context.ledger.separator_assignments_checked
        relation = bounded_separator_relation(system, context.cap, context.ledger)
        context.separator_candidates_checked += (
            context.ledger.separator_candidates_checked - before_candidates
        )
        context.separator_components_checked += (
            context.ledger.separator_components_checked - before_components
        )
        context.separator_relations_enumerated += (
            context.ledger.separator_relations_enumerated - before_relations
        )
        context.separator_assignments_checked += (
            context.ledger.separator_assignments_checked - before_assignments
        )
        if relation is None:
            return False, 0, None, None
        certificate = relation["certificate"]
        ports = tuple(
            int(value) - 1 for value in certificate["separator_variables"]
        )
        states = tuple(
            tuple(int(value) for value in state)
            for state in certificate["feasible_separator_states"]
        )
        return True, 0, ports, states
    fail("unknown proof strategy")


def audit_attempts(
    certificate: Mapping[str, Any],
    system: System,
    affine: Affine,
    context: ProofContext,
    *,
    target_variables: int | None,
    terminal: bool,
) -> tuple[str, tuple[int, ...] | None, tuple[tuple[int, ...], ...] | None]:
    expected_order = context.field.order(
        affine.nullity,
        context.cap,
        context.schedule_mode,
        context.literal_probing,
    )
    if tuple(certificate.get("strategy_order", ())) != expected_order:
        fail("proof strategy order disagrees with the transient field")
    attempts = certificate.get("attempted")
    if not isinstance(attempts, list) or not attempts:
        fail("proof lacks strategy attempts")
    if [row.get("strategy") for row in attempts] != list(
        expected_order[: len(attempts)]
    ):
        fail("proof attempts are not an order prefix")
    selected_ports = None
    selected_states = None
    for index, row in enumerate(attempts):
        strategy = row["strategy"]
        applicable, expected_projections, ports, states = strategy_scan(
            strategy,
            system,
            affine,
            context,
        )
        recorded_applicable = row.get("applicable")
        if recorded_applicable != applicable:
            fail("strategy applicability disagrees with exact reconstruction")
        if row.get("order") != index:
            fail("strategy attempt order index is invalid")
        if row.get("projection_states_checked") != expected_projections:
            fail("strategy projection cost disagrees with exact scan")
        if (
            isinstance(row.get("work"), bool)
            or not isinstance(row.get("work"), int)
            or row["work"] < 1
        ):
            fail("strategy work observation is invalid")
        if applicable and index != len(attempts) - 1:
            fail("proof continued after an applicable rule")
        if (
            not applicable
            and index == len(attempts) - 1
            and len(attempts) != len(expected_order)
        ):
            fail("proof stopped before finding a rule or exhausting the schedule")
        removed = 0 if target_variables is None else system[0] - target_variables
        context.field.observe(
            strategy,
            applicable=applicable,
            terminal=terminal and applicable,
            removed=removed if applicable else 0,
            work=row["work"],
            projections=row["projection_states_checked"],
            first=index == 0,
        )
        if applicable:
            selected_ports, selected_states = ports, states
    return attempts[-1]["strategy"], selected_ports, selected_states


def verify_node(node: Mapping[str, Any], expected_system: System, context: ProofContext) -> tuple[str, tuple[int, ...] | None, str]:
    context.ledger.proof_nodes += 1
    system = parse_system(node.get("system", {}))
    if system != expected_system or node.get("system_sha256") != system_digest(system):
        fail("proof node is detached from its expected system")
    proof_body = dict(node)
    proof_sha256 = proof_body.pop("proof_sha256", None)
    if proof_sha256 != digest(proof_body):
        fail("proof node digest is invalid")
    context.ledger.hashes_checked += 1
    kind = node.get("kind")
    status = node.get("status")
    raw_assignment = node.get("assignment")
    assignment = None if raw_assignment is None else tuple(raw_assignment)
    if status == "sat":
        if assignment is None or not satisfied(system, assignment, context.ledger):
            fail("proof SAT assignment fails its system")
    elif status not in ("unsat", "unresolved") or assignment is not None:
        fail("proof node status/assignment pairing is invalid")

    affine = affine_profile(system, context.ledger)
    if kind == "canonical_cache_hit":
        reference = node.get("reference_proof_sha256")
        if reference not in context.known:
            fail("cache hit references no earlier canonical proof")
        ref_system, ref_status, ref_assignment = context.known[reference]
        if (ref_system, ref_status, ref_assignment) != (system_digest(system), status, assignment):
            fail("cache hit disagrees with its referenced proof")
        context.ledger.cache_references += 1
        check_event(context, node.get("progress_event"), kind=kind, source=system, after=0, target_sha256=None)
    elif kind == "affine_contradiction":
        if affine.consistent or status != "unsat":
            fail("affine contradiction is not inconsistent")
        check_event(context, node.get("progress_event"), kind=kind, source=system, after=0, target_sha256=None)
    elif kind == "empty_system":
        if system[0] != 0 or not affine.consistent or status != "sat" or assignment != ():
            fail("empty-system terminal is invalid")
        if node.get("progress_event") is not None:
            fail("empty zero-potential system cannot consume another event")
    elif kind == "drop_unconstrained_variables":
        certificate = node["certificate"]
        columns = tuple(value - 1 for value in certificate["columns"])
        actual = tuple(
            column for column in range(system[0]) if all(row[column] == 0 for row in system[1])
        )
        if columns != actual or not columns:
            fail("unconstrained-variable guard is invalid")
        offset = tuple(certificate["offset"])
        transform = tuple(tuple(row) for row in certificate["transform"])
        target = transform_system(system, offset, transform)
        if parse_system(certificate["target_system"]) != target or certificate["target_system_sha256"] != system_digest(target):
            fail("unconstrained-variable target is invalid")
        check_event(
            context,
            node.get("progress_event"),
            kind=kind,
            source=system,
            after=target[0] ** 2,
            target_sha256=system_digest(target),
        )
        child_status, child_assignment, _ = verify_node(node["child"], target, context)
        expected_assignment = None if child_assignment is None else lift(offset, transform, child_assignment)
        if status != child_status or assignment != expected_assignment:
            fail("unconstrained-variable lift/status disagrees")
    elif kind == "component_split":
        components = system_components(system)
        rows = node.get("components")
        if len(components) <= 1 or not isinstance(rows, list) or len(rows) != len(components):
            fail("component split is not exact and nontrivial")
        target_hash = digest([system_digest(child) for _, child in components])
        check_event(
            context,
            node.get("progress_event"),
            kind=kind,
            source=system,
            after=sum(child[0] ** 2 for _, child in components),
            target_sha256=target_hash,
        )
        statuses = []
        combined = [0] * system[0]
        for row, (columns, child_system) in zip(rows, components, strict=True):
            if row["columns"] != [value + 1 for value in columns]:
                fail("component column map is invalid")
            child_status, child_assignment, _ = verify_node(row["proof"], child_system, context)
            statuses.append(child_status)
            if child_assignment is not None:
                for column, value in zip(columns, child_assignment, strict=True):
                    combined[column] = value
        expected_status = "unsat" if "unsat" in statuses else ("unresolved" if "unresolved" in statuses else "sat")
        expected_assignment = tuple(combined) if expected_status == "sat" else None
        if status != expected_status or assignment != expected_assignment:
            fail("component conjunction status/assignment is invalid")
    elif kind == "sparse_boolean_witness":
        if not affine.consistent:
            fail("sparse witness uses an inconsistent affine profile")
        certificate = node["certificate"]
        strategy, ports, states = audit_attempts(
            certificate,
            system,
            affine,
            context,
            target_variables=None,
            terminal=True,
        )
        expected = sparse_boolean_witness(system, AuditLedger())
        if strategy != "sparse_witness" or ports is not None or states is not None:
            fail("sparse witness was not selected by its strategy")
        if expected is None:
            fail("sparse witness guard is not applicable")
        expected_assignment, expected_certificate = expected
        for key, value in expected_certificate.items():
            if certificate.get(key) != value:
                fail(f"sparse witness certificate disagrees on {key}")
        if status != "sat" or assignment != expected_assignment:
            fail("sparse witness assignment/status is invalid")
        check_event(
            context,
            node.get("progress_event"),
            kind=kind,
            source=system,
            after=0,
            target_sha256=None,
        )
    elif kind == "bounded_nullity_enumeration":
        if not affine.consistent:
            fail("bounded terminal uses inconsistent affine profile")
        certificate = node["certificate"]
        strategy, ports, states = audit_attempts(
            certificate,
            system,
            affine,
            context,
            target_variables=None,
            terminal=True,
        )
        if strategy != "bounded_nullity" or ports is not None or states is not None:
            fail("bounded terminal was not selected by its strategy")
        expected_status, expected_assignment, checked = bounded_terminal(system, affine, context.cap, context.ledger)
        expected_fields = {
            "kind": kind,
            "terminal_nullity_cap": context.cap,
            "rank": affine.rank,
            "nullity": affine.nullity,
            "pivot_columns": [value + 1 for value in affine.pivots],
            "free_columns": [value + 1 for value in affine.free],
            "candidates_checked": checked,
            "candidate_bound": 1 << affine.nullity,
        }
        for key, value in expected_fields.items():
            if certificate.get(key) != value:
                fail(f"bounded terminal certificate disagrees on {key}")
        if (status, assignment) != (expected_status, expected_assignment):
            fail("bounded terminal outcome is invalid")
        check_event(context, node.get("progress_event"), kind=kind, source=system, after=0, target_sha256=None)
    elif kind == "empty_boolean_projection":
        certificate = node["certificate"]
        strategy, ports, states = audit_attempts(
            certificate,
            system,
            affine,
            context,
            target_variables=None,
            terminal=True,
        )
        recorded_ports = tuple(value - 1 for value in certificate["ports"])
        if ports != recorded_ports or states != () or certificate["allowed_states"] != []:
            fail("empty Boolean projection guard is invalid")
        if strategy not in ("forced_variable", "functional_pair") or status != "unsat":
            fail("empty projection terminal strategy/status is invalid")
        check_event(context, node.get("progress_event"), kind=kind, source=system, after=0, target_sha256=None)
    elif kind in ("forced_variable", "functional_pair"):
        certificate = node["certificate"]
        target = parse_system(certificate["target_system"])
        strategy, ports, states = audit_attempts(
            certificate,
            system,
            affine,
            context,
            target_variables=target[0],
            terminal=False,
        )
        if strategy != kind:
            fail("reduction node and selected strategy disagree")
        recorded_ports = tuple(value - 1 for value in certificate["ports"])
        recorded_states = tuple(tuple(row) for row in certificate["allowed_states"])
        if ports != recorded_ports or states != recorded_states or len(recorded_states) not in (1, 2):
            fail("affine reduction guard states are invalid")
        offset = tuple(certificate["offset"])
        transform = tuple(tuple(row) for row in certificate["transform"])
        if transform_system(system, offset, transform) != target:
            fail("affine reduction target is invalid")
        if certificate["target_system_sha256"] != system_digest(target):
            fail("affine reduction target digest is invalid")
        check_event(
            context,
            node.get("progress_event"),
            kind=kind,
            source=system,
            after=target[0] ** 2,
            target_sha256=system_digest(target),
        )
        child_status, child_assignment, _ = verify_node(node["child"], target, context)
        expected_assignment = None if child_assignment is None else lift(offset, transform, child_assignment)
        if status != child_status or assignment != expected_assignment:
            fail("affine reduction lift/status is invalid")
    elif kind == "literal_probe_witness":
        certificate = node["certificate"]
        strategy, ports, states = audit_attempts(
            certificate,
            system,
            affine,
            context,
            target_variables=None,
            terminal=True,
        )
        expected = bounded_literal_probe(system, AuditLedger())
        if (
            strategy != "literal_probe"
            or ports is not None
            or states is not None
            or expected is None
            or not expected["terminal"]
        ):
            fail("literal-probe witness strategy is invalid")
        expected_certificate = expected["certificate"]
        for key, value in expected_certificate.items():
            if certificate.get(key) != value:
                fail(f"literal-probe witness certificate disagrees on {key}")
        if status != "sat" or assignment != expected["assignment"]:
            fail("literal-probe witness assignment/status is invalid")
        check_event(
            context,
            node.get("progress_event"),
            kind=kind,
            source=system,
            after=0,
            target_sha256=None,
        )
    elif kind == "literal_probe_forcing":
        certificate = node["certificate"]
        target = parse_system(certificate["target_system"])
        strategy, ports, states = audit_attempts(
            certificate,
            system,
            affine,
            context,
            target_variables=target[0],
            terminal=False,
        )
        expected = bounded_literal_probe(system, AuditLedger())
        if expected is None or expected["terminal"]:
            fail("literal-probe forcing guard is not applicable")
        column = int(expected["column"])
        forced_value = int(expected["certificate"]["forced_value"])
        if (
            strategy != "literal_probe"
            or ports != (column,)
            or states != ((forced_value,),)
        ):
            fail("literal-probe forcing strategy selection is invalid")
        for key, value in expected["certificate"].items():
            if certificate.get(key) != value:
                fail(f"literal-probe forcing certificate disagrees on {key}")
        expected_offset = tuple(
            forced_value if index == column else 0
            for index in range(system[0])
        )
        survivors = tuple(index for index in range(system[0]) if index != column)
        expected_transform = tuple(
            tuple(int(old == survivor) for survivor in survivors)
            for old in range(system[0])
        )
        offset = tuple(certificate["offset"])
        transform = tuple(tuple(row) for row in certificate["transform"])
        if offset != expected_offset or transform != expected_transform:
            fail("literal-probe forcing substitution template is invalid")
        if transform_system(system, offset, transform) != target:
            fail("literal-probe forcing target is invalid")
        if certificate["target_system_sha256"] != system_digest(target):
            fail("literal-probe forcing target digest is invalid")
        check_event(
            context,
            node.get("progress_event"),
            kind=kind,
            source=system,
            after=target[0] ** 2,
            target_sha256=system_digest(target),
        )
        child_status, child_assignment, _ = verify_node(node["child"], target, context)
        expected_assignment = (
            None
            if child_assignment is None
            else lift(offset, transform, child_assignment)
        )
        if status != child_status or assignment != expected_assignment:
            fail("literal-probe forcing lift/status is invalid")
    elif kind == "nonnegative_row_bound":
        certificate = node["certificate"]
        target = parse_system(certificate["target_system"])
        strategy, ports, states = audit_attempts(
            certificate,
            system,
            affine,
            context,
            target_variables=target[0],
            terminal=False,
        )
        expected = nonnegative_row_bound(system, AuditLedger())
        if expected is None:
            fail("nonnegative row-bound guard is not applicable")
        column, expected_certificate = expected
        if strategy != "nonnegative_row_bound" or ports != (column,) or states != ((0,),):
            fail("nonnegative row-bound strategy selection is invalid")
        for key, value in expected_certificate.items():
            if certificate.get(key) != value:
                fail(f"nonnegative row-bound certificate disagrees on {key}")
        expected_offset = (0,) * system[0]
        survivors = tuple(index for index in range(system[0]) if index != column)
        expected_transform = tuple(
            tuple(int(old == survivor) for survivor in survivors)
            for old in range(system[0])
        )
        offset = tuple(certificate["offset"])
        transform = tuple(tuple(row) for row in certificate["transform"])
        if offset != expected_offset or transform != expected_transform:
            fail("nonnegative row-bound substitution template is invalid")
        if transform_system(system, offset, transform) != target:
            fail("nonnegative row-bound target is invalid")
        if certificate["target_system_sha256"] != system_digest(target):
            fail("nonnegative row-bound target digest is invalid")
        check_event(
            context,
            node.get("progress_event"),
            kind=kind,
            source=system,
            after=target[0] ** 2,
            target_sha256=system_digest(target),
        )
        child_status, child_assignment, _ = verify_node(node["child"], target, context)
        expected_assignment = (
            None if child_assignment is None else lift(offset, transform, child_assignment)
        )
        if status != child_status or assignment != expected_assignment:
            fail("nonnegative row-bound lift/status is invalid")
    elif kind == "bounded_separator_relation":
        certificate = node["certificate"]
        target = parse_system(certificate["target_system"])
        strategy, ports, states = audit_attempts(
            certificate,
            system,
            affine,
            context,
            target_variables=target[0],
            terminal=False,
        )
        expected = bounded_separator_relation(system, context.cap, AuditLedger())
        if expected is None:
            fail("bounded separator relation is not applicable")
        expected_certificate = expected["certificate"]
        expected_ports = tuple(
            int(value) - 1
            for value in expected_certificate["separator_variables"]
        )
        expected_states = tuple(
            tuple(int(value) for value in state)
            for state in expected_certificate["feasible_separator_states"]
        )
        if (
            strategy != "bounded_separator_relation"
            or ports != expected_ports
            or states != expected_states
        ):
            fail("bounded separator strategy selection is invalid")
        expected_keys = set(expected_certificate) | {
            "strategy_order",
            "attempted",
            "target_system",
            "target_system_sha256",
        }
        if set(certificate) != expected_keys:
            fail("bounded separator certificate fields are invalid")
        for key, value in expected_certificate.items():
            if certificate.get(key) != value:
                fail(f"bounded separator certificate disagrees on {key}")
        if target != expected["target"]:
            fail("bounded separator relation target is invalid")
        if certificate["target_system_sha256"] != system_digest(target):
            fail("bounded separator relation target digest is invalid")
        check_event(
            context,
            node.get("progress_event"),
            kind=kind,
            source=system,
            after=target[0] ** 2,
            target_sha256=system_digest(target),
        )
        child_status, child_assignment, _ = verify_node(node["child"], target, context)
        expected_assignment = (
            None
            if child_assignment is None
            else lift_separator(system[0], certificate, child_assignment)
        )
        if status != child_status or assignment != expected_assignment:
            fail("bounded separator relation lift/status is invalid")
    elif kind == "unresolved_residual":
        if not affine.consistent or status != "unresolved":
            fail("unresolved residual has a truth claim or inconsistent source")
        certificate = node["certificate"]
        expected_attempt_count = len(
            context.field.order(
                affine.nullity,
                context.cap,
                context.schedule_mode,
                context.literal_probing,
            )
        )
        strategy, ports, states = audit_attempts(
            certificate,
            system,
            affine,
            context,
            target_variables=None,
            terminal=False,
        )
        if (
            ports is not None
            or states is not None
            or len(certificate["attempted"]) != expected_attempt_count
        ):
            fail("unresolved residual did not exhaust every finite rule")
        if strategy not in STRATEGIES or certificate.get("kind") != "finite_rule_set_exhausted":
            fail("unresolved residual certificate is malformed")
        check_event(context, node.get("progress_event"), kind=kind, source=system, after=0, target_sha256=None)
    else:
        fail(f"unsupported proof node kind: {kind!r}")

    if kind != "canonical_cache_hit":
        context.known[proof_sha256] = (system_digest(system), status, assignment)
    return status, assignment, proof_sha256


def check_progress(
    result: Mapping[str, Any],
    source: System,
) -> list[dict[str, Any]]:
    progress = result["progress"]
    events = progress["events"]
    if progress["potential_name"] != "active_residual_squared_variable_sum":
        fail("progress potential name is invalid")
    current = source[0] ** 2
    if progress["initial"] != current or progress["event_bound"] != current:
        fail("progress initial value/bound is invalid")
    for index, event in enumerate(events):
        if event["index"] != index or event["global_before"] != current:
            fail("progress event chain is discontinuous")
        before = event["component_before"]
        after = event["component_after"]
        if (
            isinstance(before, bool)
            or isinstance(after, bool)
            or not isinstance(before, int)
            or not isinstance(after, int)
        ):
            fail("progress event uses a noninteger potential")
        if not 0 <= after < before <= current:
            fail("progress event does not strictly descend")
        current = current - before + after
        if (
            event["global_after"] != current
            or event["decrement"] != before - after
        ):
            fail("progress event accounting is invalid")
    if current != 0 or progress["final"] != 0 or progress["event_count"] != len(events):
        fail("progress chain did not halt at zero")
    if progress["strictly_descending"] is not True:
        fail("progress summary is not strict")
    return events


def verify_algorithm(algorithm: Mapping[str, Any]) -> tuple[int, str, bool]:
    if algorithm.get("schema") != ALGORITHM_SCHEMA:
        fail("algorithm schema is invalid")
    body = dict(algorithm)
    sha256 = body.pop("descriptor_sha256", None)
    if sha256 != digest(body):
        fail("algorithm descriptor digest is invalid")
    profile = algorithm.get("profile")
    if not isinstance(profile, dict) or set(profile) != {
        "terminal_nullity",
        "schedule_mode",
        "literal_probing",
    }:
        fail("algorithm profile is invalid")
    cap = profile["terminal_nullity"]
    if isinstance(cap, bool) or not isinstance(cap, int) or not 0 <= cap <= 12:
        fail("terminal nullity is not a fixed bounded integer")
    schedule_mode = profile["schedule_mode"]
    if schedule_mode not in ("adaptive", "fixed"):
        fail("algorithm schedule mode is invalid")
    literal_probing = profile["literal_probing"]
    if not isinstance(literal_probing, bool):
        fail("algorithm literal-probing mode is invalid")
    if algorithm.get("profile_sha256") != digest(
        {"schema": ALGORITHM_SCHEMA, "profile": profile}
    ):
        fail("algorithm profile digest is invalid")
    rules = algorithm.get("rules", ())
    ids = [row["id"] for row in rules]
    if ids != [
        "drop_unconstrained_variables",
        "component_split",
        "sparse_witness",
        "bounded_nullity",
        "forced_variable",
        "functional_pair",
        "literal_probe",
        "nonnegative_row_bound",
        "bounded_separator_relation",
    ]:
        fail("algorithm finite rule list changed")
    literal_rule = rules[-3]
    if (
        "single-Boolean assumption" not in literal_rule.get("guard", "")
        or "probing never recurses" not in literal_rule.get("effect", "")
    ):
        fail("literal-probing rule semantics are missing")
    separator_rule = rules[-1]
    if (
        "one or two separator variables" not in separator_rule.get("guard", "")
        or "exact separator relation" not in separator_rule.get("effect", "")
    ):
        fail("bounded separator rule semantics are missing")
    schedule = algorithm.get("schedule", {})
    expected_role = (
        "adaptive_scheduler" if schedule_mode == "adaptive" else "observation_only"
    )
    if (
        schedule.get("kind") != "fresh invocation-local exact preference field"
        or schedule.get("mode") != schedule_mode
        or schedule.get("field_role") != expected_role
        or schedule.get("default_condition")
        != (
            "adaptive ordering is not the default unless a held-out exact-resource "
            "ablation protects completion and beats the fixed schedule"
        )
        or schedule.get("literal_probing")
        != ("bounded_nonrecursive" if literal_probing else "disabled")
        or schedule.get("persistent_advice") is not False
        or schedule.get("training_corpus") is not None
        or schedule.get("truth_authority")
        != "exact guards and proof checking only"
        or schedule.get("fallback") is not None
    ):
        fail("algorithm descriptor contains invalid scheduling authority")
    envelope = algorithm.get("conservative_cost_envelope", {})
    if envelope.get("projection_implementation") != (
        "exact zero/proportionality tests on one or two affine-coordinate "
        "vectors; no per-state elimination"
    ):
        fail("algorithm descriptor hides the projection fast path")
    if envelope.get("literal_probe_trials_per_residual") != "at most 2n":
        fail("algorithm descriptor hides the literal-probing bound")
    if envelope.get("literal_propagation") != (
        "deterministic affected-row work queue with exact integer interval bounds"
    ):
        fail("algorithm descriptor hides the propagation mechanism")
    if "unresolved_residual" not in algorithm.get("open_obligation", ""):
        fail("algorithm descriptor hides the completeness obligation")
    return cap, schedule_mode, literal_probing


def proof_node_count(proof: Mapping[str, Any]) -> int:
    count = 1
    if isinstance(proof.get("child"), Mapping):
        count += proof_node_count(proof["child"])
    for row in proof.get("components", ()):
        count += proof_node_count(row["proof"])
    return count


def all_proof_systems(proof: Mapping[str, Any]) -> Iterable[System]:
    yield parse_system(proof["system"])
    if isinstance(proof.get("child"), Mapping):
        yield from all_proof_systems(proof["child"])
    for row in proof.get("components", ()):
        yield from all_proof_systems(row["proof"])


def brute_truth(formula: Formula, ledger: AuditLedger) -> tuple[str, tuple[int, ...] | None, int]:
    checked = 0
    for assignment in itertools.product((0, 1), repeat=len(formula)):
        checked += 1
        ledger.exhaustive_assignments += 1
        if all(sum(assignment[value - 1] for value in row) == 1 for row in formula):
            return "sat", assignment, checked
    return "unsat", None, checked


def verify_result(
    result: Mapping[str, Any],
    formula: Formula,
    ledger: AuditLedger,
) -> dict[str, Any]:
    if result.get("schema") != RESULT_SCHEMA:
        fail("reduction result schema is invalid")
    body = dict(result)
    sha256 = body.pop("result_sha256", None)
    if sha256 != digest(body):
        fail("reduction result digest is invalid")
    if (
        [list(row) for row in formula] != result.get("formula")
        or result.get("formula_sha256") != formula_digest(formula)
    ):
        fail("reduction result formula is detached")
    cap, schedule_mode, literal_probing = verify_algorithm(result["algorithm"])
    source = system_from_formula(formula)
    if result.get("source_system_sha256") != system_digest(source):
        fail("reduction source system digest is invalid")
    events = check_progress(result, source)
    field = FieldAudit()
    context = ProofContext(
        events=events,
        cap=cap,
        field=field,
        ledger=ledger,
        schedule_mode=schedule_mode,
        literal_probing=literal_probing,
        known={},
        used_events=[],
    )
    status, assignment, _ = verify_node(result["proof"], source, context)
    if status != result.get("status") or (
        None if result.get("assignment") is None else tuple(result["assignment"])
    ) != assignment:
        fail("root proof and result outcome disagree")
    if (
        sorted(context.used_events) != list(range(len(events)))
        or context.used_events != list(range(len(events)))
    ):
        fail("proof does not consume progress events exactly once in order")
    if result.get("field_preference") != field.expected_inspection(
        cap,
        schedule_mode,
        literal_probing,
    ):
        fail("invocation-local preference field reconstruction disagrees")
    representation = result["representation"]
    systems = tuple(all_proof_systems(result["proof"]))
    observed_bits = max(
        (
            abs(value).bit_length()
            for system in systems
            for value in (*[item for row in system[1] for item in row], *system[2])
        ),
        default=0,
    )
    input_bits = max(
        (abs(value).bit_length() for value in (*[item for row in source[1] for item in row], *source[2])),
        default=0,
    )
    if representation.get("input_integer_bit_length") != input_bits:
        fail("input bit-length accounting is invalid")
    if representation.get("coefficient_bit_length_bound") != input_bits + 2 * source[0] + 1:
        fail("coefficient bit-length bound is invalid")
    if observed_bits > representation["observed_maximum_integer_bit_length"] or representation.get("bound_respected") is not True:
        fail("observed representation exceeds its reported accounting")
    if representation.get("proof_bytes") != len(canonical_json(result["proof"]).encode("utf-8")):
        fail("proof byte accounting is invalid")
    if representation.get("proof_nodes") != proof_node_count(result["proof"]):
        fail("proof-node accounting is invalid")
    if representation.get("cache_persistence") != "invocation_local_only":
        fail("cache escaped its invocation")
    production_ledger = result["resource_ledger"]
    if production_ledger.get("proof_nodes") != representation["proof_nodes"]:
        fail("proof-node resource ledger disagrees")
    if production_ledger.get("cache_hits") != representation["cache_hits"]:
        fail("cache resource ledger disagrees")
    if production_ledger.get("field_observations") != field.epoch:
        fail("field-observation ledger disagrees")
    if production_ledger.get("variable_guards_checked") != context.variable_guards:
        fail("variable-guard ledger disagrees")
    if production_ledger.get("pair_guards_checked") != context.pair_guards:
        fail("pair-guard ledger disagrees")
    if (
        production_ledger.get("sparse_witness_candidates")
        != context.sparse_witness_candidates
    ):
        fail("sparse-witness resource ledger disagrees")
    if production_ledger.get("literal_probe_trials") != context.literal_probe_trials:
        fail("literal-probe trial ledger disagrees")
    if (
        production_ledger.get("propagation_rows_checked")
        != context.propagation_rows_checked
    ):
        fail("literal-propagation row ledger disagrees")
    if (
        production_ledger.get("propagation_bound_checks")
        != context.propagation_bound_checks
    ):
        fail("literal-propagation bound ledger disagrees")
    if (
        production_ledger.get("propagation_assignments")
        != context.propagation_assignments
    ):
        fail("literal-propagation assignment ledger disagrees")
    if production_ledger.get("projection_states_checked") != sum(field.projections):
        fail("projection-state ledger disagrees")
    if production_ledger.get("projection_queries") != context.projection_fast_queries:
        fail("production projection-query ledger disagrees")
    if production_ledger.get("projection_fast_queries") != context.projection_fast_queries:
        fail("fast projection-query ledger disagrees")
    if (
        production_ledger.get("projection_vector_entries_checked")
        != context.projection_vector_entries_checked
    ):
        fail("projection vector-entry ledger disagrees")
    if production_ledger.get("rref_calls") != production_ledger.get("affine_profiles"):
        fail("production projection path used extra RREF calls")
    if production_ledger.get("row_bound_combinations") != context.row_bound_combinations:
        fail("row-bound combination ledger disagrees")
    if (
        production_ledger.get("row_bound_coefficient_updates")
        != context.row_bound_coefficient_updates
    ):
        fail("row-bound coefficient-update ledger disagrees")
    if (
        production_ledger.get("separator_candidates_checked")
        != context.separator_candidates_checked
    ):
        fail("separator candidate ledger disagrees")
    if (
        production_ledger.get("separator_components_checked")
        != context.separator_components_checked
    ):
        fail("separator component ledger disagrees")
    if (
        production_ledger.get("separator_relations_enumerated")
        != context.separator_relations_enumerated
    ):
        fail("separator relation ledger disagrees")
    if (
        production_ledger.get("separator_assignments_checked")
        != context.separator_assignments_checked
    ):
        fail("separator assignment ledger disagrees")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in production_ledger.values()):
        fail("production resource ledger has an invalid counter")
    assessment = result.get("assessment", {})
    if assessment.get("p_equals_np_claim") is not False:
        fail("result makes a P=NP claim")
    if status == "unresolved" and assessment.get("truth_claim") is not None:
        fail("unresolved result carries a truth claim")
    return {
        "status": status,
        "assignment": assignment,
        "cap": cap,
        "schedule_mode": schedule_mode,
        "literal_probing": literal_probing,
        "variable_guards": context.variable_guards,
        "pair_guards": context.pair_guards,
        "projection_states": sum(field.projections),
    }


def cubic_components(formula: Formula) -> tuple[Formula, ...]:
    size = len(formula)
    variable_rows = [set() for _ in range(size)]
    for row_index, row in enumerate(formula):
        for value in row:
            variable_rows[value - 1].add(row_index)
    seen: set[int] = set()
    result = []
    for start in range(size):
        if start in seen:
            continue
        variables: set[int] = set()
        rows: set[int] = set()
        stack = [start]
        while stack:
            variable = stack.pop()
            if variable in variables:
                continue
            variables.add(variable)
            seen.add(variable)
            for row in variable_rows[variable]:
                if row in rows:
                    continue
                rows.add(row)
                stack.extend(value - 1 for value in formula[row] if value - 1 not in variables)
        ordered = tuple(sorted(variables))
        relabel = {old + 1: new + 1 for new, old in enumerate(ordered)}
        result.append(
            canonical_formula(tuple(tuple(relabel[value] for value in formula[row]) for row in sorted(rows)))
        )
    return tuple(result)


def expected_unswitch_scan(formula: Formula) -> dict[str, Any]:
    candidates = two_switch_candidates(formula)
    identities = [
        {
            "formula_sha256": formula_digest(candidate),
            "operation": operation,
        }
        for candidate, operation in candidates
    ]
    disconnecting = []
    for candidate, operation in candidates:
        if connected(candidate):
            continue
        disconnecting.append(
            {
                "operation": operation,
                "formula": candidate,
                "formula_sha256": formula_digest(candidate),
                "components": cubic_components(candidate),
            }
        )
    return {
        "source_formula_sha256": formula_digest(formula),
        "source_variables": len(formula),
        "candidate_count": len(candidates),
        "candidate_stream_sha256": digest(identities),
        "disconnecting_candidate_count": len(disconnecting),
        "disconnecting_candidates": disconnecting,
    }


def verify_unswitch_scan(
    row: Mapping[str, Any],
    source: Formula,
    *,
    cap: int,
    schedule_mode: str,
    ledger: AuditLedger,
) -> list[tuple[Formula, Mapping[str, Any], str]]:
    expected = expected_unswitch_scan(source)
    for key in (
        "source_formula_sha256",
        "source_variables",
        "candidate_count",
        "candidate_stream_sha256",
        "disconnecting_candidate_count",
    ):
        if row.get(key) != expected[key]:
            fail(f"minimization unswitch scan disagrees on {key}")
    recorded = row.get("disconnecting_candidates")
    if not isinstance(recorded, list) or len(recorded) != len(
        expected["disconnecting_candidates"]
    ):
        fail("minimization disconnecting candidate population is invalid")
    unresolved: list[tuple[Formula, Mapping[str, Any], str]] = []
    for actual, rebuilt in zip(
        recorded,
        expected["disconnecting_candidates"],
        strict=True,
    ):
        candidate = canonical_formula(actual.get("formula", ()))
        if (
            candidate != rebuilt["formula"]
            or actual.get("formula_sha256") != rebuilt["formula_sha256"]
            or actual.get("operation") != rebuilt["operation"]
        ):
            fail("minimization disconnecting candidate is invalid")
        component_rows = actual.get("components")
        expected_components = rebuilt["components"]
        if not isinstance(component_rows, list) or len(component_rows) != len(
            expected_components
        ):
            fail("minimization component population is invalid")
        for component_row, component in zip(
            component_rows,
            expected_components,
            strict=True,
        ):
            if (
                canonical_formula(component_row.get("formula", ())) != component
                or component_row.get("formula_sha256") != formula_digest(component)
                or component_row.get("variables") != len(component)
                or component_row.get("connected") is not True
                or not connected(component)
            ):
                fail("minimization component identity is invalid")
            checked = verify_result(component_row["reduction"], component, ledger)
            if (
                checked["cap"] != cap
                or checked["schedule_mode"] != schedule_mode
            ):
                fail("minimization component uses a different reducer profile")
            if checked["status"] == "unresolved":
                unresolved.append(
                    (
                        component,
                        component_row["reduction"],
                        rebuilt["formula_sha256"],
                    )
                )
    return unresolved


def verify_minimization(
    row: Mapping[str, Any],
    hardest: Mapping[str, Any],
    *,
    cap: int,
    schedule_mode: str,
    ledger: AuditLedger,
) -> None:
    source = connected_chain(
        (
            canonical_formula(hardest["formula"]),
            SUPPORT_THREE_SAT,
        ),
        ((0, 1),),
    )
    if (
        row.get("method")
        != "exhaustive_single_two_switch_disconnect_and_component_selection"
        or row.get("source_formula_sha256") != formula_digest(source)
        or row.get("source_variables") != len(source)
        or row.get("source_connected") is not True
        or not connected(source)
    ):
        fail("connected minimization source or method is invalid")
    source_check = verify_result(row["source_reduction"], source, ledger)
    if (
        source_check["status"] != "unresolved"
        or source_check["cap"] != cap
        or source_check["schedule_mode"] != schedule_mode
    ):
        fail("connected minimization source is not an unresolved profile match")

    current = source
    selected_result_sha256 = row["source_reduction"]["result_sha256"]
    steps = row.get("steps")
    if not isinstance(steps, list):
        fail("connected minimization steps are invalid")
    for step in steps:
        targets = verify_unswitch_scan(
            step,
            current,
            cap=cap,
            schedule_mode=schedule_mode,
            ledger=ledger,
        )
        if not targets:
            fail("connected minimization continued after local irreducibility")
        target, target_result, candidate_sha256 = min(
            targets,
            key=lambda candidate: (
                len(candidate[0]),
                formula_digest(candidate[0]),
                candidate[2],
            ),
        )
        if (
            step.get("selected_candidate_formula_sha256") != candidate_sha256
            or step.get("selected_target_formula_sha256")
            != formula_digest(target)
            or len(target) >= len(current)
            or not connected(target)
        ):
            fail("connected minimization selected the wrong shrinking target")
        current = target
        selected_result_sha256 = target_result["result_sha256"]

    terminal_targets = verify_unswitch_scan(
        row["terminal_scan"],
        current,
        cap=cap,
        schedule_mode=schedule_mode,
        ledger=ledger,
    )
    if terminal_targets:
        fail("connected minimization stopped before exhausting its local method")
    final = canonical_formula(row["formula"])
    if (
        final != current
        or row.get("formula_sha256") != formula_digest(final)
        or row.get("variables") != len(final)
        or row.get("connected") is not True
        or not connected(final)
    ):
        fail("connected minimization final formula is invalid")
    verified = verify_result(row["reduction"], final, ledger)
    if (
        verified["status"] != "unresolved"
        or verified["cap"] != cap
        or verified["schedule_mode"] != schedule_mode
        or row.get("status") != "unresolved"
        or row["reduction"]["result_sha256"] != selected_result_sha256
    ):
        fail("minimized result is not the selected unresolved counterexample")
    if (
        row.get("irreducible_under_method") is not True
        or len(final) >= len(source)
        or "not globally minimum" not in row.get("scope", "")
    ):
        fail("connected minimization scope or irreducibility is invalid")

def reduction_metrics(result: Mapping[str, Any]) -> dict[str, Any]:
    attempts = [
        attempt
        for node in walk_nodes(result["proof"])
        for attempt in node.get("certificate", {}).get("attempted", ())
    ]
    ledger = result["resource_ledger"]
    return {
        "status": result["status"],
        "completed": result["status"] != "unresolved",
        "result_sha256": result["result_sha256"],
        "work_units": sum(ledger[field] for field in WORK_UNIT_FIELDS),
        "rule_attempts": len(attempts),
        "failed_rule_attempts": sum(
            not attempt["applicable"] for attempt in attempts
        ),
        "rref_calls": ledger["rref_calls"],
        "fraction_updates": ledger["fraction_updates"],
        "projection_queries": ledger["projection_queries"],
        "projection_states_checked": ledger["projection_states_checked"],
        "literal_probe_trials": ledger["literal_probe_trials"],
        "propagation_rows_checked": ledger["propagation_rows_checked"],
        "propagation_bound_checks": ledger["propagation_bound_checks"],
        "propagation_assignments": ledger["propagation_assignments"],
        "row_bound_combinations": ledger["row_bound_combinations"],
        "separator_candidates_checked": ledger["separator_candidates_checked"],
        "proof_bytes": result["representation"]["proof_bytes"],
        "reduction": result,
    }


def verify_schedule_ablation(
    row: Mapping[str, Any],
    specs: Sequence[tuple[str, str, Formula]],
    *,
    truth_by_formula: Mapping[str, str],
    cap: int,
    selected_schedule_mode: str,
    literal_probing: bool,
    ledger: AuditLedger,
) -> None:
    if (
        row.get("schema")
        != "cassifi.cubic-reduction-schedule-ablation.v1"
        or row.get("corpus") != "structured_held_out_only"
        or row.get("case_count") != len(specs)
    ):
        fail("schedule ablation identity is invalid")
    expected_stream = digest(
        [
            {"name": name, "formula_sha256": formula_digest(formula)}
            for name, _, formula in specs
        ]
    )
    if row.get("case_stream_sha256") != expected_stream:
        fail("schedule ablation case stream is invalid")
    profiles = row.get("profiles")
    if not isinstance(profiles, dict) or set(profiles) != {"adaptive", "fixed"}:
        fail("schedule ablation profiles are invalid")
    for mode in ("adaptive", "fixed"):
        profile_cap, profile_mode, profile_probing = verify_algorithm(profiles[mode])
        if (
            profile_cap != cap
            or profile_mode != mode
            or profile_probing != literal_probing
        ):
            fail("schedule ablation profile does not match its named mode")

    recorded_cases = row.get("cases")
    if not isinstance(recorded_cases, list) or len(recorded_cases) != len(specs):
        fail("schedule ablation case population is invalid")
    verified_rows: list[dict[str, Any]] = []
    for actual, (name, group, formula) in zip(
        recorded_cases,
        specs,
        strict=True,
    ):
        formula_sha256 = formula_digest(formula)
        truth_status = truth_by_formula[formula_sha256]
        if (
            actual.get("name") != name
            or actual.get("group") != group
            or actual.get("formula_sha256") != formula_sha256
            or actual.get("variables") != len(formula)
            or actual.get("truth_status") != truth_status
        ):
            fail("schedule ablation case identity is invalid")
        checked_modes: dict[str, dict[str, Any]] = {}
        for mode in ("adaptive", "fixed"):
            metrics = actual.get(mode)
            if not isinstance(metrics, dict) or "reduction" not in metrics:
                fail("schedule ablation mode metrics are missing")
            result = metrics["reduction"]
            if result.get("algorithm") != profiles[mode]:
                fail("schedule ablation result uses a detached profile")
            checked = verify_result(result, formula, ledger)
            if (
                checked["cap"] != cap
                or checked["schedule_mode"] != mode
                or checked["literal_probing"] != literal_probing
            ):
                fail("schedule ablation result profile is invalid")
            if checked["status"] in ("sat", "unsat") and checked["status"] != truth_status:
                fail("schedule ablation truth claim is invalid")
            expected_metrics = reduction_metrics(result)
            if metrics != expected_metrics:
                fail("schedule ablation exact-resource metrics disagree")
            checked_modes[mode] = expected_metrics
        verified_rows.append({"name": name, **checked_modes})

    aggregate_fields = (
        "work_units",
        "rule_attempts",
        "failed_rule_attempts",
        "rref_calls",
        "fraction_updates",
        "projection_queries",
        "projection_states_checked",
        "literal_probe_trials",
        "propagation_rows_checked",
        "propagation_bound_checks",
        "propagation_assignments",
        "row_bound_combinations",
        "separator_candidates_checked",
        "proof_bytes",
    )
    aggregates: dict[str, dict[str, Any]] = {}
    for mode in ("adaptive", "fixed"):
        statuses = Counter(item[mode]["status"] for item in verified_rows)
        aggregates[mode] = {
            "completed_cases": len(verified_rows) - statuses["unresolved"],
            "unresolved_cases": statuses["unresolved"],
            "statuses": dict(sorted(statuses.items())),
            **{
                field: sum(item[mode][field] for item in verified_rows)
                for field in aggregate_fields
            },
        }
    if row.get("aggregates") != aggregates:
        fail("schedule ablation aggregates disagree")

    fixed_only = [
        item["name"]
        for item in verified_rows
        if item["fixed"]["completed"] and not item["adaptive"]["completed"]
    ]
    adaptive_only = [
        item["name"]
        for item in verified_rows
        if item["adaptive"]["completed"] and not item["fixed"]["completed"]
    ]
    score_fields = (
        "unresolved_cases",
        "work_units",
        "failed_rule_attempts",
        "proof_bytes",
    )
    adaptive_score = [aggregates["adaptive"][field] for field in score_fields]
    fixed_score = [aggregates["fixed"][field] for field in score_fields]
    completion_protected = not fixed_only
    adaptive_benefit = completion_protected and adaptive_score < fixed_score
    selected = "adaptive" if adaptive_benefit else "fixed"
    expected_decision = {
        "metric_order": list(score_fields),
        "comparison": "lexicographic_completion_first_exact_resource_cost",
        "fixed_only_completions": fixed_only,
        "adaptive_only_completions": adaptive_only,
        "completion_protected": completion_protected,
        "adaptive_score": adaptive_score,
        "fixed_score": fixed_score,
        "adaptive_measured_benefit": adaptive_benefit,
        "selected_default_schedule_mode": selected,
        "default_field_role": (
            "adaptive_scheduler" if selected == "adaptive" else "observation_only"
        ),
    }
    if row.get("decision") != expected_decision:
        fail("schedule ablation decision is invalid")
    if selected != selected_schedule_mode:
        fail("canonical reducer schedule ignores its held-out ablation")
    if row.get("timing_policy") != (
        "wall clock is excluded from the canonical decision because it is "
        "not independently replayable; exact resource counters are primary"
    ):
        fail("schedule ablation timing policy is invalid")



def verify_inference_ablation(
    row: Mapping[str, Any],
    specs: Sequence[tuple[str, str, Formula]],
    *,
    truth_by_formula: Mapping[str, str],
    selected_algorithm: Mapping[str, Any],
    ledger: AuditLedger,
) -> str:
    """Reconstruct the cap/probing comparison and its exact-resource decision."""

    if (
        row.get("schema") != "cassifi.cubic-reduction-inference-ablation.v1"
        or row.get("corpus") != "complete_fixed_structured_and_random"
        or row.get("case_count") != len(specs)
    ):
        fail("inference ablation identity is invalid")
    expected_stream = digest(
        [
            {"name": name, "formula_sha256": formula_digest(formula)}
            for name, _, formula in specs
        ]
    )
    if row.get("case_stream_sha256") != expected_stream:
        fail("inference ablation case stream is invalid")

    profile_contracts = {
        "cap4_baseline": (4, "fixed", False),
        "cap5_baseline": (5, "fixed", False),
        "cap4_literal_probe": (4, "fixed", True),
    }
    profiles = row.get("profiles")
    if not isinstance(profiles, dict) or set(profiles) != set(profile_contracts):
        fail("inference ablation profiles are invalid")
    for profile_name, contract in profile_contracts.items():
        if verify_algorithm(profiles[profile_name]) != contract:
            fail("inference ablation profile does not match its name")

    recorded_cases = row.get("cases")
    if not isinstance(recorded_cases, list) or len(recorded_cases) != len(specs):
        fail("inference ablation case population is invalid")
    verified_rows: list[dict[str, Any]] = []
    for actual, (name, group, formula) in zip(recorded_cases, specs, strict=True):
        formula_sha256 = formula_digest(formula)
        truth_status = truth_by_formula[formula_sha256]
        if (
            actual.get("name") != name
            or actual.get("group") != group
            or actual.get("formula_sha256") != formula_sha256
            or actual.get("variables") != len(formula)
            or actual.get("truth_status") != truth_status
        ):
            fail("inference ablation case identity is invalid")
        checked_profiles: dict[str, dict[str, Any]] = {}
        for profile_name, contract in profile_contracts.items():
            metrics = actual.get(profile_name)
            if not isinstance(metrics, dict) or "reduction" not in metrics:
                fail("inference ablation profile metrics are missing")
            result = metrics["reduction"]
            if result.get("algorithm") != profiles[profile_name]:
                fail("inference ablation result uses a detached profile")
            checked = verify_result(result, formula, ledger)
            if (
                checked["cap"],
                checked["schedule_mode"],
                checked["literal_probing"],
            ) != contract:
                fail("inference ablation result profile is invalid")
            if checked["status"] in ("sat", "unsat") and checked["status"] != truth_status:
                fail("inference ablation truth claim is invalid")
            expected_metrics = reduction_metrics(result)
            if metrics != expected_metrics:
                fail("inference ablation exact-resource metrics disagree")
            checked_profiles[profile_name] = expected_metrics
        verified_rows.append({"name": name, **checked_profiles})

    aggregate_fields = (
        "work_units",
        "rule_attempts",
        "failed_rule_attempts",
        "rref_calls",
        "fraction_updates",
        "projection_queries",
        "projection_states_checked",
        "row_bound_combinations",
        "separator_candidates_checked",
        "literal_probe_trials",
        "propagation_rows_checked",
        "propagation_bound_checks",
        "propagation_assignments",
        "proof_bytes",
    )
    aggregates: dict[str, dict[str, Any]] = {}
    for profile_name in profile_contracts:
        statuses = Counter(item[profile_name]["status"] for item in verified_rows)
        aggregates[profile_name] = {
            "completed_cases": len(verified_rows) - statuses["unresolved"],
            "unresolved_cases": statuses["unresolved"],
            "statuses": dict(sorted(statuses.items())),
            **{
                field: sum(item[profile_name][field] for item in verified_rows)
                for field in aggregate_fields
            },
        }
    if row.get("aggregates") != aggregates:
        fail("inference ablation aggregates disagree")

    baseline = "cap4_baseline"
    score_fields = (
        "unresolved_cases",
        "work_units",
        "failed_rule_attempts",
        "proof_bytes",
    )
    baseline_only = {
        profile_name: [
            item["name"]
            for item in verified_rows
            if item[baseline]["completed"] and not item[profile_name]["completed"]
        ]
        for profile_name in profile_contracts
    }
    completion_gain = {
        profile_name: [
            item["name"]
            for item in verified_rows
            if item[profile_name]["completed"] and not item[baseline]["completed"]
        ]
        for profile_name in profile_contracts
    }
    eligible = [
        profile_name
        for profile_name in profile_contracts
        if not baseline_only[profile_name]
    ]
    scores = {
        profile_name: [aggregates[profile_name][field] for field in score_fields]
        for profile_name in profile_contracts
    }
    selected = min(eligible, key=lambda profile_name: (*scores[profile_name], profile_name))
    expected_decision = {
        "baseline_profile": baseline,
        "metric_order": list(score_fields),
        "comparison": "completion_protected_lexicographic_exact_resource_cost",
        "baseline_only_completions": baseline_only,
        "completion_gain_cases": completion_gain,
        "eligible_profiles": eligible,
        "scores": scores,
        "selected_default_profile_name": selected,
        "selected_default_profile": profiles[selected]["profile"],
    }
    if row.get("decision") != expected_decision:
        fail("inference ablation decision is invalid")
    if selected_algorithm != profiles[selected]:
        fail("canonical algorithm ignores the independently selected inference profile")
    if row.get("timing_policy") != (
        "wall clock is reported only outside the canonical receipt; "
        "independently replayable exact resource counters select the profile"
    ):
        fail("inference ablation timing policy is invalid")
    return selected


def verify(path: str | Path = RECEIPT) -> dict[str, Any]:
    receipt = json.loads(Path(path).read_text(encoding="utf-8"))
    if receipt.get("schema") != SCHEMA:
        fail("receipt schema is invalid")
    body = dict(receipt)
    receipt_sha256 = body.pop("receipt_sha256", None)
    if receipt_sha256 != digest(body):
        fail("receipt digest is invalid")
    cap, schedule_mode, literal_probing = verify_algorithm(receipt["algorithm"])
    random_rows, rebuilt_generation = random_specs(receipt["generation"])
    if rebuilt_generation != receipt["generation"]:
        fail("deterministic adversarial generation receipt disagrees")
    structured_rows, rebuilt_structured = structured_specs()
    if rebuilt_structured != receipt.get("structured_generation"):
        fail("structured held-out generation receipt disagrees")
    fixed_rows = fixed_specs()
    expected_specs = [*fixed_rows, *structured_rows, *random_rows]
    hashes = [formula_digest(formula) for _, _, formula in expected_specs]
    if len(set(hashes)) != len(hashes):
        fail("reconstructed corpus partitions overlap")
    cases = receipt.get("cases")
    if not isinstance(cases, list) or len(cases) != len(expected_specs):
        fail("receipt case population is invalid")
    ledger = AuditLedger(receipt_cases=len(cases))
    verified_rows: list[dict[str, Any]] = []
    for case, (name, group, formula) in zip(cases, expected_specs, strict=True):
        if case.get("name") != name or case.get("group") != group:
            fail("case identity/order disagrees with reconstruction")
        if canonical_formula(case.get("formula", ())) != formula:
            fail(f"case formula disagrees: {name}")
        if case.get("formula_sha256") != formula_digest(formula) or case.get("variables") != len(formula):
            fail("case formula identity accounting is invalid")
        if case.get("connected") != connected(formula):
            fail("case connectivity flag is invalid")
        truth_status, truth_witness, checked = brute_truth(formula, ledger)
        expected_truth = {
            "status": truth_status,
            "first_witness": None if truth_witness is None else list(truth_witness),
            "assignments_checked": checked,
        }
        if case.get("truth") != expected_truth:
            fail(f"case exhaustive truth disagrees: {name}")
        result_check = verify_result(case["reduction"], formula, ledger)
        if case["reduction"]["algorithm"] != receipt["algorithm"]:
            fail("case algorithm descriptor differs from receipt descriptor")
        if (
            result_check["cap"] != cap
            or result_check["schedule_mode"] != schedule_mode
            or result_check["literal_probing"] != literal_probing
        ):
            fail("case profile differs from receipt profile")
        if result_check["status"] in ("sat", "unsat") and result_check["status"] != truth_status:
            fail("case truth claim disagrees with exhaustive evaluation")
        unresolved_nodes = [
            node for node in walk_nodes(case["reduction"]["proof"]) if node["kind"] == "unresolved_residual"
        ]
        expected_residual = {
            "count": len(unresolved_nodes),
            "variable_counts": sorted(node["system"]["variable_count"] for node in unresolved_nodes),
            "maximum_variables": max((node["system"]["variable_count"] for node in unresolved_nodes), default=0),
            "system_sha256": sorted(node["system_sha256"] for node in unresolved_nodes),
        }
        if case.get("residual") != expected_residual:
            fail("case residual profile is invalid")
        score = [
            int(result_check["status"] == "unresolved"),
            expected_residual["maximum_variables"],
            case["reduction"]["resource_ledger"]["pair_guards_checked"],
            case["reduction"]["resource_ledger"]["projection_states_checked"],
            case["reduction"]["progress"]["event_count"],
        ]
        if case.get("hardness", {}).get("tuple") != score:
            fail("case hardness score is invalid")
        verified_rows.append({"case": case, "status": result_check["status"], "truth": truth_status})
    if receipt.get("case_stream_sha256") != digest(cases):
        fail("case stream digest is invalid")

    hardest = max(cases, key=lambda case: (*case["hardness"]["tuple"], case["formula_sha256"]))
    unresolved = [case for case in cases if case["reduction"]["status"] == "unresolved"]
    minimal = min(unresolved, key=lambda case: (case["variables"], case["formula_sha256"]))
    selection = receipt["selection"]
    if selection.get("hardest_case") != hardest["name"] or selection.get("minimal_observed_unresolved_case") != minimal["name"]:
        fail("adversarial selection is invalid")
    truth_by_formula = {
        row["case"]["formula_sha256"]: row["truth"] for row in verified_rows
    }
    selected_inference_profile = verify_inference_ablation(
        receipt["inference_ablation"],
        expected_specs,
        truth_by_formula=truth_by_formula,
        selected_algorithm=receipt["algorithm"],
        ledger=ledger,
    )
    verify_schedule_ablation(
        receipt["schedule_ablation"],
        structured_rows,
        truth_by_formula=truth_by_formula,
        cap=cap,
        selected_schedule_mode=schedule_mode,
        literal_probing=literal_probing,
        ledger=ledger,
    )
    verify_minimization(
        receipt["minimization"],
        hardest,
        cap=cap,
        schedule_mode=schedule_mode,
        ledger=ledger,
    )

    statuses = Counter(row["status"] for row in verified_rows)
    truths = Counter(row["truth"] for row in verified_rows)
    group_statuses = {
        group: dict(
            sorted(Counter(row["status"] for row in verified_rows if row["case"]["group"] == group).items())
        )
        for group in sorted({case["group"] for case in cases})
    }
    expected_summary = {
        "cases": len(cases),
        "fixed_cases": len(fixed_rows),
        "structured_heldout_cases": len(structured_rows),
        "seeded_random_cases": len(random_rows),
        "variables_minimum": min(case["variables"] for case in cases),
        "variables_maximum": max(case["variables"] for case in cases),
        "reduction_statuses": dict(sorted(statuses.items())),
        "truth_statuses": dict(sorted(truths.items())),
        "group_statuses": group_statuses,
        "truth_claim_mismatches": 0,
        "progress_failures": 0,
        "representation_bound_failures": 0,
        "persistent_adaptive_states": 0,
        "canonical_cache_hits": sum(
            case["reduction"]["representation"]["cache_hits"] for case in cases
        ),
        "hardest_formula_sha256": hardest["formula_sha256"],
        "hardest_score": hardest["hardness"]["tuple"],
        "minimal_observed_unresolved_variables": minimal["variables"],
        "minimal_observed_unresolved_sha256": minimal["formula_sha256"],
        "connected_minimization_reduction": (
            receipt["minimization"]["source_variables"]
            - receipt["minimization"]["variables"]
        ),
        "selected_schedule_mode": schedule_mode,
        "selected_inference_profile": selected_inference_profile,
    }
    if receipt.get("summary") != expected_summary:
        fail("receipt aggregate summary is invalid")
    if receipt.get("assessment", {}).get("p_equals_np") != "not_established":
        fail("receipt overstates the measured result")
    return {
        "schema": "cassifi.cubic-reduction-discovery-verification.v1",
        "status": "verified",
        "receipt_sha256": receipt_sha256,
        "algorithm_sha256": receipt["algorithm"]["descriptor_sha256"],
        "cases": len(cases),
        "unresolved_cases": len(unresolved),
        "proof_checking_resource_ledger": ledger.as_dict(),
    }


def walk_nodes(proof: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    yield proof
    child = proof.get("child")
    if isinstance(child, Mapping):
        yield from walk_nodes(child)
    for row in proof.get("components", ()):
        yield from walk_nodes(row["proof"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", type=Path, default=RECEIPT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(json.dumps(verify(args.receipt), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
