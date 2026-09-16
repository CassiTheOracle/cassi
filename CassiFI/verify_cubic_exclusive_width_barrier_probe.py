"""Independently reconstruct and verify the cubic width-barrier search receipt.

This verifier uses only the Python standard library.  It locally rebuilds the
frozen formulas, legal switches, deterministic random corpus, exact rational
kernels, complete ground-basis censuses, width-two families, all-pair
classifications, synthetic predicate controls, aggregates, and assessment.  It
imports neither the producer nor any production kernel, switch, or
admissibility implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, NoReturn, Sequence

DEFAULT_RECEIPT = Path("_diag/cubic_exclusive_width_barrier_probe.json")
SCHEMA = "cassifi.cubic-exclusive-width-barrier-probe.v1"
MAX_BASIS_SUBSETS = 200_000
RANDOM_SIZE = 12
RANDOM_ACCEPTED_DRAWS = 20_000
RANDOM_SEED = 0xE11B1E
PAIR_NAMESPACE = "one-based original variable-column numbers"
SWITCH_NAMESPACE = (
    "zero-based clause rows followed by one-based exchanged variable columns"
)
STATES = ("00", "01", "10", "11")
TRUTH_STATES = frozenset(("01", "10"))

Formula = tuple[tuple[int, int, int], ...]
Vector = tuple[Fraction, ...]
Basis = tuple[int, ...]
Ports = tuple[int, int]
Switch = tuple[int, int, int, int]

RANK_TWO_IDENTICAL_SUPPORT: Formula = (
    (1, 2, 12),
    (1, 6, 11),
    (1, 11, 12),
    (2, 3, 6),
    (2, 3, 12),
    (3, 8, 10),
    (4, 5, 9),
    (4, 6, 9),
    (4, 8, 10),
    (5, 7, 9),
    (5, 7, 11),
    (7, 8, 10),
)
DISTINCT_SUPPORT_PARALLEL: Formula = (
    (1, 4, 5),
    (1, 4, 11),
    (1, 6, 12),
    (2, 3, 10),
    (2, 4, 7),
    (2, 6, 7),
    (3, 5, 9),
    (3, 9, 11),
    (5, 8, 12),
    (6, 7, 9),
    (8, 10, 11),
    (8, 10, 12),
)
SEED_SPECS: tuple[tuple[str, Formula, tuple[Ports, ...]], ...] = (
    (
        "rank-two-identical-support",
        RANK_TWO_IDENTICAL_SUPPORT,
        ((8, 10),),
    ),
    (
        "distinct-support-parallel",
        DISTINCT_SUPPORT_PARALLEL,
        ((2, 9), (4, 6)),
    ),
)
FROZEN_SEED_DIGESTS = {
    "rank-two-identical-support": (
        "a08c300f3fcc70b791c37bd6e3999e0656f70b5efdc2d68e4b8da89c2642c859"
    ),
    "distinct-support-parallel": (
        "c26d0346c837aa4af28c0f4e687eff573ee441abbc3d340a3e7785e714bac37e"
    ),
}
EXPECTED_NEIGHBOR_SWITCH_ACCOUNTING = {
    "base_equivalent_specs": 16,
    "canonical_domain_formulas": 766,
    "distinct_nonbase_neighbors": 764,
    "duplicate_nonbase_specs": 80,
    "nonbase_switch_specs": 844,
    "raw_switch_specs": 860,
    "seed_formulas": 2,
}
EXPECTED_NEIGHBOR_SUMMARY = {
    "admissible_pairs": 0,
    "connected_formulas": 766,
    "disconnected_formulas": 0,
    "eligible_pairs": 0,
    "exact_census_formulas": 766,
    "exclusive_pairs": 343,
    "formulas_with_exclusive_pairs": 249,
    "formulas": 766,
    "inconclusive_formulas": 0,
    "no_width_two_formulas": 10,
    "nullity_two_all_bases_width_two": 497,
    "pair_cases_checked": 49_896,
    "pair_cases_inconclusive": 0,
    "pair_cases_not_applicable": 660,
    "pair_opportunities": 50_556,
    "rank_below_two_distinct": 162,
    "rank_below_two_identical": 0,
    "rank_dimension_excluded_formulas": 0,
    "rank_two_identical": 181,
    "width_two_formulas": 756,
}
EXPECTED_RANDOM_SUMMARY = {
    "accepted_draws": 20_000,
    "admissible_pairs": 0,
    "census_attempted_formulas": 2_853,
    "configuration_attempts": 490_819,
    "connected_formulas": 19_993,
    "disconnected_formulas": 7,
    "duplicate_draws": 0,
    "eligible_pairs": 0,
    "exact_census_formulas": 2_853,
    "exclusive_pairs": 252,
    "formulas": 20_000,
    "formulas_with_exclusive_pairs": 195,
    "inconclusive_formulas": 0,
    "no_width_two_formulas": 11,
    "nullity_two_all_bases_width_two": 2_714,
    "pair_cases_checked": 187_572,
    "pair_cases_inconclusive": 0,
    "pair_cases_not_applicable": 726,
    "pair_opportunities_connected": 1_319_538,
    "pair_opportunities_disconnected": 462,
    "pair_opportunities_rank_dimension_excluded": 1_131_240,
    "rank_below_two_distinct": 49,
    "rank_below_two_identical": 118,
    "rank_dimension_excluded_formulas": 17_140,
    "rank_two_identical": 85,
    "unique_formulas": 20_000,
    "width_two_formulas": 2_842,
}
EXPECTED_RANDOM_NULLITY_HISTOGRAM = {
    "0": 6_202,
    "1": 10_938,
    "2": 2_714,
    "3": 138,
    "4": 1,
}
SYNTHETIC_BARRIER_VECTORS = (
    (0, 0, 1),
    (0, 1, -1),
    (0, 1, 0),
    (1, -1, -1),
    (1, -1, 0),
    (1, 0, -1),
)
SYNTHETIC_BARRIER_PORTS = (1, 6)
SYNTHETIC_NO_BARRIER_VECTORS = (
    (1, 0),
    (0, 1),
    (1, 1),
    (1, -1),
)
SYNTHETIC_NO_BARRIER_PORTS = (1, 2)


class VerificationError(ValueError):
    """Raised when the receipt disagrees with independent reconstruction."""


def fail(message: str) -> NoReturn:
    raise VerificationError(message)


def canonical(formula: Sequence[Sequence[int]]) -> Formula:
    size = len(formula)
    if size < 3:
        fail("formula is too small")
    occurrences = [0] * size
    rows: list[tuple[int, int, int]] = []
    for raw in formula:
        if len(raw) != 3:
            fail("formula row is not a triple")
        values = tuple(sorted(int(value) for value in raw))
        if len(set(values)) != 3 or any(
            value < 1 or value > size for value in values
        ):
            fail("formula row is not a distinct in-range triple")
        row = (values[0], values[1], values[2])
        rows.append(row)
        for value in row:
            occurrences[value - 1] += 1
    if any(count != 3 for count in occurrences):
        fail("formula is not cubic")
    return tuple(sorted(rows))


def incidence_connected(formula: Formula) -> bool:
    size = len(formula)
    adjacency = [set() for _ in range(2 * size)]
    for row, clause in enumerate(formula):
        for variable in clause:
            target = size + variable - 1
            adjacency[row].add(target)
            adjacency[target].add(row)
    seen = {0}
    stack = [0]
    while stack:
        vertex = stack.pop()
        for target in adjacency[vertex]:
            if target not in seen:
                seen.add(target)
                stack.append(target)
    return len(seen) == 2 * size


def rref(
    matrix: Sequence[Sequence[Fraction]],
) -> tuple[list[list[Fraction]], tuple[int, ...]]:
    values = [list(row) for row in matrix]
    row_count = len(values)
    column_count = len(values[0]) if values else 0
    pivots: list[int] = []
    pivot_row = 0
    for column in range(column_count):
        source = next(
            (
                row
                for row in range(pivot_row, row_count)
                if values[row][column]
            ),
            None,
        )
        if source is None:
            continue
        values[pivot_row], values[source] = values[source], values[pivot_row]
        scale = values[pivot_row][column]
        values[pivot_row] = [value / scale for value in values[pivot_row]]
        for row in range(row_count):
            if row == pivot_row:
                continue
            factor = values[row][column]
            if factor:
                values[row] = [
                    left - factor * right
                    for left, right in zip(values[row], values[pivot_row])
                ]
        pivots.append(column)
        pivot_row += 1
        if pivot_row == row_count:
            break
    return values, tuple(pivots)


def kernel_columns(formula: Formula) -> tuple[int, tuple[Vector, ...]]:
    size = len(formula)
    matrix = [
        [
            Fraction(int(column in clause))
            for column in range(1, size + 1)
        ]
        for clause in formula
    ]
    reduced, pivots = rref(matrix)
    free = tuple(column for column in range(size) if column not in pivots)
    free_positions = {column: index for index, column in enumerate(free)}
    pivot_positions = {column: index for index, column in enumerate(pivots)}
    vectors: list[Vector] = []
    for column in range(size):
        if column in free_positions:
            free_index = free_positions[column]
            vectors.append(
                tuple(
                    Fraction(int(index == free_index))
                    for index in range(len(free))
                )
            )
        else:
            row = pivot_positions[column]
            vectors.append(
                tuple(
                    -reduced[row][free_column] for free_column in free
                )
            )
    return len(pivots), tuple(vectors)


def vector_rank(vectors: Sequence[Vector]) -> int:
    if not vectors:
        return 0
    matrix = [
        [vectors[column][row] for column in range(len(vectors))]
        for row in range(len(vectors[0]))
    ]
    return len(rref(matrix)[1])


def basis_coordinates(basis: Sequence[Vector], vector: Vector) -> Vector:
    dimension = len(basis)
    if dimension == 0:
        if any(vector):
            fail("nonzero vector has no zero-dimensional coordinates")
        return ()
    augmented = [
        [basis[column][row] for column in range(dimension)] + [vector[row]]
        for row in range(dimension)
    ]
    reduced, pivots = rref(augmented)
    if pivots[:dimension] != tuple(range(dimension)):
        fail("basis coordinate solve is singular")
    return tuple(reduced[row][-1] for row in range(dimension))


def basis_census(formula: Formula) -> dict[str, Any]:
    matrix_rank, vectors = kernel_columns(formula)
    size = len(formula)
    nullity = size - matrix_rank
    subset_total = math.comb(size, nullity)
    common: dict[str, Any] = {
        "rank": matrix_rank,
        "nullity": nullity,
        "basis_subsets_total": subset_total,
        "basis_subsets_checked": 0,
        "independent_ground_bases": 0,
        "width_two_basis_count": 0,
        "width_two_bases": [],
        "exact": False,
    }
    if nullity == 0:
        return {
            **common,
            "status": "not_applicable",
            "reason": "zero_nullity",
            "basis_subsets_checked": 1,
            "independent_ground_bases": 1,
            "exact": True,
        }
    if subset_total > MAX_BASIS_SUBSETS:
        return {
            **common,
            "status": "inconclusive",
            "reason": "basis_subset_cap",
        }
    independent_count = 0
    width_two: list[list[int]] = []
    for selected in itertools.combinations(range(size), nullity):
        basis = tuple(vectors[index] for index in selected)
        if vector_rank(basis) != nullity:
            continue
        independent_count += 1
        width = max(
            sum(value != 0 for value in basis_coordinates(basis, vector))
            for vector in vectors
        )
        if width <= 2:
            width_two.append([index + 1 for index in selected])
    return {
        **common,
        "status": "exact" if width_two else "not_applicable",
        "reason": (
            "all_original_column_bases_enumerated"
            if width_two
            else "no_width_two_bases"
        ),
        "basis_subsets_checked": subset_total,
        "independent_ground_bases": independent_count,
        "width_two_basis_count": len(width_two),
        "width_two_bases": width_two,
        "exact": True,
    }


def components(
    adjacency: Sequence[Sequence[int]],
    vertices: Sequence[int] | None = None,
) -> list[list[int]]:
    remaining = set(range(len(adjacency)) if vertices is None else vertices)
    result: list[list[int]] = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        stack = [start]
        component = [start]
        while stack:
            vertex = stack.pop()
            for target in reversed(adjacency[vertex]):
                if target in remaining:
                    remaining.remove(target)
                    stack.append(target)
                    component.append(target)
        result.append(sorted(component))
    return result


def exchange_graph(
    raw_bases: Sequence[Sequence[int]],
    size: int,
) -> dict[str, Any]:
    bases = tuple(
        sorted(tuple(sorted(int(value) for value in basis)) for basis in raw_bases)
    )
    if len(set(bases)) != len(bases):
        fail("width-two basis list contains duplicates")
    index = {basis: vertex for vertex, basis in enumerate(bases)}
    universe = set(range(1, size + 1))
    edges: set[tuple[int, int]] = set()
    for vertex, basis in enumerate(bases):
        selected = set(basis)
        for removed in basis:
            for added in sorted(universe - selected):
                neighbor = tuple(sorted((selected - {removed}) | {added}))
                target = index.get(neighbor)
                if target is not None and vertex < target:
                    edges.add((vertex, target))
    ordered_edges = sorted(edges)
    adjacency: list[list[int]] = [[] for _ in bases]
    for left, right in ordered_edges:
        adjacency[left].append(right)
        adjacency[right].append(left)
    for row in adjacency:
        row.sort()
    graph_components = components(adjacency)
    return {
        "vertices": [list(basis) for basis in bases],
        "edges": [list(edge) for edge in ordered_edges],
        "adjacency": adjacency,
        "connected": len(graph_components) == 1,
    }


def state_signature(basis: Sequence[int], ports: Ports) -> str:
    selected = set(basis)
    return f"{int(ports[0] in selected)}{int(ports[1] in selected)}"


def membership_signature(bases: Sequence[Basis], column: int) -> str:
    return "".join("1" if column in basis else "0" for basis in bases)


def column_supports(formula: Formula) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(
            row + 1
            for row, clause in enumerate(formula)
            if column in clause
        )
        for column in range(1, len(formula) + 1)
    )


def projective_key(vector: Sequence[Fraction]) -> Vector | None:
    first = next((value for value in vector if value), None)
    if first is None:
        return None
    return tuple(value / first for value in vector)


def classify_admissible_pair(
    formula: Formula,
    graph: dict[str, Any],
    ports: Ports,
) -> dict[str, Any]:
    bases = tuple(tuple(basis) for basis in graph["vertices"])
    states = tuple(state_signature(basis, ports) for basis in bases)
    state_counts = {state: states.count(state) for state in STATES}
    exclusive = (
        state_counts["00"] == 0
        and state_counts["11"] == 0
        and state_counts["01"] > 0
        and state_counts["10"] > 0
    )
    fibres: dict[str, dict[str, bool]] = {}
    for state in TRUTH_STATES:
        vertices = [
            vertex for vertex, value in enumerate(states) if value == state
        ]
        fibres[state] = {
            "connected": bool(vertices)
            and len(components(graph["adjacency"], vertices)) == 1
        }
    cross_edges = [
        edge
        for edge in graph["edges"]
        if states[edge[0]] in TRUTH_STATES
        and states[edge[1]] in TRUTH_STATES
        and states[edge[0]] != states[edge[1]]
    ]
    signatures = {
        column: membership_signature(bases, column)
        for column in range(1, len(formula) + 1)
    }
    shadows = []
    for column in range(1, len(formula) + 1):
        if column in ports:
            continue
        for side, port in (("left", ports[0]), ("right", ports[1])):
            if signatures[column] == signatures[port]:
                shadows.append((column, side))
    alternates = []
    if exclusive:
        swapped = tuple(state[1] + state[0] for state in states)
        for alternate in itertools.combinations(range(1, len(formula) + 1), 2):
            if alternate == ports:
                continue
            alternate_states = tuple(
                state_signature(basis, alternate) for basis in bases
            )
            if alternate_states == states or alternate_states == swapped:
                alternates.append(alternate)
    _, vectors = kernel_columns(formula)
    supports = column_supports(formula)
    left = vectors[ports[0] - 1]
    right = vectors[ports[1] - 1]
    left_key = projective_key(left)
    right_key = projective_key(right)
    nonzero = left_key is not None and right_key is not None
    pair_rank = vector_rank((left, right))
    parallel = nonzero and left_key == right_key
    identical = supports[ports[0] - 1] == supports[ports[1] - 1]
    reasons: list[str] = []
    if not exclusive:
        reasons.append("not_exclusive_truth_states")
    if not nonzero:
        reasons.append("zero_kernel_column")
    if parallel or pair_rank < 2:
        reasons.append("projectively_parallel_kernel_columns")
    if identical:
        reasons.append("identical_primal_incidence")
    if not graph["connected"]:
        reasons.append("exchange_graph_disconnected")
    if not all(fibres[state]["connected"] for state in TRUTH_STATES):
        reasons.append("truth_state_fibre_disconnected")
    if not cross_edges:
        reasons.append("no_single_exchange_truth_flip")
    if shadows:
        reasons.append("auxiliary_column_shadow")
    if alternates:
        reasons.append("alternate_pair_partition")
    return {
        "admissible": not reasons,
        "rejection_reasons": reasons,
    }


def formula_digest(formula: Sequence[Sequence[int]]) -> str:
    rebuilt = canonical(formula)
    return hashlib.sha256(
        json.dumps(rebuilt, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def switch_specs(formula: Sequence[Sequence[int]]) -> list[Switch]:
    specs: list[Switch] = []
    for left_row, right_row in itertools.combinations(range(len(formula)), 2):
        left = set(formula[left_row])
        right = set(formula[right_row])
        for variable in sorted(left - right):
            for partner in sorted(right - left):
                specs.append((left_row, right_row, variable, partner))
    return specs


def apply_spec(formula: Sequence[Sequence[int]], spec: Switch) -> Formula:
    left_row, right_row, variable, partner = spec
    clauses = [list(clause) for clause in formula]
    clauses[left_row][clauses[left_row].index(variable)] = partner
    clauses[right_row][clauses[right_row].index(partner)] = variable
    return canonical(tuple(tuple(sorted(clause)) for clause in clauses))


def fraction_vectors(
    vectors: Sequence[Sequence[int]],
) -> tuple[Vector, ...]:
    return tuple(tuple(Fraction(value) for value in vector) for vector in vectors)


def vector_configuration_profile(
    raw_vectors: Sequence[Sequence[int]],
    ports: Ports,
) -> dict[str, Any]:
    vectors = fraction_vectors(raw_vectors)
    dimension = len(vectors[0])
    if any(len(vector) != dimension for vector in vectors):
        fail("synthetic vectors have inconsistent dimensions")
    if vector_rank(vectors) != dimension:
        fail("synthetic vectors do not span their ambient dimension")
    basis_rows: list[dict[str, Any]] = []
    for selected in itertools.combinations(range(len(vectors)), dimension):
        basis_vectors = tuple(vectors[index] for index in selected)
        if vector_rank(basis_vectors) != dimension:
            continue
        maximum_support = max(
            sum(
                coordinate != 0
                for coordinate in basis_coordinates(basis_vectors, vector)
            )
            for vector in vectors
        )
        basis = tuple(index + 1 for index in selected)
        basis_rows.append(
            {
                "basis": list(basis),
                "state": state_signature(basis, ports),
                "maximum_support": maximum_support,
                "width_two": maximum_support <= 2,
            }
        )
    state_profile: dict[str, Any] = {}
    for state in STATES:
        rows = [row for row in basis_rows if row["state"] == state]
        minimum = min((row["maximum_support"] for row in rows), default=None)
        witnesses = [
            row["basis"] for row in rows if row["maximum_support"] == minimum
        ]
        state_profile[state] = {
            "ordinary_basis_count": len(rows),
            "minimum_width": minimum,
            "minimum_witness": witnesses[0] if witnesses else None,
            "width_two_basis_count": sum(row["width_two"] for row in rows),
        }
    width_two_states = {
        row["state"] for row in basis_rows if row["width_two"]
    }
    pair_rank = vector_rank(
        (vectors[ports[0] - 1], vectors[ports[1] - 1])
    )
    ordinary_all_states = all(
        state_profile[state]["ordinary_basis_count"] > 0 for state in STATES
    )
    exclusive_width_two = width_two_states == set(TRUTH_STATES)
    two_sided_barrier = (
        ordinary_all_states
        and exclusive_width_two
        and state_profile["00"]["minimum_width"] > 2
        and state_profile["11"]["minimum_width"] > 2
    )
    return {
        "vectors": [list(vector) for vector in raw_vectors],
        "ports": list(ports),
        "dimension": dimension,
        "pair_rank": pair_rank,
        "ordinary_basis_count": len(basis_rows),
        "width_two_basis_count": sum(row["width_two"] for row in basis_rows),
        "width_two_bases": [
            row["basis"] for row in basis_rows if row["width_two"]
        ],
        "width_two_states": sorted(width_two_states),
        "state_profile": state_profile,
        "ordinary_all_states": ordinary_all_states,
        "exclusive_width_two": exclusive_width_two,
        "two_sided_width_barrier": two_sided_barrier,
    }


def synthetic_controls() -> dict[str, Any]:
    positive = vector_configuration_profile(
        SYNTHETIC_BARRIER_VECTORS,
        SYNTHETIC_BARRIER_PORTS,
    )
    negative = vector_configuration_profile(
        SYNTHETIC_NO_BARRIER_VECTORS,
        SYNTHETIC_NO_BARRIER_PORTS,
    )
    if (
        positive["pair_rank"] != 2
        or positive["ordinary_basis_count"] != 16
        or positive["width_two_basis_count"] != 4
        or positive["state_profile"]["00"]["minimum_width"] != 3
        or positive["state_profile"]["01"]["minimum_width"] != 2
        or positive["state_profile"]["10"]["minimum_width"] != 2
        or positive["state_profile"]["11"]["minimum_width"] != 3
        or not positive["two_sided_width_barrier"]
    ):
        fail("synthetic positive barrier anchor did not fire")
    if negative["pair_rank"] != 2 or negative["two_sided_width_barrier"]:
        fail("synthetic negative barrier anchor fired")
    return {
        "positive_general_vector_anchor": positive,
        "negative_all_bases_width_two_anchor": negative,
        "scope": (
            "predicate controls over rational vector configurations; neither "
            "anchor is claimed to be a cubic incidence kernel"
        ),
    }


def pair_profile(
    formula: Formula,
    bases: tuple[Basis, ...],
    vectors: tuple[Vector, ...],
) -> dict[str, Any]:
    size = len(formula)
    signatures: list[int] = []
    for column in range(1, size + 1):
        signature = 0
        for vertex, basis in enumerate(bases):
            if column in basis:
                signature |= 1 << vertex
        signatures.append(signature)
    supports = column_supports(formula)
    counts: Counter[str] = Counter(pair_cases_checked=math.comb(size, 2))
    exclusive_rows: list[dict[str, Any]] = []
    graph: dict[str, Any] | None = None
    for left, right in itertools.combinations(range(size), 2):
        left_signature = signatures[left]
        right_signature = signatures[right]
        both = (left_signature & right_signature).bit_count()
        state_counts = {
            "00": len(bases)
            - left_signature.bit_count()
            - right_signature.bit_count()
            + both,
            "01": right_signature.bit_count() - both,
            "10": left_signature.bit_count() - both,
            "11": both,
        }
        exclusive = (
            state_counts["00"] == 0
            and state_counts["11"] == 0
            and state_counts["01"] > 0
            and state_counts["10"] > 0
        )
        if not exclusive:
            continue
        counts["exclusive_pairs"] += 1
        pair_rank = vector_rank((vectors[left], vectors[right]))
        left_key = projective_key(vectors[left])
        right_key = projective_key(vectors[right])
        nonzero = left_key is not None and right_key is not None
        parallel = nonzero and left_key == right_key
        identical = supports[left] == supports[right]
        eligible = pair_rank == 2 and not identical
        if eligible:
            category = "eligible"
            counts["eligible_pairs"] += 1
            if graph is None:
                graph = exchange_graph(bases, size)
            classification = classify_admissible_pair(
                formula,
                graph,
                (left + 1, right + 1),
            )
            admissible_pair = classification["admissible"]
            rejection_reasons = classification["rejection_reasons"]
            if admissible_pair:
                counts["admissible_pairs"] += 1
        elif pair_rank == 2:
            category = "rank_two_identical"
            counts[category] += 1
            admissible_pair = False
            rejection_reasons = ["identical_primal_incidence"]
        elif identical:
            category = "rank_below_two_identical"
            counts[category] += 1
            admissible_pair = False
            rejection_reasons = [
                "rank_below_two",
                "identical_primal_incidence",
            ]
        else:
            category = "rank_below_two_distinct"
            counts[category] += 1
            admissible_pair = False
            rejection_reasons = ["rank_below_two"]
        exclusive_rows.append(
            {
                "ports": [left + 1, right + 1],
                "state_counts": state_counts,
                "kernel_columns_nonzero": nonzero,
                "kernel_pair_rank": pair_rank,
                "kernel_projectively_parallel": parallel,
                "primal_column_supports": [
                    list(supports[left]),
                    list(supports[right]),
                ],
                "primal_incidence_identical": identical,
                "category": category,
                "eligible": eligible,
                "ordinary_00_and_11_exist_by_duality": eligible,
                "two_sided_width_barrier": eligible,
                "admissible": admissible_pair,
                "rejection_reasons": rejection_reasons,
            }
        )
    return {
        "counts": {
            key: counts[key]
            for key in (
                "pair_cases_checked",
                "exclusive_pairs",
                "rank_below_two_distinct",
                "rank_below_two_identical",
                "rank_two_identical",
                "eligible_pairs",
                "admissible_pairs",
            )
        },
        "exclusive_pairs": exclusive_rows,
    }


def analyze_formula(formula: Formula, source: dict[str, Any]) -> dict[str, Any]:
    rebuilt = canonical(formula)
    size = len(rebuilt)
    common: dict[str, Any] = {
        "formula_sha256": formula_digest(rebuilt),
        "variables": size,
        "source": source,
        "pair_opportunities": math.comb(size, 2),
    }
    connected = incidence_connected(rebuilt)
    if not connected:
        return {**common, "connected": False, "status": "disconnected"}
    matrix_rank, vectors = kernel_columns(rebuilt)
    nullity = size - matrix_rank
    algebra = {
        **common,
        "connected": True,
        "rank": matrix_rank,
        "nullity": nullity,
    }
    if nullity < 2:
        return {
            **algebra,
            "status": "rank_dimension_excluded",
            "reason": "kernel_dimension_below_two",
        }
    census = basis_census(rebuilt)
    census_record = {
        "basis_subsets_total": census["basis_subsets_total"],
        "basis_subsets_checked": census["basis_subsets_checked"],
        "independent_ground_bases": census["independent_ground_bases"],
        "width_two_basis_count": census["width_two_basis_count"],
        "exact": census["exact"],
        "status": census["status"],
        "reason": census["reason"],
    }
    if not census["exact"]:
        return {
            **algebra,
            "status": "inconclusive",
            "census": census_record,
        }
    if nullity == 2 and (
        census["width_two_basis_count"] != census["independent_ground_bases"]
    ):
        fail("a two-dimensional kernel produced a basis above width two")
    if not census["width_two_bases"]:
        return {
            **algebra,
            "status": "not_applicable",
            "reason": "no_width_two_bases",
            "census": census_record,
        }
    bases = tuple(tuple(basis) for basis in census["width_two_bases"])
    return {
        **algebra,
        "status": "exact",
        "census": census_record,
        "pair_profile": pair_profile(rebuilt, bases, vectors),
    }


def summarize(rows: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter(formulas=len(rows))
    for row in rows:
        if not row["connected"]:
            counts["disconnected_formulas"] += 1
            continue
        counts["connected_formulas"] += 1
        status = row["status"]
        if status == "rank_dimension_excluded":
            counts["rank_dimension_excluded_formulas"] += 1
        elif status == "inconclusive":
            counts["inconclusive_formulas"] += 1
        else:
            counts["exact_census_formulas"] += 1
            if row["nullity"] == 2:
                counts["nullity_two_all_bases_width_two"] += 1
            if status == "not_applicable":
                counts["no_width_two_formulas"] += 1
            else:
                counts["width_two_formulas"] += 1
                pair_counts = row["pair_profile"]["counts"]
                counts.update(pair_counts)
                if pair_counts["exclusive_pairs"]:
                    counts["formulas_with_exclusive_pairs"] += 1
    for key in (
        "connected_formulas",
        "disconnected_formulas",
        "rank_dimension_excluded_formulas",
        "exact_census_formulas",
        "inconclusive_formulas",
        "width_two_formulas",
        "no_width_two_formulas",
        "nullity_two_all_bases_width_two",
        "pair_cases_checked",
        "exclusive_pairs",
        "rank_below_two_distinct",
        "rank_below_two_identical",
        "rank_two_identical",
        "eligible_pairs",
        "admissible_pairs",
        "formulas_with_exclusive_pairs",
    ):
        counts[key] += 0
    return dict(sorted(counts.items()))


def assert_seed(name: str, formula: Formula, ports_list: tuple[Ports, ...]) -> Formula:
    rebuilt = canonical(formula)
    if formula_digest(rebuilt) != FROZEN_SEED_DIGESTS[name]:
        fail(f"{name}: frozen seed digest changed")
    if not incidence_connected(rebuilt):
        fail(f"{name}: frozen seed is disconnected")
    census = basis_census(rebuilt)
    if not census["exact"] or not census["width_two_bases"]:
        fail(f"{name}: frozen seed lost its width-two census")
    expected = {
        "rank-two-identical-support": {(8, 10): (2, False, True)},
        "distinct-support-parallel": {
            (2, 9): (1, True, False),
            (4, 6): (1, True, False),
        },
    }
    _, vectors = kernel_columns(rebuilt)
    supports = column_supports(rebuilt)
    bases = tuple(tuple(basis) for basis in census["width_two_bases"])
    for ports in ports_list:
        states = [state_signature(basis, ports) for basis in bases]
        left_key = projective_key(vectors[ports[0] - 1])
        right_key = projective_key(vectors[ports[1] - 1])
        observed = (
            vector_rank((vectors[ports[0] - 1], vectors[ports[1] - 1])),
            left_key is not None
            and right_key is not None
            and left_key == right_key,
            supports[ports[0] - 1] == supports[ports[1] - 1],
        )
        if set(states) != set(TRUTH_STATES) or observed != expected[name][ports]:
            fail(f"{name} {ports}: frozen defect changed")
    return rebuilt


def neighbor_population() -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    formulas: dict[str, dict[str, Any]] = {}
    seed_digests: set[str] = set()
    neighbor_digests: set[str] = set()
    counts: Counter[str] = Counter()
    for name, raw_formula, ports_list in SEED_SPECS:
        formula = assert_seed(name, raw_formula, ports_list)
        base_digest = formula_digest(formula)
        seed_digests.add(base_digest)
        base = formulas.setdefault(
            base_digest,
            {"formula": formula, "is_seed": True, "sources": []},
        )
        base["is_seed"] = True
        base["sources"].append({"seed": name, "switch": None})
        specs = switch_specs(formula)
        counts["raw_switch_specs"] += len(specs)
        for spec in specs:
            left_row, right_row, variable, partner = spec
            left = set(formula[left_row])
            right = set(formula[right_row])
            if not (
                left_row < right_row
                and variable in left - right
                and partner in right - left
            ):
                fail(f"illegal or misoriented switch: {spec}")
            switched = apply_spec(formula, spec)
            digest = formula_digest(switched)
            if digest == base_digest:
                counts["base_equivalent_specs"] += 1
                continue
            counts["nonbase_switch_specs"] += 1
            neighbor_digests.add(digest)
            entry = formulas.setdefault(
                digest,
                {"formula": switched, "is_seed": False, "sources": []},
            )
            entry["sources"].append({"seed": name, "switch": list(spec)})
    counts["seed_formulas"] = len(seed_digests)
    counts["distinct_nonbase_neighbors"] = len(neighbor_digests)
    counts["duplicate_nonbase_specs"] = (
        counts["nonbase_switch_specs"] - len(neighbor_digests)
    )
    counts["canonical_domain_formulas"] = len(formulas)
    accounting = dict(sorted(counts.items()))
    if accounting != EXPECTED_NEIGHBOR_SWITCH_ACCOUNTING:
        fail("frozen neighbor switch accounting changed")
    return formulas, accounting


def build_neighbor_domain() -> dict[str, Any]:
    formulas, switch_accounting = neighbor_population()
    rows = [
        analyze_formula(
            formulas[digest]["formula"],
            {
                "kind": "frozen_seed_or_distance_one_neighbor",
                "is_seed": formulas[digest]["is_seed"],
                "sources": formulas[digest]["sources"],
            },
        )
        for digest in sorted(formulas)
    ]
    summary = summarize(rows)
    summary["pair_opportunities"] = sum(row["pair_opportunities"] for row in rows)
    summary["pair_cases_not_applicable"] = sum(
        row["pair_opportunities"]
        for row in rows
        if row["status"] == "not_applicable"
    )
    summary["pair_cases_inconclusive"] = sum(
        row["pair_opportunities"]
        for row in rows
        if row["status"] == "inconclusive"
    )
    summary = dict(sorted(summary.items()))
    if summary != EXPECTED_NEIGHBOR_SUMMARY:
        fail("frozen all-pair neighbor summary changed")
    return {
        "name": "frozen_distance_one_all_pairs",
        "scope": {
            "seed_formulas": [
                {
                    "name": name,
                    "formula": [list(clause) for clause in formula],
                    "formula_sha256": FROZEN_SEED_DIGESTS[name],
                    "designated_ports": [list(ports) for ports in ports_list],
                }
                for name, formula, ports_list in SEED_SPECS
            ],
            "include_seeds": True,
            "include_every_distinct_nonbase_neighbor": True,
            "evaluate_every_original_column_pair": True,
            "switch_namespace": SWITCH_NAMESPACE,
        },
        "switch_accounting": switch_accounting,
        "summary": summary,
        "formulas": rows,
    }


def random_simple_cubic_formula(
    rng: random.Random,
    size: int,
) -> tuple[Formula, int]:
    labels = list(range(1, size + 1))
    attempts = 0
    while True:
        attempts += 1
        permutations: list[list[int]] = []
        for _ in range(3):
            candidate = labels.copy()
            rng.shuffle(candidate)
            permutations.append(candidate)
        rows = tuple(
            sorted(
                tuple(
                    sorted(permutations[offset][row] for offset in range(3))
                )
                for row in range(size)
            )
        )
        if any(len(set(row)) != 3 for row in rows):
            continue
        if len(set(rows)) != size:
            continue
        return canonical(rows), attempts


def generate_random_corpus(
    accepted_draws: int = RANDOM_ACCEPTED_DRAWS,
    seed: int = RANDOM_SEED,
    size: int = RANDOM_SIZE,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    rng = random.Random(seed)
    formulas: dict[str, dict[str, Any]] = {}
    configuration_attempts = 0
    stream = hashlib.sha256()
    for draw_index in range(accepted_draws):
        formula, attempts = random_simple_cubic_formula(rng, size)
        configuration_attempts += attempts
        digest = formula_digest(formula)
        stream.update(f"{draw_index}:{attempts}:{digest}\n".encode("ascii"))
        entry = formulas.setdefault(
            digest,
            {
                "formula": formula,
                "first_draw_index": draw_index,
                "draw_multiplicity": 0,
            },
        )
        entry["draw_multiplicity"] += 1
    generation = {
        "variables": size,
        "accepted_draws": accepted_draws,
        "seed": seed,
        "configuration_attempts": configuration_attempts,
        "unique_formulas": len(formulas),
        "duplicate_draws": accepted_draws - len(formulas),
        "draw_stream_sha256": stream.hexdigest(),
        "draw_stream_record": "draw_index:configuration_attempts:formula_sha256\\n",
    }
    return formulas, generation


def build_random_domain(
    accepted_draws: int = RANDOM_ACCEPTED_DRAWS,
    seed: int = RANDOM_SEED,
    size: int = RANDOM_SIZE,
) -> dict[str, Any]:
    formulas, generation = generate_random_corpus(accepted_draws, seed, size)
    rows = [
        analyze_formula(
            formulas[digest]["formula"],
            {
                "kind": "deterministic_simple_configuration_model",
                "first_draw_index": formulas[digest]["first_draw_index"],
                "draw_multiplicity": formulas[digest]["draw_multiplicity"],
            },
        )
        for digest in sorted(formulas)
    ]
    summary = summarize(rows)
    summary.update(
        {
            "accepted_draws": generation["accepted_draws"],
            "configuration_attempts": generation["configuration_attempts"],
            "unique_formulas": generation["unique_formulas"],
            "duplicate_draws": generation["duplicate_draws"],
            "census_attempted_formulas": sum(
                row["connected"] and row["nullity"] >= 2 for row in rows
            ),
            "pair_opportunities_connected": sum(
                row["pair_opportunities"] for row in rows if row["connected"]
            ),
            "pair_opportunities_disconnected": sum(
                row["pair_opportunities"]
                for row in rows
                if not row["connected"]
            ),
            "pair_opportunities_rank_dimension_excluded": sum(
                row["pair_opportunities"]
                for row in rows
                if row["status"] == "rank_dimension_excluded"
            ),
            "pair_cases_not_applicable": sum(
                row["pair_opportunities"]
                for row in rows
                if row["status"] == "not_applicable"
            ),
            "pair_cases_inconclusive": sum(
                row["pair_opportunities"]
                for row in rows
                if row["status"] == "inconclusive"
            ),
        }
    )
    summary = dict(sorted(summary.items()))
    nullity_histogram = Counter(
        row["nullity"] for row in rows if row["connected"]
    )
    serialized_histogram = {
        str(key): nullity_histogram[key] for key in sorted(nullity_histogram)
    }
    if (
        accepted_draws == RANDOM_ACCEPTED_DRAWS
        and seed == RANDOM_SEED
        and size == RANDOM_SIZE
    ):
        if summary != EXPECTED_RANDOM_SUMMARY:
            fail("frozen random corpus summary changed")
        if serialized_histogram != EXPECTED_RANDOM_NULLITY_HISTOGRAM:
            fail("frozen random nullity histogram changed")
    return {
        "name": "deterministic_simple_cubic_corpus",
        "scope": {
            "generator": (
                "three independently shuffled permutations; reject repeated "
                "variables within a row and duplicate clause rows"
            ),
            "connected_formula_requirement": True,
            "nullity_zero_or_one": (
                "rank-dimension excluded because no kernel-column pair can "
                "have rank two"
            ),
            "nullity_at_least_two": "complete exact ground-basis census",
            "stopping_rule": "scan every accepted draw",
            "distributional_claim": "none",
        },
        "generation": generation,
        "nullity_histogram_connected": serialized_histogram,
        "summary": summary,
        "formulas": rows,
    }


def expected_receipt() -> dict[str, Any]:
    controls = synthetic_controls()
    domains = [build_neighbor_domain(), build_random_domain()]
    eligible_pairs = sum(
        domain["summary"]["eligible_pairs"] for domain in domains
    )
    admissible_pairs = sum(
        domain["summary"]["admissible_pairs"] for domain in domains
    )
    result = (
        "eligible_cubic_width_barrier_found"
        if eligible_pairs
        else "no_eligible_pair_in_two_bounded_cubic_domains"
    )
    return {
        "schema": SCHEMA,
        "definitions": {
            "ground_basis": "a basis selected from the original kernel-coordinate columns",
            "basis_width": "maximum coordinate-support size of any original kernel column relative to the selected ground basis",
            "exclusive_pair": "the complete width-two basis family realizes only 01 and 10, with both states nonempty",
            "projective_parallel_convention": "true only for two nonzero columns with equal normalized projective keys; zero columns are tracked separately",
            "eligible_pair": "exclusive, kernel pair rank two, and distinct primal incidence columns; nonzero and nonparallel follow from rank two",
            "dual_basis_escape_lemma": "kernel pair rank two extends to an ordinary 11 ground basis; distinct nonzero equal-weight primal columns extend to a dual basis whose complement is an ordinary 00 ground basis",
            "two_sided_width_barrier": "ordinary 00 and 11 bases exist but every width-two ground basis has state 01 or 10",
            "pair_namespace": PAIR_NAMESPACE,
        },
        "synthetic_controls": controls,
        "domains": domains,
        "summary": {
            "bounded_domains": len(domains),
            "cubic_formulas": sum(domain["summary"]["formulas"] for domain in domains),
            "pair_cases_checked": sum(domain["summary"]["pair_cases_checked"] for domain in domains),
            "exclusive_pairs": sum(domain["summary"]["exclusive_pairs"] for domain in domains),
            "eligible_pairs": eligible_pairs,
            "admissible_pairs": admissible_pairs,
            "synthetic_positive_barrier_fires": controls["positive_general_vector_anchor"]["two_sided_width_barrier"],
            "synthetic_negative_barrier_rejected": not controls["negative_all_bases_width_two_anchor"]["two_sided_width_barrier"],
        },
        "assessment": {
            "result": result,
            "exclusive_pair_degeneracy_conjecture": "not established",
            "general_vector_impossibility": "falsified by synthetic anchor",
            "cubic_specific_impossibility": "not established",
            "p_equals_np": "not established",
            "scope": "complete only for the frozen distance-one all-pair domain and the deterministic 20,000-draw simple n=12 corpus",
        },
    }


def verify(path: str | Path = DEFAULT_RECEIPT) -> dict[str, Any]:
    receipt_path = Path(path)
    try:
        actual = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read receipt: {error}")
    expected = expected_receipt()
    if actual != expected:
        fail("receipt mismatch")
    return {
        "status": "verified",
        "schema": expected["schema"],
        **expected["summary"],
        "result": expected["assessment"]["result"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", default=str(DEFAULT_RECEIPT))
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.receipt), sort_keys=True))


if __name__ == "__main__":
    main()
