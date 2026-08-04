#!/usr/bin/env python3
"""Churning-gate adaptive drive test: does a NON-fixed-period drive settle?

Follow-up to `consciousness/neurodivergence-as-gate-configuration.md` §9
(the 2026-08-04 churning-gate test) and the amplitude scan
(`two-fluid/run_churning_gate_amp_scan.py`): from the low-q mixed-channel
init, a fixed-period in-channel drive pumped the churning gate at every
amplitude probed, and the undriven reference churned without stabilizing
a vertex. The remaining question: does the gate settle under a drive that
is NOT fixed-period? Three arms beyond the undriven reference:

  feedback   q-modulated feedback drive (the framework-native arm: the
             self-plucking loop IS the field responding to its own
             state). Drive amplitude ∝ (1 - q_site(t)) at the site's own
             channel and P0: drive hard while churning, ease off as q
             rises. Scale: amp(t) = 0.15 * (1 - q_site(t)) / (1 - q0),
             clamped to [0, 0.15], so amp = 0.15 when the gate is fully
             open at t=0 and falls as q rises. q_site is measured every
             step with the same channel_openness path that T.measure
             uses (instantaneous q over the site mask, the gate's own
             timescale; no extra smoothing).
  noise      aperiodic counterfactual: white noise on the in-channel
             component, std = 0.15/sqrt(2) (RMS-matched to the 0.15
             sine), fixed seed. Organized perturbation with phase-
             matching factor ≈ 0 per the framework taxonomy: it should
             not phase-match anything—does it churn, settle, or pump?
  alternat   de-resonant counterfactual: period alternating between P0
             and phi*P0 each full cycle at amp 0.15, in-channel—never
             locks a rational ratio.

Protocol (lambda=0.05, t=4, N=48; same churning init, seed 42; same
in-process P0 from the t=4 ref window). Verdict quantities at the site:
  eps_rel        site mean |epsilon| at t_end / init
  q_gap          q_glob - q_site; narrowing = closing the open gate
  q_site         the feedback arm's whole point is q rising
  phase_max      dominant phase-histogram fraction (vertex stabilizing)
  ey/ei_min_site clamp diagnostics (1e-3 positivity floor), min over run

Settling (all three): eps_rel <= ref_eps_rel - 0.05 AND q-gap narrowed
by >= 0.02 vs ref AND phase_max rose >= 0.2 vs ref. Pump: eps_rel >= 1.3
with the q-gap not narrowing.

Usage: python two-fluid/run_churning_gate_adaptive.py
Output: runs/<id>_churning_adaptive/results.json + figure
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
import run_trauma_wake_lock as T
import run_churning_gate as G  # baseline: churning_init, run_case, summarize

T.LAM = 0.05
T.DT = 0.001
T.REPORT = 50
T.STEPS = 4000          # t = 4: the doc's upper bound

DRIVE_AMP = 0.15
NOISE_STD = DRIVE_AMP / np.sqrt(2.0)   # RMS-matched to the 0.15 sine
NOISE_SEED = 20260804
CLAMP_FLOOR = 1e-3


def q_site_now(solver, ey, ei, mask):
    """Instantaneous q over the site, via the measure path's gate."""
    _, q = T.channel_openness(ey, ei)
    return float((q * mask).sum() / mask.sum())


def run_case_drive(solver, tag, mode, p0, outdir=None):
    """Churning init + adaptive drive; returns hist with 'drive_amp'."""
    print(f"\n=== run: {tag} (mode={mode}, "
          f"p0={'-' if p0 is None else f'{p0:.4f}'}) ===")
    ey_hat, ei_hat, u_hat = G.churning_init(solver, seed=42)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    msum = mask.sum()
    t0 = time.time()
    hist = []
    rng = np.random.default_rng(NOISE_SEED)
    noise = rng.normal(0.0, NOISE_STD, T.STEPS) if mode == 'noise' else None

    # feedback arm: baseline q at t=0 sets the full-open amplitude scale
    if mode == 'feedback':
        ey0 = torch.fft.ifftn(ey_hat).real
        ei0 = torch.fft.ifftn(ei_hat).real
        q0 = q_site_now(solver, ey0, ei0, mask)
        one_minus_q0 = max(1.0 - q0, 1e-6)
        print(f"  [feedback] q_site(t=0) = {q0:.3f} -> full-open amp "
              f"{DRIVE_AMP}, floor amp 0")
    else:
        q0 = one_minus_q0 = None

    phase = 0.0          # alternating arm: continuous phase, 2*pi per cycle
    for step in range(T.STEPS):
        ey = torch.fft.ifftn(ey_hat).real
        t_now = step * T.DT

        if mode == 'ref':
            amp_t = 0.0
            drive = 0.0
        elif mode == 'feedback':
            ei = torch.fft.ifftn(ei_hat).real
            q_site = q_site_now(solver, ey, ei, mask)
            amp_t = min(DRIVE_AMP * (1.0 - q_site) / one_minus_q0,
                        DRIVE_AMP)
            drive = amp_t * np.sin(2.0 * np.pi * t_now / p0)
        elif mode == 'noise':
            amp_t = NOISE_STD
            drive = float(noise[step])   # mean-zero white, in-channel
        elif mode == 'alternat':
            amp_t = DRIVE_AMP
            cycle = int(phase / (2.0 * np.pi))   # period switches per cycle
            period_k = p0 if cycle % 2 == 0 else T.PHI * p0
            drive = amp_t * np.sin(phase)
            phase += 2.0 * np.pi * T.DT / period_k
        else:
            raise ValueError(f"unknown mode {mode}")

        if drive != 0.0:
            ey = ey + drive * mask
            ey_hat = torch.fft.fftn(ey)
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)

        if step % T.REPORT == 0 or step == T.STEPS - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            d = T.measure(solver, ey, ei, mask)
            bm = mask > 0.5
            d['ey_min_site'] = float(ey[bm].min())
            d['ei_min_site'] = float(ei[bm].min())
            d['eps_var_x'] = float((ey - T.PHI * ei)[bm].var())
            d['drive_amp'] = amp_t
            d.update({'step': step, 't': step * T.DT})
            hist.append(d)

    print(f"  [{tag}] {T.STEPS} steps in {time.time() - t0:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'mode': mode, 'hist': hist}, f, indent=1)
    return hist


def run_min_clamps(hist):
    """Minimum ey/ei over the site across the run (clamp diagnostics)."""
    ey_min = min(d['ey_min_site'] for d in hist)
    ei_min = min(d['ei_min_site'] for d in hist)
    return ey_min, ei_min


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t=4.0")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_churning_adaptive"
    os.makedirs(rdir, exist_ok=True)

    solver = T.build_solver(device)

    # ── Reference: measure P0 and the site's channel phase in-process ────
    h_ref = run_case_drive(solver, 'ref', 'ref', None, outdir=rdir)
    p0 = T.dominant_period([d['eps_site'] for d in h_ref], T.DT)
    if p0 is None:
        print("No dominant period in the ref series; aborting.")
        return
    basin = G.site_phase_basin(h_ref[0])
    ey_hat, ei_hat, u_hat = G.churning_init(solver, seed=42)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    bm = mask > 0.5
    eps_mean_init = float(((ey - T.PHI * ei) * mask).sum() / bm.sum())
    in_ch, cross_ch = G.arm_channels(basin, eps_mean_init)
    print(f"\nMeasured natural period P0 = {p0:.4f} (drive period = P0)")
    print(f"Site phase basin at t=0: {basin}  mean eps = {eps_mean_init:+.3f}")
    print(f"  -> in-channel drive on '{in_ch}', cross on '{cross_ch}'")

    h_fb = run_case_drive(solver, 'feedback', 'feedback', p0, outdir=rdir)
    h_noise = run_case_drive(solver, 'noise', 'noise', p0, outdir=rdir)
    h_alt = run_case_drive(solver, 'alternat', 'alternat', p0, outdir=rdir)

    s_ref = G.summarize('ref', h_ref)
    s_fb = G.summarize('feedback', h_fb)
    s_noise = G.summarize('noise', h_noise)
    s_alt = G.summarize('alternat', h_alt)

    results = {
        'meta': {'P0': p0, 'drive_period': p0, 'drive_amp': DRIVE_AMP,
                 'noise_std': NOISE_STD, 'noise_seed': NOISE_SEED,
                 'alternating_periods': [p0, T.PHI * p0],
                 'feedback_scale': f'{DRIVE_AMP}*(1-q_site)/(1-q0), '
                                   f'clamped at {DRIVE_AMP}, q per step '
                                   f'via channel_openness',
                 'basin_t0': basin, 'eps_mean_t0': eps_mean_init,
                 'in_channel': in_ch, 'cross_channel': cross_ch,
                 'lam': T.LAM, 'N': T.N, 't_end': T.STEPS * T.DT,
                 'settle_eps_margin': 0.05, 'settle_gap_narrow': 0.02,
                 'settle_phase_rise': 0.2, 'pump_eps_rel': 1.3},
        'ref': s_ref, 'feedback': s_fb, 'noise': s_noise,
        'alternating': s_alt,
    }
    for name, h in [('ref', h_ref), ('feedback', h_fb), ('noise', h_noise),
                    ('alternat', h_alt)]:
        results.setdefault('clamp_min_site', {})[name] = run_min_clamps(h)
        results.setdefault('q_site_series', {})[name] = \
            [d['q_site'] for d in h]
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    # ── Table ─────────────────────────────────────────────────────────────
    print("\n=== CHURNING-GATE ADAPTIVE RESULTS (t=4) ===")
    print(f"{'arm':>9s} {'eps_rel':>7s} {'peak':>6s} "
          f"{'q_gap init->end':>15s} {'q_site init->end':>17s} "
          f"{'phase_max':>16s} {'ey_min':>7s} {'ei_min':>7s}")
    rows = [('ref', s_ref, h_ref), ('feedback', s_fb, h_fb),
            ('noise', s_noise, h_noise), ('alternat', s_alt, h_alt)]
    for name, s, h in rows:
        ey_min, ei_min = run_min_clamps(h)
        q0 = h[0]['q_site']
        print(f"{name:>9s} {s['eps_rel']:7.3f} {s['peak_eps_rel']:6.3f} "
              f"{s['q_gap_init']:+6.3f}->{s['q_gap']:+6.3f} "
              f"{q0:6.3f}->{s['q_site']:6.3f} "
              f"{s['phase_max_init']:6.2f}->{s['phase_max']:6.2f} "
              f"{ey_min:7.3f} {ei_min:7.3f}")

    # ── Verdicts ──────────────────────────────────────────────────────────
    r = s_ref
    gap_narrow = lambda s: r['q_gap'] - s['q_gap'] >= 0.02
    phase_rise = lambda s: s['phase_max'] - r['phase_max'] >= 0.2
    settling = lambda s: (s['eps_rel'] <= r['eps_rel'] - 0.05 and
                          gap_narrow(s) and phase_rise(s))
    pump = lambda s: s['eps_rel'] >= 1.3 and not gap_narrow(s)

    print("\n=== VERDICT ===")
    for name, s in [('feedback', s_fb), ('noise', s_noise),
                    ('alternat', s_alt)]:
        print(f"{name}: settling={settling(s)}  pump={pump(s)}  "
              f"(eps_rel {s['eps_rel']:.3f}, q-gap "
              f"{s['q_gap_init']:+.3f}->{s['q_gap']:+.3f}, phase_max "
              f"{s['phase_max_init']:.2f}->{s['phase_max']:.2f})")

    q_series = {name: [d['q_site'] for d in h] for name, h in
                [('ref', h_ref), ('feedback', h_fb), ('noise', h_noise),
                 ('alternat', h_alt)]}
    q_fb_end = q_series['feedback'][-1]
    q_ref_end = q_series['ref'][-1]
    print(f"q_site trajectory: ref {q_series['ref'][0]:.3f}->"
          f"{q_ref_end:.3f}; feedback {q_series['feedback'][0]:.3f}->"
          f"{q_fb_end:.3f} (rise {q_fb_end - q_series['feedback'][0]:+.3f})")
    amp_series = [d['drive_amp'] for d in h_fb]
    print(f"feedback drive amplitude: start "
          f"{amp_series[0]:.3f}, end {amp_series[-1]:.3f}, "
          f"max {max(amp_series):.3f}")

    if settling(s_fb):
        print("*** FEEDBACK SETTLES: the q-modulated self-plucking drive "
              "drains eps below the undriven floor with the q-gap "
              "narrowing and a vertex stabilizing—the churning gate "
              "closes when the field drives itself in response to its "
              "own state. ***")
    elif pump(s_fb):
        print("*** FEEDBACK PUMPS: the q-modulated drive still pumps the "
              "churning gate (eps above the floor, gap not narrowing)—"
              "the fixed-period null extends to the self-plucking loop. ***")
    else:
        print("FEEDBACK NEUTRAL: tracks the undriven churn.")

    if settling(s_noise):
        print("NOISE SETTLES (unexpected).")
    elif pump(s_noise):
        print("NOISE PUMPS: aperiodic white drive pumps the open gate "
              "despite phase-matching factor ~ 0 (rectification, not "
              "phase matching).")
    else:
        print("NOISE NEUTRAL: churns like the reference—aperiodic drive "
              "neither matches nor pumps.")

    if settling(s_alt):
        print("ALTERNATING SETTLES (unexpected).")
    elif pump(s_alt):
        print("ALTERNATING PUMPS: the de-resonant P0/phi*P0 alternation "
              "still pumps the open gate.")
    else:
        print("ALTERNATING NEUTRAL: churns like the reference.")

    # ── Figure ─────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 3, figsize=(16, 8))
        colors = {'ref': 'gray', 'feedback': 'C2', 'noise': 'C1',
                  'alternat': 'C3'}
        labels = {'ref': 'ref', 'feedback': 'feedback (q-mod)',
                  'noise': 'noise (RMS=0.15)', 'alternat': 'alternat P0/phiP0'}
        for name, h in [('ref', h_ref), ('feedback', h_fb),
                        ('noise', h_noise), ('alternat', h_alt)]:
            t = [d['t'] for d in h]
            axes[0, 0].plot(t, [d['eps_site'] for d in h],
                            colors[name], label=labels[name])
            axes[0, 1].plot(t, [d['q_site'] for d in h],
                            colors[name], label=labels[name])
            axes[0, 2].plot(t, [d['phase_frac'][1] for d in h],
                            colors[name], label=labels[name])
            axes[1, 0].plot(t, [d['sigma_r_site'] for d in h],
                            colors[name], label=labels[name])
        axes[1, 1].plot([d['t'] for d in h_fb],
                        [d['drive_amp'] for d in h_fb], 'C2',
                        label='feedback amp (0.15*(1-q)/(1-q0))')
        axes[1, 2].plot([d['t'] for d in h_alt],
                        [d['drive_amp'] for d in h_alt], 'C3',
                        label='alternat amp (0.15)')
        axes[0, 0].set_title('site mean |epsilon| (churn amplitude)')
        axes[0, 1].set_title('site q (5-channel coherence)')
        axes[0, 2].set_title('site Fire-channel fraction (churn basin)')
        axes[1, 0].set_title('site sigma_r (dispersion of r = EY/EI)')
        axes[1, 1].set_title('feedback drive amplitude (q-modulated)')
        axes[1, 2].set_title('alternating-arm drive amplitude')
        for ax in axes.flat:
            ax.set_xlabel('t')
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
        fig.suptitle(f'Churning-gate adaptive drives (P0 {p0:.3f}, basin '
                     f'{basin}, amp scale {DRIVE_AMP}, noise RMS '
                     f'{NOISE_STD:.3f})')
        fig.tight_layout()
        fig.savefig(f"{rdir}/churning_adaptive.png", dpi=130)
        plt.close()
        print(f"\nFigure: {rdir}/churning_adaptive.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
