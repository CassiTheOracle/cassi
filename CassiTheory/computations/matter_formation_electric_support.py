#!/usr/bin/env python3
"""Qualify conditional stationary electric support and common-charge dilution.

Run: python computations/matter_formation_electric_support.py
Inputs, controls and tolerances: matter-formation-continuum-report.md section 41.1.
The interval calculation and Gaussian initial states are not formation trajectories.
"""
from __future__ import annotations

import json
import math

import numpy as np
import sympy as sp
from scipy.integrate import quad

PHI = (1.0 + math.sqrt(5.0)) / 2.0
INPUTS = {"rho": 1.2, "v_Q": 0.9, "g_Q": 0.71, "C_Psi": 1.3,
          "C_Phi": 0.75, "epsilon_x": 0.26, "cos_beta": PHI**-3,
          "scale_measure": 1.0, "P_N": 1.0}
GRIDS = (15, 31, 63)
RADII = (1.0, 2.0, 4.0, 8.0)


def exact_temporal() -> tuple[dict, dict]:
    """Differentiate both component kinetic terms before doing the projection."""
    rho, cp, cf, v, g = sp.symbols("rho C_Psi C_Phi v g", positive=True)
    t, u = sp.symbols("tan_half_beta u", real=True)
    avec = sp.Matrix(sp.symbols("a1 a2 a3", real=True))
    sigma = (sp.Matrix([[0, 1], [1, 0]]), sp.Matrix([[0, -sp.I], [sp.I, 0]]),
             sp.diag(1, -1))
    psi = sp.sqrt(rho / (1 + t*t)) * sp.Matrix([1, t])
    adj = sp.Matrix([0, 0, v])
    op = sum((avec[j]*sigma[j]/2 for j in range(3)), sp.zeros(2))
    dpsi = sp.I*(u*sp.eye(2) - g*op)*psi
    dadj = g*avec.cross(adj)
    kinetic = sp.simplify(cp*(dpsi.conjugate().T*dpsi)[0]/2 + cf*dadj.dot(dadj)/2)
    source_psi = sp.Matrix([cp*g*sp.im((psi.conjugate().T*sigma[j]*dpsi)[0])/2
                            for j in range(3)])
    source_adj = -cf*g*adj.cross(dadj)
    source = sp.simplify(source_psi + source_adj)
    mass = sp.simplify(sp.hessian(kinetic, avec))
    stokes = sp.Matrix([(psi.conjugate().T*s*psi)[0] for s in sigma])
    b = sp.simplify(cp*g*stokes/2)
    expected_mass = g*g*(cp*rho*sp.eye(3)/4 + cf*(v*v*sp.eye(3)-adj*adj.T))
    astar = sp.simplify(mass.inv()*b*u)
    inertia = sp.factor(cp*rho-(b.T*mass.inv()*b)[0])
    expected_j = 4*cp*rho*cf*v*v*(2*t/(1+t*t))**2/(cp*rho+4*cf*v*v)
    shifted = avec-astar
    completed = inertia*u*u/2 + (shifted.T*mass*shifted)[0]/2
    horizontal = dict(zip(avec, astar))
    hdpsi, hdadj = sp.simplify(dpsi.subs(horizontal)), sp.simplify(dadj.subs(horizontal))
    momentum = sp.simplify(cp*sp.im((psi.conjugate().T*hdpsi)[0]))
    henergy = sp.simplify(cp*(hdpsi.conjugate().T*hdpsi)[0]/2 + cf*hdadj.dot(hdadj)/2)
    residuals = {
        "component_mass": mass-expected_mass,
        "gauss_variation_sign": sp.Matrix([sp.diff(kinetic, a) for a in avec])+source,
        "source_decomposition": source-(b*u-mass*avec),
        "stokes_norm": stokes.dot(stokes)-rho*rho,
        "projected_inertia": inertia-expected_j,
        "completed_square": kinetic-completed,
        "horizontal_gauss": source.subs(horizontal),
        "horizontal_momentum": momentum-inertia*u,
        "horizontal_energy": henergy-inertia*u*u/2,
    }
    reduced = {key: [sp.simplify(x) for x in value] if isinstance(value, sp.MatrixBase)
               else [sp.simplify(value)] for key, value in residuals.items()}
    checks = {key: all(x == 0 for x in values) for key, values in reduced.items()}
    return checks, {"residuals": {key: [str(x) for x in values] for key, values in reduced.items()},
                    "mass_matrix": str(mass), "b": str(b), "J_t": str(inertia),
                    "a_star": str(astar), "canonical_momentum": str(momentum),
                    "assumptions": "Positive coefficients, nonzero vacuum norms, sin(beta)^2>0; stationary profiles up to one common U(1) rotation; finite energy and zero boundary work.",
                    "frequency_argument": "The completed square bounds the exterior kinetic density below by J_t,infinity*omega_N^2/4 outside a sufficiently large ball. Finite energy forces omega_N=0.",
                    "electric_equality": "Covariant Gauss integration gives a sum of nonnegative gradient and mass forms. Equality makes A_0 covariantly constant and zero wherever rho>0; constant norm then makes it zero throughout the connected domain, including an empty bounded core."}


def charge_calculation() -> tuple[dict, dict]:
    """Evaluate the actual vacuum velocities, then integrate radial densities."""
    p = INPUTS
    c, s = p["cos_beta"], math.sqrt(1-p["cos_beta"]**2)
    sigma = np.array([[[0, 1], [1, 0]], [[0, -1j], [1j, 0]], [[1, 0], [0, -1]]])
    psi = math.sqrt(p["rho"])*np.array([math.sqrt((1+c)/2), math.sqrt((1-c)/2)])
    adj = np.array([0., 0., p["v_Q"]])
    stokes = np.array([np.vdot(psi, a@psi).real for a in sigma])
    mass = p["g_Q"]**2*(p["C_Psi"]*p["rho"]*np.eye(3)/4
             + p["C_Phi"]*(np.dot(adj, adj)*np.eye(3)-np.outer(adj, adj)))
    b = p["g_Q"]*p["C_Psi"]*stokes/2
    astar = np.linalg.solve(mass, b)
    hdpsi = 1j*(np.eye(2)-p["g_Q"]*np.einsum("a,aij->ij", astar, sigma)/2)@psi
    hdadj = p["g_Q"]*np.cross(astar, adj)
    j = p["C_Psi"]*np.vdot(psi, hdpsi).imag
    energy_coefficient = (p["C_Psi"]*np.vdot(hdpsi, hdpsi).real+p["C_Phi"]*np.dot(hdadj, hdadj))/2
    formula = 4*p["C_Psi"]*p["rho"]*p["C_Phi"]*p["v_Q"]**2*s*s/(p["C_Psi"]*p["rho"]+4*p["C_Phi"]*p["v_Q"]**2)
    gauss_psi = p["C_Psi"]*p["g_Q"]*np.array([np.vdot(psi, a@hdpsi).imag/2 for a in sigma])
    gauss_adj = -p["C_Phi"]*p["g_Q"]*np.cross(adj, hdadj)
    checks = {"numeric_inertia": abs(j-formula) <= 1e-11,
              "numeric_gauss": np.max(np.abs(gauss_psi+gauss_adj)) <= 1e-11,
              "numeric_energy_coefficient": abs(energy_coefficient-j/2) <= 1e-11,
              "positive_vacuum_inertia": j > 0}
    rows = []
    for radius in RADII:
        def speed(r):
            return p["P_N"]*math.exp(-(r/radius)**2)/(math.pi**1.5*radius**3*j)
        charge, charge_error = quad(lambda r: 4*math.pi*r*r*j*speed(r), 0, np.inf, epsabs=1e-13, epsrel=1e-13)
        energy, energy_error = quad(lambda r: 4*math.pi*r*r*energy_coefficient*speed(r)**2, 0, np.inf, epsabs=1e-13, epsrel=1e-13)
        expected = p["P_N"]**2/(2*j*(2*math.pi)**1.5*radius**3)
        checks[f"charge_R{radius:g}"] = abs(charge-p["P_N"]) <= 1e-11
        checks[f"energy_R{radius:g}"] = abs(energy-expected) <= 1e-11
        rows.append({"R": radius, "P_N": charge, "energy": energy,
                     "quadrature_errors": [charge_error, energy_error], "expected_energy": expected})
    return checks, {"J_t": float(j), "mass_matrix": mass.tolist(), "b": b.tolist(),
                    "unit_u_velocities": {"psi_real": hdpsi.real.tolist(), "psi_imag": hdpsi.imag.tolist(),
                                          "adjoint": hdadj.tolist(), "a_star": astar.tolist()},
                    "gauss_psi": gauss_psi.tolist(), "gauss_adjoint": gauss_adj.tolist(), "rows": rows,
                    "scope": "Exact constrained initial data at chi_C=0, zero electric momentum and vacuum field coordinates. P_N has action units. Energy tends to zero as R^-3 at fixed nonzero P_N; nonnegative full energy cannot attain zero at that charge. No real-time spreading or exclusion of local metastability is inferred."}


def interval_calculation() -> tuple[dict, dict]:
    """Assemble block Hessians directly from each edge's Rodrigues matrix."""
    p = INPUTS
    axis = np.array([1., 2., -1.])/math.sqrt(6)
    cross = np.array([[0., -axis[2], axis[1]], [axis[2], 0., -axis[0]], [-axis[1], axis[0], 0.]])
    checks, rows, negative, raw = {}, [], [], []
    for n in GRIDS:
        h = 2/(n+1)
        x = np.linspace(-1, 1, n+2)
        angles = .11*np.cos(math.pi*(x[:-1]+x[1:])/2)
        rotations = [np.eye(3)+math.sin(a)*cross+(1-math.cos(a))*(cross@cross) for a in angles]
        edge_hessian = np.zeros((3*(n+2), 3*(n+2)))
        for i, rot in enumerate(rotations):
            left, right = slice(3*i, 3*i+3), slice(3*i+3, 3*i+6)
            edge_hessian[left, left] += np.eye(3)/h
            edge_hessian[right, right] += np.eye(3)/h
            edge_hessian[right, left] -= rot/h
            edge_hessian[left, right] -= rot.T/h
        for profile in ("uniform", "empty_core"):
            norm = np.ones(n)
            if profile == "empty_core":
                s = np.clip((np.abs(x[1:-1])-.25)/.25, 0, 1)
                norm = s**3*(10-15*s+6*s*s)
            beta = .2*np.sin(math.pi*x[1:-1])
            adj = p["v_Q"]*norm[:, None]*np.column_stack((np.sin(beta), np.zeros(n), np.cos(beta)))
            masses = p["g_Q"]**2*(p["C_Psi"]*p["rho"]*norm[:, None, None]*np.eye(3)[None, :, :]/4
                        + p["C_Phi"]*(np.einsum("na,na->n", adj, adj)[:, None, None]*np.eye(3)[None, :, :]
                        - np.einsum("na,nb->nab", adj, adj)))
            matter_hessian = np.zeros_like(edge_hessian)
            for i, mass in enumerate(masses, 1):
                sl = slice(3*i, 3*i+3)
                matter_hessian[sl, sl] = h*mass
            full = p["epsilon_x"]*edge_hessian+matter_hessian
            interior = full[3:-3, 3:-3]
            vals = np.linalg.eigvalsh(interior/h)
            bound = 4*p["epsilon_x"]/h**2*math.sin(math.pi/(2*(n+1)))**2
            a = np.zeros((n+2, 3))
            a[0] = [.2, -.1, .3]
            rhs = -full[3:-3, :3]@a[0]
            a[1:-1] = np.linalg.solve(interior, rhs).reshape(n, 3)
            force = full@a.ravel()
            boundary_work = float(np.dot(a[0], force[:3]))
            boundary_energy = float(a.ravel()@full@a.ravel()/2)
            edge_energy = p["epsilon_x"]/(2*h)*sum(np.dot(a[i+1]-rot@a[i], a[i+1]-rot@a[i]) for i, rot in enumerate(rotations))
            matter_energy = h*np.einsum("na,nab,nb->", a[1:-1], masses, a[1:-1])/2
            residual = float(np.max(np.abs(force[3:-3]))/max(1., np.max(np.abs(rhs))))
            identity_residual = abs(2*boundary_energy-boundary_work)/max(1., abs(boundary_work))
            key = f"{profile}_N{n}"
            checks[key+"_positive_bound"] = float(vals[0]) >= bound-1e-10*max(1., bound)
            checks[key+"_stationary"] = residual <= 1e-10
            checks[key+"_boundary_work"] = identity_residual <= 1e-10 and boundary_energy > 0 and boundary_work > 0
            checks[key+"_energy_reconstruction"] = abs(boundary_energy-edge_energy-matter_energy) <= 1e-10
            rows.append({"N": n, "profile": profile, "lowest_eigenvalue": float(vals[0]),
                         "dirichlet_lower_bound": bound, "boundary_energy": boundary_energy,
                         "boundary_work": boundary_work, "stationarity_residual": residual,
                         "boundary_identity_residual": identity_residual})
            raw.append({"N": n, "profile": profile, "x": x.tolist(), "rho": (p["rho"]*norm).tolist(),
                        "adjoint": adj.tolist(), "link_angles": angles.tolist(), "eigenvalues": vals.tolist(),
                        "boundary_solution": a.tolist(), "boundary_force": force[:3].tolist(),
                        "edge_energy": float(edge_energy), "matter_energy": float(matter_energy)})
            if profile == "uniform":
                bad_vals = np.linalg.eigvalsh((-p["epsilon_x"]*edge_hessian+matter_hessian)[3:-3, 3:-3]/h)
                negative.append({"N": n, "lowest_eigenvalue": float(bad_vals[0]), "eigenvalues": bad_vals.tolist()})
                checks[f"negative_epsilon_N{n}"] = bool(bad_vals[0] < 0)
    return checks, {"rows": rows, "negative_controls": negative, "raw": raw,
                    "scope": "A covariant interval-operator and boundary-work witness. Boundary voltage and negative electric coefficient are explicitly excluded physical assumptions, not alternative formation runs."}


def main() -> int:
    exact_checks, derivation = exact_temporal()
    charge_checks, charge = charge_calculation()
    electric_checks, electric = interval_calculation()
    checks = {key: bool(value) for key, value in (exact_checks | charge_checks | electric_checks).items()}
    passed = all(checks.values())
    result = {"verdict": "PASS" if passed else "FAIL", "checks": checks, "inputs": INPUTS,
              "derivation": derivation, "charge": charge, "electric": electric,
              "complete_physical_matter_formation": False}
    print(json.dumps(result, allow_nan=False, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
