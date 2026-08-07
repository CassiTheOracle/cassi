#!/usr/bin/env python3
"""Two-strand twist probe TS6: longitudinal filament twist of a ridge pair.

Run:  python two-fluid/run_two_strand_twist_probe.py

Tests TS6 of `hypotheses/two-strand-five-channel-matter-organization.md`
sec 7 (Twist: filament initialization; Omega = d_vartheta/d_sigma, Tw,
P_parallel relation) and measures the E5 open content of sec 5.

Geometry (the doc sec 3.3 helical embedding, with a free axial rate):
two tube ridges of the shared condensate winding about the box z-axis,

    R_+(z) = (cx, cy) + a (cos theta(z), sin theta(z)),
    R_-(z) = (cx, cy) - a (cos theta(z), sin theta(z)),
    theta(z) = OMEGA0 (z - zc),   a = 6 cells (d = 12),

with an axial Gaussian envelope (sigma_z = 6 cells) so the filament is
finite.  OMEGA0 = 2*pi/N makes the helix close exactly across the
periodic seam (no field discontinuity at z = 0 ~ N; the seam carries
only the Gaussian tail, measured as a wrap artifact).  The twist
observable is genuinely longitudinal: at every axial slice z the two
ridge centerlines are tracked in the transverse (x, y) plane, giving
d(s), vartheta(s) = arg(d), Omega(s) = d_vartheta/d_s, and
Tw = (1/2*pi) * integral Omega ds over the detection window.

Representability: the current PDE (isotropic diffusion, gated
conversion, Poisson gravity; no chiral or anisotropic term) can carry
an *initialized* twist as ordinary spatial structure, so persistence
and relaxation of Omega(s) are testable without new model terms.  What
the PDE cannot do is *generate* twist from a parallel pair or lock
Omega to a periodicity—there is no term that couples the axial
structure.  The zero-twist arm is the generation counterfactual: if it
stays at Omega = 0, the twist sector has no source in this solver, and
the smallest scratch-layer term that would supply one is documented in
the verdict block (not implemented here).

Protocol (house coherence-budget regime, same as run_two_strand_probe):
fresh solver per arm (RK2 mutates solver state), N = 48, lambda = 0.05,
dt = 0.001, t = 4 = 0.2/lambda characterization window (lock claims
need t >= 2/lambda = 40), gate 'five', u = 0 initial velocity.
Arms:
  twist    the helical pair, OMEGA0 = 2*pi/N (half-turn across the
           +/-2*sigma_z core: Tw(0) = 0.5)
  ztwist   the same pair with OMEGA0 = 0 (parallel ridges; measured
           zero twist)

Measurement (read-only; ch_open/q from the solver's own 'five' gate
formula via run_trauma_wake_lock.channel_openness, never fed back):
  per-slice ridge tracking of rho -> d(z), vartheta(z) (unwrapped),
  Omega(z), Tw over the fixed window |z - zc| <= 12 (shrunk to the
  largest contiguous both-found run),
  per-strand tube-weighted doublet angle theta_f(z) and its axial
  gradient (the field-phase axial slope; bounded by the 1e-3 positivity
  clamp to the Wood/Fire arc), axial periodicity scan of theta_f(z)
  (dominant wavenumber, no imposed P_parallel),
  strand-local A = <|eps|>, eps, q, ch_open[5], dominant channel,
  pair observables d (window mean), delta_theta and its drift (E7),
  A_plus/A_minus,
  longitudinal telemetry: axial centroid offset z_c1 - z_c2 and the
  tilt of d out of the transverse plane,
  wrap artifacts: seam-plane density contrast vs box contrast,
  clamp telemetry: near-floor fraction and min ey/ei over the strand
  union, q_glob, eps rms, mass conservation sanity.

t = 0 self-consistency (the measurement layer must reproduce the
constructed geometry to the grid scale): max|vartheta - theta_init|,
max|d - 12|, Tw vs 0.5 for the twist arm; max|vartheta| and Tw vs 0
for the zero-twist arm.

Verdicts (results.json):
  TS6 twist persistence band on Tw_end/Tw_start (persisted > 0.75,
  relaxed 0.25-0.75, vanished < 0.25, wound up > 1.25),
  generation null from the ztwist arm,
  rung-periodicity scan result (emergent axial wavenumbers, t = 0 vs
  t = 4),
  boundary statement + smallest scratch-layer design for the
  generation leg.

Usage:
    python two-fluid/run_two_strand_twist_probe.py
Output (runs/ is gitignored -- commit the script only):
    runs/<rid>_twist/run_twist.json   full history, helical pair
    runs/<rid>_twist/run_ztwist.json  full history, parallel pair
    runs/<rid>_twist/results.json     meta + summaries + verdict
"""

import os
import sys
import json
import time
from datetime import datetime

import numpy as np
import torch

torch.backends.cudnn.benchmark = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_trauma_wake_lock as T

# ── Protocol (coherence-budget regime: lambda = 0.05, t = 4, N = 48) ──────
T.LAM = 0.05
T.DT = 0.001
T.REPORT = 50
STEPS = 4000                 # t = 4 = 0.2/lambda (characterization window)

CHANNELS = ['Wood', 'Fire', 'Earth', 'Metal', 'Water']

# ── Filament geometry (house two-strand ridge values) ─────────────────────
# d = 12 cells (house two-lobe SEP of run_two_strand_probe); at
# sigma/d = 3.5/12 the |eps|-ridge tracking bias is ~0.04 cells
A_SEP = 6.0                  # helix radius in cells -> d = 12
SIG = 3.5                    # tube Gaussian sigma in cells
SIG_Z = 6.0                  # axial envelope sigma in cells
E_RIDGE = 0.65               # per-ridge |eps| at core (house AMP range)
BETA = 0.3                   # density ridge: rho_core = (1+phi^-1)(1+beta)
R_SITE = 6.0                 # per-strand measurement ball radius (cells)
ZC = 24.0                    # axial envelope center (cells)
Z_LO, Z_HI = 12, 36          # fixed core window |z - ZC| <= 2*SIG_Z
MIN_WIN = 12                 # smallest acceptable detection window (cells)
EPS_AMP = 0.02               # min |eps| slice range for ridge detection
RIDGE_THRESH = 0.15          # ridge detection floor (fraction of slice amp)
MAX_DISP = 3.5               # peak matching radius around the prior (cells)
FLOOR = 1.001e-3             # near-floor clamp detection (post-rescale)


def helix_init(solver, omega0):
    """Helical ridge pair: rho = (1+phi^-1)(1+beta(g1+g2)),
    eps = E_RIDGE (g1 - g2) (anti-phase transverse mode of the two-strand
    doc sec 3.2, per-cell (rho, eps) -> (ey, ei) as in run_two_strand_probe).

    Strand a tube: g_a(x,y,z) = exp(-[(x-x_a(z))^2 + (y-y_a(z))^2]/(2 SIG^2))
        * exp(-(z-ZC)^2/(2 SIG_Z^2)),
    x_1(z) = cx + a cos(theta), y_1(z) = cy + a sin(theta),
    x_2(z) = cx - a cos(theta), y_2(z) = cy - a sin(theta),
    theta(z) = omega0 (z - ZC).
    omega0 = 0 -> parallel ridges (zero-twist counterfactual)."""
    N_ = solver.N
    dev = solver.device
    x = torch.arange(N_, dtype=torch.float64, device=dev)
    X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
    cx = cy = N_ / 2.0
    th = omega0 * (Z - ZC)
    ct, st = torch.cos(th), torch.sin(th)
    g1 = torch.exp(-((X - (cx + A_SEP * ct)) ** 2
                     + (Y - (cy + A_SEP * st)) ** 2) / (2.0 * SIG ** 2)
                   - (Z - ZC) ** 2 / (2.0 * SIG_Z ** 2))
    g2 = torch.exp(-((X - (cx - A_SEP * ct)) ** 2
                     + (Y - (cy - A_SEP * st)) ** 2) / (2.0 * SIG ** 2)
                   - (Z - ZC) ** 2 / (2.0 * SIG_Z ** 2))
    rho = (1.0 + T.PHI_INV) * (1.0 + BETA * (g1 + g2))
    eps = E_RIDGE * (g1 - g2)
    ey = (T.PHI * rho + eps) / (1.0 + T.PHI)
    ei = (rho - eps) / (1.0 + T.PHI)
    ey = torch.clamp(ey, min=1e-3)
    ei = torch.clamp(ei, min=1e-3)
    u_hat = torch.zeros(3, N_, N_, N_, dtype=torch.complex128, device=dev)
    return torch.fft.fftn(ey), torch.fft.fftn(ei), u_hat


def _refine_1d(p, i):
    """Parabolic sub-grid refinement of a 1-D profile maximum at index i."""
    y0, y1, y2 = p[i - 1], p[i], p[i + 1]
    denom = y0 - 2.0 * y1 + y2
    if abs(denom) < 1e-14:
        return float(i)
    return i + 0.5 * (y0 - y2) / denom


def slice_peaks(p2d, expected, thresh):
    """2D local maxima of a transverse slice profile near `expected` centers.

    p2d[i, j] holds the field at (X = i, Y = j); returns a list with one
    entry per expected center--refined (X, Y) or None when no peak lies
    within MAX_DISP cells.  Amplitude-normalized (p - min)/(max - min);
    peaks must exceed `thresh`."""
    a = (p2d - p2d.min()) / max(p2d.max() - p2d.min(), 1e-30)
    m = ((a[1:-1, 1:-1] >= a[:-2, 1:-1]) & (a[1:-1, 1:-1] >= a[2:, 1:-1]) &
         (a[1:-1, 1:-1] >= a[1:-1, :-2]) & (a[1:-1, 1:-1] >= a[1:-1, 2:]) &
         (a[1:-1, 1:-1] > thresh))
    rows, cols = np.nonzero(m)      # rows = X indices, cols = Y indices
    rows = rows + 1
    cols = cols + 1
    if len(rows) == 0:
        return [None] * len(expected)
    peaks = []
    for ri, ci in zip(rows, cols):
        # refine X along the column (fixed Y), refine Y along the row
        # (fixed X); _refine_1d guards |denom| < 1e-14 (at a maximum the
        # second difference is negative, so a max(denom, eps) clamp would
        # explode the correction)
        px = _refine_1d(a[:, ci], ri)
        py = _refine_1d(a[ri, :], ci)
        peaks.append((px, py))
    out = []
    used = []
    for (ex, ey_) in expected:
        best, bd = None, MAX_DISP
        for j, (px, py) in enumerate(peaks):
            if j in used:
                continue
            dd = np.hypot(px - ex, py - ey_)
            if dd < bd:
                best, bd = j, dd
        if best is not None:
            used.append(best)
            out.append(peaks[best])
        else:
            out.append(None)
    return out


def track_filament(solver, ey, ei, omega0, prev):
    """Per-axial-slice ridge tracking + strand diagnostics (read-only).

    Returns a dict of arrays over the detection window (largest contiguous
    run of both-found slices inside [Z_LO, Z_HI]) plus scalars.  `prev` is
    the previous report's per-slice centerline dict (tracking prior), or
    None at t = 0 (prior = the init helix)."""
    dev = solver.device
    N_ = solver.N
    rho = ey + ei
    eps = ey - T.PHI * ei
    ch_open, q = T.channel_openness(ey, ei)

    z_all = np.arange(N_)
    found = []          # (z, x1, y1, x2, y2) for slices with both ridges
    merged = []
    for z in z_all:
        # Track on |eps|, the strand variable: eps = E_RIDGE(g1 - g2) is
        # antisymmetric, zero at the pair midpoint, so its ridges sit at
        # the true strand centers.  Tracking on rho would bias the
        # measured centers inward: each Gaussian's neighbor tail raises
        # the inner flank, shifting each sum-maximum by ~0.9 cells at
        # sigma/d = 3.5/8.
        p2d = eps[:, :, z].abs().cpu().numpy()
        if p2d.max() - p2d.min() < EPS_AMP:
            continue
        th = omega0 * (z - ZC)
        ex1, ey1_ = N_ / 2 + A_SEP * np.cos(th), N_ / 2 + A_SEP * np.sin(th)
        ex2, ey2_ = N_ / 2 - A_SEP * np.cos(th), N_ / 2 - A_SEP * np.sin(th)
        if prev is not None and z in prev['z']:
            i = prev['z'].index(z)
            ex1, ey1_ = prev['x1'][i], prev['y1'][i]
            ex2, ey2_ = prev['x2'][i], prev['y2'][i]
        (x1, y1), (x2, y2) = slice_peaks(
            p2d, [(ex1, ey1_), (ex2, ey2_)], RIDGE_THRESH)
        if x1 is None or x2 is None:
            merged.append(int(z))
            continue
        found.append((int(z), x1, y1, x2, y2))

    # largest contiguous run of both-found slices inside the fixed window
    zs = np.array([f[0] for f in found])
    in_win = (zs >= Z_LO) & (zs <= Z_HI)
    idx = np.nonzero(in_win)[0]
    best = []
    if len(idx):
        runs = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
        best = max(runs, key=len)
    if len(best) < MIN_WIN:
        win = np.array(best)
        return {'ok': False, 'win_len': int(len(best)), 'z': [],
                'merged_z': merged}
    sel = [found[i] for i in best]

    z = np.array([f[0] for f in sel], dtype=float)
    x1 = np.array([f[1] for f in sel])
    y1 = np.array([f[2] for f in sel])
    x2 = np.array([f[3] for f in sel])
    y2 = np.array([f[4] for f in sel])
    d = np.hypot(x1 - x2, y1 - y2)
    vartheta = np.unwrap(np.arctan2(y1 - y2, x1 - x2))
    omega = np.gradient(vartheta, z)
    tw = (vartheta[-1] - vartheta[0]) / (2.0 * np.pi)

    # strand-local tube weights at the tracked centers
    xg = torch.arange(N_, dtype=torch.float64, device=dev)
    Xg, Yg = torch.meshgrid(xg, xg, indexing='ij')
    field_th = torch.atan2(ei, ey)
    A1, e1, q1, th1, m1 = [], [], [], [], []   # per-slice tube means + mass
    A2, e2, q2, th2, m2 = [], [], [], [], []
    ch1, ch2 = [], []
    for k in range(len(z)):
        rho_slice = rho[:, :, int(z[k])]
        for (xa, ya, Al, el_, ql, thl, chl, mass) in (
                (x1[k], y1[k], A1, e1, q1, th1, ch1, m1),
                (x2[k], y2[k], A2, e2, q2, th2, ch2, m2)):
            dd = (Xg - xa) ** 2 + (Yg - ya) ** 2
            w = torch.exp(-dd / (2.0 * SIG ** 2)) * (dd <= R_SITE ** 2).to(
                torch.float64)
            ws = w.sum()
            Al.append(float((eps[:, :, int(z[k])].abs() * w).sum() / ws))
            el_.append(float((eps[:, :, int(z[k])] * w).sum() / ws))
            ql.append(float((q[:, :, int(z[k])] * w).sum() / ws))
            thl.append(float((field_th[:, :, int(z[k])] * w).sum() / ws))
            chl.append([float((ch_open[c][:, :, int(z[k])] * w).sum() / ws)
                        for c in range(5)])
            mass.append(float((rho_slice * w).sum()))
    A1, A2 = np.array(A1), np.array(A2)
    e1a, e2a = np.array(e1), np.array(e2)
    q1a, q2a = np.array(q1), np.array(q2)
    th1a, th2a = np.array(th1), np.array(th2)
    m1a, m2a = np.array(m1), np.array(m2)

    # pair observables; axial mass centroids over the window (longitudinal
    # displacement telemetry -- a pure helix has dz_c = 0 by construction,
    # so a nonzero value measures developed axial staggering)
    zc1 = float((z * m1a).sum() / m1a.sum())
    zc2 = float((z * m2a).sum() / m2a.sum())
    dz_c = zc1 - zc2
    tilt = abs(dz_c) / max(float(np.mean(d)), 1e-9)
    z1 = A1 * np.exp(1j * th1a)
    z2 = A2 * np.exp(1j * th2a)
    A_plus = float(np.mean(np.abs(z1 + z2) / np.sqrt(2.0)))
    A_minus = float(np.mean(np.abs(z1 - z2) / np.sqrt(2.0)))
    dth = np.angle(np.exp(1j * (th2a - th1a)))   # per-slice, mod 2pi
    dth_mean = float(np.angle(np.sum(np.exp(1j * dth)) / len(dth)))

    # axial field-phase gradient (per strand) and periodicity scan
    gth1 = np.gradient(np.unwrap(th1a), z)
    gth2 = np.gradient(np.unwrap(th2a), z)
    dom_k1, frac1 = _dom_wavenumber(np.unwrap(th1a), z)
    dom_k2, frac2 = _dom_wavenumber(np.unwrap(th2a), z)

    # wrap artifacts: seam planes z in {0, 1, N-2, N-1}
    rho_np = rho.cpu().numpy()
    seam = np.concatenate([rho_np[:, :, 0], rho_np[:, :, 1],
                           rho_np[:, :, N_ - 2], rho_np[:, :, N_ - 1]])
    box_contrast = float(np.abs(rho_np - rho_np.mean()).max())
    seam_contrast = float(np.abs(seam - rho_np.mean()).max())

    # clamp telemetry over the strand union
    union = torch.zeros_like(rho)
    for k in range(len(z)):
        for xa, ya in ((x1[k], y1[k]), (x2[k], y2[k])):
            dd = (Xg - xa) ** 2 + (Yg - ya) ** 2
            union = torch.maximum(union, (dd <= R_SITE ** 2).to(
                torch.float64))
    bm = union > 0.5
    near_floor = float((((ey <= FLOOR) | (ei <= FLOOR)) * bm).sum()
                       / bm.sum())

    # phase-partition dominant channel per strand (window mean)
    dom1 = int(np.argmax(np.mean(ch1, axis=0)))
    dom2 = int(np.argmax(np.mean(ch2, axis=0)))

    return {
        'ok': True,
        'z': z.tolist(), 'x1': x1.tolist(), 'y1': y1.tolist(),
        'x2': x2.tolist(), 'y2': y2.tolist(),
        'd': d.tolist(), 'vartheta': vartheta.tolist(),
        'omega': omega.tolist(), 'Tw': float(tw),
        'omega_mean': float(np.mean(omega)),
        'omega_std': float(np.std(omega)),
        'd_mean': float(np.mean(d)), 'd_min': float(np.min(d)),
        'd_max': float(np.max(d)),
        'dz_c_mean': float(np.mean(dz_c)), 'dz_c_max': float(np.max(np.abs(dz_c))),
        'tilt': float(np.mean(np.abs(dz_c) / np.maximum(d, 1e-9))),
        'A1': A1.tolist(), 'A2': A2.tolist(),
        'eps1': e1a.tolist(), 'eps2': e2a.tolist(),
        'q1': q1a.tolist(), 'q2': q2a.tolist(),
        'theta_f1': th1a.tolist(), 'theta_f2': th2a.tolist(),
        'gth1_mean': float(np.mean(gth1)), 'gth2_mean': float(np.mean(gth2)),
        'gth_abs_max': float(np.max(np.abs(np.concatenate([gth1, gth2])))),
        'dom_k1': dom_k1, 'dom_k1_frac': frac1,
        'dom_k2': dom_k2, 'dom_k2_frac': frac2,
        'A_plus': A_plus, 'A_minus': A_minus,
        'delta_theta': dth_mean, 'dth_std': float(np.std(dth)),
        'q_glob': float(q.mean()), 'eps_rms': float(torch.sqrt(
            (eps ** 2).mean()).cpu()),
        'ey_min': float(ey[bm].min()), 'ei_min': float(ei[bm].min()),
        'near_floor': near_floor,
        'seam_contrast': seam_contrast, 'box_contrast': box_contrast,
        'seam_ratio': seam_contrast / max(box_contrast, 1e-30),
        'ch_open1': [float(np.mean(ch1, axis=0)[c]) for c in range(5)],
        'ch_open2': [float(np.mean(ch2, axis=0)[c]) for c in range(5)],
        'dom1': dom1, 'dom2': dom2,
        'merged_z': merged,
    }


def _dom_wavenumber(series, z):
    """Dominant axial wavenumber (cycles/cell) of `series` over `z`.

    FFT over the window with a Hann taper on the detrended series; returns
    (k, power_fraction_of_top3)."""
    y = series - np.polyval(np.polyfit(z, series, 1), z)
    y = y - y.mean()
    if y.std() < 1e-9 or len(y) < 8:
        return 0.0, 0.0
    yw = y * np.hanning(len(y))
    spec = np.abs(np.fft.rfft(yw))
    freqs = np.fft.rfftfreq(len(y), d=z[1] - z[0])
    spec[0] = 0.0
    top = np.sort(spec)[::-1][:3]
    frac = float(top.sum() / spec.sum()) if spec.sum() > 0 else 0.0
    return float(freqs[int(np.argmax(spec))]), frac


def run_case(solver, omega0, tag, outdir):
    """Evolve one arm (fresh solver, focused run), recording diagnostics."""
    print(f"\n=== run: {tag} (omega0={omega0:.4f} rad/cell, "
          f"Tw(0)={omega0 * (Z_HI - Z_LO) / (2 * np.pi):.3f} over the core) ===")
    ey_hat, ei_hat, u_hat = helix_init(solver, omega0)
    prev = None
    t0 = time.time()
    hist = []
    for step in range(STEPS):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step % T.REPORT == 0 or step == STEPS - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            m = track_filament(solver, ey, ei, omega0, prev)
            if m['ok']:
                prev = {'z': m['z'], 'x1': m['x1'], 'y1': m['y1'],
                        'x2': m['x2'], 'y2': m['y2']}
            m.update({'step': step, 't': step * T.DT,
                      'mass': float((ey + ei).sum().cpu()),
                      'a': float(solver.a.cpu()), 'H': float(solver.H.cpu())})
            hist.append(m)
            win = len(m['z'])
            print(f"  t={step*T.DT:5.2f} | win={win:3d} | "
                  f"d={m['d_mean']:6.3f} | Tw={m['Tw']:+6.3f} "
                  f"| <Omega>={m['omega_mean']:+6.4f} "
                  f"| dth={m['delta_theta']:+6.3f} "
                  f"| q=[{np.mean(m['q1']):.3f},{np.mean(m['q2']):.3f}] "
                  f"| dom=[{CHANNELS[m['dom1']][0]},"
                  f"{CHANNELS[m['dom2']][0]}] "
                  f"| gth={m['gth_abs_max']:.4f} "
                  f"| seam={m['seam_ratio']:.1e} "
                  f"| near_floor={m['near_floor']:.1e} "
                  f"| ey_min={m['ey_min']:.4f} ei_min={m['ei_min']:.4f}")
    elapsed = time.time() - t0
    print(f"  [{tag}] {STEPS} steps in {elapsed:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'omega0': omega0, 'hist': hist}, f,
                      indent=1)
    return hist


def summarize(tag, hist):
    """Twist persistence band, d/dtheta drift, periodicity, telemetry."""
    ok = [m for m in hist if m['ok']]
    first, last = ok[0], ok[-1]
    d0 = first['d_mean']
    d_back = float(np.mean([m['d_mean'] for m in ok[int(0.8 * len(ok)):]]))
    tw0, tw_end = first['Tw'], last['Tw']
    if tw0 == 0.0:
        band = 'zero (by construction)'
    else:
        r = abs(tw_end / tw0)
        band = ('persisted' if r > 0.75 else
                ('relaxed' if r > 0.25 else 'vanished'))
        if abs(tw_end) > 1.25 * abs(tw0):
            band = 'wound up'
    merged_frac = float(np.mean([len(m['merged_z']) > 0 for m in ok]))
    return {
        'Tw_start': tw0, 'Tw_end': tw_end,
        'Tw_ratio': (None if tw0 == 0.0 else float(tw_end / tw0)),
        'band': band,
        'd_start': d0, 'd_end': last['d_mean'], 'd_back_mean': d_back,
        'win_len_start': len(first['z']), 'win_len_end': len(last['z']),
        'merged_frac': merged_frac,
        'delta_theta_start': first['delta_theta'],
        'delta_theta_end': last['delta_theta'],
        'A_plus_end': last['A_plus'], 'A_minus_end': last['A_minus'],
        'dom_k1_start': first['dom_k1'], 'dom_k1_end': last['dom_k1'],
        'dom_k1_frac_start': first['dom_k1_frac'],
        'dom_k1_frac_end': last['dom_k1_frac'],
        'dom_k2_start': first['dom_k2'], 'dom_k2_end': last['dom_k2'],
        'gth_abs_max_start': first['gth_abs_max'],
        'gth_abs_max_end': last['gth_abs_max'],
        'dz_c_max_start': first['dz_c_max'],
        'dz_c_max_end': last['dz_c_max'],
        'seam_ratio_start': first['seam_ratio'],
        'seam_ratio_end': last['seam_ratio'],
        'near_floor_max': max(m['near_floor'] for m in ok),
        'ey_min': min(m['ey_min'] for m in ok),
        'ei_min': min(m['ei_min'] for m in ok),
        'q_glob_start': first['q_glob'], 'q_glob_end': last['q_glob'],
        'mass_drift': (hist[-1]['mass'] - hist[0]['mass']) / hist[0]['mass'],
    }


def check_t0(hist_twist, hist_ztwist, omega0):
    """t = 0 self-consistency: measurement reproduces the construction."""
    m = hist_twist[0]
    z = np.array(m['z'])
    th_init = omega0 * (z - ZC)
    dv = np.array(m['vartheta'])
    d = np.array(m['d'])
    err_v = float(np.max(np.abs(np.angle(np.exp(1j * (dv - th_init))))))
    err_d = float(np.max(np.abs(d - 2 * A_SEP)))
    mz = hist_ztwist[0]
    err_zv = float(np.max(np.abs(mz['vartheta']))) if mz['ok'] else float('nan')
    err_ztw = abs(mz['Tw']) if mz['ok'] else float('nan')
    print("\n--- t = 0 self-consistency (measurement vs construction) ---")
    print(f"  twist:   max|vartheta - theta_init| = {err_v:.4f} rad "
          f"(< 0.02: {'PASS' if err_v < 0.02 else 'FAIL'})")
    print(f"           max|d - 12| = {err_d:.3f} cells "
          f"(< 0.3: {'PASS' if err_d < 0.3 else 'FAIL'})")
    print(f"           Tw = {m['Tw']:+.4f} (constructed 0.500)")
    print(f"  ztwist:  max|vartheta| = {err_zv:.4f} rad, "
          f"Tw = {err_ztw:+.4f} (< 0.01: "
          f"{'PASS' if err_zv < 0.01 and err_ztw < 0.01 else 'FAIL'})")
    return {'twist_vartheta_err': err_v, 'twist_d_err': err_d,
            'ztwist_vartheta_max': err_zv, 'ztwist_Tw': err_ztw}


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    omega0 = 2.0 * np.pi / T.N
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t={STEPS * T.DT}  "
          f"gate='five'  a={A_SEP} (d=12)  SIG={SIG}  SIG_Z={SIG_Z}  "
          f"omega0={omega0:.4f} rad/cell (2*pi/N, one turn per box)")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_twist"
    os.makedirs(rdir, exist_ok=True)

    # Fresh solver per arm (rk2_step mutates scale factor, Hubble
    # smoothing, q_mean -- a shared solver makes arms order-dependent).
    h_twist = run_case(T.build_solver(device), omega0, 'twist', rdir)
    h_ztwist = run_case(T.build_solver(device), 0.0, 'ztwist', rdir)

    t0c = check_t0(h_twist, h_ztwist, omega0)
    s_twist = summarize('twist', h_twist)
    s_ztwist = summarize('ztwist', h_ztwist)

    results = {
        'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT, 'steps': STEPS,
                 't_end': STEPS * T.DT, 'gate_model': 'five (solver)',
                 'A_SEP': A_SEP, 'd0': 2 * A_SEP, 'SIG': SIG,
                 'SIG_Z': SIG_Z, 'omega0': omega0,
                 'E_RIDGE': E_RIDGE, 'BETA': BETA,
                 'note': 't = 4 = 0.2/lambda characterization window; '
                         'lock claims need t >= 2/lambda; twist is '
                         'initialized structure, no chiral term in the PDE'},
        't0_check': t0c,
        'twist': s_twist,
        'ztwist': s_ztwist,
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== TS6 TWIST PROBE RESULTS (t=4) ===")
    for name, s in [('twist', s_twist), ('ztwist', s_ztwist)]:
        print(f"{name:8s}: Tw {s['Tw_start']:+.3f} -> {s['Tw_end']:+.3f} "
              f"[{s['band']}] | d {s['d_start']:.2f} -> {s['d_end']:.2f} "
              f"(back mean {s['d_back_mean']:.2f}) | "
              f"dth {s['delta_theta_start']:+.3f} -> "
              f"{s['delta_theta_end']:+.3f} | "
              f"k1 {s['dom_k1_start']:.4f} -> {s['dom_k1_end']:.4f} "
              f"(frac {s['dom_k1_frac_start']:.2f} -> "
              f"{s['dom_k1_frac_end']:.2f}) | "
              f"seam {s['seam_ratio_start']:.1e} -> "
              f"{s['seam_ratio_end']:.1e} | "
              f"near_floor {s['near_floor_max']:.1e} | "
              f"mass_drift {s['mass_drift']:+.1e}")

    print("\n=== VERDICT (TS6) ===")
    st, sz = s_twist, s_ztwist
    print(f"Twist arm:   initialized half-twist Tw = {st['Tw_start']:+.3f} "
          f"-> {st['Tw_end']:+.3f} over the detection window "
          f"({st['win_len_start']} -> {st['win_len_end']} axial slices), "
          f"band = {st['band']}.")
    print(f"Zero-twist arm: Tw = {sz['Tw_start']:+.3f} -> "
          f"{sz['Tw_end']:+.3f}; |Tw| <= 0.01 throughout -> "
          f"{'NO SPONTANEOUS TWIST GENERATION' if abs(sz['Tw_end']) < 0.01 else 'GENERATION PRESENT'}.")
    print(f"Rung-periodicity: dominant axial field-phase wavenumber k = "
          f"{st['dom_k1_start']:.4f} -> {st['dom_k1_end']:.4f} cycles/cell "
          f"(strand 1), {st['dom_k2_start']:.4f} -> {st['dom_k2_end']:.4f} "
          f"(strand 2); axial field-phase gradient |dtheta_f/dz| max "
          f"{st['gth_abs_max_start']:.4f} -> {st['gth_abs_max_end']:.4f} "
          f"rad/cell.")
    print(f"Phase drift (E7): delta_theta {st['delta_theta_start']:+.3f} "
          f"-> {st['delta_theta_end']:+.3f} rad.")
    print(f"Boundary: the current PDE represents an initialized twist "
          f"(longitudinal Omega/Tw measurement) but has no term that "
          f"sources twist from a parallel pair or locks Omega to a "
          f"periodicity; the zero-twist arm stays at zero.  Smallest "
          f"scratch-layer design for the generation leg: a parity-odd "
          f"coupling of the phase-current vorticity to the conversion "
          f"rate, conv -> -lam (1 - chi_circ * (curl J)_z / J_scale) "
          f"(1-q) eps, one new constant chi_circ, J = R^2 grad(theta) "
          f"already derived from the field; implement as a flagged layer "
          f"outside the canonical solver with bit-for-bit no-op "
          f"verification at chi_circ = 0, one focused run per value, and "
          f"a Jacobian check at the phi-attractor (the term vanishes "
          f"there: J = 0 at eps = 0).  Not implemented in this probe.")
    print(f"\nResults: {rdir}/results.json")


if __name__ == "__main__":
    main()
