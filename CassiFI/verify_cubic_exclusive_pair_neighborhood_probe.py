"""Independently verify the exclusive-pair distance-one neighborhood receipt.

The verifier imports neither the neighborhood runner nor any production
admissibility, switch, or kernel implementation. It owns the frozen seed
formulas, switch enumeration, exact rational elimination, complete basis
censuses, exchange graphs, pair classifications, aggregates, and assessment.
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

DEFAULT_RECEIPT = Path("_diag/cubic_exclusive_pair_neighborhood_probe.json")
SCHEMA = "cassifi.cubic-exclusive-pair-neighborhood-probe.v1"
MAX_BASIS_SUBSETS = 200_000

Formula = tuple[tuple[int, int, int], ...]
Vector = tuple[Fraction, ...]
Basis = tuple[int, ...]
Ports = tuple[int, int]
Switch = tuple[int, int, int, int]

VERTEX_NAMESPACE = (
    "zero-based indices into lexicographically sorted width-two bases"
)
STATES = ("00", "01", "10", "11")
TRUTH_STATES = frozenset(("01", "10"))

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
        "maximum_subsets": MAX_BASIS_SUBSETS,
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
    raw_bases: Sequence[Sequence[int]], size: int
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
        "vertex_namespace": VERTEX_NAMESPACE,
        "vertices": [list(basis) for basis in bases],
        "edges": [list(edge) for edge in ordered_edges],
        "adjacency": adjacency,
        "connected": len(graph_components) == 1,
    }


def membership_signature(bases: Sequence[Basis], column: int) -> str:
    return "".join("1" if column in basis else "0" for basis in bases)


def state_signature(basis: Sequence[int], ports: Ports) -> str:
    selected = set(basis)
    return f"{int(ports[0] in selected)}{int(ports[1] in selected)}"


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


def analyze_pair(
    graph: dict[str, Any], size: int, ports: Ports
) -> dict[str, Any]:
    bases = tuple(
        tuple(int(value) for value in basis) for basis in graph["vertices"]
    )
    states = tuple(state_signature(basis, ports) for basis in bases)
    counts = Counter(states)
    state_counts = {state: counts[state] for state in STATES}
    exclusive = (
        state_counts["00"] == 0
        and state_counts["11"] == 0
        and state_counts["01"] > 0
        and state_counts["10"] > 0
    )
    fibres: dict[str, dict[str, Any]] = {}
    for state in ("01", "10"):
        vertices = [
            vertex for vertex, value in enumerate(states) if value == state
        ]
        fibre_components = components(graph["adjacency"], vertices)
        fibres[state] = {
            "connected": bool(vertices) and len(fibre_components) == 1,
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
    shadows: list[tuple[int, str]] = []
    for column in range(1, size + 1):
        if column in ports:
            continue
        for side, port in (("left", ports[0]), ("right", ports[1])):
            if signatures[column] == signatures[port]:
                shadows.append((column, side))
    alternates: list[tuple[int, int]] = []
    if exclusive:
        swapped = tuple(state[1] + state[0] for state in states)
        for alternate in itertools.combinations(range(1, size + 1), 2):
            if alternate == ports:
                continue
            alternate_states = tuple(
                state_signature(basis, alternate) for basis in bases
            )
            if alternate_states == states or alternate_states == swapped:
                alternates.append(alternate)
    return {
        "signature_counts": state_counts,
        "exclusive_truth_states": exclusive,
        "exchange": {
            "full_graph_connected": graph["connected"],
            "truth_fibres": fibres,
            "cross_state_edge_count": len(cross_edges),
            "single_exchange_truth_flip": bool(cross_edges),
        },
        "auxiliary_column_shadows": shadows,
        "alternate_pair_partitions": alternates,
    }


def classify_pair(
    formula: Formula, graph: dict[str, Any], ports: Ports
) -> dict[str, Any]:
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
    if not all(
        exchange["truth_fibres"][state]["connected"]
        for state in ("01", "10")
    ):
        reasons.append("truth_state_fibre_disconnected")
    if not exchange["single_exchange_truth_flip"]:
        reasons.append("no_single_exchange_truth_flip")
    if family["auxiliary_column_shadows"]:
        reasons.append("auxiliary_column_shadow")
    if family["alternate_pair_partitions"]:
        reasons.append("alternate_pair_partition")
    return {
        **family,
        "kernel_columns_nonzero": nonzero,
        "kernel_pair_rank": pair_rank,
        "kernel_projectively_parallel": parallel,
        "primal_column_supports": [
            list(supports[ports[0] - 1]),
            list(supports[ports[1] - 1]),
        ],
        "primal_incidence_identical": identical,
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
    try:
        clauses[left_row][clauses[left_row].index(variable)] = partner
        clauses[right_row][clauses[right_row].index(partner)] = variable
    except (IndexError, ValueError) as error:
        fail(f"invalid switch specification: {error}")
    return canonical(tuple(tuple(sorted(clause)) for clause in clauses))


def compact_census(census: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": census["status"],
        "reason": census["reason"],
        "exact": census["exact"],
        "maximum_subsets": census["maximum_subsets"],
        "rank": census["rank"],
        "nullity": census["nullity"],
        "basis_subsets_total": census["basis_subsets_total"],
        "basis_subsets_checked": census["basis_subsets_checked"],
        "independent_ground_bases": census["independent_ground_bases"],
        "width_two_basis_count": census["width_two_basis_count"],
    }


def compact_pair(classification: dict[str, Any], ports: Ports) -> dict[str, Any]:
    reasons = classification["rejection_reasons"]
    nonzero = "zero_kernel_column" not in reasons
    eligible = (
        classification["exclusive_truth_states"]
        and nonzero
        and classification["kernel_pair_rank"] == 2
        and not classification["kernel_projectively_parallel"]
        and not classification["primal_incidence_identical"]
    )
    exchange = classification["exchange"]
    return {
        "status": "exact",
        "ports": list(ports),
        "state_counts": classification["signature_counts"],
        "exclusive": classification["exclusive_truth_states"],
        "eligible": eligible,
        "admissible": not reasons,
        "kernel_columns_nonzero": nonzero,
        "kernel_pair_rank": classification["kernel_pair_rank"],
        "kernel_projectively_parallel": classification[
            "kernel_projectively_parallel"
        ],
        "primal_column_supports": classification["primal_column_supports"],
        "primal_incidence_identical": classification[
            "primal_incidence_identical"
        ],
        "full_exchange_graph_connected": exchange["full_graph_connected"],
        "truth_fibres_connected": {
            state: exchange["truth_fibres"][state]["connected"]
            for state in ("01", "10")
        },
        "cross_state_edge_count": exchange["cross_state_edge_count"],
        "single_exchange_truth_flip": exchange["single_exchange_truth_flip"],
        "auxiliary_column_shadow_count": len(
            classification["auxiliary_column_shadows"]
        ),
        "alternate_pair_partition_count": len(
            classification["alternate_pair_partitions"]
        ),
        "rejection_reasons": reasons,
    }


def unavailable_pair(ports: Ports, status: str, reason: str) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "ports": list(ports),
    }


def baseline_record(formula: Formula, ports_list: tuple[Ports, ...]) -> dict[str, Any]:
    census = basis_census(formula)
    if not census["exact"] or census["status"] != "exact":
        fail("frozen near-miss seed lacks an exact width-two census")
    graph = exchange_graph(census["width_two_bases"], len(formula))
    return {
        "census": compact_census(census),
        "pairs": [
            compact_pair(classify_pair(formula, graph, ports), ports)
            for ports in ports_list
        ],
    }


def neighbor_record(
    formula: Formula,
    representative: Switch,
    multiplicity: int,
    ports_list: tuple[Ports, ...],
) -> dict[str, Any]:
    connected = incidence_connected(formula)
    record: dict[str, Any] = {
        "formula_sha256": formula_digest(formula),
        "representative_switch": list(representative),
        "switch_multiplicity": multiplicity,
        "connected": connected,
    }
    if not connected:
        record["census"] = None
        record["pairs"] = [
            unavailable_pair(ports, "not_applicable", "disconnected_neighbor")
            for ports in ports_list
        ]
        return record
    census = basis_census(formula)
    record["census"] = compact_census(census)
    if not census["exact"]:
        record["pairs"] = [
            unavailable_pair(ports, "inconclusive", census["reason"])
            for ports in ports_list
        ]
        return record
    if census["status"] != "exact":
        record["pairs"] = [
            unavailable_pair(ports, "not_applicable", census["reason"])
            for ports in ports_list
        ]
        return record
    graph = exchange_graph(census["width_two_bases"], len(formula))
    record["pairs"] = [
        compact_pair(classify_pair(formula, graph, ports), ports)
        for ports in ports_list
    ]
    return record


def seed_record(name: str, raw_formula: Formula, ports_list: tuple[Ports, ...]) -> dict[str, Any]:
    formula = canonical(raw_formula)
    digest = formula_digest(formula)
    if digest != FROZEN_SEED_DIGESTS[name]:
        fail(f"{name}: frozen seed digest changed")
    specs = switch_specs(formula)
    populations: dict[str, dict[str, Any]] = {}
    base_digest = formula_digest(formula)
    base_equivalent_specs = 0
    for spec in specs:
        neighbor = apply_spec(formula, spec)
        neighbor_digest = formula_digest(neighbor)
        if neighbor_digest == base_digest:
            base_equivalent_specs += 1
            continue
        population = populations.setdefault(
            neighbor_digest,
            {
                "formula": neighbor,
                "representative": spec,
                "multiplicity": 0,
            },
        )
        population["multiplicity"] += 1
    neighbors = [
        neighbor_record(
            populations[key]["formula"],
            populations[key]["representative"],
            populations[key]["multiplicity"],
            ports_list,
        )
        for key in sorted(populations)
    ]
    counts: Counter[str] = Counter(
        switch_specs=len(specs),
        base_equivalent_specs=base_equivalent_specs,
        duplicate_nonbase_specs=(
            len(specs) - base_equivalent_specs - len(neighbors)
        ),
        distinct_neighbors=len(neighbors),
        connected_neighbors=0,
        disconnected_neighbors=0,
        exact_censuses=0,
        inconclusive_censuses=0,
        width_two_neighbors=0,
        no_width_two_neighbors=0,
        designated_pair_cases=len(neighbors) * len(ports_list),
        pair_cases_checked=0,
        pair_cases_not_applicable=0,
        pair_cases_inconclusive=0,
        exclusive_pairs=0,
        eligible_pairs=0,
        admissible_pairs=0,
    )
    rejection_combinations: Counter[str] = Counter()
    nullity_histogram: Counter[str] = Counter()
    for neighbor in neighbors:
        if neighbor["connected"]:
            counts["connected_neighbors"] += 1
        else:
            counts["disconnected_neighbors"] += 1
        census = neighbor["census"]
        if census is not None:
            if census["exact"]:
                counts["exact_censuses"] += 1
                nullity_histogram[str(census["nullity"])] += 1
            else:
                counts["inconclusive_censuses"] += 1
            if census["status"] == "exact":
                counts["width_two_neighbors"] += 1
            elif census["exact"]:
                counts["no_width_two_neighbors"] += 1
        for pair in neighbor["pairs"]:
            if pair["status"] == "inconclusive":
                counts["pair_cases_inconclusive"] += 1
                continue
            if pair["status"] != "exact":
                counts["pair_cases_not_applicable"] += 1
                continue
            counts["pair_cases_checked"] += 1
            if not pair["exclusive"]:
                continue
            counts["exclusive_pairs"] += 1
            reasons = pair["rejection_reasons"]
            rejection_combinations["+".join(reasons) or "admissible"] += 1
            if pair["eligible"]:
                counts["eligible_pairs"] += 1
            if pair["admissible"]:
                counts["admissible_pairs"] += 1
    pair_accounting_complete = (
        counts["designated_pair_cases"]
        == counts["pair_cases_checked"]
        + counts["pair_cases_not_applicable"]
        + counts["pair_cases_inconclusive"]
    )
    switch_accounting_complete = (
        counts["switch_specs"]
        == counts["base_equivalent_specs"]
        + counts["duplicate_nonbase_specs"]
        + counts["distinct_neighbors"]
    )
    return {
        "name": name,
        "formula": [list(clause) for clause in formula],
        "formula_sha256": digest,
        "ports": [list(ports) for ports in ports_list],
        "baseline": baseline_record(formula, ports_list),
        "neighbors": neighbors,
        "counts": dict(sorted(counts.items())),
        "nullity_histogram": dict(sorted(nullity_histogram.items())),
        "exclusive_rejection_combinations": dict(
            sorted(rejection_combinations.items())
        ),
        "switch_accounting_complete": switch_accounting_complete,
        "pair_accounting_complete": pair_accounting_complete,
    }


def expected_receipt() -> dict[str, Any]:
    seeds = [
        seed_record(name, formula, ports)
        for name, formula, ports in SEED_SPECS
    ]
    summary_fields = (
        "switch_specs",
        "base_equivalent_specs",
        "duplicate_nonbase_specs",
        "distinct_neighbors",
        "connected_neighbors",
        "disconnected_neighbors",
        "exact_censuses",
        "inconclusive_censuses",
        "width_two_neighbors",
        "no_width_two_neighbors",
        "designated_pair_cases",
        "pair_cases_checked",
        "pair_cases_not_applicable",
        "pair_cases_inconclusive",
        "exclusive_pairs",
        "eligible_pairs",
        "admissible_pairs",
    )
    summary = {
        field: sum(seed["counts"][field] for seed in seeds)
        for field in summary_fields
    }
    summary.update(
        {
            "seed_formulas": len(seeds),
            "designated_pairs": sum(len(seed["ports"]) for seed in seeds),
            "switch_accounting_complete": all(
                seed["switch_accounting_complete"] for seed in seeds
            ),
            "pair_accounting_complete": all(
                seed["pair_accounting_complete"] for seed in seeds
            ),
        }
    )
    exact = (
        summary["switch_accounting_complete"]
        and summary["pair_accounting_complete"]
        and summary["inconclusive_censuses"] == 0
        and summary["pair_cases_inconclusive"] == 0
    )
    if not exact:
        result = "inconclusive_distance_one_search"
    elif summary["eligible_pairs"]:
        result = "eligible_pair_found"
    else:
        result = "finite_distance_one_search_null"
    return {
        "schema": SCHEMA,
        "definition": {
            "switch": "a legal degree-preserving exchange of one distinct variable between two clause rows; tuple entries are zero-based left row, zero-based right row, left variable, right variable",
            "neighbor_scope": "every distinct non-base canonical formula reachable by exactly one legal switch from either frozen seed",
            "designated_pair_case": "one frozen port pair evaluated on one distinct neighbor; exact, not_applicable, and inconclusive cases are all counted",
            "eligible_pair": "exclusive with nonzero rank-two nonparallel kernel columns and distinct primal incidence columns",
            "admissible_pair": "eligible and satisfying the complete exchange, truth-fibre, auxiliary-shadow, and alternate-partition certificate",
            "basis_subset_cap": MAX_BASIS_SUBSETS,
        },
        "frozen_domain": {
            "seed_names": [name for name, _, _ in SEED_SPECS],
            "seed_sha256": FROZEN_SEED_DIGESTS,
            "distance": 1,
            "search_complete": True,
        },
        "seeds": seeds,
        "summary": summary,
        "assessment": {
            "result": result,
            "scope": "complete canonical distance-one switch neighborhoods of two frozen formulas and three designated exclusive pairs",
            "exclusive_pair_degeneracy_conjecture": "not established",
            "complexity_classification": "not established",
            "p_equals_np": "not established",
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
        "distinct_neighbors": expected["summary"]["distinct_neighbors"],
        "pair_cases_checked": expected["summary"]["pair_cases_checked"],
        "exclusive_pairs": expected["summary"]["exclusive_pairs"],
        "eligible_pairs": expected["summary"]["eligible_pairs"],
        "admissible_pairs": expected["summary"]["admissible_pairs"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", type=Path, default=DEFAULT_RECEIPT)
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.receipt), sort_keys=True))


if __name__ == "__main__":
    main()
