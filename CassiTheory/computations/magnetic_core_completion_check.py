#!/usr/bin/env python3
"""Check conditional magnetic-core identities, including transverse screening.

Run: python computations/magnetic_core_completion_check.py
Screening protocol: computations/matter-formation-continuum-report.md section 39.1.
"""

import math

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0
TOL = 1e-11


def close(a: float, b: float = 0.0, tol: float = TOL) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def profile_k(x: float) -> float:
    return x / math.sinh(x)


def profile_h(x: float) -> float:
    return 1.0 / math.tanh(x) - 1.0 / x


def profile_k_prime(x: float) -> float:
    sinh_x = math.sinh(x)
    return (sinh_x - x * math.cosh(x)) / sinh_x**2


def profile_h_prime(x: float) -> float:
    return 1.0 / x**2 - 1.0 / math.sinh(x) ** 2


def bps_density(x: float) -> float:
    k = profile_k(x)
    h = profile_h(x)
    k_prime = profile_k_prime(x)
    h_prime = profile_h_prime(x)
    return (
        k_prime**2
        + (1.0 - k**2) ** 2 / (2.0 * x**2)
        + x**2 * h_prime**2 / 2.0
        + k**2 * h**2
    )


# MC-1: the gauge-invariant composition scalar reduces to E_Y - phi E_I
# in the asymptotic unitary gauge Phi^a = v_Q delta^{a3}.
e_y = 3.2
e_i = 1.7
rho = e_y + e_i
spin_3 = e_y - e_i
composition = ((1.0 - PHI) * rho + (1.0 + PHI) * spin_3) / 2.0
assert close(composition, e_y - PHI * e_i)

# A common SO(3) rotation of the adjoint Higgs and spin vector preserves the
# scalar used by the completion potential.
def rotate_y(vector: tuple[float, float, float], radians: float) -> tuple[float, float, float]:
    x, y, z = vector
    return (
        math.cos(radians) * x + math.sin(radians) * z,
        y,
        -math.sin(radians) * x + math.cos(radians) * z,
    )


angle = 0.73
adjoint = (0.0, 0.0, 1.4)
spin = (0.6, -0.8, spin_3)
rotated_adjoint = rotate_y(adjoint, angle)
rotated_spin = rotate_y(spin, angle)
dot_before = sum(a * b for a, b in zip(adjoint, spin))
dot_after = sum(a * b for a, b in zip(rotated_adjoint, rotated_spin))
assert close(dot_before, dot_after)

# MC-2: the Prasad-Sommerfield profiles obey the first-order monopole system.
for x in (0.2, 0.7, 1.3, 3.0, 8.0):
    k = profile_k(x)
    h = profile_h(x)
    k_prime = profile_k_prime(x)
    h_prime = profile_h_prime(x)
    assert close(k_prime, -k * h)
    assert close(x**2 * h_prime, 1.0 - k**2)
    boundary_derivative = h_prime * (1.0 - k**2) - 2.0 * h * k * k_prime
    assert close(bps_density(x), boundary_derivative)

small_x = 1e-4
large_x = 80.0
assert abs(profile_k(small_x) - (1.0 - small_x**2 / 6.0)) < 1e-12
assert abs(profile_h(small_x) - small_x / 3.0) < 1e-11
assert profile_k(large_x) < 1e-32
assert close(profile_h(large_x), 1.0 - 1.0 / large_x)


# Midpoint quadrature plus the analytic BPS tail recovers the unit
# dimensionless monopole energy. At x >= 80, K is exponentially negligible
# and H = 1 - 1/x up to far below this check's tolerance.
upper = 80.0
steps = 160_000
dx = upper / steps
dimensionless_energy = sum(bps_density((index + 0.5) * dx) for index in range(steps)) * dx
dimensionless_energy += 1.0 / upper
assert abs(dimensionless_energy - 1.0) < 2e-8

# MC-3: source-unit BPS mass, core width, flux, and the registered exterior
# coefficient are invariant under B -> aB, g -> g/a, mu -> a^2 mu,
# Phi -> aPhi.
g_q = 0.83
mu_x = 0.71
v_q = 1.2
scale_length = 2.4
n_g = 1
flux = 4.0 * math.pi * n_g / g_q
core_inverse_length = g_q * v_q
bps_mass = 4.0 * math.pi * abs(n_g) * scale_length * v_q / (mu_x * g_q)
exterior_coefficient = flux**2 * scale_length / (8.0 * math.pi * mu_x)
e_x_squared = g_q**2 * mu_x
assert close(exterior_coefficient, 2.0 * math.pi * n_g**2 * scale_length / e_x_squared)

normalization = 1.7
rescaled_g = g_q / normalization
rescaled_mu = normalization**2 * mu_x
rescaled_v = normalization * v_q
rescaled_flux = normalization * flux
rescaled_mass = (
    4.0 * math.pi * abs(n_g) * scale_length * rescaled_v
    / (rescaled_mu * rescaled_g)
)
rescaled_exterior = rescaled_flux**2 * scale_length / (8.0 * math.pi * rescaled_mu)
assert close(rescaled_g * rescaled_v, core_inverse_length)
assert close(rescaled_mass, bps_mass)
assert close(rescaled_exterior, exterior_coefficient)

# The Higgs-to-vector mass ratio is normalization invariant as well.
lambda_h = 0.19
vector_mass_squared = (g_q * v_q) ** 2
higgs_mass_squared = 2.0 * mu_x * lambda_h * v_q**2
beta_squared = higgs_mass_squared / vector_mass_squared
rescaled_lambda = lambda_h / normalization**4
rescaled_beta_squared = 2.0 * rescaled_mu * rescaled_lambda / rescaled_g**2
assert close(beta_squared, rescaled_beta_squared)

# MC-4: scalar phase gradients cancel longitudinal connections only.
# The transverse response is fixed by the total condensate density.
rho_0 = 0.8
k_x = 1.2
e_y_vacuum = rho_0 / PHI
e_i_vacuum = rho_0 / PHI**2
assert close(e_y_vacuum + e_i_vacuum, rho_0)
assert close(e_y_vacuum / e_i_vacuum, PHI)
london_mass_squared = g_q**2 * k_x * rho_0 / 4.0
penetration_inverse_squared = mu_x * london_mass_squared
assert penetration_inverse_squared > 0.0

screening_max_error = 0.0
for yang_fraction in (0.2, 0.5, 1.0 / PHI):
    e_y = rho_0 * yang_fraction
    e_i = rho_0 - e_y
    cos_beta = (e_y - e_i) / rho_0
    for wave, connection, stiffness in (
        ((1.0, 2.0, -1.0), (0.6, -0.3, 0.2), (k_x, k_x, k_x)),
        ((1.0, 2.0, -1.0, 0.75), (0.6, -0.3, 0.2, 0.8), (k_x, k_x, k_x, 0.7)),
    ):
        wave = np.array(wave)
        connection = np.array(connection)
        stiffness = np.array(stiffness)
        symbol = float(np.dot(stiffness * wave, wave))
        projection = float(np.dot(stiffness * wave, connection)) / symbol
        transverse = connection - projection * wave

        # Minimize both species' phases directly in their original kinetic energy.
        phase_y = g_q * projection / 2.0
        phase_i = -phase_y
        component_energy = 0.5 * float(np.sum(stiffness * (
            e_y * (phase_y * wave - g_q * connection / 2.0) ** 2
            + e_i * (phase_i * wave + g_q * connection / 2.0) ** 2
        )))
        projected_energy = rho_0 * g_q**2 * float(np.dot(
            stiffness * transverse, transverse
        )) / 8.0
        assert close(component_energy, projected_energy)
        if wave.size == 3:
            response = 2.0 * component_energy / float(np.dot(transverse, transverse))
            assert close(response, london_mass_squared)
        screening_max_error = max(screening_max_error, abs(component_energy - projected_energy))
        longitudinal_energy = 0.5 * float(np.sum(stiffness * (
            e_y * (phase_y * wave - g_q * projection * wave / 2.0) ** 2
            + e_i * (phase_i * wave + g_q * projection * wave / 2.0) ** 2
        )))
        assert close(longitudinal_energy)

        # With the relative phase fixed, only the longitudinal counterflow
        # term receives the composition-dependent factor 1-cos(beta)^2.
        relative_phase = 0.37
        c_vector = relative_phase * wave + g_q * connection
        common_phase = cos_beta * float(np.dot(stiffness * wave, c_vector)) / (2.0 * symbol)
        common_energies = []
        for shift in (0.0, -0.1, 0.1):
            phase_y = common_phase + shift - relative_phase / 2.0
            phase_i = common_phase + shift + relative_phase / 2.0
            common_energies.append(0.5 * float(np.sum(stiffness * (
                e_y * (phase_y * wave - g_q * connection / 2.0) ** 2
                + e_i * (phase_i * wave + g_q * connection / 2.0) ** 2
            ))))
        constrained_energy = rho_0 / 8.0 * (
            float(np.dot(stiffness * c_vector, c_vector))
            - cos_beta**2 * float(np.dot(stiffness * wave, c_vector)) ** 2 / symbol
        )
        assert close(common_energies[0], constrained_energy)
        increment = rho_0 * symbol * 0.1**2 / 2.0
        for shifted_energy in common_energies[1:]:
            assert close(shifted_energy - common_energies[0], increment)
            assert shifted_energy > common_energies[0]

    # Unit tube: opposite species windings fix the common winding to zero.
    azimuthal_connection = 0.6
    tube_energy = k_x / 2.0 * (
        e_y * (1.0 - g_q * azimuthal_connection / 2.0) ** 2
        + e_i * (-1.0 + g_q * azimuthal_connection / 2.0) ** 2
    )
    assert close(tube_energy, k_x * rho_0 / 2.0 * (
        1.0 - g_q * azimuthal_connection / 2.0
    ) ** 2)
    tube_curvature = k_x * (e_y + e_i) * g_q**2 / 4.0
    assert close(tube_curvature, london_mass_squared)

# Vanishing condensate and vanishing coupling remove the direct response.
for density, coupling in ((0.0, g_q), (rho_0, 0.0)):
    energy = k_x / 2.0 * density * (coupling / 2.0) ** 2
    assert close(energy)

counterflow_stiffness = k_x * e_y_vacuum * e_i_vacuum / rho_0
assert close(counterflow_stiffness, k_x * rho_0 / PHI**3)
assert not close(g_q**2 * counterflow_stiffness, london_mass_squared)

spatial_winding_y = 1
spatial_winding_i = -1
vortex_flux_from_y = 4.0 * math.pi * spatial_winding_y / g_q
vortex_flux_from_i = -4.0 * math.pi * spatial_winding_i / g_q
assert close(vortex_flux_from_y, flux)
assert close(vortex_flux_from_i, flux)
assert spatial_winding_y - spatial_winding_i == 2

# MC-5: a screened attractive monopole-antimonopole tail and positive string
# tension give no finite-separation minimum in the registered branch.
string_tension = 0.37
tail_strength = 0.52
penetration_inverse = math.sqrt(penetration_inverse_squared)
for separation in (0.4, 1.0, 3.0, 8.0):
    pair_slope = string_tension + tail_strength * math.exp(
        -penetration_inverse * separation
    ) * (penetration_inverse / separation + 1.0 / separation**2)
    assert pair_slope > 0.0

print("Cassi magnetic-core completion check")
print(f"  BPS dimensionless energy             = {dimensionless_energy:.12f}")
print(f"  unit residual flux                   = {flux:.12f}")
print(f"  source-interval BPS mass             = {bps_mass:.12f}")
print(f"  inverse vector-core length           = {core_inverse_length:.12f}")
print(f"  Higgs/vector mass-ratio squared      = {beta_squared:.12f}")
print(f"  transverse London inverse length^2  = {penetration_inverse_squared:.12f}")
print(f"  maximum screening energy residual   = {screening_max_error:.3e}")
print(f"  minimum relative spatial winding     = {spatial_winding_y - spatial_winding_i}")
print("ALL CHECKS PASSED")
