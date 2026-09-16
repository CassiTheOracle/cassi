"""Independent verifier for the growing-nullity Schaefer receipt.

This file intentionally does not import the probe, the cubic decision module, or
the analysis runner. It rebuilds incidence validation, rational elimination,
all component basis censuses, the direct-sum product counts, and the connected
n=24 bridge width census from scratch.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections import deque
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

RECEIPT = Path("_diag/growing_nullity_schaefer_probe.json")
SCHEMA = "cassifi.growing-nullity-schaefer.v1"
SCHAEFER_CLASSES = (
    "zero_valid",
    "one_valid",
    "horn",
    "dual_horn",
    "bijunctive",
    "affine",
)
ALL_BASES_TERNARY_SAT = (
    (1, 2, 7),
    (1, 4, 10),
    (1, 6, 10),
    (2, 7, 9),
    (2, 11, 12),
    (3, 4, 11),
    (3, 6, 7),
    (3, 8, 12),
    (4, 9, 10),
    (5, 6, 11),
    (5, 8, 9),
    (5, 8, 12),
)
ALL_BASES_TERNARY_UNSAT = (
    (1, 3, 7),
    (1, 6, 12),
    (1, 7, 8),
    (2, 3, 6),
    (2, 10, 13),
    (2, 13, 15),
    (3, 4, 12),
    (4, 7, 9),
    (4, 11, 12),
    (5, 8, 10),
    (5, 11, 15),
    (5, 13, 14),
    (6, 9, 14),
    (8, 11, 14),
    (9, 10, 15),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical_formula(raw: Sequence[Sequence[int]]) -> tuple[tuple[int, int, int], ...]:
    size = len(raw)
    require(size >= 3, "formula too small")
    occurrences = [0] * size
    clauses: list[tuple[int, int, int]] = []
    for clause in raw:
        require(len(clause) == 3, "clause arity mismatch")
        require(len(set(clause)) == 3, "clause has duplicate variable")
        require(
            all(isinstance(value, int) and not isinstance(value, bool) for value in clause),
            "variable is not an integer",
        )
        require(all(1 <= value <= size for value in clause), "variable out of range")
        ordered = tuple(sorted(clause))
        typed_ordered = (ordered[0], ordered[1], ordered[2])
        clauses.append(typed_ordered)
        for value in ordered:
            occurrences[value - 1] += 1
    require(all(count == 3 for count in occurrences), "column degree mismatch")
    return tuple(sorted(clauses))


def formula_digest(formula: Sequence[Sequence[int]]) -> str:
    payload = json.dumps(canonical_formula(formula), separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def matrix_for(formula: tuple[tuple[int, int, int], ...]) -> list[list[Fraction]]:
    matrix = [[Fraction(0) for _ in formula] for _ in formula]
    for row, clause in enumerate(formula):
        for variable in clause:
            matrix[row][variable - 1] = Fraction(1)
    return matrix


def rref(matrix: Sequence[Sequence[Fraction]]) -> tuple[list[list[Fraction]], tuple[int, ...]]:
    values = [list(row) for row in matrix]
    rows = len(values)
    columns = len(values[0]) if values else 0
    pivots: list[int] = []
    pivot_row = 0
    for column in range(columns):
        source = next((row for row in range(pivot_row, rows) if values[row][column]), None)
        if source is None:
            continue
        values[pivot_row], values[source] = values[source], values[pivot_row]
        divisor = values[pivot_row][column]
        values[pivot_row] = [value / divisor for value in values[pivot_row]]
        for row in range(rows):
            if row == pivot_row or values[row][column] == 0:
                continue
            multiplier = values[row][column]
            values[row] = [
                value - multiplier * pivot_value
                for value, pivot_value in zip(values[row], values[pivot_row], strict=True)
            ]
        pivots.append(column)
        pivot_row += 1
        if pivot_row == rows:
            break
    return values, tuple(pivots)


def basis_system(
    formula: tuple[tuple[int, int, int], ...], pivots: tuple[int, ...]
) -> dict[str, Any] | None:
    size = len(formula)
    if len(set(pivots)) != len(pivots) or any(column < 0 or column >= size for column in pivots):
        return None
    pivot_set = set(pivots)
    free = tuple(column for column in range(size) if column not in pivot_set)
    order = pivots + free
    permuted = [[row[column] for column in order] for row in matrix_for(formula)]
    reduced, found = rref(permuted)
    if found != tuple(range(len(pivots))):
        return None
    coefficients = tuple(
        tuple(reduced[row][column] for column in range(len(pivots), size))
        for row in range(len(pivots))
    )
    supports = tuple(sum(value != 0 for value in row) for row in coefficients)
    return {
        "pivots": pivots,
        "free": free,
        "coefficients": coefficients,
        "supports": supports,
    }


def profile(formula: tuple[tuple[int, int, int], ...]) -> dict[str, Any]:
    reduced, pivots = rref(matrix_for(formula))
    del reduced
    return {"rank": len(pivots), "nullity": len(formula) - len(pivots), "pivots": pivots}


def relation_properties(tuples: Sequence[tuple[int, ...]], arity: int) -> dict[str, bool]:
    members = set(tuples)
    horn = all(
        tuple(left[index] & right[index] for index in range(arity)) in members
        for left in tuples for right in tuples
    )
    dual_horn = all(
        tuple(left[index] | right[index] for index in range(arity)) in members
        for left in tuples for right in tuples
    )
    bijunctive = all(
        tuple(int(left[index] + middle[index] + right[index] >= 2) for index in range(arity)) in members
        for left in tuples for middle in tuples for right in tuples
    )
    affine = all(
        tuple(left[index] ^ middle[index] ^ right[index] for index in range(arity)) in members
        for left in tuples for middle in tuples for right in tuples
    )
    return {
        "zero_valid": (0,) * arity in members,
        "one_valid": (1,) * arity in members,
        "horn": horn,
        "dual_horn": dual_horn,
        "bijunctive": bijunctive,
        "affine": affine,
    }


def relation_classes(
    system: dict[str, Any], *, kernel_basis_orientation: bool = True
) -> tuple[str, ...]:
    """Classify relations by their kernel-basis pivot values, not RREF c."""
    properties: list[dict[str, bool]] = []
    for coefficients in system["coefficients"]:
        if kernel_basis_orientation:
            coefficients = tuple(-value for value in coefficients)
        support = tuple(index for index, value in enumerate(coefficients) if value)
        allowed: list[tuple[int, ...]] = []
        for bits in itertools.product((0, 1), repeat=len(support)):
            value = sum(
                (coefficients[index] * (3 * bit - 1) for index, bit in zip(support, bits, strict=True)),
                start=Fraction(0),
            )
            if value in (Fraction(-1), Fraction(2)):
                allowed.append(bits)
        properties.append(relation_properties(allowed, len(support)))
    return tuple(name for name in SCHAEFER_CLASSES if all(row[name] for row in properties))


def class_key(classes: Sequence[str]) -> str:
    return ",".join(classes) if classes else "none"


def exact_census(formula: tuple[tuple[int, int, int], ...]) -> dict[str, Any]:
    shape = profile(formula)
    rank = shape["rank"]
    widths: dict[str, int] = {}
    classes: dict[str, int] = {}
    bases = 0
    for pivots in itertools.combinations(range(len(formula)), rank):
        system = basis_system(formula, pivots)
        if system is None:
            continue
        bases += 1
        width_key = str(max(system["supports"], default=0))
        widths[width_key] = widths.get(width_key, 0) + 1
        key = class_key(relation_classes(system))
        classes[key] = classes.get(key, 0) + 1
    return {
        "formula_sha256": formula_digest(formula),
        "clauses": len(formula),
        "variables": len(formula),
        "rank": rank,
        "nullity": shape["nullity"],
        "column_subsets_checked": math.comb(len(formula), rank),
        "column_bases_found": bases,
        "basis_width_histogram": {key: widths[key] for key in sorted(widths, key=int)},
        "common_schaefer_class_histogram": {key: classes[key] for key in sorted(classes)},
        "minimum_width": min(map(int, widths)),
        "maximum_width": max(map(int, widths)),
        "all_bases_width_at_least_three": all(int(key) >= 3 for key in widths),
    }


def satisfies(formula: tuple[tuple[int, int, int], ...], assignment: Sequence[int]) -> bool:
    return all(sum(assignment[variable - 1] for variable in clause) == 1 for clause in formula)


def brute_status(formula: tuple[tuple[int, int, int], ...]) -> str:
    for assignment in itertools.product((0, 1), repeat=len(formula)):
        if satisfies(formula, assignment):
            return "sat"
    return "unsat"


def independent_connected(formula: tuple[tuple[int, int, int], ...]) -> bool:
    size = len(formula)
    adjacency: list[list[int]] = [[] for _ in range(2 * size)]
    for row, clause in enumerate(formula):
        for variable in clause:
            variable_node = size + variable - 1
            adjacency[row].append(variable_node)
            adjacency[variable_node].append(row)
    reached = {0}
    frontier = deque([0])
    while frontier:
        node = frontier.popleft()
        for neighbor in adjacency[node]:
            if neighbor not in reached:
                reached.add(neighbor)
                frontier.append(neighbor)
    return len(reached) == 2 * size


def offset_formula(formula: tuple[tuple[int, int, int], ...], offset: int):
    return tuple(tuple(value + offset for value in clause) for clause in formula)


def bridge_formula(formula: tuple[tuple[int, int, int], ...]):
    size = len(formula)
    rows = [set(clause) for clause in formula]
    rows.extend(set(clause) for clause in offset_formula(formula, size))
    left_variable = formula[0][0]
    right_variable = size + left_variable
    rows[0].remove(left_variable)
    rows[0].add(right_variable)
    rows[size].remove(right_variable)
    rows[size].add(left_variable)
    return canonical_formula(tuple(tuple(sorted(row)) for row in rows))


def multiply_width_histograms(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    output: dict[str, int] = {}
    for left_key, left_count in left.items():
        for right_key, right_count in right.items():
            key = str(max(int(left_key), int(right_key)))
            output[key] = output.get(key, 0) + left_count * right_count
    return output


def intersect_class_histograms(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    output: dict[str, int] = {}
    for left_key, left_count in left.items():
        left_classes = set() if left_key == "none" else set(left_key.split(","))
        for right_key, right_count in right.items():
            right_classes = set() if right_key == "none" else set(right_key.split(","))
            key = class_key(sorted(left_classes & right_classes))
            output[key] = output.get(key, 0) + left_count * right_count
    return output


def expected_scaling(component: dict[str, Any], blocks: int, satisfiable_status: bool) -> dict[str, Any]:
    width_histogram = {"1": 1}
    class_histogram = {class_key(SCHAEFER_CLASSES): 1}
    for _ in range(blocks):
        width_histogram = multiply_width_histograms(width_histogram, component["basis_width_histogram"])
        class_histogram = intersect_class_histograms(class_histogram, component["common_schaefer_class_histogram"])
    return {
        "blocks": blocks,
        "clauses": component["clauses"] * blocks,
        "variables": component["variables"] * blocks,
        "rank": component["rank"] * blocks,
        "nullity": component["nullity"] * blocks,
        "connected": blocks == 1,
        "basis_count": component["column_bases_found"] ** blocks,
        "basis_width_histogram": width_histogram,
        "common_schaefer_class_histogram": class_histogram,
        "minimum_width": min(map(int, width_histogram)),
        "zero_valid_basis_exists": satisfiable_status,
        "construction": "direct_sum_product_of_component_bases",
    }


def verify_zero_certificate(
    formula: tuple[tuple[int, int, int], ...], certificate: dict[str, Any]
) -> None:
    vector = tuple(Fraction(value) for value in certificate["reconstructed_kernel_vector"])
    matrix = matrix_for(formula)
    require(all(sum(row[index] * vector[index] for index in range(len(formula))) == 0 for row in matrix), "zero certificate is not in the kernel")
    require(all(value in (Fraction(-1), Fraction(2)) for value in vector), "zero certificate leaves the alphabet")
    assignment = tuple(int((value + 1) / 3) for value in vector)
    require(satisfies(formula, assignment), "zero certificate does not satisfy exact-one clauses")
    free_columns = tuple(column - 1 for column in certificate["free_columns"])
    pivot_columns = tuple(column - 1 for column in certificate["pivot_columns"])
    require(set(free_columns).isdisjoint(pivot_columns), "certificate bases overlap")
    require(set(free_columns) | set(pivot_columns) == set(range(len(formula))), "certificate bases do not cover")
    require(all(assignment[column] == 0 for column in free_columns), "certificate free coordinates are not zero variables")
    system = basis_system(formula, pivot_columns)
    require(system is not None, "certificate pivot columns are not a basis")
    assert system is not None
    reconstructed = [Fraction(0)] * len(formula)
    for column in free_columns:
        reconstructed[column] = Fraction(-1)
    for row, pivot in enumerate(system["pivots"]):
        reconstructed[pivot] = sum(system["coefficients"][row], start=Fraction(0))
    require(tuple(reconstructed) == vector, "certificate reconstruction mismatch")
    expected = dict(certificate)
    expected.pop("certificate_digest")
    digest = hashlib.sha256(json.dumps(expected, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()
    require(digest == certificate["certificate_digest"], "zero certificate digest mismatch")


def main() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(receipt["schema"] == SCHEMA, "schema mismatch")
    expected_formulas = {
        "sat": canonical_formula(ALL_BASES_TERNARY_SAT),
        "unsat": canonical_formula(ALL_BASES_TERNARY_UNSAT),
    }
    component_censuses: dict[str, dict[str, Any]] = {}
    for name, formula in expected_formulas.items():
        component = receipt["components"][name]
        require(component["formula"] == [list(clause) for clause in formula], f"{name}: formula mismatch")
        require(component["census"]["formula_sha256"] == formula_digest(formula), f"{name}: formula digest mismatch")
        census = exact_census(formula)
        require(component["census"] == census, f"{name}: exact census mismatch")
        status = brute_status(formula)
        require(component["status"] == status, f"{name}: SAT status mismatch")
        if status == "sat":
            require(component["zero_valid_certificate"] is not None, "SAT certificate missing")
            verify_zero_certificate(formula, component["zero_valid_certificate"])
        else:
            require(component["zero_valid_certificate"] is None, "UNSAT certificate present")
        component_censuses[name] = census

    for name, satisfiable_status in (("sat", True), ("unsat", False)):
        for row in receipt["scaling"][name]:
            expected = expected_scaling(component_censuses[name], row["blocks"], satisfiable_status)
            require(row == expected, f"{name} direct-sum scaling mismatch at {row['blocks']}")

    expected_bridge = bridge_formula(expected_formulas["sat"])
    bridge = receipt["connected_bridge"]
    require(bridge["formula"] == [list(clause) for clause in expected_bridge], "bridge formula mismatch")
    require(bridge["formula_sha256"] == formula_digest(expected_bridge), "bridge digest mismatch")
    require(independent_connected(expected_bridge), "bridge is disconnected")
    bridge_shape = profile(expected_bridge)
    require(bridge["profile"]["rank"] == bridge_shape["rank"], "bridge rank mismatch")
    require(bridge["profile"]["nullity"] == bridge_shape["nullity"], "bridge nullity mismatch")
    bridge_census = exact_census(expected_bridge)
    width = bridge["basis_width"]
    require(width["column_subsets_checked"] == bridge_census["column_subsets_checked"], "bridge subset count mismatch")
    require(width["column_bases_found"] == bridge_census["column_bases_found"], "bridge basis count mismatch")
    require(width["basis_maximum_support_histogram"] == bridge_census["basis_width_histogram"], "bridge width histogram mismatch")
    require(width["minimum_maximum_pivot_free_support"] == bridge_census["minimum_width"] == 3, "bridge minimum width mismatch")
    require(width["bases_with_width_at_most_two"] == 0, "bridge unexpectedly has a width-two basis")
    bridge_pivot_columns = tuple(column - 1 for column in bridge["profile"]["pivot_columns"])
    bridge_canonical_system = basis_system(expected_bridge, bridge_pivot_columns)
    require(bridge_canonical_system is not None, "bridge canonical pivot columns are not a basis")
    assert bridge_canonical_system is not None
    require(bridge["canonical_relation_language"]["common_schaefer_classes"] == list(relation_classes(bridge_canonical_system, kernel_basis_orientation=True)), "bridge canonical relation language mismatch")
    require(receipt["conclusion"] == {
        "connected_bridge_preserves_width_three_at_n24": True,
        "connected_unbounded_width_classification": "not established",
        "direct_sum_is_disconnected": True,
        "direct_sum_width_three_is_exact": True,
        "nullity_grows_linearly": True,
        "zero_valid_basis_is_not_width_two": True,
    }, "conclusion mismatch")
    print(json.dumps({
        "schema": SCHEMA,
        "components_verified": 2,
        "scalings_verified": 10,
        "bridge_bases_verified": bridge_census["column_bases_found"],
        "bridge_minimum_width": bridge_census["minimum_width"],
        "status": "verified",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
