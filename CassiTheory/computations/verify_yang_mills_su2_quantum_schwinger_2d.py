#!/usr/bin/env python3
"""Verify a finite-volume SU(2) quantum Schwinger-function generator.

The model is the finite character transfer matrix declared in
``yang-mills-su2-quantum-schwinger-2d-prereg-v1.md``.  It is deliberately
separate from the larger-volume Hamiltonian target.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.special import iv

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-su2-quantum-schwinger-2d-prereg-v1.md"
SOURCE = Path(__file__).resolve()
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_su2_quantum_schwinger_2d" / "verification-v1.json"

BETA_VALUES = (1.0, 2.0, 4.0)
SPATIAL_LENGTHS = (1, 2, 4)
CHARACTER_CUTOFFS = (8, 16, 24, 32)
CHANNELS = (1, 2, 3)
TIMES = (0.0, 0.5, 1.0, 2.0, 4.0)
DELTA_T = 0.5
PRIMARY_TOLERANCE = 1.0e-11
EXPECTED_ROWS = len(BETA_VALUES) * len(SPATIAL_LENGTHS) * len(CHARACTER_CUTOFFS)
CHECKS_PER_ROW = 11
EXPECTED_ROW_CHECKS = EXPECTED_ROWS * CHECKS_PER_ROW
EXPECTED_TOP_LEVEL_CHECKS = 6
EXPECTED_CHECKS = EXPECTED_ROW_CHECKS + EXPECTED_TOP_LEVEL_CHECKS


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close_enough(left: float, right: float, tolerance: float = PRIMARY_TOLERANCE) -> bool:
    return bool(abs(left - right) <= tolerance * max(1.0, abs(left), abs(right)))


def check(name: str, passed: bool, **detail: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **detail}


def character_data(beta: float, cutoff: int) -> tuple[np.ndarray, np.ndarray]:
    indices = np.arange(1, cutoff + 1, dtype=float)
    coefficients = 2.0 * iv(indices, beta) / beta
    ratios = coefficients / indices
    return coefficients, ratios


def fusion_matrix(channel: int, cutoff: int) -> np.ndarray:
    """Return multiplication by chi_(channel/2) in the retained basis.

    Basis index n is the representation dimension n=2j+1.  The doubled
    spin of that basis vector is n-1, so the output dimension m satisfies
    m-1 in {|channel-(n-1)|, ..., channel+n-1} with step two.
    """

    matrix = np.zeros((cutoff, cutoff), dtype=float)
    for n in range(1, cutoff + 1):
        first = abs(channel - (n - 1))
        last = channel + n - 1
        for doubled_spin in range(first, last + 1, 2):
            m = doubled_spin + 1
            if 1 <= m <= cutoff:
                matrix[m - 1, n - 1] = 1.0
    return matrix


def finite_payload(value: Any) -> bool:
    if isinstance(value, dict):
        return all(finite_payload(item) for item in value.values())
    if isinstance(value, list):
        return all(finite_payload(item) for item in value)
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        return math.isfinite(float(value))
    return True


def schwinger_row(beta: float, spatial_length: int, cutoff: int) -> dict[str, Any]:
    coefficients, ratios = character_data(beta, cutoff)
    transfer = ratios**spatial_length
    transfer_matrix = np.diag(transfer)
    energies = spatial_length * np.log(ratios[0] / ratios)
    transfer_symmetry_residual = float(np.max(np.abs(transfer_matrix - transfer_matrix.T)))
    transfer_symmetric = transfer_symmetry_residual <= PRIMARY_TOLERANCE
    channels: dict[str, Any] = {}
    row_checks: list[dict[str, Any]] = []

    coefficient_positive = bool(np.all(np.isfinite(coefficients)) and np.all(coefficients > 0.0))
    transfer_positive = bool(np.all(np.isfinite(transfer)) and np.all(transfer > 0.0))
    row_checks.append(
        check(
            "positive_finite_coefficients_and_transfer",
            coefficient_positive and transfer_positive,
            minimum_coefficient=float(np.min(coefficients)),
            minimum_transfer=float(np.min(transfer)),
        )
    )
    row_checks.append(
        check(
            "symmetric_transfer_matrix",
            transfer_symmetric,
            symmetry_residual=transfer_symmetry_residual,
        )
    )

    monotone = bool(np.all(ratios[:-1] > ratios[1:]))
    row_checks.append(
        check(
            "strict_transfer_order",
            monotone,
            minimum_ratio_drop=float(np.min(ratios[:-1] - ratios[1:])),
        )
    )

    energies_ok = bool(
        close_enough(float(energies[0]), 0.0)
        and np.all(np.isfinite(energies))
        and np.all(energies[1:] > 0.0)
    )
    row_checks.append(
        check(
            "normalized_ground_and_positive_gaps",
            energies_ok,
            ground_energy=float(energies[0]),
            minimum_gap=float(np.min(energies[1:])),
        )
    )

    all_observables_symmetric = True
    all_vacuum_orbits = True
    all_correlators_nonnegative = True
    all_effective_masses = True
    all_semigroup = True
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
        shifted_correlators = [math.exp(-(time + DELTA_T) * spectral_energy) for time in TIMES]
        effective_masses = [
            -(1.0 / DELTA_T) * math.log(shifted / value)
            for value, shifted in zip(correlators, shifted_correlators)
        ]
        semigroup_error = max(
            abs(shifted - value * math.exp(-DELTA_T * spectral_energy))
            for value, shifted in zip(correlators, shifted_correlators)
        )
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
            "semigroup_error": float(semigroup_error),
        }
        all_observables_symmetric &= symmetry_residual <= PRIMARY_TOLERANCE
        all_vacuum_orbits &= vacuum_error <= PRIMARY_TOLERANCE
        all_correlators_nonnegative &= all(value >= 0.0 and math.isfinite(value) for value in correlators)
        all_effective_masses &= all(
            close_enough(value, spectral_energy) for value in effective_masses
        )
        all_semigroup &= semigroup_error <= PRIMARY_TOLERANCE
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
            maximum_vacuum_orbit_error=max(value["vacuum_orbit_error"] for value in channels.values()),
        )
    )
    row_checks.append(
        check(
            "nonnegative_connected_correlators",
            all_correlators_nonnegative,
            minimum_correlator=min(min(value["correlators"]) for value in channels.values()),
        )
    )
    row_checks.append(
        check(
            "effective_mass_identity",
            all_effective_masses,
            maximum_effective_mass_error=max(
                max(abs(value - channel_value["spectral_energy"]) for value in channel_value["effective_masses"])
                for channel_value in channels.values()
            ),
        )
    )
    row_checks.append(
        check(
            "semigroup_identity",
            all_semigroup,
            maximum_semigroup_error=max(value["semigroup_error"] for value in channels.values()),
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

    row = {
        "beta": float(beta),
        "spatial_length": int(spatial_length),
        "character_cutoff": int(cutoff),
        "coefficient_values": coefficients.tolist(),
        "ratio_values": ratios.tolist(),
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


def run(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        schwinger_row(beta, spatial_length, cutoff)
        for beta in BETA_VALUES
        for spatial_length in SPATIAL_LENGTHS
        for cutoff in CHARACTER_CUTOFFS
    ]
    checks = [
        check("protocol_source_exists", PROTOCOL.exists() and SOURCE.exists()),
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
    ]
    record: dict[str, Any] = {
        "schema": "cassi.yang-mills.su2.quantum-schwinger-2d.v1",
        "verdict": "PASS" if all(item["passed"] for item in checks) else "FAIL",
        "classification": "FINITE_VOLUME_2D_QUANTUM_SCHWINGER_GENERATOR",
        "scope": "Finite two-dimensional SU(2) Wilson transfer model only; no cutoff, thermodynamic, OS, or continuum claim.",
        "protocol": str(PROTOCOL.relative_to(ROOT)).replace("\\", "/"),
        "protocol_sha256": sha256(PROTOCOL),
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256(SOURCE),
        "schedule": {
            "beta_values": list(BETA_VALUES),
            "spatial_lengths": list(SPATIAL_LENGTHS),
            "character_cutoffs": list(CHARACTER_CUTOFFS),
            "channels": list(CHANNELS),
            "times": list(TIMES),
            "delta_t": DELTA_T,
        },
        "tolerances": {"primary": PRIMARY_TOLERANCE},
        "summary": {
            "rows": len(rows),
            "row_checks": sum(len(row["checks"]) for row in rows),
            "top_level_checks": len(checks),
            "checks": sum(len(row["checks"]) for row in rows) + len(checks),
            "passed": sum(item["passed"] for item in checks)
            + sum(item["passed"] for row in rows for item in row["checks"]),
            "failed": sum(not item["passed"] for item in checks)
            + sum(not item["passed"] for row in rows for item in row["checks"]),
        },
        "checks": checks,
        "rows": rows,
        "uniformity_and_scope": [
            "The transfer matrix, fusion channels, and correlators are finite exact-model quantities.",
            "The character-cutoff and spatial-length schedules are diagnostics only.",
            "No larger-volume Hamiltonian receipt is read or written by this study.",
            "No thermodynamic, Osterwalder-Schrader, continuum, or physical mass-gap estimate is inferred.",
        ],
    }
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    record = run(args.output)
    print(json.dumps(record["summary"], sort_keys=True))
    return 0 if record["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
