#!/usr/bin/env python3
"""
Full Calibrated w_a ODE—Bare + Qi-Gravity (xi = phi^6)
==========================================================

Reproduces the Cassi structural prediction w_a = +0.46 (bare),
then computes w_a WITH the Qi-gravity H enhancement xi = phi^6
(corrected Yang-fraction coupling form: w_a = +0.012; see
calibrate_initial_ratio_xi_v2.py, corrected 2026-07-31).

The ODE is lambda-independent: dr/da = f(r, a) where lambda cancels
from the ratio dr/dt / H, so the result is structural.

Calibrated initial condition: r_0 at a=0.01 chosen to match the
internal w_0 = -0.838 calibration target (not a measured DESI
constraint—corrected 2026-07-31) or the gap-derived r_0
(w_0 = -0.856; corrected 2026-07-31: w_0 = -0.87, see
calibrate_initial_ratio_xi_v2.py).

Run: python wa_full_ode.py
"""

import numpy as np
import math

PHI = (1 + math.sqrt(5)) / 2
LAM = 0.1
XI = PHI**6  # Qi-gravity coupling ≈ 17.944
P2 = PHI**(-2)

def q_gate(r):
    """Qi gate: q = 1/(1 + phi^-2 + (r-phi)^2/(1+r)^2)."""
    eps_sq = (r - PHI)**2 / (1 + r)**2
    return 1.0 / (1.0 + P2 + eps_sq)

def H_bare(r):
    """Hubble without Qi-gravity."""
    H_empty = (LAM / 3.0) * P2
    # Use abs(phi-r) to handle both r < phi and r > phi
    H_c = (LAM / 3.0) * abs(PHI - r) * (1.0 + r) / r
    return H_c + H_empty

def H_eff(r, xi):
    """Hubble with Qi-gravity: H_eff = H_bare * sqrt(1 + xi*q)."""
    return H_bare(r) * math.sqrt(1.0 + xi * q_gate(r))

def dr_dt(r):
    """dr/dt = -lambda*(1-q)*(r-phi)*(1+r). Sign handles r < phi or r > phi."""
    return -LAM * (1.0 - q_gate(r)) * (r - PHI) * (1.0 + r)

def integrate_ode(r_start, a_start=0.01, a_end=1.0, n_pts=50000, xi=0.0):
    """Integrate dr/da = dr/dt / (H_eff * a) and compute w(a)."""
    
    ln_a = np.linspace(math.log(a_start), math.log(a_end), n_pts)
    a_grid = np.exp(ln_a)
    
    r = np.zeros(n_pts)
    r[0] = r_start
    
    # Integrate with midpoint method
    for i in range(n_pts - 1):
        a_cur = a_grid[i]
        a_next = a_grid[i+1]
        da = a_next - a_cur
        a_mid = 0.5 * (a_cur + a_next)
        
        r_cur = r[i]
        H_val = H_eff(r_cur, xi)
        drda = dr_dt(r_cur) / (H_val * a_mid)
        
        r_next = r_cur + drda * da
        # Keep r physically bounded
        if r_next >= PHI:
            r_next = PHI - 1e-15
        if r_next <= 0:
            r_next = 1e-15
        r[i+1] = r_next
    
    # Compute H(a) and w(a)
    H_vals = np.array([H_eff(rr, xi) for rr in r])
    
    # d ln H / d ln a via central differences
    dlnH_dlna = np.zeros(n_pts)
    for i in range(1, n_pts - 1):
        da_fwd = a_grid[i+1] - a_grid[i-1]
        dH = (H_vals[i+1] - H_vals[i-1]) / da_fwd
        dlnH_dlna[i] = (a_grid[i] / H_vals[i]) * dH
    
    # Endpoints
    dlnH_dlna[0] = (a_grid[0] / H_vals[0]) * (H_vals[1] - H_vals[0]) / (a_grid[1] - a_grid[0])
    dlnH_dlna[-1] = (a_grid[-1] / H_vals[-1]) * (H_vals[-1] - H_vals[-2]) / (a_grid[-1] - a_grid[-2])
    
    w_vals = -1.0 - (2.0/3.0) * dlnH_dlna
    
    # Fit w(a) = w_0 + w_a*(1-a) over a ∈ [0.33, 1.0] (standard DESI range)
    mask = a_grid >= 0.33
    a_fit = a_grid[mask]
    w_fit = w_vals[mask]
    
    X = np.column_stack([np.ones_like(a_fit), 1.0 - a_fit])
    coeffs = np.linalg.lstsq(X, w_fit, rcond=None)[0]
    
    return a_grid, w_vals, coeffs[0], coeffs[1], r, H_vals

# ── Calibration: find r_start that gives w_0 ≈ -0.838 ──────────────────────
print("=== Calibrating initial ratio for w_0 match ===")
print()

# Binary search for r_start that gives w_0 ≈ -0.838 (bare, xi=0)
# The ratio at a=0.01 should be r = E_Y/E_I << phi (Yin-dominated early)
# Docs say calibrated r_0 = 1/23 at a_0 = 0.01

# Quick scan: try a few initial ratios
for r_try in [0.04, 0.043, 0.0435, 0.044, 0.045, 0.05, 0.10, 0.20]:
    a_grid, w_vals, w0, wa, r_hist, H_hist = integrate_ode(r_try, xi=0.0, n_pts=20000)
    print(f"  r_start={r_try:.4f}: w_0={w0:.4f}, w_a={wa:+.4f}")

# The calibrated r should give w_0 ≈ -0.838
# Let me find it precisely
print()
print("Binary search for calibrated r_start...")

lo, hi = 0.04, 0.05
for _ in range(30):
    mid = (lo + hi) / 2
    _, _, w0_mid, _, _, _ = integrate_ode(mid, xi=0.0, n_pts=15000)
    if w0_mid > -0.838:  # w_0 is more negative → need larger r
        lo = mid
    else:
        hi = mid

r_cal = (lo + hi) / 2
a_grid, w_vals, w0_cal, wa_cal, r_hist, H_hist = integrate_ode(r_cal, xi=0.0, n_pts=50000)
print(f"  Calibrated: r_start = {r_cal:.6f}")
print(f"  Bare (xi=0):  w_0 = {w0_cal:.4f}, w_a = {wa_cal:+.4f}")
print()

# ── Now add Qi-gravity ──────────────────────────────────────────────────────
a_xi, w_xi, w0_xi, wa_xi, r_xi, H_xi = integrate_ode(r_cal, xi=XI, n_pts=50000)
print(f"  Qi-gravity:   w_0 = {w0_xi:.4f}, w_a = {wa_xi:+.4f}")

print()
print(f"  Internal calibration target (not DESI):  w_0 = -0.838 ± 0.055, w_a = -0.51 ± 0.38")
print()

dw0 = w0_xi - w0_cal
dwa = wa_xi - wa_cal
print(f"  Shift from Qi-gravity: Δw_0 = {dw0:+.4f}, Δw_a = {dwa:+.4f}")

# Also try gap-derived (uncalibrated) r = phi^-5/(2-phi^-5)
r_gap = PHI**(-5) / (2 - PHI**(-5))
_, _, w0_gap, wa_gap, _, _ = integrate_ode(r_gap, xi=0.0, n_pts=50000)
_, _, w0_gap_xi, wa_gap_xi, _, _ = integrate_ode(r_gap, xi=XI, n_pts=50000)
print()
print(f"  Gap-derived r_0 = {r_gap:.6f}:")
print(f"    Bare: w_0 = {w0_gap:.4f}, w_a = {wa_gap:+.4f}")
print(f"    +xi:  w_0 = {w0_gap_xi:.4f}, w_a = {wa_gap_xi:+.4f}")

# w at key redshifts
print()
print("  w(a) at key redshifts (Qi-gravity):")
for z_label, a_val in [("z=0", 1.0), ("z=0.5", 1/1.5), ("z=1", 0.5), ("z=2", 1/3)]:
    idx = min(np.searchsorted(a_xi, a_val), len(w_xi)-1)
    print(f"    {z_label:>6s} (a={a_val:.3f}): w = {w_xi[idx]:.4f}")
