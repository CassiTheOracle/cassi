#!/usr/bin/env python3
"""
Cassi GR Bridge: φ-Governed General Relativity Extensions
==========================================================

Pillar 2: Post-Newtonian corrections and linearized GR with φ-governed
G_eff(q) coupling to the Cassi two-fluid framework.

Phase A: Post-Newtonian corrections (~300 lines)
  - Effective potential with 1PN correction
  - Perihelion precession (Mercury-verified)
  - Orbital integration in PN effective potential

Phase B: Linearized GR with FFT solver (~400 lines)
  - Stress-energy tensor construction
  - Metric perturbation solver (□h̄_{μν} = -16πG T_{μν})
  - Gravitational wave strain (TT gauge projection)
  - Schwarzschild radius with φ-modified G_eff

Usage:
    python two-fluid/cassi_gr_bridge.py --test all
    python two-fluid/cassi_gr_bridge.py --test precession
    python two-fluid/cassi_gr_bridge.py --test schwarzschild --q 0.5
    python two-fluid/cassi_gr_bridge.py --test linearized --grid 64
"""

import sys, argparse, time, os
import numpy as np
import torch
sys.path.insert(0, 'two-fluid')
from cassi_bridge_v2 import CassiBridgeV2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

# ─── Universal constants ───────────────────────────────────────────────────
PHI     = (1.0 + np.sqrt(5.0)) / 2.0   # ≈ 1.618034
PHI_INV = 1.0 / PHI                     # ≈ 0.618034
PHI_INV2 = PHI_INV ** 2                 # ≈ 0.381966

G_N = 6.67430e-11         # m^3 kg^-1 s^-2
C   = 299792458.0          # m/s
M_SUN = 1.98847e30         # kg
AU  = 1.495978707e11       # m
ARCSEC_PER_RAD = 206264.80624709636  # arcseconds per radian


# ═══════════════════════════════════════════════════════════════════════════
# GR Bridge
# ═══════════════════════════════════════════════════════════════════════════

class CassGRBridge:
    """GR extensions to the Cassi two-fluid framework.

    Pillar 2: General Relativity with φ-governed G_eff(q) coupling.

    Phase A: Post-Newtonian corrections (~300 lines)
    Phase B: Linearized GR with FFT solver (~400 lines)

    Parameters
    ----------
    grid : int
        Grid points per dimension for FFT operations (Phase B).
    L : float
        Physical box size in code units.
    device : str or torch.device
        Compute device.
    q : float
        Default Qi coherence parameter for G_eff calculations.
    """
    def __init__(self, grid=64, L=20.0, device=None, q=0.5):
        # Grid
        self.grid = grid
        self.L = L
        self.dim = 3
        self.shape = (grid, grid, grid)
        self.dx = L / grid
        self.dV = self.dx ** 3
        self.N_cells = grid ** 3

        # Default Qi coherence
        self.q = q

        # Device
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = device

        # ── Fourier grid (Phase B) ──────────────────────────────────────
        k_x = 2.0 * np.pi * torch.fft.fftfreq(grid, d=self.dx, device=self.device)
        k_y = 2.0 * np.pi * torch.fft.fftfreq(grid, d=self.dx, device=self.device)
        k_z = 2.0 * np.pi * torch.fft.fftfreq(grid, d=self.dx, device=self.device)

        kx, ky, kz = torch.meshgrid(k_x, k_y, k_z, indexing='ij')
        k2 = kx**2 + ky**2 + kz**2

        # Safe k² (zero mode = 1 to avoid division by zero)
        k2_safe = k2.clone()
        k2_safe[0, 0, 0] = 1.0

        self.kx = kx
        self.ky = ky
        self.kz = kz
        self.k2 = k2
        self.k2_safe = k2_safe

        # Identity in k-space for TT projector
        self.delta_ij = torch.eye(3, device=self.device)  # 3x3 identity

        # Pre-allocate workspaces
        self._tmp_k = torch.zeros(self.shape, dtype=torch.complex64, device=self.device)

        # History
        self.history = {}
        # ── CassiBridgeV2 backend (composition) ─────────────────────────
        self.backend = CassiBridgeV2(grid=grid, L=L, mass=1.0,
                                     phi_gravity=False, device=self.device)

    # ─────────────────────────────────────────────────────────────────────
    # Phase A: Post-Newtonian Corrections
    # ─────────────────────────────────────────────────────────────────────

    def get_geff(self, q=0.0):
        """G_eff(q)/G_N = 1 + (φ⁶−1)·q  [corrected 2026-08-03].

        Max boost φ⁶ ≈ 17.94 at q → 1 (the derived Qi-gravity coupling,
        `foundations/xi-derivation.md`); Newtonian at q = 0. The withdrawn
        approximate coupling 1+(φ−1)q (max boost φ ≈ 1.62) and the earlier
        empirical π/ρ-scaled fit with ξ = 18 are removed.

        Parameters
        ----------
        q : float
            Qi coherence (0 = background, ~0.7 = halo saturation).

        Returns
        -------
        float
            Effective gravitational constant G_eff in m³ kg⁻¹ s⁻².
        """
        xi = PHI ** 6
        return G_N * (1.0 + (xi - 1.0) * q)

    def effective_potential(self, r, M, L, c=C, q=0):
        """Effective radial potential (Newtonian + 1PN GR correction).

        The last term is the 1PN GR correction (perihelion-advancing term).
        Valid for r >> r_s and v << c.

        Parameters
        ----------
        r : float or ndarray
            Radial coordinate in meters.
        M : float
            Central mass in kg.
        L : float
            Specific angular momentum (per unit mass) in m^2/s.
        c : float
            Speed of light in m/s.
        q : float
            Qi coherence for G_eff (default 0 = pure GR).

        Returns
        -------
        V_newton : float or ndarray
            Newtonian effective potential: -G*M/r + L^2/(2*r^2).
        V_gr : float or ndarray
            GR correction term: -(G*M)*L^2/(c^2 * r^3).
        V_total : float or ndarray
            Total effective potential.
        """
        G_eff = self.get_geff(q)
        r = np.asarray(r, dtype=np.float64)

        GMr = G_eff * M / r
        V_newton_grav = -GMr
        V_centrifugal = L**2 / (2.0 * r**2)
        V_newton = V_newton_grav + V_centrifugal
        V_gr = -GMr * L**2 / (c**2 * r**2)
        V_total = V_newton + V_gr

        return V_newton, V_gr, V_total

    def effective_acceleration(self, r, M, L, c=C, q=0):
        """Radial acceleration from 1PN effective potential.

        a_r = -dV_eff/dr = -G*M/r^2 + L^2/r^3 - 3*G*M*L^2/(c^2 * r^4)

        Parameters
        ----------
        r : float or ndarray
            Radial coordinate in meters.
        M : float
            Central mass in kg.
        L : float
            Specific angular momentum in m^2/s.
        c : float
            Speed of light in m/s.
        q : float
            Qi coherence for G_eff (default 0 = pure GR).

        Returns
        -------
        float or ndarray
            Radial acceleration in m/s^2.
        """
        G_eff = self.get_geff(q)
        r = np.asarray(r, dtype=np.float64)

        GM = G_eff * M
        a_newton = -GM / r**2 + L**2 / r**3
        a_gr = -3.0 * GM * L**2 / (c**2 * r**4)
        return a_newton + a_gr

    def perihelion_precession_formula(self, a, e, M, c=C, q=0):
        """GR perihelion precession per orbit.

        Δφ = 6πGM / (a(1-e²)c²)   radians per orbit

        For Mercury (a = 5.791e10 m, e = 0.2056):
            Δφ ≈ 5.02e-7 rad/orbit ≈ 0.1038 arcsec/orbit
            × 415 orbits/century ≈ 43 arcsec/century

        Parameters
        ----------
        a : float
            Semi-major axis in meters.
        e : float
            Orbital eccentricity (0 ≤ e < 1).
        M : float
            Central mass in kg.
        c : float
            Speed of light in m/s.
        q : float
            Qi coherence for G_eff (default 0 = pure GR).

        Returns
        -------
        delta_phi_rad : float
            Precession per orbit in radians.
        delta_phi_arcsec : float
            Precession per orbit in arcseconds.
        """
        G_eff = self.get_geff(q)
        denom = a * (1.0 - e**2) * c**2
        delta_phi_rad = 6.0 * np.pi * G_eff * M / denom
        delta_phi_arcsec = delta_phi_rad * ARCSEC_PER_RAD
        return delta_phi_rad, delta_phi_arcsec

    def integrate_orbit(self, r0, v0, M, L=None, n_orbits=1.0,
                        steps_per_orbit=10000, c=C, q=0, return_full=False):
        """Integrate orbit in PN effective potential to find precession.

        Uses velocity-Verlet (leapfrog) integration in polar coordinates
        (r, phi) with conserved angular momentum L.

        Parameters
        ----------
        r0 : float
            Initial radius in meters (perihelion for bound orbit).
        v0 : float
            Initial radial velocity in m/s.
        M : float
            Central mass in kg.
        L : float or None
            Specific angular momentum in m^2/s. If None, computed from
            circular orbit at r0.
        n_orbits : float
            Number of orbits to integrate.
        steps_per_orbit : int
            Integration steps per orbit period.
        c : float
            Speed of light in m/s.
        q : float
            Qi coherence for G_eff (default 0 = pure GR).
        return_full : bool
            If True, return full trajectory arrays.

        Returns
        -------
        r_history : ndarray
            Radial coordinate history (only if return_full=True).
        phi_history : ndarray
            Azimuthal angle history (only if return_full=True).
        total_precession : float
            Total perihelion precession in radians over the integration.
        """
        G_eff = self.get_geff(q)
        GM = G_eff * M

        # If no L provided, compute from circular orbit angular momentum
        if L is None:
            L = np.sqrt(GM * r0)

        # Compute specific orbital energy from radial AND tangential velocities
        # v_radial = v0, v_tangential = L / r0
        v_tan = L / r0
        v_sq = v0**2 + v_tan**2
        E = 0.5 * v_sq - GM / r0
        if E >= 0:
            print("Warning: orbit is unbound (E >= 0), using r0 as scale")
            T = 2.0 * np.pi * r0**1.5 / np.sqrt(GM)
        else:
            a_kepler = -GM / (2.0 * E)
            T = 2.0 * np.pi * a_kepler**1.5 / np.sqrt(GM)
        dt = T / steps_per_orbit
        n_steps = int(n_orbits * steps_per_orbit)

        # Initialize
        r = float(r0)
        vr = float(v0)
        phi = 0.0
        r_prev = r
        step_last = n_steps

        # Storage
        if return_full:
            r_hist = np.zeros(n_steps + 1)
            phi_hist = np.zeros(n_steps + 1)
            r_hist[0] = r
            phi_hist[0] = phi

        # Perihelion tracking
        peri_phi_prev = 0.0       # phi at previous perihelion
        peri_count = 0
        precession_angles = []
        total_precession = 0.0

        # Velocity-Verlet integration
        for step in range(n_steps):
            # Save current r for minimum detection
            r_old = r

            # Current acceleration
            a_r = -GM / r**2 + L**2 / r**3 - 3.0 * GM * L**2 / (c**2 * r**4)

            # Half-step velocity
            v_half = vr + 0.5 * dt * a_r

            # Full-step position
            r_new = r + dt * v_half

            # Safety: prevent r <= 0
            if r_new <= 1e-3 * r0:
                print(f"Warning: Orbit crashed at step {step}, r={r_new:.3e}")
                step_last = step
                break

            # New acceleration
            a_r_new = (-GM / r_new**2 + L**2 / r_new**3
                       - 3.0 * GM * L**2 / (c**2 * r_new**4))

            # Full-step velocity
            vr = v_half + 0.5 * dt * a_r_new

            # Azimuthal update
            phi += dt * L * (0.5 / r**2 + 0.5 / r_new**2)

            # Advance position
            r = r_new

            # Detect perihelion: local minimum in r
            # r_old > r and r > r_new means r is a minimum
            # (but we compare r (the updated value = r_new) with r_old and what will be next r)
            # Actually: after advancing, r = r_new. We need:
            #   r_old > r_prev (mass) → r was decreasing
            #   This step: r_old → r, if r_old > r and r < r_next_step, that's a minimum at r
            # But we don't have r_next yet.
            #
            # Better: detect minimum as r_prev > r_old and r_old < r
            # i.e. r decreased from r_prev to r_old, then increased from r_old to r
            # That means r_old is a local minimum.
            if step > 2 and r_prev > r_old and r_old < r:
                peri_count += 1
                # Use interpolated phi at the minimum (r_old is the minimum)
                # The phi at the current step is the accumulated value AFTER the update,
                # so we estimate phi at the minimum as phi - dt*L/r^2 (back a half step)
                # Actually phi was updated with: phi += dt * L * (0.5/r_old^2 + 0.5/r^2)
                # The half-step phi at minimum is approx phi - 0.5*dt*L/r_old^2
                # For precession, we just need phi at consecutive perihelia.
                # Use phi_interp = phi - dt * L / (2 * r_old**2)  (half-step before the current phi)
                phi_at_min = phi - 0.5 * dt * L / r_old**2
                if peri_count > 1:
                    precession = phi_at_min - peri_phi_prev - 2.0 * np.pi
                    precession_angles.append(precession)
                peri_phi_prev = phi_at_min

            # Shift for next step
            r_prev = r_old

            if return_full:
                r_hist[step + 1] = r
                phi_hist[step + 1] = phi

        # Total precession
        if len(precession_angles) > 0:
            total_precession = sum(precession_angles)

        if return_full:
            last = min(step_last, n_steps)
            return r_hist[:last + 1], phi_hist[:last + 1], total_precession
        else:
            return total_precession
    # ─────────────────────────────────────────────────────────────────────

    def build_stress_energy(self, rho, jx, jy, jz, pressure=None):
        """Build T_{μν} from density and current.

        T_00 = ρ              (energy density)
        T_0i = j_i            (momentum density)
        T_ij = ρ*u_i*u_j + p*δ_ij  (stress tensor)

        Velocity inferred as u_i = j_i / ρ (with floor to avoid division
        by zero). Pressure defaults to p = ρ/3 (radiation-like) unless
        explicitly provided.

        Parameters
        ----------
        rho : torch.Tensor
            Energy density field on grid.
        jx, jy, jz : torch.Tensor
            Momentum density components.
        pressure : torch.Tensor or None
            Pressure field (optional). If None, uses ρ/3.

        Returns
        -------
        dict
            T_munu with keys 'T00', 'T0i' (list of 3), 'Tij' (3x3 list).
        """
        # Ensure all tensors are on the right device
        rho = rho.to(device=self.device) if torch.is_tensor(rho) else rho
        jx = jx.to(device=self.device) if torch.is_tensor(jx) else jx
        jy = jy.to(device=self.device) if torch.is_tensor(jy) else jy
        jz = jz.to(device=self.device) if torch.is_tensor(jz) else jz

        # Clamp density to avoid division issues
        rho_safe = torch.clamp(rho, min=1e-30)

        # T_00: energy density
        T00 = rho

        # T_0i: momentum density
        T0i = [jx, jy, jz]

        # Velocity field
        ux = jx / rho_safe
        uy = jy / rho_safe
        uz = jz / rho_safe

        # Pressure
        if pressure is None:
            p = rho / 3.0  # radiation-like equation of state
        else:
            p = pressure.to(device=self.device) if torch.is_tensor(pressure) else pressure

        # T_ij: stress tensor
        Txx = rho * ux * ux + p
        Tyy = rho * uy * uy + p
        Tzz = rho * uz * uz + p
        Txy = rho * ux * uy
        Txz = rho * ux * uz
        Tyz = rho * uy * uz

        Tij = [[Txx, Txy, Txz],
               [Txy, Tyy, Tyz],
               [Txz, Tyz, Tzz]]

        return {'T00': T00, 'T0i': T0i, 'Tij': Tij}

    def _fft_field(self, field):
        """FFT a real field to Fourier space."""
        return torch.fft.fftn(field.to(dtype=torch.float32, device=self.device))

    def _ifft_field(self, field_k):
        """Inverse FFT a Fourier-space field to real space."""
        return torch.fft.ifftn(field_k).real

    def solve_metric_perturbation(self, T_munu, kx=None, ky=None, kz=None, k2=None):
        """Solve □h̄_{μν} = -16πG T_{μν} in Fourier space.

        In the weak-field/long-wavelength limit, the wave operator
        reduces to the Laplacian:
            h̄_{μν}(k) = 16πG * T_{μν}(k) / k²

        The trace-reversed metric perturbation h̄_{μν} is related to
        the physical perturbation by:
            h_{μν} = h̄_{μν} - (1/2) η_{μν} h̄ᵃᵃ

        Parameters
        ----------
        T_munu : dict
            Stress-energy tensor from build_stress_energy().
        kx, ky, kz : torch.Tensor or None
            Fourier-space wave vectors. Uses self.kx etc. if None.
        k2 : torch.Tensor or None
            k² = kx² + ky² + kz². Uses self.k2_safe if None.

        Returns
        -------
        hbar : dict
            Trace-reversed metric perturbation h̄_{μν} with keys
            'h00', 'h0i' (list of 3), 'hij' (3x3 list) in real space.
        """
        if kx is None:
            kx = self.kx
        if ky is None:
            ky = self.ky
        if kz is None:
            kz = self.kz
        if k2 is None:
            k2 = self.k2_safe

        G_eff = self.get_geff()
        prefactor = 16.0 * np.pi * G_eff

        # Helper: FFT a real field and divide by k²
        def solve_component(field_real):
            if field_real is None:
                return torch.zeros(self.shape, device=self.device)
            field_k = self._fft_field(field_real)
            field_k[0, 0, 0] = 0.0  # remove DC mode
            field_k = prefactor * field_k / k2
            return field_k  # still in Fourier space

        # ── Solve in Fourier space ──
        h00_k = solve_component(T_munu['T00'])

        h0i_k = []
        for i in range(3):
            h0i_k.append(solve_component(T_munu['T0i'][i]))

        hij_k = [[None for _ in range(3)] for _ in range(3)]
        for i in range(3):
            for j in range(3):
                hij_k[i][j] = solve_component(T_munu['Tij'][i][j])

        # ── Build trace-reversed h̄ in k-space, then IFFT ──
        hbar = {}
        # For convenience, also store k-space versions for TT projection
        hbar['h00_k'] = h00_k
        hbar['h0i_k'] = h0i_k
        hbar['hij_k'] = hij_k

        # IFFT each component to real space
        hbar['h00'] = self._ifft_field(h00_k)
        hbar['h0i'] = [self._ifft_field(h0i_k[i]) for i in range(3)]
        hij_real = [[None for _ in range(3)] for _ in range(3)]
        for i in range(3):
            for j in range(i, 3):
                val = self._ifft_field(hij_k[i][j])
                hij_real[i][j] = val
                if i != j:
                    hij_real[j][i] = val
        hbar['hij'] = hij_real

        return hbar

    def compute_gw_strain(self, h_ij, kx=None, ky=None, kz=None, k2=None):
        """Extract h_+ and h_× polarization amplitudes in TT gauge.

        Projects h_ij onto transverse-traceless gauge:
            h_ij_TT = P_ik P_jl h_kl - (1/2) P_ij P_kl h_kl
        where P_ij = δ_ij - k_i k_j / k²

        Then:
            h_+ = (h_xx_TT - h_yy_TT) / 2
            h_× = h_xy_TT

        Parameters
        ----------
        h_ij : list of lists
            3×3 list of real-space metric perturbation fields.
        kx, ky, kz : torch.Tensor or None
            Fourier-space wave vectors. Uses self.kx etc. if None.
        k2 : torch.Tensor or None
            k². Uses self.k2_safe if None.

        Returns
        -------
        h_plus : torch.Tensor
            Plus polarization in real space.
        h_cross : torch.Tensor
            Cross polarization in real space.
        h_strain_rms : float
            RMS strain sqrt(⟨h_+² + h_×²⟩).
        """
        if kx is None:
            kx = self.kx
        if ky is None:
            ky = self.ky
        if kz is None:
            kz = self.kz
        if k2 is None:
            k2 = self.k2_safe

        # Ensure k² is safe
        k2_safe = k2.clone()
        k2_safe[0, 0, 0] = 1.0

        # Projector P_ij = δ_ij - k_i k_j / k²
        # Build in Fourier space
        k_norm = [kx / k2_safe, ky / k2_safe, kz / k2_safe]

        # FFT each component of h_ij
        hk = [[None for _ in range(3)] for _ in range(3)]
        for i in range(3):
            for j in range(i, 3):
                hk[i][j] = self._fft_field(h_ij[i][j])
                if i != j:
                    hk[j][i] = hk[i][j]

        # Apply TT projector in k-space
        # P_ik = δ_ik - k_i n_k where n_k = k_k / k²
        # h_TT_ij(k) = P_im P_jn h_mn(k) - (1/2) P_ij P_mn h_mn(k)

        # We'll compute:
        # h̃_ij = P_im P_jn h_mn  (projection)
        # Then subtract trace: h_TT_ij = h̃_ij - (1/2) P_ij tr(h̃)

        # First compute P_ij for all i,j
        P = [[None for _ in range(3)] for _ in range(3)]
        for i in range(3):
            for j in range(3):
                if i == j:
                    P[i][j] = 1.0 - k_norm[i] * k_norm[j] * k2_safe
                else:
                    P[i][j] = -k_norm[i] * k_norm[j] * k2_safe

        # Compute h̃_ij = P_im P_jn h_mn
        htilde_k = [[None for _ in range(3)] for _ in range(3)]
        for i in range(3):
            for j in range(3):
                acc = torch.zeros(self.shape, dtype=torch.complex64, device=self.device)
                for m in range(3):
                    for n in range(3):
                        acc = acc + P[i][m] * P[j][n] * hk[m][n]
                htilde_k[i][j] = acc

        # Trace of h̃
        trace_h = torch.zeros(self.shape, dtype=torch.complex64, device=self.device)
        for i in range(3):
            trace_h = trace_h + htilde_k[i][i]

        # h̃_TT_ij = h̃_ij - (1/2) P_ij * tr(h̃)
        htt_k = [[None for _ in range(3)] for _ in range(3)]
        for i in range(3):
            for j in range(3):
                htt_k[i][j] = htilde_k[i][j] - 0.5 * P[i][j] * trace_h

        # IFFT back to real space
        htt = [[None for _ in range(3)] for _ in range(3)]
        for i in range(3):
            for j in range(i, 3):
                val = self._ifft_field(htt_k[i][j])
                htt[i][j] = val
                if i != j:
                    htt[j][i] = val

        # Plus and cross polarizations
        h_plus = 0.5 * (htt[0][0] - htt[1][1])
        h_cross = htt[0][1]

        # RMS strain
        strain_sq = h_plus**2 + h_cross**2
        h_strain_rms = float(torch.sqrt(strain_sq.mean()).cpu().numpy())

        return h_plus, h_cross, h_strain_rms

    def schwarzschild_radius(self, M, q=None):
        """Schwarzschild radius with φ-modified G_eff.

        r_s = 2 * G_eff(q) * M / c²

        For M = 1 M_sun, q = 0.5:
            r_s ≈ 2 * (G_N * (1 + (φ⁶−1)*0.5)) * M_sun / c²
            ≈ 3.86 km  (GR: 2.95 km)

        Parameters
        ----------
        M : float
            Mass in solar masses (M_sun). Internally converted to kg.
        q : float or None
            Qi coherence parameter. Uses self.q if None.

        Returns
        -------
        float
            Schwarzschild radius in meters.
        """
        G_eff = self.get_geff(q)
        M_kg = M * M_SUN
        r_s = 2.0 * G_eff * M_kg / C**2
        return r_s

    # ─────────────────────────────────────────────────────────────────────
    # φ-Predictions Summary
    # ─────────────────────────────────────────────────────────────────────

    def summary(self):
        """Print summary of φ-governed GR predictions."""
        print("=" * 60)
        print("Cassi GR Bridge—φ-Governed General Relativity")
        print("=" * 60)

        # Constants
        print(f"\n  Constants:")
        print(f"    φ = {PHI:.6f}")
        print(f"    G_N = {G_N:.6e} m³ kg⁻¹ s⁻²")
        print(f"    G_eff(q=0.5) = {self.get_geff(0.5):.6e} m³ kg⁻¹ s⁻²")

        # Schwarzschild
        r_s_q05 = self.schwarzschild_radius(1.0, q=0.5)
        r_s_gr = 2.0 * G_N * M_SUN / C**2
        print(f"\n  Schwarzschild Radius (M = 1 M_sun):")
        print(f"    GR:  r_s = {r_s_gr:.4e} m = {r_s_gr / 1e3:.4f} km")
        print(f"    φ-gravity, q=0.5: r_s = {r_s_q05:.4e} m = {r_s_q05 / 1e3:.4f} km")

        # Perihelion precession
        print(f"\n  Mercury Perihelion Precession:")
        dphi_rad, dphi_asec = self.perihelion_precession_formula(
            5.791e10, 0.2056, M_SUN)
        print(f"    Per orbit: {dphi_rad:.4e} rad = {dphi_asec:.4f} arcsec")
        orbits_century = 415.0
        total = dphi_asec * orbits_century
        print(f"    Per century: {total:.2f} arcsec/century")
        print(f"    Observed anomalous: ~43 arcsec/century")

        # φ-prediction for G_eff
        print(f"\n  φ-Governed G_eff(q):")
        for qi in [0.0, 0.25, 0.5, 0.75, 1.0]:
            geff = self.get_geff(qi)
            ratio = geff / G_N
            print(f"    q = {qi:.2f}: G_eff = {geff:.6e}, G_eff/G_N = {ratio:.6f}")

        print("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════
# Runner / Test Functions
# ═══════════════════════════════════════════════════════════════════════════

def test_schwarzschild(bridge, outdir):
    """Test Schwarzschild radius calculation."""
    print("\n" + "=" * 60)
    print("TEST: Schwarzschild Radius")
    print("=" * 60)

    for q_val in [0.0, 0.25, 0.5, 0.75, 1.0]:
        r_s = bridge.schwarzschild_radius(1.0, q=q_val)
        r_s_km = r_s / 1e3
        print(f"  q = {q_val:.2f}: r_s = {r_s:.4e} m = {r_s_km:.4f} km")

    # GR value for comparison
    r_s_gr = 2.0 * G_N * M_SUN / C**2
    print(f"\n  GR (q=0): r_s = {r_s_gr:.4e} m = {r_s_gr / 1e3:.4f} km")
    print(f"  Expected: ~3 km for M = 1 M_sun")

    return r_s_gr


def test_precession(bridge, outdir):
    """Test Mercury perihelion precession."""
    print("\n" + "=" * 60)
    print("TEST: Mercury Perihelion Precession")
    print("=" * 60)

    # Mercury orbital parameters
    a_mercury = 0.38709893 * AU  # semi-major axis in meters
    e_mercury = 0.20563069       # eccentricity

    print(f"  Mercury orbital parameters:")
    print(f"    a = {a_mercury:.4e} m = {a_mercury / AU:.4f} AU")
    print(f"    e = {e_mercury:.6f}")

    # Formula
    dphi_rad, dphi_asec = bridge.perihelion_precession_formula(
        a_mercury, e_mercury, M_SUN)
    print(f"\n  Formula result (per orbit):")
    print(f"    Δφ = {dphi_rad:.4e} rad = {dphi_asec:.4f} arcsec")

    orbits_century = 415.0
    total = dphi_asec * orbits_century
    print(f"  Per century ({orbits_century} orbits): {total:.2f} arcsec")

    # Also test with simplified numbers from the spec
    a_test = 5.791e10
    e_test = 0.2056
    dphi_rad2, dphi_asec2 = bridge.perihelion_precession_formula(
        a_test, e_test, M_SUN)
    total2 = dphi_asec2 * orbits_century
    print(f"\n  Spec numbers (a={a_test:.4e}, e={e_test:.4f}):")
    print(f"    Δφ = {dphi_rad2:.4e} rad = {dphi_asec2:.4f} arcsec/orbit")
    print(f"    Per century: {total2:.2f} arcsec")
    print(f"  Expected: ~43 arcsec/century")

    return total


def test_linearized(bridge, outdir):
    """Test linearized GR solver with a simple density field.

    Creates a Gaussian density perturbation and solves for the
    metric perturbation, then computes gravitational wave strain.
    """
    print("\n" + "=" * 60)
    print("TEST: Linearized GR Solver")
    print("=" * 60)

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Create a Gaussian density pulse at the origin
    N = bridge.grid
    x = torch.linspace(-bridge.L / 2, bridge.L / 2, N, device=bridge.device)
    y = torch.linspace(-bridge.L / 2, bridge.L / 2, N, device=bridge.device)
    z = torch.linspace(-bridge.L / 2, bridge.L / 2, N, device=bridge.device)
    X, Y, Z = torch.meshgrid(x, y, z, indexing='ij')

    # Gaussian density: ρ = ρ₀ * exp(-r²/(2σ²))
    sigma = bridge.L / 8.0
    rho0 = 1.0
    rho = rho0 * torch.exp(-(X**2 + Y**2 + Z**2) / (2.0 * sigma**2))

    # Rotating current: j = ρ * ω × r (rigid rotation around z-axis)
    omega = 0.5
    jx = -rho * omega * Y
    jy = rho * omega * X
    jz = torch.zeros_like(rho)

    print(f"  Grid: {N}³, L = {bridge.L}")
    print(f"  Density peak: ρ₀ = {rho0}")
    print(f"  Gaussian σ = {sigma:.4f}")
    print(f"  Rotation ω = {omega}")

    # Build stress-energy tensor
    print("\n  Building T_{μν}...")
    T = bridge.build_stress_energy(rho, jx, jy, jz, pressure=None)

    print(f"    T00 range: [{T['T00'].min().item():.4e}, {T['T00'].max().item():.4e}]")
    print(f"    T0i mean |j|: {torch.sqrt(jx**2 + jy**2 + jz**2).mean().item():.6e}")

    # Solve metric perturbation
    print("\n  Solving □h̄_{μν} = -16πG T_{μν}...")
    hbar = bridge.solve_metric_perturbation(T)

    print(f"    h̄_00 range: [{hbar['h00'].min().item():.4e}, {hbar['h00'].max().item():.4e}]")

    # Compute GW strain
    print("\n  Extracting gravitational wave strain...")
    h_plus, h_cross, h_rms = bridge.compute_gw_strain(hbar['hij'])

    print(f"    h_+ range: [{h_plus.min().item():.4e}, {h_plus.max().item():.4e}]")
    print(f"    h_× range: [{h_cross.min().item():.4e}, {h_cross.max().item():.4e}]")
    print(f"    h_rms = {h_rms:.6e}")

    # Plot
    fig, axes = plt.subplots(2, 3, figsize=(14, 10))

    # Mid-plane slices
    mid = N // 2

    # Density
    im0 = axes[0, 0].imshow(rho[:, :, mid].cpu().numpy(), cmap='viridis',
                             extent=[-bridge.L/2, bridge.L/2, -bridge.L/2, bridge.L/2])
    axes[0, 0].set_title('Density ρ (z=0 slice)')
    axes[0, 0].set_xlabel('x')
    axes[0, 0].set_ylabel('y')
    plt.colorbar(im0, ax=axes[0, 0], fraction=0.046)

    # h̄_00
    h00_slice = hbar['h00'][:, :, mid].cpu().numpy()
    im1 = axes[0, 1].imshow(h00_slice, cmap='RdBu_r',
                             extent=[-bridge.L/2, bridge.L/2, -bridge.L/2, bridge.L/2])
    axes[0, 1].set_title('h̄_00 (z=0 slice)')
    axes[0, 1].set_xlabel('x')
    axes[0, 1].set_ylabel('y')
    plt.colorbar(im1, ax=axes[0, 1], fraction=0.046)

    # h̄_0x (gravitomagnetic)
    h0x_slice = hbar['h0i'][0][:, :, mid].cpu().numpy()
    im2 = axes[0, 2].imshow(h0x_slice, cmap='RdBu_r',
                             extent=[-bridge.L/2, bridge.L/2, -bridge.L/2, bridge.L/2])
    axes[0, 2].set_title('h̄_0x (gravitomagnetic)')
    axes[0, 2].set_xlabel('x')
    axes[0, 2].set_ylabel('y')
    plt.colorbar(im2, ax=axes[0, 2], fraction=0.046)

    # h_+ (GW strain)
    hplus_slice = h_plus[:, :, mid].cpu().numpy()
    im3 = axes[1, 0].imshow(hplus_slice, cmap='RdBu_r',
                             extent=[-bridge.L/2, bridge.L/2, -bridge.L/2, bridge.L/2])
    axes[1, 0].set_title('h_+ (plus polarization)')
    axes[1, 0].set_xlabel('x')
    axes[1, 0].set_ylabel('y')
    plt.colorbar(im3, ax=axes[1, 0], fraction=0.046)

    # h_× (GW strain)
    hcross_slice = h_cross[:, :, mid].cpu().numpy()
    im4 = axes[1, 1].imshow(hcross_slice, cmap='RdBu_r',
                             extent=[-bridge.L/2, bridge.L/2, -bridge.L/2, bridge.L/2])
    axes[1, 1].set_title('h_× (cross polarization)')
    axes[1, 1].set_xlabel('x')
    axes[1, 1].set_ylabel('y')
    plt.colorbar(im4, ax=axes[1, 1], fraction=0.046)

    # Combined strain
    strain = torch.sqrt(h_plus**2 + h_cross**2)
    strain_slice = strain[:, :, mid].cpu().numpy()
    im5 = axes[1, 2].imshow(strain_slice, cmap='hot',
                             extent=[-bridge.L/2, bridge.L/2, -bridge.L/2, bridge.L/2])
    axes[1, 2].set_title(f'Strain |h| (RMS = {h_rms:.4e})')
    axes[1, 2].set_xlabel('x')
    axes[1, 2].set_ylabel('y')
    plt.colorbar(im5, ax=axes[1, 2], fraction=0.046)

    plt.tight_layout()
    save_path = outdir / 'cassi_gr_linearized.png'
    fig.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"\n  Saved linearized GR plot to {save_path}")

    return h_rms


def test_orbit(bridge, outdir):
    """Test orbital integration with PN corrections."""
    print("\n" + "=" * 60)
    print("TEST: Orbital Integration (PN Effective Potential)")
    print("=" * 60)

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Solar mass with Mercury-like orbit
    M = M_SUN
    a_merc = 0.38709893 * AU
    e_merc = 0.20563069
    r_peri = a_merc * (1.0 - e_merc)  # perihelion distance (m)
    # Correct Keplerian velocity at perihelion from vis-viva:
    # v² = GM * (2/r - 1/a), at perihelion r = a(1-e):
    # v_peri = sqrt(GM * (1+e) / r_peri)
    v_peri = np.sqrt(G_N * M * (1.0 + e_merc) / r_peri)

    print(f"  M = {M / M_SUN:.1f} M_sun")
    print(f"  r_peri = {r_peri:.4e} m = {r_peri / AU:.4f} AU")
    print(f"  v_peri = {v_peri:.1f} m/s")

    # Compute angular momentum
    L = r_peri * v_peri

    print(f"  L = {L:.4e} m²/s")

    # Integrate just a few orbits for testing
    n_test = 3.0
    steps = 20000
    print(f"\n  Integrating {n_test} orbits ({int(n_test * steps)} steps)...")

    t0 = time.time()
    r_hist, phi_hist, precession = bridge.integrate_orbit(
        r_peri, 0.0, M, L=L, n_orbits=n_test,
        steps_per_orbit=steps, q=0, return_full=True)
    dt = time.time() - t0

    print(f"  Integration time: {dt:.2f} s")
    print(f"  Total precession over {n_test} orbits: {precession:.6e} rad")
    print(f"  Per orbit: {precession / n_test:.6e} rad = {precession / n_test * ARCSEC_PER_RAD:.6f} arcsec")

    # Plot trajectory
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Cartesian trajectory
    x_traj = r_hist * np.cos(phi_hist)
    y_traj = r_hist * np.sin(phi_hist)

    ax = axes[0]
    ax.plot(x_traj / AU, y_traj / AU, 'b-', lw=0.8)
    ax.plot(0, 0, 'yo', markersize=8, label='Sun')
    ax.set_xlabel('x (AU)')
    ax.set_ylabel('y (AU)')
    ax.set_title(f'Mercury-like Orbit ({n_test} orbits)')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.legend()

    # Radial distance
    ax = axes[1]
    ax.plot(phi_hist, r_hist / AU, 'r-', lw=0.8)
    ax.set_xlabel('φ (rad)')
    ax.set_ylabel('r (AU)')
    ax.set_title('Radial Distance vs. Azimuth')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    save_path = outdir / 'cassi_gr_orbit.png'
    fig.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"\n  Saved orbit plot to {save_path}")

    return precession


# ═══════════════════════════════════════════════════════════════════════════
# Main / CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='CassGRBridge: GR extensions to Cassi two-fluid framework',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
φ-predictions:
  G_eff(q) = G_N * (1 + (φ⁶−1)·q) for q ∈ [0,1] — max boost φ⁶ ≈ 17.94
  Mercury precession: 43 arcsec/century at q=0 (pure GR)
  Schwarzschild: ~3 km for 1 M_sun at q ≈ 0.5
        """)
    parser.add_argument('--test', default='all',
                        choices=['schwarzschild', 'precession', 'linearized',
                                 'orbit', 'summary', 'all'],
                        help='Which test to run')
    parser.add_argument('--grid', type=int, default=64,
                        help='Grid resolution for linearized GR')
    parser.add_argument('--L', type=float, default=20.0,
                        help='Box size for linearized GR')
    parser.add_argument('--q', type=float, default=0.5,
                        help='Qi coherence for G_eff test')
    parser.add_argument('--outdir', default='figures',
                        help='Output directory for figures')
    args = parser.parse_args()

    # Create bridge
    bridge = CassGRBridge(grid=args.grid, L=args.L, q=args.q)

    # Run tests
    if args.test == 'summary':
        bridge.summary()
        return

    if args.test in ('all', 'schwarzschild'):
        test_schwarzschild(bridge, args.outdir)

    if args.test in ('all', 'precession'):
        test_precession(bridge, args.outdir)

    if args.test in ('all', 'linearized'):
        test_linearized(bridge, args.outdir)

    if args.test in ('all', 'orbit'):
        test_orbit(bridge, args.outdir)

    print("\nDone.")


if __name__ == '__main__':
    main()
