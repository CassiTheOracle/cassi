#!/usr/bin/env python3
"""Bubble PDE: Fibonacci spatial-mode analysis + pole-orientation diagnostic.

Initializes a triaxial ellipsoid bubble in the 3D two-fluid PDE with the
two-pole (east/west) Wu Xing 5-channel gate, evolves it, and analyzes:

1. Angular power spectrum—static mode decomposition at each pole
2. Angular coefficient orientation—tracks the argument of key Fibonacci-mode
   Fourier coefficients over time as a pole-pattern rotation diagnostic

The canonical state contains two real density fields, E_Y and E_I.  Their
derived density-plane angle is theta = atan2(E_I, E_Y); conversion changes
this angle by relaxation toward equilibrium.  It is not an independently
evolved compact phase or a fixed periodic phase clock.  This script does not
compute theta or dtheta/dt: its tracked phi_m = arg(a_m) is the argument of a
spatial Fourier coefficient of the E_Y pole pattern, not the density-plane
angle.

The triaxial-helix interpretation, rotating pentagon, and five-phase Wu Xing
modulation are tested model hypotheses—not consequences of the canonical
two-fluid equations.  In particular, a pattern along the chord string
(z-axis) is not by itself a physical 3D helix, and coefficient-angle drift
does not derive one.  Comparing that drift with lambda is likewise a
model-hypothesis diagnostic, not a conversion-ODE phase clock.
The supplied lambda is a solver normalization/timescale convention here; this
script does not derive its value from w = 5 or from a one-event-per-cycle
interpretation.

Static mode power (FFT averaged over time) can be insensitive to a changing
pole-pattern orientation.  We therefore track the coefficient argument
phi_m(t) = arg(a_m(t)) of each angular Fourier coefficient.

Usage:
    python run_pde_bubble_spiral.py                # N=48, 8000 steps
    python run_pde_bubble_spiral.py --N 64 --steps 12000
    python run_pde_bubble_spiral.py --resume runs/20260722_HHMMSS_bubble_spiral
Results (July 2026):
- Static modes: m=2 (ellipsoid cross-section) dominates at both poles.
  No m=5 Fibonacci mode emergence—the pentagon is geometric, not dynamic.
- Angular coefficient-argument drift: d(arg a_m)/dt ~ 1.5e-4 rad/step
  versus the tested model-hypothesis scale 0.1 rad/step for m=5 at
  lambda=0.02.  This spatial-pattern diagnostic does not measure theta,
  establish a compact phase, or prove a physical 3D helix.
- Gate analysis: the two-pole gate modulates spatial pattern (5-channel
  structure at poles), not convergence rate.  Irreducible (1-q)_min ~ 0.24.
  Gate never saturates—N=292 is not determined by gate closure.
- The pentagon/spiral remains a tested geometric hypothesis for the
  phi-ellipsoid (golden-angle phyllotaxis), not a PDE-emergent result.
  Claims about cascade depth, primordial Yang-Yin ratio, or lambda derivation
  belong to separate model hypotheses (foundations/wu-xing-derivation.md).
"""

import torch, numpy as np, sys, os, argparse, glob, re
from datetime import datetime

# ── Import from local two-fluid/ ─────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI, PHI_INV

# ── Constants ────────────────────────────────────────────────────────────────
FIB_MODES = [3, 5, 8, 13, 21, 34]
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
    old = sorted(glob.glob(os.path.join(run_dir, 'checkpoint_*.pt')))[:-2]
    for f in old:
        os.remove(f)
    return ckpt_file

# ── Bubble initial condition ─────────────────────────────────────────────────
def triaxial_bubble(shape, cx, cy, cz, rx, ry, rz, amplitude=1.0):
    """Ellipsoidal Gaussian bubble: axes (phi, 1, 1/phi) -> rx:ry:rz = phi^2:phi:1."""
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

# ── Pole extraction helper ───────────────────────────────────────────────────
def _pole_radial_mask(Ny, Nx):
    """Shared radial mask for pole analysis. Returns mask, angles, r_max."""
    cy, cx = Ny // 2, Nx // 2
    Y, X = torch.meshgrid(
        torch.arange(Ny, dtype=torch.float64) - cy,
        torch.arange(Nx, dtype=torch.float64) - cx,
        indexing='ij'
    )
    radius = torch.sqrt(X**2 + Y**2)
    r_max = min(cy, cx) * 0.7
    mask = (radius > r_max * 0.1) & (radius < r_max)
    angles = torch.atan2(Y[mask], X[mask]) % (2 * np.pi)
    return mask, angles

def _pole_z_range(Nz, pole_sign, n_slices=4):
    """Z-slice range near the specified pole."""
    if pole_sign > 0:
        return max(Nz - n_slices - 1, Nz * 3 // 4), Nz
    else:
        return 0, min(n_slices + 1, Nz // 4)

# ── Angular mode power spectrum (static) ─────────────────────────────────────
def pole_angular_modes(field_3d, pole_sign=1, n_slices=4):
    """Static angular Fourier power spectrum averaged over z-slices.

    Returns: (mode_powers: dict m->fraction, dominant_m: int, dom_frac: float%)
    """
    Nz, Ny, Nx = field_3d.shape
    mask, angles = _pole_radial_mask(Ny, Nx)
    if mask.sum() < 20:
        return {}, 0, 0.0

    z_start, z_end = _pole_z_range(Nz, pole_sign, n_slices)
    n_mask = mask.sum().item()
    n_angular = min(64, n_mask // 4)
    accum_power = torch.zeros(n_angular // 2, dtype=torch.float64)

    for z_idx in range(z_start, z_end):
        values = field_3d[z_idx, :, :].double()[mask]
        values = values - values.mean()
        for m in range(n_angular // 2):
            cos_m = torch.cos(m * angles)
            sin_m = torch.sin(m * angles)
            a_real = (values * cos_m).sum()
            a_imag = -(values * sin_m).sum()
            accum_power[m] += (a_real**2 + a_imag**2).item()

    total = accum_power.sum().item() + 1e-30
    mode_powers = {m: accum_power[m].item() / total for m in range(1, n_angular // 2)}
    if not mode_powers:
        return {}, 0, 0.0

    mid = {m: p for m, p in mode_powers.items() if m >= 2}
    if not mid:
        return mode_powers, 0, 0.0
    dom = max(mid, key=mid.get)
    return mode_powers, dom, mid[dom] * 100

# ── Angular Fourier-coefficient argument tracking ────────────────────────────
def pole_angular_phases(field_3d, pole_sign=1, track_modes=None, n_slices=4):
    """Return complex Fourier coefficient a_m for each tracked mode.

    a_m = Σ f(θ)·e^{-imθ}—a complex number whose argument
    phi_m = arg(a_m) tracks the angular orientation of mode m at this
    timestep.  If the pole pattern rotates by Δθ per timestep, arg(a_m)
    advances by m·Δθ.  This coefficient argument is a spatial-pattern
    diagnostic, not the density-plane angle theta = atan2(E_I, E_Y).

    Returns: dict m -> complex (real, imag) for each tracked mode.
    """
    if track_modes is None:
        track_modes = [5, 8, 13]

    Nz, Ny, Nx = field_3d.shape
    mask, angles = _pole_radial_mask(Ny, Nx)
    if mask.sum() < 20:
        return {}

    z_start, z_end = _pole_z_range(Nz, pole_sign, n_slices)

    # Accumulate complex coefficients across z-slices
    accum = {m: 0.0 + 0.0j for m in track_modes}
    for z_idx in range(z_start, z_end):
        values = field_3d[z_idx, :, :].double()[mask]
        values = values - values.mean()
        for m in track_modes:
            cos_m = torch.cos(m * angles)
            sin_m = torch.sin(m * angles)
            a_real = (values * cos_m).sum().item()
            a_imag = -(values * sin_m).sum().item()
            accum[m] += complex(a_real, a_imag)

    return accum

# ── Main run ─────────────────────────────────────────────────────────────────
def run_bubble_spiral(args):
    """Run PDE with two-pole gate + bubble IC; test spatial-mode and
    pole-pattern orientation hypotheses.
    """

    # ── Setup: fresh or resume ───────────────────────────────────────────
    if args.resume:
        run_dir = args.resume
        logfile = os.path.join(run_dir, 'log.txt')
        modes_file = os.path.join(run_dir, 'modes.txt')
        phases_file = os.path.join(run_dir, 'phases.txt')
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
        # Append mode to existing files
    else:
        rid = datetime.now().strftime('%Y%m%d_%H%M%S') + '_bubble_spiral'
        run_dir = os.path.join('runs', rid)
        os.makedirs(run_dir, exist_ok=True)
        logfile = os.path.join(run_dir, 'log.txt')
        modes_file = os.path.join(run_dir, 'modes.txt')
        phases_file = os.path.join(run_dir, 'phases.txt')

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
        with open(logfile, 'w', encoding='utf-8') as f:
            f.write(f'# N={args.N} lam={args.lam} gate=two_pole steps={args.steps}\n')
            f.write(f'# bubble: rx={args.brx:.4f} ry={args.bry:.4f} rz={args.brz:.4f} amp={args.bamp}\n')
            f.write(f'# {"step":>6s} {"a":>10s} {"H":>10s} {"r":>8s} {"q":>8s}\n')

        with open(modes_file, 'w', encoding='utf-8') as f:
            f.write(f'# N={args.N} gate=two_pole—static angular mode powers\n')
            header = f'# {"step":>6s} {"dom_N":>5s} {"%N":>6s} {"dom_S":>5s} {"%S":>6s}'
            for fib in FIB_MODES:
                header += f' {"m="+str(fib):>8s}'
            f.write(header + '\n')

        with open(phases_file, 'w', encoding='utf-8') as f:
            f.write(f'# N={args.N} gate=two_pole—angular Fourier-coefficient arguments (radians) for spatial-pattern orientation diagnostics\n')
            f.write(f'# Tested hypothesis only: coefficient-argument drift scale d(arg a_m)/dt ~ lambda = {args.lam} rad/step; this is not dtheta/dt\n')
            header = '# step'
            for pole in ['N', 'S']:
                for m in [5, 8, 13]:
                    header += f' phi{pole}{m}_re phi{pole}{m}_im'
            f.write(header + '\n')
        start_step = 0
        print(f'[bubble_spiral] N={args.N}, steps={args.steps}, gate=two_pole')
        print(f'  bubble: rx={args.brx:.3f} ry={args.bry:.3f} rz={args.brz:.3f} amp={args.bamp}')
        print(f'  run dir: {run_dir}')

    # ── Evolve ────────────────────────────────────────────────────────────
    track_modes = [5, 8, 13]
    for step in range(start_step, args.steps + 1):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, args.dt)

        report = step % LOG_INTERVAL == 0 or step == args.steps
        mode_sample = step % args.mode_int == 0 or step == args.steps
        progress = step % 1000 == 0 or step == args.steps
        # Materialize the current E_Y field once for whichever diagnostics
        # need it.  In particular, progress cadence need not equal mode_int.
        ey = (torch.fft.ifftn(ey_hat).real
              if (report or mode_sample or progress) else None)

        # Periodic logging
        if report:
            a = solver.a.item()
            H = solver._H_smooth.item()
            ei = torch.fft.ifftn(ei_hat).real
            r = (ey.mean() / (ei.mean() + 1e-12)).item()
            qm = solver.q_mean

            if np.isnan(a) or np.isnan(r):
                print(f'  [NaN] step={step}—aborting')
                with open(logfile, 'a', encoding='utf-8') as f:
                    f.write(f'NaN at step {step}\n')
                break

            with open(logfile, 'a', encoding='utf-8') as f:
                f.write(f'{step:7d} {a:10.6e} {H:10.6e} {r:8.4f} {qm:8.4f}\n')

        # Mode analysis + spatial coefficient-argument tracking
        if mode_sample:
            # Static mode powers
            modes_n, dom_n, frac_n = pole_angular_modes(ey, pole_sign=1)
            modes_s, dom_s, frac_s = pole_angular_modes(ey, pole_sign=-1)

            fib_powers = []
            for fib in FIB_MODES:
                pn = modes_n.get(fib, 0) * 100
                ps = modes_s.get(fib, 0) * 100
                fib_powers.append(f'{pn+ps:8.2f}')

            with open(modes_file, 'a', encoding='utf-8') as f:
                f.write(f'{step:7d} {dom_n:5d} {frac_n:6.1f} {dom_s:5d} {frac_s:6.1f}'
                        + ''.join(fib_powers) + '\n')
            # Angular Fourier-coefficient arguments for spatial-pattern orientation
            ph_n = pole_angular_phases(ey, pole_sign=1, track_modes=track_modes)
            ph_s = pole_angular_phases(ey, pole_sign=-1, track_modes=track_modes)

            with open(phases_file, 'a', encoding='utf-8') as f:
                parts = [f'{step:7d}']
                for ph in [ph_n, ph_s]:
                    for m in track_modes:
                        c = ph.get(m, 0j)
                        parts.append(f' {c.real:12.6e} {c.imag:12.6e}')
                f.write(''.join(parts) + '\n')

        # Periodic checkpoint
        if step > 0 and step % CKPT_INTERVAL == 0:
            save_checkpoint(step, solver, u_hat, ey_hat, ei_hat, run_dir)

        if progress:
            # The report cadence need not align with mode analysis.  Refresh all
            # diagnostics from this report's field when no mode sample ran at
            # this step, so the console always shows current, meaningful values.
            if not mode_sample:
                modes_n, _, _ = pole_angular_modes(ey, pole_sign=1)
                modes_s, _, _ = pole_angular_modes(ey, pole_sign=-1)
                ph_n = pole_angular_phases(ey, pole_sign=1, track_modes=track_modes)
                ph_s = pole_angular_phases(ey, pole_sign=-1, track_modes=track_modes)

            # Compute instantaneous coefficient argument of m=5 for orientation diagnostics
            m5_phase_n = np.angle(ph_n.get(5, 0j)) if ph_n else 0
            m5_phase_s = np.angle(ph_s.get(5, 0j)) if ph_s else 0
            fib_str = ' '.join([f'm={fib}:{modes_n.get(fib,0)*100:4.1f}%' for fib in [5, 8, 13]])
            print(f'  step={step:5d} a={a:.4f} H={H:.4f} r={r:.4f} q={qm:.4f} '
                  f'N:m5arg={np.degrees(m5_phase_n):6.1f}° S:m5arg={np.degrees(m5_phase_s):6.1f}° [{fib_str}]')

    # Final checkpoint
    if step > 0:
        save_checkpoint(step, solver, u_hat, ey_hat, ei_hat, run_dir)

    print(f'\n[bubble_spiral] Done -> {run_dir}')
    print(f'  Log:       {logfile}')
    print(f'  Modes:     {modes_file}')
    print(f'  Coefficient arguments: {phases_file}')
    return run_dir

# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    p = argparse.ArgumentParser(
        description='Bubble PDE: Fibonacci spatial modes + pole-pattern orientation diagnostics (two-pole gate)')
    p.add_argument('--resume', type=str, default=None,
                   help='Resume from run directory')
    p.add_argument('--steps', type=int, default=8000,
                   help='Number of RK2 steps (default: 8000)')
    p.add_argument('--N', type=int, default=48,
                   help='Grid resolution (default: 48)')
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
    p.add_argument('--bamp', type=float, default=0.3,
                   help='Bubble amplitude relative to mean (default: 0.3)')
    p.add_argument('--brx', type=float, default=0.7,
                   help='Bubble x-radius (default: 0.7; L=2*brx/phi^2~0.53)')
    p.add_argument('--bry', type=float, default=None,
                   help='Bubble y-radius (default: brx/phi)')
    p.add_argument('--brz', type=float, default=None,
                   help='Bubble z-radius (default: brx/phi^2)')
    p.add_argument('--mode_int', type=int, default=200,
                   help='Mode analysis interval (default: 200)')

    args = p.parse_args()

    if args.bry is None:
        args.bry = args.brx / PHI
    if args.brz is None:
        args.brz = args.brx / PHI**2
    print('=== Bubble PDE: Fibonacci Spatial Modes + Orientation Diagnostics ===')
    print(f'  Gate: two-pole  |  N={args.N}  |  Steps: {args.steps}')
    print(f'  Bubble axes: ({args.brx:.3f}, {args.bry:.3f}, {args.brz:.3f}) '
          f'ratio = ({args.brx/args.brz:.3f} : {args.bry/args.brz:.3f} : 1)')
    print(f'  lambda_5 (tested geometry scale) = L/5 = {2*args.brz/5:.3f}')
    print(f'  Tested coefficient-argument drift scale: d(arg a_m)/dt ~ lambda = {args.lam} rad/step')
    print()

    run_bubble_spiral(args)