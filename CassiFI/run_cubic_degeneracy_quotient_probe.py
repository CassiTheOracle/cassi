"""Measure exact quotient behavior for the four Result AA basis families.

The probe selects the lexicographically first formula in each canonical
width-two family, applies every measured exclusive-pair quotient, checks the
complete Boolean solution projection, and follows deterministic reductions to
a constructive width-two terminal.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

import cubic_kernel_decision as production

SCHEMA = "cassifi.cubic-degeneracy-quotient-probe.v1"
ROOT = Path(__file__).resolve().parent
AA_PATH = ROOT / "_diag/cubic_degeneracy_structure_probe.json"
LIFT_PATH = ROOT / "_diag/cubic_lift_realization_probe.json"
OUTPUT = ROOT / "_diag/cubic_degeneracy_quotient_probe.json"

Vector = tuple[Fraction, ...]


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")
    ).hexdigest()


def affine_profile(
    matrix: Sequence[Sequence[Fraction]], rhs: Sequence[Fraction]
) -> dict[str, Any]:
    column_count = len(matrix[0]) if matrix else 0
    augmented = [list(row) + [value] for row, value in zip(matrix, rhs, strict=True)]
    reduced, pivots, _ = production._rref(augmented)
    if column_count in pivots:
        return {
            "consistent": False,
            "rank": len(pivots) - 1,
            "nullity": 0,
            "particular": tuple(),
            "vectors": tuple(),
        }
    coefficient_pivots = tuple(pivot for pivot in pivots if pivot < column_count)
    free = tuple(
        column for column in range(column_count) if column not in coefficient_pivots
    )
    pivot_rows = {pivot: row for row, pivot in enumerate(coefficient_pivots)}
    particular = []
    vectors = []
    free_positions = {column: index for index, column in enumerate(free)}
    for column in range(column_count):
        if column in free_positions:
            index = free_positions[column]
            particular.append(Fraction(0))
            vectors.append(
                tuple(Fraction(int(position == index)) for position in range(len(free)))
            )
        else:
            row = pivot_rows[column]
            particular.append(reduced[row][-1])
            vectors.append(tuple(-reduced[row][free_column] for free_column in free))
    return {
        "consistent": True,
        "rank": len(coefficient_pivots),
        "nullity": len(free),
        "particular": tuple(particular),
        "vectors": tuple(vectors),
    }


def basis_rows(vectors: tuple[Vector, ...]) -> tuple[tuple[tuple[int, ...], int], ...]:
    if not vectors:
        return ((tuple(), 0),)
    dimension = len(vectors[0])
    if dimension == 0:
        return ((tuple(), 0),)

    n = len(vectors)
    # Precompute ranks for all combinations to avoid repeated expensive calls
    # We map a frozenset of indices to its rank
    rank_cache: dict[frozenset[int], int] = {}

    # Helper to get rank
    def get_rank(indices: tuple[int, ...]) -> int:
        key = frozenset(indices)
        if key in rank_cache:
            return rank_cache[key]
        res = production._vector_rank(tuple(vectors[i] for i in indices))
        rank_cache[key] = res
        return res

    # Precompute ranks for all combinations of size 'dimension'
    # This is O(C(n, d) * cost_of_rank), but saves us from doing it repeatedly in the main loop
    # Actually, we only need to do this once per call, which is what we are doing now,
    # but the original code does it inside the loop? No, the original code calls it inside the loop.
    # Wait, the original code calls production._vector_rank(selected_vectors) inside the loop.
    # The loop iterates over combinations. So it calls rank once per combination.
    # The issue is that if this function is called multiple times with the same vectors,
    # we are recomputing everything. But the rules say "Never cache a call's result for reuse by a later call with the same arguments".
    # This implies we cannot cache across calls to basis_rows.
    # HOWEVER, within a single call to basis_rows, we iterate over combinations.
    # The original code calls _vector_rank for each combination.
    # Is there redundancy? No, each combination is unique.
    # So the optimization must be elsewhere.

    # Let's re-read the profile.
    # Top caller: <built-in method builtins.max> (267 calls, 0.1362 s)
    # This is strange. There are only 1588 calls to the generator.
    # The max is called inside the width calculation.
    # width = max(...)
    # The generator runs 1588 times. Each time it calls max.
    # The max iterates over 'vectors' (n vectors).
    # So for each valid basis, we do n calls to _basis_coordinates.
    # _basis_coordinates likely iterates over the basis vectors.
    # The total complexity is O(C(n, d) * n * d).
    # If n is large, C(n, d) is huge.
    # But wait, the profile says 1588 calls to the generator.
    # This means the loop over combinations ran 1588 times and found 1588 valid bases?
    # Or maybe the generator is the loop itself?
    # "run_cubic_degeneracy_quotient_probe:<genexpr>" -> 1588 calls.
    # This suggests the generator expression inside max is being evaluated 1588 times?
    # No, max consumes the generator. So max is called 1588 times (once per valid basis).
    # And inside max, for each vector in 'vectors', it calls _basis_coordinates.
    # So total calls to _basis_coordinates is 1588 * n.
    # If n is around 20-30, that's 30k-50k calls.
    # But the profile says max took 0.1362s.
    # The other top caller is _vector_rank with 418 calls.
    # This implies only 418 combinations had rank == dimension.
    # So the loop over combinations found 418 valid bases.
    # And for those 418 bases, it computed the width.
    # The width calculation involves iterating over ALL vectors (n vectors).
    # So the bottleneck is likely the width calculation: 418 * n * cost_of_basis_coord.
    # Or maybe the combinations loop is too slow?
    # 418 calls to _vector_rank is small.
    # The 1588 calls to the generator (max) is the width calculation.
    # So we have 418 valid bases. For each, we iterate n vectors.
    # If n is large, this is the bottleneck.

    # Optimization:
    # 1. Precompute the rank check is already done once per combination.
    # 2. The width calculation is the heavy part.
    #    width = max( sum(coordinate != 0 for coordinate in production._basis_coordinates(selected_vectors, vector)) for vector in vectors )
    #    This sums the number of non-zero coordinates in the expansion of 'vector' in terms of 'selected_vectors'.
    #    This is equivalent to the L0 norm of the coordinate vector.
    #    Can we optimize this?
    #    _basis_coordinates likely solves a linear system or uses Gaussian elimination.
    #    If we can precompute something, maybe?
    #    But the rules say no caching across calls.
    #    However, we can precompute the rank of all subsets of size < dimension? No, that's more work.
    #    Maybe we can optimize the width calculation.
    #    Notice that 'selected_vectors' is a basis.
    #    The coordinates of 'vector' in this basis are unique.
    #    We are summing the number of non-zero entries.
    #    Is there a way to avoid calling _basis_coordinates for every vector?
    #    Probably not, unless we have a faster way to compute the representation.

    # Wait, let's look at the profile again.
    # "cubic_kernel_decision:_vector_rank" (418 calls).
    # This confirms only 418 combinations passed the rank check.
    # So the loop over combinations (itertools.combinations) is fast enough (418 iterations).
    # The bottleneck is the width calculation for these 418 bases.
    # For each base, we iterate over ALL vectors (n vectors).
    # If n is large, say 100, then 418 * 100 = 41800 calls to _basis_coordinates.
    # If _basis_coordinates is expensive, this is the problem.

    # How to optimize?
    # We cannot cache across calls.
    # But maybe we can avoid calling _basis_coordinates for vectors that are clearly dependent?
    # No, we need the width for ALL vectors.
    # Wait, the width is defined as the max over all vectors of the number of non-zero coordinates.
    # This is the maximum sparsity of the representation? No, number of non-zeros.
    # So it's the maximum "weight" of the representation.

    # Is there any redundancy?
    # If 'vector' is one of the 'selected_vectors', the representation is a unit vector, so weight is 1.
    # So for the vectors in 'selected_vectors', the weight is 1.
    # We only need to check vectors NOT in 'selected_vectors'.
    # This saves n - dimension checks per base.
    # If dimension is small compared to n, this is a significant saving.
    # Let's implement this.

    rows = []
    # Precompute the set of indices for quick lookup
    # Actually, we can just check if index in selected.

    for selected in itertools.combinations(range(n), dimension):
        selected_vectors = tuple(vectors[i] for i in selected)
        if production._vector_rank(selected_vectors) != dimension:
            continue

        # Optimization: The vectors in 'selected' have weight 1 in this basis.
        # So the max is at least 1.
        # We only need to check vectors not in 'selected'.

        current_max = 1  # Since selected vectors have weight 1

        # We need to find the vector with the maximum weight.
        # Iterate over all vectors, skip those in selected.
        # To skip efficiently, convert selected to a set.
        selected_set = set(selected)

        # We can try to optimize the loop.
        # But the main cost is _basis_coordinates.
        # Is there any other optimization?
        # Maybe we can break early if we find a vector with weight > current_max?
        # No, we need the max.
        # But if we find a vector with weight equal to the maximum possible (which is dimension?), we can stop?
        # The maximum possible weight is dimension (if all coordinates are non-zero).
        # So if we find a vector with weight == dimension, we can stop and set current_max = dimension.
        # This is a good heuristic.

        for vector in vectors:
            if vector in vectors and vector in selected:
                # Wait, 'vector' is the whole vector tuple, 'selected' is indices.
                # We need to check if the vector at index 'i' is in 'selected'.
                # But 'vector' is the value, not the index.
                # We should iterate by index to know if it's in selected.
                pass

        # Correct loop:
        for idx, vector in enumerate(vectors):
            if idx in selected_set:
                continue
            weight = sum(coordinate != 0 for coordinate in production._basis_coordinates(selected_vectors, vector))
            if weight > current_max:
                current_max = weight
                # Optimization: if current_max reaches dimension, we can't do better.
                if current_max == dimension:
                    break

        rows.append((tuple(i + 1 for i in selected), current_max))

    return tuple(rows)


def exclusive_pairs(rows: Sequence[tuple[tuple[int, ...], int]], size: int) -> list[tuple[int, int]]:
    width_two = tuple(basis for basis, width in rows if width <= 2)
    pairs = []
    for left, right in itertools.combinations(range(1, size + 1), 2):
        states = {
            f"{int(left in basis)}{int(right in basis)}" for basis in width_two
        }
        if states == {"01", "10"}:
            pairs.append((left, right))
    return pairs


def boolean_solutions(
    matrix: Sequence[Sequence[Fraction]], rhs: Sequence[Fraction]
) -> tuple[tuple[int, ...], ...]:
    size = len(matrix[0]) if matrix else 0
    if size == 0:
        return ()

    # Calculate the LCM of all denominators to convert Fractions to integers
    from math import gcd

    def lcm(a: int, b: int) -> int:
        if a == 0 or b == 0:
            return 0
        return abs(a * b) // gcd(a, b)

    common_denom = 1
    for row in matrix:
        for f in row:
            common_denom = lcm(common_denom, f.denominator)
    for f in rhs:
        common_denom = lcm(common_denom, f.denominator)

    # Convert matrix and rhs to integer representations
    # int_matrix[i][j] = matrix[i][j] * common_denom
    int_matrix = [[int(c * common_denom) for c in row] for row in matrix]
    int_rhs = [int(t * common_denom) for t in rhs]

    num_eqs = len(int_matrix)
    solutions = []

    # Precompute indices for speed
    indices = range(size)

    # Iterate over all boolean assignments
    for assignment in itertools.product((0, 1), repeat=size):
        match = True
        for i in range(num_eqs):
            target = int_rhs[i]
            current_sum = 0
            row = int_matrix[i]
            # Dot product: sum(row[j] * assignment[j])
            # Since assignment[j] is 0 or 1, we can just add row[j] if assignment[j] is 1
            for j in indices:
                if assignment[j]:
                    current_sum += row[j]
            if current_sum != target:
                match = False
                break
        if match:
            solutions.append(assignment)

    return tuple(solutions)


def pair_projection_allowed(profile: dict[str, Any], left: int, right: int) -> tuple[tuple[int, int], ...]:
    particular = profile["particular"]
    vectors = profile["vectors"]
    allowed = []
    for pair in itertools.product((0, 1), repeat=2):
        equations = (vectors[left], vectors[right])
        targets = (
            Fraction(pair[0]) - particular[left],
            Fraction(pair[1]) - particular[right],
        )
        coefficient_rank = production._vector_rank(equations)
        augmented_rank = production._vector_rank(
            tuple(vector + (target,) for vector, target in zip(equations, targets, strict=True))
        )
        if coefficient_rank == augmented_rank:
            allowed.append(pair)
    return tuple(allowed)


def substitute_pair(
    matrix: Sequence[Sequence[Fraction]],
    rhs: Sequence[Fraction],
    left: int,
    right: int,
    category: str,
    profile: dict[str, Any],
) -> tuple[list[list[Fraction]], list[Fraction], dict[str, Any]]:
    size = len(matrix[0])
    survivors = [index for index in range(size) if index not in (left, right)]
    old_to_new = {old: new for new, old in enumerate(survivors)}
    offset = [Fraction(0) for _ in range(size)]
    transform = [
        [Fraction(0) for _ in range(len(survivors) + 1)] for _ in range(size)
    ]
    for old, new in old_to_new.items():
        transform[old][new] = Fraction(1)
    relation: dict[str, Any]
    if category == "primal_twins":
        transform[left][-1] = Fraction(1)
        relation = {
            "kind": "twin_sum_canonical_lift",
            "allowed_original_pairs": [[0, 0], [1, 0], [0, 1]],
            "canonical_parameter_pairs": [[0, 0], [1, 0]],
        }
    else:
        allowed = pair_projection_allowed(profile, left, right)
        if len(allowed) > 2:
            raise AssertionError(f"parallel pair has nonfunctional Boolean projection {allowed}")
        if not allowed:
            return [[Fraction(0)]], [Fraction(1)], {
                "kind": "contradiction",
                "allowed_original_pairs": [],
            }
        if len(allowed) == 1:
            transform = [row[:-1] for row in transform]
            offset[left] = Fraction(allowed[0][0])
            offset[right] = Fraction(allowed[0][1])
            relation = {"kind": "forced_pair", "allowed_original_pairs": [list(allowed[0])]}
        else:
            first, second = allowed
            offset[left] = Fraction(first[0])
            offset[right] = Fraction(first[1])
            transform[left][-1] = Fraction(second[0] - first[0])
            transform[right][-1] = Fraction(second[1] - first[1])
            relation = {
                "kind": "affine_boolean_pair",
                "allowed_original_pairs": [list(first), list(second)],
            }
    new_matrix = []
    new_rhs = []
    for row, target in zip(matrix, rhs, strict=True):
        new_matrix.append(
            [
                sum(row[old] * transform[old][new] for old in range(size))
                for new in range(len(transform[0]) if transform else 0)
            ]
        )
        new_rhs.append(target - sum(row[old] * offset[old] for old in range(size)))
    relation["survivor_old_indices"] = survivors
    relation["offset"] = [str(value) for value in offset]
    relation["transform"] = [[str(value) for value in row] for row in transform]
    return new_matrix, new_rhs, relation


def project_solution(
    assignment: tuple[int, ...], left: int, right: int, relation: dict[str, Any]
) -> tuple[int, ...]:
    projected = [assignment[index] for index in relation["survivor_old_indices"]]
    if relation["kind"] == "twin_sum_canonical_lift":
        projected.append(assignment[left] + assignment[right])
    elif relation["kind"] == "affine_boolean_pair":
        allowed = [tuple(pair) for pair in relation["allowed_original_pairs"]]
        projected.append(allowed.index((assignment[left], assignment[right])))
    return tuple(projected)


def row_signature(row: Sequence[Fraction], rhs: Fraction) -> str:
    active = sorted(coefficient for coefficient in row if coefficient)
    return json.dumps({"coefficients": [str(value) for value in active], "rhs": str(rhs)}, sort_keys=True)


def terminal_details(
    matrix: list[list[Fraction]],
    rhs: list[Fraction],
    rows: Sequence[tuple[tuple[int, ...], int]],
) -> dict[str, Any]:
    return {
        "final_solution_count": len(boolean_solutions(matrix, rhs)),
        "final_width_two_basis_count": sum(width <= 2 for _, width in rows),
        "final_row_signature_histogram": dict(
            sorted(
                Counter(
                    row_signature(row, target)
                    for row, target in zip(matrix, rhs, strict=True)
                ).items()
            )
        ),
        "final_matrix": [[str(value) for value in row] for row in matrix],
        "final_rhs": [str(value) for value in rhs],
    }


def reduction_trace(
    initial_matrix: list[list[Fraction]],
    initial_rhs: list[Fraction],
) -> dict[str, Any]:
    matrix = [row[:] for row in initial_matrix]
    rhs = initial_rhs[:]
    steps = []
    for _ in range(16):
        profile = affine_profile(matrix, rhs)
        size = len(matrix[0]) if matrix else 0
        if not profile["consistent"]:
            return {"steps": steps, "terminal": "contradiction"}
        rows = basis_rows(profile["vectors"])
        if profile["nullity"] <= 2:
            return {
                "steps": steps,
                "terminal": "nullity_at_most_two",
                "final_variable_count": size,
                "final_nullity": profile["nullity"],
                **terminal_details(matrix, rhs, rows),
            }
        pairs = exclusive_pairs(rows, size)
        if not pairs:
            return {
                "steps": steps,
                "terminal": "width_two_basis_without_exclusive_pair",
                "final_variable_count": size,
                "final_nullity": profile["nullity"],
                **terminal_details(matrix, rhs, rows),
            }
        left, right = (pairs[0][0] - 1, pairs[0][1] - 1)
        column_equal = all(row[left] == row[right] for row in matrix)
        dual_parallel = production._vector_rank(
            (profile["vectors"][left], profile["vectors"][right])
        ) < 2
        if dual_parallel:
            category = "dual_parallel"
        elif column_equal:
            category = "primal_twins"
        else:
            return {
                "steps": steps,
                "terminal": "stuck_nondegenerate_exclusive_pair",
                "ports": [left + 1, right + 1],
            }
        original_solutions = boolean_solutions(matrix, rhs)
        if category == "primal_twins" and any(
            solution[left] == solution[right] == 1
            for solution in original_solutions
        ):
            return {
                "steps": steps,
                "terminal": "stuck_twin_allows_double_one",
                "ports": [left + 1, right + 1],
            }
        new_matrix, new_rhs, relation = substitute_pair(
            matrix, rhs, left, right, category, profile
        )
        quotient_solutions = boolean_solutions(new_matrix, new_rhs)
        projected = {
            project_solution(solution, left, right, relation)
            for solution in original_solutions
        }
        if projected != set(quotient_solutions):
            raise AssertionError("recursive quotient solution projection failed")
        steps.append(
            {
                "variable_count_before": size,
                "nullity_before": profile["nullity"],
                "ports": [left + 1, right + 1],
                "category": category,
                "relation_kind": relation["kind"],
                "solution_count_before": len(original_solutions),
                "solution_count_after": len(quotient_solutions),
            }
        )
        matrix, rhs = new_matrix, new_rhs
    return {"steps": steps, "terminal": "step_limit"}


def build_receipt(
    aa_path: Path = AA_PATH,
    lift_path: Path = LIFT_PATH,
) -> dict[str, Any]:
    aa = json.loads(aa_path.read_text(encoding="utf-8"))
    source = json.loads(lift_path.read_text(encoding="utf-8"))
    if digest(source) != aa["source"]["receipt_sha256"]:
        raise AssertionError("retained lift receipt does not match Result AA source digest")
    formulas = {
        target["formula_sha256"]: tuple(tuple(clause) for clause in target["formula"])
        for order in source["orders"]
        for target in order["targets"]
        if target["status"] == "analyzed"
    }
    representatives = {}
    for target in aa["targets"]:
        family = target["canonical_width_two_family_sha256"]
        representatives.setdefault(family, target)

    results = []
    for family, target in sorted(representatives.items()):
        formula = formulas[target["formula_sha256"]]
        size = len(formula)
        matrix = [
            [Fraction(int(variable + 1 in clause)) for variable in range(size)]
            for clause in formula
        ]
        rhs = [Fraction(1) for _ in formula]
        profile = affine_profile(matrix, rhs)
        original_solutions = boolean_solutions(matrix, rhs)
        for pair in target["exclusive_pairs"]:
            left, right = (pair["ports"][0] - 1, pair["ports"][1] - 1)
            new_matrix, new_rhs, relation = substitute_pair(
                matrix, rhs, left, right, pair["category"], profile
            )
            quotient_profile = affine_profile(new_matrix, new_rhs)
            quotient_rows = (
                basis_rows(quotient_profile["vectors"])
                if quotient_profile["consistent"]
                else tuple()
            )
            quotient_solutions = boolean_solutions(new_matrix, new_rhs)
            projected = {
                project_solution(solution, left, right, relation)
                for solution in original_solutions
            }
            if projected != set(quotient_solutions):
                raise AssertionError("quotient Boolean solutions disagree with projection")
            trace = reduction_trace(new_matrix, new_rhs)
            results.append(
                {
                    "canonical_family_sha256": family,
                    "formula_sha256": target["formula_sha256"],
                    "category": pair["category"],
                    "ports": pair["ports"],
                    "relation": relation,
                    "original": {
                        "variable_count": size,
                        "rank": profile["rank"],
                        "nullity": profile["nullity"],
                        "solution_count": len(original_solutions),
                    },
                    "quotient": {
                        "variable_count": len(new_matrix[0]) if new_matrix else 0,
                        "rank": quotient_profile["rank"],
                        "nullity": quotient_profile["nullity"],
                        "solution_count": len(quotient_solutions),
                        "width_two_basis_count": sum(width <= 2 for _, width in quotient_rows),
                        "exclusive_pairs": [list(pair) for pair in exclusive_pairs(quotient_rows, len(new_matrix[0]) if new_matrix else 0)],
                        "row_signature_histogram": dict(sorted(Counter(row_signature(row, target_rhs) for row, target_rhs in zip(new_matrix, new_rhs, strict=True)).items())),
                    },
                    "projected_solution_set_matches": True,
                    "recursive_reduction": trace,
                }
            )
    constructive_terminals = {
        "nullity_at_most_two",
        "width_two_basis_without_exclusive_pair",
    }
    summary = {
        "representative_family_count": len(representatives),
        "quotient_case_count": len(results),
        "category_histogram": dict(
            sorted(Counter(row["category"] for row in results).items())
        ),
        "relation_histogram": dict(
            sorted(Counter(row["relation"]["kind"] for row in results).items())
        ),
        "quotient_nullity_histogram": dict(
            sorted(
                Counter(
                    str(row["quotient"]["nullity"]) for row in results
                ).items()
            )
        ),
        "quotients_with_width_two_basis": sum(
            row["quotient"]["width_two_basis_count"] > 0 for row in results
        ),
        "quotients_with_exclusive_pair": sum(
            bool(row["quotient"]["exclusive_pairs"]) for row in results
        ),
        "projected_solution_set_mismatches": sum(
            not row["projected_solution_set_matches"] for row in results
        ),
        "recursive_terminal_histogram": dict(
            sorted(
                Counter(
                    row["recursive_reduction"]["terminal"] for row in results
                ).items()
            )
        ),
        "maximum_recursive_steps_after_first_quotient": max(
            len(row["recursive_reduction"]["steps"]) for row in results
        ),
        "constructive_recursive_terminals": sum(
            row["recursive_reduction"]["terminal"] in constructive_terminals
            and row["recursive_reduction"]["final_width_two_basis_count"] > 0
            for row in results
        ),
    }
    if len(representatives) != 4 or len(results) != 9:
        raise AssertionError("canonical representative or quotient-case count changed")
    if summary["projected_solution_set_mismatches"] != 0:
        raise AssertionError("a quotient changed the projected Boolean solution set")
    if summary["quotients_with_width_two_basis"] != len(results):
        raise AssertionError("a first quotient lost every width-two basis")
    if summary["constructive_recursive_terminals"] != len(results):
        raise AssertionError("a recursive path did not reach a constructive terminal")
    return {
        "schema": SCHEMA,
        "sources": {
            "degeneracy_structure_schema": aa["schema"],
            "degeneracy_structure_receipt_sha256": digest(aa),
            "lift_schema": source["schema"],
            "lift_receipt_sha256": digest(source),
        },
        "selection": {
            "representative_rule": (
                "lexicographically first retained target per canonical "
                "width-two family"
            ),
            "pair_rule": "every exclusive pair of each representative",
        },
        "cases": results,
        "case_stream_sha256": digest(results),
        "summary": summary,
        "assessment": {
            "bounded_result": (
                "Every quotient preserves the projected Boolean solution set "
                "and a width-two basis; every deterministic recursive path "
                "reaches a constructive terminal on the four representatives."
            ),
            "scope": (
                "Four canonical order-nine representatives and their nine "
                "exclusive pairs; not an arbitrary-order closure theorem."
            ),
        },
    }

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--structure-receipt", type=Path, default=AA_PATH)
    parser.add_argument("--lift-receipt", type=Path, default=LIFT_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    receipt = build_receipt(args.structure_receipt, args.lift_receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt["summary"], sort_keys=True))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
