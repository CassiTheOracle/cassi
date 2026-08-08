#!/usr/bin/env python3
"""Helix-construction detuning probe (two-strand lattice-stack program).

Run:  python two-fluid/run_helix_detune_probe.py
      (--steps N, --arm TAG repeatable, --init-check, --from-runs DIR)

The flat stack construction places every layer's two-hump pair at a fixed
azimuth (translated along z, per-layer phase theta_i = i*dtheta applied to
the (rho, eps) doublet).  The helix construction rotates the pair's
azimuth with z instead: layer n's pair sits at azimuth n*dtheta around the
cylinder axis, with the same per-layer phase.  r0 = SEP/2 = 6 cells is the
flat construction's own hump radius (the flat pair straddles the axis with
its humps at radius SEP/2), so the helix keeps the exact flat radii:
strand A at radius r0, azimuth n*dtheta; strand B at radius r0, azimuth
n*dtheta + pi.  No new free parameters -- at dtheta = 0 the construction
reduces bit-exactly to the flat stack (the h0 equivalence control).

Observables.  The z,y-integrated density of a rotating pair is azimuthally
uniform ("powder" projection): the transverse two-hump contrast C_abs of
the flat metric is expected degenerate (~0) for rotating helices and is
reported as the degeneracy check.  The construction-invariant observables
are (1) the axial slab-phasor envelope A(z) -- the array-factor law
A_tot = s_tot |sin(M dtheta/2)/sin(dtheta/2)| is rotation-invariant and is
verified at t = 0; (2) the per-layer radial pair analysis -- for each
layer window, the windowed density projected onto the layer's radial line
and onto the azimuthal circle at radius r0: per-layer separation d_n,
radial contrast C_abs,n, and azimuthal pair separation; (3) winding and
axial phase current (existing machinery).

Arms (fresh solver per arm, N = 48, gate 'five', t = 40 = 2/lambda):
  h0: dtheta = 0, M = 8   construction validation: bit-exact vs the flat
                           M = 8 dtheta = 0 stack; must reproduce the flat
                           M = 8 passing-arm envelope (b2_0 record:
                           C_abs 0.925/0.847 at t = 4/40 ~ the committed
                           0.848 passing value)
  h1: P = 10 (dtheta = 36 deg), M = 21   two-turn-plus 10-pitch helix;
                           A(21, 36 deg) = |sin 378 / sin 18| = 1.000
  h2: P = 10.5 (dtheta = 34.29 deg), M = 21   the DNA arm: exact two-turn
                           closure of the 10.5 pitch (21 * 34.2857 deg =
                           720 deg) -> A_tot(0) = 0 exact null
  h3: P = 10.5, M = 36   the law's would-be M* height at the DNA pitch
                           (M*(34.29 deg) = ceil(35.28) = 36; M0 = 10.5
                           non-integer -> the 3.12 exclusion predicts the
                           non-integer family has no passing height >= 8);
                           A(36, 34.29 deg) = 3.307
  h4: P = 10, M = 32   helix version of the passing flat arm (d1/a32,
                           A = 1.902): geometry-equivalence at the passer
                           height

Labels h0-h4 are probe labels, not master prediction numbers.  Output:
runs/<rid>_helix_detune/run_<arm>.json + results.json (raw; NO doc
changes, NO commit until the director reads the raw outputs).
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_trauma_wake_lock as T
import run_two_strand_probe as P
import run_lattice_stack_probe as L1
import run_lattice_stack2_probe as L2

torch.backends.cudnn.benchmark = True

T.LAM = 0.05
T.DT = 0.001
T.REPORT = 50
STEPS = 40000                 # t = 40 = 2/lambda (lock timescale)

SIG, SEP, E_RIDGE, BETA, RHO0 = L1.SIG, L1.SEP, L1.E_RIDGE, L1.BETA, L1.RHO0

# Helix geometry constants (no free parameters):
# r0 = SEP/2: the flat construction's hump radius -- the flat pair
# straddles the axis with both humps at radius SEP/2, so the helix keeps
# each strand at that radius and only rotates the azimuth.
R0 = SEP / 2.0

DTH_36 = 2.0 * np.pi / 10.0        # P = 10 pitch (36 deg)
DTH_DNA = 2.0 * np.pi / 10.5       # P = 10.5 pitch (34.2857 deg)


def helix_init(solver, M, dtheta, r0=R0, clamp=True):
    """M two-lobe layers along z; layer n's pair rotated to azimuth
    n*dtheta about the z axis (strand A at radius r0, azimuth n*dtheta;
    strand B at radius r0, azimuth n*dtheta + pi), with the same per-layer
    phase theta_n = n*dtheta in the (rho, eps) doublet as the flat stack.

    dtheta = 0 reduces bit-exactly to L2.stack_init_phases with all-zero
    phases (strand A at azimuth 0 = the flat +SEP/2 hump, strand B at
    azimuth pi = the flat -SEP/2 hump; same radii, same arithmetic).
    `clamp=False` returns the unclamped construction (protocol-diagnostic:
    the pre-clamp field verifies the array-factor anchors at the
    construction level; the clamped field is the evolution state).
    Returns (ey_hat, ei_hat, u_hat, zs).
    """
    N_ = solver.N
    dev = solver.device
    M = int(M)
    x = torch.arange(N_, dtype=torch.float64, device=dev)
    X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
    cx = N_ / 2.0
    spacing = N_ / M
    zs = [cx + (j - (M - 1) / 2.0) * spacing for j in range(M)]
    rho = torch.full((N_, N_, N_), RHO0, dtype=torch.float64, device=dev)
    eps = torch.zeros_like(rho)
    offsets = (0.0, float(N_), -float(N_))
    for j, zi in enumerate(zs):
        th = j * dtheta
        ct, st = math.cos(th), math.sin(th)
        # Strand convention must match the flat construction at dtheta = 0:
        # flat gm = g1 - g2 with g1 at azimuth pi (x = cx - SEP/2) and g2 at
        # azimuth 0 (x = cx + SEP/2), so g1 is the pi-side hump and g2 the
        # 0-side hump.  The helix keeps that: g1 = strand B at azimuth
        # th + pi, g2 = strand A at azimuth th, both at radius r0.
        a1, b1 = cx - r0 * ct, cx - r0 * st      # strand B (azimuth th + pi)
        a2, b2 = cx + r0 * ct, cx + r0 * st      # strand A (azimuth th)
        g1 = torch.zeros_like(X)
        g2 = torch.zeros_like(X)
        for off in offsets:
            zc = Z - zi + off
            g1 = g1 + torch.exp(-((X - a1) ** 2 + (Y - b1) ** 2 + zc ** 2)
                                / (2.0 * SIG ** 2))
            g2 = g2 + torch.exp(-((X - a2) ** 2 + (Y - b2) ** 2 + zc ** 2)
                                / (2.0 * SIG ** 2))
        gp = g1 + g2
        gm = g1 - g2
        rho += RHO0 * BETA * gp * ct - E_RIDGE * gm * st
        eps += RHO0 * BETA * gp * st + E_RIDGE * gm * ct
    ey = (T.PHI * rho + eps) / (1.0 + T.PHI)
    ei = (rho - eps) / (1.0 + T.PHI)
    if clamp:
        ey = torch.clamp(ey, min=1e-3)
        ei = torch.clamp(ei, min=1e-3)
    u_hat = torch.zeros(3, N_, N_, N_, dtype=torch.complex128, device=dev)
    return torch.fft.fftn(ey), torch.fft.fftn(ei), u_hat, zs


def _bilinear(grid, x, y, N_):
    """Bilinear sample of a periodic [N,N] grid at fractional (x, y)."""
    x = math.fmod(x, N_)
    y = math.fmod(y, N_)
    if x < 0:
        x += N_
    if y < 0:
        y += N_
    x0 = int(math.floor(x))
    y0 = int(math.floor(y))
    fx, fy = x - x0, y - y0
    x1, y1 = (x0 + 1) % N_, (y0 + 1) % N_
    return ((1.0 - fx) * ((1.0 - fy) * grid[x0, y0] + fy * grid[x0, y1]) +
            fx * ((1.0 - fy) * grid[x1, y0] + fy * grid[x1, y1]))


def radial_pair_analysis(solver, ey, ei, windows, zs, dtheta, r0=R0,
                         step=0.5, smax=15.0, nang=90):
    """Per-layer radial/azimuthal pair structure of a helix state.

    For each layer n (raised-cosine window), the windowed density
    rho_n(x, y) is projected (a) onto the layer's radial line (azimuth
    n*dtheta through the axis): ridge tracking gives the per-layer
    separation d_n and two-hump contrast C_abs,n; (b) onto the azimuthal
    circle at radius r0: the two strongest peaks give the azimuthal pair
    separation.  Returns per-layer lists + circular means."""
    N_ = solver.N
    cx = N_ / 2.0
    rho = ey + ei
    M = len(zs)
    s_axis = np.arange(-smax, smax + 1e-9, step)
    i_neg = int(round((-r0 + smax) / step))
    i_pos = int(round((r0 + smax) / step))
    layers = []
    for n in range(M):
        w = windows[n]
        rho_w = (rho * w[None, None, :]).sum(dim=2).cpu().numpy()
        alpha = n * dtheta
        ca, sa = math.cos(alpha), math.sin(alpha)
        prof = np.array([_bilinear(rho_w, cx + s * ca, cx + s * sa, N_)
                         for s in s_axis])
        bg = 0.5 * (prof[0] + prof[-1])       # local floor at the line ends
        dprof = prof - bg
        ad = np.abs(dprof)
        positions, merged = P.track_ridges(ad, [i_neg, i_pos], None)
        if merged or len(positions) < 2:
            layers.append({'d': 0.0, 'C_abs': 0.0, 'present': False,
                           'az_sep': 0.0, 'az_contrast': 0.0})
            continue
        s1, s2 = s_axis[int(round(positions[0]))], s_axis[int(round(positions[1]))]
        sm = 0.5 * (s1 + s2)
        ad_r = max(ad[int(round(positions[0]))], ad[int(round(positions[1]))])
        i_m = int(round((sm + smax) / step))
        i_m = min(max(i_m, 0), len(ad) - 1)
        c_abs = float((ad_r - ad[i_m]) / max(ad_r, 1e-30))
        # azimuthal pair separation at radius r0
        ang = np.array([_bilinear(rho_w, cx + r0 * math.cos(2.0 * np.pi * k
                        / nang), cx + r0 * math.sin(2.0 * np.pi * k / nang),
                        N_) for k in range(nang)])
        amin = ang.min()
        an = (ang - amin) / max(ang.max() - amin, 1e-30)
        pk = np.where((an[(np.arange(nang) + 1) % nang] <= an) &
                      (an[(np.arange(nang) - 1) % nang] <= an) &
                      (an > 0.15))[0]
        if len(pk) >= 2:
            order = np.argsort(an[pk])[::-1][:2]
            p1, p2 = pk[order]
            sep = abs(p1 - p2) / nang * 2.0 * np.pi
            sep = min(sep, 2.0 * np.pi - sep)
            layers.append({'d': float(abs(s2 - s1)), 'C_abs': c_abs,
                           'present': True, 'az_sep': float(sep),
                           'az_contrast': float((an[pk[order[0]]] -
                                                 an[pk[order[1]]]) /
                                                max(an[pk[order[0]]], 1e-30))})
        else:
            layers.append({'d': float(abs(s2 - s1)), 'C_abs': c_abs,
                           'present': True, 'az_sep': 0.0,
                           'az_contrast': 0.0})
    ds = np.array([l['d'] for l in layers])
    cs = np.array([l['C_abs'] for l in layers])
    azs = np.array([l['az_sep'] for l in layers])
    return {'per_layer': layers,
            'd_mean': float(ds.mean()), 'd_std': float(ds.std()),
            'C_abs_mean': float(cs.mean()),
            'present_frac': float(np.mean([l['present'] for l in layers])),
            'az_sep_mean': float(azs[azs > 0].mean()) if (azs > 0).any()
                           else 0.0}


def ring_m2(ey, ei, r0=R0, nang=90):
    """Spontaneous azimuthal m=2 amplitude of the z-integrated ring at
    radius r0: a2 = |sum_k rho_ring(phi_k) e^{i2 phi_k}| / sum rho_ring.
    Exactly 0 at t=0 for any uniform ring (h2's 42-point construction);
    growth marks the emergence branch of the helix null arms."""
    N_ = ey.shape[0]
    cx = N_ / 2.0
    rho = (ey + ei).sum(dim=2).cpu().numpy()     # z-integrated [N,N]
    ang = np.array([_bilinear(rho, cx + r0 * math.cos(2.0 * np.pi * k / nang),
                              cx + r0 * math.sin(2.0 * np.pi * k / nang), N_)
                    for k in range(nang)])
    tot = ang.sum()
    if tot < 1e-30:
        return {'m2': 0.0, 'm1': 0.0, 'uniformity': 0.0}
    k2 = np.arange(nang)
    m2 = abs(np.sum(ang * np.exp(2j * 2.0 * np.pi * k2 / nang))) / tot
    m1 = abs(np.sum(ang * np.exp(1j * 2.0 * np.pi * k2 / nang))) / tot
    return {'m2': float(m2), 'm1': float(m1), 'uniformity':
            float((ang.max() - ang.min()) / max(ang.max(), 1e-30))}


def measure_helix(solver, ey, ei, rho_prof, centers, prev, windows, zs,
                  rho_bg, dtheta, radial):
    """L1.measure plus the per-layer radial/azimuthal pair analysis and
    the ring m=2 amplitude (computed at the checkpoint times only,
    `radial` = bool)."""
    d = L1.measure(solver, ey, ei, rho_prof, centers, prev, windows, zs,
                   rho_bg)
    if radial:
        d['radial'] = radial_pair_analysis(solver, ey, ei, windows, zs,
                                           dtheta)
        d['ring_m2'] = ring_m2(ey, ei)
    return d


def resonance_t0(solver, ey, ei, windows, zs, phases):
    """t=0 verification of the array-factor law from the initialized
    fields (slab phasor: the x,y integral of a pair is rotation-
    invariant, so the law carries over from the flat construction)."""
    S = L1.slab_phasor(ey, ei, RHO0)
    A_tot = float(S.sum().abs())
    s_tot = 2.0 * RHO0 * BETA * (2.0 * np.pi) ** 1.5 * SIG ** 3
    W = (windows.to(torch.complex128) @ S).cpu().numpy()
    ph = np.angle(W)
    adv = []
    for i in range(len(zs) - 1):
        dv = (ph[i + 1] - ph[i]) % (2.0 * np.pi)
        if dv > np.pi:
            dv -= 2.0 * np.pi
        adv.append(dv)
    return {
        'A_tot': A_tot,
        's_tot_analytic': s_tot,
        'ratio_vs_analytic': A_tot / max(s_tot, 1e-30),
        'layer_phase': ph.tolist(),
        'layer_amp': np.abs(W).tolist(),
        'phase_advance': adv,
        'max_advance_dev': max((abs(a - (phases[i + 1] - phases[i])
                                     if i < len(phases) - 1 else 0.0)
                                for i, a in enumerate(adv)), default=0.0),
        'floor_ey': int((ey <= 1e-3 + 1e-12).sum()),
        'floor_ei': int((ei <= 1e-3 + 1e-12).sum()),
        'min_ey': float(ey.min()),
        'min_ei': float(ei.min()),
    }


def array_factor(M, dth):
    if abs(dth) < 1e-12:
        return float(M)
    return abs(math.sin(M * dth / 2.0) / math.sin(dth / 2.0))


ARMS = [
    ('h0', 8, 0.0,
     {'kind': 'equivalence',
      'A_pred': 8.0, 'C_abs0_pred': None,
      'C_abs40_range': (0.80, 0.90),
      'note': 'dtheta = 0, M = 8: construction validation -- init must be '
              'bit-exact vs the flat M = 8 dtheta = 0 stack; envelope must '
              'reproduce the flat M = 8 passing record (b2_0: C_abs '
              '+0.925/+0.847 at t = 4/40, the committed 0.848-class '
              'passing value)'}),
    ('h1', 21, DTH_36,
     {'kind': 'envelope', 'R': array_factor(21, DTH_36),
      'A_pred': 1.0,
      'C_abs0_pred': '~0 (azimuth counts 3 at 0 deg, 2 elsewhere; '
                     'x-projection inner pair at +-0.309r = +-1.85 cells, '
                     '3.7 cells apart, fails the >= 6-cell present guard)',
      'C_abs40_range': (0.05, 0.30),
      'winding_con': 2.0,
      'note': 'P = 10 helix, M = 21: A(21, 36 deg) = |sin 378 / sin 18| '
              '= 1.000 [D]; two-turn-plus 10-pitch helix; weak/flat '
              'emergence expected (escape or retention, no contraction)'}),
    ('h2', 21, DTH_DNA,
     {'kind': 'null', 'R': array_factor(21, DTH_DNA),
      'A_pred': 0.0,
      'C_abs0_pred': '0.00 (exact two-turn closure: 21 * (360/10.5) deg = '
                     '720 deg; 21 distinct azimuths at 17.1429 deg spacing '
                     '= 42-point uniform ring at 8.5714 deg)',
      'C_abs40_range': (0.30, 0.70),
      'winding_con': 20.0 * DTH_DNA / (2.0 * np.pi),
      'note': 'P = 10.5 helix, M = 21: the DNA arm -- exact two-turn '
              'closure of the 10.5 pitch, A_tot(0) = 0 exact null in '
              'every linear coherent sum [D]; THE emergence arm (the '
              'exact-closure null analog of f4/f6): C_abs(40) 0.30-0.70 '
              'with f4-like per-slab d contraction ~10 -> 2.5-3.5 cells '
              'at t=40, no merge, ring m2 growth >= 0.3, closure defect '
              'psi_20 - psi_0 - 20*dtheta = 0 mod 2pi held'}),
    ('h3', 36, DTH_DNA,
     {'kind': 'exclusion', 'R': array_factor(36, DTH_DNA),
      'A_pred': math.sin(3.0 * np.pi / 7.0) / math.sin(2.0 * np.pi / 21.0),
      'C_abs0_pred': '0-0.07 (15x2 + 6x1 azimuth structure)',
      'C_abs40_range': (None, 0.10),
      'winding_con': 35.0 * DTH_DNA / (2.0 * np.pi),
      'note': 'P = 10.5, M = 36: the law\'s would-be M* height at the DNA '
              'pitch (M*(34.29 deg) = ceil(35.28) = 36); M0 = 10.5 '
              'non-integer -> 3.12 exclusion predicts no passing height '
              '>= 8; A = sin(3pi/7)/sin(2pi/21) = 3.30759 [D]; far-off-'
              'closure delta = 154.29 deg, the 54 deg M=16 dissolution '
              'analog: C_abs(40) <= 0.10 or negative'}),
    ('h4', 32, DTH_36,
     {'kind': 'envelope', 'R': array_factor(32, DTH_36),
      'A_pred': 2.0 * math.cos(np.pi / 10.0),
      'C_abs0_pred': '0-0.07 (azimuth counts 4 at {0, 36 deg}, 3 '
                     'elsewhere; m=2 azimuthal excess 0.0506)',
      'C_abs40_range': (0.05, 0.30),
      'winding_con': 31.0 * DTH_36 / (2.0 * np.pi),
      'note': 'P = 10 helix, M = 32: helix version of the passing flat '
              'arm (d1/a32 geometry, A = 1.90211 [D]); the degenerate '
              'twin of d1 -- it CANNOT reproduce d1\'s 0.848 because the '
              'two-hump structure is absent at t=0; that absence is the '
              'geometry-degeneracy control; C_abs(40) 0.05-0.30'}),
]


def run_case(solver, M, dtheta, tag, outdir, steps=STEPS):
    print(f"\n=== run: {tag} (M={M}, dtheta={dtheta:.5f} rad = "
          f"{math.degrees(dtheta):.3f} deg, R={array_factor(M, dtheta):.4f}, "
          f"t={steps * T.DT}) ===")
    phases = [i * dtheta for i in range(M)]
    ey_hat, ei_hat, u_hat, zs = helix_init(solver, M, dtheta)
    centers = [solver.N / 2.0 - SEP / 2.0, solver.N / 2.0 + SEP / 2.0]
    windows = L1.layer_windows(solver.N, zs, solver.device)
    ey0 = torch.fft.ifftn(ey_hat).real
    ei0 = torch.fft.ifftn(ei_hat).real
    res0 = resonance_t0(solver, ey0, ei0, windows, zs, phases)
    print(f"  t=0: A_tot={res0['A_tot']:.4f} "
          f"(s_tot={res0['s_tot_analytic']:.2f}, "
          f"ratio={res0['ratio_vs_analytic']:.5f}, "
          f"R={array_factor(M, dtheta):.4f}) | "
          f"min fields {res0['min_ey']:.4f}/{res0['min_ei']:.4f} | "
          f"floor cells {res0['floor_ey']}/{res0['floor_ei']}")

    t0 = time.time()
    hist = []
    prev = None
    profiles = {}
    radial = {}
    S0 = L1.slab_phasor(ey0, ei0, RHO0).cpu().numpy()
    J0, F0, _, _ = L1.current_profiles(solver, ey0, ei0, zs)
    profiles['0.0'] = {'A': np.abs(S0).tolist(), 'arg': np.angle(S0).tolist(),
                       'Jz': J0.tolist(), 'Fc': F0.tolist()}
    radial['0.0'] = radial_pair_analysis(solver, ey0, ei0, windows, zs,
                                         dtheta)
    for step in range(steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step % T.REPORT == 0 or step == steps - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            rho_prof = (ey + ei).sum(dim=(1, 2)).cpu().numpy()
            rho_bg = RHO0 if step == 0 else float((ey + ei).mean())
            at_check = (step == 0 or abs(step * T.DT - 4.0) < 0.6 or
                        abs(step * T.DT - 40.0) < 0.6 or step == steps - 1)
            d = measure_helix(solver, ey, ei, rho_prof, centers, prev,
                              windows, zs, rho_bg, dtheta, at_check)
            prev = ([d['x1'], d['x2']] if not d['merged'] else [d['x1']])
            d.update({'step': step, 't': step * T.DT})
            hist.append(d)
            if at_check:
                rho_m = float((ey + ei).mean())
                Sn = L1.slab_phasor(ey, ei, rho_m).cpu().numpy()
                Jn, Fn, _, _ = L1.current_profiles(solver, ey, ei, zs)
                profiles[f"{step * T.DT:.1f}"] = {
                    'A': np.abs(Sn).tolist(), 'arg': np.angle(Sn).tolist(),
                    'Jz': Jn.tolist(), 'Fc': Fn.tolist()}
                radial[f"{step * T.DT:.1f}"] = d['radial']
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
            json.dump({'kind': tag, 'M': M, 'dtheta': dtheta, 'r0': R0,
                       'phases': phases, 'zs': zs, 'steps': steps,
                       'R': array_factor(M, dtheta),
                       'resonance_t0': res0, 'profiles': profiles,
                       'radial': radial, 'hist': hist}, f, indent=1)
    return {'tag': tag, 'M': M, 'dtheta': dtheta, 'elapsed': elapsed,
            'resonance_t0': res0, 'hist': hist, 'profiles': profiles,
            'radial': radial}


def at_t(hist, t_target):
    return min(hist, key=lambda d: abs(d['t'] - t_target))


def summarize_arm(r):
    h = r['hist']
    t0, t4, t40 = h[0], at_t(h, 4.0), at_t(h, 40.0)
    rad4 = r['radial'].get('4.0') or r['radial'].get('4.05')
    rad40 = r['radial'].get('40.0')
    if rad4 is None:
        for tgt in ('4.0', '4.05', '3.95'):
            if tgt in r['radial']:
                rad4 = r['radial'][tgt]
                break
    return {
        't0': {'A_peak': t0['A_peak'], 'C_abs': t0['C_abs'],
               'winding': t0['winding'], 'd': t0['d'],
               'radial': r['radial']['0.0'], 'ring_m2': t0['ring_m2']},
        't4': {'d': t4['d'], 'C_abs': t4['C_abs'], 'A_peak': t4['A_peak'],
               'winding': t4['winding'], 'delta_theta': t4['delta_theta'],
               'q_mid': t4['q_mid'], 'radial': rad4,
               'ring_m2': t4.get('ring_m2')},
        't40': {'d': t40['d'], 'C_abs': t40['C_abs'], 'A_peak': t40['A_peak'],
                'winding': t40['winding'], 'delta_theta': t40['delta_theta'],
                'A_plus': t40['A_plus'], 'q_mid': t40['q_mid'],
                'merged': t40['merged'], 'radial': rad40,
                'ring_m2': t40.get('ring_m2')},
        'A_peak_ratio_t4': t4['A_peak'] / max(t0['A_peak'], 1e-30),
        'A_peak_ratio_t40': t40['A_peak'] / max(t0['A_peak'], 1e-30),
        'mass_drift': abs(t40['mass'] - t0['mass']) / max(t0['mass'], 1e-30),
        'ey_min': min(d['ey_min'] for d in h),
        'ei_min': min(d['ei_min'] for d in h),
        'nan': any(np.isnan(d['A_peak']) for d in h),
    }


def phase_rms(rec, dtheta, M):
    """RMS of (measured per-layer phase - commanded n*dtheta), wrapped to
    [-pi, pi), in units of dtheta.  None when the record has no phases."""
    lp = rec.get('layer_phase')
    if lp is None or dtheta == 0.0:
        return None
    devs = []
    for n, ph in enumerate(lp):
        dv = (ph - n * dtheta) % (2.0 * np.pi)
        if dv > np.pi:
            dv -= 2.0 * np.pi
        devs.append(dv)
    devs = np.array(devs)
    return float(np.sqrt((devs ** 2).mean()) / abs(dtheta))


def construction_A_tot(device, M, dtheta):
    """Unclamped helix-construction A_tot (pre-clamp): the [D] array-factor
    anchors are verified at the construction level; the clamped-field
    residue is clamp truncation (B5/f7 mechanism) scaling with the init
    floor fraction (4.4-9.8% on the dense helix arms)."""
    solver = T.build_solver(device)
    ey_u, ei_u, _, _ = helix_init(solver, M, dtheta, clamp=False)
    return float(L1.slab_phasor(torch.fft.ifftn(ey_u).real,
                                torch.fft.ifftn(ei_u).real, RHO0).sum().abs())


def finalize(runs, rdir, device=None):
    for r in runs:
        if 'summary' not in r:
            r['summary'] = summarize_arm(r)
    s_tot = float(2.0 * RHO0 * BETA * (2.0 * np.pi) ** 1.5 * SIG ** 3)

    def arm(tag):
        return next((r for r in runs if r['tag'] == tag), None)

    results = {
        'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT,
                 't_end': runs[0]['hist'][-1]['t'],
                 'gate_model': 'five (solver)',
                 'wave': 'helix-construction detuning probe (h0-h4)',
                 'construction': 'helix: layer n pair at azimuth '
                                 'n*dtheta, strand radius r0 = SEP/2 = 6 '
                                 '(flat construction hump radius), '
                                 'per-layer phase n*dtheta',
                 'protocol': 'fresh solver per arm, t=40=2/lambda, '
                             'init-only, canonical solver untouched'},
        'arms': {},
    }
    for r in runs:
        results['arms'][r['tag']] = {
            'M': r['M'], 'dtheta': r['dtheta'],
            'R_pred': array_factor(r['M'], r['dtheta']),
            'resonance_t0': r['resonance_t0'], 'summary': r['summary'],
            'elapsed_s': r['elapsed'],
            'Jz_abs_mean_0': r['hist'][0]['Jz_abs_mean'],
            'Fc_mean_0': r['hist'][0]['Fc_mean']}

    print(f"\n=== HELIX-DETUNE PROBE RESULTS (t=40) ===")
    print(f"Array-factor law at t=0 (s_tot = {s_tot:.2f}, "
          f"rotation-invariant slab phasor):")
    for tag in results['arms']:
        a = results['arms'][tag]
        r0r = a['resonance_t0']
        R = a['R_pred']
        if R > 1e-9:
            ratio = r0r['A_tot'] / (s_tot * R)
            ok = 0.95 <= ratio <= 1.05
            print(f"  {tag}: A_tot={r0r['A_tot']:9.2f} vs s_tot*R="
                  f"{s_tot * R:9.2f}  ratio={ratio:.4f}  "
                  f"{'PASS' if ok else 'FAIL'}")
        else:
            ok = r0r['A_tot'] < 1e-6 * s_tot
            print(f"  {tag}: R=0 (exact null): A_tot={r0r['A_tot']:.4e} "
                  f"(s_tot={s_tot:.2f})  "
                  f"{'PASS' if ok else 'FAIL'}")

    verdicts = {}
    for tag, M, dtheta, pred in ARMS:
        r = arm(tag)
        if r is None:
            print(f"  {tag}: not in this run set")
            continue
        s = r['summary']
        rt = r['resonance_t0']
        ra40 = s['t40']['radial']
        kind = pred['kind']
        # phase-latch diagnostics: rms vs commanded n*dtheta, winding
        # retention vs constructed winding
        wcon = pred.get('winding_con')
        pr0 = phase_rms(r['hist'][0], dtheta, M)
        pr4 = phase_rms(at_t(r['hist'], 4.0), dtheta, M)
        pr40 = phase_rms(at_t(r['hist'], 40.0), dtheta, M)
        wret = None
        if wcon:
            wret = s['t40']['winding'] / max(wcon, 1e-30)
        wcon_s = f"(constructed {wcon:.4f}, retention {wret:.2f})" \
            if wcon else "(no constructed-winding anchor)"
        print(f"\n  {tag} (M={M}, dtheta={math.degrees(dtheta):.3f} deg, "
              f"R={pred.get('R', 0.0):.4f}):")
        print(f"    C_abs (x-projection) 0/4/40 = {s['t0']['C_abs']:+.3f}/"
              f"{s['t4']['C_abs']:+.3f}/{s['t40']['C_abs']:+.3f}  "
              f"(degeneracy check) | A_peak 0/4/40 = {s['t0']['A_peak']:.2f}/"
              f"{s['t4']['A_peak']:.2f}/{s['t40']['A_peak']:.2f} "
              f"ratio40={s['A_peak_ratio_t40']:.3f} | "
              f"wind(40)={s['t40']['winding']:+.3f} {wcon_s} | "
              f"d(40)={s['t40']['d']:.2f} merged={s['t40']['merged']}")
        for tt, rk in (('0', s['t0']['radial']), ('4', s['t4']['radial']),
                       ('40', s['t40']['radial'])):
            if rk is None:
                print(f"      radial t={tt}: (missing)")
                continue
            print(f"      radial t={tt}: d_n mean={rk['d_mean']:.2f} "
                  f"(std {rk['d_std']:.2f}) C_abs_n mean={rk['C_abs_mean']:+.3f} "
                  f"present={rk['present_frac']:.2f} "
                  f"az_sep={rk['az_sep_mean']:.3f} rad")
        print(f"      ring m2: t=0 {s['t0']['ring_m2']['m2']:.4f} | "
              f"t=4 {s['t4']['ring_m2']['m2'] if s['t4']['ring_m2'] else float('nan'):.4f} | "
              f"t=40 {s['t40']['ring_m2']['m2'] if s['t40']['ring_m2'] else float('nan'):.4f} "
              f"| phase rms (units of dtheta): t=0 {pr0 if pr0 is None else f'{pr0:.4f}'} "
              f"t=4 {pr4 if pr4 is None else f'{pr4:.4f}'} "
              f"t=40 {pr40 if pr40 is None else f'{pr40:.4f}'}")
        v = None
        if kind == 'equivalence':
            # Construction equivalence: bit-exact reduction to the flat
            # zero-phase stack (verified in --init-check: max|dE| = 0 on
            # both fields) and the [D] A anchor.  The envelope is its own
            # record: the zero-phase stack's C_abs(4/40) = +0.647/+0.510
            # with A_peak retention 0.076 and zero winding -- churning,
            # not the 72-deg passer's 0.961/0.848 (the passing retention
            # requires the phase ramp, which the aligned stack lacks).
            c4, c40 = s['t4']['C_abs'], s['t40']['C_abs']
            v = f"CONSTRUCTION EQUIVALENT (bit-exact init vs flat " \
                f"zero-phase stack; A anchor {rt['A_tot'] / s_tot:.5f} vs " \
                f"8.0); envelope = the new flat zero-phase record " \
                f"(C_abs {c4:+.3f}/{c40:+.3f} at 4/40, A_peak ret40 " \
                f"{s['A_peak_ratio_t40']:.3f}, wind(40) " \
                f"{s['t40']['winding']:+.3f}) -- churning, not the " \
                f"72-deg passer (0.961/0.848); passing requires the " \
                f"phase ramp"
        elif kind in ('envelope', 'exclusion', 'null'):
            # [D] t=0 anchors: verified at the construction level
            # (pre-clamp); the clamped A_tot carries the truncation residue
            ap = pred['A_pred']
            A_u = construction_A_tot(device if device is not None
                                     else torch.device('cpu'), M, dtheta)
            a_ok = abs(A_u - ap * s_tot) < 0.03 * s_tot
            v = f"[D] A_tot(unclamped)={A_u:.2f} vs anchor " \
                f"{ap:.5f}*s_tot ({'PASS' if a_ok else 'FAIL'}); clamped " \
                f"{rt['A_tot']:.2f} = clamp truncation of " \
                f"{rt['floor_ey'] + rt['floor_ei']} floored cells"
            # [H] t=40 emergence band on the x-projection C_abs
            lo, hi = pred['C_abs40_range']
            c40 = s['t40']['C_abs']
            in_band = ((lo is None or c40 >= lo) and
                       (hi is None or c40 <= hi))
            band = f"[{lo if lo is not None else '-inf'}, " \
                   f"{hi if hi is not None else '+inf'}]"
            v += f" | [H] C_abs(40)={c40:+.3f} vs band {band} " \
                 f"({'PASS' if in_band else 'OUT'})"
            if kind == 'null':
                if A_u < 1e-6 * s_tot:
                    null_class = 'exact (float-level, like the flat nulls)'
                elif A_u < 0.01 * s_tot:
                    null_class = ('exact at the construction level; '
                                  'residue = rotated-footprint grid wobble '
                                  '(the flat nulls cancel to 1e-15 only '
                                  'because their footprints are identical)')
                else:
                    null_class = 'NOT NULL'
                v = f"CONFIRMED exact null: A_tot(unclamped)={A_u:.4e} = " \
                    f"{A_u / s_tot:.3e} s_tot -- {null_class}; clamped " \
                    f"{rt['A_tot']:.2f} = truncation residue" \
                    f" | [H] C_abs(40)={c40:+.3f} vs band {band} " \
                    f"({'PASS' if in_band else 'OUT'})"
        verdicts[tag] = {'prediction': pred, 'verdict': v,
                         'ring_m2_t0': s['t0']['ring_m2']['m2'],
                         'ring_m2_t40': s['t40']['ring_m2']['m2'],
                         'phase_rms_t40': pr40,
                         'winding_retention': wret}
        print(f"    prediction [{kind}]: {pred['note']}")
        print(f"    -> {v}")

    print(f"\nTelemetry:")
    for r in runs:
        s = r['summary']
        rt = r['resonance_t0']
        print(f"  {r['tag']}: mass drift {s['mass_drift']:.2e} | "
              f"init floors {rt['floor_ey'] + rt['floor_ei']:6d} | "
              f"run-min {s['ey_min']:.4f}/{s['ei_min']:.4f} | NaN "
              f"{s['nan']} | {r['elapsed']:.1f}s")

    results['verdicts'] = verdicts
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults: {rdir}/results.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--steps', type=int, default=STEPS)
    parser.add_argument('--arm', action='append', default=None)
    parser.add_argument('--init-check', action='store_true')
    parser.add_argument('--from-runs', default=None, metavar='DIR')
    args = parser.parse_args()

    if args.from_runs is not None:
        import glob as _glob
        runs = []
        for f in sorted(_glob.glob(f"{args.from_runs}/run_*.json")):
            d = json.load(open(f))
            runs.append({'tag': d['kind'], 'M': d['M'], 'dtheta': d['dtheta'],
                         'elapsed': 0.0, 'resonance_t0': d['resonance_t0'],
                         'hist': d['hist'], 'profiles': d['profiles'],
                         'radial': d['radial']})
        print(f"Rebuilding from {len(runs)} preserved arms in {args.from_runs}")
        finalize(runs, args.from_runs,
                 torch.device('cuda' if torch.cuda.is_available() else 'cpu'))
        return

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t={args.steps * T.DT}  "
          f"gate='five'  helix construction  r0={R0}")

    arms = ARMS
    if args.arm is not None:
        arms = [a for a in arms if a[0] in args.arm]
        if not arms:
            raise SystemExit(f"no matching arms in {[a[0] for a in arms]}")
    print(f"Arms: {', '.join(a[0] for a in arms)}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_helix_detune"
    os.makedirs(rdir, exist_ok=True)

    if args.init_check:
        # h0 construction validation: helix(dtheta=0) vs flat all-zero
        solver = T.build_solver(device)
        M0, dth0 = 8, 0.0
        ey_h, ei_h, _, zs_h = helix_init(solver, M0, dth0)
        phases0 = [0.0] * M0
        ey_f, ei_f, _, zs_f = L2.stack_init_phases(solver, phases0)
        dh = torch.fft.ifftn(ey_h).real - torch.fft.ifftn(ey_f).real
        di = torch.fft.ifftn(ei_h).real - torch.fft.ifftn(ei_f).real
        print(f"  h0 flat-equivalence: max |dEy| = {dh.abs().max():.3e} "
              f"max |dEi| = {di.abs().max():.3e} "
              f"(bit-exact if both 0)")
        for tag, M, dtheta, pred in arms:
            solver = T.build_solver(device)
            phases = [i * dtheta for i in range(M)]
            # construction-level [D] anchor verification (pre-clamp)
            ey_u, ei_u, _, zs_u = helix_init(solver, M, dtheta, clamp=False)
            Su = L1.slab_phasor(torch.fft.ifftn(ey_u).real,
                                torch.fft.ifftn(ei_u).real, RHO0)
            A_u = float(Su.sum().abs())
            s_tot_u = float(2.0 * RHO0 * BETA * (2.0 * np.pi) ** 1.5 * SIG ** 3)
            print(f"  {tag} [D] unclamped: A_tot={A_u:10.3f} = "
                  f"{A_u / s_tot_u:.5f} s_tot (anchor "
                  f"{pred.get('A_pred', float('nan')):.5f})")
            ey_hat, ei_hat, u_hat, zs = helix_init(solver, M, dtheta)
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            windows = L1.layer_windows(solver.N, zs, solver.device)
            rt = resonance_t0(solver, ey, ei, windows, zs, phases)
            ra = radial_pair_analysis(solver, ey, ei, windows, zs, dtheta)
            rm = ring_m2(ey, ei)
            print(f"  {tag}: A_tot={rt['A_tot']:10.3f} "
                  f"ratio={rt['ratio_vs_analytic']:.5f} "
                  f"(R={array_factor(M, dtheta):.4f}) "
                  f"min={rt['min_ey']:.4f}/{rt['min_ei']:.4f} "
                  f"floors={rt['floor_ey']}/{rt['floor_ei']} "
                  f"| C_abs(x)={L1.two_hump(ey, ei, RHO0 * solver.N ** 2)['C_abs']:+.3f} "
                  f"| radial d_n={ra['d_mean']:.2f} C_abs_n={ra['C_abs_mean']:+.3f} "
                  f"az_sep={ra['az_sep_mean']:.3f} | ring m2={rm['m2']:.4f}")
        print(f"(init check only; {len(arms)} arms)")
        return

    runs = []
    for tag, M, dtheta, pred in arms:
        solver = T.build_solver(device)     # fresh solver per arm
        r = run_case(solver, M, dtheta, tag, rdir, args.steps)
        runs.append(r)
    finalize(runs, rdir, device)


if __name__ == "__main__":
    main()
