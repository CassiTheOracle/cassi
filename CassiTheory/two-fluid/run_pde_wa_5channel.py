#!/usr/bin/env python3
"""PDE w(a) test: 5-channel Wu Xing gate vs single-channel at N=32.

Runs background (Hubble-mode) expansion for the gate models of
`foundations/wa-pentagon-gate.md` §3:
  single   — the current single-channel Qi gate (baseline)
  five     — 5-channel adiabatic redistribution (doc §2; late (1-q) floor)
  five_ke  — five + ke control ring = Wu Xing control-release dynamics
             (doc §3.3; the Delta = +0.055 sign-flip candidate)
Fits CPL (w0, wa) from each arm's PDE expansion history over a in [0.3, 1.0]
and prints the gate comparison: does the 5-channel gate shift w_a toward the
DESI-implied direction (more negative), and does the control-release
delta(1-q) > 0 sign-flip appear?

Adaptive dt (see `two-fluid/run_pde_wa_test.py` header): dt = min(dt_cap, 4a^2)
follows the RK2 diffusion-stability bound; the original fixed dt=0.0005 could
not reach the fit window in any feasible step budget.

Usage:
    python two-fluid/run_pde_wa_5channel.py --arms single,five,five_ke
    python two-fluid/run_pde_wa_5channel.py --arms five --steps 60000 --seed 42
    python two-fluid/run_pde_wa_5channel.py --arms five_ke --resume
"""

import argparse, glob, json, os, sys
from datetime import datetime

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI, PHI_INV

# cap 0.005 is the converged schedule: cap 0.01 develops a late-time
# numerical r-oscillation (a swings 0.4<->2, r->7.6); cap 0.005 stays
# monotone through a ~ 1.0 (verified 2026-08-05).
DT_CAP_DEFAULT = 0.005
STEPS_DEFAULT = 90000  # adaptive-dt budget to reach a ~ 1.0 at cap 0.005 ~85k
ARMS = ['single', 'five', 'five_ke']


def dt_for(solver, dt_cap):
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


def run_arm(gate, args):
    if args.resume:
        run_dir = args.resume
        with open(os.path.join(run_dir, 'meta.json')) as f:
            meta = json.load(f)
        args.seed = meta['seed']
        args.dt_cap = meta['dt_cap']
        args.device = meta.get('device', 'cpu')
        steps_total = args.steps if args.steps else meta['steps']
        ckpt = load_latest_checkpoint(run_dir)
        if ckpt is None:
            print(f'[ERROR] no checkpoint in {run_dir}'); sys.exit(1)
        start_step = ckpt['step'] + 1
        logfile = os.path.join(run_dir, 'log.txt')
        solver = make_solver(gate, args.seed, args.device)
        solver.gate_model = gate
        solver.a = ckpt['a']; solver.H = ckpt['H']
        solver._H_smooth = ckpt['H_smooth']; solver.q_mean = ckpt['q_mean']
        u_hat, ey_hat, ei_hat = ckpt['u_hat'], ckpt['ey_hat'], ckpt['ei_hat']
        print(f'Resuming {run_dir} at step {start_step} '
              f'(gate={gate}, seed={args.seed}, device={args.device})')
    else:
        rid = datetime.now().strftime('%Y%m%d_%H%M%S')
        run_dir = os.path.join('runs', f'{rid}_wa_{gate}')
        os.makedirs(run_dir, exist_ok=True)
        steps_total = args.steps or STEPS_DEFAULT
        start_step = 0
        logfile = os.path.join(run_dir, 'log.txt')
        with open(logfile, 'w') as f:
            f.write(f'# N=32 lam=0.02 gate={gate} seed={args.seed} '
                    f'steps={steps_total} dt=min({args.dt_cap}, 4a^2)\n')
            f.write('# step a H_smooth r_mean q_mean\n')
        solver = make_solver(gate, args.seed, args.device)
        solver.gate_model = gate
        u_hat, ey_hat, ei_hat = solver.initial_expanding(
            amplitude=0.01, seed=args.seed)
        print(f'Starting N=32 gate={gate} seed={args.seed} '
              f'device={args.device} ({steps_total} steps) -> {run_dir}')

    meta = dict(device=args.device, gate_model=gate, seed=args.seed, dt_cap=args.dt_cap,
                steps=steps_total, N=32, lam=0.02, a0=0.01,
                initial_ratio=21.2, hubble_mode='conversion',
                start_step=start_step)
    with open(os.path.join(run_dir, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)

    snaps = []
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
                print(f'[{gate}] NaN at step {step}')
                break
            snaps.append(dict(step=step, a=a, H=H, r=r, q_mean=qm))
            with open(logfile, 'a') as f:
                f.write(f'{step} {a:.6e} {H:.6e} {r:.6f} {qm:.6f}\n')

        if step % args.ckpt_every == 0 and step > start_step:
            save_checkpoint(run_dir, step, solver, u_hat, ey_hat, ei_hat)

        if step % (args.ckpt_every * 2) == 0 and snaps:
            h = snaps[-1]
            print(f'  [{gate}] step={step:6d} a={h["a"]:.5f} r={h["r"]:.4f} '
                  f'H={h["H"]:.5f} q={h["q_mean"]:.4f}', flush=True)

    a_arr, H_arr, w_arr = compute_w_from_snaps(snaps)
    w0, wa, reached, n_fit = fit_w0_wa(a_arr, w_arr)
    a_min_l, a_max_l = a_arr[0], a_arr[-1]
    omq_early = (np.mean([1.0 - s['q_mean'] for s in snaps
                          if 0.30 <= s['a'] <= 0.45])
                 if a_max_l >= 0.3 else np.nan)
    omq_late = (np.mean([1.0 - s['q_mean'] for s in snaps
                         if s['a'] >= 0.85])
                if a_max_l >= 0.85 else np.nan)
    res = dict(gate_model=gate, seed=args.seed,
               steps_done=snaps[-1]['step'] if snaps else 0,
               a_min_log=a_min_l, a_max_log=a_max_l,
               fit_window_reached=reached, fit_n=n_fit, w0=w0, wa=wa,
               omq_early=omq_early, omq_late=omq_late,
               omq_delta=(None if (omq_early != omq_early or
                                   omq_late != omq_late)
                          else omq_late - omq_early))
    with open(os.path.join(run_dir, 'results.json'), 'w') as f:
        json.dump(res, f, indent=1)

    print(f'\n[{gate}] a range {a_min_l:.4f} -> {a_max_l:.4f} '
          f'(window reached: {reached})')
    print(f'[{gate}] w0 = {w0:.4f}   wa = {wa:+.4f}   (fit over {n_fit} pts)')
    if res['omq_delta'] is not None:
        print(f'[{gate}] <1-q>: early {omq_early:.4f} -> late {omq_late:.4f} '
              f'(delta {res["omq_delta"]:+.4f})')
    return run_dir, res


def latest_results(suffix):
    cands = sorted(glob.glob(os.path.join('runs', '*' + suffix,
                                          'results.json')),
                   key=os.path.getmtime)
    if not cands:
        return None
    with open(cands[-1]) as f:
        return json.load(f)


def print_comparison(seed):
    rows = {}
    for gate in ARMS:
        res = latest_results(f'_wa_{gate}')
        if res is None:
            res = latest_results(f'_pde_wa') if gate == 'single' else None
        if res is not None and (seed is None or res['seed'] == seed):
            rows[gate] = res

    print('\n═══ GATE COMPARISON (PDE, N=32) ═══')
    if 'single' not in rows:
        print('  (no single-channel results found — run --arms single)')
        return
    s = rows['single']
    print(f"  {'gate':>8s} {'w0':>8s} {'wa':>8s} {'dwa vs single':>14s} "
          f"{'d(1-q)':>8s} {'a_max':>8s}")
    for gate in ARMS:
        if gate not in rows:
            continue
        r = rows[gate]
        dwa = r['wa'] - s['wa']
        d = r['omq_delta']
        print(f"  {gate:>8s} {r['w0']:8.4f} {r['wa']:+8.4f} {dwa:+14.4f} "
              f"{d if d is not None else float('nan'):8.4f} "
              f"{r['a_max_log']:8.4f}")
    print()
    print('  ODE baselines (from two-fluid/calibrate_initial_ratio_xi_v2.py,')
    print('  wa_full_ode.py): bare w0=-0.856 wa=+0.457 | +xi(phi^6, yang-frac)')
    print('  w0=-0.87 wa=+0.012 (Calibrated) | ratified conv->expansion')
    print('  coupling: wa ~ -0.38 | DESI DR2: wa ~ -0.73 +- 0.28 [INFERENCE]')
    flip = None
    for gate in ('five_ke', 'five'):
        r = rows.get(gate)
        if r and r['fit_window_reached'] and r['wa'] < 0:
            flip = gate
            break
    if flip:
        print(f'  *** {flip} w_a SIGN FLIPPED (negative) ***')
    else:
        print('  No sign flip: w_a stays positive in every gate arm '
              '(H = H_empty + H_conv is monotone decreasing in r, so the')
        print('  bare conversion-mode PDE cannot produce w_a < 0; the DESI-')
        print('  direction shift requires the xi / ratified H couplings,')
        print('  which are not in this PDE configuration)')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='5-channel vs single w(a) PDE')
    p.add_argument('--arms', type=str, default=','.join(ARMS),
                   help='comma list of gate models to run: ' + ','.join(ARMS))
    p.add_argument('--steps', type=int, default=None)
    p.add_argument('--dt-cap', type=float, default=DT_CAP_DEFAULT)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--log-every', type=int, default=500)
    p.add_argument('--ckpt-every', type=int, default=5000)
    p.add_argument('--resume', type=str, default=None)
    p.add_argument('--device', type=str, default='cpu',
                   help="'cpu' or 'cuda' (all arms must share a device)")
    args = p.parse_args()

    arms = [a.strip() for a in args.arms.split(',') if a.strip()]
    for a in arms:
        if a not in ARMS:
            print(f'[ERROR] unknown gate model: {a}'); sys.exit(1)
        if args.resume and len(arms) > 1:
            print('[ERROR] --resume takes exactly one arm'); sys.exit(1)

    for i, gate in enumerate(arms):
        if i:
            print()
        run_arm(gate, args)

    print_comparison(args.seed)
