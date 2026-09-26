"""Independent verification of the cubic incidence-kernel evidence receipt.

This module imports neither the implementation nor its runner. It rebuilds all
rational row reductions, exhausts every basis in the registered basis-width
controls, checks every certificate against the source CNF, and exhausts all
574 fixed-gauge cubic formulas through six variables.
"""

from __future__ import annotations

from collections import deque
import hashlib
import itertools
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

SOURCE = Path("_diag/alias_exact_one_decision.json")
RECEIPT = Path("_diag/cubic_kernel_analysis.json")
SCHEMA = "cassifi.cubic-kernel-analysis.v6"
_ALLOWED = (Fraction(-1), Fraction(2))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical_formula(formula: Any) -> tuple[tuple[int, int, int], ...]:
    require(isinstance(formula, list), "formula must be a list")
    size = len(formula)
    require(size >= 3, "formula is too small")
    occurrences = [0] * size
    clauses: list[tuple[int, int, int]] = []
    for raw_clause in formula:
        require(isinstance(raw_clause, list), "clause must be a list")
        require(len(raw_clause) == 3, "clause arity is not three")
        require(
            all(isinstance(value, int) and not isinstance(value, bool) for value in raw_clause),
            "variable identifier is not an integer",
        )
        require(all(1 <= value <= size for value in raw_clause), "variable out of range")
        require(len(set(raw_clause)) == 3, "clause repeats a variable")
        ordered = sorted(raw_clause)
        clause = (ordered[0], ordered[1], ordered[2])
        clauses.append(clause)
        for variable in clause:
            occurrences[variable - 1] += 1
    require(all(count == 3 for count in occurrences), "variable is not cubic")
    return tuple(sorted(clauses))


def formula_sha256(formula: tuple[tuple[int, int, int], ...]) -> str:
    payload = json.dumps(formula, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def matrix_for(formula: tuple[tuple[int, int, int], ...]) -> list[list[Fraction]]:
    size = len(formula)
    matrix = [[Fraction(0) for _ in range(size)] for _ in range(size)]
    for row, clause in enumerate(formula):
        for variable in clause:
            matrix[row][variable - 1] = Fraction(1)
    return matrix


def independent_rref(
    matrix: Sequence[Sequence[Fraction]],
) -> tuple[list[list[Fraction]], tuple[int, ...], int]:
    work = [list(row) for row in matrix]
    size = len(work)
    next_row = 0
    pivots: list[int] = []
    updates = 0
    for column in range(size):
        candidates = [row for row in range(next_row, size) if work[row][column] != 0]
        if not candidates:
            continue
        source_row = candidates[0]
        work[next_row], work[source_row] = work[source_row], work[next_row]
        divisor = work[next_row][column]
        for target in range(column, size):
            work[next_row][target] /= divisor
            updates += 1
        for row in range(size):
            if row == next_row:
                continue
            multiplier = work[row][column]
            if multiplier == 0:
                continue
            for target in range(column, size):
                work[row][target] -= multiplier * work[next_row][target]
                updates += 1
        pivots.append(column)
        next_row += 1
        if next_row == size:
            break
    return work, tuple(pivots), updates


def fraction_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def independent_profile(formula: tuple[tuple[int, int, int], ...]) -> dict[str, Any]:
    rref, pivots, updates = independent_rref(matrix_for(formula))
    pivot_set = set(pivots)
    free = tuple(column for column in range(len(formula)) if column not in pivot_set)
    coefficients = tuple(
        tuple(rref[row][column] for column in free) for row in range(len(pivots))
    )
    supports = tuple(
        sum(value != 0 for value in row) for row in coefficients
    )
    support_histogram = {
        str(support): supports.count(support) for support in sorted(set(supports))
    }
    basis: list[list[str]] = []
    for selected_free in range(len(free)):
        free_values = tuple(
            Fraction(int(index == selected_free)) for index in range(len(free))
        )
        vector = [Fraction(0)] * len(formula)
        for column, value in zip(free, free_values, strict=True):
            vector[column] = value
        for row, pivot in enumerate(pivots):
            vector[pivot] = -sum(
                (
                    coefficient * value
                    for coefficient, value in zip(
                        coefficients[row], free_values, strict=True
                    )
                ),
                start=Fraction(0),
            )
        basis.append([fraction_text(value) for value in vector])

    serialized = {
        "pivot_columns": [column + 1 for column in pivots],
        "free_columns": [column + 1 for column in free],
        "pivot_free_coefficients": [
            [fraction_text(value) for value in row] for row in coefficients
        ],
    }
    system_digest = hashlib.sha256(
        json.dumps(serialized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    numerators = [abs(value.numerator) for row in rref for value in row]
    denominators = [value.denominator for row in rref for value in row]
    return {
        "clauses": len(formula),
        "variables": len(formula),
        "rank": len(pivots),
        "nullity": len(free),
        "candidate_kernel_vectors": 1 << len(free),
        "pivot_columns": [column + 1 for column in pivots],
        "free_columns": [column + 1 for column in free],
        "kernel_basis": basis,
        "maximum_pivot_free_support": max(supports, default=0),
        "pivot_free_support_histogram": support_histogram,
        "fraction_updates": updates,
        "maximum_numerator_bits": max(1, max(numerators, default=0).bit_length()),
        "maximum_denominator_bits": max(1, max(denominators, default=1).bit_length()),
        "system_digest": system_digest,
    }


def independent_basis_system(
    formula: tuple[tuple[int, int, int], ...],
    pivot_columns: tuple[int, ...],
) -> dict[str, Any] | None:
    size = len(formula)
    if (
        len(set(pivot_columns)) != len(pivot_columns)
        or any(column < 0 or column >= size for column in pivot_columns)
    ):
        return None
    pivot_set = set(pivot_columns)
    free = tuple(column for column in range(size) if column not in pivot_set)
    order = pivot_columns + free
    matrix = matrix_for(formula)
    permuted = [[row[column] for column in order] for row in matrix]
    rref, found_pivots, updates = independent_rref(permuted)
    rank = len(pivot_columns)
    if found_pivots != tuple(range(rank)):
        return None
    coefficients = tuple(
        tuple(rref[row][column] for column in range(rank, size))
        for row in range(rank)
    )
    supports = tuple(
        sum(value != 0 for value in row) for row in coefficients
    )
    serialized = {
        "pivot_columns": [column + 1 for column in pivot_columns],
        "free_columns": [column + 1 for column in free],
        "pivot_free_coefficients": [
            [fraction_text(value) for value in row]
            for row in coefficients
        ],
    }
    digest = hashlib.sha256(
        json.dumps(
            serialized, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    numerators = [abs(value.numerator) for row in rref for value in row]
    denominators = [value.denominator for row in rref for value in row]
    return {
        "pivots": pivot_columns,
        "free": free,
        "coefficients": coefficients,
        "supports": supports,
        "fraction_updates": updates,
        "maximum_numerator_bits": max(
            1, max(numerators, default=0).bit_length()
        ),
        "maximum_denominator_bits": max(
            1, max(denominators, default=1).bit_length()
        ),
        "system_digest": digest,
    }


def independent_basis_profile(
    formula: tuple[tuple[int, int, int], ...],
    pivot_columns: tuple[int, ...],
) -> dict[str, Any]:
    system = independent_basis_system(formula, pivot_columns)
    if system is None:
        raise AssertionError("specified columns are not a basis")
    pivots = system["pivots"]
    free = system["free"]
    coefficients = system["coefficients"]
    supports = system["supports"]
    basis: list[list[str]] = []
    for selected_free in range(len(free)):
        free_values = tuple(
            Fraction(int(index == selected_free))
            for index in range(len(free))
        )
        vector = [Fraction(0)] * len(formula)
        for column, value in zip(free, free_values, strict=True):
            vector[column] = value
        for row, pivot in enumerate(pivots):
            vector[pivot] = -sum(
                (
                    coefficient * value
                    for coefficient, value in zip(
                        coefficients[row], free_values, strict=True
                    )
                ),
                start=Fraction(0),
            )
        basis.append([fraction_text(value) for value in vector])
    return {
        "clauses": len(formula),
        "variables": len(formula),
        "rank": len(pivots),
        "nullity": len(free),
        "candidate_kernel_vectors": 1 << len(free),
        "pivot_columns": [column + 1 for column in pivots],
        "free_columns": [column + 1 for column in free],
        "kernel_basis": basis,
        "maximum_pivot_free_support": max(supports, default=0),
        "pivot_free_support_histogram": {
            str(support): supports.count(support)
            for support in sorted(set(supports))
        },
        "fraction_updates": system["fraction_updates"],
        "maximum_numerator_bits": system["maximum_numerator_bits"],
        "maximum_denominator_bits": system["maximum_denominator_bits"],
        "system_digest": system["system_digest"],
    }


def independent_basis_width(
    formula: tuple[tuple[int, int, int], ...],
    *,
    analyze_basis_exchange: bool = False,
) -> dict[str, Any]:
    canonical_profile = independent_profile(formula)
    size = len(formula)
    rank = canonical_profile["rank"]
    histogram: dict[int, int] = {}
    uncovered_histogram: dict[int, int] = {}
    records: dict[tuple[int, ...], tuple[int, int]] = {}
    best_key: tuple[int, int, tuple[int, ...]] | None = None
    best_system: dict[str, Any] | None = None
    basis_count = 0
    for pivot_columns in itertools.combinations(range(size), rank):
        system = independent_basis_system(formula, pivot_columns)
        if system is None:
            continue
        basis_count += 1
        supports = system["supports"]
        width = max(supports, default=0)
        uncovered = sum(support > 2 for support in supports)
        histogram[width] = histogram.get(width, 0) + 1
        uncovered_histogram[uncovered] = (
            uncovered_histogram.get(uncovered, 0) + 1
        )
        if analyze_basis_exchange:
            records[pivot_columns] = (width, uncovered)
        key = (width, sum(supports), pivot_columns)
        if best_key is None or key < best_key:
            best_key = key
            best_system = system
    if best_key is None:
        raise AssertionError("basis-width search found no basis")
    if best_system is None:
        raise AssertionError("basis-width search lost its witness")
    supports = best_system["supports"]
    witness = {
        "pivot_columns": [
            column + 1 for column in best_system["pivots"]
        ],
        "free_columns": [
            column + 1 for column in best_system["free"]
        ],
        "pivot_free_coefficients": [
            [fraction_text(value) for value in row]
            for row in best_system["coefficients"]
        ],
        "pivot_free_supports": list(supports),
        "maximum_pivot_free_support": best_key[0],
        "total_pivot_free_support": best_key[1],
        "maximum_fundamental_cocircuit_size": best_key[0] + 1,
        "system_digest": best_system["system_digest"],
    }
    result = {
        "clauses": size,
        "variables": size,
        "rank": rank,
        "nullity": size - rank,
        "column_subsets_checked": math.comb(size, rank),
        "column_bases_found": basis_count,
        "basis_maximum_support_histogram": {
            str(width): histogram[width] for width in sorted(histogram)
        },
        "uncovered_pivot_count_histogram": {
            str(count): uncovered_histogram[count]
            for count in sorted(uncovered_histogram)
        },
        "bases_at_optimum": histogram[best_key[0]],
        "bases_with_width_at_most_two": sum(
            count for width, count in histogram.items() if width <= 2
        ),
        "maximum_maximum_pivot_free_support": max(histogram),
        "exact_optimum": True,
        "canonical_pivot_columns": canonical_profile["pivot_columns"],
        "canonical_maximum_pivot_free_support": canonical_profile[
            "maximum_pivot_free_support"
        ],
        "minimum_maximum_pivot_free_support": best_key[0],
        "minimum_total_support_at_optimum": best_key[1],
        "minimum_uncovered_pivots": min(uncovered_histogram),
        "improves_canonical_basis": (
            best_key[0]
            < canonical_profile["maximum_pivot_free_support"]
        ),
        "bounded_support_2sat_basis_exists": best_key[0] <= 2,
        "basis_exchange": (
            independent_basis_exchange_profile(
                size=size,
                canonical_basis=tuple(
                    column - 1
                    for column in canonical_profile["pivot_columns"]
                ),
                records=records,
            )
            if analyze_basis_exchange
            else None
        ),
        "witness": witness,
    }
    result["certificate_digest"] = hashlib.sha256(
        json.dumps(
            result, sort_keys=True, separators=(",", ":")
        ).encode("ascii")
    ).hexdigest()
    return result


def independent_vector_rank(
    vectors: tuple[tuple[Fraction, ...], ...],
) -> int:
    if not vectors:
        return 0
    matrix = [
        [vectors[column][row] for column in range(len(vectors))]
        for row in range(len(vectors[0]))
    ]
    row_count = len(matrix)
    column_count = len(vectors)
    pivot_row = 0
    for column in range(column_count):
        source = next(
            (
                row
                for row in range(pivot_row, row_count)
                if matrix[row][column] != 0
            ),
            None,
        )
        if source is None:
            continue
        matrix[pivot_row], matrix[source] = matrix[source], matrix[pivot_row]
        divisor = matrix[pivot_row][column]
        for target in range(column, column_count):
            matrix[pivot_row][target] /= divisor
        for row in range(row_count):
            if row == pivot_row:
                continue
            multiplier = matrix[row][column]
            if multiplier == 0:
                continue
            for target in range(column, column_count):
                matrix[row][target] -= multiplier * matrix[pivot_row][target]
        pivot_row += 1
        if pivot_row == row_count:
            break
    return pivot_row


def independent_zero_valid_basis(
    formula: tuple[tuple[int, int, int], ...],
    assignment: list[int],
) -> dict[str, Any]:
    profile = independent_profile(formula)
    canonical_pivots = tuple(
        column - 1 for column in profile["pivot_columns"]
    )
    canonical_system = independent_basis_system(formula, canonical_pivots)
    if canonical_system is None:
        raise AssertionError("canonical basis is missing")
    nullity = profile["nullity"]
    canonical_free = canonical_system["free"]
    coefficients = canonical_system["coefficients"]
    coordinate_vectors: list[tuple[Fraction, ...]] = []
    free_positions = {
        column: index for index, column in enumerate(canonical_free)
    }
    pivot_positions = {
        column: index for index, column in enumerate(canonical_pivots)
    }
    for column in range(len(formula)):
        if column in free_positions:
            free_index = free_positions[column]
            coordinate_vectors.append(
                tuple(
                    Fraction(int(index == free_index))
                    for index in range(nullity)
                )
            )
        else:
            coordinate_vectors.append(
                tuple(
                    -value
                    for value in coefficients[pivot_positions[column]]
                )
            )

    selected_columns: list[int] = []
    selected_vectors: list[tuple[Fraction, ...]] = []
    for column, value in enumerate(assignment):
        if value != 0:
            continue
        candidates = tuple((*selected_vectors, coordinate_vectors[column]))
        if independent_vector_rank(candidates) == len(candidates):
            selected_columns.append(column)
            selected_vectors.append(coordinate_vectors[column])
            if len(selected_columns) == nullity:
                break
    require(
        len(selected_columns) == nullity,
        "zero coordinates do not span the dual kernel representation",
    )
    selected_set = set(selected_columns)
    pivot_columns = tuple(
        column for column in range(len(formula))
        if column not in selected_set
    )
    system = independent_basis_system(formula, pivot_columns)
    if system is None:
        raise AssertionError("zero-valid complement is not a column basis")

    vector = [Fraction(0)] * len(formula)
    for column in system["free"]:
        vector[column] = Fraction(-1)
    for row, pivot in enumerate(system["pivots"]):
        vector[pivot] = sum(system["coefficients"][row], start=Fraction(0))
    expected = [Fraction(3 * value - 1) for value in assignment]
    require(vector == expected, "zero-valid basis reconstructed another vector")

    supports = system["supports"]
    result = {
        "clauses": len(formula),
        "variables": len(formula),
        "rank": len(pivot_columns),
        "nullity": nullity,
        "zero_assignment_columns": sum(value == 0 for value in assignment),
        "zero_coordinate_rank": len(selected_columns),
        "pivot_columns": [column + 1 for column in pivot_columns],
        "free_columns": [column + 1 for column in selected_columns],
        "pivot_free_supports": list(supports),
        "maximum_pivot_free_support": max(supports, default=0),
        "reconstructed_kernel_vector": [int(value) for value in vector],
        "system_digest": system["system_digest"],
    }
    result["certificate_digest"] = hashlib.sha256(
        json.dumps(
            result, sort_keys=True, separators=(",", ":")
        ).encode("ascii")
    ).hexdigest()
    return result


def independent_dual_triangle_profile(
    formula: tuple[tuple[int, int, int], ...],
) -> dict[str, Any]:
    canonical_profile = independent_profile(formula)
    pivots = tuple(
        column - 1 for column in canonical_profile["pivot_columns"]
    )
    system = independent_basis_system(formula, pivots)
    if system is None:
        raise AssertionError("canonical columns do not form a basis")
    free = system["free"]
    dual_rank = len(free)
    vectors = [[Fraction(0)] * dual_rank for _ in formula]
    for coordinate, column in enumerate(free):
        vectors[column][coordinate] = Fraction(1)
    for row, column in enumerate(system["pivots"]):
        vectors[column] = list(system["coefficients"][row])
    columns = tuple(tuple(vector) for vector in vectors)

    singleton_ranks = [
        independent_vector_rank((vector,)) for vector in columns
    ]
    loops = [
        index for index, rank in enumerate(singleton_ranks) if rank == 0
    ]
    parallel_pairs: list[tuple[int, int]] = []
    independent_pairs: set[tuple[int, int]] = set()
    for pair in itertools.combinations(range(len(columns)), 2):
        left, right = pair
        rank = independent_vector_rank((columns[left], columns[right]))
        if singleton_ranks[left] == singleton_ranks[right] == 1 and rank == 1:
            parallel_pairs.append(pair)
        elif rank == 2:
            independent_pairs.add(pair)
    triangles: list[tuple[int, int, int]] = []
    for triple in itertools.combinations(range(len(columns)), 3):
        if not all(
            tuple(sorted(pair)) in independent_pairs
            for pair in itertools.combinations(triple, 2)
        ):
            continue
        if independent_vector_rank(
            tuple(columns[index] for index in triple)
        ) == 2:
            triangles.append(triple)

    degrees = [0] * len(columns)
    for loop in loops:
        degrees[loop] += 1
    for pair in parallel_pairs:
        for element in pair:
            degrees[element] += 1
    for triple in triangles:
        for element in triple:
            degrees[element] += 1
    clause_sets = {
        tuple(variable - 1 for variable in clause) for clause in formula
    }
    triangle_set = set(triangles)
    serialized = {
        "loops": [element + 1 for element in loops],
        "parallel_pairs": [
            [left + 1, right + 1] for left, right in parallel_pairs
        ],
        "triangles": [
            [first + 1, second + 1, third + 1]
            for first, second, third in triangles
        ],
    }
    return {
        "elements": len(columns),
        "dual_rank": dual_rank,
        "loops": serialized["loops"],
        "parallel_pairs": serialized["parallel_pairs"],
        "triangles": serialized["triangles"],
        "loop_count": len(loops),
        "parallel_pair_count": len(parallel_pairs),
        "triangle_count": len(triangles),
        "small_circuit_count": (
            len(loops) + len(parallel_pairs) + len(triangles)
        ),
        "clause_cocircuit_triangles": len(clause_sets & triangle_set),
        "additional_triangles": len(triangle_set - clause_sets),
        "small_circuit_degree_histogram": {
            str(degree): degrees.count(degree)
            for degree in sorted(set(degrees))
        },
        "elements_without_small_circuit": [
            index + 1
            for index, degree in enumerate(degrees)
            if degree == 0
        ],
        "constraint_digest": hashlib.sha256(
            json.dumps(
                serialized, sort_keys=True, separators=(",", ":")
            ).encode("ascii")
        ).hexdigest(),
    }


def independent_basis_exchange_profile(
    *,
    size: int,
    canonical_basis: tuple[int, ...],
    records: dict[tuple[int, ...], tuple[int, int]],
) -> dict[str, Any]:
    bases = sorted(records)
    adjacency = {basis: set() for basis in bases}
    edge_count = 0
    for index, left in enumerate(bases):
        left_set = set(left)
        for right in bases[index + 1 :]:
            if len(left_set.symmetric_difference(right)) != 2:
                continue
            adjacency[left].add(right)
            adjacency[right].add(left)
            edge_count += 1

    optimum = min(width for width, _ in records.values())
    optimum_bases = {
        basis for basis, (width, _) in records.items() if width == optimum
    }
    distances = {basis: 0 for basis in optimum_bases}
    frontier = deque(sorted(optimum_bases))
    while frontier:
        basis = frontier.popleft()
        for neighbor in sorted(adjacency[basis]):
            if neighbor not in distances:
                distances[neighbor] = distances[basis] + 1
                frontier.append(neighbor)
    require(len(distances) == len(records), "basis exchange graph disconnected")

    strict_reachable = set(optimum_bases)
    for width in sorted({value[0] for value in records.values()}):
        if width == optimum:
            continue
        for basis in bases:
            if records[basis][0] != width:
                continue
            if any(
                records[neighbor][0] < width
                and neighbor in strict_reachable
                for neighbor in adjacency[basis]
            ):
                strict_reachable.add(basis)

    nonincreasing_reachable: set[tuple[int, ...]] = set()
    for width in sorted({value[0] for value in records.values()}):
        allowed = {
            basis
            for basis, (candidate_width, _) in records.items()
            if candidate_width <= width
        }
        reached = set(optimum_bases)
        frontier = deque(sorted(optimum_bases))
        while frontier:
            basis = frontier.popleft()
            for neighbor in sorted(adjacency[basis]):
                if neighbor in allowed and neighbor not in reached:
                    reached.add(neighbor)
                    frontier.append(neighbor)
        nonincreasing_reachable.update(
            basis for basis in reached if records[basis][0] == width
        )

    local_minima = [
        basis
        for basis in bases
        if records[basis][0] > optimum
        and not any(
            records[neighbor][0] < records[basis][0]
            for neighbor in adjacency[basis]
        )
    ]
    first_trap = local_minima[0] if local_minima else None
    graph_rows = [
        {
            "basis": [column + 1 for column in basis],
            "width": records[basis][0],
            "uncovered": records[basis][1],
            "neighbors": [
                [column + 1 for column in neighbor]
                for neighbor in sorted(adjacency[basis])
            ],
        }
        for basis in bases
    ]
    return {
        "basis_nodes": len(records),
        "exchange_edges": edge_count,
        "connected": True,
        "optimum_width": optimum,
        "optimum_basis_nodes": len(optimum_bases),
        "canonical_distance_to_optimum": distances[canonical_basis],
        "maximum_distance_to_optimum": max(distances.values(), default=0),
        "distance_to_optimum_histogram": {
            str(distance): list(distances.values()).count(distance)
            for distance in sorted(set(distances.values()))
        },
        "exchange_degree_histogram": {
            str(degree): sum(
                len(neighbors) == degree for neighbors in adjacency.values()
            )
            for degree in sorted(
                {len(neighbors) for neighbors in adjacency.values()}
            )
        },
        "nonglobal_local_minima": len(local_minima),
        "strict_descent_reaches_optimum": len(strict_reachable),
        "nonincreasing_reaches_optimum": len(nonincreasing_reachable),
        "first_nonglobal_local_minimum": (
            None
            if first_trap is None
            else {
                "pivot_columns": [column + 1 for column in first_trap],
                "free_columns": [
                    column + 1
                    for column in range(size)
                    if column not in first_trap
                ],
                "width": records[first_trap][0],
                "uncovered_pivots": records[first_trap][1],
            }
        ),
        "graph_digest": hashlib.sha256(
            json.dumps(
                graph_rows, sort_keys=True, separators=(",", ":")
            ).encode("ascii")
        ).hexdigest(),
    }


def connected(formula: tuple[tuple[int, int, int], ...]) -> bool:
    size = len(formula)
    adjacency = [[] for _ in range(2 * size)]
    for clause_index, clause in enumerate(formula):
        for variable in clause:
            node = size + variable - 1
            adjacency[clause_index].append(node)
            adjacency[node].append(clause_index)
    visited = {0}
    pending = [0]
    while pending:
        node = pending.pop()
        for neighbor in adjacency[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                pending.append(neighbor)
    return len(visited) == 2 * size


def satisfies(
    formula: tuple[tuple[int, int, int], ...], assignment: Sequence[int]
) -> bool:
    return len(assignment) == len(formula) and all(
        value in (0, 1) for value in assignment
    ) and all(
        sum(assignment[variable - 1] for variable in clause) == 1
        for clause in formula
    )

def independently_classify_relation(
    tuples: Sequence[tuple[int, ...]], arity: int
) -> dict[str, bool]:
    members = set(tuples)

    def closed(
        operation: Any, operand_count: int
    ) -> bool:
        return all(
            tuple(
                operation(*(operands[index][coordinate] for index in range(operand_count)))
                for coordinate in range(arity)
            )
            in members
            for operands in itertools.product(tuples, repeat=operand_count)
        )

    return {
        "zero_valid": (0,) * arity in members,
        "one_valid": (1,) * arity in members,
        "horn": closed(lambda left, right: left & right, 2),
        "dual_horn": closed(lambda left, right: left | right, 2),
        "bijunctive": closed(
            lambda left, middle, right: int(left + middle + right >= 2), 3
        ),
        "affine": closed(lambda left, middle, right: left ^ middle ^ right, 3),
    }


def independent_relation_language(profile: dict[str, Any]) -> dict[str, Any]:
    maximum_support = profile["maximum_pivot_free_support"]
    if maximum_support > 3:
        return {
            "analyzed": False,
            "maximum_supported_arity": 3,
            "common_schaefer_classes": None,
            "support_histogram": profile["pivot_free_support_histogram"],
            "ternary_relations": None,
        }

    basis = [
        [Fraction(value) for value in vector]
        for vector in profile["kernel_basis"]
    ]
    relations = []
    for pivot_column in profile["pivot_columns"]:
        coefficients = [vector[pivot_column - 1] for vector in basis]
        active = tuple(
            index
            for index, coefficient in enumerate(coefficients)
            if coefficient != 0
        )
        allowed: list[tuple[int, ...]] = []
        for bits in itertools.product((0, 1), repeat=len(active)):
            value = Fraction(0)
            for index, bit in zip(active, bits, strict=True):
                value += coefficients[index] * (3 * bit - 1)
            if value == -1 or value == 2:
                allowed.append(bits)
        relations.append(
            {
                "pivot_column": pivot_column,
                "free_columns": [
                    profile["free_columns"][index] for index in active
                ],
                "coefficients": [str(coefficients[index]) for index in active],
                "allowed_tuples": [list(bits) for bits in allowed],
                "properties": independently_classify_relation(
                    allowed, len(active)
                ),
            }
        )

    class_names = (
        "zero_valid",
        "one_valid",
        "horn",
        "dual_horn",
        "bijunctive",
        "affine",
    )
    return {
        "analyzed": True,
        "maximum_supported_arity": 3,
        "common_schaefer_classes": [
            class_name
            for class_name in class_names
            if all(
                relation["properties"][class_name] for relation in relations
            )
        ],
        "support_histogram": profile["pivot_free_support_histogram"],
        "ternary_relations": [
            relation for relation in relations if len(relation["free_columns"]) == 3
        ],
    }


def brute_status(formula: tuple[tuple[int, int, int], ...]) -> str:
    for assignment in itertools.product((0, 1), repeat=len(formula)):
        if satisfies(formula, assignment):
            return "sat"
    return "unsat"


def independent_kernel_status(
    formula: tuple[tuple[int, int, int], ...]
) -> tuple[str, int]:
    rref, pivots, _ = independent_rref(matrix_for(formula))
    free = tuple(column for column in range(len(formula)) if column not in set(pivots))
    if not free:
        return "unsat", 0
    if len(formula) % 3:
        return "unsat", 0
    checked = 0
    for free_values in itertools.product(_ALLOWED, repeat=len(free)):
        checked += 1
        vector = [Fraction(0)] * len(formula)
        for column, value in zip(free, free_values, strict=True):
            vector[column] = value
        for row, pivot in enumerate(pivots):
            vector[pivot] = -sum(
                (rref[row][column] * vector[column] for column in free),
                start=Fraction(0),
            )
        if all(value in _ALLOWED for value in vector):
            return "sat", checked
    return "unsat", checked

def independent_enumeration_receipt(
    formula: tuple[tuple[int, int, int], ...],
) -> tuple[str, int, str, list[int] | None]:
    rref, pivots, _ = independent_rref(matrix_for(formula))
    free = tuple(column for column in range(len(formula)) if column not in set(pivots))
    rejected = hashlib.sha256()
    checked = 0
    for free_values in itertools.product(_ALLOWED, repeat=len(free)):
        checked += 1
        vector = [Fraction(0)] * len(formula)
        for column, value in zip(free, free_values, strict=True):
            vector[column] = value
        for row, pivot in enumerate(pivots):
            vector[pivot] = -sum(
                (rref[row][column] * vector[column] for column in free),
                start=Fraction(0),
            )
        invalid = next(
            (
                (column, vector[column])
                for column in pivots
                if vector[column] not in _ALLOWED
            ),
            None,
        )
        if invalid is None:
            assignment = [int((value + 1) / 3) for value in vector]
            return "sat", checked, rejected.hexdigest(), assignment
        column, value = invalid
        rejected.update(
            (
                ",".join(fraction_text(item) for item in free_values)
                + f"|{column + 1}|{fraction_text(value)}\n"
            ).encode("ascii")
        )
    return "unsat", checked, rejected.hexdigest(), None

def independent_binary_relations(
    formula: tuple[tuple[int, int, int], ...],
    pivot_columns: tuple[int, ...] | None = None,
) -> tuple[list[tuple[int, int]], tuple[int, ...], int | None]:
    if pivot_columns is None:
        rref, pivots, _ = independent_rref(matrix_for(formula))
        pivot_set = set(pivots)
        free = tuple(
            column for column in range(len(formula))
            if column not in pivot_set
        )
        coefficient_rows = tuple(
            tuple(rref[row][column] for column in free)
            for row in range(len(pivots))
        )
    else:
        system = independent_basis_system(formula, pivot_columns)
        if system is None:
            raise AssertionError("2-SAT verifier received a nonbasis")
        pivots = system["pivots"]
        free = system["free"]
        coefficient_rows = system["coefficients"]
    clauses: list[tuple[int, int]] = []
    empty_relation_pivot: int | None = None
    for row_index, pivot in enumerate(pivots):
        coefficients = coefficient_rows[row_index]
        support = tuple(
            index for index, coefficient in enumerate(coefficients) if coefficient
        )
        require(len(support) <= 2, "binary relation verifier received wider support")
        for bits in itertools.product((0, 1), repeat=len(support)):
            pivot_value = -sum(
                (
                    coefficients[index] * Fraction(3 * bit - 1)
                    for index, bit in zip(support, bits, strict=True)
                ),
                start=Fraction(0),
            )
            if pivot_value in _ALLOWED:
                continue
            literals = tuple(
                index + 1 if bit == 0 else -(index + 1)
                for index, bit in zip(support, bits, strict=True)
            )
            if not literals:
                empty_relation_pivot = pivot + 1
                break
            clauses.append(
                (literals[0], literals[0] if len(literals) == 1 else literals[1])
            )
        if empty_relation_pivot is not None:
            break
    return sorted(set(clauses)), free, empty_relation_pivot


def implication_conflict(
    variable_count: int, clauses: Sequence[tuple[int, int]]
) -> int | None:
    def node(literal: int) -> int:
        return 2 * (abs(literal) - 1) + int(literal < 0)

    graph = [[] for _ in range(2 * variable_count)]
    for left, right in clauses:
        left_node = node(left)
        right_node = node(right)
        graph[left_node ^ 1].append(right_node)
        graph[right_node ^ 1].append(left_node)

    reachability: list[set[int]] = []
    for source in range(len(graph)):
        reached = {source}
        pending = [source]
        while pending:
            current = pending.pop()
            for target in graph[current]:
                if target not in reached:
                    reached.add(target)
                    pending.append(target)
        reachability.append(reached)
    for variable in range(variable_count):
        positive = 2 * variable
        negative = positive + 1
        if negative in reachability[positive] and positive in reachability[negative]:
            return variable
    return None


def verify_two_sat_certificate(
    name: str,
    formula: tuple[tuple[int, int, int], ...],
    decision: dict[str, Any],
    pivot_columns: tuple[int, ...] | None = None,
) -> None:
    clauses, free, empty_pivot = independent_binary_relations(
        formula, pivot_columns
    )
    certificate = decision["two_sat_certificate"]
    require(isinstance(certificate, dict), f"{name}: missing 2-SAT certificate")
    expected_digest = hashlib.sha256(
        json.dumps(clauses, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    require(certificate["free_variables"] == len(free), f"{name}: 2-SAT width mismatch")
    require(certificate["clauses"] == len(clauses), f"{name}: 2-SAT clause count mismatch")
    require(certificate["clause_digest"] == expected_digest, f"{name}: 2-SAT digest mismatch")
    require(certificate["empty_relation_pivot"] == empty_pivot, f"{name}: empty relation mismatch")
    require(decision["candidates_checked"] == 0, f"{name}: 2-SAT used enumeration")
    require(decision["rejection_digest"] is None, f"{name}: unexpected rejection digest")

    bits = certificate["satisfying_free_bits"]
    if empty_pivot is not None:
        require(bits is None, f"{name}: empty relation has an assignment")
        require(decision["reason"] == "forced_zero_pivot", f"{name}: forced-zero reason mismatch")
        require(decision["status"] == "unsat", f"{name}: forced-zero status mismatch")
        require(certificate["conflict_free_column"] is None, f"{name}: false conflict column")
        require(decision["assignment"] is None, f"{name}: false forced-zero assignment")
        require(decision["kernel_vector"] is None, f"{name}: false forced-zero vector")
        return

    conflict = implication_conflict(len(free), clauses)
    expected_conflict_column = None if conflict is None else free[conflict] + 1
    require(
        certificate["conflict_free_column"] == expected_conflict_column,
        f"{name}: implication conflict mismatch",
    )
    if bits is None:
        require(conflict is not None, f"{name}: satisfiable 2-SAT reported UNSAT")
        require(
            decision["reason"] == "bounded_support_2sat_unsat",
            f"{name}: bounded-support UNSAT reason mismatch",
        )
        require(decision["status"] == "unsat", f"{name}: bounded-support status mismatch")
        require(decision["assignment"] is None, f"{name}: false 2-SAT UNSAT assignment")
        require(decision["kernel_vector"] is None, f"{name}: false 2-SAT UNSAT vector")
        return

    require(conflict is None, f"{name}: conflicting 2-SAT has an assignment")
    require(
        len(bits) == len(free) and all(bit in (0, 1) for bit in bits),
        f"{name}: malformed free assignment",
    )
    require(
        all(
            (bits[abs(left) - 1] == int(left > 0))
            or (bits[abs(right) - 1] == int(right > 0))
            for left, right in clauses
        ),
        f"{name}: free assignment violates a 2-SAT clause",
    )
    require(
        decision["reason"] == "bounded_support_2sat_sat",
        f"{name}: bounded-support SAT reason mismatch",
    )
    require(decision["status"] == "sat", f"{name}: bounded-support status mismatch")
    require(satisfies(formula, decision["assignment"]), f"{name}: bad 2-SAT witness")
    if pivot_columns is None:
        rref, pivots, _ = independent_rref(matrix_for(formula))
        coefficient_rows = tuple(
            tuple(rref[row][column] for column in free)
            for row in range(len(pivots))
        )
    else:
        system = independent_basis_system(formula, pivot_columns)
        if system is None:
            raise AssertionError(f"{name}: selected columns are not a basis")
        pivots = system["pivots"]
        coefficient_rows = system["coefficients"]
    free_values = tuple(Fraction(3 * bit - 1) for bit in bits)
    vector = [Fraction(0)] * len(formula)
    for column, value in zip(free, free_values, strict=True):
        vector[column] = value
    for row, pivot in enumerate(pivots):
        vector[pivot] = -sum(
            (
                coefficient * value
                for coefficient, value in zip(
                    coefficient_rows[row], free_values, strict=True
                )
            ),
            start=Fraction(0),
        )
    expected_vector = [int(value) for value in vector]
    expected_assignment = [int((value + 1) / 3) for value in vector]
    require(
        decision["kernel_vector"] == expected_vector,
        f"{name}: 2-SAT kernel reconstruction mismatch",
    )
    require(
        decision["assignment"] == expected_assignment,
        f"{name}: 2-SAT assignment reconstruction mismatch",
    )


def verify_decision(
    name: str,
    formula: tuple[tuple[int, int, int], ...],
    profile: dict[str, Any],
    decision: dict[str, Any],
    pivot_columns: tuple[int, ...] | None = None,
) -> None:
    for key in (
        "clauses",
        "variables",
        "rank",
        "nullity",
        "pivot_columns",
        "free_columns",
        "candidate_kernel_vectors",
        "maximum_pivot_free_support",
        "pivot_free_support_histogram",
        "system_digest",
        "maximum_numerator_bits",
        "maximum_denominator_bits",
    ):
        require(decision[key] == profile[key], f"{name}: decision {key} mismatch")

    reason = decision["reason"]
    if reason == "full_rank":
        require(profile["rank"] == len(formula), f"{name}: false full-rank reason")
        require(decision["status"] == "unsat", f"{name}: full-rank status mismatch")
        require(decision["candidates_checked"] == 0, f"{name}: full-rank work mismatch")
        require(decision["two_sat_certificate"] is None, f"{name}: false 2-SAT certificate")
        require(decision["assignment"] is None, f"{name}: false full-rank assignment")
        require(decision["kernel_vector"] is None, f"{name}: false full-rank vector")
        require(decision["rejection_digest"] is None, f"{name}: false full-rank digest")
    elif reason == "cardinality_not_divisible_by_three":
        require(len(formula) % 3 != 0, f"{name}: false cardinality reason")
        require(decision["status"] == "unsat", f"{name}: cardinality status mismatch")
        require(decision["candidates_checked"] == 0, f"{name}: cardinality work mismatch")
        require(decision["two_sat_certificate"] is None, f"{name}: false 2-SAT certificate")
        require(decision["assignment"] is None, f"{name}: false cardinality assignment")
        require(decision["kernel_vector"] is None, f"{name}: false cardinality vector")
        require(decision["rejection_digest"] is None, f"{name}: false cardinality digest")
    elif reason in (
        "forced_zero_pivot",
        "bounded_support_2sat_sat",
        "bounded_support_2sat_unsat",
    ):
        require(
            profile["maximum_pivot_free_support"] <= 2,
            f"{name}: 2-SAT applied beyond binary support",
        )
        verify_two_sat_certificate(
            name, formula, decision, pivot_columns
        )
    elif reason in ("alphabet_kernel_vector", "alphabet_exhausted"):
        require(
            profile["maximum_pivot_free_support"] > 2,
            f"{name}: enumeration bypassed the polynomial support case",
        )
        require(
            pivot_columns is None,
            f"{name}: noncanonical enumerated decision is not expected",
        )
        status, checked, digest, assignment = independent_enumeration_receipt(formula)
        require(status == decision["status"], f"{name}: independent enumeration verdict mismatch")
        require(checked == decision["candidates_checked"], f"{name}: enumeration count mismatch")
        require(digest == decision["rejection_digest"], f"{name}: rejection digest mismatch")
        require(assignment == decision["assignment"], f"{name}: enumerated assignment mismatch")
        require(decision["two_sat_certificate"] is None, f"{name}: false 2-SAT certificate")
        if reason == "alphabet_exhausted":
            require(
                checked == (1 << profile["nullity"]),
                f"{name}: incomplete alphabet exhaustion",
            )
            require(decision["kernel_vector"] is None, f"{name}: false exhausted vector")
        else:
            if assignment is None:
                raise AssertionError(f"{name}: SAT enumeration has no assignment")
            require(satisfies(formula, assignment), f"{name}: bad SAT assignment")
            vector = decision["kernel_vector"]
            require(all(value in (-1, 2) for value in vector), f"{name}: bad kernel alphabet")
            require(
                all(
                    sum(row[i] * vector[i] for i in range(len(vector))) == 0
                    for row in matrix_for(formula)
                ),
                f"{name}: vector is outside the kernel",
            )
    else:
        raise AssertionError(f"{name}: unknown decision reason {reason!r}")


def exhaustive_small() -> dict[str, int]:
    counts = {
        "formulas": 0,
        "sat": 0,
        "unsat": 0,
        "assignments": 0,
        "basis_nodes": 0,
        "basis_exchange_edges": 0,
        "width_two_basis_formulas": 0,
        "mixed_width_formulas": 0,
        "strict_descent_trap_formulas": 0,
        "nonincreasing_trap_formulas": 0,
    }
    by_size: dict[int, tuple[int, int, int]] = {}
    for size in range(3, 7):
        identity = tuple(range(size))
        permutations = tuple(itertools.permutations(range(size)))
        formulas: set[tuple[tuple[int, int, int], ...]] = set()
        for second in permutations:
            if any(second[row] == identity[row] for row in range(size)):
                continue
            for third in permutations:
                if any(
                    third[row] in (identity[row], second[row])
                    for row in range(size)
                ):
                    continue
                raw_formula = [
                    sorted((row + 1, second[row] + 1, third[row] + 1))
                    for row in range(size)
                ]
                formula = tuple(
                    (clause[0], clause[1], clause[2])
                    for clause in sorted(raw_formula)
                )
                formulas.add(formula)

        local_sat = 0
        local_unsat = 0
        for formula in formulas:
            status = brute_status(formula)
            kernel_status, _ = independent_kernel_status(formula)
            require(status == kernel_status, f"n={size}: kernel verdict mismatch")
            basis_width = independent_basis_width(
                formula, analyze_basis_exchange=True
            )
            exchange = basis_width["basis_exchange"]
            require(
                exchange["connected"],
                f"n={size}: disconnected basis-exchange graph",
            )
            counts["basis_nodes"] += exchange["basis_nodes"]
            counts["basis_exchange_edges"] += exchange["exchange_edges"]
            counts["width_two_basis_formulas"] += int(
                basis_width["minimum_maximum_pivot_free_support"] <= 2
            )
            counts["mixed_width_formulas"] += int(
                len(basis_width["basis_maximum_support_histogram"]) > 1
            )
            counts["strict_descent_trap_formulas"] += int(
                exchange["strict_descent_reaches_optimum"]
                < exchange["basis_nodes"]
            )
            counts["nonincreasing_trap_formulas"] += int(
                exchange["nonincreasing_reaches_optimum"]
                < exchange["basis_nodes"]
            )
            for assignment in itertools.product((0, 1), repeat=size):
                vector = tuple(3 * value - 1 for value in assignment)
                matrix = matrix_for(formula)
                in_kernel = all(
                    sum(row[index] * vector[index] for index in range(size)) == 0
                    for row in matrix
                )
                require(
                    in_kernel == satisfies(formula, assignment),
                    f"n={size}: pointwise kernel equivalence failed",
                )
                counts["assignments"] += 1
            if status == "sat":
                local_sat += 1
            else:
                local_unsat += 1
        by_size[size] = (len(formulas), local_sat, local_unsat)
        counts["formulas"] += len(formulas)
        counts["sat"] += local_sat
        counts["unsat"] += local_unsat

    require(
        by_size == {
            3: (1, 1, 0),
            4: (1, 0, 1),
            5: (22, 0, 22),
            6: (550, 520, 30),
        },
        "exhaustive fixed-gauge inventory changed",
    )
    return counts


def main() -> None:
    source_raw = SOURCE.read_bytes()
    source = json.loads(source_raw)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(receipt.get("schema") == SCHEMA, "schema mismatch")
    require(
        receipt.get("source_receipt_sha256") == hashlib.sha256(source_raw).hexdigest(),
        "source receipt digest mismatch",
    )

    source_groups: dict[str, tuple[str, set[str]]] = {}
    for source_case in source["cases"]:
        if len(source_case["certificate"]["cubic_variables"]) != source_case["variables"]:
            continue
        formula = canonical_formula(source_case["formula"])
        digest = formula_sha256(formula)
        status = source_case["certificate"]["status"]
        if digest not in source_groups:
            source_groups[digest] = (status, set())
        require(source_groups[digest][0] == status, "source formula verdict conflict")
        source_groups[digest][1].add(source_case["name"])

    audited: list[dict[str, Any]] = []
    for row in receipt["cases"]:
        name = row["name"]
        formula = canonical_formula(row["formula"])
        require(row["formula"] == [list(clause) for clause in formula], f"{name}: noncanonical formula")
        require(row["formula_sha256"] == formula_sha256(formula), f"{name}: formula digest mismatch")
        require(row["connected"] == connected(formula), f"{name}: connectivity mismatch")
        profile = independent_profile(formula)
        require(row["profile"] == profile, f"{name}: exact profile mismatch")
        require(
            row["relation_language"] == independent_relation_language(profile),
            f"{name}: relation-language profile mismatch",
        )

        if row["category"] == "prior_pure_cubic":
            require(row["formula_sha256"] in source_groups, f"{name}: unknown source formula")
            source_status, source_names = source_groups[row["formula_sha256"]]
            require(row["expected_status"] == source_status, f"{name}: source status mismatch")
            require(
                set(row["provenance"]["source_case_names"]) == source_names,
                f"{name}: source provenance mismatch",
            )

        decision = row["decision"]
        require(isinstance(decision, dict), f"{name}: missing decision certificate")
        verify_decision(name, formula, profile, decision)
        require(decision["status"] == row["expected_status"], f"{name}: verdict mismatch")
        if row["expected_status"] == "sat":
            witness = row["construction_witness"]
            if witness is None:
                witness = decision["assignment"]
            require(satisfies(formula, witness), f"{name}: SAT witness mismatch")

        if row["category"].startswith("connected_linear_nullity"):
            provenance = row["provenance"]
            blocks = provenance["k33_blocks"]
            core = provenance["crown_core_vertices_per_side"]
            links = provenance["rank_one_switches"]
            require(row["connected"], f"{name}: family is disconnected")
            require(
                len(formula) == 3 * blocks + core,
                f"{name}: family size mismatch",
            )
            require(
                provenance["initial_block_diagonal_nullity"] == 2 * blocks,
                f"{name}: initial nullity mismatch",
            )
            require(
                provenance["proved_nullity_lower_bound"] == 2 * blocks - links,
                f"{name}: rank-one lower bound mismatch",
            )
            require(
                profile["nullity"] >= provenance["proved_nullity_lower_bound"],
                f"{name}: observed nullity violates the rank-one bound",
            )

        audited.append(row)

    basis_audited: list[dict[str, Any]] = []
    for row in receipt["basis_width_cases"]:
        name = row["name"]
        formula = canonical_formula(row["formula"])
        require(
            row["formula"] == [list(clause) for clause in formula],
            f"{name}: noncanonical basis-width formula",
        )
        require(
            row["formula_sha256"] == formula_sha256(formula),
            f"{name}: basis-width formula digest mismatch",
        )
        canonical_profile = independent_profile(formula)
        require(
            row["canonical_profile"] == canonical_profile,
            f"{name}: canonical basis profile mismatch",
        )
        verify_decision(
            name,
            formula,
            canonical_profile,
            row["canonical_decision"],
        )
        require(
            row["canonical_decision"]["status"]
            == row["expected_status"],
            f"{name}: canonical basis decision mismatch",
        )
        if row["expected_status"] == "sat":
            assignment = row["canonical_decision"]["assignment"]
            require(
                isinstance(assignment, list)
                and satisfies(formula, assignment),
                f"{name}: zero-valid source witness is invalid",
            )
            zero_valid_basis = independent_zero_valid_basis(
                formula, assignment
            )
            require(
                row["zero_valid_basis"] == zero_valid_basis,
                f"{name}: zero-valid basis certificate mismatch",
            )
        else:
            require(
                row["zero_valid_basis"] is None,
                f"{name}: UNSAT case has a zero-valid basis",
            )
        exact_width = independent_basis_width(
            formula, analyze_basis_exchange=True
        )
        require(
            row["basis_width"] == exact_width,
            f"{name}: exact basis-width certificate mismatch",
        )
        dual_triangle_profile = independent_dual_triangle_profile(formula)
        require(
            row["dual_triangle_profile"] == dual_triangle_profile,
            f"{name}: dual triangle profile mismatch",
        )
        witness_columns = tuple(
            column - 1
            for column in exact_width["witness"]["pivot_columns"]
        )
        if row["expected_boundary"] == "canonical_to_binary":
            require(
                exact_width["canonical_maximum_pivot_free_support"] == 3
                and exact_width["minimum_maximum_pivot_free_support"] == 2
                and exact_width["improves_canonical_basis"],
                f"{name}: canonical-to-binary boundary mismatch",
            )
            optimized = row["optimized_decision"]
            require(
                isinstance(optimized, dict),
                f"{name}: missing optimized decision",
            )
            optimized_profile = independent_basis_profile(
                formula, witness_columns
            )
            verify_decision(
                name,
                formula,
                optimized_profile,
                optimized,
                witness_columns,
            )
            require(
                optimized["status"] == row["expected_status"],
                f"{name}: optimized decision verdict mismatch",
            )
        elif row["expected_boundary"] == "all_bases_ternary":
            require(
                exact_width["minimum_maximum_pivot_free_support"] == 3
                and exact_width["basis_maximum_support_histogram"]
                == {"3": exact_width["column_bases_found"]},
                f"{name}: not every column basis is ternary",
            )
            require(
                row["optimized_decision"] is None,
                f"{name}: false binary-basis decision",
            )
        else:
            raise AssertionError(
                f"{name}: unknown basis-width boundary"
            )
        exchange = exact_width["basis_exchange"]
        if row["expected_exchange_boundary"] == "strict_descent_trap":
            require(
                exchange["nonglobal_local_minima"] > 0
                and exchange["strict_descent_reaches_optimum"]
                < exchange["basis_nodes"]
                and exchange["nonincreasing_reaches_optimum"]
                == exchange["basis_nodes"],
                f"{name}: strict-descent trap mismatch",
            )
        elif row["expected_exchange_boundary"] == "no_strict_descent_trap":
            require(
                exchange["nonglobal_local_minima"] == 0,
                f"{name}: unexpected strict-descent trap",
            )
        else:
            raise AssertionError(
                f"{name}: unknown basis-exchange boundary"
            )
        basis_audited.append(row)
    require(len(basis_audited) == 5, "basis-width case count mismatch")

    require(
        {
            (row["expected_boundary"], row["expected_status"])
            for row in basis_audited
        }
        == {
            ("canonical_to_binary", "sat"),
            ("canonical_to_binary", "unsat"),
            ("all_bases_ternary", "sat"),
            ("all_bases_ternary", "unsat"),
        },
        "basis-width SAT/UNSAT boundary coverage mismatch",
    )

    singular = [
        row
        for row in audited
        if row["expected_status"] == "unsat"
        and row["profile"]["nullity"] > 0
        and row["profile"]["clauses"] % 3 == 0
    ]
    require(len(singular) == 3, "singular non-cardinality obstruction count mismatch")
    singular_by_name = {row["name"]: row for row in singular}
    require(
        singular_by_name["singular-alphabet-unsat-n9"]["profile"]["kernel_basis"]
        == [["-1", "0", "0", "0", "0", "0", "1", "0", "0"]],
        "forced-zero obstruction basis mismatch",
    )
    full_support_basis = singular_by_name["full-support-alphabet-unsat-n9"][
        "profile"
    ]["kernel_basis"][0]
    require(
        all(value != "0" for value in full_support_basis),
        "full-support obstruction has a zero coordinate",
    )
    require(
        singular_by_name["support-three-unsat-n15"]["profile"][
            "maximum_pivot_free_support"
        ]
        == 3,
        "support-three obstruction width mismatch",
    )

    high_nullity = [
        row
        for row in audited
        if row["category"].startswith("connected_linear_nullity")
    ]
    largest_family = max(
        high_nullity, key=lambda row: row["profile"]["variables"]
    )
    audited_by_name = {row["name"]: row for row in audited}
    relation_boundary = {
        "support_three_sat_common_schaefer_classes": audited_by_name[
            "support-three-planted-sat-n9"
        ]["relation_language"]["common_schaefer_classes"],
        "support_three_unsat_common_schaefer_classes": audited_by_name[
            "support-three-unsat-n15"
        ]["relation_language"]["common_schaefer_classes"],
        "interpretation": (
            "the measured support-three UNSAT residual has no single standard "
            "Schaefer closure shared by all pivot relations; this does not prove "
            "NP-hardness for the restricted family of RREF-generated languages"
        ),
    }
    require(receipt["relation_boundary"] == relation_boundary, "relation boundary mismatch")
    summary = {
        "basis_width_cases": len(basis_audited),
        "canonical_to_binary_basis_cases": sum(
            row["expected_boundary"] == "canonical_to_binary"
            for row in basis_audited
        ),
        "all_bases_ternary_cases": sum(
            row["expected_boundary"] == "all_bases_ternary"
            for row in basis_audited
        ),
        "basis_column_subsets_checked": sum(
            row["basis_width"]["column_subsets_checked"]
            for row in basis_audited
        ),
        "basis_column_bases_checked": sum(
            row["basis_width"]["column_bases_found"]
            for row in basis_audited
        ),
        "basis_exchange_nodes_checked": sum(
            row["basis_width"]["basis_exchange"]["basis_nodes"]
            for row in basis_audited
        ),
        "basis_exchange_edges_checked": sum(
            row["basis_width"]["basis_exchange"]["exchange_edges"]
            for row in basis_audited
        ),
        "strict_descent_trap_cases": sum(
            bool(
                row["basis_width"]["basis_exchange"][
                    "nonglobal_local_minima"
                ]
            )
            for row in basis_audited
        ),
        "nonglobal_strict_local_minima": sum(
            row["basis_width"]["basis_exchange"]["nonglobal_local_minima"]
            for row in basis_audited
        ),
        "all_exchange_graphs_connected": all(
            row["basis_width"]["basis_exchange"]["connected"]
            for row in basis_audited
        ),
        "dual_small_circuits_checked": sum(
            row["dual_triangle_profile"]["small_circuit_count"]
            for row in basis_audited
        ),
        "cases": len(audited),
        "sat": sum(row["expected_status"] == "sat" for row in audited),
        "unsat": sum(row["expected_status"] == "unsat" for row in audited),
        "full_rank_unsat": sum(
            row["expected_status"] == "unsat" and row["profile"]["nullity"] == 0
            for row in audited
        ),
        "singular_noncardinality_unsat": len(singular),
        "zero_valid_basis_certificates": sum(
            row["zero_valid_basis"] is not None for row in basis_audited
        ),
        "forced_zero_pivot_unsat": sum(
            row["decision"]["reason"] == "forced_zero_pivot" for row in audited
        ),
        "bounded_support_2sat_decisions": sum(
            row["decision"]["reason"].startswith("bounded_support_2sat")
            for row in audited
        ),
        "enumerated_kernel_decisions": sum(
            row["decision"]["reason"].startswith("alphabet_") for row in audited
        ),
        "maximum_clauses": max(row["profile"]["clauses"] for row in audited),
        "maximum_nullity": max(row["profile"]["nullity"] for row in audited),
        "maximum_pivot_free_support": max(
            row["profile"]["maximum_pivot_free_support"] for row in audited
        ),
        "support_three_sat_common_schaefer_classes": relation_boundary[
            "support_three_sat_common_schaefer_classes"
        ],
        "support_three_unsat_common_schaefer_classes": relation_boundary[
            "support_three_unsat_common_schaefer_classes"
        ],
        "maximum_connected_nullity_ratio": max(
            row["profile"]["nullity"] / row["profile"]["variables"]
            for row in high_nullity
        ),
        "largest_family_nullity_ratio": (
            largest_family["profile"]["nullity"]
            / largest_family["profile"]["variables"]
        ),
        "all_family_nullities_meet_rank_one_bound": all(
            row["profile"]["nullity"]
            >= row["provenance"]["proved_nullity_lower_bound"]
            for row in high_nullity
        ),
        "all_decisions_agree": True,
        "all_sat_witnesses_check": True,
        "linear_nullity_families_checked": len(high_nullity),
    }
    require(receipt["summary"] == summary, "summary mismatch")
    require(
        receipt["theorem"]
        == {
            "domain": (
                "square 0/1 incidence matrices with exactly three ones in every "
                "row and column"
            ),
            "equivalence": "Mx = 1, x in {0,1}^n iff M(3x-1) = 0",
            "kernel_alphabet": "z in ker(M) intersect {-1,2}^n",
            "rank_corollary": "full column rank implies UNSAT",
            "cardinality_corollary": "SAT implies n is divisible by 3",
            "algorithm": (
                "use 2-SAT when every pivot relation for a supplied column basis "
                "has at most two free coordinates; otherwise enumerate {-1,2} "
                "on free columns"
            ),
            "bounded_support_theorem": (
                "a supplied basis with maximum pivot free-support at most two "
                "is verifiable and decidable in polynomial time"
            ),
            "basis_width_matroid_equivalence": (
                "for pivot basis B and free complement F, pivot support plus one "
                "is fundamental-cocircuit size in the column matroid, equivalently "
                "fundamental-circuit size for basis F in its dual; width at most "
                "two exactly says F frames the dual"
            ),
            "dual_frame_boundary": (
                "width at most two is exactly the existence of a ground-set basis "
                "that frames the dual column matroid; this is stronger than merely "
                "having a row-equivalent external frame representation"
            ),
            "fixed_nullity_basis_search": (
                "for every fixed nullity k, enumerating the binomial(n,k) dual "
                "bases is O(n^k) and therefore polynomial; this does not cover "
                "families whose nullity grows with n"
            ),
            "zero_valid_basis_equivalence": (
                "a cubic exact-one formula is SAT iff some dual ground-set basis "
                "makes every induced pivot relation contain the all-zero Boolean "
                "free tuple; a satisfying assignment and such a basis certificate "
                "convert to one another in polynomial time"
            ),
            "zero_valid_basis_complexity": (
                "existence of a zero-valid dual ground-set basis is NP-complete "
                "even for planar square incidence matrices with exactly three "
                "ones in every row and column"
            ),
            "graphic_dual_subclass": (
                "when the dual column matroid is graphic, a width-two basis is "
                "exactly a spanning forest that is a tree 2-spanner in each "
                "component; graphic recognition and tree-2-spanner construction "
                "are polynomial"
            ),
            "graphic_primal_subclass": (
                "when the column matroid is graphic, a width-two basis is exactly "
                "a spanning forest of congestion at most three in each component; "
                "graphic recognition and threshold-three spanning-tree-congestion "
                "construction are polynomial"
            ),
            "basis_search": (
                "the exact analyzer enumerates binomial(n,rank) column subsets; "
                "it proves small-instance optima but is not a polynomial basis finder"
            ),
            "bit_complexity": (
                "poly(n) for a supplied binary-support basis; "
                "O(2^nullity poly(n)) for the fallback, using exact rational arithmetic"
            ),
            "limitation": (
                "zero-valid internal basis recognition is NP-complete, while fixed "
                "nullity and graphic primal or dual structure give polynomially "
                "recognizable subclasses for the width-two question; the "
                "unrestricted internal frame-basis problem for this cubic rational-"
                "matrix family is not classified here, and exhaustive controls "
                "contain strict local minima under improving one-column exchange"
            ),
            "p_equals_np": "not established",
        },
        "theorem statement mismatch",
    )

    exhaustive = exhaustive_small()
    output = {
        **summary,
        "source_digest_checked": True,
        "all_profiles_recomputed_exactly": True,
        "all_certificates_checked": True,
        "all_basis_width_optima_recomputed": True,
        "exhaustive_fixed_gauge_formulas": exhaustive["formulas"],
        "exhaustive_sat": exhaustive["sat"],
        "exhaustive_unsat": exhaustive["unsat"],
        "exhaustive_pointwise_assignments": exhaustive["assignments"],
        "exhaustive_basis_nodes": exhaustive["basis_nodes"],
        "exhaustive_basis_exchange_edges": exhaustive["basis_exchange_edges"],
        "exhaustive_width_two_basis_formulas": exhaustive[
            "width_two_basis_formulas"
        ],
        "exhaustive_mixed_width_formulas": exhaustive["mixed_width_formulas"],
        "exhaustive_strict_descent_trap_formulas": exhaustive[
            "strict_descent_trap_formulas"
        ],
        "exhaustive_nonincreasing_trap_formulas": exhaustive[
            "nonincreasing_trap_formulas"
        ],
    }
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
