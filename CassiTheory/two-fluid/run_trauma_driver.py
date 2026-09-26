#!/usr/bin/env python3
"""Driver question for the trauma wake-lock: what sustains a frozen wake?

Open question 7 in `consciousness/trauma-as-frozen-gate.md`: the wake-lock
test (§10.4) showed an un-driven standing pattern decays like any other
perturbation—the frozen wake, if real, must be driven. Candidates:

  (a) reflecting cavity: already closed—the standing init
      (cos 2pi x/N · cos 2pi y/N · cos 2pi z/N) is a perfect m=1 box
      eigenmode of the periodic domain, i.e. zero radiation loss, and it
      still decayed at the conversion rate (§10.4).
  (b) ongoing re-stimulation: a weak recurring Yang-deficit trigger at the
      site ("perpetual stimulus"). Tested here.
  (c) the phase structure of the re-stimulation: run_trauma_drive_compare
      found phi*P0 drives DRAIN the site and e*P0 drives PUMP it. Does the
      envelope phase of a weak recurring trigger decide whether the lock
      accumulates?

Injection is a RATE: per-step amplitude = I * dt with I = 0.04 (in
epsilon/unit-time), chosen so the steady state eps* = I/gamma ~ 0.47 sits
well above the undriven decay floor (0.28 at t=10) without drowning the
site. Cumulative stimulus over t=10 is 0.4—half the original event's peak
amplitude—delivered in 1e-4 steps of the event per unit time: a chronic
trigger, not a re-traumatization.

Runs (lambda=0.1, t=10; the regime where the undriven standing mode falls
to ~42% retained):
  ref   standing, no injection (reproduces the §10.4 null in-process; P0
        re-measured from this run)
  dc    standing + weak CONTINUOUS injection; stops at t=10, runs to t=20:
        the extinction test
  phi   same mean injection rate, envelope pulsed at T = phi*P0 (the decay
        channel found by run_trauma_drive_compare.py)
  e     same mean injection rate, envelope pulsed at T = e*P0 (the pump
        channel)

Verdict: does a weak recurring trigger hold eps_site at a plateau above the
undriven decay curve, keep q_site depressed and the phase displaced (lock);
does the phi-phased envelope fail to hold it (processing prevents
re-traumatization); does stopping the stimulus release the site (extinction
works)?

Usage: python two-fluid/run_trauma_driver.py
Output: runs/<id>_driver/results.json + figure
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

# Mirror the §10.4 long-run conditions (run 3 of the wake-lock test)
T.LAM = 0.1
T.DT = 0.001
T.REPORT = 50
T.AMP = 0.8

INJ_RATE = 0.04     # injection rate in epsilon/unit-time (see docstring)
T_END = 10.0        # injection window / reference horizon
T_EXT = 20.0        # extinction horizon for the dc run
STOP_AT = 10.0      # dc run: injection off after this time
PHI = T.PHI


def run_case(solver, inject=None, p0=None, stop_inject_at=None,
             t_end=T_END, tag='run', outdir=None):
    """Evolve the standing init with optional weak injection at the site."""
    steps = int(round(t_end / T.DT))
    amp = INJ_RATE * T.DT          # per-step amplitude = rate * dt
    print(f"\n=== run: {tag} (t_end={t_end}, inject={inject}, "
          f"rate={INJ_RATE}/s) ===")
    ey_hat, ei_hat, u_hat = T.init_fields(solver, 'standing', seed=42)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    t0 = time.time()
    hist = []

    for step in range(steps):
        ey = torch.fft.ifftn(ey_hat).real
        t_now = step * T.DT
        if inject is not None and (stop_inject_at is None
                                   or t_now < stop_inject_at):
            inj = amp
            if inject != 'dc':
                t_inj = PHI * p0 if inject == 'phi' else np.e * p0
                inj *= 1.0 + np.sin(2.0 * np.pi * t_now / t_inj)
            ey = ey - inj * mask
            ey_hat = torch.fft.fftn(ey)
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)

        if step % T.REPORT == 0 or step == steps - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            d = T.measure(solver, ey, ei, mask)
            d.update({'step': step, 't': t_now})
            hist.append(d)
            print(f"  t={t_now:5.2f} | eps_site={d['eps_site']:.4f} "
                  f"| q_site={d['q_site']:.3f} q_glob={d['q_glob']:.3f} "
                  f"| sig_r={d['sigma_r_site']:.4f} "
                  f"| phase={['%.2f' % f for f in d['phase_frac']]}")

    print(f"  [{tag}] {steps} steps in {time.time() - t0:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'hist': hist}, f, indent=1)
    return hist


def at_t(hist, t_target):
    """Nearest-sample diagnostics at time t_target."""
    return min(hist, key=lambda d: abs(d['t'] - t_target))


def summarize(name, hist, t_target):
    d = at_t(hist, t_target)
    eps0 = hist[0]['eps_site']
    return {
        't': t_target,
        'eps_site': d['eps_site'],
        'eps_rel': d['eps_site'] / max(eps0, 1e-12),
        'q_site': d['q_site'],
        'q_gap': d['q_glob'] - d['q_site'],
        'displ': 1.0 - d['phase_frac'][0],   # fraction NOT in Wood
        'sigma_r': d['sigma_r_site'],
    }


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  dt={T.DT}  "
          f"inj_rate={INJ_RATE}/s")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_driver"
    os.makedirs(rdir, exist_ok=True)

    solver = T.build_solver(device)

    # Reference: undriven standing (reproduces the §10.4 null)
    h_ref = run_case(solver, tag='ref', outdir=rdir)
    p0 = T.dominant_period([d['eps_site'] for d in h_ref], T.DT)
    print(f"\nMeasured natural period P0 = {p0:.4f} "
          f"(T_phi={PHI * p0:.4f}, T_e={np.e * p0:.4f})")

    # Weak continuous injection, then stop at t=10: extinction test
    h_dc = run_case(solver, inject='dc', stop_inject_at=STOP_AT,
                    t_end=T_EXT, tag='dc', outdir=rdir)

    # Pulsed injection envelopes (same mean rate), t=10
    h_phi = run_case(solver, inject='phi', p0=p0, tag='phi', outdir=rdir)
    h_e = run_case(solver, inject='e', p0=p0, tag='e', outdir=rdir)

    s_ref = summarize('ref', h_ref, 10.0)
    s_dc = summarize('dc', h_dc, 10.0)
    s_dc_end = summarize('dc', h_dc, 20.0)
    s_phi = summarize('phi', h_phi, 10.0)
    s_e = summarize('e', h_e, 10.0)

    results = {
        'meta': {'INJ_RATE': INJ_RATE, 'T_END': T_END, 'T_EXT': T_EXT,
                 'STOP_AT': STOP_AT, 'P0': p0,
                 'T_phi': PHI * p0, 'T_e': np.e * p0},
        'ref_t10': s_ref, 'dc_t10': s_dc, 'dc_t20': s_dc_end,
        'phi_t10': s_phi, 'e_t10': s_e,
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== DRIVER QUESTION RESULTS (t=10) ===")
    print(f"ref : eps={s_ref['eps_site']:.3f} ({s_ref['eps_rel']:.0%}) "
          f"q_gap={s_ref['q_gap']:+.3f} displ={s_ref['displ']:.2f}")
    print(f"dc  : eps={s_dc['eps_site']:.3f} ({s_dc['eps_rel']:.0%}) "
          f"q_gap={s_dc['q_gap']:+.3f} displ={s_dc['displ']:.2f}")
    print(f"phi : eps={s_phi['eps_site']:.3f} ({s_phi['eps_rel']:.0%}) "
          f"q_gap={s_phi['q_gap']:+.3f} displ={s_phi['displ']:.2f}")
    print(f"e   : eps={s_e['eps_site']:.3f} ({s_e['eps_rel']:.0%}) "
          f"q_gap={s_e['q_gap']:+.3f} displ={s_e['displ']:.2f}")
    print(f"\nExtinction (dc, t=20, injection off since t=10): "
          f"eps={s_dc_end['eps_site']:.3f} q_gap={s_dc_end['q_gap']:+.3f} "
          f"displ={s_dc_end['displ']:.2f}")

    held = s_dc['eps_site'] > s_ref['eps_site'] * 1.2
    phi_drains = s_phi['eps_site'] < s_dc['eps_site'] * 0.8
    e_pumps = s_e['eps_site'] > s_dc['eps_site'] * 1.2
    released = s_dc_end['eps_site'] < s_dc['eps_site'] * 0.6

    print("\n=== VERDICT ===")
    print(f"Perpetual stimulus holds the wake: {held}")
    print(f"phi-phased envelope drains (no lock): {phi_drains}")
    print(f"e-phased envelope pumps (lock): {e_pumps}")
    print(f"Stopping the stimulus releases the site: {released}")

    # ── Figure ─────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 2, figsize=(13, 9))
        runs = [('ref', h_ref, 'gray'), ('dc', h_dc, 'C0'),
                ('phi', h_phi, 'C2'), ('e', h_e, 'C3')]
        for name, h, c in runs:
            t = [d['t'] for d in h]
            axes[0, 0].plot(t, [d['eps_site'] for d in h], c, label=name)
            axes[0, 1].plot(t, [d['q_site'] for d in h], c, label=name)
            axes[1, 0].plot(t, [d['phase_frac'][1] for d in h], c,
                            label=name)
            axes[1, 1].plot(t, [d['sigma_r_site'] for d in h], c, label=name)
        axes[0, 0].axvline(10.0, color='w', ls=':', alpha=0.5)
        axes[0, 0].set_title('site |ε| (perturbation amplitude)')
        axes[0, 1].set_title('site q (5-channel coherence)')
        axes[1, 0].set_title('site Fire-channel fraction (displacement)')
        axes[1, 1].set_title('site σ_r (dispersion of r = EY/EI)')
        for ax in axes.flat:
            ax.set_xlabel('t')
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(f"{rdir}/driver.png", dpi=130)
        plt.close()
        print(f"\nFigure: {rdir}/driver.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
