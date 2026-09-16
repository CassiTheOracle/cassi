"""Falsify a concrete width-two basis-construction heuristic.

The theorem-level branch tested here is deliberately explicit:

    greedy-pair-cover
        Build a kernel-coordinate basis one element at a time. At each step,
        choose the independent column that maximizes the number of coordinate
        columns covered by the selected set and its pairwise spans; break ties
        by the original column index.

The probe measures candidate-generation work and independently verifies every
returned candidate. It does not claim a polynomial bit-complexity bound for
the exact rational arithmetic, and the exhaustive basis census is an oracle,
not a polynomial constructor. A single formula with an exact width-two basis
but a greedy width greater than two is a finite, reproducible falsification.
It is not a hardness result.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cubic_kernel_decision import (  # noqa: E402
    canonical_cubic_formula,
    cubic_kernel_basis_width,
)

OUTPUT = Path("_diag/width_two_constructor_probe.json")
SCHEMA = "cassifi.width-two-constructor-probe.v1"
BASIS_SUBSET_CAP = 100_000
RANDOM_SIZES = (8, 10, 12, 14)
RANDOM_CASES_PER_SIZE = 120
MAX_RANDOM_ATTEMPTS_PER_SIZE = 2_000

RANDOM_ATTEMPTS_PER_SAMPLE = 200

Formula = tuple[tuple[int, int, int], ...]
Vector = tuple[Fraction, ...]


def digest(formula: Formula) -> str:
    return hashlib.sha256(
        json.dumps(formula, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def _rref(
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


def _kernel_coordinate_columns(formula: Formula) -> tuple[Vector, ...]:
    size = len(formula)
    matrix = [
        [Fraction(int(variable in clause)) for variable in range(1, size + 1)]
        for clause in formula
    ]
    reduced, pivots = _rref(matrix)
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


def _rank(vectors: Sequence[Vector]) -> int:
    if not vectors:
        return 0
    _, pivots = _rref(vectors)
    return len(pivots)


def _covered_count(
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
            if _rank((vectors[left], vectors[right], vector)) <= 2:
                covered += 1
                break
    return covered


def _support_profile(
    vectors: Sequence[Vector],
    selected: Sequence[int],
) -> tuple[int, ...]:
    profile: list[int] = []
    for target, vector in enumerate(vectors):
        if not any(vector):
            profile.append(0)
            continue
        if target in selected or any(
            _rank((vectors[index], vector)) <= 1 for index in selected
        ):
            profile.append(1)
            continue
        if any(
            _rank((vectors[left], vectors[right], vector)) <= 2
            for left, right in itertools.combinations(selected, 2)
        ):
            profile.append(2)
            continue
        profile.append(3)
    return tuple(profile)


def _width_against_basis(vectors: Sequence[Vector], selected: Sequence[int]) -> int:
    return max(_support_profile(vectors, selected), default=0)


def verify_candidate_basis(
    formula: Formula,
    basis: Sequence[int] | None,
) -> dict[str, Any]:
    vectors = _kernel_coordinate_columns(formula)
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
    rank = _rank(tuple(vectors[index] for index in selected))
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
    support_profile = _support_profile(vectors, selected)
    return {
        "valid": True,
        "reason": "verified",
        "basis": list(basis),
        "rank": rank,
        "nullity": nullity,
        "support_profile": list(support_profile),
        "maximum_support": max(support_profile, default=0),
    }


def greedy_pair_cover(formula: Formula) -> dict[str, Any]:
    """Return a deterministic heuristic candidate and operation counters."""

    vectors = _kernel_coordinate_columns(formula)
    nullity = len(vectors[0]) if vectors else 0
    selected: list[int] = []
    coverage_trace: list[dict[str, int]] = []
    operation_counts = {
        "candidate_columns_considered": 0,
        "rank_checks": 0,
        "pair_span_checks": 0,
        "coverage_evaluations": 0,
    }

    def checked_rank(items: Sequence[Vector]) -> int:
        operation_counts["rank_checks"] += 1
        return _rank(items)

    def candidate_generation() -> dict[str, Any]:
        return {
            **operation_counts,
            "steps": coverage_trace,
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
                "coverage_trace": coverage_trace,
                "candidate_generation": candidate_generation(),
                "fail_closed": True,
                "fail_closed_reason": "no_independent_extension",
            }
        scored: list[tuple[int, int]] = []
        for candidate in candidates:
            operation_counts["coverage_evaluations"] += 1
            scored.append(
                (
                    -_covered_count(
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
        coverage_trace.append(
            {
                "chosen_column": chosen + 1,
                "covered_columns": _covered_count(
                    vectors,
                    selected,
                    stats=operation_counts,
                ),
                "rank": len(selected),
                "independent_candidates": len(candidates),
                "score_evaluations": len(scored),
            }
        )
    width = _width_against_basis(vectors, selected)
    return {
        "status": "width_two" if width <= 2 else "width_gt_two",
        "basis": [index + 1 for index in selected],
        "width": width,
        "coverage_trace": coverage_trace,
        "candidate_generation": candidate_generation(),
        "fail_closed": False,
        "fail_closed_reason": None,
    }


def _all_small_cubic_formulas(size: int) -> tuple[Formula, ...]:
    triples = tuple(itertools.combinations(range(1, size + 1), 3))
    found: list[Formula] = []
    degrees = [0] * (size + 1)
    chosen: list[tuple[int, int, int]] = []

    def visit(start: int) -> None:
        remaining_clauses = size - len(chosen)
        if remaining_clauses == 0:
            if all(degrees[variable] == 3 for variable in range(1, size + 1)):
                found.append(tuple(chosen))
            return
        if len(triples) - start < remaining_clauses:
            return
        for index in range(start, len(triples)):
            if len(triples) - index < remaining_clauses:
                break
            clause = triples[index]
            if any(degrees[variable] >= 3 for variable in clause):
                continue
            for variable in clause:
                degrees[variable] += 1
            chosen.append(clause)
            possible = all(
                degrees[variable] <= 3
                and degrees[variable] + (remaining_clauses - 1) * 3 >= 3
                for variable in range(1, size + 1)
            )
            if possible:
                visit(index + 1)
            chosen.pop()
            for variable in clause:
                degrees[variable] -= 1

    visit(0)
    return tuple(found)


def _random_cubic_formula(size: int, rng: random.Random) -> Formula | None:
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
            return canonical_cubic_formula(rows)
        except ValueError:
            continue
    return None


def _build_corpus() -> tuple[tuple[Formula, ...], list[dict[str, Any]]]:
    formulas: dict[str, Formula] = {}
    generation: list[dict[str, Any]] = []
    for size in (4, 6):
        for formula in _all_small_cubic_formulas(size):
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
            formula = _random_cubic_formula(size, rng)
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


def _corpus() -> tuple[Formula, ...]:
    return _build_corpus()[0]


def analyze_formula(formula: Formula) -> dict[str, Any] | None:
    vectors = _kernel_coordinate_columns(formula)
    nullity = len(vectors[0]) if vectors else 0
    rank = len(formula) - nullity
    subset_total = math.comb(len(formula), rank)
    if subset_total > BASIS_SUBSET_CAP:
        return None
    exact = cubic_kernel_basis_width(
        formula,
        maximum_column_subsets=BASIS_SUBSET_CAP,
    )
    candidate = greedy_pair_cover(formula)
    candidate_verification = verify_candidate_basis(formula, candidate["basis"])
    greedy = {**candidate, "verification": candidate_verification}
    if candidate["basis"] is not None:
        if not candidate_verification["valid"]:
            raise AssertionError("greedy candidate failed independent verification")
        if candidate["width"] != candidate_verification["maximum_support"]:
            raise AssertionError("greedy width disagrees with verification")
    exact_width = exact["minimum_maximum_pivot_free_support"]
    exact_pivot_basis = exact["witness"]["pivot_columns"]
    exact_free_basis = [
        column
        for column in range(1, len(formula) + 1)
        if column not in exact_pivot_basis
    ]
    counterexample = exact_width <= 2 and greedy["width"] != exact_width
    return {
        "formula": [list(row) for row in formula],
        "formula_sha256": digest(formula),
        "variables": len(formula),
        "rank": rank,
        "nullity": nullity,
        "column_subsets_checked": exact["column_subsets_checked"],
        "exact_width": exact_width,
        "exact_width_two_exists": exact_width <= 2,
        "exact_free_basis": exact_free_basis,
        "exact_free_supports": exact["witness"]["pivot_free_supports"],
        "greedy": greedy,
        "counterexample": counterexample,
    }


def build_receipt() -> dict[str, Any]:
    formulas, generation = _build_corpus()
    cases: list[dict[str, Any]] = []
    skipped = 0
    for formula in formulas:
        result = analyze_formula(formula)
        if result is None:
            skipped += 1
            continue
        cases.append(result)
    counterexamples = [case for case in cases if case["counterexample"]]
    generation_complete = all(row["complete"] for row in generation)
    if not any(case["nullity"] == 0 for case in cases):
        raise AssertionError("corpus lost the nullity-zero edge case")
    if not any(case["nullity"] > 0 for case in cases):
        raise AssertionError("corpus lost every nonzero-nullity case")
    return {
        "schema": SCHEMA,
        "hypothesis": {
            "name": "greedy-pair-cover",
            "claim_tested": (
                "the deterministic coverage-greedy basis constructor finds a "
                "width-two basis whenever one exists"
            ),
            "status": (
                "falsified"
                if counterexamples and generation_complete
                else "incomplete"
                if not generation_complete
                else "not_falsified"
            ),
            "scope": (
                "the registered finite cubic corpus only; this is not a "
                "complexity classification"
            ),
            "exact_oracle": (
                "complete rank-sized column-subset census within the recorded cap"
            ),
            "candidate_complexity": (
                "operation counters are recorded; no polynomial bit-complexity "
                "claim is made"
            ),
        },
        "corpus_generation": generation,
        "cases": cases,
        "counterexamples": counterexamples[:10],
        "summary": {
            "corpus_cases": len(cases) + skipped,
            "exact_cases": len(cases),
            "skipped_over_subset_cap": skipped,
            "generation_complete": generation_complete,
            "generation_report": generation,
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
        },
    }


def run(output: Path = OUTPUT) -> dict[str, Any]:
    receipt = build_receipt()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt["summary"], sort_keys=True))
    if receipt["counterexamples"]:
        print(
            json.dumps(
                {
                    "first_counterexample": receipt["counterexamples"][0][
                        "formula_sha256"
                    ],
                    "exact_width": receipt["counterexamples"][0]["exact_width"],
                    "greedy_width": receipt["counterexamples"][0]["greedy"][
                        "width"
                    ],
                },
                sort_keys=True,
            )
        )
    return receipt


if __name__ == "__main__":
    run()
