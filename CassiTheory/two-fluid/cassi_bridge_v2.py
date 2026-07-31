#!/usr/bin/env python3
"""
Cassi Bridge v2: Two-Fluid-Informed Hydrogen ↔ Cosmology Bridge
===============================================================

Single Schrödinger-Poisson engine upgraded with lessons from:
- N-body solver:   Qi-gated source terms, gravitational saturation
- Two-fluid cosmo: φ-damped density memory, stress-energy Hubble

The same code path spans both limits:
- Atomic:        M=1, fixed proton Coulomb well, imaginary time → hydrogen 1s
- Cosmological:  M≫1, self-consistent gravity, expanding background → LSS
- Molecular:     H₂⁺ two-center bond via LCAO + imaginary-time relaxation
- DFT:           Multi-electron atoms via LDA exchange-correlation SCF

Key mechanisms (all controlled by φ ≈ 1.618):
  1. Qi-gated entropic source:  S = (1-q)·ρ + q·[ρ + α·s(δ)]
  2. φ-damped density memory:   ρ_mem ← (1-φ⁻¹)·ρ_mem + φ⁻¹·ρ
  3. Stress-energy Hubble:      H = H_empty + H_conv + H_struct(q)
  4. N-body gravitational saturation: caps ∇Φ at σ_thresh
  5. Yang dark-energy oscillation:    φ-periodic source modulation
  6. Holographic information bound:   entropy-triggered smoothing
  7. Gravitomagnetic sector:  j → A → B² in Poisson source
  8. EM gauge sector:         j → A_EM → |A|²/(2M) diamagnetic barrier
  9. DFT/LDA:                 Hartree + exchange-correlation for multi-e⁻ atoms

Usage:
    python two-fluid/cassi_bridge_v2.py --mode atomic
    python two-fluid/cassi_bridge_v2.py --mode cosmos
    python two-fluid/cassi_bridge_v2.py --mode h2plus --scan-bonds
    python two-fluid/cassi_bridge_v2.py --mode dft --Z 2
    python two-fluid/cassi_bridge_v2.py --mode all --grid 96
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


# ═══════════════════════════════════════════════════════════════════════════
# Unified Bridge Solver
# ═══════════════════════════════════════════════════════════════════════════

class CassiBridgeV2:
    """Schrödinger-Poisson bridge with two-fluid and n-body insights.

    The wavefunction ψ(r,t) evolves under:
        i ∂_t ψ = [ -∇²/(2M) + V_ext + g|ψ|² + Φ[ρ] ] ψ

    where Φ is the Cassi information potential computed from the density
    ρ = |ψ|² with Qi-gated entropic corrections, holographic smoothing,
    and Yang dark-energy oscillation.

    Parameters
    ----------
    grid : int
        Grid points per dimension (N³ total).
    L : float
        Physical box size.
    mass : float
        Effective mass M. M=1 → atomic (quantum pressure active).
        M≫1 → cosmological (semi-classical dust limit).
    alpha_disp : float
        Scale-dependent dispersion exponent. 1.0 = standard gravity.
        1-φ⁻¹ ≈ 0.382 → enhanced small-scale gravity.
    alpha_yin : float
        Yin entropic coupling strength. 0 = off.
    yin_mode : str
        'relative' (softens structure) or 'signed' (amplifies structure).
    yang_amp : float
        Yang dark-energy oscillation amplitude.
    yang_period : float
        Yang oscillation period. Default = φ⁻¹ ≈ 0.618.
    g : float
        Nonlinear self-interaction strength (atomic self-focusing).
    phi_damp : bool
        Enable φ-damped propagation: ψ ← φ⁻¹·ψ_old + (1-φ⁻¹)·ψ_new.
    qi_gate : bool
        Enable Qi-gated source terms.
    qi_memory : bool
        Enable φ-damped density memory for Qi coherence.
    qi_tau : float
        Memory time constant. Default = φ⁻¹.
    grav_sigma : float
        N-body saturation scale for |∇Φ|. 0 = off.
    holographic : bool
        Enable holographic information bound smoothing.
    eta : float
        Holographic bound coefficient.
    beta : float
        Smoothing scale exponent.
    expanding : bool
        Enable expanding background.
    H0 : float
        Hubble constant at a=1.
    omega_m : float
        Matter density fraction (LCDM).
    omega_lambda : float
        Dark energy density fraction (LCDM).
    hubble_mode : str
        'friedmann' (LCDM) or 'stress_energy' (Cassi-native).
    device : str or torch.device
        Compute device.
    """
    def __init__(self, grid=64, L=20.0, mass=1.0,
                 alpha_disp=1.0, v0=1.0,
                 alpha_yin=0.0, yin_mode='none',
                 yang_amp=0.0, yang_period=None,
                 g=0.0, phi_damp=False,
                 qi_gate=False, qi_memory=False, qi_tau=None,
                 grav_sigma=0.0,
                 holographic=False, eta=0.004, beta=1.0,
                 alpha_mag=0.0, alpha_em=0.0,
                 expanding=False, H0=0.05, omega_m=0.3, omega_lambda=0.7,
                 hubble_mode='friedmann',
                 phi_gravity=False,
                 kinetic_mode='schrodinger',
                 device=None):
        # Grid
        self.grid = grid
        self.L = L
        self.dim = 3
        self.shape = (grid, grid, grid)
        self.dx = L / grid
        self.dV = self.dx ** 3
        self.N_cells = grid ** 3

        # Physics
        self.mass = mass
        self.alpha_disp = alpha_disp
        self.v0 = v0
        self.alpha_yin = alpha_yin
        self.yin_mode = yin_mode
        self.yang_amp = yang_amp
        self.yang_period = yang_period if yang_period is not None else PHI_INV
        self.g = g
        self.phi_damp = phi_damp
        self.qi_gate = qi_gate
        self.qi_memory = qi_memory
        self.qi_tau = qi_tau if qi_tau is not None else PHI_INV
        self.grav_sigma = grav_sigma
        self.holographic = holographic
        self.eta = eta
        self.beta = beta
        self.alpha_mag = alpha_mag
        self.alpha_em = alpha_em
        self.phi_gravity = phi_gravity
        self.kinetic_mode = kinetic_mode

        # Expansion
        self.expanding = expanding
        self.H0 = H0
        self.omega_m = omega_m
        self.omega_lambda = omega_lambda
        self.hubble_mode = hubble_mode

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

        # Scale-dependent dispersion kernel
        with torch.no_grad():
            k_ratio = self.k_mag.clone()
            k_ratio[0, 0, 0] = self.k0
            self.v2_k = v0**2 * (k_ratio / self.k0) ** (2.0 * (alpha_disp - 1.0))
            self.v2_k[0, 0, 0] = 1.0

        # ── Real-space grid ─────────────────────────────────────────────
        x = torch.linspace(-L/2, L/2, grid, device=self.device)
        self.X, self.Y, self.Z = torch.meshgrid(x, x, x, indexing='ij')
        self.R = torch.sqrt(self.X**2 + self.Y**2 + self.Z**2)

        # ── State ───────────────────────────────────────────────────────
        self.a = 1.0
        self.H = 0.0
        self._H_smooth = torch.tensor(0.0, device=self.device)
        self.tau_phys = 0.0
        self.rho_memory = None   # φ-damped density EMA
        self.eps_sq_memory = None  # per-cell Qi memory
        self.q_mean = 0.0
        self.B_rms = 0.0    # RMS magnetic field
        self.B2_mean = 0.0  # mean magnetic energy density
        self.A2_mean = 0.0  # mean EM vector-potential squared
        self.A_rms = 0.0    # RMS EM vector potential

        # Pre-allocate FFT buffers
        self._tmp_k = torch.zeros(self.shape, dtype=torch.complex64, device=self.device)
        self._tmp_r = torch.zeros(self.shape, dtype=torch.float32, device=self.device)

        # Dirac kinetic mode setup
        if self.kinetic_mode == 'dirac':
            self._init_dirac()

    def _init_dirac(self):
        """Precompute Dirac matrices and k-space helpers for relativistic mode."""
        self.c = 137.035999084  # speed of light in atomic units (1/α)
        self.spinor_dim = 4

        # Pauli matrices
        I2 = torch.eye(2, dtype=torch.complex64, device=self.device)
        O2 = torch.zeros(2, 2, dtype=torch.complex64, device=self.device)
        sx = torch.tensor([[0, 1], [1, 0]], dtype=torch.complex64, device=self.device)
        sy = torch.tensor([[0, -1j], [1j, 0]], dtype=torch.complex64, device=self.device)
        sz = torch.tensor([[1, 0], [0, -1]], dtype=torch.complex64, device=self.device)

        def _alpha(s):
            top = torch.cat([O2, s], dim=1)
            bot = torch.cat([s, O2], dim=1)
            return torch.cat([top, bot], dim=0)

        self.alpha_x = _alpha(sx)
        self.alpha_y = _alpha(sy)
        self.alpha_z = _alpha(sz)

        # β = [[I, 0], [0, -I]]  (4×4)
        top = torch.cat([I2, O2], dim=1)
        bot = torch.cat([O2, -I2], dim=1)
        self.beta_mat = torch.cat([top, bot], dim=0)

        # σ_x, σ_y, σ_z stored for spinor analysis
        self.sigma_x = sx
        self.sigma_y = sy
        self.sigma_z = sz

    @staticmethod
    def _get_density(psi):
        """Return total density (sum over spinor components if 4-spinor)."""
        if psi.dim() == 4 and psi.shape[0] == 4:
            return (torch.abs(psi) ** 2).sum(dim=0)
        return torch.abs(psi) ** 2

    # ────────────────────────────────────────────────────────────────────
    # Qi Coherence (from n-body work)
    # ────────────────────────────────────────────────────────────────────

    def qi_coherence(self, rho):
        """Compute Qi coherence q from density field.

        q = M / (M + φ⁻² + ε²)
        where M = ρ² (field power) and ε² = (ρ - ρ_mem)² (deviation from memory).

        Returns (q, eps_sq_eff, q_mean).
        """
        M_qi = rho ** 2

        if self.rho_memory is not None:
            eps_sq = (rho - self.rho_memory) ** 2
        else:
            eps_sq = torch.zeros_like(rho)

        # Per-cell EMA memory (optional temporal inertia)
        if self.qi_memory:
            if self.eps_sq_memory is None:
                self.eps_sq_memory = torch.zeros_like(eps_sq)
            self.eps_sq_memory = (
                (1.0 - self.qi_tau) * self.eps_sq_memory
                + self.qi_tau * eps_sq
            )
            eps_sq_eff = self.eps_sq_memory
        else:
            eps_sq_eff = eps_sq

        q = M_qi / (M_qi + PHI_INV2 + eps_sq_eff + 1e-30)
        q_mean = q.mean()

        return q, eps_sq_eff, q_mean

    # ────────────────────────────────────────────────────────────────────
    # Entropic Source (from bridge theory §3.2)
    # ────────────────────────────────────────────────────────────────────

    def entropic_source(self, delta, mode='relative'):
        """Yin information source s(δ) from overdensity field.

        - relative: s = (1+δ)ln(1+δ) - δ     (softens structure)
        - signed:   s = sign(δ)·ln(1+|δ|)    (amplifies structure)
        """
        if mode == 'relative':
            safe = torch.clamp(1.0 + delta, min=1e-6)
            return safe * torch.log(safe) - delta
        elif mode == 'signed':
            return torch.sign(delta) * torch.log(1.0 + torch.abs(delta))
        else:
            return torch.zeros_like(delta)

    # ────────────────────────────────────────────────────────────────────
    # Field Information & Holographic Bound (bridge theory §3.4)
    # ────────────────────────────────────────────────────────────────────

    def field_information(self, rho):
        """KL divergence of normalized density from uniformity."""
        rho_sum = rho.sum()
        if rho_sum <= 0:
            return 0.0
        p = rho / rho_sum
        q = 1.0 / self.N_cells
        return float((p * torch.log(p / q)).sum())

    def gaussian_smooth(self, rho, R_h):
        """Gaussian smoothing at scale R_h."""
        rho_k = torch.fft.fftn(rho)
        kernel = torch.exp(-0.5 * (self.k_mag * R_h) ** 2)
        return torch.fft.ifftn(rho_k * kernel).real

    # ────────────────────────────────────────────────────────────────────
    # Magnetic / Gravitomagnetic Sector
    # ────────────────────────────────────────────────────────────────────

    def compute_current(self, psi):
        """Probability current j = Im(ψ*∇ψ).

        In the Madelung representation ψ = √ρ e^{iS}, the current is j = ρ ∇S = ρ u.
        This is the gravitomagnetic source—mass current in GR weak-field limit.
        """
        psi_k = torch.fft.fftn(psi)
        grad_x = torch.fft.ifftn(1j * self.kx * psi_k)
        grad_y = torch.fft.ifftn(1j * self.ky * psi_k)
        grad_z = torch.fft.ifftn(1j * self.kz * psi_k)
        jx = (torch.conj(psi) * grad_x).imag
        jy = (torch.conj(psi) * grad_y).imag
        jz = (torch.conj(psi) * grad_z).imag
        return jx, jy, jz

    def vector_potential(self, jx, jy, jz):
        """Solve ∇²A = -j for the gravitomagnetic vector potential.

        In the weak-field GR limit: ∇² h_{0i} = -16πG j_i.
        Here we absorb constants into alpha_mag.
        Coulomb gauge: ∇·A = 0 (enforced by dropping k=0 mode).
        """
        jx_k = torch.fft.fftn(jx); jx_k[0, 0, 0] = 0.0
        jy_k = torch.fft.fftn(jy); jy_k[0, 0, 0] = 0.0
        jz_k = torch.fft.fftn(jz); jz_k[0, 0, 0] = 0.0

        Ax = torch.fft.ifftn(jx_k / self.k2_safe).real
        Ay = torch.fft.ifftn(jy_k / self.k2_safe).real
        Az = torch.fft.ifftn(jz_k / self.k2_safe).real
        return Ax, Ay, Az

    def magnetic_field(self, Ax, Ay, Az):
        """B = ∇×A and magnetic energy density B²/2."""
        Ax_k = torch.fft.fftn(Ax)
        Ay_k = torch.fft.fftn(Ay)
        Az_k = torch.fft.fftn(Az)

        Bx = torch.fft.ifftn(1j * (self.ky * Az_k - self.kz * Ay_k)).real
        By = torch.fft.ifftn(1j * (self.kz * Ax_k - self.kx * Az_k)).real
        Bz = torch.fft.ifftn(1j * (self.kx * Ay_k - self.ky * Ax_k)).real

        B2 = Bx**2 + By**2 + Bz**2
        return B2  # magnetic energy density × 2 (B² = 2 × energy density)

    def current_divergence(self, jx, jy, jz):
        """∇·j—mass conservation diagnostic."""
        jx_k = torch.fft.fftn(jx)
        jy_k = torch.fft.fftn(jy)
        jz_k = torch.fft.fftn(jz)
        div_j = torch.fft.ifftn(1j * (self.kx * jx_k + self.ky * jy_k + self.kz * jz_k)).real
        return float(div_j.std())

    # ────────────────────────────────────────────────────────────────────
    # DFT: Hartree and Exchange-Correlation (LDA)
    # ────────────────────────────────────────────────────────────────────

    def compute_hartree(self, rho):
        """Hartree potential V_H from electron density: ∇²V_H = 4πρ."""
        rho_k = torch.fft.fftn(rho)
        rho_k[0, 0, 0] = 0.0
        V_H_k = 4.0 * np.pi * rho_k / self.k2_safe
        return torch.fft.ifftn(V_H_k).real

    @staticmethod
    def _pw92_correlation(rho):
        """PW92 LDA correlation: returns (Vc, rho*ec)."""
        rho_safe = torch.clamp(rho, min=1e-30)
        A_c = 0.031090690869654895034
        a1 = 0.21370; b1 = 7.5957; b2 = 3.5876; b3 = 1.6382; b4 = 0.49294
        rs = (3.0 / (4.0 * np.pi * rho_safe)) ** (1.0 / 3.0)
        rs_s = torch.clamp(rs, min=1e-12)
        sqrt_rs = torch.sqrt(rs_s)
        D = 2.0 * A_c * (b1 * sqrt_rs + b2 * rs_s + b3 * rs_s * sqrt_rs + b4 * rs_s ** 2)
        D = torch.clamp(D, min=1e-30)
        ec = -2.0 * A_c * (1.0 + a1 * rs_s) * torch.log(1.0 + 1.0 / D)
        dD = 2.0 * A_c * (b1/(2*sqrt_rs) + b2 + 1.5*b3*sqrt_rs + 2.0*b4*rs_s)
        dec = -2.0*A_c*a1 * torch.log(1+1/D) + 2.0*A_c*(1+a1*rs_s)*dD/(D*(D+1))
        Vc = ec + (rs_s / 3.0) * dec
        return Vc, rho_safe * ec

    @staticmethod
    def lda_xc_potential(rho):
        """LDA exchange-correlation potential: V_x(Dirac) + V_c(PW92)."""
        Cx = (3.0 / np.pi) ** (1.0 / 3.0)
        rho_safe = torch.clamp(rho, min=1e-30)
        Vx = -Cx * rho_safe ** (1.0 / 3.0)
        Vc, _ = CassiBridgeV2._pw92_correlation(rho)
        return Vx + Vc

    @staticmethod
    def lda_xc_energy(rho, dV):
        """LDA exchange-correlation energy per volume element."""
        Cx = (3.0 / np.pi) ** (1.0 / 3.0)
        rho_safe = torch.clamp(rho, min=1e-30)
        ex = -0.75 * Cx * rho_safe ** (4.0 / 3.0)
        _, rho_ec = CassiBridgeV2._pw92_correlation(rho)
        return float(torch.sum(ex + rho_ec) * dV)

    def _compute_gradient(self, rho):
        """Grad(rho) and |grad(rho)|^2 via spectral derivatives."""
        rho_k = torch.fft.fftn(rho)
        gx = torch.fft.ifftn(1j * self.kx * rho_k).real
        gy = torch.fft.ifftn(1j * self.ky * rho_k).real
        gz = torch.fft.ifftn(1j * self.kz * rho_k).real
        return gx, gy, gz, gx**2 + gy**2 + gz**2

    def pbe_exchange_potential(self, rho):
        """PBE exchange potential: V_local + V_gradient."""
        Cx = (3.0/np.pi)**(1.0/3.0); kappa = 0.804; mu = 0.21951
        gx, gy, gz, gsq = self._compute_gradient(rho)
        rho_s = torch.clamp(rho, min=1e-30)
        kF = (3.0*np.pi**2 * rho_s)**(1.0/3.0)
        s = torch.sqrt(gsq + 1e-30) / (2.0*kF*rho_s + 1e-20)
        s2 = s**2
        denom = 1.0 + mu*s2/kappa
        Fx = 1.0 + kappa - kappa/denom
        Fxp = 2.0*mu*s / (denom**2 + 1e-30)

        V_local = torch.zeros_like(rho)
        m = rho_s > 1e-10
        V_local[m] = -4.0/3.0 * Cx * rho_s[m]**(1.0/3.0) * (Fx[m] - s[m]*Fxp[m])

        A = torch.zeros_like(rho)
        mg = gsq > 1e-20
        A[mg] = Cx * rho_s[mg]**(4.0/3.0) * Fxp[mg] * s[mg] / (gsq[mg] + 1e-30)
        Vx_k = torch.fft.fftn(A*gx); Vy_k = torch.fft.fftn(A*gy); Vz_k = torch.fft.fftn(A*gz)
        V_grad = torch.fft.ifftn(1j*(self.kx*Vx_k + self.ky*Vy_k + self.kz*Vz_k)).real
        return V_local + V_grad

    def pbe_exchange_energy(self, rho, dV):
        """PBE exchange energy."""
        Cx = (3.0/np.pi)**(1.0/3.0); kappa = 0.804; mu = 0.21951
        _, _, _, gsq = self._compute_gradient(rho)
        rho_s = torch.clamp(rho, min=1e-30)
        kF = (3.0*np.pi**2 * rho_s)**(1.0/3.0)
        s = torch.sqrt(gsq + 1e-30) / (2.0*kF*rho_s + 1e-20)
        denom = 1.0 + mu*s**2/kappa
        Fx = 1.0 + kappa - kappa/denom
        ex = torch.zeros_like(rho)
        m = rho_s > 1e-10
        ex[m] = -Cx * rho_s[m]**(4.0/3.0) * Fx[m]
        return float(ex.sum() * dV)

    def pbe_xc_potential(self, rho):
        """PBE exchange + PW92 correlation potential."""
        Vx = self.pbe_exchange_potential(rho)
        Vc, _ = self._pw92_correlation(rho)
        return Vx + Vc

    def pbe_xc_energy(self, rho, dV):
        """PBE exchange + PW92 correlation energy."""
        Ex = self.pbe_exchange_energy(rho, dV)
        _, rho_ec = self._pw92_correlation(rho)
        Ec = float(rho_ec.sum() * dV)
        return Ex + Ec


    # ────────────────────────────────────────────────────────────────────
    # Unified Cassi Source
    # ────────────────────────────────────────────────────────────────────

    def build_source(self, rho, tau=0.0, rho_mag=None):
        """Build the effective source S[ρ] for the Poisson equation.

        The Qi gate modulates the entropic correction:
        - High coherence (q→1): entropic term suppressed → standard gravity
        - Low coherence (q→0): full entropic correction active
        """
        rho_bar = rho.mean()

        # Baseline: matter density
        S = rho.clone()

        # Qi-gated Yin entropic source
        if self.alpha_yin != 0.0 and self.yin_mode != 'none' and rho_bar > 0:
            delta = rho / rho_bar - 1.0
            s = self.entropic_source(delta, mode=self.yin_mode)

            if self.qi_gate:
                q, _, q_mean_tensor = self.qi_coherence(rho)
                self.q_mean = float(q_mean_tensor.item())
                gate = 1.0 - q  # low coherence → full entropic correction
            else:
                gate = torch.ones_like(rho)

            S = S + gate * self.alpha_yin * s * rho_bar

        # Yang dark-energy oscillation
        if self.yang_amp != 0.0:
            factor = 1.0 + self.yang_amp * 0.5 * (
                1.0 + torch.sin(torch.tensor(2.0 * np.pi * tau / self.yang_period,
                                             device=self.device))
            )
            S = S * factor

        # Magnetic/gravitomagnetic pressure: B²/2 sourced by current j
        # Adds to gravitational source as ρ_mag = α_mag · B²/2
        # Physically: magnetic fields gravitate (stress-energy tensor)
        if rho_mag is not None and self.alpha_mag > 0:
            S = S + self.alpha_mag * rho_mag

        # Holographic bound: smooth if information exceeds area bound
        if self.holographic:
            info = self.field_information(S)
            I_max = self.eta * (self.N_cells ** (2.0 / self.dim))
            if info > I_max:
                R_h = self.dx * ((info / I_max) ** self.beta)
                S = self.gaussian_smooth(S, R_h)

        return S

    # ────────────────────────────────────────────────────────────────────
    # Potential (with N-body saturation)
    # ────────────────────────────────────────────────────────────────────

    def potential(self, rho, tau=0.0, rho_mag=None, A2_em=None):
        """Compute gravitational/information potential Φ from density.

        Φ_k = -Ŝ_k / [v₀² (k/k₀)^{2(α-1)} k²]

        With N-body saturation: softens |∇Φ| when gradients exceed σ.

        When phi_gravity is True, the Poisson source is amplified by
        G_eff(q)/G_N = 1 + (φ-1)·q, where Qi coherence q ∈ [0,1].
        """
        S = self.build_source(rho, tau=tau, rho_mag=rho_mag)
        S_hat = torch.fft.fftn(S)
        S_hat[0, 0, 0] = 0.0  # remove mean

        # φ-enhanced G_eff(q) coupling (Pillar 2)
        if self.phi_gravity:
            if self.qi_gate and hasattr(self, 'q_mean') and self.q_mean > 0:
                q_val = self.q_mean
            else:
                # Compute q from density contrast
                rho_bar = rho.mean()
                if rho_bar > 0:
                    delta = rho / rho_bar - 1.0
                    delta_rms = float((delta ** 2).mean().sqrt())
                    q_val = 1.0 / (1.0 + delta_rms + 1e-12)
                else:
                    q_val = 0.0
            # G_eff(q) / G_N = 1 + (φ-1)·q
            eff_factor = 1.0 + (PHI - 1.0) * q_val
            S_hat = S_hat * eff_factor

        # Scale-dependent Poisson kernel
        denom = self.v2_k * self.k2_safe
        Phi_hat = -S_hat / denom
        Phi = torch.fft.ifftn(Phi_hat).real

        # N-body gradient saturation (from nbody work)
        if self.grav_sigma > 0:
            grad_x = torch.fft.ifftn(1j * self.kx * Phi_hat).real
            grad_y = torch.fft.ifftn(1j * self.ky * Phi_hat).real
            grad_z = torch.fft.ifftn(1j * self.kz * Phi_hat).real
            f2 = grad_x**2 + grad_y**2 + grad_z**2
            sf = f2 / (f2 + self.grav_sigma**2 + 1e-10)

            # Apply saturation in Fourier space: Φ_sat = ifft(sf_hat ⊛ Φ_hat)
            # Approximate: multiply in real space then re-transform
            # (exact would require convolution; this is first-order)
            Phi_sat_hat = torch.fft.fftn(sf * Phi)
            Phi_sat_hat[0, 0, 0] = 0.0
            Phi = torch.fft.ifftn(Phi_sat_hat).real

        # Scale by 1/a in comoving coordinates
        if self.expanding:
            Phi = Phi / self.a

        # Add EM diamagnetic potential: alpha_em * |A|^2 / (2*M)
        if A2_em is not None and self.alpha_em > 0:
            Phi = Phi + self.alpha_em * A2_em / (2.0 * self.mass)

        return Phi

    # ────────────────────────────────────────────────────────────────────
    # Hubble Parameter (from two-fluid solver)
    # ────────────────────────────────────────────────────────────────────

    def _update_hubble(self, rho):
        """Compute Hubble parameter from density field.

        Modes:
          'friedmann':     H = H₀ √(ρ_tot)   (LCDM-like)
          'stress_energy': H = H_empty + H_conv + H_struct  (Cassi-native)
        """
        if not self.expanding:
            self.H = 0.0
            return

        rho_mean = float(rho.mean())

        if self.hubble_mode == 'stress_energy':
            H_empty = (self.H0 / 3.0) * PHI_INV2
            if self.qi_gate:
                q_val = self.q_mean
            else:
                delta_std = float(((rho / (rho.mean() + 1e-12) - 1.0) ** 2).mean().sqrt())
                q_val = 1.0 / (1.0 + delta_std)

            H_conv = self.H0 * (1.0 - q_val)
            delta_rms = float(((rho / (rho_mean + 1e-12) - 1.0) ** 2).mean().sqrt())
            H_struct = self.H0 * 0.1 * delta_rms
            H_raw = H_empty + H_conv + H_struct
        else:
            H_raw = self.H0 * np.sqrt(max(rho_mean, 1e-12))

        # Smooth and clamp
        h_smooth = 0.1
        prev = float(self._H_smooth.item())
        self._H_smooth = torch.tensor(
            (1.0 - h_smooth) * prev + h_smooth * H_raw,
            device=self.device
        )
        self.H = float(self._H_smooth.item())

    def _update_expansion(self, dt):
        """Advance scale factor a(t)."""
        if not self.expanding:
            return
        self.H = max(min(self.H, 1.0), -1.0)  # clamp
        self.a = self.a * np.exp(self.H * dt)
        self.tau_phys += dt

    # ────────────────────────────────────────────────────────────────────
    # Split-Step Propagation
    # ────────────────────────────────────────────────────────────────────

    def kinetic_propagator(self, psi, dt, imaginary=False):
        """Kinetic step in Fourier space.

        Schrödinger: exp(-i k² dt / (2 M a²))
        Dirac:      exp(-i H_D dt)  where H_D = c α·k + β c²
        """
        if self.kinetic_mode == 'dirac':
            return self._kinetic_propagator_dirac(psi, dt, imaginary)
        # Standard Schrödinger propagator
        psi_k = torch.fft.fftn(psi)
        a2 = self.a ** 2 if self.expanding else 1.0
        exponent = -0.5 * self.k2 * dt / (self.mass * a2)
        factor = torch.exp(exponent) if imaginary else torch.exp(1j * exponent)
        return torch.fft.ifftn(psi_k * factor)

    def potential_propagator(self, psi, Phi, dt, imaginary=False):
        """Potential step: exp(-i (Φ + g|ψ|²) dt) in real space.

        For Dirac mode, the scalar potential couples identically to all 4
        spinor components. The total density is summed over components.
        """
        rho = self._get_density(psi)
        V_eff = Phi + self.g * rho
        factor = torch.exp(-V_eff * dt) if imaginary else torch.exp(-1j * V_eff * dt)
        return psi * factor

    def _kinetic_propagator_dirac(self, psi, dt, imaginary=False):
        """Dirac kinetic step: exp(-i H_D dt) in k-space.

        H_D(k) = c (α_x k_x + α_y k_y + α_z k_z) + β c²
        Since H_D² = E_k² I₄, the exact matrix exponential is:
          real time:  exp(-i H_D dt) = cos(E dt) I - i sin(E dt) H_D/E
          imag time:  exp(-H_D dt)   = cosh(E dt) I - sinh(E dt) H_D/E
        """
        c = self.c if self.c is not None else 137.036
        kx, ky, kz = self.kx, self.ky, self.kz
        k2 = self.k2
        E = torch.sqrt(c ** 2 * k2 + c ** 4)  # (N, N, N)

        # FFT each spinor component separately
        psi_k = torch.fft.fftn(psi, dim=(1, 2, 3))  # (4, N, N, N)
        p0, p1, p2, p3 = psi_k[0], psi_k[1], psi_k[2], psi_k[3]

        # H_D ψ in k-space (component-wise, avoids 4×4 matrix construction)
        # H_D ψ =
        #   c(k_z ψ₂ + (k_x - i k_y) ψ₃) + c² ψ₀                    [comp 0]
        #   c((k_x + i k_y) ψ₂ - k_z ψ₃) + c² ψ₁                    [comp 1]
        #   c(k_z ψ₀ + (k_x - i k_y) ψ₁) - c² ψ₂                    [comp 2]
        #   c((k_x + i k_y) ψ₀ - k_z ψ₁) - c² ψ₃                    [comp 3]
        h0 = c * (kz * p2 + (kx - 1j * ky) * p3) + c ** 2 * p0
        h1 = c * ((kx + 1j * ky) * p2 - kz * p3) + c ** 2 * p1
        h2 = c * (kz * p0 + (kx - 1j * ky) * p1) - c ** 2 * p2
        h3 = c * ((kx + 1j * ky) * p0 - kz * p1) - c ** 2 * p3

        E_inv = E.clone()
        E_inv[E_inv == 0] = 1.0

        if imaginary:
            # exp(-H_D dt) = cosh(E dt) I - sinh(E dt) H_D / E
            ch = torch.cosh(E * dt)
            sh = torch.sinh(E * dt) / E_inv
            new_p0 = ch * p0 - sh * h0
            new_p1 = ch * p1 - sh * h1
            new_p2 = ch * p2 - sh * h2
            new_p3 = ch * p3 - sh * h3
        else:
            # exp(-i H_D dt) = cos(E dt) I - i sin(E dt) H_D / E
            cs = torch.cos(E * dt)
            sn = torch.sin(E * dt) / E_inv
            new_p0 = cs * p0 - 1j * sn * h0
            new_p1 = cs * p1 - 1j * sn * h1
            new_p2 = cs * p2 - 1j * sn * h2
            new_p3 = cs * p3 - 1j * sn * h3

        psi_k_new = torch.stack([new_p0, new_p1, new_p2, new_p3], dim=0)
        return torch.fft.ifftn(psi_k_new, dim=(1, 2, 3))

    def step(self, psi, dt, tau=0.0, V_ext=None,
             self_consistent=True, imaginary=False, psi_mem=None):
        """One full Strang split-step.

        Parameters
        ----------
        psi : torch.Tensor (complex64)
            Wavefunction.
        dt : float
            Time step.
        tau : float
            Current physical time (for Yang oscillation).
        V_ext : torch.Tensor or None
            External potential (e.g. proton Coulomb well).
        self_consistent : bool
            If True, density sources its own potential.
        imaginary : bool
            If True, imaginary-time propagation (relaxation to ground state).
        psi_mem : torch.Tensor or None
            Previous ψ for φ-damping.

        Returns
        -------
        psi : torch.Tensor
            Updated wavefunction.
        psi_mem : torch.Tensor
            Updated memory (for φ-damping).
        """
        # Density
        rho = self._get_density(psi)

        # Update φ-damped density memory
        if self.qi_memory:
            if self.rho_memory is None:
                self.rho_memory = rho.clone()
            else:
                self.rho_memory = (
                    (1.0 - self.qi_tau) * self.rho_memory
                    + self.qi_tau * rho
                )

        # Update Hubble
        self._update_hubble(rho)

        # Update expansion
        self._update_expansion(dt)

        # ── Gauge field computation (gravitomagnetic + electromagnetic) ──
        rho_mag = None
        A2_em = None
        need_gauge = self_consistent and (self.alpha_mag > 0 or self.alpha_em > 0)
        if need_gauge:
            jx, jy, jz = self.compute_current(psi)
            Ax, Ay, Az = self.vector_potential(jx, jy, jz)
            if self.alpha_mag > 0:
                rho_mag = self.magnetic_field(Ax, Ay, Az)  # B²
                self.B2_mean = float(rho_mag.mean())
                self.B_rms = float(np.sqrt(max(self.B2_mean, 0.0)))
            if self.alpha_em > 0:
                A2_em = Ax**2 + Ay**2 + Az**2
                self.A2_mean = float(A2_em.mean())
                self.A_rms = float(np.sqrt(max(self.A2_mean, 0.0)))

        # Compute potential
        if self_consistent:
            Phi = self.potential(rho, tau=tau, rho_mag=rho_mag, A2_em=A2_em)
        else:
            Phi = torch.zeros_like(rho)

        # Add external potential (scaled by 1/a in expanding coordinates)
        if V_ext is not None:
            scale = 1.0 / self.a if self.expanding else 1.0
            Phi = Phi + V_ext * scale

        # ── First half potential step ──
        psi = self.potential_propagator(psi, Phi, dt / 2.0, imaginary)

        # ── Full kinetic step ──
        psi_prop = self.kinetic_propagator(psi, dt, imaginary)

        # Hubble drag: ψ → ψ · exp(-3H dt/2) for comoving norm conservation
        if self.expanding and not imaginary:
            psi_prop = psi_prop * np.exp(-1.5 * self.H * dt)

        # φ-damping: mix with previous step
        if self.phi_damp and psi_mem is not None:
            psi_new = PHI_INV * psi_mem + (1.0 - PHI_INV) * psi_prop
        else:
            psi_new = psi_prop

        psi_mem_out = psi_new.clone()
        psi = psi_new

        # ── Second half potential step (with updated density) ──
        rho = self._get_density(psi)
        if self_consistent:
            Phi = self.potential(rho, tau=tau + dt, rho_mag=rho_mag, A2_em=A2_em)
        else:
            Phi = torch.zeros_like(rho)
        if V_ext is not None:
            scale = 1.0 / self.a if self.expanding else 1.0
            Phi = Phi + V_ext * scale

        psi = self.potential_propagator(psi, Phi, dt / 2.0, imaginary)

        # Normalize for imaginary-time relaxation
        if imaginary:
            norm = torch.sqrt(self._get_density(psi).sum() * self.dV)
            psi = psi / norm

        return psi, psi_mem_out

    # ────────────────────────────────────────────────────────────────────
    # Diagnostics
    # ────────────────────────────────────────────────────────────────────

    def energy(self, psi, V_ext=None, self_consistent=True):
        """Compute total energy ⟨ψ|H|ψ⟩."""
        if self.kinetic_mode == 'dirac':
            return self._energy_dirac(psi, V_ext, self_consistent)

        # Standard Schrödinger energy
        psi_k = torch.fft.fftn(psi)
        a2 = self.a ** 2 if self.expanding else 1.0
        lap_k = -self.k2 * psi_k / a2
        lap = torch.fft.ifftn(lap_k)
        E_kin = -0.5 / self.mass * (torch.conj(psi) * lap).sum().real * self.dV

        rho = self._get_density(psi)
        if self_consistent:
            Phi = self.potential(rho)
        else:
            Phi = torch.zeros_like(rho)

        if V_ext is not None:
            scale = 1.0 / self.a if self.expanding else 1.0
            Phi = Phi + V_ext * scale

        E_pot = (Phi * rho).sum().real * self.dV
        E_nl = 0.5 * self.g * (rho ** 2).sum().real * self.dV

        return float((E_kin + E_pot + E_nl).item())

    def _energy_dirac(self, psi, V_ext=None, self_consistent=True):
        """Dirac energy: ⟨ψ|H_D|ψ⟩ computed in k-space + potential."""
        c = self.c if self.c is not None else 137.036
        kx, ky, kz = self.kx, self.ky, self.kz

        # FFT each spinor component
        psi_k = torch.fft.fftn(psi, dim=(1, 2, 3))  # (4, N, N, N)
        p0, p1, p2, p3 = psi_k[0], psi_k[1], psi_k[2], psi_k[3]

        # H_D ψ in k-space (same component formulas as propagator)
        h0 = c * (kz * p2 + (kx - 1j * ky) * p3) + c ** 2 * p0
        h1 = c * ((kx + 1j * ky) * p2 - kz * p3) + c ** 2 * p1
        h2 = c * (kz * p0 + (kx - 1j * ky) * p1) - c ** 2 * p2
        h3 = c * ((kx + 1j * ky) * p0 - kz * p1) - c ** 2 * p3

        # ψ_k† · H_D ψ_k  (Parseval: sum in k-space, normalize by dV/N³)
        E_k_density = (torch.conj(p0) * h0 + torch.conj(p1) * h1 +
                       torch.conj(p2) * h2 + torch.conj(p3) * h3)
        E_kin = E_k_density.real.sum() * self.dV / self.N_cells

        # Potential part (same as Schrödinger, with total density)
        rho = self._get_density(psi)
        if self_consistent:
            Phi = self.potential(rho)
        else:
            Phi = torch.zeros_like(rho)
        if V_ext is not None:
            scale = 1.0 / self.a if self.expanding else 1.0
            Phi = Phi + V_ext * scale
        E_pot = (Phi * rho).sum().real * self.dV
        E_nl = 0.5 * self.g * (rho ** 2).sum().real * self.dV

        return float((E_kin + E_pot + E_nl).item())

    def expectation_r(self, psi):
        """Expectation value ⟨r⟩."""
        rho = self._get_density(psi)
        return float((self.R * rho).sum() * self.dV)

    def radial_profile(self, psi, n_bins=80):
        """Radial density profile for spherical analysis."""
        rho = self._get_density(psi)
        r_flat = self.R.flatten().cpu().numpy()
        rho_flat = rho.flatten().cpu().numpy()
        bins = np.linspace(0, self.L / 2, n_bins + 1)
        centers = 0.5 * (bins[:-1] + bins[1:])
        profile = np.array([
            rho_flat[(r_flat >= b0) & (r_flat < b1)].mean()
            if ((r_flat >= b0) & (r_flat < b1)).any() else 0.0
            for b0, b1 in zip(bins[:-1], bins[1:])
        ])
        return centers, profile

    def density_slice(self, psi, axis=0, mid=None):
        """2D slice through the density field."""
        if mid is None:
            mid = self.grid // 2
        rho = self._get_density(psi)
        if axis == 0:
            return rho[mid, :, :].cpu().numpy()
        elif axis == 1:
            return rho[:, mid, :].cpu().numpy()
        else:
            return rho[:, :, mid].cpu().numpy()


# ═══════════════════════════════════════════════════════════════════════════
# Initial Conditions
# ═══════════════════════════════════════════════════════════════════════════

def initial_atomic(solver, sigma=1.5):
    """Gaussian wave packet centered at origin (atomic initial condition)."""
    psi = (1.0 / (np.pi ** 0.75 * sigma ** 1.5)) * torch.exp(
        -solver.R ** 2 / (2.0 * sigma ** 2)
    )
    psi = psi.to(torch.complex64)
    norm = torch.sqrt((torch.abs(psi) ** 2).sum() * solver.dV)
    return psi / norm


def initial_cosmos(solver, amplitude=0.05, n_s=-2.0, seed=42):
    """Random Gaussian field with power-law spectrum (cosmological ICs)."""
    gen = torch.Generator(device=solver.device)
    gen.manual_seed(seed)
    white = (torch.randn(solver.shape, generator=gen, device=solver.device)
             + 1j * torch.randn(solver.shape, generator=gen, device=solver.device))

    with torch.no_grad():
        amp = torch.where(
            solver.k_mag > 0,
            (solver.k_mag / solver.k0) ** (n_s / 2.0),
            torch.zeros_like(solver.k_mag)
        )

    delta = torch.fft.ifftn(white * amp).real
    delta = delta - delta.mean()
    delta = delta * (amplitude / delta.std())

    rho = torch.clamp(1.0 + delta, min=1e-6)
    theta = torch.rand(solver.shape, generator=gen, device=solver.device) * 2.0 * np.pi
    psi = torch.sqrt(rho) * torch.exp(1j * theta)
    psi = psi.to(torch.complex64)

    # Normalize to total mass = box volume
    norm_factor = float(np.sqrt(solver.dV * solver.N_cells))
    norm = torch.sqrt((torch.abs(psi) ** 2).sum() * solver.dV)
    return psi / norm * norm_factor


# ═══════════════════════════════════════════════════════════════════════════
# Power Spectrum
# ═══════════════════════════════════════════════════════════════════════════

def power_spectrum(delta, L, n_bins=32):
    """Radial power spectrum P(k) from density contrast field."""
    grid = delta.shape[0]
    dx_t = L / grid
    k_1d = 2.0 * np.pi * np.fft.fftfreq(grid, d=dx_t)
    kz, ky, kx = np.meshgrid(k_1d, k_1d, k_1d, indexing='ij')
    k_mag = np.sqrt(kx**2 + ky**2 + kz**2)

    # Convert to numpy if tensor
    if hasattr(delta, 'cpu'):
        delta = delta.cpu().numpy()

    delta_k = np.fft.fftn(delta)
    P = np.abs(delta_k) ** 2 / (L ** 3)

    k_min = k_mag[k_mag > 0].min()
    k_max = k_mag.max()
    bins = np.linspace(k_min, k_max, n_bins + 1)
    k_out = 0.5 * (bins[:-1] + bins[1:])
    Pk = np.zeros(n_bins)

    for i in range(n_bins):
        mask = (k_mag >= bins[i]) & (k_mag < bins[i + 1])
        if mask.any():
            Pk[i] = P[mask].mean()

    valid = Pk > 0
    return k_out[valid], Pk[valid]


# ═══════════════════════════════════════════════════════════════════════════
# Run Modes
# ═══════════════════════════════════════════════════════════════════════════

def run_atomic(grid=64, L=20.0, dt=0.005, n_steps=4000,
               sigma_init=1.5, eps=0.1, phi_damp=True,
               report_every=400):
    """Atomic limit: hydrogen ground state via imaginary-time relaxation.

    M=1, fixed soft-Coulomb proton well, no self-consistent gravity.
    φ-damping suppresses oscillatory transients during convergence.
    """
    print(f"\n{'='*60}")
    print(f"ATOMIC LIMIT: Hydrogen Ground State")
    print(f"{'='*60}")
    print(f"  grid={grid}³  L={L:.1f} a₀  M=1  dt={dt}  steps={n_steps}")
    print(f"  φ-damping: {phi_damp}  ε_soft={eps}")

    solver = CassiBridgeV2(
        grid=grid, L=L, mass=1.0,
        phi_damp=phi_damp,
        g=0.0,  # no nonlinear self-focusing for hydrogen test
    )

    # Soft Coulomb potential for proton at origin
    V_ext = -1.0 / torch.sqrt(solver.R ** 2 + eps ** 2)

    # Initial Gaussian wave packet
    psi = initial_atomic(solver, sigma=sigma_init)
    psi_mem = psi.clone()

    history = {'steps': [], 'E': [], 'r': [], 'a': []}
    t0 = time.time()

    for step in range(n_steps):
        psi, psi_mem = solver.step(
            psi, dt, V_ext=V_ext,
            self_consistent=False, imaginary=True,
            psi_mem=psi_mem if phi_damp else None
        )

        if step % report_every == 0 or step == n_steps - 1:
            E = solver.energy(psi, V_ext=V_ext, self_consistent=False)
            r_exp = solver.expectation_r(psi)
            history['steps'].append(step)
            history['E'].append(E)
            history['r'].append(r_exp)
            history['a'].append(solver.a)
            print(f"  step {step:5d} | E={E:+.6f} E_h | <r>={r_exp:.4f} a₀")

    elapsed = time.time() - t0
    print(f"  Converged in {elapsed:.1f}s ({elapsed/n_steps*1000:.2f} ms/step)")

    # Final diagnostics
    E_final = history['E'][-1]
    r_final = history['r'][-1]
    print(f"\nFinal:  E = {E_final:+.6f} E_h  (target: -0.500)")
    print(f"          <r> = {r_final:.4f} a₀  (target: 1.500)")
    print(f"          ΔE = {abs(E_final + 0.5):.6f}  Δr = {abs(r_final - 1.5):.4f}")

    return solver, psi, history


# ═══════════════════════════════════════════════════════════════════════════
# DFT: Multi-Electron Atoms via Hartree-Fock / LDA
# ═══════════════════════════════════════════════════════════════════════════

def run_cosmos(grid=64, L=100.0, mass=100.0, dt=0.01, n_steps=500,
               alpha_disp=1.0 - PHI_INV, alpha_yin=1.0, yin_mode='relative',
               yang_amp=1.0, phi_damp=True, qi_gate=True, qi_memory=True,
               holographic=True, eta=0.004, grav_sigma=0.2,
               alpha_mag=0.0, alpha_em=0.0,
               expanding=True, H0=0.05, hubble_mode='stress_energy',
               seed=42, report_every=50):
    """Cosmological limit: structure formation with expanding background.

    M≫1 → semi-classical dust. Self-consistent gravity with full Cassi source:
    Qi-gated entropic correction, φ-damped memory, Yang oscillation,
    holographic bound, N-body saturation, stress-energy Hubble.
    """
    print(f"\n{'='*60}")
    print(f"COSMOLOGICAL LIMIT: Structure Formation")
    print(f"{'='*60}")
    print(f"  grid={grid}³  L={L:.0f}  M={mass:.0f}  dt={dt}  steps={n_steps}")
    print(f"  α_disp={alpha_disp:.4f}  α_yin={alpha_yin}  yin={yin_mode}")
    print(f"  grav_σ={grav_sigma}  holographic={holographic}  η={eta}")
    print(f"  α_mag={alpha_mag}  α_em={alpha_em}  H0={H0}  Hubble: {hubble_mode}  expanding: {expanding}")

    solver = CassiBridgeV2(
        grid=grid, L=L, mass=mass,
        alpha_disp=alpha_disp, v0=1.0,
        alpha_yin=alpha_yin, yin_mode=yin_mode,
        yang_amp=yang_amp, yang_period=PHI_INV,
        phi_damp=phi_damp,
        qi_gate=qi_gate, qi_memory=qi_memory,
        grav_sigma=grav_sigma,
        alpha_mag=alpha_mag,
        alpha_em=alpha_em,
        expanding=expanding, H0=H0,
        hubble_mode=hubble_mode,
    )

    psi = initial_cosmos(solver, amplitude=0.05, n_s=-2.0, seed=seed)
    psi_mem = psi.clone() if phi_damp else None
    tau = 0.0
    snaps = []
    t0 = time.time()

    for step in range(n_steps):
        psi, psi_mem = solver.step(
            psi, dt, tau=tau,
            self_consistent=True, imaginary=False,
            psi_mem=psi_mem
        )
        tau += dt

        # Re-normalize to preserve mean density (mass conservation)
        rho = torch.abs(psi) ** 2
        rho_bar = rho.mean()
        psi = psi / torch.sqrt(rho_bar)

        if step % report_every == 0 or step == n_steps - 1:
            rho = torch.abs(psi) ** 2
            delta = rho - 1.0
            delta_rms = float(delta.std())
            info = solver.field_information(rho)
            k, Pk = power_spectrum(delta, L)

            snap = {
                'step': step, 'tau': tau,
                'rho': rho.cpu().numpy().copy(),
                'delta_rms': delta_rms,
                'information': info,
                'k': k, 'Pk': Pk,
                'a': solver.a, 'H': solver.H,
                'B_rms': solver.B_rms, 'B2_mean': solver.B2_mean,
                'A_rms': solver.A_rms, 'A2_mean': solver.A2_mean,
            }
            snaps.append(snap)
            q_str = f"  q={solver.q_mean:.4f}" if qi_gate else ""
            b_str = f"  B_rms={solver.B_rms:.4f}" if alpha_mag > 0 else ""
            em_str = f"  A_rms={solver.A_rms:.4f}" if alpha_em > 0 else ""
            print(f"  step {step:4d} | τ={tau:.3f} | a={solver.a:.4f} | "
                  f"H={solver.H:.4f} | δ_rms={delta_rms:.4f}{q_str}{b_str}{em_str}")

    elapsed = time.time() - t0
    print(f"  Evolved in {elapsed:.1f}s ({elapsed/n_steps*1000:.2f} ms/step)")

    final = snaps[-1]
    print(f"\nFinal:  a = {final['a']:.4f}  H = {final['H']:.4f}")
    print(f"          δ_rms = {final['delta_rms']:.4f}  I[ρ] = {final['information']:.4f}")
    if alpha_mag > 0:
        print(f"          B_rms = {final['B_rms']:.4f}  B²_mean = {final['B2_mean']:.4f}")
    if alpha_em > 0:
        print(f"          A_rms = {final['A_rms']:.4f}  A²_mean = {final['A2_mean']:.4f}")

    return solver, psi, snaps



# ═══════════════════════════════════════════════════════════════════════════
# H₂⁺ Molecule: Two-Center Bonding
# ═══════════════════════════════════════════════════════════════════════════

def build_diatomic_potential(solver, d, eps=0.1, axis=2):
    """Two-center soft Coulomb potential. Protons at ±d/2 along axis."""
    half = d / 2.0

    if axis == 0:
        r1 = torch.sqrt((solver.X - half)**2 + solver.Y**2 + solver.Z**2 + eps**2)
        r2 = torch.sqrt((solver.X + half)**2 + solver.Y**2 + solver.Z**2 + eps**2)
    elif axis == 1:
        r1 = torch.sqrt(solver.X**2 + (solver.Y - half)**2 + solver.Z**2 + eps**2)
        r2 = torch.sqrt(solver.X**2 + (solver.Y + half)**2 + solver.Z**2 + eps**2)
    else:
        r1 = torch.sqrt(solver.X**2 + solver.Y**2 + (solver.Z - half)**2 + eps**2)
        r2 = torch.sqrt(solver.X**2 + solver.Y**2 + (solver.Z + half)**2 + eps**2)

    return -1.0 / r1 - 1.0 / r2


def initial_h2_plus(solver, d, symmetric=True, axis=2):
    """LCAO initial guess: sum/difference of 1s orbitals at each center."""
    half = d / 2.0

    if axis == 0:
        r1 = torch.sqrt((solver.X - half)**2 + solver.Y**2 + solver.Z**2)
        r2 = torch.sqrt((solver.X + half)**2 + solver.Y**2 + solver.Z**2)
    elif axis == 1:
        r1 = torch.sqrt(solver.X**2 + (solver.Y - half)**2 + solver.Z**2)
        r2 = torch.sqrt(solver.X**2 + (solver.Y + half)**2 + solver.Z**2)
    else:
        r1 = torch.sqrt(solver.X**2 + solver.Y**2 + (solver.Z - half)**2)
        r2 = torch.sqrt(solver.X**2 + solver.Y**2 + (solver.Z + half)**2)

    psi1 = torch.exp(-r1)
    psi2 = torch.exp(-r2)

    psi = psi1 + psi2 if symmetric else psi1 - psi2
    psi = psi.to(torch.complex64)
    norm = torch.sqrt((torch.abs(psi)**2).sum() * solver.dV)
    return psi / norm


def run_h2_plus(grid=64, L=15.0, dt=0.003, n_steps=2000,
                d=2.0, eps=0.1, symmetric=True,
                report_every=200):
    """H₂⁺ molecule: imaginary-time relaxation at fixed bond length.

    One electron in the field of two fixed protons separated by distance d.
    Ground state (symmetric LCAO) → bonding σ_g orbital.
    """
    label = "bonding σ_g" if symmetric else "antibonding σ_u*"
    print(f"\n{'='*60}")
    print(f"H₂⁺ {label}: d = {d:.2f} a₀")
    print(f"{'='*60}")
    print(f"  grid={grid}³  L={L:.1f} a₀  dt={dt}  steps={n_steps}  ε_soft={eps}")

    solver = CassiBridgeV2(grid=grid, L=L, mass=1.0)
    V_ext = build_diatomic_potential(solver, d, eps)
    psi = initial_h2_plus(solver, d, symmetric)

    history = {'steps': [], 'E': []}
    t0 = time.time()

    for step in range(n_steps):
        psi, _ = solver.step(
            psi, dt, V_ext=V_ext,
            self_consistent=False, imaginary=True, psi_mem=None
        )

        if step % report_every == 0 or step == n_steps - 1:
            E = solver.energy(psi, V_ext=V_ext, self_consistent=False)
            history['steps'].append(step)
            history['E'].append(E)
            print(f"  step {step:5d} | E_el = {E:+.6f} E_h")

    elapsed = time.time() - t0
    E_final = history['E'][-1]
    E_total = E_final + 1.0 / d  # add nuclear repulsion
    print(f"  Final:  E_el = {E_final:+.6f} E_h")
    print(f"          E_total = {E_total:+.6f} E_h  (incl. 1/R = {1.0/d:.4f})")
    print(f"  Time: {elapsed:.1f}s")

    return solver, psi, history, E_final, E_total


def scan_bond_lengths(grid=64, L=15.0, dt=0.003, n_steps=1500,
                      eps=0.1, d_min=1.0, d_max=6.0, n_points=11,
                      report_every=200):
    """Scan internuclear distance: potential energy curve of H₂⁺."""
    print(f"\n{'='*60}")
    print(f"H₂⁺ BOND LENGTH SCAN")
    print(f"{'='*60}")
    print(f"  d = {d_min:.1f} – {d_max:.1f} a₀  ({n_points} points)")
    print(f"  grid={grid}³  L={L:.1f} a₀  steps={n_steps} per point")

    d_values = np.linspace(d_min, d_max, n_points)
    results = []
    t0 = time.time()

    # Compute grid-limited reference hydrogen energy at this resolution
    ref_solver = CassiBridgeV2(grid=grid, L=L, mass=1.0)
    ref_V = -1.0 / torch.sqrt(ref_solver.R**2 + eps**2)
    ref_psi = torch.exp(-ref_solver.R).to(torch.complex64)
    ref_psi = ref_psi / torch.sqrt((torch.abs(ref_psi)**2).sum() * ref_solver.dV)
    # Relax to the grid-limited ground state
    for _ in range(n_steps):
        ref_psi, _ = ref_solver.step(
            ref_psi, dt, V_ext=ref_V,
            self_consistent=False, imaginary=True, psi_mem=None
        )
    E_H = float(ref_solver.energy(ref_psi, V_ext=ref_V, self_consistent=False))
    print(f"  Reference E_H = {E_H:.6f} E_h (relaxed hydrogen at ε={eps})")

    for i, d in enumerate(d_values):
        solver = CassiBridgeV2(grid=grid, L=L, mass=1.0)
        V_ext = build_diatomic_potential(solver, d, eps)
        psi = initial_h2_plus(solver, d, symmetric=True)

        for step in range(n_steps):
            psi, _ = solver.step(
                psi, dt, V_ext=V_ext,
                self_consistent=False, imaginary=True, psi_mem=None
            )

        E_el = solver.energy(psi, V_ext=V_ext, self_consistent=False)
        E_total = E_el + 1.0 / d

        # Density diagnostics—slice along bond axis (xz-plane at y=0)
        rho = torch.abs(psi)**2
        rho_slice = rho[:, grid // 2, :].cpu().numpy()  # xz-plane at y=0
        info = solver.field_information(rho)

        results.append({
            'd': d, 'E_el': E_el, 'E_total': E_total,
            'rho_slice': rho_slice, 'information': info,
            'psi': psi
        })

        bind = E_total - E_H
        print(f"  [{i+1:2d}/{n_points}] d={d:.2f}  "
              f"E_el={E_el:+.6f}  E_total={E_total:+.6f}  "
              f"E_bind={bind:+.6f} E_h  ({bind*27.2114:+.2f} eV)")

    elapsed = time.time() - t0

    # Find equilibrium
    E_totals = [r['E_total'] for r in results]
    idx_min = np.argmin(E_totals)
    d_eq = d_values[idx_min]
    E_eq = E_totals[idx_min]
    E_bind_eq = E_eq - E_H

    print(f"\nEquilibrium: d_eq = {d_eq:.2f} a₀")
    print(f"  E_total(d_eq) = {E_eq:+.6f} E_h")
    print(f"  Binding energy = {E_bind_eq:+.6f} E_h = {E_bind_eq*27.2114:+.2f} eV")
    print(f"  (Exact H₂⁺: d_eq = 2.00 a₀, E_bind = -0.1026 E_h = -2.79 eV)")
    print(f"  Scan time: {elapsed:.1f}s")

    return d_values, results, E_H


def plot_h2_plus(d_values, results, outdir='figures', E_H=-0.5, L=15.0):
    """Plot H₂⁺ potential energy curve and bonding diagnostics."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    E_totals = np.array([r['E_total'] for r in results])
    E_els = np.array([r['E_el'] for r in results])

    idx_min = np.argmin(E_totals)
    d_eq = d_values[idx_min]
    E_eq = E_totals[idx_min]

    fig, axes = plt.subplots(2, 3, figsize=(16, 10))

    # ── Potential energy curve ──
    ax = axes[0, 0]
    ax.plot(d_values, E_totals, 'b-o', lw=2, ms=6, label='Bridge v2')
    ax.axhline(E_H, color='gray', ls=':', lw=1.5, label=f'H + H⁺ (E_H={E_H:.3f})')
    ax.axvline(d_eq, color='red', ls='--', lw=1.5, alpha=0.5)
    ax.scatter([d_eq], [E_eq], c='red', s=100, zorder=5,
               label=f'd_eq = {d_eq:.2f} a₀')
    ax.set_xlabel('Internuclear distance d [a₀]')
    ax.set_ylabel('Total energy E_total [E_h]')
    ax.set_title('H₂⁺ Potential Energy Curve')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # ── Binding energy ──
    ax = axes[0, 1]
    E_bind = E_totals - E_H  # relative to grid-limited dissociation
    ax.plot(d_values, E_bind * 27.2114, 'darkgreen', lw=2, marker='s', ms=6)
    ax.axhline(0, color='gray', ls=':', lw=1)
    ax.axhline(-2.79, color='red', ls=':', lw=1.5, label='Exact H₂⁺ (−2.79 eV)')
    ax.scatter([d_eq], [E_bind[idx_min] * 27.2114], c='red', s=100, zorder=5)
    ax.set_xlabel('d [a₀]')
    ax.set_ylabel('Binding energy [eV]')
    ax.set_title('Binding Energy')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # ── Density slices at key distances ──
    key_indices = [0, idx_min, -1]
    key_labels = [f'd = {d_values[i]:.1f}' for i in key_indices]
    for panel_idx, (ki, label, _) in enumerate(zip(key_indices, key_labels, ['', '', ''])):
        ax = axes[1, panel_idx]
        rho_slice = results[ki]['rho_slice']
        im = ax.imshow(rho_slice.T, origin='lower', cmap='inferno',
                       extent=[-L/2, L/2, -L/2, L/2])
        ax.set_title(f'Density |ψ|² ({label})')
        ax.set_xlabel('x [a₀]')
        ax.set_ylabel('z [a₀]')
        plt.colorbar(im, ax=ax, fraction=0.046)

    fig.suptitle('Cassi Bridge v2—H₂⁺ Molecular Bonding',
                 fontsize=14, fontweight='bold')
    fig.tight_layout()
    out = outdir / 'cassi_bridge_v2_h2plus.png'
    fig.savefig(out, dpi=150, bbox_inches='tight')
    print(f'  Saved {out}')
    plt.close(fig)



# ═══════════════════════════════════════════════════════════════════════════
# Plotting
# ═══════════════════════════════════════════════════════════════════════════

def plot_bridge(atomic_data, cosmos_snaps, outdir='figures'):
    """Generate comparison plots for both limits."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # ── Atomic plots ──────────────────────────────────────────────────
    if atomic_data is not None:
        solver_a, psi_a, hist_a = atomic_data

        fig, axes = plt.subplots(2, 3, figsize=(16, 10))

        # Radial density profile vs exact 1s
        ax = axes[0, 0]
        r_1d = np.linspace(0, solver_a.L / 2, 200)
        rho_exact = (1.0 / np.pi) * np.exp(-2.0 * r_1d)  # |ψ_1s|²
        centers, profile = solver_a.radial_profile(psi_a)
        ax.plot(centers, profile / profile.max(), 'b-', lw=2, label='Bridge')
        ax.plot(r_1d, rho_exact / rho_exact.max(), 'k:', lw=2, label='Exact 1s')
        ax.set_xlim(0, 8)
        ax.set_xlabel('r [a₀]')
        ax.set_ylabel('Normalized density')
        ax.set_title('Radial Profile vs Hydrogen 1s')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Energy convergence
        ax = axes[0, 1]
        ax.plot(hist_a['steps'], hist_a['E'], 'b-', lw=2)
        ax.axhline(-0.5, color='k', ls=':', lw=2, label='E₁ = −0.5 E_h')
        ax.set_xlabel('Step')
        ax.set_ylabel('Energy [E_h]')
        ax.set_title('Energy Convergence')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Radius convergence
        ax = axes[0, 2]
        ax.plot(hist_a['steps'], hist_a['r'], 'b-', lw=2)
        ax.axhline(1.5, color='k', ls=':', lw=2, label='⟨r⟩₁ₛ = 1.5 a₀')
        ax.set_xlabel('Step')
        ax.set_ylabel('⟨r⟩ [a₀]')
        ax.set_title('Radius Convergence')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Density slice (xy-plane at z=0)
        ax = axes[1, 0]
        rho_slice = solver_a.density_slice(psi_a, axis=0)
        im = ax.imshow(rho_slice.T, origin='lower', cmap='inferno',
                       extent=[-solver_a.L/2, solver_a.L/2, -solver_a.L/2, solver_a.L/2])
        ax.set_xlabel('x [a₀]')
        ax.set_ylabel('y [a₀]')
        ax.set_title('Density |ψ|² (central slice)')
        plt.colorbar(im, ax=ax, fraction=0.046)

        # Phase of wavefunction
        ax = axes[1, 1]
        phase_slice = np.angle(psi_a[solver_a.grid // 2, :, :].cpu().numpy())
        im = ax.imshow(phase_slice.T, origin='lower', cmap='twilight',
                       extent=[-solver_a.L/2, solver_a.L/2, -solver_a.L/2, solver_a.L/2])
        ax.set_xlabel('x [a₀]')
        ax.set_ylabel('y [a₀]')
        ax.set_title('Phase arg(ψ) (central slice)')
        plt.colorbar(im, ax=ax, fraction=0.046)

        # E vs r trajectory
        ax = axes[1, 2]
        ax.plot(hist_a['r'], hist_a['E'], 'b-', lw=1.5, alpha=0.7)
        ax.scatter([hist_a['r'][0]], [hist_a['E'][0]], c='green', s=100, marker='o',
                   zorder=5, label='Start')
        ax.scatter([hist_a['r'][-1]], [hist_a['E'][-1]], c='red', s=100, marker='*',
                   zorder=5, label='Final')
        ax.axhline(-0.5, color='k', ls=':', lw=1)
        ax.axvline(1.5, color='k', ls=':', lw=1)
        ax.set_xlabel('⟨r⟩ [a₀]')
        ax.set_ylabel('E [E_h]')
        ax.set_title('Energy–Radius Trajectory')
        ax.legend()
        ax.grid(True, alpha=0.3)

        fig.suptitle('Cassi Bridge v2—Atomic Limit: Hydrogen Ground State',
                     fontsize=14, fontweight='bold')
        fig.tight_layout()
        out = outdir / 'cassi_bridge_v2_atomic.png'
        fig.savefig(out, dpi=150, bbox_inches='tight')
        print(f'  Saved {out}')
        plt.close(fig)

    # ── Cosmological plots ─────────────────────────────────────────────
    if cosmos_snaps is not None and len(cosmos_snaps) > 0:
        final = cosmos_snaps[-1]
        L_cos = 100.0  # default, should match run

        fig, axes = plt.subplots(2, 3, figsize=(16, 10))

        # Density projection (z-integrated)
        ax = axes[0, 0]
        proj = final['rho'].sum(axis=0)
        im = ax.imshow(np.log10(np.clip(proj, a_min=proj[proj > 0].min(), a_max=None)).T,
                       origin='lower', cmap='inferno',
                       extent=[-L_cos/2, L_cos/2, -L_cos/2, L_cos/2])
        a_str = f"a={final.get('a', 1):.3f}"
        ax.set_title(f'log₁₀ Density Projection ({a_str})')
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        plt.colorbar(im, ax=ax, fraction=0.046)

        # Power spectrum evolution
        ax = axes[0, 1]
        colors = ['black', 'blue', 'darkorange']
        labels = ['initial', 'mid', 'final']
        indices = [0, len(cosmos_snaps) // 2, -1]
        for idx, c, label in zip(indices, colors, labels):
            s = cosmos_snaps[idx]
            valid = s['Pk'] > 0
            ax.loglog(s['k'][valid], s['Pk'][valid], '-o', ms=3,
                      color=c, label=f"{label} (τ={s['tau']:.1f})")
        ax.set_xlabel('k')
        ax.set_ylabel('P(k)')
        ax.set_title('Power Spectrum Evolution')
        ax.legend()
        ax.grid(True, which='both', alpha=0.3)

        # δ_rms vs τ
        ax = axes[0, 2]
        taus = [s['tau'] for s in cosmos_snaps]
        ax.plot(taus, [s['delta_rms'] for s in cosmos_snaps],
                'darkorange', lw=2, marker='o', ms=4)
        ax.set_xlabel('τ')
        ax.set_ylabel('δ_rms')
        ax.set_title('Structure Growth')
        ax.grid(True, alpha=0.3)

        # Scale factor a(τ)
        ax = axes[1, 0]
        a_vals = [s.get('a', 1) for s in cosmos_snaps]
        ax.plot(taus, a_vals, 'purple', lw=2, marker='o', ms=4)
        ax.set_xlabel('τ')
        ax.set_ylabel('a(τ)')
        ax.set_title('Scale Factor')
        ax.grid(True, alpha=0.3)

        # Hubble H(τ)
        ax = axes[1, 1]
        H_vals = [s.get('H', 0) for s in cosmos_snaps]
        ax.plot(taus, H_vals, 'darkgreen', lw=2, marker='s', ms=4)
        ax.axhline(y=0, color='k', ls='-', lw=0.5)
        ax.set_xlabel('τ')
        ax.set_ylabel('H(τ)')
        ax.set_title('Hubble Parameter')
        ax.grid(True, alpha=0.3)

        # Field information I[ρ]
        ax = axes[1, 2]
        info_vals = [s['information'] for s in cosmos_snaps]
        ax.plot(taus, info_vals, 'darkred', lw=2, marker='^', ms=4)
        ax.set_xlabel('τ')
        ax.set_ylabel('I[ρ]')
        ax.set_title('Field Information (KL divergence)')
        ax.grid(True, alpha=0.3)

        fig.suptitle('Cassi Bridge v2—Cosmological Limit: Structure Formation',
                     fontsize=14, fontweight='bold')
        fig.tight_layout()
        out = outdir / 'cassi_bridge_v2_cosmos.png'
        fig.savefig(out, dpi=150, bbox_inches='tight')
        print(f'  Saved {out}')
        plt.close(fig)

    # ── Combined summary diagnostic ────────────────────────────────────
    if atomic_data is not None and cosmos_snaps is not None and len(cosmos_snaps) > 0:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('off')

        _, _, hist_a = atomic_data
        final_c = cosmos_snaps[-1]

        lines = [
            "Cassi Bridge v2—Scale Span",
            "=" * 50,
            "",
            "Atomic Limit (Hydrogen):",
            f"  Grid: {hist_a['steps'][-1]} steps",
            f"  Final E:  {hist_a['E'][-1]:+.6f} E_h  (target: −0.500)",
            f"  Final ⟨r⟩: {hist_a['r'][-1]:.4f} a₀  (target: 1.500)",
            f"  Mass M = 1  |  Self-consistent: OFF  |  Expansion: OFF",
            "",
            "Cosmological Limit (LSS):",
            f"  Final τ: {final_c['tau']:.2f}",
            f"  Final a:  {final_c['a']:.4f}",
            f"  Final H:  {final_c['H']:.4f}",
            f"  Final δ_rms: {final_c['delta_rms']:.4f}",
            f"  Final I[ρ]: {final_c['information']:.4f}",
            f"  Mass M = 100  |  Self-consistent: ON  |  Expansion: ON",
            "",
            "Mechanisms Shared Across Both Limits:",
            f"  φ = {PHI:.6f}  (scale-separation constant)",
            "  • Qi-gated entropic source",
            "  • φ-damped density memory",
            "  • N-body gravitational saturation",
            "  • Split-step spectral propagation",
            "  • Scale-dependent Poisson kernel",
            "",
            "Same PDE. Same φ. 40 orders of magnitude.",
        ]

        for i, line in enumerate(lines):
            ax.text(0.05, 0.95 - i * 0.035, line, transform=ax.transAxes,
                    fontsize=11, family='monospace', verticalalignment='top')

        out = outdir / 'cassi_bridge_v2_summary.png'
        fig.savefig(out, dpi=150, bbox_inches='tight')
        print(f'  Saved {out}')
        plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Cassi Bridge v2: Hydrogen ↔ Cosmology (Two-Fluid-Informed)'
    )
    parser.add_argument('--mode', default='all',
                        choices=['atomic', 'cosmos', 'all', 'h2plus'],
                        help='Which limit to run')
    parser.add_argument('--grid', type=int, default=64,
                        help='Grid points per dimension')
    parser.add_argument('--L-atomic', type=float, default=20.0,
                        help='Box size for atomic mode [a0]')
    parser.add_argument('--L-cosmos', type=float, default=100.0,
                        help='Box size for cosmological mode')
    parser.add_argument('--steps-atomic', type=int, default=4000,
                        help='Relaxation steps (atomic)')
    parser.add_argument('--steps-cosmos', type=int, default=500,
                        help='Evolution steps (cosmological)')
    parser.add_argument('--dt-atomic', type=float, default=0.005,
                        help='Time step (atomic)')
    parser.add_argument('--dt-cosmos', type=float, default=0.01,
                        help='Time step (cosmological)')
    parser.add_argument('--mass-cosmos', type=float, default=100.0,
                        help='Effective mass for cosmological mode')
    parser.add_argument('--d', type=float, default=2.0,
                        help='Bond length for H2+ [a0]')
    parser.add_argument('--steps-h2', type=int, default=2000,
                        help='Relaxation steps for H2+')
    parser.add_argument('--dt-h2', type=float, default=0.003,
                        help='Time step for H2+')
    parser.add_argument('--L-h2', type=float, default=15.0,
                        help='Box size for H2+ [a0]')
    parser.add_argument('--scan-bonds', action='store_true',
                        help='Scan H2+ bond-length curve')
    parser.add_argument('--d-min', type=float, default=1.0,
                        help='Min bond length for scan')
    parser.add_argument('--d-max', type=float, default=6.0,
                        help='Max bond length for scan')
    parser.add_argument('--n-points', type=int, default=11,
                        help='Number of scan points')
    parser.add_argument('--H0', type=float, default=0.05,
                        help='Hubble constant')
    parser.add_argument('--hubble-mode', default='stress_energy',
                        choices=['friedmann', 'stress_energy'],
                        help='Hubble parameter mode')
    parser.add_argument('--no-qi-gate', action='store_true',
                        help='Disable Qi gating')
    parser.add_argument('--no-qi-memory', action='store_true',
                        help='Disable Qi memory')
    parser.add_argument('--no-phi-damp', action='store_true',
                        help='Disable φ-damping')
    parser.add_argument('--no-expanding', action='store_true',
                        help='Disable expansion (cosmological)')
    parser.add_argument('--no-holographic', action='store_true',
                        help='Disable holographic bound')
    parser.add_argument('--alpha-yin', type=float, default=1.0,
                        help='Yin entropic coupling')
    parser.add_argument('--yin-mode', default='relative',
                        choices=['relative', 'signed', 'none'],
                        help='Entropic source mode')
    parser.add_argument('--yang-amp', type=float, default=1.0,
                        help='Yang dark-energy amplitude')
    parser.add_argument('--grav-sigma', type=float, default=0.2,
                        help='N-body saturation scale')
    parser.add_argument('--alpha-mag', type=float, default=0.0,
                        help='Magnetic/gravitomagnetic coupling (0=off)')
    parser.add_argument('--alpha-em', type=float, default=0.0, help='EM gauge coupling (0=off)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed (cosmological)')
    parser.add_argument('--outdir', default='figures',
                        help='Output directory for plots')
    args = parser.parse_args()

    fig_dir = Path(args.outdir)
    fig_dir.mkdir(parents=True, exist_ok=True)

    atomic_data = None
    cosmos_snaps = None

    qi_gate = not args.no_qi_gate
    qi_memory = not args.no_qi_memory
    phi_damp = not args.no_phi_damp
    expanding = not args.no_expanding
    holographic = not args.no_holographic

    # ── H₂⁺ molecule ──────────────────────────────────────────────────
    if args.mode == 'h2plus':
        if args.scan_bonds:
            d_vals, results, E_H = scan_bond_lengths(
                grid=args.grid, L=args.L_h2, dt=args.dt_h2,
                n_steps=args.steps_h2,
                d_min=args.d_min, d_max=args.d_max,
                n_points=args.n_points,
            )
            plot_h2_plus(d_vals, results, outdir=args.outdir, E_H=E_H, L=args.L_h2)
        else:
            run_h2_plus(
                grid=args.grid, L=args.L_h2, d=args.d,
                dt=args.dt_h2, n_steps=args.steps_h2,
            )
        print(f"\n{'='*60}")
        print("BRIDGE v2 COMPLETE")
        print(f"{'='*60}")
        return

    # ── Atomic / cosmological / both ──────────────────────────────────
    if args.mode in ('all', 'atomic'):
        atomic_data = run_atomic(
            grid=args.grid, L=args.L_atomic,
            dt=args.dt_atomic, n_steps=args.steps_atomic,
            phi_damp=phi_damp,
            report_every=max(1, args.steps_atomic // 10),
        )
    if args.mode in ('all', 'cosmos'):
        _, _, cosmos_snaps = run_cosmos(
            grid=args.grid, L=args.L_cosmos,
            mass=args.mass_cosmos,
            dt=args.dt_cosmos, n_steps=args.steps_cosmos,
            alpha_disp=1.0 - PHI_INV,
            alpha_yin=args.alpha_yin,
            yin_mode=args.yin_mode if args.alpha_yin > 0 else 'none',
            yang_amp=args.yang_amp,
            phi_damp=phi_damp,
            qi_gate=qi_gate, qi_memory=qi_memory,
            holographic=holographic, eta=0.004,
            grav_sigma=args.grav_sigma,
            alpha_mag=args.alpha_mag,
            alpha_em=args.alpha_em,
            expanding=expanding, H0=args.H0,
            hubble_mode=args.hubble_mode,
            seed=args.seed,
            report_every=max(1, args.steps_cosmos // 10),
        )

    if atomic_data is not None or cosmos_snaps is not None:
        plot_bridge(atomic_data, cosmos_snaps, outdir=args.outdir)

    print(f"\n{'='*60}")
    print("BRIDGE v2 COMPLETE")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
