"""Classify exclusive width-two pairs in the complete cubic lift target census.

The source population is the symmetry-complete simple connected cubic cover produced
by ``run_cubic_lift_realization_probe`` through the requested maximum order.  This
probe asks whether every exclusive width-two port pair is forced by one of two
visible degeneracies: parallel columns in the exact dual kernel representation,
or identical columns in the primal clause-incidence matrix.  It also records the
stronger finite-census mode rule and canonical width-two basis-family classes.
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
from typing import Any, Iterable, Sequence

import run_cubic_exclusive_width_barrier_probe as barrier
import run_cubic_lift_realization_probe as lift

SCHEMA = "cassifi.cubic-degeneracy-structure-probe.v1"
DEFAULT_MAXIMUM_ORDER = lift.DEFAULT_MAXIMUM_ORDER
OUTPUT = Path("_diag/cubic_degeneracy_structure_probe.json")

Basis = tuple[int, ...]
Family = tuple[Basis, ...]
Vector = tuple[Fraction, ...]


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")


def _digest(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _matrix_rank(rows: Sequence[Sequence[Fraction]]) -> int:
    if not rows:
        return 0
    values = [list(row) for row in rows]
    row_count = len(values)
    column_count = len(values[0])
    pivot_row = 0
    for column in range(column_count):
        pivot = next(
            (row for row in range(pivot_row, row_count) if values[row][column]),
            None,
        )
        if pivot is None:
            continue
        values[pivot_row], values[pivot] = values[pivot], values[pivot_row]
        scale = values[pivot_row][column]
        values[pivot_row] = [value / scale for value in values[pivot_row]]
        for row in range(row_count):
            if row == pivot_row or not values[row][column]:
                continue
            factor = values[row][column]
            values[row] = [
                left - factor * right
                for left, right in zip(
                    values[row], values[pivot_row], strict=True
                )
            ]
        pivot_row += 1
        if pivot_row == row_count:
            break
    return pivot_row


def _nullspace_rows(rows: Sequence[Sequence[Fraction]]) -> list[list[Fraction]]:
    if not rows:
        return []
    values = [list(row) for row in rows]
    row_count = len(values)
    column_count = len(values[0])
    pivots: list[int] = []
    pivot_row = 0
    for column in range(column_count):
        pivot = next(
            (row for row in range(pivot_row, row_count) if values[row][column]),
            None,
        )
        if pivot is None:
            continue
        values[pivot_row], values[pivot] = values[pivot], values[pivot_row]
        scale = values[pivot_row][column]
        values[pivot_row] = [value / scale for value in values[pivot_row]]
        for row in range(row_count):
            if row == pivot_row or not values[row][column]:
                continue
            factor = values[row][column]
            values[row] = [
                left - factor * right
                for left, right in zip(
                    values[row], values[pivot_row], strict=True
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
            vector[pivot] = -values[row][free]
        basis.append(vector)
    return basis


def _incidence_columns(formula: lift.Formula) -> tuple[tuple[int, ...], ...]:
    order = len(formula)
    return tuple(
        tuple(index for index, clause in enumerate(formula) if variable in clause)
        for variable in range(1, order + 1)
    )


def _projective_key(vector: Vector) -> tuple[str, ...]:
    pivot = next((value for value in vector if value), None)
    if pivot is None:
        return ("zero",)
    return tuple(str(value / pivot) for value in vector)


def _class_sizes(values: Iterable[Any]) -> list[int]:
    return sorted(Counter(values).values(), reverse=True)


def _canonical_basis_family(family: Family, order: int) -> Family:
    """Canonicalize a basis hypergraph under all degree-preserving relabelings."""

    # Precompute degrees
    degrees = Counter(vertex for basis in family for vertex in basis)

    # Group vertices by degree
    degree_groups = [
        tuple(vertex for vertex in range(1, order + 1) if degrees[vertex] == degree)
        for degree in sorted(set(degrees.values()))
    ]

    # If no degree groups, return empty family
    if not degree_groups:
        return ()

    # Precompute start labels for each group
    start_labels = []
    current_label = 1
    for group in degree_groups:
        start_labels.append(current_label)
        current_label += len(group)

    # Convert family to list of lists for mutability/efficiency
    # Also, we need to sort each basis initially? No, we sort after relabeling.
    # But we can pre-sort the basis vertices to help with something? No.

    # Precompute the basis as list of lists of vertex indices
    basis_list = [list(basis) for basis in family]

    # Precompute the number of bases
    num_bases = len(basis_list)

    # If there are no permutations (e.g., all groups size 1), just compute once
    # But we still need to find the canonical form.

    # We will iterate over all permutations of degree groups
    # To speed up, we can use itertools.product

    # Precompute permutations for each group
    group_perms = [list(itertools.permutations(group)) for group in degree_groups]

    # If any group has size 1, its permutation is just the original tuple
    # This doesn't change much, but itertools.permutations handles it.

    best: Family | None = None

    # Iterate over all combinations of permutations
    for perm_combo in itertools.product(*group_perms):
        # Build relabel map as a list for fast access
        # relabel[v] = new_label
        # We can use a list of size order+1
        relabel = [0] * (order + 1)

        # Fill relabel map
        for group_idx, group_perm in enumerate(perm_combo):
            start = start_labels[group_idx]
            for i, vertex in enumerate(group_perm):
                relabel[vertex] = start + i

        # Generate candidate
        # For each basis, map vertices to labels, sort, and create tuple
        candidate_bases = []
        for basis in basis_list:
            # Map vertices to labels
            mapped = [relabel[v] for v in basis]
            # Sort the mapped vertices
            mapped.sort()
            candidate_bases.append(tuple(mapped))

        # Sort the list of bases
        candidate_bases.sort()
        candidate = tuple(candidate_bases)

        # Update best
        if best is None or candidate < best:
            best = candidate

    if best is None:
        raise AssertionError("basis family canonicalization had no permutation")

    return best


def _basis_rows(
    vectors: tuple[Vector, ...],
    rank: int,
) -> list[tuple[Basis, int]]:
    rows: list[tuple[Basis, int]] = []
    for selected in itertools.combinations(range(len(vectors)), rank):
        selected_vectors = tuple(vectors[index] for index in selected)
        if lift.production._vector_rank(selected_vectors) != rank:
            continue
        maximum_support = max(
            sum(
                coordinate != 0
                for coordinate in lift.production._basis_coordinates(
                    selected_vectors,
                    vector,
                )
            )
            for vector in vectors
        )
        basis = tuple(index + 1 for index in selected)
        rows.append((basis, maximum_support))
    return rows


def _analyze_target(
    target: dict[str, Any],
    canonical_cache: dict[tuple[int, Family], tuple[str, Family]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    formula: lift.Formula = tuple(
        tuple(int(variable) for variable in clause) for clause in target["formula"]
    )
    order = len(formula)
    system = lift.production._system(formula)
    vectors = lift.production._kernel_coordinate_vectors(system, order)
    nullity = len(system["free_columns_zero_based"])
    exact_rank = order - nullity
    if exact_rank != target["rank"] or nullity != target["nullity"]:
        raise AssertionError("source target rank disagrees with exact reconstruction")
    basis_rows = _basis_rows(vectors, nullity)
    width_histogram = Counter(width for _, width in basis_rows)
    width_two_family: Family = tuple(
        basis for basis, width in basis_rows if width <= 2
    )
    cache_key = (order, width_two_family)
    if cache_key not in canonical_cache:
        canonical = _canonical_basis_family(width_two_family, order)
        canonical_cache[cache_key] = (_digest(canonical), canonical)
    canonical_digest, _ = canonical_cache[cache_key]

    primal_columns = _incidence_columns(formula)
    primal_twin_pairs: set[tuple[int, int]] = set()
    dual_parallel_pairs: set[tuple[int, int]] = set()
    exclusive_pairs: set[tuple[int, int]] = set()
    exclusive_rows: list[dict[str, Any]] = []
    degenerate_nonexclusive = 0
    state_pattern_histogram: Counter[str] = Counter()

    for left, right in itertools.combinations(range(order), 2):
        pair = (left + 1, right + 1)
        dual_parallel = _matrix_rank((vectors[left], vectors[right])) < 2
        primal_twins = primal_columns[left] == primal_columns[right]
        if dual_parallel:
            dual_parallel_pairs.add(pair)
        if primal_twins:
            primal_twin_pairs.add(pair)
        states = {
            f"{int(pair[0] in basis)}{int(pair[1] in basis)}"
            for basis in width_two_family
        }
        state_pattern_histogram["".join(sorted(states))] += 1
        exclusive = states == {"01", "10"}
        if exclusive:
            exclusive_pairs.add(pair)
            category = (
                "dual_parallel"
                if dual_parallel
                else "primal_twins"
                if primal_twins
                else "eligible"
            )
            exclusive_rows.append(
                {
                    "ports": list(pair),
                    "category": category,
                    "dual_pair_rank": _matrix_rank(
                        (vectors[left], vectors[right])
                    ),
                    "primal_incidence_identical": primal_twins,
                }
            )
        elif dual_parallel or primal_twins:
            degenerate_nonexclusive += 1

    implication_violations = sorted(
        pair
        for pair in exclusive_pairs
        if pair not in dual_parallel_pairs and pair not in primal_twin_pairs
    )
    mode = "primal_twins" if primal_twin_pairs else "dual_parallel"
    expected_exclusive = primal_twin_pairs if primal_twin_pairs else dual_parallel_pairs
    mode_rule_match = exclusive_pairs == expected_exclusive

    structural_profile = {
        "order": order,
        "rank": exact_rank,
        "nullity": nullity,
        "ordinary_basis_width_histogram": {
            str(width): count for width, count in sorted(width_histogram.items())
        },
        "width_two_basis_count": len(width_two_family),
        "dual_projective_class_sizes": _class_sizes(
            _projective_key(vector) for vector in vectors
        ),
        "primal_incidence_class_sizes": _class_sizes(primal_columns),
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
        "structural_profile_sha256": _digest(structural_profile),
        "primal_twin_pair_count": len(primal_twin_pairs),
        "dual_parallel_pair_count": len(dual_parallel_pairs),
        "exclusive_pair_count": len(exclusive_pairs),
        "exclusive_pairs": exclusive_rows,
        "degenerate_nonexclusive_pair_count": degenerate_nonexclusive,
        "width_two_state_pattern_histogram": dict(
            sorted(state_pattern_histogram.items())
        ),
        "finite_mode": mode,
        "finite_mode_rule_match": mode_rule_match,
        "degeneracy_implication_violation_count": len(implication_violations),
    }
    return row, structural_profile


def _synthetic_profile(
    raw_vectors: Sequence[Sequence[int]], ports: tuple[int, int]
) -> dict[str, Any]:
    vectors: tuple[Vector, ...] = tuple(
        tuple(Fraction(value) for value in vector) for vector in raw_vectors
    )
    dimension = len(vectors[0])
    basis_rows = _basis_rows(vectors, dimension)
    width_two_family = tuple(basis for basis, width in basis_rows if width <= 2)
    states = {
        f"{int(ports[0] in basis)}{int(ports[1] in basis)}"
        for basis in width_two_family
    }
    coordinate_rows = [
        [vector[coordinate] for vector in vectors]
        for coordinate in range(dimension)
    ]
    primal_rows = _nullspace_rows(coordinate_rows)
    port_indices = (ports[0] - 1, ports[1] - 1)
    primal_columns = tuple(
        tuple(row[index] for row in primal_rows) for index in port_indices
    )
    return {
        "vectors": [list(vector) for vector in raw_vectors],
        "ports": list(ports),
        "dual_pair_rank": _matrix_rank(
            (vectors[port_indices[0]], vectors[port_indices[1]])
        ),
        "primal_pair_rank": _matrix_rank(primal_columns),
        "primal_columns_identical": primal_columns[0] == primal_columns[1],
        "ordinary_basis_count": len(basis_rows),
        "width_two_basis_count": len(width_two_family),
        "width_two_states": sorted(states),
        "exclusive_width_two": states == {"01", "10"},
    }


def _synthetic_controls() -> dict[str, Any]:
    positive = _synthetic_profile(
        barrier.SYNTHETIC_BARRIER_VECTORS,
        barrier.SYNTHETIC_BARRIER_PORTS,
    )
    negative = _synthetic_profile(
        barrier.SYNTHETIC_NO_BARRIER_VECTORS,
        barrier.SYNTHETIC_NO_BARRIER_PORTS,
    )
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
        raise AssertionError("synthetic positive implication control did not fire")
    if negative["exclusive_width_two"]:
        raise AssertionError("synthetic negative control became exclusive")
    return {
        "positive_noncubic_general_vector_configuration": positive,
        "negative_noncubic_general_vector_configuration": negative,
        "scope": (
            "Exact rational vector controls with orthogonal primal "
            "representations; neither is claimed to be a cubic incidence kernel."
        ),
    }


def _source_cover(source: dict[str, Any]) -> list[dict[str, Any]]:
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


def build_receipt(maximum_order: int = DEFAULT_MAXIMUM_ORDER) -> dict[str, Any]:
    source = lift.build_receipt(maximum_order)
    targets = [
        target
        for order in source["orders"]
        for target in order["targets"]
        if target["status"] == "analyzed"
    ]
    canonical_cache: dict[tuple[int, Family], tuple[str, Family]] = {}
    target_rows: list[dict[str, Any]] = []
    profiles_by_digest: dict[str, dict[str, Any]] = {}
    class_counts: Counter[str] = Counter()
    class_outcomes: dict[str, Counter[str]] = defaultdict(Counter)

    for target in targets:
        row, profile = _analyze_target(target, canonical_cache)
        target_rows.append(row)
        class_digest = row["canonical_width_two_family_sha256"]
        profile_digest = row["structural_profile_sha256"]
        profiles_by_digest.setdefault(profile_digest, profile)
        class_counts[class_digest] += 1
        class_outcomes[class_digest][row["finite_mode"]] += 1
        class_outcomes[class_digest][
            f"exclusive_pairs:{row['exclusive_pair_count']}"
        ] += 1

    target_rows.sort(key=lambda row: (row["order"], row["formula_sha256"]))
    canonical_family_by_digest = {
        digest: family for digest, family in canonical_cache.values()
    }
    structural_classes = []
    for class_digest, count in sorted(class_counts.items()):
        member_rows = [
            row
            for row in target_rows
            if row["canonical_width_two_family_sha256"] == class_digest
        ]
        profile_digests = sorted(
            {row["structural_profile_sha256"] for row in member_rows}
        )
        structural_classes.append(
            {
                "canonical_width_two_family_sha256": class_digest,
                "canonical_width_two_family": [
                    list(basis) for basis in canonical_family_by_digest[class_digest]
                ],
                "formula_count": count,
                "structural_profile_sha256": profile_digests,
                "finite_outcome_histogram": dict(
                    sorted(class_outcomes[class_digest].items())
                ),
            }
        )

    exclusive_category_histogram = Counter(
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
        "exclusive_category_histogram": dict(
            sorted(exclusive_category_histogram.items())
        ),
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
        "structural_profiles": len(profiles_by_digest),
    }
    controls = _synthetic_controls()
    summary["exclusive_nondegenerate_pairs"] = exclusive_category_histogram.get(
        "eligible", 0
    )
    summary["exclusive_degenerate_pairs"] = (
        exclusive_category_histogram.get("dual_parallel", 0)
        + exclusive_category_histogram.get("primal_twins", 0)
    )
    if (
        summary["exclusive_nondegenerate_pairs"]
        != summary["degeneracy_implication_violations"]
    ):
        raise AssertionError(
            "eligible category disagrees with implication violations"
        )
    if (
        summary["exclusive_degenerate_pairs"]
        + summary["exclusive_nondegenerate_pairs"]
        != summary["exclusive_pairs"]
    ):
        raise AssertionError("exclusive category partition is incomplete")
    summary["noncubic_control_violation_fired"] = controls[
        "positive_noncubic_general_vector_configuration"
    ]["generalized_implication_violation"]
    if summary["degeneracy_implication_violations"]:
        raise AssertionError("cubic target degeneracy implication failed")
    if summary["finite_mode_rule_mismatches"]:
        raise AssertionError("finite cubic target mode rule failed")

    receipt = {
        "schema": SCHEMA,
        "parameters": {
            "minimum_order": lift.MINIMUM_ORDER,
            "maximum_order": maximum_order,
            "target_minimum_nullity": lift.TARGET_NULLITY,
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
            "receipt_sha256": _digest(source),
            "formula_cover": _source_cover(source),
            "summary": source["summary"],
        },
        "synthetic_controls": controls,
        "structural_profiles": [
            {"sha256": digest, **profile}
            for digest, profile in sorted(profiles_by_digest.items())
        ],
        "structural_classes": structural_classes,
        "targets": target_rows,
        "target_stream_sha256": _digest(target_rows),
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
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maximum-order", type=int, default=DEFAULT_MAXIMUM_ORDER)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    receipt = build_receipt(args.maximum_order)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt["summary"], sort_keys=True))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
