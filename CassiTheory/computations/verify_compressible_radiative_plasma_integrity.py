#!/usr/bin/env python3
"""Run the fixed integrity qualification for the compressible plasma closure."""

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

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "cassi-compressible-radiative-plasma-integrity-v2"
DEFAULT_OUTPUT = (
    ROOT / "runs" / "compressible_radiative_plasma_integrity" / "verification.json"
)
INTEGRITY_PREREG_SOURCE = Path(
    "computations/compressible-radiative-plasma-integrity-prereg.md"
)
KERNEL_SOURCE = Path("computations/compressible_radiative_plasma.py")
BASE_VERIFIER_SOURCE = Path("computations/verify_compressible_radiative_plasma.py")
INTEGRITY_VERIFIER_SOURCE = Path(
    "computations/verify_compressible_radiative_plasma_integrity.py"
)
SOURCE_PATHS = (
    INTEGRITY_PREREG_SOURCE,
    Path("computations/compressible-radiative-plasma-prereg.md"),
    Path("turbulence/compressible-radiative-plasma-closure.md"),
    KERNEL_SOURCE,
    BASE_VERIFIER_SOURCE,
    INTEGRITY_VERIFIER_SOURCE,
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


def _strictly_under(root: Path, candidate: Path) -> bool:
    return candidate != root and root in candidate.parents


def _validate_snapshot_root(snapshot_root: Path) -> Path:
    repository_root = ROOT.resolve()
    root = snapshot_root.resolve()
    if not _strictly_under(repository_root, root) or not root.is_dir():
        raise ValueError(f"snapshot root is not a directory under ROOT: {root}")
    return root


def _validate_source_paths(
    source_paths: Iterable[Path],
    snapshot_staging: Path,
) -> tuple[tuple[Path, Path, Path], ...]:
    repository_root = ROOT.resolve()
    staging_root = snapshot_staging.resolve()
    if not _strictly_under(repository_root, staging_root):
        raise ValueError(f"snapshot staging is not under ROOT: {staging_root}")

    validated: list[tuple[Path, Path, Path]] = []
    seen: set[str] = set()
    for supplied in source_paths:
        relative = Path(supplied)
        if relative.is_absolute() or relative.anchor:
            raise ValueError(f"source path must be relative: {relative}")
        if ".." in relative.parts:
            raise ValueError(f"source path must not contain '..': {relative}")
        key = relative.as_posix()
        if key in seen:
            raise ValueError(f"duplicate source path: {key}")
        source_path = (repository_root / relative).resolve()
        staged_destination = (staging_root / relative).resolve()
        if not _strictly_under(repository_root, source_path):
            raise ValueError(f"source path escapes ROOT: {relative}")
        if not _strictly_under(staging_root, staged_destination):
            raise ValueError(f"staged destination escapes snapshot root: {relative}")
        seen.add(key)
        validated.append((relative, source_path, staged_destination))
    return tuple(validated)


def _load_published_manifest(
    manifest_path: Path,
    snapshot_root: Path,
    expected_sources: dict[str, dict[str, Any]],
) -> tuple[Path, dict[str, dict[str, Any]]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise ValueError("published manifest schema mismatch")
    recorded_root = manifest.get("snapshot_root")
    if not isinstance(recorded_root, str):
        raise ValueError("published manifest has no relative snapshot root")
    recorded_root_path = Path(recorded_root)
    if (
        recorded_root_path.is_absolute()
        or recorded_root_path.anchor
        or ".." in recorded_root_path.parts
        or recorded_root_path.as_posix() != recorded_root
    ):
        raise ValueError(f"published snapshot root is not canonical: {recorded_root}")
    manifest_root = _validate_snapshot_root(ROOT / recorded_root_path)
    expected_root = _validate_snapshot_root(snapshot_root)
    if manifest_root != expected_root:
        raise ValueError("published manifest snapshot root mismatch")

    sources = manifest.get("sources")
    if not isinstance(sources, dict) or sources != expected_sources:
        raise ValueError("published manifest source records mismatch")
    for key, recorded in sources.items():
        if not isinstance(key, str) or not isinstance(recorded, dict):
            raise ValueError("published manifest source record is malformed")
        relative = Path(key)
        snapshot = recorded.get("snapshot")
        if (
            recorded.get("path") != key
            or not isinstance(snapshot, str)
            or snapshot != key
            or relative.is_absolute()
            or relative.anchor
            or ".." in relative.parts
            or relative.as_posix() != key
        ):
            raise ValueError(f"published source record is not canonical: {key}")
        expected_path = (manifest_root / relative).resolve()
        snapshot_path = (manifest_root / Path(snapshot)).resolve()
        if (
            snapshot_path != expected_path
            or not _strictly_under(manifest_root, snapshot_path)
        ):
            raise ValueError(f"published source snapshot escapes root: {key}")
    return manifest_root, sources


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

    root = _validate_snapshot_root(snapshot_root)
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


def bind_frozen_execution_modules(
    sources: dict[str, dict[str, Any]],
    snapshot_root: Path,
) -> tuple[ModuleType, dict[str, Any]]:
    """Bind every scientific module to the manifest's frozen snapshot tree."""
    if np is None or sp is None or integrate is None:
        raise RuntimeError("scientific dependencies must be loaded before source binding")
    frozen_kernel, kernel_binding = load_frozen_module(
        sources,
        KERNEL_SOURCE,
        snapshot_root,
        role="integrity_kernel",
    )
    frozen_base, base_binding = load_frozen_module(
        sources,
        BASE_VERIFIER_SOURCE,
        snapshot_root,
        role="integrity_base_verifier",
    )
    frozen_integrity, integrity_binding = load_frozen_module(
        sources,
        INTEGRITY_VERIFIER_SOURCE,
        snapshot_root,
        role="integrity_verifier",
    )

    frozen_base.np = np
    frozen_base.sp = sp
    for name in frozen_base.SCIENTIFIC_EXPORTS:
        if not hasattr(frozen_kernel, name):
            raise ImportError(f"frozen kernel has no export {name!r}")
        setattr(frozen_base, name, getattr(frozen_kernel, name))

    frozen_integrity.np = np
    frozen_integrity.sp = sp
    frozen_integrity.integrate = integrate
    frozen_integrity.kernel = frozen_kernel
    frozen_integrity.base_verifier = frozen_base
    bindings = {
        "passed": True,
        "error": None,
        "modules": {
            "kernel": kernel_binding,
            "base_verifier": base_binding,
            "integrity_verifier": integrity_binding,
        },
    }
    return frozen_integrity, bindings


def evidence_paths(output: Path) -> tuple[Path, Path, Path]:
    target = output.resolve()
    if ROOT != target and ROOT not in target.parents:
        raise ValueError("output must remain inside the CassiTheory root")
    manifest_path = target.with_name("input_manifest.json")
    snapshot_root = target.parent / "source_snapshots"
    nested_root = snapshot_root / "prerequisite_controls"
    manifest_staging = manifest_path.with_name(manifest_path.name + ".incomplete")
    snapshot_staging = snapshot_root.with_name(snapshot_root.name + ".incomplete")
    for path in (
        target,
        manifest_path,
        snapshot_root,
        nested_root,
        manifest_staging,
        snapshot_staging,
    ):
        if path.exists():
            raise FileExistsError(f"refusing existing evidence path: {path}")
    return target, manifest_path, snapshot_root


def prepare_evidence(
    output: Path,
) -> tuple[Path, Path, Path, dict[str, dict[str, Any]]]:
    target, manifest_path, snapshot_root = evidence_paths(output)
    manifest_staging = manifest_path.with_name(manifest_path.name + ".incomplete")
    snapshot_staging = snapshot_root.with_name(snapshot_root.name + ".incomplete")
    validated_sources = _validate_source_paths(SOURCE_PATHS, snapshot_staging)

    try:
        payloads = [
            (relative, source_path.read_bytes(), staged_destination)
            for relative, source_path, staged_destination in validated_sources
        ]
        target.parent.mkdir(parents=True, exist_ok=True)
        snapshot_staging.mkdir()
        sources: dict[str, dict[str, Any]] = {}
        for relative, payload, staged_destination in payloads:
            staged_destination.parent.mkdir(parents=True, exist_ok=True)
            staged_destination.write_bytes(payload)
            digest = sha256_bytes(payload)
            sources[relative.as_posix()] = {
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
                    "sources": sources,
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
        return target, manifest_path, snapshot_root, sources
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
    snapshot_root: Path | None = None,
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
        },
    )
    print(f"COMPRESSIBLE PLASMA INTEGRITY RESULT: INCONCLUSIVE ({stage})")
    print(f"receipt: {target.relative_to(ROOT).as_posix()}")
    print(f"prerequisite error: {message}", file=sys.stderr)
    return 2


def load_dependencies() -> dict[str, str]:
    """Load external numerical dependencies before frozen-source execution."""
    loaded_np = importlib.import_module("numpy")
    loaded_sp = importlib.import_module("sympy")
    loaded_scipy = importlib.import_module("scipy")
    loaded_integrate = importlib.import_module("scipy.integrate")
    global np, sp, integrate
    np = loaded_np
    sp = loaded_sp
    integrate = loaded_integrate
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


def prerequisite_controls(book: CheckBook, target: Path) -> dict[str, Any]:
    outer_snapshot_root = (target.parent / "source_snapshots").resolve()
    base_module_path = Path(base_verifier.__file__).resolve()
    expected_base_module_path = (outer_snapshot_root / BASE_VERIFIER_SOURCE).resolve()
    root_bound = base_module_path == expected_base_module_path
    if not root_bound:
        raise RuntimeError("frozen base verifier is not loaded from the outer snapshot root")

    nested_root = outer_snapshot_root / "prerequisite_controls"
    nested_root.mkdir(parents=True, exist_ok=True)

    def under(root: Path, candidate: Path) -> bool:
        return candidate == root or root in candidate.parents

    def receipt_snapshot_root(
        receipt: dict[str, Any],
        receipt_target: Path,
    ) -> tuple[Path | None, bool]:
        value = receipt.get("snapshot_root")
        if not isinstance(value, str):
            return None, False
        candidate = (outer_snapshot_root / value).resolve()
        expected = (receipt_target.parent / "source_snapshots").resolve()
        return candidate, under(outer_snapshot_root, candidate) and candidate == expected

    def receipt_manifest_bound(
        receipt: dict[str, Any],
        receipt_target: Path,
    ) -> bool:
        value = receipt.get("input_manifest")
        if not isinstance(value, str):
            return False
        candidate = (outer_snapshot_root / value).resolve()
        expected = (receipt_target.parent / "input_manifest.json").resolve()
        return candidate == expected

    def receipt_sources_bound(
        receipt: dict[str, Any],
        receipt_target: Path,
        expected_sources: set[str],
    ) -> tuple[bool, Path | None, bool]:
        snapshot_root, snapshot_root_bound = receipt_snapshot_root(
            receipt,
            receipt_target,
        )
        if snapshot_root is None:
            return False, None, False
        sources = receipt.get("sources", {})
        if not isinstance(sources, dict) or set(sources) != expected_sources:
            return False, snapshot_root, snapshot_root_bound
        source_paths_bound = True
        for source_key, recorded in sources.items():
            if not isinstance(recorded, dict) or recorded.get("path") != source_key:
                source_paths_bound = False
                continue
            source_relative = Path(source_key)
            recorded_relative = Path(str(recorded.get("snapshot", "")))
            source_path = (snapshot_root / source_relative).resolve()
            recorded_path = (snapshot_root / recorded_relative).resolve()
            source_paths_bound = source_paths_bound and (
                not recorded_relative.is_absolute()
                and under(snapshot_root, recorded_path)
                and recorded_path == source_path
            )
        return (
            snapshot_root_bound and source_paths_bound
            and receipt_manifest_bound(receipt, receipt_target),
            snapshot_root,
            snapshot_root_bound,
        )

    def module_bindings_bound(
        receipt: dict[str, Any],
        snapshot_root: Path | None,
    ) -> bool:
        if snapshot_root is None:
            return False
        bindings = receipt.get("execution_binding", {}).get("modules", {})
        expected_modules = {
            "kernel": KERNEL_SOURCE.as_posix(),
            "verifier": BASE_VERIFIER_SOURCE.as_posix(),
        }
        if not isinstance(bindings, dict) or set(bindings) != set(expected_modules):
            return False
        for name, source_key in expected_modules.items():
            binding = bindings.get(name)
            if not isinstance(binding, dict):
                return False
            snapshot_relative = Path(str(binding.get("snapshot", "")))
            module_relative = Path(str(binding.get("module_file", "")))
            expected = (snapshot_root / source_key).resolve()
            expected_binding_root = snapshot_root.relative_to(
                outer_snapshot_root
            ).as_posix()
            if (
                binding.get("snapshot_root") != expected_binding_root
                or snapshot_relative.is_absolute()
                or module_relative.is_absolute()
                or (snapshot_root / snapshot_relative).resolve() != expected
                or (snapshot_root / module_relative).resolve() != expected
            ):
                return False
        return True

    expected_base_sources = {
        path.as_posix() for path in base_verifier.SOURCE_PATHS
    }
    qualification_target = nested_root / "qualification" / "verification.json"
    qualification_code = base_verifier.run_verification(qualification_target)
    qualification_receipt = json.loads(
        qualification_target.read_text(encoding="utf-8")
    )
    qualification_sources_bound, qualification_snapshot_root, qualification_root_bound = (
        receipt_sources_bound(
            qualification_receipt,
            qualification_target,
            expected_base_sources,
        )
    )
    qualification_bindings = qualification_receipt["execution_binding"]["modules"]
    qualification_modules_bound = module_bindings_bound(
        qualification_receipt,
        qualification_snapshot_root,
    )
    qualification_pass = (
        qualification_code == 0
        and qualification_receipt["status"] == "PASS"
        and qualification_receipt["scientific_classification"]
        == "SUPPORTS-conditional compressible radiative-plasma closure"
        and qualification_receipt["checks"]["passed"] == 70
        and qualification_receipt["checks"]["total"] == 70
        and qualification_receipt["checks"]["expected_total"] == 70
        and qualification_receipt["checks"]["module_expected_total"] == 70
        and qualification_receipt["checks"]["module_expected_error"] is None
        and qualification_receipt["checks"]["declaration_matches_expected"]
        and qualification_receipt["checks"]["count_matches_expected"]
        and qualification_receipt["source_integrity"]["after_snapshot"]["passed"]
        and qualification_receipt["source_integrity"]["before_controls"]["passed"]
        and qualification_receipt["source_integrity"]["after_controls"]["passed"]
        and qualification_receipt["execution_binding"]["passed"]
        and qualification_sources_bound
        and qualification_modules_bound
    )

    def missing_dependency() -> dict[str, str]:
        raise ImportError("fixed missing-dependency control")

    dependency_target = nested_root / "dependency" / "verification.json"
    dependency_code = base_verifier.run_verification(
        dependency_target,
        dependency_loader=missing_dependency,
    )
    dependency_receipt = json.loads(
        dependency_target.read_text(encoding="utf-8")
    )
    dependency_sources_bound, _, dependency_root_bound = receipt_sources_bound(
        dependency_receipt,
        dependency_target,
        expected_base_sources,
    )
    dependency_pass = (
        dependency_code == 2
        and dependency_receipt["status"] == "INCONCLUSIVE"
        and dependency_receipt["scientific_classification"] == "INCONCLUSIVE"
        and dependency_receipt["checks"]["total"] == 0
        and dependency_receipt["prerequisite_stage"] == "scientific-dependencies"
        and dependency_receipt["input_manifest"] is not None
        and dependency_sources_bound
    )
    book.add(
        "prerequisite.snapshot_root_and_missing_dependency",
        qualification_pass and dependency_pass,
        root_bound=root_bound,
        qualification_exit_code=qualification_code,
        qualification_root_bound=qualification_root_bound,
        qualification_sources_bound=qualification_sources_bound,
        qualification_modules_bound=qualification_modules_bound,
        qualification_receipt=qualification_receipt,
        dependency_exit_code=dependency_code,
        dependency_root_bound=dependency_root_bound,
        dependency_sources_bound=dependency_sources_bound,
        dependency_receipt=dependency_receipt,
    )

    source_target = nested_root / "source" / "verification.json"
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
        and source_receipt["snapshot_root"] is None
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
        "nested_root": nested_root.relative_to(outer_snapshot_root).as_posix(),
        "snapshot_root_qualification": qualification_receipt,
        "dependency": dependency_receipt,
        "source_read": source_receipt,
    }


def execute_integrity_controls(book: CheckBook, target: Path) -> dict[str, Any]:
    """Execute the complete fixed integrity schedule in this verifier module."""
    return {
        "state_and_thermodynamics": state_and_thermo_controls(book),
        "shock": shock_control(book),
        "lines": line_controls(book),
        "transfer": transfer_controls(book),
        "stellar": stellar_controls(book),
        "prerequisites": prerequisite_controls(book, target),
    }


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def run(output: Path) -> int:
    required_check_count = EXPECTED_CHECKS
    try:
        target, _, snapshot_root = evidence_paths(output)
    except Exception as exc:
        print(f"EVIDENCE PATH FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    try:
        target, manifest_path, snapshot_root, sources = prepare_evidence(output)
    except Exception as exc:
        return write_inconclusive(
            target,
            stage="source-read",
            error=exc,
            snapshot_root=snapshot_root,
        )

    try:
        snapshot_root, sources = _load_published_manifest(
            manifest_path,
            snapshot_root,
            sources,
        )
    except Exception as exc:
        return write_inconclusive(
            target,
            stage="manifest-read",
            error=exc,
            manifest_path=manifest_path,
            snapshot_root=snapshot_root,
            sources=sources,
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
            dependencies = load_dependencies()
        except Exception as exc:
            return write_inconclusive(
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
                execution_module, execution_binding = bind_frozen_execution_modules(
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
            results = execution_module.execute_integrity_controls(book, target)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"

    source_integrity["after_controls"] = verify_source_integrity(
        sources,
        snapshot_root,
    )
    integrity_passed = all(
        phase["passed"] for phase in source_integrity.values()
    )
    binding_passed = bool(execution_binding["passed"])
    if not integrity_passed and error is None:
        error = "source integrity mismatch after qualification controls"

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
            "fixed qualification check count mismatch: "
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
            "SUPPORTS-compressible radiative-plasma integrity qualification"
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
    if failed_checks:
        print("failed checks: " + ", ".join(failed_checks))
    if error is not None:
        print(f"verification error: {error}", file=sys.stderr)
    return 0 if status == "PASS" else 1


def main() -> int:
    args = parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    return run(output)


if __name__ == "__main__":
    raise SystemExit(main())
