from __future__ import annotations

from fractions import Fraction

import pytest

from cassi_math_latex import (
    MathLatexError,
    MathLatexEvaluationError,
    MathLatexSyntaxError,
    evaluate_equation,
    evaluate_expression,
    parse_english_equation,
    parse_english_expression,
    parse_english_word_problem,
    parse_english_word_problem_system,
    parse_english_word_problem_chain,
    parse_english_word_problem_story,
    parse_latex_equation,
    parse_latex_expression,
    render_english,
    render_latex,
    solve_linear_equation,
    solve_english_word_problem_chain,
    solve_english_word_problem_story,
    solve_linear_system,
    verify_linear_system_trace,
    verify_linear_trace,
)
from run_cassi_math_latex import (
    ENGLISH_TRACES,
    LANGUAGE_LESSONS,
    STORY_LESSONS,
    STORY_CHAIN_LESSONS,
    SYSTEM_CLASSIFICATION_CASES,
    SYSTEM_TRACES,
    WORD_PROBLEM_LESSONS,
    WORD_PROBLEM_SYSTEM_LESSONS,
    LESSONS,
    LINEAR_TRACES,
    _run_refusal_controls,
    _validate_language_lesson,
    _validate_language_trace,
    _validate_lesson,
    _validate_story_chain_lesson,
    _validate_story_lesson,
    _validate_system_classification,
    _validate_system_trace,
    _validate_trace,
    _validate_word_problem,
    _validate_word_problem_system,
)


def test_fraction_implicit_multiplication_and_left_right_round_trip() -> None:
    expression = parse_latex_expression(r"\left(2x+1\right)\frac{3}{2}")
    assert evaluate_expression(expression, {"x": 4}) == {"numerator": 27, "denominator": 2}
    rendered = render_latex(expression)
    assert rendered == r"(2\cdot x + 1)\cdot \frac{3}{2}"
    assert render_latex(parse_latex_expression(rendered)) == rendered


def test_exact_square_root_and_greek_symbol() -> None:
    expression = parse_latex_expression(r"\sqrt{81}+\alpha^2")
    assert evaluate_expression(expression, {"alpha": 3}) == 18
    with pytest.raises(MathLatexEvaluationError):
        evaluate_expression(parse_latex_expression(r"\sqrt{2}"))


def test_linear_equation_returns_exact_rational_solution() -> None:
    equation = parse_latex_equation(r"3x+1=2")
    solution = solve_linear_equation(equation, "x")
    assert solution == {"status": "unique", "variable": "x", "value": {"numerator": 1, "denominator": 3}}
    assert evaluate_equation(equation, {"x": Fraction(1, 3)}) is True


def test_english_and_latex_share_exact_canonical_meaning() -> None:
    for lesson in LANGUAGE_LESSONS:
        english = (
            parse_english_expression(lesson["english"])
            if lesson["kind"] == "expression"
            else parse_english_equation(lesson["english"])
        )
        latex = (
            parse_latex_expression(lesson["latex"])
            if lesson["kind"] == "expression"
            else parse_latex_equation(lesson["latex"])
        )
        assert english == latex
        assert _validate_language_lesson(lesson)["status"] == "PASS"
        assert render_english(latex)


def test_english_math_refuses_unknown_words_and_round_trips_equations() -> None:
    equation = parse_english_equation("the sum of x and 2 is 5")
    assert render_latex(equation) == "x + 2 = 5"
    assert parse_english_equation(render_english(equation)) == equation
    with pytest.raises(MathLatexSyntaxError):
        parse_english_expression("the blue number of x")




def test_bounded_word_problems_normalize_to_one_exact_equation() -> None:
    for lesson in WORD_PROBLEM_LESSONS:
        problem = parse_english_word_problem(lesson["source"], lesson["variable"])
        assert problem["schema"] == "cassi.math-language.word-problem.v1"
        assert problem["equation"]["schema"] == "cassi.math-latex.equation.v1"
        assert solve_linear_equation(problem["equation"], lesson["variable"]) == lesson["expected"]
        assert _validate_word_problem(lesson)["status"] == "PASS"


def test_word_problems_reject_unbounded_named_entities_and_phrases() -> None:
    with pytest.raises(MathLatexSyntaxError):
        parse_english_word_problem("the apples plus 2 is 5")
    with pytest.raises(MathLatexSyntaxError):
        parse_english_word_problem("a mysterious quantity equals 4")


def test_multi_variable_word_problems_share_exact_system_solver() -> None:
    for lesson in WORD_PROBLEM_SYSTEM_LESSONS:
        problem = parse_english_word_problem_system(lesson["source"], lesson["variables"])
        assert problem["schema"] == "cassi.math-language.word-problem-system.v1"
        assert len(problem["equations"]) == 2
        assert solve_linear_system(problem["equations"], lesson["variables"]) == lesson["expected"]
        assert _validate_word_problem_system(lesson)["status"] == "PASS"


def test_multi_variable_word_problems_reject_ambiguous_systems() -> None:
    with pytest.raises(MathLatexSyntaxError):
        parse_english_word_problem_system("the sum of two numbers is 10")
    with pytest.raises(MathLatexSyntaxError):
        parse_english_word_problem_system("the sum of apples is 10 and their difference is 2")




def test_derived_relation_phrases_preserve_system_order() -> None:
    problem = parse_english_word_problem_system(
        "one number is 2 more than another and their sum is 10"
    )
    assert problem["normalized"] == "x is y plus 2 and x plus y is 10"
    assert problem["variables"] == ["x", "y"]
    assert solve_linear_system(problem["equations"], ("x", "y")) == {
        "status": "unique",
        "variables": {"x": 6, "y": 4},
    }


def test_derived_word_problems_reject_unbounded_relation_text() -> None:
    with pytest.raises(MathLatexSyntaxError):
        parse_english_word_problem_system(
            "one number is 2 more than another and their apples total 10"
        )


def test_named_age_and_ticket_stories_derive_exact_systems() -> None:
    for lesson in STORY_LESSONS:
        problem = parse_english_word_problem_story(
            lesson["source"], lesson["variables"], lesson["aliases"]
        )
        assert problem["schema"] == "cassi.math-language.word-problem-story.v1"
        assert len(problem["system"]["equations"]) == 2
        assert solve_english_word_problem_story(
            lesson["source"], lesson["variables"], lesson["aliases"]
        )["solution"] == lesson["expected"]
        assert _validate_story_lesson(lesson)["status"] == "PASS"


def test_story_aliases_and_cost_phrases_fail_closed() -> None:
    with pytest.raises(MathLatexSyntaxError):
        parse_english_word_problem_story(
            "alice is 4 years older than bob and their ages sum to 30",
            ("x", "y"),
            {"alice": "z", "bob": "y"},
        )
    with pytest.raises(MathLatexSyntaxError):
        parse_english_word_problem_story(
            "3 tickets cost x dollars each and 2 tickets cost y dollars each for 23 dollars total",
        )


def test_ratio_and_percentage_phrases_reduce_to_exact_fractional_equations() -> None:
    percentage = parse_english_word_problem_story(
        "one quantity is 20 percent more than another and their sum is 33"
    )
    half = parse_english_word_problem_story(
        "one quantity is half as much as another and their sum is 18"
    )
    assert percentage["normalized"] == (
        "x is y plus (20 divided by 100) times y and x plus y is 33"
    )
    assert half["normalized"] == "x is y divided by 2 and x plus y is 18"



def test_discount_markup_and_unit_price_phrases_reduce_exactly() -> None:
    discount = parse_english_word_problem_story(
        "a 20 percent discount on y gives x and x plus y equals 90"
    )
    markup = parse_english_word_problem_story(
        "a 10 percent markup on y gives x and x plus y equals 231"
    )
    units = parse_english_word_problem_story(
        "3 items cost x dollars each and 2 items cost y dollars each for 36 dollars total and x is 2 dollars more than y"
    )
    assert discount["normalized"] == (
        "x is y minus (20 divided by 100) times y and x plus y equals 90"
    )
    assert markup["normalized"] == (
        "x is y plus (10 divided by 100) times y and x plus y equals 231"
    )
    assert units["normalized"] == "3 times x plus 2 times y equals 36 and x is y plus 2"



def test_discount_then_tax_and_markup_then_tax_are_composed_exactly() -> None:
    discounted = parse_english_word_problem_story(
        "a 25 percent discount followed by 20 percent tax on y gives x and x plus y equals 38"
    )
    marked_up = parse_english_word_problem_story(
        "a 10 percent markup followed by 10 percent tax on y gives x and x plus y equals 221"
    )
    assert discounted["normalized"] == (
        "x is (y minus (25 divided by 100) times y) plus "
        "(20 divided by 100) times (y minus (25 divided by 100) times y) "
        "and x plus y equals 38"
    )
    assert marked_up["normalized"] == (
        "x is (y plus (10 divided by 100) times y) plus "
        "(10 divided by 100) times (y plus (10 divided by 100) times y) "
        "and x plus y equals 221"
    )


def test_compound_and_simple_interest_reduce_to_exact_growth() -> None:
    compound = parse_english_word_problem_story(
        "an investment y grows by 10 percent for 2 years to x and x plus y equals 221"
    )
    simple = parse_english_word_problem_story(
        "a principal y earns 5 percent simple interest for 2 years to x and x plus y equals 210"
    )
    assert compound["normalized"] == (
        "x is ((y plus (10 divided by 100) times y) plus "
        "(10 divided by 100) times (y plus (10 divided by 100) times y)) "
        "and x plus y equals 221"
    )
    assert simple["normalized"] == (
        "x is y plus (5 times 2 divided by 100) times y and x plus y equals 210"
    )



def test_intermediate_finance_chain_solves_named_states() -> None:
    problem = parse_english_word_problem_chain(
        "a 10 percent markup on y gives z and a 10 percent tax on z gives x "
        "and x plus y equals 221"
    )
    assert problem["normalized"] == (
        "z is y plus (10 divided by 100) times y and "
        "x is z plus (10 divided by 100) times z and x plus y equals 221"
    )
    solved = solve_english_word_problem_chain(
        "a 10 percent markup on y gives z and a 10 percent tax on z gives x "
        "and x plus y equals 221"
    )
    assert solved["solution"] == {
        "status": "unique",
        "variables": {"x": 121, "y": 100, "z": 110},
    }


def test_named_intermediate_story_fixtures_validate_and_solve() -> None:
    for lesson in STORY_CHAIN_LESSONS:
        payload = _validate_story_chain_lesson(lesson)
        assert payload["status"] == "PASS"
        assert payload["solution"] == lesson["expected"]

def test_english_linear_proof_trace_replays_exact_operations() -> None:
    proof = verify_linear_trace(
        ENGLISH_TRACES[0]["sources"],
        ENGLISH_TRACES[0]["variable"],
        ENGLISH_TRACES[0]["operations"],
        surface="english",
    )
    assert proof["schema"] == "cassi.math-language.linear-trace.v1"
    assert proof["status"] == "PASS"
    assert all(transition["operation_applied"] for transition in proof["transitions"])
    assert _validate_language_trace(ENGLISH_TRACES[0])["status"] == "PASS"


def test_linear_proof_trace_preserves_exact_solution_set() -> None:
    operations = (
        {"kind": "subtract_both_sides", "value": 3},
        {"kind": "divide_both_sides", "value": 2},
    )
    proof = verify_linear_trace(("2x+3=11", "2x=8", "x=4"), "x", operations)
    assert proof["status"] == "PASS"
    assert all(transition["equivalent"] for transition in proof["transitions"])
    assert all(transition["operation_applied"] for transition in proof["transitions"])
    assert [transition["operation"]["description"] for transition in proof["transitions"]] == [
        "subtract 3 from both sides",
        "divide both sides by 2",
    ]
    assert proof["steps"][-1]["solution"] == {"status": "unique", "variable": "x", "value": 4}
    assert _validate_trace(LINEAR_TRACES[0])["status"] == "PASS"


def test_linear_proof_trace_fails_closed_on_changed_solution() -> None:
    proof = verify_linear_trace(("2x+3=11", "x=5"), "x")
    assert proof["status"] == "FAIL"
    assert proof["transitions"] == [
        {
            "from_step": 0,
            "to_step": 1,
            "equivalent": False,
            "scale": {"numerator": 1, "denominator": 2},
        }
    ]
    invalid = {**LINEAR_TRACES[0], "sources": ("2x+3=11", "x=5", "x=4")}
    with pytest.raises(MathLatexError):
        _validate_trace(invalid)


def test_linear_proof_trace_rejects_wrong_operation_label() -> None:
    invalid = {
        **LINEAR_TRACES[0],
        "operations": (
            {"kind": "subtract_both_sides", "value": 3},
            {"kind": "divide_both_sides", "value": 3},
        ),
    }
    proof = verify_linear_trace(
        invalid["sources"],
        invalid["variable"],
        invalid["operations"],
    )
    assert proof["status"] == "FAIL"
    assert proof["transitions"][1]["equivalent"] is True
    assert proof["transitions"][1]["operation_applied"] is False
    with pytest.raises(MathLatexError):
        _validate_trace(invalid)
    with pytest.raises(MathLatexEvaluationError):
        verify_linear_trace(
            ("x=1", "x=1"),
            "x",
            ({"kind": "multiply_both_sides", "value": 0},),
        )


def test_variable_collection_and_movement_are_operation_checked() -> None:
    trace = LINEAR_TRACES[1]
    proof = verify_linear_trace(trace["sources"], trace["variable"], trace["operations"])
    assert proof["status"] == "PASS"
    assert all(transition["operation_applied"] for transition in proof["transitions"])
    assert [transition["operation"]["kind"] for transition in proof["transitions"]] == [
        "collect_like_terms",
        "move_variable_term_to_left",
        "divide_both_sides",
    ]
    assert _validate_trace(trace)["status"] == "PASS"


def test_variable_operation_rejects_wrong_variable() -> None:
    with pytest.raises(MathLatexEvaluationError):
        verify_linear_trace(
            ("2x=x+4", "x=4"),
            "x",
            ({"kind": "move_variable_term_to_left", "variable": "y", "coefficient": 1},),
        )


def test_fractional_coefficient_normalization_is_exact() -> None:
    trace = LINEAR_TRACES[2]
    proof = verify_linear_trace(trace["sources"], trace["variable"], trace["operations"])
    assert proof["status"] == "PASS"
    assert all(transition["operation_applied"] for transition in proof["transitions"])
    assert proof["steps"][0]["normal_form"]["coefficient"] == {
        "numerator": 3,
        "denominator": 2,
    }
    assert proof["steps"][-1]["solution"] == {"status": "unique", "variable": "x", "value": 6}
    assert _validate_trace(trace)["status"] == "PASS"


def test_signed_fractional_distribution_is_source_checked() -> None:
    trace = LINEAR_TRACES[3]
    proof = verify_linear_trace(trace["sources"], trace["variable"], trace["operations"])
    assert proof["status"] == "PASS"
    assert all(transition["operation_applied"] for transition in proof["transitions"])
    assert proof["transitions"][0]["operation"]["factor"] == {
        "numerator": -3,
        "denominator": 2,
    }
    assert proof["steps"][-1]["solution"] == {"status": "unique", "variable": "x", "value": -2}
    invalid_operations = (
        {
            "kind": "distribute_factor",
            "factor": {"numerator": 3, "denominator": 2},
            "side": "left",
        },
        *trace["operations"][1:],
    )
    with pytest.raises(MathLatexEvaluationError):
        verify_linear_trace(trace["sources"], trace["variable"], invalid_operations)


def test_two_sided_distribution_and_variable_movement_are_exact() -> None:
    trace = LINEAR_TRACES[4]
    proof = verify_linear_trace(trace["sources"], trace["variable"], trace["operations"])
    assert proof["status"] == "PASS"
    assert all(transition["operation_applied"] for transition in proof["transitions"])
    assert [transition["operation"]["kind"] for transition in proof["transitions"]] == [
        "distribute_factor",
        "distribute_factor",
        "move_variable_term_to_left",
        "subtract_both_sides",
        "divide_both_sides",
    ]
    assert proof["steps"][-1]["solution"] == {"status": "unique", "variable": "x", "value": 0}
    assert _validate_trace(trace)["status"] == "PASS"


def test_two_sided_movement_rejects_wrong_source_coefficient() -> None:
    trace = LINEAR_TRACES[4]
    invalid_operations = (
        *trace["operations"][:2],
        {
            "kind": "move_variable_term_to_left",
            "variable": "x",
            "coefficient": {"numerator": 3, "denominator": 2},
        },
        *trace["operations"][3:],
    )
    with pytest.raises(MathLatexEvaluationError):
        verify_linear_trace(trace["sources"], trace["variable"], invalid_operations)


def test_two_equation_system_trace_is_exact() -> None:
    trace = SYSTEM_TRACES[0]
    proof = verify_linear_system_trace(
        trace["states"],
        trace["variables"],
        trace["operations"],
    )
    assert proof["status"] == "PASS"
    assert all(transition["operation_applied"] for transition in proof["transitions"])
    assert proof["steps"][-1]["solution"] == {
        "status": "unique",
        "variables": {"x": 5, "y": 5},
    }
    assert _validate_system_trace(trace)["status"] == "PASS"
    equations = [
        parse_latex_equation("x+y=10"),
        parse_latex_equation("2x-y=5"),
    ]
    assert solve_linear_system(equations, ("x", "y")) == {
        "status": "unique",
        "variables": {"x": 5, "y": 5},
    }


def test_two_equation_system_trace_rejects_wrong_row_multiple() -> None:
    trace = SYSTEM_TRACES[0]
    invalid_operations = (
        {
            "kind": "add_equation_multiple",
            "target_row": 0,
            "source_row": 1,
            "multiple": 2,
        },
        *trace["operations"][1:],
    )
    proof = verify_linear_system_trace(
        trace["states"],
        trace["variables"],
        invalid_operations,
    )
    assert proof["status"] == "FAIL"
    assert proof["transitions"][0]["operation_applied"] is False


def test_singular_systems_classify_dependent_and_inconsistent() -> None:
    for case in SYSTEM_CLASSIFICATION_CASES:
        equations = [parse_latex_equation(source) for source in case["sources"]]
        assert solve_linear_system(equations, case["variables"]) == case["expected"]
        assert _validate_system_classification(case)["status"] == "PASS"
    assert solve_linear_system(
        [parse_latex_equation("0=0"), parse_latex_equation("x=1")],
        ("x", "y"),
    ) == {"status": "dependent", "variables": ["x", "y"]}


def test_linear_solver_refuses_quadratic_and_unknown_symbols() -> None:
    with pytest.raises(MathLatexEvaluationError):
        solve_linear_equation(parse_latex_equation("x^2=4"), "x")
    with pytest.raises(MathLatexEvaluationError):
        solve_linear_equation(parse_latex_equation("x+y=4"), "x")


def test_lessons_round_trip_and_refusal_controls() -> None:
    assert all(_validate_lesson(lesson)["round_trip"] for lesson in LESSONS)
    controls = _run_refusal_controls()
    assert [row["status"] for row in controls] == ["REFUSED", "REFUSED"]
