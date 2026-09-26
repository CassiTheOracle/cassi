#!/usr/bin/env python3
"""Two-strand Yin-Yang breathing suite: does the separation mode oscillate?

Run:  python two-fluid/run_two_strand_breathing_suite.py

The two-strand program's fourth collective variable is "separation or
breathing" (`consciousness/two-strand-qi-neuroscience.md` sec 2).  The
Yin-excess branch (`hypotheses/two-strand-five-channel-matter-organization.md`
sec 3.5) is the only finite-separation branch the canonical PDE supports:
Pi = EY - EI < 0 in every ridge makes the buoyancy force F = Pi grad(Phi)
self-attractive, the pair contracts, conversion erases the Yin excess by
t ~ 21 (Pi sign flip), and the remnant coalesces at t ~ 47.6.  The native
conversion is one-way (eps -> 0; no negative attractor) and a continuous
drive only drains the excess, so the first scratch test is the DISCRETE
field exchange Psi_Y <-> Psi_I (Pi -> -Pi exactly), the init's own
transformation, applied between steps at a cadence anchored to the
in-process natural period P0 of the reference arm (fallback 1/lambda --
the single existing conversion timescale, matching the measured natural
flip 21.3 ~= 1/lambda -- when the ref series has no dominant period).
FORCED SCRATCH PHYSICS: the exchange is not a PDE term; it is an
externally imposed instantaneous operation, labeled in every record.

Arms (all: canonical solver untouched, fresh solver per arm, N = 48,
lam = 0.05, dt = 0.001, gate 'five', Yin-excess pair init sep = 12,
density-tracked strand balls, REPORT = 100):

  native   no drive, t = 80.  Reproduction arm: must re-measure the Pi
           sign flip (t ~ 21.3) and coalescence (t ~ 47.6) of the
           committed records (20260807_014428_two_strand_yin_excess,
           20260807_025739_two_strand_yin_excess_cont), record-by-record
           continuity at the continuation's own tolerance; supplies the
           in-process P0 and the moving no-drive floor.
  swap_p0  field exchange at cadence P0 (t = 5 P0, 5 exchanges) -- the
           primary scratch test.  Breathing requires >= 2 complete
           Yin -> Yang -> Yin cycles per ridge in per-ridge Pi AND a d(t)
           response of >= 2 full cycles at period 2 P0 (+-30%) or a
           converged limit-cycle diagnostic.
  swap_phi field exchange at cadence phi*P0 (t = 4 phi P0, 4 exchanges)
           -- golden-ratio cadence control (the framework's own ratio).
  swap_e   field exchange at cadence e*P0 (t = 3 e P0, 3 exchanges) --
           incommensurate cadence control (churning-gate period-control
           convention).
  drive    the existing churning-gate drive convention
           (`two-fluid/run_churning_gate.py`): periodic in-channel
           (Fire / ey) oscillation at the central site mask (R = 6,
           covers the pair envelope), amplitude 0.15, period P0 -- the
           repo's existing periodic-drive alternative (continuous, one-way
           draining; expected to accelerate coalescence, contrast arm).

Measurements (every record): Pi(t) per ridge (pi_strand both ridges,
pi_mid, pi_glob, Pi_tot), per-ridge Pi sign fractions and cycle counts,
phase lag (cross-correlation of pi_mid vs d_dot in units of P0, plus a
per-half-cycle extremum timing table), d(t) and d_dot (smoothed central
difference), q (q_mid/q_flank/q_glob), epsilon (eps_mid + per-strand
A/eps), mass (component totals + drift), clamp (ey_min/ei_min +
floor-touch count), twist proxy (delta_theta relative phase and theta_xy
pair-axis orientation; Tw = 0 by construction for the planar init),
five-channel projections (per-strand ch_open[5], phase_frac[5],
conv_gate[5], conv_phase[5], dominant channel, sheng_ke), H/a telemetry.

Verdicts (results.json):
  B1  native reproduction: continuity + flip time + coalescence time.
  B2  swap_p0 breathing: per-ridge Pi alternations (>= 2 complete cycles
      on BOTH ridges, |pi| >= 0.05 at each extremum), d-response (>= 2
      full cycles at 2 P0 +-30% or converged limit cycle), phase lag.
      A forced Pi alternation without the d-response is a driven
      artifact, reported as NULL -- no breathing claim from a sign flip.
  B2c cadence controls: per-ridge Pi and d cycles at the phi*P0 and e*P0
      cadences; period-specificity (primary breathes, controls do not)
      anchors the breathing to P0.
  B3  drive alternative: d cycles, coalescence-time shift vs native, and
      the standard churning summaries (eps_rel, q_gap, basin).
  B4  telemetry: per-arm mass drift, floor touches, a_end, H_end, NaN
      abort; scratch-operation counts.

Output (runs/ is gitignored -- commit the script only):
  runs/<rid>_two_strand_breathing/run_<arm>.json   per-arm histories
  runs/<rid>_two_strand_breathing/results.json     meta + verdicts
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
import run_two_strand_yin_excess_suite as S          # suite module, read-only
import run_two_strand_yin_excess_continuation as SC  # continuity fn, read-only
import run_trauma_wake_lock as T

# ── Protocol (suite-identical) ───────────────────────────────────────────
T.LAM = 0.05
T.DT = 0.001
REPORT = 100                 # measurement cadence (steps)
SEP = 12                     # baseline pair separation (cells)
FLOOR = 1e-3                 # solver positivity clamp floor
FLOOR_TOUCH = 1.01e-3        # telemetry trigger (as the suite)
CHANNELS = ['Wood', 'Fire', 'Earth', 'Metal', 'Water']

LAM_INV = 1.0 / T.LAM        # 20: the single existing conversion timescale
P0_ACCEPT = (0.25 * LAM_INV, 3.0 * LAM_INV)   # P0 acceptance window [5, 60]
DRIVE_AMP = 0.15             # the committed churning-gate amplitude
DRIVE_T_END = 80.0

# Reproduction targets from the committed records
T_FLIP_REF = 21.3            # first record with both pi_strand >= 0
T_FLIP_TOL = 0.5
T_MERGE_REF = 47.6           # first record with a single ridge or d < 2
T_MERGE_TOL = 2.0
D40_REF = 7.5086             # d at t = 40 from the continuation record
D40_TOL = 0.01

# Breathing thresholds (stated in the protocol, not fitted)
PI_AMP_MIN = 0.05            # per-ridge Pi extremum floor (mean-field
                             # reading resolution ~0.03)
D_AMP_MIN = 0.5              # d-cycle amplitude floor (cells)
PERIOD_TOL = 0.30            # cycle-period tolerance vs the cadence


def pi_ridge_stats(h):
    """Per-ridge Pi sign fractions and complete Yin->Yang->Yin cycles.

    For each ridge: sign fraction = fraction of records with
    pi_strand[k] < 0 (Yin) vs >= 0 (Yang); cycle count = complete
    Yin -> Yang -> Yin alternations with |pi| >= PI_AMP_MIN at each
    phase extremum, counted over the TWO-STRAND window only (records
    before the first single-ridge/coalesced record -- post-coalescence
    alternations are single-ridge pumping, not strand cycles).  Flat
    segments (|pi| < PI_AMP_MIN) are dropped from the collapsed phase
    sequence: they are the crossing band, not a phase."""
    h = [d for d in h if not (d['merged'] or d['d'] < 2.0)]
    if len(h) < 2:
        return [{'ridge': k, 'yin_frac': None, 'yang_frac': None,
                 'phase_seq': [], 'cycles': 0, 'two_strand_window': False}
                for k in range(2)]
    out = []
    for k in range(2):
        pi = np.array([d['pi_strand'][k] for d in h])
        yin_frac = float((pi < 0.0).mean())
        signs = []
        for p in pi:
            if p <= -PI_AMP_MIN:
                signs.append('Yin')
            elif p >= PI_AMP_MIN:
                signs.append('Yang')
            else:
                signs.append('flat')
        seq = []
        for s in signs:                      # collapse repeats, drop flats
            if s == 'flat':
                continue
            if not seq or s != seq[-1]:
                seq.append(s)
        n_cyc = sum(1 for i in range(len(seq) - 2)
                    if seq[i] == 'Yin' and seq[i + 1] == 'Yang'
                    and seq[i + 2] == 'Yin')
        out.append({'ridge': k, 'yin_frac': yin_frac,
                    'yang_frac': 1.0 - yin_frac,
                    'phase_seq': seq, 'cycles': n_cyc,
                    'two_strand_window': True})
    return out


def smoothed_derivative(ts, vals, window=5):
    """Central difference of a series over +-window records."""
    vals = np.asarray(vals, dtype=float)
    ts = np.asarray(ts, dtype=float)
    out = np.zeros_like(vals)
    for i in range(len(vals)):
        lo, hi = max(0, i - window), min(len(vals), i + window + 1)
        if hi - lo < 2:
            continue
        out[i] = (vals[hi - 1] - vals[lo]) / (ts[hi - 1] - ts[lo])
    return out


def d_cycles(h, period_ref):
    """Full d(t) oscillation cycles at the expected breathing period.

    Extrema of the smoothed d series (sign changes of d_dot) strictly
    alternate max/min, so consecutive extrema are HALF-cycles spaced at
    period_ref/2.  A full cycle is a max->min->max (or min->max->min)
    triplet: count valid half-cycle spacings (within +-PERIOD_TOL of
    period_ref/2, vertical span >= D_AMP_MIN against the nearest
    opposite-type extremum) and floor at full cycles (valid_spacings // 2,
    exact because types strictly alternate).
    Returns (n_full_cycles, extremum indices)."""
    ts = np.array([d['t'] for d in h])
    d = np.array([d['d'] for d in h])
    ddot = smoothed_derivative(ts, d)
    idx = []
    for i in range(1, len(ddot) - 1):
        if ddot[i - 1] > 0 and ddot[i] <= 0:      # local maximum
            idx.append((i, 'max'))
        elif ddot[i - 1] < 0 and ddot[i] >= 0:    # local minimum
            idx.append((i, 'min'))
    if len(idx) < 2:
        return 0, []
    # local prominence: vertical span vs the nearest opposite-type extremum
    # on either side must exceed D_AMP_MIN
    keep = []
    for j, (i, kind) in enumerate(idx):
        best = None
        for j2, (i2, kind2) in enumerate(idx):
            if j2 == j or kind2 == kind:
                continue
            span = abs(d[i] - d[i2])
            if best is None or span < best:
                best = span
        if best is not None and best >= D_AMP_MIN:
            keep.append(i)
    if len(keep) < 2:
        return 0, []
    half = 0.5 * period_ref
    n_valid = 0
    for i in range(1, len(keep)):
        spacing = ts[keep[i]] - ts[keep[i - 1]]
        if abs(spacing - half) <= PERIOD_TOL * half:
            n_valid += 1
    return n_valid // 2, [int(i) for i in keep]


def limit_cycle_diag(h, drive_times):
    """Stability of Poincare samples (d, d_dot, pi_mid) at drive instants.

    A stable 2-cycle has same-phase samples converging: the final
    |x_{n+2} - x_n| step <= PERIOD_TOL of the sample norm and not larger
    than the first step."""
    ts = np.array([d['t'] for d in h])
    d = np.array([d['d'] for d in h])
    ddot = smoothed_derivative(ts, d)
    pi = np.array([d['pi_mid'] for d in h])
    xs = []
    for st in drive_times:
        j = int(np.argmin(np.abs(ts - st)))
        xs.append(np.array([d[j], ddot[j], pi[j]]))
    if len(xs) < 4:
        return None, xs
    steps = [np.linalg.norm(xs[i + 2] - xs[i]) for i in range(len(xs) - 2)]
    rel = [s / (np.linalg.norm(xs[i]) + 1e-12) for i, s in enumerate(steps)]
    converged = (len(rel) >= 2 and rel[-1] <= PERIOD_TOL
                 and rel[-1] <= rel[0] * 1.05)
    return {'converged': bool(converged), 'abs_steps': steps,
            'rel_steps': rel}, xs


def phase_lag(h, period_ref):
    """Cross-correlation lag of pi_mid vs d_dot, in units of period_ref."""
    ts = np.array([d['t'] for d in h])
    pi = np.array([d['pi_mid'] for d in h])
    ddot = smoothed_derivative(ts, np.array([d['d'] for d in h]))
    pn = (pi - pi.mean()) / (pi.std() + 1e-30)
    dn = (ddot - ddot.mean()) / (ddot.std() + 1e-30)
    n = len(ts)
    lags = np.arange(-n + 1, n)
    cc = np.correlate(pn, dn, mode='full')
    k = int(np.argmax(cc))
    lag_t = lags[k] * (ts[1] - ts[0]) if n > 1 else 0.0
    return {'lag_t': float(lag_t), 'lag_frac': float(lag_t / period_ref),
            'cc_max': float(cc[k] / n)}


def flip_and_merge_times(h):
    """First both-strands-positive record (Pi flip) and first single-ridge
    or d < 2 record (coalescence); None when absent."""
    flip_t = None
    for d in h:
        if all(p >= 0.0 for p in d['pi_strand']):
            flip_t = d['t']
            break
    merge_t = None
    for d in h[1:]:
        if d['merged'] or d['d'] < 2.0:
            merge_t = d['t']
            break
    return flip_t, merge_t


def at_t(h, t_target):
    return min(h, key=lambda d: abs(d['t'] - t_target))


def run_arm(mode, outdir, tag=None, swap_period=None, t_end=None, p0=None):
    """Evolve one arm (fresh solver inside).  mode: native | swap | drive.

    tag: filename/record label (defaults to mode; the swap family uses
    distinct tags so no run file is clobbered).  swap arms: discrete
    Psi_Y <-> Psi_I exchange at cadence swap_period.  drive arm:
    churning-gate Fire/ey site drive at period p0, amp 0.15.
    Returns (hist, meta)."""
    if tag is None:
        tag = mode
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    solver = T.build_solver(device)
    steps = int(round(t_end / T.DT))
    print(f"\n=== run: {tag} (t_end={t_end:.1f}, steps={steps}, "
          f"swap_period={swap_period}, p0={p0}) ===")
    ey_hat, ei_hat, u_hat = S.yin_excess_init(solver, SEP)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)

    ey0 = torch.fft.ifftn(ey_hat).real
    ei0 = torch.fft.ifftn(ei_hat).real
    mass0 = {'ey': float(ey0.sum()), 'ei': float(ei0.sum()),
             'tot': float((ey0 + ei0).sum())}
    centers = [solver.N / 2.0 - SEP / 2.0, solver.N / 2.0 + SEP / 2.0]
    prev = None
    t0 = time.time()
    hist = []
    floor_touch = 0
    nan_abort = None
    n_swap = 0
    cy = cz = solver.N // 2
    swap_steps = ([int(round(n * swap_period / T.DT)) for n in range(1, 6)]
                  if mode == 'swap' and swap_period else [])
    swap_steps = [s for s in swap_steps if s < steps]
    swap_times = [s * T.DT for s in swap_steps]
    snap_steps = sorted({0, 4000, steps - 1})

    for step in range(steps):
        # ── scratch operations between steps (no solver edits) ──────────
        if mode == 'swap' and step in swap_steps:
            ey_hat, ei_hat = ei_hat, ey_hat      # Psi_Y <-> Psi_I, Pi -> -Pi
            n_swap += 1
        elif mode == 'drive':
            t_now = step * T.DT
            drive = DRIVE_AMP * np.sin(2.0 * np.pi * t_now / p0)
            ey = torch.fft.ifftn(ey_hat).real
            ey = ey + drive * mask
            ey_hat = torch.fft.fftn(ey)

        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)

        if step % REPORT == 0 or step == steps - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            if bool(torch.isnan(ey).any()) or bool(torch.isnan(ei).any()):
                nan_abort = step
                print(f"  [{tag}] NaN in the fields at step {step} "
                      f"(t={step * T.DT:.3f}); aborting the arm")
                break
            rho_prof = (ey + ei).sum(dim=(1, 2)).cpu().numpy()
            d = S.measure_density(solver, ey, ei, rho_prof, centers, prev)
            prev = ([d['x1'], d['x2']] if not d['merged'] else [d['x1']])
            S.pi_telemetry(solver, ey, ei, d)
            d.update({'step': step, 't': step * T.DT,
                      'a': float(solver.a), 'H': float(solver.H)})
            if d['ey_min'] < FLOOR_TOUCH or d['ei_min'] < FLOOR_TOUCH:
                floor_touch += 1
            if step in snap_steps:
                q = T.channel_openness(ey, ei)[1]
                eps_f = ey - S.C.PHI * ei
                pi_f = ey - ei
                d['q_prof'] = q[:, cy, cz].cpu().numpy().tolist()
                d['eps_prof'] = eps_f[:, cy, cz].cpu().numpy().tolist()
                d['pi_prof'] = pi_f[:, cy, cz].cpu().numpy().tolist()
                d['rho_prof_ax'] = (ey + ei)[:, cy, cz].cpu().numpy().tolist()
            hist.append(d)
            if step % (10 * REPORT) == 0 or step == steps - 1:
                s0 = d['strands'][0]
                s1 = (d['strands'][1] if not d['merged'] else d['strands'][0])
                print(f"  t={step * T.DT:5.1f} | d={d['d']:6.3f} "
                      f"Rc={d['Rc']:6.2f} | dth={d['delta_theta']:+6.3f} "
                      f"| pi=[{d['pi_strand'][0]:+.3f},"
                      f"{d['pi_strand'][1]:+.3f}] "
                      f"| A=[{s0['A']:.3f},{s1['A']:.3f}] "
                      f"| q_mid={d['q_mid']:.3f} q_flank={d['q_flank']:.3f} "
                      f"| ey_min={d['ey_min']:.4f} ei_min={d['ei_min']:.4f}")
    ey1 = torch.fft.ifftn(ey_hat).real
    ei1 = torch.fft.ifftn(ei_hat).real
    mass1 = {'ey': float(ey1.sum()), 'ei': float(ei1.sum()),
             'tot': float((ey1 + ei1).sum())}
    mass_drift = {k: abs(mass1[k] - mass0[k]) / abs(mass0[k])
                  for k in mass0}
    elapsed = time.time() - t0
    meta = {'mode': mode, 'tag': tag, 'elapsed': elapsed,
            'floor_touch': floor_touch,
            'mass0': mass0, 'mass1': mass1, 'mass_drift': mass_drift,
            'a_end': float(solver.a), 'H_end': float(solver.H),
            'nan_abort': nan_abort, 'n_swap': n_swap,
            'swap_period': swap_period, 'swap_times': swap_times,
            'drive_period': p0 if mode == 'drive' else None,
            'drive_amp': DRIVE_AMP if mode == 'drive' else None,
            'scratch_note': (
                'Psi_Y <-> Psi_I field exchange applied between steps at '
                'the stated cadence -- FORCED SCRATCH PHYSICS, not a PDE '
                'term' if mode == 'swap' else
                'churning-gate drive convention at the central site mask '
                '-- scratch-layer drive, no solver edit'
                if mode == 'drive' else 'no scratch operation')}
    print(f"  [{mode}] {len(hist)} records in {elapsed:.1f}s "
          f"(floor touches: {floor_touch}, mass drift: "
          f"{mass_drift['tot']:.2e}, a_end: {meta['a_end']:.4f}, "
          f"H_end: {meta['H_end']:.4f}, swaps: {n_swap})")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'mode': mode, 'sep': SEP, 'yin': True,
                       'hist': hist, 'meta': meta}, f, indent=1)
    return hist, meta


def main():
    argv = sys.argv[1:]
    arms_req = ['native', 'swap_p0', 'swap_phi', 'swap_e', 'drive']
    baseline_dir = None
    k = 0
    while k < len(argv):
        if argv[k] == '--arms':
            arms_req = [a.strip() for a in argv[k + 1].split(',')]
            k += 1
        elif argv[k] == '--baseline-dir':
            baseline_dir = argv[k + 1]
            k += 1
        k += 1
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  gate='five'  SEP={SEP}")
    print(f"Arms requested: {arms_req}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_two_strand_breathing"
    os.makedirs(rdir, exist_ok=True)

    arms, meta = {}, {}

    # ── native reference: reproduction + in-process P0 ───────────────────
    if 'native' in arms_req:
        h, m = run_arm('native', rdir, t_end=80.0)
        arms['native'], meta['native'] = h, m
    else:
        if baseline_dir is None:
            baseline_dir = max(
                [d for d in os.listdir('runs')
                 if d.endswith('_two_strand_breathing')],
                key=lambda d: os.path.getmtime(f"runs/{d}"))
        with open(f"{baseline_dir}/run_native.json") as f:
            h = json.load(f)['hist']
        arms['native'] = h
        meta['native'] = {'mode': 'native', 'tag': 'native',
                          'loaded_from': baseline_dir}
        print(f"native loaded from {baseline_dir} (not re-run)")

    p0 = T.dominant_period([d['pi_mid'] for d in arms['native']], T.DT)
    p0_measured = p0 if (p0 is not None
                         and P0_ACCEPT[0] <= p0 <= P0_ACCEPT[1]) else None
    p0 = p0_measured if p0_measured is not None else LAM_INV
    print(f"\nIn-process P0 (dominant period of the native pi_mid series): "
          f"{p0_measured if p0_measured is not None else 'none in [5, 60]'} "
          f"-> used P0 = {p0:.3f} "
          f"{'(fallback 1/lambda)' if p0_measured is None else ''}")

    # ── swap family (primary + cadence controls) ─────────────────────────
    t_phi = min(4.0 * p0 * S.C.PHI, 220.0)
    t_e = min(3.0 * p0 * np.e, 220.0)
    if 'swap_p0' in arms_req:
        h, m = run_arm('swap', rdir, tag='swap_p0', swap_period=p0,
                       t_end=5.0 * p0)
        arms['swap_p0'], meta['swap_p0'] = h, m
    if 'swap_phi' in arms_req:
        h, m = run_arm('swap', rdir, tag='swap_phi',
                       swap_period=p0 * S.C.PHI, t_end=t_phi)
        arms['swap_phi'], meta['swap_phi'] = h, m
    if 'swap_e' in arms_req:
        h, m = run_arm('swap', rdir, tag='swap_e',
                       swap_period=p0 * np.e, t_end=t_e)
        arms['swap_e'], meta['swap_e'] = h, m

    # ── drive arm: the existing churning-gate alternative ────────────────
    if 'drive' in arms_req:
        h, m = run_arm('drive', rdir, p0=p0, t_end=DRIVE_T_END)
        arms['drive'], meta['drive'] = h, m

    # ── B1: native reproduction vs the committed records ─────────────────
    with open(f"runs/20260807_025739_two_strand_yin_excess_cont/"
              f"run_ysep12_t80.json") as f:
        base80 = json.load(f)['hist']
    cont_ok, diffs, n_run, n_base = SC.continuity(arms['native'], base80)
    flip_t, merge_t = flip_and_merge_times(arms['native'])
    d40 = at_t(arms['native'], 40.0)['d']
    b1 = {
        'continuity': {'verdict': 'passed' if cont_ok else 'mismatch',
                       'max_record_diff': max(diffs.values()),
                       'diffs': diffs, 'n_run_records': n_run,
                       'n_baseline_records': n_base},
        'pi_flip_t': flip_t, 'pi_flip_ref': T_FLIP_REF,
        'pi_flip_ok': flip_t is not None
        and abs(flip_t - T_FLIP_REF) <= T_FLIP_TOL,
        'merge_t': merge_t, 'merge_ref': T_MERGE_REF,
        'merge_ok': merge_t is not None
        and abs(merge_t - T_MERGE_REF) <= T_MERGE_TOL,
        'd40': d40, 'd40_ref': D40_REF,
        'd40_ok': abs(d40 - D40_REF) <= D40_TOL,
        'merged_at_end': bool(arms['native'][-1]['merged']),
    }

    # ── B2: primary swap arm breathing verdict ───────────────────────────
    b2 = None
    if 'swap_p0' in arms_req:
        ridge_stats = pi_ridge_stats(arms['swap_p0'])
        n_d, extrema = d_cycles(arms['swap_p0'], 2.0 * p0)
        lc, poincare = limit_cycle_diag(arms['swap_p0'],
                                        meta['swap_p0']['swap_times'])
        pl = phase_lag(arms['swap_p0'], p0)
        s_flip, s_merge = flip_and_merge_times(arms['swap_p0'])
        both_ridges = all(r['cycles'] >= 2 for r in ridge_stats)
        d_breathes = n_d >= 2 or (lc is not None and lc['converged'])
        b2 = {
            'p0': p0, 'p0_measured': p0_measured, 'p0_fallback': LAM_INV,
            'pi_ridge_stats': ridge_stats,
            'pi_cycles_both_ridges': bool(both_ridges),
            'pi_amp_min': PI_AMP_MIN,
            'd_cycles_full': n_d, 'd_extrema': extrema,
            'd_amp_min': D_AMP_MIN,
            'period_ref': 2.0 * p0, 'period_tol': PERIOD_TOL,
            'limit_cycle': lc,
            'poincare_swap_samples': [s.tolist() for s in poincare],
            'phase_lag': pl,
            'd_breathes': bool(d_breathes),
            'breathing': bool(both_ridges and d_breathes),
            'verdict': (
                'BREATHING: >= 2 complete Yin->Yang->Yin cycles on both '
                'ridges AND >= 2 full d cycles at 2 P0 (or a converged '
                'limit cycle)' if (both_ridges and d_breathes) else
                'NULL: per-ridge Pi alternation is forced by the exchange '
                '(driven artifact); the separation mode does not complete '
                'two cycles (no breathing claim from a sign flip alone)'),
            'flip_t': s_flip, 'merge_t': s_merge,
            'd_start': arms['swap_p0'][0]['d'],
            'd_end': arms['swap_p0'][-1]['d'],
            'd_min': min(d['d'] for d in arms['swap_p0']),
            'd_max': max(d['d'] for d in arms['swap_p0']),
        }

    # ── B2c: cadence controls (period-specificity) ───────────────────────
    b2c = {}
    for tag in ('swap_phi', 'swap_e'):
        if tag not in arms_req:
            continue
        mtag = meta[tag]
        rs = pi_ridge_stats(arms[tag])
        n_dc, ext_c = d_cycles(arms[tag], 2.0 * mtag['swap_period'])
        lcc, _ = limit_cycle_diag(arms[tag], mtag['swap_times'])
        b2c[tag] = {
            'swap_period': mtag['swap_period'],
            'n_swaps': mtag['n_swap'],
            'pi_ridge_stats': rs,
            'd_cycles_full': n_dc, 'd_extrema': ext_c,
            'd_breathes': bool(n_dc >= 2 or (lcc and lcc['converged'])),
            'limit_cycle': lcc,
            'merge_t': flip_and_merge_times(arms[tag])[1],
        }
    if b2 is not None and len(b2c) == 2:
        period_specific = (b2['breathing']
                           and not b2c['swap_phi']['d_breathes']
                           and not b2c['swap_e']['d_breathes'])
        b2c['period_specific'] = bool(period_specific)

    # ── B3: drive arm (churning-gate alternative) ────────────────────────
    b3 = None
    if 'drive' in arms_req:
        n_d_d, ext_d = d_cycles(arms['drive'], 2.0 * p0)
        d_flip, d_merge = flip_and_merge_times(arms['drive'])
        df0 = arms['drive'][0]
        dfl = arms['drive'][-1]
        b3 = {
            'drive_period': p0, 'drive_amp': DRIVE_AMP, 'channel': 'fire/ey',
            'd_cycles_full': n_d_d, 'd_extrema': ext_d,
            'd_breathes': bool(n_d_d >= 2),
            'merge_t': d_merge, 'native_merge_t': merge_t,
            'coalescence_shift': (d_merge - merge_t) if d_merge else None,
            'flip_t': d_flip, 'native_flip_t': flip_t,
            'd_end': dfl['d'],
            'eps_rel': dfl['strands'][0]['A']
            / max(df0['strands'][0]['A'], 1e-12),
            'q_gap_end': dfl['q_glob'] - dfl['q_mid'],
            'q_mid_0': df0['q_mid'], 'q_mid_end': dfl['q_mid'],
            'phase_frac_end': dfl['strands'][0]['phase_frac'],
            'dominant_end': CHANNELS[dfl['strands'][0]['dominant']],
        }

    # ── B4: telemetry ────────────────────────────────────────────────────
    b4 = {tag: {k: m[k] for k in ('mass_drift', 'floor_touch', 'a_end',
                                  'H_end', 'nan_abort', 'n_swap',
                                  'swap_period', 'scratch_note')}
          for tag, m in meta.items() if 'mass_drift' in m}

    results = {
        'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT,
                 't_end': {tag: arms[tag][-1]['t'] for tag in arms},
                 'gate_model': 'five (solver)',
                 'E_RIDGE': S.P.E_RIDGE, 'BETA': S.P.BETA, 'SIG': S.P.SIG,
                 'SEP': SEP,
                 'init': ('Yin-excess swapped pair, sep = 12 (suite sec '
                          '3.5); canonical ExpandingTwoFluid3DGPU untouched, '
                          'fresh solver per arm'),
                 'p0': {'measured': p0_measured,
                        'fallback': None if p0_measured is not None
                        else LAM_INV,
                        'used': p0,
                        'accept_window': list(P0_ACCEPT),
                        'series': 'native pi_mid'},
                 'swap_family': {'operation': 'Psi_Y <-> Psi_I exchange '
                                              '(Pi -> -Pi), FORCED SCRATCH '
                                              'PHYSICS',
                                 'primary': {'cadence': p0, 't_end':
                                             5.0 * p0},
                                 'controls': {'phi': {'cadence': p0 * S.C.PHI,
                                                      't_end': t_phi},
                                              'e': {'cadence': p0 * np.e,
                                                    't_end': t_e}}},
                 'drive': {'amp': DRIVE_AMP, 'period': p0, 't_end':
                           DRIVE_T_END,
                           'convention': 'churning-gate Fire/ey site drive'},
                 'baselines': {'suite': 'runs/20260807_014428_'
                                        'two_strand_yin_excess',
                               'continuation': 'runs/20260807_025739_'
                                               'two_strand_yin_excess_cont'},
                 'arms': {tag: m for tag, m in meta.items()}},
        'arms': {tag: {'d_start': h[0]['d'], 'd_end': h[-1]['d'],
                       'd_min': min(d['d'] for d in h),
                       'd_max': max(d['d'] for d in h),
                       'pi_strand_0': h[0]['pi_strand'],
                       'pi_strand_end': h[-1]['pi_strand'],
                       'q_mid_0': h[0]['q_mid'],
                       'q_mid_end': h[-1]['q_mid'],
                       'eps_mid_0': h[0]['eps_mid'],
                       'eps_mid_end': h[-1]['eps_mid'],
                       'delta_theta_0': h[0]['delta_theta'],
                       'delta_theta_end': h[-1]['delta_theta'],
                       'theta_xy_0': h[0]['theta_xy'],
                       'theta_xy_end': h[-1]['theta_xy'],
                       'flip_t': flip_and_merge_times(h)[0],
                       'merge_t': flip_and_merge_times(h)[1]}
                 for tag, h in arms.items()},
        'verdicts': {'B1_native_reproduction': b1,
                     'B2_swap_p0_breathing': b2,
                     'B2c_cadence_controls': b2c,
                     'B3_drive_alternative': b3,
                     'B4_telemetry': b4},
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== TWO-STRAND BREATHING VERDICTS ===")
    print(f"P0 = {p0:.3f} "
          f"({'measured' if p0_measured is not None else 'fallback 1/lambda'})")
    print(f"B1 native: continuity "
          f"{'PASSED' if b1['continuity']['verdict'] == 'passed' else 'MISMATCH'}"
          f" (max diff {b1['continuity']['max_record_diff']:.2e}) | "
          f"pi flip {flip_t} (ref {T_FLIP_REF}) | merge {merge_t} "
          f"(ref {T_MERGE_REF}) | d40 {d40:.4f} (ref {D40_REF})")
    if b2 is not None:
        print(f"B2 swap@P0: ridges "
              f"{[(r['ridge'], r['cycles'], round(r['yin_frac'], 3))
                 for r in ridge_stats]} | d cycles {n_d} | limit cycle "
              f"{'converged' if lc and lc['converged'] else 'not converged'} "
              f"| phase lag {pl['lag_t']:.2f} ({pl['lag_frac']:+.2f} x P0)")
        print(f"   -> {b2['verdict']}")
    for tag in ('swap_phi', 'swap_e'):
        if tag in b2c:
            print(f"B2c {tag}: cadence {meta[tag]['swap_period']:.2f} | "
                  f"ridges {[r['cycles'] for r in b2c[tag]['pi_ridge_stats']]} "
                  f"| d cycles {b2c[tag]['d_cycles_full']} "
                  f"| d_breathes {b2c[tag]['d_breathes']}")
    if 'period_specific' in b2c:
        print(f"B2c period-specific: {b2c['period_specific']}")
    if b3 is not None:
        print(f"B3 drive: P0 = {p0:.3f} | d cycles {b3['d_cycles_full']} | "
              f"merge {b3['merge_t']} (native {merge_t}) | "
              f"d_end {b3['d_end']:.2f} "
              f"| q_mid {b3['q_mid_0']:.3f}->{b3['q_mid_end']:.3f}")
    for tag, m in meta.items():
        if 'mass_drift' not in m:
            continue
        print(f"   {tag:8s}: floor {m['floor_touch']}, mass drift "
              f"{m['mass_drift']['tot']:.2e}, nan {m['nan_abort']}, "
              f"a_end {m['a_end']:.4f}, H_end {m['H_end']:.4f}, "
              f"swaps {m['n_swap']}")
    print(f"\nResults: {rdir}/results.json")
    if torch.cuda.is_available():
        torch.cuda.synchronize()


if __name__ == "__main__":
    main()
