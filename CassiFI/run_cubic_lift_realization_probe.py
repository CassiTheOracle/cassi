"""Exhaust a symmetry-complete bounded cover of cubic kernel lifts.

Every square cubic incidence graph decomposes into three perfect matchings.  We
fix the first matching to the identity, put the second into one canonical
representative of each fixed-point-free cycle type, and enumerate the third.
This covers every formula up to row and variable relabeling; it is intentionally
not presented as a labeled or unlabeled graph census because representatives
may repeat an isomorphism class.

For every connected distinct-clause formula in the cover whose exact rational
nullity is at least three, the probe enumerates every original-column kernel
basis, computes its exact coefficient width, and checks every variable pair for
a two-sided width-two barrier.  The default order-nine bound is the first bound
in this cover at which nullity-three formulas occur.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import cubic_kernel_decision as production

OUTPUT = Path("_diag/cubic_lift_realization_probe.json")
SCHEMA = "cassifi.cubic-lift-realization-probe.v1"
MINIMUM_ORDER = 3
MAXIMUM_SUPPORTED_ORDER = 9
DEFAULT_MAXIMUM_ORDER = 9
TARGET_NULLITY = 3
MODULAR_PRIME = 1_000_003
PAIR_NAMESPACE = "one-based original variable-column numbers"

Formula = tuple[tuple[int, int, int], ...]
Vector = tuple[Fraction, ...]
Basis = tuple[int, ...]
Matching = tuple[int, ...]

NULLITY_THREE_CONTROL: Formula = (
    (1, 2, 3),
    (1, 2, 4),
    (1, 2, 5),
    (3, 4, 6),
    (3, 6, 7),
    (4, 8, 9),
    (5, 6, 7),
    (5, 8, 9),
    (7, 8, 9),
)

# Frozen from the independently reconstructed default order-nine run.  A
# non-default bound remains deterministic but is not compared with this anchor.
EXPECTED_CANONICAL_SUMMARY: dict[str, Any] = {
    "connected_target_formulas": 1_402,
    "disconnected_target_formulas": 0,
    "eligible_pairs": 0,
    "exact_nullity_at_least_three_formulas": 1_402,
    "exclusive_pairs": 2_887,
    "first_order_with_nullity_at_least_three": 9,
    "maximum_order": 9,
    "minimum_order": 3,
    "modular_false_positives": 0,
    "modular_target_candidates": 1_402,
    "orders_screened": 7,
    "pair_cases_checked": 50_472,
    "rank_below_two_distinct": 1_920,
    "rank_below_two_identical": 0,
    "rank_two_identical": 967,
    "two_sided_width_barriers": 0,
    "unique_row_sorted_formulas": 204_667,
}


def formula_digest(formula: Sequence[Sequence[int]]) -> str:
    canonical = production.canonical_cubic_formula(formula)
    return hashlib.sha256(
        json.dumps(canonical, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def cycle_partitions(total: int, minimum_part: int = 2) -> Iterator[tuple[int, ...]]:
    """Yield nondecreasing partitions with no fixed-point cycle."""

    if total == 0:
        yield ()
        return
    for part in range(minimum_part, total + 1):
        for suffix in cycle_partitions(total - part, part):
            yield (part, *suffix)


def canonical_cycle_permutation(partition: Sequence[int]) -> Matching:
    """Return the lexicographic disjoint-cycle representative of a cycle type."""

    if not partition or any(part < 2 for part in partition):
        raise ValueError("cycle partition must contain only parts at least two")
    if tuple(partition) != tuple(sorted(partition)):
        raise ValueError("cycle partition must be nondecreasing")
    result: list[int] = []
    offset = 0
    for size in partition:
        result.extend(offset + index + 1 for index in range(size - 1))
        result.append(offset)
        offset += size
    return tuple(result)


def formula_from_factorization(second: Matching, third: Matching) -> Formula:
    """Build identity + second + third as a canonical cubic formula."""

    size = len(second)
    if len(third) != size:
        raise ValueError("matching sizes differ")
    expected = list(range(size))
    if sorted(second) != expected or sorted(third) != expected:
        raise ValueError("factorization rows must be permutations")
    if any(third[row] in (row, second[row]) or second[row] == row for row in range(size)):
        raise ValueError("the three perfect matchings are not edge-disjoint")
    rows = tuple(
        tuple(sorted((row + 1, second[row] + 1, third[row] + 1)))
        for row in range(size)
    )
    return production.canonical_cubic_formula(rows)


def rank_mod_prime(formula: Formula, prime: int = MODULAR_PRIME) -> int:
    """Return incidence rank over F_prime for a sound rational-rank lower bound."""

    size = len(formula)
    matrix = [
        [int(column in clause) for column in range(1, size + 1)]
        for clause in formula
    ]
    pivot_row = 0
    for column in range(size):
        source = next(
            (
                row
                for row in range(pivot_row, size)
                if matrix[row][column] % prime
            ),
            None,
        )
        if source is None:
            continue
        matrix[pivot_row], matrix[source] = matrix[source], matrix[pivot_row]
        inverse = pow(matrix[pivot_row][column], -1, prime)
        for row in range(pivot_row + 1, size):
            if not matrix[row][column] % prime:
                continue
            factor = matrix[row][column] * inverse % prime
            for target in range(column, size):
                matrix[row][target] = (
                    matrix[row][target]
                    - factor * matrix[pivot_row][target]
                ) % prime
        pivot_row += 1
        if pivot_row == size:
            break
    return pivot_row


def _formula_stream_digest(formulas: Iterable[Formula]) -> str:
    stream = hashlib.sha256()
    for formula in formulas:
        stream.update(
            json.dumps(formula, separators=(",", ":")).encode("ascii") + b"\n"
        )
    return stream.hexdigest()

def _json_stream_digest(rows: Iterable[Any]) -> str:
    stream = hashlib.sha256()
    for row in rows:
        stream.update(
            json.dumps(row, separators=(",", ":"), sort_keys=True).encode("ascii")
            + b"\n"
        )
    return stream.hexdigest()


def _column_supports(formula: Formula) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(
            row + 1
            for row, clause in enumerate(formula)
            if column in clause
        )
        for column in range(1, len(formula) + 1)
    )


def _state_signature(basis: Sequence[int], ports: tuple[int, int]) -> str:
    selected = set(basis)
    return f"{int(ports[0] in selected)}{int(ports[1] in selected)}"


def exclusive_category(pair_rank: int, primal_incidence_identical: bool) -> str:
    """Classify an already-exclusive pair by the two escape-lemma defects."""

    if pair_rank == 2 and not primal_incidence_identical:
        return "eligible"
    if pair_rank == 2:
        return "rank_two_identical"
    if primal_incidence_identical:
        return "rank_below_two_identical"
    return "rank_below_two_distinct"


def basis_profile(
    formula: Formula,
) -> tuple[dict[str, Any], tuple[Vector, ...], tuple[tuple[Basis, int], ...]]:
    """Enumerate all ground bases and their exact maximum coefficient support."""

    system = production._system(formula)
    vectors = production._kernel_coordinate_vectors(system, len(formula))
    nullity = len(system["free_columns_zero_based"])
    subset_total = math.comb(len(formula), nullity)
    rows: list[tuple[Basis, int]] = []
    histogram: Counter[int] = Counter()
    width_two: list[list[int]] = []
    for selected in itertools.combinations(range(len(formula)), nullity):
        selected_vectors = tuple(vectors[index] for index in selected)
        if production._vector_rank(selected_vectors) != nullity:
            continue
        maximum_support = max(
            (
                sum(
                    coordinate != 0
                    for coordinate in production._basis_coordinates(
                        selected_vectors,
                        vector,
                    )
                )
                for vector in vectors
            ),
            default=0,
        )
        basis = tuple(index + 1 for index in selected)
        rows.append((basis, maximum_support))
        histogram[maximum_support] += 1
        if maximum_support <= 2:
            width_two.append(list(basis))
    serialized = {
        "rank": len(formula) - nullity,
        "nullity": nullity,
        "basis_subsets_total": subset_total,
        "basis_subsets_checked": subset_total,
        "independent_ground_bases": len(rows),
        "ground_basis_stream_sha256": _json_stream_digest(
            {
                "basis": list(basis),
                "maximum_support": maximum_support,
            }
            for basis, maximum_support in rows
        ),
        "width_two_basis_count": len(width_two),
        "width_two_basis_stream_sha256": _json_stream_digest(width_two),
        "basis_maximum_support_histogram": {
            str(width): histogram[width] for width in sorted(histogram)
        },
        "exact": True,
    }
    return serialized, vectors, tuple(rows)


def pair_profile(
    formula: Formula,
    vectors: tuple[Vector, ...],
    basis_rows: tuple[tuple[Basis, int], ...],
) -> dict[str, Any]:
    """Check all pairs for a directly witnessed two-sided width barrier."""

    size = len(formula)
    width_two = tuple(basis for basis, width in basis_rows if width <= 2)
    signatures: list[int] = []
    for column in range(1, size + 1):
        signature = 0
        for vertex, basis in enumerate(width_two):
            if column in basis:
                signature |= 1 << vertex
        signatures.append(signature)
    supports = _column_supports(formula)
    counts: Counter[str] = Counter(pair_cases_checked=math.comb(size, 2))
    exclusive_rows: list[dict[str, Any]] = []
    for left, right in itertools.combinations(range(size), 2):
        left_signature = signatures[left]
        right_signature = signatures[right]
        both = (left_signature & right_signature).bit_count()
        state_counts = {
            "00": len(width_two)
            - left_signature.bit_count()
            - right_signature.bit_count()
            + both,
            "01": right_signature.bit_count() - both,
            "10": left_signature.bit_count() - both,
            "11": both,
        }
        exclusive = (
            state_counts["00"] == 0
            and state_counts["11"] == 0
            and state_counts["01"] > 0
            and state_counts["10"] > 0
        )
        if not exclusive:
            continue
        counts["exclusive_pairs"] += 1
        ports = (left + 1, right + 1)
        ordinary_state_profile: dict[str, Any] = {}
        for state in ("00", "01", "10", "11"):
            state_rows = [
                (basis, width)
                for basis, width in basis_rows
                if _state_signature(basis, ports) == state
            ]
            minimum = min((width for _, width in state_rows), default=None)
            witness = next(
                (
                    list(basis)
                    for basis, width in state_rows
                    if width == minimum
                ),
                None,
            )
            ordinary_state_profile[state] = {
                "basis_count": len(state_rows),
                "minimum_width": minimum,
                "minimum_witness": witness,
            }
        pair_rank = production._vector_rank((vectors[left], vectors[right]))
        identical = supports[left] == supports[right]
        category = exclusive_category(pair_rank, identical)
        eligible = category == "eligible"
        ordinary_all_states = all(
            ordinary_state_profile[state]["basis_count"] > 0
            for state in ("00", "01", "10", "11")
        )
        two_sided_width_barrier = (
            ordinary_all_states
            and ordinary_state_profile["00"]["minimum_width"] > 2
            and ordinary_state_profile["11"]["minimum_width"] > 2
        )
        if eligible != two_sided_width_barrier:
            raise AssertionError("escape-lemma category disagrees with direct basis census")
        counts[category] += 1
        if eligible:
            counts["eligible_pairs"] += 1
        if two_sided_width_barrier:
            counts["two_sided_width_barriers"] += 1
        exclusive_rows.append(
            {
                "ports": list(ports),
                "width_two_state_counts": state_counts,
                "kernel_pair_rank": pair_rank,
                "primal_column_supports": [
                    list(supports[left]),
                    list(supports[right]),
                ],
                "primal_incidence_identical": identical,
                "category": category,
                "eligible": eligible,
                "ordinary_state_profile": ordinary_state_profile,
                "ordinary_all_states": ordinary_all_states,
                "two_sided_width_barrier": two_sided_width_barrier,
            }
        )
    keys = (
        "pair_cases_checked",
        "exclusive_pairs",
        "rank_below_two_distinct",
        "rank_below_two_identical",
        "rank_two_identical",
        "eligible_pairs",
        "two_sided_width_barriers",
    )
    return {
        "counts": {key: counts[key] for key in keys},
        "exclusive_pair_stream_sha256": _json_stream_digest(exclusive_rows),
        "eligible_pair_witnesses": [
            row for row in exclusive_rows if row["eligible"]
        ],
    }


def analyze_formula(formula: Formula) -> dict[str, Any]:
    canonical = production.canonical_cubic_formula(formula)
    census, vectors, basis_rows = basis_profile(canonical)
    if census["nullity"] < TARGET_NULLITY:
        raise ValueError("lift candidate must have nullity at least three")
    return {
        "formula": [list(clause) for clause in canonical],
        "formula_sha256": formula_digest(canonical),
        "connected": production.incidence_connected(canonical),
        "rank": census["rank"],
        "nullity": census["nullity"],
        "basis_census": census,
        "pair_profile": pair_profile(canonical, vectors, basis_rows),
    }


def _enumerate_formula_population(
    order: int,
    *,
    representative_second_matchings: bool,
) -> set[Formula]:
    identity = tuple(range(order))
    if representative_second_matchings:
        seconds: Iterable[Matching] = (
            canonical_cycle_permutation(partition)
            for partition in cycle_partitions(order)
        )
    else:
        seconds = (
            permutation
            for permutation in itertools.permutations(identity)
            if all(permutation[row] != row for row in range(order))
        )
    formulas: set[Formula] = set()
    for second in seconds:
        for third in itertools.permutations(identity):
            if any(
                third[row] == row or third[row] == second[row]
                for row in range(order)
            ):
                continue
            formula = formula_from_factorization(second, third)
            if len(set(formula)) == order:
                formulas.add(formula)
    return formulas


def _column_relabel_key(formula: Formula) -> Formula:
    order = len(formula)

    def relabel(permutation: Matching) -> Formula:
        rows: list[tuple[int, int, int]] = []
        for clause in formula:
            values = sorted(permutation[value - 1] + 1 for value in clause)
            rows.append((values[0], values[1], values[2]))
        return tuple(sorted(rows))

    return min(
        relabel(permutation)
        for permutation in itertools.permutations(range(order))
    )


def symmetry_completeness_control() -> dict[str, Any]:
    """Brute-force the cycle-type quotient against the full p,q domain at n<=6."""

    rows: list[dict[str, Any]] = []
    for order in range(4, 7):
        full = _enumerate_formula_population(
            order,
            representative_second_matchings=False,
        )
        representatives = _enumerate_formula_population(
            order,
            representative_second_matchings=True,
        )
        full_classes = {_column_relabel_key(formula) for formula in full}
        representative_classes = {
            _column_relabel_key(formula) for formula in representatives
        }
        if full_classes != representative_classes:
            raise AssertionError("cycle-type quotient lost a small-order class")
        rows.append(
            {
                "order": order,
                "full_row_sorted_formulas": len(full),
                "representative_row_sorted_formulas": len(representatives),
                "full_isomorphism_classes": len(full_classes),
                "representative_isomorphism_classes": len(
                    representative_classes
                ),
                "class_stream_sha256": _formula_stream_digest(
                    sorted(full_classes)
                ),
                "same_isomorphism_classes": True,
            }
        )
    return {
        "orders": rows,
        "all_small_order_classes_preserved": True,
        "isomorphism_convention": (
            "row sorting quotients clause relabeling; exhaustive variable "
            "permutation quotients variable relabeling; bipartition sides are "
            "not exchanged"
        ),
    }


def classification_controls() -> list[dict[str, Any]]:
    cases = (
        (1, False, "rank_below_two_distinct"),
        (1, True, "rank_below_two_identical"),
        (2, True, "rank_two_identical"),
        (2, False, "eligible"),
    )
    rows = []
    for pair_rank, identical, expected in cases:
        observed = exclusive_category(pair_rank, identical)
        if observed != expected:
            raise AssertionError("exclusive-pair category control failed")
        rows.append(
            {
                "kernel_pair_rank": pair_rank,
                "primal_incidence_identical": identical,
                "category": observed,
            }
        )
    return rows


def enumerate_order(order: int) -> dict[str, Any]:
    """Build one symmetry-complete covering population and analyze its targets."""

    if not MINIMUM_ORDER <= order <= MAXIMUM_SUPPORTED_ORDER:
        raise ValueError("order is outside the supported bounded domain")
    identity = tuple(range(order))
    partitions = tuple(cycle_partitions(order))
    formulas: set[Formula] = set()
    target_provenance: dict[Formula, dict[str, Any]] = {}
    modular_histogram: Counter[int] = Counter()
    exact_target_histogram: Counter[int] = Counter()
    permutations_scanned = 0
    legal_factorizations = 0
    distinct_clause_factorizations = 0
    modular_target_candidates = 0
    modular_false_positives = 0

    for partition in partitions:
        second = canonical_cycle_permutation(partition)
        for third in itertools.permutations(identity):
            permutations_scanned += 1
            if any(
                third[row] == row or third[row] == second[row]
                for row in range(order)
            ):
                continue
            legal_factorizations += 1
            formula = formula_from_factorization(second, third)
            if len(set(formula)) != order:
                continue
            distinct_clause_factorizations += 1
            if formula in formulas:
                continue
            formulas.add(formula)
            modular_rank = rank_mod_prime(formula)
            modular_histogram[modular_rank] += 1
            if modular_rank > order - TARGET_NULLITY:
                continue
            modular_target_candidates += 1
            profile = production.cubic_kernel_profile(formula)
            nullity = int(profile["nullity"])
            if nullity < TARGET_NULLITY:
                modular_false_positives += 1
                continue
            exact_target_histogram[nullity] += 1
            target_provenance[formula] = {
                "cycle_partition": list(partition),
                "identity_matching": list(range(1, order + 1)),
                "second_matching": [value + 1 for value in second],
                "third_matching": [value + 1 for value in third],
            }

    target_rows: list[dict[str, Any]] = []
    pair_totals: Counter[str] = Counter()
    width_patterns: Counter[str] = Counter()
    connected_targets = 0
    disconnected_targets = 0
    for formula in sorted(target_provenance):
        connected = production.incidence_connected(formula)
        common = {
            "formula": [list(clause) for clause in formula],
            "formula_sha256": formula_digest(formula),
            "first_factorization": target_provenance[formula],
            "connected": connected,
        }
        if not connected:
            disconnected_targets += 1
            profile = production.cubic_kernel_profile(formula)
            target_rows.append(
                {
                    **common,
                    "status": "disconnected",
                    "rank": profile["rank"],
                    "nullity": profile["nullity"],
                }
            )
            continue
        connected_targets += 1
        analysis = analyze_formula(formula)
        pair_totals.update(analysis["pair_profile"]["counts"])
        width_patterns[
            f"k{analysis['nullity']}:w2-bases-{analysis['basis_census']['width_two_basis_count']}"
        ] += 1
        target_rows.append(
            {
                **common,
                "status": "analyzed",
                "rank": analysis["rank"],
                "nullity": analysis["nullity"],
                "basis_census": analysis["basis_census"],
                "pair_profile": analysis["pair_profile"],
            }
        )

    pair_keys = (
        "pair_cases_checked",
        "exclusive_pairs",
        "rank_below_two_distinct",
        "rank_below_two_identical",
        "rank_two_identical",
        "eligible_pairs",
        "two_sided_width_barriers",
    )
    return {
        "order": order,
        "cycle_partitions": [list(partition) for partition in partitions],
        "cycle_type_count": len(partitions),
        "third_permutations_scanned": permutations_scanned,
        "legal_factorizations": legal_factorizations,
        "distinct_clause_factorizations": distinct_clause_factorizations,
        "duplicate_row_sorted_factorizations": (
            distinct_clause_factorizations - len(formulas)
        ),
        "unique_row_sorted_formulas": len(formulas),
        "formula_stream_sha256": _formula_stream_digest(sorted(formulas)),
        "modular_rank_histogram": {
            str(rank): modular_histogram[rank]
            for rank in sorted(modular_histogram)
        },
        "modular_target_candidates": modular_target_candidates,
        "modular_false_positives": modular_false_positives,
        "exact_target_nullity_histogram": {
            str(nullity): exact_target_histogram[nullity]
            for nullity in sorted(exact_target_histogram)
        },
        "exact_nullity_at_least_three_formulas": len(target_provenance),
        "connected_target_formulas": connected_targets,
        "disconnected_target_formulas": disconnected_targets,
        "width_two_pattern_histogram": {
            key: width_patterns[key] for key in sorted(width_patterns)
        },
        "pair_summary": {key: pair_totals[key] for key in pair_keys},
        "targets": target_rows,
    }


def build_receipt(maximum_order: int = DEFAULT_MAXIMUM_ORDER) -> dict[str, Any]:
    if not MINIMUM_ORDER <= maximum_order <= MAXIMUM_SUPPORTED_ORDER:
        raise ValueError(
            f"maximum order must be in {MINIMUM_ORDER}..{MAXIMUM_SUPPORTED_ORDER}"
        )
    control_analysis = analyze_formula(NULLITY_THREE_CONTROL)
    orders = [
        enumerate_order(order)
        for order in range(MINIMUM_ORDER, maximum_order + 1)
    ]
    pair_keys = tuple(orders[0]["pair_summary"])
    exact_targets = sum(
        row["exact_nullity_at_least_three_formulas"] for row in orders
    )
    connected_targets = sum(row["connected_target_formulas"] for row in orders)
    summary: dict[str, Any] = {
        "minimum_order": MINIMUM_ORDER,
        "maximum_order": maximum_order,
        "orders_screened": len(orders),
        "unique_row_sorted_formulas": sum(
            row["unique_row_sorted_formulas"] for row in orders
        ),
        "modular_target_candidates": sum(
            row["modular_target_candidates"] for row in orders
        ),
        "modular_false_positives": sum(
            row["modular_false_positives"] for row in orders
        ),
        "exact_nullity_at_least_three_formulas": exact_targets,
        "connected_target_formulas": connected_targets,
        "disconnected_target_formulas": sum(
            row["disconnected_target_formulas"] for row in orders
        ),
    }
    for key in pair_keys:
        summary[key] = sum(row["pair_summary"][key] for row in orders)
    nontrivial_orders = [
        row["order"]
        for row in orders
        if row["exact_nullity_at_least_three_formulas"]
    ]
    summary["first_order_with_nullity_at_least_three"] = (
        min(nontrivial_orders) if nontrivial_orders else None
    )
    if summary["two_sided_width_barriers"]:
        result = "cubic_width_barrier_found_in_bounded_symmetry_cover"
    else:
        result = "no_cubic_width_barrier_in_bounded_symmetry_cover"
    summary = dict(sorted(summary.items()))
    if (
        maximum_order == DEFAULT_MAXIMUM_ORDER
        and EXPECTED_CANONICAL_SUMMARY is not None
        and summary != EXPECTED_CANONICAL_SUMMARY
    ):
        raise AssertionError("frozen canonical lift summary changed")
    return {
        "schema": SCHEMA,
        "configuration": {
            "minimum_order": MINIMUM_ORDER,
            "maximum_order": maximum_order,
            "maximum_supported_order": MAXIMUM_SUPPORTED_ORDER,
            "target_nullity": TARGET_NULLITY,
            "modular_prime": MODULAR_PRIME,
            "simple_formula_convention": (
                "each clause contains three distinct variables, every variable "
                "occurs three times, and all clause triples are distinct; "
                "distinct variable incidence columns are not required"
            ),
        },
        "definitions": {
            "ground_basis": (
                "a basis selected from the original kernel-coordinate columns"
            ),
            "basis_width": (
                "maximum coefficient-support size after every original kernel "
                "column is re-expressed in the selected ground basis"
            ),
            "exclusive_pair": (
                "the complete width-two basis family realizes only 01 and 10, "
                "with both states nonempty"
            ),
            "eligible_pair": (
                "an exclusive pair with kernel rank two and distinct primal "
                "incidence columns"
            ),
            "two_sided_width_barrier": (
                "ordinary bases exist in all four states while width-two bases "
                "exist only in 01 and 10"
            ),
            "pair_namespace": PAIR_NAMESPACE,
            "kernel_coordinate_convention": (
                "canonical RREF coordinates are serialized; a common invertible "
                "kernel-coordinate change preserves pair rank and all "
                "basis-relative coefficient supports"
            ),
        },
        "coverage_certificate": {
            "kind": "complete symmetry cover, not a graph multiplicity census",
            "proof_steps": [
                "Every finite three-regular bipartite graph is three-edge-colorable, so its edges decompose into three perfect matchings.",
                "Relabel variable vertices so the first perfect matching is the identity; the other two matchings become edge-disjoint fixed-point-free permutations p and q.",
                "A simultaneous clause and variable relabeling preserves the identity matching and conjugates p, so p can be chosen as the canonical representative of its cycle partition.",
                "Enumerating every q disjoint from identity and p therefore includes a row/variable relabeling of every cubic formula in the bounded domain.",
                "Row sorting and variable relabeling preserve rational nullity, incidence connectivity, basis width, and existence of an eligible pair because every variable pair is checked.",
            ],
            "modular_screen_soundness": (
                "rank over F_p is at most rational rank for an integer matrix; "
                "therefore modular rank above n-3 safely excludes rational "
                "nullity at least three, while every retained modular candidate "
                "is reranked exactly over the rationals"
            ),
            "nullity_screen_soundness": (
                "a two-dimensional kernel makes every ground basis width at "
                "most two; an eligible pair also has ordinary 00 and 11 bases, "
                "so a two-sided width-two barrier requires nullity at least three"
            ),
            "small_order_bruteforce_control": symmetry_completeness_control(),
        },
        "controls": {
            "exclusive_category_truth_table": classification_controls(),
            "nullity_three_rank_two_identical_control": control_analysis,
        },
        "orders": orders,
        "summary": summary,
        "assessment": {
            "result": result,
            "bounded_conclusion": (
                f"no connected distinct-clause cubic formula through order "
                f"{maximum_order} realizes an eligible two-sided width barrier"
                if not summary["two_sided_width_barriers"]
                else (
                    f"at least one connected distinct-clause cubic formula "
                    f"through order {maximum_order} realizes a two-sided width barrier"
                )
            ),
            "exclusive_pair_degeneracy_conjecture": (
                f"verified only in the complete symmetry cover through order "
                f"{maximum_order}"
            ),
            "general_cubic_impossibility": "not established",
            "p_equals_np": "not established",
            "scope": (
                "complete for existence, not multiplicity, under row and "
                "variable relabeling within the stated order bound; no claim "
                "is made for larger formulas"
            ),
        },
    }


def run(
    output: Path = OUTPUT,
    maximum_order: int = DEFAULT_MAXIMUM_ORDER,
) -> dict[str, Any]:
    receipt = build_receipt(maximum_order)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument(
        "--maximum-order",
        type=int,
        default=DEFAULT_MAXIMUM_ORDER,
    )
    arguments = parser.parse_args()
    receipt = run(arguments.output, arguments.maximum_order)
    print(
        json.dumps(
            {
                "schema": receipt["schema"],
                "summary": receipt["summary"],
                "assessment": receipt["assessment"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
