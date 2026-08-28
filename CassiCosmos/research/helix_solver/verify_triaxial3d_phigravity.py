#!/usr/bin/env python3
"""
verify_triaxial3d_phigravity.py -- construction/validation gates for the wave-12b probe.

Per triaxial3d_phigravity_prereg.md S3. Runs (deterministic, matrix-free, seeded):
  G1 arm-B anchor:   wave-10 arm-B reproduction (g=1, pi/rho=1) -> sigma_x/z @2400 = 1.001 +/-0.005
                     and sigma_x/y = 1.012 +/-0.005 and peak/p0 = 21.980 +/-0.005.
  G2 Poisson exactness: single Fourier mode inversion rel err < 1e-9; mean(Phi) ~ 0.
  G3 TSC deposit:    partition of unity (single particle -> mass 1.0); total-mass conservation.
  G4 determinism:    arm C (phi^6) 100-step double run bitwise identical.
  G5 no-NaN:         arm B and arm C finite on a short run.
  G6 (REPORTED):     arm-C q/g range across the field at t=0.
Prints ALL CHECKS PASSED on success.

Run from repo root:  python research/helix_solver/verify_triaxial3d_phigravity.py
"""

import numpy as np

import triaxial3d_particle_probe as pp
import triaxial3d_phigravity_probe as pg
from triaxial3d_feed_probe import make_poisson

N = pp.N
results: list[tuple[str, bool, str]] = []


def gate(name, ok, msg):
    results.append((name, bool(ok), str(msg)))
    print(f"GATE {name}: {'PASS' if ok else 'FAIL'}  {msg}")


def main() -> None:
    # ---- G1: arm-B anchor (reproduces wave-10) ------------------------------
    print("== G1: arm-B anchor reproduces wave-10 ==")
    b = pp.run_arm_b()
    t, pk, rxy, rxz = b[-1]
    ok_xz = abs(rxz - 1.001) <= 0.005
    ok_xy = abs(rxy - 1.012) <= 0.005
    ok_pk = abs(pk - 21.980) <= 0.005
    gate("G1_armB_anchor", ok_xz and ok_xy and ok_pk,
         f"@2400 sigma_x/z={rxz:.3f} (1.001), sigma_x/y={rxy:.3f} (1.012), peak/p0={pk:.3f} (21.980)")

    # ---- G2: Poisson exactness ----------------------------------------------
    print("== G2: spectral Poisson solve exact on a single Fourier mode ==")
    solve = make_poisson(pp.EXTENT)
    nx, ny, nz = 2, 1, 3
    i = np.arange(N)
    rho = (np.cos(2 * np.pi * nx * i / N)[:, None, None]
           * np.cos(2 * np.pi * ny * i / N)[None, :, None]
           * np.cos(2 * np.pi * nz * i / N)[None, None, :])
    kphys = [2 * np.pi * n / (2 * pp.EXTENT[a]) for a, n in ((0, nx), (1, ny), (2, nz))]
    k2 = sum(k * k for k in kphys)
    phi_expected = -rho / k2
    phi = solve(rho)
    err = np.max(np.abs(phi - phi_expected)) / max(np.max(np.abs(phi_expected)), 1e-300)
    mean0 = abs(phi.mean()) < 1e-12
    gate("G2_poisson_exact", err < 1e-9 and mean0,
         f"single-mode inversion rel err = {err:.2e} (<1e-9), mean(Phi)={phi.mean():.2e}")

    # ---- G3: TSC deposit partition of unity ---------------------------------
    print("== G3: TSC deposit partition of unity + total mass ==")
    mass1 = np.array([1.0])
    r_c = pp.deposit(np.array([[32.0, 32.0, 32.0]]), mass1)
    r_f = pp.deposit(np.array([[32.3, 32.7, 32.2]]), mass1)
    pu = abs(r_c.sum() - 1.0) < 1e-12 and abs(r_f.sum() - 1.0) < 1e-12
    p, _v = pp.seed_particles()
    full = pp.deposit(pp.physical_to_cell(p), np.full(pp.NP, 1.0 / pp.NP))
    total_ok = abs(full.sum() - 1.0) < 1e-12
    gate("G3_tsc_partition", pu and total_ok,
         f"single-particle sum={r_c.sum():.6f} (center), {r_f.sum():.6f} (fractional); "
         f"full-cloud sum={full.sum():.6f} (total mass 1.0)")

    # ---- G4: determinism (arm C phi^6) --------------------------------------
    print("== G4: arm-C (phi^6) determinism (100-step double run) ==")
    pa = pg.arm_c_phi_positions(100)
    pb = pg.arm_c_phi_positions(100)
    gate("G4_determinism", bool(np.array_equal(pa, pb)), "two 100-step arm-C runs bitwise identical")

    # ---- G5: no-NaN ---------------------------------------------------------
    print("== G5: arms finite ==")
    b_short = pp.run_arm_b(trace=(100,))
    c_short = pg.run_arm_c_phi(trace=(100,))
    finite = all(np.isfinite(x) for x in b_short[0]) and all(np.isfinite(x) for x in c_short[0])
    gate("G5_no_nan", finite,
         f"arm B @100 finite, arm C @100 finite (B sigma_x/z={b_short[0][3]:.3f}, "
         f"C part sigma_x/z={c_short[0][3]:.3f}, C field sigma_x/z={c_short[0][4]:.3f})")

    # ---- G6: q/g range REPORTED ---------------------------------------------
    print("== G6: arm-C q/g range @t0 (REPORTED) ==")
    qmin, qmax, gmin, gmax = pg.arm_c_qg_range()
    print(f"  q in [{qmin:.4f}, {qmax:.4f}], g in [{gmin:.4f}, {gmax:.4f}] "
          f"(phi^6-1 = {pg.XI_MINUS_1:.4f})")

    print()
    all_pass = all(ok for _, ok, _ in results)
    print("ALL CHECKS PASSED" if all_pass else "SOME GATES FAILED")
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
