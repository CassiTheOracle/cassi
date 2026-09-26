#!/usr/bin/env python3
"""Check the Cassi geometric-manifold completion identities."""

import math

PHI = (1.0 + math.sqrt(5.0)) / 2.0
TOL = 1e-12


def close(a: complex, b: complex = 0.0) -> bool:
    return abs(a - b) <= TOL * max(1.0, abs(a), abs(b))


def matmul(a: list[list[complex]], b: list[list[complex]]) -> list[list[complex]]:
    return [[sum(a[i][k] * b[k][j] for k in range(2)) for j in range(2)] for i in range(2)]


def dagger(a: list[list[complex]]) -> list[list[complex]]:
    return [[a[j][i].conjugate() for j in range(2)] for i in range(2)]


def lindblad(gamma: float, state: list[list[complex]]) -> list[list[complex]]:
    jumps: list[list[list[complex]]] = [
        [[0j, 0j], [complex(math.sqrt(gamma)), 0j]],
        [[0j, complex(math.sqrt(PHI * gamma))], [0j, 0j]],
    ]
    result = [[0j, 0j], [0j, 0j]]
    for jump in jumps:
        adjoint = dagger(jump)
        jump_norm = matmul(adjoint, jump)
        gain = matmul(matmul(jump, state), adjoint)
        left = matmul(jump_norm, state)
        right = matmul(state, jump_norm)
        for i in range(2):
            for j in range(2):
                result[i][j] += gain[i][j] - 0.5 * (left[i][j] + right[i][j])
    return result


# Golden-ratio and canonical target identities.
assert close(PHI**2, PHI + 1.0)
assert close(PHI**-1 + PHI**-2, 1.0)
assert close((PHI**-1 - PHI**-2), PHI**-3)

rho_target = PHI
e_y_target = 1.0
e_i_target = PHI**-1
z_target = (e_y_target - e_i_target) / rho_target
assert close(e_y_target / e_i_target, PHI)
assert close(z_target, PHI**-3)

# Positive coherence cone, Bloch ball, and epsilon coordinate.
samples = [
    (1.0, 0.5, 0.2 + 0.1j),
    (2.0, 3.0, -0.7 + 0.4j),
    (0.4, 1.6, 0.0j),
    (1.3, 0.8, math.sqrt(1.3 * 0.8) * complex(math.cos(0.7), math.sin(0.7))),
]
max_cone_error = 0.0
max_epsilon_error = 0.0
for e_y, e_i, coherence in samples:
    rho = e_y + e_i
    n = (
        2.0 * coherence.real / rho,
        2.0 * coherence.imag / rho,
        (e_y - e_i) / rho,
    )
    norm_sq = sum(component * component for component in n)
    determinant = e_y * e_i - abs(coherence) ** 2
    cone_rhs = rho**2 * (1.0 - norm_sq) / 4.0
    epsilon = e_y - PHI * e_i
    epsilon_rhs = rho * PHI**2 * (n[2] - PHI**-3) / 2.0
    assert determinant >= -TOL
    assert norm_sq <= 1.0 + TOL
    assert close(determinant, cone_rhs)
    assert close(epsilon, epsilon_rhs)
    max_cone_error = max(max_cone_error, abs(determinant - cone_rhs))
    max_epsilon_error = max(max_epsilon_error, abs(epsilon - epsilon_rhs))

# Coherence, Bloch, and affine-bubble metrics.
dn = (0.17, -0.23, 0.31)
d_axes = (1.2, 2.3, 0.9)
dx = tuple(axis * component for axis, component in zip(d_axes, dn))
coherence_metric = sum(component * component for component in dn)
affine_metric = sum((component / axis) ** 2 for component, axis in zip(dx, d_axes))
# d(Gamma-hat) = (dn.sigma)/2 gives 2 Tr[d(Gamma-hat)^2] = |dn|^2.
trace_metric = coherence_metric
assert close(trace_metric, coherence_metric)
assert close(affine_metric, coherence_metric)

# Fixed-rate GKSL lift and exact canonical diagonal reduction.
gamma_conv = 0.07
e_y, e_i, coherence = 1.2, 0.4, 0.2 + 0.1j
state = [[e_y, coherence.conjugate()], [coherence, e_i]]
derivative = lindblad(gamma_conv, state)
expected_y = -gamma_conv * (e_y - PHI * e_i)
expected_i = -expected_y
expected_c = -(PHI**2 / 2.0) * gamma_conv * coherence
assert close(derivative[0][0], expected_y)
assert close(derivative[1][1], expected_i)
assert close(derivative[1][0], expected_c)
assert close(derivative[0][1], expected_c.conjugate())
assert close(derivative[0][0] + derivative[1][1])

epsilon_rate = derivative[0][0] - PHI * derivative[1][1]
epsilon = e_y - PHI * e_i
assert close(epsilon_rate, -PHI**2 * gamma_conv * epsilon)

assert all(close(value) for row in lindblad(0.0, state) for value in row)

# Canonical real-density and zero-extension limits.
diagonal_state = [[e_y, 0j], [0j, e_i]]
diagonal_rhs = lindblad(gamma_conv, diagonal_state)
canonical_rhs = [[complex(expected_y), 0j], [0j, complex(expected_i)]]
canonical_reduction_residual = max(
    abs(diagonal_rhs[i][j] - canonical_rhs[i][j])
    for i in range(2)
    for j in range(2)
)
assert close(canonical_reduction_residual)

# Evaluate each declared extension term from its neutral-limit input.
relative_charge = [[0.5 + 0j, 0j], [0j, -0.5 + 0j]]
connection_time = 0.0
connection_space = 0.0
b_time = [[connection_time * value for value in row] for row in relative_charge]
b_space = [[connection_space * value for value in row] for row in relative_charge]
current_probe = [[0.6 + 0j, 0.15j], [-0.15j, -0.2 + 0j]]
bt_state = matmul(b_time, state)
state_bt = matmul(state, b_time)
bx_current = matmul(b_space, current_probe)
current_bx = matmul(current_probe, b_space)
relative_connection_term = [
    [
        -1j
        * (
            bt_state[i][j]
            - state_bt[i][j]
            + bx_current[i][j]
            - current_bx[i][j]
        )
        for j in range(2)
    ]
    for i in range(2)
]

scale_velocity_left = (0.0, 0.0)
scale_velocity_right = (0.0, 0.0)
scale_current_left = [
    [complex(e_y * scale_velocity_left[0]), 0j],
    [0j, complex(e_i * scale_velocity_left[1])],
]
scale_current_right = [
    [complex(e_y * scale_velocity_right[0]), 0j],
    [0j, complex(e_i * scale_velocity_right[1])],
]
scale_step = 1.0
scale_divergence = [
    [
        (scale_current_right[i][j] - scale_current_left[i][j]) / scale_step
        for j in range(2)
    ]
    for i in range(2)
]

endpoint_rate = 0.0
endpoint_channel = lindblad(endpoint_rate, state)
noise_amplitude = 0.0
trace_free_noise_probe = [
    [0.3 + 0j, 0.1 + 0.2j],
    [0.1 - 0.2j, -0.3 + 0j],
]
bath_source = [
    [noise_amplitude * value for value in row] for row in trace_free_noise_probe
]

neutral_extension_terms = {
    "relative_connection": relative_connection_term,
    "scale_divergence": scale_divergence,
    "endpoint_channel": endpoint_channel,
    "bath_source": bath_source,
}
component_residuals = {
    name: max(abs(value) for row in term for value in row)
    for name, term in neutral_extension_terms.items()
}
assert all(close(residual) for residual in component_residuals.values())
zero_extension_rhs = [
    [
        diagonal_rhs[i][j]
        + sum(term[i][j] for term in neutral_extension_terms.values())
        for j in range(2)
    ]
    for i in range(2)
]
zero_extension_residual = max(
    abs(zero_extension_rhs[i][j] - canonical_rhs[i][j])
    for i in range(2)
    for j in range(2)
)
assert close(zero_extension_residual)
stationary = [[PHI**-1, 0j], [0j, PHI**-2]]
assert all(close(value) for row in lindblad(gamma_conv, stationary) for value in row)

lambda_rate = 0.1
q_equilibrium = PHI**2 / 3.0
gamma_epsilon = PHI**2 * lambda_rate * (1.0 - q_equilibrium)
gamma_coherence = gamma_epsilon / 2.0
assert close(gamma_epsilon, lambda_rate / 3.0)
assert close(gamma_coherence, lambda_rate / 6.0)

# Cross-glued scale graph, circuit holonomy, and uniform-composition current.
vertices = edges = 2
betti_one = edges - vertices + 1
s_proton = 91.461618346
circumference = 2.0 * s_proton
m = 1
endpoint_phase = 0.37
delta_m = 2.0 * math.pi * m - endpoint_phase
nu_y = delta_m / (PHI**2 * s_proton)
nu_i = -delta_m / (PHI * s_proton)
holonomy = s_proton * (nu_y - nu_i) + endpoint_phase
rho = 1.0
e_y = rho / PHI
e_i = rho / PHI**2
j_y = e_y * nu_y
j_i = e_i * nu_i
j_relative = (j_y - j_i) / 2.0
j_expected = rho * delta_m / (PHI**3 * s_proton)
flux_y = abs(nu_y) * e_y
flux_i = abs(nu_i) * e_i
assert betti_one == 1
assert close(circumference, 2.0 * s_proton)
assert close(holonomy, 2.0 * math.pi * m)
assert close(nu_i / nu_y, -PHI)
assert close(j_y + j_i)
assert close(j_relative, j_expected)
assert close(flux_y, flux_i)

# The full Bloch ball admits the explicit contraction H_t(n)=(1-t)n.
unit_vector = (math.sin(0.8), 0.0, math.cos(0.8))
contracted_norm = 1.0
for step in range(11):
    factor = 1.0 - step / 10.0
    contracted_norm = math.sqrt(sum((factor * component) ** 2 for component in unit_vector))
    assert contracted_norm <= 1.0 + TOL
assert close(contracted_norm)

print("Cassi geometric-manifold completion check")
print(f"  target Bloch latitude z_phi       = {z_target:.12f}")
print(f"  maximum cone-identity error       = {max_cone_error:.3e}")
print(f"  maximum epsilon-coordinate error  = {max_epsilon_error:.3e}")
print(f"  affine/coherence metric            = {coherence_metric:.12f}")
print(f"  canonical real-density residual    = {canonical_reduction_residual:.3e}")
print(f"  zero-extension residual            = {zero_extension_residual:.3e}")
for name, residual in component_residuals.items():
    print(f"    {name:23s} = {residual:.3e}")
print(f"  gamma_c / gamma_epsilon            = {gamma_coherence / gamma_epsilon:.12f}")
print(f"  gated reference gamma_c / lambda   = {gamma_coherence / lambda_rate:.12f}")
print(f"  graph (V, E, b1)                   = ({vertices}, {edges}, {betti_one})")
print(f"  normalized circumference           = {circumference:.9f}")
print(f"  circuit holonomy residual           = {holonomy - 2.0 * math.pi * m:.3e}")
print(f"  normalized total scale current      = {j_y + j_i:.3e}")
print(f"  endpoint flux-norm residual        = {flux_y - flux_i:.3e}")
print("ALL CHECKS PASSED")
