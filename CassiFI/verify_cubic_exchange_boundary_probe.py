"""Independently verify the cubic exchange-boundary receipt.

This verifier imports neither the boundary producer nor the admissible-cell
probe.  It rebuilds the frozen cubic formulas, exact rational kernel columns,
complete width-two basis censuses, exchange graphs, exclusive pair states, and
the exact common-basis kernel relation for every 01-to-10 boundary edge.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, NoReturn, Sequence

DEFAULT_RECEIPT = Path("_diag/cubic_exchange_boundary_probe.json")
SCHEMA = "cassifi.cubic-exchange-boundary-probe.v1"
MAX_BASIS_SUBSETS = 200_000

Formula = tuple[tuple[int, int, int], ...]
Vector = tuple[Fraction, ...]
Basis = tuple[int, ...]

PORT_NAMESPACE = "original variable columns, 1-based"
VERTEX_NAMESPACE = "zero-based indices into lexicographically sorted width-two bases"
STATES = ("00", "01", "10", "11")
TRUTH_STATES = frozenset(("01", "10"))

SUPPORT_THREE_SAT: Formula = (
    (1, 6, 3), (1, 3, 5), (1, 8, 2),
    (4, 6, 8), (4, 8, 5), (4, 3, 2),
    (7, 9, 5), (7, 9, 2), (7, 9, 6),
)
SUPPORT_THREE_UNSAT: Formula = (
    (1, 14, 11), (2, 1, 15), (3, 10, 5),
    (4, 8, 14), (5, 11, 7), (6, 12, 1),
    (7, 9, 2), (8, 15, 12), (9, 5, 6),
    (10, 13, 3), (11, 4, 8), (12, 3, 10),
    (13, 6, 4), (14, 7, 13), (15, 2, 9),
)
ALL_BASES_TERNARY_SAT: Formula = (
    (1, 2, 7), (1, 4, 10), (1, 6, 10),
    (2, 7, 9), (2, 11, 12), (3, 4, 11),
    (3, 6, 7), (3, 8, 12), (4, 9, 10),
    (5, 6, 11), (5, 8, 9), (5, 8, 12),
)
ALL_BASES_TERNARY_UNSAT: Formula = (
    (1, 3, 7), (1, 6, 12), (1, 7, 8),
    (2, 3, 6), (2, 10, 13), (2, 13, 15),
    (3, 4, 12), (4, 7, 9), (4, 11, 12),
    (5, 8, 10), (5, 11, 15), (5, 13, 14),
    (6, 9, 14), (8, 11, 14), (9, 10, 15),
)
GREEDY_EXCHANGE_TRAP_SAT: Formula = (
    (1, 2, 6), (1, 3, 5), (1, 3, 7),
    (2, 4, 6), (2, 4, 9), (3, 4, 5),
    (5, 8, 9), (6, 7, 8), (7, 8, 9),
)

FROZEN_FIXTURE_DIGESTS = {
    "hexagonal-prism": "0860a4706931c3b362a2f277b3cf6373ed2f90649bcee5330f2db556a68db33b",
    "support-three-sat": "c154b01433577cbad78ea942614b7fd3b3f6ff485802833df403787b9a08a1e4",
    "greedy-exchange-trap-sat": "9f323fccf0bbba8a11a14ccd3dd91bdcaf655ab2523b3ddd6dfda88a1c029e2a",
    "support-three-unsat": "8a270824bbf4bff4dffba3d8ad70f89a083a2a5ede4eedf85967e7c4ddba60d5",
    "all-bases-ternary-sat": "382752c3cc4a88fd9d9b5dc65a068165f8c6d29cb48e6c2374891f834aae7ff2",
    "all-bases-ternary-unsat": "4d3215ad1f61ea5db72a0128fa399d265ea5a93c943c2a638e49ea36292c99e7",
}


class VerificationError(ValueError):
    """Raised when a receipt disagrees with independent reconstruction."""


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
        if len(set(values)) != 3 or any(value < 1 or value > size for value in values):
            fail("formula row is not a distinct in-range triple")
        row = (values[0], values[1], values[2])
        rows.append(row)
        for value in row:
            occurrences[value - 1] += 1
    if any(count != 3 for count in occurrences):
        fail("formula is not cubic")
    return tuple(sorted(rows))


def digest(formula: Formula) -> str:
    return hashlib.sha256(
        json.dumps(formula, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def incidence_connected(formula: Formula) -> bool:
    size = len(formula)
    adjacency = [set() for _ in range(2 * size)]
    for row, clause in enumerate(formula):
        for variable in clause:
            node = size + variable - 1
            adjacency[row].add(node)
            adjacency[node].add(row)
    seen = {0}
    stack = [0]
    while stack:
        node = stack.pop()
        for target in adjacency[node]:
            if target not in seen:
                seen.add(target)
                stack.append(target)
    return len(seen) == 2 * size


def prism_formula(cycle_length: int) -> Formula:
    if cycle_length < 4 or cycle_length % 2:
        fail("invalid prism cycle length")
    half = cycle_length // 2
    top = {index: index // 2 + 1 for index in range(1, cycle_length, 2)}
    bottom = {
        index: half + index // 2 + 1
        for index in range(0, cycle_length, 2)
    }
    rows: list[tuple[int, int, int]] = []
    for index in range(0, cycle_length, 2):
        rows.append(
            (
                top[(index - 1) % cycle_length],
                top[(index + 1) % cycle_length],
                bottom[index],
            )
        )
    for index in range(1, cycle_length, 2):
        rows.append(
            (
                bottom[(index - 1) % cycle_length],
                bottom[(index + 1) % cycle_length],
                top[index],
            )
        )
    return canonical(rows)


def fixture_specs() -> tuple[tuple[str, str, Formula], ...]:
    specs = (
        ("hexagonal-prism", "planar-nullity-two-control", prism_formula(6)),
        ("support-three-sat", "sat-width-two-control", canonical(SUPPORT_THREE_SAT)),
        ("greedy-exchange-trap-sat", "sat-exchange-control", canonical(GREEDY_EXCHANGE_TRAP_SAT)),
        ("support-three-unsat", "unsat-width-two-control", canonical(SUPPORT_THREE_UNSAT)),
        ("all-bases-ternary-sat", "sat-no-width-two-control", canonical(ALL_BASES_TERNARY_SAT)),
        ("all-bases-ternary-unsat", "unsat-no-width-two-control", canonical(ALL_BASES_TERNARY_UNSAT)),
    )
    for name, _, formula in specs:
        if digest(formula) != FROZEN_FIXTURE_DIGESTS[name]:
            fail(f"{name}: frozen fixture digest changed")
    return specs


def rref(matrix: Sequence[Sequence[Fraction]]) -> tuple[list[list[Fraction]], tuple[int, ...]]:
    values = [list(row) for row in matrix]
    row_count = len(values)
    column_count = len(values[0]) if values else 0
    pivots: list[int] = []
    pivot_row = 0
    for column in range(column_count):
        source = next(
            (row for row in range(pivot_row, row_count) if values[row][column]),
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
        [Fraction(int(column in clause)) for column in range(1, size + 1)]
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
                tuple(Fraction(int(index == free_index)) for index in range(len(free)))
            )
        else:
            row = pivot_positions[column]
            vectors.append(tuple(-reduced[row][free_column] for free_column in free))
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
    rank, vectors = kernel_columns(formula)
    size = len(formula)
    nullity = size - rank
    subset_total = math.comb(size, nullity)
    if subset_total > MAX_BASIS_SUBSETS:
        fail("verifier encountered an unexpected basis cap")
    common: dict[str, Any] = {
        "rank": rank,
        "nullity": nullity,
        "basis_subsets_total": subset_total,
        "basis_subsets_checked": 0,
        "independent_ground_bases": 0,
        "width_two_basis_count": 0,
        "width_two_bases": [],
        "basis_maximum_support_histogram": {},
        "exact": False,
        "maximum_subsets": MAX_BASIS_SUBSETS,
    }
    if nullity == 0:
        return {
            **common,
            "status": "not_applicable",
            "reason": "zero_nullity",
            "basis_subsets_checked": 1,
            "independent_ground_bases": 1,
            "basis_maximum_support_histogram": {"0": 1},
            "exact": True,
        }
    histogram: Counter[int] = Counter()
    width_two: list[list[int]] = []
    independent = 0
    for selected in itertools.combinations(range(size), nullity):
        basis = tuple(vectors[index] for index in selected)
        if vector_rank(basis) != nullity:
            continue
        independent += 1
        width = max(
            sum(value != 0 for value in basis_coordinates(basis, vector))
            for vector in vectors
        )
        histogram[width] += 1
        if width <= 2:
            width_two.append([index + 1 for index in selected])
    return {
        **common,
        "status": "exact" if width_two else "not_applicable",
        "reason": "all_original_column_bases_enumerated" if width_two else "no_width_two_bases",
        "basis_subsets_checked": subset_total,
        "independent_ground_bases": independent,
        "width_two_basis_count": len(width_two),
        "width_two_bases": width_two,
        "basis_maximum_support_histogram": {
            str(width): histogram[width] for width in sorted(histogram)
        },
        "exact": True,
    }


def components(adjacency: Sequence[Sequence[int]], vertices: Sequence[int] | None = None) -> list[list[int]]:
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


def exchange_graph(raw_bases: Sequence[Sequence[int]], size: int) -> dict[str, Any]:
    bases = tuple(sorted(tuple(sorted(int(value) for value in basis)) for basis in raw_bases))
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
        "vertex_namespace": VERTEX_NAMESPACE,
        "vertices": [list(basis) for basis in bases],
        "vertex_count": len(bases),
        "edge_count": len(ordered_edges),
        "edges": [list(edge) for edge in ordered_edges],
        "adjacency": adjacency,
        "component_count": len(graph_components),
        "components": graph_components,
        "connected": len(graph_components) == 1,
        "isolated_vertices": [
            vertex for vertex, row in enumerate(adjacency) if not row
        ],
    }


def membership_signature(bases: Sequence[Basis], column: int) -> str:
    return "".join("1" if column in basis else "0" for basis in bases)


def state_signature(basis: Sequence[int], ports: tuple[int, int]) -> str:
    selected = set(basis)
    return f"{int(ports[0] in selected)}{int(ports[1] in selected)}"


def column_supports(formula: Formula) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(row + 1 for row, clause in enumerate(formula) if column in clause)
        for column in range(1, len(formula) + 1)
    )


def projective_key(vector: Sequence[Fraction]) -> Vector | None:
    first = next((value for value in vector if value), None)
    if first is None:
        return None
    return tuple(value / first for value in vector)


def analyze_pair(graph: dict[str, Any], size: int, ports: tuple[int, int]) -> dict[str, Any]:
    bases = tuple(tuple(int(value) for value in basis) for basis in graph["vertices"])
    states = tuple(state_signature(basis, ports) for basis in bases)
    counts = Counter(states)
    state_counts = {state: counts[state] for state in STATES}
    exclusive = (
        state_counts["00"] == 0
        and state_counts["11"] == 0
        and state_counts["01"] > 0
        and state_counts["10"] > 0
    )
    fibres: dict[str, Any] = {}
    for state in ("01", "10"):
        vertices = [vertex for vertex, value in enumerate(states) if value == state]
        fibre_components = components(graph["adjacency"], vertices)
        fibres[state] = {
            "vertices": vertices,
            "basis_count": len(vertices),
            "component_count": len(fibre_components),
            "components": fibre_components,
            "connected": bool(vertices) and len(fibre_components) == 1,
            "disconnected_witness": (
                {
                    "vertices": [fibre_components[0][0], fibre_components[1][0]],
                    "bases": [
                        list(bases[fibre_components[0][0]]),
                        list(bases[fibre_components[1][0]]),
                    ],
                }
                if len(fibre_components) > 1
                else None
            ),
        }
    cross_edges = [
        [left, right]
        for left, right in graph["edges"]
        if states[left] in TRUTH_STATES
        and states[right] in TRUTH_STATES
        and states[left] != states[right]
    ]
    signatures = {
        column: membership_signature(bases, column)
        for column in range(1, size + 1)
    }
    shadows: list[dict[str, Any]] = []
    for column in range(1, size + 1):
        if column in ports:
            continue
        for side, port in (("left", ports[0]), ("right", ports[1])):
            if signatures[column] == signatures[port]:
                shadows.append(
                    {
                        "column": column,
                        "matches": side,
                        "port": port,
                        "signature": signatures[column],
                    }
                )
    alternates: list[dict[str, Any]] = []
    if exclusive:
        target = states
        swapped = tuple(state[1] + state[0] for state in states)
        for alternate in itertools.combinations(range(1, size + 1), 2):
            if alternate == ports:
                continue
            alternate_states = tuple(state_signature(basis, alternate) for basis in bases)
            if alternate_states == target:
                orientation = "same"
            elif alternate_states == swapped:
                orientation = "swapped"
            else:
                continue
            alternates.append(
                {
                    "ports": list(alternate),
                    "orientation": orientation,
                    "signature_counts": {
                        state: alternate_states.count(state) for state in STATES
                    },
                }
            )
    full_components = graph["components"]
    return {
        "signature_counts": state_counts,
        "exclusive_truth_states": exclusive,
        "port_membership_signatures": {
            "left": signatures[ports[0]],
            "right": signatures[ports[1]],
        },
        "exchange": {
            "full_graph_connected": graph["connected"],
            "truth_fibres": fibres,
            "cross_state_edge_count": len(cross_edges),
            "cross_state_edges": cross_edges,
            "single_exchange_truth_flip": bool(cross_edges),
            "full_graph_disconnected_witness": (
                {
                    "vertices": [full_components[0][0], full_components[1][0]],
                    "bases": [
                        list(bases[full_components[0][0]]),
                        list(bases[full_components[1][0]]),
                    ],
                }
                if len(full_components) > 1
                else None
            ),
        },
        "auxiliary_column_shadows": shadows,
        "alternate_pair_partitions": alternates,
    }


def classify_pair(formula: Formula, graph: dict[str, Any], ports: tuple[int, int]) -> dict[str, Any]:
    family = analyze_pair(graph, len(formula), ports)
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
    exchange = family["exchange"]
    reasons: list[str] = []
    if not family["exclusive_truth_states"]:
        reasons.append("not_exclusive_truth_states")
    if not nonzero:
        reasons.append("zero_kernel_column")
    if parallel or pair_rank < 2:
        reasons.append("projectively_parallel_kernel_columns")
    if identical:
        reasons.append("identical_primal_incidence")
    if not exchange["full_graph_connected"]:
        reasons.append("exchange_graph_disconnected")
    if not all(exchange["truth_fibres"][state]["connected"] for state in ("01", "10")):
        reasons.append("truth_state_fibre_disconnected")
    if not exchange["single_exchange_truth_flip"]:
        reasons.append("no_single_exchange_truth_flip")
    if family["auxiliary_column_shadows"]:
        reasons.append("auxiliary_column_shadow")
    if family["alternate_pair_partitions"]:
        reasons.append("alternate_pair_partition")
    return {
        **family,
        "kernel_pair_rank": pair_rank,
        "kernel_projectively_parallel": parallel,
        "primal_column_supports": [
            list(supports[ports[0] - 1]), list(supports[ports[1] - 1])
        ],
        "primal_incidence_identical": identical,
        "rejection_reasons": reasons,
    }


def fraction_text(value: Fraction) -> str:
    return str(value)


def null_relation(vectors: Sequence[Vector]) -> tuple[Fraction, ...]:
    dimension = len(vectors[0])
    matrix = [
        [vectors[column][row] for column in range(len(vectors))]
        for row in range(dimension)
    ]
    reduced, pivots = rref(matrix)
    if len(pivots) != len(vectors) - 1:
        fail("boundary relation is not one-dimensional")
    free = next(column for column in range(len(vectors)) if column not in pivots)
    relation = [Fraction(0) for _ in vectors]
    relation[free] = Fraction(1)
    for row, pivot in enumerate(pivots):
        relation[pivot] = -reduced[row][free]
    first = next(value for value in relation if value)
    return tuple(value / first for value in relation)


def boundary_record(formula: Formula, ports: tuple[int, int]) -> dict[str, Any]:
    census = basis_census(formula)
    if not census["exact"]:
        fail("boundary fixture census is not exact")
    graph = exchange_graph(census["width_two_bases"], len(formula))
    classification = classify_pair(formula, graph, ports)
    if not classification["exclusive_truth_states"]:
        fail(f"{ports}: expected exclusive pair")
    _, vectors = kernel_columns(formula)
    states = tuple(state_signature(basis, ports) for basis in graph["vertices"])
    boundaries: list[dict[str, Any]] = []
    for left_vertex, right_vertex in graph["edges"]:
        left_state = states[left_vertex]
        right_state = states[right_vertex]
        if {left_state, right_state} != set(TRUTH_STATES):
            continue
        if left_state == "01":
            from_vertex, to_vertex = left_vertex, right_vertex
        else:
            from_vertex, to_vertex = right_vertex, left_vertex
        from_basis = tuple(graph["vertices"][from_vertex])
        to_basis = tuple(graph["vertices"][to_vertex])
        removed = tuple(sorted(set(from_basis) - set(to_basis)))
        added = tuple(sorted(set(to_basis) - set(from_basis)))
        common = tuple(sorted(set(from_basis) & set(to_basis)))
        if removed != (ports[1],) or added != (ports[0],):
            fail(f"{ports}: boundary edge is not the designated port swap")
        ordered_columns = common + ports
        relation = null_relation(
            tuple(vectors[column - 1] for column in ordered_columns)
        )
        relation_by_column = {
            str(column): fraction_text(coefficient)
            for column, coefficient in zip(ordered_columns, relation)
        }
        boundaries.append(
            {
                "edge": [left_vertex, right_vertex],
                "from_state": "01",
                "to_state": "10",
                "from_vertex": from_vertex,
                "to_vertex": to_vertex,
                "from_basis": list(from_basis),
                "to_basis": list(to_basis),
                "common_basis": list(common),
                "removed_column": ports[1],
                "added_column": ports[0],
                "symmetric_difference": list(ports),
                "ordered_relation_columns": list(ordered_columns),
                "kernel_relation": relation_by_column,
                "port_relation_coefficients_nonzero": (
                    relation_by_column[str(ports[0])] != "0"
                    and relation_by_column[str(ports[1])] != "0"
                ),
            }
        )
    return {
        "status": "exact",
        "formula": [list(clause) for clause in formula],
        "formula_sha256": digest(formula),
        "variables": len(formula),
        "ports": list(ports),
        "census": census,
        "exchange_graph": graph,
        "state_counts": classification["signature_counts"],
        "port_membership_signatures": classification["port_membership_signatures"],
        "truth_fibres": classification["exchange"]["truth_fibres"],
        "cross_state_edge_count": classification["exchange"]["cross_state_edge_count"],
        "boundary_edge_count": len(boundaries),
        "boundary_edges": boundaries,
        "auxiliary_column_shadows": classification["auxiliary_column_shadows"],
        "alternate_pair_partitions": classification["alternate_pair_partitions"],
        "kernel_pair_rank": classification["kernel_pair_rank"],
        "kernel_projectively_parallel": classification["kernel_projectively_parallel"],
        "primal_column_supports": classification["primal_column_supports"],
        "primal_incidence_identical": classification["primal_incidence_identical"],
        "rejection_reasons": classification["rejection_reasons"],
        "boundary_port_swap_identity": all(
            edge["removed_column"] == ports[1]
            and edge["added_column"] == ports[0]
            and edge["symmetric_difference"] == list(ports)
            for edge in boundaries
        ),
        "boundary_relation_identity": all(
            edge["port_relation_coefficients_nonzero"] for edge in boundaries
        ),
    }


def expected_receipt() -> dict[str, Any]:
    fixture_rows: list[dict[str, Any]] = []
    source_fixtures = 0
    applicable_fixtures = 0
    not_applicable_fixtures = 0
    candidate_pairs_total = 0
    candidate_pairs_attempted = 0
    candidate_pairs_checked = 0
    not_applicable_candidate_pairs = 0
    exclusive_pairs = 0
    boundary_edges = 0
    all_port_swaps = True
    all_relations_nonzero = True
    for name, role, formula in fixture_specs():
        source_fixtures += 1
        if not incidence_connected(formula):
            fail(f"{name}: frozen fixture is disconnected")
        pair_total = math.comb(len(formula), 2)
        candidate_pairs_total += pair_total
        census = basis_census(formula)
        if not census["exact"]:
            fail(f"{name}: frozen basis census is inconclusive")
        if census["status"] != "exact":
            not_applicable_fixtures += 1
            not_applicable_candidate_pairs += pair_total
            continue
        applicable_fixtures += 1
        graph = exchange_graph(census["width_two_bases"], len(formula))
        candidate_ports = tuple(
            itertools.combinations(range(1, len(formula) + 1), 2)
        )
        classifications = [
            classify_pair(formula, graph, ports) for ports in candidate_ports
        ]
        candidate_pairs_attempted += len(classifications)
        candidate_pairs_checked += len(classifications)
        exclusive = [
            ports
            for ports, row in zip(candidate_ports, classifications)
            if row["exclusive_truth_states"]
        ]
        if not exclusive:
            continue
        boundaries = [boundary_record(formula, ports) for ports in exclusive]
        for row in boundaries:
            exclusive_pairs += 1
            boundary_edges += row["boundary_edge_count"]
            all_port_swaps = all_port_swaps and row["boundary_port_swap_identity"]
            all_relations_nonzero = (
                all_relations_nonzero and row["boundary_relation_identity"]
            )
        fixture_rows.append(
            {
                "name": name,
                "role": role,
                "formula": [list(clause) for clause in formula],
                "formula_sha256": digest(formula),
                "variables": len(formula),
                "census": census,
                "exclusive_pairs": [list(pair) for pair in exclusive],
                "boundary_records": boundaries,
            }
        )
    pair_scan_complete = (
        candidate_pairs_attempted == candidate_pairs_checked
        and candidate_pairs_total
        == candidate_pairs_checked + not_applicable_candidate_pairs
    )
    result = (
        "boundary_identity_verified_on_frozen_exclusive_pairs"
        if (
            pair_scan_complete
            and exclusive_pairs > 0
            and boundary_edges > 0
            and all_port_swaps
            and all_relations_nonzero
        )
        else "inconclusive_boundary_identity"
    )
    return {
        "schema": SCHEMA,
        "definition": {
            "port_namespace": PORT_NAMESPACE,
            "vertex_namespace": VERTEX_NAMESPACE,
            "boundary_edge": "an exchange-graph edge whose endpoint states are 01 and 10 for one exclusive pair",
            "boundary_orientation": "each boundary edge is normalized from state 01 to state 10; the right port is removed and the left port is added",
            "kernel_relation": "the unique exact dependence among the common basis columns and the two exchanged port columns, normalized by its first nonzero coefficient",
            "scope": "finite exchange-boundary measurement on the frozen exclusive pairs; it does not claim that a boundary edge causes a global auxiliary shadow or alternate partition",
        },
        "frozen_domain": {
            "fixture_names": [name for name, _, _ in fixture_specs()],
            "fixture_sha256": FROZEN_FIXTURE_DIGESTS,
            "exclusive_pair_source": "all original-column pairs are reconstructed and filtered by the exclusive 01/10 state predicate",
            "candidate_pair_accounting": "total counts every original-column pair in the frozen fixtures; attempted and checked count only exact width-two fixtures; pairs in exact no-width-two fixtures are not applicable",
        },
        "fixtures": fixture_rows,
        "summary": {
            "source_fixtures": source_fixtures,
            "applicable_fixtures": applicable_fixtures,
            "not_applicable_fixtures": not_applicable_fixtures,
            "candidate_pairs_total": candidate_pairs_total,
            "candidate_pairs_attempted": candidate_pairs_attempted,
            "candidate_pairs_checked": candidate_pairs_checked,
            "not_applicable_candidate_pairs": not_applicable_candidate_pairs,
            "candidate_pair_scan_complete": pair_scan_complete,
            "fixtures_with_exclusive_pairs": len(fixture_rows),
            "exclusive_pairs": exclusive_pairs,
            "boundary_edges": boundary_edges,
            "all_boundary_port_swaps": all_port_swaps,
            "all_boundary_relations_nonzero": all_relations_nonzero,
        },
        "assessment": {
            "result": result,
            "scope": "five exclusive pairs in the six frozen connected cubic controls",
            "interpretation": "the boundary identity is verified on the frozen pairs; this does not prove a universal exchange-boundary theorem",
            "global_admissible_cell_theorem": "not established",
        },
    }


def compare(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        fail(f"{label} mismatch")


def verify(path: str | Path = DEFAULT_RECEIPT) -> dict[str, Any]:
    try:
        receipt = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read receipt: {error}")
    expected = expected_receipt()
    compare(receipt, expected, "receipt")
    return {
        "status": "verified",
        "schema": SCHEMA,
        "candidate_pairs_checked": expected["summary"]["candidate_pairs_checked"],
        "not_applicable_candidate_pairs": expected["summary"][
            "not_applicable_candidate_pairs"
        ],
        "exclusive_pairs": expected["summary"]["exclusive_pairs"],
        "boundary_edges": expected["summary"]["boundary_edges"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", type=Path, default=DEFAULT_RECEIPT)
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.receipt), sort_keys=True))


if __name__ == "__main__":
    main()
