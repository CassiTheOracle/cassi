#!/usr/bin/env python3
"""Held-gate long-time drive: does the affirmation drain persist at 2/lambda?

Follow-up to `consciousness/gender-as-qi-configuration.md` §8
(`two-fluid/run_misgendering_drive.py`): on the HELD configuration
(standing init: pure Yang deficit, identity phase Fire 72 deg), the
misgendering tests at t = 2 found an in-channel (Fire) recurring drive
DRAINS the held site (0.261 retained, q-gap closed) while a cross-channel
(Wood) drive at eps-parity PUMPS it (2.075x), and §8.1 (t = 4 readings,
`two-fluid/run_misgendering_release.py`) found affirmation recovers below
the undriven floor. Those readings are all short-window (t = 2-4 =
0.1-0.2/lambda). The churning-gate arc learned the lesson
(`consciousness/neurodivergence-as-gate-configuration.md` §9.4,
`two-fluid/run_churning_gate_quench_long.py`): at t = 40 = 2/lambda the
sub-threshold quench resolved to a driven transient, the drive phase
inverting mid-run.

Binary question at t = 40 = 2/lambda (two conversion timescales,
1/lambda = 20 s): does sustained in-channel (affirmation) drive keep
draining the held site, or does the re-injection accumulate and invert
the drain — making the §8.1 "affirmation drains below the undriven
floor" claim a short-window effect like the churning quench was?

Protocol (lambda = 0.05, dt = 0.001, N = 48, t = 40 = 40000 steps).
Standing init exactly as the misgendering test (pure Yang deficit at the
site, identity phase Fire 72 deg), per-arm FRESH solver instances (the
canonical-init convention of `run_churning_gate_quench_long.py`: rk2_step
mutates the solver's scale factor, smoothed Hubble rate, and global
q_mean, so a shared solver makes later arms order-dependent). P0 is
measured in-process from a dedicated t = 4 reference run (4000 steps,
81-point series; the load-bearing window per the churning-arc convention
of `run_churning_gate_quench_long.py` — the t = 2 window gives P0 =
0.041, the t = 4 window P0 = 0.081 for the same physics, and pump
strength is drive-period sensitive: 2.08x at P0 = 0.041 vs 4.72x at
2P0 ~ 0.082, `gender-as-qi-configuration.md` §8.1; all drives run at
P0 = 0.081 here). The drive itself is the §8 schedule: a mean-zero
P0 oscillation added to the real-space field at the site before the
rk2 step — on ey for Fire (in-channel, affirmation, amp 0.15), on ei
for Wood (cross-channel, misgendering, amp 0.15/phi for eps-parity:
the conversion runs on eps = EY - phi*EI, so component amplitude a on
ei injects phi*a of eps while the same a on ey injects a).

Arms (4, fresh solver each):
  ref           standing init, no drive, t = 40 (does the held site
                itself relax on the conversion timescale? The churning
                ref decayed 0.87 -> 0.53; expect the standing site to
                decay too — the "floor" is moving)
  affirmation   Fire (in-channel) drive at P0, amp 0.15, t = 40.
                Discriminator: does eps_site stay >= 0.05 below the
                undriven floor at t = 4/20/40 (drain sustained) or
                cross above it at some t < 40 (drain transient, phase
                inversion)? Full eps_site(t) series + crossing time.
  misgendering  Wood (cross-channel) drive at eps-parity (amp 0.15/phi),
                t = 40. Does the pump plateau (bounded by clamp/
                conversion) or keep growing? (t = 2 gave 2.08x; the
                churning pump kept growing — does the held pump
                saturate?)
  affirmation-p041  Fire drive at the §8 drive period P0 = 0.041
                (the t = 2 window value), amp 0.15, t = 40.
                SUPPLEMENTARY arm: at the t = 4 window value
                P0 = 0.081 the in-channel drive PUMPS the held site
                from the start (rel 3.94 at t = 4, peak 9.7x — the
                §8.2 period law extended to Fire), so the drain
                question is unanswerable at that period: the §8 drain
                (0.261 at t = 2) exists only near P0 = 0.041. This arm
                runs the binary question at the period where the drain
                exists. Its t = 2 snapshot doubles as the fidelity check
                against §8 (the fresh-solver value is 0.071 rel vs §8's
                0.261: the §8 arms shared one solver, and a shared solver
                makes later arms order-dependent — the caveat the
                canonical-init convention rules out).

Diagnostics per arm (t = 4/20/40 snapshots + full series): eps_site
(mean |eps| over the site ball), eps_rel vs t = 0, q_site, q-gap,
phase histogram + phase_max, sigma_r_site, ey/ei_min_site + floor-touch
counts over the run (floor 1e-3, near-floor 1.5e-3), eps time-variance
in QUARTERS (t in [0,10), [10,20), [20,30), [30,40]). Extra diagnostic:
the site's own dominant period over the second half (t in [20, 40],
401-point window), window-binned per the dominant_period caveat of
`gender-as-qi-configuration.md` §8.1.

Verdict logic (printed explicitly):
  DRAIN-SUSTAINED  iff affirmation eps_site(t=40) <= ref eps_site(t=40)
                    - 0.05 AND affirmation q-gap(t=40) <= ref q-gap(t=40)
                    + 0.01.
  DRAIN-TRANSIENT  iff the affirmation eps series crosses above ref by
                    >= 0.05 at some t in [2, 40] and stays there
                    (>= 60% of subsequent reports >= ref + 0.05);
                    crossing time reported.
  AMBIGUOUS otherwise. The misgendering arm's behavior is reported
  honestly (growth rate, saturation, clamp limits) without a verdict
  threshold.

Checkpoint/resume (per pde-checkpoint-resume): per-arm checkpoints every
4000 steps save (step, a, H_smooth, H, q_mean, u_hat, ey_hat, ei_hat,
hist); --resume DIR skips completed arms (run_<tag>.json present) and
continues unfinished arms from their last checkpoint. State restored:
solver.a, solver._H_smooth, solver.H, solver.q_mean — the four scalars
rk2_step mutates (qi_memory is off in build_solver, so eps_sq_memory is
not carried).

Usage: python two-fluid/run_held_gate_longtime.py [--resume DIR]
Output: runs/<id>_held_gate_longtime/results.json + figure
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

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

T.LAM = 0.05
T.DT = 0.001
T.REPORT = 50

CLAMP_FLOOR = 1e-3
NEAR_FLOOR = 1.5e-3
T4_STEPS = 4000         # t = 4 (P0 window)
T40_STEPS = 40000       # t = 40 = 2/lambda
CKPT_EVERY = 4000       # checkpoint cadence (steps)

DRIVE_AMP = 0.15        # repo-standard drive amplitude (on ey; above the
                        # phase-blindness floor >= 0.05, below the known
                        # drain amplitude 0.3)
WOOD_AMP = DRIVE_AMP / T.PHI  # eps-parity: delta-eps from +-a on ei is
                              # +-phi*a, so Wood uses a/phi
FIRE = 1                # phase_frac index of the identity channel (72 deg)

# Verdict margins (house + task-specified)
MARGIN_EPS = 0.05       # drain arms must sit >= 0.05 below ref at t = 40
MARGIN_QGAP = 0.01      # affirmation q-gap <= ref q-gap + 0.01 at t = 40
CROSS_T0 = 2.0          # crossing window opens at t = 2 (the §8 drain
                        # reading point; the held-config inversion happens
                        # right after the drain window, t ~ 2-4, unlike the
                        # churning arc's t in [8, 40])
CROSS_FRACTION = 0.6    # >= 60% of post-crossing reports above ref + margin

T_GOALS = (2.0, 4.0, 20.0, 40.0)   # t = 2: the §8 drain reading point


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
                 drive_period=None, drive_amp=None, resume=False):
    """Fresh-solver standing init (seed 42); optional periodic drive.

    Standing-init construction and the drive schedule are reused from
    `run_misgendering_drive.py` (T.init_fields 'standing', seed 42; the
    mean-zero P0 oscillation added to the real-space field at the site
    before the rk2 step, on ey for Fire / ei for Wood at eps-parity).
    Mid-arm checkpointing every CKPT_EVERY steps, resume from the last
    checkpoint (solver state a / _H_smooth / H / q_mean restored — the
    four scalars rk2_step mutates). A FRESH solver is built per arm so
    no arm inherits the previous arm's state; identical schedules are
    bit-reproducible across fresh-solver arms.
    """
    amp = DRIVE_AMP if drive_amp is None else drive_amp
    print(f"\n=== run: {tag} (channel={drive_channel}, "
          f"period={drive_period}, amp={amp}, steps={steps}) ===")
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
        ey_hat, ei_hat, u_hat = T.init_fields(solver, 'standing', seed=42)
        hist = []

    for step in range(start_step, steps):
        ey = torch.fft.ifftn(ey_hat).real
        if drive_channel is not None:
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
    return s


def crossing_analysis(h_aff, h_ref, t0=CROSS_T0, margin=MARGIN_EPS):
    """First t >= t0 where aff eps_site >= ref eps_site + margin.

    Returns dict with crossing time, whether the crossing persists
    (>= CROSS_FRACTION of subsequent reports stay >= ref + margin), the
    max gap over [t0, 40], and the gap at t = 40.
    """
    out = {'crossing_time': None, 'persists': False, 'max_gap': 0.0,
           'gap_t40': None, 'cross_fraction': None, 'n_reports': 0}
    pts = []
    for da, dr in zip(h_aff, h_ref):
        if da['t'] >= t0:
            pts.append((da['t'], da['eps_site'] - dr['eps_site']))
    if not pts:
        return out
    gaps = np.array([g for _, g in pts])
    out['max_gap'] = float(gaps.max())
    out['gap_t40'] = float(gaps[-1])
    cross_i = np.argmax(gaps >= margin) if (gaps >= margin).any() else None
    if cross_i is not None:
        t_cross = pts[cross_i][0]
        after = gaps[cross_i:]
        frac = float((after >= margin).mean())
        out.update({'crossing_time': t_cross, 'persists': frac >= CROSS_FRACTION,
                    'cross_fraction': frac, 'n_reports': int(len(after))})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--resume', metavar='DIR', default=None,
                    help='resume an interrupted run directory')
    args = ap.parse_args()

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t=40 (2/lambda), "
          f"fire_amp={DRIVE_AMP}, wood_amp={WOOD_AMP:.4f}")

    if args.resume:
        rdir = os.path.normpath(args.resume)
        rid = os.path.basename(rdir)
        print(f"Resuming run directory {rdir}")
    else:
        rid = datetime.now().strftime("%Y%m%d_%H%M%S")
        rdir = os.path.join(REPO, 'runs', f"{rid}_held_gate_longtime")
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
    print(f"\nMeasured natural period P0 = {p0:.4f} (drive period = P0)")

    arms = {
        'ref':          dict(tag='ref', steps=T40_STEPS),
        'affirmation':  dict(tag='affirmation', steps=T40_STEPS,
                             drive_channel='fire', drive_period=p0,
                             drive_amp=DRIVE_AMP),
        'misgendering': dict(tag='misgendering', steps=T40_STEPS,
                             drive_channel='wood', drive_period=p0,
                             drive_amp=WOOD_AMP),
        # Supplementary: the §8 drain-period arm (P0 = 0.041 from the
        # t = 2 window). At the t = 4 window period 0.081 the Fire drive
        # pumps the held site from the start, so the drain question is
        # run at the period where the §8 drain exists.
        'affirmation-p041': dict(tag='affirmation-p041', steps=T40_STEPS,
                                 drive_channel='fire', drive_period=0.041,
                                 drive_amp=DRIVE_AMP),
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
                              resume=args.resume is not None)

    s_ref = arm_summary('ref', h['ref'])
    s_arm = {k: arm_summary(k, hh) for k, hh in h.items() if k != 'ref'}

    # ── Crossing / drain discriminator (per affirmation arm) ────────────
    aff_arms = ['affirmation', 'affirmation-p041']
    qgap_ref_t40 = s_ref['t40']['q_gap']
    cross = {k: crossing_analysis(h[k], h['ref']) for k in aff_arms}
    gaps = {k: s_arm[k]['t40']['eps_site'] - s_ref['t40']['eps_site']
            for k in aff_arms}
    qgaps = {k: s_arm[k]['t40']['q_gap'] for k in aff_arms}

    verdicts = {}
    for k in aff_arms:
        # A drain phase must exist at t = 2 (the §8 reading point) for
        # the drain-vs-inversion question to be meaningful at this drive
        # period.
        drain_phase_t2 = s_arm[k]['t2']['eps_site'] <= \
            s_ref['t2']['eps_site'] - MARGIN_EPS
        if not drain_phase_t2:
            verdicts[k] = 'NO-DRAIN-AT-PERIOD'
        elif cross[k]['persists']:
            verdicts[k] = 'DRAIN-TRANSIENT'
        elif gaps[k] <= -MARGIN_EPS and \
                qgaps[k] <= qgap_ref_t40 + MARGIN_QGAP:
            verdicts[k] = 'DRAIN-SUSTAINED'
        else:
            verdicts[k] = 'AMBIGUOUS'

    results = {
        'meta': {
            'P0': p0, 'drive_period': p0,
            'fire_amp': DRIVE_AMP, 'wood_amp': WOOD_AMP,
            'identity_channel': 'Fire (72 deg)',
            'misgendering_channel': 'Wood (0 deg)',
            'lam': T.LAM, 'N': T.N, 't_end': T40_STEPS * T.DT,
            'canonical_init': 'fresh solver per arm (rk2_step mutates '
                              'solver a / H_smooth / q_mean; shared-'
                              'solver reuse makes later arms order-'
                              'dependent)',
            'standing_init': 'pure Yang deficit, identity phase Fire '
                             '72 deg (T.init_fields standing, seed 42; '
                             'same init as run_misgendering_drive.py)',
            'p0_window': '81-point t=4 ref window (churning-arc '
                         'convention; the t=2 window gives P0 = 0.041 '
                         'for the same physics, and pump strength is '
                         'drive-period sensitive per §8.1: 2.08x at '
                         'P0 = 0.041 vs 4.72x at 2P0 ~ 0.082). RESULT: '
                         'at P0 = 0.081 the Fire drive pumps the held '
                         'site from the start (rel 3.94 at t = 4), so '
                         'the drain question is unanswerable at that '
                         'period; the affirmation-p041 arm runs it at '
                         'the §8 drain period 0.041',
            'clamp_floor': CLAMP_FLOOR, 'near_floor': NEAR_FLOOR,
            'margin_eps': MARGIN_EPS, 'margin_qgap': MARGIN_QGAP,
            'cross_window': f't in [{CROSS_T0:g}, 40]',
            'cross_persist_fraction': CROSS_FRACTION,
            'verdict_logic': 'NO-DRAIN-AT-PERIOD iff the arm is not '
                             '>= 0.05 below ref at t = 2 (no drain '
                             'window exists at this drive period); '
                             'else DRAIN-SUSTAINED iff eps_site(t40) '
                             '<= ref - 0.05 and q-gap(t40) <= ref '
                             'q-gap + 0.01; DRAIN-TRANSIENT iff the '
                             'eps series crosses above ref + 0.05 at '
                             'some t in [2, 40] and stays there '
                             '(>= 60% of subsequent reports)',
        },
        'ref': s_ref,
        'arms': s_arm,
        'crossing': cross,
        'verdict': {
            'verdicts': verdicts,
            'aff_gap_t40': gaps,
            'qgap_aff_t40': qgaps,
            'qgap_ref_t40': qgap_ref_t40,
            'drain_sustained_criteria': {
                k: {
                    'eps_gap_t40': gaps[k],
                    'eps_margin_ok': gaps[k] <= -MARGIN_EPS,
                    'qgap_margin_ok': qgaps[k] <=
                                      qgap_ref_t40 + MARGIN_QGAP,
                } for k in aff_arms
            },
            'crossing': cross,
        },
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    # ── Console tables ───────────────────────────────────────────────────
    print("\n=== HELD-GATE LONG-TIME DRIVE (t = 40 = 2/lambda) ===")
    print(f"P0 = {p0:.4f}  ref: eps t4 {s_ref['t4']['eps_site']:.3f} "
          f"(rel {s_ref['t4']['eps_rel']:.3f})  t20 "
          f"{s_ref['t20']['eps_site']:.3f}  t40 {s_ref['t40']['eps_site']:.3f} "
          f"(rel {s_ref['t40']['eps_rel']:.3f})  q_site t40 "
          f"{s_ref['t40']['q_site']:.3f}")

    hdr = (f"{'arm':>14s} {'eps4':>6s} {'eps20':>6s} {'eps40':>6s} "
           f"{'q40':>6s} {'qgap40':>7s} {'ph40':>5s} {'sigr40':>7s} "
           f"{'eymin':>7s} {'eimin':>7s} {'tch':>4s}")
    print(hdr)
    for name in ['ref', 'affirmation', 'affirmation-p041',
                 'misgendering']:
        s = s_ref if name == 'ref' else s_arm[name]
        t4, t20, t40 = s['t4'], s['t20'], s['t40']
        print(f"{name:>14s} {t4['eps_site']:6.3f} "
              f"{t20['eps_site']:6.3f} {t40['eps_site']:6.3f} "
              f"{t40['q_site']:6.3f} {t40['q_gap']:+7.3f} "
              f"{t40['phase_max']:5.2f} {t40['sigma_r_site']:7.4f} "
              f"{s['ey_min_run']:7.4f} {s['ei_min_run']:7.4f} "
              f"{s['ey_floor_touches']:4d}")

    print("\n--- eps variance by quarter (bounded vs decaying) ---")
    print(f"{'arm':>14s} {'q1':>9s} {'q2':>9s} {'q3':>9s} {'q4':>9s} "
          f"{'max/min':>8s} {'P2ndHalf':>9s}")
    for name in ['ref', 'affirmation', 'affirmation-p041',
                 'misgendering']:
        s = s_ref if name == 'ref' else s_arm[name]
        qv = s['eps_var_quarters']
        p2 = s['period_second_half']
        print(f"{name:>14s} " + " ".join(f"{v:9.5f}" for v in qv) +
              f" {s['eps_var_quarter_ratio']:8.2f} "
              f"{p2 if p2 is None else f'{p2:.4f}':>9s}")

    print("\n--- q_site over time + last-third slope ---")
    for name in ['ref', 'affirmation', 'affirmation-p041',
                 'misgendering']:
        s = s_ref if name == 'ref' else s_arm[name]
        print(f"{name:>14s} q0 {s['q_site_0']:.3f} -> "
              f"t4 {s['t4']['q_site']:.3f} -> t20 {s['t20']['q_site']:.3f} "
              f"-> t40 {s['t40']['q_site']:.3f}  "
              f"slope(last 1/3) {s['q_site_last_third_slope']:+.5f}")

    # ── Misgendering pump characterization ───────────────────────────────
    mg = s_arm['misgendering']
    mg_series = np.array([d['eps_site'] for d in h['misgendering']])
    mg_t = np.array([d['t'] for d in h['misgendering']])
    mg0 = mg['eps_site_0']
    half1 = mg_series[mg_t < 20.0]
    half2 = mg_series[mg_t >= 20.0]
    mg_rate = float(np.polyfit(mg_t[mg_t >= 4.0], mg_series[mg_t >= 4.0],
                               1)[0])
    print("\n--- misgendering (Wood) pump characterization ---")
    print(f"eps_site: t4 {mg['t4']['eps_site']:.3f} "
          f"t20 {mg['t20']['eps_site']:.3f} t40 {mg['t40']['eps_site']:.3f} "
          f"(rel t40 {mg['t40']['eps_rel']:.3f})")
    print(f"first-half mean {half1.mean():.3f}, second-half mean "
          f"{half2.mean():.3f}  linear slope over [4,40]: {mg_rate:+.5f}/s")
    print(f"clamp: ey_min_run {mg['ey_min_run']:.4f} "
          f"({mg['ey_floor_touches']} touches), ei_min_run "
          f"{mg['ei_min_run']:.4f} ({mg['ei_floor_touches']} touches)")

    print("\n=== VERDICT ===")
    for k in aff_arms:
        print(f"[{k}] period={0.041 if k.endswith('p041') else p0:.3f} "
              f"gap vs ref at t=40: {gaps[k]:+.3f} "
              f"(sustained needs <= -0.05), q-gap t40 {qgaps[k]:+.3f} "
              f"vs ref {qgap_ref_t40:+.3f} (needs <= ref + 0.01)")
        print(f"    crossing (t in [2, 40]): "
              f"time={cross[k]['crossing_time']}, "
              f"persists={cross[k]['persists']} (frac "
              f"{cross[k]['cross_fraction']}), "
              f"max_gap={cross[k]['max_gap']:+.3f}")
    for k in aff_arms:
        print(f"*** VERDICT [{k}]: {verdicts[k]} ***")
    if verdicts['affirmation-p041'] == 'DRAIN-SUSTAINED':
        print("The in-channel (affirmation) drive at the §8 drain period "
              "keeps the site >= 0.05 below the undriven floor through "
              "two conversion timescales with the q-gap closed: the §8.1 "
              "drain claim holds at t = 40 = 2/lambda; no phase "
              "inversion.")
    elif verdicts['affirmation-p041'] == 'DRAIN-TRANSIENT':
        print(f"The §8-period affirmation eps series crossed above ref "
              f"by >= 0.05 at t = {cross['affirmation-p041']['crossing_time']:.1f} "
              f"and stayed: the drain is a driven transient, not a "
              f"sustained state — the §8.1 short-window reading inverted "
              f"at the conversion timescale.")
    elif verdicts['affirmation-p041'] == 'NO-DRAIN-AT-PERIOD':
        print("At the §8 drain period the affirmation arm sits above the "
              "undriven floor already at t = 4: no drain window exists "
              "at any timescale at this period.")
    else:
        print("Neither criterion met cleanly; report per-arm numbers.")

    # ── Figure ─────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 3, figsize=(16, 9))
        t_ref = [d['t'] for d in h['ref']]
        for ax in axes.flat:
            ax.grid(alpha=0.3)

        # (0,0) eps(t): all arms + ref floor
        ax = axes[0, 0]
        ax.plot(t_ref, [d['eps_site'] for d in h['ref']], 'gray',
                label='ref (undriven)')
        ax.plot([d['t'] for d in h['affirmation']],
                [d['eps_site'] for d in h['affirmation']], 'C2',
                label='affirmation (Fire, P0)')
        ax.plot([d['t'] for d in h['affirmation-p041']],
                [d['eps_site'] for d in h['affirmation-p041']], 'C0',
                label='affirmation (Fire, P0=0.041)')
        ax.plot([d['t'] for d in h['misgendering']],
                [d['eps_site'] for d in h['misgendering']], 'C3',
                label='misgendering (Wood)')
        ax.axhline(s_ref['t40']['eps_site'], ls='--', color='k', alpha=0.5,
                   label=f"ref floor t40 {s_ref['t40']['eps_site']:.3f}")
        ax.set_title('site mean |epsilon|')
        ax.set_xlabel('t'); ax.legend(fontsize=8)

        # (0,1) q_site(t)
        ax = axes[0, 1]
        ax.plot(t_ref, [d['q_site'] for d in h['ref']], 'gray',
                label='ref (undriven)')
        for k, c in (('affirmation', 'C2'), ('affirmation-p041', 'C0'),
                     ('misgendering', 'C3')):
            ax.plot([d['t'] for d in h[k]], [d['q_site'] for d in h[k]],
                    c, label=k)
        ax.set_title('site q (5-channel coherence)')
        ax.set_xlabel('t'); ax.legend(fontsize=8)

        # (0,2) variance quarters
        ax = axes[0, 2]
        names = ['ref', 'affirmation', 'affirmation-p041',
                 'misgendering']
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

        # (1,0) eps_rel(t) normalized to t = 0
        ax = axes[1, 0]
        for name, c in (('ref', 'gray'), ('affirmation', 'C2'),
                        ('affirmation-p041', 'C0'),
                        ('misgendering', 'C3')):
            hh = h[name]
            e0 = max(hh[0]['eps_site'], 1e-12)
            ax.plot([d['t'] for d in hh],
                    [d['eps_site'] / e0 for d in hh], c, label=name)
        ax.set_title('eps_rel vs t=0')
        ax.set_xlabel('t'); ax.legend(fontsize=8)

        # (1,1) Fire fraction
        ax = axes[1, 1]
        ax.plot(t_ref, [d['phase_frac'][FIRE] for d in h['ref']], 'gray',
                label='ref (undriven)')
        for k, c in (('affirmation', 'C2'), ('affirmation-p041', 'C0'),
                     ('misgendering', 'C3')):
            ax.plot([d['t'] for d in h[k]],
                    [d['phase_frac'][FIRE] for d in h[k]], c, label=k)
        ax.set_title('site Fire-channel fraction (identity)')
        ax.set_xlabel('t'); ax.legend(fontsize=8)

        # (1,2) ey_min_site over time (clamp telemetry)
        ax = axes[1, 2]
        ax.plot(t_ref, [d['ey_min_site'] for d in h['ref']], 'gray',
                label='ref (undriven)')
        for k, c in (('affirmation', 'C2'), ('affirmation-p041', 'C0'),
                     ('misgendering', 'C3')):
            ax.plot([d['t'] for d in h[k]],
                    [d['ey_min_site'] for d in h[k]], c, label=k)
        ax.axhline(NEAR_FLOOR, ls=':', color='k', alpha=0.5,
                   label='near-floor 1.5e-3')
        ax.set_yscale('log')
        ax.set_title('site ey_min (positivity clamp telemetry)')
        ax.set_xlabel('t'); ax.legend(fontsize=8)

        fig.suptitle(f'Held-gate long-time drive (standing init, P0 '
                     f'{p0:.3f}, t = 40 = 2/lambda; '
                     f'verdict: {verdicts["affirmation-p041"]})')
        fig.tight_layout()
        fig.savefig(f"{rdir}/held_gate_longtime.png", dpi=130)
        plt.close()
        print(f"\nFigure: {rdir}/held_gate_longtime.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
