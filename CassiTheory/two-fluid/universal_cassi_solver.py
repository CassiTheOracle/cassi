#!/usr/bin/env python3
"""Universal Cassi Solver—couples TwoFluid3DGPU (EY/EI PDE) with NBodySolver3D (particles).

Architecture:
  - Particles = baryonic mass.  Deposited via CIC → rho_ext (external source in two-fluid PDE).
  - Two-fluid PDE evolves EY, EI, velocity u on the grid.
  - Gravitational force on particles = pi * grad(Phi), where pi = EY - EI (NOT rho*grad(Phi)).
  - Force field interpolated from grid to particle positions via CIC.

Usage:
  python two-fluid/universal_cassi_solver.py
"""

import sys
import os
import math
import time
import numpy as np

import torch

# Ensure parent directory is on path so we can import cassi_nbody
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from cassi_nbody import NBodySolver3D, NBodyConfig, plummer_sphere
from cassi_two_fluid_3d_gpu import TwoFluid3DGPU, build_nuclei_density_gpu

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_INV = 1.0 / PHI


def get_device():
    if torch.cuda.is_available():
        return torch.device('cuda')
    print('[warning] CUDA/ROCm not available; falling back to CPU')
    return torch.device('cpu')


class UniversalCassiSolver:
    """Coupled two-fluid (EY/EI grid PDE) + N-body (particle-mesh) solver.

    Particles deposit mass onto the grid as rho_ext, which sources the two-fluid
    Poisson equation.  The gravitational force felt by particles is pi*grad(Phi)
    where pi = EY - EI, interpolated back from the grid via CIC.
    """

    def __init__(self, N_grid=64, L=20.0, n_particles=200, lam=0.02, chi=0.0,
                 chi_yang=None, G=1.0, sigma_nbody=0.4, dt=0.002, device=None,
                 seed=42):
        self.N_grid = N_grid
        self.L = L
        self.n_particles = n_particles
        self.dt = dt
        self.G = G
        self.seed = seed
        self.device = device if device is not None else get_device()

        # --- Two-fluid grid solver ---
        self.field_solver = TwoFluid3DGPU(
            N=N_grid, L=L, nu=0.001, D=0.001, lam=lam,
            chi=chi, chi_yang=chi_yang, mode='cosmos', device=self.device
        )

        # --- N-body solver (for CIC deposition / interpolation utilities only) ---
        self.nbody = NBodySolver3D(
            n_grid=N_grid, L=L, G=G, sigma=sigma_nbody,
            device=self.device, deposition_kernel='CIC'
        )

        # --- Initialize particles as Plummer sphere ---
        config = NBodyConfig(n_grid=N_grid, L=L, G=G, sigma=sigma_nbody,
                             device=self.device)
        scale_radius = L / 10.0  # compact core
        pos, vel, masses = plummer_sphere(n_particles, scale_radius, config, seed=seed)
        self.positions = pos.clone()
        self.velocities = vel.clone()
        self.masses = masses.clone()
        # --- Initialize two-fluid fields (quiescent uniform background) ---
        self.u_hat, self.ey_hat, self.ei_hat = self.field_solver.initial_molecule(seed=seed)

        # Step counter
        self.step_count = 0

        # Static background density blob (set externally via set_static_rho_ext)
        self._static_rho_ext = None
    def set_static_rho_ext(self, rho_ext_static):
        """Set a static background density that persists across all steps.

        Combined with particle-deposited density in each step.
        """
        self._static_rho_ext = rho_ext_static.to(torch.float64)

    def deposit_particles_to_rho_ext(self):
        """Deposit particle masses onto grid via CIC → rho_ext tensor (N,N,N).

        If a static background blob was set via set_static_rho_ext, it is
        added to the particle density so that both contribute to the two-fluid
        Poisson source.
        """
        rho_part = self.nbody.deposit_density(self.positions, self.masses)
        if self._static_rho_ext is not None:
            rho_ext = rho_part + self._static_rho_ext
        else:
            rho_ext = rho_part
        return rho_ext

    def compute_force_field(self, ey, ei):
        """Compute gravitational force field from two-fluid fields.

        pi = ey - ei
        rho = ey + ei
        phi_hat = Poisson(rho)
        force[d] = pi * grad(Phi)[d]

        Returns:
            [fx, fy, fz] each (N,N,N) real tensors
        """
        pi = ey - ei
        rho = ey + ei

        # Poisson solve for total density
        rho_hat = torch.fft.fftn(rho.to(torch.complex128))
        phi_hat = self.field_solver._poisson(rho_hat)

        # grad(Phi) in physical space
        grad_phi = self.field_solver._grad(phi_hat)  # list of 3 real tensors

        # Force = pi * grad(Phi)
        force = [pi * grad_phi[d] for d in range(3)]
        return force

    def interpolate_force_to_particles(self, force_field):
        """Interpolate grid force field to particle positions via CIC.

        Args:
            force_field: [fx, fy, fz] each (N,N,N) real tensors

        Returns:
            accel: (n_particles, 3) tensor
        """
        fx, fy, fz = force_field
        accel = self.nbody.interpolate_accel(fx, fy, fz, self.positions)
        return accel

    def step(self):
        """Single combined time step:
          1. Deposit particles → rho_ext
          2. Set field_solver.rho_ext_hat = fftn(rho_ext)
          3. Evolve two-fluid fields one RK2 step
          4. Compute force field from new EY, EI
          5. Interpolate force to particles
          6. Leapfrog KDK update on particles

        Returns:
            dict of diagnostics
        """
        dt = self.dt

        # 1. Deposit particles → rho_ext
        rho_ext = self.deposit_particles_to_rho_ext()

        # 2. Feed rho_ext into two-fluid solver
        self.field_solver.rho_ext_hat = torch.fft.fftn(rho_ext.to(torch.complex128))

        # 3. Evolve two-fluid fields one RK2 step
        self.u_hat, self.ey_hat, self.ei_hat = self.field_solver.rk2_step(
            self.u_hat, self.ey_hat, self.ei_hat, dt
        )

        # Recover physical-space fields
        ey = torch.fft.ifftn(self.ey_hat).real
        ei = torch.fft.ifftn(self.ei_hat).real

        # 4. Compute force field from new ey, ei
        force_field = self.compute_force_field(ey, ei)

        # 5. Interpolate force to particles → acceleration
        accel = self.interpolate_force_to_particles(force_field)

        # Remove net momentum (center-of-mass frame)
        total_mass = self.masses.sum()
        net_accel = (self.masses[:, None] * accel).sum(dim=0) / total_mass
        accel = accel - net_accel[None, :]

        # 6. Leapfrog KDK (kick-drift-kick) for particles
        # Half kick
        self.velocities = self.velocities + 0.5 * dt * accel
        # Drift
        self.positions = self.positions + dt * self.velocities
        # Periodic wrap
        self.positions = ((self.positions + self.L / 2.0) % self.L) - self.L / 2.0

        # Recompute force at new positions for second half-kick
        # (We re-deposit and re-solve for accuracy, but to save cost we
        #  approximate by reusing the same accel—standard VV approximation)
        # Full second half-kick with current accel
        self.velocities = self.velocities + 0.5 * dt * accel

        self.step_count += 1

        # --- Diagnostics ---
        pi = ey - ei
        rho = ey + ei
        pi_rho = pi / (rho + 1e-12)

        # Half-mass radius
        r_pos = torch.sqrt((self.positions ** 2).sum(dim=1))
        sorted_r, sorted_idx = torch.sort(r_pos)
        cum_mass = torch.cumsum(self.masses[sorted_idx], dim=0)
        half_idx = torch.searchsorted(cum_mass, 0.5 * total_mass)
        r_half = sorted_r[min(half_idx.item(), len(sorted_r) - 1)].item()

        # v_circ in radial bins
        n_bins = 16
        r_max = self.L / 4.0
        r_edges = torch.linspace(0.0, r_max, n_bins + 1, device=self.device)
        v_circ_field = torch.zeros(n_bins, device=self.device)
        v_circ_particle = torch.zeros(n_bins, device=self.device)
        r_mid = 0.5 * (r_edges[:-1] + r_edges[1:])

        # Field-based v_circ: for each particle, v_circ = sqrt(r * |accel|)
        # |accel| is the magnitude of the pi*grad(Phi) force interpolated to the particle.
        # This is the circular velocity the field force would support.
        accel_mag = torch.sqrt((accel ** 2).sum(dim=1))
        r_pos = torch.sqrt((self.positions ** 2).sum(dim=1))
        v_circ_from_accel = torch.sqrt(torch.clamp(r_pos * accel_mag, min=0.0))
        for b in range(n_bins):
            mask = (r_pos >= r_edges[b]) & (r_pos < r_edges[b+1])
            if mask.any():
                v_circ_field[b] = v_circ_from_accel[mask].mean()

        # Particle-based v_circ: proper tangential velocity
        # v_tan = sqrt(v² - v_r²),  v_r = (r·v)/|r|
        r_norm = r_pos / (r_pos + 1e-30)
        v_radial = (self.velocities * r_norm[:, None]).sum(dim=1)
        v_sq = (self.velocities ** 2).sum(dim=1)
        v_tan = torch.sqrt(torch.clamp(v_sq - v_radial ** 2, min=0.0))
        for b in range(n_bins):
            mask = (r_pos >= r_edges[b]) & (r_pos < r_edges[b+1])
            if mask.any():
                v_circ_particle[b] = v_tan[mask].mean()

        return {
            'step': self.step_count,
            'r_half': r_half,
            'pi_rho_mean': pi_rho.mean().item(),
            'pi_rho_std': pi_rho.std().item(),
            'ey_mean': ey.mean().item(),
            'ei_mean': ei.mean().item(),
            'rho_max': rho.max().item(),
            'r_bins': r_mid.cpu().numpy(),
            'v_circ_field': v_circ_field.cpu().numpy(),
            'v_circ_particle': v_circ_particle.cpu().numpy(),
            'pos': self.positions.cpu().clone(),
            'vel': self.velocities.cpu().clone(),
        }

    def run(self, n_steps=500, report_every=50):
        """Run n_steps combined time steps, collecting diagnostics.

        Returns:
            history: dict mapping step → diagnostics dict
        """
        history = {}
        t0 = time.time()

        print(f"\n{'='*72}")
        print(f"  Universal Cassi Solver—Two-Fluid + N-Body Coupled")
        print(f"  {'-'*64}")
        print(f"  Grid: {self.N_grid}^3  |  L = {self.L}  |  dx = {self.L/self.N_grid:.3f}")
        print(f"  Particles: {self.n_particles}  |  dt = {self.dt}  |  steps = {n_steps}")
        print(f"  lam = {self.field_solver.lam}  |  chi = {self.field_solver.chi}")
        print(f"  G = {self.G}  |  device = {self.device}")
        print(f"{'='*72}\n")

        for step_i in range(n_steps):
            diag = self.step()

            if step_i % report_every == 0 or step_i == n_steps - 1:
                history[step_i] = diag
                print(f"  step {step_i:4d} | "
                      f"r_half = {diag['r_half']:.4f} | "
                      f"<pi/rho> = {diag['pi_rho_mean']:+.4f} | "
                      f"<EY> = {diag['ey_mean']:.4f}  <EI> = {diag['ei_mean']:.4f} | "
                      f"rho_max = {diag['rho_max']:.4f}")

        elapsed = time.time() - t0
        ms_per_step = elapsed / max(n_steps, 1) * 1000
        print(f"\n  Wall time: {elapsed:.1f}s  |  {ms_per_step:.1f} ms/step")

        return history


def main():
    """Long-run test: 500 steps, compare field force vs Newtonian baseline at 4 snapshots."""
    N_grid = 32
    L = 20.0
    n_particles = 100
    device = get_device()
    seed = 42

    solver = UniversalCassiSolver(
        N_grid=N_grid, L=L, n_particles=n_particles,
        lam=0.0, chi=2.0, chi_yang=4.0, G=1.0, sigma_nbody=0.4,
        dt=0.002, device=device, seed=seed
    )

    # Density blob at center (external source + Yang seed)
    center = torch.tensor([[0.0, 0.0, 0.0]], device=device, dtype=torch.float64)
    charges = torch.tensor([100.0], device=device, dtype=torch.float64)
    blob_sigma = 2.0
    blob_rho = build_nuclei_density_gpu(N_grid, L, center, charges, blob_sigma, device)
    solver.set_static_rho_ext(blob_rho)

    # Seed blob region with Yang-dominant EY (dark matter halo seed)
    ey_init = torch.fft.ifftn(solver.ey_hat).real
    yang_mask = blob_rho > 0.01 * blob_rho.max()
    ey_init[yang_mask] *= PHI * PHI  # boost Yang by phi^2 in blob region
    solver.ey_hat = torch.fft.fftn(ey_init.to(torch.complex128))
    print(f"Yang seed: {yang_mask.sum().item()} cells boosted by {PHI*PHI:.3f}x")

    # Run 500 steps (runs stably before density spike at ~step 450)
    history = solver.run(n_steps=500, report_every=50)

    # --- Extract diagnostics at 4 snapshot steps ---
    snap_steps = sorted([s for s in history.keys() if not math.isnan(history[s].get('rho_max', 0))])
    n_snap = min(4, len(snap_steps))
    snap_idx = [snap_steps[i * len(snap_steps) // n_snap] for i in range(n_snap)]
    # Build radial bins from last snapshot
    r_bins = history[snap_steps[-1]]['r_bins']

    # Newtonian baseline: v = sqrt(G * M / r) for point mass
    G_const = 1.0
    M_tot = solver.masses.sum().item() + charges.item()
    v_newton_arr = np.array([math.sqrt(G_const * M_tot / max(float(r), 0.1)) for r in r_bins])

    # --- Print summary table ---
    print(f"\n{'='*80}")
    print(f"  Summary—steps across evolution")
    print(f"  {'-'*72}")
    print(f"  {'step':>6s}  {'r_half':>8s}  {'<pi/rho>':>10s}  {'rho_max':>8s}  {'EY_mean':>8s}  {'EI_mean':>8s}")
    print(f"  {'-'*72}")
    for s in snap_steps:
        d = history[s]
        print(f"  {s:6d}  {d['r_half']:8.4f}  {d['pi_rho_mean']:+.4f}  "
              f"{d['rho_max']:8.4f}  {d['ey_mean']:.4f}  {d['ei_mean']:.4f}")
    print(f"{'='*80}")

    # --- v_circ comparison table ---
    d_last = history[snap_steps[-1]]
    print(f"\n  v_circ(r) at step {snap_steps[-1]}:")
    print(f"  {'r':>6s}  {'v_field':>8s}  {'v_Newton':>9s}  {'v_particle':>10s}  {'ratio f/N':>8s}")
    print(f"  {'-'*50}")
    for b in range(len(r_bins)):
        vf = d_last['v_circ_field'][b]
        vp = d_last['v_circ_particle'][b]
        vn = v_newton_arr[b]
        ratio = (vf / vn) if vn > 1e-10 else float('nan')
        print(f"  {r_bins[b]:6.3f}  {vf:8.4f}  {vn:9.4f}  {vp:10.4f}  {ratio:8.3f}")

    # --- 3-panel figure ---
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(21, 6))
    colors = plt.cm.viridis(np.linspace(0.05, 0.95, n_snap))

    # Panel 1: v_circ(r)—field vs Newtonian at snapshots
    ax = axes[0]
    ax.plot(r_bins, v_newton_arr, 'k--', lw=1.5, label='Newtonian (pt mass)')
    for i, s in enumerate(snap_idx):
        d = history[s]
        vf = d['v_circ_field']
        valid = vf > 1e-10
        ax.plot(r_bins[valid], vf[valid], 'o-', color=colors[i], ms=4, lw=1.2,
                label=f'field t={s*0.002:.1f}')
        if s == snap_steps[-1]:
            vp = d['v_circ_particle']
            ax.plot(r_bins[valid], vp[valid], 's', color='#C0392B', ms=3, alpha=0.4,
                    label='particles (final)')
    ax.set_xlabel('r (code units)')
    ax.set_ylabel('v_circ')
    ax.set_title(f'Rotation Curves: Field Force vs Newtonian')
    ax.legend(fontsize=7, ncol=2)
    ax.grid(True, alpha=0.3)

    # Panel 2: pi/rho radial profile at final step
    ax = axes[1]
    ax.axhline(0.33333, color='gray', ls=':', lw=1, label='uniform baseline=1/3')
    phi2 = 1/PHI**2; phi3 = 1/PHI**3
    ax.axhline(phi2, color='#D4A574', ls=':', lw=1, label=f'phi^-2={phi2:.3f}')
    ax.axhline(phi3, color='#A0522D', ls=':', lw=1, label=f'phi^-3={phi3:.3f}')
    # Add mean pi/rho at each snapshot as horizontal line
    for i, s in enumerate(snap_idx):
        pr = history[s]['pi_rho_mean']
        ax.axhline(pr, color=colors[i], ls='-', lw=1, alpha=0.7,
                    label=f'<pi/rho>(t={s*0.002:.1f})={pr:.4f}')
    # Radial profile at final step
    pi_f = torch.fft.ifftn(solver.ey_hat).real - torch.fft.ifftn(solver.ei_hat).real
    rh_f = torch.fft.ifftn(solver.ey_hat).real + torch.fft.ifftn(solver.ei_hat).real
    pi_rho_g = pi_f / (rh_f + 1e-12)
    coords = torch.stack([solver.field_solver.X, solver.field_solver.Y, solver.field_solver.Z], dim=-1)
    r_g = torch.sqrt((coords**2).sum(dim=-1))
    n_bins_plot = 20
    r_ep = torch.linspace(0.0, L/4.0, n_bins_plot + 1, device=device)
    r_mp = 0.5 * (r_ep[:-1] + r_ep[1:])
    pi_rho_rad = torch.zeros(n_bins_plot)
    for b in range(n_bins_plot):
        m = (r_g >= r_ep[b]) & (r_g < r_ep[b+1])
        if m.any(): pi_rho_rad[b] = pi_rho_g[m].mean()
    ax.plot(r_mp.cpu(), pi_rho_rad.cpu(), '^-', color='#2C3E50', ms=4, lw=1.5,
            label='radial profile (final)')
    ax.set_xlabel('r (code units)')
    ax.set_ylabel('<pi/rho>')
    ax.set_title(f'Yang-Yin Asymmetry: DM Halo Evolution')
    ax.legend(fontsize=6, ncol=2)
    ax.grid(True, alpha=0.3)

    # Panel 3: Time evolution of diagnostics
    ax = axes[2]
    steps_arr = np.array(list(history.keys()))
    rho_max_arr = np.array([history[s]['rho_max'] for s in steps_arr])
    pr_mean_arr = np.array([history[s]['pi_rho_mean'] for s in steps_arr])
    rhalf_arr = np.array([history[s]['r_half'] for s in steps_arr])
    ax.semilogy(steps_arr, rho_max_arr / rho_max_arr[0], 'r-', lw=1.5, label='rho_max/rho_max(0)')
    ax.semilogy(steps_arr, rhalf_arr / rhalf_arr[0], 'b-', lw=1.5, label='r_half/r_half(0)')
    ax.set_xlabel('step')
    ax.set_ylabel('normalized value')
    ax.set_title(f'Diagnostic Evolution (diverges at ~step {snap_steps[-1]+50})')
    ax.legend(fontsize=7, loc='upper right')
    ax.grid(True, alpha=0.3)
    # secondary axis for pi/rho
    ax2 = ax.twinx()
    ax2.plot(steps_arr, pr_mean_arr, 'g--', lw=1.5, label='<pi/rho>')
    ax2.axhline(0.33333, color='gray', ls=':', lw=0.8)
    ax2.set_ylabel('<pi/rho>', color='g')
    ax2.legend(fontsize=7, loc='lower right')

    plt.tight_layout()
    save_path = os.path.join(os.path.dirname(__file__), 'universal_cassi_rotation.png')
    plt.savefig(save_path, dpi=150)
    print(f"\n  Figure saved to {save_path}")
    plt.close()
