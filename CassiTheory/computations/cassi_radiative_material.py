#!/usr/bin/env python3
"""Reference kernels for the selected Cassi radiative-material closure.

Run from the CassiTheory root:
    python computations/cassi_radiative_material.py --time 2 --dt 0.01

The defaults are dimensionless verification coefficients.  They carry no
physical Cassi material calibration.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass

import numpy as np


METRIC = np.diag(np.asarray([-1.0, 1.0, 1.0, 1.0]))


@dataclass(frozen=True)
class RadiationParameters:
    light_speed: float = 3.0
    radiation_constant: float = 1.0
    heat_capacity: float = 2.0
    absorption: float = 0.7
    transport: float = 1.1

    def __post_init__(self) -> None:
        values = asdict(self)
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError("All radiation coefficients must be finite")
        for name in ("light_speed", "radiation_constant", "heat_capacity"):
            if values[name] <= 0.0:
                raise ValueError(f"{name} must be positive")
        for name in ("absorption", "transport"):
            if values[name] < 0.0:
                raise ValueError(f"{name} must be nonnegative")
        if self.transport < self.absorption:
            raise ValueError("transport extinction must include true absorption")


def planck_kernel(x: float) -> float:
    """Return x^3/(exp(x)-1), including its finite endpoint limit."""
    if not math.isfinite(x) or x < 0.0:
        raise ValueError("Planck coordinate must be finite and nonnegative")
    if x == 0.0 or x > 745.0:
        return 0.0
    return x**3 / math.expm1(x)


def lte_energy(temperature: float, parameters: RadiationParameters) -> float:
    if not math.isfinite(temperature) or temperature < 0.0:
        raise ValueError("temperature must be finite and nonnegative")
    return parameters.radiation_constant * temperature**4


def m1_chi(reduced_flux: float) -> float:
    if not math.isfinite(reduced_flux) or reduced_flux < 0.0 or reduced_flux > 1.0:
        raise ValueError("reduced flux must lie in [0, 1]")
    return (3.0 + 4.0 * reduced_flux**2) / (
        5.0 + 2.0 * math.sqrt(4.0 - 3.0 * reduced_flux**2)
    )


def m1_pressure(energy: float, flux: np.ndarray, light_speed: float) -> np.ndarray:
    """Return the three-dimensional M1 radiation-pressure tensor."""
    flux = np.asarray(flux, dtype=np.float64)
    if flux.shape != (3,) or not np.isfinite(flux).all():
        raise ValueError("flux must be one finite three-vector")
    if not math.isfinite(energy) or energy < 0.0:
        raise ValueError("radiation energy must be finite and nonnegative")
    if not math.isfinite(light_speed) or light_speed <= 0.0:
        raise ValueError("light speed must be finite and positive")
    flux_norm = float(np.linalg.norm(flux))
    if energy == 0.0:
        if flux_norm != 0.0:
            raise ValueError("zero radiation energy requires zero flux")
        return np.zeros((3, 3), dtype=np.float64)
    reduced = flux_norm / (light_speed * energy)
    if reduced > 1.0 + 32.0 * np.finfo(np.float64).eps:
        raise ValueError("radiation moments violate |F| <= c E")
    reduced = min(reduced, 1.0)
    if flux_norm == 0.0:
        return np.eye(3, dtype=np.float64) * (energy / 3.0)
    direction = flux / flux_norm
    chi = m1_chi(reduced)
    eddington = 0.5 * (1.0 - chi) * np.eye(3)
    eddington += 0.5 * (3.0 * chi - 1.0) * np.outer(direction, direction)
    return energy * eddington


def radiation_tensor(
    energy: float, flux: np.ndarray, pressure: np.ndarray, light_speed: float
) -> np.ndarray:
    flux = np.asarray(flux, dtype=np.float64)
    pressure = np.asarray(pressure, dtype=np.float64)
    if flux.shape != (3,) or pressure.shape != (3, 3):
        raise ValueError("radiation tensor requires a three-flux and 3x3 pressure")
    if not np.isfinite(flux).all() or not np.isfinite(pressure).all():
        raise ValueError("radiation moments must be finite")
    if not math.isfinite(energy) or energy < 0.0:
        raise ValueError("radiation energy must be finite and nonnegative")
    if not math.isfinite(light_speed) or light_speed <= 0.0:
        raise ValueError("light speed must be finite and positive")
    result = np.empty((4, 4), dtype=np.float64)
    result[0, 0] = energy
    result[0, 1:] = flux / light_speed
    result[1:, 0] = flux / light_speed
    result[1:, 1:] = pressure
    return result


def four_velocity(velocity: np.ndarray, light_speed: float) -> np.ndarray:
    velocity = np.asarray(velocity, dtype=np.float64)
    if velocity.shape != (3,) or not np.isfinite(velocity).all():
        raise ValueError("velocity must be one finite three-vector")
    if not math.isfinite(light_speed) or light_speed <= 0.0:
        raise ValueError("light speed must be finite and positive")
    beta2 = float(np.dot(velocity, velocity)) / light_speed**2
    if beta2 >= 1.0:
        raise ValueError("material velocity must be subluminal")
    lorentz = 1.0 / math.sqrt(1.0 - beta2)
    return np.concatenate(([lorentz * light_speed], lorentz * velocity))


def comoving_moments(
    tensor: np.ndarray, velocity_four: np.ndarray, light_speed: float
) -> tuple[float, np.ndarray]:
    tensor = np.asarray(tensor, dtype=np.float64)
    velocity_four = np.asarray(velocity_four, dtype=np.float64)
    if tensor.shape != (4, 4) or velocity_four.shape != (4,):
        raise ValueError("expected a 4x4 tensor and four-velocity")
    if not np.isfinite(tensor).all() or not np.isfinite(velocity_four).all():
        raise ValueError("covariant inputs must be finite")
    velocity_covariant = METRIC @ velocity_four
    energy = float(velocity_covariant @ tensor @ velocity_covariant / light_speed**2)
    projector = np.eye(4) + np.outer(velocity_four, velocity_covariant) / light_speed**2
    flux_four = -projector @ tensor @ velocity_covariant
    return energy, flux_four


def interaction_four_force(
    tensor: np.ndarray,
    velocity_four: np.ndarray,
    temperature: float,
    parameters: RadiationParameters,
) -> np.ndarray:
    """Radiation four-force density; matter receives its exact negative."""
    energy, flux_four = comoving_moments(tensor, velocity_four, parameters.light_speed)
    equilibrium = lte_energy(temperature, parameters)
    return (
        parameters.absorption * (equilibrium - energy)
        * velocity_four / parameters.light_speed
        - parameters.transport * flux_four / parameters.light_speed
    )


def isotropic_lte_tensor(
    equilibrium_energy: float, velocity_four: np.ndarray, light_speed: float
) -> np.ndarray:
    """Lorentz-frame tensor of isotropic equilibrium radiation."""
    if not math.isfinite(equilibrium_energy) or equilibrium_energy < 0.0:
        raise ValueError("equilibrium energy must be finite and nonnegative")
    velocity_four = np.asarray(velocity_four, dtype=np.float64)
    if velocity_four.shape != (4,) or not np.isfinite(velocity_four).all():
        raise ValueError("velocity_four must be one finite four-vector")
    return (
        (4.0 * equilibrium_energy / (3.0 * light_speed**2))
        * np.outer(velocity_four, velocity_four)
        + (equilibrium_energy / 3.0) * METRIC
    )


def slab_intensity(incoming: float, source: float, optical_depth: float) -> float:
    """Exact constant-source formal solution, stable for small optical depth."""
    values = (incoming, source, optical_depth)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("slab inputs must be finite")
    if incoming < 0.0 or source < 0.0 or optical_depth < 0.0:
        raise ValueError("slab inputs must be nonnegative")
    transmission = math.exp(-optical_depth)
    absorbed = -math.expm1(-optical_depth)
    return incoming * transmission + source * absorbed


def material_entropy(temperature: float, parameters: RadiationParameters) -> float:
    if not math.isfinite(temperature) or temperature <= 0.0:
        raise ValueError("temperature must be finite and positive")
    return parameters.heat_capacity * math.log(temperature)


def radiation_entropy(energy: float, parameters: RadiationParameters) -> float:
    if not math.isfinite(energy) or energy < 0.0:
        raise ValueError("radiation energy must be finite and nonnegative")
    return (
        (4.0 / 3.0)
        * parameters.radiation_constant**0.25
        * energy**0.75
    )


def total_entropy(
    temperature: float, energy: float, parameters: RadiationParameters
) -> float:
    return material_entropy(temperature, parameters) + radiation_entropy(energy, parameters)


def exchange_rhs(
    temperature: float, energy: float, parameters: RadiationParameters
) -> np.ndarray:
    if temperature <= 0.0 or energy < 0.0:
        raise ValueError("exchange state requires T>0 and E>=0")
    source = parameters.light_speed * parameters.absorption * (
        lte_energy(temperature, parameters) - energy
    )
    return np.asarray([-source / parameters.heat_capacity, source], dtype=np.float64)


def equilibrium_temperature(total_energy: float, parameters: RadiationParameters) -> float:
    if not math.isfinite(total_energy) or total_energy <= 0.0:
        raise ValueError("total energy must be finite and positive")
    low = 0.0
    high = total_energy / parameters.heat_capacity
    for _ in range(160):
        middle = 0.5 * (low + high)
        value = (
            parameters.heat_capacity * middle
            + lte_energy(middle, parameters)
            - total_energy
        )
        if value > 0.0:
            high = middle
        else:
            low = middle
    return 0.5 * (low + high)


def implicit_exchange_step(
    temperature: float,
    energy: float,
    dt: float,
    parameters: RadiationParameters,
) -> tuple[float, float]:
    """Energy-conservative backward-Euler absorption/emission step."""
    if not all(math.isfinite(value) for value in (temperature, energy, dt)):
        raise ValueError("exchange inputs must be finite")
    if temperature <= 0.0 or energy < 0.0 or dt < 0.0:
        raise ValueError("exchange requires T>0, E>=0 and dt>=0")
    if dt == 0.0 or parameters.absorption == 0.0:
        return temperature, energy
    total = parameters.heat_capacity * temperature + energy
    coupling = parameters.light_speed * parameters.absorption * dt

    def residual(candidate: float) -> float:
        next_energy = (
            energy + coupling * lte_energy(candidate, parameters)
        ) / (1.0 + coupling)
        return parameters.heat_capacity * candidate + next_energy - total

    low = 0.0
    high = total / parameters.heat_capacity
    if residual(low) > 0.0 or residual(high) < 0.0:
        raise ArithmeticError("implicit exchange root is not bracketed")
    for _ in range(160):
        middle = 0.5 * (low + high)
        if residual(middle) > 0.0:
            high = middle
        else:
            low = middle
    next_temperature = 0.5 * (low + high)
    next_energy = total - parameters.heat_capacity * next_temperature
    if next_temperature <= 0.0 or next_energy < 0.0:
        raise FloatingPointError("implicit exchange left the positive state")
    return next_temperature, next_energy


def evolve_exchange(
    temperature: float,
    energy: float,
    duration: float,
    dt: float,
    parameters: RadiationParameters,
) -> np.ndarray:
    if not math.isfinite(duration) or not math.isfinite(dt) or duration <= 0.0 or dt <= 0.0:
        raise ValueError("duration and dt must be finite and positive")
    count = round(duration / dt)
    if count < 1 or abs(count * dt - duration) > 1e-12 * max(1.0, duration):
        raise ValueError("duration must contain an integer number of steps")
    history = np.empty((count + 1, 5), dtype=np.float64)
    total = parameters.heat_capacity * temperature + energy
    history[0] = (0.0, temperature, energy, total, total_entropy(temperature, energy, parameters))
    for index in range(count):
        temperature, energy = implicit_exchange_step(temperature, energy, dt, parameters)
        history[index + 1] = (
            (index + 1) * dt,
            temperature,
            energy,
            parameters.heat_capacity * temperature + energy,
            total_entropy(temperature, energy, parameters),
        )
    return history


def flux_relax(
    energy: float,
    flux: np.ndarray,
    dt: float,
    parameters: RadiationParameters,
) -> tuple[np.ndarray, np.ndarray]:
    if not math.isfinite(dt) or dt < 0.0:
        raise ValueError("dt must be finite and nonnegative")
    flux = np.asarray(flux, dtype=np.float64)
    m1_pressure(energy, flux, parameters.light_speed)
    attenuation = math.exp(-parameters.light_speed * parameters.transport * dt)
    next_flux = flux * attenuation
    matter_momentum_gain = (flux - next_flux) / parameters.light_speed**2
    return next_flux, matter_momentum_gain


def diffusion_flux(
    energy_gradient: np.ndarray, transport_extinction: float, light_speed: float
) -> np.ndarray:
    energy_gradient = np.asarray(energy_gradient, dtype=np.float64)
    if energy_gradient.shape != (3,) or not np.isfinite(energy_gradient).all():
        raise ValueError("energy gradient must be one finite three-vector")
    if not math.isfinite(transport_extinction) or transport_extinction <= 0.0:
        raise ValueError("transport extinction must be finite and positive")
    if not math.isfinite(light_speed) or light_speed <= 0.0:
        raise ValueError("light speed must be finite and positive")
    return -(light_speed / (3.0 * transport_extinction)) * energy_gradient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--time", type=float, default=2.0)
    parser.add_argument("--dt", type=float, default=0.01)
    parser.add_argument("--temperature", type=float, default=2.0)
    parser.add_argument("--radiation-energy", type=float, default=0.1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    parameters = RadiationParameters()
    history = evolve_exchange(
        args.temperature,
        args.radiation_energy,
        args.time,
        args.dt,
        parameters,
    )
    initial = history[0]
    final = history[-1]
    equilibrium = equilibrium_temperature(initial[3], parameters)
    report = {
        "parameters": asdict(parameters),
        "steps": len(history) - 1,
        "initial": {
            "temperature": initial[1],
            "radiation_energy": initial[2],
            "total_energy": initial[3],
            "entropy": initial[4],
        },
        "final": {
            "temperature": final[1],
            "radiation_energy": final[2],
            "total_energy": final[3],
            "entropy": final[4],
        },
        "equilibrium_temperature": equilibrium,
        "equilibrium_radiation_energy": lte_energy(equilibrium, parameters),
        "max_total_energy_drift": float(np.max(np.abs(history[:, 3] - initial[3]))),
        "minimum_entropy_step": float(np.min(np.diff(history[:, 4]))),
    }
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
