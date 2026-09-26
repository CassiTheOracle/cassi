"""Independent verifier for the audited greedy width-two probe.

The verifier rebuilds the finite corpus, candidate-generation counters,
fail-closed candidate checks, and exact rational basis census without importing
the runner or the production cubic-kernel module.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
from fractions import Fraction
from pathlib import Path
from typing import Any, NoReturn, Sequence, cast

ROOT = Path(__file__).resolve().parent
DEFAULT_RECEIPT = ROOT / "_diag" / "width_two_constructor_probe.json"
SCHEMA = "cassifi.width-two-constructor-probe.v1"
BASIS_SUBSET_CAP = 100_000
RANDOM_SIZES = (8, 10, 12, 14)
RANDOM_CASES_PER_SIZE = 120
MAX_RANDOM_ATTEMPTS_PER_SIZE = 2_000
RANDOM_ATTEMPTS_PER_SAMPLE = 200


Formula = tuple[tuple[int, int, int], ...]
Vector = tuple[Fraction, ...]


class VerificationError(ValueError):
    """Raised when the constructor receipt is inconsistent."""


def fail(message: str) -> NoReturn:
    raise VerificationError(message)


def canonical_formula(formula: Sequence[Sequence[int]]) -> Formula:
    if not isinstance(formula, Sequence) or isinstance(formula, (str, bytes)):
        fail("formula is not a sequence")
    size = len(formula)
    if size < 3:
        fail("formula has fewer than three clauses")
    rows: list[tuple[int, int, int]] = []
    occurrences = [0] * (size + 1)
    for raw in formula:
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            fail("clause is not a sequence")
        if len(raw) != 3:
            fail("clause does not have arity three")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in raw):
            fail("clause contains a non-integer variable")
        if any(value < 1 or value > size for value in raw):
            fail("variable is outside 1..n")
        if len(set(raw)) != 3:
            fail("clause repeats a variable")
        ordered = sorted(raw)
        row = (ordered[0], ordered[1], ordered[2])
        rows.append(row)
        for variable in row:
            occurrences[variable] += 1
    if any(total != 3 for total in occurrences[1:]):
        fail("variable occurrence count is not three")
    result = tuple(sorted(rows))
    if len(set(result)) != len(result):
        fail("formula repeats a clause")
    return result


def digest(formula: Formula) -> str:
    return hashlib.sha256(
        json.dumps(formula, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def rref(
    matrix: Sequence[Sequence[Fraction]],
) -> tuple[list[list[Fraction]], tuple[int, ...]]:
    values = [list(row) for row in matrix]
    row_count = len(values)
    column_count = len(values[0]) if values else 0
    pivots: list[int] = []
    pivot_row = 0
    for column in range(column_count):
        selected = next(
            (row for row in range(pivot_row, row_count) if values[row][column]),
            None,
        )
        if selected is None:
            continue
        values[pivot_row], values[selected] = values[selected], values[pivot_row]
        pivot = values[pivot_row][column]
        for target in range(column, column_count):
            values[pivot_row][target] /= pivot
        for row in range(row_count):
            if row == pivot_row or not values[row][column]:
                continue
            factor = values[row][column]
            for target in range(column, column_count):
                values[row][target] -= factor * values[pivot_row][target]
        pivots.append(column)
        pivot_row += 1
        if pivot_row == row_count:
            break
    return values, tuple(pivots)


def kernel_columns(formula: Formula) -> tuple[Vector, ...]:
    size = len(formula)
    matrix = [
        [Fraction(int(variable in clause)) for variable in range(1, size + 1)]
        for clause in formula
    ]
    reduced, pivots = rref(matrix)
    free = tuple(column for column in range(size) if column not in pivots)
    columns: list[Vector] = []
    for column in range(size):
        vector = [Fraction(0)] * len(free)
        if column in free:
            vector[free.index(column)] = Fraction(1)
        else:
            row = pivots.index(column)
            for coordinate, free_column in enumerate(free):
                vector[coordinate] = -reduced[row][free_column]
        columns.append(tuple(vector))
    return tuple(columns)


def vector_rank(vectors: Sequence[Vector]) -> int:
    if not vectors:
        return 0
    _, pivots = rref(vectors)
    return len(pivots)


def covered_count(
    vectors: Sequence[Vector],
    selected: Sequence[int],
    *,
    stats: dict[str, int] | None = None,
) -> int:
    covered = 0
    for target, vector in enumerate(vectors):
        if not any(vector):
            covered += 1
            continue
        if target in selected:
            covered += 1
            continue
        for left, right in itertools.combinations(selected, 2):
            if stats is not None:
                stats["pair_span_checks"] += 1
            if vector_rank((vectors[left], vectors[right], vector)) <= 2:
                covered += 1
                break
    return covered


def support_profile(
    vectors: Sequence[Vector],
    selected: Sequence[int],
) -> tuple[int, ...]:
    profile: list[int] = []
    for target, vector in enumerate(vectors):
        if not any(vector):
            profile.append(0)
            continue
        if target in selected or any(
            vector_rank((vectors[index], vector)) <= 1 for index in selected
        ):
            profile.append(1)
            continue
        if any(
            vector_rank((vectors[left], vectors[right], vector)) <= 2
            for left, right in itertools.combinations(selected, 2)
        ):
            profile.append(2)
            continue
        profile.append(3)
    return tuple(profile)


def width_against_basis(vectors: Sequence[Vector], selected: Sequence[int]) -> int:
    return max(support_profile(vectors, selected), default=0)


def verify_candidate_basis(
    formula: Formula,
    basis: Sequence[int] | None,
) -> dict[str, Any]:
    vectors = kernel_columns(formula)
    nullity = len(vectors[0]) if vectors else 0
    if basis is None:
        return {
            "valid": False,
            "reason": "no_basis",
            "basis": None,
            "rank": 0,
            "nullity": nullity,
            "support_profile": None,
            "maximum_support": None,
        }
    if (
        isinstance(basis, (str, bytes))
        or any(isinstance(value, bool) or not isinstance(value, int) for value in basis)
        or any(value < 1 or value > len(vectors) for value in basis)
        or len(set(basis)) != len(basis)
    ):
        return {
            "valid": False,
            "reason": "malformed_basis",
            "basis": list(basis),
            "rank": None,
            "nullity": nullity,
            "support_profile": None,
            "maximum_support": None,
        }
    selected = tuple(value - 1 for value in basis)
    rank = vector_rank(tuple(vectors[index] for index in selected))
    if len(selected) != nullity or rank != nullity:
        return {
            "valid": False,
            "reason": "basis_rank_or_size",
            "basis": list(basis),
            "rank": rank,
            "nullity": nullity,
            "support_profile": None,
            "maximum_support": None,
        }
    profile = support_profile(vectors, selected)
    return {
        "valid": True,
        "reason": "verified",
        "basis": list(basis),
        "rank": rank,
        "nullity": nullity,
        "support_profile": list(profile),
        "maximum_support": max(profile, default=0),
    }


def greedy_pair_cover(formula: Formula) -> dict[str, Any]:
    vectors = kernel_columns(formula)
    nullity = len(vectors[0]) if vectors else 0
    selected: list[int] = []
    trace: list[dict[str, int]] = []
    operation_counts = {
        "candidate_columns_considered": 0,
        "rank_checks": 0,
        "pair_span_checks": 0,
        "coverage_evaluations": 0,
    }

    def checked_rank(items: Sequence[Vector]) -> int:
        operation_counts["rank_checks"] += 1
        return vector_rank(items)

    def candidate_generation() -> dict[str, Any]:
        return {
            **operation_counts,
            "steps": trace,
        }

    while len(selected) < nullity:
        current_rank = checked_rank(
            tuple(vectors[index] for index in selected)
        )
        candidates: list[int] = []
        for index in range(len(vectors)):
            if index in selected:
                continue
            operation_counts["candidate_columns_considered"] += 1
            if checked_rank(
                tuple(vectors[item] for item in (*selected, index))
            ) > current_rank:
                candidates.append(index)
        if not candidates:
            return {
                "status": "no_basis",
                "basis": None,
                "width": None,
                "coverage_trace": trace,
                "candidate_generation": candidate_generation(),
                "fail_closed": True,
                "fail_closed_reason": "no_independent_extension",
            }
        scored: list[tuple[int, int]] = []
        for candidate in candidates:
            operation_counts["coverage_evaluations"] += 1
            scored.append(
                (
                    -covered_count(
                        vectors,
                        (*selected, candidate),
                        stats=operation_counts,
                    ),
                    candidate,
                )
            )
        _, chosen = min(scored)
        selected.append(chosen)
        operation_counts["coverage_evaluations"] += 1
        trace.append(
            {
                "chosen_column": chosen + 1,
                "covered_columns": covered_count(
                    vectors,
                    selected,
                    stats=operation_counts,
                ),
                "rank": len(selected),
                "independent_candidates": len(candidates),
                "score_evaluations": len(scored),
            }
        )
    width = width_against_basis(vectors, selected)
    return {
        "status": "width_two" if width <= 2 else "width_gt_two",
        "basis": [index + 1 for index in selected],
        "width": width,
        "coverage_trace": trace,
        "candidate_generation": candidate_generation(),
        "fail_closed": False,
        "fail_closed_reason": None,
    }


def all_small_cubic_formulas(size: int) -> tuple[Formula, ...]:
    triples = tuple(itertools.combinations(range(1, size + 1), 3))
    found: list[Formula] = []
    degrees = [0] * (size + 1)
    chosen: list[tuple[int, int, int]] = []

    def visit(start: int) -> None:
        remaining = size - len(chosen)
        if remaining == 0:
            if all(degrees[variable] == 3 for variable in range(1, size + 1)):
                found.append(tuple(chosen))
            return
        if len(triples) - start < remaining:
            return
        for index in range(start, len(triples)):
            if len(triples) - index < remaining:
                break
            clause = triples[index]
            if any(degrees[variable] >= 3 for variable in clause):
                continue
            for variable in clause:
                degrees[variable] += 1
            chosen.append(clause)
            possible = all(
                degrees[variable] <= 3
                and degrees[variable] + (remaining - 1) * 3 >= 3
                for variable in range(1, size + 1)
            )
            if possible:
                visit(index + 1)
            chosen.pop()
            for variable in clause:
                degrees[variable] -= 1

    visit(0)
    return tuple(found)


def random_cubic_formula(size: int, rng: random.Random) -> Formula | None:
    labels = list(range(1, size + 1))
    for _ in range(RANDOM_ATTEMPTS_PER_SAMPLE):
        permutations: list[list[int]] = []
        for _ in range(3):
            candidate = labels.copy()
            rng.shuffle(candidate)
            permutations.append(candidate)
        rows = tuple(
            sorted(
                tuple(sorted(permutations[offset][row] for offset in range(3)))
                for row in range(size)
            )
        )
        if len(set(rows)) != size:
            continue
        try:
            return canonical_formula(rows)
        except VerificationError:
            continue
    return None


def _build_corpus() -> tuple[tuple[Formula, ...], list[dict[str, Any]]]:
    formulas: dict[str, Formula] = {}
    generation: list[dict[str, Any]] = []
    for size in (4, 6):
        for formula in all_small_cubic_formulas(size):
            formulas[digest(formula)] = formula
    rng = random.Random(0xCA551)
    for size in RANDOM_SIZES:
        accepted = 0
        attempts = 0
        while (
            accepted < RANDOM_CASES_PER_SIZE
            and attempts < MAX_RANDOM_ATTEMPTS_PER_SIZE
        ):
            attempts += 1
            formula = random_cubic_formula(size, rng)
            if formula is not None:
                formulas[digest(formula)] = formula
                accepted += 1
        generation.append(
            {
                "variables": size,
                "requested": RANDOM_CASES_PER_SIZE,
                "accepted": accepted,
                "attempts": attempts,
                "complete": accepted == RANDOM_CASES_PER_SIZE,
            }
        )
    return tuple(formulas[key] for key in sorted(formulas)), generation


def corpus() -> tuple[Formula, ...]:
    return _build_corpus()[0]


def basis_census(formula: Formula) -> dict[str, Any]:
    size = len(formula)
    matrix = [
        [Fraction(int(variable in clause)) for variable in range(1, size + 1)]
        for clause in formula
    ]
    _, canonical_pivots = rref(matrix)
    rank = len(canonical_pivots)
    histogram: dict[int, int] = {}
    best_key: tuple[int, int, tuple[int, ...], tuple[int, ...]] | None = None
    best_supports: tuple[int, ...] = ()
    bases_found = 0
    for pivots in itertools.combinations(range(size), rank):
        free = tuple(column for column in range(size) if column not in pivots)
        order = pivots + free
        permuted = [[row[column] for column in order] for row in matrix]
        reduced, local_pivots = rref(permuted)
        if local_pivots != tuple(range(rank)):
            continue
        supports = tuple(
            sum(value != 0 for value in reduced[row][rank:])
            for row in range(rank)
        )
        bases_found += 1
        width = max(supports, default=0)
        histogram[width] = histogram.get(width, 0) + 1
        key = (width, sum(supports), pivots, free)
        if best_key is None or key < best_key:
            best_key = key
            best_supports = supports
    if best_key is None:
        fail("no exact column basis found")
    return {
        "rank": rank,
        "nullity": size - rank,
        "column_subsets_checked": math.comb(size, rank),
        "column_bases_found": bases_found,
        "minimum_maximum_pivot_free_support": best_key[0],
        "free_basis": [column + 1 for column in best_key[3]],
        "free_supports": list(best_supports),
        "histogram": {str(width): histogram[width] for width in sorted(histogram)},
    }


def verify_case(case: dict[str, Any]) -> None:
    if not isinstance(case, dict):
        fail("case is not an object")
    raw_formula = case.get("formula")
    if not isinstance(raw_formula, Sequence):
        fail("case formula is missing")
    formula = canonical_formula(
        cast(Sequence[Sequence[int]], raw_formula)
    )
    if case.get("formula_sha256") != digest(formula):
        fail("formula digest mismatch")
    if case.get("variables") != len(formula):
        fail("variable count mismatch")
    columns = kernel_columns(formula)
    nullity = len(columns[0]) if columns else 0
    rank = len(formula) - nullity
    expected_census = basis_census(formula)
    if case.get("rank") != rank or case.get("nullity") != nullity:
        fail("rank or nullity mismatch")
    if case.get("column_subsets_checked") != expected_census[
        "column_subsets_checked"
    ]:
        fail("basis subset count mismatch")
    if case.get("exact_width") != expected_census[
        "minimum_maximum_pivot_free_support"
    ]:
        fail("exact width mismatch")
    if case.get("exact_free_basis") != expected_census["free_basis"]:
        fail("exact free basis witness mismatch")
    if case.get("exact_free_supports") != expected_census["free_supports"]:
        fail("exact free support witness mismatch")
    if case.get("exact_width_two_exists") is not (
        expected_census["minimum_maximum_pivot_free_support"] <= 2
    ):
        fail("exact width-two flag mismatch")
    expected_candidate = greedy_pair_cover(formula)
    expected_greedy = {
        **expected_candidate,
        "verification": verify_candidate_basis(
            formula,
            expected_candidate["basis"],
        ),
    }
    if case.get("greedy") != expected_greedy:
        fail("greedy constructor result mismatch")
    expected_counterexample = (
        expected_census["minimum_maximum_pivot_free_support"] <= 2
        and expected_greedy["width"]
        != expected_census["minimum_maximum_pivot_free_support"]
    )
    if case.get("counterexample") is not expected_counterexample:
        fail("counterexample flag mismatch")


def verify(path: str | Path = DEFAULT_RECEIPT) -> dict[str, Any]:
    receipt = json.loads(Path(path).read_text(encoding="utf-8"))
    if receipt.get("schema") != SCHEMA:
        fail("schema mismatch")
    cases = receipt.get("cases")
    if not isinstance(cases, list):
        fail("cases are missing")
    expected_formulas, expected_generation = _build_corpus()
    expected_cases: list[Formula] = []
    for formula in expected_formulas:
        columns = kernel_columns(formula)
        nullity = len(columns[0]) if columns else 0
        rank = len(formula) - nullity
        if math.comb(len(formula), rank) <= BASIS_SUBSET_CAP:
            expected_cases.append(formula)
    expected_digests = {digest(formula) for formula in expected_cases}
    actual_digests = {case.get("formula_sha256") for case in cases}
    if actual_digests != expected_digests:
        fail("corpus formula set mismatch")
    if receipt.get("corpus_generation") != expected_generation:
        fail("corpus generation metadata mismatch")
    for case in cases:
        verify_case(case)
    counterexamples = [case for case in cases if case["counterexample"]]
    generation_complete = all(row["complete"] for row in expected_generation)
    summary = receipt.get("summary")
    expected_summary = {
        "corpus_cases": len(expected_formulas),
        "exact_cases": len(cases),
        "skipped_over_subset_cap": len(expected_formulas) - len(cases),
        "generation_complete": generation_complete,
        "generation_report": expected_generation,
        "basis_censuses_complete": all(
            case["column_subsets_checked"] <= BASIS_SUBSET_CAP for case in cases
        ),
        "basis_subsets_checked": sum(
            case["column_subsets_checked"] for case in cases
        ),
        "exact_width_two_cases": sum(
            case["exact_width_two_exists"] for case in cases
        ),
        "greedy_width_two_cases": sum(
            case["greedy"]["status"] == "width_two" for case in cases
        ),
        "counterexamples": len(counterexamples),
        "nullity_zero_cases": sum(case["nullity"] == 0 for case in cases),
        "nonzero_nullity_cases": sum(case["nullity"] > 0 for case in cases),
        "verified_candidate_bases": sum(
            case["greedy"]["verification"]["valid"] for case in cases
        ),
        "fail_closed_no_basis": sum(
            case["greedy"]["fail_closed"] for case in cases
        ),
        "candidate_columns_considered": sum(
            case["greedy"]["candidate_generation"][
                "candidate_columns_considered"
            ]
            for case in cases
        ),
        "candidate_rank_checks": sum(
            case["greedy"]["candidate_generation"]["rank_checks"]
            for case in cases
        ),
        "candidate_pair_span_checks": sum(
            case["greedy"]["candidate_generation"]["pair_span_checks"]
            for case in cases
        ),
        "candidate_coverage_evaluations": sum(
            case["greedy"]["candidate_generation"]["coverage_evaluations"]
            for case in cases
        ),
        "maximum_variables": max((case["variables"] for case in cases), default=0),
    }
    if summary != expected_summary:
        fail("summary mismatch")
    if receipt.get("counterexamples") != counterexamples[:10]:
        fail("counterexample listing mismatch")
    hypothesis = receipt.get("hypothesis", {})
    if hypothesis.get("name") != "greedy-pair-cover":
        fail("hypothesis name mismatch")
    expected_status = (
        "falsified"
        if counterexamples and generation_complete
        else "incomplete"
        if not generation_complete
        else "not_falsified"
    )
    if hypothesis.get("status") != expected_status:
        fail("hypothesis status mismatch")
    return {
        "schema": SCHEMA,
        "result": "PASS",
        "verified_cases": len(cases),
        "counterexamples": len(counterexamples),
        "generation_complete": generation_complete,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
