#!/usr/bin/env python3
"""
cascade_repro_probe.py — wave 11: is the oblate record real in its own source?

Deterministic, numpy-only reimplementation of the damped-wave two-fluid PDE in
CassiTheory/visual-explainers/string_bubble_cascade.py (read-only source), plus the
pre-registered honesty arms (see cascade_repro_prereg.md). No RNG in the physics; the only
RNG is the explicit seeded IC perturbation for Arm 4.

Arms:
  0  faithful reproduction (phi-weighted coherence estimator, seeded sigma_x = PHI*sigma_y)
  1  estimator honesty: energy-perturbation (r-neutral) extents, same dynamics/IC
  2  IC honesty: transverse envelope made isotropic (sigma_x = sigma_y)
  3  label honesty: ratios at step ~1100 (docs) vs 3500/15000 (code's actual idx_bubble)
  4  ensemble: 4 seeded IC perturbations of the emergent sigma_x/z at the record step

Measurement step is 1100 (amendment b): the oblate record is a transient there; the code's
idx_bubble (3500 default / 15000 long-run) never contains it.
"""

import os
import sys

import numpy as np

# ─── Constants (byte-copied from the source) ────────────────────────────────
PHI = (1 + np.sqrt(5)) / 2
SPIRAL_PITCH = 2 * np.pi / np.log(PHI)  # ~13.06 rad per e-fold

N = 64
L = 12.0
dx = L / N
dt = 0.006
save_interval = 100

c0 = 0.6
alpha_c2 = 0.15
gamma = 0.02
lam = 0.1

E0 = 1.0
A_amp = 0.3
sigma_z = L / 8
sigma_r = L / 8
z_max = L / 4
eps5 = 0.05
ell0 = L / 4

A_ring_per = 0.15
r0_ring = 0.8
sigma_ring = 0.4
sigma_z_ring = 1.5
n_strings = 5

# Frozen arm-4 perturbation amplitude (relative to the wave amplitude A_amp)
NOISE_EPS = 1e-3
ENSEMBLE_SEEDS = [42, 43, 44, 45]

# Record / label steps (amendment b): the oblate transient lives at ~1100.
RECORD_STEP = 1100          # docs' cited step (where sigma_x/z ~= 2.5 transiently appears)
DEFAULT_FINAL = 3500        # default run's final step == code's idx_bubble (argmin|snap-15000|)
LONG_STEP = 15000           # the code's literal idx_bubble target, reachable only at ~15k steps

# Frozen thresholds (cascade_repro_prereg.md, amendment b)
REPRO_XY_LO, REPRO_XY_HI = 1.3, 1.9     # coh sigma_x/y @1100 ~ 1.59 (phi ballpark)
REPRO_XZ_LO, REPRO_XZ_HI = 2.0, 3.0     # coh sigma_x/z @1100 ~ 2.50 (the oblate transient)
ENERGY_ROUND = 1.1                      # r-neutral energy must stay ~1.0 (round)
SURVIVE_XZ = 1.8                        # "still oblate"
COLLAPSE_XZ = 1.5                       # "dropped toward round"
COLLAPSE_XY = 1.15                      # seeded transverse phi gone
SEED_CV_MAX = 0.3                       # Arm-4 stability


# ─── Grid ────────────────────────────────────────────────────────────────────
def make_grid():
    x = np.linspace(-L / 2, L / 2, N)
    y = np.linspace(-L / 2, L / 2, N)
    z = np.linspace(-L / 2, L / 2, N)
    X, Y, Z = np.meshgrid(x, y, z, indexing="ij")  # axes: 0=x, 1=y, 2=z
    z_flat = z
    theta_z = SPIRAL_PITCH * np.log(np.maximum((z_flat + L / 2 + dx) / ell0, 1e-6))
    theta_3d = theta_z[np.newaxis, np.newaxis, :]
    z_N = -L / 4
    z_S = +L / 4
    G_N = np.exp(-(Z - z_N) ** 2 / (2 * sigma_z ** 2))
    G_S = np.exp(-(Z - z_S) ** 2 / (2 * sigma_z ** 2))
    return X, Y, Z, theta_3d, G_N, G_S


def init_fields(X, Y, Z, theta_3d, G_N, G_S, transverse_phi_factor=PHI, noise_seed=None):
    """Port of the source IC. transverse_phi_factor=PHI is faithful; =1.0 is Arm 2."""
    sigma0_z = np.full(N, sigma_r)
    sigma_x_z = transverse_phi_factor * sigma0_z
    sigma_y_z = sigma0_z
    sigma_x_3d = sigma_x_z[np.newaxis, np.newaxis, :]
    sigma_y_3d = sigma_y_z[np.newaxis, np.newaxis, :]

    EY = np.full((N, N, N), E0)
    EI = np.full((N, N, N), E0)
    VY = np.zeros((N, N, N))
    VI = np.zeros((N, N, N))

    for bx, by in [(0.0, 0.0)]:
        Xb = X - bx
        Yb = Y - by
        Rb = np.sqrt(Xb ** 2 + Yb ** 2)
        theta_b = np.arctan2(Yb, Xb)

        T_env_b = np.exp(-(Xb ** 2 / (2 * sigma_x_3d ** 2 + 1e-12)
                           + Yb ** 2 / (2 * sigma_y_3d ** 2 + 1e-12)))
        T_5fold_b = 1.0 + eps5 * np.cos(5.0 * theta_b + theta_3d)
        T_b = T_env_b * T_5fold_b

        EY_fwd_b = A_amp * G_N * T_b * np.cos(theta_3d + 5 * theta_b)
        EI_fwd_b = A_amp * G_N * T_b * np.cos(theta_3d + 5 * theta_b + np.pi / 2)
        EY_anti_b = A_amp * G_S * T_b * np.cos(theta_3d + 5 * theta_b + np.pi)
        EI_anti_b = A_amp * G_S * T_b * np.cos(theta_3d + 5 * theta_b + np.pi + np.pi / 2)

        EY += EY_fwd_b + EY_anti_b
        EI += EI_fwd_b + EI_anti_b

        dEY_fwd_dz = np.gradient(EY_fwd_b, dx, axis=2)
        dEI_fwd_dz = np.gradient(EI_fwd_b, dx, axis=2)
        dEY_anti_dz = np.gradient(EY_anti_b, dx, axis=2)
        dEI_anti_dz = np.gradient(EI_anti_b, dx, axis=2)
        VY += -c0 * dEY_fwd_dz + c0 * dEY_anti_dz
        VI += -c0 * dEI_fwd_dz + c0 * dEI_anti_dz

        for i in range(n_strings):
            theta_i = 2 * np.pi * i / n_strings
            dtheta = np.arctan2(np.sin(theta_b - theta_i), np.cos(theta_b - theta_i))
            ang_env = np.exp(-dtheta ** 2 / (2 * (np.pi / 7) ** 2))
            rad_env = np.exp(-(Rb - r0_ring) ** 2 / (2 * sigma_ring ** 2))
            z_env = np.exp(-Z ** 2 / (2 * sigma_z_ring ** 2))
            ring = A_ring_per * rad_env * z_env * ang_env

            EY_ring = ring * np.cos(5 * theta_b + theta_3d)
            EI_ring = ring * np.cos(5 * theta_b + theta_3d + np.pi / 2)
            EY += EY_ring
            EI += EI_ring

            r_safe = Rb + 1e-12
            ur_x = Xb / r_safe
            ur_y = Yb / r_safe
            dEY_dr = (ur_x * np.gradient(EY_ring, dx, axis=0)
                      + ur_y * np.gradient(EY_ring, dx, axis=1))
            dEI_dr = (ur_x * np.gradient(EI_ring, dx, axis=0)
                      + ur_y * np.gradient(EI_ring, dx, axis=1))
            VY += -c0 * dEY_dr
            VI += -c0 * dEI_dr

    if noise_seed is not None:
        rng = np.random.default_rng(noise_seed)
        EY = EY + rng.normal(0.0, NOISE_EPS * A_amp, (N, N, N))
        EI = EI + rng.normal(0.0, NOISE_EPS * A_amp, (N, N, N))

    mass0 = EY.sum() + EI.sum()
    return EY, EI, VY, VI, mass0


# ─── PDE (faithful port) ─────────────────────────────────────────────────────
def c2_field(EY, EI):
    r = EY / (EI + 1e-12)
    eps_r = np.abs(r - PHI)
    return c0 ** 2 * eps_r / (alpha_c2 + eps_r)


def div_c2_grad_both(fY, fI, c2):
    """nabla.(c^2 nabla f) for both fields; half-point face averaging, 3D periodic."""
    rY = np.zeros_like(fY)
    rI = np.zeros_like(fI)
    for ax in range(3):
        c2_face = 0.5 * (c2 + np.roll(c2, -1, axis=ax))
        fluxY = c2_face * (np.roll(fY, -1, axis=ax) - fY)
        fluxI = c2_face * (np.roll(fI, -1, axis=ax) - fI)
        rY += fluxY - np.roll(fluxY, 1, axis=ax)
        rI += fluxI - np.roll(fluxI, 1, axis=ax)
    rY /= dx * dx
    rI /= dx * dx
    return rY, rI


def rhs(EY, EI, VY, VI):
    c2 = c2_field(EY, EI)
    lapY, lapI = div_c2_grad_both(EY, EI, c2)
    conv = lam * (EY - PHI * EI)
    return VY, lapY - gamma * VY - conv, VI, lapI - gamma * VI + conv


def rk4_step(EY, EI, VY, VI, mass0):
    dEY1, dVY1, dEI1, dVI1 = rhs(EY, EI, VY, VI)
    dEY2, dVY2, dEI2, dVI2 = rhs(EY + 0.5 * dt * dEY1, EI + 0.5 * dt * dEI1,
                                  VY + 0.5 * dt * dVY1, VI + 0.5 * dt * dVI1)
    dEY3, dVY3, dEI3, dVI3 = rhs(EY + 0.5 * dt * dEY2, EI + 0.5 * dt * dEI2,
                                  VY + 0.5 * dt * dVY2, VI + 0.5 * dt * dVI2)
    dEY4, dVY4, dEI4, dVI4 = rhs(EY + dt * dEY3, EI + dt * dEI3,
                                  VY + dt * dVY3, VI + dt * dVI3)

    EY_new = EY + (dt / 6.0) * (dEY1 + 2 * dEY2 + 2 * dEY3 + dEY4)
    EI_new = EI + (dt / 6.0) * (dEI1 + 2 * dEI2 + 2 * dEI3 + dEI4)
    VY_new = VY + (dt / 6.0) * (dVY1 + 2 * dVY2 + 2 * dVY3 + dVY4)
    VI_new = VI + (dt / 6.0) * (dVI1 + 2 * dVI2 + 2 * dVI3 + dVI4)

    total = EY_new.sum() + EI_new.sum()
    scale = mass0 / max(total, 1e-12)
    EY_new *= scale
    EI_new *= scale
    return EY_new, EI_new, VY_new, VI_new


# ─── Estimators ──────────────────────────────────────────────────────────────
def coherence_extents(EY, EI, X, Y, Z):
    """phi-weighted (faithful): RMS extent of the r~=phi coherence shell."""
    r = EY / (EI + 1e-12)
    weight = np.exp(-(r - PHI) ** 2 / (2 * 0.08 ** 2))
    total = weight.sum() + 1e-12
    xc = (X * weight).sum() / total
    yc = (Y * weight).sum() / total
    zc = (Z * weight).sum() / total
    sx = np.sqrt(((X - xc) ** 2 * weight).sum() / total)
    sy = np.sqrt(((Y - yc) ** 2 * weight).sum() / total)
    sz = np.sqrt(((Z - zc) ** 2 * weight).sum() / total)
    return sx, sy, sz


def energy_extents(EY, EI, X, Y, Z):
    """r-neutral: RMS extent of the energy perturbation (source rms_extents)."""
    energy_pert = (EY - E0) ** 2 + (EI - E0) ** 2
    total = energy_pert.sum() + 1e-12
    xc = (X * energy_pert).sum() / total
    yc = (Y * energy_pert).sum() / total
    zc = (Z * energy_pert).sum() / total
    sx = np.sqrt(((X - xc) ** 2 * energy_pert).sum() / total)
    sy = np.sqrt(((Y - yc) ** 2 * energy_pert).sum() / total)
    sz = np.sqrt(((Z - zc) ** 2 * energy_pert).sum() / total)
    return sx, sy, sz


# ─── Evolution ───────────────────────────────────────────────────────────────
def evolve(EY, EI, VY, VI, mass0, X, Y, Z, n_steps):
    """Evolve n_steps, recording coh+energy extents every save_interval."""
    snapshots = []
    csx, csy, csz = coherence_extents(EY, EI, X, Y, Z)
    esx, esy, esz = energy_extents(EY, EI, X, Y, Z)
    snapshots.append((0, csx, csy, csz, esx, esy, esz))
    for step in range(1, n_steps + 1):
        EY, EI, VY, VI = rk4_step(EY, EI, VY, VI, mass0)
        if step % save_interval == 0 or step == n_steps:
            csx, csy, csz = coherence_extents(EY, EI, X, Y, Z)
            esx, esy, esz = energy_extents(EY, EI, X, Y, Z)
            snapshots.append((step, csx, csy, csz, esx, esy, esz))
    return snapshots


def snap_at(snapshots, target_step):
    """Closest snapshot to target_step (matching the source's argmin over snapshots)."""
    ss = np.array([s[0] for s in snapshots])
    idx = np.argmin(np.abs(ss - target_step))
    return snapshots[idx]


def _ratios(snap):
    _, csx, csy, csz, esx, esy, esz = snap
    return {
        "step": snap[0],
        "coh_xy": csx / max(csy, 1e-12),
        "coh_xz": csx / max(csz, 1e-12),
        "en_xy": esx / max(esy, 1e-12),
        "en_xz": esx / max(esz, 1e-12),
    }


# ─── Arms ────────────────────────────────────────────────────────────────────
def arm_0_and_1_and_3():
    """Faithful run to LONG_STEP; gives the record (1100), the default final (3500),
    and the code's literal idx_bubble target (15000) all from one trajectory."""
    X, Y, Z, theta_3d, G_N, G_S = make_grid()
    EY, EI, VY, VI, mass0 = init_fields(X, Y, Z, theta_3d, G_N, G_S, PHI)
    snaps = evolve(EY, EI, VY, VI, mass0, X, Y, Z, LONG_STEP)

    at_1100 = _ratios(snap_at(snaps, RECORD_STEP))
    at_3500 = _ratios(snap_at(snaps, DEFAULT_FINAL))
    at_15000 = _ratios(snaps[-1])

    # argmax of coh_xz over the trajectory (where the transient peaks)
    best = (0.0, 0)
    for s in snaps:
        r = _ratios(s)
        if r["coh_xz"] > best[0]:
            best = (r["coh_xz"], s[0])
    return {
        "snaps": snaps,
        "at_1100": at_1100, "at_3500": at_3500, "at_15000": at_15000,
        "peak_xz": best[0], "peak_step": best[1],
    }


def arm_2():
    """IC honesty: transverse envelope isotropic (sigma_x = sigma_y). Run to RECORD_STEP."""
    X, Y, Z, theta_3d, G_N, G_S = make_grid()
    EY, EI, VY, VI, mass0 = init_fields(X, Y, Z, theta_3d, G_N, G_S, 1.0)
    snaps = evolve(EY, EI, VY, VI, mass0, X, Y, Z, RECORD_STEP)
    return _ratios(snaps[-1])


def arm_4():
    """Ensemble: 4 seeded IC perturbations, coh sigma_x/z at RECORD_STEP."""
    X, Y, Z, theta_3d, G_N, G_S = make_grid()
    results = []
    for seed in ENSEMBLE_SEEDS:
        EY, EI, VY, VI, mass0 = init_fields(X, Y, Z, theta_3d, G_N, G_S, PHI, noise_seed=seed)
        snaps = evolve(EY, EI, VY, VI, mass0, X, Y, Z, RECORD_STEP)
        r = _ratios(snaps[-1])
        results.append((seed, r["coh_xz"]))
    return results


# ─── Verdict printing ────────────────────────────────────────────────────────
def main():
    print("=== wave-11 cascade-repro probe ===")
    print(f"  PHI={PHI:.6f}  N={N}  L={L}  dx={dx:.4f}  dt={dt}  record step={RECORD_STEP}")
    print()

    r0 = arm_0_and_1_and_3()
    a1100, a3500, a15000 = r0["at_1100"], r0["at_3500"], r0["at_15000"]

    print("  (Arm 0) faithful reproduction (phi-weighted coherence estimator):")
    print(f"    coh sigma_x/sigma_y @{RECORD_STEP} = {a1100['coh_xy']:.3f}  (docs ~1.422, target phi={PHI:.3f})")
    print(f"    coh sigma_x/sigma_z @{RECORD_STEP} = {a1100['coh_xz']:.3f}  (docs ~2.510, target phi^2={PHI**2:.3f})")
    print(f"    transient argmax coh sigma_x/z = {r0['peak_xz']:.3f} at step {r0['peak_step']}")
    rep_ok = (REPRO_XY_LO <= a1100["coh_xy"] <= REPRO_XY_HI) and (REPRO_XZ_LO <= a1100["coh_xz"] <= REPRO_XZ_HI)
    print(f"    reproduction within tolerance: {'YES' if rep_ok else 'NO'}")
    print()
    print("  (Arm 1) estimator honesty -- energy-perturbation (r-neutral) extents, SAME run:")
    print(f"    energy sigma_x/sigma_y @{RECORD_STEP} = {a1100['en_xy']:.3f}")
    print(f"    energy sigma_x/sigma_z @{RECORD_STEP} = {a1100['en_xz']:.3f}   (round ~1.0; 2.510 survives only if >= {SURVIVE_XZ})")
    print()
    print("  (Arm 3) label honesty -- coh sigma_x/sigma_z at docs' ~1100 vs code's 3500/15000:")
    print(f"    @{RECORD_STEP} = {a1100['coh_xz']:.3f}   (the oblate transient, docs' 'step 1100')")
    print(f"    @{DEFAULT_FINAL} = {a3500['coh_xz']:.3f}   (default run's idx_bubble = last snapshot)")
    print(f"    @{LONG_STEP} = {a15000['coh_xz']:.3f}   (code's literal idx_bubble target)")
    d3500 = abs(a1100["coh_xz"] - a3500["coh_xz"]) / max(abs(a1100["coh_xz"]), 1e-12)
    d15000 = abs(a1100["coh_xz"] - a15000["coh_xz"]) / max(abs(a1100["coh_xz"]), 1e-12)
    print(f"    |delta(1100-3500)|/1100 = {d3500:.3f}   |delta(1100-15000)|/1100 = {d15000:.3f}   (materially different if > 0.20)")
    print()

    r2 = arm_2()
    print("  (Arm 2) IC honesty -- transverse envelope isotropic (sigma_x = sigma_y):")
    print(f"    coh sigma_x/sigma_y @{RECORD_STEP} = {r2['coh_xy']:.3f}   (seeded phi={PHI:.3f} gone? need < {COLLAPSE_XY})")
    print(f"    coh sigma_x/sigma_z @{RECORD_STEP} = {r2['coh_xz']:.3f}   (2.510 survives? need >= {SURVIVE_XZ})")
    print(f"    energy sigma_x/sigma_z @{RECORD_STEP} = {r2['en_xz']:.3f}")
    print()

    r4 = arm_4()
    vals = [v for _, v in r4]
    mean = float(np.mean(vals))
    sd = float(np.std(vals))
    cv = sd / max(abs(mean), 1e-12)
    print(f"  (Arm 4) ensemble -- 4 seeded IC perturbations, coh sigma_x/sigma_z @{RECORD_STEP}:")
    for seed, v in r4:
        print(f"    seed {seed}: sigma_x/sigma_z = {v:.3f}")
    print(f"    mean = {mean:.3f}  std = {sd:.3f}  CV = {cv:.3f}")
    print()

    # ── Frozen decision tree ──
    a1_survives = a1100["en_xz"] >= SURVIVE_XZ
    a2_survives = r2["coh_xz"] >= SURVIVE_XZ
    a2_xy_collapsed = r2["coh_xy"] < COLLAPSE_XY
    a4_stable = (cv < SEED_CV_MAX) and all(v >= SURVIVE_XZ for v in vals)
    energy_round = a1100["en_xz"] < ENERGY_ROUND

    print("  === FROZEN VERDICTS ===")
    print(f"  Arm-0 reproduction {'PASSED (faithful harness)' if rep_ok else 'FAILED'}.")
    print(f"  Arm-1 estimator honesty: energy sigma_x/z @{RECORD_STEP} = {a1100['en_xz']:.3f} -> "
          f"{'SURVIVES (>=1.8)' if a1_survives else 'COLLAPSES (<1.8)'}; "
          f"{'energy IS round (~1.0)' if energy_round else 'energy NOT round'}")
    print(f"  Arm-2 IC honesty: coh sigma_x/y = {r2['coh_xy']:.3f} -> "
          f"{'collapsed to ~1.00 (seeded ratio gone)' if a2_xy_collapsed else 'did NOT collapse'}; "
          f"coh sigma_x/z = {r2['coh_xz']:.3f} -> {'SURVIVES (>=1.8)' if a2_survives else 'COLLAPSES (<1.8)'}")
    print(f"  Arm-3 label honesty: {a1100['coh_xz']:.3f}@{RECORD_STEP} vs "
          f"{a3500['coh_xz']:.3f}@{DEFAULT_FINAL} vs {a15000['coh_xz']:.3f}@{LONG_STEP} -> "
          f"{'MATERIALLY DIFFERENT (citation wrong)' if (d3500 > 0.20 or d15000 > 0.20) else 'not materially different'}")
    print(f"  Arm-4 ensemble: CV={cv:.3f} -> {'SEED-STABLE' if a4_stable else 'NOT seed-stable (single-run number is not a record)'}")

    if not rep_ok:
        verdict = "INCONCLUSIVE (harness not faithful)"
    elif a1_survives and a2_survives and a4_stable:
        verdict = "SUPPORTS (2.510 is a genuine emergent record)"
    else:
        failed = []
        if not a1_survives:
            failed.append(f"Arm-1 estimator honesty (energy sigma_x/z={a1100['en_xz']:.3f})")
        if not a2_survives:
            failed.append(f"Arm-2 IC honesty (coh sigma_x/z={r2['coh_xz']:.3f})")
        if not a4_stable:
            failed.append(f"Arm-4 seed stability (CV={cv:.3f})")
        verdict = "CONTRADICTS (collapses under " + "; ".join(failed) + ")"
    print(f"  OVERALL: {verdict}")
    print()


if __name__ == "__main__":
    main()
