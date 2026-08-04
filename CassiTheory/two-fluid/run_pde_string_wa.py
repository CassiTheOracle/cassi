#!/usr/bin/env python3
"""
String-Seeded PDE w_a Pipeline: pinch-localized 5-channel gate vs homogeneous ODE
==================================================================================

Seeds a coherence string (constant-density, r=phi region) along the cascade (z)
axis in the 3D expanding two-fluid PDE with the 5-channel Wu Xing gate.
Extracts spatially-resolved (1-q) decomposed by conversion activity, computes
w(a) and fits w_0, w_a, and compares against the homogeneous ODE baseline.

Usage:
    python run_pde_string_wa.py --N 32 --steps 2000
    python run_pde_string_wa.py --N 48 --steps 4000
"""

import argparse, os, sys, time, math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI, PHI_INV


# ═══════════════════════════════════════════════════════════════════════════
# §1  String seeding—constant-density phi-equilibrium cylinder
# ═══════════════════════════════════════════════════════════════════════════

def seed_string(solver, string_radius=0.25, pinch_z=0.5, pinch_width=0.08,
                pinch_depth=0.4, background_amp=0.05, seed=42):
    """Seed a coherence string: constant-total-density cylinder with r=phi.

    Background: Yin-dominated (r << phi), gate open, conversion active.
    String: same total density as background, but r=phi inside (high q,
    conversion stalled). Pinch at z=pinch_z*L where the gate is most active.

    No density contrast = no advective destruction. The string persists as
    a purely ratio-based spatial feature.
    """

    # Background: Yin-dominated with r ≈ 0.05 (matching ODE r_start)
    # Bypass initial_expanding—its min=0.1 clamp raises EY above target.
    N, L = solver.N, solver.L
    gen = torch.Generator(device=solver.device)
    gen.manual_seed(seed)
    ei_bg = 1.0 + 0.03 * torch.randn((N, N, N), generator=gen,
                                     device=solver.device, dtype=torch.float64)
    ey_bg = 0.05 * ei_bg + 0.01 * torch.randn((N, N, N), generator=gen,
                                               device=solver.device, dtype=torch.float64)
    ey_bg = torch.clamp(ey_bg, min=1e-3)
    ei_bg = torch.clamp(ei_bg, min=1e-3)
    r_bg = (ey_bg.mean() / (ei_bg.mean() + 1e-12)).item()
    rho_bg = ey_bg + ei_bg

    u_hat = [torch.fft.fftn(0.02 * torch.randn((N, N, N), generator=gen,
                                                device=solver.device, dtype=torch.float64))
             for _ in range(3)]

    # String geometry
    dx = solver.dx
    z = torch.arange(0, L, step=dx, device=solver.device, dtype=torch.float64)
    ZZ, YY, XX = torch.meshgrid(z, z, z, indexing='ij')
    radius = torch.sqrt((XX - L/2)**2 + (YY - L/2)**2)

    z0 = pinch_z * L
    pinch_prof = 1.0 - pinch_depth * torch.exp(
        -((ZZ - z0)**2) / (2 * pinch_width**2 * L**2))
    r_eff = string_radius * pinch_prof.clamp(0.05, 1.0)  # narrower at pinch
    string_env = torch.exp(-radius**2 / (2 * r_eff**2 * L**2))
    w = string_env.clamp(0.0, 1.0)  # core → w=1 → full r=φ

    # Target: r=phi at same total density
    ey_phi = PHI * rho_bg / (1.0 + PHI)
    ei_phi = rho_bg / (1.0 + PHI)

    # Blend: w=0 → bg, w=1 → phi-string
    ey = (1.0 - w) * ey_bg + w * ey_phi
    ei = (1.0 - w) * ei_bg + w * ei_phi
    ey = torch.clamp(ey, min=1e-3)
    ei = torch.clamp(ei, min=1e-3)

    return u_hat, torch.fft.fftn(ey), torch.fft.fftn(ei), r_bg


def compute_regions(solver, ey, ei):
    """Decompose space by conversion activity: conv = (1-q) * |EY - phi*EI|.

    String:  conv < 10% of median  (near equilibrium)
    Active:  conv >= 10% of median  (conversion active)
    Inert:   density < 1% of mean
    """
    q, omq = solver.compute_q_field(ey, ei)
    conv = omq * torch.abs(ey - PHI * ei)
    conv_lo = 0.1 * conv.median()
    rho = ey + ei
    rho_floor = rho.mean() * 0.01

    ms = (conv < conv_lo) & (rho > rho_floor)
    ma = (conv >= conv_lo) & (rho > rho_floor)
    mi = rho <= rho_floor
    return q, omq, conv, ms, ma, mi


# ═══════════════════════════════════════════════════════════════════════════
# §2  PDE evolution
# ═══════════════════════════════════════════════════════════════════════════

def run_pde(args):
    dev = 'cuda' if (args.gpu and torch.cuda.is_available()) else 'cpu'
    rid = datetime.now().strftime('%Y%m%d_%H%M%S') + '_str_wa'
    run_dir = os.path.join('runs', rid)
    os.makedirs(run_dir, exist_ok=True)

    solver = ExpandingTwoFluid3DGPU(
        N=args.N, L=2.0*np.pi, nu=args.nu, D=args.D, lam=args.lam,
        chi=0.0, a0=args.a0, initial_ratio=None,
        hubble_mode=args.hubble_mode, max_H=args.max_H,
        h_smooth=args.h_smooth, qi_gate=True,
        mode='cosmos', device=dev)
    solver.gate_model = 'five'

    u_hat, ey_hat, ei_hat, r_bg = seed_string(
        solver, string_radius=args.string_r, pinch_z=args.pinch_z,
        pinch_width=args.pinch_w, pinch_depth=args.pinch_d,
        background_amp=args.bg_amp, seed=args.seed)

    ey0 = torch.fft.ifftn(ey_hat).real
    ei0 = torch.fft.ifftn(ei_hat).real
    q0, _, _, ms0, ma0, _ = compute_regions(solver, ey0, ei0)
    r0 = (ey0.mean() / (ei0.mean() + 1e-12)).item()
    print(f'N={args.N} steps={args.steps} lam={args.lam} gate=five  device={dev}')
    print(f'r_bg={r_bg:.4f} r0={r0:.4f} q0={q0.mean().item():.4f} '
          f'f_str={ms0.sum().item()/ms0.numel():.3f} '
          f'f_act={ma0.sum().item()/ma0.numel():.3f}')
    print(f'{"step":>6s} {"a":>10s} {"H":>10s} {"r":>8s} {"q":>8s} '
          f'{"f_str":>8s} {"f_act":>8s} {"omq_s":>8s} {"omq_a":>8s}')
    print('-' * 82)

    logfile = os.path.join(run_dir, 'log.txt')
    with open(logfile, 'w') as f:
        f.write(f'# N={args.N} lam={args.lam} gate=five steps={args.steps}\n'
                f'# step a H r q_mean omq_vol omq_str omq_act '
                f'conv_med f_str f_act\n')

    t0 = time.time()
    snaps = []
    for step in range(args.steps + 1):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, args.dt)

        if step % args.report == 0 or step == args.steps:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            a = solver.a.item(); H = solver.H.item()
            r_val = (ey.mean() / (ei.mean() + 1e-12)).item()

            q, omq, cr, ms, ma, mi = compute_regions(solver, ey, ei)
            nt = float(ms.numel())
            fs = ms.sum().item() / nt
            fa = ma.sum().item() / nt
            ov = omq.mean().item()
            os_ = omq[ms].mean().item() if ms.sum() > 0 else 0.0
            oa = omq[ma].mean().item() if ma.sum() > 0 else 0.0
            cm = cr.median().item()
            qm = q.mean().item()

            snaps.append(dict(
                step=step, a=a, H=H, r=r_val, q_mean=qm,
                omq_vol=ov, omq_string=os_, omq_active=oa,
                conv_median=cm, frac_string=fs, frac_active=fa,
                q=q.cpu().numpy().copy(),
                conv_rate=cr.cpu().numpy().copy()))

            with open(logfile, 'a') as f:
                f.write(f'{step:6d} {a:10.6e} {H:10.6e} {r_val:8.4f} '
                        f'{qm:8.4f} {ov:10.6e} {os_:10.6e} '
                        f'{oa:10.6e} {cm:10.6e} {fs:10.6e} {fa:10.6e}\n')

            if step % (args.report * 5) == 0 or step == args.steps:
                print(f'{step:6d} {a:10.4f} {H:10.4f} {r_val:8.4f} '
                      f'{qm:8.4f} {fs:8.3f} {fa:8.3f} {os_:8.4f} {oa:8.4f}')

    elapsed = time.time() - t0
    print(f'\nDone in {elapsed:.1f}s ({elapsed/max(args.steps,1):.4f}s/step)')
    return solver, snaps, run_dir


# ═══════════════════════════════════════════════════════════════════════════
# §3  w(a) from H(a)
# ═══════════════════════════════════════════════════════════════════════════

def compute_w_from_snaps(snaps):
    a = np.array([s['a'] for s in snaps])
    H = np.array([s['H'] for s in snaps])
    n = len(a)
    dln = np.zeros(n)
    for i in range(1, n-1):
        da = a[i+1] - a[i-1]
        if da > 0 and H[i] > 0:
            dln[i] = (a[i]/H[i]) * (H[i+1]-H[i-1]) / da
    if H[0] > 0 and a[1] > a[0]:
        dln[0] = (a[0]/H[0]) * (H[1]-H[0]) / (a[1]-a[0])
    if H[-1] > 0 and a[-1] > a[-2]:
        dln[-1] = (a[-1]/H[-1]) * (H[-1]-H[-2]) / (a[-1]-a[-2])
    return a, H, -1.0 - (2.0/3.0)*dln


def fit_w0_wa(a, w, a_min=0.3):
    mask = a >= a_min
    if mask.sum() < 3:
        mask = np.ones_like(a, dtype=bool)
    X = np.column_stack([np.ones_like(a[mask]), 1.0 - a[mask]])
    c = np.linalg.lstsq(X, w[mask], rcond=None)[0]
    return c[0], c[1]


# ═══════════════════════════════════════════════════════════════════════════
# §4  Homogeneous ODE (5-channel gate + xi)
# ═══════════════════════════════════════════════════════════════════════════

def q5(r):
    e, l = 0.438, 0.348
    return max(e + (l-e)/(1.0 + np.exp(-(r-PHI_INV)/0.3)), 0.0)


def run_ode(lam=0.1, xi=PHI**6, n_pts=20000):
    def H_eff(r):
        Hb = (lam/3)*PHI_INV**2 + (lam/3)*abs(PHI-r)*(1+r)/max(r,1e-12)
        return Hb * math.sqrt(1 + xi*(1-q5(r)))

    a = np.exp(np.linspace(math.log(0.01), 0, n_pts))
    r = np.zeros(n_pts); r[0] = 0.043
    for i in range(n_pts-1):
        am = 0.5*(a[i]+a[i+1])
        Hv = H_eff(r[i])
        drda = -lam*q5(r[i])*(r[i]-PHI)*(1+r[i]) / (Hv*am) if Hv>0 else 0
        r[i+1] = np.clip(r[i]+drda*(a[i+1]-a[i]), 1e-15, PHI-1e-15)

    Hv = np.array([H_eff(rr) for rr in r])
    dln = np.zeros(n_pts)
    for i in range(1, n_pts-1):
        da = a[i+1]-a[i-1]
        if da>0 and Hv[i]>0:
            dln[i] = (a[i]/Hv[i])*(Hv[i+1]-Hv[i-1])/da
    if Hv[0]>0: dln[0] = (a[0]/Hv[0])*(Hv[1]-Hv[0])/(a[1]-a[0])
    if Hv[-1]>0: dln[-1] = (a[-1]/Hv[-1])*(Hv[-1]-Hv[-2])/(a[-1]-a[-2])
    w = -1.0 - (2.0/3.0)*dln
    return a, w, *fit_w0_wa(a, w), r


# ═══════════════════════════════════════════════════════════════════════════
# §5  Diagnostic plots
# ═══════════════════════════════════════════════════════════════════════════

BG = '#060612'
YG, YI, GN, RD, TM, TS, RI, WH = (
    '#E8B830','#4A6DB5','#4ECDC4','#E84855',
    '#D0D0D0','#808090','#303040','#F0F0F0')

plt.rcParams.update({
    'figure.facecolor':BG,'axes.facecolor':BG,'text.color':TM,
    'axes.labelcolor':TM,'axes.edgecolor':RI,'xtick.color':TS,
    'ytick.color':TS,'grid.color':RI,'grid.alpha':0.3,
    'legend.facecolor':BG,'legend.edgecolor':RI,'figure.dpi':120})


def plot_diagnostics(solver, snaps, ode_res, run_dir):
    rd = Path(run_dir)

    ap = np.array([s['a'] for s in snaps])
    Hp = np.array([s['H'] for s in snaps])
    ov = np.array([s['omq_vol'] for s in snaps])
    os_ = np.array([s['omq_string'] for s in snaps])
    oa = np.array([s['omq_active'] for s in snaps])
    fs = np.array([s['frac_string'] for s in snaps])
    fa = np.array([s['frac_active'] for s in snaps])
    qm = np.array([s['q_mean'] for s in snaps])
    rv = np.array([s['r'] for s in snaps])

    aw, Hw, wp = compute_w_from_snaps(snaps)
    w0p, wap = fit_w0_wa(aw, wp)
    ao, wo, w0o, wao, ro = ode_res

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.patch.set_facecolor(BG)

    # A. (1-q) by region
    ax = axes[0,0]
    ax.plot(ap, ov, color=YG, lw=2, marker='o', ms=4, label='volume')
    ax.plot(ap, os_, color=GN, lw=2, marker='s', ms=3, label='string')
    ax.plot(ap, oa, color=RD, lw=1.5, marker='^', ms=3, label='active')
    ax.set(xlabel='a', ylabel=r'$\langle 1-q \rangle$',
           title='A. Gate openness by region')
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    # B. Volume fractions
    ax = axes[0,1]
    ax.fill_between(ap, 0, fs, color=GN, alpha=0.4, label='string')
    ax.fill_between(ap, fs, fs+fa, color=RD, alpha=0.3, label='active')
    ax.set(xlabel='a', ylabel='volume fraction',
           title='B. Region volume fractions')
    ax.legend(fontsize=8); ax.set_ylim(0,1); ax.grid(True, alpha=0.3)

    # C. q_mean and r
    ax = axes[0,2]
    ax.plot(ap, qm, color=YG, lw=2, label=r'$q_{\rm mean}$')
    ax2 = ax.twinx()
    ax2.plot(ap, rv, color=YI, lw=1.5, ls='--', label='r')
    ax2.axhline(y=PHI, color=TS, ls=':', lw=1, label=f'φ={PHI:.3f}')
    ax.set(xlabel='a', ylabel=r'$q_{\rm mean}$', title='C. Coherence & ratio')
    ax.grid(True, alpha=0.3)
    h1,l1 = ax.get_legend_handles_labels()
    h2,l2 = ax2.get_legend_handles_labels()
    ax.legend(h1+h2,l1+l2,fontsize=8)

    # D. w(a)
    ax = axes[1,0]
    ax.plot(ao, wo, color=YI, lw=2, ls='--',
            label=f'ODE 5ch+ξ: w₀={w0o:.3f}, wa={wao:+.3f}')
    ax.plot(aw, wp, color=YG, lw=2,
            label=f'PDE: w₀={w0p:.3f}, wa={wap:+.3f}')
    ax.axhline(y=-1.0, color=TS, ls=':', lw=1, label='Λ')
    ax.axhline(y=-0.87, color=GN, ls=':', lw=1, alpha=0.5)  # calibration target (DESI-anchored, Calibrated tier — see parameter-inventory §10 fit ledger); not a prediction — synced to doctrine settlement 2026-08-03
    ax.text(0.97, -0.877, 'calib. target (DESI-anchored, not a prediction)', color=GN, fontsize=7, ha='right')
    ax.set(xlabel='a', ylabel='w(a)',
           title='D. Dark energy equation of state')
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    # E. H(a)
    ax = axes[1,1]
    ax.plot(ap, Hp, color=YG, lw=2)
    ax.set(xlabel='a', ylabel='H', title='E. Hubble parameter')
    ax.grid(True, alpha=0.3)

    # F. Key numbers
    ax = axes[1,2]; ax.axis('off')
    lines = [
        ("STRING PDE w_a PIPELINE", 14, 'bold', YG),
        ("", 6, 'normal', TS),
        (f"N={solver.N}³  steps={len(snaps)}  λ={solver.lam}", 10, 'normal', TM),
        ("", 6, 'normal', TS),
        ("─── PDE ───", 12, 'bold', GN),
        (f"w₀ = {w0p:.4f}   w_a = {wap:+.4f}", 12, 'bold', YG),
        (f"⟨1−q⟩_vol = {ov[-1]:.4f}", 9, 'normal', TM),
        (f"⟨1−q⟩_str = {os_[-1]:.4f}", 9, 'normal', GN),
        (f"⟨1−q⟩_act = {oa[-1]:.4f}", 9, 'normal', RD),
        (f"f_str={fs[-1]:.3f}  f_act={fa[-1]:.3f}", 9, 'normal', TM),
        ("", 6, 'normal', TS),
        ("─── ODE 5ch+ξ ───", 12, 'bold', YI),
        (f"w₀ = {w0o:.4f}   w_a = {wao:+.4f}", 12, 'bold', YI),
        ("", 6, 'normal', TS),
        ("─── CALIBRATION TARGET (DESI-anchored, not a prediction) ───", 12, 'bold', WH),
        ("w₀=−0.87 ± 0.06", 9, 'normal', TM),
        ("w_a=+0.012 ± 0.28", 9, 'normal', TM),
        ("", 6, 'normal', TS),
        (f"Δw_a(PDE−ODE)={wap-wao:+.4f}", 10, 'bold',
         GN if abs(wap-wao)<0.1 else RD)]
    y = 0.96
    for txt,sz,wt,cl in lines:
        if txt:
            ax.text(0.04, y, txt, transform=ax.transAxes, fontsize=sz,
                    fontweight=wt, color=cl, va='top', family='monospace')
        y -= 0.04

    fig.suptitle('STRING-SEEDED PDE: Pinch-Localized 5-Channel Gate vs ODE',
                 fontsize=16, fontweight='bold', color=YG, y=0.99)
    fig.tight_layout(rect=[0,0,1,0.965])
    out = rd / 'string_wa_diag.png'
    fig.savefig(out, dpi=150, bbox_inches='tight', facecolor=BG)
    print(f'  Saved {out}')
    plt.close(fig)

    # Figure 2: q and conv_rate spatial slices
    fn = snaps[-1]
    qf, cf = fn['q'], fn['conv_rate']; N = qf.shape[0]
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    fig.patch.set_facecolor(BG)
    for row, (fld, cmap, label) in enumerate([
            (qf, 'inferno', 'q'), (cf, 'plasma', 'conv_rate')]):
        for col, (slc, title) in enumerate([
                (fld[N//2,:,:].T, f'{label}(x,y) pinch z=L/2'),
                (fld[:,N//2,:].T, f'{label}(z,x) through axis'),
                (fld[:,:,N//2].T, f'{label}(z,y) through axis')]):
            ax = axes[row,col]
            im = ax.imshow(slc, origin='lower', cmap=cmap,
                           extent=[0,solver.L,0,solver.L])
            ax.set_title(title, fontsize=9)
            plt.colorbar(im, ax=ax, fraction=0.046)
    fig.suptitle(f'q and conv_rate at a={fn["a"]:.4f}',
                 fontsize=13, fontweight='bold', color=YG)
    fig.tight_layout(rect=[0,0,1,0.95])
    out = rd / 'string_wa_slices.png'
    fig.savefig(out, dpi=150, bbox_inches='tight', facecolor=BG)
    print(f'  Saved {out}')
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════
# §6  Main
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    p = argparse.ArgumentParser(description='String-Seeded PDE w_a Pipeline')
    p.add_argument('--N', type=int, default=32)
    p.add_argument('--steps', type=int, default=2000)
    p.add_argument('--dt', type=float, default=0.0005)
    p.add_argument('--report', type=int, default=200)
    p.add_argument('--lam', type=float, default=0.1)
    p.add_argument('--D', type=float, default=0.0001)
    p.add_argument('--nu', type=float, default=0.0005)
    p.add_argument('--a0', type=float, default=0.01)
    p.add_argument('--max_H', type=float, default=0.5)
    p.add_argument('--h_smooth', type=float, default=0.05)
    p.add_argument('--hubble_mode', type=str, default='stress_energy')
    p.add_argument('--string_r', type=float, default=0.25)
    p.add_argument('--pinch_z', type=float, default=0.5)
    p.add_argument('--pinch_w', type=float, default=0.08)
    p.add_argument('--pinch_d', type=float, default=0.3)
    p.add_argument('--bg_amp', type=float, default=0.03)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--gpu', action='store_true', default=False)
    args = p.parse_args()

    print('=' * 65)
    print('  STRING-SEEDED PDE w_a PIPELINE')
    print('  Pinch-localized 5-channel gate vs homogeneous ODE')
    print('=' * 65)

    solver, snaps, run_dir = run_pde(args)
    if len(snaps) < 3:
        print('[ERROR] Too few snapshots.'); sys.exit(1)

    print('\n=== Homogeneous ODE (5ch + xi) ===')
    ao, wo, w0o, wao, ro = run_ode(lam=args.lam)
    print(f'  ODE:  w₀ = {w0o:.4f}  w_a = {wao:+.4f}')

    aw, Hw, wp = compute_w_from_snaps(snaps)
    w0p, wap = fit_w0_wa(aw, wp)
    print(f'\n  PDE:  w₀ = {w0p:.4f}  w_a = {wap:+.4f}')
    print(f'  Δw_a(PDE−ODE) = {wap-wao:+.4f}')
    print(f'  Calibration target (DESI-anchored, not a prediction):  w₀=−0.87±0.06  w_a=+0.012±0.28  [synced to doctrine settlement 2026-08-03]')

    fn = snaps[-1]
    print(f'\n  Final regions: f_str={fn["frac_string"]:.3f} '
          f'f_act={fn["frac_active"]:.3f}')
    print(f'  ⟨1−q⟩_vol={fn["omq_vol"]:.4f}  '
          f'⟨1−q⟩_str={fn["omq_string"]:.4f}  '
          f'⟨1−q⟩_act={fn["omq_active"]:.4f}')

    plot_diagnostics(solver, snaps, (ao, wo, w0o, wao, ro), run_dir)
    print(f'\n  Done. Results in {run_dir}/')
