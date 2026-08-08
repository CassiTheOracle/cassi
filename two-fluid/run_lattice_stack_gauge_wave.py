#!/usr/bin/env python3
"""Gauge-resolution wave (wave 6 of the lattice-stack program, labels g1-g12).

Run:  python two-fluid/run_lattice_stack_gauge_wave.py
      (--steps N, --arm TAG repeatable, --init-check, --scan-rotation,
       --rot DEG, --from-runs DIR, --fine)

Reuses the committed run_lattice_stack_falsifier / run_lattice_stack2_probe
machinery (imported read-only); same protocol: fresh solver per arm,
N = 48, gate 'five', dt = 0.001, t = 40 = 2/lambda, canonical solver
untouched, zero new terms, no registry changes.

Wave 5 (section 3.15) established the born-class split: the alpha = 0
landscape mixes construction-level born contrast (C_abs(0) ~ 0.9, the
antisymmetric envelope branch, |Ssin/Scos| > RHO0*BETA/E_RIDGE = 0.7468)
with born-flat init (C_abs(0) ~ 0, the symmetric branch) and clamp seed.
This wave re-measures the clamp-polluted DEATH arms at the clean gauge
rotations found by the 720-step common-rotation scan (theory worker;
every rotation re-verified by this script's --scan-rotation before the
batch runs):

  g1:  dtheta = 38 deg, M = 32, alpha = 297 deg   (born-flat; 12 zero-floor
       rotations in [296.5, 301.5])               -- the M = 32 edge test
  g2:  dtheta = 60 deg, M = 16, alpha = 28.5 deg  (born-full, delta = 120)
  g3:  dtheta = 54 deg, M = 16, alpha = 286 deg   (born-flat, delta = 144)
  g4:  dtheta = 45 deg, M = 22, alpha = 22.5 deg  (born-full, delta = 90)
  g5a: dtheta = 45 deg, M = 20, alpha = 229 deg   (born-full, delta = 180)
  g5b: dtheta = 45 deg, M = 21, alpha = 229 deg   (born-full, delta = 135)
  g5c: dtheta = 45 deg, M = 22, alpha = 229 deg   (born-flat, delta = 90)
  g5d: dtheta = 45 deg, M = 23, alpha = 229 deg   (born-flat, delta = 45)
  g8:  dtheta = 144 deg, M = 16, alpha = 90 deg   (perfectly antisymmetric
       clean born-full: Scos = 0, Ssin = 1.0, delta = 144)
  g9:  dtheta = 144 deg, M = 4, alpha = 0 deg     (A = 1.0, single lobe)
  g10: dtheta = 144 deg, M = 8, alpha = 0 deg     (A = 0.618, single lobe)
  g11: dtheta = 60 deg, M = 15, alpha = 251 deg   (born-full, delta = 180,
       A = 2.0)
  g12: dtheta = 36 deg, M = 25, alpha = 0 deg     (1904 floor cells = 1.7%
       < 2%; sub-M* anchor-family height)
  g13-g17 (--fine, priority LOW): 34.5/35.5/36.5/37.5/37.8 deg at M = 32,
       alpha = 0 -- band-shape characterization of the M = 32 window.

Born class at init: born-flat (C_abs(0) ~ 0) vs born-full (C_abs(0) ~ 0.9,
construction-level; |Ssin/Scos| > 0.7468 = RHO0*BETA/E_RIDGE for these
geometries, where Scos = sum cos theta_j, Ssin = sum sin theta_j over the
layer phases).  A global rotation preserves A_tot(0) exactly and drops the
clamp residue to float-exact (section 3.11(c)/f7 theorem).

Output: runs/<rid>_lattice_stack_g/run_<arm>.json + results.json (raw;
NO doc changes until the director reads the raw outputs).
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
import run_trauma_wake_lock as T
import run_two_strand_probe as P
import run_lattice_stack_probe as L1
import run_lattice_stack2_probe as L2

T.LAM = 0.05
T.DT = 0.001
T.REPORT = 50
STEPS = 40000                 # t = 40 = 2/lambda

S_TOT = float(2.0 * L2.RHO0 * L2.BETA * (2.0 * np.pi) ** 1.5 * L2.SIG ** 3)
BORN_THRESH = L2.RHO0 * L2.BETA / L2.E_RIDGE   # 0.7468: antisymmetric
                                               # envelope dominance


def lin(M, dth, rot=0.0):
    return [i * dth + rot for i in range(M)]


def array_factor(M, dth_deg):
    """|sum_j e^{i j dtheta}| = |sin(M dtheta/2)| / |sin(dtheta/2)|."""
    dth = math.radians(dth_deg)
    num = abs(math.sin(M * dth / 2.0))
    den = abs(math.sin(dth / 2.0))
    return num / max(den, 1e-30)


def stack_delta(M, dth_deg):
    """Total stack twist reduced mod 2*pi and folded to the acute angle:
    delta = fold((M*dtheta) mod 360), the wave-5 convention (w7 45 deg/M=21
    -> 945 -> 225 -> 135; f13 108 deg/M=16 -> 1728 -> 288 -> 72)."""
    d = (M * dth_deg) % 360.0
    return d if d <= 180.0 else 360.0 - d


def sin_cos_sums(phases):
    """Scos = sum cos theta_j, Ssin = sum sin theta_j (exact arithmetic)."""
    C0 = sum(math.cos(p) for p in phases)
    S0 = sum(math.sin(p) for p in phases)
    return C0, S0


def born_class(C0, S0):
    """|Ssin/Scos| vs RHO0*BETA/E_RIDGE: born-full = antisymmetric envelope
    dominance (construction-level two-hump contrast), born-flat otherwise."""
    if abs(C0) < 1e-12:
        return 'full' if abs(S0) > 1e-12 else 'null'
    return 'full' if abs(S0 / C0) > BORN_THRESH else 'flat'


def profile_born_contrast(prof, p_bg, c1, c2):
    """1-D version of L1.two_hump on the z,y-integrated rho(x) profile:
    C_abs = (ad_r - ad_m)/ad_r with ad = |prof| (construction background
    p_bg = rho_mean*N^2, the measure() convention at t = 0)."""
    ad = np.abs(prof)
    if ad.max() < 1e-4 * p_bg:
        return 0.0
    positions, merged = P.track_ridges(ad, [c1, c2], None)
    if merged or len(positions) < 2:
        return 0.0
    x1, x2 = float(positions[0]), float(positions[1])
    xm = 0.5 * (x1 + x2)
    i1, i2, im = int(round(x1)), int(round(x2)), int(round(xm))
    ad_r = max(ad[i1], ad[i2])
    return float((ad_r - ad[im]) / max(ad_r, 1e-30))


def scan_born(device, phases, n=720, report_alpha=None):
    """720-step common-rotation scan with the born class per rotation.

    Floors use the construction's rotation linearity (SA/SB path, exactly
    as in run_lattice_stack_falsifier); the born class uses the exact
    Scos/Ssin
    arithmetic plus the analytic z,y-integrated profile
        prof(x, a) = cos a * U(x) - sin a * V(x)
    with U, V built from the per-layer x-profiles (the same linear
    construction the field init uses).  Returns aggregate counts plus the
    table rows for the zero-floor windows and the requested alpha."""
    N_ = T.N
    x = torch.arange(N_, dtype=torch.float64, device=device)
    X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
    cx = N_ / 2.0
    c1, c2 = cx - L2.SEP / 2.0, cx + L2.SEP / 2.0
    M = len(phases)
    spacing = N_ / M
    zs = [cx + (j - (M - 1) / 2.0) * spacing for j in range(M)]
    offsets = (0.0, float(N_), -float(N_))
    SA = torch.zeros_like(X)
    SB = torch.zeros_like(X)
    Gp = np.zeros((M, N_), dtype=np.float64)
    Gm = np.zeros((M, N_), dtype=np.float64)
    for j, (zi, ph) in enumerate(zip(zs, phases)):
        ct, st = math.cos(ph), math.sin(ph)
        g1 = torch.zeros_like(X)
        g2 = torch.zeros_like(X)
        for off in offsets:
            zc = Z - zi + off
            g1 = g1 + torch.exp(-((X - c1) ** 2 + (Y - cx) ** 2 + zc ** 2)
                                / (2.0 * L2.SIG ** 2))
            g2 = g2 + torch.exp(-((X - c2) ** 2 + (Y - cx) ** 2 + zc ** 2)
                                / (2.0 * L2.SIG ** 2))
        gp = g1 + g2
        gm = g1 - g2
        SA = SA + L2.RHO0 * L2.BETA * gp * ct - L2.E_RIDGE * gm * st
        SB = SB + L2.RHO0 * L2.BETA * gp * st + L2.E_RIDGE * gm * ct
        Gp[j] = gp.sum(dim=(1, 2)).cpu().numpy()
        Gm[j] = gm.sum(dim=(1, 2)).cpu().numpy()
    C0, S0 = sin_cos_sums(phases)
    # prof(x, a) = cos a * U - sin a * V
    U = L2.RHO0 * L2.BETA * (np.cos(np.array(phases))[:, None] * Gp).sum(0) \
        - L2.E_RIDGE * (np.sin(np.array(phases))[:, None] * Gm).sum(0)
    V = L2.RHO0 * L2.BETA * (np.sin(np.array(phases))[:, None] * Gp).sum(0) \
        + L2.E_RIDGE * (np.cos(np.array(phases))[:, None] * Gm).sum(0)
    rows = []
    n_clean = 0
    n_full = n_flat = 0
    windows = []               # consecutive zero-floor runs
    run = None
    for k in range(n):
        a = 2.0 * np.pi * k / n
        ca, sa = math.cos(a), math.sin(a)
        rho = L2.RHO0 + ca * SA - sa * SB
        eps = sa * SA + ca * SB
        ey = (T.PHI * rho + eps) / (1.0 + T.PHI)
        ei = (rho - eps) / (1.0 + T.PHI)
        fe = int((ey <= 1e-3 + 1e-12).sum().item())
        fi = int((ei <= 1e-3 + 1e-12).sum().item())
        Scos = C0 * ca - S0 * sa
        Ssin = S0 * ca + C0 * sa
        cls = born_class(Scos, Ssin)
        prof = ca * U - sa * V
        p_bg = L2.RHO0 * N_ ** 2 + float(prof.sum()) / N_
        cabs = profile_born_contrast(prof, p_bg, c1, c2)
        row = {'alpha': a, 'alpha_deg': np.degrees(a), 'floors': fe + fi,
               'born': cls, 'Scos': Scos, 'Ssin': Ssin,
               'ratio_sin_cos': (abs(Ssin / Scos)
                                 if abs(Scos) > 1e-12 else float('inf')),
               'C_abs_analytic': cabs}
        rows.append(row)
        if fe + fi == 0:
            n_clean += 1
            if cls == 'full':
                n_full += 1
            else:
                n_flat += 1
            if run is None:
                run = [k, k]
            else:
                run[1] = k
        else:
            if run is not None:
                windows.append((run[0], run[1]))
                run = None
    if run is not None:
        windows.append((run[0], run[1]))
    out = {'n_rotations': n, 'n_zero_floor': n_clean,
           'n_zero_floor_born_full': n_full, 'n_zero_floor_born_flat': n_flat,
           'zero_floor_windows_deg': [(w[0] * 360.0 / n, w[1] * 360.0 / n)
                                      for w in windows]}
    if report_alpha is not None:
        k = int(round(report_alpha * n / 360.0)) % n
        out['chosen'] = rows[k]
    return out


def verify_rotation(device, phases):
    """Exact-path check: floor contact and t = 0 born contrast of the
    clamped construction at the chosen rotation (L2.stack_init_phases +
    ifftn, as in run_case2)."""
    solver = T.build_solver(device)
    ey_hat, ei_hat, _, zs = L2.stack_init_phases(solver, phases)
    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    rho_prof = (ey + ei).sum(dim=(1, 2)).cpu().numpy()
    rho_mean = float((ey + ei).mean())
    centers = [solver.N / 2.0 - L2.SEP / 2.0, solver.N / 2.0 + L2.SEP / 2.0]
    windows = L1.layer_windows(solver.N, zs, solver.device)
    d = L1.measure(solver, ey, ei, rho_prof, centers, None, windows, zs,
                   rho_mean)
    return {'floors_ey': int((ey <= 1e-3 + 1e-12).sum().item()),
            'floors_ei': int((ei <= 1e-3 + 1e-12).sum().item()),
            'min_ey': float(ey.min()), 'min_ei': float(ei.min()),
            'C_abs_0': d['C_abs'], 'C_rho_0': d['C_rho'],
            'd_0': d['d'], 'present': d['two_hump']['present']}


ARMS = [
    ('g1', 38.0, 32, None, 297.0,
     {'kind': 'edge_test', 'born': 'flat',
      'note': '38 deg M=32 at the clean born-flat gauge (alpha=0 born-full '
              'death +0.186 was clamp-polluted, 840 floors; 12 zero-floor '
              'rotations in [296.5, 301.5]): if C_abs(40) >= 0.5 the '
              'alpha=0 landscape is clamp-artifact and the born-flat band '
              'is 33-38 deg all-pass; if < 0.5 the 38 deg death is a real '
              'born-flat edge'}),
    ('g2', 60.0, 16, None, 28.5,
     {'kind': 'born_full_delta', 'born': 'full',
      'note': '60 deg M=16 born-full delta=120 at a clean gauge (f11\'s '
              'alpha=0 fail +0.130 was clamp-influenced; 290 born-full '
              'clean rotations incl. alpha 28.5): does a clean born-full '
              'delta=120 pass?'}),
    ('g3', 54.0, 16, None, 286.0,
     {'kind': 'born_flat_delta', 'born': 'flat',
      'note': '54 deg M=16 born-flat delta=144 at a clean gauge (48 clean '
              'rotations, all born-flat; f2\'s collapse -0.409 was '
              'born-full + 531 floors): does clean born-flat delta=144 '
              'pass? (resolves the m8_72-vs-f2 delta=144 split at a flat '
              'gauge)'}),
    ('g4', 45.0, 22, None, 22.5,
     {'kind': 'born_full_delta', 'born': 'full',
      'note': '45 deg M=22 born-full delta=90 at a clean gauge (w8\'s '
              'alpha=0 fail +0.129; 177 born-full clean rotations incl. '
              'alpha 22.5): real or clamp?'}),
    ('g5a', 45.0, 20, None, 229.0,
     {'kind': 'same_gauge', 'born': 'full',
      'note': '45 deg M=20 at gauge 229 (533 floors = 0.48% < 2%): the '
              'delta-walk discriminator row (born-full delta=180)'}),
    ('g5b', 45.0, 21, None, 229.0,
     {'kind': 'same_gauge', 'born': 'full',
      'note': '45 deg M=21 at gauge 229 (zero floors): the delta-walk '
              'discriminator row (born-full delta=135, at M*)'}),
    ('g5c', 45.0, 22, None, 229.0,
     {'kind': 'same_gauge', 'born': 'flat',
      'note': '45 deg M=22 at gauge 229 (zero floors): the delta-walk '
              'discriminator row (born-flat delta=90)'}),
    ('g5d', 45.0, 23, None, 229.0,
     {'kind': 'same_gauge', 'born': 'flat',
      'note': '45 deg M=23 at gauge 229 (zero floors): the delta-walk '
              'discriminator row (born-flat delta=45)'}),
    ('g8', 144.0, 16, None, 90.0,
     {'kind': 'probe', 'born': 'full',
      'note': '144 deg M=16 at alpha=90: perfectly antisymmetric clean '
              'born-full (Scos=0, Ssin=1.0), delta=144 -- the clean '
              'symmetric-class born-full delta=144 probe (f13\'s delta=72 '
              'passes; no clean delta=144 born-full precedent)'}),
    ('g9', 144.0, 4, None, 0.0,
     {'kind': 'lean_pass', 'born': None,  'note': '144 deg M=4 at alpha=0 (A = 1.0, single-lobe geometry): '
              'lean PASS per theory'}),
    ('g10', 144.0, 8, None, 0.0,
     {'kind': 'lean_pass', 'born': None,  'note': '144 deg M=8 at alpha=0 (A = 0.618, single-lobe geometry): '
              'lean PASS per theory'}),
    ('g11', 60.0, 15, None, 251.0,
     {'kind': 'lean_pass', 'born': 'full',
      'note': '60 deg M=15 at gauge 251 (137 clean rotations, 25 born-full '
              'incl. alpha 251; delta=180, A = 2.0): lean PASS -- a clean '
              'falsifier of the 60 deg family (if 60/15 passes while '
              '60/16@28.5 fails, the 60 deg death is delta-selective; if '
              'both pass, 60 deg joins the passing families)'}),
    ('g12', 36.0, 25, None, 0.0,
     {'kind': 'lean_pass_floored', 'born': None,  'note': '36 deg M=25 at alpha=0 (no clean gauge exists; 1904 floor '
              'cells = 1.7% < 2%): lean PASS per the theory\'s fine-scan '
              'band prediction; caveat the floors'}),
]

FINE_ARMS = [
    ('g13', 34.5, 32, None, 0.0,
     {'kind': 'fine_scan', 'born': None,  'note': 'fine scan of the M=32 band interior (34.29-35 deg mild '
              'minimum is real per theory): lean PASS'}),
    ('g14', 35.5, 32, None, 0.0,
     {'kind': 'fine_scan', 'born': None,  'note': 'fine scan of the M=32 band: lean PASS'}),
    ('g15', 36.5, 32, None, 0.0,
     {'kind': 'fine_scan', 'born': None,  'note': 'fine scan of the M=32 band: lean PASS'}),
    ('g16', 37.5, 32, None, 0.0,
     {'kind': 'fine_scan', 'born': None,  'note': 'fine scan of the M=32 band: lean PASS'}),
    ('g17', 37.8, 32, None, 0.0,
     {'kind': 'fine_scan', 'born': None,  'note': 'fine scan of the M=32 band high side (37 deg passes +0.539, '
              '38 deg fails +0.186 at alpha=0): lean PASS'}),
]


def arm_phases(arm):
    tag, dth, M, rung, rot, pred = arm
    return lin(M, math.radians(dth), math.radians(rot))


def prepare(arms):
    """Inject the computed stack twist delta = fold(M*dtheta mod 360) into
    every arm's prediction dict (single source: stack_delta)."""
    return [(t, d, M, ro, rot, {**pr, 'delta': stack_delta(M, d)})
            for t, d, M, ro, rot, pr in arms]


def run_arm(device, tag, phases, rung_of, outdir, steps):
    solver = T.build_solver(device)          # fresh solver per arm
    r = L2.run_case2(solver, tag, phases, rung_of, outdir, steps)
    r['summary'] = L2.summarize2(r)
    return r


def finalize(runs, rdir, arms):
    def arm(tag):
        return next((r for r in runs if r['tag'] == tag), None)

    def c40(tag):
        return arm(tag)['summary']['t40']['C_abs']

    results = {'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT,
                        't_end': runs[0]['hist'][-1]['t'],
                        'wave': 'gauge-resolution wave (g1-g12, + g13-g17 '
                                'fine scans): clean-gauge re-measurement of '
                                'the clamp-polluted death arms',
                        'protocol': 'fresh solver per arm, t=40=2/lambda, '
                                    'init-only phases, canonical solver '
                                    'untouched, zero new terms'},
               'arms': {}}
    for r in runs:
        results['arms'][r['tag']] = {
            'phases': r['phases'], 'n_layers': r['n_layers'],
            'n_rungs': r['n_rungs'],
            'resonance_t0': r['resonance_t0'], 'summary': r['summary'],
            'elapsed_s': r['elapsed']}

    print(f"\n=== GAUGE-RESOLUTION WAVE (t=40) ===")
    verdicts = {}
    g5 = {}
    for tag, dth, M, rung, rot, pred in arms:
        r = arm(tag)
        if r is None:
            print(f"  {tag}: not in this run set")
            continue
        rt = r['resonance_t0']
        s = r['summary']
        A_D = array_factor(M, dth)
        C0, S0 = sin_cos_sums(r['phases'])
        born = born_class(C0, S0)
        line = (f"  {tag}: A_tot(0)={rt['A_tot']:9.3f} "
                f"ratio={rt['ratio_vs_analytic']:.5f} "
                f"ratio/A[D]={rt['ratio_vs_analytic'] / A_D:.5f} "
                f"floors={rt['floor_ey'] + rt['floor_ei']:5d} | "
                f"born {born} (|Ss/Sc|={abs(S0 / C0) if abs(C0) > 1e-12 else float('inf'):.4f}, "
                f"C_abs(0)={s['t0']['C_abs']:+.3f}) | "
                f"C_abs 0/4/40 = {s['t0']['C_abs']:+.3f}/"
                f"{s['t4']['C_abs']:+.3f}/{s['t40']['C_abs']:+.3f} | "
                f"d 0/4/40 = {s['t0']['d']:.2f}/{s['t4']['d']:.2f}/"
                f"{s['t40']['d']:.2f} dth(40)={s['t40']['delta_theta']:+.3f} "
                f"merged(40)={s['t40']['merged']} | "
                f"A_peak(40)/A_peak(0)={s['A_peak_ratio_t40']:.3f} "
                f"wind(40)={s['t40']['winding']:+.3f} | "
                f"mass drift {s['mass_drift']:.2e} NaN {s['nan']}")
        kind = pred['kind']
        v = None
        if kind == 'edge_test':
            v = ('BORN-FLAT 38 DEG PASSES: the alpha=0 38 deg death was '
                 'clamp-artifact; the born-flat band is 33-38 deg all-pass'
                 if c40(tag) >= 0.5 else
                 'BORN-FLAT 38 DEG DEATH CONFIRMED: the 38 deg death is a '
                 'real born-flat edge (outside the born-flat passing band)')
        elif kind == 'born_full_delta':
            v = (f"CLEAN BORN-FULL delta={pred['delta']} PASSES: the "
                 f"alpha=0 fail was clamp-influenced"
                 if c40(tag) >= 0.5 else
                 f"CLEAN BORN-FULL delta={pred['delta']} DEATH CONFIRMED")
        elif kind == 'born_flat_delta':
            v = (f"CLEAN BORN-FLAT delta={pred['delta']} PASSES: the "
                 f"m8_72-vs-f2 delta=144 split resolves to the flat class"
                 if c40(tag) >= 0.5 else
                 f"CLEAN BORN-FLAT delta={pred['delta']} DEATH CONFIRMED")
        elif kind == 'same_gauge':
            g5[tag] = c40(tag)
            v = f"gauge-229 row (born {born}, delta={pred['delta']}): " + \
                ('PASS >= 0.5' if c40(tag) >= 0.5 else 'FAIL < 0.5')
        elif kind == 'probe':
            v = 'probe (no pass/fail pre-registered)'
        elif kind == 'lean_pass':
            v = 'CONFIRMED (lean pass)' if c40(tag) >= 0.5 else \
                'CONTRADICTED (fail)'
        elif kind == 'lean_pass_floored':
            n_floor = rt['floor_ey'] + rt['floor_ei']
            if n_floor > 0.02 * T.N ** 3:
                v = ('INCONCLUSIVE (clamp-seeded; floors > 2%)')
            else:
                v = ('CONFIRMED (lean pass; ' +
                     f"{100.0 * n_floor / T.N ** 3:.1f}% floored) "
                     if c40(tag) >= 0.5 else 'CONTRADICTED (fail)')
        elif kind == 'fine_scan':
            v = 'CONFIRMED (lean pass)' if c40(tag) >= 0.5 else \
                'CONTRADICTED (fail)'
        if pred['born'] is not None and born != pred['born']:
            v += f" [BORN-CLASS DEVIATION: expected {pred['born']}]"
        verdicts[tag] = {'prediction': pred, 'verdict': v,
                         'A_derived': A_D, 'born': born}
        print(line)
        print(f"     prediction [{kind}]: {pred['note']}")
        print(f"     -> {v}")
    if g5:
        ok = all(c >= 0.5 for t, c in g5.items() if t in ('g5a', 'g5b')) and \
             all(c < 0.5 for t, c in g5.items() if t in ('g5c', 'g5d'))
        ok2 = all(c >= 0.5 for t, c in g5.items())
        g5v = ('GAUGE DISCRIMINATOR: delta-walk REAL (born-full passes at '
               'delta 180/135, dies at delta 90/45)'
               if ok else
               'GAUGE DISCRIMINATOR: the 45 deg failers are born-full-class '
               'deaths; born-flat 45 deg passes at all delta (22/23 pass '
               'born-flat)' if ok2 else
               'GAUGE DISCRIMINATOR: mixed reading -- see rows')
        print(f"     g5 discriminator: {g5v}")
        verdicts['g5_discriminator'] = g5v

    results['verdicts'] = verdicts
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults: {rdir}/results.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--steps', type=int, default=STEPS)
    parser.add_argument('--tend', type=float, default=None,
                        help='run to physical time tend (steps = tend/dt); '
                             'overrides --steps')
    parser.add_argument('--arm', action='append', default=None)
    parser.add_argument('--init-check', action='store_true')
    parser.add_argument('--rot', type=float, default=0.0, metavar='DEG',
                        help='override: global phase rotation (deg) applied '
                             'to every layer of every selected arm '
                             '(replaces the per-arm gauge)')
    parser.add_argument('--scan-rotation', action='store_true',
                        help='720-step born-class + floor scan per selected '
                             'arm with exact-path verification of the '
                             'per-arm gauge, print, exit')
    parser.add_argument('--fine', action='store_true',
                        help='run the g13-g17 fine scans instead of g1-g12 '
                             '(priority LOW)')
    parser.add_argument('--from-runs', default=None, metavar='DIR')
    parser.add_argument('--rid-suffix', default='lattice_stack_g',
                        metavar='SUFFIX')
    args = parser.parse_args()

    if args.from_runs is not None:
        import glob as _glob
        runs = []
        for f in sorted(_glob.glob(f"{args.from_runs}/run_*.json")):
            d = json.load(open(f))
            runs.append({'tag': d['kind'], 'phases': d['phases'],
                         'rung_of': d['rung_of'], 'elapsed': 0.0,
                         'resonance_t0': d['resonance_t0'],
                         'hist': d['hist'], 'profiles': d['profiles'],
                         'n_layers': d['n_layers'],
                         'n_rungs': d['n_rungs']})
            runs[-1]['summary'] = L2.summarize2(runs[-1])
        arms = ARMS + (FINE_ARMS if any(r['tag'].startswith('g1') and
                                        r['tag'] in ('g13',) for r in runs)
                       else ARMS)
        arms = prepare(arms)
        print(f"Rebuilding from {len(runs)} preserved arms in {args.from_runs}")
        finalize(runs, args.from_runs, arms)
        return

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if args.tend is not None:
        args.steps = int(round(args.tend / T.DT))
    arms = FINE_ARMS if args.fine else ARMS
    if args.arm is not None:
        arms = [a for a in arms if a[0] in args.arm]
        if not arms:
            raise SystemExit(f"no matching arms in {[a[0] for a in arms]}")
    arms = prepare(arms)
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t={args.steps * T.DT}  "
          f"born threshold |Ss/Sc| > {BORN_THRESH:.4f}")
    print(f"Arms: {', '.join(a[0] for a in arms)}")

    if args.rot:
        print(f"Global phase rotation override: +{args.rot:.3f} deg")
        arms = [(t, d, M, ro, args.rot, pr) for t, d, M, ro, _, pr in arms]

    if args.scan_rotation:
        for tag, dth, M, rung, rot, pred in arms:
            base = lin(M, math.radians(dth))          # unrotated phases
            sc = scan_born(device, base, report_alpha=rot)
            vf = verify_rotation(device, arm_phases((tag, dth, M, rung, rot,
                                                     pred)))
            ch = sc['chosen']
            print(f"  {tag} ({dth:.1f} deg, M={M}, alpha={rot:g}): "
                  f"{sc['n_zero_floor']}/{sc['n_rotations']} zero-floor "
                  f"rotations ({sc['n_zero_floor_born_full']} born-full, "
                  f"{sc['n_zero_floor_born_flat']} born-flat); windows deg: "
                  f"{sc['zero_floor_windows_deg']}")
            print(f"    chosen alpha={rot:g}: scan floors {ch['floors']} "
                  f"born {ch['born']} (|Ss/Sc|={ch['ratio_sin_cos']:.4f}, "
                  f"C_abs(an)={ch['C_abs_analytic']:+.3f}) | exact-path "
                  f"floors {vf['floors_ey']}/{vf['floors_ei']} "
                  f"min {vf['min_ey']:.4f}/{vf['min_ei']:.4f} | "
                  f"exact C_abs(0)={vf['C_abs_0']:+.3f} "
                  f"d(0)={vf['d_0']:.2f} present={vf['present']}")
        print("(scan only; rerun without --scan-rotation for the batch)")
        return

    if args.init_check:
        for tag, dth, M, rung, rot, pred in arms:
            phases = arm_phases((tag, dth, M, rung, rot, pred))
            solver = T.build_solver(device)
            ey_hat, ei_hat, u_hat, zs = L2.stack_init_phases(solver, phases)
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            windows = L1.layer_windows(solver.N, zs, solver.device)
            rt = L2.resonance_t0(solver, ey, ei, windows, zs, phases, 0.0, 0.0)
            rho_prof = (ey + ei).sum(dim=(1, 2)).cpu().numpy()
            rho_mean = float((ey + ei).mean())
            centers = [solver.N / 2.0 - L2.SEP / 2.0,
                       solver.N / 2.0 + L2.SEP / 2.0]
            d = L1.measure(solver, ey, ei, rho_prof, centers, None, windows,
                           zs, rho_mean)
            C0, S0 = sin_cos_sums(phases)
            born = born_class(C0, S0)
            print(f"  {tag} (alpha={rot:g}): A_tot={rt['A_tot']:10.3f} "
                  f"ratio={rt['ratio_vs_analytic']:.5f} "
                  f"min={rt['min_ey']:.4f}/{rt['min_ei']:.4f} "
                  f"floors={rt['floor_ey']}/{rt['floor_ei']} | "
                  f"born {born} C_abs(0)={d['C_abs']:+.3f} "
                  f"d(0)={d['d']:.2f}")
        print(f"(init check only; {len(arms)} arms)")
        return

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_{args.rid_suffix}"
    os.makedirs(rdir, exist_ok=True)

    runs = []
    for tag, dth, M, rung, rot, pred in arms:
        phases = arm_phases((tag, dth, M, rung, rot, pred))
        if args.arm is not None and tag not in args.arm:
            continue
        runs.append(run_arm(device, tag, phases, rung, rdir, args.steps))
    finalize(runs, rdir, arms)


if __name__ == "__main__":
    main()
