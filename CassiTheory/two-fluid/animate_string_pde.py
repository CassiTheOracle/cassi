#!/usr/bin/env python3
"""
3D Animation of the String-Seeded Two-Fluid PDE
================================================

Renders an MP4 of the coherence-string PDE evolving under the 5-channel
Wu Xing gate. The left panel is a rotating 3D volumetric view (three
orthogonal slice planes colored by conversion activity conv = (1-q)|EY-phi*EI|,
plus scatter of the string and active voxels). The right column tracks the
cosmological diagnostics w(a), volume fractions, and H(a) with a moving
time cursor.

Reuses seed_string / compute_regions from run_pde_string_wa.py and the
ExpandingTwoFluid3DGPU solver from two-fluid/.

Usage:
    python animate_string_pde.py --N 32 --steps 1200 --report 40 --fps 12
    python animate_string_pde.py --N 48 --steps 4000 --report 80 --fps 24 --gpu

Output:
    runs/<timestamp>_anim/animation.mp4
    runs/<timestamp>_anim/frame_XXXX.png   (with --png)

Requires imageio-ffmpeg (pip install imageio-ffmpeg) for MP4 assembly; the
bundled ffmpeg binary is auto-detected. Falls back to a PNG frame sequence
if the encoder is unavailable.
"""

import argparse, os, sys, time, math, subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers 3d projection)
from matplotlib.animation import FFMpegWriter
from datetime import datetime
from pathlib import Path
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI, PHI_INV
from run_pde_string_wa import seed_string, compute_regions, compute_w_from_snaps


# ═══════════════════════════════════════════════════════════════════════════
# House palette
# ═══════════════════════════════════════════════════════════════════════════
BG       = '#060612'
YANG     = '#E8B830'   # Yang gold
YIN      = '#4A6DB5'   # Yin indigo
SAFE     = '#4ECDC4'   # safe green
DANGER   = '#E84855'   # danger red
TM       = '#D0D0D0'   # text main
TS       = '#808090'   # text sub
RI       = '#303040'   # ring/grid
WH       = '#F0F0F0'
YIN_DEEP = '#140a33'
YIN_MID  = '#2a1a5e'
YANG_DK  = '#5a3a10'
YANG_PEAK= '#ffe060'

plt.rcParams.update({
    'figure.facecolor': BG, 'axes.facecolor': BG, 'savefig.facecolor': BG,
    'text.color': TM, 'axes.labelcolor': TM, 'axes.edgecolor': RI,
    'xtick.color': TS, 'ytick.color': TS, 'grid.color': RI, 'grid.alpha': 0.3,
    'font.family': 'DejaVu Sans', 'mathtext.default': 'regular'})

# conv-rate colormap: dark -> yin indigo -> yang gold -> peak
CONV_CMAP = LinearSegmentedColormap.from_list(
    'cassi_conv', [BG, YIN_DEEP, YIN_MID, YIN, YANG_DK, YANG, YANG_PEAK])


def _ffmpeg_exe():
    """Locate an ffmpeg binary: imageio-ffmpeg bundle, else PATH."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        for cand in ('ffmpeg', 'ffmpeg.exe'):
            try:
                subprocess.run([cand, '-version'], capture_output=True, check=True)
                return cand
            except Exception:
                pass
    return None


# ═══════════════════════════════════════════════════════════════════════════
# §1  Run the PDE, collect snapshots with 3D fields
# ═══════════════════════════════════════════════════════════════════════════

def run_sim(args):
    dev = 'cuda' if (args.gpu and torch.cuda.is_available()) else 'cpu'
    rid = datetime.now().strftime('%Y%m%d_%H%M%S') + '_anim'
    run_dir = os.path.join('runs', rid)
    os.makedirs(run_dir, exist_ok=True)

    solver = ExpandingTwoFluid3DGPU(
        N=args.N, L=2.0 * np.pi, nu=args.nu, D=args.D, lam=args.lam,
        chi=0.0, a0=args.a0, initial_ratio=None,
        hubble_mode=args.hubble_mode, max_H=args.max_H,
        h_smooth=args.h_smooth, qi_gate=True, mode='cosmos', device=dev)
    solver.gate_model = 'five'

    u_hat, ey_hat, ei_hat, r_bg = seed_string(
        solver, string_radius=args.string_r, pinch_z=args.pinch_z,
        pinch_width=args.pinch_w, pinch_depth=args.pinch_d,
        background_amp=args.bg_amp, seed=args.seed)

    ey0 = torch.fft.ifftn(ey_hat).real
    ei0 = torch.fft.ifftn(ei_hat).real
    r0 = (ey0.mean() / (ei0.mean() + 1e-12)).item()
    print(f'N={args.N} steps={args.steps} report={args.report} lam={args.lam} '
          f'gate=five device={dev}')
    print(f'r_bg={r_bg:.4f} r0={r0:.4f}')

    snaps = []
    # precompute fixed geometry mask for the string cylinder
    z = torch.linspace(0, solver.L, solver.N, device=solver.device, dtype=torch.float64)
    _, YY, XX = torch.meshgrid(z, z, z, indexing='ij')
    r_xy = torch.sqrt((XX - solver.L/2)**2 + (YY - solver.L/2)**2)
    r_str_cyl = args.string_r * solver.L
    fix_str = (r_xy < r_str_cyl * 0.6).cpu().numpy()     # inner core (matches scatter)
    fix_bg  = (r_xy > r_str_cyl * 1.4).cpu().numpy()     # outer region (matches scatter)
    str_vol = float(fix_str.sum()) / float(fix_str.size)  # fraction of volume
    bg_vol  = float(fix_bg.sum()) / float(fix_bg.size)
    t0 = time.time()
    for step in range(args.steps + 1):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, args.dt)
        if step % args.report == 0 or step == args.steps:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            a = solver.a.item(); H = solver.H.item()
            r_val = (ey.mean() / (ei.mean() + 1e-12)).item()
            q, omq, cr, ms, ma, mi = compute_regions(solver, ey, ei)
            nt = float(ms.numel())
            ey_np = ey.cpu().numpy()
            ei_np = ei.cpu().numpy()
            r_np = ey_np / (ei_np + 1e-30)
            snaps.append(dict(
                step=step, a=a, H=H, r=r_val,
                q_mean=q.mean().item(), omq_vol=omq.mean().item(),
                frac_string=ms.sum().item() / nt,
                frac_active=ma.sum().item() / nt,
                r_str_fixed=float(r_np[fix_str].mean()),
                r_bg_fixed=float(r_np[fix_bg].mean()),
                str_vol=str_vol, bg_vol=bg_vol,
                q=q.cpu().numpy().copy(),
                conv=cr.cpu().numpy().copy(),
                mask_string=ms.cpu().numpy().copy(),
                mask_active=ma.cpu().numpy().copy()))
            if step % (args.report * 5) == 0 or step == args.steps:
                print(f'  step {step:5d}  a={a:.4f}  H={H:.4f}  r={r_val:.4f}  '
                      f'f_str={snaps[-1]["frac_string"]:.3f}')
    print(f'sim done in {time.time()-t0:.1f}s  ({len(snaps)} snapshots)')
    return solver, snaps, run_dir


# ═══════════════════════════════════════════════════════════════════════════
# §2  ODE baseline (5ch + xi) for the w(a) comparison panel
# ═══════════════════════════════════════════════════════════════════════════

def _q5(r):
    e, l = 0.438, 0.348
    return max(e + (l - e) / (1.0 + np.exp(-(r - PHI_INV) / 0.3)), 0.0)


def run_ode_baseline(lam=0.1, xi=PHI ** 6, n_pts=4000):
    def H_eff(r):
        Hb = (lam / 3) * PHI_INV ** 2 + (lam / 3) * abs(PHI - r) * (1 + r) / max(r, 1e-12)
        return Hb * math.sqrt(1 + xi * (1 - _q5(r)))

    a = np.exp(np.linspace(math.log(0.01), 0, n_pts))
    r = np.zeros(n_pts); r[0] = 0.043
    for i in range(n_pts - 1):
        am = 0.5 * (a[i] + a[i + 1])
        Hv = H_eff(r[i])
        drda = -lam * _q5(r[i]) * (r[i] - PHI) * (1 + r[i]) / (Hv * am) if Hv > 0 else 0
        r[i + 1] = np.clip(r[i] + drda * (a[i + 1] - a[i]), 1e-15, PHI - 1e-15)
    Hv = np.array([H_eff(rr) for rr in r])
    dln = np.zeros(n_pts)
    for i in range(1, n_pts - 1):
        da = a[i + 1] - a[i - 1]
        if da > 0 and Hv[i] > 0:
            dln[i] = (a[i] / Hv[i]) * (Hv[i + 1] - Hv[i - 1]) / da
    if Hv[0] > 0: dln[0] = (a[0] / Hv[0]) * (Hv[1] - Hv[0]) / (a[1] - a[0])
    if Hv[-1] > 0: dln[-1] = (a[-1] / Hv[-1]) * (Hv[-1] - Hv[-2]) / (a[-1] - a[-2])
    return a, -1.0 - (2.0 / 3.0) * dln


# ═══════════════════════════════════════════════════════════════════════════
# §3  Frame rendering
# ═══════════════════════════════════════════════════════════════════════════

def render_frame(snap, idx, n_frames, solver, series, ode_aw, fig, ax3d,
                 ax_w, ax_frac, ax_H, artists, L, string_r,
                 n_cloud, cloud_size, n_str_pts, str_pt_size):
    """Update all axes for frame idx. Returns list of matplotlib artists."""
    s = snap
    N = s['conv'].shape[0]
    a_now = s['a']

    # ── 3D panel: slice planes + scatter ──────────────────────────────
    ax3d.clear()
    ax3d.set_xlim(0, L); ax3d.set_ylim(0, L); ax3d.set_zlim(0, L)
    ax3d.set_box_aspect((1, 1, 1))
    ax3d.set_facecolor(BG)
    ax3d.xaxis.pane.fill = ax3d.yaxis.pane.fill = ax3d.zaxis.pane.fill = False
    ax3d.xaxis.pane.set_edgecolor(RI); ax3d.yaxis.pane.set_edgecolor(RI)
    ax3d.zaxis.pane.set_edgecolor(RI)
    ax3d.set_xlabel('x', color=TS, fontsize=8); ax3d.set_ylabel('y', color=TS, fontsize=8)
    ax3d.set_zlabel('z', color=TS, fontsize=8)
    ax3d.tick_params(colors=TS, labelsize=6)

    # rotating camera
    azim = (idx / max(n_frames - 1, 1)) * 360.0
    elev = 22.0 + 8.0 * np.sin(2 * np.pi * idx / max(n_frames - 1, 1))
    ax3d.view_init(elev=elev, azim=azim)

    # domain wireframe box
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    corners = np.array([[0, 0, 0], [L, 0, 0], [L, L, 0], [0, L, 0],
                        [0, 0, L], [L, 0, L], [L, L, L], [0, L, L]])
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
             (0, 4), (1, 5), (2, 6), (3, 7)]
    segs = [[corners[i], corners[j]] for i, j in edges]
    ax3d.add_collection3d(Line3DCollection(segs, colors=RI, linewidths=0.8, alpha=0.6))

    # ── Dense point-cloud volume rendering ─────────────────────────────
    # Importance-sample ~n_cloud voxels by conv_rate: active regions
    # (high conv) are dense + bright, the string (low conv) appears as
    # a dark void in the glowing cloud.  Fixed-geometry indigo cylinder
    # points anchor the string location regardless of field evolution.
    conv = s['conv']
    cv99 = float(np.percentile(conv[conv > 0], 99)) if (conv > 0).any() else 1.0
    cv_norm = Normalize(vmin=0, vmax=max(cv99, 1e-30))
    bg_rgb = np.array([0.0235, 0.0235, 0.0706])   # #060612

    rng = np.random.default_rng(42)   # fixed seed → no flicker between frames
    conv_flat = conv.ravel()
    probs = np.maximum(conv_flat, 1e-30)
    probs /= probs.sum()
    idx_c = rng.choice(N * N * N, size=min(n_cloud, N * N * N), p=probs, replace=True)
    zc_c, yc_c, xc_c = np.unravel_index(idx_c, (N, N, N))
    vals_c = conv_flat[idx_c]

    # alpha from conv (higher = more visible), bake into color by blending with BG
    alpha_c = np.clip((vals_c / (cv99 + 1e-30)) ** 0.6, 0.08, 1.0)
    rgb_c = CONV_CMAP(cv_norm(vals_c))[:, :3]
    blended_c = rgb_c * alpha_c[:, None] + bg_rgb * (1 - alpha_c[:, None])
    ax3d.scatter(xc_c * (L / N), yc_c * (L / N), zc_c * (L / N),
                 c=blended_c, s=cloud_size, alpha=1.0, edgecolors='none',
                 depthshade=True, rasterized=True)
    # ── String cylinder: fixed-geometry indigo points ──
    z_samp = rng.uniform(0, N, n_str_pts)
    theta_samp = rng.uniform(0, 2 * np.pi, n_str_pts)
    r_str_cyl = string_r * N * 0.55  # inner core in voxel units
    x_s = N / 2 + r_str_cyl * np.cos(theta_samp)
    y_s = N / 2 + r_str_cyl * np.sin(theta_samp)
    x_s += rng.normal(0, r_str_cyl * 0.08, n_str_pts)
    y_s += rng.normal(0, r_str_cyl * 0.08, n_str_pts)
    str_alpha = 0.70
    ax3d.scatter(x_s * (L / N), y_s * (L / N), z_samp * (L / N),
                 c=YIN, s=str_pt_size, alpha=str_alpha, edgecolors='none',
                 depthshade=True, rasterized=True)

    ax3d.set_title('Dense point-cloud · conv_rate glow   ·   indigo = string core',
                   fontsize=9, color=YANG, pad=4)
    # overlay text in 3D corner
    ax3d.text2D(0.02, 0.965,
                f"a={a_now:.4f}   step={s['step']}   "
                f"⟨1−q⟩={s['omq_vol']:.3f}   r={s['r']:.3f}",
                transform=ax3d.transAxes, fontsize=8, color=TM,
                family='monospace', va='top')

    # ── Right column: diagnostics with moving cursor ──────────────────
    aw, wp = series['aw'], series['wp']
    ao, wo = ode_aw

    # w(a) panel
    ax_w.clear(); ax_w.set_facecolor(BG)
    m = aw <= a_now
    ax_w.plot(ao, wo, color=YIN, lw=1.5, ls='--', alpha=0.8, label='ODE 5ch+ξ')
    if m.sum() >= 1:
        ax_w.plot(aw[m], wp[m], color=YANG, lw=2, label='PDE')
    ax_w.axhline(-1.0, color=TS, ls=':', lw=0.8)
    ax_w.axvline(a_now, color=SAFE, lw=1.2, alpha=0.9)
    ax_w.set_xlabel('a', fontsize=8); ax_w.set_ylabel('w(a)', fontsize=8)
    ax_w.set_title('Dark-energy equation of state', fontsize=9, color=YANG)
    ax_w.set_ylim(-2.5, 1.0)
    # flag when PDE w is off-scale (needs longer a-range; see handoff)
    if m.sum() >= 1 and np.nanmin(wp[m]) < -2.5:
        ax_w.text(0.97, 0.06, 'PDE w off-scale\n(tiny a-range)',
                  transform=ax_w.transAxes, fontsize=6, color=DANGER,
                  ha='right', va='bottom', alpha=0.85)
    ax_w.legend(fontsize=7, frameon=False, labelcolor=TM)

    # Region r panel (persistent fixed-geometry string vs background)
    ax_frac.clear(); ax_frac.set_facecolor(BG)
    r_sf = np.array([x['r_str_fixed'] for x in series['snaps']])
    r_bf = np.array([x['r_bg_fixed'] for x in series['snaps']])
    ap = np.array([x['a'] for x in series['snaps']])
    mm = ap <= a_now
    ax_frac.plot(ap[mm], r_sf[mm], color=YIN, lw=2, label='string core')
    ax_frac.plot(ap[mm], r_bf[mm], color=DANGER, lw=2, label='background')
    ax_frac.axhline(y=PHI, color=TS, ls=':', lw=0.8, alpha=0.7)
    ax_frac.text(0.98, 0.92, f'φ={PHI:.3f}', transform=ax_frac.transAxes,
                 fontsize=7, color=TS, ha='right', va='top')
    ax_frac.axvline(a_now, color=SAFE, lw=1.2, alpha=0.9)
    ax_frac.set_xlabel('a', fontsize=8); ax_frac.set_ylabel('r = EY/EI', fontsize=8)
    ax_frac.set_title('Region r = EY/EI (fixed geometry)', fontsize=9, color=YANG)
    ax_frac.legend(fontsize=7, frameon=False, labelcolor=TM)
    ax_frac.set_ylim(0, 2.0); ax_frac.grid(True, alpha=0.25)
    ax_frac.tick_params(labelsize=7)

    # H(a) panel
    ax_H.clear(); ax_H.set_facecolor(BG)
    Hp = np.array([x['H'] for x in series['snaps']])
    ax_H.plot(ap[mm], Hp[mm], color=YANG, lw=2)
    ax_H.axvline(a_now, color=SAFE, lw=1.2, alpha=0.9)
    ax_H.set_xlabel('a', fontsize=8); ax_H.set_ylabel('H', fontsize=8)
    ax_H.set_title('Hubble parameter', fontsize=9, color=YANG)
    ax_H.set_ylim(0, solver.max_H)
    ax_H.grid(True, alpha=0.25); ax_H.tick_params(labelsize=7)

    return []


# ═══════════════════════════════════════════════════════════════════════════
# §4  Animation assembly
# ═══════════════════════════════════════════════════════════════════════════

def make_animation(solver, snaps, run_dir, args, ode_aw):
    rd = Path(run_dir)
    L = solver.L
    aw, _, wp = compute_w_from_snaps(snaps)
    series = dict(aw=aw, wp=wp, snaps=snaps)
    n_frames = len(snaps)

    fig = plt.figure(figsize=(14, 8.5), dpi=args.dpi)
    fig.patch.set_facecolor(BG)
    ax3d = fig.add_axes([0.02, 0.06, 0.50, 0.84], projection='3d')
    ax_w    = fig.add_axes([0.56, 0.60, 0.41, 0.22])
    ax_frac = fig.add_axes([0.56, 0.33, 0.41, 0.22])
    ax_H    = fig.add_axes([0.56, 0.06, 0.41, 0.22])

    fig.suptitle('Cassi Two-Fluid PDE—String-Seeded 5-Channel Gate Evolution',
                 fontsize=15, fontweight='bold', color=YANG, y=0.97)
    fig.text(0.5, 0.945,
             f'N={solver.N}³  λ={solver.lam}  gate=Wu Xing (5ch)  ·  '
             f'rotating volumetric view + cosmological diagnostics',
             ha='center', fontsize=9, color=TS)

    out_mp4 = rd / 'animation.mp4'
    ff = _ffmpeg_exe()
    frames_dir = rd / ('frames' if args.png else '_tmp_frames')
    frames_dir.mkdir(exist_ok=True)

    print(f'rendering {n_frames} frames ...')
    t0 = time.time()
    for i, snap in enumerate(snaps):
        render_frame(snap, i, n_frames, solver, series, ode_aw, fig, ax3d,
                     ax_w, ax_frac, ax_H, {}, L, args.string_r,
                     args.n_cloud, args.cloud_size, args.n_str_pts,
                     args.str_pt_size)
        fig.savefig(frames_dir / f'frame_{i:04d}.png', dpi=args.dpi, facecolor=BG)
        if (i + 1) % max(1, n_frames // 10) == 0:
            print(f'  frame {i + 1}/{n_frames}  ({time.time()-t0:.1f}s)')
    print(f'render done in {time.time()-t0:.1f}s')

    # ── Assemble MP4 ──────────────────────────────────────────────────
    if ff is None:
        print(f'\n[WARN] no ffmpeg found. PNG frames in {frames_dir}/')
        print(f'       assemble with: ffmpeg -framerate {args.fps} '
              f'-i {frames_dir}/frame_%04d.png -c:v libx264 '
              f'-pix_fmt yuv420p {out_mp4}')
        return str(frames_dir)

    cmd = [ff, '-y', '-framerate', str(args.fps),
           '-i', str(frames_dir / 'frame_%04d.png'),
           '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
           '-crf', str(args.crf), '-preset', args.preset,
           str(out_mp4)]
    print(f'\nassembling MP4: {out_mp4.name}')
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print('[ERROR] ffmpeg failed:\n', r.stderr[-1500:])
        return str(frames_dir)
    if not args.png:
        for p in frames_dir.glob('frame_*.png'):
            try: p.unlink()
            except OSError: pass
        try: frames_dir.rmdir()
        except OSError: pass
    print(f'\n  wrote {out_mp4}  ({out_mp4.stat().st_size/1e6:.2f} MB)')
    return str(out_mp4)


# ═══════════════════════════════════════════════════════════════════════════
# §5  Main
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    p = argparse.ArgumentParser(description='3D Animation of String-Seeded PDE')
    p.add_argument('--N', type=int, default=32)
    p.add_argument('--steps', type=int, default=1200)
    p.add_argument('--dt', type=float, default=0.0005)
    p.add_argument('--report', type=int, default=40)
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
    p.add_argument('--fps', type=int, default=12)
    p.add_argument('--crf', type=int, default=20)
    p.add_argument('--preset', type=str, default='medium')
    p.add_argument('--dpi', type=int, default=100)
    p.add_argument('--png', action='store_true', default=False,
                   help='keep PNG frames alongside the MP4')
    p.add_argument('--n-cloud', type=int, default=10000,
                   help='dense point-cloud: voxels sampled per frame')
    p.add_argument('--cloud-size', type=float, default=6,
                   help='point-cloud dot size')
    p.add_argument('--n-str-pts', type=int, default=1500,
                   help='string cylinder overlay points')
    p.add_argument('--str-pt-size', type=float, default=16,
                   help='string cylinder dot size')
    args = p.parse_args()

    print('=' * 65)
    print('  3D ANIMATION—STRING-SEEDED TWO-FLUID PDE')
    print('  rotating volumetric view + cosmological diagnostics')
    print('=' * 65)

    solver, snaps, run_dir = run_sim(args)
    if len(snaps) < 2:
        print('[ERROR] too few snapshots'); sys.exit(1)
    print('\n=== ODE baseline (5ch + xi) ===')
    ao, wo = run_ode_baseline(lam=args.lam)
    print(f'  ODE w range: [{wo.min():.3f}, {wo.max():.3f}]')

    out = make_animation(solver, snaps, run_dir, args, (ao, wo))
    print(f'\n  Done. Output: {out}')