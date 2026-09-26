#!/usr/bin/env python3
"""
Cascade Depth: N from PDE attractor dynamics
============================================

With r_0 selected as a conditional Wu Xing initial-condition/reference and
λ = 0.1 fixed by the solver convention, while λ = 1/(2w) is a Hypothesized
linkage, the homogeneous two-fluid ODE is fully specified. The cascade depth N is:

    N = ∫_{r_0}^{φ} H(r) / (|dr/dt| · ln φ) dr

where H(r) and dr/dt are the PDE's homogeneous dynamics.

This script computes the integral and compares to the empirical N ≈ 292.

Run:  python computations/cascade_depth_integral.py
"""

import numpy as np
import math

PHI = (1 + math.sqrt(5)) / 2
LAM = 0.1  # λ=0.1 solver convention; 1/(2w) Hypothesized linkage at w=5
r0 = PHI**(-5) / (2 - PHI**(-5))
P2 = PHI**(-2)

print("=== Cascade Depth from PDE Attractor Dynamics ===")
print(f"  φ    = {PHI:.10f}")
print(f"  λ    = {LAM}")
print(f"  r_0  = {r0:.6f}")
print(f"  φ⁻²  = {P2:.6f}")
print()

# ── Homogeneous ODE functions ────────────────────────────────────────────────
def one_minus_q(r):
    """Qi gate openness (1-q), dimensionless form with ρ=1."""
    eps_sq = (r - PHI)**2 / (1 + r)**2
    return (P2 + eps_sq) / (1.0 + P2 + eps_sq)

def H_conv(r):
    """Hubble from conversion mode: H = H_empty + H_conv."""
    H_empty = (LAM / 3.0) * P2
    H_c = (LAM / 3.0) * (PHI - r) * (1.0 + r) / r
    return H_c + H_empty

def dr_dt_abs(r):
    """|dr/dt| = λ(1-q)(φ-r)(1+r) for r < φ."""
    return LAM * one_minus_q(r) * (PHI - r) * (1.0 + r)

# ── Integrand snapshots ──────────────────────────────────────────────────────
for label, r_val in [("r_0", r0), ("φ⁻¹", PHI**(-1)), ("φ-0.1", PHI - 0.1),
                      ("φ-0.01", PHI - 0.01), ("φ-1e-4", PHI - 1e-4)]:
    omq = one_minus_q(r_val)
    H = H_conv(r_val)
    dr = dr_dt_abs(r_val)
    dNdr = H / (dr * math.log(PHI))
    print(f"  r={label:>8s}: (1-q)={omq:.4f}  H={H:.6f}  |dr/dt|={dr:.6f}  dN/dr={dNdr:.3f}")

# ── Numerical integration ─────────────────────────────────────────────────────
print()
print("  ── Numerical integration ──")

def integrate_r_interval(r_start, r_end, n_pts=5000):
    """Integrate in u=-ln(phi-r), resolving the logarithmic attractor tail."""
    u_grid = np.linspace(
        -math.log(PHI - r_start),
        -math.log(PHI - r_end),
        n_pts,
    )
    delta_grid = np.exp(-u_grid)
    r_grid = PHI - delta_grid
    omq = (P2 + (r_grid - PHI)**2 / (1 + r_grid)**2) / (
        1.0 + P2 + (r_grid - PHI)**2 / (1 + r_grid)**2
    )
    H = (
        (LAM / 3.0) * (PHI - r_grid) * (1.0 + r_grid) / r_grid
        + (LAM / 3.0) * P2
    )
    dr_dt = LAM * omq * (PHI - r_grid) * (1.0 + r_grid)
    integrand_u = H * delta_grid / (dr_dt * math.log(PHI))
    if hasattr(np, "trapezoid"):
        return np.trapezoid(integrand_u, u_grid)
    return np.trapz(integrand_u, u_grid)


for r_end_offset in [1e-2, 1e-4, 1e-6]:
    N_val = integrate_r_interval(r0, PHI - r_end_offset)
    print(f"  r_end = φ - {r_end_offset:.0e}:  N = {N_val:.1f}  ({N_val/292*100:.1f}% of empirical 292)")

# ── Analytic tail approximation ───────────────────────────────────────────────
print()
print("  ── Analytic tail ──")
omq_min = P2 / (1.0 + P2)  # (1-q) as r → φ
C = (LAM/3)*P2 / (LAM * omq_min * PHI**2 * math.log(PHI))
print(f"  (1-q)_min = {omq_min:.6f}")
print(f"  Tail coefficient C = {C:.4f}")

for delta_start, delta_end in [(1e-2, 1e-6), (1e-4, 1e-8), (1e-6, 1e-12)]:
    N_tail = C * math.log(delta_start / delta_end)
    print(f"  N_tail [φ-{delta_start:.0e} → φ-{delta_end:.0e}] = {N_tail:.1f}")

# ── Full contribution breakdown ──────────────────────────────────────────────
print()
print("  ── Contribution breakdown (r_end = φ - 1e-4) ──")

r_end = PHI - 1e-4
r_pinch = PHI**(-1)
N_to_pinch = integrate_r_interval(r0, r_pinch)
N_after = integrate_r_interval(r_pinch, r_end)
N_total = N_to_pinch + N_after

print(f"  N(r_0 → φ⁻¹):     {N_to_pinch:8.1f}  ({N_to_pinch/N_total*100:.1f}%)")
print(f"  N(φ⁻¹ → φ-1e-4):  {N_after:8.1f}  ({N_after/N_total*100:.1f}%)")
print(f"  N(total):          {N_total:8.1f}")
print(f"  Empirical N:       292")
print(f"  Ratio:             {N_total/292:.3f}")


# ── Numerical assessment ─────────────────────────────────────────────────────
print()
print("  ═══════════════════════════════════════════════════")
print("  NUMERICAL ASSESSMENT")
print("  ═══════════════════════════════════════════════════")
print()
print(f"  The integral gives N ≈ {N_total:.0f} with cutoff at r = φ - 1e-4.")
print()
print(f"  The tail is LOG-DIVERGENT: ΔN ≈ {C:.3f} · ln((φ-r_start)/(φ-r_end))")
print(f"  Every factor of 10 closer to φ adds ~{C*math.log(10):.1f} rungs.")
print()
if abs(N_total - 292) < 50:
    print(f"  N lies in the right ballpark for comparison. The specific value 292")
    print(f"  remains the empirical cosmic-age calibration setting r_final (how close")
    print(f"  to φ the universe is today). The integral reports a cutoff-dependent")
    print(f"  homogeneous value; the dimensionful calibration remains empirical.")
else:
    print(f"  N = {N_total:.0f} at the declared cutoff is far from 292.")
    print(f"  The divergent tail could reach 292 only by choosing r_final")
    print(f"  correspondingly close to φ; the ODE supplies no such stopping rule.")

# ASSESSMENT
# The homogeneous two-fluid ODE does not select N = 292. Its integral is
# logarithmically divergent as r approaches phi, so any finite N requires a
# declared terminal offset. With r_end = phi - 1e-4 the homogeneous dynamics
# give a cutoff-dependent value; choosing an offset that gives 292 would move
# the empirical calibration into r_final.
#
# The observed cascade depth is instead the DIMENSIONAL ratio:
#   N = log_phi(R_H/l_Pl) = log_phi( [c/H_0] / sqrt(hbar G/c^3) )
#
# This ratio involves dimensionful constants (c, hbar, G, H_0). A dimensionless
# constant cannot determine it without a reference scale.
#
# STATUS: N ≈ 292 is the empirical current-epoch calibration that anchors the
# dimensionless cascade to this universe. The solver convention and phi-based
# relations specify the dimensionless inputs used here; the dimensionful
# constants remain external.
# ══════════════════════════════════════════════════════════════
