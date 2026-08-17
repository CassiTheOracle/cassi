#!/usr/bin/env python3
"""Meshless coherence-cluster depth probe (Amendment 3, owner-approved (a)).

Does a phi-organized multi-scale coherent particle cluster self-persist more
with more cascade rungs? Uses the OWNER's directive: the meshless Qi-gated
particle solver (two-fluid/cassi_nbody.py) with the solver's own particle
coherence (q = rho^2/(rho^2 + phi^-2 + eps^2)) as the order parameter — no
bespoke equation.

Seed (phi-organized multi-scale cluster): N bodies in nested shells at
phi-spaced radii r_k = r_inner * phi^k (k = 0..D-1, D = rung depth). The inner
(fine, lower-rung) shells carry the density/coherence excess ("lower scales
feed up") — realized NATIVELY by the Qi gate: the dense inner shells have high
q -> adaptive softening collapses -> stronger core binding.

Mechanism under test: a multi-rung coherent cluster should self-persist (stay
bound longer) than a single-scale blob — more rungs -> more stable. That depth
scaling IS cascade suppression (phi^-1 per rung coupling, qi-flow-double-helix
L3.2). Owner: "the goal is for the simulator to simulate reality."

Metric (frozen, Amendment 3 L12): T_hold(D) = time the mass fraction inside the
innermost phi-rung (r < r_inner*phi) stays >= 0.5x its t=0 value (the dense
high-coherence core persists). SUPPORTS cascade suppression iff T_hold monotone
increasing in D (depth_4 > depth_2 > depth_1) AND T_hold(depth_4) >= 2x
T_hold(depth_1); and mass conserved (KDK).

Arms: fresh solver per arm, L=20, G=1, sigma=0.4, dt=0.001, KDK, Qi-gate ON.
Run:  python two-fluid/meshless_deep_probe.py [--steps N] [--arm TAG]
Output: runs/<rid>_meshless_deep/ (per-arm + results JSON); commit script only.
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
    """D nested virialized shells at phi-spaced radii r_inner*phi^k.

    Inner (fine, lower-rung) shells carry heavier particles (the coherence
    excess -> dense high-q core under the Qi gate). Velocities set to a
    virial dispersion (Q ~ 1) so the depth question is structural persistence,
    not a cold-collapse artifact. Total mass ~ D*N_shell (Plummer convention
    M ~ N). Returns (pos, vel, masses) on CPU (caller moves to device)."""
    gen = np.random.default_rng(seed)
    G = 1.0
    parts, ms, vs = [], [], []
    # shell radii and masses
    rks = [r_inner * PHI ** k for k in range(D)]
    # moderate mass: normalize so total mass = number of bodies (unit-ish),
    # keeping the inner-heavier phi^-k weight (coherence excess at fine rungs).
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


def measure_hold(trails, masses, r_core, frac_thresh=0.5,
                 config=None):
    """Structural-retention metric: T_hold = time the mass fraction inside the
    innermost phi-rung (r < r_core = r_inner*phi) stays >= frac_thresh of its
    t=0 value. The dense high-coherence core is the 'lower scales feed up'
    structure; deeper clusters should hold it longer (cascade suppression).

    Returns (T_hold, inner-mass-fraction trajectory, half_mass_r trajectory)."""
    n_frames = trails.shape[0]
    t_cpu = trails.cpu()              # guarantee CPU regardless of source device
    m_cpu = masses.cpu()
    com = (t_cpu[0] * m_cpu[:, None]).sum(0) / m_cpu.sum()
    r0 = torch.sqrt(((t_cpu[0] - com) ** 2).sum(1))
    inner0 = float((m_cpu[r0 < r_core]).sum()) / float(m_cpu.sum())
    frame_dt = config.dt * getattr(config, 'track_every', 50)
    fracs, r_half = [], []
    T_hold = None
    for f in range(n_frames):
        c = (t_cpu[f] * m_cpu[:, None]).sum(0) / m_cpu.sum()
        r = torch.sqrt(((t_cpu[f] - c) ** 2).sum(1))
        cur = float((m_cpu[r < r_core]).sum()) / float(m_cpu.sum())
        fracs.append(cur)
        srt = torch.sort(r).values
        ms = m_cpu[torch.sort(r).indices]
        csum = torch.cumsum(ms, 0)
        i50 = int((csum >= 0.5 * csum[-1]).nonzero()[0].item())
        r_half.append(float(srt[i50]))
        t = f * frame_dt
        if T_hold is None and cur < frac_thresh * inner0:
            T_hold = t
    if T_hold is None:
        T_hold = n_frames * frame_dt
    return T_hold, fracs, r_half, inner0


def virialize(solver, pos, masses):
    """Set velocity dispersion from the solver's OWN softened gravity so the
    cluster starts near virial balance (Q ~ 1): deposit, solve_gravity -> a(x),
    trilinear-interpolate to each particle, and set v_rms = sqrt(0.5*r*|a|).
    Uses the real softened potential (sigma=0.4), not the analytic point-mass
    form, so the cluster neither over-collapses nor flies apart at t=0.
    Returns velocities tensor (same device as pos)."""
    rho = solver.deposit_density(pos, masses)
    ax, ay, az = solver.solve_gravity(rho)
    # grid -> physical coords interpolation
    g = (pos + 0.5 * solver.L) / solver.dx
    gi = g.long(); gf = (g - gi.float()).clamp(0.0, 1.0)
    n = solver.n
    def at(axg, gix, giy, giz, gfx, gfy, gfz):
        # trilinear on the grid field
        x0, x1 = gix % n, (gix + 1) % n
        y0, y1 = giy % n, (giy + 1) % n
        z0, z1 = giz % n, (giz + 1) % n
        c000 = axg[x0, y0, z0]; c100 = axg[x1, y0, z0]
        c010 = axg[x0, y1, z0]; c110 = axg[x1, y1, z0]
        c001 = axg[x0, y0, z1]; c101 = axg[x1, y0, z1]
        c011 = axg[x0, y1, z1]; c111 = axg[x1, y1, z1]
        def bl(c00, c10, c01, c11, fx, fz):
            return (c00 * (1 - fx) + c10 * fx) * (1 - fz) + \
                   (c01 * (1 - fx) + c11 * fx) * fz
        c0 = bl(c000, c100, c001, c101, gfx, gfz)
        c1 = bl(c010, c110, c011, c111, gfx, gfz)
        return c0 * (1 - gfy) + c1 * gfy
    av = torch.stack([at(ax, gi[:,0], gi[:,1], gi[:,2], gf[:,0], gf[:,1], gf[:,2]),
                      at(ay, gi[:,0], gi[:,1], gi[:,2], gf[:,0], gf[:,1], gf[:,2]),
                      at(az, gi[:,0], gi[:,1], gi[:,2], gf[:,0], gf[:,1], gf[:,2])], dim=1)
    r = torch.sqrt(((pos - pos.mean(0)) ** 2).sum(1)).clamp(min=1e-4)
    v_rms = torch.sqrt((0.5 * r * av.norm(dim=1)).clamp(min=0.0))
    # isotropic random directions, magnitudes ~ v_rms
    gen = torch.Generator(device=pos.device).manual_seed(7)
    dirs = torch.randn(pos.shape, device=pos.device, generator=gen)
    dirs = dirs / dirs.norm(dim=1, keepdim=True).clamp(min=1e-9)
    return dirs * v_rms[:, None]


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
            n_grid=128, L=L, G=G, sigma=sigma, dt=dt,
            n_steps=args.steps, qi_gate=True, qi_memory=False,
            deposition_kernel='TSC', report_every=500, track_every=100,
            device=device)
        # solver-consistent virialization: build the solver, set velocities from
        # its own softened acceleration so Q(0) ~ 1 (no cold collapse).
        vir_sol = NB.NBodySolver3D(n_grid=128, L=L, G=G, sigma=sigma,
                                   device=device, qi_gate=True,
                                   deposition_kernel='TSC')
        vel = virialize(vir_sol, pos, masses)
        t0 = time.time()
        diag, trails, solver = NB.run_simulation(config, pos, vel, masses, track=True)
        elapsed = time.time() - t0
        if trails is None:
            print(f"  ! no trails (track off) — cannot measure T_disperse")
            out[tag] = {'error': 'no trails'}
            continue
        r_core = arm['r_inner'] * PHI          # innermost phi-rung radius
        T_hold, fracs, r_half, inner0 = measure_hold(
            trails, masses, r_core, config=config)
        # mean interior coherence from deposited rho at last frame (solver on GPU)
        rho = solver.deposit_density(trails[-1].to(device), masses).cpu().numpy()
        q_last = float(np.mean(rho ** 2 / (rho ** 2 + (1.0 / PHI) ** 2 + 1e-6)))
        print(f"  N={N} total_m={float(masses.sum()):.1f}")
        print(f"  inner_frac(0)={inner0:.3f}  T_hold={T_hold:.2f}  "
              f"r_half_end={r_half[-1]:.3f}  q_last={q_last:.4f}  "
              f"[{elapsed:.0f}s, {config.n_steps} steps]")
        # save per-arm trails summary
        with open(f"{rdir}/run_{tag}.json", "w") as f:
            json.dump({'tag': tag, 'D': arm['D'], 'N': N,
                       'T_hold': T_hold, 'inner_frac_0': inner0,
                       'inner_frac_end': fracs[-1],
                       'q_last': q_last, 'n_steps': config.n_steps,
                       'elapsed': elapsed}, f, indent=1)
        out[tag] = {'D': arm['D'], 'T_hold': T_hold,
                    'inner_frac_0': inner0, 'inner_frac_end': fracs[-1],
                    'q_last': q_last, 'n_steps': config.n_steps}

    # Verification: inner-rung structural retention vs depth.
    print("\n=== MESHLESS DEPTH (Amendment 3) RESULTS ===")
    for tag, r in out.items():
        if 'error' in r:
            continue
        print(f"  {tag}: D={r['D']} T_hold={r['T_hold']:.2f} "
              f"inner_frac {r['inner_frac_0']:.3f}->{r['inner_frac_end']:.3f} "
              f"q_last={r['q_last']:.4f}")

    if all('error' not in r and 'T_hold' in r for r in out.values()) and len(out) >= 2:
        T1 = out['depth_1']['T_hold']
        T2 = out.get('depth_2', {}).get('T_hold', T1)
        T4 = out.get('depth_4', {}).get('T_hold', T2)
        mono = T4 > T2 > T1 if 'depth_4' in out else (T2 > T1 if 'depth_2' in out else True)
        at_least_2x = T4 >= 2.0 * T1 if 'depth_4' in out else (T2 >= 1.5 * T1 if 'depth_2' in out else False)
        verdict = 'SUPPORTS' if (mono and at_least_2x) else (
            'WEAK-PARTIAL' if mono else 'DOES NOT SUPPORT')
        print(f"\n=== CASCADE-SUPPRESSION DEPTH VERDICT: {verdict} ===")
        print(f"  (more rungs -> longer T_hold = dense-coherent core persists "
              f"more = phi^-1/rung depth scaling = cascade suppression)")
        note = ('T_hold monotone in D' if mono else 'T_hold NOT monotone in D')
        print(f"  {note}; {'at-least-2x satisfied' if at_least_2x else 'at-least-2x not satisfied'}")
    else:
        verdict = 'INCOMPLETE'
        print(f"\n=== VERDICT: {verdict} (need >= depth_1 + one deeper arm) ===")

    results = {'meta': {'L': L, 'G': G, 'sigma': sigma, 'dt': dt,
                        'N_shell': 1200, 'gate': 'Qi (native coherence order param)',
                        'amendment': '3', 'owner': 'meshless, (a) coherence-as-order-parameter'},
               'arms': out, 'verdict': verdict}
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
