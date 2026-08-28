#!/usr/bin/env python3
"""
triaxial3d_phigravity_probe.py -- wave 12b (U3): full phi^6-modulated gravity.

Tests the LAST untested lever: the engine's coherence-modulated gravity
  a = -G_N * (pi/rho) * grad(g*Phi),  g = 1 + (phi^6 - 1)*q,
  q = rho^2/(rho^2 + phi^-2 + eps^2),  rho = EY+EI,  eps = EY - phi*EI
(cassi_nbody_gravity.glsl L7-17, L354-361, L431-466, L499-518). Wave-10 froze g=1.

Arms (per triaxial3d_phigravity_prereg.md):
  A  free-streaming control (wave-10 arm A, verbatim)
  B  wave-10 arm B (g=1, pi/rho=1) -- the calibration anchor
  C  full coupling: wave-10 arm C composition, but particle gravity uses the whole-product
     grad(g*Phi) with g = 1+(phi^6-1)*q sampled from the evolving field (UPDATED field -> S=g*Phi
     -> forward central-difference grad S -> trilinear sample -> *(-G_N*pi/rho)).
Asks whether the phi^6 chord factor imprints the field's transverse anisotropy (wave-10 true-frame
sigma_x/y ~= 1.580) onto the collapsing cloud, and whether it deforms the field bubble.

Measurement frame: TRUE engine frame (axis0=x=phi-extent, axis2=z=phi^2-extent); round=1.000.

Run from repo root:  python research/helix_solver/triaxial3d_phigravity_probe.py
"""

import numpy as np

from phi_grid import PHI
import triaxial3d as t3
from triaxial3d_feed_probe import make_poisson, N, SIM, EXTENT, G_N, DT, CLAMP_HI
import triaxial3d_particle_probe as p10

PHI_INV2 = 0.3819660112501051          # phi^-2 (shader PHI_INV2)
XI_MINUS_1 = PHI ** 6 - 1.0            # phi^6 - 1 (shader pc.xi - 1), ~16.9443
TRACE = (200, 600, 1200, 1800, 2400)
NP = p10.NP
H_ARR = np.array(SIM)                  # per-axis cell sizes (phi, 1, phi^2)


# ─── phi^6-modulated gravity (the law, whole-product) ──────────────────────
def q_field(ey, ei):
    """q = rho^2/(rho^2 + phi^-2 + eps^2), rho=EY+EI, eps=EY-phi*EI (shader L502)."""
    rho_f = ey + ei
    eps = ey - PHI * ei
    return rho_f ** 2 / (rho_f ** 2 + PHI_INV2 + eps ** 2)


def g_field(ey, ei):
    """g = 1 + (phi^6 - 1)*q (shader L517)."""
    return 1.0 + XI_MINUS_1 * q_field(ey, ei)


def grad_s_forward(S):
    """Forward central difference +grad S (shader grad_pass L463-465, 3-point)."""
    gx = (np.roll(S, -1, axis=0) - np.roll(S, 1, axis=0)) / (2.0 * H_ARR[0])
    gy = (np.roll(S, -1, axis=1) - np.roll(S, 1, axis=1)) / (2.0 * H_ARR[1])
    gz = (np.roll(S, -1, axis=2) - np.roll(S, 1, axis=2)) / (2.0 * H_ARR[2])
    return gx, gy, gz


def force_phigravity(p_target, phi, ey, ei, g_n=G_N):
    """a = -G_N * (pi/rho) * grad(g*Phi). S = g*Phi built whole on the grid from the
    (updated) field; grad S via forward central differences; trilinear-sampled at p_target."""
    S = g_field(ey, ei) * phi
    gsx, gsy, gsz = grad_s_forward(S)
    cell = p10.physical_to_cell(p_target)
    ax = p10.trilinear_sample(gsx, cell)
    ay = p10.trilinear_sample(gsy, cell)
    az = p10.trilinear_sample(gsz, cell)
    pi = p10.pi_over_rho_field(ey, ei, cell)
    return -g_n * pi[:, None] * np.stack([ax, ay, az], axis=1)


# ─── Arm runners ────────────────────────────────────────────────────────────
def run_arm_c_phi(trace=TRACE, g_n=G_N):
    """Full composition with phi^6-modulated g (whole-product grad(g*Phi))."""
    solve = make_poisson(EXTENT)
    p, v = p10.seed_particles()
    mass = np.full(NP, 1.0 / NP)

    gf = t3.TwoFluid3D(SIM)
    ey, ei = t3.seed_bubble3d(N, SIM)
    vey = vei = np.zeros_like(ey)
    dt2 = gf.dt * gf.dt

    # warm-up (engine order: deposit -> Poisson -> PDE -> coupling -> force)
    cell = p10.physical_to_cell(p)
    rho = p10.deposit(cell, mass)
    peak0 = float(rho.max())
    phi = solve(rho)
    ey, ei, vey, vei = gf.step(ey, ei, vey, vei)
    ey = ey + 0.001 * rho * dt2
    ei = ei + 0.000707 * rho * dt2
    acc = force_phigravity(p, phi, ey, ei, g_n)

    out = []
    last = 0
    for target in trace:
        for _ in range(target - last):
            cell = p10.physical_to_cell(p)
            rho = p10.deposit(cell, mass)
            phi = solve(rho)
            ey, ei, vey, vei = gf.step(ey, ei, vey, vei)
            ey = ey + 0.001 * rho * dt2
            ei = ei + 0.000707 * rho * dt2
            v_half = v + acc * (0.5 * DT)
            p_new = p10.wrap_physical(p + v_half * DT)
            a_new = force_phigravity(p_new, phi, ey, ei, g_n)
            v_new = v_half + a_new * (0.5 * DT)
            p, v, acc = p_new, v_new, a_new
        last = target
        sx, sy, sz = p10.particle_sigma(p)
        fpx, fpy, fpz = p10.field_sigma_physical(ey + ei)
        s3x, s3y, s3z = t3.sigma3(ey + ei, SIM)
        peak = float(p10.deposit(p10.physical_to_cell(p), mass).max())
        out.append((target, peak / peak0, sx / sy, sx / sz,
                    fpx / fpz, fpx / fpy, s3x / s3z))
    return out


def arm_c_phi_positions(nsteps):
    """Final particle positions after nsteps of phi^6-modulated arm C (determinism gate)."""
    solve = make_poisson(EXTENT)
    p, v = p10.seed_particles()
    mass = np.full(NP, 1.0 / NP)
    gf = t3.TwoFluid3D(SIM)
    ey, ei = t3.seed_bubble3d(N, SIM)
    vey = vei = np.zeros_like(ey)
    dt2 = gf.dt * gf.dt
    cell = p10.physical_to_cell(p)
    rho = p10.deposit(cell, mass)
    phi = solve(rho)
    ey, ei, vey, vei = gf.step(ey, ei, vey, vei)
    ey = ey + 0.001 * rho * dt2
    ei = ei + 0.000707 * rho * dt2
    acc = force_phigravity(p, phi, ey, ei, G_N)
    for _ in range(nsteps):
        cell = p10.physical_to_cell(p)
        rho = p10.deposit(cell, mass)
        phi = solve(rho)
        ey, ei, vey, vei = gf.step(ey, ei, vey, vei)
        ey = ey + 0.001 * rho * dt2
        ei = ei + 0.000707 * rho * dt2
        v_half = v + acc * (0.5 * DT)
        p_new = p10.wrap_physical(p + v_half * DT)
        a_new = force_phigravity(p_new, phi, ey, ei, G_N)
        v_new = v_half + a_new * (0.5 * DT)
        p, v, acc = p_new, v_new, a_new
    return p


def arm_c_qg_range():
    """q and g range across the field at t=0 (REPORTED diagnostic)."""
    ey, ei = t3.seed_bubble3d(N, SIM)
    q = q_field(ey, ei)
    g = g_field(ey, ei)
    return float(q.min()), float(q.max()), float(g.min()), float(g.max())


# ─── Verdict printing ───────────────────────────────────────────────────────
def main() -> None:
    print("== wave 12b (U3): phi^6-modulated gravity on the sim's (phi,1,phi^2) box ==")
    print(f"  law: a = -G_N*(pi/rho)*grad(g*Phi), g=1+(phi^6-1)*q, q=rho^2/(rho^2+phi^-2+eps^2)")
    print(f"  phi^6-1 = {XI_MINUS_1:.4f}  (up to 18x gravity in high-q cells)")
    print(f"  pins: N={N}, N_p={NP}, sigma0={p10.SIGMA0:.2f}, G_N={G_N}, dt={DT}, 2400 steps, "
          f"rng_seed={p10.RNG_SEED}")

    qmin, qmax, gmin, gmax = arm_c_qg_range()
    print(f"  (diagnostic) field q range @t0 = [{qmin:.4f}, {qmax:.4f}], g range = [{gmin:.4f}, {gmax:.4f}]")

    a = p10.run_arm_a()
    print("\n  (A) free-streaming control (no gravity; must stay round):")
    for t, rxy, rxz in a:
        print(f"      t={t:>5}: sigma_x/y={rxy:.3f}  sigma_x/z={rxz:.3f}")
    a_round = all(0.95 <= rxz <= 1.05 and 0.95 <= rxy <= 1.05 for _, rxy, rxz in a)

    print(f"\n  (B) wave-10 arm-B reproduction (g=1, pi/rho=1):")
    b = p10.run_arm_b()
    for t, pk, rxy, rxz in b:
        print(f"      t={t:>5}: sigma_x/y={rxy:.3f}  sigma_x/z={rxz:.3f}  peak/p0={pk:.3f}")

    base = p10.run_field_baseline()
    print("\n  (field baseline) wave-9 field-only control (no particles):")
    for t, f_xz, f_xy, s3_xz in base:
        print(f"      t={t:>5}: true sigma_x/z={f_xz:.3f}  true sigma_x/y={f_xy:.3f}  sigma3_x/z={s3_xz:.3f}")

    print(f"\n  (C) FULL phi^6-modulated gravity (g=1+(phi^6-1)*q; whole-product grad(g*Phi)):")
    c = run_arm_c_phi()
    for t, pk, rxy, rxz, f_xz, f_xy, s3_xz in c:
        print(f"      t={t:>5}: part sigma_x/y={rxy:.3f}  part sigma_x/z={rxz:.3f}  peak/p0={pk:.3f}  "
              f"| field sigma_x/z={f_xz:.3f} (sigma3={s3_xz:.3f})  field sigma_x/y={f_xy:.3f}")

    print()
    print("== frozen verdicts (primary statistic sigma_x/z @ t=2400) ==")
    a_xz = a[-1][2]
    print(f"  (A) control sigma_x/z @2400 = {a_xz:.3f} (round guard: {'PASS' if a_round else 'FAIL'})")

    b_xz = b[-1][3]
    b_anchor_ok = abs(b_xz - 1.001) <= 0.005 and abs(b[-1][2] - 1.012) <= 0.005 and abs(b[-1][1] - 21.980) <= 0.005
    print(f"  (B) anchor sigma_x/z @2400 = {b_xz:.3f} (sigma_x/y={b[-1][2]:.3f}, peak/p0={b[-1][1]:.3f}) "
          f"-> {'REPRODUCED wave-10' if b_anchor_ok else 'ANCHOR MISMATCH'}")

    c_xz = c[-1][3]      # arm-C particle sigma_x/z
    c_field_xz = c[-1][4]  # arm-C field sigma_x/z (true frame)
    base_xz = base[-1][1]

    if not (np.isfinite(c_xz) and np.isfinite(c_field_xz)):
        verdict = "INCONCLUSIVE (non-finite field/particle state)"
    elif not a_round:
        verdict = "INCONCLUSIVE (control failed the roundness guard)"
    elif not b_anchor_ok:
        verdict = "INCONCLUSIVE (arm-B anchor did not reproduce wave-10)"
    elif c_xz >= 1.05 or c_field_xz >= 1.218:
        which = []
        if c_xz >= 1.05:
            which.append(f"particle sigma_x/z={c_xz:.3f} >= 1.05")
        if c_field_xz >= 1.218:
            which.append(f"field sigma_x/z={c_field_xz:.3f} >= 1.218")
        verdict = "SUPPORTS (" + "; ".join(which) + ")"
    else:
        verdict = (f"CONTRADICTS (particle sigma_x/z={c_xz:.3f} < 1.05 within noise of 1.00 AND "
                   f"field sigma_x/z={c_field_xz:.3f} < 1.218 unchanged from baseline {base_xz:.3f})")

    print(f"  C: particle sigma_x/z @2400 = {c_xz:.3f}  (wave-10 baseline 1.00; threshold 1.05)")
    print(f"     field sigma_x/z @2400 = {c_field_xz:.3f}  (true frame; baseline {base_xz:.3f}; "
          f"5% rise threshold {1.160*1.05:.3f})")
    print(f"     C particle peak/p0 @2400 = {c[-1][1]:.3f}  (vs wave-10 arm C = 1.616)")
    print(f"  OVERALL: {verdict}")
    print("done")


if __name__ == "__main__":
    main()
