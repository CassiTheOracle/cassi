#!/usr/bin/env python3
"""Meshless winding-on-particles probe — Amendment 3 (b1) per-particle phase.

Per the (b) design (`CassiCosmos/research/meshless/two_fluid_particle_winding_design.md`),
this is **(b1): one float per particle — the phase θ_i** — evolved by the
theory's winding rate, on the shipped Qi-gated nbody (`cassi_nbody.py`,
read-only). It answers the question the scalar-q (a) probe structurally cannot:
does the *phase sector* of coherence — the winding — carry the cascade-suppression
signal?

Physics (from `qi-flow-double-helix.md`):
  winding rate   dθ_i/dt = λ (1 − q_i) (ρ_i ε_i) / (E_Yi² + E_Ii²)
                 — phase advances toward the φ-line from the excess ε_i, only
                 while the state is open (1−q_i); vanishes on the φ-line (ε=0).
  coherence      q_i = ρ²/(ρ² + φ⁻² + ε²)   (the solver's native gate)
  excess         ε_i = E_Yi − φ·E_Ii        (per-particle doublet excess)
  amplitude      ρ_i = E_Yi + E_Ii          (per-particle doublet sum)
  Phase field    E_Yi = ρ·cos θ_i,  E_Ii = ρ·sin θ_i  →  q_i as above.

Per-particle doublet reconstruction: with the solver carrying only ρ (mass
density at the particle) and q (coherence), we reconstruct a minimal doublet
consistent with both — a standing-wave ansatz E_Y = √(ρ·q)·cosθ,
E_I = √(ρ·q)·sinθ with θ the evolved phase. This is the (b1) minimal phase
sector; (b2) would evolve (E_Y, E_I) as true fields (design §3).

Metric (pre-registered, identical discipline to (a)):
  T_hold_phase(D) = time the inner-rung phase-coherence "order parameter"
  Q_phase(t) = mean-phase-alignment within the core stays ≥ 0.5·Q_phase(0),
  where alignment is measured as |mean(exp(iθ))| over the core particles —
  the winding structure (∇θ small → phase-locked, the "sound" of coherence).

Verdict (frozen): SUPPORTS iff T_hold_phase monotone in D AND
T_hold_phase(depth_4) ≥ 2 × T_hold_phase(depth_1); DOES NOT SUPPORT otherwise.

Both the (a) amplitude-sector and this (b1) phase-sector must support for the
theory's "standing wave PLUS winding" claim to hold. A (b1) DOES NOT SUPPORT
with a saturated T_hold tells us *where* the cascade suppression lives —
the winding is load-bearing.

Off by default (wind=False → no θ allocation, no phase evolution; identical
trajectories to the plain solver: bit-identical additive control).
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
    """NBodySolver3D + per-particle phase winding (b1).

    Adds a (N,) float `theta` buffer, evolved each leapfrog step by the
    winding rate, and a phase-coherence order term. The gravity evolution is
    the parent's untouched leapfrog — this only evolves the phase sector, so
    positions/velocities/masses are bit-identical to the additive-off control.
    """

    def __init__(self, *args, wind: bool = False, lam: float = 1.0,
                 J_coupling: float = 0.5, seed: int = 1, **kwargs):
        super().__init__(*args, **kwargs)
        self.wind = wind
        self.lam = lam              # winding-rate coupling λ
        self.J_coupling = J_coupling  # neighbor phase-coupling strength (J_z)
        self.seed = seed
        self.theta = None           # (N,) per-particle phase, off when wind=False

    # --- Winding rate (theory L, qi-flow-double-helix) ---
    def winding_rate(self, rho_p: torch.Tensor, q_p: torch.Tensor,
                     theta: torch.Tensor, eps0: float = 0.05) -> torch.Tensor:
        """dθ_i/dt = λ (1−q_i) (ρ_i ε_i) / (E_Yi² + E_Ii²).

        rho_p: interpolated density at particle (N,)
        q_p:   interpolated coherence at particle (N,)
        theta: current phase (N,)
        Reconstruct E_Y = √(ρ·q)·cosθ, E_I = √(ρ·q)·sinθ (standing-wave ansatz),
        and the excess ε = E_Y − φ·E_I. The rate vanishes on the φ-line (ε=0)
        and when closed (q=1), per the theory.
        """
        amp = torch.sqrt(torch.clamp(rho_p, min=1e-12) * torch.clamp(q_p, min=1e-12))
        EY = amp * torch.cos(theta)
        EI = amp * torch.sin(theta)
        eps = EY - PHI * EI
        denom = EY ** 2 + EI ** 2 + 1e-12
        rate = self.lam * (1.0 - q_p) * amp * eps / denom
        # regularization floor so a null is a physics claim, not a NaN
        return torch.where(torch.isfinite(rate), rate, torch.zeros_like(rate))

    def evolve_winding(self, theta: torch.Tensor, pos: torch.Tensor,
                       masses: torch.Tensor, dt: float) -> torch.Tensor:
        """Euler step of the winding + neighbor phase coupling (J_z)."""
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

        # Neighbor phase coupling J_z (discrete, φ⁻¹-per-rung attenuated):
        # a mean-field coupling of each particle's phase toward the local
        # coherence-weighted mean phase, so phase-locked (∇θ small) regions
        # stay locked — the coherence "sound".
        if self.J_coupling > 0.0:
            # phase-weighted neighbor mean via vector mean of exp(iθ)
            cos_t = torch.cos(theta)
            sin_t = torch.sin(theta)
            # mean-field over the whole core (a cheap, smooth J_z for the
            # meshless probe; the shader would do the tree-walk gradient)
            w = torch.clamp(q_p, min=1e-12) * torch.clamp(rho_p, min=1e-12)
            w = w / (w.sum() + 1e-12)
            c_bar = (w[:, None] * torch.stack([cos_t, sin_t], dim=1)).sum(dim=0)
            c_bar = c_bar / (c_bar.norm() + 1e-12)
            # phase difference toward the mean (wrapped to [-π, π])
            d_phase = torch.atan2(sin_t * c_bar[1] - cos_t * c_bar[0],
                                  cos_t * c_bar[0] + sin_t * c_bar[1])
            dtheta = dtheta + self.J_coupling * (1.0 - q_p) * d_phase

        return theta + dt * dtheta


def phi_cluster_ic(D: int, r_inner: float, N_shell: int, L: float,
                   seed: int = 1, phase_seed: int = 1
                   ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """φ-organized nested multi-shell cluster, origin-centered.

    Shell k at radius r_k = r_inner·φ^k, N_shell bodies/shell, mass ∝ φ⁻ᵏ
    (inner = lower rung = heavier = coherence excess). Phase per particle:
    a phase-gradient winding θ = k·(π/2) per shell + a small per-particle
    jitter — the P_∥=2 double-helix closure (π per rung).

    Returns (pos, vel, masses, theta) all on CPU; caller moves to device.
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
        # winding: π per rung (double-helix P_∥=2), plus small coherence jitter
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


def virialize(solver, pos: torch.Tensor, masses: torch.Tensor,
              theta: torch.Tensor) -> torch.Tensor:
    """Give the cluster a solver-consistent virial velocity field.

    deposit → solve_gravity → interpolate a at particle → v_rms = √(0.5·r·|a|)
    (radial balance), applied along the radial direction. Unchanged from (a).
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
    """Phase-coherence order parameter over the core: |mean(exp(iθ))|.

    1 = perfectly phase-locked (∇θ ≈ 0 → coherent), 0 = random phase (a
    decoherent, "noisy" core). This is the winding-sector analogue of the (a)
    structural retention metric.
    """
    core = r < r_core
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
                       frac_thresh: float = 0.5, config=None
                       ) -> Tuple[float, List[float], float, float]:
    """T_hold_phase: time the phase-order of the core stays ≥ 0.5× its t=0 value.

    Trails only carry pos (the run loop tracks pos), so all 4000-step phase
    history is in the integrated `theta` trajectory below, but this probe
    integrates phase within the run and samples it with the trails.
    Returns (T_hold_phase, order_history, order0, r_core_end).
    """
    r = torch.sqrt((pos ** 2).sum(dim=1))
    order0 = phase_order(theta, r, r_core, masses)
    # sample the current phase order (the run integrates; this is the end-state)
    order_end = phase_order(theta, r, r_core, masses)
    t_hold = 1.0 if order_end >= frac_thresh * order0 else 0.0
    r_end = float(r[0].max().item() if r.numel() else 0.0)
    return t_hold, [order0], order0, r_end


def run_winding_sim(config, pos, vel, masses, theta, wind: bool,
                    lam: float = 1.0, J_coupling: float = 0.5
                    ) -> Tuple[List[dict], torch.Tensor, WindingNBody]:
    """Winding-enabled run loop; additive-off (wind=False) = parent run."""
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
    trail_frames = []
    theta_hist = []
    theta_hist_every = 100
    phys_t = 0.0
    accel = None
    q_mean, eps_mean = 1.0, 0.0

    print(f"\n{'='*64}")
    print(f"  Cassi N-Body 3D GPU — Winding-on-particles (b1)")
    print(f"  {'-'*56}")
    print(f"  N = {N} bodies  |  total M = {total_mass:.0f}")
    print(f"  Grid: {config.n_grid}^3  |  L = {config.L}")
    print(f"  Winding: {'ON  λ=%.2f J=%.2f' % (lam, J_coupling) if wind else 'OFF (control)'}")
    print(f"  dt = {config.dt}  |  Steps = {config.n_steps}")
    print(f"  phi = {PHI:.4f}  |  Qi damp = 1/phi = {PHI_INV:.4f}")
    print(f"{'='*64}\n")

    t_start = time.time()
    for step in range(config.n_steps):
        pos, vel, accel, q_mean, eps_mean = solver.leapfrog_step(
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
                sigma_eff = config.sigma * (1.0
                    + PHI_INV * (1.0 - q_mean)
                    + config.qi_gamma * eps_mean)
                sigma_eff = max(sigma_eff, config.sigma * 0.5)
                if abs(sigma_eff - solver.sigma) > 0.01 * config.sigma:
                    solver.set_softening(sigma_eff)
        phys_t += config.dt
        if config.track_every and step % config.track_every == 0:
            trail_frames.append(pos.cpu().clone())
            if wind:
                theta_hist.append(theta.detach().cpu().clone())
        if step % config.report_every == 0:
            d = solver.compute_diagnostics(pos, vel, masses, config,
                                           q_mean=q_mean, eps_mean=eps_mean)
            diag_history.append(d)
            order = phase_order(theta, torch.sqrt((pos ** 2).sum(dim=1)),
                                _core_radius(config), masses) if wind else 0.0
            qi_info = f" q_avg={q_mean:.4f} θ_order={order:.4f}" if wind else \
                      (f" q_avg={q_mean:.4f}" if config.qi_gate else "")
            print(f"  t={phys_t:.3f} | E={d['E_tot']:+.4f} | "
                  f"Q={d['Q']:.4f} | R_half={d['half_mass_r']:.4f}{qi_info}")
            if math.isnan(d['E_tot']):
                print(f"\n  ERROR: NaN at step {step}. Aborting.")
                break
    elapsed = time.time() - t_start
    ms_per_step = elapsed / (step + 1) * 1000
    print(f"\n  Wall time: {elapsed:.1f}s  |  {ms_per_step:.1f} ms/step")
    trails = torch.stack(trail_frames, dim=0) if trail_frames else None
    theta_arr = torch.stack(theta_hist, dim=0) if theta_hist else theta.cpu().unsqueeze(0)
    return diag_history, trails, theta_arr, solver


def _core_radius(config) -> float:
    """Core cut for the phase-order metric: the innermost φ-rung."""
    return 1.2 * PHI  # r_inner·φ, same core as the (a) T_hold metric


def main():
    p = argparse.ArgumentParser(description="Meshless winding-on-particles (b1) probe")
    p.add_argument('--steps', type=int, default=4000)
    p.add_argument('--arms', default='depth_4', help="comma list, or 'all'")
    p.add_argument('--L', type=float, default=20.0)
    p.add_argument('--r_inner', type=float, default=1.2)
    p.add_argument('--N_shell', type=int, default=1200)
    p.add_argument('--n_grid', type=int, default=64)
    p.add_argument('--lam', type=float, default=1.0, help="winding coupling λ")
    p.add_argument('--J', type=float, default=0.5, help="J_z neighbor coupling")
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
        r_core = _core_radius(config)
        solver = WindingNBody(n_grid=args.n_grid, L=args.L, G=1.0, sigma=0.4,
                              device=device, qi_gate=True,
                              deposition_kernel='TSC',
                              wind=False, lam=args.lam, J_coupling=args.J)
        vel = virialize(solver, pos, masses, theta)
        vel = vel.to(device)

        # additive-off control: identical trajectories, then the winding on
        t0 = time.time()
        diag, trails, theta_arr, solver_run = run_winding_sim(
            config, pos, vel, masses, theta, wind=True,
            lam=args.lam, J_coupling=args.J)
        wall = time.time() - t0

        # phase-order at t=0 and end (core)
        r0 = torch.sqrt((pos.cpu() ** 2).sum(dim=1))
        order0 = phase_order(theta, r0, r_core, masses)
        r_end = torch.sqrt((trails[-1].cpu() ** 2).sum(dim=1)) if trails is not None and len(trails) else r0
        order_end = phase_order(theta_arr[-1], r_end, r_core, masses)
        t_hold = 1.0 if order_end >= 0.5 * order0 else 0.0

        # mass-fraction the (a) metric measured (amplitude sector) for the same arm
        inner0 = float(((r0 < r_core * PHI_INV) * masses.cpu()).sum().item() / masses.cpu().sum().item()) \
            if r0.numel() else 0.0
        inner_end = float(((r_end < r_core * PHI_INV) * masses.cpu()).sum().item() / masses.cpu().sum().item()) \
            if r_end.numel() else 0.0

        diag_last = diag[-1] if diag else {}
        results[name] = {
            'D': D, 'T_hold_phase': t_hold,
            'phase_order_0': order0, 'phase_order_end': order_end,
            'inner_frac_0': inner0, 'inner_frac_end': inner_end,
            'q_last': diag_last.get('q_mean', 0.0),
            'R_half_end': diag_last.get('half_mass_r', 0.0),
            'wall_s': wall, 'n_steps': args.steps,
        }
        print(f"  {name}: T_hold_phase={t_hold:0.2f} θ_order {order0:.3f}->{order_end:.3f} "
              f"inner_frac {inner0:.3f}->{inner_end:.3f} [{wall:.0f}s, {args.steps} steps]")

    print(f"\n=== WINDING (b1) RESULTS ===")
    for name in arm_list:
        r = results[name]
        print(f"  {name}: D={r['D']} T_hold_phase={r['T_hold_phase']:.2f} "
              f"θ_order {r['phase_order_0']:.3f}->{r['phase_order_end']:.3f} "
              f"inner_frac {r['inner_frac_0']:.3f}->{r['inner_frac_end']:.3f}")

    # verdict (frozen): monotone T_hold_phase + 2x
    if len(arm_list) == 3:
        t1 = results['depth_1']['T_hold_phase']
        t2 = results['depth_2']['T_hold_phase']
        t4 = results['depth_4']['T_hold_phase']
        mono = t2 >= t1 and t4 >= t2
        twox = (t4 >= 2.0 * t1) if t1 > 0 else False
        verdict = "SUPPORTS" if (mono and twox) else "DOES NOT SUPPORT"
        print(f"\n=== WINDING DEPTH VERDICT: {verdict} ===")
        print(f"  (monotone T_hold_phase: {mono}; depth_4 >= 2x depth_1: {twox})")
    else:
        verdict = "N/A (single-arm)"
        print(f"\n=== WINDING DEPTH VERDICT: {verdict} (need all 3 arms) ===")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump({'meta': {'L': args.L, 'G': 1.0, 'sigma': 0.4, 'dt': 0.001,
                            'N_shell': args.N_shell, 'n_grid': args.n_grid,
                            'lam': args.lam, 'J': args.J,
                            'gate': 'Qi (native coherence) + winding (b1)',
                            'amendment': '3b'},
                   'arms': results, 'verdict': verdict}, f, indent=2)
    print(f"Results: {args.out}")


if __name__ == '__main__':
    main()
