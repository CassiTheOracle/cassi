"""Screen canonical planar cubic exact-one incidence graphs.

The target is narrower than unrestricted cubic exact-one SAT: this probe
requires a simple bipartite clause-variable incidence graph that is connected,
planar, and vertex-3-connected. It exhausts every internal column basis and
records whether any basis has maximum pivot-free support at most two. A zero
obstruction count is a finite screen, not a theorem.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import sys
from pathlib import Path
from typing import Any, Sequence

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cubic_kernel_decision import (
    canonical_cubic_formula,
    cubic_kernel_basis_width,
    cubic_kernel_profile,
    decide_cubic_kernel,
)

OUTPUT = Path("_diag/planar_cubic_obstruction_probe.json")
SCHEMA = "cassifi.planar-cubic-obstruction-probe.v1"
MAX_BASIS_SUBSETS = 200_000

Formula = tuple[tuple[int, int, int], ...]
Rotation = tuple[tuple[int, ...], ...]


def formula_digest(formula: Sequence[Sequence[int]]) -> str:
    canonical = canonical_cubic_formula(formula)
    return hashlib.sha256(
        json.dumps(canonical, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def cube_formula() -> Formula:
    return canonical_cubic_formula(
        ((1, 2, 3), (1, 2, 4), (1, 3, 4), (2, 3, 4))
    )


def prism_formula(cycle_length: int) -> Formula:
    """Return the clause side of an even circular-prism graph."""

    if cycle_length < 4 or cycle_length % 2:
        raise ValueError("the bipartite prism needs an even cycle of length >= 4")
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
        ordered = sorted(values)
        rows.append((ordered[0], ordered[1], ordered[2]))
    for index in range(1, cycle_length, 2):
        values = (
            bottom[(index - 1) % cycle_length],
            bottom[(index + 1) % cycle_length],
            top[index],
        )
        ordered = sorted(values)
        rows.append((ordered[0], ordered[1], ordered[2]))
    return canonical_cubic_formula(tuple(rows))


def heawood_formula() -> Formula:
    """Fano-plane incidence, retained as a nonplanar cubic control."""

    return canonical_cubic_formula(
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


def graph_from_formula(formula: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    canonical = canonical_cubic_formula(formula)
    size = len(canonical)
    adjacency = [set() for _ in range(2 * size)]
    for clause, row in enumerate(canonical):
        for variable in row:
            variable_node = size + variable - 1
            adjacency[clause].add(variable_node)
            adjacency[variable_node].add(clause)
    return tuple(tuple(sorted(neighbors)) for neighbors in adjacency)


def _rotation_faces(
    graph: Sequence[Sequence[int]], rotation: Sequence[Sequence[int]]
) -> tuple[int, int]:
    if len(graph) != len(rotation):
        raise ValueError("rotation has the wrong vertex count")
    normalized = [tuple(row) for row in rotation]
    for vertex, neighbors in enumerate(graph):
        if len(normalized[vertex]) != len(neighbors):
            raise ValueError("rotation has the wrong degree")
        if set(normalized[vertex]) != set(neighbors):
            raise ValueError("rotation does not describe the graph")
    edge_count = sum(len(row) for row in graph) // 2
    seen: set[tuple[int, int]] = set()
    faces = 0
    for left, neighbors in enumerate(graph):
        for right in neighbors:
            dart = (left, right)
            if dart in seen:
                continue
            faces += 1
            current = dart
            while current not in seen:
                seen.add(current)
                source, target = current
                row = normalized[target]
                position = row.index(source)
                current = (target, row[(position + 1) % len(row)])
    if len(seen) != 2 * edge_count:
        raise ValueError("rotation did not traverse every directed edge")
    return faces, len(graph) - edge_count + faces


def _rotation_search(graph: Sequence[Sequence[int]]) -> dict[str, Any]:
    """Exhaust all cubic rotation systems for small structural controls."""

    if any(len(row) != 3 for row in graph):
        raise ValueError("rotation search expects a cubic graph")
    vertex_count = len(graph)
    if vertex_count > 14:
        raise ValueError("exhaustive rotation search is reserved for small controls")
    base = [tuple(sorted(row)) for row in graph]
    reverse = [tuple(reversed(row)) for row in base]
    best_euler: int | None = None
    checked = 0
    for mask in range(1 << vertex_count):
        checked += 1
        rotation = tuple(
            reverse[vertex] if mask & (1 << vertex) else base[vertex]
            for vertex in range(vertex_count)
        )
        _, euler = _rotation_faces(graph, rotation)
        best_euler = euler if best_euler is None else max(best_euler, euler)
        if euler == 2:
            return {
                "method": "exhaustive-rotation",
                "complete": True,
                "planar": True,
                "rotation_systems_checked": checked,
                "maximum_euler_characteristic": best_euler,
                "euler_characteristic": euler,
                "rotation": [list(row) for row in rotation],
            }
    return {
        "method": "exhaustive-rotation",
        "complete": True,
        "planar": False,
        "rotation_systems_checked": checked,
        "maximum_euler_characteristic": best_euler,
        "euler_characteristic": None,
        "rotation": None,
    }


def _connected_after_removal(
    graph: Sequence[Sequence[int]], removed: set[int]
) -> bool:
    remaining = [vertex for vertex in range(len(graph)) if vertex not in removed]
    if len(remaining) <= 1:
        return True
    reached = {remaining[0]}
    frontier = [remaining[0]]
    while frontier:
        vertex = frontier.pop()
        for neighbor in graph[vertex]:
            if neighbor in removed or neighbor in reached:
                continue
            reached.add(neighbor)
            frontier.append(neighbor)
    return len(reached) == len(remaining)


def structural_summary(
    formula: Sequence[Sequence[int]],
    planarity: dict[str, Any],
) -> dict[str, Any]:
    graph = graph_from_formula(formula)
    vertex_count = len(graph)
    connected = _connected_after_removal(graph, set())
    cut: list[int] | None = None
    three_connected = connected and vertex_count >= 4
    if three_connected:
        for size in (1, 2):
            for removed_tuple in itertools.combinations(range(vertex_count), size):
                if not _connected_after_removal(graph, set(removed_tuple)):
                    three_connected = False
                    cut = list(removed_tuple)
                    break
            if not three_connected:
                break
    bipartite = all(
        (left < len(formula)) != (right < len(formula))
        for left, neighbors in enumerate(graph)
        for right in neighbors
    )
    cubic = all(len(neighbors) == 3 for neighbors in graph)
    simple = all(len(set(neighbors)) == len(neighbors) for neighbors in graph)
    return {
        "vertices": vertex_count,
        "edges": sum(len(row) for row in graph) // 2,
        "simple": simple,
        "cubic": cubic,
        "bipartite": bipartite,
        "connected": connected,
        "vertex_3_connected": three_connected,
        "first_vertex_cut": cut,
        "planarity": planarity,
    }


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
        values = (
            top[(index - 1) % cycle_length],
            top[(index + 1) % cycle_length],
            bottom[index],
        )
        ordered = sorted(values)
        raw_rows.append((ordered[0], ordered[1], ordered[2]))
    for index in range(1, cycle_length, 2):
        values = (
            bottom[(index - 1) % cycle_length],
            bottom[(index + 1) % cycle_length],
            top[index],
        )
        ordered = sorted(values)
        raw_rows.append((ordered[0], ordered[1], ordered[2]))

    def top_node(index: int) -> int:
        return (
            top_clause[index]
            if index % 2 == 0
            else cycle_length + top[index] - 1
        )

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

    canonical = canonical_cubic_formula(tuple(raw_rows))
    clause_by_row = {row: index for index, row in enumerate(canonical)}

    def relabel(node: int) -> int:
        return clause_by_row[raw_rows[node]] if node < cycle_length else node

    rotation_rows: list[tuple[int, ...] | None] = [None] * (2 * cycle_length)
    for raw_node, neighbors in raw_rotation.items():
        node = relabel(raw_node)
        rotation_rows[node] = tuple(relabel(neighbor) for neighbor in neighbors)
    if any(row is None for row in rotation_rows):
        raise AssertionError("hexagonal rotation lost a vertex")
    return canonical, tuple(row for row in rotation_rows if row is not None)


def _vertex_sum_with_rotation(
    left_formula: Formula,
    left_rotation: Rotation,
    right_formula: Formula,
    right_rotation: Rotation,
    *,
    left_clause: int = 0,
    right_variable: int = 1,
    permutation: tuple[int, int, int] = (0, 1, 2),
) -> tuple[Formula, Rotation]:
    left_size = len(left_formula)
    right_size = len(right_formula)
    left_boundary_nodes = tuple(left_rotation[left_clause])
    right_variable_node = right_size + right_variable - 1
    right_boundary_nodes = tuple(right_rotation[right_variable_node])
    if not all(node >= left_size for node in left_boundary_nodes):
        raise AssertionError("left boundary is not a clause's variables")
    if not all(node < right_size for node in right_boundary_nodes):
        raise AssertionError("right boundary is not a variable's clauses")
    left_boundary_variables = tuple(node - left_size + 1 for node in left_boundary_nodes)
    right_boundary_clauses = right_boundary_nodes
    matched = {
        right_boundary_clauses[index]: left_boundary_variables[permutation[index]]
        for index in range(3)
    }
    right_clause_for_left_variable = {
        variable: clause for clause, variable in matched.items()
    }
    new_size = left_size + right_size - 1
    raw_rows: list[tuple[int, int, int]] = [
        row for index, row in enumerate(left_formula) if index != left_clause
    ]
    right_variable_map = {
        variable: left_size + (variable - 1 if variable < right_variable else variable - 2) + 1
        for variable in range(1, right_size + 1)
        if variable != right_variable
    }
    for clause_index, row in enumerate(right_formula):
        values = tuple(
            matched[clause_index]
            if variable == right_variable
            else right_variable_map[variable]
            for variable in row
        )
        ordered = sorted(values)
        raw_rows.append((ordered[0], ordered[1], ordered[2]))
    canonical = canonical_cubic_formula(tuple(raw_rows))
    clause_by_row = {row: index for index, row in enumerate(canonical)}

    def map_left(node: int) -> int:
        if node < left_size:
            if node == left_clause:
                raise AssertionError("removed left clause was referenced")
            return node if node < left_clause else node - 1
        variable = node - left_size + 1
        return new_size + variable - 1

    def map_right(node: int) -> int:
        if node < right_size:
            return left_size - 1 + node
        variable = node - right_size + 1
        if variable == right_variable:
            raise AssertionError("removed right variable was referenced")
        return new_size + right_variable_map[variable] - 1

    raw_rotation: dict[int, tuple[int, ...]] = {}
    for old_node, neighbors in enumerate(left_rotation):
        if old_node == left_clause:
            continue
        mapped_neighbors: list[int] = []
        for neighbor in neighbors:
            if neighbor == left_clause:
                variable = old_node - left_size + 1
                mapped_neighbors.append(
                    map_right(right_clause_for_left_variable[variable])
                )
            else:
                mapped_neighbors.append(map_left(neighbor))
        raw_rotation[map_left(old_node)] = tuple(mapped_neighbors)
    for old_node, neighbors in enumerate(right_rotation):
        if old_node == right_variable_node:
            continue
        mapped_neighbors = []
        for neighbor in neighbors:
            if neighbor == right_variable_node:
                mapped_neighbors.append(
                    map_left(left_size + matched[old_node] - 1)
                )
            else:
                mapped_neighbors.append(map_right(neighbor))
        raw_rotation[map_right(old_node)] = tuple(mapped_neighbors)

    raw_clause_rows = raw_rows
    raw_to_canonical = {
        raw_index: clause_by_row[row]
        for raw_index, row in enumerate(raw_clause_rows)
    }

    def relabel(node: int) -> int:
        return raw_to_canonical[node] if node < new_size else node

    rotation_rows: list[tuple[int, ...] | None] = [None] * (2 * new_size)
    for raw_node, neighbors in raw_rotation.items():
        node = relabel(raw_node)
        rotation_rows[node] = tuple(relabel(neighbor) for neighbor in neighbors)
    if any(row is None for row in rotation_rows):
        raise AssertionError("vertex sum rotation lost a vertex")
    return canonical, tuple(row for row in rotation_rows if row is not None)


def hex_sum_chain(piece_count: int = 6) -> tuple[Formula, Rotation]:
    if piece_count < 2:
        raise ValueError("the chain needs at least two pieces")
    formula, rotation = _hex_prism_with_rotation()
    base_formula, base_rotation = _hex_prism_with_rotation()
    for _ in range(1, piece_count):
        formula, rotation = _vertex_sum_with_rotation(
            formula,
            rotation,
            base_formula,
            base_rotation,
            permutation=(0, 2, 1),
        )
    faces, euler = _rotation_faces(graph_from_formula(formula), rotation)
    if euler != 2:
        raise AssertionError(
            f"hexagonal 3-sum chain is not planar: faces={faces}, euler={euler}"
        )
    return formula, rotation


def exact_one_truth_table(formula: Formula) -> dict[str, Any]:
    models: list[list[int]] = []
    for assignment in itertools.product((0, 1), repeat=len(formula)):
        if all(
            sum(assignment[variable - 1] for variable in clause) == 1
            for clause in formula
        ):
            models.append(list(assignment))
    return {
        "status": "sat" if models else "unsat",
        "model_count": len(models),
        "witness": models[0] if models else None,
    }


def _fixture_rows() -> list[tuple[str, Formula, dict[str, Any], str]]:
    cube = cube_formula()
    prism = prism_formula(6)
    heawood = heawood_formula()
    chain, chain_rotation = hex_sum_chain(6)
    return [
        (
            "cube",
            cube,
            _rotation_search(graph_from_formula(cube)),
            "planar-control",
        ),
        (
            "hexagonal-prism",
            prism,
            _rotation_search(graph_from_formula(prism)),
            "planar-control",
        ),
        (
            "heawood-fano-control",
            heawood,
            _rotation_search(graph_from_formula(heawood)),
            "nonplanar-control",
        ),
        (
            "hexagonal-3sum-chain-6",
            chain,
            {
                "method": "supplied-rotation",
                "complete": False,
                "planar": True,
                "rotation_systems_checked": 0,
                "maximum_euler_characteristic": 2,
                "euler_characteristic": 2,
                "rotation": [list(row) for row in chain_rotation],
            },
            "planar-negative-control",
        ),
    ]


def build_case(
    name: str,
    formula: Formula,
    planarity: dict[str, Any],
    role: str,
) -> dict[str, Any]:
    profile = cubic_kernel_profile(formula)
    basis = cubic_kernel_basis_width(
        formula,
        maximum_column_subsets=MAX_BASIS_SUBSETS,
    )
    decision = decide_cubic_kernel(formula)
    label = (
        exact_one_truth_table(formula)
        if len(formula) <= 12
        else {
            "status": decision["status"],
            "model_count": None,
            "witness": decision["assignment"],
        }
    )
    structural = structural_summary(formula, planarity)
    candidate = bool(
        structural["simple"]
        and structural["cubic"]
        and structural["bipartite"]
        and structural["connected"]
        and structural["vertex_3_connected"]
        and planarity["planar"]
        and basis["minimum_maximum_pivot_free_support"] > 2
    )
    return {
        "name": name,
        "role": role,
        "formula": [list(row) for row in formula],
        "formula_sha256": formula_digest(formula),
        "variables": len(formula),
        "structural": structural,
        "profile": {
            key: profile[key]
            for key in (
                "rank",
                "nullity",
                "candidate_kernel_vectors",
                "maximum_pivot_free_support",
            )
        },
        "basis": {
            key: basis[key]
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
        },
        "label": label,
        "decision_status": decision["status"],
        "bounded_arity_two_basis_exists": basis[
            "bounded_support_2sat_basis_exists"
        ],
        "candidate_obstruction": candidate,
    }


def build_receipt() -> dict[str, Any]:
    cases = [build_case(*row) for row in _fixture_rows()]
    summary = {
        "cases": len(cases),
        "planar_cases": sum(row["structural"]["planarity"]["planar"] for row in cases),
        "planar_vertex_3_connected_cases": sum(
            row["structural"]["planarity"]["planar"]
            and row["structural"]["vertex_3_connected"]
            for row in cases
        ),
        "nonplanar_controls": sum(
            not row["structural"]["planarity"]["planar"] for row in cases
        ),
        "basis_censuses_complete": all(
            row["basis"]["exact_optimum"] for row in cases
        ),
        "basis_subsets_checked": sum(
            row["basis"]["column_subsets_checked"] for row in cases
        ),
        "basis_columns_found": sum(
            row["basis"]["column_bases_found"] for row in cases
        ),
        "width_two_or_better": sum(
            row["bounded_arity_two_basis_exists"] for row in cases
        ),
        "width_two_obstructions": sum(
            row["candidate_obstruction"] for row in cases
        ),
        "sat": sum(row["decision_status"] == "sat" for row in cases),
        "unsat": sum(row["decision_status"] == "unsat" for row in cases),
        "maximum_variables": max(row["variables"] for row in cases),
        "maximum_nullity": max(row["profile"]["nullity"] for row in cases),
    }
    return {
        "schema": SCHEMA,
        "assessment": {
            "result": "no planar 3-connected width-two obstruction in registered fixtures",
            "scope": (
                "simple cubic bipartite clause-variable incidence graphs; "
                "three planar controls plus one nonplanar control"
            ),
            "p_equals_np": "not established",
            "unrestricted_sat": "not established",
            "basis_claim": (
                "every column basis of every registered fixture was checked "
                "by the exact finite census"
            ),
        },
        "cases": cases,
        "summary": summary,
    }


def run(output: Path = OUTPUT) -> dict[str, Any]:
    receipt = build_receipt()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt["summary"], sort_keys=True))
    return receipt


if __name__ == "__main__":
    run()
