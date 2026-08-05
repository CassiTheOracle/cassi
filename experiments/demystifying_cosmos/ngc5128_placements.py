#!/usr/bin/env python3
"""Cassi Centaurus A—Cascade Placements for NGC 5128.

Reproduces the rung placements in `demystifying-the-cosmos/NGC-5128.md` §7
(distance, dust-band scale, merger timescale) and carries the two falsifiable
test helpers from §8: the phi-spacing radial-ring test (T1) and the 1.70x
edge-anisotropy constant (T2).

Usage
-----
    python experiments/demystifying_cosmos/ngc5128_placements.py

Outputs
-------
    Table of rung placements + verification:
      - distance rung sits 8.4 rungs below the Cassi bubble (285)
      - merger timescale sits 4.1 rungs below the horizon rung (291.54)
      - T1: phi-spaced peak ratios pass on the synthetic demo profile
      - T2: edge anisotropy sqrt(4*phi^2/(1+phi^2)) = 1.7013
"""

import math

PHI = (1.0 + math.sqrt(5.0)) / 2.0
LNPHI = math.log(PHI)

T_PL = 5.391e-44   # s
L_PL = 1.616e-35   # m
LY = 9.4607e15     # m
PC = 3.0857e16     # m
YR = 3.15576e7     # s

# Framework anchors
RUNG_BUBBLE = 285.0     # Cassi bubble (5 x 57 closure)
RUNG_HORIZON = 291.54   # today's horizon rung (wake-geometry §4)


def rung(x_over_planck):
    """n = log_phi(x / x_Pl): cascade rung of a quantity above its Planck unit."""
    return math.log(x_over_planck) / LNPHI


def phi_peak_ratios(radii):
    """T1: consecutive peak ratios vs phi. Returns list of (ratio, |ratio-phi|)."""
    out = []
    for a, b in zip(radii[:-1], radii[1:]):
        r = b / a
        out.append((r, abs(r - PHI)))
    return out


def main():
    d_cena = 11.0e6 * LY          # article: 11 Mly
    t_merger = 2.0e9 * YR         # article: ~2 Gyr ago
    band_scale = 3.0e3 * PC       # dust band ~ kpc scale

    n_dist = rung(d_cena / L_PL)
    n_band = rung(band_scale / L_PL)
    n_merger = rung(t_merger / T_PL)

    print("=" * 68)
    print("CASSI CENTAURUS A—RUNG PLACEMENTS (NGC 5128)")
    print("=" * 68)
    print(f"\n  {'Quantity':<28s}{'Value':>12s}{'Rung n':>10s}")
    print(f"  {'Distance (11 Mly)':<28s}{d_cena:>12.3e}{n_dist:>10.3f}")
    print(f"  {'Dust band (~3 kpc)':<28s}{band_scale:>12.3e}{n_band:>10.3f}")
    print(f"  {'Merger timescale (2 Gyr)':<28s}{t_merger:>12.3e}{n_merger:>10.3f}")

    print("\nVerification:")
    print(f"  distance {n_dist:.3f} vs bubble rung {RUNG_BUBBLE:.0f}      -> "
          f"{n_dist - RUNG_BUBBLE:.1f} rungs (expect -8.4)")
    print(f"  merger {n_merger:.3f} vs horizon {RUNG_HORIZON:.2f}     -> "
          f"{RUNG_HORIZON - n_merger:.2f} rungs below (expect ~4.1)")

    # T1 demo: phi-spaced synthetic peaks
    demo = [1.0 * PHI**k for k in range(5)]
    ratios = phi_peak_ratios(demo)
    t1_ok = all(d < 1e-9 for _, d in ratios)
    print(f"\n  T1 (phi-spaced wake rings): synthetic phi-lattice peaks -> "
          f"ratios {[round(r, 4) for r, _ in ratios]} -> "
          f"{'PASS' if t1_ok else 'FAIL'}")
    print(f"     test recipe: radial MIRI profile, find peaks, compare "
          f"consecutive radii to phi")

    # T2 constant
    aniso = math.sqrt(4.0 * PHI**2 / (1.0 + PHI**2))
    t2_ok = abs(aniso - 1.70) < 0.01
    print(f"\n  T2 (edge anisotropy): sqrt(4*phi^2/(1+phi^2)) = {aniso:.4f} "
          f"-> {'PASS' if t2_ok else 'FAIL'} (prediction 38)")

    checks = [
        abs((n_dist - RUNG_BUBBLE) - (-8.4)) < 0.1,
        abs((RUNG_HORIZON - n_merger) - 4.1) < 0.1,
        t1_ok,
        t2_ok,
    ]
    status = all(checks)
    print(f"\n  All placement checks: {'PASS' if status else 'FAIL'}")
    print("  (placements are observations, not framework predictions)")
    return 0 if status else 1


if __name__ == "__main__":
    raise SystemExit(main())
