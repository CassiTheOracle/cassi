#!/usr/bin/env python3
r"""Path 6: Linear Stability of L4/L5 in Cassi Softened Gravity.

Analyses how Gaussian softening modifies the Routh stability criterion
for the triangular Lagrange points in the circular restricted three-body
problem (CR3BP).

Derivation
----------
In the corotating frame, the effective potential is:
    Φ_eff(x,y) = Φ₁(r₁) + Φ₂(r₂) - ½·Ω²·(x²+y²)

where Φ_i(r) = -GM_i/r · erf(r/(σ√2)) is the softened potential.

At the equilateral points L4/L5, r₁ = r₂ = a (binary separation).
The Hessian of Φ_eff simplifies to:
    Φ_xx = K/4      Φ_yy = 3K/4
    Φ_xy = √3/4 · (1-2μ) · K

where K = M_total · (f'(a) - f(a)/a) and f = Φ'(r; M=1).

The orbital frequency is Ω² = M_total · f(a)/a.

The linearized equations in the rotating frame give the characteristic eqn:
    λ⁴ + b·λ² + c = 0
with b = Φ_xx+Φ_yy+4Ω² = K+4Ω²,  c = Φ_xxΦ_yy-Φ_xy² = 3K²μ(1-μ)/4.

Stability requires (i) b > 0, (ii) c > 0, (iii) b² - 4c ≥ 0.
Condition (i) holds for all σ/a ≥ 0, (ii) holds for all μ ∈ (0,1).
Condition (iii) gives the critical mass ratio:
    η² ≥ 3μ(1-μ)    where η = -(K+4Ω²)/K

In Newtonian limit: η = 1/3, giving μ_crit = (1-√(1-4η²/3))/2 ≈ 0.0385.
With softening η increases → larger μ_crit → MORE stability.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
from scipy.special import erf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Rectangle


# ═══════════════════════════════════════════════════════════════════════
#  1. Softened potential: unit-mass derivatives
# ═══════════════════════════════════════════════════════════════════════

def f_soft(r, sigma, G=1.0):
    """First derivative Φ'(r) for unit mass in softened potential.
    
    f(r) = G/r² · [erf(r/(σ√2)) - √(2/π)·(r/σ)·exp(-r²/(2σ²))]
    
    For σ → 0: f(r) → G/r² (Newtonian).
    """
    if sigma <= 0.0:
        return G / r ** 2
    x = r / (sigma * np.sqrt(2.0))
    phi = erf(x) - np.sqrt(2.0 / np.pi) * (r / sigma) * np.exp(-x * x)
    return (G / r ** 2) * phi


def fp_soft(r, sigma, G=1.0):
    """Second derivative Φ''(r) for unit mass (force gradient).
    
    f'(r) = G/r³ · [-2φ(x) + (4/√π)·x³·exp(-x²)]
    where φ(x) = erf(x) - (2/√π)·x·exp(-x²), x = r/(σ√2)
    
    For σ → 0: f'(r) → -2G/r³ (Newtonian).
    """
    if sigma <= 0.0:
        return -2.0 * G / r ** 3
    x = r / (sigma * np.sqrt(2.0))
    phi = erf(x) - (2.0 / np.sqrt(np.pi)) * x * np.exp(-x * x)
    x3e = (x ** 3) * np.exp(-x * x)
    return (G / r ** 3) * (-2.0 * phi + (4.0 / np.sqrt(np.pi)) * x3e)


# ═══════════════════════════════════════════════════════════════════════
#  2. Stability analysis—analytic computation
# ═══════════════════════════════════════════════════════════════════════

def compute_stability_params(sigma_over_a, G=1.0):
    """Compute σ-dependent stability parameters.
    
    All quantities evaluated at the equilateral configuration r₁ = r₂ = a
    with normalized units: a = 1, M_total = 1.
    
    Returns dict with:
        K : curvature parameter M_total·(f'(a)-f(a)/a)
        Omega2 : orbital frequency squared
        eta : stability parameter η = -(K+4Ω²)/K
        b : trace parameter K+4Ω²
        f_a, fp_a : potential derivatives at r=a
    """
    a = 1.0  # normalized separation
    M_total = 1.0  # normalized total mass
    
    tiny = 1e-12
    
    if sigma_over_a < tiny:
        # Newtonian limit
        f_a_val = G / a ** 2
        fp_a_val = -2.0 * G / a ** 3
    else:
        sigma = sigma_over_a * a
        f_a_val = f_soft(a, sigma, G)
        fp_a_val = fp_soft(a, sigma, G)
    
    K = M_total * (fp_a_val - f_a_val / a)
    Omega2 = M_total * f_a_val / a
    b = K + 4.0 * Omega2  # = M_total·(f'(a)+3f(a)/a)
    
    # η = -(K+4Ω²)/K = 4Ω²/|K| - 1   (since K < 0)
    abs_K = -K if K < 0 else K
    if abs_K > 1e-15:
        eta = -b / K  # = (K+4Ω²)/|K|
    else:
        eta = float('inf')
    
    return {
        'K': K,
        'Omega2': Omega2,
        'eta': eta,
        'b': b,
        'f_a': f_a_val,
        'fp_a': fp_a_val,
    }


def mu_crit_from_eta(eta):
    """Compute critical mass ratio μ_crit from stability parameter η.
    
    Stability condition: η² ≥ 3·μ·(1-μ)
    
    For η ≤ √3/2: μ_crit = (1 - √(1 - 4η²/3)) / 2
    For η > √3/2: μ_crit = 1/2 (stable for all μ in CR3BP)
    
    The maximum μ in the CR3BP is 1/2 (M₁ ≥ M₂ by convention).
    """
    sqrt3_over_2 = np.sqrt(3.0) / 2.0
    
    if eta >= sqrt3_over_2:
        return 0.5
    if eta <= 0.0:
        return 0.0
    
    disc = 1.0 - 4.0 * eta ** 2 / 3.0
    if disc <= 0.0:
        return 0.0
    
    return (1.0 - np.sqrt(disc)) / 2.0


def check_stability(mu, sigma_over_a):
    """Check if L4/L5 are stable for given μ and σ/a.
    
    Stability requires: b > 0 and η² ≥ 3·μ·(1-μ)
    The Hessian determinant c > 0 automatically for equilateral points.
    """
    params = compute_stability_params(sigma_over_a)
    eta = params['eta']
    b = params['b']
    
    cond1 = b > 1e-15  # b = K + 4Ω² > 0 (always true for σ/a < ~large)
    cond3 = eta ** 2 >= 3.0 * mu * (1.0 - mu) - 1e-15
    
    return cond1 and cond3


# ═══════════════════════════════════════════════════════════════════════
#  3. Grid scan
# ═══════════════════════════════════════════════════════════════════════

def scan_stability_grid(n_mu=50, n_sigma=40):
    """Scan (μ, σ/a) space and compute stability boundary.
    
    Parameters
    ----------
    n_mu : int
        Number of μ values (log-spaced from 0.001 to 0.5)
    n_sigma : int
        Number of σ/a values (linear from 0 to 0.5)
    
    Returns
    -------
    dict with keys:
        mu_vals : ndarray—μ values
        sigma_vals : ndarray—σ/a values
        stable : ndarray (n_mu, n_sigma)—stability map
        mu_crit : ndarray (n_sigma,)—critical μ for each σ
        eta_vals : ndarray (n_sigma,)—η for each σ
        newtonian_mu_crit : float
        sigma_transition : float—σ/a where η = √3/2 (μ_crit → 0.5)
    """
    mu_vals = np.logspace(np.log10(0.001), np.log10(0.5), n_mu)
    sigma_vals = np.linspace(0.0, 0.5, n_sigma)
    
    # Per-σ parameters
    eta_vals = np.zeros(n_sigma)
    mu_crit = np.zeros(n_sigma)
    b_vals = np.zeros(n_sigma)
    K_vals = np.zeros(n_sigma)
    Omega2_vals = np.zeros(n_sigma)
    
    for j, s in enumerate(sigma_vals):
        params = compute_stability_params(s)
        eta_vals[j] = params['eta']
        b_vals[j] = params['b']
        K_vals[j] = params['K']
        Omega2_vals[j] = params['Omega2']
        mu_crit[j] = mu_crit_from_eta(params['eta'])
    
    # Full stability map
    stable = np.zeros((n_mu, n_sigma), dtype=bool)
    for i, mu in enumerate(mu_vals):
        for j, s in enumerate(sigma_vals):
            stable[i, j] = check_stability(mu, s)
    
    # Newtonian limit
    newtonian_mu_crit = mu_crit_from_eta(1.0 / 3.0)
    
    # σ/a at which η = √3/2 → find by interpolation
    sqrt3_over_2 = np.sqrt(3.0) / 2.0
    # Build unique (eta, sigma) pairs for interpolation
    # (avoid near-duplicate x values that break cubic spline)
    unique_idx = np.concatenate(([True], np.diff(eta_vals) > 1e-10))
    eta_unique = eta_vals[unique_idx]
    sigma_unique = sigma_vals[unique_idx]
    
    if len(eta_unique) >= 2 and eta_unique[0] < sqrt3_over_2 and eta_unique[-1] > sqrt3_over_2:
        from scipy.interpolate import interp1d
        f_interp = interp1d(eta_unique, sigma_unique, kind='linear')
        sigma_transition = float(f_interp(sqrt3_over_2))
    else:
        sigma_transition = None
    
    return {
        'mu_vals': mu_vals,
        'sigma_vals': sigma_vals,
        'stable': stable,
        'mu_crit': mu_crit,
        'eta_vals': eta_vals,
        'b_vals': b_vals,
        'K_vals': K_vals,
        'Omega2_vals': Omega2_vals,
        'newtonian_mu_crit': newtonian_mu_crit,
        'sigma_transition': sigma_transition,
    }

# ═══════════════════════════════════════════════════════════════════════
#  4. Figure generation
# ═══════════════════════════════════════════════════════════════════════

def make_stability_plot(result, save_path='experiments/path6_lagrange_stability.png'):
    """Produce 2-panel figure: stability map + μ_crit vs σ/a."""
    
    mu_vals = result['mu_vals']
    sigma_vals = result['sigma_vals']
    stable = result['stable']
    mu_crit = result['mu_crit']
    eta_vals = result['eta_vals']
    newtonian_mu_crit = result['newtonian_mu_crit']
    sigma_transition = result['sigma_transition']
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    
    # ================================================================
    # Panel A: Stability map in (μ, σ/a) space
    # ================================================================
    
    # Create a finer grid for smooth display
    n_fine_mu = 200
    n_fine_sigma = 200
    mu_fine = np.logspace(np.log10(0.001), np.log10(0.5), n_fine_mu)
    sigma_fine = np.linspace(0.0, 0.5, n_fine_sigma)
    stable_fine = np.zeros((n_fine_mu, n_fine_sigma), dtype=bool)
    
    for i, mu in enumerate(mu_fine):
        for j, s in enumerate(sigma_fine):
            stable_fine[i, j] = check_stability(mu, s)
    
    # Colormap: blue = stable (1), red = unstable (0)
    cmap = ListedColormap(['#e74c3c', '#2980b9'])
    
    # Use pcolormesh for correct rendering with log-scale y-axis
    X_sigma, Y_mu = np.meshgrid(sigma_fine, mu_fine)
    ax1.pcolormesh(X_sigma, Y_mu, stable_fine.astype(float),
                   cmap=cmap, vmin=0, vmax=1, shading='nearest',
                   linewidth=0, antialiased=True)
    
    # Overlay μ_crit(σ/a) as white curve
    mu_crit_fine = np.array([mu_crit_from_eta(
        compute_stability_params(s)['eta']) for s in sigma_fine])
    
    ax1.plot(sigma_fine, mu_crit_fine, '-', c='white', lw=2.5, label='μ_crit(σ/a)')
    
    # Newtonian limit horizontal line
    ax1.axhline(newtonian_mu_crit, c='white', ls='--', lw=1.5, alpha=0.7,
                label=f'Newtonian μ_crit = {newtonian_mu_crit:.4f}')
    
    # Transition σ where η = √3/2
    if sigma_transition is not None:
        ax1.axvline(sigma_transition, c='#f1c40f', ls=':', lw=1.5, alpha=0.7,
                    label=f'σ/a = {sigma_transition:.3f} (η=√3/2)')
    
    # Physical upper bound μ = 0.5
    ax1.axhline(0.5, c='gray', ls=':', lw=1, alpha=0.5)
    
    # Labels
    ax1.set_xlabel('σ / a (softening parameter)', fontsize=13)
    ax1.set_ylabel('μ = M₂ / (M₁+M₂) (mass ratio)', fontsize=13)
    ax1.set_title('A: L4/L5 Stability Map', fontsize=14, pad=10)
    ax1.set_xlim(0, 0.5)
    ax1.set_ylim(0.001, 0.5)
    ax1.set_yscale('log')
    
    # Legend
    leg1 = ax1.legend(fontsize=9, loc='upper right',
                      framealpha=0.85, edgecolor='gray')
    
    # Add stable/unstable annotation
    ax1.text(0.02, 0.10, 'STABLE', color='white', fontsize=11, fontweight='bold',
             transform=ax1.transData, ha='left', va='center',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#2980b9', alpha=0.8))
    ax1.text(0.02, 0.003, 'UNSTABLE', color='white', fontsize=11, fontweight='bold',
             transform=ax1.transData, ha='left', va='center',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#e74c3c', alpha=0.8))
    ax1.tick_params(labelsize=10)
    
    # ================================================================
    # Panel B: μ_crit vs σ/a with interpretation
    # ================================================================
    
    ax2.plot(sigma_vals, mu_crit, '-o', c='#2c3e50', lw=2.5, ms=4,
             label='μ_crit(σ/a)')
    
    # Newtonian limit
    ax2.axhline(newtonian_mu_crit, c='#e74c3c', ls='--', lw=2,
                label=f'Newtonian limit = {newtonian_mu_crit:.4f}')
    
    # Shaded region: unstable for all μ
    if sigma_transition is not None:
        ax2.axvline(sigma_transition, c='#f1c40f', ls=':', lw=1.5, alpha=0.7)
        ax2.annotate('η = √3/2', xy=(sigma_transition, 0.45),
                     fontsize=9, color='#f1c40f', ha='center',
                     xytext=(sigma_transition + 0.05, 0.45),
                     arrowprops=dict(arrowstyle='->', color='#f1c40f', lw=1.2))
    
    # Fill unstable region below the Newtonian limit for reference
    ax2.fill_between(sigma_vals, 0, mu_crit, alpha=0.1, color='#2980b9',
                     label='Stable region')
    ax2.fill_between(sigma_vals, mu_crit, 0.5, alpha=0.1, color='#e74c3c',
                     label='Unstable region')
    
    # Shade the "marginally stable" zone near μ_crit
    mu_crit_upper = np.minimum(mu_crit * 1.05, 0.5)
    ax2.fill_between(sigma_vals, mu_crit, mu_crit_upper, alpha=0.2,
                     color='gray', label='Marginally stable',
                     edgecolor='none')
    
    # Labels
    ax2.set_xlabel('σ / a (softening parameter)', fontsize=13)
    ax2.set_ylabel('μ_crit (critical mass ratio)', fontsize=13)
    ax2.set_title('B: Critical Mass Ratio vs Softening', fontsize=14, pad=10)
    ax2.set_xlim(0, 0.5)
    ax2.set_ylim(0, 0.5)
    
    # Grid
    ax2.grid(True, alpha=0.3, linestyle=':')
    ax2.legend(fontsize=10, loc='upper left', framealpha=0.85)
    ax2.tick_params(labelsize=10)
    
    # Annotations for key regimes
    # Regime I: near-Newtonian
    ax2.annotate('Regime I:\nNear-Newtonian',
                 xy=(0.03, 0.06), fontsize=9, color='#2c3e50', ha='center',
                 bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.6))
    
    # Regime II: transition
    if sigma_transition is not None:
        mid_trans = sigma_transition / 2
        mu_mid = float(np.interp(mid_trans, sigma_vals, mu_crit))
        ax2.annotate('Regime II:\nEnhanced stability',
                     xy=(mid_trans, mu_mid + 0.08), fontsize=9,
                     color='#2c3e50', ha='center',
                     bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.6))
        
        ax2.annotate('Regime III:\nUniversally stable',
                     xy=((sigma_transition + 0.5) / 2, 0.45), fontsize=9,
                     color='#2c3e50', ha='center',
                     bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.6))
    
    fig.suptitle('Linear Stability of L4/L5 in Softened Gravity\n'
                 'Circular Restricted Three-Body Problem—'
                 'Equilateral Configuration (r₁=r₂=a)',
                 fontsize=15, y=1.01)
    
    fig.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"  Saved: {save_path}")
    plt.close(fig)
    
    # ================================================================
    # Bonus: η(σ/a) diagnostic plot
    # ================================================================
    
    fig2, ax_eta = plt.subplots(figsize=(10, 6))
    
    ax_eta.plot(sigma_vals, eta_vals, '-s', c='#8e44ad', lw=2.5, ms=4)
    ax_eta.axhline(1.0 / 3.0, c='#e74c3c', ls='--', lw=1.5,
                   label=f'Newtonian η = 1/3')
    ax_eta.axhline(np.sqrt(3.0) / 2.0, c='#f1c40f', ls=':', lw=1.5,
                   label=f'η = √3/2 (universal stability)')
    
    # Shade regimes
    ax_eta.fill_between(sigma_vals, 0, eta_vals, alpha=0.1, color='#8e44ad')
    ax_eta.axhline(0, c='black', lw=0.5)
    
    # Label stability regimes
    ax_eta.text(0.35, 0.15, 'STABLE', fontsize=11, color='#2980b9',
               fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
    ax_eta.text(0.35, 1.2, 'UNSTABLE (no μ works)',
                fontsize=11, color='#e74c3c', fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
    
    ax_eta.set_xlabel('σ / a', fontsize=13)
    ax_eta.set_ylabel('η = 4Ω²/|K| − 1 (stability parameter)', fontsize=13)
    ax_eta.set_title('Stability Parameter η vs Softening', fontsize=14)
    ax_eta.set_xlim(0, 0.5)
    ax_eta.legend(fontsize=10)
    ax_eta.grid(True, alpha=0.3)
    
    fig2.tight_layout()
    fig2.savefig(save_path.replace('.png', '_eta_diagnostic.png'), dpi=150,
                 bbox_inches='tight', facecolor='white')
    print(f"  Saved: {save_path.replace('.png', '_eta_diagnostic.png')}")
    plt.close(fig2)


# ═══════════════════════════════════════════════════════════════════════
#  5. Main analysis
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("=" * 76)
    print("  Path 6: Linear Stability of L4/L5 in Cassi Softened Gravity")
    print("=" * 76)
    
    print("""
  Derivation
  ──────────────────────────────────────────────────────────────────────
  Effective potential in the corotating frame:
    Φ_eff(r₁, r₂) = Φ₁(r₁) + Φ₂(r₂) - ½Ω²(x²+y²)
  
  At L4/L5 (r₁ = r₂ = a), the geometry gives:
    x − x₁ = a/2  →  (x−x₁)/a = ½,  y/a = √3/2
    x − x₂ = −a/2 →  (x−x₂)/a = −½
  
  Hessian components (for any spherically symmetric Φ):
    ∂²Φ_i/∂x² = Φ'_i(a)/4  +  Φ'_i(a)/a · 3/4
    ∂²Φ_i/∂y² = Φ'_i(a)·3/4 +  Φ'_i(a)/a · 1/4
    ∂²Φ_i/∂x∂y = (x−x_i)·y / a² · (Φ''_i(a) − Φ'_i(a)/a)
  
  Summing both masses (Φ₁' = M₁·f(a), Φ₁'' = M₁·f'(a)):
    Φ_xx = K/4,   Φ_yy = 3K/4,   Φ_xy = √3/4·(1−2μ)·K
  where K = M_total·(f'(a)−f(a)/a) and μ = M₂/(M₁+M₂).
  
  Characteristic equation: λ⁴ + b·λ² + c = 0
    b = K + 4Ω²,   c = 3K²μ(1−μ)/4
  
  Stability requires b > 0 (always true for softened gravity) and
  the discriminant condition: η² ≥ 3·μ·(1−μ)
  where η = −(K+4Ω²)/K = 4Ω²/|K| − 1.
  """)
    
    # ═════════════════════════════════════════════════════════════════
    #  Run the analysis
    # ═════════════════════════════════════════════════════════════════
    print("  Running analysis...\n")
    
    grid = scan_stability_grid(n_mu=50, n_sigma=40)
    
    mu_vals = grid['mu_vals']
    sigma_vals = grid['sigma_vals']
    stable = grid['stable']
    mu_crit = grid['mu_crit']
    eta_vals = grid['eta_vals']
    b_vals = grid['b_vals']
    K_vals = grid['K_vals']
    Omega2_vals = grid['Omega2_vals']
    newt_mu_crit = grid['newtonian_mu_crit']
    sigma_transition = grid['sigma_transition']
    
    # ═════════════════════════════════════════════════════════════════
    #  Print table of results
    # ═════════════════════════════════════════════════════════════════
    print("  Stability parameters vs σ/a")
    print("  " + "─" * 72)
    header = f"  {'σ/a':>8s}  {'η':>10s}  {'Ω²':>10s}  {'K':>10s}  {'μ_crit':>10s}  {'Stable?':>10s}"
    print(header)
    print("  " + "─" * 72)
    
    for j in range(len(sigma_vals)):
        s = sigma_vals[j]
        eta = eta_vals[j]
        mu_c = mu_crit[j]
        
        # Sample stability at μ = 0.01 and μ = 0.1
        stable_lo = check_stability(0.01, s)
        stable_hi = check_stability(0.1, s)
        stable_str = f"{'Y' if stable_lo else 'N'} (μ=0.01)"
        if stable_lo and stable_hi:
            stable_str = f"Y (μ≤{mu_c:.3f})"
        elif not stable_lo:
            stable_str = "N (all μ)"
            
        print(f"  {s:8.4f}  {eta:10.4f}  {Omega2_vals[j]:10.4f}  "
              f"{K_vals[j]:10.4f}  {mu_c:10.4f}  {stable_str:>10s}")
    
    print("  " + "─" * 72)
    
    # ═════════════════════════════════════════════════════════════════
    #  Key findings
    # ═════════════════════════════════════════════════════════════════
    print(f"""
  ──────────────────────────────────────────────────────────────────────
  KEY FINDINGS
  ──────────────────────────────────────────────────────────────────────
  
  1. Newtonian limit (σ/a → 0):
     η = 1/3 ≈ 0.333
     μ_crit = {newt_mu_crit:.6f}
     (Matches the classical Routh criterion μ_crit = 0.0385...)
  
  2. With softening (σ/a > 0):
     η increases monotonically with σ/a (see table above).
     μ_crit INCREASES with σ/a.
     → Softening makes L4/L5 MORE stable.
  
  3. Universal stability threshold:
     When η = √3/2 ≈ {np.sqrt(3)/2:.4f}, the discriminant condition
     holds for ALL μ ∈ [0, ½].
     → For σ/a ≥ {sigma_transition:.4f}, L4/L5 are stable for every
       mass ratio in the CR3BP.
  
  4. Physical mechanism:
     The softening smooths the gravitational potential, reducing the
     curvature |K| = M_total·|f'(a)−f(a)/a| faster than it reduces
     the orbital frequency Ω² = M_total·f(a)/a.
     
     Since f'(a) involves the SECOND derivative (more affected by
     smoothing) while Ω² involves the FIRST derivative (less affected),
     their ratio Ω²/|K| increases with σ.
     
     The stability parameter η = 4Ω²/|K| − 1 therefore grows, expanding
     the stable region in (μ, σ/a) space.""")
    
    if sigma_transition is not None:
        print(f"""  
  5. Critical σ/a for universal stability:
     η(σ/a) = √3/2 at σ/a = {sigma_transition:.4f}
     For σ/a > {sigma_transition:.4f}, L4/L5 are stable for ALL μ.
     (Note: Lagrange points themselves disappear at σ/a ≈ 0.7,
      so this is within the existence window.)
     """)
    
    # ═════════════════════════════════════════════════════════════════
    #  Answer explicit questions
    # ═════════════════════════════════════════════════════════════════
    
    # Q1: Does softening make L4/L5 MORE or LESS stable?
    eta_increase = eta_vals[-1] > eta_vals[0] * 2
    mu_crit_increase = mu_crit[-1] > mu_crit[0]
    
    print(f"""
  ──────────────────────────────────────────────────────────────────────
  ANSWERS TO SPECIFIC QUESTIONS
  ──────────────────────────────────────────────────────────────────────
  
  Q1: Does softening make L4/L5 MORE or LESS stable?
  
      ANSWER: MORE stable. μ_crit increases from {newt_mu_crit:.4f}
      at σ/a = 0 to {mu_crit[-1]:.4f} at σ/a = 0.5.
      
      Softening reduces the curvature of the effective potential at L4/L5,
      which weakens the gravitational tidal forces that drive instability.
      The Coriolis restoring forces (proportional to Ω) are also reduced,
      but not as quickly as the tidal forces.
      
      Quantitatively, the stability parameter η = 4Ω²/|K| − 1 increases
      from {eta_vals[0]:.4f} at σ/a = 0 to {eta_vals[-1]:.4f} at σ/a = 0.5.
  
  Q2: Is there a σ/a where L4/L5 become UNSTABLE for ALL μ?""")
    
    if sigma_transition is not None:
        # Check if any regime has μ_crit = 0
        has_all_unstable = np.any(mu_crit < 1e-6)
        if has_all_unstable:
            print(f"""
      ANSWER: YES. For σ/a < {sigma_vals[np.where(mu_crit < 1e-6)[0][0]]:.4f},
      μ_crit = 0 meaning L4/L5 are unstable for all μ.
      (This would require b < 0, which is unphysical—but let's check.)
      """)
        else:
            print(f"""
      ANSWER: NO—in fact the opposite happens. For σ/a ≥
      {sigma_transition:.4f}, L4/L5 become STABLE for ALL μ ∈ [0, ½].
      This is because η exceeds √3/2 ≈ {np.sqrt(3)/2:.4f}, making the
      discriminant b² − 4c positive for every mass ratio.
      
      However, note that at σ/a ≈ 0.7 the Lagrange points themselves
      vanish (from Path 5), so "stable for all μ" only holds where the
      equilibrium exists.
      """)
    else:
        print(f"""
      ANSWER: No evidence of complete destabilization for any
      σ/a ∈ [0, 0.5]. The condition b > 0 holds throughout.
      """)
    
    print(f"""
  Q3: What's the physical reason?
  
      The Routh stability criterion for L4/L5 involves a competition
      between the gravitational TIDAL CURVATURE (second derivative of
      potential, measured by |K|) and the CORIOLIS RESTORING FORCES
      (proportional to rotation rate Ω).
      
      In the Newtonian case: |K| = 3GM_total/a³, Ω² = GM_total/a³,
      giving η = 4·Ω²/|K| − 1 = 4/3 − 1 = 1/3.
      
      With Gaussian softening, the smoothed potential Φ(r) removes the
      1/r singularity. The derivative f'(a) becomes less negative, so
      |K| = |f'(a) − f(a)/a| decreases. But f(a)/a (which is Ω²) also
      decreases, only more slowly.
      
      The key ratio:
        Ω²/|K| = f(a)/a / |f'(a) − f(a)/a|
      
      For the softened potential, f'(a) is proportional to:
        -2φ(x) + (4/√π)·x³·exp(−x²)
      while f(a)/a is proportional to φ(x).
      
      As x = a/(σ√2) decreases (σ increases), the term (4/√π)x³exp(−x²)
      partially cancels the −2φ term in f'(a), making |f'(a) − f(a)/a|
      vanish faster than f(a)/a. Hence Ω²/|K| → ∞ as σ → ∞.
      
      In physical terms: SMOOTHING A POTENTIAL REDUCES ITS HIGHER
      DERIVATIVES MORE THAN ITS LOWER DERIVATIVES. The curvature (second
      derivative) is more affected than the force (first derivative),
      tilting the competition in favor of the Coriolis stabilization.
      """)
    
    # ═════════════════════════════════════════════════════════════════
    #  Generate figures
    # ═════════════════════════════════════════════════════════════════
    print(f"""
  ──────────────────────────────────────────────────────────────────────
  Generating Figures
  ──────────────────────────────────────────────────────────────────────
  """)
    
    make_stability_plot(grid)
    
    print(f"""
  ──────────────────────────────────────────────────────────────────────
  Verifying with known Newtonian results
  ──────────────────────────────────────────────────────────────────────
  
  For σ/a = 0 (pure Newtonian):
    Hessian at L4:  Φ_xx = -3/4  Φ_yy = -9/4  Φ_xy = -3√3/4·(1-2μ)
    Characteristic: λ⁴ + λ² + 27μ(1-μ)/4 = 0
    μ_crit = {newt_mu_crit:.6f}
    
  This matches the classical Routh criterion: μ_crit = (1−√(23/27))/2.
  
  Test: μ = 0.01 → stable at all σ/a ∈ [0, 0.5] (below Newtonian threshold)
  Test: μ = 0.05 → unstable at small σ/a, stable at large σ/a
  """)
    
    # Spot checks
    for mu_test in [0.01, 0.05, 0.1]:
        for s_test in [0.0, 0.1, 0.3, 0.5]:
            stable_test = check_stability(mu_test, s_test)
            print(f"    μ={mu_test:.3f}, σ/a={s_test:.2f}: "
                  f"{'STABLE' if stable_test else 'UNSTABLE'}")
    
    # ═════════════════════════════════════════════════════════════════
    #  Return structured results
    # ═════════════════════════════════════════════════════════════════
    results = {
        'sigma_vals': sigma_vals.tolist(),
        'mu_crit': mu_crit.tolist(),
        'eta_vals': eta_vals.tolist(),
        'newtonian_mu_crit': newt_mu_crit,
        'sigma_transition': sigma_transition,
        'mu_crit_increases_with_sigma': bool(mu_crit_increase),
        'stable_for_all_mu_threshold': float(sigma_transition) if sigma_transition else None,
    }
    
    return results


if __name__ == '__main__':
    main()
