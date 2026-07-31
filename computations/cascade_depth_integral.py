#!/usr/bin/env python3
"""
Cascade Depth: N from PDE attractor dynamics
============================================

Now that r_0 and λ = 1/(2w) are derived from w=5, the homogeneous
two-fluid ODE is fully specified. The cascade depth N is:

    N = ∫_{r_0}^{φ} H(r) / (|dr/dt| · ln φ) dr

where H(r) and dr/dt are the PDE's homogeneous dynamics.

This script computes the integral and compares to the empirical N ≈ 292.

Run:  python foundations/cascade_depth_integral.py
"""

import numpy as np
import math

PHI = (1 + math.sqrt(5)) / 2
LAM = 0.1  # 1/(2w), w=5 derived
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

for r_end_offset in [1e-2, 1e-4, 1e-6]:
    r_end = PHI - r_end_offset
    n_pts = 5000
    r_grid = np.linspace(r0, r_end, n_pts)

    omq = (P2 + (r_grid - PHI)**2 / (1 + r_grid)**2) / (1.0 + P2 + (r_grid - PHI)**2 / (1 + r_grid)**2)
    H = (LAM / 3.0) * (PHI - r_grid) * (1.0 + r_grid) / r_grid + (LAM / 3.0) * P2
    dr = LAM * omq * (PHI - r_grid) * (1.0 + r_grid)
    igrand = H / (dr * math.log(PHI))

    N_val = np.trapezoid(igrand, r_grid)
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
n_pts = 5000
r_grid = np.linspace(r0, r_end, n_pts)
omq = (P2 + (r_grid - PHI)**2 / (1 + r_grid)**2) / (1.0 + P2 + (r_grid - PHI)**2 / (1 + r_grid)**2)
H = (LAM / 3.0) * (PHI - r_grid) * (1.0 + r_grid) / r_grid + (LAM / 3.0) * P2
dr = LAM * omq * (PHI - r_grid) * (1.0 + r_grid)
igrand = H / (dr * math.log(PHI))

r_pinch = PHI**(-1)
idx_p = np.searchsorted(r_grid, r_pinch)

N_to_pinch = np.trapezoid(igrand[:idx_p], r_grid[:idx_p])
N_after = np.trapezoid(igrand[idx_p:], r_grid[idx_p:])
N_total = N_to_pinch + N_after

print(f"  N(r_0 → φ⁻¹):     {N_to_pinch:8.1f}  ({N_to_pinch/N_total*100:.1f}%)")
print(f"  N(φ⁻¹ → φ-1e-4):  {N_after:8.1f}  ({N_after/N_total*100:.1f}%)")
print(f"  N(total):          {N_total:8.1f}")
print(f"  Empirical N:       292")
print(f"  Ratio:             {N_total/292:.3f}")

# Also: from observational r (today: r ≈ φ with tiny offset from w0)
# The attractor never quite reaches φ in finite time
# r_final = φ · (1 - H₀·t_age adjustment)
# This is essentially empirical

# ── Honest assessment ────────────────────────────────────────────────────────
print()
print("  ═══════════════════════════════════════════════════")
print("  HONEST ASSESSMENT")
print("  ═══════════════════════════════════════════════════")
print()
print(f"  The integral gives N ≈ {N_total:.0f} with cutoff at r = φ - 1e-4.")
print()
print(f"  The tail is LOG-DIVERGENT: ΔN ≈ {C:.3f} · ln((φ-r_start)/(φ-r_end))")
print(f"  Every factor of 10 closer to φ adds ~{C*math.log(10):.1f} rungs.")
print()
if abs(N_total - 292) < 50:
    print(f"  N lies in the right ballpark. The specific value 292 emerges from")
    print(f"  the empirical cosmic age setting r_final (how close to φ the universe is today).")
    print(f"  The cascade depth is CONDITIONALLY derived: given the age of the")
    print(f"  universe, the dynamics (now fully specified) determine N.")
else:
    print(f"  N = {N_total:.0f} is far from 292.")
    print(f"  Check: the ODE model may be missing spatial structure contributions")
    print(f"  to H(r) or incomplete treatment of (1-q) at the attractor.")

# ══════════════════════════════════════════════════════════════
# THEOREM (July 2026): The cascade depth N = 292 cannot be
# derived from the homogeneous two-fluid ODE with the derived
# λ = 0.1 and r_0 ≈ 0.0472. The homogeneous dynamics give
# N ≈ 9 φ-doublings over the full r-range.
#
# N = 292 emerges from the DIMENSIONAL ratio:
#   N = log_φ(R_H/ℓ_Pl) = log_φ( [c/H_0] / √(ℏG/c³) )
#
# This ratio involves three dimensionful constants (c, ℏ, G).
# A dimensionless constant cannot determine a dimensionful ratio
# without a reference scale.
#
# STATUS: N = 292 is the single empirical calibration point
# that anchors the dimensionless cascade to a specific
# universe. All dimensionless parameters are derived from φ.
# The dimensionful constants (c, ℏ, G) remain external.
# ══════════════════════════════════════════════════════════════
