"""Discover exact binary-state candidates in small cubic kernel configurations.

The probe exhausts a frozen set of existing connected cubic formulas.  A pair
of original variable columns is an exclusive state pair when every internal
width-two dual basis selects exactly one member and both choices occur.  Pairs
with zero or projectively parallel kernel columns, or with identical primal
incidence supports, are rejected as truth-state cells.

A rejected identical-incidence pair is retained as a negative composition
control.  Degree-preserving two-edge switches between two copies are exhaustively
re-enumerated; global state relations are measured from actual bases, never
inferred by multiplying local counts.  This bounded search is conjecture
discovery, not a reduction or a complexity theorem.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cubic_kernel_decision as production

OUTPUT = Path("_diag/cubic_truth_state_cell_probe.json")
SCHEMA = "cassifi.cubic-truth-state-cell-probe.v2"
MAX_BASIS_SUBSETS = 200_000

Formula = tuple[tuple[int, int, int], ...]
Vector = tuple[Fraction, ...]
Basis = tuple[int, ...]
Edge = tuple[int, int]

PORT_NAMESPACE = "original variable columns, 1-based"
EDGE_NAMESPACE = (
    "incidence edges (clause row, variable column), 1-based within each "
    "9-variable component"
)

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

# The support-three SAT control has the smallest exclusive pair in the frozen
# fixtures. Columns 7 and 9 are nonparallel in the dual kernel representation
# but have identical primal incidence supports, so they are a deliberately
# rejected symmetry control rather than a claimed truth-state cell.
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
_ALLOWED_LOCAL_STATES = frozenset(("01", "10"))
_ALL_BINARY_RELATIONS = frozenset(
    f"{left}|{right}"
    for left in _ALLOWED_LOCAL_STATES
    for right in _ALLOWED_LOCAL_STATES
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


def incidence_matrix(formula: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    canonical = production.canonical_cubic_formula(formula)
    size = len(canonical)
    return tuple(
        tuple(int(column in clause) for column in range(1, size + 1))
        for clause in canonical
    )


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


def _projective_key(vector: Sequence[Fraction]) -> Vector | None:
    first = next((value for value in vector if value), None)
    if first is None:
        return None
    return tuple(value / first for value in vector)


def _kernel_data(formula: Formula) -> tuple[dict[str, Any], tuple[Vector, ...]]:
    system = production._system(formula)
    vectors = production._kernel_coordinate_vectors(system, len(formula))
    return system, vectors


def enumerate_internal_width_two_bases(
    formula: Sequence[Sequence[int]],
    *,
    maximum_subsets: int = MAX_BASIS_SUBSETS,
) -> dict[str, Any]:
    """Exhaust all original-column dual bases and retain the width-two family."""

    canonical = production.canonical_cubic_formula(formula)
    system, vectors = _kernel_data(canonical)
    size = len(canonical)
    nullity = len(system["free_columns_zero_based"])
    rank = size - nullity
    subset_total = math.comb(size, rank)
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
    }
    if subset_total > maximum_subsets:
        return {
            **common,
            "status": "inconclusive",
            "reason": "basis_subset_cap",
            "maximum_subsets": maximum_subsets,
        }

    checked = 0
    independent = 0
    width_histogram: dict[int, int] = {}
    width_two: list[list[int]] = []
    for selected in itertools.combinations(range(size), nullity):
        checked += 1
        basis_vectors = tuple(vectors[index] for index in selected)
        if production._vector_rank(basis_vectors) != nullity:
            continue
        independent += 1
        maximum_support = 0
        for vector in vectors:
            coordinates = production._basis_coordinates(basis_vectors, vector)
            maximum_support = max(
                maximum_support,
                sum(value != 0 for value in coordinates),
            )
        width_histogram[maximum_support] = width_histogram.get(maximum_support, 0) + 1
        if maximum_support <= 2:
            width_two.append([index + 1 for index in selected])

    return {
        **common,
        "status": "exact",
        "reason": "all_original_column_bases_enumerated",
        "basis_subsets_checked": checked,
        "independent_ground_bases": independent,
        "width_two_basis_count": len(width_two),
        "width_two_bases": width_two,
        "basis_maximum_support_histogram": {
            str(width): width_histogram[width] for width in sorted(width_histogram)
        },
        "exact": True,
        "maximum_subsets": maximum_subsets,
    }


def exclusive_port_signatures(
    formula: Sequence[Sequence[int]],
    census: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return every pair realizing exactly the two exclusive basis signatures."""

    if not census["exact"]:
        return []
    canonical = production.canonical_cubic_formula(formula)
    _, vectors = _kernel_data(canonical)
    supports = column_supports(canonical)
    bases = tuple(frozenset(basis) for basis in census["width_two_bases"])
    records: list[dict[str, Any]] = []
    for left, right in itertools.combinations(range(1, len(canonical) + 1), 2):
        counts: dict[str, int] = {}
        for basis in bases:
            signature = f"{int(left in basis)}{int(right in basis)}"
            counts[signature] = counts.get(signature, 0) + 1
        if set(counts) != _ALLOWED_LOCAL_STATES:
            continue

        left_vector = vectors[left - 1]
        right_vector = vectors[right - 1]
        pair_rank = production._vector_rank((left_vector, right_vector))
        left_key = _projective_key(left_vector)
        right_key = _projective_key(right_vector)
        zero_column = left_key is None or right_key is None
        projectively_parallel = (
            not zero_column and left_key == right_key
        )
        identical_incidence = supports[left - 1] == supports[right - 1]
        rejection_reasons: list[str] = []
        if zero_column:
            rejection_reasons.append("zero_kernel_column")
        if projectively_parallel or pair_rank < 2:
            rejection_reasons.append("projectively_parallel_kernel_columns")
        if identical_incidence:
            rejection_reasons.append("identical_primal_incidence")
        records.append(
            {
                "port_namespace": PORT_NAMESPACE,
                "ports": [left, right],
                "signature_counts": {
                    state: counts[state] for state in sorted(counts)
                },
                "kernel_pair_rank": pair_rank,
                "kernel_projectively_parallel": projectively_parallel,
                "primal_column_supports": [
                    list(supports[left - 1]),
                    list(supports[right - 1]),
                ],
                "primal_incidence_identical": identical_incidence,
                "eligible_truth_state_pair": not rejection_reasons,
                "rejection_reasons": rejection_reasons,
            }
        )
    return records


def switch_compose(
    left_formula: Sequence[Sequence[int]],
    right_formula: Sequence[Sequence[int]],
    left_edge: Edge,
    right_edge: Edge,
) -> Formula:
    """Join two cubic formulas by a degree-preserving incidence two-switch."""

    left = production.canonical_cubic_formula(left_formula)
    right = production.canonical_cubic_formula(right_formula)
    left_size = len(left)
    right_size = len(right)
    left_row, left_variable = left_edge
    right_row, right_variable = right_edge
    if not 1 <= left_row <= left_size or left_variable not in left[left_row - 1]:
        raise ValueError("left switch edge is absent")
    if not 1 <= right_row <= right_size or right_variable not in right[right_row - 1]:
        raise ValueError("right switch edge is absent")

    rows = [set(clause) for clause in left]
    rows.extend(
        {variable + left_size for variable in clause}
        for clause in right
    )
    shifted_right_row = left_size + right_row - 1
    shifted_right_variable = left_size + right_variable
    if shifted_right_variable in rows[left_row - 1]:
        raise ValueError("left switch target already exists")
    if left_variable in rows[shifted_right_row]:
        raise ValueError("right switch target already exists")
    rows[left_row - 1].remove(left_variable)
    rows[left_row - 1].add(shifted_right_variable)
    rows[shifted_right_row].remove(shifted_right_variable)
    rows[shifted_right_row].add(left_variable)

    combined = production.canonical_cubic_formula(
        tuple(tuple(sorted(row)) for row in rows)
    )
    if not production.incidence_connected(combined):
        raise AssertionError("degree-preserving switch did not connect both formulas")
    return combined


def _state_signature(basis: frozenset[int], ports: tuple[int, int]) -> str:
    return f"{int(ports[0] in basis)}{int(ports[1] in basis)}"


def evaluate_composition(
    formula: Formula,
    ports: tuple[int, int],
    name: str,
    left_edge: Edge,
    right_edge: Edge,
) -> dict[str, Any]:
    combined = switch_compose(formula, formula, left_edge, right_edge)
    combined_digest = formula_digest(combined)
    if combined_digest != FROZEN_COMPOSITION_DIGESTS[name]:
        raise AssertionError(f"{name}: frozen composition digest changed")
    offset = len(formula)
    right_ports = (ports[0] + offset, ports[1] + offset)
    edge_record = {
        "left_clause_variable": list(left_edge),
        "right_clause_variable": list(right_edge),
    }
    base = {
        "name": name,
        "switch_edge_namespace": EDGE_NAMESPACE,
        "switch_edges": edge_record,
        "formula": [list(clause) for clause in combined],
        "formula_sha256": combined_digest,
        "connected": production.incidence_connected(combined),
        "census": enumerate_internal_width_two_bases(combined),
        "port_namespace": PORT_NAMESPACE,
        "left_ports": list(ports),
        "right_ports": list(right_ports),
    }
    census = base["census"]
    if not census["exact"]:
        return {
            **base,
            "relation_counts": {},
            "clean_local_states": None,
            "proper_binary_relation": None,
            "both_states_on_each_side": None,
            "useful_binary_relation": None,
            "escape_basis_count": None,
        }

    relation_counts: dict[str, int] = {}
    escape_count = 0
    for raw_basis in census["width_two_bases"]:
        basis = frozenset(raw_basis)
        left_state = _state_signature(basis, ports)
        right_state = _state_signature(basis, right_ports)
        key = f"{left_state}|{right_state}"
        relation_counts[key] = relation_counts.get(key, 0) + 1
        if (
            left_state not in _ALLOWED_LOCAL_STATES
            or right_state not in _ALLOWED_LOCAL_STATES
        ):
            escape_count += 1

    relation_keys = frozenset(relation_counts)
    clean = escape_count == 0
    proper = bool(relation_keys) and relation_keys < _ALL_BINARY_RELATIONS
    left_states = {key[:2] for key in relation_keys}
    right_states = {key[-2:] for key in relation_keys}
    both_states = (
        left_states == _ALLOWED_LOCAL_STATES
        and right_states == _ALLOWED_LOCAL_STATES
    )
    useful = clean and proper and both_states
    return {
        **base,
        "relation_counts": {
            key: relation_counts[key] for key in sorted(relation_counts)
        },
        "clean_local_states": clean,
        "proper_binary_relation": proper,
        "both_states_on_each_side": both_states,
        "useful_binary_relation": useful,
        "escape_basis_count": escape_count,
    }


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




def evaluate_fixture(name: str, role: str, formula: Formula) -> dict[str, Any]:
    canonical = production.canonical_cubic_formula(formula)
    if not production.incidence_connected(canonical):
        raise AssertionError(f"{name}: frozen fixture is disconnected")
    census = enumerate_internal_width_two_bases(canonical)
    pairs = exclusive_port_signatures(canonical, census)
    return {
        "name": name,
        "role": role,
        "formula": [list(clause) for clause in canonical],
        "formula_sha256": formula_digest(canonical),
        "variables": len(canonical),
        "connected": True,
        "decision_status": production.decide_cubic_kernel(canonical)["status"],
        "census": census,
        "exclusive_pairs": pairs,
        "eligible_truth_state_pairs": [
            record["ports"]
            for record in pairs
            if record["eligible_truth_state_pair"]
        ],
    }


def build_receipt() -> dict[str, Any]:
    fixtures = [evaluate_fixture(*spec) for spec in fixture_specs()]
    by_name = {record["name"]: record for record in fixtures}
    diagnostic = by_name[DIAGNOSTIC_FORMULA]
    diagnostic_record = next(
        (
            record
            for record in diagnostic["exclusive_pairs"]
            if tuple(record["ports"]) == DIAGNOSTIC_PORTS
        ),
        None,
    )
    if diagnostic_record is None:
        raise AssertionError("diagnostic exclusive pair disappeared")
    if diagnostic_record["eligible_truth_state_pair"]:
        raise AssertionError("identical-incidence diagnostic became eligible")

    diagnostic_formula = production.canonical_cubic_formula(diagnostic["formula"])
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
    eligible_pairs = sum(
        len(record["eligible_truth_state_pairs"]) for record in fixtures
    )
    exact_fixture_censuses = sum(record["census"]["exact"] for record in fixtures)
    exact_composition_censuses = sum(
        record["census"]["exact"] for record in compositions
    )
    useful_compositions = sum(
        record["useful_binary_relation"] is True for record in compositions
    )
    summary = {
        "fixtures": len(fixtures),
        "exact_fixture_censuses": exact_fixture_censuses,
        "fixture_basis_subsets_checked": sum(
            record["census"]["basis_subsets_checked"] for record in fixtures
        ),
        "fixture_independent_ground_bases": sum(
            record["census"]["independent_ground_bases"] for record in fixtures
        ),
        "fixture_width_two_bases": sum(
            record["census"]["width_two_basis_count"] for record in fixtures
        ),
        "exclusive_pairs": sum(len(record["exclusive_pairs"]) for record in fixtures),
        "eligible_truth_state_pairs": eligible_pairs,
        "rejected_identical_incidence_pairs": sum(
            pair["primal_incidence_identical"]
            for record in fixtures
            for pair in record["exclusive_pairs"]
        ),
        "diagnostic_compositions": len(compositions),
        "exact_composition_censuses": exact_composition_censuses,
        "composition_basis_subsets_checked": sum(
            record["census"]["basis_subsets_checked"] for record in compositions
        ),
        "composition_width_two_bases": sum(
            record["census"]["width_two_basis_count"] for record in compositions
        ),
        "clean_compositions": sum(
            record["clean_local_states"] is True for record in compositions
        ),
        "useful_binary_relations": useful_compositions,
    }
    if exact_fixture_censuses != len(fixtures):
        result = "inconclusive_fixture_cap"
    elif eligible_pairs:
        result = "eligible_truth_state_pair_found"
    else:
        result = "no_eligible_truth_state_pair_in_frozen_fixtures"
    return {
        "schema": SCHEMA,
        "definition": {
            "basis_index_space": "original dual kernel columns",
            "port_namespace": PORT_NAMESPACE,
            "switch_edge_namespace": EDGE_NAMESPACE,
            "exclusive_pair": "all width-two bases realize exactly signatures 01 and 10, both nonempty",
            "eligibility": (
                "both kernel columns nonzero and projectively independent, with distinct "
                "primal incidence supports"
            ),
            "useful_composition": (
                "all global bases preserve local 01/10 states and realize a nonempty proper "
                "binary relation using both states on each side"
            ),
        },
        "fixtures": fixtures,
        "diagnostic_control": {
            "formula": DIAGNOSTIC_FORMULA,
            "port_namespace": PORT_NAMESPACE,
            "ports": list(DIAGNOSTIC_PORTS),
            "classification": diagnostic_record,
            "reason": (
                "the pair is nonparallel in the dual kernel representation but is rejected "
                "because its primal incidence columns are identical"
            ),
        },
        "compositions": compositions,
        "summary": summary,
        "assessment": {
            "result": result,
            "scope": (
                "six pre-existing connected cubic controls and six fixed two-switch "
                "compositions of one rejected identical-incidence pair"
            ),
            "interpretation": (
                "bounded candidate discovery only; no arbitrary-composition normalization "
                "lemma and no SAT reduction"
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
