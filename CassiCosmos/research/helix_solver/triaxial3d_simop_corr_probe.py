"""triaxial3d_simop_corr_probe.py -- wave 8: the sim-operator correction contrast.

Per triaxial3d_simop_corr_prereg.md. Deterministic, numpy, matrix-free. The one
decisive contrast: run the SAME physically-round seed and two-fluid dynamics on
(a) the SIM's actual operator h = (phi, 1, phi^2) (cell sizes from the box
extents, per cassi_two_fluid.glsl h_i = extent_i/(N/2)) and (b) the bubble-shaped
aspect h = (phi, 1, 1/phi) used by waves 6-7. If (a) is NOT z-bounded while (b)
is, waves 6-7's "oblate direction" was aspect-circular (baked in), and the sim's
recorded sigma_x/z=2.510 must come from a mechanism the operator alone lacks.

Run from the repo root:  python research/helix_solver/triaxial3d_simop_corr_probe.py
"""

import numpy as np

from phi_grid import PHI
import triaxial3d as t3

N = 64
SIM = (PHI, 1.0, PHI * PHI)      # the sim's box-extent cell sizes (phi,1,phi^2)
BUB = (PHI, 1.0, 1.0 / PHI)      # the waves-6/7 bubble-shaped aspect (phi,1,1/phi)
TRACE = (200, 600, 1200, 1800, 2400)


def trace(h):
    g = t3.TwoFluid3D(h)
    ey, ei = t3.seed_bubble3d(N, h)
    ve = wi = np.zeros_like(ey)
    p0 = float((ey + ei).max())
    out = []
    last = 0
    for target in TRACE:
        for _ in range(target - last):
            ey, ei, ve, wi = g.step(ey, ei, ve, wi)
        last = target
        rho = ey + ei
        sx, sy, sz = t3.sigma3(rho, g.h)
        out.append((target, rho.max() / p0, sx / sy, sx / sz))
    return out


def main() -> None:
    print("== wave 8: the sim-operator correction contrast ==")
    print(f"  doctrine: sigma_x/y -> phi={PHI:.3f}, sigma_x/z -> phi^2={PHI*PHI:.3f}; "
          f"sim record 1.422 / 2.510 (string_bubble_cascade.py)")
    sim = trace(SIM)
    bub = trace(BUB)
    print("  (a) SIM operator h=(phi,1,phi^2) — the sim's real cell sizes (fully periodic):")
    for t, pk, rxy, rxz in sim:
        print(f"      t={t:>5}: sigma_x/y={rxy:.3f}  sigma_x/z={rxz:.3f}  peak/p0={pk:.3f}")
    print("  (b) BUBBLE aspect h=(phi,1,1/phi) — waves 6-7 (baked-in oblate):")
    for t, pk, rxy, rxz in bub:
        print(f"      t={t:>5}: sigma_x/y={rxy:.3f}  sigma_x/z={rxz:.3f}  peak/p0={pk:.3f}")

    # --- the frozen verdict -----------------------------------------------------
    sim_final = sim[-1][3]
    bub_final_xy, bub_final_xz = bub[-1][2], bub[-1][3]
    print()
    if sim_final < 1.0:
        print(f"  VERDICT: CONFIRMED correction — the SIM operator (fully periodic, "
              f"(phi,1,phi^2)) yields a Z-STRETCHED bubble (sigma_x/z={sim_final:.3f} < 1), NOT "
              f"the doctrine's oblate z-bounded shape. The waves-6/7 'oblate direction confirmed' "
              f"(sigma_x/z={bub_final_xz:.3f}) was aspect-circular: the (phi,1,1/phi) operator "
              f"bakes the oblate shape in. The pure two-fluid anisotropic operator does NOT "
              f"produce the sim's recorded sigma_x/z=2.510; that record must arise from the "
              f"source feed / cluster geometry / gravity sector the operator alone lacks.")
    else:
        print(f"  VERDICT: sim operator DOES give z-bounded ({sim_final:.3f}); investigate further.")
    print("done")


if __name__ == "__main__":
    main()
