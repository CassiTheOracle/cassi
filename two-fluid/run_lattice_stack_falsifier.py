#!/usr/bin/env python3
"""M-star law falsifier arms (wave 3 of the lattice-stack program).

Run:  python two-fluid/run_lattice_stack_falsifier.py
      (--steps N, --arm TAG repeatable, --init-check, --from-runs DIR)

Reuses the committed run_lattice_stack2_probe machinery (imported
read-only); same protocol: fresh solver per arm, N = 48, gate 'five',
dt = 0.001, t = 40 = 2/lambda, canonical solver untouched, zero new
terms, no registry changes.

Tests the section 3.11 candidate law M*(dtheta) = (32 pi^2/25)/dtheta^2
(tiered Hypothesized, two-point) and the section 3.10/3.11 B5 readings:

  f1: dtheta = 3 pi/10, M = 8    law: M* = 14.22 -> predict FAIL
                                 (C_abs(40) < 0.5)
  f2: dtheta = 3 pi/10, M = 16   law: M* = 14.22 -> predict PASS
  f3: dtheta = 2 pi/5,  M = 32   regime control: law predicts fail ~0.28
                                 (M >> M* = 8 at the 1.5-cell spacing);
                                 a pass would void the law by extending
                                 the continuous-ramp regime to 2 pi/5
  f4: dtheta = 2 pi/5,  M = 5    the unrun null arm: the pentagon cycle
                                 closes (A_tot(0) = 0 exact), the
                                 lobe-1/lobe-2 divider of the z-integrated
                                 profile; report the emergence behavior
  f5: dtheta = pi/2,    M = 6    law: M* = 5.12 -> predict PASS
  f6: dtheta = pi/2,    M = 8    two closed 4-cycles: A_tot(0) = 0 exact
                                 -> predict null-fail at the law level;
                                 report the emergence behavior
  f7: b2_pi rotated by +pi/2     clamp-free variant (no layer touches the
                                 floor): predicts the t = 0 residual drops
                                 to ~1e-14 (clamp-seed test) and the
                                 unmasking is slower than b2_pi's 0.861
                                 at t = 4

Output: runs/<rid>_lattice_stack_f/run_<arm>.json + results.json (raw;
NO doc changes, NO commit until the director reads the raw outputs).
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_trauma_wake_lock as T
import run_lattice_stack_probe as L1
import run_lattice_stack2_probe as L2

T.LAM = 0.05
T.DT = 0.001
T.REPORT = 50
STEPS = 40000
S_TOT = float(2.0 * L2.RHO0 * L2.BETA * (2.0 * np.pi) ** 1.5 * L2.SIG ** 3)

DTH_A = 3.0 * np.pi / 10.0


def lin(M, dth):
    return [i * dth for i in range(M)]


ARMS = [
    ('f1', lin(8, DTH_A), None,
     {'kind': 'fail', 'law_Mstar': 14.22,
      'note': 'M=8 < M*=14.22 at 3pi/10: predict C_abs(40) < 0.5'}),
    ('f2', lin(16, DTH_A), None,
     {'kind': 'pass', 'law_Mstar': 14.22,
      'note': 'M=16 > M*=14.22 at 3pi/10: predict C_abs(40) >= 0.5'}),
    ('f3', lin(32, 2.0 * np.pi / 5.0), None,
     {'kind': 'regime_control', 'predict_C_abs_40': 0.28,
      'note': 'M=32 >> M*=8 at 2pi/5, 1.5-cell spacing: law predicts fail '
              '~0.28; a pass voids the law (continuous-ramp extends to 2pi/5)'}),
    ('f4', lin(5, 2.0 * np.pi / 5.0), None,
     {'kind': 'null',
      'note': 'M=5 closes the pentagon cycle: A_tot(0) = 0 exact, '
              'C_abs(0) = 0 (lobe-1/lobe-2 divider of the z-integrated '
              'profile); report the emergence behavior at t=4/t=40'}),
    ('f5', lin(6, np.pi / 2.0), None,
     {'kind': 'pass', 'law_Mstar': 5.12,
      'note': 'M=6 > M*=5.12 at pi/2: predict C_abs(40) >= 0.5'}),
    ('f6', lin(8, np.pi / 2.0), None,
     {'kind': 'null_fail',
      'note': 'M=8 = two closed 4-cycles: A_tot(0) = 0 exact -> null-fail '
              'at the law level; report the emergence behavior'}),
    ('f7', [r * np.pi + i * 2.0 * np.pi / 5.0 + 2.0 * np.pi / 3.0
            for r in (0, 1) for i in range(4)], [0] * 4 + [1] * 4,
     {'kind': 'clamp_free',
      'note': 'b2_pi rotated by +2pi/3 (global; A1 = 0 preserved): the '
              'zero-floor rotation (CPU scan: 0/0 floor cells, min fields '
              '0.029/0.022); predict residual -> 1e-14 (clamp-seed test: '
              'the unclamped rung sum cancels exactly) and slower '
              'unmasking than b2_pi (C_abs(4) < 0.861)'}),
]


def run_arm(device, tag, phases, rung_of, outdir, steps):
    solver = T.build_solver(device)          # fresh solver per arm
    r = L2.run_case2(solver, tag, phases, rung_of, outdir, steps)
    r['summary'] = L2.summarize2(r)
    return r


def finalize(runs, rdir):
    def arm(tag):
        return next((r for r in runs if r['tag'] == tag), None)

    results = {'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT,
                        't_end': runs[0]['hist'][-1]['t'],
                        'wave': 'M-star law falsifier arms',
                        'law_under_test': 'M*(dtheta) = (32 pi^2/25)/dtheta^2 '
                                          '(Hypothesized, two-point)'},
               'arms': {}}
    for r in runs:
        results['arms'][r['tag']] = {
            'phases': r['phases'], 'n_layers': r['n_layers'],
            'n_rungs': r['n_rungs'],
            'resonance_t0': r['resonance_t0'], 'summary': r['summary'],
            'elapsed_s': r['elapsed']}

    def c40(tag):
        s = arm(tag)['summary']
        return s['t40']['C_abs']

    print(f"\n=== M-STAR LAW FALSIFIER ARMS (t=40) ===")
    verdicts = {}
    for tag, phases, rung_of, pred in ARMS:
        r = arm(tag)
        if r is None:
            print(f"  {tag}: not in this run set")
            continue
        rt = r['resonance_t0']
        s = r['summary']
        kind = pred['kind']
        line = (f"  {tag}: A_tot(0)={rt['A_tot']:9.3f} "
                f"ratio={rt['ratio_vs_analytic']:.5f} "
                f"floors={rt['floor_ey'] + rt['floor_ei']:5d} | "
                f"C_abs 0/4/40 = {s['t0']['C_abs']:+.3f}/"
                f"{s['t4']['C_abs']:+.3f}/{s['t40']['C_abs']:+.3f} | "
                f"A_peak(40)/A_peak(0)={s['A_peak_ratio_t40']:.3f} "
                f"wind(40)={s['t40']['winding']:+.3f} | "
                f"mass drift {s['mass_drift']:.2e} NaN {s['nan']}")
        v = None
        if kind == 'fail':
            v = 'CONFIRMED (fail)' if c40(tag) < 0.5 else \
                'CONTRADICTED (pass)'
        elif kind == 'pass':
            v = 'CONFIRMED (pass)' if c40(tag) >= 0.5 else \
                'CONTRADICTED (fail)'
        elif kind == 'regime_control':
            v = 'LAW VOIDED (continuous-ramp passes at 2pi/5)' \
                if c40(tag) >= 0.5 else 'law holds (fail as predicted)'
        elif kind == 'null':
            v = 'CONFIRMED (exact null)' if rt['A_tot'] < 1e-6 * S_TOT \
                else 'UNEXPECTED (non-null)'
        elif kind == 'null_fail':
            v = 'CONFIRMED (null-fail)' if rt['A_tot'] < 1e-6 * S_TOT \
                else 'UNEXPECTED (non-null)'
        elif kind == 'clamp_free':
            residual_ok = rt['A_tot'] < 1e-6 * S_TOT
            slow_ok = s['t4']['C_abs'] < 0.861
            v = f"residual->1e-14: {'CONFIRMED' if residual_ok else 'REFUTED'} " \
                f"(A_tot={rt['A_tot']:.3e}); slower unmasking: " \
                f"{'CONFIRMED' if slow_ok else 'REFUTED'} " \
                f"(C_abs(4)={s['t4']['C_abs']:.3f} vs b2_pi 0.861)"
        verdicts[tag] = {'prediction': pred, 'verdict': v}
        print(line)
        print(f"     prediction [{pred['kind']}]: {pred['note']}")
        print(f"     -> {v}")

    results['verdicts'] = verdicts
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults: {rdir}/results.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--steps', type=int, default=STEPS)
    parser.add_argument('--tend', type=float, default=None,
                        help='run to physical time tend (steps = tend/dt); '
                             'overrides --steps')
    parser.add_argument('--arm', action='append', default=None)
    parser.add_argument('--init-check', action='store_true')
    parser.add_argument('--from-runs', default=None, metavar='DIR')
    args = parser.parse_args()

    if args.from_runs is not None:
        import glob as _glob
        runs = []
        for f in sorted(_glob.glob(f"{args.from_runs}/run_*.json")):
            d = json.load(open(f))
            runs.append({'tag': d['kind'], 'phases': d['phases'],
                         'rung_of': d['rung_of'], 'elapsed': 0.0,
                         'resonance_t0': d['resonance_t0'],
                         'hist': d['hist'], 'profiles': d['profiles'],
                         'n_layers': d['n_layers'],
                         'n_rungs': d['n_rungs']})
            runs[-1]['summary'] = L2.summarize2(runs[-1])
        print(f"Rebuilding from {len(runs)} preserved arms in {args.from_runs}")
        finalize(runs, args.from_runs)
        return

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if args.tend is not None:
        args.steps = int(round(args.tend / T.DT))
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t={args.steps * T.DT}  "
          f"law under test: M*(dtheta) = (32 pi^2/25)/dtheta^2")
    arms = ARMS
    if args.arm is not None:
        arms = [a for a in arms if a[0] in args.arm]
        if not arms:
            raise SystemExit(f"no matching arms in {[a[0] for a in arms]}")
    print(f"Arms: {', '.join(a[0] for a in arms)}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_lattice_stack_f"
    os.makedirs(rdir, exist_ok=True)

    if args.init_check:
        for tag, phases, rung_of, pred in arms:
            solver = T.build_solver(device)
            ey_hat, ei_hat, u_hat, zs = L2.stack_init_phases(solver, phases)
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            windows = L1.layer_windows(solver.N, zs, solver.device)
            rt = L2.resonance_t0(solver, ey, ei, windows, zs, phases, 0.0, 0.0)
            print(f"  {tag}: A_tot={rt['A_tot']:10.3f} "
                  f"ratio={rt['ratio_vs_analytic']:.5f} "
                  f"min={rt['min_ey']:.4f}/{rt['min_ei']:.4f} "
                  f"floors={rt['floor_ey']}/{rt['floor_ei']}")
        print(f"(init check only; {len(arms)} arms)")
        return

    runs = []
    for tag, phases, rung_of, pred in ARMS:
        if args.arm is not None and tag not in args.arm:
            continue
        runs.append(run_arm(device, tag, phases, rung_of, rdir, args.steps))
    finalize(runs, rdir)


if __name__ == "__main__":
    main()
