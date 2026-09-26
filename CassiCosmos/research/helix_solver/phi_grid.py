"""phi_grid.py -- the phi-shelled axial (string/cascade) grid for the ultimate Cassi solver.

Wave-1 probe machinery, per CassiCosmos/research/helix_solver/helix_solver_prereg.md.

Provides:
  - make_phi_grid(K, z0) / make_uniform_grid(z0, zK, N): the two grids (the prereg SS1.1).
  - non-uniform 2nd- and 1st-derivative stencils (polynomial-exact, prereg SS1.2).
  - second_derivative_matrix(grid) -> the tridiagonal operator A (u''_i = (A u)_i).
  - first_derivative(grid) -> D1.
  - WaveGrid: a held grid + leapfrog stepper (prereg SS1.3).

Deterministic: no RNG anywhere. numpy only.
"""

from __future__ import annotations

import numpy as np

PHI = 1.618033988749895


# ---------------------------------------------------------------------------
# Grids (prereg SS1.1)
# ---------------------------------------------------------------------------

def make_phi_grid(K: int = 8, z0: float = 1.0) -> np.ndarray:
    """z_k = z0 * phi^k for k = 0..K-1. Spacing ratio h_{k+1}/h_k = phi exactly."""
    return z0 * PHI ** np.arange(K, dtype=np.float64)


def make_uniform_grid(z0: float, zK: float, N: int) -> np.ndarray:
    """The same [z0, zK] span, N uniform points (the null arm)."""
    return np.linspace(z0, zK, N)


# ---------------------------------------------------------------------------
# Non-uniform, polynomial-exact stencils (prereg SS1.2, flux-conservative form)
# ---------------------------------------------------------------------------

def first_derivative_matrix(z: np.ndarray) -> np.ndarray:
    """D1 so u'_i = (D1 @ u)_i at interior points, 1st row/col zeroed (Dirichlet ends)."""
    n = len(z)
    D = np.zeros((n, n))
    h = np.diff(z)
    h_m = np.concatenate(([h[0]], h))
    h_p = np.concatenate((h, [h[-1]]))
    for i in range(1, n - 1):
        a = h_m[i]
        b = h_p[i]
        # u'_i = [a^2 u_{i+1} - b^2 u_{i-1} + (b^2 - a^2) u_i] / (a b (a+b))
        D[i, i - 1] = -b * b / (a * b * (a + b))
        D[i, i] = (b * b - a * a) / (a * b * (a + b))
        D[i, i + 1] = a * a / (a * b * (a + b))
    return D


def edge_matrices(z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(B, W, M) for the finite-volume wave operator.

    B = (n-1)x n edge-difference incidence (B u)_k = u_{k+1} - u_k.
    W = diag(1/h_k) edge weights.
    M = diag((h_{k-1}+h_k)/2) cell volumes.

    The Laplacian A = -M^-1 B^T W B is symmetric under the M inner product and
    gives (A z^2)_i = 2 exactly on any grid (the finite-volume form), so it
    conserves E = 0.5 (v^T M v + c^2 (Bu)^T W (Bu)) under the M-weighted leapfrog.
    """
    n = len(z)
    h = np.diff(z)
    B = np.zeros((n - 1, n))
    for k in range(n - 1):
        B[k, k] = -1.0
        B[k, k + 1] = 1.0
    W = np.diag(1.0 / h)
    # cell volumes: interior M_ii = (h_{i-1}+h_i)/2, ends = the half-cell
    Mvol = np.empty(n)
    Mvol[0] = h[0] / 2.0
    Mvol[-1] = h[-1] / 2.0
    Mvol[1:-1] = (h[:-1] + h[1:]) / 2.0
    M = np.diag(Mvol)
    return B, W, M


def second_derivative_matrix(z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The finite-volume Laplacian A, mass M, and edge data (B, W).

    Returns (A, Minv, Bt_W_B): A = -M^-1 B^T W B, Minv = M^-1, and BtWB = B^T W B.
    (A u)_i = [(u_{i+1}-u_i)/h_i - (u_i-u_{i-1})/h_{i-1}] / [(h_i+h_{i-1})/2].
    """
    B, W, M = edge_matrices(z)
    BtWB = -(B.T @ W @ B)
    Minv = np.diag(1.0 / np.diag(M))
    A = Minv @ BtWB
    return A, Minv, (B, W)


# ---------------------------------------------------------------------------
# The stepper (prereg SS1.3)
# ---------------------------------------------------------------------------

class WaveGrid:
    """Holds a grid, its wave operator, and a staggered leapfrog stepper."""

    def __init__(self, z: np.ndarray, c: float = 1.0):
        self.z = np.asarray(z, dtype=np.float64)
        self.c = float(c)
        self.N = len(self.z)
        # the finite-volume Laplacian A (-M^-1 B^T W B) and the edge data (B, W)
        A, Minv, (B, W) = second_derivative_matrix(self.z)
        self.A, self.Minv, self.B, self.W = A, Minv, B, W
        # cell-volume mass matrix M (diagonal)
        self.M = np.diag(1.0 / np.diag(self.Minv))
        self.D1 = first_derivative_matrix(self.z)   # u'  operator
        self.BtWB = -(self.B.T @ self.W @ self.B)
        self.dt: float | None = None

    def set_dt(self, dt: float) -> None:
        # CFL guard: explicit leapfrog needs c*dt <= min spacing (Von Neumann bound).
        assert dt <= np.min(np.diff(self.z)) / self.c, "dt above the CFL bound"
        self.dt = float(dt)

    def step(self, u: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """One M-weighted leapfrog step: v += dt c^2 A u; u += dt v. Ends stay 0."""
        assert self.dt is not None, "set_dt() first"
        dt = self.dt
        v = v + dt * self.c * self.c * (self.A @ u)
        u = u + dt * v
        u[0] = 0.0
        u[-1] = 0.0
        v[0] = 0.0
        v[-1] = 0.0
        return u, v

    def run(self, u: np.ndarray, v: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
        for _ in range(n):
            u, v = self.step(u, v)
        return u, v


# ---------------------------------------------------------------------------
# Energy (for the harness gate)
# ---------------------------------------------------------------------------

def energy(u: np.ndarray, v: np.ndarray, gr: WaveGrid) -> float:
    """Finite-volume wave energy, conserved by the M-weighted leapfrog.

    E = 0.5 * (v^T M v + c^2 (Bu)^T W (Bu)), with M the cell-volume mass matrix,
    B the edge incidence, W = diag(1/h). This is the exact symplectic invariant
    on any (non-uniform) grid.
    """
    kinetic = float(v @ (gr.M @ v))
    edge = float((gr.B @ u) @ (gr.W @ (gr.B @ u)))
    return 0.5 * (kinetic + gr.c * gr.c * edge)
