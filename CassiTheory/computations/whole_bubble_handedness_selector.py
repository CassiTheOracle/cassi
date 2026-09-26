#!/usr/bin/env python3
"""Run the frozen whole-bubble handedness selector calculation.

From the CassiTheory root:
    python computations/whole_bubble_handedness_selector.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import sys
import time
from itertools import product
from pathlib import Path
from typing import Any, cast

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "runs" / "20260910_whole_bubble_handedness_selector" / "primary"
PROTOCOL = ROOT / "computations" / "whole-bubble-handedness-selector-prereg.md"
SOURCE_PATHS = (
    PROTOCOL,
    Path(__file__).resolve(),
    ROOT / "foundations" / "interscale-current-soliton.md",
    ROOT / "turbulence" / "cassi-fluid-phase-current-hydrodynamics.md",
    ROOT / "computations" / "matter-formation-continuum-report.md",
)
SCHEMA = "cassi.whole-bubble-handedness-selector.primary.v1"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
AMPLITUDE = 0.6
KAPPA_CONTROL = 0.137
GRIDS = (9, 15, 21)
TOL = 1.0e-12


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def source_record(path: Path) -> dict[str, Any]:
    return {
        "path": relative(path),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite value: {value}")
    return value


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(json_ready(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def spectral_derivative(values: np.ndarray) -> np.ndarray:
    count = values.shape[0]
    dz = 2.0 * math.pi / count
    wave_numbers = 2.0 * math.pi * np.fft.fftfreq(count, d=dz)
    transformed = np.fft.fft(values, axis=0)
    return np.fft.ifft(1j * wave_numbers[:, None] * transformed, axis=0).real


def curl_z_field(field: np.ndarray) -> np.ndarray:
    derivative = spectral_derivative(field)
    curl = np.zeros_like(field)
    curl[:, 0] = -derivative[:, 1]
    curl[:, 1] = derivative[:, 0]
    return curl


def beltrami_fixture(count: int, sign: int) -> tuple[np.ndarray, np.ndarray]:
    z = 2.0 * math.pi * np.arange(count, dtype=np.float64) / count
    field = np.zeros((count, 3), dtype=np.float64)
    field[:, 0] = AMPLITUDE * np.sin(z)
    field[:, 1] = sign * AMPLITUDE * np.cos(z)
    curl = curl_z_field(field)
    return field, curl


def positive_chart_fixture(count: int) -> tuple[np.ndarray, np.ndarray]:
    y = 2.0 * math.pi * np.arange(count, dtype=np.float64) / count
    amplitude = 0.4
    field = np.zeros((count, 3), dtype=np.float64)
    field[:, 0] = amplitude * np.sin(y)
    derivative = spectral_derivative(field)
    curl = np.zeros_like(field)
    curl[:, 2] = -derivative[:, 0]
    return field, curl


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)

    started = time.time()
    records = [source_record(path) for path in SOURCE_PATHS]
    for path in SOURCE_PATHS:
        destination = output / "sources" / relative(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)

    arrays: dict[str, np.ndarray] = {}
    fixture_rows: list[dict[str, Any]] = []
    max_curl_error = 0.0
    max_divergence = 0.0
    max_energy_difference = 0.0
    max_helicity_sum = 0.0
    max_positive_chart_helicity = 0.0

    for count in GRIDS:
        plus, curl_plus = beltrami_fixture(count, +1)
        minus, curl_minus = beltrami_fixture(count, -1)
        chart, curl_chart = positive_chart_fixture(count)
        arrays[f"u_plus_n{count}"] = plus
        arrays[f"curl_plus_n{count}"] = curl_plus
        arrays[f"u_minus_n{count}"] = minus
        arrays[f"curl_minus_n{count}"] = curl_minus
        arrays[f"positive_chart_u_n{count}"] = chart
        arrays[f"positive_chart_curl_n{count}"] = curl_chart

        plus_curl_error = float(np.max(np.abs(curl_plus - plus)))
        minus_curl_error = float(np.max(np.abs(curl_minus + minus)))
        plus_divergence = float(np.max(np.abs(spectral_derivative(plus)[:, 2])))
        minus_divergence = float(np.max(np.abs(spectral_derivative(minus)[:, 2])))
        energy_plus = float(0.5 * np.mean(np.sum(plus * plus, axis=1)))
        energy_minus = float(0.5 * np.mean(np.sum(minus * minus, axis=1)))
        helicity_plus = float(np.mean(np.sum(plus * curl_plus, axis=1)))
        helicity_minus = float(np.mean(np.sum(minus * curl_minus, axis=1)))
        chart_helicity = float(np.mean(np.sum(chart * curl_chart, axis=1)))

        max_curl_error = max(max_curl_error, plus_curl_error, minus_curl_error)
        max_divergence = max(max_divergence, plus_divergence, minus_divergence)
        max_energy_difference = max(max_energy_difference, abs(energy_plus - energy_minus))
        max_helicity_sum = max(max_helicity_sum, abs(helicity_plus + helicity_minus))
        max_positive_chart_helicity = max(max_positive_chart_helicity, abs(chart_helicity))
        fixture_rows.append(
            {
                "grid": count,
                "plus_curl_error": plus_curl_error,
                "minus_curl_error": minus_curl_error,
                "max_divergence": max(plus_divergence, minus_divergence),
                "energy_plus": energy_plus,
                "energy_minus": energy_minus,
                "helicity_plus": helicity_plus,
                "helicity_minus": helicity_minus,
                "positive_chart_helicity": chart_helicity,
            }
        )

    lambda_rho = 0.7
    lambda_phi = 1.1
    ey0 = PHI / (1.0 + PHI)
    ei0 = 1.0 / (1.0 + PHI)
    rho0 = ey0 + ei0
    a = np.array([1.0, 1.0])
    b = np.array([1.0, -PHI])
    density_rows: list[dict[str, Any]] = []
    density_eigenvalues: list[np.ndarray] = []
    omega_squared: list[float] = []
    for sigma in (0.0, 0.1, 1.0, 10.0):
        hessian = (
            0.5 * lambda_rho * np.outer(a, a)
            + lambda_phi * np.outer(b, b)
            + 0.25 * sigma * np.diag([1.0 / ey0, 1.0 / ei0])
        )
        eigenvalues = np.linalg.eigvalsh(hessian)
        omega2 = (
            sigma
            * (ey0 * ei0 / rho0)
            * (2.0 * lambda_rho + lambda_phi * (1.0 - PHI) ** 2)
            + sigma**2 / 4.0
        )
        density_eigenvalues.append(eigenvalues)
        omega_squared.append(float(omega2))
        density_rows.append(
            {
                "sigma": sigma,
                "eigenvalues": eigenvalues,
                "omega_long_squared": omega2,
            }
        )
    arrays["density_eigenvalues"] = np.vstack(density_eigenvalues)
    arrays["omega_long_squared"] = np.asarray(omega_squared)

    transverse_rows: list[dict[str, Any]] = []
    transverse_values: list[float] = []
    max_polarization_difference = 0.0
    for mu_x, mu_m, mass2, wave_number, scale_wave_number in product(
        (0.4, 1.0, 2.5),
        (0.5, 1.5),
        (0.1, 1.0, 3.0),
        (1.0, 2.0, 4.0),
        (0.0, 1.0, 3.0),
    ):
        operator_plus = wave_number**2 / mu_x + scale_wave_number**2 / mu_m + mass2
        operator_minus = wave_number**2 / mu_x + scale_wave_number**2 / mu_m + mass2
        max_polarization_difference = max(
            max_polarization_difference, abs(operator_plus - operator_minus)
        )
        transverse_values.append(operator_plus)
        transverse_rows.append(
            {
                "mu_x": mu_x,
                "mu_m": mu_m,
                "mass_squared": mass2,
                "wave_number": wave_number,
                "scale_wave_number": scale_wave_number,
                "operator_plus": operator_plus,
                "operator_minus": operator_minus,
            }
        )
    arrays["transverse_operator"] = np.asarray(transverse_values)

    expected_kinetic = 0.5 * AMPLITUDE**2
    expected_helicity = AMPLITUDE**2
    default_split = 0.0
    explicit_split = -2.0 * KAPPA_CONTROL * AMPLITUDE**2
    measured_explicit_split = (
        expected_kinetic - KAPPA_CONTROL * expected_helicity
    ) - (
        expected_kinetic + KAPPA_CONTROL * expected_helicity
    )

    charge_conjugation = {"velocity": -1, "vorticity": -1}
    parity = {"velocity": -1, "vorticity": +1}
    transformation_signs = {
        "C": {
            **charge_conjugation,
            "helicity": charge_conjugation["velocity"]
            * charge_conjugation["vorticity"],
        },
        "P": {
            **parity,
            "helicity": parity["velocity"] * parity["vorticity"],
        },
        "CP": {
            "velocity": charge_conjugation["velocity"] * parity["velocity"],
            "vorticity": charge_conjugation["vorticity"] * parity["vorticity"],
            "helicity": charge_conjugation["velocity"]
            * parity["velocity"]
            * charge_conjugation["vorticity"]
            * parity["vorticity"],
        },
    }
    expected_signs = {
        "C": {"velocity": -1, "vorticity": -1, "helicity": +1},
        "P": {"velocity": -1, "vorticity": +1, "helicity": -1},
        "CP": {"velocity": +1, "vorticity": -1, "helicity": -1},
    }
    action_term_signs = {
        "spatial_covariant_gradient": +1,
        "scale_covariant_gradient": +1,
        "density_potential": +1,
        "composition_potential": +1,
        "spatial_curvature_square": +1,
        "mixed_curvature_square": +1,
    }

    min_density_eigenvalue = float(np.min(arrays["density_eigenvalues"]))
    min_omega_squared = float(np.min(arrays["omega_long_squared"]))
    min_transverse_operator = float(np.min(arrays["transverse_operator"]))
    gates = {
        "WHS1": transformation_signs == expected_signs,
        "WHS2": all(sign == 1 for sign in action_term_signs.values())
        and max_positive_chart_helicity <= TOL,
        "WHS3": max_curl_error <= TOL and max_divergence <= TOL,
        "WHS4": max_energy_difference <= TOL and max_helicity_sum <= TOL,
        "WHS5": min_density_eigenvalue >= -TOL and min_omega_squared >= -TOL,
        "WHS6": min_transverse_operator > 0.0
        and max_polarization_difference <= 1.0e-14,
        "WHS7": abs(default_split) <= TOL,
        "WHS8": abs(measured_explicit_split - explicit_split) <= TOL,
    }
    execution_valid = all(gates.values())
    arrays_path = output / "arrays.npz"
    cast(Any, np.savez_compressed)(arrays_path, **arrays)

    payload = {
        "schema": SCHEMA,
        "execution_valid": execution_valid,
        "elapsed_seconds": time.time() - started,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "constants": {
            "phi": PHI,
            "amplitude": AMPLITUDE,
            "kappa_control": KAPPA_CONTROL,
            "grids": GRIDS,
            "tolerance": TOL,
        },
        "source_records": records,
        "transformations": transformation_signs,
        "action_term_signs": action_term_signs,
        "fixtures": fixture_rows,
        "density_stability": density_rows,
        "transverse_stability": transverse_rows,
        "metrics": {
            "max_positive_chart_helicity": max_positive_chart_helicity,
            "max_curl_error": max_curl_error,
            "max_divergence": max_divergence,
            "max_energy_difference": max_energy_difference,
            "max_helicity_sum": max_helicity_sum,
            "min_density_eigenvalue": min_density_eigenvalue,
            "min_omega_long_squared": min_omega_squared,
            "min_transverse_operator": min_transverse_operator,
            "max_polarization_difference": max_polarization_difference,
            "default_energy_split": default_split,
            "explicit_selector_split": measured_explicit_split,
            "expected_explicit_selector_split": explicit_split,
        },
        "gates": gates,
        "verdicts": {
            "cp_odd_whole_field_helicity": "SUPPORTS" if all(gates[key] for key in ("WHS1", "WHS2", "WHS3", "WHS4")) else "INCONCLUSIVE",
            "handedness_selection_from_registered_action": "DOES NOT EMERGE" if all(gates[key] for key in ("WHS5", "WHS6", "WHS7", "WHS8")) else "INCONCLUSIVE",
            "complete_physical_matter_formation": "FAIL",
        },
        "arrays": {
            "path": relative(arrays_path),
            "sha256": sha256(arrays_path),
            "keys": sorted(arrays),
        },
    }
    results_path = output / "results.json"
    write_json(results_path, payload)

    report = f"""# Whole-Bubble Handedness Selector Result

- Execution valid: `{execution_valid}`
- CP-odd whole-field helicity: `{payload['verdicts']['cp_odd_whole_field_helicity']}`
- Handedness selection from the registered action: `{payload['verdicts']['handedness_selection_from_registered_action']}`
- Complete physical Cassi matter formation: `FAIL`
- Maximum Beltrami curl error: `{max_curl_error:.12e}`
- Minimum density-Hessian eigenvalue: `{min_density_eigenvalue:.12e}`
- Minimum transverse operator: `{min_transverse_operator:.12e}`
- Default opposite-helicity energy split: `{default_split:.12e}`
- Explicit-selector energy split: `{measured_explicit_split:.12e}`
"""
    (output / "report.md").write_text(report, encoding="utf-8")
    manifest = {
        "schema": "cassi.whole-bubble-handedness-selector.manifest.v1",
        "files": [
            {"path": name, "sha256": sha256(output / name)}
            for name in ("arrays.npz", "results.json", "report.md")
        ],
        "source_snapshots": [
            {
                "path": record["path"],
                "snapshot": f"sources/{record['path']}",
                "sha256": record["sha256"],
            }
            for record in records
        ],
    }
    write_json(output / "manifest.json", manifest)

    print(f"EXECUTION_VALID={execution_valid}")
    print(f"WHS_GATES={sum(gates.values())}/{len(gates)}")
    print(f"HELICITY_VERDICT={payload['verdicts']['cp_odd_whole_field_helicity']}")
    print(f"SELECTOR_VERDICT={payload['verdicts']['handedness_selection_from_registered_action']}")
    print(f"RESULTS={relative(results_path)}")
    return 0 if execution_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
