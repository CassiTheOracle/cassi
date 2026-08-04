#!/usr/bin/env python3
"""Churning-gate amplitude scan: is the pump amplitude-thresholded?

Follow-up to `consciousness/neurodivergence-as-gate-configuration.md` §9
(the 2026-08-04 churning-gate test, `two-fluid/run_churning_gate.py`):
from the low-q mixed-channel init, the in-channel drive at amp 0.15
pumped the site (3.31x retained, q-gap widening) and the undriven
reference churned without stabilizing a vertex. Two open questions:

  (a) is the pump amplitude-thresholded, and does ANY in-channel
      amplitude settle the gate—eps below the undriven floor, q-gap
      narrowing, a vertex stabilizing?
  (b) what does the held-configuration drain amplitude (0.30) do to an
      OPEN gate—drain it like the held site, or pump it like 0.15 does?

Protocol (lambda=0.05, t=4, N=48; same churning init, seed 42; same
in-process P0 measured from the t=4 ref window; drive at the same P0,
per the dominant_period window caveat of `consciousness/gender-as-qi-
configuration.md` §8.1):
  ref        undriven
  in-0.025   in-channel at P0, amp 0.025 (below the phase-blindness
             floor, >= 0.05 — the no-op control)
  in-0.05    in-channel at P0, amp 0.05 (the phase floor)
  in-0.10    in-channel at P0, amp 0.10
  in-0.15    in-channel at P0, amp 0.15 (reproduces the known pump)
  in-0.20    in-channel at P0, amp 0.20
  in-0.30    in-channel at P0, amp 0.30 (the held-config drain amp)
  cross-0.05 cross-channel at P0, eps-parity amp 0.05/phi (ordering
             contrast at the floor)
  cross-0.30 cross-channel at P0, eps-parity amp 0.30/phi (ordering
             contrast at the drain amplitude)

Arms reuse `run_case` from the baseline script (same init, same drive
schedule, same diagnostics). Verdict quantities at the site (ball around
the box center):
  eps_rel        site mean |epsilon| at t_end / init (churn amplitude)
  q_gap          q_glob - q_site; narrowing = closing the open gate
  phase_max      dominant phase-histogram fraction (vertex stabilizing)
  ey/ei_min_site clamp diagnostics (1e-3 positivity floor), min over run

Settling (all three): eps_rel <= ref_eps_rel - 0.05 AND q-gap narrowed
by >= 0.02 vs ref AND phase_max rose >= 0.2 vs ref. Pump: eps_rel >= 1.3
with the q-gap not narrowing. Threshold: the lowest in-channel amplitude
whose behavior deviates from the 0.025 no-op control (|d_eps_rel| > 0.05
or |d_q_gap| > 0.02), which also validates the control against ref.

Usage: python two-fluid/run_churning_gate_amp_scan.py
Output: runs/<id>_churning_amp/results.json + figure
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
T.STEPS = 4000          # t = 4: the doc's upper bound, drive gets ~50+ cycles

CLAMP_FLOOR = 1e-3
NEAR_FLOOR = 1.5e-3

IN_AMPS = [0.025, 0.05, 0.10, 0.15, 0.20, 0.30]
CROSS_AMPS = [0.05, 0.30]          # eps-parity ordering contrasts


def run_min_clamps(hist):
    """Minimum ey/ei over the site across the run (clamp diagnostics)."""
    ey_min = min(d['ey_min_site'] for d in hist)
    ei_min = min(d['ei_min_site'] for d in hist)
    return ey_min, ei_min


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t=4.0")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_churning_amp"
    os.makedirs(rdir, exist_ok=True)

    solver = T.build_solver(device)

    # ── Reference: measure P0 and the site's channel phase in-process ────
    h_ref = G.run_case(solver, tag='ref', outdir=rdir)
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
    print(f"  -> in-channel drive on '{in_ch}', cross-channel on '{cross_ch}'")

    # ── Arms ──────────────────────────────────────────────────────────────
    h_in = {}
    for amp in IN_AMPS:
        tag = f"in{amp * 100:.0f}"
        h_in[amp] = G.run_case(solver, tag=tag, outdir=rdir,
                               drive_channel=in_ch, drive_period=p0,
                               drive_amp=amp)
    h_cross = {}
    for amp in CROSS_AMPS:
        tag = f"cross{amp * 100:.0f}"
        h_cross[amp] = G.run_case(solver, tag=tag, outdir=rdir,
                                  drive_channel=cross_ch, drive_period=p0,
                                  drive_amp=amp / T.PHI)

    s_ref = G.summarize('ref', h_ref)
    s_in = {amp: G.summarize(f'in-{amp}', h) for amp, h in h_in.items()}
    s_cross = {amp: G.summarize(f'cross-{amp}', h)
               for amp, h in h_cross.items()}

    results = {
        'meta': {'P0': p0, 'drive_period': p0, 'lam': T.LAM, 'N': T.N,
                 't_end': T.STEPS * T.DT, 'basin_t0': basin,
                 'eps_mean_t0': eps_mean_init, 'in_channel': in_ch,
                 'cross_channel': cross_ch, 'in_amps': IN_AMPS,
                 'cross_amps': [a / T.PHI for a in CROSS_AMPS],
                 'settle_eps_margin': 0.05, 'settle_gap_narrow': 0.02,
                 'settle_phase_rise': 0.2, 'pump_eps_rel': 1.3},
        'ref': s_ref,
        'in_channel': {str(amp): s for amp, s in s_in.items()},
        'cross_channel': {str(amp): s for amp, s in s_cross.items()},
    }
    # per-arm run-min clamps
    clamps = {}
    for amp, h in h_in.items():
        clamps[f'in-{amp}'] = run_min_clamps(h)
    for amp, h in h_cross.items():
        clamps[f'cross-{amp}'] = run_min_clamps(h)
    clamps['ref'] = run_min_clamps(h_ref)
    results['clamp_min_site'] = clamps

    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    # ── Table ─────────────────────────────────────────────────────────────
    print("\n=== CHURNING-GATE AMPLITUDE SCAN (t=4) ===")
    print(f"{'arm':>9s} {'eps_rel':>7s} {'peak':>6s} "
          f"{'q_gap init->end':>15s} {'phase_max':>16s} "
          f"{'ey_min':>7s} {'ei_min':>7s} {'eps_var_t':>9s}")
    rows = [('ref', s_ref, h_ref)]
    rows += [(f'in-{amp}', s_in[amp], h_in[amp]) for amp in IN_AMPS]
    rows += [(f'cross-{amp}', s_cross[amp], h_cross[amp])
             for amp in CROSS_AMPS]
    for name, s, h in rows:
        ey_min, ei_min = run_min_clamps(h)
        print(f"{name:>9s} {s['eps_rel']:7.3f} {s['peak_eps_rel']:6.3f} "
              f"{s['q_gap_init']:+6.3f}->{s['q_gap']:+6.3f} "
              f"{s['phase_max_init']:6.2f}->{s['phase_max']:6.2f} "
              f"{ey_min:7.3f} {ei_min:7.3f} {s['eps_var_t_back']:9.5f}")

    # ── Verdicts ──────────────────────────────────────────────────────────
    r = s_ref
    gap_narrow_vs_ref = lambda s: r['q_gap'] - s['q_gap'] >= 0.02
    phase_rise_vs_ref = lambda s: s['phase_max'] - r['phase_max'] >= 0.2
    settling = lambda s: (s['eps_rel'] <= r['eps_rel'] - 0.05 and
                          gap_narrow_vs_ref(s) and phase_rise_vs_ref(s))
    pump = lambda s: s['eps_rel'] >= 1.3 and not gap_narrow_vs_ref(s)
    changed = lambda s: (abs(s['eps_rel'] - s_in[0.025]['eps_rel']) > 0.05 or
                         abs(s['q_gap'] - s_in[0.025]['q_gap']) > 0.02)

    print("\n=== VERDICT ===")
    control_ok = (abs(s_in[0.025]['eps_rel'] - r['eps_rel']) < 0.05 and
                  abs(s_in[0.025]['q_gap'] - r['q_gap']) < 0.02)
    print(f"No-op control (in-0.025) matches ref: {control_ok}")

    for amp in IN_AMPS:
        s = s_in[amp]
        print(f"in-{amp}: settling={settling(s)}  pump={pump(s)}  "
              f"changed_vs_floor_control={changed(s)}")

    threshold = None
    for amp in IN_AMPS:
        if changed(s_in[amp]):
            threshold = amp
            break
    if threshold is not None:
        print(f"Amplitude threshold (first deviation from the no-op "
              f"control): in-channel amp = {threshold:.3f}")
    else:
        print("Amplitude threshold: none within the probed range—all "
              "amplitudes behave like the no-op control.")

    any_settle = any(settling(s_in[amp]) for amp in IN_AMPS)
    any_pump = any(pump(s_in[amp]) for amp in IN_AMPS)
    drain30 = s_in[0.30]
    held_drain_verdict = ("DRAINS the open gate" if settling(drain30) else
                          "PUMPS the open gate" if pump(drain30) else
                          "tracks the undriven churn")
    print(f"In-channel settling at any amplitude: {any_settle}")
    print(f"In-channel pumping at any amplitude: {any_pump}")
    print(f"Held-config drain amplitude 0.30 on the OPEN gate: "
          f"{held_drain_verdict} "
          f"(eps_rel {drain30['eps_rel']:.3f}, q-gap "
          f"{drain30['q_gap_init']:+.3f}->{drain30['q_gap']:+.3f})")
    for amp in CROSS_AMPS:
        s = s_cross[amp]
        print(f"cross-{amp} (eps-parity): eps_rel {s['eps_rel']:.3f}, "
              f"q-gap {s['q_gap_init']:+.3f}->{s['q_gap']:+.3f}")

    if any_settle:
        print("*** SETTLING AMPLITUDE FOUND: some in-channel amplitude "
              "drains eps below the undriven floor with the q-gap "
              "narrowing and a vertex stabilizing—the churning gate "
              "closes under the right drive strength. ***")
    elif any_pump:
        print("*** NO SETTLING, PUMP AT EVERY AMPLITUDE: every in-channel "
              "amplitude pumps the churning gate or tracks the undriven "
              "churn—the churning gate does not close under a fixed-"
              "period in-channel drive of any strength; the §9 null "
              "extends across the amplitude axis. ***")
    else:
        print("NO SETTLING AND NO PUMP: all amplitudes track the "
              "undriven churn (no amplitude dependence).")

    # ── Figure ─────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 2, figsize=(13, 9))
        cmap = plt.get_cmap('plasma')
        t = [d['t'] for d in h_ref]
        axes[0, 0].plot(t, [d['eps_site'] for d in h_ref], 'gray',
                        label='ref')
        axes[0, 1].plot(t, [d['q_site'] for d in h_ref], 'gray', label='ref')
        axes[1, 0].plot(t, [d['phase_frac'][1] for d in h_ref], 'gray',
                        label='ref')
        axes[1, 1].plot(t, [d['sigma_r_site'] for d in h_ref], 'gray',
                        label='ref')
        for amp, h in h_in.items():
            c = cmap(0.15 + 0.75 * (amp - min(IN_AMPS)) /
                     (max(IN_AMPS) - min(IN_AMPS)))
            tt = [d['t'] for d in h]
            axes[0, 0].plot(tt, [d['eps_site'] for d in h], color=c,
                            label=f'in-{amp}')
            axes[0, 1].plot(tt, [d['q_site'] for d in h], color=c)
            axes[1, 0].plot(tt, [d['phase_frac'][1] for d in h], color=c)
            axes[1, 1].plot(tt, [d['sigma_r_site'] for d in h], color=c)
        axes[0, 0].set_title('site mean |epsilon| (churn amplitude)')
        axes[0, 1].set_title('site q (5-channel coherence)')
        axes[1, 0].set_title('site Fire-channel fraction (churn basin)')
        axes[1, 1].set_title('site sigma_r (dispersion of r = EY/EI)')
        for ax in axes.flat:
            ax.set_xlabel('t')
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
        fig.suptitle(f'Churning-gate amplitude scan (in-channel at P0 '
                     f'{p0:.3f}, basin {basin}; cross at eps-parity '
                     f'0.05, 0.30)')
        fig.tight_layout()
        fig.savefig(f"{rdir}/churning_amp_scan.png", dpi=130)
        plt.close()
        print(f"\nFigure: {rdir}/churning_amp_scan.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
