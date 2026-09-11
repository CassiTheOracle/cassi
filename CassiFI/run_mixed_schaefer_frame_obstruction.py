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


def _build_pair_subset_bits(size: int, nullity: int) -> dict[tuple[int, int], int]:
    subsets = math.comb(size, nullity)
    byte_length = (subsets + 7) // 8
    payloads: dict[tuple[int, int], bytearray] = {
        pair: bytearray(byte_length) for pair in itertools.combinations(range(size), 2)
    }
    for index, subset in enumerate(itertools.combinations(range(size), nullity)):
        byte = index >> 3
        bit = 1 << (index & 7)
        for pair in itertools.combinations(subset, 2):
            payloads[pair][byte] |= bit
    return {
        pair: int.from_bytes(bytes(payload), "little")
        for pair, payload in payloads.items()
    }


_SUBSET_BITS: dict[tuple[int, int], dict[tuple[int, int], int]] = {}
_SUBSET_INDEX: dict[tuple[int, int], tuple[tuple[int, ...], ...]] = {}


def pair_subset_bits(size: int, nullity: int) -> dict[tuple[int, int], int]:
    """Map each element pair to the free subsets that contain it."""

    key = (size, nullity)
    cached = _SUBSET_BITS.get(key)
    if cached is None:
        cached = _build_pair_subset_bits(size, nullity)
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


def width_two_screen(formula: Sequence[Sequence[int]]) -> dict[str, Any]:
    """Exhaustively decide whether some column basis frames the dual in width two.

    A free set ``F`` frames the dual exactly when every ground-set element lies
    in the span of at most two elements of ``F``. The screen first intersects
    subset bitsets to keep only free subsets whose internal pairs cover the
    whole ground set, then checks exact independence for any survivor.
    """

    columns = dual_columns(formula)
    size = len(columns)
    nullity = len(columns[0]) if size else 0
    class_of, class_masks, representatives = column_classes(columns)
    class_pair_masks: dict[tuple[int, int], int] = {}
    for left in range(len(class_masks)):
        for right in range(left, len(class_masks)):
            cover = 0
            if left == right:
                cover = class_masks[left]
            else:
                pair_rank = rank_int((representatives[left], representatives[right]))
                for candidate in range(len(class_masks)):
                    if (
                        rank_int(
                            (
                                representatives[left],
                                representatives[right],
                                representatives[candidate],
                            )
                        )
                        == pair_rank
                    ):
                        cover |= class_masks[candidate]
            class_pair_masks[(left, right)] = cover

    pair_covers: dict[tuple[int, int], int] = {}
    element_pairs: list[list[tuple[int, int]]] = [[] for _ in range(size)]
    for left, right in itertools.combinations(range(size), 2):
        low, high = sorted((class_of[left], class_of[right]))
        cover = class_pair_masks[(low, high)]
        pair_covers[(left, right)] = cover
        for element in range(size):
            if (cover >> element) & 1:
                element_pairs[element].append((left, right))

    full = (1 << size) - 1
    bits = pair_subset_bits(size, nullity)
    order = sorted(range(size), key=lambda element: len(element_pairs[element]))
    candidates = (1 << math.comb(size, nullity)) - 1
    for element in order:
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

    subsets = free_subsets(size, nullity)
    bases_examined = 0
    remaining = candidates
    while remaining:
        low = remaining & -remaining
        index = low.bit_length() - 1
        remaining ^= low
        free_columns = subsets[index]
        if nullity <= 2 or rank_int(
            tuple(columns[column] for column in free_columns)
        ) == nullity:
            bases_examined += 1
            covered = 0
            for pair in itertools.combinations(free_columns, 2):
                covered |= pair_covers[pair]
            if covered != full:
                raise AssertionError("subset bitset filter admitted an uncovered free set")
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
                    screen = width_two_screen(formula)
                    records.append(
                        {
                            "digest": formula_digest(formula),
                            "connected": incidence_connected(formula),
                            "rank": profile["rank"],
                            "nullity": profile["nullity"],
                            "status": decision["status"],
                            "canonical_width": profile["maximum_pivot_free_support"],
                            "width_two_basis_exists": screen["exists"],
                            "width_two_search_complete": screen["complete"],
                            "width_two_candidates_after_filter": screen["candidates_after_filter"],
                            "width_two_bases_examined": screen["bases_examined"],
                            "width_two_witness_free_columns": screen["witness_free_columns"],
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
    mixed_screen = width_two_screen(mixed)
    census_has_width_two = any(int(key) <= 2 for key in mixed_width_histogram)
    if mixed_screen["exists"] != census_has_width_two:
        raise AssertionError("subset filter disagrees with the exhaustive basis census")
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
            "width_two_basis_exists": mixed_screen["exists"],
            "width_two_search_complete": mixed_screen["complete"],
            "width_two_candidates_after_filter": mixed_screen["candidates_after_filter"],
            "width_two_agrees_with_census": mixed_screen["exists"] == census_has_width_two,
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
            "formula_digest_sha256": hashlib.sha256(digest_payload.encode("ascii")).hexdigest(),
        },
        "scope": {
            "frame_property": "ground-set dual basis with every fundamental circuit of size at most three",
            "one_switches_only": True,
            "known_cross_component_edge_cut": 2,
            "connected_width_two_screened": True,
            "screen_certificate": "exact pair-coverage filter over all binomial(27,5) free subsets, with exact independence for survivors",
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
