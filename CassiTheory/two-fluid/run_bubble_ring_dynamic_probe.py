#!/usr/bin/env python3
"""Bubble ring-ladder probe (DYNAMIC realization): does the canonical
two-fluid solver DYNAMICALLY realize the radial matter-ring ladder predicted
for a bubble (Prediction 51)?

Run:  python two-fluid/run_bubble_ring_dynamic_probe.py
      (--steps N total RK2 steps; --epochs "t1,t2,..." override the
       profile-epochs; defaults below)

NOTE ON NAMING / PARALLEL WORKSTREAM (2026-08-12): the sibling file
two-fluid/run_bubble_ring_probe.py is owned by a parallel worker and contains
the ANALYTIC ring-law verification (Leg A/B/C: matter at ell_n*phi^-k, voids
at ell_n*phi^-(k+1/2), the phase-quantized envelope rho ~ cos^2(pi u),
count N = ln100/lnphi ~ 10 -- the kinematic content, "what a simulated
bubble must show").  THIS file (run_bubble_ring_dynamic_probe.py) tests the
OPEN, distinct content: whether the two-fluid PDE DYNAMICALLY realizes the
ladder from a standing spherical condensate in the canonical solver.  The two
must be cited to different names.

Tier Hypothesized: the ring law is kinematic -- doublet radial phase
alpha = pi*log_phi(r/l_n) + pool-cell parities (matter rings at integer
rungs, void troughs at half-rungs, `foundations/spin-fibonacci-spiral.md`,
`foundations/rung-offset-mechanism.md` sec 4.1).  A bubble carries a radial
ring ladder: matter rings at r_k = R*phi^-k, void troughs at
R*phi^-(k+1/2), successive matter-ring ratio phi^-1 = 0.6180 (null:
phi^-1/2 = 0.7862), ~10 matter ridges at the 1% contrast floor, strict
matter/void alternation.

THE OPEN QUESTION THIS PROBE TESTS: whether the PDE DYNAMICALLY realizes the
ladder from a standing spherical condensate in the canonical solver (NOT
whether the ladder's positions are kinematically consistent -- that is the
Hypothesized part).  An honest null is a valid outcome.

============================================================================
PRE-REGISTRATION  (decision tree -- written before ANY run; verbatim)
============================================================================
Seed: a spherical standing condensate at the reference state (E_Y = 1,
E_I = phi^-1 interior, dilute exterior), radius R ~ several cells, in the
canonical solver (N = 64 or 96, L = 2*pi, dt = 0.001, lambda = 0.05,
qi_gate = True, gate single, D = 0, no gravity drive, no velocity).

Measurement: at the bubble epoch (t where the radial structure is
quasi-steady; probe several epochs), extract the radial profile of
rho(r) = E_Y+E_I (and q(r)) by azimuthal averaging around the field
centroid; identify local maxima (matter rings) and minima (voids) OUTSIDE
the core (r > ~4 cells, to avoid the core-contamination region); keep
maxima whose contrast vs the local mean exceeds a 1% floor.

Decision rule:
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
============================================================================

Arms (fresh solver per arm, N = 64 default -- the pre-registration permits
N = 64 if N = 96 is too slow; on this GPU N = 96 is ~10x slower (5.4 vs
54.6 steps/s), so N = 64 is used and noted):
  bubble  spherical standing condensate: interior at the reference state
          (E_Y = 1, E_I = phi^-1, rho = phi, eps = 0), dilute exterior at a
          mild Yin-excess (ratio 0.75, eps ~ -0.35) so the conversion
          relaxation drives non-trivial dynamics from the density front.
          radius R = 12 cells, transition sigma_edge = 2.5 cells.
The interior is set exactly at the reference equilibrium so the ladder is
NOT seeded at the core; any ring structure must arise from the dynamics.

Measurement regime: D = 0, nu = 0, chi = 0, cs2 = 0, no imposed velocity
(u = 0 init), qi_gate = True (gate_model = 'single'), hubble_mode =
'conversion' -- the pre-registered canonical settings at which the only
field dynamics are the qi-gated conversion relaxation (and, sourced only by
the density profile's intrinsic buoyancy, a possible velocity response).
Whether rings EMERGE is the tested content.

Radial extraction: per-cell distance m from the fixed centroid
(N/2, N/2, N/2) in cells; bin cells by integer shell; azimuthally average
EY, EI, rho = EY+EI, and q (via the solver's compute_q_field, same code
path the dynamics use).  Measurement radial rank m in [R_CORE, N/2 - 1]
(core-contamination cut R_CORE = 4 cells; the m -> N/2 far-side wrap region
is excluded).  Peaks/troughs found on a light Gaussian-smoothed profile
(sigma ~ 2 cells) by first-difference sign change with a prominence gate at
the 1% contrast floor.

Epochs: profiles recorded at t = 0, 2, 5, 8, 10, 15, 20, 30, 40 and at the
final step; the bubble epoch is taken over the late quasi-steady window
(t in [8, t_end]), reported per-epoch; the primary verdict uses the epoch
whose radial structure is most structured (max ring count), consistent with
"probe several epochs, use the bubble epoch".

Output (runs/ is gitignored -- commit the script only):
  runs/<YYYYmmdd_HHMMSS>_bubble_ring_dynamic.json   full per-epoch record
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
D = 0.0
NU = 0.0
CHI = 0.0
CS2 = 0.0
HUBBLE_MODE = 'conversion'
QI_GATE = True
QI_MEMORY = False
STEPS = 40000           # t = 40 (2/lambda lock timescale)
PROFILE_EVERY = 2000    # cheap radial extract cadence (also guards the run)
EPOCHS = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0]
T_END = STEPS * DT

# Single-arm geometry for the bubble (no arms matrix -- one arm, the seed)
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


def build_solver(device):
    """Fresh canonical solver per arm; single gate (constructor default)."""
    solver = ExpandingTwoFluid3DGPU(
        N=N, L=L, nu=NU, D=D, lam=LAM, chi=CHI, cs2=CS2,
        hubble_mode=HUBBLE_MODE, qi_gate=QI_GATE,
        qi_memory=QI_MEMORY, device=device)
    assert solver.gate_model == 'single'
    return solver


def bubble_init(solver, ey_int=EY_INT, ei_int=EI_INT,
                ey_ext=EY_EXT, ei_ext=EI_EXT):
    """Spherical standing condensate: reference-state interior, dilute
    exterior, smooth radial transition.  Returns ey_hat, ei_hat, u_hat."""
    N_ = solver.N
    dev = solver.device
    x = torch.arange(N_, dtype=torch.float64, device=dev)
    X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
    c = N_ / 2.0
    R = torch.sqrt((X - c) ** 2 + (Y - c) ** 2 + (Z - c) ** 2)
    # Smooth 0->1 interior fraction: f=1 inside (r<<R), 0 outside (r>>R)
    f = 0.5 * (1.0 - torch.tanh((R - R_BUBBLE) / SIGMA_EDGE))
    ey = ey_int * f + ey_ext * (1.0 - f)
    ei = ei_int * f + ei_ext * (1.0 - f)
    ey = torch.clamp(ey, min=1e-3)
    ei = torch.clamp(ei, min=1e-3)
    u_hat = [torch.fft.fftn(torch.zeros((N_,) * 3, dtype=torch.float64,
                                         device=dev)) for _ in range(3)]
    return torch.fft.fftn(ey), torch.fft.fftn(ei), u_hat


def radial_profiles(solver, ey, ei):
    """Azimuthal average about the centroid (N/2,N/2,N/2), in cell shells.

    Returns dict with arrays indexed by radial rank m = 0..N//2 - 1:
    r_cells (shell center), ey, ei, rho, q, and count per shell.
    q comes from the solver's own compute_q_field (same code path as the
    dynamics).  Periodic far-side shells (m near N//2) are excluded by the
    measurement rank cut in peak extraction, not here.
    """
    N_ = solver.N
    dev = solver.device
    x = torch.arange(N_, dtype=torch.float64, device=dev)
    X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
    c = N_ / 2.0
    R = torch.sqrt((X - c) ** 2 + (Y - c) ** 2 + (Z - c) ** 2)
    m = R.long()
    rho = ey + ei
    q, _ = solver.compute_q_field(ey, ei)
    out = {}
    for name, field in (('ey', ey), ('ei', ei), ('rho', rho), ('q', q)):
        acc = torch.zeros(N_ // 2, dtype=torch.float64, device=dev)
        cnt = torch.zeros(N_ // 2, dtype=torch.float64, device=dev)
        shell_mask = m < (N_ // 2 - 1)
        idx = m[shell_mask]
        vals = field[shell_mask]
        acc.scatter_add_(0, idx, vals)
        cnt.scatter_add_(0, idx, torch.ones_like(idx, dtype=torch.float64))
        out[name] = (acc / cnt).cpu().numpy()
    r_cells = np.arange(N_ // 2, dtype=np.float64) + 0.5
    out['r_cells'] = r_cells
    out['r_length'] = r_cells * (L / N_)
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

    Returns the ranked structure: for each extremum, {'kind': 'max'|'min',
    'r_cells', 'r_norm' (r/R_bubble), 'val', 'contrast', 'local_mean'}.
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
    # resolve with contrast floor and min separation
    kept_max = []
    for k in maxima:
        i = k
        abs_idx = int(np.where(mask)[0][i])
        lm = local_mean(ysm, int(abs_idx))
        contrast = (ys[i] - lm) / max(abs(lm), 1e-30)
        if abs(contrast) >= floor:
            if kept_max and (rs[i] - rs[kept_max[-1]]) < PEAK_SEP:
                continue
            kept_max.append(k)
    maxima = kept_max
    # re-filter minima to only those between consecutive kept maxima
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

    max_rows = [row(k, 'max') for k in maxima]
    min_rows = [row(k, 'min') for k in minima]
    return max_rows, min_rows, ys, mask


def overall_verdict(max_rows, min_rows):
    """Apply the pre-registered decision tree (see module docstring)."""
    n_ring = len(max_rows)
    detail = {'n_matter_maxima': n_ring}

    # (iii) alternation: every matter max separated from the next by exactly
    # one minimum (a void trough between each adjacent pair of maxima).
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

    # (ii) ring-count consistency
    if RING_COUNT_LO <= n_ring <= RING_COUNT_HI:
        count_grade = 'consistent'
    elif n_ring <= WEAK_RING_MAX:
        count_grade = 'weak_or_absent'
    else:
        count_grade = 'borderline'
    detail['ring_count_grade'] = count_grade

    # (i) successive ratios
    ratios = []
    for a, b in zip(max_rows[:-1], max_rows[1:]):
        r_out = b['r_cells'] / a['r_cells']  # outward ratio
        r_in = a['r_cells'] / b['r_cells']   # inward ratio (phi^-direction)
        ratios.append({'r_out': float(r_out), 'r_in': float(r_in)})
    detail['successive_ratios'] = ratios
    detail['ratio_out'] = [r['r_out'] for r in ratios]
    detail['ratio_in'] = [r['r_in'] for r in ratios]

    if n_ring < MIN_RINGS_FOR_RATIO:
        verdict = 'NO RINGS' if n_ring < 2 else 'INDETERMINATE'
        detail['why'] = (f'{n_ring} matter maxima < {MIN_RINGS_FOR_RATIO} '
                         f'needed for the ratio test; '
                         f'ring count {count_grade}')
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


def run_case(device, steps=STEPS, epochs=None):
    """Evolve the bubble (fresh solver), recording per-epoch profiles."""
    if epochs is None:
        epochs = EPOCHS
    solver = build_solver(device)
    ey_hat, ei_hat, u_hat = bubble_init(solver)
    t_targets = sorted(set(round(e, 6) for e in epochs))

    def extract(t, step, epoch_target):
        ey = torch.fft.ifftn(ey_hat).real
        ei = torch.fft.ifftn(ei_hat).real
        rp = radial_profiles(solver, ey, ei)
        max_rows, min_rows, ys, mask = find_structure(rp['rho'], rp['r_cells'])
        return {
            't': round(t, 6), 'step': step, 'epoch_target': epoch_target,
            'H': float(solver.H), 'a': float(solver.a),
            'rho_mean': float((ey + ei).mean()),
            'ey_min': float(ey.min()), 'ei_min': float(ei.min()),
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
        # profile at each target epoch as soon as reached, and at every
        # PROFILE_EVERY cadence (guarding record) and at the final step
        while t_targets and t >= t_targets[0] - 1e-9:
            rec = extract(t, step, t_targets[0])
            hist.append(rec)
            t_targets.pop(0)
        if step % PROFILE_EVERY == 0 and not t_targets:
            if (round(t, 6), None) not in [(h['t'], h['epoch_target'])
                                           for h in hist]:
                rec = extract(t, step, None)
                hist.append(rec)
    if not t_targets or True:
        rec = extract(steps * DT, step, steps * DT)
        hist.append(rec)
    elapsed = time.time() - t0
    return solver, hist, elapsed


def primary_epoch(hist):
    """Select the 'bubble epoch' across the measured epochs.

    Quasi-steady window is the late half of the run (t >= steps*dt/2);
    among those, the epoch with the most matter maxima (most structured
    radial ladder).  Fall back to the most structured epoch overall if the
    late window is empty.
    """
    h_e = [h for h in hist if h.get('epoch_target') is not None]
    if not h_e:
        h_e = hist
    t_mid = max(h['t'] for h in hist) / 2.0
    late = [h for h in h_e if h['t'] >= t_mid]
    pool = late if late else h_e
    best = max(pool, key=lambda h: len(h['maxima']))
    return best


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--steps', type=int, default=STEPS,
                        help='total RK2 steps (t = steps*dt)')
    parser.add_argument('--epochs', default=None,
                        help='comma-separated epoch list (override EPOCHS)')
    args = parser.parse_args()
    steps = args.steps
    epochs = ([float(e) for e in args.epochs.split(',')] if args.epochs
              else None)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    dev_name = (torch.cuda.get_device_name(0)
                if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device} ({dev_name})  N={N} (dropped from 96: 10x "
          f"slower on GPU)  L={L:.4f}  dt={DT}  lam={LAM}  D={D}  nu={NU}  "
          f"chi={CHI}  cs2={CS2}  gate='single'  qi_gate={QI_GATE}  "
          f"hubble='{HUBBLE_MODE}'  t={steps * DT}")

    t_start = time.time()
    solver, hist, elapsed = run_case(device, steps=steps, epochs=epochs)

    # pre-registered per-epoch verdicts
    for h in hist:
        v, d = overall_verdict(h['maxima'], h['minima'])
        h['verdict'] = v
        h['detail'] = d

    # primary bubble epoch
    primary = primary_epoch(hist)
    pv, pd = overall_verdict(primary['maxima'], primary['minima'])

    print(f"\n=== BUBBLE RING DYNAMIC PROBE (t={steps * DT}, N={N}, "
          f"lam={LAM}, gate='single') ===")
    print(f"Seed: sphere R={R_BUBBLE} cells, sigma_edge={SIGMA_EDGE}, "
          f"interior EY={EY_INT}/EI={EI_INT} (reference, rho=phi), "
          f"exterior EY={EY_EXT}/EI={EI_EXT} (dilute, Yin-excess); "
          f"core cut r>{R_CORE} cells; contrast floor {CONTRAST_FLOOR*100:.0f}%.")
    print(f"  elapsed run: {elapsed:.1f}s ({len(hist)} profiles)")
    for h in hist:
        tag = (f"t={h['t']:6.2f}" + (f" [epoch {h['epoch_target']:.0f}]"
               if h['epoch_target'] is not None else ""))
        mx = h['maxima']
        ratios = ', '.join(f"{r['r_in']:.3f}"
                           for r in h['detail']['successive_ratios'])
        r_str = ', '.join(str(round(m['r_norm'], 2)) for m in mx[:6])
        print(f"  {tag:28s} maxima={len(mx):2d} "
              f"r=[{r_str}]  inward-ratios=[{ratios}]  {h['verdict']}")
    print(f"\n  primary bubble epoch t={primary['t']:.2f}: "
          f"{primary['verdict']} -- {primary['detail']['why']}")
    print(f"\n=== FINAL VERDICT: {pv} ===")
    print(f"  details: {pd['why']}")

    # ── record ──────────────────────────────────────────────────────────
    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(repo_root, 'runs')
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, f"{rid}_bubble_ring_dynamic.json")

    pre_reg = (
        "Seed: spherical standing condensate at the reference state "
        "(E_Y=1, E_I=phi^-1 interior, dilute exterior), radius R ~ several "
        "cells, canonical solver (N=64/96, L=2pi, dt=0.001, lambda=0.05, "
        "qi_gate=True, gate single, D=0, no gravity drive, no velocity). "
        "Measurement: at the bubble epoch (quasi-steady t; several epochs), "
        "radial profile rho(r)=EY+EI and q(r) by azimuthal averaging around "
        "the field centroid; local maxima (matter rings) and minima (voids) "
        "outside the core (r>~4 cells); maxima with contrast vs local mean "
        "> 1% floor kept. Decision: (i) >=3 successive matter maxima -> "
        "successive radius ratios; each within +-0.08 of 0.6180 and OUTSIDE "
        "0.7862+-0.05 -> SUPPORTS phi-ladder; within 0.7862+-0.05 and "
        "outside 0.6180+-0.08 -> SUPPORTS NULL; else INDETERMINATE. "
        "(ii) ring count 6-10 consistent; 1-2 weak/absent (report honestly). "
        "(iii) every matter max separated from the next by exactly one min. "
        "Honest outcomes: SUPPORTS / SUPPORTS NULL / INDETERMINATE / "
        "NO RINGS, each with the numbers."
    )

    primary_detail = dict(pd)
    primary_detail['epoch_t'] = primary['t']
    record = {
        'prediction': 'Prediction 51 -- bubble radial ring ladder: matter '
                      'rings at r_k = R*phi^(-k), void troughs at '
                      'R*phi^(-(k+1/2)), successive matter-ring ratio '
                      'phi^-1 = 0.6180 (null phi^-1/2 = 0.7862), ~10 ridges '
                      'at 1% contrast floor, strict matter/void alternation. '
                      'Tier Hypothesized (kinematic: doublet radial phase '
                      'alpha = pi*log_phi(r/l_n) + pool-cell parities); the '
                      'PDE DYNAMIC realization is the tested content.',
        'pre_registration': pre_reg,
        'note_on_sibling': 'two-fluid/run_bubble_ring_probe.py (parallel '
                           'worker) is the ANALYTIC ring-law verification '
                           '(Leg A/B/C: matter at ell_n*phi^-k, voids at '
                           'ell_n*phi^-(k+1/2), phase-quantized envelope '
                           'rho~cos^2(pi u), count N=ln100/lnphi~10).  THIS '
                           'file (run_bubble_ring_dynamic_probe.py) tests the '
                           'distinct open content: PDE DYNAMIC realization.',
        'meta': {
            'N': N, 'L': L, 'dt': DT, 'lam': LAM, 'D': D, 'nu': NU,
            'chi': CHI, 'cs2': CS2, 'hubble_mode': HUBBLE_MODE,
            'qi_gate': QI_GATE, 'gate_model': 'single',
            'qi_memory': QI_MEMORY, 't_end': steps * DT, 'steps': steps,
            'n_dropped_from_96_note': 'N=96 was 10x slower (5.4 vs 54.6 '
                'steps/s on this GPU); N=64 used per pre-registration fallback',
            'device': str(device), 'device_name': dev_name,
            'seed': {'r_bubble_cells': R_BUBBLE, 'sigma_edge': SIGMA_EDGE,
                     'ey_int': EY_INT, 'ei_int': EI_INT,
                     'ey_ext': EY_EXT, 'ei_ext': EI_EXT,
                     'exterior_ratio': EY_EXT / EI_EXT,
                     'exterior_eps': float(EY_EXT - PHI * EI_EXT),
                     'note': 'interior at reference equilibrium (eps=0) so '
                             'the ladder is NOT core-seeded; exterior '
                             'carries a mild Yin-excess to drive conversion '
                             'relaxation dynamics'},
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
        'epochs': [{'t': h['t'], 'epoch_target': h.get('epoch_target'),
                    'H': h['H'], 'a': h['a'], 'rho_mean': h['rho_mean'],
                    'ey_min': h['ey_min'], 'ei_min': h['ei_min'],
                    'maxima': h['maxima'], 'minima': h['minima'],
                    'detail': h['detail'], 'verdict': h['verdict']}
                   for h in hist],
        'primary_epoch_t': primary['t'],
        'verdict': {
            'decision': pv,
            'detail': primary_detail,
            'n_epochs': len(hist),
            'total_wall_s': time.time() - t_start,
        },
    }
    record['primary_profiles'] = {
        't': primary['t'],
        'r_cells': primary['r_cells'],
        'rho_profile': primary['rho_profile'],
        'q_profile': primary['q_profile'],
    }
    with open(outpath, 'w') as f:
        json.dump(record, f, indent=1)
    print(f"\nRecord: {outpath}")


if __name__ == "__main__":
    main()
