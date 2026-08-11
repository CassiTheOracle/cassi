#!/usr/bin/env python3
"""
Weinberg Angle: the φ⁻³ Coupling-Ratio Identity
================================================

Verifies the exact algebraic content of the boundary condition
sin²θ_W = φ⁻³ and the failure of the VEV-asymmetry rotation that
`standard-model/su2-gauge-extension.md` §3.2 previously invoked.

The equivalence chain (all exact, φ = (1+√5)/2):
    sin²θ_W = φ⁻³  ⟺  tan²θ_W = φ⁻³/(1−φ⁻³) = 1/(φ³−1) = 1/(2φ)
                 ⟺  (g/g')² = 2φ
using φ³ − 1 = 2φ (from φ³ = 2φ + 1) and the equivalent forms
φ⁻³ = 1/(1+2φ) = (φ−1)/(φ+1).

The neutral mass matrix from |D_μ⟨Ψ⟩|² (dividing out v²/4) is

    M² = (v²/4) [[g², 2κgg'], [2κgg', g'²]],  κ = (φ−1)/(φ+1) = φ⁻³.

Checks:
  1. massless photon requires det M² = 0, i.e. κ = 1/2 — fails (κ = 0.236);
  2. diagonalizing at the framework's own g'/g = 0.556 gives a Z-like
     eigenvector with sin²θ ≈ 0.10, not 0.236;
  3. the eigen-angle equals tan²θ = 1/(2φ) only for g'/g ≈ 0.749,
     incompatible with the 0.556 the boundary condition itself implies;
  4. measured g'/g = √(sin²θ_W(m_Z)/(1−sin²θ_W(m_Z))) = 0.5484 vs the
     φ-value 0.5559 (+1.36%).

Usage: python computations/weinberg_phi_identity.py
"""

import numpy as np
from numpy.linalg import eigh

PHI = (1 + np.sqrt(5)) / 2
S2_ZPOLE = 0.23122          # MS-bar measured sin²θ_W(m_Z), PDG-style anchor


def check(label, cond, detail=""):
    print(f"  [{'OK' if cond else 'FAIL'}] {label} {detail}")


print("φ = %.8f\n" % PHI)

print("Equivalence chain (sin²θ_W = φ⁻³ ⟺ tan²θ_W = 1/(2φ) ⟺ (g/g')² = 2φ):")
s2 = PHI**-3
t2 = s2 / (1 - s2)
check("sin²θ_W = φ⁻³ = %.6f" % s2, np.isclose(s2, 0.236067978))
check("tan²θ_W = 1/(2φ) = %.8f" % t2, np.isclose(t2, 1 / (2 * PHI)))
check("tan²θ_W = φ⁻¹/2 = %.8f" % (PHI**-1 / 2), np.isclose(t2, PHI**-1 / 2))
check("1/(φ³−1) = %.8f = 1/(2φ)" % (1 / (PHI**3 - 1)),
      np.isclose(1 / (PHI**3 - 1), 1 / (2 * PHI)))
check("φ³−1 = 2φ = %.8f" % (PHI**3 - 1), np.isclose(PHI**3 - 1, 2 * PHI))
check("φ⁻³ = 1/(1+2φ) = %.8f" % (1 / (1 + 2 * PHI)), np.isclose(s2, 1 / (1 + 2 * PHI)))
check("φ⁻³ = (φ−1)/(φ+1) = %.8f" % ((PHI - 1) / (PHI + 1)),
      np.isclose(s2, (PHI - 1) / (PHI + 1)))
check("unified-Lagrangian assignment (1−φ⁻³)/φ⁻³ = 2φ = %.6f"
      % ((1 - s2) / s2), np.isclose((1 - s2) / s2, 2 * PHI))
gp = np.sqrt(1 / (2 * PHI))
print("  → g'/g = √(1/(2φ)) = %.5f" % gp)

print("\nMeasured comparison (Z-pole):")
gp_meas = np.sqrt(S2_ZPOLE / (1 - S2_ZPOLE))
check("g'/g(m_Z) = %.5f  vs φ-value %.5f: +%.2f%%"
      % (gp_meas, gp, 100 * (gp / gp_meas - 1)),
      np.isclose(100 * (gp / gp_meas - 1), 1.36, atol=0.01))
check("sin²θ offset: %.2f%% above 0.23122" % (100 * (s2 / S2_ZPOLE - 1)),
      np.isclose(100 * (s2 / S2_ZPOLE - 1), 2.10, atol=0.01))

print("\nMass matrix (v²/4 units): M² = [[g², 2κgg'],[2κgg', g'²]], κ = (φ−1)/(φ+1):")
k = (PHI - 1) / (PHI + 1)
t = gp                       # framework's own g'/g implied by sin²θ_W = φ⁻³
M = np.array([[1.0, 2 * k * t], [2 * k * t, t * t]])
w, V = eigh(M)
check("κ = φ⁻³ = %.6f ≠ 1/2 → det M² ≠ 0 (photon massive)" % k,
      not np.isclose(4 * k * k, 1.0))
check("light eigenvalue %.4f·g²v²/4 > 0 (no massless photon)" % w[0], w[0] > 0)
x = V[1, 1] / V[0, 1]        # heavy (Z-like) eigenvector slope
th = np.arctan(x)
check("Z-like eigenvector at sin²θ = %.3f (not 0.236)" % np.sin(th)**2,
      np.isclose(np.sin(th)**2, 0.10, atol=0.01))
# eigen-angle equals the target tan²θ = 1/(2φ) only when tan(2θ) = 4κt/(1−t²)
# is solved for t with κ fixed:
tan2t = 2 * np.sqrt(t2) / (1 - t2)
roots = np.roots([tan2t, 4 * k, -tan2t])
t_target = roots[(roots > 0) & (np.isreal(roots))][0].real
check("eigen-angle = target needs g'/g = %.3f ≠ 0.556" % t_target,
      not np.isclose(t_target, t, atol=0.05))
print("  (the VEV asymmetry sets the off-diagonal coefficient; it cannot set")
print("   the angle, which is fixed by the diagonal ratio g'²/(g²+g'²))")

print("\nAll checks are algebraic identities (φ-algebra) or linear algebra on the")
print("doc's own matrix; the boundary condition itself remains asserted (§3.2).")
