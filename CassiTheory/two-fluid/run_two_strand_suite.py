#!/usr/bin/env python3
"""Two-strand Stage-0 suite: TS1–TS5 PDE gates at the lock timescale.

Run:  python two-fluid/run_two_strand_suite.py

Follow-up research wave for `hypotheses/two-strand-five-channel-matter-organization.md`
(TS1–TS5) and `consciousness/two-strand-qi-neuroscience.md` (NS1–NS4).  The
committed baseline `two-fluid/run_two_strand_probe.py` (commit 315a425,
t = 4 = 0.2/lambda characterization window) is imported read-only and
extended to the lock timescale t = 40 = 2/lambda (long-window discipline:
churning-gate suite, 2026-08-04 — 1/lambda is the conversion timescale,
lock claims require t >= 2/lambda).  Fresh solver per arm (rk2_step mutates
solver state: scale factor, smoothed Hubble rate, q_mean); no solver edits;
no new model parameters — every analysis threshold below is a protocol
constant, the same kind the baseline probe already uses.

Arms (all N = 48, lambda = 0.05, dt = 0.001, t = 40, gate 'five'):
  sep12  two-lobe pair at SEP = 12 cells, E_RIDGE = 0.65 on both ridges
         (the committed baseline init) — TS1 lock persistence, TS4
         morphology, TS5 interlace record, TS3 control.
  sep6   pair at SEP = 6 cells  — TS2 separation series.
  sep3   pair at SEP = 3 cells  — TS2 (near-d0: one broad ridge).
  sep0   sep = 0: eps = 0 identically, the exact one-string reference — TS2.
  sym    SEP = 12, both ridges at 1.2 * E_RIDGE — TS3 symmetric mode.
  asym   SEP = 12, ridges at 1.2 / 0.8 * E_RIDGE — TS3 antisymmetric
         amplitude mode (the doc sec 6 gate-imbalance damping target:
         gamma_imb = lambda (1+phi) B, gamma(0) = 0.0764 at lambda = 0.1
         -> 0.0382 at lambda = 0.05, min B gives m(40)/m(0) < 0.7).

Verdicts (per test, in results.json):
  TS1: lock-timescale persistence — 'passed' (finite separation within the
       sec 3 band: back-20% mean of d in [0.25 d0, 1.2 d0], no merge),
       'null' (merged or separated at t = 40), 'unresolved' (tracking lost).
  TS2: centerline convergence as d -> 0 — residuals r(sep) vs the sep0
       one-string reference at t = 40 for q_mid, eps_mid, rho_mid
       (primary) and q_flank, A_plus (secondary); monotone approach
       r(3) < r(6) < r(12) on >= 3 of 5 and r(3) <= 0.5 r(12) on >= 2
       primaries is 'passed'; any primary divergence r(3) > r(12) is 'null'.
  TS3: symmetric/antisymmetric perturbation modes — the antisymmetric arm
       must (a) damp its amplitude imbalance m = (A1-A2)/(A1+A2) with
       m(40)/m(0) < 0.7 (doc sec 6 bound), (b) move d or DeltaTheta vs the
       sep12 control (relative-mode response), (c) leave the centerline
       fixed (max |Rc - Rc(0)| <= 1 cell).  Also records the antisymmetric
       channel signature c^- = (-0.236, +0.584, 0, +0.056, +0.002) cosine
       similarity at t = 0.  'null' if no response or the centerline moves.
  TS4: central-q morphology at lock timescale — anti-phase paired-sheet
       branch would show a field-measured central low-q node: q_mid <
       q_flank - 0.003 and a local minimum of q(x) at the midpoint.
       Central q at/above flank q is the in-phase central-antinode branch
       ('null', matching the t = 4 outcome); 'unresolved' if merged.
  TS5: interlace record — alpha := DeltaTheta (the doc sec 4.3
       operationalization: the measured near-in-phase state gives
       alpha ~ 0, an even multiple), joint projection order of
       {2 pi i / 5 + a alpha}; near-in-phase states must give a
       coincident-pentagon 5-fold joint projection; 10-fold only for odd
       interlace (alpha in {36, 108, ...} deg); irregular 10-fold (e.g.
       quadrature) is the explicit falsifier -> 'null'.

Output (runs/ is gitignored — commit the script only):
  runs/<rid>_two_strand_suite/run_<arm>.json   per-arm full histories
  runs/<rid>_two_strand_suite/results.json     meta + summaries + verdicts
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
import run_trauma_wake_lock as T

# ── t=0 ridge seed (near-d0 separation series) ──────────────────────────
# The baseline tracker finds maxima of the rho x-profile.  At sep <= 6
# cells (SIG = 5) the two density ridges overlap into a single profile
# bump, so the tracker cannot resolve the constructed pair at t = 0 and
# reports one merged ridge (d_start = 0, both strands at the midpoint),
# even though the anti-phase eps lobes sit at the constructed centers.
# Seed only the first measurement with the constructed centers; every
# later record uses the baseline tracker unchanged, so the evolution and
# all t > 0 records are bit-identical to the unseeded run.
_orig_track_ridges = P.track_ridges


def _track_ridges_seeded(rho_prof, centers, prev):
    ridges, merged = _orig_track_ridges(rho_prof, centers, prev)
    if merged and prev is None and len(centers) == 2:
        return list(centers), False
    return ridges, merged


P.track_ridges = _track_ridges_seeded

# ── Protocol (lock timescale: t = 40 = 2/lambda) ─────────────────────────
T.LAM = 0.05
T.DT = 0.001
STEPS = 40000                # t = 40
REPORT = 100                 # 401 records per arm
SEP = 12                     # baseline pair separation (cells)
DELTA = 0.2                  # TS3 perturbation amplitude (mode amplitude,
                             # not a model parameter)

CHANNELS = ['Wood', 'Fire', 'Earth', 'Metal', 'Water']
SNAP_STEPS = (0, 4000, STEPS - 1)      # t = 0, 4, 40 profile snapshots

# TS3 doc-sec-6 antisymmetric channel signature (linearized, normalized)
C_MINUS = np.array([-0.236, +0.584, 0.0, +0.056, +0.002])


def two_lobe_init(solver, sep, amp1=P.E_RIDGE, amp2=P.E_RIDGE):
    """Baseline anti-phase transverse-mode init with per-ridge eps
    amplitudes.  eps = amp1*g1 - amp2*g2; defaults reproduce
    P.two_lobe_init exactly (eps = E_RIDGE (g1 - g2)).  sep = 0 gives the
    literal d -> 0 limit: eps = 0 identically, one density ridge."""
    N_ = solver.N
    dev = solver.device
    x = torch.arange(N_, dtype=torch.float64, device=dev)
    X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
    cx = N_ / 2.0
    c1, c2 = cx - sep / 2.0, cx + sep / 2.0
    g1 = torch.exp(-((X - c1) ** 2 + (Y - cx) ** 2 + (Z - cx) ** 2)
                   / (2.0 * P.SIG ** 2))
    g2 = torch.exp(-((X - c2) ** 2 + (Y - cx) ** 2 + (Z - cx) ** 2)
                   / (2.0 * P.SIG ** 2))
    rho = (1.0 + T.PHI_INV) * (1.0 + P.BETA * (g1 + g2))
    if amp1 == amp2:
        # bit-exact with the baseline probe's E_RIDGE * (g1 - g2)
        eps = amp1 * (g1 - g2)
    else:
        eps = amp1 * g1 - amp2 * g2
    ey = (T.PHI * rho + eps) / (1.0 + T.PHI)
    ei = (rho - eps) / (1.0 + T.PHI)
    ey = torch.clamp(ey, min=1e-3)
    ei = torch.clamp(ei, min=1e-3)
    u_hat = torch.zeros(3, N_, N_, N_, dtype=torch.complex128, device=dev)
    return torch.fft.fftn(ey), torch.fft.fftn(ei), u_hat


def run_case(solver, sep, tag, outdir, amp1=P.E_RIDGE, amp2=P.E_RIDGE):
    """Evolve one arm (fresh solver), recording diagnostics every REPORT
    steps.  The sep12 arm also snapshots q/eps/rho profiles along the
    ridge axis (x at y = z = N/2) at t = 0, 4, 40 for the TS4 node/antinode
    classification."""
    print(f"\n=== run: {tag} (sep={sep}, amp=({amp1:g},{amp2:g})) ===")
    ey_hat, ei_hat, u_hat = two_lobe_init(solver, sep, amp1, amp2)
    centers = ([solver.N / 2.0 - sep / 2.0, solver.N / 2.0 + sep / 2.0]
               if sep > 1e-6 else [solver.N / 2.0])
    prev = None
    t0 = time.time()
    hist = []
    floor_touch = 0
    for step in range(STEPS):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step % REPORT == 0 or step == STEPS - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            rho_prof = (ey + ei).sum(dim=(1, 2)).cpu().numpy()
            d = P.measure_strands(solver, ey, ei, rho_prof, centers, prev)
            prev = ([d['x1'], d['x2']] if not d['merged'] else [d['x1']])
            d.update({'step': step, 't': step * T.DT})
            if d['ey_min'] < 1.01e-3 or d['ei_min'] < 1.01e-3:
                floor_touch += 1
            if step in SNAP_STEPS:
                q = T.channel_openness(ey, ei)[1]
                cy = cz = solver.N // 2
                eps_f = ey - T.PHI * ei
                d['q_prof'] = q[:, cy, cz].cpu().numpy().tolist()
                d['eps_prof'] = eps_f[:, cy, cz].cpu().numpy().tolist()
                d['rho_prof_ax'] = (ey + ei)[:, cy, cz].cpu().numpy().tolist()
            hist.append(d)
            if step % (10 * REPORT) == 0 or step == STEPS - 1:
                s0 = d['strands'][0]
                s1 = (d['strands'][1] if not d['merged'] else d['strands'][0])
                print(f"  t={step*T.DT:5.1f} | d={d['d']:6.3f} "
                      f"Rc={d['Rc']:6.2f} | dth={d['delta_theta']:+6.3f} "
                      f"| A=[{s0['A']:.3f},{s1['A']:.3f}] "
                      f"q=[{s0['q']:.3f},{s1['q']:.3f}] "
                      f"| dom=[{CHANNELS[s0['dominant']][0]},"
                      f"{CHANNELS[s1['dominant']][0]}] {d['sheng_ke']} "
                      f"| q_mid={d['q_mid']:.3f} q_flank={d['q_flank']:.3f} "
                      f"| ey_min={d['ey_min']:.4f} ei_min={d['ei_min']:.4f}")
    elapsed = time.time() - t0
    print(f"  [{tag}] {STEPS} steps in {elapsed:.1f}s "
          f"(floor touches: {floor_touch})")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'sep': sep, 'amp1': amp1, 'amp2': amp2,
                       'hist': hist}, f, indent=1)
    return hist, {'elapsed': elapsed, 'floor_touch': floor_touch,
                  'a_end': float(solver.a), 'H_end': float(solver.H)}


# ── Test-level analysis (all read-only on the histories) ─────────────────

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
    transitions = sum(1 for a, b in zip(h[:-1], h[1:])
                      if (a['strands'][0]['dominant'] !=
                          b['strands'][0]['dominant']) or
                      (not a['merged'] and not b['merged'] and
                       a['strands'][1]['dominant'] !=
                       b['strands'][1]['dominant']))
    dth0, dth4, dth_end = (h[0]['delta_theta'],
                           h[min(range(len(h)), key=lambda i: abs(h[i]['t'] - 4.0))]
                           ['delta_theta'], last['delta_theta'])
    return {
        'ns1': ns1, 'd_start': d0, 'd_end': last['d'], 'd_back_mean': d_back,
        'd_max': max(d['d'] for d in h),
        'merged_at_end': bool(last['merged']),
        'delta_theta_0': dth0, 'delta_theta_4': dth4,
        'delta_theta_end': dth_end,
        'A_plus_end': last['A_plus'], 'A_minus_end': last['A_minus'],
        'theta_xy_start': first['theta_xy'], 'theta_xy_end': last['theta_xy'],
        'Rc_drift': max(abs(d['Rc'] - first['Rc']) for d in h),
        'q_mid_start': first['q_mid'], 'q_mid_end': last['q_mid'],
        'q_flank_start': first['q_flank'], 'q_flank_end': last['q_flank'],
        'q_glob_start': first['q_glob'], 'q_glob_end': last['q_glob'],
        'eps_mid_end': last['eps_mid'], 'rho_mid_end': last['rho_mid'],
        'channel_transitions': transitions,
        'ey_min': min(d['ey_min'] for d in h),
        'ei_min': min(d['ei_min'] for d in h),
    }


def ts1_verdict(s):
    """TS1: NS1 at lock timescale — finite-separation state at t = 40."""
    if s['ns1'] == 'persisted':
        return 'passed', 'finite separation persists at t=40=2/lambda ' \
                         '(d_back in [0.25 d0, 1.2 d0])'
    if s['ns1'] == 'merged':
        return 'null', 'pair merged at lock timescale: no finite-separation ' \
                       'attractor under the existing PDE'
    if s['ns1'] == 'separated':
        return 'null', 'pair escaped (d_back > 1.2 d0): no bound state'
    return 'unresolved', 'ridge tracking lost; no relative coordinate'


def ts2_verdict(arms):
    """TS2: centerline convergence of the pair to the one-string reference
    as d -> 0, measured at t = 40 against the sep0 arm (eps = 0 by
    construction)."""
    obs = ['q_mid', 'eps_mid', 'rho_mid', 'q_flank', 'A_plus']
    primary = ['q_mid', 'eps_mid', 'rho_mid']
    res = {}
    c0 = {o: arms['sep0'][-1][o] for o in obs}
    for o in obs:
        res[o] = {s: abs(arms[s][-1][o] - c0[o]) for s in ('sep3', 'sep6',
                                                           'sep12')}
    res0 = {}
    c00 = {o: arms['sep0'][0][o] for o in obs}
    for o in obs:
        res0[o] = {s: abs(arms[s][0][o] - c00[o]) for s in ('sep3', 'sep6',
                                                            'sep12')}
    active = [o for o in obs if max(res[o].values()) > 1e-3]
    mono = sum(1 for o in active
               if res[o]['sep3'] < res[o]['sep6'] < res[o]['sep12'])
    half = sum(1 for o in primary if o in active and
               res[o]['sep3'] <= 0.5 * res[o]['sep12'])
    diverged = [o for o in primary if o in active and
                res[o]['sep3'] > res[o]['sep12']]
    if diverged:
        v = 'null'
        why = (f'centerline observable(s) {diverged} diverge from the '
               f'one-string reference as d -> 0: the pair is not an '
               f'extension of the one-string theory')
    elif mono >= 3 and half >= 2:
        v = 'passed'
        why = (f'centerline residuals approach the sep0 reference '
               f'monotonically ({mono}/5 observables monotone; {half}/3 '
               f'primaries at least halved at sep=3)')
    else:
        v = 'unresolved'
        why = (f'residuals neither monotone ({mono}/5) nor halved '
               f'({half}/3 primaries); degenerate or non-monotone series')
    return v, why, {'residuals_t40': res, 'residuals_t0': res0,
                    'active': active, 'monotone_count': mono,
                    'half_primary_count': half, 'diverged': diverged}


def ts3_verdict(h_ctrl, h_sym, h_asym):
    """TS3: symmetric/antisymmetric perturbation modes.  The antisymmetric
    arm must damp its amplitude imbalance (doc sec 6), move d or DeltaTheta
    vs the control, and leave the centerline fixed (NS3)."""
    def A(h, k):
        return [d['strands'][k]['A'] for d in h]

    def m_series(h):
        out = []
        for d in h:
            a1 = d['strands'][0]['A']
            a2 = (d['strands'][1]['A'] if not d['merged'] else a1)
            out.append((a1 - a2) / (a1 + a2 + 1e-30))
        return out

    m_ctrl, m_sym, m_asym = m_series(h_ctrl), m_series(h_sym), m_series(h_asym)
    ratio_asym = abs(m_asym[-1]) / max(abs(m_asym[0]), 1e-30)
    ratio_sym = abs(m_sym[-1]) / max(abs(m_sym[0]), 1e-30)
    # relative-mode response vs the control: max |d| and circular |dth| gap
    dd = max(abs(d['d'] - c['d']) for d, c in zip(h_asym, h_ctrl))
    dth = max(min(abs((d['delta_theta'] - c['delta_theta']) % (2 * np.pi)),
                  abs((c['delta_theta'] - d['delta_theta']) % (2 * np.pi)))
              for d, c in zip(h_asym, h_ctrl))
    # centerline drift
    drift_asym = max(abs(d['Rc'] - h_asym[0]['Rc']) for d in h_asym)
    drift_ctrl = max(abs(d['Rc'] - h_ctrl[0]['Rc']) for d in h_ctrl)
    # antisymmetric channel signature at t = 0 (doc sec 6, c^-)
    s0 = h_asym[0]['strands'][0]
    s1 = h_asym[0]['strands'][1]
    dc = (np.array(s0['conv_gate']) - np.array(s1['conv_gate']))
    norm = np.linalg.norm(dc)
    dc_n = dc / norm if norm > 1e-12 else np.zeros(5)
    cos_sim = float(np.dot(dc_n, C_MINUS) / np.linalg.norm(C_MINUS))

    damping = ratio_asym < 0.7
    response = dd >= 0.5 or dth >= 0.05
    fixed = drift_asym <= 1.0
    merged = h_asym[-1]['merged']
    if merged:
        v, why = 'unresolved', 'antisymmetric arm merged; no relative mode'
    elif not response:
        v, why = 'null', ('no relative-mode response: d and DeltaTheta track '
                          'the control within noise (NS3 falsifier)')
    elif not fixed:
        v, why = 'null', (f'antisymmetric perturbation moved the centerline '
                          f'(drift {drift_asym:.2f} cells > 1.0): relative '
                          f'mode not centerline-fixed (NS3 falsifier)')
    elif not damping:
        v, why = 'null', (f'imbalance not damped: m(40)/m(0) = '
                          f'{ratio_asym:.2f} >= 0.7 (doc sec 6 bound failed)')
    else:
        v, why = 'passed', ('antisymmetric mode damps its imbalance '
                            f'(m(40)/m(0) = {ratio_asym:.2f} < 0.7), moves '
                            f'd/DeltaTheta at fixed centerline (drift '
                            f'{drift_asym:.2f} cells)')
    return v, why, {
        'm_ctrl_0': m_ctrl[0], 'm_ctrl_end': m_ctrl[-1],
        'm_sym_0': m_sym[0], 'm_sym_end': m_sym[-1],
        'm_asym_0': m_asym[0], 'm_asym_end': m_asym[-1],
        'ratio_asym': ratio_asym, 'ratio_sym': ratio_sym,
        'd_gap_max': dd, 'dth_gap_max': dth,
        'Rc_drift_asym': drift_asym, 'Rc_drift_ctrl': drift_ctrl,
        'c_minus_cos_sim': cos_sim, 'c_minus_recorded': dc_n.tolist(),
        'damping': damping, 'response': response, 'centerline_fixed': fixed,
    }


def ts4_verdict(s, last_prof):
    """TS4: central-q morphology at lock timescale (NS4 re-test, phase from
    fields).  Anti-phase paired-sheet branch: central low-q node between
    higher-q ridges, measured from the field."""
    q_mid, q_flank = s['q_mid_end'], s['q_flank_end']
    prof = last_prof['q_prof']
    mid = len(prof) // 2
    lo = prof[max(0, mid - 2):mid]
    hi = prof[mid + 1:min(len(prof), mid + 3)]
    local_min = len(lo) > 0 and len(hi) > 0 and \
        prof[mid] <= min(min(lo), min(hi)) - 0.003
    node = q_mid < q_flank - 0.003 and local_min
    if s['merged_at_end']:
        v, why = 'unresolved', 'pair merged; morphology question moot'
    elif node:
        v, why = 'passed', ('central low-q node between higher-q ridges at '
                            't = 40 (q_mid < q_flank - 0.003, field-measured '
                            'q(x) local min at the midpoint): anti-phase '
                            'paired-sheet morphology realized')
    else:
        v, why = 'null', ('central q at/above flank q at t = 40 '
                          f'(q_mid {q_mid:.4f} vs q_flank {q_flank:.4f}): '
                          'the in-phase central-antinode branch, not the '
                          'anti-phase paired-sheet morphology (matches the '
                          't = 4 null)')
    return v, why, {'q_mid_end': q_mid, 'q_flank_end': q_flank,
                    'local_min': local_min, 'q_prof_mid': prof[mid]}


def joint_order(alpha, tol=0.0873):
    """Distinct-cluster count of the joint vertex set
    {2 pi i / 5 + a alpha} mod 2 pi under circular tolerance `tol` (rad)."""
    verts = sorted((2 * np.pi * i / 5 + a * alpha) % (2 * np.pi)
                   for a in (0, 1) for i in range(5))
    gaps = []
    for k in range(len(verts)):
        nxt = verts[(k + 1) % len(verts)]
        gaps.append((nxt - verts[k]) % (2 * np.pi))
    return max(1, sum(1 for g in gaps if g >= tol))


def classify_joint(alpha):
    """Joint projection classification vs the decagon theorem (sec 4.3)."""
    n = joint_order(alpha)
    a_deg = float(np.degrees(alpha) % 360.0)
    circ = lambda x: min(abs((a_deg - x) % 360.0), abs((x - a_deg) % 360.0))
    if n <= 5:
        return '5-fold coincident (even interlace)', n
    d_odd = min(circ(x) for x in (36.0, 108.0, 180.0, 252.0, 324.0))
    if d_odd <= 5.0:
        return '10-fold regular decagon (odd interlace)', n
    return '10-fold irregular (interlace not quantized)', n


def ts5_verdict(h):
    """TS5: interlace record (DeltaTheta, alpha, joint projection order).
    alpha := DeltaTheta (the doc's operational proxy); the algebra predicts
    a coincident-pentagon 5-fold joint projection for near-in-phase states,
    10-fold only for odd interlace; quadrature is the explicit falsifier."""
    alphas = [d['delta_theta'] for d in h]
    classes = [classify_joint(a)[0] for a in alphas]
    end_class, end_n = classify_joint(alphas[-1])
    # occupied joint order: distinct channels with real support at t_end
    occ = set()
    for d in (h[-1],):
        for k in range(2 if not d['merged'] else 1):
            for c, f in enumerate(d['strands'][k]['phase_frac']):
                if f > 1e-3:
                    occ.add(c)
    merged = h[-1]['merged']
    if merged:
        v = 'unresolved'
        why = 'strands merged; no joint interlace record'
    elif end_class.startswith('5-fold'):
        v = 'passed'
        why = ('near-in-phase state gives the coincident-pentagon 5-fold '
               'joint projection (even interlace), as the algebra predicts')
    elif end_class.startswith('10-fold regular'):
        v = 'passed-odd'
        why = ('odd interlace realized: joint projection is the regular '
               'decagon (the conditional claim activates)')
    else:
        v = 'null'
        why = ('realized interlace violates odd-multiple quantization '
               '(10-fold irregular, e.g. quadrature): decagon theorem '
               'fails as embedding map (TS5 falsifier)')
    return v, why, {
        'delta_theta_0': alphas[0], 'delta_theta_end': alphas[-1],
        'alpha_end_deg': float(np.degrees(alphas[-1]) % 360.0),
        'joint_order_end': end_n, 'class_end': end_class,
        'classes': classes,
        'per_strand_order': 5,          # each strand's own pentagon lattice
        'occupied_joint_order': len(occ),
        'occupied_channels': sorted(occ),
    }


def reproduction_check(h_sep12):
    """The suite's sep12 arm passes through the published t = 4 baseline;
    check the numbers match the committed probe record (sec 3 of the
    hypothesis doc) on this machine."""
    at = min(h_sep12, key=lambda d: abs(d['t'] - 4.0))
    ref = {'d': 10.08, 'delta_theta': 0.227, 'q_mid': 0.7074,
           'q_flank': 0.7009, 'A_plus': 0.444, 'A_minus': 0.051,
           'eps_mid': -0.020, 'rho_mid': 2.078}
    tol = {'d': 0.05, 'delta_theta': 0.005, 'q_mid': 0.001, 'q_flank': 0.001,
           'A_plus': 0.005, 'A_minus': 0.005, 'eps_mid': 0.002,
           'rho_mid': 0.01}
    got = {'d': at['d'], 'delta_theta': at['delta_theta'],
           'q_mid': at['q_mid'], 'q_flank': at['q_flank'],
           'A_plus': at['A_plus'], 'A_minus': at['A_minus'],
           'eps_mid': at['eps_mid'], 'rho_mid': at['rho_mid']}
    ok = all(abs(got[k] - ref[k]) <= tol[k] for k in ref)
    return ok, got, ref, tol


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t={STEPS * T.DT}  "
          f"gate='five'  E_RIDGE={P.E_RIDGE}  BETA={P.BETA}  SIG={P.SIG}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_two_strand_suite"
    os.makedirs(rdir, exist_ok=True)

    arms = {}
    meta = {}
    # TS1/TS3-control/TS4/TS5 arm: baseline pair at lock timescale
    h, m = run_case(T.build_solver(device), SEP, 'sep12', rdir)
    arms['sep12'] = h
    meta['sep12'] = m
    # TS2 separation series
    for s in (6.0, 3.0, 0.0):
        tag = f"sep{int(s)}"
        h, m = run_case(T.build_solver(device), s, tag, rdir)
        arms[tag] = h
        meta[tag] = m
    # TS3 perturbation arms
    h, m = run_case(T.build_solver(device), SEP, 'sym', rdir,
                    amp1=P.E_RIDGE * (1.0 + DELTA),
                    amp2=P.E_RIDGE * (1.0 + DELTA))
    arms['sym'] = h
    meta['sym'] = m
    h, m = run_case(T.build_solver(device), SEP, 'asym', rdir,
                    amp1=P.E_RIDGE * (1.0 + DELTA),
                    amp2=P.E_RIDGE * (1.0 - DELTA))
    arms['asym'] = h
    meta['asym'] = m

    sums = {tag: arm_summary(h) for tag, h in arms.items()}

    # ── Verdicts ─────────────────────────────────────────────────────────
    ts1_v, ts1_why = ts1_verdict(sums['sep12'])
    ts2_v, ts2_why, ts2_d = ts2_verdict(arms)
    ts3_v, ts3_why, ts3_d = ts3_verdict(arms['sep12'], arms['sym'],
                                        arms['asym'])
    ts4_v, ts4_why, ts4_d = ts4_verdict(sums['sep12'], arms['sep12'][-1])
    ts5_v, ts5_why, ts5_d = ts5_verdict(arms['sep12'])
    repro_ok, repro_got, repro_ref, repro_tol = reproduction_check(
        arms['sep12'])

    results = {
        'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT, 'steps': STEPS,
                 't_end': STEPS * T.DT, 'gate_model': 'five (solver)',
                 'E_RIDGE': P.E_RIDGE, 'BETA': P.BETA, 'SIG': P.SIG,
                 'SEP': SEP, 'R_SITE': P.R_SITE, 'DELTA': DELTA,
                 'baseline': 'run_two_strand_probe.py @ 315a425 (t=4)',
                 'arms': meta,
                 'criteria': {
                     'TS1': 'persisted: back-20% mean d in [0.25 d0, 1.2 d0] '
                            'at t=40 (sec 3 bands)',
                     'TS2': 'monotone r(3)<r(6)<r(12) on >=3 of 5 '
                            'observables and r(3) <= 0.5 r(12) on >=2 '
                            'primaries; primary divergence -> null',
                     'TS3': 'm(40)/m(0) < 0.7 (sec 6 bound), d/DeltaTheta '
                            'response vs control, Rc drift <= 1 cell',
                     'TS4': 'q_mid < q_flank - 0.003 and q(x) local min at '
                            'midpoint, from fields, at t=40',
                     'TS5': 'joint order of {2pi i/5 + a*alpha}, alpha := '
                            'DeltaTheta, 5 deg tolerance; 10-fold regular '
                            'only for odd interlace; quadrature falsifies'}},
        'arms': sums,
        'reproduction_t4': {'ok': repro_ok, 'got': repro_got,
                            'published_ref': repro_ref, 'tol': repro_tol},
        'verdicts': {
            'TS1': {'test': 'NS1 at lock timescale (t >= 2/lambda = 40): '
                            'pair persistence',
                    'verdict': ts1_v, 'why': ts1_why},
            'TS2': {'test': 'NS2 extended: separation series {0,3,6,12} '
                            'cells, centerline convergence as d -> 0',
                    'verdict': ts2_v, 'why': ts2_why, 'data': ts2_d},
            'TS3': {'test': 'NS3: symmetric/antisymmetric perturbation '
                            'modes; antisymmetric mode moves (d, DeltaTheta) '
                            'at fixed centerline',
                    'verdict': ts3_v, 'why': ts3_why, 'data': ts3_d},
            'TS4': {'test': 'NS4 re-test at lock timescale, phase from '
                            'fields; central-low-q morphology',
                    'verdict': ts4_v, 'why': ts4_why, 'data': ts4_d},
            'TS5': {'test': 'Interlace record: (DeltaTheta, alpha, joint '
                            'projection order); 5-fold for near-in-phase, '
                            '10-fold only for odd interlace',
                    'verdict': ts5_v, 'why': ts5_why, 'data': ts5_d},
        },
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== TWO-STRAND SUITE VERDICTS (t=40, lock timescale) ===")
    for tag in ('sep12', 'sep6', 'sep3', 'sep0', 'sym', 'asym'):
        s = sums[tag]
        print(f"{tag:5s}: ns1={s['ns1']:>9s} d {s['d_start']:.2f}->"
              f"{s['d_end']:.2f} (back {s['d_back_mean']:.2f}) | "
              f"dth {s['delta_theta_0']:+.3f}->{s['delta_theta_end']:+.3f} "
              f"| A+= {s['A_plus_end']:.3f} A-= {s['A_minus_end']:.3f} | "
              f"q_mid {s['q_mid_start']:.3f}->{s['q_mid_end']:.3f} vs "
              f"q_flank {s['q_flank_start']:.3f}->{s['q_flank_end']:.3f} | "
              f"trans={s['channel_transitions']} | "
              f"Rc drift {s['Rc_drift']:.2f}")
    print(f"\nt=4 reproduction vs published baseline: "
          f"{'OK' if repro_ok else 'MISMATCH'}")
    for k, v in repro_got.items():
        print(f"  {k}: got {v:.4f} vs ref {repro_ref[k]:.4f} "
              f"(tol {repro_tol[k]})")
    for ts in ('TS1', 'TS2', 'TS3', 'TS4', 'TS5'):
        v = results['verdicts'][ts]
        print(f"\n{ts}: {v['verdict'].upper()} — {v['why']}")
    print(f"\nResults: {rdir}/results.json")


if __name__ == "__main__":
    main()
