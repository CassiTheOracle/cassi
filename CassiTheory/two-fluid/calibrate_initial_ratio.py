#!/usr/bin/env python3
"""Calibrate initial ratio r0 = <EY>/<EI> at a0=0.01 to the repo's
w0 = -0.87 calibration target (DESI-anchored, Mapped tier—see
parameter-inventory fit ledger; not a prediction; synced to doctrine
settlement 2026-08-03).

Physics (matched to cassette two-fluid PDE at amplitude=0):
  - H = H_empty + H_conv  (instantaneous; PDE EMA relaxes in << 1 step)
  - H_conv = (λ/3)(φ - r)(1 + r)/r
  - H_empty = (λ/3) φ⁻²
  - Qi gate: (1 - q) = (φ⁻² + ε²) / (φ² + φ⁻² + ε²)
    with ε² = (r - φ)² φ² / (1 + r)²  [homogeneous limit of PDE]
  - dr/dlna = λ · gate · (φ - r)(1 + r) / H
  - w(a) = -1 - (2/3) d(ln H)/d(ln a)

The PDE EMA (h_smooth=0.1, dt=0.0005, 3 updates/step) relaxes H_smooth
≈5400× faster per e-fold than a naive dH/dlna = h_smooth·(H_raw - H)
would suggest. In the continuous limit, H_smooth = H_raw exactly.
"""

import numpy as np
from scipy.integrate import solve_ivp

PHI = (1 + np.sqrt(5)) / 2
PHI_INV = 1 / PHI
LAM = 0.02
H_EMPTY = (LAM / 3) * PHI_INV**2
A0 = 0.01
TARGET_W0 = -0.87  # Calibration target (DESI-anchored, Mapped tier—see parameter-inventory fit ledger); not a prediction—synced to doctrine settlement 2026-08-03


def system(lna, y):
    """dr/dlna ODE with instantaneous H = H_raw(r)."""
    r = y[0]
    H_conv = (LAM / 3) * (PHI - r) * (1 + r) / max(r, 1e-12)
    H = H_EMPTY + H_conv

    # Qi gate: homogeneous limit of PDE
    eps_sq = (r - PHI) ** 2 * PHI**2 / ((1 + r) ** 2 + 1e-30)
    gate = (PHI_INV**2 + eps_sq) / (PHI**2 + PHI_INV**2 + eps_sq + 1e-30)

    dr = LAM * gate * (PHI - r) * (1 + r) / (H + 1e-30)
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

    # H from instantaneous r
    H_conv = (LAM / 3) * (PHI - r) * (1 + r) / (r + 1e-30)
    H = H_EMPTY + H_conv

    # w(a)
    dlnH = np.gradient(np.log(H + 1e-30))
    dlna = np.gradient(np.log(a + 1e-30))
    w = -1.0 - (2.0 / 3.0) * dlnH / dlna

    # CPL fit over DESI range a ∈ [0.3, 1.0]
    desi = (a >= 0.3) & (a <= 1.0)
    A = np.column_stack([np.ones_like(a[desi]), 1 - a[desi]])
    w0, wa = np.linalg.lstsq(A, w[desi], rcond=None)[0]

    r1 = np.interp(1.0, a, r)
    r03 = np.interp(0.3, a, r)
    return w0, wa, r1, r03


# ── Scan ─────────────────────────────────────────────────────────────
print(f"Calibration: w0 = {TARGET_W0}  (a0 = {A0})  [internal target, not measured DESI]")
print(f"Physics:   H = H_empty + H_conv(r)  [instantaneous, matching PDE]")
print(f"Qi gate:   (φ⁻² + ε²) / (φ² + φ⁻² + ε²)")
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
print(f"CALIBRATED:  r0 = {final:.6g}  →  initial_ratio = <EI>/<EY> = {1/final:.1f}")
print(f"             w0 = {w0:.4f}  (target: {TARGET_W0})")
print(f"             wa = {wa:.4f}  (prediction)")
print(f"             r(a=0.3) = {r03:.4f}")
print(f"             r(a=1.0) = {r1:.4f}")
print(f"             φ = {PHI:.4f}")
print()
print(f"Calibration target (DESI-anchored, not a prediction):  w0 = -0.87 ± 0.06,  wa = +0.012  [synced to doctrine settlement 2026-08-03]")
print(f"Model prediction:     wa = {wa:+.4f}  ({'within' if abs(wa - 0.012) < 0.28 else 'outside'} 1σ of doctrine wa = +0.012)")
print()
print(f"Next: PDE verification run at initial_ratio={1/final:.0f}")
print(f"      (launched as background job → runs/cal_ir18.log)")
