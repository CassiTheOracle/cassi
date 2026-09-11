"""Bounded mixed-spectrum and one-switch frame-boundary probe.

This is not a random corpus. It composes the two independently censused
all-bases cubic controls, then enumerates every incidence 2-switch between the
SAT and UNSAT components. Each formula is screened for a width-two dual frame
by intersecting free-subset bitsets of element-pair spans, which is complete
for both answers: it decides the width-two question over all `C(n, nullity)`
free subsets and checks exact independence only for surviving candidates. The
independent verifier rebuilds the same formulas, screens, canonical widths, and
all aggregate counts without importing this file.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

from cubic_kernel_decision import (
    canonical_cubic_formula,
    cubic_kernel_profile,
    decide_cubic_kernel,
    incidence_connected,
)
from growing_nullity_schaefer_probe import (
    ALL_BASES_TERNARY_SAT,
    ALL_BASES_TERNARY_UNSAT,
    exact_basis_census,
    intersect_class_histograms,
    multiply_histograms,
)

OUTPUT = Path("_diag/mixed_schaefer_frame_obstruction.json")
SCHEMA = "cassifi.mixed-schaefer-frame-obstruction.v2"


def formula_digest(formula: Sequence[Sequence[int]]) -> str:
    canonical = canonical_cubic_formula(formula)
    payload = json.dumps(canonical, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def canonical_class_histogram(histogram: dict[str, int]) -> dict[str, int]:
    canonical: dict[str, int] = {}
    for raw_key, count in histogram.items():
        classes = () if raw_key == "none" else tuple(sorted(raw_key.split(",")))
        display_key = ",".join(classes) or "none"
        canonical[display_key] = canonical.get(display_key, 0) + count
    return {
        key: canonical[key]
        for key in sorted(canonical)
    }


def canonical_census(census: dict[str, Any]) -> dict[str, Any]:
    result = dict(census)
    result["common_schaefer_class_histogram"] = canonical_class_histogram(
        census["common_schaefer_class_histogram"]
    )
    return result


def rank_int(rows: Sequence[Sequence[int]]) -> int:
    """Exact rank of a small integer matrix by fraction-free elimination."""

    values = [list(row) for row in rows if any(row)]
    if not values:
        return 0
    columns = len(values[0])
    pivot_row = 0
    for column in range(columns):
        source = next(
            (row for row in range(pivot_row, len(values)) if values[row][column]),
            None,
        )
        if source is None:
            continue
        values[pivot_row], values[source] = values[source], values[pivot_row]
        lead = values[pivot_row][column]
        for row in range(pivot_row + 1, len(values)):
            if not values[row][column]:
                continue
            factor = values[row][column]
            values[row] = [
                lead * value - factor * pivot_value
                for value, pivot_value in zip(values[row], values[pivot_row], strict=True)
            ]
        pivot_row += 1
        if pivot_row == len(values):
            break
    return pivot_row


def dual_columns(formula: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    """Exact integer kernel-coordinate columns of the dual column matroid."""

    profile = cubic_kernel_profile(formula)
    rows: list[tuple[int, ...]] = []
    for vector in profile["kernel_basis"]:
        values = [Fraction(value) for value in vector]
        scale = 1
        for value in values:
            scale = math.lcm(scale, value.denominator)
        rows.append(tuple(int(value * scale) for value in values))
    return tuple(
        tuple(row[column] for row in rows) for column in range(len(profile["kernel_basis"][0]))
    )


def _build_subset_bits(
    size: int, nullity: int, bound: int
) -> dict[tuple[int, ...], int]:
    total = math.comb(size, nullity)
    byte_length = (total + 7) // 8
    payloads: dict[tuple[int, ...], bytearray] = {
        subset: bytearray(byte_length)
        for subset in itertools.combinations(range(size), bound)
    }
    for index, free in enumerate(itertools.combinations(range(size), nullity)):
        byte = index >> 3
        bit = 1 << (index & 7)
        for subset in itertools.combinations(free, bound):
            payloads[subset][byte] |= bit
    return {
        subset: int.from_bytes(bytes(payload), "little")
        for subset, payload in payloads.items()
    }


_SUBSET_BITS: dict[tuple[int, int, int], dict[tuple[int, ...], int]] = {}
_SUBSET_INDEX: dict[tuple[int, int], tuple[tuple[int, ...], ...]] = {}


def subset_bits(size: int, nullity: int, bound: int) -> dict[tuple[int, ...], int]:
    """Map each element subset of size ``bound`` to the free subsets containing it."""

    key = (size, nullity, bound)
    cached = _SUBSET_BITS.get(key)
    if cached is None:
        cached = _build_subset_bits(size, nullity, bound)
        _SUBSET_BITS[key] = cached
    return cached


def free_subsets(size: int, nullity: int) -> tuple[tuple[int, ...], ...]:
    key = (size, nullity)
    cached = _SUBSET_INDEX.get(key)
    if cached is None:
        cached = tuple(itertools.combinations(range(size), nullity))
        _SUBSET_INDEX[key] = cached
    return cached


def column_classes(
    columns: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[tuple[int, ...], ...]]:
    """Group parallel columns so pair spans are computed once per class pair."""

    order: dict[tuple[int, ...], int] = {}
    class_of: list[int] = []
    class_masks: list[int] = []
    representatives: list[tuple[int, ...]] = []
    for element, column in enumerate(columns):
        scale = 0
        for value in column:
            scale = math.gcd(scale, abs(value))
        reduced = tuple(column)
        if scale:
            reduced = tuple(value // scale for value in column)
            for value in reduced:
                if value:
                    if value < 0:
                        reduced = tuple(-item for item in reduced)
                    break
        index = order.get(reduced)
        if index is None:
            index = len(class_masks)
            order[reduced] = index
            class_masks.append(0)
            representatives.append(reduced)
        class_of.append(index)
        class_masks[index] |= 1 << element
    return tuple(class_of), tuple(class_masks), tuple(representatives)


def covering_subsets(
    columns: tuple[tuple[int, ...], ...], bound: int
) -> tuple[list[list[tuple[int, ...]]], dict[tuple[int, ...], int]]:
    """Index the elements covered by every ``bound``-subset of the ground set.

    Width ``w`` means every ground-set element lies in the span of at most ``w``
    elements of the free set, so ``bound = w`` coverage inside ``F`` is exactly
    the width-at-most-``bound`` test for an independent ``F``. Returns the
    element-to-covering-subsets index and the subset-to-element-mask table.
    """

    size = len(columns)
    class_of, class_masks, representatives = column_classes(columns)
    class_count = len(class_masks)
    by_multiset: dict[tuple[int, ...], int] = {}
    for multiset in itertools.combinations_with_replacement(range(class_count), bound):
        rows = tuple(representatives[index] for index in multiset)
        base = rank_int(rows)
        cover = 0
        for candidate in range(class_count):
            if rank_int(rows + (representatives[candidate],)) == base:
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


def coverage_screen(
    columns: tuple[tuple[int, ...], ...], bound: int
) -> dict[str, Any]:
    """Decide whether a free basis is spanned by ``bound``-subsets of itself.

    The subset bitsets keep exactly the free subsets whose internal
    ``bound``-subsets already cover the ground set, so an empty intersection is
    complete over all free subsets. Survivors are ranked until one is
    independent; a positive answer stops at the first independent survivor.
    """

    size = len(columns)
    nullity = len(columns[0]) if size else 0
    covers, subset_masks = covering_subsets(columns, bound)
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

    subsets = free_subsets(size, nullity)
    candidates_examined = 0
    remaining = candidates
    while remaining:
        low = remaining & -remaining
        index = low.bit_length() - 1
        remaining ^= low
        free_columns = subsets[index]
        candidates_examined += 1
        if nullity <= bound or rank_int(
            tuple(columns[column] for column in free_columns)
        ) == nullity:
            covered = 0
            for subset in itertools.combinations(free_columns, bound):
                covered |= subset_masks[subset]
            if covered != (1 << size) - 1:
                raise AssertionError("subset bitset filter admitted an uncovered free set")
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


def basis_width(
    columns: tuple[tuple[int, ...], ...], free_columns: Sequence[int]
) -> int:
    """Exact maximum pivot-free support of one independent free set.

    Row-reduce the matrix whose columns are the free vectors while the whole
    ground set rides along as a right-hand side; the reduced table holds the
    coordinates of every element in the free set, so the largest number of
    non-zero coordinates over the elements is the frame width of that basis.
    """

    size = len(columns)
    width_of = len(free_columns)
    matrix = [
        [Fraction(columns[free_columns[index]][coordinate]) for index in range(width_of)]
        for coordinate in range(width_of)
    ]
    table = [
        [Fraction(columns[element][coordinate]) for element in range(size)]
        for coordinate in range(width_of)
    ]
    for column in range(width_of):
        source = next(
            (row for row in range(column, width_of) if matrix[row][column]), None
        )
        if source is None:
            raise AssertionError("free set is not independent")
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


def frame_screen(formula: Sequence[Sequence[int]]) -> dict[str, Any]:
    """Decide the frame width of one cubic incidence matrix as far as it closes.

    Bound two closes either way: a witness means ``omega <= 2``, an empty
    intersection means ``omega >= 3``. Bound three then either exhibits an
    independent free set whose exact width is measured directly, or certifies
    ``omega >= 4``.
    """

    columns = dual_columns(formula)
    canonical = cubic_kernel_profile(formula)["maximum_pivot_free_support"]
    width_two = coverage_screen(columns, 2)
    if width_two["exists"]:
        witness = [column - 1 for column in width_two["witness_free_columns"] or []]
        width = basis_width(columns, witness)
        if width > 2:
            raise AssertionError("width-two witness failed exact width validation")
        return {
            "width_two_basis_exists": True,
            "width_two_search_complete": False,
            "width_two_candidates_after_filter": width_two["candidates_after_filter"],
            "width_two_candidates_examined": width_two["candidates_examined"],
            "width_three_basis_exists": None,
            "width_three_search_complete": None,
            "width_three_candidates_after_filter": None,
            "width_three_candidates_examined": None,
            "canonical_width": canonical,
            "witness_free_columns": width_two["witness_free_columns"],
            "witness_width": width,
            "omega": width,
            "omega_exact": True,
        }

    width_three = coverage_screen(columns, 3)
    if width_three["exists"]:
        witness = [column - 1 for column in width_three["witness_free_columns"] or []]
        width = basis_width(columns, witness)
        if width > 3:
            raise AssertionError("width-three witness failed exact width validation")
        return {
            "width_two_basis_exists": False,
            "width_two_search_complete": True,
            "width_two_candidates_after_filter": width_two["candidates_after_filter"],
            "width_two_candidates_examined": width_two["candidates_examined"],
            "width_three_basis_exists": True,
            "width_three_search_complete": False,
            "width_three_candidates_after_filter": width_three["candidates_after_filter"],
            "width_three_candidates_examined": width_three["candidates_examined"],
            "canonical_width": canonical,
            "witness_free_columns": width_three["witness_free_columns"],
            "witness_width": width,
            "omega": width,
            "omega_exact": width == 3,
        }
    return {
        "width_two_basis_exists": False,
        "width_two_search_complete": True,
        "width_two_candidates_after_filter": width_two["candidates_after_filter"],
        "width_two_candidates_examined": width_two["candidates_examined"],
        "width_three_basis_exists": False,
        "width_three_search_complete": True,
        "width_three_candidates_after_filter": width_three["candidates_after_filter"],
        "width_three_candidates_examined": width_three["candidates_examined"],
        "canonical_width": canonical,
        "witness_free_columns": None,
        "witness_width": None,
        "omega": None,
        "omega_exact": False,
        "omega_lower_bound": 4,
    }


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




def mixed_formula() -> tuple[tuple[int, int, int], ...]:
    sat_size = len(ALL_BASES_TERNARY_SAT)
    return canonical_cubic_formula(
        tuple(ALL_BASES_TERNARY_SAT)
        + tuple(
            tuple(variable + sat_size for variable in clause)
            for clause in ALL_BASES_TERNARY_UNSAT
        )
    )


def switch_formula(
    left_row: int,
    left_variable: int,
    right_row: int,
    right_variable: int,
) -> tuple[tuple[int, int, int], ...]:
    sat_size = len(ALL_BASES_TERNARY_SAT)
    rows = [set(clause) for clause in ALL_BASES_TERNARY_SAT]
    rows.extend(
        set(variable + sat_size for variable in clause)
        for clause in ALL_BASES_TERNARY_UNSAT
    )
    if left_variable not in rows[left_row] or right_variable not in rows[right_row]:
        raise AssertionError("switch source incidence is absent")
    if right_variable in rows[left_row] or left_variable in rows[right_row]:
        raise AssertionError("switch would duplicate an incidence")
    rows[left_row].remove(left_variable)
    rows[left_row].add(right_variable)
    rows[right_row].remove(right_variable)
    rows[right_row].add(left_variable)
    return canonical_cubic_formula(tuple(tuple(sorted(row)) for row in rows))


def switch_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    sat_size = len(ALL_BASES_TERNARY_SAT)
    for left_row, left_clause in enumerate(ALL_BASES_TERNARY_SAT):
        for left_variable in left_clause:
            for right_row, right_clause in enumerate(ALL_BASES_TERNARY_UNSAT):
                for right_variable_local in right_clause:
                    right_variable = right_variable_local + sat_size
                    formula = switch_formula(
                        left_row,
                        left_variable,
                        sat_size + right_row,
                        right_variable,
                    )
                    decision = decide_cubic_kernel(formula)
                    profile = cubic_kernel_profile(formula)
                    screen = frame_screen(formula)
                    records.append(
                        {
                            "digest": formula_digest(formula),
                            "connected": incidence_connected(formula),
                            "rank": profile["rank"],
                            "nullity": profile["nullity"],
                            "status": decision["status"],
                            "canonical_width": screen["canonical_width"],
                            **screen,
                        }
                    )
    return records


def histogram(records: Sequence[dict[str, Any]], field: str) -> dict[str, int]:
    counts = Counter(str(record[field]) for record in records)
    return {key: counts[key] for key in sorted(counts, key=lambda item: (len(item), item))}


def build_receipt() -> dict[str, Any]:
    sat_census = canonical_census(exact_basis_census(ALL_BASES_TERNARY_SAT))
    unsat_census = canonical_census(exact_basis_census(ALL_BASES_TERNARY_UNSAT))
    mixed = mixed_formula()
    mixed_profile = cubic_kernel_profile(mixed)
    mixed_decision = decide_cubic_kernel(mixed)
    mixed_width_histogram = multiply_histograms(
        sat_census["basis_width_histogram"],
        unsat_census["basis_width_histogram"],
    )
    mixed_class_histogram = canonical_class_histogram(
        intersect_class_histograms(
            sat_census["common_schaefer_class_histogram"],
            unsat_census["common_schaefer_class_histogram"],
        )
    )
    records = switch_records()
    digests = sorted(record["digest"] for record in records)
    digest_payload = json.dumps(digests, separators=(",", ":"))
    mixed_screen = frame_screen(mixed)
    census_has_width_two = any(int(key) <= 2 for key in mixed_width_histogram)
    if mixed_screen["width_two_basis_exists"] != census_has_width_two:
        raise AssertionError("subset filter disagrees with the exhaustive basis census")
    census_width_three = all(int(key) == 3 for key in mixed_width_histogram)
    if mixed_screen["omega"] is not None and census_width_three:
        if mixed_screen["omega"] != 3:
            raise AssertionError("mixed witness width disagrees with the width-three census")
    if census_width_three and not mixed_screen["omega_exact"]:
        raise AssertionError("mixed width-three census did not close exactly")
    if census_width_three:
        if mixed_screen["width_three_candidates_after_filter"] != sum(
            mixed_width_histogram.values()
        ):
            raise AssertionError("mixed triple-coverage survivors do not match the census")
    return {
        "schema": SCHEMA,
        "components": {
            "sat": sat_census,
            "unsat": unsat_census,
        },
        "mixed_direct_sum": {
            "formula": [list(clause) for clause in mixed],
            "formula_sha256": formula_digest(mixed),
            "variables": len(mixed),
            "rank": mixed_profile["rank"],
            "nullity": mixed_profile["nullity"],
            "connected": incidence_connected(mixed),
            "status": mixed_decision["status"],
            "column_bases": sat_census["column_bases_found"] * unsat_census["column_bases_found"],
            "basis_width_histogram": mixed_width_histogram,
            "common_schaefer_class_histogram": mixed_class_histogram,
            "all_bases_width_at_least_three": all(
                int(key) >= 3 for key in mixed_width_histogram
            ),
            **mixed_screen,
            "width_two_agrees_with_census": (
                mixed_screen["width_two_basis_exists"] == census_has_width_two
            ),
        },
        "one_switch_enumeration": {
            "left_component_incidence_edges": sum(len(clause) for clause in ALL_BASES_TERNARY_SAT),
            "right_component_incidence_edges": sum(len(clause) for clause in ALL_BASES_TERNARY_UNSAT),
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
            "formula_digest_sha256": hashlib.sha256(digest_payload.encode("ascii")).hexdigest(),
        },
        "scope": {
            "frame_property": "ground-set dual basis with every fundamental circuit of size at most three",
            "one_switches_only": True,
            "known_cross_component_edge_cut": 2,
            "connected_frame_screened": True,
            "screen_certificate": "exact bound-coverage filter over all binomial(n,k) free subsets of each formula, with exact independence for survivors and exact rational width for every witness",
            "no_hardness_claim": True,
        },
    }


def main() -> None:
    receipt = build_receipt()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema": receipt["schema"],
        "mixed": {
            "variables": receipt["mixed_direct_sum"]["variables"],
            "rank": receipt["mixed_direct_sum"]["rank"],
            "nullity": receipt["mixed_direct_sum"]["nullity"],
            "column_bases": receipt["mixed_direct_sum"]["column_bases"],
            "width_histogram": receipt["mixed_direct_sum"]["basis_width_histogram"],
            "common_classes": receipt["mixed_direct_sum"]["common_schaefer_class_histogram"],
        },
        "one_switch": receipt["one_switch_enumeration"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
