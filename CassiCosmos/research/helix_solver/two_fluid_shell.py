"""two_fluid_shell.py -- the two-fluid PDE on the axial grids (uniform vs phi-shell).

Wave-5 probe machinery, per CassiCosmos/research/helix_solver/two_fluid_shell_prereg.md.

The sim's two-fluid PDE (cassi_two_fluid.glsl), 1D axial restriction:
    d2EY/dt2 = c^2 d2EY/dz2 - w0^2 (EY - phi EI)
    d2EI/dt2 = c^2 d2EI/dz2 + w0^2 (EY - phi EI)
with the finite-volume Laplacian (wave 1's mandatory conservative operator) on
either a uniform reference line or the smooth-cascade phi-shell grid (wave 2).
Leapfrog (order-2 staggered), the gate-iv Gaussian source.

Provides (deterministic, numpy):
  - TwoFluidLine: holds a grid, the FV Laplacian, and the leapfrog two-fluid step.
  - make_reference(span, K), make_phi_shell(K, m): the two grids (reuse smooth_grid).
  - run(., Nsteps): evolve, returning the EY/EI/rho time traces at chosen probes.
"""

from __future__ import annotations

import numpy as np

from phi_grid import PHI, second_derivative_matrix, edge_matrices
from smooth_cascade import smooth_grid

OMEGA2 = 20.0
C = 1.0


def _fv_laplacian(z):
    """A = -M^-1 B^T W B (the conservative finite-volume Laplacian), returns A."""
    B, W, M = edge_matrices(z)
    Minv = np.diag(1.0 / np.diag(M))
    BtWB = -(B.T @ W @ B)
    return Minv @ BtWB


def make_reference(span, K):
    """Uniform reference line over [0, span] with K cells (spacing h = span/K)."""
    return np.linspace(0.0, span, K + 1, dtype=np.float64)


def make_phi_shell(K=8, z0=1.0, m=12):
    """The smooth-cascade phi-shell grid of wave 2."""
    return smooth_grid(K, z0, m)


class TwoFluidLine:
    """Two-fluid wave on a 1D line with the finite-volume Laplacian.

    Leapfrog: v += dt (c^2 A psi - omega^2 couple); psi += dt v. The couple is
    +- omega2 (EY - phi EI) as in the shader. Deterministic.
    """

    def __init__(self, z, w0_2=OMEGA2, c=C):
        self.z = np.asarray(z, dtype=np.float64)
        self.N = len(self.z)
        self.w0_2 = float(w0_2)
        self.c = float(c)
        self.A = _fv_laplacian(self.z)
        self.dt = 0.05 * np.min(np.diff(self.z))   # far below CFL
        self._kicked = False

    def kick(self, ey, ei, vey, vei):
        """One half-step of acceleration onto the velocities: the proper staggered
        (leapfrog) start. Without it the integrator is O(dt) first-order (the wave-1
        IC-stagger lesson: free-case drift 0.49 -> 3.6e-4 with the kick)."""
        dt = self.dt
        diff = ey - PHI * ei
        aey = self.c * self.c * (self.A @ ey) - self.w0_2 * diff
        aei = self.c * self.c * (self.A @ ei) + self.w0_2 * diff
        return vey + 0.5 * dt * aey, vei + 0.5 * dt * aei

    def step(self, ey, ei, vey, vei):
        dt = self.dt
        if not self._kicked:
            vey, vei = self.kick(ey, ei, vey, vei)
            self._kicked = True
        diff = ey - PHI * ei
        # accelerate
        aey = self.c * self.c * (self.A @ ey) - self.w0_2 * diff
        aei = self.c * self.c * (self.A @ ei) + self.w0_2 * diff
        vey_n = vey + dt * aey
        vei_n = vei + dt * aei
        ey_n = ey + dt * vey_n
        ei_n = ei + dt * vei_n
        # hard Dirichlet at both ends
        ey_n[0] = ey_n[-1] = 0.0
        ei_n[0] = ei_n[-1] = 0.0
        vey_n[0] = vey_n[-1] = 0.0
        vei_n[0] = vei_n[-1] = 0.0
        return ey_n, ei_n, vey_n, vei_n

    def run(self, ey, ei, vey, vei, nsteps, probe_idx=()):
        """Evolve nsteps; return the final (ey,ei) and the rho time traces at probe_idx."""
        n = len(next(iter([ey])))
        traces = {idx: [] for idx in probe_idx}
        for _ in range(nsteps):
            ey, ei, vey, vei = self.step(ey, ei, vey, vei)
            for idx in probe_idx:
                traces[idx].append((ey[idx] + ei[idx]))
        return ey, ei, vey, vei, traces


# the gate-iv Gaussian source on the ground state (two-fluid, phi-separated EY/EI)
def make_ic(z, amp=0.05, width=None):
    """EY Gaussian centered, EI offset by the phi-separation; rho = EY+EI."""
    N = len(z)
    zc = 0.5 * (z[0] + z[-1])
    if width is None:
        width = 0.02 * (z[-1] - z[0])
    ey = amp * np.exp(-((z - zc) ** 2) / (2 * width ** 2))
    # EI offset by the Yin-Yang separation (the shader source_ei offset ratio)
    ei_off = 0.2 * (z[-1] - z[0])
    ei = amp * 0.707 * np.exp(-((z - (zc + ei_off)) ** 2) / (2 * width ** 2))
    ey[0] = ey[-1] = ei[0] = ei[-1] = 0.0
    return ey, ei
