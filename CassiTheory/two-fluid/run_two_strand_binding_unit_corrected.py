#!/usr/bin/env python3
"""Unit-corrected two-strand wake-binding suite: T1-T4 acceptance tests for
the E3 wake aggregation flux under the corrected length convention.

Run:  python two-fluid/run_two_strand_binding_unit_corrected.py
      python two-fluid/run_two_strand_binding_unit_corrected.py --tend 4
      python two-fluid/run_two_strand_binding_unit_corrected.py --calibrate

Scratch layer on the canonical solver (cassi_two_fluid_3d_gpu.py is never
edited; the layer subclasses the committed binding layer, which subclasses
ExpandingTwoFluid3DGPU):

UNIT AUDIT (director finding; `two-fluid/scratch_wake_grad_source.py`):
the committed binding suite (`run_two_strand_binding_suite.py`) forms the
wake operator factor (1 + ell^2 k^2) with ell = P.SIG = 5 CELLS while the
solver's k is in rad/L-units (k_1d = 2 pi fftfreq(N, d=dx), dx = L/N; with
L = 2 pi the box fundamental is k = 1.0 rad/L).  The product 5 cells *
rad/L is dimensionally inconsistent and over-diffusive by
(P.SIG/ELL_L)^2 = 58.4x: ell^2 k^2 = 25 k^2 retains ~4% of the box
fundamental and ~0.25% of the pair-scale modes (k ~ 4 rad/L), which is the
measured "transfer W_peak ~ 1.6e-2 S_peak".  fftn/ifftn are self-inverse,
so no ifftn normalization is at play; the suppression is the unit error in
ell.  The committed operator is also diagonally unstable at the box corner
modes: 1 - dt/tau (1 + 25 k^2) goes negative for k^2 > 1600 (corner modes
reach k^2 = 1728); the corrected operator stays >= 0.963.

This suite uses the unit-covariant length in the OPERATOR only:

    ELL_L = P.SIG * (L/N) = 0.6545 L-units   (the committed 5-cell length)

The source S_W = (1-q) eps^2 carries no length and is unchanged, and the
mass-like flux dE_a/dt \u2283 -chi_w div(E_a grad W) is unchanged.  All
acceptance criteria (T1-T4) are the committed suite's, so the question
"does the eps^2 binding null survive the unit correction?" is answered by
the same yardstick.

Wake field W (updated ONCE per rk2_step, after the clamp, from the final
clamped fields -- the IIR-memory discipline):
    S_W = (1-q) eps^2,   eps = EY - phi EI,  (1-q) from the solver's own
    'five' gate via compute_q_field (the stress_energy pattern)
    dW/dt = -W/tau_W + S_W/tau_W + (ELL_L^2/tau_W) laplacian(W)
    tau_W = 1/lam,  spectral update
    W_hat <- [W_hat (1 - dt/tau_W (1 + ELL_L^2 k^2))
              + (dt/tau_W) S_hat] * dealias

Aggregation flux (mass-like, both components, added in rhs after the
canonical gate/conv block):
    dE_a/dt  \u2283  -chi_w div(E_a grad W)        (a = Y, I)
    chi_w = 0: every hook is guarded, so the layer is bit-inert (T1).

COUPLING CALIBRATION (minimal bracket): the wake fixed point on the frozen
sep=12 init, W* = ifftn(S_hat * dealias / (1 + ELL_L^2 k^2)), defines the
static flux speed at the ridge centers, v = chi_w |grad W*| (cells/t per
unit chi_w).  chi* is set so that v at the ridges equals the measured
escape drift (~0.2 cells/t, the TS1 late-window rate, doc §3.3); the
bracket is the minimal (chi*/3, chi*, 3 chi*) triple.

Arms (fresh solver per arm, N=48, lam=0.05, dt=0.001, gate 'five';
t = 4 for the characterization window, t = 40 = 2/lambda for the
lock-timescale verdicts):
  ctrl    canonical ExpandingTwoFluid3DGPU, sep12 -- T1 control + committed
          baseline reproduction + T2 control
  u12_0   unit-corrected binding sep12, chi_w = 0      -- T1 bit-exact no-op
  u12_lo  unit-corrected binding sep12, chi_w = chi*/3 -- T2 (sub-critical)
  u12_*   unit-corrected binding sep12, chi_w = chi*   -- T2 + T4
  u12_hi  unit-corrected binding sep12, chi_w = 3 chi* -- T2
  u0_0    unit-corrected binding sep0,  chi_w = 0      -- T3 reference
  u0_1    unit-corrected binding sep0,  chi_w = chi*   -- T3 one-string

Verdicts (results.json): T1-T4 and TS1 exactly as in the committed suite.

No registries or parameter-inventory updates: the verdict is reconciled by
the director before any doctrine change (the layer is a scratch TEST of the
E3 mechanism, Hypothesized; E1 coefficients remain outputs to project).

Output (runs/ is gitignored -- commit the script only):
  runs/<rid>_binding_unit_corrected_t<t>/run_<arm>.json   per-arm histories
  runs/<rid>_binding_unit_corrected_t<t>/results.json     meta + verdicts
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
import run_two_strand_probe as P      # baseline probe, read-only
import run_two_strand_binding_suite as B   # committed suite (analysis
                                           # functions + layer base),
                                           # read-only
import cassi_two_fluid_3d_gpu as C    # canonical solver, read-only

# ── Protocol (lock timescale: t = 40 = 2/lambda) ─────────────────────────
T = B.T
LAM = 0.05
DT = 0.001
SEP = 12                     # baseline pair separation (cells)
V_ESCAPE = 0.2               # cells/t (TS1 late-window drift, doc §3.3)
BRACKET_FACTORS = (1.0 / 3.0, 1.0, 3.0)   # minimal bracket around chi*
DX = T.L / T.N               # 0.13090 L-units per cell
ELL_L = P.SIG * DX           # committed 5-cell length in L-units: 0.65450
OVER_DIFF = (P.SIG / ELL_L) ** 2   # 58.36x -- the committed operator excess
W_MAX_BOUND = 10.0           # T4 wake boundedness ceiling (committed)

CHANNELS = ['Wood', 'Fire', 'Earth', 'Metal', 'Water']


def tag_of(chi_w):
    """Arm tag for a coupling value: 1000.0 -> 'u12_1000', 260.3 -> 'u12_260.3'."""
    return f"u12_{'%.4g' % chi_w}"


def _round_chi(x):
    return float(round(x, 2))


def calibrate(solver):
    """Static flux/escape calibration on the frozen sep=12 init.

    Wake fixed point with the corrected operator,
        W* = ifftn(S_hat * dealias / (1 + ELL_L^2 k^2)),  S = (1-q) eps^2,
    defines the static flux speed at the ridge centers,
        v [cells/t] = chi_w * |grad W*|  (per-cell gradient),
    and chi* = V_ESCAPE / max|grad W*| at the ridges.  The gradient axis is
    verified against a central-difference check on the axial profile (the
    spectral 'kx' slot is the physical dim-2 slot in this solver; the ridge
    axis is physical dim 0).  Reports the W*/S transfer under both the
    corrected and the committed operator for the audit record.
    """
    ey_hat, ei_hat, _ = B.two_lobe_init(solver, SEP)
    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    eps = ey - C.PHI * ei
    rho = ey + ei
    _, one_minus_q = solver.compute_q_field(ey, ei)
    S = one_minus_q * eps * eps
    S_hat = torch.fft.fftn(S)

    W_hat = S_hat * solver.dealias / (1.0 + ELL_L * ELL_L * solver.k2)
    W = torch.fft.ifftn(W_hat).real
    W_hat_c = S_hat * solver.dealias / (1.0 + P.SIG * P.SIG * solver.k2)
    W_c = torch.fft.ifftn(W_hat_c).real   # committed (over-diffusive) op

    rho_ax = rho[:, solver.N // 2, solver.N // 2].cpu().numpy()
    W_ax = W[:, solver.N // 2, solver.N // 2].cpu().numpy()
    p = rho_ax
    pampl = (p - p.min()) / max(p.max() - p.min(), 1e-30)
    idx = np.where((pampl[1:-1] >= pampl[:-2]) &
                   (pampl[1:-1] >= pampl[2:]) &
                   (pampl[1:-1] > P.RIDGE_THRESH))[0] + 1
    ridges = []
    for i in idx:
        y0, y1, y2 = p[i - 1], p[i], p[i + 1]
        denom = y0 - 2.0 * y1 + y2
        d = 0.5 * (y0 - y2) / denom if abs(denom) > 1e-14 else 0.0
        ridges.append(i + (d if abs(d) <= 2.0 else 0.0))
    ridges = sorted(ridges)[:2]
    i1, i2 = int(round(ridges[0])), int(round(ridges[1]))

    gw = solver._grad(torch.fft.fftn(W))
    # The solver's k arrays are meshgrid(k1,k1,k1) with indexing='ij', so
    # the 'kz' slot (dim 0 of the grid) multiplies the dim-2 modes: the
    # physical-x gradient (the ridge axis) is _grad(...)[2], in per-L
    # units.  Per-cell = per-L * dx (verified against a 4th-order
    # central-difference on the axial profile).
    g_ridge = [float(gw[2][i1, solver.N // 2, solver.N // 2] * DX),
               float(gw[2][i2, solver.N // 2, solver.N // 2] * DX)]
    # dim-0 slot -- recorded for the axis audit (should be ~0 on-axis)
    g_dim0 = float(gw[0][i1, solver.N // 2, solver.N // 2] * DX)
    fd1 = (-W_ax[i1 + 2] + 8.0 * W_ax[i1 + 1] - 8.0 * W_ax[i1 - 1]
           + W_ax[i1 - 2]) / 12.0
    fd2 = (-W_ax[i2 + 2] + 8.0 * W_ax[i2 + 1] - 8.0 * W_ax[i2 - 1]
           + W_ax[i2 - 2]) / 12.0

    gw_c = solver._grad(torch.fft.fftn(W_c))   # committed operator
    g_committed = [float(gw_c[2][i1, solver.N // 2, solver.N // 2] * DX),
                   float(gw_c[2][i2, solver.N // 2, solver.N // 2] * DX)]

    gmax = max(abs(g) for g in g_ridge)
    chi_star = V_ESCAPE / gmax if gmax > 1e-30 else float('inf')
    bracket = sorted({_round_chi(chi_star * f) for f in BRACKET_FACTORS})
    if len(bracket) < 3:            # guard against rounding collisions
        bracket = sorted({round(chi_star * f, 3) for f in BRACKET_FACTORS})

    return {
        'DX': DX, 'ELL_L': ELL_L, 'over_diffusion_factor': OVER_DIFF,
        'ell_committed_cells': P.SIG,
        'k_fundamental_rad_per_L': 2.0 * np.pi / T.L,
        'k_pair_scale_rad_per_L': 2.0 * np.pi / (SEP * DX),
        'retention_fundamental_committed': 1.0 / (1.0 + P.SIG ** 2 *
                                                  (2.0 * np.pi / T.L) ** 2),
        'retention_fundamental_corrected': 1.0 / (1.0 + ELL_L ** 2 *
                                                  (2.0 * np.pi / T.L) ** 2),
        'retention_pair_committed': 1.0 / (1.0 + P.SIG ** 2 *
                                           (2.0 * np.pi / (SEP * DX)) ** 2),
        'retention_pair_corrected': 1.0 / (1.0 + ELL_L ** 2 *
                                           (2.0 * np.pi / (SEP * DX)) ** 2),
        'S_max': float(S.max()), 'W_max_corrected': float(W.max()),
        'W_peak_ratio_S_corrected': float(W.max() / S.max()),
        'W_peak_ratio_S_committed_op': float(W_c.max() / S.max()),
        'ridges': ridges,
        'gradW_cells_per_t_per_chi_ridge1': g_ridge[0],
        'gradW_cells_per_t_per_chi_ridge2': g_ridge[1],
        'gradW_committed_op_ridges_cells_per_t_per_chi': g_committed,
        'gradW_dim0_slot_ridge1_for_axis_audit': g_dim0,
        'fd4_check_ridge1': float(fd1), 'fd4_check_ridge2': float(fd2),
        'chi_star': chi_star, 'bracket': bracket,
        'bracket_factors': list(BRACKET_FACTORS),
        'v_escape_cells_per_t': V_ESCAPE,
        'axis_verified': (abs(g_ridge[0] - float(fd1)) <
                          2e-3 * max(abs(float(fd1)), 1e-30) and
                          abs(g_ridge[1] - float(fd2)) <
                          2e-3 * max(abs(float(fd2)), 1e-30)),
    }


# ── The scratch layer (canonical solver untouched) ───────────────────────

class UnitCorrectedBinding(B.BindingTwoFluid):
    """Committed binding layer with the unit-corrected wake length.

    Only the operator length changes: ELL_L = P.SIG * (L/N) L-units instead
    of P.SIG cells.  Source, flux, and all guards are the committed suite's.
    """

    def __init__(self, chi_w=0.0, ell=ELL_L, tau_w=None, *args, **kwargs):
        super().__init__(chi_w=chi_w, ell=ell, tau_w=tau_w, *args, **kwargs)


def build_canonical(device):
    return B.build_canonical(device)


def build_binding(device, chi_w, ell=ELL_L, tau_w=None):
    solver = UnitCorrectedBinding(
        N=B.T.N, L=B.T.L, nu=B.T.NU, D=B.T.D, lam=B.T.LAM, chi=0.0,
        hubble_mode='conversion', cs2=0.0, qi_gate=True, qi_memory=False,
        device=device, chi_w=chi_w, ell=ell, tau_w=tau_w)
    solver.gate_model = 'five'
    return solver


def run_case(builder, sep, tag, outdir, steps, report):
    """Evolve one arm (fresh solver), recording diagnostics every `report`
    steps plus the axial rho profile and box rho mean at every record
    (needed for the T2 two-hump persistence checkpoints)."""
    solver = builder()
    print(f"\n=== run: {tag} (sep={sep}, chi_w={getattr(solver, 'chi_w', 0.0)}) ===")
    ey_hat, ei_hat, u_hat = B.two_lobe_init(solver, sep)
    ey0 = torch.fft.ifftn(ey_hat).real
    ei0 = torch.fft.ifftn(ei_hat).real
    mass0 = float((ey0 + ei0).sum())
    centers = ([solver.N / 2.0 - sep / 2.0, solver.N / 2.0 + sep / 2.0]
               if sep > 1e-6 else [solver.N / 2.0])
    prev = None
    t0 = time.time()
    hist = []
    floor_touch = 0
    cy = cz = solver.N // 2
    nan_abort = None
    snap_steps = (0, min(4000, steps - 1), steps - 1)
    for step in range(steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, DT)
        if step % report == 0 or step == steps - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            if bool(torch.isnan(ey).any()) or bool(torch.isnan(ei).any()):
                nan_abort = step
                print(f"  [{tag}] NaN in the fields at step {step} "
                      f"(t={step * DT:.3f}); aborting the arm")
                break
            rho_prof = (ey + ei).sum(dim=(1, 2)).cpu().numpy()
            d = B.measure_strands_safe(solver, ey, ei, rho_prof, centers,
                                       prev)
            prev = ([d['x1'], d['x2']] if not d['merged'] else [d['x1']])
            d.update({'step': step, 't': step * DT,
                      'rho_prof_ax': (ey + ei)[:, cy, cz].cpu().numpy().tolist(),
                      'rho_mean': float((ey + ei).mean())})
            if d['ey_min'] < 1.01e-3 or d['ei_min'] < 1.01e-3:
                floor_touch += 1
            if step in snap_steps:
                q = B.T.channel_openness(ey, ei)[1]
                eps_f = ey - C.PHI * ei
                d['q_prof'] = q[:, cy, cz].cpu().numpy().tolist()
                d['eps_prof'] = eps_f[:, cy, cz].cpu().numpy().tolist()
            if getattr(solver, 'W', None) is not None:
                d['W_max'] = float(solver.W.max())
                d['W_mean'] = float(solver.W.mean())
            hist.append(d)
            if step % (10 * report) == 0 or step == steps - 1:
                s0 = d['strands'][0]
                s1 = (d['strands'][1] if not d['merged'] else d['strands'][0])
                wtxt = (f" | W_max={d['W_max']:.4f}" if 'W_max' in d else '')
                print(f"  t={step*DT:5.1f} | d={d['d']:6.3f} "
                      f"Rc={d['Rc']:6.2f} | dth={d['delta_theta']:+6.3f} "
                      f"| A=[{s0['A']:.3f},{s1['A']:.3f}] "
                      f"| q_mid={d['q_mid']:.3f} q_flank={d['q_flank']:.3f} "
                      f"| ey_min={d['ey_min']:.4f} ei_min={d['ei_min']:.4f}"
                      f"{wtxt}")
    ey1 = torch.fft.ifftn(ey_hat).real
    ei1 = torch.fft.ifftn(ei_hat).real
    mass1 = float((ey1 + ei1).sum())
    mass_drift = abs(mass1 - mass0) / mass0
    w_end = (float(solver.W.max())
             if getattr(solver, 'W', None) is not None else 0.0)
    grad_w_end = 0.0
    if getattr(solver, 'W', None) is not None:
        gw = solver._grad(torch.fft.fftn(solver.W))
        grad_w_end = float(max(g.cpu().abs().max() for g in gw))
    elapsed = time.time() - t0
    meta = {'elapsed': elapsed, 'floor_touch': floor_touch,
            'mass0': mass0, 'mass1': mass1, 'mass_drift': mass_drift,
            'W_max_end': w_end, 'grad_w_max_end': grad_w_end,
            'nan_abort': nan_abort}
    print(f"  [{tag}] {steps} steps in {elapsed:.1f}s "
          f"(floor touches: {floor_touch}, mass drift: {mass_drift:.2e}, "
          f"W_max_end: {w_end:.4f}, |gradW|_max_end: {grad_w_end:.4f})")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'sep': sep,
                       'chi_w': getattr(solver, 'chi_w', 0.0),
                       'hist': hist, 'meta': meta}, f, indent=1)
    return hist, meta, (u_hat, ey_hat, ei_hat), solver


def arm_defs(chi_star):
    lo, star, hi = _round_chi(chi_star * BRACKET_FACTORS[0]), \
        _round_chi(chi_star), _round_chi(chi_star * BRACKET_FACTORS[2])
    return [
        ('ctrl', 'canonical', SEP, 0.0),
        ('u12_0', 'binding', SEP, 0.0),
        (tag_of(lo), 'binding', SEP, lo),
        (tag_of(star), 'binding', SEP, star),
        (tag_of(hi), 'binding', SEP, hi),
        ('u0_0', 'binding', 0.0, 0.0),
        ('u0_1', 'binding', 0.0, star),
    ], star


def build_for(kind, device, chi_w):
    if kind == 'canonical':
        return build_canonical(device)
    return build_binding(device, chi_w)


def run_arms(rdir, arm_list, device, defs, steps, report):
    arms, meta, states = {}, {}, {}
    for spec in defs:
        tag = spec[0]
        if tag not in arm_list:
            continue
        kind, sep = spec[1], spec[2]
        chi_w = spec[3]
        h, m, st, _ = run_case(
            lambda: build_for(kind, device, chi_w), sep, tag, rdir,
            steps, report)
        torch.save({'u': [x.cpu() for x in st[0]],
                    'ey': st[1].cpu(), 'ei': st[2].cpu()},
                   f"{rdir}/state_{tag}.pt")
        arms[tag], meta[tag], states[tag] = h, m, st
    return arms, meta, states


def load_arms(rdir, arm_list):
    arms, meta, states = {}, {}, {}
    for tag in arm_list:
        with open(f"{rdir}/run_{tag}.json") as f:
            rec = json.load(f)
        arms[tag] = rec['hist']
        meta[tag] = rec['meta']
        st = torch.load(f"{rdir}/state_{tag}.pt", map_location='cpu')
        states[tag] = (st['u'], st['ey'], st['ei'])
    return arms, meta, states


def compute_verdicts(arms, meta, states, rdir, chi_star, calib, t_end, steps):
    defs, star = arm_defs(chi_star)
    required = {s[0] for s in defs}
    missing = sorted(required - set(arms))
    if missing:
        print(f"[verdicts skipped: arm subset lacks {missing}; "
              f"run the full arm set for T1-T4]")
        return None
    sums = {tag: B.arm_summary(h) for tag, h in arms.items()}

    t1_ok, t1_d = B.t1_verdict(arms['ctrl'], arms['u12_0'],
                               states['ctrl'], states['u12_0'])
    repro_ok, repro_got, repro_ref, repro_tol = \
        B.reproduction_check(arms['ctrl'])
    t2 = {}
    for spec in defs:
        tag = spec[0]
        if tag.startswith('u12_') and tag != 'u12_0':
            chi_w = spec[3]
            ok, d = B.t2_verdict(arms[tag], arms['ctrl'], chi_w)
            t2[tag] = {'verdict': 'passed' if ok else 'null',
                       'detail': d, 'ts1_outcome': B.ts1_outcome(d, sums[tag])}
    t3_ok, t3_d = B.t3_verdict(arms['u0_0'], arms['u0_1'],
                               states['u0_0'], states['u0_1'])
    star_tag = tag_of(star)
    w_series = [d.get('W_max', 0.0) for d in arms[star_tag]]
    w_has_nan = any(np.isnan(v) for v in w_series)
    t4_ok, t4_d = B.t4_verdict(meta[star_tag], meta['ctrl'], t2[star_tag],
                               sums[star_tag]['W_max_over_run'],
                               meta[star_tag]['grad_w_max_end'], w_has_nan)
    order = [s[0] for s in defs if s[0].startswith('u12_') and s[0] != 'u12_0']
    d40s = [t2[t]['detail']['d40'] for t in order]
    depths = [t2[t]['detail']['two_hump_t40_detail'].get('dip_depth')
              for t in order]
    mono_d = all(d40s[i] > d40s[i + 1] for i in range(len(d40s) - 1))
    mono_depth = all(depths[i] is not None and depths[i + 1] is not None
                     and depths[i] < depths[i + 1]
                     for i in range(len(depths) - 1))
    mono = mono_d and mono_depth

    results = {
        'meta': {'N': B.T.N, 'lam': B.T.LAM, 'dt': DT, 'steps': steps,
                 't_end': t_end, 'gate_model': 'five (solver)',
                 'E_RIDGE': P.E_RIDGE, 'BETA': P.BETA, 'SIG': P.SIG,
                 'SEP': SEP, 'R_SITE': P.R_SITE,
                 'CHI_STAR': star, 'CHI_BRACKET': [round(chi_star * f, 3)
                                                   for f in BRACKET_FACTORS],
                 'tau_w': 1.0 / B.T.LAM, 'ell_L': ELL_L,
                 'ell_committed_cells': P.SIG,
                 'over_diffusion_factor': OVER_DIFF,
                 'unit_finding': 'committed suite used ell = 5 cells '
                                 'against k in rad/L-units: over-diffusive '
                                 f'by {OVER_DIFF:.1f}x and diagonally '
                                 'unstable at corner modes; this suite uses '
                                 'ELL_L = SIG*(L/N) in the wake operator; '
                                 'the eps^2 source and the mass-like flux '
                                 'are unchanged',
                 'calibration': calib,
                 'layer': 'wake W: dW/dt = -W/tau + S_W/tau + '
                          '(ELL_L^2/tau) laplacian(W), '
                          'S_W = (1-q) eps^2; flux: '
                          'dE_a/dt \u2283 -chi_w div(E_a grad W)',
                 'arms': meta,
                 'criteria': {
                     'T1': 'chi_w=0 bit-exact vs canonical: max|dEY|=max|dEI|'
                           '=max|du|=0.0 at t=4 and t=40, full histories equal',
                     'T2': 'two-hump rho profile at t=40 (dip <= min(hL,hR) '
                           '- 0.01 rho_mean) persistent over t in [30,40]; '
                           'd(40) < d(20) - 0.3; d(t) <= d_ctrl(t) + 0.5 for '
                           't >= 20; TS1 band (back-20% mean in '
                           '[0.25 d0, 1.2 d0]); monotone-in-chi across the '
                           'calibrated bracket',
                     'T3': 'sep0 at chi_w=chi* == sep0 at chi_w=0 to <= 1e-20 '
                           '(max|eps| <= 1e-12)',
                     'T4': 'no floor touches, ey/ei >= 1.01e-3, mass drift '
                           '<= 1e-11, W bounded (max <= 10, no NaN), smooth'}},
        'arms': sums,
        'reproduction_t4': {'ok': repro_ok, 'got': repro_got,
                            'published_ref': repro_ref, 'tol': repro_tol},
        'verdicts': {
            'T1': {'test': 'bit-exact no-op at chi_w = 0 vs canonical',
                   'verdict': 'passed' if t1_ok else 'null', 'data': t1_d},
            'T2': {'test': 'monotone binding at finite coupling',
                   'arms': t2,
                   'monotone_in_chi': mono,
                   'monotone_in_chi_data': {'d40': d40s, 'dip_depth': depths,
                                            'd40_strict': mono_d,
                                            'depth_strict': mono_depth}},
            'T3': {'test': 'one-string recovery preservation',
                   'verdict': 'passed' if t3_ok else 'null', 'data': t3_d},
            'T4': {'test': 'no clamp pathologies at chi*',
                   'verdict': 'passed' if t4_ok else 'null', 'data': t4_d},
            'TS1_at_chistar': {'test': 'TS1 lock-timescale outcome at '
                                       f'chi_w = {star}',
                               'outcome': t2[star_tag]['ts1_outcome'],
                               'data': t2[star_tag]['detail']},
        },
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== UNIT-CORRECTED WAKE-BINDING SUITE VERDICTS "
          f"(t={t_end}, lock timescale) ===")
    for tag in sorted(sums):
        s = sums[tag]
        print(f"{tag:6s}: ns1={s['ns1']:>9s} d {s['d_start']:.2f}->"
              f"{s['d_end']:.2f} (back {s['d_back_mean']:.2f}) | "
              f"A+= {s['A_plus_end']:.3f} | q_mid {s['q_mid_end']:.3f} vs "
              f"q_flank {s['q_flank_end']:.3f} | "
              f"W_max {s['W_max_over_run']:.4f} | "
              f"ey_min {s['ey_min']:.4f}")
    print(f"\nt=4 reproduction vs published baseline: "
          f"{'OK' if repro_ok else 'MISMATCH'}")
    print(f"\nT1 (bit-exact no-op): {t1_d['max_du']:.3e} "
          f"{t1_d['max_dey']:.3e} {t1_d['max_dei']:.3e} "
          f"(max|du|, max|dEY|, max|dEI|) -> "
          f"{'PASSED' if t1_ok else 'NULL'}")
    chi_by_tag = {s[0]: s[3] for s in defs}
    for t in order:
        dd = t2[t]['detail']
        print(f"T2 {t} (chi={chi_by_tag[t]}): "
              f"ts1={t2[t]['ts1_outcome']:>9s} two_hump={dd['two_hump_t40']} "
              f"persist={dd['persistence_frac_30_40']:.2f} "
              f"d40={dd['d40']:.2f} d20={dd['d20']:.2f} "
              f"turn={dd['turnaround']} over_ctrl={dd['max_over_ctrl_t_ge_20']:.2f} "
              f"band={dd['ts1_band']} -> {t2[t]['verdict'].upper()}")
    print(f"T2 monotone-in-chi: d40 {[f'{v:.2f}' for v in d40s]} "
          f"dips {[f'{v:.4f}' if v is not None else '-' for v in depths]} "
          f"-> {'PASSED' if mono else 'NULL'}")
    print(f"\nT3 (one-string preservation): max|dEY| {t3_d['max_dey']:.3e} "
          f"max|eps| {t3_d['max_eps_end']:.3e} -> "
          f"{'PASSED' if t3_ok else 'NULL'}")
    print(f"T4 (clamp/W telemetry): floor {meta[star_tag]['floor_touch']} "
          f"mass_drift {meta[star_tag]['mass_drift']:.2e} "
          f"W_max {sums[star_tag]['W_max_over_run']:.4f} "
          f"gradW_end {meta[star_tag]['grad_w_max_end']:.4f} -> "
          f"{'PASSED' if t4_ok else 'NULL'}")
    print(f"\nTS1 at chi* = {star}: {t2[star_tag]['ts1_outcome'].upper()}")
    print(f"\nResults: {rdir}/results.json")
    return results


def main():
    mode = 'run'
    t_end = 40
    arm_list = None
    rdir = None
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == '--analyze':
            mode = 'analyze'
        elif argv[i] == '--calibrate':
            mode = 'calibrate'
        elif argv[i] == '--tend':
            t_end = float(argv[i + 1])
            i += 1
        elif argv[i] == '--arms':
            arm_list = argv[i + 1].split(',')
            i += 1
        elif argv[i] == '--rdir':
            rdir = argv[i + 1]
            i += 1
        i += 1
    steps = int(t_end / DT)
    report = 100
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    cal_solver = build_canonical(device)
    calib = calibrate(cal_solver)
    del cal_solver
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    print(f"\nDevice: {device}  N={B.T.N}  lam={B.T.LAM}  dt={DT}  "
          f"t={t_end}  gate='five'  E_RIDGE={P.E_RIDGE}  BETA={P.BETA}  "
          f"SIG={P.SIG}  SEP={SEP}")
    print(f"UNIT AUDIT: ell_committed = {P.SIG} cells vs k in rad/L -> "
          f"ELL_L = {ELL_L:.5f} L-units; over-diffusion "
          f"({P.SIG}/{ELL_L:.5f})^2 = {OVER_DIFF:.1f}x")
    print(f"Static eps^2 wake (corrected op): W/S = "
          f"{calib['W_peak_ratio_S_corrected']:.4f} "
          f"(committed op: {calib['W_peak_ratio_S_committed_op']:.4f}); "
          f"gradW at ridges = [{calib['gradW_cells_per_t_per_chi_ridge1']:+.5f},"
          f"{calib['gradW_cells_per_t_per_chi_ridge2']:+.5f}] cells/t per chi "
          f"(FD4 check [{calib['fd4_check_ridge1']:+.5f},"
          f"{calib['fd4_check_ridge2']:+.5f}], axis_verified="
          f"{calib['axis_verified']})")
    chi_star = calib['chi_star']
    print(f"chi* = {chi_star:.3f} (v_escape = {V_ESCAPE} cells/t); "
          f"bracket = {calib['bracket']}")

    if mode == 'calibrate':
        return

    defs, _ = arm_defs(chi_star)
    if arm_list is None:
        arm_list = [s[0] for s in defs]
    print(f"arms: {arm_list}")

    if rdir is None:
        rid = datetime.now().strftime("%Y%m%d_%H%M%S")
        rdir = f"runs/{rid}_binding_unit_corrected_t{int(t_end)}"
    os.makedirs(rdir, exist_ok=True)

    if mode == 'run':
        arms, meta, states = run_arms(rdir, arm_list, device, defs,
                                      steps, report)
    else:
        arms, meta, states = load_arms(rdir, arm_list)
    compute_verdicts(arms, meta, states, rdir, chi_star, calib, t_end, steps)
    if torch.cuda.is_available():
        torch.cuda.synchronize()   # ROCm teardown deadlocks on async work


if __name__ == "__main__":
    main()
