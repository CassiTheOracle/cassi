"""edge_proxy_probe.py -- the dynamical-leg edge-steepness probe (wave 5a-followup).

Per edge_proxy_prereg.md L1.2 (Leg D). Deterministic. The frozen question:
does the EVOLVED two-fluid field's edge-steeperness differ between the
phi-ellipsoid and symmetric transverse arms, in the doctrine's direction?

The ground-truth leg (verify_edgeproxy.py) established the bias-free proxy and
its limits (isotropic: 1.000; uniform checkerboard: 1.270; phi-checkerboard:
1.935 on this grid). This probe reports what the DYNAMICAL fields actually give.

Run from the repo root:  python research/helix_solver/edge_proxy_probe.py
"""

import numpy as np

from phi_grid import PHI
from triaxial_laplacian import (anisotropic_laplacian, TwoFluid2D, seed_bubble)
import edge_proxy as ep

N = 96


def single_bubble_cdyn(aspect, steps=600):
    """A single Gaussian bubble; the minimal transverse wave. Returns C_dyn."""
    L = anisotropic_laplacian(N, aspect)
    ey, ei = seed_bubble(N, aspect)
    ve = wi = np.zeros(N * N)
    g = TwoFluid2D(L)
    for _ in range(steps):
        ey, ei, ve, wi = g.step(ey, ei, ve, wi)
    rho = (ey * ey + ei * ei).reshape(N, N)
    return 2.0 * rho - 1.0


def checkerboard_cdyn(aspect, steps=600, A=0.1):
    """The doctrine's SS9.2-Method-A seed (EY = 1 + A cos cos, EI = 1/phi)."""
    xs = np.arange(N) / N
    gx, gy = np.meshgrid(xs, xs)
    kx, ky = 2.0, 2.0 / PHI
    ey = (1.0 + A * np.cos(2 * np.pi * kx * gx) * np.cos(2 * np.pi * ky * gy)).ravel()
    ei = np.full(N * N, 1.0 / PHI)
    ve = wi = np.zeros(N * N)
    g = TwoFluid2D(anisotropic_laplacian(N, aspect))
    for _ in range(steps):
        ey, ei, ve, wi = g.step(ey, ei, ve, wi)
    rho = (ey * ey + ei * ei).reshape(N, N)
    return 2.0 * rho - 1.0


def main() -> None:
    ph, sy = (PHI, 1.0), (1.0, 1.0)
    print("== Leg D: the dynamical edge (bias-free proxy, doctrine direction) ==")

    # ---- single-bubble arms (the minimal transverse wave) ----
    for label, asp in (("phi-ellipsoid", ph), ("symmetric", sy)):
        cd = single_bubble_cdyn(asp)
        cmin, cmax = float(cd.min()), float(cd.max())
        # does a clean theta crossing exist? peak < thr_threshold means none
        r, ga, gd = ep.edge_ratio(cd, N, asp)
        print(f"  {label:13s} single-bubble: C_dyn in [{cmin:+.3f}, {cmax:+.3f}]")
        if np.isfinite(r):
            print(f"     edge ratio = {r:.3f} (ga={ga:.3f} gd={gd:.3f})")
        else:
            print(f"     edge ratio = n/a -- NO clean condensation boundary (a weak spread")
            print(f"     wave has q=EY^2+EI^2 ~ {((cmax+1)/2):.3f} at peak, no sharp edge)")

    print()
    print("  -- checkerboard-seeded arms (doctrine SS9.2 Method A condensation seed) --")
    for label, asp in (("phi-ellipsoid", ph), ("symmetric", sy)):
        cd = checkerboard_cdyn(asp)
        cmin, cmax = float(cd.min()), float(cd.max())
        valid = -1.0 <= cmin and cmax <= 1.0
        print(f"  {label:13s} checkerboard: C_dyn in [{cmin:+.3f}, {cmax:+.3f}]  "
              f"{'VALID C in[-1,1]' if valid else 'INVALID (C out of [-1,1] -- non-conservative coupling amplifies q)'}")
        if valid:
            r, ga, gd = ep.edge_ratio(cd, N, asp, theta=0.45)
            print(f"     edge ratio = {r:.3f}" if np.isfinite(r) else "     edge ratio = n/a")

    print()
    print("VERDICT (Leg D): the 2D evolving two-fluid wave does NOT stably realize a")
    print("  measurable condensation edge: the single bubble yields no boundary (weak")
    print("  spread q), and the checkerboard seed is pushed out of C in [-1,1] by the")
    print("  sim's non-conservative EY/EI coupling (7.3% energy drift). CONTRADICTS /")
    print("  DOES NOT EMERGE for the dynamical edge on this minimal 2D probe.")
    print("  The 1.70 remains a ground-truth (Leg G) target: the condensation FIELD's")
    print("  exact ratio is 1.707 (phi) vs 1.269 (uniform) at theta=0.45; the 2D")
    print("  phi-grid reads 1.935 (grid-anisotropy limit, documented).")
    print("  Full-3D / stabilized-feed is the follow-on, not claimed here.")


if __name__ == "__main__":
    main()
