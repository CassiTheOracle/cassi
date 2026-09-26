#!/usr/bin/env python3
"""Run the fixed source-step accuracy qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp

from cassi_radiative_material import (
    RadiationParameters,
    equilibrium_temperature,
    evolve_exchange,
    lte_energy,
)


SCHEMA = "cassi-radiative-material-qualification-v1"
SOURCES = (
    "computations/cassi-radiative-material-qualification-prereg.md",
    "computations/cassi_radiative_material.py",
    "computations/verify_cassi_radiative_material_qualification.py",
    "runs/cassi_radiative_material/verification.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root: Path, output: Path) -> tuple[Path, Path, list[dict[str, str]]]:
    root = root.resolve()
    output = output.resolve()
    if root != output and root not in output.parents:
        raise ValueError("output must remain inside the CassiTheory root")
    manifest = output.with_name("input_manifest.json")
    snapshots = output.parent / "source_snapshots"
    for path in (output, manifest, snapshots):
        if path.exists():
            raise FileExistsError(f"refusing existing evidence path: {path}")
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshots.mkdir()
    records: list[dict[str, str]] = []
    for relative in SOURCES:
        source = root / relative
        snapshot = snapshots / relative.replace("/", "__")
        shutil.copyfile(source, snapshot)
        records.append(
            {
                "path": relative,
                "sha256": sha256(source),
                "snapshot": snapshot.relative_to(root).as_posix(),
                "snapshot_sha256": sha256(snapshot),
            }
        )
    manifest.write_text(
        json.dumps({"schema": SCHEMA, "sources": records}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output, manifest, records


def normalized_error(value: np.ndarray, reference: np.ndarray) -> float:
    return float(np.linalg.norm(value - reference) / max(1.0, np.linalg.norm(reference)))


def finite_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): finite_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_json(item) for item in value]
    if isinstance(value, np.ndarray):
        return finite_json(value.tolist())
    if isinstance(value, (np.floating, np.integer)):
        return finite_json(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite receipt value")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runs/cassi_radiative_material_qualification/verification.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    output, manifest, sources = prepare(root, root / args.output)
    parameters = RadiationParameters()
    initial = np.asarray([0.2, 0.5], dtype=np.float64)
    duration = 2.0
    steps = (0.004, 0.002, 0.001)

    def rhs(_time: float, state: np.ndarray) -> np.ndarray:
        source = parameters.light_speed * parameters.absorption * (
            parameters.radiation_constant * state[0] ** 4 - state[1]
        )
        return np.asarray([-source / parameters.heat_capacity, source])

    reference = solve_ivp(
        rhs,
        (0.0, duration),
        initial,
        method="DOP853",
        rtol=1e-12,
        atol=1e-12,
    )
    checks: list[dict[str, Any]] = []

    def check(label: str, passed: bool, **details: Any) -> None:
        if any(item["label"] == label for item in checks):
            raise ValueError(f"duplicate check label: {label}")
        checks.append({"label": label, "passed": bool(passed), **details})

    check("independent DOP853 reference", reference.success, message=reference.message)
    reference_endpoint = reference.y[:, -1]
    rows: list[dict[str, Any]] = []
    errors: list[float] = []
    all_positive = True
    max_energy_drift = 0.0
    min_entropy_step = math.inf
    max_energy_reconstruction = 0.0
    max_entropy_reconstruction = 0.0
    for dt in steps:
        history = evolve_exchange(initial[0], initial[1], duration, dt, parameters)
        endpoint = history[-1, 1:3]
        error = normalized_error(endpoint, reference_endpoint)
        errors.append(error)
        reconstructed_energy = parameters.heat_capacity * history[:, 1] + history[:, 2]
        reconstructed_entropy = (
            parameters.heat_capacity * np.log(history[:, 1])
            + (4.0 / 3.0)
            * parameters.radiation_constant**0.25
            * history[:, 2] ** 0.75
        )
        energy_drift = float(np.max(np.abs(reconstructed_energy - reconstructed_energy[0])))
        entropy_step = float(np.min(np.diff(reconstructed_entropy)))
        energy_reconstruction = float(np.max(np.abs(reconstructed_energy - history[:, 3])))
        entropy_reconstruction = float(np.max(np.abs(reconstructed_entropy - history[:, 4])))
        all_positive = all_positive and bool(np.isfinite(history).all()) and bool(np.all(history[:, 1:3] > 0.0))
        max_energy_drift = max(max_energy_drift, energy_drift)
        min_entropy_step = min(min_entropy_step, entropy_step)
        max_energy_reconstruction = max(max_energy_reconstruction, energy_reconstruction)
        max_entropy_reconstruction = max(max_entropy_reconstruction, entropy_reconstruction)
        rows.append(
            {
                "dt": dt,
                "steps": len(history) - 1,
                "endpoint": endpoint,
                "normalized_error": error,
                "energy_drift": energy_drift,
                "minimum_entropy_step": entropy_step,
                "energy_reconstruction_error": energy_reconstruction,
                "entropy_reconstruction_error": entropy_reconstruction,
            }
        )

    ratios = [errors[index] / errors[index + 1] for index in range(len(errors) - 1)]
    check("qualified source positivity", all_positive, trajectories=len(steps))
    check(
        "qualified source energy conservation",
        max_energy_drift <= 2e-12,
        maximum_absolute_drift=max_energy_drift,
    )
    check(
        "qualified source entropy monotonicity",
        min_entropy_step >= -2e-12,
        minimum_step=min_entropy_step,
    )
    check(
        "qualified endpoint error decreases",
        all(errors[index + 1] < errors[index] for index in range(len(errors) - 1)),
        errors=errors,
    )
    check(
        "qualified first-order refinement",
        min(ratios) >= 1.8,
        ratios=ratios,
    )
    check(
        "qualified finest endpoint accuracy",
        errors[-1] <= 5e-5,
        normalized_error=errors[-1],
    )

    total = parameters.heat_capacity * initial[0] + initial[1]
    equilibrium_temperature_value = equilibrium_temperature(total, parameters)
    equilibrium = np.asarray(
        [equilibrium_temperature_value, lte_energy(equilibrium_temperature_value, parameters)]
    )
    initial_distance = normalized_error(initial, equilibrium)
    final_distance = normalized_error(rows[-1]["endpoint"], equilibrium)
    check(
        "qualified equilibrium approach",
        final_distance < initial_distance,
        initial_distance=initial_distance,
        final_distance=final_distance,
    )
    check(
        "qualified diagnostic reconstruction",
        max_energy_reconstruction <= 1e-13 and max_entropy_reconstruction <= 1e-13,
        maximum_energy_error=max_energy_reconstruction,
        maximum_entropy_error=max_entropy_reconstruction,
    )

    passed = sum(bool(item["passed"]) for item in checks)
    status = "PASS" if reference.success and passed == len(checks) else "FAIL"
    receipt = {
        "schema": SCHEMA,
        "status": status,
        "scientific_classification": (
            "SUPPORTS-backward-Euler source subcycling"
            if status == "PASS"
            else ("INCONCLUSIVE" if not reference.success else "FAIL")
        ),
        "checks": {"passed": passed, "total": len(checks), "items": checks},
        "initial": initial,
        "duration": duration,
        "parameters": {
            "light_speed": parameters.light_speed,
            "radiation_constant": parameters.radiation_constant,
            "heat_capacity": parameters.heat_capacity,
            "absorption": parameters.absorption,
            "transport": parameters.transport,
        },
        "reference_endpoint": reference_endpoint,
        "equilibrium": equilibrium,
        "runs": rows,
        "refinement_ratios": ratios,
        "input_manifest": manifest.relative_to(root).as_posix(),
        "sources": sources,
        "scope": "Unchanged gray source equation and benchmark; no physical Cassi material calibration.",
    }
    output.write_text(
        json.dumps(finite_json(receipt), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"RADIATIVE SOURCE QUALIFICATION: {status} ({passed}/{len(checks)} checks)")
    print(f"receipt: {output.relative_to(root).as_posix()}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
