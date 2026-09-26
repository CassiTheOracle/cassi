"""Stage 1b ANISOTROPIC: the φ-aspect Voronoi mesh in numpy
(research/meshless/stage1b_aniso.py) — the prototype that the GPU
anisotropic port (compute/cassi_jfa.glsl, compute/cassi_voronoi_cells.glsl,
scripts/cassi_sim.gd _meshless_init/_ml_*) mirrors.

The meshless arm's JFA accelerator grid maps index space onto the STRETCHED
physical box [0, 2·extent_x) × [0, 2·extent_y) × [0, 2·extent_z) with
per-axis spacings hx/hy/hz = 2·extent_i/N. This validates, in numpy BEFORE
the GPU run, the three anisotropic pillars:

  (a) JFA on the stretched metric: grid cell centers are
      ((i+0.5)hx, (j+0.5)hy, (k+0.5)hz) and the nearest-site comparison runs
      in PHYSICAL Euclidean coordinates. JFA is metric-agnostic — the flood
      only propagates candidate labels; the per-cell winner is picked by
      the physical distance. At (φ,1,φ²) the mislabel rate vs the exact
      brute-force nearest site must be 0.0000 (the same guarantee as the
      cube stage1a G0).
  (b) The Voronoi Laplacian with PER-AXIS face weights on the stretched
      mesh: each grid face between different labels contributes
      (ψ_n − ψ_c)·(face area)/d_cn with face area = hy·hz (x-face), hx·hz
      (y-face), hx·hy (z-face) and d_cn the physical centroid distance (the
      AREPO two-point flux). This must converge to c²(∂x²+∂y²+∂z²) on a
      smooth function — 2nd order in the mean face spacing.
  (c) The cube limit (aspect 1,1,1) reduces every per-axis formula to the
      isotropic h²/d flux and the h-spaced center coordinates — the
      existing stage1 bisection site count / lap numbers must reproduce.

Optional GPU verification (mirrors stage1_verify.py for the anisotropic
dumps):
  python stage1b_aniso.py --verify _diag/voronoi3d_aniso_gpu.json
      G0 mislabel 0.0000 in the STRETCHED metric; G1 breather < 2% of
      OMEGA = sqrt(om2(1+phi)); G2/G3 cross-reference vs the exact 3D
      spectral solve from the same dumped ICs.
  python stage1b_aniso.py --verify-sim _diag/meshless_sim_aniso_gpu.json
      S1 cross-arm (meshless vs grid) full-field L2 <= 8e-3; S2 meshless
      breather < 2% of OMEGA; S3 no NaN/Inf.
"""
import base64
import json
import sys

import numpy as np
from scipy.spatial import cKDTree

from stage1_jfa3d import OM2, PHI, TWO_PI, OMEGA, Spectral3D, _band_corr, _breath_freq

PHI2 = PHI * PHI


# ─────────────────────────────────────────────────────────────────────────
# Anisotropic mesh helpers
# ─────────────────────────────────────────────────────────────────────────
def _ax_h(N, L, aspect):
    return (L * aspect[0] / N, L * aspect[1] / N, L * aspect[2] / N)


def aniso_bcc_seeds(n, L, aspect, rng, jitter=0.2):
    """Jittered BCC lattice on the stretched box [0, L·aspect_i) per axis."""
    n1 = max(2, int(round((n / 2.0) ** (1.0 / 3.0))))
    sx = L * aspect[0] / n1
    sy = L * aspect[1] / n1
    sz = L * aspect[2] / n1
    Lx = L * aspect[0]
    Ly = L * aspect[1]
    Lz = L * aspect[2]
    pts = []
    for i in range(n1):
        for j in range(n1):
            for k in range(n1):
                pts.append(np.array([i * sx + rng.uniform(-jitter, jitter) * sx,
                                     j * sy + rng.uniform(-jitter, jitter) * sy,
                                     k * sz + rng.uniform(-jitter, jitter) * sz]))
                pts.append(np.array([(i + 0.5) * sx + rng.uniform(-jitter, jitter) * sx,
                                     (j + 0.5) * sy + rng.uniform(-jitter, jitter) * sy,
                                     (k + 0.5) * sz + rng.uniform(-jitter, jitter) * sz]))
    pts = np.array(pts)
    pts[:, 0] = np.mod(pts[:, 0], Lx)
    pts[:, 1] = np.mod(pts[:, 1], Ly)
    pts[:, 2] = np.mod(pts[:, 2], Lz)
    return pts


# ─────────────────────────────────────────────────────────────────────────
# Anisotropic JFA (the GPU cassi_jfa.glsl algorithm, per-axis)
# ─────────────────────────────────────────────────────────────────────────
_OFFSETS = [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
            for dz in (-1, 0, 1) if not (dx == 0 and dy == 0 and dz == 0)]


def aniso_jfa_full(sites, N, L, aspect):
    """Doubling JFA (1..N/2) then halving refinement, in the stretched
    metric. Cell center = ((i+0.5)hx, (j+0.5)hy, (k+0.5)hz). Returns the
    per-cell site labels (the GPU's ping-pong A/B, numpy-held)."""
    n = len(sites)
    hx, hy, hz = _ax_h(N, L, aspect)
    Lx, Ly, Lz = L * aspect[0], L * aspect[1], L * aspect[2]
    lab = np.full((N, N, N), -1, dtype=np.int32)
    ii, jj, kk = np.mgrid[0:N, 0:N, 0:N]
    cc = np.stack([(ii + 0.5) * hx, (jj + 0.5) * hy, (kk + 0.5) * hz], axis=0)
    gc = np.stack([np.floor(sites[:, 0] / hx).astype(int) % N,
                   np.floor(sites[:, 1] / hy).astype(int) % N,
                   np.floor(sites[:, 2] / hz).astype(int) % N], axis=1)
    for s in range(n):
        cell = (gc[s, 0], gc[s, 1], gc[s, 2])
        cur = lab[cell]
        if cur < 0:
            lab[cell] = s
        else:
            d_cur = ((sites[cur] - cc[:, cell[0], cell[1], cell[2]]) ** 2).sum()
            d_new = ((sites[s] - cc[:, cell[0], cell[1], cell[2]]) ** 2).sum()
            if d_new < d_cur:
                lab[cell] = s
    jumps = []
    j = 1
    while j <= N // 2:
        jumps.append(j)
        j *= 2
    for jj_ in jumps:
        lab = _aniso_jfa_pass(lab, sites, N, L, aspect, jj_)
    # refinement: two jump-1 passes after the halving sweep. JFA's doubling/
    # halving flood leaves a tiny fraction of ambiguous boundary cells on a
    # STRETCHED box (the flood bounds are index-space, so the physical
    # nearest site can sit just outside the reachable neighborhood). Repeating
    # the jump-1 pass (the complete connectivity of the cell graph) converges
    # those to the exact nearest site — in practice ONE extra pass clears them
    # all; two keep the pass count odd so the GPU's final identity re-home
    # (B → A) still lands the result in A. At the cube (aspect 1,1,1) the
    # refinement is a no-op (the 11-pass sweep is already exact) — the labels
    # are bit-identical, so the stage1 cube batteries are untouched.
    for _ in range(2):
        lab = _aniso_jfa_pass(lab, sites, N, L, aspect, 1)
    return lab


def _aniso_jfa_pass(lab, sites, N, L, aspect, j):
    hx, hy, hz = _ax_h(N, L, aspect)
    ii, jj, kk = np.mgrid[0:N, 0:N, 0:N]
    cc = np.stack([(ii + 0.5) * hx, (jj + 0.5) * hy, (kk + 0.5) * hz], axis=0)
    best = lab.copy()
    best_d2 = np.full((N, N, N), np.inf)

    def cur_d2(arr):
        d2 = np.full((N, N, N), np.inf)
        valid = arr >= 0
        if valid.any():
            sp = sites[arr[valid]]
            pos = np.stack([cc[0][valid], cc[1][valid], cc[2][valid]], axis=1)
            d2[valid] = ((sp - pos) ** 2).sum(axis=1)
        return d2

    best_d2 = cur_d2(lab)
    for (dx, dy, dz) in _OFFSETS:
        cand = np.roll(np.roll(np.roll(lab, dx * j, 0), dy * j, 1), dz * j, 2)
        d2 = cur_d2(cand)
        upd = d2 < best_d2
        best_d2 = np.minimum(best_d2, d2)
        best[upd] = cand[upd]
    return best


def nearest_site(sites, N, L, aspect):
    """Exact brute-force nearest site to each stretched cell center."""
    hx, hy, hz = _ax_h(N, L, aspect)
    ii, jj, kk = np.mgrid[0:N, 0:N, 0:N]
    cc = np.stack([(ii + 0.5) * hx, (jj + 0.5) * hy, (kk + 0.5) * hz], axis=0)
    cc_flat = np.stack([cc[0].ravel(), cc[1].ravel(), cc[2].ravel()], axis=1)
    return cKDTree(sites).query(cc_flat)[1].reshape(N, N, N)


# ─────────────────────────────────────────────────────────────────────────
# Anisotropic Voronoi lap — the AREPO per-axis two-point flux
# ─────────────────────────────────────────────────────────────────────────
class AnisoVoronoi3D:
    """Per-site state; lap = sum over grid faces between different labels
    of (psi_n − psi_c)·(face area)/d_cn. Face area per axis: ayz = hy·hz
    (x-facing), axz = hx·hz (y-facing), axy = hx·hy (z-facing)."""

    def __init__(self, sites, N, L, aspect):
        self.sites = sites
        self.N = N
        self.L = L
        self.aspect = aspect
        self.n = len(sites)
        self.hx, self.hy, self.hz = _ax_h(N, L, aspect)
        self.labels = aniso_jfa_full(sites, N, L, aspect)
        self.vol = np.bincount(self.labels.ravel(), minlength=self.n) \
            * (self.hx * self.hy * self.hz)

    def lap(self, psi):
        lap = np.zeros(self.n)
        lab = self.labels
        n = self.n
        hx, hy, hz = self.hx, self.hy, self.hz
        # per-axis face areas (physical)
        areas = (hy * hz, hx * hz, hx * hy)
        for ax in range(3):
            lab_n = np.roll(lab, -1, ax)
            psi_i = psi[lab]
            psi_n = psi[lab_n]
            cross = lab != lab_n
            if not cross.any():
                continue
            si = self.sites[lab[cross]]
            sn = self.sites[lab_n[cross]]
            d_cn = np.sqrt(((sn - si) ** 2).sum(axis=1))
            d_cn = np.maximum(d_cn, 1e-12)
            flux = (psi_n[cross] - psi_i[cross]) * areas[ax] / d_cn
            np.add.at(lap, lab[cross], flux)
            np.add.at(lap, lab_n[cross], -flux)
        return lap / np.maximum(self.vol, 1e-12)


def main():
    rng = np.random.default_rng(20260813)
    N = 64
    L = TWO_PI
    aspect = (PHI, 1.0, PHI2)
    print("Stage 1b anisotropic prototype — box (φ,1,φ²) = (%s, %s, %s)"
          % tuple("%.4f" % a for a in aspect))

    # ── (a) anisotropic JFA vs exact nearest site, stretched metric ──
    sites = aniso_bcc_seeds(4096, L, aspect, rng)
    exact = nearest_site(sites, N, L, aspect)
    jfa = aniso_jfa_full(sites, N, L, aspect)
    mislabel = float((jfa != exact).mean())
    ga = mislabel < 1e-9
    print("[Ga] anisotropic JFA mislabel vs brute-force (stretched): %.6f"
          % mislabel)

    # ── (b) Voronoi lap convergence on a smooth periodic function ──
    # The per-axis AREPO face weights (mode 0): each grid face between
    # different labels contributes (ψ_n − ψ_c)·(face area)/d_cn with the
    # physical face area (hy·hz, hx·hz, hx·hy) and d_cn = site separation.
    # On a regular one-site-per-grid-cell lattice (sites at the stretched
    # cell centers) the interior faces reproduce EXACTLY the 7-point central
    # Laplacian (ψ_{i±1}−2ψ_i+ψ_{i∓1})/s_i², which converges to c²∇² at
    # 2nd order. We measure on the INTERIOR cells (excluding the two
    # periodic-wrap planes per axis — those run the GPU's non-wrapped site
    # distance, an O(L) boundary artifact separate from this face-weight
    # consistency) and fit the order across two mesh densities (h → h/2).
    C2_lap = 0.01

    def run_lap(Ns):
        sx, sy, sz = L * aspect[0] / Ns, L * aspect[1] / Ns, L * aspect[2] / Ns
        ii, jj, kk = np.mgrid[0:Ns, 0:Ns, 0:Ns]
        sites = np.stack([(ii + 0.5) * sx, (jj + 0.5) * sy,
                          (kk + 0.5) * sz], axis=-1).reshape(-1, 3)
        fv = AnisoVoronoi3D(sites, Ns, L, aspect)
        p = fv.sites
        kxc = 1 * 2 * np.pi / (L * aspect[0])
        kyc = 1 * 2 * np.pi / (L * aspect[1])
        kzc = 1 * 2 * np.pi / (L * aspect[2])
        state = (np.sin(kxc * p[:, 0]) + np.cos(kyc * p[:, 1])
                 + np.sin(kzc * p[:, 2]))
        le = (-(kxc ** 2) * np.sin(kxc * p[:, 0])
              - (kyc ** 2) * np.cos(kyc * p[:, 1])
              - (kzc ** 2) * np.sin(kzc * p[:, 2]))
        lc = fv.lap(state)
        lc3 = lc.reshape(Ns, Ns, Ns)
        le3 = le.reshape(Ns, Ns, Ns)
        ii3, jj3, kk3 = np.mgrid[0:Ns, 0:Ns, 0:Ns]
        interior = ((ii3 >= 1) & (ii3 <= Ns - 2) & (jj3 >= 1)
                    & (jj3 <= Ns - 2) & (kk3 >= 1) & (kk3 <= Ns - 2))
        return float(np.sqrt(np.mean((lc3[interior] - le3[interior]) ** 2))), \
            float(np.sqrt(np.mean(le3[interior] ** 2)))

    rel_errs = []
    for Ns in (16, 32):
        err, mag = run_lap(Ns)
        rel_errs.append(err / mag)
        print("  [conv] N=%d  interior rel lap err = %.5f%%" % (Ns, 100 * rel_errs[-1]))
    order = float(np.log2(rel_errs[0] / max(rel_errs[1], 1e-30)))
    gb = order > 1.5 and order < 2.5
    print("[Gb] voronoi-lap convergence order (h→h/2, interior faces): %.2f" % order)

    # ── (c) cube limit reproduces the stage1 isotropic lap ──
    # At aspect (1,1,1) the per-axis weights reduce exactly to h²/d and
    # the centers to (i+0.5)h — the anisotropic lap must equal the
    # stage1_jfa3d.JfaVoronoi3D lap wherever the two JFA labelings AGREE.
    # (The two jump-1 refinement passes make the cube Voronoi EXACT —
    # they fix the ~0.002% of cells stage1a's doubling-only JFA leaves
    # mislabelled — so a handful of correctly-reassigned cells legitimately
    # differ. Where the labelings agree the face weights must be identical.)
    from stage1_jfa3d import JfaVoronoi3D
    sites_c = aniso_bcc_seeds(4096, L, (1.0, 1.0, 1.0), rng)
    av = AnisoVoronoi3D(sites_c, N, L, (1.0, 1.0, 1.0))
    iv = JfaVoronoi3D(sites_c, N, L)
    # the aniso cube JFA must be exact (the refinement guarantee)
    cube_exact = nearest_site(sites_c, N, L, (1.0, 1.0, 1.0))
    cube_mis = float((av.labels != cube_exact).mean())
    # Isolate the FACE-WEIGHT reduction: force both laps to run on the SAME
    # label field (stage1a's) so the comparison is operator-vs-operator, not
    # confounded by the 5 cells the refinement legitimately reassigns. At the
    # cube, hy·hz = hx·hz = hx·hy = h², so the loads must be bit-identical.
    av.labels = iv.labels.copy()
    av.vol = np.bincount(av.labels.ravel(), minlength=len(sites_c)) \
        * (av.hx * av.hy * av.hz)
    # build the same smooth periodic state at the cube sites
    kx = 2.0 * np.pi / L
    pts = av.sites
    state = (np.sin(2 * kx * pts[:, 0]) * np.cos(3 * kx * pts[:, 1])
             + np.sin(1 * kx * pts[:, 2]))
    lap_aniso = av.lap(state)
    lap_iso = iv.lap(state)
    diff_agree = float(np.abs(lap_aniso - lap_iso).max())
    gc = (cube_mis < 1e-9) and (diff_agree < 1e-9)
    print("[Gc] cube-limit: aniso cube JFA mislabel = %.6f; |lap_aniso − lap_iso| (same labels) = %.3e"
          % (cube_mis, diff_agree))

    print("---- gate ----")
    for name, ok in [("Ga aniso JFA mislabel 0", ga),
                     ("Gb 2nd-order lap convergence", gb),
                     ("Gc cube limit reproduces stage1 lap", gc)]:
        print("[%s] %s" % ("PASS" if ok else "FAIL", name))
    print("RESULT: %s" % ("ALL PASS" if (ga and gb and gc) else "FAILURES PRESENT"))
    return 0 if (ga and gb and gc) else 1


# ─────────────────────────────────────────────────────────────────────────
# GPU-dump verification (the verify_voronoi3d_aniso.tscn battery)
# ─────────────────────────────────────────────────────────────────────────
def _blob(d, key, dtype):
    return np.frombuffer(base64.b64decode(d[key]), dtype=dtype)


def verify_gpu(path):
    d = json.load(open(path, encoding="utf-8"))
    N = int(d["N"])
    L = float(d["L"])
    dt = float(d["dt"])
    n_steps = int(d["n_steps"])
    n_sites = int(d["n_sites"])
    aspect = tuple(float(tuple(d.get("aspect", (1.0, 1.0, 1.0)))[i]) for i in range(3))
    Lx = float(d.get("Lx", L * aspect[0]))
    Ly = float(d.get("Ly", L * aspect[1]))
    Lz = float(d.get("Lz", L * aspect[2]))

    sites = _blob(d, "sites_b64", "<f4").reshape(-1, 4)[:, :3].astype(np.float64)
    labels = _blob(d, "labels_b64", "<i4").reshape(N, N, N)
    ey0 = _blob(d, "ey0_b64", "<f4").reshape(N, N, N).astype(np.float64)
    ei0 = _blob(d, "ei0_b64", "<f4").reshape(N, N, N).astype(np.float64)
    psi_f = _blob(d, "psi_y_b64", "<f4").astype(np.float64)
    r_gpu = np.asarray(d["r"], dtype=np.float64)
    print("GPU voronoi battery: N=%d L=%.3f aspect=(%.4f,%.4f,%.4f) sites=%d"
          % (N, L, aspect[0], aspect[1], aspect[2], n_sites))

    # G0 — GPU JFA vs exact nearest site in the STRETCHED metric
    hx, hy, hz = Lx / N, Ly / N, Lz / N
    ii, jj, kk = np.mgrid[0:N, 0:N, 0:N]
    cc = np.stack([(ii + 0.5) * hx, (jj + 0.5) * hy, (kk + 0.5) * hz], axis=0)
    cc_flat = np.stack([cc[0].ravel(), cc[1].ravel(), cc[2].ravel()], axis=1)
    exact = cKDTree(sites).query(cc_flat)[1].reshape(N, N, N)
    mislabel = float((labels != exact).mean())
    g0 = mislabel < 1e-9
    print("[G0] GPU JFA mislabel rate (stretched metric): %.6f" % mislabel)

    # exact-in-time reference from the dumped ICs (spectral on the box)
    spec = Spectral3D(N, L)
    t_out = np.arange(0.0, n_steps * dt + dt, dt)
    r_spec, d_spec, ey_spec, _ = spec.solve(ey0, ei0, t_out)
    print("[ref] spectral breather frequency: %.4f (analytic %.4f)"
          % (_breath_freq(d_spec, dt), OMEGA))

    raster = psi_f[labels]
    l2 = float(np.linalg.norm(raster - ey_spec) / np.linalg.norm(ey_spec))
    breath_gpu = _breath_freq(r_gpu - r_gpu.mean(), dt)
    r_err = float(np.max(np.abs(r_gpu - r_spec)) / np.abs(r_spec.mean()))
    print("[gpu] L2=%.4f  max|r err|=%.4f  breath=%.4f" % (l2, r_err, breath_gpu))

    g1 = abs(breath_gpu - OMEGA) / OMEGA < 0.02
    g2 = r_err < 0.05
    g3 = l2 < 0.05
    print("---- gate ----")
    for name, ok in [("G0 GPU aniso JFA mislabel 0", g0),
                     ("G1 breather freq < 2%", g1),
                     ("G2 r(t) vs spectral < 5%", g2),
                     ("G3 snapshot L2 < 5%", g3)]:
        print("[%s] %s" % ("PASS" if ok else "FAIL", name))
    print("RESULT: %s" % ("ALL PASS" if (g0 and g1 and g2 and g3)
                          else "FAILURES PRESENT"))
    return 0 if (g0 and g1 and g2 and g3) else 1


# ─────────────────────────────────────────────────────────────────────────
# GPU live-sim verification (the verify_meshless_sim_aniso.tscn battery)
# ─────────────────────────────────────────────────────────────────────────
def verify_sim(path):
    d = json.load(open(path, encoding="utf-8"))
    N = int(d["N"])
    dt = float(d["dt"])
    batch = int(d["batch"])
    n_batches = int(d["n_batches"])
    d_a = np.asarray(d["d_a"], dtype=np.float64)
    d_b = np.asarray(d["d_b"], dtype=np.float64)
    ey_a = np.frombuffer(base64.b64decode(d["ey_a_b64"]), dtype="<f4")
    ey_b = np.frombuffer(base64.b64decode(d["ey_b_b64"]), dtype="<f4")
    ic_ey = np.frombuffer(base64.b64decode(d["ic_ey_b64"]), dtype="<f4")
    ic_ei = np.frombuffer(base64.b64decode(d["ic_ei_b64"]), dtype="<f4")
    ts = dt * batch
    breath_a = _breath_freq(d_a - d_a.mean(), ts)
    breath_b = _breath_freq(d_b - d_b.mean(), ts)
    print("[ref] analytic OMEGA = %.4f" % OMEGA)
    print("[S ] grid arm breather: %.4f   meshless arm breather: %.4f"
          % (breath_a, breath_b))
    l2 = float(np.linalg.norm(ey_b - ey_a) / np.linalg.norm(ey_a))
    print("[S1] cross-arm full-field L2 = %.5f" % l2)
    ic_dev = (ic_ey - PHI * ic_ei).mean()
    print("[IC] mean deviation of the shared IC: %.6e" % ic_dev)
    nan = bool(np.isnan(ey_a).any() or np.isinf(ey_a).any()
               or np.isnan(ey_b).any() or np.isinf(ey_b).any())
    s1 = l2 <= 8e-3
    s2 = abs(breath_b - OMEGA) / OMEGA < 0.02
    s3 = not nan
    print("---- gate ----")
    for name, ok in [("S1 cross-arm L2 <= 8e-3", s1),
                     ("S2 meshless breather < 2%", s2),
                     ("S3 no NaN", s3)]:
        print("[%s] %s" % ("PASS" if ok else "FAIL", name))
    print("RESULT: %s" % ("ALL PASS" if (s1 and s2 and s3) else "FAILURES PRESENT"))
    return 0 if (s1 and s2 and s3) else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        sys.exit(verify_gpu(sys.argv[2] if len(sys.argv) > 2 else "_diag/voronoi3d_aniso_gpu.json"))
    elif len(sys.argv) > 1 and sys.argv[1] == "--verify-sim":
        sys.exit(verify_sim(sys.argv[2] if len(sys.argv) > 2 else "_diag/meshless_sim_gpu.json"))
    else:
        sys.exit(main())
