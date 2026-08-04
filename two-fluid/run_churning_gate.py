#!/usr/bin/env python3
"""Churning-gate drive test: does a matched recurring drive close the gate?

Test design: `consciousness/neurodivergence-as-gate-configuration.md` §8.

Binary question: from a low-q mixed-channel init (the churning state: no
dominant pentagon vertex, gate open), does a recurring in-channel drive
close the gate—q rising, a channel stabilizing, epsilon-variance
falling—while a recurring cross-channel drive at equal epsilon-perturbation
leaves it churning or pumps it?

The churning init is the open-gate counterpart of the standing init used in
the misgendering test (`two-fluid/run_misgendering_drive.py`): a localized
site (periodic ball, R=6) held at low q with mixed channel weights on a
quiet phi-equilibrium background. Per-cell ratios r = EY/EI are drawn from
three populations (seed 42): 50% in the churn band r ~ [0.45, 0.95]
(eps_norm ~ 0.16-0.32, the q-minimum: Wood suppressed, Fire/Earth open),
20% deep r ~ [0.15, 0.40] (eps_norm ~ 0.42-0.68: Metal/Water gates open),
30% near equilibrium r ~ [1.45, 1.90] (Wood basin). Under the 1e-3
positivity clamp only Wood (0 deg) and Fire (72 deg) are representable in
the field angle (`two-fluid/run_trauma_phase_channels.py`), so the phase
histogram is a Wood/Fire split with no vertex above ~0.7; the GATE weights
ch_open spread across all five channels.

The site's measured channel phase at t=0 (phase-histogram argmax) and its
mean epsilon sign define the arm directions, per the misgendering mapping:
a negative-mean-epsilon site sits in the Fire basin, so the in-channel
(settling) drive oscillates the Yang component (ey injects +a of epsilon,
opposing the deficit), and the cross-channel drive one pentagon step away
oscillates the Yin component (ei injects -phi*a), phi-normalized to
epsilon-parity (wood_amp = DRIVE_AMP/phi).

Runs (lambda=0.05, t=4, N=48; minimal protocol, no sweeps):
  ref    churning init, no drive; P0 and the channel phase measured
         in-process from this run
  in     churning + in-channel oscillation at P0, amp 0.15
         (matched drive: the field's own channel at its natural period)
  cross  churning + cross-channel oscillation at P0, amp 0.15/phi
         (epsilon-parity: same peak epsilon-injection, one pentagon step)
  period churning + in-channel oscillation at period e*P0, amp 0.15
         (mismatched-period control: same channel, incommensurate period)

All arms receive the same explicit P0 (measured from the t=4 ref window),
per the dominant_period window caveat of `consciousness/gender-as-qi-
configuration.md` §8.1.

Verdict quantities at the site (ball around the box center):
  eps_site      mean |epsilon| over the site (perturbation amplitude)
  q_site/q_glob 5-channel Qi coherence (site vs global); q_gap = glob-site
  ch_open[5]    per-channel gate openness at the site
  phase_frac[5] per-channel phase histogram at the site
  ey/ei_min_site clamp diagnostics (1e-3 positivity floor)
  eps_var_t     time-variance of eps_site over the window (and back 40%)
  eps_var_x     spatial variance of epsilon over the site at t_end

Usage: python two-fluid/run_churning_gate.py
Output: runs/<id>_churning_gate/results.json + figure
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

T.LAM = 0.05
T.DT = 0.001
T.REPORT = 50
T.STEPS = 4000          # t = 4: the doc's upper bound, drive gets ~50+ cycles

DRIVE_AMP = 0.15        # above the phase-blindness floor (>= 0.05),
                        # below the known drain amplitude (0.3)
WOOD_AMP = DRIVE_AMP / T.PHI  # eps-parity: delta-e from +-a on ei is
                               # +-phi*a, so the cross-channel arm uses a/phi
CHANNELS = ['Wood', 'Fire', 'Earth', 'Metal', 'Water']

# Churning-init populations (fractions of the site ball; seed 42)
P_MID, P_DEEP = 0.50, 0.20       # churn-band and deep-band fractions
R_MID = (0.45, 0.95)             # eps_norm ~ 0.16-0.32 (q-minimum band)
R_DEEP = (0.15, 0.40)            # eps_norm ~ 0.42-0.68 (opens Metal/Water)
R_EQ = (1.45, 1.90)              # Wood basin (relaxed band)
EI_W = 0.15                      # per-cell ei spread (+/-)


def churning_init(solver, seed=42):
    """Low-q mixed-channel site on a quiet phi-equilibrium background."""
    N_ = solver.N
    dev = solver.device
    mask = T.site_mask(N_, T.R_SITE, dev)
    g = torch.Generator(device=dev)
    g.manual_seed(seed)

    u1 = torch.rand((N_,) * 3, generator=g, device=dev, dtype=torch.float64)
    u2 = torch.rand((N_,) * 3, generator=g, device=dev, dtype=torch.float64)
    u3 = torch.rand((N_,) * 3, generator=g, device=dev, dtype=torch.float64)
    kind = torch.where(u1 < P_MID, torch.tensor(0, device=dev),
                       torch.where(u1 < P_MID + P_DEEP,
                                   torch.tensor(1, device=dev),
                                   torch.tensor(2, device=dev)))
    r = torch.where(kind == 0, R_MID[0] + (R_MID[1] - R_MID[0]) * u2,
                    torch.where(kind == 1,
                                R_DEEP[0] + (R_DEEP[1] - R_DEEP[0]) * u2,
                                R_EQ[0] + (R_EQ[1] - R_EQ[0]) * u2))
    ei = 1.0 + EI_W * (u3 - 0.5) * 2.0

    ey = torch.ones((N_,) * 3, dtype=torch.float64, device=dev)
    ei_f = torch.full((N_,) * 3, T.PHI_INV, dtype=torch.float64, device=dev)
    ey = ey + mask * (r * ei - 1.0)
    ei_f = ei_f + mask * (ei - T.PHI_INV)
    ey = torch.clamp(ey, min=1e-3)
    ei_f = torch.clamp(ei_f, min=1e-3)
    u_hat = torch.zeros(3, N_, N_, N_, dtype=torch.complex128, device=dev)
    return torch.fft.fftn(ey), torch.fft.fftn(ei_f), u_hat


def site_phase_basin(hist_first):
    """Dominant channel of the site phase histogram at t=0 (in-process)."""
    return CHANNELS[int(np.argmax(hist_first['phase_frac']))]


def arm_channels(basin, eps_mean):
    """Map the measured basin to (in_channel, cross_channel) components.

    Misgendering-test mapping: a negative-mean-epsilon site sits in the
    Fire basin; the settling (in-channel) drive oscillates ey (injects +a
    of epsilon), the cross-channel drive one pentagon step away oscillates
    ei (injects -phi*a). Mirror for a Wood-basin site.
    """
    if basin == 'Fire' and eps_mean < 0.0:
        return 'fire', 'wood'      # in = ey oscillation, cross = ei
    if basin == 'Wood' and eps_mean > 0.0:
        return 'wood', 'fire'      # in = ei oscillation, cross = ey
    # Unrepresentable basin or sign mismatch: fall back to the epsilon sign
    return ('fire', 'wood') if eps_mean < 0.0 else ('wood', 'fire')


def run_case(solver, tag, outdir=None, drive_channel=None,
             drive_period=None, drive_amp=None):
    """Churning init; optional periodic drive at the site."""
    amp = DRIVE_AMP if drive_amp is None else drive_amp
    print(f"\n=== run: {tag} (channel={drive_channel}, "
          f"period={drive_period}, amp={amp}) ===")
    ey_hat, ei_hat, u_hat = churning_init(solver, seed=42)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    t0 = time.time()
    hist = []

    for step in range(T.STEPS):
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

        if step % T.REPORT == 0 or step == T.STEPS - 1:
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

    print(f"  [{tag}] {T.STEPS} steps in {time.time() - t0:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'hist': hist}, f, indent=1)
    return hist


def summarize(name, hist):
    """Verdict quantities at t_end, plus peak over the back 40%."""
    first, last = hist[0], hist[-1]
    eps0 = max(first['eps_site'], 1e-12)
    eps_rel = last['eps_site'] / eps0
    back = hist[int(0.6 * len(hist)):]
    peak_rel = max(d['eps_site'] for d in back) / eps0
    eps_series = np.array([d['eps_site'] for d in hist])
    eps_var_t_full = float(eps_series.var())
    eps_var_t_back = float(eps_series[int(0.6 * len(eps_series)):].var())
    return {
        'eps_rel': eps_rel,
        'peak_eps_rel': peak_rel,
        'q_gap': last['q_glob'] - last['q_site'],
        'q_gap_init': first['q_glob'] - first['q_site'],
        'q_site': last['q_site'],
        'phase_frac': last['phase_frac'],
        'phase_frac_init': first['phase_frac'],
        'phase_max': max(last['phase_frac']),
        'phase_max_init': max(first['phase_frac']),
        'ch_open': last['ch_open'],
        'eps_var_t_full': eps_var_t_full,
        'eps_var_t_back': eps_var_t_back,
        'eps_var_x': last['eps_var_x'],
        'ey_min_site': last['ey_min_site'],
        'ei_min_site': last['ei_min_site'],
        'sigma_r_site': last['sigma_r_site'],
    }


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t=4.0  "
          f"drive_amp={DRIVE_AMP}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_churning_gate"
    os.makedirs(rdir, exist_ok=True)

    solver = T.build_solver(device)

    # ── Reference: measure P0 and the site's channel phase in-process ────
    h_ref = run_case(solver, tag='ref', outdir=rdir)
    p0 = T.dominant_period([d['eps_site'] for d in h_ref], T.DT)
    if p0 is None:
        print("No dominant period in the ref series; aborting.")
        return
    basin = site_phase_basin(h_ref[0])
    # mean epsilon sign over the site at t=0 (from the init construction)
    ey_hat, ei_hat, u_hat = churning_init(solver, seed=42)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    bm = mask > 0.5
    eps_mean_init = float(((ey - T.PHI * ei) * mask).sum() / bm.sum())
    in_ch, cross_ch = arm_channels(basin, eps_mean_init)
    print(f"\nMeasured natural period P0 = {p0:.4f} (drive period = P0)")
    print(f"Site phase basin at t=0: {basin}  "
          f"mean eps = {eps_mean_init:+.3f}")
    print(f"  -> in-channel drive on '{in_ch}' (settling), "
          f"cross-channel on '{cross_ch}' (eps-parity)")

    h_in = run_case(solver, tag='in', drive_channel=in_ch,
                    drive_period=p0, outdir=rdir)
    h_cross = run_case(solver, tag='cross', drive_channel=cross_ch,
                       drive_period=p0, drive_amp=WOOD_AMP, outdir=rdir)
    h_period = run_case(solver, tag='period', drive_channel=in_ch,
                        drive_period=np.e * p0, outdir=rdir)

    s_ref = summarize('ref', h_ref)
    s_in = summarize('in', h_in)
    s_cross = summarize('cross', h_cross)
    s_period = summarize('period', h_period)

    results = {
        'meta': {'P0': p0, 'drive_period': p0, 'period_control_period':
                 np.e * p0, 'drive_amp': DRIVE_AMP, 'wood_amp': WOOD_AMP,
                 'basin_t0': basin, 'eps_mean_t0': eps_mean_init,
                 'in_channel': in_ch, 'cross_channel': cross_ch,
                 'lam': T.LAM, 'N': T.N, 't_end': T.STEPS * T.DT},
        'ref': s_ref, 'in_channel': s_in, 'cross_channel': s_cross,
        'period_control': s_period,
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== CHURNING-GATE RESULTS (t=4) ===")
    for name, s in [('ref          ', s_ref), ('in-channel  ', s_in),
                    ('cross-channel', s_cross), ('period e*P0 ', s_period)]:
        print(f"{name}: eps_rel={s['eps_rel']:.3f} "
              f"(peak {s['peak_eps_rel']:.3f}) q_gap="
              f"{s['q_gap_init']:+.3f}->{s['q_gap']:+.3f} "
              f"phase_max {s['phase_max_init']:.2f}->{s['phase_max']:.2f} "
              f"[{','.join(f'{v:.2f}' for v in s['phase_frac'])}] "
              f"ey_min={s['ey_min_site']:.4f} "
              f"eps_var_t={s['eps_var_t_back']:.5f}")

    # ── Verdict (binary: does the matched drive close the churning gate?) ─
    gap_init = s_ref['q_gap_init']
    in_closes = (s_in['q_gap'] < gap_init - 0.02 and
                 s_in['eps_rel'] < s_ref['eps_rel'] - 0.05)
    cross_holds = s_cross['eps_rel'] > s_ref['eps_rel'] + 0.05 or \
        s_cross['q_gap'] > s_ref['q_gap'] + 0.01
    ref_churns = (s_ref['q_gap'] > gap_init - 0.02 and
                  s_ref['phase_max'] < s_ref['phase_max_init'] + 0.05)
    channel_specific = (abs(s_in['eps_rel'] - s_cross['eps_rel']) > 0.05 or
                        abs(s_in['q_gap'] - s_cross['q_gap']) > 0.02)
    period_specific = (abs(s_in['eps_rel'] - s_period['eps_rel']) > 0.05 or
                       abs(s_in['q_gap'] - s_period['q_gap']) > 0.02)

    print("\n=== VERDICT ===")
    print(f"In-channel drive closes the gate (q-gap down, eps below ref): "
          f"{in_closes}")
    print(f"Cross-channel drive holds or pumps above ref: {cross_holds}")
    print(f"Undriven reference churns (gap open, no vertex stabilizing): "
          f"{ref_churns}")
    print(f"Channel-specific (arms differ): {channel_specific}")
    print(f"Period-specific (e*P0 differs from P0 at same channel): "
          f"{period_specific}")
    if in_closes and cross_holds and channel_specific:
        print("*** CHANNEL-SPECIFIC CLOSURE: the recurring drive at the "
              "site's own channel closes the churning gate—q rises, the "
              "gap narrows, eps drains below the undriven floor—while the "
              "same-amplitude drive one pentagon step away at epsilon-"
              "parity leaves it churning or pumps it. The matched-drive "
              "settling claim of §4.2 is mechanism-tested for the "
              "open-gate configuration. ***")
    elif in_closes and not cross_holds:
        print("PARTIAL: the in-channel drive closes the gate, but the "
              "cross-channel arm does not hold/pump above the reference—"
              "the churn itself dominates at this amplitude.")
    elif not in_closes and cross_holds:
        print("NULL (in-channel): the matched drive does NOT close the "
              "churning gate at this amplitude/period—the open-gate "
              "settling claim is bounded at the held-configuration "
              "regime.")
    else:
        print("NULL: no channel contrast at this amplitude—both arms "
              "track the undriven churn.")

    # ── Figure ─────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 2, figsize=(13, 9))
        runs = [('ref', h_ref, 'gray'), ('in', h_in, 'C2'),
                ('cross', h_cross, 'C3'), ('period', h_period, 'C1')]
        for name, h, c in runs:
            t = [d['t'] for d in h]
            axes[0, 0].plot(t, [d['eps_site'] for d in h], c, label=name)
            axes[0, 1].plot(t, [d['q_site'] for d in h], c, label=name)
            axes[1, 0].plot(t, [d['phase_frac'][1] for d in h], c,
                            label=name)
            axes[1, 1].plot(t, [d['sigma_r_site'] for d in h], c,
                            label=name)
        axes[0, 0].set_title('site mean |epsilon| (churn amplitude)')
        axes[0, 1].set_title('site q (5-channel coherence)')
        axes[1, 0].set_title('site Fire-channel fraction (churn basin)')
        axes[1, 1].set_title('site sigma_r (dispersion of r = EY/EI)')
        for ax in axes.flat:
            ax.set_xlabel('t')
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
        fig.suptitle(f'Churning-gate drive (amp {DRIVE_AMP}, period P0 '
                     f'{p0:.3f}, basin {basin}, e*P0 control)')
        fig.tight_layout()
        fig.savefig(f"{rdir}/churning_gate.png", dpi=130)
        plt.close()
        print(f"\nFigure: {rdir}/churning_gate.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
