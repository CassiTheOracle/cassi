#!/usr/bin/env python3
"""
Cascade RGE: GUT → EW—Gauge Couplings & Beyond-SM Spectrum
==============================================================

Discrete φ-RG evolution of gauge couplings from GUT (step 8) to the
electroweak scale (step 80), determining the beyond-SM particle content
required to match α_s(M_Z) = 0.118.

Theory:
  α_GUT = φ⁻³/(4π) at cascade step 8
  φ-RG: α⁻¹(n+1) = α⁻¹(n) + b·ln(φ)/(2π)  (lower energy = larger n)
  SM: b₁=-4.1, b₂=3.17, b₃=7 (GUT normalization)
  Audit §1.4: α_s(M_Z) from SM alone is 2× too small

Convention (doctrine settlement 2026-08-03):
  This script runs the DISCRETE 72-rung φ-RG convention: E(n) = M_Pl·φ⁻ⁿ with
  the GUT at step 8, so E_GUT = M_Pl·φ⁻⁸ = 2.60×10¹⁷ GeV and the 72-rung span
  covers 72·ln φ = 34.65 in ln μ (vs 32.33 for ln(10¹⁶ GeV/M_Z)).  Its output
  α_s(M_Z) ≈ 0.0683 with Δb₃ ≈ 1.12 is convention-dependent and is NOT the
  canonical value.  Canonical: α_s(M_Z) = 0.0581, Δb = 1.70 from the continuous
  one-loop SM RGE with α_GUT = φ⁻³/(4π), M_GUT = 10¹⁶ GeV, b₃ = −7
  (parameter-inventory.md; numeric-reconciliation 06 §2).

Usage: python computations/cascade_gut_ew_rge.py
"""

import numpy as np
from numpy import sqrt, log, pi

PHI     = (1 + sqrt(5)) / 2
PHI_INV = 1 / PHI
LN_PHI  = log(PHI)

M_PL  = 1.220890e19
N_GUT = 8
N_EW  = 80
N_SPAN = N_EW - N_GUT  # 72 rungs
M_Z   = 91.1876

def E(n): return M_PL * PHI**(-n)
# Discrete-convention scale ladder: E_GUT = E(8) = 2.60×10¹⁷ GeV—NOT the
# canonical M_GUT = 10¹⁶ GeV of the continuous one-loop SM RGE (see docstring).

E_GUT = E(N_GUT)
alpha_GUT = PHI**(-3) / (4*pi)

# SM beta functions (GUT normalization)
b1_sm = -41/10
b2_sm =  19/6
b3_sm =   7

# α_s observed
alpha3_obs = 0.1181

# ======================================================================

print("=" * 72)
print("  CASCADE RGE: GUT → EW—GAUGE COUPLINGS & PARTICLE SPECTRUM")
print("=" * 72)
print()
print(f"  GUT:  step {N_GUT}, E = {E_GUT:.2e} GeV, α_GUT = φ⁻³/(4π) = {alpha_GUT:.4f}")
# NOTE: E_GUT = 2.60×10¹⁷ GeV is the discrete 72-rung convention scale; the
# canonical M_GUT = 10¹⁶ GeV (continuous one-loop SM RGE) gives α_s(M_Z) = 0.0581,
# Δb = 1.70—this script's 0.0683/Δb₃ = 1.12 output is NOT canonical (06 §2).
print(f"  EW:   step {N_EW}, E = {E(N_EW):.2e} GeV, M_Z = {M_Z:.1f} GeV")
print(f"  Span: {N_SPAN} φ-steps")
print()

# §1  φ-RG flow from GUT to EW
print("── §1  φ-RG FLOW (SM CONTENT ONLY) ──")
print()

# φ-RG: α⁻¹(n+1) = α⁻¹(n) + b·ln(φ)/(2π)
# i.e., after N steps: α⁻¹(N_EW) = α_GUT⁻¹ + b·N·ln(φ)/(2π)
#
# Verify: dα⁻¹/d ln μ = b/(2π). Going to lower μ (d ln μ < 0):
#   dα⁻¹ = (b/2π)·d ln μ < 0   (α⁻¹ decreases, α increases—asymptotic freedom)
# In cascade: E(n) = M_PL/φ^n, ln(E(N_EW)/E(N_GUT)) = -N·ln φ
#   α⁻¹(N_EW) = α_GUT⁻¹ + (b/2π)·(-N·ln φ) = α_GUT⁻¹ - b·N·ln φ/(2π)

def alpha_inv_phi_RG(n_steps, b):
    """α⁻¹ after n_steps DOWN from GUT (to lower energy)."""
    return 1/alpha_GUT - b * LN_PHI * n_steps / (2*pi)

inv_a1_sm = alpha_inv_phi_RG(N_SPAN, b1_sm)
inv_a2_sm = alpha_inv_phi_RG(N_SPAN, b2_sm)
inv_a3_sm = alpha_inv_phi_RG(N_SPAN, b3_sm)

print(f"  SM β-function coefficients (GUT normalization):")
print(f"    b₁ = {b1_sm:.1f}, b₂ = {b2_sm:.2f}, b₃ = {b3_sm:.1f}")
print()
print(f"  α⁻¹ after {N_SPAN} φ-steps:")
print(f"    α₁⁻¹(M_Z) = {1/alpha_GUT:.1f} - |{b1_sm:.1f}|·{N_SPAN}·{LN_PHI:.4f}/(2π) = {inv_a1_sm:.1f}")
print(f"    α₂⁻¹(M_Z) = {1/alpha_GUT:.1f} - {b2_sm:.2f}·{N_SPAN}·{LN_PHI:.4f}/(2π) = {inv_a2_sm:.1f}")
print(f"    α₃⁻¹(M_Z) = {1/alpha_GUT:.1f} - {b3_sm:.1f}·{N_SPAN}·{LN_PHI:.4f}/(2π) = {inv_a3_sm:.1f}")
print()
print(f"  Couplings at M_Z:")
print(f"    α₁(M_Z) = {1/inv_a1_sm:.4f}")
print(f"    α₂(M_Z) = {1/inv_a2_sm:.4f}")
print(f"    α₃(M_Z) = {1/inv_a3_sm:.4f}   ← SM prediction")
print(f"    Observed:  α₃(M_Z) = {alpha3_obs:.4f}")
print(f"    Ratio: α₃(SM)/α₃(obs) = {1/inv_a3_sm/alpha3_obs:.2f} → {(1/inv_a3_sm/alpha3_obs)**(-1):.1f}× too small")
print()

# §2  Required Δb₃
print("── §2  BEYOND-SM PARTICLE CONTENT ──")
print()

# α⁻¹(M_Z) observed = 1/0.1181 = 8.47
# α⁻¹(M_Z) from GUT with SM = inv_a3_sm
# The difference is the deficit in α⁻¹ decrease:
# We need α⁻¹ to drop MORE → larger b₃ → MORE particle content

inv_target = 1/alpha3_obs
deficit = inv_a3_sm - inv_target  # how much more α⁻¹ needs to decrease
db3_needed = deficit / (LN_PHI * N_SPAN / (2*pi))
# Convention flag (doctrine settlement 2026-08-03): the Δb₃ ≈ 1.12 printed below
# is the discrete 72-rung φ-RG value and is NOT the canonical Δb = 1.70 of the
# continuous one-loop SM RGE (M_GUT = 10¹⁶ GeV) quoted in parameter-inventory.md.

print(f"  α⁻¹(M_Z) target:  {inv_target:.1f}")
print(f"  α⁻¹(M_Z) from SM: {inv_a3_sm:.1f}")
print(f"  Deficit:          {deficit:.1f} (need α⁻¹ to decrease MORE)")
print(f"  Δb₃ required:     b₃_eff - b₃_SM = {db3_needed:.2f}")
print()

# Candidate particles
print(f"  Particle contributions to Δb₃ (per complete multiplet):")
print(f"    Vector-like quark doublet Q(3,2,1/6) + Q̄:  Δb₃ = 4/3 ≈ 1.33")
print(f"    Colored scalar triplet:                     Δb₃ = 2/3 ≈ 0.67")
print(f"    Extra full SM generation:                   Δb₃ = 4.0")
print()

# The cascade predicts Fibonacci predecessor echoes
# F₅=5, F₆=8, F₇=13 mapped to 72-rung span:
#   Gen 1 (F₅): 5/13 × 72 ≈ 27.7 rungs from GUT → step 35.7
#   Gen 2 (F₆): 8/13 × 72 ≈ 44.3 rungs from GUT → step 52.3
#   Gen 3 (F₇): 13/13 × 72 = 72 rungs → step 80

# The Fibonacci echo at F₈=21 exceeds the EW scale (21/13×72 = 116 > 72),
# so no complete extra generation. But partial echoes (vector-like, no
# chiral structure) are possible at the Fibonacci precursor positions.

# For Δb₃ ≈ {db3_needed}, a vector-like quark doublet at the F₆/F₇
# Fibonacci precursor provides Δb₃ ≈ 1.33—within 20% of required.

print(f"  Cascade-predicted spectrum:")
print(f"    Fibonacci sub-rung positions (mapped to {N_SPAN} rungs):")
for k, label in [(5, "F₅"), (6, "F₆"), (7, "F₇")]:
    fib_k = [0,1,1,2,3,5,8,13][k]
    pos = fib_k / 13 * N_SPAN
    step = N_GUT + pos
    print(f"      {label}={fib_k}: pos {pos:.1f} → step {step:.1f}, E = {E(step):.1e} GeV")
print()

# §3  Verify with VLQ
print("── §3  VERIFICATION: SM + VLQ ──")
print()

db3_vlq = 4/3
b3_cascade = b3_sm + db3_vlq
inv_a3_vlq = alpha_inv_phi_RG(N_SPAN, b3_cascade)
a3_vlq = 1/inv_a3_vlq

print(f"  b₃(SM+VLQ) = {b3_sm:.1f} + 4/3 = {b3_cascade:.2f}")
print(f"  α₃⁻¹(M_Z) = {inv_a3_vlq:.1f}")
print(f"  α₃(M_Z)   = {a3_vlq:.4f}")
print(f"  Observed   = {alpha3_obs:.4f}")
print(f"  Deviation  = {100*(a3_vlq-alpha3_obs)/alpha3_obs:+.1f}%")
print()

# §4  Summary
print("=" * 72)
print("  SUMMARY")
print("=" * 72)
print()
print(f"  α_GUT = φ⁻³/(4π) = {alpha_GUT:.4f} at step {N_GUT}")
print(f"  SM alone: α₃(M_Z) = {1/inv_a3_sm:.3f} → {alpha3_obs/(1/inv_a3_sm):.1f}× too small")
print(f"  Required: Δb₃ = {db3_needed:.2f} from beyond-SM particles")
print(f"  Predicted: VLQ doublet Q(3,2,1/6)+Q̄ at ~{E(N_GUT + 5/13*N_SPAN):.1e} GeV")
print(f"             Δb₃(VLQ) = 4/3 = 1.33 → α₃(M_Z) = {a3_vlq:.3f}")
print(f"             Within {abs(100*(a3_vlq-alpha3_obs)/alpha3_obs):.0f}% of observed")
print()
print(f"  Status: HYPOTHESIZED—cascade RGE predicts specific beyond-SM")
print(f"  particle content. The VLQ mass is ~10¹³ GeV (step ~36), too heavy")
print(f"  for direct production but testable through precision gauge coupling")
print(f"  measurements at FCC-ee (sin²θ_W, α_s).")
print()
print("=" * 72)
