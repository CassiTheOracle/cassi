"""Stage 1a: 3D jump-flooding Voronoi two-fluid prototype (MESHLESS_PLAN.md).

Validates, in numpy BEFORE any GLSL, the two algorithmic pillars of the GPU
Stage 1 port:

  1. Voronoi construction by JUMP FLOODING (JFA, Rong & Tan) on an N^3
     accelerator grid — the grid is a lookup accelerator ONLY (no physics
     lives on it). Sites are scattered into their grid cells, then the
     26-neighborhood JFA (doubling passes 1..N/2, then a halving refinement
     sweep) labels every grid cell with its nearest site.

  2. The two-point flux wave Laplacian ON the JFA grid: the state is
     per-Voronoi-cell (site); faces are the grid-cell boundaries between
     different labels — each face contributes (psi_n - psi_c) h^2 / d_cn
     to both cells (the grid-aligned staircase approximation of the true
     Voronoi face; it converges as N grows relative to the site count).

Gates:
  G0 JFA mislabel rate vs the exact KDTree assignment (< 2%)
  G1 breather frequency vs analytic OMEGA = sqrt(om2 (1+phi)) (< 2%)
  G2 r(t) = <EY>/<EI> trajectory vs the exact 3D spectral reference (< 5%)
  G3 snapshot L2 vs the exact reference (< 5%)
  G4 spectrum correlation in the power band (> 0.95)

Run:  python stage1_jfa3d.py
"""
import numpy as np
from scipy.spatial import cKDTree

PHI = (1.0 + 5.0 ** 0.5) / 2.0
C2 = 0.01
OM2 = 20.0
OMEGA = np.sqrt(OM2 * (1.0 + PHI))   # analytic breather frequency ~ 7.236
TWO_PI = 2.0 * np.pi


# ─────────────────────────────────────────────────────────────────────────
# Spectral reference — exact in time per Fourier mode (3D)
# ─────────────────────────────────────────────────────────────────────────
class Spectral3D:
    """Same exact-in-time construction as Stage 0's Spectral2D, in 3D."""

    def __init__(self, N, L):
        self.N = N
        self.L = L
        kf = np.fft.fftfreq(N) * N * TWO_PI / L   # k = 2pi n / L (fftfreq = n/N)
        self.kx = kf[:, None, None]
        self.ky = kf[None, :, None]
        self.kz = kf[None, None, :]
        self.k2 = self.kx ** 2 + self.ky ** 2 + self.kz ** 2
        self.w_sum = np.sqrt(C2 * self.k2)
        self.w_dev = np.sqrt(C2 * self.k2 + OM2 * (1.0 + PHI))

    def solve(self, ey0, ei0, t_out):
        eyh = np.fft.fftn(ey0)
        eih = np.fft.fftn(ei0)
        c_s = (eyh + eih) / (1.0 + PHI)
        c_d = (eyh - PHI * eih) / (1.0 + PHI)
        r = np.empty(len(t_out))
        d = np.empty(len(t_out))
        ey_out = np.empty_like(ey0)
        ei_out = np.empty_like(ei0)
        for i, t in enumerate(t_out):
            cs_t = c_s * np.cos(self.w_sum * t)
            cd_t = c_d * np.cos(self.w_dev * t)
            eyh_t = PHI * cs_t + cd_t
            eih_t = cs_t - cd_t
            r[i] = eyh_t[0, 0, 0].real / eih_t[0, 0, 0].real
            d[i] = eyh_t[0, 0, 0].real - PHI * eih_t[0, 0, 0].real
            if i == len(t_out) - 1:
                ey_out = np.fft.ifftn(eyh_t).real
                ei_out = np.fft.ifftn(eih_t).real
        return r, d, ey_out, ei_out


# ─────────────────────────────────────────────────────────────────────────
# 3D ICs — smooth modes + ratio r0 = 1.5, optional deviation blob
# ─────────────────────────────────────────────────────────────────────────
def make_ics3d(N, L, rng, r0=1.5, amp=0.02, blob=None):
    ii = np.arange(N)[:, None, None]
    jj = np.arange(N)[None, :, None]
    kk = np.arange(N)[None, None, :]
    ey = np.zeros((N, N, N))
    ei = np.zeros((N, N, N))
    for _ in range(6):
        nx_, ny_, nz_ = rng.integers(1, 4, size=3)
        k = np.sqrt(nx_ * nx_ + ny_ * ny_ + nz_ * nz_)
        ph = rng.uniform(0, TWO_PI)
        ph2 = rng.uniform(0, TWO_PI)
        a = TWO_PI * (nx_ * ii + ny_ * jj + nz_ * kk) / N
        ey += np.cos(a + ph) / k
        ei += np.cos(a + ph2) / k
    ey -= ey.mean()
    ei -= ei.mean()
    ey *= amp / np.abs(ey).max()
    ei *= amp / np.abs(ei).max()
    if blob is not None:
        A_blob, sig_blob = blob
        c = N * 0.5
        g = np.exp(-((ii - c) ** 2 + (jj - c) ** 2 + (kk - c) ** 2)
                   * (L / N) ** 2 / (2.0 * sig_blob ** 2))
        ey += A_blob * g
        ei -= A_blob * g
    return r0 * (1.0 + ey), 1.0 * (1.0 + ei)


def _bilinear3d(px, py, pz, ey0, ei0, L):
    """Trilinear sampling of the IC arrays at arbitrary points (periodic)."""
    N = ey0.shape[0]
    h = L / N
    gx = np.mod(px, L) / h
    gy = np.mod(py, L) / h
    gz = np.mod(pz, L) / h
    i0 = np.floor(gx).astype(int) % N
    j0 = np.floor(gy).astype(int) % N
    k0 = np.floor(gz).astype(int) % N
    i1 = (i0 + 1) % N
    j1 = (j0 + 1) % N
    k1 = (k0 + 1) % N
    fx = gx - np.floor(gx)
    fy = gy - np.floor(gy)
    fz = gz - np.floor(gz)

    def tri(a):
        c00 = a[i0, j0, k0] * (1 - fx) + a[i1, j0, k0] * fx
        c01 = a[i0, j0, k1] * (1 - fx) + a[i1, j0, k1] * fx
        c10 = a[i0, j1, k0] * (1 - fx) + a[i1, j1, k0] * fx
        c11 = a[i0, j1, k1] * (1 - fx) + a[i1, j1, k1] * fx
        c0 = c00 * (1 - fy) + c10 * fy
        c1 = c01 * (1 - fy) + c11 * fy
        return c0 * (1 - fz) + c1 * fz
    return tri(ey0), tri(ei0)


# ─────────────────────────────────────────────────────────────────────────
# Seeds — jittered BCC lattice (the natural 3D analog of the 2D hex grid,
# and thematically the dual-lattice of CASCADE_GRID.md)
# ─────────────────────────────────────────────────────────────────────────
def bcc_seeds(n, L, rng, jitter=0.2):
    n1 = max(2, int(round((n / 2.0) ** (1.0 / 3.0))))
    spacing = L / n1
    pts = []
    for i in range(n1):
        for j in range(n1):
            for k in range(n1):
                pts.append((np.array([i, j, k]) * spacing
                            + rng.uniform(-jitter, jitter, 3) * spacing))
                pts.append((np.array([i + 0.5, j + 0.5, k + 0.5]) * spacing
                            + rng.uniform(-jitter, jitter, 3) * spacing))
    pts = np.mod(np.array(pts), L)
    return pts


# ─────────────────────────────────────────────────────────────────────────
# Jump-flooding Voronoi (3D, 26-neighborhood)
# ─────────────────────────────────────────────────────────────────────────
_OFFSETS = [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
            for dz in (-1, 0, 1) if not (dx == 0 and dy == 0 and dz == 0)]


def jfa_full(sites, N, L):
    """Scatter sites into the accelerator grid, then doubling JFA passes
    (1..N/2) followed by a halving refinement sweep. Returns per-cell site
    labels (int32) — the approximate Voronoi membership."""
    n = len(sites)
    h = L / N
    gc = np.floor(sites / h).astype(int) % N
    lab = np.full((N, N, N), -1, dtype=np.int32)
    # scatter: one site per cell (collisions: keep the site nearer the cell
    # center — rare for n << N^3)
    cc = (np.mgrid[0:N, 0:N, 0:N].astype(np.float64) + 0.5) * h
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
    # JFA passes
    jumps = []
    j = 1
    while j <= N // 2:
        jumps.append(j)
        j *= 2
    for jj in jumps:
        lab = _jfa_pass(lab, sites, N, L, jj)
    return lab


def _jfa_pass(lab, sites, N, L, j):
    h = L / N
    cc = (np.mgrid[0:N, 0:N, 0:N].astype(np.float64) + 0.5) * h
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

    # seed with the current labels' own distances
    own = cur_d2(lab)
    best_d2 = own
    for (dx, dy, dz) in _OFFSETS:
        cand = np.roll(np.roll(np.roll(lab, dx * j, 0), dy * j, 1), dz * j, 2)
        d2 = cur_d2(cand)
        upd = d2 < best_d2
        best_d2 = np.minimum(best_d2, d2)
        best[upd] = cand[upd]
    return best


# ─────────────────────────────────────────────────────────────────────────
# Cell solver — two-point flux on the JFA grid
# ─────────────────────────────────────────────────────────────────────────
class JfaVoronoi3D:
    """Per-cell (site) state (psiY, psiI, piY, piI); the Laplacian is the
    two-point flux across grid faces that separate different JFA labels —
    the staircase approximation of the true Voronoi face, converging as N
    grows relative to the site count."""

    def __init__(self, sites, N, L):
        self.sites = sites
        self.N = N
        self.L = L
        self.n = len(sites)
        self.h = L / N
        self.labels = jfa_full(sites, N, L)
        self.vol = np.bincount(self.labels.ravel(),
                               minlength=self.n) * self.h ** 3

    def lap(self, psi):
        lap = np.zeros(self.n)
        lab = self.labels
        n = self.n
        h2 = self.h ** 2
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
            flux = (psi_n[cross] - psi_i[cross]) * h2 / d_cn
            np.add.at(lap, lab[cross], flux)
            np.add.at(lap, lab_n[cross], -flux)
        return lap / np.maximum(self.vol, 1e-12)

    def step(self, psiY, psiI, piY, piI, dt):
        dev = psiY - PHI * psiI
        piY = piY + dt * (C2 * self.lap(psiY) - OM2 * dev)
        piI = piI + dt * (C2 * self.lap(psiI) + OM2 * dev)
        psiY = psiY + dt * piY
        psiI = psiI + dt * piI
        return psiY, psiI, piY, piI

    def solve(self, ey0_fn, ei0_fn, dt, n_steps):
        pts = self.sites
        psiY = ey0_fn(pts[:, 0], pts[:, 1], pts[:, 2]).copy()
        psiI = ei0_fn(pts[:, 0], pts[:, 1], pts[:, 2]).copy()
        piY = np.zeros(self.n)
        piI = np.zeros(self.n)
        r = np.empty(n_steps + 1)
        d = np.empty(n_steps + 1)
        r[0] = (psiY * self.vol).sum() / (psiI * self.vol).sum()
        d[0] = ((psiY - PHI * psiI) * self.vol).sum() / self.vol.sum()
        for s in range(n_steps):
            psiY, psiI, piY, piI = self.step(psiY, psiI, piY, piI, dt)
            r[s + 1] = (psiY * self.vol).sum() / (psiI * self.vol).sum()
            d[s + 1] = ((psiY - PHI * psiI) * self.vol).sum() / self.vol.sum()
        return r, d, psiY, psiI

    def rasterize(self, psi):
        """Piecewise-constant cell field on the accelerator grid."""
        return psi[self.labels]


def _breath_freq(r, dt):
    r_cent = r - r.mean()
    n = len(r)
    spec = np.abs(np.fft.rfft(r_cent, n=n * 8))
    freqs = np.fft.rfftfreq(n * 8, dt)
    j = int(np.argmax(spec))
    if 0 < j < len(freqs) - 1:
        a0, a1, a2 = spec[j - 1], spec[j], spec[j + 1]
        delta = 0.5 * (a0 - a2) / (a0 - 2.0 * a1 + a2)
        return (freqs[j] + delta * (freqs[1] - freqs[0])) * TWO_PI
    return freqs[j] * TWO_PI


def _band_corr(p_spec, p_vor, k):
    sel = (k > 0) & (k <= 8.0)
    a = p_spec[sel]
    b = p_vor[sel]
    a -= a.mean()
    b -= b.mean()
    return float(np.corrcoef(a, b)[0, 1])


def main():
    rng = np.random.default_rng(20260813)
    N = 64
    L = TWO_PI
    T = 1.5
    DT = 0.005
    t_out = np.arange(0.0, T + DT, DT)
    ey0, ei0 = make_ics3d(N, L, rng)
    spec = Spectral3D(N, L)
    r_spec, d_spec, ey_spec, ei_spec = spec.solve(ey0, ei0, t_out)
    print("analytic breather OMEGA = %.4f rad/t (period %.3f)" % (OMEGA, TWO_PI / OMEGA))
    print("[G1] spectral breather frequency: %.4f" % _breath_freq(d_spec, DT))

    sites = bcc_seeds(4096, L, rng)
    fv = JfaVoronoi3D(sites, N, L)
    print("sites=%d  labels: %d distinct, %d unlabeled" % (
        len(sites), len(np.unique(fv.labels)), int((fv.labels < 0).sum())))

    # G0 — JFA mislabel rate vs the exact KDTree assignment
    cc = (np.mgrid[0:N, 0:N, 0:N].astype(np.float64) + 0.5) * (L / N)
    cc_flat = np.stack([cc[0].ravel(), cc[1].ravel(), cc[2].ravel()], axis=1)
    exact = cKDTree(sites).query(cc_flat)[1].reshape(N, N, N)
    mislabel = float((fv.labels != exact).mean())
    print("[G0] JFA mislabel rate: %.4f" % mislabel)

    ey_fn = lambda px, py, pz: _bilinear3d(px, py, pz, ey0, ei0, L)[0]
    ei_fn = lambda px, py, pz: _bilinear3d(px, py, pz, ey0, ei0, L)[1]
    r_vor, d_vor, ey_v, ei_v = fv.solve(ey_fn, ei_fn, DT, len(t_out) - 1)
    l2 = float(np.linalg.norm(fv.rasterize(ey_v) - ey_spec)
               / np.linalg.norm(ey_spec))
    r_err = float(np.max(np.abs(r_vor - r_spec)) / np.abs(r_spec.mean()))
    breath_v = _breath_freq(d_vor, DT)
    p_spec = np.abs(np.fft.fftn(ey_spec - ey_spec.mean())) ** 2
    p_vor = np.abs(np.fft.fftn(fv.rasterize(ey_v) - fv.rasterize(ey_v).mean())) ** 2
    kf = np.fft.fftfreq(N) * N
    k = np.sqrt(kf[:, None, None] ** 2 + kf[None, :, None] ** 2
                + kf[None, None, :] ** 2)
    corr = _band_corr(p_spec.ravel(), p_vor.ravel(), k.ravel())
    print("[cell] L2=%.4f  max|r err|=%.4f  breath=%.4f  corr=%.4f"
          % (l2, r_err, breath_v, corr))

    g0 = mislabel < 0.02
    g1 = abs(breath_v - OMEGA) / OMEGA < 0.02
    g2 = r_err < 0.05
    g3 = l2 < 0.05
    g4 = corr > 0.95
    print("---- gate ----")
    for name, ok in [("G0 JFA mislabel", g0),
                     ("G1 breather freq", g1),
                     ("G2 r(t) trajectory", g2),
                     ("G3 snapshot L2", g3),
                     ("G4 spectrum", g4)]:
        print("[%s] %s" % ("PASS" if ok else "FAIL", name))
    print("RESULT: %s" % ("ALL PASS" if (g0 and g1 and g2 and g3 and g4)
                          else "FAILURES PRESENT"))


if __name__ == "__main__":
    main()
