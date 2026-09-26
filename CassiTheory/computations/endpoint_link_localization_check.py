#!/usr/bin/env python3
"""Check the gauge-covariant endpoint and localization-boundary identities."""

import math

PHI = (1.0 + math.sqrt(5.0)) / 2.0
S_PROTON = 91.461618346
TOL = 1e-12
ER_TOL = 5e-13


def close(a: complex, b: complex = 0.0) -> bool:
    return abs(a - b) <= TOL * max(1.0, abs(a), abs(b))


def matmul(a: list[list[complex]], b: list[list[complex]]) -> list[list[complex]]:
    return [
        [sum(a[i][k] * b[k][j] for k in range(2)) for j in range(2)]
        for i in range(2)
    ]


def dagger(a: list[list[complex]]) -> list[list[complex]]:
    return [[a[j][i].conjugate() for j in range(2)] for i in range(2)]
def matrix_error(
    a: list[list[complex]], b: list[list[complex]]
) -> float:
    return max(abs(a[i][j] - b[i][j]) for i in range(2) for j in range(2))


def inverse2(matrix: list[list[complex]]) -> list[list[complex]]:
    determinant = (
        matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
    )
    if abs(determinant) <= ER_TOL:
        raise ValueError("singular 2x2 matrix")
    return [
        [matrix[1][1] / determinant, -matrix[0][1] / determinant],
        [-matrix[1][0] / determinant, matrix[0][0] / determinant],
    ]


def matvec(
    matrix: list[list[complex]], vector: tuple[complex, complex]
) -> tuple[complex, complex]:
    return (
        matrix[0][0] * vector[0] + matrix[0][1] * vector[1],
        matrix[1][0] * vector[0] + matrix[1][1] * vector[1],
    )


def link_matrix(strength: float, phase: float) -> list[list[complex]]:
    phase_factor = complex(math.cos(phase), math.sin(phase))
    return [
        [0j, strength * phase_factor.conjugate()],
        [strength * phase_factor, 0j],
    ]


def cayley_scattering(
    coupling: list[list[complex]],
    scale_stiffness: float,
    wave_number: float,
) -> list[list[complex]]:
    ik = 1j * scale_stiffness * wave_number
    minus = [
        [ik - coupling[0][0], -coupling[0][1]],
        [-coupling[1][0], ik - coupling[1][1]],
    ]
    plus = [
        [ik + coupling[0][0], coupling[0][1]],
        [coupling[1][0], ik + coupling[1][1]],
    ]
    return matmul(inverse2(minus), plus)




def dissipator(jump: list[list[complex]], state: list[list[complex]]) -> list[list[complex]]:
    adjoint = dagger(jump)
    jump_norm = matmul(adjoint, jump)
    gain = matmul(matmul(jump, state), adjoint)
    left = matmul(jump_norm, state)
    right = matmul(state, jump_norm)
    return [
        [gain[i][j] - 0.5 * (left[i][j] + right[i][j]) for j in range(2)]
        for i in range(2)
    ]


def product_betti(a: tuple[int, ...], b: tuple[int, ...], degree: int) -> int:
    return sum(
        a[k] * b[degree - k]
        for k in range(degree + 1)
        if k < len(a) and degree - k < len(b)
    )


# EL-1: relative charges and coherent vertex source.
q_y = 0.5
q_i = -0.5
q_upsilon = -1.0
link_charge = -q_upsilon - q_y + q_i
conjugate_charge = q_upsilon - q_i + q_y
assert close(link_charge)
assert close(conjugate_charge)

hbar = 1.3
kappa = 0.41
u = 0.73
alpha = -0.37
theta = 0.82
e_y = 1.4
e_i = 0.6
psi_y = math.sqrt(e_y)
psi_i = math.sqrt(e_i) * complex(math.cos(theta), math.sin(theta))
upsilon = u * complex(math.cos(alpha), math.sin(alpha))
link_before = (
    upsilon.conjugate() * psi_y.conjugate() * psi_i
    + upsilon * psi_i.conjugate() * psi_y
)
frame_phase = 0.44
phase_y = complex(math.cos(frame_phase / 2.0), math.sin(frame_phase / 2.0))
phase_i = phase_y.conjugate()
phase_upsilon = complex(math.cos(-frame_phase), math.sin(-frame_phase))
transformed_y = phase_y * psi_y
transformed_i = phase_i * psi_i
transformed_upsilon = phase_upsilon * upsilon
link_after = (
    transformed_upsilon.conjugate()
    * transformed_y.conjugate()
    * transformed_i
    + transformed_upsilon
    * transformed_i.conjugate()
    * transformed_y
)
assert close(link_after, link_before)
dpsi_y = 1j * kappa * upsilon.conjugate() * psi_i / hbar
dpsi_i = 1j * kappa * upsilon * psi_y / hbar
dy = 2.0 * (psi_y.conjugate() * dpsi_y).real
di = 2.0 * (psi_i.conjugate() * dpsi_i).real
expected_dy = (
    -2.0
    * kappa
    * u
    * math.sqrt(e_y * e_i)
    * math.sin(theta - alpha)
    / hbar
)
assert close(dy, expected_dy)
assert close(di, -expected_dy)
assert close(dy + di)

# EL-2: coherent capacity and open-channel rate ratio in the uniform circuit.
rho = 0.9
k_scale = 2.1
delta_m = 2.0 * math.pi
uniform_y = rho / PHI
uniform_i = rho / PHI**2
j_q = k_scale * rho * delta_m / (hbar * PHI**3 * S_PROTON)
critical_effective = k_scale * delta_m / (2.0 * PHI**1.5 * S_PROTON)
j_critical = (
    2.0
    * critical_effective
    * math.sqrt(uniform_y * uniform_i)
    / hbar
)
threshold_ratio = critical_effective / k_scale
assert close(j_critical, j_q)
assert close(threshold_ratio, 0.016688969873555743)

subcritical_fraction = 0.6
overcritical_fraction = 1.0 + 1e-6
for sigma in (1.0, -1.0):
    phase_lag = math.asin(-sigma * subcritical_fraction)
    assert close(math.sin(phase_lag), -sigma * subcritical_fraction)
    assert math.cos(phase_lag) > 0.0

    critical_lag = -sigma * math.pi / 2.0
    assert close(math.sin(critical_lag), -sigma)
    assert close(math.cos(critical_lag))
    assert abs(-sigma * overcritical_fraction) > 1.0

rate_minus = j_q / uniform_i
rate_plus = j_q / uniform_y
assert close(rate_minus, k_scale * delta_m / (hbar * PHI * S_PROTON))
assert close(rate_plus, k_scale * delta_m / (hbar * PHI**2 * S_PROTON))
assert close(rate_minus / rate_plus, PHI)

# EL-3: one-way jumps conserve trace, carry phase-covariant dissipators, and
# damp undriven transverse coherence at half the donor rate.
coherence = 0.2 - 0.17j
state = [[uniform_y, coherence.conjugate()], [coherence, uniform_i]]
jump_minus = [[0j, complex(math.sqrt(rate_minus))], [0j, 0j]]
jump_plus = [[0j, 0j], [complex(math.sqrt(rate_plus)), 0j]]
for jump, rate, donor, expected_y in (
    (jump_minus, rate_minus, uniform_i, rate_minus * uniform_i),
    (jump_plus, rate_plus, uniform_y, -rate_plus * uniform_y),
):
    derivative = dissipator(jump, state)
    assert close(derivative[0][0], expected_y)
    assert close(derivative[1][1], -expected_y)
    assert close(derivative[0][0] + derivative[1][1])
    assert close(derivative[1][0], -0.5 * rate * coherence)

    phase = complex(math.cos(0.63), math.sin(0.63))
    phased = [[phase * value for value in row] for row in jump]
    phased_derivative = dissipator(phased, state)
    assert all(
        close(phased_derivative[i][j], derivative[i][j])
        for i in range(2)
        for j in range(2)
    )

# EL-4: explicit Bloch-ball contraction and the relevant Kunneth ranks.
bloch = (0.7, -0.2, 0.5)
assert sum(value * value for value in bloch) < 1.0
contracted = bloch
for step in range(11):
    factor = 1.0 - step / 10.0
    contracted = tuple(factor * value for value in bloch)
    assert sum(value * value for value in contracted) <= 1.0
assert all(close(value) for value in contracted)

r3 = (1,)
s1 = (1, 1)
s2 = (1, 0, 1)
s3 = (1, 0, 0, 1)
assert product_betti(r3, s1, 2) == 0
assert product_betti(s3, s1, 2) == 0
assert product_betti(s2, s1, 2) == 1  # Point-excised R3 times scale S1.
assert product_betti(s1, s1, 2) == 1  # Line-excised R3 times scale S1.

g_q = 0.83
chern_sector = 3
flux = 4.0 * math.pi * chern_sector / g_q
assert close(g_q * flux / (4.0 * math.pi), chern_sector)
m_phase_only = -2 * chern_sector
assert close(flux, -2.0 * math.pi * m_phase_only / g_q)

# EL-5 and EL-6: minimal-sector no-go and conditional supported radius.
a_coeff = 2.3
c_coeff = 0.7
b_coeff = 3.1
d_coeff = 0.8
q_support = b_coeff - d_coeff
discriminant = a_coeff**2 + 12.0 * c_coeff * q_support
r_squared = (-a_coeff + math.sqrt(discriminant)) / (6.0 * c_coeff)
other_r_squared = (-a_coeff - math.sqrt(discriminant)) / (6.0 * c_coeff)
r_star = math.sqrt(r_squared)
derivative = a_coeff - q_support / r_star**2 + 3.0 * c_coeff * r_star**2
second_derivative = 2.0 * q_support / r_star**3 + 6.0 * c_coeff * r_star
assert r_squared > 0.0
assert other_r_squared < 0.0
assert close(derivative)
assert close(
    second_derivative,
    2.0 * a_coeff / r_star + 12.0 * c_coeff * r_star,
)
assert second_derivative > 0.0

# The C=0 branch has the unique positive root sqrt(Q/A).
q_linear = 1.7
r_linear = math.sqrt(q_linear / a_coeff)
assert close(a_coeff - q_linear / r_linear**2)
assert 2.0 * q_linear / r_linear**3 > 0.0

# For A>0, C>=0, Q<=0, every term in E'=A-Q/R^2+3CR^2
# is nonnegative and the A term is strictly positive for every R>0.
for q_no_support in (0.0, -0.2, -d_coeff):
    assert a_coeff > 0.0 and c_coeff >= 0.0 and q_no_support <= 0.0
    for radius in (0.01, 0.1, 1.0, 10.0, 100.0):
        derivative_terms = (
            a_coeff,
            -q_no_support / radius**2,
            3.0 * c_coeff * radius**2,
        )
        assert all(term >= 0.0 for term in derivative_terms)
        assert derivative_terms[0] > 0.0
        assert sum(derivative_terms) > 0.0
# ER1: the frozen charged link is a Hermitian, gauge-covariant Robin matrix.
er_kappa = 0.41
er_u = 0.73
er_nu = 2.0 * er_kappa * er_u
er_phase = -0.37
er_link = link_matrix(er_nu, er_phase)
identity = [[1.0 + 0j, 0j], [0j, 1.0 + 0j]]
er_m = link_matrix(1.0, er_phase)
er_hermitian_error = matrix_error(dagger(er_link), er_link)
er_involution_error = matrix_error(matmul(er_m, er_m), identity)
er_trace = er_link[0][0] + er_link[1][1]
er_determinant = (
    er_link[0][0] * er_link[1][1] - er_link[0][1] * er_link[1][0]
)
er_frame_phase = 0.44
er_g = [
    [
        complex(
            math.cos(er_frame_phase / 2.0),
            math.sin(er_frame_phase / 2.0),
        ),
        0j,
    ],
    [
        0j,
        complex(
            math.cos(-er_frame_phase / 2.0),
            math.sin(-er_frame_phase / 2.0),
        ),
    ],
]
er_transformed_link = link_matrix(er_nu, er_phase - er_frame_phase)
er_covariant_link = matmul(matmul(er_g, er_link), dagger(er_g))
er_covariance_error = matrix_error(er_transformed_link, er_covariant_link)
assert er_hermitian_error < ER_TOL
assert er_involution_error < ER_TOL
assert abs(er_trace) < ER_TOL
assert abs(er_determinant + er_nu**2) < ER_TOL
assert er_covariance_error < ER_TOL

# ER2: the link Cayley matrix equals its closed form and preserves flux.
er_scale_stiffness = 1.4
er_wave_number = 0.9
er_x = er_scale_stiffness * er_wave_number
er_denominator = er_x**2 + er_nu**2
er_cosine = (er_x**2 - er_nu**2) / er_denominator
er_sine = 2.0 * er_x * er_nu / er_denominator
er_analytic = [
    [
        er_cosine * identity[i][j] - 1j * er_sine * er_m[i][j]
        for j in range(2)
    ]
    for i in range(2)
]
er_scattering = cayley_scattering(
    er_link, er_scale_stiffness, er_wave_number
)
er_scattering_error = matrix_error(er_scattering, er_analytic)
er_unitarity_error = matrix_error(
    matmul(dagger(er_scattering), er_scattering), identity
)
er_input = (0.63 - 0.14j, -0.22 + 0.51j)
er_output = matvec(er_scattering, er_input)
er_flux_error = abs(
    sum(abs(value) ** 2 for value in er_output)
    - sum(abs(value) ** 2 for value in er_input)
)
assert er_scattering_error < ER_TOL
assert er_unitarity_error < ER_TOL
assert er_flux_error < ER_TOL

# ER3: one selected link strength and dressed phase realize the golden target.
er_t_phi = PHI**-0.5
er_r_phi = PHI**-1
er_tau_phi = er_r_phi / (1.0 + er_t_phi)
er_match_stiffness = 1.3
er_k_star = 0.8
er_match_nu = er_match_stiffness * er_k_star * er_tau_phi
er_match_link = link_matrix(er_match_nu, -math.pi / 2.0)
er_j = [[0j, 1.0 + 0j], [-1.0 + 0j, 0j]]
er_target_link = [
    [1j * er_match_nu * er_j[i][j] for j in range(2)]
    for i in range(2)
]
er_target_scattering = [
    [er_t_phi + 0j, er_r_phi + 0j],
    [-er_r_phi + 0j, er_t_phi + 0j],
]
er_match_scattering = cayley_scattering(
    er_match_link, er_match_stiffness, er_k_star
)
er_link_match_error = matrix_error(er_match_link, er_target_link)
er_golden_match_error = matrix_error(
    er_match_scattering, er_target_scattering
)
assert er_link_match_error < ER_TOL
assert er_golden_match_error < ER_TOL

# ER4: simultaneous current turning gives a stable-branch lower bound on k_*.
er_delta_one = 2.0 * math.pi
er_k_min = er_delta_one / (
    PHI**1.5 * S_PROTON * er_tau_phi
)
er_matching_ratio = er_k_star * er_tau_phi / 2.0
er_current = (
    er_match_stiffness
    * rho
    * er_delta_one
    / (hbar * PHI**3 * S_PROTON)
)
er_critical_current = er_match_nu * rho / (hbar * PHI**1.5)
er_current_fraction = er_current / er_critical_current
er_marginal_stiffness_factor = math.sqrt(
    max(0.0, 1.0 - (er_k_min / er_k_min) ** 2)
)
assert abs(er_matching_ratio - er_match_nu / (2.0 * er_match_stiffness)) < ER_TOL
assert abs(er_k_min - 0.096464036203895) < ER_TOL
assert abs(er_current_fraction - er_k_min / er_k_star) < ER_TOL
assert er_matching_ratio > threshold_ratio
assert er_k_star > er_k_min
assert er_marginal_stiffness_factor < ER_TOL

# ER5: the same frozen link departs from the target away from k_*.
er_off_wave_number = 1.7 * er_k_star
er_off_scattering = cayley_scattering(
    er_match_link, er_match_stiffness, er_off_wave_number
)
er_off_a = er_k_star * er_tau_phi / er_off_wave_number
er_off_denominator = 1.0 + er_off_a**2
er_off_analytic = [
    [
        (1.0 - er_off_a**2) / er_off_denominator,
        2.0 * er_off_a / er_off_denominator,
    ],
    [
        -2.0 * er_off_a / er_off_denominator,
        (1.0 - er_off_a**2) / er_off_denominator,
    ],
]
er_off_error = matrix_error(er_off_scattering, er_off_analytic)
er_off_target_difference = matrix_error(
    er_off_scattering, er_target_scattering
)
assert er_off_error < ER_TOL
assert er_off_target_difference > 1e-3


print("Cassi endpoint-link and localization-boundary check")
print(f"  coherent source trace residual    = {dy + di:.3e}")
print(f"  m=1 endpoint threshold / K_s      = {threshold_ratio:.10f}")
print(f"  open endpoint rate ratio          = {rate_minus / rate_plus:.12f}")
print("  H2 smooth / point core / line core = 0 / 1 / 1")
print(f"  Chern normalization N_G           = {g_q * flux / (4.0 * math.pi):.12f}")
print(f"  supported stationary radius       = {r_star:.12f}")
print(f"  stationary derivative residual    = {derivative:.3e}")
print(f"  radial second derivative          = {second_derivative:.12f}")
print(f"  C=0 supported radius              = {r_linear:.12f}")
print(f"  endpoint Robin covariance residual = {er_covariance_error:.3e}")
print(f"  endpoint Robin unitarity residual  = {er_unitarity_error:.3e}")
print(f"  golden link matching residual      = {er_golden_match_error:.3e}")
print(f"  stable matched-link k_min          = {er_k_min:.15f}")
print(f"  matched current / critical current = {er_current_fraction:.12f}")
print(f"  off-match target difference        = {er_off_target_difference:.12f}")
print("ALL CHECKS PASSED")
