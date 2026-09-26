#!/usr/bin/env python3
"""Measure the pre-registered finite-volume C=0-to-C=1 Feshbach bridge."""
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
from scipy.sparse import csr_matrix

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
PROTOCOL = ROOT / "computations/yang-mills-volume-feshbach-bridge-prereg.md"
INDEPENDENT_SOURCE = ROOT / "computations/verify_yang_mills_volume_feshbach_bridge_independent.py"
EXACT_SOURCE = ROOT / "computations/verify_yang_mills_exact_block_spectrum.py"
LARGE_SOURCE = ROOT / "computations/verify_yang_mills_su2_larger_volume_hamiltonian.py"
SCIENTIFIC_PROTOCOL = ROOT / "computations/yang-mills-su2-larger-volume-hamiltonian-prereg.md"
RECOVERY_PROTOCOL = ROOT / "computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md"
LARGE_RECEIPT = ROOT / "runs/yang_mills_su2_larger_volume_hamiltonian_recovery/verification.json"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_volume_feshbach_bridge/verification.json"

COUPLINGS = (Fraction(1, 64), Fraction(1, 16), Fraction(1, 4), Fraction(1))
EXPECTED_DIMENSIONS = {"small": {"P": 1, "Q": 4}, "large": {"P": 1, "Q": 868}}
GROUND_RESIDUAL_TOLERANCE = 1.0e-11
INEQUALITY_RELATIVE_TOLERANCE = 1.0e-10
INEQUALITY_ABSOLUTE_TOLERANCE = 1.0e-12
FESHBACH_ABSOLUTE_TOLERANCE = 1.0e-10
FRAME_TOLERANCE = 1.0e-12
TAIL_FLOOR_TOLERANCE = 1.0e-9
MATRIX_TOLERANCE = 1.0e-10


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def json_sha256(value: Any) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load source: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_sources() -> tuple[Any, Any]:
    exact = load_module("verify_yang_mills_exact_block_spectrum", EXACT_SOURCE)
    large = load_module("ym_large_volume_recovered", LARGE_SOURCE)
    return exact, large


def check(result: dict[str, Any], name: str, passed: bool, detail: Any) -> None:
    if any(row["name"] == name for row in result["checks"]):
        raise ValueError(f"duplicate check name: {name}")
    result["checks"].append({"name": name, "passed": bool(passed), "detail": detail})
    if not passed:
        result["failures"].append(name)


def inequality_pass(actual: float, bound: float) -> bool:
    return float(actual) <= float(bound) * (1.0 + INEQUALITY_RELATIVE_TOLERANCE) + INEQUALITY_ABSOLUTE_TOLERANCE


def orthonormal_range(matrix: np.ndarray) -> np.ndarray:
    left, singular, _ = np.linalg.svd(np.asarray(matrix, dtype=float), full_matrices=False)
    if singular.size == 0:
        return np.zeros((matrix.shape[0], 0), dtype=float)
    scale = max(float(singular[0]), 1.0)
    rank = int(np.count_nonzero(singular > FRAME_TOLERANCE * scale))
    return left[:, :rank]


def small_outer(exact: Any, coupling: Fraction) -> tuple[np.ndarray, dict[str, Any]]:
    space = exact.SpectrumSpace(1)
    generalized = np.asarray(space.hamiltonian(coupling), dtype=float)
    overlap_diag = np.diag(space.overlap).astype(float)
    inverse_sqrt = 1.0 / np.sqrt(overlap_diag)
    matrix = np.asarray(inverse_sqrt[:, None] * generalized * inverse_sqrt[None, :], dtype=float)
    return matrix, {
        "states": [list(state) for state in space.states],
        "retained_states": [list(state) for state in exact.SpectrumSpace(0).states],
        "state_sha256": json_sha256([list(state) for state in space.states]),
        "retained_state_sha256": json_sha256([list(state) for state in exact.SpectrumSpace(0).states]),
        "dimension": len(space.states),
        "retained_dimension": len(exact.SpectrumSpace(0).states),
    }


def large_sources(large: Any) -> tuple[tuple[Any, ...], tuple[Any, ...], csr_matrix, list[dict[str, Any]], dict[str, Any]]:
    retained = tuple(large.basis_states(0))
    outer = tuple(large.basis_states(1))
    if not retained or not outer:
        raise ArithmeticError("large graph source basis is empty")
    operator = csr_matrix((len(outer), len(outer)), dtype=complex)
    records: list[dict[str, Any]] = []
    for word in large.PLAQUETTES:
        evaluated = large.evaluate_plaquette(outer, {}, {}, word, 1)
        matrix = evaluated.pop("matrix")
        operator = (operator + matrix).tocsr()
        records.append(evaluated)
    operator.sum_duplicates()
    operator.sort_indices()
    metadata = {
        "states": [list(state) for state in outer],
        "retained_states": [list(state) for state in retained],
        "state_sha256": large.basis_hash(outer),
        "retained_state_sha256": large.basis_hash(retained),
        "dimension": len(outer),
        "retained_dimension": len(retained),
        "operator_nnz": int(operator.nnz),
    }
    return retained, outer, operator, records, metadata


def large_outer(large: Any, states: tuple[Any, ...], operator: csr_matrix, coupling: Fraction) -> np.ndarray:
    norms = np.asarray([large.state_norm(state) for state in states], dtype=float)
    kinetic = np.asarray([large.state_energy(state) for state in states], dtype=float)
    x = float(coupling)
    diagonal = (kinetic + 22.0 * x) * norms
    hamiltonian = csr_matrix((diagonal, (np.arange(len(states)), np.arange(len(states)))), shape=(len(states), len(states))) - x * operator
    inverse_sqrt = 1.0 / np.sqrt(norms)
    physical = hamiltonian.multiply(inverse_sqrt[:, None]).multiply(inverse_sqrt[None, :]).toarray()
    return np.asarray(0.5 * (physical + physical.T.conjugate()).real, dtype=float)


def outer_data(matrix: np.ndarray) -> dict[str, Any]:
    values, vectors = eigh(matrix)
    energy = float(values[0])
    omega = np.asarray(vectors[:, 0], dtype=float)
    omega /= np.linalg.norm(omega)
    if omega[np.argmax(np.abs(omega))] < 0.0:
        omega = -omega
    return {
        "matrix": matrix,
        "values": values,
        "energy": energy,
        "omega": omega,
        "ground_residual": float(np.linalg.norm(matrix @ omega - energy * omega)),
        "gap": float(values[1] - energy),
        "vacuum_projection": np.eye(len(values), dtype=float) - np.outer(omega, omega),
    }


def feshbach_row(
    graph: str,
    coupling: Fraction,
    outer: dict[str, Any],
    retained_index: int,
    retained_dimension: int,
    outer_dimension: int,
    result: dict[str, Any],
) -> dict[str, Any]:
    coordinate = np.zeros((outer_dimension, 1), dtype=float)
    coordinate[retained_index, 0] = 1.0
    retained_frame = orthonormal_range(outer["vacuum_projection"] @ coordinate)
    discarded_frame = null_space(
        np.vstack((outer["omega"][None, :], retained_frame.T)),
        rcond=FRAME_TOLERANCE,
    )
    shifted = outer["matrix"] - outer["energy"] * np.eye(outer_dimension, dtype=float)
    retained_block = retained_frame.T @ shifted @ retained_frame
    coupling_block = retained_frame.T @ shifted @ discarded_frame
    discarded_block = discarded_frame.T @ shifted @ discarded_frame
    retained_values = eigh(retained_block, eigvals_only=True)
    discarded_values, discarded_vectors = eigh(discarded_block)
    alpha = float(retained_values[0])
    delta = float(discarded_values[0])
    beta = float(np.linalg.norm(coupling_block, ord=2))
    finite_gap = float(outer["gap"])
    lambda_test = 0.5 * min(finite_gap, delta)
    resolvent_norm = float(1.0 / np.min(discarded_values - lambda_test))
    resolvent_bound = 1.0 / (delta - lambda_test)
    coupling_eigen = coupling_block @ discarded_vectors
    self_energy_value = float(np.sum((coupling_eigen[0] ** 2) / (discarded_values - lambda_test)))
    self_energy_norm = abs(self_energy_value)
    self_energy_bound = beta * beta / (delta - lambda_test)
    feshbach_minimum = alpha - lambda_test - self_energy_value
    phi_test = alpha - lambda_test - self_energy_bound
    phi_zero = alpha - beta * beta / delta
    certified_gap = None
    if phi_zero > 0.0:
        discriminant = (alpha - delta) ** 2 + 4.0 * beta * beta
        certified_gap = 0.5 * (alpha + delta - math.sqrt(discriminant))
    tail_floor_distance = float(np.min(np.abs(discarded_values - delta)))
    label = str(coupling)
    prefix = f"graph={graph},x={label}"
    row = {
        "graph": graph,
        "coupling": label,
        "x": float(coupling),
        "full_dimension": outer_dimension,
        "retained_source_dimension": retained_dimension,
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
        "tail_floor_resolvent_defined": bool(tail_floor_distance > TAIL_FLOOR_TOLERANCE),
        "outer_matrix_sha256": array_sha256(outer["matrix"]),
    }
    expected_q = EXPECTED_DIMENSIONS[graph]["Q"]
    check(result, f"{prefix}:dimensions and ranks",
          outer_dimension == expected_q and retained_dimension == 1
          and retained_frame.shape[1] == 1
          and discarded_frame.shape[1] == expected_q - 2,
          {"full": outer_dimension, "retained_source": retained_dimension,
           "retained_rank": int(retained_frame.shape[1]),
           "discarded_rank": int(discarded_frame.shape[1]),
           "expected": {"full": expected_q, "retained": 1, "discarded": expected_q - 2}})
    check(result, f"{prefix}:normalized Hamiltonian finite and Hermitian",
          bool(np.all(np.isfinite(outer["matrix"])))
          and float(np.max(np.abs(outer["matrix"] - outer["matrix"].T))) <= MATRIX_TOLERANCE,
          {"hermiticity_residual": float(np.max(np.abs(outer["matrix"] - outer["matrix"].T)))})
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
          tail_floor_distance == 0.0 and not row["tail_floor_resolvent_defined"],
          {"distance_to_tail_floor": tail_floor_distance,
           "resolvent_defined": row["tail_floor_resolvent_defined"]})
    return row


def build_record(exact: Any, large: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "cassi.yang-mills.volume-feshbach-bridge.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "protocol": {"path": PROTOCOL.relative_to(ROOT).as_posix(), "sha256": sha256(PROTOCOL)},
            "source": {"path": SOURCE.relative_to(ROOT).as_posix(), "sha256": sha256(SOURCE)},
            "independent_source": {"path": INDEPENDENT_SOURCE.relative_to(ROOT).as_posix(), "sha256": sha256(INDEPENDENT_SOURCE)},
            "exact_source": {"path": EXACT_SOURCE.relative_to(ROOT).as_posix(), "sha256": sha256(EXACT_SOURCE)},
            "large_source": {"path": LARGE_SOURCE.relative_to(ROOT).as_posix(), "sha256": sha256(LARGE_SOURCE)},
            "scientific_protocol": {"path": SCIENTIFIC_PROTOCOL.relative_to(ROOT).as_posix(), "sha256": sha256(SCIENTIFIC_PROTOCOL)},
            "recovery_protocol": {"path": RECOVERY_PROTOCOL.relative_to(ROOT).as_posix(), "sha256": sha256(RECOVERY_PROTOCOL)},
            "large_receipt": {"path": LARGE_RECEIPT.relative_to(ROOT).as_posix(), "sha256": sha256(LARGE_RECEIPT)},
        },
        "schedule": {
            "graphs": {key: value for key, value in EXPECTED_DIMENSIONS.items()},
            "retained_cutoff": 0,
            "outer_cutoff": 1,
            "couplings": [str(value) for value in COUPLINGS],
            "rows": 8,
        },
        "checks": [],
        "failures": [],
        "rows": [],
    }
    small_outer_matrix, small_metadata = small_outer(exact, COUPLINGS[0])
    small_space_one = exact.SpectrumSpace(1)
    small_space_zero = exact.SpectrumSpace(0)
    small_zero_state = small_space_zero.states[0]
    check(result, "small source dimensions and retained embedding",
          len(small_space_zero.states) == 1 and len(small_space_one.states) == 4
          and small_zero_state in small_space_one.index,
          {"retained": len(small_space_zero.states), "outer": len(small_space_one.states), "state": list(small_zero_state)})
    large_retained, large_outer_states, large_operator, large_records, large_metadata = large_sources(large)
    large_zero_state = large_retained[0]
    check(result, "large source dimensions and retained embedding",
          len(large_retained) == 1 and len(large_outer_states) == 868
          and large_zero_state in set(large_outer_states)
          and all(value == 0 for value in large_zero_state),
          {"retained": len(large_retained), "outer": len(large_outer_states), "state": list(large_zero_state)})
    check(result, "large recovered plaquette controls",
          len(large_records) == 11
          and all(item["finite"] and item["spectator_channels_preserved"]
                  and item["maximum_hermiticity_residual"] <= MATRIX_TOLERANCE
                  and item["maximum_normalized_column_norm_squared"] <= 4.0 + MATRIX_TOLERANCE
                  for item in large_records),
          {"plaquettes": len(large_records), "records": [
              {key: item[key] for key in ("name", "candidate_entries", "nonzero_entries", "spectator_channels_preserved", "maximum_normalized_column_norm_squared")}
              for item in large_records
          ]})
    small_index = small_space_one.index[small_zero_state]
    large_index = large_outer_states.index(large_zero_state)
    small_cache = {coupling: (small_outer_matrix if coupling == COUPLINGS[0] else small_outer(exact, coupling)[0]) for coupling in COUPLINGS}
    for coupling in COUPLINGS:
        result["rows"].append(feshbach_row(
            "small", coupling, outer_data(small_cache[coupling]), small_index, 1, 4, result))
        large_matrix = large_outer(large, large_outer_states, large_operator, coupling)
        result["rows"].append(feshbach_row(
            "large", coupling, outer_data(large_matrix), large_index, 1, 868, result))
    expected_graphs = {graph: [row for row in result["rows"] if row["graph"] == graph] for graph in EXPECTED_DIMENSIONS}
    check(result, "volume bridge row schedule and summaries",
          len(result["rows"]) == 8
          and all(len(rows) == 4 for rows in expected_graphs.values())
          and {row["coupling"] for row in result["rows"]} == {str(value) for value in COUPLINGS},
          {"rows": len(result["rows"]), "by_graph": {key: len(value) for key, value in expected_graphs.items()}})
    positive_rows = [row for row in result["rows"] if row["certified_gap_lower_bound"] is not None and row["certified_gap_lower_bound"] > 0.0]
    volume_summary: dict[str, Any] = {}
    for coupling in (str(value) for value in COUPLINGS):
        small_row = next(row for row in result["rows"]
                         if row["graph"] == "small" and row["coupling"] == coupling)
        large_row = next(row for row in result["rows"]
                         if row["graph"] == "large" and row["coupling"] == coupling)
        volume_summary[coupling] = {
            "alpha_large_to_small": large_row["alpha_retained"] / small_row["alpha_retained"],
            "delta_large_to_small": large_row["delta_discarded"] / small_row["delta_discarded"],
            "beta_large_to_small": large_row["beta_coupling"] / small_row["beta_coupling"],
        }
    result["volume_summary"] = volume_summary
    result["basis"] = {
        "small": small_metadata,
        "large": large_metadata,
        "large_operator_nnz": int(large_operator.nnz),
    }
    result["large_matrix_records"] = large_records
    result["status"] = "PASS" if not result["failures"] else "FAIL"
    if result["status"] != "PASS":
        result["classification"] = "INCONCLUSIVE"
    elif len(positive_rows) == len(result["rows"]):
        result["classification"] = "SUPPORTS_FINITE_VOLUME_FESHBACH_BRIDGE"
    else:
        result["classification"] = "NO_POSITIVE_FINITE_VOLUME_BRIDGE"
    result["summary"] = {
        "checks": len(result["checks"]),
        "passing_checks": sum(1 for row in result["checks"] if row["passed"]),
        "rows": len(result["rows"]),
        "positive_certified_rows": len(positive_rows),
        "graphs": len(EXPECTED_DIMENSIONS),
        "couplings": len(COUPLINGS),
    }
    result["scope"] = {
        "retained_family": "exact gauge-invariant C=0 constant sector",
        "outer_family": "finite gauge-invariant C=1 source space",
        "volume_uniform_bound": "UNRESOLVED",
        "lattice_spacing_uniform_bound": "UNRESOLVED",
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
    required = (PROTOCOL, SOURCE, INDEPENDENT_SOURCE, EXACT_SOURCE, LARGE_SOURCE, SCIENTIFIC_PROTOCOL, RECOVERY_PROTOCOL, LARGE_RECEIPT)
    if not all(path.exists() for path in required):
        raise FileNotFoundError("protocol, sources, large-volume protocols or receipt is missing")
    inputs = {path: path.read_bytes() for path in required}
    record = build_record(*load_sources())
    if any(path.read_bytes() != content for path, content in inputs.items()):
        raise RuntimeError("input bytes changed during the run; refusing to seal a mixed-source receipt")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(f"Receipt: {output}")
    print(json.dumps({key: record[key] for key in ("status", "classification", "summary", "failures")}, indent=2))
    for row in record["rows"]:
        print(
            "row "
            f"graph={row['graph']} x={row['coupling']} "
            f"alpha={row['alpha_retained']:.12g} "
            f"delta={row['delta_discarded']:.12g} "
            f"beta={row['beta_coupling']:.12g} "
            f"rho={row['self_energy_ratio_at_zero']:.12g} "
            f"phi_zero={row['phi_zero']:.12g} "
            f"root={row['certified_gap_lower_bound']!r}"
        )
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
