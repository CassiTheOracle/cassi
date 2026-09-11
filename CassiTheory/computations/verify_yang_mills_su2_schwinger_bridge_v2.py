#!/usr/bin/env python3
"""Verify the finite-regulator SU(2) Schwinger-function bridge.

The model is the class-function one-plaquette Hamiltonian in a finite
character basis.  The ground state is obtained from the declared finite
Hamiltonian itself; no projected full-group Ritz density is used.

The receipt is finite-regulator evidence.  It deliberately makes no claim
about character-cutoff removal, spatial volume growth, or the continuum.
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

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-su2-schwinger-prereg-v2.md"
SOURCE = Path(__file__).resolve()
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_su2_schwinger_bridge" / "verification-v2.json"

DOUBLED_CUTOFFS = (8, 16, 24, 32)
G2_VALUES = (0.5, 1.0, 2.0)
TIMES = (0.0, 0.5, 1.0, 2.0)
DELTA_T = 0.5
PRIMARY_TOLERANCE = 1.0e-11
INDEPENDENT_TOLERANCE = 1.0e-9
EXPECTED_ROWS = len(DOUBLED_CUTOFFS) * len(G2_VALUES)
EXPECTED_CHECKS = EXPECTED_ROWS * 8


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite_hamiltonian(n_max: int, g2: float) -> tuple[np.ndarray, np.ndarray]:
    """Return H and the projected fundamental-character observable."""
    if n_max < 1 or n_max % 2:
        raise ValueError("n_max must be a positive even doubled-spin cutoff")
    if not math.isfinite(g2) or g2 <= 0.0:
        raise ValueError("g2 must be finite and positive")

    n = np.arange(n_max + 1, dtype=float)
    j = 0.5 * n
    h = np.diag(0.5 * g2 * j * (j + 1.0) + 2.0 / g2)
    observable = np.zeros_like(h)
    for index in range(n_max):
        observable[index, index + 1] = 1.0
        observable[index + 1, index] = 1.0
    h -= observable / g2
    return h, observable


def ground_and_spectrum(h: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    values, vectors = np.linalg.eigh(h)
    ground = np.asarray(vectors[:, 0], dtype=float)
    if float(np.sum(ground)) < 0.0:
        ground = -ground
    residual = float(np.linalg.norm(h @ ground - values[0] * ground, ord=2))
    return values, ground, residual


def schwinger_row(n_max: int, g2: float) -> dict[str, Any]:
    h, observable = finite_hamiltonian(n_max, g2)
    values, ground, ground_residual = ground_and_spectrum(h)
    transformed = observable @ ground
    # Reconstruct the spectral basis used for the correlator.
    values, vectors = np.linalg.eigh(h)
    if float(np.dot(vectors[:, 0], ground)) < 0.0:
        vectors[:, 0] *= -1.0
    amplitudes = vectors.T @ transformed
    gaps = values - values[0]
    mean = float(amplitudes[0])
    operator_norm = float(np.max(np.abs(np.linalg.eigvalsh(observable))))

    def correlator(time: float) -> float:
        return float(np.sum((amplitudes[1:] ** 2) * np.exp(-gaps[1:] * time)))

    times = []
    for time in TIMES:
        c0 = correlator(time)
        c1 = correlator(time + DELTA_T)
        effective = -math.log(c1 / c0) / DELTA_T if c0 > 0.0 and c1 > 0.0 else math.nan
        times.append(
            {
                "t": time,
                "correlator": c0,
                "next_correlator": c1,
                "effective_mass": effective,
            }
        )

    spectral_gap = float(values[1] - values[0])
    sign_scale = max(1.0, float(np.max(np.sum(np.abs(h), axis=1))))
    sign_tolerance = 256.0 * np.finfo(float).eps * (n_max + 1) * sign_scale
    checks = [
        {
            "name": "hamiltonian_symmetric",
            "passed": bool(np.max(np.abs(h - h.T)) <= PRIMARY_TOLERANCE),
            "value": float(np.max(np.abs(h - h.T))),
        },
        {
            "name": "observable_symmetric",
            "passed": bool(np.max(np.abs(observable - observable.T)) <= PRIMARY_TOLERANCE),
            "value": float(np.max(np.abs(observable - observable.T))),
        },
        {
            "name": "ground_state_residual",
            "passed": bool(ground_residual <= PRIMARY_TOLERANCE),
            "value": ground_residual,
        },
        {
            "name": "perron_ground_sign_certificate",
            "passed": bool(float(ground[0]) > 0.0 and float(np.min(ground)) >= -sign_tolerance),
            "value": float(np.min(ground)),
            "tolerance": sign_tolerance,
        },
        {
            "name": "positive_first_gap",
            "passed": bool(spectral_gap > 0.0),
            "value": spectral_gap,
        },
        {
            "name": "connected_correlator_nonnegative",
            "passed": bool(all(row["correlator"] >= -PRIMARY_TOLERANCE for row in times)),
            "value": float(min(row["correlator"] for row in times)),
        },
        {
            "name": "effective_mass_above_spectral_gap",
            "passed": bool(
                all(
                    row["effective_mass"] + PRIMARY_TOLERANCE >= spectral_gap
                    for row in times
                )
            ),
            "value": float(min(row["effective_mass"] for row in times)),
        },
        {
            "name": "operator_bound_on_C0",
            "passed": bool(times[0]["correlator"] <= 4.0 + PRIMARY_TOLERANCE),
            "value": times[0]["correlator"],
        },
    ]

    return {
        "n_max": n_max,
        "j_max": n_max / 2.0,
        "g2": g2,
        "dimension": n_max + 1,
        "ground_energy": float(values[0]),
        "first_excited_energy": float(values[1]),
        "spectral_gap": spectral_gap,
        "ground_residual": ground_residual,
        "min_ground_coefficient": float(np.min(ground)),
        "ground_coefficients": ground.tolist(),
        "operator_norm": operator_norm,
        "vacuum_one_point": mean,
        "times": times,
        "checks": checks,
    }


def run(output: Path) -> dict[str, Any]:
    rows = [schwinger_row(n_max, g2) for n_max in DOUBLED_CUTOFFS for g2 in G2_VALUES]
    checks = [check for row in rows for check in row["checks"]]
    passed = all(bool(check["passed"]) for check in checks)
    record: dict[str, Any] = {
        "schema": "cassi.yang-mills.su2-schwinger-bridge.v2",
        "verdict": "PASS" if passed else "FAIL",
        "classification": "FINITE_REGULATOR_SCHWINGER_BRIDGE",
        "scope": (
            "Exact vacuum correlators of the declared one-plaquette finite character-cutoff "
            "Hamiltonian; cutoff and continuum limits are outside this receipt."
        ),
        "protocol": str(PROTOCOL.relative_to(ROOT)).replace("\\", "/"),
        "protocol_sha256": sha256(PROTOCOL),
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256(SOURCE),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "schedule": {
            "doubled_cutoffs": list(DOUBLED_CUTOFFS),
            "g2_values": list(G2_VALUES),
            "times": list(TIMES),
            "delta_t": DELTA_T,
        },
        "tolerances": {
            "primary": PRIMARY_TOLERANCE,
            "independent": INDEPENDENT_TOLERANCE,
        },
        "summary": {
            "rows": len(rows),
            "checks": len(checks),
            "passed": sum(bool(check["passed"]) for check in checks),
            "failed": sum(not bool(check["passed"]) for check in checks),
        },
        "rows": rows,
        "uniformity_and_scope": [
            "The receipt constructs the true ground state of each declared finite matrix.",
            "The character-cutoff drift is a numerical diagnostic, not a truncation theorem.",
            "No spatial-volume sequence, thermodynamic limit, or continuum mass gap is evaluated.",
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
