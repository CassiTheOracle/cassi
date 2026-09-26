"""verify_triaxial3d_feed.py -- construction/validation gates for the wave-9 feed/gravity probes.

Per triaxial3d_feed_prereg.md S3. Runs (deterministic, numpy, matrix-free):
  - G-seed-round:      the physically-round seed on (phi,1,phi^2) is unbiased (sigma ratios ~1.0)
                       and non-wrapping.
  - G-free-conservation: free (w0^2=0) two-fluid energy drift < 5e-3 over 2400 steps.
  - G-poisson:         the spectral Poisson solve inverts the exact Fourier mode (checks the k^2
                       grid, axis order, sign and k=0 nulling); div(grad(Phi)) ~ rho (checks the
                       gradient/divergence wiring); the gravity source is positive (attractive) at
                       a mass peak.
  - G-determinism:     Q1a, Q1b, Q2 and control each bitwise identical across two 100-step runs.
  - G-no-NaN:          all arms finite.
  - Sanity:            the pure control reproduces the wave-8 prolate anchor sigma_x/z in
                       [0.15, 0.60] at 2400 steps.
Prints ALL CHECKS PASSED on success.

Run from the repo root:  python research/helix_solver/verify_triaxial3d_feed.py
"""

import numpy as np

from phi_grid import PHI
import triaxial3d as t3
import triaxial3d_feed_probe as fp

N = 64
SIM = (PHI, 1.0, PHI * PHI)
results: list[tuple[str, bool, str]] = []


def gate(name, ok, msg):
    results.append((name, bool(ok), str(msg)))
    print(f"GATE {name}: {'PASS' if ok else 'FAIL'}  {msg}")


def energy(ey, ei, ve, wi, lap_fn):
    return 0.5 * (np.sum(ve * ve) + np.sum(wi * wi)
                  - np.sum(ey * lap_fn(ey)) - np.sum(ei * lap_fn(ei)))


def main() -> None:
    # ---- G1: seed round + non-wrapping -------------------------------------
    print("== G1: physically-round seed is unbiased on (phi,1,phi^2) ==")
    ey, ei = t3.seed_bubble3d(N, SIM)
    sx, sy, sz = t3.sigma3(ey + ei, SIM)
    r_xy, r_xz = sx / sy, sx / sz
    # non-wrapping: mass at the z-boundary (max |rho| on the z=0 face) ~ 0
    rho = np.abs(ey + ei)
    zedge = rho[:, :, 0].max()
    gate("G1_seed_round",
         0.95 <= r_xy <= 1.05 and 0.95 <= r_xz <= 1.05 and zedge < 1e-6 * rho.max(),
         f"seed sigma_x/y={r_xy:.4f}, sigma_x/z={r_xz:.4f} (~1.0), z-boundary mass {zedge:.2e}")

    # ---- G2: free-case energy conservation ---------------------------------
    print("== G2: free (w0=0) 2400-step drift < 5e-3 ==")
    gf = t3.TwoFluid3D(SIM, w0_2=0.0)
    eyf, eif = t3.seed_bubble3d(N, gf.h)
    eyf0, eif0 = eyf.copy(), eif.copy()
    vf = wif = np.zeros_like(eyf)
    e0 = energy(eyf0, eif0, vf, wif, gf.lap)
    for _ in range(2400):
        eyf, eif, vf, wif = gf.step(eyf, eif, vf, wif)
    e1 = energy(eyf, eif, vf, wif, gf.lap)
    drift = abs(e1 - e0) / max(abs(e0), 1e-12)
    gate("G2_free_conservation", drift < 5e-3,
         f"free 2400-step drift = {drift:.2e} (<5e-3)")

    # ---- G3: Poisson solve correctness -------------------------------------
    print("== G3: spectral Poisson solve + gradient/divergence wiring ==")
    solve = fp.make_poisson(fp.EXTENT)
    # Exact single-Fourier-mode inversion: nabla^2 Phi = rho, Phi = -rho/k^2.
    nx, ny, nz = 2, 1, 3
    i = np.arange(N)
    rho = (np.cos(2 * np.pi * nx * i / N)[:, None, None]
           * np.cos(2 * np.pi * ny * i / N)[None, :, None]
           * np.cos(2 * np.pi * nz * i / N)[None, None, :])
    kphys = [2 * np.pi * n / (2 * fp.EXTENT[a]) for a, n in ((0, nx), (1, ny), (2, nz))]
    k2 = sum(k * k for k in kphys)
    phi_expected = -rho / k2
    phi = solve(rho)
    err = np.max(np.abs(phi - phi_expected)) / max(np.max(np.abs(phi_expected)), 1e-300)
    mean0 = abs(phi.mean()) < 1e-12
    gate("G3a_poisson_invert", err < 1e-9 and mean0,
         f"single-mode inversion rel err = {err:.2e} (<1e-9), mean(Phi)={phi.mean():.2e}")

    # Gravity source sign: attractive (positive S_grav at a positive mass peak).
    gg = fp.GravityTwoFluid3D(SIM)
    sg = gg.gravity_source(ey, ei)          # ey, ei from the round seed (positive peak at center)
    pk = (ey + ei).argmax()
    s_peak = sg.flat[pk]
    # Exact discrete div(grad) on a single Fourier mode (verifies grad/div wiring: axes, h,
    # sign). For u = cos(2pi nx i/N) cos(2pi ny j/N) cos(2pi nz k/N), the central-difference
    # div(grad(u)) = -sum_i sin^2(2 pi n_i / N) / h_i^2  *  u  (exact to float precision).
    cx = np.cos(2 * np.pi * nx * i / N)
    cy = np.cos(2 * np.pi * ny * i / N)
    cz = np.cos(2 * np.pi * nz * i / N)
    u_mode = cx[:, None, None] * cy[None, :, None] * cz[None, None, :]
    sym = -(np.sin(2 * np.pi * nx / N) ** 2 / SIM[0] ** 2
            + np.sin(2 * np.pi * ny / N) ** 2 / SIM[1] ** 2
            + np.sin(2 * np.pi * nz / N) ** 2 / SIM[2] ** 2)
    gxm, gym, gzm = fp.grad_phi(u_mode, SIM)
    lap_m = fp.div_vec(gxm, gym, gzm, SIM)
    err_m = np.max(np.abs(lap_m - sym * u_mode)) / max(np.max(np.abs(sym * u_mode)), 1e-300)
    gate("G3b_grad_div_wiring", err_m < 1e-9,
         f"div(grad(u)) vs exact symbol rel err = {err_m:.2e} (<1e-9; wiring exact)")
    gate("G3c_gravity_attractive", s_peak > 0.0,
         f"S_grav at the seed peak = {s_peak:.3e} (>0 -> attractive)")

    # ---- G4: determinism ---------------------------------------------------
    print("== G4: determinism (100-step double runs, all arms) ==")
    rho_mass = fp.tsc_deposit()
    g_ey, g_ei = fp.make_gain_profiles()

    def run_control_100():
        g = t3.TwoFluid3D(SIM)
        ey, ei = t3.seed_bubble3d(N, SIM)
        v = w = np.zeros_like(ey)
        for _ in range(100):
            ey, ei, v, w = g.step(ey, ei, v, w)
        return ey, ei

    def run_feed_100(rho_mass=None, gain=None):
        g = t3.TwoFluid3D(SIM)
        ey, ei = t3.seed_bubble3d(N, SIM)
        v = w = np.zeros_like(ey)
        dt2 = g.dt * g.dt
        for _ in range(100):
            ey, ei, v, w = g.step(ey, ei, v, w)
            if rho_mass is not None:
                ey = ey + 0.001 * rho_mass * dt2
                ei = ei + 0.000707 * rho_mass * dt2
            if gain is not None:
                ey = ey + gain[0] * dt2
                ei = ei + gain[1] * dt2
        return ey, ei

    def run_gravity_100():
        g = fp.GravityTwoFluid3D(SIM)
        ey, ei = t3.seed_bubble3d(N, SIM)
        v = w = np.zeros_like(ey)
        for _ in range(100):
            ey, ei, v, w = g.step(ey, ei, v, w)
        return ey, ei

    det_ok = True
    det_msg = []
    for nm, fn in (("control", run_control_100),
                   ("Q1a", lambda: run_feed_100(rho_mass=rho_mass)),
                   ("Q1b", lambda: run_feed_100(gain=(g_ey, g_ei))),
                   ("Q2", run_gravity_100)):
        a_ey, a_ei = fn()
        b_ey, b_ei = fn()
        ok = bool(np.array_equal(a_ey, b_ey) and np.array_equal(a_ei, b_ei))
        det_ok = det_ok and ok
        det_msg.append(f"{nm}={'bitwise' if ok else 'DIFFERS'}")
    gate("G4_determinism", det_ok, ", ".join(det_msg))

    # ---- G5: no NaN + sanity ----------------------------------------------
    print("== G5: finite fields + wave-8 control anchor ==")
    # reuse the control/gravity/feed results for finiteness
    c_ey, c_ei = run_control_100()
    q1a_ey, q1a_ei = run_feed_100(rho_mass=rho_mass)
    q1b_ey, q1b_ei = run_feed_100(gain=(g_ey, g_ei))
    q2_ey, q2_ei = run_gravity_100()
    finite = all(np.isfinite(f).all() for f in
                 (c_ey, c_ei, q1a_ey, q1a_ei, q1b_ey, q1b_ei, q2_ey, q2_ei))
    gate("G5a_no_nan", finite, "all arms finite after 100 steps")

    # full-2400 control anchor (wave-8): sigma_x/z in [0.15, 0.60]
    g = t3.TwoFluid3D(SIM)
    ey, ei = t3.seed_bubble3d(N, SIM)
    v = w = np.zeros_like(ey)
    for _ in range(2400):
        ey, ei, v, w = g.step(ey, ei, v, w)
    rho = ey + ei
    sx, sy, sz = t3.sigma3(rho, SIM)
    rxz = sx / sz
    gate("G5b_control_anchor", 0.15 <= rxz <= 0.60,
         f"control sigma_x/z @2400 = {rxz:.3f} (wave-8 anchor 0.329; expect [0.15,0.60])")

    print()
    all_pass = all(ok for _, ok, _ in results)
    print("ALL CHECKS PASSED" if all_pass else "SOME GATES FAILED")
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
