#!/usr/bin/env python3
"""
Baryon-Asymmetry Dilution-Span Closure Sweep
============================================

Tests every mechanism-anchored construction of the 44-rung dilution span in
`foundations/baryon-asymmetry.md` §4.4–4.5, with the corrected GUT seed
n ≈ 13.33 (M_GUT = 2×10¹⁶ GeV, `parameter-inventory.md` §10 row 493) and the
exact required exponents:

    log_φ(1/η_obs) = 44.0906  (PDG 6.104×10⁻¹⁰)
    log_φ(1/η_obs) = 44.1263  (doc convention 6.0×10⁻¹⁰)
    φ⁻⁴⁴            = 6.376×10⁻¹⁰  (+4.5% / +6.3% — the ledgered fit)

Sweep contents (each is a candidate reading of the span):

(a) Threshold-crossing spans — coherence-budget per-rung form
    1 − q_i = φ^(−i−δ)  (proton-coherence-budget.md §3, δ = 3 from the
    σ-regularization q_0 = 1 − φ⁻³): crossings of 1−q at 0.618/0.5/0.1/0.01
    sit at i+δ = 1.00/1.44/4.79/9.57 — at or below the GUT seed, so the
    span from the seed is 7–15 rungs, never 44 or 46.7.

(b) Gate-model crossings — the doc's own (1−q) = (φ⁻²+ε²)/(1+φ⁻²+ε²):
    crosses φ⁻¹ at r = 0.240 (reproduces §4.2) and 0.5 at r = 0.466, and
    NEVER reaches 0.1/0.01 (floor 1/(1+φ²) = 0.2764). The r → cascade-step
    map is not derived (homogeneous ODE gives N ≈ 9 total steps), so no
    freeze-out rung follows from the gate alone.

(c) Endpoint scan — span 44 needs the endpoint n = 13.33 + 44 = 57.33,
    E(57.33) = 1.28×10⁷ GeV: an empty-desert scale between the rung-40
    inflation scale (5.3×10¹⁰ GeV) and the rung-60 intermediate scale
    (3.5×10⁶ GeV). No known scale, no structural anchor (57.33 is 2.3 rungs
    above F₁₀ = 55).

(d) Composite gap — log_φ(g) = −0.1964 (g = 1 − φ⁻⁵): the product
    g·φ⁻⁴⁴ = 5.80×10⁻¹⁰ is −5.0% vs PDG, flipping the +4.5% sign of plain
    φ⁻⁴⁴ with the same magnitude; composite exponent 44.196 ≠ 44.09–44.13.

(e) Factor decompositions — 44 = 4×11 = 2×22 (no framework anchors);
    44 = 60 − 16 with rung 16 inside the GUT band but 2.7 rungs from the
    pinned seed; the numerological near-miss φ⁻⁴⁴·(1+g)/2 = 6.09×10⁻¹⁰
    (−0.3% vs PDG) has no dynamical role for (1+g)/2 = 1 − φ⁻⁵/2 and is
    rejected as a second fitted factor on a fitted exponent.

Verdict: no closure. Strongest mechanism-anchored candidate — the
pinch-minus-seed span 60 − 13.33 = 46.67 — sits 5.5% above the exact log
44.13 (η 3.4× low under uniform φ⁻¹-per-rung dilution); the span that would
close (44.13) ends at rung 57.33, where nothing sits. Blocking step: the
freeze-out threshold rung is not fixed by any mechanism.

Usage: python computations/eta_span_closure_check.py
"""

import math

PHI    = (1 + math.sqrt(5)) / 2
LN_PHI = math.log(PHI)
LOG10_PHI = math.log10(PHI)

M_PL     = 1.2209e19   # GeV — Planck mass (mass-ladder convention)
ETA_PDG  = 6.104e-10   # PDG 2024 baryon-to-photon ratio
ETA_DOC  = 6.0e-10     # doc convention
N_GUT    = 13.33       # corrected GUT-seed rung (M_GUT = 2×10¹⁶ GeV)
DELTA    = 3.0         # σ-regularization offset: q_0 = 1 − φ⁻³
N_PINCH  = 60.0        # Qi-gate pinch rung (r = φ⁻¹)

def lg(x):
    return math.log(x) / LN_PHI

def E_rung(n):
    return M_PL / PHI**n

def one_minus_q(eps):
    return (PHI**-2 + eps**2) / (1 + PHI**-2 + eps**2)

def eps_of_r(r):
    return (PHI - r) / (1 + r)

def r_of_target(t):
    """Invert (φ⁻²+ε²)/(1+φ⁻²+ε²) = t for r. None if t below the floor."""
    num = t + t * PHI**-2 - PHI**-2
    if num < 0:
        return None
    eps = math.sqrt(num / (1 - t))
    return (PHI - eps) / (1 + eps)

print("=" * 76)
print("  BARYON-ASYMMETRY DILUTION-SPAN CLOSURE SWEEP")
print("  (baryon-asymmetry.md §4.4–4.5; corrected seed n = 13.33)")
print("=" * 76)

print()
print("─ ANCHORS ─")
print(f"  log_φ(1/η) [PDG  6.104e-10] = {lg(1/ETA_PDG):.4f}")
print(f"  log_φ(1/η) [doc  6.0e-10 ] = {lg(1/ETA_DOC):.4f}")
print(f"  φ⁻⁴⁴              = {PHI**-44:.4e}")
print(f"  φ⁻⁴⁴/η:  PDG {(PHI**-44/ETA_PDG-1)*100:+.2f}%   doc {(PHI**-44/ETA_DOC-1)*100:+.2f}%")

print()
print("─ (a) THRESHOLD CROSSINGS, per-rung form 1−q_i = φ^(−i−δ) ─")
print(f"  (δ = {DELTA:.0f}: proton-budget σ-regularization, q_0 = 1 − φ⁻³)")
print(f"  {'threshold 1−q':>14} {'i+δ at crossing':>16} {'rung i (δ=3)':>13} {'span from seed 13.33':>20}")
for t in (PHI**-1, 0.5, 0.1, 0.01):
    ipd = lg(1 / t)
    i = ipd - DELTA
    print(f"  {t:>14.3f} {ipd:>16.3f} {i:>13.2f} {13.33-i:>20.2f}")

print()
print("─ (b) GATE-MODEL CROSSINGS, doc form (1−q) = (φ⁻²+ε²)/(1+φ⁻²+ε²) ─")
floor = one_minus_q(0.0)
print(f"  floor (ε→0): 1−q = {floor:.5f} = 1/(1+φ²) = {1/(1+PHI**2):.5f}")
for t in (PHI**-1, 0.5, 0.1, 0.01):
    r = r_of_target(t)
    if r is None:
        print(f"  1−q = {t}:  never reached (floor {floor:.4f})")
    else:
        print(f"  1−q = {t}:  r = {r:.4f}   (1−q = φ⁻¹ at r = 0.240 reproduces §4.2 ✓)")
print(f"  at r_0 = 0.047:  1−q = {one_minus_q(eps_of_r(0.047)):.4f}")
print(f"  at r = 0.618 (pinch): 1−q = {one_minus_q(eps_of_r(0.618)):.4f}")
print(f"  → the gate alone fixes no freeze-out rung: the r→step map is not")
print(f"    derived (homogeneous ODE gives N ≈ 9 total steps, not 292).")

print()
print("─ (c) ENDPOINT SCAN (span = n_end − 13.33 = 44 ⇒ n_end = 57.33) ─")
print(f"  {'rung':>7} {'E [GeV]':>12}  register")
for n in (40, 44, 46.67, 52, 57.33, 60):
    reg = {40: "inflation energy scale (table)",
           44: "—desert—",
           46.67: "—desert—",
           52: "old freeze-out (calibrated)",
           57.33: "needed endpoint: EMPTY",
           60: "intermediate/SUSY scale (table)"}[n]
    print(f"  {n:>7.2f} {E_rung(n):>12.3e}  {reg}")
print(f"  GUT band 10^15.5–10^16.5 GeV spans rungs {lg(M_PL/10**16.5):.1f}–{lg(M_PL/10**15.5):.1f}")

print()
print("─ (d) COMPOSITE GAP ─")
g = 1 - PHI**-5
print(f"  g = 1−φ⁻⁵ = {g:.6f};  log_φ(g) = {lg(g):.5f}  (≠ −1/5 = −0.2)")
print(f"  g·φ⁻⁴⁴ = {g*PHI**-44:.4e}   PDG {(g*PHI**-44/ETA_PDG-1)*100:+.2f}%   doc {(g*PHI**-44/ETA_DOC-1)*100:+.2f}%")
print(f"  composite exponent 44 + log_φ(1/g) = {44-lg(g):.4f}  vs exact 44.09–44.13")
print(f"  → gap entering the product flips the sign of the residual, same magnitude.")

print()
print("─ (e) FACTOR DECOMPOSITIONS ─")
print(f"  44 = 4×11 = 2×22:  4, 11, 22 have no framework anchor")
print(f"    (structural numbers: Fibonacci {{5,8,13,21,34,55}}, Wu Xing 5, dim 3)")
print(f"  44 = 60 − 16:       rung 16 → E = {E_rung(16):.2e} GeV is inside the GUT band")
print(f"    but 2.7 rungs from the pinned seed 13.33 — rejected")
print(f"  φ⁻⁴⁴·(1+g)/2 = {PHI**-44*(1+g)/2:.4e}  PDG {(PHI**-44*(1+g)/2/ETA_PDG-1)*100:+.2f}%  — closest two-factor")
print(f"    product found, but (1+g)/2 = 1 − φ⁻⁵/2 has no dynamical role:")
print(f"    a second fitted factor on a fitted exponent — rejected")

print()
print("─ CANDIDATE SPANS ─")
print(f"  {'construction':<34} {'span':>7} {'η = φ^(−span)':>14} {'vs η_obs (doc)':>15}")
rows = [
    ("gate threshold r≈0.240 → step ~40", 40 - N_GUT),
    ("n_freeze 46.67 − seed 13.33", 46.67 - N_GUT),
    ("old freeze 52 − seed 13.33", 52 - N_GUT),
    ("seed 13.33 + 44 (needed)", 44.0),
    ("pinch 60 − seed 13.33", N_PINCH - N_GUT),
]
for name, span in rows:
    eta = PHI**-span
    print(f"  {name:<34} {span:>7.2f} {eta:>14.3e} {eta/ETA_DOC:>14.1f}×")

print()
print("─ STRONGEST CANDIDATE vs EXACT LOG ─")
gap = (46.67 - lg(1/ETA_DOC)) / 46.67
print(f"  pinch-minus-seed span 46.67 vs exact log {lg(1/ETA_DOC):.2f}:")
print(f"    (46.67−44.13)/46.67 = {gap*100:.1f}%  (46.67/44.13 = {46.67/44.13:.3f})")
print(f"    φ^(−46.67)/η_obs = {PHI**-46.67/ETA_DOC:.2f}  → 1/{1/(PHI**-46.67/ETA_DOC):.1f}× below observed")
print(f"    φ^2.57 = {PHI**2.57:.2f}  (the 2.57-rung overshoot)")

print()
print("─ VERDICT ─")
print("  No mechanism-anchored construction reproduces the exact log")
print("  44.09–44.13. The 44-rung span remains the ledgered fit; the")
print("  blocking step: the freeze-out threshold rung is not fixed by any")
print("  mechanism — the (1−q) = φ⁻¹ gate crossing at r ≈ 0.240 maps to a")
print("  cascade step only through the hand-assigned 5-phase boundaries, and")
print("  the endpoint that would close the fit (57.33) sits at an empty")
print("  desert scale, E = 1.3×10⁷ GeV.")
print("=" * 76)
