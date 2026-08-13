#!/usr/bin/env python3
"""Bubble ring-ladder probe (DYNAMIC realization, spatial-coupling arms):
does the canonical two-fluid solver DYNAMICALLY realize the radial
matter-ring ladder predicted for a bubble (Prediction 51) under finite
spatial coupling?

Run:  python two-fluid/run_bubble_ring_dynamic_probe.py
      (--steps N; --epochs "t1,t2,..."; --arms "A,B,C,W" to restrict)

NOTE ON NAMING / PARALLEL WORKSTREAM (2026-08-12): the sibling file
two-fluid/run_bubble_ring_probe.py is owned by a parallel worker and contains
the ANALYTIC ring-law verification (Leg A/B/C: matter at ell_n*phi^-k, voids
at ell_n*phi^-(k+1/2), the phase-quantized envelope rho ~ cos^2(pi u),
count N = ln100/lnphi ~ 10 -- the kinematic content, "what a simulated
bubble must show").  THIS file (run_bubble_ring_dynamic_probe.py) tests the
OPEN, distinct content: whether the two-fluid PDE DYNAMICALLY realizes the
ladder from a standing spherical condensate in the canonical solver.  The two
must be cited to different names.

Why multiple arms (rev 2): the original single arm (D=0, nu=0, u=0, chi=0,
cs2=0 -- qi-gated conversion only) had NO spatial coupling of any kind, so
stands no chance of forming ring structure regardless of the ring law.  Rev 2
adopts the canonical solver's spatial-coupling terms (same seed, same epochs,
identical pre-registered decision tree per arm) to test whether any canonical
coupling channel dynamically realizes the ladder:

  Arm A (baseline null):  D=0,  nu=0,  cs2=0  (conversion-only; re-run for a
                          clean co-located record -- the 2026-08-13 NO RINGS)
  Arm B (diffusion):      D=0.0002, nu=0, cs2=0  (scalar diffusion; canonical
                          probe value: run_trauma_wake_lock / run_pde_wa_5ch
                          / run_pde_wa_test use D=0.0002)
  Arm C (gravity):        D=0, nu=0.0005, cs2=0  (the canonical gravity path:
                          the intrinsic Poisson-buoyancy force Pi grad_Phi
                          sources the velocity field which advects the fields;
                          nu=0.0005 is the canonical probe viscosity that lets
                          the gravity-driven velocity stay finite/stabilized.
                          chi is 0 because the solver codes the chi chemotaxis
                          density-flux as the source of all chi>0 instabilities
                          and every committed probe sets chi=0)
  Arm W (wave-verify):    D=0.0002, nu=0.0005, cs2=0.5  (closest wave-like
                          coupling the canonical first-order solver has:
                          cs2 is a velocity pressure-gradient force -cs2 grad rho;
                          used to answer the wave-mode question empirically)

WAVE-MODE VERIFICATION (committed solver): ExpandingTwoFluid3DGPU.rhs is a
FIRST-ORDER-in-time advection/diffusion/conversion (+ velocity) PDE advanced
by RK2 -- there is NO second-order-in-time term d^2 E / dt^2 = c^2*.Laplace E
- w0^2 (E_Y - phi E_I).  cs2 enters only as -cs2*grad rho on the VELOCITY RHS
(force), not as a density wave operator.  Therefore the FULL dynamical form of
the ring law (the owner's space-sim second-order wave equation
d^2 E = c^2 grad^2 E - w0^2 (E_Y - phi E_I), which carries the phi-anchored
resonance and is what actually produces the observed radial rings) is NOT in
this committed solver; Arm W below tests the closest available proxy (cs2
pressure-driven velocity), and the full second-order realization belongs to
the space-sim's GLSL PDE (physics/godot/space-sim), not to this file.

Tier Hypothesized: the ring law is kinematic -- doublet radial phase
alpha = pi*log_phi(r/l_n) + pool-cell parities (matter rings at integer
rungs, void troughs at half-rungs, `foundations/spin-fibonacci-spiral.md`,
`foundations/rung-offset-mechanism.md` sec 4.1).  A bubble carries a radial
ring ladder: matter rings at r_k = R*phi^-k, void troughs at
R*phi^-(k+1/2), successive matter-ring ratio phi^-1 = 0.6180 (null:
phi^-1/2 = 0.7862), ~10 matter ridges at the 1% contrast floor, strict
matter/void alternation.

THE OPEN QUESTION THIS PROBE TESTS: whether the PDE DYNAMICALLY realizes the
ladder from a standing spherical condensate in the canonical solver, GIVEN
each available spatial-coupling channel.  An honest null is a valid outcome.

============================================================================
PRE-REGISTRATION  (decision tree -- identical, per arm, verbatim)
============================================================================
Seed: a spherical standing condensate at the reference state (E_Y = 1,
E_I = phi^-1 interior, dilute exterior), radius R ~ several cells, in the
canonical solver (N = 64 or 96, L = 2*pi, dt = 0.001, lambda = 0.05,
qi_gate = True, gate single, D > 0 for some arms, no imposed velocity
u = 0 init).

Measurement: at the bubble epoch (t where the radial structure is
quasi-steady; probe several epochs), extract the radial profile of
rho(r) = E_Y+E_I (and q(r)) by azimuthal averaging around the field
centroid; identify local maxima (matter rings) and minima (voids) OUTSIDE
the core (r > ~4 cells, to avoid the core-contamination region); keep
maxima whose contrast vs the local mean exceeds a 1% floor.

Decision rule (applied identically to each selected epoch, then a primary
bubble epoch chosen from the late quasi-steady window [t/2, t_end] by max
matter-maximum count):
  (i)  if >= 3 successive matter-ring maxima are found, compute the
       successive radius ratios; if each lies within +/-0.08 of 0.6180 and
       OUTSIDE 0.7862 +/- 0.05 -> SUPPORTS the phi-ladder; if within
       0.7862 +/- 0.05 and outside 0.6180 +/- 0.08 -> SUPPORTS THE NULL
       (phi^-1/2); otherwise INDETERMINATE.
  (ii) The ring count: if 6-10 matter maxima -> consistent; if 1-2 -> the
       dynamic realization is weak or absent -- report honestly.
  (iii) Alternation: verify every matter maximum is separated from the next
       by exactly one minimum.

Honest outcomes all acceptable: SUPPORTS / SUPPORTS NULL / INDETERMINATE /
NO RINGS (dynamics does not realize the ladder) -- each with the numbers.

Arms (fresh solver per arm; same seed, same epochs; N = 64 default -- N = 96
is ~10x slower on this GPU (benchmarked 5.4 vs ~115 steps/s), so N = 64 is
used and noted):
  A  baseline null          D=0        nu=0      cs2=0
  B  diffusion              D=0.0002   nu=0      cs2=0
  C  gravity (buoyancy vel) D=0        nu=0.0005 cs2=0
  W  wave-verify (cs2)      D=0.0002   nu=0.0005 cs2=0.5
All: chi=0 (canonical; chemotaxis coded as the chi>0 instability source),
qi_gate=True (gate_model='single'), hubble_mode='conversion'.
============================================================================

Measurement regime notes: with u = 0 init and only the terms above active,
Arm A has zero spatial coupling (pure local conversion); Arm B adds spectral
scalar diffusion (can only smooth, cannot create extrema); Arm C sources the
velocity via the Poisson buoyancy so advection can redistribute density;
Arm W adds the cs2 pressure (sound) force to the velocity, the closest
wave-like coupling in this first-order solver.  Whether rings EMERGE in each
is the tested content.

Radial extraction: per-cell distance m from the fixed centroid (N/2,N/2,N/2)
in cells; bin cells by integer shell; azimuthally average EY, EI,
rho = EY+EI, and q (via the solver's compute_q_field, same code path the
dynamics use).  Measurement radial rank m in [R_CORE, N/2 - 1]
(core-contamination cut R_CORE = 4 cells; the m -> N/2 far-side wrap region
is excluded).  Peaks/troughs found on a light Gaussian-smoothed profile
(sigma ~ 2 cells) by first-difference sign change with a prominence gate at
the 1% contrast floor.

Epochs: profiles recorded at t = 0, 2, 5, 8, 10, 15, 20, 40 and at the final
step; the primary (bubble) epoch is taken over the late quasi-steady window
(t in [t_end/2, t_end]) by max ring count, reported per-epoch and per-arm.

Output (runs/ is gitignored -- commit the script only):
  runs/<YYYYmmdd_HHMMSS>_bubble_ring_dynamic.json   full per-arm record
"""

import os
import sys
import json
import time
import math
import argparse
from datetime import datetime

import numpy as np
import torch

torch.backends.cudnn.benchmark = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI, PHI_INV

# ── Pre-registered protocol ─────────────────────────────────────────────
N = 64                  # dropped from 96 (10x slower on GPU; noted)
L = 2.0 * np.pi
DT = 0.001
LAM = 0.05
CHI = 0.0
HUBBLE_MODE = 'conversion'
QI_GATE = True
QI_MEMORY = False
STEPS = 40000           # t = 40 (2/lambda lock timescale)
EPOCHS = [0.0, 2.0, 5.0, 8.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0]
T_END = STEPS * DT

# Canonical spatial-coupling values (lattice-stack / wa probe family)
D_DIFF = 0.0002         # canonical scalar diffusion (run_trauma_wake_lock)
NU_GRAV = 0.0005        # canonical viscosity (stabilizes gravity-driven u)
CS2_WAVE = 0.5          # wave-verify sound-pressure coupling (closest proxy)

ARMS = [
    # tag, D, nu, cs2, desc
    ('A', 0.0, 0.0, 0.0, 'baseline null (conversion-only)'),
    ('B', D_DIFF, 0.0, 0.0, 'diffusion D=0.0002'),
    ('C', 0.0, NU_GRAV, 0.0, 'gravity buoyancy-velocity nu=0.0005'),
    ('W', D_DIFF, NU_GRAV, CS2_WAVE, 'wave-verify cs2=0.5 (closest proxy)'),
]

# Single-arm geometry for the bubble (same seed across all arms)
R_BUBBLE = 12.0         # bubble radius in cells (~1.18 length units)
SIGMA_EDGE = 2.5        # transition width (cells)
EY_INT = 1.0            # interior reference state E_Y
EI_INT = PHI_INV        # interior reference state E_I (= phi^-1, eps=0)
EY_EXT = 0.30           # dilute exterior
EI_EXT = 0.40           # exterior (ratio 0.75, Yin-excess eps~-0.35)
R_CORE = 4.0            # core-contamination cut (cells)
SMOOTH_SIGMA = 2.0      # radial-profile smoothing before peak finding (cells)
CONTRAST_FLOOR = 0.01   # 1% contrast floor vs local mean
PEAK_SEP = 1.0          # min separation between distinct maxima (cells)

# Decision-rule constants (verbatim from pre-registration)
RATIO_LADDER = PHI_INV          # 0.6180
RATIO_LADDER_TOL = 0.08         # +/- 0.08 of 0.6180
RATIO_NULL = math.sqrt(PHI_INV) # 0.7862 (phi^-1/2)
RATIO_NULL_TOL = 0.05           # +/- 0.05 of 0.7862
RING_COUNT_HI, RING_COUNT_LO = 10, 6
WEAK_RING_MAX = 2
MIN_RINGS_FOR_RATIO = 3

# Shared far-side-avoidance rank: measure radial ranks m in [0, N/2 - 1]
# (cells with m < N/2, i.e. within one box half-width of the centroid; the
# wrapped far-side cells with m >= N/2 are dropped).  All shells in
# [0, N/2-1] are populated, so no NaN shell remains.
_MAX_SHELL = N // 2


class SeedGrid:
    """Precomputed centroid-distance grid (shared across arms & extracts)."""

    def __init__(self, solver):
        N_ = solver.N
        dev = solver.device
        x = torch.arange(N_, dtype=torch.float64, device=dev)
        X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
        c = N_ / 2.0
        self.R = torch.sqrt((X - c) ** 2 + (Y - c) ** 2 + (Z - c) ** 2)
        self.m = self.R.long()
        self.shell_mask = self.m < _MAX_SHELL
        self.idx = self.m[self.shell_mask]


def build_solver(device, D, nu, cs2):
    """Fresh canonical solver per arm; single gate (constructor default)."""
    solver = ExpandingTwoFluid3DGPU(
        N=N, L=L, nu=nu, D=D, lam=LAM, chi=CHI, cs2=cs2,
        hubble_mode=HUBBLE_MODE, qi_gate=QI_GATE,
        qi_memory=QI_MEMORY, device=device)
    assert solver.gate_model == 'single'
    return solver


def bubble_init(grid):
    """Spherical standing condensate: reference-state interior, dilute
    exterior, smooth radial transition.  Returns ey_hat, ei_hat, u_hat."""
    f = 0.5 * (1.0 - torch.tanh((grid.R - R_BUBBLE) / SIGMA_EDGE))
    ey = EY_INT * f + EY_EXT * (1.0 - f)
    ei = EI_INT * f + EI_EXT * (1.0 - f)
    ey = torch.clamp(ey, min=1e-3)
    ei = torch.clamp(ei, min=1e-3)
    dev = ey.device
    u_hat = [torch.fft.fftn(torch.zeros(ey.shape, dtype=torch.float64,
                                         device=dev)) for _ in range(3)]
    return torch.fft.fftn(ey), torch.fft.fftn(ei), u_hat


def radial_profiles(solver, ey, ei, grid):
    """Azimuthal average about the centroid (N/2,N/2,N/2), in cell shells.

    Returns dict with arrays indexed by radial rank m = 0..N//2 - 1:
    r_cells (shell center), ey, ei, rho, q, and count per shell.
    q comes from the solver's own compute_q_field (same code path as the
    dynamics).  Periodic far-side shells (m near N//2) are excluded.
    """
    N_ = solver.N
    rho = ey + ei
    q, _ = solver.compute_q_field(ey, ei)
    idx = grid.idx
    shells = torch.arange(N_ // 2, dtype=torch.float64, device=ey.device)
    out = {}
    for name, field in (('ey', ey), ('ei', ei), ('rho', rho), ('q', q)):
        acc = torch.zeros(N_ // 2, dtype=torch.float64, device=ey.device)
        cnt = torch.zeros(N_ // 2, dtype=torch.float64, device=ey.device)
        acc.scatter_add_(0, idx, field[grid.shell_mask])
        cnt.scatter_add_(0, idx,
                         torch.ones(idx.shape, dtype=torch.float64,
                                    device=ey.device))
        out[name] = (acc / cnt).cpu().numpy()
    out['r_cells'] = (shells + 0.5).cpu().numpy()
    out['r_length'] = out['r_cells'] * (L / N_)
    return out


def gauss_smooth(y, sigma):
    """Gaussian smoothing over integer rank (edge-truncated, no wrap)."""
    grid = np.arange(len(y), dtype=np.float64)
    out = np.empty_like(y)
    for i in range(len(y)):
        w = np.exp(-0.5 * ((grid - i) / sigma) ** 2)
        out[i] = np.sum(w * y) / w.sum()
    return out


def local_mean(y, i, half=4):
    """Mean of the profile over a local window around index i (excluding i)."""
    lo = max(0, i - half)
    hi = min(len(y), i + half + 1)
    idx = [k for k in range(lo, hi) if k != i]
    if not idx:
        return y[i]
    return float(np.mean(y[idx]))


def find_structure(rho, r_cells, r_core=R_CORE, sigma=SMOOTH_SIGMA,
                   floor=CONTRAST_FLOOR):
    """Peak/trough extraction on the smoothed radial profile.
    Maxima must lie at r > r_core and pass the contrast-vs-local-mean floor.
    Troughs are recorded between consecutive maxima for the alternation
    check (informational; the decision rule gates on contrasting maxima).
    """
    mask = r_cells > r_core
    ysm = gauss_smooth(rho, sigma)
    ys = ysm[mask]
    rs = r_cells[mask]
    maxima, minima = [], []
    prev = ys[0]
    trend = 0  # 0 waiting, +1 rising, -1 falling
    for i in range(1, len(ys)):
        if ys[i] > prev:
            if trend <= 0:
                if i - 1 > 0:
                    minima.append(i - 1)
                trend = 1
        elif ys[i] < prev:
            if trend >= 0:
                if i - 1 > 0:
                    maxima.append(i - 1)
                trend = -1
        prev = ys[i]
    kept_max = []
    for k in maxima:
        abs_idx = int(np.where(mask)[0][k])
        lm = local_mean(ysm, int(abs_idx))
        contrast = (ys[k] - lm) / max(abs(lm), 1e-30)
        if abs(contrast) >= floor:
            if kept_max and (rs[k] - rs[kept_max[-1]]) < PEAK_SEP:
                continue
            kept_max.append(k)
    maxima = kept_max
    if len(maxima) >= 2:
        kept_min = []
        for mk in range(len(maxima) - 1):
            a, b = maxima[mk], maxima[mk + 1]
            between = [mi for mi in minima if a < mi < b]
            if between:
                m_best = min(between, key=lambda mi: ys[mi])
                kept_min.append(m_best)
        minima = kept_min
    else:
        minima = []

    def row(k, kind):
        abs_idx = int(np.where(mask)[0][k])
        lm = local_mean(ysm, abs_idx)
        return {
            'kind': kind,
            'r_cells': float(rs[k]),
            'r_norm': float(rs[k] / R_BUBBLE),
            'val': float(ys[k]),
            'local_mean': float(lm),
            'contrast': float((ys[k] - lm) / max(abs(lm), 1e-30)),
        }

    return [row(k, 'max') for k in maxima], [row(k, 'min') for k in minima]


def overall_verdict(max_rows, min_rows):
    """Apply the pre-registered decision tree (see module docstring)."""
    n_ring = len(max_rows)
    detail = {'n_matter_maxima': n_ring}

    alternation = None
    if n_ring >= 2:
        proper = True
        min_r = [m['r_cells'] for m in min_rows]
        for a, b in zip(max_rows[:-1], max_rows[1:]):
            between = sum(1 for mr in min_r if a['r_cells'] < mr < b['r_cells'])
            if between != 1:
                proper = False
        alternation = bool(proper)
    detail['alternation'] = alternation

    if RING_COUNT_LO <= n_ring <= RING_COUNT_HI:
        count_grade = 'consistent'
    elif n_ring <= WEAK_RING_MAX:
        count_grade = 'weak_or_absent'
    else:
        count_grade = 'borderline'
    detail['ring_count_grade'] = count_grade

    ratios = []
    for a, b in zip(max_rows[:-1], max_rows[1:]):
        r_out = b['r_cells'] / a['r_cells']
        r_in = a['r_cells'] / b['r_cells']
        ratios.append({'r_out': float(r_out), 'r_in': float(r_in)})
    detail['successive_ratios'] = ratios
    detail['ratio_out'] = [r['r_out'] for r in ratios]
    detail['ratio_in'] = [r['r_in'] for r in ratios]

    if n_ring < MIN_RINGS_FOR_RATIO:
        verdict = 'NO RINGS' if n_ring < 2 else 'INDETERMINATE'
        detail['why'] = (f'{n_ring} matter maxima < {MIN_RINGS_FOR_RATIO} '
                         f'needed for the ratio test; ring count {count_grade}')
    else:
        ratios_in = np.array(detail['ratio_in'])
        ladder_ok = bool(np.all(np.abs(ratios_in - RATIO_LADDER)
                                <= RATIO_LADDER_TOL))
        null_ok = bool(np.all(np.abs(ratios_in - RATIO_NULL)
                              <= RATIO_NULL_TOL))
        ladder_outside_null = bool(np.all(
            np.abs(ratios_in - RATIO_NULL) > RATIO_NULL_TOL))
        null_outside_ladder = bool(np.all(
            np.abs(ratios_in - RATIO_LADDER) > RATIO_LADDER_TOL))
        if ladder_ok and ladder_outside_null:
            verdict = 'SUPPORTS'
        elif null_ok and null_outside_ladder:
            verdict = 'SUPPORTS NULL'
        else:
            verdict = 'INDETERMINATE'
        detail['why'] = (f'{n_ring} matter maxima; inward ratios '
                         f'{np.round(ratios_in, 4).tolist()} vs ladder '
                         f'{RATIO_LADDER:.4f}+-{RATIO_LADDER_TOL} '
                         f'(null {RATIO_NULL:.4f}+-{RATIO_NULL_TOL}); '
                         f'ladder_ok={ladder_ok} null_ok={null_ok} '
                         f'ladder_excludes_null={ladder_outside_null} '
                         f'null_excludes_ladder={null_outside_ladder}; '
                         f'ring count {count_grade}; alternation={alternation}')
    return verdict, detail


def run_arm(device, tag, D, nu, cs2, grid, steps=STEPS, epochs=None):
    """Evolve one arm (fresh solver), recording per-epoch profiles."""
    if epochs is None:
        epochs = EPOCHS
    solver = build_solver(device, D, nu, cs2)
    ey_hat, ei_hat, u_hat = bubble_init(grid)
    t_targets = sorted(set(round(e, 6) for e in epochs))

    def extract(t, step, epoch_target):
        ey = torch.fft.ifftn(ey_hat).real
        ei = torch.fft.ifftn(ei_hat).real
        rp = radial_profiles(solver, ey, ei, grid)
        max_rows, min_rows = find_structure(rp['rho'], rp['r_cells'])
        return {
            't': round(t, 6), 'step': step, 'epoch_target': epoch_target,
            'H': float(solver.H), 'a': float(solver.a),
            'rho_mean': float((ey + ei).mean()),
            'ey_min': float(ey.min()), 'ei_min': float(ei.min()),
            'u_rms': float(sum(torch.fft.ifftn(u_hat[d]).real.pow(2).mean()
                               for d in range(3)).sqrt().item()),
            'r_cells': rp['r_cells'].tolist(),
            'rho_profile': rp['rho'].tolist(),
            'q_profile': rp['q'].tolist(),
            'maxima': max_rows,
            'minima': min_rows,
        }

    t0 = time.time()
    hist = []
    step = 0
    while step < steps:
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, DT)
        step += 1
        t = step * DT
        while t_targets and t >= t_targets[0] - 1e-9:
            hist.append(extract(t, step, t_targets[0]))
            t_targets.pop(0)
    elapsed = time.time() - t0
    return solver, hist, elapsed


def primary_epoch(hist):
    """Bubble epoch: from the late quasi-steady window [t/2, t_end], the
    epoch with the most matter maxima (most structured radial ladder)."""
    h_e = [h for h in hist if h.get('epoch_target') is not None]
    if not h_e:
        h_e = hist
    t_mid = max(h['t'] for h in hist) / 2.0
    late = [h for h in h_e if h['t'] >= t_mid]
    pool = late if late else h_e
    return max(pool, key=lambda h: len(h['maxima']))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--steps', type=int, default=STEPS,
                        help='total RK2 steps (t = steps*dt)')
    parser.add_argument('--epochs', default=None,
                        help='comma-separated epoch list (override EPOCHS)')
    parser.add_argument('--arms', default='A,B,C,W',
                        help='comma-separated arm tags to run')
    args = parser.parse_args()
    steps = args.steps
    epochs = ([float(e) for e in args.epochs.split(',')] if args.epochs
              else None)
    arm_tags = [t.strip() for t in args.arms.split(',') if t.strip()]
    arms = [a for a in ARMS if a[0] in arm_tags]
    if not arms:
        raise SystemExit(f"no matching arms in {[t for t in ARMS]}")

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    dev_name = (torch.cuda.get_device_name(0)
                if torch.cuda.is_available() else 'cpu')
    solver_probe = build_solver(device, 0.0, 0.0, 0.0)
    grid = SeedGrid(solver_probe)  # shared centroid grid

    print(f"Device: {device} ({dev_name})  N={N} (dropped from 96: 10x "
          f"slower on GPU)  L={L:.4f}  dt={DT}  lam={LAM}  chi={CHI}  "
          f"gate='single'  qi_gate={QI_GATE}  hubble='{HUBBLE_MODE}'  "
          f"t={steps * DT}")
    print(f"Arms: {', '.join(f'{a[0]}(D={a[1]},nu={a[2]},cs2={a[3]})'
                             for a in arms)}")

    t_start = time.time()
    results = {}
    for tag, D, nu, cs2, desc in arms:
        print(f"\n=== run: {tag} -- {desc} ===")
        solver, hist, elapsed = run_arm(device, tag, D, nu, cs2, grid,
                                        steps=steps, epochs=epochs)
        for h in hist:
            v, d = overall_verdict(h['maxima'], h['minima'])
            h['verdict'] = v
            h['detail'] = d
        primary = primary_epoch(hist)
        pv, pd = overall_verdict(primary['maxima'], primary['minima'])
        print(f"[{tag}] {elapsed:.1f}s ({len(hist)} profiles) | "
              f"primary t={primary['t']:.1f} {pv} -- {pd['why']}")
        results[tag] = {
            'D': D, 'nu': nu, 'cs2': cs2, 'desc': desc, 'elapsed_s': elapsed,
            'hist': hist, 'primary': _to_prim(primary),
            'primary_epoch_t': primary['t'],
            'verdict': {'decision': pv, 'detail': dict(pd, epoch_t=primary['t'])},
        }

    # console table
    print("\n=== BUBBLE RING DYNAMIC PROBE (spatial-coupling arms, "
          f"N={N}, t={steps * DT}) ===")
    print(f"Seed: sphere R={R_BUBBLE} cells, sigma_edge={SIGMA_EDGE}, "
          f"interior EY={EY_INT}/EI={EI_INT} (reference, rho=phi), "
          f"exterior EY={EY_EXT}/EI={EI_EXT} (dilute, Yin-excess); "
          f"core cut r>{R_CORE} cells; contrast floor {CONTRAST_FLOOR*100:.0f}%.")
    for tag in results:
        r = results[tag]
        p = r['primary']
        mxs = p['maxima']
        rnorm = ', '.join(str(round(m['r_norm'], 2)) for m in mxs[:8])
        inward = ', '.join(
            f"{a['r_cells'] / b['r_cells']:.3f}"
            for a, b in zip(mxs[:-1], mxs[1:]))
        print(f"  Arm {tag} (D={r['D']},nu={r['nu']},cs2={r['cs2']}): "
              f"maxima={len(mxs)} r=[{rnorm}]  inward-ratios=[{inward}]  "
              f"| u_rms_end={p['u_rms']:.2e} | {r['verdict']['decision']}")

    print("\n=== VERDICT TABLE ===")
    for tag in results:
        v = results[tag]['verdict']
        print(f"  Arm {tag}: {v['decision']} -- {v['detail']['why']}")
    final = [results[t]['verdict']['decision'] for t in results]
    print(f"\n=== FINAL: {', '.join(final)} ===")

    # ── record ──────────────────────────────────────────────────────────
    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(repo_root, 'runs')
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, f"{rid}_bubble_ring_dynamic.json")

    pre_reg = (
        "Identical per arm. Seed: spherical standing condensate at the "
        "reference state (E_Y=1, E_I=phi^-1 interior, dilute exterior), "
        "radius R~12 cells, canonical solver (N=64/96, L=2pi, dt=0.001, "
        "lambda=0.05, qi_gate=True gate single, no imposed velocity). "
        "Arms: A baseline null (D=0,nu=0,cs2=0); B diffusion (D=0.0002,nu=0,"
        "cs2=0); C gravity buoyancy-velocity (D=0,nu=0.0005,cs2=0, chi=0); "
        "W wave-verify cs2 pressure proxy (D=0.0002,nu=0.0005,cs2=0.5). "
        "Measurement: radial profile rho(r)=EY+EI and q(r) by azimuthal "
        "averaging about the centroid; local maxima (matter rings) and "
        "minima (voids) outside the core (r>~4 cells); maxima with contrast "
        "vs local mean > 1% floor kept. Decision (i) >=3 successive maxima: "
        "successive radius ratios; each within +-0.08 of 0.6180 and OUTSIDE "
        "0.7862+-0.05 -> SUPPORTS phi-ladder; within 0.7862+-0.05 and "
        "outside 0.6180+-0.08 -> SUPPORTS NULL; else INDETERMINATE. "
        "(ii) ring count 6-10 consistent; 1-2 weak/absent. (iii) every "
        "matter max separated from next by exactly one min. Outcomes: "
        "SUPPORTS / SUPPORTS NULL / INDETERMINATE / NO RINGS."
    )

    record = {
        'prediction': 'Prediction 51 -- bubble radial ring ladder: matter '
                      'rings at r_k = R*phi^(-k), void troughs at '
                      'R*phi^(-(k+1/2)), successive matter-ring ratio '
                      'phi^-1 = 0.6180 (null phi^-1/2 = 0.7862), ~10 ridges '
                      'at 1% contrast floor, strict matter/void alternation. '
                      'Tier Hypothesized (kinematic); the PDE DYNAMIC '
                      'realization under each canonical spatial-coupling '
                      'channel is the tested content.',
        'pre_registration': pre_reg,
        'wave_mode_verification': {
            'has_second_order_wave_term': False,
            'explanation': 'ExpandingTwoFluid3DGPU.rhs is a FIRST-ORDER-in-'
                           'time advection/diffusion/conversion (+velocity) '
                           'PDE advanced by RK2; there is NO d^2E/dt^2 term. '
                           'cs2 enters only as -cs2*grad rho on the VELOCITY '
                           'RHS (pressure force), not as a density wave '
                           'operator. The full dynamical form of the ring '
                           'law (space-sim second-order wave equation '
                           'd^2E = c^2.Laplace E - w0^2 (E_Y - phi E_I) with '
                           'the phi-anchored resonance) is NOT in this '
                           'solver; it belongs to the space-sim GLSL PDE '
                           '(physics/godot/space-sim). Arm W tests the '
                           'closest first-order proxy (cs2 pressure-driven '
                           'velocity).',
        },
        'note_on_sibling': 'two-fluid/run_bubble_ring_probe.py (parallel '
                           'worker) is the ANALYTIC ring-law verification '
                           '(Leg A/B/C). THIS file tests the distinct open '
                           'content: PDE DYNAMIC realization per coupling '
                           'channel.',
        'meta': {
            'N': N, 'L': L, 'dt': DT, 'lam': LAM, 'chi': CHI,
            'hubble_mode': HUBBLE_MODE, 'qi_gate': QI_GATE,
            'gate_model': 'single', 'qi_memory': QI_MEMORY,
            't_end': steps * DT, 'steps': steps,
            'n_dropped_from_96_note': 'N=96 ~10x slower on GPU; N=64 used',
            'device': str(device), 'device_name': dev_name,
            'canonical_coupling_sources': {
                'diffusion_D': 'run_trauma_wake_lock/run_pde_wa_5ch/'
                               'run_pde_wa_test use D=0.0002',
                'gravity_path': 'chi=0 (chemotaxis flagged as chi>0 '
                                'instability source); canonical gravity is '
                                'the intrinsic Poisson buoyancy Pi*grad_Phi '
                                'sourcing the velocity field; nu=0.0005 is '
                                'the canonical probe viscosity',
                'wave_cs2': 'cs2 is a velocity pressure-gradient force only; '
                            'no second-order density wave term exists'},
            'seed': {'r_bubble_cells': R_BUBBLE, 'sigma_edge': SIGMA_EDGE,
                     'ey_int': EY_INT, 'ei_int': EI_INT,
                     'ey_ext': EY_EXT, 'ei_ext': EI_EXT,
                     'exterior_ratio': EY_EXT / EI_EXT,
                     'exterior_eps': float(EY_EXT - PHI * EI_EXT),
                     'note': 'interior at reference equilibrium (eps=0), '
                             'ladder NOT core-seeded; exterior mild Yin-excess '
                             'drives conversion relaxation'},
            'measurement': {'core_cut_cells': R_CORE,
                            'smooth_sigma_cells': SMOOTH_SIGMA,
                            'contrast_floor': CONTRAST_FLOOR,
                            'peak_sep_cells': PEAK_SEP,
                            'epochs': epochs if epochs is not None else EPOCHS},
            'decision': {'r_ladder': RATIO_LADDER,
                         'r_ladder_tol': RATIO_LADDER_TOL,
                         'r_null': RATIO_NULL, 'r_null_tol': RATIO_NULL_TOL,
                         'ring_hi': RING_COUNT_HI, 'ring_lo': RING_COUNT_LO,
                         'weak_max_ring': WEAK_RING_MAX,
                         'min_rings_for_ratio': MIN_RINGS_FOR_RATIO},
        },
        'arms': {tag: {
            'D': r['D'], 'nu': r['nu'], 'cs2': r['cs2'], 'desc': r['desc'],
            'elapsed_s': r['elapsed_s'],
            'epochs': [{k: h[k] for k in
                        ('t', 'epoch_target', 'H', 'a', 'rho_mean', 'ey_min',
                         'ei_min', 'u_rms', 'maxima', 'minima', 'detail',
                         'verdict')} for h in r['hist']],
            'primary_epoch_t': r['primary_epoch_t'],
            'verdict': r['verdict'],
        } for tag, r in results.items()},
        'verdicts': {tag: results[tag]['verdict']['decision']
                     for tag in results},
        'total_wall_s': time.time() - t_start,
    }
    # full primary profiles per arm
    for tag, r in results.items():
        p = r['primary']
        record['arms'][tag]['primary_profile'] = {
            't': p['t'],
            'r_cells': p['r_cells'],
            'rho_profile': p['rho_profile'],
            'q_profile': p['q_profile'],
        }
    with open(outpath, 'w') as f:
        json.dump(record, f, indent=1)
    print(f"\nRecord: {outpath}")


def _to_prim(h):
    """Snapshot a primary-epoch dict without numpy (already plain)."""
    return {k: h[k] for k in
            ('t', 'epoch_target', 'H', 'a', 'rho_mean', 'ey_min', 'ei_min',
             'u_rms', 'r_cells', 'rho_profile', 'q_profile', 'maxima',
             'minima')}


if __name__ == "__main__":
    main()
