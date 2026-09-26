#!/usr/bin/env python3
"""Misgendering-drive test: is the sustaining driver channel-specific?

Gender mapping (`consciousness/gender-as-qi-configuration.md` §4): the
gender document claims chronic misgendering is a DRIVE TERM—a recurring
perturbation whose phase sits offset from the person's own configuration
(the identity phase), sustaining incongruence (q depressed, the gate
churning (1-q)) where a same-amplitude drive at the identity's own phase
would not.

Established endpoints (2026-07-31, standing init = the held configuration):
  - undriven standing decays at the conversion rate (ref here ~0.91
    retained at t=2, lambda=0.05; run_trauma_crossover.py)
  - weak chronic injection (amp 4e-5) is PHASE-BLIND: envelope phase
    irrelevant (run_trauma_driver.py)
  - the phase channel engages at amp >= 0.05 and is strongest at 0.15
    (run_trauma_crossover.py)
  - the phi*P0 drain / e*P0 pump contrast is a PERIOD effect at the
    identity's own channel (run_trauma_drive_compare.py)

The open, gender-specific question: does the ANGLE phase of the drive
relative to the site's own phase matter? The standing init is a pure Yang
deficit, which lands the site in the Fire channel (72 deg)—measured, for
this exact init, by run_trauma_phase_channels.py. Under the positivity
clamp only Wood (0 deg) and Fire (72 deg) are representable in the field
angle, so the identity-vs-misgendering binary is Fire vs Wood.

Runs (lambda=0.05, t=2, N=48; minimal protocol, no sweeps):
  ref  standing init, no drive; P0 measured in-process from this run
  A    standing + WOOD-channel oscillation at P0, amp 0.15
       (misgendering: drive angle offset from the identity phase)
  B    standing + FIRE-channel oscillation at P0, amp 0.15
       (affirmation: drive at the identity's own channel)

The two arms differ only in which field component carries the drive
(ey for Fire, ei for Wood) at identical period and duration, with the
peak EPSILON-perturbation matched: the conversion is driven by
e = EY - phi*EI, so a component amplitude a on ei injects phi*a of e
while a on ey injects a. The Wood arm is therefore normalized to
DRIVE_AMP/phi (~0.0927) so both arms inject the same peak e.

Verdict: if A holds the site displaced above the undriven decay while B
does not, the sustainer is channel-specific—misgendering has mechanical
content beyond generic drive. If A and B agree, the angle phase is not
the variable at this amplitude and misgendering reduces to generic drive
(period-level drain/pump remains, drive_compare).

Usage: python two-fluid/run_misgendering_drive.py
Output: runs/<id>_misgendering_drive/results.json + figure
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
T.STEPS = 2000          # t = 2: the crossover short-run regime
T.AMP = 0.8

DRIVE_AMP = 0.15        # above the phase-blindness floor (>= 0.05),
                        # below the known drain amplitude (0.3)
WOOD_AMP = DRIVE_AMP / T.PHI  # eps-parity: delta-e from +-a on ei is
                               # +-phi*a, so Wood uses a/phi
FIRE = 1                # phase_frac index of the identity channel (72 deg)


def run_case(solver, drive_channel=None, drive_period=None, tag='run',
             outdir=None, drive_amp=None):
    """Standing init (identity = Fire); optional P0 oscillation at the site.

    Fire arm: drive the Yang component (ey), the identity's own channel.
    Wood arm: drive the Yin component (ei), the cross-channel offset,
    normalized to eps-parity (drive_amp=WOOD_AMP). Identical schedule both
    arms; zero mean over full periods.
    """
    amp = DRIVE_AMP if drive_amp is None else drive_amp
    print(f"\n=== run: {tag} (channel={drive_channel}, amp={amp}) ===")
    ey_hat, ei_hat, u_hat = T.init_fields(solver, 'standing', seed=42)
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
            d.update({'step': step, 't': step * T.DT})
            hist.append(d)

    print(f"  [{tag}] {T.STEPS} steps in {time.time() - t0:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'hist': hist}, f, indent=1)
    return hist


def summarize(name, hist):
    """Verdict quantities at t_end; displacement = fraction off Fire."""
    first, last = hist[0], hist[-1]
    return {
        'eps_site': last['eps_site'],
        'eps_rel': last['eps_site'] / max(first['eps_site'], 1e-12),
        'q_site': last['q_site'],
        'q_gap': last['q_glob'] - last['q_site'],
        'fire_frac': last['phase_frac'][FIRE],
        'displ': 1.0 - last['phase_frac'][FIRE],
        'displ_start': 1.0 - first['phase_frac'][FIRE],
        'sigma_r': last['sigma_r_site'],
    }


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t=2.0  "
          f"drive_amp={DRIVE_AMP}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_misgendering_drive"
    os.makedirs(rdir, exist_ok=True)

    solver = T.build_solver(device)

    h_ref = run_case(solver, tag='ref', outdir=rdir)
    p0 = T.dominant_period([d['eps_site'] for d in h_ref], T.DT)
    if p0 is None:
        print("No dominant period in the ref series; aborting.")
        return
    print(f"\nMeasured natural period P0 = {p0:.4f} (drive period = P0)")

    h_a = run_case(solver, drive_channel='wood', drive_period=p0,
                   drive_amp=WOOD_AMP, tag='misgendering', outdir=rdir)
    h_b = run_case(solver, drive_channel='fire', drive_period=p0,
                   tag='affirmation', outdir=rdir)

    s_ref = summarize('ref', h_ref)
    s_a = summarize('misgendering', h_a)
    s_b = summarize('affirmation', h_b)

    results = {
        'meta': {'P0': p0, 'drive_period': p0, 'drive_amp': DRIVE_AMP,
                 'wood_amp': WOOD_AMP,
                 'identity_channel': 'Fire (72 deg)',
                 'misgendering_channel': 'Wood (0 deg)',
                 'lam': T.LAM, 'N': T.N, 't_end': T.STEPS * T.DT},
        'ref': s_ref, 'misgendering_wood': s_a, 'affirmation_fire': s_b,
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== MISGENDERING-DRIVE RESULTS (t=2) ===")
    print(f"ref         : eps_rel={s_ref['eps_rel']:.3f} "
          f"q_gap={s_ref['q_gap']:+.3f} fire={s_ref['fire_frac']:.2f} "
          f"displ {s_ref['displ_start']:.2f}->{s_ref['displ']:.2f}")
    print(f"misgendering: eps_rel={s_a['eps_rel']:.3f} "
          f"q_gap={s_a['q_gap']:+.3f} fire={s_a['fire_frac']:.2f} "
          f"displ {s_a['displ_start']:.2f}->{s_a['displ']:.2f}")
    print(f"affirmation : eps_rel={s_b['eps_rel']:.3f} "
          f"q_gap={s_b['q_gap']:+.3f} fire={s_b['fire_frac']:.2f} "
          f"displ {s_b['displ_start']:.2f}->{s_b['displ']:.2f}")

    sustained = s_a['eps_rel'] > s_ref['eps_rel'] + 0.05
    channel_specific = (abs(s_a['eps_rel'] - s_b['eps_rel']) > 0.05 or
                        abs(s_a['q_gap'] - s_b['q_gap']) > 0.02)
    in_channel_holds = s_b['eps_rel'] > s_ref['eps_rel'] + 0.05
    displaced = s_a['fire_frac'] < s_ref['fire_frac'] - 0.05

    print("\n=== VERDICT ===")
    print(f"Cross-channel drive holds the site above decay: {sustained}")
    print(f"In-channel drive holds the site above decay: {in_channel_holds}")
    print(f"Channel-specific (arms differ): {channel_specific}")
    print(f"Cross-channel drive displaces the phase off Fire: {displaced}")
    if sustained and channel_specific and not in_channel_holds:
        print("*** CHANNEL-SPECIFIC SUSTAIN: the Wood-channel drive holds "
              "the displaced site where the same-amplitude Fire-channel "
              "drive does not. Misgendering has mechanical content beyond "
              "generic drive. ***")
    elif sustained and channel_specific and in_channel_holds:
        print("CHANNEL-SPECIFIC but both hold: the arms differ (A != B) "
              "yet the in-channel drive also sustains—affirmation is "
              "not neutral at this amplitude.")
    elif sustained and not channel_specific:
        print("NON-SPECIFIC: both channels sustain equally—the angle "
              "phase is not the variable at this amplitude; misgendering "
              "reduces to generic drive (period-level drain/pump remains, "
              "run_trauma_drive_compare.py).")
    else:
        print("NO SUSTAIN: neither arm holds the site above the undriven "
              "decay at this amplitude—below the sustain threshold, or "
              "the channel contrast is absent in this regime.")

    # ── Figure ─────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 2, figsize=(13, 9))
        runs = [('ref', h_ref, 'gray'), ('misgendering', h_a, 'C3'),
                ('affirmation', h_b, 'C2')]
        for name, h, c in runs:
            t = [d['t'] for d in h]
            axes[0, 0].plot(t, [d['eps_site'] for d in h], c, label=name)
            axes[0, 1].plot(t, [d['q_site'] for d in h], c, label=name)
            axes[1, 0].plot(t, [d['phase_frac'][FIRE] for d in h], c,
                            label=name)
            axes[1, 1].plot(t, [d['sigma_r_site'] for d in h], c, label=name)
        axes[0, 0].set_title('site |epsilon| (perturbation amplitude)')
        axes[0, 1].set_title('site q (5-channel coherence)')
        axes[1, 0].set_title('site Fire-channel fraction (identity)')
        axes[1, 1].set_title('site sigma_r (dispersion of r = EY/EI)')
        for ax in axes.flat:
            ax.set_xlabel('t')
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
        fig.suptitle(f'Misgendering drive (amp {DRIVE_AMP}, period P0 '
                     f'{p0:.3f}, identity = Fire)')
        fig.tight_layout()
        fig.savefig(f"{rdir}/misgendering_drive.png", dpi=130)
        plt.close()
        print(f"\nFigure: {rdir}/misgendering_drive.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
