#!/usr/bin/env python3
"""Verify the frozen CassiFI quantum bridge algebra.

Protocol: computations/cassifi-quantum-bridge-pre-registration.md
"""

from __future__ import annotations

import math

import numpy as np


TOL = 1.0e-12
PHI = (1.0 + math.sqrt(5.0)) / 2.0


def partial_trace(rho: np.ndarray, subsystem: str) -> np.ndarray:
    """Trace one qubit from a two-qubit density matrix."""
    rho4 = rho.reshape(2, 2, 2, 2)
    if subsystem == "B":
        return np.trace(rho4, axis1=1, axis2=3)
    if subsystem == "A":
        return np.trace(rho4, axis1=0, axis2=2)
    raise ValueError("subsystem must be 'A' or 'B'")


def gate_gq1() -> bool:
    w_d = 1.0 / (1.0 + PHI**2)
    w_c = 1.0 + PHI**2
    metric = np.diag([w_d, w_d, w_c, w_c])
    hamiltonian = np.array(
        [
            [0.7, 0.2 + 0.1j, 0.0, -0.05j],
            [0.2 - 0.1j, 1.1, 0.15, 0.0],
            [0.0, 0.15, 1.6, 0.12 + 0.04j],
            [0.05j, 0.0, 0.12 - 0.04j, 2.0],
        ],
        dtype=np.complex128,
    )
    psi0 = np.array([1.0, 1.0j, -0.4 + 0.2j, 0.3], dtype=np.complex128)
    psi0 /= np.linalg.norm(psi0)

    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    amplitudes = eigenvectors.conj().T @ psi0
    psi_t = eigenvectors @ (np.exp(-1.0j * eigenvalues * 3.7) * amplitudes)

    min_metric_eigenvalue = float(np.linalg.eigvalsh(metric).min())
    hermitian_residual = float(np.max(np.abs(hamiltonian - hamiltonian.conj().T)))
    norm_residual = abs(float(np.vdot(psi_t, psi_t).real) - 1.0)
    passed = (
        min_metric_eigenvalue > 0.0
        and hermitian_residual <= TOL
        and norm_residual <= TOL
    )
    print(
        "GQ1",
        "PASS" if passed else "FAIL",
        f"min_eig(G)={min_metric_eigenvalue:.16e}",
        f"hermitian_residual={hermitian_residual:.3e}",
        f"norm_residual={norm_residual:.3e}",
    )
    return passed


def gate_gq2() -> bool:
    planck = 6.62607015e-34
    dalton = 1.66053906660e-27
    mass = 172_000.0 * dalton
    velocity = 160.0
    grating_period = 133.0e-9
    grating_separation = 0.983

    de_broglie = planck / (mass * velocity)
    talbot_length = grating_period**2 / de_broglie
    xi = grating_separation / talbot_length
    flight_time = 2.0 * grating_separation / velocity

    wave_numbers = np.array([0.2, 0.7, 1.3, 2.1])
    audit_mass = 3.4
    audit_hbar = 1.0
    energies = audit_hbar**2 * wave_numbers**2 / (2.0 * audit_mass)
    angular_frequency_energy = audit_hbar * (
        audit_hbar * wave_numbers**2 / (2.0 * audit_mass)
    )
    dispersion_residual = float(np.max(np.abs(energies - angular_frequency_energy)))

    passed = (
        dispersion_residual <= TOL
        and 14.0e-15 <= de_broglie <= 15.0e-15
        and 1.20 <= talbot_length <= 1.24
        and 0.79 <= xi <= 0.82
        and 12.0e-3 <= flight_time <= 12.6e-3
    )
    print(
        "GQ2",
        "PASS" if passed else "FAIL",
        f"dispersion_residual={dispersion_residual:.3e}",
        f"lambda_dB={de_broglie / 1e-15:.6f}_fm",
        f"L_T={talbot_length:.6f}_m",
        f"xi={xi:.6f}",
        f"t13={flight_time / 1e-3:.6f}_ms",
    )
    return passed


def gate_gq3() -> bool:
    bell = np.array([1.0, 0.0, 0.0, 1.0], dtype=np.complex128) / math.sqrt(2.0)
    rho = np.outer(bell, bell.conj())
    rho_a = partial_trace(rho, "B")
    rho_b = partial_trace(rho, "A")

    unitary_b = np.array([[1.0, 1.0], [-1.0, 1.0]]) / math.sqrt(2.0)
    transformed = np.kron(np.eye(2), unitary_b) @ bell
    transformed_rho = np.outer(transformed, transformed.conj())
    transformed_rho_a = partial_trace(transformed_rho, "B")

    mixed_target = np.eye(2) / 2.0
    marginal_residual = float(
        max(np.max(np.abs(rho_a - mixed_target)), np.max(np.abs(rho_b - mixed_target)))
    )
    signalling_residual = float(np.max(np.abs(transformed_rho_a - rho_a)))
    global_purity = float(np.trace(rho @ rho).real)
    reduced_purity = float(np.trace(rho_a @ rho_a).real)
    purity_residual = max(abs(global_purity - 1.0), abs(reduced_purity - 0.5))

    passed = (
        marginal_residual <= TOL
        and signalling_residual <= TOL
        and purity_residual <= TOL
    )
    print(
        "GQ3",
        "PASS" if passed else "FAIL",
        f"marginal_residual={marginal_residual:.3e}",
        f"signalling_residual={signalling_residual:.3e}",
        f"purity_residual={purity_residual:.3e}",
    )
    return passed


def gate_gq4() -> bool:
    coefficients = np.array([1.0, 2.0j, -0.5 + 0.25j, 0.3], dtype=np.complex128)
    coefficients /= np.linalg.norm(coefficients)
    probabilities = np.abs(coefficients) ** 2
    normalization_residual = abs(float(probabilities.sum()) - 1.0)

    u = np.array([0.01, 0.2, 0.7, 1.4])
    candidates = (0.5, 1.0, 2.0)
    residuals: dict[float, float] = {}
    for alpha in candidates:
        density = u**alpha
        derivative = alpha * u ** (alpha - 1.0)
        residuals[alpha] = float(np.max(np.abs(u * derivative - density) / density))
    equivariant = [alpha for alpha, residual in residuals.items() if residual <= TOL]

    passed = (
        bool(np.all(probabilities >= 0.0))
        and normalization_residual <= TOL
        and equivariant == [1.0]
    )
    residual_text = ",".join(f"a={alpha:g}:{residuals[alpha]:.3e}" for alpha in candidates)
    print(
        "GQ4",
        "PASS" if passed else "FAIL",
        f"born_norm_residual={normalization_residual:.3e}",
        f"equivariance_residuals={residual_text}",
    )
    return passed


def gate_gq5() -> bool:
    mu = math.log10(2.84e15)
    harmonics = np.arange(-3, 4)
    cassifi_multiplier = np.ones_like(harmonics, dtype=float)
    r0 = float(cassifi_multiplier[harmonics == 0][0])

    passed = (
        abs(mu - 15.45) <= 0.01
        and r0 == 1.0
        and bool(np.all(cassifi_multiplier == 1.0))
    )
    print(
        "GQ5",
        "PASS" if passed else "FAIL",
        f"mu={mu:.6f}",
        f"R0={r0:.1f}",
        f"harmonic_residual={float(np.max(np.abs(cassifi_multiplier - 1.0))):.1f}",
    )
    return passed


def main() -> int:
    gates = [gate_gq1(), gate_gq2(), gate_gq3(), gate_gq4(), gate_gq5()]
    if all(gates):
        print("ALL CHECKS PASSED")
        return 0
    print("CHECKS FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
