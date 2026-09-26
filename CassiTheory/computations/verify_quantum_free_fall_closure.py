#!/usr/bin/env python3
"""Verify the frozen information and spectral boundaries, without fitting data.

Run from CassiTheory: python computations/verify_quantum_free_fall_closure.py
Protocol: computations/quantum_free_fall_closure_prereg.md
"""

import sympy as sp


def equal(label: str, actual: sp.Expr, expected: sp.Expr) -> None:
    residual = sp.simplify(actual - expected)
    if residual != 0:
        raise AssertionError(f"{label}: residual={residual}")
    print(f"{label}: PASS")


def main() -> None:
    phi = (1 + sp.sqrt(5)) / 2
    rho, ref = sp.symbols("rho rho_star", positive=True)
    epsilon = sp.symbols("epsilon", real=True)
    ey = (phi * rho + epsilon) / (1 + phi)
    ei = (rho - epsilon) / (1 + phi)
    base = rho**2 + ref**2 / phi**2
    q = rho**2 / (base + epsilon**2)
    q_min = rho**2 / (base + phi**2 * rho**2)
    q_max = rho**2 / base
    equal("QFC1 density reconstruction", ey + ei, rho)
    equal("QFC1 imbalance reconstruction", ey - phi * ei, epsilon)
    equal("QFC1 lower density endpoint", ey.subs(epsilon, -phi * rho), 0)
    equal("QFC1 upper density endpoint", ei.subs(epsilon, rho), 0)
    equal("QFC1 q lower endpoint", q.subs(epsilon, -phi * rho), q_min)
    equal("QFC1 q upper endpoint", q.subs(epsilon, 0), q_max)
    equal(
        "QFC1 lower-bound factorization",
        q - q_min,
        rho**2 * (phi * rho - epsilon) * (phi * rho + epsilon)
        / ((base + epsilon**2) * (base + phi**2 * rho**2)),
    )
    equal(
        "QFC1 upper-bound factorization",
        q_max - q,
        rho**2 * epsilon**2 / (base * (base + epsilon**2)),
    )
    equal("QFC1 dilute lower bound", sp.limit(q_min, rho, 0), 0)
    equal("QFC1 dilute upper bound", sp.limit(q_max, rho, 0), 0)
    equal("QFC1 dense lower bound", sp.limit(q_min, rho, sp.oo), 1 / (1 + phi**2))
    print("QFC1 dense lower bound =", sp.N(1 / (1 + phi**2), 12))

    states = []
    for sign in (1, -1):
        substitutions = {rho: 1, ref: 1, epsilon: sp.Rational(sign, 2)}
        y, i = (sp.simplify(v.subs(substitutions)) for v in (ey, ei))
        qi = sp.simplify(q.subs(substitutions))
        imbalance = sp.simplify(y - i)
        coupling = sp.simplify(imbalance * (1 + (phi**6 - 1) * qi))
        if y.is_positive is not True or i.is_positive is not True:
            raise AssertionError("QFC2 witness leaves the canonical density domain")
        if sp.simplify(sign * imbalance).is_positive is not True:
            raise AssertionError("QFC2 signed imbalance has the wrong sign")
        if sp.simplify(sign * coupling).is_positive is not True:
            raise AssertionError("QFC2 signed coupling has the wrong sign")
        states.append((y, i, qi))
        print(f"QFC2 epsilon={sign}/2:", {
            "EY": float(y), "EI": float(i), "q": float(qi),
            "s": float(imbalance), "G_C": float(coupling),
        })
    equal("QFC2 same q, opposite signed response diagnostic", states[0][2], states[1][2])

    mean_y, mean_i = ((states[0][j] + states[1][j]) / 2 for j in (0, 1))
    mean_rho, mean_eps = mean_y + mean_i, mean_y - phi * mean_i
    q_of_mean = sp.simplify(mean_rho**2 / (mean_rho**2 + phi**-2 + mean_eps**2))
    mean_q = sp.simplify((states[0][2] + states[1][2]) / 2)
    difference = sp.simplify(q_of_mean - mean_q)
    if difference.is_positive is not True:
        raise AssertionError("QFC3 coarsening witness did not differ")
    equal("QFC3 field-average equilibrium", mean_eps, 0)
    print(f"QFC3 average(q)={float(mean_q):.12f}; q(average fields)={float(q_of_mean):.12f}; difference={float(difference):.12f}: PASS")

    x, delta, a = sp.symbols("x delta a", positive=True)
    u = sp.symbols("u", nonnegative=True)
    kernel_difference = (x + delta) / (x + delta + u) - x / (x + u)
    positive_kernel = u * delta / ((x + delta + u) * (x + u))
    equal("QFC4 positive spectral kernel", kernel_difference, positive_kernel)
    if positive_kernel.is_nonnegative is not True:
        raise AssertionError("QFC4 spectral kernel sign unresolved")
    gaussian = sp.exp(-a * x) / x
    slope = sp.diff(x * gaussian, x)
    equal("QFC4 Gaussian slope", slope, -a * sp.exp(-a * x))
    if slope.is_negative is not True:
        raise AssertionError("QFC4 Gaussian slope is not strictly negative")
    equal("QFC4 zero-regulator massless control", gaussian.subs(a, 0), 1 / x)
    scaled_gaussian = x * gaussian
    witness_first = sp.simplify(scaled_gaussian.subs(x, 1 / a))
    witness_second = sp.simplify(scaled_gaussian.subs(x, 2 / a))
    witness_difference = sp.simplify(witness_second - witness_first)
    if witness_difference.is_negative is not True:
        raise AssertionError("QFC4 two-point Gaussian witness is not decreasing")
    print(f"QFC4 ax=1: xG={float(witness_first):.12f}; ax=2: xG={float(witness_second):.12f}")
    print(f"QFC4 two-point difference={float(witness_difference):.12f}: PASS")
    print("QFC4 standard positive spectral interpretation at sigma>0: REJECT")
    print("QFC1-QFC4: PASS")
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
