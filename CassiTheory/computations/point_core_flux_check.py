#!/usr/bin/env python3
"""Check the quantized point-core flux and reduced-support identities."""

import cmath
import math

S_PROTON = 91.461618346
TOL = 1e-12


def close(a: complex, b: complex = 0.0) -> bool:
    return abs(a - b) <= TOL * max(1.0, abs(a), abs(b))


def core_coefficient(n: int, scale_length: float, e_x_squared: float) -> float:
    return 2.0 * math.pi * scale_length * n * n / e_x_squared


# PF-1: minimum-charge Chern normalization and two-patch transition.
g_q = 0.83
n_g = 3
flux = 4.0 * math.pi * n_g / g_q
assert close(g_q * flux / (4.0 * math.pi), n_g)
transition_alpha = 2.0 * n_g * (2.0 * math.pi) / g_q
minimum_charge_phase = cmath.exp(1j * (g_q / 2.0) * transition_alpha)
assert close(minimum_charge_phase, 1.0)

# Directly integrate the north/south-patch curvature over the linking sphere.
patch_angle_count = 20_000
patch_d_theta = math.pi / patch_angle_count
patch_flux = sum(
    2.0
    * math.pi
    * (n_g / g_q)
    * math.sin((index + 0.5) * patch_d_theta)
    * patch_d_theta
    for index in range(patch_angle_count)
)
assert abs(patch_flux / flux - 1.0) < 1e-8

# PF-2: the radial field saturates the fixed-flux exterior bound.
mu_x = 0.71
radius = 1.9
scale_length = 2.4
b_coefficient = flux * flux * scale_length / (8.0 * math.pi * mu_x)
e_x_squared = g_q * g_q * mu_x
assert close(b_coefficient, core_coefficient(n_g, scale_length, e_x_squared))
radial_energy = b_coefficient / radius
assert radial_energy > 0.0

# Independent log-shell quadrature recovers the exterior coefficient.
outer_radius = 1_000.0 * radius
shell_count = 20_000
d_log_r = math.log(outer_radius / radius) / shell_count
quadrature_energy = 0.0
for shell in range(shell_count):
    r = radius * math.exp((shell + 0.5) * d_log_r)
    b_radial = flux / (4.0 * math.pi * r * r)
    quadrature_energy += (
        scale_length
        * 4.0
        * math.pi
        * r**2
        * b_radial**2
        / (2.0 * mu_x)
        * r
        * d_log_r
    )
finite_exterior_energy = b_coefficient * (1.0 / radius - 1.0 / outer_radius)
assert abs(quadrature_energy / finite_exterior_energy - 1.0) < 1e-8

# Direct sphere quadrature confirms that a zero-mean quadrupolar deformation
# preserves flux and raises the fixed-flux energy.
deformation = 0.6
angle_count = 20_000
d_theta = math.pi / angle_count
b_uniform = flux / (4.0 * math.pi * radius**2)
deformed_flux = 0.0
deformed_sphere_energy = 0.0
for index in range(angle_count):
    theta = (index + 0.5) * d_theta
    cosine = math.cos(theta)
    legendre_2 = 0.5 * (3.0 * cosine**2 - 1.0)
    b_deformed = b_uniform * (1.0 + deformation * legendre_2)
    area_strip = 2.0 * math.pi * radius**2 * math.sin(theta) * d_theta
    deformed_flux += b_deformed * area_strip
    deformed_sphere_energy += b_deformed**2 * area_strip
uniform_sphere_energy = b_uniform**2 * 4.0 * math.pi * radius**2
sphere_energy_ratio = deformed_sphere_energy / uniform_sphere_energy
assert abs(deformed_flux / flux - 1.0) < 1e-8
assert abs(sphere_energy_ratio - (1.0 + deformation**2 / 5.0)) < 1e-8
assert sphere_energy_ratio > 1.0

# The coefficient is invariant under the registered gauge normalization change.
normalization = 1.7
rescaled_g = g_q / normalization
rescaled_mu = normalization * normalization * mu_x
rescaled_flux = normalization * flux
rescaled_coefficient = (
    rescaled_flux * rescaled_flux * scale_length / (8.0 * math.pi * rescaled_mu)
)
assert close(rescaled_g * rescaled_flux / (4.0 * math.pi), n_g)
assert close(rescaled_coefficient, b_coefficient)
assert close(rescaled_g * rescaled_g * rescaled_mu, e_x_squared)

# The source interval is one copy; an independently repeated two-edge gauge
# term is a separate branch and doubles the coefficient.
source_interval_coefficient = core_coefficient(1, S_PROTON, 1.0)
two_edge_coefficient = core_coefficient(1, 2.0 * S_PROTON, 1.0)
assert close(two_edge_coefficient, 2.0 * source_interval_coefficient)

# PF-3: strict integer support threshold and stationary-radius curvature.
support_length = 2.4
support_e_squared = 1.7
d_coeff = 40.0
threshold = math.sqrt(
    support_e_squared * d_coeff / (2.0 * math.pi * support_length)
)
n_min = math.floor(threshold) + 1
assert core_coefficient(n_min, support_length, support_e_squared) > d_coeff
assert core_coefficient(n_min - 1, support_length, support_e_squared) <= d_coeff

n_supported = n_min
q_support = (
    core_coefficient(n_supported, support_length, support_e_squared) - d_coeff
)
a_coeff = 2.3
c_coeff = 0.7
discriminant = a_coeff * a_coeff + 12.0 * c_coeff * q_support
r_squared = (-a_coeff + math.sqrt(discriminant)) / (6.0 * c_coeff)
r_star = math.sqrt(r_squared)
derivative = a_coeff - q_support / r_star**2 + 3.0 * c_coeff * r_star**2
curvature = 2.0 * q_support / r_star**3 + 6.0 * c_coeff * r_star
assert r_squared > 0.0
assert close(derivative)
assert close(curvature, 2.0 * a_coeff / r_star + 12.0 * c_coeff * r_star)
assert curvature > 0.0

q_linear = 1.7
r_linear = math.sqrt(q_linear / a_coeff)
assert close(a_coeff - q_linear / r_linear**2)
assert close(2.0 * q_linear / r_linear**3, 2.0 * a_coeff / r_linear)

# PF-5 and PF-6: a nonzero Chern sector has no scalar j=0 matter mode.
for sector in (-4, -1, 1, 4):
    j_min = abs(sector) / 2.0
    angular_eigenvalue = j_min * (j_min + 1.0) - sector * sector / 4.0
    assert close(angular_eigenvalue, abs(sector) / 2.0)
    assert j_min > 0.0
    assert angular_eigenvalue > 0.0

# The summed two-component angular lower bound tends to
# pi*K_x*|N_G|*rho_0*L_s per unit radius and therefore diverges linearly.
k_x = 1.2
rho_0 = 0.8
angular_shell_cost = math.pi * k_x * abs(n_g) * rho_0 * scale_length
spectral_bound = (
    (k_x * abs(n_g) / 4.0) * (4.0 * math.pi * rho_0) * scale_length
)
assert close(angular_shell_cost, spectral_bound)
assert angular_shell_cost > 0.0
assert angular_shell_cost * (100.0 - radius) > angular_shell_cost * (10.0 - radius)

print("Cassi point-core flux-sector check")
print(f"  Chern sector N_G                    = {n_g}")
print(f"  fixed-flux coefficient              = {b_coefficient:.12f}")
print(f"  radial exterior energy              = {radial_energy:.12f}")
print(f"  source N=1 proton coefficient/e_x^-2 = {source_interval_coefficient:.10f}")
print(f"  strict minimum supporting |N_G|     = {n_min}")
print(f"  supported stationary radius         = {r_star:.12f}")
print(f"  stationary derivative residual      = {derivative:.3e}")
print(f"  reduced breathing curvature         = {curvature:.12f}")
print(f"  minimum monopole-harmonic j         = {abs(n_g) / 2.0:.1f}")
print(f"  angular energy/radius lower bound   = {angular_shell_cost:.12f}")
print("ALL CHECKS PASSED")
