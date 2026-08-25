#!/usr/bin/env python3
"""Meshless depth sweep retained for Amendment 3 protocol auditing.

The script evolves nested phi-spaced particle shells with the shipped N-body
solver and records a legacy inner-rung retention diagnostic. It is not a
controlled cascade-suppression experiment: increasing ``D`` also changes
particle count, total mass, outer radius, and initial inner-mass fraction.
The occupied-cell ``q`` proxy selects a legacy global adaptive-softening
heuristic rather than canonical two-fluid coherence ``q(E_Y, E_I)``.

The initial speed scale is another heuristic rather than a verified virial
equilibrium. It differs from the signed-coordinate probes' inward radial seed.
The first tracked solver frame occurs after one step, so the implementation
uses the separately retained initial state and records the exact tracked
sample times.

The registered depth arithmetic is reported only as a diagnostic pattern. It
cannot receive a support label because the protocol is invalid. A valid
comparison needs matched mass, extent, phase-space sampling, initial inner
fraction, and velocity distribution, plus a canonical nonnegative two-fluid
state or an explicitly defined independent phase variable.

Frozen statistic:
``T_hold(D)`` is the last observed time for which the mass fraction inside
``r_core = r_inner*phi`` has not fallen below half its exact initial value.
Runs without a sampled crossing are right-censored at the last tracked frame.

Run: ``python two-fluid/meshless_deep_probe.py [--steps N] [--arm TAG]``
Output: ``runs/<rid>_meshless_deep/``
"""

import os
import sys
import json
import math
import time
import argparse
from datetime import datetime

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cassi_nbody as NB

PHI = (1.0 + math.sqrt(5)) / 2.0


def phi_cluster_ic(D, r_inner, N_shell, L, seed=42):
    """Construct ``D`` nested shells at radii ``r_inner*phi**k``.

    Each shell contains ``N_shell`` particles. Per-particle shell weights fall
    as ``phi**(-k)``, then are normalized so the total mass is
    ``D*N_shell``. Consequently depth changes particle count, total mass,
    outer extent, and initial inner-rung fraction; the arms are not controlled
    counterfactuals. Returns ``(pos, vel, masses)`` on CPU.
    """
    gen = np.random.default_rng(seed)
    G = 1.0
    parts, ms, vs = [], [], []
    # shell radii and masses
    rks = [r_inner * PHI ** k for k in range(D)]
    # Normalize the mean particle mass to one within each arm. Total mass
    # therefore grows linearly with D; this is a declared protocol confound.
    w_sum = sum(PHI ** (-k) for k in range(D))
    m0 = (D * N_shell) / (N_shell * w_sum)   # per-shell normalization -> mean ~ 1
    mk_list = [m0 * PHI ** (-k) for k in range(D)]
    M_enc_prior = 0.0
    for k in range(D):
        r = rks[k]
        n = N_shell
        i = np.arange(n)
        golden = math.pi * (3.0 - math.sqrt(5.0))
        th = golden * i
        ph = np.arccos(1.0 - 2.0 * (i + 0.5) / n)
        x = np.sin(ph) * np.cos(th)
        y = np.sin(ph) * np.sin(th)
        z = np.cos(ph)
        pos_k = np.stack([x, y, z], axis=1) * r      # centered at origin (solver
        #                                              convention: pos in [-L/2,L/2])
        # potential at radius r: inner shells (<=r) act as point mass at center:
        #   Phi = -G*M(<r)/r - G*sum_{shells at r'>r} m_{k'}/r'   (shell theorem)
        M_enc = M_enc_prior + mk_list[k]
        Phi_r = -G * M_enc_prior / max(r, 1e-9) - G * sum(
            mk_list[kk] / max(rks[kk], 1e-9) for kk in range(k + 1, D))
        # virial: v_rms^2 = -Phi(r)  => 2 KE = -PE, isotropic
        v_rms = math.sqrt(max(-Phi_r, 0.0))
        v_k = gen.normal(0.0, v_rms, size=(n, 3))
        parts.append(pos_k)
        ms.append(np.full(n, mk_list[k]))
        vs.append(v_k)
        M_enc_prior = M_enc
    pos = np.concatenate(parts)
    masses = np.concatenate(ms)
    vel = np.concatenate(vs)
    return torch.tensor(pos, dtype=torch.float64), \
        torch.tensor(vel, dtype=torch.float64), \
        torch.tensor(masses, dtype=torch.float64)


def to_device(pos, vel, masses, device):
    return pos.to(device), vel.to(device), masses.to(device)


def measure_hold(trails, masses, initial_pos, r_core, frac_thresh=0.5,
                 config=None):
    """Measure retention against the exact initial state and tracked times.

    ``run_simulation`` records frames after steps 1, 1+track_every, ...; it
    does not record t=0 or necessarily the terminal state. A no-crossing run
    is therefore right-censored at the final sampled time.
    """
    if config is None:
        raise ValueError("config is required for exact sample times")
    n_frames = trails.shape[0]
    if n_frames == 0:
        raise ValueError("at least one tracked frame is required")
    t_cpu = trails.cpu()
    initial_cpu = initial_pos.cpu()
    m_cpu = masses.cpu()
    initial_com = (
        (initial_cpu * m_cpu[:, None]).sum(0) / m_cpu.sum()
    )
    initial_r = torch.sqrt(((initial_cpu - initial_com) ** 2).sum(1))
    inner0 = float((m_cpu[initial_r < r_core]).sum()) / float(m_cpu.sum())
    sample_times = [
        config.dt * (1 + f * config.track_every) for f in range(n_frames)
    ]
    fracs, r_half = [], []
    T_hold = None
    for f, sample_time in enumerate(sample_times):
        c = (t_cpu[f] * m_cpu[:, None]).sum(0) / m_cpu.sum()
        r = torch.sqrt(((t_cpu[f] - c) ** 2).sum(1))
        cur = float((m_cpu[r < r_core]).sum()) / float(m_cpu.sum())
        fracs.append(cur)
        order = torch.sort(r).indices
        srt = r[order]
        ms = m_cpu[order]
        csum = torch.cumsum(ms, 0)
        i50 = int((csum >= 0.5 * csum[-1]).nonzero()[0].item())
        r_half.append(float(srt[i50]))
        if T_hold is None and cur < frac_thresh * inner0:
            T_hold = sample_time
    censored = T_hold is None
    if censored:
        T_hold = sample_times[-1]
    return T_hold, fracs, r_half, inner0, sample_times, censored


def isotropic_speed_seed(solver, pos, masses):
    """Construct the probe's heuristic isotropic velocity seed.

    Native interpolation supplies the softened acceleration magnitude at each
    particle. Random directions use a fixed seed and speeds
    ``sqrt(0.5*r*abs(a))``. This does not impose or verify global
    ``2K/abs(PE)=1`` and is not a stationary virial equilibrium.
    """
    rho = solver.deposit_density(pos, masses)
    ax, ay, az = solver.solve_gravity(rho)
    accel = solver.interpolate_accel(ax, ay, az, pos)
    r = torch.sqrt(((pos - pos.mean(0)) ** 2).sum(1)).clamp(min=1e-4)
    speed = torch.sqrt((0.5 * r * accel.norm(dim=1)).clamp(min=0.0))
    gen = torch.Generator(device=pos.device).manual_seed(7)
    directions = torch.randn(pos.shape, device=pos.device, generator=gen)
    directions = directions / directions.norm(
        dim=1, keepdim=True
    ).clamp(min=1e-9)
    return directions * speed[:, None]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--steps', type=int, default=12000)
    parser.add_argument('--arm', action='append', default=None)
    args = parser.parse_args()

    device = NB.get_device()
    print(f"Device: {device}")
    L, G, sigma, dt = 20.0, 1.0, 0.4, 0.001
    arms = {
        'depth_1': dict(D=1, r_inner=1.2),
        'depth_2': dict(D=2, r_inner=1.2),
        'depth_4': dict(D=4, r_inner=1.2),
    }
    if args.arm is not None:
        arms = {k: v for k, v in arms.items() if k in args.arm}

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_meshless_deep"
    os.makedirs(rdir, exist_ok=True)

    out = {}
    for tag, arm in arms.items():
        print(f"\n=== {tag}: D={arm['D']} r_inner={arm['r_inner']} ===")
        N_shell = 800
        pos, vel, masses = phi_cluster_ic(arm['D'], arm['r_inner'], N_shell, L)
        pos, vel, masses = to_device(pos, vel, masses, device)
        N = pos.shape[0]
        config = NB.NBodyConfig(
            n_grid=64, L=L, G=G, sigma=sigma, dt=dt,
            n_steps=args.steps, qi_gate=True, qi_memory=False,
            deposition_kernel='TSC', report_every=500, track_every=100,
            device=device)
        # Heuristic isotropic speed seed; no virial-equilibrium claim.
        seed_solver = NB.NBodySolver3D(
            n_grid=64, L=L, G=G, sigma=sigma, device=device, qi_gate=True,
            deposition_kernel='TSC'
        )
        vel = isotropic_speed_seed(seed_solver, pos, masses)
        initial_pos = pos.detach().cpu().clone()
        t0 = time.time()
        diag, trails, solver = NB.run_simulation(
            config, pos, vel, masses, track=True
        )
        elapsed = time.time() - t0
        if trails is None:
            print("  ! no tracked frames; cannot measure retention")
            out[tag] = {'error': 'no tracked frames'}
            continue
        r_core = arm['r_inner'] * PHI
        T_hold, fracs, r_half, inner0, sample_times, censored = measure_hold(
            trails, masses, initial_pos, r_core, config=config
        )
        # Match the occupied-cell legacy proxy returned by
        # NBodySolver3D.compute_acceleration_density_memory.
        rho = solver.deposit_density(
            trails[-1].to(device), masses
        ).cpu().numpy()
        rho_max = float(np.max(rho))
        non_vac = (
            rho > 0.01 * rho_max
            if rho_max > 1e-10 else np.ones_like(rho, dtype=bool)
        )
        legacy_density_proxy = rho / (
            rho + (1.0 / PHI) ** 2 + 1e-12
        )
        legacy_density_proxy_last_sample = float(
            np.mean(legacy_density_proxy[non_vac])
            if np.any(non_vac) else 1.0
        )
        total_mass = float(masses.sum())
        outer_radius = arm['r_inner'] * PHI ** (arm['D'] - 1)
        censor_label = " (right-censored)" if censored else ""
        print(f"  N={N} total_m={total_mass:.1f} outer_radius={outer_radius:.3f}")
        print(f"  inner_frac(initial)={inner0:.3f}  "
              f"T_hold={T_hold:.3f}{censor_label}  "
              f"last_sample_t={sample_times[-1]:.3f}  "
              f"r_half_last_sample={r_half[-1]:.3f}  "
              f"legacy_density_proxy_last_sample="
              f"{legacy_density_proxy_last_sample:.4f}  "
              f"[{elapsed:.0f}s, {config.n_steps} steps]")
        arm_result = {
            'tag': tag, 'D': arm['D'], 'N': N,
            'total_mass': total_mass, 'outer_radius': outer_radius,
            'T_hold': T_hold, 'T_hold_right_censored': censored,
            'inner_frac_initial': inner0,
            'inner_frac_last_sample': fracs[-1],
            'last_sample_time': sample_times[-1],
            'legacy_density_proxy_last_sample': legacy_density_proxy_last_sample,
            'n_steps': config.n_steps, 'elapsed': elapsed,
        }
        with open(f"{rdir}/run_{tag}.json", "w") as f:
            json.dump(arm_result, f, indent=1)
        out[tag] = arm_result

    print("\n=== MESHLESS DEPTH (Amendment 3) AUDIT RESULTS ===")
    for tag, result in out.items():
        if 'error' in result:
            continue
        print(
            f"  {tag}: D={result['D']} N={result['N']} "
            f"M={result['total_mass']:.1f} "
            f"R_outer={result['outer_radius']:.3f} "
            f"T_hold={result['T_hold']:.3f} "
            f"inner_frac {result['inner_frac_initial']:.3f}"
            f"->{result['inner_frac_last_sample']:.3f} "
            f"legacy_density_proxy_last_sample="
            f"{result['legacy_density_proxy_last_sample']:.4f}"
        )

    required = {'depth_1', 'depth_2', 'depth_4'}
    if required.issubset(out) and all(
        'error' not in out[tag] for tag in required
    ):
        T1 = out['depth_1']['T_hold']
        T2 = out['depth_2']['T_hold']
        T4 = out['depth_4']['T_hold']
        monotone = T4 > T2 > T1
        at_least_2x = T4 >= 2.0 * T1
        legacy_metric_pattern = (
            'MONOTONE_AND_2X' if monotone and at_least_2x
            else 'MONOTONE_BELOW_2X' if monotone
            else 'NOT_MONOTONE'
        )
    else:
        monotone = False
        at_least_2x = False
        legacy_metric_pattern = 'N/A (requires all three arms)'

    frozen_metric_branch = 'UNSCOREABLE (protocol invalid)'
    verdict = 'INCONCLUSIVE'
    print(f"\n=== LEGACY METRIC PATTERN: {legacy_metric_pattern} ===")
    print(f"  strict monotonicity: {monotone}; "
          f"depth_4 >= 2x depth_1: {at_least_2x}")
    print(f"=== FROZEN METRIC BRANCH: {frozen_metric_branch} ===")
    print("=== SCIENTIFIC VERDICT: INCONCLUSIVE ===")
    print("  Protocol validity: FAIL (depth changes N, total mass, outer radius, "
          "initial inner fraction, and the dynamical state; gate is a legacy "
          "global density proxy).")

    results = {
        'meta': {
            'L': L, 'G': G, 'sigma': sigma, 'dt': dt, 'N_shell': 800,
            'position_seed': 42, 'velocity_direction_seed': 7,
            'gate': 'legacy global density-memory adaptive softening',
            'amendment': '3',
            'arm': 'meshless (a) scalar density-proxy sweep',
            'protocol_valid': False,
            'confounds': [
                'particle_count', 'total_mass', 'outer_radius',
                'initial_inner_fraction', 'heuristic_velocity_seed',
                'noncanonical_global_density_proxy',
            ],
        },
        'arms': out,
        'legacy_metric_pattern': legacy_metric_pattern,
        'frozen_metric_branch': frozen_metric_branch,
        'verdict': verdict,
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
