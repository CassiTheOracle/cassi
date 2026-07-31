#!/usr/bin/env python3
"""
Quark Yukawa RGE + CKM Mixing: GUT → EW
=========================================

Computes the quark mass ratios from the bare φ-power Yukawa matrices at GUT,
running the SM RGE from GUT (step 8) to EW (step 80), accounting for CKM
mixing in the mass eigenbasis.

The central question: can CKM off-diagonal mixing + SM RGE running explain
the large deviations of quark mass ratios from bare φ-powers?

Observed deviations (from three-generations.md):
  Up:    m_c/m_u ~ 580 vs φ⁷ ~ 17  (×34),  m_t/m_c ~ 136 vs φ⁸ ~ 28  (×5)
  Down:  m_s/m_d ~ 20  vs φ⁵ ~ 11  (×2),   m_b/m_s ~ 44  vs φ⁵ ~ 11  (×4)
  Lepton: m_μ/m_e ~ 207 vs φ¹¹ ~ 199 (×1.04), m_τ/m_μ ~ 17 vs φ⁶ ~ 18 (×0.94) ✓

Usage: python computations/quark_yukawa_rge.py
"""

import numpy as np
from numpy import sqrt, log, pi, exp

PHI     = (1 + sqrt(5)) / 2
PHI_INV = 1 / PHI
LN_PHI  = log(PHI)

# ============================================================================
# §0  CONSTANTS & OBSERVED MASSES
# ============================================================================

M_PL  = 1.220890e19
N_GUT = 8
N_EW  = 80
N_SPAN = N_EW - N_GUT

def E(n): return M_PL * PHI**(-n)
E_GUT = E(N_GUT)
V0 = 246.0  # Higgs VEV (GeV)

# Observed quark masses at M_Z scale (MS-bar, GeV)
# Source: PDG 2024
m_u_obs = 0.00216   # up
m_c_obs = 1.27      # charm
m_t_obs = 172.5     # top (pole → MS-bar ~163)
m_d_obs = 0.00467   # down
m_s_obs = 0.093     # strange
m_b_obs = 4.18      # bottom (MS-bar)

# Convert to Yukawa couplings: y = sqrt(2)·m/v
def m_to_y(m): return sqrt(2) * m / V0

y_obs = {
    'u': m_to_y(m_u_obs), 'c': m_to_y(m_c_obs), 't': m_to_y(m_t_obs),
    'd': m_to_y(m_d_obs), 's': m_to_y(m_s_obs), 'b': m_to_y(m_b_obs)
}

print("=" * 72)
print("  QUARK YUKAWA RGE + CKM MIXING: GUT → EW")
print("=" * 72)
print()
print(f"  GUT: step {N_GUT}, E = {E_GUT:.2e} GeV")
print(f"  EW:  step {N_EW}")
print(f"  v₀ = {V0:.0f} GeV")
print()

# ============================================================================
# §1  BARE φ-POWER YUKAWA MATRICES AT GUT
# ============================================================================

print("── §1  BARE YUKAWA MATRICES AT GUT ──")
print()

# Fibonacci offsets from three-generations.md
# Up-type:  Δ₁=7, Δ₂=8 → hierarchy: y_u : y_c : y_t = φ^(-15) : φ^(-8) : φ^0
# Down-type: Δ₁=5, Δ₂=5 → hierarchy: y_d : y_s : y_b = φ^(-10) : φ^(-5) : φ^0
#
# The top Yukawa at GUT: y_t ≈ 1 (the largest coupling)
# The bottom Yukawa at GUT: y_b ≈ φ^(-3) × y_t (from mb/mt ratio ≈ φ^(-3))
#
# But three-generations.md says: y_t ≈ 1 at GUT, y_b ~ 0.01 at GUT
# y_b = 0.01 corresponds to φ^(-10)... let me use the observed ratio:
# m_b/m_t ≈ 4.18/172.5 ≈ 0.0242 ≈ φ^(-7.6)
#
# Actually, the bare φ-power offsets determine the mass RATIOS at GUT,
# and the absolute scale is set by the top Yukawa ~ 1.

# Bare φ-power exponents (relative to gen 3):
# Up: gen3=0, gen2=-8, gen1=-15
# Down: gen3=0, gen2=-5, gen1=-10

# Absolute normalization: y_t(GUT) = φ^0 = 1
# y_b(GUT) = y_t(GUT) * φ^(-n_b) where n_b accounts for the t-b splitting
# From the SU(2) doublet structure, y_b/y_t at GUT depends on tan β
# In Cassi: y_b(GUT) / y_t(GUT) ≈ φ^(-3) (from the mass ratio structure)
# But let me use the observed ratio as a guide and adjust

# Actually, the cleanest approach: the diagonal Yukawa entries at GUT are
# determined by the φ-power offsets AND the overall scale. We know y_t ≈ 1
# at GUT from the fixed-point structure. The other entries follow.

# Off-diagonal entries from Fibonacci mixing:
# The CKM structure suggests |V_us| ≈ φ^(-3), |V_cb| ≈ φ^(-6)
# These map to off-diagonal Yukawa entries:
# Y_ij ~ sqrt(y_i * y_j) * |V_ij|
# or more precisely: Y_ij ~ y_3 * φ^(-k_ij) where k_ij depends on the
# Fibonacci mixing between generations i and j.

# For the up sector at GUT: calibrate y_t(GUT) so that y_t(EW) ≈ 1 (m_t ≈ 173 GeV)
# The top Yukawa has a quasi-IR fixed point: it runs to ~1 at EW regardless of GUT value
# We normalize: y_t(GUT) = y0_up, where y0_up is chosen to give y_t(EW) ≈ 1
y0_up = 0.55  # calibrated (see RGE output)
y33_up = y0_up                                       # top
y22_up = y0_up * PHI**(-8)                            # charm
y11_up = y0_up * PHI**(-15)                           # up
# Off-diagonal entries scale as: y_ij ≈ y_3 · θ_ij where θ_ij is the CKM mixing angle
# y_23 ≈ y_t · |V_cb| × 0.55 ≈ 0.023 → φ^(-7)
# y_12 ≈ y_c · |V_us| ≈ φ^(-8)×0.55×0.225 ≈ 3.6×10^(-4) → φ^(-15)
# y_13 ≈ y_t · |V_ub| × 0.55 ≈ 0.0022 → φ^(-11)
y23_up = y0_up * PHI**(-7)                             # charm↔top (~|V_cb|·y_t)
y32_up = y23_up
y12_up = y0_up * PHI**(-15)                            # up↔charm (~|V_us|·y_c)
y21_up = y12_up
y13_up = y0_up * PHI**(-11)                            # up↔top (~|V_ub|·y_t)
y31_up = y13_up

Y_up_GUT = np.array([
    [y11_up, y12_up, y13_up],
    [y21_up, y22_up, y23_up],
    [y31_up, y32_up, y33_up]
])

# For the down sector at GUT:
# y_b at GUT is smaller than y_t. From the hierarchy:
# m_b/m_t(obs) ≈ 0.024 = φ^(-7.6). At GUT, the ratio could be different.
# The bare φ-power gives y_b(GUT) / y_t(GUT) ≈ φ^(-3) from the
# electroweak structure (y_b couples to the same Higgs as y_t, but the
# down-type Yukawa is suppressed by the Fibonacci offset).
#
# Actually in three-generations: y_b ~ 0.01 at GUT, which is φ^(-10).
# Let me use the clean φ-power: y_b(GUT) = φ^(-3) ≈ 0.236
# But that conflicts with three-generations. Let me use the structure:
# The down sector is suppressed by φ^(-3) relative to up at each generation
# because of the SU(2) doublet structure (different Higgs coupling).

# The key: the ratio y_b(GUT)/y_t(GUT) sets the absolute scale.
# Observed m_b/m_t ≈ 0.024. At GUT, the ratio depends on running.
# For simplicity, let me use: y_b(GUT) = φ^(-3) * y_t(GUT) ≈ 0.236
# This comes from the electroweak φ-power structure.

yb_GUT_scale = y0_up * PHI**(-3)  # bottom Yukawa at GUT relative to top
y33_dn = yb_GUT_scale                                 # bottom
y22_dn = yb_GUT_scale * PHI**(-5)                      # strange
y11_dn = yb_GUT_scale * PHI**(-10)                     # down

y23_dn = yb_GUT_scale * PHI**(-3)                      # strange↔bottom
y32_dn = y23_dn
y12_dn = yb_GUT_scale * PHI**(-5)                      # down↔strange
y21_dn = y12_dn
y13_dn = yb_GUT_scale * PHI**(-7)                      # down↔bottom
y31_dn = y13_dn

Y_dn_GUT = np.array([
    [y11_dn, y12_dn, y13_dn],
    [y21_dn, y22_dn, y23_dn],
    [y31_dn, y32_dn, y33_dn]
])

print(f"  Up-type Yukawa matrix at GUT:")
for i, row in enumerate(Y_up_GUT):
    print(f"    [{row[0]:.6f}  {row[1]:.6f}  {row[2]:.6f}]")
print(f"  Diagonal hierarchy: y_u:y_c:y_t = 1 : φ⁷ : φ¹⁵ = 1 : {PHI**7:.0f} : {PHI**15:.0f}")
print()

print(f"  Down-type Yukawa matrix at GUT (×{yb_GUT_scale:.4f} = φ⁻³):")
for i, row in enumerate(Y_dn_GUT):
    print(f"    [{row[0]:.6f}  {row[1]:.6f}  {row[2]:.6f}]")
print()

# ============================================================================
# §2  DIAGONALIZATION AT GUT (BARE MASS EIGENVALUES)
# ============================================================================

print("── §2  MASS EIGENVALUES AT GUT (NO RGE, NO MIXING) ──")
print()

# Without off-diagonals (pure φ-power, no mixing):
eig_up_bare = np.sort(np.abs(np.linalg.eigvals(Y_up_GUT)))[::-1]
eig_dn_bare = np.sort(np.abs(np.linalg.eigvals(Y_dn_GUT)))[::-1]

# With off-diagonals (mixing included):
Y_up_GUT_herm = (Y_up_GUT + Y_up_GUT.T) / 2  # symmetrize
Y_dn_GUT_herm = (Y_dn_GUT + Y_dn_GUT.T) / 2
eig_up_mix = np.sort(np.abs(np.linalg.eigvalsh(Y_up_GUT_herm)))[::-1]
eig_dn_mix = np.sort(np.abs(np.linalg.eigvalsh(Y_dn_GUT_herm)))[::-1]

# Diagonal-only eigenvalues for comparison
eig_up_diag = np.sort(np.abs(np.diag(Y_up_GUT)))[::-1]
eig_dn_diag = np.sort(np.abs(np.diag(Y_dn_GUT)))[::-1]

print(f"  Up-type eigenvalues at GUT:")
print(f"    Diagonal-only: {eig_up_diag[0]:.4f}, {eig_up_diag[1]:.6f}, {eig_up_diag[2]:.6f}")
print(f"    With mixing:   {eig_up_mix[0]:.4f}, {eig_up_mix[1]:.6f}, {eig_up_mix[2]:.6f}")
ratio_up_mix_32 = eig_up_mix[1] / eig_up_mix[2] if eig_up_mix[2] > 0 else 0
ratio_up_mix_21 = eig_up_mix[0] / eig_up_mix[1] if eig_up_mix[1] > 0 else 0
print(f"    Ratios: m_c/m_u(mix) = {ratio_up_mix_21:.0f}, m_t/m_c(mix) = {ratio_up_mix_32:.0f}")
print(f"    Bare φ⁷: {PHI**7:.0f}, φ⁸: {PHI**8:.0f}")
print()

print(f"  Down-type eigenvalues at GUT:")
print(f"    Diagonal-only: {eig_dn_diag[0]:.4f}, {eig_dn_diag[1]:.6f}, {eig_dn_diag[2]:.6f}")
print(f"    With mixing:   {eig_dn_mix[0]:.4f}, {eig_dn_mix[1]:.6f}, {eig_dn_mix[2]:.6f}")
ratio_dn_mix_32 = eig_dn_mix[1] / eig_dn_mix[2] if eig_dn_mix[2] > 0 else 0
ratio_dn_mix_21 = eig_dn_mix[0] / eig_dn_mix[1] if eig_dn_mix[1] > 0 else 0
print(f"    Ratios: m_s/m_d(mix) = {ratio_dn_mix_21:.0f}, m_b/m_s(mix) = {ratio_dn_mix_32:.0f}")
print(f"    Bare φ⁵: {PHI**5:.0f}, φ⁵: {PHI**5:.0f}")
print()

# Key finding: does mixing alone explain the large enhancements?
enhancement_up_21 = ratio_up_mix_21 / PHI**7
enhancement_up_32 = ratio_up_mix_32 / PHI**8

print(f"  Mixing enhancement factors at GUT:")
print(f"    m_c/m_u: ×{enhancement_up_21:.1f}  (need ×34 to reach observed)")
print(f"    m_t/m_c: ×{enhancement_up_32:.1f}  (need ×5)")
print()

# ============================================================================
# §3  SM RGE RUNNING (1-LOOP)
# ============================================================================

print("── §3  SM RGE RUNNING GUT→EW ──")
print()

# 1-loop RGE for Yukawa couplings in the SM:
# d ln y_i / dt = (1/16π²) [ (3/2)(y_i²) + 3·Tr(Y_u†Y_u) + 3·Tr(Y_d†Y_d) + Tr(Y_e†Y_e)
#                           - (8/3)g₃² - (9/4)g₂² - (17/20)g₁² ]
# where t = ln μ
#
# For up-type: additional term from (3/2)(y_u² - y_d²) for diagonal
# For down-type: additional term from (3/2)(y_d² - y_u²) for diagonal
#
# Dominant terms at high scales:
#  - y_t² drives all up-type couplings UP
#  - g₃² drives all couplings DOWN  
#  - The balance determines net running

# SM couplings at GUT
alpha_GUT = PHI**(-3) / (4*pi)
g3_GUT = sqrt(4*pi * alpha_GUT)  # g₃ at GUT
g2_GUT = g3_GUT                    # unified at GUT
g1_GUT = g3_GUT * sqrt(5/3)        # GUT normalization

# RGE integration from GUT to EW
# Use discrete φ-steps for consistency with the cascade framework
# At each step: y(n+1) = y(n) * exp(β_y · ln φ)

def beta_ln_y(Y_up, Y_dn, g3, g2, g1):
    """β = d ln y / d ln μ for a Yukawa matrix entry (dominant terms)."""
    # Trace of Y†Y = sum of squared Yukawas
    tr_up = np.sum(Y_up**2)
    tr_dn = np.sum(Y_dn**2)
    # Lepton trace: y_τ ≈ φ^(-13) at GUT, negligible for β
    tr_lep = 0.0
    
    Y2 = 3*tr_up + 3*tr_dn + tr_lep
    
    # Common factor
    prefactor = 1/(16*pi**2)
    
    def beta_entry(y, is_up, y_other):
        """β for a single Yukawa entry."""
        # Universal terms
        beta = 3*Y2 - (8/3)*g3**2 - (9/4)*g2**2 - (17/20)*g1**2
        # Self-coupling: (3/2)(y² - y_other²) for up-type
        if is_up:
            beta += (3/2)*(y**2)
        else:
            beta += (3/2)*(y**2)
        return prefactor * beta
    
    return beta_entry

# SM gauge β-function coefficients
b3 = 7
b2 = 19/6
b1 = -41/10

# Run RGE step by step
Y_up = Y_up_GUT.copy()
Y_dn = Y_dn_GUT.copy()
for n in range(N_SPAN):
    # Use SM gauge coupling running from M_Z upward for correct values
    # (the cascade α_GUT deficit is a separate problem; here we focus on Yukawa mixing)
    frac = (n + 0.5) / N_SPAN  # interpolate between GUT and EW
    g3_sq = 4*pi * (alpha_GUT + frac * (0.1181 - alpha_GUT))
    g2_sq = 4*pi * (alpha_GUT + frac * (0.0338 - alpha_GUT))
    g1_sq = 4*pi * (alpha_GUT + frac * (0.0169 - alpha_GUT)) * (5/3)
    g3 = sqrt(max(g3_sq, 0.001))
    g2 = sqrt(max(g2_sq, 0.001))
    g1 = sqrt(max(g1_sq, 0.001))
    
    # Common trace
    tr_up = np.sum(Y_up**2)
    tr_dn = np.sum(Y_dn**2)
    Y2 = 3*tr_up + 3*tr_dn
    pref = LN_PHI / (16*pi**2)
    
    # Update each Yukawa entry
    for i in range(3):
        for j in range(3):
            y_up = Y_up[i,j]
            y_dn = Y_dn[i,j]
            if y_up > 0:
                beta_u = 3*Y2 + (3/2)*y_up**2 - (8/3)*g3**2 - (9/4)*g2**2 - (17/20)*g1**2
                Y_up[i,j] *= exp(pref * beta_u)
            if y_dn > 0:
                beta_d = 3*Y2 + (3/2)*y_dn**2 - (8/3)*g3**2 - (9/4)*g2**2 - (17/20)*g1**2
                Y_dn[i,j] *= exp(pref * beta_d)

print(f"  After {N_SPAN} φ-steps (GUT→EW):")
print(f"    g₃(EW) = {g3:.3f}  (α₃ = {g3**2/(4*pi):.4f})")
print(f"    g₂(EW) = {g2:.3f}")
print(f"    g₁(EW) = {g1:.3f}")
print()

# ============================================================================
# §4  MASS EIGENVALUES AT EW
# ============================================================================

print("── §4  MASS EIGENVALUES AT EW ──")
print()

# Diagonalize at EW
Y_up_EW_herm = (Y_up + Y_up.T) / 2
Y_dn_EW_herm = (Y_dn + Y_dn.T) / 2

eig_up_EW = np.sort(np.abs(np.linalg.eigvalsh(Y_up_EW_herm)))[::-1]
eig_dn_EW = np.sort(np.abs(np.linalg.eigvalsh(Y_dn_EW_herm)))[::-1]

# Convert to masses
m_up_EW = eig_up_EW * V0 / sqrt(2)
m_dn_EW = eig_dn_EW * V0 / sqrt(2)

print(f"  Up-type masses at EW (GeV):")
print(f"    m_u = {m_up_EW[2]*1e3:.2f} MeV  (obs: {m_u_obs*1e3:.2f} MeV)")
print(f"    m_c = {m_up_EW[1]:.3f} GeV      (obs: {m_c_obs:.3f} GeV)")
print(f"    m_t = {m_up_EW[0]:.1f} GeV      (obs: {m_t_obs:.1f} GeV)")
print(f"    m_c/m_u = {m_up_EW[1]/m_up_EW[2]:.0f}       (obs: {m_c_obs/m_u_obs:.0f})")
print(f"    m_t/m_c = {m_up_EW[0]/m_up_EW[1]:.0f}       (obs: {m_t_obs/m_c_obs:.0f})")
print()

print(f"  Down-type masses at EW (GeV):")
print(f"    m_d = {m_dn_EW[2]*1e3:.2f} MeV  (obs: {m_d_obs*1e3:.2f} MeV)")
print(f"    m_s = {m_dn_EW[1]*1e3:.1f} MeV   (obs: {m_s_obs*1e3:.1f} MeV)")
print(f"    m_b = {m_dn_EW[0]:.3f} GeV      (obs: {m_b_obs:.3f} GeV)")
print(f"    m_s/m_d = {m_dn_EW[1]/m_dn_EW[2]:.0f}        (obs: {m_s_obs/m_d_obs:.0f})")
print(f"    m_b/m_s = {m_dn_EW[0]/m_dn_EW[1]:.0f}        (obs: {m_b_obs/m_s_obs:.0f})")
print()

# ============================================================================
# §5  RGE RUNNING FACTORS
# ============================================================================

print("── §5  RGE RUNNING FACTORS ──")
print()

# How much did each eigenvalue change from GUT to EW?
eig_up_GUT_mix = np.sort(np.abs(np.linalg.eigvalsh((Y_up_GUT + Y_up_GUT.T)/2)))[::-1]
eig_dn_GUT_mix = np.sort(np.abs(np.linalg.eigvalsh((Y_dn_GUT + Y_dn_GUT.T)/2)))[::-1]

print(f"  Running factors (EW/GUT):")
for i, label in enumerate(['t', 'c', 'u']):
    r = eig_up_EW[i] / eig_up_GUT_mix[i]
    print(f"    y_{label}: GUT={eig_up_GUT_mix[i]:.6f} → EW={eig_up_EW[i]:.6f},  ×{r:.1f}")
for i, label in enumerate(['b', 's', 'd']):
    r = eig_dn_EW[i] / eig_dn_GUT_mix[i]
    print(f"    y_{label}: GUT={eig_dn_GUT_mix[i]:.6f} → EW={eig_dn_EW[i]:.6f},  ×{r:.2f}")
print()

# ============================================================================
# §6  CKM MATRIX FROM YUKAWA MISALIGNMENT
# ============================================================================

print("── §6  CKM MATRIX ──")
print()

# The CKM matrix is V_CKM = U_u† · U_d
# where U_u diagonalizes Y_up and U_d diagonalizes Y_dn
_, U_u = np.linalg.eigh(Y_up_EW_herm)
_, U_d = np.linalg.eigh(Y_dn_EW_herm)

# CKM = U_u† · U_d
V_ckm = np.abs(U_u.T.conj() @ U_d)

print(f"  |V_CKM| from Yukawa misalignment:")
print(f"    [{V_ckm[0,0]:.4f}  {V_ckm[0,1]:.4f}  {V_ckm[0,2]:.4f}]")
print(f"    [{V_ckm[1,0]:.4f}  {V_ckm[1,1]:.4f}  {V_ckm[1,2]:.4f}]")
print(f"    [{V_ckm[2,0]:.4f}  {V_ckm[2,1]:.4f}  {V_ckm[2,2]:.4f}]")
print(f"  Observed: |V_us|≈0.225, |V_cb|≈0.041, |V_ub|≈0.004")
print()

# ============================================================================
# §7  ANALYSIS: WHAT DRIVES THE DEVIATIONS?
# ============================================================================

print("── §7  ANALYSIS ──")
print()

# Separate the effects of mixing vs RGE running
print(f"  Decomposition of m_c/m_u enhancement:")
ratio_up_diag = (PHI**(-8)) / (PHI**(-15))  # bare φ-power
ratio_up_mix_gut = eig_up_GUT_mix[1] / eig_up_GUT_mix[2]
ratio_up_ew = eig_up_EW[1] / eig_up_EW[2]
obs_up = m_c_obs / m_u_obs

print(f"    Bare φ-power (no mixing):     {ratio_up_diag:.0f}")
print(f"    With mixing at GUT:            {ratio_up_mix_gut:.0f}")
print(f"    With mixing + RGE at EW:       {ratio_up_ew:.0f}")
print(f"    Observed:                      {obs_up:.0f}")
print(f"    Mixing enhancement at GUT:     ×{ratio_up_mix_gut/ratio_up_diag:.1f}")
print(f"    RGE enhancement:               ×{ratio_up_ew/ratio_up_mix_gut:.1f}")
print(f"    Total gap to observed:         ×{obs_up/ratio_up_ew:.1f}")
print()

# For down-type
print(f"  Decomposition of m_s/m_d enhancement:")
ratio_dn_diag = PHI**5
ratio_dn_mix_gut = eig_dn_GUT_mix[1] / eig_dn_GUT_mix[2]
ratio_dn_ew = eig_dn_EW[1] / eig_dn_EW[2]
obs_dn = m_s_obs / m_d_obs

print(f"    Bare φ-power (no mixing):     {ratio_dn_diag:.0f}")
print(f"    With mixing at GUT:            {ratio_dn_mix_gut:.0f}")
print(f"    With mixing + RGE at EW:       {ratio_dn_ew:.0f}")
print(f"    Observed:                      {obs_dn:.0f}")
print(f"    Mixing enhancement at GUT:     ×{ratio_dn_mix_gut/ratio_dn_diag:.1f}")
print(f"    RGE enhancement:               ×{ratio_dn_ew/ratio_dn_mix_gut:.1f}")
print(f"    Total gap to observed:         ×{obs_dn/ratio_dn_ew:.1f}")
print()

# ============================================================================
# §8  SUMMARY
# ============================================================================

print("=" * 72)
print("  SUMMARY: QUARK MASS RATIOS")
print("=" * 72)
print()
print(f"  CKM off-diagonal mixing at GUT accounts for:")
print(f"    m_c/m_u: ×{ratio_up_mix_gut/ratio_up_diag:.1f} enhancement over bare φ⁷")
print(f"    m_s/m_d: ×{ratio_dn_mix_gut/ratio_dn_diag:.1f} enhancement over bare φ⁵")
print(f"  SM RGE running (GUT→EW) accounts for:")
print(f"    Additional ×{ratio_up_ew/ratio_up_mix_gut:.1f} (up sector)")
print(f"    Additional ×{ratio_dn_ew/ratio_dn_mix_gut:.1f} (down sector)")
print(f"  Remaining gap to observed:")
print(f"    m_c/m_u: ×{obs_up/ratio_up_ew:.1f}")
print(f"    m_s/m_d: ×{obs_dn/ratio_dn_ew:.1f}")
print()
print(f"  CKM matrix from Yukawa misalignment:")
print(f"    |V_us| = {V_ckm[0,1]:.3f}  (obs: 0.225)")
print(f"    |V_cb| = {V_ckm[1,2]:.3f}  (obs: 0.041)")
print(f"    |V_ub| = {V_ckm[0,2]:.4f}  (obs: 0.004)")
print()
print("=" * 72)
print("  Pipeline complete.")
print("=" * 72)
