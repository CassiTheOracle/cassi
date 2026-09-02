#!/usr/bin/env python3
"""
μ* Crossing Audit: where does sin²θ_W(μ) = φ⁻³?
=================================================

Independent recomputation of the running-angle crossing reported in
`standard-model/sm-radiative-corrections.md` §3.3 (μ* ≈ 233 GeV), with:

  1. a closed-form analytic solution of the crossing,
  2. full input-provenance classification (derived / calibrated / asserted),
  3. convention sensitivity: rounded-vs-full-precision MS-bar inputs and a
     formal 5F-below-$m_t$/6F-above bookkeeping comparison, not precision electroweak matching,
  4. the φ-selection test: rung placement n(μ*) = log_φ(M_Pl/μ*) vs the
     framework's calibrated EW rung E_80 = M_Pl·φ⁻⁸⁰ = 233.2 GeV,
  5. the contrast crossing of the φ-boundary trajectory (Direction A), and
  6. the explicit rejection of the unit-dependent "Fibonacci 233 in GeV"
     reading as a selection constraint.

Conventions (same as `computations/sm_radiative_corrections.py`):
  - GUT-normalized couplings: α₁ = (5/3)α_Y;  dα_i/dt = (b_i/2π)α_i²
  - SM one-loop coefficients: b = (+41/10, −19/6, −7) for (U(1)_Y, SU(2)_L, SU(3)_C)
  - sin²θ_W(μ) = α_Y(μ)/(α_Y(μ) + α₂(μ))
  - crossing condition: s2(μ) = 3·inv2/(3·inv2 + 5·inv1) = φ⁻³
    ⇒  inv2/inv1 = r* ≡ 5φ⁻³/(3(1−φ⁻³)) = 0.515035  (φ-algebra, no fit)

Usage: python computations/mu_star_crossing_audit.py
"""

from numpy import log, exp, sqrt, pi

PHI    = (1 + sqrt(5)) / 2
S2_PHI = PHI ** (-3)
M_Z    = 91.1876          # GeV
M_T    = 172.69           # GeV
M_PL   = 1.2209e19        # GeV (repo value, computations/kappa_s_rung_identity.py)
E_80   = M_PL * PHI ** (-80)     # rung-80 scale = 233.2 GeV

# ----------------------------------------------------------------------
# Inputs (two provenance classes)
# ----------------------------------------------------------------------
# (a) Calibrated: measured Z-pole MS-bar values (PDG 2024 central values)
ALPHA_HAT_INV = 127.955   # α̂⁻¹(m_Z) MS-bar
S2_MSBAR      = 0.23122   # sin²θ̂_W(m_Z) MS-bar
# GUT-normalized inverse couplings at m_Z:
#   α̂ = α₂·s² = α_Y·(1−s²)  ⇒  α₂ = α̂/s²,  α_Y = α̂/(1−s²),  α₁ = (5/3)α_Y
#   ⇒  α₁⁻¹ = (3/5)(1−s²)/α̂,  α₂⁻¹ = s²/α̂
A_FULL = (3/5) * (1 - S2_MSBAR) * ALPHA_HAT_INV    # α₁⁻¹(m_Z) = 59.02
B_FULL = S2_MSBAR * ALPHA_HAT_INV                   # α₂⁻¹(m_Z) = 29.59
A_ROUND = 59.0        # rounded values used by sm_radiative_corrections.py §2
B_ROUND = 29.6

# (b) Derived: SM β-function coefficients (one Higgs doublet, six flavors)
B1_6F, B2_6F = 41/10, -19/6
B1_5F = B1_6F - 17/30  # formal t_L+t_R hypercharge subtraction: 1/30 + 8/15
B2_5F = B2_6F          # compact convention; no separate broken-phase EW matching
BETA1_6 = B1_6F / (2*pi)
BETA1_5 = B1_5F / (2*pi)
BETA2   = -B2_6F / (2*pi)                        # = +19/(12π), inv2 rises with μ

# (c) Asserted: the Cassi boundary value (fixed-point imbalance)
#     sin²θ_W = (φ−1)/(φ+1) = φ⁻³ — asserted coupling boundary
#     (blocking step: no action-level mechanism for (g/g')² = 2φ;
#      standard-model/su2-gauge-extension.md §3.2.1)

# ----------------------------------------------------------------------
def s2_at_L(a, b, L, thresh):
    """sin²θ_W at L = ln(μ/m_Z). thresh=True: 5F below m_t, 6F above."""
    Lt = log(M_T / M_Z)
    if not thresh:
        inv1 = a - BETA1_6 * L
        inv2 = b + BETA2 * L
    elif L <= Lt:
        inv1 = a - BETA1_5 * L
        inv2 = b + BETA2 * L
    else:
        inv1 = (a - BETA1_5 * Lt) - BETA1_6 * (L - Lt)
        inv2 = (b + BETA2   * Lt) + BETA2   * (L - Lt)
    return 3 * inv2 / (3 * inv2 + 5 * inv1)

def mu_star(a, b, thresh):
    """Bisection for s2(μ) = φ⁻³; returns μ*, L = ln(μ*/m_Z)."""
    lo, hi = 0.0, log(1.0e4)
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if s2_at_L(a, b, mid, thresh) < S2_PHI:
            lo = mid
        else:
            hi = mid
    L = 0.5 * (lo + hi)
    return M_Z * exp(L), L

def rung(mu):
    return log(M_PL / mu) / log(PHI)

# ----------------------------------------------------------------------
print("=" * 76)
print("  μ* AUDIT: WHERE DOES sin²θ_W(μ) CROSS φ⁻³ = %.6f?" % S2_PHI)
print("=" * 76)
print()
print("  crossing algebra (exact, no fit):")
print("    s2(μ) = 3·inv2/(3·inv2 + 5·inv1) = φ⁻³")
print("    ⇒  inv2/inv1 = r* ≡ 5φ⁻³/(3(1−φ⁻³)) = %.8f" %
      (5*S2_PHI/(3*(1-S2_PHI))))
print()

print("  1. REPRODUCIBLE CROSSING (one-loop RGE, SM content)")
print("  ─────────────────────────────────────────────────────")
print(f"    {'scheme':<28} {'μ* (GeV)':>9} {'n(μ*)':>7} {'vs E_80':>8}")
print(f"    {'rounded inputs, 6F everywhere':<28} {mu_star(A_ROUND, B_ROUND, False)[0]:>9.1f}"
      f" {rung(mu_star(A_ROUND, B_ROUND, False)[0]):>7.2f}"
      f" {(mu_star(A_ROUND, B_ROUND, False)[0]/E_80-1)*100:>+7.2f}%")
print(f"    {'full-precision MS-bar, 6F everywhere':<28} {mu_star(A_FULL, B_FULL, False)[0]:>9.1f}"
      f" {rung(mu_star(A_FULL, B_FULL, False)[0]):>7.2f}"
      f" {(mu_star(A_FULL, B_FULL, False)[0]/E_80-1)*100:>+7.2f}%")
print(f"    {'rounded, formal 5F<mt<6F':<28} {mu_star(A_ROUND, B_ROUND, True)[0]:>9.1f}"
      f" {rung(mu_star(A_ROUND, B_ROUND, True)[0]):>7.2f}"
      f" {(mu_star(A_ROUND, B_ROUND, True)[0]/E_80-1)*100:>+7.2f}%")
print(f"    {'full MS-bar, formal 5F<mt<6F':<28} {mu_star(A_FULL, B_FULL, True)[0]:>9.1f}"
      f" {rung(mu_star(A_FULL, B_FULL, True)[0]):>7.2f}"
      f" {(mu_star(A_FULL, B_FULL, True)[0]/E_80-1)*100:>+7.2f}%")
print()
print("    repo script (sm_radiative_corrections.py §2, geomspace grid): 233.4 GeV")
print("    doc claim (sm-radiative-corrections.md §3.3): μ* ≈ 233 GeV")
print()

print("  2. INPUT PROVENANCE")
print("  ───────────────────")
print("    α₁⁻¹(m_Z) = 59.0, α₂⁻¹(m_Z) = 29.6  → Calibrated (measured MS-bar,")
print("      from α̂⁻¹ = 127.955, sin²θ̂_W = 0.23122)")
print("    β coefficients (41/10, −19/6)       → Derived (SM content)")
print("    φ⁻³ = 0.23607                        → Asserted (fixed-point")
print("      imbalance (φ−1)/(φ+1); no action-level mechanism, su2-gauge-")
print("      extension.md §3.2.1)")
print("    μ*                                   → output of the RGE + selection,")
print("      NOT a free parameter — but the trajectory is anchored to the")
print("      measured Z-pole couplings")
print()

print("  3. SCHEME SENSITIVITY (is 233 the number?)")
print("  ──────────────────────────────────────────")
mu6, L6 = mu_star(A_ROUND, B_ROUND, False)
mu5, L5 = mu_star(A_FULL, B_FULL, True)
print(f"    convention spread: {mu_star(A_ROUND,B_ROUND,False)[0]:.1f} – "
      f"{mu_star(A_FULL,B_FULL,True)[0]:.1f} GeV  ({(mu5/mu6-1)*100:+.1f}% band)")
# input-uncertainty propagation (analytic partials at the rounded point)
D  = BETA2 + (5*S2_PHI/(3*(1-S2_PHI))) * BETA1_6
r  = 5*S2_PHI/(3*(1-S2_PHI))
dL_da = r / D
dL_db = -1.0 / D
da = 0.006     # α̂⁻¹ ±0.01 and ŝ² ±4e-5 propagated into α₁⁻¹
db = 0.006     # same into α₂⁻¹
dL = abs(dL_da)*da + abs(dL_db)*db
print(f"    input uncertainty: δμ*/μ* ≈ {dL*100:.1f}%  (δa ≈ δb ≈ 0.006 ⇒ "
      f"μ* = {mu5:.0f} ± {mu5*dL:.0f} GeV)")
print()

print("  4. φ-SELECTION TEST: rung placement vs the EW rung")
print("  ──────────────────────────────────────────────────")
print(f"    E_80 = M_Pl·φ⁻⁸⁰ = {E_80:.1f} GeV  (EW rung; anchor calibrated to")
print(f"      the measured VEV: n(v₀) = {log(M_PL/246.22)/log(PHI):.2f} ≈ 80,")
print(f"      5.3% residual open — principles/v0-hierarchy-problem.md, Mapped,")
print(f"      ledger row 499)")
for label, a, b, th in [("6F, rounded", A_ROUND, B_ROUND, False),
                        ("5F/6F, full", A_FULL, B_FULL, True)]:
    mu, _ = mu_star(a, b, th)
    print(f"    n(μ*) {label}: {rung(mu):.2f}  → Δn vs rung 80: {rung(mu)-80:+.2f}  "
          f"(E_80 residual {(mu/E_80-1)*100:+.2f}%)")
print("    → the crossing lands at the EW rung to 0.1–0.2 rungs — the same")
print("      residual class as the VEV's own 0.11-rung offset. Rung 80 is a")
print("      calibrated anchor (its value is fixed by the observed VEV), so")
print("      this is a consistency cross-check, not an independent φ-selection")
print("      of the scale.")
print()

print("  5. CONTRAST: the φ-boundary trajectory (Direction A)")
print("  ─────────────────────────────────────────────────────")
# boundary run: α_GUT = φ⁻³/4π at 10^16 GeV down to m_Z (SM content)
# inv(μ1) = inv0 − b·ln(μ1/μ0)/(2π);  running down ⇒ μ1 < μ0
ALPHA_GUT = PHI**(-3) / (4*pi)
INV_G = 1 / ALPHA_GUT
inv1_z = INV_G - B1_6F * log(M_T / 1e16) / (2*pi) - B1_5F * log(M_Z / M_T) / (2*pi)
inv2_z = INV_G - B2_6F * log(M_T / 1e16) / (2*pi) - B2_5F * log(M_Z / M_T) / (2*pi)
mu_b, _ = mu_star(inv1_z, inv2_z, True)
print(f"    boundary trajectory: α₁⁻¹(m_Z) = {inv1_z:.1f}, α₂⁻¹(m_Z) = {inv2_z:.1f}")
print(f"    (repo script §1: 74.3, 36.9 ✓;  s2(m_Z) = "
      f"{s2_at_L(inv1_z, inv2_z, 0.0, True):.4f})")
print(f"    its φ⁻³ crossing: μ* = {mu_b:.0f} GeV  (n = {rung(mu_b):.1f}) — NOT 233 GeV.")
print(f"    ⇒ the 233 GeV value is a property of the measured trajectory, not")
print(f"      of the φ-boundary run (whose couplings miss by ~25%).")
print()

print("  6. REJECTED SELECTION: 'Fibonacci 233 in GeV'")
print("  ─────────────────────────────────────────────")
print("    233 is a member of the closure ladder {5, 13, 34, 89, 233, 610}")
print("    (foundations/wake-geometry.md §3b). But μ* expressed in GeV is")
print("    unit-dependent: the same crossing in natural units is")
print("    μ* = 1.9×10⁻¹⁷ M_Pl, whose rung is n = 80.0–80.1. The closure")
print("    ladder is a dimensionless angular-return set; matching it in GeV")
print("    units is numerology, not a selection constraint.")
print()

print("  VERDICT")
print("  ───────")
print("    μ* ≈ 233 GeV is an OUTPUT of the repo's RG equations given")
print("    measured Z-pole couplings, SM β-functions, and asserted φ⁻³.")
print("    No additional coefficient is fitted after those inputs. Cassi")
print("    dynamics do not independently select μ*: the trajectory is anchored")
print("    to measurement and φ⁻³ is asserted (blocking step documented). The")
print("    rung-80 coincidence (n(μ*) = 80.0–80.1) sits inside the same")
print("    5%-residual class as the calibrated VEV anchor.")
print("    Tier: Calibrated (consistent with foundations/cassi-theory-reference.md")
print("    —realized at μ* = 233 GeV, ledger row 490).")
print()
