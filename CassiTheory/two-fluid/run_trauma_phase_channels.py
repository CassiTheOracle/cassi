#!/usr/bin/env python3
"""Phase-channel selectivity: does the locked channel track the event's phase?

Open question 2 in `consciousness/trauma-as-frozen-gate.md` and the
foundation of the channel-to-trauma-type mapping (§4.1, Speculative): "the
channel that locks is set by the phase of the event as the field received
it." All prior runs used ONE event direction (pure Yang deficit), which
lands the site phase at 72°—Fire. Is the lock channel selective to the
event direction?

REPRESENTABILITY BOUND (2026-07-31): the 1e-3 positivity clamp on ey/ei
pins atan2(ei, ey) to the first quadrant (0°, 90°) at every cell, for any
event, any amplitude, any geometry. Of the five pentagon channels only
Wood (0°) and Fire (72°) are representable in the field angle. Earth
(144°), Metal (216°), and Water (288°) require a negative field component
and cannot exist in this solver. The 5-target run at amp 1.6 demonstrates
the bound; the testable binary is Wood vs Fire.

Design:
  Part 1—bound demonstration (amp 1.6, five event directions targeting
  each pentagon channel; the three non-representable targets are expected
  to clamp onto Fire or Wood).
  Part 2—the selectivity binary (amp 0.8, standing geometry):
    delta = pi      Fire event: ball phase 40.8-72.0 deg, whole ball Fire
    delta = 3pi/2   Wood event: ball phase 0.06-18.5 deg, whole ball Wood
  Both events are cleanly representable. Watch the site phase histogram at
  t=2 and t=10: does each event stay on its own channel (selective over
  the representable arc), or do they converge?

Verdict (part 2): Wood event -> Wood at t=2/t=10 AND Fire event -> Fire
at t=2/t=10 is SELECTIVE. Any convergence is not.

Usage: python two-fluid/run_trauma_phase_channels.py
Output: runs/<id>_phase_channels/results.json + figure
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

T.LAM = 0.1
T.DT = 0.001
T.REPORT = 50
T.STEPS = 10000        # t = 10

CHANNELS = ['Wood', 'Fire', 'Earth', 'Metal', 'Water']
TARGETS = {'Wood': 0.0, 'Fire': 72.0, 'Earth': 144.0,
           'Metal': 216.0, 'Water': 288.0}

BOUND_AMP = 1.6
BINARY_AMP = 0.8


def center_phase(amp, delta):
    """Center-cell phase (pre-clamp): atan2(phi^-1 + A sin d, 1 + A cos d)."""
    return np.degrees(np.arctan2(T.PHI_INV + amp * np.sin(delta),
                                 1.0 + amp * np.cos(delta))) % 360.0


def init_fields(solver, delta, amp):
    """Standing geometry with the event direction delta at the center."""
    N_ = solver.N
    dev = solver.device
    ey = torch.ones((N_,) * 3, dtype=torch.float64, device=dev)
    ei = torch.full((N_,) * 3, T.PHI_INV, dtype=torch.float64, device=dev)
    x = torch.arange(N_, dtype=torch.float64, device=dev)
    pattern = (torch.cos(2.0 * np.pi * x / N_).unsqueeze(1).unsqueeze(2) *
               torch.cos(2.0 * np.pi * x / N_).unsqueeze(0).unsqueeze(2) *
               torch.cos(2.0 * np.pi * x / N_).unsqueeze(0).unsqueeze(0))
    ey = ey - amp * np.cos(delta) * pattern
    ei = ei - amp * np.sin(delta) * pattern
    ey = torch.clamp(ey, min=1e-3)
    ei = torch.clamp(ei, min=1e-3)
    u_hat = torch.zeros(3, N_, N_, N_, dtype=torch.complex128, device=dev)
    return torch.fft.fftn(ey), torch.fft.fftn(ei), u_hat


def run_case(solver, delta, amp, tag='run', outdir=None):
    print(f"\n=== run: {tag} (amp={amp}, delta={np.degrees(delta):6.1f} "
          f"deg) ===")
    ey_hat, ei_hat, u_hat = init_fields(solver, delta, amp)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    t0 = time.time()
    hist = []
    for step in range(T.STEPS):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step % T.REPORT == 0 or step == T.STEPS - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            d = T.measure(solver, ey, ei, mask)
            d.update({'step': step, 't': step * T.DT})
            hist.append(d)
    print(f"  [{tag}] {T.STEPS} steps in {time.time() - t0:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'hist': hist}, f, indent=1)
    return hist


def at_t(hist, t_target):
    return min(hist, key=lambda d: abs(d['t'] - t_target))


def dominant(phase_frac):
    return CHANNELS[int(np.argmax(phase_frac))]


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t=10")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_phase_channels"
    os.makedirs(rdir, exist_ok=True)

    solver = T.build_solver(device)
    results = {'meta': {'lam': T.LAM, 'bound_amp': BOUND_AMP,
                        'binary_amp': BINARY_AMP}, 'bound_demo': {},
               'binary': {}}

    # ── Part 1: representability bound demonstration (amp 1.6) ───────────
    print("\n--- Part 1: bound demonstration (amp 1.6, five targets) ---")
    for ch, tgt in TARGETS.items():
        # best unclamped delta for the target
        best, best_err = None, 1e9
        for d in np.linspace(0.0, 2.0 * np.pi, 1440):
            err = abs((center_phase(BOUND_AMP, d) - tgt + 180.0) % 360.0
                      - 180.0)
            if err < best_err:
                best, best_err = d, err
        th = center_phase(BOUND_AMP, best)
        # post-clamp center phase
        ey_c = max(1.0 + BOUND_AMP * np.cos(best), 1e-3)
        ei_c = max(T.PHI_INV + BOUND_AMP * np.sin(best), 1e-3)
        th_clamped = np.degrees(np.arctan2(ei_c, ey_c)) % 360.0
        h = run_case(solver, best, BOUND_AMP, tag=f'bound_{ch}', outdir=rdir)
        r2 = at_t(h, 2.0)
        dom2 = dominant(r2['phase_frac'])
        rep = abs((th_clamped - tgt + 180.0) % 360.0 - 180.0) <= 36.0
        results['bound_demo'][ch] = {
            'delta_deg': float(np.degrees(best)),
            'preclamp_center_deg': float(th),
            'postclamp_center_deg': float(th_clamped),
            'representable': bool(rep),
            't2_dominant': dom2,
        }
        print(f"  {ch:5s} target {tgt:5.1f} deg: delta "
              f"{np.degrees(best):6.2f} deg, pre-clamp center {th:5.1f} "
              f"deg -> post-clamp {th_clamped:5.1f} deg "
              f"({'representable' if rep else 'CLAMPED OUT'}), "
              f"t=2 dominant: {dom2}")

    n_rep = sum(1 for v in results['bound_demo'].values() if v['representable'])
    print(f"\n  Only {n_rep}/5 channels representable in the field angle "
          f"under the positivity clamp.")

    # ── Part 2: the Wood/Fire selectivity binary (amp 0.8) ────────────────
    print("\n--- Part 2: selectivity binary (amp 0.8) ---")
    fire_d = np.pi
    wood_d = 1.5 * np.pi
    print(f"  Fire event: delta=pi, ball phase 40.8-72.0 deg (whole Fire)")
    print(f"  Wood event: delta=3pi/2, ball phase 0.06-18.5 deg (whole Wood)")
    h_fire = run_case(solver, fire_d, BINARY_AMP, tag='fire', outdir=rdir)
    h_wood = run_case(solver, wood_d, BINARY_AMP, tag='wood', outdir=rdir)

    for name, h in [('fire', h_fire), ('wood', h_wood)]:
        r2 = at_t(h, 2.0)
        r10 = at_t(h, 10.0)
        results['binary'][name] = {
            't2_phase': r2['phase_frac'], 't2_dominant': dominant(r2['phase_frac']),
            't10_phase': r10['phase_frac'], 't10_dominant': dominant(r10['phase_frac']),
            't10_eps': r10['eps_site'], 't10_q_gap': r10['q_glob'] - r10['q_site'],
        }
        print(f"  {name:4s} event: t=2 -> {results['binary'][name]['t2_dominant']:5s}"
              f"  ({['%.2f' % f for f in r2['phase_frac']]}), "
              f"t=10 -> {results['binary'][name]['t10_dominant']:5s}"
              f"  ({['%.2f' % f for f in r10['phase_frac']]})")

    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    f2 = results['binary']['fire']['t2_dominant']
    w2 = results['binary']['wood']['t2_dominant']
    f10 = results['binary']['fire']['t10_dominant']
    w10 = results['binary']['wood']['t10_dominant']

    print("\n=== VERDICT ===")
    print(f"Representability: {n_rep}/5 pentagon channels exist in the "
          f"field angle; Earth/Metal/Water are clamped out.")
    if f2 == 'Fire' and w2 == 'Wood':
        print(f"SELECTIVE at t=2 (Fire event -> {f2}, Wood event -> {w2}).")
        if f10 == 'Fire' and w10 == 'Wood':
            print("SELECTIVE at t=10 too—the lock channel tracks the "
                  "event direction across the representable arc.")
        else:
            print(f"At t=10 the channels drift (Fire -> {f10}, "
                  f"Wood -> {w10})—selectivity is transient.")
    elif f2 == w2:
        print(f"NOT SELECTIVE: both events dominate {f2} at t=2—the lock "
              f"does not track the event direction even across the "
              f"representable arc.")
    else:
        print(f"MIXED at t=2: Fire event -> {f2}, Wood event -> {w2}.")

    # ── Figure ─────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        colors = ['C0', 'C1', 'C2', 'C3', 'C4']
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        for ax, (tag, title) in zip(axes, [('fire', 'Fire event '
                                            '(delta = pi)'),
                                           ('wood', 'Wood event '
                                            '(delta = 3pi/2)')]):
            with open(f"{rdir}/run_{tag}.json") as f:
                hist = json.load(f)['hist']
            t = [d['t'] for d in hist]
            for k in range(5):
                ax.plot(t, [d['phase_frac'][k] for d in hist],
                        color=colors[k], lw=1.3,
                        label=CHANNELS[k] if tag == 'fire' else None)
            ax.set_title(title)
            ax.set_ylim(-0.02, 1.02)
            ax.set_xlabel('t')
            ax.grid(alpha=0.3)
        axes[0].set_ylabel('site phase fraction')
        axes[0].legend(fontsize=8, ncol=5, loc='upper right')
        fig.suptitle('Site phase channels vs event direction '
                     '(lambda=0.1, amp=0.8)')
        fig.tight_layout()
        fig.savefig(f"{rdir}/phase_channels.png", dpi=130)
        plt.close()
        print(f"\nFigure: {rdir}/phase_channels.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
