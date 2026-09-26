#!/usr/bin/env python3
"""Meshless winding-on-particles probe — Amendment 3 (b1) density-plane angle.

Per Amendment 3(b) in
``field-experience/soliton-self-trapping-pre-registration.md`` §12, this is
**(b1): one float per particle—the density-plane angle theta_d,i**—
evolved by an explicit meshless surrogate diagnostic on the shipped legacy
density-memory adaptive-softening heuristic N-body (`cassi_nbody.py`, read-only).
density-angle sector carries a cascade-suppression signal; it does not
reconstruct the canonical two-fluid fields or verify canonical conversion.

Reference canonical-form diagnostic (from `qi-flow-double-helix.md`):
  winding rate   dθ_{d,i}/dt = λ (1 − q_i) (ρ_i ε_i) / (E_Yi² + E_Ii²)
                 — the density-plane angle advances toward the φ-line from
                   the excess ε_i, only while the state is open (1−q_i);
                   it vanishes on the φ-line (ε=0).

The meshless inputs are an explicit surrogate substitution, not the native
canonical state:
  rho_p         interpolated N-body mass-density at the particle
  q_p           legacy meshless proxy rho/(rho + φ⁻²), with the probe's
                 low-density closure threshold
  eps_i         E_Yi − φ·E_Ii, evaluated from the diagnostic ansatz below
  E_Yi, E_Ii    √(rho_p·q_p)·cos θ_{d,i}, √(rho_p·q_p)·sin θ_{d,i}

This ansatz is intentionally inserted into the canonical-form angle-rate
diagnostic.  It is not a reconstruction of canonical fields: in particular,
it need not satisfy canonical rho = E_Y + E_I or
q = rho²/(rho² + φ⁻² + eps²).  The resulting winding rate is therefore a
meshless surrogate measurement, not verification of canonical conversion.
This is a conditional mean-field surrogate. A fuller particle extension would
need nonnegative canonical densities together with an independent phase
variable, or explicit complex amplitudes; this script supplies neither. Across
the depth sweep, ``D`` also changes particle count, total mass, outer radius,
and initial inner-rung fraction, so the arms are not controlled
counterfactuals.
Metric:
  T_hold_phase(D) = time the inner-rung density-angle coherence "order
  parameter" Q_phase(t) (the frozen output name) stays ≥ 0.5·Q_phase(0),
  where alignment is measured as |mean(exp(iθ_d))| over the core particles—
  the density-angle winding structure (∇θ_d small → angle-locked, the
  "sound" of coherence).

The repository-level scientific verdict is always INCONCLUSIVE because depth
changes several causal variables, the explicit global aligner drives the
measured statistic, and the executable does not run a matched ``wind=False``
control. Equal full-horizon holds additionally censor the registered depth
discriminator.

``wind=False`` avoids density-angle allocation and evolution, but this script
does not execute or record that control, so trajectory identity is not an
empirical result of the probe.
"""
import argparse
import math
import time
import json
import os
from typing import Tuple, List, Optional, Dict

import numpy as np
import torch

# --- Cassi constants ---
PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_INV = 1.0 / PHI
PHI_INV2 = PHI_INV ** 2

import cassi_nbody as NB


class WindingNBody(NB.NBodySolver3D):
    """NBodySolver3D plus a per-particle density-angle observer.

    The extra angle is evolved after each parent leapfrog step and does not
    feed back into gravity, positions, velocities, or masses. The executable
    records only the observer-on branch; it does not verify an additive-off
    trajectory.
    """

    def __init__(self, *args, wind: bool = False, lam: float = 1.0,
                 J_coupling: float = 0.5, seed: int = 1, **kwargs):
        super().__init__(*args, **kwargs)
        self.wind = wind
        self.lam = lam              # winding-rate coupling λ
        self.J_coupling = J_coupling  # global density-angle alignment strength
        self.seed = seed
        self.theta = None           # (N,) per-particle density-plane angle

    # --- Winding-rate diagnostic (canonical-form template on surrogate inputs) ---
    def winding_rate(self, rho_p: torch.Tensor, q_p: torch.Tensor,
                     theta: torch.Tensor, eps0: float = 0.05) -> torch.Tensor:
        """Apply the canonical-form angle-rate template to meshless inputs.

        rho_p is interpolated N-body mass-density, and q_p is the legacy
        meshless proxy rho/(rho + phi^-2), not the canonical gate.  The
        diagnostic ansatz evaluates
        E_Y = sqrt(rho_p*q_p)*cos(theta_d),
        E_I = sqrt(rho_p*q_p)*sin(theta_d),
        then eps = E_Y - phi*E_I.  These E components are surrogate
        coordinates only; they are not reconstructed canonical fields and
        need not obey rho = E_Y + E_I or the canonical q identity.  The
        returned rate therefore does not verify canonical conversion.
        """
        amp = torch.sqrt(torch.clamp(rho_p, min=1e-12) * torch.clamp(q_p, min=1e-12))
        EY = amp * torch.cos(theta)
        EI = amp * torch.sin(theta)
        eps = EY - PHI * EI
        denom = EY ** 2 + EI ** 2 + 1e-12
        rate = self.lam * (1.0 - q_p) * rho_p * eps / denom
        # Keep the surrogate diagnostic finite; this is not a physics claim.
        return torch.where(torch.isfinite(rate), rate, torch.zeros_like(rate))

    def evolve_winding(self, theta: torch.Tensor, pos: torch.Tensor,
                       masses: torch.Tensor, dt: float) -> torch.Tensor:
        """Euler-step the surrogate angle and global mean-field aligner.

        The low-density rule sets the grid proxy to ``q=1`` below one percent
        of the instantaneous density maximum. This freezes the local winding
        term there; it is a model intervention, not the canonical coherence
        identity or a neutral finite-value safeguard.
        """
        if not self.wind:
            return theta
        rho = self.deposit_density(pos, masses)
        rho_max = rho.max().item() if rho.numel() else 1.0
        q = rho / (rho + PHI_INV2 + 1e-12)
        if rho_max > 1e-10:
            q = torch.where(rho < 0.01 * rho_max, torch.ones_like(q), q)
        rho_p = self._interpolate_scalar(rho, pos)
        q_p = self._interpolate_scalar(q, pos)

        dtheta = self.winding_rate(rho_p, q_p, theta)

        # Optional global alignment. This is a whole-ensemble q_p*rho_p-
        # weighted vector mean, not a spatial-neighbor interaction, tree walk,
        # gradient current, or canonical J_z closure. It explicitly drives the
        # diagnostic angles toward one direction and therefore cannot, by
        # itself, establish emergent phase locking.
        if self.J_coupling > 0.0:
            cos_t = torch.cos(theta)
            sin_t = torch.sin(theta)
            w = torch.clamp(q_p, min=1e-12) * torch.clamp(rho_p, min=1e-12)
            w = w / (w.sum() + 1e-12)
            c_bar = (w[:, None] * torch.stack([cos_t, sin_t], dim=1)).sum(dim=0)
            c_bar = c_bar / (c_bar.norm() + 1e-12)
            # Wrapped angular displacement toward the global mean.
            d_phase = torch.atan2(cos_t * c_bar[1] - sin_t * c_bar[0],
                                  cos_t * c_bar[0] + sin_t * c_bar[1])
            dtheta = dtheta + self.J_coupling * (1.0 - q_p) * d_phase
        return theta + dt * dtheta

def phi_cluster_ic(D: int, r_inner: float, N_shell: int, L: float,
                   seed: int = 1, phase_seed: int = 1
                   ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Construct the signed depth-sweep initial condition.

    Shell ``k`` lies at ``r_inner*phi**k``, contains ``N_shell`` bodies, and
    assigns per-particle mass proportional to ``phi**(-k)``. The tested
    density-plane angle is ``k*pi/2`` plus small jitter. This initialization is
    not derived from the canonical conversion ODE or a physical double helix.
    Increasing ``D`` changes particle count, total mass, outer radius, and the
    initial inner-rung fraction, so the arms are not controlled
    counterfactuals.

    Returns ``(pos, vel, masses, theta)`` on CPU.
    """
    gen = torch.Generator(device='cpu').manual_seed(seed)
    pos_list, mass_list, theta_list = [], [], []
    for k in range(D):
        r_k = r_inner * (PHI ** k)
        m_k = PHI_INV ** k
        # Fibonacci-sphere uniform placement on shell k
        i = torch.arange(N_shell, dtype=torch.float64)
        phi_ang = 2.0 * math.pi * i / PHI
        cos_th = 1.0 - 2.0 * (i + 0.5) / N_shell
        sin_th = torch.sqrt(torch.clamp(1.0 - cos_th ** 2, min=0.0))
        x = r_k * sin_th * torch.cos(phi_ang)
        y = r_k * sin_th * torch.sin(phi_ang)
        z = r_k * cos_th
        pos_k = torch.stack([x, y, z], dim=1)
        # Tested shell-angle ansatz: pi/2 per rung, plus small jitter.
        pgen = torch.Generator(device='cpu').manual_seed(phase_seed + k)
        theta_k = k * (math.pi / 2.0) + 0.05 * torch.randn(N_shell, generator=pgen)
        pos_list.append(pos_k)
        mass_list.append(torch.full((N_shell,), m_k, dtype=torch.float64))
        theta_list.append(theta_k)
    pos = torch.cat(pos_list, dim=0)
    masses = torch.cat(mass_list, dim=0)
    theta = torch.cat(theta_list, dim=0)
    vel = torch.zeros(pos.shape[0], 3, dtype=torch.float64)
    # origin-centered (the solver's convention — leapfrog wraps -L/2..L/2)
    com = pos.mean(dim=0)
    pos = pos - com[None, :]
    return pos, vel, masses, theta


def inward_radial_velocity_seed(
    solver, pos: torch.Tensor, masses: torch.Tensor,
    theta: torch.Tensor
) -> torch.Tensor:
    """Construct the probe's inward radial velocity seed.

    The speed scale is ``sqrt(0.5*r*abs(a_rad))`` and the direction follows
    the gravitational acceleration. This is not a stationary or circular
    virial state, and no global ``2K/abs(PE)=1`` condition is imposed.
    """
    rho = solver.deposit_density(pos, masses)
    ax, ay, az = solver.solve_gravity(rho)
    accel = solver.interpolate_accel(ax, ay, az, pos)
    r = torch.sqrt((pos ** 2).sum(dim=1))
    a_rad = (accel * pos).sum(dim=1) / torch.clamp(r, min=1e-9)
    v_rms = torch.sqrt(torch.clamp(0.5 * r * torch.abs(a_rad), min=0.0))
    vr = torch.zeros_like(accel)
    rmask = r > 1e-9
    rhs = (accel[rmask].double() / torch.clamp(a_rad[rmask].abs(), min=1e-12)[:, None]
           * v_rms[rmask][:, None])
    vr[rmask] = rhs.to(accel.dtype)
    return vr


def phase_order(theta: torch.Tensor, r: torch.Tensor, r_core: float,
                weights: Optional[torch.Tensor] = None) -> float:
    """Density-angle order parameter inside the registered open core.

    The cutoff is ``r < r_core``. The designed second shell lies on that
    boundary, and discrete center-of-mass recentering spreads its particles
    across the cut. The tiny offset only makes near-boundary comparison
    one-sided; it does not provide shell-invariant membership.
    """
    core_tol = 1e-9 * max(1.0, r_core)
    core = r < r_core - core_tol
    if not core.any():
        return 1.0
    t = theta.cpu()[core.cpu()]
    if weights is not None:
        w = weights.cpu()[core.cpu()]
        w = w / (w.sum() + 1e-12)
        c = (w * torch.cos(t)).sum()
        s = (w * torch.sin(t)).sum()
        return float(torch.sqrt(c ** 2 + s ** 2).item())
    return float(torch.sqrt(torch.cos(t).mean() ** 2 + torch.sin(t).mean() ** 2).item())


def measure_hold_phase(theta: torch.Tensor, masses: torch.Tensor,
                       pos: torch.Tensor, r_core: float,
                       frac_thresh: float = 0.5, config=None,
                       sample_times: Optional[List[float]] = None
                       ) -> Dict[str, object]:
    """Measure phase-order retention over sampled trajectories.

    ``theta`` must have shape ``(n_frames, N)`` and ``pos`` shape
    ``(n_frames, N, 3)``. ``sample_times`` gives the physical time for each
    frame; the run loop records exact times, including t=0 and the terminal
    state.
    """
    if theta.ndim != 2:
        raise ValueError("theta trajectory must have shape (n_frames, N)")
    if pos.ndim != 3 or pos.shape[-1] != 3:
        raise ValueError("pos trajectory must have shape (n_frames, N, 3)")
    if theta.shape[0] != pos.shape[0] or theta.shape[1] != pos.shape[1]:
        raise ValueError("theta and pos trajectories must share frame/particle dimensions")
    if masses.ndim != 1 or masses.shape[0] != theta.shape[1]:
        raise ValueError("masses must have shape (N,)")
    if theta.shape[0] == 0:
        raise ValueError("trajectories must contain at least the t=0 frame")

    theta_cpu = theta.cpu()
    pos_cpu = pos.cpu()
    masses_cpu = masses.cpu()
    order_history: List[float] = []
    radii: List[torch.Tensor] = []
    for theta_frame, pos_frame in zip(theta_cpu, pos_cpu):
        r = torch.sqrt((pos_frame ** 2).sum(dim=1))
        radii.append(r)
        order_history.append(phase_order(theta_frame, r, r_core, masses_cpu))

    order0 = order_history[0] if order_history else 1.0
    threshold = frac_thresh * order0
    if sample_times is None:
        frame_dt = float(getattr(config, 'dt', 1.0))
        frame_dt *= float(getattr(config, 'track_every', 1))
        sample_times = [frame_idx * frame_dt
                        for frame_idx in range(len(order_history))]
    elif len(sample_times) != len(order_history):
        raise ValueError("sample_times must have one entry per trajectory frame")
    elif any(t1 > t2 for t1, t2 in zip(sample_times, sample_times[1:])):
        raise ValueError("sample_times must be nondecreasing")
    t_hold = sample_times[-1] if sample_times else 0.0
    for frame_idx, order in enumerate(order_history):
        if order < threshold:
            t_hold = sample_times[frame_idx]
            break
    r_max_end = float(radii[-1].max().item()) if radii[-1].numel() else 0.0
    return {
        'T_hold_phase': t_hold,
        'order_history': order_history,
        'sample_times': sample_times,
        'phase_order_0': order0,
        'phase_order_end': order_history[-1] if order_history else order0,
        'r_max_end': r_max_end,
    }


def run_winding_sim(config, pos, vel, masses, theta, wind: bool,
                    r_core: float, lam: float = 1.0,
                    J_coupling: float = 0.5
                    ) -> Tuple[List[dict], Optional[torch.Tensor],
                               torch.Tensor, List[float], WindingNBody]:
    """Density-angle-winding run loop; additive-off (wind=False) = parent run."""
    solver = WindingNBody(n_grid=config.n_grid, L=config.L, G=config.G,
                          sigma=config.sigma, device=config.device,
                          qi_gate=config.qi_gate, qi_memory=config.qi_memory,
                          deposition_kernel=config.deposition_kernel,
                          alpha_yin=config.alpha_yin,
                          holographic_bound=config.holographic_bound,
                          holographic_eta=config.holographic_eta,
                          wind=wind, lam=lam, J_coupling=J_coupling)
    if wind:
        theta = theta.to(config.device)
    N = pos.shape[0]
    total_mass = masses.sum().item()
    qi = torch.zeros(config.n_grid, config.n_grid, config.n_grid, device=config.device)
    diag_history = []
    trail_frames = [pos.cpu().clone()]
    theta_hist = [theta.detach().cpu().clone()] if wind else []
    sample_times = [0.0]
    phys_t = 0.0
    accel = None
    legacy_density_proxy_mean = 1.0
    density_memory_residual_mean = 0.0

    print(f"\n{'='*64}")
    print(f"  Cassi N-Body 3D GPU — Winding-on-particles (b1)")
    print(f"  {'-'*56}")
    print(f"  N = {N} bodies  |  total M = {total_mass:.3f}")
    print(f"  Grid: {config.n_grid}^3  | L = {config.L}")
    print(f"  Winding: {'ON' if wind else 'OFF (control)'}  "
          f"lambda={lam:.2f} J={J_coupling:.2f}")
    print(f"  dt = {config.dt}  | Steps = {config.n_steps}")
    print(f"  phi = {PHI:.4f} | density-memory decay = 1/phi = {PHI_INV:.4f}")
    print(f"{'='*64}\n")

    t_start = time.time()
    for step in range(config.n_steps):
        (
            pos,
            vel,
            accel,
            legacy_density_proxy_mean,
            density_memory_residual_mean,
        ) = solver.leapfrog_step(
            pos, vel, masses, config.dt, accel=accel,
            vel_damp=config.vel_damp, qi_gate=config.qi_gate
        )
        if wind:
            theta = solver.evolve_winding(theta, pos, masses, config.dt)
        rho = solver.deposit_density(pos, masses)
        qi = config.qi_damp * qi + (1.0 - config.qi_damp) * rho
        if config.qi_gate:
            solver.qi_field = qi
            if step > 0:
                sigma_eff = config.sigma * (
                    1.0 + PHI_INV * (1.0 - legacy_density_proxy_mean)
                    + config.qi_gamma * density_memory_residual_mean
                )
                sigma_eff = max(sigma_eff, config.sigma * 0.5)
                if abs(sigma_eff - config.sigma) > 0.01 * config.sigma:
                    solver.set_softening(sigma_eff)
        phys_t += config.dt

        if config.track_every and (step + 1) % config.track_every == 0:
            trail_frames.append(pos.cpu().clone())
            if wind:
                theta_hist.append(theta.detach().cpu().clone())
            sample_times.append(phys_t)
        if step % config.report_every == 0:
            d = solver.compute_diagnostics(
                pos, vel, masses, config,
                legacy_density_proxy_mean=legacy_density_proxy_mean,
                density_memory_residual_mean=density_memory_residual_mean,
            )
            diag_history.append(d)
            order = phase_order(
                theta, torch.sqrt((pos ** 2).sum(dim=1)), r_core, masses
            ) if wind else 0.0
            proxy_info = (
                f" legacy_density_proxy_mean={legacy_density_proxy_mean:.4f}"
                f" theta_order={order:.4f}"
                if wind else
                (f" legacy_density_proxy_mean={legacy_density_proxy_mean:.4f}"
                 if config.qi_gate else "")
            )
            print(f"  t={phys_t:.3f} | E={d['E_tot']:+.4f} | "
                  f"Q={d['Q']:.4f} | R_half={d['half_mass_r']:.4f}"
                  f"{proxy_info}")
            if math.isnan(d['E_tot']):
                print(f"\n  ERROR: NaN energy at step {step}. Aborting.")
                break
    if not sample_times or sample_times[-1] < phys_t:
        trail_frames.append(pos.cpu().clone())
        if wind:
            theta_hist.append(theta.detach().cpu().clone())
        sample_times.append(phys_t)
    elapsed = time.time() - t_start
    ms_per_step = elapsed / max(config.n_steps, 1) * 1000
    print(f"\n  Wall time: {elapsed:.1f}s  |  {ms_per_step:.1f} ms/step")
    # Expose the final sampled legacy diagnostic for the arm summary.
    solver.legacy_density_proxy_mean = legacy_density_proxy_mean
    solver.density_memory_residual_mean = density_memory_residual_mean
    trails = torch.stack(trail_frames, dim=0) if trail_frames else None
    theta_arr = torch.stack(theta_hist, dim=0) if theta_hist else theta.cpu().unsqueeze(0)
    return diag_history, trails, theta_arr, sample_times, solver


def _core_radius(r_inner: float) -> float:
    """Registered open-core cutoff at the second shell radius."""
    return r_inner * PHI


def main():
    p = argparse.ArgumentParser(description="Meshless winding-on-particles (b1) probe")
    p.add_argument('--steps', type=int, default=4000)
    p.add_argument('--arms', default='depth_4', help="comma list, or 'all'")
    p.add_argument('--L', type=float, default=20.0)
    p.add_argument('--r_inner', type=float, default=1.2)
    p.add_argument('--N_shell', type=int, default=1200)
    p.add_argument('--n_grid', type=int, default=64)
    p.add_argument('--lam', type=float, default=1.0, help="winding coupling λ")
    p.add_argument('--J', type=float, default=0.5,
                   help="global density-angle alignment strength")
    p.add_argument('--out', type=str, default='runs/meshless_winding.json')
    args = p.parse_args()

    device = NB.get_device()
    print(f"Device: {device}")
    if not torch.cuda.is_available():
        print("[warning] CUDA/ROCm not available — falling back to CPU (slow)")

    arms = {
        'depth_1': 1, 'depth_2': 2, 'depth_4': 4,
    }
    if args.arms == 'all':
        arm_list = list(arms.keys())
    else:
        arm_list = [a.strip() for a in args.arms.split(',')]

    results = {}
    for name in arm_list:
        D = arms[name]
        print(f"\n=== {name}: D={D} r_inner={args.r_inner} ===")
        pos, vel, masses, theta = phi_cluster_ic(D, args.r_inner, args.N_shell,
                                                 args.L)
        pos = pos.to(device)
        vel = vel.to(device)
        masses = masses.to(device)
        theta = theta.to(device)

        config = NB.NBodyConfig(
            n_grid=args.n_grid, L=args.L, G=1.0, sigma=0.4, dt=0.001,
            n_steps=args.steps, qi_gate=True, qi_memory=False,
            deposition_kernel='TSC', report_every=500, track_every=100,
            device=device)
        r_core = _core_radius(args.r_inner)
        solver = WindingNBody(n_grid=args.n_grid, L=args.L, G=1.0, sigma=0.4,
                              device=device, qi_gate=True,
                              deposition_kernel='TSC',
                              wind=False, lam=args.lam, J_coupling=args.J)
        vel = inward_radial_velocity_seed(solver, pos, masses, theta)
        vel = vel.to(device)

        # The executable records only the observer-on branch.
        t0 = time.time()
        diag, trails, theta_arr, sample_times, solver_run = run_winding_sim(
            config, pos, vel, masses, theta, wind=True, r_core=r_core,
            lam=args.lam, J_coupling=args.J)
        wall = time.time() - t0

        phase_metric = measure_hold_phase(
            theta_arr, masses, trails, r_core, config=config,
            sample_times=sample_times)
        order0 = phase_metric['phase_order_0']
        order_end = phase_metric['phase_order_end']
        t_hold = phase_metric['T_hold_phase']
        r0 = torch.sqrt((trails[0].cpu() ** 2).sum(dim=1))
        r_end = torch.sqrt((trails[-1].cpu() ** 2).sum(dim=1))

        # This radial cut intersects the recentered innermost shell. The tiny
        # tolerance controls comparison roundoff but cannot restore shell IDs.
        inner_cut = r_core * PHI_INV
        inner_tol = 1e-9 * max(1.0, inner_cut)
        inner0 = float(((r0 <= inner_cut + inner_tol) * masses.cpu()).sum().item() / masses.cpu().sum().item()) \
            if r0.numel() else 0.0
        inner_end = float(((r_end <= inner_cut + inner_tol) * masses.cpu()).sum().item() / masses.cpu().sum().item()) \
            if r_end.numel() else 0.0

        diag_last = diag[-1] if diag else {}
        total_mass = float(masses.sum().item())
        outer_radius = args.r_inner * PHI ** (D - 1)
        results[name] = {
            'D': D, 'N': int(masses.numel()),
            'total_mass': total_mass, 'outer_radius': outer_radius,
            'T_hold_phase': t_hold,
            'phase_order_0': order0, 'phase_order_end': order_end,
            'phase_order_history': phase_metric['order_history'],
            'phase_sample_times': phase_metric['sample_times'],
            'r_max_end': phase_metric['r_max_end'],
            'inner_frac_0': inner0, 'inner_frac_end': inner_end,
            'legacy_density_proxy_last_sample': getattr(
                solver_run, 'legacy_density_proxy_mean', 0.0),
            'R_half_end': diag_last.get('half_mass_r', 0.0),
            'wall_s': wall, 'n_steps': args.steps,
        }
        print(f"  {name}: N={masses.numel()} M={total_mass:.1f} "
              f"R_outer={outer_radius:.3f} T_hold_phase={t_hold:0.2f} "
              f"theta_order {order0:.3f}->{order_end:.3f} "
              f"inner_frac {inner0:.3f}->{inner_end:.3f} "
              f"[{wall:.0f}s, {args.steps} steps]")

    print(f"\n=== WINDING (b1) RESULTS ===")
    for name in arm_list:
        r = results[name]
        print(f"  {name}: D={r['D']} N={r['N']} M={r['total_mass']:.1f} "
              f"R_outer={r['outer_radius']:.3f} "
              f"T_hold_phase={r['T_hold_phase']:.2f} "
              f"theta_order {r['phase_order_0']:.3f}->{r['phase_order_end']:.3f} "
              f"inner_frac {r['inner_frac_0']:.3f}->{r['inner_frac_end']:.3f}")

    # The registered arithmetic is retained as an audit diagnostic only. The
    # invalid protocol cannot receive a SUPPORTS/DOES NOT SUPPORT label.
    if len(arm_list) == 3:
        t1 = results['depth_1']['T_hold_phase']
        t2 = results['depth_2']['T_hold_phase']
        t4 = results['depth_4']['T_hold_phase']
        monotone = t2 > t1 and t4 > t2
        at_least_2x = (t4 >= 2.0 * t1) if t1 > 0 else False
        legacy_metric_pattern = (
            "MONOTONE_AND_2X" if monotone and at_least_2x
            else "MONOTONE_BELOW_2X" if monotone
            else "NOT_MONOTONE"
        )
        horizon = config.n_steps * config.dt
        all_horizon_censored = all(
            math.isclose(result['T_hold_phase'], horizon,
                         rel_tol=0.0, abs_tol=max(1e-12, 0.5 * config.dt))
            for result in results.values()
        )
        print(f"\n=== WINDING LEGACY METRIC PATTERN: "
              f"{legacy_metric_pattern} ===")
        print(f"  strictly increasing T_hold_phase: {monotone}; "
              f"depth_4 >= 2x depth_1: {at_least_2x}; "
              f"all horizon-censored: {all_horizon_censored}")
    else:
        legacy_metric_pattern = "N/A (requires all three arms)"
        all_horizon_censored = False
        print("\n=== WINDING LEGACY METRIC PATTERN: "
              "N/A (requires all three arms) ===")
    frozen_metric_branch = "UNSCOREABLE (protocol invalid)"
    verdict = "INCONCLUSIVE"
    print(f"=== FROZEN METRIC BRANCH: {frozen_metric_branch} ===")
    print("=== SCIENTIFIC VERDICT: INCONCLUSIVE ===")
    print("  Protocol validity: FAIL (confounded depth arms, imposed global "
          "alignment, low-density q override, no executed additive-off "
          "control, and raw periodic-box radii).")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump({'meta': {'L': args.L, 'G': 1.0, 'sigma': 0.4, 'dt': 0.001,
                            'N_shell': args.N_shell, 'n_grid': args.n_grid,
                            'position_seed': 1, 'phase_seed': 1,
                            'lam': args.lam, 'J': args.J,
                            'gate': 'legacy density proxy + density-angle '
                                    'surrogate + global mean-field alignment',
                            'amendment': '3b',
                            'protocol_valid': False,
                            'confounds': [
                                'particle_count', 'total_mass', 'outer_radius',
                                'initial_inner_fraction',
                                'inward_radial_velocity_seed',
                                'imposed_global_alignment',
                                'low_density_q_override',
                                'no_executed_additive_off_control',
                                'raw_periodic_box_radii',
                                'noncanonical_density_angle_surrogate',
                            ]},
                   'arms': results,
                   'legacy_metric_pattern': legacy_metric_pattern,
                   'frozen_metric_branch': frozen_metric_branch,
                   'all_horizon_censored': all_horizon_censored,
                   'verdict': verdict}, f, indent=2)
    print(f"Results: {args.out}")


if __name__ == '__main__':
    main()
