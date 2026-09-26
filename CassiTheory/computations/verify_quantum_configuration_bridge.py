#!/usr/bin/env python3
"""Run the frozen quantum-configuration bridge certificates.

Protocol: computations/quantum-configuration-bridge-pre-registration.md
"""

from __future__ import annotations

import math

import numpy as np


TOL = 1.0e-12


def certificate_dq1() -> bool:
    section_jacobian = np.array(
        [
            [1.0 / 4.0, 0.0],
            [0.0, 0.0],
            [0.0, 1.0 / 6.0],
            [0.0, 0.0],
        ]
    )
    symplectic_form = np.array(
        [
            [0.0, 1.0, 0.0, 0.0],
            [-1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
            [0.0, 0.0, -1.0, 0.0],
        ]
    )
    pullback = section_jacobian.T @ symplectic_form @ section_jacobian

    density_jacobian = np.array(
        [
            [4.0, 2.0, 0.0, 0.0],
            [0.0, 0.0, 6.0, 4.0],
        ]
    )
    section_rank = int(np.linalg.matrix_rank(section_jacobian))
    density_rank = int(np.linalg.matrix_rank(density_jacobian))
    density_nullity = density_jacobian.shape[1] - density_rank
    pullback_norm = float(np.linalg.norm(pullback, ord=2))

    passed = (
        section_rank == 2
        and pullback_norm <= TOL
        and density_rank == 2
        and density_nullity == 2
    )
    print(
        "DQ1-CERT",
        "PASS" if passed else "FAIL",
        f"rank(Ds)={section_rank}",
        f"pullback_norm={pullback_norm:.3e}",
        f"rank(Dpi)={density_rank}",
        f"nullity(Dpi)={density_nullity}",
    )
    return passed


def certificate_dq2() -> bool:
    physical_a = 0.5 * (-1.0 - 1.0) ** 2
    fisher_a = (0.5 - 0.5) ** 2 / ((0.5 + 0.5) / 2.0)

    uniform_configurations = np.array([[0.0, 0.0], [1.0, 1.0]])
    weights_b = np.array([0.8, 0.2])
    physical_b = float(
        weights_b
        @ (0.5 * (uniform_configurations[:, 1] - uniform_configurations[:, 0]) ** 2)
    )
    fisher_b = (0.2 - 0.8) ** 2 / ((0.8 + 0.2) / 2.0)

    passed = (
        abs(physical_a - 2.0) <= TOL
        and abs(fisher_a) <= TOL
        and abs(physical_b) <= TOL
        and abs(fisher_b - 0.72) <= TOL
    )
    print(
        "DQ2-CERT",
        "PASS" if passed else "FAIL",
        f"control_A=(Egrad={physical_a:.6f},IF={fisher_a:.6f})",
        f"control_B=(Egrad={physical_b:.6f},IF={fisher_b:.6f})",
    )
    return passed


def certificate_dq3() -> bool:
    a, b, c, hbar = 0.7, 0.4, -0.3, 1.2
    t = 0.37
    points = np.array([-1.1, -0.4, 0.2, 0.9])

    radius = np.exp(-a * points**2 / 2.0)
    radius_x = -a * points * radius
    radius_xx = (a**2 * points**2 - a) * radius
    phase = b * points**2 / 2.0 + c * t
    phase_x = b * points
    phase_xx = np.full_like(points, b)
    potential = 0.15 * points**2
    phase_factor = np.exp(1.0j * phase / hbar)
    psi = radius * phase_factor

    psi_t = 1.0j * c * psi / hbar
    psi_xx = phase_factor * (
        radius_xx
        + 2.0j * radius_x * phase_x / hbar
        + 1.0j * radius * phase_xx / hbar
        - radius * phase_x**2 / hbar**2
    )
    direct = 1.0j * hbar * psi_t + 0.5 * hbar**2 * psi_xx - potential * psi

    continuity = 2.0 * radius * radius_x * phase_x + radius**2 * phase_xx
    hamilton_jacobi = (
        c
        + 0.5 * phase_x**2
        + potential
        - 0.5 * hbar**2 * radius_xx / radius
    )
    composed = phase_factor * (
        -radius * hamilton_jacobi + 1.0j * hbar * continuity / (2.0 * radius)
    )
    residual = float(np.max(np.abs(direct - composed)))

    passed = residual <= TOL
    print(
        "DQ3-CERT",
        "PASS" if passed else "FAIL",
        f"max_identity_residual={residual:.3e}",
    )
    return passed


def certificate_dq4() -> bool:
    x = np.array([-1.1, -0.3, 0.6, 1.2])[:, None]
    y = np.array([-0.9, 0.2, 0.8])[None, :]
    density = np.exp(-(x**2 + y**2))
    k_x = -2.0 * y * density
    k_y = 2.0 * x * density
    divergence = 4.0 * x * y * density - 4.0 * x * y * density
    velocity_difference = np.sqrt((k_x / density) ** 2 + (k_y / density) ** 2)

    divergence_residual = float(np.max(np.abs(divergence)))
    minimum_velocity_difference = float(np.min(velocity_difference))
    passed = divergence_residual <= TOL and minimum_velocity_difference > 0.0
    print(
        "DQ4-CERT",
        "PASS" if passed else "FAIL",
        f"divergence_residual={divergence_residual:.3e}",
        f"min_|v1-v0|={minimum_velocity_difference:.6f}",
    )
    return passed


def certificate_dq5() -> bool:
    count = 128
    index = np.arange(count)
    equilibrium = 1.0 + 0.2 * np.cos(2.0 * math.pi * index / count)
    equilibrium /= equilibrium.sum()
    preparation = equilibrium * (1.0 + 0.3 * np.sin(4.0 * math.pi * index / count))
    preparation /= preparation.sum()

    kl_before = float(np.sum(preparation * np.log(preparation / equilibrium)))
    transported_preparation = np.roll(preparation, 37)
    transported_equilibrium = np.roll(equilibrium, 37)
    kl_after = float(
        np.sum(transported_preparation * np.log(transported_preparation / transported_equilibrium))
    )
    ratio_before = preparation / equilibrium
    ratio_after = np.roll(transported_preparation / transported_equilibrium, -37)
    kl_change = abs(kl_after - kl_before)
    ratio_change = float(np.max(np.abs(ratio_after - ratio_before)))

    passed = kl_before > 0.0 and kl_change <= TOL and ratio_change <= TOL
    print(
        "DQ5-CERT",
        "PASS" if passed else "FAIL",
        f"KL_before={kl_before:.12e}",
        f"KL_change={kl_change:.3e}",
        f"ratio_change={ratio_change:.3e}",
    )
    return passed


def partial_trace_b(density_matrix: np.ndarray) -> np.ndarray:
    """Trace subsystem B from a two-qubit density matrix."""
    return np.trace(density_matrix.reshape(2, 2, 2, 2), axis1=1, axis2=3)


def certificate_dq6() -> bool:
    sigma_x = np.array([[0.0, 1.0], [1.0, 0.0]])
    sigma_z = np.array([[1.0, 0.0], [0.0, -1.0]])
    bell_state = np.array([1.0, 0.0, 0.0, 1.0]) / math.sqrt(2.0)

    b_0 = (sigma_z + sigma_x) / math.sqrt(2.0)
    b_1 = (sigma_z - sigma_x) / math.sqrt(2.0)
    bell_operator = np.kron(sigma_z, b_0 + b_1) + np.kron(sigma_x, b_0 - b_1)
    expectation = float(bell_state @ bell_operator @ bell_state)
    operator_norm = float(np.linalg.norm(bell_operator, ord=2))

    density_matrix = np.outer(bell_state, bell_state)
    local_unitary = np.array([[1.0, 1.0], [1.0, -1.0]]) / math.sqrt(2.0)
    transformed_state = np.kron(np.eye(2), local_unitary) @ bell_state
    transformed_density = np.outer(transformed_state, transformed_state)
    reduced_change = float(
        np.max(np.abs(partial_trace_b(transformed_density) - partial_trace_b(density_matrix)))
    )

    target = 2.0 * math.sqrt(2.0)
    passed = (
        abs(expectation - target) <= TOL
        and abs(operator_norm - target) <= TOL
        and reduced_change <= TOL
    )
    print(
        "DQ6-CERT",
        "PASS" if passed else "FAIL",
        f"CHSH={expectation:.12f}",
        f"operator_norm={operator_norm:.12f}",
        f"remote_change={reduced_change:.3e}",
    )
    return passed


def certificate_dq8() -> bool:
    counts = np.array([16, 32, 64, 128], dtype=float)
    spacing = 2.0 * math.pi / counts
    eigenvalues = 4.0 * np.sin(spacing / 2.0) ** 2 / spacing**2
    errors = np.abs(eigenvalues - 1.0)
    orders = np.log(errors[:-1] / errors[1:]) / math.log(2.0)
    minimum_order = float(np.min(orders))

    passed = minimum_order > 1.9
    print(
        "DQ8-CERT",
        "PASS" if passed else "FAIL",
        "errors=" + ",".join(f"{error:.6e}" for error in errors),
        "orders=" + ",".join(f"{order:.6f}" for order in orders),
    )
    return passed


def main() -> int:
    certificates = [
        certificate_dq1(),
        certificate_dq2(),
        certificate_dq3(),
        certificate_dq4(),
        certificate_dq5(),
        certificate_dq6(),
        certificate_dq8(),
    ]
    if all(certificates):
        print("ALL DECLARED CERTIFICATES PASSED")
        return 0
    print("DECLARED CERTIFICATES FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
