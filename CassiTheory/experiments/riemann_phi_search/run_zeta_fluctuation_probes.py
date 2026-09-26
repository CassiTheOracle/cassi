#!/usr/bin/env python3
"""Fluctuation probes on Riemann ζ zero statistics (de-resonance minimality).

The explicit formula reads the zeros as the resonance content of the primes.
The de-resonance reading (hypotheses/riemann-hypothesis-de-resonance.md) says
that content must be minimal: the fluctuation of the zero-counting function
around its smooth average should be as small as the theorems allow.

Two data-driven probes (per the spectral program doc):

1. Selberg mean-square: S(T) = N(T) - Nbar(T) - O(1/T) is the zero-counting
   fluctuation. Selberg (1946, unconditional):
       (1/T) ∫_0^T S(t)^2 dt  ~  (1/pi^2) ln ln T
   RH is the maximal-deviation companion of this minimal mean-square. We
   measure the mean square on Odlyzko's first 100,000 zeros and compare.

2. Gram's law: with theta(g_n) = n pi, the Gram intervals [g_n, g_{n+1}]
   usually contain exactly one zero. The fraction measures how close the
   zeros sit to a perfectly regular (de-resonant) lattice.

Run from repo root:
  python experiments/riemann_phi_search/run_zeta_fluctuation_probes.py
"""

import math

import numpy as np
from scipy.special import loggamma
from scipy.optimize import brentq

from zeta_zeros import load_zeros, LN_PHI

PI2 = math.pi ** 2


def theta(t):
    """Riemann-Siegel theta: Im log Gamma(1/4 + i t/2) - (t/2) ln pi."""
    t = np.asarray(t, float)
    return loggamma(0.25 + 0.5j * t).imag - 0.5 * t * math.log(math.pi)


def main():
    g = load_zeros()
    print(f"loaded {len(g)} zeros; gamma_1={g[0]:.9f} gamma_last={g[-1]:.9f}")

    # ---- S(T) at gap midpoints (N(T) exact there, S = N - Nbar - O(1/T)) ----
    T = (g[1:] + g[:-1]) / 2.0                    # midpoints, no zero nearby
    N = np.arange(1, len(g))                      # N(T) = n at mid-gap
    Nbar = T / (2 * math.pi) * np.log(T / (2 * math.pi)) - T / (2 * math.pi) + 7 / 8
    S = N - Nbar                                   # = S(T) + O(1/T)

    # ---- Probe 1: Selberg mean-square, in bands ----
    print("\n[Probe 1] Selberg mean-square of S(T)")
    print(f"  |S| max over range: {np.abs(S).max():.2f}")
    Ttop = T[-1]
    ms_tot = np.sum(S ** 2 * np.diff(np.concatenate([[g[0]], T]))) / (Ttop - g[0])
    print(f"  full range: (1/T)∫S² dt = {ms_tot:.4f}   (1/pi²)ln ln T = "
          f"{(1/PI2) * math.log(math.log(Ttop)):.4f}")
    nband = 5
    idx = np.linspace(0, len(T) - 1, nband + 1).astype(int)
    for j in range(nband):
        sl = slice(idx[j], idx[j + 1])
        tb, te = T[sl.start], T[sl.stop - 1]
        ms = np.sum(S[sl] ** 2 * np.diff(np.concatenate([[g[sl.start]], T[sl]]))) \
            / (te - tb)
        print(f"  band {j + 1} T in [{tb:9.0f},{te:9.0f}]: mean-square = {ms:.4f}"
              f"   (1/pi²)ln ln T = {(1/PI2) * math.log(math.log(te)):.4f}"
              f"   max|S| = {np.abs(S[sl]).max():.2f}")

    # ---- Probe 2: Gram's law ----
    print("\n[Probe 2] Gram's law on [g_0, g_n]")
    g0 = brentq(lambda t: theta(t), 14.0, 18.0)   # first Gram point, theta = 0
    # scan Gram points upward from g0 until past the last zero
    gram = [g0]
    t = g0
    n = 1
    while t < g[-1]:
        # widen the bracket until the next Gram point is inside
        width = 1.015
        while theta(t * width) < math.pi * n:
            width *= 2
            if width > 64:
                raise RuntimeError("Gram scan failed to bracket")
        t = brentq(lambda x, nn=n: theta(x) - math.pi * nn, t, t * width)
        gram.append(t)
        n += 1
    gram = np.array(gram)
    ng = len(gram) - 1
    counts = np.searchsorted(g, gram)
    zeros_in = np.diff(counts)
    frac1 = float(np.mean(zeros_in == 1))
    print(f"  {ng} Gram intervals up to T={gram[-1]:.0f} (first {ng} Gram points)")
    print(f"  intervals with exactly 1 zero: {100 * frac1:.1f}%")
    for k in [0, 2, 3]:
        fk = float(np.mean(zeros_in == k))
        if fk > 0:
            print(f"  intervals with {k} zeros: {100 * fk:.2f}%")
    # deviation of zeros from their nearest Gram point, in units of local spacing
    nz = g[1:ng + 1]                              # first ng zeros
    dev = np.minimum(np.abs(nz - gram[:-1]), np.abs(nz - gram[1:]))
    local = np.diff(gram)                          # local Gram spacing
    print(f"  mean |zero - nearest Gram point| = {np.mean(dev) / np.mean(local):.3f}"
          f" of a Gram interval")
    print(f"  (ln-phi period spans {np.log(gram[-1] / gram[0]) / LN_PHI:.1f} "
          f"phi-periods; any phi-locking would show in the above fractions)")


if __name__ == "__main__":
    main()
