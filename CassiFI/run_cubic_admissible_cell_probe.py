"""Certify finite admissible truth-cell candidates in cubic width-two bases.

The probe exhausts the same frozen connected cubic controls as the preceding
truth-state screen, but replaces the informal cell heuristic with a complete
certificate over the width-two basis-exchange graph.  Every original-column
pair is classified.  Auxiliary shadow columns, alternate pair partitions,
disconnected state fibres, and missing single-exchange flips are explicit
witnessed rejection conditions.

The six registered two-switch compositions are also exhaustively rebuilt and
screened for cross-component shadows and alternate pair partitions.  Results
are bounded evidence for these formulas, not a reduction or a complexity
classification.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Sequence

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cubic_kernel_decision as production

OUTPUT = Path("_diag/cubic_admissible_cell_probe.json")
SCHEMA = "cassifi.cubic-admissible-cell-probe.v2"
MAX_BASIS_SUBSETS = 200_000
MAX_PAIR_CERTIFICATE_WORK = 250_000

Formula = tuple[tuple[int, int, int], ...]
Vector = tuple[Fraction, ...]
Basis = tuple[int, ...]
Edge = tuple[int, int]

PORT_NAMESPACE = "original variable columns, 1-based"
EDGE_NAMESPACE = (
    "incidence edges (clause row, variable column), 1-based within each "
    "9-variable component"
)
VERTEX_NAMESPACE = "zero-based indices into lexicographically sorted width-two bases"

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

DIAGNOSTIC_FORMULA = "support-three-sat"
DIAGNOSTIC_PORTS = (7, 9)
COMPOSITION_SPECS: tuple[tuple[str, Edge, Edge], ...] = (
    ("nonport-nonport", (1, 1), (1, 1)),
    ("nonport-port7", (1, 1), (5, 7)),
    ("port7-nonport", (5, 7), (1, 1)),
    ("port7-port7", (5, 7), (5, 7)),
    ("port7-port9", (5, 7), (5, 9)),
    ("port9-port9", (5, 9), (5, 9)),
)
FROZEN_COMPOSITION_DIGESTS = {
    "nonport-nonport": "183f56f43bc7b584ef716251c94b54c66bf5316cac5510687df5e04aee37594c",
    "nonport-port7": "86b11cd8c5ecfa47d5157c2b604b8be1f626055da2b303519262f405ff57ae7a",
    "port7-nonport": "57f68e6a52278d15502968ea7aa6bed628b64f01915a450d706bb7e4297de510",
    "port7-port7": "bd704241ef966a12ed44bb96e281c3153f14953b94496f1c1972083176413108",
    "port7-port9": "97e844f242c71149c57afd37b3e99ddde3a946830b9680123aefe4bc01ef7b4a",
    "port9-port9": "a1a67ee8c189f1fdf49f29bb7cdfedd7ad17d6d7d25ad567466ebc63b1144ea7",
}

STATES = ("00", "01", "10", "11")
TRUTH_STATES = frozenset(("01", "10"))
ALL_BINARY_RELATIONS = frozenset(
    f"{left}|{right}" for left in TRUTH_STATES for right in TRUTH_STATES
)


def prism_formula(cycle_length: int) -> Formula:
    if cycle_length < 4 or cycle_length % 2:
        raise ValueError("invalid prism cycle length")
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
    return production.canonical_cubic_formula(rows)


def formula_digest(formula: Sequence[Sequence[int]]) -> str:
    canonical = production.canonical_cubic_formula(formula)
    return hashlib.sha256(
        json.dumps(canonical, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def fixture_specs() -> tuple[tuple[str, str, Formula], ...]:
    specs = (
        ("hexagonal-prism", "planar-nullity-two-control", prism_formula(6)),
        ("support-three-sat", "sat-width-two-control", SUPPORT_THREE_SAT),
        ("greedy-exchange-trap-sat", "sat-exchange-control", GREEDY_EXCHANGE_TRAP_SAT),
        ("support-three-unsat", "unsat-width-two-control", SUPPORT_THREE_UNSAT),
        ("all-bases-ternary-sat", "sat-no-width-two-control", ALL_BASES_TERNARY_SAT),
        ("all-bases-ternary-unsat", "unsat-no-width-two-control", ALL_BASES_TERNARY_UNSAT),
    )
    for name, _, formula in specs:
        if formula_digest(formula) != FROZEN_FIXTURE_DIGESTS[name]:
            raise AssertionError(f"{name}: frozen fixture digest changed")
    return specs


def _kernel_data(formula: Formula) -> tuple[dict[str, Any], tuple[Vector, ...]]:
    system = production._system(formula)
    vectors = production._kernel_coordinate_vectors(system, len(formula))
    return system, vectors


def _projective_key(vector: Sequence[Fraction]) -> Vector | None:
    first = next((value for value in vector if value), None)
    if first is None:
        return None
    return tuple(value / first for value in vector)


def column_supports(formula: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    canonical = production.canonical_cubic_formula(formula)
    return tuple(
        tuple(
            row_index + 1
            for row_index, clause in enumerate(canonical)
            if column in clause
        )
        for column in range(1, len(canonical) + 1)
    )


def enumerate_width_two_bases(
    formula: Sequence[Sequence[int]],
    *,
    maximum_subsets: int = MAX_BASIS_SUBSETS,
) -> dict[str, Any]:
    """Exhaust original-column dual bases and retain the width-at-most-two set."""

    canonical = production.canonical_cubic_formula(formula)
    system, vectors = _kernel_data(canonical)
    size = len(canonical)
    nullity = len(system["free_columns_zero_based"])
    rank = size - nullity
    subset_total = math.comb(size, nullity)
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
        "maximum_subsets": maximum_subsets,
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
    if subset_total > maximum_subsets:
        return {
            **common,
            "status": "inconclusive",
            "reason": "basis_subset_cap",
        }

    independent = 0
    histogram: Counter[int] = Counter()
    width_two: list[list[int]] = []
    for selected in itertools.combinations(range(size), nullity):
        basis_vectors = tuple(vectors[index] for index in selected)
        if production._vector_rank(basis_vectors) != nullity:
            continue
        independent += 1
        maximum_support = max(
            (
                sum(
                    coordinate != 0
                    for coordinate in production._basis_coordinates(
                        basis_vectors, vector
                    )
                )
                for vector in vectors
            ),
            default=0,
        )
        histogram[maximum_support] += 1
        if maximum_support <= 2:
            width_two.append([index + 1 for index in selected])

    status = "exact" if width_two else "not_applicable"
    reason = (
        "all_original_column_bases_enumerated"
        if width_two
        else "no_width_two_bases"
    )
    return {
        **common,
        "status": status,
        "reason": reason,
        "basis_subsets_checked": subset_total,
        "independent_ground_bases": independent,
        "width_two_basis_count": len(width_two),
        "width_two_bases": width_two,
        "basis_maximum_support_histogram": {
            str(width): histogram[width] for width in sorted(histogram)
        },
        "exact": True,
    }


def _components(
    adjacency: Sequence[Sequence[int]],
    vertices: Iterable[int] | None = None,
) -> list[list[int]]:
    allowed = set(range(len(adjacency)) if vertices is None else vertices)
    components: list[list[int]] = []
    while allowed:
        start = min(allowed)
        allowed.remove(start)
        component: list[int] = []
        stack = [start]
        while stack:
            vertex = stack.pop()
            component.append(vertex)
            for target in reversed(adjacency[vertex]):
                if target in allowed:
                    allowed.remove(target)
                    stack.append(target)
        components.append(sorted(component))
    return components


def build_basis_exchange_graph(
    raw_bases: Sequence[Sequence[int]],
    size: int,
) -> dict[str, Any]:
    """Build the induced single-element-exchange graph deterministically."""

    bases = tuple(sorted({tuple(sorted(int(value) for value in basis)) for basis in raw_bases}))
    if len(bases) != len(raw_bases):
        raise ValueError("width-two basis list contains duplicates")
    index = {basis: vertex for vertex, basis in enumerate(bases)}
    edges: set[tuple[int, int]] = set()
    universe = set(range(1, size + 1))
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
    for neighbors in adjacency:
        neighbors.sort()
    components = _components(adjacency)
    return {
        "vertex_namespace": VERTEX_NAMESPACE,
        "vertices": [list(basis) for basis in bases],
        "vertex_count": len(bases),
        "edge_count": len(ordered_edges),
        "edges": [list(edge) for edge in ordered_edges],
        "adjacency": adjacency,
        "component_count": len(components),
        "components": components,
        "connected": len(components) == 1,
        "isolated_vertices": [
            vertex for vertex, neighbors in enumerate(adjacency) if not neighbors
        ],
    }


def _membership_signature(bases: Sequence[Basis], column: int) -> str:
    return "".join("1" if column in basis else "0" for basis in bases)


def _state_signature(basis: Sequence[int], ports: tuple[int, int]) -> str:
    selected = set(basis)
    return f"{int(ports[0] in selected)}{int(ports[1] in selected)}"


def _swap_state(state: str) -> str:
    return state[1] + state[0]


def analyze_pair_basis_family(
    graph: dict[str, Any],
    size: int,
    ports: tuple[int, int],
) -> dict[str, Any]:
    """Classify one pair against every vertex and exchange of a basis family."""

    bases = tuple(tuple(int(value) for value in basis) for basis in graph["vertices"])
    if [list(basis) for basis in bases] != graph["vertices"]:
        raise ValueError("exchange graph vertices are not canonical")
    if not (1 <= ports[0] < ports[1] <= size):
        raise ValueError("ports must be a sorted in-range pair")

    states = tuple(_state_signature(basis, ports) for basis in bases)
    counts = Counter(states)
    state_counts = {state: counts[state] for state in STATES}
    exclusive = (
        state_counts["00"] == 0
        and state_counts["11"] == 0
        and state_counts["01"] > 0
        and state_counts["10"] > 0
    )
    forbidden_witnesses = {
        state: (
            {
                "vertex": states.index(state),
                "basis": list(bases[states.index(state)]),
            }
            if state in states
            else None
        )
        for state in ("00", "11")
    }
    missing_truth_states = [state for state in ("01", "10") if not counts[state]]

    adjacency = graph["adjacency"]
    truth_fibres: dict[str, Any] = {}
    for state in ("01", "10"):
        vertices = [vertex for vertex, value in enumerate(states) if value == state]
        components = _components(adjacency, vertices)
        truth_fibres[state] = {
            "vertices": vertices,
            "basis_count": len(vertices),
            "component_count": len(components),
            "components": components,
            "connected": bool(vertices) and len(components) == 1,
            "disconnected_witness": (
                {
                    "vertices": [components[0][0], components[1][0]],
                    "bases": [
                        list(bases[components[0][0]]),
                        list(bases[components[1][0]]),
                    ],
                }
                if len(components) > 1
                else None
            ),
        }

    cross_state_edges = [
        [left, right]
        for left, right in (tuple(edge) for edge in graph["edges"])
        if states[left] in TRUTH_STATES
        and states[right] in TRUTH_STATES
        and states[left] != states[right]
    ]
    signatures = {
        column: _membership_signature(bases, column)
        for column in range(1, size + 1)
    }
    auxiliary_shadows: list[dict[str, Any]] = []
    for column in range(1, size + 1):
        if column in ports:
            continue
        for side, port in (("left", ports[0]), ("right", ports[1])):
            if signatures[column] == signatures[port]:
                auxiliary_shadows.append(
                    {
                        "column": column,
                        "matches": side,
                        "port": port,
                        "signature": signatures[column],
                    }
                )

    alternate_pairs: list[dict[str, Any]] = []
    if exclusive:
        target_states = states
        swapped_states = tuple(_swap_state(state) for state in states)
        for alternate in itertools.combinations(range(1, size + 1), 2):
            if alternate == ports:
                continue
            alternate_states = tuple(
                _state_signature(basis, alternate) for basis in bases
            )
            if alternate_states == target_states:
                orientation = "same"
            elif alternate_states == swapped_states:
                orientation = "swapped"
            else:
                continue
            alternate_pairs.append(
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
        "port_namespace": PORT_NAMESPACE,
        "ports": list(ports),
        "signature_counts": state_counts,
        "exclusive_truth_states": exclusive,
        "forbidden_state_witnesses": forbidden_witnesses,
        "missing_truth_states": missing_truth_states,
        "port_membership_signatures": {
            "left": signatures[ports[0]],
            "right": signatures[ports[1]],
        },
        "exchange": {
            "full_graph_connected": graph["connected"],
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
            "truth_fibres": truth_fibres,
            "cross_state_edge_count": len(cross_state_edges),
            "cross_state_edges": cross_state_edges,
            "single_exchange_truth_flip": bool(cross_state_edges),
        },
        "auxiliary_column_shadows": auxiliary_shadows,
        "alternate_pair_partitions": alternate_pairs,
    }


def classify_admissible_pair(
    formula: Formula,
    graph: dict[str, Any],
    ports: tuple[int, int],
) -> dict[str, Any]:
    family = analyze_pair_basis_family(graph, len(formula), ports)
    _, vectors = _kernel_data(formula)
    supports = column_supports(formula)
    left_vector = vectors[ports[0] - 1]
    right_vector = vectors[ports[1] - 1]
    left_key = _projective_key(left_vector)
    right_key = _projective_key(right_vector)
    nonzero = left_key is not None and right_key is not None
    pair_rank = production._vector_rank((left_vector, right_vector))
    parallel = nonzero and left_key == right_key
    identical_incidence = supports[ports[0] - 1] == supports[ports[1] - 1]

    exchange = family["exchange"]
    truth_fibres = exchange["truth_fibres"]
    reasons: list[str] = []
    if not family["exclusive_truth_states"]:
        reasons.append("not_exclusive_truth_states")
    if not nonzero:
        reasons.append("zero_kernel_column")
    if parallel or pair_rank < 2:
        reasons.append("projectively_parallel_kernel_columns")
    if identical_incidence:
        reasons.append("identical_primal_incidence")
    if not exchange["full_graph_connected"]:
        reasons.append("exchange_graph_disconnected")
    if not all(truth_fibres[state]["connected"] for state in ("01", "10")):
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
        "primal_incidence_identical": identical_incidence,
        "admissible": not reasons,
        "rejection_reasons": reasons,
    }


def switch_compose(
    left_formula: Sequence[Sequence[int]],
    right_formula: Sequence[Sequence[int]],
    left_edge: Edge,
    right_edge: Edge,
) -> Formula:
    left = production.canonical_cubic_formula(left_formula)
    right = production.canonical_cubic_formula(right_formula)
    left_size = len(left)
    left_row, left_variable = left_edge
    right_row, right_variable = right_edge
    if not 1 <= left_row <= left_size or left_variable not in left[left_row - 1]:
        raise ValueError("left switch edge is absent")
    if not 1 <= right_row <= len(right) or right_variable not in right[right_row - 1]:
        raise ValueError("right switch edge is absent")
    rows = [set(clause) for clause in left]
    rows.extend({variable + left_size for variable in clause} for clause in right)
    shifted_row = left_size + right_row - 1
    shifted_variable = left_size + right_variable
    if shifted_variable in rows[left_row - 1] or left_variable in rows[shifted_row]:
        raise ValueError("switch creates a duplicate incidence")
    rows[left_row - 1].remove(left_variable)
    rows[left_row - 1].add(shifted_variable)
    rows[shifted_row].remove(shifted_variable)
    rows[shifted_row].add(left_variable)
    result = production.canonical_cubic_formula(
        tuple(tuple(sorted(row)) for row in rows)
    )
    if not production.incidence_connected(result):
        raise AssertionError("switch result is disconnected")
    return result


def evaluate_fixture(name: str, role: str, formula: Formula) -> dict[str, Any]:
    canonical = production.canonical_cubic_formula(formula)
    digest = formula_digest(canonical)
    if digest != FROZEN_FIXTURE_DIGESTS[name]:
        raise AssertionError(f"{name}: frozen fixture digest changed")
    if not production.incidence_connected(canonical):
        raise AssertionError(f"{name}: frozen fixture is disconnected")
    census = enumerate_width_two_bases(canonical)
    graph = build_basis_exchange_graph(census["width_two_bases"], len(canonical))
    candidate_total = math.comb(len(canonical), 2)
    pair_work_total = candidate_total * graph["vertex_count"]
    if not census["exact"]:
        screen_status = "inconclusive"
    elif not census["width_two_basis_count"]:
        screen_status = "not_applicable"
    elif pair_work_total > MAX_PAIR_CERTIFICATE_WORK:
        screen_status = "inconclusive"
    else:
        screen_status = "exact"
    classifications = (
        [
            classify_admissible_pair(canonical, graph, ports)
            for ports in itertools.combinations(range(1, len(canonical) + 1), 2)
        ]
        if screen_status == "exact"
        else []
    )
    pair_work_checked = pair_work_total if screen_status == "exact" else 0
    return {
        "name": name,
        "role": role,
        "formula": [list(clause) for clause in canonical],
        "formula_sha256": digest,
        "variables": len(canonical),
        "connected": True,
        "decision_status": production.decide_cubic_kernel(canonical)["status"],
        "census": census,
        "exchange_graph": graph,
        "candidate_pairs_total": candidate_total,
        "candidate_pairs_attempted": len(classifications),
        "candidate_pairs_checked": len(classifications),
        "pair_certificate_work_total": pair_work_total,
        "pair_certificate_work_attempted": pair_work_checked,
        "pair_certificate_work_checked": pair_work_checked,
        "pair_certificate_work_cap": MAX_PAIR_CERTIFICATE_WORK,
        "pair_certificate_status": screen_status,
        "pair_screen_status": screen_status,
        "pair_classifications": classifications,
        "exclusive_pairs": [
            row["ports"] for row in classifications if row["exclusive_truth_states"]
        ],
        "admissible_pairs": [
            row["ports"] for row in classifications if row["admissible"]
        ],
    }


def _cross_component_pair(ports: Sequence[int], offset: int) -> bool:
    return (ports[0] <= offset < ports[1]) or (ports[1] <= offset < ports[0])


def evaluate_composition(
    formula: Formula,
    ports: tuple[int, int],
    name: str,
    left_edge: Edge,
    right_edge: Edge,
) -> dict[str, Any]:
    combined = switch_compose(formula, formula, left_edge, right_edge)
    digest = formula_digest(combined)
    if digest != FROZEN_COMPOSITION_DIGESTS[name]:
        raise AssertionError(f"{name}: frozen composition digest changed")
    offset = len(formula)
    right_ports = (ports[0] + offset, ports[1] + offset)
    census = enumerate_width_two_bases(combined)
    graph = build_basis_exchange_graph(census["width_two_bases"], len(combined))
    candidate_total = math.comb(len(combined), 2)
    pair_work_total = candidate_total * graph["vertex_count"]
    if not census["exact"]:
        pair_status = "inconclusive"
    elif not census["width_two_basis_count"]:
        pair_status = "not_applicable"
    elif pair_work_total > MAX_PAIR_CERTIFICATE_WORK:
        pair_status = "inconclusive"
    else:
        pair_status = "exact"
    pair_classifications = (
        [
            classify_admissible_pair(combined, graph, candidate_ports)
            for candidate_ports in itertools.combinations(
                range(1, len(combined) + 1), 2
            )
        ]
        if pair_status == "exact"
        else []
    )
    pair_work_checked = pair_work_total if pair_status == "exact" else 0
    base: dict[str, Any] = {
        "name": name,
        "switch_edge_namespace": EDGE_NAMESPACE,
        "switch_edges": {
            "left_clause_variable": list(left_edge),
            "right_clause_variable": list(right_edge),
        },
        "formula": [list(clause) for clause in combined],
        "formula_sha256": digest,
        "connected": True,
        "variables": len(combined),
        "port_namespace": PORT_NAMESPACE,
        "left_ports": list(ports),
        "right_ports": list(right_ports),
        "census": census,
        "exchange_graph": graph,
        "candidate_pairs_total": candidate_total,
        "candidate_pairs_attempted": len(pair_classifications),
        "candidate_pairs_checked": len(pair_classifications),
        "pair_certificate_work_total": pair_work_total,
        "pair_certificate_work_attempted": pair_work_checked,
        "pair_certificate_work_checked": pair_work_checked,
        "pair_certificate_work_cap": MAX_PAIR_CERTIFICATE_WORK,
        "pair_certificate_status": pair_status,
        "pair_classifications": pair_classifications,
    }
    if pair_status != "exact":
        return {
            **base,
            "relation_counts": {},
            "clean_local_states": None,
            "proper_binary_relation": None,
            "both_states_on_each_side": None,
            "useful_binary_relation": None,
            "left_pair_classification": None,
            "right_pair_classification": None,
            "cross_component_column_shadows": [],
            "cross_component_alternate_pair_partitions": [],
            "composition_escape_free": None,
        }

    bases = tuple(tuple(row) for row in graph["vertices"])
    relation_counts: Counter[str] = Counter(
        f"{_state_signature(basis, ports)}|{_state_signature(basis, right_ports)}"
        for basis in bases
    )
    relation_keys = frozenset(relation_counts)
    clean = all(
        key[:2] in TRUTH_STATES and key[-2:] in TRUTH_STATES
        for key in relation_keys
    )
    proper = bool(relation_keys) and relation_keys < ALL_BINARY_RELATIONS
    both = (
        {key[:2] for key in relation_keys} == TRUTH_STATES
        and {key[-2:] for key in relation_keys} == TRUTH_STATES
    )
    useful = clean and proper and both

    classifications_by_ports = {
        tuple(row["ports"]): row for row in pair_classifications
    }
    left_classification = classifications_by_ports[ports]
    right_classification = classifications_by_ports[right_ports]
    cross_shadows: list[dict[str, Any]] = []
    for classification in pair_classifications:
        target_ports = tuple(classification["ports"])
        target_side = (
            "left"
            if all(column <= offset for column in target_ports)
            else "right"
            if all(column > offset for column in target_ports)
            else None
        )
        if target_side is None:
            continue
        for witness in classification["auxiliary_column_shadows"]:
            column = witness["column"]
            if (target_side == "left" and column > offset) or (
                target_side == "right" and column <= offset
            ):
                cross_shadows.append(
                    {"target_side": target_side, "target_ports": list(target_ports), **witness}
                )

    cross_alternates: list[dict[str, Any]] = []
    for classification in pair_classifications:
        target_ports = tuple(classification["ports"])
        for witness in classification["alternate_pair_partitions"]:
            if _cross_component_pair(witness["ports"], offset):
                cross_alternates.append(
                    {"target_ports": list(target_ports), **witness}
                )

    escape_free = (
        useful
        and left_classification["admissible"]
        and right_classification["admissible"]
        and not cross_shadows
        and not cross_alternates
    )
    return {
        **base,
        "relation_counts": {
            key: relation_counts[key] for key in sorted(relation_counts)
        },
        "clean_local_states": clean,
        "proper_binary_relation": proper,
        "both_states_on_each_side": both,
        "useful_binary_relation": useful,
        "left_pair_classification": left_classification,
        "right_pair_classification": right_classification,
        "cross_component_column_shadows": cross_shadows,
        "cross_component_alternate_pair_partitions": cross_alternates,
        "composition_escape_free": escape_free,
    }



def _reason_histogram(fixtures: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter(
        reason
        for fixture in fixtures
        for row in fixture["pair_classifications"]
        for reason in row["rejection_reasons"]
    )
    return {reason: counts[reason] for reason in sorted(counts)}


def build_receipt() -> dict[str, Any]:
    fixtures = [evaluate_fixture(*spec) for spec in fixture_specs()]
    diagnostic_formula = production.canonical_cubic_formula(SUPPORT_THREE_SAT)
    compositions = [
        evaluate_composition(
            diagnostic_formula,
            DIAGNOSTIC_PORTS,
            name,
            left_edge,
            right_edge,
        )
        for name, left_edge, right_edge in COMPOSITION_SPECS
    ]
    all_records = fixtures + compositions
    candidate_pairs_total = sum(
        row["candidate_pairs_total"] for row in all_records
    )
    candidate_pairs_attempted = sum(
        row["candidate_pairs_attempted"] for row in all_records
    )
    candidate_pairs_checked = sum(
        row["candidate_pairs_checked"] for row in all_records
    )
    pair_work_total = sum(
        row["pair_certificate_work_total"] for row in all_records
    )
    pair_work_attempted = sum(
        row["pair_certificate_work_attempted"] for row in all_records
    )
    pair_work_checked = sum(
        row["pair_certificate_work_checked"] for row in all_records
    )
    admissible_pairs = sum(len(row["admissible_pairs"]) for row in fixtures)
    summary = {
        "fixtures": len(fixtures),
        "exact_fixture_censuses": sum(row["census"]["exact"] for row in fixtures),
        "not_applicable_fixtures": sum(
            row["pair_screen_status"] == "not_applicable" for row in fixtures
        ),
        "fixture_basis_subsets_checked": sum(
            row["census"]["basis_subsets_checked"] for row in fixtures
        ),
        "fixture_width_two_bases": sum(
            row["census"]["width_two_basis_count"] for row in fixtures
        ),
        "candidate_pairs_total": candidate_pairs_total,
        "candidate_pairs_attempted": candidate_pairs_attempted,
        "candidate_pairs_checked": candidate_pairs_checked,
        "pair_certificate_work_total": pair_work_total,
        "pair_certificate_work_attempted": pair_work_attempted,
        "pair_certificate_work_checked": pair_work_checked,
        "pair_certificate_work_cap": MAX_PAIR_CERTIFICATE_WORK,
        "inconclusive_pair_certificates": sum(
            row["pair_certificate_status"] == "inconclusive"
            for row in all_records
        ),
        "exclusive_pairs": sum(len(row["exclusive_pairs"]) for row in fixtures),
        "admissible_pairs": admissible_pairs,
        "rejection_reason_histogram": _reason_histogram(fixtures),
        "compositions": len(compositions),
        "exact_composition_censuses": sum(
            row["census"]["exact"] for row in compositions
        ),
        "composition_basis_subsets_checked": sum(
            row["census"]["basis_subsets_checked"] for row in compositions
        ),
        "composition_width_two_bases": sum(
            row["census"]["width_two_basis_count"] for row in compositions
        ),
        "useful_binary_relations": sum(
            row["useful_binary_relation"] is True for row in compositions
        ),
        "cross_component_column_shadows": sum(
            len(row["cross_component_column_shadows"]) for row in compositions
        ),
        "cross_component_alternate_pair_partitions": sum(
            len(row["cross_component_alternate_pair_partitions"])
            for row in compositions
        ),
        "escape_free_compositions": sum(
            row["composition_escape_free"] is True for row in compositions
        ),
    }
    if any(not row["census"]["exact"] for row in fixtures + compositions):
        result = "inconclusive_basis_subset_cap"
    elif any(
        row["pair_certificate_status"] == "inconclusive"
        for row in fixtures + compositions
    ):
        result = "inconclusive_pair_certificate_cap"
    elif admissible_pairs:
        result = "admissible_cell_found_in_frozen_fixtures"
    else:
        result = "no_admissible_cell_in_frozen_fixtures"
    return {
        "schema": SCHEMA,
        "definition": {
            "basis_index_space": "original dual kernel columns",
            "exchange_edge": "two width-two bases whose symmetric difference has size two",
            "port_namespace": PORT_NAMESPACE,
            "switch_edge_namespace": EDGE_NAMESPACE,
            "exclusive_truth_states": (
                "every enumerated width-two basis realizes 01 or 10 and both occur"
            ),
            "admissible_cell": (
                "exclusive nonzero nonparallel distinct-incidence ports; connected full and "
                "truth-fibre exchange graphs; at least one cross-state exchange; no auxiliary "
                "column shadow; and no alternate pair inducing the same partition up to orientation"
            ),
            "scope": "registered sufficient finite certificate, not a necessary gadget theorem",
            "candidate_pair_scan": (
                "every original-column pair is a candidate; on an applicable record, "
                "attempted and checked counts must equal total before a negative finite-screen "
                "verdict is allowed; not_applicable records are exempt because no width-two "
                "basis exists"
            ),
            "candidate_pair_scan_attempted": (
                "candidate pairs whose classification work was entered"
            ),
            "pair_certificate_work_total": (
                "candidate original-column pairs multiplied by width-two basis vertices"
            ),
            "pair_certificate_work_attempted": (
                "pair-classification units entered; zero after a cap or non-exact basis census"
            ),
            "pair_certificate_work_checked": (
                "pair-classification units completed; zero after a cap or non-exact basis census"
            ),
            "pair_certificate_work_cap": MAX_PAIR_CERTIFICATE_WORK,
        },
        "frozen_domain": {
            "fixture_names": [name for name, _, _ in fixture_specs()],
            "fixture_sha256": FROZEN_FIXTURE_DIGESTS,
            "diagnostic_formula": DIAGNOSTIC_FORMULA,
            "diagnostic_ports": list(DIAGNOSTIC_PORTS),
            "composition_specs": [
                {
                    "name": name,
                    "left_clause_variable": list(left),
                    "right_clause_variable": list(right),
                }
                for name, left, right in COMPOSITION_SPECS
            ],
            "composition_sha256": FROZEN_COMPOSITION_DIGESTS,
        },
        "fixtures": fixtures,
        "compositions": compositions,
        "summary": summary,
        "assessment": {
            "result": result,
            "scope": (
                "six frozen connected cubic controls and six frozen two-switch compositions"
            ),
            "interpretation": (
                "finite sufficient-certificate screen; absence does not rule out other cell "
                "definitions, formulas, compositions, or a direct SAT reduction"
            ),
            "p_equals_np": "not established",
            "np_hardness": "not established",
        },
    }


def run(output: Path = OUTPUT) -> dict[str, Any]:
    receipt = build_receipt()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt["summary"], sort_keys=True))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    run(arguments.output)


if __name__ == "__main__":
    main()
