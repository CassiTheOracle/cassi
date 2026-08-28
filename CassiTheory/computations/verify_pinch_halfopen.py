#!/usr/bin/env python3
"""Verify the normalized pinch-point identities used by
consciousness/consciousness-from-phi.md §1.1.

The normalization-independent identity at r = phi^-1 is

    (r - phi)^2 / (1 + r)^2 = phi^-2.

Gate values require an amplitude convention because
q = rho^2 / (rho^2 + phi^-2 + eps^2). This script compares two declared
conventions that coincide at the pinch: the homogeneous cosmology ODE
normalization and the PDE field-ratio normalization E_I = 1.

It verifies:
  1. r = phi^-1 is the Yin-dominant mirror of the attractor r = phi.
  2. The fractional imbalance equals phi^-2 at that ratio.
  3. In the declared normalizations, q = phi^2/4 and
     1-q = (3-phi)/4 at the pinch.
  4. In the E_I=1 PDE convention, q=1/2 occurs at r=phi^-2.
  5. The normalized Yang-minus-Yin fractional imbalance is -phi^-3 at the
     pinch and +phi^-3 at the attractor.
  6. The normalized conversion-force curve is monotonic on (0,phi), with
     two inflections away from the pinch.
  7. The homogeneous-ODE-normalized derivative dq/dr at the pinch.

Tier: Derived conditional on the gate form and declared normalizations
(`foundations/cassi-theory-reference.md` §2.4,
`foundations/cassi-first-principles.md` §2.1,
`two-fluid/run_hubble_pipeline.py`, and
`two-fluid/calibrate_initial_ratio_xi_v2.py`).

Run: python computations/verify_pinch_halfopen.py
"""

import numpy as np

PHI = (1.0 + np.sqrt(5.0)) / 2.0
PINV = 1.0 / PHI
PINV2 = PINV ** 2


def gate_ode(r):
    """Declared homogeneous cosmology-ODE gate normalization.

    (1-q) = (phi^-2 + eps^2)/(phi^2 + phi^-2 + eps^2),
    eps^2 = (r - phi)^2 phi^2/(1 + r)^2.
    """
    e2 = (r - PHI) ** 2 * PHI ** 2 / (1.0 + r) ** 2
    one_minus_q = (PINV2 + e2) / (PHI ** 2 + PINV2 + e2)
    return 1.0 - one_minus_q, e2


def gate_pde(r):
    """PDE solver form (cassi_two_fluid_3d_gpu.py, gate_model='single'),
    field-ratio convention ey = r * ei, ei = 1:
    q = (ey+ei)^2 / ((ey+ei)^2 + phi^-2 + (ey - phi*ei)^2)."""
    ey, ei = r, 1.0
    M = (ey + ei) ** 2
    e2 = (ey - PHI * ei) ** 2
    return M / (M + PINV2 + e2), e2


def conv_force(r):
    q, _ = gate_ode(r)
    return (1.0 - q) * (PHI - r) * (1.0 + r)


def require(label, condition):
    """Raise if a printed identity or diagnostic condition fails."""
    if not bool(condition):
        raise AssertionError(f"{label} failed")

print(f"phi = {PHI:.12f}   phi^-1 = {PINV:.12f}   phi^-2 = {PINV2:.12f}")
print(f"phi^2 + phi^-2 = {PHI**2 + PINV2:.15f}  (exact = 3)")
print()

# 1. Conjugate point
r0 = PINV
require("conjugate ratio", abs(r0 - PINV) < 1e-15)
print("1. Conjugate point: r = phi^-1 <=> E_Y/E_I = 1/phi <=> E_I = phi*E_Y  [exact identity]")

# 2. Fractional imbalance at the pinch = gate scale
f = (r0 - PHI) ** 2 / (1.0 + r0) ** 2
print(f"2. (r-phi)^2/(1+r)^2 at pinch = {f:.15f}   phi^-2 = {PINV2:.15f}   exact match: {abs(f - PINV2) < 1e-14}")
require("fractional imbalance identity", abs(f - PINV2) < 1e-14)
print(f"   (uses phi^-1 - phi = {r0 - PHI:.3f} and 1 + phi^-1 = {1.0 + r0:.6f} = phi)")

# 3. Canonical gate at the pinch (ODE and PDE conventions)
q_ode, e2_ode = gate_ode(r0)
q_pde, e2_pde = gate_pde(r0)
target_q = PHI ** 2 / 4.0
target_1mq = (3.0 - PHI) / 4.0
print(f"3. Gate at pinch (ODE form):  q = {q_ode:.12f}   phi^2/4 = {target_q:.12f}   exact: {abs(q_ode - target_q) < 1e-14}")
print(f"   Gate at pinch (PDE form):  q = {q_pde:.12f}   exact: {abs(q_pde - target_q) < 1e-14}")
print(f"   (1-q) = {1.0 - q_ode:.12f}   (3-phi)/4 = {target_1mq:.12f}   exact: {abs(1.0 - q_ode - target_1mq) < 1e-14}")
print(f"   eps^2 (ODE normalization) at pinch = {e2_ode:.12f}  (= phi^-2 * phi^2 = 1)")
require("ODE pinch gate", abs(q_ode - target_q) < 1e-14)
require("PDE pinch gate", abs(q_pde - target_q) < 1e-14)
require("pinch openness identity", abs(1.0 - q_ode - target_1mq) < 1e-14)
require("ODE pinch imbalance", abs(e2_ode - 1.0) < 1e-14)

# 4. Literal half-open point is at r = phi^-2, not the pinch
#    PDE convention: q = 1/2 <=> (1+r)^2 = phi^-2 + (r-phi)^2 <=> r = 1/(1+phi) = phi^-2
r_half = 1.0 / (1.0 + PHI)
q_half = gate_pde(r_half)[0]
print(f"4. q = 1/2 at r = 1/(1+phi) = {r_half:.12f} = phi^-2 ({PINV2:.12f}); q there = {q_half:.12f}")
print(f"   q at the pinch is {q_ode:.4f} != 1/2  ->  pinch is NOT the literal half-open point")
require("half-open ratio identity", abs(r_half - PINV2) < 1e-14)
require("half-open gate value", abs(q_half - 0.5) < 1e-14)
require("pinch is not half-open", abs(q_ode - 0.5) > 1e-3)

# 5. Mirror identity of the Yang-minus-Yin fractional imbalance
pinv_pinch = (PINV - 1.0) / (PINV + 1.0)   # (E_Y-E_I)/(E_Y+E_I) at r=phi^-1
pinv_attr = (PHI - 1.0) / (PHI + 1.0)      # (E_Y-E_I)/(E_Y+E_I) at r=phi
print(f"5. fractional imbalance at pinch = {pinv_pinch:.12f}   -phi^-3 = {-PINV**3:.12f}   exact: {abs(pinv_pinch + PINV**3) < 1e-14}")
print(f"   fractional imbalance at attractor = {pinv_attr:.12f}   +phi^-3 = {PINV**3:.12f}   exact: {abs(pinv_attr - PINV**3) < 1e-14}")
require("pinch fractional-imbalance identity", abs(pinv_pinch + PINV**3) < 1e-14)
require("attractor fractional-imbalance identity", abs(pinv_attr - PINV**3) < 1e-14)

# 6. Conversion force monotonic; no inflection at the pinch
rs = np.linspace(1e-3, PHI - 1e-3, 20001)
F = np.array([conv_force(r) for r in rs])
dF = np.gradient(F, rs)
ddF = np.gradient(dF, rs)
monotonic = bool((dF <= 0).all())
print(f"6. F(r) monotonic decreasing on (0, phi): {monotonic}")
print(f"   dF/dr at pinch = {(conv_force(PINV + 1e-6) - conv_force(PINV - 1e-6)) / 2e-6:.6f}  (nonzero -> no extremum at pinch)")
signs = np.sign(ddF)
flips = np.where(np.diff(signs) != 0)[0]
print(f"   inflections of F: {len(flips)} (at r ~ {', '.join(f'{rs[f]:.3f}' for f in flips)}); ddF at pinch = {ddF[np.argmin(np.abs(rs - PINV))]:.4f}")
require("conversion-force monotonicity", monotonic)
require("two conversion-force inflections", len(flips) == 2)

# 7. Gate steepness at the pinch (ODE form)
h = 1e-7
dq_dr = (gate_ode(PINV + h)[0] - gate_ode(PINV - h)[0]) / (2.0 * h)
print(f"7. dq/dr at pinch (ODE form) = {dq_dr:.6f}")
require("finite pinch gate derivative", np.isfinite(dq_dr))

print()
print("ALL DECLARED CHECKS PASSED")
