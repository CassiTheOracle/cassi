#!/usr/bin/env python3
"""Check the phase-defect working identities in report section 42.2.

Run: python computations/matter_formation_phase_vortex.py
The calculation fixes vacuum invariants on an annulus; it solves no core
boundary-value problem and supplies no particle-formation trajectory.
"""

import json
import math

import numpy as np
from scipy.integrate import quad, solve_ivp
from scipy.linalg import expm

RHO, A, D, V, G = 1.2, 0.83, 1.25, 0.9, 0.71
PHI = (1 + math.sqrt(5)) / 2
COMPOSITIONS = (PHI**-3, 0.0, -0.7, 0.8)
WINDINGS = (-2, -1, 0, 1, 2)
SIGMA = np.array([
    [[0, 1], [1, 0]],
    [[0, -1j], [1j, 0]],
    [[1, 0], [0, -1]],
], dtype=np.complex128)
T = SIGMA / 2
IDENTITY = np.eye(2, dtype=np.complex128)
ADJOINT = np.array([0.0, 0.0, V])
BASIS = np.eye(3)


def spinor(angle, composition, winding):
    psi = np.sqrt(RHO) * np.array([
        math.sqrt((1 + composition) / 2) * np.exp(1j * winding * angle),
        math.sqrt((1 - composition) / 2),
    ])
    derivative = np.array([1j * winding * psi[0], 0j])
    return psi, derivative


def component_energy(b, angle, composition, winding):
    psi, derivative = spinor(angle, composition, winding)
    covariant = derivative - 1j * np.einsum('a,aij,j->i', b, T, psi)
    adjoint_derivative = np.cross(b, ADJOINT)
    return float((A * np.vdot(covariant, covariant).real
                  + D * np.dot(adjoint_derivative, adjoint_derivative)) / 2)


def component_quadratic(angle, composition, winding):
    """Recover the quadratic from direct energy evaluations, without J_x."""
    e0 = component_energy(np.zeros(3), angle, composition, winding)
    plus = np.array([component_energy(e, angle, composition, winding) for e in BASIS])
    minus = np.array([component_energy(-e, angle, composition, winding) for e in BASIS])
    hessian = np.diag(plus + minus - 2 * e0)
    for i in range(3):
        for j in range(i):
            entry = (component_energy(BASIS[i] + BASIS[j], angle, composition, winding)
                     - plus[i] - plus[j] + e0)
            hessian[i, j] = hessian[j, i] = entry
    return hessian, (plus - minus) / 2


def candidate_connection(angle, composition, winding):
    f = A * RHO / (A * RHO + 4 * D * V**2)
    transverse = f * math.sqrt(1 - composition**2)
    return winding * np.array([
        transverse * math.cos(winding * angle),
        -transverse * math.sin(winding * angle),
        1 + composition,
    ])


def reduced_stiffness(composition):
    return 4 * A * RHO * D * V**2 * (1 - composition**2) / (A * RHO + 4 * D * V**2)


def normalized_difference(actual, expected):
    actual, expected = np.asarray(actual), np.asarray(expected)
    return float(np.max(np.abs(actual - expected) / np.maximum(1, np.abs(expected))))


def matrix_parts(matrix):
    return {'real': matrix.real.tolist(), 'imag': matrix.imag.tolist()}


def calculate():
    checks, exterior, annuli, caps = {}, [], [], []
    for composition in COMPOSITIONS:
        for winding in WINDINGS:
            label = f'c={composition:.17g},m={winding}'
            angles = np.linspace(0, 2 * math.pi, 17)
            connection_rows, energy_rows = [], []
            expected_energy = reduced_stiffness(composition) * winding**2 / 8
            hessian_minimum = math.inf
            for angle in angles:
                hessian, linear = component_quadratic(angle, composition, winding)
                numerical = np.linalg.solve(hessian, -linear)
                expected = candidate_connection(angle, composition, winding)
                energy = component_energy(numerical, angle, composition, winding)
                hessian_minimum = min(hessian_minimum, float(np.linalg.eigvalsh(hessian)[0]))
                connection_rows.append([float(angle), numerical.tolist(), expected.tolist(),
                                        normalized_difference(numerical, expected)])
                energy_rows.append([float(angle), energy, normalized_difference(energy, expected_energy)])
            checks[label + ':connection'] = max(row[3] for row in connection_rows) <= 1e-10
            checks[label + ':energy'] = max(row[2] for row in energy_rows) <= 1e-10
            checks[label + ':positive_hessian'] = hessian_minimum > 0

            # The Hessian is angle-independent. The linear term below is the
            # direct derivative of the component energy, not the closed b(phi).
            hessian0, _ = component_quadratic(0.0, composition, winding)
            inverse_hessian = np.linalg.inv(hessian0)

            def transport(angle, flat):
                psi, derivative = spinor(angle, composition, winding)
                tangents = -1j * np.einsum('aij,j->ai', T, psi)
                linear = A * np.real(tangents @ derivative.conj())
                b = -inverse_hessian @ linear
                matrix = np.einsum('a,aij->ij', b, T)
                return (1j * matrix @ flat.reshape(2, 2)).ravel()

            evolution = solve_ivp(transport, (0.0, 2 * math.pi), IDENTITY.ravel(),
                                  method='DOP853', rtol=1e-12, atol=1e-13)
            if not evolution.success:
                raise RuntimeError(evolution.message)
            holonomy = evolution.y[:, -1].reshape(2, 2)
            f = A * RHO / (A * RHO + 4 * D * V**2)
            axis = f * math.sqrt(1 - composition**2) * SIGMA[0] + composition * SIGMA[2]
            expected_holonomy = (-1.0)**winding * expm(1j * math.pi * winding * axis)
            expected_trace = (-1.0)**winding * math.cos(
                math.pi * winding * math.sqrt(composition**2 + f*f*(1-composition**2)))
            holonomy_error = normalized_difference(holonomy, expected_holonomy)
            unitarity = normalized_difference(holonomy.conj().T @ holonomy, IDENTITY)
            determinant = float(abs(np.linalg.det(holonomy) - 1))
            trace_error = float(abs(np.trace(holonomy) / 2 - expected_trace))
            checks[label + ':holonomy'] = holonomy_error <= 1e-9
            checks[label + ':trace'] = trace_error <= 1e-9
            checks[label + ':unitarity'] = unitarity <= 1e-9
            checks[label + ':determinant'] = determinant <= 1e-9
            if composition == COMPOSITIONS[0] and winding == 1:
                centre_distance = min(float(np.linalg.norm(holonomy - IDENTITY)),
                                      float(np.linalg.norm(holonomy + IDENTITY)))
                checks['physical_unit_winding_noncentral'] = centre_distance > 1e-3
            exterior.append({
                'composition': composition, 'winding': winding,
                'J_x': reduced_stiffness(composition),
                'connection_rows': connection_rows, 'energy_rows': energy_rows,
                'expected_angular_energy': expected_energy,
                'hessian_minimum': hessian_minimum,
                'holonomy': matrix_parts(holonomy),
                'expected_holonomy': matrix_parts(expected_holonomy),
                'half_trace': float(np.trace(holonomy).real / 2),
                'expected_half_trace': expected_trace, 'holonomy_error': holonomy_error,
                'trace_error': trace_error, 'unitarity_error': unitarity,
                'determinant_error': determinant,
            })

    composition = COMPOSITIONS[0]
    for winding in WINDINGS:
        def angular_integrand(angle):
            hessian, linear = component_quadratic(angle, composition, winding)
            return component_energy(np.linalg.solve(hessian, -linear), angle, composition, winding)

        angular, _ = quad(angular_integrand, 0, 2 * math.pi, epsabs=1e-12, epsrel=1e-12)
        for radius in (2, 4, 8):
            measured, error = quad(lambda r: angular / r, 1, radius, epsabs=1e-12, epsrel=1e-12)
            expected = math.pi * reduced_stiffness(composition) * winding**2 * math.log(radius) / 4
            difference = normalized_difference(measured, expected)
            checks[f'annulus:m={winding},R={radius}'] = difference <= 1e-10
            annuli.append({'winding': winding, 'R': radius, 'energy_per_length': measured,
                           'expected': expected, 'difference': difference, 'quadrature_error': error})

    for pole in (-1, 1):
        for winding in (-2, -1, 1, 2):
            order = abs(winding)
            beta0 = 0.0 if pole == 1 else math.pi
            delta = math.acos(composition) - beta0

            def profile(r):
                return beta0 + delta * r**order, order * delta * r**(order-1)

            def area_integrand(r):
                beta, derivative = profile(r)
                return winding * derivative * math.sin(beta) / 2

            def gradient_integrand(r):
                beta, derivative = profile(r)
                angular = winding**2 * math.sin(beta)**2 / r if r else 0.0
                return math.pi * D * V**2 * (r * derivative**2 + angular)

            measured, _ = quad(area_integrand, 0, 1, epsabs=1e-12, epsrel=1e-12)
            expected = winding * (pole - composition) / 2
            gradient_energy, _ = quad(gradient_integrand, 0, 1, epsabs=1e-12, epsrel=1e-12)
            checks[f'cap:p={pole},m={winding}:area'] = abs(measured - expected) <= 1e-10
            checks[f'cap:p={pole},m={winding}:gradient'] = math.isfinite(gradient_energy) and gradient_energy > 0
            caps.append({'pole': pole, 'winding': winding, 'orientation_area': measured,
                         'expected': expected, 'gradient_energy': gradient_energy,
                         'constant_density': RHO, 'constant_adjoint_norm': V})

    checks = {key: bool(value) for key, value in checks.items()}
    return {
        'verdict': 'PASS' if all(checks.values()) else 'FAIL',
        'checks': checks, 'inputs': {'rho': RHO, 'a': A, 'd': D, 'v_Q': V, 'g_Q': G},
        'exterior': exterior, 'annuli': annuli, 'caps': caps,
        'scope': 'Frozen-vacuum annular minimization, parallel transport, and admissible core caps only.',
        'stationary_core_solved': False, 'formation_trajectory': False,
        'complete_physical_matter_formation': False,
    }


if __name__ == '__main__':
    result = calculate()
    print(json.dumps(result, allow_nan=False, sort_keys=True, indent=2))
    raise SystemExit(0 if result['verdict'] == 'PASS' else 1)
