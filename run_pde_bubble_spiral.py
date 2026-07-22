#!/usr/bin/env python3
"""Bubble PDE: Fibonacci spiral mode emergence at the poles (two-pole gate).

Initializes a triaxial ellipsoid bubble in the 3D two-fluid PDE with the
two-pole (east/west) Wu Xing 5-channel gate, evolves it, and analyzes the
angular mode spectrum at each pole for Fibonacci spiral structure.

Theory: the bubble axes (φ, 1, 1/φ) + two-pole pentagon gate should produce
dominant m=5, 8, 13... Fibonacci modes at the poles via the same mechanism
that yields 5 spiral arms in the Fibonacci phyllotaxis on a φ-ellipsoid.

Usage:
    python run_pde_bubble_spiral.py                     # fresh run (N=64, 12000 steps)
    python run_pde_bubble_spiral.py --N 48 --steps 8000  # lighter run
    python run_pde_bubble_spiral.py --resume runs/20260722_HHMMSS_bubble_spiral

Imports the PDE solver from the local two-fluid/ directory.
"""

import torch, numpy as np, sys, os, argparse, glob, re
from datetime import datetime

# ── Import from local two-fluid/ ─────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'two-fluid'))
from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI, PHI_INV

# ── Constants ────────────────────────────────────────────────────────────────
FIB_MODES = [3, 5, 8, 13, 21, 34]  # Fibonacci numbers to track
CKPT_INTERVAL = 500
LOG_INTERVAL = 100

# ── Checkpoint helpers ───────────────────────────────────────────────────────
def find_last_checkpoint(run_dir):
    ckpts = sorted(glob.glob(os.path.join(run_dir, 'checkpoint_*.pt')))
    return ckpts[-1] if ckpts else None

def save_checkpoint(step, solver, u_hat, ey_hat, ei_hat, run_dir):
    ckpt_file = os.path.join(run_dir, f'checkpoint_{step:06d}.pt')
    torch.save({
        'step': step,
        'a': solver.a.detach().cpu(),
        'H_smooth': solver._H_smooth.detach().cpu(),
        'u_hat': [u.detach().cpu() for u in u_hat],
        'ey_hat': ey_hat.detach().cpu(),
        'ei_hat': ei_hat.detach().cpu(),
    }, ckpt_file)
    # Keep only last 2 checkpoints
    old = sorted(glob.glob(os.path.join(run_dir, 'checkpoint_*.pt')))[:-2]
    for f in old:
        os.remove(f)
    return ckpt_file

# ── Bubble initial condition ─────────────────────────────────────────────────
def triaxial_bubble(shape, cx, cy, cz, rx, ry, rz, amplitude=1.0):
    """Ellipsoidal Gaussian bubble: axes (φ, 1, 1/φ) → rx:ry:rz = φ²:φ:1."""
    z = torch.linspace(-1, 1, shape[0])
    y = torch.linspace(-1, 1, shape[1])
    x = torch.linspace(-1, 1, shape[2])
    ZZ, YY, XX = torch.meshgrid(z, y, x, indexing='ij')
    bubble = amplitude * torch.exp(-(
        (XX - cx)**2 / (2 * rx**2) +
        (YY - cy)**2 / (2 * ry**2) +
        (ZZ - cz)**2 / (2 * rz**2)
    ))
    return bubble

# ── Angular mode analysis ────────────────────────────────────────────────────
def pole_angular_modes(field_3d, pole_sign=1, n_slices=4):
    """Compute angular Fourier power spectrum averaged over z-slices near a pole.

    Uses multiple z-slices near the pole and averages the angular power spectra
    for better signal-to-noise. Normalizes properly so all mode fractions are ≤1.

    Returns:
        mode_powers: dict m → power fraction (0 to 1, sum over displayed m ≤ 1)
        dominant_m: int, mode with highest power (excluding m=0,1)
        dom_frac: float, dominant mode fraction * 100
    """
    Nz, Ny, Nx = field_3d.shape
    cy, cx = Ny // 2, Nx // 2

    # Z-slice range near pole
    if pole_sign > 0:
        z_start = max(Nz - n_slices - 1, Nz * 3 // 4)
        z_end = Nz
    else:
        z_start = 0
        z_end = min(n_slices + 1, Nz // 4)

    # Radial mask (shared across z-slices)
    Y, X = torch.meshgrid(
        torch.arange(Ny, dtype=torch.float64) - cy,
        torch.arange(Nx, dtype=torch.float64) - cx,
        indexing='ij'
    )
    radius = torch.sqrt(X**2 + Y**2)
    r_max = min(cy, cx) * 0.7
    mask = (radius > r_max * 0.1) & (radius < r_max)

    if mask.sum() < 20:
        return {}, 0, 0.0

    angles = torch.atan2(Y[mask], X[mask]) % (2 * np.pi)
    n_mask = mask.sum().item()

    # Accumulate angular Fourier coefficients across z-slices
    n_angular = min(64, n_mask // 4)
    accum_power = torch.zeros(n_angular // 2, dtype=torch.float64)
    total_var = 0.0

    for z_idx in range(z_start, z_end):
        f_slice = field_3d[z_idx, :, :].double()
        values = f_slice[mask]
        # Subtract mean on this slice (remove DC for mode analysis)
        values = values - values.mean()
        total_var += (values**2).sum().item()

        # Fourier decomposition: a_m = Σ f(θ)·e^{-imθ}
        for m in range(n_angular // 2):
            cos_m = torch.cos(m * angles)
            sin_m = torch.sin(m * angles)
            a_real = (values * cos_m).sum()
            a_imag = -(values * sin_m).sum()
            accum_power[m] += (a_real**2 + a_imag**2).item()

    total_var = total_var + 1e-30
    # DC mode (m=0) — we track but exclude from dominant search
    mode_powers = {}
    for m in range(1, n_angular // 2):
        # Normalize by total variance across all slices
        mode_powers[m] = accum_power[m].item() / total_var

    if not mode_powers:
        return {}, 0, 0.0

    # Dominant mode (exclude m=0,1 — DC/dipole are grid artifacts)
    mid_modes = {m: p for m, p in mode_powers.items() if m >= 2}
    if not mid_modes:
        return mode_powers, 0, 0.0

    dominant_m = max(mid_modes, key=mid_modes.get)
    dom_frac = mid_modes[dominant_m] * 100  # percentage of total variance

    return mode_powers, dominant_m, dom_frac

# ── Main run ─────────────────────────────────────────────────────────────────
def run_bubble_spiral(args):
    """Run PDE with two-pole gate + bubble IC, analyze Fibonacci emergence."""

    # ── Setup: fresh or resume ───────────────────────────────────────────
    if args.resume:
        run_dir = args.resume
        logfile = os.path.join(run_dir, 'log.txt')
        modes_file = os.path.join(run_dir, 'modes.txt')
        ckpt = find_last_checkpoint(run_dir)
        if ckpt is None:
            print(f'[ERROR] No checkpoint found in {run_dir}')
            return

        ckpt_data = torch.load(ckpt, weights_only=False, map_location='cpu')
        print(f'[resume] {ckpt} at step {ckpt_data["step"]}')

        solver = ExpandingTwoFluid3DGPU(
            N=args.N, lam=args.lam, chi=0.0, D=args.D, nu=args.nu,
            a0=args.a0, initial_ratio=args.r0, hubble_mode='conversion',
            max_H=args.max_H, h_smooth=args.hs, qi_gate=True,
            mode='cosmos', device='cpu'
        )
        solver.gate_model = 'two_pole'
        solver.a = ckpt_data['a'].to(solver.device)
        solver._H_smooth = ckpt_data['H_smooth'].to(solver.device)
        u_hat = [u.to(solver.device) for u in ckpt_data['u_hat']]
        ey_hat = ckpt_data['ey_hat'].to(solver.device)
        ei_hat = ckpt_data['ei_hat'].to(solver.device)
        start_step = ckpt_data['step'] + 1
    else:
        rid = datetime.now().strftime('%Y%m%d_%H%M%S') + '_bubble_spiral'
        run_dir = os.path.join('runs', rid)
        os.makedirs(run_dir, exist_ok=True)
        logfile = os.path.join(run_dir, 'log.txt')
        modes_file = os.path.join(run_dir, 'modes.txt')

        solver = ExpandingTwoFluid3DGPU(
            N=args.N, lam=args.lam, chi=0.0, D=args.D, nu=args.nu,
            a0=args.a0, initial_ratio=args.r0, hubble_mode='conversion',
            max_H=args.max_H, h_smooth=args.hs, qi_gate=True,
            mode='cosmos', device='cpu'
        )
        solver.gate_model = 'two_pole'

        u_hat, ey_hat, ei_hat = solver.initial_expanding(amplitude=args.amp, seed=args.seed)

        # Inject triaxial bubble at center
        ey = torch.fft.ifftn(ey_hat).real
        ei = torch.fft.ifftn(ei_hat).real
        bubble = triaxial_bubble(
            ey.shape, 0, 0, 0,
            rx=args.brx, ry=args.bry, rz=args.brz,
            amplitude=args.bamp
        )
        ey = ey + bubble * ey.mean()
        ei = ei + bubble * ei.mean()
        ey_hat = torch.fft.fftn(ey)
        ei_hat = torch.fft.fftn(ei)

        # Log headers
        with open(logfile, 'w') as f:
            f.write(f'# N={args.N} lam={args.lam} gate=two_pole steps={args.steps}\n')
            f.write(f'# bubble: rx={args.brx:.4f} ry={args.bry:.4f} rz={args.brz:.4f} amp={args.bamp}\n')
            f.write(f'# {"step":>6s} {"a":>10s} {"H":>10s} {"r":>8s} {"q":>8s}\n')

        with open(modes_file, 'w') as f:
            f.write(f'# N={args.N} gate=two_pole — Fibonacci mode tracking\n')
            header = f'# {"step":>6s} {"dom_N":>5s} {"%N":>6s} {"dom_S":>5s} {"%S":>6s}'
            for fib in FIB_MODES:
                header += f' {"m="+str(fib):>8s}'
            f.write(header + '\n')

        start_step = 0
        print(f'[bubble_spiral] N={args.N}, steps={args.steps}, gate=two_pole')
        print(f'  bubble: rx={args.brx:.3f} ry={args.bry:.3f} rz={args.brz:.3f} amp={args.bamp}')
        print(f'  run dir: {run_dir}')

    # ── Evolve ────────────────────────────────────────────────────────────
    for step in range(start_step, args.steps + 1):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, args.dt)

        # Periodic logging
        if step % LOG_INTERVAL == 0 or step == args.steps:
            a = solver.a.item()
            H = solver._H_smooth.item()
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            r = (ey.mean() / (ei.mean() + 1e-12)).item()
            qm = solver.q_mean

            if np.isnan(a) or np.isnan(r):
                print(f'  [NaN] step={step} — aborting')
                with open(logfile, 'a') as f:
                    f.write(f'NaN at step {step}\n')
                break

            with open(logfile, 'a') as f:
                f.write(f'{step:7d} {a:10.6e} {H:10.6e} {r:8.4f} {qm:8.4f}\n')

        # Mode analysis + Fibonacci tracking
        if step % args.mode_int == 0 or step == args.steps:
            ey = torch.fft.ifftn(ey_hat).real
            modes_n, dom_n, frac_n = pole_angular_modes(ey, pole_sign=1)
            modes_s, dom_s, frac_s = pole_angular_modes(ey, pole_sign=-1)

            fib_powers = []
            for fib in FIB_MODES:
                pn = modes_n.get(fib, 0) * 100
                ps = modes_s.get(fib, 0) * 100
                fib_powers.append(f'{pn+ps:8.2f}')

            with open(modes_file, 'a') as f:
                f.write(f'{step:7d} {dom_n:5d} {frac_n:6.1f} {dom_s:5d} {frac_s:6.1f}'
                        + ''.join(fib_powers) + '\n')

        # Periodic checkpoint (inside loop)
        if step > 0 and step % CKPT_INTERVAL == 0:
            save_checkpoint(step, solver, u_hat, ey_hat, ei_hat, run_dir)

        # Console progress
        if step % 1000 == 0 or step == args.steps:
            fib_str = ' '.join([f'm={fib}:{modes_n.get(fib,0)*100:4.1f}%' for fib in [5, 8, 13]])
            print(f'  step={step:5d} a={a:.4f} H={H:.4f} r={r:.4f} q={qm:.4f} '
                  f'N-dom=m{dom_n}({frac_n:.0f}%) S-dom=m{dom_s}({frac_s:.0f}%) [{fib_str}]')


    # Final checkpoint
    if step > 0:
        save_checkpoint(step, solver, u_hat, ey_hat, ei_hat, run_dir)

    print(f'\n[bubble_spiral] Done → {run_dir}')
    print(f'  Log:       {logfile}')
    print(f'  Modes:     {modes_file}')
    return run_dir


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    p = argparse.ArgumentParser(
        description='Bubble PDE: Fibonacci spiral mode test (two-pole gate)')
    p.add_argument('--resume', type=str, default=None,
                   help='Resume from run directory')
    p.add_argument('--steps', type=int, default=12000,
                   help='Number of RK2 steps (default: 12000)')
    p.add_argument('--N', type=int, default=64,
                   help='Grid resolution (default: 64)')
    p.add_argument('--lam', type=float, default=0.02,
                   help='Conversion rate (default: 0.02)')
    p.add_argument('--D', type=float, default=0.0001,
                   help='Diffusion (default: 0.0001)')
    p.add_argument('--nu', type=float, default=0.0005,
                   help='Hyperdiffusion/viscosity (default: 0.0005)')
    p.add_argument('--dt', type=float, default=0.0005,
                   help='Time step (default: 0.0005)')
    p.add_argument('--max_H', type=float, default=0.2,
                   help='Max Hubble cap (default: 0.2)')
    p.add_argument('--hs', type=float, default=0.05,
                   help='Hubble smoothing (default: 0.05)')
    p.add_argument('--a0', type=float, default=0.01,
                   help='Initial scale factor (default: 0.01)')
    p.add_argument('--r0', type=float, default=21.2,
                   help='Initial Yang/Yin ratio (default: 21.2)')
    p.add_argument('--amp', type=float, default=0.01,
                   help='Initial perturbation amplitude (default: 0.01)')
    p.add_argument('--seed', type=int, default=42,
                   help='Random seed (default: 42)')
    p.add_argument('--bamp', type=float, default=0.8,
                   help='Bubble amplitude relative to mean (default: 0.8)')
    p.add_argument('--brx', type=float, default=0.85,
                   help='Bubble x-radius (default: 0.85; L=2*brx/phi^2~0.65)')
    p.add_argument('--bry', type=float, default=None,
                   help='Bubble y-radius (default: brx/phi)')
    p.add_argument('--brz', type=float, default=None,
                   help='Bubble z-radius (default: brx/phi^2)')
    p.add_argument('--mode_int', type=int, default=200,
                   help='Mode analysis interval (default: 200)')

    args = p.parse_args()

    # Default bubble axis ratios: φ² : φ : 1
    if args.bry is None:
        args.bry = args.brx / PHI
    if args.brz is None:
        args.brz = args.brx / PHI**2

    print('═══ Bubble PDE: Fibonacci Spiral Mode Test ═══')
    print(f'  Gate: two-pole  |  N={args.N}  |  Steps: {args.steps}')
    print(f'  Bubble axes: ({args.brx:.3f}, {args.bry:.3f}, {args.brz:.3f}) '
          f'ratio = ({args.brx/args.brz:.3f} : {args.bry/args.brz:.3f} : 1)')
    print(f'  Pole-to-pole L = 2·rz = {2*args.brz:.3f}')
    print(f'  λ_5 = L/5 = {2*args.brz/5:.3f}  (standing wave half-wavelength)')
    print(f'  Expected φ-aspect: φ²:φ:1 = ({PHI**2:.3f}:{PHI:.3f}:1)')
    print()

    run_bubble_spiral(args)

