#!/usr/bin/env python3
"""Measure the pre-registered volume-adapted local-plaquette Feshbach family."""
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
PROTOCOL = ROOT / "computations/yang-mills-volume-adapted-feshbach-prereg.md"
INDEPENDENT_SOURCE = ROOT / "computations/verify_yang_mills_volume_adapted_feshbach_independent.py"
VOLUME_BRIDGE_SOURCE = ROOT / "computations/verify_yang_mills_volume_feshbach_bridge.py"
EXACT_SOURCE = ROOT / "computations/verify_yang_mills_exact_block_spectrum.py"
LARGE_SOURCE = ROOT / "computations/verify_yang_mills_su2_larger_volume_hamiltonian.py"
SCIENTIFIC_PROTOCOL = ROOT / "computations/yang-mills-su2-larger-volume-hamiltonian-prereg.md"
RECOVERY_PROTOCOL = ROOT / "computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md"
LARGE_RECEIPT = ROOT / "runs/yang_mills_su2_larger_volume_hamiltonian_recovery/verification.json"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_volume_adapted_feshbach/verification.json"

COUPLINGS = (Fraction(1, 64), Fraction(1, 16), Fraction(1, 4), Fraction(1))
EXPECTED_DIMENSIONS = {"small": 4, "large": 868}
GROUND_RESIDUAL_TOLERANCE = 1.0e-11
INEQUALITY_RELATIVE_TOLERANCE = 1.0e-10
INEQUALITY_ABSOLUTE_TOLERANCE = 1.0e-12
FESHBACH_ABSOLUTE_TOLERANCE = 1.0e-10
FRAME_TOLERANCE = 1.0e-10
TAIL_FLOOR_TOLERANCE = 1.0e-9
MATRIX_TOLERANCE = 1.0e-10


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def json_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, separators=(",", ":"), sort_keys=False).encode("utf-8")).hexdigest()


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load source: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
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


def orthonormal_range(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    left, singular, _ = np.linalg.svd(np.asarray(matrix, dtype=float), full_matrices=False)
    if singular.size == 0 or singular[0] <= 0.0:
        return np.zeros((matrix.shape[0], 0), dtype=float), singular, 0
    rank = int(np.count_nonzero(singular > FRAME_TOLERANCE * singular[0]))
    return left[:, :rank], singular, rank


def small_plaquette_matrices(exact: Any, states: tuple[Any, ...]) -> list[np.ndarray]:
    matrices = []
    for plaquette in range(len(exact.PLAQUETTES)):
        matrix = np.asarray([
            [float(np.real(exact.state_overlap(left, right, loops=(plaquette,)))) for right in states]
            for left in states
        ], dtype=float)
        matrices.append(matrix)
    return matrices


def large_source_with_plaquettes(large: Any) -> tuple[tuple[Any, ...], csr_matrix, list[dict[str, Any]], list[csr_matrix]]:
    states = tuple(large.basis_states(1))
    operator = csr_matrix((len(states), len(states)), dtype=complex)
    records: list[dict[str, Any]] = []
    matrices: list[csr_matrix] = []
    for word in large.PLAQUETTES:
        evaluated = large.evaluate_plaquette(states, {}, {}, word, 1)
        matrix = evaluated.pop("matrix")
        operator = (operator + matrix).tocsr()
        records.append(evaluated)
        matrices.append(matrix)
    operator.sum_duplicates()
    operator.sort_indices()
    return states, operator, records, matrices


def normalized_local_vectors(states: tuple[Any, ...], plaquette_matrices: list[np.ndarray], overlap_diag: np.ndarray, vacuum_index: int) -> tuple[np.ndarray, dict[str, Any]]:
    inverse_sqrt = 1.0 / np.sqrt(np.asarray(overlap_diag, dtype=float))
    vacuum = np.zeros(len(states), dtype=float)
    vacuum[vacuum_index] = 1.0
    vectors = [vacuum]
    for matrix in plaquette_matrices:
        vectors.append(inverse_sqrt * matrix @ (inverse_sqrt * vacuum))
    columns = np.column_stack(vectors)
    frame, singular, rank = orthonormal_range(columns)
    return columns, {
        "plaquettes": len(plaquette_matrices),
        "column_count": int(columns.shape[1]),
        "rank": rank,
        "singular_values": [float(value) for value in singular],
        "vector_sha256": array_sha256(columns),
        "frame_sha256": array_sha256(frame),
    }


def local_source_data(exact: Any, large: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    small_space = exact.SpectrumSpace(1)
    small_states = tuple(small_space.states)
    small_vacuum = small_states.index(exact.SpectrumSpace(0).states[0])
    small_matrices = small_plaquette_matrices(exact, small_states)
    small_overlap = np.diag(small_space.overlap).astype(float)
    small_columns, small_rank = normalized_local_vectors(small_states, small_matrices, small_overlap, small_vacuum)

    large_states, large_operator, large_records, large_matrices_sparse = large_source_with_plaquettes(large)
    large_vacuum = large_states.index(tuple(0 for _ in range(24)))
    large_matrices = [np.asarray(matrix.toarray().real, dtype=float) for matrix in large_matrices_sparse]
    large_overlap = np.asarray([large.state_norm(state) for state in large_states], dtype=float)
    large_columns, large_rank = normalized_local_vectors(large_states, large_matrices, large_overlap, large_vacuum)

    small_meta = {
        "states": [list(state) for state in small_states],
        "vacuum_index": small_vacuum,
        "state_sha256": json_sha256([list(state) for state in small_states]),
        "overlap_diag_sha256": array_sha256(small_overlap),
        "plaquette_matrix_sha256": [array_sha256(matrix) for matrix in small_matrices],
        "local": small_rank,
    }
    large_meta = {
        "states": [list(state) for state in large_states],
        "vacuum_index": large_vacuum,
        "state_sha256": large.basis_hash(large_states),
        "overlap_diag_sha256": array_sha256(large_overlap),
        "plaquette_matrix_sha256": [array_sha256(matrix) for matrix in large_matrices],
        "local": large_rank,
        "operator_nnz": int(large_operator.nnz),
    }
    matrices = {
        "small": small_matrices,
        "large": large_matrices_sparse,
        "large_operator": large_operator,
        "small_columns": small_columns,
        "large_columns": large_columns,
        "small_overlap": small_overlap,
        "large_overlap": large_overlap,
        "small_space": small_space,
        "large_states": large_states,
        "large_records": large_records,
    }
    return small_meta, large_meta, matrices


def feshbach_row(
    graph: str,
    coupling: Fraction,
    matrix: np.ndarray,
    source_columns: np.ndarray,
    source_meta: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    dimension = matrix.shape[0]
    values, vectors = eigh(matrix)
    energy = float(values[0])
    omega = np.asarray(vectors[:, 0], dtype=float)
    omega /= np.linalg.norm(omega)
    if omega[np.argmax(np.abs(omega))] < 0.0:
        omega = -omega
    ground_residual = float(np.linalg.norm(matrix @ omega - energy * omega))
    finite_gap = float(values[1] - energy)
    projected = source_columns - np.outer(omega, omega @ source_columns)
    retained_frame, projected_singular, retained_rank = orthonormal_range(projected)
    discarded_frame = null_space(np.vstack((omega[None, :], retained_frame.T)), rcond=FRAME_TOLERANCE)
    if discarded_frame.shape[1] == 0:
        label = str(coupling)
        prefix = f"graph={graph},x={label}"
        row = {
            "graph": graph,
            "coupling": label,
            "x": float(coupling),
            "full_dimension": int(dimension),
            "plaquette_count": int(source_meta["plaquettes"]),
            "retained_source_column_count": int(source_meta["column_count"]),
            "retained_source_rank": int(source_meta["rank"]),
            "retained_dimension": int(retained_rank),
            "discarded_dimension": 0,
            "source_singular_values": [float(value) for value in source_meta["singular_values"]],
            "projected_source_singular_values": [float(value) for value in projected_singular],
            "ground_energy": energy,
            "ground_residual": ground_residual,
            "finite_gap": finite_gap,
            "outer_matrix_sha256": array_sha256(matrix),
            "failure": "empty_discarded_sector",
        }
        check(result, f"{prefix}:nonempty discarded sector", False,
              {"retained_rank": retained_rank, "full_dimension": dimension})
        return row
    shifted = matrix - energy * np.eye(dimension, dtype=float)
    retained_block = retained_frame.T @ shifted @ retained_frame
    coupling_block = retained_frame.T @ shifted @ discarded_frame
    discarded_block = discarded_frame.T @ shifted @ discarded_frame
    retained_values = eigh(retained_block, eigvals_only=True)
    discarded_values, discarded_vectors = eigh(discarded_block)
    alpha = float(retained_values[0])
    delta = float(discarded_values[0])
    beta = float(np.linalg.norm(coupling_block, ord=2))
    lambda_test = 0.5 * min(finite_gap, delta)
    resolvent_denominators = discarded_values - lambda_test
    resolvent_norm = float(1.0 / np.min(resolvent_denominators))
    resolvent_bound = float(1.0 / (delta - lambda_test))
    resolvent = (discarded_vectors * (1.0 / resolvent_denominators)) @ discarded_vectors.T
    self_energy = coupling_block @ resolvent @ coupling_block.T
    self_energy = 0.5 * (self_energy + self_energy.T)
    self_energy_norm = float(np.linalg.norm(self_energy, ord=2))
    self_energy_bound = float(beta * beta / (delta - lambda_test))
    schur = retained_block - lambda_test * np.eye(retained_rank) - self_energy
    feshbach_minimum = float(np.min(eigh(schur, eigvals_only=True)))
    phi_test = float(alpha - lambda_test - self_energy_bound)
    phi_zero = float(alpha - beta * beta / delta)
    certified_gap = None
    if phi_zero > 0.0:
        discriminant = (alpha - delta) ** 2 + 4.0 * beta * beta
        certified_gap = float(0.5 * (alpha + delta - math.sqrt(discriminant)))
    tail_floor_distance = float(np.min(np.abs(discarded_values - delta)))
    label = str(coupling)
    prefix = f"graph={graph},x={label}"
    row = {
        "graph": graph,
        "coupling": label,
        "x": float(coupling),
        "full_dimension": int(dimension),
        "plaquette_count": int(source_meta["plaquettes"]),
        "retained_source_column_count": int(source_meta["column_count"]),
        "retained_source_rank": int(source_meta["rank"]),
        "retained_dimension": int(retained_rank),
        "discarded_dimension": int(discarded_frame.shape[1]),
        "source_singular_values": [float(value) for value in source_meta["singular_values"]],
        "projected_source_singular_values": [float(value) for value in projected_singular],
        "ground_energy": energy,
        "ground_residual": ground_residual,
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
        "outer_matrix_sha256": array_sha256(matrix),
    }
    check(result, f"{prefix}:dimensions and projected ranks",
          dimension == EXPECTED_DIMENSIONS[graph]
          and row["retained_source_rank"] == source_meta["rank"]
          and retained_rank <= source_meta["rank"]
          and retained_rank > 0
          and discarded_frame.shape[1] == dimension - retained_rank - 1,
          {key: row[key] for key in ("full_dimension", "retained_source_rank", "retained_dimension", "discarded_dimension")})
    check(result, f"{prefix}:normalized Hamiltonian finite and Hermitian",
          bool(np.all(np.isfinite(matrix)))
          and float(np.max(np.abs(matrix - matrix.T))) <= MATRIX_TOLERANCE,
          {"hermiticity_residual": float(np.max(np.abs(matrix - matrix.T)))})
    check(result, f"{prefix}:ground residual and positive gap",
          ground_residual <= GROUND_RESIDUAL_TOLERANCE and finite_gap > 0.0,
          {"ground_residual": ground_residual, "gap": finite_gap})
    check(result, f"{prefix}:positive floors and test domain",
          alpha > 0.0 and delta > 0.0 and 0.0 <= lambda_test < delta,
          {"alpha": alpha, "delta": delta, "lambda_test": lambda_test})
    check(result, f"{prefix}:discarded resolvent bound",
          inequality_pass(resolvent_norm, resolvent_bound),
          {"actual": resolvent_norm, "bound": resolvent_bound})
    check(result, f"{prefix}:Feshbach self-energy bound",
          inequality_pass(self_energy_norm, self_energy_bound),
          {"actual": self_energy_norm, "bound": self_energy_bound})
    check(result, f"{prefix}:direct Schur lower bound",
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
          {"distance_to_tail_floor": tail_floor_distance, "resolvent_defined": row["tail_floor_resolvent_defined"]})
    return row


def build_record(bridge: Any, exact: Any, large: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "cassi.yang-mills.volume-adapted-feshbach.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "protocol": {"path": PROTOCOL.relative_to(ROOT).as_posix(), "sha256": sha256(PROTOCOL)},
            "source": {"path": SOURCE.relative_to(ROOT).as_posix(), "sha256": sha256(SOURCE)},
            "independent_source": {"path": INDEPENDENT_SOURCE.relative_to(ROOT).as_posix(), "sha256": sha256(INDEPENDENT_SOURCE)},
            "volume_bridge_source": {"path": VOLUME_BRIDGE_SOURCE.relative_to(ROOT).as_posix(), "sha256": sha256(VOLUME_BRIDGE_SOURCE)},
            "exact_source": {"path": EXACT_SOURCE.relative_to(ROOT).as_posix(), "sha256": sha256(EXACT_SOURCE)},
            "large_source": {"path": LARGE_SOURCE.relative_to(ROOT).as_posix(), "sha256": sha256(LARGE_SOURCE)},
            "scientific_protocol": {"path": SCIENTIFIC_PROTOCOL.relative_to(ROOT).as_posix(), "sha256": sha256(SCIENTIFIC_PROTOCOL)},
            "recovery_protocol": {"path": RECOVERY_PROTOCOL.relative_to(ROOT).as_posix(), "sha256": sha256(RECOVERY_PROTOCOL)},
            "large_receipt": {"path": LARGE_RECEIPT.relative_to(ROOT).as_posix(), "sha256": sha256(LARGE_RECEIPT)},
        },
        "schedule": {
            "graphs": {"small": EXPECTED_DIMENSIONS["small"], "large": EXPECTED_DIMENSIONS["large"]},
            "retained_family": "vacuum plus every fundamental plaquette action",
            "couplings": [str(value) for value in COUPLINGS],
            "rows": 8,
        },
        "checks": [],
        "failures": [],
        "rows": [],
    }
    small_meta, large_meta, data = local_source_data(exact, large)
    small_space = data["small_space"]
    small_matrices = data["small"]
    large_states = data["large_states"]
    large_matrices = data["large"]
    large_operator = data["large_operator"]
    check(result, "small source dimensions and local family",
          len(small_space.states) == 4
          and len(small_matrices) == len(exact.PLAQUETTES)
          and small_meta["local"]["rank"] > 0
          and all(np.isfinite(matrix).all() for matrix in small_matrices),
          {"dimension": len(small_space.states), "plaquettes": len(small_matrices), "local": small_meta["local"]})
    check(result, "small plaquette decomposition",
          np.max(np.abs(sum(small_matrices) - small_space.plaquette_matrix)) <= MATRIX_TOLERANCE,
          {"residual": float(np.max(np.abs(sum(small_matrices) - small_space.plaquette_matrix)))})
    check(result, "large source dimensions and local family",
          len(large_states) == EXPECTED_DIMENSIONS["large"]
          and len(large_matrices) == len(large.PLAQUETTES)
          and large_meta["local"]["rank"] > 0
          and all(np.isfinite(matrix.data.real).all() and np.isfinite(matrix.data.imag).all() for matrix in large_matrices),
          {"dimension": len(large_states), "plaquettes": len(large_matrices), "local": large_meta["local"]})
    large_sum = sum((matrix for matrix in large_matrices), csr_matrix(large_operator.shape, dtype=complex)).tocsr()
    large_sum.sum_duplicates()
    operator_residual = large_sum - large_operator
    check(result, "large plaquette decomposition",
          operator_residual.nnz == 0 or float(np.max(np.abs(operator_residual.data))) <= MATRIX_TOLERANCE,
          {"residual": 0.0 if operator_residual.nnz == 0 else float(np.max(np.abs(operator_residual.data)))})
    check(result, "local retained source dimensions are frozen",
          small_meta["local"]["column_count"] == 1 + len(small_matrices)
          and large_meta["local"]["column_count"] == 1 + len(large_matrices),
          {"small": small_meta["local"]["column_count"], "large": large_meta["local"]["column_count"]})
    result["source_basis"] = {"small": small_meta, "large": large_meta}
    small_cache = {coupling: bridge.small_outer(exact, coupling)[0] for coupling in COUPLINGS}
    for coupling in COUPLINGS:
        result["rows"].append(feshbach_row(
            "small", coupling, small_cache[coupling], data["small_columns"], small_meta["local"], result))
        large_matrix = bridge.large_outer(large, large_states, large_operator, coupling)
        result["rows"].append(feshbach_row(
            "large", coupling, large_matrix, data["large_columns"], large_meta["local"], result))
    expected_pairs = {(graph, str(coupling)) for graph in EXPECTED_DIMENSIONS for coupling in COUPLINGS}
    observed_pairs = {(row["graph"], row["coupling"]) for row in result["rows"]}
    check(result, "volume-adapted row schedule",
          len(result["rows"]) == 8 and observed_pairs == expected_pairs,
          {"rows": len(result["rows"]), "observed": sorted(observed_pairs)})
    volume_summary: dict[str, Any] = {}
    for coupling in (str(value) for value in COUPLINGS):
        small_row = next(row for row in result["rows"]
                         if row["graph"] == "small" and row["coupling"] == coupling)
        large_row = next(row for row in result["rows"]
                         if row["graph"] == "large" and row["coupling"] == coupling)
        summary_row: dict[str, float | None] = {}
        for key, field in (
            ("alpha_large_to_small", "alpha_retained"),
            ("delta_large_to_small", "delta_discarded"),
            ("beta_large_to_small", "beta_coupling"),
        ):
            numerator = large_row.get(field)
            denominator = small_row.get(field)
            summary_row[key] = None if numerator is None or denominator is None else numerator / denominator
        volume_summary[coupling] = summary_row
    result["volume_summary"] = volume_summary
    positive_rows = [
        row for row in result["rows"]
        if row.get("certified_gap_lower_bound") is not None
        and row["certified_gap_lower_bound"] > 0.0
    ]
    result["status"] = "PASS" if not result["failures"] else "FAIL"
    if result["status"] != "PASS":
        result["classification"] = "INCONCLUSIVE"
    elif len(positive_rows) == len(result["rows"]):
        result["classification"] = "SUPPORTS_FINITE_VOLUME_VOLUME_ADAPTED_FAMILY"
    else:
        result["classification"] = "NO_POSITIVE_VOLUME_ADAPTED_FAMILY"
    result["summary"] = {
        "checks": len(result["checks"]),
        "passing_checks": sum(1 for row in result["checks"] if row["passed"]),
        "rows": len(result["rows"]),
        "positive_certified_rows": len(positive_rows),
        "graphs": 2,
        "couplings": len(COUPLINGS),
    }
    result["scope"] = {
        "retained_family": "vacuum plus exact fundamental plaquette actions",
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
    required = (PROTOCOL, SOURCE, INDEPENDENT_SOURCE, VOLUME_BRIDGE_SOURCE, EXACT_SOURCE, LARGE_SOURCE, SCIENTIFIC_PROTOCOL, RECOVERY_PROTOCOL, LARGE_RECEIPT)
    if not all(path.exists() for path in required):
        raise FileNotFoundError("protocol, sources, large-volume protocols or receipt is missing")
    input_bytes = {path: path.read_bytes() for path in required}
    bridge = load_module("verify_yang_mills_volume_feshbach_bridge", VOLUME_BRIDGE_SOURCE)
    exact, large = bridge.load_sources()
    record = build_record(bridge, exact, large)
    if any(path.read_bytes() != content for path, content in input_bytes.items()):
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
            f"source_rank={row['retained_source_rank']} "
            f"P={row['retained_dimension']} Q={row['discarded_dimension']} "
            f"alpha={row.get('alpha_retained')!r} "
            f"delta={row.get('delta_discarded')!r} "
            f"beta={row.get('beta_coupling')!r} "
            f"rho={row.get('self_energy_ratio_at_zero')!r} "
            f"phi_zero={row.get('phi_zero')!r} "
            f"root={row.get('certified_gap_lower_bound')!r}"
        )
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
