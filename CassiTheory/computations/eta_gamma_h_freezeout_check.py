#!/usr/bin/env python3
"""
Dynamical Freeze-Out (Γ/H = 1) Check for the 44-Rung Dilution Span
==================================================================

Tests the standard dynamical condition Γ = H within the document's separate
unit-density normalized gate ansatz for the 44-rung dilution span
(`foundations/baryon-asymmetry.md` §4.7 and
`computations/eta_span_closure_check.py`).  This is a conditional diagnostic;
it does not promote the ansatz to the canonical density-dependent gate.

Inputs and conventions:

    normalized gate  Γ = λ(1−q̄),      (1−q̄) = (φ⁻²+ε̄²)/(1+φ⁻²+ε̄²),
                                      ε̄ = (φ−r)/(1+r)
                                      (conditional unit-density ansatz;
                                      baryon-asymmetry.md §4.2)
    Hubble rate      H = (λ/3)[φ⁻² + (φ−r)(1+r)/r]             (homogeneous
                                      two-fluid H)
    λ = 0.1 (solver convention); λ cancels out of Γ = H exactly
    w = 5 (conditional Wu Xing reference); 1/(2w) = λ is a Hypothesized linkage
    r_GUT ≈ 0.3–0.5                   (baryon-asymmetry.md §1.2, loose estimate)
    N_GUT = 13.33                      (declared GUT-seed rung, M_GUT = 2×10¹⁶ GeV)

Candidate equation (Γ = H, λ cancels):

    (φ⁻²+ε̄²)/(1+φ⁻²+ε̄²) = (1/3)[φ⁻² + (φ−r)(1+r)/r],
    ε̄ = (φ−r)/(1+r)

Result: the equation has a unique root r_f ≈ 1.34949 (quartic over ℚ(√5);
no φ-power: log_φ(r_f) = 0.6229), but Γ/H is monotonically increasing along
the trajectory. The crossing is a THAW (Γ/H rising through 1), not a freeze
(Γ/H falling through 1). Reading it as a dilution endpoint gives a
homogeneous rung span N = 2.5–3.2 from r_GUT ≈ 0.3–0.5, versus the required
44.09–44.13.

The radiation-era cross-check makes the additional dimensional identification
λ_phys = λ_solver M_Pl and compares λ_phys(1−q̄) with
H_rad(n) = 1.66√g* · E(n)²/M_Pl. For the two tested solver values,
λ_solver = 0.1 and 1.0, its crossing sits at n ≈ 3.3–6.7, before the
GUT seed at n = 13.33. This is a conditional normalization check, not a
normalization-independent physical prediction.

Verdict: no closure within this ansatz. The 44-rung span remains the ledgered
fit (`parameter-inventory.md` §10 row 481). The calculation does not test the
canonical q(E_Y,E_I,ε_raw) at arbitrary density and therefore cannot establish
a general two-fluid freeze-out result.

Usage: python computations/eta_gamma_h_freezeout_check.py
"""

import math

PHI    = (1 + math.sqrt(5)) / 2
LN_PHI = math.log(PHI)
M_PL   = 1.2209e19     # GeV — Planck mass (mass-ladder convention)
ETA_DOC  = 6.0e-10     # doc convention
ETA_PDG  = 6.104e-10   # PDG 2024 baryon-to-photon ratio
N_GUT  = 13.33         # declared GUT-seed rung (M_GUT = 2×10¹⁶ GeV)
R0     = PHI**-5 / (2 - PHI**-5)   # 0.047214…, selected conditional Wu Xing reference
C_RAD  = 1.66 * math.sqrt(106.75)  # 1.66√g* for H_rad, g* = SM d.o.f.

def lg(x):
    return math.log(x) / LN_PHI

def one_minus_qbar(r):
    """Normalized gate openness (1−q̄) at ratio r (document §4.2)."""
    eps_bar = (PHI - r) / (1 + r)
    return (PHI**-2 + eps_bar**2) / (1 + PHI**-2 + eps_bar**2)

def h_over_lambda(r):
    """H/λ = (1/3)[φ⁻² + (φ−r)(1+r)/r] — homogeneous two-fluid H."""
    return (1.0 / 3.0) * (PHI**-2 + (PHI - r) * (1 + r) / r)

def gamma_over_h(r):
    """Γ/H = (1−q̄) / (H/λ) inside the normalized ansatz."""
    return one_minus_qbar(r) / h_over_lambda(r)

def f_cross(r):
    """Γ = H iff (1−q̄)(r) − H(r)/λ = 0."""
    return one_minus_qbar(r) - h_over_lambda(r)

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

    |dr/dt|/λ = (1−q̄)(φ−r)(1+r)  (homogeneous ratio ODE using the
    unit-density normalized gate).
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
    """Conditional crossing: λ_solver(1−q̄) = C_RAD·φ^(−2n)."""
    return 0.5 * lg(C_RAD / (lam_frac * omq))

print("=" * 76)
print("  DYNAMICAL FREEZE-OUT (Γ/H = 1) CHECK — 44-RUNG DILUTION SPAN")
print("  (baryon-asymmetry.md §4.7; rate-based conditional diagnostic)")
print("=" * 76)

print()
print("─ ANCHORS (selected gap and solver convention) ─")
print("  λ = 0.1 (solver convention)   — cancels out of Γ = H")
print("  w = 5 (conditional Wu Xing reference); 1/(2w) = λ is a Hypothesized linkage")
print(f"  r_0 = φ⁻⁵/(2−φ⁻⁵) = {R0:.6f} (selected conditional Wu Xing reference)")
print(f"  r_GUT ≈ 0.3–0.5 (doc §1.2, loose)   N_GUT = {N_GUT}")
print(f"  required log_φ(1/η): {lg(1/ETA_PDG):.4f} (PDG) / {lg(1/ETA_DOC):.4f} (doc)")

print()
print("─ CONDITIONAL CANDIDATE EQUATION (Γ = H, λ cancels exactly) ─")
print("  (φ⁻²+ε̄²)/(1+φ⁻²+ε̄²) = (1/3)[φ⁻² + (φ−r)(1+r)/r],   ε̄ = (φ−r)/(1+r)")

rf = r_of_gamma_equals_h(1.0, 1.5)
eps_f = (PHI - rf) / (1 + rf)
print()
print(f"  Unique root: r_f = {rf:.12f}")
print(f"    ε_f = {eps_f:.12f}")
print(f"    (1−q̄)(r_f) = {one_minus_qbar(rf):.12f} = H/λ(r_f)  (Γ/H = 1 ✓)")
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
print(f"  {'r0→φ−10⁻⁴':>8} {n_total:>11.3f} {'—':>11} {'—':>10}")
for rs in (0.3, 0.4, 0.5):
    Ns = n_rungs(rs, rf)
    eta = PHI**-Ns
    print(f"  {rs:>8.1f} {Ns:>11.3f} {eta:>11.2e} {eta/ETA_DOC:>10.1e}×")
print(f"  required span: 44.09–44.13  (η_obs = 6.0–6.1×10⁻¹⁰)")
print("  → 15–18× short; η would be ~5×10⁸× too large (homogeneous map,")
print("    consistent with the known N_total ≈ 9 homogeneous-depth deficit).")

print()
print("─ CONDITIONAL RADIATION-ERA CHECK ─")
print("  Identification: λ_phys = λ_solver·M_Pl")
print("  Compare λ_phys(1−q̄) with H_rad = 1.66√g*·E²/M_Pl")
print(f"  H_rad coefficient 1.66√g* (g*=106.75) = {C_RAD:.2f}")
print(f"  {'λ_solver':>18} {'(1−q̄)=0.72':>12} {'(1−q̄)=0.276':>12} {'vs N_GUT':>9}")
for lam in (0.1, 1.0):
    nlo, nhi = n_freeze_rad(lam, 0.72), n_freeze_rad(lam, 0.276)
    print(f"  {lam:>18.1f} {nlo:>12.2f} {nhi:>12.2f} {N_GUT:>9.2f}")
print(f"  Γ/H at seed n={N_GUT} ((1−q̄)=0.4, λ_solver=0.1): {0.1*0.4*PHI**(2*N_GUT)/C_RAD:.2e}")
print(f"  Γ/H at proposed endpoint n=57.33:                  {0.1*0.4*PHI**(2*57.33)/C_RAD:.2e}")
print("  → both tested normalizations cross before the GUT seed.")

print()
print("─ VERDICT ─")
print("  The Γ/H = 1 condition does not close the exponent within the")
print("  declared unit-density normalized gate ansatz. Its homogeneous")
print("  crossing at r_f = 1.3495 is a thaw, and the conditional")
print("  radiation-era crossings for λ_solver = 0.1 and 1.0 are pre-seed.")
print("  The 44-rung span remains the ledgered fit")
print("  (parameter-inventory.md §10 row 481). This calculation does not")
print("  test canonical q at arbitrary density; that requires evolved")
print("  E_Y, E_I, and ε_raw plus a derived ratio-to-step map.")
print("=" * 76)
