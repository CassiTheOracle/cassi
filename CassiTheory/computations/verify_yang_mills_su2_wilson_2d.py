#!/usr/bin/env python3
"""Verify the finite-volume two-dimensional SU(2) Wilson bridge.

The calculation uses the gauge-projected character transfer spectrum of the
periodic two-dimensional Wilson model.  It is a finite-volume benchmark for
the Schwinger-function layer; it is not a four-dimensional mass-gap proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any

import numpy as np
from scipy import __version__ as scipy_version
from scipy.special import iv

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-su2-wilson-2d-prereg.md"
SOURCE = Path(__file__).resolve()
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_su2_wilson_2d" / "verification.json"

BETA_VALUES = (1.0, 2.0, 4.0)
SPATIAL_LENGTHS = (1, 2, 4)
TEMPORAL_LENGTHS = (1, 2, 4)
CHARACTER_CUTOFFS = (8, 16, 24, 32)
TIME_SEPARATIONS = (0, 1, 2, 4)
PRIMARY_TOLERANCE = 1.0e-11
INDEPENDENT_TOLERANCE = 1.0e-9
EXPECTED_ROWS = (
    len(BETA_VALUES)
    * len(SPATIAL_LENGTHS)
    * len(TEMPORAL_LENGTHS)
    * len(CHARACTER_CUTOFFS)
)
CHECKS_PER_ROW = 8
EXPECTED_ROW_CHECKS = EXPECTED_ROWS * CHECKS_PER_ROW
EXPECTED_TOP_LEVEL_CHECKS = 12
EXPECTED_CHECKS = EXPECTED_ROW_CHECKS + EXPECTED_TOP_LEVEL_CHECKS


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close_enough(left: float, right: float, tolerance: float = PRIMARY_TOLERANCE) -> bool:
    return abs(left - right) <= tolerance * max(1.0, abs(left), abs(right))


def check(name: str, passed: bool, **detail: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **detail}


def character_data(beta: float, n_max: int) -> tuple[np.ndarray, np.ndarray]:
    indices = np.arange(1, n_max + 1, dtype=float)
    coefficients = 2.0 * iv(indices, beta) / beta
    transfer = coefficients / indices
    return coefficients, transfer


def q_bound_log(beta: float, n: int) -> float:
    return (
        math.log(2.0)
        + beta * beta / 4.0
        - math.log(beta * n)
        + n * math.log(beta / 2.0)
        - math.lgamma(n + 1.0)
    )


def q_bound(beta: float, n: int) -> float:
    return math.exp(q_bound_log(beta, n))


def tail_bound(
    beta: float, n_max: int, area: int
) -> tuple[float, float, float, float, float]:
    first_omitted = q_bound(beta, n_max + 1)
    rho = beta * (n_max + 1) / (2.0 * (n_max + 2) ** 2)
    log_first_power = area * q_bound_log(beta, n_max + 1)
    log_bound = log_first_power - math.log1p(-(rho**area))
    bound = math.exp(log_bound) if log_bound >= math.log(np.finfo(float).tiny) else 0.0
    return first_omitted, rho, bound, math.exp(log_first_power) if log_first_power >= math.log(np.finfo(float).tiny) else 0.0, log_bound


def row(beta: float, spatial_length: int, temporal_length: int, n_max: int) -> dict[str, Any]:
    area = spatial_length * temporal_length
    indices = np.arange(1, n_max + 1, dtype=int)
    coefficients, transfer = character_data(beta, n_max)
    transfer_from_formula = 2.0 * iv(indices.astype(float), beta) / (beta * indices)
    ratio = float(transfer[1] / transfer[0])
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
    tail_transfer = 2.0 * iv(tail_indices, beta) / (beta * tail_indices)
    tail_probe = float(np.sum(tail_transfer**area))
    partition = float(np.sum(transfer**area))
    omitted_log_relative_bound = omitted_log_bound - math.log(partition)
    expected_effective_mass = spatial_length * math.log(float(transfer[0] / transfer[1]))
    correlator_error = max(
        abs(item["correlator"] - ratio ** (spatial_length * item["t"]))
        for item in correlators
    )
    effective_error = max(
        abs(item["effective_mass"] - expected_effective_mass)
        for item in correlators
    )
    checks = [
        check(
            "positive_bessel_coefficients",
            bool(np.all(coefficients > 0.0)),
            minimum=float(np.min(coefficients)),
        ),
        check(
            "strict_transfer_decrease",
            bool(np.all(transfer[:-1] > transfer[1:])),
            minimum_difference=float(np.min(transfer[:-1] - transfer[1:])),
        ),
        check(
            "transfer_eigenvalue_formula",
            bool(np.max(np.abs(transfer - transfer_from_formula)) <= PRIMARY_TOLERANCE),
            maximum_error=float(np.max(np.abs(transfer - transfer_from_formula))),
        ),
        check(
            "character_fusion_correlator",
            bool(correlator_error <= PRIMARY_TOLERANCE),
            maximum_error=correlator_error,
        ),
        check(
            "effective_mass_identity",
            bool(effective_error <= PRIMARY_TOLERANCE),
            maximum_error=effective_error,
            expected=expected_effective_mass,
        ),
        check(
            "positive_character_tail_bound",
            bool(
                math.isfinite(omitted_bound)
                and math.isfinite(omitted_log_bound)
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
            bool(area == spatial_length * temporal_length),
            area=area,
        ),
    ]
    return {
        "beta": beta,
        "spatial_length": spatial_length,
        "temporal_length": temporal_length,
        "area": area,
        "character_cutoff": n_max,
        "character_indices": indices.tolist(),
        "character_coefficients": coefficients.tolist(),
        "transfer_eigenvalues": transfer.tolist(),
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


def run(output: Path) -> dict[str, Any]:
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
        check("protocol_path", str(PROTOCOL.relative_to(ROOT)).replace("\\", "/") == "computations/yang-mills-su2-wilson-2d-prereg.md"),
        check("protocol_hash_available", bool(sha256(PROTOCOL))),
        check("source_path", str(SOURCE.relative_to(ROOT)).replace("\\", "/") == "computations/verify_yang_mills_su2_wilson_2d.py"),
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
        "schema": "cassi.yang-mills.su2-wilson-2d.v1",
        "verdict": "PASS" if passed else "FAIL",
        "classification": "FINITE_VOLUME_2D_WILSON_SCHWINGER_BRIDGE",
        "scope": (
            "Gauge-projected finite-volume two-dimensional SU(2) Wilson transfer spectrum, "
            "fundamental-character correlator and certified character tail; four-dimensional "
            "volume growth, continuum construction and physical mass gap are outside this receipt."
        ),
        "protocol": str(PROTOCOL.relative_to(ROOT)).replace("\\", "/"),
        "protocol_sha256": sha256(PROTOCOL),
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256(SOURCE),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy_version,
        "schedule": {
            "beta_values": list(BETA_VALUES),
            "spatial_lengths": list(SPATIAL_LENGTHS),
            "temporal_lengths": list(TEMPORAL_LENGTHS),
            "character_cutoffs": list(CHARACTER_CUTOFFS),
            "time_separations": list(TIME_SEPARATIONS),
        },
        "tolerances": {
            "primary": PRIMARY_TOLERANCE,
            "independent": INDEPENDENT_TOLERANCE,
        },
        "summary": {
            "rows": len(rows),
            "checks": len(all_checks),
            "passed": sum(bool(item["passed"]) for item in all_checks),
            "failed": sum(not bool(item["passed"]) for item in all_checks),
            "row_checks": len(row_checks),
            "top_level_checks": len(top_checks),
        },
        "checks": top_checks,
        "rows": rows,
        "uniformity_and_scope": [
            "The character expansion is gauge projected by normalized SU(2) Haar integration.",
            "The correlator is an exact finite-volume transfer identity for the declared observable.",
            "The tail receipt bounds the two-dimensional character expansion at each scheduled area.",
            "No four-dimensional spatial-volume, thermodynamic, OS, or physical mass-gap claim is inferred.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output = output.resolve()
    if output.exists() and not args.force:
        parser.error(f"refusing to overwrite existing receipt: {output}")
    record = run(output)
    print(
        f"{record['verdict']}: {record['summary']['passed']}/"
        f"{record['summary']['checks']} checks, {record['summary']['rows']} rows"
    )
    return 0 if record["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
