#!/usr/bin/env python3
"""Cassi Lighthouse Pulsar—Cascade Placements for PSR J1101-6101.

Reproduces the rung placements in `demystifying-the-cosmos/PSR-J1101-6101.md`
§6: n = log_phi(x / x_Pl) for the neutron-star mass, radius, spin period,
and light-cylinder radius, with the verification block.

Usage
-----
    python experiments/demystifying_cosmos/pulsar_lighthouse_placements.py

Outputs
-------
    Table of rung placements + verification:
      - mass rung matches the repo's Chandrasekhar row (182.3, gwtc4 §2)
      - radius sits one rung above the rung-185 anchor (Everest 8.8 km)
      - light cylinder within 0.10 rungs of the half-rung 197.5
"""

import math

PHI = (1.0 + math.sqrt(5.0)) / 2.0
LNPHI = math.log(PHI)

T_PL = 5.391e-44   # s
L_PL = 1.616e-35   # m
M_PL = 2.176e-8    # kg
MSUN = 1.989e30    # kg
C = 2.998e8        # m/s


def rung(x_over_planck):
    """n = log_phi(x / x_Pl): cascade rung of a quantity above its Planck unit."""
    return math.log(x_over_planck) / LNPHI


def main():
    freq = 16.0                     # Hz (article)
    P = 1.0 / freq                  # spin period
    m_ns = 1.4 * MSUN              # Chandrasekhar-mass neutron star
    r_ns = 1.2e4                    # ~12 km radius
    r_lc = C * P / (2.0 * math.pi)  # light-cylinder radius

    n_mass = rung(m_ns / M_PL)
    n_rad = rung(r_ns / L_PL)
    n_period = rung(P / T_PL)
    n_lc = rung(r_lc / L_PL)

    print("=" * 68)
    print("CASSI LIGHTHOUSE PULSAR—RUNG PLACEMENTS (PSR J1101-6101)")
    print("=" * 68)
    print(f"\n  {'Quantity':<28s}{'Value':>12s}{'Rung n':>10s}")
    print(f"  {'NS mass (1.4 M_sun)':<28s}{m_ns:>12.3e}{n_mass:>10.3f}")
    print(f"  {'NS radius (~12 km)':<28s}{r_ns:>12.3e}{n_rad:>10.3f}")
    print(f"  {'Spin period (16 Hz)':<28s}{P:>12.3e}{n_period:>10.3f}")
    print(f"  {'Light-cylinder radius':<28s}{r_lc:>12.3e}{n_lc:>10.3f}")

    print("\nVerification:")
    print(f"  mass rung {n_mass:.3f} vs repo Chandrasekhar row 182.3  -> "
          f"|d| = {abs(n_mass - 182.3):.3f} rungs")
    print(f"  radius rung {n_rad:.3f} vs rung-185 anchor (Everest)    -> "
          f"above by {n_rad - 185.0:.3f} rungs")
    print(f"  light cylinder {n_lc:.3f} vs half-rung 197.5            -> "
          f"|d| = {abs(n_lc - 197.5):.3f} rungs "
          f"({'PASS' if abs(n_lc - 197.5) < 0.10 else 'INFO'})")

    checks = [
        abs(n_mass - 182.3) < 0.05,
        abs(n_rad - 186.0) < 0.10,
        abs(n_period - 201.3) < 0.10,
    ]
    status = all(checks)
    print(f"\n  All placement checks: {'PASS' if status else 'FAIL'}")
    print("  (placements are observations, not framework predictions;\n"
          "   gwtc4 marks the 182-194 zone ladder Hypothesized, disfavored)")
    return 0 if status else 1


if __name__ == "__main__":
    raise SystemExit(main())
