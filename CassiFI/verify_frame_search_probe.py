"""Independent verifier for the frame-search receipt.

Imports neither the runner nor any cubic-kernel implementation.  It rebuilds
every formula (the five controls, the five direct sums, all 1620 incidence
two-switches, and the nine chains), the canonical order, the exact rational
kernel-coordinate columns, the class partition, every search verdict with a
different branching order (highest uncovered class, pairs descending), every
certificate the receipt claims, and the width-two sieve of the
frame-separation probe as an independent second decision procedure.

Reference ties: the control and sum verdicts are compared against the recorded
widths of the frame-separation receipt, and the switch population is tied to
the mixed-probe enumeration by recomputing the sorted-digest hash of all 1620
switches.  Chains whose nullity is at most six are decided again by the exact
ground-element sieve over every ``C(n, nullity)`` subset; the nullity seven and
nine chains are corroborated by random independent draws.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

RECEIPT = Path("_diag/frame_search_probe.json")
FRAME_RECEIPT = Path("_diag/frame_separation_probe.json")
MIXED_RECEIPT = Path("_diag/mixed_schaefer_frame_obstruction.json")
SCHEMA = "cassifi.frame-search-probe.v1"
NODE_CAP = 200_000
SAMPLE_DRAWS = 1_200
SAMPLE_SEED = 20260910
SAMPLE_SMALL = 60

SUPPORT_THREE_SAT = (
    (1, 6, 3), (1, 3, 5), (1, 8, 2), (4, 6, 8), (4, 8, 5),
    (4, 3, 2), (7, 9, 5), (7, 9, 2), (7, 9, 6),
)
SUPPORT_THREE_UNSAT = (
    (1, 14, 11), (2, 1, 15), (3, 10, 5), (4, 8, 14), (5, 11, 7),
    (6, 12, 1), (7, 9, 2), (8, 15, 12), (9, 5, 6), (10, 13, 3),
    (11, 4, 8), (12, 3, 10), (13, 6, 4), (14, 7, 13), (15, 2, 9),
)
GREEDY_EXCHANGE_TRAP_SAT = (
    (1, 2, 6), (1, 3, 5), (1, 3, 7), (2, 4, 6), (2, 4, 9),
    (3, 4, 5), (5, 8, 9), (6, 7, 8), (7, 8, 9),
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
CONTROLS: dict[str, tuple[tuple[int, int, int], ...]] = {
    "support-three-sat-n9": SUPPORT_THREE_SAT,
    "support-three-unsat-n15": SUPPORT_THREE_UNSAT,
    "greedy-exchange-trap-sat-n9": GREEDY_EXCHANGE_TRAP_SAT,
    "all-bases-ternary-sat-n12": ALL_BASES_TERNARY_SAT,
    "all-bases-ternary-unsat-n15": ALL_BASES_TERNARY_UNSAT,
}
SUMS: dict[str, tuple[tuple[tuple[int, int, int], ...], ...]] = {
    "sum-three-sat+three-sat-n18": (SUPPORT_THREE_SAT, SUPPORT_THREE_SAT),
    "sum-three-sat+three-unsat-n24": (SUPPORT_THREE_SAT, SUPPORT_THREE_UNSAT),
    "sum-three-sat+bases-sat-n21": (SUPPORT_THREE_SAT, ALL_BASES_TERNARY_SAT),
    "sum-bases-sat+bases-sat-n24": (ALL_BASES_TERNARY_SAT, ALL_BASES_TERNARY_SAT),
    "sum-bases-sat+bases-unsat-n27": (ALL_BASES_TERNARY_SAT, ALL_BASES_TERNARY_UNSAT),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical(formula: Sequence[Sequence[int]]) -> tuple[tuple[int, int, int], ...]:
    """Own canonical order and cubic exact-one validation."""

    size = len(formula)
    require(size >= 3, "formula needs at least three clauses")
    clauses: list[tuple[int, int, int]] = []
    occurrences = [0] * size
    for clause in formula:
        require(len(clause) == 3, "clauses must be triples")
        ordered = tuple(sorted(int(variable) for variable in clause))
        require(len(set(ordered)) == 3, "clause variables must be distinct")
        for variable in ordered:
            require(1 <= variable <= size, "variables must span 1..n")
            occurrences[variable - 1] += 1
        clauses.append((ordered[0], ordered[1], ordered[2]))
    require(all(count == 3 for count in occurrences), "every variable must occur three times")
    return tuple(sorted(clauses))


def kernel_columns(
    formula: Sequence[Sequence[int]],
) -> tuple[int, tuple[tuple[Fraction, ...], ...], tuple[tuple[Fraction, ...], ...]]:
    """Exact rank and dual columns over the rationals, from a fresh elimination."""

    size = len(formula)
    matrix = [
        [Fraction(1) if variable in clause else Fraction(0) for variable in range(1, size + 1)]
        for clause in formula
    ]
    pivots: list[int] = []
    free: list[int] = []
    row = 0
    for column in range(size):
        source = next((index for index in range(row, len(matrix)) if matrix[index][column]), None)
        if source is None:
            free.append(column)
            continue
        matrix[row], matrix[source] = matrix[source], matrix[row]
        divisor = matrix[row][column]
        matrix[row] = [value / divisor for value in matrix[row]]
        for index in range(len(matrix)):
            if index == row or not matrix[index][column]:
                continue
            factor = matrix[index][column]
            matrix[index] = [
                value - factor * pivot_value
                for value, pivot_value in zip(matrix[index], matrix[row], strict=True)
            ]
        pivots.append(column)
        row += 1
    basis: list[list[Fraction]] = []
    for free_index, free_column in enumerate(free):
        del free_index
        vector = [Fraction(0)] * size
        vector[free_column] = Fraction(1)
        for pivot_index, pivot_column in enumerate(pivots):
            vector[pivot_column] = -matrix[pivot_index][free_column]
        basis.append(vector)
    columns = tuple(
        tuple(basis[index][element] for index in range(len(free))) for element in range(size)
    )
    return len(pivots), tuple(columns), tuple(tuple(vector) for vector in basis)


def primitive(values: Sequence[Fraction]) -> tuple[int, ...]:
    """Primitive integer representative with a positive leading entry."""

    scaled = [Fraction(value) for value in values]
    scale = 1
    for value in scaled:
        scale = math.lcm(scale, value.denominator)
    integers = [int(value * scale) for value in scaled]
    divisor = 0
    for value in integers:
        divisor = math.gcd(divisor, abs(value))
    if divisor:
        integers = [value // divisor for value in integers]
    for value in integers:
        if value:
            if value < 0:
                integers = [-entry for entry in integers]
            break
    return tuple(integers)


def classes_of(columns: Sequence[Sequence[Fraction]]) -> list[tuple[int, ...]]:
    """Distinct projective classes of the dual columns."""

    classes: list[tuple[int, ...]] = []
    for column in columns:
        point = primitive(column)
        if any(point):
            if point not in classes:
                classes.append(point)
    return classes


def rank_of(vectors: Sequence[Sequence[Fraction | int]]) -> int:
    matrix = [[Fraction(value) for value in vector] for vector in vectors if any(vector)]
    if not matrix:
        return 0
    width = len(matrix[0])
    rank = 0
    for column in range(width):
        source = next((row for row in range(rank, len(matrix)) if matrix[row][column]), None)
        if source is None:
            continue
        matrix[rank], matrix[source] = matrix[source], matrix[rank]
        for row in range(rank + 1, len(matrix)):
            if not matrix[row][column]:
                continue
            factor = matrix[row][column] / matrix[rank][column]
            matrix[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(matrix[row], matrix[rank], strict=True)
            ]
        rank += 1
        if rank == len(matrix):
            break
    return rank


def in_span(left: Sequence[Any], right: Sequence[Any], point: Sequence[Any]) -> bool:
    return rank_of((left, right, point)) <= 2


def pair_masks(
    classes: Sequence[tuple[int, ...]],
) -> tuple[dict[tuple[int, int], int], int]:
    masks: dict[tuple[int, int], int] = {}
    for left, right in itertools.combinations(range(len(classes)), 2):
        mask = (1 << left) | (1 << right)
        for target in range(len(classes)):
            if in_span(classes[left], classes[right], classes[target]):
                mask |= 1 << target
        masks[(left, right)] = mask
    return masks, (1 << len(classes)) - 1


def search(
    classes: Sequence[tuple[int, ...]], rank: int, node_cap: int = NODE_CAP
) -> tuple[list[int] | None, int, bool]:
    """Own complete search: highest uncovered class first, pairs descending."""

    masks, full = pair_masks(classes)
    nodes = 0
    capped = False

    def recurse(chosen: list[int]) -> list[int] | None:
        nonlocal nodes, capped
        nodes += 1
        if nodes > node_cap:
            capped = True
            return None
        covered = 0
        for left, right in itertools.combinations(chosen, 2):
            covered |= masks[(min(left, right), max(left, right))]
        uncovered = full & ~covered
        if not uncovered:
            return list(chosen) if rank_of([classes[index] for index in chosen]) == len(chosen) else None
        if len(chosen) == rank:
            return None
        target = uncovered.bit_length() - 1
        candidates = [pair for pair, mask in masks.items() if mask >> target & 1]
        for pair in reversed(candidates):
            addition = [index for index in pair if index not in chosen]
            trial = chosen + addition
            if len(trial) > rank:
                continue
            if rank_of([classes[index] for index in trial]) != len(trial):
                continue
            result = recurse(trial)
            if result is not None:
                return result
            if capped:
                return None
        return None

    chosen = recurse([])
    return chosen, nodes, capped


def extend(classes: Sequence[tuple[int, ...]], chosen: Sequence[int], rank: int) -> list[int]:
    basis = list(chosen)
    for index in range(len(classes)):
        if len(basis) == rank:
            break
        if index in basis:
            continue
        if rank_of([classes[item] for item in basis + [index]]) == len(basis) + 1:
            basis.append(index)
    require(len(basis) == rank, "independent set does not extend to a ground basis")
    return basis


def invert(matrix: Sequence[Sequence[Fraction]]) -> list[list[Fraction]]:
    size = len(matrix)
    augmented = [
        [Fraction(value) for value in row] + [Fraction(int(row_index == column)) for column in range(size)]
        for row_index, row in enumerate(matrix)
    ]
    for column in range(size):
        source = next((row for row in range(column, size) if augmented[row][column]), None)
        if source is None:
            raise AssertionError("matrix is singular")
        augmented[column], augmented[source] = augmented[source], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column or not augmented[row][column]:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(augmented[row], augmented[column], strict=True)
            ]
    return [row[size:] for row in augmented]


def width_of(columns: Sequence[Sequence[Fraction]], free: Sequence[int]) -> int:
    """Exact coordinates in a free basis: largest support over all elements."""

    width = len(free)
    basis = [[columns[free[column]][coordinate] for column in range(width)] for coordinate in range(width)]
    inverse = invert(basis)
    largest = 0
    for element in range(len(columns)):
        coordinates = [
            sum(inverse[row][column] * columns[element][column] for column in range(width))
            for row in range(width)
        ]
        largest = max(largest, sum(1 for value in coordinates if value))
    return largest


def direct_sum(formulas: Sequence[Sequence[Sequence[int]]]) -> tuple[tuple[int, int, int], ...]:
    rows: list[tuple[int, int, int]] = []
    offset = 0
    for formula in formulas:
        for clause in formula:
            ordered = sorted(variable + offset for variable in clause)
            rows.append((ordered[0], ordered[1], ordered[2]))
        offset += len(formula)
    return canonical(rows)


def assemble(blocks: Sequence[Sequence[Sequence[int]]]) -> tuple[list[list[int]], list[tuple[int, int]]]:
    clauses: list[list[int]] = []
    offsets: list[tuple[int, int]] = []
    offset = 0
    for block in blocks:
        offsets.append((len(clauses), offset))
        clauses.extend([[variable + offset for variable in clause] for clause in block])
        offset += len(block)
    return clauses, offsets


def apply_switch(clauses: list[list[int]], left_row: int, right_row: int) -> None:
    left, right = clauses[left_row], clauses[right_row]
    left_variable = next(value for value in left if value not in right)
    right_variable = next(value for value in right if value not in left)
    left[left.index(left_variable)] = right_variable
    right[right.index(right_variable)] = left_variable
    clauses[left_row] = sorted(left)
    clauses[right_row] = sorted(right)


def chain(blocks: Sequence[Sequence[Sequence[int]]], links: Sequence[tuple[int, int]]):
    clauses, offsets = assemble(blocks)
    for link_index, (left, right) in enumerate(links):
        apply_switch(clauses, offsets[left][0] + link_index % 3, offsets[right][0] + link_index % 3)
    return canonical(tuple(tuple(clause) for clause in clauses))


def switch_specs() -> list[tuple[int, int, int, int]]:
    specs = []
    for left_row, left_clause in enumerate(ALL_BASES_TERNARY_SAT):
        for left_variable in left_clause:
            for right_row, right_clause in enumerate(ALL_BASES_TERNARY_UNSAT):
                for right_variable in right_clause:
                    specs.append((left_row, left_variable, right_row, right_variable))
    return specs


def switch_formula(spec: tuple[int, int, int, int]):
    left_row, left_variable, right_row, right_variable = spec
    sat_size = len(ALL_BASES_TERNARY_SAT)
    rows = [list(clause) for clause in ALL_BASES_TERNARY_SAT]
    rows.extend([variable + sat_size for variable in clause] for clause in ALL_BASES_TERNARY_UNSAT)
    right_variable = right_variable + sat_size
    require(left_variable in rows[left_row], "switch source incidence is absent")
    require(right_variable in rows[sat_size + right_row], "switch target incidence is absent")
    require(right_variable not in rows[left_row], "switch would duplicate an incidence")
    require(left_variable not in rows[sat_size + right_row], "switch would duplicate an incidence")
    rows[left_row][rows[left_row].index(left_variable)] = right_variable
    rows[sat_size + right_row][rows[sat_size + right_row].index(right_variable)] = left_variable
    return canonical(tuple(tuple(sorted(clause)) for clause in rows))


def chain_formula(name: str):
    """Rebuild one named chain: consecutive blocks joined by cross switches."""

    if name.startswith("path-sat"):
        blocks = [ALL_BASES_TERNARY_SAT] * int(name[-1])
        links = [(index, index + 1) for index in range(len(blocks) - 1)]
    elif name.startswith("path-unsat"):
        blocks = [ALL_BASES_TERNARY_UNSAT] * int(name[-1])
        links = [(index, index + 1) for index in range(len(blocks) - 1)]
    elif name.startswith("path-alternating"):
        count = int(name[-1])
        blocks = [
            ALL_BASES_TERNARY_SAT if index % 2 == 0 else ALL_BASES_TERNARY_UNSAT
            for index in range(count)
        ]
        links = [(index, index + 1) for index in range(count - 1)]
    else:
        blocks = [ALL_BASES_TERNARY_SAT] * 3
        links = [(0, 1), (0, 2)]
    return chain(blocks, links)


def digest(formula: Sequence[Sequence[int]]) -> str:
    payload = json.dumps(canonical(formula), separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def sieve(
    columns: Sequence[Sequence[Fraction]], nullity: int, limit: int = 4
) -> tuple[list[tuple[int, ...]], int, int]:
    """Own exact ground-element sieve over every ``C(n, nullity)`` subset.

    Returns independent covering subsets, the number of subsets examined, and
    the number of covering subsets that are dependent (which certify nothing).
    """

    size = len(columns)
    full = (1 << size) - 1
    masks: dict[tuple[int, int], int] = {}
    by_class: dict[tuple[tuple[int, ...], tuple[int, ...]], int] = {}
    classes = [primitive(column) for column in columns]
    for left, right in itertools.combinations(range(size), 2):
        key = (classes[left], classes[right])
        if key not in by_class:
            mask = (1 << left) | (1 << right)
            for element in range(size):
                if in_span(columns[left], columns[right], columns[element]):
                    mask |= 1 << element
            by_class[key] = mask
        masks[(left, right)] = by_class[key]
    witnesses: list[tuple[int, ...]] = []
    examined = 0
    dependent = 0
    for subset in itertools.combinations(range(size), nullity):
        examined += 1
        covered = 0
        for left, right in itertools.combinations(subset, 2):
            covered |= masks[(left, right)]
        if covered != full:
            continue
        if rank_of([columns[index] for index in subset]) != nullity:
            dependent += 1
            continue
        witnesses.append(subset)
        if len(witnesses) >= limit:
            break
    return witnesses, examined, dependent


def class_enumeration(
    classes: Sequence[tuple[int, ...]], nullity: int, limit: int = 350_000
) -> tuple[list[tuple[int, ...]] | None, int]:
    """Exhaustive decision over every ``C(classes, nullity)`` class subset.

    Returns an independent covering class set (at most one) and the universe
    size, or ``(None, size)`` when the universe exceeds the limit.
    """

    total = math.comb(len(classes), nullity)
    if total > limit:
        return None, total
    masks, full = pair_masks(classes)
    witnesses: list[tuple[int, ...]] = []
    for chosen in itertools.combinations(range(len(classes)), nullity):
        covered = 0
        for left, right in itertools.combinations(chosen, 2):
            covered |= masks[(left, right)]
        if covered != full:
            continue
        if rank_of([classes[index] for index in chosen]) != nullity:
            continue
        witnesses.append(chosen)
        break
    return witnesses, total


def connected(formula: Sequence[Sequence[int]]) -> bool:
    size = len(formula)
    parent = list(range(size + size))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for row, clause in enumerate(formula):
        for variable in clause:
            left, right = find(row), find(size + variable - 1)
            if left != right:
                parent[right] = left
    return len({find(node) for node in range(2 * size)}) == 1


def check_certificate(
    name: str,
    formula: Sequence[Sequence[int]],
    record: dict[str, Any],
    columns: Sequence[Sequence[Fraction]],
    classes: Sequence[tuple[int, ...]],
) -> int:
    """Recheck a claimed frame with own coverage, independence and width."""

    claimed = [primitive(point) for point in record["frame_classes"]]
    for point in claimed:
        require(point in classes, f"{name}: claimed frame class is not a ground class")
    require(
        len(set(claimed)) == len(claimed) == record["nullity"],
        f"{name}: claimed frame is not a full ground basis",
    )
    covered = all(
        any(in_span(left, right, point) for left, right in itertools.combinations(claimed, 2))
        for point in classes
    )
    require(covered, f"{name}: claimed frame does not cover every class")
    independent = rank_of(claimed) == len(claimed)
    require(independent, f"{name}: claimed frame is dependent")
    free = sorted(record["free_set"])
    require(len(free) == len(set(free)) == record["nullity"], f"{name}: free set size mismatch")
    realized = sorted(primitive(columns[index]) for index in free)
    require(realized == sorted(claimed), f"{name}: free set does not realize the claimed frame")
    require(
        sorted({claim for claim in claimed}) == sorted(set(claimed)),
        f"{name}: claimed frame classes repeat a class",
    )
    width = width_of(columns, free)
    require(width == record["width"] == 2, f"{name}: width mismatch ({width})")
    return width


def main() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    frame_receipt = json.loads(FRAME_RECEIPT.read_text(encoding="utf-8"))
    mixed_receipt = json.loads(MIXED_RECEIPT.read_text(encoding="utf-8"))
    require(receipt["schema"] == SCHEMA, "schema mismatch")
    require(receipt["status"] == "measured", "runner status mismatch")

    reference_widths = {
        row["name"]: row["omega"]
        for row in frame_receipt["controls"] + frame_receipt["sums"]
    }
    specs = switch_specs()
    switch_formulas = [switch_formula(spec) for spec in specs]
    digests = sorted(digest(formula) for formula in switch_formulas)
    payload = json.dumps(digests, separators=(",", ":"))
    require(
        hashlib.sha256(payload.encode("ascii")).hexdigest()
        == mixed_receipt["one_switch_enumeration"]["formula_digest_sha256"],
        "switch population digest does not tie to the mixed -probe enumeration",
    )
    require(
        mixed_receipt["one_switch_enumeration"]["omega_histogram"] == {"3": len(specs)},
        "mixed-probe widths are not all three",
    )
    sampled = {
        int(record["name"].split("-")[-1]): record
        for record in receipt["cases"]
        if record["group"] == "switches"
    }

    verdict_agreements = 0
    certificate_checks = 0
    sieve_no_frame = 0
    sieve_frame = 0
    sieve_examined = 0
    sieve_dependent = 0
    search_nodes_total = 0
    class_enumeration_checks = 0
    class_no_frame = 0
    class_frame = 0
    class_universes = 0
    class_skipped = 0
    for record in receipt["cases"]:
        name = record["name"]
        group = record["group"]
        if group == "controls":
            formula = CONTROLS[name]
        elif group == "sums":
            formula = direct_sum(SUMS[name])
        elif group == "switches":
            formula = switch_formulas[int(name.split("-")[-1])]
        else:
            formula = chain_formula(name)
        rebuilt = canonical(formula)
        rank, columns, _ = kernel_columns(rebuilt)
        classes = classes_of(columns)
        nullity = len(columns[0])
        require(len(rebuilt) == record["size"], f"{name}: size mismatch")
        require(nullity == record["nullity"], f"{name}: nullity mismatch")
        require(rank == record["rank"], f"{name}: rank mismatch")
        require(len(classes) == record["classes"], f"{name}: class count mismatch")
        require(connected(rebuilt) == record["connected"], f"{name}: connectivity mismatch")

        chosen, nodes, capped = search(classes, nullity)
        search_nodes_total += nodes
        require(not capped, f"{name}: independent search hit the node cap")
        verdict = "no_frame" if chosen is None else "frame"
        require(verdict == record["verdict"], f"{name}: verdict mismatch")
        require(not record["capped"], f"{name}: receipt search was capped")
        verdict_agreements += 1
        if chosen is not None:
            basis = extend(classes, chosen, nullity)
            require(
                all(
                    any(in_span(classes[left], classes[right], point) for left, right in itertools.combinations(basis, 2))
                    for point in classes
                ),
                f"{name}: independent covering set failed its own coverage",
            )
            free = sorted(
                next(index for index, column in enumerate(columns) if primitive(column) == classes[item])
                for item in basis
            )
            require(width_of(columns, free) == 2, f"{name}: own frame does not have width two")
            certificate_checks += check_certificate(name, rebuilt, record, columns, classes)
        if group in ("controls", "sums"):
            expected = reference_widths[name]
            require(
                (verdict == "frame") == (expected == 2),
                f"{name}: verdict does not match the recorded width {expected}",
            )

        class_witnesses, class_universe = class_enumeration(classes, nullity)
        if class_witnesses is None:
            class_skipped += 1
        else:
            class_universes += class_universe
            class_enumeration_checks += 1
            if verdict == "no_frame":
                require(
                    not class_witnesses,
                    f"{name}: the class enumeration found an independent covering set",
                )
                class_no_frame += 1
            else:
                require(
                    bool(class_witnesses),
                    f"{name}: the class enumeration found no independent covering set",
                )
                class_frame += 1

        if nullity <= 6:
            witnesses, examined, dependent = sieve(columns, nullity, limit=1 if verdict == "frame" else 4)
            sieve_examined += examined
            sieve_dependent += dependent
            if verdict == "no_frame":
                require(
                    not witnesses,
                    f"{name}: the ground-element sieve found an independent covering basis",
                )
                sieve_no_frame += 1
            else:
                require(bool(witnesses), f"{name}: the ground-element sieve found no covering basis")
                sieve_frame += 1

    drawn = 0
    independent_draws = 0
    identity_agreements = 0
    width_two_draws = 0
    generator = random.Random(SAMPLE_SEED)
    for record in receipt["cases"]:
        name = record["name"]
        if record["group"] == "controls":
            formula = CONTROLS[name]
        elif record["group"] == "sums":
            formula = direct_sum(SUMS[name])
        elif record["group"] == "switches":
            formula = switch_formulas[int(name.split("-")[-1])]
        else:
            formula = chain_formula(name)
        rebuilt = canonical(formula)
        _, columns, _ = kernel_columns(rebuilt)
        classes = classes_of(columns)
        nullity = len(columns[0])
        draws = SAMPLE_DRAWS if (record["group"] == "chains" and nullity > 6) else SAMPLE_SMALL
        for _ in range(draws):
            draw = sorted(generator.sample(range(len(rebuilt)), nullity))
            drawn += 1
            if rank_of([columns[index] for index in draw]) != nullity:
                continue
            independent_draws += 1
            drawn_classes = [primitive(columns[index]) for index in draw]
            covering = all(
                any(
                    in_span(left, right, point)
                    for left, right in itertools.combinations(drawn_classes, 2)
                )
                for point in classes
            )
            narrow = width_of(columns, draw) <= 2
            require(
                narrow == covering,
                f"{name}: width and pair-join coverage disagree on a sampled basis",
            )
            identity_agreements += 1
            if narrow:
                width_two_draws += 1
            if record["verdict"] == "no_frame":
                require(not narrow, f"{name}: a sampled basis reached width two")
    require(drawn >= SAMPLE_SMALL * len(receipt["cases"]), "random draw count mismatch")

    criteria = receipt["criteria"]
    require(
        criteria["expected_verdicts_matched"] == criteria["expected_verdicts_total"] == len(receipt["cases"]),
        "expected verdict accounting mismatch",
    )
    require(
        criteria["connected_chains"] == 9
        and sum(record["connected"] for record in receipt["cases"] if record["group"] == "chains") == 9,
        "chain connectivity accounting mismatch",
    )
    require(criteria["chain_sizes"] == [24, 27, 30, 36, 36, 39, 45, 48, 60], "chain sizes mismatch")
    require(criteria["largest_chain_nullity"] == 9, "largest nullity mismatch")
    require(criteria["largest_chain_census_size"] == math.comb(60, 9), "census size mismatch")
    require(criteria["switch_population"] == len(specs) == 1620, "switch population mismatch")
    require(criteria["switch_sample"] == len(sampled), "switch sample mismatch")
    require(criteria["no_hardness_claim"] is True, "no-hardness marker missing")

    print(json.dumps({
        "schema": SCHEMA,
        "cases_verified": len(receipt["cases"]),
        "verdict_agreements": verdict_agreements,
        "certificates_verified": certificate_checks,
        "class_enumeration_checks": class_enumeration_checks,
        "class_enumeration_no_frame": class_no_frame,
        "class_enumeration_frame": class_frame,
        "class_universes_examined": class_universes,
        "class_universes_skipped": class_skipped,
        "sieve_no_frame_agreements": sieve_no_frame,
        "sieve_frame_agreements": sieve_frame,
        "sieve_subsets_examined": sieve_examined,
        "sieve_dependent_coverings": sieve_dependent,
        "independent_search_nodes": search_nodes_total,
        "random_draws": drawn,
        "random_independent_draws": independent_draws,
        "sampled_width_identity_agreements": identity_agreements,
        "sampled_width_two_draws": width_two_draws,
        "switch_population_digest_sha256": hashlib.sha256(payload.encode("ascii")).hexdigest(),
        "status": "verified",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
