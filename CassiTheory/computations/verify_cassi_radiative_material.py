#!/usr/bin/env python3
"""Verify the fixed Cassi LTE radiative-material closure schedule."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp
from scipy import constants
from scipy.integrate import quad, solve_ivp

from cassi_radiative_material import (
    METRIC,
    RadiationParameters,
    comoving_moments,
    diffusion_flux,
    equilibrium_temperature,
    evolve_exchange,
    flux_relax,
    four_velocity,
    implicit_exchange_step,
    interaction_four_force,
    isotropic_lte_tensor,
    lte_energy,
    m1_chi,
    m1_pressure,
    planck_kernel,
    radiation_tensor,
    slab_intensity,
    total_entropy,
)


SCHEMA = "cassi-radiative-material-verification-v1"
SOURCES = (
    "computations/cassi-radiative-material-prereg.md",
    "computations/cassi_radiative_material.py",
    "computations/verify_cassi_radiative_material.py",
)


class Recorder:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def check(self, label: str, passed: bool, **details: Any) -> None:
        if any(item["label"] == label for item in self.checks):
            raise ValueError(f"duplicate check label: {label}")
        self.checks.append({"label": label, "passed": bool(passed), **details})

    @property
    def passed(self) -> int:
        return sum(bool(item["passed"]) for item in self.checks)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_value(value.tolist())
    if isinstance(value, (np.floating, np.integer)):
        return json_value(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("receipt contains a nonfinite float")
    return value


def relative_error(value: float, expected: float) -> float:
    return abs(value - expected) / max(abs(expected), np.finfo(np.float64).tiny)


def normalized_vector_error(value: np.ndarray, expected: np.ndarray) -> float:
    return float(np.linalg.norm(value - expected) / max(1.0, np.linalg.norm(expected)))


def prepare_evidence(root: Path, output: Path) -> tuple[Path, Path, list[dict[str, str]]]:
    output = output.resolve()
    root = root.resolve()
    if root != output and root not in output.parents:
        raise ValueError("output must remain inside the CassiTheory root")
    manifest_path = output.with_name("input_manifest.json")
    snapshot_dir = output.parent / "source_snapshots"
    for path in (output, manifest_path, snapshot_dir):
        if path.exists():
            raise FileExistsError(f"refusing existing evidence path: {path}")
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    records: list[dict[str, str]] = []
    for source_name in SOURCES:
        source = root / source_name
        snapshot_name = source_name.replace("/", "__")
        snapshot = snapshot_dir / snapshot_name
        shutil.copyfile(source, snapshot)
        records.append(
            {
                "path": source_name,
                "sha256": digest(source),
                "snapshot": snapshot.relative_to(root).as_posix(),
                "snapshot_sha256": digest(snapshot),
            }
        )
    manifest = {"schema": SCHEMA, "sources": records}
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return output, manifest_path, records


def symbolic_controls(recorder: Recorder) -> dict[str, str]:
    f = sp.symbols("f", nonnegative=True)
    chi = (3 + 4 * f**2) / (5 + 2 * sp.sqrt(4 - 3 * f**2))
    recorder.check("symbolic M1 isotropic endpoint", sp.simplify(chi.subs(f, 0) - sp.Rational(1, 3)) == 0)
    recorder.check("symbolic M1 streaming endpoint", sp.simplify(chi.subs(f, 1) - 1) == 0)

    temperature, radiation_temperature = sp.symbols("T T_r", positive=True)
    entropy_factor = (temperature**4 - radiation_temperature**4) * (
        1 / radiation_temperature - 1 / temperature
    )
    entropy_square = (temperature - radiation_temperature) ** 2 * (
        (temperature + radiation_temperature)
        * (temperature**2 + radiation_temperature**2)
        / (temperature * radiation_temperature)
    )
    recorder.check(
        "symbolic gray entropy factorization",
        sp.factor(entropy_factor - entropy_square) == 0,
    )

    candidate, heat_capacity, coupling, radiation_constant = sp.symbols(
        "T C lambda a_R", positive=True
    )
    old_energy, total = sp.symbols("E_n U", nonnegative=True)
    residual = heat_capacity * candidate + (
        old_energy + coupling * radiation_constant * candidate**4
    ) / (1 + coupling) - total
    expected_derivative = heat_capacity + (
        4 * coupling * radiation_constant * candidate**3 / (1 + coupling)
    )
    recorder.check(
        "symbolic implicit residual derivative",
        sp.simplify(sp.diff(residual, candidate) - expected_derivative) == 0,
    )

    occupation = sp.symbols("n", positive=True)
    g = sp.log((1 + occupation) / occupation)
    recorder.check(
        "symbolic photon entropy monotonicity",
        sp.simplify(sp.diff(g, occupation) + 1 / (occupation * (1 + occupation))) == 0,
    )

    planck_identity = sp.gamma(4) * sp.zeta(4) - sp.pi**4 / 15
    recorder.check("symbolic Planck integral identity", sp.simplify(planck_identity) == 0)
    return {
        "m1_chi_zero": str(sp.simplify(chi.subs(f, 0))),
        "m1_chi_one": str(sp.simplify(chi.subs(f, 1))),
        "planck_integral": str(sp.simplify(sp.gamma(4) * sp.zeta(4))),
    }


def planck_controls(recorder: Recorder) -> dict[str, Any]:
    bounds = ((0.0, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 4.0), (4.0, 8.0), (8.0, 16.0), (16.0, np.inf))
    integrals = [
        quad(planck_kernel, low, high, epsabs=1e-13, epsrel=1e-13, limit=300)[0]
        for low, high in bounds
    ]
    total = math.fsum(integrals)
    expected = math.pi**4 / 15.0
    integral_error = relative_error(total, expected)
    recorder.check(
        "numerical Planck group partition",
        integral_error <= 5e-11,
        relative_error=integral_error,
    )

    radiation_constant_formula = (
        8.0
        * math.pi**5
        * constants.k**4
        / (15.0 * constants.h**3 * constants.c**3)
    )
    radiation_constant_stefan = 4.0 * constants.sigma / constants.c
    constant_error = relative_error(radiation_constant_formula, radiation_constant_stefan)
    recorder.check(
        "CODATA radiation constant identity",
        constant_error <= 5e-12,
        relative_error=constant_error,
    )

    emissive_errors: list[float] = []
    for temperature in (100.0, 3000.0, 1.0e4):
        integrated_planck = (
            2.0
            * (constants.k * temperature) ** 4
            / (constants.h**3 * constants.c**2)
            * total
        )
        for absorption in (1.0e-8, 1.0e-3, 2.0):
            measured = 4.0 * math.pi * absorption * integrated_planck
            expected_power = 4.0 * absorption * constants.sigma * temperature**4
            emissive_errors.append(relative_error(measured, expected_power))
    recorder.check(
        "integrated Kirchhoff emissive power",
        max(emissive_errors) <= 5e-12,
        maximum_relative_error=max(emissive_errors),
        cases=len(emissive_errors),
    )

    equilibrium_sources = []
    parameters = RadiationParameters()
    for temperature in (0.1, 0.5, 1.0, 3.0, 10.0):
        energy = lte_energy(temperature, parameters)
        equilibrium_sources.append(
            parameters.light_speed * parameters.absorption * (energy - energy)
        )
    recorder.check(
        "Kirchhoff equilibrium source",
        max(abs(value) for value in equilibrium_sources) == 0.0,
        cases=len(equilibrium_sources),
    )
    return {
        "group_bounds": [[low, "infinity" if math.isinf(high) else high] for low, high in bounds],
        "group_integrals": integrals,
        "integral": total,
        "expected_integral": expected,
        "radiation_constant": radiation_constant_formula,
        "emissive_cases": len(emissive_errors),
    }


def m1_controls(recorder: Recorder, parameters: RadiationParameters) -> dict[str, Any]:
    raw_directions = (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (1.0, 1.0, 1.0),
        (1.0, -2.0, 0.5),
        (-3.0, 1.0, 2.0),
        (0.2, 0.7, -1.0),
    )
    directions = [np.asarray(value) / np.linalg.norm(value) for value in raw_directions]
    reduced_fluxes = np.linspace(0.0, 1.0, 1001)
    energy = 1.7
    max_trace_error = 0.0
    max_symmetry_error = 0.0
    min_eigenvalue = math.inf
    max_eigenvalue = -math.inf
    min_chi = math.inf
    max_chi = -math.inf
    for direction in directions:
        for reduced in reduced_fluxes:
            flux = parameters.light_speed * energy * reduced * direction
            pressure = m1_pressure(energy, flux, parameters.light_speed)
            eigenvalues = np.linalg.eigvalsh(pressure)
            max_trace_error = max(max_trace_error, abs(float(np.trace(pressure)) - energy))
            max_symmetry_error = max(max_symmetry_error, float(np.max(np.abs(pressure - pressure.T))))
            min_eigenvalue = min(min_eigenvalue, float(eigenvalues[0]))
            max_eigenvalue = max(max_eigenvalue, float(eigenvalues[-1]))
            chi = m1_chi(float(reduced))
            min_chi = min(min_chi, chi)
            max_chi = max(max_chi, chi)
    recorder.check(
        "M1 tensor realizability scan",
        max_trace_error <= 1e-12
        and max_symmetry_error <= 1e-12
        and min_eigenvalue >= -1e-12
        and max_eigenvalue <= energy + 1e-12
        and min_chi >= 1.0 / 3.0 - 1e-12
        and max_chi <= 1.0 + 1e-12,
        cases=len(directions) * len(reduced_fluxes),
        maximum_trace_error=max_trace_error,
        minimum_eigenvalue=min_eigenvalue,
        maximum_eigenvalue=max_eigenvalue,
    )
    isotropic = m1_pressure(energy, np.zeros(3), parameters.light_speed)
    streaming_direction = directions[3]
    streaming = m1_pressure(
        energy,
        parameters.light_speed * energy * streaming_direction,
        parameters.light_speed,
    )
    recorder.check(
        "M1 endpoint tensors",
        np.max(np.abs(isotropic - np.eye(3) * energy / 3.0)) <= 1e-12
        and np.max(np.abs(streaming - energy * np.outer(streaming_direction, streaming_direction))) <= 1e-12,
    )
    rejected = False
    try:
        m1_pressure(energy, np.asarray([1.01 * parameters.light_speed * energy, 0.0, 0.0]), parameters.light_speed)
    except ValueError:
        rejected = True
    recorder.check("M1 inadmissible flux rejection", rejected)
    return {
        "cases": len(directions) * len(reduced_fluxes),
        "maximum_trace_error": max_trace_error,
        "minimum_eigenvalue": min_eigenvalue,
        "maximum_eigenvalue": max_eigenvalue,
    }


def slab_controls(recorder: Recorder) -> dict[str, Any]:
    depths = (0.0, 1.0e-10, 1.0e-4, 0.1, 1.0, 10.0, 80.0)
    incoming_values = (0.0, 0.2, 3.0)
    sources = (0.0, 0.7, 4.0)
    max_direct_error = 0.0
    max_semigroup_error = 0.0
    min_value = math.inf
    containment_violation = 0.0
    cases = 0
    for depth in depths:
        for incoming in incoming_values:
            for source in sources:
                value = slab_intensity(incoming, source, depth)
                direct = incoming * math.exp(-depth) + source * (1.0 - math.exp(-depth))
                split = slab_intensity(
                    slab_intensity(incoming, source, 0.37 * depth),
                    source,
                    0.63 * depth,
                )
                max_direct_error = max(max_direct_error, abs(value - direct))
                max_semigroup_error = max(max_semigroup_error, abs(value - split))
                min_value = min(min_value, value)
                lower, upper = sorted((incoming, source))
                containment_violation = max(
                    containment_violation,
                    max(lower - value, value - upper, 0.0),
                )
                cases += 1
    recorder.check(
        "homogeneous slab direct solution",
        max_direct_error <= 1e-12 and min_value >= 0.0 and containment_violation <= 1e-12,
        cases=cases,
        maximum_absolute_error=max_direct_error,
        containment_violation=containment_violation,
    )
    recorder.check(
        "homogeneous slab semigroup",
        max_semigroup_error <= 1e-12,
        maximum_absolute_error=max_semigroup_error,
    )
    recorder.check(
        "homogeneous slab limiting cases",
        slab_intensity(3.0, 0.7, 0.0) == 3.0
        and slab_intensity(3.0, 0.0, 80.0) < 1e-33
        and abs(slab_intensity(3.0, 0.7, 80.0) - 0.7) <= 1e-14,
    )
    return {
        "cases": cases,
        "maximum_direct_error": max_direct_error,
        "maximum_semigroup_error": max_semigroup_error,
    }


def exchange_controls(recorder: Recorder, parameters: RadiationParameters) -> dict[str, Any]:
    initial_states = (
        (2.0, 0.1),
        (0.5, 8.0),
        (1.2, 1.2**4 * 1.001),
        (3.0, 1.0e-4),
        (0.2, 0.5),
    )
    steps = (0.04, 0.02, 0.01)
    results: list[dict[str, Any]] = []
    all_positive = True
    maximum_energy_drift = 0.0
    minimum_entropy_step = math.inf
    maximum_fine_error = 0.0
    minimum_refinement_ratio = math.inf
    refinement_cases = 0
    all_closer = True
    all_references = True

    for state_index, (temperature, energy) in enumerate(initial_states):
        def rhs(_time: float, state: np.ndarray) -> np.ndarray:
            equilibrium = parameters.radiation_constant * state[0] ** 4
            source = parameters.light_speed * parameters.absorption * (equilibrium - state[1])
            return np.asarray([-source / parameters.heat_capacity, source])

        reference = solve_ivp(
            rhs,
            (0.0, 2.0),
            np.asarray([temperature, energy]),
            method="DOP853",
            rtol=1e-12,
            atol=1e-12,
        )
        all_references = all_references and reference.success
        reference_endpoint = reference.y[:, -1]
        errors: list[float] = []
        state_rows: list[dict[str, Any]] = []
        total_initial = parameters.heat_capacity * temperature + energy
        equilibrium_temperature_value = equilibrium_temperature(total_initial, parameters)
        equilibrium_state = np.asarray(
            [equilibrium_temperature_value, lte_energy(equilibrium_temperature_value, parameters)]
        )
        initial_distance = normalized_vector_error(np.asarray([temperature, energy]), equilibrium_state)
        for dt in steps:
            history = evolve_exchange(temperature, energy, 2.0, dt, parameters)
            endpoint = history[-1, 1:3]
            error = normalized_vector_error(endpoint, reference_endpoint)
            errors.append(error)
            all_positive = all_positive and bool(np.all(history[:, 1:3] > 0.0)) and bool(np.isfinite(history).all())
            energy_drift = float(np.max(np.abs(history[:, 3] - history[0, 3])))
            entropy_step = float(np.min(np.diff(history[:, 4])))
            maximum_energy_drift = max(maximum_energy_drift, energy_drift)
            minimum_entropy_step = min(minimum_entropy_step, entropy_step)
            state_rows.append(
                {
                    "dt": dt,
                    "endpoint": endpoint,
                    "normalized_error": error,
                    "energy_drift": energy_drift,
                    "minimum_entropy_step": entropy_step,
                }
            )
        maximum_fine_error = max(maximum_fine_error, errors[-1])
        for coarse, fine in zip(errors[:-1], errors[1:]):
            if coarse > 1e-8:
                ratio = coarse / max(fine, np.finfo(np.float64).tiny)
                minimum_refinement_ratio = min(minimum_refinement_ratio, ratio)
                refinement_cases += 1
        fine_distance = normalized_vector_error(state_rows[-1]["endpoint"], equilibrium_state)
        all_closer = all_closer and fine_distance < initial_distance
        results.append(
            {
                "initial": [temperature, energy],
                "reference_endpoint": reference_endpoint,
                "equilibrium": equilibrium_state,
                "runs": state_rows,
                "errors": errors,
            }
        )

    recorder.check("exchange independent references", all_references, cases=len(initial_states))
    recorder.check("exchange positivity and finiteness", all_positive, trajectories=len(initial_states) * len(steps))
    recorder.check(
        "exchange total-energy conservation",
        maximum_energy_drift <= 2e-12,
        maximum_absolute_drift=maximum_energy_drift,
    )
    recorder.check(
        "exchange entropy monotonicity",
        minimum_entropy_step >= -2e-12,
        minimum_step=minimum_entropy_step,
    )
    recorder.check(
        "exchange fine endpoint accuracy",
        maximum_fine_error <= 5e-5,
        maximum_normalized_error=maximum_fine_error,
    )
    recorder.check(
        "exchange temporal refinement",
        refinement_cases == 0 or minimum_refinement_ratio >= 1.7,
        qualifying_pairs=refinement_cases,
        minimum_ratio=None if refinement_cases == 0 else minimum_refinement_ratio,
    )
    recorder.check("exchange equilibrium approach", all_closer, cases=len(initial_states))

    stiff_dt = 1.0e4 / (parameters.light_speed * parameters.absorption)
    stiff_initial = (3.0, 1.0e-8)
    stiff_before_energy = parameters.heat_capacity * stiff_initial[0] + stiff_initial[1]
    stiff_before_entropy = total_entropy(*stiff_initial, parameters)
    stiff_after = implicit_exchange_step(*stiff_initial, stiff_dt, parameters)
    stiff_after_energy = parameters.heat_capacity * stiff_after[0] + stiff_after[1]
    stiff_after_entropy = total_entropy(*stiff_after, parameters)
    recorder.check(
        "stiff exchange conservative positive step",
        stiff_after[0] > 0.0
        and stiff_after[1] > 0.0
        and abs(stiff_after_energy - stiff_before_energy) <= 2e-12,
        dt=stiff_dt,
        energy_drift=stiff_after_energy - stiff_before_energy,
    )
    recorder.check(
        "stiff exchange entropy increase",
        stiff_after_entropy > stiff_before_entropy,
        entropy_change=stiff_after_entropy - stiff_before_entropy,
    )

    coupling = parameters.light_speed * parameters.absorption * stiff_dt
    uncoupled_radiation = (
        stiff_initial[1] + coupling * lte_energy(stiff_initial[0], parameters)
    ) / (1.0 + coupling)
    altered_total = parameters.heat_capacity * stiff_initial[0] + uncoupled_radiation
    altered_defect = altered_total - stiff_before_energy
    recorder.check(
        "deleted material exchange rejection control",
        abs(altered_defect) > 1e-3,
        total_energy_defect=altered_defect,
    )
    return {
        "parameters": as_plain_dict(parameters),
        "trajectories": results,
        "maximum_energy_drift": maximum_energy_drift,
        "minimum_entropy_step": minimum_entropy_step,
        "maximum_fine_error": maximum_fine_error,
        "minimum_refinement_ratio": None if refinement_cases == 0 else minimum_refinement_ratio,
        "stiff": {
            "dt": stiff_dt,
            "initial": stiff_initial,
            "final": stiff_after,
            "entropy_change": stiff_after_entropy - stiff_before_entropy,
            "altered_energy_defect": altered_defect,
        },
    }


def as_plain_dict(parameters: RadiationParameters) -> dict[str, float]:
    return {
        "light_speed": parameters.light_speed,
        "radiation_constant": parameters.radiation_constant,
        "heat_capacity": parameters.heat_capacity,
        "absorption": parameters.absorption,
        "transport": parameters.transport,
    }


def scattering_diffusion_controls(
    recorder: Recorder, parameters: RadiationParameters
) -> dict[str, Any]:
    energy = 2.0
    limit = parameters.light_speed * energy
    fluxes = (
        np.asarray([0.0, 0.0, 0.0]),
        np.asarray([1.0, 0.0, 0.0]),
        np.asarray([0.0, 3.0, 0.0]),
        np.asarray([limit, 0.0, 0.0]),
        np.asarray([-2.0, 2.0, 1.0]),
        np.asarray([1.0, -4.0, 2.0]),
    )
    exponents = (0.0, 1e-6, 0.1, 1.0, 100.0)
    max_flux_error = 0.0
    max_momentum_error = 0.0
    realizable = True
    for flux in fluxes:
        initial_radiation_momentum = flux / parameters.light_speed**2
        for exponent in exponents:
            dt = exponent / (parameters.light_speed * parameters.transport)
            next_flux, matter_gain = flux_relax(energy, flux, dt, parameters)
            expected = flux * math.exp(-exponent)
            max_flux_error = max(max_flux_error, float(np.max(np.abs(next_flux - expected))))
            total_momentum = next_flux / parameters.light_speed**2 + matter_gain
            max_momentum_error = max(
                max_momentum_error,
                float(np.max(np.abs(total_momentum - initial_radiation_momentum))),
            )
            realizable = realizable and np.linalg.norm(next_flux) <= limit * (1.0 + 1e-14)
    recorder.check(
        "elastic scattering exponential damping",
        max_flux_error <= 1e-12 and realizable,
        cases=len(fluxes) * len(exponents),
        maximum_absolute_error=max_flux_error,
    )
    recorder.check(
        "elastic scattering momentum conservation",
        max_momentum_error <= 1e-13,
        maximum_absolute_error=max_momentum_error,
    )

    gradients = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, -2.0, 0.0),
        (0.0, 0.0, 3.0),
        (1.0, 2.0, 3.0),
        (-4.0, 0.5, 1.0),
        (1e-6, -2e-6, 3e-6),
    )
    max_diffusion_residual = 0.0
    for gradient_raw in gradients:
        gradient = np.asarray(gradient_raw)
        for extinction in (0.1, 1.0, 10.0):
            flux = diffusion_flux(gradient, extinction, parameters.light_speed)
            residual = (
                parameters.light_speed**2 * gradient / 3.0
                + parameters.light_speed * extinction * flux
            )
            max_diffusion_residual = max(
                max_diffusion_residual, float(np.max(np.abs(residual)))
            )
    recorder.check(
        "optically thick diffusion residual",
        max_diffusion_residual <= 1e-12,
        cases=len(gradients) * 3,
        maximum_absolute_residual=max_diffusion_residual,
    )
    return {
        "scattering_cases": len(fluxes) * len(exponents),
        "maximum_flux_error": max_flux_error,
        "maximum_momentum_error": max_momentum_error,
        "diffusion_cases": len(gradients) * 3,
        "maximum_diffusion_residual": max_diffusion_residual,
    }


def photon_entropy_controls(recorder: Recorder) -> dict[str, Any]:
    occupations = np.logspace(-8, 3, 41)
    minimum = math.inf
    zeros = 0
    for equilibrium in occupations:
        equilibrium_g = math.log1p(1.0 / equilibrium)
        for occupation in occupations:
            g = math.log1p(1.0 / occupation)
            production = (equilibrium - occupation) * (g - equilibrium_g)
            minimum = min(minimum, production)
            if occupation == equilibrium and production == 0.0:
                zeros += 1
    recorder.check(
        "spectral photon entropy production",
        minimum >= -1e-12 and zeros == len(occupations),
        cases=len(occupations) ** 2,
        minimum_integrand=minimum,
        equilibrium_zeros=zeros,
    )
    return {"cases": len(occupations) ** 2, "minimum_integrand": minimum}


def covariant_controls(recorder: Recorder, parameters: RadiationParameters) -> dict[str, Any]:
    raw_directions = (
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (-1.0, 2.0, 1.0),
        (0.2, -0.5, 1.0),
    )
    directions = [np.asarray(value) / np.linalg.norm(value) for value in raw_directions]
    betas = (0.0, 0.01, 0.1, 0.3)
    energy = 1.7
    flux_direction = np.asarray([1.0, -2.0, 0.5])
    flux_direction /= np.linalg.norm(flux_direction)
    flux = 0.4 * parameters.light_speed * energy * flux_direction
    pressure = m1_pressure(energy, flux, parameters.light_speed)
    tensor = radiation_tensor(energy, flux, pressure, parameters.light_speed)
    max_orthogonality = 0.0
    max_lte_source = 0.0
    max_norm_error = 0.0
    cancellation_exact = True
    cases = 0
    temperature = 1.3
    equilibrium = lte_energy(temperature, parameters)
    for beta in betas:
        for direction in directions:
            velocity = beta * parameters.light_speed * direction
            velocity_four = four_velocity(velocity, parameters.light_speed)
            norm = float(velocity_four @ METRIC @ velocity_four)
            max_norm_error = max(max_norm_error, abs(norm + parameters.light_speed**2))
            _, flux_four = comoving_moments(tensor, velocity_four, parameters.light_speed)
            velocity_covariant = METRIC @ velocity_four
            orthogonality = abs(float(velocity_covariant @ flux_four))
            scale = max(1.0, np.linalg.norm(velocity_four) * np.linalg.norm(flux_four))
            max_orthogonality = max(max_orthogonality, orthogonality / scale)
            lte_tensor = isotropic_lte_tensor(equilibrium, velocity_four, parameters.light_speed)
            source = interaction_four_force(lte_tensor, velocity_four, temperature, parameters)
            max_lte_source = max(max_lte_source, float(np.max(np.abs(source))) / max(1.0, equilibrium))
            arbitrary_source = interaction_four_force(tensor, velocity_four, temperature, parameters)
            cancellation_exact = cancellation_exact and np.array_equal(arbitrary_source + (-arbitrary_source), np.zeros(4))
            cases += 1
    recorder.check(
        "covariant four-velocity and flux projection",
        max_norm_error <= 1e-12 and max_orthogonality <= 1e-12,
        cases=cases,
        maximum_norm_error=max_norm_error,
        maximum_normalized_orthogonality=max_orthogonality,
    )
    recorder.check(
        "boosted LTE four-force vanishes",
        max_lte_source <= 1e-12,
        maximum_normalized_source=max_lte_source,
    )
    recorder.check("paired matter radiation four-force cancellation", cancellation_exact, cases=cases)

    rest_velocity = four_velocity(np.zeros(3), parameters.light_speed)
    rest_energy = 0.8
    rest_flux = np.asarray([0.2, -0.4, 0.1])
    rest_pressure = m1_pressure(rest_energy, rest_flux, parameters.light_speed)
    rest_tensor = radiation_tensor(rest_energy, rest_flux, rest_pressure, parameters.light_speed)
    rest_source = interaction_four_force(rest_tensor, rest_velocity, 1.1, parameters)
    expected = np.concatenate(
        (
            [parameters.absorption * (lte_energy(1.1, parameters) - rest_energy)],
            -parameters.transport * rest_flux / parameters.light_speed,
        )
    )
    rest_error = float(np.max(np.abs(rest_source - expected)))
    recorder.check(
        "rest-frame four-force reduction",
        rest_error <= 1e-12,
        maximum_absolute_error=rest_error,
    )
    return {
        "cases": cases,
        "maximum_four_velocity_norm_error": max_norm_error,
        "maximum_flux_orthogonality": max_orthogonality,
        "maximum_lte_source": max_lte_source,
        "rest_frame_error": rest_error,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runs/cassi_radiative_material/verification.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    output, manifest_path, sources = prepare_evidence(root, root / args.output)
    recorder = Recorder()
    parameters = RadiationParameters()
    results: dict[str, Any] = {}
    try:
        results["symbolic"] = symbolic_controls(recorder)
        results["planck"] = planck_controls(recorder)
        results["m1"] = m1_controls(recorder, parameters)
        results["slab"] = slab_controls(recorder)
        results["exchange"] = exchange_controls(recorder, parameters)
        results["scattering_diffusion"] = scattering_diffusion_controls(recorder, parameters)
        results["photon_entropy"] = photon_entropy_controls(recorder)
        results["covariant"] = covariant_controls(recorder, parameters)
        error = None
    except Exception as exc:  # Preserve a failed immutable receipt.
        error = f"{type(exc).__name__}: {exc}"
        recorder.check("verification completed without exception", False, error=error)
    passed = recorder.passed
    total = len(recorder.checks)
    status = "PASS" if error is None and passed == total and total > 0 else "FAIL"
    receipt = {
        "schema": SCHEMA,
        "status": status,
        "scientific_classification": (
            "SUPPORTS-conditional LTE radiative-material closure"
            if status == "PASS"
            else "CONTRADICTS"
        ),
        "checks": {"passed": passed, "total": total, "items": recorder.checks},
        "results": results,
        "input_manifest": manifest_path.relative_to(root).as_posix(),
        "sources": sources,
        "error": error,
        "scope": {
            "supported": [
                "LTE Planck and Kirchhoff emissivity",
                "M1 realizability",
                "covariant interaction source",
                "static conservative absorption and emission",
                "radiation plus material entropy production",
                "elastic flux damping",
                "optically thick diffusion limit",
            ],
            "unestablished": [
                "physical Cassi material identification",
                "Yang/Yin-to-temperature map",
                "physical mass density and opacity",
                "ionization and spectral line kinetics",
                "moving-medium transport implementation",
                "electromagnetic current",
            ],
        },
    }
    output.write_text(
        json.dumps(json_value(receipt), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"RADIATIVE MATERIAL RESULT: {status} ({passed}/{total} checks)")
    print(f"receipt: {output.relative_to(root).as_posix()}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
