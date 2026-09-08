#!/usr/bin/env python3
"""Derive and exercise the conditional gauge-invariant neutral phase.

Run: python computations/matter_formation_neutral_phase.py
Frozen scope and schedule: matter-formation-continuum-report.md section 40.1.
This is a classical linear-wave calculation, not a matter-formation trajectory.
"""

import json
import math

import numpy as np
import sympy as sp
from scipy.linalg import eigh


PHI = (1.0 + math.sqrt(5.0)) / 2.0
INPUTS = {
    "rho": 1.2,
    "K_x": 0.83,
    "mu_x": 0.8,
    "v_Q": 0.9,
    "C_Psi": 1.3,
    "C_Phi": 0.7,
    "epsilon_x": 0.6,
    "g_Q": 0.71,
    "cos_beta": PHI ** -3,
}
PAULI = np.array([
    [[0, 1], [1, 0]],
    [[0, -1j], [1j, 0]],
    [[1, 0], [0, -1]],
], dtype=complex)


def exact_projection():
    """Schur complement for a unit common-phase derivative."""
    a, d, rho, v, g = sp.symbols("a d rho v g", positive=True)
    s, b = sp.symbols("s b", real=True)
    mass = sp.diag(g**2 * (a*rho/4 + d*v**2),
                   g**2 * (a*rho/4 + d*v**2), g**2*a*rho/4)
    source = a*g*rho/2 * sp.Matrix([s, 0, b])
    reduced = sp.expand(a*rho - (source.T * mass.inv() * source)[0])
    reduced = sp.factor(reduced.subs(s**2, 1-b**2))
    expected = a*rho*(1-b**2)*4*d*v**2/(a*rho + 4*d*v**2)
    identities = {
        "exact_schur_complement": sp.simplify(reduced-expected) == 0,
        "aligned_positive_endpoint": sp.simplify(reduced.subs(b, 1)) == 0,
        "aligned_negative_endpoint": sp.simplify(reduced.subs(b, -1)) == 0,
        "rigid_adjoint_limit": sp.simplify(
            sp.limit(reduced, d, sp.oo)-a*rho*(1-b**2)) == 0,
        "zero_adjoint_limit": sp.simplify(sp.limit(reduced, d, 0)) == 0,
    }
    return identities, str(reduced)


def direction_projection(a, d, b):
    """Compare the full matrix minimum with the direct field energy."""
    rho, v, g = (INPUTS[name] for name in ("rho", "v_Q", "g_Q"))
    psi = np.sqrt(rho) * np.array([math.sqrt((1+b)/2), math.sqrt((1-b)/2)])
    adjoint = np.array([0.0, 0.0, v])
    spin = np.array([np.vdot(psi, sigma @ psi).real for sigma in PAULI])
    mass = g*g * (a*rho/4*np.eye(3) + d*v*v*np.diag([1.0, 1.0, 0.0]))
    source = a*g*spin/2
    minimum = np.linalg.solve(mass, source)

    def component_energy(connection):
        generator = np.einsum("a,aij->ij", connection, PAULI)/2
        fundamental_derivative = 1j*psi - 1j*g*(generator @ psi)
        adjoint_derivative = g*np.cross(connection, adjoint)
        return float(a*np.vdot(fundamental_derivative, fundamental_derivative).real/2
                     + d*np.dot(adjoint_derivative, adjoint_derivative)/2)

    coefficient = a*rho*(1-b*b)*4*d*v*v/(a*rho + 4*d*v*v)
    measured = 2*component_energy(minimum)
    errors = [abs(measured-coefficient), float(np.linalg.norm(mass @ minimum-source))]
    costs = []
    for axis in range(3):
        for sign in (-1, 1):
            shift = np.zeros(3)
            shift[axis] = sign*0.1
            cost = component_energy(minimum+shift)-component_energy(minimum)
            errors.append(abs(cost-float(shift @ mass @ shift)/2))
            costs.append(float(cost))
    return {
        "a": a, "d": d, "cos_beta": b,
        "J": coefficient, "component_J": measured,
        "minimum_connection": minimum.tolist(),
        "max_residual": max(errors), "minimum_shift_cost": min(costs),
        "frozen_connection_J": a*rho,
        "abelian_only_J": a*rho*(1-b*b),
    }


def phase_matrices(k):
    """Gauss-reduced T,V for Theta=q cos(kx), Ax=a sin(kx)."""
    p = INPUTS
    rho, v, g, b = (p[name] for name in ("rho", "v_Q", "g_Q", "cos_beta"))
    direction = np.array([math.sqrt(1-b*b), b])
    a_t, a_x = p["C_Psi"]*rho, p["K_x"]*rho
    source_t, source_x = g*a_t*direction/2, g*a_x*direction/2
    mass_t = g*g*np.diag([a_t/4+p["C_Phi"]*v*v, a_t/4])
    mass_x = g*g*np.diag([a_x/4+v*v/p["mu_x"], a_x/4])
    eps = p["epsilon_x"]
    gauss = mass_t + eps*k*k*np.eye(2)
    inverse = np.linalg.solve(gauss, np.eye(2))
    kinetic = np.zeros((3, 3))
    kinetic[0, 0] = a_t-source_t @ inverse @ source_t
    kinetic[0, 1:] = eps*k*(source_t @ inverse)
    kinetic[1:, 0] = kinetic[0, 1:]
    kinetic[1:, 1:] = eps*np.eye(2)-eps*eps*k*k*inverse
    stiffness = np.zeros((3, 3))
    stiffness[0, 0] = a_x*k*k
    stiffness[0, 1:] = k*source_x
    stiffness[1:, 0] = stiffness[0, 1:]
    stiffness[1:, 1:] = mass_x
    return kinetic, stiffness


def linear_wave():
    """Actual fixed-step RK4 evolution of the frozen linear field mode."""
    kinetic, stiffness = phase_matrices(0.08)
    evolution = np.block([[np.zeros((3, 3)), np.eye(3)],
                          [-np.linalg.solve(kinetic, stiffness), np.zeros((3, 3))]])
    state = np.array([1e-3, 0, 0, 0, 0, 0], dtype=float)
    initial_energy = float(state[:3] @ stiffness @ state[:3])/2
    dt = 1/128
    rows = []
    for step in range(32*128+1):
        if step % 128 == 0:
            q, velocity = state[:3], state[3:]
            energy = float(velocity @ kinetic @ velocity + q @ stiffness @ q)/2
            rows.append({
                "time": step/128, "coordinates": q.tolist(),
                "velocities": velocity.tolist(),
                "relative_energy_error": (energy-initial_energy)/initial_energy,
            })
        if step == 32*128:
            break
        k1 = evolution @ state
        k2 = evolution @ (state+dt*k1/2)
        k3 = evolution @ (state+dt*k2/2)
        k4 = evolution @ (state+dt*k3)
        state += dt*(k1+2*k2+2*k3+k4)/6
    return rows


def main():
    checks, formula = exact_projection()
    projections = []
    for a, d in ((INPUTS["C_Psi"], INPUTS["C_Phi"]),
                 (INPUTS["K_x"], 1/INPUTS["mu_x"])):
        for b in (-0.7, 0.0, INPUTS["cos_beta"], 0.8):
            projections.append(direction_projection(a, d, b))
    checks["component_projection"] = all(row["max_residual"] < 1e-10 for row in projections)
    checks["positive_displacement_cost"] = all(row["minimum_shift_cost"] > 0 for row in projections)
    checks["frozen_and_abelian_projections_distinguished"] = all(
        row["frozen_connection_J"] > row["J"] and row["abelian_only_J"] > row["J"]
        for row in projections)
    jt = projections[2]["J"]
    jx = projections[6]["J"]
    spectra = []
    residuals = []
    for k in (0.0, 0.01, 0.02, 0.04, 0.08):
        kinetic, stiffness = phase_matrices(k)
        values, vectors = eigh(stiffness, kinetic)
        checks[f"positive_kinetic_k_{k}"] = bool(np.all(np.linalg.eigvalsh(kinetic) > 0))
        for index, value in enumerate(values):
            vec = vectors[:, index]
            residual = np.linalg.norm(stiffness @ vec-value*(kinetic @ vec))
            scale = max(1.0, (np.linalg.norm(stiffness)+abs(value)*np.linalg.norm(kinetic))*np.linalg.norm(vec))
            residuals.append(float(residual/scale))
        spectra.append({"k": k, "omega_squared": values.tolist()})
    speed_squared = jx/jt
    slope_error = abs(spectra[1]["omega_squared"][0]/0.01**2/speed_squared-1)
    checks["zero_frequency_at_zero_wave_number"] = abs(spectra[0]["omega_squared"][0]) < 1e-12
    checks["positive_nonzero_wave_spectrum"] = all(min(row["omega_squared"]) > 0 for row in spectra[1:])
    checks["sound_speed_limit"] = slope_error < 1e-3
    checks["generalized_eigen_residual"] = max(residuals) < 1e-10
    wave = linear_wave()
    checks["linear_wave_energy"] = max(abs(row["relative_energy_error"]) for row in wave) < 1e-9
    checks["finite_wave_values"] = bool(np.all(np.isfinite([
        value for row in wave for value in row["coordinates"]+row["velocities"]])))
    passed = all(checks.values())
    result = {
        "verdict": "PASS" if passed else "FAIL",
        "scope": "Conditional classical neutral-phase projection and linear wave; no quantum-state selection",
        "checks": checks, "inputs": INPUTS, "exact_J": formula,
        "phase_coefficients": {"J_t": jt, "J_x": jx, "sound_speed_squared": speed_squared,
                               "vartheta_time": jt/4, "vartheta_space": jx/4},
        "projections": projections, "spectra": spectra,
        "max_generalized_eigen_residual": max(residuals),
        "small_k_relative_slope_error": slope_error,
        "wave_method": "RK4, dt=1/128", "wave": wave,
        "complete_physical_matter_formation": False,
    }
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
