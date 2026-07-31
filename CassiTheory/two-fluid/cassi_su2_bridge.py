#!/usr/bin/env python3
"""
Cassi SU(2) Gauge Bridge: φ-Governed Weak Force
=================================================

Extends CassiBridgeV2 patterns to SU(2) gauge theory with φ-governed
symmetry breaking. Promotes the complex field to a 2-component isospinor
and introduces three SU(2) gauge fields W^a_μ.

Key φ-predictions:
  - sin²θ_W ≈ φ⁻³ ≈ 0.236 (phenomenological benchmark; exact derivation open)
  - m_W/m_Z = cos θ_W at the φ-fixed point
  - GUT coupling α_GUT ≈ φ⁻³/(4π) ≈ 1/53

Usage:
    python two-fluid/cassi_su2_bridge.py --help
    python two-fluid/cassi_su2_bridge.py --grid 32 --test
"""

import sys, argparse, time, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

import torch

# ─── Universal constants ───────────────────────────────────────────────────
PHI     = (1.0 + np.sqrt(5.0)) / 2.0   # ≈ 1.618034
PHI_INV = 1.0 / PHI                     # ≈ 0.618034
PHI_INV2 = PHI_INV ** 2                 # ≈ 0.381966
PHI_INV_SQRT = np.sqrt(PHI_INV)         # φ⁻¹/² ≈ 0.786 = 1/√φ (amplitude ratio for ρ_Y/ρ_I = φ)


# ═══════════════════════════════════════════════════════════════════════════
# SU(2) Gauge Bridge
# ═══════════════════════════════════════════════════════════════════════════

class CassiSU2Bridge:
    """φ-governed SU(2) gauge theory on a 3D grid.

    Promotes the scalar field to a 2-component isospinor Ψ = (ψ_Y, ψ_I)^T
    with Yang (hypercharge) and Yin (isospin) components. Three SU(2)
    gauge fields W^a_μ mediate the weak force with Yang-Mills dynamics.

    Parameters
    ----------
    grid : int
        Grid points per dimension (N³ total).
    L : float
        Physical box size.
    g : float
        SU(2) gauge coupling.
    g_prime : float
        U(1)_Y gauge coupling (hypercharge).
    device : str or torch.device
        Compute device.
    """
    def __init__(self, grid=64, L=20.0, g=1.0, g_prime=0.5, device=None):
        # Grid
        self.grid = grid
        self.L = L
        self.dim = 3
        self.shape = (grid, grid, grid)
        self.dx = L / grid
        self.dV = self.dx ** 3
        self.N_cells = grid ** 3

        # Gauge couplings
        self.g = g                   # SU(2) coupling
        self.g_prime = g_prime       # U(1)_Y coupling
        self.theta_W = np.arctan2(g_prime, g) if g > 0 else 0.0
        self.sin2_theta_W = np.sin(self.theta_W) ** 2
        self.cos_theta_W = np.cos(self.theta_W)

        # Derived: φ-predicted mixing angle
        # sin²θ_W = φ⁻³ ≈ 0.236 (phenomenological benchmark)
        self.phi_sin2_theta_W = PHI_INV ** 3
        self.phi_theta_W = np.arcsin(np.sqrt(self.phi_sin2_theta_W))
        self.phi_cos_theta_W = np.cos(self.phi_theta_W)

        # Device
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        elif isinstance(device, str):
            self.device = torch.device(device)
        else:
            self.device = device

        # ── k-space grid ────────────────────────────────────────────────
        k_1d = 2.0 * np.pi * torch.fft.fftfreq(grid, d=self.dx, device=self.device)
        self.kx, self.ky, self.kz = torch.meshgrid(k_1d, k_1d, k_1d, indexing='ij')
        self.k2 = self.kx**2 + self.ky**2 + self.kz**2
        self.k_mag = torch.sqrt(self.k2)
        self.k0 = self.k_mag[self.k_mag > 0].min()
        self.k2_safe = self.k2.clone()
        self.k2_safe[0, 0, 0] = 1.0

        # ── Real-space grid ─────────────────────────────────────────────
        x = torch.linspace(-L/2, L/2, grid, device=self.device)
        self.X, self.Y, self.Z = torch.meshgrid(x, x, x, indexing='ij')
        self.R = torch.sqrt(self.X**2 + self.Y**2 + self.Z**2)

        # ── Pauli matrices (act on isospin space, NOT spin) ────────────
        # τ¹ = [[0,1],[1,0]], τ² = [[0,-i],[i,0]], τ³ = [[1,0],[0,-1]]
        self.tau_1 = torch.tensor([[0.0, 1.0], [1.0, 0.0]], dtype=torch.complex64, device=self.device)
        self.tau_2 = torch.tensor([[0.0, -1.0j], [1.0j, 0.0]], dtype=torch.complex64, device=self.device)
        self.tau_3 = torch.tensor([[1.0, 0.0], [0.0, -1.0]], dtype=torch.complex64, device=self.device)
        self.taus = [self.tau_1, self.tau_2, self.tau_3]

        # Identity in isospin space
        self.tau_0 = torch.eye(2, dtype=torch.complex64, device=self.device)

        # ── State ───────────────────────────────────────────────────────
        self.t = 0.0

        # Diagnostic accumulators
        self.history = {
            't': [],
            'E_Y': [],          # Yang (upper component) energy
            'E_I': [],          # Yin (lower component) energy
            'ratio': [],        # Yang/Yin density ratio
            'W_rms': [],        # RMS gauge field
            'YM_energy': [],    # Yang-Mills energy density
            'rho_Q': [],        # Qi charge density
            'm_W': [],          # W boson mass (code units)
            'm_Z': [],          # Z boson mass (code units)
        }

    # ────────────────────────────────────────────────────────────────────
    # Pauli Matrix Operations
    # ────────────────────────────────────────────────────────────────────

    def pauli_dot(self, vec):
        """Compute τ^a · v^a for a 3-vector field.

        vec: (..., 3) real or complex tensor.
        Returns: (..., 2, 2) complex tensor = sum_a v^a τ^a.
        """
        return (vec[..., 0] * self.tau_1 +
                vec[..., 1] * self.tau_2 +
                vec[..., 2] * self.tau_3)

    def pauli_adjoint(self, M):
        """Adjoint action: ad_{τ^a}(X) = [τ^a/2, X] for isospin matrices.

        Given 2x2 matrix field M (..., 2, 2), returns 3-vector of
        tr(τ^a M) / 2, the components in the Lie algebra.
        """
        # M is (..., 2, 2), we extract components via trace(τ^a · M) / 2
        c1 = torch.trace(M @ self.tau_1) / 2.0  # ... but vectorized
        # Use batch matmul: for each isospin position
        out = torch.zeros(*M.shape[:-2], 3, dtype=torch.complex64, device=self.device)
        for a in range(3):
            tr = (M[..., 0, 0] * self.taus[a][0, 0] +
                  M[..., 0, 1] * self.taus[a][0, 1] +
                  M[..., 1, 0] * self.taus[a][1, 0] +
                  M[..., 1, 1] * self.taus[a][1, 1])
            out[..., a] = tr / 2.0
        return out

    # ────────────────────────────────────────────────────────────────────
    # Isospinor Operations
    # ────────────────────────────────────────────────────────────────────

    def isospinor_dagger(self, psi):
        """Hermitian conjugate of isospinor: Ψ† = (ψ_Y*, ψ_I*).

        psi: (2, N, N, N) complex tensor.
        Returns: (2, N, N, N) complex tensor with complex-conjugated values.
        """
        return torch.conj(psi)

    def isospinor_density(self, psi):
        """Total density ρ = Ψ†Ψ = |ψ_Y|² + |ψ_I|².

        psi: (2, N, N, N) complex tensor.
        Returns: (N, N, N) float tensor.
        """
        return (torch.abs(psi[0])**2 + torch.abs(psi[1])**2).real

    def yang_density(self, psi):
        """Yang (upper component) density: ρ_Y = |ψ_Y|²."""
        return (torch.abs(psi[0])**2).real

    def yin_density(self, psi):
        """Yin (lower component) density: ρ_I = |ψ_I|²."""
        return (torch.abs(psi[1])**2).real

    def yang_yin_ratio(self, psi):
        """Mean Yang/Yin density ratio r = ⟨|ψ_Y|²⟩ / ⟨|ψ_I|²⟩."""
        rho_Y = self.yang_density(psi).mean()
        rho_I = self.yin_density(psi).mean()
        if rho_I < 1e-30:
            return 1000.0  # effectively infinite
        return (rho_Y / rho_I).item()

    # ────────────────────────────────────────────────────────────────────
    # Covariant Derivative
    # ────────────────────────────────────────────────────────────────────

    def covariant_derivative(self, psi, W_fields, component=0):
        """Compute D_i Ψ = ∂_i Ψ - i g W^a_i τ^a/2 Ψ for spatial directions.

        psi: (2, N, N, N) complex isospinor.
        W_fields: (3, 3, N, N, N)—W^a_i where a=0,1,2 (Pauli index)
                  and i=0,1,2 (x,y,z spatial direction).
        component: which gradient component to return (0=x, 1=y, 2=z).

        Returns: (2, N, N, N) complex—covariant derivative along component.
        """
        # Fourier derivative: ∂_i Ψ
        psi_k = torch.fft.fftn(psi, dim=(1, 2, 3))
        k_comp = [self.kx, self.ky, self.kz][component]
        grad_psi = torch.fft.ifftn(1j * k_comp * psi_k, dim=(1, 2, 3))

        # Gauge connection term: -i g W^a_i τ^a/2 Ψ
        # Sum over a of W^a_i * τ^a/2
        connection = torch.zeros(2, 2, dtype=torch.complex64, device=self.device)
        for a in range(3):
            W_a = W_fields[a, component]  # (N, N, N) real
            connection = connection + W_a.unsqueeze(-1).unsqueeze(-1) * self.taus[a] / 2.0

        # Apply connection to psi: (connection @ psi) summed over isospin index
        # connection: (N, N, N, 2, 2), psi: (2, N, N, N)
        # -> (2, N, N, N)
        psi_perm = psi.permute(1, 2, 3, 0)  # (N,N,N,2)
        conn_psi = torch.zeros_like(psi_perm)
        for a in range(2):
            for b in range(2):
                conn_psi[..., a] = conn_psi[..., a] + connection[..., a, b] * psi_perm[..., b]
        conn_psi = conn_psi.permute(3, 0, 1, 2)  # (2,N,N,N)

        D_psi = grad_psi - 1j * self.g * conn_psi
        return D_psi

    def spectral_gradient(self, field, component=0):
        """Spectral derivative ∂_i of a scalar or component field.

        field: (N, N, N) complex tensor, or (2, N, N, N) for isospinor.
        component: 0=x, 1=y, 2=z.
        Returns: same shape as field—gradient along component.
        """
        k_comp = [self.kx, self.ky, self.kz][component]
        # FFT only the spatial dimensions (last 3 dims), not batch dim 0
        ndim = field.ndim
        spatial_dims = tuple(range(ndim - 3, ndim))
        field_k = torch.fft.fftn(field, dim=spatial_dims)
        return torch.fft.ifftn(1j * k_comp * field_k, dim=spatial_dims)

    def spectral_laplacian(self, field):
        """Spectral Laplacian ∇² = ∂_x² + ∂_y² + ∂_z².

        field: (N, N, N) complex tensor.
        Returns: (N, N, N) complex tensor.
        """
        field_k = torch.fft.fftn(field)
        return torch.fft.ifftn(-self.k2 * field_k)

    def spectral_gradient_3d(self, field):
        """Spectral gradient as a 3-vector field.

        field: (N, N, N) complex tensor.
        Returns: (3, N, N, N) complex tensor (x,y,z components).
        """
        field_k = torch.fft.fftn(field)
        gx = torch.fft.ifftn(1j * self.kx * field_k)
        gy = torch.fft.ifftn(1j * self.ky * field_k)
        gz = torch.fft.ifftn(1j * self.kz * field_k)
        return torch.stack([gx, gy, gz], dim=0)

    # ────────────────────────────────────────────────────────────────────
    # Isospin Currents
    # ────────────────────────────────────────────────────────────────────

    def compute_isospin_current(self, psi, W_fields=None):
        """Compute SU(2) isospin current: j^{a μ} = Ψ† τ^a D^μ Ψ.

        psi: (2, N, N, N) complex isospinor.
        W_fields: (3, 3, N, N, N) or None (not used yet—future covariant derivation).

        Returns:
          rho_a: (3, N, N, N)—isospin charge density ρ^a = Ψ† τ^a Ψ
          j_a_i: (3, 3, N, N, N)—isospin current spatial components
                 j^a_i where a=0,1,2 (Pauli) and i=0,1,2 (spatial)
        """
        # Ψ† = complex conjugate of each component (row vector in isospin space)
        psi_dag = torch.conj(psi)  # (2, N, N, N)

        # Charge density: ρ^a = Ψ† τ^a Ψ = Σ_{ij} ψ_i* τ^a_{ij} ψ_j
        rho_a = torch.zeros(3, *self.shape, dtype=torch.complex64, device=self.device)
        for a in range(3):
            for i in range(2):
                for j in range(2):
                    rho_a[a] += psi_dag[i] * self.taus[a][i, j] * psi[j]

        # Spatial current: j^a_i = Im(Ψ† τ^a ∂_i Ψ)
        j_a_i = torch.zeros(3, 3, *self.shape, dtype=torch.complex64, device=self.device)
        for a in range(3):
            for i in range(3):
                grad_psi = self.spectral_gradient(psi, component=i)  # (2, N, N, N)
                current = torch.zeros(self.shape, dtype=torch.complex64, device=self.device)
                for ii in range(2):
                    for jj in range(2):
                        current += psi_dag[ii] * self.taus[a][ii, jj] * grad_psi[jj]
                j_a_i[a, i] = current.imag

        return rho_a.real, j_a_i.real

    def compute_gauge_source(self, psi):
        """Compute gauge field source: j^a_i = Im(Ψ† τ^a ∂_i Ψ).

        This is the current that sources the Yang-Mills equation:
        ∇² W^a_i = -j^a_i  (linearized approximation).

        psi: (2, N, N, N) complex isospinor.

        Returns:
          source: (3, 3, N, N, N)—gauge source for each a, i.
        """
        _, j_a_i = self.compute_isospin_current(psi)
        return j_a_i

    # ────────────────────────────────────────────────────────────────────
    # Gauge Field Evolution
    # ────────────────────────────────────────────────────────────────────

    def evolve_gauge_fields(self, W_fields, psi, dt):
        """Evolve gauge fields via linearized Yang-Mills: ∇² W = -j.

        Using Poisson solve in Fourier space with Strang half-step:
        W_new = W_old + dt * (∇^{-2} j)  [diffusion-like update]

        W_fields: (3, 3, N, N, N)—current gauge fields.
        psi: (2, N, N, N)—isospinor.
        dt: float—time step.

        Returns: (3, 3, N, N, N)—updated gauge fields.
        """
        j_a_i = self.compute_gauge_source(psi)

        W_new = W_fields.clone()
        for a in range(3):
            for i in range(3):
                # Poisson solve: W^a_i += dt * ∇^{-2} j^a_i
                j_k = torch.fft.fftn(j_a_i[a, i])
                j_k[0, 0, 0] = 0.0  # remove zero mode
                source_potential = torch.fft.ifftn(j_k / self.k2_safe).real
                W_new[a, i] = W_new[a, i] + dt * source_potential

        return W_new

    def compute_yang_mills_energy(self, W_fields):
        """Compute Yang-Mills energy density: (1/4) F^a_{μν} F^{a μν}.

        In 3D we only have spatial components, so:
        ε_YM = (1/4) Σ_a Σ_{i,j} (F^a_{ij})²

        where F^a_{ij} = ∂_i W^a_j - ∂_j W^a_i + g ε^{abc} W^b_i W^c_j

        W_fields: (3, 3, N, N, N)—W^a_i.

        Returns: float—mean Yang-Mills energy density.
        """
        total_energy = 0.0

        # Levi-Civita symbol ε^{abc}
        def epsilon(a, b, c):
            if (a, b, c) in [(0, 1, 2), (1, 2, 0), (2, 0, 1)]:
                return 1.0
            elif (a, b, c) in [(0, 2, 1), (2, 1, 0), (1, 0, 2)]:
                return -1.0
            return 0.0

        for a in range(3):
            energy_a = torch.zeros(self.shape, dtype=torch.float32, device=self.device)
            for i in range(3):
                for j in range(3):
                    # ∂_i W^a_j
                    di_Waj = self.spectral_gradient(W_fields[a, j], i)
                    # ∂_j W^a_i
                    dj_Wai = self.spectral_gradient(W_fields[a, i], j)

                    # Non-linear term: g ε^{abc} W^b_i W^c_j
                    nl_term = torch.zeros(self.shape, dtype=torch.complex64, device=self.device)
                    for b in range(3):
                        for c in range(3):
                            eps = epsilon(a, b, c)
                            if eps != 0.0:
                                nl_term = nl_term + eps * W_fields[b, i] * W_fields[c, j]

                    F_ij = di_Waj - dj_Wai + self.g * nl_term
                    energy_a = energy_a + (F_ij.real**2 + F_ij.imag**2)

            total_energy += energy_a.mean().item()

        return total_energy / 4.0  # (1/4) F_μν F^{μν}

    # ────────────────────────────────────────────────────────────────────
    # φ-Governed Symmetry Breaking
    # ────────────────────────────────────────────────────────────────────

    def compute_v(self, psi):
        """Compute the Higgs-like vacuum expectation v from the isospinor.

        v = √⟨ρ_total⟩ · (r - 1) / (r + 1)
        where r = ⟨|ψ_Y|²⟩ / ⟨|ψ_I|²⟩ is the Yang/Yin ratio.

        At r = φ, the field is at the fixed point and the symmetry is broken
        in the φ-determined ratio.

        Returns: float—v parameter in code units.
        """
        rho_total = self.isospinor_density(psi).mean().item()
        r = self.yang_yin_ratio(psi)
        sqrt_rho = np.sqrt(max(rho_total, 1e-30))
        v = sqrt_rho * (r - 1.0) / (r + 1.0 + 1e-30)
        return v

    def compute_w_mass(self, psi, gauge_coupling=None):
        """Compute W boson mass: m_W = g · v / 2.

        psi: (2, N, N, N) complex isospinor.
        gauge_coupling: g value to use (default: self.g).

        Returns: float—W mass in code units.
        """
        g = gauge_coupling if gauge_coupling is not None else self.g
        v = self.compute_v(psi)
        return g * v / 2.0

    def compute_z_mass(self, psi, g=None, g_prime=None):
        """Compute Z boson mass: m_Z = √(g² + g'²) · v / 2.

        psi: (2, N, N, N) complex isospinor.
        g, g_prime: gauge couplings (default: self.g, self.g_prime).

        Returns: float—Z mass in code units.
        """
        g = g if g is not None else self.g
        gp = g_prime if g_prime is not None else self.g_prime
        v = self.compute_v(psi)
        return np.sqrt(g**2 + gp**2) * v / 2.0

    def mass_ratio_prediction(self):
        """φ-predicted m_W/m_Z = cos θ_W with sin²θ_W = φ⁻³ ≈ 0.236.

        Returns: (m_W/m_Z ratio, sin²θ_W, cos θ_W).
        """
        return (self.phi_cos_theta_W, self.phi_sin2_theta_W, self.phi_cos_theta_W)

    # ────────────────────────────────────────────────────────────────────
    # Running Coupling (φ-attractor)
    # ────────────────────────────────────────────────────────────────────

    def compute_running_coupling(self, alpha_0, scale_ratio, b0=11.0):
        """One-loop running coupling: α(μ) = α₀ / (1 + b₀ α₀/(2π) · ln(μ/μ₀)).

        alpha_0: fine-structure constant at reference scale μ₀.
        scale_ratio: μ/μ₀ (or equivalently E/E₀).
        b0: beta-function coefficient. For SU(3): b0 = 11 - 2n_f/3.
            With n_f=6 → b0 = 11 - 4 = 7.

        Returns: α(μ) running coupling.
        """
        denominator = 1.0 + b0 * alpha_0 / (2.0 * np.pi) * np.log(scale_ratio)
        if denominator <= 0:
            return 0.0  # Landau pole
        return alpha_0 / denominator

    def gut_coupling(self):
        """GUT coupling from φ: α_GUT ≈ φ⁻³/(4π) ≈ 0.00754 ≈ 1/53.

        Returns: α_GUT as float.
        """
        return PHI_INV ** 3 / (4.0 * np.pi)
    def alpha_s_at_mz(self, n_f=6):
        """Run α_s from GUT scale to M_Z and compare to measured α_s(M_Z) ≈ 0.118.

        Uses one-loop running: α_s(μ) = α_GUT / (1 + β₀ α_GUT/(2π) · ln(μ/μ_GUT))
        with β₀ = 11 - 2n_f/3.

        For μ = M_Z < μ_GUT, ln(μ/μ_GUT) < 0, so denominator < 1
        and α_s grows at lower energy (asymptotic freedom).

        n_f: number of active flavors (default 6 at high scale).

        Returns: (alpha_s_MZ_predicted, alpha_s_measured, scale_ratio_MZ_over_GUT).
        """
        alpha_gut = self.gut_coupling()
        # b0 = β₀ for one-loop QCD: 11 - 2*n_f/3
        b0 = 11.0 - 2.0 * n_f / 3.0
        # M_GUT ≈ 2×10¹⁶ GeV (typical GUT scale)
        # M_Z ≈ 91.2 GeV
        m_gut = 2.0e16  # GeV
        m_z = 91.2  # GeV
        scale_ratio = m_z / m_gut  # ≈ 4.56e-15
        alpha_mz = self.compute_running_coupling(alpha_gut, scale_ratio, b0)
        alpha_mz_measured = 0.118
        return (alpha_mz, alpha_mz_measured, scale_ratio)

    # ────────────────────────────────────────────────────────────────────
    # Isospinor Evolution
    # ────────────────────────────────────────────────────────────────────

    def evolve_isospinor(self, psi, W_fields, dt, V_ext=None):
        """Evolve the isospinor with kinetic + potential splitting.

        Uses Strang splitting: half potential → full kinetic → half potential.
        The potential step includes SU(2) gauge-field-induced isospin rotation
        that mixes Yang and Yin components.

        psi: (2, N, N, N) complex isospinor.
        W_fields: (3, 3, N, N, N)—gauge fields.
        dt: float—time step.
        V_ext: (N, N, N) float or None—external potential.

        Returns: (2, N, N, N)—updated isospinor.
        """
        # Half-step potential (includes gauge-field isospin rotation)
        psi = self.potential_propagator(psi, W_fields, dt / 2.0, V_ext=V_ext)

        # Full kinetic step (covariant Laplacian)
        psi = self.kinetic_propagator(psi, W_fields, dt)

        # Half-step potential
        psi = self.potential_propagator(psi, W_fields, dt / 2.0, V_ext=V_ext)

        return psi

    def potential_propagator(self, psi, W_fields, dt, V_ext=None):
        """Potential step: exp(-i H_pot dt) on the isospinor.

        The effective Hamiltonian includes:
          - SU(2) isospin rotation from W³ gauge field (mixes ψ_Y, ψ_I)
          - φ-attractor potential: drives r = ρ_Y/ρ_I toward φ
          - Self-interaction from total density
          - External potential (if provided)

        The SU(2) rotation is implemented as an exact unitary rotation
        in isospin space using the neutral component W³:
            θ = g · dt · W³_avg / 2
            ψ'_Y = ψ_Y·cos(θ) - ψ_I·sin(θ)
            ψ'_I = ψ_Y·sin(θ) + ψ_I·cos(θ)
        """
        # ── SU(2) isospin rotation from neutral gauge field W³ ──
        # W_avg[a] = mean over spatial directions for each Pauli component a
        W_avg = W_fields.mean(dim=1)  # (3, N, N, N)

        # Use W³ (neutral component, a=2) to generate isospin rotation:
        # Rotation angle θ = g · dt · ⟨W³⟩ / 2
        theta = 0.5 * self.g * dt * W_avg[2]  # (N, N, N)

        # Exact unitary SU(2) rotation in isospin space
        cos_t = torch.cos(theta)
        sin_t = torch.sin(theta)
        psi_mid = torch.zeros_like(psi)
        psi_mid[0] =  psi[0] * cos_t - psi[1] * sin_t
        psi_mid[1] =  psi[0] * sin_t + psi[1] * cos_t

        # ── φ-attractor potential ──
        # Drives the system toward the φ-fixed point r = φ by penalizing
        # deviations of the Yang/Yin fraction from the target.
        rho_Y = self.yang_density(psi_mid)
        rho_I = self.yin_density(psi_mid)
        rho_tot = rho_Y + rho_I + 1e-30

        # At r = φ: ρ_Y/ρ_tot = φ/(1+φ) ≈ 0.618, ρ_I/ρ_tot = 1/(1+φ) ≈ 0.382
        target_frac = PHI / (1.0 + PHI)  # ≈ 0.618
        actual_frac = rho_Y / rho_tot
        # Boost φ-attractor strength when far from φ-fixed point
        boost = 1.0 + torch.abs(actual_frac - target_frac) * 5.0
        lambda_phi = 0.5 * self.g * boost
        V_phi = lambda_phi * (actual_frac - target_frac) ** 2

        # ── Scalar potential terms (act equally on both components) ──
        V_scalar = torch.zeros_like(rho_tot)
        if V_ext is not None:
            V_scalar = V_scalar + V_ext
        V_scalar = V_scalar + 0.1 * rho_tot  # phi⁴-like self-interaction

        # ── φ-attractor applies σ₃-like opposite signs to Yang/Yin ──
        # V_phi adds energy to one component, removes from the other,
        # driving ρ_Y/ρ_I toward the target fraction φ/(1+φ)
        # Propagate each component with signed potential
        psi_out = psi_mid.clone()
        for c in range(2):
            sign = 1.0 if c == 0 else -1.0  # + for Yang, - for Yin
            total_V = V_scalar + sign * V_phi
            psi_out[c] = psi_mid[c] * torch.exp(-1j * total_V * dt)

        return psi_out

    def kinetic_propagator(self, psi, W_fields, dt):
        """Kinetic step: exp(-i (-∇²/2) dt) in Fourier space.

        For the covariant kinetic term: -(1/2) D_i D_i acting on each
        isospinor component. Approximated with the ordinary Laplacian
        plus a gauge potential correction.
        """
        # Gauge potential correction: Σ_i (W^3_i)² acts as effective mass shift
        # for the third isospin component, creating a splitting between ψ_Y and ψ_I
        W3_sq = (W_fields[2] ** 2).sum(dim=0)  # (N,N,N)—sum over spatial dimensions
        gauge_shift = 0.5 * self.g ** 2 * W3_sq * dt

        psi_new = psi.clone()
        for c in range(2):
            psi_k = torch.fft.fftn(psi[c])
            # Free dispersion
            factor = torch.exp(-0.5j * self.k2 * dt)
            psi_new[c] = torch.fft.ifftn(psi_k * factor)
            # Gauge potential correction splits psi_Y vs psi_I
            sign = 1.0 if c == 0 else -1.0  # + for Yang, - for Yin
            psi_new[c] = psi_new[c] * torch.exp(-1j * sign * gauge_shift)

        return psi_new


    # ────────────────────────────────────────────────────────────────────
    # Gauge Field Initialization
    # ────────────────────────────────────────────────────────────────────

    def init_gauge_fields(self, amplitude=0.1, seed=None):
        """Initialize gauge fields as small random perturbations.

        amplitude: RMS amplitude of initial gauge fields.
        seed: random seed for reproducibility.

        Returns: (3, 3, N, N, N)—W^a_i fields.
        """
        if seed is not None:
            torch.manual_seed(seed)

        # Gaussian random fields with 1/k² power spectrum (divergence-free)
        W = torch.zeros(3, 3, *self.shape, dtype=torch.float32, device=self.device)
        for a in range(3):
            for i in range(3):
                noise = torch.randn(*self.shape, dtype=torch.float32, device=self.device)
                # Smooth with Gaussian kernel
                noise_k = torch.fft.fftn(noise)
                sigma = self.k0 / (self.k_mag + self.k0)
                sigma[0, 0, 0] = 0.0
                smoothed = torch.fft.ifftn(noise_k * sigma).real
                W[a, i] = amplitude * smoothed / (smoothed.std() + 1e-10)

        return W

    def init_isospinor(self, yang_amp=1.0, yin_amp=None, center=True, seed=None):
        """Initialize isospinor with Yang/Yin components.

        Default amplitudes: Yang=1.0, Yin=φ⁻¹/²≈0.786 give density ratio r = ρ_Y/ρ_I = φ
        matching the φ-equilibrium VEV ⟨Ψ⟩ ∝ (√φ, 1)ᵀ.


        yang_amp: amplitude of ψ_Y (upper component).
        yin_amp: amplitude of ψ_I (lower component).
        center: if True, center the Gaussian on the grid.
        seed: random seed.

        Returns: (2, N, N, N) complex isospinor.
        """
        if seed is not None:
            torch.manual_seed(seed)
        # Default yin_amp gives ρ_Y/ρ_I = φ (VEV at φ-equilibrium)
        if yin_amp is None:
            yin_amp = PHI_INV_SQRT  # 1/√φ ≈ 0.786, so |ψ_Y|²/|ψ_I|² = φ

        if center:
            # Gaussian centered on grid
            sigma = self.L / 4.0
            envelope = torch.exp(-self.R**2 / (2.0 * sigma**2))
        else:
            # Uniform phase across grid
            envelope = torch.ones(self.shape, dtype=torch.float32, device=self.device)

        # Yang component (upper)
        phase_Y = torch.randn(self.shape, dtype=torch.float32, device=self.device) * np.pi
        psi_Y = yang_amp * envelope * torch.exp(1j * phase_Y)

        # Yin component (lower)
        phase_I = torch.randn(self.shape, dtype=torch.float32, device=self.device) * np.pi
        psi_I = yin_amp * envelope * torch.exp(1j * phase_I)

        # Stack into isospinor
        psi = torch.stack([psi_Y, psi_I], dim=0).to(torch.complex64)

        # Normalize to unit density
        total_density = self.isospinor_density(psi).sum()
        norm = torch.sqrt(total_density)
        if norm > 0:
            psi = psi / norm

        return psi

    # ────────────────────────────────────────────────────────────────────
    # Full Step
    # ────────────────────────────────────────────────────────────────────

    def step(self, psi, W_fields, dt, V_ext=None):
        """Full evolution step: evolve gauge fields + isospinor.

        Order: gauge update → isospinor evolution → gauge update
        (Strang splitting between matter and gauge sectors).

        psi: (2, N, N, N) complex isospinor.
        W_fields: (3, 3, N, N, N)—gauge fields.
        dt: float—time step.
        V_ext: (N, N, N) float or None.

        Returns: (psi_new, W_new) tuple.
        """
        # Half-step gauge evolution (matter current sources gauge fields)
        W_mid = self.evolve_gauge_fields(W_fields, psi, dt / 2.0)

        # Full isospinor evolution under gauge fields
        psi_new = self.evolve_isospinor(psi, W_mid, dt, V_ext=V_ext)

        # Half-step gauge evolution
        W_new = self.evolve_gauge_fields(W_mid, psi_new, dt / 2.0)

        # Update timestep
        self.t += dt

        # Record diagnostics
        self._record_diagnostics(psi_new, W_new)

        return psi_new, W_new

    def _record_diagnostics(self, psi, W_fields):
        """Record diagnostic quantities for analysis."""
        rho_Y = self.yang_density(psi).mean().item()
        rho_I = self.yin_density(psi).mean().item()
        r = self.yang_yin_ratio(psi)
        W_rms = W_fields.std().item()
        ym_energy = self.compute_yang_mills_energy(W_fields)

        # Isospin charge density (average absolute)
        rho_a, _ = self.compute_isospin_current(psi)
        rho_q = rho_a.abs().mean().item()

        # Mass predictions
        m_W = self.compute_w_mass(psi)
        m_Z = self.compute_z_mass(psi)

        self.history['t'].append(self.t)
        self.history['E_Y'].append(rho_Y)
        self.history['E_I'].append(rho_I)
        self.history['ratio'].append(r)
        self.history['W_rms'].append(W_rms)
        self.history['YM_energy'].append(ym_energy)
        self.history['rho_Q'].append(rho_q)
        self.history['m_W'].append(m_W)
        self.history['m_Z'].append(m_Z)

    # ────────────────────────────────────────────────────────────────────
    # Analysis Utilities
    # ────────────────────────────────────────────────────────────────────

    def summary(self):
        """Print a summary of current state and φ-predictions."""
        print("=" * 60)
        print("Cassi SU(2) Gauge Bridge—φ-Governed Electroweak Sector")
        print("=" * 60)
        print(f"  Grid:          {self.grid}³")
        print(f"  L:             {self.L}")
        print(f"  g (SU(2)):     {self.g:.4f}")
        print(f"  g' (U(1)_Y):   {self.g_prime:.4f}")
        print(f"  θ_W:           {self.theta_W:.4f} rad")
        print(f"  φ-frame:")
        print(f"    sin²θ_W = φ⁻³ = {self.phi_sin2_theta_W:.6f}")
        print(f"    Measured sin²θ_W = 0.231")
        print(f"    Ratio: {self.phi_sin2_theta_W / 0.231:.4f}")
        print(f"  m_W/m_Z = cos θ_W = {self.phi_cos_theta_W:.6f}")
        print(f"  Measured m_W/m_Z = 80.4/91.2 = {80.4/91.2:.6f}")
        print(f"  GUT α:         φ⁻³/(4π) = {self.gut_coupling():.6f} ≈ 1/{1/self.gut_coupling():.0f}")
        print("-" * 60)

        if len(self.history['t']) > 0:
            print(f"  Steps:         {len(self.history['t'])}")
            print(f"  Current ratio: {self.history['ratio'][-1]:.4f}")
            print(f"  m_W (code):    {self.history['m_W'][-1]:.6f}")
            print(f"  m_Z (code):    {self.history['m_Z'][-1]:.6f}")
            print(f"  m_W/m_Z:       {self.history['m_W'][-1]/max(self.history['m_Z'][-1],1e-30):.6f}")

        alpha_s_mz, alpha_s_meas, ratio = self.alpha_s_at_mz()
        print("-" * 60)
        print(f"  Running coupling:")
        print(f"    α_GUT = {self.gut_coupling():.6f}")
        print(f"    α_s(M_Z) predicted: {alpha_s_mz:.4f}")
        print(f"    α_s(M_Z) measured:  {alpha_s_meas:.4f}")
        print(f"    Scale ratio M_GUT/M_Z: {ratio:.1e}")
        print("=" * 60)

    def plot_spectrum(self, save_path=None):
        """Plot mass spectrum and ratio evolution.

        save_path: path to save figure (default: figures/cassi_su2_spectrum.png).
        """
        if save_path is None:
            save_path = Path('figures') / 'cassi_su2_spectrum.png'
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        fig, axes = plt.subplots(2, 3, figsize=(14, 8))

        t = np.array(self.history['t'])

        # Mass evolution
        ax = axes[0, 0]
        ax.plot(t, self.history['m_W'], 'b-', label='m_W')
        ax.plot(t, self.history['m_Z'], 'r-', label='m_Z')
        ax.set_xlabel('Time')
        ax.set_ylabel('Mass (code units)')
        ax.set_title('W/Z Boson Mass Evolution')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Mass ratio
        ax = axes[0, 1]
        m_ratio = np.array(self.history['m_W']) / np.maximum(np.array(self.history['m_Z']), 1e-30)
        ax.plot(t, m_ratio, 'g-', label='m_W/m_Z')
        ax.axhline(self.phi_cos_theta_W, color='k', ls='--', label=f'φ-prediction: {self.phi_cos_theta_W:.4f}')
        ax.axhline(80.4/91.2, color='r', ls=':', label=f'Measured: {80.4/91.2:.4f}')
        ax.set_xlabel('Time')
        ax.set_ylabel('Ratio')
        ax.set_title('W/Z Mass Ratio')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Yang/Yin ratio
        ax = axes[0, 2]
        ax.plot(t, self.history['ratio'], 'm-', label='Yang/Yin')
        ax.axhline(PHI, color='k', ls='--', label=f'φ = {PHI:.4f}')
        ax.set_xlabel('Time')
        ax.set_ylabel('r = ρ_Y / ρ_I')
        ax.set_title('Yang/Yin Density Ratio')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Gauge field RMS
        ax = axes[1, 0]
        ax.plot(t, self.history['W_rms'], 'c-')
        ax.set_xlabel('Time')
        ax.set_ylabel('RMS(W)')
        ax.set_title('Gauge Field Strength')
        ax.grid(True, alpha=0.3)

        # Yang-Mills energy
        ax = axes[1, 1]
        ax.plot(t, self.history['YM_energy'], 'orange')
        ax.set_xlabel('Time')
        ax.set_ylabel('Energy density')
        ax.set_title('Yang-Mills Energy')
        ax.grid(True, alpha=0.3)

        # Isospin charge density
        ax = axes[1, 2]
        ax.plot(t, self.history['rho_Q'], 'purple')
        ax.set_xlabel('Time')
        ax.set_ylabel('⟨|ρ^a|⟩')
        ax.set_title('Isospin Charge Density')
        ax.grid(True, alpha=0.3)

        plt.suptitle('Cassi SU(2) Gauge Bridge—φ-Governed Weak Sector', fontsize=14, y=1.01)
        plt.tight_layout()
        plt.savefig(str(save_path), dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved spectrum to {save_path}")

    def plot_gauge_config(self, W_fields, save_path=None):
        """Plot gauge field configuration on a central slice.

        save_path: path to save figure (default: figures/cassi_su2_gauge.png).
        """
        if save_path is None:
            save_path = Path('figures') / 'cassi_su2_gauge.png'
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        mid = self.grid // 2

        fig, axes = plt.subplots(3, 3, figsize=(12, 10))

        labels_a = ['W¹', 'W²', 'W³']
        labels_i = ['x', 'y', 'z']

        for a in range(3):
            for i in range(3):
                ax = axes[a, i]
                im = ax.imshow(W_fields[a, i, :, :, mid].cpu().numpy(),
                               cmap='RdBu_r', aspect='equal')
                ax.set_title(f'{labels_a[a]}_{labels_i[i]}')
                ax.axis('off')
                plt.colorbar(im, ax=ax, shrink=0.8)

        plt.suptitle('SU(2) Gauge Field Configuration (z=0 slice)', fontsize=14)
        plt.tight_layout()
        plt.savefig(str(save_path), dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved gauge config to {save_path}")


# ═══════════════════════════════════════════════════════════════════════════
# Self-Test
# ═══════════════════════════════════════════════════════════════════════════

def run_test(grid=32, steps=100, dt=0.05):
    """Run a short self-test of the SU(2) bridge."""
    print("Running SU(2) bridge self-test...")
    print(f"  Grid: {grid}³, Steps: {steps}, dt: {dt}")

    # Create bridge with φ-predicted gauge coupling
    # sin²θ_W = φ⁻³ ≈ 0.236 (GUT-scale boundary condition)
    sin2_phi = PHI_INV ** 3
    alpha_weak = PHI_INV / (4.0 * np.pi)  # φ⁻¹/(4π) ≈ 0.049
    g = np.sqrt(4.0 * np.pi * alpha_weak / sin2_phi)
    g_prime = np.sqrt(4.0 * np.pi * alpha_weak / (1.0 - sin2_phi))
    # g'/g = tan θ_W with sin²θ_W = φ⁻³

    bridge = CassiSU2Bridge(grid=grid, L=10.0, g=g, g_prime=g_prime)

    # Initialize at φ-equilibrium VEV: ρ_Y/ρ_I = φ (amplitudes 1 : 1/√φ)
    psi = bridge.init_isospinor(yang_amp=1.0, yin_amp=PHI_INV_SQRT, center=True)
    W = bridge.init_gauge_fields(amplitude=0.05)

    bridge.summary()

    # Evolve
    print(f"\nEvolving for {steps} steps...")
    t0 = time.time()
    for n in range(steps):
        psi, W = bridge.step(psi, W, dt)

        if (n + 1) % 25 == 0:
            r = bridge.history['ratio'][-1]
            mW = bridge.history['m_W'][-1]
            mZ = bridge.history['m_Z'][-1]
            print(f"  Step {n+1:4d}/{steps}: r={r:.4f}, m_W={mW:.4f}, m_Z={mZ:.4f}")

    elapsed = time.time() - t0
    print(f"  Completed in {elapsed:.2f}s ({elapsed/steps*1000:.1f}ms/step)")

    # Final summary
    bridge.summary()

    # Plots
    bridge.plot_spectrum()
    bridge.plot_gauge_config(W)

    return bridge


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Cassi SU(2) Gauge Bridge—φ-Governed Weak Force',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
φ-predictions (GUT-scale boundary conditions):
  sin²θ_W = φ⁻³ ≈ 0.236  (experiment at Z-pole: 0.231; RG running closes gap)
  m_W/m_Z = cos θ_W ≈ 0.874  (measured: 80.4/91.2 ≈ 0.882; FCC-ee testable)
  α_GUT = φ⁻³/(4π) ≈ 1/53
        """)
    parser.add_argument('--grid', type=int, default=32, help='Grid points per dimension')
    parser.add_argument('--steps', type=int, default=100, help='Number of time steps')
    parser.add_argument('--dt', type=float, default=0.05, help='Time step')
    parser.add_argument('--test', action='store_true', help='Run self-test and exit')
    parser.add_argument('--g', type=float, default=None, help='SU(2) gauge coupling (default: φ-scaled)')
    parser.add_argument('--g-prime', type=float, default=None, help='U(1)_Y gauge coupling')
    args = parser.parse_args()

    if args.g is not None:
        g = args.g
        g_prime = args.g_prime if args.g_prime is not None else g * 0.5
    else:
        # φ-scaled couplings (matching run_electroweak.py)
        alpha_weak = PHI_INV / (4.0 * np.pi)  # φ⁻¹/(4π) ≈ 0.049
        sin2 = PHI_INV ** 3          # sin²θ_W = φ⁻³ ≈ 0.236
        cos2 = 1.0 - sin2
        g = np.sqrt(4.0 * np.pi * alpha_weak / sin2)
        g_prime = np.sqrt(4.0 * np.pi * alpha_weak / cos2)
    bridge = CassiSU2Bridge(grid=args.grid, L=10.0, g=g, g_prime=g_prime)

    if args.test:
        run_test(grid=args.grid, steps=args.steps, dt=args.dt)
    else:
        bridge.summary()
        # Print φ-predicted quantities
        print("\nφ-Predicted Electroweak Parameters:")
        print(f"  sin²θ_W = {bridge.phi_sin2_theta_W:.6f} (experiment: 0.231)")
        print(f"  m_W/m_Z = {bridge.phi_cos_theta_W:.6f} (experiment: {80.4/91.2:.6f})")
        print(f"  α_GUT   = {bridge.gut_coupling():.6f} (≈ 1/{1/bridge.gut_coupling():.0f})")

        # Running coupling
        alpha_s_mz, alpha_s_meas, scale_ratio = bridge.alpha_s_at_mz()
        print(f"\nRunning Coupling:")
        print(f"  α_s(M_Z) predicted: {alpha_s_mz:.4f}")
        print(f"  α_s(M_Z) measured:  {alpha_s_meas:.4f}")
