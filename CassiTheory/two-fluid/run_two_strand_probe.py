#!/usr/bin/env python3
"""Two-strand probe: channel-projected conversion traces of a two-lobe pair.

Run:  python two-fluid/run_two_strand_probe.py

Tests the PDE-testable targets of `consciousness/two-strand-qi-neuroscience.md`
sec 7 (NS1 bound pair, NS2 one-string recovery, NS4 phase-selected
morphology) with the smallest two-lobe initialization the solver supports.
The five-channel closure is `foundations/wu-xing-derivation.md`; the gate
formulas and sheng/ke cycle conventions are those of
`foundations/wu-xing-cycle-structure.md` and the solver's 'five' gate.

Init (no new model parameters, no solver edits): two Gaussian ridges of the
epsilon field, equal and opposite, on density ridges over the quiet
phi-equilibrium background.  With rho = (1+phi^-1)(1+beta(g1+g2)) and
eps = E(g1 - g2), the doublet is recovered per cell by
    ey = (phi rho + eps)/(1+phi),   ei = (rho - eps)/(1+phi).
This is exactly the anti-phase transverse mode of the two-strand doc sec 3.2:
an eps-node at the midpoint, two flanking eps-ridges, same local Qi profile
translated (equal |eps| = E_RIDGE at the cores, equal q).  The relative
Yang-Yin phase DeltaTheta is measured from the fields, not assumed.

Arms (focused protocol, no sweeps; fresh solver per arm):
  two_lobe   the pair at separation SEP = 12 cells (t = 4, lambda = 0.05,
             N = 48, gate_model 'five'; the churning-gate regime)
  d0         the literal d -> 0 limit: both ridges at the same centerline
             (sep = 0).  Then eps = 0 identically (anti-phase cancellation)
             and rho is a single density ridge: the one-string reference of
             NS2.  Same total ridge content, same protocol.

Channel projection of the conversion source (the decisive diagnostic):
  conv = -lam (1-q) eps,  with (1-q) = sum_c eta_c ch_open_c, so the
  c-channel's share of the conversion source is
      conv_c = -lam eta_c ch_open_c eps        (gate-weighted projection)
  ch_open/q are sourced from the solver's own 'five' gate formula, replicated
  read-only by run_trauma_wake_lock.channel_openness (never fed back into the
  PDE).  A second, diagnostic-only projection partitions conv by the cell's
  field angle theta = atan2(ei, ey) onto the five pentagon channels
  (phase-angle projection; used only for measurement, no dynamic effect).
  Representability bound (run_trauma_phase_channels.py): the 1e-3 positivity
  clamp pins atan2(ei, ey) to the first quadrant, so only Wood (0 deg) and
  Fire (72 deg) are reachable in the field angle; DeltaTheta here is bounded
  by that arc and is reported as measured.

Per-strand and pair observables at every report:
  ridge positions from the rho x-profile (parabolic refinement); d = |R1-R2|,
  Rc = (R1+R2)/2, transverse orientation theta_xy and its temporal rate (the
  ball-lobe twist proxy; the doc's longitudinal Omega = d_theta/d_sigma needs
  a filament init and is out of scope here),
  per-strand trace amplitude A_k = <|eps|> (ridge-profile-weighted: the
  strand's own Gaussian at the tracked position, truncated at R_SITE),
  signed eps_k, q_k, sigma_r_k,
  doublet angle theta_k, plus/minus collective traces |Z+/-| = |z1 +/- z2|/2,
  per-strand ch_open[5] and the two channel-projected conversion vectors
  conv_gate[5] and conv_phase[5], dominant phase channel and its sheng/ke
  relation to the other strand's channel (sheng = +1, ke = +2 mod 5),
  central q (ball radius 2 at the midpoint) vs flank q (NS4 morphology),
  ey/ei floor minima over the strand union (clamp diagnostics).

Verdicts (stated in results.json):
  NS1: d(t_end)/d0 -- merged (< 0.25 d0 or one ridge lost), separated
       (> 1.2 d0), or persisted at finite d (within the band).
  NS2: the d0 arm is the one-string reference; its centerline observables
       (q, eps, rho at the ridge center) are compared against the pair's
       midpoint values at t_end -- the d -> 0 recovery check.
  NS4: central q vs mean flank q at t = 0 and t = 4, measured from the field
       (no morphological assumption).
  Channel traces: per-strand conversion vectors at t = 0, 2, 4 with the
  dominant-channel sheng/ke relation series and its transition count.

Timescale caveat: t = 4 = 0.2/lambda is a characterization window (the
coherence-budget regime).  Lock claims need t >= 2/lambda (40 s) per the
churning-gate verdict logic; persistence here is reported as a first-pass
classification, not a lock.

Usage:
    python two-fluid/run_two_strand_probe.py
Output (runs/ is gitignored -- commit the script only):
    runs/<rid>_two_strand/run_two_lobe.json   full history, sep = 12
    runs/<rid>_two_strand/run_d0.json         full history, sep = 0 (d->0)
    runs/<rid>_two_strand/results.json        meta + summaries + verdict
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
import run_trauma_wake_lock as T

# ── Protocol (coherence-budget regime: lambda = 0.05, t = 4, N = 48) ──────
T.LAM = 0.05
T.DT = 0.001
T.REPORT = 50
STEPS = 4000                 # t = 4 = 0.2/lambda (characterization window)

CHANNELS = ['Wood', 'Fire', 'Earth', 'Metal', 'Water']

# ── Two-lobe pair geometry (house two-bubble convention) ──────────────────
SIG = 5.0                    # ridge Gaussian sigma in cells
SEP = 12                     # center separation in cells (N//4)
E_RIDGE = 0.65               # per-ridge |eps| at core (house AMP range)
BETA = 0.3                   # density ridge: rho_core = (1+phi^-1)(1+beta)
R_SITE = 6.0                 # per-strand measurement ball radius (cells)
MID_R = 2.0                  # central-region ball radius (cells)
RIDGE_THRESH = 0.15          # ridge detection floor (fraction of profile amp)


def two_lobe_init(solver, sep):
    """Two-lobe coherent state: rho = (1+phi^-1)(1+beta(g1+g2)),
    eps = E_RIDGE (g1 - g2).  eps has a node at the midpoint (doc sec 3.2
    anti-phase transverse mode); the Yang-Yin doublet follows per cell from
    (rho, eps).  sep = 0 gives the literal d -> 0 limit: eps = 0 everywhere,
    a single density ridge at 1 + 2 beta g."""
    N_ = solver.N
    dev = solver.device
    x = torch.arange(N_, dtype=torch.float64, device=dev)
    X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
    cx = N_ / 2.0
    c1, c2 = cx - sep / 2.0, cx + sep / 2.0
    g1 = torch.exp(-((X - c1) ** 2 + (Y - cx) ** 2 + (Z - cx) ** 2)
                   / (2.0 * SIG ** 2))
    g2 = torch.exp(-((X - c2) ** 2 + (Y - cx) ** 2 + (Z - cx) ** 2)
                   / (2.0 * SIG ** 2))
    rho = (1.0 + T.PHI_INV) * (1.0 + BETA * (g1 + g2))
    eps = E_RIDGE * (g1 - g2)
    ey = (T.PHI * rho + eps) / (1.0 + T.PHI)
    ei = (rho - eps) / (1.0 + T.PHI)
    ey = torch.clamp(ey, min=1e-3)
    ei = torch.clamp(ei, min=1e-3)
    u_hat = torch.zeros(3, N_, N_, N_, dtype=torch.complex128, device=dev)
    return torch.fft.fftn(ey), torch.fft.fftn(ei), u_hat


def ball_mask(N_, cx, cy, cz, radius, device):
    """Ball of `radius` cells around (cx, cy, cz) with periodic wrapping
    (same periodic-distance formula as run_trauma_wake_lock.site_mask)."""
    x = torch.arange(N_, dtype=torch.float64, device=device)
    dx = torch.minimum((x - cx) % N_, (cx - x) % N_)
    d2 = dx.unsqueeze(1).unsqueeze(2) ** 2 + \
         dx.unsqueeze(0).unsqueeze(2) ** 2 + \
         dx.unsqueeze(0).unsqueeze(1) ** 2
    return (torch.sqrt(d2) <= radius).to(torch.float64)


def _refine_1d(p, i):
    """Parabolic sub-grid refinement of a 1-D profile maximum at index i."""
    y0, y1, y2 = p[i - 1], p[i], p[i + 1]
    denom = y0 - 2.0 * y1 + y2
    if abs(denom) < 1e-14:
        return float(i)
    return i + 0.5 * (y0 - y2) / denom


def track_ridges(rho_prof, centers, prev):
    """Ridge positions from the rho x-profile (maxima with parabolic
    refinement, matched to the init centers, deduped within 2 cells).

    Returns (positions, merged).  positions has one entry when the pair has
    merged or the profile lost a ridge; holds `prev` when no maxima are
    found (dispersed field).
    """
    p = rho_prof
    pampl = (p - p.min()) / max(p.max() - p.min(), 1e-30)
    idx = np.where((pampl[1:-1] >= pampl[:-2]) &
                   (pampl[1:-1] >= pampl[2:]) &
                   (pampl[1:-1] > RIDGE_THRESH))[0] + 1
    if len(idx) == 0:
        fallback = (prev if prev is not None else
                    ([centers[0]] if len(centers) == 1 else centers))
        return fallback, True
    xs = [_refine_1d(p, int(i)) for i in idx]
    out = []
    for xc in centers:
        if not xs:
            break
        k = int(np.argmin([abs(x - xc) for x in xs]))
        out.append(xs.pop(k))
    if len(out) == 2 and abs(out[0] - out[1]) < 2.0:
        # coalesced pair: keep the stronger ridge
        i0, i1 = int(round(out[0])), int(round(out[1]))
        out = [out[0] if p[i0] >= p[i1] else out[1]]
    return out, len(out) == 1


def measure_strands(solver, ey, ei, rho_prof, centers, prev):
    """Per-strand + pair diagnostics at the current state (read-only).

    ch_open/q come from the solver's own 'five' gate formula via
    run_trauma_wake_lock.channel_openness -- replicated for measurement
    only, never fed back.  conv_gate is the gate-weighted projection of the
    conversion source; conv_phase is the diagnostic-only phase-angle
    projection (cell angle onto the nearest pentagon channel).
    """
    dev = solver.device
    eps = ey - T.PHI * ei
    ch_open, q = T.channel_openness(ey, ei)
    one_minus_q = 1.0 - q
    conv_full = -T.LAM * one_minus_q * eps          # full source per cell
    eta5 = torch.tensor([1.0, T.PHI_INV, T.PHI_INV, T.PHI_INV, T.PHI_INV],
                        device=dev, dtype=torch.float64).reshape(5, 1, 1, 1)
    conv_gate_full = -T.LAM * eta5 * ch_open * eps.unsqueeze(0)  # [5,N,N,N]

    # phase-angle channel partition (diagnostic-only)
    theta = torch.atan2(ei, ey)
    nearest = (theta.unsqueeze(0) -
               torch.tensor(T.CH_ANGLES, device=dev, dtype=torch.float64)
               .unsqueeze(-1).unsqueeze(-1).unsqueeze(-1)).abs().argmin(dim=0)

    ridges, merged = track_ridges(rho_prof, centers, prev)
    if merged:
        x1 = x2 = float(ridges[0])
    else:
        x1, x2 = float(ridges[0]), float(ridges[1])
    Rc = 0.5 * (x1 + x2)
    d = abs(x2 - x1)

    # y-positions of the ridges (slab around each x-ridge) for the
    # transverse orientation theta_xy of the separation vector
    y_pos = []
    for xr in (ridges if merged else [x1, x2]):
        lo = max(0, int(round(xr)) - 3)
        hi = min(int(round(xr)) + 4, solver.N)
        slab = ey[lo:hi]
        if slab.numel() == 0:
            y_pos.append(solver.N / 2.0)
            continue
        yp = slab.sum(dim=0).sum(dim=1).cpu().numpy()
        yp = yp - yp.min()
        i = int(np.argmax(yp)) if yp.max() > 1e-30 else solver.N // 2
        if i in (0, len(yp) - 1):
            y_pos.append(float(i))
        else:
            y_pos.append(_refine_1d(yp, i))
    if merged:
        y1 = y2 = y_pos[0]
    else:
        y1, y2 = y_pos

    theta_xy = np.arctan2(y1 - y2, x1 - x2) if not merged else 0.0

    cy = cz = solver.N / 2.0
    if merged:
        centers_xy = [(x1, y1)]
    else:
        centers_xy = [(x1, y1), (x2, y2)]
    xg = torch.arange(solver.N, dtype=torch.float64, device=dev)
    Xg, Yg, Zg = torch.meshgrid(xg, xg, xg, indexing='ij')
    weights = []
    hard_balls = []
    for (xk, yk) in centers_xy:
        dd = (Xg - xk) ** 2 + (Yg - yk) ** 2 + (Zg - cz) ** 2
        # strand = the ridge's own local Qi profile: Gaussian weight with
        # the init ridge sigma, truncated at the measurement ball radius
        weights.append(torch.exp(-dd / (2.0 * SIG ** 2)) *
                       (dd <= R_SITE ** 2).to(torch.float64))
        hard_balls.append((dd <= R_SITE ** 2).to(torch.float64))
    union = torch.clamp(sum(hard_balls), max=1.0)

    out = {'d': d, 'Rc': Rc, 'merged': bool(merged), 'theta_xy': theta_xy,
           'x1': x1, 'x2': x2, 'y1': y1, 'y2': y2}

    strand = []
    for k, w in enumerate(weights):
        wsum = w.sum()
        A_k = float((eps.abs() * w).sum() / wsum)
        eps_k = float((eps * w).sum() / wsum)
        q_k = float((q * w).sum() / wsum)
        r = ey / ei
        r_w = (r * w).sum() / wsum
        sig_r = float(torch.sqrt(((r - r_w) ** 2 * w).sum() / wsum))
        th_k = float((theta * w).sum() / wsum)
        ch_k = [float((ch_open[c] * w).sum() / wsum) for c in range(5)]
        conv_g = [float((conv_gate_full[c] * w).sum() / wsum)
                  for c in range(5)]
        # phase-partitioned conversion: mean of conv_full over the strand
        # cells whose field angle is nearest channel c (diagnostic-only)
        conv_p = []
        for c in range(5):
            sel = (nearest == c).to(torch.float64) * w
            conv_p.append(float((conv_full * sel).sum() / wsum))
        phase_frac = [float(((nearest == c).to(torch.float64) * w).sum()
                            / wsum) for c in range(5)]
        dom = int(np.argmax(phase_frac))
        strand.append({'A': A_k, 'eps': eps_k, 'q': q_k, 'sigma_r': sig_r,
                       'theta': th_k, 'ch_open': ch_k, 'conv_gate': conv_g,
                       'conv_phase': conv_p, 'phase_frac': phase_frac,
                       'dominant': dom})

    out['strands'] = strand
    if merged:
        out['delta_theta'] = 0.0
        out['A_plus'] = strand[0]['A']
        out['A_minus'] = 0.0
        out['theta_c'] = strand[0]['theta']
        out['sheng_ke'] = 'same'
        out['sheng_ke_step'] = 0
    else:
        s1, s2 = strand
        out['delta_theta'] = float(np.angle(np.exp(1j * (s2['theta'] -
                                                         s1['theta']))))
        z1 = s1['A'] * np.exp(1j * s1['theta'])
        z2 = s2['A'] * np.exp(1j * s2['theta'])
        out['A_plus'] = float(abs(z1 + z2) / np.sqrt(2.0))
        out['A_minus'] = float(abs(z1 - z2) / np.sqrt(2.0))
        out['theta_c'] = 0.5 * (s1['theta'] + s2['theta'])
        # sheng/ke relation of strand 2 relative to strand 1's channel
        rel = (s2['dominant'] - s1['dominant']) % 5
        names = {0: 'same', 1: 'sheng', 2: 'ke', 3: 'ke-rev', 4: 'sheng-rev'}
        out['sheng_ke'] = names[rel]
        out['sheng_ke_step'] = rel

    # central region (pair midpoint / single-ridge center) vs flank q
    mid_mask = ball_mask(solver.N, Rc, cy, cz, MID_R, dev)
    out['q_mid'] = float((q * mid_mask).sum() / mid_mask.sum())
    out['eps_mid'] = float((eps * mid_mask).sum() / mid_mask.sum())
    out['rho_mid'] = float(((ey + ei) * mid_mask).sum() / mid_mask.sum())
    out['q_flank'] = 0.5 * (strand[0]['q'] + (strand[1]['q']
                                              if not merged
                                              else strand[0]['q']))

    bm = union > 0.5
    out['ey_min'] = float(ey[bm].min())
    out['ei_min'] = float(ei[bm].min())
    out['q_glob'] = float(q.mean())
    return out


def run_case(solver, sep, tag, outdir):
    """Evolve one arm (fresh solver, focused run), recording diagnostics."""
    print(f"\n=== run: {tag} (sep={sep}) ===")
    ey_hat, ei_hat, u_hat = two_lobe_init(solver, sep)
    centers = ([solver.N / 2.0 - sep / 2.0, solver.N / 2.0 + sep / 2.0]
               if sep > 1e-6 else [solver.N / 2.0])
    prev = None
    t0 = time.time()
    hist = []
    for step in range(STEPS):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step % T.REPORT == 0 or step == STEPS - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            rho_prof = (ey + ei).sum(dim=(1, 2)).cpu().numpy()
            d = measure_strands(solver, ey, ei, rho_prof, centers, prev)
            prev = (([d['x1'], d['x2']] if not d['merged'] else [d['x1']]))
            d.update({'step': step, 't': step * T.DT})
            hist.append(d)
            s0, s1 = d['strands'][0], (d['strands'][1] if not d['merged']
                                       else d['strands'][0])
            print(f"  t={step*T.DT:5.2f} | d={d['d']:6.3f} "
                  f"Rc={d['Rc']:6.2f} | dth={d['delta_theta']:+6.3f} "
                  f"| A=[{s0['A']:.3f},{s1['A']:.3f}] "
                  f"q=[{s0['q']:.3f},{s1['q']:.3f}] "
                  f"| dom=[{CHANNELS[s0['dominant']][0]},"
                  f"{CHANNELS[s1['dominant']][0]}] {d['sheng_ke']} "
                  f"| q_mid={d['q_mid']:.3f} q_flank={d['q_flank']:.3f} "
                  f"| ey_min={d['ey_min']:.4f} ei_min={d['ei_min']:.4f}")
    elapsed = time.time() - t0
    print(f"  [{tag}] {STEPS} steps in {elapsed:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'sep': sep, 'hist': hist}, f, indent=1)
    return hist


def summarize(tag, hist):
    """NS1/NS2/NS4 summaries plus channel-trace snapshots."""
    first, last = hist[0], hist[-1]
    d0 = first['d']
    back = hist[int(0.8 * len(hist)):]
    d_back = float(np.mean([d['d'] for d in back]))
    if d0 < 1e-6:
        ns1 = 'reference (d = 0 by construction)'
    elif last['merged'] or d_back < 0.25 * d0:
        ns1 = 'merged'
    elif d_back > 1.2 * d0:
        ns1 = 'separated'
    else:
        ns1 = 'persisted'

    def at_t(t_target):
        return min(hist, key=lambda d: abs(d['t'] - t_target))

    traces = {}
    for t_t in (0.0, 2.0, 4.0):
        d = at_t(t_t)
        s0, s1 = d['strands'][0], (d['strands'][1] if not d['merged']
                                   else d['strands'][0])
        traces[t_t] = {
            'd': d['d'], 'delta_theta': d['delta_theta'],
            'strand_A': {'conv_gate': s0['conv_gate'],
                         'conv_phase': s0['conv_phase'],
                         'dominant': CHANNELS[s0['dominant']]},
            'strand_B': {'conv_gate': s1['conv_gate'],
                         'conv_phase': s1['conv_phase'],
                         'dominant': CHANNELS[s1['dominant']]},
            'sheng_ke': d['sheng_ke'],
        }
    transitions = sum(1 for a, b in zip(hist[:-1], hist[1:])
                      if (a['strands'][0]['dominant'] !=
                          b['strands'][0]['dominant']) or
                      (not a['merged'] and not b['merged'] and
                       a['strands'][1]['dominant'] !=
                       b['strands'][1]['dominant']))
    return {
        'ns1': ns1,
        'd_start': d0, 'd_end': last['d'], 'd_back_mean': d_back,
        'merged_at_end': bool(last['merged']),
        'q_mid_start': first['q_mid'], 'q_mid_end': last['q_mid'],
        'q_flank_start': first['q_flank'], 'q_flank_end': last['q_flank'],
        'eps_mid_end': last['eps_mid'], 'rho_mid_end': last['rho_mid'],
        'A_plus_end': last['A_plus'], 'A_minus_end': last['A_minus'],
        'theta_xy_start': first['theta_xy'], 'theta_xy_end': last['theta_xy'],
        'channel_transitions': transitions,
        'traces': traces,
        'ey_min': min(d['ey_min'] for d in hist),
        'ei_min': min(d['ei_min'] for d in hist),
    }


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t={STEPS * T.DT}  "
          f"gate='five'  E_RIDGE={E_RIDGE}  BETA={BETA}  SIG={SIG}  "
          f"SEP={SEP}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_two_strand"
    os.makedirs(rdir, exist_ok=True)

    # Fresh solver per arm (rk2_step mutates scale factor, Hubble
    # smoothing, q_mean -- a shared solver makes arms order-dependent).
    h_pair = run_case(T.build_solver(device), SEP, 'two_lobe', rdir)
    h_d0 = run_case(T.build_solver(device), 0.0, 'd0', rdir)

    s_pair = summarize('two_lobe', h_pair)
    s_d0 = summarize('d0', h_d0)

    results = {
        'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT, 'steps': STEPS,
                 't_end': STEPS * T.DT, 'gate_model': 'five (solver)',
                 'E_RIDGE': E_RIDGE, 'BETA': BETA, 'SIG': SIG, 'SEP': SEP,
                 'R_SITE': R_SITE,
                 'note': 't = 4 = 0.2/lambda characterization window; '
                         'lock claims need t >= 2/lambda'},
        'two_lobe': s_pair,
        'd0_reference': s_d0,
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== TWO-STRAND PROBE RESULTS (t=4) ===")
    for name, s in [('two_lobe', s_pair), ('d0', s_d0)]:
        print(f"{name:9s}: NS1={s['ns1']:>17s} d {s['d_start']:.2f}->"
              f"{s['d_end']:.2f} (back mean {s['d_back_mean']:.2f}) | "
              f"q_mid {s['q_mid_start']:.3f}->{s['q_mid_end']:.3f} vs "
              f"q_flank {s['q_flank_start']:.3f}->{s['q_flank_end']:.3f} | "
              f"transitions={s['channel_transitions']} | "
              f"ey_min={s['ey_min']:.4f} ei_min={s['ei_min']:.4f}")

    print("\nChannel-projected conversion traces (gate-weighted, "
          "per-strand mean of -lam*eta_c*ch_open_c*eps):")
    for t_t, tr in s_pair['traces'].items():
        sA, sB = tr['strand_A'], tr['strand_B']
        gA = ', '.join(f"{c}:{v:+.4f}" for c, v in
                       zip(CHANNELS, sA['conv_gate']))
        gB = ', '.join(f"{c}:{v:+.4f}" for c, v in
                       zip(CHANNELS, sB['conv_gate']))
        print(f"  t={t_t}: d={tr['d']:.2f} dth={tr['delta_theta']:+.3f} "
              f"dom=[{sA['dominant']},{sB['dominant']}] "
              f"{tr['sheng_ke']}")
        print(f"    A (dom {sA['dominant']}): {gA}")
        print(f"    B (dom {sB['dominant']}): {gB}")

    print("\n=== VERDICT ===")
    print(f"NS1 (bound pair): {s_pair['ns1']} at t=4 "
          f"(d {s_pair['d_start']:.2f} -> {s_pair['d_end']:.2f} cells, "
          f"back-20% mean {s_pair['d_back_mean']:.2f}).")
    print(f"NS2 (d->0 recovery): d0 arm is the one-string reference "
          f"(eps = 0 by construction). Pair midpoint vs reference center "
          f"at t_end: q {s_pair['q_mid_end']:.3f} vs "
          f"{s_d0['q_mid_end']:.3f}, eps {s_pair['eps_mid_end']:+.3f} vs "
          f"{s_d0['eps_mid_end']:+.3f}, rho {s_pair['rho_mid_end']:.3f} vs "
          f"{s_d0['rho_mid_end']:.3f}.")
    print(f"NS4 (morphology): central q {s_pair['q_mid_start']:.3f}->"
          f"{s_pair['q_mid_end']:.3f} vs flank q "
          f"{s_pair['q_flank_start']:.3f}->{s_pair['q_flank_end']:.3f} "
          f"(measured from the field; the eps-node exists by construction, "
          f"the q profile is an outcome).")
    print(f"Channel traces: {s_pair['channel_transitions']} dominant-"
          f"channel transitions over the run; per-strand gate-weighted and "
          f"phase-projected conversion vectors in results.json.")
    print(f"\nResults: {rdir}/results.json")


if __name__ == "__main__":
    main()
