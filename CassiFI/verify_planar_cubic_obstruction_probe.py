"""Independent verifier for ``run_planar_cubic_obstruction_probe.py``.

This module intentionally imports only the Python standard library. It rebuilds
the registered formulas, checks graph structure and rotation certificates, and
recomputes the rational column-basis census without importing the production
kernel implementation or the runner.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parent
DEFAULT_RECEIPT = ROOT / "_diag" / "planar_cubic_obstruction_probe.json"
SCHEMA = "cassifi.planar-cubic-obstruction-probe.v1"

Formula = tuple[tuple[int, int, int], ...]
Rotation = tuple[tuple[int, ...], ...]


class VerificationError(ValueError):
    """Raised when a receipt fails an independent check."""


def fail(message: str) -> None:
    raise VerificationError(message)


def canonical_formula(formula: Sequence[Sequence[int]]) -> Formula:
    if not isinstance(formula, Sequence) or isinstance(formula, (str, bytes)):
        fail("formula is not a sequence")
    size = len(formula)
    if size < 3:
        fail("formula has fewer than three clauses")
    rows: list[tuple[int, int, int]] = []
    occurrences = [0] * size
    for raw in formula:
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            fail("clause is not a sequence")
        if len(raw) != 3:
            fail("clause does not have arity three")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in raw):
            fail("clause contains a non-integer variable")
        if any(value < 1 or value > size for value in raw):
            fail("variable is outside 1..n")
        if len(set(raw)) != 3:
            fail("clause repeats a variable")
        ordered = sorted(raw)
        row = (ordered[0], ordered[1], ordered[2])
        rows.append(row)
        for variable in row:
            occurrences[variable - 1] += 1
    if any(total != 3 for total in occurrences):
        fail("variable occurrence count is not three")
    result = tuple(sorted(rows))
    if len(set(result)) != len(result):
        fail("formula repeats a clause")
    return result


def digest(formula: Formula) -> str:
    return hashlib.sha256(
        json.dumps(formula, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def cube_formula() -> Formula:
    return canonical_formula(
        ((1, 2, 3), (1, 2, 4), (1, 3, 4), (2, 3, 4))
    )


def prism_formula(cycle_length: int) -> Formula:
    half = cycle_length // 2
    top = {index: index // 2 + 1 for index in range(1, cycle_length, 2)}
    bottom = {
        index: half + index // 2 + 1
        for index in range(0, cycle_length, 2)
    }
    rows: list[tuple[int, int, int]] = []
    for index in range(0, cycle_length, 2):
        ordered = sorted(
            (
                top[(index - 1) % cycle_length],
                top[(index + 1) % cycle_length],
                bottom[index],
            )
        )
        rows.append((ordered[0], ordered[1], ordered[2]))
    for index in range(1, cycle_length, 2):
        ordered = sorted(
            (
                bottom[(index - 1) % cycle_length],
                bottom[(index + 1) % cycle_length],
                top[index],
            )
        )
        rows.append((ordered[0], ordered[1], ordered[2]))
    return canonical_formula(rows)


def heawood_formula() -> Formula:
    return canonical_formula(
        (
            (1, 2, 3),
            (1, 4, 5),
            (1, 6, 7),
            (2, 4, 6),
            (2, 5, 7),
            (3, 4, 7),
            (3, 5, 6),
        )
    )


def graph_from_formula(formula: Formula) -> tuple[tuple[int, ...], ...]:
    size = len(formula)
    adjacency = [set() for _ in range(2 * size)]
    for clause, row in enumerate(formula):
        for variable in row:
            variable_node = size + variable - 1
            adjacency[clause].add(variable_node)
            adjacency[variable_node].add(clause)
    return tuple(tuple(sorted(row)) for row in adjacency)


def _hex_prism_with_rotation() -> tuple[Formula, Rotation]:
    cycle_length = 6
    half = cycle_length // 2
    top = {index: index // 2 + 1 for index in range(1, cycle_length, 2)}
    bottom = {
        index: half + index // 2 + 1
        for index in range(0, cycle_length, 2)
    }
    raw_rows: list[tuple[int, int, int]] = []
    top_clause = {
        index: position for position, index in enumerate(range(0, cycle_length, 2))
    }
    bottom_clause = {
        index: len(top_clause) + position
        for position, index in enumerate(range(1, cycle_length, 2))
    }
    for index in range(0, cycle_length, 2):
        ordered = sorted(
            (
                top[(index - 1) % cycle_length],
                top[(index + 1) % cycle_length],
                bottom[index],
            )
        )
        raw_rows.append((ordered[0], ordered[1], ordered[2]))
    for index in range(1, cycle_length, 2):
        ordered = sorted(
            (
                bottom[(index - 1) % cycle_length],
                bottom[(index + 1) % cycle_length],
                top[index],
            )
        )
        raw_rows.append((ordered[0], ordered[1], ordered[2]))

    def top_node(index: int) -> int:
        return top_clause[index] if index % 2 == 0 else cycle_length + top[index] - 1

    def bottom_node(index: int) -> int:
        return (
            bottom_clause[index]
            if index % 2 == 1
            else cycle_length + bottom[index] - 1
        )

    raw_rotation: dict[int, tuple[int, ...]] = {}
    for index in range(cycle_length):
        top_neighbors = (
            top_node((index - 1) % cycle_length),
            top_node((index + 1) % cycle_length),
            bottom_node(index),
        )
        bottom_neighbors = (
            bottom_node((index - 1) % cycle_length),
            bottom_node((index + 1) % cycle_length),
            top_node(index),
        )
        raw_rotation[top_node(index)] = tuple(reversed(top_neighbors))
        raw_rotation[bottom_node(index)] = bottom_neighbors

    formula = canonical_formula(raw_rows)
    clause_by_row = {row: index for index, row in enumerate(formula)}

    def relabel(node: int) -> int:
        return clause_by_row[raw_rows[node]] if node < cycle_length else node

    rows: list[tuple[int, ...] | None] = [None] * (2 * cycle_length)
    for raw_node, neighbors in raw_rotation.items():
        rows[relabel(raw_node)] = tuple(relabel(neighbor) for neighbor in neighbors)
    if any(row is None for row in rows):
        fail("independent hex rotation lost a vertex")
    return formula, tuple(row for row in rows if row is not None)


def _vertex_sum_with_rotation(
    left_formula: Formula,
    left_rotation: Rotation,
    right_formula: Formula,
    right_rotation: Rotation,
    *,
    left_clause: int = 0,
    right_variable: int = 1,
    permutation: tuple[int, int, int] = (0, 2, 1),
) -> tuple[Formula, Rotation]:
    left_size = len(left_formula)
    right_size = len(right_formula)
    left_boundary = tuple(left_rotation[left_clause])
    right_variable_node = right_size + right_variable - 1
    right_boundary = tuple(right_rotation[right_variable_node])
    if not all(node >= left_size for node in left_boundary):
        fail("independent left boundary is not a clause boundary")
    if not all(node < right_size for node in right_boundary):
        fail("independent right boundary is not a variable boundary")
    left_variables = tuple(node - left_size + 1 for node in left_boundary)
    matched = {
        right_boundary[index]: left_variables[permutation[index]]
        for index in range(3)
    }
    right_clause_for_left_variable = {
        variable: clause for clause, variable in matched.items()
    }
    new_size = left_size + right_size - 1
    right_variable_map = {
        variable: left_size + (variable - 1 if variable < right_variable else variable - 2) + 1
        for variable in range(1, right_size + 1)
        if variable != right_variable
    }
    raw_rows: list[tuple[int, int, int]] = [
        row for index, row in enumerate(left_formula) if index != left_clause
    ]
    for clause_index, row in enumerate(right_formula):
        ordered = sorted(
            matched[clause_index]
            if variable == right_variable
            else right_variable_map[variable]
            for variable in row
        )
        raw_rows.append((ordered[0], ordered[1], ordered[2]))
    formula = canonical_formula(raw_rows)
    clause_by_row = {row: index for index, row in enumerate(formula)}

    def map_left(node: int) -> int:
        if node < left_size:
            if node == left_clause:
                fail("independent map referenced removed left clause")
            return node if node < left_clause else node - 1
        variable = node - left_size + 1
        return new_size + variable - 1

    def map_right(node: int) -> int:
        if node < right_size:
            return left_size - 1 + node
        variable = node - right_size + 1
        if variable == right_variable:
            fail("independent map referenced removed right variable")
        return new_size + right_variable_map[variable] - 1

    raw_rotation: dict[int, tuple[int, ...]] = {}
    for old_node, neighbors in enumerate(left_rotation):
        if old_node == left_clause:
            continue
        mapped: list[int] = []
        for neighbor in neighbors:
            if neighbor == left_clause:
                variable = old_node - left_size + 1
                mapped.append(map_right(right_clause_for_left_variable[variable]))
            else:
                mapped.append(map_left(neighbor))
        raw_rotation[map_left(old_node)] = tuple(mapped)
    for old_node, neighbors in enumerate(right_rotation):
        if old_node == right_variable_node:
            continue
        mapped = []
        for neighbor in neighbors:
            if neighbor == right_variable_node:
                mapped.append(map_left(left_size + matched[old_node] - 1))
            else:
                mapped.append(map_right(neighbor))
        raw_rotation[map_right(old_node)] = tuple(mapped)

    raw_to_canonical = {
        raw_index: clause_by_row[row]
        for raw_index, row in enumerate(raw_rows)
    }

    def relabel(node: int) -> int:
        return raw_to_canonical[node] if node < new_size else node

    rows: list[tuple[int, ...] | None] = [None] * (2 * new_size)
    for raw_node, neighbors in raw_rotation.items():
        rows[relabel(raw_node)] = tuple(relabel(neighbor) for neighbor in neighbors)
    if any(row is None for row in rows):
        fail("independent vertex sum lost a vertex")
    return formula, tuple(row for row in rows if row is not None)


def hex_sum_chain(piece_count: int = 6) -> tuple[Formula, Rotation]:
    formula, rotation = _hex_prism_with_rotation()
    base_formula, base_rotation = _hex_prism_with_rotation()
    for _ in range(1, piece_count):
        formula, rotation = _vertex_sum_with_rotation(
            formula, rotation, base_formula, base_rotation
        )
    faces, euler = rotation_faces(graph_from_formula(formula), rotation)
    if euler != 2 or faces != 33:
        fail(f"independent chain embedding has faces={faces}, euler={euler}")
    return formula, rotation


def rotation_faces(
    graph: Sequence[Sequence[int]], rotation: Sequence[Sequence[int]]
) -> tuple[int, int]:
    if len(graph) != len(rotation):
        fail("rotation vertex count mismatch")
    normalized = [tuple(row) for row in rotation]
    for vertex, neighbors in enumerate(graph):
        if len(normalized[vertex]) != len(neighbors):
            fail("rotation degree mismatch")
        if set(normalized[vertex]) != set(neighbors):
            fail("rotation edge mismatch")
    edges = sum(len(row) for row in graph) // 2
    seen: set[tuple[int, int]] = set()
    faces = 0
    for source, neighbors in enumerate(graph):
        for target in neighbors:
            if (source, target) in seen:
                continue
            faces += 1
            current = (source, target)
            while current not in seen:
                seen.add(current)
                left, right = current
                row = normalized[right]
                current = (right, row[(row.index(left) + 1) % len(row)])
    if len(seen) != 2 * edges:
        fail("rotation did not cover all darts")
    return faces, len(graph) - edges + faces


def rotation_search(graph: Sequence[Sequence[int]]) -> dict[str, Any]:
    vertex_count = len(graph)
    if vertex_count > 14:
        fail("independent exhaustive planarity search received a large graph")
    base = [tuple(sorted(row)) for row in graph]
    reverse = [tuple(reversed(row)) for row in base]
    maximum: int | None = None
    for checked, mask in enumerate(range(1 << vertex_count), start=1):
        rotation = tuple(
            reverse[vertex] if mask & (1 << vertex) else base[vertex]
            for vertex in range(vertex_count)
        )
        _, euler = rotation_faces(graph, rotation)
        maximum = euler if maximum is None else max(maximum, euler)
        if euler == 2:
            return {
                "method": "exhaustive-rotation",
                "complete": True,
                "planar": True,
                "rotation_systems_checked": checked,
                "maximum_euler_characteristic": maximum,
                "euler_characteristic": 2,
                "rotation": [list(row) for row in rotation],
            }
    return {
        "method": "exhaustive-rotation",
        "complete": True,
        "planar": False,
        "rotation_systems_checked": 1 << vertex_count,
        "maximum_euler_characteristic": maximum,
        "euler_characteristic": None,
        "rotation": None,
    }


def connected_after_removal(graph: Sequence[Sequence[int]], removed: set[int]) -> bool:
    remaining = [vertex for vertex in range(len(graph)) if vertex not in removed]
    if len(remaining) <= 1:
        return True
    reached = {remaining[0]}
    frontier = [remaining[0]]
    while frontier:
        vertex = frontier.pop()
        for neighbor in graph[vertex]:
            if neighbor not in removed and neighbor not in reached:
                reached.add(neighbor)
                frontier.append(neighbor)
    return len(reached) == len(remaining)


def structural(
    formula: Formula,
    planarity: dict[str, Any],
) -> dict[str, Any]:
    graph = graph_from_formula(formula)
    size = len(formula)
    connected = connected_after_removal(graph, set())
    cut: list[int] | None = None
    three_connected = connected
    for removal_size in (1, 2):
        if not three_connected:
            break
        for removed_tuple in itertools.combinations(range(len(graph)), removal_size):
            if not connected_after_removal(graph, set(removed_tuple)):
                three_connected = False
                cut = list(removed_tuple)
                break
    bipartite = all(
        (left < size) != (right < size)
        for left, neighbors in enumerate(graph)
        for right in neighbors
    )
    cubic = all(len(row) == 3 for row in graph)
    simple = all(len(set(row)) == len(row) for row in graph)
    return {
        "vertices": len(graph),
        "edges": sum(len(row) for row in graph) // 2,
        "simple": simple,
        "cubic": cubic,
        "bipartite": bipartite,
        "connected": connected,
        "vertex_3_connected": three_connected,
        "first_vertex_cut": cut,
        "planarity": planarity,
    }


def incidence(formula: Formula) -> list[list[Fraction]]:
    size = len(formula)
    matrix = [[Fraction(0) for _ in range(size)] for _ in range(size)]
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
        selected = next(
            (row for row in range(pivot_row, rows) if values[row][column]),
            None,
        )
        if selected is None:
            continue
        values[pivot_row], values[selected] = values[selected], values[pivot_row]
        pivot = values[pivot_row][column]
        for target in range(column, columns):
            values[pivot_row][target] /= pivot
        for row in range(rows):
            if row == pivot_row or not values[row][column]:
                continue
            factor = values[row][column]
            for target in range(column, columns):
                values[row][target] -= factor * values[pivot_row][target]
        pivots.append(column)
        pivot_row += 1
        if pivot_row == rows:
            break
    return values, tuple(pivots)


def system_for_basis(
    matrix: Sequence[Sequence[Fraction]], pivot_columns: tuple[int, ...]
) -> tuple[int, ...] | None:
    size = len(matrix)
    free = tuple(column for column in range(size) if column not in pivot_columns)
    order = pivot_columns + free
    permuted = [[row[column] for column in order] for row in matrix]
    reduced, pivots = rref(permuted)
    if pivots != tuple(range(len(pivot_columns))):
        return None
    supports = tuple(
        sum(value != 0 for value in reduced[row][len(pivot_columns) :])
        for row in range(len(pivot_columns))
    )
    return supports


def basis_census(formula: Formula) -> dict[str, Any]:
    matrix = incidence(formula)
    reduced, pivots = rref(matrix)
    del reduced
    size = len(formula)
    rank = len(pivots)
    histogram: dict[int, int] = {}
    bases_found = 0
    best: tuple[int, int, tuple[int, ...]] | None = None
    for pivot_columns in itertools.combinations(range(size), rank):
        supports = system_for_basis(matrix, pivot_columns)
        if supports is None:
            continue
        bases_found += 1
        width = max(supports, default=0)
        histogram[width] = histogram.get(width, 0) + 1
        key = (width, sum(supports), pivot_columns)
        if best is None or key < best:
            best = key
    if best is None:
        fail("independent basis census found no basis")
    return {
        "rank": rank,
        "nullity": size - rank,
        "column_subsets_checked": comb(size, rank),
        "column_bases_found": bases_found,
        "basis_maximum_support_histogram": {
            str(width): histogram[width] for width in sorted(histogram)
        },
        "bases_at_optimum": histogram[best[0]],
        "minimum_maximum_pivot_free_support": best[0],
        "minimum_total_support_at_optimum": best[1],
        "exact_optimum": True,
        "bounded_support_2sat_basis_exists": best[0] <= 2,
    }


def profile(formula: Formula) -> dict[str, int]:
    _, pivots = rref(incidence(formula))
    rank = len(pivots)
    nullity = len(formula) - rank
    supports = system_for_basis(incidence(formula), pivots)
    return {
        "rank": rank,
        "nullity": nullity,
        "candidate_kernel_vectors": 1 << nullity,
        "maximum_pivot_free_support": max(supports or (), default=0),
    }


def truth_table(formula: Formula) -> dict[str, Any]:
    models: list[list[int]] = []
    for assignment in itertools.product((0, 1), repeat=len(formula)):
        if all(sum(assignment[v - 1] for v in row) == 1 for row in formula):
            models.append(list(assignment))
    return {
        "status": "sat" if models else "unsat",
        "model_count": len(models),
        "witness": models[0] if models else None,
    }


def kernel_label(formula: Formula) -> dict[str, Any]:
    matrix = incidence(formula)
    reduced, pivots = rref(matrix)
    size = len(formula)
    free = tuple(column for column in range(size) if column not in pivots)
    models: list[list[int]] = []
    for free_values in itertools.product((Fraction(-1), Fraction(2)), repeat=len(free)):
        vector = [Fraction(0)] * size
        for column, value in zip(free, free_values):
            vector[column] = value
        for row, pivot in enumerate(pivots):
            vector[pivot] = -sum(
                reduced[row][column] * vector[column] for column in free
            )
        if any(value not in (Fraction(-1), Fraction(2)) for value in vector):
            continue
        assignment = [int((value + 1) / 3) for value in vector]
        if all(sum(assignment[v - 1] for v in row) == 1 for row in formula):
            models.append(assignment)
    return {
        "status": "sat" if models else "unsat",
        "model_count": len(models),
        "witness": models[0] if models else None,
    }


def expected_fixtures() -> dict[str, tuple[Formula, str]]:
    chain, _ = hex_sum_chain(6)
    return {
        "cube": (cube_formula(), "planar-control"),
        "hexagonal-prism": (prism_formula(6), "planar-control"),
        "heawood-fano-control": (heawood_formula(), "nonplanar-control"),
        "hexagonal-3sum-chain-6": (chain, "planar-negative-control"),
    }


def verify_case(case: dict[str, Any], expected: tuple[Formula, str]) -> None:
    if not isinstance(case, dict):
        fail("case is not an object")
    name = case.get("name")
    formula = canonical_formula(case.get("formula"))
    expected_formula, expected_role = expected
    if formula != expected_formula:
        fail(f"{name}: formula differs from independent fixture")
    if case.get("role") != expected_role:
        fail(f"{name}: role mismatch")
    if case.get("variables") != len(formula):
        fail(f"{name}: variable count mismatch")
    if case.get("formula_sha256") != digest(formula):
        fail(f"{name}: formula digest mismatch")

    planarity = case.get("structural", {}).get("planarity")
    if not isinstance(planarity, dict):
        fail(f"{name}: missing planarity record")
    graph = graph_from_formula(formula)
    if planarity.get("method") == "exhaustive-rotation":
        expected_planarity = rotation_search(graph)
        for key in (
            "method",
            "complete",
            "planar",
            "rotation_systems_checked",
            "maximum_euler_characteristic",
            "euler_characteristic",
            "rotation",
        ):
            if planarity.get(key) != expected_planarity.get(key):
                fail(f"{name}: exhaustive planarity field {key} mismatch")
    elif planarity.get("method") == "supplied-rotation":
        rotation = planarity.get("rotation")
        if not isinstance(rotation, list):
            fail(f"{name}: supplied rotation is absent")
        faces, euler = rotation_faces(graph, rotation)
        if not planarity.get("complete") is False:
            fail(f"{name}: supplied rotation must be marked incomplete")
        if planarity.get("planar") is not True or euler != 2:
            fail(f"{name}: supplied rotation is not a sphere embedding")
        if planarity.get("rotation_systems_checked") != 0:
            fail(f"{name}: supplied rotation search count is not zero")
        if planarity.get("maximum_euler_characteristic") != 2:
            fail(f"{name}: supplied rotation maximum Euler mismatch")
        if planarity.get("euler_characteristic") != 2:
            fail(f"{name}: supplied rotation Euler mismatch")
        if faces != 33:
            fail(f"{name}: supplied chain has unexpected face count")
    else:
        fail(f"{name}: unknown planarity method")

    expected_structural = structural(formula, planarity)
    if case.get("structural") != expected_structural:
        fail(f"{name}: structural summary mismatch")

    expected_profile = profile(formula)
    if case.get("profile") != expected_profile:
        fail(f"{name}: kernel profile mismatch")
    expected_basis = basis_census(formula)
    if case.get("basis") != {
        key: expected_basis[key]
        for key in (
            "rank",
            "nullity",
            "column_subsets_checked",
            "column_bases_found",
            "basis_maximum_support_histogram",
            "bases_at_optimum",
            "minimum_maximum_pivot_free_support",
            "minimum_total_support_at_optimum",
            "exact_optimum",
        )
    }:
        fail(f"{name}: exhaustive basis census mismatch")

    expected_label = truth_table(formula) if len(formula) <= 12 else kernel_label(formula)
    label = case.get("label")
    if not isinstance(label, dict) or label.get("status") != expected_label["status"]:
        fail(f"{name}: exact-one status mismatch")
    if len(formula) <= 12 and label != expected_label:
        fail(f"{name}: truth-table label mismatch")
    if case.get("decision_status") != expected_label["status"]:
        fail(f"{name}: decision status mismatch")
    if case.get("bounded_arity_two_basis_exists") != expected_basis[
        "bounded_support_2sat_basis_exists"
    ]:
        fail(f"{name}: width-two flag mismatch")
    expected_candidate = (
        expected_structural["simple"]
        and expected_structural["cubic"]
        and expected_structural["bipartite"]
        and expected_structural["connected"]
        and expected_structural["vertex_3_connected"]
        and planarity["planar"]
        and expected_basis["minimum_maximum_pivot_free_support"] > 2
    )
    if case.get("candidate_obstruction") is not expected_candidate:
        fail(f"{name}: obstruction predicate mismatch")


def verify(path: str | Path = DEFAULT_RECEIPT) -> dict[str, Any]:
    receipt_path = Path(path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema") != SCHEMA:
        fail("schema mismatch")
    expected = expected_fixtures()
    cases = receipt.get("cases")
    if not isinstance(cases, list) or {case.get("name") for case in cases} != set(expected):
        fail("fixture set mismatch")
    by_name = {case["name"]: case for case in cases}
    for name, fixture in expected.items():
        verify_case(by_name[name], fixture)

    summary = receipt.get("summary")
    recomputed = {
        "cases": len(cases),
        "planar_cases": sum(
            case["structural"]["planarity"]["planar"] for case in cases
        ),
        "planar_vertex_3_connected_cases": sum(
            case["structural"]["planarity"]["planar"]
            and case["structural"]["vertex_3_connected"]
            for case in cases
        ),
        "nonplanar_controls": sum(
            not case["structural"]["planarity"]["planar"] for case in cases
        ),
        "basis_censuses_complete": all(
            case["basis"]["exact_optimum"] for case in cases
        ),
        "basis_subsets_checked": sum(
            case["basis"]["column_subsets_checked"] for case in cases
        ),
        "basis_columns_found": sum(
            case["basis"]["column_bases_found"] for case in cases
        ),
        "width_two_or_better": sum(
            case["bounded_arity_two_basis_exists"] for case in cases
        ),
        "width_two_obstructions": sum(
            case["candidate_obstruction"] for case in cases
        ),
        "sat": sum(case["decision_status"] == "sat" for case in cases),
        "unsat": sum(case["decision_status"] == "unsat" for case in cases),
        "maximum_variables": max(case["variables"] for case in cases),
        "maximum_nullity": max(case["profile"]["nullity"] for case in cases),
    }
    if summary != recomputed:
        fail("summary mismatch")
    assessment = receipt.get("assessment", {})
    if assessment.get("p_equals_np") != "not established":
        fail("receipt overclaims P versus NP")
    if assessment.get("unrestricted_sat") != "not established":
        fail("receipt overclaims unrestricted SAT")
    if summary["width_two_obstructions"] != 0:
        fail("registered screen unexpectedly contains an obstruction")
    return {
        "schema": SCHEMA,
        "verified_cases": len(cases),
        "basis_subsets_checked": summary["basis_subsets_checked"],
        "result": "PASS",
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
