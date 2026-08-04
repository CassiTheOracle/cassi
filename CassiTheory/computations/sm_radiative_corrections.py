#!/usr/bin/env python3
"""
SM Radiative Corrections: φ-Boundary → Z-Pole
==============================================

The complete one-loop (plus leading two-loop) radiative-correction program
that carries the Cassi φ-anchored GUT boundary conditions down to the Z-pole
observables, and the reverse direction (measured Z-pole values run up to
test unification claims).

Theory sources:
  - Sirlin & Ferroglia, Rev. Mod. Phys. 85, 263 (2013) [arXiv:1210.5296]
    on-shell master relations, Δα decomposition, Δr, sin²θ_W scheme values
  - Ferroglia, Ossola, Passera & Sirlin, PRD 65, 113002 (2002)
    [arXiv:hep-ph/0203224] compact formulae for M_W and sin²θ_eff^lept
    (complete one-loop + two-loop (M_t²/M_W²)ⁿ-enhanced)

Conventions:
  - GUT-normalized couplings: α₁ = (5/3)α_Y;  dα_i/dt = (b_i/2π)α_i²
  - SM one-loop coefficients (one Higgs doublet, 6 flavors):
      b = (+41/10, −19/6, −7)  for (U(1)_Y, SU(2)_L, SU(3)_C)
  - Decoupling thresholds at m_t (top), m_W/m_Z for EW running
  - sin²θ_W(μ) = α_Y(μ)/(α_Y(μ) + α₂(μ))  [MS-bar-like gauge-coupling ratio]

Usage: python computations/sm_radiative_corrections.py
"""

import numpy as np
from numpy import sqrt, log, pi

PHI     = (1 + sqrt(5)) / 2
PHI_INV = 1 / PHI

# ----------------------------------------------------------------------
# §0  Inputs (PDG 2024 central values unless noted)
# ----------------------------------------------------------------------
ALPHA_INV_0  = 137.035999       # α(0), fine-structure constant
G_F          = 1.1663788e-5     # GeV^-2, Fermi constant from μ decay
M_Z          = 91.1876          # GeV
M_T          = 172.69           # GeV
M_H          = 125.25           # GeV
M_W_EXP      = 80.360           # GeV, PDG 2024 (CDF excluded)
M_W_EXP_ERR  = 0.011
M_W_FIT      = 80.354           # GeV, PDG global-fit prediction (m_t, m_H above)
ALPHA_S_MZ   = 0.1180           # α_s(m_Z) MS-bar
S2_MSBAR     = 0.23122          # sin²θ̂_W(m_Z) MS-bar
S2_EFF_EXP   = 0.23153          # sin²θ_eff^lept (Z-pole asymmetries)
ALPHA_HAT_INV = 127.955         # α̂(m_Z) MS-bar
DALPHA_HAD   = 0.02761          # Δα_had^(5) (Hagiwara et al. 2011)
DALPHA_LEP   = 0.03150          # Δα_lept (3-loop, Steinhauser)
DALPHA_TOP   = -0.000072        # Δα_top (perturbative, negative)
M_GUT_CANON  = 1.0e16           # GeV, canonical continuous one-loop M_GUT
M_GUT_NOM    = 2.0e16           # GeV, nominal Cassi value

ALPHA_GUT    = PHI**(-3) / (4 * pi)      # φ⁻³/4π ≈ 1/53.2
S2_PHI       = PHI**(-3)                 # φ⁻³ ≈ 0.23607

def fmt(x, n=4):
    return f"{x:.{n}f}"

# ======================================================================
print("=" * 76)
print("  SM RADIATIVE CORRECTIONS: φ-BOUNDARY → Z-POLE")
print("=" * 76)
print(f"  φ = {PHI:.6f},  α_GUT = φ⁻³/4π = 1/{1/ALPHA_GUT:.1f}")
print(f"  M_GUT: canonical {M_GUT_CANON:.0e} GeV, nominal {M_GUT_NOM:.0e} GeV")
print()

# ======================================================================
# §1  One-loop gauge RGE with decoupling thresholds
# ======================================================================
print("── §1  GAUGE-COUPLING RGE (1-loop, thresholds at m_t, m_W/m_Z) ──")
print()

# dα_i/dt = (b_i/2π)α_i²  →  α_i⁻¹(μ) = α_i⁻¹(μ₀) − (b_i/2π) ln(μ/μ₀)
# b_i = (+41/10, −19/6, −7) above m_t; top decouples below m_t:
B1_6F, B2_6F, B3_6F = 41/10, -19/6, -7.0
B1_5F = B1_6F - (4/3) * 3 * (1/3)**2 * (5/3)   # remove top from b₁ (GUT norm)
B3_5F = B3_6F + 2/3                             # remove top from b₃
B2_5F = B2_6F                                   # top is SU(2) singlet

def alpha_inv_run(inv0, b, mu0, mu1):
    """α⁻¹ at mu1 from α⁻¹ at mu0, one-loop, constant b between."""
    return inv0 - b * log(mu1 / mu0) / (2 * pi)

def run_down_from_boundary(m_gut):
    """α_GUT = φ⁻³/4π at M_GUT for all three couplings → values at m_Z,
    with the top decoupling threshold at m_t (6→5 flavors) and EW
    thresholds at m_W, m_Z for the α_em reconstruction."""
    inv1_g = alpha_inv_run(1/ALPHA_GUT, B1_6F, m_gut, M_T)
    inv2_g = alpha_inv_run(1/ALPHA_GUT, B2_6F, m_gut, M_T)
    inv3_g = alpha_inv_run(1/ALPHA_GUT, B3_6F, m_gut, M_T)
    inv1 = alpha_inv_run(inv1_g, B1_5F, M_T, M_Z)
    inv2 = alpha_inv_run(inv2_g, B2_5F, M_T, M_Z)
    inv3 = alpha_inv_run(inv3_g, B3_5F, M_T, M_Z)
    a1, a2, a3 = 1/inv1, 1/inv2, 1/inv3
    aY = (3/5) * a1
    s2 = aY / (aY + a2)
    aem = a2 * s2
    return inv1, inv2, inv3, s2, aem

print("  Direction A — φ-boundary at M_GUT, run DOWN to m_Z (SM content):")
print(f"  {'M_GUT':>10} {'α₁⁻¹(m_Z)':>10} {'α₂⁻¹(m_Z)':>10} {'α₃⁻¹(m_Z)':>10}"
      f" {'sin²θ_W':>9} {'α_em⁻¹':>9}")
for mg in (M_GUT_CANON, M_GUT_NOM):
    inv1, inv2, inv3, s2, aem = run_down_from_boundary(mg)
    print(f"  {mg:>10.0e} {inv1:>10.1f} {inv2:>10.1f} {inv3:>10.1f}"
          f" {s2:>9.4f} {1/aem:>9.1f}")
inv1_c, inv2_c, inv3_c, s2_c, aem_c = run_down_from_boundary(M_GUT_CANON)
print()
print(f"  Measured at m_Z (GUT-normalized MS-bar): α₁⁻¹ = 59.0, α₂⁻¹ = 29.6,"
      f" α₃⁻¹ = 8.47, sin²θ̂_W = 0.23122, α̂⁻¹ = 127.96")
print(f"  → φ-boundary misses: α₁⁻¹ {100*(inv1_c/59.0-1):+.0f}%,"
      f" α₂⁻¹ {100*(inv2_c/29.6-1):+.0f}%,"
      f" α₃⁻¹ {100*(inv3_c/8.47-1):+.0f}%  (α_s = {1/inv3_c:.3f} vs 0.1180,"
      f" ×{ALPHA_S_MZ/(1/inv3_c):.2f} deficit)")
print()

# 2-loop QCD for α_s from the φ-boundary (b₁ coefficient, MS-bar form)
def alpha_s_2loop(a0, mu0, mu1, nf_hi, nf_lo, m_th):
    """2-loop QCD running with 6 flavors above m_th, 5 below.

    dα_s/dt = −(b₀ α² + b₁ α³/(2π)) / (2π),  b₀ = 11 − 2n_f/3,
    b₁ = 102 − 38n_f/3 (MS-bar)."""
    b0 = lambda nf: 11 - 2*nf/3
    b1 = lambda nf: 102 - 38*nf/3
    def rhs(a, nf):
        return -(b0(nf) * a**2 + b1(nf) * a**3 / (2*pi)) / (2*pi)
    mus = np.geomspace(mu0, mu1, 20000)
    a = a0
    for i in range(1, len(mus)):
        nf = nf_hi if mus[i] > m_th else nf_lo
        dt = log(mus[i]/mus[i-1])
        # RK2
        k1 = rhs(a, nf)
        k2 = rhs(a + dt*k1/2, nf)
        a += dt * k2
    return a

a3_2loop = alpha_s_2loop(ALPHA_GUT, M_GUT_CANON, M_Z, 6, 5, M_T)
print(f"  α_s(m_Z) from φ-boundary:  1-loop = {1/inv3_c:.4f},  2-loop QCD = {a3_2loop:.4f}")
print(f"  (measured 0.1180 → deficit ×{ALPHA_S_MZ/a3_2loop:.2f}; the documented"
      f" Δb = 1.70 beyond-SM requirement)")
print()

# ----------------------------------------------------------------------
# §2  Measured Z-pole values run UP: unification intersections
# ----------------------------------------------------------------------
print("── §2  MEASURED VALUES RUN UP: WHERE DO THE COUPLINGS MEET? ──")
print()

INV1_MZ = 59.0        # (5/3)·α̂⁻¹·cos²θ̂ = 59.0
INV2_MZ = 29.6
INV3_MZ = 1/ALPHA_S_MZ

def inv_at(inv_mz, b, mu):
    return alpha_inv_run(inv_mz, b, M_Z, mu)

from numpy import exp
def intersec(inv_a, b_a, inv_b, b_b):
    # α_i⁻¹(μ) = inv_i − (b_i/2π) ln(μ/m_Z);  set equal:
    # (inv_a − inv_b) = (b_a − b_b) L /2π  →  L = 2π(inv_a − inv_b)/(b_a − b_b)
    L = 2 * pi * (inv_a - inv_b) / (b_a - b_b)
    return M_Z * exp(L), L

for label, (ia, ba, ib, bb) in {
    "α₁ = α₂": (INV1_MZ, B1_6F, INV2_MZ, B2_6F),
    "α₂ = α₃": (INV2_MZ, B2_6F, INV3_MZ, B3_6F),
    "α₁ = α₃": (INV1_MZ, B1_6F, INV3_MZ, B3_6F),
}.items():
    mu, L = intersec(ia, ba, ib, bb)
    inv_c = ia - ba * L / (2 * pi)
    print(f"  {label}: μ* = {mu:.2e} GeV   (α⁻¹ = {inv_c:.1f}, α = {1/inv_c:.4f})")

# Minimal-SU(5)-style check: force α₃ through the α₁ = α₂ point
mu_12, L_12 = intersec(INV1_MZ, B1_6F, INV2_MZ, B2_6F)
inv_c12 = INV1_MZ - B1_6F * L_12 / (2 * pi)
inv3_impl = inv_c12 + B3_6F * L_12 / (2 * pi)
print(f"  SU(5)-style check: α₃ forced through α₁=α₂ at {mu_12:.1e} GeV "
      f"→ α₃⁻¹(m_Z) = {inv3_impl:.1f}")
print(f"    α_s(m_Z) = {1/inv3_impl:.4f} (1-loop) vs 0.1180 → a "
      f"{ALPHA_S_MZ/(1/inv3_impl):.1f}× deficit, same direction as the φ-boundary "
      f"(classic minimal-SU(5) estimate ≈ 0.07)")

# couplings and sin²θ_W at 10^16 and 2×10^16
for mg in (1.0e16, M_GUT_NOM):
    inv1 = inv_at(INV1_MZ, B1_6F, mg)
    inv2 = inv_at(INV2_MZ, B2_6F, mg)
    inv3 = inv_at(INV3_MZ, B3_6F, mg)
    aY = (3/5) / inv1
    a2 = 1 / inv2
    s2 = aY / (aY + a2)
    print(f"  At {mg:.0e} GeV: α₁⁻¹ = {inv1:.1f}, α₂⁻¹ = {inv2:.1f}, α₃⁻¹ = {inv3:.1f},"
          f" sin²θ_W = {s2:.4f}")

# MSSM variant (2 doublets, superpartners at 1 TeV): b = (33/5, 1, −3)
print()
print("  MSSM variant (b = (33/5, 1, −3) above 1 TeV, SM below):")
M_SUSY = 1.0e3
inv1_s = alpha_inv_run(INV1_MZ, B1_6F, M_Z, M_SUSY)
inv2_s = alpha_inv_run(INV2_MZ, B2_6F, M_Z, M_SUSY)
for mg in (1.0e16, M_GUT_NOM):
    inv1 = alpha_inv_run(inv1_s, 33/5, M_SUSY, mg)
    inv2 = alpha_inv_run(inv2_s, 1.0, M_SUSY, mg)
    aY = (3/5) / inv1
    s2 = aY / (aY + 1/inv2)
    print(f"    At {mg:.0e} GeV: sin²θ_W = {s2:.4f}")

# scale where sin²θ_W = φ⁻³ (running up from m_Z)
def s2_at(mu):
    inv1 = inv_at(INV1_MZ, B1_6F, mu)
    inv2 = inv_at(INV2_MZ, B2_6F, mu)
    aY = (3/5) / inv1
    return aY / (aY + 1/inv2), inv1, inv2

mus = np.geomspace(M_Z, 1.0e6, 2000)
mu_star = None
for mu in mus:
    s2m, _, _ = s2_at(mu)
    if s2m >= S2_PHI:
        mu_star = mu
        break
print()
print(f"  sin²θ_W(μ) crosses φ⁻³ = {S2_PHI:.5f} at μ* = {mu_star:.1f} GeV")

# Downward check: starting from sin²θ_W = φ⁻³ at 2×10^16 GeV, run down
def run_down_from_s2(s2_0, m_gut, mssm):
    """sin²θ_W(m_Z) starting from sin²θ_W = s2_0 with α₂(M_GUT) = α_GUT."""
    a2 = ALPHA_GUT
    aY = a2 * s2_0 / (1 - s2_0)
    a1 = (5/3) * aY
    mus = np.geomspace(m_gut, M_Z, 4000)
    M_SUSY = 1.0e3
    for i in range(1, len(mus)):
        mu = mus[i]
        if mssm and mu > M_SUSY:
            b1, b2 = 33/5, 1.0
        else:
            b1, b2 = B1_6F, B2_6F
        dt = log(mus[i] / mus[i-1])
        a1 += (b1 * a1**2 / (2*pi)) * dt
        a2 += (b2 * a2**2 / (2*pi)) * dt
    aY = (3/5) * a1
    return aY / (aY + a2)

s2_down_sm   = run_down_from_s2(S2_PHI, M_GUT_NOM, False)
s2_down_mssm = run_down_from_s2(S2_PHI, M_GUT_NOM, True)
print(f"  Running φ⁻³ = 0.236 DOWN from 2×10¹⁶ GeV gives sin²θ_W(m_Z) ="
      f" {s2_down_sm:.2f} (SM) / {s2_down_mssm:.2f} (MSSM) — not 0.231")
print()

# ----------------------------------------------------------------------
# §3  ᾱ(m_Z) from α(0): the running of α (vacuum polarization)
# ----------------------------------------------------------------------
print("── §3  ᾱ(m_Z) FROM α(0): Δα = Δα_lept + Δα_had + Δα_top ──")
print()
DALPHA = DALPHA_LEP + DALPHA_HAD + DALPHA_TOP
ALPHA_BAR_INV = ALPHA_INV_0 * (1 - DALPHA)
print(f"  Δα_lept = {DALPHA_LEP:.5f}   (3-loop, Steinhauser 1998)")
print(f"  Δα_had⁽⁵⁾ = {DALPHA_HAD:.5f}   (e⁺e⁻ data + PQCD, Hagiwara et al. 2011)")
print(f"  Δα_top = {DALPHA_TOP:.6f}")
print(f"  Δα = {DALPHA:.5f}  →  ᾱ⁻¹(m_Z) = {ALPHA_BAR_INV:.2f}   (measured 128.9;"
      f" MS-bar α̂⁻¹ = {ALPHA_HAT_INV:.3f})")
print()

# ----------------------------------------------------------------------
# §4  Δr and M_W: the on-shell radiative-correction master relation
# ----------------------------------------------------------------------
print("── §4  Δr AND M_W (μ-decay master relation, FOPS compact formula) ──")
print()

# Master relation (OS scheme, Sirlin 1980; modern numerator convention):
#   s²c² = (πα(0)/√2 G_F M_Z²) (1 + Δr),   s² = 1 − M_W²/M_Z²
A2_0 = pi * (1/ALPHA_INV_0) / (sqrt(2) * G_F)
print(f"  A₀² = πα(0)/(√2 G_F) = {A2_0:.1f} GeV²")
print(f"  Measured: M_W = {M_W_EXP} GeV → s²c²M_Z² = "
      f"{M_W_EXP**2*(1-M_W_EXP**2/M_Z**2):.1f} GeV² → Δr = "
      f"{M_W_EXP**2*(1-M_W_EXP**2/M_Z**2)/A2_0 - 1:.5f}")
s2_os_meas = 1 - M_W_EXP**2 / M_Z**2
s2_os_err  = 2 * M_W_EXP * M_W_EXP_ERR / M_Z**2
print(f"  → OS sin²θ_W = {s2_os_meas:.5f} ± {s2_os_err:.5f}"
      f"   (S&F 2013 quote 0.22290(29) ↔ m_W = 80.385)")

# FOPS compact formula (EFF scheme, PRD 65, 113002), Eqs. (13)-(14)
S2EFF_0 = 0.231383
C1, C2, C3, C4, C5 = 4.948e-4, 9.69e-3, 2.78e-3, 4.5e-4, 3.50e-5
MW_0    = 80.3862
D1, D2, D3, D4, D5 = 5.730e-2, 5.08e-1, 5.42e-1, 8.5e-3, 8.98e-3

def fops(m_h, m_t=174.3, dal_ha=0.02761, als=0.118):
    A1 = log(m_h / 100.0)
    A2 = dal_ha / 0.02761 - 1.0
    A3 = (m_t / 174.3)**2 - 1.0
    A4 = als / 0.118 - 1.0
    s2e = S2EFF_0 + (C1*A1 + C5*A2) / (1 + C2*A2 - C3*A3 + C4*A4)
    mw = MW_0 - D1*A1 - D5*A1**2 - D2*A2 + D3*A3 - D4*A4
    return s2e, mw

s2e, mw = fops(M_H, m_t=M_T, dal_ha=DALPHA_HAD, als=ALPHA_S_MZ)
print()
print(f"  FOPS (EFF scheme, 1-loop + leading 2-loop), modern inputs "
      f"(m_t = {M_T}, m_H = {M_H}, Δα_h = {DALPHA_HAD}, α_s = {ALPHA_S_MZ}):")
print(f"    sin²θ_eff^lept = {s2e:.5f}   (measured {S2_EFF_EXP} ± 0.00016)"
      f"   → {(s2e - S2_EFF_EXP)/0.00016:+.1f}σ")
print(f"    M_W = {mw:.3f} GeV   (measured {M_W_EXP} ± {M_W_EXP_ERR};"
      f" PDG global fit {M_W_FIT})")

# Δr from the FOPS M_W  (master relation: s²c² = (A₀²/M_Z²)(1 + Δr))
s2_os = 1 - mw**2 / M_Z**2
dr = (s2_os * (1 - s2_os) * M_Z**2) / A2_0 - 1
print(f"    → OS sin²θ_W = {s2_os:.5f},  Δr = {dr:.5f}")

# Decomposition: Δr = Δα − (c²/s²)Δρ + Δr_rem
c2s2 = (1 - S2_MSBAR) / S2_MSBAR
d_rho = 3 * G_F * M_T**2 / (8 * sqrt(2) * pi**2)
d_rho_qcd = d_rho * (1 - 2.859 * ALPHA_S_MZ / pi)   # 2-loop QCD correction
print()
print(f"  Decomposition (one-loop, MS-bar angle):")
print(f"    Δρ = 3G_F m_t²/(8√2π²) = {d_rho:.5f}   (with 2-loop QCD: {d_rho_qcd:.5f})")
print(f"    (c²/s²)Δρ = {c2s2 * d_rho:.5f}   (QCD-corrected: {c2s2 * d_rho_qcd:.5f})")
print(f"    Δr = Δα − (c²/s²)Δρ + Δr_rem  →  Δr_rem = {dr - DALPHA + c2s2*d_rho_qcd:+.5f}")
print(f"    (Δr − Δα = {dr - DALPHA:+.5f} — the >20σ evidence for electroweak"
      f" corrections beyond the running of α; 26σ in S&F 2013 §III.I)")
print()

# φ-tree m_W/m_Z with the ρ correction
MW_PHI_TREE = M_Z * sqrt(1 - S2_PHI)
MW_PHI_RHO  = MW_PHI_TREE * sqrt(1 + d_rho)
print(f"  φ-tree: m_W/m_Z = √(1−φ⁻³) = {sqrt(1-S2_PHI):.4f} → m_W = {MW_PHI_TREE:.2f} GeV")
print(f"  φ-tree + leading ρ correction: m_W = {MW_PHI_RHO:.2f} GeV"
      f"   (measured {M_W_EXP} → gap {(MW_PHI_RHO/M_W_EXP-1)*100:+.2f}%)")
print()

# ----------------------------------------------------------------------
# §5  Higgs sector: λ running and vacuum stability
# ----------------------------------------------------------------------
print("── §5  HIGGS QUARTIC: λ(m_Z) → λ(M_Pl), VACUUM STABILITY ──")
print()
V2 = 1 / (sqrt(2) * G_F)
V  = sqrt(V2)
LAM_MZ = M_H**2 / (2 * V2)
YT_MZ  = sqrt(2) * M_T / V
print(f"  v = 1/(√2 G_F)^{{1/2}} = {V:.2f} GeV,  λ(m_Z) = m_H²/(2v²) = {LAM_MZ:.4f}")

# sm-from-phi §2.3 check: λ_φ = (φ⁻²/2)(g₂²/8) with g₂(m_Z)
G2_MZ = sqrt(4 * pi / 29.6)   # α₂(m_Z) = 1/29.6
LAM_PHI = (PHI**(-2) / 2) * (G2_MZ**2 / 8)
print(f"  sm-from-phi §2.3 check: λ_φ = (φ⁻²/2)(g₂²/8) = {LAM_PHI:.5f}"
      f" → m_H = v√(2λ_φ) = {V * sqrt(2*LAM_PHI):.1f} GeV  (NOT 125 GeV —"
      f" the old formula does not reproduce m_H)")

# one-loop λ RGE: dλ/dt = (1/16π²)[24λ² + 12λy_t² − 6y_t⁴
#                − (9/2)λg₂² − (3/2)λg'² + (3/8)(2g₂⁴ + (g₂²+g'²)²)]
# d y_t/dt = (y_t/16π²)[(9/2)y_t² − 8g₃² − (9/4)g₂² − (17/12)g'²]
# g' = g₁·√(3/5), g₁ GUT-normalized.
def run_higgs(mu0, mu1, lam0, yt0, g1_0, g2_0, g3_0, n_steps=20000):
    def rhs(mu, lam, yt, g1, g2, g3):
        nf = 6 if mu > M_T else 5
        gp = g1 * sqrt(3/5)                     # SM-normalized hypercharge coupling
        dg1 = (41/10 - (0 if nf == 6 else (4/3)*3*(1/9)*(5/3))) * g1**3 / (16*pi**2)
        dg2 = (-19/6) * g2**3 / (16*pi**2)
        dg3 = (-(11 - 2*nf/3)) * g3**3 / (16*pi**2)
        dl = (24*lam**2 + 12*lam*yt**2 - 6*yt**4
              - (9/2)*lam*g2**2 - (3/2)*lam*gp**2
              + (3/8)*(2*g2**4 + (g2**2 + gp**2)**2)) / (16*pi**2)
        dyt = yt * ((9/2)*yt**2 - 8*g3**2 - (9/4)*g2**2 - (17/12)*gp**2) / (16*pi**2)
        return dl, dyt, dg1, dg2, dg3
    mus = np.geomspace(mu0, mu1, n_steps)
    lam, yt, g1, g2, g3 = lam0, yt0, g1_0, g2_0, g3_0
    for i in range(1, len(mus)):
        dt = log(mus[i] / mus[i-1])
        # RK4
        k1 = rhs(mus[i-1], lam, yt, g1, g2, g3)
        k2 = rhs(mus[i-1]*exp(dt/2), lam+dt*k1[0]/2, yt+dt*k1[1]/2,
                 g1+dt*k1[2]/2, g2+dt*k1[3]/2, g3+dt*k1[4]/2)
        k3 = rhs(mus[i-1]*exp(dt/2), lam+dt*k2[0]/2, yt+dt*k2[1]/2,
                 g1+dt*k2[2]/2, g2+dt*k2[3]/2, g3+dt*k2[4]/2)
        k4 = rhs(mus[i], lam+dt*k3[0], yt+dt*k3[1],
                 g1+dt*k3[2], g2+dt*k3[3], g3+dt*k3[4])
        lam += dt*(k1[0]+2*k2[0]+2*k3[0]+k4[0])/6
        yt  += dt*(k1[1]+2*k2[1]+2*k3[1]+k4[1])/6
        g1  += dt*(k1[2]+2*k2[2]+2*k3[2]+k4[2])/6
        g2  += dt*(k1[3]+2*k2[3]+2*k3[3]+k4[3])/6
        g3  += dt*(k1[4]+2*k2[4]+2*k3[4]+k4[4])/6
    return lam, yt

G1_MZ = sqrt(4 * pi / 59.0)        # GUT-normalized α₁ = 1/59.0
G2_MZ = sqrt(4 * pi / 29.6)
G3_MZ = sqrt(4 * pi / 8.47)
# Yukawa from the RUNNING top mass at m_Z (m_t(m_Z) ≈ 163.5 GeV):
YT_MZ_RUN = sqrt(2) * 163.5 / V
lam_pl, yt_pl = run_higgs(M_Z, 1.0e19, LAM_MZ, YT_MZ_RUN, G1_MZ, G2_MZ, G3_MZ)
lam_pl_pole, _ = run_higgs(M_Z, 1.0e19, LAM_MZ, YT_MZ, G1_MZ, G2_MZ, G3_MZ)
lam_10, _ = run_higgs(M_Z, 1.0e10, LAM_MZ, YT_MZ_RUN, G1_MZ, G2_MZ, G3_MZ)
print(f"  y_t(m_Z) from running top mass (m_t(m_Z) ~ 163.5 GeV) = {YT_MZ_RUN:.4f};"
      f"  from pole mass = {YT_MZ:.4f}")
print(f"  λ(m_Z) = {LAM_MZ:.4f} → λ(10¹⁰ GeV) = {lam_10:.4f} →"
      f" λ(M_Pl) = {lam_pl:+.4f} (running y_t) / {lam_pl_pole:+.4f} (pole y_t)")
print(f"  One loop: borderline at the stability boundary; NNLO"
      f" (Degrassi et al. 2012, arXiv:1205.6497): λ(M_Pl) = −0.011 → the SM"
      f" vacuum is METASTABLE (lifetime ≫ age of the universe)")
print()

# ----------------------------------------------------------------------
# §5.5  Higgs-mass candidates: φ-anchored formulas and honest verdicts
# ----------------------------------------------------------------------
print("── §5.5  HIGGS-MASS CANDIDATES: WHAT φ GIVES FOR m_H ──")
print()
M_H_EXP = 125.25
# (2) Wu-Xing route (parameter-inventory §3.1): λ_WX = 1/(2w) = 0.1, w = 5 derived;
#     consistency check m_H²φ/(4v₀²) ≈ λ_WX  →  m_H = √(4λ_WX/φ)·v
LAM_WX = 1 / (2 * 5)
M_H_WX = V * sqrt(4 * LAM_WX / PHI)
LAM_CHK = M_H_EXP**2 * PHI / (4 * V**2)
print(f"  (2) Wu-Xing quartic: m_H²φ/(4v₀²) = λ_WX = 1/(2w) = {LAM_WX:.4f}"
      f" (w = 5 derived)")
print(f"      λ check: {LAM_CHK:.4f} vs 0.1 → +{100*(LAM_CHK/0.1-1):.1f}%")
print(f"      → m_H = √(4λ_WX/φ)·v = {M_H_WX:.2f} GeV vs {M_H_EXP}"
      f" ({100*(M_H_WX/M_H_EXP-1):+.1f}%)   [Hypothesized: in the 2–5% band,"
      f" residual mechanism open]")
print()
# (3) stability boundary: bisect m_H so that λ(M_Pl) = 0 (1-loop, running y_t)
def lam_pl_of(mh):
    return run_higgs(M_Z, 1.0e19, mh**2/(2*V**2), YT_MZ_RUN,
                     G1_MZ, G2_MZ, G3_MZ)[0]
lo, hi = 100.0, 150.0
for _ in range(35):
    mid = (lo + hi) / 2
    if lam_pl_of(mid) > 0:
        hi = mid      # stable for this m_H → boundary lies below
    else:
        lo = mid
M_H_BOUND = (lo + hi) / 2
print(f"  (3) stability boundary: λ(M_Pl) = 0 → m_H = {M_H_BOUND:.1f} GeV (1-loop)")
print(f"      NNLO boundary: 129.4 ± 1.8 GeV at m_t = 173.1 (Degrassi et al. 2012)")
print(f"      → 129.2 at m_t = 172.69; measured {M_H_EXP} is"
      f" {100*(M_H_EXP/M_H_BOUND-1):+.1f}% above the 1-loop line and"
      f" {100*(M_H_EXP/129.2-1):+.1f}% ({abs(M_H_EXP-129.2)/1.81:.1f}σ) below"
      f" the NNLO line")
print(f"      → the measured mass lies inside the loop-order spread of the"
      f" λ(M_Pl) = 0 line (λ(M_Pl) = −0.011 NNLO → metastable)")
print()
# (4) two-fluid eigenmasses at the φ-point:
#     V = (g/4)(x+y)² + (λ/2)(x−φy)² − μ²(x+y),  x = Ψ₀², y = Ψ₁²
#     field-space Hessian at |Ψ|²_min = v²,  g = φ⁻³,  λ = λ_WX = 0.1
g_tf, lam_tf = PHI**(-3), LAM_WX
mu2_tf = g_tf * V**2 / 2
x0 = 2 * mu2_tf / (g_tf * PHI)
y0 = 2 * mu2_tf / (g_tf * PHI**2)
M11 = 3*g_tf*x0 + g_tf*y0 + 3*lam_tf*x0 - 2*lam_tf*PHI*y0 - 2*mu2_tf
M22 = g_tf*x0 + 3*g_tf*y0 - 2*lam_tf*PHI*x0 + 3*lam_tf*PHI**2*y0 - 2*mu2_tf
M12 = 2*(g_tf - 2*lam_tf*PHI) * sqrt(x0*y0)
tr2 = (M11 + M22) / 2
dd2 = sqrt(((M11 - M22) / 2)**2 + M12**2)
m_hi = sqrt(max(tr2 + dd2, 0.0))
m_lo = sqrt(max(tr2 - dd2, 0.0))
print(f"  (4) two-fluid eigenmasses (g = φ⁻³, λ = λ_WX = 0.1, |Ψ|²_min = v²):")
print(f"      m = {m_hi:.1f} / {m_lo:.1f} GeV — bracket m_H = 125.25"
      f" (geometric mean {sqrt(m_hi*m_lo):.1f}, "
      f"{100*(sqrt(m_hi*m_lo)/M_H_EXP-1):+.1f}%)   [Hypothesized structure;"
      f" normalization convention matters at the ~20% level]")
print()
# (5) fractional-rung coincidences — documented, REJECTED as fits
print("  (5) sharpest fractional-rung coincidences (no mechanism → fits,"
      " not predictions; cf. the m_e half-step 26.5 precedent):")
for lab, val in [
    ("m_H = m_t·φ^(−2/3)", M_T / PHI**(2/3)),
    ("m_H = m_Z·φ^(+2/3)", M_Z * PHI**(2/3)),
    ("m_H = v·φ^(−7/5)",   V   / PHI**(7/5)),
]:
    print(f"      {lab} = {val:.2f} GeV  ({100*(val/M_H_EXP-1):+.2f}%)")
print(f"      (m_t/m_H = φ^(2/3) at 0.03% is the sharpest known mass-ratio"
      f" coincidence; rejected absent a mechanism — 2/3-rung offsets have"
      f" no Cassi origin)")
print()
# rung placements on the M_Pl mass ladder
MPL = 1.2209e19
print("  Rung placements n = log_φ(M_Pl/m), M_Pl = 1.2209×10¹⁹ GeV:")
for lab, m in [("v₀", V), ("m_t", M_T), ("m_H", M_H_EXP), ("m_Z", M_Z),
               ("m_J/ψ", 3.0969), ("m_μ", 0.1056583755)]:
    print(f"      {lab:6s} n = {log(MPL/m)/log(PHI):7.2f}")
print()

# ----------------------------------------------------------------------
# §6  Summary
# ----------------------------------------------------------------------
print("=" * 76)
print("  SUMMARY: φ-BOUNDARY VS MEASURED, WITH FULL SM RADIATIVE CORRECTIONS")
print("=" * 76)
print()
print("  Direction A — φ-boundary (α_GUT = φ⁻³/4π at M_GUT = 10¹⁶ GeV) run down:")
print(f"    α₁⁻¹(m_Z) = {inv1_c:.1f}  vs 59.0   ({100*(inv1_c/59.0-1):+.0f}%)")
print(f"    α₂⁻¹(m_Z) = {inv2_c:.1f}  vs 29.6   ({100*(inv2_c/29.6-1):+.0f}%)")
print(f"    α₃⁻¹(m_Z) = {inv3_c:.1f}  vs 8.47   ({100*(inv3_c/8.47-1):+.0f}%)"
      f"  → α_s = {1/inv3_c:.3f} vs 0.1180 (×{ALPHA_S_MZ/(1/inv3_c):.1f} deficit,"
      f" Δb = 1.70)")
print(f"    sin²θ_W(m_Z) = {s2_c:.4f}  vs 0.23122   "
      f"({100*(s2_c/0.23122-1):+.1f}%)")
print(f"    α_em⁻¹(m_Z) = {1/aem_c:.0f}  vs 128.9   ({100*((1/aem_c)/128.9-1):+.0f}%)")
print()
print("  Direction B — measured Z-pole values run up:")
print(f"    α₁ = α₂ at ~10¹³ GeV (α⁻¹ ~ 42); α₂ = α₃ at ~10¹⁷ GeV;"
      f" no exact unification in the SM")
print(f"    sin²θ_W(2×10¹⁶) = {s2_at(M_GUT_NOM)[0]:.3f}  (φ⁻³ = 0.2361 is NOT"
      f" the GUT-scale value)")
print(f"    sin²θ_W(μ) = φ⁻³ at μ* = {mu_star:.0f} GeV")
print()
print("  Standard-Model closure (independent of φ):")
print(f"    ᾱ⁻¹(m_Z) = {ALPHA_BAR_INV:.2f} from α(0) + Δα = {DALPHA:.5f}   ✓")
print(f"    M_W = {mw:.3f} GeV (FOPS) / {M_W_FIT} (PDG fit) vs {M_W_EXP} ± {M_W_EXP_ERR}   ✓")
print(f"    sin²θ_eff^lept = {s2e:.5f} vs {S2_EFF_EXP} ± 0.00016   ✓")
print(f"    Δr = {dr:.4f}; Δr − Δα = {dr-DALPHA:+.4f} (26σ EW signal)")
print(f"    λ(M_Pl) = {lam_pl:+.4f} (1-loop; NNLO −0.011) → metastable vacuum (SM)")
print()
print("  Cassi φ-anchored tree predictions after radiative corrections:")
print(f"    m_W/m_Z = √(1−φ⁻³) = {sqrt(1-S2_PHI):.4f} → +ρ-correction: "
      f"{MW_PHI_RHO/M_Z:.4f}  vs measured {M_W_EXP/M_Z:.4f}  "
      f"({100*(MW_PHI_RHO/M_Z - M_W_EXP/M_Z)/(M_W_EXP/M_Z):+.2f}%)")
print(f"    sin²θ_W = φ⁻³ = {S2_PHI:.5f} vs 0.23122 at m_Z: +{100*(S2_PHI/0.23122-1):.1f}%"
      f" (realized at μ* ~ {mu_star:.0f} GeV, not at the GUT scale)")
print()
print("=" * 76)
