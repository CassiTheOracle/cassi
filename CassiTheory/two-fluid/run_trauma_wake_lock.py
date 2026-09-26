#!/usr/bin/env python3
"""Trauma wake-lock PDE test: does a standing wave pin the 5-channel Qi gate?

Test design: `consciousness/trauma-as-frozen-gate.md` §10.

Binary question: does a *pinned* (standing-wave) perturbation keep the local
Qi gate locked—channel openness displaced, q depressed below the field's
global value, sigma_r elevated—while a *radiating* perturbation lets the
site relax back to baseline?

Runs (minimal protocol, no sweeps):
  1. standing —epsilon-perturbation as a pinned cosine pattern
                 (cos kx · cos ky · cos kz), the frozen-wake analog
  2. radiating—same peak amplitude as a localized Gaussian packet,
                 the healthy-stimulus analog
  3. random   —independent random fields, no organized structure
                 (clean counterfactual / baseline calibration)
  4. drive    —standing + a phi-phased oscillation at the site (EMDR
                 analog); run only if run 1 shows pinning and a dominant
                 oscillation period is found

Solver: ExpandingTwoFluid3DGPU with qi_gate=True, gate_model='five'
(the 5-channel Wu Xing gate with adiabatic redistribution).

Verdict quantities at the site (ball around the box center):
  eps_rms_site   perturbation amplitude (epsilon = EY - phi*EI)
  q_site, q_glob 5-channel Qi coherence (site vs global)
  ch_open[5]     per-channel openness at the site
  fire_frac      fraction of site cells whose phase angle sits in the
                 Fire channel (72 deg)—the displacement marker
  sigma_r_site   spatial dispersion of r = EY/EI at the site

Usage: python two-fluid/run_trauma_wake_lock.py
Output: runs/<id>_wake_lock/results.json + figure
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

# ── Parameters ────────────────────────────────────────────────────────────
N = 48
L = 2.0 * np.pi
DT = 0.001
STEPS = 10000       # t_max = 10: dispersal timescale is sigma/c ~ 4+
REPORT = 50         # measurement cadence (steps)
LAM = 0.1
D = 0.0002
NU = 0.0005
AMP = 0.8              # peak perturbation amplitude (Yang deficit)
SIG = 4.0              # Gaussian sigma in cells
R_SITE = 6.0           # site ball radius in cells (covers the core)
DRIVE_AMP = 0.3        # EMDR-analog drive amplitude
PHI_MULT = PHI         # drive period = PHI * natural period

# Pentagonal phase channels: theta_k = 2*pi*k/5
CH_ANGLES = np.array([2.0 * np.pi * k / 5.0 for k in range(5)])


def site_mask(N_, radius, device):
    """Ball of `radius` cells around the box center, with periodic wrapping.

    Uses the correct periodic distance: dx = min((x-c) mod N, (c-x) mod N).
    (The naive (x-c) % N is a floor modulo and maps -1 -> N-1, which would
    distort the ball and dilute localized diagnostics.)
    """
    x = torch.arange(N_, dtype=torch.float64, device=device)
    dx = torch.minimum((x - N_ / 2) % N_, (N_ / 2 - x) % N_)
    d2 = dx.unsqueeze(1).unsqueeze(2) ** 2 + \
         dx.unsqueeze(0).unsqueeze(2) ** 2 + \
         dx.unsqueeze(0).unsqueeze(1) ** 2
    return (torch.sqrt(d2) <= radius).to(torch.float64)


def build_solver(device):
    solver = ExpandingTwoFluid3DGPU(
        N=N, L=L, nu=NU, D=D, lam=LAM, chi=0.0,
        hubble_mode='conversion', cs2=0.0, qi_gate=True,
        qi_memory=False, device=device)
    solver.gate_model = 'five'   # 5-channel gate with adiabatic redistribution
    return solver


def init_fields(solver, kind, seed=42):
    """Return (ey_hat, ei_hat, u_hat) for the given perturbation kind."""
    N_ = solver.N
    dev = solver.device
    gen = torch.Generator(device=dev)
    gen.manual_seed(seed)

    ey = torch.ones((N_,) * 3, dtype=torch.float64, device=dev)
    ei = torch.full((N_,) * 3, PHI_INV, dtype=torch.float64, device=dev)

    x = torch.arange(N_, dtype=torch.float64, device=dev)
    X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')

    if kind == 'standing':
        # Pinned cosine pattern: anti-node of Yang DEFICIT at the box center.
        # cos(2pi x/L) = -1 at x = L/2, so +AMP*prod gives -AMP at center.
        xc = x * (L / N_)
        pattern = (torch.cos(2.0 * np.pi * xc / L).unsqueeze(1).unsqueeze(2) *
                   torch.cos(2.0 * np.pi * xc / L).unsqueeze(0).unsqueeze(2) *
                   torch.cos(2.0 * np.pi * xc / L).unsqueeze(0).unsqueeze(0))
        ey = ey + AMP * pattern
    elif kind == 'radiating':
        # Localized Gaussian packet, same peak amplitude.
        r2 = (X - N_ / 2) ** 2 + (Y - N_ / 2) ** 2 + (Z - N_ / 2) ** 2
        ey = ey - AMP * torch.exp(-r2 / (2.0 * SIG ** 2))
    elif kind == 'random':
        ey = ey + 0.05 * torch.randn((N_,) * 3, generator=gen,
                                     device=dev, dtype=torch.float64)
        ei = ei + 0.05 * torch.randn((N_,) * 3, generator=gen,
                                     device=dev, dtype=torch.float64)
    else:
        raise ValueError(kind)

    ey = torch.clamp(ey, min=1e-3)
    ei = torch.clamp(ei, min=1e-3)
    u_hat = torch.zeros(3, N_, N_, N_, dtype=torch.complex128, device=dev)
    return torch.fft.fftn(ey), torch.fft.fftn(ei), u_hat


def channel_openness(ey, ei, phi_inv2=PHI_INV ** 2):
    """Per-cell 5-channel openness (replicates the solver's 'five' gate).

    Returns (ch_open[5], q) matching the gate formulas in the solver.
    """
    M = (ey + ei) ** 2
    eps_sq = (ey - PHI * ei) ** 2
    eps_norm = eps_sq / (eps_sq + M + phi_inv2 + 1e-30)
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
    one_minus_q = (eta5 * ch_open).sum(dim=0)
    q = (1.0 - one_minus_q).clamp(0.0, 1.0)
    return ch_open, q


def measure(solver, ey, ei, mask):
    """Site + global diagnostics at the current state."""
    dev = solver.device
    m = mask
    msum = m.sum()
    eps = ey - PHI * ei

    eps_site = float((eps * m).abs().sum() / msum)
    eps_glob = float(eps.abs().mean())

    ch_open, q = channel_openness(ey, ei)
    q_site = float((q * m).sum() / msum)
    q_glob = float(q.mean())

    ch_site = [float((ch_open[k] * m).sum() / msum) for k in range(5)]

    # Phase-angle channel histogram at the site
    theta = torch.atan2(ei, ey)
    nearest = (theta.unsqueeze(0) - torch.tensor(CH_ANGLES, device=dev,
                                                 dtype=torch.float64)
               .unsqueeze(-1).unsqueeze(-1).unsqueeze(-1)).abs().argmin(dim=0)
    counts = torch.bincount(nearest[m == 1].long(), minlength=5).to(torch.float64)
    frac = counts / msum

    r = ey / ei
    sigma_r_site = float((r * m).std() if msum > 1 else 0.0)

    return {
        'eps_site': eps_site, 'eps_glob': eps_glob,
        'q_site': q_site, 'q_glob': q_glob,
        'ch_open': ch_site,
        'phase_frac': frac.tolist(),
        'sigma_r_site': sigma_r_site,
    }


def dominant_period(t_series, dt):
    """Dominant oscillation period from a time series (FFT peak, no DC)."""
    y = np.array(t_series)
    y = y - y.mean()
    if len(y) < 8 or y.std() < 1e-9:
        return None
    spec = np.abs(np.fft.rfft(y))
    freqs = np.fft.rfftfreq(len(y), d=dt)
    spec[0] = 0.0
    pk = int(np.argmax(spec))
    if spec[pk] < 2.0 * spec[1:].mean():
        return None
    return 1.0 / freqs[pk] if freqs[pk] > 0 else None


def run_case(solver, kind, drive_period=None, seed=42, outdir=None):
    """Evolve one case, recording site diagnostics every REPORT steps."""
    tag = kind if drive_period is None else f"{kind}+drive"
    print(f"\n=== run: {tag} ===")
    ey_hat, ei_hat, u_hat = init_fields(solver, kind, seed=seed)
    mask = site_mask(solver.N, R_SITE, solver.device)
    t0 = time.time()
    hist = []

    for step in range(STEPS):
        ey = torch.fft.ifftn(ey_hat).real
        if drive_period is not None:
            # EMDR analog: phi-phased oscillation re-injected at the site
            t_now = step * DT
            drive = DRIVE_AMP * np.sin(2.0 * np.pi * t_now / drive_period)
            ey = ey + drive * mask
            ey_hat = torch.fft.fftn(ey)
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, DT)

        if step % REPORT == 0 or step == STEPS - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            d = measure(solver, ey, ei, mask)
            d.update({'step': step, 't': step * DT})
            hist.append(d)
            print(f"  t={step*DT:5.2f} | eps_site={d['eps_site']:.4f} "
                  f"| q_site={d['q_site']:.3f} q_glob={d['q_glob']:.3f} "
                  f"| sig_r={d['sigma_r_site']:.4f} "
                  f"| phase={['%.2f' % f for f in d['phase_frac']]}")

    elapsed = time.time() - t0
    print(f"  [{tag}] {STEPS} steps in {elapsed:.1f}s")
    if outdir:
        with open(f"{outdir}/run_{tag}.json", "w") as f:
            json.dump({'kind': tag, 'hist': hist}, f, indent=1)
    return hist


def summarize(name, hist):
    """Verdict quantities: how much the site stayed displaced at t_end."""
    first, last = hist[0], hist[-1]
    eps_rel = last['eps_site'] / max(first['eps_site'], 1e-12)
    q_gap = last['q_glob'] - last['q_site']
    phase0 = np.array(first['phase_frac'])
    phase1 = np.array(last['phase_frac'])
    displ0 = 1.0 - phase0[0]      # fraction NOT in Wood at start
    displ1 = 1.0 - phase1[0]      # fraction NOT in Wood at end
    sigma_rel = last['sigma_r_site'] / max(first['sigma_r_site'], 1e-12)
    return {
        'eps_rel': eps_rel, 'q_gap': q_gap,
        'displ_start': displ0, 'displ_end': displ1,
        'sigma_rel': sigma_rel,
    }


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}  N={N}  steps={STEPS}  dt={DT}  "
          f"lam={LAM}  qi_gate=5ch")

    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_wake_lock"
    os.makedirs(rdir, exist_ok=True)

    solver = build_solver(device)

    results = {'meta': {'N': N, 'steps': STEPS, 'dt': DT, 'lam': LAM,
                        'amp': AMP, 'sigma_cells': SIG},
               'runs': {}}

    # Run 1: standing (diagnostic)
    h1 = run_case(solver, 'standing', outdir=rdir)
    results['runs']['standing'] = summarize('standing', h1)
    s = results['runs']['standing']
    print(f"  [standing] eps_rel={s['eps_rel']:.2f} q_gap={s['q_gap']:+.3f} "
          f"displ {s['displ_start']:.2f}->{s['displ_end']:.2f} "
          f"sigma_rel={s['sigma_rel']:.2f}")

    # Run 2: radiating (control)
    h2 = run_case(solver, 'radiating', outdir=rdir)
    results['runs']['radiating'] = summarize('radiating', h2)
    s = results['runs']['radiating']
    print(f"  [radiating] eps_rel={s['eps_rel']:.2f} q_gap={s['q_gap']:+.3f} "
          f"displ {s['displ_start']:.2f}->{s['displ_end']:.2f} "
          f"sigma_rel={s['sigma_rel']:.2f}")

    # Run 3: random (clean counterfactual)
    h3 = run_case(solver, 'random', seed=7, outdir=rdir)
    results['runs']['random'] = summarize('random', h3)
    s = results['runs']['random']
    print(f"  [random] eps_rel={s['eps_rel']:.2f} q_gap={s['q_gap']:+.3f} "
          f"displ {s['displ_start']:.2f}->{s['displ_end']:.2f}")

    # Run 4 (conditional): standing + phi-phased drive, EMDR analog
    p0 = dominant_period([d['eps_site'] for d in h1], DT)
    pinned = (results['runs']['standing']['eps_rel'] > 0.5 and
              results['runs']['standing']['q_gap'] > 0.02)
    if pinned and p0 is not None:
        t_drive = PHI_MULT * p0
        print(f"\n  Standing pinned; natural period P0={p0:.3f}; "
              f"drive period T=phi*P0={t_drive:.3f}")
        h4 = run_case(solver, 'standing', drive_period=t_drive, seed=42,
                      outdir=rdir)
        results['runs']['drive'] = summarize('drive', h4)
        s = results['runs']['drive']
        print(f"  [drive] eps_rel={s['eps_rel']:.2f} "
              f"q_gap={s['q_gap']:+.3f} "
              f"displ {s['displ_start']:.2f}->{s['displ_end']:.2f}")
    else:
        reason = 'not pinned' if not pinned else 'no dominant period'
        print(f"\n  Skipping drive run: {reason} (pinned={pinned}, P0={p0})")

    with open(f"{rdir}/results.json", "w") as f:
        json.dump(results, f, indent=2)

    # ── Verdict ────────────────────────────────────────────────────────────
    print("\n=== VERDICT ===")
    st, ra = results['runs']['standing'], results['runs']['radiating']
    lock = (st['eps_rel'] > 0.5 and st['q_gap'] > 0.02 and
            st['displ_end'] > 0.5 * st['displ_start'])
    relax = ra['eps_rel'] < 0.5
    print(f"Standing:  eps_rel={st['eps_rel']:.2f} q_gap={st['q_gap']:+.3f} "
          f"displacement kept={st['displ_end']/max(st['displ_start'],1e-12):.0%}")
    print(f"Radiating: eps_rel={ra['eps_rel']:.2f} q_gap={ra['q_gap']:+.3f} "
          f"displacement kept={ra['displ_end']/max(ra['displ_start'],1e-12):.0%}")
    if lock and relax:
        print("*** LOCK MECHANISM SUPPORTED: pinned perturbation keeps the "
              "gate displaced while the radiating one relaxes. ***")
    elif lock and not relax:
        print("PARTIAL: standing pins, but the radiating case also does not "
              "relax within this run length—timescale may exceed t_max.")
    elif not lock and relax:
        print("NEGATIVE: the standing pattern does NOT pin the gate in this "
              "PDE—the frozen wake requires a driven source, or the "
              "pinning mechanism is absent.")
    else:
        print("INCONCLUSIVE: neither case shows the expected contrast.")

    # ── Figure ─────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 2, figsize=(13, 9))
        runs = [('standing', h1, 'C0'), ('radiating', h2, 'C3'),
                ('random', h3, 'gray')]
        for name, h, c in runs:
            t = [d['t'] for d in h]
            axes[0, 0].plot(t, [d['eps_site'] for d in h], c, label=name)
            axes[0, 1].plot(t, [d['q_site'] for d in h], c, label=name)
            axes[1, 0].plot(t, [d['phase_frac'][1] for d in h], c,
                            label=name)
            axes[1, 1].plot(t, [d['sigma_r_site'] for d in h], c, label=name)
        axes[0, 0].set_title('site |ε| (perturbation amplitude)')
        axes[0, 1].set_title('site q (5-channel coherence)')
        axes[1, 0].set_title('site Fire-channel fraction (displacement)')
        axes[1, 1].set_title('site σ_r (dispersion of r = EY/EI)')
        for ax in axes.flat:
            ax.set_xlabel('t')
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(f"{rdir}/wake_lock.png", dpi=130)
        plt.close()
        print(f"\nFigure: {rdir}/wake_lock.png")
    except Exception as e:
        print(f"\nFigure skipped: {e}")

    print(f"Results: {rdir}/results.json")


if __name__ == "__main__":
    main()
