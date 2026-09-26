#!/usr/bin/env python3
"""Drive-frequency comparison for the trauma wake-lock test.

Follow-up to `run_trauma_wake_lock.py` §10.4 (2026-07-31): the standing run
with a phi-phased drive (T = phi*P0) accelerated relaxation (eps retained
65% vs 91% undriven). Binary question: is the effect phi-specific, or does
any same-amplitude oscillation stir the site back to baseline?

Protocol (mirrors run 2 conditions exactly, for direct comparability):
  - solver: ExpandingTwoFluid3DGPU, qi_gate=True, gate_model='five',
    lam=0.05, dt=0.001, t_max=2.0, N=48
  - perturbation: standing cos^3 Yang deficit, peak -0.8
  - drive amplitude 0.3, two periods:
      T_phi = phi * P0   (the original positive result)
      T_alt = e * P0     (counterfactual: clearly non-phi irrational)
  - P0 measured fresh from an undriven standing run in this process

Usage: python two-fluid/run_trauma_drive_compare.py
Output: runs/<id>_drive_compare/results.json
"""

import sys
import os
import json
import time
from datetime import datetime

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_trauma_wake_lock as T

# Mirror run 2 of the wake-lock test (lambda=0.05, t=2.0)
T.LAM = 0.05
T.STEPS = 2000
T.DT = 0.001
T.REPORT = 50

PHI = T.PHI


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  lam={T.LAM}  steps={T.STEPS}  dt={T.DT}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_drive_compare"
    os.makedirs(rdir, exist_ok=True)

    solver = T.build_solver(device)

    # 1. Undriven standing (reference)—measure P0 from its eps series
    h_ref = T.run_case(solver, 'standing', outdir=rdir)
    p0 = T.dominant_period([d['eps_site'] for d in h_ref], T.DT)
    if p0 is None:
        print("No dominant period found in the standing series; aborting.")
        return
    print(f"Measured natural period P0 = {p0:.4f}")

    # 2. Drive at phi*P0 (original positive)
    h_phi = T.run_case(solver, 'standing', drive_period=PHI * p0, outdir=rdir)

    # 3. Drive at e*P0 (non-phi counterfactual, same amplitude)
    h_alt = T.run_case(solver, 'standing', drive_period=np.e * p0, outdir=rdir)

    ref = T.summarize('ref', h_ref)
    phi = T.summarize('phi', h_phi)
    alt = T.summarize('alt', h_alt)

    results = {
        'meta': {'P0': p0, 'T_phi': PHI * p0, 'T_alt': np.e * p0,
                 'drive_amp': T.DRIVE_AMP},
        'undriven': ref,
        'drive_phi': phi,
        'drive_alt': alt,
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== DRIVE-FREQUENCY COMPARISON ===")
    print(f"undriven      : eps_rel={ref['eps_rel']:.3f} "
          f"q_gap={ref['q_gap']:+.3f} "
          f"displ {ref['displ_start']:.2f}->{ref['displ_end']:.2f}")
    print(f"drive phi*P0  : eps_rel={phi['eps_rel']:.3f} "
          f"q_gap={phi['q_gap']:+.3f} "
          f"displ {phi['displ_start']:.2f}->{phi['displ_end']:.2f}")
    print(f"drive e*P0    : eps_rel={alt['eps_rel']:.3f} "
          f"q_gap={alt['q_gap']:+.3f} "
          f"displ {alt['displ_start']:.2f}->{alt['displ_end']:.2f}")

    relax_phi = phi['eps_rel'] < ref['eps_rel'] - 0.05
    relax_alt = alt['eps_rel'] < ref['eps_rel'] - 0.05
    if relax_phi and not relax_alt:
        print("*** PHI-SPECIFIC: the phi-phased drive relaxes the site; "
              "the non-phi drive does not. ***")
    elif relax_phi and relax_alt:
        print("NON-SPECIFIC: both drives relax the site—the effect is "
              "stirring, not phi-resonance.")
    elif not relax_phi:
        print("REPRODUCTION FAILED: the phi-drive effect did not reproduce "
              "in this run.")
    else:
        print("AMBIGUOUS.")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
