"""Independent verifier for the cubic truth-state cell discovery receipt.

This verifier intentionally imports neither the producer nor the shared cubic
kernel implementation. It rebuilds the frozen formulas, exact rational kernel
coordinates, original-column basis census, exclusive-port classification, and
two-switch compositions from scratch. The search is bounded evidence only; it
does not assert a reduction or a complexity theorem.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any, NoReturn, Sequence

DEFAULT_RECEIPT = Path("_diag/cubic_truth_state_cell_probe.json")
SCHEMA = "cassifi.cubic-truth-state-cell-probe.v2"
MAX_BASIS_SUBSETS = 200_000

Formula = tuple[tuple[int, int, int], ...]
Vector = tuple[Fraction, ...]
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
FROZEN_FIXTURE_DIGESTS = {
    "hexagonal-prism": "0860a4706931c3b362a2f277b3cf6373ed2f90649bcee5330f2db556a68db33b",
    "support-three-sat": "c154b01433577cbad78ea942614b7fd3b3f6ff485802833df403787b9a08a1e4",
    "greedy-exchange-trap-sat": "9f323fccf0bbba8a11a14ccd3dd91bdcaf655ab2523b3ddd6dfda88a1c029e2a",
    "support-three-unsat": "8a270824bbf4bff4dffba3d8ad70f89a083a2a5ede4eedf85967e7c4ddba60d5",
    "all-bases-ternary-sat": "382752c3cc4a88fd9d9b5dc65a068165f8c6d29cb48e6c2374891f834aae7ff2",
    "all-bases-ternary-unsat": "4d3215ad1f61ea5db72a0128fa399d265ea5a93c943c2a638e49ea36292c99e7",
}
FROZEN_COMPOSITION_DIGESTS = {
    "nonport-nonport": "183f56f43bc7b584ef716251c94b54c66bf5316cac5510687df5e04aee37594c",
    "nonport-port7": "86b11cd8c5ecfa47d5157c2b604b8be1f626055da2b303519262f405ff57ae7a",
    "port7-nonport": "57f68e6a52278d15502968ea7aa6bed628b64f01915a450d706bb7e4297de510",
    "port7-port7": "bd704241ef966a12ed44bb96e281c3153f14953b94496f1c1972083176413108",
    "port7-port9": "97e844f242c71149c57afd37b3e99ddde3a946830b9680123aefe4bc01ef7b4a",
    "port9-port9": "a1a67ee8c189f1fdf49f29bb7cdfedd7ad17d6d7d25ad567466ebc63b1144ea7",
}
ALLOWED_LOCAL_STATES = frozenset(("01", "10"))
ALL_BINARY_RELATIONS = frozenset(
    f"{left}|{right}"
    for left in ALLOWED_LOCAL_STATES
    for right in ALLOWED_LOCAL_STATES
)


class VerificationError(ValueError):
    """Raised when a receipt disagrees with the independent reconstruction."""


def fail(message: str) -> NoReturn:
    raise VerificationError(message)


def canonical(formula: Sequence[Sequence[int]]) -> Formula:
    size = len(formula)
    if size < 3:
        fail("formula is too small")
    rows: list[tuple[int, int, int]] = []
    occurrences = [0] * size
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
            variable_node = size + variable - 1
            adjacency[row].add(variable_node)
            adjacency[variable_node].add(row)
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
        values = (
            top[(index - 1) % cycle_length],
            top[(index + 1) % cycle_length],
            bottom[index],
        )
        rows.append((values[0], values[1], values[2]))
    for index in range(1, cycle_length, 2):
        values = (
            bottom[(index - 1) % cycle_length],
            bottom[(index + 1) % cycle_length],
            top[index],
        )
        rows.append((values[0], values[1], values[2]))
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
    if not values:
        return values, ()
    row_count = len(values)
    column_count = len(values[0])
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
        divisor = values[pivot_row][column]
        values[pivot_row] = [value / divisor for value in values[pivot_row]]
        for row in range(row_count):
            if row == pivot_row or not values[row][column]:
                continue
            factor = values[row][column]
            values[row] = [
                value - factor * pivot
                for value, pivot in zip(values[row], values[pivot_row], strict=True)
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


def vector_rank(vectors: Sequence[Sequence[Fraction]]) -> int:
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
    histogram: dict[int, int] = {}
    width_two: list[list[int]] = []
    independent = 0
    for selected in itertools.combinations(range(size), nullity):
        basis = tuple(vectors[index] for index in selected)
        if vector_rank(basis) != nullity:
            continue
        independent += 1
        width = max(
            (
                sum(value != 0 for value in basis_coordinates(basis, vector))
                for vector in vectors
            ),
            default=0,
        )
        histogram[width] = histogram.get(width, 0) + 1
        if width <= 2:
            width_two.append([index + 1 for index in selected])
    return {
        "rank": rank,
        "nullity": nullity,
        "basis_subsets_total": subset_total,
        "basis_subsets_checked": subset_total,
        "independent_ground_bases": independent,
        "width_two_basis_count": len(width_two),
        "width_two_bases": width_two,
        "basis_maximum_support_histogram": {
            str(width): histogram[width] for width in sorted(histogram)
        },
        "exact": True,
        "maximum_subsets": MAX_BASIS_SUBSETS,
        "reason": "all_original_column_bases_enumerated",
        "status": "exact",
    }


def column_supports(formula: Formula) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(row + 1 for row, clause in enumerate(formula) if column in clause)
        for column in range(1, len(formula) + 1)
    )


def projective(vector: Vector) -> Vector | None:
    first = next((value for value in vector if value), None)
    if first is None:
        return None
    return tuple(value / first for value in vector)


def exclusive_pairs(formula: Formula, census: dict[str, Any]) -> list[dict[str, Any]]:
    _, vectors = kernel_columns(formula)
    supports = column_supports(formula)
    bases = tuple(frozenset(basis) for basis in census["width_two_bases"])
    records: list[dict[str, Any]] = []
    for left, right in itertools.combinations(range(1, len(formula) + 1), 2):
        counts: dict[str, int] = {}
        for basis in bases:
            signature = f"{int(left in basis)}{int(right in basis)}"
            counts[signature] = counts.get(signature, 0) + 1
        if set(counts) != ALLOWED_LOCAL_STATES:
            continue
        left_key = projective(vectors[left - 1])
        right_key = projective(vectors[right - 1])
        parallel = left_key is not None and left_key == right_key
        pair_rank = vector_rank((vectors[left - 1], vectors[right - 1]))
        identical = supports[left - 1] == supports[right - 1]
        reasons: list[str] = []
        if left_key is None or right_key is None:
            reasons.append("zero_kernel_column")
        if parallel or pair_rank < 2:
            reasons.append("projectively_parallel_kernel_columns")
        if identical:
            reasons.append("identical_primal_incidence")
        records.append(
            {
                "port_namespace": PORT_NAMESPACE,
                "ports": [left, right],
                "signature_counts": {state: counts[state] for state in sorted(counts)},
                "kernel_pair_rank": pair_rank,
                "kernel_projectively_parallel": parallel,
                "primal_column_supports": [
                    list(supports[left - 1]), list(supports[right - 1])
                ],
                "primal_incidence_identical": identical,
                "eligible_truth_state_pair": not reasons,
                "rejection_reasons": reasons,
            }
        )
    return records


def switch_compose(
    left_formula: Formula,
    right_formula: Formula,
    left_edge: Edge,
    right_edge: Edge,
) -> Formula:
    left_size = len(left_formula)
    right_row, right_variable = right_edge
    left_row, left_variable = left_edge
    if not 1 <= left_row <= left_size or left_variable not in left_formula[left_row - 1]:
        fail("left switch edge is absent")
    if not 1 <= right_row <= len(right_formula) or right_variable not in right_formula[right_row - 1]:
        fail("right switch edge is absent")
    rows = [set(row) for row in left_formula]
    rows.extend({value + left_size for value in row} for row in right_formula)
    shifted_row = left_size + right_row - 1
    shifted_variable = right_variable + left_size
    if shifted_variable in rows[left_row - 1] or left_variable in rows[shifted_row]:
        fail("switch creates a duplicate incidence")
    rows[left_row - 1].remove(left_variable)
    rows[left_row - 1].add(shifted_variable)
    rows[shifted_row].remove(shifted_variable)
    rows[shifted_row].add(left_variable)
    result = canonical(tuple(tuple(sorted(row)) for row in rows))
    if not incidence_connected(result):
        fail("switch result is disconnected")
    return result


def exact_one_status(formula: Formula) -> str:
    for assignment in itertools.product((0, 1), repeat=len(formula)):
        if all(sum(assignment[value - 1] for value in row) == 1 for row in formula):
            return "sat"
    return "unsat"

def state_signature(basis: frozenset[int], ports: tuple[int, int]) -> str:
    return f"{int(ports[0] in basis)}{int(ports[1] in basis)}"

def composition_record(
    formula: Formula,
    ports: tuple[int, int],
    name: str,
    left_edge: Edge,
    right_edge: Edge,
) -> dict[str, Any]:
    combined = switch_compose(formula, formula, left_edge, right_edge)
    combined_digest = digest(combined)
    if combined_digest != FROZEN_COMPOSITION_DIGESTS[name]:
        fail(f"{name}: frozen composition digest changed")
    census = basis_census(combined)
    offset = len(formula)
    right_ports = (ports[0] + offset, ports[1] + offset)
    relation_counts: dict[str, int] = {}
    escape_count = 0
    for raw_basis in census["width_two_bases"]:
        basis = frozenset(raw_basis)
        left_state = state_signature(basis, ports)
        right_state = state_signature(basis, right_ports)
        key = f"{left_state}|{right_state}"
        relation_counts[key] = relation_counts.get(key, 0) + 1
        if left_state not in ALLOWED_LOCAL_STATES or right_state not in ALLOWED_LOCAL_STATES:
            escape_count += 1
    keys = frozenset(relation_counts)
    clean = escape_count == 0
    proper = bool(keys) and keys < ALL_BINARY_RELATIONS
    left_states = {key[:2] for key in keys}
    right_states = {key[-2:] for key in keys}
    both = left_states == ALLOWED_LOCAL_STATES and right_states == ALLOWED_LOCAL_STATES
    return {
        "name": name,
        "switch_edge_namespace": EDGE_NAMESPACE,
        "switch_edges": {
            "left_clause_variable": list(left_edge),
            "right_clause_variable": list(right_edge),
        },
        "formula": [list(row) for row in combined],
        "formula_sha256": combined_digest,
        "connected": True,
        "census": census,
        "port_namespace": PORT_NAMESPACE,
        "left_ports": list(ports),
        "right_ports": list(right_ports),
        "relation_counts": {key: relation_counts[key] for key in sorted(relation_counts)},
        "clean_local_states": clean,
        "proper_binary_relation": bool(proper),
        "both_states_on_each_side": bool(both),
        "useful_binary_relation": bool(clean and proper and both),
        "escape_basis_count": escape_count,
    }


def compare(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        fail(f"{label} mismatch")


def verify_fixture(case: dict[str, Any], expected: tuple[str, str, Formula]) -> dict[str, Any]:
    name, role, formula = expected
    if case.get("name") != name or case.get("role") != role:
        fail(f"{name}: identity mismatch")
    canonical_formula = canonical(formula)
    if case.get("formula") != [list(row) for row in canonical_formula]:
        fail(f"{name}: formula mismatch")
    if case.get("formula_sha256") != digest(canonical_formula):
        fail(f"{name}: formula digest mismatch")
    if case.get("variables") != len(canonical_formula):
        fail(f"{name}: variable count mismatch")
    if case.get("connected") is not True or not incidence_connected(canonical_formula):
        fail(f"{name}: connectivity mismatch")
    census = basis_census(canonical_formula)
    compare(case.get("census"), census, f"{name}: basis census")
    expected_pairs = exclusive_pairs(canonical_formula, census)
    compare(case.get("exclusive_pairs"), expected_pairs, f"{name}: exclusive pairs")
    expected_eligible = [
        record["ports"] for record in expected_pairs if record["eligible_truth_state_pair"]
    ]
    compare(case.get("eligible_truth_state_pairs"), expected_eligible, f"{name}: eligible pairs")
    compare(case.get("decision_status"), exact_one_status(canonical_formula), f"{name}: SAT status")
    return {"name": name, "census": census, "pairs": expected_pairs}


def verify(path: str | Path = DEFAULT_RECEIPT) -> dict[str, Any]:
    receipt_path = Path(path)
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read receipt: {error}") from error
    if receipt.get("schema") != SCHEMA:
        fail("schema mismatch")
    expected_definition = {
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
    }
    compare(receipt.get("definition"), expected_definition, "definition")
    fixture_cases = receipt.get("fixtures")
    if not isinstance(fixture_cases, list):
        fail("fixtures missing")
    expected_specs = fixture_specs()
    if [case.get("name") for case in fixture_cases] != [spec[0] for spec in expected_specs]:
        fail("fixture set mismatch")
    verified_fixtures = [
        verify_fixture(case, expected)
        for case, expected in zip(fixture_cases, expected_specs, strict=True)
    ]

    diagnostic = fixture_cases[1]
    classification = diagnostic.get("exclusive_pairs")
    if not isinstance(classification, list):
        fail("diagnostic exclusive-pair list missing")
    diagnostic_pair = next(
        (record for record in classification if tuple(record.get("ports", ())) == (7, 9)),
        None,
    )
    if diagnostic_pair is None:
        fail("diagnostic pair missing")
    if diagnostic_pair.get("eligible_truth_state_pair") is not False:
        fail("duplicate-incidence diagnostic was accepted")
    if diagnostic_pair.get("primal_incidence_identical") is not True:
        fail("diagnostic pair did not preserve duplicate-incidence rejection")
    expected_control = {
        "formula": DIAGNOSTIC_FORMULA,
        "port_namespace": PORT_NAMESPACE,
        "ports": [7, 9],
        "classification": diagnostic_pair,
        "reason": (
            "the pair is nonparallel in the dual kernel representation but is rejected "
            "because its primal incidence columns are identical"
        ),
    }
    compare(receipt.get("diagnostic_control"), expected_control, "diagnostic control")

    composition_cases = receipt.get("compositions")
    if not isinstance(composition_cases, list) or len(composition_cases) != len(COMPOSITION_SPECS):
        fail("composition set mismatch")
    base_formula = canonical(SUPPORT_THREE_SAT)
    expected_compositions = [
        composition_record(base_formula, DIAGNOSTIC_PORTS, name, left, right)
        for name, left, right in COMPOSITION_SPECS
    ]
    for actual, expected in zip(composition_cases, expected_compositions, strict=True):
        compare(actual, expected, f"{actual.get('name')}: composition")

    summary = receipt.get("summary")
    if not isinstance(summary, dict):
        fail("summary missing")
    recomputed_summary = {
        "fixtures": len(verified_fixtures),
        "exact_fixture_censuses": sum(item["census"]["exact"] for item in verified_fixtures),
        "fixture_basis_subsets_checked": sum(
            item["census"]["basis_subsets_checked"] for item in verified_fixtures
        ),
        "fixture_independent_ground_bases": sum(
            item["census"]["independent_ground_bases"] for item in verified_fixtures
        ),
        "fixture_width_two_bases": sum(
            item["census"]["width_two_basis_count"] for item in verified_fixtures
        ),
        "exclusive_pairs": sum(len(item["pairs"]) for item in verified_fixtures),
        "eligible_truth_state_pairs": sum(
            sum(pair["eligible_truth_state_pair"] for pair in item["pairs"])
            for item in verified_fixtures
        ),
        "rejected_identical_incidence_pairs": sum(
            pair["primal_incidence_identical"]
            for item in verified_fixtures
            for pair in item["pairs"]
        ),
        "diagnostic_compositions": len(expected_compositions),
        "exact_composition_censuses": sum(
            item["census"]["exact"] for item in expected_compositions
        ),
        "composition_basis_subsets_checked": sum(
            item["census"]["basis_subsets_checked"] for item in expected_compositions
        ),
        "composition_width_two_bases": sum(
            item["census"]["width_two_basis_count"] for item in expected_compositions
        ),
        "clean_compositions": sum(
            item["clean_local_states"] is True for item in expected_compositions
        ),
        "useful_binary_relations": sum(
            item["useful_binary_relation"] is True for item in expected_compositions
        ),
    }
    compare(summary, recomputed_summary, "summary")
    assessment = receipt.get("assessment", {})
    if assessment.get("p_equals_np") != "not established":
        fail("receipt overclaims P versus NP")
    if assessment.get("np_hardness") != "not established":
        fail("receipt overclaims NP-hardness")
    if assessment.get("result") != "no_eligible_truth_state_pair_in_frozen_fixtures":
        fail("unexpected bounded result")
    return {
        "schema": SCHEMA,
        "verified_fixtures": len(verified_fixtures),
        "verified_compositions": len(expected_compositions),
        "basis_subsets_checked": (
            recomputed_summary["fixture_basis_subsets_checked"]
            + recomputed_summary["composition_basis_subsets_checked"]
        ),
        "result": "PASS",
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    print(json.dumps(verify(args.receipt), sort_keys=True))
