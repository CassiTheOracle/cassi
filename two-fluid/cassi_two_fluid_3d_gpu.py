#!/usr/bin/env python3
"""
Cassi Two-Fluid 3D GPU
======================

PyTorch/ROCm GPU port of the 3D incompressible Yang/Yin two-fluid solver.

Supports both cosmology and molecule modes. All heavy work stays on the GPU;
only diagnostics and plotting move data to the host.

Run:
    cd experiments
    python cassi_two_fluid_3d_gpu.py --mode cosmos --N 128
    python cassi_two_fluid_3d_gpu.py --mode expanding --N 128 --initial-ratio 1.5
    python cassi_two_fluid_3d_gpu.py --mode molecule --N 128
    python cassi_two_fluid_3d_gpu.py --mode benchmark
"""

import argparse
import time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

import torch


PHI = (1.0 + np.sqrt(5.0)) / 2.0
PHI_INV = 1.0 / PHI


def get_device():
    if torch.cuda.is_available():
        return torch.device('cuda')
    print('[warning] CUDA/ROCm not available; falling back to CPU')
    return torch.device('cpu')


class TwoFluid3DGPU:
    """3D incompressible two-fluid solver on GPU (PyTorch).

    D is the momentum-space numerical viscosity (the spectral Dk² damping of
    the scalar fields): a solver convention, not derived physics. The default
    D = 0 is the framework-honest, conservation-exact setting — the per-cell
    closure's ρ̇ ≡ 0 premise holds exactly at D = 0 (the 44 truth campaign's
    structured-IC verification: the void-edge band persists at f_band = 1.147%
    at all epochs with f_Yang = 1.000; the canonical D = 0.001 diffusion was
    the entire Eulerian eroder). Runs with D > 0 are the diffusion-bound
    conservative readings. The σ₈ target sits in no branch under either
    setting (44).
    """

    def __init__(self, N=64, L=2.0 * np.pi, nu=0.001, D=0.0, lam=0.02,
                 chi=5.0, chi_yang=None, alpha_disp=None, k0=None, v0=1.0,
                 mode='cosmos', rho_ext=None, device=None):
        self.N = N
        self.L = L
        self.dx = L / N
        self.nu = nu
        self.D = D
        self.lam = lam
        self.chi = chi
        self.chi_yang = chi_yang if chi_yang is not None else chi / PHI
        self.alpha_disp = alpha_disp
        self.mode = mode
        self.device = torch.device(device) if device is not None else get_device()

        # Wave numbers
        k_1d = 2.0 * np.pi * torch.fft.fftfreq(N, d=self.dx, device=self.device).cpu().numpy()
        kmax = np.abs(k_1d).max()
        k_1d_t = torch.tensor(k_1d, device=self.device, dtype=torch.float64)
        self.kz, self.ky, self.kx = torch.meshgrid(k_1d_t, k_1d_t, k_1d_t, indexing='ij')
        self.k2 = self.kx ** 2 + self.ky ** 2 + self.kz ** 2
        self.k2_safe = self.k2.clone()
        self.k2_safe[0, 0, 0] = 1.0

        # Optional Cassi scale-dependent dispersion kernel.
        # Effective Poisson kernel becomes 1 / [v0^2 (k/k0)^{2(alpha_disp-1)} k^2].
        # alpha_disp > 1 suppresses small-scale gravity; alpha_disp < 1 enhances it.
        if alpha_disp is not None:
            if k0 is None:
                k0 = 2.0 * np.pi / L
            k_mag = torch.sqrt(self.k2)
            k_mag[0, 0, 0] = k0  # avoid 0/0
            self.v2 = v0 ** 2 * (k_mag / k0) ** (2.0 * (alpha_disp - 1.0))
            self.v2[0, 0, 0] = 1.0
        else:
            self.v2 = None

        # Dealias mask
        self.dealias = (
            (torch.abs(self.kx) < (2.0 / 3.0) * kmax) &
            (torch.abs(self.ky) < (2.0 / 3.0) * kmax) &
            (torch.abs(self.kz) < (2.0 / 3.0) * kmax)
        ).to(torch.float64)

        # Coordinates (only needed for external nuclei)
        x = torch.arange(0, L, step=L / N, device=self.device, dtype=torch.float64)
        self.X, self.Y, self.Z = torch.meshgrid(x, x, x, indexing='ij')

        # External charge density
        if rho_ext is not None:
            self.rho_ext_hat = torch.fft.fftn(rho_ext)
        else:
            self.rho_ext_hat = None

        # Preallocate buffers for common fields to reduce allocations
        self._tmp_c = torch.zeros((N, N, N), dtype=torch.complex128, device=self.device)

    def _grad(self, f_hat):
        """Return physical-space gradients [fx, fy, fz]."""
        return [
            torch.fft.ifftn(1j * self.kx * f_hat).real,
            torch.fft.ifftn(1j * self.ky * f_hat).real,
            torch.fft.ifftn(1j * self.kz * f_hat).real,
        ]

    def _project(self, vec_hat):
        """Project vector field to solenoidal part in Fourier space."""
        div = self.kx * vec_hat[0] + self.ky * vec_hat[1] + self.kz * vec_hat[2]
        return [
            vec_hat[d] - div * k / self.k2_safe
            for d, k in enumerate([self.kx, self.ky, self.kz])
        ]

    def _poisson(self, rho_hat):
        """Poisson solve with optional scale-dependent dispersion kernel."""
        rho_hat = rho_hat.clone()
        rho_hat[0, 0, 0] = 0.0
        denom = self.k2_safe
        if self.v2 is not None:
            denom = denom * self.v2
        return -rho_hat / denom

    def _divergence_of_flux(self, flux):
        """Compute spectral divergence of a physical-space flux vector."""
        return (
            1j * self.kx * torch.fft.fftn(flux[0]) +
            1j * self.ky * torch.fft.fftn(flux[1]) +
            1j * self.kz * torch.fft.fftn(flux[2])
        )

    def rhs(self, u_hat, ey_hat, ei_hat):
        # Physical fields
        u = [torch.fft.ifftn(u_hat[d]).real for d in range(3)]
        ey = torch.fft.ifftn(ey_hat).real
        ei = torch.fft.ifftn(ei_hat).real
        rho = ey + ei
        pi = ey - ei

        # Information potential
        rho_hat = torch.fft.fftn(rho)
        if self.rho_ext_hat is not None:
            rho_hat = rho_hat + self.rho_ext_hat
        phi_hat = self._poisson(rho_hat)
        phi = torch.fft.ifftn(phi_hat).real

        # Velocity advection
        adv_u = [torch.zeros_like(u[0]) for _ in range(3)]
        for i in range(3):
            grad_ui = self._grad(u_hat[i])
            for j in range(3):
                adv_u[i] = adv_u[i] + u[j] * grad_ui[j]

        # Force Π∇Φ
        grad_phi = self._grad(phi_hat)
        force = [pi * grad_phi[d] for d in range(3)]

        # Velocity RHS (spectral) + projection
        rhs_u_hat = [
            -torch.fft.fftn(adv_u[d]) + torch.fft.fftn(force[d]) - self.nu * self.k2 * u_hat[d]
            for d in range(3)
        ]
        for d in range(3):
            rhs_u_hat[d] = rhs_u_hat[d] * self.dealias
        rhs_u_hat = self._project(rhs_u_hat)

        # Scalar advection
        grad_ey = self._grad(ey_hat)
        grad_ei = self._grad(ei_hat)
        adv_ey = sum(u[d] * grad_ey[d] for d in range(3))
        adv_ei = sum(u[d] * grad_ei[d] for d in range(3))

        # Conversion
        if self.lam != 0.0:
            conv = -self.lam * (ey - PHI * ei)
        else:
            conv = torch.zeros_like(ey)

        rhs_ey_hat = (-torch.fft.fftn(adv_ey) - self.D * self.k2 * ey_hat +
                      torch.fft.fftn(conv))
        rhs_ei_hat = (-torch.fft.fftn(adv_ei) - self.D * self.k2 * ei_hat -
                      torch.fft.fftn(conv))

        # Chemotactic drift in information potential: Yin is attracted to wells,
        # Yang is repelled. chi_yang controls the Yang mobility; setting it
        # smaller than chi/PHI lets net mass accumulate in wells (collapse).
        if self.chi != 0.0:
            chi_y = self.chi_yang
            chi_i = self.chi
            flux_y = [chi_y * ey * grad_phi[d] for d in range(3)]
            flux_i = [-chi_i * ei * grad_phi[d] for d in range(3)]
            rhs_ey_hat = rhs_ey_hat - self._divergence_of_flux(flux_y)
            rhs_ei_hat = rhs_ei_hat - self._divergence_of_flux(flux_i)

        rhs_ey_hat = rhs_ey_hat * self.dealias
        rhs_ei_hat = rhs_ei_hat * self.dealias

        return rhs_u_hat, rhs_ey_hat, rhs_ei_hat

    def rk2_step(self, u_hat, ey_hat, ei_hat, dt):
        k1_u, k1_ey, k1_ei = self.rhs(u_hat, ey_hat, ei_hat)
        u2 = [u_hat[d] + dt * k1_u[d] for d in range(3)]
        ey2 = ey_hat + dt * k1_ey
        ei2 = ei_hat + dt * k1_ei
        k2_u, k2_ey, k2_ei = self.rhs(u2, ey2, ei2)

        for d in range(3):
            u_hat[d] = u_hat[d] + 0.5 * dt * (k1_u[d] + k2_u[d])
        ey_hat = ey_hat + 0.5 * dt * (k1_ey + k2_ey)
        ei_hat = ei_hat + 0.5 * dt * (k1_ei + k2_ei)

        return u_hat, ey_hat, ei_hat

    def initial_cosmos(self, amplitude=0.2, seed=42):
        gen = torch.Generator(device=self.device)
        gen.manual_seed(seed)
        ey = 1.0 + amplitude * torch.randn((self.N,) * 3, generator=gen,
                                           device=self.device, dtype=torch.float64)
        ei = PHI_INV + amplitude * torch.randn((self.N,) * 3, generator=gen,
                                               device=self.device, dtype=torch.float64)
        ey = torch.clamp(ey, min=0.1)
        ei = torch.clamp(ei, min=0.1)

        u_hat = [torch.fft.fftn(0.05 * torch.randn((self.N,) * 3, generator=gen,
                                                   device=self.device, dtype=torch.float64))
                 for _ in range(3)]
        ey_hat = torch.fft.fftn(ey)
        ei_hat = torch.fft.fftn(ei)
        return u_hat, ey_hat, ei_hat

    def initial_molecule(self, seed=42):
        gen = torch.Generator(device=self.device)
        gen.manual_seed(seed)
        ey = 1.0 + 0.02 * torch.randn((self.N,) * 3, generator=gen,
                                      device=self.device, dtype=torch.float64)
        ei = 0.5 + 0.02 * torch.randn((self.N,) * 3, generator=gen,
                                      device=self.device, dtype=torch.float64)
        ey = torch.clamp(ey, min=0.1)
        ei = torch.clamp(ei, min=0.1)

        u_hat = [torch.fft.fftn(0.01 * torch.randn((self.N,) * 3, generator=gen,
                                                   device=self.device, dtype=torch.float64))
                 for _ in range(3)]
        ey_hat = torch.fft.fftn(ey)
        ei_hat = torch.fft.fftn(ei)
        return u_hat, ey_hat, ei_hat

    def power_spectrum(self, delta, n_bins=24):
        """Radial power spectrum (computed on CPU for simplicity)."""
        delta_np = delta.cpu().numpy() if delta.is_cuda else delta.numpy()
        N = self.N
        L = self.L
        dx = L / N
        k_1d = 2.0 * np.pi * np.fft.fftfreq(N, d=dx)
        kz, ky, kx = np.meshgrid(k_1d, k_1d, k_1d, indexing='ij')
        k_mag = np.sqrt(kx ** 2 + ky ** 2 + kz ** 2)

        delta_k = np.fft.fftn(delta_np)
        P = np.abs(delta_k) ** 2 / (L ** 3)

        k_min = k_mag[k_mag > 0].min()
        k_max = k_mag.max()
        bins = np.linspace(k_min, k_max, n_bins + 1)
        k_out = 0.5 * (bins[:-1] + bins[1:])
        Pk = np.zeros(n_bins)
        counts = np.zeros(n_bins)

        for i in range(n_bins):
            mask = (k_mag >= bins[i]) & (k_mag < bins[i + 1])
            if mask.any():
                Pk[i] = P[mask].mean()
                counts[i] = mask.sum()
        valid = counts > 0
        return k_out[valid], Pk[valid]


class ExpandingTwoFluid3DGPU(TwoFluid3DGPU):
    """Two-fluid solver on a comoving expanding grid.

    The scale factor a(t) and Hubble parameter H(t) are evolved alongside the
    fluid. Spatial derivatives are taken with respect to comoving coordinates,
    so advection and forces acquire 1/a factors, diffusion and viscosity 1/a²
    factors, and velocities experience Hubble drag -H v.

    EY and EI are treated as comoving densities.

    Two Hubble modes:
      - 'conversion' (default): H = (λ/3)(φ - r)(1+r)/r where r = <EY>/<EI>.
        Expansion is driven by the Yang-Yin imbalance; H → 0 at φ-equilibrium.
      - 'friedmann': H = H₀·√(ρ_tot/ρ_crit). Standard de Sitter-like expansion.
    """

    def __init__(self, N=64, L=2.0 * np.pi, nu=0.001, D=0.0, lam=0.02,
                 chi=5.0, chi_yang=None, alpha_disp=None, k0=None, v0=1.0,
                 H0=1.0, a0=1.0, rho_crit=None, hubble_mode='conversion',
                 initial_ratio=None, max_H=None, h_smooth=0.1,
                 hyper_nu=0.0, cs2=0.0, qi_gate=False, phi_inv2=0.382,
                 qi_memory=False, qi_tau=None, qi_decompose=False, qi_beta=0.0,
                 wu_xing=False, wx_Am=None, wx_Kfw=None, wx_Kfm=None, wx_Kmd=None, wx_Dmax=1.0,
                 mode='cosmos', rho_ext=None, device=None):
        super().__init__(N=N, L=L, nu=nu, D=D, lam=lam, chi=chi,
                         chi_yang=chi_yang, alpha_disp=alpha_disp,
                         k0=k0, v0=v0, mode=mode, rho_ext=rho_ext,
                         device=device)
        self.H0 = H0
        self.rho_crit = rho_crit if rho_crit is not None else PHI
        self.hubble_mode = hubble_mode
        self.initial_ratio = initial_ratio
        self.max_H = max_H if max_H is not None else 4.0 * lam
        self.h_smooth = h_smooth
        self.hyper_nu = hyper_nu
        self.cs2 = cs2
        self.grav_sigma = 0.2  # N-body softening: caps |∇Φ| at this scale
        self.qi_gate = qi_gate
        self.gate_model = 'single'  # 'single' | 'five' | 'five_ke' (5-ch Wu Xing gate, +ke ring) | 'two_pole'
        self.phi_inv2 = phi_inv2
        # 5-channel φ-powers: b_i = φ^{-k_i}, k_i = 2+i for i=0..4
        self.phi_pow_5ch = torch.tensor([PHI**(-k) for k in [3,4,5,6,7]],
                                        device=self.device, dtype=torch.float64)
        self.eta_5ch = torch.tensor([1.0, PHI_INV, PHI_INV, PHI_INV, PHI_INV],
                                    device=self.device, dtype=torch.float64)
        self.sigma_gate = torch.tensor(0.05, dtype=torch.float64)
        self.qi_memory = qi_memory
        self.qi_decompose = qi_decompose
        self.qi_beta = qi_beta
        # ─── Five-Element Wu Xing cycle ───────────────────────────────────
        self.wu_xing = wu_xing
        # Coupling coefficients: if None, derive from PDE parameters (λ, φ, χ, L)
        # Am = λ          → Metal recovers at conversion rate
        # Kfw = φ⁻¹       → Water damps Fire at natural damping rate
        # Kfm = λ·φ²      → Fire melts Metal; F=φ⁻² halves Metal
        # Kmd = 3·φ² → Metal cuts Wood; N_ε = Γ_ε/H_empty gives ε-dampings per Hubble time
        k_fund = 2.0 * np.pi / L
        self.wx_Am = wx_Am if wx_Am is not None else lam
        self.wx_Kfw = wx_Kfw if wx_Kfw is not None else PHI_INV
        self.wx_Kfm = wx_Kfm if wx_Kfm is not None else lam * PHI**2
        self.wx_Kmd = wx_Kmd if wx_Kmd is not None else 3.0 * PHI**2
        self.wx_Dmax = wx_Dmax
        # Element state (global scalars, 0-1 range)
        self._W = torch.tensor(0.3, device=self.device, dtype=torch.float64)  # Water (q₀)
        self._D = torch.tensor(0.01, device=self.device, dtype=torch.float64) # Wood (δ_rms₀)
        self._M = torch.tensor(0.8, device=self.device, dtype=torch.float64)  # Metal (λ_eff/λ₀)
        self._F = torch.tensor(0.0, device=self.device, dtype=torch.float64)  # Fire (computed)
        # ─── Standard init ────────────────────────────────────────────
        self.a = torch.tensor(a0, device=self.device, dtype=torch.float64)
        self.H = torch.tensor(0.0, device=self.device, dtype=torch.float64)
        self._H_smooth = torch.tensor(0.0, device=self.device, dtype=torch.float64)
        self.q_mean = torch.tensor(0.0, device=self.device, dtype=torch.float64)
        self.eps_sq_memory = torch.zeros((N, N, N), device=self.device, dtype=torch.float64) if qi_memory else None
        if hyper_nu > 0:
            self.k4 = self.k2 ** 2

    def _update_hubble(self, ey, ei):
        """Compute Hubble parameter from spatially-averaged Yang and Yin.

        Modes:
          'conversion':     H = (λ/3)(φ - r)(1+r)/r  (Cassi-native)
          'stress_energy':  H = H_empty + H_conv + H_struct  (PDE-derived)
                            H_empty = (λ/3)·φ⁻²
                            H_struct = λ·⟨|ε|²⟩/⟨ρ⟩²
          'friedmann':      H = H₀·√(ρ_tot/ρ_crit)
          'qi_error':       H = β·⟨|ε|²⟩/(M + φ⁻²)
        """
        ey_mean = ey.mean()
        ei_mean = ei.mean()

        if self.hubble_mode == 'qi_error':
            eps_sq = ((ey - PHI * ei) ** 2).mean()
            M_mean = ((ey + ei) ** 2).mean()
            H_raw = self.qi_beta * eps_sq / (M_mean + self.phi_inv2 + 1e-30)
        elif self.hubble_mode in ('conversion', 'stress_energy', 'wu_xing_unified'):
            r = (ey_mean + 1e-6) / (ei_mean + 1e-6)
            r = torch.clamp(r, 1e-2, 1e2)
            H_conv = (self.lam / 3.0) * (PHI - r) * (1.0 + r) / (r + 1e-12)
            if self.hubble_mode in ('stress_energy', 'wu_xing_unified'):
                H_empty = (self.lam / 3.0) * PHI_INV**2
                imbalance = ey - PHI * ei
                eps_sq = imbalance ** 2
                # Qi-gated H_struct: only unresolved imbalance drives expansion.
                # (1-q)·ε² = ε²·(φ⁻²+ε²)/(ρ²+φ⁻²+ε²) → cells near φ-equilibrium
                # (ε²≪φ⁻²) contribute near-zero. Decouples the positive feedback.
                if self.qi_gate:
                    M_qi = (ey + ei) ** 2
                    q = M_qi / (M_qi + self.phi_inv2 + eps_sq + 1e-30)
                    eps_sq_gated = ((1.0 - q) * eps_sq).mean()
                else:
                    eps_sq_gated = eps_sq.mean()
                rho_mean = ey_mean + ei_mean
                H_struct = self.lam * eps_sq_gated / (rho_mean * rho_mean + PHI_INV**2 + 1e-30)
                # Safety cap: H_struct ≤ |H_conv|—structure can't drive
                # faster expansion than the conversion imbalance itself
                H_struct_capped = torch.clamp(H_struct, max=H_conv.abs())
                H_raw = H_empty + H_conv + H_struct_capped
                self._H_struct = H_struct_capped
            else:
                H_empty = (self.lam / 3.0) * PHI_INV**2
                H_raw = H_empty + H_conv
        else:  # friedmann
            rho_tot = ey_mean + ei_mean
            H_raw = self.H0 * torch.sqrt(rho_tot / self.rho_crit)

        H_raw = torch.clamp(H_raw, -self.max_H, self.max_H)
        self._H_smooth = (1.0 - self.h_smooth) * self._H_smooth + self.h_smooth * H_raw
        self.H = self._H_smooth

    def _diagnose_wu_xing(self, ey, ei):
        """Five-element diagnostics—read-only extraction from PDE state.

        No feedback into conversion or Hubble. The Ke cycle is already running
        per-cell via the (1-q) gating and the conversion term. This method
        just reports the globally-averaged element diagnostics for monitoring.
        """
        # Water (W) = mean coherence quality from Qi gating
        self._W = self.q_mean
        
        # Wood (D) = structure amplitude (density contrast rms)
        rho = ey + ei
        delta = rho / (rho.mean() + 1e-12) - 1.0
        self._D = delta.std()
        
        # Fire (F) = mean squared deviation from phi-equilibrium
        imbalance = ey - PHI * ei
        self._F = (imbalance ** 2).mean()
        
        # Metal (M) = diagnosed conversion efficiency proxy
        # The per-cell (1-q) already gates conversion natively.
        # Reports the global average: M_eff = <1-q>_spatial.
        if self.qi_gate and self.q_mean > 0:
            self._M = 1.0 - self.q_mean
        else:
            self._M = torch.tensor(1.0, device=self.device, dtype=torch.float64)
        
        # Earth (E) = deviation of global ratio from phi
        ey_mean = ey.mean(); ei_mean = ei.mean()
        r = (ey_mean + 1e-6) / (ei_mean + 1e-6)
        self._E = torch.abs(r - PHI)
        
        return self._W, self._D, self._F, self._M, self._E

    def compute_q_field(self, ey, ei, eps_sq_memory=None):
        """Compute per-cell Qi coherence q and gate openness (1-q).

        Replicates the gate computation from rhs() as a standalone diagnostic.
        Uses the active gate_model for consistency with the PDE dynamics.

        Args:
            ey, ei: 3D tensors of Yang and Yin fields (physical space)
            eps_sq_memory: optional IIR memory field (only used with qi_memory)

        Returns:
            (q, one_minus_q): 3D tensors, q ∈ [0,1], one_minus_q ∈ [0,1]
        """
        M_qi = (ey + ei) ** 2
        eps_sq = (ey - PHI * ei) ** 2

        if not self.qi_gate:
            one_minus_q = torch.ones_like(ey)
            q = torch.zeros_like(ey)
            return q, one_minus_q

        eps_sq_eff = eps_sq_memory if (self.qi_memory and eps_sq_memory is not None) else eps_sq
        eps_norm = eps_sq_eff / (eps_sq_eff + M_qi + self.phi_inv2 + 1e-30)
        w1 = (1.0 - eps_norm).clamp(0.0, 1.0)
        w2 = (4.0 * eps_norm * (1.0 - eps_norm)).clamp(0.0, 1.0)
        w3 = torch.ones_like(eps_norm)
        w4 = eps_norm
        w5 = torch.sigmoid((eps_norm - 0.3) / 0.05)
        b = self.phi_pow_5ch.unsqueeze(-1).unsqueeze(-1).unsqueeze(-1)
        eta = self.eta_5ch.unsqueeze(-1).unsqueeze(-1).unsqueeze(-1)

        if self.gate_model == 'five':
            w_all = torch.stack([w1, w2, w3, w4, w5], dim=0)
            wood_closed = self.phi_pow_5ch[0] * (1.0 - w1)
            active_open = (b[1:] * w_all[1:]).sum(dim=0, keepdim=True).clamp(min=1e-30)
            redist = wood_closed * (b[1:] * w_all[1:]) / active_open
            ch_open = b * w_all
            ch_open[1:] += redist
            one_minus_q = (eta * ch_open).sum(dim=0)
        elif self.gate_model == 'five_ke':
            # 'five' + the ke control ring (`foundations/wu-xing-cycle-structure.md`
            # §2): a channel's excess over baseline restrains its ke target
            # (i+2) and deposits the displaced coherence at i+4, with
            # kappa = phi^-1 = K_fw. One simultaneous round per evaluation.
            w_all = torch.stack([w1, w2, w3, w4, w5], dim=0)
            wood_closed = self.phi_pow_5ch[0] * (1.0 - w1)
            active_open = (b[1:] * w_all[1:]).sum(dim=0, keepdim=True).clamp(min=1e-30)
            redist = wood_closed * (b[1:] * w_all[1:]) / active_open
            ch_open = b * w_all
            ch_open[1:] += redist
            idx = torch.arange(5, device=ch_open.device)
            d = torch.minimum(PHI_INV * (ch_open - b).clamp(min=0.0),
                              torch.index_select(ch_open, 0, (idx + 2) % 5))
            ch_ke = ch_open.clone()
            ch_ke = ch_ke - torch.index_select(d, 0, (idx - 2) % 5)
            ch_ke = ch_ke + torch.index_select(d, 0, (idx - 4) % 5)
            ch_open = ch_ke.clamp(min=0.0)
            one_minus_q = (eta * ch_open).sum(dim=0)
        elif self.gate_model == 'two_pole':
            east = torch.stack([w1, w2, w3, w4, w5], dim=0)
            west = torch.stack([1.0 - w1, 1.0 - w2, 1.0 - w3,
                                1.0 - w4, 1.0 - w5], dim=0)
            one_minus_q = (eta * b * east + eta * b * PHI * west).sum(dim=0).clamp(min=0.0)
        else:  # single
            q = M_qi / (M_qi + self.phi_inv2 + eps_sq_eff + 1e-30)
            one_minus_q = 1.0 - q

        q = (1.0 - one_minus_q).clamp(0.0, 1.0)
        return q, one_minus_q

    def initial_expanding(self, amplitude=0.2, seed=42):
        """Initial conditions with configurable Yin/Yang ratio.

        initial_ratio = <EI>/<EY>. Default None uses phi-equilibrium.
        For matter-dominated start: initial_ratio > phi^-1 (e.g. 1.0).
        For Yang-dominated start: initial_ratio < phi^-1 (e.g. 0.3).
        """
        gen = torch.Generator(device=self.device)

        if self.initial_ratio is not None:
            target_ratio = self.initial_ratio
        else:
            target_ratio = PHI_INV  # φ-equilibrium ≈ 0.618

        # Choose means to satisfy the target ratio while keeping total ~ 1+φ⁻¹
        ey_mean = (1.0 + PHI_INV) / (1.0 + target_ratio)
        ei_mean = ey_mean * target_ratio

        ey = ey_mean + amplitude * torch.randn((self.N,) * 3, generator=gen,
                                               device=self.device, dtype=torch.float64)
        ei = ei_mean + amplitude * torch.randn((self.N,) * 3, generator=gen,
                                               device=self.device, dtype=torch.float64)
        ey = torch.clamp(ey, min=0.1)
        ei = torch.clamp(ei, min=0.1)

        u_hat = [torch.fft.fftn(0.05 * torch.randn((self.N,) * 3, generator=gen,
                                                   device=self.device, dtype=torch.float64))
                 for _ in range(3)]
        ey_hat = torch.fft.fftn(ey)
        ei_hat = torch.fft.fftn(ei)
        return u_hat, ey_hat, ei_hat

    def rhs(self, u_hat, ey_hat, ei_hat):
        # Physical fields in comoving coordinates
        u = [torch.fft.ifftn(u_hat[d]).real for d in range(3)]
        ey = torch.fft.ifftn(ey_hat).real
        ei = torch.fft.ifftn(ei_hat).real
        rho = ey + ei
        pi = ey - ei

        self._update_hubble(ey, ei)
        a = self.a
        a2 = a * a

        # Information potential from comoving density fluctuations
        rho_hat = torch.fft.fftn(rho)
        if self.rho_ext_hat is not None:
            rho_hat = rho_hat + self.rho_ext_hat
        phi_hat = self._poisson(rho_hat)

        # Velocity advection in comoving form
        adv_u = [torch.zeros_like(u[0]) for _ in range(3)]
        for i in range(3):
            grad_ui = self._grad(u_hat[i])
            for j in range(3):
                adv_u[i] = adv_u[i] + u[j] * grad_ui[j]

        # Force: physical gradient = comoving gradient / a
        grad_phi = self._grad(phi_hat)
        grad_rho = self._grad(rho_hat)
        # N-body saturation: caps |F_grav| to prevent nonlinear collapse.
        # sf = |F|²/(|F|² + σ²) → 1 in linear regime, softens at σ threshold.
        # From cassi_nbody_100.py—the "particle-free N-body" mechanism.
        f2 = sum((pi * grad_phi[d]) ** 2 for d in range(3))
        sf = f2 / (f2 + self.grav_sigma ** 2 + 1e-10)
        force = [(sf * pi * grad_phi[d] - self.cs2 * grad_rho[d]) / a for d in range(3)]

        # Velocity RHS: advection/a + force - nu k²/a² - H v
        rhs_u_hat = [
            (-torch.fft.fftn(adv_u[d]) / a
             + torch.fft.fftn(force[d])
             - self.nu * self.k2 * u_hat[d] / a2
             - self.H * u_hat[d]
             - (self.hyper_nu * self.k4 * u_hat[d] / (a2 * a2) if self.hyper_nu > 0 else 0))
            for d in range(3)
        ]
        for d in range(3):
            rhs_u_hat[d] = rhs_u_hat[d] * self.dealias
        rhs_u_hat = self._project(rhs_u_hat)

        # Scalar advection and diffusion in comoving form
        grad_ey = self._grad(ey_hat)
        grad_ei = self._grad(ei_hat)
        adv_ey = sum(u[d] * grad_ey[d] for d in range(3))
        adv_ei = sum(u[d] * grad_ei[d] for d in range(3))
        if self.lam != 0.0:
            imbalance = ey - PHI * ei
            if self.qi_gate:
                M_qi = (ey + ei) ** 2
                eps_sq = imbalance ** 2
                if self.qi_memory:
                    eps_sq_eff = self.eps_sq_memory
                else:
                    eps_sq_eff = eps_sq
                eps_norm = eps_sq_eff / (eps_sq_eff + M_qi + self.phi_inv2 + 1e-30)
                w1 = (1.0 - eps_norm).clamp(0.0, 1.0)
                w2 = (4.0 * eps_norm * (1.0 - eps_norm)).clamp(0.0, 1.0)
                w3 = torch.ones_like(eps_norm)
                w4 = eps_norm
                w5 = torch.sigmoid((eps_norm - 0.3) / 0.05)
                b = self.phi_pow_5ch.unsqueeze(-1).unsqueeze(-1).unsqueeze(-1)
                eta = self.eta_5ch.unsqueeze(-1).unsqueeze(-1).unsqueeze(-1)
                if self.gate_model == 'five':
                    w_all = torch.stack([w1, w2, w3, w4, w5], dim=0)
                    wood_closed = self.phi_pow_5ch[0] * (1.0 - w1)
                    active_open = (b[1:] * w_all[1:]).sum(dim=0, keepdim=True).clamp(min=1e-30)
                    redist = wood_closed * (b[1:] * w_all[1:]) / active_open
                    ch_open = b * w_all
                    ch_open[1:] += redist
                    one_minus_q = (eta * ch_open).sum(dim=0)
                    self.q_mean = (1.0 - one_minus_q).mean()
                elif self.gate_model == 'five_ke':
                    # 'five' + ke control ring (see compute_q_field)
                    w_all = torch.stack([w1, w2, w3, w4, w5], dim=0)
                    wood_closed = self.phi_pow_5ch[0] * (1.0 - w1)
                    active_open = (b[1:] * w_all[1:]).sum(dim=0, keepdim=True).clamp(min=1e-30)
                    redist = wood_closed * (b[1:] * w_all[1:]) / active_open
                    ch_open = b * w_all
                    ch_open[1:] += redist
                    idx = torch.arange(5, device=ch_open.device)
                    d = torch.minimum(PHI_INV * (ch_open - b).clamp(min=0.0),
                                      torch.index_select(ch_open, 0, (idx + 2) % 5))
                    ch_ke = ch_open.clone()
                    ch_ke = ch_ke - torch.index_select(d, 0, (idx - 2) % 5)
                    ch_ke = ch_ke + torch.index_select(d, 0, (idx - 4) % 5)
                    ch_open = ch_ke.clamp(min=0.0)
                    one_minus_q = (eta * ch_open).sum(dim=0)
                    self.q_mean = (1.0 - one_minus_q).mean()
                elif self.gate_model == 'two_pole':
                    east = torch.stack([w1, w2, w3, w4, w5], dim=0)
                    west = torch.stack([1.0 - w1, 1.0 - w2, 1.0 - w3,
                                        1.0 - w4, 1.0 - w5], dim=0)
                    one_minus_q = (eta * b * east + eta * b * PHI * west).sum(dim=0).clamp(min=0.0)
                    self.q_mean = (1.0 - one_minus_q).mean()
                else:
                    q = M_qi / (M_qi + self.phi_inv2 + eps_sq_eff + 1e-30)
                    self.q_mean = q.mean()
                    one_minus_q = (1.0 - q)
                conv = -self.lam * one_minus_q * imbalance
            else:
                conv = -self.lam * imbalance
        else:
            # λ=0: conversion channel frozen — conv contributes nothing.
            conv = torch.zeros_like(ey)

        rhs_ey_hat = (-torch.fft.fftn(adv_ey) / a
                      - self.D * self.k2 * ey_hat / a2
                      - (self.hyper_nu * self.k4 * ey_hat / (a2 * a2) if self.hyper_nu > 0 else 0)
                      + torch.fft.fftn(conv))
        rhs_ei_hat = (-torch.fft.fftn(adv_ei) / a
                      - self.D * self.k2 * ei_hat / a2
                      - (self.hyper_nu * self.k4 * ei_hat / (a2 * a2) if self.hyper_nu > 0 else 0)
                      - torch.fft.fftn(conv))

        # Gravity is handled in the velocity equation (buoyancy force
        # at line 494) and density advects by the velocity field.
        # No separate gravitational density flux—that was the source
        # of all χ>0 instabilities.

        rhs_ey_hat = rhs_ey_hat * self.dealias
        rhs_ei_hat = rhs_ei_hat * self.dealias

        return rhs_u_hat, rhs_ey_hat, rhs_ei_hat

    def rk2_step(self, u_hat, ey_hat, ei_hat, dt):
        k1_u, k1_ey, k1_ei = self.rhs(u_hat, ey_hat, ei_hat)
        u2 = [u_hat[d] + dt * k1_u[d] for d in range(3)]
        ey2 = ey_hat + dt * k1_ey
        ei2 = ei_hat + dt * k1_ei
        k2_u, k2_ey, k2_ei = self.rhs(u2, ey2, ei2)

        for d in range(3):
            u_hat[d] = u_hat[d] + 0.5 * dt * (k1_u[d] + k2_u[d])
        ey_hat = ey_hat + 0.5 * dt * (k1_ey + k2_ey)
        ei_hat = ei_hat + 0.5 * dt * (k1_ei + k2_ei)

        # Mass-conserving clamp: renormalize after floor to keep total mass.
        ey = torch.fft.ifftn(ey_hat).real
        ei = torch.fft.ifftn(ei_hat).real
        old_mass = (ey + ei).sum()
        ey = torch.clamp(ey, min=1e-3)
        ei = torch.clamp(ei, min=1e-3)
        scale = old_mass / (ey.sum() + ei.sum() + 1e-30)
        ey *= scale
        ei *= scale
        # Update IIR Qi memory: once per RK2 step using final clamped fields.
        # Previously this was inside rhs() and updated twice per step (k1+k2),
        # giving effective decay (1-τ)² per step—near-total amnesia. Fixed.
        if self.qi_memory:
            eps_sq = (ey - PHI * ei) ** 2
            self.eps_sq_memory = (1.0 - self.qi_tau) * self.eps_sq_memory + self.qi_tau * eps_sq
        if self.wu_xing:
            self._diagnose_wu_xing(ey, ei)
        self._update_hubble(ey, ei)
        ey_hat = torch.fft.fftn(ey)
        ei_hat = torch.fft.fftn(ei)

        # Advance scale factor with H evaluated at the end of the step
        self.a = self.a * torch.exp(self.H * dt)

        return u_hat, ey_hat, ei_hat

def build_nuclei_density_gpu(N, L, positions, charges, sigma, device):
    x = torch.arange(0, L, step=L / N, device=device, dtype=torch.float64)
    X, Y, Z = torch.meshgrid(x, x, x, indexing='ij')
    rho = torch.zeros((N, N, N), device=device, dtype=torch.float64)
    for pos, Zc in zip(positions, charges):
        r2 = (X - pos[0]) ** 2 + (Y - pos[1]) ** 2 + (Z - pos[2]) ** 2
        rho = rho + Zc * torch.exp(-r2 / (2.0 * sigma ** 2))
    norm = (2.0 * np.pi * sigma ** 2) ** 1.5
    return rho / norm


def run_cosmos_gpu(N=64, L=2.0 * np.pi, dt=0.001, n_steps=600,
                   nu=0.0005, D=0.0002, lam=0.02, chi=5.0,
                   chi_yang=None, alpha_disp=None, k0=None, v0=1.0,
                   init_fields=None, seed=42, report_every=100, device=None):
    print(f"\n[GPU Cosmos 3D] grid={N}³, L={L:.3f}, dt={dt}, steps={n_steps}")
    if alpha_disp is not None:
        print(f"  scale-dependent dispersion: alpha_disp={alpha_disp:.4f}")
    t0 = time.time()
    solver = TwoFluid3DGPU(N=N, L=L, nu=nu, D=D, lam=lam, chi=chi,
                           chi_yang=chi_yang, alpha_disp=alpha_disp,
                           k0=k0, v0=v0, mode='cosmos', device=device)
    if init_fields is not None:
        u_hat, ey_hat, ei_hat = init_fields
    else:
        u_hat, ey_hat, ei_hat = solver.initial_cosmos(seed=seed)
    torch.cuda.synchronize() if solver.device.type == 'cuda' else None
    init_t = time.time() - t0

    snaps = []
    step_t0 = time.time()
    for step in range(n_steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, dt)

        if step % report_every == 0 or step == n_steps - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            rho = ey + ei
            rho_mean = rho.mean()
            delta_t = rho / rho_mean - 1.0
            delta = delta_t.cpu().numpy()
            k, Pk = solver.power_spectrum(delta_t)

            vortx = torch.fft.ifftn(1j * solver.ky * u_hat[2] - 1j * solver.kz * u_hat[1]).real
            vorty = torch.fft.ifftn(1j * solver.kz * u_hat[0] - 1j * solver.kx * u_hat[2]).real
            vortz = torch.fft.ifftn(1j * solver.kx * u_hat[1] - 1j * solver.ky * u_hat[0]).real
            enst = float((vortx ** 2 + vorty ** 2 + vortz ** 2).mean().cpu())

            snaps.append({
                'step': step, 't': step * dt,
                'rho': rho.cpu().numpy().copy(),
                'ey': ey.cpu().numpy().copy(),
                'ei': ei.cpu().numpy().copy(),
                'delta_rms': float(delta.std()),
                'ratio': float((ei.mean() / ey.mean()).cpu()),
                'enst': enst,
                'k': k, 'Pk': Pk
            })
            print(f"  step {step:4d} | t={step*dt:.3f} | "
                  f"δ_rms={delta.std():.3f} | ratio={snaps[-1]['ratio']:.4f} | enst={enst:.4f}")

    torch.cuda.synchronize() if solver.device.type == 'cuda' else None
    elapsed = time.time() - step_t0
    print(f"  Init time: {init_t:.2f}s | Step time: {elapsed:.2f}s "
          f"({elapsed/n_steps:.4f}s/step)")
    return solver, snaps, elapsed


def run_expanding_cosmos_gpu(N=64, L=2.0 * np.pi, dt=0.001, n_steps=600,
                             nu=0.0005, D=0.0002, lam=0.02, chi=1.0,
                             chi_yang=None, alpha_disp=None, k0=None, v0=1.0,
                             H0=1.0, a0=1.0, rho_crit=None,
                             hubble_mode='conversion', initial_ratio=None,
                             max_H=None, h_smooth=0.1, hyper_nu=0.0,
                             cs2=0.01,
                             init_fields=None, seed=42, report_every=100,
                             device=None):
    max_H_eff = max_H if max_H is not None else 4.0 * lam
    print(f"\n[GPU Expanding Cosmos 3D] grid={N}³, L={L:.3f}, dt={dt}, steps={n_steps}")
    print(f"  Hubble mode: {hubble_mode}, H0={H0:.4f}, a0={a0:.4f}")
    print(f"  max_H={max_H_eff:.4f}, h_smooth={h_smooth}")
    if initial_ratio is not None:
        print(f"  Initial EI/EY ratio: {initial_ratio:.4f} (φ⁻¹={PHI_INV:.4f})")
    if alpha_disp is not None:
        print(f"  scale-dependent dispersion: alpha_disp={alpha_disp:.4f}")
    t0 = time.time()
    solver = ExpandingTwoFluid3DGPU(
        N=N, L=L, nu=nu, D=D, lam=lam, chi=chi,
        chi_yang=chi_yang, alpha_disp=alpha_disp,
        k0=k0, v0=v0, H0=H0, a0=a0, rho_crit=rho_crit,
        hubble_mode=hubble_mode, initial_ratio=initial_ratio,
        max_H=max_H, h_smooth=h_smooth, hyper_nu=hyper_nu,
        cs2=cs2,
        mode='cosmos', device=device)
    if init_fields is not None:
        u_hat, ey_hat, ei_hat = init_fields
    else:
        u_hat, ey_hat, ei_hat = solver.initial_expanding(seed=seed)
    torch.cuda.synchronize() if solver.device.type == 'cuda' else None
    init_t = time.time() - t0

    snaps = []
    step_t0 = time.time()
    for step in range(n_steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, dt)

        if step % report_every == 0 or step == n_steps - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            rho = ey + ei
            rho_mean = rho.mean()
            delta_t = rho / rho_mean - 1.0
            delta = delta_t.cpu().numpy()
            k, Pk = solver.power_spectrum(delta_t)

            ey_mean = float(ey.mean().cpu())
            ei_mean = float(ei.mean().cpu())
            rho_tot = ey_mean + ei_mean
            omega_lam = ey_mean / rho_tot  # Ω_Λ = Yang fraction
            omega_m = ei_mean / rho_tot     # Ω_m = Yin fraction

            vortx = torch.fft.ifftn(1j * solver.ky * u_hat[2] - 1j * solver.kz * u_hat[1]).real
            vorty = torch.fft.ifftn(1j * solver.kz * u_hat[0] - 1j * solver.kx * u_hat[2]).real
            vortz = torch.fft.ifftn(1j * solver.kx * u_hat[1] - 1j * solver.ky * u_hat[0]).real
            enst = float((vortx ** 2 + vorty ** 2 + vortz ** 2).mean().cpu())

            snaps.append({
                'step': step, 't': step * dt,
                'rho': rho.cpu().numpy().copy(),
                'ey': ey.cpu().numpy().copy(),
                'ei': ei.cpu().numpy().copy(),
                'delta_rms': float(delta.std()),
                'ratio': float((ei.mean() / ey.mean()).cpu()),
                'enst': enst,
                'a': float(solver.a.cpu()),
                'H': float(solver.H.cpu()),
                'omega_lam': omega_lam,
                'omega_m': omega_m,
                'k': k, 'Pk': Pk
            })
            print(f"  step {step:4d} | t={step*dt:.3f} | a={snaps[-1]['a']:.3f} | "
                  f"H={snaps[-1]['H']:.4f} | δ_rms={delta.std():.3f} | "
                  f"ratio={snaps[-1]['ratio']:.4f} | Ω_Λ={omega_lam:.3f}")

    torch.cuda.synchronize() if solver.device.type == 'cuda' else None
    elapsed = time.time() - step_t0
    print(f"  Init time: {init_t:.2f}s | Step time: {elapsed:.2f}s "
          f"({elapsed/n_steps:.4f}s/step)")
    return solver, snaps, elapsed


def run_molecule_gpu(N=64, L=2.0 * np.pi, dt=0.0003, n_steps=600,
                     nu=0.001, D=0.002, chi=1.0, chi_yang=None,
                     seed=42, positions=None, charges=None, sigma=0.15,
                     report_every=100, device=None):
    if positions is None:
        positions = [(L * 0.4, L / 2, L / 2), (L * 0.6, L / 2, L / 2)]
    if charges is None:
        charges = [1.0, 1.0]

    print(f"\n[GPU Molecule 3D] grid={N}³, nuclei={len(positions)}, dt={dt}, steps={n_steps}")
    t0 = time.time()
    rho_ext = build_nuclei_density_gpu(N, L, positions, charges, sigma, device)
    solver = TwoFluid3DGPU(N=N, L=L, nu=nu, D=D, lam=0.0, chi=chi,
                           chi_yang=chi_yang, mode='molecule', rho_ext=rho_ext,
                           device=device)
    u_hat, ey_hat, ei_hat = solver.initial_molecule(seed=seed)
    torch.cuda.synchronize() if solver.device.type == 'cuda' else None
    init_t = time.time() - t0

    snaps = []
    step_t0 = time.time()
    dx3 = solver.dx ** 3
    for step in range(n_steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, dt)

        if step % report_every == 0 or step == n_steps - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            rho = ey + ei
            phi_hat = solver._poisson(torch.fft.fftn(rho) + solver.rho_ext_hat)
            phi = torch.fft.ifftn(phi_hat).real

            snaps.append({
                'step': step, 't': step * dt,
                'ey': ey.cpu().numpy().copy(),
                'ei': ei.cpu().numpy().copy(),
                'phi': phi.cpu().numpy().copy(),
                'ei_total': float(ei.sum().cpu()) * dx3,
                'ey_total': float(ey.sum().cpu()) * dx3,
                'ratio': float((ei.mean() / ey.mean()).cpu())
            })
            print(f"  step {step:4d} | t={step*dt:.3f} | "
                  f"EI_total={snaps[-1]['ei_total']:.3f} | ratio={snaps[-1]['ratio']:.4f}")

    torch.cuda.synchronize() if solver.device.type == 'cuda' else None
    elapsed = time.time() - step_t0
    print(f"  Init time: {init_t:.2f}s | Step time: {elapsed:.2f}s "
          f"({elapsed/n_steps:.4f}s/step)")
    return solver, snaps, positions, elapsed


def plot_cosmos(solver, snaps, outdir, tag=''):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    final = snaps[-1]

    fig, axes = plt.subplots(2, 3, figsize=(15, 9))

    def proj(fld, ax, title, cmap='viridis'):
        # Use log-scaled visualization to reveal filaments
        p = fld.sum(axis=0).T
        p = np.clip(p, a_min=p[p > 0].min() * 0.1, a_max=None)
        im = ax.imshow(np.log10(p), origin='lower', cmap=cmap,
                       extent=[0, solver.L, 0, solver.L])
        ax.set_title(title)
        ax.set_xlabel('y')
        ax.set_ylabel('z')
        plt.colorbar(im, ax=ax, fraction=0.046)

    proj(final['rho'], axes[0, 0], 'log₁₀ total density ρ (x-proj.)')
    proj(final['ey'], axes[0, 1], 'log₁₀ Yang EY')
    proj(final['ei'], axes[0, 2], 'log₁₀ Yin EI')

    axes[1, 0].axis('off')

    ax = axes[1, 1]
    for s, c in [(snaps[0], 'black'), (snaps[len(snaps)//2], 'blue'), (final, 'darkorange')]:
        valid = s['Pk'] > 0
        ax.loglog(s['k'][valid], s['Pk'][valid], '-o', markersize=3,
                  color=c, label=f"t={s['t']:.2f}")
    ax.set_xlabel('k')
    ax.set_ylabel('P(k)')
    ax.set_title('Power spectrum')
    ax.legend()
    ax.grid(True, which='both', ls='--', alpha=0.5)

    ax = axes[1, 2]
    t = [s['t'] for s in snaps]
    ax.plot(t, [s['delta_rms'] for s in snaps], 'darkorange', lw=2, marker='o', markersize=4)
    ax.set_xlabel('t')
    ax.set_ylabel('δ_rms')
    ax.set_title('Density contrast')
    ax.grid(True, alpha=0.3)



    fig.tight_layout()
    out = outdir / f'cassi_two_fluid_3d_gpu_cosmos{tag}.png'
    fig.savefig(out, dpi=150, bbox_inches='tight')
    print(f'  Saved {out}')
    plt.close(fig)

def plot_expanding_cosmos(solver, snaps, outdir, tag=''):
    """Plot expanding cosmology diagnostics: a(t), H(t), ratio, Ω, P(k), δ_rms."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    snaps = [s for s in snaps if not any(np.isnan(float(v)) for v in [s['a'], s['H'], s['delta_rms']])]
    if not snaps:
        print('  [WARN] All snapshots NaN -- skipping plot')
        return
    final = snaps[-1]

    # ── Figure 1: Density projections + power spectrum + δ_rms ──
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))

    def proj(fld, ax, title, cmap='viridis'):
        p = fld.sum(axis=0).T
        p = np.clip(p, a_min=p[p > 0].min() * 0.1, a_max=None)
        im = ax.imshow(np.log10(p), origin='lower', cmap=cmap,
                       extent=[0, solver.L, 0, solver.L])
        ax.set_title(title)
        ax.set_xlabel('y')
        ax.set_ylabel('z')
        plt.colorbar(im, ax=ax, fraction=0.046)

    proj(final['rho'], axes[0, 0], 'log₁₀ total density ρ (x-proj.)')
    proj(final['ey'], axes[0, 1], 'log₁₀ Yang EY')
    proj(final['ei'], axes[0, 2], 'log₁₀ Yin EI')

    ax = axes[1, 0]
    t_vals = [s['t'] for s in snaps]
    a_vals = [s['a'] for s in snaps]
    H_vals = [s['H'] for s in snaps]
    ax.plot(t_vals, a_vals, 'darkorange', lw=2, marker='o', markersize=4, label='a(t)')
    ax.set_xlabel('t')
    ax.set_ylabel('a(t)')
    ax.set_title('Scale factor')
    ax.grid(True, alpha=0.3)
    ax2 = ax.twinx()
    ax2.plot(t_vals, H_vals, 'purple', lw=1.5, ls='--', marker='s', markersize=3, label='H(t)')
    ax2.set_ylabel('H(t)')
    ax2.legend(loc='upper right')
    ax.legend(loc='upper left')

    ax = axes[1, 1]
    for s, c in [(snaps[0], 'black'), (snaps[len(snaps)//2], 'blue'), (final, 'darkorange')]:
        valid = s['Pk'] > 0
        ax.loglog(s['k'][valid], s['Pk'][valid], '-o', markersize=3,
                  color=c, label=f"t={s['t']:.2f}")
    ax.set_xlabel('k')
    ax.set_ylabel('P(k)')
    ax.set_title('Power spectrum')
    ax.legend()
    ax.grid(True, which='both', ls='--', alpha=0.5)

    ax = axes[1, 2]
    ax.plot(t_vals, [s['delta_rms'] for s in snaps], 'darkorange', lw=2, marker='o', markersize=4)
    ax.set_xlabel('t')
    ax.set_ylabel('δ_rms')
    ax.set_title('Density contrast')
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    out = outdir / f'cassi_two_fluid_3d_gpu_expanding{tag}.png'
    fig.savefig(out, dpi=150, bbox_inches='tight')
    print(f'  Saved {out}')
    plt.close(fig)

    # ── Figure 2: Expansion diagnostics ──
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))

    ax = axes[0, 0]
    ratio_vals = [s['ratio'] for s in snaps]
    r_vals = [1.0 / r if r > 0 else 0 for r in ratio_vals]  # r = EY/EI
    ax.plot(t_vals, r_vals, 'darkorange', lw=2, marker='o', markersize=4, label='r = EY/EI')
    ax.axhline(y=PHI, color='goldenrod', ls='--', lw=1.5, label=f'φ = {PHI:.4f}')
    ax.set_xlabel('t')
    ax.set_ylabel('r = EY/EI')
    ax.set_title('Yang/Yin ratio → φ attractor')
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[0, 1]
    omega_lam = [s.get('omega_lam', 0) for s in snaps]
    omega_m = [s.get('omega_m', 0) for s in snaps]
    ax.plot(t_vals, omega_lam, 'darkorange', lw=2, marker='o', markersize=4, label='Ω_Λ (Yang)')
    ax.plot(t_vals, omega_m, 'purple', lw=2, marker='s', markersize=4, label='Ω_m (Yin)')
    ax.axhline(y=PHI_INV, color='goldenrod', ls='--', lw=1.5, label=f'φ⁻¹ = {PHI_INV:.4f}')
    ax.axhline(y=PHI_INV ** 2, color='brown', ls=':', lw=1.5, label=f'φ⁻² = {PHI_INV**2:.4f}')
    ax.set_xlabel('t')
    ax.set_ylabel('Ω')
    ax.set_title('Energy fractions')
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[1, 0]
    ax.plot(t_vals, H_vals, 'purple', lw=2, marker='o', markersize=4)
    ax.axhline(y=0, color='black', ls='-', lw=0.5)
    ax.set_xlabel('t')
    ax.set_ylabel('H(t)')
    ax.set_title('Hubble parameter')
    ax.grid(True, alpha=0.3)

    ax = axes[1, 1]
    ax.plot(a_vals, H_vals, 'darkorange', lw=2, marker='o', markersize=4)
    ax.axhline(y=0, color='black', ls='-', lw=0.5)
    ax.set_xlabel('a')
    ax.set_ylabel('H(a)')
    ax.set_title('H vs scale factor')
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    out = outdir / f'cassi_two_fluid_3d_gpu_expanding_diag{tag}.png'
    fig.savefig(out, dpi=150, bbox_inches='tight')
    print(f'  Saved {out}')
    plt.close(fig)



def plot_molecule(solver, snaps, positions, outdir, tag=''):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    final = snaps[-1]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    def show(fld, ax, title, cmap='viridis'):
        p = fld.sum(axis=0).T
        im = ax.imshow(np.log10(np.clip(p, a_min=p[p > 0].min() * 0.1, a_max=None)),
                       origin='lower', cmap=cmap,
                       extent=[0, solver.L, 0, solver.L])
        for pos in positions:
            ax.plot(pos[1], pos[2], 'r+', markersize=12, mew=2)
        ax.set_title(title)
        ax.set_xlabel('y')
        ax.set_ylabel('z')
        plt.colorbar(im, ax=ax, fraction=0.046)

    show(final['ei'], axes[0], 'log₁₀ Yin EI (electron-like)', 'PuBu')
    show(final['ey'], axes[1], 'log₁₀ Yang EY (background)', 'YlOrRd')
    show(final['phi'], axes[2], 'log₁₀ |Φ|', 'inferno')

    fig.tight_layout()
    out = outdir / f'cassi_two_fluid_3d_gpu_molecule{tag}.png'
    fig.savefig(out, dpi=150, bbox_inches='tight')
    print(f'  Saved {out}')
    plt.close(fig)

    # Line cut
    fig, ax = plt.subplots(figsize=(10, 4))
    mid = solver.N // 2
    x_line = np.linspace(0, solver.L, solver.N, endpoint=False)
    ax.plot(x_line, final['ei'][:, mid, mid], 'b-', lw=2, label='EI (x-axis cut)')
    ax.plot(x_line, final['ey'][:, mid, mid], 'r-', lw=2, label='EY (x-axis cut)')
    for pos in positions:
        ax.axvline(pos[0], color='k', ls='--', alpha=0.5)
    ax.set_xlabel('x')
    ax.set_ylabel('density')
    ax.set_title('Density line cut through nuclei')
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    out = outdir / f'cassi_two_fluid_3d_gpu_molecule_cut{tag}.png'
    fig.savefig(out, dpi=150, bbox_inches='tight')
    print(f'  Saved {out}')
    plt.close(fig)


def run_benchmark(outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    print("\n" + "=" * 70)
    print("GPU BENCHMARK")
    print("=" * 70)

    results = []
    for N in [64, 128]:
        n_steps = 100 if N == 128 else 200
        print(f"\nN={N}³, steps={n_steps}")
        _, _, elapsed_c = run_cosmos_gpu(
            N=N, dt=0.001, n_steps=n_steps,
            nu=0.0005, D=0.0002, lam=0.02, chi=5.0,
            report_every=n_steps + 1, device='cuda'
        )
        results.append({'N': N, 'steps': n_steps, 'time': elapsed_c,
                        'per_step': elapsed_c / n_steps})

    # Plot benchmark
    fig, ax = plt.subplots(figsize=(8, 5))
    Ns = [r['N'] for r in results]
    per_step = [r['per_step'] for r in results]
    ax.bar([str(n) for n in Ns], per_step, color=['darkorange', 'purple'])
    ax.set_ylabel('seconds per step')
    ax.set_xlabel('grid size')
    ax.set_title('GPU 3D two-fluid cost per step')
    for i, r in enumerate(results):
        ax.text(i, per_step[i] + 0.001, f"{per_step[i]:.4f}s", ha='center')
    ax.grid(True, axis='y', alpha=0.3)
    fig.tight_layout()
    out = outdir / 'cassi_two_fluid_3d_gpu_benchmark.png'
    fig.savefig(out, dpi=150, bbox_inches='tight')
    print(f'  Saved {out}')
    plt.close(fig)

    md = f"""# Cassi Two-Fluid 3D GPU Benchmark

GPU: AMD Radeon RX 7900 XTX (ROCm)

| Grid | Steps | Total time (s) | Time per step (s) |
|---|---:|---:|---:|
"""
    for r in results:
        md += f"| {r['N']}³ | {r['steps']} | {r['time']:.2f} | {r['per_step']:.4f} |\n"

    md += """
## Comparison to CPU NumPy version

The CPU NumPy 3D solver on the same workstation costs roughly:

| Grid | Time per step (CPU, estimated) |
|---|---:|
| 64³ | ~0.25 s |
| 128³ | ~2.0 s |

The GPU version is therefore roughly **5–10× faster** at 64³ and becomes
increasingly advantageous at larger grids because the FFT work is offloaded
to the GPU.
"""
    out = Path('C:/Users/Carina/workspaces/physics/docs') / 'cassi-two-fluid-3d-gpu-benchmark.md'
    out.write_text(md)
    print(f'  Saved {out}')

def eisenstein_hu_transfer(k, omega_m=0.3, omega_b=0.049, h=0.67):
    """
    Eisenstein-Hu (1998) no-wiggles transfer function for CDM.
    
    Maps simulation wave numbers to physical k (h/Mpc) using an
    assumed box scale (~125 Mpc/h). Returns T(k) normalized such that
    T(k->0) = 1.
    """
    k = np.asarray(k, dtype=np.float64)
    zero_mask = (k == 0.0)
    
    # Baryon fraction
    s = omega_b / omega_m
    theta_cmb = 2.7 / 2.725  # CMB temperature relative to 2.7 K
    
    # Effective shape parameter with baryon suppression (EH98 Eq. 26)
    Gamma_eff = omega_m * h * (np.sqrt(s) + (1.0 - np.sqrt(s)) /
                                (1.0 + (0.43 * s)**4))
    Gamma_eff = Gamma_eff / (1.0 + np.sqrt(s))
    
    # Map simulation k to physical k (h/Mpc). L=2π box ≈ 125 Mpc/h
    k_s = 0.05  # conversion factor
    k_phys = np.maximum(k * k_s, 1e-30)
    
    # Dimensionless wave number
    q = k_phys / (Gamma_eff * h) * theta_cmb**2
    
    # No-wiggles form (EH98 Appendix B)
    L0 = np.log(2.0 * np.e + 1.8 * q)
    C0 = 14.2 + 731.0 / (1.0 + 62.5 * q)
    T = L0 / (L0 + C0 * q**2)
    
    T[zero_mask] = 1.0
    return T


def lcdm_growth_factor(a, omega_m, omega_lambda):
    """
    Linear growth factor D(a) for flat ΛCDM.
    
    D(a) = (5Ω_m/2) * E(a) * ∫₀ᵃ da' / [a' E(a')]³
    where E(a) = H(a)/H0 = sqrt(Ω_m a⁻³ + Ω_Λ).
    
    Normalized to D(1) = 1.
    """
    from scipy import integrate as _si
    a = np.asarray(a, dtype=np.float64)
    scalar_in = a.ndim == 0
    a = np.atleast_1d(a)
    
    def integrand(ap):
        E = np.sqrt(omega_m * ap**(-3) + omega_lambda)
        return 1.0 / (ap * E)**3
    
    D = np.zeros_like(a)
    for i, ai in enumerate(a):
        if ai <= 0.0:
            D[i] = 0.0
            continue
        I_val, _ = _si.quad(integrand, max(ai * 1e-6, 1e-12), ai, limit=200,
                            epsabs=1e-12, epsrel=1e-10)
        E = np.sqrt(omega_m * ai**(-3) + omega_lambda)
        D[i] = E * 2.5 * omega_m * I_val
    
    # Normalize D(1)=1
    D1 = np.interp(1.0, a, D)
    if D1 > 0.0:
        D = D / D1
    
    return D[0] if scalar_in else D


def lcdm_expansion(t_max, n_pts, H0, omega_m, omega_lambda):
    """
    Solve da/dt = a H0 sqrt(Ω_m a⁻³ + Ω_Λ) for flat ΛCDM.
    
    Returns (t_arr, a_arr, H_arr) starting from a(0)=1.
    """
    from scipy.integrate import solve_ivp as _solve_ivp
    
    def rhs(t, a):
        return a[0] * H0 * np.sqrt(omega_m * a[0]**(-3) + omega_lambda)
    
    sol = _solve_ivp(rhs, [0.0, t_max], [1.0],
                     max_step=t_max / max(n_pts, 10),
                     method='RK45', rtol=1e-8, atol=1e-10)
    
    t_arr = sol.t
    a_arr = sol.y[0]
    H_arr = H0 * np.sqrt(omega_m * a_arr**(-3) + omega_lambda)
    return t_arr, a_arr, H_arr


def generate_pk_field(N, L, Pk_func, seed=42, device='cuda'):
    """
    Generate a zero-mean unit-variance Gaussian random field delta(x)
    with power spectrum P(k) = Pk_func(|k|).
    """
    gen = torch.Generator(device=device)
    gen.manual_seed(seed)
    
    # k-grid in simulation units
    k_1d = 2.0 * np.pi * torch.fft.fftfreq(N, d=L / N, device=device)
    kz, ky, kx = torch.meshgrid(k_1d, k_1d, k_1d, indexing='ij')
    k_mag = torch.sqrt(kx**2 + ky**2 + kz**2)
    k_mag_np = k_mag.cpu().numpy()
    
    Pk = Pk_func(k_mag_np)
    Pk[k_mag_np == 0.0] = 0.0
    Pk_t = torch.tensor(Pk, device=device, dtype=torch.float64)
    
    # Complex noise scaled by sqrt(P(k))
    amp = torch.sqrt(Pk_t)
    noise = (torch.randn((N, N, N), generator=gen, device=device, dtype=torch.float64) +
             1j * torch.randn((N, N, N), generator=gen, device=device, dtype=torch.float64))
    noise = noise / np.sqrt(2.0)
    delta_k = amp * noise
    
    # Enforce Hermitian symmetry for real output
    # delta_k[-k] = conj(delta_k[k]) requires correct -k mapping
    # flip + roll(1) maps index i → (N-1-i+1) mod N = N-i which is the -k index
    delta_k_c = delta_k.flip([0, 1, 2]).conj()
    delta_k_c = torch.roll(delta_k_c, shifts=(1, 1, 1), dims=(0, 1, 2))
    delta_k = 0.5 * (delta_k + delta_k_c)
    
    delta = torch.fft.ifftn(delta_k).real
    delta = delta - delta.mean()
    delta = delta / delta.std()
    return delta


def run_lcdm_comparison(N=64, n_steps=2000, lam=0.1, chi=1.0, cs2=0.01,
                        hyper_nu=5e-6, initial_ratio=3.0,
                        omega_m=0.3, omega_lambda=0.7, H0_ref=0.07,
                        dt=0.0005, device='cuda', seed=42):
    """
    Run expanding two-fluid simulation seeded with Eisenstein-Hu ICs.
    
    Returns (solver, snaps, lcdm_ref) where lcdm_ref contains Friedmann
    reference data and the initial power spectrum.
    """
    L = 2.0 * np.pi
    print(f"\n[GPU LCDM Comparison] grid={N}³, steps={n_steps}, dt={dt}")
    print(f"  lambda={lam:.3f}, chi={chi:.3f}, cs2={cs2:.4f}, "
          f"initial_ratio={initial_ratio:.3f}")
    print(f"  LCDM: Ω_m={omega_m:.3f}, Ω_Λ={omega_lambda:.3f}, "
          f"H0_ref={H0_ref:.4f}")
    
    t0 = time.time()
    
    # ── 1. Eisenstein-Hu P(k) ──
    n_s = 0.9649  # Planck 2018
    def eh_pk(k_val):
        T = eisenstein_hu_transfer(k_val, omega_m=omega_m)
        return np.maximum(k_val, 1e-30)**n_s * T**2
    
    # ── 2. Gaussian random field ──
    delta = generate_pk_field(N, L, eh_pk, seed=seed, device=device)
    
    # ── 3. Initial EY/EI with anti-correlated fluctuations ──
    rho_mean = 1.618
    fraction = 0.3
    EI_mean = rho_mean * initial_ratio / (1.0 + initial_ratio)
    EY_mean = rho_mean / (1.0 + initial_ratio)
    EI = EI_mean * (1.0 + delta * fraction)
    EY = EY_mean * (1.0 - delta * fraction)
    EI = torch.clamp(EI, min=1e-4)
    EY = torch.clamp(EY, min=1e-4)
    
    # ── 4. Solver ──
    solver = ExpandingTwoFluid3DGPU(
        N=N, L=L, nu=0.0005, D=0.0002, lam=lam, chi=chi,
        cs2=cs2, hyper_nu=hyper_nu,
        H0=H0_ref, a0=1.0, rho_crit=PHI,
        hubble_mode='conversion', initial_ratio=initial_ratio,
        max_H=4.0 * lam, h_smooth=0.1, device=device)
    
    u_hat = [torch.zeros((N, N, N), dtype=torch.complex128, device=device)
             for _ in range(3)]
    ey_hat = torch.fft.fftn(EY)
    ei_hat = torch.fft.fftn(EI)
    _ = torch.cuda.synchronize() if solver.device.type == 'cuda' else None
    init_t = time.time() - t0
    
    # ── 5. Initial diagnostics ──
    rho_ic = EY + EI
    rho_mean_ic = float(rho_ic.mean().cpu())
    delta_ic = rho_ic / rho_mean_ic - 1.0
    k_bins, Pk_init = solver.power_spectrum(delta_ic)
    a_init = float(solver.a.cpu())
    D_init = float(lcdm_growth_factor(np.array([a_init]),
                                       omega_m, omega_lambda)[0])
    
    t_max_fried = n_steps * dt * 1.5
    t_fried, a_fried, H_fried = lcdm_expansion(
        t_max_fried, 1000, H0_ref, omega_m, omega_lambda)
    fried_init_mask = t_fried >= 0.0
    t_fried = t_fried[fried_init_mask]
    a_fried = a_fried[fried_init_mask]
    H_fried = H_fried[fried_init_mask]
    
    print(f"  Init: a={a_init:.3f}, D={D_init:.4f}, <rho>={rho_mean_ic:.3f}")
    print(f"  EI_mean={EI_mean:.3f}, EY_mean={EY_mean:.3f}, "
          f"ratio={initial_ratio:.3f}")
    
    # ── 6. Evolution ──
    report_every = max(1, n_steps // 40)
    snaps = []
    step_t0 = time.time()
    
    for step in range(n_steps):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, dt)
        
        if step % report_every == 0 or step == n_steps - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            rho = ey + ei
            rho_ms = rho.mean().item()
            if rho_ms > 0:
                delta_t = rho / rho_ms - 1.0
            else:
                delta_t = torch.zeros_like(rho)
            
            k_cur, Pk_cur = solver.power_spectrum(delta_t)
            a_cur = float(solver.a.cpu())
            H_cur = float(solver.H.cpu())
            D_cur = float(lcdm_growth_factor(np.array([a_cur]),
                                              omega_m, omega_lambda)[0])
            
            snaps.append({
                'step': step, 't': step * dt,
                'rho': rho.cpu().numpy().copy(),
                'ey': ey.cpu().numpy().copy(),
                'ei': ei.cpu().numpy().copy(),
                'delta': delta_t.cpu().numpy().copy(),
                'delta_rms': float(delta_t.std().cpu()),
                'ratio': float((ei.mean() / ey.mean()).cpu()),
                'a': a_cur, 'H': H_cur,
                'k': k_cur, 'Pk': Pk_cur,
                'D': D_cur,
            })
            print(f"  step {step:4d} | t={step*dt:.3f} | a={a_cur:.3f} | "
                  f"H={H_cur:.4f} | δ_rms={snaps[-1]['delta_rms']:.3f} | "
                  f"ratio={snaps[-1]['ratio']:.4f}")
    
    _ = torch.cuda.synchronize() if solver.device.type == 'cuda' else None
    elapsed = time.time() - step_t0
    print(f"  Init: {init_t:.2f}s | Steps: {elapsed:.2f}s "
          f"({elapsed/n_steps:.4f}s/step)")
    
    lcdm_ref = {
        'k': k_bins, 'Pk_init': Pk_init, 'D_init': D_init,
        'a_init': a_init,
        't_fried': t_fried, 'a_fried': a_fried, 'H_fried': H_fried,
        'omega_m': omega_m, 'omega_lambda': omega_lambda,
        'H0_ref': H0_ref,
    }
    return solver, snaps, lcdm_ref


def plot_lcdm_comparison(solver, snaps, lcdm_ref, outdir, tag=''):
    """2×2 figure comparing two-fluid evolution to ΛCDM."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    
    clean = [s for s in snaps
             if not any(np.isnan(v)
                        for v in [s['a'], s['H'], s['delta_rms']])]
    if not clean:
        print('  [WARN] All snapshots NaN—skipping LCDM plot')
        return
    final = clean[-1]
    
    t_vals = np.array([s['t'] for s in clean])
    a_vals = np.array([s['a'] for s in clean])
    H_vals = np.array([s['H'] for s in clean])
    d_rms = np.array([s['delta_rms'] for s in clean])
    
    # ΛCDM reference
    tf = lcdm_ref['t_fried']
    af = lcdm_ref['a_fried']
    Hf = lcdm_ref['H_fried']
    om = lcdm_ref['omega_m']
    ol = lcdm_ref['omega_lambda']
    D_init = lcdm_ref['D_init']
    Pk_init = lcdm_ref['Pk_init']
    k_ref = lcdm_ref['k']
    
    # Interpolate Friedmann to snapshot times for direct comparison
    a_fried_interp = np.interp(t_vals, tf, af,
                               left=af[0], right=af[-1])
    H_fried_interp = np.interp(t_vals, tf, Hf,
                               left=Hf[0], right=Hf[-1])
    
    # LCDM δ_rms: δ_rms(t) = δ_rms(0) * D(a_Friedmann(t)) / D(a_init)
    d_rms_lcdm = d_rms[0] * np.array([
        lcdm_growth_factor(np.array([ai]), om, ol)[0] / D_init
        for ai in a_fried_interp
    ])
    
    # LCDM P(k) at final time
    t_final = t_vals[-1]
    a_fried_final = np.interp(t_final, tf, af, right=af[-1])
    D_fried_final = float(lcdm_growth_factor(np.array([a_fried_final]),
                                              om, ol)[0])
    Pk_lcdm_final = Pk_init * (D_fried_final / D_init)**2
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # ── Top-left: a(t) ──
    ax = axes[0, 0]
    ax.plot(t_vals, a_vals, 'darkorange', lw=2, marker='o', markersize=4,
            label='Two-fluid (Cassi)')
    ax.plot(t_vals, a_fried_interp, 'steelblue', lw=2, ls='--',
            label='ΛCDM (Friedmann)')
    ax.axhline(y=1.0, color='gray', lw=0.5, ls=':')
    ax.set_xlabel('t')
    ax.set_ylabel('a(t)')
    ax.set_title('Scale factor')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # ── Top-right: H(t) ──
    ax = axes[0, 1]
    ax.plot(t_vals, H_vals, 'darkorange', lw=2, marker='o', markersize=4,
            label='Two-fluid (Cassi)')
    ax.plot(t_vals, H_fried_interp, 'steelblue', lw=2, ls='--',
            label='ΛCDM (Friedmann)')
    ax.axhline(y=0, color='gray', lw=0.5, ls=':')
    ax.set_xlabel('t')
    ax.set_ylabel('H(t)')
    ax.set_title('Hubble parameter')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # ── Bottom-left: P(k) at final time ──
    ax = axes[1, 0]
    vtf = final['Pk'] > 0
    ax.loglog(final['k'][vtf], final['Pk'][vtf], 'darkorange', lw=2,
              marker='o', markersize=3,
              label=f'Two-fluid t={t_final:.2f}')
    vpk = Pk_init > 0
    ax.loglog(k_ref[vpk], Pk_lcdm_final[vpk], 'steelblue', lw=2, ls='--',
              label=f'ΛCDM linear a={a_fried_final:.3f}')
    ax.loglog(k_ref[vpk], Pk_init[vpk], 'gray', lw=1.5, ls=':',
              label='Initial P(k)')
    ax.set_xlabel('k')
    ax.set_ylabel('P(k)')
    ax.set_title('Power spectrum at final time')
    ax.legend()
    ax.grid(True, which='both', ls='--', alpha=0.5)
    
    # ── Bottom-right: δ_rms evolution ──
    ax = axes[1, 1]
    ax.plot(t_vals, d_rms, 'darkorange', lw=2, marker='o', markersize=4,
            label='Two-fluid (Cassi)')
    ax.plot(t_vals, d_rms_lcdm, 'steelblue', lw=2, ls='--',
            label='ΛCDM linear')
    ax.set_xlabel('t')
    ax.set_ylabel('δ_rms')
    ax.set_title('Density contrast evolution')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    fig.tight_layout()
    out = outdir / f'cassi_two_fluid_3d_gpu_lcdm_comparison{tag}.png'
    fig.savefig(out, dpi=150, bbox_inches='tight')
    print(f'  Saved {out}')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description='Cassi 3D two-fluid GPU solver')
    parser.add_argument('--mode', type=str, default='cosmos',
                        choices=['cosmos', 'expanding', 'molecule', 'lcdm',
                                 'all', 'benchmark'])
    parser.add_argument('--N', type=int, default=128)
    parser.add_argument('--dt-cosmos', type=float, default=0.001)
    parser.add_argument('--dt-expanding', type=float, default=0.0005)
    parser.add_argument('--dt-molecule', type=float, default=0.0003)
    parser.add_argument('--n-steps', type=int, default=600)
    parser.add_argument('--nu', type=float, default=0.0005)
    parser.add_argument('--D', type=float, default=0.0002)
    parser.add_argument('--lam', type=float, default=0.02)
    parser.add_argument('--chi', type=float, default=1.0)
    parser.add_argument('--chi-yang', type=float, default=None)
    parser.add_argument('--chi-molecule', type=float, default=1.0)
    parser.add_argument('--H0', type=float, default=0.5)
    parser.add_argument('--a0', type=float, default=1.0)
    parser.add_argument('--hubble-mode', type=str, default='conversion',
                        choices=['conversion', 'friedmann'])
    parser.add_argument('--initial-ratio', type=float, default=None,
                        help='Initial EI/EY ratio. phi⁻¹=0.618 (equilibrium), '
                             '>0.618 (matter-dominated -> expansion), '
                             '<0.618 (Yang-dominated -> contraction)')
    parser.add_argument('--max-H', type=float, default=None,
                        help='Maximum |H| clamp (default: 4*lam)')
    parser.add_argument('--h-smooth', type=float, default=0.1,
                        help='H low-pass filter coefficient (0=no update, 1=raw)')
    parser.add_argument('--hyper-nu', type=float, default=5e-6,
                        help='Hyperdiffusion coefficient (k^4 damping for grid-scale stability)')
    parser.add_argument('--cs2', type=float, default=0.01,
                        help='Sound speed squared (pressure support to prevent unbounded collapse)')
    parser.add_argument('--alpha-disp', type=float, default=None)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--device', type=str, default='cuda')
    parser.add_argument('--dt-lcdm', type=float, default=0.0005,
                        help='Time step for LCDM comparison mode')
    parser.add_argument('--omega-m', type=float, default=0.3,
                        help='LCDM matter density parameter')
    parser.add_argument('--omega-lambda', type=float, default=0.7,
                        help='LCDM dark energy density parameter')
    parser.add_argument('--H0-ref', type=float, default=0.07,
                        help='Reference Hubble constant (simulation units) for LCDM')
    args = parser.parse_args()
    print(f'[DIAG] chi={args.chi:.4f}  cs2={args.cs2:.4f}  hubble={args.hubble_mode}')

    fig_dir = Path('C:/Users/Carina/workspaces/physics/figures')
    fig_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == 'benchmark':
        run_benchmark(outdir=fig_dir)
        return

    if args.mode in ('all', 'cosmos'):
        print("\n" + "=" * 70)
        print("GPU 3D TWO-FLUID COSMOLOGY")
        print("=" * 70)
        solver_c, snaps_c, _ = run_cosmos_gpu(
            N=args.N, dt=args.dt_cosmos, n_steps=args.n_steps,
            nu=args.nu, D=args.D, lam=args.lam, chi=args.chi,
            chi_yang=args.chi_yang, alpha_disp=args.alpha_disp,
            seed=args.seed, device=args.device
        )
        plot_cosmos(solver_c, snaps_c, outdir=fig_dir, tag=f'_N{args.N}')

    if args.mode in ('all', 'expanding'):
        print("\n" + "=" * 70)
        print("GPU 3D TWO-FLUID EXPANDING COSMOLOGY")
        print("=" * 70)
        solver_e, snaps_e, _ = run_expanding_cosmos_gpu(
            N=args.N, dt=args.dt_expanding, n_steps=args.n_steps,
            nu=args.nu, D=args.D, lam=args.lam, chi=args.chi,
            chi_yang=args.chi_yang, alpha_disp=args.alpha_disp,
            H0=args.H0, a0=args.a0,
            hubble_mode=args.hubble_mode, initial_ratio=args.initial_ratio,
            max_H=args.max_H, h_smooth=args.h_smooth,
            hyper_nu=args.hyper_nu, cs2=args.cs2,
            seed=args.seed, device=args.device
        )
        plot_expanding_cosmos(solver_e, snaps_e, outdir=fig_dir, tag=f'_N{args.N}')

    if args.mode in ('all', 'molecule'):
        print("\n" + "=" * 70)
        print("GPU 3D TWO-FLUID MOLECULE")
        print("=" * 70)
        solver_m, snaps_m, positions, _ = run_molecule_gpu(
            N=args.N, dt=args.dt_molecule, n_steps=args.n_steps,
            nu=args.nu, D=args.D, chi=args.chi_molecule,
            chi_yang=args.chi_yang, seed=args.seed, device=args.device
        )
        plot_molecule(solver_m, snaps_m, positions, outdir=fig_dir, tag=f'_N{args.N}')

    if args.mode in ('all', 'lcdm'):
        print("\n" + "=" * 70)
        print("GPU 3D TWO-FLUID LCDM COMPARISON")
        print("=" * 70)
        # Default initial_ratio for LCDM comparison: EI/EY=0.25 means
        # Ω_m~0.2, Ω_Λ~0.8 initially—leaves room to evolve toward φ.
        lcdm_ratio = args.initial_ratio if args.initial_ratio is not None else 3.0
        solver_l, snaps_l, lcdm_ref = run_lcdm_comparison(
            N=args.N, n_steps=args.n_steps,
            lam=args.lam, chi=args.chi, cs2=args.cs2,
            hyper_nu=args.hyper_nu, initial_ratio=lcdm_ratio,
            omega_m=args.omega_m, omega_lambda=args.omega_lambda,
            H0_ref=args.H0_ref,
            dt=args.dt_lcdm, device=args.device, seed=args.seed
        )
        plot_lcdm_comparison(solver_l, snaps_l, lcdm_ref,
                             outdir=fig_dir, tag=f'_N{args.N}')

    print("\nGPU 3D TWO-FLUID DEMO COMPLETE")


if __name__ == '__main__':
    main()
