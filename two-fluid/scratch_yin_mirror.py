#!/usr/bin/env python3
"""Yin-mirror scratch-layer suite: the steady negative-attractor branch.

Run:  python two-fluid/scratch_yin_mirror.py
Resume (run one missing arm, then recompute all verdicts from the
records in an existing run dir):
      python two-fluid/scratch_yin_mirror.py --resume <rid> [--only <arm>]

Audit outcome (theory lead, 2026-08-07): the canonical conversion pair
dt(eps) = -lam (1+phi) (1-q) eps drives eps = EY - phi*EI to 0, whose
Yang fraction is Pi/rho = phi^-3 > 0; a steady Pi < 0 state does not
exist under the canonical dynamics (every Pi < 0 state has eps < 0 and
dt(Pi) = -2 lam g eps > 0).  The only constant-free steady negative-
attractor state is the MIRROR manifold EY = phi^-1 EI (Pi/rho =
-phi^-3): the canonical attractor with field labels exchanged and the
linearized conversion rate scaled by phi^-1 (the conjugate branch).
The half-space sign-opposite conversion, conv = -lam (1-q) |EY - phi EI|,
has no interior fixed point: its steady state is a numerical-floor
artifact.  This suite measures all three claims with the smallest
scratch layer (one conversion-target replacement, zero new constants),
following the TwistChiAxialLayer pattern: super().rhs() verbatim when
the flag is off (bit-for-bit no-op by construction).

Layer (class MirrorBranchLayer, canonical solver imported read-only):
  mode 'none'   : canonical path, zero extra operations (T0).
  mode 'mirror' : conv = -lam (1-q) (EY - phi^-1 EI)   (mirror target).
  mode 'abs'    : conv = -lam (1-q) |EY - phi EI|       (half-space drive).

Arms (fresh solver per arm; N = 48, lam = 0.05, dt = 1e-3, gate 'five';
swapped two-lobe init as the yin-excess suite; t = 80 = 4/lambda for
the science arms, t = 50 for the canonical references -- the conjugate
comparisons need canonical records only to t = 80/phi = 49.4):
  canon_ysep12  canonical solver, sep = 12, t = 50  (T0/T2 references,
                 continuity vs the committed yin-excess record)
  none_ysep12   MirrorBranchLayer(mode='none'), sep = 12, t = 50 (T0)
  mirror_ysep12 mode='mirror', sep = 12, t = 80     (T1 pair, T2, T4)
  canon_ysep0   canonical solver, sep = 0,  t = 50  (T2 one-string ref)
  mirror_ysep0  mode='mirror', sep = 0,  t = 80     (T1/T2 one-string)
  abs_ysep12    mode='abs', sep = 12, t = 80        (T3 floor artifact)

Verdicts (results.json):
  T0 no-op       bit-exact: none_ysep12 == canon_ysep12 record-by-record
                 (every numeric leaf incl. per-strand telemetry)
  T1 mirror fp   interior fixed point near Pi/rho = -phi^-3 = -0.2361:
                 epsA = EY - phi^-1 EI -> 0 (|epsA| < 0.10 at t = 80),
                 canonical eps -> -rho/phi (rel residual < 1%),
                 Pi/rho in [-0.29, -0.19], min fields > 0.3, q_mid in
                 [0.62, 0.68] (five-gate at eps_norm ~ 1/4), H_end in
                 [0.04, 0.06] (the mirror is a conversion rest state but
                 not a Hubble rest state: H -> lambda(phi^-2 + phi^2)/3
                 = lam)
  T2 conjugate   (a) early-window gate-normalized rate ratio (exact at
                 t = 0): gamma_mirror/gamma_canon = 1/phi = 0.618 +- 20%
                 on [0, 10], pair epsA_strand[0] vs pair eps_mid (the
                 one-string epsA_mid is degenerate: the symmetric init
                 sits on the mirror manifold); (b) late-window
                 differential decay law d ln|eps|/dt = -lam (1+phi^-1)
                 (1-q) (mirror pair epsA_strand[0], [40, 80]) and
                 -lam (1+phi) (1-q) (canon one-string eps_mid,
                 [25, 50]) within 30%; (c) the gravity/H residual
                 budget reported (H, a, u_max, Rc drift)
  T3 abs drive   no interior fixed point: EY hits the 1e-3 floor by
                 t <= 25 and Pi/rho_glob < -0.95 at t_end (or NaN-abort
                 after floor contact) -- the clamp-sustained artifact
  T4 E1          mirror pair d(t): contraction early (attraction
                 sustained), diluted by the conversion-mode expansion
                 (H ~ 0.05 keeps a(t) ~ exp(0.05 t), force ~ 1/a);
                 bands: merged / contracting / plateau / separated; a
                 plateau with |rate| < 0.015 and d > 2 is the E1
                 candidate and requires the t = 160 extension
  T5 telemetry   mass drift <= 1e-11, zero floor touches (mirror arms),
                 no NaN, fresh solver per arm

Continuity (C1): canon_ysep12 and canon_ysep0 are compared
record-by-record against the committed yin-excess suite record
(runs/20260807_014428_two_strand_yin_excess) for t <= 40 at the
continuation's cross-process tolerance (dynamics keys <= 1e-4 abs,
component totals <= 1e-4 rel, total mass <= 1e-9 rel).

No parameter or prediction registry changes: no scratch coefficient is
adopted (the mirror target is the existing derived constant phi^-1 and
the abs arm is a documented drive).

Output (runs/ is gitignored -- commit the script only):
  runs/<rid>_two_strand_yin_mirror/run_<arm>.json   per-arm histories
  runs/<rid>_two_strand_yin_mirror/results.json     meta + verdicts
"""

import os
import sys
import json
import time
import math
from datetime import datetime

import numpy as np
import torch

torch.backends.cudnn.benchmark = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_two_strand_probe as P            # geometry + constants, read-only
import run_trauma_wake_lock as T            # build_solver + gate, read-only
import run_two_strand_yin_excess_suite as S  # init + measurement, read-only
from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI, PHI_INV

# ── Protocol (the yin-excess suite's, with t_end per arm) ────────────────
T.LAM = 0.05
T.DT = 0.001
REPORT = 100                 # one record per 0.1 t
SEP = 12                     # baseline pair separation (cells)
FLOOR = 1e-3                 # solver positivity clamp floor
FLOOR_TOUCH = 1.01e-3        # telemetry trigger (as in the suite)
T50 = 50000                  # t = 50: canonical reference arms
T80 = 80000                  # t = 80 = 4/lambda: science arms
SUITE_BASELINE = "runs/20260807_014428_two_strand_yin_excess"

# T1/T2 bands (derived in the module docstring and the audit)
T1_EPSA = 0.10               # |epsA_mid| or per-strand |epsA| at t_end
T1_EPS_REL = 0.01            # |eps + rho/phi| / |rho/phi| at the mirror
T1_PIRHO_LO, T1_PIRHO_HI = -0.29, -0.19   # near -phi^-3 = -0.2361
T1_Q_LO, T1_Q_HI = 0.62, 0.68          # five-gate q at eps_norm ~ 1/4
T1_H_LO, T1_H_HI = 0.04, 0.06          # H -> lambda = 0.05
T1_MIN_FIELD = 0.3           # interior: both fields far above the floor
T2_RATIO_LO, T2_RATIO_HI = 0.49, 0.74  # 1/phi = 0.618 +- 20%
T2_DIFF_ERR = 0.30           # differential decay law band (rel. err)
T2_EARLY = 10.0              # early-rate window
T2_A_WIN = (40.0, 80.0)      # mirror late window
T2_C_WIN = (25.0, 50.0)      # canon late window (t <= 50 arm)
T3_FLOOR_T = 25.0            # first floor touch must occur by t = 25
T3_PIRHO = -0.95             # Pi/rho_glob at t_end (floor-saturated)
T4_RATE_CONTRACT = 0.015     # |rate| above this is contraction
T5_MASS_DRIFT = 1.0e-11      # total-mass drift tolerance


class MirrorBranchLayer(ExpandingTwoFluid3DGPU):
    """ExpandingTwoFluid3DGPU + flagged conversion-target replacement.

    mode='none'  returns super().rhs() verbatim: the canonical path
                 executes with zero extra operations (bit-for-bit no-op
                 by construction, verified as T0).
    mode='mirror'  conv = -lam (1-q) (EY - phi^-1 EI): the conjugate
                 branch.  The gate (1-q) is untouched -- it stays the
                 direction-blind five-channel openness of the canonical
                 imbalance, so the layer replaces only the conversion
                 target, zero new constants.
    mode='abs'  conv = -lam (1-q) |EY - phi EI|: the half-space
                 sign-opposite conversion (anti-damping on eps < 0).
    """

    def __init__(self, *args, scratch_mode='none', **kwargs):
        super().__init__(*args, **kwargs)
        if scratch_mode not in ('none', 'mirror', 'abs'):
            raise ValueError(f"scratch_mode must be 'none'|'mirror'|'abs', "
                             f"got {scratch_mode!r}")
        self.scratch_mode = scratch_mode

    def rhs(self, u_hat, ey_hat, ei_hat):
        out = super().rhs(u_hat, ey_hat, ei_hat)
        if self.scratch_mode == 'none':
            return out
        rhs_u_hat, rhs_ey_hat, rhs_ei_hat = out
        ey = torch.fft.ifftn(ey_hat).real
        ei = torch.fft.ifftn(ei_hat).real
        eps = ey - PHI * ei
        _, one_minus_q = self.compute_q_field(ey, ei)   # active gate
        conv_canon = -self.lam * one_minus_q * eps
        if self.scratch_mode == 'mirror':
            conv_scratch = -self.lam * one_minus_q * (ey - PHI_INV * ei)
        else:  # 'abs'
            conv_scratch = -self.lam * one_minus_q * eps.abs()
        dconv_hat = torch.fft.fftn(conv_scratch - conv_canon) * self.dealias
        rhs_ey_hat = rhs_ey_hat + dconv_hat
        rhs_ei_hat = rhs_ei_hat - dconv_hat
        return rhs_u_hat, rhs_ey_hat, rhs_ei_hat


def build_canon(device):
    solver = T.build_solver(device)
    return solver


def build_scratch(device, mode):
    solver = MirrorBranchLayer(
        N=T.N, L=T.L, nu=T.NU, D=T.D, lam=T.LAM, chi=0.0,
        hubble_mode='conversion', cs2=0.0, qi_gate=True,
        qi_memory=False, device=device, scratch_mode=mode)
    solver.gate_model = 'five'
    return solver


def add_epsA(solver, ey, ei, out):
    """Mirror-imbalance telemetry: epsA = EY - phi^-1 EI per strand,
    at the midpoint ball, and globally (same masks as S.pi_telemetry)."""
    dev = solver.device
    epsA = ey - PHI_INV * ei
    cy = cz = solver.N / 2.0
    xg = torch.arange(solver.N, dtype=torch.float64, device=dev)
    Xg, Yg, Zg = torch.meshgrid(xg, xg, xg, indexing='ij')
    centers_xy = ([(out['x1'], out['y1']), (out['x2'], out['y2'])]
                  if not out['merged'] else [(out['x1'], out['y1'])])
    eA = []
    for (xk, yk) in centers_xy:
        dd = (Xg - xk) ** 2 + (Yg - yk) ** 2 + (Zg - cz) ** 2
        w = torch.exp(-dd / (2.0 * P.SIG ** 2)) * \
            (dd <= P.R_SITE ** 2).to(torch.float64)
        eA.append(float((epsA * w).sum() / w.sum()))
    if len(eA) == 1:
        eA = eA * 2
    mid_mask = P.ball_mask(solver.N, out['Rc'], cy, cz, P.MID_R, dev)
    out['epsA_strand'] = eA
    out['epsA_mid'] = float((epsA * mid_mask).sum() / mid_mask.sum())
    out['epsA_glob'] = float(epsA.mean())
    return out


def run_case(solver, sep, tag, t_end, outdir):
    """Evolve one arm (fresh solver), recording diagnostics every REPORT
    steps plus q/eps/epsA/pi/rho axial profiles at t = 0, 40, t_end.
    A copy of S.run_case with the epsA and u_max telemetry added; the
    measurement functions (S.measure_density, S.pi_telemetry) are used
    read-only."""
    print(f"\n=== run: {tag} (sep={sep}, t_end={t_end}, "
          f"mode={solver.scratch_mode if isinstance(solver, MirrorBranchLayer) else 'canonical'}) ===")
    ey_hat, ei_hat, u_hat = S.yin_excess_init(solver, sep)
    ey0 = torch.fft.ifftn(ey_hat).real
    ei0 = torch.fft.ifftn(ei_hat).real
    mass0 = {'ey': float(ey0.sum()), 'ei': float(ei0.sum()),
             'tot': float((ey0 + ei0).sum())}
    centers = ([solver.N / 2.0 - sep / 2.0, solver.N / 2.0 + sep / 2.0]
               if sep > 1e-6 else [solver.N / 2.0])
    prev = None
    t0 = time.time()
    hist = []
    floor_touch = 0
    nan_abort = None
    cy = cz = solver.N // 2
    snap_steps = tuple(sorted({0, 40000, t_end - 1}))
    for step in range(t_end):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step % REPORT == 0 or step == t_end - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            if bool(torch.isnan(ey).any()) or bool(torch.isnan(ei).any()):
                nan_abort = step
                print(f"  [{tag}] NaN in the fields at step {step} "
                      f"(t={step * T.DT:.3f}); aborting the arm")
                break
            u = [torch.fft.ifftn(u_hat[d]).real for d in range(3)]
            rho_prof = (ey + ei).sum(dim=(1, 2)).cpu().numpy()
            d = S.measure_density(solver, ey, ei, rho_prof, centers, prev)
            prev = ([d['x1'], d['x2']] if not d['merged'] else [d['x1']])
            S.pi_telemetry(solver, ey, ei, d)
            add_epsA(solver, ey, ei, d)
            d.update({'step': step, 't': step * T.DT,
                      'a': float(solver.a), 'H': float(solver.H),
                      'u_max': float(max(uu.abs().max() for uu in u))})
            if d['ey_min'] < FLOOR_TOUCH or d['ei_min'] < FLOOR_TOUCH:
                floor_touch += 1
            if step in snap_steps:
                q = T.channel_openness(ey, ei)[1]
                eps_f = ey - PHI * ei
                epsA_f = ey - PHI_INV * ei
                pi_f = ey - ei
                d['q_prof'] = q[:, cy, cz].cpu().numpy().tolist()
                d['eps_prof'] = eps_f[:, cy, cz].cpu().numpy().tolist()
                d['epsA_prof'] = epsA_f[:, cy, cz].cpu().numpy().tolist()
                d['pi_prof'] = pi_f[:, cy, cz].cpu().numpy().tolist()
                d['rho_prof_ax'] = (ey + ei)[:, cy, cz].cpu().numpy().tolist()
            hist.append(d)
            if step % (10 * REPORT) == 0 or step == t_end - 1:
                s0 = d['strands'][0]
                s1 = (d['strands'][1] if not d['merged'] else d['strands'][0])
                print(f"  t={step * T.DT:5.1f} | d={d['d']:6.3f} "
                      f"Rc={d['Rc']:6.2f} | dth={d['delta_theta']:+6.3f} "
                      f"| pi=[{d['pi_strand'][0]:+.3f},"
                      f"{d['pi_strand'][1]:+.3f}] "
                      f"| epsA=[{d['epsA_strand'][0]:+.3f},"
                      f"{d['epsA_strand'][1]:+.3f}] "
                      f"| q_mid={d['q_mid']:.3f} q_flank={d['q_flank']:.3f} "
                      f"| H={d['H']:.4f} a={d['a']:.3f} "
                      f"| ey_min={d['ey_min']:.4f} ei_min={d['ei_min']:.4f}")
    ey1 = torch.fft.ifftn(ey_hat).real
    ei1 = torch.fft.ifftn(ei_hat).real
    mass1 = {'ey': float(ey1.sum()), 'ei': float(ei1.sum()),
             'tot': float((ey1 + ei1).sum())}
    mass_drift = {k: abs(mass1[k] - mass0[k]) / abs(mass0[k])
                  for k in mass0}
    elapsed = time.time() - t0
    meta = {'elapsed': elapsed, 'floor_touch': floor_touch,
            'mass0': mass0, 'mass1': mass1, 'mass_drift': mass_drift,
            'a_end': float(solver.a), 'H_end': float(solver.H),
            'nan_abort': nan_abort}
    print(f"  [{tag}] {len(hist)} records in {elapsed:.1f}s "
          f"(floor touches: {floor_touch}, mass drift: "
          f"{mass_drift['tot']:.2e}, a_end: {meta['a_end']:.4f}, "
          f"H_end: {meta['H_end']:.4f})")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'sep': sep, 't_end': t_end,
                       'mode': (solver.scratch_mode
                                if isinstance(solver, MirrorBranchLayer)
                                else 'canonical'),
                       'hist': hist, 'meta': meta}, f, indent=1)
    return hist, meta


# ── Verdict machinery (read-only on the histories) ───────────────────────

def at_t(h, t_target):
    return min(h, key=lambda d: abs(d['t'] - t_target))


def arm_summary(h):
    first, last = h[0], h[-1]
    d0 = first['d']
    back = h[int(0.8 * len(h)):]
    d_back = float(np.mean([d['d'] for d in back]))
    if d0 < 1e-6:
        ns1 = 'reference'
    elif last['merged'] or d_back < 0.25 * d0:
        ns1 = 'merged'
    elif d_back > 1.2 * d0:
        ns1 = 'separated'
    else:
        ns1 = 'persisted'
    return {
        'ns1': ns1, 'd_start': d0, 'd_end': last['d'], 'd_back_mean': d_back,
        'd_max': max(d['d'] for d in h),
        'merged_at_end': bool(last['merged']),
        'delta_theta_0': first['delta_theta'],
        'delta_theta_end': last['delta_theta'],
        'pi_strand_0': first['pi_strand'],
        'pi_strand_end': last['pi_strand'],
        'epsA_strand_0': first['epsA_strand'],
        'epsA_strand_end': last['epsA_strand'],
        'epsA_mid_0': first['epsA_mid'],
        'epsA_mid_end': last['epsA_mid'],
        'eps_mid_0': first['eps_mid'],
        'eps_mid_end': last['eps_mid'],
        'rho_mid_0': first['rho_mid'],
        'rho_mid_end': last['rho_mid'],
        'q_mid_0': first['q_mid'],
        'q_mid_end': last['q_mid'],
        'q_glob_0': first['q_glob'],
        'q_glob_end': last['q_glob'],
        'pi_glob_end': last['pi_glob'],
        'Pi_tot_end': last['Pi_tot'],
        'rho_tot_end': last['ey_tot'] + last['ei_tot'],
        'ey_min': min(d['ey_min'] for d in h),
        'ei_min': min(d['ei_min'] for d in h),
        'H_0': first['H'], 'H_end': last['H'],
        'a_0': first['a'], 'a_end': last['a'],
        'u_max': max(d['u_max'] for d in h),
        'Rc_drift': max(abs(d['Rc'] - first['Rc']) for d in h),
        'merge_t': merge_time(h),
    }


def merge_time(h):
    for d in h[1:]:
        if d['merged'] or d['d'] < 2.0:
            return d['t']
    return None


def _num_leaves(v):
    """All numeric leaves of a record value (scalars, lists, and
    list-of-dict telemetry such as 'strands' are all compared)."""
    out = []
    if isinstance(v, dict):
        for x in v.values():
            out.extend(_num_leaves(x))
    elif isinstance(v, (list, tuple)):
        for x in v:
            out.extend(_num_leaves(x))
    elif isinstance(v, (int, float)):
        out.append(float(v))
    return out


def t0_verdict(h_none, h_canon):
    max_diff = 0.0
    worst_key = None
    if len(h_none) != len(h_canon):
        return {'verdict': 'mismatch', 'reason': 'record count differs',
                'n_none': len(h_none), 'n_canon': len(h_canon)}
    for d_n, d_c in zip(h_none, h_canon):
        for k in d_n:
            if k not in d_c:
                continue
            vn, vc = _num_leaves(d_n[k]), _num_leaves(d_c[k])
            if len(vn) != len(vc):
                dd = float('inf')
            else:
                dd = max((abs(a - b) for a, b in zip(vn, vc)),
                         default=0.0)
            if dd > max_diff:
                max_diff = dd
                worst_key = k
    return {'verdict': 'bit-exact' if max_diff == 0.0 else 'mismatch',
            'max_record_diff': max_diff, 'worst_key': worst_key,
            'n_records': len(h_none)}


def _eps_mirror_residual(h):
    """|eps_mid + rho_mid/phi| / |rho_mid/phi| at the arm end: the
    mirror manifold is eps = -rho/phi, so the fixed-point check is
    rho-relative (the attractor density is not known a priori)."""
    last = h[-1]
    target = -last['rho_mid'] / PHI
    return abs(last['eps_mid'] - target) / max(abs(target), 1e-30)


def t1_verdict(h0, h12):
    """Interior mirror fixed point: one-string and pair mirror arms."""
    s0, s12 = arm_summary(h0), arm_summary(h12)
    pirho0 = s0['Pi_tot_end'] / s0['rho_tot_end']
    pirho12 = s12['Pi_tot_end'] / s12['rho_tot_end']
    eps_res0 = _eps_mirror_residual(h0)
    checks = {
        'interior_min_field': min(s0['ey_min'], s0['ei_min'],
                                  s12['ey_min'], s12['ei_min']) > T1_MIN_FIELD,
        'epsA_small': (abs(s0['epsA_mid_end']) < T1_EPSA and
                       max(abs(e) for e in s12['epsA_strand_end']) < T1_EPSA),
        'eps_at_mirror': eps_res0 < T1_EPS_REL,
        'pirho_near_minus_phi3': (T1_PIRHO_LO < pirho0 < T1_PIRHO_HI and
                                  T1_PIRHO_LO < pirho12 < T1_PIRHO_HI),
        'q_mirror': T1_Q_LO < s0['q_mid_end'] < T1_Q_HI,
        'H_to_lambda': T1_H_LO < s0['H_end'] < T1_H_HI,
    }
    ok = all(checks.values())
    return {
        'verdict': 'interior mirror fixed point' if ok else 'not reached',
        'checks': checks,
        'one_string': {'epsA_mid_end': s0['epsA_mid_end'],
                       'eps_mid_end': s0['eps_mid_end'],
                       'eps_mirror_target': -h0[-1]['rho_mid'] / PHI,
                       'eps_rel_residual': eps_res0,
                       'rho_mid_end': s0['rho_mid_end'],
                       'Pi/rho_end': pirho0,
                       'q_mid_end': s0['q_mid_end'],
                       'H_end': s0['H_end'], 'a_end': s0['a_end'],
                       'min_fields': (s0['ey_min'], s0['ei_min'])},
        'pair': {'epsA_strand_end': s12['epsA_strand_end'],
                 'd_end': s12['d_end'],
                 'Pi/rho_end': pirho12,
                 'q_mid_end': s12['q_mid_end'],
                 'min_fields': (s12['ey_min'], s12['ei_min'])},
        'targets': {'Pi/rho': -PHI ** -3, 'epsA': 0.0,
                    'eps': '-rho/phi (rel residual < 1%)',
                    'q': 'five-gate at eps_norm ~ 1/4',
                    'H': T.LAM},
    }


def _slope(h, key, t_lo, t_hi):
    pts = [(d['t'], math.log(abs(d[key]) + 1e-30))
           for d in h if t_lo <= d['t'] <= t_hi and abs(d[key]) > 1e-9]
    if len(pts) < 3:
        return None
    t = np.array([p[0] for p in pts])
    y = np.array([p[1] for p in pts])
    return float(np.polyfit(t, y, 1)[0])


def _diff_decay_err(h, key, qkey, t_lo, t_hi, rate_pre, idx=None):
    """Relative error of d ln|v|/dt vs -rate_pre * (1-q) over the
    window (the linearized conversion law with the measured gate).
    idx selects one element of a list-valued key (per-strand epsA)."""
    errs = []
    for d0, d1 in zip(h, h[1:]):
        if not (t_lo <= d0['t'] < t_hi):
            continue
        dt = d1['t'] - d0['t']
        if dt <= 0:
            continue
        v0 = d0[key][idx] if idx is not None else d0[key]
        v1 = d1[key][idx] if idx is not None else d1[key]
        if abs(v0) < 1e-9 or abs(v1) < 1e-9:
            continue
        meas = (math.log(abs(v1) + 1e-30) -
                math.log(abs(v0) + 1e-30)) / dt
        pred = -rate_pre * (1.0 - d0[qkey])
        if abs(pred) > 1e-9:
            errs.append(abs(meas - pred) / abs(pred))
    return errs


def _qnorm_rate(h, key, idx, qkey, t_lo, t_hi, tol=1e-12):
    """Mean of (d ln|v|/dt)/(1 - q) over the window: the
    gate-normalized linearized conversion rate.  Used for the early
    conjugate ratio, where the mirror and canonical arms evolve their
    gates at different rates and the raw slopes are not comparable."""
    rates = []
    for d0, d1 in zip(h, h[1:]):
        if not (t_lo <= d0['t'] < t_hi):
            continue
        dt = d1['t'] - d0['t']
        if dt <= 0:
            continue
        v0 = d0[key][idx] if idx is not None else d0[key]
        v1 = d1[key][idx] if idx is not None else d1[key]
        if abs(v0) < tol or abs(v1) < tol:
            continue
        meas = (math.log(abs(v1) + 1e-30) -
                math.log(abs(v0) + 1e-30)) / dt
        if abs(1.0 - d0[qkey]) > 1e-9:
            rates.append(meas / (1.0 - d0[qkey]))
    return float(np.mean(rates)) if rates else None


def t2_verdict(hM0, hC0, hM12, hC12):
    """Conjugate identity: (a) early rate ratio 1/phi; (b) late
    differential decay law with the measured gate; (c) gravity/H
    residual budget.

    Observables: the one-string arm's epsA_mid is degenerate (the
    symmetric init lies on the mirror manifold to float precision), so
    (a) uses the pair arm's per-strand epsA and (b) uses the pair arm's
    per-strand epsA on [40, 80] and the one-string canon eps_mid on
    [25, 50]."""
    # (a) gate-normalized early rate ratio on the pair arms
    gA = _qnorm_rate(hM12, 'epsA_strand', 0, 'q_mid', 0.0, T2_EARLY)
    gC = _qnorm_rate(hC12, 'eps_mid', None, 'q_mid', 0.0, T2_EARLY)
    ratio = (gA / gC) if (gA is not None and gC is not None and gC != 0) else None
    ok_a = ratio is not None and T2_RATIO_LO < ratio < T2_RATIO_HI

    errsA = _diff_decay_err(hM12, 'epsA_strand', 'q_mid', *T2_A_WIN,
                            T.LAM * (1.0 + PHI_INV), idx=0)
    errsC = _diff_decay_err(hC0, 'eps_mid', 'q_mid', *T2_C_WIN,
                            T.LAM * (1.0 + PHI))
    meanA = float(np.mean(errsA)) if errsA else float('inf')
    meanC = float(np.mean(errsC)) if errsC else float('inf')
    ok_b = meanA < T2_DIFF_ERR and meanC < T2_DIFF_ERR

    # (c) gravity/H residual budget: mirror(t) vs canon(t/phi) on H, a,
    # u_max, Rc drift.  The declared residual is the conversion-mode
    # expansion: the mirror arm keeps r ~ phi^-1, so H stays ~ lambda and
    # a(t) ~ exp(lambda t), while the canonical arm relaxes to r = phi,
    # H -> H_empty, a grows slowly.
    resid = {'max_H_gap': 0.0, 'max_a_gap': 0.0, 'max_u_mirror': 0.0,
             'max_u_canon': 0.0, 'Rc_drift_mirror': 0.0,
             'Rc_drift_canon': 0.0}
    for dM in hM0:
        tc = dM['t'] / PHI
        dC = at_t(hC0, tc)
        resid['max_H_gap'] = max(resid['max_H_gap'],
                                 abs(dM['H'] - dC['H']))
        resid['max_a_gap'] = max(resid['max_a_gap'],
                                 abs(dM['a'] - dC['a']))
    resid['max_u_mirror'] = max(d['u_max'] for d in hM0)
    resid['max_u_canon'] = max(d['u_max'] for d in hC0)
    sM0, sC0 = arm_summary(hM0), arm_summary(hC0)
    resid['Rc_drift_mirror'] = sM0['Rc_drift']
    resid['Rc_drift_canon'] = sC0['Rc_drift']

    # Early-window pair comparison (conversion-dominated): epsA(t) vs
    # the canonical imbalance of the swapped pair at t/phi, t/phi <= 15.
    pair_errs = []
    for dM in hM12:
        tc = dM['t'] / PHI
        if tc > 15.0:
            break
        dC = at_t(hC12, tc)
        pair_errs.append(abs(dM['epsA_mid'] - dC['eps_mid']))
    pair_max = max(pair_errs) if pair_errs else float('inf')

    return {
        'verdict': 'conjugate' if (ok_a and ok_b) else 'not conjugate',
        'early_rate_ratio': {'mirror_qnorm_rate': gA,
                             'canon_qnorm_rate': gC,
                             'ratio': ratio, 'target': 1.0 / PHI,
                             'band': (T2_RATIO_LO, T2_RATIO_HI),
                             'observable': ('pair epsA_strand[0] vs pair '
                                            'eps_mid, gate-normalized, '
                                            '[0, 10]'),
                             'ok': ok_a},
        'late_decay_law': {'mirror_mean_rel_err': meanA,
                           'canon_mean_rel_err': meanC,
                           'band': T2_DIFF_ERR, 'ok': ok_b,
                           'mirror_observable': 'pair epsA_strand[0]',
                           'canon_observable': 'one-string eps_mid',
                           'mirror_window': list(T2_A_WIN),
                           'canon_window': list(T2_C_WIN)},
        'gravity_H_residual': resid,
        'pair_early_max_abs_err': pair_max,
        'one_string_epsA_mid': 'degenerate (~1e-13 at all t: the '
                               'symmetric one-string init sits on the '
                               'mirror manifold to float precision), '
                               'not a rate observable',
    }


def t3_verdict(h, meta):
    floor_t = None
    for d in h:
        if d['ey_min'] <= FLOOR_TOUCH:
            floor_t = d['t']
            break
    last = h[-1]
    pirho = last['Pi_tot'] / (last['ey_tot'] + last['ei_tot'])
    nan = meta['nan_abort']
    floor_ok = floor_t is not None and floor_t <= T3_FLOOR_T
    if nan is not None:
        ok = floor_ok
        verdict = ('floor artifact (clamp-sustained), NaN-abort at '
                   f"t={nan:.1f}") if floor_ok else ('NaN-abort before '
                                                     'floor contact')
    else:
        ok = floor_ok and pirho < T3_PIRHO
        verdict = ('floor artifact (clamp-sustained)'
                   if ok else 'unexpected interior state')
    return {
        'verdict': verdict, 'ok': ok,
        'first_floor_touch_t': floor_t,
        'Pi/rho_end': pirho, 'ey_min': min(d['ey_min'] for d in h),
        'ei_min': min(d['ei_min'] for d in h),
        'H_end': last['H'], 'a_end': last['a'],
        'nan_abort': nan, 'floor_touches': meta['floor_touch'],
        'd_end': last['d'], 'mass_drift': meta['mass_drift']['tot'],
    }


def t4_verdict(h):
    s = arm_summary(h)
    d0 = s['d_start']
    n = len(h)
    win = h[int(0.9 * n):]
    rate = (win[-1]['d'] - win[0]['d']) / (win[-1]['t'] - win[0]['t'])
    back = float(np.mean([d['d'] for d in win]))
    mt = merge_time(h)
    if mt is not None or back < 0.25 * d0:
        outcome = 'merged'
    elif rate > 0.01:
        outcome = 'separated'
    elif rate < -T4_RATE_CONTRACT:
        outcome = 'contracting'
    else:
        outcome = 'plateau'
    if outcome in ('merged', 'contracting'):
        e1 = 'null (no finite-d0 binding; sustained attraction ends in coalescence or unbounded contraction)'
    elif outcome == 'plateau':
        e1 = 'candidate: t = 160 extension required (dilution freeze vs binding force)'
    else:
        e1 = 'null (escape)'
    return {
        'outcome': outcome, 'rate_last10': rate,
        'd_start': d0, 'd_end': s['d_end'], 'd_back_mean': back,
        'merge_t': mt, 'merged_at_end': s['merged_at_end'],
        'pi_strand_0': s['pi_strand_0'], 'pi_strand_end': s['pi_strand_end'],
        'epsA_strand_0': s['epsA_strand_0'],
        'epsA_strand_end': s['epsA_strand_end'],
        'H_end': s['H_end'], 'a_end': s['a_end'],
        'E1': e1,
    }


def t5_verdict(meta, mirror_tags):
    out = {}
    for tag, m in meta.items():
        out[tag] = {'mass_drift_tot': m['mass_drift']['tot'],
                    'floor_touches': m['floor_touch'],
                    'nan_abort': m['nan_abort'],
                    'a_end': m['a_end'], 'H_end': m['H_end']}
    mirror_ok = all(out[t]['mass_drift_tot'] <= T5_MASS_DRIFT
                    and out[t]['floor_touches'] == 0
                    and out[t]['nan_abort'] is None for t in mirror_tags)
    all_ok = all(out[t]['mass_drift_tot'] <= T5_MASS_DRIFT
                 and out[t]['nan_abort'] is None for t in meta)
    return {'verdict': 'clean' if (mirror_ok and all_ok) else 'violation',
            'mirror_tags': list(mirror_tags), 'arms': out,
            'tolerance': T5_MASS_DRIFT}


def continuity(h, baseline_h):
    """Record-by-record match vs the committed yin-excess suite record
    for t <= 40 (the continuation's cross-process criteria: dynamics
    keys <= 1e-4 abs, component totals <= 1e-4 rel, total mass <= 1e-9
    rel)."""
    base = [d for d in baseline_h if d['t'] <= 40.0 + 1e-9]
    run = [d for d in h if d['t'] <= 40.0 + 1e-9]
    dyn_keys = ['d', 'Rc', 'delta_theta', 'A_plus', 'A_minus', 'q_mid',
                'q_flank', 'eps_mid', 'rho_mid', 'x1', 'x2', 'ey_min',
                'ei_min', 'q_glob', 'pi_mid', 'pi_glob', 'a', 'H']
    tot_keys = ['Pi_tot', 'ey_tot', 'ei_tot']
    diffs = {}
    for k in dyn_keys:
        if k not in run[0] or k not in base[0]:
            continue
        if isinstance(run[0][k], list):
            diffs[k] = max(abs(a - b)
                           for a, b in zip([d[k][0] for d in run],
                                           [d[k][0] for d in base]))
        else:
            diffs[k] = max(abs(d[k] - b[k]) for d, b in zip(run, base))
    tot_diffs = {}
    for k in tot_keys:
        if k not in run[0] or k not in base[0]:
            continue
        tot_diffs[k] = max(abs(d[k] - b[k]) / max(abs(b[k]), 1e-30)
                           for d, b in zip(run, base))
    tot = max(abs((d['ey_tot'] + d['ei_tot']) -
                  (b['ey_tot'] + b['ei_tot']))
              / max(abs(b['ey_tot'] + b['ei_tot']), 1e-30)
              for d, b in zip(run, base))
    dyn_ok = max(diffs.values(), default=0.0) <= 1e-4
    tot_ok = max(tot_diffs.values(), default=0.0) <= 1e-4
    mass_ok = tot <= 1e-9
    return {'verdict': 'passed' if (dyn_ok and tot_ok and mass_ok)
            else 'mismatch',
            'max_dynamics_diff': max(diffs.values(), default=0.0),
            'max_totals_rel': max(tot_diffs.values(), default=0.0),
            'totals_rel': tot_diffs,
            'max_tot_mass_rel': tot, 'n_run': len(run), 'n_base': len(base)}


def _json_safe(o):
    """Convert numpy scalars to native types for JSON (verdict math
    mixes torch/numpy floats with Python ints/bools)."""
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, (bool, int, float, str)) or o is None:
        return o
    return str(o)


def compute_verdicts(arms, meta, rdir, canon_records):
    sums = {tag: arm_summary(h) for tag, h in arms.items()}
    results = {
        'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT,
                 'gate_model': 'five (solver)',
                 'init': 'canonical two-lobe state with ey <-> ei '
                         'exchanged (Yin-excess init, as the suite)',
                 'layer': 'MirrorBranchLayer: mode none = canonical '
                          'passthrough; mirror = conv -lam(1-q)(EY - '
                          'phi^-1 EI); abs = conv -lam(1-q)|EY - phi EI|',
                 'arms': {tag: m for tag, m in meta.items()}},
        'arms': sums,
        'verdicts': {
            'T0_noop': t0_verdict(arms['none_ysep12'], arms['canon_ysep12']),
            'T1_mirror_fixed_point': t1_verdict(arms['mirror_ysep0'],
                                                arms['mirror_ysep12']),
            'T2_conjugate_identity': t2_verdict(arms['mirror_ysep0'],
                                                arms['canon_ysep0'],
                                                arms['mirror_ysep12'],
                                                arms['canon_ysep12']),
            'T3_abs_drive': t3_verdict(arms['abs_ysep12'],
                                       meta['abs_ysep12']),
            'T4_E1': t4_verdict(arms['mirror_ysep12']),
            'T5_telemetry': t5_verdict(meta, ('mirror_ysep0',
                                              'mirror_ysep12')),
            'C1_continuity': {
                'canon_ysep12': continuity(arms['canon_ysep12'],
                                           canon_records['ysep12']),
                'canon_ysep0': continuity(arms['canon_ysep0'],
                                          canon_records['ysep0']),
            },
        },
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(_json_safe(results), f, indent=2)
    return results


def main():
    argv = sys.argv[1:]
    resume = only = None
    if '--resume' in argv:
        resume = argv[argv.index('--resume') + 1]
    if '--only' in argv:
        only = argv[argv.index('--only') + 1]

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  dt={T.DT}  "
          f"gate='five'  init=swapped two-lobe  "
          f"t_canon={T50 * T.DT}  t_science={T80 * T.DT}")

    if resume:
        rid = resume
        rdir = f"runs/{rid}_two_strand_yin_mirror"
        print(f"[resume] run dir: {rdir}")
    else:
        rid = datetime.now().strftime("%Y%m%d_%H%M%S")
        rdir = f"runs/{rid}_two_strand_yin_mirror"
    os.makedirs(rdir, exist_ok=True)

    all_specs = [
        ('canon_ysep12', build_canon, SEP, T50),
        ('none_ysep12', lambda d: build_scratch(d, 'none'), SEP, T50),
        ('mirror_ysep12', lambda d: build_scratch(d, 'mirror'), SEP, T80),
        ('canon_ysep0', build_canon, 0.0, T50),
        ('mirror_ysep0', lambda d: build_scratch(d, 'mirror'), 0.0, T80),
        ('abs_ysep12', lambda d: build_scratch(d, 'abs'), SEP, T80),
    ]
    specs = all_specs
    if only:
        specs = [s for s in all_specs if s[0] == only]
        if not specs:
            raise SystemExit(f"unknown arm {only!r}; choose from "
                             f"canon_ysep12, none_ysep12, mirror_ysep12, "
                             f"canon_ysep0, mirror_ysep0, abs_ysep12")
    arms = {}
    meta = {}
    for tag, builder, sep, t_end in specs:
        fname = f"{rdir}/run_{tag}.json"
        if os.path.exists(fname):
            with open(fname) as f:
                r = json.load(f)
            arms[tag] = r['hist']
            meta[tag] = r['meta']
            print(f"[resume] loaded {tag} ({len(r['hist'])} records)")
            continue
        solver = builder(device)          # fresh solver per arm
        h, m = run_case(solver, sep, tag, t_end, rdir)
        arms[tag], meta[tag] = h, m
    for tag, builder, sep, t_end in all_specs:
        if tag in arms:
            continue
        with open(f"{rdir}/run_{tag}.json") as f:
            r = json.load(f)
        arms[tag] = r['hist']
        meta[tag] = r['meta']
        print(f"[resume] loaded {tag} ({len(r['hist'])} records)")

    # Committed suite records for the continuity check
    canon_records = {}
    for name, fname in (('ysep12', 'run_ysep12.json'),
                        ('ysep0', 'run_ysep0.json')):
        with open(f"{SUITE_BASELINE}/{fname}") as f:
            canon_records[name] = json.load(f)['hist']

    results = compute_verdicts(arms, meta, rdir, canon_records)

    print("\n=== YIN-MIRROR SCRATCH SUITE VERDICTS ===")
    for tag in ('canon_ysep12', 'none_ysep12', 'mirror_ysep12',
                'canon_ysep0', 'mirror_ysep0', 'abs_ysep12'):
        s = sums_local(arms)[tag]
        print(f"{tag:13s}: ns1={s['ns1']:>9s} d {s['d_start']:.2f}->"
              f"{s['d_end']:.2f} (back {s['d_back_mean']:.2f}) | "
              f"pi=[{s['pi_strand_0'][0]:+.3f},{s['pi_strand_0'][1]:+.3f}]"
              f"->[{s['pi_strand_end'][0]:+.3f},{s['pi_strand_end'][1]:+.3f}]"
              f" | epsA=[{s['epsA_strand_0'][0]:+.3f}->"
              f"{s['epsA_strand_end'][0]:+.3f}]"
              f" | eps_mid {s['eps_mid_0']:+.3f}->{s['eps_mid_end']:+.3f}"
              f" | q_mid {s['q_mid_0']:.3f}->{s['q_mid_end']:.3f} | "
              f"ey_min {s['ey_min']:.4f} ei_min {s['ei_min']:.4f} | "
              f"H_end {s['H_end']:.4f} a_end {s['a_end']:.3f} | "
              f"mass_drift {meta[tag]['mass_drift']['tot']:.2e}")
    v = results['verdicts']
    print(f"\nT0 no-op: {v['T0_noop']['verdict']} "
          f"(max diff {v['T0_noop']['max_record_diff']:.1e})")
    print(f"T1 mirror fixed point: {v['T1_mirror_fixed_point']['verdict']}")
    print(f"T2 conjugate: {v['T2_conjugate_identity']['verdict']} "
          f"(rate ratio {v['T2_conjugate_identity']['early_rate_ratio']['ratio']:.3f} "
          f"vs 1/phi = {1/PHI:.3f}; late-law rel err "
          f"{v['T2_conjugate_identity']['late_decay_law']['mirror_mean_rel_err']:.3f}/"
          f"{v['T2_conjugate_identity']['late_decay_law']['canon_mean_rel_err']:.3f})")
    print(f"T3 abs drive: {v['T3_abs_drive']['verdict']} "
          f"(first floor touch {v['T3_abs_drive']['first_floor_touch_t']}, "
          f"Pi/rho_end {v['T3_abs_drive']['Pi/rho_end']:+.3f})")
    print(f"T4 E1 (mirror pair): {v['T4_E1']['outcome']} "
          f"(rate {v['T4_E1']['rate_last10']:+.4f} cells/t, "
          f"merge_t {v['T4_E1']['merge_t']}, d {v['T4_E1']['d_start']:.2f}->"
          f"{v['T4_E1']['d_end']:.2f}) -- {v['T4_E1']['E1']}")
    print(f"T5 telemetry: {v['T5_telemetry']['verdict']}")
    print(f"C1 continuity: canon_ysep12 "
          f"{v['C1_continuity']['canon_ysep12']['verdict']} "
          f"(max dyn {v['C1_continuity']['canon_ysep12']['max_dynamics_diff']:.1e}), "
          f"canon_ysep0 {v['C1_continuity']['canon_ysep0']['verdict']} "
          f"(max dyn {v['C1_continuity']['canon_ysep0']['max_dynamics_diff']:.1e})")
    print(f"\nResults: {rdir}/results.json")
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def sums_local(arms):
    return {tag: arm_summary(h) for tag, h in arms.items()}


if __name__ == "__main__":
    main()
