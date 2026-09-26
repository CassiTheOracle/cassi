#!/usr/bin/env python3
"""
Cassi Nuclear—Exploratory Force and Binding Model.

This exploratory model applies a softened force at an assigned nuclear scale.
It does not derive a physical nuclear interaction or validate decay channels.

The assigned fm-scale width, attractive kernel, and binding coefficients are
toy inputs. No gravity-to-strong-interaction identification, physical soliton
nucleus, isotope fit, decay mechanism, neutron-star model, or QGP prediction
is established here. The physical particle and interaction requirements are
listed in foundations/quantum-free-fall-correspondence.md section 11.1.
"""

import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_INV = 1.0 / PHI
XI = PHI ** 6                  # Assigned toy coupling; no nuclear matching

# Nuclear scale
SIGMA_NUCLEAR = 0.5  # fm (femtometers)
M_NUCLEON = 938.272  # MeV/c²


def cassi_force_nuclear(r, sigma=SIGMA_NUCLEAR, xi=XI):
    """Toy attractive kernel with s = r / (sigma * sqrt(2)).

    F(r) = -xi * [erf(s) - sqrt(2/pi) * s * exp(-s*s)] / r**2.
    This expression is not a derived physical nuclear interaction.
    """
    if r < 1e-10:
        return 0.0
    s = r / (sigma * math.sqrt(2.0))
    soft = math.erf(s) - math.sqrt(2.0/math.pi) * s * math.exp(-s*s)
    return -xi * soft / (r * r)


def nuclear_potential(r, sigma=SIGMA_NUCLEAR, xi=XI):
    """Integrate the toy kernel to the supplied numerical cutoff."""
    from scipy.integrate import quad
    V, _ = quad(lambda s: cassi_force_nuclear(s + 1e-10, sigma, xi), r, 100, limit=200)
    return V


def nuclear_binding_energy(A, Z, sigma=SIGMA_NUCLEAR, xi=XI):
    """Return an uncalibrated mass-formula analogue and its value per A.

    The coefficients are assigned model inputs, with the volume term scaled
    by the toy potential at r = sigma. No isotope fit is established here.
    """
    # Toy potential magnitude at the assigned width
    V_well = abs(nuclear_potential(sigma, sigma, xi))
    
    # Volume energy (dominant term)
    a_v = V_well * 0.1  # Assigned toy scale
    B_volume = a_v * A
    
    # Surface term (nucleons at surface feel less binding)
    B_surface = -a_v * A**(2/3) * 0.5
    
    # Coulomb term (protons repel)
    B_coulomb = -0.0007 * Z * (Z - 1) / A**(1/3)
    
    # Asymmetry term (neutron-proton imbalance)
    B_asym = -0.023 * (A - 2*Z)**2 / A
    
    B_total = B_volume + B_surface + B_coulomb + B_asym
    
    return B_total, B_total/A


def binding_energy_per_nucleon(A, Z):
    """Return the toy binding analogue per A, without isotope calibration."""
    B, B_per_A = nuclear_binding_energy(A, Z)
    return B_per_A


def main():
    print("=" * 65)
    print("CASSI NUCLEAR—Exploratory Force and Binding Model")
    print("=" * 65)
    print("Exploratory toy model; no physical nuclear or decay closure is derived.")
    
    print(f"\n  σ_nuclear = {SIGMA_NUCLEAR} fm")
    print(f"  σ_gravity ≈ 1 kpc")
    print(f"  Ratio: σ_grav/σ_nuclear = {1e3 * 3.086e19 / 1e-15:.1e}")
    print("  Assigned scale comparison; no interaction unification is derived.")
    
    # Force comparison
    print("\n1. Force comparison at different scales:")
    for r in [0.01, 0.1, 0.5, 1.0, 2.0, 5.0]:
        F_nuc = cassi_force_nuclear(r)
        # At nuclear scale, Coulomb force for two protons
        F_coul = 1.44 / r**2  # MeV/fm for two protons
        ratio = abs(F_nuc / F_coul) if F_coul != 0 else float('inf')
        print(f"  r = {r:.2f} fm:  F_Cassi = {F_nuc:+.2e}  F_Coulomb = {F_coul:+.2e}  ratio = {ratio:.1f}")
    
    # Potential well
    print("\n2. Nuclear potential well:")
    for r in [0.01, 0.1, 0.5, 1.0, 2.0]:
        V = nuclear_potential(r)
        print(f"  r = {r:.2f} fm:  V(r) = {V:.3f}")
    
    # Binding energy curve
    print("\n3. Toy binding-energy analogue (uncalibrated model units):")
    print(f"  {'A':>4s}  {'Z':>3s}  {'Element':>6s}  {'B/A':>10s}")
    nuclei = [
        (2, 1, '²H'),
        (4, 2, '⁴He'),
        (12, 6, '¹²C'),
        (16, 8, '¹⁶O'),
        (56, 26, '⁵⁶Fe'),
        (100, 42, 'Mo'),
        (200, 80, 'Hg'),
        (238, 92, '²³⁸U'),
    ]
    for A, Z, name in nuclei:
        B_per_A = binding_energy_per_nucleon(A, Z)
        print(f"  {A:4d}  {Z:3d}  {name:>6s}  {B_per_A:10.2f}")
    
    print("\n4. Physical scope:")
    print("  No nuclear spectra, decay amplitudes or lifetimes are computed.")
    print("  Beta decay requires a weak charge-changing sector; canonical q is nonnegative.")
    print("  Physical particle and interaction requirements:")
    print("  foundations/quantum-free-fall-correspondence.md section 11.1.")
    
    print("\n" + "=" * 65)


if __name__ == '__main__':
    main()
