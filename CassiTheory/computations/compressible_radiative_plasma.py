#!/usr/bin/env python3
"""Reference kernels for the conditional compressible radiative-plasma closure.

Run from the CassiTheory root:
    python computations/compressible_radiative_plasma.py

The defaults are dimensionless verification values. This module does not
assign physical units or chemical identities to the Cassi field.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy.linalg import expm


@dataclass(frozen=True)
class GasState:
    pressure: float
    internal_energy: float
    total_energy: float
    temperature: float


@dataclass(frozen=True)
class ConservativeMaterialState:
    density: float
    momentum: np.ndarray
    total_energy: float
    species_densities: np.ndarray
    level_populations: np.ndarray

@dataclass(frozen=True)
class ShockState:
    rho: float
    pressure: float
    temperature: float
    velocity: float


@dataclass(frozen=True)
class AngularMoments:
    energy: float
    flux: np.ndarray
    pressure: np.ndarray


def _finite_positive(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _finite_nonnegative(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


def _state_arrays(
    populations: np.ndarray | Iterable[float],
    level_energies: np.ndarray | Iterable[float],
) -> tuple[np.ndarray, np.ndarray]:
    numbers = np.asarray(populations, dtype=np.float64)
    energies = np.asarray(level_energies, dtype=np.float64)
    if numbers.ndim != 1 or energies.shape != numbers.shape or numbers.size == 0:
        raise ValueError("populations and level energies must be equal nonempty vectors")
    if not np.all(np.isfinite(numbers)) or np.any(numbers < 0.0):
        raise ValueError("populations must be finite and nonnegative")
    if not np.all(np.isfinite(energies)) or np.any(energies < 0.0):
        raise ValueError("level energies must be finite and nonnegative")
    return numbers, energies


def ideal_level_gas(
    rho: float,
    velocity: np.ndarray | Iterable[float],
    temperature: float,
    populations: np.ndarray | Iterable[float],
    electron_density: float,
    level_energies: np.ndarray | Iterable[float],
    *,
    boltzmann: float = 1.0,
) -> GasState:
    """Return pressure and energy for a dilute monatomic multilevel gas."""
    density = _finite_positive("rho", rho)
    temp = _finite_positive("temperature", temperature)
    k_b = _finite_positive("boltzmann", boltzmann)
    electrons = float(electron_density)
    if not math.isfinite(electrons) or electrons < 0.0:
        raise ValueError("electron density must be finite and nonnegative")
    numbers, energies = _state_arrays(populations, level_energies)
    particle_density = electrons + float(np.sum(numbers))
    if particle_density <= 0.0:
        raise ValueError("total particle density must be positive")
    flow = np.asarray(velocity, dtype=np.float64)
    if flow.ndim != 1 or not np.all(np.isfinite(flow)):
        raise ValueError("velocity must be a finite vector")
    thermal = 1.5 * k_b * temp * particle_density
    level = float(np.dot(numbers, energies))
    internal = thermal + level
    kinetic = 0.5 * density * float(np.dot(flow, flow))
    return GasState(
        pressure=k_b * temp * particle_density,
        internal_energy=internal,
        total_energy=internal + kinetic,
        temperature=temp,
    )


def conservative_material_state(
    rho: float,
    velocity: np.ndarray | Iterable[float],
    specific_internal_energy: float,
    mass_fractions: np.ndarray | Iterable[float],
    level_populations: np.ndarray | Iterable[float],
    *,
    fraction_tolerance: float = 1.0e-12,
) -> ConservativeMaterialState:
    """Pack rho, rho*u, rho*E, rho*Y_s and n_sℓ after admissibility checks."""
    density = _finite_positive("rho", rho)
    internal = _finite_positive("specific internal energy", specific_internal_energy)
    tolerance = _finite_positive("fraction tolerance", fraction_tolerance)
    flow = np.asarray(velocity, dtype=np.float64)
    fractions = np.asarray(mass_fractions, dtype=np.float64)
    levels = np.asarray(level_populations, dtype=np.float64)
    if flow.ndim != 1 or flow.size == 0 or not np.all(np.isfinite(flow)):
        raise ValueError("velocity must be a finite nonempty vector")
    if fractions.ndim != 1 or fractions.size == 0:
        raise ValueError("mass fractions must be a nonempty vector")
    if not np.all(np.isfinite(fractions)) or np.any(fractions < 0.0):
        raise ValueError("mass fractions must be finite and nonnegative")
    if abs(float(np.sum(fractions)) - 1.0) > tolerance:
        raise ValueError("mass fractions must sum to one")
    if levels.ndim != 1 or not np.all(np.isfinite(levels)) or np.any(levels < 0.0):
        raise ValueError("level populations must be a finite nonnegative vector")
    momentum = density * flow
    total = density * (internal + 0.5 * float(np.dot(flow, flow)))
    return ConservativeMaterialState(
        density=density,
        momentum=momentum,
        total_energy=total,
        species_densities=density * fractions,
        level_populations=levels,
    )


def recover_internal_energy_density(state: ConservativeMaterialState) -> float:
    """Recover rho*e from a validated conservative material state."""
    kinetic = float(np.dot(state.momentum, state.momentum)) / (2.0 * state.density)
    internal = state.total_energy - kinetic
    if not math.isfinite(internal) or internal <= 0.0:
        raise ValueError("conservative state has no positive internal energy")
    return internal


def recover_temperature(
    internal_energy: float,
    populations: np.ndarray | Iterable[float],
    electron_density: float,
    level_energies: np.ndarray | Iterable[float],
    *,
    boltzmann: float = 1.0,
) -> float:
    """Invert the frozen-population ideal multilevel EOS."""
    internal = float(internal_energy)
    k_b = _finite_positive("boltzmann", boltzmann)
    electrons = float(electron_density)
    if not math.isfinite(internal) or not math.isfinite(electrons) or electrons < 0.0:
        raise ValueError("internal energy and electron density must be admissible")
    numbers, energies = _state_arrays(populations, level_energies)
    particle_density = electrons + float(np.sum(numbers))
    level = float(np.dot(numbers, energies))
    thermal = internal - level
    if particle_density <= 0.0 or thermal <= 0.0:
        raise ValueError("state has no positive thermal-energy remainder")
    return 2.0 * thermal / (3.0 * k_b * particle_density)


def normal_shock(
    rho_upstream: float,
    pressure_upstream: float,
    mach_upstream: float,
    *,
    gamma: float = 5.0 / 3.0,
) -> tuple[ShockState, ShockState]:
    """Return ideal-gas states on both sides of a stationary normal shock."""
    rho1 = _finite_positive("upstream density", rho_upstream)
    p1 = _finite_positive("upstream pressure", pressure_upstream)
    mach = _finite_positive("upstream Mach number", mach_upstream)
    ratio = _finite_positive("gamma", gamma)
    if mach <= 1.0 or ratio <= 1.0:
        raise ValueError("normal-shock control requires Mach > 1 and gamma > 1")
    sound1 = math.sqrt(ratio * p1 / rho1)
    velocity1 = mach * sound1
    compression = (ratio + 1.0) * mach**2 / ((ratio - 1.0) * mach**2 + 2.0)
    pressure_ratio = 1.0 + 2.0 * ratio * (mach**2 - 1.0) / (ratio + 1.0)
    rho2 = compression * rho1
    p2 = pressure_ratio * p1
    velocity2 = velocity1 / compression
    return (
        ShockState(rho=rho1, pressure=p1, temperature=p1 / rho1, velocity=velocity1),
        ShockState(rho=rho2, pressure=p2, temperature=p2 / rho2, velocity=velocity2),
    )


def shock_fluxes(state: ShockState, *, gamma: float = 5.0 / 3.0) -> np.ndarray:
    """Return mass, normal momentum and total-energy fluxes."""
    ratio = _finite_positive("gamma", gamma)
    if ratio <= 1.0:
        raise ValueError("gamma must exceed one")
    enthalpy = ratio * state.pressure / ((ratio - 1.0) * state.rho)
    mass = state.rho * state.velocity
    momentum = state.rho * state.velocity**2 + state.pressure
    energy = mass * (enthalpy + 0.5 * state.velocity**2)
    return np.asarray([mass, momentum, energy], dtype=np.float64)


def shock_entropy_increment(
    upstream: ShockState, downstream: ShockState, *, gamma: float = 5.0 / 3.0
) -> float:
    """Return the ideal-gas entropy increment divided by c_v."""
    pressure_ratio = downstream.pressure / upstream.pressure
    density_ratio = downstream.rho / upstream.rho
    return math.log(pressure_ratio / density_ratio**gamma)


def boltzmann_distribution(
    energies: np.ndarray | Iterable[float],
    degeneracies: np.ndarray | Iterable[float],
    temperature: float,
    *,
    boltzmann: float = 1.0,
) -> np.ndarray:
    levels = np.asarray(energies, dtype=np.float64)
    weights = np.asarray(degeneracies, dtype=np.float64)
    temp = _finite_positive("temperature", temperature)
    k_b = _finite_positive("boltzmann", boltzmann)
    if levels.ndim != 1 or levels.size == 0 or weights.shape != levels.shape:
        raise ValueError("energies and degeneracies must be equal nonempty vectors")
    if np.any(~np.isfinite(levels)) or np.any(~np.isfinite(weights)) or np.any(weights <= 0.0):
        raise ValueError("level data must be finite with positive degeneracies")
    logarithms = np.log(weights) - levels / (k_b * temp)
    logarithms -= float(np.max(logarithms))
    populations = np.exp(logarithms)
    return populations / float(np.sum(populations))


def detailed_balance_generator(
    energies: np.ndarray | Iterable[float],
    degeneracies: np.ndarray | Iterable[float],
    temperature: float,
    downward_rates: Iterable[tuple[int, int, float]],
    *,
    boltzmann: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Construct a column-conservative rate generator with detailed balance."""
    equilibrium = boltzmann_distribution(
        energies, degeneracies, temperature, boltzmann=boltzmann
    )
    generator = np.zeros((equilibrium.size, equilibrium.size), dtype=np.float64)
    seen: set[tuple[int, int]] = set()
    for upper, lower, raw_rate in downward_rates:
        if not 0 <= lower < upper < equilibrium.size:
            raise ValueError("downward-rate indices must satisfy lower < upper")
        if (upper, lower) in seen:
            raise ValueError("duplicate downward transition")
        seen.add((upper, lower))
        down = _finite_positive("downward rate", raw_rate)
        up = down * equilibrium[upper] / equilibrium[lower]
        generator[lower, upper] += down
        generator[upper, lower] += up
    for source in range(generator.shape[1]):
        generator[source, source] = -float(np.sum(generator[:, source]))
    return generator, equilibrium


def evolve_populations(generator: np.ndarray, populations: np.ndarray, time: float) -> np.ndarray:
    matrix = np.asarray(generator, dtype=np.float64)
    state = np.asarray(populations, dtype=np.float64)
    duration = float(time)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or state.shape != (matrix.shape[0],):
        raise ValueError("generator and population dimensions do not match")
    if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(state)) or np.any(state < 0.0):
        raise ValueError("generator and populations must be finite and populations nonnegative")
    if not math.isfinite(duration) or duration < 0.0:
        raise ValueError("time must be finite and nonnegative")
    if np.max(np.abs(np.sum(matrix, axis=0))) > 1.0e-12:
        raise ValueError("rate generator columns must sum to zero")
    off_diagonal = matrix.copy()
    np.fill_diagonal(off_diagonal, 0.0)
    if np.any(off_diagonal < 0.0):
        raise ValueError("rate generator has a negative off-diagonal entry")
    result = expm(matrix * duration) @ state
    if np.min(result) < -1.0e-12:
        raise ArithmeticError("population evolution left the positive cone")
    return np.maximum(result, 0.0)


def planck_intensity(
    frequency: float,
    temperature: float,
    *,
    planck: float = 1.0,
    light_speed: float = 1.0,
    boltzmann: float = 1.0,
) -> float:
    nu = _finite_positive("frequency", frequency)
    temp = _finite_positive("temperature", temperature)
    h = _finite_positive("planck", planck)
    c = _finite_positive("light speed", light_speed)
    k_b = _finite_positive("boltzmann", boltzmann)
    exponent = h * nu / (k_b * temp)
    if exponent > 700.0:
        return 0.0
    return 2.0 * h * nu**3 / (c**2 * math.expm1(exponent))


def two_level_lte_populations(
    total_population: float,
    lower_weight: float,
    upper_weight: float,
    frequency: float,
    temperature: float,
    *,
    planck: float = 1.0,
    boltzmann: float = 1.0,
) -> tuple[float, float]:
    total = _finite_positive("total population", total_population)
    g_l = _finite_positive("lower statistical weight", lower_weight)
    g_u = _finite_positive("upper statistical weight", upper_weight)
    nu = _finite_positive("frequency", frequency)
    temp = _finite_positive("temperature", temperature)
    h = _finite_positive("planck", planck)
    k_b = _finite_positive("boltzmann", boltzmann)
    ratio = (g_u / g_l) * math.exp(-h * nu / (k_b * temp))
    lower = total / (1.0 + ratio)
    return lower, total - lower


def line_coefficients(
    lower_population: float,
    upper_population: float,
    lower_weight: float,
    upper_weight: float,
    frequency: float,
    b_ul: float,
    profile: float,
    *,
    planck: float = 1.0,
    light_speed: float = 1.0,
) -> tuple[float, float, float, float]:
    """Return emissivity, absorption, A_ul and B_lu for one line sample."""
    n_l = _finite_nonnegative("lower population", lower_population)
    n_u = _finite_nonnegative("upper population", upper_population)
    g_l = _finite_positive("lower statistical weight", lower_weight)
    g_u = _finite_positive("upper statistical weight", upper_weight)
    nu = _finite_positive("frequency", frequency)
    b_down = _finite_positive("B_ul", b_ul)
    phi = _finite_positive("line profile", profile)
    h = _finite_positive("planck", planck)
    c = _finite_positive("light speed", light_speed)
    b_up = g_u * b_down / g_l
    a_down = 2.0 * h * nu**3 * b_down / c**2
    scale = h * nu * phi / (4.0 * math.pi)
    emissivity = scale * n_u * a_down
    absorption = scale * (n_l * b_up - n_u * b_down)
    return emissivity, absorption, a_down, b_up


def line_energy_exchange(
    lower_population: float,
    upper_population: float,
    mean_intensity: float,
    frequency: float,
    a_ul: float,
    b_ul: float,
    b_lu: float,
    *,
    planck: float = 1.0,
) -> tuple[float, float, float]:
    n_l = _finite_nonnegative("lower population", lower_population)
    n_u = _finite_nonnegative("upper population", upper_population)
    intensity = _finite_nonnegative("mean intensity", mean_intensity)
    nu = _finite_positive("frequency", frequency)
    a_down = _finite_positive("A_ul", a_ul)
    b_down = _finite_positive("B_ul", b_ul)
    b_up = _finite_positive("B_lu", b_lu)
    h = _finite_positive("planck", planck)
    transition_rate = n_u * (a_down + b_down * intensity) - n_l * b_up * intensity
    photon_gain = h * nu * transition_rate
    return transition_rate, -photon_gain, photon_gain


def isotropic_transfer_energy_source(
    emissivity: float,
    extinction: float,
    radiation_energy: float,
    *,
    light_speed: float = 1.0,
) -> tuple[float, float]:
    """Return radiation and material energy sources for isotropic eta-alpha transfer."""
    eta = _finite_nonnegative("emissivity", emissivity)
    alpha = _finite_nonnegative("extinction", extinction)
    energy = _finite_nonnegative("radiation energy", radiation_energy)
    c = _finite_positive("light speed", light_speed)
    radiation_source = 4.0 * math.pi * eta - c * alpha * energy
    return radiation_source, -radiation_source


def photoionization_partition(
    frequencies: np.ndarray | Iterable[float],
    widths: np.ndarray | Iterable[float],
    cross_sections: np.ndarray | Iterable[float],
    mean_intensities: np.ndarray | Iterable[float],
    population: float,
    threshold_energy: float,
    *,
    planck: float = 1.0,
) -> tuple[float, float, float, float]:
    nu = np.asarray(frequencies, dtype=np.float64)
    delta = np.asarray(widths, dtype=np.float64)
    sigma = np.asarray(cross_sections, dtype=np.float64)
    mean = np.asarray(mean_intensities, dtype=np.float64)
    if nu.ndim != 1 or nu.size == 0 or not (delta.shape == sigma.shape == mean.shape == nu.shape):
        raise ValueError("photoionization arrays must have equal nonempty shapes")
    if np.any(~np.isfinite(nu + delta + sigma + mean)) or np.any(delta <= 0.0) or np.any(sigma < 0.0) or np.any(mean < 0.0):
        raise ValueError("photoionization quadrature data are inadmissible")
    number = _finite_positive("population", population)
    threshold = _finite_positive("threshold energy", threshold_energy)
    h = _finite_positive("planck", planck)
    photon_energy = h * nu
    if np.any(photon_energy < threshold):
        raise ValueError("photoionization frequency lies below threshold")
    photon_rate_weights = 4.0 * math.pi * sigma * mean * delta / photon_energy
    rate = float(np.sum(photon_rate_weights))
    absorbed = number * float(np.sum(photon_rate_weights * photon_energy))
    stored = number * threshold * rate
    heat = number * float(np.sum(photon_rate_weights * (photon_energy - threshold)))
    return rate, absorbed, stored, heat


def critical_density(radiative_rate: float, collisional_coefficient: float) -> float:
    return _finite_positive("radiative rate", radiative_rate) / _finite_positive(
        "collisional coefficient", collisional_coefficient
    )


def virial_star_energy(
    mass: float, radius: float, *, gravity: float = 1.0, structure: float = 3.0 / 5.0
) -> tuple[float, float, float]:
    m = _finite_positive("mass", mass)
    r = _finite_positive("radius", radius)
    g = _finite_positive("gravity", gravity)
    alpha = _finite_positive("structure coefficient", structure)
    gravitational = -alpha * g * m**2 / r
    internal = -0.5 * gravitational
    return internal, gravitational, internal + gravitational


def kelvin_helmholtz_release(
    mass: float,
    initial_radius: float,
    final_radius: float,
    *,
    gravity: float = 1.0,
    structure: float = 3.0 / 5.0,
) -> float:
    if final_radius >= initial_radius:
        raise ValueError("Kelvin-Helmholtz control requires contraction")
    _, _, initial = virial_star_energy(
        mass, initial_radius, gravity=gravity, structure=structure
    )
    _, _, final = virial_star_energy(
        mass, final_radius, gravity=gravity, structure=structure
    )
    return initial - final


def accretion_partition(
    mass: float,
    radius: float,
    accretion_rate: float,
    efficiency: float,
    *,
    gravity: float = 1.0,
) -> tuple[float, float, float]:
    m = _finite_positive("mass", mass)
    r = _finite_positive("radius", radius)
    rate = float(accretion_rate)
    eta = float(efficiency)
    g = _finite_positive("gravity", gravity)
    if not math.isfinite(rate) or rate < 0.0 or not math.isfinite(eta) or not 0.0 <= eta <= 1.0:
        raise ValueError("accretion rate and efficiency are inadmissible")
    available = g * m * rate / r
    return available, eta * available, (1.0 - eta) * available


def nuclear_reaction_power(
    stoichiometry: np.ndarray | Iterable[float],
    masses: np.ndarray | Iterable[float],
    baryon_numbers: np.ndarray | Iterable[float],
    charges: np.ndarray | Iterable[float],
    event_rate: float,
    *,
    light_speed: float = 1.0,
) -> tuple[np.ndarray, float, float, float]:
    nu = np.asarray(stoichiometry, dtype=np.float64)
    mass = np.asarray(masses, dtype=np.float64)
    baryon = np.asarray(baryon_numbers, dtype=np.float64)
    charge = np.asarray(charges, dtype=np.float64)
    if nu.ndim != 1 or nu.size == 0 or not (mass.shape == baryon.shape == charge.shape == nu.shape):
        raise ValueError("nuclear arrays must have equal nonempty shapes")
    if np.any(~np.isfinite(nu + mass + baryon + charge)) or np.any(mass <= 0.0):
        raise ValueError("nuclear data are inadmissible")
    rate = float(event_rate)
    c = _finite_positive("light speed", light_speed)
    if not math.isfinite(rate) or rate < 0.0:
        raise ValueError("event rate must be finite and nonnegative")
    sources = nu * rate
    power = -c**2 * float(np.dot(mass, sources))
    return sources, power, float(np.dot(baryon, sources)), float(np.dot(charge, sources))


def control_volume_energy_residual(
    photon_luminosity: float,
    neutrino_luminosity: float,
    mechanical_outflow: float,
    external_power: float,
    gross_nuclear_power: float,
    matter_energy_inflow: float,
    stored_energy_rate: float,
) -> float:
    """Evaluate L_gamma+L_nu+E_mech,out-P_ext-L_nuc-E_matter,in+dE_stored/dt."""
    photon = _finite_nonnegative("photon luminosity", photon_luminosity)
    neutrino = _finite_nonnegative("neutrino luminosity", neutrino_luminosity)
    mechanical = _finite_nonnegative("mechanical outflow", mechanical_outflow)
    nuclear = _finite_nonnegative("gross nuclear power", gross_nuclear_power)
    matter_in = _finite_nonnegative("matter energy inflow", matter_energy_inflow)
    external = float(external_power)
    stored = float(stored_energy_rate)
    if not math.isfinite(external) or not math.isfinite(stored):
        raise ValueError("external power and stored-energy rate must be finite")
    return photon + neutrino + mechanical - external - nuclear - matter_in + stored


def require_control_volume_energy_balance(
    photon_luminosity: float,
    neutrino_luminosity: float,
    mechanical_outflow: float,
    external_power: float,
    gross_nuclear_power: float,
    matter_energy_inflow: float,
    stored_energy_rate: float,
    *,
    tolerance: float = 1.0e-12,
) -> float:
    """Return the residual or reject a source ledger outside scaled tolerance."""
    tol = _finite_positive("energy-balance tolerance", tolerance)
    residual = control_volume_energy_residual(
        photon_luminosity,
        neutrino_luminosity,
        mechanical_outflow,
        external_power,
        gross_nuclear_power,
        matter_energy_inflow,
        stored_energy_rate,
    )
    scale = max(
        1.0,
        abs(float(photon_luminosity))
        + abs(float(neutrino_luminosity))
        + abs(float(mechanical_outflow))
        + abs(float(external_power))
        + abs(float(gross_nuclear_power))
        + abs(float(matter_energy_inflow))
        + abs(float(stored_energy_rate)),
    )
    if abs(residual) > tol * scale:
        raise ValueError(
            f"control-volume energy residual {residual:.17g} exceeds "
            f"scaled tolerance {tol * scale:.17g}"
        )
    return residual


def radiative_temperature_gradient(
    luminosity: float,
    radius: float,
    density: float,
    temperature: float,
    rosseland_opacity: float,
    *,
    radiation_constant: float = 1.0,
    light_speed: float = 1.0,
) -> float:
    lum = float(luminosity)
    r = _finite_positive("radius", radius)
    rho = _finite_positive("density", density)
    temp = _finite_positive("temperature", temperature)
    opacity = _finite_positive("Rosseland opacity", rosseland_opacity)
    a_rad = _finite_positive("radiation constant", radiation_constant)
    c = _finite_positive("light speed", light_speed)
    if not math.isfinite(lum):
        raise ValueError("luminosity must be finite")
    return -3.0 * opacity * rho * lum / (16.0 * math.pi * a_rad * c * r**2 * temp**3)


def axis_quadrature() -> tuple[np.ndarray, np.ndarray]:
    directions = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, -1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, 0.0, -1.0],
        ],
        dtype=np.float64,
    )
    return directions, np.full(6, 4.0 * math.pi / 6.0, dtype=np.float64)


def validate_quadrature(
    directions: np.ndarray, weights: np.ndarray, *, tolerance: float = 1.0e-12
) -> dict[str, float]:
    rays = np.asarray(directions, dtype=np.float64)
    solid = np.asarray(weights, dtype=np.float64)
    if rays.ndim != 2 or rays.shape[1] != 3 or solid.shape != (rays.shape[0],):
        raise ValueError("quadrature dimensions are invalid")
    if np.any(~np.isfinite(rays)) or np.any(~np.isfinite(solid)) or np.any(solid <= 0.0):
        raise ValueError("quadrature entries must be finite with positive weights")
    norms = np.linalg.norm(rays, axis=1)
    zeroth = abs(float(np.sum(solid)) - 4.0 * math.pi)
    first = float(np.linalg.norm(np.sum(solid[:, None] * rays, axis=0)))
    second_tensor = np.einsum("m,mi,mj->ij", solid, rays, rays)
    second = float(np.linalg.norm(second_tensor - (4.0 * math.pi / 3.0) * np.eye(3)))
    norm_error = float(np.max(np.abs(norms - 1.0)))
    diagnostics = {"zeroth": zeroth, "first": first, "second": second, "norm": norm_error}
    if max(diagnostics.values()) > tolerance:
        raise ValueError(f"quadrature moment condition failed: {diagnostics}")
    return diagnostics


def angular_moments(
    intensities: np.ndarray | Iterable[float],
    directions: np.ndarray,
    weights: np.ndarray,
    *,
    light_speed: float = 1.0,
) -> AngularMoments:
    values = np.asarray(intensities, dtype=np.float64)
    rays = np.asarray(directions, dtype=np.float64)
    solid = np.asarray(weights, dtype=np.float64)
    c = _finite_positive("light speed", light_speed)
    if values.shape != (rays.shape[0],) or solid.shape != values.shape or rays.shape[1:] != (3,):
        raise ValueError("intensity and quadrature dimensions do not match")
    if np.any(~np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError("intensities must be finite and nonnegative")
    energy = float(np.dot(solid, values)) / c
    flux = np.einsum("m,m,mi->i", solid, values, rays)
    pressure = np.einsum("m,m,mi,mj->ij", solid / c, values, rays, rays)
    return AngularMoments(energy=energy, flux=flux, pressure=pressure)


def isotropic_scattering_step(
    intensities: np.ndarray | Iterable[float],
    weights: np.ndarray | Iterable[float],
    optical_time: float,
) -> np.ndarray:
    values = np.asarray(intensities, dtype=np.float64)
    solid = np.asarray(weights, dtype=np.float64)
    depth = float(optical_time)
    if values.ndim != 1 or solid.shape != values.shape or values.size == 0:
        raise ValueError("intensities and weights must be equal nonempty vectors")
    if np.any(~np.isfinite(values)) or np.any(values < 0.0) or np.any(solid <= 0.0):
        raise ValueError("scattering state is inadmissible")
    if not math.isfinite(depth) or depth < 0.0:
        raise ValueError("optical time must be finite and nonnegative")
    mean = float(np.dot(solid, values)) / float(np.sum(solid))
    return mean + (values - mean) * math.exp(-depth)


def periodic_axis_shift(field: np.ndarray, axis: int, cells: int) -> np.ndarray:
    values = np.asarray(field, dtype=np.float64)
    if values.ndim < 1 or not 0 <= axis < values.ndim:
        raise ValueError("streaming axis is invalid")
    if not np.all(np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError("streamed intensity must be finite and nonnegative")
    return np.roll(values, shift=int(cells), axis=axis)


def main() -> None:
    upstream, downstream = normal_shock(1.0, 1.0, 2.0)
    directions, weights = axis_quadrature()
    intensities = np.asarray([1.0, 1.0, 0.0, 0.0, 0.0, 0.0])
    moments = angular_moments(intensities, directions, weights)
    report = {
        "dimensionless_control": True,
        "shock_density_ratio": downstream.rho / upstream.rho,
        "shock_pressure_ratio": downstream.pressure / upstream.pressure,
        "shock_entropy_over_cv": shock_entropy_increment(upstream, downstream),
        "counterbeam_energy": moments.energy,
        "counterbeam_flux": moments.flux.tolist(),
        "counterbeam_pressure": moments.pressure.tolist(),
    }
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
