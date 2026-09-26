#!/usr/bin/env python3
"""Gauge-resolution wave (wave 6 of the lattice-stack program, labels g1-g12)
and residue-rule falsifier wave (wave 7, labels r1-r11).

Run:  python two-fluid/run_lattice_stack_gauge_wave.py
      (--steps N, --arm TAG repeatable, --init-check, --scan-rotation,
       --rot DEG, --from-runs DIR, --fine, --wave7)

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

Wave 7 (section 3.18, labels r1-r11) tests the hypothesized residue
mechanism behind the born-full retain set: born-full init survives iff
the twist residue res = (M*dtheta) mod 360 is 5-fold-commensurate, i.e.
the pentagon-lattice distance d72 = min_k |res - 72k| (k = 0..5) lies in
the pass set {0, 9, 36} against the fail band [14.4, 27], with the
measured gap (9, 14.4) separating them.  The boxed delta-set
{72, 135, 144, 180} and the d72 mechanism DISAGREE at delta = 136 deg
(d72 = 8, pass gap, but 136 not in the boxed set): arm r1 is the
headline discriminator.  All arms N = 48, t = 40, gate 'five', fresh
solver per arm; born class at the run gauge via |Ssin/Scos| vs 0.7468.

  r1:  34 deg, M = 4,  delta 136, d72 8    DISCRIMINATOR (no committed
       verdict; pass => mechanism governs, fail => boxed set exact)
  r2:  72 deg, M = 13, delta 144, d72 0    predict PASS (A = phi)
  r3:  54 deg, M = 12, delta 72,  d72 0    predict PASS
  r4:  54 deg, M = 10, delta 180, d72 36   predict PASS
  r5:  36 deg, M = 27, delta 108, d72 36   predict PASS (A = phi^2)
  r6:  60 deg, M = 9,  delta 180, d72 36   predict PASS
  r7:  45 deg, M = 19, delta 135, d72 9    predict PASS (boundary value)
  r8:  60 deg, M = 10, delta 120, d72 24   predict FAIL (death class)
  r9:  60 deg, M = 8,  delta 120, d72 24   predict FAIL (death class;
       runs at a clean born-full rotation, alpha ~ 248)
  r10: 54 deg, M = 11, delta 126, d72 18   predict FAIL (fail band)
  r11: 60 deg, M = 11, delta 60,  d72 12   GAP BOUNDARY LOCATOR (inside
       the measured gap (9, 14.4); no committed prediction -- report and
       classify: pass => boundary above 12, fail => boundary at/below 12)

Wave 8 (--wave8, labels r12-r21; section 3.19) tests the 2-point
family-height mnemonic of section 3.18 -- FAIL iff r = c+2 with
c = M//6, r = M mod 6 -- and the M*-vs-residue discriminator at 54 deg.
Same protocol: N = 48, t = 40, gate 'five', fresh solver per arm; arms
whose alpha = 0 gauge is born-flat run at a clean born-full rotation
found by the 720-step scan (r9-style); the run gauge is recorded per arm.

  r12: 60 deg, M = 13, res 60, d72 12, A = 1.0       PREDICT PASS (r=1)
  r13: 60 deg, M = 14, res 120, d72 24, A = sqrt 3   PREDICT PASS (r=2)
       CYCLE-2 DISCRIMINATOR: same (d,A,d72) class as M=8/10 (pass) and
       M=16 (fail); PASS => the M=16 death is r=4-specific
  r14: 60 deg, M = 17, res 300, d72 12, A = 1.0      PREDICT PASS (r=5)
  r15: 60 deg, M = 12, res 0, A = 0 EXACT (2-turn    NULL-BRANCH PROBE:
       null), born-NULL at every gauge                emergence +0.5..0.7
       predicted (f4-class); pass => the null is a live antinode
  r16: 60 deg, M = 16 at a clean BORN-FLAT rotation  PREDICT PASS (flip
       control at the death height; g4/g5c logic)     control)
  r17: 54 deg, M = 9, res 126, d72 18, A = 1.9626    PREDICT FAIL (band
       (= r10's A)                                    A-independence)
  r18: 54 deg, M = 13, res 342 (d 18), d72 18,       PREDICT FAIL (small-A
       A = 0.3446 (smallest envelope)                 fail-band probe)
  r19: 54 deg, M = 15, res 90, d72 18, A = 1.5575    M*-vs-RESIDUE
       M* = ceil(12.6331/0.88827) = 15                DISCRIMINATOR: M*
       rule says PASS, residue rule says FAIL
  r20: 30 deg, M = 40, res 120, d72 24, A = 3.3461   PREDICT FAIL per
       (sub-M*, M* = 47; floor caution: gauge-scan;  residue; a PASS
       INCONCLUSIVE if no clean rotation and > 2%)    transfers the anomaly
  r21: 60 deg, M = 23, res 300 (d 60), d72 12,       OPTIONAL FAR ARM
       A = 1.0, c = 3, r = 5                          (--far): PREDICT FAIL
       (r = c+2 encoding's first 3-cycle test); run only if the
       r12-r20 batch finishes cleanly

Wave 9 (--wave9, labels a1-a3, b1-b3, d1-d3, e1-e4, f1-f4, g1-g4,
h1-h2; section 3.20) is the height-selection wave: gauge invariance of
the one-sided rule (a/b at three born-full gauges), the 60 deg death
classes at c = 3 (e1/e2) plus the 4-turn test (e4) and the 3-turn null
(e3), the 54 deg M = 3 (mod 4) law at 6/6+4 (f1-f4), the 30 deg sub-M*
band (g1-g4), the 45 deg above-M* continuation (h1-h2), and rule R1 at
t = 80 (d1-d3, --tend 80 per arm via the arm's t_end).  Protocol change
W9-i: the hist record stores the full z,y-integrated rho(x) 48-vector at
every 0.05 report step (801 entries per t = 40 arm, 1601 per t = 80
arm), resolving the wave-8 endpoint caveat.

Output: runs/<rid>_lattice_stack_w8/run_<arm>.json + results.json (raw;
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


def residue(M, dth_deg):
    """Twist residue res = (M*dtheta) mod 360 (wave-7 mechanism input)."""
    return (M * dth_deg) % 360.0


def pentagon_distance(M, dth_deg):
    """d72 = min_k |res - 72k|, k = 0..5: the 5-fold-commensurability
    distance of the twist residue (wave-7 mechanism)."""
    res = residue(M, dth_deg)
    return min(abs(res - 72.0 * k) for k in range(6))


WAVE7_ARMS = [
    ('r1', 34.0, 4, None, 0.0,
     {'kind': 'discriminator', 'born': 'full',
      'A_derived': 3.17125, 'd72': 8.0,
      'note': 'THE DISCRIMINATOR: delta=136 deg, d72=8 (pass gap) but '
              '136 not in the boxed delta-set {72,135,144,180}. PASS => '
              'the residue mechanism governs (136 joins the retain set); '
              'FAIL => the boxed set is exact and the d72 gap was '
              'coincidence. A(4,34) = |sin 68/sin 17| = 3.1712. '
              'born-full at alpha=0 (|Ss/Sc|=1.2349); verify in '
              'init-check; if floors >= 2% pick a clean born-full gauge'}),
    ('r2', 72.0, 13, None, 195.0,
     {'kind': 'predict_pass', 'born': 'full',
      'A_derived': 1.61803, 'd72': 0.0,
      'note': 'delta=144 (936 mod 360 = 216 -> 144), d72=0; A(13,72) = '
              '|sin 468/sin 36| = 1.6180 = phi [D]. PREDICT PASS -- the '
              'cleanest probe; 452 clean rotations (288 born-full, 164 '
              'born-flat) per the scan; gauge 195 deg: clean born-full, '
              '|Ss/Sc| = 19.08 (the brief\'s 288 is the born-full COUNT, '
              'not the gauge -- alpha=288 is born-flat)'}),
    ('r3', 54.0, 12, None, 0.0,
     {'kind': 'predict_pass', 'born': 'full',
      'A_derived': 1.29471, 'd72': 0.0,
      'note': 'delta=72, d72=0; A(12,54) = |sin 324/sin 27| = 1.2947 [D]. '
              'PREDICT PASS -- the 54 deg family first born-full test '
              '(f1/f2 were born-full at clamp-touched gauges)'}),
    ('r4', 54.0, 10, None, 0.0,
     {'kind': 'predict_pass', 'born': 'full',
      'A_derived': 2.20269, 'd72': 36.0,
      'note': 'delta=180, d72=36; A(10,54) = |sin 270/sin 27| = 2.2027 '
              '[D]. PREDICT PASS'}),
    ('r5', 36.0, 27, None, 0.0,
     {'kind': 'predict_pass', 'born': 'full',
      'A_derived': 2.61803, 'd72': 36.0,
      'note': 'delta=108, d72=36; A(27,36) = |sin 486/sin 18| = 2.6180 = '
              'phi^2 [D]. PREDICT PASS -- the untested 5-fold complement '
              '(108 = 36+72)'}),
    ('r6', 60.0, 9, None, 0.0,
     {'kind': 'predict_pass', 'born': 'full',
      'A_derived': 2.0, 'd72': 36.0,
      'note': 'delta=180, d72=36; A(9,60) = |sin 270/sin 30| = 2.0 [D]. '
              'PREDICT PASS'}),
    ('r7', 45.0, 19, None, 0.0,
     {'kind': 'predict_pass', 'born': 'full',
      'A_derived': 2.41421, 'd72': 9.0,
      'note': 'delta=135, d72=9 (on the boundary); A(19,45) = |sin '
              '427.5/sin 22.5| = 2.4142 = 1+sqrt 2 [D]. PREDICT PASS '
              '(135 in the boxed set; d72=9 is the boundary value shared '
              'with w7/g5b)'}),
    ('r8', 60.0, 10, None, 0.0,
     {'kind': 'predict_fail', 'born': 'full',
      'A_derived': 1.73205, 'd72': 24.0,
      'note': 'delta=120, res=240, d72=24 (fail band); A(10,60) = |sin '
              '300/sin 30| = 1.732 = sqrt 3 [D]. PREDICT FAIL (120 deg '
              'death class; alpha=0 floors 35 = 0.03% per the wave-6 '
              'scan -- protocol-legal)'}),
    ('r9', 60.0, 8, None, 248.0,
     {'kind': 'predict_fail', 'born': 'full',
      'A_derived': 1.73205, 'd72': 24.0,
      'note': 'delta=120, res=120, d72=24 (fail band); A(8,60) = |sin '
              '240/sin 30| = 1.732 = sqrt 3 [D]. PREDICT FAIL (120 deg '
              'death class). Runs at a clean born-full rotation (alpha '
              '~ 248; 91 clean born-full rotations per the wave-6 scan); '
              'verify in init-check'}),
    ('r10', 54.0, 11, None, 0.0,
     {'kind': 'predict_fail', 'born': 'full',
      'A_derived': 1.96261, 'd72': 18.0,
      'note': 'delta=126, res=234, d72=18 (fail band); A(11,54) = |sin '
              '297/sin 27| = 1.9626 [D]. PREDICT FAIL'}),
    ('r11', 60.0, 11, None, 0.0,
     {'kind': 'gap_boundary', 'born': 'full',
      'A_derived': 1.0, 'd72': 12.0,
      'note': 'GAP BOUNDARY LOCATOR: delta=60, res=300, d72=12 -- INSIDE '
              'the measured gap (9, 14.4). NO committed prediction. PASS '
              '=> the boundary lies above 12 (gap extends to >= 12); '
              'FAIL => boundary at/below 12 (gap narrows toward the '
              'measured 14.4-fail). A(11,60) = |sin 330/sin 30| = 1.0 '
              '[D]; born-full at alpha=0 with 0 floors per the wave-6 '
              'scan'}),
]


WAVE8_ARMS = [
    ('r12', 60.0, 13, None, 321.5,
     {'kind': 'encoding_pass', 'born': 'full',
      'A_derived': 1.0, 'd72': 12.0, 'w_turns': 2.1667, 'c': 2, 'r': 1,
      'seam': 0.0,
      'note': '60 deg/M=13: res=60, d=60, d72=12 (pass gap), A(13,60) = '
              '|sin 390/sin 30| = 1.0 [D], w = 2.167 turns, c=2 r=1. '
              'PREDICT PASS (residue rule d72=12 + r != c+2 encoding). '
              'Born-FLAT at alpha=0 (|Ss/Sc| = 0) -> run at a clean '
              'born-full gauge (r9-style scan); FAIL would show the r=1 '
              'class dies at 2 cycles'}),
    ('r13', 60.0, 14, None, 293.0,
     {'kind': 'encoding_pass', 'born': 'full',
      'A_derived': 1.73205, 'd72': 24.0, 'w_turns': 2.3333, 'c': 2, 'r': 2,
      'seam': 60.0,
      'note': '60 deg/M=14: res=120, d=120, d72=24 (fail band), A(14,60) '
              '= |sin 420/sin 30| = sqrt 3 [D], w = 2.333 turns, c=2 r=2. '
              'THE CYCLE-2 DISCRIMINATOR: same (d,A,d72) class as M=8/10 '
              '(pass, below M*=12) and M=16 (fail, above); M=14 is above '
              'M*. Born-flat at alpha=0 -> rotated gauge (NO clean '
              'born-full rotation exists; alpha=293.0 is the lowest-floor '
              'born-full gauge, 4 floor cells = 0.004% (exact-path)). PASS '
              '=> the '
              'M=16 death is r=4-specific (encoding holds); FAIL => d=120 '
              'dies above M* regardless of r. PREDICT PASS per encoding'}),
    ('r14', 60.0, 17, None, 0.0,
     {'kind': 'encoding_pass', 'born': 'full',
      'A_derived': 1.0, 'd72': 12.0, 'w_turns': 2.8333, 'c': 2, 'r': 5,
      'seam': 240.0,
      'note': '60 deg/M=17: res=300, d=60, d72=12 (pass gap), A(17,60) = '
              '|sin 510/sin 30| = 1.0 [D], w = 2.833 turns, c=2 r=5. '
              'Born-FULL at alpha=0 (|Ss/Sc| = 1.732). PREDICT PASS per '
              'the encoding; FAIL falsifies it (r=5 dies at 2 cycles '
              'like r=4)'}),
    ('r15', 60.0, 12, None, 0.0,
     {'kind': 'null_branch', 'born': None,
      'A_derived': 0.0, 'd72': 0.0, 'w_turns': 2.0, 'c': 2, 'r': 0,
      'seam': 0.0,
      'note': '60 deg/M=12: res=0, d=0, d72=0, A(12,60) = |sin 360/sin '
              '30| = 0 EXACT (2-turn null), born-NULL at every gauge. '
              'THE NULL-BRANCH PROBE at the resonant height: f4-class '
              'emergence prediction (born-flat nulls emerge +0.5..0.7: '
              'f4 +0.677, f9 +0.504; d5 +0.146 and h2 +0.798 are the '
              '36/34.29 deg analogs). Pass here means the 2-turn null is '
              'a live antinode sitting exactly between the d=180 heights '
              '(9,15) and the d=120 heights (8,16)'}),
    ('r16', 60.0, 16, None, 285.0,
     {'kind': 'flip_control', 'born': 'flat',
      'A_derived': 1.73205, 'd72': 24.0, 'w_turns': 2.6667, 'c': 2, 'r': 4,
      'seam': 120.0,
      'note': '60 deg/M=16 at a CLEAN BORN-FLAT rotation (alpha=285.0; '
              '163 clean born-flat rotations per the scan, window '
              '(233.2, 306.8) inside [128.5, 321.5]). res=240, d=120, '
              'd72=24, A(16,60) = |sin 480/sin 30| = sqrt 3 [D]. THE '
              'BORN-CLASS FLIP CONTROL at the death height: g4/g5c logic '
              'says flat passes where full fails; f10/r9 is the M=8 '
              'mirror (flat +0.352 vs full +0.779). Pass => the M=16 '
              'death is born-full-class-specific; fail => 60/16 dies in '
              'both classes. PREDICT PASS'}),
    ('r17', 54.0, 9, None, 274.0,
     {'kind': 'band_fail', 'born': 'full',
      'A_derived': 1.96261, 'd72': 18.0, 'w_turns': 1.35, 'c': 1, 'r': 3,
      'seam': 72.0,
      'note': '54 deg/M=9: res=126, d=126, d72=18 (fail band), A(9,54) = '
              '|sin 243/sin 27| = 1.9626 [D] -- IDENTICAL to r10\'s A, '
              'w = 1.35 turns, c=1 r=3. Born-flat at alpha=0 by a hair '
              '(|Ss/Sc| = 0.727 < 0.7468) -> rotated gauge (NO clean '
              'rotation exists at any class; alpha=274.0 is a '
              'lowest-floor born-full gauge, 108 floor cells = 0.10%). '
              'PREDICT FAIL (d72=18 band) -- tests band A-independence '
              'and its extent below the M=10 pass'}),
    ('r18', 54.0, 13, None, 101.0,
     {'kind': 'band_fail', 'born': 'full',
      'A_derived': 0.34458, 'd72': 18.0, 'w_turns': 1.95, 'c': 2, 'r': 1,
      'seam': 288.0,
      'note': '54 deg/M=13: res=342 (folded d=18), d72=18, A(13,54) = '
              '|sin 351/sin 27| = 0.3446 [D] (smallest envelope in the '
              'program\'s proposal), w = 1.95 turns, c=2 r=1. Born-flat '
              'at alpha=0 -> rotated gauge (NO clean rotation exists; '
              'alpha=101.0 is a lowest-floor born-full gauge, 34 floor '
              'cells = 0.03%). PREDICT FAIL -- small-A fail-band probe'}),
    ('r19', 54.0, 15, None, 305.0,
     {'kind': 'mstar_discriminator', 'born': 'full',
      'A_derived': 1.55754, 'd72': 18.0, 'w_turns': 2.25, 'c': 2, 'r': 3,
      'seam': 36.0, 'M*': 15,
      'note': '54 deg/M=15: res=90, d=90, d72=18 (fail band), A(15,54) = '
              '|sin 405/sin 27| = 1.5575 [D], w = 2.25 turns, M* = '
              'ceil(12.6331/0.88827) = 15, c=2 r=3. Born-flat at alpha=0 '
              '(|Ss/Sc| = 0.325) -> rotated gauge (NO clean born-full '
              'rotation exists; the 5 clean rotations at [319.5, 321.5] '
              'are born-flat; alpha=305.0 is a lowest-floor born-full '
              'gauge, 59 floor cells = 0.05%). THE M*-vs-RESIDUE '
              'DISCRIMINATOR: the M* rule (passes at M* on 45/108/30 '
              'deg) says PASS; the residue rule (d72=18 fail band) says '
              'FAIL. At 54 deg M*=15 is NOT a null (unlike 60 deg), so '
              'this separates the two hypotheses'}),
    ('r20', 30.0, 40, None, 0.0,
     {'kind': 'transfer_probe', 'born': 'full',
      'A_derived': 3.34607, 'd72': 24.0, 'w_turns': 3.3333, 'c': 6, 'r': 4,
      'seam': 90.0,
      'note': '30 deg/M=40: res=120, d=120, d72=24 (fail band), A(40,30) '
              '= |sin 600/sin 15| = 3.3461 [D], w = 3.333 turns, sub-M* '
              '(M* = 47). Born-FULL at alpha=0 (|Ss/Sc| = 1.0). FLOOR '
              'CAUTION: the 30 deg family had structural floor contact '
              'at M=32 (f12) but zero floors at M=47 (w10); the 720-step '
              'scan finds NO clean rotation for M=40 (min floor cells '
              '443 = 0.4% at alpha ~278); alpha=0 runs with 1048 floor '
              'cells = 0.95% < 2% -- protocol-legal, family-comparison '
              'gauge (f12/w10 both ran at alpha=0). Verdict INCONCLUSIVE '
              'only if floors exceed 2%. THE 60-DEG TRANSFER ARM: does '
              '"d72=24 passes below M*" (60/8, 60/10) extend to a second '
              'family, or does the residue rule\'s fail band hold at 30 '
              'deg? PREDICT FAIL per residue; a PASS transfers the '
              'anomaly'}),
    ('r21', 60.0, 23, None, 0.0,
     {'kind': 'encoding_fail', 'born': 'full',
      'A_derived': 1.0, 'd72': 12.0, 'w_turns': 3.8333, 'c': 3, 'r': 5,
      'seam': 240.0,
      'note': 'OPTIONAL FAR ARM (run only if the batch finishes cleanly): '
              '60 deg/M=23: c=3, r=5, res=300 (d=60), d72=12 (pass gap), '
              'A(23,60) = |sin 690/sin 30| = 1.0 [D], w = 3.833 turns. '
              'Born-full class at alpha=0 per the r11 pattern. PREDICT '
              'FAIL per the encoding (r = c+2: 5 = 3+2) -- the '
              'mnemonic\'s first 3-cycle test'}),
]


WAVE9_ARMS = [
    # Wave 9 (section 3.20, labels a1-a3, b1-b3, d1-d3, e1-e4, f1-f4, g1-g4,
    # h1-h2): the height-selection wave.  Same protocol (N = 48, gate
    # 'five', fresh solver per arm, init-only phases, canonical solver
    # untouched) plus the W9-i protocol change: the hist record stores the
    # full z,y-integrated rho(x) 48-vector at every 0.05 report step,
    # resolving the wave-8 endpoint caveat (last-2-time-unit ridge-tracker
    # snaps).  Born-full per arm verified by the 720-step scan; the seam
    # shifts with the gauge alpha, the verdicts must not (batch 1).
    #
    # Batch 1 -- gauge invariance (54 deg/M=12 baseline r3 PASS +0.854,
    # d72=0; 54 deg/M=11 baseline r10 FAIL -1.428, d72=18, M=11 = 3 mod 4):
    ('a1', 54.0, 12, None, 0.0,
     {'kind': 'gauge_pass', 'born': 'full', 'A_derived': 1.29471,
      'w_turns': 1.8,
      'note': '54 deg/M=12 (r3 baseline) at born-full gauge alpha=0 '
              '(98 floor cells = 0.09%; no zero-floor rotation exists '
              'for this arm): PREDICT PASS +0.6..0.95 -- '
              'gauge-invariance row 1/3'}),
    ('a2', 54.0, 12, None, 26.0,
     {'kind': 'gauge_pass', 'born': 'full', 'A_derived': 1.29471,
      'w_turns': 1.8,
      'note': '54 deg/M=12 at alpha=26.0 (born-full island edge nearest '
              'the intended 60 deg -- alpha=60 itself is born-flat; '
              '90 floor cells = 0.08%): PREDICT PASS +0.6..0.95 -- '
              'gauge-invariance row 2/3'}),
    ('a3', 54.0, 12, None, 120.0,
     {'kind': 'gauge_pass', 'born': 'full', 'A_derived': 1.29471,
      'w_turns': 1.8,
      'note': '54 deg/M=12 at alpha=120.0 (born-full island mid, 77 floor '
              'cells = 0.07%): PREDICT PASS +0.6..0.95 -- '
              'gauge-invariance row 3/3'}),
    ('b1', 54.0, 11, None, 0.0,
     {'kind': 'gauge_fail', 'born': 'full', 'A_derived': 1.96261,
      'w_turns': 1.65,
      'note': '54 deg/M=11 (r10 baseline) at alpha=0: PREDICT FAIL '
              '(d72=18, M=11 = 3 mod 4 death class) -- gauge-invariance '
              'row 1/3'}),
    ('b2', 54.0, 11, None, 53.0,
     {'kind': 'gauge_fail', 'born': 'full', 'A_derived': 1.96261,
      'w_turns': 1.65,
      'note': '54 deg/M=11 at alpha=53.0 (born-full island edge nearest '
              'the intended 60 deg -- alpha=60 itself is born-flat; 154 '
              'floor cells = 0.14%): PREDICT FAIL -- gauge-invariance '
              'row 2/3'}),
    ('b3', 54.0, 11, None, 127.0,
     {'kind': 'gauge_fail', 'born': 'full', 'A_derived': 1.96261,
      'w_turns': 1.65,
      'note': '54 deg/M=11 at alpha=127.0 (born-full island edge nearest '
              'the intended 120 deg; 192 floor cells = 0.17%): PREDICT '
              'FAIL -- gauge-invariance row 3/3'}),
    # Batch 2 -- 60 deg height scans (2-cycle-specificity at c=3; the
    # one-sided rule's high-cycle test):
    ('e1', 60.0, 21, None, 256.5,
     {'kind': 'height_pass', 'born': 'full', 'A_derived': 2.0,
      'w_turns': 3.5,
      'note': '60 deg/M=21: res=180, d=180, d72=36, A=2.0 -- the M=9 '
              'A-class at c=3, w=3.5: PREDICT PASS (the 60 deg M=9 death '
              'must not recur at c=3); alpha=256.5 is a clean born-full '
              'gauge (zero floors, window [256.5, 319.0], |Ss/Sc|=0.949)'}),
    ('e2', 60.0, 22, None, 205.5,
     {'kind': 'height_pass', 'born': 'full', 'A_derived': 1.73205,
      'w_turns': 3.6667,
      'note': '60 deg/M=22: res=240, d=120, d72=24, A=sqrt3 -- the M=16 '
              'A-class at c=3, w=3.667: PREDICT PASS (the M=16 death '
              'must not recur at c=3); alpha=205.5 is a clean born-full '
              'gauge (zero floors, window [205.5, 305.5], |Ss/Sc|=2.10)'}),
    ('e3', 60.0, 18, None, 0.0,
     {'kind': 'null_probe', 'born': 'null', 'A_derived': 0.0,
      'w_turns': 3.0,
      'note': '60 deg/M=18: res=0, d72=0, A=0 EXACT -- the 3-turn hexagon '
              'null: PREDICT DEAD NULL (C(40) < 0.5; r15 peaked +0.967@20 '
              'then decayed)'}),
    ('e4', 60.0, 25, None, 90.0,
     {'kind': 'height_pass', 'born': 'full', 'A_derived': 1.0,
      'w_turns': 4.1667,
      'note': '60 deg/M=25: res=60, d=60, d72=12, A=1.0, w=4.167 -- the '
              'one-sided rule\'s 4-turn test: PREDICT PASS; alpha=0 is '
              'born-flat, alpha=90.0 is a clean born-full gauge (zero '
              'floors)'}),
    # Batch 3 -- 54 deg M = 3 (mod 4) falsifiers (the 6/6 height law):
    ('f1', 54.0, 14, None, 332.0,
     {'kind': 'law_pass', 'born': 'full', 'A_derived': 0.68072,
      'w_turns': 2.1,
      'note': '54 deg/M=14: res=36, d=36, d72=36, A=0.681, w=2.1, M=14 = '
              '2 mod 4: PREDICT PASS; alpha=0 is born-flat, alpha=332.0 '
              'is the lowest-floor born-full gauge (3 cells = 0.003%; no '
              'clean rotation exists for this arm)'}),
    ('f2', 54.0, 17, None, 241.0,
     {'kind': 'law_pass', 'born': 'full', 'A_derived': 2.17557,
      'w_turns': 2.55,
      'note': '54 deg/M=17: res=198, d=162, d72=18, w=2.55, M=17 = 1 '
              'mod 4: PREDICT PASS (d72=18 but outside the death class); '
              'alpha=241.0 is a clean born-full gauge (zero floors, '
              'window [241.0, 302.5], |Ss/Sc|=1.07)'}),
    ('f3', 54.0, 19, None, 0.0,
     {'kind': 'law_fail', 'born': 'full', 'A_derived': 1.0,
      'w_turns': 2.85,
      'note': '54 deg/M=19: res=306, d=54, d72=18, A=1.0, w=2.85, M=19 = '
              '3 mod 4: PREDICT FAIL (the law continues above M*=15)'}),
    ('f4', 54.0, 16, None, 278.0,
     {'kind': 'clean_gauge_pass', 'born': 'full', 'A_derived': 2.09488,
      'w_turns': 2.4,
      'note': '54 deg/M=16 at the lowest-floor born-full gauge '
              'alpha=278.0 (35 cells = 0.032%; the w8 alpha=0 born-full '
              'reading was clamp-polluted with 531 floors, and no clean '
              'zero-floor born-full rotation exists -- the 48 clean '
              'rotations in [285.5, 309.0] are all born-flat): PREDICT '
              'PASS (d72=0 + M=16 = 0 mod 4)'}),
    # Batch 4 -- 30 deg sub-M* band (M* = 47; one clean born-full reading
    # so far):
    ('g1', 30.0, 41, None, 0.0,
     {'kind': 'band_pass', 'born': 'full', 'A_derived': 3.73205,
      'w_turns': 3.4167,
      'note': '30 deg/M=41: res=150, d72=6: PREDICT PASS'}),
    ('g2', 30.0, 43, None, 0.0,
     {'kind': 'band_pass', 'born': 'full', 'A_derived': 3.73205,
      'w_turns': 3.5833,
      'note': '30 deg/M=43: res=210, d72=6: PREDICT PASS'}),
    ('g3', 30.0, 46, None, 157.5,
     {'kind': 'band_pass', 'born': 'full', 'A_derived': 1.93185,
      'w_turns': 3.8333,
      'note': '30 deg/M=46: res=300, d=60, d72=12: PREDICT PASS; '
              'alpha=157.5 is a clean born-full gauge (zero floors, '
              'window [157.0, 262.5], |Ss/Sc|=2.41)'}),
    ('g4', 30.0, 44, None, 0.0,
     {'kind': 'band_probe', 'born': 'full', 'A_derived': 3.34607,
      'w_turns': 3.6667,
      'note': '30 deg/M=44: res=240, d=120, d72=24, w=3.667, M-M*=-3: '
              'NO COMMITTED PREDICTION (decides the 30 deg death-class '
              'structure: sub-M* d72=24 band vs M=40-specific)'}),
    # Batch 5 -- 45 deg above-M* (death continuation):
    ('h1', 45.0, 25, None, 323.0,
     {'kind': 'above_mstar_fail', 'born': 'full', 'A_derived': 1.0,
      'w_turns': 3.125,
      'note': '45 deg/M=25: res=45, d=45, d72=27, A=1.0, w=3.125: '
              'PREDICT FAIL (above M*=21, d72 >= 18); alpha=0 is '
              'born-flat, alpha=323.0 is a clean born-full gauge (zero '
              'floors, window [308.0, 359.5])'}),
    ('h2', 45.0, 26, None, 300.5,
     {'kind': 'above_mstar_fail', 'born': 'full', 'A_derived': 1.84776,
      'w_turns': 3.25,
      'note': '45 deg/M=26: res=90, d=90, d72=18, w=3.25: PREDICT FAIL '
              '(above M*=21); alpha=0 is born-flat, alpha=300.5 is the '
              'lowest-floor born-full gauge (43 cells = 0.039%; no clean '
              'born-full rotation exists)'}),
    # Batch 6 -- t=80 continuations (rule R1 at 8/lambda):
    ('d1', 34.0, 4, None, 0.0,
     {'kind': 'continuation', 'born': 'full', 'A_derived': 3.17125,
      'w_turns': 0.3778, 't_end': 80.0,
      'note': 'r1 continuation (34 deg/M=4, d72=8, stationary class): '
              'PREDICT C_abs(80) >= 0.5 with continued churn; terminal '
              'crossing up-or-none at 80'}),
    ('d2', 60.0, 11, None, 0.0,
     {'kind': 'continuation', 'born': 'full', 'A_derived': 1.0,
      'w_turns': 1.8333, 't_end': 80.0,
      'note': 'r11 continuation (60 deg/M=11, d72=12 gap boundary): '
              'PREDICT C_abs(80) in [0.4, 0.9] with elevated winding'}),
    ('d3', 54.0, 11, None, 0.0,
     {'kind': 'continuation', 'born': 'full', 'A_derived': 1.96261,
      'w_turns': 1.65, 't_end': 80.0,
      'note': 'r10 continuation (54 deg/M=11, d72=18 fail class): '
              'PREDICT C_abs(80) < -1.0 (inversion stable sink)'}),
]


def arm_phases(arm):
    tag, dth, M, rung, rot, pred = arm
    return lin(M, math.radians(dth), math.radians(rot))


def prepare(arms):
    """Inject the computed stack twist delta = fold(M*dtheta mod 360) and
    the pentagon distance d72 = min_k |res - 72k| into every arm's
    prediction dict (single source: stack_delta / pentagon_distance)."""
    return [(t, d, M, ro, rot, {**pr, 'delta': stack_delta(M, d),
                                'd72': pentagon_distance(M, d)})
            for t, d, M, ro, rot, pr in arms]


def run_arm(device, tag, phases, rung_of, outdir, steps):
    solver = T.build_solver(device)          # fresh solver per arm
    r = L2.run_case2(solver, tag, phases, rung_of, outdir, steps)
    r['summary'] = L2.summarize2(r)
    return r


def run_arm_w9(device, tag, phases, rung_of, outdir, steps):
    """Wave-9 arm: identical protocol to run_case2 (fresh solver, t = 40 =
    2/lambda default, init-only phases) with the W9-i protocol change --
    the z,y-integrated rho(x) 48-vector is stored in every 0.05 report
    step of the hist record (full record; ~0.4 MB/arm at t = 40),
    resolving the wave-8 endpoint caveat: the t in [36, 40] verdicts can
    be re-read from the raw profiles instead of the ridge-tracker snaps."""
    M = len(phases)
    print(f"\n=== run: {tag} (layers={M}, rungs="
          f"{max(rung_of) + 1 if rung_of else 1}) ===")
    ey_hat, ei_hat, u_hat, zs = L2.stack_init_phases(solver :=
                                                     T.build_solver(device),
                                                     phases)
    centers = [solver.N / 2.0 - L2.SEP / 2.0, solver.N / 2.0 + L2.SEP / 2.0]
    windows = L1.layer_windows(solver.N, zs, solver.device)
    ey0 = torch.fft.ifftn(ey_hat).real
    ei0 = torch.fft.ifftn(ei_hat).real
    res0 = L2.resonance_t0(solver, ey0, ei0, windows, zs, phases, 0.0, 0.0)
    res0['min_ey'] = float(ey0.min())
    res0['min_ei'] = float(ei0.min())
    print(f"  t=0: A_tot={res0['A_tot']:.4f} (s_tot={res0['s_tot_analytic']:.2f}, "
          f"ratio={res0['ratio_vs_analytic']:.5f}) | "
          f"min fields {res0['min_ey']:.4f}/{res0['min_ei']:.4f} | "
          f"floor cells {res0['floor_ey']}/{res0['floor_ei']}")

    t0 = time.time()
    hist = []
    prev = None
    profiles = {}
    S0 = L1.slab_phasor(ey0, ei0, L2.RHO0).cpu().numpy()
    J0, F0, _, _ = L1.current_profiles(solver, ey0, ei0, zs)
    profiles['0.0'] = {'A': np.abs(S0).tolist(), 'arg': np.angle(S0).tolist(),
                       'Jz': J0.tolist(), 'Fc': F0.tolist()}
    for step in range(steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step % T.REPORT == 0 or step == steps - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            rho_prof = (ey + ei).sum(dim=(1, 2)).cpu().numpy()
            rho_bg = L2.RHO0 if step == 0 else float((ey + ei).mean())
            d = L2.measure2(solver, ey, ei, rho_prof, centers, prev,
                            windows, zs, rho_bg, rung_of)
            prev = ([d['x1'], d['x2']] if not d['merged'] else [d['x1']])
            d.update({'step': step, 't': step * T.DT,
                      'rho_prof': rho_prof.tolist()})
            hist.append(d)
            if abs(step * T.DT - 4.0) < 0.6 or abs(step * T.DT - 40.0) < 0.6 \
                    or step == steps - 1:
                rho_m = float((ey + ei).mean())
                Sn = L1.slab_phasor(ey, ei, rho_m).cpu().numpy()
                Jn, Fn, _, _ = L1.current_profiles(solver, ey, ei, zs)
                profiles[f"{step * T.DT:.1f}"] = {
                    'A': np.abs(Sn).tolist(), 'arg': np.angle(Sn).tolist(),
                    'Jz': Jn.tolist(), 'Fc': Fn.tolist()}
            if step % 1000 == 0 or step == steps - 1:
                print(f"  t={step*T.DT:6.2f} | d={d['d']:6.3f} "
                      f"Rc={d['Rc']:6.2f} | A_peak={d['A_peak']:7.2f} "
                      f"C_abs={d['C_abs']:+.3f} wind={d['winding']:+6.3f} "
                      f"|Jz|={d['Jz_abs_mean']:8.1f} | q_mid={d['q_mid']:.4f} "
                      f"q_flank={d['q_flank']:.4f} | "
                      f"ey_min={d['ey_min']:.4f} ei_min={d['ei_min']:.4f}")
    elapsed = time.time() - t0
    print(f"  [{tag}] {steps} steps in {elapsed:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'phases': phases,
                       'rung_of': rung_of,
                       'n_layers': M,
                       'n_rungs': max(rung_of) + 1 if rung_of else 1,
                       'zs': zs, 'steps': steps,
                       'resonance_t0': res0, 'profiles': profiles,
                       'hist': hist}, f, indent=1)
    r = {'tag': tag, 'phases': phases, 'rung_of': rung_of,
         'n_layers': M, 'n_rungs': max(rung_of) + 1 if rung_of else 1,
         'elapsed': elapsed, 'resonance_t0': res0, 'hist': hist,
         'profiles': profiles}
    r['summary'] = L2.summarize2(r)
    return r


def finalize_w9(runs, rdir, arms):
    """Wave-9 report: per-arm raw line (gauge, born class, A ratio vs [D],
    C_abs 0/4/36/38/40, d 0/4/40, dth, retention, merged, floors, drift,
    NaN, runtime), the W9-i profile-storage verification, and the verdict
    table against the pre-registered predictions."""
    def arm(tag):
        return next((r for r in runs if r['tag'] == tag), None)

    wave_str = ('wave 9 (a1-a3, b1-b3, d1-d3, e1-e4, f1-f4, g1-g4, h1-h2): '
                'the height-selection wave -- gauge invariance of the '
                'one-sided rule at 54 deg (a/b), the 60 deg death-class '
                'non-recurrence at c=3 (e1-e2) and the 4-turn test (e4), '
                'the 3-turn hexagon null (e3), the 54 deg M = 3 (mod 4) '
                'height law at 6/6+4 (f1-f4), the 30 deg sub-M* band '
                '(g1-g4), the 45 deg above-M* death continuation (h1-h2), '
                'and rule R1 at t = 80 (d1-d3); protocol change W9-i: '
                'full z,y-integrated rho(x) profile record at every 0.05 '
                'step resolves the wave-8 endpoint caveat')
    results = {'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT,
                        't_end': runs[0]['hist'][-1]['t'],
                        'wave': wave_str,
                        'protocol': 'fresh solver per arm, t=40=2/lambda '
                                    '(t=80 for d1-d3), init-only phases, '
                                    'canonical solver untouched, zero new '
                                    'terms, W9-i profile record'},
               'arms': {}}
    verdicts = {}
    print(f"\n=== HEIGHT-SELECTION WAVE (W9) ===")
    for tag, dth, M, rung, rot, pred in arms:
        r = arm(tag)
        if r is None:
            print(f"  {tag}: not in this run set")
            continue
        rt = r['resonance_t0']
        s = r['summary']
        h = r['hist']
        A_D = pred['A_derived']
        C0, S0 = sin_cos_sums(r['phases'])
        born = born_class(C0, S0)
        c36 = L2.at_t(h, 36.0)['C_abs']
        c38 = L2.at_t(h, 38.0)['C_abs']
        c_t = L2.at_t(h, pred.get('t_end', 40.0))
        c40 = s['t40']['C_abs']
        n_floor = rt['floor_ey'] + rt['floor_ei']
        line = (f"  {tag} (alpha={rot:g}): A_tot(0)={rt['A_tot']:9.3f} "
                f"ratio={rt['ratio_vs_analytic']:.5f} "
                f"ratio/A[D]={(rt['ratio_vs_analytic'] / A_D if A_D > 1e-9 else float('inf')):.5f} "
                f"floors={n_floor:5d} | "
                f"res={residue(M, dth):g} d={stack_delta(M, dth):g} "
                f"d72={pentagon_distance(M, dth):g} A[D]={A_D:g} | "
                f"born {born} (|Ss/Sc|={abs(S0 / C0) if abs(C0) > 1e-12 else float('inf'):.4f}, "
                f"C_abs(0)={s['t0']['C_abs']:+.3f}) | "
                f"C_abs 0/4/36/38/{pred.get('t_end', 40.0):g} = "
                f"{s['t0']['C_abs']:+.3f}/{s['t4']['C_abs']:+.3f}/"
                f"{c36:+.3f}/{c38:+.3f}/{c_t['C_abs']:+.3f} | "
                f"d 0/4/40 = {s['t0']['d']:.2f}/{s['t4']['d']:.2f}/"
                f"{s['t40']['d']:.2f} dth(40)={s['t40']['delta_theta']:+.3f} "
                f"merged(40)={s['t40']['merged']} | "
                f"A_peak(40)/A_peak(0)={s['A_peak_ratio_t40']:.3f} "
                f"wind(40)={s['t40']['winding']:+.3f} | "
                f"mass drift {s['mass_drift']:.2e} NaN {s['nan']} | "
                f"{r['elapsed']:.0f}s")
        if pred.get('t_end', 40.0) > 40.0:
            line += (f" | C_abs(80)={c_t['C_abs']:+.3f} "
                     f"d(80)={c_t['d']:.2f} dth(80)={c_t['delta_theta']:+.3f} "
                     f"wind(80)={c_t['winding']:+.3f}")
        kind = pred['kind']
        v = None
        if kind == 'gauge_pass':
            v = (f"GAUGE PASS CONFIRMED (C_abs(40)={c40:+.3f} in the "
                 f"pre-registered +0.6..0.95 band)"
                 if 0.6 <= c40 <= 0.95 else
                 f"GAUGE PASS DEVIATION (C_abs(40)={c40:+.3f} outside "
                 f"+0.6..0.95)" if c40 >= 0.5 else
                 f"GAUGE PASS CONTRADICTED (C_abs(40)={c40:+.3f} < 0.5)")
        elif kind == 'gauge_fail':
            v = (f"GAUGE FAIL CONFIRMED (C_abs(40)={c40:+.3f} < 0.5)"
                 if c40 < 0.5 else
                 f"GAUGE FAIL CONTRADICTED (C_abs(40)={c40:+.3f} >= 0.5)")
        elif kind == 'height_pass':
            v = (f"CONFIRMED (pass; the death class does not recur at "
                 f"c=3)" if c40 >= 0.5 else
                 f"CONTRADICTED (fail; the death class recurs at c=3)")
        elif kind == 'null_probe':
            v = (f"DEAD NULL CONFIRMED (C_abs(40)={c40:+.3f} < 0.5)"
                 if c40 < 0.5 else
                 f"NULL EMERGENCE (C_abs(40)={c40:+.3f} >= 0.5)")
        elif kind == 'law_pass':
            v = (f"CONFIRMED (pass; outside the M = 3 (mod 4) death "
                 f"class)" if c40 >= 0.5 else
                 f"CONTRADICTED (fail)")
        elif kind == 'law_fail':
            v = (f"CONFIRMED (fail; the M = 3 (mod 4) law holds at "
                 f"M=19 above M*)" if c40 < 0.5 else
                 f"CONTRADICTED (pass; the law breaks above M*)")
        elif kind == 'clean_gauge_pass':
            if n_floor > 0.02 * T.N ** 3:
                v = 'INCONCLUSIVE (clamp-seeded; floors > 2%)'
            else:
                v = (f"CONFIRMED (pass; clean born-full d72=0 at "
                     f"alpha={rot:g}, {n_floor} floors)"
                     if c40 >= 0.5 else
                     f"CONTRADICTED (fail at the clean gauge)")
        elif kind == 'band_pass':
            v = (f"CONFIRMED (pass; the 30 deg sub-M* band retains)"
                 if c40 >= 0.5 else
                 f"CONTRADICTED (fail in the sub-M* band)")
        elif kind == 'band_probe':
            v = (f"NO COMMITTED PREDICTION: d72=24 at M=44 (sub-M*) "
                 f"-> C_abs(40)={c40:+.3f} "
                 + ('(passes: the d72=24 death is M=40-specific)'
                    if c40 >= 0.5 else
                    '(fails: the sub-M* d72=24 band dies at 30 deg)'))
        elif kind == 'above_mstar_fail':
            v = (f"CONFIRMED (fail; the 45 deg above-M* death "
                 f"continues)" if c40 < 0.5 else
                 f"CONTRADICTED (pass above M*=21)")
        elif kind == 'continuation':
            tE = pred['t_end']
            cE = c_t['C_abs']
            if tag == 'd1':
                v = (f"CONFIRMED (C_abs({tE:g})={cE:+.3f} >= 0.5)"
                     if cE >= 0.5 else
                     f"CONTRADICTED (C_abs({tE:g})={cE:+.3f} < 0.5)")
            elif tag == 'd2':
                v = (f"CONFIRMED (C_abs({tE:g})={cE:+.3f} in [0.4, 0.9])"
                     if 0.4 <= cE <= 0.9 else
                     f"DEVIATION (C_abs({tE:g})={cE:+.3f} outside "
                     f"[0.4, 0.9])")
            else:
                v = (f"CONFIRMED (C_abs({tE:g})={cE:+.3f} < -1.0, "
                     f"inversion stable sink)"
                     if cE < -1.0 else
                     f"DEVIATION (C_abs({tE:g})={cE:+.3f} >= -1.0)")
        if pred['born'] is not None and born != pred['born']:
            v += f" [BORN-CLASS DEVIATION: expected {pred['born']}]"
        verdicts[tag] = {'prediction': pred, 'verdict': v, 'born': born,
                         'C_abs_t40': c40, 'floors': n_floor,
                         'elapsed_s': r['elapsed']}
        print(line)
        print(f"     prediction [{kind}]: {pred['note']}")
        print(f"     -> {v}")

    # W9-i profile-storage verification (the endpoint-caveat resolution)
    prof_ok = {}
    for tag, dth, M, rung, rot, pred in arms:
        r = arm(tag)
        if r is None:
            continue
        h = r['hist']
        lens = set(len(e['rho_prof']) for e in h)
        ts = sorted(set(round(e['t'], 6) for e in h))
        gaps = [round(b - a, 3) for a, b in zip(ts, ts[1:])]
        # every interior report step is 0.05 apart; only the terminal
        # snap (step == steps-1 -> t = t_end - dt) may be a partial gap
        dense = len(gaps) < 2 or (
            all(abs(g - 0.05) < 1e-9 for g in gaps[:-1])
            and 0.0 < gaps[-1] <= 0.05 + 1e-9)
        tail = [e for e in h if 36.0 <= e['t'] <= pred.get('t_end', 40.0)]
        tg = [round(b['t'], 6) - round(a['t'], 6)
              for a, b in zip(tail, tail[1:])]
        tail_dense = (len(tg) < 2 or
                      (all(abs(g - 0.05) < 1e-9 for g in tg[:-1])
                       and 0.0 < tg[-1] <= 0.05 + 1e-9))
        prof_ok[tag] = {'entries': len(h), 'rho_len': sorted(lens),
                        'dense_0.05': dense, 'tail_entries': len(tail),
                        'tail_dense': tail_dense,
                        'tail_span': [round(tail[0]['t'], 2),
                                      round(tail[-1]['t'], 2)] if tail
                                      else None}
        print(f"  [W9-i] {tag}: {len(h)} profile entries "
              f"(len {sorted(lens)}), dense-0.05={dense}, "
              f"tail [{prof_ok[tag]['tail_span'][0]}, "
              f"{prof_ok[tag]['tail_span'][1]}] {len(tail)} entries "
              f"dense={tail_dense}")
    results['profile_record'] = prof_ok

    # Composite verdicts
    ga = [arm(t) for t in ('a1', 'a2', 'a3')]
    gb = [arm(t) for t in ('b1', 'b2', 'b3')]
    if all(g is not None for g in ga + gb):
        ok = all(L2.at_t(g['hist'], 40.0)['C_abs'] >= 0.5 for g in ga) and \
             all(L2.at_t(g['hist'], 40.0)['C_abs'] < 0.5 for g in gb)
        verdicts['gauge_invariance'] = (
            'GAUGE INVARIANCE CONFIRMED: all three born-full gauges pass '
            'a1/a2/a3 and fail b1/b2/b3 -- the one-sided rule is '
            'gauge-invariant under common rotation (seam shifts, verdicts '
            'do not)' if ok else
            'GAUGE INVARIANCE REFUTED: at least one verdict flips with '
            'the gauge')
        print(f"     composite: {verdicts['gauge_invariance']}")
    results['verdicts'] = verdicts
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults: {rdir}/results.json")


def finalize(runs, rdir, arms, wave='g'):
    if wave == 'w9':
        return finalize_w9(runs, rdir, arms)

    def arm(tag):
        return next((r for r in runs if r['tag'] == tag), None)

    def c40(tag):
        return arm(tag)['summary']['t40']['C_abs']

    if wave == 'w8':
        wave_str = ('wave 8 (r12-r21): the 60 deg family-height encoding '
                    'r != c+2 at 2 cycles (r12-r14), the 2-turn null '
                    'branch at 60/12 (r15), the born-class flip at 60/16 '
                    '(r16), the d72=18 fail band at 54 deg (r17-r18), '
                    'the M*-vs-residue discriminator at 54 deg (r19), '
                    'the 30 deg transfer probe (r20), the 3-cycle far '
                    'arm (r21)')
    elif any(r['tag'] == 'r1' for r in runs):
        wave_str = ('residue-rule falsifier wave (r1-r11): '
                    'the d72 = min_k|res - 72k| mechanism vs '
                    'the boxed delta-set {72,135,144,180}; '
                    'r1 = the delta=136 discriminator; r11 = '
                    'the gap-boundary locator')
    else:
        wave_str = ('gauge-resolution wave (g1-g12, + '
                    'g13-g17 fine scans): clean-gauge '
                    're-measurement of the '
                    'clamp-polluted death arms')
    results = {'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT,
                        't_end': runs[0]['hist'][-1]['t'],
                        'wave': wave_str,
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

    print(f"\n=== {'M*-VS-RESIDUE WAVE' if wave == 'w8' else 'GAUGE-RESOLUTION WAVE'} (t=40) ===")
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
                f"delta={pred['delta']:g} d72={pred['d72']:g} | "
                f"born {born} (|Ss/Sc|={abs(S0 / C0) if abs(C0) > 1e-12 else float('inf'):.4f}, "
                f"C_abs(0)={s['t0']['C_abs']:+.3f}) | ")
        if wave == 'w8':
            h = r['hist']
            c36 = L2.at_t(h, 36.0)['C_abs']
            c38 = L2.at_t(h, 38.0)['C_abs']
            line += (f"C_abs 0/4/36/38/40 = {s['t0']['C_abs']:+.3f}/"
                     f"{s['t4']['C_abs']:+.3f}/{c36:+.3f}/{c38:+.3f}/"
                     f"{s['t40']['C_abs']:+.3f} | "
                     f"d 0/4/40 = {s['t0']['d']:.2f}/{s['t4']['d']:.2f}/"
                     f"{s['t40']['d']:.2f} dth(40)={s['t40']['delta_theta']:+.3f} "
                     f"merged(40)={s['t40']['merged']} | "
                     f"A_peak(40)/A_peak(0)={s['A_peak_ratio_t40']:.3f} "
                     f"wind(40)={s['t40']['winding']:+.3f} | "
                     f"mass drift {s['mass_drift']:.2e} NaN {s['nan']}")
        else:
            line += (f"C_abs 0/4/40 = {s['t0']['C_abs']:+.3f}/"
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
        elif kind == 'discriminator':
            v = (f"DISCRIMINATOR: delta={pred['delta']:g} (d72="
                 f"{pred['d72']:g}, pass gap) PASSES -> the residue "
                 f"mechanism governs; the boxed delta-set extends to "
                 f"{pred['delta']:g} deg"
                 if c40(tag) >= 0.5 else
                 f"DISCRIMINATOR: delta={pred['delta']:g} (d72="
                 f"{pred['d72']:g}, pass gap) DIES -> the boxed delta-set "
                 f"is exact; the d72 gap was coincidence")
        elif kind == 'predict_pass':
            v = ('CONFIRMED (pass)' if c40(tag) >= 0.5 else
                 'CONTRADICTED (fail)')
        elif kind == 'predict_fail':
            v = ('CONFIRMED (fail)' if c40(tag) < 0.5 else
                 'CONTRADICTED (pass)')
        elif kind == 'gap_boundary':
            v = (f"GAP BOUNDARY: d72={pred['d72']:g} (inside the measured "
                 f"gap (9, 14.4)) PASSES -> the boundary lies above "
                 f"{pred['d72']:g}; the gap extends to >= {pred['d72']:g}"
                 if c40(tag) >= 0.5 else
                 f"GAP BOUNDARY: d72={pred['d72']:g} (inside the measured "
                 f"gap (9, 14.4)) FAILS -> the boundary lies at or below "
                 f"{pred['d72']:g}; the gap narrows toward the measured "
                 f"14.4-fail")
        elif kind == 'encoding_pass':
            v = (f"CONFIRMED (pass; the 60 deg r != c+2 encoding holds "
                 f"at {pred['w_turns']:.2f} turns, r={pred['r']})"
                 if c40(tag) >= 0.5 else
                 f"CONTRADICTED (fail; the encoding's r={pred['r']} "
                 f"class dies at {pred['w_turns']:.2f} turns)")
        elif kind == 'null_branch':
            v = (f"NULL-BRANCH EMERGENCE (pass; the 2-turn null is a "
                 f"live antinode between the d=180 and d=120 heights)"
                 if c40(tag) >= 0.5 else
                 f"NULL-BRANCH NULL (no emergence; the exact 2-turn "
                 f"null stays dead)")
        elif kind == 'flip_control':
            v = (f"BORN-CLASS FLIP CONFIRMED (pass; the 60/16 death is "
                 f"born-full-class-specific; born-flat retains at the "
                 f"death height)"
                 if c40(tag) >= 0.5 else
                 f"FLIP REFUTED (fail; 60/16 dies in both born classes)")
        elif kind == 'band_fail':
            v = (f"CONFIRMED (fail; the d72=18 band holds at this "
                 f"height/envelope)"
                 if c40(tag) < 0.5 else
                 f"CONTRADICTED (pass; the d72=18 band passes at this "
                 f"height/envelope)")
        elif kind == 'mstar_discriminator':
            mstar = pred.get('M*', '?')
            v = (f"M*-RULE WINS: passes at M* = {mstar} "
                 f"despite d72=18; the residue fail band does not govern "
                 f"at the critical height"
                 if c40(tag) >= 0.5 else
                 f"RESIDUE-RULE WINS: fails at d72=18 even at M* = "
                 f"{mstar}; the M* pass "
                 f"rule does not transfer to the 54 deg family")
        elif kind == 'transfer_probe':
            n_floor = rt['floor_ey'] + rt['floor_ei']
            if n_floor > 0.02 * T.N ** 3:
                v = 'INCONCLUSIVE (clamp-seeded; floors > 2% at the run gauge)'
            else:
                v = (f"CONFIRMED (fail per the residue rule; d72=24 "
                     f"fails at 30 deg too)"
                     if c40(tag) < 0.5 else
                     f"ANOMALY TRANSFERS (pass; d72=24 retains below "
                     f"M* in the 30 deg family)")
        elif kind == 'encoding_fail':
            v = (f"CONFIRMED (fail; the r = c+2 encoding holds at "
                 f"{pred['w_turns']:.2f} turns)"
                 if c40(tag) < 0.5 else
                 f"CONTRADICTED (pass; r=5 retains at 3 cycles)")
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
    parser.add_argument('--wave7', action='store_true',
                        help='run the r1-r11 residue-rule falsifier wave '
                             'instead of g1-g12 (section 3.18)')
    parser.add_argument('--wave8', action='store_true',
                        help='run the r12-r21 M*-vs-residue wave instead '
                             'of g1-g12 (section 3.19)')
    parser.add_argument('--wave9', action='store_true',
                        help='run the W9 height-selection wave (a1-a3, '
                             'b1-b3, d1-d3, e1-e4, f1-f4, g1-g4, h1-h2; '
                             'section 3.20) with the W9-i full-profile '
                             'record')
    parser.add_argument('--far', action='store_true',
                        help='with --wave8: include the optional far arm '
                             'r21 (run only when the r12-r20 batch '
                             'finishes cleanly)')
    parser.add_argument('--from-runs', default=None, metavar='DIR')
    parser.add_argument('--rid-suffix', default=None, metavar='SUFFIX')
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
        if args.wave9:
            arms = WAVE9_ARMS
        elif args.wave8:
            arms = WAVE8_ARMS
        elif args.wave7:
            arms = WAVE7_ARMS
        else:
            arms = ARMS + (FINE_ARMS if any(r['tag'].startswith('g1') and
                                            r['tag'] in ('g13',)
                                            for r in runs)
                           else ARMS)
        arms = prepare(arms)
        print(f"Rebuilding from {len(runs)} preserved arms in {args.from_runs}")
        finalize(runs, args.from_runs, arms,
                 wave='w9' if args.wave9 else ('w8' if args.wave8
                                               else ('r' if args.wave7
                                                     else 'g')))
        return

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if args.wave9:
        arms = WAVE9_ARMS
    elif args.tend is not None:
        arms = ARMS
        args.steps = int(round(args.tend / T.DT))
    elif args.wave8:
        arms = WAVE8_ARMS
        if not args.far:
            arms = [a for a in arms if a[0] != 'r21']
    elif args.wave7:
        arms = WAVE7_ARMS
    else:
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
    suffix = args.rid_suffix or ('lattice_stack_w9' if args.wave9
                                 else 'lattice_stack_w8' if args.wave8
                                 else 'lattice_stack_r' if args.wave7
                                 else 'lattice_stack_g')
    rdir = f"runs/{rid}_{suffix}"
    os.makedirs(rdir, exist_ok=True)

    runs = []
    for tag, dth, M, rung, rot, pred in arms:
        phases = arm_phases((tag, dth, M, rung, rot, pred))
        if args.arm is not None and tag not in args.arm:
            continue
        steps = int(round(pred.get('t_end', 40.0) / T.DT)) \
            if args.wave9 else args.steps
        if args.wave9:
            runs.append(run_arm_w9(device, tag, phases, rung, rdir, steps))
        else:
            runs.append(run_arm(device, tag, phases, rung, rdir, steps))
    finalize(runs, rdir, arms,
             wave='w9' if args.wave9 else ('w8' if args.wave8
                                           else ('r' if args.wave7 else 'g')))


if __name__ == "__main__":
    main()
