#!/usr/bin/env python3
"""Calibrate initial ratio r0 with the Yang-fraction-weighted Qi coupling.

Revision 2026-07-31 (v2): the coupling verified in galactic rotation
curves (SPARC v5-v8: v^2 = G [M_bar + (1 + xi q) M_Y] / r — the boost
applies to the Yang component only) has the homogeneous analogue

    H_eff^2 = H_bare^2 * [1 + xi q * r/(1+r)],   r = E_Y/E_I,

i.e. the boost is weighted by the Yang fraction r/(1+r), which is
exactly phi/(1+phi) = 1/phi ~ 0.618 at the attractor r = phi. The v1
form H_eff = H_bare * sqrt(1 + xi q) implicitly assumed pure-Yang
sourcing (fraction = 1) and boosted H by ~2.5x already at z ~ 99 where
r ~ 0.03 (Yin-dominated) — inconsistent with the galactic convention.

DESI DR2 anchors (2026-07-31 verification):
  - Paper II abstract (arXiv:2503.14738): w0 > -1, wa < 0 at 3.1 sigma
    (BAO+CMB); 2.8-4.2 sigma with SNe compilations
  - Pivot values from the paper: w_p = -1.024 +- 0.043 / -0.954 +- 0.024
  - Table 9 (widely reported, per-table note): w0 ~ -0.72 +- 0.09,
    wa ~ -0.73 +- 0.28 (BAO+CMB+Pantheon+); range across SNe:
    wa ~ -0.6 to -1.1
  - The repo's previous calibration-target pair is NOT a
    verified DESI constraint: it was the calibration target hardcoded in
    calibrate_initial_ratio.py / figure_data.py and echoed back by
    observational_constraints.md 1.4-1.5 ("0 sigma" = circular); both
    scripts now carry the DESI-anchored w0 = -0.87 (calibration target,
    not a prediction; synced to doctrine settlement 2026-08-03).

Run: python two-fluid/calibrate_initial_ratio_xi_v2.py
"""

import numpy as np
from scipy.integrate import solve_ivp

PHI = (1 + np.sqrt(5)) / 2
PHI_INV = 1 / PHI
LAM = 0.02
XI = PHI**6  # ~ 17.944
H_EMPTY = (LAM / 3) * PHI_INV**2
A0 = 0.01

# Real DESI w0 anchors for calibration (Table 9 recollection + range)
W0_CENTRAL = -0.75
W0_LO = -0.72
W0_HI = -0.79
# DESI wa anchors
WA_T9 = (-0.73, 0.28)     # Table 9, BAO+CMB+Pantheon+ [INFERENCE]
WA_RANGE = (-0.60, -1.10) # across SNe compilations


def gate_and_q(r):
    """Canonical homogeneous gate: q = phi^2 / (phi^2 + phi^-2 + eps^2),
    eps^2 = (r-phi)^2 phi^2 / (1+r)^2.  q_max = 0.873 at r = phi."""
    eps_sq = (r - PHI) ** 2 * PHI**2 / ((1 + r) ** 2 + 1e-30)
    gate = (PHI_INV**2 + eps_sq) / (PHI**2 + PHI_INV**2 + eps_sq + 1e-30)
    return gate, 1.0 - gate


def H_bare(r):
    H_conv = (LAM / 3) * (PHI - r) * (1 + r) / max(r, 1e-12)
    return H_EMPTY + H_conv


def H_eff(r, mode):
    """H_eff under the three coupling conventions:
    'bare': no coupling; 'full': sqrt(1+xi q) (v1, pure-Yang sourcing);
    'yang': sqrt(1 + xi q * r/(1+r)) (v2, Yang-fraction weighting)."""
    if mode == 'bare':
        return H_bare(r)
    _, q = gate_and_q(r)
    if mode == 'full':
        return H_bare(r) * np.sqrt(1.0 + XI * q)
    if mode == 'yang':
        frac = r / (1.0 + r)
        return H_bare(r) * np.sqrt(1.0 + XI * q * frac)
    raise ValueError(mode)


def system(lna, y, mode):
    r = y[0]
    H = H_eff(r, mode)
    gate, _ = gate_and_q(r)
    dr = LAM * gate * (PHI - r) * (1 + r) / (H + 1e-30)
    return [dr]


def compute_w0(r0, mode):
    """Run ODE from a=0.01 to a=8; return (w0, wa) CPL over a in [0.3, 1]."""
    sol = solve_ivp(system, [np.log(A0), np.log(8.0)], [r0],
                    args=(mode,), method="BDF", max_step=0.01,
                    atol=1e-9, rtol=1e-8)
    a = np.exp(sol.t)
    r = sol.y[0]
    H = np.array([H_eff(rr, mode) for rr in r])
    dlnH = np.gradient(np.log(H + 1e-30))
    dlna = np.gradient(np.log(a + 1e-30))
    w = -1.0 - (2.0 / 3.0) * dlnH / dlna
    desi = (a >= 0.3) & (a <= 1.0)
    A = np.column_stack([np.ones_like(a[desi]), 1 - a[desi]])
    w0, wa = np.linalg.lstsq(A, w[desi], rcond=None)[0]
    return w0, wa


def calibrate(target, mode, lo=0.001, hi=0.15):
    for _ in range(30):
        mid = (lo + hi) / 2
        w0, _ = compute_w0(mid, mode)
        if w0 > target:
            lo = mid
        else:
            hi = mid
        if abs(w0 - target) < 2e-4:
            break
    return (lo + hi) / 2


# ============================================================
print(f"w_a revisit: Yang-fraction-weighted Qi coupling (v2)")
print(f"xi = phi^6 = {XI:.3f}   lambda = {LAM}")
print(f"DESI anchors: w0 ~ {W0_CENTRAL} ({W0_LO}..{W0_HI});  "
      f"wa = {WA_T9[0]} +- {WA_T9[1]} (Table 9 [INF]); range {WA_RANGE}")
print()

# --- 1. structural (gap-derived) r0, all three coupling modes ---
r_gap = PHI**(-5) / (2 - PHI**(-5))
print(f"Gap-derived r0 = {r_gap:.5f} (EI/EY = {1/r_gap:.1f})")
print(f"{'mode':>6s}  {'w0':>8s}  {'wa':>8s}")
for mode in ['bare', 'full', 'yang']:
    w0, wa = compute_w0(r_gap, mode)
    print(f"{mode:>6s}  {w0:8.4f}  {wa:8.4f}")

# --- 2. calibrated r0 (to real DESI w0), all modes ---
print(f"\nCalibrated to w0 = {W0_CENTRAL}:")
for mode in ['bare', 'full', 'yang']:
    r0c = calibrate(W0_CENTRAL, mode)
    w0, wa = compute_w0(r0c, mode)
    print(f"  {mode:>6s}: r0 = {r0c:.5f} (EI/EY = {1/r0c:.1f})  "
          f"w0 = {w0:.4f}  wa = {wa:+.4f}")

# --- 2b. w0 landscape vs r0 (yang mode) ---
print(f"\nw0 landscape (yang mode):")
print(f"{'r0':>8s}  {'EI/EY':>6s}  {'w0':>8s}  {'wa':>8s}")
for r0 in [0.001, 0.002, 0.005, 0.01, 0.02, 0.03, 0.04721, 0.08]:
    w0, wa = compute_w0(r0, 'yang')
    print(f"{r0:8.5f}  {1/r0:6.1f}  {w0:8.4f}  {wa:8.4f}")

# --- 3. sigma vs DESI wa anchors ---
print(f"\nTension with DESI wa (structural gap r0 = {r_gap:.4f}):")
for mode in ['bare', 'full', 'yang']:
    _, wa = compute_w0(r_gap, mode)
    for name, (mu, sig) in [("Table 9", WA_T9),
                            ("SNe range low", (WA_RANGE[0], 0.28)),
                            ("SNe range high", (WA_RANGE[1], 0.35))]:
        nsigma = (wa - mu) / sig
        print(f"  {mode:>6s}: wa = {wa:+.3f} vs DESI {name} wa = {mu:+.2f} "
              f"+- {sig:.2f}: {abs(nsigma):.1f} sigma")

# --- 4. w0 sensitivity of the calibrated shift ---
print(f"\nCalibration-target sensitivity (yang mode):")
for target in [W0_LO, W0_CENTRAL, W0_HI]:
    r0c = calibrate(target, 'yang')
    _, wa = compute_w0(r0c, 'yang')
    print(f"  w0 target {target:+.3f}: r0 = {r0c:.5f}, wa = {wa:+.4f}")

# --- 5. lambda-independence check (yang mode) ---
print(f"\nLambda-independence check (yang mode, gap r0):")
for lam in [0.02, 0.05, 0.1]:
    LAM = lam
    H_EMPTY = (LAM / 3) * PHI_INV**2
    w0, wa = compute_w0(r_gap, 'yang')
    print(f"  lambda = {lam}: w0 = {w0:.4f}, wa = {wa:+.4f}")
LAM = 0.02
H_EMPTY = (LAM / 3) * PHI_INV**2

# --- 6. phantom-crossing check ---
print(f"\nPhantom-crossing check (yang mode):")
r0c = calibrate(W0_CENTRAL, 'yang')
sol = solve_ivp(system, [np.log(A0), np.log(8.0)], [r0c],
                args=('yang',), method="BDF", max_step=0.01,
                atol=1e-9, rtol=1e-8)
a = np.exp(sol.t)
r = sol.y[0]
H = np.array([H_eff(rr, 'yang') for rr in r])
dlnH = np.gradient(np.log(H + 1e-30))
dlna = np.gradient(np.log(a + 1e-30))
w = -1.0 - (2.0 / 3.0) * dlnH / dlna
print(f"  min w over a in [0.3, 1]: {w[(a>=0.3)&(a<=1)].min():+.4f} "
      f"({'stays above -1 (no phantom)' if w[(a>=0.3)&(a<=1)].min() > -1 else 'crosses -1'})")
