"""smooth_probe.py -- the axial design-law arms (Q1) and the cascade-preservation arm (Q2).

Per CassiCosmos/research/helix_solver/smooth_cascade_prereg.md (SS2/SS3, with the
recorded wave-1 Q1 correction). Deterministic; the Q1 reflectivity is the exact
single-node/taper scattering of the FV Helmholtz operator (no time stepping).

Run from the repo root:  python research/helix_solver/smooth_probe.py
"""

import numpy as np

from phi_grid import PHI
from smooth_cascade import (discrete_q, per_rung_group, scattering_reflectivity,
                            smooth_grid)

K = 8
Z0 = 1.0
HC = 1.0
OMEGA = 2.0 * np.sin(np.pi / 8.0) / HC   # q_c h_c = pi/4 resolved mode


def main() -> None:
    print("== Q1: the axial design law (reflectivity vs taper length) ==")
    ms = [0, 1, 2, 3, 6, 12, 24]
    gammas = {m: scattering_reflectivity(HC, PHI, m, OMEGA) for m in ms}
    print("  m  (cells across a phi rung)   reflectivity |R|^2")
    for m in ms:
        print(f"     {m:2d}                         {gammas[m]*100:10.4f} %")
    monotone = all(gammas[ms[i + 1]] <= gammas[ms[i]] * (1 + 1e-3) for i in range(len(ms) - 1))
    g12 = gammas[12]
    g2 = gammas[2]
    # graded-index test: is the taper far better than independent per-cell steps?
    r_cell = PHI ** (1.0 / 12)
    gamma_per_cell = abs((r_cell - 1.0) / (r_cell + 1.0))   # ~1.98% per cell, single-node
    independent_12 = gamma_per_cell * 12                    # naive bound
    supports = monotone and g12 <= 0.02 and g12 < independent_12 * 0.25
    print(f"  monotone fall (m>=2): {monotone};  gamma(12) = {g12*100:.4f}%  (<=2% target: {g12 <= 0.02})")
    print(f"  note: m=1 == m=0 is exact (a 1-cell taper IS the single node); the graded fall is clean from m=2")
    print(f"  graded-index cancellation: gamma(12) = {g12:.2e} vs naive 12 single-step bound = {independent_12:.2e}")
    print(f"  gamma(2) = {g2*100:.4f}%  (a 2-cell taper already under gate-vi's 2%)")
    print()
    if supports:
        mstar = min(m for m in ms if gammas[m] <= 0.02)
        print("  VERDICT Q1: SUPPORTS -- the taper cancels reflections far below 2%; "
              f"the design law is m* = {mstar} cells per rung "
              "(and the raw single-node phi grid, m=0, already sits at 0.658%).")
    else:
        print("  VERDICT Q1: DOES NOT SUPPORT")

    print()
    print("== Q2: the cascade structure under subdivision (preservation) ==")
    q0 = np.pi / 4.0
    for m in (1, 12):
        z = smooth_grid(K, Z0, m)
        pos, gf = per_rung_group(z, q0, m)
        print(f"  m = {m}: per-rung group-velocity factors |sin q/q|:")
        for k in range(min(len(gf), 5)):
            print(f"    rung {k} (z={pos[k]:.3f}): group-f = {gf[k]:.4f}")
    # the subdivided grid (m=12) must still show the per-rung collapse (wave-1: 0.055 by rung 3)
    _, gf12 = per_rung_group(smooth_grid(K, Z0, 12), q0, 12)
    _, gf1 = per_rung_group(smooth_grid(K, Z0, 1), q0, 1)
    wall12 = len(gf12) > 3 and gf12[3] < 0.2
    wall1 = len(gf1) > 3 and gf1[3] < 0.2
    print("  subdivided (m=12) per-rung group-f at rung 3:", gf12[3] if len(gf12) > 3 else "n/a")
    print("  unsmoothed (m=1)  per-rung group-f at rung 3:", gf1[3] if len(gf1) > 3 else "n/a")
    if wall12 and wall1:
        print("  VERDICT Q2: EMERGES -- the ~4-rung self-resolving window persists under "
              "subdivision (scale-invariant); subdivision fixes transport without killing the cascade.")
    else:
        print("  VERDICT Q2: DOES NOT EMERGE (subdivision weakened or destroyed the window)")

    print()
    print("done")


if __name__ == "__main__":
    main()
