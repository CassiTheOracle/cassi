#!/usr/bin/env python3
"""Verify the frozen conditional transport-score recurrence and Gaussian controls."""

from __future__ import annotations

import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-transport-score-prereg.md"
SOURCE = Path(__file__).resolve()
OUT_DIR = ROOT / "runs" / "yang_mills_transport_score"
OUT_PATH = OUT_DIR / "verification.json"
MATRIX_TOL = 1.0e-10
ALGEBRAIC_TOL = 1.0e-11
CHAIN_SIZES = (4, 8, 16, 32, 64)
CHAIN_MASSES = (0.0, 0.5)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matrix_error(actual: np.ndarray, expected: np.ndarray) -> float:
    numerator = float(np.linalg.norm(actual - expected, ord=2))
    denominator = max(1.0, float(np.linalg.norm(expected, ord=2)))
    return numerator / denominator


def scalar_error(actual: float, expected: float) -> float:
    return abs(actual - expected) / max(1.0, abs(expected))


def positive_sqrt(matrix: np.ndarray) -> np.ndarray:
    values, vectors = np.linalg.eigh(matrix)
    if float(np.min(values)) <= 0.0:
        raise ValueError("positive_sqrt requires a positive matrix")
    return (vectors * np.sqrt(values)) @ vectors.T


def largest_two_by_two(a: float, b: float, d: float) -> float:
    return 0.5 * (a + d + math.sqrt((a - d) ** 2 + 4.0 * b * b))


def recurrence(lambda_c: float, lambda_fib: float, score_coefficient: float) -> dict[str, float]:
    a = 1.0 / (2.0 * lambda_c)
    b = score_coefficient / lambda_c
    d = 2.0 * (1.0 / lambda_fib + score_coefficient * score_coefficient / lambda_c)
    c_closed = largest_two_by_two(a, b, d)
    c_direct = float(np.max(np.linalg.eigvalsh(np.array([[a, b], [b, d]], dtype=float))))
    return {
        "A": a,
        "B": b,
        "D": d,
        "C_closed": c_closed,
        "C_direct": c_direct,
        "bound": 1.0 / c_closed,
    }


def block_metrics(precision: np.ndarray, retained: np.ndarray) -> dict[str, Any]:
    size = precision.shape[0]
    retained_set = set(int(index) for index in retained)
    eliminated = np.array([index for index in range(size) if index not in retained_set], dtype=int)
    q_vv = precision[np.ix_(retained, retained)]
    q_vr = precision[np.ix_(retained, eliminated)]
    q_rv = precision[np.ix_(eliminated, retained)]
    q_rr = precision[np.ix_(eliminated, eliminated)]
    transport = -np.linalg.solve(q_rr, q_rv)
    discarded = q_vr @ np.linalg.solve(q_rr, q_rv)
    q_eff = q_vv - discarded

    lambda_c = 2.0 * float(np.min(np.linalg.eigvalsh(q_eff)))
    lambda_fib = 2.0 * float(np.min(np.linalg.eigvalsh(q_rr)))
    theta = float(np.linalg.norm(transport, ord=2))
    theta_sq = theta * theta
    score_covariance = 2.0 * discarded
    kappa_sq = float(np.max(np.linalg.eigvalsh(score_covariance)))
    relaxed_theta_sq = kappa_sq / lambda_fib

    hminus1 = recurrence(lambda_c, lambda_fib, theta)
    l2_score = recurrence(lambda_c, lambda_fib, math.sqrt(max(0.0, relaxed_theta_sq)))

    metric_weights = np.full(size, 0.5, dtype=float)
    metric_weights[retained] = 2.0
    metric_sqrt = np.diag(np.sqrt(metric_weights))
    exact_gap = 2.0 * float(np.min(np.linalg.eigvalsh(metric_sqrt @ precision @ metric_sqrt)))

    schur_inverse_error = matrix_error(
        np.linalg.inv(q_eff),
        np.linalg.inv(precision)[np.ix_(retained, retained)],
    )
    transport_identity_error = matrix_error(
        q_rr @ transport + q_rv,
        np.zeros_like(q_rv),
    )

    return {
        "retained": retained.tolist(),
        "eliminated": eliminated.tolist(),
        "lambda_c": lambda_c,
        "lambda_fib": lambda_fib,
        "theta": theta,
        "theta_sq": theta_sq,
        "kappa_sq": kappa_sq,
        "kappa_sq_over_lambda_fib": relaxed_theta_sq,
        "comparison_factor": relaxed_theta_sq / theta_sq if theta_sq > 0.0 else 1.0,
        "hminus1_recurrence": hminus1,
        "l2_recurrence": l2_score,
        "exact_anisotropic_gap": exact_gap,
        "schur_inverse_error": schur_inverse_error,
        "transport_identity_error": transport_identity_error,
        "minimum_q_eff_eigenvalue": float(np.min(np.linalg.eigvalsh(q_eff))),
        "minimum_q_rr_eigenvalue": float(np.min(np.linalg.eigvalsh(q_rr))),
    }


def chain_precision(size: int, mass: float) -> tuple[np.ndarray, np.ndarray]:
    matrix = np.diag(np.full(size, 2.0 + mass * mass))
    matrix += np.diag(np.full(size - 1, -1.0), 1)
    matrix += np.diag(np.full(size - 1, -1.0), -1)
    return matrix, positive_sqrt(matrix)


def main() -> int:
    checks: list[dict[str, Any]] = []
    matrix_errors: list[float] = []
    scalar_errors: list[float] = []

    def check(name: str, passed: bool, **details: Any) -> None:
        checks.append({"name": name, "pass": bool(passed), **details})

    chain_rows: list[dict[str, Any]] = []
    for size in CHAIN_SIZES:
        for mass in CHAIN_MASSES:
            dirichlet, precision = chain_precision(size, mass)
            retained = np.arange(0, size, 2, dtype=int)
            metrics = block_metrics(precision, retained)
            sqrt_error = matrix_error(precision @ precision, dirichlet)
            matrix_errors.extend(
                [sqrt_error, metrics["schur_inverse_error"], metrics["transport_identity_error"]]
            )

            hminus1 = metrics["hminus1_recurrence"]
            l2_score = metrics["l2_recurrence"]
            c_error = scalar_error(hminus1["C_closed"], hminus1["C_direct"])
            scalar_errors.append(c_error)

            row = {
                "size": size,
                "mass": mass,
                "square_root_error": sqrt_error,
                **metrics,
            }
            chain_rows.append(row)
            label = f"N{size}_m{mass:g}"
            check(f"chain_square_root_{label}", sqrt_error <= MATRIX_TOL, error=sqrt_error)
            check(
                f"chain_schur_{label}",
                metrics["schur_inverse_error"] <= MATRIX_TOL
                and metrics["minimum_q_eff_eigenvalue"] > 0.0,
                error=metrics["schur_inverse_error"],
            )
            check(
                f"chain_transport_{label}",
                metrics["transport_identity_error"] <= MATRIX_TOL
                and metrics["theta_sq"] <= metrics["kappa_sq_over_lambda_fib"] + ALGEBRAIC_TOL,
                error=metrics["transport_identity_error"],
            )
            check(
                f"chain_recurrence_{label}",
                c_error <= ALGEBRAIC_TOL
                and hminus1["bound"] + ALGEBRAIC_TOL >= l2_score["bound"],
                error=c_error,
            )
            check(
                f"chain_exact_gap_{label}",
                hminus1["bound"] <= metrics["exact_anisotropic_gap"] + ALGEBRAIC_TOL
                and l2_score["bound"] <= metrics["exact_anisotropic_gap"] + ALGEBRAIC_TOL,
                hminus1_bound=hminus1["bound"],
                l2_bound=l2_score["bound"],
                exact_gap=metrics["exact_anisotropic_gap"],
            )

    fixture_specs = [
        {
            "name": "equality",
            "precision": np.array([[2.0, -1.0, 0.0], [-1.0, 2.0, 0.0], [0.0, 0.0, 2.0]]),
            "expected_theta_sq": 0.25,
            "expected_relaxed_theta_sq": 0.25,
            "expected_factor": 1.0,
        },
        {
            "name": "strict",
            "precision": np.array([[4.0, 0.0, -3.0], [0.0, 1.0, 0.0], [-3.0, 0.0, 9.0]]),
            "expected_theta_sq": 1.0 / 9.0,
            "expected_relaxed_theta_sq": 1.0,
            "expected_factor": 9.0,
        },
    ]
    fixture_rows: list[dict[str, Any]] = []
    for spec in fixture_specs:
        metrics = block_metrics(spec["precision"], np.array([0], dtype=int))
        theta_error = scalar_error(metrics["theta_sq"], spec["expected_theta_sq"])
        relaxed_error = scalar_error(
            metrics["kappa_sq_over_lambda_fib"], spec["expected_relaxed_theta_sq"]
        )
        factor_error = scalar_error(metrics["comparison_factor"], spec["expected_factor"])
        scalar_errors.extend([theta_error, relaxed_error, factor_error])
        fixture_rows.append(
            {
                "name": spec["name"],
                "precision": spec["precision"].tolist(),
                "expected_theta_sq": spec["expected_theta_sq"],
                "expected_relaxed_theta_sq": spec["expected_relaxed_theta_sq"],
                "expected_factor": spec["expected_factor"],
                **metrics,
            }
        )
        check(f"fixture_theta_{spec['name']}", theta_error <= ALGEBRAIC_TOL, error=theta_error)
        check(
            f"fixture_l2_relaxation_{spec['name']}",
            relaxed_error <= ALGEBRAIC_TOL,
            error=relaxed_error,
        )
        check(f"fixture_factor_{spec['name']}", factor_error <= ALGEBRAIC_TOL, error=factor_error)
        check(
            f"fixture_ordering_{spec['name']}",
            metrics["hminus1_recurrence"]["bound"] + ALGEBRAIC_TOL
            >= metrics["l2_recurrence"]["bound"]
            and metrics["hminus1_recurrence"]["bound"]
            <= metrics["exact_anisotropic_gap"] + ALGEBRAIC_TOL,
        )

    margin_specs = [
        (0.0, 0.0, 0.0, 0.0, True),
        (0.0, 1.0, 0.0, 0.0, True),
        (0.0, 1.0, 0.0, 1.0e-6, False),
        (1.0, 3.0, 0.0, 3.0 / 16.0, True),
        (1.0, 3.0, 0.0, 0.19, False),
        (2.0, 4.0, 0.5, 0.175, True),
        (2.0, 4.0, 0.5, 0.18, False),
        (0.5, 3.0, 1.0, 0.0, False),
        (3.0, 0.5, 1.0, 0.0, False),
        (3.0, 10.0, 1.0, 0.1, True),
    ]
    margin_rows: list[dict[str, Any]] = []
    for index, (delta_c, delta_v, delta_f, theta_sq, expected) in enumerate(margin_specs):
        h = 1.0 / (1.0 + delta_c)
        v = 1.0 / (1.0 + delta_v)
        target = 1.0 / (1.0 + delta_f)
        theta = math.sqrt(theta_sq)
        matrix = np.array(
            [[h, 2.0 * h * theta], [2.0 * h * theta, v + 4.0 * h * theta_sq]],
            dtype=float,
        )
        direct = float(np.max(np.linalg.eigvalsh(matrix)))
        closed = largest_two_by_two(float(matrix[0, 0]), float(matrix[0, 1]), float(matrix[1, 1]))
        eigen_error = scalar_error(direct, closed)
        scalar_errors.append(eigen_error)
        matrix_pass = direct <= target + ALGEBRAIC_TOL
        budget = (target - h) * (target - v) / (4.0 * h * target)
        closed_pass = (
            h <= target + ALGEBRAIC_TOL
            and v <= target + ALGEBRAIC_TOL
            and theta_sq <= budget + ALGEBRAIC_TOL
        )
        margin_rows.append(
            {
                "index": index,
                "delta_c": delta_c,
                "delta_v": delta_v,
                "delta_f": delta_f,
                "theta_sq": theta_sq,
                "h": h,
                "v": v,
                "target": target,
                "budget": budget,
                "C_normalized_direct": direct,
                "C_normalized_closed": closed,
                "matrix_pass": matrix_pass,
                "closed_pass": closed_pass,
                "expected": expected,
            }
        )
        check(f"margin_eigenvalue_{index}", eigen_error <= ALGEBRAIC_TOL, error=eigen_error)
        check(
            f"margin_decision_{index}",
            matrix_pass == closed_pass == expected,
            matrix_pass=matrix_pass,
            closed_pass=closed_pass,
            expected=expected,
        )

    momenta = np.array([-math.pi + index * math.pi / 8.0 for index in range(17)])
    symbol_rows: list[dict[str, Any]] = []
    for mass in CHAIN_MASSES:
        q_left = np.sqrt(mass * mass + 4.0 * np.sin(momenta / 4.0) ** 2)
        q_right = np.sqrt(mass * mass + 4.0 * np.cos(momenta / 4.0) ** 2)
        a_values = 0.5 * (q_left + q_right)
        b_values = 0.5 * np.abs(q_left - q_right)
        q_eff_values = a_values - b_values * b_values / a_values
        lambda_fib_inf = 2.0 * float(np.min(a_values))
        theta_inf = float(np.max(b_values / a_values))
        zero_index = 8
        q_eff_zero = float(q_eff_values[zero_index])
        root = math.sqrt(mass * mass + 4.0)
        expected_lambda_fib = mass + root
        expected_theta = (root - mass) / (root + mass)
        expected_q_eff_zero = 0.0 if mass == 0.0 else 2.0 * mass * root / (mass + root)
        determinant_error = float(np.max(np.abs(a_values * a_values - b_values * b_values - q_left * q_right)))
        fibre_error = scalar_error(lambda_fib_inf, expected_lambda_fib)
        theta_error = scalar_error(theta_inf, expected_theta)
        coarse_error = scalar_error(q_eff_zero, expected_q_eff_zero)
        matrix_errors.append(determinant_error)
        scalar_errors.extend([fibre_error, theta_error, coarse_error])
        symbol_rows.append(
            {
                "mass": mass,
                "momenta": momenta.tolist(),
                "a_values": a_values.tolist(),
                "b_values": b_values.tolist(),
                "q_eff_values": q_eff_values.tolist(),
                "lambda_fib_infinite": lambda_fib_inf,
                "theta_infinite": theta_inf,
                "q_eff_zero": q_eff_zero,
                "expected_lambda_fib_infinite": expected_lambda_fib,
                "expected_theta_infinite": expected_theta,
                "expected_q_eff_zero": expected_q_eff_zero,
                "determinant_error": determinant_error,
            }
        )
        label = f"m{mass:g}"
        check(f"symbol_fibre_{label}", fibre_error <= ALGEBRAIC_TOL, error=fibre_error)
        check(f"symbol_transport_{label}", theta_error <= ALGEBRAIC_TOL, error=theta_error)
        check(f"symbol_coarse_{label}", coarse_error <= ALGEBRAIC_TOL, error=coarse_error)
        check(
            f"symbol_determinant_{label}",
            determinant_error <= ALGEBRAIC_TOL,
            error=determinant_error,
        )

    if len(checks) != 86:
        raise RuntimeError(f"primary check-count drift: expected 86, got {len(checks)}")
    names = [item["name"] for item in checks]
    if len(set(names)) != len(names):
        raise RuntimeError("primary check names are not unique")

    passed = all(item["pass"] for item in checks)
    receipt = {
        "schema": "cassi.yang-mills-transport-score.verification.v1",
        "verdict": "PASS" if passed else "FAIL",
        "protocol": PROTOCOL.relative_to(ROOT).as_posix(),
        "protocol_sha256": sha256(PROTOCOL),
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": sha256(SOURCE),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "tolerances": {"matrix": MATRIX_TOL, "algebraic": ALGEBRAIC_TOL},
        "summary": {
            "checks": len(checks),
            "passed": sum(1 for item in checks if item["pass"]),
            "failed": sum(1 for item in checks if not item["pass"]),
            "chain_rows": len(chain_rows),
            "fixture_rows": len(fixture_rows),
            "margin_rows": len(margin_rows),
            "symbol_rows": len(symbol_rows),
            "max_matrix_error": max(matrix_errors, default=0.0),
            "max_scalar_error": max(scalar_errors, default=0.0),
        },
        "chain_rows": chain_rows,
        "fixture_rows": fixture_rows,
        "margin_rows": margin_rows,
        "symbol_rows": symbol_rows,
        "checks": checks,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": receipt["verdict"], **receipt["summary"]}, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
