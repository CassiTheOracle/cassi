#!/usr/bin/env python3
"""Verify the microscopic-EFT algebra in the physical-becoming hierarchy.

Run from the CassiTheory repository root:

    python computations/verify_physical_becoming_eft.py

The script checks the two-singlet quartic map, its stability form, the
conditional canonical-vacuum Hessian modes, and the one-loop RG obstruction
to preserving the selected phi-attractor surface. It does not choose the
free quartics, supply a UV completion, or derive the mesoscopic two-density
PDE.
"""

from __future__ import annotations

import sympy as sp


def require_zero(name: str, expression: sp.Expr) -> None:
    value = sp.simplify(expression)
    print(f"{name}: {value}")
    if value != 0:
        raise AssertionError(f"{name} failed: {value}")


def require_true(name: str, condition: bool) -> None:
    print(f"{name}: {condition}")
    if not condition:
        raise AssertionError(f"{name} failed")


def main() -> None:
    phi = (sp.Integer(1) + sp.sqrt(5)) / 2
    g_4 = sp.symbols("g_4", positive=True, real=True)
    lambda_a = sp.symbols("lambda_A", nonnegative=True, real=True)
    chi_y, chi_i = sp.symbols("chi_Y chi_I", real=True)

    print("Physical-becoming microscopic EFT verification")
    print(f"phi = {sp.N(phi, 16)}")

    selected = (
        g_4 / 4 * (chi_y**2 + chi_i**2) ** 2
        + lambda_a / 2 * (chi_y**2 - phi * chi_i**2) ** 2
    )
    lambda_y = g_4 + 2 * lambda_a
    lambda_i = g_4 + 2 * phi**2 * lambda_a
    lambda_yi = 2 * g_4 - 4 * phi * lambda_a
    general_quartic = (
        lambda_y * chi_y**4 / 4
        + lambda_i * chi_i**4 / 4
        + lambda_yi * chi_y**2 * chi_i**2 / 4
    )
    require_zero("selected quartic map", sp.expand(selected - general_quartic))

    manifold_constraint = sp.simplify(
        -2 * phi**2 * lambda_y + 2 * phi * lambda_i + lambda_yi
    )
    require_zero("phi-attractor surface constraint", manifold_constraint)
    require_zero(
        "phi-ray Y mass bracket",
        phi * lambda_y + lambda_yi / 2 - g_4 * phi**2,
    )
    require_zero(
        "phi-ray I mass bracket",
        lambda_i + phi * lambda_yi / 2 - g_4 * phi**2,
    )

    # Equation (EFT4) is manifestly a sum of squares. The nonzero vacuum
    # below requires g_4 > 0; quartic stability additionally permits
    # lambda_A = 0. These are declared domain assumptions, not derived checks.
    print("quartic/vacuum domain assumed: g_4 > 0 and lambda_A >= 0")
    print(
        "normalization-dependent tree-level single-channel bounds: "
        "|lambda_Y,I| <= 4*pi/3"
    )
    print("coupled-channel tree-level unitarity also constrains lambda_YI")
    # Conditional Hessian prediction for (EFT6c). This uses canonical
    # singlet kinetic terms, negligible portals/curvature, and the nonzero
    # minimum rho_chi=mu_chi^2/g_4 on the phi ray.
    mu_chi_sq = sp.symbols("mu_chi_sq", positive=True, real=True)
    rho_chi = sp.simplify(mu_chi_sq / g_4)
    rho_field = chi_y**2 + chi_i**2
    epsilon_field = chi_y**2 - phi * chi_i**2
    vacuum_potential = (
        -mu_chi_sq * rho_field / 2
        + g_4 * rho_field**2 / 4
        + lambda_a * epsilon_field**2 / 2
    )
    hessian = sp.hessian(vacuum_potential, (chi_y, chi_i))
    chi_i_vac = sp.sqrt(rho_chi) / phi
    chi_y_vac = sp.sqrt(phi) * sp.sqrt(rho_chi) / phi
    hessian_vac = sp.simplify(
        hessian.subs({chi_y: chi_y_vac, chi_i: chi_i_vac})
    )
    h_radial = sp.Matrix([sp.sqrt(phi) / phi, 1 / phi])
    h_angular = sp.Matrix([1 / phi, -sp.sqrt(phi) / phi])
    require_zero("radial mode norm", h_radial.dot(h_radial) - 1)
    require_zero("angular mode norm", h_angular.dot(h_angular) - 1)
    require_zero("radial-angular orthogonality", h_radial.dot(h_angular))
    m_radial_sq = sp.simplify(2 * g_4 * rho_chi)
    m_angular_sq = sp.simplify(4 * phi * lambda_a * rho_chi)
    require_zero(
        "radial mass identity m_R^2=2*mu_chi^2",
        m_radial_sq - 2 * mu_chi_sq,
    )
    require_zero(
        "angular mass identity m_A^2=4*phi*lambda_A*rho_chi",
        m_angular_sq - 4 * phi * lambda_a * rho_chi,
    )
    for component in range(2):
        require_zero(
            f"radial Hessian eigenmode component {component}",
            (hessian_vac * h_radial - m_radial_sq * h_radial)[component],
        )
        require_zero(
            f"angular Hessian eigenmode component {component}",
            (hessian_vac * h_angular - m_angular_sq * h_angular)[component],
        )
    require_zero(
        "Hessian mass-squared ratio",
        sp.simplify(m_angular_sq / m_radial_sq - 2 * phi * lambda_a / g_4),
    )
    tan_theta_radial = sp.simplify(h_radial[1] / h_radial[0])
    require_zero(
        "radial mode angle tan(theta_R)=phi^(-1/2)",
        tan_theta_radial - phi**(-sp.Rational(1, 2)),
    )
    print(
        "conditional Hessian modes: "
        "h_R=(sqrt(phi)*dchi_Y+dchi_I)/phi, "
        "h_A=(dchi_Y-sqrt(phi)*dchi_I)/phi"
    )
    print(
        "conditional masses: m_R^2=2*mu_chi^2, "
        "m_A^2/m_R^2=2*phi*lambda_A/g_4"
    )
    print(
        "conditional radial angle theta_R = "
        f"{sp.N(sp.atan(tan_theta_radial) * 180 / sp.pi, 8)} degrees"
    )


    # One-loop beta numerators for V = lambda_Y Y^4/4 + lambda_I I^4/4
    # + lambda_YI Y^2 I^2/4. The common factor 1/(16 pi^2) is omitted.
    beta_y_num = 18 * lambda_y**2 + sp.Rational(1, 2) * lambda_yi**2
    beta_i_num = 18 * lambda_i**2 + sp.Rational(1, 2) * lambda_yi**2
    beta_yi_num = (
        4 * lambda_yi**2
        + 6 * lambda_yi * (lambda_y + lambda_i)
    )

    fixed_lambda_y, fixed_lambda_i, fixed_lambda_yi = sp.symbols(
        "fixed_lambda_Y fixed_lambda_I fixed_lambda_YI", real=True
    )
    fixed_solutions = sp.solve(
        [
            18 * fixed_lambda_y**2
            + sp.Rational(1, 2) * fixed_lambda_yi**2,
            18 * fixed_lambda_i**2
            + sp.Rational(1, 2) * fixed_lambda_yi**2,
            4 * fixed_lambda_yi**2
            + 6
            * fixed_lambda_yi
            * (fixed_lambda_y + fixed_lambda_i),
        ],
        [fixed_lambda_y, fixed_lambda_i, fixed_lambda_yi],
        dict=True,
    )
    require_true(
        "only simultaneous real one-loop beta zero is Gaussian",
        fixed_solutions
        == [
            {
                fixed_lambda_i: 0,
                fixed_lambda_y: 0,
                fixed_lambda_yi: 0,
            }
        ],
    )

    normal_beta_num = sp.factor(
        -2 * phi**2 * beta_y_num
        + 2 * phi * beta_i_num
        + beta_yi_num
    )
    expected_normal_beta_num = 12 * lambda_a * (
        (44 + 20 * sp.sqrt(5)) * lambda_a
        + (7 + 3 * sp.sqrt(5)) * g_4
    )
    require_zero(
        "RG normal-beta identity",
        normal_beta_num - expected_normal_beta_num,
    )
    require_true(
        "RG normal beta has positive coefficients",
        all(
            bool(coefficient > 0)
            for coefficient in sp.Poly(
                expected_normal_beta_num, lambda_a, g_4
            ).coeffs()
        ),
    )

    # The radial O(2)-symmetric ray survives when lambda_A = 0, but the
    # phi-attractor structure is then absent.
    require_zero(
        "radial ray is tangent",
        normal_beta_num.subs(lambda_a, 0),
    )

    print("bridge dimensions: [chi^2]=M^2, [M_match^2]=M^2")
    print("physical density map: [Z M_match^2 <chi^2>]=M^4")
    print("VERDICT: unrestricted counterterm EFT is radiatively closed")
    print("VERDICT: restricted phi-attractor surface REJECTED as RG invariant")
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
