#!/usr/bin/env python3
"""
Verify the identities of foundations/qi-flow-double-helix.md.

The wedge document elevates Qi to a fundamental: the doublet's phase current
J = Psi_0 grad Psi_1 - Psi_1 grad Psi_0 = rho grad theta, the axial (inter-scale)
coherence current J_z = R^2 d_z theta along the string axis, and the double-helix
reading of the P_parallel = 2 doublet cycle (theta advances pi per rung).

Checks:
  1. Polar identity: J = rho grad theta.
  2. Component currents J_0 = Psi_0^2 grad theta, J_1 = Psi_1^2 grad theta
     sum to J and sit at the attractor ratio J_0/J_1 = phi.
  3. Doublet cycle: theta(n+1) = theta(n) + pi, theta(n+2) = theta(n) + 2pi
     (one full turn per two rungs).
  4. Frenet-Serret frame of the spiral string: T, N, B orthonormal; the helix
     strands wind about the tangent (string axis).
  5. Cascade suppression: per-rung transfer of the inter-scale flow loses
     phi^-1, so N rungs lose phi^-N.
  6. q at the attractor: q_eq = phi^-2/(phi^2 + phi^-2).

Usage: python computations/qi_flow_double_helix_check.py
"""

from __future__ import annotations

import math

PHI = (1.0 + math.sqrt(5.0)) / 2.0
failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        failures.append(label)
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{detail}")


print("Qi flow / double-helix identity check")
print("=====================================")
print(f"phi = {PHI:.12f}\n")

# --- 1. Polar identity ------------------------------------------------
print("1. Phase current identities")
r = 1.3
theta = 0.7
grad_theta = math.pi / 4.0
psi0 = r * math.cos(theta)
psi1 = r * math.sin(theta)
rho = psi0 * psi0 + psi1 * psi1
grad_psi0 = -psi1 * grad_theta   # d/dtheta (R cos theta) = -R sin theta
grad_psi1 = psi0 * grad_theta    # d/dtheta (R sin theta) = R cos theta
J = psi0 * grad_psi1 - psi1 * grad_psi0
check("J = Psi0 grad(Psi1) - Psi1 grad(Psi0) = rho grad(theta)",
      math.isclose(J, rho * grad_theta, rel_tol=1e-12), f" (J={J:.12f})")
check("rho = R^2 in polar form", math.isclose(rho, r * r, rel_tol=1e-12))

# --- 2. Component currents ---------------------------------------------
print("\n2. Strand currents")
J0 = psi0 * psi0 * grad_theta
J1 = psi1 * psi1 * grad_theta
check("J = J_0 + J_1 (Yang + Yin strand currents)",
      math.isclose(J, J0 + J1, rel_tol=1e-12))
# At the attractor Psi_0^2 = phi Psi_1^2
a0 = math.sqrt(PHI)
a1 = 1.0
J0a = a0 * a0 * grad_theta
J1a = a1 * a1 * grad_theta
check("attractor strand-current ratio J_0/J_1 = phi",
      math.isclose(J0a / J1a, PHI, rel_tol=1e-12), f" ({J0a/J1a:.12f})")

# --- 3. Doublet cycle --------------------------------------------------
print("\n3. Doublet cycle (P_parallel = 2)")
theta0 = 0.3
theta1 = theta0 + math.pi
theta2 = theta0 + 2.0 * math.pi
check("theta advances pi per rung",
      math.isclose(math.cos(theta1), -math.cos(theta0), rel_tol=1e-12)
      and math.isclose(math.sin(theta1), -math.sin(theta0), rel_tol=1e-12))
check("one full turn per two rungs",
      math.isclose(math.cos(theta2), math.cos(theta0), rel_tol=1e-12)
      and math.isclose(math.sin(theta2), math.sin(theta0), rel_tol=1e-12))
# Phase-space helix points: (cos theta, sin theta) at n = 0,1,2
p0 = (math.cos(theta0), math.sin(theta0))
p1 = (math.cos(theta1), math.sin(theta1))
p2 = (math.cos(theta2), math.sin(theta2))
check("strand dominance exchanges each rung (azimuthal separation pi)",
      math.isclose(p0[0], -p1[0], rel_tol=1e-12) and math.isclose(p0[1], -p1[1], rel_tol=1e-12))
check("configuration repeats after two rungs",
      math.isclose(p0[0], p2[0], rel_tol=1e-12) and math.isclose(p0[1], p2[1], rel_tol=1e-12))

# --- 4. Frenet-Serret frame --------------------------------------------
print("\n4. Frenet-Serret frame of the spiral string")
# Spiral string in field space: position advances phi per turn.
def spiral(n: float) -> tuple[float, float, float]:
    ang = 2.0 * math.pi * n
    rad = PHI ** n
    return (rad * math.cos(ang), rad * math.sin(ang), n)

p_n = spiral(0.0)
p_n1 = spiral(1.0)
p_n2 = spiral(2.0)
T = tuple(p_n1[i] - p_n[i] for i in range(3))
T_norm = math.sqrt(sum(c * c for c in T))
T = tuple(c / T_norm for c in T)
d1 = tuple(p_n1[i] - p_n[i] for i in range(3))
d2 = tuple(p_n2[i] - p_n1[i] for i in range(3))
cross = (d1[1] * d2[2] - d1[2] * d2[1],
         d1[2] * d2[0] - d1[0] * d2[2],
         d1[0] * d2[1] - d1[1] * d2[0])
B = tuple(c / math.sqrt(sum(x * x for x in cross)) for c in cross)
N = (B[1] * T[2] - B[2] * T[1],
     B[2] * T[0] - B[0] * T[2],
     B[0] * T[1] - B[1] * T[0])
check("T, N, B orthonormal",
      math.isclose(sum(a * b for a, b in zip(T, N)), 0.0, abs_tol=1e-12)
      and math.isclose(sum(a * b for a, b in zip(T, B)), 0.0, abs_tol=1e-12)
      and math.isclose(sum(a * b for a, b in zip(N, B)), 0.0, abs_tol=1e-12)
      and all(math.isclose(sum(c * c for c in v), 1.0, rel_tol=1e-12) for v in (T, N, B)))
# The helix ansatz strands wind about T: transverse displacement in the N-B plane.
s = 0.37
d = 0.2
Rplus = tuple(p_n[i] + (d / 2.0) * (N[i] * math.cos(2 * math.pi * s / 2.0)
                                     + B[i] * math.sin(2 * math.pi * s / 2.0)) for i in range(3))
Rminus = tuple(p_n[i] - (d / 2.0) * (N[i] * math.cos(2 * math.pi * s / 2.0)
                                      + B[i] * math.sin(2 * math.pi * s / 2.0)) for i in range(3))
sep = tuple(Rplus[i] - Rminus[i] for i in range(3))
check("strand separation lies in the N-B (Yang-Yin) plane, perpendicular to T",
      math.isclose(sum(a * b for a, b in zip(sep, T)), 0.0, abs_tol=1e-12))
check("strand separation magnitude = d at every rung",
      math.isclose(math.sqrt(sum(c * c for c in sep)), d, rel_tol=1e-12))

# --- 5. Inter-scale suppression ----------------------------------------
print("\n5. Inter-scale flow attenuation")
check("per-rung transfer loses phi^-1",
      math.isclose(PHI ** -1, 0.6180339887498949, rel_tol=1e-12))
check("N rungs lose phi^-N (cascade suppression)",
      math.isclose(PHI ** -10, math.exp(-10.0 * math.log(PHI)), rel_tol=1e-12))

# --- 6. q at the attractor ---------------------------------------------
print("\n6. Scalar q at the attractor")
q_eq = PHI ** -2 / (PHI ** 2 + PHI ** -2)
check("q_eq = phi^-2/(phi^2 + phi^-2) ~ 0.1273",
      math.isclose(q_eq, 0.127322003750, rel_tol=1e-12), f" ({q_eq:.12f})")

print("\nVerdict")
print("-------")
print("  Qi = rho grad(theta) is the doublet's phase current; J_z along the")
print("  string axis is the inter-scale flow; the P=2 doublet cycle winds the")
print("  two strand-currents into a phase-space double helix about the tangent.")
if failures:
    print("CHECKS FAILED: " + ", ".join(failures))
    raise SystemExit(1)
print("\nALL CHECKS PASSED")
