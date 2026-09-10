#!/usr/bin/env python3
"""Qualify the vanishing-Wilson sequence in the quark–meson carrier calculation.

Run from the CassiTheory root:
    python computations/qcd_quark_meson_carrier_resolution.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np
import scipy
from scipy import sparse
from scipy.sparse import linalg as spla


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "qcd-quark-meson-carrier-qualification-prereg.md"
PRIMARY_RECEIPT = (
    ROOT
    / "runs"
    / "20260910_qcd_quark_meson_carrier"
    / "amendment-2"
    / "primary"
    / "results.json"
)
PRIMARY_ARRAYS = PRIMARY_RECEIPT.with_name("arrays.npz")
INDEPENDENT_RECEIPT = (
    ROOT
    / "runs"
    / "20260910_qcd_quark_meson_carrier"
    / "amendment-2"
    / "verification"
    / "verification.json"
)
INDEPENDENT_ARRAYS = INDEPENDENT_RECEIPT.with_name("verification_arrays.npz")
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "20260910_qcd_quark_meson_carrier"
    / "qualification"
    / "primary"
)
SCHEMA = "cassi.qcd-quark-meson-carrier-resolution.primary.v1"
EXPECTED_INPUT_HASHES = {
    PRIMARY_RECEIPT: "6f067ee37527ccf04c562a5345331ee84d9cc2d6102c3cd997ff1624c3e14870",
    PRIMARY_ARRAYS: "0e9e5458f4f659fe92574951c1780120ed41973bb520eb41b38bd12410586abe",
    INDEPENDENT_RECEIPT: "59e18ba7208ad94a4997e6b36b4b9364bdabd78e676613dfc075eb2e4f357c76",
    INDEPENDENT_ARRAYS: "e568846985cc4f3ea03ad7c557a16a518170806d3baa5bcfcad354dc737f01a3",
}

HBARC = 197.3269804
F_PI = 93.0
M_PI = 139.6
M_SIGMA = 1200.0
M_Q = 500.0
LAMBDA = (M_SIGMA**2 - M_PI**2) / (2.0 * F_PI**2)
R_MAX = 12.0
GRIDS = np.array([1200, 2400, 4800, 9600], dtype=np.int64)
A_VALUES = np.round(np.arange(0.40, 1.0000001, 0.05), 12)
ENDPOINT_RADIUS = 0.5368112726086816


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


def profile(a: float, radius: float, radial: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    denominator = radial**4 + radius**4
    cosine = (radial**4 - radius**4) / denominator
    sine = 2.0 * radius**2 * radial**2 / denominator
    scalar = 1.0 - a + a * cosine
    pion = -a * sine
    return scalar, pion


def derivative_matrix(n: int, spacing: float) -> sparse.csr_matrix:
    derivative = sparse.lil_matrix((n, n), dtype=np.float64)
    derivative[0, 0] = -0.5 / spacing
    derivative[0, 1] = 0.5 / spacing
    indices = np.arange(1, n - 1)
    derivative[indices, indices - 1] = -0.5 / spacing
    derivative[indices, indices + 1] = 0.5 / spacing
    derivative[n - 1, n - 2] = -0.5 / spacing
    return derivative.tocsr()


def node_count(h: np.ndarray, probability: np.ndarray) -> int:
    cumulative = np.cumsum(probability)
    endpoint = int(np.searchsorted(cumulative, 0.999, side="left"))
    endpoint = max(2, min(endpoint, h.size - 1))
    peak = float(np.max(np.abs(h[: endpoint + 1])))
    mask = np.abs(h[: endpoint + 1]) > 1.0e-3 * peak
    signs = np.sign(h[: endpoint + 1][mask])
    return int(np.count_nonzero(signs[1:] * signs[:-1] < 0.0)) if signs.size > 1 else 0


def solve_level(a: float, radius: float, n: int) -> dict[str, Any]:
    spacing = R_MAX / n
    radial = (np.arange(n, dtype=np.float64) + 0.5) * spacing
    sqrt_weight = radial * math.sqrt(spacing)
    inverse_sqrt_weight = 1.0 / sqrt_weight
    derivative = derivative_matrix(n, spacing)
    transformed_derivative = (
        sparse.diags(sqrt_weight)
        @ derivative
        @ sparse.diags(inverse_sqrt_weight)
    )
    wilson = 0.5 * HBARC * spacing * (
        transformed_derivative.T @ transformed_derivative
    )
    scalar, pion = profile(a, radius, radial)
    mass = sparse.diags(M_Q * scalar) + wilson
    offdiagonal = HBARC * transformed_derivative - sparse.diags(M_Q * pion)
    hamiltonian = sparse.bmat(
        [[mass, offdiagonal.T], [offdiagonal, -mass]],
        format="csc",
        dtype=np.float64,
    )
    difference = hamiltonian - hamiltonian.T
    symmetry_error = float(np.max(np.abs(difference.data))) if difference.nnz else 0.0
    values, vectors = spla.eigsh(
        hamiltonian,
        k=12,
        sigma=1.0e-8,
        which="LM",
        tol=1.0e-11,
        maxiter=20000,
    )
    order = np.argsort(values)
    values = np.asarray(values[order], dtype=np.float64)
    vectors = np.asarray(vectors[:, order], dtype=np.float64)
    candidates: list[dict[str, Any]] = []
    for column, energy in enumerate(values):
        vector = vectors[:, column].copy()
        h = vector[:n] * inverse_sqrt_weight
        j = vector[n:] * inverse_sqrt_weight
        if h[0] < 0.0:
            vector *= -1.0
            h *= -1.0
            j *= -1.0
        probability = vector[:n] ** 2 + vector[n:] ** 2
        probability /= np.sum(probability)
        nodes = node_count(h, probability)
        if -M_Q < energy < M_Q and nodes == 0:
            candidates.append(
                {
                    "energy_mev": float(energy),
                    "nodes_h": nodes,
                    "rms_fm": math.sqrt(float(np.dot(probability, radial**2))),
                    "tail_probability_r_ge_8fm": float(
                        np.sum(probability[radial >= 8.0])
                    ),
                    "radial": radial,
                    "h": h,
                    "j": j,
                    "probability": probability,
                }
            )
    if not candidates:
        raise RuntimeError(f"no nodeless in-gap level at a={a}, R={radius}, N={n}")
    selected = min(candidates, key=lambda row: abs(row["energy_mev"]))
    return {
        "a": float(a),
        "radius_fm": float(radius),
        "n": int(n),
        "spacing_fm": float(spacing),
        "energy_mev": selected["energy_mev"],
        "nodes_h": selected["nodes_h"],
        "rms_fm": selected["rms_fm"],
        "tail_probability_r_ge_8fm": selected["tail_probability_r_ge_8fm"],
        "symmetry_error": symmetry_error,
        "eigenvalues_mev": values,
        "radial": selected["radial"],
        "h": selected["h"],
        "j": selected["j"],
        "probability": selected["probability"],
    }


def fit_sequence(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n_values = np.array([row["n"] for row in rows], dtype=np.float64)
    energies = np.array([row["energy_mev"] for row in rows], dtype=np.float64)
    inverse = 1.0 / n_values
    design = np.column_stack((np.ones_like(inverse), inverse, inverse**2))
    coefficients, _, _, _ = np.linalg.lstsq(design, energies, rcond=None)
    predicted = design @ coefficients
    residuals = energies - predicted
    rms = math.sqrt(float(np.mean(residuals**2)))

    last_inverse = inverse[-3:]
    last_design = np.column_stack(
        (np.ones_like(last_inverse), last_inverse, last_inverse**2)
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


def resolved_pairs(section: dict[str, Any], coordinate: str) -> dict[str, Any]:
    rows = section["rows"]
    overlaps = section["adjacent_bound_branch_overlaps"]
    pairs: list[dict[str, Any]] = []
    overlap_cursor = 0
    previous_bound_index: int | None = None
    for index, row in enumerate(rows):
        if not row["bound_state"]:
            previous_bound_index = None
            continue
        if previous_bound_index is not None:
            if overlap_cursor >= len(overlaps):
                raise RuntimeError("overlap list ended before bound-state pairs")
            previous = rows[previous_bound_index]
            overlap = float(overlaps[overlap_cursor])
            overlap_cursor += 1
            previous_resolved = abs(float(previous["level_mev"])) <= 0.999 * M_Q
            current_resolved = abs(float(row["level_mev"])) <= 0.999 * M_Q
            if previous_resolved and current_resolved:
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
    if overlap_cursor != len(overlaps):
        raise RuntimeError(
            f"unused overlaps: consumed {overlap_cursor}, available {len(overlaps)}"
        )
    if not pairs:
        raise RuntimeError(f"no resolved {coordinate} pairs")
    return {
        "independent_energy_window_mev": [-0.999 * M_Q, 0.999 * M_Q],
        "pairs": pairs,
        "minimum_overlap": min(pair["overlap"] for pair in pairs),
    }


def main(output_dir: Path) -> int:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite evidence in {output_dir}")
    for path, expected_hash in EXPECTED_INPUT_HASHES.items():
        if not path.exists():
            raise FileNotFoundError(path)
        actual_hash = sha256_bytes(path.read_bytes())
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"immutable input mismatch for {path.relative_to(ROOT)}: {actual_hash}"
            )

    output_dir.mkdir(parents=True)
    source_dir = output_dir / "sources"
    source_dir.mkdir()
    shutil.copy2(PROTOCOL, source_dir / PROTOCOL.name)
    shutil.copy2(SELF, source_dir / SELF.name)
    upstream_dir = source_dir / "upstream"
    upstream_dir.mkdir()
    for path in EXPECTED_INPUT_HASHES:
        destination = upstream_dir / path.name
        if destination.exists():
            destination = upstream_dir / f"{path.parent.name}_{path.name}"
        shutil.copy2(path, destination)

    primary = json.loads(PRIMARY_RECEIPT.read_text(encoding="utf-8"))
    independent = json.loads(INDEPENDENT_RECEIPT.read_text(encoding="utf-8"))
    if primary["schema"] != "cassi.qcd-quark-meson-carrier.primary.v1":
        raise RuntimeError("unexpected upstream primary schema")
    if independent["schema"] != "cassi.qcd-quark-meson-carrier.verification.v1":
        raise RuntimeError("unexpected upstream independent schema")

    envelope_by_a = {
        round(float(row["a"]), 12): row for row in primary["formation_envelope"]["rows"]
    }
    sparse_rows: dict[tuple[float, float], list[dict[str, Any]]] = {}
    raw_arrays: dict[str, np.ndarray] = {}
    envelope_results: list[dict[str, Any]] = []
    for a in A_VALUES:
        source_row = envelope_by_a[round(float(a), 12)]
        radius = float(source_row["radius_fm"])
        rows = [solve_level(float(a), radius, int(n)) for n in GRIDS]
        sparse_rows[(float(a), radius)] = rows
        fit = fit_sequence(rows)
        continuum_total = 3.0 * fit["four_point_coefficients"]["e_infinity_mev"] + float(
            source_row["meson_mev"]
        )
        continuum_excess = continuum_total - 3.0 * M_Q
        upper_excess = continuum_excess + 3.0 * fit["uncertainty_mev"]
        envelope_results.append(
            {
                "a": float(a),
                "radius_fm": radius,
                "primary_level_mev": float(source_row["level_mev"]),
                "meson_mev": float(source_row["meson_mev"]),
                "grid_rows": [
                    {
                        key: row[key]
                        for key in (
                            "n",
                            "spacing_fm",
                            "energy_mev",
                            "nodes_h",
                            "rms_fm",
                            "tail_probability_r_ge_8fm",
                            "symmetry_error",
                            "eigenvalues_mev",
                        )
                    }
                    for row in rows
                ],
                "fit": fit,
                "continuum_total_mev": continuum_total,
                "continuum_excess_mev": continuum_excess,
                "upper_excess_mev": upper_excess,
            }
        )
        label = f"a{int(round(float(a) * 100)):03d}"
        raw_arrays[f"{label}_energy_mev"] = np.array(
            [row["energy_mev"] for row in rows]
        )
        raw_arrays[f"{label}_n"] = GRIDS

    endpoint_rows = sparse_rows[(1.0, float(envelope_by_a[1.0]["radius_fm"]))]
    if not math.isclose(
        float(envelope_by_a[1.0]["radius_fm"]), ENDPOINT_RADIUS, rel_tol=0.0, abs_tol=1.0e-12
    ):
        raise RuntimeError("endpoint radius differs from frozen value")
    endpoint_fit = fit_sequence(endpoint_rows)
    endpoint_e_infinity = endpoint_fit["four_point_coefficients"]["e_infinity_mev"]
    endpoint_meson = float(primary["measurements"]["selected_meson_mev"])
    endpoint_total = 3.0 * endpoint_e_infinity + endpoint_meson
    endpoint_binding = 3.0 * M_Q - endpoint_total
    endpoint_uncertainty = endpoint_fit["uncertainty_mev"]

    shooting_energy = float(independent["measurements"]["independent_endpoint_level_mev"])
    shooting_total = float(independent["measurements"]["independent_endpoint_total_mev"])
    shooting_radius = float(
        independent["independent_radius_reconstruction"]["selected_radius_fm"]
    )
    shooting_rms = float(independent["measurements"]["independent_endpoint_rms_fm"])

    radius_pairs = resolved_pairs(primary["endpoint_radius_scan"], "radius_fm")
    amplitude_pairs = resolved_pairs(primary["fixed_radius_amplitude_scan"], "a")
    reconstructed_barrier = max(
        0.0, max(row["continuum_excess_mev"] for row in envelope_results)
    )
    upper_barrier = max(0.0, max(row["upper_excess_mev"] for row in envelope_results))

    all_spectra_finite = all(
        math.isfinite(row["energy_mev"])
        and row["nodes_h"] == 0
        and row["symmetry_error"] < 1.0e-10
        for rows in sparse_rows.values()
        for row in rows
    )
    fits_rms_pass = all(
        row["fit"]["four_point_rms_mev"] < 0.10 for row in envelope_results
    )
    intercepts_pass = all(
        row["fit"]["intercept_difference_mev"] < 0.20
        for row in envelope_results
    )
    qmq1_inputs = {
        "all_spectra_finite_nodeless_symmetric": all_spectra_finite,
        "all_four_point_rms_below_0p10_mev": fits_rms_pass,
        "all_intercept_differences_below_0p20_mev": intercepts_pass,
        "endpoint_shooting_absolute_difference_mev": abs(
            endpoint_e_infinity - shooting_energy
        ),
        "endpoint_total_absolute_difference_mev": abs(endpoint_total - shooting_total),
        "endpoint_constant_bias_sign": endpoint_fit["constant_bias_sign"],
    }
    qmq1_pass = bool(
        all_spectra_finite
        and fits_rms_pass
        and intercepts_pass
        and qmq1_inputs["endpoint_shooting_absolute_difference_mev"] <= 0.50
        and qmq1_inputs["endpoint_total_absolute_difference_mev"] <= 2.0
        and endpoint_fit["constant_bias_sign"]
    )
    qualified_binding_margin = endpoint_binding - 3.0 * endpoint_uncertainty
    qmq2_supports = bool(
        qmq1_pass
        and radius_pairs["minimum_overlap"] > 0.70
        and amplitude_pairs["minimum_overlap"] > 0.70
        and qualified_binding_margin > 5.0
        and abs(shooting_radius - ENDPOINT_RADIUS) <= 0.02
        and 0.2 <= shooting_rms <= 1.5
    )
    if qmq2_supports:
        qmq2_verdict = "SUPPORTS"
    elif endpoint_total + 3.0 * endpoint_uncertainty >= 3.0 * M_Q:
        qmq2_verdict = "CONTRADICTS"
    else:
        qmq2_verdict = "INCONCLUSIVE"
    if qmq2_verdict == "SUPPORTS" and upper_barrier <= 155.0:
        qmq3_verdict = "SUPPORTS"
    elif qmq2_verdict == "CONTRADICTS":
        qmq3_verdict = "CONTRADICTS"
    else:
        qmq3_verdict = "INCONCLUSIVE"
    verdicts = {
        "QMQ1": "PASS" if qmq1_pass else "FAIL",
        "QMQ2": qmq2_verdict,
        "QMQ3": qmq3_verdict,
        "QMQ4": "FAIL",
    }

    finest_endpoint = endpoint_rows[-1]
    raw_arrays["endpoint_radial_n9600_fm"] = finest_endpoint["radial"]
    raw_arrays["endpoint_h_n9600"] = finest_endpoint["h"]
    raw_arrays["endpoint_j_n9600"] = finest_endpoint["j"]
    raw_arrays["endpoint_probability_n9600"] = finest_endpoint["probability"]
    array_path = output_dir / "resolution_arrays.npz"
    np.savez_compressed(array_path, **raw_arrays)

    payload = {
        "schema": SCHEMA,
        "completed": True,
        "scientific_execution_started": True,
        "protocol": identity(PROTOCOL),
        "sources": {
            "primary": identity(SELF),
            "immutable_inputs": [identity(path) for path in EXPECTED_INPUT_HASHES],
            "snapshots": [identity(path) for path in source_dir.rglob("*") if path.is_file()],
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
            "executable": sys.executable,
            "cpu_count": os.cpu_count(),
        },
        "constants": {
            "hbar_c_mev_fm": HBARC,
            "f_pi_mev": F_PI,
            "m_pi_mev": M_PI,
            "m_sigma_mev": M_SIGMA,
            "m_q_mev": M_Q,
            "lambda": LAMBDA,
            "r_max_fm": R_MAX,
            "grids": GRIDS,
            "a_values": A_VALUES,
            "endpoint_radius_fm": ENDPOINT_RADIUS,
        },
        "upstream_verdicts": {
            "qmc": independent["verdicts"],
            "complete_physical_matter_formation": independent[
                "complete_physical_matter_formation"
            ],
        },
        "resolved_branch_overlap": {
            "radius_scan": radius_pairs,
            "amplitude_scan": amplitude_pairs,
        },
        "endpoint": {
            "grid_rows": [
                {
                    key: row[key]
                    for key in (
                        "n",
                        "spacing_fm",
                        "energy_mev",
                        "nodes_h",
                        "rms_fm",
                        "tail_probability_r_ge_8fm",
                        "symmetry_error",
                        "eigenvalues_mev",
                    )
                }
                for row in endpoint_rows
            ],
            "fit": endpoint_fit,
            "continuum_level_mev": endpoint_e_infinity,
            "continuum_meson_mev": endpoint_meson,
            "continuum_total_mev": endpoint_total,
            "continuum_binding_margin_mev": endpoint_binding,
            "qualified_binding_margin_mev": qualified_binding_margin,
            "independent_shooting_level_mev": shooting_energy,
            "independent_shooting_total_mev": shooting_total,
            "independent_selected_radius_fm": shooting_radius,
            "independent_rms_fm": shooting_rms,
        },
        "formation_envelope": {
            "rows": envelope_results,
            "analytic_small_radius_excess_mev_a_le_0p35": 0.0,
            "reconstructed_barrier_mev": reconstructed_barrier,
            "conservative_upper_barrier_mev": upper_barrier,
            "threshold_mev": 155.0,
        },
        "gate_inputs": {
            "QMQ1": qmq1_inputs,
            "QMQ2": {
                "qmq1_pass": qmq1_pass,
                "minimum_radius_overlap": radius_pairs["minimum_overlap"],
                "minimum_amplitude_overlap": amplitude_pairs["minimum_overlap"],
                "qualified_binding_margin_mev": qualified_binding_margin,
                "radius_absolute_difference_fm": abs(shooting_radius - ENDPOINT_RADIUS),
                "independent_rms_fm": shooting_rms,
            },
            "QMQ3": {
                "qmq2": qmq2_verdict,
                "conservative_upper_barrier_mev": upper_barrier,
                "threshold_mev": 155.0,
            },
            "QMQ4": {
                "passed": False,
                "unchanged_missing_requirements": independent["gate_inputs"]["QMC6"][
                    "requirements"
                ],
            },
        },
        "verdicts": verdicts,
        "complete_physical_matter_formation": False,
        "artifacts": {
            "arrays": {
                "path": array_path.relative_to(ROOT).as_posix(),
                "sha256": sha256_bytes(array_path.read_bytes()),
                "bytes": array_path.stat().st_size,
            }
        },
        "failure": None,
    }
    result_path = output_dir / "results.json"
    write_json(result_path, payload)
    print(
        json.dumps(
            {
                "result": result_path.relative_to(ROOT).as_posix(),
                "endpoint_continuum_level_mev": endpoint_e_infinity,
                "endpoint_shooting_difference_mev": abs(
                    endpoint_e_infinity - shooting_energy
                ),
                "continuum_binding_margin_mev": endpoint_binding,
                "resolved_overlap_minima": {
                    "radius": radius_pairs["minimum_overlap"],
                    "amplitude": amplitude_pairs["minimum_overlap"],
                },
                "reconstructed_barrier_mev": reconstructed_barrier,
                "conservative_upper_barrier_mev": upper_barrier,
                "verdicts": verdicts,
                "complete_physical_matter_formation": False,
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0 if qmq1_pass else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    try:
        raise SystemExit(main(arguments.output_dir))
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise
