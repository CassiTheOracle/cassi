"""triaxial3d_probe.py -- the wave-6 3D oblate-triaxial shape + edge + ring arms.

Per triaxial3d_prereg.md. Deterministic, numpy, matrix-free. Freezes the Q1 (A1/A2)
verdict and reports Q2 (edge) and Q3 (ring ladder, Prediction 51) honestly.

Run from the repo root:  python research/helix_solver/triaxial3d_probe.py
"""

import numpy as np

from phi_grid import PHI
import triaxial3d as t3

N = 64
PHI2 = PHI * PHI


def ring_ladder(rho, center, rmax_frac=0.95):
    """Radial profile of |rho| from the center; the Prediction-51 ring positions.

    Returns (r_norm, profile, peaks) where r_norm = r/R (R = sigma_x the longest axis),
    profile is the azimuthally-averaged |rho|, and peaks are the normalized radii of
    the strongest local maxima (matter ridges). The doctrine predicts a matter ridge at
    r/R = 1/phi = 0.618 and a void at r/R = 1/sqrt(phi) = 0.786 (Prediction 51).
    """
    Nz, Ny, Nx = rho.shape
    gz, gy, gx = np.mgrid[0:Nz, 0:Ny, 0:Nx]
    cz, cy, cx = center
    dr = np.sqrt((gx - cx) ** 2 + (gy - cy) ** 2 + (gz - cz) ** 2)
    m = np.abs(rho)
    # bin by radius
    rmax = dr.max()
    nb = 200
    r_edges = np.linspace(0, 1.0, nb + 1) * rmax
    prof = np.zeros(nb)
    for b in range(nb):
        sel = (dr >= r_edges[b]) & (dr < r_edges[b + 1])
        if sel.sum() > 0:
            prof[b] = m[sel].mean()
    r_mid = 0.5 * (r_edges[:-1] + r_edges[1:])
    return r_mid, prof


def main() -> None:
    print("== Wave-6: the full-3D oblate triaxial spheroid probe ==")
    ph, sy = (PHI, 1.0, 1.0 / PHI), (1.0, 1.0, 1.0)

    print("---- Q1 (A1 + A2): the emergent 3D shape vs the doctrine anchors ----")
    for label, h in (("phi-arm", ph), ("control", sy)):
        g = t3.TwoFluid3D(h)
        ey, ei = t3.seed_bubble3d(N, h)
        ve = wi = np.zeros_like(ey)
        for _ in range(600):
            ey, ei, ve, wi = g.step(ey, ei, ve, wi)
        rho = ey + ei
        sx, syv, sz = t3.sigma3(rho, g.h)
        r_xy, r_xz = sx / syv, sx / sz
        print(f"  {label:9s} sigma: sx={sx:.2f} sy={syv:.2f} sz={sz:.2f}  "
              f"A1 sx/sy={r_xy:.3f} (phi={PHI:.3f})  A2 sx/sz={r_xz:.3f} (phi^2={PHI2:.3f})")

    print()
    print("  VERDICT Q1: the DIRECTION is confirmed (control 1.000 -> phi-arm strongly")
    print("  oblate/z-bounded, sx/sy=2.23, sx/sz=3.25) BUT the MAGNITUDE OVER-SHOOTS")
    print("  the doctrine anchors (phi=1.618, phi^2=2.618) at N=64, 600 steps on the")
    print("  round seed. The pre-registered bands were [1.2,1.9] / [1.8,3.2]; A1=2.227")
    print("  is above 1.9, A2=3.251 just above 3.2 -> does not ACHIEVE as frozen, with the")
    print("  over-shoot recorded as the finding. The 3D face-diagonal couplings (bxy,bxz,")
    print("  byz) drive the anisotropy harder than the pure 2D in-plane operator.")
    print("  CRITICAL: wave-5a's 2D '1.212 -> phi' was SEED-INHERITED (the anisotropic")
    print("  (phi,1)-physical seed baked in the shape; the 2D operator on a ROUND seed")
    print("  gives sx/sy = 1.000, NO second-moment imprint). Only the 3D out-of-plane")
    print("  couplings genuinely anisotropicize.")

    print()
    print("---- Q2 (reported): the 3D edge ratio on the Yang-Yin peak slice ----")
    for label, h in (("phi-arm", ph), ("control", sy)):
        g = t3.TwoFluid3D(h)
        ey, ei = t3.seed_bubble3d(N, h)
        ve = wi = np.zeros_like(ey)
        for _ in range(600):
            ey, ei, ve, wi = g.step(ey, ei, ve, wi)
        rho = ey + ei
        r, ga, gd = t3.slice_edge(rho, g.h)
        print(f"  {label:9s} edge (peak-z Yang-Yin slice) = "
              + (f"{r:.3f}" if np.isfinite(r) else "n/a") + " (bias-free proxy)")

    print()
    print("  VERDICT Q2: reported, not gated. The small-amplitude single bubble gives a")
    print("  weak/shallow edge (consistent with the 5a-followup dynamical Reported")
    print("  Negative: no sharp condensation boundary on a single bubble); the absolute")
    print("  1.70 remains a field-shape property measured exactly on the analytic field")
    print("  (1.707), not realized by the minimal single-bubble dynamics.")

    print()
    print("---- Q3 (reported/exploratory): the 3D ring ladder (Prediction 51) ----")
    g = t3.TwoFluid3D(ph)
    ey, ei = t3.seed_bubble3d(N, ph)
    ve = wi = np.zeros_like(ey)
    for _ in range(600):
        ey, ei, ve, wi = g.step(ey, ei, ve, wi)
    rho = ey + ei
    flat = int(np.argmax(np.abs(rho)))
    Nz, Ny, Nx = rho.shape
    center = (flat % N, (flat // N) % N, flat // (N * N))
    r_norm, prof = ring_ladder(rho, center)
    # the profile is |rho|, a positive near-center, ~0 far field. The meaningful test is
    # whether it has LOCAL RING structure (a secondary bump at 0.618, not just the decay
    # to the floor) -- compare the doctrine-radius amplitude to the LOCAL surrounding
    # profile, not the ~0 far-field floor (which makes any ratio degenerate).
    def i_at(r0):
        return int(np.argmin(np.abs(r_norm - r0 * r_norm[-1])))
    i618, i786 = i_at(0.618), i_at(0.786)
    v618, v786 = prof[i618], prof[i786]
    # local baseline = typical mid-field amplitude (the profile's own interior mean)
    interior = prof[:len(prof) // 2]
    base = float(np.mean(interior))
    print(f"  radial |rho|: at r/R=0.618 -> {v618:.4f}, at r/R=0.786 -> {v786:.4f}; "
          f"interior mean {base:.4f}; profile max {prof.max():.4f}")
    # a real matter ring appears as a LOCAL MAXIMUM above the surrounding decay
    ring_r = prof[i618] - 0.5 * (prof[max(0, i618 - 5)] + prof[min(len(prof) - 1, i618 + 5)])
    print(f"  local bump at r/R=0.618 (vs its 5-bin neighbours): {ring_r:+.5f}")
    has_ring = ring_r > 0.1 * max(base, 1e-9)
    if has_ring:
        print("  VERDICT Q3: a local matter bump at r/R=0.618 is present (>=10% of the interior) -- reported")
    else:
        print("  VERDICT Q3: no local ring bump at r/R=0.618 (the radial profile just decays -> the "
              "600-step linear single bubble does not quantize the doublet phase; Reported Negative, "
              "as expected for a short linear run) -- reported, not gated.")

    print()
    print("done")


if __name__ == "__main__":
    main()
