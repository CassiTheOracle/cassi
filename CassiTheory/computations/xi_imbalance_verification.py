#!/usr/bin/env python3
"""
Xi Imbalance Inverse-Square: Verification
==========================================

Verifies the derivation of the Qi-gravity coupling xi = phi^6 as the
inverse-square of the fixed-point imbalance (foundations/xi-derivation.md §2):

    alpha_0 = pi/rho = (phi - 1)/(phi + 1) = phi^-3     (attractor fixed point)
    xi      = phi^6   = alpha_0^-2 = (phi^-3)^-2        (quadratic coupling input)

Consistency checks:
  (i)   saturation ceiling G_eff,max/G = alpha_0 * xi = phi^3 = 4.236067978
        (dwarf-spheroidal M/L ceiling, audit.md §3)
  (ii)  empirical pin xi vs 18: 0.31% residual (Calibrated, ledger row 498)
  (iii) sin^2(theta_W) = 1/(1 + 2*phi) = phi^-3  (Weinberg angle = same
        imbalance; 1 + 2*phi = phi^3)
  (iv)  alpha_GUT = phi^-3/(4*pi) ~ 1/53
  (v)   emotions gate ladder base: b_i = phi^-(2+i) = phi^-2 * phi^-i
        (consciousness/emotions-as-gate-configurations.md §2.2)
  (vi)  MW halo boost at q = 0.67: 1 + (phi^6 - 1)*0.67 = 12.3527

Usage: python computations/xi_imbalance_verification.py
"""

import numpy as np

PHI = (1 + np.sqrt(5)) / 2

alpha = (PHI - 1) / (PHI + 1)          # fixed-point imbalance pi/rho
xi = PHI**6

print("alpha_0 = (phi-1)/(phi+1) =", repr(alpha))
print("phi^-3                    =", repr(PHI**-3))
print("exact identity:           ", np.isclose(alpha, PHI**-3, rtol=1e-15))
print()
print("xi = phi^6                =", repr(xi))
print("alpha_0^-2                =", repr(alpha**-2))
print("exact identity:           ", np.isclose(xi, alpha**-2, rtol=1e-15))
print()
print("(i)   G_eff,max/G = alpha_0*xi = phi^3 =", repr(PHI**3),
      " (dwarf M/L ceiling 4.2361)")
print("(ii)  xi vs empirical pin 18: residual =", repr((18 - xi) / 18))
print("(iii) sin^2(theta_W) = 1/(1+2*phi) =", repr(1 / (1 + 2 * PHI)),
      "; 1+2*phi == phi^3:", np.isclose(1 + 2 * PHI, PHI**3, rtol=1e-15))
print("(iv)  alpha_GUT = phi^-3/(4*pi) =", repr(PHI**-3 / (4 * np.pi)),
      " ~ 1/", round(4 * np.pi / PHI**-3, 2), sep="")
ladder = [PHI ** (-(2 + i)) for i in range(1, 6)]
print("(v)   b_i = phi^-(2+i):", ["%.6f" % b for b in ladder],
      "; base phi^-2 =", repr(PHI**-2),
      "; exact b_i == phi^-2*phi^-i:",
      [bool(np.isclose(b, PHI**-2 * PHI**-i, rtol=1e-15))
       for i, b in enumerate(ladder, start=1)])
print("(vi)  MW boost(0.67) = 1 + (phi^6-1)*0.67 =", repr(1 + (xi - 1) * 0.67))
