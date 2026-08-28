#!/usr/bin/env python3
"""Misgendering-release test: does affirmation accelerate recovery?

Follow-up to `two-fluid/run_misgendering_drive.py` (§8 of
`consciousness/gender-as-qi-configuration.md`): the cross-channel (Wood)
drive pumps a held Fire site to ~2x its imbalance while the in-channel
(Fire) drive drains a standing site. The open question is the RELEASE:
after a Wood drive has pumped the site, does switching to a Fire drive
(affirmation) recover faster or more completely than simply stopping the
drive (removal)?

Established endpoints:
  - stopping the trigger releases a driven lock on the conversion
    timescale (run_trauma_driver.py)
  - an active phi*P0 drive drains a displaced site (run_trauma_drive_
    compare.py)
  - Wood pumps / Fire drains at eps-parity from a standing site
    (run_misgendering_drive.py, 2026-08-02)

The new binary question: from an actively PUMPED state, is active
in-channel support better than silence?

Runs (lambda=0.05, t=4, N=48; minimal protocol):
  ref         no drive, t=4 (natural decay floor)
  removal     Wood drive t in [0,2), silence t in [2,4)
  affirmation Wood drive t in [0,2), Fire drive t in [2,4)

Phase 1 (Wood, eps-parity amp 0.15/phi, period P0) reproduces the §8
misgendering arm from the same seed—a built-in reproducibility check.
Phase 2 arms share the identical pumped state at t=2 and differ only in
what follows: silence or an in-channel drive at the repo-standard amp.

Verdict: affirmation accelerates if eps_aff(t=4) < eps_rem(t=4) - 0.05
(or the decay half-life is shorter); neutral if within 0.05; pumps if
eps_aff > eps_rem + 0.05.

Usage: python two-fluid/run_misgendering_release.py [p0]
       optional p0 overrides the measured natural period (e.g. 0.041 for
       strict §8 comparability; the measured value is window-dependent:
       0.081 at t=4 vs 0.041 at t=2 with the same physics)
Output: runs/<id>_misgendering_release/results.json + figure
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
T.STEPS = 4000          # t = 4: pump phase [0,2), release phase [2,4)
T.AMP = 0.8

DRIVE_AMP = 0.15        # repo-standard drive amplitude (on ey)
WOOD_AMP = DRIVE_AMP / T.PHI  # eps-parity for the Yin component
SWITCH_STEP = 2000      # t = 2: end of the misgendering phase
FIRE = 1                # phase_frac index of the identity channel (72 deg)


def run_case(solver, phase1_channel=None, phase2_channel=None,
             drive_period=None, tag='run', outdir=None):
    """Standing init (identity = Fire); optional Wood drive to t=2, then
    either silence (removal) or a Fire drive (affirmation) to t=4.

    Phase 1 is identical across driven arms (same seed, same eps-parity
    Wood schedule), so phase-2 arms start from the same pumped state.
    """
    print(f"\n=== run: {tag} (phase1={phase1_channel}, phase2={phase2_channel}) ===")
    ey_hat, ei_hat, u_hat = T.init_fields(solver, 'standing', seed=42)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    t0 = time.time()
    hist = []

    for step in range(T.STEPS):
        ey = torch.fft.ifftn(ey_hat).real
        if step < SWITCH_STEP and phase1_channel == 'wood':
            t_now = step * T.DT
            drive = WOOD_AMP * np.sin(2.0 * np.pi * t_now / drive_period)
            ei = torch.fft.ifftn(ei_hat).real
            ei = ei + drive * mask
            ei_hat = torch.fft.fftn(ei)
        elif phase2_channel == 'fire':
            t_now = (step - SWITCH_STEP) * T.DT
            drive = DRIVE_AMP * np.sin(2.0 * np.pi * t_now / drive_period)
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
            d.update({'step': step, 't': step * T.DT})
            hist.append(d)

    print(f"  [{tag}] {T.STEPS} steps in {time.time() - t0:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'hist': hist}, f, indent=1)
    return hist


def at(hist, t_target):
    return min(hist, key=lambda d: abs(d['t'] - t_target))


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t=4.0  "
          f"wood_amp={WOOD_AMP} fire_amp={DRIVE_AMP}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    if len(sys.argv) > 1:
        p0 = float(sys.argv[1])
        p0_source = 'argv'
    else:
        p0 = None
        p0_source = 'measured'
    rid += f"_p{int((p0 if p0 else 0) * 1000)}"
    rdir = f"runs/{rid}_misgendering_release"
    os.makedirs(rdir, exist_ok=True)

    solver = T.build_solver(device)

    h_ref = run_case(solver, tag='ref', outdir=rdir)
    if p0 is None:
        p0 = T.dominant_period([d['eps_site'] for d in h_ref], T.DT)
        if p0 is None:
            print("No dominant period in the ref series; aborting.")
            return
    print(f"\nNatural period P0 = {p0:.4f} ({p0_source})")

    h_rem = run_case(solver, phase1_channel='wood', phase2_channel=None,
                     drive_period=p0, tag='removal', outdir=rdir)
    h_aff = run_case(solver, phase1_channel='wood', phase2_channel='fire',
                     drive_period=p0, tag='affirmation', outdir=rdir)

    e0 = h_ref[0]['eps_site']
    eps = {k: h[-1]['eps_site'] / e0 for k, h in
           [('ref', h_ref), ('removal', h_rem), ('affirmation', h_aff)]}
    eps_t2 = {k: at(h, 2.0)['eps_site'] / e0 for k, h in
              [('removal', h_rem), ('affirmation', h_aff)]}
    qgap = {k: h[-1]['q_glob'] - h[-1]['q_site'] for k, h in
            [('ref', h_ref), ('removal', h_rem), ('affirmation', h_aff)]}
    pump_state = at(h_rem, 2.0)['eps_site'] / e0

    results = {
        'meta': {'P0': p0, 'drive_period': p0, 'p0_source': p0_source,
                 'fire_amp': DRIVE_AMP,
                 'wood_amp': WOOD_AMP, 'switch_t': 2.0,
                 'identity_channel': 'Fire (72 deg)',
                 'misgendering_channel': 'Wood (0 deg)',
                 'lam': T.LAM, 'N': T.N, 't_end': T.STEPS * T.DT},
        'eps_rel_t4': eps, 'eps_rel_t2': eps_t2,
        'q_gap_t4': qgap, 'pump_state_t2': pump_state,
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== MISGENDERING-RELEASE RESULTS ===")
    print(f"Pump state at t=2 (both arms, same seed): "
          f"eps_rel={pump_state:.3f}  (§8 misgendering arm: 2.075)")
    for k in ('ref', 'removal', 'affirmation'):
        print(f"{k:11s}: eps_rel(t=4)={eps[k]:.3f}  q_gap(t=4)={qgap[k]:+.3f}")
    print(f"  phase-1 reproducibility vs §8 (2.075): "
          f"{'OK' if abs(pump_state - 2.075) < 0.1 else 'MISMATCH'}")

    accelerates = eps['affirmation'] < eps['removal'] - 0.05
    neutral = abs(eps['affirmation'] - eps['removal']) <= 0.05
    pumps = eps['affirmation'] > eps['removal'] + 0.05

    print("\n=== VERDICT ===")
    if accelerates:
        print("*** AFFIRMATION ACCELERATES: the in-channel drive after a "
              "pump recovers the site faster/more than silence at the "
              "same state. Active support beats removal. ***")
    elif neutral:
        print("NEUTRAL: affirmation and removal recover at the same rate "
              "from the pumped state—the drain is a standing-state "
              "property, not an active-recovery mechanism.")
    elif pumps:
        print("AFFIRMATION PUMPS: the in-channel drive on the pumped state "
              "drives it further off—the drain does not transfer from the "
              "standing to the pumped state.")
    else:
        print("INDETERMINATE: no criterion met.")

    # ── Figure ─────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 2, figsize=(13, 9))
        runs = [('ref', h_ref, 'gray'), ('removal', h_rem, 'C3'),
                ('affirmation', h_aff, 'C2')]
        for name, h, c in runs:
            t = [d['t'] for d in h]
            axes[0, 0].plot(t, [d['eps_site'] for d in h], c, label=name)
            axes[0, 1].plot(t, [d['q_site'] for d in h], c, label=name)
            axes[1, 0].plot(t, [d['phase_frac'][FIRE] for d in h], c,
                            label=name)
            axes[1, 1].plot(t, [d['sigma_r_site'] for d in h], c, label=name)
        for ax in axes.flat:
            ax.axvline(2.0, color='w', ls='--', alpha=0.4, lw=0.8)
        axes[0, 0].set_title('site |epsilon| (pump to t=2, release after)')
        axes[0, 1].set_title('site q (5-channel coherence)')
        axes[1, 0].set_title('site Fire-channel fraction (identity)')
        axes[1, 1].set_title('site sigma_r (dispersion of r = EY/EI)')
        for ax in axes.flat:
            ax.set_xlabel('t')
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
        fig.suptitle(f'Misgendering release (Wood to t=2, then silence vs '
                     f'Fire; P0={p0:.3f})')
        fig.tight_layout()
        fig.savefig(f"{rdir}/misgendering_release.png", dpi=130)
        plt.close()
        print(f"\nFigure: {rdir}/misgendering_release.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
