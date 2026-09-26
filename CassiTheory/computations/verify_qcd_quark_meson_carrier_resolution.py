#!/usr/bin/env python3
"""Independently verify the frozen quark–meson resolution qualification.

Run from the CassiTheory root:
    python computations/verify_qcd_quark_meson_carrier_resolution.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "qcd-quark-meson-carrier-qualification-prereg.md"
UPSTREAM_PRIMARY = (
    ROOT
    / "runs"
    / "20260910_qcd_quark_meson_carrier"
    / "amendment-2"
    / "primary"
    / "results.json"
)
UPSTREAM_INDEPENDENT = (
    ROOT
    / "runs"
    / "20260910_qcd_quark_meson_carrier"
    / "amendment-2"
    / "verification"
    / "verification.json"
)
DEFAULT_INPUT = (
    ROOT
    / "runs"
    / "20260910_qcd_quark_meson_carrier"
    / "qualification"
    / "primary"
    / "results.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "20260910_qcd_quark_meson_carrier"
    / "qualification"
    / "verification"
)
SCHEMA = "cassi.qcd-quark-meson-carrier-resolution.verification.v1"
PRIMARY_SCHEMA = "cassi.qcd-quark-meson-carrier-resolution.primary.v1"
M_Q = 500.0
GRIDS = np.array([1200, 2400, 4800, 9600], dtype=np.int64)
ENDPOINT_RADIUS = 0.5368112726086816
EXPECTED_INPUT_HASHES = {
    "runs/20260910_qcd_quark_meson_carrier/amendment-2/primary/results.json": "6f067ee37527ccf04c562a5345331ee84d9cc2d6102c3cd997ff1624c3e14870",
    "runs/20260910_qcd_quark_meson_carrier/amendment-2/primary/arrays.npz": "0e9e5458f4f659fe92574951c1780120ed41973bb520eb41b38bd12410586abe",
    "runs/20260910_qcd_quark_meson_carrier/amendment-2/verification/verification.json": "59e18ba7208ad94a4997e6b36b4b9364bdabd78e676613dfc075eb2e4f357c76",
    "runs/20260910_qcd_quark_meson_carrier/amendment-2/verification/verification_arrays.npz": "e568846985cc4f3ea03ad7c557a16a518170806d3baa5bcfcad354dc737f01a3",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256_bytes(data),
        "bytes": len(data),
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(json_ready(payload), indent=2, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def require_close(name: str, actual: float, recorded: float, tolerance: float) -> None:
    if not math.isfinite(actual) or not math.isfinite(recorded):
        raise RuntimeError(f"{name}: nonfinite value")
    if abs(actual - recorded) > tolerance:
        raise RuntimeError(
            f"{name}: reconstructed {actual:.17g}, recorded {recorded:.17g}"
        )


def reconstruct_fit(grid_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if [int(row["n"]) for row in grid_rows] != GRIDS.tolist():
        raise RuntimeError("grid sequence differs from protocol")
    n_values = np.array([row["n"] for row in grid_rows], dtype=np.float64)
    energies = np.array([row["energy_mev"] for row in grid_rows], dtype=np.float64)
    inverse = 1.0 / n_values
    design = np.column_stack((np.ones(4), inverse, inverse**2))
    coefficients, _, _, _ = np.linalg.lstsq(design, energies, rcond=None)
    predicted = design @ coefficients
    residuals = energies - predicted
    rms = math.sqrt(float(np.mean(residuals**2)))
    last_inverse = inverse[-3:]
    last_design = np.column_stack(
        (np.ones(3), last_inverse, last_inverse**2)
    )
    last_coefficients = np.linalg.solve(last_design, energies[-3:])
    intercept_difference = abs(float(coefficients[0] - last_coefficients[0]))
    uncertainty = max(0.20, 2.0 * intercept_difference, 2.0 * rms)
    biases = energies - coefficients[0]
    return {
        "n": n_values,
        "inverse_n": inverse,
        "energies_mev": energies,
        "four_point_coefficients": {
            "e_infinity_mev": float(coefficients[0]),
            "c1_mev": float(coefficients[1]),
            "c2_mev": float(coefficients[2]),
        },
        "four_point_predicted_mev": predicted,
        "four_point_residuals_mev": residuals,
        "four_point_rms_mev": rms,
        "last_three_coefficients": {
            "e_infinity_mev": float(last_coefficients[0]),
            "c1_mev": float(last_coefficients[1]),
            "c2_mev": float(last_coefficients[2]),
        },
        "intercept_difference_mev": intercept_difference,
        "uncertainty_mev": uncertainty,
        "biases_mev": biases,
        "constant_bias_sign": bool(np.all(biases > 0.0) or np.all(biases < 0.0)),
    }


def compare_fit(name: str, reconstructed: dict[str, Any], recorded: dict[str, Any]) -> None:
    require_close(
        f"{name}.four_e_infinity",
        reconstructed["four_point_coefficients"]["e_infinity_mev"],
        float(recorded["four_point_coefficients"]["e_infinity_mev"]),
        1.0e-10,
    )
    require_close(
        f"{name}.four_c1",
        reconstructed["four_point_coefficients"]["c1_mev"],
        float(recorded["four_point_coefficients"]["c1_mev"]),
        1.0e-6,
    )
    require_close(
        f"{name}.four_c2",
        reconstructed["four_point_coefficients"]["c2_mev"],
        float(recorded["four_point_coefficients"]["c2_mev"]),
        1.0e-3,
    )
    require_close(
        f"{name}.rms",
        reconstructed["four_point_rms_mev"],
        float(recorded["four_point_rms_mev"]),
        1.0e-12,
    )
    require_close(
        f"{name}.last_e_infinity",
        reconstructed["last_three_coefficients"]["e_infinity_mev"],
        float(recorded["last_three_coefficients"]["e_infinity_mev"]),
        1.0e-10,
    )
    require_close(
        f"{name}.intercept_difference",
        reconstructed["intercept_difference_mev"],
        float(recorded["intercept_difference_mev"]),
        1.0e-10,
    )
    require_close(
        f"{name}.uncertainty",
        reconstructed["uncertainty_mev"],
        float(recorded["uncertainty_mev"]),
        1.0e-10,
    )
    if reconstructed["constant_bias_sign"] is not recorded["constant_bias_sign"]:
        raise RuntimeError(f"{name}.constant_bias_sign differs")


def reconstruct_pairs(section: dict[str, Any], coordinate: str) -> dict[str, Any]:
    overlaps = section["adjacent_bound_branch_overlaps"]
    rows = section["rows"]
    pairs: list[dict[str, Any]] = []
    cursor = 0
    previous_bound_index: int | None = None
    for index, row in enumerate(rows):
        if not row["bound_state"]:
            previous_bound_index = None
            continue
        if previous_bound_index is not None:
            if cursor >= len(overlaps):
                raise RuntimeError("upstream overlap list is truncated")
            previous = rows[previous_bound_index]
            overlap = float(overlaps[cursor])
            cursor += 1
            if (
                abs(float(previous["level_mev"])) <= 0.999 * M_Q
                and abs(float(row["level_mev"])) <= 0.999 * M_Q
            ):
                pairs.append(
                    {
                        "left": float(previous[coordinate]),
                        "right": float(row[coordinate]),
                        "left_energy_mev": float(previous["level_mev"]),
                        "right_energy_mev": float(row["level_mev"]),
                        "overlap": overlap,
                    }
                )
        previous_bound_index = index
    if cursor != len(overlaps):
        raise RuntimeError("upstream overlap list has unused entries")
    return {
        "independent_energy_window_mev": [-0.999 * M_Q, 0.999 * M_Q],
        "pairs": pairs,
        "minimum_overlap": min(row["overlap"] for row in pairs),
    }


def compare_pairs(name: str, actual: dict[str, Any], recorded: dict[str, Any]) -> None:
    if len(actual["pairs"]) != len(recorded["pairs"]):
        raise RuntimeError(f"{name}: resolved pair count differs")
    for index, (left, right) in enumerate(zip(actual["pairs"], recorded["pairs"])):
        if left != right:
            raise RuntimeError(f"{name}: pair {index} differs")
    require_close(
        f"{name}.minimum_overlap",
        actual["minimum_overlap"],
        float(recorded["minimum_overlap"]),
        0.0,
    )


def verify(input_path: Path, output_dir: Path) -> int:
    input_path = input_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite evidence in {output_dir}")
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    primary = json.loads(input_path.read_text(encoding="utf-8"))
    if primary.get("schema") != PRIMARY_SCHEMA or not primary.get("completed"):
        raise RuntimeError("primary receipt is incomplete or has the wrong schema")
    if primary.get("failure") is not None:
        raise RuntimeError("primary receipt records a failure")

    protocol_identity = identity(PROTOCOL)
    if primary["protocol"] != protocol_identity:
        raise RuntimeError("live protocol identity differs from primary receipt")
    source_identity = primary["sources"]["primary"]
    primary_source = ROOT / source_identity["path"]
    if identity(primary_source) != source_identity:
        raise RuntimeError("live primary source identity differs from receipt")
    for snapshot in primary["sources"]["snapshots"]:
        snapshot_path = ROOT / snapshot["path"]
        if identity(snapshot_path) != snapshot:
            raise RuntimeError(f"source snapshot mismatch: {snapshot['path']}")
    immutable_identities = {
        row["path"]: row for row in primary["sources"]["immutable_inputs"]
    }
    for relative, expected_hash in EXPECTED_INPUT_HASHES.items():
        live = identity(ROOT / relative)
        if live["sha256"] != expected_hash:
            raise RuntimeError(f"immutable live input mismatch: {relative}")
        if immutable_identities.get(relative) != live:
            raise RuntimeError(f"immutable receipt identity mismatch: {relative}")

    upstream_primary = json.loads(UPSTREAM_PRIMARY.read_text(encoding="utf-8"))
    upstream_independent = json.loads(
        UPSTREAM_INDEPENDENT.read_text(encoding="utf-8")
    )
    if primary["upstream_verdicts"]["qmc"] != upstream_independent["verdicts"]:
        raise RuntimeError("upstream QMC verdict copy differs")
    if primary["upstream_verdicts"]["complete_physical_matter_formation"] is not False:
        raise RuntimeError("upstream physical-completion value differs")

    arrays_identity = primary["artifacts"]["arrays"]
    arrays_path = ROOT / arrays_identity["path"]
    if identity(arrays_path) != arrays_identity:
        raise RuntimeError("primary array identity differs")
    arrays = np.load(arrays_path, allow_pickle=False)

    endpoint_reconstruction = reconstruct_fit(primary["endpoint"]["grid_rows"])
    compare_fit("endpoint", endpoint_reconstruction, primary["endpoint"]["fit"])
    envelope_reconstructions: list[dict[str, Any]] = []
    for row in primary["formation_envelope"]["rows"]:
        label = f"a{int(round(float(row['a']) * 100)):03d}"
        reconstructed = reconstruct_fit(row["grid_rows"])
        compare_fit(label, reconstructed, row["fit"])
        np.testing.assert_array_equal(arrays[f"{label}_n"], GRIDS)
        np.testing.assert_allclose(
            arrays[f"{label}_energy_mev"],
            reconstructed["energies_mev"],
            rtol=0.0,
            atol=0.0,
        )
        continuum_total = (
            3.0 * reconstructed["four_point_coefficients"]["e_infinity_mev"]
            + float(row["meson_mev"])
        )
        continuum_excess = continuum_total - 3.0 * M_Q
        upper_excess = continuum_excess + 3.0 * reconstructed["uncertainty_mev"]
        require_close(
            f"{label}.continuum_total", continuum_total, row["continuum_total_mev"], 1.0e-10
        )
        require_close(
            f"{label}.continuum_excess", continuum_excess, row["continuum_excess_mev"], 1.0e-10
        )
        require_close(
            f"{label}.upper_excess", upper_excess, row["upper_excess_mev"], 1.0e-10
        )
        envelope_reconstructions.append(
            {
                "a": float(row["a"]),
                "fit": reconstructed,
                "continuum_total_mev": continuum_total,
                "continuum_excess_mev": continuum_excess,
                "upper_excess_mev": upper_excess,
            }
        )

    endpoint_e = endpoint_reconstruction["four_point_coefficients"]["e_infinity_mev"]
    endpoint_meson = float(upstream_primary["measurements"]["selected_meson_mev"])
    endpoint_total = 3.0 * endpoint_e + endpoint_meson
    endpoint_binding = 3.0 * M_Q - endpoint_total
    endpoint_uncertainty = endpoint_reconstruction["uncertainty_mev"]
    qualified_binding = endpoint_binding - 3.0 * endpoint_uncertainty
    require_close("endpoint.level", endpoint_e, primary["endpoint"]["continuum_level_mev"], 1.0e-10)
    require_close("endpoint.meson", endpoint_meson, primary["endpoint"]["continuum_meson_mev"], 0.0)
    require_close("endpoint.total", endpoint_total, primary["endpoint"]["continuum_total_mev"], 1.0e-10)
    require_close("endpoint.binding", endpoint_binding, primary["endpoint"]["continuum_binding_margin_mev"], 1.0e-10)
    require_close("endpoint.qualified_binding", qualified_binding, primary["endpoint"]["qualified_binding_margin_mev"], 1.0e-10)

    shooting_energy = float(
        upstream_independent["measurements"]["independent_endpoint_level_mev"]
    )
    shooting_total = float(
        upstream_independent["measurements"]["independent_endpoint_total_mev"]
    )
    shooting_radius = float(
        upstream_independent["independent_radius_reconstruction"]["selected_radius_fm"]
    )
    shooting_rms = float(
        upstream_independent["measurements"]["independent_endpoint_rms_fm"]
    )
    upstream_copies = {
        "independent_shooting_level_mev": shooting_energy,
        "independent_shooting_total_mev": shooting_total,
        "independent_selected_radius_fm": shooting_radius,
        "independent_rms_fm": shooting_rms,
    }
    for key, value in upstream_copies.items():
        require_close(f"endpoint.{key}", value, float(primary["endpoint"][key]), 0.0)

    radius_pairs = reconstruct_pairs(upstream_primary["endpoint_radius_scan"], "radius_fm")
    amplitude_pairs = reconstruct_pairs(upstream_primary["fixed_radius_amplitude_scan"], "a")
    compare_pairs(
        "radius_pairs", radius_pairs, primary["resolved_branch_overlap"]["radius_scan"]
    )
    compare_pairs(
        "amplitude_pairs",
        amplitude_pairs,
        primary["resolved_branch_overlap"]["amplitude_scan"],
    )

    barrier = max(
        0.0, max(row["continuum_excess_mev"] for row in envelope_reconstructions)
    )
    upper_barrier = max(
        0.0, max(row["upper_excess_mev"] for row in envelope_reconstructions)
    )
    require_close(
        "formation.barrier",
        barrier,
        primary["formation_envelope"]["reconstructed_barrier_mev"],
        1.0e-10,
    )
    require_close(
        "formation.upper_barrier",
        upper_barrier,
        primary["formation_envelope"]["conservative_upper_barrier_mev"],
        1.0e-10,
    )

    all_spectra_finite = all(
        math.isfinite(float(grid_row["energy_mev"]))
        and int(grid_row["nodes_h"]) == 0
        and float(grid_row["symmetry_error"]) < 1.0e-10
        for row in primary["formation_envelope"]["rows"]
        for grid_row in row["grid_rows"]
    )
    fits_rms_pass = all(
        row["fit"]["four_point_rms_mev"] < 0.10
        for row in envelope_reconstructions
    )
    intercepts_pass = all(
        row["fit"]["intercept_difference_mev"] < 0.20
        for row in envelope_reconstructions
    )
    qmq1_inputs = {
        "all_spectra_finite_nodeless_symmetric": all_spectra_finite,
        "all_four_point_rms_below_0p10_mev": fits_rms_pass,
        "all_intercept_differences_below_0p20_mev": intercepts_pass,
        "endpoint_shooting_absolute_difference_mev": abs(endpoint_e - shooting_energy),
        "endpoint_total_absolute_difference_mev": abs(endpoint_total - shooting_total),
        "endpoint_constant_bias_sign": endpoint_reconstruction["constant_bias_sign"],
    }
    if qmq1_inputs != primary["gate_inputs"]["QMQ1"]:
        raise RuntimeError("QMQ1 gate inputs differ")
    qmq1_pass = bool(
        all_spectra_finite
        and fits_rms_pass
        and intercepts_pass
        and qmq1_inputs["endpoint_shooting_absolute_difference_mev"] <= 0.50
        and qmq1_inputs["endpoint_total_absolute_difference_mev"] <= 2.0
        and endpoint_reconstruction["constant_bias_sign"]
    )
    qmq2_inputs = {
        "qmq1_pass": qmq1_pass,
        "minimum_radius_overlap": radius_pairs["minimum_overlap"],
        "minimum_amplitude_overlap": amplitude_pairs["minimum_overlap"],
        "qualified_binding_margin_mev": qualified_binding,
        "radius_absolute_difference_fm": abs(shooting_radius - ENDPOINT_RADIUS),
        "independent_rms_fm": shooting_rms,
    }
    if qmq2_inputs != primary["gate_inputs"]["QMQ2"]:
        raise RuntimeError("QMQ2 gate inputs differ")
    qmq2_supports = bool(
        qmq1_pass
        and radius_pairs["minimum_overlap"] > 0.70
        and amplitude_pairs["minimum_overlap"] > 0.70
        and qualified_binding > 5.0
        and abs(shooting_radius - ENDPOINT_RADIUS) <= 0.02
        and 0.2 <= shooting_rms <= 1.5
    )
    if qmq2_supports:
        qmq2 = "SUPPORTS"
    elif endpoint_total + 3.0 * endpoint_uncertainty >= 3.0 * M_Q:
        qmq2 = "CONTRADICTS"
    else:
        qmq2 = "INCONCLUSIVE"
    if qmq2 == "SUPPORTS" and upper_barrier <= 155.0:
        qmq3 = "SUPPORTS"
    elif qmq2 == "CONTRADICTS":
        qmq3 = "CONTRADICTS"
    else:
        qmq3 = "INCONCLUSIVE"
    verdicts = {
        "QMQ1": "PASS" if qmq1_pass else "FAIL",
        "QMQ2": qmq2,
        "QMQ3": qmq3,
        "QMQ4": "FAIL",
    }
    if verdicts != primary["verdicts"]:
        raise RuntimeError("verdict reconstruction differs")
    if primary["complete_physical_matter_formation"] is not False:
        raise RuntimeError("primary physical-completion field is not false")

    output_dir.mkdir(parents=True)
    source_dir = output_dir / "sources"
    source_dir.mkdir()
    shutil.copy2(PROTOCOL, source_dir / PROTOCOL.name)
    shutil.copy2(SELF, source_dir / SELF.name)
    shutil.copy2(input_path, source_dir / "primary_results.json")
    shutil.copy2(arrays_path, source_dir / "primary_resolution_arrays.npz")

    verification_arrays_path = output_dir / "verification_arrays.npz"
    np.savez_compressed(
        verification_arrays_path,
        a=np.array([row["a"] for row in envelope_reconstructions]),
        continuum_total_mev=np.array(
            [row["continuum_total_mev"] for row in envelope_reconstructions]
        ),
        continuum_excess_mev=np.array(
            [row["continuum_excess_mev"] for row in envelope_reconstructions]
        ),
        upper_excess_mev=np.array(
            [row["upper_excess_mev"] for row in envelope_reconstructions]
        ),
        radius_pair_overlaps=np.array(
            [row["overlap"] for row in radius_pairs["pairs"]]
        ),
        amplitude_pair_overlaps=np.array(
            [row["overlap"] for row in amplitude_pairs["pairs"]]
        ),
    )
    result = {
        "schema": SCHEMA,
        "completed": True,
        "scientific_execution_started": True,
        "protocol": protocol_identity,
        "primary_receipt": identity(input_path),
        "primary_arrays": identity(arrays_path),
        "sources": {
            "verifier": identity(SELF),
            "snapshots": [identity(path) for path in source_dir.rglob("*") if path.is_file()],
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
            "executable": sys.executable,
        },
        "endpoint_reconstruction": {
            "fit": endpoint_reconstruction,
            "continuum_level_mev": endpoint_e,
            "continuum_total_mev": endpoint_total,
            "continuum_binding_margin_mev": endpoint_binding,
            "qualified_binding_margin_mev": qualified_binding,
            **upstream_copies,
        },
        "resolved_branch_overlap": {
            "radius_scan": radius_pairs,
            "amplitude_scan": amplitude_pairs,
        },
        "formation_reconstruction": {
            "rows": envelope_reconstructions,
            "reconstructed_barrier_mev": barrier,
            "conservative_upper_barrier_mev": upper_barrier,
            "threshold_mev": 155.0,
        },
        "gate_inputs": {
            "QMQ1": qmq1_inputs,
            "QMQ2": qmq2_inputs,
            "QMQ3": {
                "qmq2": qmq2,
                "conservative_upper_barrier_mev": upper_barrier,
                "threshold_mev": 155.0,
            },
            "QMQ4": primary["gate_inputs"]["QMQ4"],
        },
        "verdicts": verdicts,
        "exact_verdict_agreement": True,
        "complete_physical_matter_formation": False,
        "artifacts": {
            "arrays": identity(verification_arrays_path),
        },
        "failure": None,
    }
    result_path = output_dir / "verification.json"
    write_json(result_path, result)
    print(
        json.dumps(
            {
                "result": result_path.relative_to(ROOT).as_posix(),
                "endpoint_continuum_level_mev": endpoint_e,
                "endpoint_shooting_difference_mev": abs(endpoint_e - shooting_energy),
                "qualified_binding_margin_mev": qualified_binding,
                "resolved_overlap_minima": {
                    "radius": radius_pairs["minimum_overlap"],
                    "amplitude": amplitude_pairs["minimum_overlap"],
                },
                "reconstructed_barrier_mev": barrier,
                "conservative_upper_barrier_mev": upper_barrier,
                "verdicts": verdicts,
                "exact_verdict_agreement": True,
                "complete_physical_matter_formation": False,
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0 if verdicts["QMQ1"] == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    try:
        raise SystemExit(verify(arguments.input, arguments.output_dir))
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise
