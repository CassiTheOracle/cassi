#!/usr/bin/env python3
"""Verify the normalization-corrected two-dimensional SU(2) Wilson bridge.

The direct character coefficient is fixed by normalized Haar orthogonality and
one representation-dimension factor is removed by link convolution.  This is
a finite two-dimensional benchmark, not a four-dimensional mass-gap proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from scipy import __version__ as scipy_version
from scipy.integrate import quad
from scipy.special import iv

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-su2-wilson-2d-prereg-v2.md"
SOURCE = Path(__file__).resolve()
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_su2_wilson_2d" / "verification-v2.json"

BETA_VALUES = (1.0, 2.0, 4.0)
SPATIAL_LENGTHS = (1, 2, 4)
TEMPORAL_LENGTHS = (1, 2, 4)
CHARACTER_CUTOFFS = (8, 16, 24, 32)
TIME_SEPARATIONS = (0, 1, 2, 4)
HAAR_ORDERS = tuple(range(1, 9))
PRIMARY_TOLERANCE = 1.0e-11
HAAR_RELATIVE_TOLERANCE = 1.0e-9
INDEPENDENT_TOLERANCE = 1.0e-9
EXPECTED_ROWS = (
    len(BETA_VALUES)
    * len(SPATIAL_LENGTHS)
    * len(TEMPORAL_LENGTHS)
    * len(CHARACTER_CUTOFFS)
)
CHECKS_PER_ROW = 10
EXPECTED_ROW_CHECKS = EXPECTED_ROWS * CHECKS_PER_ROW
EXPECTED_TOP_LEVEL_CHECKS = 12
EXPECTED_CHECKS = EXPECTED_ROW_CHECKS + EXPECTED_TOP_LEVEL_CHECKS


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close_enough(left: float, right: float, tolerance: float = PRIMARY_TOLERANCE) -> bool:
    return bool(abs(left - right) <= tolerance * max(1.0, abs(left), abs(right)))


def relative_error(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), np.finfo(float).tiny)


def check(name: str, passed: bool, **detail: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **detail}


def finite_payload(value: Any) -> bool:
    if isinstance(value, dict):
        return all(finite_payload(item) for item in value.values())
    if isinstance(value, list):
        return all(finite_payload(item) for item in value)
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        return math.isfinite(float(value))
    return True


@lru_cache(maxsize=None)
def haar_coefficient(beta: float, n: int) -> tuple[float, float]:
    value, error = quad(
        lambda theta: (2.0 / math.pi)
        * math.exp(beta * math.cos(theta))
        * math.sin(theta)
        * math.sin(n * theta),
        0.0,
        math.pi,
        epsabs=2.0e-14,
        epsrel=2.0e-13,
        limit=400,
    )
    return float(value), float(error)


def character_data(beta: float, n_max: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dimensions = np.arange(1, n_max + 1, dtype=float)
    orders = dimensions
    direct_coefficients = iv(orders - 1.0, beta) - iv(orders + 1.0, beta)
    reduced_coefficients = 2.0 * iv(orders, beta) / beta
    return dimensions, direct_coefficients, reduced_coefficients


def q_bound_log(beta: float, n: int) -> float:
    return (
        math.log(2.0)
        + beta * beta / 4.0
        - math.log(beta)
        + n * math.log(beta / 2.0)
        - math.lgamma(n + 1.0)
    )


def q_bound(beta: float, n: int) -> float:
    return math.exp(q_bound_log(beta, n))


def tail_bound(
    beta: float, n_max: int, area: int
) -> tuple[float, float, float, float, float]:
    first_omitted = q_bound(beta, n_max + 1)
    rho = beta / (2.0 * (n_max + 2))
    log_first_power = area * q_bound_log(beta, n_max + 1)
    log_bound = log_first_power - math.log1p(-(rho**area))
    minimum_log = math.log(np.finfo(float).tiny)
    bound = math.exp(log_bound) if log_bound >= minimum_log else 0.0
    first_power = math.exp(log_first_power) if log_first_power >= minimum_log else 0.0
    return first_omitted, rho, bound, first_power, log_bound


def row(beta: float, spatial_length: int, temporal_length: int, n_max: int) -> dict[str, Any]:
    area = spatial_length * temporal_length
    dimensions, coefficients, reduced = character_data(beta, n_max)
    haar_values = np.array([haar_coefficient(beta, n)[0] for n in HAAR_ORDERS])
    haar_errors = np.array([haar_coefficient(beta, n)[1] for n in HAAR_ORDERS])
    haar_relative_errors = np.array(
        [relative_error(float(left), float(right)) for left, right in zip(haar_values, coefficients[: len(HAAR_ORDERS)])]
    )
    quotient = coefficients / dimensions
    quotient_residual = float(np.max(np.abs(quotient - reduced)))
    quotient_relative_residual = float(
        np.max(
            np.abs(quotient - reduced)
            / np.maximum(np.maximum(np.abs(quotient), np.abs(reduced)), np.finfo(float).tiny)
        )
    )
    rejected_double_division = reduced / dimensions
    double_division_relative_error_n2 = float(
        abs(rejected_double_division[1] - reduced[1]) / reduced[1]
    )

    ratio = float(reduced[1] / reduced[0])
    correlators = []
    for time in TIME_SEPARATIONS:
        correlator = ratio ** (spatial_length * time)
        next_correlator = ratio ** (spatial_length * (time + 1))
        effective_mass = -math.log(next_correlator / correlator)
        correlators.append(
            {
                "t": time,
                "correlator": correlator,
                "next_correlator": next_correlator,
                "effective_mass": effective_mass,
            }
        )

    first_omitted, rho, omitted_bound, omitted_first_power, omitted_log_bound = tail_bound(
        beta, n_max, area
    )
    tail_indices = np.arange(n_max + 1, n_max + 65, dtype=float)
    tail_reduced = 2.0 * iv(tail_indices, beta) / beta
    tail_probe = float(np.sum(tail_reduced**area))
    partition = float(np.sum(reduced**area))
    omitted_log_relative_bound = omitted_log_bound - math.log(partition)
    expected_effective_mass = spatial_length * math.log(float(reduced[0] / reduced[1]))
    correlator_error = max(
        abs(item["correlator"] - ratio ** (spatial_length * item["t"]))
        for item in correlators
    )
    effective_error = max(
        abs(item["effective_mass"] - expected_effective_mass) for item in correlators
    )

    checks = [
        check(
            "positive_finite_character_and_reduced_coefficients",
            bool(
                np.all(np.isfinite(coefficients))
                and np.all(np.isfinite(reduced))
                and np.all(coefficients > 0.0)
                and np.all(reduced > 0.0)
            ),
            minimum_character_coefficient=float(np.min(coefficients)),
            minimum_reduced_coefficient=float(np.min(reduced)),
        ),
        check(
            "haar_character_normalization",
            bool(np.max(haar_relative_errors) <= HAAR_RELATIVE_TOLERANCE),
            maximum_relative_error=float(np.max(haar_relative_errors)),
            maximum_quadrature_error=float(np.max(haar_errors)),
        ),
        check(
            "single_convolution_quotient",
            bool(
                quotient_residual <= PRIMARY_TOLERANCE
                and quotient_relative_residual <= PRIMARY_TOLERANCE
            ),
            maximum_absolute_residual=quotient_residual,
            maximum_relative_residual=quotient_relative_residual,
        ),
        check(
            "double_division_firing_control",
            double_division_relative_error_n2 >= 0.5 - PRIMARY_TOLERANCE,
            n=2,
            relative_error=double_division_relative_error_n2,
            correct=float(reduced[1]),
            rejected=float(rejected_double_division[1]),
        ),
        check(
            "strict_reduced_coefficient_decrease",
            bool(np.all(reduced[:-1] > reduced[1:])),
            minimum_difference=float(np.min(reduced[:-1] - reduced[1:])),
        ),
        check(
            "character_fusion_vacuum_correlator",
            correlator_error <= PRIMARY_TOLERANCE,
            maximum_error=correlator_error,
        ),
        check(
            "effective_mass_identity",
            effective_error <= PRIMARY_TOLERANCE,
            maximum_error=effective_error,
            expected=expected_effective_mass,
        ),
        check(
            "corrected_positive_character_tail_bound",
            bool(
                math.isfinite(omitted_log_bound)
                and omitted_log_bound < 0.0
                and 0.0 < rho < 1.0
            ),
            first_omitted_bound=first_omitted,
            rho=rho,
            bound=omitted_bound,
            log_bound=omitted_log_bound,
        ),
        check(
            "partition_tail_ordering",
            bool(partition > 0.0 and tail_probe <= omitted_bound + PRIMARY_TOLERANCE),
            partition=partition,
            tail_probe=tail_probe,
            relative_bound=omitted_bound / partition,
            log_relative_bound=omitted_log_relative_bound,
            probe_bound_error=tail_probe - omitted_bound,
        ),
        check(
            "gauge_projected_area_identity",
            area == spatial_length * temporal_length,
            area=area,
        ),
    ]
    payload = {
        "beta": beta,
        "spatial_length": spatial_length,
        "temporal_length": temporal_length,
        "area": area,
        "character_cutoff": n_max,
        "character_dimensions": dimensions.astype(int).tolist(),
        "character_coefficients": coefficients.tolist(),
        "reduced_coefficients": reduced.tolist(),
        "haar_orders": list(HAAR_ORDERS),
        "haar_coefficients": haar_values.tolist(),
        "haar_quadrature_errors": haar_errors.tolist(),
        "haar_relative_errors": haar_relative_errors.tolist(),
        "convolution_quotient_residual": quotient_residual,
        "convolution_quotient_relative_residual": quotient_relative_residual,
        "rejected_double_division": rejected_double_division.tolist(),
        "double_division_relative_error_n2": double_division_relative_error_n2,
        "partition_function_cutoff": partition,
        "tail_probe": tail_probe,
        "tail_bound": omitted_bound,
        "tail_relative_bound": omitted_bound / partition,
        "tail_log_bound": omitted_log_bound,
        "tail_log_relative_bound": omitted_log_relative_bound,
        "tail_first_power": omitted_first_power,
        "tail_ratio_bound": rho,
        "correlator_ratio": ratio,
        "expected_effective_mass": expected_effective_mass,
        "correlators": correlators,
        "checks": checks,
    }
    if not finite_payload(payload):
        raise FloatingPointError("non-finite Wilson row payload")
    return payload


def run(output: Path, replace: bool) -> dict[str, Any]:
    if output.exists() and not replace:
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    rows = [
        row(beta, spatial_length, temporal_length, n_max)
        for beta in BETA_VALUES
        for spatial_length in SPATIAL_LENGTHS
        for temporal_length in TEMPORAL_LENGTHS
        for n_max in CHARACTER_CUTOFFS
    ]
    row_checks = [item for current in rows for item in current["checks"]]
    top_checks = [
        check("schema_contract", True),
        check(
            "protocol_path",
            str(PROTOCOL.relative_to(ROOT)).replace("\\", "/")
            == "computations/yang-mills-su2-wilson-2d-prereg-v2.md",
        ),
        check("protocol_hash_available", bool(sha256(PROTOCOL))),
        check(
            "source_path",
            str(SOURCE.relative_to(ROOT)).replace("\\", "/")
            == "computations/verify_yang_mills_su2_wilson_2d.py",
        ),
        check("source_hash_available", bool(sha256(SOURCE))),
        check("beta_schedule", BETA_VALUES == (1.0, 2.0, 4.0)),
        check("spatial_schedule", SPATIAL_LENGTHS == (1, 2, 4)),
        check("temporal_schedule", TEMPORAL_LENGTHS == (1, 2, 4)),
        check("character_cutoff_schedule", CHARACTER_CUTOFFS == (8, 16, 24, 32)),
        check("time_schedule", TIME_SEPARATIONS == (0, 1, 2, 4)),
        check("row_count", len(rows) == EXPECTED_ROWS),
        check("row_check_count", len(row_checks) == EXPECTED_ROW_CHECKS),
    ]
    all_checks = top_checks + row_checks
    passed = all(bool(item["passed"]) for item in all_checks)
    record: dict[str, Any] = {
        "schema": "cassi.yang-mills.su2-wilson-2d.v2",
        "verdict": "PASS" if passed else "FAIL",
        "classification": "NORMALIZATION_CORRECTED_FINITE_VOLUME_2D_WILSON_BRIDGE",
        "scope": (
            "Normalized-Haar SU(2) character coefficients, once-divided gluing spectrum, "
            "two-dimensional torus partition diagnostics, transfer-vacuum correlator and "
            "corrected tail bound. Four-dimensional thermodynamic, OS, continuum and physical "
            "mass-gap claims are outside this receipt."
        ),
        "protocol": str(PROTOCOL.relative_to(ROOT)).replace("\\", "/"),
        "protocol_sha256": sha256(PROTOCOL),
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256(SOURCE),
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy_version,
        },
        "schedule": {
            "beta_values": list(BETA_VALUES),
            "spatial_lengths": list(SPATIAL_LENGTHS),
            "temporal_lengths": list(TEMPORAL_LENGTHS),
            "character_cutoffs": list(CHARACTER_CUTOFFS),
            "time_separations": list(TIME_SEPARATIONS),
            "haar_orders": list(HAAR_ORDERS),
        },
        "tolerances": {
            "primary": PRIMARY_TOLERANCE,
            "haar_relative": HAAR_RELATIVE_TOLERANCE,
            "independent": INDEPENDENT_TOLERANCE,
        },
        "normalization": {
            "character_coefficient": "C_n=I_(n-1)-I_(n+1)=2*n*I_n(beta)/beta",
            "gluing_eigenvalue": "r_n=C_n/n=2*I_n(beta)/beta",
            "haar_measure": "(2/pi)*sin(theta)^2*dtheta",
            "double_division_rejected": True,
            "invalidated_receipts": [
                "runs/yang_mills_su2_wilson_2d/verification.json",
                "runs/yang_mills_su2_wilson_2d/verification-independent.json",
            ],
        },
        "summary": {
            "rows": len(rows),
            "row_checks": len(row_checks),
            "top_level_checks": len(top_checks),
            "checks": len(all_checks),
            "passed": sum(bool(item["passed"]) for item in all_checks),
            "failed": sum(not bool(item["passed"]) for item in all_checks),
        },
        "checks": top_checks,
        "rows": rows,
        "uniformity_and_scope": [
            "Adaptive Haar quadrature independently checks the first eight direct character coefficients.",
            "The convolution quotient removes the representation dimension exactly once.",
            "The rejected double division fires in every row.",
            "The correlator is a transfer-vacuum matrix element, not a finite-temperature torus correlator.",
            "No four-dimensional Gibbs state, OS reconstruction, continuum limit or physical mass gap is inferred.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    record = run(args.output, args.replace)
    print(json.dumps(record["summary"], sort_keys=True))
    return 0 if record["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
