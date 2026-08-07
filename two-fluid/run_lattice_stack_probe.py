#!/usr/bin/env python3
"""Lattice-stack coherence probe: M two-lobe layers, per-layer phase theta_i = i*dtheta.

Run:  python two-fluid/run_lattice_stack_probe.py
      (--steps N and --arm TAG repeatable override the matrix/runtime)

Tests the theory-director hypothesis that an emergent two-strand envelope
arises from coherence stacking across M lattice layers with per-layer phase
theta_i = i*dtheta -- initialization-only, zero new terms, canonical solver
untouched (the same constraint as the two-strand probes).

Stack geometry: M identical two-lobe layers (the committed two-strand init,
SIG = 5, SEP = 12, E_RIDGE = 0.65, BETA = 0.3) stacked along z with uniform
period s = N/M cells, layer i centered at z_i = N/2 + (i - (M-1)/2)*s.

Phase convention: the layer phase is a rotation of the layer's (rho, eps)
perturbation doublet about the phi-equilibrium background in the anti-phase
conversion plane (the plane in which the conversion dynamics act):
    drho_i = rho0*BETA*(g1+g2)*cos(theta_i) - E_RIDGE*(g1-g2)*sin(theta_i)
    deps_i = rho0*BETA*(g1+g2)*sin(theta_i) + E_RIDGE*(g1-g2)*cos(theta_i)
with rho0 = 1 + phi^-1, theta_i = i*dtheta.  M=1, dtheta=0 is the committed
two_lobe_init construction (rho = rho0(1+beta(g1+g2)), eps = E(g1-g2));
the rotation preserves representability under the positivity floor for every
arm in the matrix (min fields > 0.1 >> 1e-3).

Resonance law: because the antisymmetric lobe pair has zero transverse
integral, the transverse-integrated slab phasor of layer i is exactly
    S_i(z) = s(z - z_i) exp(i theta_i),   s(z) = rho0*BETA*2*(2 pi SIG^2) e^{-z^2/2SIG^2},
so the total coherent amplitude obeys the array-factor (diffraction) law
    |sum_i integral S_i dz| = s_tot |sin(M dtheta/2) / sin(dtheta/2)|,   s_tot = 2 rho0 BETA (2 pi)^{3/2} SIG^3.
The field's own slab phasor is measured as S(z) = sum_{x,y} [(rho - <rho>) + i eps],
so the law is verified at t = 0 directly from the initialized fields.

Arms (fresh solver per arm, t = 40 = 2/lambda lock timescale, N = 48,
gate 'five'; the t = 4 characterization records come from the same runs):
  m1_0     M=1, dtheta=0   single-layer baseline -- acceptance A1: must
                           reproduce the published record (t=4 persisted
                           d 9.90->10.08; t=40 escape d 9.90->15.73, TS1)
  m2_2pi5  M=2   pentagon step   R = phi   (|sin(2pi/5)|/sin(pi/5) = 1.618)
  m4_2pi5  M=4   pentagon step   R = 1
  m8_2pi5  M=8   pentagon step   R = phi
  m16_2pi5 M=16  pentagon step   R = 1     (full lattice, 3-cell period)
  m8_pi5   M=8   decagon step    R = 1.902 (odd-multiple interlace, sec 4.3)
  m8_pi2   M=8   quadrature      R = 0     (the excluded interlace, sec 4.3)
  m8_pi    M=8   anti-phase      R = 0     (alternating checkerboard stack)
The four dtheta values map onto the sec 4.3 interlace branches: 2 pi/5 is
the even multiple (coincident-pentagon 5-fold), pi/5 and pi are the odd
multiples (decagonal -- pi = 5 x 36 deg, so the anti-phase arm's vertex set
{2 pi i/5} u {2 pi i/5 + pi} is 10 points, a decagon, not coincident
pentagons), pi/2 is quadrature (excluded).

Measurements per report:
  axial coherence envelope A(z) = |S(z)| and its phase profile (helical/phase
  winding along the stack axis: unwrapped phase advance across the layer
  sequence / 2 pi),
  axial phase current J_z = ey*d_z ei - ei*d_z ey (the R^2 grad-theta phase
  current of the existing formalism, R^2 = ey^2 + ei^2; read-only, no
  feedback), slab profile Jz(z) = sum_{x,y} J_z, per-adjacent-layer-pair
  values at the pair midplane, and the axial coherence flux F_c = q*|J_z|
  (q from the solver's own 'five' gate), slab profile and per-pair values,
  per-layer windowed phasors (partition-of-unity raised-cosine projection),
  transverse two-hump structure on the z,y-integrated rho(x) profile: signed
  ridge-vs-midpoint contrast C_rho and the |drho| two-hump contrast C_abs,
  d(t) drift and per-strand doublet phases via the committed two-strand probe
  measurements (read-only reuse of run_two_strand_probe.measure_strands),
  q_mid/q_flank/q_glob, whole-field ey/ei floor minima, mass drift, H, a.
Secondary observable (director steering): whether the envelope's t=4
retention (A_peak ratio, two-hump C_abs) correlates across arms with the
t=0 mean |J_z| and with dtheta -- reported as cross-arm correlations (n = 8,
qualitative).  Qi-as-coherence-flow framing: per-layer step dtheta = k_z*dz
with k_z the axial phase gradient; k_z_eff = mean phase advance / spacing is
reported per arm at t = 0, 4, 40.

Acceptance:
  A1. m1_0 reproduces the published single-layer behavior (t=4 persisted,
      t=40 escape) as the one-string/single-layer limit.
  A2. the resonance law |sin(M dtheta/2)/sin(dtheta/2)| is verified at t=0
      from the initialized fields (A_tot vs s_tot*R; per-layer phase advance).
  A3. report whether a persistent two-hump envelope survives t=4 and t=40
      at any (M, dtheta).

Output (runs/ is gitignored -- commit the script only):
  runs/<rid>_lattice_stack/run_<arm>.json   full history per arm
  runs/<rid>_lattice_stack/results.json     meta + summaries + verdicts
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

# ── Protocol (coherence-budget regime, lock timescale) ───────────────────
T.LAM = 0.05
T.DT = 0.001
T.REPORT = 50
STEPS = 40000                # t = 40 = 2/lambda (lock timescale)

# House two-lobe geometry (run_two_strand_probe conventions)
SIG = P.SIG
SEP = P.SEP
E_RIDGE = P.E_RIDGE
BETA = P.BETA
RHO0 = 1.0 + T.PHI_INV

CHANNELS = P.CHANNELS


def stack_init(solver, M, dtheta):
    """M two-lobe layers along z, layer i phase-rotated by theta_i = i*dtheta
    in the (rho, eps) perturbation doublet plane (see module docstring).

    M=1, dtheta=0 reproduces the committed two_lobe_init construction.
    Returns (ey_hat, ei_hat, u_hat, zs).
    """
    N_ = solver.N
    dev = solver.device
    x = torch.arange(N_, dtype=torch.float64, device=dev)
    X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
    cx = N_ / 2.0
    c1, c2 = cx - SEP / 2.0, cx + SEP / 2.0
    spacing = N_ / M
    zs = [cx + (i - (M - 1) / 2.0) * spacing for i in range(M)]
    rho = torch.full((N_, N_, N_), RHO0, dtype=torch.float64, device=dev)
    eps = torch.zeros_like(rho)
    # Periodic wrap: the box is periodic in z, so each layer's Gaussian is
    # the sum over the k = -1, 0, +1 copies (the canonical single-layer init
    # sits at the box center and never needed the copies; stacked layers at
    # the seam do -- without them the edge layers lose their wrapped tail
    # and the stack's total mass undercounts).
    offsets = (0.0, float(N_), -float(N_))
    for i, zi in enumerate(zs):
        th = i * dtheta
        ct, st = math.cos(th), math.sin(th)
        g1 = torch.zeros_like(X)
        g2 = torch.zeros_like(X)
        for off in offsets:
            zc = Z - zi + off
            g1 = g1 + torch.exp(-((X - c1) ** 2 + (Y - cx) ** 2 + zc ** 2)
                                / (2.0 * SIG ** 2))
            g2 = g2 + torch.exp(-((X - c2) ** 2 + (Y - cx) ** 2 + zc ** 2)
                                / (2.0 * SIG ** 2))
        gp = g1 + g2
        gm = g1 - g2
        rho += RHO0 * BETA * gp * ct - E_RIDGE * gm * st
        eps += RHO0 * BETA * gp * st + E_RIDGE * gm * ct
    ey = (T.PHI * rho + eps) / (1.0 + T.PHI)
    ei = (rho - eps) / (1.0 + T.PHI)
    ey = torch.clamp(ey, min=1e-3)
    ei = torch.clamp(ei, min=1e-3)
    u_hat = torch.zeros(3, N_, N_, N_, dtype=torch.complex128, device=dev)
    return torch.fft.fftn(ey), torch.fft.fftn(ei), u_hat, zs


def slab_phasor(ey, ei, rho_bg):
    """Axial slab phasor S(z) = sum_{x,y} [(rho - rho_bg) + i eps]."""
    rho = ey + ei
    eps = ey - T.PHI * ei
    return (rho - rho_bg + 1j * eps).sum(dim=(0, 1))


def layer_windows(N, zs, device):
    """Partition-of-unity raised-cosine windows centered on each layer
    (periodic distance, width = layer spacing)."""
    z = torch.arange(N, dtype=torch.float64, device=device)
    M = len(zs)
    s = N / M
    w = torch.zeros(M, N, dtype=torch.float64, device=device)
    for i, zi in enumerate(zs):
        d = torch.minimum((z - zi) % N, (zi - z) % N)
        h = 0.5 * (1.0 + torch.cos(np.pi * d / s)) * (d <= s).to(torch.float64)
        w[i] = h
    return w / w.sum(dim=0, keepdim=True)


def axial_current(ey, ei, solver):
    """Per-cell axial phase current J_z = ey*d_z ei - ei*d_z ey.

    This is the R^2 grad-theta phase current of the existing formalism
    (R^2 = ey^2 + ei^2, theta = atan2(ei, ey)); read-only diagnostic,
    spectral derivative consistent with the solver's own _grad."""
    d_ey = torch.fft.ifftn(1j * solver.kz * torch.fft.fftn(ey)).real
    d_ei = torch.fft.ifftn(1j * solver.kz * torch.fft.fftn(ei)).real
    return ey * d_ei - ei * d_ey


def current_profiles(solver, ey, ei, zs):
    """Axial current and coherence-flux slab profiles + per-pair values.

    Jz_slab(z) = sum_{x,y} J_z,  Fc_slab(z) = sum_{x,y} q|J_z| (q from the
    solver's own 'five' gate).  Pair values are the mean over the 3-cell
    window around the midplane between adjacent layer centers.
    Returns (Jz_slab, Fc_slab, Jz_pair, Fc_pair)."""
    N_ = solver.N
    Jz = axial_current(ey, ei, solver)
    Jz_slab = Jz.sum(dim=(0, 1)).cpu().numpy()
    _, q = T.channel_openness(ey, ei)
    Fc_slab = (q * Jz.abs()).sum(dim=(0, 1)).cpu().numpy()
    Jz_pair, Fc_pair = [], []
    for a, b in zip(zs[:-1], zs[1:]):
        zm = 0.5 * (a + b)
        lo = int(round(zm - 1.0)) % N_
        hi = int(round(zm + 1.0)) % N_
        if hi >= lo:
            sl = slice(lo, hi + 1)
        else:                                   # wrapped window
            sl = np.concatenate([np.arange(lo, N_), np.arange(0, hi + 1)])
        Jz_pair.append(float(Jz_slab[sl].mean()))
        Fc_pair.append(float(Fc_slab[sl].mean()))
    return Jz_slab, Fc_slab, Jz_pair, Fc_pair


def two_hump(ey, ei, p_bg):
    """Transverse two-hump structure of the z,y-integrated rho(x) profile.

    C_rho: signed (ridge - midpoint)/ridge contrast of rho(x) -- negative for
    the density-trough (anti-phase) layers.  C_abs: |drho| two-hump contrast,
    positive whenever the transverse envelope keeps two humps with an
    interior node.  'present' = two |drho| maxima >= 6 cells apart.
    """
    rho = ey + ei
    p = rho.sum(dim=(1, 2)).cpu().numpy()
    d = p - p_bg
    ad = np.abs(d)
    if ad.max() < 1e-4 * p_bg:
        return {'present': False, 'C_rho': 0.0, 'C_abs': 0.0,
                'x1': None, 'x2': None, 'd': 0.0}
    positions, merged = P.track_ridges(
        ad, [ey.shape[0] / 2.0 - SEP / 2.0, ey.shape[0] / 2.0 + SEP / 2.0],
        None)
    if merged or len(positions) < 2:
        return {'present': False, 'C_rho': 0.0, 'C_abs': 0.0,
                'x1': None, 'x2': None, 'd': 0.0}
    x1, x2 = float(positions[0]), float(positions[1])
    xm = 0.5 * (x1 + x2)
    i1, i2, im = int(round(x1)), int(round(x2)), int(round(xm))
    p_r = max(p[i1], p[i2])
    ad_r = max(ad[i1], ad[i2])
    return {'present': True, 'C_rho': float((p_r - p[im]) / max(abs(p_r), 1e-30)),
            'C_abs': float((ad_r - ad[im]) / max(ad_r, 1e-30)),
            'x1': x1, 'x2': x2, 'd': float(abs(x2 - x1))}


def measure(solver, ey, ei, rho_prof, centers, prev, windows, zs, rho_bg):
    """All diagnostics at the current state (read-only)."""
    d = P.measure_strands(solver, ey, ei, rho_prof, centers, prev)
    rho_mean = float((ey + ei).mean())
    S = slab_phasor(ey, ei, rho_bg)
    A = S.abs().cpu().numpy()
    d['A_peak'] = float(A.max())
    d['A_mean'] = float(A.mean())
    idx = [int(round(zi)) % solver.N for zi in zs]
    phi = np.unwrap(np.angle(S.cpu().numpy()[idx]))
    d['winding'] = float((phi[-1] - phi[0]) / (2.0 * np.pi))
    W = windows.to(torch.complex128) @ S
    d['layer_phase'] = np.angle(W.cpu().numpy()).tolist()
    d['layer_amp'] = W.abs().cpu().numpy().tolist()
    Jz_slab, Fc_slab, Jz_pair, Fc_pair = current_profiles(solver, ey, ei, zs)
    d['Jz_abs_mean'] = float(np.abs(Jz_slab).mean())
    d['Fc_mean'] = float(Fc_slab.mean())
    d['Jz_pair'] = Jz_pair
    d['Fc_pair'] = Fc_pair
    if len(zs) > 1:
        adv = [((b - a) % (2.0 * np.pi)) for a, b in zip(d['layer_phase'][:-1],
                                                         d['layer_phase'][1:])]
        adv = [x - 2.0 * np.pi if x > np.pi else x for x in adv]
        d['kz_eff'] = float(np.mean(adv) / (zs[1] - zs[0]))
    else:
        d['kz_eff'] = 0.0
    th = two_hump(ey, ei, rho_mean * solver.N ** 2)
    d['two_hump'] = th
    d['C_rho'] = th['C_rho']
    d['C_abs'] = th['C_abs']
    d['ey_min'] = float(ey.min())
    d['ei_min'] = float(ei.min())
    d['mass'] = float((ey + ei).sum())
    d['H'] = float(solver.H)
    d['a'] = float(solver.a)
    return d


def resonance_t0(solver, ey, ei, windows, zs, M, dtheta):
    """t=0 verification of the array-factor law from the initialized fields.

    S_init uses the construction background rho0 (the exact phi-equilibrium);
    the per-layer windowed phasors read the phase advance directly.
    """
    N_ = solver.N
    S = slab_phasor(ey, ei, RHO0)
    A_tot = float(S.sum().abs())
    s_tot_analytic = 2.0 * RHO0 * BETA * (2.0 * np.pi) ** 1.5 * SIG ** 3
    W = (windows.to(torch.complex128) @ S).cpu().numpy()
    phases = np.angle(W)
    amps = np.abs(W)
    advance = []
    for i in range(len(zs) - 1):
        dv = (phases[i + 1] - phases[i]) % (2.0 * np.pi)
        if dv > np.pi:
            dv -= 2.0 * np.pi
        advance.append(dv)
    return {
        'A_tot': A_tot,
        's_tot_analytic': s_tot_analytic,
        'ratio_vs_analytic': A_tot / max(s_tot_analytic, 1e-30),
        'layer_phase': phases.tolist(),
        'layer_amp': amps.tolist(),
        'phase_advance': advance,
        'max_advance_dev': max((abs(a - dtheta) for a in advance),
                               default=0.0),
        'floor_ey': int((ey <= 1e-3 + 1e-12).sum()),
        'floor_ei': int((ei <= 1e-3 + 1e-12).sum()),
    }


def run_case(solver, M, dtheta, tag, outdir, steps=STEPS):
    """Evolve one arm (fresh solver), recording diagnostics."""
    print(f"\n=== run: {tag} (M={M}, dtheta={dtheta:.4f} rad, "
          f"R={resonance(M, dtheta):.4f}, t={steps * T.DT}) ===")
    if M == 1:
        ey_hat, ei_hat, u_hat = P.two_lobe_init(solver, SEP)
        zs = [solver.N / 2.0]
    else:
        ey_hat, ei_hat, u_hat, zs = stack_init(solver, M, dtheta)
    centers = [solver.N / 2.0 - SEP / 2.0, solver.N / 2.0 + SEP / 2.0]
    windows = layer_windows(solver.N, zs, solver.device)
    spacing = solver.N / M

    # t=0 resonance verification on the raw initialization
    ey0 = torch.fft.ifftn(ey_hat).real
    ei0 = torch.fft.ifftn(ei_hat).real
    res0 = resonance_t0(solver, ey0, ei0, windows, zs, M, dtheta)
    res0['min_ey'] = float(ey0.min())
    res0['min_ei'] = float(ei0.min())
    print(f"  t=0 resonance: A_tot={res0['A_tot']:.3f} "
          f"(s_tot={res0['s_tot_analytic']:.3f}, "
          f"ratio={res0['ratio_vs_analytic']:.5f}, R={resonance(M, dtheta):.4f}) "
          f"| phase advance max dev {res0['max_advance_dev']:.4f} rad "
          f"| min fields {res0['min_ey']:.4f}/{res0['min_ei']:.4f} "
          f"| floor cells {res0['floor_ey']}/{res0['floor_ei']}")

    t0 = time.time()
    hist = []
    prev = None
    profiles = {}
    S0 = slab_phasor(ey0, ei0, RHO0).cpu().numpy()
    J0, F0, _, _ = current_profiles(solver, ey0, ei0, zs)
    profiles['0.0'] = {'A': np.abs(S0).tolist(), 'arg': np.angle(S0).tolist(),
                       'Jz': J0.tolist(), 'Fc': F0.tolist()}

    for step in range(steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step % T.REPORT == 0 or step == steps - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            rho_prof = (ey + ei).sum(dim=(1, 2)).cpu().numpy()
            d = measure(solver, ey, ei, rho_prof, centers, prev,
                        windows, zs, RHO0 if step == 0 else float((ey + ei).mean()))
            prev = ([d['x1'], d['x2']] if not d['merged'] else [d['x1']])
            d.update({'step': step, 't': step * T.DT})
            hist.append(d)
            if abs(step * T.DT - 4.0) < 0.6 or abs(step * T.DT - 40.0) < 0.6 \
                    or step == steps - 1:
                rho_m = float((ey + ei).mean())
                Sn = slab_phasor(ey, ei, rho_m).cpu().numpy()
                Jn, Fn, _, _ = current_profiles(solver, ey, ei, zs)
                profiles[f"{step * T.DT:.1f}"] = {
                    'A': np.abs(Sn).tolist(), 'arg': np.angle(Sn).tolist(),
                    'Jz': Jn.tolist(), 'Fc': Fn.tolist()}
            if step % 1000 == 0 or step == steps - 1:
                s0 = d['strands'][0]
                print(f"  t={step*T.DT:6.2f} | d={d['d']:6.3f} "
                      f"Rc={d['Rc']:6.2f} | dth={d['delta_theta']:+6.3f} "
                      f"| A=[{s0['A']:.3f},{d['strands'][1]['A'] if not d['merged'] else s0['A']:.3f}] "
                      f"| A_peak={d['A_peak']:7.2f} C_abs={d['C_abs']:+.3f} "
                      f"wind={d['winding']:+6.3f} |Jz|={d['Jz_abs_mean']:8.1f} "
                      f"Fc={d['Fc_mean']:8.1f} | q_mid={d['q_mid']:.4f} "
                      f"q_flank={d['q_flank']:.4f} | "
                      f"ey_min={d['ey_min']:.4f} ei_min={d['ei_min']:.4f} "
                      f"H={d['H']:.4f} a={d['a']:.3f}")
    elapsed = time.time() - t0
    print(f"  [{tag}] {steps} steps in {elapsed:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'M': M, 'dtheta': dtheta,
                       'spacing': spacing, 'zs': zs, 'steps': steps,
                       'R': resonance(M, dtheta),
                       'resonance_t0': res0, 'profiles': profiles,
                       'hist': hist}, f, indent=1)
    return {'tag': tag, 'M': M, 'dtheta': dtheta, 'elapsed': elapsed,
            'resonance_t0': res0, 'hist': hist, 'profiles': profiles}


def resonance(M, dtheta):
    """Array-factor magnitude |sin(M dtheta/2)/sin(dtheta/2)| (M for dtheta=0)."""
    if abs(dtheta) < 1e-12:
        return float(M)
    return abs(math.sin(M * dtheta / 2.0) / math.sin(dtheta / 2.0))


def at_t(hist, t_target):
    return min(hist, key=lambda d: abs(d['t'] - t_target))


def summarize_arm(r):
    """Verdict quantities at t=0/4/40 from the arm history."""
    h = r['hist']
    t4, t40 = at_t(h, 4.0), at_t(h, 40.0)
    t0 = h[0]
    mass0 = t0['mass']
    degenerate = t0['A_peak'] < 1e-6      # R=0 arms: no t=0 envelope
    return {
        't4': {'d': t4['d'], 'merged': t4['merged'],
               'A_plus': t4['A_plus'], 'A_minus': t4['A_minus'],
               'delta_theta': t4['delta_theta'],
               'two_hump': t4['two_hump'], 'C_abs': t4['C_abs'],
               'A_peak': t4['A_peak'], 'winding': t4['winding'],
               'q_mid': t4['q_mid'], 'q_flank': t4['q_flank'],
               'layer_phase': t4['layer_phase'],
               'Jz_abs_mean': t4['Jz_abs_mean'], 'Fc_mean': t4['Fc_mean'],
               'kz_eff': t4['kz_eff']},
        't40': {'d': t40['d'], 'merged': t40['merged'],
                'A_plus': t40['A_plus'], 'A_minus': t40['A_minus'],
                'delta_theta': t40['delta_theta'],
                'two_hump': t40['two_hump'], 'C_abs': t40['C_abs'],
                'A_peak': t40['A_peak'], 'winding': t40['winding'],
                'q_mid': t40['q_mid'], 'q_flank': t40['q_flank'],
                'layer_phase': t40['layer_phase'],
                'Jz_abs_mean': t40['Jz_abs_mean'], 'Fc_mean': t40['Fc_mean'],
                'kz_eff': t40['kz_eff']},
        'A_peak_ratio_t4': t4['A_peak'] / max(t0['A_peak'], 1e-30),
        'A_peak_ratio_t40': t40['A_peak'] / max(t0['A_peak'], 1e-30),
        'A_peak_t0': t0['A_peak'],
        'degenerate_peak': degenerate,
        'mass_drift': abs(t40['mass'] - mass0) / max(mass0, 1e-30),
        'ey_min': min(d['ey_min'] for d in h),
        'ei_min': min(d['ei_min'] for d in h),
        'H_end': t40['H'], 'a_end': t40['a'],
    }


def finalize(runs, rdir):
    """Assemble results.json, verdicts, and the console summary from the
    run dicts (each with tag/M/dtheta/elapsed/resonance_t0/hist/profiles).
    Also used by --from-runs to rebuild from preserved per-arm JSONs."""
    for r in runs:
        if 'summary' not in r:
            r['summary'] = summarize_arm(r)
    results = {
        'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT,
                 't_end': runs[0]['hist'][-1]['t'],
                 'gate_model': 'five (solver)',
                 'SIG': SIG, 'SEP': SEP, 'E_RIDGE': E_RIDGE, 'BETA': BETA,
                 'stack_axis': 'z', 'spacing': 'N/M cells',
                 'phase_convention': 'SO(2) rotation of the (rho, eps) '
                                     'perturbation doublet about the '
                                     'phi-equilibrium background',
                 'note': 't = 40 = 2/lambda lock timescale; t = 4 '
                         'characterization records from the same runs'},
        'arms': {r['tag']: {
            'M': r['M'], 'dtheta': r['dtheta'],
            'R_pred': resonance(r['M'], r['dtheta']),
            'resonance_t0': r['resonance_t0'], 'summary': r['summary'],
            'elapsed_s': r['elapsed'],
            'Jz_abs_mean_0': r['hist'][0]['Jz_abs_mean'],
            'Fc_mean_0': r['hist'][0]['Fc_mean'],
            'kz_eff_0': r['hist'][0]['kz_eff']} for r in runs},
    }

    # ── Verdicts ──────────────────────────────────────────────────────────
    b = results['arms']['m1_0']
    s = b['summary']
    base_ok = (9.85 <= s['t4']['d'] <= 10.5 and 14.5 <= s['t40']['d'] <= 17.0
               and s['t40']['delta_theta'] <= 0.10 and s['t40']['A_plus'] <= 0.20
               and 0.705 <= s['t40']['q_mid'] <= 0.712)
    print(f"\n=== LATTICE-STACK PROBE RESULTS (t=40) ===")
    print(f"A1 baseline (m1_0): d 9.90 -> {s['t4']['d']:.2f} (t=4) -> "
          f"{s['t40']['d']:.2f} (t=40) | dth(40)={s['t40']['delta_theta']:.3f} "
          f"| A_plus(40)={s['t40']['A_plus']:.3f} | q_mid(40)={s['t40']['q_mid']:.4f} "
          f"| reproduced={base_ok}")

    s_tot_cal = b['resonance_t0']['A_tot']      # m1_0 calibrates s_tot
    print(f"\nA2 resonance law at t=0 (s_tot calibrated by m1_0 = {s_tot_cal:.2f}):")
    for tag in results['arms']:
        a = results['arms'][tag]
        r0 = a['resonance_t0']
        R = a['R_pred']
        ratio = r0['A_tot'] / max(s_tot_cal * R, 1e-30) if R > 1e-9 else r0['A_tot'] / max(s_tot_cal, 1e-30)
        if R > 1e-9:
            ok = 0.95 <= ratio <= 1.05
            print(f"  {tag:8s}: A_tot={r0['A_tot']:9.2f} vs s_tot*R="
                  f"{s_tot_cal * R:9.2f}  ratio={ratio:.4f}  "
              f"adv_dev={r0['max_advance_dev']:.4f} rad  {'PASS' if ok else 'FAIL'}")
        else:
            print(f"  {tag:8s}: R=0 (cancellation): A_tot={r0['A_tot']:.4e} "
                  f"(s_tot={s_tot_cal:.2f})  {'PASS' if r0['A_tot'] < 1e-6 * s_tot_cal else 'FAIL'}")

    print(f"\nA3 two-hump envelope persistence:")
    for tag in results['arms']:
        a = results['arms'][tag]
        s = a['summary']
        for tt in ('t4', 't40'):
            th = s[tt]['two_hump']
            print(f"  {tag:8s} {tt}: present={th['present']} "
                  f"C_rho={th['C_rho']:+.3f} C_abs={th['C_abs']:+.3f} "
                  f"d={s[tt]['d']:.2f} A_peak={s[tt]['A_peak']:7.2f} "
                  f"wind={s[tt]['winding']:+6.3f}")
    print()
    for tag in results['arms']:
        a = results['arms'][tag]
        s = a['summary']
        ratio4 = s['A_peak_ratio_t4'] if not s.get('degenerate_peak') else float('nan')
        ratio40 = s['A_peak_ratio_t40'] if not s.get('degenerate_peak') else float('nan')
        print(f"  {tag:8s}: A_peak ratio t4={ratio4:.3f} "
              f"t40={ratio40:.3f} | d {s['t4']['d']:.2f}->"
              f"{s['t40']['d']:.2f} | q_mid {s['t4']['q_mid']:.4f}->"
              f"{s['t40']['q_mid']:.4f} | Jz0={a['Jz_abs_mean_0']:8.1f} "
              f"Fc0={a['Fc_mean_0']:8.1f} kz0={a['kz_eff_0']:+.4f} | "
              f"mass drift {s['mass_drift']:.1e} "
              f"| ey_min {s['ey_min']:.4f} ei_min {s['ei_min']:.4f} "
              f"| H_end {s['H_end']:.4f} a_end {s['a_end']:.2f} | "
              f"{a['elapsed_s']:.1f}s")

    results['verdicts'] = {
        'A1_baseline_reproduced': bool(base_ok),
        'A2_resonance_t0': {
            tag: ('PASS' if (results['arms'][tag]['R_pred'] > 1e-9 and
                             0.95 <= results['arms'][tag]['resonance_t0']['A_tot'] /
                             max(s_tot_cal * results['arms'][tag]['R_pred'], 1e-30) <= 1.05)
                   or (results['arms'][tag]['R_pred'] <= 1e-9 and
                       results['arms'][tag]['resonance_t0']['A_tot'] < 1e-6 * s_tot_cal)
                   else 'FAIL')
            for tag in results['arms']},
        'A3_two_hump_t4': {tag: bool(results['arms'][tag]['summary']['t4']['two_hump']['present']
                                      and results['arms'][tag]['summary']['t4']['C_abs'] >= 0.05)
                           for tag in results['arms']},
        'A3_two_hump_t40': {tag: bool(results['arms'][tag]['summary']['t40']['two_hump']['present']
                                      and results['arms'][tag]['summary']['t40']['C_abs'] >= 0.05)
                            for tag in results['arms']},
    }

    # B1: does the envelope's t=4 retention correlate with the axial current?
    # R=0 arms have no t=0 envelope (exact cancellation) -- their retention
    # ratio is degenerate and they are excluded from the correlation.
    keep = [r for r in runs if resonance(r['M'], r['dtheta']) > 1e-9]
    jz0 = np.array([r['hist'][0]['Jz_abs_mean'] for r in keep])
    dth = np.array([r['dtheta'] for r in keep])
    ret4 = np.array([r['summary']['A_peak_ratio_t4'] for r in keep])
    cabs4 = np.array([r['summary']['t4']['C_abs'] for r in keep])

    def corr(x, y):
        if len(x) < 3 or np.std(x) < 1e-12 or np.std(y) < 1e-12:
            return {'pearson': 0.0, 'spearman': 0.0, 'n': int(len(x)),
                    'degenerate': True}
        pr = float(np.corrcoef(x, y)[0, 1])
        try:
            import scipy.stats as st
            sp = float(st.spearmanr(x, y).statistic)
        except Exception:
            rx = np.argsort(np.argsort(x))
            ry = np.argsort(np.argsort(y))
            sp = float(np.corrcoef(rx, ry)[0, 1])
        return {'pearson': pr, 'spearman': sp, 'n': int(len(x)),
                'degenerate': False}

    results['verdicts']['B1_current_correlation'] = {
        'retention_vs_Jz': corr(jz0, ret4),
        'retention_vs_dtheta': corr(dth, ret4),
        'C_abs_vs_Jz': corr(jz0, cabs4),
        'C_abs_vs_dtheta': corr(dth, cabs4),
        'excluded': [r['tag'] for r in runs if all(r is not k for k in keep)],
        'note': 'cross-arm correlations over the R > 0 arms only '
                '(R = 0 arms have no t = 0 envelope by construction); '
                'Jz at t ~ 0 (first in-loop record), C_abs at t = 4, '
                'retention = A_peak(4)/A_peak(0)'}

    print("\nB1 axial-coherence-current correlation "
          f"(n = {len(keep)}, R > 0 arms, qualitative):")
    for k, v in results['verdicts']['B1_current_correlation'].items():
        if isinstance(v, dict) and not v.get('degenerate'):
            print(f"  {k:20s}: pearson={v['pearson']:+.3f} "
                  f"spearman={v['spearman']:+.3f}")
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n=== VERDICT ===")
    print(f"A1 (single-layer limit): {'PASS' if base_ok else 'FAIL'} -- "
          f"m1_0 reproduces the published t=4 persisted / t=40 escape record.")
    print(f"A2 (resonance law at t=0): "
          f"{'PASS' if all(v == 'PASS' for v in results['verdicts']['A2_resonance_t0'].values()) else 'PARTIAL/FAIL'}")
    pers = [tag for tag in results['arms']
            if results['verdicts']['A3_two_hump_t4'][tag]
            and results['verdicts']['A3_two_hump_t40'][tag]]
    print(f"A3 (persistent two-hump envelope at t=4 AND t=40): "
          f"{pers if pers else 'NONE -- no arm keeps the two-hump envelope to t=40'}")
    print(f"\nResults: {rdir}/results.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--steps', type=int, default=STEPS,
                        help='override STEPS (t = steps*dt)')
    parser.add_argument('--arm', action='append', default=None,
                        help='restrict to one arm tag (repeatable)')
    parser.add_argument('--from-runs', default=None, metavar='DIR',
                        help='rebuild results.json + verdicts from preserved '
                             'per-arm run_*.json files in DIR (no rerun)')
    args = parser.parse_args()
    steps = args.steps

    if args.from_runs is not None:
        import glob as _glob
        runs = []
        for f in sorted(_glob.glob(f"{args.from_runs}/run_*.json")):
            d = json.load(open(f))
            runs.append({'tag': d['kind'], 'M': d['M'], 'dtheta': d['dtheta'],
                         'elapsed': 0.0, 'resonance_t0': d['resonance_t0'],
                         'hist': d['hist'], 'profiles': d['profiles']})
        print(f"Rebuilding results from {len(runs)} preserved arms in "
              f"{args.from_runs}")
        finalize(runs, args.from_runs)
        return

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t={steps * T.DT}  "
          f"gate='five'  SIG={SIG}  SEP={SEP}  E_RIDGE={E_RIDGE}  "
          f"BETA={BETA}  s_tot(analytic)={2.0 * RHO0 * BETA * (2.0 * np.pi) ** 1.5 * SIG ** 3:.2f}")

    arms = [
        ('m1_0', 1, 0.0),
        ('m2_2pi5', 2, 2.0 * np.pi / 5.0),
        ('m4_2pi5', 4, 2.0 * np.pi / 5.0),
        ('m8_2pi5', 8, 2.0 * np.pi / 5.0),
        ('m16_2pi5', 16, 2.0 * np.pi / 5.0),
        ('m8_pi5', 8, np.pi / 5.0),
        ('m8_pi2', 8, np.pi / 2.0),
        ('m8_pi', 8, np.pi),
    ]
    if args.arm is not None:
        arms = [a for a in arms if a[0] in args.arm]
        if not arms:
            raise SystemExit(f"no matching arms in {[a[0] for a in arms]}")
    print(f"Arms: {', '.join(a[0] for a in arms)}  "
          f"R: {', '.join(f'{a[0]}={resonance(a[1], a[2]):.3f}' for a in arms)}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_lattice_stack"
    os.makedirs(rdir, exist_ok=True)

    runs = []
    for tag, M, dtheta in arms:
        solver = T.build_solver(device)     # fresh solver per arm
        r = run_case(solver, M, dtheta, tag, rdir)
        r['summary'] = summarize_arm(r)
        runs.append(r)

    finalize(runs, rdir)


if __name__ == "__main__":
    main()
