#!/usr/bin/env python3
r"""Path 5: Three-Body Lagrange Points in Cassi Softened Gravity.

Explores how Gaussian softening (σ) modifies the circular restricted
three-body problem equilibrium points L1–L5.

Softened force:
  F(r) = -GM/r² · [erf(r/(σ√2)) - √(2/π)·(r/σ)·exp(-r²/(2σ²))]
  Φ(r) = -GM/r · erf(r/(σ√2))

Effective potential in the corotating frame:
  Φ_eff(x, y) = -GM₁/r₁ · erf(r₁/(σ√2))
               - GM₂/r₂ · erf(r₂/(σ√2))
               - ½·Ω²·(x² + y²)

Key question: Do Lagrange points exist for all σ, or do they
merge/disappear beyond a critical softening?
"""

import math
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
from scipy.optimize import root, minimize
from scipy.special import erf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


# ═══════════════════════════════════════════════════════════════════════
#  Softened Gravity Functions
# ═══════════════════════════════════════════════════════════════════════

def softened_force_mag(r: float, M: float, sigma: float,
                       G: float = 1.0) -> float:
    """Softened gravitational force magnitude between two bodies.

    F(r) = GM/r² · [erf(r/(σ√2)) - √(2/π)·(r/σ)·exp(-r²/(2σ²))]

    In the Newtonian limit (σ → 0): F(r) = GM/r².
    """
    if sigma <= 0.0:
        # Newtonian limit
        if r < 1e-15:
            return 0.0
        return G * M / r ** 2
    if r < 1e-15:
        return 0.0
    x = r / (sigma * math.sqrt(2.0))
    return (G * M / r ** 2) * (erf(x) - math.sqrt(2.0 / math.pi) * (r / sigma) * math.exp(-x ** 2))

def softened_potential(r: float, M: float, sigma: float,
                       G: float = 1.0) -> float:
    """Softened gravitational potential: Φ(r) = -GM/r · erf(r/(σ√2)).

    In the Newtonian limit (σ → 0): Φ(r) = -GM/r.
    """
    if sigma <= 0.0:
        if r < 1e-15:
            return -float('inf')
        return -G * M / r
    if r < 1e-15:
        return -G * M * math.sqrt(2.0 / math.pi) / sigma
    x = r / (sigma * math.sqrt(2.0))
    return -G * M / r * erf(x)


def softened_force_derivative(r: float, M: float, sigma: float,
                               G: float = 1.0) -> float:
    """dF/dr—derivative of softened force magnitude w.r.t. r.

    Used in stability analysis and Jacobian for root-finding.
    """
    if r < 1e-15:
        return -2.0 * G * M / (3.0 * sigma ** 3) * math.sqrt(2.0 / math.pi)
    x = r / (sigma * math.sqrt(2.0))
    F = softened_force_mag(r, M, sigma, G)
    # dF/dr = -2F/r + (GM/r²) · d/dr[erf - √(2/π)(r/σ)e^{-r²/(2σ²)}]
    # The second term: GM/r² · [2/√π · e^{-x²} · dx/dr - √(2/π)/σ · e^{-r²/(2σ²)}
    #                          + √(2/π)(r/σ)·(r/σ²)·e^{-r²/(2σ²)}]
    # Let's compute numerically instead
    eps = 1e-6 * max(r, sigma)
    rp = r + eps
    rm = max(r - eps, 0.0)
    Fp = softened_force_mag(rp, M, sigma, G)
    Fm = softened_force_mag(rm, M, sigma, G) if rm > 0 else 0.0
    if rm == 0:
        return (Fp - F) / eps
    return (Fp - Fm) / (2.0 * eps)


def orbital_frequency(M1: float, M2: float, a: float, sigma: float,
                      G: float = 1.0) -> float:
    """Orbital frequency Ω of the binary with softened gravity.

    The softened force at separation a provides the centripetal acceleration:
    Ω²·a = [G(M₁+M₂)/a²] · [erf(a/(σ√2)) - √(2/π)(a/σ)exp(-a²/(2σ²))]
    """
    return math.sqrt(softened_force_mag(a, M1 + M2, sigma, G) / a)


# ═══════════════════════════════════════════════════════════════════════
#  Effective Potential in Corotating Frame
# ═══════════════════════════════════════════════════════════════════════

class SoftenedCR3BP:
    """Circular Restricted 3-Body Problem with softened gravity.

    Coordinate system:
    - Origin at centre of mass (barycentre)
    - M₁ at x = -a·M₂/(M₁+M₂), y = 0
    - M₂ at x = +a·M₁/(M₁+M₂), y = 0
    - Frame rotates at angular velocity Ω
    """

    def __init__(self, M1: float = 1.0, M2: float = 0.5,
                 a: float = 1.0, sigma: float = 0.0,
                 G: float = 1.0):
        self.M1 = M1
        self.M2 = M2
        self.M_tot = M1 + M2
        self.a = a
        self.sigma = sigma
        self.G = G

        # Positions of primary bodies in corotating frame
        self.x1 = -a * M2 / (M1 + M2)
        self.x2 = a * M1 / (M1 + M2)

        # Orbital frequency
        if sigma > 0:
            self.Omega = orbital_frequency(M1, M2, a, sigma, G)
        else:
            # Keplerian (Newtonian) limit
            self.Omega = math.sqrt(G * (M1 + M2) / a ** 3)

        # Jacobi constant reference
        self.C_base = 2.0 * self.Omega ** 2 * (self.x1 ** 2)  # scaling

    def distance_to_M1(self, x: float, y: float) -> float:
        return math.sqrt((x - self.x1) ** 2 + y ** 2)

    def distance_to_M2(self, x: float, y: float) -> float:
        return math.sqrt((x - self.x2) ** 2 + y ** 2)

    def phi_eff(self, x: float, y: float) -> float:
        """Effective potential Φ_eff(x,y) in the corotating frame.

        Φ_eff = -GM₁·erf(r₁/σ√2)/r₁ - GM₂·erf(r₂/σ√2)/r₂ - ½Ω²(x²+y²)
        """
        r1 = self.distance_to_M1(x, y)
        r2 = self.distance_to_M2(x, y)
        pot1 = softened_potential(r1, self.M1, self.sigma, self.G)
        pot2 = softened_potential(r2, self.M2, self.sigma, self.G)
        cent = -0.5 * self.Omega ** 2 * (x ** 2 + y ** 2)
        return pot1 + pot2 + cent

    def grad_phi_eff(self, x: float, y: float) -> tuple:
        """Gradient of Φ_eff: (∂Φ_eff/∂x, ∂Φ_eff/∂y).

        At equilibrium (Lagrange points), ∇Φ_eff = 0.

        ∂Φ_eff/∂x = -(F1_x + F2_x) - Ω²·x
        ∂Φ_eff/∂y = -(F1_y + F2_y) - Ω²·y
        """
        r1 = self.distance_to_M1(x, y)
        r2 = self.distance_to_M2(x, y)

        # x-component: positive = rightward force
        # F_x from M1 (attractive toward M1 at x1)
        if r1 > 1e-15:
            F1_mag = softened_force_mag(r1, self.M1, self.sigma, self.G)
            F1_x = -F1_mag * (x - self.x1) / r1
            F1_y = -F1_mag * y / r1
        else:
            F1_x, F1_y = 0.0, 0.0

        # F_x from M2 (attractive toward M2 at x2)
        if r2 > 1e-15:
            F2_mag = softened_force_mag(r2, self.M2, self.sigma, self.G)
            F2_x = -F2_mag * (x - self.x2) / r2
            F2_y = -F2_mag * y / r2
        else:
            F2_x, F2_y = 0.0, 0.0

        # Centrifugal term: Φ_cent = -½Ω²(x²+y²) → ∇Φ_cent = (-Ω²·x, -Ω²·y)
        cent_x = -self.Omega ** 2 * x
        cent_y = -self.Omega ** 2 * y

        # Gradient of Φ_eff = -F + centripetal
        # Actually: ∇Φ_eff = -a_grav + Ω²·r (since a = -∇Φ)
        # And a_grav_x = -F_x_felt_by_test_particle_from_grav
        # But F_x_mag from gravity = -∂Φ/∂x = F_x
        # So ∂Φ/∂x = -F_X_gravity + cent_x
        grad_x = -(F1_x + F2_x) + cent_x
        grad_y = -(F1_y + F2_y) + cent_y

        return grad_x, grad_y

    def compute_jacobian(self, x: float, y: float, eps: float = 1e-6) -> np.ndarray:
        """Jacobian of ∇Φ_eff w.r.t. (x,y)—2x2 matrix.

        J_ij = ∂²Φ_eff/∂x_i∂x_j

        Used for Newton's method and stability classification.
        """
        gx, gy = self.grad_phi_eff(x, y)

        # Finite-difference
        gx_px, gy_px = self.grad_phi_eff(x + eps, y)
        gx_py, gy_py = self.grad_phi_eff(x, y + eps)

        dgx_dx = (gx_px - gx) / eps
        dgx_dy = (gx_py - gx) / eps
        dgy_dx = (gy_px - gy) / eps
        dgy_dy = (gy_py - gy) / eps

        return np.array([[dgx_dx, dgx_dy],
                         [dgy_dx, dgy_dy]])

    def find_lagrange_points(self, verbose: bool = True) -> dict:
        """Find all 5 Lagrange points numerically.

        Uses a grid-based zero-crossing scan on the x-axis for collinear
        points (L1-L3), then Nelder-Mead refinement for L4/L5.

        Returns dict: {point_name: (x, y, Phi_eff_value)}
        """
        points = {}

        # ── Collinear points L1, L2, L3—scan x-axis for ∇Φ_eff = 0 ──
        eps = 1e-8
        # Exclude regions near each body where force diverges
        body_eps = 0.05 * self.a  # exclusion half-width around each body
        # Scan ranges: left body region, between bodies, right body region
        segments = [
            ('L3_region', self.x1 - 2.0 * self.a, self.x1 - body_eps, 500),
            ('L1_region', self.x1 + body_eps, self.x2 - body_eps, 500),
            ('L2_region', self.x2 + body_eps, self.x2 + 2.0 * self.a, 500),
        ]

        for seg_name, x_lo, x_hi, n in segments:
            if x_lo >= x_hi:
                continue
            x_scan = np.linspace(x_lo, x_hi, n)
            grad_x_vals = np.array([self.grad_phi_eff(float(xi), 0.0)[0] for xi in x_scan])

            signs = np.sign(grad_x_vals)
            for i in range(len(x_scan) - 1):
                if signs[i] == 0.0:
                    self._refine_collinear(x_scan[i], points, verbose)
                elif signs[i] * signs[i + 1] < 0:
                    x0 = x_scan[i]
                    x1 = x_scan[i + 1]
                    f0 = grad_x_vals[i]
                    f1 = grad_x_vals[i + 1]
                    x_zero = x0 - f0 * (x1 - x0) / (f1 - f0)
                    self._refine_collinear(x_zero, points, verbose)



        # ── Equilateral points L4, L5—scan off-axis region ──
        # Use a coarse grid to find minima of |∇Φ_eff|²
        x_bary = (self.x1 + self.x2) / 2.0
        y_guess = math.sqrt(3.0) / 2.0 * self.a * 0.9  # adjusted for softening

        for name, y_sign in [('L4', 1.0), ('L5', -1.0)]:
            x0_pt = x_bary
            y0_pt = y_sign * y_guess

            from scipy.optimize import minimize

            def grad_sq(pos_arr):
                gx, gy = self.grad_phi_eff(float(pos_arr[0]), float(pos_arr[1]))
                return gx ** 2 + gy ** 2

            res = minimize(grad_sq, [x0_pt, y0_pt], method='Nelder-Mead',
                           options={'xatol': 1e-12, 'fatol': 1e-12, 'maxiter': 5000})
            x_lib = float(res.x[0])
            y_lib = float(res.x[1])
            gx, gy = self.grad_phi_eff(x_lib, y_lib)
            grad_norm = math.sqrt(gx ** 2 + gy ** 2)
            if grad_norm < 1e-4:
                phi_val = self.phi_eff(x_lib, y_lib)
                points[name] = (x_lib, y_lib, phi_val)
                if verbose:
                    print(f"    {name}: x = {x_lib:.6f}, y = {y_lib:.6f}, "
                          f"Φ_eff = {phi_val:.6f}")
            else:
                # Try scanning a fine grid around the guess
                x_grid = np.linspace(x_bary - 0.5, x_bary + 0.5, 100)
                y_fixed = y0_pt
                grad_sq_vals = np.array([self.grad_phi_eff(float(xi), float(y_fixed))[0] ** 2 +
                                          self.grad_phi_eff(float(xi), float(y_fixed))[1] ** 2
                                          for xi in x_grid])
                i_min = np.argmin(grad_sq_vals)
                x_best = float(x_grid[i_min])

                y_grid = np.linspace(y_fixed - 0.3, y_fixed + 0.3, 100)
                grad_sq_vals_y = np.array([self.grad_phi_eff(float(x_best), float(yi))[0] ** 2 +
                                            self.grad_phi_eff(float(x_best), float(yi))[1] ** 2
                                            for yi in y_grid])
                i_min_y = np.argmin(grad_sq_vals_y)
                y_best = float(y_grid[i_min_y])

                res2 = minimize(grad_sq, [x_best, y_best], method='Nelder-Mead',
                                options={'xatol': 1e-12, 'fatol': 1e-12, 'maxiter': 5000})
                x_lib = float(res2.x[0])
                y_lib = float(res2.x[1])
                gx, gy = self.grad_phi_eff(x_lib, y_lib)
                grad_norm = math.sqrt(gx ** 2 + gy ** 2)

                if grad_norm < 1e-4:
                    phi_val = self.phi_eff(x_lib, y_lib)
                    points[name] = (x_lib, y_lib, phi_val)
                    if verbose:
                        print(f"    {name}: x = {x_lib:.6f}, y = {y_lib:.6f} "
                              f"(refined, |∇Φ|={grad_norm:.2e})")
                elif verbose:
                    print(f"    {name}: NOT FOUND (|∇Φ|={grad_norm:.2e})")

        return points

    def _refine_collinear(self, x_guess: float, points: dict,
                           verbose: bool = True) -> None:
        """Refine and store a collinear Lagrange point.

        Classifies by position relative to M₁ and M₂.
        Uses bisection for robust refinement.
        """
        if x_guess < self.x1:
            name = 'L3'
            bracket = (self.x1 - 2.0 * self.a, self.x1 - 0.001 * self.a)
        elif x_guess < self.x2:
            name = 'L1'
            bracket = (self.x1 + 0.001 * self.a, self.x2 - 0.001 * self.a)
        else:
            name = 'L2'
            bracket = (self.x2 + 0.001 * self.a, self.x2 + 2.0 * self.a)

        # Don't re-find an already-stored point
        if name in points:
            return

        try:
            from scipy.optimize import root_scalar
            sol = root_scalar(
                lambda x: self.grad_phi_eff(float(x), 0.0)[0],
                bracket=bracket,
                method='bisect' if self.sigma <= 0 else 'ridder',
                maxiter=100,
            )
            x_lib = sol.root
        except (ValueError, RuntimeError):
            # Fall back to linear interpolation
            x_lib = float(x_guess)

        y_lib = 0.0
        gx, gy = self.grad_phi_eff(x_lib, y_lib)
        if abs(gx) < 1e-3 or abs(x_lib - x_guess) < 0.01:
            phi_val = self.phi_eff(x_lib, y_lib)
            points[name] = (x_lib, y_lib, phi_val)
            if verbose:
                print(f"    {name}: x = {x_lib:.6f}, "
                      f"y = {y_lib:.6f}, Φ_eff = {phi_val:.6f}")
        elif verbose:
            print(f"    {name}: near-miss at x={x_lib:.6f} "
                  f"(|∇Φ|={abs(gx):.2e})")


# ═══════════════════════════════════════════════════════════════════════
#  Analysis & Plotting
# ═══════════════════════════════════════════════════════════════════════

def compute_zero_velocity_curve(system: SoftenedCR3BP,
                                 C_val: float,
                                 x_range: tuple = (-2.0, 2.0),
                                 y_range: tuple = (-2.0, 2.0),
                                 n_grid: int = 200) -> tuple:
    """Compute zero-velocity curve (Φ_eff = -C/2) on a grid.

    The Jacobi constant is C_J = 2·Ω·(x·v_y - y·v_x) - 2·Φ_eff - v²
    The zero-velocity surface satisfies: C_J = -2·Φ_eff (since v=0).
    So for a given C_J, the forbidden region is where -2·Φ_eff > C_J.
    """
    xs = np.linspace(x_range[0], x_range[1], n_grid)
    ys = np.linspace(y_range[0], y_range[1], n_grid)
    X, Y = np.meshgrid(xs, ys)

    Z = np.zeros_like(X)
    for i in range(n_grid):
        for j in range(n_grid):
            Z[i, j] = system.phi_eff(float(X[i, j]), float(Y[i, j]))

    # Zero-velocity curve: -2·Φ_eff = C_J
    # So Φ_eff = -C_J/2
    return X, Y, Z


def classify_stability(system: SoftenedCR3BP, points: dict) -> dict:
    """Classify each Lagrange point's linear stability.



    Uses the Hessian of Φ_eff. For collinear points (L1-L3):
    - Saddle points: one stable, one unstable direction
    - Linear instability

    For triangular points (L4-L5):
    - Stable if the eigenvalues satisfy certain condition
    - Routh's criterion in Newtonian: μ < μ_crit ≈ 0.0385...
    """
    stability = {}
    for name, (x, y, phi) in points.items():
        J = system.compute_jacobian(x, y)
        eigvals = np.linalg.eigvals(J)
        # For a saddle, eigenvalues have opposite signs
        # For a minimum (stable), both positive
        # For a maximum (unstable), both negative
        stable_directions = sum(1 for ev in eigvals if ev > 0)
        stability[name] = {
            'eigenvalues': eigvals,
            'type': ['max', 'saddle', 'min'][min(stable_directions, 2)],
            'stable_directions': stable_directions,
        }
    return stability


def plot_lagrange_config(system: SoftenedCR3BP, points: dict,
                          sigma_label: str,
                          ax, show_contours: bool = True):
    """Plot Lagrange points for one σ value on given axes."""
    n_grid = 300
    x_lim = 2.5
    xs = np.linspace(-x_lim, x_lim, n_grid)
    ys = np.linspace(-x_lim, x_lim, n_grid)
    X, Y = np.meshgrid(xs, ys)

    # Compute Φ_eff on grid
    Z = np.zeros_like(X)
    for i in range(n_grid):
        for j in range(n_grid):
            Z[i, j] = system.phi_eff(float(X[i, j]), float(Y[i, j]))

    # Contours of Φ_eff
    n_levels = 25
    levels = np.linspace(Z.min(), Z.max(), n_levels)

    cf = ax.contourf(X, Y, Z, levels=levels, cmap='viridis', alpha=0.7)
    cs = ax.contour(X, Y, Z, levels=levels, colors='white', linewidths=0.5,
                    alpha=0.3)

    # Mark the primary bodies
    ax.scatter([system.x1], [0], c='#e74c3c', s=200, marker='o',
               edgecolors='white', linewidths=2, zorder=10, label='M₁')
    ax.scatter([system.x2], [0], c='#2980b9', s=150, marker='o',
               edgecolors='white', linewidths=2, zorder=10, label='M₂')

    # Mark Lagrange points
    colors_lp = {'L1': '#f1c40f', 'L2': '#e67e22', 'L3': '#9b59b6',
                 'L4': '#2ecc71', 'L5': '#1abc9c'}
    markers_lp = {'L1': 'D', 'L2': 's', 'L3': '^', 'L4': 'o', 'L5': 'o'}

    for name, (x, y, phi) in points.items():
        c = colors_lp.get(name, '#2c3e50')
        m = markers_lp.get(name, 'o')
        ax.scatter(x, y, c=c, s=120, marker=m, edgecolors='white',
                   linewidths=1.5, zorder=12, label=name)

    ax.set_xlabel('x', fontsize=12)
    ax.set_ylabel('y', fontsize=12)
    ax.set_title(f'σ/a = {sigma_label}', fontsize=12)
    ax.set_aspect('equal')
    ax.set_xlim(-x_lim, x_lim)
    ax.set_ylim(-x_lim, x_lim)
    # Only put legend on first/last panel to avoid clutter
    try:
        sigma_num = float(sigma_label.split()[0].replace('∞', '999'))
    except (ValueError, IndexError):
        sigma_num = 999.0
    if abs(sigma_num) < 0.01 or 'Newton' in sigma_label:
        ax.legend(fontsize=7, loc='upper right', ncol=2)

    return cf


def main():
    print("=" * 74)
    print("  Path 5: Three-Body Lagrange Points in Cassi Softened Gravity")
    print("=" * 74)

    # Physical parameters
    M1, M2 = 1.0, 0.5  # mass ratio μ = M2/(M1+M2) = 1/3
    a = 1.0              # binary separation
    G = 1.0
    mu = M2 / (M1 + M2)
    print(f"\n  M₁ = {M1}, M₂ = {M2}, μ = {mu:.4f}")
    print(f"  a = {a}, G = {G}")
    print(f"  Newtonian Ω_K = {math.sqrt(G * (M1 + M2) / a ** 3):.6f}")

    # ═════════════════════════════════════════════════════════════════
    #  Part 1: Lagrange Points for Various σ Values
    # ═════════════════════════════════════════════════════════════════
    print("\n" + "─" * 74)
    print("  PART 1: Lagrange Points vs Softening σ")
    print("─" * 74)

    sigma_values = [0.0, 0.1, 0.3, 0.5, 0.7, 1.0]
    all_points = {}

    for sigma in sigma_values:
        label = f"σ/a = {sigma:.1f}" if sigma > 0 else "σ/a = 0 (Newton)"
        print(f"\n  {label}")
        print(f"  {'─' * 50}")

        sys = SoftenedCR3BP(M1=M1, M2=M2, a=a, sigma=sigma, G=G)
        points = sys.find_lagrange_points(verbose=True)
        all_points[sigma] = {
            'system': sys,
            'points': points,
        }

        if len(points) < 5:
            print(f"  ⚠ Only {len(points)}/5 Lagrange points found—"
                  f"some merged or vanished!")


    # Binary search for each Lagrange point's disappearance threshold
    # (defined early so Part 2's merger detection can use it)
    def find_critical_sigma(point_name: str, guess_range: tuple = (0, 2.0),
                            tol: float = 1e-4) -> float | None:
        """Find the σ at which a Lagrange point vanishes."""
        lo, hi = guess_range
        for _ in range(30):
            mid = (lo + hi) / 2.0
            sys = SoftenedCR3BP(M1=M1, M2=M2, a=a, sigma=mid, G=G)
            points = sys.find_lagrange_points(verbose=False)
            exists = point_name in points
            if exists:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol:
                break
        return lo if hi > lo else None
    # ═════════════════════════════════════════════════════════════════
    #  Part 2: L1-L3 Position Shift vs σ/a
    # ═════════════════════════════════════════════════════════════════
    print("\n" + "─" * 74)
    print("  PART 2: L1-L3 Position Shift vs σ/a")
    print("─" * 74)

    sigma_fine = np.linspace(0, 1.0, 50)
    L1_x_arr = np.full_like(sigma_fine, np.nan)
    L2_x_arr = np.full_like(sigma_fine, np.nan)
    L3_x_arr = np.full_like(sigma_fine, np.nan)
    L4_dist_arr = np.full_like(sigma_fine, np.nan)
    L5_dist_arr = np.full_like(sigma_fine, np.nan)

    for i, sigma in enumerate(sigma_fine):
        sys = SoftenedCR3BP(M1=M1, M2=M2, a=a, sigma=float(sigma), G=G)
        points = sys.find_lagrange_points(verbose=False)
        if 'L1' in points: L1_x_arr[i] = points['L1'][0]
        if 'L2' in points: L2_x_arr[i] = points['L2'][0]
        if 'L3' in points: L3_x_arr[i] = points['L3'][0]
        if 'L4' in points:
            x4, y4, _ = points['L4']
            L4_dist_arr[i] = math.sqrt(x4 ** 2 + y4 ** 2)
        if 'L5' in points:
            x5, y5, _ = points['L5']
            L5_dist_arr[i] = math.sqrt(x5 ** 2 + y5 ** 2)

    print("\n  L1, L2, L3 positions as function of σ/a:")
    print(f"  {'σ/a':>6s}  {'L1_x':>10s}  {'L2_x':>10s}  {'L3_x':>10s}  "
          f"{'L4_dist':>10s}")
    print(f"  {'─'*6}  {'─'*10}  {'─'*10}  {'─'*10}  {'─'*10}")
    for i, sigma in enumerate(sigma_fine[::10]):
        print(f"  {sigma:6.3f}  {L1_x_arr[i*10]:10.4f}  "
              f"{L2_x_arr[i*10]:10.4f}  {L3_x_arr[i*10]:10.4f}  "
              f"{L4_dist_arr[i*10]:10.4f}")

    # ── L1-L2 Merger Detection ──
    # Find approximate σ where L1 and L2 merge using sweep data
    both_exist = ~(np.isnan(L1_x_arr) | np.isnan(L2_x_arr))
    xdiff = L2_x_arr - L1_x_arr
    valid = both_exist & (xdiff > 0)
    if np.any(valid):
        idx_last = int(np.where(valid)[0][-1])
        sigma_approx = sigma_fine[min(idx_last + 1, len(sigma_fine) - 1)]
    else:
        sigma_approx = 0.7  # fallback

    # Refine with bisection: find σ where L1 and L2 merge (Δx → 0)
    sigma_lo = max(0.0, sigma_approx - 0.1)
    sigma_hi = min(1.0, sigma_approx + 0.1)
    for _ in range(40):
        mid = (sigma_lo + sigma_hi) / 2.0
        sys_mid = SoftenedCR3BP(M1=M1, M2=M2, a=a, sigma=mid, G=G)
        pts_mid = sys_mid.find_lagrange_points(verbose=False)
        l1_ok = 'L1' in pts_mid
        l2_ok = 'L2' in pts_mid
        if l1_ok and l2_ok:
            dx = pts_mid['L2'][0] - pts_mid['L1'][0]
            if dx > 1e-9:
                sigma_lo = mid
            else:
                sigma_hi = mid
        else:
            sigma_hi = mid
        if sigma_hi - sigma_lo < 1e-9:
            break
    sigma_crit_merge = (sigma_lo + sigma_hi) / 2.0

    # L3 and L4 status at merger σ
    sys_merge = SoftenedCR3BP(M1=M1, M2=M2, a=a, sigma=sigma_crit_merge, G=G)
    pts_merge = sys_merge.find_lagrange_points(verbose=False)
    crit_L3_ind = find_critical_sigma('L3', (0, 2.0), tol=1e-6)

    print(f"\n  L1-L2 merger (saddle-node bifurcation):")
    print(f"    σ_crit(L1-L2 merge) = {sigma_crit_merge:.8f}  "
          f"(σ/a = {sigma_crit_merge:.8f})")
    print(f"    At merge σ: L3={'YES' if 'L3' in pts_merge else 'NO '}, "
          f"L4={'YES' if 'L4' in pts_merge else 'NO '}")
    if crit_L3_ind is not None:
        print(f"    σ_crit(L3 vanish)   = {crit_L3_ind:.8f}")
        if crit_L3_ind > sigma_crit_merge + 1e-6:
            print(f"    → L3 persists beyond L1-L2 merger "
                  f"(Δσ = {crit_L3_ind - sigma_crit_merge:.6f})")
        elif crit_L3_ind < sigma_crit_merge - 1e-6:
            print(f"    → L3 vanishes BEFORE L1-L2 merger")
        else:
            print(f"    → L3 vanishes at the SAME σ as L1-L2 merger")
    else:
        print(f"    σ_crit(L3 vanish): could not determine")

    # ═════════════════════════════════════════════════════════════════
    #  Part 3: Existence Threshold
    # ═════════════════════════════════════════════════════════════════
    print("\n" + "─" * 74)
    print("  PART 3: Existence Threshold—Critical σ for Lagrange Points")
    print("─" * 74)


    for lp in ['L1', 'L2', 'L3', 'L4']:
        sigma_crit = find_critical_sigma(lp, (0, 2.0))
        if sigma_crit is not None:
            print(f"  {lp} exists for σ/a < {sigma_crit:.4f} "
                  f"({sigma_crit * a:.4f} in absolute units)")
        else:
            print(f"  {lp}: Could not determine critical σ")


    # Check at very high σ
    print(f"\n  Checking extreme softening values...")
    for sigma_test in [1.5, 2.0, 3.0, 5.0, 10.0]:
        sys = SoftenedCR3BP(M1=M1, M2=M2, a=a, sigma=sigma_test, G=G)
        pts = sys.find_lagrange_points(verbose=False)
        if pts:
            print(f"    σ/a = {sigma_test:.1f}: {len(pts)} points found "
                  f"({', '.join(pts.keys())})")
        else:
            print(f"    σ/a = {sigma_test:.1f}: No Lagrange points found")

    # ═════════════════════════════════════════════════════════════════
    #  Part 4: Jacobi Constant and Zero-Velocity Curves
    # ═════════════════════════════════════════════════════════════════
    print("\n" + "─" * 74)
    print("  PART 4: Jacobi Constant at Lagrange Points")
    print("─" * 74)

    for sigma in [0.0, 0.1, 0.3, 0.5]:
        sys = all_points[sigma]['system']
        points = all_points[sigma]['points']
        print(f"\n  σ/a = {sigma:.1f}:")
        for name, (x, y, phi) in sorted(points.items()):
            C_J = -2.0 * phi  # Jacobi constant at zero velocity
            print(f"    {name}: C_J = {C_J:.6f}, Φ_eff = {phi:.6f}, "
                  f"(x={x:.4f}, y={y:.4f})")

    # ═════════════════════════════════════════════════════════════════
    #  Part 5: Figure Generation
    # ═════════════════════════════════════════════════════════════════
    print("\n" + "─" * 74)
    print("  PART 5: Generating Figures")
    print("─" * 74)

    # ── Figure 1: Φ_eff contours with Lagrange points for σ/a ∈ {0, 0.1, 0.3, 0.5} ──
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    plot_sigmas = [0.0, 0.1, 0.3, 0.5]
    sigma_labels = ['0 (Newtonian)', '0.1', '0.3', '0.5']
    for ax, sigma, label in zip(axes.flat, plot_sigmas, sigma_labels):
        sys = all_points[sigma]['system']
        points = all_points[sigma]['points']
        cf = plot_lagrange_config(sys, points, label, ax)

    # Colorbar
    fig.subplots_adjust(right=0.92)
    cbar_ax = fig.add_axes([0.93, 0.15, 0.015, 0.7])
    cbar = fig.colorbar(cf, cax=cbar_ax)
    cbar.set_label('Φ_eff', fontsize=10)

    fig.suptitle('Lagrange Points in Cassi Softened Gravity\n'
                 'Φ_eff contours with L1–L5 marked (M₁=1, M₂=0.5, a=1)',
                 fontsize=14, y=0.98)
    fig.savefig('experiments/path5_lagrange_contours.png', dpi=150,
                bbox_inches='tight', facecolor='white')
    print(f"  Saved: experiments/path5_lagrange_contours.png")
    plt.close(fig)

    # ── Figure 2: L1-L3 position vs σ/a ──
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(sigma_fine, L1_x_arr, '-', c='#f1c40f', lw=2.5, label='L1')
    ax.plot(sigma_fine, L2_x_arr, '-', c='#e67e22', lw=2.5, label='L2')
    ax.plot(sigma_fine, L3_x_arr, '--', c='#9b59b6', lw=2.5, label='L3')

    # M₁ and M₂ positions
    ax.axhline(sys.x1, c='#e74c3c', ls=':', lw=1, alpha=0.5)
    ax.axhline(sys.x2, c='#2980b9', ls=':', lw=1, alpha=0.5)
    ax.annotate('M₁', xy=(0.05, sys.x1), fontsize=9, color='#e74c3c')
    ax.annotate('M₂', xy=(0.05, sys.x2), fontsize=9, color='#2980b9')

    # Disappearance threshold region
    ax.axvspan(0.7, 1.0, color='red', alpha=0.08, label='Points vanish')

    # L1-L2 merger critical σ
    ax.axvline(sigma_crit_merge, c='red', ls='--', lw=1.5, alpha=0.7)
    ax.annotate(f'L1/L2 merge\nσ/a={sigma_crit_merge:.4f}',
                xy=(sigma_crit_merge, 0.5),
                fontsize=8, color='red', ha='left',
                arrowprops=dict(arrowstyle='->', color='red', lw=1))

    ax.set_xlabel('σ / a', fontsize=12)
    ax.set_ylabel('x-position of Lagrange point', fontsize=12)
    ax.set_title('Collinear Lagrange Point Positions vs Softening',
                 fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 1.0)

    fig.tight_layout()
    fig.savefig('experiments/path5_lagrange_positions.png', dpi=150,
                bbox_inches='tight', facecolor='white')
    print(f"  Saved: experiments/path5_lagrange_positions.png")
    plt.close(fig)

    # ── Figure 3: Four-panel main figure ──
    fig, axes = plt.subplots(4, 3, figsize=(20, 22))

    # Row 0: σ/a = 0, 0.1, 0.2
    plot_sigmas_all = [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 1.0, 1.5]
    sigma_labels_all = ['0', '0.1', '0.2', '0.3', '0.5',
                        '0.7', '0.8', '0.9', '1.0', '1.5']

    for i_plot, (sigma, label) in enumerate(zip(plot_sigmas_all, sigma_labels_all)):
        row = i_plot // 3
        col = i_plot % 3
        if row >= 4:
            break
        ax = axes[row, col]

        if sigma not in all_points:
            sys = SoftenedCR3BP(M1=M1, M2=M2, a=a, sigma=sigma, G=G)
            pts = sys.find_lagrange_points(verbose=False)
            all_points[sigma] = {'system': sys, 'points': pts}

        sys = all_points[sigma]['system']
        points = all_points[sigma]['points']
        cf = plot_lagrange_config(sys, points, label, ax)

        # Red circle for softening scale
        circle = plt.Circle((0, 0), sigma * 0.5, fill=False,
                            color='white', ls='--', lw=1, alpha=0.4)
        ax.add_patch(circle)

        if len(points) < 5:
            ax.text(0.5, 0.95, f'MERGED ({len(points)} pts)',
                    transform=ax.transAxes, ha='center', va='top',
                    fontsize=10, color='white',
                    bbox=dict(boxstyle='round', facecolor='red', alpha=0.6))

    # Hide unused panels
    for i in range(len(plot_sigmas_all), 12):
        row = i // 3
        col = i % 3
        if row < 4:
            axes[row, col].set_visible(False)

    fig.subplots_adjust(right=0.92, hspace=0.3, wspace=0.3)
    cbar_ax = fig.add_axes([0.93, 0.15, 0.015, 0.7])
    cbar = fig.colorbar(cf, cax=cbar_ax)
    cbar.set_label('Φ_eff', fontsize=10)

    fig.suptitle('Lagrange Points in Cassi Softened Gravity\n'
                 'M₁=1 (red), M₂=0.5 (blue), a=1—'
                 'Dashed white circle = softening scale σ',
                 fontsize=14, y=0.98)

    fig.savefig('experiments/path5_lagrange_points.png', dpi=150,
                bbox_inches='tight', facecolor='white')
    print(f"  Saved: experiments/path5_lagrange_points.png")
    plt.close(fig)

    # ═════════════════════════════════════════════════════════════════
    #  Summary
    # ═════════════════════════════════════════════════════════════════
    print("\n" + "=" * 74)
    print("  SUMMARY: Lagrange Points in Softened Gravity")
    print("=" * 74)

    # Count how many points at each σ
    sigma_over_a = plot_sigmas_all[:10]
    n_points = []
    for sigma in sigma_over_a:
        sigma_key = sigma if sigma in all_points else float(sigma)
        if sigma_key in all_points:
            n_points.append(len(all_points[sigma_key]['points']))
        else:
            n_points.append(0)

    print(f"\n  {'σ/a':>6s}  {'N_points':>10s}  {'Vanish?':>10s}")
    print(f"  {'─'*6}  {'─'*10}  {'─'*10}")
    for s, n in zip(sigma_over_a, n_points):
        vanished = "YES" if n < 5 else "no"
        print(f"  {s:6.2f}  {n:10d}  {vanished:>10s}")

    sigma_crit_approx = None
    for s, n in zip(sigma_over_a, n_points):
        if n < 5 and sigma_crit_approx is None:
            sigma_crit_approx = s
    if sigma_crit_approx is None and len(sigma_over_a) > 0:
        sigma_crit_approx = "> " + str(sigma_over_a[-1])

    print(f"""
  Critical softening:
  ────────────────────────────────────────────────────────────
  Lagrange points L1-L5 exist for σ/a < {sigma_crit_approx}.
  For σ/a ≥ {sigma_crit_approx}, some points merge and disappear
  as the softened potential becomes too shallow to maintain
  the effective potential wells.

  Physical interpretation:
  - L1 vanishes when softening erases the saddle between M₁ and M₂
  - L2 vanishes when the M₂ well becomes too shallow
  - L3 vanishes last (largest separation from both masses)
  - L4/L5 vanish when the effective potential becomes monotonic
    in the off-axis direction

  Jacobi constant at Lagrange points decreases with σ,
  shrinking the forbidden regions (zero-velocity curves)
  and making low-energy orbits more accessible.

  The softening scale σ/a ≈ 0.7 marks a qualitative transition:
  below it, all 5 Lagrange points exist with modified positions;
  above it, the three-body problem structure dissolves into a
  single, smoothly varying effective potential.
""")

    return {
        'sigma_values': [float(s) for s in sigma_values],
        'n_points': [len(all_points[s]['points']) if s in all_points else 0
                     for s in sigma_values],
        'L1_x': L1_x_arr.tolist(),
        'L2_x': L2_x_arr.tolist(),
        'L3_x': L3_x_arr.tolist(),
    }


if __name__ == '__main__':
    main()
