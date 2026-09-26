#!/usr/bin/env python3
"""Signed-component meshless stress test associated with Amendment 3 (b2).

Each particle carries two signed coordinates ``EY`` and ``EI`` initialized as

    EY = A cos(theta),  EI = A sin(theta).

That construction occupies all four quadrants. It therefore lies outside the
canonical real-density domain E_Y >= 0, E_I >= 0 used by the two-fluid PDE.
Applying the canonical conversion formula to these coordinates does not make
them canonical densities.

The optional ``J_coupling`` is a global q-weighted vector-mean alignment. It
has no spatial-neighbor kernel, tree walk, gradient current, or canonical
J_z closure. Its rotation preserves EY**2 + EI**2 to first order while
generally changing EY + EI. Consequently, the component sum is not a
conserved mass diagnostic for the combined update.

The depth arms also change particle count, total mass, outer radius, initial
inner-rung fraction, and the seeded dynamical state with ``D``. The executable
runs only the observer-on branch and measures raw origin-centered radii after
periodic wrapping. It records endpoint phase order rather than a sampled hold
time. The frozen b2 discriminator is therefore unscoreable, and this script's
scientific verdict is always INCONCLUSIVE. It remains executable as a
numerical stress test of the signed-coordinate construction.
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
    """NBodySolver3D plus two signed per-particle component coordinates.

    The coordinates undergo the canonical conversion algebra outside its
    nonnegative-density domain, followed by optional global mean-field
    alignment. They are observer variables: gravity, positions, velocities,
    and particle masses remain those of the parent leapfrog.
    """

    def __init__(self, *args, doublet: bool = False, lam: float = 1.0,
                 J_coupling: float = 0.5, **kwargs):
        super().__init__(*args, **kwargs)
        self.doublet = doublet
        self.lam = lam
        self.J_coupling = J_coupling
        self.EY = None
        self.EI = None

    # --- Canonical conversion algebra evaluated on signed coordinates ---
    def doublet_rate(self, EY: torch.Tensor, EI: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Return the equal-and-opposite conversion contribution.

        This substep preserves ``EY + EI`` algebraically. The later alignment
        substep generally changes that sum, and signed inputs remain outside
        the canonical real-density domain.
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
        """Euler step of conversion algebra plus global mean-field alignment."""
        if not self.doublet:
            return EY, EI
        dEY, dEI = self.doublet_rate(EY, EI)

        # Global q-weighted phase alignment over the whole ensemble.
        if self.J_coupling > 0.0:
            rho = EY + EI
            eps = EY - PHI * EI
            M = rho * rho
            q = M / (M + PHI_INV2 + eps * eps + 1e-30)
            w = torch.clamp(q, min=1e-12) * torch.clamp(rho, min=1e-12)
            w = w / (w.sum() + 1e-12)
            c_bar = (w[:, None] * torch.stack([EY, EI], dim=1)).sum(dim=0)
            c_bar = c_bar / (c_bar.norm() + 1e-12)
            magnitude = torch.clamp(torch.sqrt(EY ** 2 + EI ** 2), min=1e-12)
            cos_t = EY / magnitude
            sin_t = EI / magnitude
            # R is the wrapped displacement theta - theta_mean. Applying -R
            # rotates each signed component pair toward the global mean.
            R = torch.atan2(sin_t * c_bar[0] - cos_t * c_bar[1],
                            cos_t * c_bar[0] + sin_t * c_bar[1])
            dR = self.J_coupling * (1.0 - q) * R
            EY_new = EY + dt * (dEY + dR * EI)
            EI_new = EI + dt * (dEI - dR * EY)
            return EY_new, EI_new

        return EY + dt * dEY, EI + dt * dEI


def phi_cluster_ic(D: int, r_inner: float, N_shell: int, L: float,
                   seed: int = 1, phase_seed: int = 1,
                   doublet: bool = True
                   ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Return a φ-spaced cluster with two signed component coordinates.

    The phase seed uses theta = k*pi/2 plus jitter, so the resulting
    ``EY = A*cos(theta)`` and ``EI = A*sin(theta)`` include negative values.
    They can be interpreted as Cartesian amplitude coordinates for this stress
    test; they do not satisfy the canonical nonnegative-density domain.

    Returns ``(pos, vel, masses, EY, EI)`` on CPU.
    """
    pos, vel, masses, theta = _phi_cluster_phases(D, r_inner, N_shell, L,
                                                  seed, phase_seed)
    if doublet:
        # Signed Cartesian amplitude coordinates for the stress test.
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


def inward_radial_velocity_seed(
    solver, pos: torch.Tensor, masses: torch.Tensor
) -> torch.Tensor:
    """Construct an inward radial seed; this is not a virial equilibrium."""
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
    """Signed-coordinate phase order inside the registered open core."""
    core_tol = 1e-9 * max(1.0, r_core)
    core = r < r_core - core_tol
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
                    r_core: float, lam: float = 1.0,
                    J_coupling: float = 0.5
                    ) -> Tuple[List[dict], torch.Tensor, torch.Tensor, torch.Tensor, DoubletNBody, float]:
    """Run the signed-component observer alongside the parent N-body solver."""
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
    trail_frames = [pos.cpu().clone()]
    ey_hist = [EY.detach().cpu().clone()] if doublet else []
    ei_hist = [EI.detach().cpu().clone()] if doublet else []
    phys_t = 0.0
    accel = None
    legacy_density_proxy_mean, density_memory_residual_mean = 1.0, 0.0
    component_sum_0 = float((EY + EI).sum().item()) if doublet else 0.0

    print(f"\n{'='*64}")
    print("  Signed-component meshless stress test (b2 protocol invalid)")
    print(f"  {'-'*56}")
    print(f"  N = {N} bodies  |  particle mass = {total_mass:.0f}")
    print(f"  Grid: {config.n_grid}^3  |  L = {config.L}")
    print(f"  Signed coordinates: {'ON  λ=%.2f J=%.2f' % (lam, J_coupling) if doublet else 'OFF'}")
    print(f"  dt = {config.dt}  |  Steps = {config.n_steps}")
    print(f"  phi = {PHI:.4f}  |  density-memory decay = 1/phi = {PHI_INV:.4f}")
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
        if doublet:
            EY, EI = solver.evolve_doublet(EY, EI, pos, masses, config.dt)
        rho = solver.deposit_density(pos, masses)
        qi = config.qi_damp * qi + (1.0 - config.qi_damp) * rho
        if config.qi_gate:
            solver.qi_field = qi
            if step > 0:
                sigma_eff = config.sigma * (1.0
                    + PHI_INV * (1.0 - legacy_density_proxy_mean)
                    + config.qi_gamma * density_memory_residual_mean)
                sigma_eff = max(sigma_eff, config.sigma * 0.5)
                if abs(sigma_eff - solver.sigma) > 0.01 * config.sigma:
                    solver.set_softening(sigma_eff)
        phys_t += config.dt
        if config.track_every and (step + 1) % config.track_every == 0:
            trail_frames.append(pos.cpu().clone())
            if doublet:
                ey_hist.append(EY.detach().cpu().clone())
                ei_hist.append(EI.detach().cpu().clone())
        if step % config.report_every == 0:
            d = solver.compute_diagnostics(
                pos, vel, masses, config,
                legacy_density_proxy_mean=legacy_density_proxy_mean,
                density_memory_residual_mean=density_memory_residual_mean,
            )
            diag_history.append(d)
            if doublet:
                order = doublet_phase_order(
                    EY, EI, torch.sqrt((pos ** 2).sum(dim=1)),
                    r_core, masses)
                component_sum = float((EY + EI).sum().item())
                proxy_info = (
                    f" legacy_density_proxy_mean={legacy_density_proxy_mean:.4f} "
                    f"phase_order={order:.4f} "
                    f"component_sum={component_sum:.3f}"
                )
            else:
                proxy_info = (
                    f" legacy_density_proxy_mean="
                    f"{legacy_density_proxy_mean:.4f}"
                    if config.qi_gate else ""
                )
            print(f"  t={phys_t:.3f} | parent_E={d['E_tot']:+.4f} | "
                  f"Q={d['Q']:.4f} | R_half={d['half_mass_r']:.4f}{proxy_info}")
            finite_components = (not doublet or
                                 (bool(torch.isfinite(EY).all().item()) and
                                  bool(torch.isfinite(EI).all().item())))
            if math.isnan(d['E_tot']) or not finite_components:
                print(f"\n  ERROR: non-finite state at step {step}. Aborting.")
                break
    if not trail_frames or not torch.equal(trail_frames[-1], pos.cpu()):
        trail_frames.append(pos.cpu().clone())
        if doublet:
            ey_hist.append(EY.detach().cpu().clone())
            ei_hist.append(EI.detach().cpu().clone())
    elapsed = time.time() - t_start
    ms_per_step = elapsed / max(config.n_steps, 1) * 1000
    print(f"\n  Wall time: {elapsed:.1f}s  |  {ms_per_step:.1f} ms/step")
    if doublet:
        print(f"  Signed-component sum: {component_sum_0:.3f} -> "
              f"{(EY + EI).sum().item():.3f}")
    # Expose the final sampled legacy diagnostic for the arm summary.
    solver.legacy_density_proxy_mean = legacy_density_proxy_mean
    solver.density_memory_residual_mean = density_memory_residual_mean
    trails = torch.stack(trail_frames, dim=0)
    ey_arr = torch.stack(ey_hist, dim=0) if ey_hist else EY.cpu().unsqueeze(0)
    ei_arr = torch.stack(ei_hist, dim=0) if ei_hist else EI.cpu().unsqueeze(0)
    return diag_history, trails, ey_arr, ei_arr, solver, elapsed


def _core_radius(r_inner: float) -> float:
    """Registered open-core cutoff at the second shell radius."""
    return r_inner * PHI


def main():
    p = argparse.ArgumentParser(
        description="Signed-component meshless stress test (invalid b2 protocol)")
    p.add_argument('--steps', type=int, default=4000)
    p.add_argument('--arms', default='depth_4', help="comma list, or 'all'")
    p.add_argument('--L', type=float, default=20.0)
    p.add_argument('--r_inner', type=float, default=1.2)
    p.add_argument('--N_shell', type=int, default=1200)
    p.add_argument('--n_grid', type=int, default=64)
    p.add_argument('--lam', type=float, default=1.0, help="conversion-algebra coupling")
    p.add_argument('--J', type=float, default=0.5,
                   help="global signed-component alignment strength")
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
        r_core = _core_radius(args.r_inner)
        solver = DoubletNBody(n_grid=args.n_grid, L=args.L, G=1.0, sigma=0.4,
                              device=device, qi_gate=True,
                              deposition_kernel='TSC',
                              doublet=False, lam=args.lam, J_coupling=args.J)
        vel = inward_radial_velocity_seed(solver, pos, masses)
        vel = vel.to(device)

        t0 = time.time()
        diag, trails, ey_arr, ei_arr, solver_run, wall = run_doublet_sim(
            config, pos, vel, masses, EY, EI, doublet=True, r_core=r_core,
            lam=args.lam, J_coupling=args.J)
        wall = time.time() - t0

        # Endpoint-only signed-component diagnostics. They do not resolve the
        # frozen hold-time discriminator.
        r0 = torch.sqrt((pos.cpu() ** 2).sum(dim=1))
        order0 = doublet_phase_order(EY, EI, r0, r_core, masses)
        r_end = torch.sqrt((trails[-1].cpu() ** 2).sum(dim=1))
        order_end = doublet_phase_order(
            ey_arr[-1], ei_arr[-1], r_end, r_core, masses)
        endpoint_retained = order_end >= 0.5 * order0

        component_sum_0 = float((EY + EI).sum().item())
        component_sum_end = float((ey_arr[-1] + ei_arr[-1]).sum().item())
        ey_negative_fraction_0 = float((EY < 0.0).double().mean().item())
        ei_negative_fraction_0 = float((EI < 0.0).double().mean().item())
        # Include the innermost shell at r_inner. A tiny relative tolerance
        # removes float64 roundoff at the analytically exact boundary.
        inner_cut = r_core * PHI_INV
        inner_tol = 1e-9 * max(1.0, inner_cut)
        inner0 = float(
            ((r0 <= inner_cut + inner_tol) * masses.cpu()).sum().item()
            / masses.cpu().sum().item()) if r0.numel() else 0.0
        inner_end = float(
            ((r_end <= inner_cut + inner_tol) * masses.cpu()).sum().item()
            / masses.cpu().sum().item()) if r_end.numel() else 0.0

        diag_last = diag[-1] if diag else {}
        total_mass = float(masses.sum().item())
        outer_radius = args.r_inner * PHI ** (D - 1)
        results[name] = {
            'D': D,
            'N': int(masses.numel()),
            'total_mass': total_mass,
            'outer_radius': outer_radius,
            'phase_endpoint_retained': endpoint_retained,
            'phase_order_0': order0,
            'phase_order_end': order_end,
            'component_sum_0': component_sum_0,
            'component_sum_end': component_sum_end,
            'component_sum_drift_rel': (
                abs(component_sum_end - component_sum_0)
                / (abs(component_sum_0) + 1e-12)),
            'ey_negative_fraction_0': ey_negative_fraction_0,
            'ei_negative_fraction_0': ei_negative_fraction_0,
            'inner_particle_mass_fraction_0': inner0,
            'inner_particle_mass_fraction_end': inner_end,
            'legacy_density_proxy_last_sample': getattr(
                solver_run, 'legacy_density_proxy_mean', 0.0),
            'R_half_end': diag_last.get('half_mass_r', 0.0),
            'wall_s': wall,
            'n_steps': args.steps,
        }
        print(f"  {name}: N={masses.numel()} M={total_mass:.1f} "
              f"R_outer={outer_radius:.3f} endpoint_retained={endpoint_retained} "
              f"phase_order {order0:.3f}->{order_end:.3f} "
              f"component_sum {component_sum_0:.3f}->{component_sum_end:.3f} "
              f"negative_fractions(EY,EI)=({ey_negative_fraction_0:.3f},"
              f"{ei_negative_fraction_0:.3f}) "
              f"[{wall:.0f}s, {args.steps} steps]")

    print("\n=== SIGNED-COMPONENT STRESS-TEST RESULTS ===")
    for name in arm_list:
        result = results[name]
        print(f"  {name}: D={result['D']} "
              f"endpoint_retained={result['phase_endpoint_retained']} "
              f"phase_order {result['phase_order_0']:.3f}->"
              f"{result['phase_order_end']:.3f} "
              f"component_sum {result['component_sum_0']:.3f}->"
              f"{result['component_sum_end']:.3f}")

    frozen_metric_branch = "UNSCOREABLE (protocol invalid)"
    verdict = "INCONCLUSIVE"
    print(f"\n=== FROZEN METRIC BRANCH: {frozen_metric_branch} ===")
    print("=== SCIENTIFIC VERDICT: INCONCLUSIVE ===")
    print("  protocol validity: FAIL (signed density-domain violation; "
          "global imposed alignment; endpoint-only hold metric; no executed "
          "control; raw periodic-box radii; depth changes N, total mass, "
          "outer radius, and initial inner fraction)")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump({
            'meta': {
                'L': args.L, 'G': 1.0, 'sigma': 0.4, 'dt': 0.001,
                'N_shell': args.N_shell, 'n_grid': args.n_grid,
                'position_seed': 1, 'phase_seed': 1,
                'lam': args.lam, 'J': args.J,
                'model': 'signed components + global mean-field alignment',
                'amendment': '3c',
            },
            'protocol_validity': 'FAIL',
            'frozen_metric_branch': frozen_metric_branch,
            'invalidity_reasons': [
                'signed coordinates violate canonical nonnegative-density domain',
                'alignment is global rather than spatial-neighbor coupling',
                'endpoint retention does not measure T_hold_phase',
                'no executed observer-off trajectory control',
                'inward radial velocity seed is not a virial equilibrium',
                'raw radii do not unwrap the periodic trajectory',
                'depth changes particle count, total mass, outer radius, and '
                'initial inner-rung fraction',
                'fixed particle-mass conservation does not test the observer state',
            ],
            'arms': results,
            'verdict': verdict,
        }, f, indent=2)
    print(f"Results: {args.out}")


if __name__ == '__main__':
    main()
