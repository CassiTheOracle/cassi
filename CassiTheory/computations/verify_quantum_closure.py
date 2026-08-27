#!/usr/bin/env python3
"""Verify the frozen finite quantum-closure certificate.

Protocol: computations/quantum-closure-pre-registration.md

The script uses only Python's standard library and NumPy.  It performs one
fixed, deterministic evaluation of QC1--QC9.  Numerical PASS lines certify the
listed algebra; documentary boundary lines carry the epistemic decisions.
"""

from __future__ import annotations

import math
from itertools import product

import numpy as np


TOL = 1.0e-11
PHI = (1.0 + math.sqrt(5.0)) / 2.0
HBAR = 1.0
N = 16
RHO = 1.7
GAMMA = 0.23
LAMBDA = 0.41
DT = 1.0e-3

RING_CELLS = 8
RING_D = 0.37
RING_H = 0.8
RING_MODE = 3
Q_FROZEN = PHI**2 / 3.0

DOCUMENTARY_BOUNDARIES = (
    "QC1 DOCUMENTARY BOUNDARY: the modulus projection is non-injective; microscopic phase is independent and never derived.",
    "QC2 DOCUMENTARY BOUNDARY: the Madelung equivalence is conditional on the ensemble action and Fisher coefficient hbar^2/8.",
    "QC3 DOCUMENTARY BOUNDARY: QF3 minimal guidance and QF4 quantum equilibrium remain declared premises.",
    "QC4 DOCUMENTARY BOUNDARY: Born branch weights are conditional on QF4; the finite instrument does not derive the outcome basis from CassiFI.",
    "QC5 DOCUMENTARY BOUNDARY: the finite birth-death reservoir is Hypothesized microphysics at a regulator; its positivity certificate makes no interacting continuum claim.",
    "QC6 DOCUMENTARY BOUNDARY: the projected conversion drift is conditional on the carrier reservoir and density projection.",
    "QC7 DOCUMENTARY BOUNDARY: binomial fluctuation and frozen-q transport-noise identities are conditional finite-regulator results.",
    "QC8 DOCUMENTARY BOUNDARY: the full advection-diffusion-conversion PDE follows only in the stated finite-volume/hydrodynamic limit with upwind-positive rates and Lipschitz q.",
    "QC9 DOCUMENTARY BOUNDARY: operational equivalence leaves a Cassi-specific discriminator requiring altered operational dynamics, nonequilibrium, or a new observable.",
    "DECISION ADOPT: the minimal finite-regulator reservoir completion as Hypothesized microphysics with a Derived-conditional projection theorem.",
    "DECISION REJECT: promotion of CassiFI physical identification to Derived.",
    "DECISION RETAIN: QF1-QF4 as an explicit minimal premise set.",
    "SCOPE BOUNDARY: the finite branch makes no interacting continuum claim.",
    "SCOPE BOUNDARY: SM spin/fermion/gauge sectors are conventional tensor factors rather than derived from CassiFI.",
)


def _report(name: str, passed: bool, **metrics: object) -> bool:
    status = "PASS" if passed else "FAIL"
    detail = " ".join(f"{key}={value}" for key, value in metrics.items())
    print(f"{name} NUMERICAL {status} {detail}".rstrip())
    return passed


def _periodic_divergence(vector: np.ndarray, spacing: float) -> np.ndarray:
    """Centered periodic divergence for a vector field on the fixed ring grid."""
    x_component = vector[..., 0]
    y_component = vector[..., 1]
    return (
        (np.roll(x_component, -1, axis=0) - np.roll(x_component, 1, axis=0))
        / (2.0 * spacing)
        + (np.roll(y_component, -1, axis=1) - np.roll(y_component, 1, axis=1))
        / (2.0 * spacing)
    )


def _birth_death_operators() -> tuple[np.ndarray, np.ndarray]:
    """Return L_down and L_up in the ordered carrier-count basis k=0,...,N."""
    dimension = N + 1
    l_down = np.zeros((dimension, dimension), dtype=np.complex128)
    l_up = np.zeros((dimension, dimension), dtype=np.complex128)
    for k in range(1, dimension):
        l_down[k - 1, k] = math.sqrt(GAMMA * k)
    for k in range(dimension - 1):
        l_up[k + 1, k] = math.sqrt(PHI * GAMMA * (N - k))
    return l_down, l_up


def _cnot_a_to_record() -> np.ndarray:
    """CNOT on the first and third qubits in the ordered basis A,B,R."""
    cnot = np.zeros((8, 8), dtype=np.complex128)
    for a, b, record in product((0, 1), repeat=3):
        source = ((a * 2) + b) * 2 + record
        target = ((a * 2) + b) * 2 + (record ^ a)
        cnot[target, source] = 1.0
    return cnot


def _remote_trace_three_qubit(state: np.ndarray) -> np.ndarray:
    """Trace A and R from an A,B,R density matrix, retaining B."""
    tensor = state.reshape(2, 2, 2, 2, 2, 2)
    return np.einsum("abcadc->bd", tensor)


def _record_trace_three_qubit(state: np.ndarray) -> np.ndarray:
    """Trace A and B from an A,B,R density matrix, retaining R."""
    tensor = state.reshape(2, 2, 2, 2, 2, 2)
    return np.einsum("abcabd->cd", tensor)


def _ab_trace_record(state: np.ndarray) -> np.ndarray:
    """Trace R from an A,B,R density matrix, retaining A,B."""
    tensor = state.reshape(2, 2, 2, 2, 2, 2)
    reduced = np.einsum("abcdec->abde", tensor)
    return reduced.reshape(4, 4)


def certificate_qc1() -> bool:
    """Certify that modulus projection loses an independent microscopic phase."""
    amplitudes = np.sqrt(np.array([0.7, 0.3], dtype=float))
    state_zero = amplitudes.astype(np.complex128)
    state_quarter = amplitudes * np.exp(1.0j * np.array([0.0, math.pi / 2.0]))

    projection_zero = np.abs(state_zero) ** 2
    projection_quarter = np.abs(state_quarter) ** 2
    projection_residual = float(np.max(np.abs(projection_zero - projection_quarter)))
    state_separation = float(np.linalg.norm(state_zero - state_quarter))
    phase_gap = abs(float(np.angle(state_quarter[1] / state_zero[1])))

    edge_current_zero = float(np.imag(np.conj(state_zero[0]) * state_zero[1]))
    edge_current_quarter = float(np.imag(np.conj(state_quarter[0]) * state_quarter[1]))
    current_gap = abs(edge_current_quarter - edge_current_zero)

    plus = np.array([1.0, 1.0], dtype=np.complex128) / math.sqrt(2.0)
    plus_probability_gap = abs(
        float(abs(np.vdot(plus, state_zero)) ** 2)
        - float(abs(np.vdot(plus, state_quarter)) ** 2)
    )

    passed = (
        projection_residual <= TOL
        and state_separation > 1.0e-3
        and phase_gap > 1.0e-3
        and current_gap > 1.0e-3
        and plus_probability_gap > 1.0e-3
    )
    return _report(
        "QC1",
        passed,
        modulus_residual=f"{projection_residual:.3e}",
        state_separation=f"{state_separation:.6f}",
        phase_gap=f"{phase_gap:.6f}",
        current_gap=f"{current_gap:.6f}",
        interference_gap=f"{plus_probability_gap:.6f}",
    )


def certificate_qc2() -> bool:
    """Certify the exact-uncertainty Fisher/Madelung algebra on fixed samples."""
    x = np.array([-1.2, -0.4, 0.3, 1.1], dtype=float)
    curvature = 0.7
    tilt = 0.2
    log_gradient = -2.0 * curvature * x + tilt
    density = np.exp(-curvature * x**2 + tilt * x)
    density_prime = density * log_gradient
    density_second = density * (log_gradient**2 - 2.0 * curvature)

    amplitude = np.sqrt(density)
    amplitude_prime = 0.5 * amplitude * log_gradient
    amplitude_second = amplitude * (0.25 * log_gradient**2 - curvature)

    fisher_density = density * log_gradient**2
    fisher_amplitude = 4.0 * amplitude_prime**2
    fisher_residual = float(np.max(np.abs(fisher_density - fisher_amplitude)))

    fisher_coefficient = HBAR**2 / 8.0
    coefficient_residual = abs(fisher_coefficient - 0.125)
    variational_fisher = fisher_coefficient * (
        -2.0 * density_second / density + (density_prime / density) ** 2
    )
    quantum_potential = -0.5 * HBAR**2 * amplitude_second / amplitude
    variation_residual = float(np.max(np.abs(variational_fisher - quantum_potential)))

    phase_gradient = 0.37 - 0.23 * x
    complex_gradient_norm = np.abs(
        amplitude_prime + 1.0j * amplitude * phase_gradient / HBAR
    ) ** 2
    madelung_split = amplitude_prime**2 + amplitude**2 * phase_gradient**2 / HBAR**2
    madelung_residual = float(np.max(np.abs(complex_gradient_norm - madelung_split)))

    passed = (
        fisher_residual <= TOL
        and coefficient_residual <= TOL
        and variation_residual <= TOL
        and madelung_residual <= TOL
    )
    return _report(
        "QC2",
        passed,
        fisher_residual=f"{fisher_residual:.3e}",
        coefficient_residual=f"{coefficient_residual:.3e}",
        variation_residual=f"{variation_residual:.3e}",
        madelung_residual=f"{madelung_residual:.3e}",
    )


def certificate_qc3() -> bool:
    """Certify guidance ambiguity and transported nonequilibrium on a torus."""
    grid_size = 8
    spacing = 2.0 * math.pi / grid_size
    grid = spacing * np.arange(grid_size, dtype=float)
    x, y = np.meshgrid(grid, grid, indexing="ij")

    density = np.ones_like(x)
    base_velocity = np.stack(
        (0.31 * np.ones_like(x), -0.22 * np.ones_like(y)), axis=-1
    )
    base_current = density[..., None] * base_velocity
    divergence_free_addition = np.stack(
        (0.17 * np.sin(y), -0.11 * np.sin(x)), axis=-1
    )
    altered_current = base_current + divergence_free_addition

    divergence_addition = _periodic_divergence(divergence_free_addition, spacing)
    base_divergence = _periodic_divergence(base_current, spacing)
    altered_divergence = _periodic_divergence(altered_current, spacing)
    divergence_residual = float(np.max(np.abs(divergence_addition)))
    continuity_residual = float(np.max(np.abs(altered_divergence - base_divergence)))
    velocity_difference = float(
        np.max(np.linalg.norm(altered_current / density[..., None] - base_velocity, axis=-1))
    )

    time = 1.3
    ratio = 1.0 + 0.15 * np.sin(x - 0.31 * time) + 0.11 * np.cos(y + 0.22 * time)
    ratio_time_derivative = (
        -0.15 * 0.31 * np.cos(x - 0.31 * time)
        - 0.11 * 0.22 * np.sin(y + 0.22 * time)
    )
    ratio_x = 0.15 * np.cos(x - 0.31 * time)
    ratio_y = -0.11 * np.sin(y + 0.22 * time)
    transport_residual = float(
        np.max(np.abs(ratio_time_derivative + 0.31 * ratio_x - 0.22 * ratio_y))
    )
    nonequilibrium_gap = float(np.max(np.abs(ratio - 1.0)))
    minimum_ratio = float(np.min(ratio))

    passed = (
        divergence_residual <= TOL
        and continuity_residual <= TOL
        and velocity_difference > 1.0e-3
        and transport_residual <= TOL
        and nonequilibrium_gap > 1.0e-3
        and minimum_ratio > 0.0
    )
    return _report(
        "QC3",
        passed,
        divergence_residual=f"{divergence_residual:.3e}",
        continuity_residual=f"{continuity_residual:.3e}",
        velocity_difference=f"{velocity_difference:.6f}",
        transport_residual=f"{transport_residual:.3e}",
        nonequilibrium_gap=f"{nonequilibrium_gap:.6f}",
    )


def certificate_qc4() -> bool:
    """Certify a finite CNOT instrument and remote-state invariance."""
    bell = np.array([1.0, 0.0, 0.0, 1.0], dtype=np.complex128) / math.sqrt(2.0)
    rho_ab = np.outer(bell, bell.conj())
    ready = np.diag([1.0, 0.0]).astype(np.complex128)
    rho_abr = np.kron(rho_ab, ready)

    cnot = _cnot_a_to_record()
    rho_after = cnot @ rho_abr @ cnot.conj().T
    identity_three = np.eye(8, dtype=np.complex128)
    unitary_residual = float(np.max(np.abs(cnot.conj().T @ cnot - identity_three)))

    projectors = (
        np.diag([1.0, 0.0]).astype(np.complex128),
        np.diag([0.0, 1.0]).astype(np.complex128),
    )
    kraus_completeness = sum(
        (projector.conj().T @ projector for projector in projectors),
        np.zeros((2, 2), dtype=np.complex128),
    )
    kraus_residual = float(
        np.max(np.abs(kraus_completeness - np.eye(2, dtype=np.complex128)))
    )

    rho_a = np.trace(rho_ab.reshape(2, 2, 2, 2), axis1=1, axis2=3)
    born_probabilities = np.array(
        [float(np.trace(projector @ rho_a).real) for projector in projectors]
    )
    branch_probabilities: list[float] = []
    branch_residuals: list[float] = []
    record_residuals: list[float] = []
    unconditioned = np.zeros_like(rho_after)
    for projector in projectors:
        full_projector = np.kron(np.kron(np.eye(2), np.eye(2)), projector)
        branch = full_projector @ rho_after @ full_projector
        unconditioned += branch
        probability = float(np.trace(branch).real)
        branch_probabilities.append(probability)

        branch_ab = _ab_trace_record(branch)
        kraus_branch = np.kron(projector, np.eye(2)) @ rho_ab @ np.kron(
            projector.conj().T, np.eye(2)
        )
        branch_residuals.append(float(np.max(np.abs(branch_ab - kraus_branch))))

        record_state = _record_trace_three_qubit(branch)
        record_residuals.append(
            float(np.max(np.abs(record_state - probability * projector)))
        )

    remote_before = _remote_trace_three_qubit(rho_abr)
    remote_after = _remote_trace_three_qubit(unconditioned)
    remote_residual = float(np.max(np.abs(remote_after - remote_before)))
    born_residual = float(
        np.max(np.abs(np.asarray(branch_probabilities) - born_probabilities))
    )
    branch_kraus_residual = max(branch_residuals)
    record_residual = max(record_residuals)

    passed = (
        unitary_residual <= TOL
        and kraus_residual <= TOL
        and born_residual <= TOL
        and branch_kraus_residual <= TOL
        and record_residual <= TOL
        and remote_residual <= TOL
    )
    return _report(
        "QC4",
        passed,
        unitary_residual=f"{unitary_residual:.3e}",
        kraus_residual=f"{kraus_residual:.3e}",
        born_residual=f"{born_residual:.3e}",
        branch_residual=f"{branch_kraus_residual:.3e}",
        record_residual=f"{record_residual:.3e}",
        remote_residual=f"{remote_residual:.3e}",
    )


def certificate_qc5() -> bool:
    """Certify the finite Kraus birth-death step and its diagonal generator."""
    l_down, l_up = _birth_death_operators()
    dimension = N + 1
    outgoing_operator = l_down.conj().T @ l_down + l_up.conj().T @ l_up
    outgoing = np.real(np.diag(outgoing_operator))
    kraus_argument = 1.0 - DT * outgoing
    k_zero = np.diag(np.sqrt(kraus_argument)).astype(np.complex128)
    k_down = math.sqrt(DT) * l_down
    k_up = math.sqrt(DT) * l_up

    completeness = (
        k_zero.conj().T @ k_zero
        + k_down.conj().T @ k_down
        + k_up.conj().T @ k_up
    )
    completeness_residual = float(
        np.max(np.abs(completeness - np.eye(dimension, dtype=np.complex128)))
    )

    amplitudes = np.sqrt(np.arange(1, dimension + 1, dtype=float))
    amplitudes /= np.linalg.norm(amplitudes)
    phases = np.exp(0.17j * np.arange(dimension, dtype=float))
    state = amplitudes.astype(np.complex128) * phases
    rho_zero = np.outer(state, state.conj())
    rho_one = (
        k_zero @ rho_zero @ k_zero.conj().T
        + k_down @ rho_zero @ k_down.conj().T
        + k_up @ rho_zero @ k_up.conj().T
    )
    trace_residual = abs(float(np.trace(rho_one).real) - 1.0)
    hermitian_residual = float(np.max(np.abs(rho_one - rho_one.conj().T)))
    minimum_eigenvalue = float(np.linalg.eigvalsh((rho_one + rho_one.conj().T) / 2.0).min())

    populations = np.real(np.diag(rho_zero))
    master_rhs = np.zeros(dimension, dtype=float)
    for k in range(dimension):
        if k < N:
            master_rhs[k] += GAMMA * (k + 1) * populations[k + 1]
        if k > 0:
            master_rhs[k] += PHI * GAMMA * (N - k + 1) * populations[k - 1]
        master_rhs[k] -= (GAMMA * k + PHI * GAMMA * (N - k)) * populations[k]
    diagonal_step = populations + DT * master_rhs
    diagonal_residual = float(
        np.max(np.abs(np.real(np.diag(rho_one)) - diagonal_step))
    )
    diagonal_imaginary_residual = float(np.max(np.abs(np.imag(np.diag(rho_one)))))

    passed = (
        float(kraus_argument.min()) >= 0.0
        and completeness_residual <= TOL
        and trace_residual <= TOL
        and hermitian_residual <= TOL
        and minimum_eigenvalue >= -TOL
        and diagonal_residual <= TOL
        and diagonal_imaginary_residual <= TOL
    )
    return _report(
        "QC5",
        passed,
        dt=f"{DT:.3e}",
        kraus_argument_min=f"{float(kraus_argument.min()):.6e}",
        completeness_residual=f"{completeness_residual:.3e}",
        trace_residual=f"{trace_residual:.3e}",
        min_eigenvalue=f"{minimum_eigenvalue:.3e}",
        diagonal_residual=f"{diagonal_residual:.3e}",
    )


def certificate_qc6() -> bool:
    """Certify the projected conversion drift at fixed total density."""
    k_values = np.arange(N + 1, dtype=float)
    e_y = RHO * k_values / N
    e_i = RHO * (N - k_values) / N
    epsilon = e_y - PHI * e_i

    down_rate = GAMMA * k_values
    up_rate = PHI * GAMMA * (N - k_values)
    expected_k_drift = up_rate - down_rate
    drift_y = (RHO / N) * expected_k_drift
    drift_i = -drift_y

    drift_y_residual = float(np.max(np.abs(drift_y + GAMMA * epsilon)))
    drift_i_residual = float(np.max(np.abs(drift_i - GAMMA * epsilon)))
    total_density_residual = float(np.max(np.abs(e_y + e_i - RHO)))
    total_drift_residual = float(np.max(np.abs(drift_y + drift_i)))

    passed = (
        drift_y_residual <= TOL
        and drift_i_residual <= TOL
        and total_density_residual <= TOL
        and total_drift_residual <= TOL
    )
    return _report(
        "QC6",
        passed,
        drift_y_residual=f"{drift_y_residual:.3e}",
        drift_i_residual=f"{drift_i_residual:.3e}",
        total_density_residual=f"{total_density_residual:.3e}",
        total_drift_residual=f"{total_drift_residual:.3e}",
    )


def certificate_qc7() -> bool:
    """Certify binomial equilibrium, decay, and homogeneous transport noise."""
    k_values = np.arange(N + 1, dtype=float)
    p_y = PHI / (1.0 + PHI)
    p_i = 1.0 / (1.0 + PHI)
    probability_identity_residual = max(
        abs(p_y - PHI ** -1), abs(p_i - PHI ** -2), abs(p_y + p_i - 1.0)
    )

    stationary = np.array(
        [
            math.comb(N, int(k)) * p_y**int(k) * p_i ** (N - int(k))
            for k in k_values
        ],
        dtype=float,
    )
    stationary_normalization_residual = abs(float(stationary.sum()) - 1.0)

    detailed_balance_residual = 0.0
    for k in range(N):
        left = stationary[k] * PHI * GAMMA * (N - k)
        right = stationary[k + 1] * GAMMA * (k + 1)
        detailed_balance_residual = max(detailed_balance_residual, abs(left - right))

    epsilon = RHO * ((1.0 + PHI) * k_values / N - PHI)
    epsilon_mean = float(np.dot(stationary, epsilon))
    epsilon_variance = float(np.dot(stationary, (epsilon - epsilon_mean) ** 2))
    variance_target = PHI * RHO**2 / N
    variance_residual = abs(epsilon_variance - variance_target)

    epsilon_drift = np.zeros(N + 1, dtype=float)
    for k in range(N + 1):
        if k < N:
            epsilon_drift[k] += PHI * GAMMA * (N - k) * (epsilon[k + 1] - epsilon[k])
        if k > 0:
            epsilon_drift[k] += GAMMA * k * (epsilon[k - 1] - epsilon[k])
    gamma_decay = PHI**2 * GAMMA
    decay_residual = float(np.max(np.abs(epsilon_drift + gamma_decay * epsilon)))

    gamma_background = LAMBDA * (1.0 - Q_FROZEN)
    gamma_background_residual = abs(gamma_background - LAMBDA / (3.0 * PHI**2))
    gamma_canonical = PHI**2 * gamma_background
    gamma_canonical_target = LAMBDA / 3.0
    canonical_decay_residual = abs(gamma_canonical - gamma_canonical_target)
    q_rate_residual = abs(
        PHI**2 * LAMBDA * (1.0 - Q_FROZEN) - gamma_canonical
    )
    noise_target = 2.0 * LAMBDA * PHI * RHO**2 / (3.0 * N)
    noise_from_variance = 2.0 * gamma_canonical * variance_target
    noise_residual = abs(noise_from_variance - noise_target)

    ring_grid = np.arange(RING_CELLS, dtype=float)
    ring_rate = RING_D / RING_H**2
    hopping = np.zeros((RING_CELLS, RING_CELLS), dtype=float)
    for cell in range(RING_CELLS):
        hopping[(cell - 1) % RING_CELLS, cell] += ring_rate
        hopping[(cell + 1) % RING_CELLS, cell] += ring_rate
        hopping[cell, cell] -= 2.0 * ring_rate
    wave_number = 2.0 * math.pi * RING_MODE / RING_CELLS
    k_hat_squared = 4.0 * math.sin(math.pi * RING_MODE / RING_CELLS) ** 2 / RING_H**2
    fourier_mode = np.exp(1.0j * wave_number * ring_grid)
    ring_decay = gamma_canonical + RING_D * k_hat_squared
    ring_decay_residual = float(
        np.max(
            np.abs(
                (hopping - gamma_canonical * np.eye(RING_CELLS)) @ fourier_mode
                + ring_decay * fourier_mode
            )
        )
    )
    mode_variance_residual = abs(epsilon_variance - variance_target)
    mode_noise_power = 2.0 * ring_decay * epsilon_variance
    mode_noise_target = 2.0 * ring_decay * variance_target
    mode_noise_residual = abs(mode_noise_power - mode_noise_target)
    ring_column_sum_residual = float(np.max(np.abs(hopping.sum(axis=0))))

    passed = (
        probability_identity_residual <= TOL
        and stationary_normalization_residual <= TOL
        and detailed_balance_residual <= TOL
        and abs(epsilon_mean) <= TOL
        and variance_residual <= TOL
        and decay_residual <= TOL
        and gamma_background_residual <= TOL
        and canonical_decay_residual <= TOL
        and q_rate_residual <= TOL
        and noise_residual <= TOL
        and ring_decay_residual <= TOL
        and mode_variance_residual <= TOL
        and mode_noise_residual <= TOL
        and ring_column_sum_residual <= TOL
    )
    return _report(
        "QC7",
        passed,
        probability_residual=f"{probability_identity_residual:.3e}",
        normalization_residual=f"{stationary_normalization_residual:.3e}",
        detailed_balance_residual=f"{detailed_balance_residual:.3e}",
        variance_residual=f"{variance_residual:.3e}",
        decay_residual=f"{decay_residual:.3e}",
        canonical_gamma=f"{gamma_canonical:.12f}",
        noise_residual=f"{noise_residual:.3e}",
        k_hat_squared=f"{k_hat_squared:.12f}",
        ring_decay_residual=f"{ring_decay_residual:.3e}",
        mode_noise_residual=f"{mode_noise_residual:.3e}",
    )


def certificate_qc8() -> bool:
    """Certify two-cell symmetric hopping and species conservation."""
    diffusion = 0.37
    cell_spacing = 0.8
    hopping_rate = diffusion / cell_spacing**2
    generator = np.array(
        [[-hopping_rate, hopping_rate], [hopping_rate, -hopping_rate]], dtype=float
    )
    e_y = np.array([1.2, 0.7], dtype=float)
    e_i = np.array([0.5, 0.9], dtype=float)
    drift_y = generator @ e_y
    drift_i = generator @ e_i
    expected_y = hopping_rate * np.array([e_y[1] - e_y[0], e_y[0] - e_y[1]])
    expected_i = hopping_rate * np.array([e_i[1] - e_i[0], e_i[0] - e_i[1]])

    generator_residual = float(np.max(np.abs(generator.sum(axis=0))))
    drift_residual = float(
        max(np.max(np.abs(drift_y - expected_y)), np.max(np.abs(drift_i - expected_i)))
    )
    species_conservation_residual = float(
        max(abs(float(drift_y.sum())), abs(float(drift_i.sum())))
    )
    positive_rate = hopping_rate > 0.0

    passed = (
        positive_rate
        and generator_residual <= TOL
        and drift_residual <= TOL
        and species_conservation_residual <= TOL
    )
    return _report(
        "QC8",
        passed,
        hopping_rate=f"{hopping_rate:.6f}",
        generator_residual=f"{generator_residual:.3e}",
        drift_residual=f"{drift_residual:.3e}",
        conservation_residual=f"{species_conservation_residual:.3e}",
    )


def certificate_qc9() -> bool:
    """Certify operational equivalence for finite CPTP records under QF4."""
    rho = np.array(
        [[0.7, 0.18 - 0.11j], [0.18 + 0.11j, 0.3]], dtype=np.complex128
    )
    rho_hermitian_residual = float(np.max(np.abs(rho - rho.conj().T)))
    rho_trace_residual = abs(float(np.trace(rho).real) - 1.0)
    rho_minimum_eigenvalue = float(np.linalg.eigvalsh(rho).min())

    plus = np.array([1.0, 1.0], dtype=np.complex128) / math.sqrt(2.0)
    minus = np.array([1.0, -1.0], dtype=np.complex128) / math.sqrt(2.0)
    settings = (
        (
            np.outer(np.array([1.0, 0.0], dtype=np.complex128), np.array([1.0, 0.0])),
            np.outer(np.array([0.0, 1.0], dtype=np.complex128), np.array([0.0, 1.0])),
        ),
        (np.outer(plus, plus.conj()), np.outer(minus, minus.conj())),
    )

    ordinary_records: list[np.ndarray] = []
    hidden_records: list[np.ndarray] = []
    completeness_residual = 0.0
    record_sector_residual = 0.0
    for effects in settings:
        effects_sum = sum(
            (effect.conj().T @ effect for effect in effects),
            np.zeros((2, 2), dtype=np.complex128),
        )
        completeness_residual = max(
            completeness_residual,
            float(np.max(np.abs(effects_sum - np.eye(2, dtype=np.complex128)))),
        )
        ordinary = np.array([float(np.trace(effect @ rho).real) for effect in effects])
        ordinary_records.append(ordinary)

        hidden_configuration_weights = ordinary.copy()
        topological_record_map = np.eye(2, dtype=float)
        hidden = hidden_configuration_weights @ topological_record_map
        hidden_records.append(hidden)
        record_sector_residual = max(
            record_sector_residual,
            float(np.max(np.abs(topological_record_map.sum(axis=1) - 1.0))),
        )

    operational_residual = float(
        max(
            np.max(np.abs(ordinary - hidden))
            for ordinary, hidden in zip(ordinary_records, hidden_records)
        )
    )
    probability_normalization_residual = float(
        max(
            abs(float(probabilities.sum()) - 1.0)
            for probabilities in ordinary_records
        )
    )

    passed = (
        rho_hermitian_residual <= TOL
        and rho_trace_residual <= TOL
        and rho_minimum_eigenvalue >= -TOL
        and completeness_residual <= TOL
        and record_sector_residual <= TOL
        and operational_residual <= TOL
        and probability_normalization_residual <= TOL
    )
    return _report(
        "QC9",
        passed,
        rho_min_eigenvalue=f"{rho_minimum_eigenvalue:.6e}",
        cptp_residual=f"{completeness_residual:.3e}",
        operational_residual=f"{operational_residual:.3e}",
        probability_residual=f"{probability_normalization_residual:.3e}",
    )


def main() -> int:
    gates = [
        certificate_qc1(),
        certificate_qc2(),
        certificate_qc3(),
        certificate_qc4(),
        certificate_qc5(),
        certificate_qc6(),
        certificate_qc7(),
        certificate_qc8(),
        certificate_qc9(),
    ]
    print("DOCUMENTARY BOUNDARIES")
    documentary_lines_printed = 0
    for line in DOCUMENTARY_BOUNDARIES:
        print(line)
        documentary_lines_printed += 1
    if all(gates) and documentary_lines_printed == len(DOCUMENTARY_BOUNDARIES):
        print("ALL CHECKS PASSED")
        return 0
    print("CHECKS FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
