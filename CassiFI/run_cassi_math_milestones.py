"""Measure field-backed math complexity from one persisted CassiFI state."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from cassi_field_cognition import _canonical_semantic_state, semantic_cognition_kernel
from cassi_math_language import evaluate, parse_latex


DEFAULT_STATE_INPUT = Path("CassiFI/_diag/math/gsm8k_training_state_2.json")
_ADAPTIVE_KEYS = (
    "beliefs",
    "bounds",
    "family",
    "invalidation",
    "libraries",
    "records",
    "schema",
    "scope",
)


CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "m0-integer",
        "milestone": "M0 exact atoms and rationals",
        "level": 0,
        "surface": "latex",
        "text": "42",
        "latex": "42",
        "kind": "ground",
        "expected": "42",
    },
    {
        "id": "m0-rational",
        "milestone": "M0 exact atoms and rationals",
        "level": 0,
        "surface": "latex",
        "text": r"\frac{7}{3}",
        "latex": r"\frac{7}{3}",
        "kind": "ground",
        "expected": "7/3",
    },
    {
        "id": "m1-add",
        "milestone": "M1 learned binary arithmetic",
        "level": 1,
        "surface": "english",
        "text": "( 123 plus 456 )",
        "latex": "123+456",
        "kind": "ground",
        "learned": True,
        "expected": "579",
    },
    {
        "id": "m1-sub",
        "milestone": "M1 learned binary arithmetic",
        "level": 1,
        "surface": "english",
        "text": "( 900 minus 127 )",
        "latex": "900-127",
        "kind": "ground",
        "learned": True,
        "expected": "773",
    },
    {
        "id": "m1-mul",
        "milestone": "M1 learned binary arithmetic",
        "level": 1,
        "surface": "english",
        "text": "( 37 times 24 )",
        "latex": "37*24",
        "kind": "ground",
        "learned": True,
        "expected": "888",
    },
    {
        "id": "m1-div",
        "milestone": "M1 learned binary arithmetic",
        "level": 1,
        "surface": "english",
        "text": "( 84 divided by 18 )",
        "latex": "84/18",
        "kind": "ground",
        "learned": True,
        "expected": "14/3",
    },
    {
        "id": "m2-learned-composition",
        "milestone": "M2 learned composition",
        "level": 2,
        "surface": "english",
        "text": "( ( 2 plus 3 ) times 4 )",
        "latex": "(2+3)*4",
        "kind": "ground",
        "learned": True,
        "expected": "20",
    },
    {
        "id": "m2-exact-composition",
        "milestone": "M2 exact composition",
        "level": 2,
        "surface": "latex",
        "text": "(2+3)*(4-1)",
        "latex": "(2+3)*(4-1)",
        "kind": "ground",
        "expected": "15",
    },
    {
        "id": "m3-power",
        "milestone": "M3 exact nonlinear arithmetic",
        "level": 3,
        "surface": "latex",
        "text": "3^4",
        "latex": "3^4",
        "kind": "ground",
        "expected": "81",
    },
    {
        "id": "m3-square-root",
        "milestone": "M3 exact nonlinear arithmetic",
        "level": 3,
        "surface": "latex",
        "text": r"\sqrt{144}",
        "latex": r"\sqrt{144}",
        "kind": "ground",
        "expected": "12",
    },
    {
        "id": "m4-relation",
        "milestone": "M4 exact relations",
        "level": 4,
        "surface": "latex",
        "text": "7*6>=42",
        "latex": "7*6>=42",
        "kind": "ground",
        "expected": "True",
    },
    {
        "id": "m5-linear-integer",
        "milestone": "M5 one-variable linear solving",
        "level": 5,
        "surface": "latex",
        "text": "2x+3=11",
        "latex": "2x+3=11",
        "kind": "solve",
        "variable": "x",
        "expected_solution": "4",
    },
    {
        "id": "m5-linear-rational",
        "milestone": "M5 one-variable linear solving",
        "level": 5,
        "surface": "latex",
        "text": r"\frac{3}{2}x-1=5",
        "latex": r"\frac{3}{2}x-1=5",
        "kind": "solve",
        "variable": "x",
        "expected_solution": "4",
    },
    {
        "id": "m6-nonlinear-boundary",
        "milestone": "M6 nonlinear solver boundary",
        "level": 6,
        "surface": "latex",
        "text": "x^2=9",
        "latex": "x^2=9",
        "kind": "refusal",
        "variable": "x",
        "expected_solution_status": "support-gap",
    },
    {
        "id": "m7-inequality-eval",
        "milestone": "M7 inequality solving",
        "level": 7,
        "surface": "latex",
        "text": "3*4<=12",
        "latex": "3*4<=12",
        "kind": "ground",
        "expected": "True",
    },
    {
        "id": "m7-linear-inequality",
        "milestone": "M7 inequality solving",
        "level": 7,
        "surface": "latex",
        "text": "3x+2<=11",
        "latex": "3x+2<=11",
        "kind": "solve-inequality",
        "variable": "x",
        "expected_solution_status": "supported",
        "expected_upper": "3",
        "expected_upper_inclusive": True,
    },
    {
        "id": "m8-linear-algebra",
        "milestone": "M8 linear algebra",
        "level": 8,
        "surface": "english",
        "text": "determinant of [[1, 2], [3, 4]]",
        "kind": "future",
        "future_capability": "vectors, matrices, and exact linear systems",
    },
    {
        "id": "m9-polynomial-algebra",
        "milestone": "M9 polynomial algebra",
        "level": 9,
        "surface": "english",
        "text": "expand (x + 1)^2",
        "kind": "future",
        "future_capability": "expand and collect polynomial expressions",
    },
    {
        "id": "m10-polynomial-equations",
        "milestone": "M10 polynomial equations",
        "level": 10,
        "surface": "english",
        "text": "solve x^2 - 5x + 6 = 0",
        "kind": "future",
        "future_capability": "solve polynomial equations with certificates",
    },
    {
        "id": "m11-rational-functions",
        "milestone": "M11 rational functions",
        "level": 11,
        "surface": "english",
        "text": "simplify 1/(x+1) + 1/(x+1)",
        "kind": "future",
        "future_capability": "simplify rational functions and state domains",
    },
    {
        "id": "m12-functions",
        "milestone": "M12 functions",
        "level": 12,
        "surface": "english",
        "text": "compose f and g",
        "kind": "future",
        "future_capability": "compose, invert, and transform functions",
    },
    {
        "id": "m13-sequences",
        "milestone": "M13 sequences",
        "level": 13,
        "surface": "english",
        "text": "fibonacci(10)",
        "kind": "future",
        "future_capability": "recurrences, induction checks, and closed forms",
    },
    {
        "id": "m14-geometry",
        "milestone": "M14 geometry",
        "level": 14,
        "surface": "english",
        "text": "distance between (0, 0) and (3, 4)",
        "kind": "future",
        "future_capability": "Euclidean and coordinate geometry",
    },
    {
        "id": "m15-trigonometry",
        "milestone": "M15 trigonometry",
        "level": 15,
        "surface": "english",
        "text": "sin(pi/6)",
        "kind": "future",
        "future_capability": "identities, triangles, and periodic functions",
    },
    {
        "id": "m16-complex-numbers",
        "milestone": "M16 complex numbers",
        "level": 16,
        "surface": "english",
        "text": "sqrt(-1)",
        "kind": "future",
        "future_capability": "complex arithmetic, roots, and polar form",
    },
    {
        "id": "m17-calculus",
        "milestone": "M17 calculus",
        "level": 17,
        "surface": "english",
        "text": "derivative of x^3",
        "kind": "future",
        "future_capability": "limits, derivatives, and local expansions",
    },
    {
        "id": "m18-analysis",
        "milestone": "M18 analysis",
        "level": 18,
        "surface": "english",
        "text": "integral from 0 to 1 of x^2",
        "kind": "future",
        "future_capability": "integrals, differential equations, and convergence",
    },
    {
        "id": "m19-probability",
        "milestone": "M19 probability",
        "level": 19,
        "surface": "english",
        "text": "probability of two heads in two flips",
        "kind": "future",
        "future_capability": "random variables, expectation, and distributions",
    },
    {
        "id": "m20-combinatorics",
        "milestone": "M20 combinatorics",
        "level": 20,
        "surface": "english",
        "text": "choose 10 items 3 at a time",
        "kind": "future",
        "future_capability": "counting, recurrences, and extremal constructions",
    },
    {
        "id": "m21-discrete-mathematics",
        "milestone": "M21 discrete mathematics",
        "level": 21,
        "surface": "english",
        "text": "shortest path in a finite graph",
        "kind": "future",
        "future_capability": "graphs, algorithms, and finite structures",
    },
    {
        "id": "m22-abstract-algebra",
        "milestone": "M22 abstract algebra",
        "level": 22,
        "surface": "english",
        "text": "order of the element 2 modulo 7",
        "kind": "future",
        "future_capability": "groups, rings, fields, and homomorphisms",
    },
    {
        "id": "m23-gcd",
        "milestone": "M23 number theory foundations",
        "level": 23,
        "surface": "english",
        "text": "gcd( 48, 18 )",
        "kind": "future",
        "future_capability": "greatest common divisor",
    },
    {
        "id": "m23-modulus",
        "milestone": "M23 number theory foundations",
        "level": 23,
        "surface": "english",
        "text": "29 mod 5",
        "kind": "future",
        "future_capability": "modular remainder",
    },
    {
        "id": "m24-prime-test",
        "milestone": "M24 primality",
        "level": 24,
        "surface": "english",
        "text": "prime( 97 )",
        "kind": "future",
        "future_capability": "certified primality testing",
    },
    {
        "id": "m25-factorization",
        "milestone": "M25 factorization",
        "level": 25,
        "surface": "english",
        "text": "factor( 360 )",
        "kind": "future",
        "future_capability": "prime factorization with a product certificate",
    },
    {
        "id": "m26-prime-generation",
        "milestone": "M26 prime generation",
        "level": 26,
        "surface": "english",
        "text": "primes up to 30",
        "kind": "future",
        "future_capability": "calculate and certify successive prime numbers",
    },
)


MATH_ROADMAP: tuple[dict[str, Any], ...] = (
    {"level": 0, "family": "exact number representation", "capability": "integers and rationals", "status": "measured", "anchor_case_ids": ["m0-integer", "m0-rational"]},
    {"level": 1, "family": "learned arithmetic", "capability": "learned add, subtract, multiply, divide", "status": "measured", "anchor_case_ids": ["m1-add", "m1-sub", "m1-mul", "m1-div"]},
    {"level": 2, "family": "composition", "capability": "compose learned constructions", "status": "measured-partial", "anchor_case_ids": ["m2-learned-composition", "m2-exact-composition"]},
    {"level": 3, "family": "nonlinear arithmetic", "capability": "powers and exact roots", "status": "measured", "anchor_case_ids": ["m3-power", "m3-square-root"]},
    {"level": 4, "family": "order theory", "capability": "equalities and inequalities", "status": "measured", "anchor_case_ids": ["m4-relation"]},
    {"level": 5, "family": "algebra", "capability": "one-variable linear equations", "status": "measured", "anchor_case_ids": ["m5-linear-integer", "m5-linear-rational"]},
    {"level": 6, "family": "solver boundaries", "capability": "correct nonlinear refusal", "status": "measured", "anchor_case_ids": ["m6-nonlinear-boundary"]},
    {"level": 7, "family": "inequality solving", "capability": "one-variable linear inequalities", "status": "measured", "anchor_case_ids": ["m7-inequality-eval", "m7-linear-inequality"]},
    {"level": 8, "family": "linear algebra", "capability": "simultaneous equations, vectors, and matrices", "status": "planned", "anchor_case_ids": ["m8-linear-algebra"]},
    {"level": 9, "family": "polynomial algebra", "capability": "expansion, collection, and factor identities", "status": "planned", "anchor_case_ids": ["m9-polynomial-algebra"]},
    {"level": 10, "family": "polynomial equations", "capability": "roots, multiplicity, and exact certificates", "status": "planned", "anchor_case_ids": ["m10-polynomial-equations"]},
    {"level": 11, "family": "rational functions", "capability": "domains, simplification, and partial fractions", "status": "planned", "anchor_case_ids": ["m11-rational-functions"]},
    {"level": 12, "family": "functions", "capability": "composition, inverses, and transformations", "status": "planned", "anchor_case_ids": ["m12-functions"]},
    {"level": 13, "family": "sequences", "capability": "recurrences, induction checks, and closed forms", "status": "planned", "anchor_case_ids": ["m13-sequences"]},
    {"level": 14, "family": "geometry", "capability": "Euclidean and coordinate geometry", "status": "planned", "anchor_case_ids": ["m14-geometry"]},
    {"level": 15, "family": "trigonometry", "capability": "identities, triangles, and periodic functions", "status": "planned", "anchor_case_ids": ["m15-trigonometry"]},
    {"level": 16, "family": "complex numbers", "capability": "complex arithmetic, roots, and polar form", "status": "planned", "anchor_case_ids": ["m16-complex-numbers"]},
    {"level": 17, "family": "calculus", "capability": "limits, derivatives, and local expansions", "status": "planned", "anchor_case_ids": ["m17-calculus"]},
    {"level": 18, "family": "analysis", "capability": "integrals, differential equations, and convergence", "status": "planned", "anchor_case_ids": ["m18-analysis"]},
    {"level": 19, "family": "probability", "capability": "random variables, expectation, and distributions", "status": "planned", "anchor_case_ids": ["m19-probability"]},
    {"level": 20, "family": "combinatorics", "capability": "counting, recurrences, and extremal constructions", "status": "planned", "anchor_case_ids": ["m20-combinatorics"]},
    {"level": 21, "family": "discrete mathematics", "capability": "graphs, algorithms, and finite structures", "status": "planned", "anchor_case_ids": ["m21-discrete-mathematics"]},
    {"level": 22, "family": "abstract algebra", "capability": "groups, rings, fields, and homomorphisms", "status": "planned", "anchor_case_ids": ["m22-abstract-algebra"]},
    {"level": 23, "family": "number theory", "capability": "divisibility, gcd, congruences, and orders", "status": "planned", "anchor_case_ids": ["m23-gcd", "m23-modulus"]},
    {"level": 24, "family": "primality", "capability": "certified primality testing", "status": "planned", "anchor_case_ids": ["m24-prime-test"]},
    {"level": 25, "family": "factorization", "capability": "prime factorization with independent verification", "status": "planned", "anchor_case_ids": ["m25-factorization"]},
    {"level": 26, "family": "prime generation", "capability": "calculate and certify successive prime numbers", "status": "terminal-target", "anchor_case_ids": ["m26-prime-generation"]},
)


def _reference_is_prime(value: int) -> bool:
    if value < 2:
        return False
    if value % 2 == 0:
        return value == 2
    divisor = 3
    while divisor * divisor <= value:
        if value % divisor == 0:
            return False
        divisor += 2
    return True


def _prime_goal() -> dict[str, Any]:
    anchors = (2, 3, 5, 97, 7919, 104729)
    return {
        "terminal_level": 26,
        "status": "planned",
        "capability": "calculate and independently certify successive primes",
        "primality_anchors": [
            {"number": number, "is_prime": _reference_is_prime(number)}
            for number in anchors
        ],
        "first_generation_target": {
            "inclusive_limit": 1000,
            "expected_prime_count": 168,
            "last_prime": 997,
        },
        "verification_rule": "redivide every reported candidate by all integers through floor(sqrt(candidate))",
    }


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canonical_bytes(value)
    return hashlib.sha256(raw).hexdigest()


def _load_checkpoint(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    decoded = json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, Mapping):
        raise ValueError("math benchmark checkpoint must be a JSON object")
    return _canonical_semantic_state(decoded), _sha256(raw)


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> str:
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(encoded)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return _sha256(encoded)


def _adaptive_digest(state: Mapping[str, Any]) -> str:
    return _sha256({key: state[key] for key in _ADAPTIVE_KEYS})


def _adaptive_changed_keys(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> list[str]:
    return [
        key
        for key in _ADAPTIVE_KEYS
        if before.get(key) != after.get(key)
    ]


def _value_text(value: Any) -> str:
    return str(value)


def _transition(
    state: dict[str, Any],
    case: Mapping[str, Any],
    *,
    operation_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    request: dict[str, Any] = {
        "operation": "interpret-math",
        "operation_id": operation_id,
        "surface": case["surface"],
        "text": case["text"],
    }
    if case.get("kind") in {"solve", "solve-inequality", "refusal"}:
        request["solve"] = True
        request["variable"] = case["variable"]
    transition = semantic_cognition_kernel(state, request, 4096)
    if transition.status != "done":
        raise RuntimeError(f"benchmark transition did not finish: {transition.status}")
    return transition.state, transition.output


def _score_case(case: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    alternatives = result.get("alternatives", [])
    if not isinstance(alternatives, list):
        alternatives = []
    construction_ids = sorted(
        {
            str(item["construction_id"])
            for item in alternatives
            if isinstance(item, Mapping) and item.get("construction_id") is not None
        }
    )
    output: dict[str, Any] = {
        "id": case["id"],
        "milestone": case["milestone"],
        "level": case["level"],
        "surface": case["surface"],
        "kind": case["kind"],
        "status": result.get("status"),
        "alternative_count": len(alternatives),
        "construction_ids": construction_ids,
        "passed": False,
    }
    if case["kind"] == "ground":
        expected = case["expected"]
        exact_matches: list[str] = []
        for alternative in alternatives:
            if not isinstance(alternative, Mapping):
                continue
            try:
                actual = _value_text(evaluate(alternative["term"]))
            except Exception:  # noqa: BLE001 - one case must not hide the board
                continue
            if actual == expected:
                exact_matches.append(str(alternative.get("construction_id")))
        output["expected"] = expected
        output["exact_matches"] = exact_matches
        output["field_exact"] = bool(exact_matches)
        output["learned_exact"] = any(
            value != "None" for value in exact_matches
        )
        output["passed"] = bool(exact_matches) and (
            not case.get("learned", False) or output["learned_exact"]
        )
    elif case["kind"] == "solve":
        expected = case["expected_solution"]
        solution_matches: list[str] = []
        solution_statuses: list[str] = []
        for alternative in alternatives:
            if not isinstance(alternative, Mapping):
                continue
            solution = alternative.get("solution")
            if not isinstance(solution, Mapping):
                continue
            status = str(solution.get("status"))
            solution_statuses.append(status)
            if status == "supported" and isinstance(solution.get("solution"), Mapping):
                candidate = solution["solution"]
                if candidate.get("kind") == "atom":
                    solution_matches.append(str(candidate.get("value")))
        output["expected_solution"] = expected
        output["solution_statuses"] = sorted(set(solution_statuses))
        output["solution_matches"] = solution_matches
        output["passed"] = expected in solution_matches
    elif case["kind"] == "solve-inequality":
        expected_status = case["expected_solution_status"]
        solution_statuses = []
        interval_matches = []
        for alternative in alternatives:
            if not isinstance(alternative, Mapping):
                continue
            solution = alternative.get("solution")
            if not isinstance(solution, Mapping):
                continue
            status = str(solution.get("status"))
            solution_statuses.append(status)
            interval = solution.get("solution")
            if (
                status == "supported"
                and isinstance(interval, Mapping)
                and interval.get("kind") == "interval"
            ):
                upper = interval.get("upper")
                try:
                    upper_text = _value_text(evaluate(upper))
                except Exception:  # noqa: BLE001 - one case must not hide the board
                    upper_text = None
                if (
                    upper_text == case["expected_upper"]
                    and interval.get("upper_inclusive")
                    is case["expected_upper_inclusive"]
                ):
                    interval_matches.append(str(alternative.get("construction_id")))
        output["expected_solution_status"] = expected_status
        output["expected_upper"] = case["expected_upper"]
        output["expected_upper_inclusive"] = case["expected_upper_inclusive"]
        output["solution_statuses"] = sorted(set(solution_statuses))
        output["interval_matches"] = interval_matches
        output["passed"] = expected_status in solution_statuses and bool(
            interval_matches
        )
    elif case["kind"] == "future":
        output["future_capability"] = case["future_capability"]
        output["planned"] = True
        output["passed"] = False
    elif case["kind"] == "refusal":
        expected_status = case["expected_solution_status"]
        solution_statuses = []
        for alternative in alternatives:
            if isinstance(alternative, Mapping):
                solution = alternative.get("solution")
                if isinstance(solution, Mapping):
                    solution_statuses.append(str(solution.get("status")))
        output["expected_solution_status"] = expected_status
        output["solution_statuses"] = sorted(set(solution_statuses))
        output["passed"] = bool(alternatives) and bool(solution_statuses) and all(
            status == expected_status for status in solution_statuses
        )
    return output


def run_benchmark(state_input: Path) -> dict[str, Any]:
    state, state_input_sha256 = _load_checkpoint(state_input)
    starting_transitions = int(state["ledger"]["transitions"])
    operation_prefix = f"math-benchmark:{state_input_sha256[:16]}:{starting_transitions}"
    adaptive_before = {
        key: json.loads(json.dumps(state[key], sort_keys=True))
        for key in _ADAPTIVE_KEYS
    }
    rows: list[dict[str, Any]] = []
    for index, case in enumerate(CASES):
        try:
            state, result = _transition(
                state,
                case,
                operation_id=f"{operation_prefix}:{index}:{case['id']}",
            )
            row = _score_case(case, result)
        except Exception as exc:  # noqa: BLE001 - record bounded refusal per case
            row = {
                "id": case["id"],
                "milestone": case["milestone"],
                "level": case["level"],
                "surface": case["surface"],
                "kind": case["kind"],
                "passed": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        rows.append(row)
    adaptive_after = {
        key: json.loads(json.dumps(state[key], sort_keys=True))
        for key in _ADAPTIVE_KEYS
    }
    changed_keys = _adaptive_changed_keys(adaptive_before, adaptive_after)
    adaptive_before_digest = _sha256(adaptive_before)
    adaptive_after_digest = _sha256(adaptive_after)
    memory_preserved = not changed_keys

    milestones: list[dict[str, Any]] = []
    for level in sorted({int(case["level"]) for case in CASES}):
        level_rows = [row for row in rows if row["level"] == level]
        milestones.append(
            {
                "level": level,
                "milestone": level_rows[0]["milestone"],
                "passed": all(row["passed"] for row in level_rows),
                "passed_cases": sum(1 for row in level_rows if row["passed"]),
                "total_cases": len(level_rows),
            }
        )
    highest_contiguous = -1
    for milestone in milestones:
        if not milestone["passed"]:
            break
        highest_contiguous = int(milestone["level"])
    next_milestone = next(
        (milestone for milestone in milestones if not milestone["passed"]),
        None,
    )
    if next_milestone is None:
        next_target = {
            "level": highest_contiguous + 1,
            "milestone": "complete board",
            "failed_cases": [],
            "goal": "Extend the board with a harder held-out family.",
        }
    else:
        next_target = {
            "level": int(next_milestone["level"]),
            "milestone": next_milestone["milestone"],
            "failed_cases": [
                row["id"]
                for row in rows
                if row["level"] == next_milestone["level"] and not row["passed"]
            ],
            "goal": (
                "Make every learned-field case in this milestone pass while "
                "preserving exact held-out verification."
            ),
        }

    return {
        "schema": "cassifi.math-milestones.v1",
        "state": {
            "input": str(state_input),
            "input_sha256": state_input_sha256,
            "starting_transitions": starting_transitions,
            "benchmark_transitions": len(CASES),
            "ending_transitions_in_memory": int(state["ledger"]["transitions"]),
            "adaptive_digest_before": adaptive_before_digest,
            "adaptive_digest_after": adaptive_after_digest,
            "adaptive_changed_keys": changed_keys,
            "memory_preserved_during_inference": memory_preserved,
        },
        "milestones": milestones,
        "highest_contiguous_milestone": highest_contiguous,
        "next_target": next_target,
        "roadmap": list(MATH_ROADMAP),
        "prime_goal": _prime_goal(),
        "cases": rows,
        "boundaries": [
            "all executable cases ran sequentially through one loaded field state",
            "the benchmark wrote no successor state and created no control field",
            "exact values and linear solutions were checked from the independent math kernel",
            "learned cases require a non-null field construction, while exact-surface cases do not",
            "the roadmap spans the computational spine from exact arithmetic through prime generation; it is not a proof of all mathematical theorems",
            "the nonlinear solver boundary is scored as a refusal milestone, not as a solved equation",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-input", type=Path, default=DEFAULT_STATE_INPUT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_benchmark(args.state_input)
    _write_json_atomic(args.output, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
