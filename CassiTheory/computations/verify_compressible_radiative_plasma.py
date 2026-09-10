#!/usr/bin/env python3
"""Verify the fixed compressible radiative-plasma closure schedule."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import math
import sys
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable

np: Any = None
sp: Any = None

SCIENTIFIC_EXPORTS = (
    "accretion_partition",
    "angular_moments",
    "axis_quadrature",
    "boltzmann_distribution",
    "control_volume_energy_residual",
    "critical_density",
    "detailed_balance_generator",
    "doppler_profile",
    "evolve_populations",
    "ideal_level_gas",
    "isotropic_scattering_step",
    "isotropic_transfer_energy_source",
    "kelvin_helmholtz_release",
    "line_coefficients",
    "line_energy_exchange",
    "normal_shock",
    "nuclear_reaction_power",
    "periodic_axis_shift",
    "photoionization_partition",
    "planck_intensity",
    "radiative_temperature_gradient",
    "recover_temperature",
    "require_control_volume_energy_balance",
    "shock_entropy_increment",
    "shock_fluxes",
    "two_level_lte_populations",
    "validate_quadrature",
    "validate_phase_matrix",
    "virial_star_energy",
)


def load_scientific_dependencies() -> dict[str, str]:
    """Load only external numerical dependencies before frozen-source execution."""
    loaded_np = importlib.import_module("numpy")
    loaded_sp = importlib.import_module("sympy")
    loaded_scipy = importlib.import_module("scipy")
    global np, sp
    np = loaded_np
    sp = loaded_sp
    return {
        "numpy": str(loaded_np.__version__),
        "sympy": str(loaded_sp.__version__),
        "scipy": str(loaded_scipy.__version__),
    }


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "cassi-compressible-radiative-plasma-verification-v2"
DEFAULT_OUTPUT = ROOT / "runs" / "compressible_radiative_plasma" / "verification.json"
KERNEL_SOURCE = Path("computations/compressible_radiative_plasma.py")
VERIFIER_SOURCE = Path("computations/verify_compressible_radiative_plasma.py")
SOURCE_PATHS = (
    Path("computations/compressible-radiative-plasma-prereg.md"),
    Path("turbulence/compressible-radiative-plasma-closure.md"),
    KERNEL_SOURCE,
    VERIFIER_SOURCE,
)
EXPECTED_CHECKS = 70
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
        expected_type = False
        try:
            operation()
        except ValueError as exc:
            expected_type = True
            error = f"ValueError: {exc}"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        self.add(name, expected_type, error=error)

    @property
    def passed(self) -> bool:
        return len(self.checks) == EXPECTED_CHECKS and all(
            row["passed"] for row in self.checks.values()
        )

    @property
    def failed(self) -> list[str]:
        return [name for name, row in self.checks.items() if not row["passed"]]


def json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if np is not None and isinstance(value, np.ndarray):
        return json_value(value.tolist())
    if np is not None and isinstance(value, np.generic):
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


def load_frozen_module(
    sources: dict[str, dict[str, Any]],
    relative: Path,
    snapshot_root: Path,
    *,
    role: str,
) -> tuple[ModuleType, dict[str, Any]]:
    """Load one module from the exact source snapshot recorded in the manifest."""
    key = relative.as_posix()
    if key not in sources:
        raise ValueError(f"manifest has no frozen source for {key}")
    recorded = sources[key]
    if recorded.get("path") != key:
        raise ValueError(f"manifest path identity mismatch for {key}")

    root = snapshot_root.resolve()
    snapshot_relative = Path(str(recorded["snapshot"]))
    expected_snapshot_path = (root / relative).resolve()
    snapshot_path = (root / snapshot_relative).resolve()
    if (
        snapshot_relative.is_absolute()
        or snapshot_path != expected_snapshot_path
        or (snapshot_path != root and root not in snapshot_path.parents)
    ):
        raise ValueError(f"snapshot path is not receipt-local for {key}: {snapshot_relative}")
    expected_hash = str(recorded["sha256"])
    expected_snapshot_hash = str(recorded["snapshot_sha256"])
    expected_bytes = int(recorded["bytes"])
    before_hash = sha256(snapshot_path)
    before_bytes = snapshot_path.stat().st_size
    if (
        before_hash != expected_hash
        or before_hash != expected_snapshot_hash
        or before_bytes != expected_bytes
    ):
        raise RuntimeError(f"frozen source mismatch before loading {key}")

    token = hashlib.sha256(
        f"{role}\0{snapshot_path}".encode("utf-8")
    ).hexdigest()[:16]
    module_name = f"_cassi_frozen_{role}_{token}"
    specification = importlib.util.spec_from_file_location(module_name, snapshot_path)
    if specification is None or specification.loader is None:
        raise ImportError(f"cannot construct a module specification for {key}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    try:
        specification.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise

    module_file = Path(str(getattr(module, "__file__", ""))).resolve()
    after_hash = sha256(snapshot_path)
    after_bytes = snapshot_path.stat().st_size
    matches = (
        module_file == snapshot_path
        and before_hash == after_hash
        and after_hash == expected_hash
        and after_hash == expected_snapshot_hash
        and after_bytes == expected_bytes
    )
    if not matches:
        sys.modules.pop(module_name, None)
        raise RuntimeError(f"frozen source mismatch after loading {key}")
    return module, {
        "role": role,
        "source": key,
        "snapshot": snapshot_path.relative_to(root).as_posix(),
        "module_name": module_name,
        "module_file": module_file.relative_to(root).as_posix(),
        "snapshot_root": root.relative_to(ROOT).as_posix(),
        "before_sha256": before_hash,
        "after_sha256": after_hash,
        "recorded_sha256": expected_hash,
        "bytes": after_bytes,
        "recorded_bytes": expected_bytes,
        "matches": matches,
    }


def bind_frozen_scientific_modules(
    sources: dict[str, dict[str, Any]],
    snapshot_root: Path,
) -> tuple[ModuleType, dict[str, Any]]:
    """Bind the kernel and scientific schedule to their frozen source files."""
    if np is None or sp is None:
        raise RuntimeError("scientific dependencies must be loaded before source binding")
    frozen_kernel, kernel_binding = load_frozen_module(
        sources,
        KERNEL_SOURCE,
        snapshot_root,
        role="compressible_radiative_plasma_kernel",
    )
    frozen_verifier, verifier_binding = load_frozen_module(
        sources,
        VERIFIER_SOURCE,
        snapshot_root,
        role="compressible_radiative_plasma_verifier",
    )
    frozen_verifier.np = np
    frozen_verifier.sp = sp
    for name in frozen_verifier.SCIENTIFIC_EXPORTS:
        if not hasattr(frozen_kernel, name):
            raise ImportError(f"frozen kernel has no export {name!r}")
        setattr(frozen_verifier, name, getattr(frozen_kernel, name))
    bindings = {
        "passed": True,
        "error": None,
        "modules": {
            "kernel": kernel_binding,
            "verifier": verifier_binding,
        },
    }
    return frozen_verifier, bindings


def evidence_paths(output: Path) -> tuple[Path, Path, Path]:
    target = output.resolve()
    if ROOT != target and ROOT not in target.parents:
        raise ValueError("output must remain inside the CassiTheory root")
    manifest_path = target.with_name("input_manifest.json")
    snapshot_root = target.parent / "source_snapshots"
    manifest_staging = manifest_path.with_name(manifest_path.name + ".incomplete")
    snapshot_staging = snapshot_root.with_name(snapshot_root.name + ".incomplete")
    for path in (
        target,
        manifest_path,
        snapshot_root,
        manifest_staging,
        snapshot_staging,
    ):
        if path.exists():
            raise FileExistsError(f"refusing existing evidence path: {path}")
    return target, manifest_path, snapshot_root


def prepare_evidence(
    output: Path,
    source_paths: Iterable[Path] = SOURCE_PATHS,
) -> tuple[Path, Path, Path, dict[str, dict[str, Any]]]:
    target, manifest_path, snapshot_root = evidence_paths(output)
    payloads = {relative: (ROOT / relative).read_bytes() for relative in source_paths}
    manifest_staging = manifest_path.with_name(manifest_path.name + ".incomplete")
    snapshot_staging = snapshot_root.with_name(snapshot_root.name + ".incomplete")
    # All reserved evidence paths were verified absent by evidence_paths().

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        snapshot_staging.mkdir()
        manifest: dict[str, dict[str, Any]] = {}
        for relative, payload in payloads.items():
            staged_destination = snapshot_staging / relative
            staged_destination.parent.mkdir(parents=True, exist_ok=True)
            staged_destination.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            manifest[relative.as_posix()] = {
                "path": relative.as_posix(),
                "snapshot": relative.as_posix(),
                "bytes": len(payload),
                "sha256": digest,
                "snapshot_sha256": digest,
            }
        snapshot_staging.rename(snapshot_root)
        manifest_payload = (
            json.dumps(
                {
                    "schema": SCHEMA,
                    "snapshot_root": snapshot_root.relative_to(ROOT).as_posix(),
                    "sources": manifest,
                },
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        )
        with manifest_staging.open("x", encoding="utf-8") as stream:
            stream.write(manifest_payload)
        manifest_staging.replace(manifest_path)
        return target, manifest_path, snapshot_root, manifest
    except Exception:
        if manifest_staging.exists():
            manifest_staging.unlink()
        if manifest_path.exists():
            manifest_path.unlink()
        if snapshot_staging.exists():
            shutil.rmtree(snapshot_staging)
        if snapshot_root.exists():
            shutil.rmtree(snapshot_root)
        raise


def verify_source_integrity(
    sources: dict[str, dict[str, Any]],
    snapshot_root: Path,
) -> dict[str, Any]:
    root = snapshot_root.resolve()
    rows: dict[str, Any] = {}
    passed = True
    for relative, recorded in sources.items():
        try:
            current_path = ROOT / relative
            snapshot_relative = Path(str(recorded["snapshot"]))
            expected_snapshot_path = (root / relative).resolve()
            snapshot_path = (root / snapshot_relative).resolve()
            root_bound = snapshot_path == root or root in snapshot_path.parents
            location_matches = (
                not snapshot_relative.is_absolute()
                and snapshot_path == expected_snapshot_path
                and root_bound
            )
            current = sha256(current_path)
            snapshot = sha256(snapshot_path)
            current_bytes = current_path.stat().st_size
            snapshot_bytes = snapshot_path.stat().st_size
            matches = (
                location_matches
                and current == recorded["sha256"]
                and snapshot == recorded["snapshot_sha256"]
                and current == snapshot
                and current_bytes == recorded["bytes"]
                and snapshot_bytes == recorded["bytes"]
            )
            error = None
        except Exception as exc:
            current = None
            snapshot = None
            current_bytes = None
            snapshot_bytes = None
            root_bound = False
            location_matches = False
            matches = False
            error = f"{type(exc).__name__}: {exc}"
        rows[relative] = {
            "current_sha256": current,
            "recorded_sha256": recorded["sha256"],
            "snapshot_sha256": snapshot,
            "current_bytes": current_bytes,
            "snapshot_bytes": snapshot_bytes,
            "recorded_bytes": recorded["bytes"],
            "snapshot_root": root.relative_to(ROOT).as_posix(),
            "recorded_snapshot": recorded.get("snapshot"),
            "root_bound": root_bound,
            "location_matches": location_matches,
            "matches": matches,
            "error": error,
        }
        passed = passed and matches
    return {"passed": passed, "rows": rows}


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


def require_normalized_match(
    actual: float,
    expected: float,
    *,
    tolerance: float,
) -> None:
    left = float(actual)
    right = float(expected)
    limit = float(tolerance)
    if (
        not math.isfinite(left)
        or not math.isfinite(right)
        or not math.isfinite(limit)
        or limit < 0.0
    ):
        raise ValueError("comparison values and tolerance must be finite and admissible")
    residual = abs(left - right) / max(1.0, abs(right))
    if not math.isfinite(residual) or residual > limit:
        raise ValueError(
            f"normalized residual {residual:.17g} exceeds tolerance {limit:.17g}"
        )


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
    book.rejected(
        "shock.reject_missing_enthalpy",
        lambda: require_normalized_match(
            bad_energy_2,
            bad_energy_1,
            tolerance=1.0e-2,
        ),
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

    gross_contributions = np.asarray([0.3, 0.2, 0.4, 0.1])
    photon_luminosity = 0.73
    retained_heat = 0.19
    neutrino_loss = 0.08
    mechanical_outflow = 0.0
    gross_nuclear = float(gross_contributions[2])
    matter_energy_inflow = float(gross_contributions[3])
    gross_stored_release = float(gross_contributions[0] + gross_contributions[1])
    stored_energy_rate = -gross_stored_release + retained_heat
    available = float(np.sum(gross_contributions))
    accounted = (
        photon_luminosity
        + retained_heat
        + neutrino_loss
        + mechanical_outflow
    )
    ledger_error = abs(
        control_volume_energy_residual(
            photon_luminosity=photon_luminosity,
            neutrino_luminosity=neutrino_loss,
            mechanical_outflow=mechanical_outflow,
            external_power=0.0,
            gross_nuclear_power=gross_nuclear,
            matter_energy_inflow=matter_energy_inflow,
            stored_energy_rate=stored_energy_rate,
        )
    )
    net_nuclear_misdefinition = gross_nuclear - neutrino_loss
    double_count_residual = abs(
        control_volume_energy_residual(
            photon_luminosity=photon_luminosity,
            neutrino_luminosity=neutrino_loss,
            mechanical_outflow=mechanical_outflow,
            external_power=0.0,
            gross_nuclear_power=net_nuclear_misdefinition,
            matter_energy_inflow=matter_energy_inflow,
            stored_energy_rate=stored_energy_rate,
        )
    )
    book.add(
        "stellar.complete_energy_ledger",
        ledger_error <= 2.0e-14
        and abs(available - accounted) <= 2.0e-14
        and double_count_residual > 1.0e-2,
        available=available,
        photon_luminosity=photon_luminosity,
        retained_heat=retained_heat,
        neutrino_loss=neutrino_loss,
        mechanical_outflow=mechanical_outflow,
        stored_energy_rate=stored_energy_rate,
        accounted=accounted,
        gross_nuclear_source=gross_nuclear,
        residual=ledger_error,
        net_nuclear_double_count_residual=double_count_residual,
        strict_double_count_lower_bound=1.0e-2,
    )
    book.rejected(
        "stellar.reject_overdrawn_luminosity",
        lambda: require_control_volume_energy_balance(
            photon_luminosity=1.01,
            neutrino_luminosity=neutrino_loss,
            mechanical_outflow=mechanical_outflow,
            external_power=0.0,
            gross_nuclear_power=gross_nuclear,
            matter_energy_inflow=matter_energy_inflow,
            stored_energy_rate=stored_energy_rate,
            tolerance=2.0e-14,
        ),
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
    isotropic_phase = np.full(
        (weights.size, weights.size), 1.0 / (4.0 * math.pi), dtype=np.float64
    )
    phase_error = validate_phase_matrix(
        isotropic_phase, weights, tolerance=2.0e-14
    )
    book.add(
        "angular.axis_quadrature",
        max(quadrature.values()) <= 2.0e-14 and phase_error <= 2.0e-14,
        **quadrature,
        phase_matrix_column_error=phase_error,
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
    negative_weight = weights.copy()
    negative_weight[0] = -negative_weight[0]
    nonunit_directions = directions.copy()
    nonunit_directions[0] *= 0.9
    nonfinite_intensity = np.ones(weights.size)
    nonfinite_intensity[0] = math.nan
    nonfinite_scattering_weight = weights.copy()
    nonfinite_scattering_weight[0] = math.nan
    negative_phase = isotropic_phase.copy()
    negative_phase[0, 0] = -negative_phase[0, 0]
    nonnormalized_phase = isotropic_phase.copy()
    nonnormalized_phase[0, 0] *= 2.0
    rejection_cases: dict[str, Callable[[], Any]] = {
        "altered_quadrature": lambda: validate_quadrature(
            directions, altered, tolerance=2.0e-14
        ),
        "negative_moment_weight": lambda: angular_moments(
            np.ones(weights.size), directions, negative_weight
        ),
        "nonunit_moment_direction": lambda: angular_moments(
            np.ones(weights.size), nonunit_directions, weights
        ),
        "nonfinite_moment_intensity": lambda: angular_moments(
            nonfinite_intensity, directions, weights
        ),
        "nonfinite_scattering_weight": lambda: isotropic_scattering_step(
            np.ones(weights.size), nonfinite_scattering_weight, 0.1
        ),
        "negative_phase_entry": lambda: validate_phase_matrix(
            negative_phase, weights, tolerance=2.0e-14
        ),
        "nonnormalized_phase_column": lambda: validate_phase_matrix(
            nonnormalized_phase, weights, tolerance=2.0e-14
        ),
    }
    rejection_outcomes: dict[str, str] = {}
    rejections_passed = True
    for name, operation in rejection_cases.items():
        try:
            operation()
            rejection_outcomes[name] = "NO ERROR"
            rejections_passed = False
        except ValueError as exc:
            rejection_outcomes[name] = f"ValueError: {exc}"
        except Exception as exc:
            rejection_outcomes[name] = f"{type(exc).__name__}: {exc}"
            rejections_passed = False
    book.add(
        "angular.reject_malformed_quadrature",
        rejections_passed,
        outcomes=rejection_outcomes,
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
        "phase_matrix_column_error": phase_error,
        "angular_rejection_outcomes": rejection_outcomes,
    }


def execute_scientific_controls(book: CheckBook) -> dict[str, Any]:
    """Execute the complete fixed schedule in this verifier module."""
    return {
        "symbolic": symbolic_controls(book),
        "eos": eos_controls(book),
        "shocks": shock_controls(book),
        "populations": population_controls(book),
        "lines": line_controls(book),
        "stellar": stellar_controls(book),
        "angular": angular_controls(book),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def write_json_receipt(target: Path, receipt: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(json_value(receipt), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_inconclusive_receipt(
    target: Path,
    *,
    stage: str,
    error: Exception,
    manifest_path: Path | None = None,
    snapshot_root: Path | None = None,
    sources: dict[str, dict[str, Any]] | None = None,
) -> int:
    message = f"{type(error).__name__}: {error}"
    receipt = {
        "schema": SCHEMA,
        "status": "INCONCLUSIVE",
        "scientific_classification": "INCONCLUSIVE",
        "checks": {
            "passed": 0,
            "total": 0,
            "expected_total": EXPECTED_CHECKS,
            "failed": [],
            "items": {},
        },
        "results": {},
        "snapshot_root": (
            snapshot_root.relative_to(ROOT).as_posix()
            if snapshot_root is not None and snapshot_root.exists()
            else None
        ),
        "input_manifest": (
            manifest_path.relative_to(ROOT).as_posix()
            if manifest_path is not None
            else None
        ),
        "sources": sources or {},
        "error": message,
        "prerequisite_stage": stage,
    }
    write_json_receipt(target, receipt)
    print(f"COMPRESSIBLE RADIATIVE PLASMA RESULT: INCONCLUSIVE ({stage})")
    print(f"receipt: {target.relative_to(ROOT).as_posix()}")
    print(f"prerequisite error: {message}", file=sys.stderr)
    return 2

def run_verification(
    output: Path,
    *,
    source_paths: Iterable[Path] = SOURCE_PATHS,
    dependency_loader: Callable[[], dict[str, str]] = load_scientific_dependencies,
) -> int:
    required_check_count = EXPECTED_CHECKS
    try:
        target, _, snapshot_root = evidence_paths(output)
    except Exception as exc:
        print(f"EVIDENCE PATH FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    try:
        target, manifest_path, snapshot_root, sources = prepare_evidence(
            output,
            source_paths,
        )
    except Exception as exc:
        return write_inconclusive_receipt(
            target,
            stage="source-read",
            error=exc,
            snapshot_root=snapshot_root,
        )

    source_integrity: dict[str, Any] = {
        "after_snapshot": verify_source_integrity(sources, snapshot_root)
    }
    dependencies: dict[str, str] = {}
    execution_binding: dict[str, Any] = {
        "passed": False,
        "modules": {},
        "error": None,
    }
    execution_module: ModuleType | None = None
    if source_integrity["after_snapshot"]["passed"]:
        try:
            dependencies = dependency_loader()
        except Exception as exc:
            return write_inconclusive_receipt(
                target,
                stage="scientific-dependencies",
                error=exc,
                manifest_path=manifest_path,
                snapshot_root=snapshot_root,
                sources=sources,
            )
        source_integrity["before_controls"] = verify_source_integrity(
            sources,
            snapshot_root,
        )
        if source_integrity["before_controls"]["passed"]:
            try:
                execution_module, execution_binding = bind_frozen_scientific_modules(
                    sources,
                    snapshot_root,
                )
            except Exception as exc:
                execution_binding["error"] = f"{type(exc).__name__}: {exc}"

    book = execution_module.CheckBook() if execution_module is not None else CheckBook()
    results: dict[str, Any] = {}
    error: str | None = None
    if not source_integrity["after_snapshot"]["passed"]:
        error = "source integrity mismatch immediately after snapshot publication"
    elif not source_integrity["before_controls"]["passed"]:
        error = "source integrity mismatch before scientific controls"
    elif execution_module is None:
        error = "execution source binding failed: " + str(execution_binding["error"])
    else:
        try:
            results = execution_module.execute_scientific_controls(book)
        except Exception as exc:  # Preserve a source-bound failed receipt.
            error = f"{type(exc).__name__}: {exc}"
            book.add("verification.completed_without_exception", False, error=error)

    source_integrity["after_controls"] = verify_source_integrity(
        sources,
        snapshot_root,
    )
    integrity_passed = all(
        phase["passed"] for phase in source_integrity.values()
    )
    binding_passed = bool(execution_binding["passed"])
    if not integrity_passed and error is None:
        error = "source integrity mismatch after scientific controls"

    passed_count = sum(bool(row["passed"]) for row in book.checks.values())
    failed_checks = [
        name for name, row in book.checks.items() if not bool(row["passed"])
    ]
    total_count = len(book.checks)
    expected_total = required_check_count
    module_expected_total: int | None = None
    module_expected_error: str | None = None
    try:
        declared_total = getattr(execution_module, "EXPECTED_CHECKS", -1)
    except Exception as exc:
        module_expected_error = f"{type(exc).__name__}: {exc}"
    else:
        if type(declared_total) is int:
            module_expected_total = declared_total
        else:
            module_expected_error = (
                "TypeError: EXPECTED_CHECKS must be an integer, "
                f"got {type(declared_total).__name__}"
            )
    declaration_matches_expected = module_expected_total == expected_total
    count_matches_expected = (
        total_count == expected_total and declaration_matches_expected
    )
    if not count_matches_expected and error is None:
        declaration_text = (
            str(module_expected_total)
            if module_expected_error is None
            else f"invalid [{module_expected_error}]"
        )
        error = (
            "fixed scientific check count mismatch: "
            f"observed={total_count}, required={expected_total}, "
            f"frozen_declaration={declaration_text}"
        )
    status = (
        "PASS"
        if (
            error is None
            and not failed_checks
            and integrity_passed
            and binding_passed
            and count_matches_expected
        )
        else "FAIL"
    )
    if status == "PASS":
        scientific_classification = (
            "SUPPORTS-conditional compressible radiative-plasma closure"
        )
    elif not integrity_passed or not binding_passed or not count_matches_expected:
        scientific_classification = "INCONCLUSIVE"
    else:
        scientific_classification = "CONTRADICTS"
    receipt = {
        "schema": SCHEMA,
        "status": status,
        "scientific_classification": scientific_classification,
        "checks": {
            "passed": passed_count,
            "total": total_count,
            "expected_total": expected_total,
            "module_expected_total": module_expected_total,
            "module_expected_error": module_expected_error,
            "declaration_matches_expected": declaration_matches_expected,
            "count_matches_expected": count_matches_expected,
            "failed": failed_checks,
            "items": book.checks,
        },
        "results": results,
        "snapshot_root": snapshot_root.relative_to(ROOT).as_posix(),
        "input_manifest": manifest_path.relative_to(ROOT).as_posix(),
        "sources": sources,
        "source_integrity": source_integrity,
        "execution_binding": execution_binding,
        "dependencies": dependencies,
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
    write_json_receipt(target, receipt)
    print(
        f"COMPRESSIBLE RADIATIVE PLASMA RESULT: {status} "
        f"({passed_count}/{total_count} checks)"
    )
    print(f"receipt: {target.relative_to(ROOT).as_posix()}")
    if failed_checks:
        print("failed checks: " + ", ".join(failed_checks))
    if error is not None:
        print(f"verification error: {error}", file=sys.stderr)
    return 0 if status == "PASS" else 1


def main() -> int:
    args = parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    return run_verification(output)


if __name__ == "__main__":
    raise SystemExit(main())
