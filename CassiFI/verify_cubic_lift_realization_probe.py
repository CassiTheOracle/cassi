"""Independently reconstruct the bounded cubic-lift realization receipt.

This verifier uses only the Python standard library.  It imports neither the
producer nor the production kernel implementation.  It rebuilds the perfect-
matching symmetry cover, the small-order full-domain quotient control, modular
rank screen, exact rational kernels, every ground-basis width, every exclusive
pair classification, all digests and aggregates, and the final bounded verdict.
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
from typing import Any, Iterable, Iterator, NoReturn, Sequence

DEFAULT_RECEIPT = Path("_diag/cubic_lift_realization_probe.json")
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


class VerificationError(ValueError):
    """Raised when a lift receipt disagrees with independent reconstruction."""


def fail(message: str) -> NoReturn:
    raise VerificationError(message)


def canonical(formula: Sequence[Sequence[int]]) -> Formula:
    size = len(formula)
    if size < MINIMUM_ORDER:
        fail("formula is too small")
    occurrences = [0] * size
    rows: list[tuple[int, int, int]] = []
    for raw_clause in formula:
        if len(raw_clause) != 3:
            fail("formula row is not a triple")
        values = sorted(int(value) for value in raw_clause)
        if len(set(values)) != 3 or any(
            value < 1 or value > size for value in values
        ):
            fail("formula row is not a distinct in-range triple")
        clause = (values[0], values[1], values[2])
        rows.append(clause)
        for value in clause:
            occurrences[value - 1] += 1
    if any(count != 3 for count in occurrences):
        fail("formula is not cubic")
    return tuple(sorted(rows))


def formula_digest(formula: Sequence[Sequence[int]]) -> str:
    rebuilt = canonical(formula)
    return hashlib.sha256(
        json.dumps(rebuilt, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def cycle_partitions(total: int, lower_bound: int = 2) -> Iterator[tuple[int, ...]]:
    if total == 0:
        yield ()
        return
    for first in range(lower_bound, total + 1):
        for remainder in cycle_partitions(total - first, first):
            yield (first, *remainder)


def canonical_cycle_permutation(partition: Sequence[int]) -> Matching:
    if not partition or any(length < 2 for length in partition):
        fail("invalid cycle partition")
    if tuple(partition) != tuple(sorted(partition)):
        fail("cycle partition is not sorted")
    image: list[int] = []
    start = 0
    for length in partition:
        image.extend(range(start + 1, start + length))
        image.append(start)
        start += length
    return tuple(image)


def formula_from_factorization(second: Matching, third: Matching) -> Formula:
    size = len(second)
    ground = list(range(size))
    if len(third) != size or sorted(second) != ground or sorted(third) != ground:
        fail("factorization does not contain permutations")
    rows: list[tuple[int, int, int]] = []
    for row in range(size):
        if second[row] == row or third[row] in (row, second[row]):
            fail("factorization matchings overlap")
        values = sorted((row + 1, second[row] + 1, third[row] + 1))
        rows.append((values[0], values[1], values[2]))
    return canonical(rows)


def rank_mod_prime(formula: Formula, prime: int = MODULAR_PRIME) -> int:
    size = len(formula)
    matrix = [
        [int(column + 1 in clause) for column in range(size)]
        for clause in formula
    ]
    rank = 0
    for column in range(size):
        pivot = next(
            (row for row in range(rank, size) if matrix[row][column] % prime),
            None,
        )
        if pivot is None:
            continue
        matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
        pivot_inverse = pow(matrix[rank][column], -1, prime)
        matrix[rank] = [
            value * pivot_inverse % prime for value in matrix[rank]
        ]
        for row in range(size):
            if row == rank:
                continue
            factor = matrix[row][column] % prime
            if factor:
                matrix[row] = [
                    (left - factor * right) % prime
                    for left, right in zip(matrix[row], matrix[rank])
                ]
        rank += 1
        if rank == size:
            break
    return rank


def formula_stream_digest(formulas: Iterable[Formula]) -> str:
    digest = hashlib.sha256()
    for formula in formulas:
        digest.update(
            json.dumps(formula, separators=(",", ":")).encode("ascii") + b"\n"
        )
    return digest.hexdigest()


def json_stream_digest(rows: Iterable[Any]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(
            json.dumps(row, separators=(",", ":"), sort_keys=True).encode("ascii")
            + b"\n"
        )
    return digest.hexdigest()


def rref(
    matrix: Sequence[Sequence[Fraction]],
) -> tuple[list[list[Fraction]], tuple[int, ...]]:
    # Convert to list of lists of Fractions for mutability
    # We work with references to lists to avoid copying entire rows unnecessarily
    values = [list(row) for row in matrix]
    row_count = len(values)
    if row_count == 0:
        return [], ()

    column_count = len(values[0])
    pivots: list[int] = []
    pivot_row = 0

    for column in range(column_count):
        if pivot_row >= row_count:
            break

        # Find a row with a non-zero entry in the current column, starting from pivot_row
        source = -1
        for r in range(pivot_row, row_count):
            if values[r][column]:
                source = r
                break

        if source == -1:
            continue

        # Swap rows
        if source != pivot_row:
            values[pivot_row], values[source] = values[source], values[pivot_row]

        # Normalize the pivot row
        scale = values[pivot_row][column]
        # In-place normalization of the pivot row
        pivot_row_list = values[pivot_row]
        for i in range(column_count):
            pivot_row_list[i] = pivot_row_list[i] / scale

        # Eliminate other rows
        for r in range(row_count):
            if r == pivot_row:
                continue
            factor = values[r][column]
            if factor:
                row_list = values[r]
                # In-place row operation: row[r] -= factor * pivot_row
                # We can optimize this by iterating only relevant columns or all
                # Since it's RREF, we need to update all columns
                for i in range(column_count):
                    row_list[i] = row_list[i] - factor * pivot_row_list[i]

        pivots.append(column)
        pivot_row += 1

    return values, tuple(pivots)


def kernel_columns(formula: Formula) -> tuple[int, tuple[Vector, ...]]:
    size = len(formula)
    matrix = [
        [Fraction(int(column + 1 in clause)) for column in range(size)]
        for clause in formula
    ]
    reduced, pivots = rref(matrix)
    free = tuple(column for column in range(size) if column not in pivots)
    free_positions = {column: index for index, column in enumerate(free)}
    pivot_positions = {column: index for index, column in enumerate(pivots)}
    vectors: list[Vector] = []
    for column in range(size):
        if column in free_positions:
            free_index = free_positions[column]
            vectors.append(
                tuple(
                    Fraction(int(index == free_index))
                    for index in range(len(free))
                )
            )
        else:
            row = pivot_positions[column]
            vectors.append(
                tuple(-reduced[row][free_column] for free_column in free)
            )
    return len(pivots), tuple(vectors)


def vector_rank(vectors: Sequence[Vector]) -> int:
    if not vectors:
        return 0
    matrix = [
        [vectors[column][row] for column in range(len(vectors))]
        for row in range(len(vectors[0]))
    ]
    return len(rref(matrix)[1])


def basis_coordinates(basis: Sequence[Vector], vector: Vector) -> Vector:
    dimension = len(basis)
    augmented = [
        [basis[column][row] for column in range(dimension)] + [vector[row]]
        for row in range(dimension)
    ]
    reduced, pivots = rref(augmented)
    if pivots[:dimension] != tuple(range(dimension)):
        fail("ground-basis coordinate solve is singular")
    return tuple(reduced[row][-1] for row in range(dimension))


def incidence_connected(formula: Formula) -> bool:
    size = len(formula)
    adjacency = [set() for _ in range(2 * size)]
    for row, clause in enumerate(formula):
        for variable in clause:
            column_vertex = size + variable - 1
            adjacency[row].add(column_vertex)
            adjacency[column_vertex].add(row)
    seen = {0}
    stack = [0]
    while stack:
        vertex = stack.pop()
        for target in adjacency[vertex]:
            if target not in seen:
                seen.add(target)
                stack.append(target)
    return len(seen) == 2 * size


def column_supports(formula: Formula) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(
            row + 1
            for row, clause in enumerate(formula)
            if column in clause
        )
        for column in range(1, len(formula) + 1)
    )


def state_signature(basis: Sequence[int], ports: tuple[int, int]) -> str:
    return "".join("1" if port in basis else "0" for port in ports)


def exclusive_category(pair_rank: int, identical: bool) -> str:
    if pair_rank >= 2:
        return "rank_two_identical" if identical else "eligible"
    return "rank_below_two_identical" if identical else "rank_below_two_distinct"


def basis_profile(
    formula: Formula,
) -> tuple[dict[str, Any], tuple[Vector, ...], tuple[tuple[Basis, int], ...]]:
    matrix_rank, vectors = kernel_columns(formula)
    nullity = len(formula) - matrix_rank
    subset_total = math.comb(len(formula), nullity)
    rows: list[tuple[Basis, int]] = []
    width_histogram: Counter[int] = Counter()
    width_two: list[list[int]] = []
    for selected in itertools.combinations(range(len(formula)), nullity):
        selected_vectors = tuple(vectors[index] for index in selected)
        if vector_rank(selected_vectors) != nullity:
            continue
        width = max(
            (
                sum(
                    coordinate != 0
                    for coordinate in basis_coordinates(selected_vectors, vector)
                )
                for vector in vectors
            ),
            default=0,
        )
        basis = tuple(index + 1 for index in selected)
        rows.append((basis, width))
        width_histogram[width] += 1
        if width <= 2:
            width_two.append(list(basis))
    receipt = {
        "rank": matrix_rank,
        "nullity": nullity,
        "basis_subsets_total": subset_total,
        "basis_subsets_checked": subset_total,
        "independent_ground_bases": len(rows),
        "ground_basis_stream_sha256": json_stream_digest(
            {"basis": list(basis), "maximum_support": width}
            for basis, width in rows
        ),
        "width_two_basis_count": len(width_two),
        "width_two_basis_stream_sha256": json_stream_digest(width_two),
        "basis_maximum_support_histogram": {
            str(width): width_histogram[width]
            for width in sorted(width_histogram)
        },
        "exact": True,
    }
    return receipt, vectors, tuple(rows)


def pair_profile(
    formula: Formula,
    vectors: tuple[Vector, ...],
    basis_rows: tuple[tuple[Basis, int], ...],
) -> dict[str, Any]:
    width_two = tuple(basis for basis, width in basis_rows if width <= 2)
    size = len(formula)
    signatures = []
    for column in range(1, size + 1):
        mask = sum(
            1 << index
            for index, basis in enumerate(width_two)
            if column in basis
        )
        signatures.append(mask)
    supports = column_supports(formula)
    counts: Counter[str] = Counter(pair_cases_checked=math.comb(size, 2))
    exclusive_rows: list[dict[str, Any]] = []
    for left, right in itertools.combinations(range(size), 2):
        overlap = (signatures[left] & signatures[right]).bit_count()
        states = {
            "00": len(width_two)
            - signatures[left].bit_count()
            - signatures[right].bit_count()
            + overlap,
            "01": signatures[right].bit_count() - overlap,
            "10": signatures[left].bit_count() - overlap,
            "11": overlap,
        }
        if not (
            states["00"] == 0
            and states["11"] == 0
            and states["01"] > 0
            and states["10"] > 0
        ):
            continue
        counts["exclusive_pairs"] += 1
        ports = (left + 1, right + 1)
        ordinary_profile: dict[str, Any] = {}
        for state in ("00", "01", "10", "11"):
            matching = [
                (basis, width)
                for basis, width in basis_rows
                if state_signature(basis, ports) == state
            ]
            minimum = min((width for _, width in matching), default=None)
            witness = next(
                (
                    list(basis)
                    for basis, width in matching
                    if width == minimum
                ),
                None,
            )
            ordinary_profile[state] = {
                "basis_count": len(matching),
                "minimum_width": minimum,
                "minimum_witness": witness,
            }
        pair_rank = vector_rank((vectors[left], vectors[right]))
        identical = supports[left] == supports[right]
        category = exclusive_category(pair_rank, identical)
        eligible = category == "eligible"
        ordinary_all_states = all(
            ordinary_profile[state]["basis_count"] > 0
            for state in ("00", "01", "10", "11")
        )
        barrier = (
            ordinary_all_states
            and ordinary_profile["00"]["minimum_width"] > 2
            and ordinary_profile["11"]["minimum_width"] > 2
        )
        if eligible != barrier:
            fail("direct basis barrier disagrees with escape-lemma category")
        counts[category] += 1
        if eligible:
            counts["eligible_pairs"] += 1
        if barrier:
            counts["two_sided_width_barriers"] += 1
        exclusive_rows.append(
            {
                "ports": list(ports),
                "width_two_state_counts": states,
                "kernel_pair_rank": pair_rank,
                "primal_column_supports": [
                    list(supports[left]),
                    list(supports[right]),
                ],
                "primal_incidence_identical": identical,
                "category": category,
                "eligible": eligible,
                "ordinary_state_profile": ordinary_profile,
                "ordinary_all_states": ordinary_all_states,
                "two_sided_width_barrier": barrier,
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
        "exclusive_pair_stream_sha256": json_stream_digest(exclusive_rows),
        "eligible_pair_witnesses": [
            row for row in exclusive_rows if row["eligible"]
        ],
    }


def analyze_formula(formula: Formula) -> dict[str, Any]:
    rebuilt = canonical(formula)
    census, vectors, rows = basis_profile(rebuilt)
    if census["nullity"] < TARGET_NULLITY:
        fail("candidate nullity is below target")
    return {
        "formula": [list(clause) for clause in rebuilt],
        "formula_sha256": formula_digest(rebuilt),
        "connected": incidence_connected(rebuilt),
        "rank": census["rank"],
        "nullity": census["nullity"],
        "basis_census": census,
        "pair_profile": pair_profile(rebuilt, vectors, rows),
    }


def enumerate_formula_population(
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
            candidate
            for candidate in itertools.permutations(identity)
            if all(candidate[row] != row for row in range(order))
        )
    formulas: set[Formula] = set()
    for second in seconds:
        for third in itertools.permutations(identity):
            if any(
                third[row] in (row, second[row]) for row in range(order)
            ):
                continue
            formula = formula_from_factorization(second, third)
            if len(set(formula)) == order:
                formulas.add(formula)
    return formulas


def column_relabel_key(formula: Formula) -> Formula:
    order = len(formula)
    candidates: list[Formula] = []
    for permutation in itertools.permutations(range(order)):
        rows: list[tuple[int, int, int]] = []
        for clause in formula:
            values = sorted(permutation[value - 1] + 1 for value in clause)
            rows.append((values[0], values[1], values[2]))
        candidates.append(tuple(sorted(rows)))
    return min(candidates)


def symmetry_completeness_control() -> dict[str, Any]:
    rows = []
    for order in (4, 5, 6):
        full = enumerate_formula_population(
            order,
            representative_second_matchings=False,
        )
        reduced = enumerate_formula_population(
            order,
            representative_second_matchings=True,
        )
        full_classes = {column_relabel_key(formula) for formula in full}
        reduced_classes = {column_relabel_key(formula) for formula in reduced}
        if full_classes != reduced_classes:
            fail("small-order representative domain loses an isomorphism class")
        rows.append(
            {
                "order": order,
                "full_row_sorted_formulas": len(full),
                "representative_row_sorted_formulas": len(reduced),
                "full_isomorphism_classes": len(full_classes),
                "representative_isomorphism_classes": len(reduced_classes),
                "class_stream_sha256": formula_stream_digest(sorted(full_classes)),
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
    specifications = (
        (1, False, "rank_below_two_distinct"),
        (1, True, "rank_below_two_identical"),
        (2, True, "rank_two_identical"),
        (2, False, "eligible"),
    )
    rows = []
    for rank, identical, expected in specifications:
        category = exclusive_category(rank, identical)
        if category != expected:
            fail("exclusive category truth table does not fire")
        rows.append(
            {
                "kernel_pair_rank": rank,
                "primal_incidence_identical": identical,
                "category": category,
            }
        )
    return rows


def enumerate_order(order: int) -> dict[str, Any]:
    if not MINIMUM_ORDER <= order <= MAXIMUM_SUPPORTED_ORDER:
        fail("order is outside supported bounds")
    identity = tuple(range(order))
    partitions = tuple(cycle_partitions(order))
    formulas: set[Formula] = set()
    provenance: dict[Formula, dict[str, Any]] = {}
    modular_histogram: Counter[int] = Counter()
    exact_histogram: Counter[int] = Counter()
    permutations_scanned = 0
    legal_factorizations = 0
    distinct_clause_factorizations = 0
    modular_candidates = 0
    false_positives = 0
    for partition in partitions:
        second = canonical_cycle_permutation(partition)
        for third in itertools.permutations(identity):
            permutations_scanned += 1
            if any(third[row] in (row, second[row]) for row in range(order)):
                continue
            legal_factorizations += 1
            formula = formula_from_factorization(second, third)
            if len(set(formula)) != order:
                continue
            distinct_clause_factorizations += 1
            if formula in formulas:
                continue
            formulas.add(formula)
            finite_rank = rank_mod_prime(formula)
            modular_histogram[finite_rank] += 1
            if finite_rank > order - TARGET_NULLITY:
                continue
            modular_candidates += 1
            rational_rank, _ = kernel_columns(formula)
            nullity = order - rational_rank
            if nullity < TARGET_NULLITY:
                false_positives += 1
                continue
            exact_histogram[nullity] += 1
            provenance[formula] = {
                "cycle_partition": list(partition),
                "identity_matching": list(range(1, order + 1)),
                "second_matching": [value + 1 for value in second],
                "third_matching": [value + 1 for value in third],
            }

    targets: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()
    width_patterns: Counter[str] = Counter()
    connected_count = 0
    disconnected_count = 0
    for formula in sorted(provenance):
        connected = incidence_connected(formula)
        common = {
            "formula": [list(clause) for clause in formula],
            "formula_sha256": formula_digest(formula),
            "first_factorization": provenance[formula],
            "connected": connected,
        }
        if not connected:
            disconnected_count += 1
            rational_rank, _ = kernel_columns(formula)
            targets.append(
                {
                    **common,
                    "status": "disconnected",
                    "rank": rational_rank,
                    "nullity": order - rational_rank,
                }
            )
            continue
        connected_count += 1
        analysis = analyze_formula(formula)
        totals.update(analysis["pair_profile"]["counts"])
        width_patterns[
            f"k{analysis['nullity']}:w2-bases-{analysis['basis_census']['width_two_basis_count']}"
        ] += 1
        targets.append(
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
        "formula_stream_sha256": formula_stream_digest(sorted(formulas)),
        "modular_rank_histogram": {
            str(rank): modular_histogram[rank]
            for rank in sorted(modular_histogram)
        },
        "modular_target_candidates": modular_candidates,
        "modular_false_positives": false_positives,
        "exact_target_nullity_histogram": {
            str(nullity): exact_histogram[nullity]
            for nullity in sorted(exact_histogram)
        },
        "exact_nullity_at_least_three_formulas": len(provenance),
        "connected_target_formulas": connected_count,
        "disconnected_target_formulas": disconnected_count,
        "width_two_pattern_histogram": {
            key: width_patterns[key] for key in sorted(width_patterns)
        },
        "pair_summary": {key: totals[key] for key in pair_keys},
        "targets": targets,
    }


def expected_receipt(maximum_order: int) -> dict[str, Any]:
    if not MINIMUM_ORDER <= maximum_order <= MAXIMUM_SUPPORTED_ORDER:
        fail("receipt maximum order is outside supported bounds")
    control_analysis = analyze_formula(NULLITY_THREE_CONTROL)
    orders = [
        enumerate_order(order)
        for order in range(MINIMUM_ORDER, maximum_order + 1)
    ]
    pair_keys = tuple(orders[0]["pair_summary"])
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
        "exact_nullity_at_least_three_formulas": sum(
            row["exact_nullity_at_least_three_formulas"] for row in orders
        ),
        "connected_target_formulas": sum(
            row["connected_target_formulas"] for row in orders
        ),
        "disconnected_target_formulas": sum(
            row["disconnected_target_formulas"] for row in orders
        ),
    }
    for key in pair_keys:
        summary[key] = sum(row["pair_summary"][key] for row in orders)
    nontrivial = [
        row["order"]
        for row in orders
        if row["exact_nullity_at_least_three_formulas"]
    ]
    summary["first_order_with_nullity_at_least_three"] = (
        min(nontrivial) if nontrivial else None
    )
    result = (
        "cubic_width_barrier_found_in_bounded_symmetry_cover"
        if summary["two_sided_width_barriers"]
        else "no_cubic_width_barrier_in_bounded_symmetry_cover"
    )
    summary = dict(sorted(summary.items()))
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
            "ground_basis": "a basis selected from the original kernel-coordinate columns",
            "basis_width": "maximum coefficient-support size after every original kernel column is re-expressed in the selected ground basis",
            "exclusive_pair": "the complete width-two basis family realizes only 01 and 10, with both states nonempty",
            "eligible_pair": "an exclusive pair with kernel rank two and distinct primal incidence columns",
            "two_sided_width_barrier": "ordinary bases exist in all four states while width-two bases exist only in 01 and 10",
            "pair_namespace": PAIR_NAMESPACE,
            "kernel_coordinate_convention": "canonical RREF coordinates are serialized; a common invertible kernel-coordinate change preserves pair rank and all basis-relative coefficient supports",
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
            "modular_screen_soundness": "rank over F_p is at most rational rank for an integer matrix; therefore modular rank above n-3 safely excludes rational nullity at least three, while every retained modular candidate is reranked exactly over the rationals",
            "nullity_screen_soundness": "a two-dimensional kernel makes every ground basis width at most two; an eligible pair also has ordinary 00 and 11 bases, so a two-sided width-two barrier requires nullity at least three",
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


def verify(
    path: str | Path = DEFAULT_RECEIPT,
    maximum_order: int = DEFAULT_MAXIMUM_ORDER,
) -> dict[str, Any]:
    receipt_path = Path(path)
    try:
        actual = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read receipt: {error}")
    if actual.get("schema") != SCHEMA:
        fail("receipt schema mismatch")
    configuration = actual.get("configuration")
    if not isinstance(configuration, dict):
        fail("receipt configuration is missing")
    if configuration.get("maximum_order") != maximum_order:
        fail("receipt maximum order mismatch")
    expected = expected_receipt(maximum_order)
    if actual != expected:
        fail("receipt mismatch")
    return {
        "status": "verified",
        "schema": SCHEMA,
        **expected["summary"],
        "result": expected["assessment"]["result"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", default=str(DEFAULT_RECEIPT))
    parser.add_argument(
        "--maximum-order",
        type=int,
        default=DEFAULT_MAXIMUM_ORDER,
    )
    arguments = parser.parse_args()
    print(
        json.dumps(
            verify(arguments.receipt, arguments.maximum_order),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
