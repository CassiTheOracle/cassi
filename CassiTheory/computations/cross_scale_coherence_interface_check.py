#!/usr/bin/env python3
"""Frozen EC1–EC7 receipt for the cross-scale coherence interface.

Run from the CassiTheory repository root:
    python computations/cross_scale_coherence_interface_check.py
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass

import numpy as np


PHI = (1.0 + math.sqrt(5.0)) / 2.0
HBAR = 1.0
N_STEPS = 5
T_POWER = PHI**-1
TOL = 1.0e-11

A = np.array(
    [[1.25, 0.18 - 0.06j], [0.18 + 0.06j, 0.85]], dtype=np.complex128
)
B = np.array(
    [[0.95, -0.11 + 0.04j], [-0.11 - 0.04j, 1.15]], dtype=np.complex128
)
K0 = np.array(
    [[0.22 + 0.04j, -0.09 + 0.05j], [0.07 - 0.03j, 0.18 - 0.02j]],
    dtype=np.complex128,
)

ALPHA = 0.37
BETA = -0.61
H_IN = np.diag([0.70, -0.20]).astype(np.complex128)
H_OUT = np.diag([-0.10, 0.50]).astype(np.complex128)
V = np.diag([0.31, 0.19]).astype(np.complex128)
DT = 0.17
Q = np.diag([0.5, -0.5]).astype(np.complex128)

A_SINGULAR = np.diag([1.0, 0.8]).astype(np.complex128)
B_SINGULAR = np.diag([0.9, 0.0]).astype(np.complex128)
C_SINGULAR = np.array([[0.20, 0.0], [0.10j, 0.0]], dtype=np.complex128)

TEST_EY = 1.0
TEST_EI = PHI**-1
TEST_C = 0.12 + 0.07j
TEST_LAMBDA = 0.20
TEST_V = 0.30

SCOPE_FLAGS = {
    "q_cross_coherence_transfer_coupling": False,
    "cosmological_bubble_interpretation": False,
    "geometry_backreaction_equation": False,
    "mixed_stress_constitutive_map": False,
    "microscopic_reservoir": False,
    "local_su2_particle_import": False,
}


@dataclass(frozen=True)
class Gate:
    name: str
    passed: bool
    detail: str


def max_abs(value: np.ndarray | complex | float) -> float:
    return float(np.max(np.abs(value)))


def hermitian_power(matrix: np.ndarray, exponent: float) -> np.ndarray:
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    powered = eigenvalues**exponent
    return (eigenvectors * powered) @ eigenvectors.conj().T


def block_state(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    return np.block([[a, c], [c.conj().T, b]])


def interface_sources(v: np.ndarray, c: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    source_in = -1j / HBAR * (v @ c.conj().T - c @ v.conj().T)
    source_out = -1j / HBAR * (v.conj().T @ c - c.conj().T @ v)
    return source_in, source_out


def relative_frame(angle: float) -> np.ndarray:
    return np.diag([np.exp(-0.5j * angle), np.exp(0.5j * angle)])


def unitary_from_hermitian(hamiltonian: np.ndarray, duration: float) -> np.ndarray:
    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    phases = np.exp(-1j * eigenvalues * duration / HBAR)
    return (eigenvectors * phases) @ eigenvectors.conj().T


def propagate(
    seed: np.ndarray, left: np.ndarray, right: np.ndarray, steps: int
) -> np.ndarray:
    result = seed.copy()
    for _ in range(steps):
        result = left @ result @ right.conj().T
    return result


def base_blocks() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    sqrt_a = hermitian_power(A, 0.5)
    sqrt_b = hermitian_power(B, 0.5)
    c = sqrt_a @ K0 @ sqrt_b
    gamma = block_state(A, B, c)
    return sqrt_a, sqrt_b, c, gamma


def gate_ec1() -> Gate:
    _, _, c, gamma = base_blocks()
    min_a = float(np.min(np.linalg.eigvalsh(A)))
    min_b = float(np.min(np.linalg.eigvalsh(B)))
    k_norm = float(np.linalg.norm(K0, 2))
    schur = A - c @ np.linalg.inv(B) @ c.conj().T
    schur_min = float(np.min(np.linalg.eigvalsh(schur)))
    gamma_min = float(np.min(np.linalg.eigvalsh(gamma)))

    b_pinv = np.linalg.pinv(B_SINGULAR)
    support_residual = max_abs(
        (np.eye(2, dtype=np.complex128) - B_SINGULAR @ b_pinv)
        @ C_SINGULAR.conj().T
    )
    singular_schur = (
        A_SINGULAR - C_SINGULAR @ b_pinv @ C_SINGULAR.conj().T
    )
    singular_schur_min = float(np.min(np.linalg.eigvalsh(singular_schur)))
    singular_gamma_min = float(
        np.min(np.linalg.eigvalsh(block_state(A_SINGULAR, B_SINGULAR, C_SINGULAR)))
    )

    unsupported = C_SINGULAR.copy()
    unsupported[0, 1] = 0.05
    unsupported_residual = max_abs(
        (np.eye(2, dtype=np.complex128) - B_SINGULAR @ b_pinv)
        @ unsupported.conj().T
    )
    unsupported_min = float(
        np.min(np.linalg.eigvalsh(block_state(A_SINGULAR, B_SINGULAR, unsupported)))
    )

    passed = (
        min_a > 0.0
        and min_b > 0.0
        and k_norm < 1.0
        and schur_min >= -TOL
        and gamma_min >= -TOL
        and support_residual <= TOL
        and singular_schur_min >= -TOL
        and singular_gamma_min >= -TOL
        and unsupported_residual > TOL
        and unsupported_min < -1.0e-6
    )
    detail = (
        f"min_A={min_a:.3e} min_B={min_b:.3e} ||K0||op={k_norm:.3e} "
        f"min_block={gamma_min:.3e} min_Schur={schur_min:.3e} "
        f"singular_support={support_residual:.3e} "
        f"unsupported_support={unsupported_residual:.3e} "
        f"unsupported_min={unsupported_min:.3e}"
    )
    return Gate("EC1", passed, detail)


def gate_ec2() -> Gate:
    _, _, c, _ = base_blocks()
    source_in, source_out = interface_sources(V, c)
    u_in = relative_frame(ALPHA)
    u_out = relative_frame(BETA)

    a_gauge = u_in @ A @ u_in.conj().T
    b_gauge = u_out @ B @ u_out.conj().T
    c_gauge = u_in @ c @ u_out.conj().T
    v_gauge = u_in @ V @ u_out.conj().T

    sqrt_a_gauge = hermitian_power(a_gauge, 0.5)
    sqrt_b_gauge = hermitian_power(b_gauge, 0.5)
    invsqrt_a_gauge = hermitian_power(a_gauge, -0.5)
    invsqrt_b_gauge = hermitian_power(b_gauge, -0.5)
    k_gauge = invsqrt_a_gauge @ c_gauge @ invsqrt_b_gauge
    k_target = u_in @ K0 @ u_out.conj().T
    k_error = max_abs(k_gauge - k_target)
    reconstruction_error = max_abs(
        sqrt_a_gauge @ k_gauge @ sqrt_b_gauge - c_gauge
    )

    source_in_gauge, source_out_gauge = interface_sources(v_gauge, c_gauge)
    source_in_error = max_abs(
        source_in_gauge - u_in @ source_in @ u_in.conj().T
    )
    source_out_error = max_abs(
        source_out_gauge - u_out @ source_out @ u_out.conj().T
    )
    worst = max(k_error, reconstruction_error, source_in_error, source_out_error)
    detail = (
        f"K_error={k_error:.3e} reconstruction_error={reconstruction_error:.3e} "
        f"source_in_error={source_in_error:.3e} "
        f"source_out_error={source_out_error:.3e}"
    )
    return Gate("EC2", worst <= TOL, detail)


def gate_ec3() -> Gate:
    _, _, c, _ = base_blocks()
    source_in, source_out = interface_sources(V, c)
    hermitian_error = max(
        max_abs(source_in - source_in.conj().T),
        max_abs(source_out - source_out.conj().T),
    )
    number_residual = abs(np.trace(source_in) + np.trace(source_out))
    charge_residual = abs(
        np.trace(Q @ source_in) + np.trace(Q @ source_out)
    )
    intertwiner_error = max_abs(Q @ V - V @ Q)
    worst = max(
        hermitian_error,
        float(number_residual),
        float(charge_residual),
        intertwiner_error,
    )
    detail = (
        f"Hermitian_error={hermitian_error:.3e} "
        f"number_residual={number_residual:.3e} "
        f"charge_residual={charge_residual:.3e} "
        f"intertwiner_error={intertwiner_error:.3e}"
    )
    return Gate("EC3", worst <= TOL, detail)


def gate_ec4() -> Gate:
    left_unitary = relative_frame(0.23)
    right_unitary = relative_frame(-0.41)
    seed_norm = float(np.linalg.norm(K0, "fro"))

    closed = propagate(K0, left_unitary, right_unitary, N_STEPS)
    one_sided = propagate(
        K0, math.sqrt(T_POWER) * left_unitary, right_unitary, N_STEPS
    )
    symmetric = propagate(
        K0,
        math.sqrt(T_POWER) * left_unitary,
        math.sqrt(T_POWER) * right_unitary,
        N_STEPS,
    )
    closed_ratio = float(np.linalg.norm(closed, "fro")) / seed_norm
    one_sided_ratio = float(np.linalg.norm(one_sided, "fro")) / seed_norm
    symmetric_ratio = float(np.linalg.norm(symmetric, "fro")) / seed_norm
    one_sided_target = PHI ** (-N_STEPS / 2.0)
    symmetric_target = PHI**-N_STEPS

    closed_error = abs(closed_ratio - 1.0)
    one_sided_error = abs(one_sided_ratio - one_sided_target)
    symmetric_error = abs(symmetric_ratio - symmetric_target)
    bound_excess = max(
        0.0,
        closed_ratio - 1.0,
        one_sided_ratio - one_sided_target,
        symmetric_ratio - symmetric_target,
    )

    forward_power = T_POWER**N_STEPS
    returned_power = sum(
        (1.0 - T_POWER) * T_POWER**step for step in range(N_STEPS)
    )
    power_residual = abs(forward_power + returned_power - 1.0)
    passed = max(
        closed_error,
        one_sided_error,
        symmetric_error,
        bound_excess,
        power_residual,
    ) <= TOL
    detail = (
        f"closed={closed_ratio:.12f} one_sided={one_sided_ratio:.12f} "
        f"symmetric={symmetric_ratio:.12f} bound_excess={bound_excess:.3e} "
        f"power_residual={power_residual:.3e}"
    )
    return Gate("EC4", passed, detail)


def gate_ec5() -> Gate:
    _, _, c, _ = base_blocks()
    source_in, _ = interface_sources(V, c)
    source_norm = float(np.linalg.norm(source_in, "fro"))
    source_bound = (
        2.0 / HBAR * float(np.linalg.norm(V, 2)) * float(np.linalg.norm(c, "fro"))
    )
    bound_excess = max(0.0, source_norm - source_bound)

    rho = TEST_EY + TEST_EI
    epsilon = TEST_EY - PHI * TEST_EI
    q_test = rho * rho / (rho * rho + PHI**-2 + epsilon * epsilon)
    gamma_c = PHI**2 / 2.0 * TEST_LAMBDA * (1.0 - q_test)
    v_test = TEST_V * np.eye(2, dtype=np.complex128)
    c_test = np.array(
        [[0.0, 0.0], [-1j * gamma_c * TEST_C / TEST_V, 0.0]],
        dtype=np.complex128,
    )
    witness_source, _ = interface_sources(v_test, c_test)
    transverse_source = witness_source[1, 0]
    source_error = abs(transverse_source - gamma_c * TEST_C)

    aligned_overlap = float(np.real(np.conjugate(TEST_C) * transverse_source))
    dg40_residual = abs(aligned_overlap - gamma_c * abs(TEST_C) ** 2)
    quadrature_overlap = float(
        np.real(np.conjugate(1j * TEST_C) * transverse_source)
    )
    anti_overlap = float(np.real(np.conjugate(-TEST_C) * transverse_source))

    zero_v_sources = interface_sources(np.zeros_like(V), c)
    zero_c_sources = interface_sources(V, np.zeros_like(c))
    zero_v_error = max(max_abs(value) for value in zero_v_sources)
    zero_c_error = max(max_abs(value) for value in zero_c_sources)

    passed = (
        bound_excess <= TOL
        and source_error <= TOL
        and dg40_residual <= TOL
        and aligned_overlap > 0.0
        and abs(quadrature_overlap) <= TOL
        and anti_overlap < 0.0
        and zero_v_error <= TOL
        and zero_c_error <= TOL
    )
    detail = (
        f"source_norm={source_norm:.3e} bound={source_bound:.3e} "
        f"gamma_c={gamma_c:.12f} witness_error={source_error:.3e} "
        f"DG40_residual={dg40_residual:.3e} "
        f"overlaps=({aligned_overlap:.3e},{quadrature_overlap:.3e},{anti_overlap:.3e}) "
        f"zero_errors=({zero_v_error:.3e},{zero_c_error:.3e})"
    )
    return Gate("EC5", passed, detail)


def gate_ec6() -> Gate:
    _, _, _, gamma = base_blocks()
    hamiltonian = np.block([[H_IN, V], [V.conj().T, H_OUT]])
    evolution = unitary_from_hermitian(hamiltonian, DT)
    evolved = evolution @ gamma @ evolution.conj().T
    identity = np.eye(4, dtype=np.complex128)
    q_total = np.block(
        [[Q, np.zeros((2, 2))], [np.zeros((2, 2)), Q]]
    ).astype(np.complex128)

    unitarity_error = max_abs(evolution @ evolution.conj().T - identity)
    evolved_min = float(np.min(np.linalg.eigvalsh(evolved)))
    trace_residual = abs(np.trace(evolved) - np.trace(gamma))
    charge_residual = abs(
        np.trace(q_total @ evolved) - np.trace(q_total @ gamma)
    )
    energy_residual = abs(
        np.trace(hamiltonian @ evolved) - np.trace(hamiltonian @ gamma)
    )
    passed = (
        unitarity_error <= TOL
        and evolved_min >= -TOL
        and trace_residual <= TOL
        and charge_residual <= TOL
        and energy_residual <= TOL
    )
    detail = (
        f"unitarity_error={unitarity_error:.3e} min_evolved={evolved_min:.3e} "
        f"trace_residual={trace_residual:.3e} "
        f"charge_residual={charge_residual:.3e} "
        f"energy_residual={energy_residual:.3e}"
    )
    return Gate("EC6", passed, detail)


def gate_ec7() -> Gate:
    selected = [name for name, enabled in SCOPE_FLAGS.items() if enabled]
    passed = not selected
    detail = (
        f"declared_false={len(SCOPE_FLAGS) - len(selected)}/{len(SCOPE_FLAGS)} "
        f"selected={','.join(selected) if selected else 'none'}"
    )
    return Gate("EC7", passed, detail)


def main() -> int:
    gates = (
        gate_ec1(),
        gate_ec2(),
        gate_ec3(),
        gate_ec4(),
        gate_ec5(),
        gate_ec6(),
        gate_ec7(),
    )

    print("CROSS-SCALE COHERENCE INTERFACE RECEIPT")
    print(f"phi={PHI:.15f} N={N_STEPS} tolerance={TOL:.1e}")
    for gate in gates:
        verdict = "PASS" if gate.passed else "FAIL"
        print(f"{gate.name}: {verdict}—{gate.detail}")

    overall = all(gate.passed for gate in gates)
    print(f"OVERALL: {'PASS' if overall else 'FAIL'}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
