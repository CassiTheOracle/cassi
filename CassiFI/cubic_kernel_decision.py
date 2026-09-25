"""Exact rational kernel analysis for cubic monotone one-in-three SAT.

For a formula with ``n`` clauses, ``n`` variables, three distinct variables in
all clauses, and three occurrences of every variable, let ``M`` be its square
0/1 incidence matrix.  The formula has an exact-one assignment ``x`` exactly
when

    z = 3 x - 1  belongs to ker(M) and z_i is in {-1, 2} for every i.

The implementation computes a deterministic rational RREF.  If every pivot
coordinate depends on at most two free coordinates, exact alphabet membership
reduces to 2-SAT and is polynomial even when nullity is linear.  Otherwise it
enumerates the ``2**nullity`` allowed free-coordinate values.  This does not
give a polynomial-time algorithm for unrestricted cubic one-in-three SAT.
The line-profile helper adds sound forced-long-line pruning and a complete
projective-class coverage search for nullity at most three.  For general
nullity, the short-line branch is fixed-parameter in nullity, and the
long-line branch uses a bounded residual-basis search followed by exact
affine endpoint completion.  The complete recognizer is therefore
fixed-parameter in nullity, with an upper bound of
``2**O(nullity**2) * poly(input_size)``; this remains exponential when
nullity grows with the input and does not resolve unrestricted cubic
one-in-three SAT.
"""

from __future__ import annotations

from collections import deque
import hashlib
import itertools
import json
import math
from fractions import Fraction
from typing import Any, Sequence

Formula = tuple[tuple[int, int, int], ...]
Matrix = tuple[tuple[int, ...], ...]
_ALLOWED_KERNEL_VALUES = (Fraction(-1), Fraction(2))


class CubicKernelDecisionError(ValueError):
    """Raised when an input is outside the cubic exact-one theorem's domain."""


def canonical_cubic_formula(formula: Sequence[Sequence[int]]) -> Formula:
    """Validate and canonically order a square cubic exact-one formula."""

    # Duck-typing check for Sequence-like objects, excluding str/bytes
    if not hasattr(formula, '__iter__') or not hasattr(formula, '__len__'):
        raise CubicKernelDecisionError("formula must be a sequence of clauses")
    if isinstance(formula, (str, bytes)):
        raise CubicKernelDecisionError("formula must be a sequence of clauses")

    clause_count = len(formula)
    if clause_count < 3:
        raise CubicKernelDecisionError("formula must contain at least three clauses")

    clauses: list[tuple[int, int, int]] = []
    occurrences = [0] * clause_count

    # Pre-allocate a list for clause variables to avoid repeated list creation
    clause_vars = [0, 0, 0]

    for raw_clause in formula:
        # Check if raw_clause is a sequence (iterable and sized) but not str/bytes
        if not hasattr(raw_clause, '__iter__') or not hasattr(raw_clause, '__len__'):
            raise CubicKernelDecisionError("every clause must be a sequence")
        if isinstance(raw_clause, (str, bytes)):
            raise CubicKernelDecisionError("every clause must be a sequence")

        if len(raw_clause) != 3:
            raise CubicKernelDecisionError(
                "every clause must contain exactly three variables"
            )

        # Validate and extract variables
        is_valid = True
        for i, variable in enumerate(raw_clause):
            # Check if variable is an int but not a bool
            # In Python, bool is a subclass of int, so we must check bool first
            if isinstance(variable, bool):
                is_valid = False
                break
            if not isinstance(variable, int):
                is_valid = False
                break
            if not 1 <= variable <= clause_count:
                is_valid = False
                break
            clause_vars[i] = variable

        if not is_valid:
            raise CubicKernelDecisionError("variable identifiers must be integers")

        # Check for distinct variables
        if clause_vars[0] == clause_vars[1] or clause_vars[0] == clause_vars[2] or clause_vars[1] == clause_vars[2]:
            raise CubicKernelDecisionError(
                "the three variables in a clause must be distinct"
            )

        # Sort the clause variables
        # Manual sort for 3 elements is faster than sorted()
        a, b, c = clause_vars
        if a > b:
            a, b = b, a
        if b > c:
            b, c = c, b
            if a > b:
                a, b = b, a
        normalized = (a, b, c)
        clauses.append(normalized)

        # Update occurrences
        occurrences[a - 1] += 1
        occurrences[b - 1] += 1
        occurrences[c - 1] += 1

    # Check if every variable occurs exactly 3 times
    for count in occurrences:
        if count != 3:
            raise CubicKernelDecisionError(
                "every variable must occur in exactly three clauses"
            )

    return tuple(sorted(clauses))


def canonical_cubic_matrix(matrix: Sequence[Sequence[int]]) -> Matrix:
    """Validate and canonically order a square 0/1 cubic matrix."""

    if not isinstance(matrix, Sequence) or isinstance(matrix, (str, bytes)):
        raise CubicKernelDecisionError("matrix must be a sequence of rows")
    size = len(matrix)
    if size < 3:
        raise CubicKernelDecisionError("matrix must have size at least three")

    rows: list[tuple[int, ...]] = []
    column_sums = [0] * size
    for raw_row in matrix:
        if not isinstance(raw_row, Sequence) or isinstance(raw_row, (str, bytes)):
            raise CubicKernelDecisionError("every matrix row must be a sequence")
        if len(raw_row) != size:
            raise CubicKernelDecisionError("matrix must be square")
        row: list[int] = []
        for value in raw_row:
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value not in (0, 1)
            ):
                raise CubicKernelDecisionError("matrix entries must be 0 or 1")
            row.append(value)
        if sum(row) != 3:
            raise CubicKernelDecisionError(
                "every matrix row must contain exactly three ones"
            )
        for column, value in enumerate(row):
            column_sums[column] += value
        rows.append(tuple(row))

    if any(total != 3 for total in column_sums):
        raise CubicKernelDecisionError(
            "every matrix column must contain exactly three ones"
        )
    return tuple(sorted(rows))


def _formula_from_cubic_matrix(matrix: Matrix) -> Formula:
    clauses: list[tuple[int, int, int]] = []
    for row in matrix:
        columns = [column + 1 for column, value in enumerate(row) if value]
        if len(columns) != 3:
            raise AssertionError("canonical cubic matrix row lost its three ones")
        clauses.append((columns[0], columns[1], columns[2]))
    return tuple(clauses)


def incidence_matrix(formula: Formula) -> list[list[Fraction]]:
    """Return the exact square incidence matrix of a canonical formula."""

    size = len(formula)
    matrix = [[Fraction(0) for _ in range(size)] for _ in range(size)]
    for clause_index, clause in enumerate(formula):
        for variable in clause:
            matrix[clause_index][variable - 1] = Fraction(1)
    return matrix


def _rref(
    matrix: Sequence[Sequence[Fraction]],
) -> tuple[list[list[Fraction]], tuple[int, ...], int]:
    """Compute deterministic Gauss-Jordan RREF over the rationals."""

    values = [list(row) for row in matrix]
    row_count = len(values)
    column_count = len(values[0]) if values else 0
    pivot_columns: list[int] = []
    pivot_row = 0
    fraction_updates = 0

    for column in range(column_count):
        selected = next(
            (row for row in range(pivot_row, row_count) if values[row][column]),
            None,
        )
        if selected is None:
            continue
        if selected != pivot_row:
            values[pivot_row], values[selected] = values[selected], values[pivot_row]

        pivot = values[pivot_row][column]
        for target_column in range(column, column_count):
            values[pivot_row][target_column] /= pivot
            fraction_updates += 1

        for row in range(row_count):
            if row == pivot_row or not values[row][column]:
                continue
            factor = values[row][column]
            for target_column in range(column, column_count):
                values[row][target_column] -= factor * values[pivot_row][target_column]
                fraction_updates += 1

        pivot_columns.append(column)
        pivot_row += 1
        if pivot_row == row_count:
            break

    return values, tuple(pivot_columns), fraction_updates








def _fraction_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _system(formula: Formula) -> dict[str, Any]:
    rref, pivot_columns, fraction_updates = _rref(incidence_matrix(formula))
    pivot_set = set(pivot_columns)
    free_columns = tuple(
        column for column in range(len(formula)) if column not in pivot_set
    )
    coefficients = tuple(
        tuple(rref[row][column] for column in free_columns)
        for row in range(len(pivot_columns))
    )
    supports = tuple(
        sum(value != 0 for value in row) for row in coefficients
    )
    serialized = {
        "pivot_columns": [column + 1 for column in pivot_columns],
        "free_columns": [column + 1 for column in free_columns],
        "pivot_free_coefficients": [
            [_fraction_text(value) for value in row] for row in coefficients
        ],
    }
    digest = hashlib.sha256(
        json.dumps(serialized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    numerators = [abs(value.numerator) for row in rref for value in row]
    denominators = [value.denominator for row in rref for value in row]
    return {
        "rref": rref,
        "pivot_columns_zero_based": pivot_columns,
        "free_columns_zero_based": free_columns,
        "pivot_free_coefficients": coefficients,
        "pivot_free_supports": supports,
        "fraction_updates": fraction_updates,
        "system_digest": digest,
        "maximum_numerator_bits": max(1, max(numerators, default=0).bit_length()),
        "maximum_denominator_bits": max(
            1, max(denominators, default=1).bit_length()
        ),
    }


def _system_for_pivot_basis(
    matrix: Sequence[Sequence[Fraction]],
    pivot_columns: tuple[int, ...],
) -> dict[str, Any] | None:
    """Return the standard kernel system for a specified column basis."""

    size = len(matrix)
    if (
        len(set(pivot_columns)) != len(pivot_columns)
        or any(column < 0 or column >= size for column in pivot_columns)
    ):
        raise ValueError("pivot columns must be distinct matrix columns")
    pivot_set = set(pivot_columns)
    free_columns = tuple(
        column for column in range(size) if column not in pivot_set
    )
    column_order = pivot_columns + free_columns
    permuted = [
        [row[column] for column in column_order]
        for row in matrix
    ]
    rref, permuted_pivots, fraction_updates = _rref(permuted)
    rank = len(pivot_columns)
    if (
        len(permuted_pivots) != rank
        or permuted_pivots != tuple(range(rank))
    ):
        return None

    coefficients = tuple(
        tuple(rref[row][column] for column in range(rank, size))
        for row in range(rank)
    )
    supports = tuple(
        sum(value != 0 for value in row) for row in coefficients
    )
    serialized = {
        "pivot_columns": [column + 1 for column in pivot_columns],
        "free_columns": [column + 1 for column in free_columns],
        "pivot_free_coefficients": [
            [_fraction_text(value) for value in row]
            for row in coefficients
        ],
    }
    system_digest = hashlib.sha256(
        json.dumps(
            serialized, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    numerators = [abs(value.numerator) for row in rref for value in row]
    denominators = [value.denominator for row in rref for value in row]
    return {
        "pivot_columns_zero_based": pivot_columns,
        "free_columns_zero_based": free_columns,
        "pivot_free_coefficients": coefficients,
        "pivot_free_supports": supports,
        "fraction_updates": fraction_updates,
        "maximum_numerator_bits": max(
            1, max(numerators, default=0).bit_length()
        ),
        "maximum_denominator_bits": max(
            1, max(denominators, default=1).bit_length()
        ),
        "system_digest": system_digest,
    }


def cubic_kernel_profile(formula: Sequence[Sequence[int]]) -> dict[str, Any]:
    """Return exact rank/nullity and deterministic elimination accounting."""

    canonical = canonical_cubic_formula(formula)
    system = _system(canonical)
    rank = len(system["pivot_columns_zero_based"])
    nullity = len(system["free_columns_zero_based"])
    basis = []
    for free_index in range(nullity):
        free_values = tuple(
            Fraction(int(index == free_index)) for index in range(nullity)
        )
        vector = _candidate_vector(
            len(canonical),
            system["pivot_columns_zero_based"],
            system["free_columns_zero_based"],
            system["pivot_free_coefficients"],
            free_values,
        )
        basis.append([_fraction_text(value) for value in vector])
    supports = system["pivot_free_supports"]
    support_histogram = {
        str(support): supports.count(support) for support in sorted(set(supports))
    }
    return {
        "clauses": len(canonical),
        "variables": len(canonical),
        "rank": rank,
        "nullity": nullity,
        "candidate_kernel_vectors": 1 << nullity,
        "pivot_columns": [
            column + 1 for column in system["pivot_columns_zero_based"]
        ],
        "free_columns": [
            column + 1 for column in system["free_columns_zero_based"]
        ],
        "kernel_basis": basis,
        "maximum_pivot_free_support": max(supports, default=0),
        "pivot_free_support_histogram": support_histogram,
        "fraction_updates": system["fraction_updates"],
        "maximum_numerator_bits": system["maximum_numerator_bits"],
        "maximum_denominator_bits": system["maximum_denominator_bits"],
        "system_digest": system["system_digest"],
    }


def _kernel_coordinate_vectors(
    system: dict[str, Any], size: int
) -> tuple[tuple[Fraction, ...], ...]:
    """Represent the dual column matroid in kernel-coordinate space."""

    free_columns = system["free_columns_zero_based"]
    coefficients = system["pivot_free_coefficients"]
    nullity = len(free_columns)
    free_index = {
        column: index for index, column in enumerate(free_columns)
    }
    pivot_index = {
        column: index
        for index, column in enumerate(system["pivot_columns_zero_based"])
    }
    vectors: list[tuple[Fraction, ...]] = []
    for column in range(size):
        if column in free_index:
            index = free_index[column]
            vectors.append(
                tuple(
                    Fraction(int(coordinate == index))
                    for coordinate in range(nullity)
                )
            )
        else:
            vectors.append(
                tuple(-value for value in coefficients[pivot_index[column]])
            )
    return tuple(vectors)


def _vector_rank(vectors: Sequence[Sequence[Fraction]]) -> int:
    if not vectors:
        return 0
    _, pivots, _ = _rref(vectors)
    return len(pivots)


def _projective_key(
    vector: Sequence[Fraction],
) -> tuple[Fraction, ...] | None:
    if not any(vector):
        return None
    first = next(value for value in vector if value)
    return tuple(value / first for value in vector)


def _subspace_intersection_vector(
    left: tuple[Fraction, ...],
    right: tuple[Fraction, ...],
    other_left: tuple[Fraction, ...],
    other_right: tuple[Fraction, ...],
) -> tuple[Fraction, ...] | None:
    """Return a generator when two rank-two subspaces meet in rank one."""

    relations = [
        [
            left[row],
            right[row],
            -other_left[row],
            -other_right[row],
        ]
        for row in range(len(left))
    ]
    reduced, pivots, _ = _rref(relations)
    if len(pivots) != 3:
        return None
    free = next(column for column in range(4) if column not in pivots)
    coefficients = [Fraction(0)] * 4
    coefficients[free] = Fraction(1)
    for row, pivot in enumerate(pivots):
        coefficients[pivot] = -reduced[row][free]
    return tuple(
        coefficients[0] * left[row]
        + coefficients[1] * right[row]
        for row in range(len(left))
    )


def _projective_geometry(
    source: dict[str, Any] | Sequence[Sequence[Fraction | int]],
    size: int | None = None,
) -> dict[str, Any]:
    """Return exact projective classes and observed rank-two flats."""

    if isinstance(source, dict):
        if size is None:
            raise CubicKernelDecisionError(
                "matrix geometry requires the matrix size"
            )
        vectors = _kernel_coordinate_vectors(source, size)
    else:
        if size is not None:
            raise CubicKernelDecisionError(
                "vector geometry does not accept a matrix size"
            )
        vectors = tuple(
            tuple(Fraction(value) for value in vector)
            for vector in source
        )
    class_indices: dict[tuple[Fraction, ...], int] = {}
    class_vectors: list[tuple[Fraction, ...]] = []
    class_columns: list[list[int]] = []
    column_classes: list[int | None] = []
    for column, vector in enumerate(vectors):
        key = _projective_key(vector)
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

    line_set: set[tuple[int, ...]] = set()
    long_line_set: set[tuple[int, ...]] = set()
    for left, right in itertools.combinations(range(len(class_vectors)), 2):
        line = tuple(
            point
            for point, vector in enumerate(class_vectors)
            if _vector_rank(
                (class_vectors[left], class_vectors[right], vector)
            )
            <= 2
        )
        line_set.add(line)
        if len(line) >= 4:
            long_line_set.add(line)

    return {
        "vectors": vectors,
        "class_indices": class_indices,
        "class_vectors": class_vectors,
        "class_columns": class_columns,
        "column_classes": column_classes,
        "lines": sorted(line_set),
        "long_lines": sorted(long_line_set),
    }


def _mandatory_basis_classes(
    geometry: dict[str, Any],
) -> tuple[int, ...]:
    """Classes that every internal width-two basis must select.

    A nonbasis class of support two lies on the projective line through the two
    selected basis classes supporting it.  That line therefore contains at
    least three observed classes.  Any class outside every such rich line must
    itself be a basis class.
    """

    rich_line_classes = {
        class_index
        for line in geometry["lines"]
        if len(line) >= 3
        for class_index in line
    }
    return tuple(
        class_index
        for class_index in range(len(geometry["class_vectors"]))
        if class_index not in rich_line_classes
    )


def _class_pair_span_masks(
    class_vectors: Sequence[tuple[Fraction, ...]],
    pairs: Sequence[tuple[int, int]],
) -> dict[tuple[int, int], int]:
    """Cache exact projective pair spans as class bitmasks."""

    masks: dict[tuple[int, int], int] = {}
    for left, right in pairs:
        mask = 0
        for target, vector in enumerate(class_vectors):
            if _vector_rank(
                (class_vectors[left], class_vectors[right], vector)
            ) <= 2:
                mask |= 1 << target
        masks[(left, right)] = mask
    return masks


def _width_two_geometry_basis(
    geometry: dict[str, Any],
    nullity: int,
) -> dict[str, Any]:
    """Recognize a width-two class basis using the structured long-line search."""

    class_vectors = geometry["class_vectors"]
    class_count = len(class_vectors)
    long_lines = geometry["long_lines"]
    mandatory_classes = _mandatory_basis_classes(geometry)
    mandatory_rank = _vector_rank(
        tuple(class_vectors[index] for index in mandatory_classes)
    )
    if not long_lines:
        class_bound = nullity + math.comb(nullity, 2)
        subset_total = (
            math.comb(class_count, nullity)
            if 0 <= nullity <= class_count
            else 0
        )
        if nullity <= 2:
            greedy_chosen: list[int] = []
            if nullity == 0:
                return {
                    "status": "width_two",
                    "reason": "nullity_at_most_two",
                    "candidate_classes": (),
                    "residual_subsets_total": subset_total,
                    "residual_subsets_checked": 0,
                    "independent_basis_candidates": 1,
                    "endpoint_subsets_checked": 0,
                    "endpoint_independent_subsets": 0,
                    "endpoint_line_compatible_subsets": 0,
                    "domain_values_tried": 0,
                    "pair_span_pairs_checked": 0,
                }
            for index in range(class_count):
                if _vector_rank(
                    tuple(
                        class_vectors[item]
                        for item in greedy_chosen + [index]
                    )
                ) > len(greedy_chosen):
                    greedy_chosen.append(index)
                    if len(greedy_chosen) == nullity:
                        return {
                            "status": "width_two",
                            "reason": "nullity_at_most_two",
                            "candidate_classes": tuple(greedy_chosen),
                            "residual_subsets_total": subset_total,
                            "residual_subsets_checked": 0,
                            "independent_basis_candidates": 1,
                            "endpoint_subsets_checked": 0,
                            "endpoint_independent_subsets": 0,
                            "endpoint_line_compatible_subsets": 0,
                            "domain_values_tried": 0,
                            "pair_span_pairs_checked": 0,
                        }
            return {
                "status": "no_width_two_basis",
                "reason": "insufficient_class_rank",
                "candidate_classes": None,
                "residual_subsets_total": subset_total,
                "residual_subsets_checked": 0,
                "independent_basis_candidates": 0,
                "endpoint_subsets_checked": 0,
                "endpoint_independent_subsets": 0,
                "endpoint_line_compatible_subsets": 0,
                "domain_values_tried": 0,
                "pair_span_pairs_checked": 0,
            }
        if class_count > class_bound:
            return {
                "status": "no_width_two_basis",
                "reason": "short_line_class_bound",
                "candidate_classes": None,
                "residual_subsets_total": subset_total,
                "residual_subsets_checked": 0,
                "independent_basis_candidates": 0,
                "endpoint_subsets_checked": 0,
                "endpoint_independent_subsets": 0,
                "endpoint_line_compatible_subsets": 0,
                "domain_values_tried": 0,
                "pair_span_pairs_checked": 0,
            }
        if (
            len(mandatory_classes) > nullity
            or mandatory_rank < len(mandatory_classes)
        ):
            return {
                "status": "no_width_two_basis",
                "reason": "mandatory_class_obstruction",
                "candidate_classes": None,
                "residual_subsets_total": subset_total,
                "residual_subsets_checked": 0,
                "independent_basis_candidates": 0,
                "endpoint_subsets_checked": 0,
                "endpoint_independent_subsets": 0,
                "endpoint_line_compatible_subsets": 0,
                "domain_values_tried": 0,
                "pair_span_pairs_checked": 0,
            }
        pair_keys = list(itertools.combinations(range(class_count), 2))
        pair_span_masks = _class_pair_span_masks(class_vectors, pair_keys)
        full_mask = (1 << class_count) - 1
        subset_total = (
            math.comb(class_count, nullity)
            if 0 <= nullity <= class_count
            else 0
        )
        subsets_checked = 0
        independent_candidates = 0
        if 0 <= nullity <= class_count:
            for chosen in itertools.combinations(range(class_count), nullity):
                subsets_checked += 1
                if _vector_rank(
                    tuple(class_vectors[index] for index in chosen)
                ) != nullity:
                    continue
                independent_candidates += 1
                if not set(mandatory_classes).issubset(chosen):
                    continue
                covered = sum(1 << index for index in chosen)
                for pair in itertools.combinations(chosen, 2):
                    covered |= pair_span_masks[pair]
                if covered == full_mask:
                    return {
                        "status": "width_two",
                        "reason": "exact_exhaustive_geometry_search",
                        "candidate_classes": chosen,
                        "residual_subsets_total": subset_total,
                        "residual_subsets_checked": subsets_checked,
                        "independent_basis_candidates": independent_candidates,
                        "endpoint_subsets_checked": 0,
                        "endpoint_independent_subsets": 0,
                        "endpoint_line_compatible_subsets": 0,
                        "domain_values_tried": 0,
                        "pair_span_pairs_checked": len(pair_span_masks),
                    }
        return {
            "status": "no_width_two_basis",
            "reason": "exact_exhaustive_geometry_search",
            "candidate_classes": None,
            "residual_subsets_total": subset_total,
            "residual_subsets_checked": subsets_checked,
            "independent_basis_candidates": independent_candidates,
            "endpoint_subsets_checked": 0,
            "endpoint_independent_subsets": 0,
            "endpoint_line_compatible_subsets": 0,
            "domain_values_tried": 0,
            "pair_span_pairs_checked": len(pair_span_masks),
        }

    constraints = _long_line_constraints(geometry, nullity)
    reason = constraints["reason"]
    if reason is not None:
        return {
            "status": "no_width_two_basis",
            "reason": reason,
            "candidate_classes": None,
            "residual_subsets_total": 0,
            "residual_subsets_checked": 0,
            "independent_basis_candidates": 0,
            "endpoint_subsets_checked": 0,
            "endpoint_independent_subsets": 0,
            "endpoint_line_compatible_subsets": 0,
            "domain_values_tried": 0,
            "pair_span_pairs_checked": 0,
        }

    layout = _prepare_long_line_layout(geometry, nullity, constraints)
    reason = layout["reason"]
    if reason is not None:
        return {
            "status": "no_width_two_basis",
            "reason": reason,
            "candidate_classes": None,
            "residual_subsets_total": 0,
            "residual_subsets_checked": 0,
            "independent_basis_candidates": 0,
            "endpoint_subsets_checked": 0,
            "endpoint_independent_subsets": 0,
            "endpoint_line_compatible_subsets": 0,
            "domain_values_tried": 0,
            "pair_span_pairs_checked": 0,
        }

    residual_classes = layout["residual_classes"]
    residual_slots = layout["residual_slots"]
    residual_subsets_total = (
        math.comb(len(residual_classes), residual_slots)
        if 0 <= residual_slots <= len(residual_classes)
        else 0
    )
    required_residual_classes = tuple(
        index
        for index in mandatory_classes
        if index not in set(layout["reference_classes"])
    )
    if (
        mandatory_rank < len(mandatory_classes)
        or len(required_residual_classes) > residual_slots
    ):
        return {
            "status": "no_width_two_basis",
            "reason": "mandatory_class_obstruction",
            "candidate_classes": None,
            "residual_subsets_total": residual_subsets_total,
            "residual_subsets_checked": 0,
            "independent_basis_candidates": 0,
            "endpoint_subsets_checked": 0,
            "endpoint_independent_subsets": 0,
            "endpoint_line_compatible_subsets": 0,
            "domain_values_tried": 0,
            "pair_span_pairs_checked": 0,
        }
    residual_class_bound = (
        residual_slots + math.comb(nullity, 2) - len(long_lines)
        if nullity >= 0
        else -1
    )
    if nullity > 2 and residual_class_bound < len(residual_classes):
        return {
            "status": "no_width_two_basis",
            "reason": "long_line_residual_class_bound",
            "candidate_classes": None,
            "residual_subsets_total": residual_subsets_total,
            "residual_subsets_checked": 0,
            "independent_basis_candidates": 0,
            "endpoint_subsets_checked": 0,
            "endpoint_independent_subsets": 0,
            "endpoint_line_compatible_subsets": 0,
            "domain_values_tried": 0,
            "pair_span_pairs_checked": 0,
        }

    residual_subsets_checked = 0
    independent_basis_candidates = 0
    endpoint_subsets_checked = 0
    endpoint_independent_subsets = 0
    endpoint_line_compatible_subsets = 0
    domain_values_tried = 0
    for residual_choice in itertools.combinations(
        residual_classes,
        residual_slots,
    ):
        residual_subsets_checked += 1
        if not set(required_residual_classes).issubset(residual_choice):
            continue
        full_reference = tuple(layout["reference_classes"]) + tuple(
            residual_choice
        )
        if _vector_rank(
            tuple(class_vectors[index] for index in full_reference)
        ) != nullity:
            continue
        independent_basis_candidates += 1
        completion = _complete_long_line_endpoints(
            geometry,
            nullity,
            residual_choice,
            layout,
        )
        endpoint_subsets_checked += completion["endpoint_subsets_checked"]
        endpoint_independent_subsets += completion[
            "endpoint_independent_subsets"
        ]
        endpoint_line_compatible_subsets += completion[
            "endpoint_line_compatible_subsets"
        ]
        domain_values_tried += completion["domain_values_tried"]
        candidate_classes = completion["candidate_classes"]
        if candidate_classes is None:
            continue
        return {
            "status": "width_two",
            "reason": "long_line_class_coverage",
            "candidate_classes": candidate_classes,
            "residual_subsets_total": residual_subsets_total,
            "residual_subsets_checked": residual_subsets_checked,
            "independent_basis_candidates": independent_basis_candidates,
            "endpoint_subsets_checked": endpoint_subsets_checked,
            "endpoint_independent_subsets": endpoint_independent_subsets,
            "endpoint_line_compatible_subsets": endpoint_line_compatible_subsets,
            "domain_values_tried": domain_values_tried,
            "pair_span_pairs_checked": 0,
            "completion": completion,
        }
    return {
        "status": "no_width_two_basis",
        "reason": "long_line_basis_search_exhausted",
        "candidate_classes": None,
        "residual_subsets_total": residual_subsets_total,
        "residual_subsets_checked": residual_subsets_checked,
        "independent_basis_candidates": independent_basis_candidates,
        "endpoint_subsets_checked": endpoint_subsets_checked,
        "endpoint_independent_subsets": endpoint_independent_subsets,
        "endpoint_line_compatible_subsets": endpoint_line_compatible_subsets,
        "domain_values_tried": domain_values_tried,
        "pair_span_pairs_checked": 0,
    }


def _long_line_constraints(
    geometry: dict[str, Any],
    nullity: int,
) -> dict[str, Any]:
    """Find the basis classes forced by intersecting coordinate lines."""

    class_indices = geometry["class_indices"]
    class_vectors = geometry["class_vectors"]
    class_columns = geometry["class_columns"]
    long_lines = geometry["long_lines"]
    line_intersections: list[dict[str, Any]] = []
    forced_classes: set[int] = set()
    for left_index, right_index in itertools.combinations(
        range(len(long_lines)), 2
    ):
        left_line = long_lines[left_index]
        right_line = long_lines[right_index]
        left_vector = class_vectors[left_line[0]]
        right_vector = class_vectors[left_line[1]]
        other_left_vector = class_vectors[right_line[0]]
        other_right_vector = class_vectors[right_line[1]]
        if _vector_rank(
            (
                left_vector,
                right_vector,
                other_left_vector,
                other_right_vector,
            )
        ) != 3:
            continue
        intersection = _subspace_intersection_vector(
            left_vector,
            right_vector,
            other_left_vector,
            other_right_vector,
        )
        key = _projective_key(intersection or ())
        class_index = class_indices.get(key) if key is not None else None
        if class_index is not None:
            forced_classes.add(class_index)
        line_intersections.append(
            {
                "lines": [left_index + 1, right_index + 1],
                "class": None if class_index is None else class_index + 1,
                "column": (
                    None if class_index is None else class_columns[class_index][0]
                ),
            }
        )

    forced_sorted = sorted(forced_classes)
    forced_rank = _vector_rank(
        tuple(class_vectors[index] for index in forced_sorted)
    )
    forced_by_line = [
        sorted(set(line).intersection(forced_classes))
        for line in long_lines
    ]
    reason: str | None = None
    if any(item["class"] is None for item in line_intersections):
        reason = "unrepresented_long_line_intersection"
    elif len(forced_sorted) > nullity:
        reason = "too_many_forced_classes"
    elif forced_rank < len(forced_sorted):
        reason = "dependent_forced_classes"
    elif any(len(items) > 2 for items in forced_by_line):
        reason = "too_many_forced_classes_on_long_line"

    return {
        "line_intersections": line_intersections,
        "forced_classes": forced_sorted,
        "forced_rank": forced_rank,
        "forced_classes_per_long_line": forced_by_line,
        "reason": reason,
    }


def _prepare_long_line_layout(
    geometry: dict[str, Any],
    nullity: int,
    constraints: dict[str, Any],
) -> dict[str, Any]:
    """Derive the independent reference axes forced by long lines."""

    class_vectors = geometry["class_vectors"]
    long_lines = geometry["long_lines"]
    forced_classes = tuple(constraints["forced_classes"])
    forced_set = set(forced_classes)
    one_lines: list[dict[str, Any]] = []
    zero_lines: list[dict[str, Any]] = []
    for line_index, line in enumerate(long_lines):
        line_forced = sorted(set(line).intersection(forced_set))
        if len(line_forced) > 2:
            return {
                "reason": "too_many_forced_classes_on_long_line",
            }
        if len(line_forced) == 2:
            continue
        if len(line_forced) == 1:
            reference = next(
                class_index
                for class_index in line
                if class_index not in forced_set
            )
            one_lines.append(
                {
                    "line_index": line_index,
                    "line": line,
                    "parent": line_forced[0],
                    "reference": reference,
                    "variable": len(one_lines),
                }
            )
        else:
            zero_lines.append(
                {
                    "line_index": line_index,
                    "line": line,
                    "references": (line[0], line[1]),
                }
            )

    reference_classes = list(forced_classes)
    reference_classes.extend(
        record["reference"] for record in one_lines
    )
    for record in zero_lines:
        reference_classes.extend(record["references"])
    long_line_union = sorted(
        {class_index for line in long_lines for class_index in line}
    )
    long_line_rank = _vector_rank(
        tuple(class_vectors[index] for index in long_line_union)
    )
    expected_long_rank = (
        len(forced_classes)
        + len(one_lines)
        + 2 * len(zero_lines)
    )
    if long_line_rank != expected_long_rank:
        return {
            "reason": "long_line_rank_decomposition_failed",
        }
    if len(set(reference_classes)) != len(reference_classes):
        return {
            "reason": "long_line_reference_axis_reused",
        }
    if _vector_rank(
        tuple(class_vectors[index] for index in reference_classes)
    ) != long_line_rank:
        return {
            "reason": "long_line_reference_basis_dependent",
        }
    if long_line_rank > nullity:
        return {
            "reason": "long_line_rank_exceeds_nullity",
        }
    long_line_union_set = set(long_line_union)
    residual_classes = [
        index
        for index in range(len(class_vectors))
        if index not in long_line_union_set
    ]
    residual_slots = nullity - long_line_rank
    if residual_slots < 0:
        return {
            "reason": "long_line_rank_exceeds_nullity",
        }
    return {
        "reason": None,
        "forced_classes": forced_classes,
        "one_lines": one_lines,
        "zero_lines": zero_lines,
        "reference_classes": reference_classes,
        "long_line_union": long_line_union,
        "long_line_rank": long_line_rank,
        "residual_classes": residual_classes,
        "residual_slots": residual_slots,
    }


def _basis_coordinates(
    basis: Sequence[Sequence[Fraction]],
    vector: Sequence[Fraction],
) -> tuple[Fraction, ...]:
    """Return exact coordinates of a vector in a full-rank basis."""

    dimension = len(basis)
    if len(vector) != dimension or any(
        len(item) != dimension for item in basis
    ):
        raise AssertionError("basis coordinates have inconsistent dimensions")
    if dimension == 0:
        if any(vector):
            raise AssertionError(
                "nonzero vector has no zero-dimensional coordinates"
            )
        return ()
    augmented = [
        [
            basis[column][row]
            for column in range(dimension)
        ]
        + [vector[row]]
        for row in range(dimension)
    ]
    reduced, pivots, _ = _rref(augmented)
    if pivots != tuple(range(dimension)):
        raise AssertionError("basis coordinates require a full-rank basis")
    return tuple(reduced[row][-1] for row in range(dimension))


def _span_coordinates(
    basis: Sequence[Sequence[Fraction]],
    vector: Sequence[Fraction],
) -> tuple[Fraction, ...]:
    """Return exact coordinates in an independent, possibly partial span."""

    span_dimension = len(basis)
    ambient_dimension = len(vector)
    if any(len(item) != ambient_dimension for item in basis):
        raise AssertionError("span coordinates have inconsistent dimensions")
    if span_dimension == 0:
        if any(vector):
            raise AssertionError(
                "nonzero vector is outside the zero-dimensional span"
            )
        return ()
    augmented = [
        [
            basis[column][row]
            for column in range(span_dimension)
        ]
        + [vector[row]]
        for row in range(ambient_dimension)
    ]
    reduced, pivots, _ = _rref(augmented)
    if pivots != tuple(range(span_dimension)):
        raise AssertionError("vector is outside the supplied span")
    return tuple(reduced[row][-1] for row in range(span_dimension))


def _solve_affine_domains(
    domains: Sequence[Sequence[Fraction | int]],
    unary: Sequence[tuple[int, Fraction | int]] = (),
    binary: Sequence[
        tuple[int, int, Fraction | int, Fraction | int, Fraction | int]
    ] = (),
) -> tuple[tuple[Fraction, ...] | None, int]:
    """Solve finite exact unary/binary affine domains by propagation."""

    normalized_domains = [
        tuple(sorted({Fraction(value) for value in domain}))
        for domain in domains
    ]
    variable_count = len(normalized_domains)
    unary_values: dict[int, list[Fraction]] = {}
    for variable, raw_value in unary:
        if not 0 <= variable < variable_count:
            raise CubicKernelDecisionError(
                "unary affine variable is out of range"
            )
        unary_values.setdefault(variable, []).append(Fraction(raw_value))

    adjacency: list[
        list[tuple[int, Fraction, Fraction, Fraction]]
    ] = [[] for _ in range(variable_count)]
    for left, right, raw_left, raw_right, raw_constant in binary:
        if (
            not 0 <= left < variable_count
            or not 0 <= right < variable_count
            or left == right
        ):
            raise CubicKernelDecisionError(
                "binary affine variables must be distinct and in range"
            )
        left_coefficient = Fraction(raw_left)
        right_coefficient = Fraction(raw_right)
        constant = Fraction(raw_constant)
        if not left_coefficient or not right_coefficient:
            raise CubicKernelDecisionError(
                "binary affine coefficients must be nonzero"
            )
        adjacency[left].append(
            (right, left_coefficient, right_coefficient, constant)
        )
        adjacency[right].append(
            (left, right_coefficient, left_coefficient, constant)
        )

    allowed_domains: list[tuple[Fraction, ...]] = []
    for variable, domain in enumerate(normalized_domains):
        required = unary_values.get(variable, [])
        allowed_domains.append(
            tuple(
                value
                for value in domain
                if all(value == required_value for required_value in required)
            )
        )
    if any(not domain for domain in allowed_domains):
        return None, 0

    components: list[tuple[int, ...]] = []
    visited: set[int] = set()
    for start in range(variable_count):
        if start in visited:
            continue
        members: list[int] = []
        frontier = [start]
        visited.add(start)
        while frontier:
            variable = frontier.pop()
            members.append(variable)
            for other, _, _, _ in adjacency[variable]:
                if other not in visited:
                    visited.add(other)
                    frontier.append(other)
        components.append(tuple(sorted(members)))

    assignment: list[Fraction | None] = [None] * variable_count
    root_attempts = 0
    for component_members in components:
        root = component_members[0]
        found: dict[int, Fraction] | None = None
        for root_value in allowed_domains[root]:
            root_attempts += 1
            local: dict[int, Fraction] = {root: root_value}
            frontier = [root]
            consistent = True
            while frontier and consistent:
                variable = frontier.pop()
                value = local[variable]
                for other, own, other_coefficient, constant in (
                    adjacency[variable]
                ):
                    implied = (constant - own * value) / other_coefficient
                    if implied not in allowed_domains[other]:
                        consistent = False
                        break
                    previous = local.get(other)
                    if previous is not None:
                        if previous != implied:
                            consistent = False
                            break
                    else:
                        local[other] = implied
                        frontier.append(other)
            if consistent and len(local) == len(component_members):
                found = local
                break
        if found is None:
            return None, root_attempts
        for variable, value in found.items():
            assignment[variable] = value

    if any(value is None for value in assignment):
        raise AssertionError("affine solver left a variable unassigned")
    return tuple(value for value in assignment if value is not None), root_attempts


def _complete_long_line_endpoints(
    geometry: dict[str, Any],
    nullity: int,
    residual_choice: Sequence[int],
    layout: dict[str, Any],
) -> dict[str, Any]:
    """Complete one residual basis with exact off-line support constraints."""

    class_vectors = geometry["class_vectors"]
    forced_classes = tuple(layout["forced_classes"])
    one_lines = layout["one_lines"]
    zero_lines = layout["zero_lines"]
    reference_classes = tuple(layout["reference_classes"])

    def failure(reason: str, **extra: Any) -> dict[str, Any]:
        return {
            "candidate_classes": None,
            "reason": reason,
            "endpoint_subsets_checked": 1,
            "endpoint_independent_subsets": 0,
            "endpoint_line_compatible_subsets": 0,
            "domain_values_tried": 0,
            **extra,
        }

    if len(residual_choice) != nullity - layout["long_line_rank"]:
        return failure("residual_basis_size_mismatch")
    if len(set(residual_choice)) != len(residual_choice):
        return failure("residual_basis_repeated_class")
    full_reference_classes = reference_classes + tuple(residual_choice)
    if len(set(full_reference_classes)) != len(full_reference_classes):
        return failure("residual_basis_reuses_long_line_axis")
    if _vector_rank(
        tuple(class_vectors[index] for index in full_reference_classes)
    ) != nullity:
        return failure("residual_basis_dependent_modulo_long_lines")
    reference_vectors = tuple(
        class_vectors[index] for index in full_reference_classes
    )
    coordinates = {
        class_index: _basis_coordinates(
            reference_vectors,
            class_vectors[class_index],
        )
        for class_index in range(len(class_vectors))
    }

    h_count = len(forced_classes)
    one_count = len(one_lines)
    zero_offset = h_count + one_count
    residual_offset = zero_offset + 2 * len(zero_lines)
    h_positions = {
        class_index: position
        for position, class_index in enumerate(forced_classes)
    }

    zero_selected: list[int] = []
    required_zero_directions: list[list[tuple[Fraction, ...]]] = []
    for zero_index, record in enumerate(zero_lines):
        offset = zero_offset + 2 * zero_index
        direction_to_class: dict[tuple[Fraction, ...], int] = {}
        for class_index in record["line"]:
            direction = _projective_key(
                coordinates[class_index][offset : offset + 2]
            )
            if direction is None:
                return failure("isolated_line_class_has_zero_projection")
            direction_to_class.setdefault(direction, class_index)
        required: set[tuple[Fraction, ...]] = set()
        for class_index in layout["residual_classes"]:
            direction = _projective_key(
                coordinates[class_index][offset : offset + 2]
            )
            if direction is None:
                continue
            if direction not in direction_to_class:
                return failure("isolated_projection_unrepresented")
            required.add(direction)
        if len(required) > 2:
            return failure("too_many_isolated_projection_directions")
        selected = [
            direction_to_class[direction]
            for direction in sorted(required)
        ]
        for class_index in record["line"]:
            if len(selected) == 2:
                break
            if class_index not in selected:
                selected.append(class_index)
        if len(selected) != 2:
            return failure("isolated_line_has_insufficient_classes")
        zero_selected.extend(selected)
        required_zero_directions.append(sorted(required))

    domains: list[tuple[Fraction, ...]] = []
    one_parameter_classes: list[dict[Fraction, int]] = []
    for record in one_lines:
        parent = record["parent"]
        reference = record["reference"]
        parameters: dict[Fraction, int] = {}
        for class_index in record["line"]:
            if class_index == parent:
                continue
            left_coefficient, right_coefficient = _span_coordinates(
                (
                    class_vectors[reference],
                    class_vectors[parent],
                ),
                class_vectors[class_index],
            )
            if not left_coefficient:
                return failure("one_endpoint_parameter_at_infinity")
            parameters[right_coefficient / left_coefficient] = class_index
        if not parameters:
            return failure("one_endpoint_domain_empty")
        one_parameter_classes.append(parameters)
        domains.append(tuple(sorted(parameters)))

    unary: list[tuple[int, Fraction]] = []
    binary: list[
        tuple[int, int, Fraction, Fraction, Fraction]
    ] = []
    for class_index in layout["residual_classes"]:
        vector_coordinates = coordinates[class_index]
        active_by_parent: dict[
            int, list[tuple[int, Fraction]]
        ] = {}
        active_leaf_count = 0
        for record in one_lines:
            leaf_value = vector_coordinates[
                h_count + record["variable"]
            ]
            if not leaf_value:
                continue
            active_leaf_count += 1
            parent_position = h_positions[record["parent"]]
            active_by_parent.setdefault(parent_position, []).append(
                (record["variable"], leaf_value)
            )
        zero_support = sum(
            _projective_key(
                vector_coordinates[
                    zero_offset + 2 * zero_index
                    : zero_offset + 2 * zero_index + 2
                ]
            )
            is not None
            for zero_index in range(len(zero_lines))
        )
        residual_support = sum(
            value != 0
            for value in vector_coordinates[residual_offset:]
        )
        fixed_support = zero_support + residual_support + sum(
            value != 0
            for parent_position, value in enumerate(
                vector_coordinates[:h_count]
            )
            if parent_position not in active_by_parent
        )
        if active_leaf_count > 2:
            return failure("residual_has_too_many_active_one_lines")
        if active_leaf_count == 2:
            if fixed_support:
                return failure("residual_support_budget_exhausted")
            for parent_position, items in active_by_parent.items():
                constant = vector_coordinates[parent_position]
                if len(items) == 1:
                    variable, coefficient = items[0]
                    unary.append((variable, constant / coefficient))
                elif len(items) == 2:
                    first, second = items
                    binary.append(
                        (
                            first[0],
                            second[0],
                            first[1],
                            second[1],
                            constant,
                        )
                    )
                else:
                    return failure("residual_parent_has_too_many_leaves")
        elif active_leaf_count == 1:
            if fixed_support > 1:
                return failure("residual_support_exceeds_two")
            if fixed_support == 1:
                parent_position, items = next(
                    iter(active_by_parent.items())
                )
                if len(items) != 1:
                    return failure("residual_parent_has_too_many_leaves")
                variable, coefficient = items[0]
                unary.append(
                    (
                        variable,
                        vector_coordinates[parent_position] / coefficient,
                    )
                )
        elif fixed_support > 2:
            return failure("residual_support_exceeds_two")

    assignment, domain_values_tried = _solve_affine_domains(
        domains,
        unary,
        binary,
    )
    if assignment is None:
        return failure(
            "affine_endpoint_constraints_unsatisfied",
            domain_values_tried=domain_values_tried,
        )
    one_selected = [
        one_parameter_classes[variable][assignment[variable]]
        for variable in range(len(one_lines))
    ]
    selected_classes = tuple(
        sorted(
            tuple(forced_classes)
            + tuple(one_selected)
            + tuple(zero_selected)
            + tuple(residual_choice)
        )
    )
    if len(selected_classes) != nullity:
        return failure("completed_basis_has_wrong_size")
    if len(set(selected_classes)) != len(selected_classes):
        return failure("completed_basis_repeated_class")
    selected_vectors = tuple(
        class_vectors[index] for index in selected_classes
    )
    if _vector_rank(selected_vectors) != nullity:
        return failure("completed_basis_is_dependent")
    support_by_class: dict[int, int] = {}
    for class_index, vector in enumerate(class_vectors):
        support = sum(
            value != 0
            for value in _basis_coordinates(selected_vectors, vector)
        )
        support_by_class[class_index] = support
        if support > 2:
            return failure(
                "completed_basis_support_exceeds_two",
                offending_class=class_index,
                offending_support=support,
                support_by_class=support_by_class,
                domain_values_tried=domain_values_tried,
            )
    return {
        "candidate_classes": selected_classes,
        "reason": "affine_endpoint_completion",
        "endpoint_subsets_checked": 1,
        "endpoint_independent_subsets": 1,
        "endpoint_line_compatible_subsets": 1,
        "domain_values_tried": domain_values_tried,
        "domains": domains,
        "unary_constraints": unary,
        "binary_constraints": binary,
        "reference_classes": list(reference_classes),
        "one_endpoint_classes": one_selected,
        "zero_endpoint_classes": zero_selected,
        "required_zero_directions": required_zero_directions,
        "support_by_class": support_by_class,
    }


def cubic_kernel_width_two_line_profile(
    formula: Sequence[Sequence[int]],
) -> dict[str, Any]:
    """Apply sound long-line constraints and exact nullity-three search.

    A non-coordinate rank-two subspace has at most three distinct
    two-sparse projective points.  Consequently, every observed projective
    line containing at least four kernel-coordinate classes must be a
    coordinate line in any width-two basis.  The resulting intersection
    constraints are necessary for every nullity, while class-pair coverage
    is complete when the nullity is at most three.

    ``status == "unresolved"`` is deliberately not a negative result: it
    means that residual basis search is still required.
    """

    canonical = canonical_cubic_formula(formula)
    system = _system(canonical)
    size = len(canonical)
    rank = len(system["pivot_columns_zero_based"])
    nullity = len(system["free_columns_zero_based"])
    geometry = _projective_geometry(system, size)
    class_vectors = geometry["class_vectors"]
    class_columns = geometry["class_columns"]
    column_classes = geometry["column_classes"]
    long_lines = geometry["long_lines"]

    constraints = _long_line_constraints(geometry, nullity)
    line_intersections = constraints["line_intersections"]
    forced_sorted = constraints["forced_classes"]
    forced_rank = constraints["forced_rank"]
    forced_by_line = constraints["forced_classes_per_long_line"]
    reason = constraints["reason"]

    candidate_columns: list[int] | None = None
    candidate_reason: str | None = None
    class_triples_checked = 0
    eligible_class_triples = 0
    pair_span_pairs_checked = 0
    if reason is None and nullity <= 2:
        candidate_columns = [
            column + 1 for column in system["free_columns_zero_based"]
        ]
        candidate_reason = "nullity_at_most_two"
    elif reason is None and nullity == 3:
        forced_set = frozenset(forced_sorted)
        long_line_sets = tuple(frozenset(line) for line in long_lines)
        eligible_triples: list[tuple[int, int, int]] = []
        for chosen in itertools.combinations(range(len(class_vectors)), 3):
            class_triples_checked += 1
            chosen_set = frozenset(chosen)
            if not forced_set.issubset(chosen_set):
                continue
            if any(
                len(chosen_set.intersection(line)) != 2
                for line in long_line_sets
            ):
                continue
            eligible_triples.append(chosen)
        eligible_class_triples = len(eligible_triples)
        pair_keys = sorted(
            {
                pair
                for chosen in eligible_triples
                for pair in itertools.combinations(chosen, 2)
            }
        )
        pair_span_masks = _class_pair_span_masks(
            class_vectors,
            pair_keys,
        )
        pair_span_pairs_checked = len(pair_span_masks)
        full_class_mask = (1 << len(class_vectors)) - 1
        for chosen in eligible_triples:
            if _vector_rank(
                tuple(class_vectors[index] for index in chosen)
            ) != 3:
                continue
            covered = 0
            for pair in itertools.combinations(chosen, 2):
                covered |= pair_span_masks[pair]
            if covered != full_class_mask:
                continue
            candidate_columns = sorted(
                class_columns[index][0] for index in chosen
            )
            candidate_reason = "nullity_three_class_coverage"
            break
        if candidate_columns is None:
            reason = "nullity_three_class_coverage_exhausted"
    elif reason is None and len(forced_sorted) == nullity:
        candidate_columns = sorted(
            class_columns[index][0] for index in forced_sorted
        )
        candidate_reason = "forced_basis"
    elif reason is None:
        reason = "residual_basis_search"

    certificate: dict[str, Any] | None = None
    status = "unresolved"
    if reason is not None and reason != "residual_basis_search":
        status = "no_width_two_basis"
    elif candidate_columns is not None:
        matrix = tuple(
            tuple(
                int(variable in clause)
                for variable in range(1, size + 1)
            )
            for clause in canonical
        )
        certificate = verify_cubic_width_two_basis(
            matrix,
            candidate_columns,
        )
        if not certificate["accepted"]:
            if candidate_reason == "forced_basis":
                status = "no_width_two_basis"
                reason = "forced_basis_fails_support_bound"
            else:
                raise AssertionError(
                    "structural width-two candidate failed exact verification"
                )
        else:
            status = "width_two"
            reason = candidate_reason

    return {
        "matrix_size": size,
        "rank": rank,
        "nullity": nullity,
        "classes": [
            {
                "class": index + 1,
                "columns": columns,
                "representative_column": columns[0],
                "vector": [
                    _fraction_text(value)
                    for value in class_vectors[index]
                ],
            }
            for index, columns in enumerate(class_columns)
        ],
        "column_classes": [
            None if index is None else index + 1
            for index in column_classes
        ],
        "long_lines": [
            {
                "classes": [index + 1 for index in line],
                "columns": [class_columns[index][0] for index in line],
            }
            for line in long_lines
        ],
        "line_intersections": line_intersections,
        "forced_classes": [index + 1 for index in forced_sorted],
        "forced_columns": [
            class_columns[index][0] for index in forced_sorted
        ],
        "forced_rank": forced_rank,
        "forced_classes_per_long_line": [
            [index + 1 for index in items]
            for items in forced_by_line
        ],
        "class_triples_checked": class_triples_checked,
        "eligible_class_triples": eligible_class_triples,
        "pair_span_pairs_checked": pair_span_pairs_checked,
        "candidate_free_columns": candidate_columns,
        "certificate": certificate,
        "status": status,
        "reason": reason,
    }


def cubic_kernel_short_line_basis(
    formula: Sequence[Sequence[int]],
) -> dict[str, Any]:
    """Decide internal width two under the all-short-line hypothesis.

    If every observed projective line has at most three classes, a width-two
    basis of rank ``k`` can cover at most one nonbasis class per basis pair.
    Therefore the exact class universe is bounded by
    ``k + binomial(k, 2)``.  The search is fixed-parameter in ``k`` and
    returns ``unresolved`` rather than applying the bound to long-line input.
    """

    canonical = canonical_cubic_formula(formula)
    system = _system(canonical)
    size = len(canonical)
    rank = len(system["pivot_columns_zero_based"])
    nullity = len(system["free_columns_zero_based"])
    geometry = _projective_geometry(system, size)
    class_vectors = geometry["class_vectors"]
    class_columns = geometry["class_columns"]
    column_classes = geometry["column_classes"]
    lines = geometry["lines"]
    long_lines = geometry["long_lines"]
    mandatory_classes = _mandatory_basis_classes(geometry)
    mandatory_rank = _vector_rank(
        tuple(class_vectors[index] for index in mandatory_classes)
    )
    class_count = len(class_vectors)
    class_bound = nullity + math.comb(nullity, 2)
    class_subsets_total = (
        math.comb(class_count, nullity)
        if class_count >= nullity
        else 0
    )
    short_line_hypothesis = not long_lines
    candidate_columns: list[int] | None = None
    candidate_reason: str | None = None
    status = "unresolved"
    reason: str | None = None
    class_subsets_checked = 0
    independent_class_bases = 0
    pair_span_pairs_checked = 0
    pair_span_masks: dict[tuple[int, int], int] = {}

    if nullity <= 2:
        candidate_columns = [
            column + 1 for column in system["free_columns_zero_based"]
        ]
        candidate_reason = "nullity_at_most_two"
    elif not short_line_hypothesis:
        reason = "long_line_outside_short_line_method"
    elif class_count > class_bound:
        status = "no_width_two_basis"
        reason = "short_line_class_bound"
    else:
        pair_keys = list(
            itertools.combinations(range(class_count), 2)
        )
        pair_span_masks = _class_pair_span_masks(
            class_vectors,
            pair_keys,
        )
        pair_span_pairs_checked = len(pair_span_masks)
        full_class_mask = (1 << class_count) - 1
        if 0 <= nullity <= class_count:
            for chosen in itertools.combinations(
                range(class_count), nullity
            ):
                class_subsets_checked += 1
                if _vector_rank(
                    tuple(class_vectors[index] for index in chosen)
                ) != nullity:
                    continue
                independent_class_bases += 1
                if not set(mandatory_classes).issubset(chosen):
                    continue
                covered = sum(1 << index for index in chosen)
                for pair in itertools.combinations(chosen, 2):
                    covered |= pair_span_masks[pair]
                if covered != full_class_mask:
                    continue
                candidate_columns = sorted(
                    class_columns[index][0] for index in chosen
                )
                candidate_reason = "short_line_class_coverage"
                break
        if candidate_columns is None:
            status = "no_width_two_basis"
            reason = "short_line_class_search_exhausted"

    certificate: dict[str, Any] | None = None
    if candidate_columns is not None:
        matrix = tuple(
            tuple(
                int(variable in clause)
                for variable in range(1, size + 1)
            )
            for clause in canonical
        )
        certificate = verify_cubic_width_two_basis(
            matrix,
            candidate_columns,
        )
        if not certificate["accepted"]:
            raise AssertionError(
                "short-line candidate failed exact width-two verification"
            )
        status = "width_two"
        reason = candidate_reason

    return {
        "matrix_size": size,
        "rank": rank,
        "nullity": nullity,
        "class_count": class_count,
        "class_bound": class_bound,
        "mandatory_classes": [index + 1 for index in mandatory_classes],
        "mandatory_class_count": len(mandatory_classes),
        "mandatory_class_rank": mandatory_rank,
        "mandatory_class_rejects": (
            len(mandatory_classes) > nullity
            or mandatory_rank < len(mandatory_classes)
        ),
        "short_line_hypothesis": short_line_hypothesis,
        "maximum_observed_line_size": max(
            (len(line) for line in lines),
            default=0,
        ),
        "classes": [
            {
                "class": index + 1,
                "columns": columns,
                "representative_column": columns[0],
                "vector": [
                    _fraction_text(value)
                    for value in class_vectors[index]
                ],
            }
            for index, columns in enumerate(class_columns)
        ],
        "column_classes": [
            None if index is None else index + 1
            for index in column_classes
        ],
        "long_lines": [
            {
                "classes": [index + 1 for index in line],
                "columns": [class_columns[index][0] for index in line],
            }
            for line in long_lines
        ],
        "class_subsets_total": class_subsets_total,
        "class_subsets_checked": class_subsets_checked,
        "independent_class_bases": independent_class_bases,
        "pair_span_pairs_checked": pair_span_pairs_checked,
        "candidate_free_columns": candidate_columns,
        "certificate": certificate,
        "status": status,
        "reason": reason,
    }


def cubic_kernel_width_two_basis(
    formula: Sequence[Sequence[int]],
) -> dict[str, Any]:
    """Complete exact recognition of an internal width-two basis.

    Long lines are coordinate lines in every accepted basis.  Their
    remaining endpoint choices are represented by finite affine domains, and
    every residual basis is completed and audited exactly.  The only
    combinatorial search left here is the residual basis choice.
    """

    canonical = canonical_cubic_formula(formula)
    system = _system(canonical)
    size = len(canonical)
    rank = len(system["pivot_columns_zero_based"])
    nullity = len(system["free_columns_zero_based"])
    geometry = _projective_geometry(system, size)
    class_vectors = geometry["class_vectors"]
    class_columns = geometry["class_columns"]
    column_classes = geometry["column_classes"]
    lines = geometry["lines"]
    long_lines = geometry["long_lines"]
    mandatory_classes = _mandatory_basis_classes(geometry)
    mandatory_rank = _vector_rank(
        tuple(class_vectors[index] for index in mandatory_classes)
    )
    class_count = len(class_vectors)
    class_bound = nullity + math.comb(nullity, 2)

    if not long_lines:
        result = cubic_kernel_short_line_basis(canonical)
        result["method"] = "short_line_class_search"
        result["search_complete"] = True
        return result

    constraints = _long_line_constraints(geometry, nullity)
    forced_sorted = constraints["forced_classes"]
    long_line_union = sorted(
        {index for line in long_lines for index in line}
    )
    long_line_union_set = set(long_line_union)
    residual_classes = [
        index
        for index in range(class_count)
        if index not in long_line_union_set
    ]
    long_line_rank = _vector_rank(
        tuple(class_vectors[index] for index in long_line_union)
    )
    long_line_count = len(long_lines)
    residual_slots = nullity - long_line_rank
    residual_class_bound = (
        residual_slots + math.comb(nullity, 2) - long_line_count
        if nullity >= 0
        else -1
    )
    residual_subsets_total = (
        math.comb(len(residual_classes), residual_slots)
        if 0 <= residual_slots <= len(residual_classes)
        else 0
    )
    search = _width_two_geometry_basis(geometry, nullity)
    candidate_classes = search["candidate_classes"]
    candidate_columns: list[int] | None = None
    certificate: dict[str, Any] | None = None
    if candidate_classes is not None:
        candidate_columns = sorted(
            class_columns[index][0] for index in candidate_classes
        )
        matrix = tuple(
            tuple(
                int(variable in clause)
                for variable in range(1, size + 1)
            )
            for clause in canonical
        )
        certificate = verify_cubic_width_two_basis(
            matrix,
            candidate_columns,
        )
        if not certificate["accepted"]:
            raise AssertionError(
                "complete width-two candidate failed exact verification"
            )

    return {
        "matrix_size": size,
        "rank": rank,
        "nullity": nullity,
        "class_count": class_count,
        "class_bound": class_bound,
        "mandatory_classes": [index + 1 for index in mandatory_classes],
        "mandatory_class_count": len(mandatory_classes),
        "mandatory_class_rank": mandatory_rank,
        "mandatory_class_rejects": (
            len(mandatory_classes) > nullity
            or mandatory_rank < len(mandatory_classes)
        ),
        "short_line_hypothesis": False,
        "maximum_observed_line_size": max(
            (len(line) for line in lines),
            default=0,
        ),
        "classes": [
            {
                "class": index + 1,
                "columns": columns,
                "representative_column": columns[0],
                "vector": [
                    _fraction_text(value)
                    for value in class_vectors[index]
                ],
            }
            for index, columns in enumerate(class_columns)
        ],
        "column_classes": [
            None if index is None else index + 1
            for index in column_classes
        ],
        "long_lines": [
            {
                "classes": [index + 1 for index in line],
                "columns": [class_columns[index][0] for index in line],
            }
            for line in long_lines
        ],
        "line_intersections": constraints["line_intersections"],
        "forced_classes": [index + 1 for index in forced_sorted],
        "forced_columns": [
            class_columns[index][0] for index in forced_sorted
        ],
        "forced_rank": constraints["forced_rank"],
        "forced_classes_per_long_line": [
            [index + 1 for index in items]
            for items in constraints["forced_classes_per_long_line"]
        ],
        "long_line_count": long_line_count,
        "long_line_union": [index + 1 for index in long_line_union],
        "long_line_rank": long_line_rank,
        "residual_classes": [index + 1 for index in residual_classes],
        "residual_slots": residual_slots,
        "residual_class_bound": residual_class_bound,
        "endpoint_subsets_total": residual_subsets_total,
        "endpoint_subsets_checked": search[
            "endpoint_subsets_checked"
        ],
        "endpoint_independent_subsets": search[
            "endpoint_independent_subsets"
        ],
        "endpoint_line_compatible_subsets": search[
            "endpoint_line_compatible_subsets"
        ],
        "residual_subsets_total": search["residual_subsets_total"],
        "residual_subsets_checked": search[
            "residual_subsets_checked"
        ],
        "independent_basis_candidates": search[
            "independent_basis_candidates"
        ],
        "pair_span_pairs_checked": search["pair_span_pairs_checked"],
        "domain_values_tried": search["domain_values_tried"],
        "endpoint_search_mode": "affine_exact_completion",
        "endpoint_completions_checked": search[
            "endpoint_subsets_checked"
        ],
        "endpoint_completions_total": residual_subsets_total,
        "candidate_free_columns": candidate_columns,
        "certificate": certificate,
        "method": "long_line_endpoint_search",
        "search_complete": True,
        "status": search["status"],
        "reason": search["reason"],
    }


def verify_cubic_width_two_basis(
    matrix: Sequence[Sequence[int]],
    free_columns: Sequence[int],
    *,
    maximum_support: int = 2,
) -> dict[str, Any]:
    """Verify a sorted kernel-column basis for an input cubic matrix.

    The certificate ``free_columns`` is a basis of the kernel-coordinate
    columns.  Its complement is therefore passed to
    ``_system_for_pivot_basis`` as the primal column basis.
    """

    if (
        isinstance(maximum_support, bool)
        or not isinstance(maximum_support, int)
        or maximum_support < 0
    ):
        raise CubicKernelDecisionError(
            "maximum_support must be a nonnegative integer"
        )
    canonical_matrix = canonical_cubic_matrix(matrix)
    size = len(canonical_matrix)
    if (
        not isinstance(free_columns, Sequence)
        or isinstance(free_columns, (str, bytes))
        or any(
            isinstance(column, bool)
            or not isinstance(column, int)
            or not 1 <= column <= size
            for column in free_columns
        )
    ):
        raise CubicKernelDecisionError(
            "free_columns must contain valid one-based matrix indices"
        )
    normalized_free = tuple(free_columns)
    if normalized_free != tuple(sorted(normalized_free)):
        raise CubicKernelDecisionError("free_columns must be sorted")
    if len(set(normalized_free)) != len(normalized_free):
        raise CubicKernelDecisionError("free_columns must be distinct")

    formula = _formula_from_cubic_matrix(canonical_matrix)
    canonical_system = _system(formula)
    rank = len(canonical_system["pivot_columns_zero_based"])
    nullity = len(canonical_system["free_columns_zero_based"])
    if len(normalized_free) != nullity:
        raise CubicKernelDecisionError(
            f"free_columns must contain exactly {nullity} indices"
        )

    free_zero_based = tuple(column - 1 for column in normalized_free)
    free_set = set(free_zero_based)
    pivot_columns = tuple(
        column for column in range(size) if column not in free_set
    )
    canonical_kernel_columns = _kernel_coordinate_vectors(canonical_system, size)
    free_kernel_columns = tuple(
        canonical_kernel_columns[column] for column in free_zero_based
    )
    if _vector_rank(free_kernel_columns) != nullity:
        raise CubicKernelDecisionError(
            "free_columns do not form a kernel-coordinate basis"
        )

    # F is a basis in kernel-coordinate space; its complement is the primal
    # column basis required by _system_for_pivot_basis.
    basis_system = _system_for_pivot_basis(
        incidence_matrix(formula), pivot_columns
    )
    if basis_system is None:
        raise CubicKernelDecisionError(
            "the complement of free_columns is not a primal column basis"
        )
    basis_coordinate_columns = _kernel_coordinate_vectors(basis_system, size)
    basis_coordinate_supports = tuple(
        sum(value != 0 for value in vector)
        for vector in basis_coordinate_columns
    )
    for coordinate, column in enumerate(free_zero_based):
        expected = tuple(
            Fraction(int(index == coordinate)) for index in range(nullity)
        )
        if basis_coordinate_columns[column] != expected:
            raise AssertionError(
                "the primal-complement system did not normalize free columns"
            )

    canonical_kernel_basis = [
        [
            _fraction_text(canonical_kernel_columns[column][coordinate])
            for column in range(size)
        ]
        for coordinate in range(nullity)
    ]
    basis_coordinates = [
        [_fraction_text(value) for value in vector]
        for vector in basis_coordinate_columns
    ]

    observed_kernel_entry_bits = 1
    for vector in canonical_kernel_columns:
        for value in vector:
            observed_kernel_entry_bits = max(
                observed_kernel_entry_bits,
                abs(value.numerator).bit_length(),
                value.denominator.bit_length(),
            )
    observed_basis_coordinate_bits = 1
    for vector in basis_coordinate_columns:
        for value in vector:
            observed_basis_coordinate_bits = max(
                observed_basis_coordinate_bits,
                abs(value.numerator).bit_length(),
                value.denominator.bit_length(),
            )
    determinant_abs_bound = 3**rank
    effective_nullity = max(1, nullity)
    coordinate_abs_bound = (
        effective_nullity**effective_nullity
        * 3 ** (rank * effective_nullity)
    ) ** 2
    bit_bounds = {
        "determinant_abs_bound": f"3^{rank}",
        "kernel_entry_abs_bound": f"3^{rank}",
        "basis_coordinate_abs_bound": (
            f"(k^k * 3^(rank*k))^2, k={nullity}; use 1 for k=0"
        ),
        "kernel_entry_bit_bound": determinant_abs_bound.bit_length(),
        "basis_coordinate_bit_bound": coordinate_abs_bound.bit_length(),
        "observed_kernel_entry_bits": observed_kernel_entry_bits,
        "observed_basis_coordinate_bits": observed_basis_coordinate_bits,
    }
    if (
        observed_kernel_entry_bits > bit_bounds["kernel_entry_bit_bound"]
        or observed_basis_coordinate_bits
        > bit_bounds["basis_coordinate_bit_bound"]
    ):
        raise AssertionError("exact coordinates exceeded the cubic bit bound")

    zero_kernel_columns = [
        column + 1
        for column, vector in enumerate(canonical_kernel_columns)
        if not any(vector)
    ]
    projective_classes: dict[tuple[Fraction, ...], list[int]] = {}
    for column, vector in enumerate(canonical_kernel_columns):
        if not any(vector):
            continue
        first = next(value for value in vector if value != 0)
        key = tuple(value / first for value in vector)
        projective_classes.setdefault(key, []).append(column + 1)
    parallel_kernel_classes = [
        columns for columns in projective_classes.values() if len(columns) > 1
    ]

    return {
        "matrix": [list(row) for row in canonical_matrix],
        "matrix_size": size,
        "rank": rank,
        "nullity": nullity,
        "pivot_columns": [column + 1 for column in pivot_columns],
        "free_columns": list(normalized_free),
        "basis_invertible": True,
        "accepted": max(basis_coordinate_supports, default=0) <= maximum_support,
        "maximum_support_limit": maximum_support,
        "maximum_basis_coordinate_support": max(
            basis_coordinate_supports, default=0
        ),
        "basis_coordinate_supports": list(basis_coordinate_supports),
        "canonical_kernel_basis": canonical_kernel_basis,
        "basis_coordinates": basis_coordinates,
        "zero_kernel_columns": zero_kernel_columns,
        "parallel_kernel_classes": parallel_kernel_classes,
        "pivot_free_coefficients": [
            [_fraction_text(value) for value in row]
            for row in basis_system["pivot_free_coefficients"]
        ],
        "canonical_system_digest": canonical_system["system_digest"],
        "basis_system_digest": basis_system["system_digest"],
        "bit_bounds": bit_bounds,
    }


def cubic_kernel_zero_valid_basis(
    formula: Sequence[Sequence[int]],
    assignment: Sequence[int],
) -> dict[str, Any]:
    """Turn a satisfying assignment into a zero-valid dual ground-set basis.

    In an exact-one assignment, the incidence columns selected by the one
    variables have pairwise disjoint, nonempty row supports.  No nonzero kernel
    vector can therefore be supported only on those columns.  Coordinate
    projection onto the zero variables is injective on the kernel, so those
    coordinates contain a basis of the dual column matroid.
    """

    canonical = canonical_cubic_formula(formula)
    size = len(canonical)
    if (
        not isinstance(assignment, Sequence)
        or isinstance(assignment, (str, bytes))
        or len(assignment) != size
        or any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value not in (0, 1)
            for value in assignment
        )
    ):
        raise CubicKernelDecisionError(
            "assignment must contain exactly one Boolean integer per variable"
        )
    if not all(
        sum(assignment[variable - 1] for variable in clause) == 1
        for clause in canonical
    ):
        raise CubicKernelDecisionError(
            "assignment does not satisfy the cubic exact-one formula"
        )

    canonical_system = _system(canonical)
    nullity = len(canonical_system["free_columns_zero_based"])
    vectors = _kernel_coordinate_vectors(canonical_system, size)
    free_columns: list[int] = []
    free_vectors: list[tuple[Fraction, ...]] = []
    for column, value in enumerate(assignment):
        if value != 0:
            continue
        candidate_vectors = (*free_vectors, vectors[column])
        if _vector_rank(candidate_vectors) == len(candidate_vectors):
            free_columns.append(column)
            free_vectors.append(vectors[column])
            if len(free_columns) == nullity:
                break
    if len(free_columns) != nullity:
        raise AssertionError(
            "zero coordinates of an exact-one witness must span the dual"
        )

    free_set = set(free_columns)
    pivot_columns = tuple(
        column for column in range(size) if column not in free_set
    )
    system = _system_for_pivot_basis(incidence_matrix(canonical), pivot_columns)
    if system is None:
        raise AssertionError(
            "complement of a dual coordinate basis must be a column basis"
        )
    free_values = tuple(Fraction(-1) for _ in free_columns)
    vector = _candidate_vector(
        size,
        system["pivot_columns_zero_based"],
        system["free_columns_zero_based"],
        system["pivot_free_coefficients"],
        free_values,
    )
    expected = tuple(Fraction(3 * value - 1) for value in assignment)
    if vector != expected:
        raise AssertionError(
            "zero-valid basis did not reconstruct its exact-one witness"
        )

    supports = system["pivot_free_supports"]
    result = {
        "clauses": size,
        "variables": size,
        "rank": len(pivot_columns),
        "nullity": nullity,
        "zero_assignment_columns": sum(value == 0 for value in assignment),
        "zero_coordinate_rank": len(free_columns),
        "pivot_columns": [column + 1 for column in pivot_columns],
        "free_columns": [column + 1 for column in free_columns],
        "pivot_free_supports": list(supports),
        "maximum_pivot_free_support": max(supports, default=0),
        "reconstructed_kernel_vector": [int(value) for value in vector],
        "system_digest": system["system_digest"],
    }
    result["certificate_digest"] = hashlib.sha256(
        json.dumps(
            result, sort_keys=True, separators=(",", ":")
        ).encode("ascii")
    ).hexdigest()
    return result


def cubic_kernel_dual_triangle_profile(
    formula: Sequence[Sequence[int]],
) -> dict[str, Any]:
    """Return all size-at-most-three circuits of the dual column matroid.

    For a dual basis ``F``, an element outside ``F`` has coordinate support at
    most two exactly when its fundamental circuit is a loop, parallel pair, or
    triangle contained in ``F`` together with that element.  Enumerating these
    small circuits exposes the basis-independent local framing constraints; it
    does not solve the global basis-selection problem.
    """

    canonical = canonical_cubic_formula(formula)
    system = _system(canonical)
    vectors = _kernel_coordinate_vectors(system, len(canonical))
    singleton_ranks = tuple(_vector_rank((vector,)) for vector in vectors)
    loops = tuple(
        index for index, rank in enumerate(singleton_ranks) if rank == 0
    )
    parallel_pairs: list[tuple[int, int]] = []
    independent_pairs: set[tuple[int, int]] = set()
    for left, right in itertools.combinations(range(len(vectors)), 2):
        pair = (left, right)
        rank = _vector_rank((vectors[left], vectors[right]))
        if singleton_ranks[left] == singleton_ranks[right] == 1 and rank == 1:
            parallel_pairs.append(pair)
        elif rank == 2:
            independent_pairs.add(pair)

    triangles: list[tuple[int, int, int]] = []
    for triple in itertools.combinations(range(len(vectors)), 3):
        if not all(
            tuple(sorted(pair)) in independent_pairs
            for pair in itertools.combinations(triple, 2)
        ):
            continue
        if _vector_rank(tuple(vectors[index] for index in triple)) == 2:
            triangles.append(triple)

    small_circuit_degrees = [0] * len(vectors)
    for index in loops:
        small_circuit_degrees[index] += 1
    for pair in parallel_pairs:
        for index in pair:
            small_circuit_degrees[index] += 1
    for triple in triangles:
        for index in triple:
            small_circuit_degrees[index] += 1
    clause_sets = {tuple(variable - 1 for variable in clause) for clause in canonical}
    triangle_set = set(triangles)
    serialized = {
        "loops": [index + 1 for index in loops],
        "parallel_pairs": [
            [left + 1, right + 1] for left, right in parallel_pairs
        ],
        "triangles": [
            [first + 1, second + 1, third + 1]
            for first, second, third in triangles
        ],
    }
    return {
        "elements": len(vectors),
        "dual_rank": len(system["free_columns_zero_based"]),
        "loops": serialized["loops"],
        "parallel_pairs": serialized["parallel_pairs"],
        "triangles": serialized["triangles"],
        "loop_count": len(loops),
        "parallel_pair_count": len(parallel_pairs),
        "triangle_count": len(triangles),
        "small_circuit_count": (
            len(loops) + len(parallel_pairs) + len(triangles)
        ),
        "clause_cocircuit_triangles": len(clause_sets & triangle_set),
        "additional_triangles": len(triangle_set - clause_sets),
        "small_circuit_degree_histogram": {
            str(degree): small_circuit_degrees.count(degree)
            for degree in sorted(set(small_circuit_degrees))
        },
        "elements_without_small_circuit": [
            index + 1
            for index, degree in enumerate(small_circuit_degrees)
            if degree == 0
        ],
        "constraint_digest": hashlib.sha256(
            json.dumps(
                serialized, sort_keys=True, separators=(",", ":")
            ).encode("ascii")
        ).hexdigest(),
    }


def _basis_exchange_profile(
    *,
    size: int,
    canonical_basis: tuple[int, ...],
    records: dict[tuple[int, ...], tuple[int, int]],
) -> dict[str, Any]:
    """Analyze exact one-element exchanges among an enumerated basis set."""

    basis_set = set(records)
    adjacency = {basis: set() for basis in basis_set}
    edges: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    for basis in sorted(basis_set):
        selected = set(basis)
        for removed in basis:
            for added in range(size):
                if added in selected:
                    continue
                neighbor = tuple(sorted((selected - {removed}) | {added}))
                if neighbor not in basis_set or basis >= neighbor:
                    continue
                adjacency[basis].add(neighbor)
                adjacency[neighbor].add(basis)
                edges.append((basis, neighbor))

    optimum = min(width for width, _ in records.values())
    optimum_bases = {
        basis for basis, (width, _) in records.items() if width == optimum
    }
    distances = {basis: 0 for basis in optimum_bases}
    queue = deque(sorted(optimum_bases))
    while queue:
        basis = queue.popleft()
        for neighbor in sorted(adjacency[basis]):
            if neighbor in distances:
                continue
            distances[neighbor] = distances[basis] + 1
            queue.append(neighbor)
    if len(distances) != len(records):
        raise AssertionError("matroid basis-exchange graph must be connected")

    strict_descent_reachable = set(optimum_bases)
    for width in sorted({value[0] for value in records.values()}):
        if width == optimum:
            continue
        for basis in sorted(basis_set):
            if records[basis][0] != width:
                continue
            if any(
                records[neighbor][0] < width
                and neighbor in strict_descent_reachable
                for neighbor in adjacency[basis]
            ):
                strict_descent_reachable.add(basis)

    nonincreasing_reachable: set[tuple[int, ...]] = set()
    for width in sorted({value[0] for value in records.values()}):
        allowed = {
            basis for basis, (basis_width, _) in records.items()
            if basis_width <= width
        }
        reached = set(optimum_bases)
        frontier = deque(sorted(optimum_bases))
        while frontier:
            basis = frontier.popleft()
            for neighbor in sorted(adjacency[basis]):
                if neighbor not in allowed or neighbor in reached:
                    continue
                reached.add(neighbor)
                frontier.append(neighbor)
        nonincreasing_reachable.update(
            basis for basis in reached if records[basis][0] == width
        )

    nonglobal_local_minima = [
        basis
        for basis in sorted(basis_set)
        if records[basis][0] > optimum
        and not any(
            records[neighbor][0] < records[basis][0]
            for neighbor in adjacency[basis]
        )
    ]
    first_trap = nonglobal_local_minima[0] if nonglobal_local_minima else None
    graph_rows = [
        {
            "basis": [column + 1 for column in basis],
            "width": records[basis][0],
            "uncovered": records[basis][1],
            "neighbors": [
                [column + 1 for column in neighbor]
                for neighbor in sorted(adjacency[basis])
            ],
        }
        for basis in sorted(basis_set)
    ]
    return {
        "basis_nodes": len(records),
        "exchange_edges": len(edges),
        "connected": True,
        "optimum_width": optimum,
        "optimum_basis_nodes": len(optimum_bases),
        "canonical_distance_to_optimum": distances[canonical_basis],
        "maximum_distance_to_optimum": max(distances.values(), default=0),
        "distance_to_optimum_histogram": {
            str(distance): list(distances.values()).count(distance)
            for distance in sorted(set(distances.values()))
        },
        "exchange_degree_histogram": {
            str(degree): sum(
                len(neighbors) == degree for neighbors in adjacency.values()
            )
            for degree in sorted({len(neighbors) for neighbors in adjacency.values()})
        },
        "nonglobal_local_minima": len(nonglobal_local_minima),
        "strict_descent_reaches_optimum": len(strict_descent_reachable),
        "nonincreasing_reaches_optimum": len(nonincreasing_reachable),
        "first_nonglobal_local_minimum": (
            None
            if first_trap is None
            else {
                "pivot_columns": [column + 1 for column in first_trap],
                "free_columns": [
                    column + 1
                    for column in range(size)
                    if column not in first_trap
                ],
                "width": records[first_trap][0],
                "uncovered_pivots": records[first_trap][1],
            }
        ),
        "graph_digest": hashlib.sha256(
            json.dumps(
                graph_rows, sort_keys=True, separators=(",", ":")
            ).encode("ascii")
        ).hexdigest(),
    }


def cubic_kernel_basis_width(
    formula: Sequence[Sequence[int]],
    *,
    maximum_column_subsets: int = 1_000_000,
    analyze_basis_exchange: bool = False,
) -> dict[str, Any]:
    """Exactly minimize pivot support over all column bases.

    The maximum pivot-to-free support is one less than the largest
    fundamental cocircuit in the represented column matroid, or equivalently
    one less than the largest fundamental circuit in its dual. Optional
    exchange analysis records whether greedy single-basis pivots can reach an
    optimum. The exhaustive search is not a general polynomial-time basis
    finder.
    """

    if (
        isinstance(maximum_column_subsets, bool)
        or not isinstance(maximum_column_subsets, int)
        or maximum_column_subsets < 1
    ):
        raise CubicKernelDecisionError(
            "maximum_column_subsets must be a positive integer"
        )
    canonical = canonical_cubic_formula(formula)
    matrix = incidence_matrix(canonical)
    canonical_system = _system(canonical)
    size = len(canonical)
    rank = len(canonical_system["pivot_columns_zero_based"])
    column_subsets = math.comb(size, rank)
    if column_subsets > maximum_column_subsets:
        raise CubicKernelDecisionError(
            "exact basis-width search requires "
            f"{column_subsets} column subsets, exceeding the "
            f"{maximum_column_subsets} limit"
        )

    best_system: dict[str, Any] | None = None
    best_key: tuple[int, int, tuple[int, ...]] | None = None
    basis_count = 0
    basis_width_histogram: dict[int, int] = {}
    uncovered_histogram: dict[int, int] = {}
    basis_records: dict[tuple[int, ...], tuple[int, int]] = {}
    for pivot_columns in itertools.combinations(range(size), rank):
        system = _system_for_pivot_basis(matrix, pivot_columns)
        if system is None:
            continue
        basis_count += 1
        supports = system["pivot_free_supports"]
        width = max(supports, default=0)
        basis_width_histogram[width] = (
            basis_width_histogram.get(width, 0) + 1
        )
        uncovered = sum(support > 2 for support in supports)
        uncovered_histogram[uncovered] = (
            uncovered_histogram.get(uncovered, 0) + 1
        )
        if analyze_basis_exchange:
            basis_records[pivot_columns] = (width, uncovered)
        key = (
            width,
            sum(supports),
            pivot_columns,
        )
        if best_key is None or key < best_key:
            best_key = key
            best_system = system

    if best_system is None or best_key is None:
        raise AssertionError("a matrix RREF must expose at least one basis")

    canonical_supports = canonical_system["pivot_free_supports"]
    best_supports = best_system["pivot_free_supports"]
    witness = {
        "pivot_columns": [
            column + 1
            for column in best_system["pivot_columns_zero_based"]
        ],
        "free_columns": [
            column + 1
            for column in best_system["free_columns_zero_based"]
        ],
        "pivot_free_coefficients": [
            [_fraction_text(value) for value in row]
            for row in best_system["pivot_free_coefficients"]
        ],
        "pivot_free_supports": list(best_supports),
        "maximum_pivot_free_support": best_key[0],
        "total_pivot_free_support": best_key[1],
        "maximum_fundamental_cocircuit_size": best_key[0] + 1,
        "system_digest": best_system["system_digest"],
    }
    result = {
        "clauses": size,
        "variables": size,
        "rank": rank,
        "nullity": size - rank,
        "column_subsets_checked": column_subsets,
        "column_bases_found": basis_count,
        "basis_maximum_support_histogram": {
            str(width): basis_width_histogram[width]
            for width in sorted(basis_width_histogram)
        },
        "bases_at_optimum": basis_width_histogram[best_key[0]],
        "maximum_maximum_pivot_free_support": max(
            basis_width_histogram
        ),
        "exact_optimum": True,
        "canonical_pivot_columns": [
            column + 1
            for column in canonical_system["pivot_columns_zero_based"]
        ],
        "canonical_maximum_pivot_free_support": max(
            canonical_supports, default=0
        ),
        "minimum_maximum_pivot_free_support": best_key[0],
        "minimum_total_support_at_optimum": best_key[1],
        "improves_canonical_basis": (
            best_key[0] < max(canonical_supports, default=0)
        ),
        "bounded_support_2sat_basis_exists": best_key[0] <= 2,
        "bases_with_width_at_most_two": sum(
            count
            for width, count in basis_width_histogram.items()
            if width <= 2
        ),
        "minimum_uncovered_pivots": min(uncovered_histogram),
        "uncovered_pivot_count_histogram": {
            str(count): uncovered_histogram[count]
            for count in sorted(uncovered_histogram)
        },
        "basis_exchange": (
            _basis_exchange_profile(
                size=size,
                canonical_basis=canonical_system["pivot_columns_zero_based"],
                records=basis_records,
            )
            if analyze_basis_exchange
            else None
        ),
        "witness": witness,
    }
    result["certificate_digest"] = hashlib.sha256(
        json.dumps(
            result, sort_keys=True, separators=(",", ":")
        ).encode("ascii")
    ).hexdigest()
    return result


def _candidate_vector(
    size: int,
    pivot_columns: tuple[int, ...],
    free_columns: tuple[int, ...],
    coefficients: tuple[tuple[Fraction, ...], ...],
    free_values: tuple[Fraction, ...],
) -> tuple[Fraction, ...]:
    vector = [Fraction(0)] * size
    for column, value in zip(free_columns, free_values, strict=True):
        vector[column] = value
    for row, pivot_column in enumerate(pivot_columns):
        vector[pivot_column] = -sum(
            (
                coefficient * value
                for coefficient, value in zip(
                    coefficients[row], free_values, strict=True
                )
            ),
            start=Fraction(0),
        )
    return tuple(vector)

def _literal_node(literal: int) -> int:
    variable = abs(literal) - 1
    return 2 * variable + int(literal < 0)


def _solve_two_sat(
    variable_count: int, clauses: Sequence[tuple[int, int]]
) -> tuple[tuple[int, ...] | None, int | None]:
    graph = [[] for _ in range(2 * variable_count)]
    reverse = [[] for _ in range(2 * variable_count)]
    for left, right in clauses:
        left_node = _literal_node(left)
        right_node = _literal_node(right)
        implications = (
            (left_node ^ 1, right_node),
            (right_node ^ 1, left_node),
        )
        for source, target in implications:
            graph[source].append(target)
            reverse[target].append(source)

    visited = [False] * len(graph)
    order: list[int] = []
    for root in range(len(graph)):
        if visited[root]:
            continue
        visited[root] = True
        stack = [(root, 0)]
        while stack:
            node, edge_index = stack[-1]
            if edge_index < len(graph[node]):
                target = graph[node][edge_index]
                stack[-1] = (node, edge_index + 1)
                if not visited[target]:
                    visited[target] = True
                    stack.append((target, 0))
                continue
            order.append(node)
            stack.pop()

    components = [-1] * len(graph)
    component = 0
    for root in reversed(order):
        if components[root] != -1:
            continue
        components[root] = component
        stack = [root]
        while stack:
            node = stack.pop()
            for target in reverse[node]:
                if components[target] == -1:
                    components[target] = component
                    stack.append(target)
        component += 1

    for variable in range(variable_count):
        if components[2 * variable] == components[2 * variable + 1]:
            return None, variable
    assignment = tuple(
        int(components[2 * variable] > components[2 * variable + 1])
        for variable in range(variable_count)
    )
    return assignment, None


def _bounded_support_2sat(system: dict[str, Any]) -> tuple[
    tuple[int, ...] | None, dict[str, Any]
]:
    coefficients = system["pivot_free_coefficients"]
    free_columns = system["free_columns_zero_based"]
    pivot_columns = system["pivot_columns_zero_based"]
    clauses: list[tuple[int, int]] = []
    empty_relation_pivot: int | None = None

    for row_index, row in enumerate(coefficients):
        support = tuple(index for index, value in enumerate(row) if value != 0)
        if len(support) > 2:
            raise ValueError("pivot relation exceeds binary support")
        for bits in itertools.product((0, 1), repeat=len(support)):
            pivot_value = -sum(
                (
                    row[index] * Fraction(3 * bit - 1)
                    for index, bit in zip(support, bits, strict=True)
                ),
                start=Fraction(0),
            )
            if pivot_value in _ALLOWED_KERNEL_VALUES:
                continue
            literals = tuple(
                index + 1 if bit == 0 else -(index + 1)
                for index, bit in zip(support, bits, strict=True)
            )
            if not literals:
                empty_relation_pivot = pivot_columns[row_index] + 1
                break
            if len(literals) == 1:
                clauses.append((literals[0], literals[0]))
            else:
                clauses.append((literals[0], literals[1]))
        if empty_relation_pivot is not None:
            break

    clauses = sorted(set(clauses))
    clause_digest = hashlib.sha256(
        json.dumps(clauses, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    if empty_relation_pivot is not None:
        assignment = None
        conflict_free_column = None
    else:
        assignment, conflict_index = _solve_two_sat(len(free_columns), clauses)
        conflict_free_column = (
            None if conflict_index is None else free_columns[conflict_index] + 1
        )
    return assignment, {
        "free_variables": len(free_columns),
        "clauses": len(clauses),
        "clause_digest": clause_digest,
        "empty_relation_pivot": empty_relation_pivot,
        "conflict_free_column": conflict_free_column,
    }


def decide_cubic_kernel(
    formula: Sequence[Sequence[int]],
    *,
    pivot_columns: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Decide exactly, optionally using a specified one-based column basis."""

    canonical = canonical_cubic_formula(formula)
    canonical_system = _system(canonical)
    if pivot_columns is None:
        system = canonical_system
    else:
        requested = tuple(pivot_columns)
        size = len(canonical)
        if (
            any(
                isinstance(column, bool) or not isinstance(column, int)
                for column in requested
            )
            or any(column < 1 or column > size for column in requested)
            or len(set(requested)) != len(requested)
        ):
            raise CubicKernelDecisionError(
                "pivot_columns must contain distinct one-based columns"
            )
        rank = len(canonical_system["pivot_columns_zero_based"])
        if len(requested) != rank:
            raise CubicKernelDecisionError(
                f"pivot_columns must contain exactly {rank} columns"
            )
        system = _system_for_pivot_basis(
            incidence_matrix(canonical),
            tuple(column - 1 for column in requested),
        )
        if system is None:
            raise CubicKernelDecisionError(
                "pivot_columns do not form a column basis"
            )
    pivots = system["pivot_columns_zero_based"]
    free = system["free_columns_zero_based"]
    coefficients = system["pivot_free_coefficients"]
    supports = system["pivot_free_supports"]
    support_histogram = {
        str(support): supports.count(support) for support in sorted(set(supports))
    }
    size = len(canonical)
    rank = len(pivots)
    nullity = len(free)
    common = {
        "clauses": size,
        "variables": size,
        "rank": rank,
        "nullity": nullity,
        "pivot_columns": [column + 1 for column in pivots],
        "free_columns": [column + 1 for column in free],
        "candidate_kernel_vectors": 1 << nullity,
        "maximum_pivot_free_support": max(supports, default=0),
        "pivot_free_support_histogram": support_histogram,
        "system_digest": system["system_digest"],
        "maximum_numerator_bits": system["maximum_numerator_bits"],
        "maximum_denominator_bits": system["maximum_denominator_bits"],
    }

    if nullity == 0:
        return {
            **common,
            "status": "unsat",
            "reason": "full_rank",
            "candidates_checked": 0,
            "assignment": None,
            "kernel_vector": None,
            "rejection_digest": None,
            "two_sat_certificate": None,
        }
    if size % 3:
        return {
            **common,
            "status": "unsat",
            "reason": "cardinality_not_divisible_by_three",
            "candidates_checked": 0,
            "assignment": None,
            "kernel_vector": None,
            "rejection_digest": None,
            "two_sat_certificate": None,
        }

    if max(supports, default=0) <= 2:
        free_bits, certificate = _bounded_support_2sat(system)
        certificate = {
            **certificate,
            "satisfying_free_bits": (
                None if free_bits is None else list(free_bits)
            ),
        }
        if free_bits is None:
            return {
                **common,
                "status": "unsat",
                "reason": (
                    "forced_zero_pivot"
                    if certificate["empty_relation_pivot"] is not None
                    else "bounded_support_2sat_unsat"
                ),
                "candidates_checked": 0,
                "assignment": None,
                "kernel_vector": None,
                "rejection_digest": None,
                "two_sat_certificate": certificate,
            }

        free_values = tuple(Fraction(3 * bit - 1) for bit in free_bits)
        vector = _candidate_vector(size, pivots, free, coefficients, free_values)
        if not all(value in _ALLOWED_KERNEL_VALUES for value in vector):
            raise AssertionError("2-SAT reconstruction violated the kernel alphabet")
        assignment = [int((value + 1) / 3) for value in vector]
        if not all(
            sum(assignment[variable - 1] for variable in clause) == 1
            for clause in canonical
        ):
            raise AssertionError("2-SAT kernel witness failed exact-one validation")
        return {
            **common,
            "status": "sat",
            "reason": "bounded_support_2sat_sat",
            "candidates_checked": 0,
            "assignment": assignment,
            "kernel_vector": [int(value) for value in vector],
            "rejection_digest": None,
            "two_sat_certificate": certificate,
        }

    rejection_hasher = hashlib.sha256()
    candidates_checked = 0
    for free_values in itertools.product(_ALLOWED_KERNEL_VALUES, repeat=nullity):
        candidates_checked += 1
        vector = _candidate_vector(size, pivots, free, coefficients, free_values)
        invalid = next(
            (
                (column, vector[column])
                for column in pivots
                if vector[column] not in _ALLOWED_KERNEL_VALUES
            ),
            None,
        )
        if invalid is not None:
            column, value = invalid
            rejection_hasher.update(
                (
                    ",".join(_fraction_text(item) for item in free_values)
                    + f"|{column + 1}|{_fraction_text(value)}\n"
                ).encode("ascii")
            )
            continue

        assignment = [int((value + 1) / 3) for value in vector]
        if not all(
            sum(assignment[variable - 1] for variable in clause) == 1
            for clause in canonical
        ):
            raise AssertionError("kernel reconstruction failed exact-one validation")
        return {
            **common,
            "status": "sat",
            "reason": "alphabet_kernel_vector",
            "candidates_checked": candidates_checked,
            "assignment": assignment,
            "kernel_vector": [int(value) for value in vector],
            "rejection_digest": rejection_hasher.hexdigest(),
            "two_sat_certificate": None,
        }

    return {
        **common,
        "status": "unsat",
        "reason": "alphabet_exhausted",
        "candidates_checked": candidates_checked,
        "assignment": None,
        "kernel_vector": None,
        "rejection_digest": rejection_hasher.hexdigest(),
        "two_sat_certificate": None,
    }


def incidence_connected(formula: Sequence[Sequence[int]]) -> bool:
    """Return whether the formula's bipartite incidence graph is connected."""

    canonical = canonical_cubic_formula(formula)
    size = len(canonical)
    adjacency = [[] for _ in range(2 * size)]
    for clause_index, clause in enumerate(canonical):
        for variable in clause:
            variable_vertex = size + variable - 1
            adjacency[clause_index].append(variable_vertex)
            adjacency[variable_vertex].append(clause_index)
    reached = {0}
    frontier = [0]
    while frontier:
        vertex = frontier.pop()
        for neighbor in adjacency[vertex]:
            if neighbor not in reached:
                reached.add(neighbor)
                frontier.append(neighbor)
    return len(reached) == 2 * size


__all__ = [
    "CubicKernelDecisionError",
    "canonical_cubic_formula",
    "canonical_cubic_matrix",
    "cubic_kernel_profile",
    "cubic_kernel_basis_width",
    "cubic_kernel_width_two_basis",
    "cubic_kernel_width_two_line_profile",
    "cubic_kernel_short_line_basis",
    "cubic_kernel_zero_valid_basis",
    "cubic_kernel_dual_triangle_profile",
    "decide_cubic_kernel",
    "incidence_connected",
    "incidence_matrix",
    "verify_cubic_width_two_basis",
]
