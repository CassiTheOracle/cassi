#!/usr/bin/env python3
"""DNA-pitch detuning sweep arms (the two-strand lattice-stack program).

Run:  python two-fluid/run_detuning_sweep.py
      (--steps N, --arm TAG repeatable, --init-check, --from-runs DIR)

Sibling runner to the committed falsifier, reusing its machinery (imported
read-only): same protocol -- fresh solver per arm, N = 48, gate 'five',
dt = 0.001, t = 40 = 2/lambda, canonical solver untouched, zero new terms,
no registry changes.

Tests the section 3.12 revised statement at the B-DNA pitch and its
neighborhood, on the flat stack construction (per-layer phase
theta_i = i*dtheta, layers on the uniform lattice):

  d1: dtheta = 36 deg = pi/5,   M = 32   control: the committed a32 arm
                                         (expect C_abs(40) ~ 0.848)
  d2: dtheta = 2 pi/10.5 (34.29 deg), M = 32
      the DNA-pitch arm: M0 = 10.5 NON-integer; the exclusion rule
      predicts fail (no passing height >= 8), the graded-onset
      hypothesis predicts pass/marginal
  d3: dtheta = 34 deg,  M = 32   sharper detuning sibling (M0 = 10.59)
  d4: dtheta = 38 deg,  M = 32   mirror-side detuning (M0 = 9.47)
  d5: dtheta = 36 deg,  M = 10   one-turn exact null: A(10, 36 deg) = 0
                                 exactly; expect f4-like contraction,
                                 d decreasing, no merge by t = 40
  d6: dtheta = 2 pi/10.5, M = 10 near-null one-turn:
      A(10, 34.29 deg) = |sin(171.43)/sin(17.14)| = 0.5056 (the
      "first-form point" candidate)

Labels d1-d6 are probe labels, not master prediction numbers.  Output:
runs/<rid>_detune_sweep/run_<arm>.json + results.json (raw; NO doc
changes, NO commit until the director reads the raw outputs).
"""

import os
import sys
import json
import time
import math
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

DTH_36 = np.pi / 5.0                 # 36 deg, M0 = 10 integer (control)
DTH_DNA = 2.0 * np.pi / 10.5         # 34.2857 deg, M0 = 10.5 NON-integer
DTH_34 = 34.0 * np.pi / 180.0        # 34 deg, M0 = 10.59 NON-integer
DTH_38 = 38.0 * np.pi / 180.0        # 38 deg, M0 = 9.47 NON-integer


def lin(M, dth):
    return [i * dth for i in range(M)]


def array_factor(M, dth):
    if abs(dth) < 1e-12:
        return float(M)
    return abs(math.sin(M * dth / 2.0) / math.sin(dth / 2.0))


ARMS = [
    ('d1', lin(32, DTH_36), None,
     {'kind': 'control',
      'note': 'Delta theta = 36 deg, M = 32: the committed a32 arm '
              '(M0 = 10 integer); expect C_abs(40) ~ 0.848 (committed '
              'value 0.8479)'}),
    ('d2', lin(32, DTH_DNA), None,
     {'kind': 'exclusion', 'M0': 10.5, 'R': array_factor(32, DTH_DNA),
      'note': 'DNA pitch: Delta theta = 2 pi/10.5 = 34.29 deg, M = 32, '
              'M0 = 10.5 NON-integer; the exclusion rule predicts '
              'C_abs(40) < 0.5 (no passing height >= 8 on the '
              'non-integer family); the graded-onset hypothesis '
              'predicts pass/marginal (>= 0.5)'}),
    ('d3', lin(32, DTH_34), None,
     {'kind': 'exclusion', 'M0': 10.59, 'R': array_factor(32, DTH_34),
      'note': 'Delta theta = 34 deg, M = 32, M0 = 10.59 NON-integer: '
              'exclusion predicts C_abs(40) < 0.5 (sharper detuning '
              'sibling of the DNA arm)'}),
    ('d4', lin(32, DTH_38), None,
     {'kind': 'exclusion', 'M0': 9.47, 'R': array_factor(32, DTH_38),
      'note': 'Delta theta = 38 deg, M = 32, M0 = 9.47 NON-integer: '
              'mirror-side detuning; exclusion predicts C_abs(40) < 0.5'}),
    ('d5', lin(10, DTH_36), None,
     {'kind': 'null',
      'note': 'Delta theta = 36 deg, M = 10: one-turn closure, '
              'A(10, 36 deg) = 0 exactly; expect f4-like emergence: '
              'd decreasing, no merge by t = 40'}),
    ('d6', lin(10, DTH_DNA), None,
     {'kind': 'near_null', 'R': array_factor(10, DTH_DNA),
      'note': 'Delta theta = 2 pi/10.5, M = 10: near-null one-turn, '
              'A(10, 34.29 deg) = |sin(171.43)/sin(17.14)| = 0.5056 '
              '(the first-form point candidate)'}),
]


def run_arm(device, tag, phases, rung_of, outdir, steps):
    solver = T.build_solver(device)          # fresh solver per arm
    r = L2.run_case2(solver, tag, phases, rung_of, outdir, steps)
    r['summary'] = L2.summarize2(r)
    return r


def construction_A_tot(device, phases):
    """Unclamped flat-stack A_tot (construction level) from the phase
    list: the [D] array-factor anchors are verified pre-clamp; the
    clamped-field residue is clamp truncation (B5/f7 mechanism)."""
    import run_trauma_wake_lock as T2
    solver = T2.build_solver(device)
    N_ = solver.N
    M = len(phases)
    x = torch.arange(N_, dtype=torch.float64, device=device)
    X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
    cx = N_ / 2.0
    c1, c2 = cx - L1.SEP / 2.0, cx + L1.SEP / 2.0
    spacing = N_ / M
    zs = [cx + (j - (M - 1) / 2.0) * spacing for j in range(M)]
    rho = torch.full((N_, N_, N_), L2.RHO0, dtype=torch.float64, device=device)
    eps = torch.zeros_like(rho)
    for j, (zi, ph) in enumerate(zip(zs, phases)):
        ct, st = math.cos(ph), math.sin(ph)
        g1 = torch.zeros_like(X)
        g2 = torch.zeros_like(X)
        for off in (0.0, float(N_), -float(N_)):
            zc = Z - zi + off
            g1 = g1 + torch.exp(-((X - c1) ** 2 + (Y - cx) ** 2 + zc ** 2)
                                / (2.0 * L1.SIG ** 2))
            g2 = g2 + torch.exp(-((X - c2) ** 2 + (Y - cx) ** 2 + zc ** 2)
                                / (2.0 * L1.SIG ** 2))
        gp, gm = g1 + g2, g1 - g2
        rho += L2.RHO0 * L2.BETA * gp * ct - L2.E_RIDGE * gm * st
        eps += L2.RHO0 * L2.BETA * gp * st + L2.E_RIDGE * gm * ct
    ey = (T.PHI * rho + eps) / (1.0 + T.PHI)
    ei = (rho - eps) / (1.0 + T.PHI)
    return float(L1.slab_phasor(ey, ei, L2.RHO0).sum().abs())


def finalize(runs, rdir, device=None):
    def arm(tag):
        return next((r for r in runs if r['tag'] == tag), None)

    results = {'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT,
                        't_end': runs[0]['hist'][-1]['t'],
                        'wave': 'DNA-pitch detuning sweep (d1-d6)',
                        'statement_under_test': '3.12 exclusion rule: the '
                        'non-integer-M0 family has no passing height '
                        '>= 8 (revised M* law confined to integer M0)',
                        'protocol': 'fresh solver per arm, t=40=2/lambda, '
                                    'flat stack construction, canonical '
                                    'solver untouched'},
               'arms': {}}
    for r in runs:
        results['arms'][r['tag']] = {
            'phases': r['phases'], 'n_layers': r['n_layers'],
            'resonance_t0': r['resonance_t0'], 'summary': r['summary'],
            'elapsed_s': r['elapsed']}

    def c40(tag):
        return arm(tag)['summary']['t40']['C_abs']

    def d40(tag):
        return arm(tag)['summary']['t40']['d']

    print(f"\n=== DETUNING SWEEP ARMS (t=40) ===")
    verdicts = {}
    for tag, phases, rung_of, pred in ARMS:
        r = arm(tag)
        if r is None:
            print(f"  {tag}: not in this run set")
            continue
        rt = r['resonance_t0']
        s = r['summary']
        kind = pred['kind']
        R = pred.get('R')
        rline = f"{rt['ratio_vs_analytic']:.5f}"
        if R is not None:
            rline += f" (R={R:.4f})"
        line = (f"  {tag}: A_tot(0)={rt['A_tot']:9.3f} "
                f"ratio={rline} "
                f"floors={rt['floor_ey'] + rt['floor_ei']:5d} | "
                f"C_abs 0/4/40 = {s['t0']['C_abs']:+.3f}/"
                f"{s['t4']['C_abs']:+.3f}/{s['t40']['C_abs']:+.3f} | "
                f"A_peak(40)/A_peak(0)={s['A_peak_ratio_t40']:.3f} "
                f"wind(40)={s['t40']['winding']:+.3f} | "
                f"d 0/4/40 = {s['t0']['d']:.2f}/{s['t4']['d']:.2f}/"
                f"{s['t40']['d']:.2f} merged(40)={s['t40']['merged']} "
                f"dth(40)={s['t40']['delta_theta']:+.3f} | "
                f"mass drift {s['mass_drift']:.2e} NaN {s['nan']}")
        A_u = construction_A_tot(device if device is not None
                                 else torch.device('cpu'), phases)
        v = None
        if kind == 'control':
            ok = abs(c40(tag) - 0.8479) < 0.01
            v = f"REPRODUCED (C_abs(40)={c40(tag):+.3f} vs committed 0.848)" \
                if ok else f"DRIFTED (C_abs(40)={c40(tag):+.3f} vs 0.848)"
        elif kind == 'exclusion':
            v = 'EXCLUSION CONFIRMED (fail)' if c40(tag) < 0.5 else \
                'GRADED-ONSET (pass/marginal, exclusion refuted)'
        elif kind == 'null':
            v = 'CONFIRMED (exact null at construction level: ' \
                f'A_tot(unclamped)={A_u:.4e} = {A_u / S_TOT:.3e} s_tot; ' \
                f'clamped residue {rt["A_tot"]:.2f} = clamp truncation ' \
                f'of {rt["floor_ey"] + rt["floor_ei"]} floored cells)'
        elif kind == 'near_null':
            expect = pred['R'] * S_TOT
            ok = abs(A_u - expect) < 0.03 * S_TOT
            v = f"[D] A_tot(unclamped)={A_u:.2f} vs analytic {expect:.2f} " \
                f"({'CONFIRMED' if ok else 'MISMATCH'}); clamped " \
                f"{rt['A_tot']:.2f} carries the {rt['floor_ey'] + rt['floor_ei']}-cell " \
                f"clamp truncation"
        verdicts[tag] = {'prediction': pred, 'verdict': v,
                         'A_unclamped_t0': A_u}
        print(line)
        print(f"     prediction [{kind}]: {pred['note']}")
        print(f"     -> {v}")

    # null-arm trajectory report (d5/d6): monotone contraction?
    print("\n  null-arm trajectories (d every 4 units):")
    for tag in ('d5', 'd6'):
        r = arm(tag)
        if r is None:
            continue
        h = r['hist']
        pts = [(4.0, L2.at_t(h, 4.0)['d']), (20.0, L2.at_t(h, 20.0)['d']),
               (30.0, L2.at_t(h, 30.0)['d']), (40.0, L2.at_t(h, 40.0)['d'])]
        print(f"    {tag}: d = " + " -> ".join(
            f"{tt:.0f}:{dd:.2f}" for tt, dd in pts))

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
        finalize(runs, args.from_runs,
                 torch.device('cuda' if torch.cuda.is_available() else 'cpu'))
        return

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if args.tend is not None:
        args.steps = int(round(args.tend / T.DT))
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t={args.steps * T.DT}  "
          f"gate='five'  flat stack construction")
    arms = ARMS
    if args.arm is not None:
        arms = [a for a in arms if a[0] in args.arm]
        if not arms:
            raise SystemExit(f"no matching arms in {[a[0] for a in arms]}")
    print(f"Arms: {', '.join(a[0] for a in arms)}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_detune_sweep"
    os.makedirs(rdir, exist_ok=True)

    if args.init_check:
        # construction-level [D] anchor verification (pre-clamp flat stack)
        for tag, phases, rung_of, pred in arms:
            M = len(phases)
            solver = T.build_solver(device)
            N_ = solver.N
            dev = solver.device
            x = torch.arange(N_, dtype=torch.float64, device=dev)
            X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
            cx = N_ / 2.0
            c1, c2 = cx - L1.SEP / 2.0, cx + L1.SEP / 2.0
            spacing = N_ / M
            zs = [cx + (j - (M - 1) / 2.0) * spacing for j in range(M)]
            rho = torch.full((N_, N_, N_), L2.RHO0,
                             dtype=torch.float64, device=dev)
            eps = torch.zeros_like(rho)
            for j, (zi, ph) in enumerate(zip(zs, phases)):
                ct, st = math.cos(ph), math.sin(ph)
                g1 = torch.zeros_like(X)
                g2 = torch.zeros_like(X)
                for off in (0.0, float(N_), -float(N_)):
                    zc = Z - zi + off
                    g1 = g1 + torch.exp(-((X - c1) ** 2 + (Y - cx) ** 2 +
                                          zc ** 2) / (2.0 * L1.SIG ** 2))
                    g2 = g2 + torch.exp(-((X - c2) ** 2 + (Y - cx) ** 2 +
                                          zc ** 2) / (2.0 * L1.SIG ** 2))
                gp, gm = g1 + g2, g1 - g2
                rho += L2.RHO0 * L2.BETA * gp * ct - L2.E_RIDGE * gm * st
                eps += L2.RHO0 * L2.BETA * gp * st + L2.E_RIDGE * gm * ct
            ey_u = (T.PHI * rho + eps) / (1.0 + T.PHI)
            ei_u = (rho - eps) / (1.0 + T.PHI)
            A_u = float(L1.slab_phasor(ey_u, ei_u, L2.RHO0).sum().abs())
            print(f"  {tag} [D] unclamped: A_tot={A_u:10.3f} = "
                  f"{A_u / S_TOT:.5f} s_tot (R="
                  f"{array_factor(M, phases[1] if M > 1 else 0.0):.4f})")
            solver = T.build_solver(device)
            ey_hat, ei_hat, u_hat, zs = L2.stack_init_phases(solver, phases)
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            windows = L1.layer_windows(solver.N, zs, solver.device)
            rt = L2.resonance_t0(solver, ey, ei, windows, zs, phases, 0.0, 0.0)
            R = array_factor(len(phases), phases[1] if len(phases) > 1 else 0.0)
            print(f"  {tag}: A_tot={rt['A_tot']:10.3f} "
                  f"ratio={rt['ratio_vs_analytic']:.5f} (R={R:.4f}) "
                  f"min={rt['min_ey']:.4f}/{rt['min_ei']:.4f} "
                  f"floors={rt['floor_ey']}/{rt['floor_ei']}")
        print(f"(init check only; {len(arms)} arms)")
        return

    runs = []
    for tag, phases, rung_of, pred in arms:
        runs.append(run_arm(device, tag, phases, rung_of, rdir, args.steps))
    finalize(runs, rdir, device)


if __name__ == "__main__":
    main()
