#!/usr/bin/env python3
"""Independently verify the unconstrained radial-baryon rejection.

Run from the CassiTheory repository root:
    python computations/verify_qcd_unconstrained_radial_baryon.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "qcd-unconstrained-radial-baryon-prereg.md"
PRIMARY_SOURCE = ROOT / "computations" / "qcd_unconstrained_radial_baryon.py"
UPSTREAM = (
    ROOT
    / "runs"
    / "20260910_qcd_interacting_baryon"
    / "primary"
    / "recovery3"
    / "results.json"
)
DEFAULT_INPUT = (
    ROOT
    / "runs"
    / "20260910_qcd_unconstrained_radial_baryon"
    / "recovery4"
    / "results.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "20260910_qcd_unconstrained_radial_baryon"
    / "verification"
    / "recovery4"
)

HBARC = 197.3269804
F_PI = 93.0
COUPLING = 23.0
GRID_N = 48
RMAX_FM = 10.0
DELTA_MEV = 2.0
NEAR_ZERO_COUNT = 12
SHIFT_MEV = 1.0e-9
EXPECTED_BRANCH_KIND = "positive_nodeless_state_disappeared"
EXPECTED_DECISIONS = {
    "QURB1": "PASS",
    "QURB2": "FAIL",
    "QURB3": "SKIPPED_PREREQUISITE",
    "QURB4": "SKIPPED_PREREQUISITE",
    "QURB5": "SKIPPED_PREREQUISITE",
    "QURB6": "SKIPPED_PREREQUISITE",
    "QURB7": "REJECT",
    "QURB8": "FAIL",
    "complete_physical_matter_formation": False,
    "overall": "UNCONSTRAINED_RADIAL_BARYON_REJECT",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def source_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def all_finite(value: Any) -> bool:
    if isinstance(value, dict):
        return all(all_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(all_finite(item) for item in value)
    if isinstance(value, bool) or value is None:
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    return isinstance(value, str)


def count_nodes(amplitude: np.ndarray, probability: np.ndarray) -> int:
    cumulative = np.cumsum(probability)
    cutoff = int(np.searchsorted(cumulative, 0.999, side="left"))
    cutoff = max(2, min(cutoff, amplitude.size - 1))
    peak = float(np.max(np.abs(amplitude[: cutoff + 1])))
    if peak == 0.0:
        return amplitude.size
    retained = np.abs(amplitude[: cutoff + 1]) > 1.0e-3 * peak
    signs = np.sign(amplitude[: cutoff + 1][retained])
    if signs.size < 2:
        return 0
    return int(np.count_nonzero(signs[1:] * signs[:-1] < 0.0))


def profile_from_parameters(reference_z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dr = RMAX_FM / GRID_N
    radial = (np.arange(GRID_N, dtype=np.float64) + 0.5) * dr
    amplitude, radius, chi_amplitude, chi_radius = reference_z
    denominator = radial**4 + radius**4
    scalar = 1.0 - amplitude + amplitude * (radial**4 - radius**4) / denominator
    pion = -2.0 * amplitude * radius**2 * radial**2 / denominator
    chi = chi_amplitude * np.exp(-((radial / chi_radius) ** 2))
    return scalar, pion, chi


def reconstruct_spectrum(
    scalar: np.ndarray, pion: np.ndarray, chi: np.ndarray
) -> dict[str, Any]:
    dr = RMAX_FM / GRID_N
    radial = (np.arange(GRID_N, dtype=np.float64) + 0.5) * dr
    if any(values.shape != (GRID_N,) for values in (scalar, pion, chi)):
        raise ValueError("profile arrays do not match the frozen N=48 grid")

    derivative = np.zeros((GRID_N, GRID_N), dtype=np.float64)
    derivative[0, 0] = -0.5 / dr
    derivative[0, 1] = 0.5 / dr
    indices = np.arange(1, GRID_N - 1)
    derivative[indices, indices - 1] = -0.5 / dr
    derivative[indices, indices + 1] = 0.5 / dr
    derivative[-1, -2] = -0.5 / dr

    weight_sqrt = radial * math.sqrt(dr)
    derivative_tilde = weight_sqrt[:, None] * derivative / weight_sqrt[None, :]
    wilson = 0.5 * HBARC * dr * (derivative_tilde.T @ derivative_tilde)
    mass_denominator = np.sqrt(chi * chi + DELTA_MEV * DELTA_MEV)
    scalar_mass = COUPLING * F_PI * scalar / mass_denominator
    pion_mass = COUPLING * F_PI * pion / mass_denominator
    mass = np.diag(scalar_mass) + wilson
    off_diagonal = HBARC * derivative_tilde - np.diag(pion_mass)
    hamiltonian = np.block(
        [[mass, off_diagonal.T], [off_diagonal, -mass]]
    )

    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    nearest = np.argsort(np.abs(eigenvalues - SHIFT_MEV))[:NEAR_ZERO_COUNT]
    nearest = nearest[np.argsort(eigenvalues[nearest])]
    rows: list[dict[str, Any]] = []
    candidate_count = 0
    max_residual = 0.0
    weight_inverse = 1.0 / weight_sqrt
    for index in nearest:
        energy = float(eigenvalues[index])
        vector = eigenvectors[:, index]
        probability = vector[:GRID_N] ** 2 + vector[GRID_N:] ** 2
        probability /= float(np.sum(probability))
        nodes = count_nodes(vector[:GRID_N] * weight_inverse, probability)
        residual = float(
            np.linalg.norm(hamiltonian @ vector - energy * vector)
            / max(1.0, abs(energy))
        )
        max_residual = max(max_residual, residual)
        selected = energy > 0.0 and nodes == 0
        candidate_count += int(selected)
        rows.append(
            {
                "energy_mev": energy,
                "upper_nodes": nodes,
                "positive_nodeless": selected,
                "relative_residual": residual,
            }
        )

    selected_energies = [
        row["energy_mev"] for row in rows if row["positive_nodeless"]
    ]
    return {
        "grid": {"n": GRID_N, "rmax_fm": RMAX_FM, "delta_mev": DELTA_MEV},
        "near_zero_count": NEAR_ZERO_COUNT,
        "near_zero_states": rows,
        "positive_nodeless_count": candidate_count,
        "selected_energy_mev": min(selected_energies) if selected_energies else None,
        "hamiltonian_hermiticity_max_abs": float(
            np.max(np.abs(hamiltonian - hamiltonian.T))
        ),
        "eigenpair_relative_residual_max": max_residual,
    }


def manifest_matches(receipt: dict[str, Any], key: str, path: Path) -> bool:
    record = receipt.get("source_manifest", {}).get(key, {})
    expected = source_record(path)
    return all(record.get(field) == expected[field] for field in expected)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.resolve()
    output_dir = args.output_dir.resolve()
    started = time.time()

    receipt = json.loads(input_path.read_text(encoding="utf-8"))
    reference_z = np.asarray(
        receipt.get("seeds", {}).get("reference_z"), dtype=np.float64
    )
    rows = receipt.get("primary", {}).get("rows", [])
    first_row = rows[0] if len(rows) == 1 else {}
    optimizer = first_row.get("optimizer", {})
    branch = optimizer.get("branch_event", {})
    branch_profile = branch.get("profile", {})
    reference_spectrum = reconstruct_spectrum(*profile_from_parameters(reference_z))
    branch_spectrum = reconstruct_spectrum(
        np.asarray(branch_profile.get("scalar"), dtype=np.float64),
        np.asarray(branch_profile.get("pion"), dtype=np.float64),
        np.asarray(branch_profile.get("chi_mev"), dtype=np.float64),
    )
    profile_path = input_path.parent / "profiles.npz"
    with np.load(profile_path, allow_pickle=False) as profiles:
        endpoint_spectrum = reconstruct_spectrum(
            np.asarray(profiles["primary_scalar"], dtype=np.float64),
            np.asarray(profiles["primary_pion"], dtype=np.float64),
            np.asarray(profiles["primary_chi_mev"], dtype=np.float64),
        )
    decisions = receipt.get("decisions", {})
    endpoint_energy = (
        first_row.get("endpoint", {}).get("spectrum", {}).get(
            "candidate_energy_mev"
        )
    )
    reconstructed_endpoint_energy = endpoint_spectrum["selected_energy_mev"]

    checks = {
        "VQURB1_SCHEMA": receipt.get("schema")
        == "cassi.qcd-unconstrained-radial-baryon.primary.v1",
        "VQURB2_PROTOCOL_STATUS": receipt.get("protocol_status")
        == "executed_frozen",
        "VQURB3_FINITE_RECEIPT": all_finite(receipt),
        "VQURB4_PROTOCOL_SOURCE": manifest_matches(receipt, "protocol", PROTOCOL),
        "VQURB5_PRIMARY_SOURCE": manifest_matches(
            receipt, "primary", PRIMARY_SOURCE
        ),
        "VQURB6_UPSTREAM_SOURCE": manifest_matches(receipt, "upstream", UPSTREAM),
        "VQURB7_REFERENCE_SHAPE": reference_z.shape == (4,)
        and bool(np.all(np.isfinite(reference_z))),
        "VQURB8_SINGLE_FROZEN_BRANCH_STOP": len(rows) == 1
        and first_row.get("grid")
        == {"n": GRID_N, "rmax_fm": RMAX_FM, "delta_mev": DELTA_MEV}
        and isinstance(first_row.get("endpoint"), dict)
        and optimizer.get("termination", {}).get("pass") is False
        and first_row.get("endpoint_gate", {}).get("checks", {}).get("branch")
        is False
        and first_row.get("endpoint_gate", {}).get("pass") is False,
        "VQURB9_ALGEBRAIC_GATE": receipt.get("algebraic_controls", {}).get(
            "pass"
        )
        is True,
        "VQURB10_REFERENCE_STATE_EXISTS": reference_spectrum[
            "positive_nodeless_count"
        ]
        == 1,
        "VQURB11_ENDPOINT_RECONSTRUCTION": endpoint_energy is not None
        and reconstructed_endpoint_energy is not None
        and abs(endpoint_energy - reconstructed_endpoint_energy)
        <= 1.0e-9 * max(1.0, abs(endpoint_energy)),
        "VQURB12_BRANCH_EVENT_CAPTURED": branch.get("kind")
        == EXPECTED_BRANCH_KIND
        and branch_spectrum["positive_nodeless_count"] == 0,
        "VQURB13_HERMITICITY": max(
            reference_spectrum["hamiltonian_hermiticity_max_abs"],
            endpoint_spectrum["hamiltonian_hermiticity_max_abs"],
            branch_spectrum["hamiltonian_hermiticity_max_abs"],
        )
        <= 1.0e-12,
        "VQURB14_EIGENPAIR_RESIDUAL": max(
            reference_spectrum["eigenpair_relative_residual_max"],
            endpoint_spectrum["eigenpair_relative_residual_max"],
            branch_spectrum["eigenpair_relative_residual_max"],
        )
        <= 1.0e-10,
        "VQURB15_DECISION_RECONSTRUCTION": decisions == EXPECTED_DECISIONS,
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    output = {
        "schema": "cassi.qcd-unconstrained-radial-baryon.verification.v1",
        "source_manifest": {
            "verifier": source_record(SELF),
            "protocol": source_record(PROTOCOL),
            "primary": source_record(PRIMARY_SOURCE),
            "upstream": source_record(UPSTREAM),
            "receipt": source_record(input_path),
            "profiles": source_record(profile_path),
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "checks": checks,
        "spectra": {
            "reference": reference_spectrum,
            "retained_endpoint": endpoint_spectrum,
            "branch_trial": branch_spectrum,
        },
        "decisions": decisions,
        "verdict": verdict,
        "execution": {"elapsed_seconds": time.time() - started},
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    output_path = output_dir / "verification.json"
    output_path.write_text(
        json.dumps(output, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    print(
        " ".join(
            f"{key}={'PASS' if value else 'FAIL'}"
            for key, value in checks.items()
        )
    )
    print(f"VERIFICATION={verdict}")
    print(f"RESULTS={output_path.relative_to(ROOT).as_posix()}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
