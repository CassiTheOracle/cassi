#!/usr/bin/env python3
"""
Proton Coherence-Budget Arithmetic Closure
============================================

Recomputes the two boxed proton-lifetime claims of the framework with their
own stated inputs, and closes the ledgered discrepancy (parameter-inventory.md
§10, Q9/P10 row): the boxed GUT formula, fed with its own inputs, gives
1.3×10³⁷ yr — 323× the boxed 4×10³⁴ yr.

Claim A — GUT gauge-mediated decay, `standard-model/gut-embedding.md` §3.1:
  τ(p → e⁺π⁰) ≈ (1/α_GUT²) · (M_GUT⁴ / m_p⁵)        [boxed]
  with α_GUT = 1/53, M_GUT = 2×10¹⁶ GeV, m_p = 0.938 GeV
  boxed result printed: ≈ 4×10³⁴ yr ("within Hyper-K reach")

Claim B — coherence budget, `foundations/proton-coherence-budget.md` §3:
  N_max = Π_{i=0}^{n} 1/(1−q_i) = φ^{δ(n+1) + n(n+1)/2},  q_i = 1 − φ^{−i−δ}
  with δ = 3, n = 91.46: boxed N_max ≈ φ⁴⁵⁰⁶ ≈ 10⁹⁴² cycles → τ_p ≈ 10⁹¹⁰ yr

Tier ledger (what each link rests on):
  - GUT formula: standard SU(5) dimensional estimate (formula: Derived, as
    standard physics); inputs α_GUT = φ⁻³/4π and M_GUT = 2×10¹⁶ GeV carry the
    ledgered Δb = 1.70 beyond-SM content — Mapped (parameter-inventory.md §10).
  - Coherence budget: product structure is combinatorial (Derived, given the
    dephasing model); per-rung profile q_i = 1 − φ^{−i−δ} is Hypothesized
    (no derivation — doc §8); rung n = 91.46 = log_φ(λ_p/ℓ_Pl) is Mapped.

Usage: python computations/proton_budget_closure.py
"""

import math

PHI     = (1 + math.sqrt(5)) / 2
LN_PHI  = math.log(PHI)
LOG10_PHI = math.log10(PHI)

HBAR_GEV_S = 6.582119569e-25   # ħ in GeV·s  (1 GeV⁻¹ ↔ seconds)
YEAR_S     = 365.25 * 86400    # seconds per Julian year
M_PL       = 1.616255e-35      # Planck length [m]
HBARC_GEV_M = 1.973269804e-16  # ħc in GeV·m

# ---- Claim A inputs (exactly as printed in the box) -----------------------
ALPHA_GUT_STATED = 1.0 / 53.0
ALPHA_GUT_PHI    = PHI**(-3) / (4 * math.pi)   # φ⁻³/4π ≈ 1/53.2 (doc §3 value)
M_GUT            = 2.0e16      # GeV
M_P              = 0.938       # GeV
TAU_BOXED_YR     = 4.0e34      # printed boxed value [yr]

# ---- Claim B inputs (exactly as printed) ----------------------------------
N_PROTON   = 91.46            # rung: log_φ(λ_p/ℓ_Pl)
DELTA      = 3.0              # σ = ℓ_Pl/φ³ regularization offset
N_BOXED    = 4506.0           # printed exponent ≈ φ⁴⁵⁰⁶

# ===========================================================================
print("=" * 76)
print("  PROTON COHERENCE-BUDGET ARITHMETIC CLOSURE")
print("  (parameter-inventory.md §10 Q9/P10 ledger row; 2026-08-03 sweep)")
print("=" * 76)

# ---------------------------------------------------------------------------
print()
print("─ CLAIM A — GUT gauge-mediated τ(p→e⁺π⁰)  (gut-embedding.md §3.1) ─")
print()
print(f"  boxed formula:  τ ≈ (1/α_GUT²) · M_GUT⁴ / m_p⁵")
print(f"  stated inputs:  α_GUT = 1/53,  M_GUT = {M_GUT:.0e} GeV,  m_p = {M_P} GeV")
print()

term1 = 1.0 / ALPHA_GUT_STATED**2
m4    = M_GUT**4
m5    = M_P**5
tau_gev_inv = term1 * m4 / m5
tau_s  = tau_gev_inv * HBAR_GEV_S
tau_yr = tau_s / YEAR_S

print(f"  term-by-term evaluation of the boxed formula:")
print(f"    1/α_GUT²        = 53²                = {term1:.4g}")
print(f"    M_GUT⁴          = (2×10¹⁶)⁴ GeV⁴     = {m4:.3e} GeV⁴")
print(f"    m_p⁵            = 0.938⁵ GeV⁵        = {m5:.4f} GeV⁵")
print(f"    M_GUT⁴/m_p⁵     = {m4:.3e}/{m5:.4f}         = {m4/m5:.4e} GeV⁻¹")
print(f"    × 1/α_GUT²      = {tau_gev_inv:.4e} GeV⁻¹")
print(f"    × ħ (1 GeV⁻¹ = {HBAR_GEV_S:.4e} s)  = {tau_s:.4e} s")
print(f"    ÷ year ({YEAR_S:.4e} s)      = {tau_yr:.3e} yr")
print()

ratio = tau_yr / TAU_BOXED_YR
print(f"  HONEST VALUE of the boxed formula with its own inputs:")
print(f"      τ_p = {tau_yr:.3e} yr")
print(f"  vs the printed boxed value τ_p ≈ 4×10³⁴ yr:")
print(f"      ratio = {ratio:.1f}×   ← the ledgered 323× discrepancy")
print()

# What input set WOULD reproduce the printed 4×10³⁴?
tau_boxed_gev_inv = TAU_BOXED_YR * YEAR_S / HBAR_GEV_S
m4m5_boxed = tau_boxed_gev_inv / term1
m_gut_implied = (m4m5_boxed * m5)**0.25
m_p_implied = (m4 / m4m5_boxed)**0.2
print(f"  Where the 323× enters: the printed value is not the value of the")
print(f"  printed formula.  The stated inputs compound to {tau_yr:.3e} yr;")
print(f"  the printed 4×10³⁴ yr would require the M⁴/m⁵ term to be")
print(f"  {m4m5_boxed:.3e} GeV⁻¹ instead of {m4/m5:.3e} GeV⁻¹ —")
print(f"  i.e. M_GUT ≈ {m_gut_implied:.2e} GeV (4.2× below the stated")
print(f"  {M_GUT:.0e} GeV; (2×10¹⁶/4.7×10¹⁵)⁴ ≈ {ratio:.0f}×) or, equivalently,")
print(f"  m_p ≈ {m_p_implied:.2f} GeV.  The slip enters in the M⁴/m⁵ term at")
print(f"  the final evaluation (the 1 GeV⁻¹ → s → yr conversion of the")
print(f"  dimensional estimate); no stated input is itself misprinted.")
print()

# Cross-check with the doc's own φ-value α_GUT = φ⁻³/4π
tau_yr_phi = term_phi_1 = 1.0 / ALPHA_GUT_PHI**2 * m4 / m5 * HBAR_GEV_S / YEAR_S
print(f"  With the doc's φ-value α_GUT = φ⁻³/4π = 1/{1/ALPHA_GUT_PHI:.2f}:")
print(f"      τ_p = {tau_yr_phi:.3e} yr   (ratio vs boxed: {tau_yr_phi/TAU_BOXED_YR:.0f}×)")
print()

# ---------------------------------------------------------------------------
print("─ CLAIM B — coherence budget N_max  (proton-coherence-budget.md §3) ─")
print()
lam_p = HBARC_GEV_M / M_P            # proton Compton wavelength [m]
n_exact = math.log(lam_p / M_PL) / LN_PHI
exponent = DELTA * (n_exact + 1) + n_exact * (n_exact + 1) / 2.0
nmax_log10 = exponent * LOG10_PHI
omega_p = M_P / HBAR_GEV_S           # proton Compton frequency [Hz]
# log10 space: 10^941.6 overflows float; carry the exponent only
log10_tau_b_s  = nmax_log10 - math.log10(omega_p)
log10_tau_b_yr = log10_tau_b_s - math.log10(YEAR_S)

print(f"  n = log_φ(λ_p/ℓ_Pl) = log_φ({lam_p:.4e}/{M_PL:.4e}) = {n_exact:.2f}")
print(f"      (doc: 91.46; ledger: Mapped rung)")
print(f"  exponent = δ(n+1) + n(n+1)/2 = 3×{n_exact+1:.2f} + {n_exact:.2f}×{n_exact+1:.2f}/2")
print(f"           = {DELTA*(n_exact+1):.2f} + {n_exact*(n_exact+1)/2:.2f} = {exponent:.2f}")
print(f"      (doc prints 277.4 + 4228.3 = 4505.7; exact sum {exponent:.2f} ≈ φ⁴⁵⁰⁶ ✓)")
print(f"  N_max = φ^{exponent:.2f} = 10^{nmax_log10:.2f} cycles  (doc: ≈ 10⁹⁴² ✓)")
print(f"  ω_p = m_p c²/ħ = {M_P}/{HBAR_GEV_S:.4e} = {omega_p:.4e} Hz  (doc: 1.43×10²⁴ ✓)")
print(f"  τ_p = N_max/ω_p = 10^{log10_tau_b_s:.2f} s = 10^{log10_tau_b_yr:.2f} yr")
print(f"      (doc: ≈ 10⁹¹⁰ yr ✓)")
print(f"  → Claim B's boxed numbers DO follow from its stated inputs: the")
print(f"    chain is arithmetically self-consistent, unlike Claim A's 4×10³⁴.")
print()

# ---------------------------------------------------------------------------
print("─ CLOSED LEDGER STATEMENT ─")
print()
print(f"  Corrected τ_p (Claim A, stated inputs):  {tau_yr:.2e} yr")
print(f"    (α_GUT = 1/53 as printed; {tau_yr_phi:.2e} yr with α_GUT = φ⁻³/4π)")
print(f"  Boxed 4×10³⁴ yr: fails its own arithmetic — 323× too low.")
print(f"  Corrected value vs Super-K bound (>2.4×10³⁴ yr): consistent (null).")
print(f"  Corrected value vs Hyper-K reach (~10³⁵ yr): {math.log10(tau_yr)-35:.1f} orders")
print(f"    of magnitude ABOVE reach — the 'within Hyper-K reach' framing of")
print(f"    gut-embedding.md §3.1 does not survive the corrected arithmetic.")
print()
print(f"  Tier status of the closed result:")
print(f"    GUT chain:  formula = standard SU(5) dimensional estimate (Derived,")
print(f"                as standard physics); inputs α_GUT = φ⁻³/4π and")
print(f"                M_GUT = 2×10¹⁶ GeV (Δb = 1.70 content) = Mapped (ledger).")
print(f"                → closed value {tau_yr:.2e} yr is Mapped, arithmetic closed.")
print(f"    Coherence chain:  product structure = Derived (combinatorial);")
print(f"                per-rung q_i = 1 − φ^(−i−δ) = Hypothesized (no derivation,")
print(f"                doc §8); rung n = 91.46 = Mapped (ledger).")
print(f"                → τ_p ≈ 10⁹¹⁰ yr is internally consistent but rests on the")
print(f"                Hypothesized q_i profile; it is a different prediction")
print(f"                (coherence dephasing) from Claim A (gauge mediation).")
print()
print("=" * 76)
