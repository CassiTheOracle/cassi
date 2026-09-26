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

G61/G62 site-target measurements are printed from the same dump as a
research diagnostic. They belong to the rejected site-target arm and do not
change this established G30/G31 production integration gate's exit status.

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


def _nearest_site_indices(pos, sites, k=1, chunk=128):
    """Exact Euclidean owner/neighborhood map without scipy."""
    shape = (pos.shape[0],) if k == 1 else (pos.shape[0], k)
    out = np.empty(shape, dtype=np.int64)
    for start in range(0, pos.shape[0], chunk):
        stop = min(start + chunk, pos.shape[0])
        delta = pos[start:stop, None, :] - sites[None, :, :]
        d2 = np.einsum("csi,csi->cs", delta, delta)
        if k == 1:
            out[start:stop] = np.argmin(d2, axis=1)
        else:
            picked = np.argpartition(d2, k - 1, axis=1)[:, :k]
            order = np.argsort(np.take_along_axis(d2, picked, axis=1), axis=1)
            out[start:stop] = np.take_along_axis(picked, order, axis=1)
    return out


def _fidelity_metrics(sampled, reference, q_owner, mass_owner):
    base_mag = np.linalg.norm(reference, axis=1)
    keep = base_mag > 1e-8
    rel = np.linalg.norm(sampled - reference, axis=1) / np.maximum(base_mag, 1e-8)
    med = float(np.median(rel[keep])) if keep.any() else float("nan")
    p99 = float(np.percentile(rel[keep], 99)) if keep.any() else float("nan")
    high_q = keep & (q_owner >= np.percentile(q_owner, 75))
    high_mass = keep & (mass_owner >= np.percentile(mass_owner, 75))
    med_q = float(np.median(rel[high_q])) if high_q.any() else float("nan")
    med_mass = float(np.median(rel[high_mass])) if high_mass.any() else float("nan")
    opposite = float(np.mean(np.einsum(
        "ij,ij->i", sampled[keep], reference[keep]) < 0.0)) if keep.any() else 1.0
    passed = (
        np.isfinite([med, p99, med_q, med_mass, opposite]).all()
        and med <= 1e-2 and p99 <= 5e-2
        and med_q <= 1e-2 and med_mass <= 1e-2
        and opposite <= 1e-3
    )
    return passed, med, p99, med_q, med_mass, opposite, int((~keep).sum())




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
    site_grad = _f32(d["site_grad_b64"], nsrc, 4).reshape(-1, 4)[:, :3]

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

    # ── G61: site field interpolation ladder (Amendment A) ────────────
    knn = _nearest_site_indices(pos, sites, k=16)
    owner = knn[:, 0]
    q_owner = q[owner]
    mass_owner = mass[owner]
    sampled_nearest = site_grad[owner]
    nearest_metrics = _fidelity_metrics(
        sampled_nearest, grad, q_owner, mass_owner)

    knn8 = knn[:, :8]
    delta8 = pos[:, None, :] - sites[knn8]
    d2_8 = np.einsum("nki,nki->nk", delta8, delta8)
    weights8 = 1.0 / np.maximum(d2_8, 1e-12)
    weights8 /= weights8.sum(axis=1, keepdims=True)
    sampled_a1 = np.einsum("nk,nki->ni", weights8, site_grad[knn8])
    a1_metrics = _fidelity_metrics(sampled_a1, grad, q_owner, mass_owner)

    sampled_a2 = np.empty_like(grad)
    for particle_i, ids in enumerate(knn):
        center = sites[ids[0]]
        design = np.column_stack((
            np.ones(ids.size, dtype=np.float64),
            sites[ids] - center[None, :],
        ))
        coeff, _, _, _ = np.linalg.lstsq(design, site_grad[ids], rcond=None)
        sample_row = np.concatenate(([1.0], pos[particle_i] - center))
        sampled_a2[particle_i] = sample_row @ coeff
    a2_metrics = _fidelity_metrics(sampled_a2, grad, q_owner, mass_owner)

    selected_name = "A1-IDW8" if a1_metrics[0] else "A2-affine16"
    selected = a1_metrics if a1_metrics[0] else a2_metrics
    g61, med61, p9961, med_q61, med_m61, opposite61, excluded61 = selected
    print("=== G61: site-target interpolation fidelity ===")
    for label, metrics in (
            ("nearest", nearest_metrics), ("A1-IDW8", a1_metrics),
            ("A2-affine16", a2_metrics)):
        print("[G61:%s] %s med=%.3e p99=%.3e high-q-med=%.3e high-mass-med=%.3e opposite=%.3e excluded=%d"
              % (label, "PASS" if metrics[0] else "FAIL", *metrics[1:]))
    print("[G61] selected=%s" % selected_name)

    # ── G62: synchronized local-RD walk cost ───────────────────────────
    p_times = np.asarray(d["particle_walk_us"], dtype=np.float64)
    s_times = np.asarray(d["site_walk_us"], dtype=np.float64)
    p_med = float(np.median(p_times)) if p_times.size else float("nan")
    s_med = float(np.median(s_times)) if s_times.size else float("nan")
    ratio62 = s_med / p_med if p_med > 0.0 else float("inf")
    site_finite = bool(np.isfinite(site_grad).all())
    g62 = site_finite and np.isfinite(ratio62) and ratio62 <= 0.25
    print("=== G62: site-target walk cost ===")
    print("[G62] particle(%d) median=%.1f us site(%d) median=%.1f us ratio=%.4f finite=%s"
          % (int(d["perf_particle_count"]), p_med, int(d["perf_site_count"]), s_med,
             ratio62, site_finite))
    print("[G62] particle samples=%s" % p_times.astype(np.int64).tolist())
    print("[G62] site samples=%s" % s_times.astype(np.int64).tolist())

    production_passed = g30 and g31
    site_target_passed = g61 and g62
    print("---- production integration gate ----")
    print("[%s] G31 sanity  nan=%s inbox=%s" % ("PASS" if g31 else "FAIL", nan_inf, bool(in_box.all())))
    print("[%s] G30 GPU vs proto tree  med=%.3e" % ("PASS" if g30 else "FAIL", med))
    print("PRODUCTION RESULT: " + ("ALL PASS" if production_passed else "FAILURES PRESENT"))
    print("---- rejected site-target research diagnostic ----")
    print("[%s] G61 site-target fidelity med=%.3e p99=%.3e" % ("PASS" if g61 else "FAIL", med61, p9961))
    print("[%s] G62 site-target walk ratio=%.4f" % ("PASS" if g62 else "FAIL", ratio62))
    print("SITE-TARGET VERDICT: " + ("G61/G62 PASS" if site_target_passed else "REJECT"))
    sys.exit(0 if production_passed else 1)


if __name__ == "__main__":
    main()
