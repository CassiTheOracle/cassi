#!/usr/bin/env python3
"""PDE w(a) test at N=32: single-channel (or any gate_model) background run.

Measures w(a) from the PDE's own expansion history H(a) and fits the CPL
pair (w0, wa) over a in [0.3, 1.0], the same window the ODE baselines use
(`two-fluid/calibrate_initial_ratio_xi_v2.py`, `two-fluid/wa_full_ode.py`).

Why adaptive dt: with a fixed dt the solver is diffusion-stiff at small a —
the viscous term nu*k2/a^2 gives an RK2 stability bound dt <= 2*a^2/(nu*k2max)
≈ 5.2e-4 at a=0.01, so dt=0.0005 (the original default) is exactly at the
stability edge and reaches only a ~ 0.03 after 40k steps—far short of the
fit window.  This script steps with dt = min(dt_cap, 4*a^2), which follows
the stability bound with a 1.3x safety margin and relaxes as a grows; the
PDE equations are untouched.

Usage:
    python two-fluid/run_pde_wa_test.py --steps 60000
    python two-fluid/run_pde_wa_test.py --resume runs/<rid>_pde_wa
"""

import argparse, glob, json, os, sys, time
from datetime import datetime

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI, PHI_INV

DT_CAP_DEFAULT = 0.005     # converged: cap 0.01 develops a late-time numerical
                    # r-oscillation (a swings 0.4<->2, r->7.6); cap 0.005 stays monotone
STEPS_DEFAULT = 90000      # adaptive-dt budget to reach a ~ 1.0 at cap 0.005 is ~85k steps


def dt_for(solver, dt_cap):
    """Diffusion-stability-adaptive step: dt = min(dt_cap, 4*a^2).

    Bound: RK2 stable for dt*nu*k2max/a^2 <= 2; nu*k2max = 0.384, so
    dt <= 5.2*a^2.  Factor 4 gives a 1.3x margin; at a=0.01 this is
    4e-4, the original script's dt.
    """
    a = solver.a.item()
    return min(dt_cap, 4.0 * a * a)


def make_solver(gate_model, seed=42, device='cpu'):
    return ExpandingTwoFluid3DGPU(
        N=32, lam=0.02, chi=0.0, D=0.0001, nu=0.0005,
        a0=0.01, initial_ratio=21.2, hubble_mode='conversion',
        max_H=None, h_smooth=0.05, qi_gate=True,
        mode='cosmos', device=device)


def save_checkpoint(ckpt_dir, step, solver, u_hat, ey_hat, ei_hat):
    ckpt = os.path.join(ckpt_dir, 'checkpoint_%06d.pt' % step)
    torch.save({
        'step': step, 'a': solver.a, 'H': solver.H,
        'H_smooth': solver._H_smooth, 'q_mean': solver.q_mean,
        'u_hat': u_hat, 'ey_hat': ey_hat, 'ei_hat': ei_hat,
    }, ckpt)
    old = sorted(glob.glob(os.path.join(ckpt_dir, 'checkpoint_*.pt')))[:-2]
    for f in old:
        os.remove(f)


def load_latest_checkpoint(run_dir):
    ckpts = sorted(glob.glob(os.path.join(run_dir, 'checkpoint_*.pt')))
    if not ckpts:
        return None
    return torch.load(ckpts[-1], weights_only=False)


def compute_w_from_snaps(snaps):
    """w(a) = -1 - (2/3) d ln H / d ln a from logged (a, H) pairs."""
    a = np.array([s['a'] for s in snaps])
    H = np.array([s['H'] for s in snaps])
    n = len(a)
    dln = np.zeros(n)
    for i in range(1, n - 1):
        da = a[i + 1] - a[i - 1]
        if da > 0 and H[i] > 0:
            dln[i] = (a[i] / H[i]) * (H[i + 1] - H[i - 1]) / da
    if H[0] > 0 and a[1] > a[0]:
        dln[0] = (a[0] / H[0]) * (H[1] - H[0]) / (a[1] - a[0])
    if H[-1] > 0 and a[-1] > a[-2]:
        dln[-1] = (a[-1] / H[-1]) * (H[-1] - H[-2]) / (a[-1] - a[-2])
    return a, H, -1.0 - (2.0 / 3.0) * dln


def fit_w0_wa(a, w, a_min=0.3, a_max=1.0):
    mask = (a >= a_min) & (a <= a_max)
    reached = bool(mask.sum() >= 3)
    if not reached:
        mask = np.ones_like(a, dtype=bool)
    X = np.column_stack([np.ones_like(a[mask]), 1.0 - a[mask]])
    c = np.linalg.lstsq(X, w[mask], rcond=None)[0]
    return c[0], c[1], reached, int(mask.sum())


def run(args):
    if args.resume:
        run_dir = args.resume
        with open(os.path.join(run_dir, 'meta.json')) as f:
            meta = json.load(f)
        args.gate = meta['gate_model']
        args.seed = meta['seed']
        args.dt_cap = meta['dt_cap']
        args.device = meta.get('device', 'cpu')
        steps_total = args.steps if args.steps else meta['steps']
        ckpt = load_latest_checkpoint(run_dir)
        if ckpt is None:
            print(f'[ERROR] no checkpoint in {run_dir}'); sys.exit(1)
        start_step = ckpt['step'] + 1
        logfile = os.path.join(run_dir, 'log.txt')
        solver = make_solver(args.gate, args.seed, args.device)
        solver.gate_model = args.gate
        solver.a = ckpt['a']; solver.H = ckpt['H']
        solver._H_smooth = ckpt['H_smooth']; solver.q_mean = ckpt['q_mean']
        u_hat, ey_hat, ei_hat = ckpt['u_hat'], ckpt['ey_hat'], ckpt['ei_hat']
        print(f'Resuming {run_dir} at step {start_step} '
              f'(gate={args.gate}, seed={args.seed}, device={args.device})')
    else:
        rid = datetime.now().strftime('%Y%m%d_%H%M%S')
        run_dir = os.path.join('runs', f'{rid}_pde_wa')
        os.makedirs(run_dir, exist_ok=True)
        steps_total = args.steps or STEPS_DEFAULT
        start_step = 0
        logfile = os.path.join(run_dir, 'log.txt')
        with open(logfile, 'w') as f:
            f.write(f'# N=32 lam=0.02 gate={args.gate} seed={args.seed} '
                    f'steps={steps_total} dt=min({args.dt_cap}, 4a^2)\n')
            f.write('# step a H_smooth r_mean q_mean\n')
        solver = make_solver(args.gate, args.seed, args.device)
        solver.gate_model = args.gate
        u_hat, ey_hat, ei_hat = solver.initial_expanding(
            amplitude=0.01, seed=args.seed)
        print(f'Starting N=32 gate={args.gate} seed={args.seed} '
              f'device={args.device} ({steps_total} steps) -> {run_dir}')

    meta = dict(device=args.device, gate_model=args.gate, seed=args.seed, dt_cap=args.dt_cap,
                steps=steps_total, N=32, lam=0.02, a0=0.01,
                initial_ratio=21.2, hubble_mode='conversion',
                start_step=start_step)
    with open(os.path.join(run_dir, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)

    snaps = []
    t0 = time.time()
    for step in range(start_step, steps_total + 1):
        dt = dt_for(solver, args.dt_cap)
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, dt)

        if step % args.log_every == 0 or step == steps_total:
            a = solver.a.item()
            H = solver._H_smooth.item()
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            r = (ey.mean() / (ei.mean() + 1e-12)).item()
            qm = solver.q_mean.item()
            if np.isnan(a):
                with open(logfile, 'a') as f:
                    f.write(f'NaN at step {step}\n')
                print(f'NaN at step {step}')
                break
            snaps.append(dict(step=step, a=a, H=H, r=r, q_mean=qm))
            with open(logfile, 'a') as f:
                f.write(f'{step} {a:.6e} {H:.6e} {r:.6f} {qm:.6f}\n')

        if step % args.ckpt_every == 0 and step > start_step:
            save_checkpoint(run_dir, step, solver, u_hat, ey_hat, ei_hat)

        if step % (args.ckpt_every * 2) == 0 and snaps:
            h = snaps[-1]
            el = time.time() - t0
            print(f'  step={step:6d} a={h["a"]:.5f} r={h["r"]:.4f} '
                  f'H={h["H"]:.5f} q={h["q_mean"]:.4f} [{el:.0f}s]', flush=True)

    a_arr, H_arr, w_arr = compute_w_from_snaps(snaps)
    w0, wa, reached, n_fit = fit_w0_wa(a_arr, w_arr)
    a_min_l, a_max_l = a_arr[0], a_arr[-1]
    omq_early = np.mean([1.0 - s['q_mean'] for s in snaps
                         if 0.30 <= s['a'] <= 0.45]) if reached else np.nan
    omq_late = np.mean([1.0 - s['q_mean'] for s in snaps
                        if s['a'] >= 0.85]) if a_max_l >= 0.85 else np.nan

    res = dict(gate_model=args.gate, seed=args.seed,
               steps_done=snaps[-1]['step'] if snaps else 0,
               a_min_log=a_min_l, a_max_log=a_max_l,
               fit_window_reached=reached, fit_n=n_fit, w0=w0, wa=wa,
               omq_early=omq_early, omq_late=omq_late,
               omq_delta=(None if (omq_early != omq_early or
                                   omq_late != omq_late)
                          else omq_late - omq_early))
    with open(os.path.join(run_dir, 'results.json'), 'w') as f:
        json.dump(res, f, indent=1)

    print(f'\n=== gate={args.gate} seed={args.seed} ===')
    print(f'  a range: {a_min_l:.4f} -> {a_max_l:.4f}  '
          f'(fit window [0.3,1] reached: {reached})')
    print(f'  w0 = {w0:.4f}   wa = {wa:+.4f}   (fit over {n_fit} pts)')
    if res['omq_delta'] is not None:
        print(f'  <1-q> early {omq_early:.4f} -> late {omq_late:.4f} '
              f'(delta {res["omq_delta"]:+.4f})')
    else:
        print(f'  <1-q> early/late: n/a (fit window not reached)')
    print(f'  results: {os.path.join(run_dir, "results.json")}')
    return run_dir


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='PDE w(a) test (N=32 background)')
    p.add_argument('--steps', type=int, default=None,
                   help='total steps (default: %d; on --resume, the run\'s own '
                        'total is kept unless this is given)' % STEPS_DEFAULT)
    p.add_argument('--dt-cap', type=float, default=DT_CAP_DEFAULT)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--gate', type=str, default='single')
    p.add_argument('--log-every', type=int, default=500)
    p.add_argument('--ckpt-every', type=int, default=5000)
    p.add_argument('--resume', type=str, default=None)
    p.add_argument('--device', type=str, default='cpu',
                   help="'cpu' or 'cuda' (all arms must share a device)")
    args = p.parse_args()
    run(args)
