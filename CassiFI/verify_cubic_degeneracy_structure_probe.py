"""Independently verify the cubic degeneracy-structure probe receipt.

This verifier imports neither the audited runner nor its production decision
implementation.  It reuses only the already-independent cubic-lift verifier for
population reconstruction and exact rational basis arithmetic, then separately
reimplements every degeneracy classification and canonical-family calculation.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, NoReturn, Sequence, cast

import verify_cubic_lift_realization_probe as lift_verifier

SCHEMA = "cassifi.cubic-degeneracy-structure-probe.v1"
DEFAULT_RECEIPT = Path("_diag/cubic_degeneracy_structure_probe.json")
POSITIVE_VECTORS = (
    (0, 0, 1),
    (0, 1, -1),
    (0, 1, 0),
    (1, -1, -1),
    (1, -1, 0),
    (1, 0, -1),
)
POSITIVE_PORTS = (1, 6)
NEGATIVE_VECTORS = (
    (1, 0),
    (0, 1),
    (1, 1),
    (1, -1),
)
NEGATIVE_PORTS = (1, 2)

Formula = tuple[tuple[int, int, int], ...]
Basis = tuple[int, ...]
Family = tuple[Basis, ...]
Vector = tuple[Fraction, ...]


class VerificationError(ValueError):
    """Raised when a structure receipt disagrees with reconstruction."""


def fail(message: str) -> NoReturn:
    raise VerificationError(message)


def json_digest(value: Any) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode(
        "ascii"
    )
    return hashlib.sha256(payload).hexdigest()


def matrix_rank(rows: Sequence[Sequence[Fraction]]) -> int:
    if not rows:
        return 0
    matrix = [list(row) for row in rows]
    row_count = len(matrix)
    column_count = len(matrix[0])
    pivot_row = 0
    for column in range(column_count):
        pivot = next(
            (row for row in range(pivot_row, row_count) if matrix[row][column]),
            None,
        )
        if pivot is None:
            continue
        matrix[pivot_row], matrix[pivot] = matrix[pivot], matrix[pivot_row]
        scale = matrix[pivot_row][column]
        matrix[pivot_row] = [entry / scale for entry in matrix[pivot_row]]
        for row in range(row_count):
            if row == pivot_row or not matrix[row][column]:
                continue
            factor = matrix[row][column]
            matrix[row] = [
                left - factor * right
                for left, right in zip(
                    matrix[row], matrix[pivot_row], strict=True
                )
            ]
        pivot_row += 1
        if pivot_row == row_count:
            break
    return pivot_row


def nullspace_rows(rows: Sequence[Sequence[Fraction]]) -> list[list[Fraction]]:
    matrix = [list(row) for row in rows]
    row_count = len(matrix)
    column_count = len(matrix[0])
    pivots: list[int] = []
    pivot_row = 0
    for column in range(column_count):
        pivot = next(
            (row for row in range(pivot_row, row_count) if matrix[row][column]),
            None,
        )
        if pivot is None:
            continue
        matrix[pivot_row], matrix[pivot] = matrix[pivot], matrix[pivot_row]
        scale = matrix[pivot_row][column]
        matrix[pivot_row] = [entry / scale for entry in matrix[pivot_row]]
        for row in range(row_count):
            if row == pivot_row or not matrix[row][column]:
                continue
            factor = matrix[row][column]
            matrix[row] = [
                left - factor * right
                for left, right in zip(
                    matrix[row], matrix[pivot_row], strict=True
                )
            ]
        pivots.append(column)
        pivot_row += 1
        if pivot_row == row_count:
            break
    free_columns = [
        column for column in range(column_count) if column not in pivots
    ]
    basis: list[list[Fraction]] = []
    for free in free_columns:
        vector = [Fraction(0) for _ in range(column_count)]
        vector[free] = Fraction(1)
        for row, pivot in enumerate(pivots):
            vector[pivot] = -matrix[row][free]
        basis.append(vector)
    return basis


def incidence_columns(formula: Formula) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(index for index, clause in enumerate(formula) if variable in clause)
        for variable in range(1, len(formula) + 1)
    )


def projective_key(vector: Vector) -> tuple[str, ...]:
    pivot = next((entry for entry in vector if entry), None)
    if pivot is None:
        return ("zero",)
    return tuple(str(entry / pivot) for entry in vector)


def class_sizes(values: Iterable[Any]) -> list[int]:
    return sorted(Counter(values).values(), reverse=True)


def canonical_basis_family(family: Family, order: int) -> Family:
    degrees = Counter(vertex for basis in family for vertex in basis)
    groups = [
        tuple(vertex for vertex in range(1, order + 1) if degrees[vertex] == degree)
        for degree in sorted(set(degrees.values()))
    ]
    best: Family | None = None
    for group_permutations in itertools.product(
        *(itertools.permutations(group) for group in groups)
    ):
        vertex_order = tuple(
            vertex for group in group_permutations for vertex in group
        )
        relabel = {
            vertex: new_label
            for new_label, vertex in enumerate(vertex_order, start=1)
        }
        candidate = tuple(
            sorted(
                tuple(sorted(relabel[vertex] for vertex in basis))
                for basis in family
            )
        )
        if best is None or candidate < best:
            best = candidate
    if best is None:
        fail("canonicalization generated no candidate")
    return best


def analyze_target(
    target: dict[str, Any],
    canonical_cache: dict[tuple[int, Family], tuple[str, Family]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    formula = cast(
        Formula,
        tuple(
            tuple(int(variable) for variable in clause)
            for clause in target["formula"]
        ),
    )
    order = len(formula)
    basis_receipt, vectors, basis_rows = lift_verifier.basis_profile(formula)
    exact_rank = int(basis_receipt["rank"])
    nullity = int(basis_receipt["nullity"])
    if exact_rank != target["rank"] or nullity != target["nullity"]:
        fail("source target rank mismatch")

    width_histogram = Counter(width for _, width in basis_rows)
    width_two_family: Family = tuple(
        basis for basis, width in basis_rows if width <= 2
    )
    cache_key = (order, width_two_family)

    if cache_key not in canonical_cache:
        canonical = canonical_basis_family(width_two_family, order)
        canonical_cache[cache_key] = (json_digest(canonical), canonical)
    canonical_digest, _ = canonical_cache[cache_key]

    primal_columns = incidence_columns(formula)
    primal_twins: set[tuple[int, int]] = set()
    dual_parallel: set[tuple[int, int]] = set()
    exclusive: set[tuple[int, int]] = set()
    exclusive_rows: list[dict[str, Any]] = []
    degenerate_nonexclusive = 0
    state_histogram: Counter[str] = Counter()

    for left, right in itertools.combinations(range(order), 2):
        ports = (left + 1, right + 1)
        pair_rank = lift_verifier.vector_rank((vectors[left], vectors[right]))
        is_dual_parallel = pair_rank < 2
        is_primal_twin = primal_columns[left] == primal_columns[right]
        if is_dual_parallel:
            dual_parallel.add(ports)
        if is_primal_twin:
            primal_twins.add(ports)
        states = {
            f"{int(ports[0] in basis)}{int(ports[1] in basis)}"
            for basis in width_two_family
        }
        state_histogram["".join(sorted(states))] += 1
        is_exclusive = states == {"01", "10"}
        if is_exclusive:
            exclusive.add(ports)
            category = (
                "dual_parallel"
                if is_dual_parallel
                else "primal_twins"
                if is_primal_twin
                else "eligible"
            )
            exclusive_rows.append(
                {
                    "ports": list(ports),
                    "category": category,
                    "dual_pair_rank": pair_rank,
                    "primal_incidence_identical": is_primal_twin,
                }
            )
        elif is_dual_parallel or is_primal_twin:
            degenerate_nonexclusive += 1

    violations = sorted(
        pair
        for pair in exclusive
        if pair not in dual_parallel and pair not in primal_twins
    )
    mode = "primal_twins" if primal_twins else "dual_parallel"
    expected_exclusive = primal_twins if primal_twins else dual_parallel
    profile = {
        "order": order,
        "rank": exact_rank,
        "nullity": nullity,
        "ordinary_basis_width_histogram": {
            str(width): count for width, count in sorted(width_histogram.items())
        },
        "width_two_basis_count": len(width_two_family),
        "dual_projective_class_sizes": class_sizes(
            projective_key(vector) for vector in vectors
        ),
        "primal_incidence_class_sizes": class_sizes(primal_columns),
    }
    row = {
        "formula_sha256": str(target["formula_sha256"]),
        "order": order,
        "rank": exact_rank,
        "nullity": nullity,
        "source_ground_basis_stream_sha256": target["basis_census"][
            "ground_basis_stream_sha256"
        ],
        "source_width_two_basis_stream_sha256": target["basis_census"][
            "width_two_basis_stream_sha256"
        ],
        "canonical_width_two_family_sha256": canonical_digest,
        "structural_profile_sha256": json_digest(profile),
        "primal_twin_pair_count": len(primal_twins),
        "dual_parallel_pair_count": len(dual_parallel),
        "exclusive_pair_count": len(exclusive),
        "exclusive_pairs": exclusive_rows,
        "degenerate_nonexclusive_pair_count": degenerate_nonexclusive,
        "width_two_state_pattern_histogram": dict(sorted(state_histogram.items())),
        "finite_mode": mode,
        "finite_mode_rule_match": exclusive == expected_exclusive,
        "degeneracy_implication_violation_count": len(violations),
    }
    return row, profile


def independent_basis_rows(
    vectors: tuple[Vector, ...], dimension: int
) -> list[tuple[Basis, int]]:
    rows: list[tuple[Basis, int]] = []
    for selected in itertools.combinations(range(len(vectors)), dimension):
        basis_vectors = tuple(vectors[index] for index in selected)
        if lift_verifier.vector_rank(basis_vectors) != dimension:
            continue
        maximum_support = max(
            sum(
                coordinate != 0
                for coordinate in lift_verifier.basis_coordinates(
                    basis_vectors, vector
                )
            )
            for vector in vectors
        )
        rows.append((tuple(index + 1 for index in selected), maximum_support))
    return rows


def synthetic_profile(
    raw_vectors: Sequence[Sequence[int]], ports: tuple[int, int]
) -> dict[str, Any]:
    vectors: tuple[Vector, ...] = tuple(
        tuple(Fraction(value) for value in vector) for vector in raw_vectors
    )
    dimension = len(vectors[0])
    basis_rows = independent_basis_rows(vectors, dimension)
    width_two = tuple(basis for basis, width in basis_rows if width <= 2)
    states = {
        f"{int(ports[0] in basis)}{int(ports[1] in basis)}"
        for basis in width_two
    }
    coordinate_rows = [
        [vector[coordinate] for vector in vectors]
        for coordinate in range(dimension)
    ]
    primal_rows = nullspace_rows(coordinate_rows)
    indices = (ports[0] - 1, ports[1] - 1)
    primal_columns = tuple(
        tuple(row[index] for row in primal_rows) for index in indices
    )
    return {
        "vectors": [list(vector) for vector in raw_vectors],
        "ports": list(ports),
        "dual_pair_rank": lift_verifier.vector_rank(
            (vectors[indices[0]], vectors[indices[1]])
        ),
        "primal_pair_rank": matrix_rank(primal_columns),
        "primal_columns_identical": primal_columns[0] == primal_columns[1],
        "ordinary_basis_count": len(basis_rows),
        "width_two_basis_count": len(width_two),
        "width_two_states": sorted(states),
        "exclusive_width_two": states == {"01", "10"},
    }


def synthetic_controls() -> dict[str, Any]:
    positive = synthetic_profile(POSITIVE_VECTORS, POSITIVE_PORTS)
    negative = synthetic_profile(NEGATIVE_VECTORS, NEGATIVE_PORTS)
    positive["generalized_implication_violation"] = (
        positive["exclusive_width_two"]
        and positive["dual_pair_rank"] == 2
        and positive["primal_pair_rank"] == 2
    )
    negative["generalized_implication_violation"] = (
        negative["exclusive_width_two"]
        and negative["dual_pair_rank"] == 2
        and negative["primal_pair_rank"] == 2
    )
    if not positive["generalized_implication_violation"]:
        fail("positive generalized implication control did not fire")
    if negative["exclusive_width_two"]:
        fail("negative generalized implication control fired")
    return {
        "positive_noncubic_general_vector_configuration": positive,
        "negative_noncubic_general_vector_configuration": negative,
        "scope": (
            "Exact rational vector controls with orthogonal primal "
            "representations; neither is claimed to be a cubic incidence kernel."
        ),
    }


def source_cover(source: dict[str, Any]) -> list[dict[str, Any]]:
    fields = (
        "order",
        "cycle_type_count",
        "legal_factorizations",
        "distinct_clause_factorizations",
        "duplicate_row_sorted_factorizations",
        "unique_row_sorted_formulas",
        "formula_stream_sha256",
        "modular_target_candidates",
        "exact_nullity_at_least_three_formulas",
        "connected_target_formulas",
        "disconnected_target_formulas",
        "modular_false_positives",
    )
    return [{field: order[field] for field in fields} for order in source["orders"]]


def expected_receipt(maximum_order: int) -> dict[str, Any]:
    source = lift_verifier.expected_receipt(maximum_order)
    targets = [
        target
        for order in source["orders"]
        for target in order["targets"]
        if target["status"] == "analyzed"
    ]
    canonical_cache: dict[tuple[int, Family], tuple[str, Family]] = {}
    target_rows: list[dict[str, Any]] = []
    profiles: dict[str, dict[str, Any]] = {}
    class_counts: Counter[str] = Counter()
    class_outcomes: dict[str, Counter[str]] = defaultdict(Counter)

    for target in targets:
        row, profile = analyze_target(target, canonical_cache)
        target_rows.append(row)
        class_digest = row["canonical_width_two_family_sha256"]
        profile_digest = row["structural_profile_sha256"]
        profiles.setdefault(profile_digest, profile)
        class_counts[class_digest] += 1
        class_outcomes[class_digest][row["finite_mode"]] += 1
        class_outcomes[class_digest][
            f"exclusive_pairs:{row['exclusive_pair_count']}"
        ] += 1

    target_rows.sort(key=lambda row: (row["order"], row["formula_sha256"]))
    families = {digest: family for digest, family in canonical_cache.values()}
    classes = []
    for class_digest, count in sorted(class_counts.items()):
        members = [
            row
            for row in target_rows
            if row["canonical_width_two_family_sha256"] == class_digest
        ]
        classes.append(
            {
                "canonical_width_two_family_sha256": class_digest,
                "canonical_width_two_family": [
                    list(basis) for basis in families[class_digest]
                ],
                "formula_count": count,
                "structural_profile_sha256": sorted(
                    {row["structural_profile_sha256"] for row in members}
                ),
                "finite_outcome_histogram": dict(
                    sorted(class_outcomes[class_digest].items())
                ),
            }
        )

    categories = Counter(
        pair["category"]
        for row in target_rows
        for pair in row["exclusive_pairs"]
    )
    summary = {
        "maximum_order": maximum_order,
        "source_unique_row_sorted_formulas": source["summary"][
            "unique_row_sorted_formulas"
        ],
        "target_formulas": len(target_rows),
        "target_orders": sorted({row["order"] for row in target_rows}),
        "pair_cases": sum(math.comb(row["order"], 2) for row in target_rows),
        "exclusive_pairs": sum(row["exclusive_pair_count"] for row in target_rows),
        "exclusive_category_histogram": dict(sorted(categories.items())),
        "degeneracy_implication_violations": sum(
            row["degeneracy_implication_violation_count"] for row in target_rows
        ),
        "finite_mode_rule_mismatches": sum(
            not row["finite_mode_rule_match"] for row in target_rows
        ),
        "degenerate_nonexclusive_pairs": sum(
            row["degenerate_nonexclusive_pair_count"] for row in target_rows
        ),
        "labeled_width_two_families": len(canonical_cache),
        "canonical_width_two_families": len(class_counts),
        "structural_profiles": len(profiles),
    }
    controls = synthetic_controls()
    summary["exclusive_nondegenerate_pairs"] = categories.get("eligible", 0)
    summary["exclusive_degenerate_pairs"] = (
        categories.get("dual_parallel", 0)
        + categories.get("primal_twins", 0)
    )
    if (
        summary["exclusive_nondegenerate_pairs"]
        != summary["degeneracy_implication_violations"]
    ):
        fail("eligible category disagrees with implication violations")
    if (
        summary["exclusive_degenerate_pairs"]
        + summary["exclusive_nondegenerate_pairs"]
        != summary["exclusive_pairs"]
    ):
        fail("exclusive category partition is incomplete")
    summary["noncubic_control_violation_fired"] = controls[
        "positive_noncubic_general_vector_configuration"
    ]["generalized_implication_violation"]
    return {
        "schema": SCHEMA,
        "parameters": {
            "minimum_order": lift_verifier.MINIMUM_ORDER,
            "maximum_order": maximum_order,
            "target_minimum_nullity": lift_verifier.TARGET_NULLITY,
            "width_bound": 2,
        },
        "definitions": {
            "exclusive_width_two_pair": (
                "Across all exact width-two ground bases, the two ports occur "
                "in precisely states 01 and 10."
            ),
            "dual_parallel": (
                "The two columns of the exact rational kernel representation "
                "have rank below two."
            ),
            "primal_incidence_twins": (
                "The two columns of the cubic clause-incidence matrix are identical."
            ),
            "finite_mode_rule": (
                "For each measured target, exclusive pairs equal all primal "
                "incidence-twin pairs when any twins exist, and otherwise equal "
                "all dual-parallel pairs."
            ),
        },
        "source": {
            "schema": source["schema"],
            "receipt_sha256": json_digest(source),
            "formula_cover": source_cover(source),
            "summary": source["summary"],
        },
        "synthetic_controls": controls,
        "structural_profiles": [
            {"sha256": digest, **profile}
            for digest, profile in sorted(profiles.items())
        ],
        "structural_classes": classes,
        "targets": target_rows,
        "target_stream_sha256": json_digest(target_rows),
        "summary": summary,
        "assessment": {
            "measured_implication": (
                "Every exclusive pair in the complete measured cubic target "
                "census is dual-parallel or has identical primal incidence."
            ),
            "converse": (
                "False in the measured census: degeneracy is not sufficient "
                "for exclusivity."
            ),
            "scope": (
                f"Symmetry-complete simple connected cubic formulas through "
                f"order {maximum_order}; the synthetic noncubic positive control "
                "shows the implication is not a general vector-matroid identity."
            ),
        },
    }


def first_difference(expected: Any, observed: Any, path: str = "$") -> str | None:
    if type(expected) is not type(observed):
        return f"{path}: type {type(observed).__name__}, expected {type(expected).__name__}"
    if isinstance(expected, dict):
        if expected.keys() != observed.keys():
            missing = sorted(set(expected) - set(observed))
            extra = sorted(set(observed) - set(expected))
            return f"{path}: key mismatch missing={missing} extra={extra}"
        for key in expected:
            difference = first_difference(expected[key], observed[key], f"{path}.{key}")
            if difference:
                return difference
        return None
    if isinstance(expected, list):
        if len(expected) != len(observed):
            return f"{path}: length {len(observed)}, expected {len(expected)}"
        for index, (left, right) in enumerate(zip(expected, observed, strict=True)):
            difference = first_difference(left, right, f"{path}[{index}]")
            if difference:
                return difference
        return None
    if expected != observed:
        return f"{path}: observed {observed!r}, expected {expected!r}"
    return None


def verify(receipt: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("schema") != SCHEMA:
        fail("schema mismatch")
    parameters = receipt.get("parameters")
    if not isinstance(parameters, dict):
        fail("parameters object is missing")
    maximum_order = parameters.get("maximum_order")
    if not isinstance(maximum_order, int):
        fail("maximum_order is not an integer")
    expected = expected_receipt(maximum_order)
    difference = first_difference(expected, receipt)
    if difference:
        fail(difference)
    return expected["summary"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    try:
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        summary = verify(receipt)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"verification failed: cannot read receipt: {exc}") from exc
    except VerificationError as exc:
        raise SystemExit(f"verification failed: {exc}") from exc
    print(json.dumps(summary, sort_keys=True))
    print("independent verification passed")


if __name__ == "__main__":
    main()
