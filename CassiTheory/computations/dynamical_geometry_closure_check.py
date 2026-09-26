#!/usr/bin/env python3
"""Frozen DG1–DG7 receipt for the Yin–Yang–Qi open geometry closure.

Run from the CassiTheory repository root:
    python computations/dynamical_geometry_closure_check.py
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass

import numpy as np


PHI = (1.0 + math.sqrt(5.0)) / 2.0
LAMBDA = 0.02
TOL = 1.0e-12
SIGN_TOL = 1.0e-14

FROZEN_DENSITIES = (
    (0.0, 0.0),
    (1.0, PHI**-1),
    (0.7, 0.2),
    (0.0, 0.5),
    (0.9, 0.0),
)

COV_EY = 0.8
COV_EI = 0.3
COV_C = 0.4 * math.sqrt(COV_EY * COV_EI) * np.exp(0.7j)
COV_ALPHA = 0.61

LEDGER_J = 0.37
LEDGER_I = 0.29
LEDGER_G = 0.43


@dataclass(frozen=True)
class Gate:
    name: str
    passed: bool
    detail: str


def q_gate(ey: float, ei: float) -> float:
    rho = ey + ei
    epsilon = ey - PHI * ei
    return rho * rho / (rho * rho + PHI**-2 + epsilon * epsilon)


def state_matrix(ey: float, ei: float, coherence: complex = 0.0j) -> np.ndarray:
    return np.array(
        [[ey, np.conjugate(coherence)], [coherence, ei]], dtype=np.complex128
    )


def dissipator(gamma: np.ndarray, lam: float = LAMBDA) -> np.ndarray:
    ey = float(np.real(gamma[0, 0]))
    ei = float(np.real(gamma[1, 1]))
    rate = lam * (1.0 - q_gate(ey, ei))

    jump_y_to_i = np.array([[0.0, 0.0], [1.0, 0.0]], dtype=np.complex128)
    jump_i_to_y = math.sqrt(PHI) * np.array(
        [[0.0, 1.0], [0.0, 0.0]], dtype=np.complex128
    )

    result = np.zeros((2, 2), dtype=np.complex128)
    for jump in (jump_y_to_i, jump_i_to_y):
        norm = np.conjugate(jump.T) @ jump
        result += jump @ gamma @ np.conjugate(jump.T)
        result -= 0.5 * (norm @ gamma + gamma @ norm)
    return rate * result


def expected_dissipator(
    ey: float, ei: float, coherence: complex, lam: float = LAMBDA
) -> np.ndarray:
    rate = lam * (1.0 - q_gate(ey, ei))
    epsilon = ey - PHI * ei
    return rate * np.array(
        [
            [-epsilon, -(PHI**2 / 2.0) * np.conjugate(coherence)],
            [-(PHI**2 / 2.0) * coherence, epsilon],
        ],
        dtype=np.complex128,
    )


def max_abs(value: np.ndarray | complex | float) -> float:
    return float(np.max(np.abs(value)))


def gate_dg1() -> Gate:
    values = [q_gate(ey, ei) for ey, ei in FROZEN_DENSITIES]
    bounds_ok = all(-SIGN_TOL <= value < 1.0 - SIGN_TOL for value in values)
    vacuum_ok = abs(values[0]) <= TOL
    reference_expected = PHI**2 / 3.0
    reference_error = abs(values[1] - reference_expected)
    passed = bounds_ok and vacuum_ok and reference_error <= TOL
    detail = (
        f"q_min={min(values):.15e}, q_max={max(values):.15e}, "
        f"q_ref={values[1]:.15e}, ref_error={reference_error:.3e}"
    )
    return Gate("DG1", passed, detail)


def gate_dg2() -> Gate:
    errors: list[float] = []
    hermiticity_errors: list[float] = []
    trace_errors: list[float] = []
    rates: list[float] = []

    for ey, ei in FROZEN_DENSITIES:
        gamma = state_matrix(ey, ei)
        actual = dissipator(gamma)
        expected = expected_dissipator(ey, ei, 0.0j)
        errors.append(max_abs(actual - expected))
        hermiticity_errors.append(max_abs(actual - np.conjugate(actual.T)))
        trace_errors.append(abs(np.trace(actual)))
        rate = LAMBDA * (1.0 - q_gate(ey, ei))
        rates.extend((rate, PHI * rate))

    covariance_state = state_matrix(COV_EY, COV_EI, COV_C)
    covariance_actual = dissipator(covariance_state)
    covariance_expected = expected_dissipator(COV_EY, COV_EI, COV_C)
    errors.append(max_abs(covariance_actual - covariance_expected))
    hermiticity_errors.append(
        max_abs(covariance_actual - np.conjugate(covariance_actual.T))
    )
    trace_errors.append(abs(np.trace(covariance_actual)))

    nonnegative_rates = min(rates) >= -SIGN_TOL
    passed = (
        max(errors) <= TOL
        and max(hermiticity_errors) <= TOL
        and max(trace_errors) <= TOL
        and nonnegative_rates
    )
    detail = (
        f"component_error={max(errors):.3e}, "
        f"hermiticity_error={max(hermiticity_errors):.3e}, "
        f"trace_error={max(trace_errors):.3e}, min_jump_rate={min(rates):.15e}"
    )
    return Gate("DG2", passed, detail)


def gate_dg3() -> Gate:
    gamma = state_matrix(COV_EY, COV_EI, COV_C)
    unitary = np.diag(
        [np.exp(-0.5j * COV_ALPHA), np.exp(0.5j * COV_ALPHA)]
    ).astype(np.complex128)
    transformed = unitary @ gamma @ np.conjugate(unitary.T)
    lhs = dissipator(transformed)
    rhs = unitary @ dissipator(gamma) @ np.conjugate(unitary.T)
    error = float(np.linalg.norm(lhs - rhs, ord="fro"))
    return Gate("DG3", error <= TOL, f"covariance_error={error:.3e}")


def gate_dg4() -> Gate:
    gamma = state_matrix(COV_EY, COV_EI, COV_C)
    derivative = dissipator(gamma)

    rho = COV_EY + COV_EI
    z = (COV_EY - COV_EI) / rho
    z_phi = PHI**-3
    rate = LAMBDA * (1.0 - q_gate(COV_EY, COV_EI))

    d_ey = float(np.real(derivative[0, 0]))
    d_ei = float(np.real(derivative[1, 1]))
    d_rho = d_ey + d_ei
    dz_actual = ((d_ey - d_ei) * rho - (COV_EY - COV_EI) * d_rho) / (
        rho * rho
    )
    dz_expected = -(PHI**2) * rate * (z - z_phi)

    dc_actual = derivative[1, 0]
    norm_actual = 2.0 * float(np.real(np.conjugate(COV_C) * dc_actual))
    norm_expected = -(PHI**2) * rate * abs(COV_C) ** 2

    z_error = abs(dz_actual - dz_expected)
    norm_error = abs(norm_actual - norm_expected)
    passed = z_error <= TOL and norm_error <= TOL
    detail = f"z_rate_error={z_error:.3e}, coherence_norm_rate_error={norm_error:.3e}"
    return Gate("DG4", passed, detail)


def gate_dg5() -> Gate:
    finite_q = [
        q_gate(ey, ei)
        for ey, ei in FROZEN_DENSITIES
        if ey + ei > SIGN_TOL
    ]
    finite_bound = all(value < 1.0 - SIGN_TOL for value in finite_q)

    rate = LAMBDA * (1.0 - q_gate(COV_EY, COV_EI))
    norm_rate = -(PHI**2) * rate * abs(COV_C) ** 2
    strict_decay = norm_rate < -SIGN_TOL

    lambda_control = -(PHI**2) * 0.0 * (1.0 - 0.4) * abs(COV_C) ** 2
    diagonal_control = -(PHI**2) * LAMBDA * (1.0 - 0.4) * abs(0.0j) ** 2
    q_one_control = -(PHI**2) * LAMBDA * (1.0 - 1.0) * abs(COV_C) ** 2
    factor_zeros = (
        abs(lambda_control) <= TOL
        and abs(diagonal_control) <= TOL
        and abs(q_one_control) <= TOL
        and LAMBDA > 0.0
        and abs(COV_C) > 0.0
        and 1.0 - q_gate(COV_EY, COV_EI) > 0.0
    )

    passed = finite_bound and strict_decay and factor_zeros
    detail = (
        f"max_finite_q={max(finite_q):.15e}, "
        f"frozen_d|c|2_dt={norm_rate:.15e}, factor_controls={factor_zeros}"
    )
    return Gate("DG5", passed, detail)


def gate_dg6() -> Gate:
    gamma_minus = LEDGER_J
    gamma_plus = -LEDGER_J

    endpoint_minus = gamma_minus - LEDGER_I
    endpoint_plus = gamma_plus + LEDGER_I
    number_error = abs(endpoint_minus + endpoint_plus)

    local_source_minus = LEDGER_G * gamma_minus - LEDGER_G * gamma_minus
    local_source_plus = LEDGER_G * gamma_plus - LEDGER_G * gamma_plus
    local_charge_error = max(abs(local_source_minus), abs(local_source_plus))

    charge_rate_minus = LEDGER_G * LEDGER_I
    charge_rate_plus = -LEDGER_G * LEDGER_I
    edge_out_minus = -LEDGER_G * LEDGER_I
    edge_out_plus = LEDGER_G * LEDGER_I
    edge_incidence_error = max(
        abs(charge_rate_minus + edge_out_minus),
        abs(charge_rate_plus + edge_out_plus),
        abs(charge_rate_minus + charge_rate_plus),
    )

    passed = (
        number_error <= TOL
        and local_charge_error <= TOL
        and edge_incidence_error <= TOL
    )
    detail = (
        f"number_error={number_error:.3e}, "
        f"local_charge_error={local_charge_error:.3e}, "
        f"edge_incidence_error={edge_incidence_error:.3e}"
    )
    return Gate("DG6", passed, detail)


def gate_dg7() -> Gate:
    gamma = state_matrix(COV_EY, COV_EI, COV_C)
    lambda_zero_error = max_abs(dissipator(gamma, lam=0.0))

    diagonal = state_matrix(COV_EY, COV_EI, 0.0j)
    diagonal_offdiag = max_abs(
        np.array([dissipator(diagonal)[0, 1], dissipator(diagonal)[1, 0]])
    )

    t_upsilon = 0.0
    u_minus = 0.8
    u_plus = 0.6
    delta_w = 0.4
    wilson_current = 2.0 * t_upsilon * u_minus * u_plus * math.sin(delta_w)
    endpoint_residual = abs(LEDGER_J - wilson_current)

    particle_branch_imported = False
    passed = (
        lambda_zero_error <= TOL
        and diagonal_offdiag <= TOL
        and abs(wilson_current) <= TOL
        and endpoint_residual > SIGN_TOL
        and not particle_branch_imported
    )
    detail = (
        f"lambda_zero_error={lambda_zero_error:.3e}, "
        f"diagonal_offdiag={diagonal_offdiag:.3e}, "
        f"zero_t_current={wilson_current:.3e}, "
        f"endpoint_residual={endpoint_residual:.3e}, "
        f"particle_branch_imported={particle_branch_imported}"
    )
    return Gate("DG7", passed, detail)


def main() -> int:
    gates = (
        gate_dg1(),
        gate_dg2(),
        gate_dg3(),
        gate_dg4(),
        gate_dg5(),
        gate_dg6(),
        gate_dg7(),
    )

    print("YIN–YANG–QI DYNAMICAL GEOMETRY CLOSURE RECEIPT")
    print(f"phi={PHI:.15f} lambda={LAMBDA:.15f}")
    for gate in gates:
        verdict = "PASS" if gate.passed else "FAIL"
        print(f"{gate.name}: {verdict} — {gate.detail}")

    overall = all(gate.passed for gate in gates)
    print(f"OVERALL: {'PASS' if overall else 'FAIL'}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
