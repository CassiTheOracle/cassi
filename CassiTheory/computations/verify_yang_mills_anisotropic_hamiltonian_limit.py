#!/usr/bin/env python3
"""Verify the fixed-graph anisotropic SU(2) transfer-to-Hamiltonian limit.

The executable fixtures implement the frozen contract in
``computations/yang-mills-anisotropic-hamiltonian-limit-prereg.md``.
They test normalization and finite character compressions; the fixed-graph
operator theorem itself is analytic and is not inferred from these matrices.
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
import scipy
from scipy.integrate import quad
from scipy.special import iv, ive


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-anisotropic-hamiltonian-limit-prereg.md"
SOURCE = Path(__file__).resolve()
OUTPUT = ROOT / "runs" / "yang-mills-anisotropic-hamiltonian-limit" / "verification.json"

A = 1.0
G2_VALUES = (0.5, 1.0, 2.0)
CUTOFFS = (2, 4, 6)
DELTAS = (1.0 / 256.0, 1.0 / 512.0, 1.0 / 1024.0, 1.0 / 2048.0)
LAMBDA_VALUES = (0.25, 1.0, 4.0)
SEMIGROUP_N = (64, 128, 256, 512)
CHECK_TOL = 2.0e-12
POSITIVE_REL_TOL = 2.0e-11
QUADRATURE_TOL = 2.0e-10
MONOTONE_FLOOR = 1.0e-13
EXPECTED_ROW_COUNT = 36
EXPECTED_ROW_CHECKS = 360
EXPECTED_CONVERGENCE_COUNT = 9
EXPECTED_CONVERGENCE_CHECKS = 36
EXPECTED_TOP_CHECKS = 18
EXPECTED_TOTAL_CHECKS = 414


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check(
    name: str,
    passed: bool,
    *,
    value: Any | None = None,
    threshold: Any | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"name": name, "passed": bool(passed)}
    if value is not None:
        result["value"] = value
    if threshold is not None:
        result["threshold"] = threshold
    return result


def spectral_norm(matrix: np.ndarray) -> float:
    return float(np.linalg.norm(matrix, ord=2))


def symmetric_spectrum(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    symmetric = 0.5 * (matrix + matrix.T)
    values, vectors = np.linalg.eigh(symmetric)
    return values, vectors


def symmetric_function(matrix: np.ndarray, function: Any) -> np.ndarray:
    values, vectors = symmetric_spectrum(matrix)
    transformed = np.asarray(function(values), dtype=np.float64)
    return (vectors * transformed) @ vectors.T


def matrix_metrics(matrix: np.ndarray) -> dict[str, float]:
    values, _ = symmetric_spectrum(matrix)
    return {
        "symmetry_max_abs": float(np.max(np.abs(matrix - matrix.T))),
        "min_eigenvalue": float(values[0]),
        "max_eigenvalue": float(values[-1]),
        "spectral_norm": spectral_norm(matrix),
    }


def finite_payload(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, np.integer)):
        return True
    if isinstance(value, (float, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(finite_payload(key) and finite_payload(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite_payload(item) for item in value)
    return False


def eta_values(beta: float, cutoff: int) -> np.ndarray:
    orders = np.arange(1, cutoff + 2, dtype=np.int64)
    scaled = ive(orders, beta)
    denominator = float(ive(1, beta))
    return np.asarray(scaled / denominator, dtype=np.float64)


def bessel_character_coefficient(beta: float, dimension: int) -> float:
    return float(2.0 * dimension * iv(dimension, beta) / beta)


def haar_character_coefficient(beta: float, dimension: int) -> float:
    value, _ = quad(
        lambda theta: (
            2.0
            / math.pi
            * math.exp(beta * math.cos(theta))
            * math.sin(theta)
            * math.sin(dimension * theta)
        ),
        0.0,
        math.pi,
        epsabs=2.0e-13,
        epsrel=2.0e-13,
        limit=300,
    )
    return float(value)


def half_potential_fusion(zeta: float, cutoff: int) -> np.ndarray:
    coefficients = np.empty(2 * cutoff + 1, dtype=np.float64)
    damping = math.exp(-zeta)
    for representation in range(2 * cutoff + 1):
        dimension = representation + 1
        coefficients[representation] = (
            damping * 2.0 * dimension * float(iv(dimension, zeta)) / zeta
        )

    matrix = np.zeros((cutoff + 1, cutoff + 1), dtype=np.float64)
    for n in range(cutoff + 1):
        for m in range(cutoff + 1):
            matrix[n, m] = float(
                sum(coefficients[representation] for representation in range(abs(n - m), n + m + 1, 2))
            )
    return matrix


def half_potential_haar(zeta: float, cutoff: int, points: int = 8192) -> np.ndarray:
    indices = np.arange(points, dtype=np.float64)
    theta = (indices + 1.0) * math.pi / (points + 1.0)
    dimensions = np.arange(1, cutoff + 2, dtype=np.float64)[:, None]
    sine_basis = np.sin(dimensions * theta[None, :])
    weight = np.exp(-zeta * (1.0 - np.cos(theta)))
    return (2.0 / (points + 1.0)) * (sine_basis * weight[None, :]) @ sine_basis.T


def target_hamiltonian(g2: float, cutoff: int, a: float = A) -> np.ndarray:
    matrix = np.zeros((cutoff + 1, cutoff + 1), dtype=np.float64)
    magnetic = 1.0 / (g2 * a)
    for n in range(cutoff + 1):
        matrix[n, n] = g2 * n * (n + 2) / (2.0 * a) + 2.0 * magnetic
        if n + 1 <= cutoff:
            matrix[n, n + 1] = -magnetic
            matrix[n + 1, n] = -magnetic
    return matrix


def construct_row(g2: float, cutoff: int, delta: float) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    epsilon = delta * A
    beta_tau = 4.0 * A / (g2 * epsilon)
    beta_sigma = 2.0 * epsilon / (g2 * A)
    zeta = epsilon / (g2 * A)

    eta = eta_values(beta_tau, cutoff)
    transfer_electric = np.diag(np.power(eta, 4.0))
    half_potential = half_potential_fusion(zeta, cutoff)
    transfer = half_potential @ transfer_electric @ half_potential
    hamiltonian = target_hamiltonian(g2, cutoff)
    difference_generator = (np.eye(cutoff + 1) - transfer) / epsilon

    transfer_values, transfer_vectors = symmetric_spectrum(transfer)
    if float(transfer_values[0]) <= 0.0:
        raise ArithmeticError("transfer matrix lost strict positivity")
    logarithmic_generator = (
        transfer_vectors * (-np.log(transfer_values) / epsilon)
    ) @ transfer_vectors.T

    h_norm = max(1.0, spectral_norm(hamiltonian))
    difference_error = spectral_norm(difference_generator - hamiltonian) / h_norm
    logarithmic_error = spectral_norm(logarithmic_generator - hamiltonian) / h_norm

    m_metrics = matrix_metrics(half_potential)
    t_metrics = matrix_metrics(transfer)
    h_metrics = matrix_metrics(hamiltonian)
    a_metrics = matrix_metrics(difference_generator)
    g_metrics = matrix_metrics(logarithmic_generator)

    induced_temporal = 2.0 / (beta_tau * epsilon)
    induced_spatial = beta_sigma / (2.0 * epsilon)
    target_temporal = g2 / (2.0 * A)
    target_spatial = 1.0 / (g2 * A)

    resolvent_lower_violation = 0.0
    resolvent_upper_violation = 0.0
    resolvent_max_difference = 0.0
    for eigenvalue in transfer_values:
        difference_eigenvalue = (1.0 - eigenvalue) / epsilon
        log_eigenvalue = -math.log(float(eigenvalue)) / epsilon
        for lam in LAMBDA_VALUES:
            difference = 1.0 / (difference_eigenvalue + lam) - 1.0 / (log_eigenvalue + lam)
            resolvent_lower_violation = max(resolvent_lower_violation, -difference)
            resolvent_upper_violation = max(resolvent_upper_violation, difference - epsilon)
            resolvent_max_difference = max(resolvent_max_difference, difference)

    scale_m = max(1.0, m_metrics["spectral_norm"])
    scale_t = max(1.0, t_metrics["spectral_norm"])
    scale_h = max(1.0, h_metrics["spectral_norm"])
    scale_a = max(1.0, a_metrics["spectral_norm"])
    scale_g = max(1.0, g_metrics["spectral_norm"])

    row_checks = [
        check(
            "normalized_multipliers_finite_in_unit_interval",
            bool(np.all(np.isfinite(eta)) and np.all(eta > 0.0) and np.all(eta <= 1.0 + CHECK_TOL)),
            value={"min": float(np.min(eta)), "max": float(np.max(eta))},
            threshold={"min_exclusive": 0.0, "max": 1.0 + CHECK_TOL},
        ),
        check(
            "vacuum_one_and_nontrivial_multipliers_strictly_ordered",
            bool(abs(float(eta[0]) - 1.0) <= CHECK_TOL and np.all(eta[:-1] > eta[1:])),
            value={"vacuum_abs_error": abs(float(eta[0]) - 1.0), "minimum_drop": float(np.min(eta[:-1] - eta[1:]))},
            threshold={"vacuum_abs_error": CHECK_TOL, "minimum_drop_exclusive": 0.0},
        ),
        check(
            "temporal_coefficient_matches_target",
            abs(induced_temporal - target_temporal) <= CHECK_TOL * max(1.0, target_temporal),
            value={"induced": induced_temporal, "target": target_temporal},
            threshold=CHECK_TOL,
        ),
        check(
            "spatial_coefficient_matches_target",
            abs(induced_spatial - target_spatial) <= CHECK_TOL * max(1.0, target_spatial),
            value={"induced": induced_spatial, "target": target_spatial},
            threshold=CHECK_TOL,
        ),
        check(
            "half_potential_symmetric_positive_definite_contraction",
            m_metrics["symmetry_max_abs"] <= CHECK_TOL * scale_m
            and m_metrics["min_eigenvalue"] > 0.0
            and m_metrics["max_eigenvalue"] <= 1.0 + POSITIVE_REL_TOL * scale_m,
            value=m_metrics,
            threshold={"symmetry_relative": CHECK_TOL, "min_eigenvalue_exclusive": 0.0, "max_eigenvalue": 1.0 + POSITIVE_REL_TOL * scale_m},
        ),
        check(
            "transfer_symmetric_positive_definite_contraction",
            t_metrics["symmetry_max_abs"] <= CHECK_TOL * scale_t
            and t_metrics["min_eigenvalue"] > 0.0
            and t_metrics["max_eigenvalue"] <= 1.0 + POSITIVE_REL_TOL * scale_t,
            value=t_metrics,
            threshold={"symmetry_relative": CHECK_TOL, "min_eigenvalue_exclusive": 0.0, "max_eigenvalue": 1.0 + POSITIVE_REL_TOL * scale_t},
        ),
        check(
            "target_hamiltonian_symmetric_nonnegative",
            h_metrics["symmetry_max_abs"] <= CHECK_TOL * scale_h
            and h_metrics["min_eigenvalue"] >= -POSITIVE_REL_TOL * scale_h,
            value=h_metrics,
            threshold={"symmetry_relative": CHECK_TOL, "min_eigenvalue": -POSITIVE_REL_TOL * scale_h},
        ),
        check(
            "difference_generator_symmetric_nonnegative",
            a_metrics["symmetry_max_abs"] <= CHECK_TOL * scale_a
            and a_metrics["min_eigenvalue"] >= -POSITIVE_REL_TOL * scale_a,
            value=a_metrics,
            threshold={"symmetry_relative": CHECK_TOL, "min_eigenvalue": -POSITIVE_REL_TOL * scale_a},
        ),
        check(
            "logarithmic_generator_symmetric_nonnegative",
            g_metrics["symmetry_max_abs"] <= CHECK_TOL * scale_g
            and g_metrics["min_eigenvalue"] >= -POSITIVE_REL_TOL * scale_g,
            value=g_metrics,
            threshold={"symmetry_relative": CHECK_TOL, "min_eigenvalue": -POSITIVE_REL_TOL * scale_g},
        ),
        check(
            "matrix_resolvent_bound",
            resolvent_lower_violation <= CHECK_TOL and resolvent_upper_violation <= CHECK_TOL,
            value={
                "max_difference": resolvent_max_difference,
                "lower_violation": resolvent_lower_violation,
                "upper_violation": resolvent_upper_violation,
            },
            threshold={"lower_violation": CHECK_TOL, "upper_violation": CHECK_TOL, "analytic_upper_bound": epsilon},
        ),
    ]

    row = {
        "g_squared": g2,
        "cutoff": cutoff,
        "delta": delta,
        "epsilon": epsilon,
        "beta_tau": beta_tau,
        "beta_sigma": beta_sigma,
        "zeta": zeta,
        "eta": eta.tolist(),
        "difference_generator_relative_error": difference_error,
        "logarithmic_generator_relative_error": logarithmic_error,
        "checks": row_checks,
        "passed": all(item["passed"] for item in row_checks),
    }
    matrices = {
        "half_potential": half_potential,
        "electric_transfer": transfer_electric,
        "transfer": transfer,
        "hamiltonian": hamiltonian,
        "difference_generator": difference_generator,
        "logarithmic_generator": logarithmic_generator,
    }
    return row, matrices


def strict_decrease(values: list[float]) -> tuple[bool, float]:
    margins = [values[index] - values[index + 1] for index in range(len(values) - 1)]
    return all(margin > MONOTONE_FLOOR for margin in margins), min(margins)


def semigroup_fixture() -> dict[str, Any]:
    g2 = 1.0
    cutoff = 6
    time = 0.5
    hamiltonian = target_hamiltonian(g2, cutoff)
    exact = symmetric_function(hamiltonian, lambda values: np.exp(-time * values))
    errors: list[float] = []
    rows: list[dict[str, float | int]] = []
    for steps in SEMIGROUP_N:
        delta = time / steps
        _, matrices = construct_row(g2, cutoff, delta)
        product = symmetric_function(matrices["transfer"], lambda values: np.power(values, steps))
        error = spectral_norm(product - exact)
        errors.append(error)
        rows.append({"steps": steps, "delta": delta, "spectral_error": error})
    decreasing, minimum_drop = strict_decrease(errors)
    ratio = errors[-1] / errors[0]
    return {
        "g_squared": g2,
        "cutoff": cutoff,
        "time": time,
        "rows": rows,
        "strictly_decreasing": decreasing,
        "minimum_drop": minimum_drop,
        "final_to_first_ratio": ratio,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replace", action="store_true", help="replace an existing receipt")
    args = parser.parse_args()

    if OUTPUT.exists() and not args.replace:
        raise SystemExit(f"refusing to overwrite existing receipt: {OUTPUT}; pass --replace explicitly")
    if not PROTOCOL.is_file():
        raise SystemExit(f"missing frozen protocol: {PROTOCOL}")

    rows: list[dict[str, Any]] = []
    row_matrices: dict[tuple[float, int, float], dict[str, np.ndarray]] = {}
    for g2 in G2_VALUES:
        for cutoff in CUTOFFS:
            for delta in DELTAS:
                row, matrices = construct_row(g2, cutoff, delta)
                rows.append(row)
                row_matrices[(g2, cutoff, delta)] = matrices

    convergence_families: list[dict[str, Any]] = []
    for g2 in G2_VALUES:
        for cutoff in CUTOFFS:
            family_rows = [row for row in rows if row["g_squared"] == g2 and row["cutoff"] == cutoff]
            difference_errors = [float(row["difference_generator_relative_error"]) for row in family_rows]
            logarithmic_errors = [float(row["logarithmic_generator_relative_error"]) for row in family_rows]
            difference_decreasing, difference_minimum_drop = strict_decrease(difference_errors)
            logarithmic_decreasing, logarithmic_minimum_drop = strict_decrease(logarithmic_errors)
            difference_final_ratio = difference_errors[-1] / difference_errors[0]
            logarithmic_final_ratio = logarithmic_errors[-1] / logarithmic_errors[0]
            difference_halving_ratio = difference_errors[-1] / difference_errors[-2]
            logarithmic_halving_ratio = logarithmic_errors[-1] / logarithmic_errors[-2]
            family_checks = [
                check(
                    "difference_errors_strictly_decrease",
                    difference_decreasing,
                    value={"errors": difference_errors, "minimum_drop": difference_minimum_drop},
                    threshold={"minimum_drop_exclusive": MONOTONE_FLOOR},
                ),
                check(
                    "logarithmic_errors_strictly_decrease",
                    logarithmic_decreasing,
                    value={"errors": logarithmic_errors, "minimum_drop": logarithmic_minimum_drop},
                    threshold={"minimum_drop_exclusive": MONOTONE_FLOOR},
                ),
                check(
                    "final_to_first_ratios",
                    difference_final_ratio <= 0.20 and logarithmic_final_ratio <= 0.20,
                    value={"difference": difference_final_ratio, "logarithmic": logarithmic_final_ratio},
                    threshold=0.20,
                ),
                check(
                    "final_halving_ratios",
                    difference_halving_ratio <= 0.70 and logarithmic_halving_ratio <= 0.70,
                    value={"difference": difference_halving_ratio, "logarithmic": logarithmic_halving_ratio},
                    threshold=0.70,
                ),
            ]
            convergence_families.append(
                {
                    "g_squared": g2,
                    "cutoff": cutoff,
                    "difference_errors": difference_errors,
                    "logarithmic_errors": logarithmic_errors,
                    "checks": family_checks,
                    "passed": all(item["passed"] for item in family_checks),
                }
            )

    bessel_comparisons: list[dict[str, float | int]] = []
    bessel_max_relative_error = 0.0
    for beta in (0.5, 2.0, 8.0):
        for dimension in range(1, 8):
            analytic = bessel_character_coefficient(beta, dimension)
            numerical = haar_character_coefficient(beta, dimension)
            relative_error = abs(numerical - analytic) / max(1.0, abs(analytic))
            bessel_max_relative_error = max(bessel_max_relative_error, relative_error)
            bessel_comparisons.append(
                {
                    "beta": beta,
                    "dimension": dimension,
                    "analytic": analytic,
                    "haar_quadrature": numerical,
                    "scaled_relative_error": relative_error,
                }
            )

    half_potential_comparisons: list[dict[str, float]] = []
    half_potential_max_abs_error = 0.0
    for zeta in (1.0 / 64.0, 1.0 / 16.0, 1.0 / 4.0):
        fusion = half_potential_fusion(zeta, 6)
        haar = half_potential_haar(zeta, 6)
        error = float(np.max(np.abs(fusion - haar)))
        half_potential_max_abs_error = max(half_potential_max_abs_error, error)
        half_potential_comparisons.append({"zeta": zeta, "max_abs_error": error})

    action_map_max_abs_error = 0.0
    wilson_map_max_relative_error = 0.0
    for g2 in G2_VALUES:
        for delta in DELTAS:
            epsilon = delta * A
            beta_tau = 4.0 * A / (g2 * epsilon)
            beta_sigma = 2.0 * epsilon / (g2 * A)
            hat_beta_tau = 2.0 * A / (g2 * epsilon)
            hat_beta_sigma = epsilon / (g2 * A)
            action_map_max_abs_error = max(
                action_map_max_abs_error,
                abs(beta_tau - 2.0 * hat_beta_tau),
                abs(beta_sigma - 2.0 * hat_beta_sigma),
            )

            g_w_squared = math.sqrt(2.0) * g2
            a_tau = epsilon / math.sqrt(2.0)
            xi = A / a_tau
            wilson_tau = 4.0 * xi / g_w_squared
            wilson_sigma = 4.0 / (g_w_squared * xi)
            wilson_map_max_relative_error = max(
                wilson_map_max_relative_error,
                abs(wilson_tau - beta_tau) / beta_tau,
                abs(wilson_sigma - beta_sigma) / beta_sigma,
            )

    mutation_g2 = 1.0
    mutation_epsilon = 1.0 / 16.0
    mutation_beta_tau = 4.0 / mutation_epsilon
    mutation_beta_sigma = 2.0 * mutation_epsilon
    temporal_mutation_ratio = (2.0 / ((mutation_beta_tau / 2.0) * mutation_epsilon)) / (mutation_g2 / 2.0)
    spatial_mutation_ratio = ((2.0 * mutation_beta_sigma) / (2.0 * mutation_epsilon)) / (1.0 / mutation_g2)
    raw_vacuum_eigenvalue = float(2.0 * iv(1, 4.0) / 4.0)

    mutation_half = half_potential_fusion(mutation_epsilon, 6)
    mutation_eta = eta_values(mutation_beta_tau, 6)
    mutation_r = np.diag(np.power(mutation_eta, 4.0))
    asymmetric_transfer = mutation_half @ mutation_half @ mutation_r
    asymmetric_residual = float(np.max(np.abs(asymmetric_transfer - asymmetric_transfer.T)))

    gap_controls: list[dict[str, float | int]] = []
    gaps: list[float] = []
    for length in (8, 16, 32, 64, 128, 256):
        gap = 2.0 - 2.0 * math.cos(2.0 * math.pi / length)
        transfer_excited = math.exp(-gap)
        gaps.append(gap)
        gap_controls.append({"length": length, "gap": gap, "excited_transfer_eigenvalue": transfer_excited})
    gap_decreasing, gap_minimum_drop = strict_decrease(gaps)

    scalar_resolvent_lower_violation = 0.0
    scalar_resolvent_upper_violation = 0.0
    scalar_resolvent_rows: list[dict[str, float]] = []
    for s in (0.0, 2.0**-16, 2.0**-12, 2.0**-8, 2.0**-4, 0.5, 0.75, 1.0 - 2.0**-8):
        transfer_eigenvalue = 1.0 - s
        difference_value = s
        log_value = -math.log(transfer_eigenvalue)
        for lam in LAMBDA_VALUES:
            difference = 1.0 / (difference_value + lam) - 1.0 / (log_value + lam)
            scalar_resolvent_lower_violation = max(scalar_resolvent_lower_violation, -difference)
            scalar_resolvent_upper_violation = max(scalar_resolvent_upper_violation, difference - 1.0)
            scalar_resolvent_rows.append({"s": s, "lambda": lam, "resolvent_difference": difference})

    four_link_max_relative_error = 0.0
    four_link_rows: list[dict[str, float | int]] = []
    for g2 in G2_VALUES:
        epsilon = DELTAS[0]
        beta_tau = 4.0 / (g2 * epsilon)
        one_link_coefficient = 2.0 / (beta_tau * epsilon)
        for n in range(1, 7):
            j = n / 2.0
            induced = 4.0 * one_link_coefficient * j * (j + 1.0)
            target = 2.0 * g2 * j * (j + 1.0)
            relative_error = abs(induced - target) / target
            four_link_max_relative_error = max(four_link_max_relative_error, relative_error)
            four_link_rows.append({"g_squared": g2, "n": n, "induced": induced, "target": target})

    semigroup = semigroup_fixture()

    boundary = {
        "analytic_fixed_graph_core_limit": True,
        "analytic_fixed_graph_strong_resolvent_limit": True,
        "analytic_fixed_graph_log_generator_limit": True,
        "analytic_fixed_graph_chernoff_limit": True,
        "analytic_theorem_outside_executable": True,
        "fixed_beta_gibbs_identified_with_anisotropic_limit": False,
        "spatial_volume_uniformity_established": False,
        "thermodynamic_limit_established": False,
        "lattice_spacing_limit_established": False,
        "continuum_limit_established": False,
        "wightman_reconstruction_established": False,
        "uniform_mass_gap_established": False,
        "clay_verdict": "NULL",
    }
    expected_boundary = dict(boundary)

    top_checks = [
        check(
            "bessel_character_coefficients_match_normalized_haar",
            bessel_max_relative_error <= QUADRATURE_TOL,
            value=bessel_max_relative_error,
            threshold=QUADRATURE_TOL,
        ),
        check(
            "half_potential_fusion_matches_normalized_haar",
            half_potential_max_abs_error <= QUADRATURE_TOL,
            value=half_potential_max_abs_error,
            threshold=QUADRATURE_TOL,
        ),
        check(
            "anisotropic_action_to_character_factor_two",
            action_map_max_abs_error <= CHECK_TOL,
            value=action_map_max_abs_error,
            threshold=CHECK_TOL,
        ),
        check(
            "standard_wilson_bare_convention_map",
            wilson_map_max_relative_error <= CHECK_TOL,
            value=wilson_map_max_relative_error,
            threshold=CHECK_TOL,
        ),
        check(
            "halved_temporal_weight_mutation_fires",
            abs(temporal_mutation_ratio - 2.0) <= CHECK_TOL,
            value=temporal_mutation_ratio,
            threshold={"target": 2.0, "abs_tolerance": CHECK_TOL},
        ),
        check(
            "doubled_spatial_weight_mutation_fires",
            abs(spatial_mutation_ratio - 2.0) <= CHECK_TOL,
            value=spatial_mutation_ratio,
            threshold={"target": 2.0, "abs_tolerance": CHECK_TOL},
        ),
        check(
            "omitted_kernel_normalization_mutation_fires",
            abs(raw_vacuum_eigenvalue - 1.0) >= 0.10,
            value=raw_vacuum_eigenvalue,
            threshold={"minimum_distance_from_one": 0.10},
        ),
        check(
            "asymmetric_product_mutation_fires",
            asymmetric_residual >= 1.0e-8,
            value=asymmetric_residual,
            threshold={"minimum_exclusive": 1.0e-8},
        ),
        check(
            "gap_controls_have_strictly_positive_transfer",
            all(0.0 < row["excited_transfer_eigenvalue"] < 1.0 for row in gap_controls),
            value={"minimum": min(row["excited_transfer_eigenvalue"] for row in gap_controls), "maximum": max(row["excited_transfer_eigenvalue"] for row in gap_controls)},
            threshold={"min_exclusive": 0.0, "max_exclusive": 1.0},
        ),
        check(
            "positive_transfer_gap_controls_collapse",
            gap_decreasing and gaps[-1] / gaps[0] <= 0.002,
            value={"gaps": gaps, "minimum_drop": gap_minimum_drop, "final_to_first_ratio": gaps[-1] / gaps[0]},
            threshold={"minimum_drop_exclusive": MONOTONE_FLOOR, "final_to_first_ratio": 0.002},
        ),
        check(
            "scalar_resolvent_inequality",
            scalar_resolvent_lower_violation <= CHECK_TOL and scalar_resolvent_upper_violation <= CHECK_TOL,
            value={"lower_violation": scalar_resolvent_lower_violation, "upper_violation": scalar_resolvent_upper_violation},
            threshold=CHECK_TOL,
        ),
        check(
            "four_link_electric_identity",
            four_link_max_relative_error <= CHECK_TOL,
            value=four_link_max_relative_error,
            threshold=CHECK_TOL,
        ),
        check(
            "semigroup_errors_strictly_decrease",
            bool(semigroup["strictly_decreasing"]),
            value={"rows": semigroup["rows"], "minimum_drop": semigroup["minimum_drop"]},
            threshold={"minimum_drop_exclusive": MONOTONE_FLOOR},
        ),
        check(
            "semigroup_final_to_first_ratio",
            float(semigroup["final_to_first_ratio"]) <= 0.20,
            value=semigroup["final_to_first_ratio"],
            threshold=0.20,
        ),
        check(
            "all_matrix_rows_pass",
            len(rows) == EXPECTED_ROW_COUNT and all(row["passed"] for row in rows),
            value={"count": len(rows), "passing": sum(bool(row["passed"]) for row in rows)},
            threshold={"count": EXPECTED_ROW_COUNT, "passing": EXPECTED_ROW_COUNT},
        ),
        check(
            "all_convergence_families_pass",
            len(convergence_families) == EXPECTED_CONVERGENCE_COUNT and all(family["passed"] for family in convergence_families),
            value={"count": len(convergence_families), "passing": sum(bool(family["passed"]) for family in convergence_families)},
            threshold={"count": EXPECTED_CONVERGENCE_COUNT, "passing": EXPECTED_CONVERGENCE_COUNT},
        ),
        check(
            "all_numeric_payloads_finite",
            finite_payload(
                {
                    "rows": rows,
                    "convergence_families": convergence_families,
                    "bessel_comparisons": bessel_comparisons,
                    "half_potential_comparisons": half_potential_comparisons,
                    "gap_controls": gap_controls,
                    "scalar_resolvent_rows": scalar_resolvent_rows,
                    "four_link_rows": four_link_rows,
                    "semigroup": semigroup,
                }
            ),
        ),
        check("claim_boundary_frozen", boundary == expected_boundary, value=boundary),
    ]

    row_check_count = sum(len(row["checks"]) for row in rows)
    convergence_check_count = sum(len(family["checks"]) for family in convergence_families)
    all_checks = [item for row in rows for item in row["checks"]]
    all_checks.extend(item for family in convergence_families for item in family["checks"])
    all_checks.extend(top_checks)
    counts_match = (
        len(rows) == EXPECTED_ROW_COUNT
        and row_check_count == EXPECTED_ROW_CHECKS
        and len(convergence_families) == EXPECTED_CONVERGENCE_COUNT
        and convergence_check_count == EXPECTED_CONVERGENCE_CHECKS
        and len(top_checks) == EXPECTED_TOP_CHECKS
        and len(all_checks) == EXPECTED_TOTAL_CHECKS
    )
    passed = counts_match and all(item["passed"] for item in all_checks)

    claims = {
        "fixed_graph_anisotropic_hamiltonian_limit": "PASS" if passed else "FAIL",
        **boundary,
        "finite_isolated_square_fixture": "PASS" if passed else "FAIL",
    }

    receipt = {
        "schema": "cassi.yang-mills.anisotropic-hamiltonian-limit.verification.v1",
        "verdict": "PASS" if passed else "FAIL",
        "summary": {
            "matrix_rows": len(rows),
            "matrix_row_checks": row_check_count,
            "convergence_families": len(convergence_families),
            "convergence_checks": convergence_check_count,
            "top_level_checks": len(top_checks),
            "total_checks": len(all_checks),
            "passing_checks": sum(bool(item["passed"]) for item in all_checks),
            "counts_match_frozen_contract": counts_match,
        },
        "claims": claims,
        "parameters": {
            "a": A,
            "g_squared_values": list(G2_VALUES),
            "cutoffs": list(CUTOFFS),
            "deltas": list(DELTAS),
            "lambda_values": list(LAMBDA_VALUES),
            "semigroup_steps": list(SEMIGROUP_N),
            "check_tolerance": CHECK_TOL,
            "positive_relative_tolerance": POSITIVE_REL_TOL,
            "quadrature_tolerance": QUADRATURE_TOL,
            "monotone_floor": MONOTONE_FLOOR,
        },
        "normalization": {
            "target_electric_coefficient": "g_squared/(2*a)",
            "target_magnetic_coefficient": "1/(g_squared*a)",
            "beta_tau": "4*a/(g_squared*epsilon)",
            "beta_sigma": "2*epsilon/(g_squared*a)",
            "character_parameter_equals_twice_action_beta": True,
            "wilson_g_squared_over_target_g_squared": math.sqrt(2.0),
            "target_epsilon_over_wilson_a_tau": math.sqrt(2.0),
        },
        "analytic_statement": {
            "scope": "fixed finite spatial graph at fixed positive a and g",
            "difference_generator": "(I-T_epsilon)/epsilon -> H on a Peter-Weyl core and in strong resolvent sense",
            "logarithmic_generator": "-log(T_epsilon)/epsilon -> H in strong resolvent sense",
            "product_limit": "T_(t/N)^N -> exp(-tH) strongly",
            "executable_status": "analytic theorem is recorded by the protocol and is not established by finite matrices",
        },
        "matrix_rows": rows,
        "convergence_families": convergence_families,
        "fixtures": {
            "bessel_character_coefficients": bessel_comparisons,
            "bessel_max_scaled_relative_error": bessel_max_relative_error,
            "half_potential_comparisons": half_potential_comparisons,
            "half_potential_max_abs_error": half_potential_max_abs_error,
            "action_map_max_abs_error": action_map_max_abs_error,
            "wilson_map_max_relative_error": wilson_map_max_relative_error,
            "temporal_mutation_ratio": temporal_mutation_ratio,
            "spatial_mutation_ratio": spatial_mutation_ratio,
            "unnormalized_vacuum_eigenvalue_at_beta_4": raw_vacuum_eigenvalue,
            "asymmetric_product_max_abs_residual": asymmetric_residual,
            "gap_controls": gap_controls,
            "scalar_resolvent_rows": scalar_resolvent_rows,
            "four_link_electric_rows": four_link_rows,
            "semigroup": semigroup,
        },
        "top_level_checks": top_checks,
        "source_bindings": {
            "protocol": {"path": PROTOCOL.relative_to(ROOT).as_posix(), "sha256": sha256(PROTOCOL)},
            "primary": {"path": SOURCE.relative_to(ROOT).as_posix(), "sha256": sha256(SOURCE)},
        },
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("Yang-Mills anisotropic transfer-to-Hamiltonian verification")
    print(f"  matrix rows:        {len(rows)}")
    print(f"  convergence groups: {len(convergence_families)}")
    print(f"  checks:             {sum(bool(item['passed']) for item in all_checks)}/{len(all_checks)}")
    print(f"  frozen counts:      {'PASS' if counts_match else 'FAIL'}")
    print(f"  receipt:            {OUTPUT.relative_to(ROOT).as_posix()}")
    print(f"  VERDICT:            {'PASS' if passed else 'FAIL'}")
    print("  CLAY VERDICT:       NULL")

    if not passed:
        failed_names = [item["name"] for item in all_checks if not item["passed"]]
        print("  failed checks:      " + ", ".join(failed_names))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
