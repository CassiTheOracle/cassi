"""Independent verifier for the mandatory-class obstruction receipt.

This file deliberately reimplements the exact rational arithmetic, cubic
kernel coordinates, projective classes, rich-line mandatory rule, bounded
basis census, and local-obstruction census.  It imports neither the producer
nor ``cubic_kernel_decision.py``.
"""

from __future__ import annotations

import itertools
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Sequence, cast

RECEIPT = Path("_diag/mandatory_class_obstruction_probe.json")
SCHEMA = "cassifi.mandatory-class-obstruction-probe.v2"
BASIS_ENUM_CAP = 5_000
LOCAL_SUBSET_CAP = 200_000

Vector = tuple[Fraction, ...]

SUPPORT_THREE_SAT = (
    (1, 6, 3), (1, 3, 5), (1, 8, 2), (4, 6, 8), (4, 8, 5),
    (4, 3, 2), (7, 9, 5), (7, 9, 2), (7, 9, 6),
)
SUPPORT_THREE_UNSAT = (
    (1, 14, 11), (2, 1, 15), (3, 10, 5), (4, 8, 14), (5, 11, 7),
    (6, 12, 1), (7, 9, 2), (8, 15, 12), (9, 5, 6), (10, 13, 3),
    (11, 4, 8), (12, 3, 10), (13, 6, 4), (14, 7, 13), (15, 2, 9),
)
ALL_BASES_TERNARY_SAT = (
    (1, 2, 7), (1, 4, 10), (1, 6, 10), (2, 7, 9), (2, 11, 12), (3, 4, 11),
    (3, 6, 7), (3, 8, 12), (4, 9, 10), (5, 6, 11), (5, 8, 9), (5, 8, 12),
)
ALL_BASES_TERNARY_UNSAT = (
    (1, 3, 7), (1, 6, 12), (1, 7, 8), (2, 3, 6), (2, 10, 13), (2, 13, 15),
    (3, 4, 12), (4, 7, 9), (4, 11, 12), (5, 8, 10), (5, 11, 15),
    (5, 13, 14), (6, 9, 14), (8, 11, 14), (9, 10, 15),
)


class VerificationError(ValueError):
    """Raised when a receipt disagrees with the independent reconstruction."""


def fail(message: str) -> None:
    raise VerificationError(message)


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
    return canonical(tuple(rows))


def canonical(formula: Sequence[Sequence[int]]) -> tuple[tuple[int, int, int], ...]:
    size = len(formula)
    if size < 3:
        fail("cubic formula is too small")
    rows: list[tuple[int, int, int]] = []
    occurrences = [0] * size
    for row in formula:
        if len(row) != 3:
            fail("cubic formula has a non-triple row")
        ordered_values = tuple(sorted(int(value) for value in row))
        if (
            len(ordered_values) != 3
            or len(set(ordered_values)) != 3
            or any(value < 1 or value > size for value in ordered_values)
        ):
            fail("cubic formula row is not a valid triple")
        ordered = (
            ordered_values[0],
            ordered_values[1],
            ordered_values[2],
        )
        for value in ordered:
            occurrences[value - 1] += 1
        rows.append(ordered)
    if any(count != 3 for count in occurrences):
        fail("cubic formula is not 3-regular")
    return tuple(sorted(rows))


def geometry_from_vectors(
    vectors: Sequence[Sequence[Fraction | int]],
) -> dict[str, Any]:
    original_vectors = tuple(
        tuple(Fraction(value) for value in vector) for vector in vectors
    )
    class_indices: dict[Vector, int] = {}
    class_vectors: list[Vector] = []
    class_columns: list[list[int]] = []
    column_classes: list[int | None] = []
    for column, vector in enumerate(original_vectors):
        key = projective(vector)
        if key is None:
            column_classes.append(None)
            continue
        class_index = class_indices.get(key)
        if class_index is None:
            class_index = len(class_vectors)
            class_indices[key] = class_index
            class_vectors.append(vector)
            class_columns.append([])
        class_columns[class_index].append(column + 1)
        column_classes.append(class_index)
    class_tuple = tuple(class_vectors)
    return {
        "vectors": original_vectors,
        "class_vectors": class_tuple,
        "class_columns": tuple(tuple(columns) for columns in class_columns),
        "column_classes": tuple(column_classes),
        "lines": line_universe(class_tuple),
    }


def kernel_geometry(formula: Sequence[Sequence[int]]) -> dict[str, Any]:
    size = len(formula)
    matrix = [
        [Fraction(int(variable in clause)) for variable in range(1, size + 1)]
        for clause in formula
    ]
    pivots: list[int] = []
    row = 0
    for column in range(size):
        source = next(
            (index for index in range(row, size) if matrix[index][column]),
            None,
        )
        if source is None:
            continue
        matrix[row], matrix[source] = matrix[source], matrix[row]
        divisor = matrix[row][column]
        matrix[row] = [value / divisor for value in matrix[row]]
        for index in range(size):
            if index == row or not matrix[index][column]:
                continue
            factor = matrix[index][column]
            matrix[index] = [
                value - factor * pivot
                for value, pivot in zip(matrix[index], matrix[row], strict=True)
            ]
        pivots.append(column)
        row += 1
    free = [column for column in range(size) if column not in pivots]
    basis: list[list[Fraction]] = []
    for free_column in free:
        vector = [Fraction(0)] * size
        vector[free_column] = Fraction(1)
        for pivot_index, pivot_column in enumerate(pivots):
            vector[pivot_column] = -matrix[pivot_index][free_column]
        basis.append(vector)
    columns = tuple(
        tuple(basis[index][element] for index in range(len(free)))
        for element in range(size)
    )
    geometry = geometry_from_vectors(columns)
    geometry["nullity"] = len(free)
    return geometry


def rank(vectors: Sequence[Sequence[Fraction | int]]) -> int:
    matrix = [
        [Fraction(value) for value in vector]
        for vector in vectors
        if any(vector)
    ]
    if not matrix:
        return 0
    width = len(matrix[0])
    current = 0
    for column in range(width):
        source = next(
            (index for index in range(current, len(matrix)) if matrix[index][column]),
            None,
        )
        if source is None:
            continue
        matrix[current], matrix[source] = matrix[source], matrix[current]
        divisor = matrix[current][column]
        matrix[current] = [value / divisor for value in matrix[current]]
        for index in range(len(matrix)):
            if index == current or not matrix[index][column]:
                continue
            factor = matrix[index][column]
            matrix[index] = [
                value - factor * pivot
                for value, pivot in zip(matrix[index], matrix[current], strict=True)
            ]
        current += 1
        if current == len(matrix):
            break
    return current


def line_universe(classes: Sequence[Vector]) -> tuple[tuple[int, ...], ...]:
    lines: set[tuple[int, ...]] = set()
    for left, right in itertools.combinations(range(len(classes)), 2):
        lines.add(
            tuple(
                target
                for target, point in enumerate(classes)
                if rank((classes[left], classes[right], point)) <= 2
            )
        )
    return tuple(sorted(lines))


def mandatory_classes(classes: Sequence[Vector]) -> tuple[int, ...]:
    rich = {
        target
        for line_set in line_universe(classes)
        if len(line_set) >= 3
        for target in line_set
    }
    return tuple(index for index in range(len(classes)) if index not in rich)


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
) -> dict[str, Any]:
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
    if basis_total > BASIS_ENUM_CAP:
        return {
            **common,
            "status": "inconclusive",
            "reason": "basis_enum_cap",
        }

    coverage_masks: list[int] = []
    checked = 0
    independent = 0
    for chosen_columns in itertools.combinations(
        range(column_count), nullity
    ):
        checked += 1
        if (
            rank(tuple(original_vectors[index] for index in chosen_columns))
            != nullity
        ):
            continue
        independent += 1
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
            "basis_subsets_checked": checked,
            "independent_bases": independent,
            "minimum_size": 1 if class_count else None,
            "witness_subset": [1] if class_count else None,
            "subset_sizes_checked": [1] if class_count else [],
        }

    sizes: list[int] = []
    for subset_size in range(1, class_count + 1):
        subset_total = math.comb(class_count, subset_size)
        if subset_total > LOCAL_SUBSET_CAP:
            return {
                **common,
                "status": "inconclusive",
                "reason": "local_subset_cap",
                "basis_subsets_checked": checked,
                "independent_bases": independent,
                "subset_sizes_checked": sizes,
            }
        sizes.append(subset_size)
        for chosen in itertools.combinations(range(class_count), subset_size):
            required = sum(1 << index for index in chosen)
            if not any(mask & required == required for mask in coverage_masks):
                return {
                    **common,
                    "status": "exact",
                    "reason": "minimum_uncoverable_subset",
                    "basis_subsets_checked": checked,
                    "independent_bases": independent,
                    "minimum_size": subset_size,
                    "witness_subset": [index + 1 for index in chosen],
                    "subset_sizes_checked": sizes,
                }
    return {
        **common,
        "status": "exact",
        "reason": "every_class_subset_coverable",
        "basis_subsets_checked": checked,
        "independent_bases": independent,
        "subset_sizes_checked": sizes,
    }


def expected_specs() -> list[tuple[str, str, Any, int, str, int | None, str | None]]:
    specs: list[tuple[str, str, Any, int, str, int | None, str | None]] = [
        ("rational-coordinate-basis", "rational", axes(3), 3, "width_two", None, None),
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
            kernel_geometry(canonical(formula))["nullity"],
            expected,
            None,
            None,
        )
        for name, formula, expected in cubic_specs
    )
    return specs


def rebuild_geometry(kind: str, source: Any) -> dict[str, Any]:
    if kind == "rational":
        return geometry_from_vectors(source)
    return kernel_geometry(canonical(source))


def verify_case(
    case: dict[str, Any],
    spec: tuple[str, str, Any, int, str, int | None, str | None],
) -> None:
    name, kind, source, nullity, expected, q, family = spec
    if case.get("name") != name or case.get("kind") != kind:
        fail(f"case identity mismatch: {name}")
    if case.get("q") != q or case.get("family") != family:
        fail(f"case metadata mismatch: {name}")
    if case.get("expected_status") != expected:
        fail(f"expected status mismatch: {name}")

    geometry = rebuild_geometry(kind, source)
    original_vectors = tuple(geometry["vectors"])
    classes = tuple(geometry["class_vectors"])
    column_classes = tuple(geometry["column_classes"])
    expected_class_columns = [
        list(columns) for columns in geometry["class_columns"]
    ]
    expected_column_classes = [
        None if index is None else index + 1
        for index in column_classes
    ]
    expected_zero_columns = [
        index + 1
        for index, class_index in enumerate(column_classes)
        if class_index is None
    ]
    if case.get("nullity") != nullity:
        fail(f"nullity mismatch: {name}")
    if case.get("original_column_count") != len(original_vectors):
        fail(f"original column count mismatch: {name}")
    if case.get("class_count") != len(classes):
        fail(f"class count mismatch: {name}")
    if case.get("class_columns") != expected_class_columns:
        fail(f"class-column mapping mismatch: {name}")
    if case.get("column_classes") != expected_column_classes:
        fail(f"column-class mapping mismatch: {name}")
    if case.get("zero_column_indices") != expected_zero_columns:
        fail(f"zero-column mapping mismatch: {name}")

    expected_mandatory = mandatory_classes(classes)
    mandatory = case.get("mandatory")
    if not isinstance(mandatory, dict):
        fail(f"mandatory block missing: {name}")
    mandatory = cast(dict[str, Any], mandatory)
    mandatory_rank = rank(
        tuple(classes[index] for index in expected_mandatory)
    )
    expected_mandatory_block = {
        "classes": [index + 1 for index in expected_mandatory],
        "count": len(expected_mandatory),
        "rank": mandatory_rank,
        "rejects": (
            len(expected_mandatory) > nullity
            or mandatory_rank < len(expected_mandatory)
        ),
        "cardinality_witness": (
            [index + 1 for index in expected_mandatory[: nullity + 1]]
            if len(expected_mandatory) > nullity
            else None
        ),
    }
    if mandatory != expected_mandatory_block:
        fail(f"mandatory obstruction mismatch: {name}")

    local = exact_local_obstruction(
        geometry,
        nullity,
        applicable=expected == "no_width_two_basis",
    )
    if case.get("local_obstruction") != local:
        fail(f"local obstruction mismatch: {name}")
    maximum_line_size = max(
        (len(line_set) for line_set in geometry["lines"]),
        default=0,
    )
    if case.get("maximum_line_size") != maximum_line_size:
        fail(f"line geometry mismatch: {name}")

    production_value = case.get("production")
    if not isinstance(production_value, dict):
        fail(f"production summary missing: {name}")
    production = cast(dict[str, Any], production_value)
    if production.get("status") != expected:
        fail(f"production status mismatch: {name}")
    reason = production.get("reason")
    if not isinstance(reason, str) or not reason:
        fail(f"production reason missing: {name}")
    for field in (
        "residual_subsets_total",
        "residual_subsets_checked",
        "endpoint_subsets_checked",
        "independent_basis_candidates",
    ):
        value = production.get(field)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            fail(f"invalid production count {field}: {name}")
    total = production.get("residual_subsets_total")
    checked = production.get("residual_subsets_checked")
    if total is not None and checked is not None and checked > total:
        fail(f"production residual count exceeds total: {name}")

    candidate_value = production.get("candidate_free_columns")
    if expected == "width_two":
        if not isinstance(candidate_value, list):
            fail(f"width-two candidate missing: {name}")
        candidate = cast(list[Any], candidate_value)
        if any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 1 <= value <= len(original_vectors)
            for value in candidate
        ):
            fail(f"invalid width-two candidate columns: {name}")
        if len(candidate) != nullity or len(set(candidate)) != len(candidate):
            fail(f"width-two candidate has wrong cardinality: {name}")
        chosen_columns = tuple(value - 1 for value in candidate)
        if rank(tuple(original_vectors[index] for index in chosen_columns)) != nullity:
            fail(f"width-two candidate is not an original basis: {name}")
        chosen_classes = tuple(
            sorted(
                {
                    class_index
                    for index in chosen_columns
                    for class_index in (column_classes[index],)
                    if class_index is not None
                }
            )
        )
        if pair_coverage_mask(classes, chosen_classes) != (1 << len(classes)) - 1:
            fail(f"width-two candidate misses a projective class: {name}")
    elif candidate_value is not None:
        fail(f"NO case emitted a width-two candidate: {name}")
    if mandatory["rejects"] and production["status"] == "no_width_two_basis":
        if production["reason"] != "mandatory_class_obstruction":
            fail(f"mandatory rejection did not reach production path: {name}")


def verify(path: str | Path = RECEIPT) -> dict[str, Any]:
    receipt = json.loads(Path(path).read_text(encoding="utf-8"))
    if receipt.get("schema") != SCHEMA:
        fail("schema mismatch")
    if receipt.get("status") != "measured":
        fail("receipt status mismatch")
    if receipt.get("caps") != {
        "basis_enum_cap": BASIS_ENUM_CAP,
        "local_subset_cap": LOCAL_SUBSET_CAP,
    }:
        fail("cap contract mismatch")
    cases = receipt.get("cases")
    if not isinstance(cases, list):
        fail("cases missing")
    specs = expected_specs()
    if len(cases) != len(specs):
        fail("case count mismatch")
    for case, spec in zip(cases, specs, strict=True):
        if not isinstance(case, dict):
            fail("case is not an object")
        verify_case(case, spec)
    local_statuses: dict[str, int] = {}
    production_statuses: dict[str, int] = {}
    for case in cases:
        local_status = case["local_obstruction"]["status"]
        local_statuses[local_status] = local_statuses.get(local_status, 0) + 1
        production_status = case["production"]["status"]
        production_statuses[production_status] = production_statuses.get(production_status, 0) + 1
    expected_summary = {
        "cases": len(cases),
        "kinds": {
            kind: sum(case["kind"] == kind for case in cases)
            for kind in sorted({case["kind"] for case in cases})
        },
        "local_statuses": dict(sorted(local_statuses.items())),
        "mandatory_rejections": sum(
            case["mandatory"]["rejects"] for case in cases
        ),
        "production_statuses": dict(sorted(production_statuses.items())),
        "maximum_nullity": max(case["nullity"] for case in cases),
        "maximum_class_count": max(case["class_count"] for case in cases),
        "maximum_original_column_count": max(
            case["original_column_count"] for case in cases
        ),
    }
    if receipt.get("summary") != expected_summary:
        fail("summary mismatch")
    return {
        "schema": SCHEMA,
        "status": "verified",
        "verified_cases": len(cases),
        "local_statuses": expected_summary["local_statuses"],
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
