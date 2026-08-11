#!/usr/bin/env python3
"""
Audit the origin of the single-channel Qi transmission function.

The current application form is

    g(q) = q / (phi**2 + q**2),  0 <= q <= 1.

This script separates properties of that asserted form from a selection rule
for the form itself. It verifies the power peak, reciprocal self-duality, and
several counterfactual families. The endpoint and attractor constraints leave
A free in g_A(q) = q/(A+q**2), A >= 1. A conditional reciprocal-duality family
also leaves the positive integer m and normalization C_m free:

    g_m(q) = C_m q**m / (phi**(2*m) + q**(2*m)).

A linear small-q response selects m=1 inside that added family; the slope
condition g'(0)=phi^-2 selects C_1=1. Neither condition appears in the
first-principles action. The denominator remains an asserted input.
"""

from __future__ import annotations

import math

PHI = (1.0 + math.sqrt(5.0)) / 2.0
A0 = PHI**2

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        failures.append(label)
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{detail}")


def gate(q: float, a: float = A0) -> float:
    return q / (a + q * q)


def power(q: float, a: float = A0) -> float:
    return gate(q, a) * (1.0 - q)


def gate_family(q: float, m: int, c: float = 1.0) -> float:
    return c * q**m / (PHI ** (2 * m) + q ** (2 * m))


print("Qi gate origin audit")
print("====================")
print(f"phi = {PHI:.12f}")
print(f"phi^2 = {A0:.12f}\n")

print("1. Properties of the asserted form")
q_peak = math.sqrt(A0 * A0 + A0) - A0
peak_derivative = A0 - 2.0 * A0 * q_peak - q_peak * q_peak
check("g(0) = 0", math.isclose(gate(0.0), 0.0))
check("g(q) is positive on the open physical interval", all(gate(q) > 0.0 for q in (0.01, 0.25, 0.5, 0.75, 1.0)))
check("g(q) is monotone on 0 <= q <= 1", all(A0 - q * q > 0.0 for q in (0.0, 0.25, 0.5, 0.75, 1.0)))
check("g(q)(1-q) vanishes at q = 1", math.isclose(power(1.0), 0.0))
check("power derivative vanishes at the quoted peak", abs(peak_derivative) < 1e-12, f" (q={q_peak:.12f})")
print(f"  power peak q = {q_peak:.12f}, g(q)(1-q) = {power(q_peak):.12f}")

print("\n2. Conditional reciprocal-duality construction")
for q in (0.17, 0.31, 0.59, 0.91):
    dual = A0 / q
    check(f"g(q) = g(phi^2/q) at q={q:.2f}", math.isclose(gate(q), gate(dual), rel_tol=1e-12, abs_tol=1e-12))
for m in (1, 2, 3):
    q = 0.37
    dual = A0 / q
    check(f"self-dual family member m={m}", math.isclose(gate_family(q, m), gate_family(dual, m), rel_tol=1e-12, abs_tol=1e-12))
check("m=1 has linear small-q response", math.isclose(gate_family(1e-7, 1) / 1e-7, PHI**-2, rel_tol=1e-6))
check("m=2 has zero linear response", gate_family(1e-8, 2) / 1e-8 < 1e-8)

print("\n3. Counterfactual endpoint and attractor constraints")
for a in (1.0, A0, 4.0):
    values = [q / (a + q * q) for q in (0.0, 0.25, 0.5, 0.75, 1.0)]
    monotone = all(values[i] <= values[i + 1] for i in range(len(values) - 1))
    check(f"A={a:.6f} satisfies positivity, monotonicity, and closure", monotone and values[0] == 0.0 and power(1.0, a) == 0.0)
    print(f"  A={a:.6f}: g(1)={values[-1]:.12f}, peak q={math.sqrt(a*a+a)-a:.12f}")

print("\n4. Origin inventory")
print("  First-principles §§1-2 define the attractor, q, (1-q) closure, and IIR memory.")
print("  The unified action contains no rational g(q) term or variational equation selecting it.")
print("  The w=5 pentagon gate supplies b_i and channel efficiencies, with no reduction to the single-channel denominator.")
print("  The denominator scale phi^2 and normalization are therefore additional inputs.")

print("\nVerdict")
print("-------")
print("  Derived conditional on the asserted form: endpoint behavior, monotonicity, and power peak.")
print("  Conditional candidate: reciprocal duality + linear response + slope phi^-2 reproduces m=1, C=1.")
print("  Closure status: ASSERTED INPUT; no existing selection constraint fixes the denominator or normalization.")
if failures:
    print("\nCHECKS FAILED: " + ", ".join(failures))
    raise SystemExit(1)
print("\nALL CHECKS PASSED")
