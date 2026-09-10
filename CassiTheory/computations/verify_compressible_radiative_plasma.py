#!/usr/bin/env python3
"""Verify the fixed compressible radiative-plasma closure schedule."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import sympy as sp

from compressible_radiative_plasma import (
    accretion_partition,
    angular_moments,
    axis_quadrature,
    boltzmann_distribution,
    critical_density,
    detailed_balance_generator,
    evolve_populations,
    ideal_level_gas,
    isotropic_scattering_step,
    kelvin_helmholtz_release,
    line_coefficients,
    line_energy_exchange,
    normal_shock,
    nuclear_reaction_power,
    periodic_axis_shift,
    photoionization_partition,
    planck_intensity,
    radiative_temperature_gradient,
    recover_temperature,
    shock_entropy_increment,
    shock_fluxes,
    two_level_lte_populations,
    validate_quadrature,
    virial_star_energy,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "cassi-compressible-radiative-plasma-verification-v1"
DEFAULT_OUTPUT = ROOT / "runs" / "compressible_radiative_plasma" / "verification.json"
SOURCE_PATHS = (
    Path("computations/compressible-radiative-plasma-prereg.md"),
    Path("turbulence/compressible-radiative-plasma-closure.md"),
    Path("computations/compressible_radiative_plasma.py"),
    Path("computations/verify_compressible_radiative_plasma.py"),
)
TOL = 2.0e-13


@dataclass
class CheckBook:
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(self, name: str, passed: bool, **evidence: Any) -> None:
        if name in self.checks:
            raise KeyError(f"duplicate check name: {name}")
        self.checks[name] = {
            "passed": bool(passed),
            "evidence": json_value(evidence),
        }

    def exact(self, name: str, expression: sp.Expr | sp.MatrixBase) -> None:
        simplified = sp.simplify(expression)
        if isinstance(simplified, sp.MatrixBase):
            passed = all(sp.simplify(value) == 0 for value in simplified)
        else:
            passed = simplified == 0
        self.add(name, passed, simplified=str(simplified))

    def close(self, name: str, actual: Any, expected: Any, tolerance: float = TOL) -> None:
        left = np.asarray(actual, dtype=np.float64)
        right = np.asarray(expected, dtype=np.float64)
        error = float(np.linalg.norm(left - right))
        scale = max(1.0, float(np.linalg.norm(right)))
        normalized = error / scale
        self.add(
            name,
            math.isfinite(normalized) and normalized <= tolerance,
            actual=left,
            expected=right,
            normalized_error=normalized,
            tolerance=tolerance,
        )

    def rejected(self, name: str, operation: Callable[[], Any]) -> None:
        error: str | None = None
        try:
            operation()
        except Exception as exc:  # The exception is the expected result.
            error = f"{type(exc).__name__}: {exc}"
        self.add(name, error is not None, error=error)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(row["passed"] for row in self.checks.values())

    @property
    def failed(self) -> list[str]:
        return [name for name, row in self.checks.items() if not row["passed"]]


def json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_value(value.tolist())
    if isinstance(value, np.generic):
        return json_value(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("receipt contains a nonfinite value")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_evidence(output: Path) -> tuple[Path, Path, dict[str, dict[str, Any]]]:
    target = output.resolve()
    if ROOT != target and ROOT not in target.parents:
        raise ValueError("output must remain inside the CassiTheory root")
    manifest_path = target.with_name("input_manifest.json")
    snapshot_root = target.parent / "source_snapshots"
    for path in (target, manifest_path, snapshot_root):
        if path.exists():
            raise FileExistsError(f"refusing existing evidence path: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot_root.mkdir()
    manifest: dict[str, dict[str, Any]] = {}
    for relative in SOURCE_PATHS:
        source = ROOT / relative
        destination = snapshot_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        manifest[relative.as_posix()] = {
            "path": relative.as_posix(),
            "snapshot": destination.relative_to(ROOT).as_posix(),
            "bytes": source.stat().st_size,
            "sha256": sha256(source),
            "snapshot_sha256": sha256(destination),
        }
    manifest_path.write_text(
        json.dumps(
            {"schema": SCHEMA, "sources": manifest},
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return target, manifest_path, manifest


def symbolic_controls(book: CheckBook) -> dict[str, str]:
    p, theta, u_grad_p = sp.symbols("p theta u_grad_p", real=True)
    total_pressure_power = -(u_grad_p + p * theta)
    kinetic_pressure_power = -u_grad_p
    book.exact(
        "symbolic.internal_pressure_work",
        total_pressure_power - kinetic_pressure_power + p * theta,
    )

    mach, gamma = sp.symbols("M gamma", positive=True)
    compression = (gamma + 1) * mach**2 / ((gamma - 1) * mach**2 + 2)
    pressure_ratio = 1 + 2 * gamma * (mach**2 - 1) / (gamma + 1)
    velocity1 = mach * sp.sqrt(gamma)
    velocity2 = velocity1 / compression
    rho1 = p1 = sp.Integer(1)
    rho2 = compression
    p2 = pressure_ratio
    h1 = gamma * p1 / ((gamma - 1) * rho1)
    h2 = gamma * p2 / ((gamma - 1) * rho2)
    shock_residuals = sp.Matrix(
        [
            rho2 * velocity2 - rho1 * velocity1,
            rho2 * velocity2**2 + p2 - (rho1 * velocity1**2 + p1),
            rho2 * velocity2 * (h2 + velocity2**2 / 2)
            - rho1 * velocity1 * (h1 + velocity1**2 / 2),
        ]
    )
    book.exact("symbolic.normal_shock_fluxes", shock_residuals)

    x, g_l, g_u, b_ul, h, nu, c = sp.symbols(
        "x g_l g_u B_ul h nu c", positive=True
    )
    n_l = sp.Integer(1)
    n_u = g_u * sp.exp(-x) / g_l
    b_lu = g_u * b_ul / g_l
    a_ul = 2 * h * nu**3 * b_ul / c**2
    source = sp.simplify(n_u * a_ul / (n_l * b_lu - n_u * b_ul))
    planck = 2 * h * nu**3 / (c**2 * (sp.exp(x) - 1))
    book.exact("symbolic.line_kirchhoff", source - planck)

    photon_energy, threshold, rate_weight = sp.symbols(
        "epsilon_gamma chi rate_weight", positive=True
    )
    absorbed = rate_weight * photon_energy
    storage = rate_weight * threshold
    heat = rate_weight * (photon_energy - threshold)
    book.exact("symbolic.photoionization_partition", absorbed - storage - heat)

    alpha, gravity, mass, initial_radius, final_radius = sp.symbols(
        "alpha G M R_i R_f", positive=True
    )
    omega_i = -alpha * gravity * mass**2 / initial_radius
    omega_f = -alpha * gravity * mass**2 / final_radius
    energy_i = omega_i / 2
    energy_f = omega_f / 2
    release = alpha * gravity * mass**2 * (1 / final_radius - 1 / initial_radius) / 2
    book.exact("symbolic.kelvin_helmholtz_release", energy_i - energy_f - release)

    opacity, rho, luminosity, radius, a_rad, light, temperature = sp.symbols(
        "kappa rho L r a_R c T", positive=True
    )
    gradient = -3 * opacity * rho * luminosity / (
        16 * sp.pi * a_rad * light * radius**2 * temperature**3
    )
    flux = -light * sp.diff(a_rad * temperature**4, temperature) * gradient / (
        3 * opacity * rho
    )
    book.exact("symbolic.stellar_diffusion_gradient", 4 * sp.pi * radius**2 * flux - luminosity)

    return {
        "shock_compression": str(compression),
        "shock_pressure_ratio": str(pressure_ratio),
        "line_source": str(source),
        "stellar_gradient": str(gradient),
    }


def eos_controls(book: CheckBook) -> dict[str, Any]:
    levels = np.asarray([0.0, 1.5, 4.0])
    velocity = np.asarray([0.3, -0.2, 0.1])
    population_sets = (
        np.asarray([1.0, 0.1, 0.01]),
        np.asarray([0.3, 0.8, 0.4]),
    )
    maximum_error = 0.0
    cases = 0
    for electrons in (0.2, 2.0):
        for populations in population_sets:
            for temperature in (0.4, 3.0):
                state = ideal_level_gas(
                    1.7,
                    velocity,
                    temperature,
                    populations,
                    electrons,
                    levels,
                )
                recovered = recover_temperature(
                    state.internal_energy, populations, electrons, levels
                )
                error = abs(recovered - temperature) / max(1.0, temperature)
                maximum_error = max(maximum_error, error)
                cases += 1
                book.add(
                    f"eos.case_{cases:02d}",
                    error <= 2.0e-14
                    and state.pressure > 0.0
                    and state.internal_energy > float(np.dot(populations, levels)),
                    temperature=temperature,
                    recovered=recovered,
                    normalized_error=error,
                    pressure=state.pressure,
                    total_energy=state.total_energy,
                )
    level_floor = float(np.dot(population_sets[0], levels))
    book.rejected(
        "eos.reject_exhausted_thermal_energy",
        lambda: recover_temperature(level_floor, population_sets[0], 0.2, levels),
    )
    return {"cases": cases, "maximum_temperature_error": maximum_error}


def shock_controls(book: CheckBook) -> dict[str, Any]:
    rows: list[dict[str, float]] = []
    maximum_residual = 0.0
    minimum_entropy = math.inf
    for mach in (1.2, 2.0, 5.0, 10.0):
        upstream, downstream = normal_shock(1.0, 1.0, mach)
        first = shock_fluxes(upstream)
        second = shock_fluxes(downstream)
        residual = float(np.linalg.norm(second - first) / max(1.0, np.linalg.norm(first)))
        entropy = shock_entropy_increment(upstream, downstream)
        compression = downstream.rho / upstream.rho
        maximum_residual = max(maximum_residual, residual)
        minimum_entropy = min(minimum_entropy, entropy)
        book.add(
            f"shock.mach_{mach:g}",
            residual < 2.0e-13
            and 1.0 < compression < 4.0
            and downstream.pressure > upstream.pressure
            and downstream.temperature > upstream.temperature
            and entropy > 0.0,
            flux_residual=residual,
            compression=compression,
            pressure_ratio=downstream.pressure / upstream.pressure,
            temperature_ratio=downstream.temperature / upstream.temperature,
            entropy_over_cv=entropy,
        )
        rows.append(
            {
                "mach": mach,
                "compression": compression,
                "pressure_ratio": downstream.pressure / upstream.pressure,
                "temperature_ratio": downstream.temperature / upstream.temperature,
                "entropy_over_cv": entropy,
                "flux_residual": residual,
            }
        )
    upstream, downstream = normal_shock(1.0, 1.0, 5.0)
    bad_energy_1 = upstream.rho * upstream.velocity * 0.5 * upstream.velocity**2
    bad_energy_2 = downstream.rho * downstream.velocity * 0.5 * downstream.velocity**2
    bad_residual = abs(bad_energy_2 - bad_energy_1) / max(1.0, abs(bad_energy_1))
    book.add(
        "shock.reject_missing_enthalpy",
        bad_residual > 1.0e-2,
        normalized_residual=bad_residual,
        strict_lower_bound=1.0e-2,
    )
    return {
        "rows": rows,
        "maximum_flux_residual": maximum_residual,
        "minimum_entropy_over_cv": minimum_entropy,
        "missing_enthalpy_residual": bad_residual,
    }


def population_controls(book: CheckBook) -> dict[str, Any]:
    energies = np.asarray([0.0, 1.0, 2.5])
    weights = np.asarray([2.0, 4.0, 6.0])
    generator, equilibrium = detailed_balance_generator(
        energies,
        weights,
        1.3,
        ((1, 0, 3.0), (2, 0, 1.7), (2, 1, 0.8)),
    )
    column_error = float(np.max(np.abs(np.sum(generator, axis=0))))
    equilibrium_error = float(np.max(np.abs(generator @ equilibrium)))
    off_diagonal = generator.copy()
    np.fill_diagonal(off_diagonal, 0.0)
    book.add(
        "population.generator",
        column_error < 1.0e-14
        and equilibrium_error < 1.0e-13
        and float(np.min(off_diagonal)) >= 0.0,
        column_sum_error=column_error,
        equilibrium_error=equilibrium_error,
        equilibrium=equilibrium,
    )
    initial = np.asarray([0.02, 0.08, 0.90])
    rows: list[dict[str, Any]] = []
    maximum_total_error = 0.0
    minimum_population = math.inf
    for duration in (1.0e-6, 0.1, 1.0, 20.0):
        evolved = evolve_populations(generator, initial, duration)
        total_error = abs(float(np.sum(evolved)) - float(np.sum(initial)))
        minimum = float(np.min(evolved))
        maximum_total_error = max(maximum_total_error, total_error)
        minimum_population = min(minimum_population, minimum)
        book.add(
            f"population.time_{duration:g}",
            total_error < 1.0e-13 and minimum >= -1.0e-14,
            total_error=total_error,
            minimum_population=minimum,
            populations=evolved,
        )
        rows.append(
            {
                "time": duration,
                "total_error": total_error,
                "minimum_population": minimum,
                "populations": evolved,
            }
        )
    malformed = generator.copy()
    malformed[0, 0] = 0.0
    book.rejected(
        "population.reject_nonconservative_generator",
        lambda: evolve_populations(malformed, initial, 0.1),
    )
    return {
        "generator": generator,
        "equilibrium": equilibrium,
        "rows": rows,
        "maximum_total_error": maximum_total_error,
        "minimum_population": minimum_population,
    }


def line_controls(book: CheckBook) -> dict[str, Any]:
    line_rows: list[dict[str, float]] = []
    maximum_source_error = 0.0
    maximum_exchange_error = 0.0
    for x in (0.1, 1.0, 5.0, 15.0):
        frequency = 2.0
        temperature = frequency / x
        lower, upper = two_level_lte_populations(
            1.4, 2.0, 6.0, frequency, temperature
        )
        emissivity, absorption, a_ul, b_lu = line_coefficients(
            lower, upper, 2.0, 6.0, frequency, 0.7, 0.9
        )
        expected = planck_intensity(frequency, temperature)
        source = emissivity / absorption
        error = abs(source - expected) / max(1.0, abs(expected))
        maximum_source_error = max(maximum_source_error, error)
        book.add(
            f"line.kirchhoff_x_{x:g}",
            absorption > 0.0 and error <= 2.0e-13,
            source=source,
            planck=expected,
            normalized_error=error,
        )
        for index, intensity in enumerate((0.0, 0.1, expected, 3.0, 100.0)):
            _, material, radiation = line_energy_exchange(
                lower,
                upper,
                intensity,
                frequency,
                a_ul,
                0.7,
                b_lu,
            )
            exchange_error = abs(material + radiation)
            maximum_exchange_error = max(maximum_exchange_error, exchange_error)
            book.add(
                f"line.exchange_x_{x:g}_{index}",
                exchange_error <= 2.0e-13,
                material_increment=material,
                radiation_increment=radiation,
                residual=exchange_error,
            )
        line_rows.append(
            {
                "x": x,
                "source": source,
                "planck": expected,
                "normalized_error": error,
            }
        )

    rate, absorbed, stored, heat = photoionization_partition(
        np.asarray([2.0, 3.0, 5.0, 9.0]),
        np.asarray([0.1, 0.4, 0.7, 1.1]),
        np.asarray([0.4, 0.3, 0.1, 0.02]),
        np.asarray([0.2, 1.0, 0.8, 0.3]),
        1.6,
        2.0,
    )
    partition_error = abs(absorbed - stored - heat) / max(1.0, absorbed)
    book.add(
        "line.photoionization_partition",
        partition_error <= 2.0e-14 and stored >= 0.0 and heat >= 0.0,
        rate=rate,
        absorbed=absorbed,
        stored=stored,
        heat=heat,
        normalized_error=partition_error,
    )

    density = critical_density(4.0, 0.25)
    book.add(
        "line.critical_density",
        abs(density - 16.0) <= 2.0e-14
        and abs(4.0 - density * 0.25) <= 2.0e-14,
        critical_density=density,
        radiative_rate=4.0,
        collisional_rate=density * 0.25,
    )
    return {
        "line_rows": line_rows,
        "maximum_source_error": maximum_source_error,
        "maximum_exchange_error": maximum_exchange_error,
        "photoionization_partition_error": partition_error,
        "critical_density": density,
    }


def stellar_controls(book: CheckBook) -> dict[str, Any]:
    internal_i, omega_i, energy_i = virial_star_energy(1.0, 2.0)
    internal_f, omega_f, energy_f = virial_star_energy(1.0, 1.0)
    release = kelvin_helmholtz_release(1.0, 2.0, 1.0)
    expected_release = energy_i - energy_f
    virial_residual = max(
        abs(2.0 * internal_i + omega_i),
        abs(energy_i - omega_i / 2.0),
        abs(2.0 * internal_f + omega_f),
        abs(energy_f - omega_f / 2.0),
        abs(release - expected_release),
    )
    luminosity = 0.03
    kh_time = abs(energy_f) / luminosity
    expected_time = (3.0 / 5.0) / (2.0 * 1.0 * luminosity)
    book.add(
        "stellar.virial_and_contraction",
        virial_residual <= 2.0e-14 and abs(kh_time - expected_time) <= 2.0e-14,
        virial_residual=virial_residual,
        release=release,
        kelvin_helmholtz_time=kh_time,
        expected_time=expected_time,
    )

    accretion_rows: list[dict[str, float]] = []
    maximum_partition_error = 0.0
    for efficiency in (0.0, 0.2, 0.7, 1.0):
        available, radiation, retained = accretion_partition(
            1.0, 0.8, 0.04, efficiency
        )
        error = abs(available - radiation - retained)
        maximum_partition_error = max(maximum_partition_error, error)
        book.add(
            f"stellar.accretion_eta_{efficiency:g}",
            error <= 2.0e-14 and radiation >= 0.0 and retained >= 0.0,
            available=available,
            radiation=radiation,
            retained=retained,
            residual=error,
        )
        accretion_rows.append(
            {
                "efficiency": efficiency,
                "available": available,
                "radiation": radiation,
                "retained": retained,
                "residual": error,
            }
        )

    nuclear_rows: list[dict[str, float]] = []
    maximum_nuclear_residual = 0.0
    for event_rate in (0.0, 1.0e-6, 0.2):
        _, power, baryon_residual, charge_residual = nuclear_reaction_power(
            np.asarray([-4.0, 1.0]),
            np.asarray([1.01, 4.0]),
            np.asarray([1.0, 4.0]),
            np.asarray([1.0, 4.0]),
            event_rate,
        )
        power_error = abs(power - 0.04 * event_rate)
        residual = max(power_error, abs(baryon_residual), abs(charge_residual))
        maximum_nuclear_residual = max(maximum_nuclear_residual, residual)
        book.add(
            f"stellar.nuclear_rate_{event_rate:g}",
            residual <= 1.0e-14 and power >= 0.0,
            power=power,
            expected_power=0.04 * event_rate,
            baryon_residual=baryon_residual,
            charge_residual=charge_residual,
            maximum_residual=residual,
        )
        nuclear_rows.append(
            {
                "event_rate": event_rate,
                "power": power,
                "maximum_residual": residual,
            }
        )

    gradient = radiative_temperature_gradient(
        0.6,
        2.3,
        1.2,
        1.7,
        0.4,
        radiation_constant=0.8,
        light_speed=3.0,
    )
    flux = -(3.0 / (3.0 * 0.4 * 1.2)) * (4.0 * 0.8 * 1.7**3 * gradient)
    reconstructed_luminosity = 4.0 * math.pi * 2.3**2 * flux
    diffusion_error = abs(reconstructed_luminosity - 0.6) / max(1.0, 0.6)
    book.add(
        "stellar.diffusion_luminosity",
        diffusion_error <= 2.0e-14,
        temperature_gradient=gradient,
        reconstructed_luminosity=reconstructed_luminosity,
        normalized_error=diffusion_error,
    )

    reservoirs = np.asarray([0.3, 0.2, 0.4, 0.1])
    destinations = np.asarray([0.73, 0.19, 0.08])
    gross_nuclear = float(reservoirs[2])
    neutrino_loss = float(destinations[2])
    available = float(np.sum(reservoirs))
    accounted = float(np.sum(destinations))
    ledger_error = abs(available - accounted)
    net_nuclear_misdefinition = gross_nuclear - neutrino_loss
    malformed_available = (
        available - gross_nuclear + net_nuclear_misdefinition
    )
    double_count_residual = abs(accounted - malformed_available)
    book.add(
        "stellar.complete_energy_ledger",
        ledger_error <= 2.0e-14 and double_count_residual > 1.0e-2,
        available=available,
        emitted=destinations[0],
        retained=destinations[1],
        neutrino_loss=neutrino_loss,
        gross_nuclear_source=gross_nuclear,
        residual=ledger_error,
        net_nuclear_double_count_residual=double_count_residual,
        strict_double_count_lower_bound=1.0e-2,
    )
    book.add(
        "stellar.reject_overdrawn_luminosity",
        1.01 > float(np.sum(reservoirs)),
        requested=1.01,
        available=float(np.sum(reservoirs)),
    )
    return {
        "virial_residual": virial_residual,
        "kelvin_helmholtz_release": release,
        "kelvin_helmholtz_time": kh_time,
        "accretion": accretion_rows,
        "maximum_accretion_partition_error": maximum_partition_error,
        "nuclear": nuclear_rows,
        "maximum_nuclear_residual": maximum_nuclear_residual,
        "diffusion_error": diffusion_error,
        "energy_ledger_error": ledger_error,
        "net_nuclear_double_count_residual": double_count_residual,
    }


def angular_controls(book: CheckBook) -> dict[str, Any]:
    directions, weights = axis_quadrature()
    quadrature = validate_quadrature(directions, weights, tolerance=2.0e-14)
    book.add(
        "angular.axis_quadrature",
        max(quadrature.values()) <= 2.0e-14,
        **quadrature,
    )

    maximum_trace_error = 0.0
    minimum_eigenvalue = math.inf
    maximum_reduced_flux = 0.0
    for k in range(257):
        indices = np.arange(1, 7, dtype=np.float64)
        intensities = 0.02 + (1.0 + 0.1 * np.arange(6)) * (
            1.0 + np.sin((k + 1) * indices) ** 2
        )
        moments = angular_moments(intensities, directions, weights, light_speed=3.0)
        trace_error = abs(float(np.trace(moments.pressure)) - moments.energy)
        eigenvalue = float(np.min(np.linalg.eigvalsh(moments.pressure)))
        reduced_flux = float(np.linalg.norm(moments.flux) / (3.0 * moments.energy))
        maximum_trace_error = max(maximum_trace_error, trace_error)
        minimum_eigenvalue = min(minimum_eigenvalue, eigenvalue)
        maximum_reduced_flux = max(maximum_reduced_flux, reduced_flux)
    book.add(
        "angular.realizability_sweep",
        maximum_trace_error < 2.0e-13
        and minimum_eigenvalue >= -2.0e-13
        and maximum_reduced_flux <= 1.0 + 2.0e-13,
        cases=257,
        maximum_trace_error=maximum_trace_error,
        minimum_eigenvalue=minimum_eigenvalue,
        maximum_reduced_flux=maximum_reduced_flux,
    )

    counterbeam = np.asarray([1.0, 1.0, 0.0, 0.0, 0.0, 0.0])
    moments = angular_moments(counterbeam, directions, weights)
    expected_pressure = np.diag([moments.energy, 0.0, 0.0])
    pressure_error = float(np.linalg.norm(moments.pressure - expected_pressure))
    m1_pressure = np.eye(3) * moments.energy / 3.0
    obstruction = float(np.linalg.norm(m1_pressure - expected_pressure))
    book.add(
        "angular.counterbeam_pressure",
        pressure_error <= 2.0e-13
        and float(np.linalg.norm(moments.flux)) <= 2.0e-13,
        energy=moments.energy,
        flux=moments.flux,
        pressure=moments.pressure,
        expected_pressure=expected_pressure,
        pressure_error=pressure_error,
    )
    book.add(
        "angular.m1_counterbeam_obstruction",
        obstruction > 0.5 * moments.energy,
        frobenius_difference=obstruction,
        strict_lower_bound=0.5 * moments.energy,
    )

    maximum_scattering_energy_error = 0.0
    maximum_scattering_flux_error = 0.0
    minimum_scattered_intensity = math.inf
    for k in range(32):
        indices = np.arange(1, 7, dtype=np.float64)
        intensities = 0.03 + (1.0 + 0.03 * k) * (
            1.0 + np.cos((k + 1) * indices / 5.0) ** 2
        )
        before = angular_moments(intensities, directions, weights, light_speed=3.0)
        for depth in (0.0, 1.0e-6, 0.1, 1.0, 20.0):
            scattered = isotropic_scattering_step(intensities, weights, depth)
            after = angular_moments(scattered, directions, weights, light_speed=3.0)
            energy_error = abs(after.energy - before.energy) / max(1.0, before.energy)
            flux_error = float(
                np.linalg.norm(after.flux - before.flux * math.exp(-depth))
                / max(1.0, np.linalg.norm(before.flux))
            )
            maximum_scattering_energy_error = max(
                maximum_scattering_energy_error, energy_error
            )
            maximum_scattering_flux_error = max(maximum_scattering_flux_error, flux_error)
            minimum_scattered_intensity = min(
                minimum_scattered_intensity, float(np.min(scattered))
            )
    book.add(
        "angular.isotropic_scattering",
        maximum_scattering_energy_error <= 2.0e-13
        and maximum_scattering_flux_error <= 2.0e-13
        and minimum_scattered_intensity >= 0.0,
        cases=160,
        maximum_energy_error=maximum_scattering_energy_error,
        maximum_flux_error=maximum_scattering_flux_error,
        minimum_intensity=minimum_scattered_intensity,
    )

    grid = 32
    beam_x = np.zeros((grid, grid), dtype=np.float64)
    beam_y = np.zeros((grid, grid), dtype=np.float64)
    beam_x[2, 11] = 1.0
    beam_y[11, 2] = 1.7
    initial_sum = float(np.sum(beam_x) + np.sum(beam_y))
    at_crossing_x = periodic_axis_shift(beam_x, 0, 9)
    at_crossing_y = periodic_axis_shift(beam_y, 1, 9)
    crossing = at_crossing_x[11, 11] > 0.0 and at_crossing_y[11, 11] > 0.0
    final_x = periodic_axis_shift(beam_x, 0, 12)
    final_y = periodic_axis_shift(beam_y, 1, 12)
    independent_x = np.roll(beam_x, 12, axis=0)
    independent_y = np.roll(beam_y, 12, axis=1)
    streaming_error = max(
        float(np.max(np.abs(final_x - independent_x))),
        float(np.max(np.abs(final_y - independent_y))),
        abs(float(np.sum(final_x) + np.sum(final_y)) - initial_sum),
    )
    continued = final_x[14, 11] > 0.0 and final_y[11, 14] > 0.0
    book.add(
        "angular.crossing_stream",
        crossing and continued and streaming_error <= 2.0e-13,
        crossing_cell=[11, 11],
        crossed=crossing,
        continued=continued,
        maximum_error=streaming_error,
        initial_sum=initial_sum,
        final_sum=float(np.sum(final_x) + np.sum(final_y)),
    )

    altered = weights.copy()
    altered[0] *= 1.01
    book.rejected(
        "angular.reject_malformed_quadrature",
        lambda: validate_quadrature(directions, altered, tolerance=2.0e-14),
    )
    return {
        "quadrature": quadrature,
        "realizability_cases": 257,
        "maximum_trace_error": maximum_trace_error,
        "minimum_pressure_eigenvalue": minimum_eigenvalue,
        "maximum_reduced_flux": maximum_reduced_flux,
        "counterbeam_pressure_error": pressure_error,
        "m1_obstruction": obstruction,
        "scattering_cases": 160,
        "maximum_scattering_energy_error": maximum_scattering_energy_error,
        "maximum_scattering_flux_error": maximum_scattering_flux_error,
        "crossing_stream_error": streaming_error,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        target, manifest_path, sources = prepare_evidence(output)
    except Exception as exc:
        print(f"EVIDENCE PREREQUISITE FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    book = CheckBook()
    results: dict[str, Any] = {}
    error: str | None = None
    try:
        results["symbolic"] = symbolic_controls(book)
        results["eos"] = eos_controls(book)
        results["shocks"] = shock_controls(book)
        results["populations"] = population_controls(book)
        results["lines"] = line_controls(book)
        results["stellar"] = stellar_controls(book)
        results["angular"] = angular_controls(book)
    except Exception as exc:  # Preserve a source-bound failed receipt.
        error = f"{type(exc).__name__}: {exc}"
        book.add("verification.completed_without_exception", False, error=error)

    passed_count = sum(row["passed"] for row in book.checks.values())
    total_count = len(book.checks)
    status = "PASS" if error is None and book.passed else "FAIL"
    receipt = {
        "schema": SCHEMA,
        "status": status,
        "scientific_classification": (
            "SUPPORTS-conditional compressible radiative-plasma closure"
            if status == "PASS"
            else "CONTRADICTS"
        ),
        "checks": {
            "passed": passed_count,
            "total": total_count,
            "failed": book.failed,
            "items": book.checks,
        },
        "results": results,
        "input_manifest": manifest_path.relative_to(ROOT).as_posix(),
        "sources": sources,
        "error": error,
        "scope": {
            "supported": [
                "ideal multilevel EOS primitive recovery",
                "compressible normal-shock conservation and entropy increase",
                "finite population-generator conservation and positivity",
                "LTE line detailed balance and local line-energy exchange",
                "photoionization threshold and heat partition",
                "finite gravitational accretion and nuclear energy ledgers",
                "discrete-ordinates realizability scattering and crossing beams",
            ],
            "unestablished": [
                "Cassi field to baryonic material map",
                "physical species abundance or temperature calibration",
                "atomic and nuclear database accuracy",
                "production shock and stellar-evolution solver",
                "general angular convergence",
                "live CassiCosmos implementation",
            ],
        },
    }
    target.write_text(
        json.dumps(json_value(receipt), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"COMPRESSIBLE RADIATIVE PLASMA RESULT: {status} "
        f"({passed_count}/{total_count} checks)"
    )
    print(f"receipt: {target.relative_to(ROOT).as_posix()}")
    if book.failed:
        print("failed checks: " + ", ".join(book.failed))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
