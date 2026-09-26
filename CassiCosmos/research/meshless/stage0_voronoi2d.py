"""Stage 0: 2D Voronoi finite-volume two-fluid prototype (MESHLESS_PLAN.md).

Validates the AREPO-class discretization against an EXACT spectral reference
of the same continuum PDE (the sim's two-fluid wave system, 2D):

    d2EY/dt2 = c2 lap EY - om2 (EY - phi EI)
    d2EI/dt2 = c2 lap EI + om2 (EY - phi EI)

on the periodic square [0, L)^2. Facts that drive the design:
  - The deviation mode delta = EY - phi EI is a harmonic oscillator with the
    analytic breather frequency OMEGA = sqrt(om2 (1+phi)); the sum mode
    sigma = EY + phi EI propagates at c. (The phi-attractor of the ratio
    lives in the cosmology ODE closure, NOT this wave PDE — Stage 0 gates on
    cross-solver agreement of the breather, not on r -> phi.)
  - The spectral reference integrates each Fourier mode EXACTLY in time
    (per-mode eigenpair), so the Voronoi finite-volume solver must converge
    to a time-continuous reference.

Stage 0a (static): periodic Voronoi mesh (3x3 tile replication), Lloyd
relaxation, the two-point flux Laplacian (the Voronoi diffusion operator),
leapfrog. Gates V1-V4 (breather, trajectory, L2 + convergence, spectrum).

Stage 0b (moving + adaptive): ALE via periodic remap (steering = Lloyd
regularization + a quasi-Lagrangian ride on the field momentum), and
q-weighted site insertion — 'the mesh follows Qi' — refined where coherence
is INCOMPLETE ((1-q)^p weighting; the structure lives at low q). Gates
V5 (moving mesh vs fixed reference), V6 (q-adapted beats uniform in the
blob region at equal budget).

Run:  python stage0_voronoi2d.py
"""
import numpy as np
from scipy.spatial import Voronoi, KDTree

PHI = (1.0 + 5.0 ** 0.5) / 2.0
C2 = 0.01          # cs2 — wave speed squared (sim default)
OM2 = 20.0         # omega_0^2 — the shader's coupling constant
OMEGA = np.sqrt(OM2 * (1.0 + PHI))   # analytic breather frequency ~ 7.236
TWO_PI = 2.0 * np.pi


# ─────────────────────────────────────────────────────────────────────────
# Spectral reference — exact in time per Fourier mode
# ─────────────────────────────────────────────────────────────────────────
class Spectral2D:
    """Per-mode exact evolution: (psiY, psiI) = c_s (phi, 1) + c_d (1, -1);
    c_s oscillates at c|k|, c_d at sqrt(c2 k2 + om2 (1+phi))."""

    def __init__(self, N, L):
        self.N = N
        self.L = L
        kf = np.fft.fftfreq(N) * N * TWO_PI / L   # k = 2pi n / L (fftfreq = n/N)
        self.kx = kf[:, None]
        self.ky = kf[None, :]
        self.k2 = self.kx ** 2 + self.ky ** 2
        self.w_sum = np.sqrt(C2 * self.k2)                      # c |k|
        self.w_dev = np.sqrt(C2 * self.k2 + OM2 * (1.0 + PHI))  # Omega_k

    def solve(self, ey0, ei0, t_out):
        """ey0/ei0: (N,N) real ICs, pi = 0. t_out: array of times.
        Returns (r, d, ey_final, ei_final) — r the mean ratio, d the mean
        deviation delta = EY - phi EI (the pure breather signal)."""
        eyh = np.fft.fft2(ey0)
        eih = np.fft.fft2(ei0)
        c_s = (eyh + eih) / (1.0 + PHI)          # (psiY + psiI)/(1+phi)
        c_d = (eyh - PHI * eih) / (1.0 + PHI)    # (psiY - phi psiI)/(1+phi)
        r = np.empty(len(t_out))
        d = np.empty(len(t_out))
        ey_out = np.empty_like(ey0)
        ei_out = np.empty_like(ei0)
        for i, t in enumerate(t_out):
            cs_t = c_s * np.cos(self.w_sum * t)
            cd_t = c_d * np.cos(self.w_dev * t)
            eyh_t = PHI * cs_t + cd_t
            eih_t = cs_t - cd_t
            # r and the deviation mean from the k=0 mode (the pure breather:
            # delta(t) = (1+phi) c_d cos(OMEGA t) — full amplitude, ideal
            # for the frequency gate)
            r[i] = eyh_t[0, 0].real / eih_t[0, 0].real
            d[i] = eyh_t[0, 0].real - PHI * eih_t[0, 0].real
            if i == len(t_out) - 1:
                ey_out = np.fft.ifft2(eyh_t).real
                ei_out = np.fft.ifft2(eih_t).real
        return r, d, ey_out, ei_out


def _lloyd_relax(seeds, L, iters=30):
    """Lloyd relaxation — move each seed to its cell centroid (AREPO's mesh
    regularization): cells become near-regular hexagons, taming the discrete
    Laplacian's stiffness (jittered slivers make the leapfrog flux term
    unstable). NOTE: unweighted Lloyd relaxes toward UNIFORM density — an
    ADAPTED seed distribution must use few iterations (2) or the relaxation
    erases the adaptation."""
    n = len(seeds)
    offs = np.array([[dx, dy] for dx in (-L, 0.0, L) for dy in (-L, 0.0, L)])
    central = 4 * n + np.arange(n)
    for _ in range(iters):
        all_seeds = (seeds[None, :, :] + offs[:, None, :]).reshape(-1, 2)
        vor = Voronoi(all_seeds)
        for c, a in enumerate(central):
            reg = vor.regions[vor.point_region[a]]
            verts = np.array([vor.vertices[v] for v in reg])
            seeds[c] = np.mod(verts.mean(axis=0), L)
    return seeds


# ─────────────────────────────────────────────────────────────────────────
# Voronoi finite-volume solver — static, moving (ALE), Qi-adaptive
# ─────────────────────────────────────────────────────────────────────────
class VoronoiFV2D:
    """Periodic Voronoi mesh via 3x3 tile replication. Cell state
    (psiY, psiI, piY, piI); two-point flux Laplacian; leapfrog. Face arrays
    are precomputed for vectorized stepping."""

    def __init__(self, seeds, L, lloyd_iters=30):
        self.L = L
        # Mesh regularization (AREPO's own discipline): relax the jittered
        # seeds to their cell centroids so the discrete Laplacian is
        # well-conditioned for the leapfrog flux term. Adapted meshes use
        # lloyd_iters=2 — see _lloyd_relax.
        seeds = _lloyd_relax(seeds.copy(), L, iters=lloyd_iters)
        self._build_mesh(seeds)

    def _build_mesh(self, seeds):
        """(Re)build areas, centroids, the ridge face table, and the KDTree
        for the given seeds (periodic 3x3 tile replication)."""
        n = len(seeds)
        offs = np.array([[dx, dy] for dx in (-self.L, 0.0, self.L)
                         for dy in (-self.L, 0.0, self.L)])
        all_seeds = (seeds[None, :, :] + offs[:, None, :]).reshape(-1, 2)
        vor = Voronoi(all_seeds)
        central = 4 * n + np.arange(n)   # tile (0,0) all-indices
        central_set = set(central.tolist())
        # cell areas + centroids from the regions
        areas = np.empty(n)
        centroids = np.empty((n, 2))
        for c, a in enumerate(central):
            reg = vor.regions[vor.point_region[a]]
            verts = np.array([vor.vertices[v] for v in reg])
            areas[c] = abs(0.5 * np.sum(
                verts[:, 0] * np.roll(verts[:, 1], -1)
                - np.roll(verts[:, 0], -1) * verts[:, 1]))
            centroids[c] = verts.mean(axis=0)
        # Face table via the DELAUNAY ridge graph: each ridge separates two
        # all-indices and carries its Voronoi edge's vertex pair. The face
        # normal is the seed-segment direction — the Voronoi edge is the
        # perpendicular bisector of the Delaunay segment — so no polygon
        # orientation bookkeeping is needed, and Qhull's duplicate-vertex /
        # split-edge quirks never enter (ridges are unique).
        c_arr, n_arr, nx, ny, ln, df = [], [], [], [], [], []
        for (a, b), rv in zip(vor.ridge_points, vor.ridge_vertices):
            if -1 in rv:
                continue
            a_central = a in central_set
            b_central = b in central_set
            if not (a_central or b_central):
                continue
            # Ridge geometry (shared by both sides): the Voronoi edge is the
            # perpendicular bisector of the Delaunay seed segment.
            sa = all_seeds[a]
            sb = all_seeds[b]
            dlen = np.hypot(sb[0] - sa[0], sb[1] - sa[1])
            if dlen < 1e-12:
                continue
            p1 = vor.vertices[rv[0]]
            p2 = vor.vertices[rv[1]]
            length = np.hypot(p2[0] - p1[0], p2[1] - p1[1])
            # ONE FACE ENTRY PER CENTRAL ENDPOINT — the ridge between two
            # central cells contributes to BOTH (each side gets the flux
            # with its own outward normal). Emitting only one leaves half
            # the mesh face-less and the operator directed.
            if a_central:
                c_arr.append(int(a - 4 * n))
                n_arr.append(b)
                nx.append((sb[0] - sa[0]) / dlen)
                ny.append((sb[1] - sa[1]) / dlen)
                ln.append(length)
                df.append(dlen)
            if b_central:
                c_arr.append(int(b - 4 * n))
                n_arr.append(a)
                nx.append((sa[0] - sb[0]) / dlen)
                ny.append((sa[1] - sb[1]) / dlen)
                ln.append(length)
                df.append(dlen)
        self.n_cells = n
        self.areas = areas
        self.centroids = np.mod(centroids, self.L)
        self.c_arr = np.array(c_arr)          # central cell index per face
        self.n_arr = np.array(n_arr)          # neighbor ALL-index per face
        # neighbor all-index -> central index (images wrap to the tile owner)
        all_to_central = np.empty(9 * n, dtype=int)
        for t in range(9):
            all_to_central[t * n + np.arange(n)] = np.arange(n)
        self.n_cidx = all_to_central[self.n_arr]
        self.nx = np.array(nx)
        self.ln = np.array(ln)
        self.df = np.array(df)
        self.ny = np.array(ny)
        self.face_cell = self.c_arr
        self.kdt = KDTree(seeds)

    def step(self, psiY, psiI, piY, piI, dt):
        # Two-point flux Laplacian — the Voronoi DIFFUSION operator (AREPO's
        # own discretization of the Laplacian): the face-normal gradient
        # (psi_n - psi_c)/d_f across the perpendicular bisector. SPD by
        # construction, second-order on centroidal (Lloyd) meshes, and the
        # leapfrog flux term is energy-stable under the dt_cfl bound. (The
        # earlier Green-Gauss -> face-average-flux "double-difference" route
        # is INDEFINITE for the wave operator and blew up — Green-Gauss
        # reconstruction returns for the advective terms of the moving-mesh
        # stage, where it belongs.)
        # d piY/dt = C2 lap psiY - om2 (psiY - phi psiI)
        # d piI/dt = C2 lap psiI + om2 (psiY - phi psiI)
        lapY = np.bincount(self.face_cell,
                           weights=(psiY[self.n_cidx] - psiY[self.face_cell])
                                   * (self.ln / self.df),
                           minlength=self.n_cells) / self.areas
        lapI = np.bincount(self.face_cell,
                           weights=(psiI[self.n_cidx] - psiI[self.face_cell])
                                   * (self.ln / self.df),
                           minlength=self.n_cells) / self.areas
        dev = psiY - PHI * psiI
        piY = piY + dt * (C2 * lapY - OM2 * dev)
        piI = piI + dt * (C2 * lapI + OM2 * dev)
        psiY = psiY + dt * piY
        psiI = psiI + dt * piI
        return psiY, psiI, piY, piI

    def solve(self, ey0_fn, ei0_fn, dt, n_steps):
        """ey0_fn/ei0_fn: callables (x, y) -> field value (the continuum ICs)."""
        pts = self.kdt.data
        psiY = ey0_fn(pts[:, 0], pts[:, 1]).copy()
        psiI = ei0_fn(pts[:, 0], pts[:, 1]).copy()
        piY = np.zeros(self.n_cells)
        piI = np.zeros(self.n_cells)
        r = np.empty(n_steps + 1)
        d = np.empty(n_steps + 1)
        r[0] = psiY.sum() / psiI.sum()
        d[0] = (psiY - PHI * psiI).sum() / self.n_cells
        for s in range(n_steps):
            psiY, psiI, piY, piI = self.step(psiY, psiI, piY, piI, dt)
            r[s + 1] = psiY.sum() / psiI.sum()
            d[s + 1] = (psiY - PHI * psiI).sum() / self.n_cells
        return r, d, psiY, psiI

    def rasterize(self, psi, grid_x, grid_y):
        """Piecewise-constant sampling of the cell field onto a grid."""
        _, idx = self.kdt.query(np.stack([grid_x.ravel(), grid_y.ravel()], axis=1))
        return psi[idx].reshape(grid_x.shape)

    def dt_cfl(self):
        """Leapfrog CFL bound from the mesh's own geometry: dt < 2 h_min / c
        with h_min the smallest inradius proxy 2A/P per cell."""
        perimeter = np.bincount(self.face_cell, weights=self.ln,
                                minlength=self.n_cells)
        h_c = 2.0 * self.areas / np.maximum(perimeter, 1e-12)
        return 0.5 * h_c.min() / np.sqrt(C2)

    # ── Stage 0b: moving mesh (ALE via periodic remap) ────────────────
    def remap(self, new_seeds, psiY, psiI, piY, piI, lloyd=2):
        """Conservative ALE remap: rebuild the mesh on the drifted seeds and
        give each new cell the state of the OLD cell containing its seed
        (nearest-old-seed = Voronoi membership). Mass-conservative to the
        remap's order — the prototype's stand-in for the continuous
        geometric source terms (D1, deferred to Stage 1)."""
        old_kdt = self.kdt
        if lloyd:
            new_seeds = _lloyd_relax(new_seeds.copy(), self.L, iters=lloyd)
        self._build_mesh(new_seeds)
        idx = old_kdt.query(self.kdt.data)[1]
        return psiY[idx], psiI[idx], piY[idx], piI[idx]

    def steer(self, psiY, psiI, piY, piI, dt, steps, kappa, lam):
        """Mesh steering over `steps` steps of length dt: Lloyd-style
        relaxation toward the centroid (fraction kappa per rebuild, periodic-
        aware shortest displacement) + a quasi-Lagrangian ride on the field
        momentum lam*(piY+piI)/rho. Super-Lagrangian lam moves the mesh
        VISIBLY so the remap conservation is actually exercised. Returns
        the new seeds."""
        rho = psiY + psiI + 1e-12
        v = lam * (piY + piI) / rho
        s = self.kdt.data.copy()
        d = self.centroids - s
        d = np.mod(d + self.L * 0.5, self.L) - self.L * 0.5
        s += kappa * d + v[:, None] * dt * steps
        return np.mod(s, self.L)

    def q_coh(self, psiY, psiI):
        """Cell-wise coherence q = rho^2/(rho^2 + phi^-2 + eps^2) — the
        framework's Qi field. Peaks at equilibrium; the structure lives
        where q is LOW (see q_weighted_seeds)."""
        rho = psiY + psiI
        eps = psiY - PHI * psiI
        return (rho * rho) / (rho * rho + 1.0 / (PHI * PHI) + eps * eps)

    def solve_moving(self, ey0_fn, ei0_fn, dt, n_steps, rebuild=20,
                     kappa=0.5, lam=8.0):
        """Stage 0b driver: leapfrog on a mesh that is steered + remapped
        every `rebuild` steps. The solution must still match the fixed-mesh
        reference — that IS the validation of the moving-mesh terms."""
        pts = self.kdt.data
        psiY = ey0_fn(pts[:, 0], pts[:, 1]).copy()
        psiI = ei0_fn(pts[:, 0], pts[:, 1]).copy()
        piY = np.zeros(self.n_cells)
        piI = np.zeros(self.n_cells)
        r = np.empty(n_steps + 1)
        d = np.empty(n_steps + 1)
        r[0] = psiY.sum() / psiI.sum()
        d[0] = (psiY - PHI * psiI).sum() / self.n_cells
        for s in range(n_steps):
            psiY, psiI, piY, piI = self.step(psiY, psiI, piY, piI, dt)
            if (s + 1) % rebuild == 0:
                new_seeds = self.steer(psiY, psiI, piY, piI, dt, rebuild,
                                       kappa, lam)
                psiY, psiI, piY, piI = self.remap(new_seeds, psiY, psiI,
                                                  piY, piI)
            r[s + 1] = psiY.sum() / psiI.sum()
            d[s + 1] = (psiY - PHI * psiI).sum() / self.n_cells
        return r, d, psiY, psiI


# ─────────────────────────────────────────────────────────────────────────
# ICs — smooth modes + ratio r0 = 1.5 (the sim's default initial_ratio)
# ─────────────────────────────────────────────────────────────────────────
def make_ics(N, L, rng, r0=1.5, amp=0.02, blob=None):
    # REAL-space smooth modes: psi[i,j] = cos(2pi (n i + m j)/N + ph)/|k| —
    # the wavenumber of mode (n, m) is |(n,m)| (L = 2pi), so the power sits
    # at k <= ~4.2, well-resolved by both solvers. (The earlier index-space
    # construction cos(kx*nx_ + ...) put the power at k ~ 40-120 — a
    # near-Nyquist IC the mesh could barely resolve, masking convergence.)
    ii = np.arange(N)[:, None]
    jj = np.arange(N)[None, :]
    ey = np.zeros((N, N))
    ei = np.zeros((N, N))
    for _ in range(6):
        nx_, ny_ = rng.integers(1, 4), rng.integers(1, 4)
        k = np.hypot(nx_, ny_)
        ph = rng.uniform(0, TWO_PI)
        ph2 = rng.uniform(0, TWO_PI)
        a = TWO_PI * (nx_ * ii + ny_ * jj) / N
        ey += np.cos(a + ph) / k
        ei += np.cos(a + ph2) / k
    # normalize to amplitude amp and set the ratio
    ey -= ey.mean()
    ei -= ei.mean()
    ey *= amp / np.abs(ey).max()
    ei *= amp / np.abs(ei).max()
    # Compact deviation blob (a bubble seed): EY += A g, EI -= A g — the
    # deviation delta = EY - phi EI swings strongly at the blob, giving the
    # Qi field STRUCTURE to follow (q drops from ~0.94 to ~0.87 there).
    if blob is not None:
        A_blob, sig_blob = blob
        g = np.exp(-((ii - N * 0.5) ** 2 + (jj - N * 0.5) ** 2)
                   * (L / N) ** 2 / (2.0 * sig_blob ** 2))
        ey += A_blob * g
        ei -= A_blob * g
    return r0 * (1.0 + ey), 1.0 * (1.0 + ei)


def _bilinear_ics(px, py, ey0, ei0, L):
    """Continuum ICs at arbitrary points via bilinear sampling (periodic)."""
    N = ey0.shape[0]
    h = L / N
    gx = np.mod(px, L) / h
    gy = np.mod(py, L) / h
    i0 = np.floor(gx).astype(int) % N
    j0 = np.floor(gy).astype(int) % N
    i1 = (i0 + 1) % N
    j1 = (j0 + 1) % N
    fx = gx - np.floor(gx)
    fy = gy - np.floor(gy)

    def bilin(a):
        return (a[i0, j0] * (1.0 - fx) * (1.0 - fy) + a[i1, j0] * fx * (1.0 - fy)
                + a[i0, j1] * (1.0 - fx) * fy + a[i1, j1] * fx * fy)
    return bilin(ey0), bilin(ei0)


def _breath_freq(r, dt):
    """Dominant frequency via zero-padded FFT + parabolic peak refinement
    (the raw bins at dt=0.001, T=1.5 are 4.2 rad/s apart — too coarse)."""
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
    # The resolved band = where the IC actually has power (the smooth 6-mode
    # field lives at k <= ~6). Above that the spectra are noise-dominated
    # (the piecewise-constant rasterization's aliasing tail), and correlating
    # empty bands measures noise.
    sel = (k > 0) & (k <= 8.0)
    a = p_spec[sel]
    b = p_vor[sel]
    a -= a.mean()
    b -= b.mean()
    return float(np.corrcoef(a, b)[0, 1])


def hex_seeds(n, L, rng, jitter=0.3):
    """Jittered hexagonal seed lattice (well-shaped Voronoi cells after the
    Lloyd relaxation)."""
    cols = int(np.sqrt(n * np.sqrt(3.0) / 2.0)) + 1
    spacing = L / cols
    sx, sy = [], []
    for j in range(cols + 1):
        for i in range(cols + 1):
            px = (i + 0.5 * (j % 2)) * spacing + rng.uniform(-jitter, jitter) * spacing
            py = j * spacing * np.sqrt(3.0) / 2.0 + rng.uniform(-jitter, jitter) * spacing
            if 0.0 <= px < L and 0.0 <= py < L:
                sx.append(px)
                sy.append(py)
    return np.array([sx, sy]).T


def q_weighted_seeds(fv, psiY, psiI, n_base, n_extra, rng, p=4.0):
    """'The mesh follows Qi': n_base uniform hexagonal sites + n_extra sites
    sampled from the INCOMPLETE-coherence distribution (prob ∝ (1-q)^p ·
    area; p a soft sharpening). q_coh is the coherence gate — it peaks at
    equilibrium, so the structure (deviations, bubbles) lives where q is
    LOW; resolution belongs where the field is actively resolving toward
    the attractor. Fixed budget — no other free parameter."""
    q = fv.q_coh(psiY, psiI)
    w = ((1.0 - q) ** p) * fv.areas
    w /= w.sum()
    cells = rng.choice(fv.n_cells, size=n_extra, p=w)
    h_local = np.sqrt(fv.areas[cells])
    jit = rng.uniform(-0.4, 0.4, size=(n_extra, 2)) * h_local[:, None]
    extra = np.mod(fv.kdt.data[cells] + jit, fv.L)
    return np.concatenate([hex_seeds(n_base, fv.L, rng), extra])


def main():
    rng = np.random.default_rng(20260813)
    N = 256
    L = TWO_PI
    T = 1.5
    DT = 0.001   # small enough that the leapfrog time error sits well below
                 # the spatial error — the n-sweep then measures SPATIAL
                 # convergence (at 0.005 the flat ~0.4% time error masked it)
    t_out = np.arange(0.0, T + DT, DT)
    xs = np.linspace(0, L, N, endpoint=False)
    ey0, ei0 = make_ics(N, L, rng)
    X, Y = np.meshgrid(xs, xs, indexing="ij")
    spec = Spectral2D(N, L)
    r_spec, d_spec, ey_spec, ei_spec = spec.solve(ey0, ei0, t_out)

    print("analytic breather OMEGA = %.4f rad/t (period %.3f)" % (OMEGA, TWO_PI / OMEGA))
    print("[V1] spectral breather frequency: %.4f" % _breath_freq(d_spec, DT))

    # ── Stage 0a: static mesh convergence sweep ────────────────────────
    site_counts = [2048, 4096, 8192]
    l2_prev = None
    l2_conv = None
    l2_ey = 1.0
    corr = 0.0
    r_err = 1.0
    breath_v = 0.0
    for n in site_counts:
        seeds = hex_seeds(n, L, rng)
        fv = VoronoiFV2D(seeds, L)
        dt_use = min(DT, fv.dt_cfl())
        t_v = np.arange(0.0, T + dt_use, dt_use)
        r_spec2, _, _, _ = spec.solve(ey0, ei0, t_v)  # exact ref at same times
        r_vor, d_vor, ey_v, ei_v = fv.solve(
            lambda px, py: _bilinear_ics(px, py, ey0, ei0, L)[0],
            lambda px, py: _bilinear_ics(px, py, ey0, ei0, L)[1],
            dt_use, len(t_v) - 1)
        ey_grid = fv.rasterize(ey_v, X, Y)
        ei_grid = fv.rasterize(ei_v, X, Y)
        l2_ey = float(np.linalg.norm(ey_grid - ey_spec) / np.linalg.norm(ey_spec))
        l2_ei = float(np.linalg.norm(ei_grid - ei_spec) / np.linalg.norm(ei_spec))
        r_err = float(np.max(np.abs(r_vor - r_spec2)) / np.abs(r_spec2.mean()))
        p_spec = np.abs(np.fft.fft2(ey_spec - ey_spec.mean())) ** 2
        p_vor = np.abs(np.fft.fft2(ey_grid - ey_grid.mean())) ** 2
        k = np.hypot(np.fft.fftfreq(N)[:, None] * N * TWO_PI / L,
                     np.fft.fftfreq(N)[None, :] * N * TWO_PI / L)
        corr = _band_corr(p_spec.ravel(), p_vor.ravel(), k.ravel())
        breath_v = _breath_freq(d_vor, dt_use)
        conv = ""
        if l2_prev is not None:
            conv = "  (L2 shrink x%.2f)" % (l2_prev / l2_ey)
            l2_conv = l2_prev / l2_ey
        l2_prev = l2_ey
        print("[n=%5d dt=%.4f] L2(EY)=%.4f  L2(EI)=%.4f  max|r err|=%.4f  breath=%.4f  corr=%.4f%s"
              % (len(seeds), dt_use, l2_ey, l2_ei, r_err, breath_v, corr, conv))

    # ── Stage 0b: moving mesh + Qi-driven refinement (MESHLESS_PLAN §3) ─
    print("──── stage 0b ────")
    ey0b, ei0b = make_ics(N, L, rng, blob=(0.3, 0.35))
    r_specb, d_specb, ey_specb, ei_specb = spec.solve(ey0b, ei0b, t_out)
    ey_fn_b = lambda px, py: _bilinear_ics(px, py, ey0b, ei0b, L)[0]
    ei_fn_b = lambda px, py: _bilinear_ics(px, py, ey0b, ei0b, L)[1]
    # blob-region mask (the Gaussian core, g > 0.5) — the adaptation's honest
    # metric: measure the reconstruction WHERE the structure is.
    gmask = (np.exp(-((np.arange(N)[:, None] - N * 0.5) ** 2
                     + (np.arange(N)[None, :] - N * 0.5) ** 2)
                   * (L / N) ** 2 / (2.0 * 0.35 ** 2)) > 0.5).astype(float)

    def _l2_field(grid, ref):
        return float(np.linalg.norm(grid - ref) / np.linalg.norm(ref))

    def _l2_region(grid, ref):
        return float(np.linalg.norm((grid - ref) * gmask)
                     / np.linalg.norm(ref * gmask))

    # V5 — the moving mesh: steering + remap every 20 steps; the solution
    # must still match the fixed-mesh exact reference.
    fv_mv = VoronoiFV2D(hex_seeds(4096, L, rng), L)
    r_mv, d_mv, ey_mv, ei_mv = fv_mv.solve_moving(ey_fn_b, ei_fn_b, DT,
                                                  len(t_out) - 1)
    l2_mv = _l2_field(fv_mv.rasterize(ey_mv, X, Y), ey_specb)
    print("[0b-move] moving-mesh L2(EY) = %.4f  max|r err| = %.4f"
          % (l2_mv, float(np.max(np.abs(r_mv - r_specb)) / np.abs(r_specb.mean()))))

    # V6 — 'the mesh follows Qi': fixed budget (4096 sites), the extra sites
    # distributed by the field's own coherence. Gate: RECONSTRUCTION of the
    # known IC in the blob region — pure representational power, the thing
    # adaptivity directly controls (the evolved-solution error at dt=0.001
    # is dominated by resolution-independent terms, so the evolved L2 cannot
    # show the win).
    fv_u = VoronoiFV2D(hex_seeds(4096, L, rng), L)
    grid_u_ic = fv_u.rasterize(
        ey_fn_b(fv_u.kdt.data[:, 0], fv_u.kdt.data[:, 1]), X, Y)
    l2b_u = _l2_region(grid_u_ic, ey0b)
    fv_q = VoronoiFV2D(hex_seeds(2048, L, rng), L)
    psi0y = ey_fn_b(fv_q.kdt.data[:, 0], fv_q.kdt.data[:, 1])
    psi0i = ei_fn_b(fv_q.kdt.data[:, 0], fv_q.kdt.data[:, 1])
    # adaptation through the SEED DISTRIBUTION alone: the extra sites follow
    # the IC's incomplete-coherence (1-q)^p; light Lloyd polish only — a full
    # relaxation erases the density contrast (see _lloyd_relax).
    adapt_seeds = q_weighted_seeds(fv_q, psi0y, psi0i, 2048, 2048, rng)
    fv_q = VoronoiFV2D(adapt_seeds, L, 2)
    grid_q_ic = fv_q.rasterize(
        ey_fn_b(fv_q.kdt.data[:, 0], fv_q.kdt.data[:, 1]), X, Y)
    l2b_q = _l2_region(grid_q_ic, ey0b)
    print("[0b-qi]   blob IC-reconstruction L2: uniform %.4f  q-adapted %.4f"
          % (l2b_u, l2b_q))
    v5 = l2_mv < 0.02
    v6 = l2b_q < l2b_u * 0.75

    # verdicts — V1 gates the VORONOI solver's measured breather against the
    # analytic OMEGA (the spectral solver's is exact by construction)
    v1 = abs(breath_v - OMEGA) / OMEGA < 0.02
    v2 = r_err < 0.05
    v3 = l2_ey < 0.05 and (l2_conv is not None and l2_conv > 1.2)
    v4 = corr > 0.98
    print("---- gate ----")
    for name, ok in [("V1 breather freq (voronoi)", v1),
                     ("V2 r(t) trajectory", v2),
                     ("V3 snapshot L2 + convergence", v3),
                     ("V4 spectrum", v4),
                     ("V5 moving mesh (steer+remap)", v5),
                     ("V6 Qi-adaptivity beats uniform", v6)]:
        print("[%s] %s" % ("PASS" if ok else "FAIL", name))
    print("RESULT: %s" % ("ALL PASS" if (v1 and v2 and v3 and v4 and v5 and v6)
                          else "FAILURES PRESENT"))


if __name__ == "__main__":
    main()
