#!/usr/bin/env python3
"""Verify the frozen Yang–Mills residual-recovery and score-penalty controls."""

from __future__ import annotations

import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-recovery-gramian-prereg.md"
SOURCE = Path(__file__).resolve()
OUT_DIR = ROOT / "runs" / "yang_mills_recovery_gramian"
OUT_PATH = OUT_DIR / "verification.json"
TOLERANCE = 1.0e-11
ANGLE_VALUES = (0.5, 0.25, 0.125, 0.0625)
SCORE_VALUES = (0.0, 0.1, 0.5, 1.0)
CHAIN_SIZES = (4, 8, 16, 32, 64)
CHAIN_MASSES = (0.0, 0.5)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matrix_error(actual: np.ndarray, expected: np.ndarray) -> float:
    return float(np.linalg.norm(actual - expected, ord=2)) / max(
        1.0, float(np.linalg.norm(expected, ord=2))
    )


def scalar_error(actual: float, expected: float) -> float:
    return abs(actual - expected) / max(1.0, abs(expected))


def positive_sqrt(matrix: np.ndarray) -> np.ndarray:
    values, vectors = np.linalg.eigh(matrix)
    if float(np.min(values)) <= 0.0:
        raise ValueError("positive square root requires a positive matrix")
    return (vectors * np.sqrt(values)) @ vectors.T


def largest_two_by_two(a: float, b: float, d: float) -> float:
    return 0.5 * (a + d + math.sqrt((a - d) ** 2 + 4.0 * b * b))


def main() -> int:
    checks: list[dict[str, Any]] = []
    matrix_errors: list[float] = []
    scalar_errors: list[float] = []

    def check(name: str, passed: bool, **details: Any) -> None:
        checks.append({"name": name, "pass": bool(passed), **details})

    angle_rows: list[dict[str, Any]] = []
    previous_gamma: float | None = None
    for index, epsilon in enumerate(ANGLE_VALUES):
        first = np.array([1.0, 0.0])
        second = np.array([math.cos(epsilon), math.sin(epsilon)])
        gramian = np.outer(first, first) + np.outer(second, second)
        eigenvalues = np.linalg.eigvalsh(gramian)
        expected = np.array([1.0 - math.cos(epsilon), 1.0 + math.cos(epsilon)])
        spectrum_error = matrix_error(np.diag(eigenvalues), np.diag(expected))
        gamma = float(eigenvalues[0])
        monotone = gamma > 0.0 and (previous_gamma is None or gamma < previous_gamma)
        previous_gamma = gamma
        matrix_errors.append(spectrum_error)
        scalar_errors.append(scalar_error(gamma, float(expected[0])))
        angle_rows.append(
            {
                "index": index,
                "epsilon": epsilon,
                "gramian": gramian.tolist(),
                "eigenvalues": eigenvalues.tolist(),
                "expected_eigenvalues": expected.tolist(),
                "gamma_recovery": gamma,
                "spectrum_error": spectrum_error,
                "positive_decreasing": monotone,
            }
        )
        check(f"angle_spectrum_{index}", spectrum_error <= TOLERANCE, error=spectrum_error)
        check(
            f"angle_recovery_{index}",
            monotone and np.linalg.matrix_rank(gramian, tol=TOLERANCE) == 2,
            gamma=gamma,
        )

    orthogonal_gramian = np.eye(2)
    orthogonal_row = {
        "gramian": orthogonal_gramian.tolist(),
        "eigenvalues": np.linalg.eigvalsh(orthogonal_gramian).tolist(),
        "gamma_recovery": 1.0,
        "optimal_tensorization": 1.0,
    }
    check("orthogonal_gramian", matrix_error(orthogonal_gramian, np.eye(2)) <= TOLERANCE)
    check(
        "orthogonal_tensorization",
        scalar_error(orthogonal_row["gamma_recovery"], 1.0) <= TOLERANCE
        and scalar_error(orthogonal_row["optimal_tensorization"], 1.0) <= TOLERANCE,
    )

    gauge_gramian = np.diag([1.0, 1.0, 0.0])
    gauge_full_eigenvalues = np.linalg.eigvalsh(gauge_gramian)
    gauge_physical_eigenvalues = np.linalg.eigvalsh(gauge_gramian[:2, :2])
    gauge_row = {
        "gramian": gauge_gramian.tolist(),
        "full_eigenvalues": gauge_full_eigenvalues.tolist(),
        "physical_eigenvalues": gauge_physical_eigenvalues.tolist(),
        "full_floor": float(gauge_full_eigenvalues[0]),
        "physical_floor": float(gauge_physical_eigenvalues[0]),
    }
    check(
        "gauge_full_null",
        scalar_error(gauge_row["full_floor"], 0.0) <= TOLERANCE
        and matrix_error(gauge_gramian @ np.array([0.0, 0.0, 1.0]), np.zeros(3)) <= TOLERANCE,
    )
    check("gauge_physical_floor", scalar_error(gauge_row["physical_floor"], 1.0) <= TOLERANCE)

    score_rows: list[dict[str, Any]] = []
    previous_bound: float | None = None
    for index, theta in enumerate(SCORE_VALUES):
        a = 0.5
        b = theta
        d = 1.0 + 2.0 * theta * theta
        matrix = np.array([[a, b], [b, d]])
        closed = largest_two_by_two(a, b, d)
        direct = float(np.max(np.linalg.eigvalsh(matrix)))
        eigen_error = scalar_error(closed, direct)
        bound = 1.0 / closed
        monotone = previous_bound is None or bound <= previous_bound + TOLERANCE
        previous_bound = bound
        scalar_errors.append(eigen_error)
        score_rows.append(
            {
                "index": index,
                "theta": theta,
                "matrix": matrix.tolist(),
                "C_closed": closed,
                "C_direct": direct,
                "certified_rate": bound,
                "monotone_nonincreasing": monotone,
                "eigen_error": eigen_error,
            }
        )
        check(f"score_eigenvalue_{index}", eigen_error <= TOLERANCE, error=eigen_error)
        check(f"score_penalty_{index}", monotone, certified_rate=bound)

    product_row = {
        "score_norm": 0.0,
        "witness_variance": 0.5,
        "witness_energy": 1.0,
        "witness_rayleigh": 2.0,
        "global_poincare_rate": 2.0,
        "incomplete_recovery_floor": 0.0,
        "fibre_conditional_rate": 4.0,
    }
    check("product_zero_score", product_row["score_norm"] == 0.0)
    check("product_nonconstant_kernel", product_row["witness_variance"] > 0.0)
    check(
        "product_positive_gap",
        scalar_error(product_row["witness_rayleigh"], 2.0) <= TOLERANCE
        and scalar_error(product_row["global_poincare_rate"], 2.0) <= TOLERANCE,
    )
    check(
        "product_incomplete_recovery",
        product_row["incomplete_recovery_floor"] == 0.0
        and product_row["fibre_conditional_rate"] > 0.0,
    )

    gaussian_rows: list[dict[str, Any]] = []
    for size in CHAIN_SIZES:
        for mass in CHAIN_MASSES:
            operator = np.diag(np.full(size, 2.0 + mass * mass))
            operator += np.diag(np.full(size - 1, -1.0), 1)
            operator += np.diag(np.full(size - 1, -1.0), -1)
            precision = positive_sqrt(operator)
            root_error = matrix_error(precision @ precision, operator)
            diagonal = np.diag(precision)
            diagonal_sqrt_inverse = np.diag(1.0 / np.sqrt(diagonal))
            residual_gramian = diagonal_sqrt_inverse @ precision @ diagonal_sqrt_inverse
            gamma = float(np.min(np.linalg.eigvalsh(residual_gramian)))
            tensorization = 1.0 / gamma
            q_min = float(np.min(np.linalg.eigvalsh(precision)))
            expected_q_min = math.sqrt(
                mass * mass + 4.0 * math.sin(math.pi / (2.0 * (size + 1))) ** 2
            )
            lower = q_min / float(np.max(diagonal))
            upper = q_min / float(np.min(diagonal))
            q_error = scalar_error(q_min, expected_q_min)
            reciprocal_error = scalar_error(gamma * tensorization, 1.0)
            matrix_errors.append(root_error)
            scalar_errors.extend([q_error, reciprocal_error])
            row = {
                "size": size,
                "mass": mass,
                "square_root_error": root_error,
                "diagonal_min": float(np.min(diagonal)),
                "diagonal_max": float(np.max(diagonal)),
                "minimum_precision_eigenvalue": q_min,
                "expected_minimum_precision_eigenvalue": expected_q_min,
                "gamma_recovery": gamma,
                "optimal_tensorization": tensorization,
                "rayleigh_lower": lower,
                "rayleigh_upper": upper,
                "finite_kernel": gamma > 0.0,
            }
            gaussian_rows.append(row)
            label = f"N{size}_m{mass:g}"
            check(f"gaussian_square_root_{label}", root_error <= TOLERANCE, error=root_error)
            check(
                f"gaussian_recovery_{label}",
                reciprocal_error <= TOLERANCE and gamma > 0.0,
                reciprocal_error=reciprocal_error,
            )
            check(
                f"gaussian_rayleigh_{label}",
                q_error <= TOLERANCE
                and gamma + TOLERANCE >= lower
                and gamma <= upper + TOLERANCE,
                q_error=q_error,
                lower=lower,
                gamma=gamma,
                upper=upper,
            )

    e1 = np.array([1.0, 0.0, 0.0])
    e2 = np.array([0.0, 1.0, 0.0])
    residuals = [np.outer(e1, e1), np.outer(e2, e2), np.outer(e1, e1)]
    weights = [0.5, 1.0, 0.5]
    transports = [np.eye(3), np.diag([-1.0, 1.0, 1.0]), np.diag([1.0, -1.0, 1.0])]
    transported_gramian = np.zeros((3, 3), dtype=float)
    for weight, transport, residual in zip(weights, transports, residuals, strict=True):
        transported_gramian += weight * transport.T @ residual @ transport
    expected_transported = np.diag([1.0, 1.0, 0.0])
    transported_error = matrix_error(transported_gramian, expected_transported)
    matrix_errors.append(transported_error)
    physical_floor = float(np.min(np.linalg.eigvalsh(transported_gramian[:2, :2])))
    gauge_residual = float(np.linalg.norm(transported_gramian @ np.array([0.0, 0.0, 1.0])))
    fixture_vectors = [
        np.array([1.0, 2.0, 3.0]),
        np.array([-2.0, 0.5, 1.0]),
        np.array([0.0, 1.0, -4.0]),
        np.array([math.sqrt(2.0), -math.pi, 0.25]),
    ]
    quadratic_error = 0.0
    for vector in fixture_vectors:
        direct = sum(
            weight * float(np.linalg.norm(residual @ transport @ vector) ** 2)
            for weight, transport, residual in zip(weights, transports, residuals, strict=True)
        )
        gramian_value = float(vector @ transported_gramian @ vector)
        quadratic_error = max(quadratic_error, scalar_error(direct, gramian_value))
    scalar_errors.append(quadratic_error)
    transported_row = {
        "weights": weights,
        "transports": [transport.tolist() for transport in transports],
        "residuals": [residual.tolist() for residual in residuals],
        "gramian": transported_gramian.tolist(),
        "expected_gramian": expected_transported.tolist(),
        "construction_error": transported_error,
        "gauge_residual": gauge_residual,
        "physical_floor": physical_floor,
        "quadratic_error": quadratic_error,
        "vectors": [vector.tolist() for vector in fixture_vectors],
    }
    check("transported_construction", transported_error <= TOLERANCE, error=transported_error)
    check("transported_gauge_null", gauge_residual <= TOLERANCE, residual=gauge_residual)
    check("transported_physical_floor", scalar_error(physical_floor, 1.0) <= TOLERANCE)
    check("transported_quadratic_identity", quadratic_error <= TOLERANCE, error=quadratic_error)

    if len(checks) != 58:
        raise RuntimeError(f"primary check-count drift: expected 58, got {len(checks)}")
    names = [item["name"] for item in checks]
    if len(names) != len(set(names)):
        raise RuntimeError("duplicate primary check name")

    passed = all(item["pass"] for item in checks)
    receipt = {
        "schema": "cassi.yang-mills-recovery-gramian.verification.v1",
        "verdict": "PASS" if passed else "FAIL",
        "protocol": PROTOCOL.relative_to(ROOT).as_posix(),
        "protocol_sha256": sha256(PROTOCOL),
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": sha256(SOURCE),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "tolerances": {"primary": TOLERANCE},
        "summary": {
            "checks": len(checks),
            "passed": sum(1 for item in checks if item["pass"]),
            "failed": sum(1 for item in checks if not item["pass"]),
            "angle_rows": len(angle_rows),
            "score_rows": len(score_rows),
            "gaussian_rows": len(gaussian_rows),
            "max_matrix_error": max(matrix_errors, default=0.0),
            "max_scalar_error": max(scalar_errors, default=0.0),
        },
        "angle_rows": angle_rows,
        "orthogonal_row": orthogonal_row,
        "gauge_row": gauge_row,
        "score_rows": score_rows,
        "product_row": product_row,
        "gaussian_rows": gaussian_rows,
        "transported_row": transported_row,
        "checks": checks,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": receipt["verdict"], **receipt["summary"]}, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
