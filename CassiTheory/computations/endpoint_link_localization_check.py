#!/usr/bin/env python3
"""Check the gauge-covariant endpoint and localization-boundary identities."""

import math

PHI = (1.0 + math.sqrt(5.0)) / 2.0
S_PROTON = 91.461618346
TOL = 1e-12


def close(a: complex, b: complex = 0.0) -> bool:
    return abs(a - b) <= TOL * max(1.0, abs(a), abs(b))


def matmul(a: list[list[complex]], b: list[list[complex]]) -> list[list[complex]]:
    return [
        [sum(a[i][k] * b[k][j] for k in range(2)) for j in range(2)]
        for i in range(2)
    ]


def dagger(a: list[list[complex]]) -> list[list[complex]]:
    return [[a[j][i].conjugate() for j in range(2)] for i in range(2)]


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
print("ALL CHECKS PASSED")
