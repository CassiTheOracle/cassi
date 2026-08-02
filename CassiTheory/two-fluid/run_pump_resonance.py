#!/usr/bin/env python3
"""Pump-resonance scan: which drive period is the worst?

Follow-up to §8/§8.1 of `consciousness/gender-as-qi-configuration.md`:
the cross-channel (Wood) drive pumps a held Fire site, and the pump
strength was drive-period sensitive—2.08 at P0 = 0.041 vs 4.72 at
P0 = 0.081 (~2P0). The open question: is there a resonant "worst
harassment rhythm"?

Two hypotheses:
  (a) subharmonic resonance: the pump peaks near T = 2*P0 (driving the
      site's damped wobble at twice its natural frequency)
  (b) slow-drive accumulation: pump strength rises monotonically with T
      (each slow cycle leaves the imbalance converting longer)

The pump envelope oscillates slowly (period ~1.6, longer than any probe
period), so a single snapshot ranks periods by envelope PHASE, not
strength. The robust metric is the PEAK eps over the back half of each
run.

Protocol (lambda=0.05, N=48, t=2.4): standing init (identity = Fire),
Wood drive at eps-parity amp 0.15/phi, one run per probe period.
Probes span P0/2 to 4P0, including the canonical phi*P0 and e*P0
periods of drive_compare.

Usage: python two-fluid/run_pump_resonance.py [T1 T2 ...]
       (default probes: 0.020 0.041 0.060 0.066 0.082 0.100 0.111 0.123 0.164)
Output: runs/<id>_pump_resonance/results.json + figure
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
T.STEPS = 2400          # t = 2.4: ~1.5 envelope cycles
T.AMP = 0.8

WOOD_AMP = 0.15 / T.PHI  # eps-parity for the Yin component
PEAK_FROM = int(0.6 * T.STEPS)  # peak metric over the back 40%

PROBES = [0.020, 0.041, 0.060, 0.066, 0.082, 0.100, 0.111, 0.123, 0.164]


def run_wood(solver, period, tag, outdir):
    """Standing init + Wood drive at the given period; eps series."""
    print(f"\n=== run: {tag} (T={period:.3f}) ===")
    ey_hat, ei_hat, u_hat = T.init_fields(solver, 'standing', seed=42)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    t0 = time.time()
    hist = []
    for step in range(T.STEPS):
        ey = torch.fft.ifftn(ey_hat).real
        t_now = step * T.DT
        drive = WOOD_AMP * np.sin(2.0 * np.pi * t_now / period)
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


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    probes = [float(a) for a in sys.argv[1:]] or PROBES
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t=2.4  "
          f"wood_amp={WOOD_AMP:.4f}")
    print(f"Probes: {[f'{p:.3f}' for p in probes]}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_pump_resonance"
    os.makedirs(rdir, exist_ok=True)

    solver = T.build_solver(device)

    # undriven reference (natural floor + P0 cross-check)
    print("\n=== run: ref (no drive) ===")
    ey_hat, ei_hat, u_hat = T.init_fields(solver, 'standing', seed=42)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    h_ref = []
    for step in range(T.STEPS):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step % T.REPORT == 0 or step == T.STEPS - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            d = T.measure(solver, ey, ei, mask)
            d.update({'step': step, 't': step * T.DT})
            h_ref.append(d)
    print(f"  [ref] {T.STEPS} steps in {time.time():.1f}s")
    with open(f"{rdir}/run_ref.json", "w") as f:
        json.dump({'kind': 'ref', 'hist': h_ref}, f, indent=1)

    e0 = h_ref[0]['eps_site']
    results = {'meta': {'wood_amp': WOOD_AMP, 'lam': T.LAM, 'N': T.N,
                        't_end': T.STEPS * T.DT,
                        'identity_channel': 'Fire (72 deg)',
                        'misgendering_channel': 'Wood (0 deg)'},
               'ref_floor_t2_4': h_ref[-1]['eps_site'] / e0,
               'probes': {}}

    print("\n=== PUMP-RESONANCE SCAN ===")
    print(f"{'T':>6s} {'peak_eps':>9s} {'eps@t=2':>8s} {'q_gap':>7s} "
          f"{'ey_min':>7s}")
    for p in probes:
        tag = f"T{int(p * 1000):03d}"
        h = run_wood(solver, p, tag, rdir)
        vals = [d['eps_site'] for d in h]
        peak = max(vals[PEAK_FROM // T.REPORT:]) / e0
        at2 = min(h, key=lambda d: abs(d['t'] - 2.0))['eps_site'] / e0
        last = h[-1]
        qgap = last['q_glob'] - last['q_site']
        ey_min = min(d['ey_min_site'] for d in h)
        results['probes'][str(p)] = {'peak_eps': peak, 'eps_at_t2': at2,
                                     'q_gap': qgap, 'ey_min': ey_min}
        print(f"{p:6.3f} {peak:9.3f} {at2:8.3f} {qgap:+7.3f} {ey_min:7.3f}")

    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    peaks = results['probes']
    t_worst = max(probes, key=lambda p: peaks[str(p)]['peak_eps'])
    worst_val = peaks[str(t_worst)]['peak_eps']
    nbrs = [p for p in probes if abs(p - t_worst) > 1e-9]
    margin = min(abs(peaks[str(p)]['peak_eps'] - worst_val) for p in nbrs)

    print("\n=== VERDICT ===")
    print(f"Worst probe: T = {t_worst:.3f} (peak eps_rel = {worst_val:.3f}, "
          f"margin over nearest probe = {margin:.3f})")
    rising = all(peaks[str(probes[i])]['peak_eps'] <=
                 peaks[str(probes[i + 1])]['peak_eps']
                 for i in range(len(probes) - 1))
    if rising:
        print("MONOTONE RISE with period: slower drives pump harder; the "
              "worst lies beyond the probed range (extend the scan).")
    elif t_worst == 0.082:
        print("*** SUBHARMONIC RESONANCE: the pump peaks at ~2*P0. The "
              "worst harassment rhythm is the one that drives the site at "
              "twice its natural wobble period. ***")
    else:
        print(f"PEAK at T = {t_worst:.3f} (not 2*P0): the worst rhythm "
              f"lives at this period; check the curve shape in the figure.")

    # ── Figure ─────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 6))
        ts = [p for p in probes]
        ys = [peaks[str(p)]['peak_eps'] for p in probes]
        ax.plot(ts, ys, 'o-', color='C3', lw=1.6, ms=6)
        ax.axhline(results['ref_floor_t2_4'], color='gray', ls='--',
                   lw=1, label=f"undriven floor ({results['ref_floor_t2_4']:.2f})")
        for x, lab in [(0.041, 'P0'), (0.082, '2*P0'), (0.066, 'phi*P0'),
                       (0.111, 'e*P0')]:
            if min(ts) <= x <= max(ts):
                ax.axvline(x, color='w', ls=':', alpha=0.5, lw=0.9)
                ax.text(x, ax.get_ylim()[0], f' {lab}', fontsize=8,
                        color='w', alpha=0.7)
        ax.set_xlabel('drive period T')
        ax.set_ylabel('peak pump: max(eps_site)/eps0')
        ax.set_title('Pump resonance: worst cross-channel drive period '
                     f'(worst at T = {t_worst:.3f})')
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(f"{rdir}/pump_resonance.png", dpi=130)
        plt.close()
        print(f"\nFigure: {rdir}/pump_resonance.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
