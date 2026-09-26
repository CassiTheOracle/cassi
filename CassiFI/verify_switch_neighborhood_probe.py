"""Independent verifier for the switch-neighborhood receipt.

This verifier imports neither the runner nor any CassiFI implementation module.
It rebuilds the two all-bases controls, canonical cubic formulas, incidence
switches, rational kernel coordinates, projective classes, exact free-basis
censuses, and a differently ordered class search.  It replays every complete
one-switch neighborhood and every seeded two-switch walk, rechecks each stored
frame witness, and rebuilds all reported histograms and digests.
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

RECEIPT = Path("_diag/switch_neighborhood_probe.json")
SCHEMA = "cassifi.switch-neighborhood-probe.v1"
SEED = 20260910
WALKS_PER_CONTROL = 400
NODE_CAP = 200_000

ALL_BASES_TERNARY_SAT = (
    (1, 2, 7), (1, 4, 10), (1, 6, 10), (2, 7, 9), (2, 11, 12), (3, 4, 11),
    (3, 6, 7), (3, 8, 12), (4, 9, 10), (5, 6, 11), (5, 8, 9), (5, 8, 12),
)
ALL_BASES_TERNARY_UNSAT = (
    (1, 3, 7), (1, 6, 12), (1, 7, 8), (2, 3, 6), (2, 10, 13), (2, 13, 15),
    (3, 4, 12), (4, 7, 9), (4, 11, 12), (5, 8, 10), (5, 11, 15),
    (5, 13, 14), (6, 9, 14), (8, 11, 14), (9, 10, 15),
)
CONTROLS = {
    "all-bases-ternary-sat-n12": ALL_BASES_TERNARY_SAT,
    "all-bases-ternary-unsat-n15": ALL_BASES_TERNARY_UNSAT,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical(formula: Sequence[Sequence[int]]) -> tuple[tuple[int, int, int], ...]:
    """Canonicalize and validate a cubic 3-regular incidence formula."""

    size = len(formula)
    require(size >= 3, "formula needs at least three clauses")
    occurrences = [0] * size
    clauses: list[tuple[int, int, int]] = []
    for clause in formula:
        ordered = tuple(sorted(int(value) for value in clause))
        require(len(ordered) == 3 and len(set(ordered)) == 3, "invalid cubic clause")
        require(all(1 <= value <= size for value in ordered), "variable outside formula")
        for value in ordered:
            occurrences[value - 1] += 1
        clauses.append(ordered)
    require(all(value == 3 for value in occurrences), "formula is not 3-regular")
    return tuple(sorted(clauses))


def kernel_columns(
    formula: Sequence[Sequence[int]],
) -> tuple[int, tuple[tuple[Fraction, ...], ...]]:
    """Compute rational kernel-coordinate columns by fresh Gauss-Jordan elimination."""

    size = len(formula)
    matrix = [
        [Fraction(int(variable in clause)) for variable in range(1, size + 1)]
        for clause in formula
    ]
    pivots: list[int] = []
    free: list[int] = []
    row = 0
    for column in range(size):
        source = next((candidate for candidate in range(row, size) if matrix[candidate][column]), None)
        if source is None:
            free.append(column)
            continue
        matrix[row], matrix[source] = matrix[source], matrix[row]
        divisor = matrix[row][column]
        matrix[row] = [value / divisor for value in matrix[row]]
        for candidate in range(size):
            if candidate == row or not matrix[candidate][column]:
                continue
            factor = matrix[candidate][column]
            matrix[candidate] = [
                value - factor * pivot
                for value, pivot in zip(matrix[candidate], matrix[row], strict=True)
            ]
        pivots.append(column)
        row += 1

    basis: list[list[Fraction]] = []
    for free_column in free:
        vector = [Fraction(0)] * size
        vector[free_column] = Fraction(1)
        for pivot_row, pivot_column in enumerate(pivots):
            vector[pivot_column] = -matrix[pivot_row][free_column]
        basis.append(vector)
    columns = tuple(
        tuple(basis[coordinate][element] for coordinate in range(len(free)))
        for element in range(size)
    )
    return len(pivots), columns


def primitive(values: Sequence[Fraction | int]) -> tuple[int, ...]:
    scaled = [Fraction(value) for value in values]
    denominator_lcm = 1
    for value in scaled:
        denominator_lcm = math.lcm(denominator_lcm, value.denominator)
    integers = [int(value * denominator_lcm) for value in scaled]
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
    classes: list[tuple[int, ...]] = []
    for column in columns:
        point = primitive(column)
        if any(point) and point not in classes:
            classes.append(point)
    return classes


def rank_of(vectors: Sequence[Sequence[Fraction | int]]) -> int:
    rows = [[Fraction(value) for value in vector] for vector in vectors if any(vector)]
    if not rows:
        return 0
    width = len(rows[0])
    rank = 0
    for column in range(width):
        source = next((row for row in range(rank, len(rows)) if rows[row][column]), None)
        if source is None:
            continue
        rows[rank], rows[source] = rows[source], rows[rank]
        pivot = rows[rank][column]
        for row in range(rank + 1, len(rows)):
            if not rows[row][column]:
                continue
            factor = rows[row][column] / pivot
            rows[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(rows[row], rows[rank], strict=True)
            ]
        rank += 1
        if rank == len(rows):
            break
    return rank


def in_span(left: Sequence[int], right: Sequence[int], point: Sequence[int]) -> bool:
    return rank_of((left, right, point)) <= 2


def invert(matrix: Sequence[Sequence[Fraction]]) -> list[list[Fraction]]:
    size = len(matrix)
    augmented = [
        [Fraction(value) for value in row]
        + [Fraction(int(row_index == column)) for column in range(size)]
        for row_index, row in enumerate(matrix)
    ]
    for column in range(size):
        source = next((row for row in range(column, size) if augmented[row][column]), None)
        require(source is not None, "free-set basis is singular")
        augmented[column], augmented[source] = augmented[source], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column or not augmented[row][column]:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                value - factor * pivot
                for value, pivot in zip(augmented[row], augmented[column], strict=True)
            ]
    return [row[size:] for row in augmented]


def width_of(columns: Sequence[Sequence[Fraction]], free: Sequence[int]) -> int:
    width = len(free)
    if width == 0:
        return 0
    basis = [
        [columns[free[column]][coordinate] for column in range(width)]
        for coordinate in range(width)
    ]
    inverse = invert(basis)
    largest = 0
    for column in columns:
        coordinates = [
            sum(inverse[row][column_index] * column[column_index] for column_index in range(width))
            for row in range(width)
        ]
        largest = max(largest, sum(value != 0 for value in coordinates))
    return largest


def census_width(columns: Sequence[Sequence[Fraction]]) -> int:
    """Exhaustively minimize coordinate support over every free-element basis."""

    nullity = len(columns[0]) if columns else 0
    if nullity == 0:
        return 0
    best = nullity
    for free in itertools.combinations(range(len(columns)), nullity):
        if rank_of([columns[index] for index in free]) != nullity:
            continue
        best = min(best, width_of(columns, free))
        if best == 1:
            break
    return best


def triangle_exists(classes: Sequence[tuple[int, ...]]) -> bool:
    """Nullity-three element-triangle criterion, expressed by pair spans."""

    return any(
        all(
            any(in_span(left, right, point) for left, right in itertools.combinations(triple, 2))
            for point in classes
        )
        for triple in itertools.combinations(classes, 3)
    )


def pair_masks(classes: Sequence[tuple[int, ...]]) -> tuple[list[tuple[int, int]], list[int], int]:
    pairs = list(itertools.combinations(range(len(classes)), 2))
    masks: list[int] = []
    for left, right in pairs:
        mask = 0
        for target, point in enumerate(classes):
            if in_span(classes[left], classes[right], point):
                mask |= 1 << target
        masks.append(mask)
    by_target = [
        [index for index, mask in enumerate(masks) if mask & (1 << target)]
        for target in range(len(classes))
    ]
    return pairs, by_target, (1 << len(classes)) - 1


def search(
    classes: Sequence[tuple[int, ...]], nullity: int, node_cap: int = NODE_CAP
) -> tuple[list[int] | None, int, bool]:
    """Independent highest-uncovered-first class search."""

    if nullity <= 2:
        basis: list[int] = []
        for index, point in enumerate(classes):
            if rank_of([classes[item] for item in basis + [index]]) == len(basis) + 1:
                basis.append(index)
            if len(basis) == nullity:
                return basis, 0, False
        return None, 0, False

    pairs, by_target, full = pair_masks(classes)
    nodes = 0
    capped = False

    def recurse(chosen: list[int]) -> list[int] | None:
        nonlocal nodes, capped
        nodes += 1
        if nodes > node_cap:
            capped = True
            return None
        chosen_set = set(chosen)
        covered = 0
        for pair_index, (left, right) in enumerate(pairs):
            if left in chosen_set and right in chosen_set:
                covered |= pair_masks_cache[pair_index]
        uncovered = full & ~covered
        if not uncovered:
            return chosen if rank_of([classes[index] for index in chosen]) == len(chosen) else None
        if len(chosen) == nullity:
            return None
        target = uncovered.bit_length() - 1
        for pair_index in reversed(by_target[target]):
            left, right = pairs[pair_index]
            trial = list(chosen)
            for index in (left, right):
                if index not in trial:
                    trial.append(index)
            if len(trial) > nullity:
                continue
            if rank_of([classes[index] for index in trial]) != len(trial):
                continue
            result = recurse(trial)
            if result is not None:
                return result
            if capped:
                return None
        return None

    pair_masks_cache = []
    for left, right in pairs:
        mask = 0
        for target, point in enumerate(classes):
            if in_span(classes[left], classes[right], point):
                mask |= 1 << target
        pair_masks_cache.append(mask)
    return recurse([]), nodes, capped


def switch_specs(formula: Sequence[Sequence[int]]) -> list[tuple[int, int, int, int]]:
    specs: list[tuple[int, int, int, int]] = []
    for left_row, right_row in itertools.combinations(range(len(formula)), 2):
        left, right = set(formula[left_row]), set(formula[right_row])
        for variable in sorted(left - right):
            for partner in sorted(right - left):
                specs.append((left_row, right_row, variable, partner))
    return specs


def apply_spec(
    formula: Sequence[Sequence[int]], spec: tuple[int, int, int, int]
) -> tuple[tuple[int, int, int], ...]:
    left_row, right_row, variable, partner = spec
    clauses = [list(clause) for clause in formula]
    clauses[left_row][clauses[left_row].index(variable)] = partner
    clauses[right_row][clauses[right_row].index(partner)] = variable
    return canonical(tuple(tuple(sorted(clause)) for clause in clauses))


def digest(formula: Sequence[Sequence[int]]) -> str:
    canonical_formula = canonical(formula)
    payload = "|".join(",".join(str(value) for value in clause) for clause in canonical_formula)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def element_for_class(
    columns: Sequence[Sequence[Fraction]], point: tuple[int, ...]
) -> int:
    for index, column in enumerate(columns):
        if primitive(column) == point:
            return index
    raise AssertionError("class has no ground representative")


def evaluate(formula: Sequence[Sequence[int]]) -> dict[str, Any]:
    rebuilt = canonical(formula)
    matrix_rank, columns = kernel_columns(rebuilt)
    classes = classes_of(columns)
    nullity = len(columns[0]) if columns else 0
    omega = census_width(columns)
    record: dict[str, Any] = {
        "formula": rebuilt,
        "size": len(rebuilt),
        "rank": matrix_rank,
        "nullity": nullity,
        "classes": len(classes),
        "digest": digest(rebuilt),
        "columns": columns,
        "classes_values": classes,
        "omega": omega,
        "nodes": 0,
        "capped": False,
        "trivial": False,
        "triangle": triangle_exists(classes) if nullity == 3 else None,
    }
    if nullity <= 2:
        free: list[int] = []
        for point in classes:
            index = element_for_class(columns, point)
            if rank_of([columns[item] for item in free + [index]]) != len(free) + 1:
                continue
            free.append(index)
            if len(free) == nullity:
                break
        require(len(free) == nullity, "trivial frame could not find an independent free set")
        width = width_of(columns, free)
        require(width <= 2, "trivial frame exceeds width two")
        record.update(
            {
                "verdict": "frame",
                "trivial": True,
                "free_set": free,
                "width": width,
            }
        )
        return record
    chosen, nodes, capped = search(classes, nullity)
    record["nodes"] = nodes
    record["capped"] = capped
    record["verdict"] = "inconclusive" if capped else ("frame" if chosen is not None else "no_frame")
    return record


def check_frame_row(row: dict[str, Any], measured: dict[str, Any], context: str) -> None:
    if row["verdict"] != "frame":
        require("free_set" not in row, f"{context}: non-frame row carries a witness")
        return
    require(measured["omega"] <= 2, f"{context}: frame verdict has census width {measured['omega']}")
    free = row.get("free_set")
    require(isinstance(free, list), f"{context}: missing free set")
    require(len(free) == len(set(free)) == measured["nullity"], f"{context}: free-set size")
    require(all(isinstance(index, int) and 0 <= index < measured["size"] for index in free), f"{context}: free-set index")
    columns = measured["columns"]
    require(rank_of([columns[index] for index in free]) == measured["nullity"], f"{context}: dependent free set")
    width = width_of(columns, free)
    require(width == row.get("width") and width <= 2, f"{context}: witness width {width}")
    require(row.get("trivial") is (measured["nullity"] <= 2), f"{context}: trivial marker")


def check_base(row: dict[str, Any], measured: dict[str, Any], name: str) -> None:
    for field in ("size", "rank", "nullity", "classes", "digest", "omega", "verdict", "triangle"):
        require(row[field] == measured[field if field != "verdict" else "verdict"], f"{name}: base {field}")
    require(row["capped"] is False and isinstance(row["nodes"], int) and row["nodes"] >= 0, f"{name}: base search metadata")
    require(row["trivial"] is False, f"{name}: base unexpectedly trivial")


def check_neighborhood(
    control: dict[str, Any], formula: Sequence[Sequence[int]], name: str
) -> tuple[dict[str, tuple[tuple[int, int, int, int], tuple[tuple[int, int, int], ...]]], int]:
    base = canonical(formula)
    measured_base = evaluate(base)
    check_base(control["base"], measured_base, name)

    specs = switch_specs(base)
    unique: dict[str, tuple[tuple[int, int, int, int], tuple[tuple[int, int, int], ...]]] = {}
    for spec in specs:
        switched = apply_spec(base, spec)
        unique.setdefault(digest(switched), (spec, switched))
    require(control["size"] == len(base), f"{name}: size")
    require(control["spec_count"] == len(specs), f"{name}: legal-switch count")
    require(control["neighbor_count"] == len(unique), f"{name}: unique-neighbor count")
    rows = control.get("neighbors")
    require(isinstance(rows, list) and len(rows) == len(unique), f"{name}: complete neighbor rows missing")

    omega_histogram: dict[str, int] = {}
    verdict_histogram: dict[str, int] = {}
    triangle_checked = 0
    triangle_agreements = 0
    nodes_total = 0
    expected_frame_rows = []
    expected_no_frame_rows = []
    for row, key in zip(rows, sorted(unique), strict=True):
        spec, switched = unique[key]
        measured = evaluate(switched)
        require(row["digest"] == key and row["switch"] == list(spec), f"{name}: neighbor identity")
        for field in ("size", "rank", "nullity", "classes", "omega", "triangle", "verdict"):
            require(row[field] == measured[field], f"{name}: neighbor {field}")
        require(row["capped"] is False, f"{name}: neighbor search capped")
        require(isinstance(row["nodes"], int) and row["nodes"] >= 0, f"{name}: neighbor nodes")
        check_frame_row(row, measured, f"{name}:{key[:12]}")
        omega_key = str(measured["omega"])
        omega_histogram[omega_key] = omega_histogram.get(omega_key, 0) + 1
        verdict_histogram[measured["verdict"]] = verdict_histogram.get(measured["verdict"], 0) + 1
        nodes_total += row["nodes"]
        if measured["triangle"] is not None:
            triangle_checked += 1
            triangle_agreements += measured["triangle"] == (measured["verdict"] == "frame")
        if measured["verdict"] == "frame":
            expected_frame_rows.append({
                "switch": list(spec),
                "free_set": row["free_set"],
                "width": row["width"],
                "trivial": row["trivial"],
                "nodes": row["nodes"],
            })
        else:
            expected_no_frame_rows.append({"switch": list(spec), "nodes": row["nodes"]})

    require(control["omega_histogram"] == dict(sorted(omega_histogram.items())), f"{name}: omega histogram")
    require(control["verdict_histogram"] == dict(sorted(verdict_histogram.items())), f"{name}: verdict histogram")
    require(control["nodes_total"] == nodes_total, f"{name}: node aggregate")
    agreements = sum(row["verdict"] == ("frame" if row["omega"] <= 2 else "no_frame") for row in rows)
    require(control["census_search_agreements"] == agreements == len(rows), f"{name}: census/search agreement")
    require(control["triangle_checked"] == triangle_checked, f"{name}: triangle count")
    require(control["triangle_agreements"] == triangle_agreements == triangle_checked, f"{name}: triangle agreement")
    require(control["frame_neighbors"] == expected_frame_rows, f"{name}: frame-row projection")
    require(control["no_frame_neighbors"] == expected_no_frame_rows, f"{name}: no-frame projection")
    return unique, len(rows)


def check_walks(
    control: dict[str, Any],
    formula: Sequence[Sequence[int]],
    unique_neighbors: dict[str, tuple[tuple[int, int, int, int], tuple[tuple[int, int, int], ...]]],
    position: int,
    name: str,
) -> int:
    walks = control["walks"]
    require(control["walk_seed"] == SEED + 1 + position, f"{name}: walk seed")
    require(walks["walks"] == WALKS_PER_CONTROL, f"{name}: walk count")
    rng = random.Random(control["walk_seed"])
    base = canonical(formula)
    draws: list[str] = []
    intermediate: list[dict[str, Any]] = []
    final_formulas: dict[str, tuple[tuple[int, int, int], ...]] = {}
    multiplicities: dict[str, int] = {}
    neighbor_formulas = {key: value[1] for key, value in unique_neighbors.items()}
    for _ in range(WALKS_PER_CONTROL):
        current = base
        step_digests: list[str] = []
        for _ in range(2):
            specs = switch_specs(current)
            spec = specs[rng.randrange(len(specs))]
            current = apply_spec(current, spec)
            step_digests.append(digest(current))
        draws.extend(step_digests)
        require(step_digests[0] in neighbor_formulas, f"{name}: walk left neighborhood")
        intermediate.append(evaluate(neighbor_formulas[step_digests[0]]))
        final_formulas.setdefault(step_digests[1], current)
        multiplicities[step_digests[1]] = multiplicities.get(step_digests[1], 0) + 1

    digest_payload = "|".join(draws)
    require(
        walks["draw_sequence_sha256"]
        == hashlib.sha256(digest_payload.encode("ascii")).hexdigest(),
        f"{name}: walk digest",
    )
    finals = walks.get("finals")
    require(isinstance(finals, list) and len(finals) == len(final_formulas), f"{name}: final rows")
    final_measured: list[dict[str, Any]] = []
    for row, key in zip(finals, sorted(final_formulas), strict=True):
        require(row["digest"] == key, f"{name}: final digest ordering")
        measured = evaluate(final_formulas[key])
        final_measured.append(measured)
        for field in ("size", "rank", "nullity", "classes", "omega", "triangle", "verdict"):
            require(row[field] == measured[field], f"{name}: final {field}")
        require(row["walks"] == multiplicities[key], f"{name}: final multiplicity")
        require(row["capped"] is False and isinstance(row["nodes"], int) and row["nodes"] >= 0, f"{name}: final metadata")
        check_frame_row(row, measured, f"{name}:final:{key[:12]}")

    omega_histogram: dict[str, int] = {}
    verdict_histogram: dict[str, int] = {}
    for measured in final_measured:
        omega_histogram[str(measured["omega"])] = omega_histogram.get(str(measured["omega"]), 0) + 1
        verdict_histogram[measured["verdict"]] = verdict_histogram.get(measured["verdict"], 0) + 1
    require(walks["unique_finals"] == len(finals), f"{name}: unique final count")
    require(walks["omega_histogram"] == dict(sorted(omega_histogram.items())), f"{name}: final omega histogram")
    require(walks["verdict_histogram"] == dict(sorted(verdict_histogram.items())), f"{name}: final verdict histogram")
    agreements = sum(measured["verdict"] == ("frame" if measured["omega"] <= 2 else "no_frame") for measured in final_measured)
    require(walks["census_search_agreements"] == agreements == len(finals), f"{name}: final agreement")

    intermediate_histogram: dict[str, int] = {}
    for measured in intermediate:
        key = str(measured["omega"])
        intermediate_histogram[key] = intermediate_histogram.get(key, 0) + 1
    require(walks["intermediate_omega_histogram"] == dict(sorted(intermediate_histogram.items())), f"{name}: intermediate histogram")
    require(
        walks["intermediate_width_two"] == sum(measured["omega"] == 2 for measured in intermediate),
        f"{name}: intermediate width-two count",
    )
    require(
        walks["frames"]
        == [
            {"free_set": row["free_set"], "nodes": row["nodes"]}
            for row in finals
            if row["verdict"] == "frame"
        ],
        f"{name}: frame projection",
    )
    require(walks["nodes_total"] == sum(row["nodes"] for row in finals), f"{name}: node aggregate")

    return len(finals)
def synthetic_anchors() -> None:
    positive = (
        (1, 0, 0), (0, 1, 0), (0, 0, 1),
        (1, 1, 0), (1, 0, 1), (0, 1, 1),
    )
    negative = (
        (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1),
        (1, 2, 3), (1, 3, 2), (2, 1, 3),
    )
    positive_result, _, positive_capped = search(list(positive), 3)
    negative_result, _, negative_capped = search(list(negative), 3)
    require(positive_result is not None and not positive_capped, "positive synthetic anchor failed")
    require(negative_result is None and not negative_capped, "negative synthetic anchor was framed")

def main() -> None:
    synthetic_anchors()
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(receipt["schema"] == SCHEMA, "schema mismatch")
    require(receipt["seed"] == SEED and receipt["walks_per_control"] == WALKS_PER_CONTROL, "seed/count mismatch")
    controls = receipt.get("controls")
    require(isinstance(controls, list) and [row["control"] for row in controls] == list(CONTROLS), "control set/order mismatch")

    neighbor_total = 0
    final_total = 0
    union_digests: set[str] = set()
    for position, (control, (name, formula)) in enumerate(zip(controls, CONTROLS.items(), strict=True)):
        require(control["control"] == name, f"control {position} name mismatch")
        unique, count = check_neighborhood(control, formula, name)
        neighbor_total += count
        union_digests.update(unique)
        final_total += check_walks(control, formula, unique, position, name)
    require(receipt["cache_size"] == len(union_digests), "cache-size mismatch")

    print(json.dumps({
        "schema": SCHEMA,
        "status": "verified",
        "synthetic_anchors": 2,
        "controls_verified": len(controls),
        "neighbors_verified": neighbor_total,
        "walk_finals_verified": final_total,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
