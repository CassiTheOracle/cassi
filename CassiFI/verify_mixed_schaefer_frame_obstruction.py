"""Independent verifier for the mixed cubic frame-boundary receipt.

This verifier intentionally imports neither the runner, the growing-nullity
probe, nor the cubic decision implementation. It reconstructs both component
basis spectra, all 32,232 mixed direct-sum bases, and all 1,620 incidence
2-switch candidates from exact rational elimination, screens every formula for
a width-two dual frame with its own subset bitsets and rational ranks, rechecks
every positive witness directly, and full-enumerates every free subset of a
fixed sample of switches without any coverage prefilter.
"""

from __future__ import annotations

import functools
import hashlib
import itertools
import json
import math
from collections import deque
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

RECEIPT = Path("_diag/mixed_schaefer_frame_obstruction.json")
SCHEMA = "cassifi.mixed-schaefer-frame-obstruction.v2"
SCHAEFER_CLASSES = (
    "zero_valid",
    "one_valid",
    "horn",
    "dual_horn",
    "bijunctive",
    "affine",
)
SUPPORT_THREE_SAT = (
    (1, 6, 3),
    (1, 3, 5),
    (1, 8, 2),
    (4, 6, 8),
    (4, 8, 5),
    (4, 3, 2),
    (7, 9, 5),
    (7, 9, 2),
    (7, 9, 6),
)
SUPPORT_THREE_UNSAT = (
    (1, 14, 11),
    (2, 1, 15),
    (3, 10, 5),
    (4, 8, 14),
    (5, 11, 7),
    (6, 12, 1),
    (7, 9, 2),
    (8, 15, 12),
    (9, 5, 6),
    (10, 13, 3),
    (11, 4, 8),
    (12, 3, 10),
    (13, 6, 4),
    (14, 7, 13),
    (15, 2, 9),
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
        ordered = tuple(sorted(clause))
        typed_ordered = (ordered[0], ordered[1], ordered[2])
        require(all(1 <= value <= size for value in typed_ordered), "variable out of range")
        clauses.append(typed_ordered)
        for value in typed_ordered:
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


@functools.lru_cache(maxsize=None)
def basis_system(
    formula: tuple[tuple[int, int, int], ...], pivots: tuple[int, ...]
) -> dict[str, Any] | None:
    size = len(formula)
    if len(set(pivots)) != len(pivots) or any(column < 0 or column >= size for column in pivots):
        return None
    pivot_set = set(pivots)
    free = tuple(column for column in range(size) if column not in pivot_set)
    order = pivots + free
    reduced, found = rref([[row[column] for column in order] for row in matrix_for(formula)])
    if found != tuple(range(len(pivots))):
        return None
    coefficients = tuple(
        tuple(reduced[row][column] for column in range(len(pivots), size))
        for row in range(len(pivots))
    )
    return {
        "pivots": pivots,
        "free": free,
        "coefficients": coefficients,
        "supports": tuple(sum(value != 0 for value in row) for row in coefficients),
    }


@functools.lru_cache(maxsize=None)
def profile(formula: tuple[tuple[int, int, int], ...]) -> dict[str, Any]:
    reduced, pivots = rref(matrix_for(formula))
    del reduced
    return {"rank": len(pivots), "nullity": len(formula) - len(pivots), "pivots": pivots}


def span_basis(
    rows: Sequence[Sequence[Fraction]],
) -> tuple[tuple[int, ...], list[list[Fraction]]]:
    """Echelon basis of the span of ``rows`` with normalised pivot entries."""

    basis: list[list[Fraction]] = []
    pivots: list[int] = []
    for source in rows:
        vector = [Fraction(value) for value in source]
        for pivot, row in zip(pivots, basis, strict=True):
            if vector[pivot]:
                factor = vector[pivot]
                vector = [
                    value - factor * basis_value
                    for value, basis_value in zip(vector, row, strict=True)
                ]
        pivot = next((index for index, value in enumerate(vector) if value), None)
        if pivot is None:
            continue
        divisor = vector[pivot]
        vector = [value / divisor for value in vector]
        basis.append(vector)
        pivots.append(pivot)
    return tuple(pivots), basis


def in_span(pivots: tuple[int, ...], basis: Sequence[Sequence[Fraction]], vector: Sequence[Fraction]) -> bool:
    """Whether one vector lies in the span of an echelon basis."""

    reduced = list(vector)
    for pivot, row in zip(pivots, basis, strict=True):
        if reduced[pivot]:
            factor = reduced[pivot]
            reduced = [
                value - factor * basis_value
                for value, basis_value in zip(reduced, row, strict=True)
            ]
    return all(value == 0 for value in reduced)


def rational_rank(rows: Sequence[Sequence[Fraction]]) -> int:
    return len(rref(rows)[1])


@functools.lru_cache(maxsize=None)
def kernel_coordinate_rows(
    formula: tuple[tuple[int, int, int], ...],
) -> tuple[tuple[Fraction, ...], ...]:
    shape = profile(formula)
    system = basis_system(formula, shape["pivots"])
    require(system is not None, "canonical kernel system missing")
    assert system is not None
    pivots: tuple[int, ...] = tuple(system["pivots"])
    free: tuple[int, ...] = tuple(system["free"])
    coefficients: tuple[tuple[Fraction, ...], ...] = tuple(
        tuple(row) for row in system["coefficients"]
    )
    vectors: list[list[Fraction]] = []
    for free_index, free_column in enumerate(free):
        vector = [Fraction(0)] * len(formula)
        vector[free_column] = Fraction(1)
        for pivot_index, pivot_column in enumerate(pivots):
            vector[pivot_column] = -coefficients[pivot_index][free_index]
        vectors.append(vector)
    return tuple(
        tuple(vectors[coordinate][column] for coordinate in range(len(free)))
        for column in range(len(formula))
    )


def column_partition(
    kernel_rows: tuple[tuple[Fraction, ...], ...],
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[tuple[Fraction, ...], ...]]:
    """Collapse parallel kernel-coordinate columns into projective classes."""

    order: dict[tuple[Fraction, ...], int] = {}
    class_of: list[int] = []
    class_masks: list[int] = []
    representatives: list[tuple[Fraction, ...]] = []
    for element, column in enumerate(kernel_rows):
        pivot = next((value for value in column if value), None)
        reduced = tuple(column)
        if pivot is not None:
            reduced = tuple(value / pivot for value in column)
        index = order.get(reduced)
        if index is None:
            index = len(class_masks)
            order[reduced] = index
            class_masks.append(0)
            representatives.append(reduced)
        class_of.append(index)
        class_masks[index] |= 1 << element
    return tuple(class_of), tuple(class_masks), tuple(representatives)


def class_cover_masks(
    kernel_rows: tuple[tuple[Fraction, ...], ...], bound: int
) -> tuple[list[list[tuple[int, ...]]], dict[tuple[int, ...], int]]:
    """Index the elements covered by every ``bound``-subset of the ground set.

    Width ``w`` means every element lies in the span of at most ``w`` elements
    of the free set, so coverage by ``bound``-subsets of a free set is exactly
    the width-at-most-``bound`` test for an independent free set.
    """

    size = len(kernel_rows)
    class_of, class_masks, representatives = column_partition(kernel_rows)
    class_count = len(class_masks)
    by_multiset: dict[tuple[int, ...], int] = {}
    for multiset in itertools.combinations_with_replacement(range(class_count), bound):
        pivots, basis = span_basis(tuple(representatives[index] for index in multiset))
        cover = 0
        for candidate in range(class_count):
            if in_span(pivots, basis, representatives[candidate]):
                cover |= class_masks[candidate]
        by_multiset[multiset] = cover

    covers: list[list[tuple[int, ...]]] = [[] for _ in range(size)]
    masks: dict[tuple[int, ...], int] = {}
    for subset in itertools.combinations(range(size), bound):
        cover = by_multiset[tuple(sorted(class_of[element] for element in subset))]
        masks[subset] = cover
        for element in range(size):
            if (cover >> element) & 1:
                covers[element].append(subset)
    return covers, masks


_SUBSET_BITS: dict[tuple[int, int, int], dict[tuple[int, ...], int]] = {}
BRUTEFORCE_SAMPLE = (0, 1, 2, 405, 810, 1215, 1619)
BRUTEFORCE_CROSS_CHECK: list[dict[str, Any]] = []


def subset_bits(size: int, nullity: int, bound: int) -> dict[tuple[int, ...], int]:
    """Map each element subset of size ``bound`` to the free subsets holding it."""

    key = (size, nullity, bound)
    cached = _SUBSET_BITS.get(key)
    if cached is not None:
        return cached
    total = math.comb(size, nullity)
    payloads: dict[tuple[int, ...], bytearray] = {
        subset: bytearray((total + 7) // 8)
        for subset in itertools.combinations(range(size), bound)
    }
    for index, free in enumerate(itertools.combinations(range(size), nullity)):
        byte = index >> 3
        bit = 1 << (index & 7)
        for subset in itertools.combinations(free, bound):
            payloads[subset][byte] |= bit
    masks = {
        subset: int.from_bytes(bytes(raw), "little") for subset, raw in payloads.items()
    }
    _SUBSET_BITS[key] = masks
    return masks


def coverage_screen(
    formula: tuple[tuple[int, int, int], ...], bound: int
) -> dict[str, Any]:
    """Keep only free subsets whose internal ``bound``-subsets cover everything."""

    kernel_rows = kernel_coordinate_rows(formula)
    size = len(kernel_rows)
    nullity = len(kernel_rows[0]) if kernel_rows else 0
    covers, subset_masks = class_cover_masks(kernel_rows, bound)
    bits = subset_bits(size, nullity, bound)
    candidates = (1 << math.comb(size, nullity)) - 1
    for element in sorted(range(size), key=lambda item: len(covers[item])):
        mask = 0
        for subset in covers[element]:
            mask |= bits[subset]
        candidates &= mask
        if not candidates:
            return {
                "exists": False,
                "complete": True,
                "candidates_after_filter": 0,
                "candidates_examined": 0,
                "witness_free_columns": None,
            }

    free_sets = tuple(itertools.combinations(range(size), nullity))
    candidates_examined = 0
    remaining = candidates
    while remaining:
        low = remaining & -remaining
        index = low.bit_length() - 1
        remaining ^= low
        free_columns = free_sets[index]
        candidates_examined += 1
        if nullity <= bound or rational_rank(
            tuple(kernel_rows[column] for column in free_columns)
        ) == nullity:
            covered = 0
            for subset in itertools.combinations(free_columns, bound):
                covered |= subset_masks[subset]
            require(covered == (1 << size) - 1, "coverage filter admitted an uncovered free set")
            return {
                "exists": True,
                "complete": False,
                "candidates_after_filter": bin(candidates).count("1"),
                "candidates_examined": candidates_examined,
                "witness_free_columns": [column + 1 for column in free_columns],
            }
    return {
        "exists": False,
        "complete": True,
        "candidates_after_filter": bin(candidates).count("1"),
        "candidates_examined": candidates_examined,
        "witness_free_columns": None,
    }


def coverage_bruteforce(
    formula: tuple[tuple[int, int, int], ...], bound: int
) -> dict[str, Any]:
    """Full enumeration over every free subset, no coverage prefilter."""

    kernel_rows = kernel_coordinate_rows(formula)
    size = len(kernel_rows)
    nullity = len(kernel_rows[0]) if kernel_rows else 0
    _, subset_masks = class_cover_masks(kernel_rows, bound)
    full = (1 << size) - 1
    covering = 0
    for free_columns in itertools.combinations(range(size), nullity):
        covered = 0
        for subset in itertools.combinations(free_columns, bound):
            covered |= subset_masks[subset]
        if covered != full:
            continue
        covering += 1
        if nullity <= bound or rational_rank(
            tuple(kernel_rows[column] for column in free_columns)
        ) == nullity:
            return {
                "exists": True,
                "covering_subsets": covering,
                "witness_free_columns": [column + 1 for column in free_columns],
            }
    return {"exists": False, "covering_subsets": covering, "witness_free_columns": None}


def exact_width(
    formula: tuple[tuple[int, int, int], ...], free_columns: Sequence[int]
) -> int:
    """Exact maximum support of one free basis, solved in the kernel coordinates."""

    kernel_rows = kernel_coordinate_rows(formula)
    size = len(kernel_rows)
    width_of = len(free_columns)
    matrix = [
        [kernel_rows[free_columns[index]][coordinate] for index in range(width_of)]
        for coordinate in range(width_of)
    ]
    table = [
        [kernel_rows[element][coordinate] for element in range(size)]
        for coordinate in range(width_of)
    ]
    for column in range(width_of):
        source = next((row for row in range(column, width_of) if matrix[row][column]), None)
        require(source is not None, "claimed witness is not a free basis")
        assert source is not None
        matrix[column], matrix[source] = matrix[source], matrix[column]
        table[column], table[source] = table[source], table[column]
        divisor = matrix[column][column]
        matrix[column] = [value / divisor for value in matrix[column]]
        table[column] = [value / divisor for value in table[column]]
        for row in range(width_of):
            if row == column or not matrix[row][column]:
                continue
            multiplier = matrix[row][column]
            matrix[row] = [
                value - multiplier * pivot_value
                for value, pivot_value in zip(matrix[row], matrix[column], strict=True)
            ]
            table[row] = [
                value - multiplier * pivot_value
                for value, pivot_value in zip(table[row], table[column], strict=True)
            ]
    return max(sum(1 for row in table if row[element]) for element in range(size))


def validate_witness(
    formula: tuple[tuple[int, int, int], ...],
    free_columns: Sequence[int] | None,
    bound: int,
) -> int:
    """Recheck a claimed free basis from scratch and measure its exact width."""

    require(free_columns is not None, "frame witness missing")
    assert free_columns is not None
    shape = profile(formula)
    columns = [column - 1 for column in free_columns]
    require(len(columns) == shape["nullity"], "frame witness size mismatch")
    width = exact_width(formula, columns)
    require(width <= bound, "frame witness exceeds its bounding claim")
    return width


def frame_digest(records: Sequence[dict[str, Any]]) -> str:
    payload = [
        {
            "digest": record["digest"],
            "width_two_basis_exists": record["width_two_basis_exists"],
            "width_two_search_complete": record["width_two_search_complete"],
            "width_three_basis_exists": record["width_three_basis_exists"],
            "width_three_search_complete": record["width_three_search_complete"],
            "canonical_width": record["canonical_width"],
            "witness_free_columns": record["witness_free_columns"],
            "witness_width": record["witness_width"],
            "omega": record["omega"],
            "omega_exact": record["omega_exact"],
        }
        for record in records
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def relation_properties(tuples: Sequence[tuple[int, ...]], arity: int) -> dict[str, bool]:
    members = set(tuples)
    return {
        "zero_valid": (0,) * arity in members,
        "one_valid": (1,) * arity in members,
        "horn": all(
            tuple(left[index] & right[index] for index in range(arity)) in members
            for left in tuples for right in tuples
        ),
        "dual_horn": all(
            tuple(left[index] | right[index] for index in range(arity)) in members
            for left in tuples for right in tuples
        ),
        "bijunctive": all(
            tuple(int(left[index] + middle[index] + right[index] >= 2) for index in range(arity)) in members
            for left in tuples for middle in tuples for right in tuples
        ),
        "affine": all(
            tuple(left[index] ^ middle[index] ^ right[index] for index in range(arity)) in members
            for left in tuples for middle in tuples for right in tuples
        ),
    }


def relation_classes(system: dict[str, Any]) -> tuple[str, ...]:
    relations: list[dict[str, bool]] = []
    for coefficients in system["coefficients"]:
        pivot_values = tuple(-value for value in coefficients)
        support = tuple(index for index, value in enumerate(pivot_values) if value)
        allowed: list[tuple[int, ...]] = []
        for bits in itertools.product((0, 1), repeat=len(support)):
            value = sum(
                (
                    pivot_values[index] * (3 * bit - 1)
                    for index, bit in zip(support, bits, strict=True)
                ),
                start=Fraction(0),
            )
            if value in (Fraction(-1), Fraction(2)):
                allowed.append(bits)
        relations.append(relation_properties(allowed, len(support)))
    return tuple(sorted(name for name in SCHAEFER_CLASSES if all(row[name] for row in relations)))


def class_tuple(raw_key: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(raw_key, str):
        return () if raw_key == "none" else tuple(sorted(raw_key.split(",")))
    return tuple(sorted(raw_key))


def display_class_key(classes: Sequence[str]) -> str:
    return ",".join(class_tuple(classes)) or "none"


def basis_records(
    formula: tuple[tuple[int, int, int], ...],
) -> list[tuple[int, tuple[str, ...]]]:
    shape = profile(formula)
    records: list[tuple[int, tuple[str, ...]]] = []
    for pivots in itertools.combinations(range(len(formula)), shape["rank"]):
        system = basis_system(formula, pivots)
        if system is None:
            continue
        records.append((max(system["supports"], default=0), relation_classes(system)))
    return records


def census(formula: tuple[tuple[int, int, int], ...]) -> dict[str, Any]:
    records = basis_records(formula)
    widths: dict[str, int] = {}
    classes: dict[tuple[str, ...], int] = {}
    for width, class_name in records:
        widths[str(width)] = widths.get(str(width), 0) + 1
        classes[class_name] = classes.get(class_name, 0) + 1
    shape = profile(formula)
    return {
        "formula_sha256": formula_digest(formula),
        "clauses": len(formula),
        "variables": len(formula),
        "rank": shape["rank"],
        "nullity": shape["nullity"],
        "column_subsets_checked": math.comb(len(formula), shape["rank"]),
        "column_bases_found": len(records),
        "basis_width_histogram": {key: widths[key] for key in sorted(widths, key=int)},
        "common_schaefer_class_histogram": {
            display_class_key(key): classes[key]
            for key in sorted(classes, key=display_class_key)
        },
        "minimum_width": min(map(int, widths)),
        "maximum_width": max(map(int, widths)),
        "all_bases_width_at_least_three": all(int(key) >= 3 for key in widths),
    }


def mixed_formula() -> tuple[tuple[int, int, int], ...]:
    offset = len(ALL_BASES_TERNARY_SAT)
    return canonical_formula(
        tuple(ALL_BASES_TERNARY_SAT)
        + tuple(tuple(variable + offset for variable in clause) for clause in ALL_BASES_TERNARY_UNSAT)
    )


def connected(formula: tuple[tuple[int, int, int], ...]) -> bool:
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


def switch_formula(
    left_row: int,
    left_variable: int,
    right_row: int,
    right_variable: int,
) -> tuple[tuple[int, int, int], ...]:
    offset = len(ALL_BASES_TERNARY_SAT)
    rows = [set(clause) for clause in ALL_BASES_TERNARY_SAT]
    rows.extend(set(variable + offset for variable in clause) for clause in ALL_BASES_TERNARY_UNSAT)
    require(left_variable in rows[left_row], "left switch incidence absent")
    require(right_variable in rows[right_row], "right switch incidence absent")
    require(right_variable not in rows[left_row], "left switch duplicates incidence")
    require(left_variable not in rows[right_row], "right switch duplicates incidence")
    rows[left_row].remove(left_variable)
    rows[left_row].add(right_variable)
    rows[right_row].remove(right_variable)
    rows[right_row].add(left_variable)
    return canonical_formula(tuple(tuple(sorted(row)) for row in rows))


def exact_status(formula: tuple[tuple[int, int, int], ...]) -> str:
    shape = profile(formula)
    system = basis_system(formula, shape["pivots"])
    require(system is not None, "canonical pivot system missing")
    assert system is not None
    pivots: tuple[int, ...] = tuple(system["pivots"])
    free: tuple[int, ...] = tuple(system["free"])
    coefficients: tuple[tuple[Fraction, ...], ...] = tuple(
        tuple(row) for row in system["coefficients"]
    )
    for bits in itertools.product((0, 1), repeat=shape["nullity"]):
        free_values: tuple[Fraction, ...] = tuple(Fraction(3 * bit - 1) for bit in bits)
        vector: list[Fraction] = [Fraction(0)] * len(formula)
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
        if all(value in (Fraction(-1), Fraction(2)) for value in vector):
            return "sat"
    return "unsat"


def frame_screen(formula: tuple[tuple[int, int, int], ...]) -> dict[str, Any]:
    """Independent exact frame width: bound two then a measured bound-three basis."""

    pair = coverage_screen(formula, 2)
    width_bound = canonical_width(formula)
    if pair["exists"]:
        width = validate_witness(formula, pair["witness_free_columns"], 2)
        require(width <= width_bound, "pair witness beats the canonical upper bound")
        return {
            "width_two_basis_exists": True,
            "width_two_search_complete": False,
            "width_two_candidates_after_filter": pair["candidates_after_filter"],
            "width_two_candidates_examined": pair["candidates_examined"],
            "width_three_basis_exists": None,
            "width_three_search_complete": None,
            "width_three_candidates_after_filter": None,
            "width_three_candidates_examined": None,
            "canonical_width": width_bound,
            "witness_free_columns": pair["witness_free_columns"],
            "witness_width": width,
            "omega": width,
            "omega_exact": True,
        }

    triple = coverage_screen(formula, 3)
    if triple["exists"]:
        width = validate_witness(formula, triple["witness_free_columns"], 3)
        require(width == 3, "triple witness is not exactly width three")
        require(width <= width_bound, "triple witness beats the canonical upper bound")
        return {
            "width_two_basis_exists": False,
            "width_two_search_complete": True,
            "width_two_candidates_after_filter": pair["candidates_after_filter"],
            "width_two_candidates_examined": pair["candidates_examined"],
            "width_three_basis_exists": True,
            "width_three_search_complete": False,
            "width_three_candidates_after_filter": triple["candidates_after_filter"],
            "width_three_candidates_examined": triple["candidates_examined"],
            "canonical_width": width_bound,
            "witness_free_columns": triple["witness_free_columns"],
            "witness_width": width,
            "omega": width,
            "omega_exact": True,
        }
    require(width_bound >= 4, "canonical width contradicts the bound-three screen")
    return {
        "width_two_basis_exists": False,
        "width_two_search_complete": True,
        "width_two_candidates_after_filter": pair["candidates_after_filter"],
        "width_two_candidates_examined": pair["candidates_examined"],
        "width_three_basis_exists": False,
        "width_three_search_complete": True,
        "width_three_candidates_after_filter": triple["candidates_after_filter"],
        "width_three_candidates_examined": triple["candidates_examined"],
        "canonical_width": width_bound,
        "witness_free_columns": None,
        "witness_width": None,
        "omega": None,
        "omega_exact": False,
        "omega_lower_bound": 4,
    }


def switch_records() -> list[dict[str, Any]]:
    offset = len(ALL_BASES_TERNARY_SAT)
    records: list[dict[str, Any]] = []
    for left_row, left_clause in enumerate(ALL_BASES_TERNARY_SAT):
        for left_variable in left_clause:
            for right_row, right_clause in enumerate(ALL_BASES_TERNARY_UNSAT):
                for right_variable_local in right_clause:
                    formula = switch_formula(
                        left_row,
                        left_variable,
                        offset + right_row,
                        offset + right_variable_local,
                    )
                    shape = profile(formula)
                    index = len(records)
                    screen = frame_screen(formula)
                    if index in BRUTEFORCE_SAMPLE:
                        brute_pairs = coverage_bruteforce(formula, 2)
                        brute_triples = coverage_bruteforce(formula, 3)
                        agrees = (
                            brute_pairs["exists"] == screen["width_two_basis_exists"]
                            and brute_triples["exists"] == screen["width_three_basis_exists"]
                        )
                        BRUTEFORCE_CROSS_CHECK.append(
                            {
                                "index": index,
                                "digest": formula_digest(formula),
                                "screen_width_two_exists": screen["width_two_basis_exists"],
                                "bruteforce_width_two_exists": brute_pairs["exists"],
                                "bruteforce_width_two_covering_subsets": brute_pairs[
                                    "covering_subsets"
                                ],
                                "screen_width_three_exists": screen["width_three_basis_exists"],
                                "bruteforce_width_three_exists": brute_triples["exists"],
                                "bruteforce_width_three_covering_subsets": brute_triples[
                                    "covering_subsets"
                                ],
                                "agrees": agrees,
                            }
                        )
                        require(agrees, "brute-force frame enumeration disagrees with the screen")
                    records.append(
                        {
                            "digest": formula_digest(formula),
                            "connected": connected(formula),
                            "rank": shape["rank"],
                            "nullity": shape["nullity"],
                            "status": exact_status(formula),
                            **screen,
                        }
                    )
    return records


@functools.lru_cache(maxsize=None)
def canonical_width(formula: tuple[tuple[int, int, int], ...]) -> int:
    """Maximum pivot-free support of the canonical RREF basis."""

    shape = profile(formula)
    system = basis_system(formula, shape["pivots"])
    require(system is not None, "canonical basis system missing")
    assert system is not None
    return max(system["supports"], default=0)


def histogram(records: Sequence[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        key = str(record[field])
        counts[key] = counts.get(key, 0) + 1
    return {key: counts[key] for key in sorted(counts, key=lambda item: (len(item), item))}


def main() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(receipt["schema"] == SCHEMA, "schema mismatch")
    sat = canonical_formula(ALL_BASES_TERNARY_SAT)
    unsat = canonical_formula(ALL_BASES_TERNARY_UNSAT)
    sat_census = census(sat)
    unsat_census = census(unsat)
    require(receipt["components"]["sat"] == sat_census, "SAT component census mismatch")
    require(receipt["components"]["unsat"] == unsat_census, "UNSAT component census mismatch")
    sat_status = exact_status(sat)
    unsat_status = exact_status(unsat)
    require(sat_status == "sat", "SAT component exact status mismatch")
    require(unsat_status == "unsat", "UNSAT component exact status mismatch")

    control_anchors = [
        {
            "name": "all_bases_sat",
            "formula": canonical_formula(ALL_BASES_TERNARY_SAT),
            "width_two_exists": False,
            "width_three_exists": True,
            "width": 3,
        },
        {
            "name": "all_bases_unsat",
            "formula": canonical_formula(ALL_BASES_TERNARY_UNSAT),
            "width_two_exists": False,
            "width_three_exists": True,
            "width": 3,
        },
        {
            "name": "support_three_sat",
            "formula": canonical_formula(SUPPORT_THREE_SAT),
            "width_two_exists": True,
            "width_three_exists": None,
            "width": 2,
        },
        {
            "name": "support_three_unsat",
            "formula": canonical_formula(SUPPORT_THREE_UNSAT),
            "width_two_exists": True,
            "width_three_exists": None,
            "width": 2,
        },
    ]
    for anchor in control_anchors:
        anchored = frame_screen(anchor["formula"])
        require(
            anchored["width_two_basis_exists"] == anchor["width_two_exists"],
            f"{anchor['name']} width-two verdict changed",
        )
        if anchor["width_three_exists"] is not None:
            require(
                anchored["width_three_basis_exists"] == anchor["width_three_exists"],
                f"{anchor['name']} width-three verdict changed",
            )
        require(
            anchored["omega_exact"] and anchored["omega"] == anchor["width"],
            f"{anchor['name']} exact width changed",
        )
        triple = coverage_screen(anchor["formula"], 3)
        require(
            triple["exists"] and triple["witness_free_columns"] is not None,
            f"{anchor['name']} has no bound-three witness",
        )
        assert triple["witness_free_columns"] is not None
        require(
            exact_width(
                anchor["formula"],
                [column - 1 for column in triple["witness_free_columns"]],
            )
            <= 3,
            f"{anchor['name']} bound-three witness exceeds width three",
        )

    mixed = mixed_formula()
    mixed_status = exact_status(mixed)
    mixed_receipt = receipt["mixed_direct_sum"]
    mixed_shape = profile(mixed)
    sat_records = basis_records(sat)
    unsat_records = basis_records(unsat)
    combined_widths: dict[str, int] = {}
    combined_classes: dict[tuple[str, ...], int] = {}
    for sat_width, sat_class in sat_records:
        sat_classes = set(sat_class)
        for unsat_width, unsat_class in unsat_records:
            unsat_classes = set(unsat_class)
            width_key = str(max(sat_width, unsat_width))
            class_key_value = tuple(sorted(sat_classes & unsat_classes))
            combined_widths[width_key] = combined_widths.get(width_key, 0) + 1
            combined_classes[class_key_value] = combined_classes.get(class_key_value, 0) + 1
    expected_mixed = {
        "formula": [list(clause) for clause in mixed],
        "formula_sha256": formula_digest(mixed),
        "variables": len(mixed),
        "rank": mixed_shape["rank"],
        "nullity": mixed_shape["nullity"],
        "connected": connected(mixed),
        "status": mixed_status,
        "column_bases": len(sat_records) * len(unsat_records),
        "basis_width_histogram": {key: combined_widths[key] for key in sorted(combined_widths, key=int)},
        "common_schaefer_class_histogram": {
            display_class_key(key): combined_classes[key]
            for key in sorted(combined_classes, key=display_class_key)
        },
        "all_bases_width_at_least_three": all(int(key) >= 3 for key in combined_widths),
    }
    mixed_screen = frame_screen(mixed)
    mixed_pairs = coverage_bruteforce(mixed, 2)
    mixed_triples = coverage_bruteforce(mixed, 3)
    require(
        mixed_pairs["exists"] == mixed_screen["width_two_basis_exists"]
        and mixed_triples["exists"] == mixed_screen["width_three_basis_exists"],
        "mixed formula screen disagrees with full subset enumeration",
    )
    require(
        mixed_screen["width_two_basis_exists"] == any(int(key) <= 2 for key in combined_widths),
        "mixed formula screen disagrees with the basis census",
    )
    require(mixed_screen["omega_exact"] and mixed_screen["omega"] == 3, "mixed width is not exactly three")
    require(
        min(int(key) for key in combined_widths) == mixed_screen["omega"],
        "mixed census width and screened width disagree",
    )
    require(
        mixed_screen["width_three_candidates_after_filter"]
        == len(sat_records) * len(unsat_records),
        "mixed triple-coverage survivors do not match the width-three basis count",
    )
    expected_mixed.update(
        {
            **mixed_screen,
            "width_two_agrees_with_census": True,
        }
    )
    require(mixed_receipt == expected_mixed, "mixed direct-sum mismatch")
    require(len(sat_records) * len(unsat_records) == 32232, "mixed basis count is not 32,232")
    require(combined_widths == {"3": 32232}, "mixed width census is not invariant three")
    require(combined_classes == {(): 32232}, "mixed class intersection is not empty")

    records = switch_records()
    digests = sorted(record["digest"] for record in records)
    switch_receipt = receipt["one_switch_enumeration"]
    expected_switch = {
        "left_component_incidence_edges": 36,
        "right_component_incidence_edges": 45,
        "known_cross_component_edge_cut": 2,
        "raw_switches": len(records),
        "unique_formulas": len(set(digests)),
        "connected_formulas": sum(record["connected"] for record in records),
        "rank_histogram": histogram(records, "rank"),
        "nullity_histogram": histogram(records, "nullity"),
        "status_histogram": histogram(records, "status"),
        "width_two_basis_histogram": histogram(records, "width_two_basis_exists"),
        "width_two_search_complete_histogram": histogram(
            records, "width_two_search_complete"
        ),
        "width_three_basis_histogram": histogram(records, "width_three_basis_exists"),
        "width_three_search_complete_histogram": histogram(
            records, "width_three_search_complete"
        ),
        "canonical_width_histogram": histogram(records, "canonical_width"),
        "witness_width_histogram": histogram(records, "witness_width"),
        "omega_histogram": histogram(records, "omega"),
        "omega_exact_histogram": histogram(records, "omega_exact"),
        "omega_exact_formulas": sum(1 for record in records if record["omega_exact"]),
        "width_two_candidates_after_filter": sum(
            record["width_two_candidates_after_filter"] for record in records
        ),
        "width_two_candidates_examined": sum(
            record["width_two_candidates_examined"] for record in records
        ),
        "width_three_candidates_after_filter": sum(
            record["width_three_candidates_after_filter"] for record in records
        ),
        "width_three_candidates_examined": sum(
            record["width_three_candidates_examined"] for record in records
        ),
        "frame_screen_digest": frame_digest(records),
        "formula_digest_sha256": hashlib.sha256(
            json.dumps(digests, separators=(",", ":")).encode("ascii")
        ).hexdigest(),
    }
    require(switch_receipt == expected_switch, "one-switch enumeration mismatch")
    require(len(records) == 1620, "one-switch count is not 1,620")
    require(switch_receipt["known_cross_component_edge_cut"] == 2, "known cut mismatch")
    require(all(record["connected"] for record in records), "a cross-component switch was disconnected")
    require(all(record["rank"] == 22 and record["nullity"] == 5 for record in records), "switch rank/nullity varied")
    require(all(record["status"] == "unsat" for record in records), "switch status was not uniformly UNSAT")
    require(all(record["omega_exact"] for record in records), "a switch width did not close exactly")
    require({record["omega"] for record in records} == {3}, "a switch width is not exactly three")
    require(
        all(record["witness_width"] == 3 for record in records),
        "a switch witness width is not three",
    )
    require(
        all(record["width_two_search_complete"] and not record["width_two_basis_exists"] for record in records),
        "a switch admitted a width-two frame",
    )
    require(len(BRUTEFORCE_CROSS_CHECK) == len(BRUTEFORCE_SAMPLE), "brute-force sample size mismatch")
    require(
        all(item["agrees"] for item in BRUTEFORCE_CROSS_CHECK),
        "brute-force cross-check disagreed with the screened verdict",
    )
    print(json.dumps({
        "schema": SCHEMA,
        "mixed_bases_verified": len(sat_records) * len(unsat_records),
        "mixed_width_histogram": combined_widths,
        "mixed_common_classes": {
            display_class_key(key): combined_classes[key]
            for key in sorted(combined_classes, key=display_class_key)
        },
        "switches_verified": len(records),
        "switch_rank_histogram": histogram(records, "rank"),
        "switch_nullity_histogram": histogram(records, "nullity"),
        "switch_status_histogram": histogram(records, "status"),
        "switch_width_two_histogram": histogram(records, "width_two_basis_exists"),
        "switch_width_two_search_complete_histogram": histogram(
            records, "width_two_search_complete"
        ),
        "switch_width_three_histogram": histogram(records, "width_three_basis_exists"),
        "switch_canonical_width_histogram": histogram(records, "canonical_width"),
        "switch_witness_width_histogram": histogram(records, "witness_width"),
        "switch_omega_exact_formulas": sum(1 for record in records if record["omega_exact"]),
        "bruteforce_cross_check": {
            "sampled": len(BRUTEFORCE_CROSS_CHECK),
            "agreement": sum(1 for item in BRUTEFORCE_CROSS_CHECK if item["agrees"]),
            "width_two_histogram": histogram(
                BRUTEFORCE_CROSS_CHECK, "bruteforce_width_two_exists"
            ),
            "width_three_histogram": histogram(
                BRUTEFORCE_CROSS_CHECK, "bruteforce_width_three_exists"
            ),
        },
        "status": "verified",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
