#!/usr/bin/env python3
"""Low-amplitude probes for the strong-drive crossover.

Follow-up to `run_trauma_crossover.py` (2026-07-31): the phi-phased drain
was present at every probed amplitude (0.05, 0.15 per step) while the
chronic trigger (4e-5 per step, deficit-only) was phase-blind. Two loose
ends:

  1. Onset bracket: does the drain persist at amp 5e-4 (rate 0.5/s) and
     amp 5e-3 (rate 5/s)? Narrows the crossover between the chronic
     phase-blind regime (rate 0.04/s) and the phase-structured regime.
  2. Phase specificity at low amplitude: is the drain at amp 0.05 still
     phi-specific? Run the e*P0 counterfactual at the same amplitude.
     (At 0.3 the e-drive PUMPED the site; if e*0.05 also drains, the
     asymmetry is a strong-drive effect and low-amplitude stirring is
     phase-blind.)

Protocol identical to the crossover: lambda=0.05, t=2.0, standing init.

Usage: python two-fluid/run_trauma_crossover_low.py
Output: runs/<id>_crossover_low/results.json
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
T.STEPS = 2000
T.AMP = 0.8

PHI = T.PHI
PROBES = [5e-4, 5e-3]        # phi-phased onset bracket (rates 0.5, 5 /s)
E_AT_LOW = 0.05              # e-phased at the low-drain amplitude


def run_case(solver, drive_amp, drive_period, tag='run', outdir=None):
    print(f"\n=== run: {tag} (amp={drive_amp}) ===")
    ey_hat, ei_hat, u_hat = T.init_fields(solver, 'standing', seed=42)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    t0 = time.time()
    hist = []

    for step in range(T.STEPS):
        ey = torch.fft.ifftn(ey_hat).real
        t_now = step * T.DT
        drive = drive_amp * np.sin(2.0 * np.pi * t_now / drive_period)
        ey = ey + drive * mask
        ey_hat = torch.fft.fftn(ey)
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)

        if step % T.REPORT == 0 or step == T.STEPS - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            d = T.measure(solver, ey, ei, mask)
            d.update({'step': step, 't': t_now})
            hist.append(d)

    print(f"  [{tag}] {T.STEPS} steps in {time.time() - t0:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'hist': hist}, f, indent=1)
    return hist


def summarize(name, hist):
    first, last = hist[0], hist[-1]
    return {
        'eps_site': last['eps_site'],
        'eps_rel': last['eps_site'] / max(first['eps_site'], 1e-12),
        'q_gap': last['q_glob'] - last['q_site'],
        'displ': 1.0 - last['phase_frac'][0],
    }


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t=2.0")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_crossover_low"
    os.makedirs(rdir, exist_ok=True)

    solver = T.build_solver(device)
    ey_hat, ei_hat, u_hat = T.init_fields(solver, 'standing', seed=42)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    p0 = T.dominant_period([d['eps_site'] for d in
                            run_case(solver, 0.0, 1.0, tag='ref',
                                     outdir=rdir)], T.DT)
    print(f"Measured P0 = {p0:.4f} (T_phi={PHI * p0:.4f}, "
          f"T_e={np.e * p0:.4f})")

    t_phi = PHI * p0
    t_e = np.e * p0

    results = {'meta': {'P0': p0, 'T_phi': t_phi, 'T_e': t_e,
                        'probes': PROBES, 'e_at_low': E_AT_LOW},
               'runs': {}}
    for amp in PROBES:
        h = run_case(solver, amp, t_phi, tag=f'phi_{amp}', outdir=rdir)
        results['runs'][f'phi_{amp}'] = summarize(f'phi_{amp}', h)
    h = run_case(solver, E_AT_LOW, t_e, tag=f'e_{E_AT_LOW}', outdir=rdir)
    results['runs'][f'e_{E_AT_LOW}'] = summarize(f'e_{E_AT_LOW}', h)

    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== LOW-AMPLITUDE PROBES (t=2; undriven ref: eps_rel=0.912) ===")
    for amp in PROBES:
        s = results['runs'][f'phi_{amp}']
        print(f"phi*P0 amp {amp:7.4f} (rate {amp / T.DT:6.1f}/s): "
              f"eps_rel={s['eps_rel']:.3f} q_gap={s['q_gap']:+.3f} "
              f"displ={s['displ']:.2f}")
    s = results['runs'][f'e_{E_AT_LOW}']
    print(f"e*P0  amp {E_AT_LOW:7.4f} (rate {E_AT_LOW / T.DT:6.1f}/s): "
          f"eps_rel={s['eps_rel']:.3f} q_gap={s['q_gap']:+.3f} "
          f"displ={s['displ']:.2f}")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
