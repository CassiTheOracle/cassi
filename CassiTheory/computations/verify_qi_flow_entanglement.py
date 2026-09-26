#!/usr/bin/env python3
"""Verify the frozen Qi-flow entanglement relations.

Protocol: computations/qi-flow-entanglement-pre-registration.md
"""

from __future__ import annotations

import math

import numpy as np


TOL = 1.0e-12


def normalize(state: np.ndarray) -> np.ndarray:
    return state / np.linalg.norm(state)


def density_factorization_residual(state: np.ndarray) -> float:
    probability = np.abs(state) ** 2
    marginal_a = probability.sum(axis=1)
    marginal_b = probability.sum(axis=0)
    return float(np.max(np.abs(probability - np.outer(marginal_a, marginal_b))))


def mutual_information(state: np.ndarray) -> float:
    probability = np.abs(state) ** 2
    marginal_a = probability.sum(axis=1)
    marginal_b = probability.sum(axis=0)
    product = np.outer(marginal_a, marginal_b)
    mask = probability > 0.0
    return float(np.sum(probability[mask] * np.log(probability[mask] / product[mask])))


def second_schmidt_coefficient(state: np.ndarray) -> float:
    return float(np.linalg.svd(state, compute_uv=False)[1])


def gate_gqe1() -> bool:
    x = np.linspace(-1.5, 1.5, 7)
    y = x.copy()
    x_grid, y_grid = np.meshgrid(x, y, indexing="ij")

    envelope_a = np.exp(-0.5 * x**2)
    envelope_b = np.exp(-0.75 * y**2)
    product_state = normalize(np.outer(envelope_a, envelope_b).astype(np.complex128))

    chi = 0.4
    phase_surface = chi * x_grid * y_grid
    phase_state = normalize(product_state * np.exp(1.0j * phase_surface))
    velocity_x = np.gradient(phase_surface, x, axis=0, edge_order=2)
    velocity_y = np.gradient(phase_surface, y, axis=1, edge_order=2)
    phase_cross_yx = np.gradient(velocity_x, y, axis=1, edge_order=2)
    phase_cross_xy = np.gradient(velocity_y, x, axis=0, edge_order=2)
    phase_cross_residual = float(
        max(
            np.max(np.abs(phase_cross_yx - chi)),
            np.max(np.abs(phase_cross_xy - chi)),
        )
    )

    kappa = 0.35
    amplitude_state = normalize(
        np.exp(-0.5 * (x_grid**2 + y_grid**2 + 2.0 * kappa * x_grid * y_grid))
        .astype(np.complex128)
    )
    derivative_x = np.gradient(amplitude_state, x, axis=0, edge_order=2)
    derivative_y = np.gradient(amplitude_state, y, axis=1, edge_order=2)
    amplitude_current = float(
        max(
            np.max(np.abs(np.imag(amplitude_state.conj() * derivative_x))),
            np.max(np.abs(np.imag(amplitude_state.conj() * derivative_y))),
        )
    )
    log_density = np.log(np.abs(amplitude_state) ** 2)
    mixed_log_density = np.gradient(
        np.gradient(log_density, x, axis=0, edge_order=2),
        y,
        axis=1,
        edge_order=2,
    )
    amplitude_cross_residual = float(np.max(np.abs(mixed_log_density + 2.0 * kappa)))

    product_s2 = second_schmidt_coefficient(product_state)
    product_density_residual = density_factorization_residual(product_state)
    phase_s2 = second_schmidt_coefficient(phase_state)
    phase_density_residual = density_factorization_residual(phase_state)
    amplitude_s2 = second_schmidt_coefficient(amplitude_state)
    amplitude_information = mutual_information(amplitude_state)

    passed = (
        product_s2 <= TOL
        and product_density_residual <= TOL
        and phase_density_residual <= TOL
        and phase_s2 > 1.0e-3
        and phase_cross_residual <= TOL
        and amplitude_s2 > 1.0e-3
        and amplitude_information > 1.0e-3
        and amplitude_current <= TOL
        and amplitude_cross_residual <= TOL
    )
    print(
        "GQE1",
        "PASS" if passed else "FAIL",
        f"product_s2={product_s2:.3e}",
        f"product_rho_residual={product_density_residual:.3e}",
        f"phase_s2={phase_s2:.6e}",
        f"phase_rho_residual={phase_density_residual:.3e}",
        f"phase_cross_residual={phase_cross_residual:.3e}",
        f"amplitude_s2={amplitude_s2:.6e}",
        f"mutual_information={amplitude_information:.6e}",
        f"amplitude_current={amplitude_current:.3e}",
        f"amplitude_cross_residual={amplitude_cross_residual:.3e}",
    )
    return passed


def oscillator_entanglement(omega: float, coupling: float) -> tuple[float, float, float]:
    omega_plus = omega
    omega_minus = math.sqrt(omega**2 + 2.0 * coupling)
    nu = 0.25 * math.sqrt(
        (omega_plus + omega_minus) * (1.0 / omega_plus + 1.0 / omega_minus)
    )
    purity = 1.0 / (2.0 * nu)
    occupation = max(nu - 0.5, 0.0)
    entropy = 0.0 if occupation <= TOL else (
        (occupation + 1.0) * math.log(occupation + 1.0)
        - occupation * math.log(occupation)
    )
    return nu, purity, entropy


def covariance_symplectic_eigenvalue(omega: float, coupling: float) -> float:
    stiffness = np.array(
        [
            [omega**2 + coupling, -coupling],
            [-coupling, omega**2 + coupling],
        ]
    )
    eigenvalues, eigenvectors = np.linalg.eigh(stiffness)
    position_covariance = (
        eigenvectors @ np.diag(0.5 / np.sqrt(eigenvalues)) @ eigenvectors.T
    )
    momentum_covariance = (
        eigenvectors @ np.diag(0.5 * np.sqrt(eigenvalues)) @ eigenvectors.T
    )
    return float(
        math.sqrt(position_covariance[0, 0] * momentum_covariance[0, 0])
    )


def gate_gqe2() -> bool:
    control_nu, control_purity, control_entropy = oscillator_entanglement(1.0, 0.0)
    linked_nu, linked_purity, linked_entropy = oscillator_entanglement(1.0, 1.5)
    control_covariance_nu = covariance_symplectic_eigenvalue(1.0, 0.0)
    linked_covariance_nu = covariance_symplectic_eigenvalue(1.0, 1.5)
    covariance_residual = max(
        abs(control_covariance_nu - control_nu),
        abs(linked_covariance_nu - linked_nu),
    )

    passed = (
        abs(control_nu - 0.5) <= TOL
        and abs(control_purity - 1.0) <= TOL
        and abs(control_entropy) <= TOL
        and covariance_residual <= TOL
        and linked_nu > 0.5
        and linked_purity < 0.99
        and linked_entropy > 0.05
    )
    print(
        "GQE2",
        "PASS" if passed else "FAIL",
        f"control_nu={control_nu:.12f}",
        f"control_purity={control_purity:.12f}",
        f"control_entropy={control_entropy:.3e}",
        f"linked_nu={linked_nu:.12f}",
        f"linked_purity={linked_purity:.12f}",
        f"linked_entropy={linked_entropy:.12f}",
        f"covariance_residual={covariance_residual:.3e}",
    )
    return passed


def gate_gqe3() -> bool:
    projection = np.array([[1.0, 0.0], [0.0, 0.5], [0.0, 0.0]])
    coupling = 0.8
    singular_values = np.linalg.svd(-coupling * projection, compute_uv=False)
    expected = np.array([0.8, 0.4])
    singular_residual = float(np.max(np.abs(singular_values - expected)))
    rank = int(np.linalg.matrix_rank(-coupling * projection, tol=TOL))

    passed = singular_residual <= TOL and rank == 2
    print(
        "GQE3",
        "PASS" if passed else "FAIL",
        f"singular_values={singular_values.tolist()}",
        f"singular_residual={singular_residual:.3e}",
        f"rank={rank}",
    )
    return passed


def gate_gqe4() -> bool:
    coupling = 0.7
    hamiltonian = np.zeros((4, 4), dtype=np.complex128)
    hamiltonian[1, 2] = -coupling
    hamiltonian[2, 1] = -coupling
    initial = np.array([0.0, 0.0, 1.0, 0.0], dtype=np.complex128)
    time = math.pi / (4.0 * coupling)

    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    evolved = eigenvectors @ (
        np.exp(-1.0j * eigenvalues * time) * (eigenvectors.conj().T @ initial)
    )
    norm_residual = abs(float(np.vdot(evolved, evolved).real) - 1.0)

    amplitude_b = evolved[1]
    amplitude_a = evolved[2]
    concurrence = 2.0 * abs(amplitude_a * amplitude_b)
    exchange_current = 2.0 * coupling * abs(
        float(np.imag(amplitude_a.conj() * amplitude_b))
    )

    density = np.outer(evolved, evolved.conj()).reshape(2, 2, 2, 2)
    reduced_a = np.trace(density, axis1=1, axis2=3)
    reduced_purity = float(np.trace(reduced_a @ reduced_a).real)

    passed = (
        norm_residual <= TOL
        and abs(concurrence - 1.0) <= TOL
        and abs(exchange_current / coupling - 1.0) <= TOL
        and abs(reduced_purity - 0.5) <= TOL
    )
    print(
        "GQE4",
        "PASS" if passed else "FAIL",
        f"norm_residual={norm_residual:.3e}",
        f"concurrence={concurrence:.12f}",
        f"current_over_link_coupling={exchange_current / coupling:.12f}",
        f"reduced_purity={reduced_purity:.12f}",
    )
    return passed


def main() -> int:
    gates = [gate_gqe1(), gate_gqe2(), gate_gqe3(), gate_gqe4()]
    if all(gates):
        print("ALL CHECKS PASSED")
        return 0
    print("CHECKS FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
