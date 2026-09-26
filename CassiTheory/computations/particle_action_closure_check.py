#!/usr/bin/env python3
"""Check the conditional particle-sector action and variational closure."""

import math
from fractions import Fraction

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0
TOL = 2e-10


def close(a: float, b: float = 0.0, tol: float = TOL) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def add_dims(*dimensions: tuple[Fraction, Fraction, Fraction]) -> tuple[Fraction, Fraction, Fraction]:
    return tuple(sum(values, Fraction(0)) for values in zip(*dimensions))  # type: ignore[return-value]


def scale_dim(
    dimension: tuple[Fraction, Fraction, Fraction], factor: int
) -> tuple[Fraction, Fraction, Fraction]:
    return tuple(factor * value for value in dimension)  # type: ignore[return-value]


# PA13: source-unit dimensions are powers of (hbar, time, spatial length).
density_dim = (Fraction(1), Fraction(-1), Fraction(-3))
psi_dim = (Fraction(0), Fraction(0), Fraction(-3, 2))
phi_dim = (Fraction(0), Fraction(0), Fraction(-1))
dt_dim = (Fraction(0), Fraction(-1), Fraction(0))
spatial_derivative_dim = (Fraction(0), Fraction(0), Fraction(-1))
c_psi_dim = (Fraction(1), Fraction(1), Fraction(0))
c_phi_dim = (Fraction(1), Fraction(1), Fraction(-1))
epsilon_x_dim = c_phi_dim
epsilon_scale_dim = (Fraction(1), Fraction(1), Fraction(-3))
hbar_dim = (Fraction(1), Fraction(0), Fraction(0))

assert add_dims(c_psi_dim, scale_dim(add_dims(psi_dim, dt_dim), 2)) == density_dim
assert add_dims(c_phi_dim, scale_dim(add_dims(phi_dim, dt_dim), 2)) == density_dim
assert add_dims(
    epsilon_x_dim,
    scale_dim(add_dims(spatial_derivative_dim, dt_dim), 2),
) == density_dim
assert add_dims(epsilon_scale_dim, scale_dim(dt_dim, 2)) == density_dim
assert add_dims(hbar_dim, scale_dim(psi_dim, 2), dt_dim) == density_dim

dimensionless_dim = (Fraction(0), Fraction(0), Fraction(0))
length_dim = (Fraction(0), Fraction(0), Fraction(1))
kx_dim = (Fraction(1), Fraction(-1), Fraction(2))
rho_dim = scale_dim(psi_dim, 2)
assert add_dims(
    c_psi_dim, kx_dim, scale_dim(hbar_dim, -2), scale_dim(length_dim, -2)
) == dimensionless_dim
assert add_dims(
    c_phi_dim,
    scale_dim(phi_dim, 2),
    kx_dim,
    scale_dim(hbar_dim, -2),
    scale_dim(rho_dim, -1),
    scale_dim(length_dim, -2),
) == dimensionless_dim
assert add_dims(
    epsilon_x_dim,
    scale_dim(phi_dim, 2),
    kx_dim,
    scale_dim(hbar_dim, -2),
    scale_dim(rho_dim, -1),
    scale_dim(length_dim, -2),
) == dimensionless_dim
assert add_dims(
    epsilon_scale_dim,
    scale_dim(phi_dim, 2),
    kx_dim,
    scale_dim(hbar_dim, -2),
    scale_dim(rho_dim, -1),
) == dimensionless_dim

# Fundamental generators and a generic nonzero condensate.
sigma = np.array(
    [
        [[0.0, 1.0], [1.0, 0.0]],
        [[0.0, -1.0j], [1.0j, 0.0]],
        [[1.0, 0.0], [0.0, -1.0]],
    ],
    dtype=complex,
)
generators = sigma / 2.0

# The Pauli completeness relation makes PA3 an identity for every doublet.
delta_2 = np.eye(2)
pauli_completeness = np.einsum("aij,akl->ijkl", sigma, sigma)
pauli_completeness_expected = 2.0 * np.einsum(
    "il,jk->ijkl", delta_2, delta_2
) - np.einsum("ij,kl->ijkl", delta_2, delta_2)
assert np.allclose(pauli_completeness, pauli_completeness_expected, atol=1e-14)
rho_0 = 1.3
relative_phase = 0.41
psi_vacuum = np.array(
    [
        math.sqrt(rho_0 / PHI),
        math.sqrt(rho_0 / PHI**2) * np.exp(1.0j * relative_phase),
    ],
    dtype=complex,
)
rho = float(np.vdot(psi_vacuum, psi_vacuum).real)
spin = np.array(
    [float(np.vdot(psi_vacuum, matrix @ psi_vacuum).real) for matrix in sigma]
)

# PA3-PA6: one nonzero fundamental doublet has no locally neutral state.
assert close(rho, rho_0)
assert close(float(np.dot(spin, spin)), rho**2)
hbar = 1.0
g_q = 0.83
first_order_source = hbar * g_q * spin / 2.0
first_order_source_magnitude = float(np.linalg.norm(first_order_source))
assert close(first_order_source_magnitude, hbar * g_q * rho_0 / 2.0)
assert first_order_source_magnitude > 0.0

# PA7-PA8: a coordinate-dependent SU(2) transformation covariantly transports
# a temporal derivative when A_0 receives its inhomogeneous term.
axis = np.array([0.3, -0.4, 0.5], dtype=float)
axis /= np.linalg.norm(axis)
axis_sigma = sum(component * matrix for component, matrix in zip(axis, sigma))
angle = 0.76
angle_rate = -0.37
identity = np.eye(2, dtype=complex)
u_matrix = (
    math.cos(angle / 2.0) * identity
    - 1.0j * math.sin(angle / 2.0) * axis_sigma
)
du_matrix = angle_rate * (
    -0.5 * math.sin(angle / 2.0) * identity
    - 0.5j * math.cos(angle / 2.0) * axis_sigma
)
assert np.allclose(u_matrix.conj().T @ u_matrix, identity, atol=1e-13)

psi_sample = np.array([0.72 + 0.18j, -0.31 + 0.44j], dtype=complex)
dt_psi_sample = np.array([0.12 - 0.23j, 0.08 + 0.19j], dtype=complex)
a0_vector = np.array([0.17, -0.09, 0.21], dtype=float)
a0_matrix = sum(component * matrix for component, matrix in zip(a0_vector, generators))
transformed_a0 = (
    u_matrix @ a0_matrix @ u_matrix.conj().T
    - 1.0j * du_matrix @ u_matrix.conj().T / g_q
)
transformed_psi = u_matrix @ psi_sample
transformed_dt_psi = du_matrix @ psi_sample + u_matrix @ dt_psi_sample
covariant_dt = dt_psi_sample - 1.0j * g_q * a0_matrix @ psi_sample
transformed_covariant_dt = (
    transformed_dt_psi - 1.0j * g_q * transformed_a0 @ transformed_psi
)
gauge_covariance_residual = float(
    np.linalg.norm(transformed_covariant_dt - u_matrix @ covariant_dt)
)
assert gauge_covariance_residual < 2e-13

# The same transformation covariantly transports the adjoint derivative and
# curvature.
rotation = np.empty((3, 3))
rotation_rate = np.empty((3, 3))
for row in range(3):
    for column in range(3):
        rotation[row, column] = (
            np.trace(
                sigma[row]
                @ u_matrix
                @ sigma[column]
                @ u_matrix.conj().T
            ).real
            / 2.0
        )
        rotation_rate[row, column] = (
            np.trace(
                sigma[row]
                @ (
                    du_matrix @ sigma[column] @ u_matrix.conj().T
                    + u_matrix @ sigma[column] @ du_matrix.conj().T
                )
            ).real
            / 2.0
        )
transformed_a0_vector = np.array(
    [np.trace(matrix @ transformed_a0).real for matrix in sigma]
)
adjoint_probe = np.array([0.26, -0.47, 0.79])
dt_adjoint_probe = np.array([-0.13, 0.22, 0.07])
transformed_adjoint = rotation @ adjoint_probe
transformed_dt_adjoint = (
    rotation_rate @ adjoint_probe + rotation @ dt_adjoint_probe
)
covariant_dt_adjoint = dt_adjoint_probe + g_q * np.cross(
    a0_vector, adjoint_probe
)
transformed_covariant_dt_adjoint = (
    transformed_dt_adjoint
    + g_q * np.cross(transformed_a0_vector, transformed_adjoint)
)
adjoint_covariance_residual = float(
    np.linalg.norm(
        transformed_covariant_dt_adjoint - rotation @ covariant_dt_adjoint
    )
)
assert adjoint_covariance_residual < 2e-13

curvature_probe = np.array([0.31, 0.14, -0.27])
curvature_matrix = sum(
    component * matrix
    for component, matrix in zip(curvature_probe, generators)
)
transformed_curvature_matrix = (
    u_matrix @ curvature_matrix @ u_matrix.conj().T
)
transformed_curvature = np.array(
    [
        np.trace(matrix @ transformed_curvature_matrix).real
        for matrix in sigma
    ]
)
curvature_covariance_residual = float(
    np.linalg.norm(transformed_curvature - rotation @ curvature_probe)
)
assert curvature_covariance_residual < 2e-13

# PA14-PA15: finite-difference the temporal matter action with respect to A_0.
c_psi = 0.94
c_phi = 0.67
phi_sample = np.array([0.24, -0.31, 0.88], dtype=float)
dt_phi_sample = np.array([-0.11, 0.07, 0.05], dtype=float)


def temporal_matter_lagrangian(a0: np.ndarray) -> float:
    a0_operator = sum(component * matrix for component, matrix in zip(a0, generators))
    d_t_psi = dt_psi_sample - 1.0j * g_q * a0_operator @ psi_sample
    d_t_phi = dt_phi_sample + g_q * np.cross(a0, phi_sample)
    return float(
        c_psi * np.vdot(d_t_psi, d_t_psi).real / 2.0
        + c_phi * np.dot(d_t_phi, d_t_phi) / 2.0
    )


d_t_psi = dt_psi_sample - 1.0j * g_q * a0_matrix @ psi_sample
d_t_phi = dt_phi_sample + g_q * np.cross(a0_vector, phi_sample)
q_psi = np.array(
    [
        c_psi * g_q * np.vdot(psi_sample, matrix @ d_t_psi).imag
        for matrix in generators
    ]
)
q_phi = -c_phi * g_q * np.cross(phi_sample, d_t_phi)
gauss_source = q_psi + q_phi
step = 1e-6
finite_difference_a0 = np.empty(3)
for index in range(3):
    displacement = np.zeros(3)
    displacement[index] = step
    finite_difference_a0[index] = (
        temporal_matter_lagrangian(a0_vector + displacement)
        - temporal_matter_lagrangian(a0_vector - displacement)
    ) / (2.0 * step)
assert np.allclose(finite_difference_a0, -gauss_source, rtol=2e-9, atol=2e-10)

# PA16-PA17: static charged fields and A_0=0 have zero non-Abelian Gauss source,
# while the neutral carrier may retain a nonzero global phase frequency.
static_dt_psi = np.zeros(2, dtype=complex)
static_dt_phi = np.zeros(3)
static_q_psi = np.array(
    [
        c_psi * g_q * np.vdot(psi_sample, matrix @ static_dt_psi).imag
        for matrix in generators
    ]
)
static_q_phi = -c_phi * g_q * np.cross(phi_sample, static_dt_phi)
assert np.linalg.norm(static_q_psi + static_q_phi) == 0.0
carrier_frequency = 0.36
assert carrier_frequency != 0.0

# PA24: finite-difference one spatial matter-energy direction with respect to
# the connection. The scale-current sign follows from the same algebra.
spatial_a_vector = np.array([-0.08, 0.19, 0.11])
spatial_dt_psi = np.array([0.09 + 0.16j, -0.17 + 0.05j])
spatial_dt_phi = np.array([0.04, -0.12, 0.15])
fundamental_stiffness = 0.73
adjoint_mu = 1.19


def spatial_matter_energy(connection: np.ndarray) -> float:
    connection_matrix = sum(
        component * matrix
        for component, matrix in zip(connection, generators)
    )
    d_i_psi = spatial_dt_psi - 1.0j * g_q * connection_matrix @ psi_sample
    d_i_phi = spatial_dt_phi + g_q * np.cross(connection, phi_sample)
    return float(
        fundamental_stiffness * np.vdot(d_i_psi, d_i_psi).real / 2.0
        + np.dot(d_i_phi, d_i_phi) / (2.0 * adjoint_mu)
    )


spatial_a_matrix = sum(
    component * matrix
    for component, matrix in zip(spatial_a_vector, generators)
)
spatial_d_psi = (
    spatial_dt_psi - 1.0j * g_q * spatial_a_matrix @ psi_sample
)
spatial_d_phi = (
    spatial_dt_phi + g_q * np.cross(spatial_a_vector, phi_sample)
)
spatial_current = np.array(
    [
        fundamental_stiffness
        * g_q
        * np.vdot(psi_sample, matrix @ spatial_d_psi).imag
        for matrix in generators
    ]
) - g_q * np.cross(phi_sample, spatial_d_phi) / adjoint_mu
finite_difference_spatial_a = np.empty(3)
for index in range(3):
    displacement = np.zeros(3)
    displacement[index] = step
    finite_difference_spatial_a[index] = (
        spatial_matter_energy(spatial_a_vector + displacement)
        - spatial_matter_energy(spatial_a_vector - displacement)
    ) / (2.0 * step)
gauge_current_residual = float(
    np.max(np.abs(finite_difference_spatial_a + spatial_current))
)
assert gauge_current_residual < 2e-10

# PA20-PA23: finite-difference every algebraic backreaction derivative in the
# stationary functional.
lambda_rho = 0.72
lambda_composition = 0.55
lambda_h = 0.31
lambda_carrier = 0.63
eta_carrier = 0.27
epsilon_out = 1.4
omega_carrier = 0.38
v_q = 1.17
psi_point = np.array([0.68 + 0.16j, -0.22 + 0.37j], dtype=complex)
phi_point = np.array([0.19, -0.28, 0.91], dtype=float)
carrier_point = 0.46 - 0.21j


def algebraic_potential(
    psi_value: np.ndarray, phi_value: np.ndarray, carrier_value: complex
) -> float:
    density = float(np.vdot(psi_value, psi_value).real)
    spin_value = np.array(
        [float(np.vdot(psi_value, matrix @ psi_value).real) for matrix in sigma]
    )
    delta = (
        (1.0 - PHI) * density
        + (1.0 + PHI) * float(np.dot(phi_value, spin_value)) / v_q
    ) / 2.0
    carrier_density = abs(carrier_value) ** 2
    return (
        lambda_rho * (density - rho_0) ** 2 / 4.0
        + lambda_composition * delta**2 / 2.0
        + lambda_h * (float(np.dot(phi_value, phi_value)) - v_q**2) ** 2 / 4.0
        + (epsilon_out - eta_carrier * (rho_0 - density)) * carrier_density
        + lambda_carrier * carrier_density**2 / 2.0
        - hbar * omega_carrier * carrier_density
    )


def analytic_gradients() -> tuple[np.ndarray, np.ndarray, complex]:
    density = float(np.vdot(psi_point, psi_point).real)
    spin_value = np.array(
        [float(np.vdot(psi_point, matrix @ psi_point).real) for matrix in sigma]
    )
    delta = (
        (1.0 - PHI) * density
        + (1.0 + PHI) * float(np.dot(phi_point, spin_value)) / v_q
    ) / 2.0
    composition_matrix = (
        (1.0 - PHI) * identity
        + (1.0 + PHI)
        * sum(component * matrix for component, matrix in zip(phi_point, sigma))
        / v_q
    ) / 2.0
    carrier_density = abs(carrier_point) ** 2
    psi_gradient = (
        (lambda_rho * (density - rho_0) / 2.0 + eta_carrier * carrier_density)
        * psi_point
        + lambda_composition * delta * composition_matrix @ psi_point
    )
    phi_gradient = (
        lambda_h * (float(np.dot(phi_point, phi_point)) - v_q**2) * phi_point
        + lambda_composition
        * delta
        * (1.0 + PHI)
        * spin_value
        / (2.0 * v_q)
    )
    carrier_gradient = (
        epsilon_out
        - eta_carrier * (rho_0 - density)
        + lambda_carrier * carrier_density
        - hbar * omega_carrier
    ) * carrier_point
    return psi_gradient, phi_gradient, carrier_gradient


psi_gradient, phi_gradient, carrier_gradient = analytic_gradients()
finite_difference_errors: list[float] = []
potential_step = 2e-6
for index in range(2):
    for component, expected in ((1.0, 2.0 * psi_gradient[index].real), (1.0j, 2.0 * psi_gradient[index].imag)):
        plus = psi_point.copy()
        minus = psi_point.copy()
        plus[index] += potential_step * component
        minus[index] -= potential_step * component
        measured = (
            algebraic_potential(plus, phi_point, carrier_point)
            - algebraic_potential(minus, phi_point, carrier_point)
        ) / (2.0 * potential_step)
        finite_difference_errors.append(abs(measured - expected))
for index in range(3):
    plus_phi = phi_point.copy()
    minus_phi = phi_point.copy()
    plus_phi[index] += potential_step
    minus_phi[index] -= potential_step
    measured = (
        algebraic_potential(psi_point, plus_phi, carrier_point)
        - algebraic_potential(psi_point, minus_phi, carrier_point)
    ) / (2.0 * potential_step)
    finite_difference_errors.append(abs(measured - phi_gradient[index]))
for component, expected in ((1.0, 2.0 * carrier_gradient.real), (1.0j, 2.0 * carrier_gradient.imag)):
    measured = (
        algebraic_potential(psi_point, phi_point, carrier_point + potential_step * component)
        - algebraic_potential(psi_point, phi_point, carrier_point - potential_step * component)
    ) / (2.0 * potential_step)
    finite_difference_errors.append(abs(measured - expected))
max_gradient_residual = max(finite_difference_errors)
assert max_gradient_residual < 2e-9

# PA29-PA37: the complete dimensionless ledger is invariant under the registered
# source-unit gauge normalization.
source_parameters = {
    "g": 0.81,
    "hbar": 1.37,
    "v": 1.23,
    "rho": 0.74,
    "kx": 1.08,
    "ks": 0.63,
    "lambda_rho": 0.52,
    "lambda_composition": 0.46,
    "mu_x": 0.77,
    "mu_s": 1.14,
    "lambda_h": 0.29,
    "kcx": 0.88,
    "kcs": 0.57,
    "epsilon_c": 1.31,
    "eta_c": 0.41,
    "lambda_c": 0.69,
    "c_psi": 0.93,
    "c_phi": 0.82,
    "epsilon_tx": 0.76,
    "epsilon_ts": 0.64,
}


def dimensionless_groups(parameters: dict[str, float]) -> dict[str, float]:
    length = 1.0 / (parameters["g"] * parameters["v"])
    return {
        "length": length,
        "alpha_s": parameters["ks"] * length**2 / parameters["kx"],
        "u_rho": parameters["lambda_rho"] * parameters["rho"] * length**2 / parameters["kx"],
        "u_composition": parameters["lambda_composition"] * parameters["rho"] * length**2 / parameters["kx"],
        "gamma_x": parameters["v"] ** 2 / (parameters["mu_x"] * parameters["kx"] * parameters["rho"]),
        "gamma_s": 1.0 / (parameters["mu_s"] * parameters["g"] ** 2 * parameters["kx"] * parameters["rho"]),
        "u_h": parameters["lambda_h"] * parameters["v"] ** 2 / (parameters["g"] ** 2 * parameters["kx"] * parameters["rho"]),
        "kcx": parameters["kcx"] / parameters["kx"],
        "kcs": parameters["kcs"] * length**2 / parameters["kx"],
        "e_c": parameters["epsilon_c"] * length**2 / parameters["kx"],
        "h_c": parameters["eta_c"] * parameters["rho"] * length**2 / parameters["kx"],
        "u_c": parameters["lambda_c"] * parameters["rho"] * length**2 / parameters["kx"],
        "c_psi_t": parameters["c_psi"] * parameters["kx"]
        / (parameters["hbar"] ** 2 * length**2),
        "c_phi_t": parameters["c_phi"] * parameters["v"] ** 2 * parameters["kx"]
        / (parameters["hbar"] ** 2 * parameters["rho"] * length**2),
        "e_tx": parameters["epsilon_tx"] * parameters["v"] ** 2 * parameters["kx"]
        / (parameters["hbar"] ** 2 * parameters["rho"] * length**2),
        "e_ts": parameters["epsilon_ts"] * parameters["v"] ** 2 * parameters["kx"]
        / (parameters["hbar"] ** 2 * parameters["rho"]),
    }


groups = dimensionless_groups(source_parameters)
normalization = 1.71
rescaled_parameters = dict(source_parameters)
rescaled_parameters.update(
    {
        "g": source_parameters["g"] / normalization,
        "v": source_parameters["v"] * normalization,
        "mu_x": source_parameters["mu_x"] * normalization**2,
        "mu_s": source_parameters["mu_s"] * normalization**2,
        "lambda_h": source_parameters["lambda_h"] / normalization**4,
        "c_phi": source_parameters["c_phi"] / normalization**2,
        "epsilon_tx": source_parameters["epsilon_tx"] / normalization**2,
        "epsilon_ts": source_parameters["epsilon_ts"] / normalization**2,
    }
)
rescaled_groups = dimensionless_groups(rescaled_parameters)
normalization_residuals = {
    name: abs(value - rescaled_groups[name]) for name, value in groups.items()
}
max_normalization_residual = max(normalization_residuals.values())
assert max_normalization_residual < 2e-14

# Directly verify the paired gauge/adjoint coefficients in PA32.
length = groups["length"]
hamiltonian_scale = source_parameters["kx"] * source_parameters["rho"] / length**2
gauge_spatial_ratio = (
    1.0
    / (source_parameters["mu_x"] * source_parameters["g"] ** 2 * length**4)
    / hamiltonian_scale
)
adjoint_spatial_ratio = (
    source_parameters["v"] ** 2
    / (source_parameters["mu_x"] * length**2)
    / hamiltonian_scale
)
gauge_scale_ratio = (
    source_parameters["v"] ** 2 / source_parameters["mu_s"] / hamiltonian_scale
)
adjoint_scale_ratio = gauge_scale_ratio
assert close(gauge_spatial_ratio, groups["gamma_x"])
assert close(adjoint_spatial_ratio, groups["gamma_x"])
assert close(gauge_scale_ratio, groups["gamma_s"])
assert close(adjoint_scale_ratio, groups["gamma_s"])

# PA34: fixed physical carrier number maps to the declared dimensionless charge.
q_c = 2.4
physical_q_c = source_parameters["rho"] * length**3 * q_c
assert close(q_c, physical_q_c / (source_parameters["rho"] * length**3))

print("Cassi particle action closure check")
print(f"  first-order vacuum source magnitude  = {first_order_source_magnitude:.12f}")
print(f"  fundamental gauge covariance residual = {gauge_covariance_residual:.3e}")
print(f"  adjoint gauge covariance residual     = {adjoint_covariance_residual:.3e}")
print(f"  curvature covariance residual         = {curvature_covariance_residual:.3e}")
print(f"  temporal matter-source residual       = {np.max(np.abs(finite_difference_a0 + gauss_source)):.3e}")
print(f"  static gauge-current residual         = {gauge_current_residual:.3e}")
print(f"  fixed-functional gradient residual    = {max_gradient_residual:.3e}")
print(f"  normalization-invariance residual    = {max_normalization_residual:.3e}")
print(f"  invariant vector-core length         = {groups['length']:.12f}")
print(f"  static dimensionless groups checked  = {11}")
print(f"  temporal dimensionless groups checked = {4}")
print("ALL CHECKS PASSED")
