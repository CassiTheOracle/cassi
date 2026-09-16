"""Exact Schaefer-basis census for a scalable cubic incidence family.

The all-bases-ternary controls are fixed cubic incidence matrices whose every
column basis has maximum pivot-free support three. Direct sums preserve the
column-matroid basis product and make nullity grow linearly. A one-switch
connected SAT bridge is included as a finite connected control; its width is
exhausted exactly, but it is not used as a claim about all larger connected
families.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

from cubic_kernel_decision import (
    _system_for_pivot_basis,
    canonical_cubic_formula,
    cubic_kernel_basis_width,
    cubic_kernel_profile,
    cubic_kernel_zero_valid_basis,
    incidence_connected,
    incidence_matrix,
    decide_cubic_kernel,
)
from run_cubic_kernel_analysis import (
    ALL_BASES_TERNARY_SAT,
    ALL_BASES_TERNARY_UNSAT,
    SCHAEFER_CLASSES,
    relation_language_profile,
    relation_properties,
)

OUTPUT = Path("_diag/growing_nullity_schaefer_probe.json")
SCHEMA = "cassifi.growing-nullity-schaefer.v1"


def formula_digest(formula: Sequence[Sequence[int]]) -> str:
    canonical = canonical_cubic_formula(formula)
    payload = json.dumps(canonical, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def offset_formula(
    formula: Sequence[Sequence[int]], offset: int
) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        (clause[0] + offset, clause[1] + offset, clause[2] + offset)
        for clause in formula
    )


def direct_sum(
    formula: Sequence[Sequence[int]], blocks: int
) -> tuple[tuple[int, int, int], ...]:
    size = len(formula)
    return canonical_cubic_formula(
        tuple(
            clause
            for block in range(blocks)
            for clause in offset_formula(formula, block * size)
        )
    )


def switched_bridge(
    formula: Sequence[Sequence[int]],
) -> tuple[tuple[int, int, int], ...]:
    """Join two copies by one degree-preserving incidence 2-switch."""

    size = len(formula)
    rows = [set(clause) for clause in formula]
    rows.extend(
        set(clause)
        for clause in offset_formula(formula, size)
    )
    left_row = 0
    right_row = size
    left_variable = formula[0][0]
    right_variable = size + formula[0][0]
    if left_variable not in rows[left_row] or right_variable not in rows[right_row]:
        raise AssertionError("bridge source edges are absent")
    if right_variable in rows[left_row] or left_variable in rows[right_row]:
        raise AssertionError("bridge switch would duplicate an incidence edge")
    rows[left_row].remove(left_variable)
    rows[left_row].add(right_variable)
    rows[right_row].remove(right_variable)
    rows[right_row].add(left_variable)
    raw_rows = [tuple(sorted(row)) for row in rows]
    return canonical_cubic_formula(raw_rows)


def class_key(classes: Sequence[str]) -> str:
    return ",".join(classes) if classes else "none"


def relation_classes_for_system(
    system: dict[str, Any],
) -> tuple[str, ...]:
    relations: list[dict[str, bool]] = []
    for coefficients in system["pivot_free_coefficients"]:
        # RREF stores pivot + c*free = 0; the kernel pivot values are -c.
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
    return tuple(
        name
        for name in SCHAEFER_CLASSES
        if all(relation[name] for relation in relations)
    )


def exact_basis_census(
    formula: Sequence[Sequence[int]],
) -> dict[str, Any]:
    canonical = canonical_cubic_formula(formula)
    matrix = incidence_matrix(canonical)
    profile = cubic_kernel_profile(canonical)
    rank = profile["rank"]
    width_histogram: dict[str, int] = {}
    class_histogram: dict[str, int] = {}
    basis_count = 0
    for pivots in itertools.combinations(range(len(canonical)), rank):
        system = _system_for_pivot_basis(matrix, pivots)
        if system is None:
            continue
        basis_count += 1
        width = max(system["pivot_free_supports"], default=0)
        width_key = str(width)
        width_histogram[width_key] = width_histogram.get(width_key, 0) + 1
        classes = class_key(relation_classes_for_system(system))
        class_histogram[classes] = class_histogram.get(classes, 0) + 1
    return {
        "formula_sha256": formula_digest(canonical),
        "clauses": len(canonical),
        "variables": len(canonical),
        "rank": rank,
        "nullity": profile["nullity"],
        "column_subsets_checked": math.comb(len(canonical), rank),
        "column_bases_found": basis_count,
        "basis_width_histogram": {
            key: width_histogram[key] for key in sorted(width_histogram, key=int)
        },
        "common_schaefer_class_histogram": {
            key: class_histogram[key] for key in sorted(class_histogram)
        },
        "minimum_width": min(map(int, width_histogram)),
        "maximum_width": max(map(int, width_histogram)),
        "all_bases_width_at_least_three": all(
            int(key) >= 3 for key in width_histogram
        ),
    }


def multiply_histograms(
    left: dict[str, int], right: dict[str, int]
) -> dict[str, int]:
    output: dict[str, int] = {}
    for left_key, left_count in left.items():
        for right_key, right_count in right.items():
            key = str(max(int(left_key), int(right_key)))
            output[key] = output.get(key, 0) + left_count * right_count
    return output


def intersect_class_histograms(
    left: dict[str, int], right: dict[str, int]
) -> dict[str, int]:
    output: dict[str, int] = {}
    for left_key, left_count in left.items():
        left_classes = set() if left_key == "none" else set(left_key.split(","))
        for right_key, right_count in right.items():
            right_classes = set() if right_key == "none" else set(right_key.split(","))
            key = class_key(sorted(left_classes & right_classes))
            output[key] = output.get(key, 0) + left_count * right_count
    return output


def scaled_direct_sum(
    component: dict[str, Any], blocks: int, *, satisfiable: bool
) -> dict[str, Any]:
    width_histogram = {"1": 1}
    class_histogram = {class_key(SCHAEFER_CLASSES): 1}
    for _ in range(blocks):
        width_histogram = multiply_histograms(
            width_histogram, component["basis_width_histogram"]
        )
        class_histogram = intersect_class_histograms(
            class_histogram,
            component["common_schaefer_class_histogram"],
        )
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
        "zero_valid_basis_exists": satisfiable,
        "construction": "direct_sum_product_of_component_bases",
    }


def build_receipt() -> dict[str, Any]:
    sat_component = exact_basis_census(ALL_BASES_TERNARY_SAT)
    unsat_component = exact_basis_census(ALL_BASES_TERNARY_UNSAT)
    sat_decision = decide_cubic_kernel(ALL_BASES_TERNARY_SAT)
    unsat_decision = decide_cubic_kernel(ALL_BASES_TERNARY_UNSAT)
    if sat_decision["status"] != "sat" or unsat_decision["status"] != "unsat":
        raise AssertionError("component status changed")
    sat_certificate = cubic_kernel_zero_valid_basis(
        ALL_BASES_TERNARY_SAT, sat_decision["assignment"]
    )
    bridge = switched_bridge(ALL_BASES_TERNARY_SAT)
    bridge_profile = cubic_kernel_profile(bridge)
    bridge_width = cubic_kernel_basis_width(
        bridge, maximum_column_subsets=2_000_000
    )
    if not incidence_connected(bridge) or bridge_width["minimum_maximum_pivot_free_support"] != 3:
        raise AssertionError("connected bridge left the intended width-three boundary")
    scaling = {
        "sat": [
            scaled_direct_sum(sat_component, blocks, satisfiable=True)
            for blocks in (1, 2, 4, 8, 16)
        ],
        "unsat": [
            scaled_direct_sum(unsat_component, blocks, satisfiable=False)
            for blocks in (1, 2, 4, 8, 16)
        ],
    }
    return {
        "schema": SCHEMA,
        "components": {
            "sat": {
                "formula": [list(clause) for clause in ALL_BASES_TERNARY_SAT],
                "status": "sat",
                "census": sat_component,
                "zero_valid_certificate": sat_certificate,
            },
            "unsat": {
                "formula": [list(clause) for clause in ALL_BASES_TERNARY_UNSAT],
                "status": "unsat",
                "census": unsat_component,
                "zero_valid_certificate": None,
            },
        },
        "scaling": scaling,
        "connected_bridge": {
            "formula": [list(clause) for clause in bridge],
            "formula_sha256": formula_digest(bridge),
            "connected": True,
            "profile": bridge_profile,
            "basis_width": bridge_width,
            "canonical_relation_language": relation_language_profile(bridge_profile),
            "scope": "exact connected n=24 control only",
        },
        "conclusion": {
            "direct_sum_width_three_is_exact": True,
            "nullity_grows_linearly": True,
            "direct_sum_is_disconnected": True,
            "connected_bridge_preserves_width_three_at_n24": True,
            "connected_unbounded_width_classification": "not established",
            "zero_valid_basis_is_not_width_two": True,
        },
    }


def main() -> None:
    receipt = build_receipt()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "schema": receipt["schema"],
        "sat_scaling": receipt["scaling"]["sat"],
        "unsat_scaling": receipt["scaling"]["unsat"],
        "bridge_minimum_width": receipt["connected_bridge"]["basis_width"]["minimum_maximum_pivot_free_support"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
