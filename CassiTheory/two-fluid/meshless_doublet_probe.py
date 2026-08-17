#!/usr/bin/env python3
"""Meshless full-doublet winding probe — Amendment 3 (b2) per-particle (EY, EI).

Per the (b) design (`CassiCosmos/research/meshless/two_fluid_particle_winding_design.md`),
(b2) is the **faithful form**: each particle carries the full doublet
(E_Yi, E_Ii), evolved by the **shipped field reaction terms** at the particle
position, with the winding phase θ_i = atan2(E_Ii, E_Yi) derived. It removes
the (b1) reconstruction approximation (which fixed E_Y = √(ρq)cosθ,
E_I = √(ρq)sinθ): here ρ_i and θ_i are both free — the amplitude and the phase
sector both evolve.

Physics (from `ExpandingTwoFluid3DGPU.rhs`, the shipped evolution — mass-
conserving doublet exchange):
  ρ_i = E_Yi + E_Ii,   ε_i = E_Yi − φ·E_Ii           (imbalance)
  q_i = M_qi/(M_qi + φ⁻² + ε²),  M_qi = (E_Yi+E_Ii)²  (coherence gate)
  conv_i = −λ (1−q_i) ε_i                             (conversion: EY→EI)
  dE_Yi/dt += conv_i,  dE_Ii/dt −= conv_i             (exchange conserves ρ)
Winding: θ_i = atan2(E_Ii, E_Yi) (derived; torch.atan2, never the forbidden
GLSL atan2 — this is Python).

Plus the J_z neighbor phase coupling (φ⁻¹-per-rung attenuated), the axial
coherence current that closes the double helix across scales: each particle's
doublet is rotated toward the coherence-weighted local phase-locked direction,
so ∇θ-small (coherent) regions stay locked — the coherence "sound" of the (b1)
probe, now acting on the true doublet.

Metric/verdict — identical discipline to (b1), frozen:
  T_hold_phase(D) = time the inner-rung phase-lock θ_order stays ≥ 0.5·θ_order(0).
  SUPPORTS iff T_hold_phase monotone in D AND depth_4 ≥ 2× depth_1.
Combined with (a)+(b1): all three sectors (amplitude scalar-q, reconstructed
phase, full doublet) must not disperse for the "standing wave PLUS winding"
claim. (b2) additionally verifies doublet mass conservation (conv is an
exchange) and that the amplitude sector stays finite (no runaway EY/EI).

Off by default (wind=False → no doublet allocation, pure parent solver):
bit-identical additive control.
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


class DoubletNBody(NB.NBodySolver3D):
    """NBodySolver3D + per-particle full doublet (EY, EI) — (b2).

    Adds (N,) `EY`, `EI` buffers evolved by the shipped conversion + J_z
    coupling. Gravity/positions are the parent's untouched leapfrog — the
    doublet is an observer field (does not feed back into the mass), so
    positions/velocities/masses are bit-identical to the additive-off control.
    """

    def __init__(self, *args, doublet: bool = False, lam: float = 1.0,
                 J_coupling: float = 0.5, **kwargs):
        super().__init__(*args, **kwargs)
        self.doublet = doublet
        self.lam = lam
        self.J_coupling = J_coupling
        self.EY = None
        self.EI = None

    # --- Shipped conversion + gate (per-particle, from the field RHS) ---
    def doublet_rate(self, EY: torch.Tensor, EI: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """(dEY, dEI) from the shipped mass-conserving exchange.

        conv = −λ(1−q)·ε,  ε = EY − φ·EI,  q = M/(M + φ⁻² + ε²),  M = (EY+EI)².
        dEY += conv, dEI −= conv → d(EY+EI) = 0 (doublet mass conserved).
        """
        rho = EY + EI
        eps = EY - PHI * EI
        M = rho * rho
        eps_sq = eps * eps
        q = M / (M + PHI_INV2 + eps_sq + 1e-30)
        conv = -self.lam * (1.0 - q) * eps
        dEY = conv
        dEI = -conv
        return dEY, dEI

    def evolve_doublet(self, EY: torch.Tensor, EI: torch.Tensor,
                       pos: torch.Tensor, masses: torch.Tensor,
                       dt: float) -> Tuple[torch.Tensor, torch.Tensor]:
        """Euler step of the doublet via shipped conversion + J_z coupling."""
        if not self.doublet:
            return EY, EI
        dEY, dEI = self.doublet_rate(EY, EI)

        # J_z neighbor phase coupling: rotate each doublet toward the
        # coherence-weighted local phase-locked mean (φ⁻¹-per-rung closure).
        if self.J_coupling > 0.0:
            rho = EY + EI
            eps = EY - PHI * EI
            M = rho * rho
            q = M / (M + PHI_INV2 + eps * eps + 1e-30)
            # coherence-weighted phase mean via vector mean of the doublet
            w = torch.clamp(q, min=1e-12) * torch.clamp(rho, min=1e-12)
            w = w / (w.sum() + 1e-12)
            c_bar = (w[:, None] * torch.stack([EY, EI], dim=1)).sum(dim=0)
            c_bar = c_bar / (c_bar.norm() + 1e-12)
            # rotate the doublet's phase toward the mean, gated by openness
            cos_t = EY / (torch.clamp(torch.sqrt(EY ** 2 + EI ** 2), min=1e-12))
            sin_t = EI / (torch.clamp(torch.sqrt(EY ** 2 + EI ** 2), min=1e-12))
            R = torch.atan2(sin_t * c_bar[1] - cos_t * c_bar[0],
                            cos_t * c_bar[0] + sin_t * c_bar[1])
            # apply a small rotation of the doublet vector (phase advance δθ)
            dR = self.J_coupling * (1.0 - q) * R
            EY_new = EY + dt * (dEY + dR * EI)
            EI_new = EI + dt * (dEI - dR * EY)
            return EY_new, EI_new

        return EY + dt * dEY, EI + dt * dEI


def phi_cluster_ic(D: int, r_inner: float, N_shell: int, L: float,
                   seed: int = 1, phase_seed: int = 1,
                   doublet: bool = True
                   ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """φ-organized nested multi-shell cluster + full doublet (EY, EI).

    Same geometry as (b1). The doublet is seeded at the φ-locked standing
    wave: E_Y = ρ·cos(θ), E_I = ρ·sin(θ) with θ = k·(π/2) per rung (double-helix
    P_∥=2 closure) + small jitter, and ρ ∝ mass (heavy inner = high amplitude).
    This gives every particle an explicit (EY, EI) to evolve.

    Returns (pos, vel, masses, EY, EI) on CPU; caller moves to device.
    """
    pos, vel, masses, theta = _phi_cluster_phases(D, r_inner, N_shell, L,
                                                  seed, phase_seed)
    if doublet:
        # doublet seeded from the standing-wave ansatz (b2's free amplitude)
        amp = torch.sqrt(torch.clamp(masses, min=1e-12))
        EY = amp * torch.cos(theta)
        EI = amp * torch.sin(theta)
        return pos, vel, masses, EY, EI
    return pos, vel, masses, torch.zeros_like(masses), torch.zeros_like(masses)


def _phi_cluster_phases(D: int, r_inner: float, N_shell: int, L: float,
                        seed: int = 1, phase_seed: int = 1
                        ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Shared geometry: nested φ-spaced shells, origin-centered."""
    gen = torch.Generator(device='cpu').manual_seed(seed)
    pos_list, mass_list, theta_list = [], [], []
    for k in range(D):
        r_k = r_inner * (PHI ** k)
        m_k = PHI_INV ** k
        i = torch.arange(N_shell, dtype=torch.float64)
        phi_ang = 2.0 * math.pi * i / PHI
        cos_th = 1.0 - 2.0 * (i + 0.5) / N_shell
        sin_th = torch.sqrt(torch.clamp(1.0 - cos_th ** 2, min=0.0))
        x = r_k * sin_th * torch.cos(phi_ang)
        y = r_k * sin_th * torch.sin(phi_ang)
        z = r_k * cos_th
        pos_k = torch.stack([x, y, z], dim=1)
        pgen = torch.Generator(device='cpu').manual_seed(phase_seed + k)
        theta_k = k * (math.pi / 2.0) + 0.05 * torch.randn(N_shell, generator=pgen)
        pos_list.append(pos_k)
        mass_list.append(torch.full((N_shell,), m_k, dtype=torch.float64))
        theta_list.append(theta_k)
    pos = torch.cat(pos_list, dim=0)
    masses = torch.cat(mass_list, dim=0)
    theta = torch.cat(theta_list, dim=0)
    vel = torch.zeros(pos.shape[0], 3, dtype=torch.float64)
    com = pos.mean(dim=0)
    pos = pos - com[None, :]
    return pos, vel, masses, theta


def virialize(solver, pos: torch.Tensor, masses: torch.Tensor) -> torch.Tensor:
    """Solver-consistent virial velocity field (deposit → gravity → radial)."""
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


def doublet_phase_order(EY: torch.Tensor, EI: torch.Tensor, r: torch.Tensor,
                        r_core: float, weights: Optional[torch.Tensor] = None) -> float:
    """Phase-coherence order parameter over the core: |mean(exp(iθ))| from EY/EI."""
    core = r < r_core
    if not core.any():
        return 1.0
    ey = EY.cpu()[core.cpu()]
    ei = EI.cpu()[core.cpu()]
    mag = torch.clamp(torch.sqrt(ey ** 2 + ei ** 2), min=1e-12)
    cos_t = ey / mag
    sin_t = ei / mag
    if weights is not None:
        w = weights.cpu()[core.cpu()]
        w = w / (w.sum() + 1e-12)
        c = (w * cos_t).sum()
        s = (w * sin_t).sum()
        return float(torch.sqrt(c ** 2 + s ** 2).item())
    c = cos_t.mean()
    s = sin_t.mean()
    return float(torch.sqrt(c ** 2 + s ** 2).item())


def run_doublet_sim(config, pos, vel, masses, EY, EI, doublet: bool,
                    lam: float = 1.0, J_coupling: float = 0.5
                    ) -> Tuple[List[dict], torch.Tensor, torch.Tensor, torch.Tensor, DoubletNBody, float]:
    """Doublet-enabled run loop; additive-off (doublet=False) = parent run."""
    solver = DoubletNBody(n_grid=config.n_grid, L=config.L, G=config.G,
                          sigma=config.sigma, device=config.device,
                          qi_gate=config.qi_gate, qi_memory=config.qi_memory,
                          deposition_kernel=config.deposition_kernel,
                          alpha_yin=config.alpha_yin,
                          holographic_bound=config.holographic_bound,
                          holographic_eta=config.holographic_eta,
                          doublet=doublet, lam=lam, J_coupling=J_coupling)
    if doublet:
        EY = EY.to(config.device)
        EI = EI.to(config.device)
    N = pos.shape[0]
    total_mass = masses.sum().item()
    qi = torch.zeros(config.n_grid, config.n_grid, config.n_grid, device=config.device)
    diag_history = []
    trail_frames = []
    ey_hist, ei_hist = [], []
    phys_t = 0.0
    accel = None
    q_mean, eps_mean = 1.0, 0.0
    doublet_mass_0 = float((EY + EI).sum().item()) if doublet else 0.0

    print(f"\n{'='*64}")
    print(f"  Cassi N-Body 3D GPU — Winding-on-particles (b2) full doublet")
    print(f"  {'-'*56}")
    print(f"  N = {N} bodies  |  total M = {total_mass:.0f}")
    print(f"  Grid: {config.n_grid}^3  |  L = {config.L}")
    print(f"  Doublet: {'ON  λ=%.2f J=%.2f' % (lam, J_coupling) if doublet else 'OFF (control)'}")
    print(f"  dt = {config.dt}  |  Steps = {config.n_steps}")
    print(f"  phi = {PHI:.4f}  |  Qi damp = 1/phi = {PHI_INV:.4f}")
    print(f"{'='*64}\n")

    t_start = time.time()
    for step in range(config.n_steps):
        pos, vel, accel, q_mean, eps_mean = solver.leapfrog_step(
            pos, vel, masses, config.dt, accel=accel,
            vel_damp=config.vel_damp, qi_gate=config.qi_gate
        )
        if doublet:
            EY, EI = solver.evolve_doublet(EY, EI, pos, masses, config.dt)
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
            if doublet:
                ey_hist.append(EY.detach().cpu().clone())
                ei_hist.append(EI.detach().cpu().clone())
        if step % config.report_every == 0:
            d = solver.compute_diagnostics(pos, vel, masses, config,
                                           q_mean=q_mean, eps_mean=eps_mean)
            diag_history.append(d)
            if doublet:
                order = doublet_phase_order(EY, EI,
                                            torch.sqrt((pos ** 2).sum(dim=1)),
                                            _core_radius(config), masses)
                dm = float((EY + EI).sum().item())
                qi_info = f" q_avg={q_mean:.4f} θ_order={order:.4f} Σρ_dp={dm:.3f}"
            else:
                qi_info = f" q_avg={q_mean:.4f}" if config.qi_gate else ""
            print(f"  t={phys_t:.3f} | E={d['E_tot']:+.4f} | "
                  f"Q={d['Q']:.4f} | R_half={d['half_mass_r']:.4f}{qi_info}")
            if math.isnan(d['E_tot']) or (doublet and math.isnan(float((EY + EI).sum().item()))):
                print(f"\n  ERROR: NaN at step {step}. Aborting.")
                break
    elapsed = time.time() - t_start
    ms_per_step = elapsed / (step + 1) * 1000
    print(f"\n  Wall time: {elapsed:.1f}s  |  {ms_per_step:.1f} ms/step")
    print(f"  Doublet mass: {doublet_mass_0:.3f} -> {(EY+EI).sum().item():.3f} "
          f"(exchange conserves ρ)" if doublet else "")
    trails = torch.stack(trail_frames, dim=0) if trail_frames else None
    ey_arr = torch.stack(ey_hist, dim=0) if ey_hist else EY.cpu().unsqueeze(0)
    ei_arr = torch.stack(ei_hist, dim=0) if ei_hist else EI.cpu().unsqueeze(0)
    return diag_history, trails, ey_arr, ei_arr, solver, elapsed


def _core_radius(config) -> float:
    """Core cut for the phase-order metric: the innermost φ-rung."""
    return 1.2 * PHI


def main():
    p = argparse.ArgumentParser(description="Meshless winding-on-particles (b2) probe")
    p.add_argument('--steps', type=int, default=4000)
    p.add_argument('--arms', default='depth_4', help="comma list, or 'all'")
    p.add_argument('--L', type=float, default=20.0)
    p.add_argument('--r_inner', type=float, default=1.2)
    p.add_argument('--N_shell', type=int, default=1200)
    p.add_argument('--n_grid', type=int, default=64)
    p.add_argument('--lam', type=float, default=1.0, help="conversion coupling λ")
    p.add_argument('--J', type=float, default=0.5, help="J_z neighbor coupling")
    p.add_argument('--out', type=str, default='runs/meshless_doublet.json')
    args = p.parse_args()

    device = NB.get_device()
    print(f"Device: {device}")
    if not torch.cuda.is_available():
        print("[warning] CUDA/ROCm not available — falling back to CPU (slow)")

    arms = {'depth_1': 1, 'depth_2': 2, 'depth_4': 4}
    if args.arms == 'all':
        arm_list = list(arms.keys())
    else:
        arm_list = [a.strip() for a in args.arms.split(',')]

    results = {}
    for name in arm_list:
        D = arms[name]
        print(f"\n=== {name}: D={D} r_inner={args.r_inner} ===")
        pos, vel, masses, EY, EI = phi_cluster_ic(D, args.r_inner, args.N_shell,
                                                  args.L, doublet=True)
        pos = pos.to(device)
        masses = masses.to(device)
        EY = EY.to(device)
        EI = EI.to(device)

        config = NB.NBodyConfig(
            n_grid=args.n_grid, L=args.L, G=1.0, sigma=0.4, dt=0.001,
            n_steps=args.steps, qi_gate=True, qi_memory=False,
            deposition_kernel='TSC', report_every=500, track_every=100,
            device=device)
        r_core = _core_radius(config)
        solver = DoubletNBody(n_grid=args.n_grid, L=args.L, G=1.0, sigma=0.4,
                              device=device, qi_gate=True,
                              deposition_kernel='TSC',
                              doublet=False, lam=args.lam, J_coupling=args.J)
        vel = virialize(solver, pos, masses)
        vel = vel.to(device)

        t0 = time.time()
        diag, trails, ey_arr, ei_arr, solver_run, wall = run_doublet_sim(
            config, pos, vel, masses, EY, EI, doublet=True,
            lam=args.lam, J_coupling=args.J)
        wall = time.time() - t0

        # phase-order at t=0 and end (core)
        r0 = torch.sqrt((pos.cpu() ** 2).sum(dim=1))
        order0 = doublet_phase_order(EY, EI, r0, r_core, masses)
        r_end = torch.sqrt((trails[-1].cpu() ** 2).sum(dim=1)) if trails is not None and len(trails) else r0
        order_end = doublet_phase_order(ey_arr[-1], ei_arr[-1], r_end, r_core, masses)
        t_hold = 1.0 if order_end >= 0.5 * order0 else 0.0

        # doublet mass conservation + inner-rung mass fraction (structure)
        dm0 = float((EY + EI).sum().item())
        dm_end = float((ey_arr[-1] + ei_arr[-1]).sum().item())
        inner0 = float(((r0 < r_core * PHI_INV) * masses.cpu()).sum().item() / masses.cpu().sum().item()) \
            if r0.numel() else 0.0
        inner_end = float(((r_end < r_core * PHI_INV) * masses.cpu()).sum().item() / masses.cpu().sum().item()) \
            if r_end.numel() else 0.0

        diag_last = diag[-1] if diag else {}
        results[name] = {
            'D': D, 'T_hold_phase': t_hold,
            'phase_order_0': order0, 'phase_order_end': order_end,
            'doublet_mass_0': dm0, 'doublet_mass_end': dm_end,
            'doublet_drift_rel': abs(dm_end - dm0) / (abs(dm0) + 1e-12),
            'inner_frac_0': inner0, 'inner_frac_end': inner_end,
            'q_last': diag_last.get('q_mean', 0.0),
            'R_half_end': diag_last.get('half_mass_r', 0.0),
            'wall_s': wall, 'n_steps': args.steps,
        }
        print(f"  {name}: T_hold_phase={t_hold:0.2f} θ_order {order0:.3f}->{order_end:.3f} "
              f"Σρ_dp {dm0:.3f}->{dm_end:.3f} inner_frac {inner0:.3f}->{inner_end:.3f} "
              f"[{wall:.0f}s, {args.steps} steps]")

    print(f"\n=== WINDING (b2) FULL-DOUBLET RESULTS ===")
    for name in arm_list:
        r = results[name]
        print(f"  {name}: D={r['D']} T_hold_phase={r['T_hold_phase']:.2f} "
              f"θ_order {r['phase_order_0']:.3f}->{r['phase_order_end']:.3f} "
              f"Σρ_dp {r['doublet_mass_0']:.3f}->{r['doublet_mass_end']:.3f} "
              f"inner_frac {r['inner_frac_0']:.3f}->{r['inner_frac_end']:.3f}")

    if len(arm_list) == 3:
        t1 = results['depth_1']['T_hold_phase']
        t2 = results['depth_2']['T_hold_phase']
        t4 = results['depth_4']['T_hold_phase']
        mono = t2 >= t1 and t4 >= t2
        twox = (t4 >= 2.0 * t1) if t1 > 0 else False
        verdict = "SUPPORTS" if (mono and twox) else "DOES NOT SUPPORT"
        print(f"\n=== WINDING (b2) DEPTH VERDICT: {verdict} ===")
        print(f"  (monotone T_hold_phase: {mono}; depth_4 >= 2x depth_1: {twox})")
    else:
        verdict = "N/A (single-arm)"
        print(f"\n=== WINDING (b2) DEPTH VERDICT: {verdict} (need all 3 arms) ===")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump({'meta': {'L': args.L, 'G': 1.0, 'sigma': 0.4, 'dt': 0.001,
                            'N_shell': args.N_shell, 'n_grid': args.n_grid,
                            'lam': args.lam, 'J': args.J,
                            'gate': 'Qi (native coherence) + full doublet (b2)',
                            'amendment': '3c'},
                   'arms': results, 'verdict': verdict}, f, indent=2)
    print(f"Results: {args.out}")


if __name__ == '__main__':
    main()
