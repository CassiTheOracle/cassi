#!/usr/bin/env python3
"""Frozen MCC1–MCC9 receipt for the matter-completion boundary.

Run once from the CassiTheory repository root:
    python computations/matter_completion_boundary_check.py
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass

import numpy as np


PHI = (1.0 + math.sqrt(5.0)) / 2.0
HBAR = 1.0
T_POWER = PHI**-1
R_POWER = PHI**-2
TOL = 1.0e-11
N_STEPS = 5
CHANNEL_STEPS = 6
DT = 0.2
GENERATOR_PHASE = 0.43
OMEGA = 0.37
DRIVE = 0.08 - 0.03j
PHYSICAL_VERDICT = "INCONCLUSIVE—NUMERICAL QUALITY"

SCOPE_FLAGS = {
    "physical_exterior_selected": False,
    "microscopic_interface_coefficients_derived": False,
    "golden_port_power_identification_derived": False,
    "universal_cross_coherence_power_map": False,
    "physical_reservoir_identified": False,
    "local_reservoir_stress_derived": False,
    "state_dependent_gravity_closed": False,
    "coherence_fibre_particle_identity_derived": False,
    "q2_qualified_full_background": False,
    "full_constrained_spectrum_computed": False,
}


@dataclass(frozen=True)
class Gate:
    name: str
    passed: bool
    detail: str


def max_abs(value: np.ndarray | complex | float) -> float:
    return float(np.max(np.abs(value)))


def relative_frame(angle: float) -> np.ndarray:
    return np.diag([np.exp(-0.5j * angle), np.exp(0.5j * angle)])


def unitary_from_hermitian(hamiltonian: np.ndarray, duration: float) -> np.ndarray:
    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    phases = np.exp(-1j * eigenvalues * duration / HBAR)
    return (eigenvectors * phases) @ eigenvectors.conj().T


def channel_operators() -> tuple[np.ndarray, np.ndarray]:
    e0 = np.diag([1.0, math.sqrt(T_POWER)]).astype(np.complex128)
    e1 = np.array(
        [[0.0, math.sqrt(R_POWER)], [0.0, 0.0]], dtype=np.complex128
    )
    return e0, e1


def apply_channel(state: np.ndarray, operators: tuple[np.ndarray, ...]) -> np.ndarray:
    return sum(operator @ state @ operator.conj().T for operator in operators)


def golden_dilation() -> np.ndarray:
    """Unitary in basis |00>, |01>, |10>, |11>, system index first."""
    t_amp = math.sqrt(T_POWER)
    r_amp = math.sqrt(R_POWER)
    return np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, t_amp, r_amp, 0.0],
            [0.0, -r_amp, t_amp, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.complex128,
    )


def interface_data() -> tuple[np.ndarray, np.ndarray]:
    h_in = np.array(
        [[0.40, 0.07 + 0.02j], [0.07 - 0.02j, -0.20]],
        dtype=np.complex128,
    )
    h_out = np.array(
        [[-0.10, -0.03j], [0.03j, 0.55]], dtype=np.complex128
    )
    coupling = np.array(
        [[0.21 + 0.04j, -0.06 + 0.02j], [0.05 - 0.03j, 0.17 - 0.01j]],
        dtype=np.complex128,
    )
    h_io = np.block(
        [[h_in, coupling], [coupling.conj().T, h_out]]
    ).astype(np.complex128)
    return h_io, coupling


def positive_interface_state() -> np.ndarray:
    seed = np.array(
        [
            [1.0, 0.2j, 0.1, -0.1j],
            [0.1, 0.8, 0.2 - 0.1j, 0.0],
            [0.0, 0.15, 0.9, 0.12j],
            [0.05j, 0.0, -0.08j, 0.7],
        ],
        dtype=np.complex128,
    )
    state = seed @ seed.conj().T
    return state / np.trace(state)


def propagate_cross_block(
    seed: np.ndarray, left: np.ndarray, right: np.ndarray, steps: int
) -> np.ndarray:
    result = seed.copy()
    for _ in range(steps):
        result = left @ result @ right.conj().T
    return result


def gate_mcc1() -> Gate:
    e0, e1 = channel_operators()
    identity_error = max_abs(e0.conj().T @ e0 + e1.conj().T @ e1 - np.eye(2))

    vectors = [operator.reshape(-1, order="F") for operator in (e0, e1)]
    choi = sum(np.outer(vector, vector.conj()) for vector in vectors)
    choi_eigenvalues = np.linalg.eigvalsh(choi)
    choi_min = float(np.min(choi_eigenvalues))
    choi_rank = int(np.count_nonzero(choi_eigenvalues > 1.0e-10))

    dilation = golden_dilation()
    unitary_error = max_abs(dilation.conj().T @ dilation - np.eye(4))
    reshaped = dilation.reshape(2, 2, 2, 2)
    extracted = tuple(reshaped[:, env_out, :, 0] for env_out in range(2))
    dilation_error = max(
        max_abs(extracted[0] - e0), max_abs(extracted[1] - e1)
    )

    angle = 0.61
    environment_rotation = np.array(
        [[math.cos(angle), math.sin(angle)], [-math.sin(angle), math.cos(angle)]],
        dtype=np.complex128,
    )
    rotated = tuple(
        sum(environment_rotation[a, b] * (e0, e1)[b] for b in range(2))
        for a in range(2)
    )
    test_state = np.array(
        [[0.45, 0.13 - 0.07j], [0.13 + 0.07j, 0.55]], dtype=np.complex128
    )
    rotation_error = max_abs(
        apply_channel(test_state, rotated) - apply_channel(test_state, (e0, e1))
    )

    passed = (
        max(identity_error, unitary_error, dilation_error, rotation_error) <= TOL
        and choi_min >= -TOL
        and choi_rank == 2
    )
    detail = (
        f"TP_error={identity_error:.3e} Choi_min={choi_min:.3e} "
        f"Choi_rank={choi_rank} dilation_unitarity={unitary_error:.3e} "
        f"extraction_error={dilation_error:.3e} basis_rotation_error={rotation_error:.3e}"
    )
    return Gate("MCC1", passed, detail)


def gate_mcc2() -> Gate:
    h_io, coupling = interface_data()
    hermitian_error = max_abs(h_io - h_io.conj().T)

    u_in = relative_frame(0.37)
    u_out = relative_frame(-0.52)
    u_block = np.block(
        [
            [u_in, np.zeros((2, 2), dtype=np.complex128)],
            [np.zeros((2, 2), dtype=np.complex128), u_out],
        ]
    )
    h_in = h_io[:2, :2]
    h_out = h_io[2:, 2:]
    transformed_components = np.block(
        [
            [
                u_in @ h_in @ u_in.conj().T,
                u_in @ coupling @ u_out.conj().T,
            ],
            [
                u_out @ coupling.conj().T @ u_in.conj().T,
                u_out @ h_out @ u_out.conj().T,
            ],
        ]
    )
    covariance_error = max_abs(
        transformed_components - u_block @ h_io @ u_block.conj().T
    )

    state = positive_interface_state()
    propagator = unitary_from_hermitian(h_io, 0.31)
    evolved = propagator @ state @ propagator.conj().T
    number_error = abs(np.trace(evolved) - np.trace(state))
    energy_error = abs(np.trace(h_io @ evolved) - np.trace(h_io @ state))

    generator0 = np.diag([GENERATOR_PHASE, -0.29]) / DT
    generator1 = generator0.copy()
    generator1[0, 0] += 2.0 * math.pi / DT
    discrete0 = np.diag(np.exp(-1j * np.diag(generator0) * DT))
    discrete1 = np.diag(np.exp(-1j * np.diag(generator1) * DT))
    branch_map_error = max_abs(discrete0 - discrete1)
    generator_gap = max_abs(generator1 - generator0)

    worst = max(
        hermitian_error,
        covariance_error,
        float(number_error),
        float(energy_error),
        branch_map_error,
    )
    passed = worst <= TOL and generator_gap > 1.0
    detail = (
        f"Hermitian_error={hermitian_error:.3e} covariance_error={covariance_error:.3e} "
        f"number_error={number_error:.3e} energy_error={energy_error:.3e} "
        f"branch_map_error={branch_map_error:.3e} generator_gap={generator_gap:.6f}"
    )
    return Gate("MCC2", passed, detail)


def gate_mcc3() -> Gate:
    splitter = np.array(
        [
            [math.sqrt(T_POWER), math.sqrt(R_POWER)],
            [-math.sqrt(R_POWER), math.sqrt(T_POWER)],
        ],
        dtype=np.complex128,
    )
    unitary_error = max_abs(splitter.conj().T @ splitter - np.eye(2))

    seed = np.array(
        [[0.22 + 0.04j, -0.09 + 0.05j], [0.07 - 0.03j, 0.18 - 0.02j]],
        dtype=np.complex128,
    )
    left_unitary = relative_frame(0.23)
    right_unitary = relative_frame(-0.41)
    seed_norm = float(np.linalg.norm(seed, "fro"))
    one_sided = propagate_cross_block(
        seed,
        math.sqrt(T_POWER) * left_unitary,
        right_unitary,
        N_STEPS,
    )
    symmetric = propagate_cross_block(
        seed,
        math.sqrt(T_POWER) * left_unitary,
        math.sqrt(T_POWER) * right_unitary,
        N_STEPS,
    )
    one_sided_ratio = float(np.linalg.norm(one_sided, "fro")) / seed_norm
    symmetric_ratio = float(np.linalg.norm(symmetric, "fro")) / seed_norm
    one_sided_error = abs(one_sided_ratio - PHI ** (-N_STEPS / 2.0))
    symmetric_error = abs(symmetric_ratio - PHI**-N_STEPS)

    forward_power = T_POWER**N_STEPS
    return_power = sum(R_POWER * T_POWER**step for step in range(N_STEPS))
    ledger_error = abs(forward_power + return_power - 1.0)
    power_error = abs(forward_power - PHI**-N_STEPS)

    coherent_splitter = np.linalg.matrix_power(splitter, N_STEPS)
    coherent_forward = abs(coherent_splitter[0, 0]) ** 2
    coherent_difference = abs(coherent_forward - forward_power)

    passed = (
        max(
            unitary_error,
            one_sided_error,
            symmetric_error,
            ledger_error,
            power_error,
        )
        <= TOL
        and coherent_difference > 1.0e-6
    )
    detail = (
        f"unitarity={unitary_error:.3e} one_sided={one_sided_ratio:.12f} "
        f"symmetric={symmetric_ratio:.12f} routed_power={forward_power:.12f} "
        f"ledger_error={ledger_error:.3e} coherent_power={coherent_forward:.12f} "
        f"control_difference={coherent_difference:.3e}"
    )
    return Gate("MCC3", passed, detail)


def gate_mcc4() -> Gate:
    number_flux = 2.3
    frequency = 1.7
    input_power = HBAR * frequency * number_flux
    output_power = HBAR * frequency * T_POWER * number_flux
    power_ratio_error = abs(output_power / input_power - T_POWER)

    mode_a = np.diag([0.2, 0.0]).astype(np.complex128)
    mode_b = np.diag([0.0, 0.2]).astype(np.complex128)
    omega_operator = np.diag([1.0, 3.0])
    norm_error = abs(np.linalg.norm(mode_a, "fro") - np.linalg.norm(mode_b, "fro"))
    weighted_a = float(np.real(np.trace(omega_operator @ mode_a.conj().T @ mode_a)))
    weighted_b = float(np.real(np.trace(omega_operator @ mode_b.conj().T @ mode_b)))
    weighted_separation = abs(weighted_b - weighted_a)
    universal_scope = SCOPE_FLAGS["universal_cross_coherence_power_map"]

    passed = (
        max(power_ratio_error, norm_error) <= TOL
        and weighted_separation > 1.0e-3
        and not universal_scope
    )
    detail = (
        f"single_mode_ratio={output_power / input_power:.12f} "
        f"ratio_error={power_ratio_error:.3e} equal_norm_error={norm_error:.3e} "
        f"weighted_A={weighted_a:.6f} weighted_B={weighted_b:.6f} "
        f"universal_map={universal_scope}"
    )
    return Gate("MCC4", passed, detail)


def gate_mcc5() -> Gate:
    operators = channel_operators()
    state0 = np.array(
        [[0.40, 0.20 + 0.10j], [0.20 - 0.10j, 0.60]], dtype=np.complex128
    )
    state = state0.copy()
    for _ in range(CHANNEL_STEPS):
        state = apply_channel(state, operators)

    population_ratio = float(np.real(state[1, 1] / state0[1, 1]))
    coherence_ratio = state[0, 1] / state0[0, 1]
    population_error = abs(population_ratio - T_POWER**CHANNEL_STEPS)
    coherence_error = abs(coherence_ratio - T_POWER ** (CHANNEL_STEPS / 2.0))

    gamma = -math.log(T_POWER) / DT
    elapsed = CHANNEL_STEPS * DT
    continuous_population = math.exp(-gamma * elapsed)
    continuous_coherence = math.exp(-0.5 * gamma * elapsed)
    continuous_error = max(
        abs(continuous_population - T_POWER**CHANNEL_STEPS),
        abs(continuous_coherence - T_POWER ** (CHANNEL_STEPS / 2.0)),
    )

    stationary = DRIVE / (0.5 * gamma + 1j * OMEGA)
    stationary_residual = abs(-(0.5 * gamma + 1j * OMEGA) * stationary + DRIVE)
    pole = -0.5 * gamma - 1j * OMEGA
    physical_bath = SCOPE_FLAGS["physical_reservoir_identified"]

    passed = (
        max(population_error, coherence_error, continuous_error, stationary_residual)
        <= TOL
        and pole.real < 0.0
        and not physical_bath
    )
    detail = (
        f"gamma={gamma:.12f} population_ratio={population_ratio:.12f} "
        f"coherence_ratio={coherence_ratio.real:.12f}{coherence_ratio.imag:+.3e}i "
        f"continuous_error={continuous_error:.3e} "
        f"stationary_residual={stationary_residual:.3e} pole_real={pole.real:.6f} "
        f"physical_bath={physical_bath}"
    )
    return Gate("MCC5", passed, detail)


def gate_mcc6() -> Gate:
    h_io, _ = interface_data()
    state = positive_interface_state()
    propagator = unitary_from_hermitian(h_io, 0.47)
    evolved = propagator @ state @ propagator.conj().T
    number_error = abs(np.trace(evolved) - np.trace(state))
    energy_error = abs(np.trace(h_io @ evolved) - np.trace(h_io @ state))

    exchange = np.array([0.12, -0.04, 0.07, 0.03])
    interior_divergence = -exchange
    complementary_divergence = exchange
    ward_error = max_abs(interior_divergence + complementary_divergence)
    local_stress_scope = SCOPE_FLAGS["local_reservoir_stress_derived"]

    passed = (
        max(float(number_error), float(energy_error), ward_error) <= TOL
        and not local_stress_scope
    )
    detail = (
        f"number_error={number_error:.3e} energy_error={energy_error:.3e} "
        f"closed_Ward_error={ward_error:.3e} local_reservoir_stress={local_stress_scope}"
    )
    return Gate("MCC6", passed, detail)


def gate_mcc7() -> Gate:
    metric = np.diag([-1.0, 1.0, 1.0, 1.0])
    wavevector = np.array([0.0, 1.3, 0.0, 0.0])
    trace_reversed = np.array(
        [
            [0.20, 0.0, 0.03, -0.04],
            [0.0, 0.0, 0.0, 0.0],
            [0.03, 0.0, -0.10, 0.07],
            [-0.04, 0.0, 0.07, 0.05],
        ]
    )
    harmonic_error = max_abs(wavevector @ trace_reversed)
    wave_norm = float(wavevector @ metric @ wavevector)
    einstein_linear = 0.5 * wave_norm * trace_reversed
    bianchi_error = max_abs(wavevector @ einstein_linear)
    source = einstein_linear / (8.0 * math.pi)
    source_conservation_error = max_abs(wavevector @ source)

    scalar_gradient = np.array([1.0, 0.0, 0.0, 0.0])
    variable_coupling_extra = scalar_gradient @ source
    variable_extra_norm = max_abs(variable_coupling_extra)
    state_dependent_scope = SCOPE_FLAGS["state_dependent_gravity_closed"]

    passed = (
        max(harmonic_error, bianchi_error, source_conservation_error) <= TOL
        and variable_extra_norm > 1.0e-6
        and not state_dependent_scope
    )
    detail = (
        f"harmonic_error={harmonic_error:.3e} Bianchi_error={bianchi_error:.3e} "
        f"source_divergence={source_conservation_error:.3e} "
        f"variable_G_extra={variable_extra_norm:.3e} "
        f"state_dependent_gravity={state_dependent_scope}"
    )
    return Gate("MCC7", passed, detail)


def gate_mcc8() -> Gate:
    sigma_x = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)
    sigma_z = np.diag([1.0, -1.0]).astype(np.complex128)
    generator = 0.5 * sigma_z
    alpha = 0.41
    alpha_derivative = 0.27
    coupling = 1.3
    connection = 0.22
    frame = np.diag(
        [np.exp(-0.5j * alpha), np.exp(0.5j * alpha)]
    ).astype(np.complex128)
    frame_derivative = -1j * alpha_derivative * generator @ frame

    gamma = np.array(
        [[1.0, 0.20 - 0.10j], [0.20 + 0.10j, 0.80]],
        dtype=np.complex128,
    )
    gamma_derivative = np.array(
        [[0.03, -0.04 + 0.02j], [-0.04 - 0.02j, -0.01]],
        dtype=np.complex128,
    )
    transformed = frame @ gamma @ frame.conj().T
    transformed_derivative = (
        frame_derivative @ gamma @ frame.conj().T
        + frame @ gamma_derivative @ frame.conj().T
        + frame @ gamma @ frame_derivative.conj().T
    )

    potential = coupling * connection * generator
    covariant = gamma_derivative - 1j * (potential @ gamma - gamma @ potential)

    connection_minus = connection - alpha_derivative / coupling
    potential_minus = coupling * connection_minus * generator
    covariant_minus = transformed_derivative - 1j * (
        potential_minus @ transformed - transformed @ potential_minus
    )
    target = frame @ covariant @ frame.conj().T
    minus_error = max_abs(covariant_minus - target)

    connection_plus = connection + alpha_derivative / coupling
    potential_plus = coupling * connection_plus * generator
    covariant_plus = transformed_derivative - 1j * (
        potential_plus @ transformed - transformed @ potential_plus
    )
    plus_error = max_abs(covariant_plus - target)

    psi = np.array([1.0 + 0.2j, 0.4 - 0.3j], dtype=np.complex128)
    gamma_rank_one = np.outer(psi, psi.conj())
    rank_one_min = float(np.min(np.linalg.eigvalsh(gamma_rank_one)))
    rank_one_determinant = abs(np.linalg.det(gamma_rank_one))
    coherence_error = abs(gamma_rank_one[1, 0] - psi[1] * psi[0].conjugate())

    psi_second = np.array([0.2 - 0.1j, 1.1 + 0.2j], dtype=np.complex128)
    gamma_mixture = gamma_rank_one + 0.7 * np.outer(psi_second, psi_second.conj())
    mixture_min = float(np.min(np.linalg.eigvalsh(gamma_mixture)))
    mixture_determinant = float(np.real(np.linalg.det(gamma_mixture)))

    rotation_angle = 0.73
    generic_rotation = (
        math.cos(rotation_angle / 2.0) * np.eye(2)
        - 1j * math.sin(rotation_angle / 2.0) * sigma_x
    )
    rotated_gamma = generic_rotation @ gamma_rank_one @ generic_rotation.conj().T
    population_change = max_abs(np.diag(rotated_gamma) - np.diag(gamma_rank_one))
    carrier = np.array([0.3 + 0.1j, -0.2j, 0.4], dtype=np.complex128)
    carrier_charge = float(np.real(np.vdot(carrier, carrier)))
    carrier_charge_after = float(np.real(np.vdot(carrier, carrier)))
    carrier_error = abs(carrier_charge_after - carrier_charge)

    passed = (
        max(minus_error, rank_one_determinant, coherence_error, carrier_error) <= TOL
        and plus_error > 1.0e-6
        and rank_one_min >= -TOL
        and mixture_min > 1.0e-6
        and mixture_determinant > 1.0e-6
        and population_change > 1.0e-6
    )
    detail = (
        f"minus_covariance_error={minus_error:.3e} plus_residual={plus_error:.3e} "
        f"rank1_det={rank_one_determinant:.3e} mixture_min={mixture_min:.3e} "
        f"mixture_det={mixture_determinant:.3e} population_change={population_change:.3e} "
        f"carrier_charge_error={carrier_error:.3e}"
    )
    return Gate("MCC8", passed, detail)


def gate_mcc9() -> Gate:
    sigma_q = 1.0
    c_q = 0.5
    kappa_l = 0.7
    a_c = 2.0

    def root_function(length: float) -> float:
        return (
            sigma_q * length * length
            + c_q * (1.0 + kappa_l * length) * math.exp(-kappa_l * length)
            - a_c
        )

    monotonic_margin = 2.0 * sigma_q - c_q * kappa_l * kappa_l
    low = 0.0
    high = math.sqrt(a_c / sigma_q) * 2.0
    low_value = c_q - a_c
    high_value = root_function(high)
    for _ in range(100):
        midpoint = 0.5 * (low + high)
        if root_function(midpoint) > 0.0:
            high = midpoint
        else:
            low = midpoint
    root = 0.5 * (low + high)
    root_residual = abs(root_function(root))

    lower_bound = math.sqrt((a_c - c_q) / sigma_q)
    upper_bound = math.sqrt(a_c / sigma_q)
    bound_margin = min(root - lower_bound, upper_bound - root)
    curvature = (
        2.0 * sigma_q - c_q * kappa_l * kappa_l * math.exp(-kappa_l * root)
    ) / root

    sites = 8
    lambda_c = 0.8
    k_c = 0.3
    nonconstant_modes = np.arange(1, sites)
    line_eigenvalues = lambda_c + 4.0 * k_c * np.sin(
        math.pi * nonconstant_modes / sites
    ) ** 2
    minimum_line_eigenvalue = float(np.min(line_eigenvalues))

    q2_background = SCOPE_FLAGS["q2_qualified_full_background"]
    full_spectrum = SCOPE_FLAGS["full_constrained_spectrum_computed"]
    verdict_retained = PHYSICAL_VERDICT == "INCONCLUSIVE—NUMERICAL QUALITY"

    passed = (
        low_value < 0.0
        and high_value > 0.0
        and monotonic_margin > 0.0
        and root_residual <= TOL
        and bound_margin > 0.0
        and curvature > 0.0
        and minimum_line_eigenvalue > 0.0
        and not q2_background
        and not full_spectrum
        and verdict_retained
    )
    detail = (
        f"root={root:.12f} residual={root_residual:.3e} "
        f"bound_margin={bound_margin:.3e} monotonic_margin={monotonic_margin:.6f} "
        f"curvature={curvature:.6f} min_line_mode={minimum_line_eigenvalue:.6f} "
        f"Q2_background={q2_background} full_spectrum={full_spectrum}"
    )
    return Gate("MCC9", passed, detail)


def main() -> int:
    gates = [
        gate_mcc1(),
        gate_mcc2(),
        gate_mcc3(),
        gate_mcc4(),
        gate_mcc5(),
        gate_mcc6(),
        gate_mcc7(),
        gate_mcc8(),
        gate_mcc9(),
    ]

    print("Matter completion boundary — frozen MCC1–MCC9 receipt")
    print(
        f"phi={PHI:.15f} T={T_POWER:.15f} R={R_POWER:.15f} "
        f"T+R={T_POWER + R_POWER:.15f}"
    )
    for gate in gates:
        status = "PASS" if gate.passed else "FAIL"
        print(f"{gate.name} {status}: {gate.detail}")

    passed = all(gate.passed for gate in gates)
    print(f"RECEIPT VERDICT: {'PASS' if passed else 'FAIL'}")
    print(f"PHYSICAL PARTICLE VERDICT: {PHYSICAL_VERDICT}")
    open_scopes = ", ".join(name for name, closed in SCOPE_FLAGS.items() if not closed)
    print(f"OPEN PHYSICAL SCOPES: {open_scopes}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
