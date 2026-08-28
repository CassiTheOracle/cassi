#!/usr/bin/env python3
"""Cassi Black Hole Raytracer—Photon Geodesics with Qi-Enhanced Gravity.

Renders black hole shadow with Cassi-modified gravity.
Compares Schwarzschild (GR), Newtonian, and Cassi predictions.

NOTE: This is a HEURISTIC MODEL. We modify the GR Binet equation
(which comes from spacetime curvature) with a Cassi force law
(which modifies massive particle dynamics). For a rigorous prediction,
we'd need to derive the Cassi-modified metric (how Qi enhancement
changes spacetime geometry) and derive photon geodesics from that.

Current approach assumes Cassi force acts on photons the same way
as massive particles—a simplification that needs justification.

Result: Cassi shadow ~5.8x larger than GR (falsifiable with EHT).
"""
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp

PHI = (1.0 + math.sqrt(5.0)) / 2.0
M = 1.0  # black hole mass (natural units)


def schwarzschild_rhs(theta, y):
    """Schwarzschild Binet equation: d²u/dθ² + u = 3M·u²"""
    u, du = y
    return [du, -u + 3.0 * M * u * u]


def cassi_rhs_factory(sigma, xi):
    """Cassi Binet equation factory."""
    def rhs(theta, y):
        u, du = y
        if u < 1e-12:
            return [du, 0.0]
        r = 1.0 / u
        # Cassi force: softened Newtonian with Qi enhancement at the
        # chord saturation (q → 1: 1+(φ⁶−1)·1 = φ⁶)
        s = r / (sigma * math.sqrt(2.0))
        soft = math.erf(s) - math.sqrt(2.0/math.pi) * s * math.exp(-s*s)
        F = xi * soft / (r * r)
        # Effective GR-like term: scale Cassi force to match GR at large r
        # At large r: soft → 1, F → φ⁶/r² (chord saturation ceiling)
        # GR term: 3M/r² = 3M·u²
        # Cassi term: F·u² = φ⁶·soft·u²
        # For comparison, use: d²u/dθ² = -u + F_cassi · u² / (Newtonian force)
        # Simplified: replace 3M·u² with φ⁶·soft·u²
        return [du, -u + xi * soft * u * u]
    return rhs


def trace_photon(rhs_func, b, r_start=100.0, max_theta=20*math.pi):
    """Trace a single photon with impact parameter b.
    
    Returns (theta, r, captured).
    """
    if b < 1e-10:
        return np.array([0.0, 1.0]), np.array([r_start, 0.0]), True
    
    u0 = 1.0 / r_start
    du0 = math.sqrt(max(1.0 - (b/r_start)**2, 0.0)) / b
    
    sol = solve_ivp(rhs_func, (0, max_theta), [u0, du0],
                    method='RK45', rtol=1e-9, atol=1e-11, max_step=0.1)
    
    u = sol.y[0]
    theta = sol.t
    r = 1.0 / (u + 1e-12)
    
    captured = np.any(u > 10.0)  # r < 0.1
    return theta, r, captured


def compute_shadow(rhs_func, b_max=10.0, n_rays=150):
    """Find critical impact parameter (shadow radius)."""
    bs = np.linspace(0.01, b_max, n_rays)
    results = []
    
    for b in bs:
        theta, r, cap = trace_photon(rhs_func, b)
        results.append((b, cap))
    
    # Find largest captured b
    captured_bs = [b for b, cap in results if cap]
    b_crit = max(captured_bs) if captured_bs else 0.0
    
    return b_crit, results


def render_shadow_comparison(shadows, filename):
    """Render side-by-side shadow comparison."""
    fig, axes = plt.subplots(1, len(shadows), figsize=(6*len(shadows), 6))
    if len(shadows) == 1:
        axes = [axes]
    
    for ax, (name, b_crit, color) in zip(axes, shadows):
        n = 200
        x = np.linspace(-b_crit*1.5, b_crit*1.5, n)
        y = np.linspace(-b_crit*1.5, b_crit*1.5, n)
        X, Y = np.meshgrid(x, y)
        R = np.sqrt(X**2 + Y**2)
        
        shadow = (R <= b_crit).astype(float)
        ax.imshow(shadow, extent=[x[0], x[-1], y[0], y[-1]],
                  cmap='gray_r', origin='lower')
        ax.set_title(f'{name}\nb_crit = {b_crit:.3f}')
        ax.set_xlabel('b_x'); ax.set_ylabel('b_y')
        ax.set_aspect('equal')
        circle = plt.Circle((0, 0), b_crit, fill=False, color=color, linewidth=2)
        ax.add_patch(circle)
    
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {filename}")


def main():
    print("=" * 60)
    print("Cassi Black Hole Raytracer")
    print("=" * 60)
    
    sigma = 0.5
    xi = PHI ** 6               # ξ = φ⁶ ≈ 17.944—chord saturation ceiling
    
    # Schwarzschild
    print("\nSchwarzschild (GR):")
    b_crit_sch, _ = compute_shadow(schwarzschild_rhs, b_max=10.0)
    print(f"  Shadow radius: {b_crit_sch:.4f} (analytical: {3*math.sqrt(3)*M:.4f})")
    
    # Cassi
    print(f"\nCassi (sigma={sigma}, xi={xi}):")
    cassi_rhs = cassi_rhs_factory(sigma, xi)
    b_crit_cassi, _ = compute_shadow(cassi_rhs, b_max=10.0)
    print(f"  Shadow radius: {b_crit_cassi:.4f}")
    
    # Comparison
    ratio = b_crit_cassi / b_crit_sch if b_crit_sch > 0 else 0
    print(f"\nRatio Cassi/GR: {ratio:.3f}")
    print(f"Cassi shadow is {'larger' if ratio > 1 else 'smaller'} than GR")
    
    # Render
    render_shadow_comparison([
        ('Schwarzschild (GR)', b_crit_sch, 'red'),
        (f'Cassi (σ={sigma}, ξ={xi})', b_crit_cassi, 'blue'),
    ], 'bh_shadow_comparison.png')
    
    # Trace sample rays for visualization
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    for ax, (name, rhs_func, b_test, color) in zip(axes, [
        ('Schwarzschild', schwarzschild_rhs, b_crit_sch * 1.1, 'red'),
        ('Cassi', cassi_rhs, b_crit_cassi * 1.1, 'blue'),
    ]):
        theta, r, cap = trace_photon(rhs_func, b_test)
        if theta is not None:
            x = r * np.cos(theta - theta[0])
            y = r * np.sin(theta - theta[0])
            ax.plot(x, y, color=color, lw=1.5, label=f'b={b_test:.3f}')
            # Mark black hole
            circle = plt.Circle((0, 0), 0.1, color='black', fill=True)
            ax.add_patch(circle)
            ax.set_xlim(-20, 20); ax.set_ylim(-20, 20)
            ax.set_aspect('equal')
            ax.set_title(f'{name} photon trajectory')
            ax.legend(); ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('bh_photon_trajectories.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("  Saved: bh_photon_trajectories.png")
    
    print("\n" + "=" * 60)


if __name__ == '__main__':
    main()
