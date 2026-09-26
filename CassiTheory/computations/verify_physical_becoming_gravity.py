#!/usr/bin/env python3
"""Verify algebraic gates for the physical-becoming gravity boundary.

Run from the CassiTheory repository root:

    python computations/verify_physical_becoming_gravity.py

This checks the Cassi composite coupling at its reference state, the fixed-ray
limits, the independence of its two coarse coordinates, and the unscreened
scalar-tensor PPN bound. It does not supply a scalar source law or screening
mechanism.
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
    rho = sp.symbols("rho", positive=True, real=True)
    epsilon = sp.symbols("epsilon", real=True)

    print("Physical-becoming composite-gravity algebra verification")
    print(f"phi = {sp.N(phi, 16)}")

    e_y = (phi * rho + epsilon) / (1 + phi)
    e_i = (rho - epsilon) / (1 + phi)
    pi = sp.simplify(e_y - e_i)
    signed_fraction = sp.simplify(pi / rho)
    q = sp.simplify(rho**2 / (rho**2 + phi**-2 + epsilon**2))
    g_ratio = sp.simplify(
        signed_fraction * (1 + (phi**6 - 1) * q)
    )

    rho_ref = phi
    epsilon_ref = sp.Integer(0)
    q_ref = sp.simplify(q.subs({rho: rho_ref, epsilon: epsilon_ref}))
    s_ref = sp.simplify(
        signed_fraction.subs({rho: rho_ref, epsilon: epsilon_ref})
    )
    g_ref = sp.simplify(
        g_ratio.subs({rho: rho_ref, epsilon: epsilon_ref})
    )
    require_zero("reference signed fraction", s_ref - phi**-3)
    require_zero("reference coherence", q_ref - phi**2 / 3)
    print(f"reference G_eff/G = {sp.N(g_ref, 12)}")

    # On the declared physical coherence interval 0 <= q <= 1, this affine
    # fixed-composition branch is monotone and its endpoint values are bounds.
    q_symbol = sp.symbols("q_symbol", nonnegative=True, real=True)
    fixed_ray_ratio = sp.simplify(
        phi**-3 * (1 + (phi**6 - 1) * q_symbol)
    )
    fixed_ray_slope = sp.simplify(sp.diff(fixed_ray_ratio, q_symbol))
    require_true("fixed-ray coupling increases with q", bool(fixed_ray_slope > 0))
    require_zero(
        "fixed-ray low-coherence endpoint",
        fixed_ray_ratio.subs(q_symbol, 0) - phi**-3,
    )
    require_zero(
        "fixed-ray high-coherence endpoint",
        fixed_ray_ratio.subs(q_symbol, 1) - phi**3,
    )
    print("fixed-ray domain assumed: 0 <= q <= 1")

    # The composite coupling depends on two locally independent coarse
    # coordinates. This coordinate fact does not supply the independent
    # covariant scalar equation or source law required for closure.
    jacobian = sp.simplify(
        sp.det(
            sp.Matrix(
                [
                    [sp.diff(signed_fraction, rho), sp.diff(signed_fraction, epsilon)],
                    [sp.diff(q, rho), sp.diff(q, epsilon)],
                ]
            )
        )
    )
    jacobian_ref = sp.simplify(
        jacobian.subs({rho: rho_ref, epsilon: epsilon_ref})
    )
    print(f"coordinate Jacobian at reference state = {jacobian_ref}")
    require_true("two coarse coupling coordinates independent", jacobian_ref != 0)

    # For one unscreened, effectively massless, universally coupled
    # Einstein-frame scalar: |gamma_PPN - 1| =
    # 2 alpha_ST,0^2/(1+alpha_ST,0^2).
    cassini_uncertainty = sp.Rational(23, 1_000_000)
    alpha_st_sq_limit = sp.simplify(
        cassini_uncertainty / (2 - cassini_uncertainty)
    )
    require_true(
        "Cassini unscreened alpha_ST,0 squared below 1.2e-5",
        bool(alpha_st_sq_limit < sp.Rational(12, 1_000_000)),
    )
    print(f"one-sigma alpha_ST,0^2 scale = {sp.N(alpha_st_sq_limit, 8)}")
    print(
        "one-sigma |alpha_ST,0| scale = "
        f"{sp.N(sp.sqrt(alpha_st_sq_limit), 8)}"
    )

    # A direct Jordan-frame ansatz F=M_Pl^2/(G_eff/G) would be tensor-healthy
    # only on branches where the composite ratio is positive. This positivity
    # check does not derive that ansatz or close its scalar source equation.
    require_true("reference direct-matching ansatz positive", bool(g_ref > 0))

    print("VERDICT: reference coupling algebra and unscreened PPN limit checks pass")
    print("VERDICT: covariant scalar source and screening completion remains OPEN")
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
