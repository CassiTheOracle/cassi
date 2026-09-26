"""Independent verifier for the frame-separation receipt.

This verifier imports neither the runner nor any cubic-kernel implementation.
It rebuilds every formula, canonical order, rational elimination, kernel
coordinate column, class configuration, basis-width census, element-triangle
criterion, and nullity-three frame decision from scratch, and rechecks every
witness matrix in the receipt by direct support evaluation.

Nullity-three frame decision: the dual is frame exactly when the element
classes admit a partition into three groups, each spanning dimension at most
two, whose orthogonal spaces have an independent transversal. The eight Hall
conditions are tested exactly over the rationals, and every partition of the
classes is enumerated, so the decision is complete rather than a search
heuristic.
"""

from __future__ import annotations

import itertools
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

RECEIPT = Path("_diag/frame_separation_probe.json")
SCHEMA = "cassifi.frame-separation-probe.v1"
HALL_SUBSETS = tuple(
    subset
    for size in (1, 2, 3)
    for subset in itertools.combinations(range(3), size)
)

SUPPORT_THREE_SAT = (
    (1, 6, 3),
    (1, 3, 5),
    (1, 8, 2),
    (4, 6, 8),
    (4, 8, 5),
    (4, 3, 2),
    (7, 9, 5),
    (7, 9, 2),
    (7, 9, 6),
)
SUPPORT_THREE_UNSAT = (
    (1, 14, 11),
    (2, 1, 15),
    (3, 10, 5),
    (4, 8, 14),
    (5, 11, 7),
    (6, 12, 1),
    (7, 9, 2),
    (8, 15, 12),
    (9, 5, 6),
    (10, 13, 3),
    (11, 4, 8),
    (12, 3, 10),
    (13, 6, 4),
    (14, 7, 13),
    (15, 2, 9),
)
GREEDY_EXCHANGE_TRAP_SAT = (
    (1, 2, 6),
    (1, 3, 5),
    (1, 3, 7),
    (2, 4, 6),
    (2, 4, 9),
    (3, 4, 5),
    (5, 8, 9),
    (6, 7, 8),
    (7, 8, 9),
)
ALL_BASES_TERNARY_SAT = (
    (1, 2, 7),
    (1, 4, 10),
    (1, 6, 10),
    (2, 7, 9),
    (2, 11, 12),
    (3, 4, 11),
    (3, 6, 7),
    (3, 8, 12),
    (4, 9, 10),
    (5, 6, 11),
    (5, 8, 9),
    (5, 8, 12),
)
ALL_BASES_TERNARY_UNSAT = (
    (1, 3, 7),
    (1, 6, 12),
    (1, 7, 8),
    (2, 3, 6),
    (2, 10, 13),
    (2, 13, 15),
    (3, 4, 12),
    (4, 7, 9),
    (4, 11, 12),
    (5, 8, 10),
    (5, 11, 15),
    (5, 13, 14),
    (6, 9, 14),
    (8, 11, 14),
    (9, 10, 15),
)
CONTROLS = {
    "support-three-sat-n9": SUPPORT_THREE_SAT,
    "support-three-unsat-n15": SUPPORT_THREE_UNSAT,
    "greedy-exchange-trap-sat-n9": GREEDY_EXCHANGE_TRAP_SAT,
    "all-bases-ternary-sat-n12": ALL_BASES_TERNARY_SAT,
    "all-bases-ternary-unsat-n15": ALL_BASES_TERNARY_UNSAT,
}

C4_INCIDENCE = ((1, 0, 0), (-1, 1, 0), (0, -1, 1), (0, 0, -1))
U37_GENERAL_POSITION = (
    (1, 0, 0),
    (0, 1, 0),
    (0, 0, 1),
    (1, 1, 1),
    (1, 2, 3),
    (1, 3, 2),
    (2, 1, 3),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical(formula: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    return tuple(sorted(tuple(sorted(clause)) for clause in formula))


def incidence(formula: Sequence[Sequence[int]]) -> list[list[Fraction]]:
    size = len(formula)
    matrix = [[Fraction(0)] * size for _ in range(size)]
    for row, clause in enumerate(formula):
        for variable in clause:
            matrix[row][variable - 1] = Fraction(1)
    return matrix


def rref(matrix: Sequence[Sequence[Fraction]]) -> tuple[list[list[Fraction]], tuple[int, ...]]:
    rows = [[Fraction(value) for value in row] for row in matrix]
    pivots: list[int] = []
    position = 0
    for column in range(len(rows[0]) if rows else 0):
        pivot = None
        for scan in range(position, len(rows)):
            if rows[scan][column] != 0:
                pivot = scan
                break
        if pivot is None:
            continue
        rows[position], rows[pivot] = rows[pivot], rows[position]
        lead = rows[position][column]
        rows[position] = [value / lead for value in rows[position]]
        for other in range(len(rows)):
            if other != position and rows[other][column] != 0:
                factor = rows[other][column]
                rows[other] = [
                    value - factor * base
                    for value, base in zip(rows[other], rows[position])
                ]
        pivots.append(column)
        position += 1
        if position == len(rows):
            break
    return rows, tuple(pivots)


def matrix_rank(rows: Sequence[Sequence[Any]]) -> int:
    if not rows:
        return 0
    width = len(rows[0])
    return len(rref(rows)[1])


def kernel_data(
    formula: Sequence[Sequence[int]],
) -> tuple[list[tuple[Fraction, ...]], tuple[int, ...], tuple[int, ...]]:
    """Kernel basis vectors in free-column order, plus pivot and free columns."""

    size = len(formula)
    reduced, pivots = rref(incidence(formula))
    pivot_set = set(pivots)
    free = tuple(column for column in range(size) if column not in pivot_set)
    vectors = []
    for index in range(len(free)):
        vector = [Fraction(0)] * size
        vector[free[index]] = Fraction(1)
        for row, pivot_column in enumerate(pivots):
            vector[pivot_column] = -reduced[row][free[index]]
        vectors.append(tuple(vector))
    return vectors, pivots, free


def dual_columns(formula: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    """Kernel-coordinate columns with per-vector least-common-multiple scaling."""

    size = len(formula)
    vectors, _, _ = kernel_data(formula)
    scaled = []
    for vector in vectors:
        factor = 1
        for value in vector:
            factor = math.lcm(factor, value.denominator)
        scaled.append(tuple(int(value * factor) for value in vector))
    return tuple(
        tuple(row[column] for row in scaled) for column in range(size)
    )


def normalize(values: Sequence[int]) -> tuple[int, ...] | None:
    divisor = 0
    for value in values:
        divisor = math.gcd(divisor, abs(int(value)))
    if divisor == 0:
        return None
    reduced = tuple(int(value) // divisor for value in values)
    for value in reduced:
        if value:
            if value < 0:
                reduced = tuple(-entry for entry in reduced)
            break
    return reduced


def class_data(
    columns: Sequence[Sequence[int]],
) -> tuple[list[tuple[int, ...]], int]:
    classes: list[tuple[int, ...]] = []
    loops = 0
    for column in columns:
        point = normalize(column)
        if point is None:
            loops += 1
            continue
        if point not in classes:
            classes.append(point)
    return classes, loops


def classes_of(columns: Sequence[Sequence[int]]) -> list[tuple[int, ...]]:
    classes, loops = class_data(columns)
    require(loops == 0, "a matrix column vanished")
    return classes


def orthogonal_basis(
    vectors: Sequence[Sequence[int]], width: int = 3
) -> list[list[Fraction]]:
    """Basis of the orthogonal complement of the span of ``vectors``."""

    if not vectors:
        return [
            [Fraction(int(index == other)) for other in range(width)]
            for index in range(width)
        ]
    rows, pivots = rref([[Fraction(value) for value in vector] for vector in vectors])
    rank = len(pivots)
    free = [column for column in range(width) if column not in set(pivots)]
    basis = []
    for free_column in free:
        vector = [Fraction(0)] * width
        vector[free_column] = Fraction(1)
        for row, pivot_column in enumerate(pivots):
            vector[pivot_column] = -rows[row][free_column]
        basis.append(vector)
    return basis


def space_sum_dim(spaces: Sequence[Sequence[Sequence[Fraction]]]) -> int:
    vectors: list[list[Fraction]] = []
    for space in spaces:
        vectors.extend([list(vector) for vector in space])
    return matrix_rank(vectors) if vectors else 0


def frame_decision(classes: Sequence[Sequence[int]]) -> bool:
    """Complete nullity-three decision by enumerating every class partition."""

    if len(classes) == 0:
        return True
    for assignment in itertools.product(range(3), repeat=len(classes)):
        groups: list[list[tuple[int, ...]]] = [[], [], []]
        for point, slot in zip(classes, assignment):
            groups[slot].append(tuple(point))
        allowed = True
        spaces: list[list[list[Fraction]]] = []
        for group in groups:
            if not group:
                spaces.append(orthogonal_basis([], 3))
                continue
            if matrix_rank([list(point) for point in group]) > 2:
                allowed = False
                break
            spaces.append(orthogonal_basis([list(point) for point in group], 3))
        if not allowed:
            continue
        if all(
            space_sum_dim([spaces[index] for index in subset]) >= len(subset)
            for subset in HALL_SUBSETS
        ):
            return True
    return False


def element_triangle(
    classes: Sequence[Sequence[int]],
) -> tuple[Sequence[int], ...] | None:
    for triple in itertools.combinations(classes, 3):
        normals = []
        for left, right in itertools.combinations(triple, 2):
            normal = normalize(
                (
                    left[1] * right[2] - left[2] * right[1],
                    left[2] * right[0] - left[0] * right[2],
                    left[0] * right[1] - left[1] * right[0],
                )
            )
            normals.append(normal)
        if any(normal is None for normal in normals):
            continue
        if all(
            any(sum(a * b for a, b in zip(normal, point)) == 0 for normal in normals)
            for point in classes
        ):
            return triple
    return None


def basis_census(formula: Sequence[Sequence[int]]) -> dict[str, Any]:
    """Own census: every column basis, pivot-free support maximum."""

    canonical_formula = canonical(formula)
    matrix = incidence(canonical_formula)
    size = len(canonical_formula)
    rank = matrix_rank(matrix)
    histogram: dict[int, int] = {}
    for pivots in itertools.combinations(range(size), rank):
        order = list(pivots) + [column for column in range(size) if column not in pivots]
        permuted = [[row[column] for column in order] for row in matrix]
        reduced, found = rref(permuted)
        if tuple(found) != tuple(range(rank)):
            continue
        width = 0
        for row in range(rank):
            width = max(width, sum(reduced[row][column] != 0 for column in range(rank, size)))
        histogram[width] = histogram.get(width, 0) + 1
    return {
        "rank": rank,
        "nullity": size - rank,
        "bases": sum(histogram.values()),
        "histogram": {key: histogram[key] for key in sorted(histogram)},
        "minimum": min(histogram) if histogram else 0,
    }


def witness_support(
    matrix: Sequence[Sequence[int]], columns: Sequence[Sequence[int]]
) -> dict[str, Any]:
    width = len(matrix)
    rank = matrix_rank(matrix)
    supports = [
        sum(
            1
            for row in matrix
            if sum(a * b for a, b in zip(row, column)) != 0
        )
        for column in columns
    ]
    return {
        "rank": rank,
        "full_rank": rank == width,
        "max_support": max(supports) if supports else 0,
        "frame": rank == width and max(supports, default=0) <= 2,
    }


def direct_sum(formulas: Sequence[Sequence[Sequence[int]]]) -> tuple[tuple[int, int, int], ...]:
    offset = 0
    rows: list[tuple[int, int, int]] = []
    for formula in formulas:
        for clause in formula:
            rows.append((clause[0] + offset, clause[1] + offset, clause[2] + offset))
        offset += len(formula)
    return canonical(tuple(rows))


def coordinate_blocks(columns: Sequence[Sequence[int]]) -> list[tuple[int, ...]]:
    width = len(columns[0])
    parent = list(range(width))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for column in columns:
        support = [index for index, value in enumerate(column) if value]
        for other in support[1:]:
            left, right = find(support[0]), find(other)
            if left != right:
                parent[left] = right
    groups: dict[int, list[int]] = {}
    for index in range(width):
        groups.setdefault(find(index), []).append(index)
    return [tuple(sorted(group)) for group in groups.values()]


def main() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(receipt["schema"] == SCHEMA, "schema mismatch")

    # synthetic controls for the decision procedure
    require(frame_decision(classes_of(C4_INCIDENCE)), "C4 incidence is not frame")
    require(
        not frame_decision(list(U37_GENERAL_POSITION)),
        "seven general-position points were called frame",
    )
    collinear = 0
    for left, right, third in itertools.combinations(U37_GENERAL_POSITION, 3):
        if matrix_rank([list(left), list(right), list(third)]) < 3:
            collinear += 1
    require(collinear == 0, "the seven-point control has a collinear triple")

    control_rows = {row["name"]: row for row in receipt["controls"]}
    require(set(control_rows) == set(CONTROLS), "control set mismatch")
    census_agreements = 0
    triangle_agreements = 0
    frame_agreements = 0
    witness_agreements = 0
    loop_total = 0
    for name, formula in CONTROLS.items():
        row = control_rows[name]
        canonical_formula = canonical(formula)
        columns = dual_columns(canonical_formula)
        require(
            len(columns) == len(canonical_formula) == row["size"], f"{name}: size mismatch"
        )
        require(len(columns[0]) == row["nullity"] == 3, f"{name}: nullity mismatch")
        classes, loops = class_data(columns)
        loop_total += loops
        require(len(classes) == row["classes"], f"{name}: class count mismatch")
        census = basis_census(canonical_formula)
        require(census["minimum"] == row["omega"], f"{name}: width mismatch")
        require(census["nullity"] == 3, f"{name}: census nullity mismatch")
        census_agreements += 1
        triangle = element_triangle(classes)
        require(
            (triangle is not None) == (row["element_triangle"] is not None),
            f"{name}: element-triangle verdict mismatch",
        )
        require(
            (triangle is not None) == (census["minimum"] == 2),
            f"{name}: element triangle does not match the census",
        )
        triangle_agreements += 1
        decision = frame_decision(classes)
        require(decision == row["frame"], f"{name}: frame verdict mismatch")
        frame_agreements += 1
        if row.get("witness") is not None:
            check = witness_support(row["witness"], columns)
            require(check["frame"], f"{name}: witness does not frame the dual")
            require(check == {
                "rank": check["rank"],
                "full_rank": True,
                "max_support": check["max_support"],
                "frame": True,
            }, f"{name}: witness rank/support mismatch")
            require(check["max_support"] == row["check"]["max_support"], f"{name}: support mismatch")
            witness_agreements += 1
        if row["omega"] == 3:
            require(triangle is None, f"{name}: width three has an element triangle")
        if census["minimum"] == 2:
            require(decision, f"{name}: width two is not frame")

    require(loop_total == 0, "a control column vanished (loop) in the dual representation")

    # direct sums and the unbounded family
    receipt_sums = {row["name"]: row for row in receipt["sums"] + receipt["family"]}
    component_censuses = {
        name: basis_census(canonical(formula)) for name, formula in CONTROLS.items()
    }
    sum_witnesses = 0
    law_checks = 0
    direct_census_checks = 0
    family_rows = {row["name"]: row for row in receipt["family"]}
    for name, row in receipt_sums.items():
        components = row["components"]
        if name.startswith("sum-"):
            parts = {
                "sum-three-sat+three-sat-n18": [SUPPORT_THREE_SAT, SUPPORT_THREE_SAT],
                "sum-three-sat+three-unsat-n24": [SUPPORT_THREE_SAT, SUPPORT_THREE_UNSAT],
                "sum-three-sat+bases-sat-n21": [SUPPORT_THREE_SAT, ALL_BASES_TERNARY_SAT],
                "sum-bases-sat+bases-sat-n24": [ALL_BASES_TERNARY_SAT, ALL_BASES_TERNARY_SAT],
                "sum-bases-sat+bases-unsat-n27": [ALL_BASES_TERNARY_SAT, ALL_BASES_TERNARY_UNSAT],
            }[name]
        else:
            blocks = int(name.split("-x")[1].split("-")[0])
            parts = [ALL_BASES_TERNARY_SAT] * blocks
        require(len(parts) == components, f"{name}: component count mismatch")
        formula = direct_sum(parts)
        columns = dual_columns(formula)
        require(len(formula) == row["size"], f"{name}: size mismatch")
        require(len(columns[0]) == row["nullity"], f"{name}: nullity mismatch")
        blocks = coordinate_blocks(columns)
        require([list(block) for block in blocks] == row["blocks"], f"{name}: block mismatch")
        require(len(blocks) == components, f"{name}: block count mismatch")
        minimums = [
            component_censuses[
                next(
                    key
                    for key, value in CONTROLS.items()
                    if canonical(value) == canonical(part)
                )
            ]["minimum"]
            for part in parts
        ]
        require(max(minimums) == row["omega"], f"{name}: width law mismatch")
        law_checks += 1
        check = witness_support(row["witness"], columns)
        require(check["frame"], f"{name}: block witness does not frame the dual")
        require(check["max_support"] == row["check"]["max_support"], f"{name}: support mismatch")
        sum_witnesses += 1
        if row.get("direct_census_agrees"):
            direct = basis_census(formula)
            require(direct["minimum"] == row["omega"], f"{name}: direct census mismatch")
            direct_census_checks += 1
        if name in family_rows:
            require(row["omega"] == 3, f"{name}: family width is not three")
            require(row["nullity"] == 3 * components, f"{name}: family nullity mismatch")

    separation = receipt["separation"]
    require(separation["width_two_controls"] == 3, "width-two control count mismatch")
    require(
        separation["width_two_controls_with_element_triangle"] == 3,
        "a width-two control lost its element triangle",
    )
    require(separation["width_three_controls"] == 2, "width-three control count mismatch")
    require(
        separation["width_three_controls_without_element_triangle"] == 2,
        "a width-three control gained an element triangle",
    )
    require(
        separation["width_three_controls_that_are_frame"] == 2,
        "a width-three control is not frame",
    )
    require(
        separation["controls_criterion_matches_census"] == 5,
        "the element-triangle criterion does not match the census",
    )
    require(separation["sums_that_are_frame"] == separation["sums_total"], "a sum is not frame")
    require(separation["sums_with_width_law"] == separation["sums_total"], "width law failed")
    require(
        separation["family_frame"] == separation["family_total"], "a family member is not frame"
    )
    require(
        separation["family_invariant_width_three"] == separation["family_total"],
        "a family member lost width three",
    )
    require(separation["family_maximum_size"] >= 48, "family size shrank")
    require(separation["family_maximum_nullity"] >= 12, "family nullity shrank")

    print(json.dumps({
        "schema": SCHEMA,
        "controls_verified": len(CONTROLS),
        "census_agreements": census_agreements,
        "element_triangle_agreements": triangle_agreements,
        "frame_decision_agreements": frame_agreements,
        "control_witnesses_verified": witness_agreements,
        "sums_verified": len(receipt_sums) - len(family_rows),
        "family_verified": len(family_rows),
        "sum_witnesses_verified": sum_witnesses,
        "width_law_checks": law_checks,
        "direct_census_checks": direct_census_checks,
        "synthetic_frame_decision": {
            "c4_incidence": True,
            "u37_general_position": False,
            "u37_collinear_triples": collinear,
        },
        "nullity_three_decision": "complete partition enumeration with exact Hall conditions",
        "status": "verified",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
