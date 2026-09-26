"""Measure mandatory-class obstructions for internal width-two recognition.

This probe reuses the production exact geometry only in the producer.  It
measures the proved obstruction "every class outside every rich projective
line must be selected" on rational residual families and cubic controls.
Local obstruction minima are exhaustively computed only under explicit caps;
cap hits are recorded as inconclusive rather than treated as negative cases.
"""

from __future__ import annotations

import itertools
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Sequence
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cubic_kernel_decision as production
from run_cubic_kernel_analysis import (
    ALL_BASES_TERNARY_SAT,
    ALL_BASES_TERNARY_UNSAT,
    SUPPORT_THREE_SAT,
    SUPPORT_THREE_UNSAT,
)

OUTPUT = Path("_diag/mandatory_class_obstruction_probe.json")
SCHEMA = "cassifi.mandatory-class-obstruction-probe.v2"
BASIS_ENUM_CAP = 5_000
LOCAL_SUBSET_CAP = 200_000

Vector = tuple[Fraction, ...]


def axes(dimension: int) -> tuple[Vector, ...]:
    return tuple(
        tuple(Fraction(int(row == column)) for row in range(dimension))
        for column in range(dimension)
    )


def add(left: Sequence[Fraction], right: Sequence[Fraction]) -> Vector:
    return tuple(a + b for a, b in zip(left, right, strict=True))


def scale(factor: int | Fraction, value: Sequence[Fraction]) -> Vector:
    return tuple(Fraction(factor) * item for item in value)


def projective(value: Sequence[int | Fraction]) -> Vector | None:
    values = tuple(Fraction(item) for item in value)
    first = next((item for item in values if item), None)
    if first is None:
        return None
    return tuple(item / first for item in values)


def unique_classes(values: Iterable[Sequence[int | Fraction]]) -> tuple[Vector, ...]:
    result: list[Vector] = []
    seen: set[Vector] = set()
    for value in values:
        key = projective(value)
        if key is not None and key not in seen:
            seen.add(key)
            result.append(key)
    return tuple(result)


def line(
    left: Sequence[Fraction], right: Sequence[Fraction], parameters: Sequence[int] = (1, 2)
) -> tuple[Vector, ...]:
    return unique_classes(
        (left, right)
        + tuple(add(left, scale(parameter, right)) for parameter in parameters)
    )


def growing_residual(q: int, family: str) -> tuple[Vector, ...]:
    dimension = q + 2
    frame = axes(dimension)
    long_line = line(frame[0], frame[1])
    if family == "moment_negative":
        residual = tuple(
            projective((0, 0) + tuple(Fraction(t) ** power for power in range(q)))
            for t in range(1, 2 * q + 1)
        )
        return long_line + tuple(value for value in residual if value is not None)
    if family == "path_positive":
        residual = tuple(
            add(frame[index], frame[index + 1]) for index in range(2, q + 1)
        ) + frame[2:]
        return long_line + residual
    raise ValueError(f"unknown residual family: {family}")


def direct_sum(
    left: Sequence[Sequence[int]], right: Sequence[Sequence[int]]
) -> tuple[tuple[int, int, int], ...]:
    offset = len(left)
    rows = [tuple(int(value) for value in row) for row in left]
    rows.extend(tuple(value + offset for value in row) for row in right)
    return production.canonical_cubic_formula(tuple(rows))


def rank(vectors: Sequence[Sequence[Fraction | int]]) -> int:
    return production._vector_rank(
        tuple(tuple(Fraction(value) for value in vector) for vector in vectors)
    )


def pair_coverage_mask(classes: Sequence[Vector], basis: Sequence[int]) -> int:
    covered = sum(1 << index for index in basis)
    for left, right in itertools.combinations(basis, 2):
        for target, point in enumerate(classes):
            if rank((classes[left], classes[right], point)) <= 2:
                covered |= 1 << target
    return covered


def exact_local_obstruction(
    geometry: dict[str, Any],
    nullity: int,
    *,
    applicable: bool,
    basis_cap: int = BASIS_ENUM_CAP,
) -> dict[str, Any]:
    """Measure the minimum nonempty missed class subset for a NO case.

    Basis combinations use original column indices.  Projective duplicate
    columns remain distinct for basis counts and independence; only the
    coverage target is deduplicated to projective class indices.  The minimum
    is searched by increasing nonempty subset size, so an exact witness is
    minimal against every smaller subset.
    """

    original_vectors = tuple(geometry["vectors"])
    classes = tuple(geometry["class_vectors"])
    column_classes = tuple(geometry["column_classes"])
    column_count = len(original_vectors)
    class_count = len(classes)
    basis_total = (
        math.comb(column_count, nullity)
        if 0 <= nullity <= column_count
        else 0
    )
    common = {
        "basis_index_space": "original_columns",
        "target_index_space": "projective_classes",
        "obstruction_defined": applicable,
        "basis_subsets_total": basis_total,
        "basis_subsets_checked": 0,
        "independent_bases": 0,
        "minimum_size": None,
        "witness_subset": None,
        "subset_sizes_checked": [],
    }
    if not applicable:
        return {
            **common,
            "status": "not_applicable",
            "reason": "positive_width_two_case",
        }
    if basis_total > basis_cap:
        return {
            **common,
            "status": "inconclusive",
            "reason": "basis_enum_cap",
        }

    coverage_masks: list[int] = []
    basis_subsets_checked = 0
    independent_bases = 0
    for chosen_columns in itertools.combinations(
        range(column_count), nullity
    ):
        basis_subsets_checked += 1
        if (
            rank(tuple(original_vectors[index] for index in chosen_columns))
            != nullity
        ):
            continue
        independent_bases += 1
        chosen_classes: list[int] = []
        for column in chosen_columns:
            class_index = column_classes[column]
            if class_index is not None and class_index not in chosen_classes:
                chosen_classes.append(class_index)
        coverage_masks.append(
            pair_coverage_mask(classes, tuple(sorted(chosen_classes)))
        )

    if not coverage_masks:
        return {
            **common,
            "status": "exact",
            "reason": "no_independent_ground_basis",
            "basis_subsets_checked": basis_subsets_checked,
            "independent_bases": independent_bases,
            "minimum_size": 1 if class_count else None,
            "witness_subset": [1] if class_count else None,
            "subset_sizes_checked": [1] if class_count else [],
        }

    subset_sizes_checked: list[int] = []
    for subset_size in range(1, class_count + 1):
        subset_total = math.comb(class_count, subset_size)
        if subset_total > LOCAL_SUBSET_CAP:
            return {
                **common,
                "status": "inconclusive",
                "reason": "local_subset_cap",
                "basis_subsets_checked": basis_subsets_checked,
                "independent_bases": independent_bases,
                "subset_sizes_checked": subset_sizes_checked,
            }
        subset_sizes_checked.append(subset_size)
        for chosen in itertools.combinations(range(class_count), subset_size):
            required = sum(1 << index for index in chosen)
            if not any(mask & required == required for mask in coverage_masks):
                return {
                    **common,
                    "status": "exact",
                    "reason": "minimum_uncoverable_subset",
                    "basis_subsets_checked": basis_subsets_checked,
                    "independent_bases": independent_bases,
                    "minimum_size": subset_size,
                    "witness_subset": [index + 1 for index in chosen],
                    "subset_sizes_checked": subset_sizes_checked,
                }

    return {
        **common,
        "status": "exact",
        "reason": "every_class_subset_coverable",
        "basis_subsets_checked": basis_subsets_checked,
        "independent_bases": independent_bases,
        "subset_sizes_checked": subset_sizes_checked,
    }


def mandatory_obstruction(
    geometry: dict[str, Any], nullity: int
) -> dict[str, Any]:
    classes = production._mandatory_basis_classes(geometry)
    vectors = geometry["class_vectors"]
    class_rank = rank(tuple(vectors[index] for index in classes))
    rejects = len(classes) > nullity or class_rank < len(classes)
    return {
        "classes": [index + 1 for index in classes],
        "count": len(classes),
        "rank": class_rank,
        "rejects": rejects,
        "cardinality_witness": (
            [index + 1 for index in classes[: nullity + 1]]
            if len(classes) > nullity
            else None
        ),
    }


def production_summary(
    result: dict[str, Any], geometry: dict[str, Any]
) -> dict[str, Any]:
    candidate_classes = result.get("candidate_classes")
    candidate_columns = None
    if candidate_classes is not None:
        candidate_columns = [
            geometry["class_columns"][index][0]
            for index in candidate_classes
        ]
    return {
        "status": result["status"],
        "reason": result["reason"],
        "residual_subsets_total": result.get("residual_subsets_total"),
        "residual_subsets_checked": result.get("residual_subsets_checked"),
        "endpoint_subsets_checked": result.get("endpoint_subsets_checked"),
        "independent_basis_candidates": result.get("independent_basis_candidates"),
        "candidate_free_columns": candidate_columns,
    }


def analyze_classes(
    name: str,
    vectors: Sequence[Vector],
    nullity: int,
    expected_status: str,
    *,
    kind: str,
    q: int | None = None,
    family: str | None = None,
    source: Sequence[Sequence[int]] | None = None,
    geometry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    vector_tuple = tuple(
        tuple(Fraction(value) for value in vector) for vector in vectors
    )
    resolved_geometry = (
        production._projective_geometry(vector_tuple)
        if geometry is None
        else geometry
    )
    class_vectors = tuple(resolved_geometry["class_vectors"])
    mandatory = mandatory_obstruction(resolved_geometry, nullity)
    production_result = production._width_two_geometry_basis(
        resolved_geometry, nullity
    )
    if production_result["status"] != expected_status:
        raise AssertionError(
            f"{name}: production status {production_result['status']} != {expected_status}"
        )
    local = exact_local_obstruction(
        resolved_geometry,
        nullity,
        applicable=expected_status == "no_width_two_basis",
    )
    return {
        "name": name,
        "kind": kind,
        "q": q,
        "family": family,
        "source": None if source is None else [list(row) for row in source],
        "nullity": nullity,
        "original_column_count": len(resolved_geometry["vectors"]),
        "class_count": len(class_vectors),
        "class_columns": [
            list(columns) for columns in resolved_geometry["class_columns"]
        ],
        "column_classes": [
            None if index is None else index + 1
            for index in resolved_geometry["column_classes"]
        ],
        "zero_column_indices": [
            index + 1
            for index, class_index in enumerate(
                resolved_geometry["column_classes"]
            )
            if class_index is None
        ],
        "maximum_line_size": max(
            (len(line_set) for line_set in resolved_geometry["lines"]),
            default=0,
        ),
        "mandatory": mandatory,
        "local_obstruction": local,
        "production": production_summary(production_result, resolved_geometry),
        "expected_status": expected_status,
    }


def build_specs() -> list[tuple[str, str, Any, int, str, int | None, str | None]]:
    specs: list[tuple[str, str, Any, int, str, int | None, str | None]] = [
        (
            "rational-coordinate-basis",
            "rational",
            axes(3),
            3,
            "width_two",
            None,
            None,
        ),
        (
            "rational-general-position-k3",
            "rational",
            axes(3) + ((Fraction(1), Fraction(1), Fraction(1)),),
            3,
            "no_width_two_basis",
            None,
            None,
        ),
    ]
    for q in range(3, 8):
        for family, expected in (
            ("moment_negative", "no_width_two_basis"),
            ("path_positive", "width_two"),
        ):
            specs.append(
                (
                    f"{family}-q{q}",
                    "rational",
                    growing_residual(q, family),
                    q + 2,
                    expected,
                    q,
                    family,
                )
            )
    cubic_specs = (
        ("support-three-sat-n9", SUPPORT_THREE_SAT, "width_two"),
        ("support-three-unsat-n15", SUPPORT_THREE_UNSAT, "width_two"),
        ("all-bases-ternary-sat-n12", ALL_BASES_TERNARY_SAT, "no_width_two_basis"),
        ("all-bases-ternary-unsat-n15", ALL_BASES_TERNARY_UNSAT, "no_width_two_basis"),
        (
            "support-three-sat+sat-n18",
            direct_sum(SUPPORT_THREE_SAT, SUPPORT_THREE_SAT),
            "width_two",
        ),
    )
    specs.extend(
        (
            name,
            "cubic",
            formula,
            len(formula) - len(production._system(formula)["pivot_columns_zero_based"]),
            expected,
            None,
            None,
        )
        for name, formula, expected in cubic_specs
    )
    return specs


def build_receipt() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for name, kind, source, nullity, expected, q, family in build_specs():
        if kind == "rational":
            case = analyze_classes(
                name,
                source,
                nullity,
                expected,
                kind=kind,
                q=q,
                family=family,
            )
        else:
            canonical = production.canonical_cubic_formula(source)
            system = production._system(canonical)
            geometry = production._projective_geometry(system, len(canonical))
            case = analyze_classes(
                name,
                geometry["vectors"],
                nullity,
                expected,
                kind=kind,
                source=canonical,
                geometry=geometry,
            )
        cases.append(case)
        local = case["local_obstruction"]
        print(
            f"{name:32s} k={nullity:2d} m={case['class_count']:2d} "
            f"columns={case['original_column_count']:2d} "
            f"mandatory={case['mandatory']['count']:2d} "
            f"local={local['status']:14s} "
            f"production={case['production']['status']}"
        )
    local_histogram: dict[str, int] = {}
    for case in cases:
        status = case["local_obstruction"]["status"]
        local_histogram[status] = local_histogram.get(status, 0) + 1
    return {
        "schema": SCHEMA,
        "status": "measured",
        "caps": {
            "basis_enum_cap": BASIS_ENUM_CAP,
            "local_subset_cap": LOCAL_SUBSET_CAP,
        },
        "algorithm": {
            "mandatory_rule": (
                "classes outside every observed projective line with at least "
                "three classes must belong to every internal width-two basis"
            ),
            "local_obstruction": (
                "for no_width_two_basis cases only, minimum nonempty class "
                "subset missed by every enumerated independent original-column "
                "basis"
            ),
            "basis_semantics": (
                "enumerate original column indices; deduplicate only target "
                "coverage by projective class"
            ),
            "positive_semantics": (
                "width_two cases have undefined obstruction size and record "
                "minimum_size=null"
            ),
            "cap_semantics": (
                "a basis-enumeration cap makes the local result inconclusive; "
                "partial coverage masks never produce a negative obstruction"
            ),
        },
        "summary": {
            "cases": len(cases),
            "kinds": {
                kind: sum(case["kind"] == kind for case in cases)
                for kind in sorted({case["kind"] for case in cases})
            },
            "local_statuses": dict(sorted(local_histogram.items())),
            "mandatory_rejections": sum(
                case["mandatory"]["rejects"] for case in cases
            ),
            "production_statuses": {
                status: sum(case["production"]["status"] == status for case in cases)
                for status in sorted({case["production"]["status"] for case in cases})
            },
            "maximum_nullity": max(case["nullity"] for case in cases),
            "maximum_class_count": max(case["class_count"] for case in cases),
            "maximum_original_column_count": max(
                case["original_column_count"] for case in cases
            ),
        },
        "cases": cases,
    }


def run(output: Path = OUTPUT) -> dict[str, Any]:
    receipt = build_receipt()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt["summary"], sort_keys=True))
    return receipt


if __name__ == "__main__":
    run()
