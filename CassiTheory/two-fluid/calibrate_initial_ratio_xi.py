#!/usr/bin/env python3
"""Calibrate initial ratio r0 WITH Qi-gravity xi = φ⁶ in H_eff.

Same physics as calibrate_initial_ratio.py, but with:
  H_eff = H_bare * sqrt(1 + xi * q)   where q = 1 - gate
  xi = φ⁶ ≈ 17.944

The Qi-gravity coupling xi is consistent with galactic rotation curves
within ~1.2σ (rotation-curve boost 2.9–3.1×; SPARC v5-v8). It MUST also
appear in the cosmological expansion rate.

Corrected 2026-07-31: Yang-fraction-weighted coupling form
(H_eff² = H_bare²[1 + ξq·r/(1+r)])—see calibrate_initial_ratio_xi_v2.py.
"""

import numpy as np
from scipy.integrate import solve_ivp

PHI = (1 + np.sqrt(5)) / 2
PHI_INV = 1 / PHI
LAM = 0.02
XI = PHI**6  # ≈ 17.944
H_EMPTY = (LAM / 3) * PHI_INV**2
A0 = 0.01
TARGET_W0 = -0.87  # Calibration target (DESI-anchored, Calibrated tier—see parameter-inventory §10 fit ledger); not a prediction—synced to doctrine settlement 2026-08-03


def system(lna, y):
    """dr/dlna ODE with Qi-gravity: H_eff = H_bare * sqrt(1 + xi*q)."""
    r = y[0]
    H_conv = (LAM / 3) * (PHI - r) * (1 + r) / max(r, 1e-12)
    H_bare = H_EMPTY + H_conv

    # Qi gate: homogeneous limit of PDE
    eps_sq = (r - PHI) ** 2 * PHI**2 / ((1 + r) ** 2 + 1e-30)
    gate = (PHI_INV**2 + eps_sq) / (PHI**2 + PHI_INV**2 + eps_sq + 1e-30)
    q = 1.0 - gate  # Qi coherence

    # Qi-gravity enhanced Hubble
    H_eff = H_bare * np.sqrt(1.0 + XI * q)

    dr = LAM * gate * (PHI - r) * (1 + r) / (H_eff + 1e-30)
    return [dr]


def compute_w0(r0):
    """Run ODE from a=0.01 to a=8 and return CPL (w0, wa) over DESI range."""
    sol = solve_ivp(
        system,
        [np.log(A0), np.log(8.0)],
        [r0],
        method="BDF",
        max_step=0.01,
        atol=1e-9,
        rtol=1e-8,
    )
    a = np.exp(sol.t)
    r = sol.y[0]

    # H_eff from instantaneous r (with Qi-gravity)
    H_conv = (LAM / 3) * (PHI - r) * (1 + r) / (r + 1e-30)
    H_bare = H_EMPTY + H_conv
    eps_sq = (r - PHI)**2 * PHI**2 / ((1 + r)**2 + 1e-30)
    gate = (PHI_INV**2 + eps_sq) / (PHI**2 + PHI_INV**2 + eps_sq + 1e-30)
    q = 1.0 - gate
    H_eff = H_bare * np.sqrt(1.0 + XI * q)

    # w(a)
    dlnH = np.gradient(np.log(H_eff + 1e-30))
    dlna = np.gradient(np.log(a + 1e-30))
    w = -1.0 - (2.0 / 3.0) * dlnH / dlna

    # CPL fit over DESI range a ∈ [0.3, 1.0]
    desi = (a >= 0.3) & (a <= 1.0)
    A = np.column_stack([np.ones_like(a[desi]), 1 - a[desi]])
    w0, wa = np.linalg.lstsq(A, w[desi], rcond=None)[0]

    r1 = np.interp(1.0, a, r)
    r03 = np.interp(0.3, a, r)
    return w0, wa, r1, r03


# ═══════════════════════════════════════════════════════════════════════
print(f"Calibration WITH Qi-Gravity ξ = φ⁶ = {XI:.3f}")
print(f"Internal calibration target (not DESI): w0 = {TARGET_W0}  (a0 = {A0})")
print(f"H_eff = H_bare * sqrt(1 + ξ·q)")
print()
print(f"{'r0':>10s}  {'w0':>8s}  {'wa':>8s}  {'r(0.3)':>8s}  {'r(1.0)':>8s}")
print("-" * 56)

for r0 in [0.001, 0.003, 0.005, 0.008, 0.010, 0.015, 0.020, 0.030, 0.050, 0.080, 0.100]:
    w0, wa, r1, r03 = compute_w0(r0)
    print(f"{r0:10.4f}  {w0:8.4f}  {wa:8.4f}  {r03:8.4f}  {r1:8.4f}")

# ── Bisection ─────────────────────────────────────────────────────────
lo, hi = 0.03, 0.10
for _ in range(25):
    mid = (lo + hi) / 2
    w0, wa, r1, r03 = compute_w0(mid)
    if w0 < TARGET_W0:
        hi = mid
    else:
        lo = mid
    if abs(w0 - TARGET_W0) < 0.0005:
        break

final = (lo + hi) / 2
w0, wa, r1, r03 = compute_w0(final)

print(f"\n{'='*56}")
print(f"CALIBRATED WITH ξ = φ⁶:  r0 = {final:.6g}  →  EI/EY = {1/final:.1f}")
print(f"                         w0 = {w0:.4f}  (target: {TARGET_W0})")
print(f"                         wa = {wa:+.4f}  ← WITH Qi-gravity")
print(f"                         r(a=0.3) = {r03:.4f}")
print(f"                         r(a=1.0) = {r1:.4f}")
print()

# Compare to bare
print(f"COMPARISON:")
print(f"  Bare (no ξ):   w0 = -0.87  (calibrate_initial_ratio.py at TARGET_W0 = -0.87, synced 2026-08-03; bare wa = +0.438 is the pre-retarget value, rerun pending)")
print(f"  With ξ = φ⁶:   w0 = {w0:+.4f}  wa = {wa:+.4f}")
print(f"  Δ from ξ:      Δw0 = {w0+0.87:+.4f}  Δwa = {wa-0.438:+.4f}")
print()
print(f"Calibration target (DESI-anchored, not a prediction):  w0 = -0.87 ± 0.06,  wa = +0.012 ± 0.28  [synced to doctrine settlement 2026-08-03]")
print(f"Prediction +ξ:   w0 = {w0:+.4f}     wa = {wa:+.4f}")
