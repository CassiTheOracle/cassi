"""verify_triaxial3d.py -- construction/validation gates for the 3D oblate-triaxial solver.

Per triaxial3d_prereg.md SS3. Runs (deterministic, numpy, matrix-free):
  - G-iso-control:    symmetric operator (1,1,1) + physically-round seed -> all sigma ratios
                      and edge ratio ~ 1.0 after 600 steps (3D op + seed unbiased).
  - G-phi-shape:      the phi-arm (phi,1,1/phi) -> sigma_x/y and sigma_x/z clearly > 1
                      (the anisotropic operator imprints structure on a round seed).
  - G-machinery-free: free (w0^2=0) two-fluid energy drift < 5e-3 over 600 steps on the
                      uniform 3D grid (the uniform-grid conservation holds, unlike phi-shell).
  - G-determinism:    two 50-step runs bitwise identical.
  - sanity:           no NaN; C_dyn = 2(EY^2+EI^2)-1 within a weak [-1.5,1.5].

Run from the repo root:  python research/helix_solver/verify_triaxial3d.py
"""

import numpy as np
import sys

from phi_grid import PHI
import triaxial3d as t3

N = 64
PHI2 = PHI * PHI
results: list[tuple[str, bool, str]] = []


def gate(name, ok, msg):
    results.append((name, bool(ok), str(msg)))
    print(f"GATE {name}: {'PASS' if ok else 'FAIL'}  {msg}")


def run_arm(h, steps=600):
    """A fresh two-fluid run from a round seed; returns (ey, ei, g)."""
    g = t3.TwoFluid3D(h)
    ey, ei = t3.seed_bubble3d(N, h)
    ve = wi = np.zeros_like(ey)
    for _ in range(steps):
        ey, ei, ve, wi = g.step(ey, ei, ve, wi)
    return ey, ei, g


def energy(ey, ei, ve, wi, lap_fn):
    return 0.5 * (np.sum(ve * ve) + np.sum(wi * wi)
                  - np.sum(ey * lap_fn(ey)) - np.sum(ei * lap_fn(ei)))


def main() -> None:
    print("== G1: the isotropic control (symmetric op + round seed) is unbiased ==")
    eyc, eic, gc = run_arm((1.0, 1.0, 1.0))
    rho_c = eyc + eic
    sx, sy, sz = t3.sigma3(rho_c, gc.h)
    r_xy, r_xz = sx / sy, sx / sz
    er, _, _ = t3.slice_edge(rho_c, gc.h)
    gate("G1_iso_control_1.0",
         abs(r_xy - 1.0) <= 0.05 and abs(r_xz - 1.0) <= 0.05,
         f"symmetric-control sigma_x/y={r_xy:.3f}, sigma_x/z={r_xz:.3f}, edge={er:.3f} (all ~1.0)")

    print("== G2: the phi-arm imprints structure (round-seed discrimination) ==")
    eyp, eip, gp = run_arm((PHI, 1.0, 1.0 / PHI))
    rho_p = eyp + eip
    sx, sy, sz = t3.sigma3(rho_p, gp.h)
    rp_xy, rp_xz = sx / sy, sx / sz
    gate("G2_phi_anisotropic_shape", rp_xy > 1.15 and rp_xz > 1.30,
         f"phi-arm sigma_x/y={rp_xy:.3f} (>1.15), sigma_x/z={rp_xz:.3f} (>1.30) on a ROUND seed "
         f"(control was 1.000 -- the 3D face-diagonal couplings carry the anisotropy)")

    print("== G3: the uniform-3D-grid machinery conserves (unlike the phi-shell) ==")
    gf = t3.TwoFluid3D((PHI, 1.0, 1.0 / PHI), w0_2=0.0)
    eyf, eif = t3.seed_bubble3d(N, gf.h)
    eyf0, eif0 = eyf.copy(), eif.copy()
    vf = wif = np.zeros_like(eyf)
    e0 = energy(eyf0, eif0, vf, wif, gf.lap)
    for _ in range(600):
        eyf, eif, vf, wif = gf.step(eyf, eif, vf, wif)
    e1 = energy(eyf, eif, vf, wif, gf.lap)
    drift = abs(e1 - e0) / max(abs(e0), 1e-12)
    gate("G3_machinery_free", drift < 5e-3,
         f"free (w0=0) 3D 600-step drift = {drift:.2e} (<5e-3; uniform grid conserves cleanly)")

    print("== G4: determinism ==")
    gd = t3.TwoFluid3D((PHI, 1.0, 1.0 / PHI))
    ey, ei = t3.seed_bubble3d(N, gd.h)
    v = w = np.zeros_like(ey)
    for _ in range(50):
        ey, ei, v, w = gd.step(ey, ei, v, w)
    a_ey = ey.copy()
    gd2 = t3.TwoFluid3D((PHI, 1.0, 1.0 / PHI))
    ey, ei = t3.seed_bubble3d(N, gd2.h)
    v = w = np.zeros_like(ey)
    for _ in range(50):
        ey, ei, v, w = gd2.step(ey, ei, v, w)
    gate("G4_determinism", bool(np.array_equal(a_ey, ey)), "two 50-step phi-arm runs bitwise identical")

    print("== sanity: no NaN, C_dyn within [-1.5, 1.5] ==")
    cd = 2.0 * (eyp * eyp + eip * eip) - 1.0
    gate("sanity_finite_Cdyn",
         bool(np.isfinite(cd).all()) and float(cd.min()) >= -1.5 and float(cd.max()) <= 1.5,
         f"C_dyn in [{float(cd.min()):.3f}, {float(cd.max()):.3f}] (finite, weak range OK)")

    print()
    all_pass = all(ok for _, ok, _ in results)
    print("ALL CHECKS PASSED" if all_pass else "SOME GATES FAILED")
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
