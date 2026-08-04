#!/usr/bin/env python3
"""Churning-gate quench-regime probe: partial lock or weak pumping?

Follow-up to `consciousness/neurodivergence-as-gate-configuration.md` §9.1
(the 2026-08-04 amplitude scan, `two-fluid/run_churning_gate_amp_scan.py`):
at sub-threshold amplitudes 0.025–0.05 the in-channel (Fire) drive at P0
takes the site's mean |epsilon| below the undriven floor (0.583, 0.614 vs
0.870 in eps_rel units), q_site rises (0.666 → 0.696/0.700), the q-gap
closes, and the epsilon time-variance rises ~100–130× with no vertex
locking.

Binary question: is the sub-threshold quench a distinct partial-lock
regime (a stable low-mean-epsilon, elevated-q state with bounded
variance) or weak pumping (energy accumulating slowly, which would
eventually climb back above the undriven floor and pump)?

Canonical-init protocol. Every arm builds a FRESH solver instance and
re-initializes the churning init (seed 42), so no arm carries solver
state from a previous arm (rk2_step mutates the solver's scale factor,
smoothed Hubble rate, and global q_mean; sharing one solver across arms
was the earlier scripts' convention, but it makes later arms order-
dependent — the t=0 eps_site drifts monotonically across shared-solver
arms at the 1e-6 level and arm endpoints differ at the 1e-2 level).
With fresh solvers, identical schedules reproduce bit-identically.

P0 is measured from a dedicated t=4 reference run (4000 steps; reports
include the step-3999 endpoint, an 81-point series) — the same window
the amplitude scan used, so P0 = 0.081 exactly. The quench is
matched-period specific: measured from an 8000-step window the FFT bins
shift to 0.0800 and the amp-0.05 arm pumps instead of quenching, so the
81-point t=4 window is load-bearing. All drives run at P0, per the
dominant_period window caveat of `consciousness/gender-as-qi-
configuration.md` §8.1.

Arms (lambda=0.05, N=48, churning init seed 42):
  ref4            undriven to t = 4 (P0 measurement; canonical ref floor)
  ref8            undriven to t = 8 (trajectory reference)
  in005-persist   in-channel (Fire) at P0, amp 0.05, to t = 8
  in0025-persist  in-channel at P0, amp 0.025, to t = 8
  in005-removal   in-channel at P0, amp 0.05, to t = 4, drive OFF to t = 8
  in0025-removal  in-channel at P0, amp 0.025, to t = 4, drive OFF to t = 8
  in<amp>         in-channel at P0, amps {0.025, 0.05, 0.06, 0.07, 0.08,
                  0.09, 0.10, 0.15, 0.20, 0.30}, to t = 4 — the full
                  amplitude set rerun at canonical init (fresh solver
                  per arm): the 0.025/0.05 rows are exact reproduction
                  anchors against the stored amplitude scan, 0.06–0.09
                  locate the onset between the quench floor and the
                  known pump, 0.10–0.30 re-establish the pump branch
                  without merging the amplitude scan's shared-solver
                  rows into the table.
  cross-0.025     cross-channel (Wood) at P0, eps-parity amp 0.025/phi,
                  to t = 4 (bottom-of-quench-region ordering contrast)
  cross-0.06      cross-channel at P0, eps-parity amp 0.06/phi, to t = 4

Persistence metric (stated here and in results meta): the quench depth
is D(t) = ref_eps(t) − arm_eps(t) at same-time t from the shared ref8
run. Depth retention P = D(8)/D(4). The observation window after drive
removal is 4 s = 0.2/lambda (20% of the conversion timescale
1/lambda = 20 s); an arm counts as persistent if P >= 0.5 (holds ≥ 50%
of its t = 4 depth through the window) — the memory/lock signature.
Snap-back onto the undriven trajectory is read as mean |arm_eps −
ref_eps| over t in [6, 8] < 0.05 (the house 0.05 verdict margin).

Verdict logic:
  PARTIAL-LOCK iff (i) at t = 8 both persist arms keep eps <= ref_8 − 0.05
    AND q_site >= ref_q_site_8 + 0.02, (ii) the eps time-variance halves
    are within 2× of each other in both persist arms (bounded
    oscillation, not secular growth), (iii) the amp-0.05 removal arm
    retains ≥ 50% of its t = 4 quench depth at t = 8 (the quench has
    memory after the drive stops).
  WEAK-PUMPING iff any persist arm's eps has risen back above ref_8 −
    0.05 by t = 8, or any persist arm's variance-half ratio exceeds 2
    (secular growth), or the removal arm snaps back (depth retention
    < 0.5).
  Null/ambiguous otherwise, reported as such.

Clamp diagnostics per arm: ey_min_site/ei_min_site minima over the run
and the count of report steps touching the 1e-3 positivity floor (near
floor 1.5e-3). Every driven arm in this family touches the floor
intermittently — magnitudes are partially clamp-affected; directions and
orderings are clean.

Usage: python two-fluid/run_churning_gate_quench.py
Output: runs/<id>_churning_quench/results.json + figure
"""

import os
import sys
import glob
import json
import time
from datetime import datetime

import numpy as np
import torch

torch.backends.cudnn.benchmark = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_trauma_wake_lock as T
import run_churning_gate as G  # baseline: churning_init, arm_channels, ...

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

T.LAM = 0.05
T.DT = 0.001
T.REPORT = 50

CLAMP_FLOOR = 1e-3
NEAR_FLOOR = 1.5e-3
T8_STEPS = 8000         # t = 8
T4_STEPS = 4000         # t = 4 (baseline convention; last report at 3.999)
PERSIST_AMPS = [0.025, 0.05]
FINE_AMPS = [0.06, 0.07, 0.08, 0.09]
# Full amplitude set rerun at canonical init (fresh solver per arm):
# 0.025/0.05 = reproduction anchors vs the stored amplitude scan,
# 0.06-0.09 = onset region, 0.10-0.30 = the known pump branch.
FULL_AMPS = [0.025, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.15, 0.20, 0.30]
CROSS_AMPS = [0.025, 0.06]       # eps-parity: arm amp = amp / phi
MARGIN_EPS = 0.05       # verdict margin vs the ref floor
MARGIN_Q = 0.02         # q_site elevation margin vs ref
VAR_HALF_CAP = 2.0      # bounded-variance cap (max/min of the halves)
DEPTH_RETENTION = 0.5   # removal persistence floor
PUMP_EPS_REL = 1.3      # amp-scan pump criterion (eps_rel >= 1.3)
T_REMOVE = 4.0          # drive-off time for the removal arms


def run_arm(device, tag, outdir, steps, drive_channel=None,
            drive_period=None, drive_amp=None, drive_until=None):
    """Fresh-solver churning init (seed 42); optional periodic drive.

    A FRESH solver is built per arm so no arm inherits the previous
    arm's scale-factor / smoothed-Hubble / q_mean state (rk2_step
    mutates those; the earlier scripts shared one solver across arms,
    which makes later arms order-dependent). Identical schedules are
    bit-reproducible across fresh-solver arms.

    Step/diagnostic convention matches `run_churning_gate.run_case`
    (same init, same drive schedule before the rk2 step, same report
    cadence) with two extensions: the run length is parameterized, and a
    drive can be switched off at drive_until (drive applied on steps
    with t_now = step*DT < drive_until).
    """
    amp = G.DRIVE_AMP if drive_amp is None else drive_amp
    print(f"\n=== run: {tag} (channel={drive_channel}, "
          f"period={drive_period}, amp={amp}, steps={steps}, "
          f"drive_until={drive_until}) ===")
    solver = T.build_solver(device)
    ey_hat, ei_hat, u_hat = G.churning_init(solver, seed=42)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    t0 = time.time()
    hist = []

    for step in range(steps):
        ey = torch.fft.ifftn(ey_hat).real
        if drive_channel is not None and \
                (drive_until is None or step * T.DT < drive_until):
            t_now = step * T.DT
            drive = amp * np.sin(2.0 * np.pi * t_now / drive_period)
            if drive_channel == 'fire':
                ey = ey + drive * mask
                ey_hat = torch.fft.fftn(ey)
            else:  # wood: cross-channel, on the Yin component
                ei = torch.fft.ifftn(ei_hat).real
                ei = ei + drive * mask
                ei_hat = torch.fft.fftn(ei)
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)

        if step % T.REPORT == 0 or step == steps - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            d = T.measure(solver, ey, ei, mask)
            bm = mask > 0.5
            d['ey_min_site'] = float(ey[bm].min())
            d['ei_min_site'] = float(ei[bm].min())
            eps = ey - T.PHI * ei
            d['eps_var_x'] = float(eps[bm].var())
            d.update({'step': step, 't': step * T.DT})
            hist.append(d)

    print(f"  [{tag}] {steps} steps in {time.time() - t0:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'hist': hist}, f, indent=1)
    return hist


def at_t(hist, t_goal):
    """Snapshot nearest to t_goal (exact for multiples of REPORT*DT)."""
    return min(hist, key=lambda d: abs(d['t'] - t_goal))


def arm_summary(name, hist, t_goals=(T4_STEPS * T.DT, T8_STEPS * T.DT)):
    """Verdict quantities: per-t_goal snapshots, series statistics."""
    first = hist[0]
    eps0 = max(first['eps_site'], 1e-12)
    s = {'name': name, 't0': first['t'], 'eps_site_0': first['eps_site'],
         'q_site_0': first['q_site'],
         'q_gap_0': first['q_glob'] - first['q_site']}

    def snap(t_goal):
        d = at_t(hist, t_goal)
        return {'t': d['t'], 'eps_site': d['eps_site'],
                'eps_rel': d['eps_site'] / eps0,
                'q_site': d['q_site'], 'q_gap': d['q_glob'] - d['q_site'],
                'phase_max': max(d['phase_frac']),
                'phase_frac': d['phase_frac'],
                'sigma_r_site': d['sigma_r_site'],
                'ey_min_site': d['ey_min_site'],
                'ei_min_site': d['ei_min_site']}

    for t_goal in t_goals:
        s[f't{t_goal:g}'] = snap(t_goal)

    # peak eps_rel over the back 40% of the run (house convention)
    back = hist[int(0.6 * len(hist)):]
    s['peak_eps_rel'] = max(d['eps_site'] for d in back) / eps0

    # time-variance in halves + back 40% (bounded vs secular discriminator)
    eps_series = np.array([d['eps_site'] for d in hist])
    half = len(eps_series) // 2
    v1, v2 = float(eps_series[:half].var()), float(eps_series[half:].var())
    s['eps_var_first_half'] = v1
    s['eps_var_second_half'] = v2
    s['eps_var_half_ratio'] = max(v1, v2) / max(min(v1, v2), 1e-12)
    s['eps_var_t_back'] = float(eps_series[int(0.6 * len(eps_series)):].var())

    # q_site trend: linear-fit slope + first-vs-last tercile means
    t_arr = np.array([d['t'] for d in hist])
    q_arr = np.array([d['q_site'] for d in hist])
    s['q_site_slope'] = float(np.polyfit(t_arr, q_arr, 1)[0])
    terc = len(q_arr) // 3
    s['q_site_first_tercile'] = float(q_arr[:terc].mean())
    s['q_site_last_tercile'] = float(q_arr[-terc:].mean())

    # clamp: run minima + floor-touch count
    s['ey_min_run'] = min(d['ey_min_site'] for d in hist)
    s['ei_min_run'] = min(d['ei_min_site'] for d in hist)
    s['ey_floor_touches'] = sum(
        1 for d in hist if d['ey_min_site'] <= NEAR_FLOOR)
    s['ei_floor_touches'] = sum(
        1 for d in hist if d['ei_min_site'] <= NEAR_FLOOR)
    return s


def load_amp_scan():
    """Stored amplitude-scan summaries (for reproduction checks only)."""
    cands = sorted(glob.glob(os.path.join(REPO, 'runs', '*_churning_amp',
                                          'results.json')),
                   key=os.path.getmtime)
    if not cands:
        return None
    path = cands[-1]
    with open(path) as f:
        r = json.load(f)
    out = {float(a): s['eps_rel'] for a, s in r['in_channel'].items()}
    return {'path': path, 'p0': r['meta']['P0'], 'ref_eps_rel':
            r['ref']['eps_rel'], 'in_eps_rel': out}


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  "
          f"t=4.0 + t=8.0 windows, drive_until={T_REMOVE}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = os.path.join(REPO, 'runs', f"{rid}_churning_quench")
    os.makedirs(rdir, exist_ok=True)

    # ── P0 reference: dedicated t=4 run (81-point window, same as the
    #    amplitude scan) ───────────────────────────────────────────────────
    h_ref4 = run_arm(device, tag='ref4', outdir=rdir, steps=T4_STEPS)
    p0 = T.dominant_period([d['eps_site'] for d in h_ref4], T.DT)
    if p0 is None:
        print("No dominant period in the ref series; aborting.")
        return
    basin = G.site_phase_basin(h_ref4[0])
    ey_hat, ei_hat, u_hat = G.churning_init(T.build_solver(device), seed=42)
    mask = T.site_mask(T.N, T.R_SITE, device)
    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    bm = mask > 0.5
    eps_mean_init = float(((ey - T.PHI * ei) * mask).sum() / bm.sum())
    in_ch, cross_ch = G.arm_channels(basin, eps_mean_init)
    print(f"\nMeasured natural period P0 = {p0:.4f} (drive period = P0)")
    print(f"Site phase basin at t=0: {basin}  mean eps = {eps_mean_init:+.3f}")
    print(f"  -> in-channel drive on '{in_ch}', cross-channel on '{cross_ch}'")

    # ── Reference trajectory to t = 8 ─────────────────────────────────────
    h_ref8 = run_arm(device, tag='ref8', outdir=rdir, steps=T8_STEPS)

    # ── Persistence and removal arms ──────────────────────────────────────
    h = {}
    h['in005-persist'] = run_arm(device, 'in005-persist', rdir,
                                 steps=T8_STEPS, drive_channel=in_ch,
                                 drive_period=p0, drive_amp=0.05)
    h['in0025-persist'] = run_arm(device, 'in0025-persist', rdir,
                                  steps=T8_STEPS, drive_channel=in_ch,
                                  drive_period=p0, drive_amp=0.025)
    h['in005-removal'] = run_arm(device, 'in005-removal', rdir,
                                 steps=T8_STEPS, drive_channel=in_ch,
                                 drive_period=p0, drive_amp=0.05,
                                 drive_until=T_REMOVE)
    h['in0025-removal'] = run_arm(device, 'in0025-removal', rdir,
                                  steps=T8_STEPS, drive_channel=in_ch,
                                  drive_period=p0, drive_amp=0.025,
                                  drive_until=T_REMOVE)

    # ── Full amplitude set at canonical init (fresh solver per arm) ───────
    h_full = {}
    for amp in FULL_AMPS:
        tag = f"in{amp * 100:.0f}"
        h_full[amp] = run_arm(device, tag, rdir, steps=T4_STEPS,
                              drive_channel=in_ch, drive_period=p0,
                              drive_amp=amp)
    h_cross = {}
    for amp in CROSS_AMPS:
        tag = f"cross{amp * 100:.0f}"
        h_cross[amp] = run_arm(device, tag, rdir, steps=T4_STEPS,
                               drive_channel=cross_ch, drive_period=p0,
                               drive_amp=amp / T.PHI)

    s_ref4 = arm_summary('ref4', h_ref4, t_goals=(T4_STEPS * T.DT,))
    s_ref8 = arm_summary('ref8', h_ref8)
    s_arm = {k: arm_summary(k, hh) for k, hh in h.items()}
    s_full = {amp: arm_summary(f'in-{amp}', hh, t_goals=(T4_STEPS * T.DT,))
              for amp, hh in h_full.items()}
    s_cross = {amp: arm_summary(f'cross-{amp}', hh,
                                t_goals=(T4_STEPS * T.DT,))
               for amp, hh in h_cross.items()}

    # ── Reproduction check vs the stored amplitude scan ───────────────────
    amp_scan = load_amp_scan()
    repro = {}
    if amp_scan is not None:
        repro['source'] = amp_scan['path']
        repro['p0_scan'] = amp_scan['p0']
        repro['p0_here'] = p0
        repro['ref_t4_eps_rel_scan'] = amp_scan['ref_eps_rel']
        repro['ref_t4_eps_rel_here'] = s_ref4['t4']['eps_rel']
        for a in (0.025, 0.05):
            repro[f'in{a:g}_t4_eps_rel_scan'] = amp_scan['in_eps_rel'][a]
            repro[f'in{a:g}_t4_eps_rel_here'] = s_full[a]['t4']['eps_rel']

    # ── Fine scan: onset over the full 0.025–0.30 range ───────────────────
    ref4 = s_ref4['t4']
    rows = {amp: {'eps_rel': s['t4']['eps_rel'],
                  'peak_eps_rel': s['peak_eps_rel'],
                  'eps_site': s['t4']['eps_site'],
                  'q_gap': s['t4']['q_gap'],
                  'q_site': s['t4']['q_site'],
                  'phase_max': s['t4']['phase_max'],
                  'ey_floor_touches': s['ey_floor_touches']}
            for amp, s in s_full.items()}
    onset_eps = ref4['eps_site'] + MARGIN_EPS          # ref floor + margin
    onset_eps_rel = ref4['eps_rel'] + MARGIN_EPS
    pump_amps = sorted(a for a, r in rows.items()
                       if r['eps_rel'] >= PUMP_EPS_REL or
                       r['eps_site'] >= onset_eps)
    onset = min(pump_amps) if pump_amps else None
    # sharpness: ratio of the first pump row to the last non-pump row
    if onset is not None and onset > min(rows):
        below = [a for a in sorted(rows) if a < onset]
        ratio = rows[onset]['eps_rel'] / rows[below[-1]]['eps_rel']
    else:
        ratio = None

    # ── Persistence / removal discriminators ──────────────────────────────
    ref8 = s_ref8['t8']
    depth4 = {k: s_ref8['t4']['eps_site'] - s_arm[k]['t4']['eps_site']
              for k in ('in005-removal', 'in0025-removal')}
    depth8 = {k: s_ref8['t8']['eps_site'] - s_arm[k]['t8']['eps_site']
              for k in ('in005-removal', 'in0025-removal')}
    retention = {}
    for k in depth4:
        retention[k] = (depth8[k] / depth4[k] if depth4[k] > MARGIN_EPS
                        else float('nan'))
    # snap-back: mean |arm − ref| over t in [6, 8]
    snap_gap = {}
    ref_t = {d['t']: d['eps_site'] for d in h_ref8}
    for k in ('in005-removal', 'in0025-removal'):
        gap = [abs(d['eps_site'] - ref_t[d['t']]) for d in h[k]
               if d['t'] >= 6.0]
        snap_gap[k] = float(np.mean(gap))

    # ── Verdict ───────────────────────────────────────────────────────────
    persist_ok_eps = all(
        s_arm[k]['t8']['eps_site'] <= ref8['eps_site'] - MARGIN_EPS
        for k in ('in005-persist', 'in0025-persist'))
    persist_ok_q = all(
        s_arm[k]['t8']['q_site'] >= ref8['q_site'] + MARGIN_Q
        for k in ('in005-persist', 'in0025-persist'))
    bounded_var = all(
        s_arm[k]['eps_var_half_ratio'] <= VAR_HALF_CAP
        for k in ('in005-persist', 'in0025-persist'))
    removal_holds = (retention['in005-removal'] >= DEPTH_RETENTION)
    snap_back = snap_gap['in005-removal'] < MARGIN_EPS
    quench_ok = (s_full[0.05]['t4']['eps_site'] <=
                 ref4['eps_site'] - 0.02)

    if quench_ok and persist_ok_eps and persist_ok_q and bounded_var and \
            removal_holds and not snap_back:
        verdict = 'PARTIAL-LOCK'
    elif quench_ok and (not persist_ok_eps or not bounded_var or
                        not removal_holds or snap_back):
        verdict = 'WEAK-PUMPING'
    elif not quench_ok:
        verdict = 'NO-QUENCH-AT-CANONICAL-INIT'
    else:
        verdict = 'AMBIGUOUS'

    results = {
        'meta': {
            'P0': p0, 'drive_period': p0, 'lam': T.LAM, 'N': T.N,
            't4': T4_STEPS * T.DT, 't8': T8_STEPS * T.DT,
            't_remove': T_REMOVE, 'basin_t0': basin,
            'eps_mean_t0': eps_mean_init,
            'in_channel': in_ch, 'cross_channel': cross_ch,
            'persist_amps': PERSIST_AMPS, 'fine_amps': FINE_AMPS,
            'full_amps': FULL_AMPS,
            'cross_amps': [a / T.PHI for a in CROSS_AMPS],
            'canonical_init': 'fresh solver per arm (rk2_step mutates '
                              'solver a / H_smooth / q_mean; shared-'
                              'solver reuse makes later arms order-'
                              'dependent)',
            'clamp_floor': CLAMP_FLOOR, 'near_floor': NEAR_FLOOR,
            'margin_eps': MARGIN_EPS, 'margin_q': MARGIN_Q,
            'var_half_cap': VAR_HALF_CAP, 'depth_retention_floor':
                DEPTH_RETENTION, 'pump_eps_rel': PUMP_EPS_REL,
            'persistence_metric': 'D(t) = ref_eps(t) - arm_eps(t) from '
                                  'the shared ref8 run; retention '
                                  'P = D(8)/D(4); observation window '
                                  '4 s = 0.2/lambda (20% of the '
                                  'conversion timescale 1/lambda = 20 s); '
                                  'P >= 0.5 = persistent (memory), '
                                  'snap-back = mean |arm - ref| over '
                                  't in [6, 8] < 0.05',
            'fine_scan': {'onset_eps_site_crit': onset_eps,
                          'onset_eps_rel_crit': onset_eps_rel,
                          'pump_eps_rel_crit': PUMP_EPS_REL,
                          'rows': {str(a): r for a, r in rows.items()},
                          'onset_amp': onset,
                          'onset_step_ratio': ratio},
            'repro': repro,
        },
        'ref4': s_ref4,
        'ref8': s_ref8,
        'arms': s_arm,
        'full_amp_scan': s_full,
        'cross_channel': s_cross,
        'quench_depth': {'depth4': depth4, 'depth8': depth8,
                         'retention': retention, 'snap_gap_6_8': snap_gap},
        'verdict': {
            'verdict': verdict,
            'quench_reproduced_at_canonical_init': quench_ok,
            'persist_ok_eps': persist_ok_eps,
            'persist_ok_q': persist_ok_q,
            'bounded_var': bounded_var,
            'removal_holds_005': removal_holds,
            'snap_back_005': snap_back,
            'ref8_eps_site': ref8['eps_site'],
            'ref8_q_site': ref8['q_site'],
        },
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    # ── Console table ─────────────────────────────────────────────────────
    print("\n=== CHURNING-GATE QUENCH PROBE (canonical init) ===")
    print(f"P0 = {p0:.4f}  ref t4: eps_rel {ref4['eps_rel']:.3f} "
          f"(eps_site {ref4['eps_site']:.3f})  "
          f"ref t8: eps_site {ref8['eps_site']:.3f}, "
          f"q_site {ref8['q_site']:.3f}")
    if repro:
        print(f"Reproduction vs {os.path.basename(repro['source'])}: "
              f"ref t4 {repro['ref_t4_eps_rel_scan']:.4f} vs "
              f"{repro['ref_t4_eps_rel_here']:.4f}; "
              f"in-0.025 {repro['in0.025_t4_eps_rel_scan']:.4f} vs "
              f"{repro['in0.025_t4_eps_rel_here']:.4f}; "
              f"in-0.05 {repro['in0.05_t4_eps_rel_scan']:.4f} vs "
              f"{repro['in0.05_t4_eps_rel_here']:.4f}")
    print(f"{'arm':>15s} {'eps4':>6s} {'eps8':>6s} {'q4':>6s} {'q8':>6s} "
          f"{'var1':>8s} {'var2':>8s} {'ratio':>6s} {'qslope':>8s} "
          f"{'ey_min':>7s} {'touches':>7s}")
    for name, s in [('ref8', s_ref8)] + \
            [(k, s_arm[k]) for k in ('in005-persist', 'in0025-persist',
                                     'in005-removal', 'in0025-removal')]:
        print(f"{name:>15s} {s['t4']['eps_site']:6.3f} "
              f"{s['t8']['eps_site']:6.3f} "
              f"{s['t4']['q_site']:6.3f} {s['t8']['q_site']:6.3f} "
              f"{s['eps_var_first_half']:8.5f} "
              f"{s['eps_var_second_half']:8.5f} "
              f"{s['eps_var_half_ratio']:6.2f} "
              f"{s['q_site_slope']:8.4f} "
              f"{s['ey_min_run']:7.4f} {s['ey_floor_touches']:7d}")

    print("\n--- full amplitude set (t=4, canonical init) ---")
    print(f"{'amp':>6s} {'eps_rel':>7s} {'eps_site':>8s} {'peak':>6s} "
          f"{'q_gap':>7s} {'q_site':>6s} {'phase_max':>9s} "
          f"{'touches':>7s}")
    for amp in sorted(rows):
        r = rows[amp]
        print(f"{amp:6.3f} {r['eps_rel']:7.3f} {r['eps_site']:8.3f} "
              f"{r['peak_eps_rel']:6.3f} {r['q_gap']:+7.3f} "
              f"{r['q_site']:6.3f} {r['phase_max']:9.3f} "
              f"{r['ey_floor_touches']:7d}")
    print(f"Onset (first amp with eps_rel >= {PUMP_EPS_REL} or eps_site "
          f">= {onset_eps:.3f}): {onset}"
          + (f" (step ratio vs previous amp: {ratio:.2f})"
             if ratio is not None else ""))

    print("\n--- bottom asymmetry (cross-channel, eps-parity, t=4) ---")
    for amp in CROSS_AMPS:
        s = s_cross[amp]
        print(f"cross-{amp}: eps_rel {s['t4']['eps_rel']:.3f} "
              f"(peak {s['peak_eps_rel']:.3f}) q_gap "
              f"{s['q_gap_0']:+.3f}->{s['t4']['q_gap']:+.3f} "
              f"phase_max {s['t4']['phase_max']:.2f} "
              f"ey_min {s['ey_min_run']:.4f} "
              f"touches {s['ey_floor_touches']}")

    print("\n--- removal / persistence ---")
    for k in ('in005-removal', 'in0025-removal'):
        print(f"{k}: depth4 {depth4[k]:.3f} depth8 {depth8[k]:.3f} "
              f"retention {retention[k]:.2f} "
              f"snap_gap[6,8] {snap_gap[k]:.3f}")

    print("\n=== VERDICT ===")
    print(f"Quench reproduced at canonical init "
          f"(in-0.05 t4 <= ref t4 - 0.02): {quench_ok}")
    print(f"Persist arms keep eps <= ref8 - 0.05 at t=8: {persist_ok_eps}")
    print(f"Persist arms keep q_site >= ref8 + 0.02 at t=8: {persist_ok_q}")
    print(f"Variance halves within 2x (both persist arms): {bounded_var}")
    print(f"Removal (0.05) retention >= 50%: {removal_holds}")
    print(f"Removal (0.05) snapped back (gap < 0.05 over [6,8]): "
          f"{snap_back}")
    print(f"*** VERDICT: {verdict} ***")

    # ── Figure ─────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 3, figsize=(16, 9))
        t_ref = [d['t'] for d in h_ref8]
        for ax in axes.flat:
            ax.grid(alpha=0.3)

        # (0,0) eps(t): persistence arms + ref8 + floor
        ax = axes[0, 0]
        ax.plot(t_ref, [d['eps_site'] for d in h_ref8], 'gray',
                label='ref (undriven)')
        for k, c in (('in005-persist', 'C3'), ('in0025-persist', 'C1')):
            ax.plot([d['t'] for d in h[k]], [d['eps_site'] for d in h[k]],
                    c, label=k)
        ax.axhline(ref8['eps_site'], ls='--', color='k', alpha=0.5,
                   label=f"ref floor t8 {ref8['eps_site']:.3f}")
        ax.axhline(ref8['eps_site'] - MARGIN_EPS, ls=':', color='k',
                   alpha=0.4, label='floor − 0.05 margin')
        ax.set_title('site mean |epsilon| (persistence arms)')
        ax.set_xlabel('t'); ax.legend(fontsize=8)

        # (0,1) q_site(t)
        ax = axes[0, 1]
        ax.plot(t_ref, [d['q_site'] for d in h_ref8], 'gray',
                label='ref (undriven)')
        for k, c in (('in005-persist', 'C3'), ('in0025-persist', 'C1')):
            ax.plot([d['t'] for d in h[k]], [d['q_site'] for d in h[k]],
                    c, label=k)
        ax.axhline(ref8['q_site'] + MARGIN_Q, ls=':', color='k', alpha=0.4,
                   label='ref q + 0.02')
        ax.set_title('site q (5-channel coherence)')
        ax.set_xlabel('t'); ax.legend(fontsize=8)

        # (0,2) variance halves
        ax = axes[0, 2]
        names = ['ref8', 'in0025-persist', 'in005-persist']
        x = np.arange(len(names))
        w = 0.35
        v1 = [s_ref8['eps_var_first_half'] if n == 'ref8'
              else s_arm[n]['eps_var_first_half'] for n in names]
        v2 = [s_ref8['eps_var_second_half'] if n == 'ref8'
              else s_arm[n]['eps_var_second_half'] for n in names]
        ax.bar(x - w / 2, v1, w, label='first half')
        ax.bar(x + w / 2, v2, w, label='second half')
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=15, fontsize=8)
        ax.set_yscale('log')
        ax.set_title('epsilon time-variance by half')
        ax.legend(fontsize=8)

        # (1,0) removal arms
        ax = axes[1, 0]
        ax.plot(t_ref, [d['eps_site'] for d in h_ref8], 'gray',
                label='ref (undriven)')
        for k, c in (('in005-removal', 'C3'), ('in0025-removal', 'C1')):
            ax.plot([d['t'] for d in h[k]], [d['eps_site'] for d in h[k]],
                    c, label=k)
        ax.axvline(T_REMOVE, ls='--', color='k', alpha=0.5,
                   label='drive off (t = 4)')
        ax.set_title('site mean |epsilon| (removal arms)')
        ax.set_xlabel('t'); ax.legend(fontsize=8)

        # (1,1) eps_rel vs amp across the full range (canonical init)
        ax = axes[1, 1]
        amps = sorted(rows)
        vals = [rows[a]['eps_rel'] for a in amps]
        ax.plot(amps, vals, 'o-', color='C2')
        for a, v in zip(amps, vals):
            ax.annotate(f"{v:.2f}", (a, v), textcoords='offset points',
                        xytext=(0, 6), fontsize=7, ha='center')
        ax.axhline(ref4['eps_rel'], ls='--', color='gray',
                   label=f"ref floor {ref4['eps_rel']:.3f}")
        ax.axhline(PUMP_EPS_REL, ls=':', color='k', alpha=0.5,
                   label=f'pump criterion {PUMP_EPS_REL}')
        if onset is not None:
            ax.axvline(onset, ls='--', color='C3', alpha=0.7,
                       label=f'onset {onset}')
        ax.set_yscale('log')
        ax.set_title('eps_rel vs in-channel amp (t = 4, canonical init)')
        ax.set_xlabel('amp'); ax.legend(fontsize=8)

        # (1,2) Fire fraction
        ax = axes[1, 2]
        ax.plot(t_ref, [d['phase_frac'][1] for d in h_ref8], 'gray',
                label='ref (undriven)')
        for k, c in (('in005-persist', 'C3'), ('in005-removal', 'C2')):
            ax.plot([d['t'] for d in h[k]], [d['phase_frac'][1] for d in h[k]],
                    c, label=k)
        ax.set_title('site Fire-channel fraction (churn basin)')
        ax.set_xlabel('t'); ax.legend(fontsize=8)

        fig.suptitle(f'Churning-gate quench-regime probe (canonical init, '
                     f'P0 {p0:.3f}, basin {basin}, t = 8 windows)')
        fig.tight_layout()
        fig.savefig(f"{rdir}/churning_quench.png", dpi=130)
        plt.close()
        print(f"\nFigure: {rdir}/churning_quench.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
