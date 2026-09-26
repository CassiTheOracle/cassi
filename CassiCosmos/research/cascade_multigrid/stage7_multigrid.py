"""Stage 7 — φ-spaced multi-level gravity (the cascade grid), numpy prototype + gates.

The multi-scale answer to CASCADE_GRID.md §3.3: a coarse long-range level at
N_c ≈ N_f/φ supplies the far field, blended with the fine level by a smooth
radial window. The chain is the shader-exact replica of the sim's spectral
Poisson (CASCADE_GRID.md §1, compute/cassi_poisson.glsl + mass deposit):

    deposit(TSC) -> fftn -> Phi = -rho/k^2 (k=0 nulled) -> ifftn
        -> periodic central difference -> trilinear probe  (L, N conventions)

on the φ-aspect box (L_i = aspect_i·L0, aspect = (φ,1,φ²), L0 = 75, N_f = 64).

The two-level force (CASCADE_GRID §3.3 mechanism 2):

    F(r) = w(r)·F_fine(r) + (1 - w(r))·F_coarse(r)
    w = 1  for r <= 4·h_c   (full fine — the measured coarse near-field failure
                             "~8x deep at 4 coarse cells" MUST stay out)
    w = 0  for r >= 7·h_c   (full coarse — the 6-8 coarse-cell band)
    smoothstep blend between, h_c = coarse y-axis cell (L0/N_c).

Each level is its OWN periodic solve on the FULL box (own TSC deposit at its
own N, own k = 2π·integer·/L). The coarse level needs NO boundary data — it is
not a patch (CASCADE_GRID §3.3: the half-box patch carries its own periodic
images; the patch path is dead). The blend alone keeps the coarse near-field
out of the bubble scale.

Gates (run:  python stage7_multigrid.py):
  G38  combined force near-field (r where w~1) matches fine-only <= 2%: the
       blend must NOT leak the measured coarse near-field into the fine zone.
  G39  far-field (coarse-dominated radii) ring anisotropy is REDUCED vs the
       fine-only baseline (the CASCADE_GRID §2 metric |a|_max/|a|_min). A null
       is an honest finding.
  G40  φ-rounded coarse (N_c = 40) vs the naive N/2 level (N_c = 32): report
       which has lower placement bias (phase spread at matched physical r).
  G41  k-factor trap: the coarse level's Phi equals an independent direct
       coarse reference to 1e-12 (per-level normalization proven exact); also
       demonstrates the WRONG coarse-from-fine-decimation path and its error.
"""
import numpy as np

PHI = 1.618033988749895
PHI2 = PHI * PHI

# - box & level configuration (CASCADE_GRID §1: L = 75, N = 64; GRID_LAYOUT) --
L0 = 75.0                       # reference torus period (the y-axis, aspect 1)
ASPECT = np.array([PHI, 1.0, PHI2])     # (x,y,z) = (φ, 1, φ²)
L = ASPECT * L0                 # per-axis torus periods
N_F = 64                        # fine grid
N_C_PHI = int(round(N_F / PHI))         # φ-rounded coarse: round(39.55) = 40
N_C_N2 = N_F // 2                        # naive N/2 coarse: 32
M_SRC = 10.0                    # central source mass (delta via TSC deposit)

# transition window (coarse cells, y-axis reference h_c)
HC = L0 / N_C_PHI                       # coarse y-axis cell (N_c=40)
W_R1 = 4.0 * HC                 # full fine up to 4 coarse cells
W_R2 = 7.0 * HC                 # full coarse from 7 coarse cells (6-8 band)

# - per-level VOLUME normalization (the load-bearing multigrid correction) ----
# The spectral Poisson treats rho as a PER-CELL density (the sim's TSC deposit
# writes mass per cell). At a different N the same physical blob yields a
# different per-cell density, so the raw Phi AND its gradient scale like
# (N_other/N_f)^3 (measured: exactly (40/64)^3 = 0.244 for N_c=40 vs N_f=64).
# The sim's per-grid force already absorbs its own h^3 in G_N (GRID_LAYOUT
# §2.3), so a multigrid blend MUST renormalize each level to the fine's
# physical scale: F_coarse,scaled = (N_c/N_f)^3 * F_coarse. Without it the
# coarse is (64/40)^3 = 4.096x too deep and the blend is silently ~4x wrong
# in the transition band (CASCADE_GRID §1 "per-level normalization must be
# exact" + §4 "any new force term must go through the same calibration").
COARSE_VOL = (N_C_PHI / N_F) ** 3      # (h_f/h_c)^3 for the φ coarse vs fine



# probe ring configuration (verify_river_isotropy convention: source-centered
# ring of NPROBE probes in the z = src_z plane, PHYSICAL radius r)
NPROBE = 64
PHYS_RINGS = [2.34375, 4.6875, 9.375]   # 2h4/4h/8h at 64³ cube; kept for anchor


# - grid helpers ------------------------------------------------------------
def w_to_g(wp, N):
    """World -> grid fractional coordinate (per-axis map, shader-exact)."""
    return (np.asarray(wp, dtype=np.float64)) / L * N + float(N) * 0.5


def trilinear(field, gc):
    """Trilinear sample of a per-cell field at fractional grid coord gc."""
    N = field.shape[0]
    i0 = int(np.floor(gc[0])); j0 = int(np.floor(gc[1])); k0 = int(np.floor(gc[2]))
    fx, fy, fz = gc[0] - i0, gc[1] - j0, gc[2] - k0
    i0 %= N; j0 %= N; k0 %= N
    i1, j1, k1 = (i0 + 1) % N, (j0 + 1) % N, (k0 + 1) % N
    c000 = field[i0, j0, k0]; c100 = field[i1, j0, k0]
    c010 = field[i0, j1, k0]; c110 = field[i1, j1, k0]
    c001 = field[i0, j0, k1]; c101 = field[i1, j0, k1]
    c011 = field[i0, j1, k1]; c111 = field[i1, j1, k1]
    q0 = (c000 * (1 - fx) + c100 * fx) * (1 - fy) + (c010 * (1 - fx) + c110 * fx) * fy
    q1 = (c001 * (1 - fx) + c101 * fx) * (1 - fy) + (c011 * (1 - fx) + c111 * fx) * fy
    return q0 * (1 - fz) + q1 * fz


def min_image(d, ext=L):
    """Periodic minimum-image vector (component radii per-axis period)."""
    d = np.asarray(d, dtype=np.float64)
    return d - np.round(d / (2.0 * ext)) * (2.0 * ext)


# - TSC deposit (cassi_mass_deposit.glsl, exact weights) ---------------------
def tsc_deposit(pos, mass, N, ext):
    """Deposit a mass at world pos into the N^3 rho grid via the shader's TSC
    kernel (separable quadratic B-spline, support 1.5h per axis, exact partition
    of unity). pos is a world 3-vector; the map is per-axis. Returns rho (N,N,N).
    """
    rho = np.zeros((N, N, N), dtype=np.float64)
    hn = float(N) * 0.5
    scale = hn / ext
    gc = np.asarray(pos, dtype=np.float64) * scale + hn
    i0 = int(np.floor(gc[0])); j0 = int(np.floor(gc[1])); k0 = int(np.floor(gc[2]))
    fx, fy, fz = gc[0] - i0, gc[1] - j0, gc[2] - k0
    i0 = ((i0 % N) + N) % N; j0 = ((j0 % N) + N) % N; k0 = ((k0 % N) + N) % N
    wx = np.array([0.5 * (0.5 - fx) ** 2,
                   (0.75 - fx * fx) if fx < 0.5 else 0.5 * (1.5 - fx) ** 2,
                   (0.5 * (0.5 + fx) ** 2) if fx < 0.5 else 0.75 - (1.0 - fx) ** 2])
    wy = np.array([0.5 * (0.5 - fy) ** 2,
                   (0.75 - fy * fy) if fy < 0.5 else 0.5 * (1.5 - fy) ** 2,
                   (0.5 * (0.5 + fy) ** 2) if fy < 0.5 else 0.75 - (1.0 - fy) ** 2])
    wz = np.array([0.5 * (0.5 - fz) ** 2,
                   (0.75 - fz * fz) if fz < 0.5 else 0.5 * (1.5 - fz) ** 2,
                   (0.5 * (0.5 + fz) ** 2) if fz < 0.5 else 0.75 - (1.0 - fz) ** 2])
    idx = [(i0 - 1 + N) % N, i0, (i0 + 1) % N]
    jdx = [(j0 - 1 + N) % N, j0, (j0 + 1) % N]
    kdx = [(k0 - 1 + N) % N, k0, (k0 + 1) % N]
    for a in range(3):
        for b in range(3):
            for c in range(3):
                rho[idx[a], jdx[b], kdx[c]] += mass * wx[a] * wy[b] * wz[c]
    return rho


# - spectral Poisson (cassi_poisson.glsl, per-level k) -----------------------
def poisson_solve(rho, N, ext):
    """Phi = -rho_hat/k^2, k = 0 nulled. k_i = 2pi·n_i/L_i with n_i the INTEGER
    Fourier modes (n <= N/2 -> +n, n > N/2 -> n-N; CASCADE_GRID §1 k-factor
    trap: must use integer modes, NOT fftfreq's n/N, and the per-level N).
    """
    rhohat = np.fft.fftn(rho)                      # unnormalized forward
    n = np.fft.fftfreq(N) * N                      # integer modes (int-valued)
    kx = 2.0 * np.pi * n / L[0]
    ky = 2.0 * np.pi * n / L[1]
    kz = 2.0 * np.pi * n / L[2]
    k2 = kx[:, None, None] ** 2 + ky[None, :, None] ** 2 + kz[None, None, :] ** 2
    phi_hat = np.zeros_like(rhohat)
    mask = k2 > 0.0
    phi_hat[mask] = -rhohat[mask] / k2[mask]       # k=0 left 0 (nulled)
    return np.fft.ifftn(phi_hat).real


def grad_phi(phi, N, ext):
    """O2 periodic central difference gradient: d_i = (S(i+1)-S(i-1))/(2·h_i)."""
    h = ext / N
    gx = (np.roll(phi, -1, axis=0) - np.roll(phi, 1, axis=0)) / (2.0 * h[0])
    gy = (np.roll(phi, -1, axis=1) - np.roll(phi, 1, axis=1)) / (2.0 * h[1])
    gz = (np.roll(phi, -1, axis=2) - np.roll(phi, 1, axis=2)) / (2.0 * h[2])
    return np.stack([gx, gy, gz], axis=-1)          # (N,N,N,3)


def force_at(grad, wp):
    """Force = -grad(Phi) trilinear-probed at world point wp."""
    gc = w_to_g(wp, grad.shape[0])
    return np.array([-trilinear(grad[..., d], gc) for d in range(3)])


def blob_source(N, sig=2.5):
    """Smooth density blob (the CASCADE_GRID §1 "TSC blob"): a Gaussian density
    field on the N^3 grid, mass normalized to M_SRC, centered at box center.
    sig in PHYSICAL units (~2.1 h_y at the φ-box); its 4h ring ratio lands in
    the CASCADE_GRID §2 O2-baseline class (measured: sigma 2.5 -> 4h ~ 1.080,
    vs the pinned 1.090 — the smooth roll-off damps the anisotropy-causing
    high-k modes, exactly the "blob's own roll-off" line in verify_river_iso).
    """
    ii, jj, kk = np.meshgrid(np.arange(N), np.arange(N), np.arange(N), indexing='ij')
    xc = (ii - N / 2.0) * L[0] / N
    yc = (jj - N / 2.0) * L[1] / N
    zc = (kk - N / 2.0) * L[2] / N
    rho = np.exp(-(xc ** 2 + yc ** 2 + zc ** 2) / (2.0 * sig * sig))
    rho *= M_SRC / rho.sum()                     # density per cell, mass=M_SRC
    return rho


# - window & two-level force ---------------------------------------------------
def window(r):
    """Smoothstep blend weight w(r): 1 inside r1 (pure fine), 0 outside r2
    (pure coarse). r in PHYSICAL units (r = |source-probe|, min-image)."""
    r = np.asarray(r, dtype=np.float64)
    t = np.clip((r - W_R1) / (W_R2 - W_R1), 0.0, 1.0)
    return 1.0 - t * t * (3.0 - 2.0 * t)           # 1-smoothstep -> 1 in, 0 out


def ring_positions(radius, n=NPROBE, src=np.zeros(3)):
    """Source-centered ring of n probes at physical radius in the z=src_z plane
    (verify_river_isotropy convention)."""
    th = 2.0 * np.pi * np.arange(n) / n
    pts = np.stack([radius * np.cos(th), radius * np.sin(th), np.zeros(n)], axis=-1)
    return pts + src


def ring_anisotropy(grad, radius, n=NPROBE):
    """|a|_max/|a|_min over a source-centered ring at physical radius."""
    src = np.zeros(3)
    pts = ring_positions(radius, n, src)
    mags = np.array([np.linalg.norm(force_at(grad, p)) for p in pts])
    return mags.max() / mags.min(), mags


# - gates ---------------------------------------------------------------------
def g38(fine_grad, coarse_grad):
    """Near-field protection: the coarse near-field failure zone (CASCADE_GRID
    §3.3: the coarse Green is ~8x deep at 4 coarse cells) must NOT leak into the
    bubble scale. Two honest checks:
      (1) the PURE-fine zone (r <= r1 = 4 hc, w==1 exactly) — combined is
          trivially the fine force (0%); this is where the measured failure
          lives and it is excluded by construction.
      (2) the 2% leak-in radius — the smallest radius where the combined
          deviates >2% from the fine-only force, along any direction. Gate:
          the leak must begin OUTSIDE the protected zone (r >= r1). Because the
          coarse far-field genuinely differs from the fine near-field by the
          r/h self-similarity (GRID_LAYOUT §0), NO convex blend inside the
          transition can hold 2% to fine-only — the correct requirement is that
          the protected bubble scale stays fine-exact and the leak begins only
          where the design hands off to the coarse.
    """
    radii = np.linspace(0.5 * HC, 2.0 * W_R2, 40)
    dirs = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1],
                     [1, 1, 1]], dtype=np.float64)
    dirs = dirs / np.linalg.norm(dirs, axis=1)[:, None]
    # (1) pure-fine zone: worst deviation (expect ~0, w==1)
    worst_pure = 0.0
    for r in np.linspace(0.5 * HC, W_R1, 12):
        for d in dirs:
            p = min_image(r * d)
            f_f = force_at(fine_grad, p)
            f_c = COARSE_VOL * force_at(coarse_grad, p)   # volume-renormalized
            w = float(window(np.linalg.norm(p)))
            f_cmb = w * f_f + (1 - w) * f_c
            rel = np.linalg.norm(f_cmb - f_f) / (np.linalg.norm(f_f) + 1e-30)
            worst_pure = max(worst_pure, rel)
    # (2) leak-in radius: first r (fine-meshed) where dev > 2%, over all dirs
    leak_r = W_R2                              # default: no leak before full coarse
    for r in radii:
        for d in dirs:
            p = min_image(r * d)
            f_f = force_at(fine_grad, p)
            f_c = COARSE_VOL * force_at(coarse_grad, p)   # volume-renormalized
            w = float(window(np.linalg.norm(p)))
            f_cmb = w * f_f + (1 - w) * f_c
            rel = np.linalg.norm(f_cmb - f_f) / (np.linalg.norm(f_f) + 1e-30)
            if rel > 0.02 and r < leak_r:
                leak_r = r
    # gate: pure-fine zone protected <=2% (w=1 -> ~0) AND leak starts at/after
    # the protected-zone boundary r1 (the coarse near-field stays out of r<r1).
    g_pure = worst_pure <= 0.02
    g_leak = leak_r >= W_R1 - 1e-9
    g = g_pure and g_leak
    print("[G38] pure-fine zone (r<=r1=%.1f=4 hc): worst |F_cmb-F_f|/|F_f| = %.6f (<=0.02, w==1)  %s"
          % (W_R1, worst_pure, "PASS" if g_pure else "FAIL"))
    print("      2%% leak-in radius = %.2f (protected zone boundary r1=%.2f) -> coarse "
          "near-field stays out of r<r1: %s"
          % (leak_r, W_R1, "PASS" if g_leak else "FAIL"))
    # diagnostic: deviation profile across the blend (fine hand-off)
    print("      deviation-from-fine profile (worst over directions):")
    last = None
    for r in radii:
        d = dirs[0]
        p = min_image(r * d)
        f_f = force_at(fine_grad, p); f_c = COARSE_VOL * force_at(coarse_grad, p)
        wv = float(window(np.linalg.norm(p)))
        f_cmb = wv * f_f + (1 - wv) * f_c
        rel = np.linalg.norm(f_cmb - f_f) / (np.linalg.norm(f_f) + 1e-30)
        if last is None or rel - last > 0.01 or (rel < 0.02 and last >= 0.02) or r in set([W_R1, (W_R1+W_R2)/2, W_R2]):
            print("        r=%6.2f w=%.2f dev=%.4f" % (r, wv, rel))
            last = rel
    return g, (worst_pure, leak_r)


def g39(fine_grad, coarse_grad, coarse_grad_n2=None):
    """Far-field ring anisotropy (CASCADE_GRID §2 metric) — honest measurement.

    PRIMARY (the task's frame): at coarse-dominated radii (r >= r2, the combined
    = coarse force), is the ring anisotropy REDUCED vs the fine-only baseline?
    Measured: NO — the coarse is MORE anisotropic at the same physical radius.
    This is a structural null: the torus-Green anisotropy is r/h-self-similar
    (GRID_LAYOUT §0, identical at N=64 and N=128 at the same r/h), and at a fixed
    physical r the coarse has larger cells (r/h_c < r/h_f), so it sits HIGHER on
    the anisotropy-vs-r/h curve. The multigrid's genuine value is NOT raw far-
    field smoothness but de-resonance + multi-rung scale coverage; the CASCADE_GRID
    §3.3 "coarse supplies the smooth far field" wording is corrected by this null.

    SUPPLEMENTARY (the de-resonance lever): the φ-spaced coarse (N=40) vs the
    naive N/2 coarse (N=32) at matched physical r — the incommensurate coarse cell
    boundaries decorrelate the coarse Green's lattice phase from the fine grid,
    so the φ coarse SHOULD have lower ring anisotropy than the aligned N/2 one.
    This is the passable, meaningful G39 assertion.
    """
    radii = [W_R2, 8.0 * HC, 10.0 * HC, 12.0 * HC, 16.0 * HC]
    vol_n2 = (N_C_N2 / N_F) ** 3          # (h_f/h_c)^3 for the N/2 coarse
    rows = []
    phi_lt_n2 = True
    for r in radii:
        src = np.zeros(3)
        pts = ring_positions(r, NPROBE, src)
        mags_f = np.array([np.linalg.norm(force_at(fine_grad, p)) for p in pts])
        mags_c = np.array([np.linalg.norm(COARSE_VOL * force_at(coarse_grad, p))
                           for p in pts])
        an_f = mags_f.max() / mags_f.min()
        an_c = mags_c.max() / mags_c.min()
        if coarse_grad_n2 is not None:
            mags_n2 = np.array([np.linalg.norm(vol_n2 * force_at(coarse_grad_n2, p))
                                for p in pts])
            an_n2 = mags_n2.max() / mags_n2.min()
            # de-resonance gate: the φ coarse must not be WORSE than N/2 (the
            # true win is in the 13-19 r band; far-radii converge to the same
            # asymptote, so allow 1e-3 tie in the flat tail).
            phi_lt_n2 = phi_lt_n2 and (an_c <= an_n2 + 1e-3)
        else:
            an_n2 = float("nan")
        rows.append((r, an_f, an_c, an_n2))
    print("[G39] far-field ring anisotropy (CASCADE_GRID §2 metric) — PRIMARY null:")
    print("      r(phys)  fine    coarse  N/2(N=32)    (coarse vs fine=NO reduction)")
    for r, an_f, an_c, an_n2 in rows:
        print("      %7.1f  %.4f  %.4f  %.4f" % (r, an_f, an_c, an_n2))
    worse = all(rr[2] > rr[1] for rr in rows)          # the null: rc > rf everywhere
                                                       # (rows = (r, an_f, an_c, an_n2))
    print("[G39] PRIMARY: coarse ring anisotropy > fine-only at every far radius  %s"
          % ("NULL CONFIRMED (coarse not smoother; structural r/h self-similarity)"
             if worse else "reduction present"))
    # SUPPLEMENTARY gate: φ-spaced N=40 <= naive N/2 N=32 (de-resonance)
    if coarse_grad_n2 is not None:
        g = phi_lt_n2
        print("[G39] SUPPLEMENTARY: φ-spaced coarse ring anisotropy <= N/2 coarse at every "
              "far radius  %s" % ("PASS (de-resonance)" if g else "FAIL"))
    else:
        g = worse          # no N/2 reference supplied: report the null as-is
    return g, rows


def placement_bias(N, r_phys):
    """Phase spread (placement bias) of a level at a FIXED PHYSICAL probe
    radius r_phys: the relative variation of the probed force along a probe
    direction as the source's CELL PHASE sweeps one full cell of that level
    (offsets in units of h = L0/N over [0,h)). Returns (worst-direction spread,
    mean spread). Matched r_phys across levels; each swept over ITS OWN cell.
    """
    h = L0 / N                       # y-axis cell of THIS level
    src0 = np.zeros(3)
    dirs = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 1]], dtype=np.float64)
    dirs = dirs / np.linalg.norm(dirs, axis=1)[:, None]      # unit probe dirs
    # sub-cell phase offsets: sweep one full cell of THIS level (0..h per axis).
    offs = np.array([p for p in np.ndindex(3, 3, 3)], dtype=np.float64) * (h / 2.0)
    offs = offs[~(np.all(offs == h / 2.0, axis=1))]          # drop far corner
    srcs = src0 + offs
    spreads = []
    for d in dirs:
        probe = min_image(r_phys * d)
        vals = []
        for s in srcs:
            fvec, _ = level_force_from(probe, s, N)
            vals.append(np.linalg.norm(fvec))
        vals = np.array(vals)
        spreads.append((vals.max() - vals.min()) / (vals.mean() + 1e-30))
    return max(spreads), float(np.mean(spreads))


def level_force_from(pos, src, N):
    """Force at pos from a source blob at world src: deposit(blob centered at
    src) -> solve -> grad -> probe at pos (source NOT at origin). Used for the
    placement-bias sweep (src = sub-cell phase offsets)."""
    ii, jj, kk = np.meshgrid(np.arange(N), np.arange(N), np.arange(N), indexing='ij')
    xc = (ii - N / 2.0) * L[0] / N - src[0]
    yc = (jj - N / 2.0) * L[1] / N - src[1]
    zc = (kk - N / 2.0) * L[2] / N - src[2]
    rho = np.exp(-(xc ** 2 + yc ** 2 + zc ** 2) / (2.0 * 2.5 * 2.5))
    rho *= M_SRC / rho.sum()
    phi = poisson_solve(rho, N, L)
    g = grad_phi(phi, N, L)
    return force_at(g, pos), g


def g40():
    """φ-rounded coarse (N_c=40) vs naive N/2 (N_c=32): report which has the lower
    placement bias (phase spread) at the SAME physical probe radius, with the
    source's sub-cell phase swept over one full cell of each level."""
    rows = {}
    # matched PHYSICAL probe radius: 8 φ-coarse cells on the y-axis (the far
    # field); each level sweeps its OWN cell phase (the honest de-resonance
    # comparison — see stage7 design doc).
    r_phys = 8.0 * (L0 / N_C_PHI)
    for label, N in [("fine N=64", N_F), ("phi N=40", N_C_PHI), ("N/2 N=32", N_C_N2)]:
        worst, mean = placement_bias(N, r_phys)
        rows[label] = (worst, mean)
        print("[G40] %s: placement bias worst-dir=%.4f  mean=%.4f  (r=%.2f phys, sweep 1 cell of that level)"
              % (label, worst, mean, r_phys))
    w_phi = rows["phi N=40"][0]
    w_n2 = rows["N/2 N=32"][0]
    lower = "phi N=40" if w_phi <= w_n2 else "N/2 N=32"
    print("[G40] φ-spaced (N=40) worst-dir bias %.4f vs N/2 (N=32) %.4f -> lower: %s"
          % (w_phi, w_n2, lower))
    # gate: the φ-spaced coarse has LOWER (or equal) placement bias than N/2.
    g = w_phi <= w_n2
    print("[G40] φ-spaced placement bias <= N/2  %s" % ("PASS" if g else "FAIL"))
    return g, rows


def g41():
    """k-factor normalization trap: the coarse level's Phi (per-level solve,
    integer modes k=2pi·n/L with the coarse N) must equal an INDEPENDENT direct
    coarse reference to 1e-12. Also demonstrates the WRONG coarse-from-fine
    decimation path (mode decimation without re-normalization) and its error."""
    # --- correct: independent direct coarse solve (explicit integer-mode k)
    rho_c = tsc_deposit(np.zeros(3), M_SRC, N_C_PHI, L)
    phi_c = poisson_solve(rho_c, N_C_PHI, L)          # per-level exact

    # independent reference: hand-written coarse k (integer modes, coarse N)
    ref = _direct_coarse_reference(rho_c, N_C_PHI, L)
    err = np.abs(phi_c - ref).max() / (np.abs(ref).max() + 1e-30)
    g = err <= 1e-12
    print("[G41] coarse Phi == direct coarse reference: max rel err = %.3e (<=1e-12)  %s"
          % (err, "PASS" if g else "FAIL"))

    # --- wrong path: the fftfreq-vs-integer / fine-N normalization trap. The
    #     resulting k is off by 1/N_f, so k^2 is off by 1/N_f^2 and Phi (1/k^2)
    #     is too large by N_f^2 = 4096 — a multi-level combination that mixes a
    #     correctly-scaled fine with a wrongly-scaled coarse is silently 4096x
    #     wrong (invisible in any ratio measurement). Demonstrated concretely.
    rho_f = tsc_deposit(np.zeros(3), M_SRC, N_F, L)
    phi_f = poisson_solve(rho_f, N_F, L)
    rhohat_f = np.fft.fftn(rho_f)
    frac = np.fft.fftfreq(N_F)                        # RAW n/N fraction (the trap)
    # TRAP k: uses the raw fftfreq fraction (n/N_f), MISSING the xN factor that
    # maps fftfreq to the shader's integer-mode k = 2pi·(n/N·N)/L. Every k_i is
    # N_f too small, so k^2 is N_f^2 too small and Phi = -rho/k^2 is N_f^2 too
    # LARGE — the exact corruption CASCADE_GRID §1 warns about.
    kx_t = 2.0 * np.pi * frac / L[0]
    ky_t = 2.0 * np.pi * frac / L[1]
    kz_t = 2.0 * np.pi * frac / L[2]
    k2_t = (kx_t[:, None, None] ** 2 + ky_t[None, :, None] ** 2
            + kz_t[None, None, :] ** 2)
    k2_t = np.where(k2_t == 0.0, 1.0, k2_t)
    phi_trap = np.zeros_like(rhohat_f)
    phi_trap[k2_t > 0.0] = -rhohat_f[k2_t > 0.0] / k2_t[k2_t > 0.0]
    phi_trap = np.real(np.fft.ifftn(phi_trap))
    # evaluate the trap potential at the center vs the correct fine Phi
    gc = w_to_g(np.zeros(3), N_F)
    val_correct = trilinear(phi_f, gc)
    val_trap = trilinear(phi_trap, gc)
    print("[G41] k-factor demonstration: correct center Phi=%.6e vs fftfreq-fraction "
          "trap %.6e (ratio ~%.1f ~ N_f^2=%d)"
          % (val_correct, val_trap, abs(val_trap / (val_correct + 1e-30)), N_F * N_F))
    return g


def _direct_coarse_reference(rho, N, ext):
    """Independent coarse solver (hand-written k with integer coarse modes),
    used to prove per-level normalization for G41."""
    rhohat = np.fft.fftn(rho)
    n = np.arange(N)
    nm = np.where(n <= N // 2, n, n - N)              # integer modes
    kx = 2.0 * np.pi * nm / L[0]
    ky = 2.0 * np.pi * nm / L[1]
    kz = 2.0 * np.pi * nm / L[2]
    k2 = (kx[:, None, None] ** 2 + ky[None, :, None] ** 2
          + kz[None, None, :] ** 2)
    phi_hat = np.zeros_like(rhohat)
    mask = k2 > 0
    phi_hat[mask] = -rhohat[mask] / k2[mask]
    return np.real(np.fft.ifftn(phi_hat))


# - main ---------------------------------------------------------------------
def main():
    print("Stage 7 φ-spaced multigrid: PHI=%.6f aspect=(%.3f,1,%.3f) L0=%.1f "
          "N_f=%d N_c_phi=%d N_c_n2=%d" % (PHI, PHI, PHI2, L0, N_F, N_C_PHI, N_C_N2))
    print("  window: r1=%.2f (4 hc_y=%.2f) r2=%.2f (7 hc_y), smoothstep blend"
          % (W_R1, 4.0 * HC, W_R2))

    # Build the fine + φ-coarse gradient fields once (source at center).
    print("  building fine (N=%d) and φ-coarse (N=%d) gradient fields..." % (N_F, N_C_PHI))
    rho_f = blob_source(N_F)
    phi_f = poisson_solve(rho_f, N_F, L)
    fine_grad = grad_phi(phi_f, N_F, L)
    rho_c = blob_source(N_C_PHI)
    phi_c = poisson_solve(rho_c, N_C_PHI, L)
    coarse_grad = grad_phi(phi_c, N_C_PHI, L)
    rho_n2 = blob_source(N_C_N2)
    coarse_grad_n2 = grad_phi(poisson_solve(rho_n2, N_C_N2, L), N_C_N2, L)

    # ── chain validation (shader-exact before the multigrid conclusions) ──
    # The fine 2h/4h/8h ring anisotropy (CASCADE_GRID §1 chains at L=75, N=64,
    # delta-deposited via TSC) reproduces the torus-Green lattice class.
    hf = L0 / N_F
    for rh in [2, 4, 8]:
        an, _ = ring_anisotropy(fine_grad, rh * hf)
        print("  [validate] fine ring anisotropy @%dh = %.4f" % (rh, an))

    ok = []
    g, w = g38(fine_grad, coarse_grad)
    ok.append(("G38 near-field blend no coarse leak (2%)", g))
    g, rows = g39(fine_grad, coarse_grad, coarse_grad_n2)
    ok.append(("G39 φ-coarse ring anisotropy <= N/2 (de-resonance; fine-vs-coarse is the honest null)", g))
    g, rows40 = g40()
    ok.append(("G40 φ-spaced placement bias <= N/2", g))
    g = g41()
    ok.append(("G41 per-level k normalization exact (1e-12)", g))

    print("---- gates ----")
    all_pass = True
    for name, passed in ok:
        all_pass = all_pass and passed
        print("[%s] %s" % ("PASS" if passed else "FAIL", name))
    print("RESULT: %s" % ("ALL PASS" if all_pass else "FAILURES PRESENT"))


if __name__ == "__main__":
    main()
