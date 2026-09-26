#!/usr/bin/env python3
"""Independent component/charge reconstruction of report subsection 41.1.

Run: python computations/verify_matter_formation_common_charge.py
The spinor is aligned with z; the adjoint carries the relative angle. Gaussian
moments are integrated symbolically. No other project calculation is imported.
"""
from __future__ import annotations

import json
import math

import sympy as sp


def calculate() -> dict:
    rho, v, g, cp, cf = sp.symbols("rho v g C_Psi C_Phi", positive=True)
    c, s, u = sp.symbols("c s u", real=True)
    a = sp.Matrix(sp.symbols("a_x a_y a_z", real=True))

    def reduce_unit(expression):
        numerator, denominator = sp.fraction(sp.cancel(sp.expand(expression)))
        relation = c*c+s*s-1
        return sp.factor(sp.rem(numerator, relation, c)/sp.rem(denominator, relation, c))

    def reduce_matrix(matrix):
        return matrix.applyfunc(reduce_unit)

    sigma = [sp.Matrix([[0, 1], [1, 0]]), sp.Matrix([[0, -sp.I], [sp.I, 0]]), sp.diag(1, -1)]
    psi = sp.Matrix([sp.sqrt(rho), 0])
    direction = sp.Matrix([s, 0, c])
    adj = v*direction
    gauge = sum((a[j]*sigma[j]/2 for j in range(3)), sp.zeros(2))
    dpsi = sp.I*(u*sp.eye(2)-g*gauge)*psi
    dadj = g*a.cross(adj)
    kinetic = reduce_unit(cp*(dpsi.conjugate().T*dpsi)[0]/2+cf*dadj.dot(dadj)/2)
    mass = reduce_matrix(sp.hessian(kinetic, a))
    b = -sp.Matrix([sp.diff(kinetic, entry).subs(dict(zip(a, [0, 0, 0]))).subs(u, 1) for entry in a])
    expected_mass = g*g*(cp*rho*sp.eye(3)/4+cf*(v*v*sp.eye(3)-adj*adj.T))
    expected_b = sp.Matrix([0, 0, g*cp*rho/2])
    # Rank-one inverse in the adjoint-aligned basis; verify it before using it.
    alpha, d = cp*rho/4, cf*v*v
    inverse = (sp.eye(3)/(alpha+d)+d*direction*direction.T/(alpha*(alpha+d)))/(g*g)
    star = reduce_matrix(inverse*b*u)
    inertia = reduce_unit(cp*rho-(b.T*inverse*b)[0])
    expected_j = 4*cp*rho*cf*v*v*s*s/(cp*rho+4*cf*v*v)
    displacement = a-star
    square = reduce_unit(kinetic-inertia*u*u/2-(displacement.T*mass*displacement)[0]/2)
    qpsi = sp.Matrix([cp*g*sp.im((psi.conjugate().T*sigma[j]*dpsi)[0])/2 for j in range(3)])
    qadj = -cf*g*adj.cross(dadj)
    replacement = dict(zip(a, star))
    velocity_psi = reduce_matrix(dpsi.subs(replacement))
    velocity_adj = reduce_matrix(dadj.subs(replacement))
    momentum = reduce_unit(cp*sp.im((psi.conjugate().T*velocity_psi)[0]))
    energy = reduce_unit(cp*(velocity_psi.conjugate().T*velocity_psi)[0]/2+cf*velocity_adj.dot(velocity_adj)/2)
    epsilon = sp.Matrix([[0, 1], [-1, 0]])
    adj_matrix = sum((adj[j]*sigma[j] for j in range(3)), sp.zeros(2))
    dadj_matrix = sum((dadj[j]*sigma[j] for j in range(3)), sp.zeros(2))
    observable = (psi.T*epsilon*adj_matrix*psi)[0]
    observable_dot = (dpsi.T*epsilon*adj_matrix*psi+psi.T*epsilon*dadj_matrix*psi+psi.T*epsilon*adj_matrix*dpsi)[0]
    residuals = {
        "mass_from_components": mass-expected_mass,
        "source_from_components": b-expected_b,
        "inverse_under_unit_direction": mass*inverse-sp.eye(3),
        "completed_square": square,
        "projected_inertia": inertia-expected_j,
        "source_sign": sp.Matrix([sp.diff(kinetic, entry) for entry in a])+qpsi+qadj,
        "pointwise_gauss_cancellation": (qpsi+qadj).subs(replacement),
        "canonical_momentum": momentum-inertia*u,
        "temporal_energy": energy-inertia*u*u/2,
        "physical_phase_derivative": observable_dot-2*sp.I*u*observable,
        "aligned_endpoint_inertia": inertia.subs(s, 0),
    }
    symbolic = {name: [reduce_unit(x) for x in value] if isinstance(value, sp.MatrixBase)
                else [reduce_unit(value)] for name, value in residuals.items()}
    checks = {name: all(x == 0 for x in values) for name, values in symbolic.items()}
    golden = (1+sp.sqrt(5))/2
    cosine = sp.simplify(golden**-3)
    frozen = {rho: sp.Rational(6, 5), v: sp.Rational(9, 10), g: sp.Rational(71, 100),
              cp: sp.Rational(13, 10), cf: sp.Rational(3, 4), c: cosine, s: sp.sqrt(1-cosine*cosine)}
    jf = sp.simplify(inertia.subs(frozen))
    numeric_j = float(jf)
    checks["positive_frozen_inertia"] = numeric_j > 0
    checks["declared_composition_vacuum"] = sp.simplify((1-golden)+(1+golden)*cosine) == 0
    # Derive the 3D moments by three independent Cartesian Gaussian integrals.
    z = sp.symbols("z", real=True)
    first_moment = sp.integrate(sp.exp(-z*z), (z, -sp.oo, sp.oo))
    squared_moment = sp.integrate(sp.exp(-2*z*z), (z, -sp.oo, sp.oo))
    norm = sp.simplify(first_moment**3/sp.pi**sp.Rational(3, 2))
    checks["gaussian_normalization"] = norm == 1
    rows = []
    for radius in (1, 2, 4, 8):
        p_value = sp.Integer(1)*norm
        f_squared = sp.simplify(squared_moment**3/(sp.pi**3*radius**3))
        e_value = sp.simplify(f_squared/(2*jf))
        expected = 1/(2*numeric_j*(2*math.pi)**1.5*radius**3)
        checks[f"gaussian_energy_R{radius}"] = abs(float(e_value)-expected) <= 1e-11
        rows.append({"R": radius, "P_N": float(p_value), "energy": float(e_value),
                     "exact_energy": str(e_value), "exact_f_squared_moment": str(f_squared)})
    def numeric_matrix(matrix):
        return [[float(sp.N(entry.subs(frozen), 17)) for entry in row] for row in matrix.tolist()]
    result = {
        "verdict": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
        "complete_physical_matter_formation": False,
        "J_t": numeric_j, "J_t_exact": str(jf), "charge_rows": rows,
        "symbolic_residuals": {name: [str(x) for x in values] for name, values in symbolic.items()},
        "component_derivation": {"M": str(mass), "b": str(b), "J_t": str(inertia),
                                 "p_N": str(momentum), "energy": str(energy), "observable": str(observable)},
        "frozen_mass": numeric_matrix(mass), "frozen_b": numeric_matrix(b),
        "gaussian_moments": {"integral_exp_minus_z2": str(first_moment), "integral_exp_minus_2z2": str(squared_moment)},
        "charge_units": "P_N=int C_Psi Im(Psi dagger D_t Psi) has action units; P_N/hbar is a number normalization distinct from first-order density excess.",
        "frequency_obstruction": "For positive coefficients and a nonaligned nonzero vacuum pair, the complete square leaves positive J_t,infinity*omega_N^2/2 at infinity. A finite-energy single-common-frequency relative equilibrium has omega_N=0.",
        "electric_equality": "With zero boundary work, the covariant gradient and mass forms vanish separately. Covariantly constant A_0 has constant norm, and the nonzero fundamental exterior makes it zero, including a bounded empty core.",
        "fixed_charge_scope": "At chi_C=0, vacuum field coordinates and zero electric momentum, these exact Gauss-compatible initial velocities have fixed nonzero P_N and energy proportional to R^-3. The nonnegative Hamiltonian has infimum zero; zero temporal energy forces P_N=0, so the infimum is unattained at nonzero P_N. This does not exclude local metastability or establish a dynamical dilution trajectory.",
        "boundaries": "Space R^3, unit scale measure and no scale boundary work. External charge, voltage, finite-density reservoirs, aligned or vanishing vacuum fields, general multifrequency dynamics and quantum sectors lie outside the conclusion. The separate neutral carrier has its own charge.",
    }
    return result


def main() -> int:
    result = calculate()
    print(json.dumps(result, allow_nan=False, sort_keys=True))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
