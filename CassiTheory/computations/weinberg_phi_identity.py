#!/usr/bin/env python3
r"""
Weinberg Angle: the φ⁻³ Coupling-Ratio Identity
================================================

Verifies the exact algebraic content of the asserted boundary condition
$\sin^2\theta_W = \varphi^{-3}$ and the full gauge-boson mass matrix for the
fixed-point VEV $\langle\Psi\rangle \propto (\sqrt{\varphi},1)^T$.

The equivalence chain (all exact, $\varphi = (1+\sqrt{5})/2$):
    $\sin^2\theta_W = \varphi^{-3}$  iff  $\tan^2\theta_W = 1/(2\varphi)$
                                 iff  $(g/g')^2 = 2\varphi$.

For $T_a = \sigma_a/2$, $Y=I/2$, define

    a = 2\sqrt{\varphi}/(\varphi+1),  kappa = (\varphi−1)/(\varphi+1) = \varphi^{-3}.

The complete matrix in the $(W^1,W^2,W^3,B)$ basis, in $v^2/4$ units, is

    [[g², 0, 0, a gg'], [0, g², 0, 0],
     [0, 0, g², kappa gg'], [a gg', 0, kappa gg', g'²]].

Since $a² + kappa² = 1$, its eigenvalues are
    $g²$, $g²$, $0$, and $g²+g'²$.
The VEV orientation therefore preserves a photon null direction and rotates
the SU(2) axis that mixes with $B$. The physical mixing angle remains fixed
by the diagonal coupling ratio. The coupling-ratio origin stays open.

Checks include the exact identity, the full-matrix spectrum and null vector,
and the measured comparison $g'/g = 0.5484$ versus the boundary value 0.5559.

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

print("\nFull gauge-boson mass matrix (v²/4 units):")
k = (PHI - 1) / (PHI + 1)
a = 2 * np.sqrt(PHI) / (PHI + 1)
t = gp                       # framework's boundary g'/g
M = np.array([
    [1.0, 0.0, 0.0, a * t],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, k * t],
    [a * t, 0.0, k * t, t * t],
])
w, _ = eigh(M)
expected = np.array([0.0, 1.0, 1.0, 1.0 + t * t])
check("a² + κ² = 1", np.isclose(a * a + k * k, 1.0))
check("full matrix has the SM spectrum with a massless photon",
      np.allclose(np.sort(w), expected),
      " eigenvalues = %s" % np.array2string(np.sort(w), precision=6))
photon = np.array([t * a, 0.0, t * k, -1.0])
check("full matrix photon null vector", np.linalg.norm(M @ photon) < 1e-12)
check("physical mixing angle remains the diagonal coupling ratio",
      np.isclose(t * t / (1.0 + t * t), s2))
print("  The VEV asymmetry rotates the SU(2) axis that mixes with B;")
print("  the relative gauge coupling remains an independent boundary input.")

print("\nAll checks are algebraic identities (φ-algebra) or linear algebra on the")
print("full gauge-boson matrix; the coupling boundary itself remains asserted")
print("(see standard-model/su2-gauge-extension.md §3.2.1).")
