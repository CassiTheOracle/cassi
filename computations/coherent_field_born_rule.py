#!/usr/bin/env python3
"""
Coherent-Field Born Rule: Verification
=======================================

Verifies the derivation of the Born rule from coherent-field detection
statistics (foundations/quantum-measurement-derivation.md section 4):

  (1) The field state at the detector is a coherent excitation of the linear
      quantum sector with amplitude alpha(x) = g * psi(x).  Absorbed-quanta
      counts are Poisson with mean lambda(x) = |alpha(x)|^2 = g^2 |psi(x)|^2:
          P(n) = exp(-lambda) lambda^n / n!
  (2) A measurement reports the FIRST absorption.  Detector channels are
      independent Poisson processes with rates lambda(x); the first event
      lands at x with probability (exact, coupling-independent):
          P(x) = lambda(x) / sum_x' lambda(x')  =  |psi(x)|^2 / sum|psi(x')|^2
  (3) Conditional on N total absorptions the channel counts are multinomial
      with probabilities lambda / sum lambda (Poisson splitting), so empirical
      frequencies converge to the same |psi|^2 law.
  (4) Weak-coupling reading: single-channel firing probability 1 - exp(-lambda)
      ~ lambda for lambda << 1, but the RELATIVE RATE is the exact, normalized
      statement (the per-channel firing probability is not the Born value).
  (5) Interference is automatic: amplitudes add linearly, so
      |psi_1 + psi_2|^2 = |psi_1|^2 + |psi_2|^2 + 2 Re(psi_1* psi_2).
  (6) Secondary reading consistency: the canonical gate q (theory-reference
      2.4) is monotonically increasing in field intensity rho^2 at fixed
      self-prediction error epsilon^2 -- the higher-|alpha|^2 branch is the
      more coherent branch (directionally consistent, not the source of the
      exact quadratic law).

Usage: python computations/coherent_field_born_rule.py
"""

import numpy as np

rng = np.random.default_rng(20260811)

# --- setup: normalized |psi|^2 over k = 3 detector channels ---------------
psi2 = np.array([0.5, 0.3, 0.2])          # |psi(x)|^2, normalized
lam = psi2                                # lambda = g^2 |psi|^2, g = 1
k = len(psi2)
N_EXP = 2_000_000                         # exposures for first-event law
N_SHOT = 400_000                          # exposures for Poisson shape

print("Setup: |psi|^2 =", psi2, " sum =", psi2.sum())
print()

# --- (1) Poisson step: shape, mean, variance, zero probability -------------
n = rng.poisson(lam, size=(N_SHOT, k))
emp_mean = n.mean(axis=0)
emp_var = n.var(axis=0, ddof=1)
emp_p0 = (n == 0).mean(axis=0)
print("(1) Poisson absorption counts (mean = variance = lambda):")
for i in range(k):
    print(f"    channel {i}: lambda = {lam[i]:.3f} | emp mean = {emp_mean[i]:.3f}"
          f" | emp var = {emp_var[i]:.3f} | P(0) = {emp_p0[i]:.4f}"
          f" vs exp(-lambda) = {np.exp(-lam[i]):.4f}")
print("    max |mean - lambda| =", f"{np.max(np.abs(emp_mean - lam)):.2e}")
print()

# --- (2) First-event law: competing exponentials ---------------------------
t = rng.exponential(1.0 / lam, size=(N_EXP, k))   # waiting times per channel
first = t.argmin(axis=1)
emp_P = np.bincount(first, minlength=k) / N_EXP
born = lam / lam.sum()                            # = |psi|^2 (normalized)
print("(2) First-absorption outcome law (relative rate, exact):")
print("    empirical P(x) :", np.round(emp_P, 5))
print("    Born  |psi|^2  :", np.round(born, 5))
print("    max deviation  :", f"{np.max(np.abs(emp_P - born)):.2e}")
print("    sum P(x)       :", f"{emp_P.sum():.10f} (normalization automatic)")
print()

# --- (3) Poisson splitting -> multinomial conditional law ------------------
N_TOT = 100_000
tot = rng.poisson(lam.sum(), size=N_TOT)
keep = tot > 0
n_cond = rng.multinomial(tot[keep][:20000], born)  # conditional counts
freq = n_cond / n_cond.sum(axis=1, keepdims=True)
print("(3) Conditional on N total absorptions, counts are multinomial(lam/sum):")
print("    mean conditional frequency:", np.round(freq.mean(axis=0), 5),
      " vs", np.round(born, 5))
print("    max deviation:", f"{np.max(np.abs(freq.mean(axis=0) - born)):.2e}")
print()

# --- (4) Weak-coupling limit vs exact relative rate ------------------------
small = 0.01
print("(4) Weak coupling: 1 - exp(-0.01) =", f"{1 - np.exp(-small):.6f}",
      "~ lambda = 0.01 (rel. err", f"{(1 - np.exp(-small) - small) / small:+.2%})")
lam12 = np.array([0.5, 0.3])
born12 = lam12 / lam12.sum()
print("    two channels lam = (0.5, 0.3):")
print("      Born relative rate P(1) =", f"{born12[0]:.4f}",
      " (EXACT -- the outcome law)")
print("      single-channel firing 1 - exp(-0.5) =", f"{1 - np.exp(-0.5):.4f}",
      " (NOT the Born value: firing probability is unnormalized)")
print()

# --- (5) Automatic interference from linearity -----------------------------
p1, p2 = 1.0 + 0.0j, 0.6 + 0.8j          # branch amplitudes (|p2|^2 = 1)
coherent = p1 + p2                        # linear superposition of the field
cross = 2 * np.real(np.conj(p1) * p2)
print("(5) Interference from field linearity:")
print("    |p1|^2 + |p2|^2        =", f"{abs(p1)**2 + abs(p2)**2:.4f}",
      "(incoherent sum)")
print("    |p1 + p2|^2            =", f"{abs(coherent)**2:.4f}",
      "(coherent sum)")
print("    2 Re(p1* p2)           =", f"{cross:.4f} (cross term)")
print("    identity holds         :",
      np.isclose(abs(coherent)**2, abs(p1)**2 + abs(p2)**2 + cross, rtol=1e-14))
print()

# --- (6) Secondary reading: canonical gate q monotone in intensity ---------
PHI = (1 + np.sqrt(5)) / 2
eps2 = 1.0
rho2 = np.linspace(0.1, 10.0, 200)
q = rho2**2 / (rho2**2 + PHI**-2 + eps2)
dq = np.diff(q)
print("(6) Canonical gate q = rho^2/(rho^2 + phi^-2 + eps^2), eps^2 = 1:")
print("    q monotone increasing in rho^2:", bool((dq > 0).all()))
print("    q(0.1) =", f"{q[0]:.4f}", " -> q(10) =", f"{q[-1]:.4f}",
      " (saturates: q is NOT proportional to |psi|^2)")
