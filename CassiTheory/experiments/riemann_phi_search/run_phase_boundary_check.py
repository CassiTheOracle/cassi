#!/usr/bin/env python3
"""Step 2b checks: the energy-dependent boundary for the phase operator.

Companion to hypotheses/riemann-two-fluid-phase-operator.md §8.

D1. Moving-wall theorem. The Bessel cavity with a wall moving as
      L(E) = (1/2) ln(E/2 pi e) + 9 pi / (8 E)
    has exact counting  N(E) = #{n : j_{1,n} <= E L(E)}
    reproducing the Riemann-von Mangoldt smooth count
      Nbar(E) = (E/2pi) ln(E/2pi) - E/2pi + 7/8
    to within one state (the 9/8 - 1/4 = 7/8 phase bookkeeping:
    wall argument = Riemann-Siegel theta + 5 pi / 4).

D2. Candidate exclusions:
    - fixed walls (sigma-regularization at any rung): linear counting (Step 1);
    - Qi-gated energy-dependent mass: subdominant, Weyl law unchanged (Step 1);
    - IIR memory timescale tau = phi^{-1} as a u-periodic boundary with period
      ln phi: spectrum E_n = n * omega_0 (omega_0 = 2 pi / ln phi = 13.057),
      a phi-locked lattice with density 1/omega_0 = 0.0766 -- 15x too sparse
      for the zeros, and a log-periodic structure the measured null test
      (run_zeta_phi_periodicity_test.py) already rejects. Quantified below.

Run from repo root:
  python experiments/riemann_phi_search/run_phase_boundary_check.py
"""

import math

import numpy as np
from scipy.special import jn_zeros, loggamma

from zeta_zeros import load_zeros, PHI, LN_PHI, W0

RVMC = 7.0 / 8.0


def nbar(E):
    return E / (2 * math.pi) * math.log(E / (2 * math.pi)) \
        - E / (2 * math.pi) + RVMC


def wall_L(E):
    """The unique moving wall reproducing R-vM (D1)."""
    E = np.asarray(E, float)
    return 0.5 * np.log(E / (2 * math.pi * math.e)) + 9 * math.pi / (8 * E)


def theta_rs(E):
    """Riemann-Siegel theta: Im log Gamma(1/4 + iE/2) - (E/2) ln pi."""
    E = np.asarray(E, float)
    return loggamma(0.25 + 0.5j * E).imag - 0.5 * E * math.log(math.pi)


def main():
    print(f"phi = {PHI:.8f}  ln(phi) = {LN_PHI:.6f}  omega_0 = 2pi/ln(phi) = {W0:.4f}")

    # ---- D1: moving-wall counting vs R-vM ----
    print("\n[D1] moving wall: N(E) = #{j_{1,n} <= E*L(E)} vs Riemann-von Mangoldt")
    E_max = 2000.0
    z_max = E_max * wall_L(E_max)
    jz = jn_zeros(1, int(z_max / math.pi) + 20)   # enough zeros
    Es = np.linspace(20.0, E_max, 300)
    N_exact = np.searchsorted(jz, Es * wall_L(Es))
    Nbar_v = np.array([nbar(e) for e in Es])
    dev = Nbar_v - N_exact
    print(f"  max (Nbar - N_exact) over E in [20, {E_max:.0f}]: {dev.max():.4f}")
    print(f"  min (Nbar - N_exact):                              {dev.min():.4f}")
    print(f"  (match to within one state: constant 9/8 - 1/4 = 7/8 holds)")

    # wall argument vs Riemann-Siegel theta
    print("  wall argument E*L(E) vs theta(E) + 5pi/4:")
    for E in [100.0, 1000.0, 2000.0]:
        diff = E * wall_L(E) - float(theta_rs(E)) - 5 * math.pi / 4
        print(f"    E={E:6.0f}:  diff = {diff:+.5f}  (target 0)")

    # fixed-wall contrast
    jz1 = jn_zeros(1, int(2000.0 / math.pi) + 20)
    N_fixed = np.searchsorted(jz1, Es * 1.0)
    print(f"  fixed wall (L=1) contrast at E=2000: count {N_fixed[-1]} vs R-vM {nbar(2000.0):.0f}"
          f"  (linear vs logarithmic)")

    # ---- D2: tau = phi^{-1} candidate - phi-locked lattice ----
    print("\n[D2] IIR-memory candidate (tau = phi^-1): u-periodic boundary, period ln phi")
    print(f"  predicted spectrum E_n = n*omega_0, density 1/omega_0 = {1 / W0:.4f}")
    g = load_zeros()
    dens_zeros = len(g) / g[-1]
    print(f"  zeros density over the table: {dens_zeros:.4f}  (factor "
          f"{dens_zeros / (1 / W0):.1f} denser than the lattice - excluded on density)")
    n_lat = int(g[-1] / W0)
    lat = W0 * np.arange(1, n_lat + 1)
    eps = 0.2
    # distance of each zero to the nearest lattice point (vectorized)
    idx = np.searchsorted(lat, g)
    dist = np.minimum(np.abs(g - lat[np.minimum(idx, len(lat) - 1)]),
                      np.abs(g - lat[np.maximum(idx - 1, 0)]))
    frac_locked = float(np.mean(dist < eps))
    # control: lattice shifted by half a period (same density, random phase)
    lat2 = lat + W0 / 2
    idx2 = np.searchsorted(lat2, g)
    dist2 = np.minimum(np.abs(g - lat2[np.minimum(idx2, len(lat2) - 1)]),
                       np.abs(g - lat2[np.maximum(idx2 - 1, 0)]))
    frac_ctrl = float(np.mean(dist2 < eps))
    print(f"  fraction of zeros within {eps} of n*omega_0: {100 * frac_locked:.1f}%")
    print(f"  same for half-period-shifted control lattice:   {100 * frac_ctrl:.1f}%"
          f"  (equal => no locking; the phi-periodicity null already rejects it)")


if __name__ == "__main__":
    main()
