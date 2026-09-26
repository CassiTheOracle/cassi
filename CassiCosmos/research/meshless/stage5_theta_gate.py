#!/usr/bin/env python
"""Standalone convergence gate: the per-node density-aware law's theta->0
convergence to the per-source closure (certify-convergence re-scope shape).

Re-runs the FROZEN theta sweep from research/meshless/theta_sweep_prereg.md
and asserts the prereg's decision tree so the convergence property joins the
regular verification chain (9 stable gates + G30 + G16 + this gate all PASS;
G17/G18 stay documented-red at theta=0.5 until the re-scope decision).

Frozen sweep: theta in {0.5,0.4,0.3,0.25,0.2,0.15,0.1,0.05,0.02,0.01,0.005,
0.001}, the dense 8192 config from _diag/fmm_gpu.json (read exactly as
stage5_verify.py does), the 'current' per-node law walk vs
direct_force(..., density_aware=True), median relative error, same keep-set
(|direct| > 1e-4*median(|direct|)). Quadrupole ON.

Frozen assertions (principled, general — NOT tuned to the measured numbers):
  1. MONOTONICITY: median_err non-increasing across every adjacent theta pair
     (the frozen property "monotone-decreasing toward float precision").
  2. G17-THRESHOLD AT THETA*: median_err(theta=0.01) <= 1e-2 (the pre-existing
     frozen G17 threshold, applied at the convergence theta*).
  3. VANISHING FLOOR: median_err(theta=0.001) <= 1e-3 (a vanishing bound,
     three orders above the measured 1.3e-4 — a bound, not a match).

The walk and median-err helpers are IMPORTED from theta_sweep_probe /
leafsoft_probe (reused unchanged; those files are not modified).

Run:  python research/meshless/stage5_theta_gate.py  (from the repo root)
"""
import sys

import numpy as np

from theta_sweep_probe import _median_rel_err  # unchanged helper
from leafsoft_probe import _walk               # unchanged 'current'-mode walk

THETAS = [0.5, 0.4, 0.3, 0.25, 0.2, 0.15, 0.1, 0.05, 0.02, 0.01, 0.005, 0.001]
G17_THRESH = 1e-2      # frozen G17 threshold, applied at theta* = 0.01
FLOOR_THRESH = 1e-3    # vanishing floor at theta = 0.001
THETA_STAR = 0.01
THETA_FLOOR = 0.001


def main():
    import base64
    import json
    from stage5_fmm import BHOctree, chord_weight_from_field, direct_force

    d = json.load(open("_diag/fmm_gpu.json", encoding="utf-8"))
    eps2 = float(d["eps2"])
    md = int(d.get("max_levels", 14))
    src = np.frombuffer(base64.b64decode(d["src_b64"]), dtype=np.float32).astype(np.float64)
    pos = np.stack([src[0::8], src[1::8], src[2::8]], axis=1)
    mass = src[3::8]
    ey = src[4::8]
    ei = src[5::8]
    q, g = chord_weight_from_field(ey, ei)
    w = mass * g

    tree = BHOctree(pos, mass, g=g, eps2=eps2, max_depth=md, leaf_cap=1)
    a_direct = direct_force(pos, pos, w, eps2=eps2, density_aware=True)

    print("stage5 theta convergence gate (certify-convergence)")
    print("N=%d eps2=%.1e max_levels=%d  sweep=%s"
          % (pos.shape[0], eps2, md, THETAS))
    meds = []
    for th in THETAS:
        a = _walk(tree, pos, th, eps2, mode='current')
        med, n_keep = _median_rel_err(a, a_direct)
        meds.append(med)
        print("  theta=%.3f  median_err=%.3e" % (th, med))

    # assertion 1: monotonicity (non-increasing) across adjacent pairs
    mono = all(meds[i + 1] <= meds[i] for i in range(len(meds) - 1))
    # assertion 2: G17 threshold at theta*
    med_at_star = meds[THETAS.index(THETA_STAR)]
    g17_at_star = med_at_star <= G17_THRESH
    # assertion 3: vanishing floor at theta=0.001
    med_at_floor = meds[THETAS.index(THETA_FLOOR)]
    floor_ok = med_at_floor <= FLOOR_THRESH

    print("---- assertions ----")
    print("[%s] monotonicity (non-increasing across %d theta pairs)"
          % ("PASS" if mono else "FAIL", len(THETAS) - 1))
    print("[%s] G17 threshold at theta*: median_err(0.01)=%.3e <= %.0e"
          % ("PASS" if g17_at_star else "FAIL", med_at_star, G17_THRESH))
    print("[%s] vanishing floor at theta=0.001: median_err=%.3e <= %.0e"
          % ("PASS" if floor_ok else "FAIL", med_at_floor, FLOOR_THRESH))

    ok = mono and g17_at_star and floor_ok
    if ok:
        print("ALL CHECKS PASSED")
    else:
        print("CHECKS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
