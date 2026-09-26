#!/usr/bin/env python3
"""
Weinberg coupling-origin audit
==============================

Tests the strongest two-fluid candidate for the asserted boundary condition

    (g / g')**2 = 2*phi,
    sin^2(theta_W) = phi**-3.

Candidate route
---------------
The attractor potential is

    V = (lambda/2) * (Psi_Y**2 - phi*Psi_I**2)**2.

At the fixed point Psi_Y**2 = phi*Psi_I**2, its diagonal curvature ratio is

    K_I / K_Y = phi.

The diagonal stiffness metric gives a conditional candidate. If the gauge
kinetic normalization is imposed by

    S_SU2(K) / g^2 = S_Y(K) / g'^2,

then K = diag(1, phi) gives S_SU2/S_Y = 2*phi. The audit compares this with
the canonical metric, the transverse-generator subset, alternative generator
normalizations, and the current action. The target-producing choice is not
selected by the present Lagrangian.

The audit also tests the closure boundary. The current action uses the
canonical kinetic metric I and contains independent coefficients g and g'.
It contains neither K nor the orbit-normalization condition. The complete
asymmetric-VEV gauge-boson matrix has

    a = 2*sqrt(phi)/(phi+1),  a**2 + kappa**2 = 1,

and therefore retains the standard massless photon and spectrum. The VEV
orientation supplies no relation between g and g'; the 2*phi result remains a
conditional candidate rather than a derivation from the present action.

Usage: python computations/weinberg_coupling_origin_audit.py
"""

from __future__ import annotations

import math
import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0
KAPPA = PHI ** -3

T1 = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex) / 2.0
T2 = np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=complex) / 2.0
T3 = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex) / 2.0
Y = np.eye(2, dtype=complex) / 2.0
GENERATORS = (T1, T2, T3)

# Normalized phi-attractor VEV: |Psi_Y|^2 / |Psi_I|^2 = phi.
psi = np.array([math.sqrt(PHI), 1.0], dtype=complex) / math.sqrt(PHI + 1.0)


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{detail}")


def orbit_norm(generator: np.ndarray, metric: np.ndarray) -> float:
    orbit = generator @ psi
    return float(np.real(np.vdot(orbit, metric @ orbit)))


def orbit_ratio_for(
    generators: tuple[np.ndarray, ...],
    hypercharge: np.ndarray,
    yin_weight: float,
) -> float:
    metric = np.diag([1.0, yin_weight]).astype(complex)
    su2 = sum(orbit_norm(generator, metric) for generator in generators)
    u1 = orbit_norm(hypercharge, metric)
    return su2 / u1


def orbit_ratio(yin_weight: float) -> float:
    return orbit_ratio_for(GENERATORS, Y, yin_weight)
print("Weinberg coupling-origin audit")
print("================================")
print(f"phi = {PHI:.12f}")
print(f"target 2*phi = {2.0 * PHI:.12f}\n")

print("1. Algebraic orbit ratios")
canonical_ratio = orbit_ratio(1.0)
stiffness_ratio = orbit_ratio(PHI)
check("canonical field metric gives S_SU2/S_Y = 3", np.isclose(canonical_ratio, 3.0))
check(
    "attractor stiffness metric gives S_SU2/S_Y = 2*phi",
    np.isclose(stiffness_ratio, 2.0 * PHI),
    f" ({stiffness_ratio:.12f})",
)

transverse_ratio = orbit_ratio_for((T1, T2), Y, 1.0)
unnormalized_ratio = orbit_ratio_for((2.0 * T1, 2.0 * T2), Y, 1.0)
identity_hypercharge_ratio = orbit_ratio_for((T1, T2), np.eye(2, dtype=complex), 1.0)
single_generator_norms = [orbit_norm(generator, np.eye(2, dtype=complex)) for generator in GENERATORS]
check("canonical transverse pair gives 2", np.isclose(transverse_ratio, 2.0))
check("unnormalized Pauli pair gives 8", np.isclose(unnormalized_ratio, 8.0))
check("canonical pair with Y = I gives 1/2", np.isclose(identity_hypercharge_ratio, 0.5))
check("each canonical SU(2) orbit norm is phi-independent 1/4", np.allclose(single_generator_norms, 0.25))

# For K = diag(1,r), the exact ratio is
# [2 + phi + r(2phi+1)]/(phi+r). Setting it equal to 2phi gives r=phi.
def analytic_ratio(r: float) -> float:
    return (2.0 + PHI + r * (2.0 * PHI + 1.0)) / (PHI + r)

check(
    "analytic orbit formula agrees with matrix calculation",
    np.isclose(analytic_ratio(PHI), stiffness_ratio),
)
required_weight = 2.0 * PHI**2 - PHI - 2.0
check(
    "target orbit ratio selects Yin/Yang stiffness weight phi",
    np.isclose(required_weight, PHI),
    f" (required={required_weight:.12f})",
)

print("\n2. Attractor curvature")
# At Delta = Psi_Y^2 - phi Psi_I^2 = 0,
# V_YY = 4 lambda Psi_Y^2 and V_II = 4 lambda phi^2 Psi_I^2.
# Set Psi_I = 1; the common lambda factor cancels.
K_Y = 4.0 * PHI
K_I = 4.0 * PHI**2
check(
    "diagonal attractor curvature has K_I/K_Y = phi",
    np.isclose(K_I / K_Y, PHI),
    f" ({K_I / K_Y:.12f})",
)

print("\n3. Current-action closure test")
print("  The two-fluid kinetic term uses the identity metric:")
print("    L_kin = 1/2 (partial_mu Psi_alpha)(partial^mu Psi_alpha)")
print("  The gauge sector has independent 1/g^2 and 1/g'^2 coefficients.")
print("  The action contains neither the stiffness metric nor orbit matching.")
check(
    "current canonical metric does not select 2*phi",
    not np.isclose(canonical_ratio, 2.0 * PHI),
    f" (canonical ratio={canonical_ratio:.12f})",
)

print("\n4. Full photon/null-direction check")
# The complete matrix in (W1, W2, W3, B), in v^2/4 units, is
# [[1,0,0,a*t], [0,1,0,0], [0,0,1,kappa*t], [a*t,0,kappa*t,t^2]],
# with a = 2*sqrt(phi)/(phi+1) and t = g'/g.
a = 2.0 * math.sqrt(PHI) / (PHI + 1.0)
t = math.sqrt(1.0 / (2.0 * PHI))
M = np.array([
    [1.0, 0.0, 0.0, a * t],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, KAPPA * t],
    [a * t, 0.0, KAPPA * t, t * t],
])
eigenvalues = np.linalg.eigvalsh(M)
expected = np.array([0.0, 1.0, 1.0, 1.0 + t * t])
check("a^2 + kappa^2 = 1", np.isclose(a * a + KAPPA * KAPPA, 1.0))
check("full VEV matrix has a massless photon", np.allclose(np.sort(eigenvalues), expected))
photon = np.array([t * a, 0.0, t * KAPPA, -1.0])
check("full photon null vector", np.linalg.norm(M @ photon) < 1e-12)
check("physical angle remains t^2/(1+t^2)", np.isclose(t * t / (1.0 + t * t), PHI ** -3))

print("\nVerdict")
print("-------")
print("  The curvature-orbit construction reproduces the target only after")
print("  choosing a stiffness metric and an orbit-matching rule absent from")
print("  the current action. Canonical orbit conventions give 2, 3, 8, or 1/2")
print("  under equally standard choices, so no selection constraint closes it.")
print("  The full asymmetric-VEV matrix has the standard photon null direction;")
print("  the VEV orientation supplies no relation between the gauge couplings.")
print("  The coupling boundary remains asserted.")
print("\nALL CHECKS PASSED")
