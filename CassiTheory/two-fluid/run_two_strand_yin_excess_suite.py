#!/usr/bin/env python3
"""Two-strand Yin-excess pair suite: the framework-native attractive branch.

Run:  python two-fluid/run_two_strand_yin_excess_suite.py

Design-iteration candidate (iii) of `hypotheses/two-strand-five-channel-matter-organization.md`
sec 3.4: the wake-binding scratch layer is null (no binding window, sec 3.4),
and the realized Yang-excess pair escapes because the buoyancy force
F = Pi grad(Phi), Pi = EY - EI, grad(Phi) = -grad(nabla^-2 rho), is
self-repulsive for the Yang-excess pair (Pi > 0 in every ridge: the
(phi-1)rho density pedestal dominates the anti-phase eps lobes).  The
framework-native attractive branch is the Yin-excess pair, Pi < 0, where
the same force is self-attractive.

The smallest focused test that changes ONLY the pair initialization: the
canonical two-lobe state with the Yang and Yin fields exchanged,

    ey' = ei_canonical,  ei' = ey_canonical,

i.e. the same rho ridges, the same |eps| anti-phase lobes, the same
protocol constants (E_RIDGE = 0.65, BETA = 0.3, SIG = 5, SEP = 12) -- no
new parameter, no binding term, no solver edit (the canonical
ExpandingTwoFluid3DGPU with its existing gate/conversion/gravity terms is
used untouched, fresh solver per arm).

Representability boundary (checked as Y1): the positivity clamp is a
FLOOR (ey, ei >= 1e-3), not a sign constraint; Pi < 0 needs ei > ey with
both positive, which is representable.  A mere eps sign flip is NOT
sufficient: pi = [(phi-1)rho + 2 eps]/(1+phi) stays positive at the ridge
cores (numerically +0.16).  The structural boundary on a STEADY branch is
the conversion attractor, not the clamp: the canonical conversion pair
dt(eps) = -lam (1+phi)(1-q) eps drives eps -> 0, and eps = 0 with rho > 0
gives pi = (phi-1) ei > 0, so every trajectory ends Yang-excess; a steady
Yin-excess branch would need a representation change (e.g. sign-opposite
conversion on the eps < 0 half-space or a negative attractor eps*), which
this test does NOT implement -- it measures the transient branch the
existing PDE supports.

Arms (all N = 48, lam = 0.05, dt = 0.001, t = 40 = 2/lambda, gate 'five',
fresh solver per arm):
  ctrl    canonical Yang-excess pair, sep = 12 (the committed baseline
          init) -- Yang-excess counterfactual + machine reproduction of
          the published t = 4 baseline and t = 40 escape.
  ysep12  Yin-excess pair (field-swapped init), sep = 12 -- the primary
          arm; t = 4 characterization is read from the same record.
  ysep0   Yin-excess one-string reference (field-swapped init, sep = 0:
          eps = 0 so eps' = -(phi-1)rho < 0 everywhere, single ridge) --
          the d -> 0 reference of the Yin-excess branch.

Measurement: per-strand ridge positions are tracked from the DENSITY
field (x from the rho x-profile as in the probe; y from the rho slab).
The probe tracks y from the EY slab, whose argmax sits on the background
ring for the Yin-excess init (EY is anti-correlated with density there);
density is invariant under the ey <-> ei exchange, so the density-tracked
balls are the physical ridge centers for every arm (see measure_density).
All other measurement logic is the probe's, bit-identical.

Verdicts (results.json):
  Y1  representability: pi_strand < 0 in both ridges, Pi_tot < 0, min
      ey/ei > 1e-3 at t = 0 -- the positivity clamp does not block the
      Yin-excess branch.
  Y2  t = 4 characterization of ysep12: d, DeltaTheta, A+/A-, q_mid vs
      q_flank, pi per strand, clamp, mass drift, channel traces.
  Y3  lock-timescale outcome (t = 40, sec-3 bands): merged / persisted /
      separated / reference for each arm; d(t) trajectory and the pi
      sign-flip time (when conversion erases the Yin excess).
  Y4  one-string reference validity: ysep0 stays a single ridge (one
      tracked ridge, no NaN, bounded drift) and its centerline observables
      are the d -> 0 comparison for ysep12 at t = 40.
  Y5  Yang-excess counterfactual: ctrl reproduces the published t = 4
      baseline and the t = 40 escape (d 9.90 -> 15.73); max Delta d(t)
      vs the Yin-excess arm.
  Y6  telemetry: per-arm mass drift (EY/EI/total), floor touches, a_end,
      H_end, NaN abort.

No registries or parameter-inventory updates: no parameter is introduced
and no master prediction number is touched; the verdict is local to the
two-strand program (E1 candidate (iii)).

Output (runs/ is gitignored -- commit the script only):
  runs/<rid>_two_strand_yin_excess/run_<arm>.json   per-arm histories
  runs/<rid>_two_strand_yin_excess/results.json     meta + verdicts
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
import cassi_two_fluid_3d_gpu as C    # canonical solver, read-only

# ── Protocol (lock timescale: t = 40 = 2/lambda) ─────────────────────────
T.LAM = 0.05
T.DT = 0.001
STEPS = 40000                # t = 40
REPORT = 100                 # 401 records per arm
SEP = 12                     # baseline pair separation (cells)
FLOOR = 1e-3                 # solver positivity clamp floor
FLOOR_TOUCH = 1.01e-3        # telemetry trigger (as in the suite)

CHANNELS = ['Wood', 'Fire', 'Earth', 'Metal', 'Water']
SNAP_STEPS = (0, 4000, STEPS - 1)      # t = 0, 4, 40 profiles

# Published t = 4 baseline of the canonical pair (probe record, doc sec 3)
T4_REF = {'d': 10.08, 'delta_theta': 0.227, 'q_mid': 0.7074,
          'q_flank': 0.7009, 'A_plus': 0.444, 'A_minus': 0.051,
          'eps_mid': -0.020, 'rho_mid': 2.078}
T4_TOL = {'d': 0.05, 'delta_theta': 0.005, 'q_mid': 0.001, 'q_flank': 0.001,
          'A_plus': 0.005, 'A_minus': 0.005, 'eps_mid': 0.002,
          'rho_mid': 0.01}
# Published t = 40 escape of the canonical pair (TS1 record, doc sec 3.3)
T40_ESCAPE = 15.73           # ctrl d_end at t = 40
T40_TOL = 0.30


def yin_excess_init(solver, sep):
    """Yin-excess pair init: the canonical anti-phase two-lobe state
    (P.two_lobe_init) with the Yang and Yin fields exchanged.

    pi' = ey' - ei' = -pi_canonical < 0 in every ridge: the same density
    ridges, the same |eps| lobes, but each ridge now carries Yin excess,
    so the buoyancy force pi grad(Phi) is self-attractive.  The exchange
    commutes with the 1e-3 clamp, so this is bit-for-bit the canonical
    construction with the two fields swapped -- the smallest possible
    initialization-only change (no parameter, no binding term).
    """
    ey_hat, ei_hat, u_hat = P.two_lobe_init(solver, sep)
    return ei_hat, ey_hat, u_hat


def _refine_1d(p, i):
    """Parabolic sub-grid refinement (copy of P._refine_1d, read-only)."""
    y0, y1, y2 = p[i - 1], p[i], p[i + 1]
    denom = y0 - 2.0 * y1 + y2
    if abs(denom) < 1e-14:
        return float(i)
    return i + 0.5 * (y0 - y2) / denom


def track_ridges(rho_prof, centers, prev):
    """Ridge positions from the rho x-profile (copy of P.track_ridges,
    read-only; the suite monkey-patches this same function for its sep<=6
    seeding -- not needed here, SEP = 12 resolves cleanly)."""
    p = rho_prof
    pampl = (p - p.min()) / max(p.max() - p.min(), 1e-30)
    idx = np.where((pampl[1:-1] >= pampl[:-2]) &
                   (pampl[1:-1] >= pampl[2:]) &
                   (pampl[1:-1] > P.RIDGE_THRESH))[0] + 1
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
        i0, i1 = int(round(out[0])), int(round(out[1]))
        out = [out[0] if p[i0] >= p[i1] else out[1]]
    return out, len(out) == 1


def measure_density(solver, ey, ei, rho_prof, centers, prev):
    """Copy of P.measure_strands with ONE documented change: the ridge
    y-positions come from the DENSITY slab (ey + ei) instead of the EY
    slab.  The probe tracks y by the argmax of sum(ey) over the slab; for
    the Yin-excess init EY is anti-correlated with density (ey' =
    (rho - eps)/(1+phi) dips at the ridge cores), so the EY argmax sits on
    the background ring and the strand balls miss the ridges.  Density is
    invariant under the ey <-> ei exchange, so the density-tracked
    positions are the physical ridge centers for both arms (for the
    Yang-excess ctrl arm the two trackers agree to the refinement digit).
    All other logic is bit-identical to P.measure_strands (read-only
    import; the probe module is untouched)."""
    dev = solver.device
    eps = ey - T.PHI * ei
    ch_open, q = T.channel_openness(ey, ei)
    one_minus_q = 1.0 - q
    conv_full = -T.LAM * one_minus_q * eps
    eta5 = torch.tensor([1.0, T.PHI_INV, T.PHI_INV, T.PHI_INV, T.PHI_INV],
                        device=dev, dtype=torch.float64).reshape(5, 1, 1, 1)
    conv_gate_full = -T.LAM * eta5 * ch_open * eps.unsqueeze(0)

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

    rho_f = ey + ei
    y_pos = []
    for xr in (ridges if merged else [x1, x2]):
        lo = max(0, int(round(xr)) - 3)
        hi = min(int(round(xr)) + 4, solver.N)
        slab = rho_f[lo:hi]
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
        weights.append(torch.exp(-dd / (2.0 * P.SIG ** 2)) *
                       (dd <= P.R_SITE ** 2).to(torch.float64))
        hard_balls.append((dd <= P.R_SITE ** 2).to(torch.float64))
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
        rel = (s2['dominant'] - s1['dominant']) % 5
        names = {0: 'same', 1: 'sheng', 2: 'ke', 3: 'ke-rev', 4: 'sheng-rev'}
        out['sheng_ke'] = names[rel]
        out['sheng_ke_step'] = rel

    mid_mask = P.ball_mask(solver.N, Rc, cy, cz, P.MID_R, dev)
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


def pi_telemetry(solver, ey, ei, out):
    """Add the Pi observables to a P.measure_strands record (read-only).

    Per-strand pi = <ey - ei> over the same Gaussian x ball masks the
    probe uses for A_k, plus midpoint, global mean, and box totals of
    both components (mass telemetry)."""
    dev = solver.device
    pi = ey - ei
    cy = cz = solver.N / 2.0
    xg = torch.arange(solver.N, dtype=torch.float64, device=dev)
    Xg, Yg, Zg = torch.meshgrid(xg, xg, xg, indexing='ij')
    centers_xy = ([(out['x1'], out['y1']), (out['x2'], out['y2'])]
                  if not out['merged'] else [(out['x1'], out['y1'])])
    pis = []
    for (xk, yk) in centers_xy:
        dd = (Xg - xk) ** 2 + (Yg - yk) ** 2 + (Zg - cz) ** 2
        w = torch.exp(-dd / (2.0 * P.SIG ** 2)) * \
            (dd <= P.R_SITE ** 2).to(torch.float64)
        pis.append(float((pi * w).sum() / w.sum()))
    if len(pis) == 1:
        pis = pis * 2
    mid_mask = P.ball_mask(solver.N, out['Rc'], cy, cz, P.MID_R, dev)
    out['pi_strand'] = pis
    out['pi_mid'] = float((pi * mid_mask).sum() / mid_mask.sum())
    out['pi_glob'] = float(pi.mean())
    out['Pi_tot'] = float(pi.sum())
    out['ey_tot'] = float(ey.sum())
    out['ei_tot'] = float(ei.sum())
    return out


def run_case(solver, sep, tag, outdir, yin=True):
    """Evolve one arm (fresh solver), recording diagnostics every REPORT
    steps plus q/eps/pi/rho axial profiles at t = 0, 4, 40 and H/a per
    record (mass, clamp, Pi telemetry at every record)."""
    print(f"\n=== run: {tag} (sep={sep}, "
          f"{'Yin-excess' if yin else 'Yang-excess'}) ===")
    if yin:
        ey_hat, ei_hat, u_hat = yin_excess_init(solver, sep)
    else:
        ey_hat, ei_hat, u_hat = P.two_lobe_init(solver, sep)
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
    for step in range(STEPS):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step % REPORT == 0 or step == STEPS - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            if bool(torch.isnan(ey).any()) or bool(torch.isnan(ei).any()):
                nan_abort = step
                print(f"  [{tag}] NaN in the fields at step {step} "
                      f"(t={step * T.DT:.3f}); aborting the arm")
                break
            rho_prof = (ey + ei).sum(dim=(1, 2)).cpu().numpy()
            d = measure_density(solver, ey, ei, rho_prof, centers, prev)
            prev = ([d['x1'], d['x2']] if not d['merged'] else [d['x1']])
            pi_telemetry(solver, ey, ei, d)
            d.update({'step': step, 't': step * T.DT,
                      'a': float(solver.a), 'H': float(solver.H)})
            if d['ey_min'] < FLOOR_TOUCH or d['ei_min'] < FLOOR_TOUCH:
                floor_touch += 1
            if step in SNAP_STEPS:
                q = T.channel_openness(ey, ei)[1]
                eps_f = ey - C.PHI * ei
                pi_f = ey - ei
                d['q_prof'] = q[:, cy, cz].cpu().numpy().tolist()
                d['eps_prof'] = eps_f[:, cy, cz].cpu().numpy().tolist()
                d['pi_prof'] = pi_f[:, cy, cz].cpu().numpy().tolist()
                d['rho_prof_ax'] = (ey + ei)[:, cy, cz].cpu().numpy().tolist()
            hist.append(d)
            if step % (10 * REPORT) == 0 or step == STEPS - 1:
                s0 = d['strands'][0]
                s1 = (d['strands'][1] if not d['merged'] else d['strands'][0])
                print(f"  t={step * T.DT:5.1f} | d={d['d']:6.3f} "
                      f"Rc={d['Rc']:6.2f} | dth={d['delta_theta']:+6.3f} "
                      f"| pi=[{d['pi_strand'][0]:+.3f},"
                      f"{d['pi_strand'][1]:+.3f}] "
                      f"| A=[{s0['A']:.3f},{s1['A']:.3f}] "
                      f"q=[{s0['q']:.3f},{s1['q']:.3f}] "
                      f"| q_mid={d['q_mid']:.3f} q_flank={d['q_flank']:.3f} "
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
            json.dump({'kind': tag, 'sep': sep, 'yin': yin,
                       'hist': hist, 'meta': meta}, f, indent=1)
    return hist, meta


# ── Analyses (read-only on the histories) ────────────────────────────────

def at_t(h, t_target):
    return min(h, key=lambda d: abs(d['t'] - t_target))


def arm_summary(h):
    """Sec-3 band classification plus the Pi/phase/amplitude endpoints."""
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
        'delta_theta_4': at_t(h, 4.0)['delta_theta'],
        'delta_theta_end': last['delta_theta'],
        'A_plus_end': last['A_plus'], 'A_minus_end': last['A_minus'],
        'Rc_drift': max(abs(d['Rc'] - first['Rc']) for d in h),
        'q_mid_0': first['q_mid'], 'q_mid_4': at_t(h, 4.0)['q_mid'],
        'q_mid_end': last['q_mid'],
        'q_flank_0': first['q_flank'], 'q_flank_4': at_t(h, 4.0)['q_flank'],
        'q_flank_end': last['q_flank'],
        'q_glob_0': first['q_glob'], 'q_glob_end': last['q_glob'],
        'eps_mid_end': last['eps_mid'], 'rho_mid_end': last['rho_mid'],
        'pi_strand_0': first['pi_strand'], 'pi_strand_end': last['pi_strand'],
        'pi_glob_0': first['pi_glob'], 'pi_glob_end': last['pi_glob'],
        'Pi_tot_0': first['Pi_tot'], 'Pi_tot_end': last['Pi_tot'],
        'ey_min': min(d['ey_min'] for d in h),
        'ei_min': min(d['ei_min'] for d in h),
        'H_0': first['H'], 'H_end': last['H'],
        'a_0': first['a'], 'a_end': last['a'],
    }


def pi_flip_time(h):
    """First record at which both strands are no longer Yin-excess
    (pi_strand[k] >= 0); None if the Yin excess survives to t = 40."""
    for d in h:
        if all(p >= 0.0 for p in d['pi_strand']):
            return d['t']
    return None


def merge_time(h):
    """First record with a single tracked ridge; None if never merged."""
    for d in h[1:]:
        if d['merged']:
            return d['t']
    return None


def reproduction_check(h_ctrl):
    """ctrl arm must pass through the published t = 4 baseline and reach
    the published t = 40 escape (machine reproduction + counterfactual)."""
    at = at_t(h_ctrl, 4.0)
    got = {k: at[k] for k in T4_REF}
    ok4 = all(abs(got[k] - T4_REF[k]) <= T4_TOL[k] for k in T4_REF)
    d40 = h_ctrl[-1]['d']
    ok40 = abs(d40 - T40_ESCAPE) <= T40_TOL
    return ok4 and ok40, got, d40


def compute_verdicts(arms, meta, rdir):
    sums = {tag: arm_summary(h) for tag, h in arms.items()}
    y0 = arms['ysep12'][0]

    # ── Y1: representability of the Yin-excess branch ──────────────────
    y1_ok = (y0['pi_strand'][0] < 0.0 and y0['pi_strand'][1] < 0.0
             and y0['Pi_tot'] < 0.0 and min(y0['ey_min'], y0['ei_min'])
             >= FLOOR)
    y1 = {'verdict': 'representable' if y1_ok else 'blocked',
          'pi_strand_0': y0['pi_strand'], 'pi_glob_0': y0['pi_glob'],
          'Pi_tot_0': y0['Pi_tot'], 'ey_min_0': y0['ey_min'],
          'ei_min_0': y0['ei_min'],
          'floor': FLOOR,
          'boundary_note': ('the positivity clamp is a floor (ey, ei >= '
                            '1e-3), not a sign constraint: Pi < 0 needs '
                            'ei > ey with both positive and is representable; '
                            'a steady Yin-excess branch is still blocked by '
                            'the conversion attractor (eps -> 0 gives pi = '
                            '(phi-1) ei > 0), so the branch is transient '
                            'under the canonical conversion')}

    # ── Y2: t = 4 characterization of the Yin-excess pair ─────────────
    y4 = at_t(arms['ysep12'], 4.0)
    c4 = at_t(arms['ctrl'], 4.0)
    y2 = {
        'ysep12': {k: y4[k] for k in
                   ('d', 'delta_theta', 'A_plus', 'A_minus', 'q_mid',
                    'q_flank', 'eps_mid', 'rho_mid', 'pi_strand', 'pi_mid',
                    'pi_glob', 'Pi_tot', 'ey_min', 'ei_min', 'q_glob')},
        'ctrl_at_t4': {k: c4[k] for k in
                       ('d', 'delta_theta', 'q_mid', 'q_flank')},
        'theta_xy_0': y0['theta_xy'], 'theta_xy_4': y4['theta_xy'],
    }

    # ── Y3: lock-timescale outcome ─────────────────────────────────────
    y3 = {tag: {'ns1': s['ns1'], 'd_start': s['d_start'],
                'd_end': s['d_end'], 'd_back_mean': s['d_back_mean'],
                'merged_at_end': s['merged_at_end'],
                'pi_flip_t': pi_flip_time(arms[tag]),
                'merge_t': merge_time(arms[tag])}
          for tag, s in sums.items()}
    y3['ysep12_pi_flip_t'] = pi_flip_time(arms['ysep12'])
    y3['ctrl_pi_flip_t'] = pi_flip_time(arms['ctrl'])

    # ── Y4: one-string reference validity ──────────────────────────────
    h0 = arms['ysep0']
    ref_ok = (meta['ysep0']['nan_abort'] is None
              and meta['ysep0']['floor_touch'] == 0
              and all(d['merged'] for d in h0)
              and max(abs(d['Rc'] - h0[0]['Rc']) for d in h0) < 2.0)
    y4v = {'verdict': 'valid' if ref_ok else 'invalid',
           'Rc_drift': sums['ysep0']['Rc_drift'],
           'q_mid_0': sums['ysep0']['q_mid_0'],
           'q_mid_end': sums['ysep0']['q_mid_end'],
           'eps_mid_end': sums['ysep0']['eps_mid_end'],
           'rho_mid_end': sums['ysep0']['rho_mid_end'],
           'pi_glob_0': sums['ysep0']['pi_glob_0'],
           'pi_glob_end': sums['ysep0']['pi_glob_end'],
           'd_to_ref_t40': {'q_mid': abs(sums['ysep12']['q_mid_end']
                                         - sums['ysep0']['q_mid_end']),
                            'eps_mid': abs(sums['ysep12']['eps_mid_end']
                                           - sums['ysep0']['eps_mid_end']),
                            'rho_mid': abs(sums['ysep12']['rho_mid_end']
                                           - sums['ysep0']['rho_mid_end'])},
           'mass_drift': meta['ysep0']['mass_drift']}

    # ── Y5: Yang-excess counterfactual + reproduction ──────────────────
    repro_ok, repro_got, d40 = reproduction_check(arms['ctrl'])
    dd = max(abs(d['d'] - c['d'])
             for d, c in zip(arms['ysep12'], arms['ctrl']))
    y5 = {'reproduction_t4': repro_ok, 't4_got': repro_got,
          'ctrl_d40': d40, 'ctrl_escape': d40 > 1.2 * sums['ctrl']['d_start'],
          'max_d_gap_ysep_vs_ctrl': dd}

    # ── Y6: telemetry ──────────────────────────────────────────────────
    y6 = {tag: {k: m[k] for k in ('mass_drift', 'floor_touch', 'a_end',
                                  'H_end', 'nan_abort')}
          for tag, m in meta.items()}

    results = {
        'meta': {'N': T.N, 'lam': T.LAM, 'dt': T.DT, 'steps': STEPS,
                 't_end': STEPS * T.DT, 'gate_model': 'five (solver)',
                 'E_RIDGE': P.E_RIDGE, 'BETA': P.BETA, 'SIG': P.SIG,
                 'SEP': SEP, 'R_SITE': P.R_SITE,
                 'init': 'canonical two-lobe state with ey <-> ei exchanged '
                         '(Yin-excess: Pi = ey - ei < 0 in every ridge); '
                         'no binding term, no new parameter, canonical '
                         'ExpandingTwoFluid3DGPU untouched',
                 'arms': {tag: m for tag, m in meta.items()}},
        'arms': sums,
        'verdicts': {'Y1_representability': y1,
                     'Y2_t4_characterization': y2,
                     'Y3_lock_timescale': y3,
                     'Y4_one_string_reference': y4v,
                     'Y5_counterfactual': y5,
                     'Y6_telemetry': y6},
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== YIN-EXCESS PAIR SUITE VERDICTS (t=40, lock timescale) ===")
    for tag in ('ctrl', 'ysep12', 'ysep0'):
        s = sums[tag]
        print(f"{tag:6s}: ns1={s['ns1']:>9s} d {s['d_start']:.2f}->"
              f"{s['d_end']:.2f} (back {s['d_back_mean']:.2f}) | "
              f"pi=[{s['pi_strand_0'][0]:+.3f},{s['pi_strand_0'][1]:+.3f}]"
              f"->[{s['pi_strand_end'][0]:+.3f},{s['pi_strand_end'][1]:+.3f}]"
              f" | dth {s['delta_theta_0']:+.3f}->{s['delta_theta_end']:+.3f}"
              f" | q_mid {s['q_mid_0']:.3f}->{s['q_mid_end']:.3f} vs "
              f"q_flank {s['q_flank_0']:.3f}->{s['q_flank_end']:.3f} | "
              f"ey_min {s['ey_min']:.4f} ei_min {s['ei_min']:.4f} | "
              f"mass_drift {meta[tag]['mass_drift']['tot']:.2e}")
    print(f"\nY1 representability: {y1['verdict'].upper()} "
          f"(pi0 {y0['pi_strand']}, Pi_tot {y0['Pi_tot']:.1f}, "
          f"floors {y0['ey_min']:.4f}/{y0['ei_min']:.4f} >= {FLOOR})")
    print(f"Y3 lock-timescale: ysep12 -> {y3['ysep12']['ns1']} "
          f"(pi flip at t={y3['ysep12']['pi_flip_t']}, "
          f"merge at t={y3['ysep12']['merge_t']}); "
          f"ctrl -> {y3['ctrl']['ns1']}")
    print(f"Y4 one-string: {y4v['verdict']} (Rc drift "
          f"{sums['ysep0']['Rc_drift']:.2f} cells, pi_glob "
          f"{sums['ysep0']['pi_glob_0']:+.3f}->"
          f"{sums['ysep0']['pi_glob_end']:+.3f})")
    print(f"Y5 counterfactual: t=4 reproduction {'OK' if repro_ok else 'MISMATCH'}"
          f", ctrl d40 = {d40:.2f} (escape {'OK' if y5['ctrl_escape'] else 'no'}), "
          f"max |d_ysep - d_ctrl| = {dd:.2f} cells")
    print(f"\nResults: {rdir}/results.json")


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t={STEPS * T.DT}  "
          f"gate='five'  E_RIDGE={P.E_RIDGE}  BETA={P.BETA}  SIG={P.SIG}  "
          f"SEP={SEP}")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_two_strand_yin_excess"
    os.makedirs(rdir, exist_ok=True)

    arms = {}
    meta = {}
    # Yang-excess counterfactual (canonical baseline init)
    h, m = run_case(T.build_solver(device), SEP, 'ctrl', rdir, yin=False)
    arms['ctrl'], meta['ctrl'] = h, m
    # Yin-excess pair (primary arm)
    h, m = run_case(T.build_solver(device), SEP, 'ysep12', rdir, yin=True)
    arms['ysep12'], meta['ysep12'] = h, m
    # Yin-excess one-string reference
    h, m = run_case(T.build_solver(device), 0.0, 'ysep0', rdir, yin=True)
    arms['ysep0'], meta['ysep0'] = h, m

    compute_verdicts(arms, meta, rdir)
    if torch.cuda.is_available():
        torch.cuda.synchronize()   # ROCm teardown deadlocks on async work


if __name__ == "__main__":
    main()
