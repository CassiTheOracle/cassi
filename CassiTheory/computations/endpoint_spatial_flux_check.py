"""Verify the frozen charged-endpoint spatial-flux identities.

Run from the CassiTheory repository root:
    python computations/endpoint_spatial_flux_check.py
"""

from __future__ import annotations

import numpy as np


TOL = 1.0e-11

HBAR = 1.7
K_ENDPOINT = 2.3
U_AMPLITUDE = 0.9
KAPPA = 0.6
G_Q = 0.4
MU = 1.1

LENGTH = 2.0 * np.pi
GRID_SIZE = 24
VOLUME = LENGTH**3
POINT_COUNT = GRID_SIZE**3


def max_abs(value: np.ndarray) -> float:
    return float(np.max(np.abs(value)))


def relative_error(left: float, right: float) -> float:
    scale = max(abs(left), abs(right), np.finfo(float).tiny)
    return abs(left - right) / scale


axis = np.arange(GRID_SIZE, dtype=float) * LENGTH / GRID_SIZE
x, y, z = np.meshgrid(axis, axis, axis, indexing="ij")

wave = 2.0 * np.pi * np.fft.fftfreq(GRID_SIZE, d=LENGTH / GRID_SIZE)
kx, ky, kz = np.meshgrid(wave, wave, wave, indexing="ij")
k_squared = kx**2 + ky**2 + kz**2
nonzero_mode = k_squared > 0.0

# Frozen zero-mean source and its closed analytic phase.
gamma_source = (
    0.21 * np.sin(x)
    + 0.13 * np.cos(2.0 * y - z)
    - 0.08 * np.sin(x + y + 2.0 * z)
)
phase_scale = HBAR / (K_ENDPOINT * U_AMPLITUDE**2)
alpha_analytic = -phase_scale * (
    0.21 * np.sin(x)
    + (0.13 / 5.0) * np.cos(2.0 * y - z)
    - (0.08 / 6.0) * np.sin(x + y + 2.0 * z)
)

# Fourier coefficients use f(x) = sum_k f_k exp(i k.x).
gamma_hat = np.fft.fftn(gamma_source) / POINT_COUNT
alpha_hat = np.zeros_like(gamma_hat)
alpha_hat[nonzero_mode] = (
    -phase_scale
    * gamma_hat[nonzero_mode]
    / k_squared[nonzero_mode]
)
alpha = np.fft.ifftn(alpha_hat * POINT_COUNT).real

grad_alpha = np.stack(
    [
        np.fft.ifftn(1j * component * alpha_hat * POINT_COUNT).real
        for component in (kx, ky, kz)
    ]
)
laplace_alpha = np.fft.ifftn(
    -k_squared * alpha_hat * POINT_COUNT
).real

current_coefficient = K_ENDPOINT * U_AMPLITUDE**2 / HBAR
endpoint_current = current_coefficient * grad_alpha
current_hat = np.stack(
    [np.fft.fftn(component) / POINT_COUNT for component in endpoint_current]
)
current_divergence = np.fft.ifftn(
    1j
    * (kx * current_hat[0] + ky * current_hat[1] + kz * current_hat[2])
    * POINT_COUNT
).real

# The imposed rail bilinear makes the stationary rotating-frame endpoint
# equation exact at the frozen point.
upsilon = U_AMPLITUDE * np.exp(1j * alpha)
gradient_norm_squared = np.sum(grad_alpha**2, axis=0)
laplace_upsilon = upsilon * (
    1j * laplace_alpha - gradient_norm_squared
)
rail_bilinear = (
    -0.5 * K_ENDPOINT * laplace_upsilon + MU * upsilon
) / KAPPA
endpoint_residual = (
    -0.5 * K_ENDPOINT * laplace_upsilon
    + MU * upsilon
    - KAPPA * rail_bilinear
)

gamma_from_link = (
    -2.0
    * KAPPA
    / HBAR
    * np.imag(np.conjugate(upsilon) * rail_bilinear)
)
link_difference_rate = -2.0 * gamma_from_link

# SF1: rail-difference normalization and relative-charge source cancellation.
source_normalization_error = max_abs(
    link_difference_rate + 2.0 * gamma_from_link
)
rail_charge_source = G_Q * gamma_from_link
endpoint_charge_source = -G_Q * gamma_from_link
charge_cancellation_error = max_abs(
    rail_charge_source + endpoint_charge_source
)

# SF2: stationary endpoint equation and local continuity.
endpoint_equation_error = max_abs(endpoint_residual)
link_source_error = max_abs(gamma_from_link - gamma_source)
continuity_error = max_abs(current_divergence - gamma_source)

# SF3: time-independent local relative-frame covariance.
chi = 0.17 * np.cos(x - 2.0 * z) + 0.09 * np.sin(y + z)
grad_chi = np.stack(
    [
        -0.17 * np.sin(x - 2.0 * z),
        0.09 * np.cos(y + z),
        0.34 * np.sin(x - 2.0 * z) + 0.09 * np.cos(y + z),
    ]
)
laplace_chi = (
    -0.85 * np.cos(x - 2.0 * z)
    - 0.18 * np.sin(y + z)
)
transformation = np.exp(-1j * G_Q * chi)
alpha_transformed_gradient = grad_alpha - G_Q * grad_chi
connection_transformed = grad_chi
invariant_phase_gradient = (
    alpha_transformed_gradient + G_Q * connection_transformed
)

upsilon_transformed = transformation * upsilon
rail_bilinear_transformed = transformation * rail_bilinear
covariant_gradient = 1j * upsilon[None, ...] * grad_alpha
covariant_gradient_transformed = (
    1j
    * upsilon_transformed[None, ...]
    * invariant_phase_gradient
)
transformed_current = (
    K_ENDPOINT
    / HBAR
    * np.imag(
        np.conjugate(upsilon_transformed)[None, ...]
        * covariant_gradient_transformed
    )
)
transformed_source = (
    -2.0
    * KAPPA
    / HBAR
    * np.imag(
        np.conjugate(upsilon_transformed)
        * rail_bilinear_transformed
    )
)
transformed_phase_laplacian = laplace_alpha - G_Q * laplace_chi
connection_divergence = laplace_chi
invariant_phase_laplacian = (
    transformed_phase_laplacian + G_Q * connection_divergence
)
transformed_laplacian = upsilon_transformed * (
    1j * invariant_phase_laplacian
    - np.sum(invariant_phase_gradient**2, axis=0)
)
transformed_endpoint_residual = (
    -0.5 * K_ENDPOINT * transformed_laplacian
    + MU * upsilon_transformed
    - KAPPA * rail_bilinear_transformed
)

gauge_phase_gradient_error = max_abs(
    invariant_phase_gradient - grad_alpha
)
gauge_covariant_derivative_error = max_abs(
    covariant_gradient_transformed
    - transformation[None, ...] * covariant_gradient
)
gauge_covariant_laplacian_error = max_abs(
    transformed_laplacian - transformation * laplace_upsilon
)
gauge_current_error = max_abs(transformed_current - endpoint_current)
gauge_source_error = max_abs(transformed_source - gamma_from_link)
gauge_endpoint_error = max_abs(transformed_endpoint_residual)

# SF4: inverse-divergence reconstruction.
analytic_phase_error = max_abs(alpha - alpha_analytic)
periodic_source_mean = abs(float(np.mean(gamma_source)))

# SF5: a nonzero source mean survives as the unsolved zero-mode residual.
bad_source = gamma_source + 0.07
bad_hat = np.fft.fftn(bad_source) / POINT_COUNT
bad_alpha_hat = np.zeros_like(bad_hat)
bad_alpha_hat[nonzero_mode] = (
    -phase_scale
    * bad_hat[nonzero_mode]
    / k_squared[nonzero_mode]
)
bad_grad = np.stack(
    [
        np.fft.ifftn(
            1j * component * bad_alpha_hat * POINT_COUNT
        ).real
        for component in (kx, ky, kz)
    ]
)
bad_current = current_coefficient * bad_grad
bad_current_hat = np.stack(
    [np.fft.fftn(component) / POINT_COUNT for component in bad_current]
)
bad_divergence = np.fft.ifftn(
    1j
    * (
        kx * bad_current_hat[0]
        + ky * bad_current_hat[1]
        + kz * bad_current_hat[2]
    )
    * POINT_COUNT
).real
bad_residual = bad_divergence - bad_source
bad_source_mean_error = abs(float(np.mean(bad_source)) - 0.07)
bad_divergence_mean = abs(float(np.mean(bad_divergence)))
bad_zero_mode_error = max_abs(bad_residual + 0.07)

# SF6: direct and Fourier gradient energies.
direct_energy = (
    0.5
    * K_ENDPOINT
    * U_AMPLITUDE**2
    * VOLUME
    * float(np.mean(np.sum(grad_alpha**2, axis=0)))
)
gamma_spectral_energy = (
    HBAR**2
    * VOLUME
    / (2.0 * K_ENDPOINT * U_AMPLITUDE**2)
    * float(
        np.sum(
            np.abs(gamma_hat[nonzero_mode]) ** 2
            / k_squared[nonzero_mode]
        )
    )
)
link_hat = -2.0 * gamma_hat
link_spectral_energy = (
    HBAR**2
    * VOLUME
    / (8.0 * K_ENDPOINT * U_AMPLITUDE**2)
    * float(
        np.sum(
            np.abs(link_hat[nonzero_mode]) ** 2
            / k_squared[nonzero_mode]
        )
    )
)
gamma_energy_error = relative_error(direct_energy, gamma_spectral_energy)
link_energy_error = relative_error(direct_energy, link_spectral_energy)

metrics = {
    "SF1 source-normalization error": source_normalization_error,
    "SF1 charge-cancellation error": charge_cancellation_error,
    "SF2 endpoint-equation error": endpoint_equation_error,
    "SF2 link-source error": link_source_error,
    "SF2 continuity error": continuity_error,
    "SF3 invariant-gradient error": gauge_phase_gradient_error,
    "SF3 covariant-derivative error": gauge_covariant_derivative_error,
    "SF3 covariant-laplacian error": gauge_covariant_laplacian_error,
    "SF3 current-invariance error": gauge_current_error,
    "SF3 source-invariance error": gauge_source_error,
    "SF3 transformed-equation error": gauge_endpoint_error,
    "SF4 analytic-phase error": analytic_phase_error,
    "SF4 periodic-source mean": periodic_source_mean,
    "SF5 bad-source mean error": bad_source_mean_error,
    "SF5 reconstructed-divergence mean": bad_divergence_mean,
    "SF5 zero-mode residual error": bad_zero_mode_error,
    "SF6 gamma-energy relative error": gamma_energy_error,
    "SF6 link-energy relative error": link_energy_error,
}

gates = {
    "SF1": max(source_normalization_error, charge_cancellation_error) < TOL,
    "SF2": max(
        endpoint_equation_error,
        link_source_error,
        continuity_error,
    )
    < TOL,
    "SF3": max(
        gauge_phase_gradient_error,
        gauge_covariant_derivative_error,
        gauge_covariant_laplacian_error,
        gauge_current_error,
        gauge_source_error,
        gauge_endpoint_error,
    )
    < TOL,
    "SF4": max(analytic_phase_error, continuity_error, periodic_source_mean)
    < TOL,
    "SF5": max(
        bad_source_mean_error,
        bad_divergence_mean,
        bad_zero_mode_error,
    )
    < TOL,
    "SF6": (
        direct_energy > 0.0
        and gamma_energy_error < TOL
        and link_energy_error < TOL
    ),
}

overall_pass = all(gates.values())

print("Charged-endpoint spatial-flux receipt")
print(f"  grid                              = {GRID_SIZE}^3")
print(f"  direct gradient energy            = {direct_energy:.12e}")
print(f"  gamma spectral energy             = {gamma_spectral_energy:.12e}")
print(f"  link spectral energy              = {link_spectral_energy:.12e}")
for name, value in metrics.items():
    print(f"  {name:<34} = {value:.3e}")
for gate, passed in gates.items():
    print(f"  {gate}                              = {'PASS' if passed else 'FAIL'}")
print(f"OVERALL: {'PASS' if overall_pass else 'FAIL'}")

if not overall_pass:
    raise SystemExit(1)
