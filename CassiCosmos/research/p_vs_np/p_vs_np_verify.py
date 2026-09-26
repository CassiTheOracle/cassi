#!/usr/bin/env python
"""Independently verify the frozen Cassi P-versus-NP probe receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

ARMS = {"coherence", "static_gradient", "capped_ctds", "exp_ctds"}
EXPECTED_FAMILIES = {
    "exhaustive3": 255,
    "planted2": 12,
    "planted3": 32,
    "xor3": 8,
    "adversarial": 4,
    "unsat_control": 2,
}
STRUCTURAL_LIMIT = 1.0e-9
REPRESENTATION_LIMIT = 1.0e-12
MARGIN_LIMIT = 1.0e-3
CAP_CTDS = 64.0


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def formula(raw: Any) -> tuple[tuple[tuple[int, int], ...], ...]:
    return tuple(tuple((int(literal[0]), int(literal[1])) for literal in clause) for clause in raw)


def certify(state: np.ndarray, clauses: tuple[tuple[tuple[int, int], ...], ...]) -> tuple[bool, int, float]:
    assignment = state >= 0.0
    violated = sum(
        not any(bool(assignment[var]) == (sign > 0) for var, sign in clause)
        for clause in clauses
    )
    return violated == 0, int(violated), float(np.min(np.abs(state)))


def exact_sat(n: int, clauses: tuple[tuple[tuple[int, int], ...], ...]) -> bool:
    for bits in range(1 << n):
        if all(
            any(bool(bits & (1 << var)) == (sign > 0) for var, sign in clause)
            for clause in clauses
        ):
            return True
    return False


def aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    keys = sorted({(run["arm"], run["family"], run["n"]) for run in runs})
    for arm, family, n in keys:
        selected = [run for run in runs if run["arm"] == arm and run["family"] == family and run["n"] == n]
        successful = [run for run in selected if run["success"]]
        result[f"{arm}/{family}/n{n}"] = {
            "runs": len(selected),
            "successes": len(successful),
            "success_rate": len(successful) / len(selected),
            "median_solution_steps": float(np.median([run["first_solution_step"] for run in successful])) if successful else None,
            "max_solution_steps": max((run["first_solution_step"] for run in successful), default=None),
            "max_derivative_evaluations": max(run["derivative_evaluations"] for run in selected),
            "max_clause_weight": max(run["max_clause_weight"] for run in selected),
            "max_log2_clause_weight": max(run["max_log2_clause_weight"] for run in selected),
            "min_success_margin": min((run["success_margin"] for run in successful), default=None),
            "total_clamps": sum(run["clamp_count"] for run in selected),
        }
    return result


def same_json_numbers(left: Any, right: Any, path: str = "root") -> None:
    if isinstance(left, dict):
        require(isinstance(right, dict) and set(left) == set(right), f"{path}: key mismatch")
        for key in left:
            same_json_numbers(left[key], right[key], f"{path}.{key}")
    elif isinstance(left, list):
        require(isinstance(right, list) and len(left) == len(right), f"{path}: list mismatch")
        for index, item in enumerate(left):
            same_json_numbers(item, right[index], f"{path}[{index}]")
    elif isinstance(left, float):
        require(isinstance(right, (int, float)) and math.isclose(left, float(right), rel_tol=1e-14, abs_tol=1e-14), f"{path}: number mismatch")
    else:
        require(left == right, f"{path}: value mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", nargs="?", default="_diag/p_vs_np_probe.json")
    args = parser.parse_args()

    receipt_path = Path(args.receipt)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(receipt.get("schema") == "cassi.p-vs-np-probe.v1", "schema mismatch")
    prereg = Path(__file__).with_name("p_vs_np_prereg.md")
    require(receipt.get("prereg_sha256") == hashlib.sha256(prereg.read_bytes()).hexdigest(), "prereg hash mismatch")
    require(receipt.get("seed") == 20260909, "seed mismatch")

    cases = receipt["cases"]
    counts: dict[str, int] = {}
    indexed: dict[str, dict[str, Any]] = {}
    for case in cases:
        require(case["name"] not in indexed, f"duplicate case {case['name']}")
        indexed[case["name"]] = case
        counts[case["family"]] = counts.get(case["family"], 0) + 1
        clauses = formula(case["clauses"])
        require(all(0 <= var < case["n"] and sign in (-1, 1) for clause in clauses for var, sign in clause), f"bad literal in {case['name']}")
        require(exact_sat(case["n"], clauses) is case["expected_sat"], f"wrong SAT label for {case['name']}")
    require(counts == EXPECTED_FAMILIES, f"family counts mismatch: {counts}")

    starts = int(receipt["parameters"]["starts"])
    runs = receipt["runs"]
    require(len(runs) == len(cases) * starts * len(ARMS), "run count mismatch")
    seen: set[tuple[str, str, int]] = set()
    for run in runs:
        key = (run["case"], run["arm"], run["start"])
        require(key not in seen, f"duplicate run {key}")
        seen.add(key)
        require(run["arm"] in ARMS, f"unknown arm {run['arm']}")
        require(0 <= run["start"] < starts, f"bad start {key}")
        case = indexed[run["case"]]
        require(run["family"] == case["family"] and run["n"] == case["n"], f"case metadata mismatch {key}")
        require(run["m"] == len(case["clauses"]) and run["expected_sat"] is case["expected_sat"], f"case dimensions mismatch {key}")
        state = np.asarray(run["final_state"], dtype=np.float64)
        require(state.shape == (case["n"],) and bool(np.all(np.isfinite(state))), f"bad final state {key}")
        success, violated, margin = certify(state, formula(case["clauses"]))
        require(run["success"] is success, f"success mismatch {key}")
        require(run["final_violated"] == violated, f"violation mismatch {key}")
        if success:
            require(run["first_solution_step"] is not None, f"missing solution step {key}")
            require(math.isclose(run["success_margin"], margin, rel_tol=1e-13, abs_tol=1e-13), f"margin mismatch {key}")
        else:
            require(run["first_solution_step"] is None and run["success_margin"] is None, f"spurious solution metadata {key}")
        require(0 <= run["steps"] <= receipt["parameters"]["max_steps"], f"step bound mismatch {key}")
        require(run["derivative_evaluations"] == run["steps"], f"evaluation count mismatch {key}")
        for field, value in run.items():
            if field.startswith("max_") or field in ("physical_time",):
                require(value is None or math.isfinite(float(value)), f"nonfinite {field} in {key}")
        if run["arm"] == "capped_ctds":
            require(run["max_clause_weight"] <= CAP_CTDS * (1.0 + 1e-14), f"capped weight exceeded in {key}")
        if run["arm"] == "exp_ctds":
            require(run["max_clause_weight"] <= receipt["parameters"]["expanded_ctds"] * (1.0 + 1e-14), f"expanded weight exceeded in {key}")
        if not case["expected_sat"]:
            require(not run["success"], f"false positive in {key}")

    recomputed_aggregate = aggregate(runs)
    same_json_numbers(recomputed_aggregate, receipt["aggregate"], "aggregate")

    structural = receipt["structural"]
    structural_metrics = [
        structural["normal_mode_parity_max_abs"],
        structural["weighted_invariant_max_relative_drift"],
        structural["superposition_max_abs"],
        structural["affine_fast_forward_max_abs"],
    ]
    require(all(math.isfinite(value) for value in structural_metrics), "nonfinite structural metric")
    structural_max = max(structural_metrics)
    require(math.isclose(structural["maximum_residual"], structural_max, rel_tol=0.0, abs_tol=1e-18), "structural maximum mismatch")
    structural_verdict = "PASS" if structural_max <= STRUCTURAL_LIMIT else "FAIL"
    require(structural["verdict"] == structural_verdict, "structural verdict mismatch")

    representation = receipt["representation"]
    representation_max = max(
        representation["permutation_vector_field_max_abs"],
        representation["irrelevant_variable_vector_field_max_abs"],
    )
    require(math.isclose(representation["maximum_residual"], representation_max, rel_tol=0.0, abs_tol=1e-18), "representation maximum mismatch")
    representation_verdict = "PASS" if representation_max <= REPRESENTATION_LIMIT else "FAIL"
    require(representation["verdict"] == representation_verdict, "representation verdict mismatch")

    coherence_sat = [run for run in runs if run["arm"] == "coherence" and run["expected_sat"]]
    coherence_unsat = [run for run in runs if run["arm"] == "coherence" and not run["expected_sat"]]
    s2_ok = (
        all(run["success"] for run in coherence_sat)
        and not any(run["success"] for run in coherence_unsat)
        and min((run["success_margin"] or 0.0 for run in coherence_sat), default=0.0) >= MARGIN_LIMIT
    )

    capped = {(run["case"], run["start"]): run for run in runs if run["arm"] == "capped_ctds"}
    expanded = {(run["case"], run["start"]): run for run in runs if run["arm"] == "exp_ctds"}
    s3_ok = True
    for key, expanded_run in expanded.items():
        if not expanded_run["expected_sat"]:
            continue
        capped_run = capped[key]
        if capped_run["success"] != expanded_run["success"]:
            s3_ok = False
        if expanded_run["success"] and expanded_run["max_clause_weight"] > CAP_CTDS and not capped_run["success"]:
            s3_ok = False

    expected_verdicts = {
        "S1_linear_structure": structural_verdict,
        "S2_bounded_coherence": "SUPPORTS" if s2_ok else "CONTRADICTS",
        "S3_bounded_clause_memory": "SUPPORTS" if s3_ok else "CONTRADICTS",
        "S4_representation_invariance": representation_verdict,
    }
    expected_verdicts["overall"] = (
        "ADOPT"
        if structural_verdict == "PASS" and s2_ok and s3_ok and representation_verdict == "PASS"
        else "REJECT"
    )
    require(receipt["verdicts"] == expected_verdicts, "overall verdict mismatch")

    print(f"VERIFIED {len(cases)} formulas, {len(runs)} matched runs")
    print(f"S1 maximum residual: {structural_max:.6e} ({structural_verdict})")
    print(f"S4 maximum residual: {representation_max:.6e} ({representation_verdict})")
    print(json.dumps(expected_verdicts, indent=2))
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
