#!/usr/bin/env python3
"""Verify finite reflection kernels and fixed-regulator Euclidean controls.

The executable surface checks normalized SU(2) character coefficients, finite
reflection Gram matrices, positive transfer fixtures and implication controls.
The geometric Wilson reflection theorem and the infinite-volume compactness
argument remain analytic parts of the bound protocol.
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
PROTOCOL = ROOT / "computations" / "yang-mills-euclidean-reflection-positive-prereg.md"
SOURCE = Path(__file__).resolve()
DEFAULT_OUTPUT = (
    ROOT / "runs" / "yang_mills_euclidean_reflection_positive" / "verification.json"
)

BETA_VALUES = (0.25, 1.0, 4.0, 16.0)
CHARACTER_CUTOFFS = (4, 8, 16)
SAMPLE_COUNTS = (8, 12, 16)
HAAR_ORDERS = (1, 2, 3, 4, 5, 6)
CLOSURE_INDICES = (1, 2, 4, 8, 16, 32)
SIMPLEX_TIMES = (2, 4, 8, 16, 32)
GAP_SIZES = (8, 16, 32, 64, 128, 256)

PSD_RELATIVE_TOLERANCE = 5.0e-10
PRIMARY_TOLERANCE = 1.0e-11
HAAR_RELATIVE_TOLERANCE = 1.0e-9
EIGEN_SUPPORT_RELATIVE = 1.0e-12
EXPECTED_ROWS = len(BETA_VALUES) * len(CHARACTER_CUTOFFS) * len(SAMPLE_COUNTS)
CHECKS_PER_ROW = 8
EXPECTED_ROW_CHECKS = EXPECTED_ROWS * CHECKS_PER_ROW
EXPECTED_TOP_LEVEL_CHECKS = 20
EXPECTED_CHECKS = EXPECTED_ROW_CHECKS + EXPECTED_TOP_LEVEL_CHECKS


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def relative_error(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), np.finfo(float).tiny)


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


def character_coefficients(beta: float, n_max: int) -> np.ndarray:
    dimensions = np.arange(1, n_max + 1, dtype=float)
    return 2.0 * dimensions * iv(dimensions, beta) / beta


def character_vector(x: float, n_max: int) -> np.ndarray:
    x = min(1.0, max(-1.0, float(x)))
    values = np.empty(n_max, dtype=float)
    values[0] = 1.0
    if n_max >= 2:
        values[1] = 2.0 * x
    for index in range(2, n_max):
        values[index] = 2.0 * x * values[index - 1] - values[index - 2]
    return values


def deterministic_quaternions(count: int) -> np.ndarray:
    rows = []
    for index in range(count):
        step = float(index + 1)
        raw = np.array(
            [
                1.0 + 0.03125 * step,
                math.sin(math.sqrt(2.0) * step) + 0.125 * math.cos(step / 3.0),
                math.cos(math.sqrt(3.0) * step) - 0.1 * math.sin(step / 5.0),
                math.sin(math.sqrt(5.0) * step + 0.375),
            ],
            dtype=float,
        )
        rows.append(raw / np.linalg.norm(raw))
    return np.stack(rows)


def gram_matrix(
    quaternions: np.ndarray, coefficients: np.ndarray
) -> tuple[np.ndarray, float]:
    count = quaternions.shape[0]
    n_max = coefficients.shape[0]
    gram = np.empty((count, count), dtype=float)
    maximum_character_ratio = 0.0
    dimensions = np.arange(1, n_max + 1, dtype=float)
    for left in range(count):
        for right in range(count):
            characters = character_vector(
                float(np.dot(quaternions[left], quaternions[right])), n_max
            )
            maximum_character_ratio = max(
                maximum_character_ratio,
                float(np.max(np.abs(characters) / dimensions)),
            )
            gram[left, right] = float(np.dot(coefficients, characters))
    return gram, maximum_character_ratio


def matrix_metrics(matrix: np.ndarray) -> dict[str, Any]:
    symmetry_residual = float(np.max(np.abs(matrix - matrix.T)))
    symmetric = 0.5 * (matrix + matrix.T)
    eigenvalues = np.linalg.eigvalsh(symmetric)
    spectral_scale = float(max(1.0, np.max(np.abs(eigenvalues))))
    threshold = PSD_RELATIVE_TOLERANCE * spectral_scale
    return {
        "symmetry_residual": symmetry_residual,
        "minimum_eigenvalue": float(eigenvalues[0]),
        "maximum_eigenvalue": float(eigenvalues[-1]),
        "spectral_scale": spectral_scale,
        "psd_threshold": threshold,
        "positive_semidefinite": bool(eigenvalues[0] >= -threshold),
        "eigenvalues": eigenvalues,
    }


def spatial_weights(beta: float, quaternions: np.ndarray) -> np.ndarray:
    return np.exp(0.125 * beta * (quaternions[:, 0] - 1.0))


def build_transfer(beta: float, gram: np.ndarray, quaternions: np.ndarray) -> np.ndarray:
    weights = spatial_weights(beta, quaternions)
    return weights[:, None] * gram * weights[None, :]


def reflection_vectors(count: int) -> list[np.ndarray]:
    vectors = []
    for seed in (1.0, 2.0, 3.0):
        indices = np.arange(1, count + 1, dtype=float)
        vector = np.sin(indices * math.sqrt(seed + 1.0)) + 0.5 * np.cos(
            indices * math.sqrt(seed + 2.0)
        )
        vectors.append(vector / np.linalg.norm(vector))
    return vectors


def kernel_row(beta: float, n_max: int, sample_count: int) -> dict[str, Any]:
    quaternions = deterministic_quaternions(sample_count)
    coefficients = character_coefficients(beta, n_max)
    gram, maximum_character_ratio = gram_matrix(quaternions, coefficients)
    gram_metrics = matrix_metrics(gram)

    quadratic_forms = [float(vector @ gram @ vector) for vector in reflection_vectors(sample_count)]
    quadratic_tolerance = PSD_RELATIVE_TOLERANCE * gram_metrics["spectral_scale"]

    permutation = np.roll(np.arange(sample_count), 1)
    permuted_gram = gram[np.ix_(permutation, permutation)]
    schur = gram * permuted_gram
    schur_metrics = matrix_metrics(schur)

    transfer = build_transfer(beta, gram, quaternions)
    transfer_metrics = matrix_metrics(transfer)
    transfer_eigenvalues = transfer_metrics["eigenvalues"]
    spectral_radius = float(transfer_eigenvalues[-1])
    supported = transfer_eigenvalues[
        transfer_eigenvalues > EIGEN_SUPPORT_RELATIVE * spectral_radius
    ]
    normalized_supported = supported / spectral_radius
    effective_energies = -np.log(normalized_supported)

    checks = [
        check(
            "finite_positive_character_coefficients",
            bool(np.all(np.isfinite(coefficients)) and np.all(coefficients > 0.0)),
            minimum=float(np.min(coefficients)),
            maximum=float(np.max(coefficients)),
        ),
        check(
            "su2_character_bound",
            maximum_character_ratio <= 1.0 + PRIMARY_TOLERANCE,
            maximum_ratio=maximum_character_ratio,
        ),
        check(
            "reflection_gram_symmetry",
            gram_metrics["symmetry_residual"] <= PRIMARY_TOLERANCE * gram_metrics["spectral_scale"],
            residual=gram_metrics["symmetry_residual"],
            scale=gram_metrics["spectral_scale"],
        ),
        check(
            "reflection_gram_positive_semidefinite",
            gram_metrics["positive_semidefinite"],
            minimum_eigenvalue=gram_metrics["minimum_eigenvalue"],
            threshold=gram_metrics["psd_threshold"],
        ),
        check(
            "reflection_quadratic_forms",
            min(quadratic_forms) >= -quadratic_tolerance,
            values=quadratic_forms,
            tolerance=quadratic_tolerance,
        ),
        check(
            "crossing_plaquette_schur_product",
            schur_metrics["positive_semidefinite"],
            minimum_eigenvalue=schur_metrics["minimum_eigenvalue"],
            threshold=schur_metrics["psd_threshold"],
        ),
        check(
            "weighted_transfer_positive_semidefinite",
            transfer_metrics["positive_semidefinite"] and spectral_radius > 0.0,
            minimum_eigenvalue=transfer_metrics["minimum_eigenvalue"],
            spectral_radius=spectral_radius,
            threshold=transfer_metrics["psd_threshold"],
        ),
        check(
            "normalized_transfer_spectrum",
            bool(
                supported.size > 0
                and np.min(normalized_supported) > 0.0
                and np.max(normalized_supported) <= 1.0 + PRIMARY_TOLERANCE
                and np.min(effective_energies) >= -PRIMARY_TOLERANCE
            ),
            supported_eigenvalues=int(supported.size),
            minimum_normalized=float(np.min(normalized_supported)),
            maximum_normalized=float(np.max(normalized_supported)),
            minimum_effective_energy=float(np.min(effective_energies)),
            maximum_effective_energy=float(np.max(effective_energies)),
        ),
    ]

    return {
        "beta": beta,
        "character_cutoff": n_max,
        "sample_count": sample_count,
        "character_coefficients": coefficients.tolist(),
        "maximum_character_ratio": maximum_character_ratio,
        "gram": {
            key: value
            for key, value in gram_metrics.items()
            if key not in {"eigenvalues", "positive_semidefinite"}
        },
        "reflection_quadratic_forms": quadratic_forms,
        "schur": {
            key: value
            for key, value in schur_metrics.items()
            if key not in {"eigenvalues", "positive_semidefinite"}
        },
        "transfer": {
            key: value
            for key, value in transfer_metrics.items()
            if key not in {"eigenvalues", "positive_semidefinite"}
        },
        "transfer_supported_eigenvalues": int(supported.size),
        "minimum_normalized_transfer_eigenvalue": float(np.min(normalized_supported)),
        "maximum_normalized_transfer_eigenvalue": float(np.max(normalized_supported)),
        "minimum_effective_energy": float(np.min(effective_energies)),
        "maximum_effective_energy": float(np.max(effective_energies)),
        "checks": checks,
    }


def haar_fixture() -> dict[str, Any]:
    rows = []
    for beta in BETA_VALUES:
        expected = character_coefficients(beta, max(HAAR_ORDERS))
        for n in HAAR_ORDERS:
            value, quadrature_error = haar_coefficient(beta, n)
            target = float(expected[n - 1])
            rows.append(
                {
                    "beta": beta,
                    "n": n,
                    "haar_value": value,
                    "closed_value": target,
                    "relative_error": relative_error(value, target),
                    "quadrature_error": quadrature_error,
                }
            )
    return {
        "rows": rows,
        "maximum_relative_error": max(item["relative_error"] for item in rows),
        "maximum_quadrature_error": max(item["quadrature_error"] for item in rows),
    }


def base_matrices() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    quaternions = deterministic_quaternions(8)
    coefficients = character_coefficients(1.0, 8)
    gram, _ = gram_matrix(quaternions, coefficients)
    transfer = build_transfer(1.0, gram, quaternions)
    return quaternions, gram, transfer


def weak_limit_closure_fixture(gram: np.ndarray) -> dict[str, Any]:
    rows = []
    for index in CLOSURE_INDICES:
        current = gram + np.eye(gram.shape[0]) / float(index)
        metrics = matrix_metrics(current)
        rows.append(
            {
                "index": index,
                "minimum_eigenvalue": metrics["minimum_eigenvalue"],
                "psd_threshold": metrics["psd_threshold"],
                "positive_semidefinite": metrics["positive_semidefinite"],
                "maximum_entry_distance_to_limit": float(np.max(np.abs(current - gram))),
            }
        )
    distances = [item["maximum_entry_distance_to_limit"] for item in rows]
    passed = all(item["positive_semidefinite"] for item in rows) and all(
        left > right for left, right in zip(distances, distances[1:])
    )
    return {"passed": passed, "rows": rows}


def finite_simplex_fixture(transfer: np.ndarray) -> dict[str, Any]:
    eigenvalues, eigenvectors = np.linalg.eigh(0.5 * (transfer + transfer.T))
    spectral_radius = float(eigenvalues[-1])
    normalized = np.clip(eigenvalues / spectral_radius, 0.0, None)
    rows = []
    for time in SIMPLEX_TIMES:
        powered = (eigenvectors * (normalized**time)) @ eigenvectors.T
        diagonal = np.diag(powered)
        probabilities = diagonal / np.sum(diagonal)
        rows.append(
            {
                "time": time,
                "minimum_probability": float(np.min(probabilities)),
                "maximum_probability": float(np.max(probabilities)),
                "probability_sum": float(np.sum(probabilities)),
            }
        )
    passed = all(
        item["minimum_probability"] >= -PRIMARY_TOLERANCE
        and abs(item["probability_sum"] - 1.0) <= PRIMARY_TOLERANCE
        for item in rows
    )
    return {"passed": passed, "rows": rows}


def negative_coefficient_fixture() -> dict[str, Any]:
    quaternions = deterministic_quaternions(16)
    coefficients = character_coefficients(1.0, 8)
    dimensions = np.arange(1, 9, dtype=float)
    bad = coefficients.copy()
    bad[-1] = -(1.0 + float(np.dot(dimensions[:-1], coefficients[:-1]))) / dimensions[-1]
    gram, _ = gram_matrix(quaternions, bad)
    metrics = matrix_metrics(gram)
    diagonal_error = float(np.max(np.abs(np.diag(gram) + 1.0)))
    return {
        "passed": bool(
            bad[-1] < 0.0
            and diagonal_error <= PRIMARY_TOLERANCE
            and metrics["minimum_eigenvalue"] < -PRIMARY_TOLERANCE
            and not metrics["positive_semidefinite"]
        ),
        "bad_coefficient": float(bad[-1]),
        "maximum_diagonal_error_from_minus_one": diagonal_error,
        "minimum_eigenvalue": metrics["minimum_eigenvalue"],
        "psd_threshold": metrics["psd_threshold"],
    }


def asymmetric_kernel_fixture(gram: np.ndarray) -> dict[str, Any]:
    bad = gram.copy()
    scale = float(max(1.0, np.max(np.abs(gram))))
    bad[0, 1] += 0.125 * scale
    residual = float(np.max(np.abs(bad - bad.T)))
    return {
        "passed": residual > PRIMARY_TOLERANCE * scale,
        "symmetry_residual": residual,
        "scale": scale,
    }


def alternating_sequence_fixture() -> dict[str, Any]:
    zero = np.array([1.0, 0.0])
    one = np.array([0.0, 1.0])
    sequence = [zero if index % 2 == 0 else one for index in range(8)]
    consecutive_l1 = [
        float(np.sum(np.abs(left - right)))
        for left, right in zip(sequence, sequence[1:])
    ]
    even_l1 = [
        float(np.sum(np.abs(sequence[index] - sequence[index + 2])))
        for index in range(0, 6, 2)
    ]
    odd_l1 = [
        float(np.sum(np.abs(sequence[index] - sequence[index + 2])))
        for index in range(1, 6, 2)
    ]
    return {
        "passed": bool(
            all(abs(value - 2.0) <= PRIMARY_TOLERANCE for value in consecutive_l1)
            and all(value <= PRIMARY_TOLERANCE for value in even_l1 + odd_l1)
        ),
        "consecutive_l1": consecutive_l1,
        "even_subsequence_l1": even_l1,
        "odd_subsequence_l1": odd_l1,
    }


def collapsing_gap_fixture() -> dict[str, Any]:
    rows = []
    for size in GAP_SIZES:
        gap = 2.0 - 2.0 * math.cos(2.0 * math.pi / size)
        transfer_eigenvalues = [math.exp(-gap), 1.0]
        rows.append(
            {
                "size": size,
                "gap": gap,
                "transfer_eigenvalues": transfer_eigenvalues,
                "strictly_positive": min(transfer_eigenvalues) > 0.0,
            }
        )
    gaps = [item["gap"] for item in rows]
    passed = (
        all(item["strictly_positive"] for item in rows)
        and all(left > right > 0.0 for left, right in zip(gaps, gaps[1:]))
        and gaps[-1] < 1.0e-3
    )
    return {"passed": passed, "rows": rows}


def run(output: Path, replace: bool) -> dict[str, Any]:
    if output.exists() and not replace:
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")

    rows = [
        kernel_row(beta, n_max, sample_count)
        for beta in BETA_VALUES
        for n_max in CHARACTER_CUTOFFS
        for sample_count in SAMPLE_COUNTS
    ]
    row_checks = [item for current in rows for item in current["checks"]]
    haar = haar_fixture()
    _, base_gram, base_transfer = base_matrices()
    closure = weak_limit_closure_fixture(base_gram)
    simplex = finite_simplex_fixture(base_transfer)
    negative = negative_coefficient_fixture()
    asymmetric = asymmetric_kernel_fixture(base_gram)
    alternating = alternating_sequence_fixture()
    collapsing_gap = collapsing_gap_fixture()

    analytic_inputs = {
        "finite_torus_wilson_reflection_positivity": True,
        "finite_spatial_volume_positive_transfer": True,
        "compact_group_finite_range_gibbs_compactness": True,
        "executable_proof_of_geometric_reflection_factorization": False,
        "infinite_volume_measure_constructed_by_verifier": False,
    }
    boundaries = {
        "full_sequence_convergence_established": False,
        "uniqueness_established": False,
        "clustering_established": False,
        "anisotropic_hamiltonian_equivalence_established": False,
        "continuum_limit_established": False,
        "wightman_reconstruction_established": False,
        "uniform_mass_gap_established": False,
        "clay_verdict": "NULL",
    }

    top_checks = [
        check("schema_contract", True),
        check(
            "protocol_path",
            str(PROTOCOL.relative_to(ROOT)).replace("\\", "/")
            == "computations/yang-mills-euclidean-reflection-positive-prereg.md",
        ),
        check("protocol_hash_available", bool(sha256(PROTOCOL))),
        check(
            "source_path",
            str(SOURCE.relative_to(ROOT)).replace("\\", "/")
            == "computations/verify_yang_mills_euclidean_reflection_positive.py",
        ),
        check("source_hash_available", bool(sha256(SOURCE))),
        check("beta_schedule", BETA_VALUES == (0.25, 1.0, 4.0, 16.0)),
        check("character_cutoff_schedule", CHARACTER_CUTOFFS == (4, 8, 16)),
        check("sample_count_schedule", SAMPLE_COUNTS == (8, 12, 16)),
        check("haar_order_schedule", HAAR_ORDERS == (1, 2, 3, 4, 5, 6)),
        check("row_count", len(rows) == EXPECTED_ROWS, rows=len(rows)),
        check(
            "row_check_count",
            len(row_checks) == EXPECTED_ROW_CHECKS,
            row_checks=len(row_checks),
        ),
        check(
            "normalized_haar_character_coefficients",
            haar["maximum_relative_error"] <= HAAR_RELATIVE_TOLERANCE,
            maximum_relative_error=haar["maximum_relative_error"],
            tolerance=HAAR_RELATIVE_TOLERANCE,
        ),
        check(
            "analytic_inputs_declared",
            analytic_inputs["finite_torus_wilson_reflection_positivity"]
            and analytic_inputs["finite_spatial_volume_positive_transfer"]
            and analytic_inputs["compact_group_finite_range_gibbs_compactness"]
            and not analytic_inputs["executable_proof_of_geometric_reflection_factorization"]
            and not analytic_inputs["infinite_volume_measure_constructed_by_verifier"],
        ),
        check("weak_limit_psd_closure_fixture", closure["passed"]),
        check("finite_probability_simplex_fixture", simplex["passed"]),
        check("negative_character_coefficient_firing", negative["passed"]),
        check("asymmetric_kernel_firing", asymmetric["passed"]),
        check("alternating_sequence_firing", alternating["passed"]),
        check("collapsing_gap_firing", collapsing_gap["passed"]),
        check(
            "implication_boundaries",
            all(value is False for key, value in boundaries.items() if key != "clay_verdict")
            and boundaries["clay_verdict"] == "NULL",
        ),
    ]
    if len(top_checks) != EXPECTED_TOP_LEVEL_CHECKS:
        raise AssertionError("top-level check count drifted from frozen protocol")

    all_checks = top_checks + row_checks
    passed = len(all_checks) == EXPECTED_CHECKS and all(
        bool(item["passed"]) for item in all_checks
    )
    record: dict[str, Any] = {
        "schema": "cassi.yang-mills.euclidean-reflection-positive.v1",
        "verdict": "PASS" if passed else "FAIL",
        "classification": "FIXED_REGULATOR_EUCLIDEAN_REFLECTION_SUPPORT",
        "fixed_regulator_euclidean_support": "PASS" if passed else "FAIL",
        "scope": (
            "Finite normalized-Haar SU(2) reflection kernels, Schur products, weighted positive "
            "transfer fixtures, weak-limit closure fixtures and implication controls supporting "
            "the analytic fixed-regulator Euclidean Gibbs-subsequence theorem. The verifier does "
            "not construct the infinite-volume measure or establish a continuum or mass-gap result."
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
            "character_cutoffs": list(CHARACTER_CUTOFFS),
            "sample_counts": list(SAMPLE_COUNTS),
            "haar_orders": list(HAAR_ORDERS),
            "closure_indices": list(CLOSURE_INDICES),
            "simplex_times": list(SIMPLEX_TIMES),
            "gap_sizes": list(GAP_SIZES),
        },
        "tolerances": {
            "primary": PRIMARY_TOLERANCE,
            "haar_relative": HAAR_RELATIVE_TOLERANCE,
            "psd_relative": PSD_RELATIVE_TOLERANCE,
            "eigen_support_relative": EIGEN_SUPPORT_RELATIVE,
        },
        "normalization": {
            "character_coefficient": "C_n=I_(n-1)-I_(n+1)=2*n*I_n(beta)/beta",
            "convolution_eigenvalue": "r_n=C_n/n=2*I_n(beta)/beta",
            "haar_measure": "(2/pi)*sin(theta)^2*dtheta",
        },
        "analytic_inputs": analytic_inputs,
        "analytic_conclusion": {
            "finite_torus_measure_exists": True,
            "finite_volume_reflection_positivity_analytic_input": True,
            "finite_volume_positive_transfer_analytic_input": True,
            "infinite_volume_subsequence_argument": "ANALYTIC",
            "infinite_volume_measure_constructed_by_verifier": False,
        },
        "boundaries": boundaries,
        "summary": {
            "rows": len(rows),
            "row_checks": len(row_checks),
            "top_level_checks": len(top_checks),
            "checks": len(all_checks),
            "passed": sum(bool(item["passed"]) for item in all_checks),
            "failed": sum(not bool(item["passed"]) for item in all_checks),
        },
        "checks": top_checks,
        "haar_fixture": haar,
        "weak_limit_closure_fixture": closure,
        "finite_simplex_fixture": simplex,
        "negative_coefficient_fixture": negative,
        "asymmetric_kernel_fixture": asymmetric,
        "alternating_sequence_fixture": alternating,
        "collapsing_gap_fixture": collapsing_gap,
        "rows": rows,
    }
    if not finite_payload(record):
        raise FloatingPointError("non-finite Euclidean reflection receipt payload")
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
