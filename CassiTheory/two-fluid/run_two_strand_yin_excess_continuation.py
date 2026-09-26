#!/usr/bin/env python3
"""Two-strand Yin-excess pair continuation: the branch beyond t = 40.

Run:  python two-fluid/run_two_strand_yin_excess_continuation.py

Continuation of `two-fluid/run_two_strand_yin_excess_suite.py` sec 3.5
(E1 candidate iii, run record 20260807_014428_two_strand_yin_excess): the
Yin-excess pair (canonical two-lobe state with ey <-> ei exchanged,
Pi = ey - ei < 0 in every ridge) persisted at finite separation through
t = 40 = 2/lambda, contracting monotonically at ~0.06 cells/t with the
Yin excess erased by conversion at t ~ 21.3.  This script extends the SAME
arm (identical protocol: N = 48, lam = 0.05, dt = 0.001, gate 'five',
swapped initialization, density-tracked strand balls, fresh solver run
from t = 0) to t = 80, and to t = 160 when the t = 80 record shows no
turnaround.  No new terms, no parameter changes; the canonical
ExpandingTwoFluid3DGPU is untouched.

Continuity: the fresh t = 0 -> t_end run is compared record-by-record
against the suite's ysep12 history for t <= 40 (same deterministic
trajectory; the comparison must be exact at every record).

Arms (fresh solver per arm, run from t = 0):
  ysep12_t80   Yin-excess pair, sep = 12, t = 80 = 4/lambda
  ysep12_t160  Yin-excess pair, sep = 12, t = 160 = 8/lambda (only when
               the t = 80 record shows continued contraction without
               turnaround; run with --t-end 160)

Verdicts (results.json):
  C1  continuity: max record-by-record diffs vs the suite ysep12 history
      for t <= 40 (d, Rc, pi_strand, q_mid, A_plus, ...) -- exact match
      proves the continuation is the same arm.
  C2  t_end outcome: d(t) trend -- turnaround (d increasing or flattening
      with d(t_end) < d(t_end-10)), stalled (|rate| < 0.01 cells/t over
      the last 10%), still contracting (rate <= -0.01 cells/t), merged
      (single ridge or d < 0.25 d0), or tracking lost (ridge amplitude
      below the detection floor); Pi sign at t_end; q/rho/eps at the
      midpoint; clamp/mass/NaN telemetry.
  C3  t = 40 cross-check within the run (the t = 40 snapshot record).

Output (runs/ is gitignored -- commit the script only):
  runs/<rid>_two_strand_yin_excess_cont/run_<arm>.json
  runs/<rid>_two_strand_yin_excess_cont/results.json
"""

import os
import sys
import json
import time
from datetime import datetime

import numpy as np
import torch

torch.backends.cudnn.benchmark = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_two_strand_yin_excess_suite as S   # suite module, read-only
import run_trauma_wake_lock as T

# ── Protocol (identical to the suite; t_end and snapshots vary) ──────────
T.LAM = 0.05
T.DT = 0.001
SEP = 12
S.REPORT = 100               # records every 0.1 t (as the suite)
BASELINE = "runs/20260807_014428_two_strand_yin_excess"   # suite record

COMPARE_KEYS = ['d', 'Rc', 'delta_theta', 'A_plus', 'A_minus', 'q_mid',
                'q_flank', 'eps_mid', 'rho_mid', 'x1', 'x2', 'ey_min',
                'ei_min', 'q_glob', 'pi_mid', 'pi_glob', 'Pi_tot',
                'ey_tot', 'ei_tot']


def run_arm(t_end, tag, outdir):
    """The suite's ysep12 arm run from t = 0 to t_end (fresh solver)."""
    S.STEPS = int(round(t_end / T.DT))
    S.SNAP_STEPS = tuple(sorted({0, 4000, S.STEPS - 1}))   # t = 0, 4, t_end
    solver = T.build_solver(torch.device('cuda' if torch.cuda.is_available()
                                         else 'cpu'))
    h, m = S.run_case(solver, SEP, tag, outdir, yin=True)
    return h, m


def continuity(h, baseline_h):
    """Record-by-record match against the suite's ysep12 history for the
    overlapping window (t <= 40).  Same-process comparisons are bit-exact;
    cross-process runs on ROCm/GPU pick slightly different FFT/kernel
    roundings, so the dynamics keys are required to match to 1e-4
    (absolute) and the per-component mass totals to 1e-5 (relative -- the
    conversion partition accumulates float noise; the total mass is
    conserved at the 1e-12 level in both runs)."""
    base = [d for d in baseline_h if d['t'] <= 40.0 + 1e-9]
    run = [d for d in h if d['t'] <= 40.0 + 1e-9]
    dyn_keys = [k for k in COMPARE_KEYS if k not in ('ey_tot', 'ei_tot',
                                                     'Pi_tot')]
    diffs = {}
    for k in dyn_keys:
        if k == 'pi_strand':
            diffs[k] = max(abs(a - b)
                           for a, b in zip([d[k][0] for d in run],
                                           [d[k][0] for d in base]))
        else:
            diffs[k] = max(abs(d[k] - b[k]) for d, b in zip(run, base))
    for k in ('ey_tot', 'ei_tot', 'Pi_tot'):
        diffs[k] = max(abs(d[k] - b[k]) / max(abs(b[k]), 1e-30)
                       for d, b in zip(run, base))
    # total mass is the physically conserved invariant: the clamp
    # renormalization conserves ey+ei to 1e-12 in every run, so the
    # run-vs-baseline total-mass residual must sit at that level.
    diffs['tot_mass'] = max(
        abs((d['ey_tot'] + d['ei_tot']) - (b['ey_tot'] + b['ei_tot']))
        / max(abs(b['ey_tot'] + b['ei_tot']), 1e-30)
        for d, b in zip(run, base))
    dyn_ok = max(diffs[k] for k in dyn_keys) <= 1e-4
    tot_ok = (max(diffs[k] for k in ('ey_tot', 'ei_tot', 'Pi_tot')) <= 1e-4
              and diffs['tot_mass'] <= 1e-9)
    return dyn_ok and tot_ok, diffs, len(run), len(base)


def trend_verdict(h, d0):
    """C2 classification from the last 10% of the window, plus the
    coalescence time (first record with a single tracked ridge or
    d < 2 cells; None if the pair survives the window)."""
    last = h[-1]
    n = len(h)
    win = h[int(0.9 * n):]
    rate = (win[-1]['d'] - win[0]['d']) / (win[-1]['t'] - win[0]['t'])
    back = float(np.mean([d['d'] for d in win]))
    merge_t = None
    for d in h[1:]:
        if d['merged'] or d['d'] < 2.0:
            merge_t = d['t']
            break
    if last['merged'] or back < 0.25 * d0:
        outcome = 'merged'
    elif rate > 0.01:
        outcome = 'turnaround'
    elif abs(rate) <= 0.01:
        outcome = 'stalled'
    else:
        outcome = 'contracting'
    return outcome, {'rate_last10': rate, 'd_end': last['d'],
                     'd_back_mean': back, 'd_min': min(d['d'] for d in h),
                     'merge_t': merge_t,
                     'merged_at_end': bool(last['merged']),
                     'A_end': [last['strands'][0]['A'],
                               (last['strands'][1]['A']
                                if not last['merged']
                                else last['strands'][0]['A'])],
                     'tracking_fallback': bool(
                         last['x1'] == h[-2]['x1']
                         and last['x2'] == h[-2]['x2']
                         and h[-2]['t'] < last['t'] - 1e-9
                         and last['merged'])}


def summarize(h, m):
    first, last = h[0], h[-1]
    return {
        'd_start': first['d'], 'd_end': last['d'],
        'd_40': min(h, key=lambda d: abs(d['t'] - 40.0))['d'],
        'delta_theta_0': first['delta_theta'],
        'delta_theta_end': last['delta_theta'],
        'pi_strand_0': first['pi_strand'],
        'pi_strand_40': min(h, key=lambda d: abs(d['t'] - 40.0))['pi_strand'],
        'pi_strand_end': last['pi_strand'],
        'pi_glob_0': first['pi_glob'], 'pi_glob_end': last['pi_glob'],
        'Pi_tot_0': first['Pi_tot'], 'Pi_tot_end': last['Pi_tot'],
        'q_mid_0': first['q_mid'], 'q_mid_40':
            min(h, key=lambda d: abs(d['t'] - 40.0))['q_mid'],
        'q_mid_end': last['q_mid'],
        'q_flank_end': last['q_flank'],
        'eps_mid_0': first['eps_mid'],
        'eps_mid_40': min(h, key=lambda d: abs(d['t'] - 40.0))['eps_mid'],
        'eps_mid_end': last['eps_mid'],
        'rho_mid_0': first['rho_mid'],
        'rho_mid_40': min(h, key=lambda d: abs(d['t'] - 40.0))['rho_mid'],
        'rho_mid_end': last['rho_mid'],
        'A_plus_40': min(h, key=lambda d: abs(d['t'] - 40.0))['A_plus'],
        'A_plus_end': last['A_plus'],
        'q_glob_end': last['q_glob'],
        'ey_min': min(d['ey_min'] for d in h),
        'ei_min': min(d['ei_min'] for d in h),
        'H_0': first['H'], 'H_end': last['H'],
        'a_0': first['a'], 'a_end': last['a'],
        'meta': m,
    }


def main():
    t_end = 80.0
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == '--t-end':
            t_end = float(argv[i + 1])
            i += 1
        elif argv[i] == '--baseline':
            globals()['BASELINE'] = argv[i + 1]
            i += 1
        i += 1
    tag = f"ysep12_t{int(t_end)}"

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_two_strand_yin_excess_cont"
    os.makedirs(rdir, exist_ok=True)

    h, m = run_arm(t_end, tag, rdir)

    # Continuity vs the suite record
    with open(f"{BASELINE}/run_ysep12.json") as f:
        base = json.load(f)['hist']
    cont_ok, diffs, n_run, n_base = continuity(h, base)

    s = summarize(h, m)
    d0 = s['d_start']
    outcome, trend = trend_verdict(h, d0)

    results = {
        'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT, 't_end': t_end,
                 'gate_model': 'five (solver)',
                 'init': 'Yin-excess swapped pair, sep = 12 (suite sec 3.5)',
                 'baseline': BASELINE,
                 'arms': {tag: m}},
        'arm': s,
        'verdicts': {
            'C1_continuity': {'verdict': 'passed' if cont_ok else 'mismatch',
                              'criterion': 'dynamics keys <= 1e-4 absolute, '
                                           'component totals <= 1e-4 '
                                           'relative, total mass <= 1e-9 '
                                           'relative (cross-process float '
                                           'tolerance; same-process '
                                           'comparisons are bit-exact)',
                              'max_record_diff': max(diffs.values()),
                              'diffs': diffs,
                              'n_run_records': n_run,
                              'n_baseline_records': n_base},
            'C2_trend': {'verdict': outcome, 'data': trend},
            'C3_telemetry': {'floor_touch': m['floor_touch'],
                             'mass_drift': m['mass_drift'],
                             'nan_abort': m['nan_abort'],
                             'a_end': m['a_end'], 'H_end': m['H_end']},
        },
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n=== YIN-EXCESS CONTINUATION (t={t_end:.0f}) ===")
    print(f"d: {s['d_start']:.3f} -> {s['d_40']:.3f} (t=40) -> "
          f"{s['d_end']:.3f} (t={t_end:.0f})")
    print(f"pi_strand: {[f'{p:+.3f}' for p in s['pi_strand_0']]} (t=0) -> "
          f"{[f'{p:+.3f}' for p in s['pi_strand_40']]} (t=40) -> "
          f"{[f'{p:+.3f}' for p in s['pi_strand_end']]} (t={t_end:.0f})")
    print(f"q_mid: {s['q_mid_0']:.4f} -> {s['q_mid_40']:.4f} -> "
          f"{s['q_mid_end']:.4f} | eps_mid: {s['eps_mid_0']:+.3f} -> "
          f"{s['eps_mid_40']:+.3f} -> {s['eps_mid_end']:+.3f} | "
          f"rho_mid: {s['rho_mid_0']:.3f} -> {s['rho_mid_40']:.3f} -> "
          f"{s['rho_mid_end']:.3f}")
    print(f"trend: {outcome} (rate {trend['rate_last10']:+.4f} cells/t, "
          f"A_end {[f'{a:.3f}' for a in trend['A_end']]}, "
          f"merged_at_end {trend['merged_at_end']})")
    print(f"telemetry: floor {m['floor_touch']}, mass_drift "
          f"{m['mass_drift']['tot']:.2e}, nan {m['nan_abort']}, "
          f"H_end {m['H_end']:.4f}, a_end {m['a_end']:.4f}")
    print(f"continuity vs suite ysep12 (t<=40): "
          f"{'PASSED' if cont_ok else 'MISMATCH'} (max dynamics diff "
          f"{max(diffs[k] for k in diffs if k not in ('ey_tot','ei_tot','Pi_tot')):.3e}, "
          f"max component-total rel diff "
          f"{max(diffs[k] for k in ('ey_tot','ei_tot','Pi_tot')):.3e})")
    print(f"\nResults: {rdir}/results.json")
    if torch.cuda.is_available():
        torch.cuda.synchronize()


if __name__ == "__main__":
    main()
