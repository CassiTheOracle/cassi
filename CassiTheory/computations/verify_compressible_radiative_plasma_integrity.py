#!/usr/bin/env python3
"""Run the fixed integrity qualification for the compressible plasma closure."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import sys
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "cassi-compressible-radiative-plasma-integrity-v1"
DEFAULT_OUTPUT = (
    ROOT / "runs" / "compressible_radiative_plasma_integrity" / "verification.json"
)
SOURCE_PATHS = (
    Path("computations/compressible-radiative-plasma-integrity-prereg.md"),
    Path("computations/compressible-radiative-plasma-prereg.md"),
    Path("turbulence/compressible-radiative-plasma-closure.md"),
    Path("computations/compressible_radiative_plasma.py"),
    Path("computations/verify_compressible_radiative_plasma.py"),
    Path("computations/verify_compressible_radiative_plasma_integrity.py"),
)
EXPECTED_CHECKS = 36
TOL = 2.0e-14

np: Any = None
sp: Any = None
integrate: Any = None
kernel: Any = None
base_verifier: Any = None


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

    def close(
        self,
        name: str,
        actual: Any,
        expected: Any,
        *,
        tolerance: float = TOL,
    ) -> None:
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


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


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


def prepare_evidence(output: Path) -> tuple[Path, Path, dict[str, dict[str, Any]]]:
    target, manifest_path, snapshot_root = evidence_paths(output)
    payloads = {relative: (ROOT / relative).read_bytes() for relative in SOURCE_PATHS}
    manifest_staging = manifest_path.with_name(manifest_path.name + ".incomplete")
    snapshot_staging = snapshot_root.with_name(snapshot_root.name + ".incomplete")
    # All reserved evidence paths were verified absent by evidence_paths().

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        snapshot_staging.mkdir()
        sources: dict[str, dict[str, Any]] = {}
        for relative, payload in payloads.items():
            staged_destination = snapshot_staging / relative
            staged_destination.parent.mkdir(parents=True, exist_ok=True)
            staged_destination.write_bytes(payload)
            final_destination = snapshot_root / relative
            digest = sha256_bytes(payload)
            sources[relative.as_posix()] = {
                "path": relative.as_posix(),
                "snapshot": final_destination.relative_to(ROOT).as_posix(),
                "bytes": len(payload),
                "sha256": digest,
                "snapshot_sha256": digest,
            }
        snapshot_staging.rename(snapshot_root)
        manifest_payload = (
            json.dumps(
                {"schema": SCHEMA, "sources": sources},
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        )
        with manifest_staging.open("x", encoding="utf-8") as stream:
            stream.write(manifest_payload)
        manifest_staging.replace(manifest_path)
        return target, manifest_path, sources
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


def write_receipt(target: Path, receipt: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(json_value(receipt), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_inconclusive(
    target: Path,
    *,
    stage: str,
    error: Exception,
    manifest_path: Path | None = None,
    sources: dict[str, dict[str, Any]] | None = None,
) -> int:
    message = f"{type(error).__name__}: {error}"
    write_receipt(
        target,
        {
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
            "input_manifest": (
                manifest_path.relative_to(ROOT).as_posix()
                if manifest_path is not None
                else None
            ),
            "sources": sources or {},
            "error": message,
            "prerequisite_stage": stage,
        },
    )
    print(f"COMPRESSIBLE PLASMA INTEGRITY RESULT: INCONCLUSIVE ({stage})")
    print(f"receipt: {target.relative_to(ROOT).as_posix()}")
    print(f"prerequisite error: {message}", file=sys.stderr)
    return 2


def load_dependencies() -> dict[str, str]:
    loaded_np = importlib.import_module("numpy")
    loaded_sp = importlib.import_module("sympy")
    loaded_scipy = importlib.import_module("scipy")
    loaded_integrate = importlib.import_module("scipy.integrate")
    loaded_kernel = importlib.import_module("compressible_radiative_plasma")
    loaded_base = importlib.import_module("verify_compressible_radiative_plasma")
    global np, sp, integrate, kernel, base_verifier
    np = loaded_np
    sp = loaded_sp
    integrate = loaded_integrate
    kernel = loaded_kernel
    base_verifier = loaded_base
    return {
        "numpy": str(loaded_np.__version__),
        "sympy": str(loaded_sp.__version__),
        "scipy": str(loaded_scipy.__version__),
    }


def state_and_thermo_controls(book: CheckBook) -> dict[str, Any]:
    density = 2.5
    velocity = np.asarray([0.2, -0.4, 0.1])
    internal = 3.2
    fractions = np.asarray([0.7, 0.2, 0.1])
    levels = np.asarray([0.7, 1.05, 0.125, 0.125])
    level_species = np.asarray([0, 0, 1, 2])
    baryon_numbers = np.asarray([1.0, 1.0, 4.0, 2.0])
    state = kernel.conservative_material_state(
        density,
        velocity,
        internal,
        fractions,
        levels,
        level_species,
        baryon_numbers,
    )
    actual = np.concatenate(
        (
            np.asarray([state.density]),
            state.momentum,
            np.asarray([state.total_energy]),
            state.species_densities,
            state.level_populations,
        )
    )
    expected = np.concatenate(
        (
            np.asarray([density]),
            density * velocity,
            np.asarray([density * (internal + 0.5 * float(np.dot(velocity, velocity)))]),
            density * fractions,
            levels,
        )
    )
    book.close("state.conservative_components", actual, expected)
    species_from_levels = np.bincount(
        level_species,
        weights=baryon_numbers * levels,
        minlength=fractions.size,
    )
    book.close(
        "state.species_level_mass_identity",
        state.species_densities,
        species_from_levels,
    )
    recovered = kernel.recover_internal_energy_density(state)
    book.close("state.internal_energy_recovery", recovered, density * internal)
    book.rejected(
        "state.reject_mass_fraction_sum",
        lambda: kernel.conservative_material_state(
            density,
            velocity,
            internal,
            np.asarray([0.7, 0.2, 0.2]),
            levels,
            level_species,
            baryon_numbers,
        ),
    )
    book.rejected(
        "state.reject_nonfinite_level_population",
        lambda: kernel.conservative_material_state(
            density,
            velocity,
            internal,
            fractions,
            np.asarray([0.7, math.nan, 0.125, 0.125]),
            level_species,
            baryon_numbers,
        ),
    )
    book.rejected(
        "state.reject_species_level_mass_mismatch",
        lambda: kernel.conservative_material_state(
            density,
            velocity,
            internal,
            fractions,
            levels + np.asarray([0.01, 0.0, 0.0, 0.0]),
            level_species,
            baryon_numbers,
        ),
    )

    def collect_value_errors(
        cases: dict[str, Callable[[], Any]],
    ) -> tuple[bool, dict[str, str]]:
        outcomes: dict[str, str] = {}
        passed = True
        for name, operation in cases.items():
            try:
                operation()
                outcomes[name] = "NO ERROR"
                passed = False
            except ValueError as exc:
                outcomes[name] = f"ValueError: {exc}"
            except Exception as exc:
                outcomes[name] = f"{type(exc).__name__}: {exc}"
                passed = False
        return passed, outcomes

    mapping_passed, mapping_outcomes = collect_value_errors(
        {
            "nonintegral": lambda: kernel.conservative_material_state(
                density,
                velocity,
                internal,
                fractions,
                levels,
                np.asarray([0.0, 0.5, 1.0, 2.0]),
                baryon_numbers,
            ),
            "out_of_range": lambda: kernel.conservative_material_state(
                density,
                velocity,
                internal,
                fractions,
                levels,
                np.asarray([0, 3, 1, 2]),
                baryon_numbers,
            ),
            "missing_positive_species": lambda: kernel.conservative_material_state(
                density,
                velocity,
                internal,
                fractions,
                levels,
                np.asarray([0, 0, 1, 1]),
                baryon_numbers,
            ),
        }
    )
    book.add(
        "state.reject_malformed_level_species",
        mapping_passed,
        outcomes=mapping_outcomes,
    )

    zero_species_state = kernel.conservative_material_state(
        density,
        velocity,
        internal,
        np.asarray([0.8, 0.2, 0.0]),
        np.asarray([0.8, 1.2, 0.125]),
        np.asarray([0, 0, 1]),
        np.asarray([1.0, 1.0, 4.0]),
    )
    book.close(
        "state.allow_unrepresented_zero_density_species",
        zero_species_state.species_densities,
        np.asarray([2.0, 0.5, 0.0]),
    )

    valid_direct = {
        "density": density,
        "momentum": density * velocity,
        "total_energy": density
        * (internal + 0.5 * float(np.dot(velocity, velocity))),
        "species_densities": density * fractions,
        "level_populations": levels,
        "level_species": level_species,
        "level_baryon_numbers": baryon_numbers,
    }
    constructor_passed, constructor_outcomes = collect_value_errors(
        {
            "zero_density": lambda: kernel.ConservativeMaterialState(
                **(valid_direct | {"density": 0.0})
            ),
            "malformed_momentum": lambda: kernel.ConservativeMaterialState(
                **(valid_direct | {"momentum": np.asarray([[0.0, 0.0]])})
            ),
            "nonfinite_species": lambda: kernel.ConservativeMaterialState(
                **(
                    valid_direct
                    | {"species_densities": np.asarray([1.75, math.nan, 0.25])}
                )
            ),
            "wrong_species_sum": lambda: kernel.ConservativeMaterialState(
                **(
                    valid_direct
                    | {"species_densities": np.asarray([1.75, 0.5, 0.2])}
                )
            ),
            "negative_level": lambda: kernel.ConservativeMaterialState(
                **(
                    valid_direct
                    | {"level_populations": np.asarray([0.7, -1.05, 0.125, 0.125])}
                )
            ),
            "inconsistent_species_baryon_number": lambda: kernel.ConservativeMaterialState(
                **(
                    valid_direct
                    | {
                        "level_baryon_numbers": np.asarray(
                            [1.0, 2.0, 4.0, 2.0]
                        )
                    }
                )
            ),
        }
    )
    book.add(
        "state.public_constructor_rejects_invalid_components",
        constructor_passed,
        outcomes=constructor_outcomes,
    )

    raw_momentum = np.asarray(density * velocity)
    raw_species = np.asarray(density * fractions)
    raw_levels = np.array(levels, copy=True)
    raw_owners = np.array(level_species, copy=True)
    raw_baryons = np.array(baryon_numbers, copy=True)
    direct_state = kernel.ConservativeMaterialState(
        density=density,
        momentum=raw_momentum,
        total_energy=valid_direct["total_energy"],
        species_densities=raw_species,
        level_populations=raw_levels,
        level_species=raw_owners,
        level_baryon_numbers=raw_baryons,
    )
    preserved = {
        name: np.array(getattr(direct_state, name), copy=True)
        for name in (
            "momentum",
            "species_densities",
            "level_populations",
            "level_species",
            "level_baryon_numbers",
        )
    }
    raw_momentum[:] = 99.0
    raw_species[:] = 99.0
    raw_levels[:] = 99.0
    raw_owners[:] = 0
    raw_baryons[:] = 99.0
    mutation_errors: dict[str, str] = {}
    for name in preserved:
        try:
            getattr(direct_state, name)[0] = 0
            mutation_errors[name] = "NO ERROR"
        except ValueError as exc:
            mutation_errors[name] = f"ValueError: {exc}"
    copies_preserved = all(
        np.array_equal(getattr(direct_state, name), values)
        for name, values in preserved.items()
    )
    writes_blocked = all(value != "NO ERROR" for value in mutation_errors.values())
    book.add(
        "state.public_constructor_defensive_arrays",
        copies_preserved and writes_blocked,
        copies_preserved=copies_preserved,
        writes_blocked=writes_blocked,
        mutation_errors=mutation_errors,
    )

    book.rejected(
        "state.reject_nonpositive_internal_energy",
        lambda: kernel.ConservativeMaterialState(
            **(
                valid_direct
                | {
                    "momentum": np.asarray([10.0, 0.0, 0.0]),
                    "total_energy": 1.0,
                }
            )
        ),
    )

    rho, entropy = sp.symbols("rho entropy", positive=True, real=True)
    c_v = sp.Rational(3, 2)
    gas_constant = sp.Integer(1)
    temperature = sp.exp((entropy + gas_constant * sp.log(rho)) / c_v)
    specific_energy = c_v * temperature
    pressure = gas_constant * rho * temperature
    temperature_identity = sp.simplify(sp.diff(specific_energy, entropy) - temperature)
    pressure_identity = sp.simplify(rho**2 * sp.diff(specific_energy, rho) - pressure)
    sound_speed_identity = sp.simplify(
        sp.diff(pressure, rho) - sp.Rational(5, 3) * pressure / rho
    )
    book.add(
        "thermo.ideal_gas_fundamental_relation",
        temperature_identity == 0
        and pressure_identity == 0
        and sound_speed_identity == 0,
        temperature_identity=str(temperature_identity),
        pressure_identity=str(pressure_identity),
        frozen_sound_speed_identity=str(sound_speed_identity),
    )
    return {
        "packed_state": actual,
        "expected_state": expected,
        "species_from_levels": species_from_levels,
        "recovered_internal_energy_density": recovered,
        "mapping_rejections": mapping_outcomes,
        "constructor_rejections": constructor_outcomes,
        "defensive_array_mutations": mutation_errors,
    }


def shock_control(book: CheckBook) -> dict[str, Any]:
    residual = abs(1.2 - 1.0)
    book.rejected(
        "shock.reject_missing_enthalpy",
        lambda: base_verifier.require_normalized_match(
            1.2,
            1.0,
            tolerance=0.01,
        ),
    )
    cases = {
        "nonfinite_actual": (math.inf, 1.0, 0.01),
        "nonfinite_expected": (1.0, math.inf, 0.01),
        "nonfinite_tolerance": (1.0, 1.0, math.nan),
        "negative_tolerance": (1.0, 1.0, -0.01),
    }
    outcomes: dict[str, str] = {}
    passed = True
    for name, (actual, expected, tolerance) in cases.items():
        try:
            base_verifier.require_normalized_match(
                actual,
                expected,
                tolerance=tolerance,
            )
            outcomes[name] = "NO ERROR"
            passed = False
        except ValueError as exc:
            outcomes[name] = f"ValueError: {exc}"
        except Exception as exc:
            outcomes[name] = f"{type(exc).__name__}: {exc}"
            passed = False
    book.add(
        "shock.reject_nonfinite_normalized_comparison",
        passed,
        outcomes=outcomes,
    )
    return {
        "normalized_residual": residual,
        "tolerance": 0.01,
        "comparison_rejections": outcomes,
    }


def line_controls(book: CheckBook) -> dict[str, Any]:
    valid = (1.4, 0.3, 2.0, 6.0, 2.0, 0.7, 0.9)
    profile_rows: list[dict[str, float]] = []
    profile_passed = True
    profile_tolerance = 2.0e-12
    for center, width in ((0.25, 1.0), (1.0, 0.7), (3.0, 1.2)):
        integral, quadrature_error = integrate.quad(
            lambda frequency: float(
                kernel.doppler_profile([frequency], center, width)[0]
            ),
            0.0,
            math.inf,
            epsabs=1.0e-13,
            epsrel=1.0e-13,
            limit=200,
        )
        samples = kernel.doppler_profile(
            np.asarray([0.0, center, center + 4.0 * width]),
            center,
            width,
        )
        residual = abs(float(integral) - 1.0)
        admissible = bool(np.all(np.isfinite(samples)) and np.all(samples >= 0.0))
        profile_passed = (
            profile_passed
            and residual <= profile_tolerance
            and admissible
        )
        profile_rows.append(
            {
                "line_frequency": center,
                "doppler_width": width,
                "integral": float(integral),
                "normalized_error": residual,
                "quadrature_error": float(quadrature_error),
                "minimum_sample": float(np.min(samples)),
            }
        )
    book.add(
        "line.doppler_half_axis_normalization",
        profile_passed,
        tolerance=profile_tolerance,
        rows=profile_rows,
    )
    book.rejected(
        "line.reject_negative_lower_population",
        lambda: kernel.line_coefficients(-1.0, *valid[1:]),
    )
    book.rejected(
        "line.reject_nonfinite_upper_population",
        lambda: kernel.line_coefficients(valid[0], math.inf, *valid[2:]),
    )
    book.rejected(
        "line.reject_zero_frequency",
        lambda: kernel.line_coefficients(*valid[:4], 0.0, *valid[5:]),
    )
    book.rejected(
        "line.reject_zero_B_ul",
        lambda: kernel.line_coefficients(*valid[:5], 0.0, valid[6]),
    )
    book.rejected(
        "line.reject_zero_planck",
        lambda: kernel.line_coefficients(*valid, planck=0.0),
    )

    _, _, a_ul, b_lu = kernel.line_coefficients(*valid)
    book.rejected(
        "line.reject_negative_profile",
        lambda: kernel.line_coefficients(*valid[:6], -0.1),
    )
    zero_profile = kernel.line_coefficients(*valid[:6], 0.0)
    book.close(
        "line.allow_zero_profile",
        np.asarray(zero_profile[:2]),
        np.asarray([0.0, 0.0]),
    )
    exchange_args = (valid[0], valid[1], 0.8, valid[4], a_ul, valid[5], b_lu)
    book.rejected(
        "exchange.reject_negative_A_ul",
        lambda: kernel.line_energy_exchange(
            *exchange_args[:4], -1.0, *exchange_args[5:]
        ),
    )
    book.rejected(
        "exchange.reject_zero_B_ul",
        lambda: kernel.line_energy_exchange(
            *exchange_args[:5], 0.0, exchange_args[6]
        ),
    )
    book.rejected(
        "exchange.reject_nonfinite_B_lu",
        lambda: kernel.line_energy_exchange(*exchange_args[:6], math.nan),
    )
    book.rejected(
        "exchange.reject_negative_frequency",
        lambda: kernel.line_energy_exchange(
            *exchange_args[:3], -2.0, *exchange_args[4:]
        ),
    )
    transition_rate, material, photon = kernel.line_energy_exchange(*exchange_args)
    book.close("exchange.valid_energy_cancellation", material + photon, 0.0)
    return {
        "transition_rate": transition_rate,
        "material_increment": material,
        "photon_increment": photon,
        "A_ul": a_ul,
        "B_lu": b_lu,
        "doppler_profiles": profile_rows,
    }


def transfer_controls(book: CheckBook) -> dict[str, Any]:
    radiation, material = kernel.isotropic_transfer_energy_source(
        0.7,
        0.4,
        1.2,
        light_speed=3.0,
    )
    expected = 4.0 * math.pi * 0.7 - 3.0 * 0.4 * 1.2
    book.close(
        "transfer.isotropic_source_and_opposite_material",
        np.asarray([radiation, material, radiation + material]),
        np.asarray([expected, -expected, 0.0]),
    )
    planck = 0.8
    extinction = 0.4
    equilibrium_energy = 4.0 * math.pi * planck / 3.0
    equilibrium = kernel.isotropic_transfer_energy_source(
        extinction * planck,
        extinction,
        equilibrium_energy,
        light_speed=3.0,
    )
    book.close("transfer.equilibrium_zero_source", equilibrium, (0.0, 0.0))
    return {
        "radiation_source": radiation,
        "material_source": material,
        "equilibrium_source": equilibrium,
    }


def stellar_controls(book: CheckBook) -> dict[str, Any]:
    retained_heat = 0.19
    ledger = {
        "photon_luminosity": 0.73,
        "neutrino_luminosity": 0.08,
        "mechanical_outflow": 0.0,
        "external_power": 0.0,
        "gross_nuclear_power": 0.4,
        "matter_energy_inflow": 0.1,
        "stored_energy_rate": -0.5 + retained_heat,
    }
    residual = kernel.control_volume_energy_residual(**ledger)
    gross_budget = (
        ledger["photon_luminosity"]
        + ledger["neutrino_luminosity"]
        + ledger["mechanical_outflow"]
        + retained_heat
    )
    book.close(
        "ledger.gross_nuclear_balance",
        np.asarray([residual, gross_budget]),
        np.asarray([0.0, 1.0]),
    )
    net_ledger = dict(ledger)
    net_ledger["gross_nuclear_power"] = 0.32
    book.rejected(
        "ledger.reject_net_nuclear_double_count",
        lambda: kernel.require_control_volume_energy_balance(
            **net_ledger,
            tolerance=TOL,
        ),
    )
    overdraw = dict(ledger)
    overdraw.update(
        photon_luminosity=1.01,
        neutrino_luminosity=0.0,
        mechanical_outflow=0.0,
    )
    book.rejected(
        "ledger.reject_overdrawn_luminosity",
        lambda: kernel.require_control_volume_energy_balance(
            **overdraw,
            tolerance=TOL,
        ),
    )

    reaction = {
        "stoichiometry": np.asarray([-4.0, 1.0]),
        "masses": np.asarray([1.01, 4.0]),
        "baryon_numbers": np.asarray([1.0, 4.0]),
        "charges": np.asarray([1.0, 4.0]),
    }
    zero_sources, zero_power, zero_baryon, zero_charge = kernel.nuclear_reaction_power(
        **reaction,
        event_rate=0.0,
    )
    book.add(
        "nuclear.zero_rate_zero_power",
        bool(np.array_equal(zero_sources, np.zeros(2)))
        and zero_power == 0.0
        and zero_baryon == 0.0
        and zero_charge == 0.0,
        sources=zero_sources,
        power=zero_power,
        baryon_residual=zero_baryon,
        charge_residual=zero_charge,
    )
    positive_rows: list[dict[str, float]] = []
    positive_pass = True
    for rate in (1.0e-6, 0.2):
        _, power, baryon, charge = kernel.nuclear_reaction_power(
            **reaction,
            event_rate=rate,
        )
        error = abs(power - 0.04 * rate)
        positive_pass = positive_pass and power > 0.0 and max(
            error,
            abs(baryon),
            abs(charge),
        ) <= 1.0e-14
        positive_rows.append(
            {
                "rate": rate,
                "power": power,
                "expected_power": 0.04 * rate,
                "power_error": error,
                "baryon_residual": baryon,
                "charge_residual": charge,
            }
        )
    book.add("nuclear.positive_rates_positive_power", positive_pass, rows=positive_rows)
    return {
        "valid_ledger_residual": residual,
        "net_nuclear_residual": kernel.control_volume_energy_residual(**net_ledger),
        "overdraw_residual": kernel.control_volume_energy_residual(**overdraw),
        "positive_reactions": positive_rows,
    }


def prerequisite_controls(book: CheckBook, work_root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="prerequisite_controls_", dir=work_root) as raw:
        temporary = Path(raw)

        def missing_dependency() -> dict[str, str]:
            raise ImportError("fixed missing-dependency control")

        dependency_target = temporary / "dependency" / "verification.json"
        dependency_code = base_verifier.run_verification(
            dependency_target,
            dependency_loader=missing_dependency,
        )
        dependency_receipt = json.loads(dependency_target.read_text(encoding="utf-8"))
        dependency_pass = (
            dependency_code == 2
            and dependency_receipt["status"] == "INCONCLUSIVE"
            and dependency_receipt["scientific_classification"] == "INCONCLUSIVE"
            and dependency_receipt["checks"]["total"] == 0
            and dependency_receipt["prerequisite_stage"] == "scientific-dependencies"
            and dependency_receipt["input_manifest"] is not None
            and bool(dependency_receipt["sources"])
        )
        book.add(
            "prerequisite.missing_dependency_is_inconclusive",
            dependency_pass,
            exit_code=dependency_code,
            receipt=dependency_receipt,
        )

        source_target = temporary / "source" / "verification.json"
        source_code = base_verifier.run_verification(
            source_target,
            source_paths=(Path("computations/__missing_integrity_control__.py"),),
        )
        source_receipt = json.loads(source_target.read_text(encoding="utf-8"))
        source_pass = (
            source_code == 2
            and source_receipt["status"] == "INCONCLUSIVE"
            and source_receipt["scientific_classification"] == "INCONCLUSIVE"
            and source_receipt["checks"]["total"] == 0
            and source_receipt["prerequisite_stage"] == "source-read"
            and source_receipt["input_manifest"] is None
            and not source_receipt["sources"]
            and not source_target.with_name("input_manifest.json").exists()
            and not (source_target.parent / "source_snapshots").exists()
        )
        book.add(
            "prerequisite.missing_source_is_inconclusive",
            source_pass,
            exit_code=source_code,
            receipt=source_receipt,
        )
        return {
            "dependency": dependency_receipt,
            "source_read": source_receipt,
        }


def verify_source_integrity(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    passed = True
    for relative, recorded in sources.items():
        try:
            current_path = ROOT / relative
            snapshot_path = ROOT / recorded["snapshot"]
            current = sha256(current_path)
            snapshot = sha256(snapshot_path)
            current_bytes = current_path.stat().st_size
            snapshot_bytes = snapshot_path.stat().st_size
            matches = (
                current == recorded["sha256"]
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
            matches = False
            error = f"{type(exc).__name__}: {exc}"
        rows[relative] = {
            "current_sha256": current,
            "recorded_sha256": recorded["sha256"],
            "snapshot_sha256": snapshot,
            "current_bytes": current_bytes,
            "snapshot_bytes": snapshot_bytes,
            "recorded_bytes": recorded["bytes"],
            "matches": matches,
            "error": error,
        }
        passed = passed and matches
    return {"passed": passed, "rows": rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def run(output: Path) -> int:
    try:
        target, _, _ = evidence_paths(output)
    except Exception as exc:
        print(f"EVIDENCE PATH FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    try:
        target, manifest_path, sources = prepare_evidence(output)
    except Exception as exc:
        return write_inconclusive(target, stage="source-read", error=exc)

    source_integrity: dict[str, Any] = {
        "after_snapshot": verify_source_integrity(sources)
    }
    if not source_integrity["after_snapshot"]["passed"]:
        dependencies: dict[str, str] = {}
    else:
        try:
            dependencies = load_dependencies()
        except Exception as exc:
            return write_inconclusive(
                target,
                stage="scientific-dependencies",
                error=exc,
                manifest_path=manifest_path,
                sources=sources,
            )
        source_integrity["before_controls"] = verify_source_integrity(sources)

    book = CheckBook()
    results: dict[str, Any] = {}
    error: str | None = None
    if not source_integrity["after_snapshot"]["passed"]:
        error = "source integrity mismatch immediately after snapshot publication"
    elif not source_integrity["before_controls"]["passed"]:
        error = "source integrity mismatch before scientific controls"
    else:
        try:
            results["state_and_thermodynamics"] = state_and_thermo_controls(book)
            results["shock"] = shock_control(book)
            results["lines"] = line_controls(book)
            results["transfer"] = transfer_controls(book)
            results["stellar"] = stellar_controls(book)
            results["prerequisites"] = prerequisite_controls(book, target.parent)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"

    source_integrity["after_controls"] = verify_source_integrity(sources)
    integrity_passed = all(
        phase["passed"] for phase in source_integrity.values()
    )
    if not integrity_passed and error is None:
        error = "source integrity mismatch after qualification controls"

    passed_count = sum(row["passed"] for row in book.checks.values())
    total_count = len(book.checks)
    status = (
        "PASS"
        if error is None and book.passed and integrity_passed
        else "FAIL"
    )
    if status == "PASS":
        scientific_classification = (
            "SUPPORTS-compressible radiative-plasma integrity qualification"
        )
    elif not integrity_passed:
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
            "expected_total": EXPECTED_CHECKS,
            "failed": book.failed,
            "items": book.checks,
        },
        "results": results,
        "input_manifest": manifest_path.relative_to(ROOT).as_posix(),
        "sources": sources,
        "source_integrity": source_integrity,
        "dependencies": dependencies,
        "error": error,
        "scope": {
            "supported": [
                "species-level constrained conservative state and kinetic recovery",
                "defensive public state construction",
                "ideal-gas fundamental-relation signs and density factor",
                "line-input admissibility and local exchange conservation",
                "isotropic transfer energy-source normalization",
                "gross-nuclear control-volume energy accounting",
                "prerequisite failures classified as INCONCLUSIVE",
            ],
            "unestablished": [
                "nonideal EOS table accuracy",
                "evaluated atomic opacity or reaction-rate accuracy",
                "production finite-volume convergence",
                "general angular convergence",
                "physical Cassi material identification",
                "live CassiCosmos implementation",
            ],
        },
    }
    write_receipt(target, receipt)
    print(
        f"COMPRESSIBLE PLASMA INTEGRITY RESULT: {status} "
        f"({passed_count}/{total_count} checks)"
    )
    print(f"receipt: {target.relative_to(ROOT).as_posix()}")
    if book.failed:
        print("failed checks: " + ", ".join(book.failed))
    if error is not None:
        print(f"verification error: {error}", file=sys.stderr)
    return 0 if status == "PASS" else 1


def main() -> int:
    args = parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    return run(output)


if __name__ == "__main__":
    raise SystemExit(main())
