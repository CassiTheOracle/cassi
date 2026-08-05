#!/usr/bin/env python3
"""Churning-gate long-time quench: partial lock or driven state at 2/lambda?

Follow-up to `consciousness/neurodivergence-as-gate-configuration.md` §9.3
(`two-fluid/run_churning_gate_quench.py`): at t = 8 the sub-threshold
quench was persistent (ε below the undriven floor, bounded variance,
51–74% depth retention after drive removal, the 0.025 state with zero
relaxation) but the q_site elevation missed the +0.02 criterion
(+0.010/+0.016), so the verdict was AMBIGUOUS between partial-lock and
driven-quench. The observation window was only 4 s = 0.2/lambda of the
conversion timescale 1/lambda = 20 s.

Binary question at t = 40 = 2/lambda (two full conversion timescales):
does the sub-threshold quench hold as a stable state (partial-lock
confirmed), or does it relax onto the undriven trajectory (driven-quench
confirmed)? The discriminators are sharp: the 0.05 removal arm's §9.3
leak of ~0.007/s exhausts its t = 4 quench depth (~0.20) by t ~ 32 and
converges to ref if the quench is a driven transient; the 0.025 arm's
zero-relaxation holds flat to t = 40 if it is a lock.

Protocol (lambda = 0.05, dt = 0.001, N = 48, t = 40 = 40000 steps).
Every arm builds a FRESH solver instance and re-initializes the churning
init (seed 42), per the canonical-init convention of
`two-fluid/run_churning_gate_quench.py`: rk2_step mutates the solver's
scale factor, smoothed Hubble rate, and global q_mean, so a shared
solver makes later arms order-dependent. P0 is measured in-process from
a dedicated t = 4 reference run (4000 steps; reports include the
step-3999 endpoint, an 81-point series) — the load-bearing window: from
an 8000-step window the FFT bins shift P0 to 0.0800 and the amp-0.05 arm
pumps instead of quenching. All drives run at P0 = 0.081.

Arms (5):
  ref            undriven to t = 40 (where does the undriven churn
                 plateau? eps_rel was 0.78 at t = 8)
  in005-persist  in-channel (Fire) at P0, amp 0.05, to t = 40
  in0025-persist in-channel at P0, amp 0.025, to t = 40
  in005-removal  in-channel at P0, amp 0.05, to t = 4, drive OFF to t = 40
  in0025-removal in-channel at P0, amp 0.025, to t = 4, drive OFF to t = 40

Diagnostics (t = 4, 20, 40 snapshots + full series): eps_site (mean
|epsilon| over the site ball), eps_rel vs t = 0, q_site, q-gap, phase
histogram + phase_max, eps time-variance in QUARTERS (t in [0,10),
[10,20), [20,30), [30,40]; bounded vs decaying), q_site slope over the
last third, ey/ei_min_site + floor-touch counts, sigma_r_site. Extra
diagnostic: the site's own dominant period measured in-process over the
second half (t in [20, 40], 401-point window) of each persist arm and of
ref — does the quenched site's natural period drift from 0.081 while the
drive stays at fixed P0? (window-binned per the dominant_period caveat
of `consciousness/gender-as-qi-configuration.md` §8.1; the cross-arm
comparison is what matters.)

Persistence metric (same as §9.3): quench depth D(t) = ref_eps(t) -
arm_eps(t) at same-time t from the shared ref run; depth retention
P = D(40)/D(4). An arm counts as persistent if P >= 0.5 (holds >= 50%
of its t = 4 depth through two conversion timescales); driven-quench if
P < 0.25. The 0.025 arm's lock alternative: eps_site drift < 0.01
between t = 4 and t = 40.

Verdict logic:
  PARTIAL-LOCK CONFIRMED iff at t = 40: (a) both persist arms keep
    eps_site >= 0.05 below ref, (b) both persist arms' quarter variance
    max/min ratio <= 3 (bounded, not secular growth), (c) the 0.05
    removal arm retains >= 50% of its t = 4 quench depth OR the 0.025
    removal state is flat (|eps(40) - eps(4)| < 0.01), (d) both persist
    arms keep q_site >= ref q_site + 0.02 (the §9.3 miss criterion).
  DRIVEN-QUENCH CONFIRMED iff both persist arms' eps converges to
    within 0.05 of ref by t = 40, or the 0.05 removal depth retention
    falls below 25% at t = 40, or the q_site elevation decays to
    < +0.01 at t = 40.
  AMBIGUOUS otherwise (report per-arm regime; the boundary may be
  amplitude-dependent).

Clamp diagnostics per arm: ey_min_site/ei_min_site minima over the run
and the count of report steps touching the 1e-3 positivity floor (near
floor 1.5e-3), per the house convention.

Checkpoint/resume (per pde-checkpoint-resume): per-arm checkpoints every
4000 steps save (step, a, H_smooth, H, q_mean, u_hat, ey_hat, ei_hat,
hist); --resume DIR skips completed arms (run_<tag>.json present) and
continues unfinished arms from their last checkpoint. State restored:
solver.a, solver._H_smooth, solver.H, solver.q_mean — the four scalars
rk2_step mutates (qi_memory is off in build_solver, so eps_sq_memory is
not carried).

Usage: python two-fluid/run_churning_gate_quench_long.py [--resume DIR]
Output: runs/<id>_churning_quench_long/results.json + figure
"""

import os
import sys
import glob
import json
import time
import argparse
from datetime import datetime

import numpy as np
import torch

torch.backends.cudnn.benchmark = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_trauma_wake_lock as T
import run_churning_gate as G  # baseline: churning_init, arm_channels, ...
import run_churning_gate_quench as Q  # canonical-init conventions + verdict
                                      # margins (run_arm is NOT reused here:
                                      # it has no mid-arm checkpointing)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

T.LAM = 0.05
T.DT = 0.001
T.REPORT = 50

CLAMP_FLOOR = 1e-3
NEAR_FLOOR = 1.5e-3
T4_STEPS = 4000         # t = 4 (P0 window + drive-off time)
T40_STEPS = 40000       # t = 40 = 2/lambda
CKPT_EVERY = 4000       # checkpoint cadence (steps)
T_REMOVE = 4.0          # drive-off time for the removal arms
PERSIST_AMPS = [0.025, 0.05]

# Verdict margins (house + task-specified)
MARGIN_EPS = 0.05       # persist arms must sit >= 0.05 below ref at t = 40
MARGIN_Q = 0.02         # q_site elevation vs ref at t = 40 (the §9.3 miss)
VAR_QUARTER_CAP = 3.0   # bounded-variance cap (max/min of the quarters)
DEPTH_RETENTION = 0.5   # removal persistence floor (lock signature)
DRIVEN_RETENTION = 0.25 # removal floor (driven-quench signature)
FLAT_DRIFT = 0.01       # 0.025 lock alternative: eps drift < 0.01 since t = 4
Q_DECAY = 0.01          # q elevation below this = decayed (driven signature)

T_GOALS = (4.0, 20.0, 40.0)


def save_checkpoint(ckpt_dir, tag, step, solver, u_hat, ey_hat, ei_hat,
                    hist):
    ckpt_file = f"{ckpt_dir}/ckpt_{tag}_{step:06d}.pt"
    torch.save({
        'step': step, 'a': solver.a, 'H_smooth': solver._H_smooth,
        'H': solver.H, 'q_mean': solver.q_mean,
        'u_hat': u_hat, 'ey_hat': ey_hat, 'ei_hat': ei_hat,
        'hist': hist,
    }, ckpt_file)
    old = sorted(glob.glob(f"{ckpt_dir}/ckpt_{tag}_*.pt"))[:-2]
    for f in old:
        os.remove(f)
    return ckpt_file


def load_checkpoint(ckpt_dir, tag):
    cands = sorted(glob.glob(f"{ckpt_dir}/ckpt_{tag}_*.pt"))
    if not cands:
        return None
    return torch.load(cands[-1], weights_only=False)


def run_arm_long(device, tag, outdir, steps, drive_channel=None,
                 drive_period=None, drive_amp=None, drive_until=None,
                 resume=False):
    """Fresh-solver churning init (seed 42); optional periodic drive.

    Body follows `run_churning_gate_quench.run_arm` (same init, same
    drive schedule before the rk2 step, same report cadence) with two
    extensions: mid-arm checkpointing every CKPT_EVERY steps, and resume
    from the last checkpoint (solver state a / _H_smooth / H / q_mean are
    restored — the four scalars rk2_step mutates). A FRESH solver is
    built per arm so no arm inherits the previous arm's state; identical
    schedules are bit-reproducible across fresh-solver arms.
    """
    amp = G.DRIVE_AMP if drive_amp is None else drive_amp
    print(f"\n=== run: {tag} (channel={drive_channel}, "
          f"period={drive_period}, amp={amp}, steps={steps}, "
          f"drive_until={drive_until}) ===")
    solver = T.build_solver(device)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    t0 = time.time()

    if resume:
        ck = load_checkpoint(outdir, tag)
    else:
        ck = None
    if ck is not None:
        start_step = ck['step'] + 1
        u_hat, ey_hat, ei_hat = ck['u_hat'], ck['ey_hat'], ck['ei_hat']
        solver.a = ck['a']
        solver._H_smooth = ck['H_smooth']
        solver.H = ck['H']
        solver.q_mean = ck['q_mean']
        hist = ck['hist']
        print(f"  [{tag}] resuming from step {start_step} "
              f"({start_step * T.DT:.3f}s), {len(hist)} reports kept")
    else:
        start_step = 0
        ey_hat, ei_hat, u_hat = G.churning_init(solver, seed=42)
        hist = []

    for step in range(start_step, steps):
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

        if step % CKPT_EVERY == CKPT_EVERY - 1:
            save_checkpoint(outdir, tag, step, solver, u_hat, ey_hat,
                            ei_hat, hist)

    print(f"  [{tag}] {steps} steps in {time.time() - t0:.1f}s")
    with open(f"{outdir}/run_{tag}.json", "w") as f:
        json.dump({'kind': tag, 'hist': hist}, f, indent=1)
    for f in glob.glob(f"{outdir}/ckpt_{tag}_*.pt"):
        os.remove(f)
    return hist


def at_t(hist, t_goal):
    """Snapshot nearest to t_goal (exact for multiples of REPORT*DT)."""
    return min(hist, key=lambda d: abs(d['t'] - t_goal))


def quarter_variances(hist, nq=4):
    """eps_site time-variance per quarter of the run (bounded vs decay)."""
    eps_series = np.array([d['eps_site'] for d in hist])
    out = []
    n = len(eps_series)
    for k in range(nq):
        lo = k * n // nq
        hi = (k + 1) * n // nq
        out.append(float(eps_series[lo:hi].var()))
    return out


def arm_summary(name, hist, t_goals=T_GOALS):
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

    # eps time-variance in quarters (bounded vs decaying discriminator)
    qv = quarter_variances(hist)
    s['eps_var_quarters'] = qv
    s['eps_var_quarter_ratio'] = max(qv) / max(min(qv), 1e-12)

    # q_site trend: slope over the last third + first-vs-last tercile means
    t_arr = np.array([d['t'] for d in hist])
    q_arr = np.array([d['q_site'] for d in hist])
    terc = len(q_arr) // 3
    s['q_site_last_third_slope'] = float(np.polyfit(
        t_arr[-terc:], q_arr[-terc:], 1)[0])
    s['q_site_first_tercile'] = float(q_arr[:terc].mean())
    s['q_site_last_tercile'] = float(q_arr[-terc:].mean())

    # clamp: run minima + floor-touch count
    s['ey_min_run'] = min(d['ey_min_site'] for d in hist)
    s['ei_min_run'] = min(d['ei_min_site'] for d in hist)
    s['ey_floor_touches'] = sum(
        1 for d in hist if d['ey_min_site'] <= NEAR_FLOOR)
    s['ei_floor_touches'] = sum(
        1 for d in hist if d['ei_min_site'] <= NEAR_FLOOR)

    # natural period over the second half (t >= 20), window-binned
    half = [d for d in hist if d['t'] >= 20.0]
    s['period_second_half'] = (T.dominant_period(
        [d['eps_site'] for d in half], T.DT) if len(half) >= 8 else None)

    # leak rate over the removal window [4, 40] (linear slope)
    rem = [d for d in hist if d['t'] >= 4.0]
    s['eps_site_leak_4_40'] = float(np.polyfit(
        [d['t'] for d in rem], [d['eps_site'] for d in rem], 1)[0])
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--resume', metavar='DIR', default=None,
                    help='resume an interrupted run directory')
    args = ap.parse_args()

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  "
          f"t=40 (2/lambda), drive_until={T_REMOVE}")

    if args.resume:
        rdir = os.path.normpath(args.resume)
        rid = os.path.basename(rdir)
        print(f"Resuming run directory {rdir}")
    else:
        rid = datetime.now().strftime("%Y%m%d_%H%M%S")
        rdir = os.path.join(REPO, 'runs', f"{rid}_churning_quench_long")
        os.makedirs(rdir, exist_ok=True)

    # ── P0 reference: dedicated t=4 run (81-point window, load-bearing) ──
    if not args.resume or not os.path.exists(f"{rdir}/run_ref4.json"):
        h_ref4 = run_arm_long(device, tag='ref4', outdir=rdir,
                              steps=T4_STEPS)
    else:
        with open(f"{rdir}/run_ref4.json") as f:
            h_ref4 = json.load(f)['hist']
        print("ref4 already complete; reusing stored series")
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

    arms = {
        'ref':           dict(tag='ref', steps=T40_STEPS),
        'in005-persist': dict(tag='in005-persist', steps=T40_STEPS,
                              drive_channel=in_ch, drive_period=p0,
                              drive_amp=0.05),
        'in0025-persist': dict(tag='in0025-persist', steps=T40_STEPS,
                               drive_channel=in_ch, drive_period=p0,
                               drive_amp=0.025),
        'in005-removal': dict(tag='in005-removal', steps=T40_STEPS,
                              drive_channel=in_ch, drive_period=p0,
                              drive_amp=0.05, drive_until=T_REMOVE),
        'in0025-removal': dict(tag='in0025-removal', steps=T40_STEPS,
                               drive_channel=in_ch, drive_period=p0,
                               drive_amp=0.025, drive_until=T_REMOVE),
    }

    h = {}
    for key, spec in arms.items():
        outfile = f"{rdir}/run_{spec['tag']}.json"
        if args.resume and os.path.exists(outfile):
            with open(outfile) as f:
                h[key] = json.load(f)['hist']
            print(f"\n{key}: already complete; reusing stored series")
            continue
        h[key] = run_arm_long(device, spec['tag'], rdir,
                              steps=spec['steps'],
                              drive_channel=spec.get('drive_channel'),
                              drive_period=spec.get('drive_period'),
                              drive_amp=spec.get('drive_amp'),
                              drive_until=spec.get('drive_until'),
                              resume=args.resume is not None)

    s_ref = arm_summary('ref', h['ref'])
    s_arm = {k: arm_summary(k, hh) for k, hh in h.items() if k != 'ref'}

    # ── Removal discriminators ───────────────────────────────────────────
    depth4 = {k: s_ref['t4']['eps_site'] - s_arm[k]['t4']['eps_site']
              for k in ('in005-removal', 'in0025-removal')}
    depth40 = {k: s_ref['t40']['eps_site'] - s_arm[k]['t40']['eps_site']
               for k in ('in005-removal', 'in0025-removal')}
    retention = {}
    for k in depth4:
        retention[k] = (depth40[k] / depth4[k] if depth4[k] > MARGIN_EPS
                        else float('nan'))
    drift_4_40 = {k: abs(s_arm[k]['t40']['eps_site'] -
                         s_arm[k]['t4']['eps_site'])
                  for k in ('in005-removal', 'in0025-removal')}

    # ── Verdict ──────────────────────────────────────────────────────────
    ref40 = s_ref['t40']
    persist_eps_ok = all(
        s_arm[k]['t40']['eps_site'] <= ref40['eps_site'] - MARGIN_EPS
        for k in ('in005-persist', 'in0025-persist'))
    persist_q_ok = all(
        s_arm[k]['t40']['q_site'] >= ref40['q_site'] + MARGIN_Q
        for k in ('in005-persist', 'in0025-persist'))
    bounded_var = all(
        s_arm[k]['eps_var_quarter_ratio'] <= VAR_QUARTER_CAP
        for k in ('in005-persist', 'in0025-persist'))
    q_elev = {k: s_arm[k]['t40']['q_site'] - ref40['q_site']
              for k in ('in005-persist', 'in0025-persist')}
    q_decayed = all(v < Q_DECAY for v in q_elev.values())

    removal_holds = retention['in005-removal'] >= DEPTH_RETENTION
    removal_flat_0025 = drift_4_40['in0025-removal'] < FLAT_DRIFT
    removal_driven = any(retention[k] < DRIVEN_RETENTION
                         for k in ('in005-removal', 'in0025-removal'))

    # converge: both persist arms within MARGIN_EPS of ref at t = 40
    persist_eps_gap = {k: abs(s_arm[k]['t40']['eps_site'] -
                              ref40['eps_site'])
                       for k in ('in005-persist', 'in0025-persist')}
    driven_eps = all(g < MARGIN_EPS for g in persist_eps_gap.values())

    if persist_eps_ok and bounded_var and persist_q_ok and \
            (removal_holds or removal_flat_0025):
        verdict = 'PARTIAL-LOCK CONFIRMED'
    elif driven_eps or removal_driven or q_decayed:
        verdict = 'DRIVEN-QUENCH CONFIRMED'
    else:
        verdict = 'AMBIGUOUS'

    results = {
        'meta': {
            'P0': p0, 'drive_period': p0, 'lam': T.LAM, 'N': T.N,
            't_end': T40_STEPS * T.DT, 't_remove': T_REMOVE,
            'basin_t0': basin, 'eps_mean_t0': eps_mean_init,
            'in_channel': in_ch, 'cross_channel': cross_ch,
            'persist_amps': PERSIST_AMPS,
            'canonical_init': 'fresh solver per arm (rk2_step mutates '
                              'solver a / H_smooth / q_mean; shared-'
                              'solver reuse makes later arms order-'
                              'dependent)',
            'p0_window': '81-point t=4 ref window (load-bearing: the '
                         '80-point FFT bin gives P0 = 0.0800 and kills '
                         'the quench)',
            'clamp_floor': CLAMP_FLOOR, 'near_floor': NEAR_FLOOR,
            'margin_eps': MARGIN_EPS, 'margin_q': MARGIN_Q,
            'var_quarter_cap': VAR_QUARTER_CAP,
            'depth_retention_floor': DEPTH_RETENTION,
            'driven_retention_floor': DRIVEN_RETENTION,
            'flat_drift': FLAT_DRIFT, 'q_decay': Q_DECAY,
            'persistence_metric': 'D(t) = ref_eps(t) - arm_eps(t) from '
                                  'the shared ref run; retention '
                                  'P = D(40)/D(4); observation window '
                                  '36 s = 1.8/lambda after removal '
                                  '(two conversion timescales total); '
                                  'P >= 0.5 = lock (memory), '
                                  'P < 0.25 = driven quench (transient)',
            'period_second_half': 'dominant_period over t >= 20 '
                                  '(401-point window; window-binned per '
                                  'the dominant_period caveat)',
        },
        'ref': s_ref,
        'arms': s_arm,
        'quench_depth': {'depth4': depth4, 'depth40': depth40,
                         'retention': retention,
                         'drift_4_40': drift_4_40,
                         'leak_4_40': {k: s_arm[k]['eps_site_leak_4_40']
                                       for k in s_arm}},
        'verdict': {
            'verdict': verdict,
            'persist_eps_ok': persist_eps_ok,
            'persist_eps_gap_t40': persist_eps_gap,
            'persist_q_ok': persist_q_ok,
            'q_elev_t40': q_elev,
            'bounded_var': bounded_var,
            'var_quarter_ratios': {k: s_arm[k]['eps_var_quarter_ratio']
                                   for k in s_arm},
            'removal_holds_005': removal_holds,
            'removal_flat_0025': removal_flat_0025,
            'removal_driven_005': removal_driven,
            'q_decayed': q_decayed,
            'ref40_eps_site': ref40['eps_site'],
            'ref40_q_site': ref40['q_site'],
        },
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    # ── Console tables ───────────────────────────────────────────────────
    print("\n=== CHURNING-GATE LONG-TIME QUENCH (t = 40 = 2/lambda) ===")
    print(f"P0 = {p0:.4f}  ref: eps t4 {s_ref['t4']['eps_site']:.3f} "
          f"(rel {s_ref['t4']['eps_rel']:.3f})  t20 "
          f"{s_ref['t20']['eps_site']:.3f}  t40 {ref40['eps_site']:.3f} "
          f"(rel {ref40['eps_rel']:.3f})  q_site t40 {ref40['q_site']:.3f}")

    hdr = (f"{'arm':>15s} {'eps4':>6s} {'eps20':>6s} {'eps40':>6s} "
           f"{'q40':>6s} {'qgap40':>7s} {'ph40':>5s} {'sigr40':>7s} "
           f"{'eymin':>7s} {'tch':>4s}")
    print(hdr)
    for name in ['ref'] + [k for k in ('in005-persist', 'in0025-persist',
                                       'in005-removal', 'in0025-removal')]:
        s = s_ref if name == 'ref' else s_arm[name]
        t4, t40 = s['t4'], s['t40']
        print(f"{name:>15s} {t4['eps_site']:6.3f} "
              f"{s['t20']['eps_site']:6.3f} {t40['eps_site']:6.3f} "
              f"{t40['q_site']:6.3f} {t40['q_gap']:+7.3f} "
              f"{t40['phase_max']:5.2f} {t40['sigma_r_site']:7.4f} "
              f"{s['ey_min_run']:7.4f} {s['ey_floor_touches']:4d}")

    print("\n--- eps variance by quarter (bounded vs decaying) ---")
    print(f"{'arm':>15s} {'q1':>9s} {'q2':>9s} {'q3':>9s} {'q4':>9s} "
          f"{'max/min':>8s} {'P2ndHalf':>9s}")
    for name in ['ref'] + [k for k in ('in005-persist', 'in0025-persist',
                                       'in005-removal', 'in0025-removal')]:
        s = s_ref if name == 'ref' else s_arm[name]
        qv = s['eps_var_quarters']
        p2 = s['period_second_half']
        print(f"{name:>15s} " + " ".join(f"{v:9.5f}" for v in qv) +
              f" {s['eps_var_quarter_ratio']:8.2f} "
              f"{p2 if p2 is None else f'{p2:.4f}':>9s}")

    print("\n--- q_site over time + last-third slope ---")
    for name in ['ref'] + [k for k in ('in005-persist', 'in0025-persist',
                                       'in005-removal', 'in0025-removal')]:
        s = s_ref if name == 'ref' else s_arm[name]
        print(f"{name:>15s} q0 {s['q_site_0']:.3f} -> "
              f"t4 {s['t4']['q_site']:.3f} -> t20 {s['t20']['q_site']:.3f} "
              f"-> t40 {s['t40']['q_site']:.3f}  "
              f"slope(last 1/3) {s['q_site_last_third_slope']:+.5f}")

    print("\n--- removal / persistence ---")
    for k in ('in005-removal', 'in0025-removal'):
        print(f"{k}: depth4 {depth4[k]:.3f} depth40 {depth40[k]:.3f} "
              f"retention {retention[k]:.2f} "
              f"|drift t4->t40| {drift_4_40[k]:.3f} "
              f"leak [4,40] {s_arm[k]['eps_site_leak_4_40']:+.5f}/s")

    print("\n=== VERDICT ===")
    print(f"Persist arms eps <= ref40 - 0.05: {persist_eps_ok} "
          f"(gaps {persist_eps_gap})")
    print(f"Persist arms q_site >= ref40 + 0.02: {persist_q_ok} "
          f"(elev {q_elev})")
    print(f"Variance quarters max/min <= 3 (persist arms): {bounded_var}")
    print(f"Removal 0.05 retention >= 50%: {removal_holds}")
    print(f"Removal 0.025 flat (drift < 0.01): {removal_flat_0025}")
    print(f"Driven-eps (persist within 0.05 of ref): {driven_eps}")
    print(f"Removal retention < 25% (driven, either arm): {removal_driven}")
    print(f"q elevation decayed (< +0.01): {q_decayed}")
    print(f"*** VERDICT: {verdict} ***")

    # ── Figure ─────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 3, figsize=(16, 9))
        t_ref = [d['t'] for d in h['ref']]
        for ax in axes.flat:
            ax.grid(alpha=0.3)

        # (0,0) eps(t): persist arms + ref + floor
        ax = axes[0, 0]
        ax.plot(t_ref, [d['eps_site'] for d in h['ref']], 'gray',
                label='ref (undriven)')
        for k, c in (('in005-persist', 'C3'), ('in0025-persist', 'C1')):
            ax.plot([d['t'] for d in h[k]], [d['eps_site'] for d in h[k]],
                    c, label=k)
        ax.axhline(ref40['eps_site'], ls='--', color='k', alpha=0.5,
                   label=f"ref floor t40 {ref40['eps_site']:.3f}")
        ax.axhline(ref40['eps_site'] - MARGIN_EPS, ls=':', color='k',
                   alpha=0.4, label='floor − 0.05 margin')
        ax.set_title('site mean |epsilon| (persistence arms)')
        ax.set_xlabel('t'); ax.legend(fontsize=8)

        # (0,1) q_site(t)
        ax = axes[0, 1]
        ax.plot(t_ref, [d['q_site'] for d in h['ref']], 'gray',
                label='ref (undriven)')
        for k, c in (('in005-persist', 'C3'), ('in0025-persist', 'C1')):
            ax.plot([d['t'] for d in h[k]], [d['q_site'] for d in h[k]],
                    c, label=k)
        ax.axhline(ref40['q_site'] + MARGIN_Q, ls=':', color='k', alpha=0.4,
                   label='ref q + 0.02')
        ax.set_title('site q (5-channel coherence)')
        ax.set_xlabel('t'); ax.legend(fontsize=8)

        # (0,2) variance quarters
        ax = axes[0, 2]
        names = ['ref', 'in0025-persist', 'in005-persist']
        x = np.arange(len(names))
        w = 0.2
        for qi in range(4):
            vals = [s_ref['eps_var_quarters'][qi] if n == 'ref'
                    else s_arm[n]['eps_var_quarters'][qi] for n in names]
            ax.bar(x + (qi - 1.5) * w, vals, w, label=f'q{qi + 1}')
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=15, fontsize=8)
        ax.set_yscale('log')
        ax.set_title('epsilon time-variance by quarter')
        ax.legend(fontsize=8)

        # (1,0) removal arms
        ax = axes[1, 0]
        ax.plot(t_ref, [d['eps_site'] for d in h['ref']], 'gray',
                label='ref (undriven)')
        for k, c in (('in005-removal', 'C3'), ('in0025-removal', 'C1')):
            ax.plot([d['t'] for d in h[k]], [d['eps_site'] for d in h[k]],
                    c, label=k)
        ax.axvline(T_REMOVE, ls='--', color='k', alpha=0.5,
                   label='drive off (t = 4)')
        ax.set_title('site mean |epsilon| (removal arms)')
        ax.set_xlabel('t'); ax.legend(fontsize=8)

        # (1,1) eps_rel(t) normalized to t = 0 (persist + ref)
        ax = axes[1, 1]
        for name, c in (('ref', 'gray'), ('in005-persist', 'C3'),
                        ('in0025-persist', 'C1')):
            hh = h[name]
            e0 = max(hh[0]['eps_site'], 1e-12)
            ax.plot([d['t'] for d in hh],
                    [d['eps_site'] / e0 for d in hh], c, label=name)
        ax.set_title('eps_rel vs t=0 (persistence arms)')
        ax.set_xlabel('t'); ax.legend(fontsize=8)

        # (1,2) Fire fraction
        ax = axes[1, 2]
        ax.plot(t_ref, [d['phase_frac'][1] for d in h['ref']], 'gray',
                label='ref (undriven)')
        for k, c in (('in005-persist', 'C3'), ('in005-removal', 'C2')):
            ax.plot([d['t'] for d in h[k]], [d['phase_frac'][1] for d in h[k]],
                    c, label=k)
        ax.set_title('site Fire-channel fraction (churn basin)')
        ax.set_xlabel('t'); ax.legend(fontsize=8)

        fig.suptitle(f'Churning-gate long-time quench (canonical init, '
                     f'P0 {p0:.3f}, basin {basin}, t = 40 = 2/lambda)')
        fig.tight_layout()
        fig.savefig(f"{rdir}/churning_quench_long.png", dpi=130)
        plt.close()
        print(f"\nFigure: {rdir}/churning_quench_long.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
