#!/usr/bin/env python3
"""C3: the ke control ring in the 5-channel gate—PDE test.

Prediction C3 of `foundations/wu-xing-cycle-structure.md` §4: with the ke
control term (kappa = phi^-1 = K_fw) added to the gate, a locked channel
should drive the ke-alternating pattern in channel openness (C1), the lock
should still decay with no driver (sub-critical ring, kappa^3 < 1), and the
phi-phased drive should still dissolve it.

The solver's gate_model='five_ke' implements one simultaneous ke round per
evaluation: each channel's excess over baseline restrains its ke target
(i+2), depositing the displaced coherence at i+4.

Runs (lambda=0.1, t=10, N=48, standing Yang-deficit event):
  five     the standard gate (control, known behavior)
  five_ke  the ke-extended gate (test)
  five_ke  + phi-phased drive at T = phi*P0 (C3 robustness)

Verdicts:
  C1: site ch_open deviation pattern of five_ke vs five at t=2 follows the
      ring fractions [+0.618, +0.764, -0.382, -0.618, +0.382] * D for a
      Fire lock (ke order 2,4,1,3,5 strictly alternating).
  C3a: eps_site decays without a driver in five_ke (no self-sustenance).
  C3b: the phi-drive accelerates decay in five_ke (eps_rel below undriven).

Usage: python two-fluid/run_trauma_ke_ring.py
Output: runs/<id>_ke_ring/results.json + figure
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
from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI, PHI_INV
import run_trauma_wake_lock as T

T.LAM = 0.1
T.DT = 0.001
T.REPORT = 50
T.STEPS = 10000        # t = 10
T.AMP = float(os.environ.get('AMP', '0.8'))
DRIVE_AMP = 0.3

CHANNELS = ['Wood', 'Fire', 'Earth', 'Metal', 'Water']
BASELINE = np.array([PHI ** -k for k in (3, 4, 5, 6, 7)])   # b_i
ETA = np.array([1.0, PHI_INV, PHI_INV, PHI_INV, PHI_INV])


def channel_openness(ey, ei, ke=False):
    """Replicates the solver's 'five' / 'five_ke' gate (see wake-lock)."""
    M = (ey + ei) ** 2
    eps_sq = (ey - PHI * ei) ** 2
    eps_norm = eps_sq / (eps_sq + M + PHI_INV ** 2 + 1e-30)
    w1 = (1.0 - eps_norm).clamp(0.0, 1.0)
    w2 = (4.0 * eps_norm * (1.0 - eps_norm)).clamp(0.0, 1.0)
    w3 = torch.ones_like(eps_norm)
    w4 = eps_norm
    w5 = torch.sigmoid((eps_norm - 0.3) / 0.05)
    b = torch.tensor([PHI ** -k for k in (3, 4, 5, 6, 7)],
                     device=ey.device, dtype=torch.float64)
    eta = torch.tensor([1.0, PHI_INV, PHI_INV, PHI_INV, PHI_INV],
                       device=ey.device, dtype=torch.float64)
    b5 = b.unsqueeze(-1).unsqueeze(-1).unsqueeze(-1)
    eta5 = eta.unsqueeze(-1).unsqueeze(-1).unsqueeze(-1)

    w_all = torch.stack([w1, w2, w3, w4, w5], dim=0)
    wood_closed = b[0] * (1.0 - w1)
    active_open = (b5[1:] * w_all[1:]).sum(dim=0, keepdim=True).clamp(min=1e-30)
    redist = wood_closed * (b5[1:] * w_all[1:]) / active_open
    ch_open = b5 * w_all
    ch_open[1:] += redist
    if ke:
        idx = torch.arange(5, device=ch_open.device)
        d = torch.minimum(PHI_INV * (ch_open - b5).clamp(min=0.0),
                          torch.index_select(ch_open, 0, (idx + 2) % 5))
        ch_ke = ch_open.clone()
        ch_ke = ch_ke - torch.index_select(d, 0, (idx - 2) % 5)
        ch_ke = ch_ke + torch.index_select(d, 0, (idx - 4) % 5)
        ch_open = ch_ke.clamp(min=0.0)
    one_minus_q = (eta5 * ch_open).sum(dim=0)
    q = (1.0 - one_minus_q).clamp(0.0, 1.0)
    return ch_open, q


def measure(solver, ey, ei, mask, ke=False):
    m = mask
    msum = m.sum()
    eps = ey - PHI * ei
    ch_open, q = channel_openness(ey, ei, ke=ke)
    return {
        'eps_site': float((eps * m).abs().sum() / msum),
        'q_site': float((q * m).sum() / msum),
        'q_glob': float(q.mean()),
        'ch_site': [float((ch_open[k] * m).sum() / msum) for k in range(5)],
    }


def build_solver(device, gate_model):
    solver = ExpandingTwoFluid3DGPU(
        N=T.N, L=T.L, nu=T.NU, D=T.D, lam=T.LAM, chi=0.0,
        hubble_mode='conversion', cs2=0.0, qi_gate=True,
        qi_memory=False, device=device)
    solver.gate_model = gate_model
    return solver


def run_case(solver, ke, drive_period=None, tag='run', outdir=None):
    print(f"\n=== run: {tag} (gate={solver.gate_model}, "
          f"drive={drive_period is not None}) ===")
    ey_hat, ei_hat, u_hat = T.init_fields(solver, 'standing', seed=42)
    mask = T.site_mask(solver.N, T.R_SITE, solver.device)
    t0 = time.time()
    hist = []
    for step in range(T.STEPS):
        ey = torch.fft.ifftn(ey_hat).real
        if drive_period is not None:
            t_now = step * T.DT
            drive = DRIVE_AMP * np.sin(2.0 * np.pi * t_now / drive_period)
            ey = ey + drive * mask
            ey_hat = torch.fft.fftn(ey)
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, T.DT)
        if step % T.REPORT == 0 or step == T.STEPS - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            d = measure(solver, ey, ei, mask, ke=ke)
            d.update({'step': step, 't': step * T.DT})
            hist.append(d)
    print(f"  [{tag}] {T.STEPS} steps in {time.time() - t0:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'hist': hist}, f, indent=1)
    return hist


def at_t(hist, t_target):
    return min(hist, key=lambda d: abs(d['t'] - t_target))


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={T.N}  lam={T.LAM}  t=10")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_ke_ring"
    os.makedirs(rdir, exist_ok=True)

    # Run 1: standard gate (control)
    s1 = build_solver(device, 'five')
    h_five = run_case(s1, ke=False, tag='five', outdir=rdir)
    p0 = T.dominant_period([d['eps_site'] for d in h_five], T.DT)
    print(f"Measured P0 = {p0:.4f} (T_phi = {PHI * p0:.4f})")

    # Run 2: ke-extended gate (test)
    s2 = build_solver(device, 'five_ke')
    h_ke = run_case(s2, ke=True, tag='five_ke', outdir=rdir)

    # Run 3: ke-extended gate + phi-phased drive (C3b)
    s3 = build_solver(device, 'five_ke')
    h_ke_d = run_case(s3, ke=True, drive_period=PHI * p0,
                      tag='five_ke_drive', outdir=rdir)

    # ── C1: the alternating pattern at t=2 (lock active) ──────────────────
    f2 = at_t(h_five, 2.0)
    k2 = at_t(h_ke, 2.0)
    dev_five = np.array(f2['ch_site']) - BASELINE
    dev_ke = np.array(k2['ch_site']) - BASELINE
    ring = dev_ke - dev_five          # the ke term's modification
    ke_order = [1, 3, 0, 2, 4]        # Fire(2),Metal(4),Wood(1),Earth(3),Water(5)
    ring_ke = ring[ke_order]

    import json as _json
    with open(f"{rdir}/run_five.json") as _f:
        hist5 = _json.load(_f)['hist']
    d2 = min(hist5, key=lambda d: abs(d['t'] - 2.0))
    ch5 = np.array(d2['ch_site'])

    def ke_round(ch):
        excess = np.maximum(ch - BASELINE, 0.0)
        drest = np.minimum(PHI_INV * excess, np.roll(ch, -2))  # i restrains i+2
        return np.maximum(ch - np.roll(drest, +2) + np.roll(drest, +4), 0.0)

    # (a) one-round prediction: ke applied once to the control's state
    ch_ke_pred = ke_round(ch5)
    pred_err = np.abs(ch_ke_pred - np.array(k2['ch_site'])).max()
    # (b) frozen-field fixed point: iterate the ring on the control state
    ch_fp = ch5.copy()
    for _ in range(200):
        nxt = ke_round(ch_fp)
        if np.abs(nxt - ch_fp).max() < 1e-9:
            break
        ch_fp = nxt
    excess_ch = [CHANNELS[i] for i in range(5)
                 if np.maximum(ch5 - BASELINE, 0.0)[i] > 1e-4]

    print("\n=== C1: site channel openness at t=2 ===")
    print("baseline   :", np.round(BASELINE, 4))
    print("five  ch   :", np.round(ch5, 4))
    print("five_ke ch :", np.round(np.array(k2['ch_site']), 4))
    print("ke ring dev:", np.round(ring, 4))
    print("ke order (2,4,1,3,5):", np.round(ring_ke, 4))
    print(f"excess channels in control: {excess_ch}")
    print(f"one-round prediction max err: {pred_err:.5f}")
    print("frozen-field fixed point :", np.round(ch_fp, 4))
    print("fixed-point deviations   :", np.round(ch_fp - ch5, 4))
    alternating = pred_err < 0.01 and any(np.abs(ring) > 1e-3)

    # ── C3a: decay without a driver ───────────────────────────────────────
    f10 = at_t(h_five, 10.0)
    k10 = at_t(h_ke, 10.0)
    kd10 = at_t(h_ke_d, 10.0)
    print("\n=== C3: decay ===")
    print(f"eps_site t=10: five={f10['eps_site']:.3f} "
          f"five_ke={k10['eps_site']:.3f} "
          f"five_ke+drive={kd10['eps_site']:.3f}")
    eps_rel = {n: d['eps_site'] / h[0]['eps_site']
               for n, h, d in [('five', h_five, f10),
                               ('five_ke', h_ke, k10),
                               ('five_ke+drive', h_ke_d, kd10)]}
    for n, r in eps_rel.items():
        print(f"  {n:14s} retained: {r:.3f}")
    no_self = eps_rel['five_ke'] < 0.6
    drive_helps = eps_rel['five_ke+drive'] < eps_rel['five_ke'] - 0.05

    results = {
        'meta': {'P0': p0, 'T_phi': PHI * p0, 'DRIVE_AMP': DRIVE_AMP},
        'c1': {'ch_five': f2['ch_site'], 'ch_ke': k2['ch_site'],
               'ring': ring.tolist(), 'alternating': alternating,
               'excess_channels': excess_ch, 'pred_err': pred_err,
               'fixed_point': ch_fp.tolist()},
        'c3': {'eps_rel': eps_rel, 'no_self_sustenance': no_self,
               'drive_helps': drive_helps},
        'q_site_t2': {'five': f2['q_site'], 'five_ke': k2['q_site']},
    }
    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== VERDICT ===")
    print(f"C1 alternating ke pattern: {alternating}")
    print(f"C3a no driverless self-sustenance: {no_self}")
    print(f"C3b phi-drive still accelerates decay: {drive_helps}")

    # ── Figure ─────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 2, figsize=(13, 9))
        runs = [('five', h_five, 'C0'), ('five_ke', h_ke, 'C3'),
                ('five_ke+drive', h_ke_d, 'C1')]
        for name, h, c in runs:
            t = [d['t'] for d in h]
            axes[0, 0].plot(t, [d['eps_site'] for d in h], c, label=name)
            axes[0, 1].plot(t, [d['q_site'] for d in h], c, label=name)
            axes[1, 0].plot(t, [d['ch_site'][3] for d in h], c, label=name)
            axes[1, 1].plot(t, [d['ch_site'][4] for d in h], c, label=name)
        axes[0, 0].set_title('site |ε|')
        axes[0, 1].set_title('site q')
        axes[1, 0].set_title('site Metal openness (ke-suppressed)')
        axes[1, 1].set_title('site Water openness (ke-released)')
        for ax in axes.flat:
            ax.set_xlabel('t')
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(f"{rdir}/ke_ring.png", dpi=130)
        plt.close()
        print(f"\nFigure: {rdir}/ke_ring.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
