#!/usr/bin/env python3
"""TS6 axial twist-chi validation ramp: corrected component, tests 0-4.

Validation suite for `two-fluid/scratch_twist_chi_axial.py` (the parity-odd
conversion coupling conv -> -lam (1 - chi_ax g / J_scale) (1-q) eps of
`hypotheses/two-strand-five-channel-matter-organization.md` sec 3.2, with
g = (curl J)_x in the solver label frame = -(curl J)_z in box labels, the
axial component along the TS6 helix axis; the prior layer measured the
transverse component, box-frame -(curl J)_x -- see the layer module
docstring):

  T0  component/sign check: on a synthetic field with known axial curl
      (theta = kx*x_box, R^2 = 1 + alpha cos(ky*y_box), so
      (curl J)_{box z} = +kx*alpha*ky*sin(ky*y)), the layer's g must equal
      -kx*alpha*ky*sin(ky*y) to grid accuracy, and the prior transverse
      formula must read 0 on the same field (discriminator).  Also probes
      J_scale = max|g| at t = 0 on the TS6 helix init (read-only, no
      evolution).
  T1  bit-for-bit no-op: chi_ax = 0 vs canonical solver, both arms (twist+,
      ztwist), exact equality of (u, ey, ei) hats after every one of 4000
      steps plus solver scalar state (a, H, q_mean) at report cadence.
  T2  mirror identities: (chi, w0) in {(+1,+W0), (-1,+W0), (+1,-W0)} with
      per-w0 chi = 0 baselines.  For the axial component the coupled system
      is exactly mirror-symmetric under (chi, w0) -> (chi, -w0), so
      dTw(chi,+W0) = -dTw(chi,-W0) is an exact-symmetry check
      (|ratio_w0 + 1| < 1e-4).  The chi-flip ratio
      dTw(chi,+W0) = -dTw(-chi,+W0) is not forced by symmetry; it is the
      empirical generation-linearity test (|ratio_chi + 1| < 0.05).
  T3  magnitude ramp: chi in {0, +-0.25, +-0.5, +-1, +-2} on the twist arm,
      t = 4; monotonicity, linear-regime doubling, wound-up band, and
      domain-exit telemetry (max chi*g/J_scale, f < 0 cell fraction, clamp
      near-floor, ey/ei minima, seam ratio of the g field itself).
  T4  periodicity-lock seeds: w0 in {2*pi/N, 4*pi/N} (both closing exactly
      across the periodic seam) x chi in {0, 1}, t = 40 = 2/lam; lock
      criterion |Tw_end(2W0) - Tw_end(W0)| <= 0.05 at chi = 1 (seed
      independence) with the dominant axial wavenumber unchanged; expected
      honest null (the term carries no axial scale).

Protocol (house coherence-budget regime, same as run_two_strand_twist_probe):
fresh solver per arm (RK2 mutates solver state), N = 48, lam = 0.05,
dt = 0.001, gate 'five', u = 0.  runs/ is gitignored -- commit scripts only.
T0/T1 are the minimal component/no-op validation; the full matrix is
`--tests 0,1,2,3,4`.

Usage:
    python two-fluid/run_twist_chi_axial_ramp.py [--tests 0,1,2,3,4] [--bench N]
Output:
    runs/<rid>_chi_axial_ramp/test0.json ... test4.json, results.json, verdicts
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_trauma_wake_lock as T
import run_two_strand_twist_probe as P
from scratch_twist_chi_axial import TwistChiAxialLayer

# ── Protocol (coherence-budget regime: lambda = 0.05, t = 4 / t = 40) ─────
T.LAM = 0.05
T.DT = 0.001
T.REPORT = 50
STEPS_T4 = 4000            # t = 4   = 0.2/lambda (characterization)
STEPS_T40 = 40000          # t = 40  = 2/lambda   (lock timescale)
REPORT_T40 = 200

W0 = 2.0 * np.pi / T.N     # one full turn per periodic box (closing)
W0_2 = 4.0 * np.pi / T.N   # two full turns per box (closing)

RAMP_CHIS = [0.0, 0.25, -0.25, 0.5, -0.5, 1.0, -1.0, 2.0, -2.0]
MIRROR_ARMS = [('base_plus', 0.0, +W0), ('base_minus', 0.0, -W0),
               ('chi+_plus', +1.0, +W0), ('chi-_plus', -1.0, +W0),
               ('chi+_minus', +1.0, -W0)]

# Component/sign record (the correction, restated in the raw output):
COMPONENT_NOTE = (
    "g = (curl J)_x in the solver label frame (x = grid axis 2 = the TS6 "
    "helix axis) = -(curl J)_z in box labels; "
    "conv -> -lam (1 - chi_ax*g/J_scale) (1-q) eps, so chi_ax multiplies "
    "-(curl J)_{box z}; the TS6 sketch's chi_circ (multiplying +(curl J)_z "
    "in box labels) equals -chi_ax under this convention.")

DEVICE = None


def build_layer(device, chi_ax=0.0):
    """Fresh layer solver, canonical probe config (mirrors T.build_solver)."""
    solver = TwistChiAxialLayer(
        N=T.N, L=T.L, nu=T.NU, D=T.D, lam=T.LAM, chi=0.0,
        hubble_mode='conversion', cs2=0.0, qi_gate=True,
        qi_memory=False, chi_ax=chi_ax, device=device)
    solver.gate_model = 'five'
    return solver


def g_telemetry(solver, ey, ei):
    """Domain-exit and g-seam telemetry (read-only)."""
    g = solver._curlAxial(torch.fft.fftn(ey), torch.fft.fftn(ei), ey, ei)
    js = solver.J_scale if solver.J_scale is not None else float(g.abs().max())
    r = solver.chi_ax * g / js
    g_np = g.cpu().numpy()
    seam = np.concatenate([g_np[:, :, 0], g_np[:, :, 1],
                           g_np[:, :, T.N - 2], g_np[:, :, T.N - 1]])
    return {
        'J_scale': js,
        'max_chi_g_over_J': float(r.abs().max().cpu()),
        'frac_f_lt0_pos': float((r > 1.0).double().mean().cpu()),
        'frac_f_lt0_neg': float((r < -1.0).double().mean().cpu()),
        'g_seam_ratio': float(np.abs(seam).max() / max(np.abs(g_np).max(), 1e-30)),
    }


def evolve(solver, omega0, steps, report, tag, with_telemetry=False):
    """Fresh init per arm; per-report track_filament + optional telemetry."""
    ey_hat, ei_hat, u_hat = P.helix_init(solver, omega0)
    prev = None
    hist = []
    t0 = time.time()
    for step in range(steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step % report == 0 or step == steps - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            m = P.track_filament(solver, ey, ei, omega0, prev)
            if m['ok']:
                prev = {'z': m['z'], 'x1': m['x1'], 'y1': m['y1'],
                        'x2': m['x2'], 'y2': m['y2']}
            if with_telemetry:
                m.update(g_telemetry(solver, ey, ei))
            m.update({'step': step, 't': step * T.DT,
                      'mass': float((ey + ei).sum().cpu()),
                      'a': float(solver.a.cpu()), 'H': float(solver.H.cpu())})
            hist.append(m)
            print(f"  t={step*T.DT:5.2f} | win={len(m['z']):3d} | "
                  f"d={m['d_mean']:6.3f} | Tw={m['Tw']:+6.3f} "
                  f"| <Omega>={m['omega_mean']:+6.4f} "
                  f"| dth={m['delta_theta']:+6.3f} "
                  f"| q={m['q_glob']:.4f} | seam={m['seam_ratio']:.1e} "
                  f"| nf={m['near_floor']:.1e} | mass={m['mass']:.4f}")
    print(f"  [{tag}] {steps} steps in {time.time() - t0:.1f}s")
    return hist


ARM_DIR = None   # set by main(): runs/<rid>_chi_axial_ramp


def run_arm(tag, chi_ax, omega0, steps, report, with_telemetry=False,
            persist=True):
    solver = build_layer(DEVICE, chi_ax=chi_ax)
    hist = evolve(solver, omega0, steps, report, tag, with_telemetry)
    summ = P.summarize(tag, hist)
    summ['chi_ax'] = chi_ax
    summ['omega0'] = omega0
    summ['J_scale'] = solver.J_scale
    if persist and ARM_DIR is not None:
        with open(f"{ARM_DIR}/arm_{tag}.json", "w") as f:
            json.dump({'tag': tag, 'chi_ax': chi_ax, 'omega0': omega0,
                       'summary': summ, 'hist': hist}, f, indent=1)
    return solver, hist, summ


def test0_component(outdir):
    print("\n=== T0: analytic component/sign check (axial curl) ===")
    res = {'component_note': COMPONENT_NOTE}
    # Synthetic field: theta = kx * x_box, R^2 = 1 + alpha*cos(ky*y_box)
    #   -> J = R^2 grad(theta) = (kx R^2, 0, 0) in box labels
    #   -> (curl J)_{box z} = +kx*alpha*ky*sin(ky*y_box)
    #   -> layer g = -(curl J)_{box z} = -kx*alpha*ky*sin(ky*y_box)
    # The prior transverse formula reads 0 on this field (J has no axis-2
    # component): a sharp discriminator between the components.
    solver = build_layer(DEVICE, chi_ax=0.0)
    N_ = T.N
    dx = T.L / N_
    kx = 2.0 * np.pi / T.L          # 1 cycle per box
    ky = 4.0 * np.pi / T.L          # 2 cycles per box
    alpha = 0.3
    x_box = torch.arange(N_, dtype=torch.float64, device=DEVICE) * dx
    y_box = torch.arange(N_, dtype=torch.float64, device=DEVICE) * dx
    Xb = x_box.unsqueeze(1).unsqueeze(2).expand(N_, N_, N_)
    Yb = y_box.unsqueeze(0).unsqueeze(2).expand(N_, N_, N_)
    R2 = 1.0 + alpha * torch.cos(ky * Yb)
    R = R2.sqrt()
    ey = R * torch.cos(kx * Xb)
    ei = R * torch.sin(kx * Xb)
    g = solver._curlAxial(torch.fft.fftn(ey), torch.fft.fftn(ei), ey, ei)
    g_exp = -kx * alpha * ky * torch.sin(ky * Yb)
    err = float((g - g_exp).abs().max().cpu())
    # prior transverse formula on the same field (must be ~0)
    gey = solver._grad(torch.fft.fftn(ey))
    gei = solver._grad(torch.fft.fftn(ei))
    Jx = ey * gei[0] - ei * gey[0]          # solver-label x = grid axis 2
    Jy = ey * gei[1] - ei * gey[1]
    g_prior = (torch.fft.ifftn(1j * solver.kx * torch.fft.fftn(Jy)).real
               - torch.fft.ifftn(1j * solver.ky * torch.fft.fftn(Jx)).real)
    prior_max = float(g_prior.abs().max().cpu())
    res['err_axial_vs_analytic'] = err
    res['prior_transverse_max_abs'] = prior_max
    res['pass'] = err < 1e-6 and prior_max < 1e-6
    print(f"  max|g_axial - analytic| = {err:.3e} "
          f"({'PASS < 1e-6' if err < 1e-6 else 'FAIL'})")
    print(f"  max|g_prior_transverse| on same field = {prior_max:.3e} "
          f"(discriminator; expect ~0)")
    # J_scale probe on the TS6 helix init (read-only, no evolution)
    ey_hat, ei_hat, _ = P.helix_init(solver, W0)
    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    g0 = solver._curlAxial(ey_hat, ei_hat, ey, ei)
    res['J_scale_helix_t0'] = float(g0.abs().max().cpu())
    res['g_rms_helix_t0'] = float(g0.pow(2).mean().sqrt().cpu())
    print(f"  helix init (twist arm): J_scale = max|g| = "
          f"{res['J_scale_helix_t0']:.6e} "
          f"(prior transverse component: 6.7556e-02)")
    with open(f"{outdir}/test0.json", "w") as f:
        json.dump(res, f, indent=1)
    return res


def test1_bitforbit(outdir):
    print("\n=== T1: bit-for-bit no-op at chi_ax = 0 vs canonical ===")
    res = {'steps': STEPS_T4, 'arms': {}}
    for name, w0 in (('twist', W0), ('ztwist', 0.0)):
        canon = T.build_solver(DEVICE)
        layer = build_layer(DEVICE, chi_ax=0.0)
        cy_hat, ci_hat, cu_hat = P.helix_init(canon, w0)   # (ey, ei, u)
        ly_hat, li_hat, lu_hat = P.helix_init(layer, w0)
        first_diff = None
        for step in range(STEPS_T4):
            cu_hat, cy_hat, ci_hat = canon.rk2_step(cu_hat, cy_hat, ci_hat, T.DT)
            lu_hat, ly_hat, li_hat = layer.rk2_step(lu_hat, ly_hat, li_hat, T.DT)
            eq = (all(torch.equal(cu_hat[d], lu_hat[d]) for d in range(3))
                  and torch.equal(cy_hat, ly_hat) and torch.equal(ci_hat, li_hat))
            if not eq and first_diff is None:
                first_diff = step
            if step % T.REPORT == 0:
                eqs = (float(canon.a.cpu()) == float(layer.a.cpu())
                       and float(canon.H.cpu()) == float(layer.H.cpu())
                       and float(canon.q_mean.cpu()) == float(layer.q_mean.cpu()))
                if not eqs and first_diff is None:
                    first_diff = step
        res['arms'][name] = {
            'first_diff_step': first_diff,
            'pass': first_diff is None,
            'layer_J_scale_untouched': layer.J_scale is None,
        }
        print(f"  {name}: {'PASS (bit-identical over %d steps)' % STEPS_T4 if first_diff is None else 'FAIL at step %d' % first_diff}")
    res['pass'] = all(a['pass'] for a in res['arms'].values())
    with open(f"{outdir}/test1.json", "w") as f:
        json.dump(res, f, indent=1)
    return res


def test2_mirror(outdir):
    print("\n=== T2: sign-mirror identities (t = 4) ===")
    arms = {}
    for tag, chi, w0 in MIRROR_ARMS:
        _, _, s = run_arm(tag, chi, w0, STEPS_T4, T.REPORT)
        arms[tag] = {'Tw_start': s['Tw_start'], 'Tw_end': s['Tw_end'],
                     'band': s['band'], 'd_end': s['d_end'],
                     'mass_drift': s['mass_drift'], 'J_scale': s['J_scale']}
    base = {'+W0': arms['base_plus']['Tw_end'], '-W0': arms['base_minus']['Tw_end']}
    dTw = {
        'chi+_plus': arms['chi+_plus']['Tw_end'] - base['+W0'],
        'chi-_plus': arms['chi-_plus']['Tw_end'] - base['+W0'],
        'chi+_minus': arms['chi+_minus']['Tw_end'] - base['-W0'],
    }
    # Exact-symmetry identity (axial component): dTw(chi,+W0) = -dTw(chi,-W0)
    r_w0 = dTw['chi+_plus'] / dTw['chi+_minus'] if dTw['chi+_minus'] != 0.0 else None
    p_w0 = r_w0 is not None and abs(r_w0 + 1.0) < 1e-4
    # Empirical generation-linearity test: dTw(-chi,+W0) = -dTw(chi,+W0)
    r_chi = dTw['chi-_plus'] / dTw['chi+_plus'] if dTw['chi+_plus'] != 0.0 else None
    p_chi = r_chi is not None and abs(r_chi + 1.0) < 0.05
    res = {'arms': arms, 'dTw': dTw,
           'ratio_w0_flip': r_w0, 'mirror_symmetry': bool(p_w0),
           'ratio_chi_flip': r_chi, 'generation_linear': bool(p_chi),
           'pass': bool(p_w0)}
    print(f"  dTw(+1,+W0) = {dTw['chi+_plus']:+.5f}")
    print(f"  dTw(+1,-W0) = {dTw['chi+_minus']:+.5f}  "
          f"(exact mirror: expect -dTw(+1,+W0))")
    print(f"  ratio dTw(+W0)/dTw(-W0) = {r_w0:+.8f} -> "
          f"{'PASS (exact symmetry)' if p_w0 else 'FAIL'}")
    print(f"  dTw(-1,+W0) = {dTw['chi-_plus']:+.5f}  "
          f"(generation test: expect -dTw(+1,+W0))")
    print(f"  ratio dTw(-chi)/dTw(+chi) = {r_chi:+.4f} -> "
          f"{'PASS (linear generation)' if p_chi else 'measured'}")
    with open(f"{outdir}/test2.json", "w") as f:
        json.dump(res, f, indent=1)
    return res


def test3_ramp(outdir):
    print("\n=== T3: magnitude ramp (t = 4, twist arm) ===")
    arms = {}
    for chi in RAMP_CHIS:
        tag = f"chi{'%+.2f' % chi}"
        solver, hist, s = run_arm(tag, chi, W0, STEPS_T4, T.REPORT,
                                  with_telemetry=True)
        tele = [{k: m[k] for k in ('step', 't', 'J_scale', 'max_chi_g_over_J',
                                   'frac_f_lt0_pos', 'frac_f_lt0_neg',
                                   'g_seam_ratio', 'near_floor', 'ey_min',
                                   'ei_min', 'q_glob', 'mass')}
                for m in hist]
        arms[tag] = {'chi': chi, 'Tw_start': s['Tw_start'], 'Tw_end': s['Tw_end'],
                     'band': s['band'], 'd_end': s['d_end'],
                     'mass_drift': s['mass_drift'],
                     'J_scale': s['J_scale'],
                     'max_chi_g_over_J_max': max(t['max_chi_g_over_J'] for t in tele),
                     'frac_f_lt0_max': max(t['frac_f_lt0_pos'] + t['frac_f_lt0_neg'] for t in tele),
                     'first_f_lt0_t': next((t['t'] for t in tele
                                            if t['max_chi_g_over_J'] > 1.0), None),
                     'near_floor_max': max(t['near_floor'] for t in tele),
                     'ey_min': min(t['ey_min'] for t in tele),
                     'ei_min': min(t['ei_min'] for t in tele),
                     'g_seam_max': max(t['g_seam_ratio'] for t in tele),
                     'q_glob_end': tele[-1]['q_glob']}
        print(f"  chi={chi:+.2f}: Tw {s['Tw_start']:+.3f} -> {s['Tw_end']:+.3f} "
              f"[{s['band']}] | dTw={arms[tag]['Tw_end'] - arms['chi+0.00']['Tw_end']:+.5f} "
              f"| max chi*g/J={arms[tag]['max_chi_g_over_J_max']:.3f} "
              f"| f<0 frac {arms[tag]['frac_f_lt0_max']:.2e} "
              f"| near_floor {arms[tag]['near_floor_max']:.1e} "
              f"| ey_min {arms[tag]['ey_min']:.4f}")
    base = arms['chi+0.00']['Tw_end']
    dTw = {chi: arms[f"chi{'%+.2f' % chi}"]['Tw_end'] - base for chi in RAMP_CHIS}
    pos = [dTw[c] for c in (0.25, 0.5, 1.0, 2.0)]
    neg = [dTw[c] for c in (-0.25, -0.5, -1.0, -2.0)]
    monotone = all(p >= 0 for p in pos) and all(n <= 0 for n in neg) and \
        pos[0] <= pos[1] <= pos[2] <= pos[3] and neg[0] >= neg[1] >= neg[2] >= neg[3]
    lin_ok = None
    if abs(dTw[0.25]) > 1e-4:
        r = dTw[0.5] / dTw[0.25]
        lin_ok = 1.0 <= r <= 3.0
    wound = abs(arms['chi+2.00']['Tw_end']) > 1.25 * abs(arms['chi+2.00']['Tw_start'])
    gen = max(abs(dTw[c]) for c in RAMP_CHIS if c != 0.0)
    res = {'arms': arms, 'dTw': dTw, 'monotone': bool(monotone),
           'linear_doubling_ok': lin_ok, 'wound_up_chi2': bool(wound),
           'max_abs_dTw': gen, 'generation_present': gen >= 0.01,
           'pass': bool(monotone)}
    print(f"  monotone in chi: {'PASS' if monotone else 'FAIL'}")
    print(f"  linear doubling dTw(0.5)/dTw(0.25) = {dTw[0.5]/dTw[0.25] if abs(dTw[0.25]) > 1e-4 else 'n/a'}")
    print(f"  wound-up at chi=+2: {'YES' if wound else 'no'}")
    print(f"  generation signature max|dTw| = {gen:.5f} "
          f"({'present >= 0.01' if gen >= 0.01 else 'NULL < 0.01'})")
    with open(f"{outdir}/test3.json", "w") as f:
        json.dump(res, f, indent=1)
    return res


def test4_lock(outdir):
    print("\n=== T4: periodicity-lock seed arms (t = 40 = 2/lambda) ===")
    arms = {}
    for w0, name in ((W0, 'W0'), (W0_2, '2W0')):
        for chi in (0.0, 1.0):
            tag = f"{name}_chi{'%g' % chi}"
            _, _, s = run_arm(tag, chi, w0, STEPS_T40, REPORT_T40)
            arms[tag] = {'omega0': w0, 'chi': chi, 'Tw_start': s['Tw_start'],
                         'Tw_end': s['Tw_end'], 'band': s['band'],
                         'd_end': s['d_end'], 'd_back': s['d_back_mean'],
                         'dom_k1': s['dom_k1_end'], 'dom_k1_frac': s['dom_k1_frac_end'],
                         'dom_k2': s['dom_k2_end'],
                         'gth_max': s['gth_abs_max_end'],
                         'delta_theta': s['delta_theta_end'],
                         'seam_ratio': s['seam_ratio_end'],
                         'near_floor_max': s['near_floor_max'],
                         'mass_drift': s['mass_drift'], 'J_scale': s['J_scale']}
        print(f"  {name}: chi=0 Tw {arms[name+'_chi0']['Tw_start']:+.3f} -> "
              f"{arms[name+'_chi0']['Tw_end']:+.3f} [{arms[name+'_chi0']['band']}] | "
              f"chi=1 Tw -> {arms[name+'_chi1']['Tw_end']:+.3f} [{arms[name+'_chi1']['band']}] | "
              f"k1 {arms[name+'_chi1']['dom_k1']:.4f} (frac {arms[name+'_chi1']['dom_k1_frac']:.2f})")
    dTw_w0 = arms['W0_chi1']['Tw_end'] - arms['W0_chi0']['Tw_end']
    dTw_2w0 = arms['2W0_chi1']['Tw_end'] - arms['2W0_chi0']['Tw_end']
    tw_gap = abs(arms['2W0_chi1']['Tw_end'] - arms['W0_chi1']['Tw_end'])
    locked = tw_gap <= 0.05 and \
        abs(arms['2W0_chi1']['dom_k1'] - arms['W0_chi1']['dom_k1']) < 1e-3
    res = {'arms': arms, 'dTw_W0': dTw_w0, 'dTw_2W0': dTw_2w0,
           'seed_gap_chi1': tw_gap, 'locked': bool(locked), 'pass': bool(locked)}
    print(f"  dTw(chi=1) at W0 = {dTw_w0:+.5f}, at 2W0 = {dTw_2w0:+.5f}")
    print(f"  |Tw_end(2W0) - Tw_end(W0)| at chi=1 = {tw_gap:.4f} "
          f"-> {'LOCKED (seed-independent)' if locked else 'no lock: Tw tracks the seed'}")
    with open(f"{outdir}/test4.json", "w") as f:
        json.dump(res, f, indent=1)
    return res


def bench(n_steps=200):
    print(f"=== benchmark: {n_steps} steps, twist arm, N={T.N} ===")
    solver = build_layer(DEVICE, chi_ax=1.0)
    ey_hat, ei_hat, u_hat = P.helix_init(solver, W0)
    t0 = time.time()
    for _ in range(n_steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
    dt = (time.time() - t0) / n_steps
    print(f"  {dt*1000:.1f} ms/step -> {1/dt:.0f} steps/s; "
          f"t=4 arm ~{4000*dt:.0f}s, t=40 arm ~{40000*dt:.0f}s")


def main():
    global DEVICE, ARM_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument('--tests', default='0,1,2')
    ap.add_argument('--bench', type=int, default=0)
    args = ap.parse_args()
    tests = [int(t) for t in args.tests.split(',')]

    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {DEVICE}  N={T.N}  lam={T.LAM}  dt={T.DT}  gate='five'  "
          f"W0={W0:.4f} rad/cell")
    print(f"Component/sign: {COMPONENT_NOTE}")

    if args.bench:
        bench(args.bench)
        torch.cuda.synchronize()   # ROCm teardown deadlocks on pending work
        return

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_chi_axial_ramp"
    os.makedirs(rdir, exist_ok=True)
    ARM_DIR = rdir
    results = {'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT, 'W0': W0,
                        't4': STEPS_T4 * T.DT, 't40': STEPS_T40 * T.DT,
                        'gate_model': 'five', 'device': str(DEVICE),
                        'component': COMPONENT_NOTE, 'tests': tests}}
    if 0 in tests:
        results['test0'] = test0_component(rdir)
    if 1 in tests:
        results['test1'] = test1_bitforbit(rdir)
    if 2 in tests:
        results['test2'] = test2_mirror(rdir)
    if 3 in tests:
        results['test3'] = test3_ramp(rdir)
    if 4 in tests:
        results['test4'] = test4_lock(rdir)

    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults: {rdir}/results.json")
    torch.cuda.synchronize()   # ROCm teardown deadlocks on pending work


if __name__ == "__main__":
    try:
        main()
    finally:
        torch.cuda.synchronize()   # ROCm teardown deadlocks on pending work
