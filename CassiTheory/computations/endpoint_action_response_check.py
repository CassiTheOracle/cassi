#!/usr/bin/env python3
"""Check the preregistered source-action charged-endpoint response identities."""

import math

import numpy as np

TOL = 5e-13
ANOMALOUS_MIN = 1e-3
NONHERMITIAN_MIN = 1e-3


def phase(angle: float) -> complex:
    return complex(math.cos(angle), math.sin(angle))


def max_error(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.max(np.abs(left - right)))


def link_matrix(strength: float, alpha: float) -> np.ndarray:
    return np.array(
        [
            [0j, strength * phase(-alpha)],
            [strength * phase(alpha), 0j],
        ],
        dtype=complex,
    )


def doubled_link(coupling: np.ndarray) -> np.ndarray:
    zero = np.zeros((2, 2), dtype=complex)
    return 0.5 * np.block(
        [[coupling, zero], [zero, coupling.conjugate()]]
    )


def mixed_hessian(
    kappa: float,
    amplitude: float,
    alpha: float,
    yang: complex,
    yin: complex,
) -> np.ndarray:
    minus = phase(-alpha)
    plus = phase(alpha)
    return kappa * amplitude * np.array(
        [
            [0j, minus * yang.conjugate(), minus * yin, 0j],
            [plus * yin.conjugate(), 0j, 0j, plus * yang],
        ],
        dtype=complex,
    )


def action_kernel(
    curvature: np.ndarray,
    temporal_weight: float,
    omega: complex,
    damping: float,
) -> np.ndarray:
    sigma_three = np.diag([1.0, -1.0]).astype(complex)
    return (
        temporal_weight * (omega + 1j * damping) * sigma_three
        - curvature
    )


def energy_kernel(
    curvature: np.ndarray,
    temporal_weight: float,
    omega: complex,
    damping: float,
) -> np.ndarray:
    return -action_kernel(curvature, temporal_weight, omega, damping)


def effective_response(
    direct: np.ndarray,
    mixed: np.ndarray,
    endpoint_action: np.ndarray,
) -> np.ndarray:
    return direct - mixed.conjugate().T @ np.linalg.solve(
        endpoint_action, mixed
    )


# Frozen numerical point.
hbar = 1.0
u_amplitude = 1.0
kappa = 0.45
yang_amplitude = 0.7
yang_phase = 0.2
yin_amplitude = 0.5
yin_phase = -0.3
alpha = yin_phase - yang_phase
w_prime = 0.1575
u_second = 0.6
omega = 0.2
damping = 0.12
frame_angle = 0.37

yang = yang_amplitude * phase(yang_phase)
yin = yin_amplitude * phase(yin_phase)
upsilon_zero = u_amplitude * phase(alpha)
bilinear_zero = yang.conjugate() * yin

# AR1: a closed homogeneous conservative extremum carries zero link current.
background_error = abs(w_prime * upsilon_zero - kappa * bilinear_zero)
imaginary_balance = abs((upsilon_zero.conjugate() * bilinear_zero).imag)
link_current = (
    4.0
    * kappa
    * u_amplitude
    * yang_amplitude
    * yin_amplitude
    * math.sin(yin_phase - yang_phase - alpha)
    / hbar
)
assert background_error < TOL, background_error
assert imaginary_balance < TOL, imaginary_balance
assert abs(link_current) < TOL, link_current

# The fractional endpoint fluctuation has a positive energy curvature.
temporal_weight = hbar * u_amplitude**2
normal_curvature = u_amplitude**2 * (
    w_prime + u_amplitude**2 * u_second
)
anomalous_curvature = u_amplitude**4 * u_second
curvature = np.array(
    [
        [normal_curvature, anomalous_curvature],
        [anomalous_curvature, normal_curvature],
    ],
    dtype=complex,
)
assert normal_curvature > abs(anomalous_curvature)

# AR2: exact link and static-action expansions reproduce their Hessians.
eta_yang = 0.23 - 0.17j
eta_yin = -0.11 + 0.29j
zeta = 0.19 + 0.07j
expansion_scale = 0.37
endpoint_perturbation = upsilon_zero * zeta


def link_value(scale: float) -> complex:
    endpoint = upsilon_zero + scale * endpoint_perturbation
    rail_yang = yang + scale * eta_yang
    rail_yin = yin + scale * eta_yin
    term = endpoint.conjugate() * rail_yang.conjugate() * rail_yin
    return kappa * (term + term.conjugate())


zeroth_branch = upsilon_zero.conjugate() * yang.conjugate() * yin
linear_branch = (
    endpoint_perturbation.conjugate() * yang.conjugate() * yin
    + upsilon_zero.conjugate() * eta_yang.conjugate() * yin
    + upsilon_zero.conjugate() * yang.conjugate() * eta_yin
)
quadratic_branch = (
    endpoint_perturbation.conjugate()
    * (eta_yang.conjugate() * yin + yang.conjugate() * eta_yin)
    + upsilon_zero.conjugate() * eta_yang.conjugate() * eta_yin
)
cubic_branch = (
    endpoint_perturbation.conjugate()
    * eta_yang.conjugate()
    * eta_yin
)
coefficients = [
    kappa * (branch + branch.conjugate())
    for branch in (
        zeroth_branch,
        linear_branch,
        quadratic_branch,
        cubic_branch,
    )
]
polynomial_value = sum(
    coefficient * expansion_scale**power
    for power, coefficient in enumerate(coefficients)
)
polynomial_error = abs(link_value(expansion_scale) - polynomial_value)

link_strength = 2.0 * kappa * u_amplitude
direct_link = link_matrix(link_strength, alpha)
direct_nambu = doubled_link(direct_link)
mixed = mixed_hessian(kappa, u_amplitude, alpha, yang, yin)
rail_nambu = np.array(
    [eta_yang, eta_yin, eta_yang.conjugate(), eta_yin.conjugate()],
    dtype=complex,
)
endpoint_nambu = np.array([zeta, zeta.conjugate()], dtype=complex)
direct_quadratic = 0.5 * np.vdot(
    rail_nambu, direct_nambu @ rail_nambu
)
mixed_quadratic = 0.5 * (
    np.vdot(endpoint_nambu, mixed @ rail_nambu)
    + np.vdot(rail_nambu, mixed.conjugate().T @ endpoint_nambu)
)
mixed_hessian_error = abs(
    direct_quadratic + mixed_quadratic - coefficients[2]
)

number_linear = 2.0 * (
    upsilon_zero.conjugate() * endpoint_perturbation
).real
number_quadratic = abs(endpoint_perturbation) ** 2
static_action_coefficient = -(
    w_prime * number_quadratic
    + 0.5 * u_second * number_linear**2
)
static_nambu_coefficient = -0.5 * np.vdot(
    endpoint_nambu, curvature @ endpoint_nambu
)
static_hessian_error = abs(
    static_action_coefficient - static_nambu_coefficient
)
assert polynomial_error < TOL, polynomial_error
assert mixed_hessian_error < TOL, mixed_hessian_error
assert static_hessian_error < TOL, static_hessian_error

# AR3: zero background has no quadratic response and a positive quartic term.
zero_mixed = mixed_hessian(kappa, 0.0, alpha, 0j, 0j)
zero_direct = doubled_link(link_matrix(0.0, alpha))
zero_endpoint_mass = 1.1
zero_action = -zero_endpoint_mass * np.eye(2, dtype=complex)
zero_correction = zero_mixed.conjugate().T @ np.linalg.solve(
    zero_action, zero_mixed
)
assert np.max(np.abs(zero_mixed)) < TOL
assert np.max(np.abs(zero_direct)) < TOL
assert np.max(np.abs(zero_correction)) < TOL


def quartic_contribution(scale: float) -> complex:
    rail_yang = scale * eta_yang
    rail_yin = scale * eta_yin
    source = kappa * np.array(
        [
            rail_yang.conjugate() * rail_yin,
            rail_yin.conjugate() * rail_yang,
        ],
        dtype=complex,
    )
    return -0.5 * np.vdot(source, np.linalg.solve(zero_action, source))


quartic_low = quartic_contribution(0.4)
quartic_high = quartic_contribution(0.8)
quartic_ratio = quartic_high / quartic_low
quartic_error = abs(quartic_ratio - 16.0)
assert abs(quartic_low.imag) < TOL, quartic_low
assert abs(quartic_high.imag) < TOL, quartic_high
assert quartic_low.real > 0.0, quartic_low
assert quartic_high.real > 0.0, quartic_high
assert quartic_error < TOL, quartic_error

# AR4: positive energy curvature gives the closed and damped action poles.
curvature_eigenvalues = np.linalg.eigvalsh(curvature)
endpoint_frequency = math.sqrt(
    normal_curvature**2 - abs(anomalous_curvature) ** 2
) / temporal_weight
closed_pole_errors = [
    abs(
        np.linalg.det(
            action_kernel(
                curvature,
                temporal_weight,
                sign * endpoint_frequency,
                0.0,
            )
        )
    )
    for sign in (1.0, -1.0)
]
damped_pole_errors = [
    abs(
        np.linalg.det(
            action_kernel(
                curvature,
                temporal_weight,
                sign * endpoint_frequency - 1j * damping,
                damping,
            )
        )
    )
    for sign in (1.0, -1.0)
]
assert float(np.min(curvature_eigenvalues)) > 0.0
assert max(closed_pole_errors) < TOL, closed_pole_errors
assert abs(omega) <= 0.5 * endpoint_frequency
assert max(damped_pole_errors) < TOL, damped_pole_errors

# AR5: source-action elimination equals both Schur-complement forms.
closed_action = action_kernel(curvature, temporal_weight, omega, 0.0)
closed_energy = energy_kernel(curvature, temporal_weight, omega, 0.0)
closed_response = effective_response(direct_nambu, mixed, closed_action)
energy_form_response = (
    direct_nambu
    + mixed.conjugate().T @ np.linalg.solve(closed_energy, mixed)
)
kernel_sign_error = max_error(closed_action, -closed_energy)
response_form_error = max_error(closed_response, energy_form_response)
solved_endpoint = -np.linalg.solve(closed_action, mixed @ rail_nambu)
energy_form_endpoint = np.linalg.solve(closed_energy, mixed @ rail_nambu)
endpoint_solution_error = max_error(solved_endpoint, energy_form_endpoint)
full_quadratic = (
    0.5 * np.vdot(rail_nambu, direct_nambu @ rail_nambu)
    + 0.5 * np.vdot(solved_endpoint, closed_action @ solved_endpoint)
    + 0.5
    * (
        np.vdot(solved_endpoint, mixed @ rail_nambu)
        + np.vdot(rail_nambu, mixed.conjugate().T @ solved_endpoint)
    )
)
effective_quadratic = 0.5 * np.vdot(
    rail_nambu, closed_response @ rail_nambu
)
elimination_error = abs(full_quadratic - effective_quadratic)
assert kernel_sign_error < TOL, kernel_sign_error
assert response_form_error < TOL, response_form_error
assert endpoint_solution_error < TOL, endpoint_solution_error
assert elimination_error < TOL, elimination_error

gauge = np.diag([phase(frame_angle / 2.0), phase(-frame_angle / 2.0)])
gauge_nambu = np.block(
    [
        [gauge, np.zeros((2, 2), dtype=complex)],
        [np.zeros((2, 2), dtype=complex), gauge.conjugate()],
    ]
)
transformed_yang = phase(frame_angle / 2.0) * yang
transformed_yin = phase(-frame_angle / 2.0) * yin
transformed_alpha = alpha - frame_angle
transformed_mixed = mixed_hessian(
    kappa,
    u_amplitude,
    transformed_alpha,
    transformed_yang,
    transformed_yin,
)
transformed_direct = doubled_link(
    link_matrix(link_strength, transformed_alpha)
)
directly_transformed_response = effective_response(
    transformed_direct,
    transformed_mixed,
    closed_action,
)
covariant_response = (
    gauge_nambu @ closed_response @ gauge_nambu.conjugate().T
)
mixed_covariance_error = max_error(
    transformed_mixed,
    mixed @ gauge_nambu.conjugate().T,
)
response_covariance_error = max_error(
    directly_transformed_response,
    covariant_response,
)
anomalous_norm = float(np.max(np.abs(closed_response[:2, 2:])))
assert mixed_covariance_error < TOL, mixed_covariance_error
assert response_covariance_error < TOL, response_covariance_error
assert anomalous_norm > ANOMALOUS_MIN, anomalous_norm

# AR6: the closed response is Hermitian; damping gives the retarded class.
closed_hermiticity_error = max_error(
    closed_response, closed_response.conjugate().T
)
retarded_action = action_kernel(
    curvature, temporal_weight, omega, damping
)
advanced_action = action_kernel(
    curvature, temporal_weight, omega, -damping
)
retarded_response = effective_response(
    direct_nambu, mixed, retarded_action
)
advanced_response = effective_response(
    direct_nambu, mixed, advanced_action
)
nonhermitian_norm = max_error(
    retarded_response, retarded_response.conjugate().T
)
advanced_error = max_error(
    advanced_response, retarded_response.conjugate().T
)
assert closed_hermiticity_error < TOL, closed_hermiticity_error
assert nonhermitian_norm > NONHERMITIAN_MIN, nonhermitian_norm
assert advanced_error < TOL, advanced_error

print("Cassi source-action charged-endpoint response check")
print(f"  AR1 background residual             = {background_error:.3e}")
print(f"  AR1 closed link current             = {link_current:.3e}")
print(f"  AR2 trilinear reconstruction error  = {polynomial_error:.3e}")
print(f"  AR2 mixed-Hessian error             = {mixed_hessian_error:.3e}")
print(f"  AR2 static action-Hessian error     = {static_hessian_error:.3e}")
print(f"  AR3 positive quartic contribution   = {quartic_low.real:.12e}")
print(f"  AR3 quartic scaling error           = {quartic_error:.3e}")
print(f"  AR4 endpoint pole frequency         = {endpoint_frequency:.12f}")
print(f"  AR4 maximum pole residual           = {max(damped_pole_errors):.3e}")
print(f"  AR5 K/D sign-equivalence residual   = {max(kernel_sign_error, response_form_error, endpoint_solution_error):.3e}")
print(f"  AR5 elimination residual            = {elimination_error:.3e}")
print(f"  AR5 covariance residual             = {response_covariance_error:.3e}")
print(f"  AR5 anomalous-block norm            = {anomalous_norm:.12f}")
print(f"  AR6 closed Hermiticity residual     = {closed_hermiticity_error:.3e}")
print(f"  AR6 damped non-Hermiticity norm     = {nonhermitian_norm:.12f}")
print(f"  AR6 advanced-adjoint residual       = {advanced_error:.3e}")
print("ALL CHECKS PASSED")
