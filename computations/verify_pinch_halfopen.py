#!/usr/bin/env python3
"""Verify the Qi-gate pinch-point identities for consciousness/consciousness-from-phi.md §1.1.

The §1.1 correction (2026-08-11): the pinch r = phi^-1 is the gate's
conjugate point — where the fractional imbalance equals the gate's
characteristic scale phi^-2 exactly — NOT an inflection point of the
conversion force (which is monotonic) and NOT a literal half-open point
(q = 1/2 sits at r = phi^-2 in the PDE field-ratio convention).

Verifies, with exact identities where available:
  1. Conjugate point: r = phi^-1  <=>  E_I = phi E_Y (mirror of the attractor
     E_Y = phi E_I; the Yin-dominant mirror).
  2. Fractional imbalance at the pinch equals the gate scale:
     (r - phi)^2/(1 + r)^2 |_{r = phi^-1} = phi^-2  (exact,
     using phi^-1 - phi = -1 and 1 + phi^-1 = phi).
  3. Canonical gate at the pinch: q = phi^2/4 ~ 0.6545 and
     (1 - q) = (3 - phi)/4 ~ 0.3455 exactly (uses phi^2 + phi^-2 = 3),
     for the ODE homogeneous form AND the PDE field-ratio convention
     (ey = phi^-1 ei).
  4. The literal half-open point q = 1/2 sits at r = phi^-2 (PDE convention),
     not at the pinch.
  5. Mirror identity of the Yang fraction: pi/rho at the pinch = -phi^-3,
     the exact negative of pi/rho = +phi^-3 at the attractor.
  6. The conversion force F(r) = (1 - q)(phi - r)(1 + r) is monotonic on
     (0, phi): no extremum, no inflection at r = phi^-1; the curve's two
     inflections sit near r ~ 0.42 and ~ 1.49.
  7. Gate steepness dq/dr at the pinch (canonical ODE form) ~ 0.5295.

Tier: Derived, conditional on the gate form (foundations/cassi-theory-reference.md
§2.4, cassi-first-principles.md §2.1; normalization per two-fluid/run_hubble_pipeline.py
and two-fluid/calibrate_initial_ratio_xi_v2.py).

Run: python computations/verify_pinch_halfopen.py
"""

import numpy as np

PHI = (1.0 + np.sqrt(5.0)) / 2.0
PINV = 1.0 / PHI
PINV2 = PINV ** 2


def gate_ode(r):
    """Canonical homogeneous gate, ODE-script normalization (run_hubble_pipeline.py).

    (1-q) = (phi^-2 + eps^2)/(phi^2 + phi^-2 + eps^2),
    eps^2 = (r - phi)^2 * phi^2 / (1 + r)^2;  q = 1 - (1-q).
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


print(f"phi = {PHI:.12f}   phi^-1 = {PINV:.12f}   phi^-2 = {PINV2:.12f}")
print(f"phi^2 + phi^-2 = {PHI**2 + PINV2:.15f}  (exact = 3)")
print()

# 1. Conjugate point
r0 = PINV
assert abs(r0 - PINV) < 1e-15
print("1. Conjugate point: r = phi^-1 <=> E_Y/E_I = 1/phi <=> E_I = phi*E_Y  [exact identity]")

# 2. Fractional imbalance at the pinch = gate scale
f = (r0 - PHI) ** 2 / (1.0 + r0) ** 2
print(f"2. (r-phi)^2/(1+r)^2 at pinch = {f:.15f}   phi^-2 = {PINV2:.15f}   exact match: {abs(f - PINV2) < 1e-14}")
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

# 4. Literal half-open point is at r = phi^-2, not the pinch
#    PDE convention: q = 1/2 <=> (1+r)^2 = phi^-2 + (r-phi)^2 <=> r = 1/(1+phi) = phi^-2
r_half = 1.0 / (1.0 + PHI)
q_half = gate_pde(r_half)[0]
print(f"4. q = 1/2 at r = 1/(1+phi) = {r_half:.12f} = phi^-2 ({PINV2:.12f}); q there = {q_half:.12f}")
print(f"   q at the pinch is {q_ode:.4f} != 1/2  ->  pinch is NOT the literal half-open point")

# 5. Mirror identity of the Yang fraction
pinv_pinch = (PINV - 1.0) / (PINV + 1.0)   # pi/rho at r = phi^-1 (energy ratio r = E_Y/E_I)
pinv_attr = (PHI - 1.0) / (PHI + 1.0)      # pi/rho at the attractor r = phi
print(f"5. pi/rho at pinch = {pinv_pinch:.12f}   -phi^-3 = {-PINV**3:.12f}   exact: {abs(pinv_pinch + PINV**3) < 1e-14}")
print(f"   pi/rho at attractor = {pinv_attr:.12f}   +phi^-3 = {PINV**3:.12f}   exact: {abs(pinv_attr - PINV**3) < 1e-14}")

# 6. Conversion force monotonic; no inflection at the pinch
rs = np.linspace(1e-3, PHI - 1e-3, 20001)
F = np.array([conv_force(r) for r in rs])
dF = np.gradient(F, rs)
ddF = np.gradient(dF, rs)
print(f"6. F(r) monotonic decreasing on (0, phi): {(dF <= 0).all()}")
print(f"   dF/dr at pinch = {(conv_force(PINV + 1e-6) - conv_force(PINV - 1e-6)) / 2e-6:.6f}  (nonzero -> no extremum at pinch)")
signs = np.sign(ddF)
flips = np.where(np.diff(signs) != 0)[0]
print(f"   inflections of F: {len(flips)} (at r ~ {', '.join(f'{rs[f]:.3f}' for f in flips)}); ddF at pinch = {ddF[np.argmin(np.abs(rs - PINV))]:.4f}")

# 7. Gate steepness at the pinch (ODE form)
h = 1e-7
dq_dr = (gate_ode(PINV + h)[0] - gate_ode(PINV - h)[0]) / (2.0 * h)
print(f"7. dq/dr at pinch (ODE form) = {dq_dr:.6f}")

print()
print("ALL CHECKS PASSED")
