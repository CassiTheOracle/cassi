#!/usr/bin/env python3
"""Strong-drive crossover: at what amplitude does the phi-phased drain turn on?

Two established endpoints (same solver, standing init):
  amp 0.3  -> phi*P0 drive DRAINS the site (66% retained vs 91% undriven,
              run_trauma_drive_compare.py)
  amp 4e-5 -> envelope phase irrelevant (chronic regime, run_trauma_driver.py)

Binary question: is the phi-specific drain present at intermediate drive
amplitudes (0.05, 0.15)? This brackets the crossover between the chronic
regime (phase-blind accumulation) and the intervention regime (phi-phased
drain)—the minimum "processing intensity" that actively releases a wake.

Protocol mirrors the drive_compare short run: lambda=0.05, t=2.0, drive
period T = phi * P0 with P0 measured in-process from the undriven run.

Usage: python two-fluid/run_trauma_crossover.py
Output: runs/<id>_crossover/results.json
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
T.STEPS = 2000          # t = 2: the displaced-gate short-run regime
T.AMP = 0.8

PROBES = [0.05, 0.15]   # drive amplitudes to test (0.3 is the known drain)
PHI = T.PHI


def run_case(solver, drive_amp=None, drive_period=None, tag='run',
             outdir=None):
    """Standing init; optional phi-phased drive at the site (EMDR analog)."""
    print(f"\n=== run: {tag} (drive_amp={drive_amp}) ===")
    ey_hat, ei_hat, u_hat = T.init_fields(solver, 'standing', seed=42)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    t0 = time.time()
    hist = []

    for step in range(T.STEPS):
        ey = torch.fft.ifftn(ey_hat).real
        if drive_amp is not None:
            t_now = step * T.DT
            drive = drive_amp * np.sin(2.0 * np.pi * t_now / drive_period)
            ey = ey + drive * mask
            ey_hat = torch.fft.fftn(ey)
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)

        if step % T.REPORT == 0 or step == T.STEPS - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            d = T.measure(solver, ey, ei, mask)
            d.update({'step': step, 't': step * T.DT})
            hist.append(d)

    print(f"  [{tag}] {T.STEPS} steps in {time.time() - t0:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'hist': hist}, f, indent=1)
    return hist


def summarize(name, hist):
    first, last = hist[0], hist[-1]
    phase0 = np.array(first['phase_frac'])
    return {
        'eps_site': last['eps_site'],
        'eps_rel': last['eps_site'] / max(first['eps_site'], 1e-12),
        'q_site': last['q_site'],
        'q_gap': last['q_glob'] - last['q_site'],
        'displ': 1.0 - last['phase_frac'][0],
        'displ_start': 1.0 - phase0[0],
    }


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t=2.0")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_crossover"
    os.makedirs(rdir, exist_ok=True)

    solver = T.build_solver(device)

    h_ref = run_case(solver, tag='ref', outdir=rdir)
    p0 = T.dominant_period([d['eps_site'] for d in h_ref], T.DT)
    print(f"\nMeasured natural period P0 = {p0:.4f} "
          f"(T_phi = {PHI * p0:.4f})")
    t_drive = PHI * p0

    results = {'meta': {'P0': p0, 'T_phi': t_drive, 'probes': PROBES},
               'runs': {}}
    results['runs']['ref'] = summarize('ref', h_ref)
    for amp in PROBES:
        h = run_case(solver, drive_amp=amp, drive_period=t_drive,
                     tag=f'drive_{amp}', outdir=rdir)
        results['runs'][f'drive_{amp}'] = summarize(f'drive_{amp}', h)

    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== CROSSOVER RESULTS (t=2) ===")
    ref = results['runs']['ref']
    print(f"undriven          : eps_rel={ref['eps_rel']:.3f} "
          f"q_gap={ref['q_gap']:+.3f} displ={ref['displ']:.2f}")
    known = {'0.05': None, '0.15': None}
    for amp in PROBES:
        s = results['runs'][f'drive_{amp}']
        print(f"drive amp {amp:5.2f} : eps_rel={s['eps_rel']:.3f} "
              f"q_gap={s['q_gap']:+.3f} displ={s['displ']:.2f}")
        known[f'{amp:g}'] = s

    # Known endpoints for the verdict
    drain_03 = 0.664          # from run_trauma_drive_compare.py
    print(f"(known) drive amp 0.30: eps_rel={drain_03:.3f} (drain)")
    print(f"(known) chronic 4e-5  : eps_rel≈0.91 (phase-blind)")

    drained = [amp for amp in PROBES
               if results['runs'][f'drive_{amp}']['eps_rel']
               < ref['eps_rel'] - 0.05]
    if drained == PROBES:
        print("*** DRAIN PRESENT AT ALL PROBED AMPLITUDES—the crossover "
              "lies below 0.05. ***")
    elif not drained:
        print("NO DRAIN at probed amplitudes—the crossover lies above "
              "0.15 (between 0.15 and 0.3).")
    else:
        print(f"DRAIN ONSET between {drained[0]:.2f} and the next probe—"
              f"crossover bracketed.")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
