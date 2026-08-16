#!/usr/bin/env python
"""stage5b — meshless TREE gravity integration gates (wave 3).

Reads the GPU dump (verify_meshless_gravity.gd) and checks:
  G31 — the per-particle tree gradient has no NaN/Inf and every target is
        inside the sim box (the walk read particle positions via _pos_buf).
  G30 — the GPU per-particle tree gradient vs the stage5_fmm prototype tree
        built on the SAME gathered sources (the mode-7 gather recipe is
        re-implemented here in numpy from the planted field/rho/vol and the
        site positions), evaluated at the SAME (particle) targets.
        median relative force error <= 1e-2.

The gather recipe (cassi_tree_build.glsl mode 7, documented in the shader):
    V_s            = max(vol[s], 1e-12)
    rho_field      = ey[s] + ei[s]
    m_s            = rho_mass(site's grid cell) * V_s
                     + max(rho_field * V_s, field_floor * V_s)
    q_coh          = rho²/(rho² + phi^-2 + eps²),  rho=ey+ei, eps=ey-phi*ei
    g_s            = 1 + (phi⁶ − 1) * q_coh
    w_s            = m_s * g_s
and the tree's force at a target is a = -∇Phi_g with w_s as the source
weight (G absorbed). The GPU walk writes _ml_tree_grad = the SAME a(r)
(attractive), so G30 compares GPU tree_grad vs prototype.force() directly.

Usage: python stage5b_verify.py _diag/meshless_gravity_gpu.json
       (run from the space-sim repo root)

Force-law note (density-aware softening, commit 4ce2912, 2026-08-16): the
producing GPU shader (scripts/verify_meshless_gravity.gd ->
cassi_tree_gravity.glsl) softens each accepted node by eps2_node = eps2 +
W^(2/3). This gate's prototype tree (stage5_fmm.BHOctree) runs with
density_aware=True so G30 models the CURRENT law; the G30 threshold is
unchanged. The force law changed in 4ce2912; this gate models it here.
"""
import base64
import json
import sys

import numpy as np

from stage5_fmm import BHOctree


def _f32(b64, n, per):
    a = np.frombuffer(base64.b64decode(b64), dtype=np.float32)
    return a[: n * per].astype(np.float64)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "_diag/meshless_gravity_gpu.json"
    d = json.load(open(path))
    Np = int(d["Np"]); nsrc = int(d["nsrc"]); N = int(d["N"])
    phi = float(d["phi"]); xi = float(d["xi"])
    eps2 = float(d["eps2"]); theta = float(d["theta"])
    leaf_cap = int(d["leaf_cap"]); max_levels = int(d["max_levels"])
    floor = float(d["field_floor"])
    ext = np.array([d["extent_x"], d["extent_y"], d["extent_z"]], dtype=np.float64)
    h = 2.0 * ext / float(N)

    sites = _f32(d["sites_b64"], nsrc, 4).reshape(-1, 4)[:, :3]
    ey = _f32(d["ey_b64"], nsrc, 1)
    ei = _f32(d["ei_b64"], nsrc, 1)
    vol = _f32(d["vol_b64"], nsrc, 1)
    rho = _f32(d["rho_b64"], N * N * N, 1).reshape(N, N, N)
    pos = _f32(d["pos_b64"], Np, 4).reshape(-1, 4)[:, :3]
    grad = _f32(d["grad_b64"], Np, 4).reshape(-1, 4)[:, :3]
    icount = np.frombuffer(base64.b64decode(d["icount_b64"]), dtype=np.int32)[:Np]

    print("stage5b meshless tree verify: N=%d Np=%d nsrc=%d node_count=%d theta=%.2f eps2=%.1e"
          % (N, Np, nsrc, int(d["node_count"]), theta, eps2))

    # ── G31: no NaN/Inf; targets in-box ────────────────────────────────
    nan_inf = (not np.isfinite(grad).all()) or (not np.isfinite(pos).all())
    in_box = (np.abs(pos) <= ext[None, :] + 1e-6).all(1)
    print("=== G31: walk output sanity ===")
    print("[G31] finite: %s   targets in-box: %d/%d   interactions min=%d"
          % ("OK" if not nan_inf else "FAIL", int(in_box.sum()), Np,
             int(icount.min()) if Np else 0))
    g31 = (not nan_inf) and bool(in_box.all())

    # ── GATHER (re-implement the mode-7 source-mass recipe) ────────────
    # site -> grid cell (leapfrog convention: gi = floor(sp.x/hx) % N)
    gc = np.clip(np.floor(sites / h[None, :]).astype(np.int64), 0, N - 1)
    rho_at = rho[gc[:, 0], gc[:, 1], gc[:, 2]]
    rho_f = ey + ei
    V = np.maximum(vol, 1e-12)
    mfield = np.maximum(rho_f * V, floor * V)
    mass = rho_at * V + mfield
    # chord weight g = 1 + (xi−1)·q_coh
    eps_c = ey - phi * ei
    q = (rho_f * rho_f) / (rho_f * rho_f + phi ** -2 + eps_c * eps_c)
    g = 1.0 + (xi - 1.0) * q
    w = mass * g
    print("=== gather (recipe) ===")
    print("[gather] nsrc=%d  mass median=%.3e (rho term=%.3e, field term=%.3e)"
          % (nsrc, np.median(mass), np.median(rho_at * V), np.median(mfield)))

    # prototype tree on the SAME sources/targets
    tree = BHOctree(sites, mass, g=g, leaf_cap=leaf_cap, eps2=eps2,
                      max_depth=max_levels, density_aware=True)
    a_proto = tree.force(pos, theta=theta, quad=True)
    mag_gpu = np.linalg.norm(grad, axis=1)
    floor30 = 1e-4 * np.median(mag_gpu) if mag_gpu.size else 0.0
    resid = np.linalg.norm(grad - a_proto, axis=1) / np.maximum(mag_gpu, floor30)
    keep = mag_gpu > floor30
    med = float(np.median(resid[keep])) if keep.any() else float("nan")
    p99 = float(np.percentile(resid[keep], 99)) if keep.any() else float("nan")
    print("=== G30: GPU tree grad vs prototype tree (same sources/targets) ===")
    print("[G30] median=%.3e  99th=%.3e  (target median <= 1e-2)" % (med, p99))
    g30 = (not np.isnan(med)) and med <= 1e-2

    print("---- gate ----")
    print("[%s] G31 sanity  nan=%s inbox=%s" % ("PASS" if g31 else "FAIL", nan_inf, bool(in_box.all())))
    print("[%s] G30 GPU vs proto tree  med=%.3e" % ("PASS" if g30 else "FAIL", med))
    print("RESULT: " + ("ALL PASS" if (g30 and g31) else "FAILURES PRESENT"))
    sys.exit(0 if (g30 and g31) else 1)


if __name__ == "__main__":
    main()
