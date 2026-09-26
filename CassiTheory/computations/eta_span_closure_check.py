#!/usr/bin/env python3
"""
Baryon-Asymmetry Dilution-Span Closure Sweep
============================================

Tests every mechanism-anchored construction of the 44-rung dilution span in
`foundations/baryon-asymmetry.md` §4.4–4.5, with the declared GUT seed
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

(b) Normalized-gate crossings—the separate unit-density ansatz
    (1−q̄) = (φ⁻²+ε̄²)/(1+φ⁻²+ε̄²): it crosses φ⁻¹ at r = 0.240 and
    0.5 at r = 0.466, and never reaches 0.1 or 0.01 because its floor is
    1/(1+φ²) = 0.2764. This floor does not apply to canonical q at arbitrary
    density. No derived r → cascade-step map turns either crossing into a rung.

(c) Endpoint scan—the integer fit span 44 ends at n = 57.33. The exact
    observational exponents end at n = 57.42–57.46, where
    E ≈ 1.2–1.3×10⁷ GeV. These are empty-desert coordinates between the
    rung-40 inflation scale and the rung-60 intermediate scale. No known scale
    or structural anchor selects an endpoint.

(d) Composite gap — log_φ(g) = −0.1964 (g = 1 − φ⁻⁵): the product
    g·φ⁻⁴⁴ = 5.80×10⁻¹⁰ is −5.0% vs PDG, flipping the +4.5% sign of plain
    φ⁻⁴⁴ with the same magnitude; composite exponent 44.196 ≠ 44.09–44.13.

(e) Factor decompositions — 44 = 4×11 = 2×22 (no framework anchors);
    44 = 60 − 16 with rung 16 inside the GUT band but 2.7 rungs from the
    pinned seed; the numerological near-miss φ⁻⁴⁴·(1+g)/2 = 6.09×10⁻¹⁰
    (−0.3% vs PDG) has no dynamical role for (1+g)/2 = 1 − φ⁻⁵/2 and is
    rejected as a second fitted factor on a fitted exponent.

Verdict: no closure. The strongest mechanism-anchored candidate—the
pinch-minus-seed span 60 − 13.33 = 46.67—sits 5.8% above the exact
document log 44.13 (its unit-normalized dilution is 3.4 times low). The
observationally closing endpoints sit near rungs 57.42–57.46, where no
structural anchor is registered. No mechanism fixes the freeze-out rung.

Usage: python computations/eta_span_closure_check.py
"""

import math

PHI    = (1 + math.sqrt(5)) / 2
LN_PHI = math.log(PHI)
LOG10_PHI = math.log10(PHI)

M_PL     = 1.2209e19   # GeV — Planck mass (mass-ladder convention)
ETA_PDG  = 6.104e-10   # PDG 2024 baryon-to-photon ratio
ETA_DOC  = 6.0e-10     # doc convention
N_GUT    = 13.33       # declared GUT-seed rung (M_GUT = 2×10¹⁶ GeV)
DELTA    = 3.0         # σ-regularization offset: q_0 = 1 − φ⁻³
N_PINCH  = 60.0        # conditionally assigned pinch rung (r = φ⁻¹)

def lg(x):
    return math.log(x) / LN_PHI

def E_rung(n):
    return M_PL / PHI**n

def one_minus_qbar(eps_bar):
    """Unit-density normalized gate openness used by document §4.2."""
    return (PHI**-2 + eps_bar**2) / (1 + PHI**-2 + eps_bar**2)

def eps_bar_of_r(r):
    return (PHI - r) / (1 + r)

def r_of_target(t):
    """Invert the conditional normalized-gate ansatz for r."""
    num = t + t * PHI**-2 - PHI**-2
    if num < 0:
        return None
    eps = math.sqrt(num / (1 - t))
    return (PHI - eps) / (1 + eps)

print("=" * 76)
print("  BARYON-ASYMMETRY DILUTION-SPAN CLOSURE SWEEP")
print("  (baryon-asymmetry.md §4.4–4.5; declared seed n = 13.33)")
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
print("─ (b) CONDITIONAL NORMALIZED-GATE CROSSINGS ─")
print("  (1−q̄) = (φ⁻²+ε̄²)/(1+φ⁻²+ε̄²), with unit total density")
floor = one_minus_qbar(0.0)
print(f"  ansatz floor (ε̄→0): 1−q̄ = {floor:.5f} = 1/(1+φ²)")
for t in (PHI**-1, 0.5, 0.1, 0.01):
    r = r_of_target(t)
    if r is None:
        print(f"  1−q̄ = {t}: never reached (ansatz floor {floor:.4f})")
    else:
        print(f"  1−q̄ = {t}: r = {r:.4f}")
print(f"  at r_0 = 0.047: 1−q̄ = {one_minus_qbar(eps_bar_of_r(0.047)):.4f}")
print(f"  at r = 0.618:     1−q̄ = {one_minus_qbar(eps_bar_of_r(0.618)):.4f}")
print("  → no rung follows without a derived r→step map.")

print()
print("─ (c) ENDPOINT SCAN FROM SEED n = 13.33 ─")
n_end_pdg = N_GUT + lg(1 / ETA_PDG)
n_end_doc = N_GUT + lg(1 / ETA_DOC)
endpoint_rows = [
    (40.0, "inflation energy scale (table)"),
    (44.0, "desert coordinate"),
    (46.67, "desert coordinate"),
    (52.0, "proposed freeze-out coordinate; unanchored"),
    (N_GUT + 44.0, "integer-fit endpoint"),
    (n_end_pdg, "PDG-exact endpoint"),
    (n_end_doc, "document-exact endpoint"),
    (60.0, "intermediate scale (table)"),
]
print(f"  {'rung':>9} {'E [GeV]':>12}  register")
for n, register in endpoint_rows:
    print(f"  {n:>9.3f} {E_rung(n):>12.3e}  {register}")
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
    ("normalized gate r≈0.240 → assigned step 40", 40 - N_GUT),
    ("candidate coordinate 46.67 − seed", 46.67 - N_GUT),
    ("proposed coordinate 52 − seed", 52 - N_GUT),
    ("seed 13.33 + 44 (needed)", 44.0),
    ("pinch 60 − seed 13.33", N_PINCH - N_GUT),
]
for name, span in rows:
    eta = PHI**-span
    print(f"  {name:<34} {span:>7.2f} {eta:>14.3e} {eta/ETA_DOC:>14.1f}×")

print()
print("─ STRONGEST CANDIDATE vs EXACT LOG ─")
required_doc = lg(1 / ETA_DOC)
gap = (46.67 - required_doc) / required_doc
print(f"  pinch-minus-seed span 46.67 vs exact log {required_doc:.2f}:")
print(f"    relative span excess = {gap*100:.1f}%")
print(f"    φ^(−46.67)/η_obs = {PHI**-46.67/ETA_DOC:.2f}, or {1/(PHI**-46.67/ETA_DOC):.1f} times low")

print()
print("─ VERDICT ─")
print("  No mechanism-anchored construction reproduces the exact log")
print("  44.09–44.13. The 44-rung span remains the ledgered fit.")
print("  The conditional normalized-gate crossing at r ≈ 0.240 maps")
print("  to a cascade step only through the assigned 5-phase boundaries.")
print(f"  Exact closing endpoints n = {n_end_pdg:.3f}–{n_end_doc:.3f}")
print("  sit at unregistered desert scales.")
print("=" * 76)
