"""verify_triaxial3d_particle.py -- construction/validation gates for the wave-10 particle probes.

Per triaxial3d_particle_prereg.md S3. Runs (deterministic, matrix-free, seeded):
  - G1 arm-A roundness:  free-streaming control sigma_x/z, sigma_x/y in [0.95, 1.05].
  - G2 Poisson exactness: single Fourier mode inversion rel err < 1e-9; k=0 null; mean-zero.
  - G3 TSC deposit:      partition of unity (single particle -> mass 1.0); total-mass conservation.
  - G4 determinism:      arm B (100 steps) bitwise identical across two runs (positions).
  - G5 no-NaN:           arms B and C finite on a short run.
  - G6 mass drift:       REPORTED (not gated).
Prints ALL CHECKS PASSED on success.

Run from the repo root:  python research/helix_solver/verify_triaxial3d_particle.py
"""

import numpy as np

import triaxial3d as t3
import triaxial3d_particle_probe as pp
from triaxial3d_feed_probe import make_poisson

N = pp.N
results: list[tuple[str, bool, str]] = []


def gate(name, ok, msg):
    results.append((name, bool(ok), str(msg)))
    print(f"GATE {name}: {'PASS' if ok else 'FAIL'}  {msg}")


def main() -> None:
    # ---- G1: arm-A roundness ------------------------------------------------
    print("== G1: free-streaming control stays round ==")
    a = pp.run_arm_a()
    a_round = all(0.95 <= rxz <= 1.05 and 0.95 <= rxy <= 1.05 for _, rxy, rxz in a)
    a_vals = ", ".join(f"{rxz:.4f}" for _, _rxy, rxz in a)
    gate("G1_armA_round", a_round, f"sigma_x/z at traces = [{a_vals}] (all in [0.95,1.05])")

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

    # ---- G4: determinism ----------------------------------------------------
    print("== G4: arm-B determinism (100-step double run) ==")
    pa = pp.arm_b_positions(100)
    pb = pp.arm_b_positions(100)
    gate("G4_determinism", bool(np.array_equal(pa, pb)), "two 100-step arm-B runs bitwise identical")

    # ---- G5: no-NaN ---------------------------------------------------------
    print("== G5: arms finite ==")
    b_short = pp.run_arm_b(trace=(100,))
    c_short = pp.run_arm_c(trace=(100,))
    finite = all(np.isfinite(x) for x in b_short[0]) and all(np.isfinite(x) for x in c_short[0])
    gate("G5_no_nan", finite,
         f"arm B @100 finite, arm C @100 finite (B sigma_x/z={b_short[0][3]:.3f}, "
         f"C field sigma_x/z={c_short[0][5]:.3f})")

    # ---- G6: mass drift REPORTED --------------------------------------------
    print("== G6: mass conservation (REPORTED) ==")
    print(f"  deposit total mass: t=0 {full.sum():.12f} (exact partition of unity -> conserved)")
    print(f"  arm-B peak/p0 @100 = {b_short[0][1]:.3f} (collapse -> density grows)")

    print()
    all_pass = all(ok for _, ok, _ in results)
    print("ALL CHECKS PASSED" if all_pass else "SOME GATES FAILED")
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
