#!/usr/bin/env python3
"""Measure a finite interacting SU(2) Feshbach resolvent bound.

The calculation is deliberately finite: it uses the existing seven-link
nested-cutoff Hamiltonian, projects away its computed finite-graph ground
vector, and measures the discarded-sector resolvent and Schur self-energy.
It does not assert a uniform regulator bound or a continuum mass gap.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
from scipy.linalg import eigh, null_space

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
PROTOCOL = ROOT / "computations/yang-mills-interacting-feshbach-prereg.md"
REFERENCE = ROOT / "computations/verify_yang_mills_exact_block_spectrum.py"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_interacting_feshbach/verification.json"

RETAINED_CUTOFF = 1
FULL_CUTOFF = 3
COUPLINGS = (Fraction(1, 4), Fraction(1), Fraction(4), Fraction(16))
GROUND_RESIDUAL_TOLERANCE = 1.0e-11
INEQUALITY_RELATIVE_TOLERANCE = 1.0e-10
INEQUALITY_ABSOLUTE_TOLERANCE = 1.0e-12
FESHBACH_ABSOLUTE_TOLERANCE = 1.0e-10
FRAME_TOLERANCE = 1.0e-12


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_reference() -> Any:
    spec = importlib.util.spec_from_file_location("ym_exact_block_spectrum", REFERENCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load reference source: {REFERENCE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def check(result: dict[str, Any], name: str, passed: bool, detail: Any) -> None:
    if any(row["name"] == name for row in result["checks"]):
        raise ValueError(f"duplicate check name: {name}")
    row = {"name": name, "passed": bool(passed), "detail": detail}
    result["checks"].append(row)
    if not passed:
        result["failures"].append(name)


def finite_matrix(value: Any) -> bool:
    return bool(np.all(np.isfinite(np.asarray(value))))


def inequality_pass(actual: float, bound: float, relative: float = INEQUALITY_RELATIVE_TOLERANCE,
                    absolute: float = INEQUALITY_ABSOLUTE_TOLERANCE) -> bool:
    return float(actual) <= float(bound) * (1.0 + relative) + absolute


def orthonormal_range(matrix: np.ndarray, tolerance: float = FRAME_TOLERANCE) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=float)
    if matrix.size == 0:
        return np.zeros((matrix.shape[0], 0), dtype=float)
    left, singular, _ = np.linalg.svd(matrix, full_matrices=False)
    scale = max(float(singular[0]), 1.0)
    rank = int(np.count_nonzero(singular > tolerance * scale))
    return left[:, :rank]


def normalized_hamiltonian(reference: Any, cutoff: int, coupling: Fraction) -> tuple[Any, np.ndarray]:
    space = reference.SpectrumSpace(cutoff)
    generalized = np.asarray(space.hamiltonian(coupling), dtype=float)
    overlap_diag = np.diag(space.overlap).astype(float)
    inverse_sqrt = 1.0 / np.sqrt(overlap_diag)
    normalized = inverse_sqrt[:, None] * generalized * inverse_sqrt[None, :]
    return space, np.asarray(normalized, dtype=float)


def row_for_coupling(reference: Any, coupling: Fraction, result: dict[str, Any]) -> dict[str, Any]:
    full_space, hamiltonian = normalized_hamiltonian(reference, FULL_CUTOFF, coupling)
    retained_space, _ = normalized_hamiltonian(reference, RETAINED_CUTOFF, coupling)
    full_values, full_vectors = eigh(hamiltonian)
    energy = float(full_values[0])
    omega = np.asarray(full_vectors[:, 0], dtype=float)
    omega /= np.linalg.norm(omega)
    if omega[np.argmax(np.abs(omega))] < 0.0:
        omega = -omega

    ground_residual = float(np.linalg.norm(hamiltonian @ omega - energy * omega))
    n_full = len(full_space.states)
    retained_indices = np.asarray(
        [full_space.index[state] for state in retained_space.states], dtype=int
    )
    coordinate_frame = np.eye(n_full, dtype=float)[:, retained_indices]
    vacuum_projection = np.eye(n_full, dtype=float) - np.outer(omega, omega)
    retained_frame = orthonormal_range(vacuum_projection @ coordinate_frame)
    discarded_frame = null_space(
        np.vstack((omega[None, :], retained_frame.T)), rcond=FRAME_TOLERANCE
    )

    shifted = hamiltonian - energy * np.eye(n_full, dtype=float)
    retained_block = retained_frame.T @ shifted @ retained_frame
    coupling_block = retained_frame.T @ shifted @ discarded_frame
    discarded_block = discarded_frame.T @ shifted @ discarded_frame

    retained_values = eigh(retained_block, eigvals_only=True)
    discarded_values = eigh(discarded_block, eigvals_only=True)
    vacuum_orthogonal_frame = null_space(omega[None, :], rcond=FRAME_TOLERANCE)
    physical_values = eigh(
        vacuum_orthogonal_frame.T @ shifted @ vacuum_orthogonal_frame,
        eigvals_only=True,
    )
    gap = float(physical_values[0])
    alpha = float(retained_values[0])
    delta = float(discarded_values[0])
    beta = float(np.linalg.norm(coupling_block, ord=2))
    lambda_test = 0.5 * min(gap, delta)

    resolvent = np.linalg.inv(discarded_block - lambda_test * np.eye(len(discarded_values)))
    resolvent_norm = float(np.linalg.norm(resolvent, ord=2))
    resolvent_bound = 1.0 / (delta - lambda_test)
    self_energy = coupling_block @ resolvent @ coupling_block.T
    self_energy_norm = float(np.linalg.norm(self_energy, ord=2))
    self_energy_bound = beta * beta / (delta - lambda_test)
    feshbach = retained_block - lambda_test * np.eye(len(retained_values)) - self_energy
    feshbach_minimum = float(eigh(feshbach, eigvals_only=True)[0])
    phi_test = alpha - lambda_test - self_energy_bound
    phi_zero = alpha - beta * beta / delta
    if phi_zero > 0.0:
        discriminant = (alpha - delta) ** 2 + 4.0 * beta * beta
        certified_gap = 0.5 * (alpha + delta - math.sqrt(discriminant))
    else:
        certified_gap = None

    tail_floor_distance = float(np.min(np.abs(discarded_values - delta)))
    tail_floor_resolvent_defined = bool(tail_floor_distance > 1.0e-9)
    label = str(coupling)

    row = {
        "coupling": label,
        "x": float(coupling),
        "full_cutoff": FULL_CUTOFF,
        "retained_cutoff": RETAINED_CUTOFF,
        "full_dimension": n_full,
        "retained_dimension": int(retained_frame.shape[1]),
        "discarded_dimension": int(discarded_frame.shape[1]),
        "ground_energy": energy,
        "ground_residual": ground_residual,
        "finite_gap": gap,
        "alpha_retained": alpha,
        "delta_discarded": delta,
        "beta_coupling": beta,
        "lambda_test": lambda_test,
        "resolvent_norm": resolvent_norm,
        "resolvent_bound": resolvent_bound,
        "self_energy_norm": self_energy_norm,
        "self_energy_bound": self_energy_bound,
        "feshbach_minimum": feshbach_minimum,
        "phi_test": phi_test,
        "phi_zero": phi_zero,
        "self_energy_ratio_at_zero": beta * beta / (alpha * delta),
        "certified_gap_lower_bound": certified_gap,
        "tail_floor_distance": tail_floor_distance,
        "tail_floor_resolvent_defined": tail_floor_resolvent_defined,
    }
    prefix = f"x={label}"
    check(result, f"{prefix}:post-projection ranks",
          retained_frame.shape[1] == 4 and discarded_frame.shape[1] == 18,
          {"retained_rank": int(retained_frame.shape[1]),
           "discarded_rank": int(discarded_frame.shape[1])})
    check(result, f"{prefix}:normalized Hamiltonian finite", finite_matrix(hamiltonian),
          {"dimension": n_full})
    check(result, f"{prefix}:ground residual", ground_residual <= GROUND_RESIDUAL_TOLERANCE,
          {"value": ground_residual, "tolerance": GROUND_RESIDUAL_TOLERANCE})
    check(result, f"{prefix}:positive retained and discarded floors",
          alpha > 0.0 and delta > 0.0,
          {"alpha": alpha, "delta": delta})
    check(result, f"{prefix}:discarded resolvent bound",
          inequality_pass(resolvent_norm, resolvent_bound),
          {"actual": resolvent_norm, "bound": resolvent_bound})
    check(result, f"{prefix}:Feshbach self-energy bound",
          inequality_pass(self_energy_norm, self_energy_bound),
          {"actual": self_energy_norm, "bound": self_energy_bound})
    check(result, f"{prefix}:Schur lower bound at test energy",
          feshbach_minimum > 0.0 and feshbach_minimum + FESHBACH_ABSOLUTE_TOLERANCE >= phi_test,
          {"minimum": feshbach_minimum, "phi_test": phi_test})
    if certified_gap is not None:
        check(result, f"{prefix}:certified gap lower bound",
              gap + FESHBACH_ABSOLUTE_TOLERANCE >= certified_gap,
              {"measured_gap": gap, "certified_lower_bound": certified_gap})
    else:
        check(result, f"{prefix}:positive Schur certificate unavailable",
              phi_zero <= 0.0,
              {"phi_zero": phi_zero})
    check(result, f"{prefix}:tail-floor marks resolvent undefined",
          not tail_floor_resolvent_defined,
          {"distance_to_tail_floor": tail_floor_distance,
           "resolvent_defined": tail_floor_resolvent_defined})
    return row


def build_record(reference: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "cassi.yang-mills.interacting-feshbach.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "protocol": {"path": PROTOCOL.relative_to(ROOT).as_posix(),
                         "sha256": sha256(PROTOCOL)},
            "source": {"path": SOURCE.relative_to(ROOT).as_posix(),
                       "sha256": sha256(SOURCE)},
            "reference": {"path": REFERENCE.relative_to(ROOT).as_posix(),
                          "sha256": sha256(REFERENCE)},
        },
        "schedule": {
            "retained_cutoff": RETAINED_CUTOFF,
            "full_cutoff": FULL_CUTOFF,
            "couplings": [str(value) for value in COUPLINGS],
        },
        "checks": [],
        "failures": [],
        "rows": [],
    }
    retained_space, _ = normalized_hamiltonian(reference, RETAINED_CUTOFF, COUPLINGS[0])
    full_space, _ = normalized_hamiltonian(reference, FULL_CUTOFF, COUPLINGS[0])
    check(result, "nested basis dimensions", len(retained_space.states) == 4 and len(full_space.states) == 23,
          {"retained": len(retained_space.states), "full": len(full_space.states)})
    check(result, "nested state inclusion",
          set(retained_space.states).issubset(set(full_space.states)),
          {"retained": len(retained_space.states), "full": len(full_space.states)})

    for coupling in COUPLINGS:
        result["rows"].append(row_for_coupling(reference, coupling, result))

    positive_rows = [row for row in result["rows"] if row["certified_gap_lower_bound"] is not None
                     and row["certified_gap_lower_bound"] > 0.0]
    result["status"] = "PASS" if not result["failures"] else "FAIL"
    result["classification"] = (
        "SUPPORTS_FINITE_FESHBACH"
        if len(positive_rows) == len(result["rows"])
        else "NO_POSITIVE_SCHUR_CERTIFICATE"
    )
    result["summary"] = {
        "checks": len(result["checks"]),
        "passing_checks": sum(1 for row in result["checks"] if row["passed"]),
        "rows": len(result["rows"]),
        "positive_certified_rows": len(positive_rows),
        "minimum_resolvent_margin": min(
            row["delta_discarded"] - row["lambda_test"] for row in result["rows"]
        ),
        "minimum_self_energy_ratio_at_zero": min(
            row["self_energy_ratio_at_zero"] for row in result["rows"]
        ),
        "maximum_self_energy_ratio_at_zero": max(
            row["self_energy_ratio_at_zero"] for row in result["rows"]
        ),
    }
    result["scope"] = {
        "graph": "seven_link_two_plaquette_SU2",
        "regulator": "dimensionless finite cutoff C_P=1 to C_Q=3",
        "discarded_resolvent": "finite Q-sector only",
        "uniform_spacing_bound": "UNRESOLVED",
        "uniform_volume_bound": "UNRESOLVED",
        "continuum_recovery": "UNRESOLVED",
        "continuum_mass_gap": "UNRESOLVED",
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    if not PROTOCOL.exists() or not REFERENCE.exists():
        raise FileNotFoundError("protocol or reference source is missing")
    reference = load_reference()
    record = build_record(reference)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, allow_nan=False)
    print(f"Receipt: {output}")
    print(json.dumps({key: record[key] for key in
                      ("status", "classification", "summary", "failures")}, indent=2))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
