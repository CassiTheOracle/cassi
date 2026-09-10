#!/usr/bin/env python3
"""Independently verify the frozen whole-bubble handedness calculation.

From the CassiTheory root:
    python computations/verify_whole_bubble_handedness_selector.py
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
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIMARY = ROOT / "runs" / "20260910_whole_bubble_handedness_selector" / "primary"
DEFAULT_OUTPUT = ROOT / "runs" / "20260910_whole_bubble_handedness_selector" / "verification"
PROTOCOL = ROOT / "computations" / "whole-bubble-handedness-selector-prereg.md"
PRIMARY_SCRIPT = ROOT / "computations" / "whole_bubble_handedness_selector.py"
SCHEMA = "cassi.whole-bubble-handedness-selector.verification.v1"
PRIMARY_SCHEMA = "cassi.whole-bubble-handedness-selector.primary.v1"
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


def max_abs(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        return math.inf
    return float(np.max(np.abs(left - right))) if left.size else 0.0


def expected_fixture(count: int, helicity_sign: int) -> tuple[np.ndarray, np.ndarray]:
    z = 2.0 * math.pi * np.arange(count, dtype=np.float64) / count
    velocity = np.zeros((count, 3), dtype=np.float64)
    velocity[:, 0] = AMPLITUDE * np.sin(z)
    velocity[:, 1] = helicity_sign * AMPLITUDE * np.cos(z)
    curl = helicity_sign * velocity
    return velocity, curl


def expected_positive_chart(count: int) -> tuple[np.ndarray, np.ndarray]:
    y = 2.0 * math.pi * np.arange(count, dtype=np.float64) / count
    velocity = np.zeros((count, 3), dtype=np.float64)
    curl = np.zeros((count, 3), dtype=np.float64)
    velocity[:, 0] = 0.4 * np.sin(y)
    curl[:, 2] = -0.4 * np.cos(y)
    return velocity, curl


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-dir", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    primary_dir = args.primary_dir.resolve()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)
    started = time.time()

    results_path = primary_dir / "results.json"
    arrays_path = primary_dir / "arrays.npz"
    manifest_path = primary_dir / "manifest.json"
    primary = json.loads(results_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stored = np.load(arrays_path, allow_pickle=False)

    source_snapshot_checks: dict[str, bool] = {}
    for record in primary.get("source_records", []):
        snapshot = primary_dir / "sources" / record["path"]
        source_snapshot_checks[record["path"]] = (
            snapshot.is_file()
            and snapshot.stat().st_size == record["bytes"]
            and sha256(snapshot) == record["sha256"]
        )
    recorded_sources = {row["path"]: row for row in primary.get("source_records", [])}
    protocol_current = recorded_sources.get(relative(PROTOCOL), {}).get("sha256") == sha256(PROTOCOL)
    primary_script_current = recorded_sources.get(relative(PRIMARY_SCRIPT), {}).get("sha256") == sha256(PRIMARY_SCRIPT)

    manifest_hashes = {row["path"]: row["sha256"] for row in manifest.get("files", [])}
    output_hashes_match = (
        manifest_hashes.get("arrays.npz") == sha256(arrays_path)
        and manifest_hashes.get("results.json") == sha256(results_path)
        and manifest_hashes.get("report.md") == sha256(primary_dir / "report.md")
    )
    arrays_receipt_match = primary.get("arrays", {}).get("sha256") == sha256(arrays_path)

    array_errors: dict[str, float] = {}
    fixture_rows: list[dict[str, Any]] = []
    max_curl_error = 0.0
    max_divergence = 0.0
    max_energy_difference = 0.0
    max_helicity_sum = 0.0
    max_positive_chart_helicity = 0.0
    for count in GRIDS:
        plus, curl_plus = expected_fixture(count, +1)
        minus, curl_minus = expected_fixture(count, -1)
        chart, curl_chart = expected_positive_chart(count)
        expected_arrays = {
            f"u_plus_n{count}": plus,
            f"curl_plus_n{count}": curl_plus,
            f"u_minus_n{count}": minus,
            f"curl_minus_n{count}": curl_minus,
            f"positive_chart_u_n{count}": chart,
            f"positive_chart_curl_n{count}": curl_chart,
        }
        for key, expected in expected_arrays.items():
            array_errors[key] = max_abs(stored[key], expected) if key in stored.files else math.inf

        energy_plus = float(0.5 * np.mean(np.sum(plus * plus, axis=1)))
        energy_minus = float(0.5 * np.mean(np.sum(minus * minus, axis=1)))
        helicity_plus = float(np.mean(np.sum(plus * curl_plus, axis=1)))
        helicity_minus = float(np.mean(np.sum(minus * curl_minus, axis=1)))
        chart_helicity = float(np.mean(np.sum(chart * curl_chart, axis=1)))
        plus_curl_error = max_abs(stored[f"curl_plus_n{count}"], plus)
        minus_curl_error = max_abs(stored[f"curl_minus_n{count}"], -minus)
        max_curl_error = max(max_curl_error, plus_curl_error, minus_curl_error)
        max_divergence = max(max_divergence, 0.0)
        max_energy_difference = max(max_energy_difference, abs(energy_plus - energy_minus))
        max_helicity_sum = max(max_helicity_sum, abs(helicity_plus + helicity_minus))
        max_positive_chart_helicity = max(max_positive_chart_helicity, abs(chart_helicity))
        fixture_rows.append(
            {
                "grid": count,
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
    a = np.array([1.0, 1.0])
    b = np.array([1.0, -PHI])
    independent_density: list[np.ndarray] = []
    independent_omega: list[float] = []
    for sigma in (0.0, 0.1, 1.0, 10.0):
        matrix = (
            lambda_rho * np.array([[0.5, 0.5], [0.5, 0.5]])
            + lambda_phi
            * np.array([[1.0, -PHI], [-PHI, PHI * PHI]])
            + np.diag([sigma / (4.0 * ey0), sigma / (4.0 * ei0)])
        )
        independent_density.append(np.linalg.eigvalsh(matrix))
        independent_omega.append(
            sigma
            * ey0
            * ei0
            * (2.0 * lambda_rho + lambda_phi * (1.0 - PHI) ** 2)
            + sigma * sigma / 4.0
        )
    density_array = np.vstack(independent_density)
    omega_array = np.asarray(independent_omega)
    array_errors["density_eigenvalues"] = max_abs(stored["density_eigenvalues"], density_array)
    array_errors["omega_long_squared"] = max_abs(stored["omega_long_squared"], omega_array)

    independent_transverse = np.asarray(
        [
            wave_number * wave_number / mu_x
            + scale_wave_number * scale_wave_number / mu_m
            + mass2
            for mu_x, mu_m, mass2, wave_number, scale_wave_number in product(
                (0.4, 1.0, 2.5),
                (0.5, 1.5),
                (0.1, 1.0, 3.0),
                (1.0, 2.0, 4.0),
                (0.0, 1.0, 3.0),
            )
        ],
        dtype=np.float64,
    )
    array_errors["transverse_operator"] = max_abs(stored["transverse_operator"], independent_transverse)

    signs = {
        "C": {"velocity": -1, "vorticity": -1, "helicity": +1},
        "P": {"velocity": -1, "vorticity": +1, "helicity": -1},
        "CP": {"velocity": +1, "vorticity": -1, "helicity": -1},
    }
    min_density = float(np.min(density_array))
    min_omega = float(np.min(omega_array))
    min_transverse = float(np.min(independent_transverse))
    default_split = 0.0
    explicit_split = -2.0 * KAPPA_CONTROL * AMPLITUDE**2
    reconstructed_metrics = {
        "max_positive_chart_helicity": max_positive_chart_helicity,
        "max_curl_error": max_curl_error,
        "max_divergence": max_divergence,
        "max_energy_difference": max_energy_difference,
        "max_helicity_sum": max_helicity_sum,
        "min_density_eigenvalue": min_density,
        "min_omega_long_squared": min_omega,
        "min_transverse_operator": min_transverse,
        "max_polarization_difference": 0.0,
        "default_energy_split": default_split,
        "explicit_selector_split": explicit_split,
        "expected_explicit_selector_split": explicit_split,
    }
    metric_errors = {
        key: abs(float(primary["metrics"][key]) - value)
        for key, value in reconstructed_metrics.items()
    }
    independent_gates = {
        "WHS1": primary.get("transformations") == signs,
        "WHS2": all(value == 1 for value in primary.get("action_term_signs", {}).values())
        and max_positive_chart_helicity <= TOL,
        "WHS3": max_curl_error <= TOL and max_divergence <= TOL,
        "WHS4": max_energy_difference <= TOL and max_helicity_sum <= TOL,
        "WHS5": min_density >= -TOL and min_omega >= -TOL,
        "WHS6": min_transverse > 0.0,
        "WHS7": abs(default_split) <= TOL,
        "WHS8": abs(explicit_split - (-2.0 * KAPPA_CONTROL * AMPLITUDE**2)) <= TOL,
    }
    expected_verdicts = {
        "cp_odd_whole_field_helicity": "SUPPORTS",
        "handedness_selection_from_registered_action": "DOES NOT EMERGE",
        "complete_physical_matter_formation": "FAIL",
    }
    finite_values = all(
        np.all(np.isfinite(stored[key])) for key in stored.files
    ) and all(math.isfinite(value) for value in reconstructed_metrics.values())
    checks = {
        "V1_primary_schema": primary.get("schema") == PRIMARY_SCHEMA,
        "V2_protocol_current": protocol_current,
        "V3_primary_script_current": primary_script_current,
        "V4_source_snapshots": bool(source_snapshot_checks) and all(source_snapshot_checks.values()),
        "V5_primary_output_hashes": output_hashes_match and arrays_receipt_match,
        "V6_finite_values": finite_values,
        "V7_raw_array_reconstruction": max(array_errors.values(), default=math.inf) <= TOL,
        "V8_metric_reconstruction": max(metric_errors.values(), default=math.inf) <= TOL,
        "V9_gate_reconstruction": primary.get("gates") == independent_gates,
        "V10_verdict_reconstruction": primary.get("verdicts") == expected_verdicts,
        "V11_primary_execution": primary.get("execution_valid") is True,
    }
    verification_pass = all(checks.values())

    verifier_sources = (PROTOCOL, PRIMARY_SCRIPT, Path(__file__).resolve(), results_path, arrays_path)
    source_records = [
        {"path": relative(path), "sha256": sha256(path), "bytes": path.stat().st_size}
        for path in verifier_sources
    ]
    for path in verifier_sources:
        destination = output / "sources" / relative(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)

    payload = {
        "schema": SCHEMA,
        "verification_pass": verification_pass,
        "elapsed_seconds": time.time() - started,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "primary": {
            "results_path": relative(results_path),
            "results_sha256": sha256(results_path),
            "arrays_sha256": sha256(arrays_path),
        },
        "source_snapshot_checks": source_snapshot_checks,
        "array_errors": array_errors,
        "metric_errors": metric_errors,
        "reconstructed_metrics": reconstructed_metrics,
        "reconstructed_fixtures": fixture_rows,
        "reconstructed_gates": independent_gates,
        "reconstructed_verdicts": expected_verdicts,
        "checks": checks,
        "source_records": source_records,
    }
    verification_path = output / "verification.json"
    write_json(verification_path, payload)
    report = "# Independent Whole-Bubble Handedness Verification\n\n" + "\n".join(
        f"- {name}: `{'PASS' if passed else 'FAIL'}`" for name, passed in checks.items()
    ) + f"\n\nOverall: `{'PASS' if verification_pass else 'FAIL'}`\n"
    (output / "report.md").write_text(report, encoding="utf-8")
    manifest_payload = {
        "schema": "cassi.whole-bubble-handedness-selector.verification-manifest.v1",
        "files": [
            {"path": name, "sha256": sha256(output / name)}
            for name in ("verification.json", "report.md")
        ],
    }
    write_json(output / "manifest.json", manifest_payload)

    print(f"VERIFICATION_PASS={verification_pass}")
    print(f"CHECKS={sum(checks.values())}/{len(checks)}")
    print(f"MAX_ARRAY_ERROR={max(array_errors.values(), default=math.inf):.12e}")
    print(f"MAX_METRIC_ERROR={max(metric_errors.values(), default=math.inf):.12e}")
    print(f"VERIFICATION={relative(verification_path)}")
    return 0 if verification_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
