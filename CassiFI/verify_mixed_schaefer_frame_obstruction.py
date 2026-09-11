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


def profile(formula: tuple[tuple[int, int, int], ...]) -> dict[str, Any]:
    reduced, pivots = rref(matrix_for(formula))
    del reduced
    return {"rank": len(pivots), "nullity": len(formula) - len(pivots), "pivots": pivots}


def rational_rank(rows: Sequence[Sequence[Fraction]]) -> int:
    return len(rref(rows)[1])


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


def pair_cover_masks(
    kernel_rows: tuple[tuple[Fraction, ...], ...],
) -> dict[tuple[int, int], int]:
    """Element bitmask spanned by each pair of ground-set coordinates."""

    size = len(kernel_rows)
    class_of, class_masks, representatives = column_partition(kernel_rows)
    class_pair_masks: dict[tuple[int, int], int] = {}
    for left in range(len(class_masks)):
        for right in range(left, len(class_masks)):
            cover = 0
            if left == right:
                cover = class_masks[left]
            else:
                pair_rank = rational_rank((representatives[left], representatives[right]))
                for candidate in range(len(class_masks)):
                    if rational_rank(
                        (
                            representatives[left],
                            representatives[right],
                            representatives[candidate],
                        )
                    ) == pair_rank:
                        cover |= class_masks[candidate]
            class_pair_masks[(left, right)] = cover

    masks: dict[tuple[int, int], int] = {}
    for left, right in itertools.combinations(range(size), 2):
        low, high = sorted((class_of[left], class_of[right]))
        masks[(left, right)] = class_pair_masks[(low, high)]
    return masks


_SUBSET_BITS: dict[tuple[int, int], dict[tuple[int, int], int]] = {}
BRUTEFORCE_SAMPLE = (0, 1, 2, 405, 810, 1215, 1619)
BRUTEFORCE_CROSS_CHECK: list[dict[str, Any]] = []


def subset_bits(size: int, nullity: int) -> dict[tuple[int, int], int]:
    """Map each element pair to the free subsets that contain it (own build)."""

    key = (size, nullity)
    cached = _SUBSET_BITS.get(key)
    if cached is not None:
        return cached
    subsets = math.comb(size, nullity)
    payloads: dict[tuple[int, int], bytearray] = {
        pair: bytearray((subsets + 7) // 8)
        for pair in itertools.combinations(range(size), 2)
    }
    for index, subset in enumerate(itertools.combinations(range(size), nullity)):
        byte = index >> 3
        bit = 1 << (index & 7)
        for pair in itertools.combinations(subset, 2):
            payloads[pair][byte] |= bit
    masks = {pair: int.from_bytes(bytes(raw), "little") for pair, raw in payloads.items()}
    _SUBSET_BITS[key] = masks
    return masks


def width_two_screen(formula: tuple[tuple[int, int, int], ...]) -> dict[str, Any]:
    """Keep only free subsets whose internal pairs span the whole ground set."""

    kernel_rows = kernel_coordinate_rows(formula)
    size = len(kernel_rows)
    nullity = len(kernel_rows[0]) if kernel_rows else 0
    pair_covers = pair_cover_masks(kernel_rows)
    element_pairs: list[list[tuple[int, int]]] = [[] for _ in range(size)]
    for pair, cover in pair_covers.items():
        for element in range(size):
            if (cover >> element) & 1:
                element_pairs[element].append(pair)

    bits = subset_bits(size, nullity)
    candidates = (1 << math.comb(size, nullity)) - 1
    for element in sorted(range(size), key=lambda item: len(element_pairs[item])):
        mask = 0
        for pair in element_pairs[element]:
            mask |= bits[pair]
        candidates &= mask
        if not candidates:
            return {
                "exists": False,
                "complete": True,
                "candidates_after_filter": 0,
                "bases_examined": 0,
                "witness_free_columns": None,
            }

    free_sets = tuple(itertools.combinations(range(size), nullity))
    bases_examined = 0
    remaining = candidates
    while remaining:
        low = remaining & -remaining
        index = low.bit_length() - 1
        remaining ^= low
        free_columns = free_sets[index]
        if nullity <= 2 or rational_rank(
            tuple(kernel_rows[column] for column in free_columns)
        ) == nullity:
            bases_examined += 1
            return {
                "exists": True,
                "complete": False,
                "candidates_after_filter": bin(candidates).count("1"),
                "bases_examined": bases_examined,
                "witness_free_columns": [column + 1 for column in free_columns],
            }
    return {
        "exists": False,
        "complete": True,
        "candidates_after_filter": bin(candidates).count("1"),
        "bases_examined": bases_examined,
        "witness_free_columns": None,
    }


def width_two_bruteforce(formula: tuple[tuple[int, int, int], ...]) -> dict[str, Any]:
    """Full enumeration over every free subset, no coverage prefilter."""

    kernel_rows = kernel_coordinate_rows(formula)
    size = len(kernel_rows)
    nullity = len(kernel_rows[0]) if kernel_rows else 0
    pair_covers = pair_cover_masks(kernel_rows)
    full = (1 << size) - 1
    covering = 0
    for free_columns in itertools.combinations(range(size), nullity):
        covered = 0
        for left, right in itertools.combinations(free_columns, 2):
            covered |= pair_covers[(left, right)]
        if covered != full:
            continue
        covering += 1
        if nullity <= 2 or rational_rank(
            tuple(kernel_rows[column] for column in free_columns)
        ) == nullity:
            return {
                "exists": True,
                "covering_subsets": covering,
                "witness_free_columns": [column + 1 for column in free_columns],
            }
    return {"exists": False, "covering_subsets": covering, "witness_free_columns": None}


def validate_witness(
    formula: tuple[tuple[int, int, int], ...], free_columns: Sequence[int] | None
) -> None:
    """Recheck a claimed width-two basis directly from its free columns."""

    require(free_columns is not None, "width-two witness missing")
    assert free_columns is not None
    kernel_rows = kernel_coordinate_rows(formula)
    columns = [column - 1 for column in free_columns]
    require(len(columns) == len(kernel_rows[0]), "width-two witness size mismatch")
    require(
        rational_rank(tuple(kernel_rows[column] for column in columns)) == len(columns),
        "width-two witness is not a basis",
    )
    pair_covers = pair_cover_masks(kernel_rows)
    covered = 0
    for left, right in itertools.combinations(columns, 2):
        covered |= pair_covers[(left, right)]
    require(covered == (1 << len(kernel_rows)) - 1, "width-two witness does not span all elements")


def width_two_digest(records: Sequence[dict[str, Any]]) -> str:
    payload = [
        {
            "digest": record["digest"],
            "exists": record["width_two_basis_exists"],
            "complete": record["width_two_search_complete"],
            "canonical_width": record["canonical_width"],
            "witness_free_columns": record["width_two_witness_free_columns"],
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
                    screen = width_two_screen(formula)
                    width_bound = canonical_width(formula)
                    require(
                        width_bound > 2 or screen["exists"],
                        "canonical width contradicts the subset screen",
                    )
                    if screen["exists"]:
                        validate_witness(formula, screen["witness_free_columns"])
                    if index in BRUTEFORCE_SAMPLE:
                        brute = width_two_bruteforce(formula)
                        BRUTEFORCE_CROSS_CHECK.append(
                            {
                                "index": index,
                                "digest": formula_digest(formula),
                                "screen_exists": screen["exists"],
                                "bruteforce_exists": brute["exists"],
                                "bruteforce_covering_subsets": brute["covering_subsets"],
                                "agrees": screen["exists"] == brute["exists"],
                            }
                        )
                    records.append(
                        {
                            "digest": formula_digest(formula),
                            "connected": connected(formula),
                            "rank": shape["rank"],
                            "nullity": shape["nullity"],
                            "status": exact_status(formula),
                            "canonical_width": width_bound,
                            "width_two_basis_exists": screen["exists"],
                            "width_two_search_complete": screen["complete"],
                            "width_two_candidates_after_filter": screen["candidates_after_filter"],
                            "width_two_bases_examined": screen["bases_examined"],
                            "width_two_witness_free_columns": screen["witness_free_columns"],
                        }
                    )
    return records


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
    mixed_screen = width_two_screen(mixed)
    mixed_bruteforce = width_two_bruteforce(mixed)
    require(
        mixed_screen["exists"] == mixed_bruteforce["exists"],
        "mixed formula screen disagrees with full subset enumeration",
    )
    require(
        mixed_screen["exists"] == any(int(key) <= 2 for key in combined_widths),
        "mixed formula screen disagrees with the basis census",
    )
    expected_mixed.update(
        {
            "width_two_basis_exists": mixed_screen["exists"],
            "width_two_search_complete": mixed_screen["complete"],
            "width_two_candidates_after_filter": mixed_screen["candidates_after_filter"],
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
        "width_two_candidates_after_filter": sum(
            record["width_two_candidates_after_filter"] for record in records
        ),
        "width_two_bases_examined": sum(
            record["width_two_bases_examined"] for record in records
        ),
        "canonical_width_histogram": histogram(records, "canonical_width"),
        "width_exactly_three_formulas": sum(
            1
            for record in records
            if record["canonical_width"] == 3
            and record["width_two_search_complete"]
            and not record["width_two_basis_exists"]
        ),
        "width_two_screen_digest": width_two_digest(records),
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
    require(
        all(
            record["width_two_search_complete"]
            or record["width_two_basis_exists"]
            for record in records
        ),
        "width-two screening stopped without a witness",
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
        "switch_canonical_width_histogram": histogram(records, "canonical_width"),
        "bruteforce_cross_check": {
            "sampled": len(BRUTEFORCE_CROSS_CHECK),
            "agreement": sum(1 for item in BRUTEFORCE_CROSS_CHECK if item["agrees"]),
            "exists_histogram": histogram(BRUTEFORCE_CROSS_CHECK, "bruteforce_exists"),
        },
        "status": "verified",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
