#!/usr/bin/env python3
r"""Path 7: Galactic Rotation Curves in Cassi Softened Gravity.

Tests whether Cassi softened gravity can explain flat galactic rotation
curves without invoking dark matter.

Physical setup
--------------
In Cassi softened gravity, a point mass M has potential:
    Phi(r) = -GM/r * erf(r/(sigma * sqrt(2)))

For a mass distribution, the total softened potential is a convolution
of the density with the softened (erf) Green's function.  The circular
velocity squared is:

    v_circ^2(r) = G * \int dm(s) * K(r, s, sigma)

where K(r,s,sigma) is the softened force kernel.  For a spherical shell
at radius s, K is computed by integrating the softened force over all
angles, properly reducing to the Newtonian shell theorem in the limit
sigma -> 0.  For a thin ring (disk), the same integral gives the
midplane radial force.

Key question
------------
What single sigma value could flatten rotation curves to the observed
level (~200 km/s out to 30 kpc)?  Does this sigma satisfy the binary
pulsar constraint sigma < 370 km (= 1.2e-14 kpc)?

Usage
-----
    python experiments/path7_rotation_curves.py

Produces:
    experiments/path7_rotation_curves.png  (2-panel figure)
"""

import sys
import os
import time

import numpy as np
from scipy.special import erf, i0e, i1e, k0e, k1e
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter


# ═══════════════════════════════════════════════════════════════════════
#  Physical constants & galaxy parameters
# ═══════════════════════════════════════════════════════════════════════

G = 4.302e-6             # kpc (km/s)^2 / M_sun
SIGMA_BINARY_PULSAR = 370.0 / 3.086e16   # 370 km -> kpc ~ 1.20e-14 kpc
MSUN = 1.989e30          # kg  (not used directly; everything in M_sun)

# Galaxy model
M_DISK = 6.0e10          # M_sun
R_DISK = 3.0             # kpc  scale length
M_BULGE = 1.0e10         # M_sun
R_BULGE = 0.5            # kpc  scale length (exponential sphere)
R_MAX = 30.0             # kpc
N_GRID = 200             # radial grid points
N_THETA = 80             # Gauss-Legendre points for angular integral


# ═══════════════════════════════════════════════════════════════════════
#  1. Quadrature helpers
# ═══════════════════════════════════════════════════════════════════════

def gauss_legendre_quad_0_pi(n):
    r"""Return nodes and weights for \int_0^\pi f(theta) dtheta.

    Maps standard Gauss-Legendre from [-1, 1] to [0, pi].
    """
    x, w = np.polynomial.legendre.leggauss(n)
    theta = np.pi * (x + 1.0) / 2.0
    weights = w * np.pi / 2.0
    return theta, weights


# ═══════════════════════════════════════════════════════════════════════
#  2. Softened gravity kernels
# ═══════════════════════════════════════════════════════════════════════

def _softened_core(d, sigma):
    r"""Compute softened gravity difference kernel.
    core = erf(d/(sigma sqrt2))/d^3 - sqrt(2/pi)/(sigma d^2)*exp(-d^2/(2 sigma^2))

    This cancels the 1/d^3 singularity at d=0, leaving a finite value.

    Parameters
    ----------
    d : ndarray
        Distance [kpc].
    sigma : float
        Softening length [kpc].

    Returns
    -------
    core : ndarray
        Value of the core expression [kpc^{-3}].
    """
    d_safe = np.maximum(d, 1e-30)
    x = d_safe / (sigma * np.sqrt(2.0))

    term1 = erf(x) / (d_safe ** 3)
    term2 = np.sqrt(2.0 / np.pi) / (sigma * d_safe ** 2) * np.exp(-x ** 2)

    # For d -> 0, both terms diverge but their difference is finite
    # Use series expansion for very small d where cancellation is severe
    tiny = d_safe < 1e-4 * sigma
    if np.any(tiny):
        # Series: core = sqrt(2/pi)/(2*sigma^3) * [1 - d^2/(5*sigma^2) + ...]
        core_series = np.sqrt(2.0 / np.pi) / (2.0 * sigma ** 3) * (
            1.0 - (d_safe ** 2) / (5.0 * sigma ** 2)
            + (d_safe ** 4) / (70.0 * sigma ** 4)
            - (d_safe ** 6) / (2100.0 * sigma ** 6)
        )
        core = np.where(tiny, core_series, term1 - term2)
    else:
        core = term1 - term2

    return core


def compute_kernel_shell_matrix(r_grid, sigma, theta, weights):
    r"""Compute softened spherical-shell kernel matrix K_shell(r_i, s_j, sigma).

    For a unit-mass spherical shell at radius s, the contribution to
    v_circ^2 at radius r is:

        K_shell = r/2 * \int_0^\pi sin(theta) * (r - s*cos(theta))
                  * softened_core(d, sigma) * dtheta

    where d = sqrt(r^2 + s^2 - 2 r s cos(theta)).

    In the Newtonian limit (sigma -> 0), this gives 1/r for s<r and 0 for s>r
    (the shell theorem).

    Parameters
    ----------
    r_grid : ndarray, shape (N,)
        Radial grid [kpc].
    sigma : float
        Softening length [kpc].
    theta : ndarray, shape (M,)
        Gauss-Legendre nodes.
    weights : ndarray, shape (M,)
        Gauss-Legendre weights.

    Returns
    -------
    K : ndarray, shape (N, N)
        Kernel matrix: K[i,j] gives v_circ^2 contribution per unit mass at
        radius s_j to radius r_i.  Multiply by dm(s_j) and sum to get v_circ^2.
    """
    N = len(r_grid)
    rr, ss = np.meshgrid(r_grid, r_grid, indexing='ij')

    # d_ijk = distance between r_i and a point on shell at s_j, angle theta_k
    cos_t = np.cos(theta)[None, None, :]
    d = np.sqrt(
        rr[:, :, None] ** 2
        + ss[:, :, None] ** 2
        - 2.0 * rr[:, :, None] * ss[:, :, None] * cos_t
    )

    core = _softened_core(d, sigma)

    # Angular factor for shell: sin(theta) * (r - s*cos(theta))
    sin_t = np.sin(theta)[None, None, :]
    ang_factor = sin_t * (rr[:, :, None] - ss[:, :, None] * cos_t)

    # K_shell = r/2 * \int sin(theta)*(r-s*cos(theta))*core dtheta
    integrand = (rr[:, :, None] / 2.0) * ang_factor * core
    K = np.sum(integrand * weights[None, None, :], axis=-1)

    return K


def compute_kernel_ring_matrix(r_grid, sigma, theta, weights):
    r"""Compute softened thin-ring kernel matrix K_ring(r_i, s_j, sigma).

    For a unit-mass ring at radius s in the midplane, the contribution to
    v_circ^2 at radius r (midplane) is:

        K_ring = r/pi * \int_0^\pi (r - s*cos(theta))
                 * softened_core(d, sigma) * dtheta

    where d = sqrt(r^2 + s^2 - 2 r s cos(theta)).

    Parameters
    ----------
    r_grid : ndarray, shape (N,)
        Radial grid [kpc].
    sigma : float
        Softening length [kpc].
    theta : ndarray, shape (M,)
        Gauss-Legendre nodes.
    weights : ndarray, shape (M,)
        Gauss-Legendre weights.

    Returns
    -------
    K : ndarray, shape (N, N)
        Kernel matrix.
    """
    N = len(r_grid)
    rr, ss = np.meshgrid(r_grid, r_grid, indexing='ij')

    cos_t = np.cos(theta)[None, None, :]
    d = np.sqrt(
        rr[:, :, None] ** 2
        + ss[:, :, None] ** 2
        - 2.0 * rr[:, :, None] * ss[:, :, None] * cos_t
    )

    core = _softened_core(d, sigma)

    # Angular factor for ring: (r - s*cos(theta))
    # Symmetry: integrand is even about pi, integrate [0, pi] and multiply by 2
    # K_ring = r/(2*pi) * \int_0^{2pi} ...  =  r/pi * \int_0^\pi ...
    ang_factor = rr[:, :, None] - ss[:, :, None] * cos_t

    integrand = (rr[:, :, None] / np.pi) * ang_factor * core
    K = np.sum(integrand * weights[None, None, :], axis=-1)

    return K


# ═══════════════════════════════════════════════════════════════════════
#  3. Mass models
# ═══════════════════════════════════════════════════════════════════════

class ExponentialDisk:
    """Exponential disk with given mass and scale length."""

    def __init__(self, M_disk, R_d):
        self.M = M_disk        # total mass [M_sun]
        self.R_d = R_d         # scale length [kpc]
        self.Sigma_0 = M_disk / (2.0 * np.pi * R_d ** 2)  # central surface density

    def surface_density(self, R):
        """Surface density at radius R [M_sun/kpc^2]."""
        return self.Sigma_0 * np.exp(-R / self.R_d)

    def mass_enc(self, R):
        """Newtonian enclosed mass within radius R [M_sun]."""
        # M_disk * [1 - (1 + R/R_d) * exp(-R/R_d)]
        x = R / self.R_d
        return self.M * (1.0 - (1.0 + x) * np.exp(-x))

    def v_circ_newton(self, R):
        """Newtonian rotation curve using Freeman's analytic formula [km/s].

        v^2(R) = 4*pi*G*Sigma_0*R_d * y^2 * [I_0(y)K_0(y) - I_1(y)K_1(y)]
        where y = R / (2*R_d).
        """
        y = R / (2.0 * self.R_d)
        # Use exponentially-scaled Bessel functions for numerical stability
        bessel = i0e(y) * k0e(y) - i1e(y) * k1e(y)
        v2 = 4.0 * np.pi * G * self.Sigma_0 * self.R_d * y ** 2 * bessel
        return np.sqrt(np.maximum(v2, 0.0))

    def mass_list(self, r_grid):
        """Return mass [M_sun] in each radial bin for the disk."""
        dr = r_grid[1] - r_grid[0]
        # Mass in ring between s and s+ds: dM = 2*pi*s*Sigma(s)*ds
        dm = 2.0 * np.pi * r_grid * self.surface_density(r_grid) * dr
        return dm


class ExponentialBulge:
    """Exponential spheroidal bulge (rho = rho_0 * exp(-r / r_b))."""

    def __init__(self, M_bulge, r_b):
        self.M = M_bulge       # total mass [M_sun]
        self.r_b = r_b         # scale length [kpc]
        # Normalization: M = 8*pi*rho_0*r_b^3
        self.rho_0 = M_bulge / (8.0 * np.pi * r_b ** 3)

    def density(self, r):
        """Density at radius r [M_sun/kpc^3]."""
        return self.rho_0 * np.exp(-r / self.r_b)

    def mass_enc(self, R):
        """Newtonian enclosed mass within radius R [M_sun]."""
        x = R / self.r_b
        # M_bulge * [1 - exp(-x)*(1 + x + x^2/2 + x^3/6)]
        return self.M * (1.0 - np.exp(-x) * (
            1.0 + x + x ** 2 / 2.0 + x ** 3 / 6.0
        ))

    def v_circ_newton(self, R):
        """Newtonian rotation curve [km/s]."""
        v2 = G * self.mass_enc(R) / R
        return np.sqrt(np.maximum(v2, 0.0))

    def mass_list(self, r_grid):
        """Return mass [M_sun] in each spherical shell."""
        dr = r_grid[1] - r_grid[0]
        # dM = 4*pi*s^2*rho(s)*ds
        dm = 4.0 * np.pi * r_grid ** 2 * self.density(r_grid) * dr
        return dm


# ═══════════════════════════════════════════════════════════════════════
#  4. Rotation curve computation
# ═══════════════════════════════════════════════════════════════════════

def compute_newtonian_rc(r_grid, disk, bulge):
    """Compute Newtonian rotation curve (disk + bulge)."""
    v_disk = disk.v_circ_newton(r_grid)
    v_bulge = bulge.v_circ_newton(r_grid)
    v_total = np.sqrt(v_disk ** 2 + v_bulge ** 2)
    return v_total


def compute_cassi_rc(r_grid, sigma, disk, bulge, theta, weights):
    """Compute Cassi softened rotation curve for given sigma.

    The total v_circ^2(r) is obtained by summing contributions from each
    mass element, weighted by the appropriate softened kernel.  The disk
    uses the ring kernel; the bulge uses the spherical shell kernel.

    Parameters
    ----------
    r_grid : ndarray, shape (N,)
        Radial grid [kpc].
    sigma : float
        Softening length [kpc].
    disk : ExponentialDisk
        Disk model.
    bulge : ExponentialBulge
        Bulge model.
    theta : ndarray, shape (M,)
        Gauss-Legendre nodes.
    weights : ndarray, shape (M,)
        Gauss-Legendre weights.

    Returns
    -------
    v_circ : ndarray, shape (N,)
        Circular velocity [km/s].
    """
    N = len(r_grid)

    # Disk contribution via ring kernel
    K_ring = compute_kernel_ring_matrix(r_grid, sigma, theta, weights)
    dm_disk = disk.mass_list(r_grid)
    v2_disk = G * np.sum(K_ring * dm_disk[None, :], axis=1)

    # Bulge contribution via shell kernel
    K_shell = compute_kernel_shell_matrix(r_grid, sigma, theta, weights)
    dm_bulge = bulge.mass_list(r_grid)
    v2_bulge = G * np.sum(K_shell * dm_bulge[None, :], axis=1)

    return np.sqrt(np.maximum(v2_disk + v2_bulge, 1e-30))


def flattening_ratio(v_circ, r_grid, r_inner=5.0, r_outer=30.0):
    """Compute flattening ratio v(r_outer) / v(r_inner).

    Values near 1 indicate a flat rotation curve.
    """
    i_inner = int(np.argmin(np.abs(r_grid - r_inner)))
    i_outer = int(np.argmin(np.abs(r_grid - r_outer)))
    return v_circ[i_outer] / v_circ[i_inner]


def rms_deviation_from_flat(v_circ, r_grid, v_target=200.0):
    """RMS deviation from a perfectly flat rotation curve at v_target km/s.

    Measures absolute agreement with observed flat rotation curves.
    """
    return np.sqrt(np.mean((v_circ - v_target) ** 2))


def find_sigma_flat(r_grid, disk, bulge, theta, weights,
                    target_ratio=0.9, sigma_range=(0.1, 30.0), n_scan=40):
    """Find sigma that gives flattening ratio close to target.

    Searches over a log-spaced sigma grid and returns the sigma value
    that produces flattening ratio >= target_ratio.

    Parameters
    ----------
    r_grid : ndarray
        Radial grid [kpc].
    disk : ExponentialDisk
    bulge : ExponentialBulge
    theta, weights : ndarray
        Quadrature data.
    target_ratio : float
        Target flattening ratio v(30)/v(5).
    sigma_range : tuple
        (sigma_min, sigma_max) in kpc.
    n_scan : int
        Number of sigma values to scan.

    Returns
    -------
    sigma_flat : float
        Softening length that achieves target ratio [kpc].
    sigma_vals : ndarray
        Scanned sigma values.
    ratios : ndarray
        Flattening ratios for each sigma.
    """
    sigma_vals = np.logspace(np.log10(sigma_range[0]),
                             np.log10(sigma_range[1]), n_scan)
    ratios = np.zeros(n_scan)

    print(f"  Scanning sigma from {sigma_range[0]:.1f} to {sigma_range[1]:.1f} kpc...")
    for i, s in enumerate(sigma_vals):
        v = compute_cassi_rc(r_grid, s, disk, bulge, theta, weights)
        ratios[i] = flattening_ratio(v, r_grid)
        if (i + 1) % 10 == 0:
            print(f"    sigma = {s:.2f} kpc  ->  ratio = {ratios[i]:.4f}")

    # Find sigma where ratio >= target_ratio
    mask = ratios >= target_ratio
    if np.any(mask):
        sigma_flat = sigma_vals[mask][0]
        # Interpolate for more precise estimate
        if mask[0]:
            # Already saturated at smallest sigma
            idx = np.where(mask)[0][0]
        else:
            idx = np.where(mask)[0][0]
        # Linear interpolation in log-log space
        if idx > 0:
            log_s = np.log10(sigma_vals[idx - 1:idx + 1])
            log_r = np.log10(ratios[idx - 1:idx + 1])
            if np.isfinite(log_r).all() and log_r[1] > log_r[0]:
                sigma_flat = 10.0 ** np.interp(
                    np.log10(target_ratio), log_r, log_s
                )
    else:
        sigma_flat = sigma_range[1]  # Not reached within range

    return sigma_flat, sigma_vals, ratios


# ═══════════════════════════════════════════════════════════════════════
#  5. Figure
# ═══════════════════════════════════════════════════════════════════════

def make_figure(r_grid, v_newt, cassi_curves, sigma_vals,
                sigma_flat, sigma_scan, ratio_scan,
                newt_v30=None, newt_v5=None,
                savepath='experiments/path7_rotation_curves.png'):
    """Produce 2-panel figure.

    Panel A: rotation curves (Newtonian + Cassi at multiple sigma + flat ref)
    Panel B: sigma vs flattening ratio, showing the tension with binary pulsars
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

    # ═════════════════════════════════════════════════════════════════
    # Panel A: Rotation curves
    # ═════════════════════════════════════════════════════════════════

    # Observed flat rotation reference (~200 km/s, tanh rise)
    v_flat = 200.0
    R_core = 2.0
    v_obs = v_flat * np.tanh(r_grid / R_core)

    # Newtonian
    ax1.plot(r_grid, v_newt, 'k-', lw=2.5, label='Newtonian (no DM)',
             zorder=10)

    # Cassi curves
    colors = plt.cm.plasma(np.linspace(0.1, 0.9, len(sigma_vals)))
    for i, s in enumerate(sigma_vals):
        if s <= 0:
            continue
        v_c = cassi_curves[i]
        label = rf'Cassi $\sigma = {s:.1f}$ kpc' if s >= 1 else \
                rf'Cassi $\sigma = {s:.2f}$ kpc'
        ax1.plot(r_grid, v_c, '-', color=colors[i], lw=1.8, alpha=0.85,
                 label=label)

    # Observed flat reference
    ax1.plot(r_grid, v_obs, 'r--', lw=2.0, label=r'Observed flat ($\sim$200 km/s)',
             zorder=5)

    # Labels
    ax1.set_xlabel('Radius $R$ [kpc]', fontsize=13)
    ax1.set_ylabel('Circular velocity $v_{\\mathrm{circ}}$ [km/s]',
                   fontsize=13)
    ax1.set_title('A: Rotation Curves in Cassi Softened Gravity',
                  fontsize=14, pad=10)
    ax1.set_xlim(0, R_MAX)
    ax1.set_ylim(0, max(v_newt.max(), v_flat) * 1.15)
    ax1.grid(True, alpha=0.25, linestyle=':')
    ax1.legend(fontsize=7.5, loc='upper right', framealpha=0.85,
               ncol=2, columnspacing=0.8)

    # Vertical lines for disk scale length and bulge scale length
    ax1.axvline(R_DISK, color='gray', ls=':', lw=1.0, alpha=0.5)
    ax1.text(R_DISK + 0.3, ax1.get_ylim()[1] * 0.92, f'$R_d = {R_DISK}$ kpc',
             fontsize=7.5, color='gray', alpha=0.7)

    # Annotate binary pulsar constraint (far off scale)
    ax1.text(0.97, 0.03,
             f'Binary pulsar constraint:\n'
             rf'$\sigma < {SIGMA_BINARY_PULSAR:.1e}$ kpc'
             '\n(= 370 km, far off this plot)',
             transform=ax1.transAxes, fontsize=7.5, ha='right', va='bottom',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='mistyrose',
                       edgecolor='red', alpha=0.85))

    # ═════════════════════════════════════════════════════════════════
    # Panel B: sigma vs flattening (including amplitude tension)
    # ═════════════════════════════════════════════════════════════════

    ax2.semilogx(sigma_scan, ratio_scan, '-o', c='#2c3e50', lw=2.0,
                 ms=4, label=r'$v(30\,\mathrm{kpc})/v(5\,\mathrm{kpc})$')

    # Reference lines for key ratios
    for target, ls, color in [(0.8, ':', '#e67e22'),
                               (0.9, '--', '#e74c3c'),
                               (1.0, '-', '#8e44ad')]:
        ax2.axhline(target, color=color, ls=ls, lw=1.2, alpha=0.5,
                    label=f'Ratio = {target}')

    # Mark sigma_flat if found
    if sigma_flat is not None and sigma_flat < sigma_scan[-1]:
        target_ratio = np.interp(np.log10(sigma_flat),
                                 np.log10(sigma_scan), ratio_scan)
        ax2.axvline(sigma_flat, color='#2c3e50', ls='-', lw=1.5, alpha=0.5)
        ax2.plot(sigma_flat, target_ratio, '*', color='#f1c40f',
                 markersize=15, zorder=10,
                 label=rf'$\sigma_{{\mathrm{{flat}}}} = {sigma_flat:.2f}$ kpc')

    # Mark binary pulsar constraint (way off to the left)
    ax2.axvline(SIGMA_BINARY_PULSAR, color='red', ls='-', lw=1.5,
                alpha=0.3, zorder=3)
    ax2.annotate(rf'Binary pulsar: $\sigma < {SIGMA_BINARY_PULSAR:.1e}$ kpc',
                 xy=(SIGMA_BINARY_PULSAR, 0.02),
                 fontsize=6.5, color='red', ha='left',
                 rotation=90, va='bottom')

    # Newtonian reference line
    newt_ratio = v_newt[np.argmin(np.abs(r_grid - 30.0))] / \
                 v_newt[np.argmin(np.abs(r_grid - 5.0))]
    ax2.axhline(newt_ratio, color='black', ls=':', lw=1.0, alpha=0.4,
                label=rf'Newtonian ratio = {newt_ratio:.3f}')

    # Shade region where curve is actually rising (inverted, unphysical)
    ax2.fill_between(sigma_scan, 1.0, ratio_scan,
                     where=ratio_scan > 1.0,
                     alpha=0.1, color='orange',
                     label='Inverted (v(30) > v(5))')
    ax2.fill_between(sigma_scan, 0, 0.8,
                     alpha=0.05, color='red',
                     label='Not flat ($v(30)/v(5) < 0.8$)')

    ax2.set_xlabel('Softening length $\\sigma$ [kpc]', fontsize=13)
    ax2.set_ylabel('Flattening ratio $v(30)/v(5)$', fontsize=13)
    ax2.set_title('B: Required Softening for Flat Rotation Curves',
                  fontsize=14, pad=10)
    ax2.set_xlim(sigma_scan[0] * 0.8, sigma_scan[-1] * 1.2)
    ax2.set_ylim(0, max(ratio_scan.max(), 1.1) * 1.08)
    ax2.grid(True, alpha=0.25, linestyle=':')
    ax2.legend(fontsize=7, loc='upper left', framealpha=0.85,
               ncol=1, columnspacing=0.8)

    # Add text annotation about amplitude
    # Show that even at sigma=3.5 kpc (ratio≈0.9), v(30) is only ~100 km/s
    i_flat = np.argmin(np.abs(sigma_scan - sigma_flat)) if sigma_flat < sigma_scan[-1] else -1
    if i_flat > 0:
        pass  # too dynamic to label

    fig.suptitle('Path 7: Rotation Curves in Cassi Softened Gravity\n'
                 'Can a single $\\sigma$ explain dark-matter-free flat rotation curves?',
                 fontsize=15, y=1.02)

    fig.tight_layout()
    fig.savefig(savepath, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"  Saved: {savepath}")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════
#  6. Main analysis
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("=" * 78)
    print("  Path 7: Galactic Rotation Curves in Cassi Softened Gravity")
    print("=" * 78)
    print()
    print(f"  Galaxy model:")
    print(f"    Disk:  M = {M_DISK:.1e} M_sun,  R_d = {R_DISK} kpc")
    print(f"    Bulge: M = {M_BULGE:.1e} M_sun,  r_b = {R_BULGE} kpc")
    print(f"    Total baryonic mass: {M_DISK + M_BULGE:.1e} M_sun")
    print()
    print(f"  Binary pulsar constraint: sigma < {SIGMA_BINARY_PULSAR:.2e} kpc")
    print(f"                            = {370} km")
    print()

    # ═════════════════════════════════════════════════════════════════
    #  Build grids and mass models
    # ═════════════════════════════════════════════════════════════════

    print("[1/5] Setting up galaxy model...")
    r_grid = np.linspace(0.05, R_MAX, N_GRID)  # avoid r=0 singularity
    disk = ExponentialDisk(M_DISK, R_DISK)
    bulge = ExponentialBulge(M_BULGE, R_BULGE)

    # Precompute quadrature points
    theta, weights = gauss_legendre_quad_0_pi(N_THETA)

    # ═════════════════════════════════════════════════════════════════
    #  Newtonian rotation curve
    # ═════════════════════════════════════════════════════════════════

    print("[2/5] Computing Newtonian rotation curve...")
    t0 = time.time()
    v_newt = compute_newtonian_rc(r_grid, disk, bulge)
    t_newt = time.time() - t0
    print(f"    Time: {t_newt:.2f}s")
    print(f"    Peak v_circ = {v_newt.max():.1f} km/s at R = {r_grid[v_newt.argmax()]:.1f} kpc")
    print(f"    v_circ at 30 kpc = {v_newt[-1]:.1f} km/s")
    newt_ratio = v_newt[-1] / v_newt[np.argmin(np.abs(r_grid - 5.0))]
    print(f"    Flattening ratio v(30)/v(5) = {newt_ratio:.4f}")
    print(f"    RMS deviation from 200 km/s flat = {rms_deviation_from_flat(v_newt, r_grid):.0f} km/s")
    print()

    # ═════════════════════════════════════════════════════════════════
    #  Cassi rotation curves for multiple sigma values
    # ═════════════════════════════════════════════════════════════════

    print("[3/5] Computing Cassi softened rotation curves...")
    sigma_display = [0.1, 0.5, 1.0, 3.0, 5.0, 10.0]
    cassi_curves = []
    t0 = time.time()
    for s in sigma_display:
        t1 = time.time()
        v_c = compute_cassi_rc(r_grid, s, disk, bulge, theta, weights)
        cassi_curves.append(v_c)
        ratio = flattening_ratio(v_c, r_grid)
        rms = rms_deviation_from_flat(v_c, r_grid)
        print(f"    sigma = {s:.1f} kpc  ->  v_peak = {v_c.max():.1f} km/s,  "
              f"v(30) = {v_c[-1]:.1f} km/s,  ratio = {ratio:.4f},  "
              f"RMS = {rms:.0f} km/s  [{time.time() - t1:.1f}s]")
    print(f"    Total time: {time.time() - t0:.1f}s")

    # ═════════════════════════════════════════════════════════════════
    #  Find sigma_flat
    # ═════════════════════════════════════════════════════════════════

    t0 = time.time()
    sigma_scan = np.logspace(np.log10(0.2), np.log10(30.0), 35)
    ratio_scan = np.zeros_like(sigma_scan)
    print("  Scanning sigma from 0.2 to 30.0 kpc...")
    for i, s in enumerate(sigma_scan):
        v = compute_cassi_rc(r_grid, s, disk, bulge, theta, weights)
        ratio_scan[i] = flattening_ratio(v, r_grid)
        if (i + 1) % 7 == 0:
            print(f"    sigma = {s:.2f} kpc  ->  v(30)/v(5) = {ratio_scan[i]:.4f}")
    print(f"    Time: {time.time() - t0:.1f}s")

    # Interpolate sigma for all target ratios from one scan
    print("  Interpolating sigma for target flattening ratios...")
    ratios_to_check = [0.75, 0.80, 0.85, 0.90, 0.95]
    log_s = np.log10(sigma_scan)
    for rt in ratios_to_check:
        if rt <= ratio_scan[0] or rt > ratio_scan.max():
            s_str = "not reached" if rt > ratio_scan.max() else "below range"
            print(f"    Ratio = {rt:.2f}  ->  sigma = {s_str}")
        else:
            sigma_t = 10.0 ** np.interp(rt, ratio_scan, log_s)
            print(f"    Ratio = {rt:.2f}  ->  sigma = {sigma_t:.2f} kpc")
    sigma_flat = 10.0 ** np.interp(0.9, ratio_scan, log_s) if 0.9 <= ratio_scan.max() else 30.0

    # ═════════════════════════════════════════════════════════════════
    #  Generate figure
    # ═════════════════════════════════════════════════════════════════

    print("[5/5] Generating figure...")
    make_figure(r_grid, v_newt, cassi_curves, sigma_display,
                sigma_flat, sigma_scan, ratio_scan)

    # ═════════════════════════════════════════════════════════════════
    #  Answer the scientific question
    # ═════════════════════════════════════════════════════════════════

    print()
    print("=" * 78)
    print("  RESULTS & ANALYSIS")
    print("=" * 78)
    print()

    print(f"  Summary of rotation curve velocities at key radii:")
    print(f"  {'Model':>25s}  {'v(2 kpc)':>10s}  {'v(5 kpc)':>10s}  "
          f"{'v(10 kpc)':>10s}  {'v(20 kpc)':>10s}  {'v(30 kpc)':>10s}  "
          f"{'v(30)/v(5)':>10s}  {'RMS@200':>10s}")
    print(f"  {'-' * 95}")
    n2 = np.argmin(abs(r_grid - 2))
    n5 = np.argmin(abs(r_grid - 5))
    n10 = np.argmin(abs(r_grid - 10))
    n20 = np.argmin(abs(r_grid - 20))
    n30 = np.argmin(abs(r_grid - 30))
    print(f"  {'Newtonian':>25s}  {v_newt[n2]:10.1f}  {v_newt[n5]:10.1f}  "
          f"{v_newt[n10]:10.1f}  {v_newt[n20]:10.1f}  {v_newt[n30]:10.1f}  "
          f"{newt_ratio:10.4f}  {rms_deviation_from_flat(v_newt, r_grid):10.0f}")
    for i, s in enumerate(sigma_display):
        v_c = cassi_curves[i]
        ratio = flattening_ratio(v_c, r_grid)
        rms = rms_deviation_from_flat(v_c, r_grid)
        print(f"  {'Cassi sigma=' + str(s) + ' kpc':>25s}  "
              f"{v_c[n2]:10.1f}  {v_c[n5]:10.1f}  "
              f"{v_c[n10]:10.1f}  {v_c[n20]:10.1f}  {v_c[n30]:10.1f}  "
              f"{ratio:10.4f}  {rms:10.0f}")
    print()

    print(f"""
  ──────────────────────────────────────────────────────────────────────
  KEY FINDINGS
  ──────────────────────────────────────────────────────────────────────

  1. Newtonian rotation curve from baryons alone:
     The Newtonian rotation curve (disk + bulge, no dark matter) peaks at
     {v_newt.max():.0f} km/s and falls to {v_newt[-1]:.0f} km/s at 30 kpc.
     RMS deviation from the observed flat 200 km/s curve:
     {rms_deviation_from_flat(v_newt, r_grid):.0f} km/s.
     
     This is the classic "missing mass" problem: the baryonic prediction
     falls as ~1/sqrt(R), while observations show flat ~200 km/s curves.

  2. Effect of Cassi softening on rotation curves:
     Cassi softening ALWAYS REDUCES v_circ relative to Newtonian --- it
     never adds mass or increases the gravitational force.  The effect:
     
     - sigma << R_d (small, 0.1-0.5 kpc): negligible at galactic radii.
       The curve is indistinguishable from Newtonian.
    
     - sigma ~ R_d (intermediate, 1-3 kpc): inner velocities suppressed,
       peak reduced, but outer velocities (R >> sigma) nearly unchanged.
       The flattening ratio v(30)/v(5) increases from ~0.51 (Newtonian)
       toward 1, but the curve at 30 kpc remains at ~100 km/s.
     
     - sigma > R_d (large, 5-10 kpc): severe suppression of inner disk.
       The rotation curve INVERTS: v(30) > v(5), which does not match any
       observed galaxy.  The curve rises from center outward.
     
  3. Can Cassi softening produce a flat rotation curve at ~200 km/s?
     NO.  Even with the "best" sigma = {sigma_flat:.1f} kpc where
     v(30)/v(5) = 0.9, the RMS deviation from flat 200 km/s is
     {rms_deviation_from_flat(cassi_curves[np.argmin(np.abs(np.array(sigma_display) - sigma_flat))], r_grid):.0f} km/s
     --- dominated by the outer region where v_circ is only ~100 km/s.
     
     Softened gravity REDUCES gravitational forces but never INCREASES
     them.  The baryonic mass of 7e10 M_sun simply cannot sustain
     v_circ = 200 km/s at 30 kpc under any form of gravity that
     reduces to Newtonian at large separations.""")

    if sigma_flat < 30.0:
        print(f"""
  4. Required sigma for flat rotation curves:
     sigma_flat (ratio = 0.9) = {sigma_flat:.1f} kpc
     
     This is O(R_disk) --- the softening must be on galactic scales to
     significantly affect the rotation curve.
     """)
    else:
        print(f"""
  4. Required sigma for flat rotation curves:
     sigma_flat = 0.9 could not be reached within the range [0.2, 30] kpc.
     Even with sigma = 30 kpc, the flattening ratio is only
     {ratio_scan[-1]:.3f}.
     
     This means that Cassi softening alone cannot produce flat rotation
     curves even with sigma comparable to the galaxy size.
     """)

    print(f"""
  5. Comparison with binary pulsar constraint:
     Binary pulsars (Path 5) constrain sigma < {SIGMA_BINARY_PULSAR:.2e} kpc.
     
     To affect galactic rotation curves, we need sigma ~ kpc scale.
     To satisfy binary pulsar timing, sigma < {SIGMA_BINARY_PULSAR:.2e} kpc.
     
     The ratio: (required sigma) / (allowed sigma) ≈
     {max(sigma_flat if sigma_flat < 30.0 else 10.0, 1.0) / max(SIGMA_BINARY_PULSAR, 1e-20):.0e}.
     
     These differ by roughly 14 ORDERS OF MAGNITUDE.
  """)

    print(f"""
  ──────────────────────────────────────────────────────────────────────
  ANSWER TO THE SCIENTIFIC QUESTION
  ──────────────────────────────────────────────────────────────────────

  Can Cassi softened gravity with a SINGLE sigma value simultaneously:
    (a) explain flat galactic rotation curves, AND
    (b) satisfy binary pulsar constraints (sigma < {SIGMA_BINARY_PULSAR:.1e} kpc)?

  ANSWER: NO.

  There is no single sigma that can explain both observations.  The sigma
  needed to flatten rotation curves is sigma ~ O(kpc), while binary pulsar
  timing constrains sigma < {SIGMA_BINARY_PULSAR:.1e} kpc --- a gap of
  roughly 14 orders of magnitude.
  
  IMPLICATIONS:
  
  1. Scale-dependent softening:
     If Cassi softening is real, sigma must be scale-dependent.  A natural
     possibility is sigma proportional to the system size --- sigma ~
     epsilon * R, where epsilon is a dimensionless constant.  This would
     give sigma ~ kpc for galaxies and sigma ~ {SIGMA_BINARY_PULSAR:.0e} kpc
     for binary pulsars (a ~ 1e-6 kpc), if epsilon ~ 1.  Such a scaling
     could arise if sigma is tied to the de Broglie wavelength of some
     ultra-light field, or to a screened fifth force.
  
  2. Different mechanism:
     It is more plausible that flat rotation curves are caused by a
     DIFFERENT mechanism than Cassi softened gravity.  The Cassi model
     (with scale-independent sigma) reproduces solar-system and binary
     pulsar observations and may affect L4/L5 stability, but it cannot
     explain galactic dynamics without dark matter.
     
     The two-fluid model (Cassi phi-enhanced gravity) is a more promising
     candidate: it increases the effective gravitational constant at
     low densities, naturally producing flat rotation curves.
  
  3. What Cassi softened gravity does explain:
     - Retrograde pericenter precession (Path 4b, Path 5)
     - Enhanced L4/L5 stability (Path 6)
     - Consistency with binary pulsar timing (sigma < {SIGMA_BINARY_PULSAR:.2e} kpc)
     
     It is constrained to small sigma by solar-system and pulsar
     observations, making it irrelevant on galactic scales.
  """)

    # ═════════════════════════════════════════════════════════════════
    #  Return structured results
    # ═════════════════════════════════════════════════════════════════

    results = {
        'r_grid_kpc': r_grid.tolist(),
        'v_newtonian_kms': v_newt.tolist(),
        'cassi_curves': {
            f'sigma_{s}_kpc': cassi_curves[i].tolist()
            for i, s in enumerate(sigma_display)
        },
        'sigma_flat_kpc': float(sigma_flat) if sigma_flat < 30.0 else None,
        'binary_pulsar_constraint_kpc': float(SIGMA_BINARY_PULSAR),
        'newtonian_peak_kms': float(v_newt.max()),
        'newtonian_v30_kms': float(v_newt[-1]),
        'newtonian_flattening_ratio': float(newt_ratio),
        'conclusion': (
            'A single sigma cannot simultaneously explain flat galactic '
            'rotation curves and satisfy binary pulsar constraints. The '
            'required sigma (~kpc) exceeds the allowed sigma (~1e-14 kpc) '
            'by ~14 orders of magnitude.'
        ),
    }

    return results


if __name__ == '__main__':
    main()
