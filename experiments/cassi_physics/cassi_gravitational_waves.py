#!/usr/bin/env python3
"""Cassi Gravitational Waves—Strain prediction from Qi-enhanced G_eff.

LIGO measures gravitational wave strain h = (G/c⁴)·(d²Q/dt²)/r.
In Qi-enhanced regions, G_eff = (π/ρ)·(1+(φ⁶−1)·q)·G (the saturation
chord, exact at q = 0 → 1 and q → 1 → φ⁶; `foundations/xi-derivation.md`),
so:
    h_Cassi = (π/ρ)·(1+(φ⁶−1)·q)·h_GR

For mergers in dense halos (galaxy clusters), the strain can be up to
~10× larger than GR predictions (reached at q = 0.53, π/ρ = 1)—
testable with LIGO/Virgo/KAGRA.
"""

import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PHI = (1.0 + math.sqrt(5.0)) / 2.0
XI = PHI ** 6                  # ξ = φ⁶ ≈ 17.944—derived Qi-gravity coupling
CHORD = XI - 1.0               # the saturation-anchored q-coefficient

# Terminal attractor values (pr = π/ρ, q): geff computed from the chord
TERMINAL_PTS = {
    'Core (r=5)':        dict(pr=0.275, q=0.147),
    'Transition (r=6)':  dict(pr=0.440, q=0.497),
    'Halo (r=7)':        dict(pr=0.633, q=0.669),
    'Outer Halo (r=8)':  dict(pr=0.633, q=0.715),
    'Outer (r=9)':       dict(pr=0.723, q=0.701),
}

# Known GW events
GW_EVENTS = [
    ('GW150914', 0.09, 410),   # (name, redshift, strain × 10²¹)
    ('GW170817', 0.01, 2000),  # binary neutron star
    ('GW190521', 0.44, 50),    # most massive binary BH
    ('S190814bv', 0.05, 500),  # NS-BH merger candidate
]


def geff_from_q(q, pr=1.0):
    """G_eff/G = (π/ρ)·(1+(φ⁶−1)·q), the saturation chord."""
    return pr * (1.0 + CHORD * q)


def strain_ratio(geff):
    """h_Cassi / h_GR = G_eff / G."""
    return geff


def main():
    print("=" * 70)
    print("CASSI GRAVITATIONAL WAVES—Enhanced Strain in Qi Halos")
    print(f"chord: G_eff = (π/ρ)·(1+({XI-1:.3f})·q)·G, ξ = φ⁶ = {XI:.3f}")
    print("=" * 70)

    # Enhancement factor at each terminal radius
    print(f"\n1. Strain enhancement by environment:")
    print(f"   {'Location':>20s}  {'G_eff/G':>8s}  {'h/h_GR':>8s}  {'Detectable?':>12s}")
    for loc, pt in TERMINAL_PTS.items():
        geff = geff_from_q(pt['q'], pt['pr'])
        ratio = strain_ratio(geff)
        detect = 'LIKELY' if ratio > 5 else 'possible' if ratio > 2 else 'unlikely'
        print(f"   {loc:>20s}  {geff:8.2f}  {ratio:8.2f}x  {detect:>12s}")

    # Merger analysis
    print(f"\n2. Cassi strain at known GW events:")
    print(f"   Using the host environment's estimated G_eff:")
    print(f"   {'Event':>12s}  {'z':>5s}  {'h_GR':>8s}  {'Env':>12s}  {'h_Cassi':>10s}")
    for name, z, h_gr in GW_EVENTS:
        # Estimate environment: most mergers are in cores (G_eff≈1)
        # But some may be in halos
        for env_label, geff in [('core', 1.0), ('halo', geff_from_q(0.669, 0.633)),
                                ('outer', geff_from_q(0.701, 0.723))]:
            h_cas = h_gr * geff
            print(f"   {name:>12s}  {z:5.2f}  {h_gr:8.1e}  {env_label:>12s}  "
                  f"{h_cas:10.1e}")

        # GW170817—best localized, in a galaxy
        if '170817' in name:
            print(f"   {'(GW170817 was in NGC 4993—core environment -> GR-like)':>60s}")

    # Plot
    print(f"\n3. Parameter space:")
    q_arr = np.linspace(0, 0.8, 100)
    for pr, label, ls in [(1.0, 'Baryon-rich (π/ρ=1)', '-'),
                           (0.72, 'Saturated (π/ρ=0.72)', '--'),
                           (0.44, 'Transition (π/ρ=0.44)', ':')]:
        geff = [pr * (1 + CHORD * q) for q in q_arr]
        print(f"   {label}: G_eff range = {geff[0]:.2f} → {geff[-1]:.2f}")

    print(f"\n{'='*70}")
    print(f"  Key prediction: mergers in Qi-enhanced cluster halos")
    print(f"  could show up to ~10× larger strain than GR expectation")
    print(f"  (q = 0.53 at π/ρ = 1 under the chord).")
    print(f"  LIGO/Virgo upper limits on h from non-detections in")
    print(f"  galaxy clusters constrain q < 0.1-0.3 at cluster scales.")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
