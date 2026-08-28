#!/usr/bin/env python
"""Stage 7 — φ-native FMM prototype (phi_fmm_design.md).

Asks whether the tree itself can carry the Cassi cascade: multipole levels
spaced at φ-rungs (half_d = half_0·φ⁻ᵈ) and a de-resonance opening
(φ-irrational level radii) instead of the standard binary octree.

Imports stage5_fmm (BHOctree, direct_force, pair_energy, the G13/G15 source
machinery) UNMODIFIED — this prototype adds:

  PhiTree   — a Barnes-Hut tree with φ-contracting children (child half =
              parent_half/φ, 8 overlapping children, nearest-center
              assignment). Rational arm: φ⁻¹ ≈ 5/8 for the Fibonacci
              convergent. Honest consequences vs Morton (design doc (a)).

Gates:
  G42 — median force error vs direct at EQUAL interaction budget, comparing
        {standard octree, φ-tree irrational, φ-tree rational}. Report which
        wins; a null (standard) is honest.
  G43 — force anisotropy (ring metric) on a lattice-symmetric source: max|a|
        / min|a| around a ring. The whole point is less grid bias — measure
        it for the standard octree vs the φ-tree.
  G44 — energy drift in the G15 bound-cluster test (truncated Plummer,
        ~12 crossing times) with the φ-tree <= the standard octree's, or
        honestly reported.

Run:  python stage7_phi_fmm.py        (~2-4 min)
"""
import time
import numpy as np

from stage5_fmm import (PHI, G, BHOctree, direct_force, pair_energy,
                        chord_weight_from_field, gen_sources, gen_field,
                        _plummer_pos, _rel_err)

PHI_INV = 1.0 / PHI          # φ⁻¹ = 0.618034
RATIO_RATIONAL = 5.0 / 8.0   # Fibonacci convergent to 1/φ (0.625)


# ═════════════════════════════════════════════════════════════════════════
# φ-tree: levels at φ-rungs, 8 overlapping children, nearest-center assign
# ═════════════════════════════════════════════════════════════════════════
class PhiTree:
    """φ-spaced Barnes-Hut. Node arrays mirror BHOctree (node_ctr/half/W/com/
    Q/ps/pe/child) so the force walk uses the same monopole+quadrupole
    formulas — only the CHILD GEOMETRY and the OPENING are φ-native.

    A node of half h splits into 8 children each of half h/φ, centered at
    c + s·h·(1−1/φ), s∈{±1}³. Because 2/φ = 1.236 ≠ 2 the children OVERLAP
    (overfill the parent volume); each source is assigned to the NEAREST
    child center. level_idx enables the rational arm (contraction = ratio
    instead of φ⁻¹). No Morton/integer hashing — see phi_fmm_design.md (a).
    """
    def __init__(self, pos, mass, g=None, leaf_cap=1, eps2=0.0, max_depth=40,
                 ratio=PHI_INV):
        self.pos = np.asarray(pos, dtype=np.float64)
        self.mass = np.asarray(mass, dtype=np.float64)
        n = self.pos.shape[0]
        self.w = self.mass * (np.asarray(g, dtype=np.float64) if g is not None
                              else np.ones(n))
        self.eps2 = eps2
        self.leaf_cap = leaf_cap
        self.ratio = ratio                 # φ⁻¹ irrational, or 5/8 rational
        self.max_depth = max_depth
        lo = self.pos.min(0); hi = self.pos.max(0)
        self.ctr = 0.5 * (lo + hi)
        self.half = 0.5 * (hi - lo).max() + 1e-9
        cap = 8 * n + 64
        self.nc = 0
        self.node_ctr = np.empty((cap, 3)); self.node_half = np.empty(cap)
        self.node_W = np.empty(cap);        self.node_com = np.empty((cap, 3))
        self.node_Q = np.empty((cap, 6));   self.node_ps = np.empty(cap, np.int64)
        self.node_pe = np.empty(cap, np.int64)
        self.node_child = np.full((cap, 8), -1, np.int64)
        self._p2n(self.ctr, self.half, np.arange(n), 0)
        for nm in ["node_ctr", "node_half", "node_W", "node_com", "node_Q",
                   "node_ps", "node_pe"]:
            setattr(self, nm, getattr(self, nm)[:self.nc])
        self.node_child = self.node_child[:self.nc]

    def _p2n(self, ctr, half, idx, depth):
        ci = self.nc; self.nc += 1
        self.node_ctr[ci] = ctr; self.node_half[ci] = half
        self.node_ps[ci] = idx[0]; self.node_pe[ci] = idx[-1] + 1
        m = self.pos[idx]; wv = self.w[idx]
        W = wv.sum(); self.node_W[ci] = W
        com = (wv[:, None] * m).sum(0) / max(W, 1e-300)
        self.node_com[ci] = com
        xi = m - com
        xx, yy, zz = xi[:, 0], xi[:, 1], xi[:, 2]
        r2 = (xi * xi).sum(1)
        self.node_Q[ci] = np.array([
            (wv * (3.0 * xx * xx - r2)).sum(),
            (wv * (3.0 * xx * yy)).sum(),
            (wv * (3.0 * xx * zz)).sum(),
            (wv * (3.0 * yy * yy - r2)).sum(),
            (wv * (3.0 * yy * zz)).sum(),
            (wv * (3.0 * zz * zz - r2)).sum()])
        if len(idx) <= self.leaf_cap or depth >= self.max_depth:
            return ci
        r = self.ratio                      # contraction per level
        hphi = r * half                     # child half = half·r (φ⁻¹ or 5/8)
        sg = np.array([-1.0, 1.0])
        # 8 child centers at the φ-contracted octant corners
        off = np.array([[sg[(b >> 2) & 1], sg[(b >> 1) & 1], sg[b & 1]]
                        for b in range(8)]) * (half - hphi)
        cidx = np.arange(len(idx))
        d2 = ((self.pos[idx, None, :] - ctr[None, None, :] -
               off[None, :, :]) ** 2).sum(2)       # (P, 8)
        owner = d2.argmin(1)                        # nearest child center
        keep = np.arange(len(idx))
        for b in range(8):
            sub = idx[keep[owner == b]]
            if sub.size:
                self.node_child[ci, b] = self._p2n(ctr + off[b], hphi, sub, depth + 1)
        return ci

    # ── wavefront force walk (mirrors BHOctree.force; φ-opening) ────────
    def force(self, targets, theta=0.6, pot=False, quad=True):
        targets = np.asarray(targets, dtype=np.float64)
        T = targets.shape[0]
        acc = np.zeros((T, 3)); potv = np.zeros(T) if pot else None
        t_ids = np.arange(T)
        n_ids = np.zeros(T, dtype=np.int64)
        ninter = 0
        while t_ids.size:
            c = self.node_com[n_ids]
            d = targets[t_ids] - c
            ds2 = (d * d).sum(1); R = np.sqrt(ds2 + self.eps2)
            sep = np.sqrt(ds2); half = self.node_half[n_ids]
            is_leaf = (self.node_child[n_ids] < 0).all(1)
            contains = (np.abs(targets[t_ids] - c) <= half[:, None]).all(1)
            # φ-opening: half_d/sep > theta   (half_d is the φ-rung level)
            open_mask = (((half / np.maximum(sep, 1e-300) > theta) | contains)
                         & ~is_leaf)
            acc_set = ~open_mask
            if acc_set.any():
                ai = np.nonzero(acc_set)[0]
                tt, nn = t_ids[ai], n_ids[ai]
                dd = d[ai]; Wn = self.node_W[nn]
                monop = -G * Wn[:, None] * dd / (R[ai][:, None] ** 3)
                add = monop
                if quad:
                    Q = self.node_Q[nn]
                    qd = _qinprod(Q, dd); Qd = _qdot(Q, dd)
                    R2 = np.maximum((dd * dd).sum(1), 1e-30); R7 = R2 ** 3.5
                    add = monop + (R2[:, None] * Qd - 2.5 * qd[:, None] * dd) / R7[:, None]
                self_leaf = is_leaf[ai] & (self.node_ps[nn] == tt)
                add[self_leaf] = 0.0
                np.add.at(acc, tt, add)
                if potv is not None:
                    np.add.at(potv, tt, -self.node_W[nn] / np.maximum(R[ai], 1e-12))
                ninter += acc_set.sum()
            if not open_mask.any():
                break
            oset = np.nonzero(open_mask)[0]
            ot, on = t_ids[oset], n_ids[oset]
            ch = self.node_child[on]; ex = np.nonzero(ch >= 0)
            t_ids = ot[ex[0]]; n_ids = ch[ex[0], ex[1]]
            if t_ids.size == 0:
                break
        return (acc, potv) if pot else acc


def _count_interactions(tree, targets, theta):
    """Accepted-node budget for ANY tree exposing node_com/half/child/... —
    mirrors the wavefront walk's accept count without modifying BHOctree."""
    targets = np.asarray(targets, dtype=np.float64)
    T = targets.shape[0]; t_ids = np.arange(T); n_ids = np.zeros(T, np.int64)
    cnt = np.zeros(T)
    while t_ids.size:
        c = tree.node_com[n_ids]; d = targets[t_ids] - c
        ds2 = (d * d).sum(1); sep = np.sqrt(ds2); half = tree.node_half[n_ids]
        is_leaf = (tree.node_child[n_ids] < 0).all(1)
        contains = (np.abs(targets[t_ids] - c) <= half[:, None]).all(1)
        open_mask = (((half / np.maximum(sep, 1e-300) > theta) | contains)
                     & ~is_leaf)
        np.add.at(cnt, t_ids, ~open_mask)
        if not open_mask.any():
            break
        oset = np.nonzero(open_mask)[0]
        ch = tree.node_child[n_ids[oset]]; ex = np.nonzero(ch >= 0)
        t_ids = t_ids[oset][ex[0]]; n_ids = ch[ex[0], ex[1]]
    return cnt.mean()


def _qdot(Q, d):
    return np.stack([Q[:, 0]*d[:, 0] + Q[:, 1]*d[:, 1] + Q[:, 2]*d[:, 2],
                     Q[:, 1]*d[:, 0] + Q[:, 3]*d[:, 1] + Q[:, 4]*d[:, 2],
                     Q[:, 2]*d[:, 0] + Q[:, 4]*d[:, 1] + Q[:, 5]*d[:, 2]], axis=1)


def _qinprod(Q, d):
    return (_qdot(Q, d) * d).sum(1)


# ═════════════════════════════════════════════════════════════════════════
# G42 — median force error vs direct at EQUAL interaction budget
# ═════════════════════════════════════════════════════════════════════════
def run_g42(n=8192, L=6.0, a0=0.6, budget=270.0, eps2=1e-8, rng_seed=20260813):
    rng = np.random.default_rng(rng_seed)
    pos, masses = gen_sources(4096, 4096, L, a0, rng)
    ey = 1.0 + 0.3 * np.sin(2.0 * pos[:, 0]) * np.cos(2.0 * pos[:, 1])
    ei = 0.6 + 0.2 * np.cos(2.0 * pos[:, 2])
    _, g = gen_field(ey, ei)
    w = masses * g
    ref = direct_force(pos, pos, w, eps2=eps2)
    mag = np.linalg.norm(ref, axis=1)
    floor = 1e-4 * np.median(mag)
    keep = mag > floor
    print("=== G42: force error at equal interaction budget (~%.0f/target) ===" % budget)
    best = None
    for name, make in [
        ("octree(2-spaced)", lambda th: BHOctree(pos, masses, g=g, eps2=eps2)),
        ("phi-tree(φ)", lambda th: PhiTree(pos, masses, g=g, eps2=eps2, ratio=PHI_INV)),
        ("phi-tree(5/8)", lambda th: PhiTree(pos, masses, g=g, eps2=eps2, ratio=RATIO_RATIONAL)),
    ]:
        tree = make(0.5)
        # find theta that ACTUALLY hits the budget: bisect over [0.05, 2.0]
        lo, hi = 0.05, 2.0
        blo = _count_interactions(tree, pos, theta=lo)
        bhi = _count_interactions(tree, pos, theta=hi)
        reachable = blo > budget > bhi
        if reachable:
            for _ in range(20):
                mid = 0.5 * (lo + hi)
                b = _count_interactions(tree, pos, theta=mid)
                if b < budget:
                    hi = mid
                else:
                    lo = mid
            th = 0.5 * (lo + hi)
        else:
            th = lo if blo <= budget else hi
        a = tree.force(pos, theta=th, quad=True)
        err = np.median(_rel_err(a, ref, keep))
        bm = _count_interactions(tree, pos, theta=th)
        print("    %-16s theta=%.3f budget=%.1f  median_err=%.3e  [%s]"
              % (name, th, bm, err, "ok" if reachable else "budget-unreachable"))
        if reachable and (best is None or err < best[1]):
            best = (name, float(err))
    # only budget-reachable arms compete (equal-budget fairness); a reachable
    # winner tying the octree (a null for the φ-hypothesis) is reported.
    if best is None:
        best = ("(no budget-reachable arm)", 9e9)
    print("    [winner at equal budget] %s (a null — standard octree wins/ties — is honest)"
          % best[0])
    g42 = best[1] <= 1e-2
    return g42, best


# ═════════════════════════════════════════════════════════════════════════
# G43 — force anisotropy (ring metric) on a lattice-symmetric source
# ═════════════════════════════════════════════════════════════════════════
def run_g43(spacing=1.0, nside=4, ring=1.5, n_ring=360, theta=0.7, eps2=1e-6):
    """Sources on a simple-cubic lattice (a lattice-symmetric source). For a
    target at radius `ring` (IRRATIONAL vs the spacing so no target sits ON a
    source) the tree force magnitude vs angle gives the anisotropy (max/min).
    Less is better — the WHOLE POINT of φ-rungs is to not resonate with the
    cubic grid."""
    g = np.arange(-nside, nside + 1)
    P = np.stack(np.meshgrid(g, g, g, indexing="ij"), axis=-1).reshape(-1, 3) * spacing
    m = np.ones(P.shape[0])
    w = m.copy()
    phis = np.linspace(0, 2 * np.pi, n_ring, endpoint=False)
    tgt = np.stack([ring * np.cos(phis), ring * np.sin(phis),
                    np.zeros(n_ring)], axis=1)
    ref = direct_force(tgt, P, w, eps2=eps2)
    refmag = np.linalg.norm(ref, axis=1)
    print("=== G43: lattice anisotropy (%d sources), ring r=%.2f (spacing %.2f) ==="
          % (P.shape[0], ring, spacing))
    out = {}
    for name, tree in [
        ("octree(2)", BHOctree(P, m, g=np.ones(P.shape[0]), eps2=eps2)),
        ("phi-tree(φ)", PhiTree(P, m, g=np.ones(P.shape[0]), eps2=eps2, ratio=PHI_INV)),
    ]:
        a = tree.force(tgt, theta=theta, quad=True)
        mag = np.linalg.norm(a, axis=1)
        aniso = float(mag.max() / max(mag.min(), 1e-12))
        adir = float(np.linalg.norm(a - ref, axis=1).mean() / np.maximum(refmag.mean(), 1e-12))
        out[name] = aniso
        print("    %-14s aniso(max/min)=%.4f  dir|err|/ref=%.3e  (n=%d)"
              % (name, aniso, adir, P.shape[0]))
    g43 = out.get("phi-tree(φ)", 9e9) < out.get("octree(2)", 0.0)
    print("    [%s] phi-tree less anisotropic than octree" % ("PASS" if g43 else "FAIL(null)"))
    return g43, out


# ═════════════════════════════════════════════════════════════════════════
# G44 — energy drift in the G15 bound-cluster test, swap in the φ-tree
# ═════════════════════════════════════════════════════════════════════════
def _cluster_integrate(TreeCls, N=600, a0=0.5, theta=0.3, eps2=1e-8, ratio=PHI_INV,
                       rng_seed=20260813):
    rng = np.random.default_rng(rng_seed)
    M = 1.0; rmax = 3.0 * a0
    pos = _plummer_pos(N, a0, np.zeros(3), rng)
    keep = np.linalg.norm(pos, axis=1) <= rmax
    if keep.sum() < N:
        extra = _plummer_pos(N, a0, np.zeros(3), rng)
        extra = extra[np.linalg.norm(extra, axis=1) <= rmax]
        pos = np.concatenate([pos[keep], extra])[:N]
    m = np.full(N, M / N); g = np.ones(N)
    r = np.linalg.norm(pos, axis=1)
    sig = np.sqrt(G * M / (6.0 * np.sqrt(r ** 2 + a0 ** 2)))
    vel = sig[:, None] * rng.normal(size=pos.shape)
    U0 = pair_energy(pos, m, eps2)
    K0 = 0.5 * (m * (vel * vel).sum(1)).sum()
    scale = np.sqrt(-U0 / (2.0 * K0)) if K0 > 0 else 1.0
    vel = vel * scale; K0 *= scale * scale; E0 = K0 + U0
    dt = 0.01; T_dyn = np.sqrt((0.5 * a0) ** 3 / (G * M))
    n_steps = int(round(12.0 * T_dyn / dt))
    pc = pos.copy(); vc = vel.copy()
    if TreeCls is BHOctree:
        tree = BHOctree(pc, m, g=g, eps2=eps2)
    else:
        tree = PhiTree(pc, m, g=g, eps2=eps2, ratio=ratio)
    acc = tree.force(pc, theta=theta)
    drifts = []
    for s in range(n_steps):
        vh = vc + 0.5 * dt * acc
        pn = pc + dt * vh
        if TreeCls is BHOctree:
            tree = BHOctree(pn, m, g=g, eps2=eps2)
        else:
            tree = PhiTree(pn, m, g=g, eps2=eps2, ratio=ratio)
        an = tree.force(pn, theta=theta)
        vc = vh + 0.5 * dt * an; pc = pn; acc = an
        U = pair_energy(pc, m, eps2)
        K = 0.5 * (m * (vc * vc).sum(1)).sum()
        drifts.append(abs(K + U - E0) / abs(E0))
    return max(drifts)


def run_g44():
    print("=== G44: energy drift in the G15 bound-cluster test (N=600) ===")
    t0 = time.perf_counter()
    d_oct = _cluster_integrate(BHOctree)
    print("    octree(2)   max|dE/E0|=%.4f  (%.1fs)" % (d_oct, time.perf_counter() - t0))
    t0 = time.perf_counter()
    d_phi = _cluster_integrate(PhiTree, ratio=PHI_INV)
    print("    phi-tree(φ) max|dE/E0|=%.4f  (%.1fs)" % (d_phi, time.perf_counter() - t0))
    g44 = d_phi <= d_oct
    print("    [%s] phi-tree drift <= octree (report honestly)" % ("PASS" if g44 else "FAIL"))
    return g44, d_oct, d_phi


if __name__ == "__main__":
    t0 = time.perf_counter()
    g42, best42 = run_g42()
    print()
    g43, an43 = run_g43()
    print()
    g44, d_oct, d_phi = run_g44()
    print()
    print("---- gate ----")
    print("[%s] G42 equal-budget force error: %s" % ("PASS" if g42 else "FAIL", best42))
    print("[%s] G43 lattice anisotropy: %s" % ("PASS" if g43 else "FAIL", {k: round(v, 4) for k, v in an43.items()}))
    print("[%s] G44 energy drift: oct=%.4f phi=%.4f" % ("PASS" if g44 else "FAIL", d_oct, d_phi))
    print("RESULT: %s  (%.1fs)"
          % ("ALL PASS" if (g42 and g43 and g44) else "FAILURES PRESENT", time.perf_counter() - t0))
