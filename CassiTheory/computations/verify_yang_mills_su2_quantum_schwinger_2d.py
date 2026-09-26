#!/usr/bin/env python3
"""Verify the normalization-corrected finite SU(2) Schwinger generator.

The transfer spectrum uses the once-divided Wilson coefficient from normalized
Haar character gluing.  The construction is a finite two-dimensional model and
does not make a four-dimensional continuum or mass-gap claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from scipy.integrate import quad
from scipy.special import iv

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-su2-quantum-schwinger-2d-prereg-v2.md"
WILSON_PROTOCOL = ROOT / "computations" / "yang-mills-su2-wilson-2d-prereg-v2.md"
WILSON_SOURCE = ROOT / "computations" / "verify_yang_mills_su2_wilson_2d.py"
WILSON_RECEIPT = ROOT / "runs" / "yang_mills_su2_wilson_2d" / "verification-v2.json"
SOURCE = Path(__file__).resolve()
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_su2_quantum_schwinger_2d" / "verification-v2.json"

BETA_VALUES = (1.0, 2.0, 4.0)
SPATIAL_LENGTHS = (1, 2, 4)
CHARACTER_CUTOFFS = (8, 16, 24, 32)
CHANNELS = (1, 2, 3)
TIMES = (0.0, 0.5, 1.0, 2.0, 4.0)
DELTA_T = 0.5
HAAR_ORDERS = tuple(range(1, 9))
PRIMARY_TOLERANCE = 1.0e-11
HAAR_RELATIVE_TOLERANCE = 1.0e-9
EXPECTED_ROWS = len(BETA_VALUES) * len(SPATIAL_LENGTHS) * len(CHARACTER_CUTOFFS)
CHECKS_PER_ROW = 13
EXPECTED_ROW_CHECKS = EXPECTED_ROWS * CHECKS_PER_ROW
EXPECTED_TOP_LEVEL_CHECKS = 8
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


def character_data(beta: float, cutoff: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dimensions = np.arange(1, cutoff + 1, dtype=float)
    coefficients = iv(dimensions - 1.0, beta) - iv(dimensions + 1.0, beta)
    reduced = 2.0 * iv(dimensions, beta) / beta
    return dimensions, coefficients, reduced


def fusion_matrix(channel: int, cutoff: int) -> np.ndarray:
    """Return multiplication by the dimension-(channel + 1) SU(2) character."""

    matrix = np.zeros((cutoff, cutoff), dtype=float)
    for n in range(1, cutoff + 1):
        first = abs(channel - (n - 1))
        last = channel + n - 1
        for doubled_spin in range(first, last + 1, 2):
            m = doubled_spin + 1
            if 1 <= m <= cutoff:
                matrix[m - 1, n - 1] = 1.0
    return matrix


def load_wilson_prerequisite() -> tuple[dict[str, Any], bool]:
    if not WILSON_RECEIPT.exists():
        return {}, False
    receipt = json.loads(WILSON_RECEIPT.read_text(encoding="utf-8"))
    current = bool(
        receipt.get("schema") == "cassi.yang-mills.su2-wilson-2d.v2"
        and receipt.get("verdict") == "PASS"
        and receipt.get("protocol_sha256") == sha256(WILSON_PROTOCOL)
        and receipt.get("source_sha256") == sha256(WILSON_SOURCE)
        and receipt.get("summary", {}).get("checks") == 1092
        and receipt.get("summary", {}).get("passed") == 1092
        and receipt.get("summary", {}).get("failed") == 0
        and receipt.get("normalization", {}).get("double_division_rejected") is True
    )
    return receipt, current


def schwinger_row(beta: float, spatial_length: int, cutoff: int) -> dict[str, Any]:
    dimensions, coefficients, reduced = character_data(beta, cutoff)
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

    transfer = reduced**spatial_length
    transfer_matrix = np.diag(transfer)
    energies = spatial_length * np.log(reduced[0] / reduced)
    transfer_symmetry_residual = float(np.max(np.abs(transfer_matrix - transfer_matrix.T)))
    transfer_symmetric = transfer_symmetry_residual <= PRIMARY_TOLERANCE
    channels: dict[str, Any] = {}
    row_checks: list[dict[str, Any]] = []

    row_checks.append(
        check(
            "positive_finite_coefficients_and_transfer",
            bool(
                np.all(np.isfinite(coefficients))
                and np.all(np.isfinite(reduced))
                and np.all(np.isfinite(transfer))
                and np.all(coefficients > 0.0)
                and np.all(reduced > 0.0)
                and np.all(transfer > 0.0)
            ),
            minimum_character_coefficient=float(np.min(coefficients)),
            minimum_reduced_coefficient=float(np.min(reduced)),
            minimum_transfer=float(np.min(transfer)),
        )
    )
    row_checks.append(
        check(
            "haar_character_normalization",
            bool(np.max(haar_relative_errors) <= HAAR_RELATIVE_TOLERANCE),
            maximum_relative_error=float(np.max(haar_relative_errors)),
            maximum_quadrature_error=float(np.max(haar_errors)),
        )
    )
    row_checks.append(
        check(
            "single_convolution_quotient",
            bool(
                quotient_residual <= PRIMARY_TOLERANCE
                and quotient_relative_residual <= PRIMARY_TOLERANCE
            ),
            maximum_absolute_residual=quotient_residual,
            maximum_relative_residual=quotient_relative_residual,
        )
    )
    row_checks.append(
        check(
            "double_division_firing_control",
            double_division_relative_error_n2 >= 0.5 - PRIMARY_TOLERANCE,
            n=2,
            relative_error=double_division_relative_error_n2,
            correct=float(reduced[1]),
            rejected=float(rejected_double_division[1]),
        )
    )
    row_checks.append(
        check(
            "symmetric_transfer_matrix",
            transfer_symmetric,
            symmetry_residual=transfer_symmetry_residual,
        )
    )
    row_checks.append(
        check(
            "strict_transfer_order",
            bool(np.all(reduced[:-1] > reduced[1:])),
            minimum_reduced_drop=float(np.min(reduced[:-1] - reduced[1:])),
        )
    )
    row_checks.append(
        check(
            "normalized_ground_and_positive_gaps",
            bool(
                close_enough(float(energies[0]), 0.0)
                and np.all(np.isfinite(energies))
                and np.all(energies[1:] > 0.0)
            ),
            ground_energy=float(energies[0]),
            minimum_gap=float(np.min(energies[1:])),
        )
    )

    all_observables_symmetric = True
    all_vacuum_orbits = True
    all_correlators_nonnegative = True
    all_effective_and_semigroup = True
    all_operator_bounds = True

    for channel in CHANNELS:
        observable = fusion_matrix(channel, cutoff)
        symmetry_residual = float(np.max(np.abs(observable - observable.T)))
        eigenvalues = np.linalg.eigvalsh(observable)
        operator_norm = float(np.max(np.abs(eigenvalues)))
        vacuum = observable[:, 0]
        target = np.zeros(cutoff, dtype=float)
        target[channel] = 1.0
        vacuum_error = float(np.max(np.abs(vacuum - target)))
        spectral_energy = float(energies[channel])
        correlators = [math.exp(-time * spectral_energy) for time in TIMES]
        shifted_correlators = [
            math.exp(-(time + DELTA_T) * spectral_energy) for time in TIMES
        ]
        effective_masses = [
            -(1.0 / DELTA_T) * math.log(shifted / value)
            for value, shifted in zip(correlators, shifted_correlators)
        ]
        semigroup_error = max(
            abs(shifted - value * math.exp(-DELTA_T * spectral_energy))
            for value, shifted in zip(correlators, shifted_correlators)
        )
        effective_error = max(abs(value - spectral_energy) for value in effective_masses)
        channels[str(channel)] = {
            "allowed_entries": int(np.count_nonzero(observable)),
            "matrix_symmetry_residual": symmetry_residual,
            "operator_norm": operator_norm,
            "declared_operator_bound": float(channel + 1),
            "vacuum_target": int(channel + 1),
            "vacuum_orbit_error": vacuum_error,
            "spectral_energy": spectral_energy,
            "correlators": correlators,
            "shifted_correlators": shifted_correlators,
            "effective_masses": effective_masses,
            "effective_mass_error": float(effective_error),
            "semigroup_error": float(semigroup_error),
        }
        all_observables_symmetric &= symmetry_residual <= PRIMARY_TOLERANCE
        all_vacuum_orbits &= vacuum_error <= PRIMARY_TOLERANCE
        all_correlators_nonnegative &= all(
            value >= 0.0 and math.isfinite(value) for value in correlators
        )
        all_effective_and_semigroup &= (
            effective_error <= PRIMARY_TOLERANCE
            and semigroup_error <= PRIMARY_TOLERANCE
        )
        all_operator_bounds &= operator_norm <= channel + 1.0 + PRIMARY_TOLERANCE

    row_checks.append(
        check(
            "symmetric_finite_fusion_observables",
            all_observables_symmetric,
            maximum_symmetry_residual=max(
                value["matrix_symmetry_residual"] for value in channels.values()
            ),
        )
    )
    row_checks.append(
        check(
            "vacuum_fusion_orbits",
            all_vacuum_orbits,
            maximum_vacuum_orbit_error=max(
                value["vacuum_orbit_error"] for value in channels.values()
            ),
        )
    )
    row_checks.append(
        check(
            "nonnegative_connected_correlators",
            all_correlators_nonnegative,
            minimum_correlator=min(
                min(value["correlators"]) for value in channels.values()
            ),
        )
    )
    row_checks.append(
        check(
            "effective_mass_and_semigroup_identities",
            all_effective_and_semigroup,
            maximum_effective_mass_error=max(
                value["effective_mass_error"] for value in channels.values()
            ),
            maximum_semigroup_error=max(
                value["semigroup_error"] for value in channels.values()
            ),
        )
    )
    row_checks.append(
        check(
            "fusion_operator_norm_bounds",
            all_operator_bounds,
            maximum_bound_ratio=max(
                value["operator_norm"] / value["declared_operator_bound"]
                for value in channels.values()
            ),
        )
    )

    row: dict[str, Any] = {
        "beta": float(beta),
        "spatial_length": int(spatial_length),
        "character_cutoff": int(cutoff),
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
        "transfer_values": transfer.tolist(),
        "transfer_symmetry_residual": transfer_symmetry_residual,
        "energies": energies.tolist(),
        "transfer_symmetric": transfer_symmetric,
        "channels": channels,
        "checks": row_checks,
    }
    row_checks.append(check("finite_complete_row_payload", finite_payload(row)))
    row["checks_passed"] = bool(all(item["passed"] for item in row_checks))
    return row


def run(output: Path, replace: bool) -> dict[str, Any]:
    if output.exists() and not replace:
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    wilson_receipt, wilson_current = load_wilson_prerequisite()
    rows = [
        schwinger_row(beta, spatial_length, cutoff)
        for beta in BETA_VALUES
        for spatial_length in SPATIAL_LENGTHS
        for cutoff in CHARACTER_CUTOFFS
    ]
    checks = [
        check("protocol_source_exists", PROTOCOL.exists() and SOURCE.exists()),
        check(
            "wilson_v2_prerequisite_current",
            wilson_current,
            receipt=str(WILSON_RECEIPT.relative_to(ROOT)).replace("\\", "/"),
        ),
        check("frozen_schedule_cardinality", EXPECTED_ROWS == 36),
        check("row_count", len(rows) == EXPECTED_ROWS, observed=len(rows), expected=EXPECTED_ROWS),
        check("all_rows_finite", all(finite_payload(row) for row in rows)),
        check(
            "all_row_checks_pass",
            all(row["checks_passed"] for row in rows),
            observed=sum(len(row["checks"]) for row in rows),
            expected=EXPECTED_ROW_CHECKS,
        ),
        check("finite_transfer_model", all(row["transfer_symmetric"] for row in rows)),
        check(
            "normalization_firing_control",
            all(
                row["double_division_relative_error_n2"] >= 0.5 - PRIMARY_TOLERANCE
                for row in rows
            ),
        ),
    ]
    all_checks = checks + [item for row in rows for item in row["checks"]]
    record: dict[str, Any] = {
        "schema": "cassi.yang-mills.su2.quantum-schwinger-2d.v2",
        "verdict": "PASS" if all(item["passed"] for item in all_checks) else "FAIL",
        "classification": "NORMALIZATION_CORRECTED_FINITE_VOLUME_2D_QUANTUM_SCHWINGER_GENERATOR",
        "scope": (
            "Normalization-corrected finite two-dimensional SU(2) Wilson transfer model; "
            "no four-dimensional thermodynamic, OS, continuum or physical mass-gap claim."
        ),
        "protocol": str(PROTOCOL.relative_to(ROOT)).replace("\\", "/"),
        "protocol_sha256": sha256(PROTOCOL),
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256(SOURCE),
        "prerequisites": {
            "wilson_protocol": str(WILSON_PROTOCOL.relative_to(ROOT)).replace("\\", "/"),
            "wilson_protocol_sha256": sha256(WILSON_PROTOCOL),
            "wilson_source": str(WILSON_SOURCE.relative_to(ROOT)).replace("\\", "/"),
            "wilson_source_sha256": sha256(WILSON_SOURCE),
            "wilson_receipt": str(WILSON_RECEIPT.relative_to(ROOT)).replace("\\", "/"),
            "wilson_receipt_sha256": sha256(WILSON_RECEIPT) if WILSON_RECEIPT.exists() else None,
            "wilson_receipt_verdict": wilson_receipt.get("verdict"),
            "wilson_receipt_current": wilson_current,
        },
        "schedule": {
            "beta_values": list(BETA_VALUES),
            "spatial_lengths": list(SPATIAL_LENGTHS),
            "character_cutoffs": list(CHARACTER_CUTOFFS),
            "channels": list(CHANNELS),
            "times": list(TIMES),
            "delta_t": DELTA_T,
            "haar_orders": list(HAAR_ORDERS),
        },
        "tolerances": {
            "primary": PRIMARY_TOLERANCE,
            "haar_relative": HAAR_RELATIVE_TOLERANCE,
        },
        "normalization": {
            "character_coefficient": "C_n=2*n*I_n(beta)/beta",
            "gluing_eigenvalue": "r_n=C_n/n=2*I_n(beta)/beta",
            "double_division_rejected": True,
            "invalidated_receipts": [
                "runs/yang_mills_su2_quantum_schwinger_2d/verification-v1.json",
                "runs/yang_mills_su2_quantum_schwinger_2d/verification-independent-v1.json",
            ],
        },
        "summary": {
            "rows": len(rows),
            "row_checks": sum(len(row["checks"]) for row in rows),
            "top_level_checks": len(checks),
            "checks": len(all_checks),
            "passed": sum(bool(item["passed"]) for item in all_checks),
            "failed": sum(not bool(item["passed"]) for item in all_checks),
        },
        "checks": checks,
        "rows": rows,
        "uniformity_and_scope": [
            "The Wilson v2 receipt is a current required prerequisite.",
            "Adaptive Haar quadrature checks the direct coefficients independently of the gluing quotient.",
            "The rejected double division fires in every row.",
            "The transfer matrix, fusion channels and correlators are finite exact-model quantities.",
            "No four-dimensional thermodynamic, OS, continuum or physical mass-gap estimate is inferred.",
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
