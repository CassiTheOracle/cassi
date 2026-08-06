#!/usr/bin/env python3
"""Cassi N-Body 3D GPU - Particle-Mesh Gravity at O(N + n^3 log n).

Accurate 3D N-body solver using spectral Poisson gravity on GPU.
- Bodies deposited onto grid via Cloud-in-Cell (CIC)
- Poisson equation solved via FFT with Gaussian softening
- Leapfrog (kick-drift-kick) symplectic integration
- Qi-gated adaptive softening: coherence q = rho^2 / (rho^2 + phi^-2 + eps^2)
  where eps^2 = (rho - qi_field)^2 measures deviation from temporal equilibrium.
  Mirrors the two-fluid cosmology Qi gate (Cassian: coherence suppresses interaction).

Usage:
  python cassi_nbody.py --N 1000 --mode plummer --steps 5000
  python cassi_nbody.py --N 100 --mode benchmark
  python cassi_nbody.py --N 500 --qi-gate --steps 2000
"""

import argparse
import time
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict

import torch

# --- Cassi constants ---
PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_INV = 1.0 / PHI


# --- Device detection ---
def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device('cuda')
    print('[warning] CUDA/ROCm not available; falling back to CPU')
    return torch.device('cpu')


# --- Configuration ---
@dataclass
class NBodyConfig:
    n_grid: int = 128
    L: float = 20.0
    G: float = 1.0
    sigma: float = 0.4
    deposition_kernel: str = 'CIC'  # 'CIC', 'TSC', 'GAUSSIAN'
    dt: float = 0.001
    n_steps: int = 10000
    vel_damp: float = 1.0
    qi_damp: float = PHI_INV
    qi_gate: bool = False
    qi_memory: bool = False
    qi_beta: float = 0.5     # deprecated: replaced by PHI_INV + qi_gamma in five-element model
    qi_gamma: float = 1.0    # turbulence contribution to softening (five-element Kmd analog)
    alpha_yin: float = 0.0   # Yin relative-entropy nonlinear source (0 = off, 0.5 typical)
    holographic_bound: bool = False  # enable holographic I_max smoothing
    holographic_eta: float = 1.0     # holographic bound coefficient
    report_every: int = 250
    track_every: int = 50
    device: Optional[torch.device] = None
    def __post_init__(self):
        if self.device is None:
            self.device = get_device()


# --- N-Body Solver ---
class NBodySolver3D:
    """3D particle-mesh gravity solver with spectral Poisson + CIC/TSC/GAUSSIAN deposition."""

    def __init__(self, n_grid: int = 128, L: float = 20.0, G: float = 1.0,
                 sigma: float = 0.4, device: Optional[torch.device] = None,
                 qi_gate: bool = False, qi_memory: bool = False,
                 deposition_kernel: str = 'CIC',
                 alpha_yin: float = 0.0,
                 holographic_bound: bool = False,
                 holographic_eta: float = 1.0):
        if deposition_kernel not in ('CIC', 'TSC', 'GAUSSIAN'):
            raise ValueError(f"Unknown deposition_kernel: {deposition_kernel}")
        self.deposition_kernel = deposition_kernel
        self.alpha_yin = alpha_yin
        self.holographic_bound = holographic_bound
        self.holographic_eta = holographic_eta
        self.n = n_grid
        self.L = L
        self.dx = L / n_grid
        self.G = G
        self.sigma = sigma
        self.device = device if device is not None else get_device()
        self.qi_gate = qi_gate
        self.qi_memory = qi_memory
        self.eps_sq_memory = None
        self.qi_field = None

        # Wave number grid
        k_1d = 2.0 * math.pi * torch.fft.fftfreq(n_grid, d=self.dx, device=self.device,
                                                   dtype=torch.float64)
        self.kz, self.ky, self.kx = torch.meshgrid(k_1d, k_1d, k_1d, indexing='ij')
        self.k2 = self.kx ** 2 + self.ky ** 2 + self.kz ** 2

        # Exact spectral Laplacian (eliminates grid anisotropy)
        k2_spectral = (4.0 / self.dx**2) * (
            torch.sin(0.5 * self.kx * self.dx)**2 +
            torch.sin(0.5 * self.ky * self.dx)**2 +
            torch.sin(0.5 * self.kz * self.dx)**2
        )
        # Smooth blend: continuous at low k, exact at high k
        blend = torch.tanh(self.k2 * self.dx**2)
        self.k2_eff = self.k2 * (1.0 - blend) + k2_spectral * blend
        self.k2_eff[0, 0, 0] = self.k2[0, 0, 0]
        self.k2_eff_safe = self.k2_eff.clone()
        self.k2_eff_safe[0, 0, 0] = 1.0

        # Green's function: raw (no Fourier softening) and softened variants
        self.green_k_raw = -4.0 * math.pi * G / self.k2_eff_safe
        self.green_k_raw[0, 0, 0] = 0.0
        self._update_green_k()

        # Work buffers
        self._rho = torch.zeros((n_grid, n_grid, n_grid), device=self.device, dtype=torch.float64)
        self._flat_rho = torch.zeros(n_grid ** 3, device=self.device, dtype=torch.float64)

        # CIC corner offsets (8 corners of a cube)
        offsets = torch.tensor([
            [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1],
            [1, 1, 0], [1, 0, 1], [0, 1, 1], [1, 1, 1],
        ], device=self.device)
        self._offsets = offsets

        # TSC structures (27 corners, offset range {-1, 0, 1})
        self._tsc_offsets = self._build_tsc_offsets()

    def _update_green_k(self):
        """Recompute green_k based on current sigma, deposition_kernel, and alpha_yin."""
        if self.deposition_kernel == 'GAUSSIAN' or self.alpha_yin > 0.0:
            # No Fourier softening: Gaussian blob or Yin filter replaces it
            self.green_k = self.green_k_raw.clone()
        else:
            softening = torch.exp(-0.5 * self.k2_eff * self.sigma ** 2)
            self.green_k = self.green_k_raw * softening
        self.green_k[0, 0, 0] = 0.0

    def set_softening(self, sigma_new: float):
        """Update Gaussian softening length and recompute Green's function."""
        if abs(sigma_new - self.sigma) < 1e-6 * max(self.sigma, 1.0):
            return
        self.sigma = sigma_new
        self._update_green_k()

    # --- TSC (Triangular Shaped Cloud) utilities ---
    def _tsc_weights(self, f: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """TSC weight function for 1D fractional offset f in [-1.5, 1.5].

        Returns (w_lo, w_mid, w_hi) for cells at offsets -1, 0, +1.
        f is the fractional coordinate relative to the center cell (in [-0.5, 0.5]).
        """
        f_lo = f + 1.0    # distance from cell at offset -1: f - (-1) = f + 1
        f_mid = torch.abs(f)
        f_hi = 1.0 - f    # distance from cell at offset +1: (f+1) - f = 1 - f ... no
        # Standard: weight for cell i depends on |f - offset_i|
        # offset -1: |f - (-1)| = |f + 1|; offset 0: |f|; offset +1: |f - 1| = |1 - f|
        d_lo = torch.abs(f + 1.0)
        d_mid = torch.abs(f)
        d_hi = torch.abs(1.0 - f)

        w_lo = torch.where(d_lo <= 0.5, 0.75 - d_lo**2,
                  torch.where(d_lo <= 1.5, 0.5 * (1.5 - d_lo)**2,
                  torch.zeros_like(d_lo)))
        w_mid = torch.where(d_mid <= 0.5, 0.75 - d_mid**2,
                  torch.where(d_mid <= 1.5, 0.5 * (1.5 - d_mid)**2,
                  torch.zeros_like(d_mid)))
        w_hi = torch.where(d_hi <= 0.5, 0.75 - d_hi**2,
                  torch.where(d_hi <= 1.5, 0.5 * (1.5 - d_hi)**2,
                  torch.zeros_like(d_hi)))
        return w_lo, w_mid, w_hi

    def _build_tsc_offsets(self) -> torch.Tensor:
        """Build (27, 3) int tensor of TSC corner offsets in {-1, 0, 1}^3."""
        import itertools
        offsets_list = list(itertools.product([-1, 0, 1], repeat=3))
        return torch.tensor(offsets_list, device=self.device, dtype=torch.long)

    # --- Density deposition ---
    def deposit_density(self, positions: torch.Tensor,
                        masses: torch.Tensor) -> torch.Tensor:
        """Deposit particle masses onto grid via CIC or TSC.

        Args:
            positions: (N, 3) tensor, physical coordinates in [-L/2, L/2)
            masses: (N,) tensor

        Returns:
            rho: (n, n, n) mass density grid
        """
        if self.deposition_kernel == 'GAUSSIAN':
            return self._deposit_density_gaussian(positions, masses)

        N = positions.shape[0]
        n = self.n
        dV = self.dx ** 3

        self._flat_rho.zero_()
        self._rho.zero_()

        g = (positions + self.L / 2.0) / self.dx

        if self.deposition_kernel == 'CIC':
            floor = g.long()
            frac = g - floor.float()
            c0 = 1.0 - frac
            c1 = frac

            for corner_idx in range(8):
                ox, oy, oz = self._offsets[corner_idx]
                wx = c1[:, 0] if ox == 1 else c0[:, 0]
                wy = c1[:, 1] if oy == 1 else c0[:, 1]
                wz = c1[:, 2] if oz == 1 else c0[:, 2]
                weight = masses * wx * wy * wz
                ix = (floor[:, 0] + ox) % n
                iy = (floor[:, 1] + oy) % n
                iz = (floor[:, 2] + oz) % n
                flat_idx = iz * (n * n) + iy * n + ix
                self._flat_rho.index_put_((flat_idx,), weight.to(self._flat_rho.dtype),
                                          accumulate=True)
        else:  # TSC
            # Round to nearest grid point as center
            floor_center = torch.round(g).long()
            frac_center = g - floor_center.float()  # in [-0.5, 0.5]

            w_x_lo, w_x_mid, w_x_hi = self._tsc_weights(frac_center[:, 0])
            w_y_lo, w_y_mid, w_y_hi = self._tsc_weights(frac_center[:, 1])
            w_z_lo, w_z_mid, w_z_hi = self._tsc_weights(frac_center[:, 2])

            # Weight arrays indexed by offset: -1 -> 0, 0 -> 1, +1 -> 2
            wx_3 = torch.stack([w_x_lo, w_x_mid, w_x_hi], dim=1)  # (N, 3)
            wy_3 = torch.stack([w_y_lo, w_y_mid, w_y_hi], dim=1)
            wz_3 = torch.stack([w_z_lo, w_z_mid, w_z_hi], dim=1)

            for corner_idx in range(27):
                ox, oy, oz = self._tsc_offsets[corner_idx]
                # offset index: -1 -> 0, 0 -> 1, 1 -> 2
                ix_off = ox.item() + 1
                iy_off = oy.item() + 1
                iz_off = oz.item() + 1
                weight = masses * wx_3[:, ix_off] * wy_3[:, iy_off] * wz_3[:, iz_off]
                ix = (floor_center[:, 0] + ox) % n
                iy = (floor_center[:, 1] + oy) % n
                iz = (floor_center[:, 2] + oz) % n
                flat_idx = iz * (n * n) + iy * n + ix
                self._flat_rho.index_put_((flat_idx,), weight.to(self._flat_rho.dtype),
                                          accumulate=True)

        # Convert deposited mass to mass density
        self._rho = self._flat_rho.view(n, n, n) / dV
        return self._rho

    def _deposit_density_gaussian(self, positions: torch.Tensor,
                                   masses: torch.Tensor) -> torch.Tensor:
        """Deposit as exact Gaussian density blobs with NO Fourier softening.

        Each body deposits to cells within 3*sigma. The Gaussian weight is:
            w(r) = exp(-r^2 / (2*sigma^2)) / ((2*pi)^(1.5) * sigma^3 * dV)
        This replaces both CIC and Fourier softening—the Gaussian blob IS the
        physical mass distribution.

        Performance: O(N * (6*sigma/dx)^3). Warns if N > 5000.
        """
        if positions.shape[0] > 5000:
            import warnings
            warnings.warn(
                f"GAUSSIAN deposition with N={positions.shape[0]} bodies. "
                f"Each body touches ~{(2 * math.ceil(3 * self.sigma / self.dx) + 1) ** 3} cells. "
                f"Consider CIC/TSC for large N.",
                stacklevel=2
            )

        n = self.n
        dV = self.dx ** 3
        sigma = self.sigma
        inv_2sig2 = 1.0 / (2.0 * sigma ** 2)
        norm = 1.0 / ((2.0 * math.pi) ** 1.5 * sigma ** 3 * dV)

        self._rho.zero_()
        g = (positions + self.L / 2.0) / self.dx  # grid coordinates

        n_cells = int(math.ceil(3.0 * sigma / self.dx))
        # Precompute 1D kernel
        offsets_1d = torch.arange(-n_cells, n_cells + 1, device=self.device, dtype=torch.float64)
        dist_sq_1d = (offsets_1d * self.dx) ** 2
        kernel_1d = torch.exp(-dist_sq_1d * inv_2sig2)

        for i in range(positions.shape[0]):
            gx, gy, gz = g[i, 0].item(), g[i, 1].item(), g[i, 2].item()
            m = masses[i].item()
            if m == 0.0:
                continue

            cx = int(round(gx))
            cy = int(round(gy))
            cz = int(round(gz))

            for dx_idx in range(len(offsets_1d)):
                ix = (cx + offsets_1d[dx_idx].long().item()) % n
                wx = kernel_1d[dx_idx]
                for dy_idx in range(len(offsets_1d)):
                    iy = (cy + offsets_1d[dy_idx].long().item()) % n
                    wy = wx * kernel_1d[dy_idx]
                    for dz_idx in range(len(offsets_1d)):
                        iz = (cz + offsets_1d[dz_idx].long().item()) % n
                        w = wy * kernel_1d[dz_idx]
                        self._rho[iz, iy, ix] += m * w * norm

        return self._rho

    # --- Spectral Poisson solve ---
    def solve_gravity(self, rho: torch.Tensor) -> Tuple[torch.Tensor, ...]:
        """Solve Poisson and compute acceleration field: a = -grad(Phi).

        Returns:
            (ax, ay, az): acceleration grids, each (n, n, n)
        """
        rho_complex = rho.to(torch.complex128)
        rho_hat = torch.fft.fftn(rho_complex)

        phi_hat = self.green_k.to(torch.complex128) * rho_hat

        # Orszag 2/3 de-aliasing: zero modes above 2/3 of Nyquist
        k_max = math.pi / self.dx
        k_mag = torch.sqrt(self.k2)
        alias_mask = k_mag > (2.0 / 3.0) * k_max
        phi_hat[alias_mask] = 0.0

        ax = torch.fft.ifftn(-1j * self.kx * phi_hat).real
        ay = torch.fft.ifftn(-1j * self.ky * phi_hat).real
        az = torch.fft.ifftn(-1j * self.kz * phi_hat).real

        return ax, ay, az

    # --- P^3M Architecture (API hooks for future implementation) ---
    def find_close_pairs(self, positions: torch.Tensor,
                         r_cut: float) -> List[Tuple[int, int, torch.Tensor]]:
        """Grid-based cell list to find pairs within r_cut.

        Divides box into cells of size r_cut, places bodies in cells,
        then checks only adjacent cells for close pairs.

        Args:
            positions: (N, 3) tensor
            r_cut: maximum separation for close pairs

        Returns:
            List of (i, j, dr) tuples where dr = pos[j] - pos[i].
            Currently a stub—raises NotImplementedError.
        """
        raise NotImplementedError(
            "P^3M close-pair search not yet implemented. "
            "Design: cell-list with r_cut linking length, Qi-gated: "
            f"r_cut = r_base * (1 + {PHI_INV:.4f} * (1 - q_mean))."
        )

    def pm_force_at_separation(self, dr: torch.Tensor) -> torch.Tensor:
        """PM force lookup at given separations.

        Given a set of separation vectors dr, return the PM acceleration
        that would be computed by the spectral Poisson solver for a unit
        mass at that separation—including CIC/TSC interpolation and
        Fourier softening.

        Args:
            dr: (M, 3) tensor of separation vectors

        Returns:
            (M, 3) tensor of PM acceleration vectors.
            Currently a stub—raises NotImplementedError.
        """
        raise NotImplementedError(
            "PM force lookup table not yet implemented. "
            "Design: precompute on a 1D radial grid by placing a single "
            "particle and measuring the interpolated acceleration."
        )

    def compute_acceleration_p3m(self, positions: torch.Tensor,
                                  masses: torch.Tensor,
                                  r_cut: float) -> torch.Tensor:
        """Full P^3M pipeline: PM long-range + PP short-range correction.

        1. Compute PM acceleration (this.compute_acceleration)
        2. Find close pairs within r_cut (self.find_close_pairs)
        3. For each close pair, subtract PM force and add direct PP force

        Args:
            positions: (N, 3) tensor
            masses: (N,) tensor
            r_cut: PP linking length (Qi-gated: r_cut = r_base * (1 + phi^-1 * (1-q)))

        Returns:
            (N, 3) tensor of corrected accelerations.
            Currently a stub—raises NotImplementedError.
        """
        raise NotImplementedError(
            "P^3M not yet implemented. "
            "Architecture: PM solve + cell-list close pairs + "
            "PP correction with Qi-gated r_cut."
        )

    # --- Yin relative-entropy nonlinear source (Bridge Sec 3.2) ---
    def apply_yin_source(self, rho: torch.Tensor,
                         alpha_yin: float = 0.5) -> torch.Tensor:
        """Apply concave nonlinear source transformation to density.

        The Yin filter compresses high overdensities via relative entropy:
            S_rel(delta) = (1+delta) * ln(1+delta) - delta
            S[rho] = rho + alpha_yin * S_rel(delta) * rho_bar

        where delta = rho/rho_bar - 1.
        High overdensities feel weaker self-gravity; low-density regions untouched.

        When alpha_yin > 0, Fourier softening is disabled (nonlinear filter replaces it).

        Args:
            rho: (n, n, n) density grid
            alpha_yin: coupling strength (0 = off)

        Returns:
            Modified density source for Poisson equation.
        """
        if alpha_yin <= 0.0:
            return rho
        rho_bar = rho.mean()
        delta = rho / rho_bar - 1.0
        safe = torch.clamp(1.0 + delta, min=1e-6)
        s_rel = safe * torch.log(safe) - delta
        return rho + alpha_yin * s_rel * rho_bar

    # --- Holographic adaptive smoothing (Bridge Sec 3.4) ---
    def holographic_smooth(self, rho: torch.Tensor,
                           eta: float = 1.0,
                           beta: float = 0.5) -> torch.Tensor:
        """Apply holographic-bound Gaussian smoothing to density.

        If KL divergence from uniformity exceeds I_max = eta * N_grid^(2/3),
        smooth at scale R_h = dx * (I / I_max)^beta.

        Args:
            rho: (n, n, n) density grid
            eta: holographic bound coefficient
            beta: smoothing exponent

        Returns:
            Smoothed density grid (or unchanged if within bound).
        """
        p = rho / rho.sum()
        q_val = 1.0 / self.n ** 3
        I_field = (p * torch.log(p / q_val)).sum().item()
        I_max = eta * self.n ** (2.0 / 3.0)
        if I_field <= I_max:
            return rho
        R_h = self.dx * (I_field / I_max) ** beta
        sigma_h = R_h / (2.0 * math.sqrt(2.0 * math.log(2.0)))
        rho_hat = torch.fft.fftn(rho.to(torch.complex128))
        smooth = rho_hat * torch.exp(-0.5 * self.k2 * sigma_h ** 2)
        return torch.fft.ifftn(smooth).real
    # --- Acceleration interpolation ---
    def interpolate_accel(self, ax: torch.Tensor, ay: torch.Tensor,
                          az: torch.Tensor,
                          positions: torch.Tensor) -> torch.Tensor:
        """Interpolate acceleration at body positions via CIC or TSC."""
        N = positions.shape[0]
        n = self.n
        g = (positions + self.L / 2.0) / self.dx
        accel = torch.zeros(N, 3, device=self.device)

        if self.deposition_kernel == 'CIC':
            floor = g.long()
            frac = g - floor.float()
            c0 = 1.0 - frac
            c1 = frac

            for corner_idx in range(8):
                ox, oy, oz = self._offsets[corner_idx]
                wx = c1[:, 0] if ox == 1 else c0[:, 0]
                wy = c1[:, 1] if oy == 1 else c0[:, 1]
                wz = c1[:, 2] if oz == 1 else c0[:, 2]
                weight = wx * wy * wz
                ix = (floor[:, 0] + ox) % n
                iy = (floor[:, 1] + oy) % n
                iz = (floor[:, 2] + oz) % n
                accel[:, 0] += weight * ax[iz, iy, ix]
                accel[:, 1] += weight * ay[iz, iy, ix]
                accel[:, 2] += weight * az[iz, iy, ix]
        else:  # TSC or GAUSSIAN
            floor_center = torch.round(g).long()
            frac_center = g - floor_center.float()

            w_x_lo, w_x_mid, w_x_hi = self._tsc_weights(frac_center[:, 0])
            w_y_lo, w_y_mid, w_y_hi = self._tsc_weights(frac_center[:, 1])
            w_z_lo, w_z_mid, w_z_hi = self._tsc_weights(frac_center[:, 2])

            wx_3 = torch.stack([w_x_lo, w_x_mid, w_x_hi], dim=1)
            wy_3 = torch.stack([w_y_lo, w_y_mid, w_y_hi], dim=1)
            wz_3 = torch.stack([w_z_lo, w_z_mid, w_z_hi], dim=1)

            for corner_idx in range(27):
                ox, oy, oz = self._tsc_offsets[corner_idx]
                ix_off = ox.item() + 1
                iy_off = oy.item() + 1
                iz_off = oz.item() + 1
                weight = wx_3[:, ix_off] * wy_3[:, iy_off] * wz_3[:, iz_off]
                ix = (floor_center[:, 0] + ox) % n
                iy = (floor_center[:, 1] + oy) % n
                iz = (floor_center[:, 2] + oz) % n
                accel[:, 0] += weight * ax[iz, iy, ix]
                accel[:, 1] += weight * ay[iz, iy, ix]
                accel[:, 2] += weight * az[iz, iy, ix]

        return accel

    def compute_acceleration(self, positions: torch.Tensor,
                             masses: torch.Tensor) -> torch.Tensor:
        """Full pipeline: deposit -> [holographic] -> [yin] -> Poisson -> interpolate."""
        rho = self.deposit_density(positions, masses)
        # Holographic adaptive smoothing: applied before Yin source
        if self.holographic_bound:
            rho = self.holographic_smooth(rho, eta=self.holographic_eta)
        # Yin relative-entropy nonlinear source
        if self.alpha_yin > 0.0:
            rho = self.apply_yin_source(rho, alpha_yin=self.alpha_yin)
        ax, ay, az = self.solve_gravity(rho)
        return self.interpolate_accel(ax, ay, az, positions)

    def _interpolate_scalar(self, field: torch.Tensor,
                            positions: torch.Tensor) -> torch.Tensor:
        """Interpolate scalar field at body positions via CIC or TSC."""
        N = positions.shape[0]
        n = self.n
        g = (positions + self.L / 2.0) / self.dx
        result = torch.zeros(N, device=self.device, dtype=field.dtype)

        if self.deposition_kernel == 'CIC':
            floor = g.long()
            frac = g - floor.float()
            c0, c1 = 1.0 - frac, frac
            for corner_idx in range(8):
                ox, oy, oz = self._offsets[corner_idx]
                wx = c1[:, 0] if ox == 1 else c0[:, 0]
                wy = c1[:, 1] if oy == 1 else c0[:, 1]
                wz = c1[:, 2] if oz == 1 else c0[:, 2]
                weight = wx * wy * wz
                ix = (floor[:, 0] + ox) % n
                iy = (floor[:, 1] + oy) % n
                iz = (floor[:, 2] + oz) % n
                result += weight * field[iz, iy, ix]
        else:  # TSC or GAUSSIAN
            floor_center = torch.round(g).long()
            frac_center = g - floor_center.float()
            w_x_lo, w_x_mid, w_x_hi = self._tsc_weights(frac_center[:, 0])
            w_y_lo, w_y_mid, w_y_hi = self._tsc_weights(frac_center[:, 1])
            w_z_lo, w_z_mid, w_z_hi = self._tsc_weights(frac_center[:, 2])
            wx_3 = torch.stack([w_x_lo, w_x_mid, w_x_hi], dim=1)
            wy_3 = torch.stack([w_y_lo, w_y_mid, w_y_hi], dim=1)
            wz_3 = torch.stack([w_z_lo, w_z_mid, w_z_hi], dim=1)
            for corner_idx in range(27):
                ox, oy, oz = self._tsc_offsets[corner_idx]
                ix_off = ox.item() + 1
                iy_off = oy.item() + 1
                iz_off = oz.item() + 1
                weight = wx_3[:, ix_off] * wy_3[:, iy_off] * wz_3[:, iz_off]
                ix = (floor_center[:, 0] + ox) % n
                iy = (floor_center[:, 1] + oy) % n
                iz = (floor_center[:, 2] + oz) % n
                result += weight * field[iz, iy, ix]
        return result

    def compute_acceleration_qi(self, positions: torch.Tensor,
                                 masses: torch.Tensor
                                 ) -> Tuple[torch.Tensor, float]:
        """Qi-gated acceleration: adaptive softening via density memory.

        Mirrors the two-fluid Qi gate: coherence q = rho^2 / (rho^2 + phi^-2 + eps^2)
        where eps^2 = (rho - qi_field)^2 measures deviation from temporal equilibrium.

        - qi_field is a phi-damped EMA of past density (set by runner).
        - When rho ~ qi_field (steady state): q -> 1, gravity passes through.
        - When rho deviates from memory (collapse/merger): q -> low, gravity suppressed.
        - In vacuum: q -> 1 (no spurious gate).
        """
        rho = self.deposit_density(positions, masses)

        # Equilibrium deviation
        if self.qi_field is not None:
            eps_sq = (rho - self.qi_field) ** 2
        else:
            eps_sq = torch.zeros_like(rho)

        # Qi memory EMA (temporal inertia, optional)
        if self.qi_memory:
            if self.eps_sq_memory is None:
                self.eps_sq_memory = torch.zeros_like(eps_sq)
            self.eps_sq_memory = (1.0 - PHI_INV) * self.eps_sq_memory + PHI_INV * eps_sq
            eps_sq_eff = self.eps_sq_memory
        else:
            eps_sq_eff = eps_sq

        # Qi coherence gate (pure field power, no eps^2 in denominator)
        rho_sq = rho ** 2
        phi_inv2 = PHI_INV ** 2
        q_coherence = rho / (rho + phi_inv2 + 1e-12)
        eps_norm = eps_sq_eff / (rho_sq + 1e-12)

        # Vacuum: where rho ~ 0, force q -> 1
        rho_max = rho.max()
        if rho_max > 1e-10:
            q_coherence = torch.where(rho < 0.01 * rho_max, torch.ones_like(q_coherence), q_coherence)

        non_vac = rho > 0.01 * rho.max() if rho_max > 1e-10 else torch.ones_like(rho, dtype=torch.bool)
        q_mean = q_coherence[non_vac].mean().item() if non_vac.any() else 1.0
        eps_mean = eps_norm[non_vac].mean().item() if non_vac.any() else 0.0

        # Standard softened gravity (no force suppression)
        ax, ay, az = self.solve_gravity(rho)
        accel = self.interpolate_accel(ax, ay, az, positions)

        return accel, q_mean, eps_mean

    # --- Leapfrog integrator ---
    def leapfrog_step(self, pos: torch.Tensor, vel: torch.Tensor,
                      masses: torch.Tensor, dt: float,
                      accel: Optional[torch.Tensor] = None,
                      vel_damp: float = 1.0,
                      qi_gate: bool = False
                      ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, float, float]:
        """Kick-drift-kick (velocity Verlet). Uses self.qi_field if qi_gate=True."""
        q_mean = 1.0
        eps_mean = 0.0

        if accel is None:
            if qi_gate:
                accel, q_mean, eps_mean = self.compute_acceleration_qi(pos, masses)
            else:
                accel = self.compute_acceleration(pos, masses)

        vel_half = vel + 0.5 * dt * accel
        if vel_damp < 1.0:
            vel_half = vel_half * vel_damp

        new_pos = pos + dt * vel_half
        new_pos = ((new_pos + self.L / 2.0) % self.L) - self.L / 2.0

        if qi_gate:
            new_accel, q_mean, eps_mean = self.compute_acceleration_qi(new_pos, masses)
        else:
            new_accel = self.compute_acceleration(new_pos, masses)

        total_mass = masses.sum()
        net_accel = (masses[:, None] * new_accel).sum(dim=0) / total_mass
        new_accel = new_accel - net_accel[None, :]

        new_vel = vel_half + 0.5 * dt * new_accel

        return new_pos, new_vel, new_accel, q_mean, eps_mean

    # --- Diagnostics ---
    def compute_energy(self, pos: torch.Tensor, vel: torch.Tensor,
                       masses: torch.Tensor) -> Tuple[float, float, float]:
        """KE = 0.5 * sum(m_i * v_i^2), PE via field method."""
        v2 = (vel ** 2).sum(dim=1)
        KE = 0.5 * (masses * v2).sum().item()

        rho = self.deposit_density(pos, masses)
        rho_complex = rho.to(torch.complex128)
        rho_hat = torch.fft.fftn(rho_complex)
        phi_hat = self.green_k.to(torch.complex128) * rho_hat
        phi = torch.fft.ifftn(phi_hat).real
        dV = self.dx ** 3
        PE = 0.5 * (rho * phi).sum().item() * dV

        return KE, PE, KE + PE

    def compute_virial(self, pos: torch.Tensor, vel: torch.Tensor,
                       masses: torch.Tensor) -> float:
        """Q = 2*KE / |PE|. Approaches 1 for virialized system."""
        KE, PE, _ = self.compute_energy(pos, vel, masses)
        return 2.0 * KE / (abs(PE) + 1e-10)

    def compute_angular_momentum(self, pos: torch.Tensor, vel: torch.Tensor,
                                  masses: torch.Tensor
                                  ) -> Tuple[float, float, float, float]:
        """L = sum(m_i * r_i x v_i)."""
        Lx = (masses * (pos[:, 1] * vel[:, 2] - pos[:, 2] * vel[:, 1])).sum().item()
        Ly = (masses * (pos[:, 2] * vel[:, 0] - pos[:, 0] * vel[:, 2])).sum().item()
        Lz = (masses * (pos[:, 0] * vel[:, 1] - pos[:, 1] * vel[:, 0])).sum().item()
        L_mag = math.sqrt(Lx ** 2 + Ly ** 2 + Lz ** 2)
        return Lx, Ly, Lz, L_mag

    def compute_lagrangian_radii(self, pos: torch.Tensor, masses: torch.Tensor,
                                  fractions: List[float] = None
                                  ) -> Dict[float, float]:
        """Radii enclosing given mass fractions."""
        if fractions is None:
            fractions = [0.1, 0.25, 0.5, 0.75, 0.9]

        total_mass = masses.sum().item()
        com = (masses[:, None] * pos).sum(dim=0) / total_mass
        r = torch.sqrt(((pos - com[None, :]) ** 2).sum(dim=1))

        sorted_idx = torch.argsort(r)
        sorted_mass = masses[sorted_idx]
        sorted_r = r[sorted_idx]
        cum_mass = torch.cumsum(sorted_mass, dim=0)

        result = {}
        for f in fractions:
            target = f * total_mass
            idx = torch.searchsorted(cum_mass, target)
            idx = min(idx.item(), len(r) - 1)
            result[f] = sorted_r[idx].item()

        return result
    def compute_diagnostics(self, pos: torch.Tensor, vel: torch.Tensor,
                            masses: torch.Tensor, config=None,
                            q_mean: float = 1.0, eps_mean: float = 0.0) -> dict:
        """Full diagnostic suite."""
        KE, PE, E_tot = self.compute_energy(pos, vel, masses)
        Q = 2.0 * KE / (abs(PE) + 1e-10)
        Lx, Ly, Lz, L_mag = self.compute_angular_momentum(pos, vel, masses)
        lagr = self.compute_lagrangian_radii(pos, masses)

        total_mass = masses.sum().item()
        com_x = (masses * pos[:, 0]).sum().item() / total_mass
        com_y = (masses * pos[:, 1]).sum().item() / total_mass
        com_z = (masses * pos[:, 2]).sum().item() / total_mass

        r = torch.sqrt((pos ** 2).sum(dim=1))

        result = {
            'KE': KE, 'PE': PE, 'E_tot': E_tot,
            'Q': Q,
            'Lx': Lx, 'Ly': Ly, 'Lz': Lz, 'L_mag': L_mag,
            'COM_x': com_x, 'COM_y': com_y, 'COM_z': com_z,
            'half_mass_r': lagr.get(0.5, 0.0),
            'r10': lagr.get(0.1, 0.0),
            'r90': lagr.get(0.9, 0.0),
            'max_r': r.max().item(), 'min_r': r.min().item(),
            'q_mean': q_mean, 'eps_mean': eps_mean,
        }
        return result


# --- Initial Condition Generators ---

def random_spherical_cluster(N: int, radius: float, config: NBodyConfig,
                              seed: int = 42
                              ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Uniform-density sphere with zero velocity."""
    gen = torch.Generator(device='cpu').manual_seed(seed)

    pos_list = []
    needed = N
    while needed > 0:
        batch = min(needed * 3, 10000)
        x = (torch.rand(batch, generator=gen) - 0.5) * 2 * radius
        y = (torch.rand(batch, generator=gen) - 0.5) * 2 * radius
        z = (torch.rand(batch, generator=gen) - 0.5) * 2 * radius
        r2 = x ** 2 + y ** 2 + z ** 2
        mask = r2 <= radius ** 2
        accepted = torch.stack([x[mask], y[mask], z[mask]], dim=1)
        pos_list.append(accepted[:needed])
        needed -= accepted.shape[0]

    pos = torch.cat(pos_list, dim=0)[:N]
    vel = torch.zeros(N, 3)
    masses = torch.ones(N)

    com = pos.mean(dim=0)
    pos = pos - com[None, :]

    return pos.to(config.device), vel.to(config.device), masses.to(config.device)


def plummer_sphere(N: int, scale_radius: float, config: NBodyConfig,
                    seed: int = 42
                    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Plummer (polytrope n=5) model - virialized, isotropic.

    Density: rho(r) ~ (1 + r^2/a^2)^(-5/2)
    """
    gen = torch.Generator(device='cpu').manual_seed(seed)

    a = scale_radius
    M_total = float(N)

    # Truncate at r_max = L/4
    r_max = config.L / 4.0
    u_max = r_max ** 3 / (r_max ** 2 + a ** 2) ** 1.5
    u = u_max * torch.rand(N, generator=gen)
    u = torch.clamp(u, min=1e-12, max=u_max)
    r = a / torch.sqrt(u ** (-2.0 / 3.0) - 1.0)

    phi_ang = 2.0 * math.pi * torch.rand(N, generator=gen)
    cos_theta = 2.0 * torch.rand(N, generator=gen) - 1.0
    sin_theta = torch.sqrt(1.0 - cos_theta ** 2)

    x = r * sin_theta * torch.cos(phi_ang)
    y = r * sin_theta * torch.sin(phi_ang)
    z = r * cos_theta
    pos = torch.stack([x, y, z], dim=1)

    masses = torch.ones(N)
    com = pos.mean(dim=0)
    pos = pos - com[None, :]

    # Velocities: rejection sampling from Plummer DF
    # g(q) ~ q^2 (1 - q^2)^(7/2) where q = v/v_esc
    g_max = (2.0 / 9.0) * (7.0 / 9.0) ** 3.5

    psi = config.G * M_total / torch.sqrt(r ** 2 + a ** 2)
    v_esc = torch.sqrt(2.0 * psi)

    vel_list = []
    needed = N
    while needed > 0:
        batch = min(needed * 15, 75000)
        q = torch.rand(batch, generator=gen)
        p_accept = (q ** 2) * (1.0 - q ** 2) ** 3.5 / g_max
        u_accept = torch.rand(batch, generator=gen)
        accept_mask = u_accept < p_accept
        accepted_q = q[accept_mask][:needed]
        vel_list.append(accepted_q)
        needed -= accepted_q.shape[0]

    q_all = torch.cat(vel_list, dim=0)[:N]
    v_mag = q_all * v_esc

    phi_v = 2.0 * math.pi * torch.rand(N, generator=gen)
    cos_theta_v = 2.0 * torch.rand(N, generator=gen) - 1.0
    sin_theta_v = torch.sqrt(1.0 - cos_theta_v ** 2)

    vx = v_mag * sin_theta_v * torch.cos(phi_v)
    vy = v_mag * sin_theta_v * torch.sin(phi_v)
    vz = v_mag * cos_theta_v
    vel = torch.stack([vx, vy, vz], dim=1)

    net_v = vel.mean(dim=0)
    vel = vel - net_v[None, :]

    return pos.to(config.device), vel.to(config.device), masses.to(config.device)


def cold_collapse(N: int, radius: float, config: NBodyConfig,
                   seed: int = 42
                   ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Uniform density sphere with tiny random velocities."""
    pos, _, masses = random_spherical_cluster(N, radius, config, seed)
    gen = torch.Generator(device='cpu').manual_seed(seed + 1)
    vel = 0.01 * radius * torch.randn(N, 3, generator=gen)
    vel = vel.to(config.device)
    return pos, vel, masses


def keplerian_disk(N: int, radius: float, config: NBodyConfig,
                    seed: int = 42
                    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Thin rotating disk with Keplerian orbital velocities."""
    gen = torch.Generator(device='cpu').manual_seed(seed)
    masses = torch.ones(N)

    u = torch.rand(N, generator=gen)
    r = radius * torch.sqrt(u)

    phi_ang = 2.0 * math.pi * torch.rand(N, generator=gen)

    x = r * torch.cos(phi_ang)
    y = r * torch.sin(phi_ang)
    z = 0.02 * radius * torch.randn(N, generator=gen)

    pos = torch.stack([x, y, z], dim=1)
    com = pos.mean(dim=0)
    pos = pos - com[None, :]

    M_total = float(N)
    M_enc = M_total * (r / radius) ** 2
    M_enc = torch.clamp(M_enc, min=0.01)
    v_circ = torch.sqrt(config.G * M_enc / torch.clamp(r, min=0.01))

    vx = -v_circ * y / torch.clamp(r, min=0.01)
    vy = v_circ * x / torch.clamp(r, min=0.01)
    vz = torch.zeros(N)
    vel = torch.stack([vx, vy, vz], dim=1)

    net_v = vel.mean(dim=0)
    vel = vel - net_v[None, :]

    return pos.to(config.device), vel.to(config.device), masses.to(config.device)


# --- Simulation Runner ---
def run_simulation(config: NBodyConfig, pos: torch.Tensor, vel: torch.Tensor,
                   masses: torch.Tensor, track: bool = True
                   ) -> Tuple[List[dict], Optional[torch.Tensor], NBodySolver3D]:
    """Main simulation loop."""
    solver = NBodySolver3D(n_grid=config.n_grid, L=config.L, G=config.G,
                            sigma=config.sigma, device=config.device,
                            qi_gate=config.qi_gate, qi_memory=config.qi_memory,
                            deposition_kernel=config.deposition_kernel,
                            alpha_yin=config.alpha_yin,
                            holographic_bound=config.holographic_bound,
                            holographic_eta=config.holographic_eta)
    N = pos.shape[0]
    total_mass = masses.sum().item()

    qi = torch.zeros(config.n_grid, config.n_grid, config.n_grid,
                     device=config.device)

    diag_history = []
    trail_frames = []
    phys_t = 0.0
    accel = None

    mode_str = 'Qi-gate ON' if config.qi_gate else 'Standard fixed-sigma'
    if config.qi_gate and config.qi_memory:
        mode_str += ' + memory'

    print(f"\n{'='*64}")
    print(f"  Cassi N-Body 3D GPU - Particle-Mesh Gravity")
    print(f"  {'-'*56}")
    print(f"  N = {N} bodies  |  m = 1.0 each  |  total M = {total_mass:.0f}")
    print(f"  Grid: {config.n_grid}^3  |  L = {config.L}  |  dx = {config.L/config.n_grid:.3f}")
    print(f"  G = {config.G}  |  sigma = {config.sigma}  |  sigma/dx = {config.sigma * config.n_grid / config.L:.2f}")
    print(f"  dt = {config.dt}  |  Steps = {config.n_steps}")
    print(f"  phi = {PHI:.4f}  |  Qi damp = 1/phi = {PHI_INV:.4f}  |  {mode_str}")
    print(f"{'='*64}\n")

    t_start = time.time()

    for step in range(config.n_steps):
        pos, vel, accel, q_mean, eps_mean = solver.leapfrog_step(
            pos, vel, masses, config.dt, accel=accel,
            vel_damp=config.vel_damp, qi_gate=config.qi_gate
        )

        # Qi memory field update
        rho = solver.deposit_density(pos, masses)
        qi = config.qi_damp * qi + (1.0 - config.qi_damp) * rho
        if config.qi_gate:
            solver.qi_field = qi
            # Five-element adaptive softening:
            #   Kfw = phi^-1 damps lack of coherence (Water damps Fire)
            #   gamma = turbulence increases softening (Metal cuts Wood)
            if step > 0:  # skip step 0 (q_mean from empty memory)
                sigma_eff = config.sigma * (1.0
                    + PHI_INV * (1.0 - q_mean)           # Kfw = phi^-1
                    + config.qi_gamma * eps_mean)        # turbulence
                sigma_eff = max(sigma_eff, config.sigma * 0.5)  # floor
                if abs(sigma_eff - solver.sigma) > 0.01 * config.sigma:
                    solver.set_softening(sigma_eff)
        phys_t += config.dt

        if track and step % config.track_every == 0:
            trail_frames.append(pos.cpu().clone())

        if step % config.report_every == 0:
            d = solver.compute_diagnostics(pos, vel, masses, config,
                                            q_mean=q_mean, eps_mean=eps_mean)
            diag_history.append(d)
            qi_info = f" q_avg={q_mean:.4f}" if config.qi_gate else ""
            print(f"  t={phys_t:.3f} | E={d['E_tot']:+.4f} | "
                  f"KE={d['KE']:.4f} PE={d['PE']:+.4f} | "
                  f"Q={d['Q']:.4f} | "
                  f"R_half={d['half_mass_r']:.4f} | "
                  f"|L|={d['L_mag']:.4f}{qi_info}")

            if math.isnan(d['E_tot']):
                print(f"\n  ERROR: NaN detected at step {step}. Aborting.")
                break

    elapsed = time.time() - t_start
    ms_per_step = elapsed / (step + 1) * 1000
    print(f"\n  Wall time: {elapsed:.1f}s  |  {ms_per_step:.1f} ms/step")
    print(f"  Field method: {config.n_grid}^3 log {config.n_grid} ~ "
          f"{config.n_grid**3 * math.log2(config.n_grid):.0f} op/step")
    print(f"  Pairwise would be O(N^2) = {N**2} force calcs/step")

    trails = torch.stack(trail_frames, dim=0) if trail_frames else None
    return diag_history, trails, solver


# --- Plotting ---
def plot_results(pos: torch.Tensor, vel: torch.Tensor, masses: torch.Tensor,
                 diag_history: List[dict], config: NBodyConfig,
                 trails: Optional[torch.Tensor] = None,
                 savepath: str = 'cassi_nbody.png'):
    """Multi-panel diagnostic plot."""
    pos_np = pos.cpu().numpy()
    N = pos_np.shape[0]

    fig, axes = plt.subplots(2, 3, figsize=(18, 12))

    # Panel 1: XY projection
    ax = axes[0, 0]
    if trails is not None and trails.shape[0] > 0:
        trails_np = trails.cpu().numpy()
        n_trail = min(N, 50)
        for i in range(n_trail):
            tx = trails_np[:, i, 0]
            ty = trails_np[:, i, 1]
            ax.plot(tx, ty, lw=0.3, alpha=0.5, color='gray')
    ax.scatter(pos_np[:, 0], pos_np[:, 1], c='white', s=2, alpha=0.8, zorder=5,
               edgecolors='black', linewidth=0.3)
    ax.set(xlabel='x', ylabel='y', title=f'N={N} Final Positions (XY)')
    ax.set_aspect('equal')
    ax.grid(alpha=0.2)

    # Panel 2: Energy evolution
    ax = axes[0, 1]
    times = [i * config.report_every * config.dt for i in range(len(diag_history))]
    KE = [d['KE'] for d in diag_history]
    PE = [d['PE'] for d in diag_history]
    E_tot = [d['E_tot'] for d in diag_history]
    ax.plot(times, KE, 'r-', lw=1, label='KE')
    ax.plot(times, PE, 'b-', lw=1, label='PE')
    ax.plot(times, E_tot, 'k--', lw=1.5, label='Total E')
    ax.set(xlabel='Time', ylabel='Energy', title='Energy Evolution')
    ax.legend(fontsize=8)
    ax.grid(alpha=0.2)

    # Panel 3: Virial ratio
    ax = axes[0, 2]
    Q_vals = [d['Q'] for d in diag_history]
    ax.plot(times, Q_vals, 'g-', lw=1.5)
    ax.axhline(y=1.0, color='gray', ls='--', lw=1, label='Q=1')
    if config.qi_gate:
        q_vals = [d.get('q_mean', 1.0) for d in diag_history]
        ax2 = ax.twinx()
        ax2.plot(times, q_vals, 'orange', lw=1, ls=':', label='q_avg coherence')
        ax2.set_ylabel('q_avg', color='orange')
        ax2.legend(fontsize=7, loc='lower right')
    ax.set(xlabel='Time', ylabel='Q = 2KE/|PE|', title='Virial Ratio')
    ax.legend(fontsize=8, loc='upper right')
    ax.grid(alpha=0.2)

    # Panel 4: Lagrangian radii
    ax = axes[1, 0]
    for key, label, color in [('r10', '10%', 'cyan'), ('half_mass_r', '50%', 'magenta'), ('r90', '90%', 'orange')]:
        vals = [d[key] for d in diag_history]
        if any(v > 0 for v in vals):
            ax.plot(times, vals, lw=1.5, label=f'R_{label}', color=color)
    ax.set(xlabel='Time', ylabel='Radius', title='Lagrangian Radii')
    ax.legend(fontsize=8)
    ax.grid(alpha=0.2)

    # Panel 5: Angular momentum
    ax = axes[1, 1]
    L_mag = [d['L_mag'] for d in diag_history]
    Lx = [d['Lx'] for d in diag_history]
    Ly = [d['Ly'] for d in diag_history]
    Lz = [d['Lz'] for d in diag_history]
    ax.plot(times, L_mag, 'k-', lw=1.5, label='|L|')
    ax.plot(times, Lx, 'r--', lw=0.8, alpha=0.5, label='Lx')
    ax.plot(times, Ly, 'g--', lw=0.8, alpha=0.5, label='Ly')
    ax.plot(times, Lz, 'b--', lw=0.8, alpha=0.5, label='Lz')
    ax.set(xlabel='Time', ylabel='Angular Momentum', title='Angular Momentum')
    ax.legend(fontsize=7)
    ax.grid(alpha=0.2)

    # Panel 6: Radial density profile
    ax = axes[1, 2]
    com = pos_np.mean(axis=0)
    r = np.sqrt(((pos_np - com) ** 2).sum(axis=1))
    r_max_display = np.percentile(r, 95)
    bins = np.linspace(0, r_max_display, 40)
    hist, edges = np.histogram(r, bins=bins, weights=masses.cpu().numpy())
    bin_centers = 0.5 * (edges[:-1] + edges[1:])
    shell_vol = (4.0 / 3.0) * math.pi * (edges[1:] ** 3 - edges[:-1] ** 3)
    shell_vol = np.maximum(shell_vol, 1e-10)
    rho_r = hist / shell_vol
    valid = hist > 0
    ax.loglog(bin_centers[valid], rho_r[valid], 'k.-', ms=3, lw=0.8)
    ax.set(xlabel='r', ylabel='rho(r)', title='Radial Density Profile')
    ax.grid(alpha=0.2, which='both')

    suptitle = (
        f'Cassi N-Body 3D GPU: N={N}, Grid={config.n_grid}^3\n'
        f'G={config.G} | sigma={config.sigma} | dt={config.dt} | '
        f'Steps={config.n_steps} | {"Qi-gated" if config.qi_gate else "Standard"}'
    )
    fig.suptitle(suptitle, fontsize=9, fontweight='bold', family='monospace')
    plt.tight_layout()
    plt.savefig(savepath, dpi=150, bbox_inches='tight')
    print(f"\n  Saved plot: {savepath}")

    if diag_history:
        final_d = diag_history[-1]
        print(f"\n  === Final State ===")
        print(f"  Energy:      {final_d['E_tot']:+.4f}")
        print(f"  Virial Q:    {final_d['Q']:.4f}  (equilibrium = 1.0)")
        print(f"  R_half:      {final_d['half_mass_r']:.4f}")
        print(f"  |L|:         {final_d['L_mag']:.4f}")
        if config.qi_gate:
            print(f"  q_avg:       {final_d.get('q_mean', 1.0):.4f}")

    return fig


# --- CLI ---
IC_GENERATORS = {
    'spherical': random_spherical_cluster,
    'plummer': plummer_sphere,
    'cold': cold_collapse,
    'disk': keplerian_disk,
}


def main():
    parser = argparse.ArgumentParser(
        description='Cassi N-Body 3D GPU - Particle-Mesh Gravity Solver'
    )
    parser.add_argument('--N', type=int, default=1000, help='Number of bodies')
    parser.add_argument('--n-grid', type=int, default=128, help='Grid resolution')
    parser.add_argument('--L', type=float, default=20.0, help='Box size')
    parser.add_argument('--G', type=float, default=1.0, help='Gravitational constant')
    parser.add_argument('--sigma', type=float, default=0.4, help='Gaussian softening length')
    parser.add_argument('--deposition', type=str, default='CIC',
                        choices=['CIC', 'TSC', 'GAUSSIAN'],
                        help='Deposition kernel')
    parser.add_argument('--dt', type=float, default=0.001, help='Timestep')
    parser.add_argument('--steps', type=int, default=5000, help='Number of steps')
    parser.add_argument('--vel-damp', type=float, default=1.0,
                        help='Velocity damping (< 1 adds dissipation)')
    parser.add_argument('--mode', type=str, default='plummer',
                        choices=['spherical', 'plummer', 'cold', 'disk', 'benchmark'],
                        help='Initial condition type')
    parser.add_argument('--radius', type=float, default=5.0,
                        help='Cluster radius or Plummer scale radius')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--report-every', type=int, default=250,
                        help='Steps between diagnostic reports')
    parser.add_argument('--track-every', type=int, default=50,
                        help='Steps between trajectory snapshots')
    parser.add_argument('--output', type=str, default='cassi_nbody.png',
                        help='Output plot path')
    parser.add_argument('--no-track', action='store_true',
                        help='Disable trajectory tracking (saves memory)')
    parser.add_argument('--qi-gate', action='store_true',
                        help='Qi-gated adaptive softening (density memory coherence)')
    parser.add_argument('--qi-memory', action='store_true',
                        help='Qi memory: per-cell EMA of eps^2 (temporal inertia)')
    parser.add_argument('--qi-beta', type=float, default=0.5,
                        help='Qi softening modulation strength (deprecated, use --qi-gamma)')
    parser.add_argument('--qi-gamma', type=float, default=1.0,
                        help='Qi turbulence contribution to softening (five-element gamma)')
    parser.add_argument('--alpha-yin', type=float, default=0.0,
                        help='Yin relative-entropy nonlinear source (0=off, 0.5 typical)')
    parser.add_argument('--holographic', action='store_true',
                        help='Enable holographic I_max smoothing')
    parser.add_argument('--holographic-eta', type=float, default=1.0,
                        help='Holographic bound coefficient')
    args = parser.parse_args()

    if args.mode == 'benchmark':
        args.N = 100
    config = NBodyConfig(
        n_grid=args.n_grid, L=args.L, G=args.G, sigma=args.sigma,
        dt=args.dt, n_steps=args.steps, vel_damp=args.vel_damp,
        deposition_kernel=args.deposition,
        qi_gate=args.qi_gate, qi_memory=args.qi_memory,
        qi_beta=args.qi_beta,
        qi_gamma=args.qi_gamma,
        alpha_yin=args.alpha_yin,
        holographic_bound=args.holographic,
        holographic_eta=args.holographic_eta,
        report_every=args.report_every, track_every=args.track_every,
    )

    print(f"Device: {config.device}")
    if config.device.type == 'cuda':
        print(f"GPU: {torch.cuda.get_device_name(config.device)}")
        print(f"VRAM: {torch.cuda.get_device_properties(config.device).total_memory / 1e9:.1f} GB")

    gen_func = IC_GENERATORS[args.mode]
    pos, vel, masses = gen_func(args.N, args.radius, config, seed=args.seed)

    print(f"\n  Initial: {args.mode}, N={args.N}, radius={args.radius}")
    print(f"  Total mass: {masses.sum().item():.1f}")

    diag_history, trails, solver = run_simulation(
        config, pos, vel, masses, track=not args.no_track
    )

    plot_results(pos, vel, masses, diag_history, config,
                 trails=trails, savepath=args.output)

    print("\n  Done.\n")


if __name__ == '__main__':
    main()
