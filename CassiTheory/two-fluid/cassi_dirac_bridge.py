#!/usr/bin/env python3
"""
Dirac Bridge: Relativistic extension of CassiBridgeV2
======================================================

Implements the Dirac equation on a 3D grid with exact k-space
propagation, 4-spinor wavefunctions, spin-orbit coupling, and
fine-structure analysis.

Pillars:
  1. Dirac relativistic QM (H_D = -i c α·∇ + β mc²)
  2. Yang/Yin mapping from 4-spinor → φ-based fine-structure constant
  3. Spin-orbit coupling via Dirac bilinear currents

Usage:
    python two-fluid/cassi_dirac_bridge.py --help
    python two-fluid/cassi_dirac_bridge.py --test-dirac
"""

import sys, argparse, time, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

import torch

sys.path.insert(0, 'two-fluid')
from cassi_bridge_v2 import CassiBridgeV2, PHI, PHI_INV, PHI_INV2

# ═══════════════════════════════════════════════════════════════════════════
# Dirac Bridge: Subclass of CassiBridgeV2 with Dirac kinetic & 4-spinors
# ═══════════════════════════════════════════════════════════════════════════

class DiracBridge(CassiBridgeV2):
    """Dirac relativistic extension of the Cassi bridge.

    Replaces the Schrödinger kinetic operator (‑½∇²) with the
    Dirac Hamiltonian:
        H_D = -i c α·∇ + β m c²
    on a 4‑spinor wavefunction ψ = (ψ₁, ψ₂, ψ₃, ψ₄)^T.

    Parameters
    ----------
    grid : int
        Grid points per dimension (N³ total).
    L : float
        Physical box size (Bohr radii for atomic physics).
    mass : float
        Effective mass M (in a.u., m_e = 1 for hydrogen).
    c_light : float
        Speed of light in atomic units (default 1/α ≈ 137.036).
    alpha_disp, … : see CassiBridgeV2
    """
    def __init__(self, grid=64, L=20.0, mass=1.0, c_light=137.035999084,
                 g=0.0, phi_damp=True,
                 alpha_disp=1.0, v0=1.0,
                 alpha_yin=0.0, yin_mode='none',
                 yang_amp=0.0, yang_period=None,
                 qi_gate=False, qi_memory=False, qi_tau=None,
                 grav_sigma=0.0,
                 holographic=False, eta=0.004, beta=1.0,
                 alpha_mag=0.0, alpha_em=0.0,
                 expanding=False, H0=0.05, omega_m=0.3, omega_lambda=0.7,
                 hubble_mode='friedmann',
                 phi_gravity=False,
                 device=None):
        super().__init__(
            grid=grid, L=L, mass=mass,
            alpha_disp=alpha_disp, v0=v0,
            alpha_yin=alpha_yin, yin_mode=yin_mode,
            yang_amp=yang_amp, yang_period=yang_period,
            g=g, phi_damp=phi_damp,
            qi_gate=qi_gate, qi_memory=qi_memory, qi_tau=qi_tau,
            grav_sigma=grav_sigma,
            holographic=holographic, eta=eta, beta=beta,
            alpha_mag=alpha_mag, alpha_em=alpha_em,
            expanding=expanding, H0=H0, omega_m=omega_m,
            omega_lambda=omega_lambda, hubble_mode=hubble_mode,
            phi_gravity=phi_gravity,
            kinetic_mode='dirac',
            device=device,
        )
        # Override c (the base class sets 137.036 in _init_dirac)
        self.c = c_light

        # φ-based fine-structure coupling constant
        # α_φ = φ⁻³/(4π) ≈ 1/53 (slightly larger than α ≈ 1/137)
        self.alpha_phi = PHI_INV ** 3 / (4.0 * np.pi)

    # ── 4-Spinor Helpers ─────────────────────────────────────────────────

    def _get_density(self, psi):
        """Total probability density from a 4-spinor: Σ|ψ_i|²."""
        return (torch.abs(psi) ** 2).sum(dim=0)

    def _spinor_slices(self, psi):
        """Decompose 4-spinor into large and small components."""
        psi_L = psi[:2]   # (2, N, N, N)—large components
        psi_S = psi[2:]   # (2, N, N, N)—small components
        return psi_L, psi_S

    # ── Yang / Yin Density from 4-Spinor ────────────────────────────────

    def yang_yin_density(self, psi):
        """Compute Yang (kinetic-dominant) and Yin (rest-mass-dominant) densities.

        From the 4-spinor ψ = (ψ_L, ψ_S):
          - Yang: E_Y ∝ |ψ_L - ψ_S|²  →  kinetic dominance, r > φ
          - Yin:  E_I ∝ |ψ_L + ψ_S|²  →  rest-mass dominance, r < φ

        Returns
        -------
        yang : torch.Tensor (N, N, N)
        yin : torch.Tensor (N, N, N)
        """
        psi_L, psi_S = self._spinor_slices(psi)

        # |ψ_L - ψ_S|²  and  |ψ_L + ψ_S|²  summed over both spin orientations
        diff = psi_L - psi_S
        summ = psi_L + psi_S
        yang = (torch.abs(diff) ** 2).sum(dim=0)
        yin = (torch.abs(summ) ** 2).sum(dim=0)

        return yang, yin

    def yang_yin_ratio(self, psi):
        """E_Y / E_I—ratio of kinetic to rest-mass density.

        At the φ-point: E_Y = φ · E_I, which implies the fine-structure
        constant emerges from the golden ratio.
        """
        yang, yin = self.yang_yin_density(psi)
        ratio = yang / (yin + 1e-30)
        return ratio

    def emergent_alpha(self, psi):
        """Estimate the fine-structure constant from the Yang/Yin ratio.

        α_eff = α_φ · 2 · E_Y / (E_Y + φ·E_I)

        At the φ-point critical ratio (E_Y = φ·E_I), this gives α_eff = α_φ.
        The formula interpolates between 0 (all yin) and 2·α_φ (all yang),
        with the physical fine-structure constant emerging at the balance point.
        """
        yang, yin = self.yang_yin_density(psi)
        ratio = yang / (yin + 1e-30)
        alpha_eff = self.alpha_phi * 2.0 * ratio / (ratio + PHI)
        return float(alpha_eff.mean().item())


    # ── Energy Densities (for quantum → two-fluid seeding) ──────────────

    def energy_densities(self, psi, V_ext):
        """Compute kinetic and potential energy densities from a 4-spinor.

        Kinetic energy density (positive-definite):
            T(r) = ½ Σ_i |∇ψ_i(r)|²

        Potential energy density:
            Vρ(r) = V_ext(r) · ρ(r) = V_ext(r) · Σ_i |ψ_i(r)|²

        Returns
        -------
        T_density : torch.Tensor (N, N, N) float—normalized to sum = 1
        V_density : torch.Tensor (N, N, N) float—|V·ρ|, normalized to sum = 1
        """
        rho = self._get_density(psi)

        # Positive-definite kinetic energy density via gradient in k-space
        T = torch.zeros_like(psi[0], dtype=torch.float64)
        for i in range(4):
            if (torch.abs(psi[i]) ** 2).max() < 1e-30:
                continue
            psik = torch.fft.fftn(psi[i].to(torch.complex128))
            gx = torch.fft.ifftn(1j * self.kx * psik).real
            gy = torch.fft.ifftn(1j * self.ky * psik).real
            gz = torch.fft.ifftn(1j * self.kz * psik).real
            T += 0.5 * (gx ** 2 + gy ** 2 + gz ** 2)
        T = T.to(torch.float32)

        # Potential energy density magnitude
        Vrho = V_ext * rho
        Vrho_abs = torch.abs(Vrho)

        dV = self.dV
        T_pat = T / (T.sum() * dV + 1e-30)
        V_pat = Vrho_abs / (Vrho_abs.sum() * dV + 1e-30)

        return T_pat, V_pat
    # ── Spin Density ────────────────────────────────────────────────────

    def spin_density(self, psi):
        """Compute spin density (s_x, s_y, s_z) from Pauli expectation values.

        For each spin operator S_i = ½ σ_i (in the large-component subspace):
            s_i = ψ† · S_i · ψ   summed over volume
        For a 4-spinor:  s_i = ½ (ψ_L† σ_i ψ_L + ψ_S† σ_i ψ_S)
        """
        psi_L, psi_S = self._spinor_slices(psi)
        sx, sy, sz = self.sigma_x, self.sigma_y, self.sigma_z

        def _pauli_exp(sigma, spinor):
            # spinor has shape (2, N, N, N), sigma is (2, 2)
            # Contract: Σ_{a,b} spinor[a]^* sigma[a,b] spinor[b]
            s0 = spinor[0]
            s1 = spinor[1]
            return (torch.conj(s0) * (sigma[0, 0] * s0 + sigma[0, 1] * s1)
                    + torch.conj(s1) * (sigma[1, 0] * s0 + sigma[1, 1] * s1))

        s_x = 0.5 * (_pauli_exp(sx, psi_L) + _pauli_exp(sx, psi_S))
        s_y = 0.5 * (_pauli_exp(sy, psi_L) + _pauli_exp(sy, psi_S))
        s_z = 0.5 * (_pauli_exp(sz, psi_L) + _pauli_exp(sz, psi_S))

        return s_x, s_y, s_z

    # ── Spin Current from Dirac Bilinear ────────────────────────────────

    def compute_spin_current(self, psi):
        """Compute the spin contribution to the probability current.

        From the Dirac bilinear j^μ = ψ̄ γ^μ ψ:
          j_spin = ψ† α ψ  → (jx_s, jy_s, jz_s)
        where α_i are the Dirac alpha matrices (4×4).

        Returns tuple (jx, jy, jz) each shaped (N, N, N).
        """
        ax, ay, az = self.alpha_x, self.alpha_y, self.alpha_z

        def _alpha_exp(alpha_mat, spinor):
            # spinor (4, N, N, N), alpha_mat (4, 4)
            # ψ† α ψ = Σ_{a,b} ψ_a^* α_{a,b} ψ_b
            result = None
            for a in range(4):
                term = torch.conj(spinor[a]) * (
                    alpha_mat[a, 0] * spinor[0]
                    + alpha_mat[a, 1] * spinor[1]
                    + alpha_mat[a, 2] * spinor[2]
                    + alpha_mat[a, 3] * spinor[3]
                )
                result = term if result is None else result + term
            return result

        jx = _alpha_exp(ax, psi).real
        jy = _alpha_exp(ay, psi).real
        jz = _alpha_exp(az, psi).real

        return jx, jy, jz

    # ── Dirac Energy (overrides base class) ─────────────────────────────

    def _energy_dirac(self, psi, V_ext=None, self_consistent=True):
        """Dirac energy via k-space evaluation of ⟨H_D⟩."""
        c = self.c
        kx, ky, kz = self.kx, self.ky, self.kz

        psi_k = torch.fft.fftn(psi, dim=(1, 2, 3))
        p0, p1, p2, p3 = psi_k[0], psi_k[1], psi_k[2], psi_k[3]

        # H_D ψ in k-space
        h0 = c * (kz * p2 + (kx - 1j * ky) * p3) + c ** 2 * p0
        h1 = c * ((kx + 1j * ky) * p2 - kz * p3) + c ** 2 * p1
        h2 = c * (kz * p0 + (kx - 1j * ky) * p1) - c ** 2 * p2
        h3 = c * ((kx + 1j * ky) * p0 - kz * p1) - c ** 2 * p3

        E_k_density = (torch.conj(p0) * h0 + torch.conj(p1) * h1
                       + torch.conj(p2) * h2 + torch.conj(p3) * h3)
        E_kin = E_k_density.real.sum() * self.dV / self.N_cells

        # Potential (external + self-consistent)
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

    # ── Fine Structure Analysis ─────────────────────────────────────────

    @staticmethod
    def dirac_energy_level(n, j, Z=1.0, c_light=137.035999084):
        """Exact Dirac energy level for hydrogenic atoms.

        Parameters
        ----------
        n : int
            Principal quantum number.
        j : float
            Total angular momentum (1/2, 3/2, …).
        Z : float
            Nuclear charge.
        c_light : float
            Speed of light (1/α in atomic units).

        Returns
        -------
        E : float
            Energy in Hartree (excluding rest mass).
        """
        alpha = Z / c_light
        kappa = j + 0.5  # |κ| = j + 1/2 for Dirac
        gamma = np.sqrt(kappa ** 2 - (Z * alpha) ** 2)
        denom = n - j - 0.5 + gamma
        E_over_mc2 = (1.0 + (alpha / denom) ** 2) ** (-0.5)
        # Subtract rest mass to get binding energy in Hartree
        # E_h = m_e c² α²
        # So E (in E_h) = (E_over_mc2 - 1) * c_light**2
        return (E_over_mc2 - 1.0) * c_light ** 2

    def fine_structure_splitting(self, n=2, Z=1.0):
        """Compute fine-structure splitting for level n.

        For hydrogen (Z=1):
          ΔE = E(²P₃/₂) - E(²P₁/₂) ≈ α² R_y / 16 ≈ 4.53×10⁻⁵ eV

        Returns
        -------
        dict with 'E_j_lower', 'E_j_upper', 'splitting_Eh', 'splitting_eV',
             'alpha_phi_prediction', 'experimental_target_eV'
        """
        c = self.c
        E_lower = self.dirac_energy_level(n, 0.5, Z, c)  # j=1/2 (2S₁/₂, 2P₁/₂)
        E_upper = self.dirac_energy_level(n, 1.5, Z, c)  # j=3/2 (2P₃/₂)

        splitting_Eh = E_upper - E_lower
        splitting_eV = splitting_Eh * 27.211386245988  # 1 E_h = 27.2114 eV

        # φ-based α prediction: ΔE = α_φ² R_y / 16
        R_y = 0.5  # Rydberg energy in Hartree
        alpha_phi = PHI_INV ** 3 / (4.0 * np.pi)
        pred_Eh = alpha_phi ** 2 * R_y / 16.0
        pred_eV = pred_Eh * 27.211386245988

        # Experimental target (NIST)
        exp_eV = 4.53e-5

        return {
            'n': n, 'Z': Z,
            'E_j_lower_Eh': E_lower,
            'E_j_upper_Eh': E_upper,
            'splitting_Eh': splitting_Eh,
            'splitting_eV': splitting_eV,
            'alpha_phi': alpha_phi,
            'alpha_phi_prediction_eV': pred_eV,
            'experimental_target_eV': exp_eV,
        }

    # ── Imaginary-Time Relaxation for Dirac Hydrogen ────────────────────

    def kinetic_propagator(self, psi, dt, imaginary=False):
        """Kinetic step—dispatches to Dirac or Schrödinger.

        For imaginary-time relaxation in atomic physics, uses the
        Foldy-Wouthuysen positive-definite kinetic to avoid negative-energy
        blowup.  For real-time propagation, uses the exact Dirac operator.
        """
        if not imaginary:
            # Real time: exact Dirac exp(-i H_D dt)
            return self._kinetic_propagator_dirac(psi, dt, imaginary=False)

        # Imaginary time: use the positive Foldy-Wouthuysen kinetic
        # T_rel = sqrt(p²c² + m²c⁴) - mc²  ≥ 0
        # This avoids the negative-energy blowup of full Dirac imag-time.
        psi_k = torch.fft.fftn(psi, dim=(1, 2, 3))
        c = self.c
        E_k = torch.sqrt(c ** 2 * self.k2 + c ** 4)
        T_k = E_k - c ** 2  # relativistic kinetic energy
        factor = torch.exp(-T_k * dt)
        return torch.fft.ifftn(psi_k * factor, dim=(1, 2, 3))

    def potential_propagator(self, psi, Phi, dt, imaginary=False):
        """Potential step: exp(-i V dt) in real space.

        V is the scalar potential (Coulomb + corrections).
        Acts identically on all 4 spinor components.
        """
        rho = self._get_density(psi)
        V_eff = Phi + self.g * rho
        factor = torch.exp(-V_eff * dt) if imaginary else torch.exp(-1j * V_eff * dt)
        return psi * factor

    def schrodinger_energy(self, psi, V_ext=None):
        """Non-relativistic Schrödinger energy from a 4-spinor.

        E = -0.5 ∫ ψ† ∇² ψ dV + ∫ V ψ† ψ dV

        Sums the kinetic energy over all 4 components and adds the
        external potential on the total density (no rest mass included).
        """
        E_kin = 0.0
        for i in range(4):
            if (torch.abs(psi[i]) ** 2).max() < 1e-30:
                continue
            psi_k = torch.fft.fftn(psi[i])
            lap_k = -self.k2 * psi_k
            lap = torch.fft.ifftn(lap_k)
            E_kin += -0.5 * (torch.conj(psi[i]) * lap).sum().real * self.dV

        rho = self._get_density(psi)
        E_pot = 0.0
        if V_ext is not None:
            scale = 1.0 / self.a if self.expanding else 1.0
            E_pot = ((V_ext * scale) * rho).sum().real * self.dV

        return float((E_kin + E_pot).item())


# ═══════════════════════════════════════════════════════════════════════════
# Initial Conditions
# ═══════════════════════════════════════════════════════════════════════════

def initial_dirac_atomic(solver, sigma=1.5, spin='up'):
    """4-spinor Gaussian wave packet (Dirac-hydrogen initial condition).

    Parameters
    ----------
    solver : DiracBridge
        The solver instance (used for grid and device).
    sigma : float
        Width of the Gaussian envelope (Bohr radii).
    spin : str
        'up' → ψ₁ initialized (large up), 'down' → ψ₂ initialized.

    Returns
    -------
    psi : torch.Tensor (4, N, N, N) complex64
        Normalized 4-spinor.
    """
    # Scalar Gaussian envelope
    psi_s = (1.0 / (np.pi ** 0.75 * sigma ** 1.5)) * torch.exp(
        -solver.R ** 2 / (2.0 * sigma ** 2)
    )
    psi_s = psi_s.to(torch.complex64)
    norm_s = torch.sqrt((torch.abs(psi_s) ** 2).sum() * solver.dV)
    psi_s = psi_s / norm_s

    # 4-spinor: large components nonzero, small components zero
    psi = torch.zeros(4, solver.grid, solver.grid, solver.grid,
                      dtype=torch.complex64, device=solver.device)
    if spin == 'up':
        psi[0] = psi_s  # ψ₁ = large up
        # ψ₂ = 0 (large down)
    else:
        psi[1] = psi_s  # ψ₂ = large down

    # Normalize 4-spinor total norm to 1
    norm = torch.sqrt((torch.abs(psi) ** 2).sum() * solver.dV)
    if norm > 0:
        psi = psi / norm
    return psi


def initial_dirac_pwave(solver, sigma=2.0, spin='up', ml=0):
    """4-spinor with p-wave symmetry (for fine-structure excited states).

    Creates a p-orbital initial condition (l=1) by multiplying the
    Gaussian envelope with a linear function of coordinates.

    Parameters
    ----------
    solver : DiracBridge
    sigma : float
    spin : str
    ml : int
        Magnetic quantum number (-1, 0, 1).

    Returns
    -------
    psi : torch.Tensor (4, N, N, N) complex64
    """
    psi0 = initial_dirac_atomic(solver, sigma=sigma, spin=spin)

    # p-orbital angular factor
    if ml == 0:
        ang = solver.Z  # p_z
    elif ml == 1:
        ang = solver.X + 1j * solver.Y  # p_{+1}
    else:
        ang = solver.X - 1j * solver.Y  # p_{-1}

    # Apply to large components
    amp = torch.abs(ang)
    amp_safe = amp / (amp.max() + 1e-30)
    psi0[0] = psi0[0] * amp_safe
    psi0[1] = psi0[1] * amp_safe

    # Re-normalize
    norm = torch.sqrt((torch.abs(psi0) ** 2).sum() * solver.dV)
    if norm > 0:
        psi0 = psi0 / norm
    return psi0


# ═══════════════════════════════════════════════════════════════════════════
# Diagnostic Helpers
# ═══════════════════════════════════════════════════════════════════════════

def compute_spinor_radial(psi, R, n_bins=80):
    """Radial density profile for a 4-spinor (sum of all components)."""
    rho = (torch.abs(psi) ** 2).sum(dim=0)
    r = R.flatten().cpu().numpy()
    dr = rho.flatten().cpu().numpy()
    bins = np.linspace(0, R.max().item(), n_bins + 1)
    centers = 0.5 * (bins[:-1] + bins[1:])
    prof = np.array([
        dr[(r >= b0) & (r < b1)].mean()
        if ((r >= b0) & (r < b1)).any() else 0.0
        for b0, b1 in zip(bins[:-1], bins[1:])
    ])
    return centers, prof


def compute_spinor_components(psi, R, n_bins=80):
    """Radial profiles for each spinor component separately."""
    r = R.flatten().cpu().numpy()
    bins = np.linspace(0, R.max().item(), n_bins + 1)
    centers = 0.5 * (bins[:-1] + bins[1:])
    profiles = []
    for i in range(4):
        dr = (torch.abs(psi[i]) ** 2).flatten().cpu().numpy()
        prof = np.array([
            dr[(r >= b0) & (r < b1)].mean()
            if ((r >= b0) & (r < b1)).any() else 0.0
            for b0, b1 in zip(bins[:-1], bins[1:])
        ])
        profiles.append(prof)
    return centers, profiles


# ═══════════════════════════════════════════════════════════════════════════
# CLI Main
# ═══════════════════════════════════════════════════════════════════════════

def test_dirac_propagator(grid=32, L=20.0, sigma=1.5, steps=100, dt=0.01):
    """Test that the Dirac kinetic propagator conserves norm."""
    print(f"\n{'='*60}")
    print("DIRAC PROPAGATOR UNIT TEST")
    print(f"{'='*60}")
    print(f"  grid={grid}³  L={L:.1f}  σ={sigma}  steps={steps}  dt={dt}")

    solver = DiracBridge(grid=grid, L=L, mass=1.0, g=0.0, phi_damp=False)
    psi = initial_dirac_atomic(solver, sigma=sigma, spin='up')

    t0 = time.time()
    for step in range(steps):
        # Single real-time Dirac evolution step
        psi = solver.kinetic_propagator(psi, dt, imaginary=False)
        if step % 20 == 0 or step == steps - 1:
            norm = float((torch.abs(psi) ** 2).sum() * solver.dV)
            print(f"  step {step:4d} | norm = {norm:.10f} (deviation: {abs(norm-1):.2e})")

    elapsed = time.time() - t0
    final_norm = float((torch.abs(psi) ** 2).sum() * solver.dV)
    print(f"\n  Completed in {elapsed:.2f}s")
    print(f"  Final norm = {final_norm:.10f}  (target: 1.0)")
    print(f"  Norm conservation: {'PASS' if abs(final_norm - 1) < 1e-6 else 'FAIL'}")
    return solver


def test_initialization(grid=32, L=20.0, sigma=1.5):
    """Test the DiracBridge construction and initial state."""
    print(f"\n{'='*60}")
    print("DIRAC BRIDGE INITIALIZATION TEST")
    print(f"{'='*60}")

    solver = DiracBridge(grid=grid, L=L, mass=1.0, g=0.0, phi_damp=False)
    psi = initial_dirac_atomic(solver, sigma=sigma, spin='up')

    print(f"  psi shape: {psi.shape}  (expected: (4, {grid}, {grid}, {grid}))")
    print(f"  psi dtype: {psi.dtype}")
    print(f"  norm: {float((torch.abs(psi)**2).sum() * solver.dV):.6f}")
    print(f"  max |ψ₁|: {float(psi[0].abs().max()):.4f}")
    print(f"  max |ψ₂|: {float(psi[1].abs().max()):.4f}")
    print(f"  max |ψ₃|: {float(psi[2].abs().max()):.4f}")
    print(f"  max |ψ₄|: {float(psi[3].abs().max()):.4f}")
    print(f"  Spin up component dominant: {float(psi[0].abs().max()) > float(psi[2].abs().max())}")
    print()

    # Test Yang/Yin
    yang, yin = solver.yang_yin_density(psi)
    print(f"  Yang density mean: {float(yang.mean()):.6f}")
    print(f"  Yin density mean:  {float(yin.mean()):.6f}")
    ratio = solver.emergent_alpha(psi)
    print(f"  Emergent α (from φ): {ratio:.6f}  (α_QED = {1/137.036:.6f})")

    # Test fine-structure splitting
    fs = solver.fine_structure_splitting(n=2)
    print(f"\n  Fine-structure splitting (n=2):")
    print(f"    E(j=1/2) = {fs['E_j_lower_Eh']:+.8f} E_h")
    print(f"    E(j=3/2) = {fs['E_j_upper_Eh']:+.8f} E_h")
    print(f"    ΔE = {fs['splitting_eV']:.6e} eV")
    print(f"    φ-based prediction: {fs['alpha_phi_prediction_eV']:.6e} eV")
    print(f"    Experimental target: {fs['experimental_target_eV']:.6e} eV")

    return solver


def main():
    parser = argparse.ArgumentParser(
        description='Dirac Bridge: Relativistic QM solver for CassiBridgeV2',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python two-fluid/cassi_dirac_bridge.py --help
    python two-fluid/cassi_dirac_bridge.py --test-dirac --grid 32
    python two-fluid/cassi_dirac_bridge.py --test-init
        """,
    )
    parser.add_argument('--test-dirac', action='store_true',
                        help='Run Dirac propagator unit test')
    parser.add_argument('--test-init', action='store_true',
                        help='Test initialization and diagnostics')
    parser.add_argument('--grid', type=int, default=32,
                        help='Grid points per dimension')
    parser.add_argument('--L', type=float, default=20.0,
                        help='Box size (Bohr radii)')
    parser.add_argument('--sigma', type=float, default=1.5,
                        help='Initial Gaussian width')
    parser.add_argument('--steps', type=int, default=100,
                        help='Propagation steps')
    parser.add_argument('--dt', type=float, default=0.01,
                        help='Time step')

    args = parser.parse_args()

    if args.test_init or (not args.test_dirac):
        test_initialization(grid=args.grid, L=args.L, sigma=args.sigma)

    if args.test_dirac:
        test_dirac_propagator(grid=args.grid, L=args.L, sigma=args.sigma,
                              steps=args.steps, dt=args.dt)

    print(f"\n{'='*60}")
    print("DIRAC BRIDGE COMPLETE")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
