#!/usr/bin/env python
"""Leaf-only density-aware softening probe (pre-registered, leafsoft_prereg.md).

Tests the hypothesis that applying the density-aware softening eps2_node =
eps2 + W^(2/3) ONLY to leaves (childCount == 0, incl. max-depth-capped cells
holding coincident sources) while internal accepted nodes keep the global
eps2 restores theta-consistency — the tree approximates the direct O(N^2)
sum again at the frozen G17/G18 thresholds — while preserving the two-body
heating protection on the heavy capped leaf cells.

The leaf-only walk is implemented LOCALLY here against the stage5_fmm
BHOctree (tree building + node arrays reused; the walk variants are defined
in this module). No existing consumer or the shader is modified.

Frozen arm (see leafsoft_prereg.md): N=8192, theta=0.5, eps2=1e-6,
leaf_cap=1, max_levels=14, quadrupole ON, from _diag/fmm_gpu.json read
exactly as stage5_verify.py does. References: the proto tree on the same
points (g, eps2, max_depth), and direct_force(..., density_aware=True).

Run:  python research/meshless/leafsoft_probe.py  (from the repo root)
"""
import base64
import json
import numpy as np

from stage5_fmm import (BHOctree, chord_weight_from_field, direct_force,
                        _qmv, _qd)


# ─────────────────────────────────────────────────────────────────────────
# Walk variants — mirror cassi_tree_gravity.glsl acceptance + softening
# ─────────────────────────────────────────────────────────────────────────
def _walk(tree, targets, theta, eps2, mode):
    """mode: 'current' = per-node W^(2/3) softening on every accepted node
    (the failing 4ce2912 law); 'leaf' = W^(2/3) on leaves only, global eps2
    on internal accepted nodes. Both apply to monopole AND quadrupole paths
    (shader :146/:167). Returns acc (T,3)."""
    targets = np.asarray(targets, dtype=np.float64)
    T = targets.shape[0]
    acc = np.zeros((T, 3))
    t_ids = np.arange(T)
    n_ids = np.zeros(T, dtype=np.int64)
    while t_ids.size:
        c = tree.node_com[n_ids]
        d = targets[t_ids] - c
        ds2 = (d * d).sum(1)
        sep = np.sqrt(ds2)
        half = tree.node_half[n_ids]
        is_leaf = (tree.node_child[n_ids] < 0).all(1)
        contains = (np.abs(targets[t_ids] - c) <= half[:, None]).all(1)
        open_mask = (((half / np.maximum(sep, 1e-300) > theta) | contains)
                     & ~is_leaf)
        acc_set = ~open_mask
        if acc_set.any():
            idx = np.nonzero(acc_set)[0]
            tt = t_ids[idx]
            nn = n_ids[idx]
            dd = d[idx]
            Wn = tree.node_W[nn]
            if mode == 'leaf':
                # eps2_node = eps2 + W^(2/3) iff leaf, else global eps2
                eps2n = np.where(is_leaf[idx],
                                 eps2 + _W23(Wn), eps2)
            else:  # 'current': every accepted node softened
                eps2n = eps2 + _W23(Wn)
            Rr = np.sqrt(ds2[idx] + eps2n)
            monop = -Wn[:, None] * dd / Rr[:, None] ** 3
            add = monop
            Q = tree.node_Q[nn]
            ds2a = (dd * dd).sum(1)
            qd = _qd(Q, dd)
            Qd = _qmv(Q, dd)
            R2 = ds2a + eps2n
            R7 = R2 ** 3.5
            quadc = (R2[:, None] * Qd - 2.5 * qd[:, None] * dd) / R7[:, None]
            add = monop + quadc
            self_leaf = is_leaf[idx] & (tree.node_ps[nn] == tt)
            add[self_leaf] = 0.0
            np.add.at(acc, tt, add)
        if not open_mask.any():
            break
        oset = np.nonzero(open_mask)[0]
        ot = t_ids[oset]
        on = n_ids[oset]
        ch = tree.node_child[on]
        ex = np.nonzero(ch >= 0)
        t_ids = ot[ex[0]]
        n_ids = ch[ex[0], ex[1]]
        if t_ids.size == 0:
            break
    return acc


def _W23(W):
    # same floor as the shader's exp((2/3)·log(max(W,1e-30)))
    return np.exp((2.0 / 3.0) * np.log(np.maximum(W, 1e-30)))


def _rel_err_keep(a, ref, floor_scale=1e-4):
    mag_ref = np.linalg.norm(ref, axis=1)
    flo = floor_scale * np.median(mag_ref)
    keep = mag_ref > flo
    err = np.linalg.norm(a - ref, axis=1) / np.maximum(mag_ref, 1e-12)
    return err[keep]


def _report(name, a, ref, thresh_med, note=""):
    keepmag = np.linalg.norm(ref, axis=1)
    flo = 1e-4 * np.median(keepmag)
    keep = keepmag > flo
    err = np.linalg.norm(a - ref, axis=1) / np.maximum(keepmag, 1e-12)
    e = err[keep]
    med = float(np.median(e))
    p99 = float(np.percentile(e, 99))
    print("%-34s median=%.3e 99th=%.3e  (target med<=%.0e)  %s"
          % (name, med, p99, thresh_med, note))
    return med, p99


def main():
    d = json.load(open("_diag/fmm_gpu.json", encoding="utf-8"))
    N = int(d["N"])
    theta = float(d["theta"])
    eps2 = float(d["eps2"])
    md = int(d.get("max_levels", 14))
    src = np.frombuffer(base64.b64decode(d["src_b64"]), dtype=np.float32).astype(np.float64)
    forces = np.frombuffer(base64.b64decode(d["forces_b64"]), dtype=np.float32).astype(np.float64)
    pos = np.stack([src[0::8], src[1::8], src[2::8]], axis=1)
    mass = src[3::8]
    ey = src[4::8]
    ei = src[5::8]
    q, g = chord_weight_from_field(ey, ei)
    w = mass * g
    a_gpu = np.stack([forces[0::4], forces[1::4], forces[2::4]], axis=1)

    print("leaf-only probe: N=%d theta=%.2f eps2=%.1e max_levels=%d"
          % (N, theta, eps2, md))

    tree = BHOctree(pos, mass, g=g, eps2=eps2, max_depth=md, leaf_cap=1)
    a_direct = direct_force(pos, pos, w, eps2=eps2, density_aware=True)

    a_leaf = _walk(tree, pos, theta, eps2, mode='leaf')
    a_cur = _walk(tree, pos, theta, eps2, mode='current')

    print("=== G17 leaf-only tree vs density-aware direct ===")
    med17, p9917 = _report("G17 leaf-only tree vs direct",
                           a_leaf, a_direct, 1e-2, note="GATED")

    print("=== G18 self-exclusion (leaf-only tree vs direct) ===")
    mag_direct = np.linalg.norm(a_direct, axis=1)
    floor18 = 1e-4 * np.median(mag_direct)
    resid = np.linalg.norm(a_leaf - a_direct, axis=1) / np.maximum(mag_direct, floor18)
    resid_kept = resid[mag_direct > floor18]
    med18 = float(np.median(resid_kept))
    p999 = float(np.percentile(resid_kept, 99.9))
    n_over = int((resid_kept > 0.1).sum())
    print("[G18] leaf-only  median=%.3e  99.9th=%.3e  max=%.3e  (n>0.1: %d/%d)"
          % (med18, p999, float(resid_kept.max()), n_over, resid_kept.size))

    print("=== informational (NOT gated) ===")
    _report("leaf-only tree vs GPU dump", a_leaf, a_gpu, 5e-3,
            note="informing: how leaf-only diverges from the current GPU law")
    _report("current per-node law vs direct (baseline)", a_cur, a_direct, 1e-2,
            note="informing: the known-failing 4ce2912-law baseline")

    print("---- gate ----")
    g17 = med17 <= 1e-2
    g18 = (med18 <= 0.01) and (p999 <= 0.5)
    print("[%s] G17 (leaf-only tree vs direct)  med=%.3e" % ("PASS" if g17 else "FAIL", med17))
    print("[%s] G18 (leaf-only)  med=%.3e  p999=%.3e" % ("PASS" if g18 else "FAIL", med18, p999))
    if g17 and g18:
        verdict = "SUPPORTS"
    elif (not g17) and (not g18):
        verdict = "CONTRADICTS"
    else:
        verdict = "INCONCLUSIVE"
    print("VERDICT: %s" % verdict)
    return verdict, med17, p9917, med18, p999


if __name__ == "__main__":
    main()
