from __future__ import annotations

from fractions import Fraction

import pytest

from cassi_math_language import (
    MathLanguageError,
    canonical_math_template,
    evaluate,
    instantiate_math_template,
    integer_term,
    match_math_template,
    parse_english,
    parse_latex,
    render_english,
    render_latex,
    solve_linear_equation,
    solve_linear_inequality,
    validate_math_lessons,
)


def test_english_and_latex_surfaces_share_one_canonical_term():
    latex = parse_latex(r"2x+3=11")
    english = parse_english("twice x plus three equals eleven")

    assert english == latex
    assert render_latex(english) == r"2x + 3 = 11"
    assert parse_latex(render_latex(english)) == english
    assert parse_english(render_english(english)) == english


def test_latex_fraction_and_exact_rational_evaluation_round_trip():
    term = parse_latex(r"\frac{x+3}{2}")

    assert render_latex(term) == r"\frac{3 + x}{2}"
    assert parse_latex(render_latex(term)) == term
    assert evaluate(term, {"x": 5}) == Fraction(4)


def test_exact_linear_solver_returns_replayable_derivation():
    equation = parse_english("the sum of x and three is seven")
    result = solve_linear_equation(equation)

    assert result["status"] == "supported"
    assert result["variable"] == "x"
    assert render_latex(result["solution"], boxed=True) == r"\boxed{4}"
    assert result["verified"] is True
    assert len(result["steps"]) == 3
    assert all("rule" in step and "equation" in step for step in result["steps"])
    assert all(parse_latex(render_latex(step["equation"])) == step["equation"] for step in result["steps"])


def test_linear_fraction_equation_and_degenerate_cases_are_exact():
    fraction = solve_linear_equation(parse_latex(r"\frac{x+3}{2}=5"))
    identity = solve_linear_equation(parse_latex("x+1=x+1"))
    contradiction = solve_linear_equation(parse_latex("x+1=x+2"))

    assert fraction["status"] == "supported"
    assert render_latex(fraction["solution"]) == "7"
    assert identity["status"] == "identity"
    assert contradiction["status"] == "no-solution"


def test_exact_linear_inequality_returns_interval_and_reversal_certificate():
    upper = solve_linear_inequality(parse_latex("3x+2<=11"))
    lower = solve_linear_inequality(parse_latex("-2x+4>0"))

    assert upper["status"] == "supported"
    assert upper["solution"]["upper"]["value"] == 3
    assert upper["solution"]["upper_inclusive"] is True
    assert upper["solution"]["lower"] is None
    assert upper["verified"] is True
    assert all(upper["certificate"]["checks"].values())

    assert lower["status"] == "supported"
    assert lower["solution"]["upper"]["value"] == 2
    assert lower["solution"]["upper_inclusive"] is False
    assert lower["steps"][-1]["rule"] == "divide-coefficient-reverses-relation"
    assert lower["verified"] is True


def test_linear_inequality_degenerate_and_nonlinear_cases_are_exact():
    identity = solve_linear_inequality(parse_latex("x-x<=0"), "x")
    contradiction = solve_linear_inequality(parse_latex("x-x<0"), "x")

    assert identity["status"] == "identity"
    assert contradiction["status"] == "no-solution"
    with pytest.raises(MathLanguageError, match="outside the linear solver"):
        solve_linear_inequality(parse_latex("x^2<=9"), "x")


def test_math_kernel_refuses_unsafe_or_out_of_scope_operations():
    with pytest.raises(MathLanguageError, match="unsupported LaTeX command"):
        parse_latex(r"\begin{matrix}x\end{matrix}")
    with pytest.raises(MathLanguageError, match="division by zero"):
        parse_latex(r"\frac{1}{0}")
    with pytest.raises(MathLanguageError, match="outside the linear solver"):
        solve_linear_equation(parse_latex("x^2=9"))
    with pytest.raises(MathLanguageError, match="not an exact rational"):
        evaluate(parse_latex(r"\sqrt{2}"))


def _linear_equation_template() -> dict[str, object]:
    return {
        "kind": "constructor",
        "name": "eq",
        "args": [
            {
                "kind": "constructor",
                "name": "add",
                "args": [
                    {
                        "kind": "constructor",
                        "name": "mul",
                        "args": [
                            integer_term(2),
                            {
                                "kind": "variable",
                                "name": "variable",
                                "scope": "role",
                                "type": "variable",
                            },
                        ],
                    },
                    {
                        "kind": "variable",
                        "name": "constant",
                        "scope": "role",
                        "type": "integer",
                    },
                ],
            },
            {
                "kind": "variable",
                "name": "right",
                "scope": "role",
                "type": "integer",
            },
        ],
    }


def test_typed_math_template_validates_surfaces_and_holdout():
    template = _linear_equation_template()
    lesson = validate_math_lessons(
        template=template,
        examples=[
            {
                "english": "twice x plus three equals eleven",
                "latex": "2x+3=11",
                "bindings": {
                    "variable": "x",
                    "constant": "three",
                    "right": "eleven",
                },
            }
        ],
        holdout=[
            {
                "english": "twice y plus five equals thirteen",
                "latex": "2y+5=13",
                "bindings": {
                    "variable": "y",
                    "constant": "five",
                    "right": "thirteen",
                },
            }
        ],
    )
    term = instantiate_math_template(
        canonical_math_template(template),
        {"variable": "y", "constant": "5", "right": "13"},
    )

    assert lesson["holdout"][0]["latex"] == "2y+5=13"
    assert match_math_template(template, term) == {
        "constant": "5",
        "right": "13",
        "variable": "y",
    }


def test_semantic_math_construction_interprets_solves_and_expresses():
    from cassi_field_cognition import (
        semantic_cognition_kernel,
        semantic_cognition_state,
    )

    template = _linear_equation_template()
    state = semantic_cognition_state()
    learned = semantic_cognition_kernel(
        state,
        {
            "operation": "learn-math",
            "construction_id": "linear-equation",
            "term_template": template,
            "examples": [
                {
                    "english": "twice x plus three equals eleven",
                    "latex": "2x+3=11",
                    "bindings": {
                        "variable": "x",
                        "constant": "three",
                        "right": "eleven",
                    },
                }
            ],
            "holdout": [
                {
                    "english": "twice y plus five equals thirteen",
                    "latex": "2y+5=13",
                    "bindings": {
                        "variable": "y",
                        "constant": "five",
                        "right": "thirteen",
                    },
                }
            ],
        },
        4096,
    )
    assert learned.status == "done"
    assert learned.output["status"] == "supported"
    assert learned.output["holdout_failures"] == 0

    interpreted = semantic_cognition_kernel(
        learned.state,
        {
            "operation": "interpret-math",
            "text": "twice y plus five equals thirteen",
            "solve": True,
        },
        4096,
    )
    assert interpreted.output["status"] == "supported"
    assert interpreted.output["interpretation"]["latex"] == "2y + 5 = 13"
    assert render_latex(interpreted.output["solution"]["solution"]) == "4"

    expressed = semantic_cognition_kernel(
        interpreted.state,
        {
            "operation": "express-math",
            "term": parse_latex("2y+5=13"),
        },
        4096,
    )
    assert expressed.output["status"] == "supported"
    assert expressed.output["expression"]["surface"] == (
        "twice y plus 5 equals 13"
    )


def test_semantic_math_kernel_dispatches_linear_inequalities():
    from cassi_field_cognition import semantic_cognition_kernel, semantic_cognition_state

    interpreted = semantic_cognition_kernel(
        semantic_cognition_state(),
        {
            "operation": "interpret-math",
            "surface": "latex",
            "text": "3x+2<=11",
            "solve": True,
            "variable": "x",
        },
        4096,
    )

    assert interpreted.output["status"] == "supported"
    assert interpreted.output["solution"]["status"] == "supported"
    assert interpreted.output["solution"]["solution"]["upper"]["value"] == 3
    assert interpreted.output["solution"]["solution"]["upper_inclusive"] is True
