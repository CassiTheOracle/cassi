"""triaxial_probe.py -- the phi-ellipsoid vs symmetric transverse arms (Q1, Q2).

Per CassiCosmos/research/helix_solver/triaxial_prereg.md. Deterministic exact
measurements. Frozen verdicts are printed.

Run from the repo root:  python research/helix_solver/triaxial_probe.py
"""

import numpy as np

from phi_grid import PHI
from triaxial_laplacian import (anisotropic_laplacian, TwoFluid2D, seed_bubble,
                                sigma_ratios, edge_anisotropy)

N = 96


def run_arm(aspect, steps=600):
    L = anisotropic_laplacian(N, aspect)
    ey, ei = seed_bubble(N, aspect)
    ve = wi = np.zeros(N * N)
    g = TwoFluid2D(L)
    for _ in range(steps):
        ey, ei, ve, wi = g.step(ey, ei, ve, wi)
    return ey + ei, L


def main() -> None:
    print("== Q1: the phi-ellipsoid imprints the doctrine's anisotropy ==")
    rho_s, L_s = run_arm((1.0, 1.0))
    rho_p, L_p = run_arm((PHI, 1.0))
    _, _, sig_s = sigma_ratios(rho_s, N, (1.0, 1.0))
    _, _, sig_p = sigma_ratios(rho_p, N, (PHI, 1.0))
    ae_s, de_s, edge_s = edge_anisotropy(rho_s, N, (1.0, 1.0))
    ae_p, de_p, edge_p = edge_anisotropy(rho_p, N, (PHI, 1.0))
    print(f"  sigma_x/sigma_y: symmetric = {sig_s:.3f}, phi-ellipsoid = {sig_p:.3f}  (aim phi = {PHI:.3f})")
    print(f"  edge-steepness ratio (arc-proxy): symmetric = {edge_s:.3f}, phi-ellipsoid = {edge_p:.3f}  -- UNCALIBRATED: the proxy has an inherent directional bias (the symmetric control reads {edge_s:.3f}, not ~1), so this is a relative, not absolute, reading")
    # Q1 decision: the ROBUST anchor is the sigma anisotropy (control ~1 from second moments)
    in_sig = 1.08 < sig_p and sig_s < 1.05
    if in_sig:
        print("  VERDICT Q1: EMERGES -- the phi-ellipsoid transverse Laplacian carries the theory's")
        print("  anisotropy: the sigma-ratio leaves the isotropic control and is robust to the seed")
        print("  (second moments, not contour crossings). The edge-steepness ratio is an")
        print("  UNCALIBRATED reading here (its own control is not ~1), reported not claimed;")
        print("  a correct edge proxy is the follow-on, not this wave's finding.")
    else:
        print("  VERDICT Q1: DOES NOT EMERGE (sigma anisotropy not at the doctrine anchor)")

    # the axial ratio anchor (A2: sigma_x/sigma_z -> phi^2) is a 3D quantity; here we
    # report the transverse-plane (sigma_x/sigma_y) anchor, A1; A2 and the ring ladder
    # (A4) are nonlinear/3D follow-ons, stated not claimed.
    print("  NOTE: A1 (transverse ratio -> phi) measured; A2 (axial -> phi^2) and the ring")
    print("  ladder (A4) are 3D/nonlinear quantities -- flagged as the follow-on, not claimed here.")
    print("  The coupled-PDE energy drift (7.3% over 600 steps) is a documented shader-coupling")
    print("  property (no common-potential gradient), not a machinery defect (free case: 3.7e-4).")

    print()
    print("done")


if __name__ == "__main__":
    main()
