#!/usr/bin/env python3
"""Measure a nested-cutoff interacting SU(2) Feshbach family."""
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
PROTOCOL = ROOT / "computations/yang-mills-interacting-feshbach-cutoff-screen-prereg.md"
REFERENCE = ROOT / "computations/verify_yang_mills_exact_block_spectrum.py"
PREDECESSOR_SOURCE = ROOT / "computations/verify_yang_mills_interacting_feshbach.py"
PREDECESSOR_RECEIPT = ROOT / "runs/yang_mills_interacting_feshbach/verification.json"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_interacting_feshbach_cutoff/verification.json"

CUTOFFS = (1, 2, 3, 4, 5)
CUTOFF_PAIRS = tuple(
    (inner, outer)
    for outer in CUTOFFS[1:]
    for inner in CUTOFFS[:outer - 1]
)
COUPLINGS = (Fraction(1, 4), Fraction(1), Fraction(4), Fraction(16))
EXPECTED_DIMENSIONS = {1: 4, 2: 11, 3: 23, 4: 42, 5: 69}
GROUND_RESIDUAL_TOLERANCE = 1.0e-11
INEQUALITY_RELATIVE_TOLERANCE = 1.0e-10
INEQUALITY_ABSOLUTE_TOLERANCE = 1.0e-12
FESHBACH_ABSOLUTE_TOLERANCE = 1.0e-10
FRAME_TOLERANCE = 1.0e-12
TAIL_FLOOR_TOLERANCE = 1.0e-9


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def load_reference() -> Any:
    spec = importlib.util.spec_from_file_location("ym_exact_block_spectrum_cutoff", REFERENCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load reference source: {REFERENCE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def check(result: dict[str, Any], name: str, passed: bool, detail: Any) -> None:
    if any(row["name"] == name for row in result["checks"]):
        raise ValueError(f"duplicate check name: {name}")
    result["checks"].append({"name": name, "passed": bool(passed), "detail": detail})
    if not passed:
        result["failures"].append(name)


def inequality_pass(actual: float, bound: float) -> bool:
    return float(actual) <= float(bound) * (1.0 + INEQUALITY_RELATIVE_TOLERANCE) + INEQUALITY_ABSOLUTE_TOLERANCE


def orthonormal_range(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=float)
    if matrix.size == 0:
        return np.zeros((matrix.shape[0], 0), dtype=float)
    left, singular, _ = np.linalg.svd(matrix, full_matrices=False)
    scale = max(float(singular[0]), 1.0)
    rank = int(np.count_nonzero(singular > FRAME_TOLERANCE * scale))
    return left[:, :rank]


def normalized_hamiltonian(space: Any, coupling: Fraction) -> np.ndarray:
    generalized = np.asarray(space.hamiltonian(coupling), dtype=float)
    overlap_diag = np.diag(space.overlap).astype(float)
    inverse_sqrt = 1.0 / np.sqrt(overlap_diag)
    return np.asarray(inverse_sqrt[:, None] * generalized * inverse_sqrt[None, :], dtype=float)


def outer_data(space: Any, hamiltonian: np.ndarray) -> dict[str, Any]:
    values, vectors = eigh(hamiltonian)
    energy = float(values[0])
    omega = np.asarray(vectors[:, 0], dtype=float)
    omega /= np.linalg.norm(omega)
    if omega[np.argmax(np.abs(omega))] < 0.0:
        omega = -omega
    ground_residual = float(np.linalg.norm(hamiltonian @ omega - energy * omega))
    return {
        "space": space,
        "hamiltonian": hamiltonian,
        "values": values,
        "energy": energy,
        "omega": omega,
        "ground_residual": ground_residual,
        "shifted": hamiltonian - energy * np.eye(len(space.states), dtype=float),
        "gap": float(values[1] - energy),
        "vacuum_projection": np.eye(len(space.states), dtype=float) - np.outer(omega, omega),
    }


def row_for_pair(
    outer: dict[str, Any],
    inner_space: Any,
    inner_cutoff: int,
    outer_cutoff: int,
    coupling: Fraction,
    result: dict[str, Any],
) -> dict[str, Any]:
    full_space = outer["space"]
    retained_indices = np.asarray(
        [full_space.index[state] for state in inner_space.states], dtype=int
    )
    coordinate_frame = np.eye(len(full_space.states), dtype=float)[:, retained_indices]
    retained_frame = orthonormal_range(outer["vacuum_projection"] @ coordinate_frame)
    discarded_frame = null_space(
        np.vstack((outer["omega"][None, :], retained_frame.T)),
        rcond=FRAME_TOLERANCE,
    )
    retained_block = retained_frame.T @ outer["shifted"] @ retained_frame
    coupling_block = retained_frame.T @ outer["shifted"] @ discarded_frame
    discarded_block = discarded_frame.T @ outer["shifted"] @ discarded_frame
    retained_values = eigh(retained_block, eigvals_only=True)
    discarded_values = eigh(discarded_block, eigvals_only=True)
    alpha = float(retained_values[0])
    delta = float(discarded_values[0])
    beta = float(np.linalg.norm(coupling_block, ord=2))
    finite_gap = float(outer["gap"])
    lambda_test = 0.5 * min(finite_gap, delta)
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
    tail_floor_resolvent_defined = bool(tail_floor_distance > TAIL_FLOOR_TOLERANCE)
    label = str(coupling)
    prefix = f"cP={inner_cutoff},cQ={outer_cutoff},x={label}"
    row = {
        "inner_cutoff": inner_cutoff,
        "outer_cutoff": outer_cutoff,
        "coupling": label,
        "x": float(coupling),
        "full_dimension": len(full_space.states),
        "retained_dimension": int(retained_frame.shape[1]),
        "discarded_dimension": int(discarded_frame.shape[1]),
        "ground_energy": outer["energy"],
        "ground_residual": outer["ground_residual"],
        "finite_gap": finite_gap,
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
        "root_to_gap_ratio": None if certified_gap is None else certified_gap / finite_gap,
        "tail_floor_distance": tail_floor_distance,
        "tail_floor_resolvent_defined": tail_floor_resolvent_defined,
        "outer_matrix_sha256": array_sha256(outer["hamiltonian"]),
    }
    expected_p = EXPECTED_DIMENSIONS[inner_cutoff]
    expected_q = EXPECTED_DIMENSIONS[outer_cutoff]
    check(result, f"{prefix}:dimensions and nested inclusion",
          len(full_space.states) == expected_q
          and len(inner_space.states) == expected_p
          and set(inner_space.states).issubset(set(full_space.states))
          and retained_frame.shape[1] == expected_p
          and discarded_frame.shape[1] == expected_q - 1 - expected_p,
          {"full": len(full_space.states), "retained_source": len(inner_space.states),
           "retained_rank": int(retained_frame.shape[1]),
           "discarded_rank": int(discarded_frame.shape[1]),
           "expected": {"full": expected_q, "retained": expected_p,
                        "discarded": expected_q - 1 - expected_p}})
    check(result, f"{prefix}:normalized Hamiltonian finite and Hermitian",
          bool(np.all(np.isfinite(outer["hamiltonian"])))
          and float(np.max(np.abs(outer["hamiltonian"] - outer["hamiltonian"].T))) <= 1.0e-10,
          {"hermiticity_residual": float(np.max(np.abs(outer["hamiltonian"] - outer["hamiltonian"].T)))})
    check(result, f"{prefix}:ground residual",
          outer["ground_residual"] <= GROUND_RESIDUAL_TOLERANCE,
          {"value": outer["ground_residual"], "tolerance": GROUND_RESIDUAL_TOLERANCE})
    check(result, f"{prefix}:positive floors and test domain",
          finite_gap > 0.0 and alpha > 0.0 and delta > 0.0 and 0.0 <= lambda_test < delta,
          {"gap": finite_gap, "alpha": alpha, "delta": delta, "lambda_test": lambda_test})
    check(result, f"{prefix}:discarded resolvent bound",
          inequality_pass(resolvent_norm, resolvent_bound),
          {"actual": resolvent_norm, "bound": resolvent_bound})
    check(result, f"{prefix}:Feshbach self-energy bound",
          inequality_pass(self_energy_norm, self_energy_bound),
          {"actual": self_energy_norm, "bound": self_energy_bound})
    check(result, f"{prefix}:Schur lower bound at test energy",
          feshbach_minimum > 0.0 and feshbach_minimum + FESHBACH_ABSOLUTE_TOLERANCE >= phi_test,
          {"minimum": feshbach_minimum, "phi_test": phi_test})
    check(result, f"{prefix}:root consistency",
          certified_gap is None or certified_gap > 0.0,
          {"phi_zero": phi_zero, "certified_gap": certified_gap})
    check(result, f"{prefix}:measured gap lower bound",
          certified_gap is None or finite_gap + FESHBACH_ABSOLUTE_TOLERANCE >= certified_gap,
          {"measured_gap": finite_gap, "certified_gap": certified_gap})
    check(result, f"{prefix}:tail-floor marks resolvent undefined",
          not tail_floor_resolvent_defined and tail_floor_distance == 0.0,
          {"distance_to_tail_floor": tail_floor_distance,
           "resolvent_defined": tail_floor_resolvent_defined})
    return row


def family_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for coupling in (str(value) for value in COUPLINGS):
        selected = [row for row in rows if row["coupling"] == coupling]
        roots = [row["certified_gap_lower_bound"] for row in selected
                 if row["certified_gap_lower_bound"] is not None]
        ratios = [row["root_to_gap_ratio"] for row in selected
                  if row["root_to_gap_ratio"] is not None]
        summary[coupling] = {
            "rows": len(selected),
            "min_certified_root": min(roots) if roots else None,
            "min_root_to_gap_ratio": min(ratios) if ratios else None,
            "min_self_energy_ratio_at_zero": min(row["self_energy_ratio_at_zero"] for row in selected),
            "max_self_energy_ratio_at_zero": max(row["self_energy_ratio_at_zero"] for row in selected),
        }
    return summary


def build_record(reference: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "cassi.yang-mills.interacting-feshbach-cutoff-screen.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "protocol": {"path": PROTOCOL.relative_to(ROOT).as_posix(), "sha256": sha256(PROTOCOL)},
            "source": {"path": SOURCE.relative_to(ROOT).as_posix(), "sha256": sha256(SOURCE)},
            "reference": {"path": REFERENCE.relative_to(ROOT).as_posix(), "sha256": sha256(REFERENCE)},
            "predecessor_source": {"path": PREDECESSOR_SOURCE.relative_to(ROOT).as_posix(), "sha256": sha256(PREDECESSOR_SOURCE)},
            "predecessor_receipt": {"path": PREDECESSOR_RECEIPT.relative_to(ROOT).as_posix(), "sha256": sha256(PREDECESSOR_RECEIPT)},
        },
        "schedule": {
            "cutoffs": list(CUTOFFS),
            "cutoff_pairs": [list(pair) for pair in CUTOFF_PAIRS],
            "couplings": [str(value) for value in COUPLINGS],
            "expected_dimensions": {str(key): value for key, value in EXPECTED_DIMENSIONS.items()},
        },
        "checks": [],
        "failures": [],
        "rows": [],
    }
    spaces = {cutoff: reference.SpectrumSpace(cutoff) for cutoff in CUTOFFS}
    check(result, "nested source dimensions and pair schedule",
          [len(spaces[cutoff].states) for cutoff in CUTOFFS]
          == [EXPECTED_DIMENSIONS[cutoff] for cutoff in CUTOFFS]
          and len(CUTOFF_PAIRS) == 10,
          {"dimensions": EXPECTED_DIMENSIONS, "pairs": [list(pair) for pair in CUTOFF_PAIRS]})
    check(result, "coupling schedule",
          tuple(Fraction(value) for value in COUPLINGS)
          == (Fraction(1, 4), Fraction(1), Fraction(4), Fraction(16)),
          {"couplings": [str(value) for value in COUPLINGS]})

    outer_cache: dict[tuple[int, Fraction], dict[str, Any]] = {}
    for outer_cutoff in CUTOFFS[1:]:
        for coupling in COUPLINGS:
            space = spaces[outer_cutoff]
            outer_cache[(outer_cutoff, coupling)] = outer_data(
                space, normalized_hamiltonian(space, coupling))
    for inner_cutoff, outer_cutoff in CUTOFF_PAIRS:
        for coupling in COUPLINGS:
            result["rows"].append(row_for_pair(
                outer_cache[(outer_cutoff, coupling)], spaces[inner_cutoff],
                inner_cutoff, outer_cutoff, coupling, result))

    grouped = family_summary(result["rows"])
    expected_pairs = {tuple(pair) for pair in result["schedule"]["cutoff_pairs"]}
    actual_pairs = {(row["inner_cutoff"], row["outer_cutoff"]) for row in result["rows"]}
    expected_couplings = {str(value) for value in COUPLINGS}
    check(result, "family summary and row schedule",
          len(result["rows"]) == 40
          and actual_pairs == expected_pairs
          and {row["coupling"] for row in result["rows"]} == expected_couplings
          and all(value["rows"] == 10 for value in grouped.values()),
          {"rows": len(result["rows"]), "pairs": sorted(actual_pairs), "summary": grouped})
    positive_rows = [row for row in result["rows"]
                     if row["certified_gap_lower_bound"] is not None
                     and row["certified_gap_lower_bound"] > 0.0]
    result["family_summary"] = grouped
    result["status"] = "PASS" if not result["failures"] else "FAIL"
    result["classification"] = (
        "SUPPORTS_FINITE_CUTOFF_FESHBACH_FAMILY"
        if len(positive_rows) == len(result["rows"])
        else "NO_POSITIVE_FAMILY_CERTIFICATE"
    )
    result["summary"] = {
        "checks": len(result["checks"]),
        "passing_checks": sum(1 for row in result["checks"] if row["passed"]),
        "rows": len(result["rows"]),
        "positive_certified_rows": len(positive_rows),
        "cutoff_pairs": len(CUTOFF_PAIRS),
        "couplings": len(COUPLINGS),
    }
    result["scope"] = {
        "graph": "seven_link_two_plaquette_SU2",
        "regulator": "dimensionless nested finite cutoffs 1 through 5",
        "discarded_resolvent": "finite Q-sector family only",
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
    required = (PROTOCOL, REFERENCE, PREDECESSOR_SOURCE, PREDECESSOR_RECEIPT)
    if not all(path.exists() for path in required):
        raise FileNotFoundError("protocol, reference, predecessor source or predecessor receipt is missing")
    inputs = {path: path.read_bytes() for path in (PROTOCOL, SOURCE, REFERENCE, PREDECESSOR_SOURCE, PREDECESSOR_RECEIPT)}
    record = build_record(load_reference())
    if any(path.read_bytes() != content for path, content in inputs.items()):
        raise RuntimeError("input bytes changed during the run; refusing to seal a mixed-source receipt")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(f"Receipt: {output}")
    print(json.dumps({key: record[key] for key in
                      ("status", "classification", "summary", "failures")}, indent=2))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
