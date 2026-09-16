from __future__ import annotations

import itertools
import json

import pytest

import cassi_cubic_reduction as reduction

from cubic_kernel_decision import (
    CubicKernelDecisionError,
    canonical_cubic_formula,
    canonical_cubic_matrix,
    cubic_kernel_basis_width,
    cubic_kernel_dual_triangle_profile,
    cubic_kernel_short_line_basis,
    cubic_kernel_width_two_basis,
    cubic_kernel_width_two_line_profile,
    cubic_kernel_zero_valid_basis,
    decide_cubic_kernel,
    incidence_connected,
    incidence_matrix,
    verify_cubic_width_two_basis,
)
CROWN_FOUR = (
    (1, 2, 3),
    (1, 2, 4),
    (1, 3, 4),
    (2, 3, 4),
)
CIRCULANT_SIX = tuple(
    (index + 1, (index + 1) % 6 + 1, (index + 2) % 6 + 1)
    for index in range(6)
)
SINGULAR_ALPHABET_UNSAT = (
    (1, 7, 9),
    (2, 5, 3),
    (3, 1, 7),
    (4, 8, 2),
    (5, 4, 8),
    (6, 9, 5),
    (7, 6, 1),
    (8, 2, 6),
    (9, 3, 4),
)
FULL_SUPPORT_ALPHABET_UNSAT = (
    (1, 5, 9),
    (2, 4, 5),
    (3, 2, 1),
    (4, 9, 3),
    (5, 3, 8),
    (6, 8, 2),
    (7, 1, 4),
    (8, 7, 6),
    (9, 6, 7),
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
ALL_TERNARY_BASES_SAT = (
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


def matrix_for(formula: tuple[tuple[int, int, int], ...]) -> tuple[tuple[int, ...], ...]:
    size = len(formula)
    return tuple(
        tuple(int(variable in clause) for variable in range(1, size + 1))
        for clause in formula
    )


def direct_sum(
    left: tuple[tuple[int, int, int], ...],
    right: tuple[tuple[int, int, int], ...],
) -> tuple[tuple[int, int, int], ...]:
    offset = len(left)
    return left + tuple(
        (clause[0] + offset, clause[1] + offset, clause[2] + offset)
        for clause in right
    )





def satisfies(formula: tuple[tuple[int, ...], ...], assignment: list[int]) -> bool:
    return all(
        sum(assignment[variable - 1] for variable in clause) == 1
        for clause in formula
    )


def brute_status(formula: tuple[tuple[int, int, int], ...]) -> str:
    for assignment in itertools.product((0, 1), repeat=len(formula)):
        if all(
            sum(assignment[variable - 1] for variable in clause) == 1
            for clause in formula
        ):
            return "sat"
    return "unsat"


def fixed_gauge_formulas(size: int) -> set[tuple[tuple[int, int, int], ...]]:
    permutations = tuple(itertools.permutations(range(size)))
    formulas: set[tuple[tuple[int, int, int], ...]] = set()
    for second in permutations:
        if any(second[row] == row for row in range(size)):
            continue
        for third in permutations:
            if any(third[row] in (row, second[row]) for row in range(size)):
                continue
            raw = [
                sorted((row + 1, second[row] + 1, third[row] + 1))
                for row in range(size)
            ]
            formulas.add(
                tuple((clause[0], clause[1], clause[2]) for clause in sorted(raw))
            )
    return formulas


@pytest.mark.parametrize(
    "formula",
    [
        (),
        ((1, 2, 3),),
        ((1, 1, 2), (1, 2, 3), (1, 2, 3)),
        ((1, 2, 4), (1, 2, 3), (1, 2, 3)),
        ((1, 2, True), (1, 2, 3), (1, 2, 3)),
        ((1, 2, 3), (1, 2, 3), (1, 2, 4), (1, 2, 4)),
    ],
)
def test_rejects_inputs_outside_the_cubic_theorem_domain(formula: object) -> None:
    with pytest.raises(CubicKernelDecisionError):
        decide_cubic_kernel(formula)  # type: ignore[arg-type]



def test_matrix_certificate_uses_kernel_basis_complement_and_bit_bounds() -> None:
    full_rank = verify_cubic_width_two_basis(matrix_for(CROWN_FOUR), [])
    assert full_rank["rank"] == 4
    assert full_rank["nullity"] == 0
    assert full_rank["pivot_columns"] == [1, 2, 3, 4]
    assert full_rank["accepted"]
    assert full_rank["maximum_basis_coordinate_support"] == 0
    assert full_rank["zero_kernel_columns"] == [1, 2, 3, 4]
    assert full_rank["parallel_kernel_classes"] == []
    assert (
        full_rank["bit_bounds"]["observed_kernel_entry_bits"]
        <= full_rank["bit_bounds"]["kernel_entry_bit_bound"]
    )

    sat_width = cubic_kernel_basis_width(SUPPORT_THREE_SAT)
    witness = sat_width["witness"]["free_columns"]
    certificate = verify_cubic_width_two_basis(
        matrix_for(SUPPORT_THREE_SAT), witness
    )
    assert certificate["rank"] == 6
    assert certificate["nullity"] == 3
    assert certificate["basis_invertible"]
    assert certificate["accepted"]
    assert certificate["maximum_basis_coordinate_support"] == 2
    assert certificate["parallel_kernel_classes"] == [[1, 4], [2, 5, 6], [3, 8]]
    assert (
        certificate["bit_bounds"]["observed_basis_coordinate_bits"]
        <= certificate["bit_bounds"]["basis_coordinate_bit_bound"]
    )

    unsat_width = cubic_kernel_basis_width(SUPPORT_THREE_UNSAT)
    unsat_certificate = verify_cubic_width_two_basis(
        matrix_for(SUPPORT_THREE_UNSAT),
        unsat_width["witness"]["free_columns"],
    )
    assert unsat_certificate["accepted"]
    assert unsat_certificate["maximum_basis_coordinate_support"] == 2


def test_matrix_certificate_rejects_malformed_inputs_and_bad_witnesses() -> None:
    with pytest.raises(CubicKernelDecisionError, match="matrix entries"):
        canonical_cubic_matrix(((1, 1, 1), (1, 1, 2), (0, 0, 0)))
    with pytest.raises(CubicKernelDecisionError, match="column"):
        canonical_cubic_matrix(
            (
                (0, 1, 1, 1),
                (0, 1, 1, 1),
                (1, 0, 1, 1),
                (1, 0, 1, 1),
            )
        )
    with pytest.raises(CubicKernelDecisionError, match="sorted"):
        verify_cubic_width_two_basis(matrix_for(SUPPORT_THREE_SAT), [7, 2, 1])
    with pytest.raises(CubicKernelDecisionError, match="exactly 3"):
        verify_cubic_width_two_basis(matrix_for(SUPPORT_THREE_SAT), [1, 2])

    width_three = cubic_kernel_basis_width(ALL_TERNARY_BASES_SAT)
    rejected = verify_cubic_width_two_basis(
        matrix_for(ALL_TERNARY_BASES_SAT),
        width_three["witness"]["free_columns"],
    )
    assert not rejected["accepted"]
    assert rejected["maximum_basis_coordinate_support"] == 3


def test_line_profile_is_exact_at_nullity_three_and_conservative_beyond() -> None:
    for formula in (
        CROWN_FOUR,
        CIRCULANT_SIX,
        SINGULAR_ALPHABET_UNSAT,
        FULL_SUPPORT_ALPHABET_UNSAT,
    ):
        profile = cubic_kernel_width_two_line_profile(formula)
        assert profile["status"] == "width_two"
        assert profile["certificate"]["accepted"]

    satisfiable = cubic_kernel_width_two_line_profile(SUPPORT_THREE_SAT)
    unsatisfiable = cubic_kernel_width_two_line_profile(SUPPORT_THREE_UNSAT)
    assert satisfiable["status"] == unsatisfiable["status"] == "width_two"
    assert satisfiable["reason"] == "nullity_three_class_coverage"
    assert unsatisfiable["reason"] == "nullity_three_class_coverage"
    assert len(unsatisfiable["long_lines"]) == 1
    assert len(unsatisfiable["long_lines"][0]["classes"]) == 5
    assert unsatisfiable["eligible_class_triples"] == 20
    assert unsatisfiable["pair_span_pairs_checked"] == 20

    obstruction = cubic_kernel_width_two_line_profile(ALL_TERNARY_BASES_SAT)
    assert obstruction["status"] == "no_width_two_basis"
    assert obstruction["reason"] == "nullity_three_class_coverage_exhausted"
    assert obstruction["class_triples_checked"] == 35
    assert obstruction["eligible_class_triples"] == 35
    assert obstruction["pair_span_pairs_checked"] == 21

    growing = cubic_kernel_width_two_line_profile(
        direct_sum(SUPPORT_THREE_SAT, SUPPORT_THREE_SAT)
    )
    assert growing["nullity"] == 6
    assert growing["status"] == "unresolved"
    assert growing["reason"] == "residual_basis_search"
    assert growing["certificate"] is None



def test_short_line_class_bound_is_exact_and_long_lines_stay_unresolved() -> None:
    satisfiable = cubic_kernel_short_line_basis(SUPPORT_THREE_SAT)
    assert satisfiable["short_line_hypothesis"]
    assert satisfiable["status"] == "width_two"
    assert satisfiable["reason"] == "short_line_class_coverage"
    assert satisfiable["class_count"] <= satisfiable["class_bound"]
    assert satisfiable["certificate"]["accepted"]

    bounded_no = cubic_kernel_short_line_basis(ALL_TERNARY_BASES_SAT)
    assert bounded_no["short_line_hypothesis"]
    assert bounded_no["status"] == "no_width_two_basis"
    assert bounded_no["reason"] == "short_line_class_bound"
    assert bounded_no["class_count"] == 7
    assert bounded_no["class_bound"] == 6
    assert bounded_no["class_subsets_checked"] == 0

    growing = cubic_kernel_short_line_basis(
        direct_sum(SUPPORT_THREE_SAT, SUPPORT_THREE_SAT)
    )
    assert growing["nullity"] == 6
    assert growing["short_line_hypothesis"]
    assert growing["status"] == "width_two"
    assert growing["reason"] == "short_line_class_coverage"
    assert growing["certificate"]["accepted"]
    assert growing["class_count"] == 10
    assert growing["class_bound"] == 21

    long_line = cubic_kernel_short_line_basis(SUPPORT_THREE_UNSAT)
    assert not long_line["short_line_hypothesis"]
    assert long_line["status"] == "unresolved"
    assert long_line["reason"] == "long_line_outside_short_line_method"
    assert long_line["certificate"] is None


def test_complete_width_two_recognizer_handles_long_lines_and_decision_seam() -> None:
    for formula in (
        CROWN_FOUR,
        SINGULAR_ALPHABET_UNSAT,
        CIRCULANT_SIX,
    ):
        edge = cubic_kernel_width_two_basis(formula)
        assert edge["status"] == "width_two"
        assert edge["reason"] == "nullity_at_most_two"
        assert edge["certificate"]["accepted"]

    for formula, expected_status in (
        (SUPPORT_THREE_SAT, "sat"),
        (SUPPORT_THREE_UNSAT, "unsat"),
    ):
        result = cubic_kernel_width_two_basis(formula)
        assert result["status"] == "width_two"
        assert result["certificate"]["accepted"]
        assert result["search_complete"]
        pivot_columns = tuple(
            column
            for column in range(1, len(formula) + 1)
            if column not in result["candidate_free_columns"]
        )
        decision = decide_cubic_kernel(
            formula,
            pivot_columns=pivot_columns,
        )
        assert decision["status"] == expected_status

    long_line = cubic_kernel_width_two_basis(SUPPORT_THREE_UNSAT)
    assert long_line["method"] == "long_line_endpoint_search"
    assert long_line["long_line_count"] == 1
    assert long_line["endpoint_subsets_checked"] > 0
    assert long_line["residual_subsets_checked"] > 0

    no_basis = cubic_kernel_width_two_basis(ALL_TERNARY_BASES_SAT)
    assert no_basis["status"] == "no_width_two_basis"
    assert no_basis["reason"] == "short_line_class_bound"
    assert no_basis["certificate"] is None
    assert decide_cubic_kernel(ALL_TERNARY_BASES_SAT)["status"] == "sat"


def test_rank_alphabet_and_witness_outcomes_are_distinct() -> None:
    full_rank = decide_cubic_kernel(CROWN_FOUR)
    assert full_rank["status"] == "unsat"
    assert full_rank["reason"] == "full_rank"
    assert full_rank["nullity"] == 0

    satisfiable = decide_cubic_kernel(CIRCULANT_SIX)
    assert satisfiable["status"] == "sat"
    assert satisfiable["reason"] == "bounded_support_2sat_sat"
    assert satisfies(CIRCULANT_SIX, satisfiable["assignment"])
    kernel_vector = satisfiable["kernel_vector"]
    assert kernel_vector == [3 * value - 1 for value in satisfiable["assignment"]]
    assert all(
        sum(row[index] * kernel_vector[index] for index in range(6)) == 0
        for row in incidence_matrix(canonical_cubic_formula(CIRCULANT_SIX))
    )

    singular_unsat = decide_cubic_kernel(SINGULAR_ALPHABET_UNSAT)
    assert singular_unsat["status"] == "unsat"
    assert singular_unsat["reason"] == "forced_zero_pivot"
    assert singular_unsat["rank"] == 8
    assert singular_unsat["nullity"] == 1
    assert singular_unsat["candidates_checked"] == 0

    full_support_unsat = decide_cubic_kernel(FULL_SUPPORT_ALPHABET_UNSAT)
    assert full_support_unsat["status"] == "unsat"
    assert full_support_unsat["reason"] == "bounded_support_2sat_unsat"
    assert full_support_unsat["maximum_pivot_free_support"] == 1
    assert full_support_unsat["two_sat_certificate"]["conflict_free_column"] == 9


def test_support_three_boundary_uses_exact_fallback_for_sat_and_unsat() -> None:
    satisfiable = decide_cubic_kernel(SUPPORT_THREE_SAT)
    unsatisfiable = decide_cubic_kernel(SUPPORT_THREE_UNSAT)
    assert satisfiable["maximum_pivot_free_support"] == 3
    assert satisfiable["reason"] == "alphabet_kernel_vector"
    assert satisfies(SUPPORT_THREE_SAT, satisfiable["assignment"])
    assert unsatisfiable["maximum_pivot_free_support"] == 3
    assert unsatisfiable["reason"] == "alphabet_exhausted"
    assert unsatisfiable["candidates_checked"] == 8


def test_basis_optimization_expands_binary_support_decisions() -> None:
    for formula, expected_status in (
        (SUPPORT_THREE_SAT, "sat"),
        (SUPPORT_THREE_UNSAT, "unsat"),
    ):
        width = cubic_kernel_basis_width(formula)
        assert width["canonical_maximum_pivot_free_support"] == 3
        assert width["minimum_maximum_pivot_free_support"] == 2
        assert width["improves_canonical_basis"]
        optimized = decide_cubic_kernel(
            formula, pivot_columns=width["witness"]["pivot_columns"]
        )
        assert optimized["status"] == expected_status
        assert optimized["reason"] == f"bounded_support_2sat_{expected_status}"
        assert optimized["candidates_checked"] == 0

def test_basis_exchange_profile_exposes_strict_descent_traps() -> None:
    width = cubic_kernel_basis_width(
        GREEDY_EXCHANGE_TRAP_SAT, analyze_basis_exchange=True
    )
    assert width["basis_maximum_support_histogram"] == {"2": 8, "3": 43}
    exchange = width["basis_exchange"]
    assert exchange["connected"]
    assert exchange["basis_nodes"] == 51
    assert exchange["exchange_edges"] == 297
    assert exchange["optimum_basis_nodes"] == 8
    assert exchange["nonglobal_local_minima"] == 19
    assert exchange["strict_descent_reaches_optimum"] == 32
    assert exchange["nonincreasing_reaches_optimum"] == 51
    assert exchange["maximum_distance_to_optimum"] == 3
    assert exchange["first_nonglobal_local_minimum"] == {
        "pivot_columns": [1, 2, 4, 5, 6, 7],
        "free_columns": [3, 8, 9],
        "width": 3,
        "uncovered_pivots": 3,
    }


def test_dual_triangle_profile_recovers_clause_circuits_and_extras() -> None:
    profile = cubic_kernel_dual_triangle_profile(GREEDY_EXCHANGE_TRAP_SAT)
    triangles = {tuple(triangle) for triangle in profile["triangles"]}
    assert set(GREEDY_EXCHANGE_TRAP_SAT) <= triangles
    assert profile["dual_rank"] == 3
    assert profile["loop_count"] == 0
    assert profile["parallel_pair_count"] == 3
    assert profile["triangle_count"] == 12
    assert profile["clause_cocircuit_triangles"] == 9
    assert profile["additional_triangles"] == 3
    assert profile["elements_without_small_circuit"] == []


def test_some_ternary_kernel_systems_have_no_binary_support_basis() -> None:
    width = cubic_kernel_basis_width(ALL_TERNARY_BASES_SAT)
    assert width["column_subsets_checked"] == 220
    assert width["column_bases_found"] == 136
    assert width["basis_maximum_support_histogram"] == {"3": 136}
    assert width["minimum_maximum_pivot_free_support"] == 3
    assert not width["bounded_support_2sat_basis_exists"]


def test_exact_one_witness_induces_a_zero_valid_dual_basis() -> None:
    for formula in (SUPPORT_THREE_SAT, ALL_TERNARY_BASES_SAT):
        decision = decide_cubic_kernel(formula)
        assignment = decision["assignment"]
        certificate = cubic_kernel_zero_valid_basis(formula, assignment)
        assert certificate["zero_coordinate_rank"] == certificate["nullity"]
        assert all(
            assignment[column - 1] == 0
            for column in certificate["free_columns"]
        )
        assert certificate["reconstructed_kernel_vector"] == [
            3 * value - 1 for value in assignment
        ]
        assert decide_cubic_kernel(
            formula, pivot_columns=certificate["pivot_columns"]
        )["status"] == "sat"

    with pytest.raises(
        CubicKernelDecisionError,
        match="does not satisfy",
    ):
        cubic_kernel_zero_valid_basis(SUPPORT_THREE_SAT, [0] * 9)


def test_basis_width_is_invariant_under_variable_relabeling() -> None:
    relabel = {1: 7, 2: 4, 3: 9, 4: 2, 5: 5, 6: 1, 7: 8, 8: 3, 9: 6}
    relabeled = tuple(
        tuple(relabel[variable] for variable in clause)
        for clause in reversed(SUPPORT_THREE_SAT)
    )
    original = cubic_kernel_basis_width(SUPPORT_THREE_SAT)
    transformed = cubic_kernel_basis_width(relabeled)
    assert (
        original["minimum_maximum_pivot_free_support"]
        == transformed["minimum_maximum_pivot_free_support"]
        == 2
    )
    assert (
        original["basis_maximum_support_histogram"]
        == transformed["basis_maximum_support_histogram"]
    )


def test_basis_width_limits_and_nonbasis_columns_are_rejected() -> None:
    with pytest.raises(
        CubicKernelDecisionError, match="exceeding the 1 limit"
    ):
        cubic_kernel_basis_width(
            SUPPORT_THREE_SAT, maximum_column_subsets=1
        )
    with pytest.raises(
        CubicKernelDecisionError, match="do not form a column basis"
    ):
        decide_cubic_kernel(
            SUPPORT_THREE_SAT, pivot_columns=(1, 2, 3, 4, 8, 9)
        )


def test_clause_and_variable_relabeling_preserve_the_decision() -> None:
    permuted_clauses = tuple(reversed(CIRCULANT_SIX))
    relabel = {1: 4, 2: 2, 3: 6, 4: 1, 5: 5, 6: 3}
    relabeled = tuple(
        tuple(relabel[variable] for variable in clause) for clause in permuted_clauses
    )
    original = decide_cubic_kernel(CIRCULANT_SIX)
    transformed = decide_cubic_kernel(relabeled)
    assert original["status"] == transformed["status"] == "sat"
    assert satisfies(canonical_cubic_formula(relabeled), transformed["assignment"])
    assert incidence_connected(relabeled)


def test_all_fixed_gauge_cubic_formulas_through_six_variables_match_bruteforce() -> None:
    for size in range(3, 7):
        for formula in fixed_gauge_formulas(size):
            assert decide_cubic_kernel(formula)["status"] == brute_status(formula)


@pytest.mark.parametrize(
    ("mode", "formula"),
    [
        ("kernel_decision", CIRCULANT_SIX),
        ("recursive_reduction", SUPPORT_THREE_SAT),
    ],
)
def test_regional_cubic_quantum_one_round_trips_and_preserves_terminal_evidence(
    mode: str,
    formula: tuple[tuple[int, int, int], ...],
) -> None:
    if mode == "kernel_decision":
        expected = decide_cubic_kernel(formula)
    else:
        expected = reduction.solve_cubic_reduction(formula)
    assert reduction.REGIONAL_KERNEL_NAME == "exact.cubic"
    assert reduction.REGIONAL_KERNEL_MAX_WORK > 0
    assert reduction.REGIONAL_STATE_SCHEMA == "cassifi.regional-cubic-state.v1"
    state = reduction.regional_state(formula, mode=mode)
    assert set(state) == {
        "schema",
        "source",
        "profile",
        "phase",
        "continuation",
        "journal",
        "ledger",
        "result",
    }
    assert state["schema"] == "cassifi.regional-cubic-state.v1"
    assert state["continuation"]["mode"] == mode
    first_json = json.dumps(state, sort_keys=True)
    first = reduction.regional_kernel(state, {}, 1)
    assert first.status == "yield"
    assert first.work == 1
    assert json.dumps(first.state, sort_keys=True) != first_json
    state = json.loads(json.dumps(first.state, sort_keys=True))
    while first.status == "yield":
        first = reduction.regional_kernel(state, {}, 1)
        assert first.work <= 1
        state = json.loads(json.dumps(first.state, sort_keys=True))
    assert first.status == "done"
    assert first.output is not None
    assert first.output["status"] == expected["status"]
    assert first.output["assignment"] == expected["assignment"]
    if mode == "kernel_decision":
        assert first.output == expected
    else:
        assert first.output["proof"] == expected["proof"]
        assert first.output["progress"] == expected["progress"]
