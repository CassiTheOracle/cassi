#!/usr/bin/env python3
"""Check the conditional core-trapped Noether-charge support identities."""

import cmath
import math

TOL = 1e-11


def close(a: float, b: float = 0.0, tol: float = TOL) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def add_dims(*dimensions: tuple[int, int]) -> tuple[int, int]:
    return tuple(sum(values) for values in zip(*dimensions))  # type: ignore[return-value]


def support_function(
    length: float,
    tension: float,
    tail: float,
    screening: float,
    support: float,
) -> float:
    return (
        tension * length**2
        + tail * (1.0 + screening * length) * math.exp(-screening * length)
        - support
    )


def supported_length(
    tension: float,
    tail: float,
    screening: float,
    support: float,
) -> float:
    assert tension > 0.0 and tail > 0.0 and screening > 0.0
    assert support > tail
    lower = math.sqrt((support - tail) / tension)
    upper = math.sqrt(support / tension)
    assert support_function(lower, tension, tail, screening, support) < 0.0
    assert support_function(upper, tension, tail, screening, support) > 0.0
    for _ in range(100):
        midpoint = (lower + upper) / 2.0
        if support_function(midpoint, tension, tail, screening, support) < 0.0:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


# CC7, CC22, and CC27: every carrier Hamiltonian term and every reduced
# coefficient has the declared source-unit dimension. Dimensions are
# represented as powers of (energy, spatial length); the scale coordinate is
# dimensionless under the registered flat-ds convention.
energy_density = (1, -3)
chi_squared = (0, -3)
spatial_gradient_squared = (0, -5)
scale_gradient_squared = chi_squared
k_x_carrier_dim = (1, 2)
k_scale_carrier_dim = (1, 0)
epsilon_dim = (1, 0)
rho_dim = (0, -3)
eta_dim = (1, 3)
lambda_3d_dim = (1, 3)
assert add_dims(k_x_carrier_dim, spatial_gradient_squared) == energy_density
assert add_dims(k_scale_carrier_dim, scale_gradient_squared) == energy_density
assert add_dims(epsilon_dim, chi_squared) == energy_density
assert add_dims(eta_dim, rho_dim, chi_squared) == energy_density
assert add_dims(lambda_3d_dim, chi_squared, chi_squared) == energy_density

u_squared_dim = (0, -2)
mode_quartic_integral_dim = add_dims(u_squared_dim, u_squared_dim, (0, 2))
lambda_line_dim = add_dims(lambda_3d_dim, mode_quartic_integral_dim)
support_dim = lambda_line_dim
assert lambda_line_dim == (1, 1)
assert add_dims((1, -1), (0, 1)) == (1, 0)  # sigma_Q L
assert add_dims(support_dim, (0, -1)) == (1, 0)  # A_C / L
assert add_dims((1, 1), (0, -1)) == (1, 0)  # C_Q / L
assert add_dims((0, -1), (0, 1)) == (0, 0)  # kappa_L L

# CC6 and CC13-CC15: a global carrier phase preserves density and the spatial
# Noether current. Closed/no-flux boundaries then preserve its integrated
# number.
chi = 0.8 + 0.3j
grad_chi = -0.2 + 0.5j
phase = cmath.exp(0.63j)
rotated_chi = phase * chi
rotated_gradient = phase * grad_chi
assert close(abs(rotated_chi) ** 2, abs(chi) ** 2)
assert close(
    (rotated_chi.conjugate() * rotated_gradient).imag,
    (chi.conjugate() * grad_chi).imag,
)

# CC3-CC4: a fixed excess of the existing common Yang/Yin number has a bulk
# spreading sequence whose density energy falls as inverse volume.
lambda_rho = 0.8
excess_number = 3.0
volumes = (10.0, 100.0, 1000.0)
spreading_energies = tuple(
    lambda_rho * excess_number**2 / (4.0 * volume) for volume in volumes
)
assert spreading_energies[0] > spreading_energies[1] > spreading_energies[2]
assert close(spreading_energies[1] / spreading_energies[0], 0.1)
assert close(spreading_energies[2] / spreading_energies[1], 0.1)

# CC18-CC27: conditional transverse-mode inputs and their line reduction.
k_x_carrier = 0.75
epsilon_out = 2.0
epsilon_0 = 0.6
binding_gap = epsilon_out - epsilon_0
assert binding_gap > 0.0
decay_inverse_squared = 2.0 * binding_gap / k_x_carrier

lambda_3d = 0.9
mode_quartic_integral = 2.0 / 3.0
lambda_line = lambda_3d * mode_quartic_integral
carrier_number = 2.0
support = lambda_line * carrier_number**2 / 2.0

# CC24-CC26 and CC47: a zero-mean line-density perturbation raises the
# quartic energy above the uniform fixed-charge value.
trial_length = 1.4
perturbation = 0.4
uniform_density_integral = carrier_number**2 / trial_length
perturbed_density_integral = uniform_density_integral * (1.0 + perturbation**2 / 2.0)
assert perturbed_density_integral > uniform_density_integral
assert close(
    lambda_line * (perturbed_density_integral - uniform_density_integral) / 2.0,
    lambda_line
    * carrier_number**2
    * perturbation**2
    / (4.0 * trial_length),
)

# CC29-CC40: one supported separation, its analytic bounds, and its positive
# curvature for a declared conditional coefficient point.
tension = 0.45
tail = 0.70
screening = 0.90
matching_length = 1.0
assert support > tail
assert support - tail > tension * matching_length**2

lower_bound = math.sqrt((support - tail) / tension)
upper_bound = math.sqrt(support / tension)
length = supported_length(tension, tail, screening, support)
assert lower_bound < length < upper_bound
assert close(support_function(length, tension, tail, screening, support))

energy_slope = (
    tension
    - support / length**2
    + tail
    * math.exp(-screening * length)
    * (screening / length + 1.0 / length**2)
)
assert close(energy_slope)

curvature = (
    2.0 * tension - tail * screening**2 * math.exp(-screening * length)
) / length
assert curvature > 0.0


def reduced_energy(separation: float) -> float:
    return (
        tension * separation
        + (support - tail * math.exp(-screening * separation)) / separation
    )


step = length * 1e-4
finite_difference_curvature = (
    reduced_energy(length + step)
    - 2.0 * reduced_energy(length)
    + reduced_energy(length - step)
) / step**2
assert close(finite_difference_curvature, curvature, tol=2e-7)

# CC35: even when F initially decreases, its derivative bracket increases
# monotonically and the supported branch still has exactly one crossing.
secondary_tension = 0.08
secondary_tail = 1.1
secondary_screening = 1.4
secondary_support = 1.6
turning_length = math.log(
    secondary_tail * secondary_screening**2 / (2.0 * secondary_tension)
) / secondary_screening
assert turning_length > 0.0
assert support_function(
    turning_length,
    secondary_tension,
    secondary_tail,
    secondary_screening,
    secondary_support,
) < support_function(
    1e-12,
    secondary_tension,
    secondary_tail,
    secondary_screening,
    secondary_support,
)
secondary_length = supported_length(
    secondary_tension,
    secondary_tail,
    secondary_screening,
    secondary_support,
)
assert secondary_length > turning_length

# CC41-CC46: support, matching, and chemical retention overlap at this point.
chemical_potential = epsilon_0 + lambda_line * carrier_number / length
necessary_localization_margin = binding_gap**2 - 2.0 * lambda_line * tension
sufficient_charge_threshold = (
    2.0
    * binding_gap**2
    * tail
    / (lambda_line * necessary_localization_margin)
)
matching_charge_threshold = 2.0 * (
    tail + tension * matching_length**2
) / lambda_line
assert necessary_localization_margin > 0.0
assert carrier_number**2 > sufficient_charge_threshold
assert carrier_number**2 > matching_charge_threshold
assert chemical_potential < epsilon_out
assert lambda_line * carrier_number / length < binding_gap

# CC28: optional endpoint-locked phase energy scales as inverse length squared.
phase_change = 2.0 * math.pi
phase_energy = k_x_carrier * carrier_number * phase_change**2 / (2.0 * length**2)
doubled_length_phase_energy = (
    k_x_carrier * carrier_number * phase_change**2 / (2.0 * (2.0 * length) ** 2)
)
assert close(phase_energy / doubled_length_phase_energy, 4.0)

print("Cassi core-trapped charge support check")
print(f"  bulk spreading energy ratio          = {spreading_energies[1] / spreading_energies[0]:.12f}")
print(f"  carrier binding gap                  = {binding_gap:.12f}")
print(f"  exterior inverse decay length squared = {decay_inverse_squared:.12f}")
print(f"  line support coefficient             = {support:.12f}")
print(f"  supported separation                 = {length:.12f}")
print(f"  lower separation bound               = {lower_bound:.12f}")
print(f"  upper separation bound               = {upper_bound:.12f}")
print(f"  length curvature                     = {curvature:.12f}")
print(f"  carrier chemical potential           = {chemical_potential:.12f}")
print("ALL CHECKS PASSED")
