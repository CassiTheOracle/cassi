"""Reproduce the nullity-growth and endpoint-branch audit.

The rank, projective normalization, line discovery, and basis-width oracle in
this file are independent of the production geometry and completion routines.
The production result is compared against that oracle in a deliberate
white-box parity diagnostic, including direct completion calls for a residual
choice that fails after rank/layout filtering.  The fixtures are rational
projective configurations; they are not claimed to be kernels of cubic
incidence matrices.
"""

import argparse
import importlib.util
import itertools
import json
import math
from fractions import Fraction as Q
from pathlib import Path
from typing import Iterable, Sequence


_SPEC = importlib.util.spec_from_file_location(
    "cassifi_residual_search_production",
    Path(__file__).with_name("cubic_kernel_decision.py"),
)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("cannot load cubic_kernel_decision.py")
production = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(production)

Vector = tuple[Q, ...]


def axes(dimension: int) -> tuple[Vector, ...]:
    return tuple(
        tuple(Q(int(row == column)) for row in range(dimension))
        for column in range(dimension)
    )


def add(left: Sequence[Q], right: Sequence[Q]) -> Vector:
    return tuple(a + b for a, b in zip(left, right, strict=True))


def scale(factor: int | Q, value: Sequence[Q]) -> Vector:
    return tuple(Q(factor) * item for item in value)


def projective(value: Sequence[int | Q]) -> Vector | None:
    values = tuple(Q(item) for item in value)
    first = next((item for item in values if item), None)
    if first is None:
        return None
    return tuple(item / first for item in values)


def unique_classes(values: Iterable[Sequence[int | Q]]) -> tuple[Vector, ...]:
    result: list[Vector] = []
    seen: set[Vector] = set()
    for value in values:
        key = projective(value)
        if key is not None and key not in seen:
            seen.add(key)
            result.append(key)
    return tuple(result)


def line(
    left: Sequence[Q], right: Sequence[Q], parameters: Sequence[int] = (1, 2)
) -> tuple[Vector, ...]:
    return unique_classes(
        (left, right)
        + tuple(add(left, scale(parameter, right)) for parameter in parameters)
    )


def rank(values: Sequence[Sequence[Q]]) -> int:
    rows = [[Q(item) for item in value] for value in values if any(value)]
    if not rows:
        return 0
    width = len(rows[0])
    pivot = 0
    for column in range(width):
        source = next(
            (row for row in range(pivot, len(rows)) if rows[row][column]),
            None,
        )
        if source is None:
            continue
        rows[pivot], rows[source] = rows[source], rows[pivot]
        divisor = rows[pivot][column]
        rows[pivot] = [item / divisor for item in rows[pivot]]
        for row in range(len(rows)):
            if row == pivot or not rows[row][column]:
                continue
            factor = rows[row][column]
            rows[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(rows[row], rows[pivot], strict=True)
            ]
        pivot += 1
        if pivot == len(rows):
            break
    return pivot


def coordinates(basis: Sequence[Sequence[Q]], value: Sequence[Q]) -> tuple[Q, ...]:
    dimension = len(basis)
    if dimension == 0:
        if any(value):
            raise AssertionError("nonzero vector has no zero-dimensional coordinates")
        return ()
    rows = [
        [basis[column][row] for column in range(dimension)] + [value[row]]
        for row in range(dimension)
    ]
    for column in range(dimension):
        source = next(
            (row for row in range(column, dimension) if rows[row][column]),
            None,
        )
        if source is None:
            raise AssertionError("dependent basis in independent oracle")
        rows[column], rows[source] = rows[source], rows[column]
        divisor = rows[column][column]
        rows[column] = [item / divisor for item in rows[column]]
        for row in range(dimension):
            if row == column or not rows[row][column]:
                continue
            factor = rows[row][column]
            rows[row] = [
                item - factor * pivot_value
                for item, pivot_value in zip(rows[row], rows[column], strict=True)
            ]
    return tuple(rows[row][-1] for row in range(dimension))


def basis_width(classes: Sequence[Vector], chosen: Sequence[int]) -> int:
    basis = tuple(classes[index] for index in chosen)
    return max(
        (
            sum(item != 0 for item in coordinates(basis, value))
            for value in classes
        ),
        default=0,
    )


def line_universe(classes: Sequence[Vector]) -> tuple[tuple[int, ...], ...]:
    lines: set[tuple[int, ...]] = set()
    for left, right in itertools.combinations(range(len(classes)), 2):
        lines.add(
            tuple(
                index
                for index, value in enumerate(classes)
                if rank((classes[left], classes[right], value)) <= 2
            )
        )
    return tuple(sorted(lines))


def growing_residual(q: int, family: str) -> tuple[Vector, ...]:
    dimension = q + 2
    frame = axes(dimension)
    long_line = line(frame[0], frame[1])
    if family == "moment_negative":
        residual = tuple(
            projective((0, 0) + tuple(Q(t) ** power for power in range(q)))
            for t in range(1, 2 * q + 1)
        )
        return long_line + tuple(value for value in residual if value is not None)
    if family == "path_positive":
        residual = tuple(
            add(frame[index], frame[index + 1]) for index in range(2, q + 1)
        ) + frame[2:]
        return long_line + residual
    raise ValueError(f"unknown family: {family}")


def vandermonde_certificate(q: int, exhaustive: bool = False) -> int:
    dimension = q + 2
    residual_count = q + math.comb(dimension, 2) - 1
    nodes = tuple(range(1, residual_count + 1))
    if not exhaustive:
        # Distinct integer nodes make every Lagrange numerator and denominator
        # nonzero.  This proves the nonzero-coefficient obstruction for every
        # q-subset; one exact interpolation identity is retained as a spot
        # check of the symbolic argument.
        assert len(nodes) == len(set(nodes))
        selected = nodes[:q]
        target = nodes[q]
        coefficients = tuple(
            math.prod(
                Q(target - other, value - other)
                for other in selected
                if other != value
            )
            for value in selected
        )
        assert all(coefficients)
        assert tuple(
            sum(
                coefficient * Q(value) ** power
                for coefficient, value in zip(coefficients, selected, strict=True)
            )
            for power in range(q)
        ) == tuple(Q(target) ** power for power in range(q))
        return 1
    comparisons = 0
    for selected in itertools.combinations(nodes, q):
        target = next(value for value in nodes if value not in selected)
        coefficients = tuple(
            math.prod(
                Q(target - other, value - other)
                for other in selected
                if other != value
            )
            for value in selected
        )
        assert all(coefficients)
        assert tuple(
            sum(
                coefficient * Q(value) ** power
                for coefficient, value in zip(coefficients, selected, strict=True)
            )
            for power in range(q)
        ) == tuple(Q(target) ** power for power in range(q))
        comparisons += 1
    return comparisons


def audit_family(
    q: int, family: str, exhaustive: bool = False
) -> dict[str, object]:
    classes = unique_classes(growing_residual(q, family))
    nullity = q + 2
    all_lines = line_universe(classes)
    own_lines = tuple(line_set for line_set in all_lines if len(line_set) >= 4)
    assert len(own_lines) == 1
    geometry = production._projective_geometry(classes)
    assert {tuple(item) for item in geometry["long_lines"]} == set(own_lines)
    constraints = production._long_line_constraints(geometry, nullity)
    layout = production._prepare_long_line_layout(geometry, nullity, constraints)
    assert layout["reason"] is None
    assert layout["long_line_rank"] == 2
    residual_slots = layout["residual_slots"]
    residual_count = len(layout["residual_classes"])
    expected_subsets = math.comb(residual_count, residual_slots)

    result = None
    if exhaustive or q <= 4:
        result = production._width_two_geometry_basis(geometry, nullity)
        assert result["residual_subsets_total"] == expected_subsets

    if family == "moment_negative":
        certificate_checks = vandermonde_certificate(
            q, exhaustive=exhaustive or q <= 4
        )
        certified_status = "no_width_two_basis"
        certified_reason = "mandatory_class_and_vandermonde_certificate"
        oracle_width_two = 0
        if result is not None:
            assert result["status"] == certified_status
            if result["reason"] == "mandatory_class_obstruction":
                assert result["residual_subsets_checked"] == 0
                assert result["endpoint_subsets_checked"] == 0
            else:
                assert result["reason"] == "long_line_basis_search_exhausted"
                assert result["residual_subsets_checked"] == expected_subsets
                assert result["endpoint_subsets_checked"] == expected_subsets
    else:
        axis_start = q + 3
        candidate = (0, 1) + tuple(range(axis_start, axis_start + q))
        assert basis_width(classes, candidate) <= 2
        certificate_checks = 0
        certified_status = "width_two"
        certified_reason = "coordinate_basis_certificate"
        oracle_width_two = 1
        if result is not None:
            assert result["status"] == certified_status
            assert result["candidate_classes"] is not None

    class_basis_checks: int | None = None
    if exhaustive or q <= 4:
        oracle_width_two = 0
        class_basis_checks = 0
        for chosen in itertools.combinations(range(len(classes)), nullity):
            class_basis_checks += 1
            if rank(tuple(classes[index] for index in chosen)) != nullity:
                continue
            if basis_width(classes, chosen) <= 2:
                oracle_width_two += 1
        assert bool(oracle_width_two) == (certified_status == "width_two")

    long_line_union = set().union(*map(set, own_lines))
    mandatory = {
        index
        for index in range(len(classes))
        if not any(index in line_set for line_set in all_lines if len(line_set) >= 3)
    }
    mandatory_rejects = len(mandatory) > nullity
    assert mandatory_rejects == (family == "moment_negative")
    return {
        "family": family,
        "q": q,
        "nullity": nullity,
        "class_count": len(classes),
        "long_line_count": len(own_lines),
        "long_line_union_count": len(long_line_union),
        "residual_class_count": residual_count,
        "residual_slots": residual_slots,
        "residual_subsets_total": expected_subsets,
        "production_search": "run" if result is not None else "skipped",
        "production_status": (
            result["status"] if result is not None else certified_status
        ),
        "production_reason": (
            result["reason"] if result is not None else certified_reason
        ),
        "production_residual_subsets_checked": (
            result["residual_subsets_checked"] if result is not None else None
        ),
        "production_endpoint_subsets_checked": (
            result["endpoint_subsets_checked"] if result is not None else None
        ),
        "oracle_width_two_bases": oracle_width_two,
        "class_basis_checks": class_basis_checks,
        "vandermonde_identity_checks": certificate_checks,
        "mandatory_class_count": len(mandatory),
        "mandatory_class_rejects": mandatory_rejects,
    }

def endpoint_branch_audit() -> dict[str, object]:
    first, second, third = axes(3)
    classes = unique_classes(
        line(first, second, (1, 2, 4))
        + (
            third,
            add(third, first),
            add(third, add(first, scale(3, second))),
        )
    )
    nullity = 3
    all_lines = line_universe(classes)
    own_lines = tuple(line_set for line_set in all_lines if len(line_set) >= 4)
    assert len(own_lines) == 1
    geometry = production._projective_geometry(classes)
    assert {tuple(item) for item in geometry["long_lines"]} == set(own_lines)
    constraints = production._long_line_constraints(geometry, nullity)
    layout = production._prepare_long_line_layout(geometry, nullity, constraints)
    assert layout["reason"] is None
    assert layout["long_line_rank"] == 2
    assert layout["residual_slots"] == 1

    long_line_union = set().union(*map(set, own_lines))
    witnesses_by_residual: dict[tuple[int, ...], list[tuple[int, ...]]] = {}
    for chosen in itertools.combinations(range(len(classes)), nullity):
        if rank(tuple(classes[index] for index in chosen)) != nullity:
            continue
        if basis_width(classes, chosen) > 2:
            continue
        residual = tuple(sorted(set(chosen) - long_line_union))
        witnesses_by_residual.setdefault(residual, []).append(chosen)

    rows: list[dict[str, object]] = []
    quotient_independent_choices = 0
    positive_count = 0
    negative_count = 0
    negative_reasons: set[str] = set()
    for residual in itertools.combinations(
        layout["residual_classes"], layout["residual_slots"]
    ):
        reference = tuple(layout["reference_classes"]) + tuple(residual)
        assert rank(tuple(classes[index] for index in reference)) == nullity
        quotient_independent_choices += 1
        completion = production._complete_long_line_endpoints(
            geometry, nullity, residual, layout
        )
        expected = witnesses_by_residual.get(tuple(residual), [])
        expected_count = len(expected)
        candidate = completion["candidate_classes"]
        assert (candidate is not None) == bool(expected)
        completion_reason = str(completion["reason"])
        if expected_count:
            positive_count += 1
        else:
            negative_count += 1
            negative_reasons.add(completion_reason)
        if candidate is not None:
            assert tuple(sorted(set(candidate) - long_line_union)) == tuple(residual)
            assert basis_width(classes, candidate) <= 2
        rows.append(
            {
                "residual": list(residual),
                "quotient_independent": True,
                "oracle_witnesses": expected_count,
                "completion_candidate": (
                    None if candidate is None else list(candidate)
                ),
                "completion_reason": completion_reason,
                "endpoint_subsets_checked": completion[
                    "endpoint_subsets_checked"
                ],
            }
        )

    production_result = production._width_two_geometry_basis(
        geometry, nullity
    )
    assert positive_count > 0 and negative_count > 0
    assert production_result["status"] == "width_two"
    assert production_result["residual_subsets_total"] == len(rows)
    assert production_result["residual_subsets_checked"] < len(rows)
    assert negative_reasons == {"isolated_projection_unrepresented"}
    return {
        "name": "isolated_mixed_residual_choices",
        "class_count": len(classes),
        "long_line_count": len(own_lines),
        "residual_choices": len(rows),
        "quotient_independent_choices": quotient_independent_choices,
        "positive_endpoint_completions": positive_count,
        "negative_endpoint_completions": negative_count,
        "negative_completion_reasons": sorted(negative_reasons),
        "production_status": production_result["status"],
        "production_residual_subsets_total": production_result[
            "residual_subsets_total"
        ],
        "production_residual_subsets_checked": production_result[
            "residual_subsets_checked"
        ],
        "production_early_exit": (
            production_result["residual_subsets_checked"] < len(rows)
        ),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exhaustive",
        action="store_true",
        help="also enumerate every full class basis for q >= 5",
    )
    parser.add_argument(
        "--max-q",
        type=int,
        choices=range(3, 8),
        default=7,
        help="largest q to run (default: 7)",
    )
    args = parser.parse_args()
    rows = [
        audit_family(q, family, exhaustive=args.exhaustive)
        for q in range(3, args.max_q + 1)
        for family in ("moment_negative", "path_positive")
    ]
    output = {
        "status": "measured",
        "endpoint_branch": endpoint_branch_audit(),
        "rows": rows,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())