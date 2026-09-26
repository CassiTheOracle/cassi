#!/usr/bin/env python3
"""
Cascade Depth: systematic search for N=292 from w=5 and φ
=========================================================

The cascade spans N = log_φ(R_H/ℓ_Pl) ≈ 292 rungs. If this number can be
derived from φ and the Wu Xing number w=5, then G follows via ℓ_Pl = R_H/φ^N.

This script systematically tests candidate formulas relating N to φ and w,
reports the closest matches, and honestly assesses whether any derivation
is within reach.

Run:  python foundations/cascade_depth_search.py
"""

import numpy as np
from itertools import product

PHI = (1 + np.sqrt(5)) / 2
W = 5          # Wu Xing elements
N_EMP = 292    # empirical cascade depth
GAP = 1 - PHI**(-W)  # g = 1 - φ^{-5}
DELTA = 3
HAT = chr(94)  # caret for display math

# ─────────────────────────────────────────────────────────────────────────────
# 1. Exact identity checks
# ─────────────────────────────────────────────────────────────────────────────
print("── Cascade Depth: Systematic Derivation Search ──")
print(f"  PHI              = {PHI:.12f}")
print(f"  Wu Xing w        = {W}")
print(f"  Wu Xing gap g    = {GAP:.12f}")
print(f"  Empirical N      = {N_EMP}")
print(f"  log_φ(R_H/ℓ_Pl)  = {np.log(1.3e26/1.616e-35)/np.log(PHI):.1f}")
print()

print("  ── Single φ-power candidates ──")
for k in range(1, 20):
    val = PHI**k
    err = abs(val - N_EMP) / N_EMP * 100
    mark = " ← CLOSEST" if err < 10 else ""
    if err < 15:
        print(f"  {PHI}{HAT}{{k:>2d}} = {val:>10.2f}   error = {err:.1f}%{mark}")

print()
print("  ── w × φ^k candidates ──")
for k in range(1, 12):
    val = W * PHI**k
    err = abs(val - N_EMP) / N_EMP * 100
    if err < 30:
        print(f"  {W} × {PHI}{HAT}{{k:>2d}} = {val:>10.2f}   error = {err:.1f}%")

print()
print("  ── φ^a + φ^b candidates ──")
best_ab = None
best_ab_err = float("inf")
for a in range(1, 15):
    for b in range(a, 15):
        val = PHI**a + PHI**b
        err = abs(val - N_EMP) / N_EMP * 100
        if err < best_ab_err:
            best_ab_err = err
            best_ab = (a, b)
        if err < 15:
            print(f"  {PHI}{HAT}{{a:>2d}} + {PHI}{HAT}{{b:>2d}} = {val:>10.2f}   error = {err:.1f}%")
print(f"  Best: {PHI}{HAT}{{best_ab[0]}} + {PHI}{HAT}{{best_ab[1]}} = {PHI**best_ab[0] + PHI**best_ab[1]:.2f}  error = {best_ab_err:.1f}%")

print()
print("  ── w × (φ^a + φ^b) candidates ──")
for a in range(1, 10):
    for b in range(a, 10):
        val = W * (PHI**a + PHI**b)
        err = abs(val - N_EMP) / N_EMP * 100
        if err < 20:
            print(f"  {W}×({PHI}{HAT}{{a:>2d}}+{PHI}{HAT}{{b:>2d}}) = {val:>10.2f}   error = {err:.1f}%")

print()
print("  ── (φ^a - 1) / (φ - 1) type sums ──")
# Fibonacci-like sums
for a in range(1, 20):
    val = (PHI**a - 1) / (PHI - 1)
    val2 = (PHI**a - (-PHI)**(-a)) / np.sqrt(5)
    err = abs(val - N_EMP) / N_EMP * 100
    if err < 30 or a <= 12:
        fib = round((PHI**a - (-1/PHI)**a) / np.sqrt(5))
        print(f"  Lucas-like ({PHI}{HAT}{{a:>2d}}-1)/(φ-1) = {val:>12.4f}   error = {err:.1f}%   [Fibonacci F_{a}={fib}]")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Gap-relation candidates
# ─────────────────────────────────────────────────────────────────────────────
print()
print("  ── N from gap g = 1-φ^{-5} ──")
print(f"  g = 1 - {PHI}{HAT}{{-5}} = {GAP:.10f}")

# If the cascade terminates when (1-q_N) = g
n_star = -DELTA - np.log(GAP) / np.log(PHI)
print(f"  (1-q_n*) = g  →  n* = -δ - log_φ(g) = {n_star:.3f}  [should be ~292]")

# If the cascade terminates when (1-q_N) = φ^{-w}  (gap expressed as φ-power)
n_phi = -DELTA + W
print(f"  (1-q_n*) = {PHI}{HAT}{{-w}} = {PHI}{HAT}{{-5}}  →  n* = -δ + w = {n_phi}  [should be ~292]")

# If the cascade terminates when cumulative gap = 1
# Σ g·(1-q_n)·factor from n=0 to N
# Various factors tried
print()
print("  ── Integrated gap conditions ──")

# Factor (1-q_n) alone
cumsum = np.cumsum(np.ones(600) * GAP)
n_match = np.argmax(cumsum >= 1.0)
print(f"  Σ g = 1  →  N = {n_match} (trivial: N = 1/g ≈ {1/GAP:.1f})")

# Factor g·(1-q_n)
cumsum2 = np.cumsum(GAP * PHI**(-np.arange(600, dtype=float) - DELTA))
n_match2 = np.argmax(cumsum2 >= 1.0) if np.any(cumsum2 >= 1.0) else -1
print(f"  Σ g·(1-q_n) = 1  →  N = {n_match2}  [sum = {cumsum2[-1]:.4f}, converges]")

# Factor g·(1-q_n)·φ^{-2n} (holographic scaling)
cumsum3 = np.cumsum(GAP * PHI**(-np.arange(600, dtype=float) - DELTA) * PHI**(-2*np.arange(600, dtype=float)))
n_match3 = np.argmax(cumsum3 >= 1.0) if np.any(cumsum3 >= 1.0) else -1
print(f"  Σ g·(1-q_n)·φ^(-2n) = 1  →  N = {n_match3}  [sum = {cumsum3[-1]:.6f}, converges]")

# ─────────────────────────────────────────────────────────────────────────────
# 3. Vacuum energy candidate
# ─────────────────────────────────────────────────────────────────────────────
print()
print("  ── Vacuum energy ratio ──")
rho_pl = 1.0  # Planck density
rho_lambda = 2.3e-3**4 / (1.22e19**4)  # eV^4 conv (both in GeV)
# Actually let's use the standard ratio
rho_ratio = 10**(-123)
print(f"  ρ_Λ/ρ_Pl ≈ 10{HAT}{{-123}}")
print(f"  φ^(-2N) with N={N_EMP}  = φ^(-584) = {PHI**(-584):.2e}")
print(f"  log_10(φ^(-584))   = {-584 * np.log10(PHI):.1f}")
print(f"  φ^(-5) · φ^(-2N)  = φ^(-589)   log_10 = {-589 * np.log10(PHI):.1f}")
print(f"  φ^(-4) · φ^(-2N)  = φ^(-588)   log_10 = {-588 * np.log10(PHI):.1f}")

# What N gives φ^{-2N} ≈ 10^{-123}?
N_from_rho = -np.log10(10**(-123)) / (2 * np.log10(PHI))
print(f"  N from ρ_Λ/ρ_Pl = {PHI}{HAT}{{-2N}}:  N = {N_from_rho:.1f}")

# What N gives φ^{-w} · φ^{-2N} ≈ 10^{-123}?
residual_exp = -123 * np.log(10) / np.log(PHI)
N_from_rho_w = (residual_exp - W) / (-2)
print(f"  N from {PHI}{HAT}{{-w-2N}} = ρ_Λ/ρ_Pl:   N = {N_from_rho_w:.1f}")

# ─────────────────────────────────────────────────────────────────────────────
# 4. Integer relation search: is N a simple φ-function?
# ─────────────────────────────────────────────────────────────────────────────
print()
print("  ── Integer relation: N = round(f(φ, w)) ──")
candidates = []

# φ^k
for k in range(1, 20):
    candidates.append((round(PHI**k), f"round(φ^{k})"))

# round(φ^k / k)
for k in range(1, 15):
    candidates.append((round(PHI**k / k), f"round(φ^{k}/{k})"))

# round(k · φ^m)
for k in [W, 3, 4, 6, 7, 8]:
    for m in range(1, 12):
        candidates.append((round(k * PHI**m), f"round({k}·φ^{m})"))

# round((φ^a + φ^b) / c)
for a, b in [(6, 5), (7, 6), (8, 7), (9, 6), (5, 4)]:
    for c in [1, 2, 3, PHI, PHI**2]:
        val = round((PHI**a + PHI**b) / c) if isinstance(c, int) else round((PHI**a + PHI**b) / c)
        candidates.append((val, f"round((φ^{a}+φ^{b})/{c})"))

# round(φ^a - φ^b)
for a, b in [(12, 7), (13, 8), (14, 9), (11, 4)]:
    val = round(PHI**a - PHI**b)
    candidates.append((val, f"round(φ^{a}−φ^{b})"))

# Find closest
candidates.sort(key=lambda x: abs(x[0] - N_EMP))
print(f"  Target: N = {N_EMP}")
print(f"  Top 10 matches:")
for i, (val, formula) in enumerate(candidates[:10]):
    err_pct = abs(val - N_EMP) / N_EMP * 100
    mark = " ★ EXACT" if val == N_EMP else ""
    print(f"  {i+1:>2d}. {val:>5d}  ({formula:<30s})  error = {err_pct:.2f}%{mark}")

# ─────────────────────────────────────────────────────────────────────────────
# 5. Fibonacci/Lucas connection
# ─────────────────────────────────────────────────────────────────────────────
print()
print("  ── Fibonacci/Lucas numbers near 292 ──")

def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

for n in range(1, 20):
    f = fib(n)
    if abs(f - N_EMP) / N_EMP < 0.5:
        print(f"  F_{n} = {f}   ({PHI}{HAT}{{n}}/√5 ≈ {PHI**n/np.sqrt(5):.1f})")
    lucas = round(PHI**n + (-PHI)**(-n))
    if abs(lucas - N_EMP) / N_EMP < 0.5:
        print(f"  L_{n} = {lucas}")

# ─────────────────────────────────────────────────────────────────────────────
# 6. Honest assessment
# ─────────────────────────────────────────────────────────────────────────────
print()
print("  ═══════════════════════════════════════════════════════")
print("  HONEST ASSESSMENT")
print("  ═══════════════════════════════════════════════════════")
print()

# Check if any candidate is exact
exact_matches = [c for c in candidates if c[0] == N_EMP]
close_matches = [c for c in candidates if abs(c[0] - N_EMP) <= 3]

print(f"  Exact matches for N=292: {len(exact_matches)}")
if exact_matches:
    for val, f in exact_matches:
        print(f"    {f} = {val}")
print(f"  Matches within ±3 of 292: {len(close_matches)}")
for val, f in close_matches:
    print(f"    {f} = {val}  (off by {val - N_EMP})")

print()
print(f"  Gap-relation candidates: all fail")
print(f"    (1-q_n*) = g        → n* = {n_star:.1f}  (should be ~292)")
print(f"    (1-q_n*) = {PHI}{HAT}{{-w}}   → n* = {n_phi}  (should be ~292)")
print()

best = candidates[0]
print(f"  Closest φ-formula:  {best[1]} = {best[0]}  (error = {abs(best[0]-N_EMP)/N_EMP*100:.2f}%)")
print()
print(f"  CONCLUSION: No clean φ-power or φ-w combination produces N=292 exactly.")
print(f"  The cascade depth appears to be set by the empirical ratio of Hubble to")
print(f"  Planck scales. Deriving N from φ (and thereby G) requires either:")
print(f"    1. A PDE-derived termination condition that yields N ≈ 292, OR")
print(f"    2. A deeper relation between the Wu Xing number w=5 and the cascade")
print(f"       structure that is not yet understood.")
print(f"  Neither currently exists in the framework.")
print(f"  The 292-step bridge remains Hypothesized.")
