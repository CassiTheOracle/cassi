#!/usr/bin/env python3
"""
Dynamical Freeze-Out (Γ/H = 1) Check for the 44-Rung Dilution Span
==================================================================

Sixth closure attempt for the baryon-asymmetry exponent η ≈ φ⁻⁴⁴
(`foundations/baryon-asymmetry.md` §4.7; the first five are §4.5(a)–(e),
`computations/eta_span_closure_check.py`). This one is rate-based: the
standard dynamical freeze-out condition Γ = H, using only framework-derived
rates.

Framework inputs (all derived, no free parameters):

    conversion rate   Γ = λ(1−q),      (1−q) = (φ⁻²+ε²)/(1+φ⁻²+ε²),
                                      ε = (φ−r)/(1+r)           (two-fluid PDE,
                                      cosmology-from-phi.md §1; baryon-
                                      asymmetry.md §4.2)
    Hubble rate       H = (λ/3)[φ⁻² + (φ−r)(1+r)/r]             (homogeneous
                                      two-fluid H, same source)
    λ = 1/(2w) = 0.1 (derived, w = 5)  — cancels out of Γ = H exactly
    r_0 = φ⁻⁵/(2−φ⁻⁵) ≈ 0.0472        (Wu Xing gap, derived)
    r_GUT ≈ 0.3–0.5                   (baryon-asymmetry.md §1.2, loose estimate)
    N_GUT = 13.33                      (corrected GUT-seed rung, M_GUT = 2×10¹⁶ GeV)

Candidate equation (Γ = H, λ cancels):

    (φ⁻²+ε²)/(1+φ⁻²+ε²) = (1/3)[φ⁻² + (φ−r)(1+r)/r],   ε = (φ−r)/(1+r)

Result: the equation has a unique root r_f ≈ 1.34949 (quartic over ℚ(√5);
no φ-power: log_φ(r_f) = 0.6229), but Γ/H is monotonically increasing along
the trajectory — the crossing is a THAW (Γ/H rising through 1), not a freeze
(Γ/H falling through 1). Γ/H < 1 throughout the seeded epoch (0.29–0.39 at
r_GUT ≈ 0.3–0.5) and > 1 from r_f to the attractor: no Γ = H freeze-out
exists for the dilution of the seeded asymmetry. Reading the crossing as the
dilution endpoint anyway, the homogeneous rung span from the seed is
N = 2.5–3.2 (η ≈ 0.2–0.3, ~4–5×10⁸× observed) vs the required 44.09–44.13.

Radiation-era cross-check (Γ = λ(1−q) vs H_rad(n) = 1.66√g* · E(n)²/M_Pl,
E(n) = M_Pl φ⁻ⁿ, g* = 106.75, λ normalized via c = λ·ℓ_Pl):
the Γ = H crossing sits at n ≈ 3.3–6.7 — BEFORE the GUT seed (13.33);
Γ/H at the seed ≈ 9×10² and at the would-be 44-span endpoint (n = 57.33)
≈ 2×10²¹. No normalization of λ moves the crossing past the seed.

Verdict: no closure. The 44-rung span remains the ledgered fit
(`parameter-inventory.md` §10 row 481). Blocking step: the framework's own
two-fluid rates produce no Γ = H freeze after the seed (the crossing is a
thaw, homogeneous reading; pre-seed, radiation-era reading), and no derived
map assigns a rung to the homogeneous crossing.

Usage: python computations/eta_gamma_h_freezeout_check.py
"""

import math

PHI    = (1 + math.sqrt(5)) / 2
LN_PHI = math.log(PHI)
M_PL   = 1.2209e19     # GeV — Planck mass (mass-ladder convention)
ETA_DOC  = 6.0e-10     # doc convention
ETA_PDG  = 6.104e-10   # PDG 2024 baryon-to-photon ratio
N_GUT  = 13.33         # corrected GUT-seed rung (M_GUT = 2×10¹⁶ GeV)
R0     = PHI**-5 / (2 - PHI**-5)   # 0.047214…, Wu Xing gap derived
C_RAD  = 1.66 * math.sqrt(106.75)  # 1.66√g* for H_rad, g* = SM d.o.f.

def lg(x):
    return math.log(x) / LN_PHI

def one_minus_q(r):
    """Qi gate openness (1−q) at ratio r (baryon-asymmetry.md §4.2)."""
    eps = (PHI - r) / (1 + r)
    return (PHI**-2 + eps**2) / (1 + PHI**-2 + eps**2)

def h_over_lambda(r):
    """H/λ = (1/3)[φ⁻² + (φ−r)(1+r)/r] — homogeneous two-fluid H."""
    return (1.0 / 3.0) * (PHI**-2 + (PHI - r) * (1 + r) / r)

def gamma_over_h(r):
    """Γ/H = (1−q) / (H/λ) — λ cancels."""
    return one_minus_q(r) / h_over_lambda(r)

def f_cross(r):
    """Γ = H  <=>  (1−q)(r) − H(r)/λ = 0."""
    return one_minus_q(r) - h_over_lambda(r)

def r_of_gamma_equals_h(a, b):
    """Bisect f_cross on [a, b] (f monotone there)."""
    lo, hi = a, b
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f_cross(mid) > 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)

def n_rungs(r_lo, r_hi, n_pts=4000):
    """Homogeneous rung count N = ∫ H/(|dr/dt|·lnφ) dr, λ cancels.

    |dr/dt|/λ = (1−q)(φ−r)(1+r)  (homogeneous ratio ODE with the (1+r)
    quotient factor, cascade_depth_integral.py convention).
    """
    h = (r_hi - r_lo) / n_pts
    s = 0.0
    for i in range(n_pts + 1):
        r = r_lo + h * i
        e = (PHI - r) / (1 + r)
        oq = (PHI**-2 + e * e) / (1 + PHI**-2 + e * e)
        H = (1.0 / 3.0) * (PHI**-2 + (PHI - r) * (1 + r) / r)
        dr = oq * (PHI - r) * (1 + r)
        s += H / (dr * LN_PHI)
    # trapezoid correction at the endpoints
    for r in (r_lo, r_hi):
        e = (PHI - r) / (1 + r)
        oq = (PHI**-2 + e * e) / (1 + PHI**-2 + e * e)
        H = (1.0 / 3.0) * (PHI**-2 + (PHI - r) * (1 + r) / r)
        dr = oq * (PHI - r) * (1 + r)
        s -= 0.5 * H / (dr * LN_PHI)
    return s * h

def n_freeze_rad(lam_frac, omq):
    """Radiation-era crossing: λ(1−q) = C_RAD·M_Pl·φ^(−2n)."""
    return 0.5 * lg(C_RAD / (lam_frac * omq))

print("=" * 76)
print("  DYNAMICAL FREEZE-OUT (Γ/H = 1) CHECK — 44-RUNG DILUTION SPAN")
print("  (baryon-asymmetry.md §4.7; sixth closure attempt, rate-based)")
print("=" * 76)

print()
print("─ ANCHORS (all framework-derived) ─")
print(f"  λ = 1/(2w) = 0.1 (w=5 derived)   — cancels out of Γ = H")
print(f"  r_0 = φ⁻⁵/(2−φ⁻⁵) = {R0:.6f}")
print(f"  r_GUT ≈ 0.3–0.5 (doc §1.2, loose)   N_GUT = {N_GUT}")
print(f"  required log_φ(1/η): {lg(1/ETA_PDG):.4f} (PDG) / {lg(1/ETA_DOC):.4f} (doc)")

print()
print("─ CANDIDATE EQUATION (Γ = H, λ cancels exactly) ─")
print("  (φ⁻²+ε²)/(1+φ⁻²+ε²) = (1/3)[φ⁻² + (φ−r)(1+r)/r],   ε = (φ−r)/(1+r)")

rf = r_of_gamma_equals_h(1.0, 1.5)
eps_f = (PHI - rf) / (1 + rf)
print()
print(f"  Unique root: r_f = {rf:.12f}")
print(f"    ε_f = {eps_f:.12f}")
print(f"    (1−q)(r_f) = {one_minus_q(rf):.12f} = H/λ(r_f)  (Γ/H = 1 ✓)")
print(f"    log_φ(r_f) = {lg(rf):.6f}   — NOT a φ-power")
print(f"    r_f = {rf/PHI**-1:.3f}× the pinch ratio φ⁻¹ = 0.618;  r_f > 1 (Yang-majority)")
print(f"    quartic over ℚ(√5) with irrational coefficients — no φ-algebra identity")

print()
print("─ Γ/H ALONG THE TRAJECTORY (direction of the crossing) ─")
print(f"  {'r':>12} {'Γ/H':>10}")
for r in (R0, 0.240, 0.3, 0.4, 0.5, PHI**-1, 1.0, rf, 1.5, PHI - 1e-4):
    print(f"  {r:>12.6f} {gamma_over_h(r):>10.6f}")
print("  Γ/H rises monotonically 0.062 → 2.17: the crossing at r_f is a THAW")
print("  (Γ/H rising through 1), not a freeze (Γ/H falling through 1).")
print(f"  At the seed (r_GUT ≈ 0.3–0.5): Γ/H = {gamma_over_h(0.3):.3f}–{gamma_over_h(0.5):.3f} < 1")
print("  → no Γ = H freeze-out exists for the dilution of the seeded asymmetry.")

print()
print("─ HOMOGENEOUS RUNG SPAN seed → r_f (reading the crossing as the endpoint) ─")
print(f"  {'seed r':>8} {'N (rungs)':>11} {'η = φ^−N':>11} {'η/η_obs':>10}")
n_total = n_rungs(R0, PHI - 1e-4)
print(f"  {'r0→φ':>8} {n_total:>11.3f} {'—':>11}")
for rs in (0.3, 0.4, 0.5):
    Ns = n_rungs(rs, rf)
    eta = PHI**-Ns
    print(f"  {rs:>8.1f} {Ns:>11.3f} {eta:>11.2e} {eta/ETA_DOC:>10.1e}×")
print(f"  required span: 44.09–44.13  (η_obs = 6.0–6.1×10⁻¹⁰)")
print("  → 15–18× short; η would be ~5×10⁸× too large (homogeneous map,")
print("    consistent with the known N_total ≈ 9 homogeneous-depth deficit).")

print()
print("─ RADIATION-ERA CROSS-CHECK (Γ = λ(1−q) vs H_rad = 1.66√g*·E²/M_Pl) ─")
print(f"  H_rad coefficient 1.66√g* (g*=106.75) = {C_RAD:.2f}")
print(f"  {'λ normalization':>18} {'(1−q)=0.72':>12} {'(1−q)=0.276':>12} {'vs N_GUT':>9}")
for lam in (0.1, 1.0):
    nlo, nhi = n_freeze_rad(lam, 0.72), n_freeze_rad(lam, 0.276)
    print(f"  {f'{lam}·M_Pl (c=λℓ_Pl)':>18} {nlo:>12.2f} {nhi:>12.2f} {N_GUT:>9.2f}")
print(f"  Γ/H at seed n={N_GUT} ((1−q)=0.4, λ=0.1·M_Pl): {0.1*0.4*PHI**(2*N_GUT)/C_RAD:.2e}")
print(f"  Γ/H at would-be endpoint n=57.33:            {0.1*0.4*PHI**(2*57.33)/C_RAD:.2e}")
print("  → crossing sits BEFORE the GUT seed for every normalization;")
print("    conversion stays super-critical through the whole post-seed epoch.")

print()
print("─ VERDICT ─")
print("  The Γ/H = 1 dynamical freeze-out does not close the exponent:")
print("  the framework's own two-fluid rates produce no Γ = H FREEZE after")
print("  the seed (the unique crossing at r_f = 1.3495 is a thaw, Γ/H")
print("  rising monotonically through 1; the radiation-era crossing is")
print("  pre-seed at n ≈ 3.3–6.7). The 44-rung span remains the ledgered")
print("  fit (parameter-inventory.md §10 row 481). Blocking step: no rate-")
print("  based freeze-out selects a dilution endpoint after the GUT seed,")
print("  and the homogeneous r→step map (N_total ≈ 9) cannot stretch any")
print("  seeded epoch to 44 rungs — the spatial wake-wave extension of the")
print("  cascade remains the unclosed requirement (baryon-asymmetry.md §6.2).")
print("=" * 76)
