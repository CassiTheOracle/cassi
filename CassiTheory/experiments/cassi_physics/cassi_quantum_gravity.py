#!/usr/bin/env python3
"""Plot the registered free-propagator and dispersion diagnostics.

This script evaluates two declared, conditional objects from
``gravity/quantum-gravity.md``:

* the normalized Euclidean propagator damping ``k² G_E = exp(-(kσ)²/2)``;
* the Hypothesized dispersion
  ``ω² = k² + ω₀² (1 - exp(-(kσ)²))``.

It also integrates the displayed radial one-loop prototype with an explicit
nonzero infrared cutoff. The calculation demonstrates ultraviolet convergence
of that prototype only. It supplies no interacting vertices, all-loop
renormalization result, Lorentzian unitarity proof, or physical graviton
identification.
"""

import math

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PHI = (1.0 + math.sqrt(5.0)) / 2.0
M_PL = 1.22e19  # GeV
SIGMA = 1.0 / (PHI**3 * M_PL)  # GeV^-1
MU = M_PL * SIGMA  # ω₀σ = φ^-3


def propagator_damping(x):
    """Return the dimensionless ratio k² G_E for x = kσ."""
    x = np.asarray(x, dtype=float)
    return np.exp(-0.5 * x * x)


def radial_loop_prototype(x_ir, *, x_max=20.0, samples=20_000):
    """Integrate exp(-x²)/x /(8π²) from a positive IR cutoff.

    The dimensionless variable is x = qσ. The upper tail beyond ``x_max=20``
    is negligible in double precision. The integral diverges logarithmically
    as ``x_ir`` approaches zero.
    """
    if not 0.0 < x_ir < x_max:
        raise ValueError("require 0 < x_ir < x_max")
    x = np.geomspace(x_ir, x_max, samples)
    return np.trapezoid(np.exp(-x * x) / x, x) / (8.0 * math.pi**2)


def dispersion_ratios(x):
    """Return ω/k and dω/dk for the registered Hypothesized dispersion."""
    x = np.asarray(x, dtype=float)
    if np.any(x <= 0.0):
        raise ValueError("x must be positive")
    one_minus_exp = -np.expm1(-x * x)
    phase = np.sqrt(1.0 + MU * MU * one_minus_exp / (x * x))
    group = (1.0 + MU * MU * np.exp(-x * x)) / phase
    return phase, group


def main():
    print("=" * 72)
    print("CASSI FREE-PROPAGATOR DIAGNOSTIC—CONDITIONAL OBJECTS")
    print("=" * 72)
    print(f"σ = ℓ_Pl/φ³ = {SIGMA:.6e} GeV⁻¹")
    print(f"1/σ = φ³ M_Pl = {1.0 / SIGMA:.6e} GeV")
    print(f"μ = ω₀σ = φ⁻³ = {MU:.12f}")

    sample_x = np.array([1.0e-3, 0.1, 1.0, 3.0, 10.0])

    print("\n1. Normalized Euclidean propagator damping, k²G_E:")
    for x, damping in zip(sample_x, propagator_damping(sample_x)):
        print(f"  kσ = {x:8.3g}: exp[-(kσ)²/2] = {damping:.12e}")

    print("\n2. Radial one-loop prototype with explicit IR cutoff:")
    for x_ir in [1.0e-1, 1.0e-2, 1.0e-3, 1.0e-4]:
        value = radial_loop_prototype(x_ir)
        print(f"  x_IR = {x_ir:8.1e}: I = {value:.12e}")
    print("  Each nonzero-cutoff value is UV convergent.")
    print("  Growth as x_IR decreases records the logarithmic IR divergence.")
    print("  This prototype does not establish all-loop renormalizability.")

    print("\n3. Hypothesized mode dispersion:")
    phase, group = dispersion_ratios(sample_x)
    for x, phase_ratio, group_ratio in zip(sample_x, phase, group):
        print(
            f"  kσ = {x:8.3g}: ω/k = {phase_ratio:.12f}, "
            f"dω/dk = {group_ratio:.12f}"
        )
    print("  At high k, ω/k and dω/dk approach 1; there is no energy cap.")
    print(
        "  At low k, the 2.75% speed excess is rejected for an "
        "astrophysical graviton by GW170817."
    )

    print("\n4. Generating dimensionless diagnostic plots...")
    x = np.geomspace(1.0e-4, 20.0, 500)
    damping = propagator_damping(x)
    phase, group = dispersion_ratios(x)
    loop_integrand = np.exp(-x * x) / x / (8.0 * math.pi**2)
    x_ir = np.geomspace(1.0e-4, 1.0, 160)
    loop_values = np.array(
        [radial_loop_prototype(cutoff, samples=4_000) for cutoff in x_ir]
    )

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))

    ax = axes[0, 0]
    ax.loglog(x, damping, linewidth=2)
    ax.axvline(1.0, color="black", linestyle="--", alpha=0.5)
    ax.set_xlabel(r"$x=k\sigma$")
    ax.set_ylabel(r"$k^2G_E=e^{-x^2/2}$")
    ax.set_title("Euclidean free-propagator damping")
    ax.grid(True, alpha=0.3)

    ax = axes[0, 1]
    ax.semilogx(x, phase, label=r"$\omega/k$", linewidth=2)
    ax.semilogx(x, group, label=r"$d\omega/dk$", linewidth=2)
    ax.axhline(1.0, color="black", linestyle="--", alpha=0.5)
    ax.set_xlabel(r"$x=k\sigma$")
    ax.set_ylabel("ratio")
    ax.set_title("Hypothesized dispersion ratios")
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[1, 0]
    ax.loglog(x, loop_integrand, linewidth=2)
    ax.axvline(1.0, color="black", linestyle="--", alpha=0.5)
    ax.set_xlabel(r"$x=q\sigma$")
    ax.set_ylabel(r"$e^{-x^2}/(8\pi^2x)$")
    ax.set_title("Displayed radial loop integrand")
    ax.grid(True, alpha=0.3)

    ax = axes[1, 1]
    ax.semilogx(x_ir, loop_values, linewidth=2)
    ax.invert_xaxis()
    ax.set_xlabel(r"infrared cutoff $x_{\rm IR}$")
    ax.set_ylabel(r"$I(x_{\rm IR})$")
    ax.set_title("Finite at fixed cutoff; IR-divergent as cutoff vanishes")
    ax.grid(True, alpha=0.3)

    fig.suptitle("Cassi conditional free-propagator diagnostics", fontsize=13)
    fig.tight_layout()
    fig.savefig("cassi_quantum_gravity.png", dpi=150)
    plt.close(fig)
    print("  Saved: cassi_quantum_gravity.png")

    print("\n" + "=" * 72)
    print("STATUS BOUNDARY")
    print("=" * 72)
    print("  • The Gaussian suppresses the declared Euclidean free propagator.")
    print("  • The displayed radial prototype is UV convergent for x_IR > 0.")
    print("  • The uncut prototype remains logarithmically IR divergent.")
    print("  • Interacting and all-loop conclusions require specified vertices.")
    print("  • Lorentzian causality and unitarity remain open.")
    print("  • The composite-graviton identification remains Hypothesized.")
    print("  • The implemented low-k dispersion is rejected for observed GWs.")


if __name__ == "__main__":
    main()
