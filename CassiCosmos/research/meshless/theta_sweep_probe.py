#!/usr/bin/env python
"""theta-sweep probe (pre-registered, theta_sweep_prereg.md).

Tests whether the per-node density-aware law's deviation from the per-source
density-aware direct sum vanishes as theta->0, and at which theta it crosses
the frozen G17 threshold (median <= 1e-2). Reuses the local 'current' walk
from leafsoft_probe (which reproduces the GPU to 3.8e-7).

Frozen sweep: theta in {0.5,0.4,0.3,0.25,0.2,0.15,0.1,0.05}, the same dense
8192 config (_diag/fmm_gpu.json), current per-node law walk vs
direct_force(..., density_aware=True). If no crossing at 0.05, extend to
{0.02,0.01}.

Run:  python research/meshless/theta_sweep_probe.py  (from the repo root)
"""
import base64
import json
import numpy as np

from stage5_fmm import BHOctree, chord_weight_from_field, direct_force
from leafsoft_probe import _walk  # current-mode walk (local, unchanged)


def _median_rel_err(a, ref):
    mag_ref = np.linalg.norm(ref, axis=1)
    flo = 1e-4 * np.median(mag_ref)
    keep = mag_ref > flo
    err = np.linalg.norm(a - ref, axis=1) / np.maximum(mag_ref, 1e-12)
    return float(np.median(err[keep])), int(keep.sum())


def main():
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

    thetas = [0.5, 0.4, 0.3, 0.25, 0.2, 0.15, 0.1, 0.05]
    print("theta-sweep: current per-node law vs per-source density-aware direct")
    print("%-8s %-16s %s" % ("theta", "median_err", "cross<1e-2"))
    rows = []
    for th in thetas:
        a = _walk(tree, pos, th, eps2, mode='current')
        med, n_keep = _median_rel_err(a, a_direct)
        rows.append((th, med))
        print("%-8.3f %-16.3e %s" % (th, med, "YES" if med <= 1e-2 else "no"))

    # crossing
    cross = [th for th, med in rows if med <= 1e-2]
    if cross:
        th_star = cross[-1]  # smallest theta with med<=1e-2 (list is decreasing theta)
        print("CROSSING: theta* = %.3f (median_err <= 1e-2)" % th_star)
        verdict = "SUPPORTS_re-scope-to-smaller-theta" if th_star >= 0.1 \
            else "SUPPORTS_convergence-as-such"
    elif rows[-1][1] > 1e-2:
        # extend to 0.02, 0.01
        print("no crossing at 0.05 -> extend to {0.02, 0.01}")
        for th in (0.02, 0.01):
            a = _walk(tree, pos, th, eps2, mode='current')
            med, n_keep = _median_rel_err(a, a_direct)
            rows.append((th, med))
            print("%-8.3f %-16.3e %s" % (th, med, "YES" if med <= 1e-2 else "no"))
        smallest = rows[-1][1]
        n_all = len(rows)
        mono = all(rows[i][1] <= rows[i-1][1] for i in range(1, n_all))
        print("CROSSING: none in sweep range; smallest_median=%.3e mono_decreasing=%s"
              % (smallest, mono))
        verdict = ("SUPPORTS_convergence-as-such" if smallest < 5e-2 and mono
                   else ("CONTRADICTS" if not mono or smallest > 0.05 else
                         "SUPPORTS_convergence-as-such"))
    else:
        verdict = "SUPPORTS_convergence-as-such"

    print("VERDICT: %s" % verdict)
    return rows, verdict


if __name__ == "__main__":
    main()
