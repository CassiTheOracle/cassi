#!/usr/bin/env python3
"""Processing-capacity test: does pre-trauma coherence modulate susceptibility?

Open question 1 in `consciousness/trauma-as-frozen-gate.md`: what determines
whether an event becomes a frozen wake? The measurable claim is that
pre-trauma coherence modulates trauma susceptibility. Tested here as the
re-traumatization binary: does the same event leave a LARGER trace when it
lands on a site already carrying a wake (pre-stress, amp 0.8, evolved for
t=2) than when it lands on a quiet field?

Runs (lambda=0.1, N=48, t=22):
  prestress     standing deficit (amp 0.8) alone for t=22. Because it starts
                from the same init as the quiet-field event run, its trace
                IS the first hit's full trace on the quiet field.
  prestress+hit prestress evolved to t=2, then the SAME event injected
                again at the site, evolved to t=22.

Verdict: compare the marginal trace of the second hit, (b - a) at t=22,
against the first hit's full trace (a - quiet):
  - marginal ~ full trace   -> each hit leaves the same mark: no
    susceptibility modulation
  - marginal << full trace  -> a stressed site absorbs later events
  - marginal > full trace   -> pre-stress amplifies: re-traumatization
    locks harder (susceptibility confirmed)

Usage: python two-fluid/run_trauma_capacity.py
Output: runs/<id>_capacity/results.json + figure
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

T.LAM = 0.1
T.DT = 0.001
T.REPORT = 50
T.AMP = 0.8

STAGE1 = 2.0    # pre-stress evolution before the second hit
T_END = 22.0


def pattern_3d(N_, dev):
    """The standing init pattern: cos(2pi x/N) cos(2pi y/N) cos(2pi z/N),
    +1 at box corners, -1 at the box center (Yang deficit node)."""
    x = torch.arange(N_, dtype=torch.float64, device=dev)
    return (torch.cos(2.0 * np.pi * x / N_).unsqueeze(1).unsqueeze(2) *
            torch.cos(2.0 * np.pi * x / N_).unsqueeze(0).unsqueeze(2) *
            torch.cos(2.0 * np.pi * x / N_).unsqueeze(0).unsqueeze(0))


def run_case(solver, hit=False, t_end=T_END, tag='run', outdir=None):
    """Standing init; optionally a second identical event at t=STAGE1."""
    steps = int(round(t_end / T.DT))
    hit_at = int(round(STAGE1 / T.DT))
    print(f"\n=== run: {tag} (t_end={t_end}, second hit at t={STAGE1}) ===")
    ey_hat, ei_hat, u_hat = T.init_fields(solver, 'standing', seed=42)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    pat = pattern_3d(solver.N, solver.device)
    t0 = time.time()
    hist = []

    for step in range(steps):
        t_now = step * T.DT
        if hit and step == hit_at:
            ey = torch.fft.ifftn(ey_hat).real
            ey = ey + T.AMP * pat          # same event, re-injected
            ey = torch.clamp(ey, min=1e-3)
            ey_hat = torch.fft.fftn(ey)
            print(f"  [hit] event re-injected at t={t_now}")
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)

        if step % T.REPORT == 0 or step == steps - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            d = T.measure(solver, ey, ei, mask)
            d.update({'step': step, 't': t_now})
            hist.append(d)

    print(f"  [{tag}] {steps} steps in {time.time() - t0:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'hist': hist}, f, indent=1)
    return hist


def at_t(hist, t_target):
    return min(hist, key=lambda d: abs(d['t'] - t_target))


def summarize(name, hist, t_target):
    d = at_t(hist, t_target)
    return {
        't': t_target,
        'eps_site': d['eps_site'],
        'q_site': d['q_site'],
        'q_gap': d['q_glob'] - d['q_site'],
        'displ': 1.0 - d['phase_frac'][0],
        'sigma_r': d['sigma_r_site'],
    }


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  amp={T.AMP}  "
          f"stage1={STAGE1}  t_end={T_END}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_capacity"
    os.makedirs(rdir, exist_ok=True)

    solver = T.build_solver(device)

    h_a = run_case(solver, hit=False, tag='prestress', outdir=rdir)
    h_b = run_case(solver, hit=True, tag='prestress_hit', outdir=rdir)

    a = summarize('a', h_a, T_END)          # first hit's full trace
    b = summarize('b', h_b, T_END)          # stressed + second hit
    a2 = summarize('a', h_a, STAGE1)        # stressed state at hit time
    b2 = summarize('b', h_b, STAGE1 + 0.05)

    results = {'meta': {'stage1': STAGE1, 't_end': T_END, 'amp': T.AMP},
               'first_trace_t22': a, 'second_trace_t22': b,
               'at_hit_time': a2}
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    # Marginal trace of the second hit = b - a (both at t=22)
    marg = {k: b[k] - a[k] for k in ('eps_site', 'q_gap', 'displ', 'sigma_r')}

    print("\n=== CAPACITY TEST (t=22) ===")
    print(f"first hit on quiet field : eps={a['eps_site']:.3f} "
          f"q_gap={a['q_gap']:+.3f} displ={a['displ']:.2f} "
          f"sigma_r={a['sigma_r']:.3f}")
    print(f"second hit on stressed   : eps={b['eps_site']:.3f} "
          f"q_gap={b['q_gap']:+.3f} displ={b['displ']:.2f} "
          f"sigma_r={b['sigma_r']:.3f}")
    print(f"marginal trace of 2nd hit: eps={marg['eps_site']:+.3f} "
          f"q_gap={marg['q_gap']:+.3f} displ={marg['displ']:+.2f} "
          f"sigma_r={marg['sigma_r']:+.3f}")
    print(f"stressed state at hit time: eps={a2['eps_site']:.3f} "
          f"q_site={a2['q_site']:.3f} displ={a2['displ']:.2f}")

    ratio = marg['eps_site'] / max(a['eps_site'], 1e-9)
    print(f"marginal/first-trace ratio (eps): {ratio:.2f}")
    if ratio > 1.3:
        print("*** AMPLIFIED: the second hit leaves a LARGER trace on the "
              "pre-stressed site—susceptibility confirmed. ***")
    elif ratio < 0.7:
        print("ABSORBED: the pre-stressed site absorbs the second hit "
              "faster than the quiet field absorbed the first.")
    else:
        print("NO MODULATION: each hit leaves the same mark regardless of "
              "background coherence.")

    # ── Figure ─────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 2, figsize=(13, 9))
        runs = [('prestress', h_a, 'C0'), ('prestress+hit', h_b, 'C3')]
        for name, h, c in runs:
            t = [d['t'] for d in h]
            axes[0, 0].plot(t, [d['eps_site'] for d in h], c, label=name)
            axes[0, 1].plot(t, [d['q_site'] for d in h], c, label=name)
            axes[1, 0].plot(t, [d['phase_frac'][1] for d in h], c,
                            label=name)
            axes[1, 1].plot(t, [d['sigma_r_site'] for d in h], c, label=name)
        axes[0, 0].axvline(STAGE1, color='w', ls=':', alpha=0.5)
        axes[0, 0].set_title('site |ε|')
        axes[0, 1].set_title('site q')
        axes[1, 0].set_title('site Fire-channel fraction')
        axes[1, 1].set_title('site σ_r')
        for ax in axes.flat:
            ax.set_xlabel('t')
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(f"{rdir}/capacity.png", dpi=130)
        plt.close()
        print(f"\nFigure: {rdir}/capacity.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
