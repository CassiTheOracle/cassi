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

Wave 4 tests the revised statement (section 3.12): M* = ceil((32 pi^2/25)
/dtheta^2) on the integer-M0 family (M0 = 2 pi/dtheta), no passing height
>= 8 on the non-integer family (structural exclusion):

  f8:  dtheta = pi/4,  M = 16   M0 = 8 integer, M* = 21 -> predict FAIL
                                 (C_abs(40) < 0.5); a pass voids the law
                                 (construction is an exact null: two
                                 closed 8-cycles, A_tot(0) = 0)
  f9:  dtheta = pi/4,  M = 32   M* = 21 -> predict PASS (C_abs(40) >= 0.5);
                                 a fail voids the law (also an exact null:
                                 four closed 8-cycles)
  f10: dtheta = pi/3,  M = 8    M0 = 6 integer, M* = 12 -> predict FAIL;
                                 A(8, 60 deg) = |sin 240 / sin 30| = sqrt(3)
                                 = 1.732 (non-null construction)
  f11: dtheta = pi/3,  M = 16   M* = 12 -> predict PASS
  f12: dtheta = pi/6,  M = 32   M0 = 12 integer, M* = 47 -> predict FAIL
  f13: dtheta = 3 pi/5, M = 16  M0 = 10/3 NON-integer -> predict FAIL
                                 (exclusion control #1; a pass voids the
                                 integer-M0 exclusion)
  f14: dtheta = 27 deg, M = 16  M0 = 40/3 NON-integer -> predict FAIL
                                 (exclusion control #2)
  s1:  two rungs x M = 5 null pentagon rings (f4 construction), inter-rung
       phase dtheta_2 = pi/5 (A1 = 2 cos(pi/10) = 1.9021, A2 = 0 exact),
       run to t = 80 = 4/lambda: does the stack hold the f4 contraction
       (d 10.07 -> 2.57 at t = 40, turned around to 5.39 at t = 80) longer?
       The t = 160 = 8/lambda continuation (--tend 160; run record
       20260807_223143_lattice_stack_f) is the stacked-null discriminator:
       d bottoms at t ~ 82 at the t = 80 minimum (7.51), then relaxes to
       12.11 = d(0) by t = 160 (suppression reading).

Clean reruns (f7 recipe): arms whose init touched the 1e-3 clamp are
rerun with a common global phase rotation alpha chosen so that no
unclamped field value drops below the floor (--scan-rotation finds the
angle; --rot DEG applies it). A global rotation preserves A_tot(0)
(|sum e^{i(theta_j + alpha)}| invariant) and drops the clamp residue to
float-exact (the section 3.11(c)/f7 theorem), making the t = 0 envelope
flat: the rerun is the clean formation test.

Output: runs/<rid>_lattice_stack_f/run_<arm>.json + results.json (raw;
NO doc changes, NO commit until the director reads the raw outputs).
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

DTH_A = 3.0 * np.pi / 10.0

# wave-4 steps (revised-law falsifier)
DTH_45 = np.pi / 4.0                      # M0 = 8 (integer)
DTH_60 = np.pi / 3.0                      # M0 = 6 (integer)
DTH_30 = np.pi / 6.0                      # M0 = 12 (integer)
DTH_108 = 3.0 * np.pi / 5.0               # M0 = 10/3 (non-integer)
DTH_27 = 27.0 * np.pi / 180.0             # M0 = 40/3 (non-integer)


def lin(M, dth):
    return [i * dth for i in range(M)]


def scan_rotation_clean(device, phases, n=720):
    """f7 recipe: scan a global phase rotation alpha (every layer rotated
    by the same angle) for the largest minimum of the unclamped linear
    fields; returns the first candidate with zero floor contact, else the
    max-min candidate. Uses the construction's rotation linearity:
        rho(a) = RHO0 + cos(a) SA - sin(a) SB,  eps(a) = sin(a) SA + cos(a) SB
    with SA = sum_j (RHO0 BETA gp_j cos th_j - E_RIDGE gm_j sin th_j),
        SB = sum_j (RHO0 BETA gp_j sin th_j + E_RIDGE gm_j cos th_j).
    The chosen angle is verified against the exact construction path
    (L2.stack_init_phases with rotated phases) before use."""
    N_ = T.N
    x = torch.arange(N_, dtype=torch.float64, device=device)
    X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
    cx = N_ / 2.0
    c1, c2 = cx - L2.SEP / 2.0, cx + L2.SEP / 2.0
    M = len(phases)
    spacing = N_ / M
    zs = [cx + (j - (M - 1) / 2.0) * spacing for j in range(M)]
    offsets = (0.0, float(N_), -float(N_))
    SA = torch.zeros_like(X)
    SB = torch.zeros_like(X)
    for j, (zi, ph) in enumerate(zip(zs, phases)):
        ct, st = math.cos(ph), math.sin(ph)
        g1 = torch.zeros_like(X)
        g2 = torch.zeros_like(X)
        for off in offsets:
            zc = Z - zi + off
            g1 = g1 + torch.exp(-((X - c1) ** 2 + (Y - cx) ** 2 + zc ** 2)
                                / (2.0 * L2.SIG ** 2))
            g2 = g2 + torch.exp(-((X - c2) ** 2 + (Y - cx) ** 2 + zc ** 2)
                                / (2.0 * L2.SIG ** 2))
        gp = g1 + g2
        gm = g1 - g2
        SA = SA + L2.RHO0 * L2.BETA * gp * ct - L2.E_RIDGE * gm * st
        SB = SB + L2.RHO0 * L2.BETA * gp * st + L2.E_RIDGE * gm * ct
    best = None
    for k in range(n):
        a = 2.0 * np.pi * k / n
        ca, sa = math.cos(a), math.sin(a)
        rho = L2.RHO0 + ca * SA - sa * SB
        eps = sa * SA + ca * SB
        ey = (T.PHI * rho + eps) / (1.0 + T.PHI)
        ei = (rho - eps) / (1.0 + T.PHI)
        fe = int((ey <= 1e-3 + 1e-12).sum().item())
        fi = int((ei <= 1e-3 + 1e-12).sum().item())
        mn = min(float(ey.min()), float(ei.min()))
        if fe + fi == 0:
            return {'alpha': a, 'alpha_deg': np.degrees(a), 'min': mn,
                    'floors_ey': fe, 'floors_ei': fi,
                    'n_candidates': k + 1}
        if best is None or mn > best['min']:
            best = {'alpha': a, 'alpha_deg': np.degrees(a), 'min': mn,
                    'floors_ey': fe, 'floors_ei': fi,
                    'n_candidates': k + 1}
    return best


def verify_rotation(device, phases, alpha):
    """Exact-path check: floor contact of the clamped construction at the
    chosen rotation (L2.stack_init_phases + ifftn, as in run_case2)."""
    solver = T.build_solver(device)
    ey_hat, ei_hat, _, _ = L2.stack_init_phases(
        solver, [p + alpha for p in phases])
    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    return {'floors_ey': int((ey <= 1e-3 + 1e-12).sum().item()),
            'floors_ei': int((ei <= 1e-3 + 1e-12).sum().item()),
            'min_ey': float(ey.min()), 'min_ei': float(ei.min())}


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
    # wave 4: the revised law (integer-M0 ceiling + non-integer exclusion)
    ('f8', lin(16, DTH_45), None,
     {'kind': 'fail', 'law_Mstar': 21, 'M0': 8,
      'note': 'M=16 < M*=21 at pi/4 (M0=8 integer): predict C_abs(40) < 0.5; '
              'a pass voids the revised law (exact null: two closed '
              '8-cycles, A_tot(0) = 0)'}),
    ('f9', lin(32, DTH_45), None,
     {'kind': 'pass', 'law_Mstar': 21, 'M0': 8,
      'note': 'M=32 > M*=21 at pi/4: predict C_abs(40) >= 0.5; a fail voids '
              'the revised law (exact null: four closed 8-cycles)'}),
    ('f10', lin(8, DTH_60), None,
     {'kind': 'fail', 'law_Mstar': 12, 'M0': 6,
      'note': 'M=8 < M*=12 at pi/3 (M0=6 integer); A(8,60deg) = '
              '|sin(240)/sin(30)| = sqrt(3) = 1.732 (non-null): predict '
              'C_abs(40) < 0.5'}),
    ('f11', lin(16, DTH_60), None,
     {'kind': 'pass', 'law_Mstar': 12, 'M0': 6,
      'note': 'M=16 > M*=12 at pi/3: predict C_abs(40) >= 0.5; a fail voids '
              'the revised law'}),
    ('f12', lin(32, DTH_30), None,
     {'kind': 'fail', 'law_Mstar': 47, 'M0': 12,
      'note': 'M=32 < M*=47 at pi/6 (M0=12 integer): predict C_abs(40) < 0.5'}),
    ('f13', lin(16, DTH_108), None,
     {'kind': 'excl_fail', 'M0': '10/3',
      'note': 'exclusion control #1: M0 = 10/3 NON-integer at 3pi/5; the '
              'non-integer family has no passing height >= 8 -> predict '
              'C_abs(40) < 0.5; a pass voids the integer-M0 exclusion'}),
    ('f14', lin(16, DTH_27), None,
     {'kind': 'excl_fail', 'M0': '40/3',
      'note': 'exclusion control #2: M0 = 40/3 NON-integer at 27deg; the '
              'non-integer family has no passing height >= 8 -> predict '
              'C_abs(40) < 0.5; a pass voids the integer-M0 exclusion'}),
    ('s1', [r * np.pi / 5.0 + i * 2.0 * np.pi / 5.0
            for r in (0, 1) for i in range(5)], [0] * 5 + [1] * 5,
     {'kind': 'stacked_null',
      'note': 'two rungs x M=5 null pentagon rings (f4 construction), '
              'inter-rung phase dtheta_2 = pi/5 (A1 = 2cos(pi/10) = 1.9021, '
              'A2 = 0 exact): does the stack hold the f4 contraction '
              '(d 10.07 -> 2.57 at t=40, -> 5.39 at t=80) longer? '
              'run to t = 80 = 4/lambda; report d(t), C_abs(t), merged, '
              'floors'}),
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
                        'wave': 'M-star law falsifier arms '
                                '(f1-f7 + revised-law wave f8-f14, s1)',
                        'law_under_test': 'M*(dtheta) = ceil((32 pi^2/25)'
                                          '/dtheta^2) on integer M0; '
                                          'non-integer M0 excluded (revised '
                                          'statement, section 3.12)'},
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
                f"d 0/4/40 = {s['t0']['d']:.2f}/{s['t4']['d']:.2f}/"
                f"{s['t40']['d']:.2f} dth(40)={s['t40']['delta_theta']:+.3f} "
                f"merged(40)={s['t40']['merged']} | "
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
        elif kind == 'excl_fail':
            v = 'CONFIRMED (exclusion)' if c40(tag) < 0.5 else \
                'EXCLUSION VOIDED (pass)'
        elif kind == 'stacked_null':
            t80 = min(r['hist'], key=lambda d: abs(d['t'] - 80.0))
            v = (f"t=80: d {s['t0']['d']:.2f}->{s['t40']['d']:.2f}->"
                 f"{t80['d']:.2f} | C_abs {s['t0']['C_abs']:+.3f}/"
                 f"{s['t40']['C_abs']:+.3f}/{t80['C_abs']:+.3f} | "
                 f"dth(40)={s['t40']['delta_theta']:+.3f} "
                 f"dth(80)={t80['delta_theta']:+.3f} | "
                 f"merged(40)={s['t40']['merged']} merged(80)={t80['merged']} | "
                 f"A_peak(80)/A_peak(0)="
                 f"{t80['A_peak'] / max(s['t0']['A_peak'], 1e-30):.3f} | "
                 f"floors={rt['floor_ey'] + rt['floor_ei']} | "
                 f"mass drift {s['mass_drift']:.2e} NaN {s['nan']}")
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
    parser.add_argument('--rot', type=float, default=0.0, metavar='DEG',
                        help='global phase rotation (deg) applied to every '
                             'layer of every selected arm (f7 clamp-free '
                             'recipe)')
    parser.add_argument('--scan-rotation', action='store_true',
                        help='scan a global phase rotation with zero floor '
                             'contact for each selected arm, print, exit')
    parser.add_argument('--reflect', action='store_true',
                        help='with --scan-rotation: scan the reflected '
                             'family instead (phases -> -phases, the '
                             'doublet mirror; A_tot invariant)')
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
          f"law under test: M*(dtheta) = ceil((32 pi^2/25)/dtheta^2) "
          f"on integer M0; non-integer M0 excluded")
    arms = ARMS
    if args.arm is not None:
        arms = [a for a in arms if a[0] in args.arm]
        if not arms:
            raise SystemExit(f"no matching arms in {[a[0] for a in arms]}")
    print(f"Arms: {', '.join(a[0] for a in arms)}")

    if args.scan_rotation:
        fam = 'reflected (phases -> -phases)' if args.reflect else 'identity'
        print(f"(scanning a zero-floor global rotation per arm; "
              f"family: {fam}; {args.arm or 'all'})")
        for tag, phases, rung_of, pred in arms:
            if args.reflect:
                phases = [-p for p in phases]
            sc = scan_rotation_clean(device, phases)
            vf = verify_rotation(device, phases, sc['alpha'])
            print(f"  {tag}: alpha={sc['alpha_deg']:.3f} deg "
                  f"(min {sc['min']:.4f}, scan floors "
                  f"{sc['floors_ey']}/{sc['floors_ei']} over "
                  f"{sc['n_candidates']} candidates) | exact-path floors "
                  f"{vf['floors_ey']}/{vf['floors_ei']} "
                  f"min {vf['min_ey']:.4f}/{vf['min_ei']:.4f}")
        print("(scan only; rerun with --rot DEG)")
        return

    if args.rot:
        print(f"Global phase rotation: +{args.rot:.3f} deg applied to all "
              f"selected arms (f7 clamp-free recipe)")
        arms = [(t, [p + math.radians(args.rot) for p in ph], ro, pr)
                for t, ph, ro, pr in arms]

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
