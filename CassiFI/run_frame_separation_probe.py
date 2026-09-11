"""Frame separation probe: external framing versus ground-set frame width.

Receipt: ``_diag/frame_separation_probe.json``
Schema: ``cassifi.frame-separation-probe.v1``

The cubic exact-one width question has two neighbouring notions.

Internal width: ``omega(M) <= 2`` means a ground-set basis ``F`` of the dual
column matroid ``N*`` spans every remaining element with at most two elements
of ``F``.

External framing: ``N*`` is a frame matroid, meaning some row-equivalent
matrix has at most two nonzeros per column.

An internal width-two witness is always an ambient frame basis, so
``omega(M) <= 2`` implies external framing.  This probe measures the converse
and finds it false inside the cubic family.

Nullity three, with classes ``P`` in ``PG(2)``:

* internal: ``omega(M) <= 2`` iff three element classes ``p1, p2, p3`` exist
  whose pairwise joins ``span(pi, pj)`` cover ``P`` (an element triangle);
* external: ``N*`` is frame iff ``P`` is covered by some three lines with
  linearly independent normals, whose vertices need not be element classes.

Direct sums keep frame-ness (block diagonal witness) and have
``omega(M1 + M2) = max(omega(M1), omega(M2))``, because circuits of a direct
sum never cross components.  Slicing the width-three all-bases controls into
direct sums therefore produces a family that is externally frame with
invariant width three at every size.
"""

from __future__ import annotations

import itertools
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

import run_mixed_schaefer_frame_obstruction as runner
from cubic_kernel_decision import (
    canonical_cubic_formula,
    cubic_kernel_basis_width,
)
from growing_nullity_schaefer_probe import (
    exact_basis_census,
    multiply_histograms,
)
from run_cubic_kernel_analysis import (
    ALL_BASES_TERNARY_SAT,
    ALL_BASES_TERNARY_UNSAT,
    GREEDY_EXCHANGE_TRAP_SAT,
    SUPPORT_THREE_SAT,
    SUPPORT_THREE_UNSAT,
)

OUTPUT = Path("_diag/frame_separation_probe.json")
SCHEMA = "cassifi.frame-separation-probe.v1"
CENSUS_SUBSET_LIMIT = 25000

CONTROLS: tuple[tuple[str, tuple[tuple[int, int, int], ...]], ...] = (
    ("support-three-sat-n9", SUPPORT_THREE_SAT),
    ("support-three-unsat-n15", SUPPORT_THREE_UNSAT),
    ("greedy-exchange-trap-sat-n9", GREEDY_EXCHANGE_TRAP_SAT),
    ("all-bases-ternary-sat-n12", ALL_BASES_TERNARY_SAT),
    ("all-bases-ternary-unsat-n15", ALL_BASES_TERNARY_UNSAT),
)


def normalize(values: Sequence[int]) -> tuple[int, ...] | None:
    """Reduce an integer vector to a primitive projective representative."""

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


def cross(left: Sequence[int], right: Sequence[int]) -> tuple[int, int, int]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def dot(left: Sequence[int], right: Sequence[int]) -> int:
    return sum(a * b for a, b in zip(left, right))


def determinant(matrix: Sequence[Sequence[int]]) -> Fraction:
    size = len(matrix)
    total = Fraction(0)
    for permutation in itertools.permutations(range(size)):
        inversions = sum(
            1
            for i in range(size)
            for j in range(i + 1, size)
            if permutation[i] > permutation[j]
        )
        product = Fraction(1)
        for row, column in enumerate(permutation):
            product *= Fraction(matrix[row][column])
        total += (-1) ** inversions * product
    return total


def matrix_rank(rows: Sequence[Sequence[Fraction | int]], width: int) -> int:
    matrix = [[Fraction(value) for value in row] for row in rows]
    rank = 0
    for column in range(width):
        pivot = None
        for scan in range(rank, len(matrix)):
            if matrix[scan][column] != 0:
                pivot = scan
                break
        if pivot is None:
            continue
        matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
        lead = matrix[rank][column]
        matrix[rank] = [value / lead for value in matrix[rank]]
        for other in range(rank + 1, len(matrix)):
            if matrix[other][column] != 0:
                factor = matrix[other][column]
                matrix[other] = [
                    value - factor * base
                    for value, base in zip(matrix[other], matrix[rank])
                ]
        rank += 1
        if rank == len(matrix):
            break
    return rank


def nullspace(rows: Sequence[Sequence[int]], width: int) -> list[tuple[int, ...]]:
    """Primitive integer basis of ``{x : rows * x = 0}``."""

    if not rows:
        return [tuple(int(index == other) for other in range(width)) for index in range(width)]
    matrix = [[Fraction(value) for value in row] for row in rows]
    pivots: list[int] = []
    row = 0
    for column in range(width):
        pivot = None
        for scan in range(row, len(matrix)):
            if matrix[scan][column] != 0:
                pivot = scan
                break
        if pivot is None:
            continue
        matrix[row], matrix[pivot] = matrix[pivot], matrix[row]
        lead = matrix[row][column]
        matrix[row] = [value / lead for value in matrix[row]]
        for other in range(len(matrix)):
            if other != row and matrix[other][column] != 0:
                factor = matrix[other][column]
                matrix[other] = [
                    value - factor * base
                    for value, base in zip(matrix[other], matrix[row])
                ]
        pivots.append(column)
        row += 1
        if row == len(matrix):
            break
    free = [column for column in range(width) if column not in pivots]
    basis = []
    for free_column in free:
        vector = [Fraction(0)] * width
        vector[free_column] = Fraction(1)
        for index, pivot_column in enumerate(pivots):
            vector[pivot_column] = -matrix[index][free_column]
        scale = 1
        for value in vector:
            scale = scale * value.denominator
        entry = normalize([int(value * scale) for value in vector])
        if entry is not None:
            basis.append(entry)
    return basis


def classes_of(columns: Sequence[Sequence[int]]) -> list[tuple[int, ...]]:
    """Distinct projective classes of the dual representation columns."""

    classes: list[tuple[int, ...]] = []
    for column in columns:
        point = normalize(column)
        if point is None:
            continue
        if point not in classes:
            classes.append(point)
    return classes


def element_triangle(
    classes: Sequence[tuple[int, ...]],
) -> dict[str, Any] | None:
    """Internal criterion: a span triple whose three joins cover every class."""

    for triple in itertools.combinations(classes, 3):
        normals = []
        for left, right in itertools.combinations(triple, 2):
            normal = normalize(cross(left, right))
            if normal is None:
                break
            normals.append(normal)
        if len(normals) != 3:
            continue
        if all(any(dot(normal, point) == 0 for normal in normals) for point in classes):
            return {
                "triangle": [list(point) for point in triple],
                "join_normals": [list(normal) for normal in normals],
            }
    return None


def cover_witness(
    classes: Sequence[tuple[int, ...]],
) -> tuple[list[list[int]] | None, str | None]:
    """Exact nullity-three frame search: three lines, independent normals."""

    candidates: dict[tuple[int, ...], tuple[tuple[int, ...], tuple[int, ...]]] = {}
    for left, right in itertools.combinations(classes, 2):
        normal = normalize(cross(left, right))
        if normal is not None:
            candidates.setdefault(normal, (left, right))
    normals_list = sorted(candidates)

    def uncovered(normals: Sequence[Sequence[int]]) -> list[tuple[int, ...]]:
        return [
            point
            for point in classes
            if all(dot(normal, point) != 0 for normal in normals)
        ]

    def independent(triple: Sequence[Sequence[int]]) -> bool:
        return determinant(
            [[int(value) for value in normal] for normal in triple]
        ) != 0

    def complete(
        forced: Sequence[Sequence[int]], leftovers: Sequence[Sequence[int]]
    ) -> list[list[int]] | None:
        chosen = [[int(value) for value in normal] for normal in forced]
        for point in leftovers:
            space = nullspace([list(point)], 3)
            pool: list[tuple[int, ...]] = [entry for entry in space]
            for left, right in itertools.combinations(space, 2):
                combination = normalize([a + b for a, b in zip(left, right)])
                if combination is not None:
                    pool.append(combination)
            picked = None
            for candidate in pool:
                if candidate is None:
                    continue
                if matrix_rank(chosen + [list(candidate)], 3) == len(chosen) + 1:
                    picked = [int(value) for value in candidate]
                    break
            if picked is None:
                return None
            chosen.append(picked)
        if len(chosen) != 3 or not independent(chosen):
            return None
        return chosen

    for size in (1, 2):
        for forced in itertools.combinations(normals_list, size):
            leftovers = uncovered(forced)
            if len(leftovers) > 3 - size:
                continue
            witness = complete(forced, leftovers)
            if witness is not None:
                return witness, f"forced-{size}"
    for forced in itertools.combinations(normals_list, 3):
        if uncovered(forced) or not independent(forced):
            continue
        return [[int(value) for value in normal] for normal in forced], "forced-3"
    return None, None


def invert(matrix: Sequence[Sequence[int]]) -> list[list[Fraction]] | None:
    size = len(matrix)
    augmented = [
        [Fraction(value) for value in row]
        + [Fraction(int(index == other)) for other in range(size)]
        for index, row in enumerate(matrix)
    ]
    for column in range(size):
        pivot = None
        for scan in range(column, size):
            if augmented[scan][column] != 0:
                pivot = scan
                break
        if pivot is None:
            return None
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        lead = augmented[column][column]
        augmented[column] = [value / lead for value in augmented[column]]
        for other in range(size):
            if other != column and augmented[other][column] != 0:
                factor = augmented[other][column]
                augmented[other] = [
                    value - factor * base
                    for value, base in zip(augmented[other], augmented[column])
                ]
    return [row[size:] for row in augmented]


def ground_set_rows(
    matrix: Sequence[Sequence[int]], columns: Sequence[Sequence[int]]
) -> int:
    """Count frame basis vectors that are proportional to an element column."""

    inverse = invert(matrix)
    if inverse is None:
        return 0
    width = len(matrix)
    hits = 0
    for index in range(width):
        vector = [inverse[row][index] for row in range(width)]
        scale = 1
        for value in vector:
            scale = scale * value.denominator
        point = normalize([int(value * scale) for value in vector])
        if point is None:
            continue
        if any(normalize(column) == point for column in columns):
            hits += 1
    return hits


def witness_check(
    matrix: Sequence[Sequence[int]], columns: Sequence[Sequence[int]]
) -> dict[str, Any]:
    width = len(matrix)
    supports = [
        sum(
            1
            for row in matrix
            if sum(a * b for a, b in zip(row, column)) != 0
        )
        for column in columns
    ]
    rank = matrix_rank([list(row) for row in matrix], width)
    return {
        "rank": rank,
        "full_rank": rank == width,
        "max_support": max(supports),
        "support_values": sorted(set(supports)),
        "frame": rank == width and max(supports) <= 2,
    }


def census_width(formula: Sequence[Sequence[int]]) -> int | str:
    size = len(formula)
    profile = runner.cubic_kernel_profile(formula)
    subsets = math.comb(size, profile["rank"])
    if subsets > CENSUS_SUBSET_LIMIT:
        return f"skipped: {subsets} column subsets"
    return cubic_kernel_basis_width(formula)["minimum_maximum_pivot_free_support"]


def factorized_census(
    components: Sequence[Sequence[Sequence[int]]],
) -> dict[str, Any]:
    """Direct-sum census: sum bases are component bases, widths combine by max."""

    histogram = {"1": 1}
    per_component = []
    for component in components:
        census = exact_basis_census(component)
        per_component.append(
            {
                "clauses": census["clauses"],
                "rank": census["rank"],
                "nullity": census["nullity"],
                "column_bases_found": census["column_bases_found"],
                "basis_width_histogram": census["basis_width_histogram"],
                "minimum_width": census["minimum_width"],
            }
        )
        histogram = multiply_histograms(histogram, census["basis_width_histogram"])
    total = sum(histogram.values())
    return {
        "component_censuses": per_component,
        "combined_width_histogram": {key: histogram[key] for key in sorted(histogram, key=int)},
        "combined_bases": total,
        "minimum_width": min(int(key) for key in histogram),
    }


def evaluate_control(
    name: str, formula: Sequence[Sequence[int]]
) -> dict[str, Any]:
    columns = runner.dual_columns(formula)
    classes = classes_of(columns)
    triangle = element_triangle(classes)
    matrix, kind = cover_witness(classes)
    record: dict[str, Any] = {
        "name": name,
        "size": len(formula),
        "nullity": len(columns[0]),
        "classes": len(classes),
        "omega": census_width(formula),
        "element_triangle": triangle,
        "cover_kind": kind,
    }
    if matrix is None:
        record["witness"] = None
        record["frame"] = False
    else:
        record["witness"] = matrix
        record["check"] = witness_check(matrix, columns)
        record["frame"] = record["check"]["frame"]
        record["ground_set_rows"] = ground_set_rows(matrix, columns)
    return record


def direct_sum(formulas: Sequence[Sequence[Sequence[int]]]) -> tuple[tuple[int, int, int], ...]:
    offset = 0
    rows: list[tuple[int, int, int]] = []
    for formula in formulas:
        for clause in formula:
            rows.append((clause[0] + offset, clause[1] + offset, clause[2] + offset))
        offset += len(formula)
    return canonical_cubic_formula(tuple(rows))


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
            root_left, root_right = find(support[0]), find(other)
            if root_left != root_right:
                parent[root_left] = root_right
    groups: dict[int, list[int]] = {}
    for index in range(width):
        groups.setdefault(find(index), []).append(index)
    return [tuple(sorted(group)) for group in groups.values()]


def evaluate_sum(
    name: str, formulas: Sequence[Sequence[Sequence[int]]]
) -> dict[str, Any]:
    formula = direct_sum(formulas)
    columns = runner.dual_columns(formula)
    width = len(columns[0])
    blocks = coordinate_blocks(columns)
    factorized = factorized_census(formulas)
    record: dict[str, Any] = {
        "name": name,
        "size": len(formula),
        "components": len(formulas),
        "nullity": width,
        "blocks": [list(block) for block in blocks],
        "factorized": factorized,
        "component_omega": [entry["minimum_width"] for entry in factorized["component_censuses"]],
        "omega": factorized["minimum_width"],
    }
    direct = census_width(formula)
    record["direct_omega"] = direct
    if isinstance(direct, int):
        record["direct_census_agrees"] = direct == record["omega"]
    if len(blocks) != len(formulas) or any(len(block) != 3 for block in blocks):
        record["witness"] = None
        record["frame"] = None
        record["note"] = "block detection failed"
        return record
    position = {}
    for slot, block in enumerate(blocks):
        for local, coordinate in enumerate(block):
            position[coordinate] = (slot, local)
    matrices: list[list[list[int]]] = []
    kinds: list[str | None] = []
    classes: list[int] = []
    for block in blocks:
        projected = [
            [column[index] for index in block]
            for column in columns
            if any(column[index] for index in block)
        ]
        block_classes = classes_of(projected)
        classes.append(len(block_classes))
        matrix, kind = cover_witness(block_classes)
        kinds.append(kind)
        if matrix is None:
            record["witness"] = None
            record["frame"] = False
            record["block_kinds"] = kinds
            record["block_classes"] = classes
            return record
        matrices.append(matrix)
    assembled = [[0] * width for _ in range(width)]
    for row in range(width):
        for column in range(width):
            row_slot, row_local = position[row]
            column_slot, column_local = position[column]
            if row_slot == column_slot:
                assembled[row][column] = matrices[row_slot][row_local][column_local]
    record["block_kinds"] = kinds
    record["block_classes"] = classes
    record["witness"] = assembled
    record["check"] = witness_check(assembled, columns)
    record["frame"] = record["check"]["frame"]
    record["width_law_holds"] = record["omega"] == max(record["component_omega"])
    return record


def build_receipt() -> dict[str, Any]:
    controls = [evaluate_control(name, formula) for name, formula in CONTROLS]
    sat = ALL_BASES_TERNARY_SAT
    unsat = ALL_BASES_TERNARY_UNSAT
    three_sat = SUPPORT_THREE_SAT
    three_unsat = SUPPORT_THREE_UNSAT
    sums = [
        evaluate_sum("sum-three-sat+three-sat-n18", [three_sat, three_sat]),
        evaluate_sum("sum-three-sat+three-unsat-n24", [three_sat, three_unsat]),
        evaluate_sum("sum-three-sat+bases-sat-n21", [three_sat, sat]),
        evaluate_sum("sum-bases-sat+bases-sat-n24", [sat, sat]),
        evaluate_sum("sum-bases-sat+bases-unsat-n27", [sat, unsat]),
    ]
    family = [
        evaluate_sum(f"family-bases-sat-x{blocks}-n{blocks * len(sat)}", [sat] * blocks)
        for blocks in (1, 2, 3, 4)
    ]
    width_two = [record for record in controls if record["omega"] == 2]
    width_three = [record for record in controls if record["omega"] == 3]
    return {
        "schema": SCHEMA,
        "controls": controls,
        "sums": sums,
        "family": family,
        "criteria": {
            "internal_nullity_three": "omega <= 2 iff an element triangle covers all classes",
            "external_nullity_three": "frame iff three lines with independent normals cover all classes",
            "internal_implies_external": "an internal witness basis is an ambient frame basis",
            "direct_sum_width_law": "omega(M1 + M2) = max(omega(M1), omega(M2))",
            "direct_sum_frame": "block diagonal of two-sparse witnesses is two-sparse",
        },
        "separation": {
            "width_two_controls": len(width_two),
            "width_two_controls_with_element_triangle": sum(
                1 for record in width_two if record["element_triangle"]
            ),
            "width_three_controls": len(width_three),
            "width_three_controls_without_element_triangle": sum(
                1 for record in width_three if record["element_triangle"] is None
            ),
            "width_three_controls_that_are_frame": sum(
                1 for record in width_three if record["frame"]
            ),
            "controls_criterion_matches_census": sum(
                1
                for record in controls
                if (record["element_triangle"] is not None) == (record["omega"] == 2)
            ),
            "sums_that_are_frame": sum(1 for record in sums if record["frame"]),
            "sums_total": len(sums),
            "sums_with_width_law": sum(1 for record in sums if record.get("width_law_holds")),
            "sums_with_direct_census_agreement": sum(
                1 for record in sums if record.get("direct_census_agrees")
            ),
            "family_total": len(family),
            "family_frame": sum(1 for record in family if record["frame"]),
            "family_invariant_width_three": sum(
                1 for record in family if record["omega"] == 3 and record.get("width_law_holds")
            ),
            "family_maximum_size": max(record["size"] for record in family),
            "family_maximum_nullity": max(record["nullity"] for record in family),
        },
    }


def main() -> None:
    receipt = build_receipt()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for record in receipt["controls"]:
        print(
            f"{record['name']:30s} n={record['size']:3d} classes={record['classes']:3d} "
            f"omega={record['omega']} triangle={record['element_triangle'] is not None} "
            f"frame={record['frame']} ground_set_rows={record.get('ground_set_rows')}"
        )
    for record in receipt["sums"] + receipt["family"]:
        check = record.get("check", {})
        print(
            f"{record['name']:30s} n={record['size']:3d} omega={record['omega']} "
            f"frame={record['frame']} max_support={check.get('max_support')} "
            f"law={record.get('width_law_holds')} direct={record.get('direct_census_agrees')}"
        )
    print(json.dumps(receipt["separation"], indent=2, sort_keys=True))
    print(f"receipt: {OUTPUT}")


if __name__ == "__main__":
    main()
