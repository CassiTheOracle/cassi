#!/usr/bin/env python3
"""Independently verify a frozen toroidal spectral-transfer receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RESULTS_SHA256 = "5004c720e2e245c8cd9a8b8192f0bb7e62a0d03d0a9240e3eea4a3b7669809c6"
SELECTED_ARMS = ("A", "B", "F", "G", "I", "J")
HELIX_ARMS = ("A", "I", "J")
BAND_EDGES = np.asarray((2.0, 4.0, 8.0, 16.0), dtype=np.float64)
ATOL = 1e-10
RTOL = 1e-8


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_error(actual: float, expected: float) -> float:
    return abs(actual - expected) / max(abs(expected), 1e-30)


def compare_tree(
    stored: Any,
    recomputed: Any,
    path: str,
    errors: list[str],
    maximum: list[float],
) -> None:
    if isinstance(stored, dict) and isinstance(recomputed, dict):
        if set(stored) != set(recomputed):
            errors.append(f"{path}: key mismatch")
            return
        for key in sorted(stored):
            compare_tree(stored[key], recomputed[key], f"{path}.{key}", errors, maximum)
        return
    if isinstance(stored, list) and isinstance(recomputed, list):
        if len(stored) != len(recomputed):
            errors.append(f"{path}: length mismatch")
            return
        for index, (left, right) in enumerate(zip(stored, recomputed)):
            compare_tree(left, right, f"{path}[{index}]", errors, maximum)
        return
    if isinstance(stored, bool) or isinstance(recomputed, bool) or stored is None or recomputed is None:
        if stored != recomputed:
            errors.append(f"{path}: {stored!r} != {recomputed!r}")
        return
    if isinstance(stored, (int, float)) and isinstance(recomputed, (int, float)):
        difference = abs(float(stored) - float(recomputed))
        scale = ATOL + RTOL * max(abs(float(stored)), abs(float(recomputed)))
        normalized = difference / scale
        maximum[0] = max(maximum[0], normalized)
        if not math.isfinite(normalized) or normalized > 1.0:
            errors.append(f"{path}: normalized difference {normalized:.6g}")
        return
    if stored != recomputed:
        errors.append(f"{path}: {stored!r} != {recomputed!r}")


def make_grid(n: int, box_size: float) -> dict[str, Any]:
    dx = box_size / n
    axis = (np.arange(n, dtype=np.float64) - n // 2) * dx
    x, y, z = np.meshgrid(axis, axis, axis, indexing="ij")
    frequencies = 2.0 * math.pi * np.fft.fftfreq(n, d=dx)
    kx, ky, kz = np.meshgrid(frequencies, frequencies, frequencies, indexing="ij")
    k2 = kx * kx + ky * ky + kz * kz
    q = np.sqrt(k2) / (2.0 * math.pi / box_size)
    band_index = np.digitize(q, BAND_EDGES, right=False).astype(np.int8)
    return {
        "dv": dx**3,
        "z": z,
        "r_perp": np.sqrt(x * x + y * y),
        "chi": np.arctan2(y, x),
        "k2": k2,
        "band_index": band_index,
    }


def binned(values: np.ndarray, band_index: np.ndarray) -> np.ndarray:
    return np.bincount(
        band_index.ravel(),
        weights=np.asarray(values, dtype=np.float64).ravel(),
        minlength=5,
    ).astype(np.float64)


def spectral_snapshot(
    psi_y: np.ndarray,
    psi_i: np.ndarray,
    grid: dict[str, Any],
    g: float,
) -> dict[str, Any]:
    dv = grid["dv"]
    psi_y_hat = np.fft.fftn(psi_y, norm="ortho")
    psi_i_hat = np.fft.fftn(psi_i, norm="ortho")
    modal_density = np.real(psi_y_hat * np.conj(psi_y_hat) + psi_i_hat * np.conj(psi_i_hat))
    mass_bands = dv * binned(modal_density, grid["band_index"])
    kinetic_bands = 0.5 * dv * binned(grid["k2"] * modal_density, grid["band_index"])
    mass_total = float(np.sum(mass_bands, dtype=np.float64))
    kinetic_total = float(np.sum(kinetic_bands, dtype=np.float64))
    density = np.abs(psi_y) ** 2 + np.abs(psi_i) ** 2
    direct_mass = float(np.sum(density, dtype=np.float64) * dv)

    if g == 0.0:
        binding_fractions = None
        transfer_bands = np.zeros(5, dtype=np.float64)
        potential_total = 0.0
        fine_flux = 0.0
    else:
        density_hat = np.fft.fftn(density, norm="ortho")
        phi_hat = np.zeros_like(density_hat)
        nonzero = grid["k2"] != 0.0
        phi_hat[nonzero] = -density_hat[nonzero] / grid["k2"][nonzero]
        phi = np.real(np.fft.ifftn(phi_hat, norm="ortho"))
        potential_modes = 0.5 * g * dv * np.real(np.conj(density_hat) * phi_hat)
        potential_bands = binned(potential_modes, grid["band_index"])
        potential_total = float(np.sum(potential_bands, dtype=np.float64))
        binding_fractions = -potential_bands / max(-potential_total, 1e-30)

        rhs_y_hat = -1j * g * np.fft.fftn(phi * psi_y, norm="ortho")
        rhs_i_hat = -1j * g * np.fft.fftn(phi * psi_i, norm="ortho")
        transfer_modes = 2.0 * dv * np.real(
            np.conj(psi_y_hat) * rhs_y_hat + np.conj(psi_i_hat) * rhs_i_hat
        )
        transfer_bands = binned(transfer_modes, grid["band_index"])
        fine_flux = float(-np.sum(transfer_bands[:3], dtype=np.float64) / mass_total)

    mass_fractions = mass_bands / mass_total
    kinetic_fractions = kinetic_bands / kinetic_total
    transfer_denominator = max(float(np.sum(np.abs(transfer_bands), dtype=np.float64)), 1e-30)
    return {
        "mass_fractions": mass_fractions,
        "kinetic_fractions": kinetic_fractions,
        "binding_fractions": binding_fractions,
        "transfer_bands": transfer_bands,
        "fine_flux": fine_flux,
        "mass_total": mass_total,
        "direct_mass": direct_mass,
        "kinetic_total": kinetic_total,
        "potential_total": potential_total,
        "mass_fraction_sum_error": abs(float(np.sum(mass_fractions)) - 1.0),
        "kinetic_fraction_sum_error": abs(float(np.sum(kinetic_fractions)) - 1.0),
        "binding_fraction_sum_error": (
            0.0 if binding_fractions is None else abs(float(np.sum(binding_fractions)) - 1.0)
        ),
        "transfer_conservation": abs(float(np.sum(transfer_bands))) / transfer_denominator,
    }


def helical_decomposition(
    psi: np.ndarray,
    grid: dict[str, Any],
    r_fit: float,
) -> dict[str, Any]:
    density = np.abs(psi) ** 2
    mass = float(np.sum(density, dtype=np.float64) * grid["dv"])
    theta = np.arctan2(grid["z"], grid["r_perp"] - r_fit)
    carrier = np.cos(theta - grid["chi"]) + 1j * np.sin(theta - grid["chi"])
    density_hat = np.fft.fftn(density, norm="ortho")
    contributions: dict[str, list[float]] = {}
    total = 0j
    for index in range(5):
        projected = np.real(
            np.fft.ifftn(
                np.where(grid["band_index"] == index, density_hat, 0.0),
                norm="ortho",
            )
        )
        value = complex(np.sum(projected * carrier) * grid["dv"] / mass)
        total += value
        contributions[f"B{index}"] = [float(value.real), float(value.imag)]
    direct = complex(np.sum(density * carrier) * grid["dv"] / mass)
    return {
        "bands": contributions,
        "direct": [float(direct.real), float(direct.imag)],
        "magnitude": abs(direct),
        "vector_closure_error": abs(total - direct),
    }


def fine(row: dict[str, Any], key: str) -> float:
    values = row[key]
    return float(values[3] + values[4])


def recompute_arm(
    arm_id: str,
    stored_arm: dict[str, Any],
    v5_arm: dict[str, Any],
    input_dir: Path,
    box_size: float,
    errors: list[str],
    maximum: list[float],
) -> tuple[dict[str, Any], dict[str, float]]:
    fields_path = input_dir / v5_arm["fields_file"]
    with np.load(fields_path) as receipt:
        times = np.asarray(receipt["times"], dtype=np.float64)
        fields_y = receipt["psi_y"]
        fields_i = receipt["psi_i"]
    dtype_ok = fields_y.dtype == np.complex128 and fields_i.dtype == np.complex128
    finite = bool(np.isfinite(fields_y).all() and np.isfinite(fields_i).all())
    if not dtype_ok:
        errors.append(f"arm {arm_id}: field precision mismatch")
    if not finite:
        errors.append(f"arm {arm_id}: nonfinite fields")
    grid = make_grid(v5_arm["config"]["n"], box_size)
    g = float(v5_arm["config"]["g"])
    rows: list[dict[str, Any]] = []
    maxima = {
        "mass_closure": 0.0,
        "stored_mass": 0.0,
        "stored_kinetic": 0.0,
        "stored_potential": 0.0,
        "mass_fraction_sum": 0.0,
        "kinetic_fraction_sum": 0.0,
        "binding_fraction_sum": 0.0,
        "transfer_conservation": 0.0,
        "helical_vector_closure": 0.0,
        "stored_helical_magnitude": 0.0,
    }
    helical: dict[str, Any] = {}
    for index, time_value in enumerate(times):
        metric = v5_arm["metrics"][index]
        snapshot = spectral_snapshot(fields_y[index], fields_i[index], grid, g)
        maxima["mass_closure"] = max(
            maxima["mass_closure"], relative_error(snapshot["mass_total"], snapshot["direct_mass"])
        )
        maxima["stored_mass"] = max(
            maxima["stored_mass"], relative_error(snapshot["mass_total"], metric["mass"])
        )
        maxima["stored_kinetic"] = max(
            maxima["stored_kinetic"], relative_error(snapshot["kinetic_total"], metric["kinetic"])
        )
        if g != 0.0:
            maxima["stored_potential"] = max(
                maxima["stored_potential"], relative_error(snapshot["potential_total"], metric["potential"])
            )
        for target, source in (
            ("mass_fraction_sum", "mass_fraction_sum_error"),
            ("kinetic_fraction_sum", "kinetic_fraction_sum_error"),
            ("binding_fraction_sum", "binding_fraction_sum_error"),
            ("transfer_conservation", "transfer_conservation"),
        ):
            maxima[target] = max(maxima[target], snapshot[source])
        row = {
            "time": float(time_value),
            "mass_fractions": snapshot["mass_fractions"].tolist(),
            "kinetic_fractions": snapshot["kinetic_fractions"].tolist(),
            "binding_fractions": (
                None if snapshot["binding_fractions"] is None else snapshot["binding_fractions"].tolist()
            ),
            "transfer_bands": snapshot["transfer_bands"].tolist(),
            "fine_flux": snapshot["fine_flux"],
        }
        rows.append(row)
        compare_tree(stored_arm["series"][index], row, f"arms.{arm_id}.series[{index}]", errors, maximum)

        if arm_id in HELIX_ARMS and index in (0, len(times) - 1):
            label = "initial" if index == 0 else "final"
            helical[label] = {}
            for component, fields, metric_key in (
                ("Y", fields_y, "helix_y"),
                ("I", fields_i, "helix_i"),
            ):
                decomposition = helical_decomposition(fields[index], grid, metric["r_fit"])
                maxima["helical_vector_closure"] = max(
                    maxima["helical_vector_closure"], decomposition["vector_closure_error"]
                )
                maxima["stored_helical_magnitude"] = max(
                    maxima["stored_helical_magnitude"],
                    relative_error(decomposition["magnitude"], metric[metric_key]),
                )
                helical[label][component] = decomposition
    compare_tree(stored_arm["helical"], helical, f"arms.{arm_id}.helical", errors, maximum)

    initial, final = rows[0], rows[-1]
    delta_mass = fine(final, "mass_fractions") - fine(initial, "mass_fractions")
    delta_kinetic = fine(final, "kinetic_fractions") - fine(initial, "kinetic_fractions")
    delta_binding = 0.0 if g == 0.0 else fine(final, "binding_fractions") - fine(initial, "binding_fractions")
    flux = np.asarray([row["fine_flux"] for row in rows], dtype=np.float64)
    integrated_flux = float(np.sum(0.5 * (flux[1:] + flux[:-1]) * np.diff(times), dtype=np.float64))
    interval_error = abs(delta_mass - integrated_flux)
    sign_agreement = (
        (abs(delta_mass) < 1e-8 and abs(integrated_flux) < 1e-8)
        or delta_mass * integrated_flux > 0.0
    )
    summary = {
        "delta_fine_mass_fraction": delta_mass,
        "delta_fine_kinetic_fraction": delta_kinetic,
        "delta_fine_binding_fraction": delta_binding,
        "integrated_fine_flux": integrated_flux,
        "interval_transfer_error": interval_error,
        "interval_sign_agreement": sign_agreement,
        "forward": bool(
            g != 0.0
            and delta_mass >= 0.05
            and delta_kinetic >= 0.10
            and delta_binding >= 0.10
            and integrated_flux >= 0.02
        ),
        "no_forward": bool(
            g == 0.0
            and abs(delta_mass) < 0.01
            and abs(delta_kinetic) < 0.01
            and np.all(flux == 0.0)
        ),
        "initial_fine_mass_fraction": fine(initial, "mass_fractions"),
        "final_fine_mass_fraction": fine(final, "mass_fractions"),
        "initial_fine_kinetic_fraction": fine(initial, "kinetic_fractions"),
        "final_fine_kinetic_fraction": fine(final, "kinetic_fractions"),
        "initial_fine_binding_fraction": None if g == 0.0 else fine(initial, "binding_fractions"),
        "final_fine_binding_fraction": None if g == 0.0 else fine(final, "binding_fractions"),
    }
    compare_tree(stored_arm["closure_maxima"], maxima, f"arms.{arm_id}.closure_maxima", errors, maximum)
    compare_tree(stored_arm["summary"], summary, f"arms.{arm_id}.summary", errors, maximum)
    return summary, maxima


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transfer", type=Path)
    args = parser.parse_args()
    transfer_path = args.transfer.resolve()
    run_dir = transfer_path.parent
    output_path = run_dir / "verification.json"
    with transfer_path.open("r", encoding="utf-8") as handle:
        transfer = json.load(handle)

    errors: list[str] = []
    maximum = [0.0]
    if transfer.get("probe") != "toroidal_multiscale_transfer":
        errors.append("probe identifier mismatch")
    if transfer.get("diagnostic") != "orthonormal_q_shell_transfer_v1":
        errors.append("diagnostic identifier mismatch")
    if tuple(transfer.get("selected_arms", ())) != SELECTED_ARMS:
        errors.append("selected arm mismatch")
    expected_bands = [
        {"name": "B0", "lower_q": 0.0, "upper_q": 2.0},
        {"name": "B1", "lower_q": 2.0, "upper_q": 4.0},
        {"name": "B2", "lower_q": 4.0, "upper_q": 8.0},
        {"name": "B3", "lower_q": 8.0, "upper_q": 16.0},
        {"name": "B4", "lower_q": 16.0, "upper_q": None},
    ]
    if transfer.get("bands") != expected_bands or transfer.get("fine_bands") != ["B3", "B4"]:
        errors.append("spectral band mismatch")

    input_results = ROOT / transfer["input_results"]
    input_dir = input_results.parent
    input_verification = input_dir / "verification.json"
    if sha256_file(input_results) != EXPECTED_RESULTS_SHA256:
        errors.append("canonical V5 results hash mismatch")
    if transfer.get("input_results_sha256") != EXPECTED_RESULTS_SHA256:
        errors.append("stored V5 results hash mismatch")
    with input_results.open("r", encoding="utf-8") as handle:
        v5 = json.load(handle)
    with input_verification.open("r", encoding="utf-8") as handle:
        v5_verification = json.load(handle)
    if not v5_verification.get("pass") or v5_verification.get("errors"):
        errors.append("canonical V5 verification is not clean")

    expected_sources = {
        "field-experience/toroidal-multiscale-transfer-pre-registration.md",
        "field-experience/toroidal_multiscale_transfer_probe.py",
        "field-experience/verify_toroidal_multiscale_transfer.py",
    }
    if set(transfer.get("sources", {})) != expected_sources:
        errors.append("source manifest mismatch")
    else:
        for relative, expected_hash in transfer["sources"].items():
            if sha256_file(ROOT / relative) != expected_hash:
                errors.append(f"source hash mismatch: {relative}")

    expected_input_paths = {
        str(input_results.relative_to(ROOT)).replace("\\", "/"),
        str(input_verification.relative_to(ROOT)).replace("\\", "/"),
        *(
            str((input_dir / v5["arms"][arm_id]["fields_file"]).relative_to(ROOT)).replace("\\", "/")
            for arm_id in SELECTED_ARMS
        ),
    }
    if set(transfer.get("input_hashes", {})) != expected_input_paths:
        errors.append("input manifest mismatch")
    else:
        for relative, expected_hash in transfer["input_hashes"].items():
            if sha256_file(ROOT / relative) != expected_hash:
                errors.append(f"input hash mismatch: {relative}")

    global_maxima = {
        "mass_closure": 0.0,
        "stored_mass": 0.0,
        "stored_kinetic": 0.0,
        "stored_potential": 0.0,
        "mass_fraction_sum": 0.0,
        "kinetic_fraction_sum": 0.0,
        "binding_fraction_sum": 0.0,
        "transfer_conservation": 0.0,
        "helical_vector_closure": 0.0,
        "stored_helical_magnitude": 0.0,
    }
    summaries: dict[str, dict[str, Any]] = {}
    box_size = float(v5["constants"]["box_size"])
    for arm_id in SELECTED_ARMS:
        print(f"verifying arm {arm_id}", flush=True)
        stored_arm = transfer["arms"][arm_id]
        v5_arm = v5["arms"][arm_id]
        if stored_arm.get("config") != v5_arm["config"]:
            errors.append(f"arm {arm_id}: config mismatch")
        actual_field_hash = sha256_file(input_dir / v5_arm["fields_file"])
        if stored_arm.get("fields_sha256") != actual_field_hash:
            errors.append(f"arm {arm_id}: field hash mismatch")
        summary, maxima = recompute_arm(
            arm_id, stored_arm, v5_arm, input_dir, box_size, errors, maximum
        )
        summaries[arm_id] = summary
        for key in global_maxima:
            global_maxima[key] = max(global_maxima[key], maxima[key])

    q1 = not any(
        text.startswith(("canonical", "stored V5", "source", "input", "arm"))
        and "normalized difference" not in text
        for text in errors
    ) and all(
        transfer["arms"][arm_id]["dtype_ok"] and transfer["arms"][arm_id]["finite"]
        for arm_id in SELECTED_ARMS
    )
    q2 = bool(
        global_maxima["mass_closure"] <= 1e-10
        and global_maxima["stored_mass"] <= 1e-10
        and global_maxima["stored_kinetic"] <= 1e-6
        and global_maxima["stored_potential"] <= 1e-6
        and global_maxima["mass_fraction_sum"] <= 1e-12
        and global_maxima["kinetic_fraction_sum"] <= 1e-12
        and global_maxima["binding_fraction_sum"] <= 1e-12
        and global_maxima["helical_vector_closure"] <= 1e-10
        and global_maxima["stored_helical_magnitude"] <= 1e-6
    )
    q3 = bool(global_maxima["transfer_conservation"] <= 1e-10)
    q4_details = {
        arm_id: {
            "interval_transfer_error": summaries[arm_id]["interval_transfer_error"],
            "interval_sign_agreement": summaries[arm_id]["interval_sign_agreement"],
        }
        for arm_id in HELIX_ARMS
    }
    q4 = all(
        details["interval_transfer_error"] <= 0.05 and details["interval_sign_agreement"]
        for details in q4_details.values()
    )
    convergence: dict[str, Any] = {}
    q5 = True
    for arm_id in ("I", "J"):
        differences = {
            "delta_fine_mass_fraction": abs(
                summaries[arm_id]["delta_fine_mass_fraction"] - summaries["A"]["delta_fine_mass_fraction"]
            ),
            "delta_fine_kinetic_fraction": abs(
                summaries[arm_id]["delta_fine_kinetic_fraction"] - summaries["A"]["delta_fine_kinetic_fraction"]
            ),
            "delta_fine_binding_fraction": abs(
                summaries[arm_id]["delta_fine_binding_fraction"] - summaries["A"]["delta_fine_binding_fraction"]
            ),
            "integrated_fine_flux": abs(
                summaries[arm_id]["integrated_fine_flux"] - summaries["A"]["integrated_fine_flux"]
            ),
        }
        passed = bool(
            differences["delta_fine_mass_fraction"] <= 0.03
            and differences["delta_fine_kinetic_fraction"] <= 0.05
            and differences["delta_fine_binding_fraction"] <= 0.05
            and differences["integrated_fine_flux"] <= 0.03
        )
        convergence[arm_id] = {"pass": passed, "differences": differences}
        q5 = q5 and passed
    gates = {
        "Q1_input_identity": {"pass": q1, "errors": transfer["gates"]["Q1_input_identity"]["errors"]},
        "Q2_spectral_closure": {"pass": q2, "maxima": global_maxima},
        "Q3_transfer_conservation": {
            "pass": q3,
            "max_relative_residual": global_maxima["transfer_conservation"],
        },
        "Q4_interval_transfer": {"pass": q4, "arms": q4_details},
        "Q5_convergence": {"pass": q5, "arms": convergence},
    }
    quality = all(gate["pass"] for gate in gates.values())
    if not quality:
        verdict = "INCONCLUSIVE—DIAGNOSTIC QUALITY"
    elif not summaries["A"]["forward"]:
        verdict = "CONTRADICTS FORWARD-TRANSFER HYPOTHESIS"
    elif not summaries["B"]["no_forward"]:
        verdict = "INCONCLUSIVE—GRAVITY ATTRIBUTION"
    elif summaries["A"]["forward"] and not summaries["G"]["forward"]:
        verdict = "INCONCLUSIVE—PERTURBATION SENSITIVITY"
    elif summaries["F"]["forward"]:
        verdict = "SUPPORTS GENERIC GRAVITATIONAL FOCUSING"
    else:
        verdict = "SUPPORTS TOROIDAL-SPECIFIC FORWARD TRANSFER"

    compare_tree(transfer["gates"], gates, "gates", errors, maximum)
    if transfer.get("verdict") != verdict:
        errors.append(f"verdict mismatch: {transfer.get('verdict')} != {verdict}")
    verification = {
        "verifier": "independent_numpy_bincount_transfer_v1",
        "transfer_sha256": sha256_file(transfer_path),
        "recomputed_gates": gates,
        "recomputed_verdict": verdict,
        "max_normalized_metric_error": maximum[0],
        "errors": errors,
        "pass": not errors,
    }
    with output_path.open("x", encoding="utf-8") as handle:
        json.dump(verification, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(verification, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
