#!/usr/bin/env python3
"""φ-periodicity test on Riemann ζ zero statistics (Odlyzko's first 100,000 zeros).

Falsifiable question: do the nontrivial zeros of ζ carry log-periodic
modulation at the Cassi universal period Δ(ln T) = ln φ ≈ 0.4812
(ω₀ = 2π/ln φ ≈ 13.057)?

Protocol (repo logperiodicity-test-calibration):
  - ω₀ fixed, zero fitted parameters for the period
  - cos/sin linear basis (no phase grid)
  - report dAIC AND ω-specificity percentile p_spec (signal requires p_spec < 0.05)
  - planted-signal power check; scrambled-data null check

Run from repo root:
  python experiments/riemann_phi_search/run_zeta_phi_periodicity_test.py

Data: A. Odlyzko's table of the first 100,000 zeros (imaginary parts,
one per line), cached at runs/odlyzko_zeros1.txt (gitignored). The table is
~1.8 MB; the script re-downloads only if the cache is missing or wrong-sized.
"""

import math

import numpy as np

from zeta_zeros import load_zeros, PHI, LN_PHI, W0


# --------------------------------------------------------------------------
# regression machinery
# --------------------------------------------------------------------------
def fit_osc(y, x, w):
    X = np.column_stack([np.ones_like(x), x, np.cos(w * x), np.sin(w * x)])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(np.sum((y - X @ beta) ** 2))


def fit_lin(y, x):
    X = np.column_stack([np.ones_like(x), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(np.sum((y - X @ beta) ** 2))


def dAIC_at(y, x, w):
    n = len(y)
    aic_osc = n * np.log(fit_osc(y, x, w) / n) + 2 * 4
    aic_lin = n * np.log(fit_lin(y, x) / n) + 2 * 2
    return aic_osc - aic_lin


def specificity(y, x, w0, wgrid, excl=2.0):
    """p = fraction of grid frequencies (excluding w0 ± excl) with dAIC ≤ dAIC(w0)."""
    d0 = dAIC_at(y, x, w0)
    ds = np.array([dAIC_at(y, x, w) for w in wgrid if abs(w - w0) >= excl])
    return d0, float(np.mean(ds <= d0))


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    print(f"phi = {PHI:.10f}  ln(phi) = {LN_PHI:.8f}  omega_0 = {W0:.4f}")
    g = load_zeros()
    print(f"loaded {len(g)} zeros; gamma_1={g[0]:.9f} gamma_last={g[-1]:.9f}")
    print(f"ln-range = {math.log(g[-1] / g[0]):.2f} (~{math.log(g[-1] / g[0]) / LN_PHI:.1f} phi-periods)")

    wgrid = np.arange(2.0, 40.001, 0.2)
    rng = np.random.default_rng(7)

    # ---- Test B: unfolded spacings ----
    d = (g[1:] - g[:-1]) * np.log(g[:-1] / (2 * np.pi)) / (2 * np.pi)
    x = np.log(g[:-1])
    print(f"\n[Test B] unfolded spacings n={len(d)}  mean={d.mean():.5f}  std={d.std():.5f}")
    d0, p = specificity(d, x, W0, wgrid)
    print(f"omega_0={W0:.3f}:  dAIC={d0:+.2f}   p_spec={p:.3f}")
    best = min((w for w in wgrid if abs(w - W0) >= 2.0), key=lambda w: dAIC_at(d, x, w))
    print(f"best grid omega = {best:.1f} (dAIC={dAIC_at(d, x, best):+.2f})")
    print("planted-signal power check (spacings):")
    for A in [0.10, 0.03, 0.01]:
        dp = d + A * np.cos(W0 * x)
        d0p, pp = specificity(dp, x, W0, wgrid)
        print(f"  A={A:.2f}:  dAIC={d0p:+.2f}   p_spec={pp:.3f}")
    ds_ = d.copy(); rng.shuffle(ds_)
    d0n, pn = specificity(ds_, x, W0, wgrid)
    print(f"scrambled null:  dAIC={d0n:+.2f}   p_spec={pn:.3f}")
    m = len(d) // 4
    for i in range(4):
        sl = slice(i * m, (i + 1) * m)
        d0w, pw = specificity(d[sl], x[sl], W0, wgrid)
        print(f"window {i + 1} spacing test:  dAIC={d0w:+.2f}   p_spec={pw:.3f}")

    # ---- Test A: density deviation D(u) on a uniform ln-T grid ----
    u = np.linspace(math.log(g[0] + 0.01), math.log(g[-1]), 1000)
    T = np.exp(u)
    N = np.searchsorted(g, T)
    Nbar = T / (2 * np.pi) * np.log(T / (2 * np.pi)) - T / (2 * np.pi) + 7 / 8
    D = N - Nbar
    print(f"\n[Test A] D(u)=N-Nbar on uniform ln-T grid  n={len(D)}  |D|max={np.abs(D).max():.2f}")
    d0, p = specificity(D, u, W0, wgrid)
    print(f"omega_0={W0:.3f}:  dAIC={d0:+.2f}   p_spec={p:.3f}")
    best = min((w for w in wgrid if abs(w - W0) >= 2.0), key=lambda w: dAIC_at(D, u, w))
    print(f"best grid omega = {best:.1f} (dAIC={dAIC_at(D, u, best):+.2f})")
    print("planted-signal power check (density):")
    for A in [0.50, 0.15]:
        Dp = D + A * np.cos(W0 * u)
        d0p, pp = specificity(Dp, u, W0, wgrid)
        print(f"  A={A:.2f}:  dAIC={d0p:+.2f}   p_spec={pp:.3f}")
    Ds = D.copy(); rng.shuffle(Ds)
    d0n, pn = specificity(Ds, u, W0, wgrid)
    print(f"scrambled null:  dAIC={d0n:+.2f}   p_spec={pn:.3f}")

    # artifact diagnosis for the best grid omega (smooth-data trap check)
    Du = D - np.polyval(np.polyfit(u, D, 1), u)
    F = np.abs(np.fft.rfft(Du * np.hanning(len(Du)))) ** 2
    wspec = np.fft.rfftfreq(len(Du), d=u[1] - u[0]) * 2 * np.pi
    peak_w = wspec[np.argmax(F)]
    rank_w0 = int(np.sum(F > F[np.argmin(abs(wspec - W0))]))
    print(f"spectrum of D(u): peak at w={peak_w:.1f} (high-freq chirp mass); "
          f"omega_0 rank {rank_w0}/{len(F)}")
    m = len(u) // 4
    wins = [dAIC_at(D[i * m:(i + 1) * m], u[i * m:(i + 1) * m], best)
            for i in range(4)]
    print(f"best-omega {best:.1f} dAIC by window (T ranges): "
          + ", ".join(f"{w:+.2f}" for w in wins)
          + "  -> non-stationary across windows = chirp artifact, not a stationary signal")


if __name__ == "__main__":
    main()
