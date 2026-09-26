#!/usr/bin/env python3
"""Analyze preregistered spectral transfer in the frozen V5 toroidal fields."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "runs" / "20260831T223517Z_toroidal_coherence_survival_v5"
EXPECTED_RESULTS_SHA256 = "5004c720e2e245c8cd9a8b8192f0bb7e62a0d03d0a9240e3eea4a3b7669809c6"
SELECTED_ARMS = ("A", "B", "F", "G", "I", "J")
HELIX_ARMS = ("A", "I", "J")
BANDS = (
    ("B0", 0.0, 2.0),
    ("B1", 2.0, 4.0),
    ("B2", 4.0, 8.0),
    ("B3", 8.0, 16.0),
    ("B4", 16.0, math.inf),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_error(actual: float, expected: float) -> float:
    return abs(actual - expected) / max(abs(expected), 1e-30)


def make_grid(n: int, box_size: float) -> dict[str, Any]:
    dx = box_size / n
    coordinates = (np.arange(n, dtype=np.float64) - n // 2) * dx
    x, y, z = np.meshgrid(coordinates, coordinates, coordinates, indexing="ij")
    frequencies = 2.0 * math.pi * np.fft.fftfreq(n, d=dx)
    kx, ky, kz = np.meshgrid(frequencies, frequencies, frequencies, indexing="ij")
    k2 = kx * kx + ky * ky + kz * kz
    fundamental = 2.0 * math.pi / box_size
    q = np.sqrt(k2) / fundamental
    masks = tuple((q >= lower) & (q < upper) for _, lower, upper in BANDS)
    if not np.all(np.sum(np.stack(masks), axis=0) == 1):
        raise RuntimeError("spectral bands are not exhaustive and exclusive")
    return {
        "dx": dx,
        "dv": dx**3,
        "x": x,
        "y": y,
        "z": z,
        "r_perp": np.sqrt(x * x + y * y),
        "chi": np.arctan2(y, x),
        "k2": k2,
        "masks": masks,
    }


def band_sums(values: np.ndarray, masks: tuple[np.ndarray, ...]) -> np.ndarray:
    return np.asarray(
        [np.sum(values[mask], dtype=np.float64) for mask in masks],
        dtype=np.float64,
    )


def spectral_snapshot(
    psi_y: np.ndarray,
    psi_i: np.ndarray,
    grid: dict[str, Any],
    g: float,
) -> dict[str, Any]:
    dv = grid["dv"]
    masks = grid["masks"]
    psi_y_hat = np.fft.fftn(psi_y, norm="ortho")
    psi_i_hat = np.fft.fftn(psi_i, norm="ortho")
    modal_density = np.abs(psi_y_hat) ** 2 + np.abs(psi_i_hat) ** 2
    mass_bands = dv * band_sums(modal_density, masks)
    kinetic_bands = 0.5 * dv * band_sums(grid["k2"] * modal_density, masks)
    mass_total = float(np.sum(mass_bands, dtype=np.float64))
    kinetic_total = float(np.sum(kinetic_bands, dtype=np.float64))

    rho = np.abs(psi_y) ** 2 + np.abs(psi_i) ** 2
    direct_mass = float(np.sum(rho, dtype=np.float64) * dv)
    if g == 0.0:
        potential_bands = None
        binding_fractions = None
        transfer_bands = np.zeros(len(BANDS), dtype=np.float64)
        flux = 0.0
        potential_total = 0.0
    else:
        rho_hat = np.fft.fftn(rho, norm="ortho")
        phi_hat = np.zeros_like(rho_hat)
        nonzero = grid["k2"] > 0.0
        phi_hat[nonzero] = -rho_hat[nonzero] / grid["k2"][nonzero]
        phi = np.real(np.fft.ifftn(phi_hat, norm="ortho"))
        potential_spectral = 0.5 * g * dv * np.real(np.conj(rho_hat) * phi_hat)
        potential_bands = band_sums(potential_spectral, masks)
        potential_total = float(np.sum(potential_bands, dtype=np.float64))
        binding_fractions = -potential_bands / max(-potential_total, 1e-30)

        potential_y_hat = np.fft.fftn(phi * psi_y, norm="ortho")
        potential_i_hat = np.fft.fftn(phi * psi_i, norm="ortho")
        transfer_spectral = 2.0 * dv * np.real(
            np.conj(psi_y_hat) * (-1j * g * potential_y_hat)
            + np.conj(psi_i_hat) * (-1j * g * potential_i_hat)
        )
        transfer_bands = band_sums(transfer_spectral, masks)
        flux = float(-np.sum(transfer_bands[:3], dtype=np.float64) / mass_total)

    mass_fractions = mass_bands / mass_total
    kinetic_fractions = kinetic_bands / kinetic_total
    transfer_denominator = max(float(np.sum(np.abs(transfer_bands), dtype=np.float64)), 1e-30)
    return {
        "mass_fractions": mass_fractions,
        "kinetic_fractions": kinetic_fractions,
        "binding_fractions": binding_fractions,
        "transfer_bands": transfer_bands,
        "fine_flux": flux,
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
    rho = np.abs(psi) ** 2
    mass = float(np.sum(rho, dtype=np.float64) * grid["dv"])
    theta = np.arctan2(grid["z"], grid["r_perp"] - r_fit)
    carrier = np.exp(1j * (theta - grid["chi"]))
    rho_hat = np.fft.fftn(rho, norm="ortho")
    contributions: dict[str, list[float]] = {}
    vectors: list[complex] = []
    for (name, _, _), mask in zip(BANDS, grid["masks"]):
        projected = np.real(np.fft.ifftn(np.where(mask, rho_hat, 0.0), norm="ortho"))
        value = complex(np.sum(projected * carrier) * grid["dv"] / mass)
        vectors.append(value)
        contributions[name] = [float(value.real), float(value.imag)]
    direct = complex(np.sum(rho * carrier) * grid["dv"] / mass)
    summed = sum(vectors, 0j)
    return {
        "bands": contributions,
        "direct": [float(direct.real), float(direct.imag)],
        "magnitude": abs(direct),
        "vector_closure_error": abs(summed - direct),
    }


def fine_fraction(row: dict[str, Any], key: str) -> float:
    values = row[key]
    return float(values[3] + values[4])


def analyze_arm(
    arm_id: str,
    arm: dict[str, Any],
    input_dir: Path,
    box_size: float,
) -> tuple[dict[str, Any], dict[str, float], bool, str]:
    fields_path = input_dir / arm["fields_file"]
    with np.load(fields_path) as receipt:
        times = np.asarray(receipt["times"], dtype=np.float64)
        fields_y = receipt["psi_y"]
        fields_i = receipt["psi_i"]
    dtype_ok = fields_y.dtype == np.complex128 and fields_i.dtype == np.complex128
    finite = bool(np.isfinite(fields_y).all() and np.isfinite(fields_i).all())
    if fields_y.shape != fields_i.shape or fields_y.shape[0] != len(times):
        raise ValueError(f"arm {arm_id}: inconsistent field shapes")
    if len(arm["metrics"]) != len(times):
        raise ValueError(f"arm {arm_id}: metric/time count mismatch")

    grid = make_grid(arm["config"]["n"], box_size)
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
    g = float(arm["config"]["g"])
    for index, time_value in enumerate(times):
        stored = arm["metrics"][index]
        if abs(float(time_value) - float(stored["time"])) > 1e-12:
            raise ValueError(f"arm {arm_id}: stored time mismatch at index {index}")
        snapshot = spectral_snapshot(fields_y[index], fields_i[index], grid, g)
        maxima["mass_closure"] = max(
            maxima["mass_closure"],
            relative_error(snapshot["mass_total"], snapshot["direct_mass"]),
        )
        maxima["stored_mass"] = max(
            maxima["stored_mass"], relative_error(snapshot["mass_total"], stored["mass"])
        )
        maxima["stored_kinetic"] = max(
            maxima["stored_kinetic"], relative_error(snapshot["kinetic_total"], stored["kinetic"])
        )
        if g != 0.0:
            maxima["stored_potential"] = max(
                maxima["stored_potential"],
                relative_error(snapshot["potential_total"], stored["potential"]),
            )
        for target, source in (
            ("mass_fraction_sum", "mass_fraction_sum_error"),
            ("kinetic_fraction_sum", "kinetic_fraction_sum_error"),
            ("binding_fraction_sum", "binding_fraction_sum_error"),
            ("transfer_conservation", "transfer_conservation"),
        ):
            maxima[target] = max(maxima[target], snapshot[source])
        rows.append(
            {
                "time": float(time_value),
                "mass_fractions": snapshot["mass_fractions"].tolist(),
                "kinetic_fractions": snapshot["kinetic_fractions"].tolist(),
                "binding_fractions": (
                    None
                    if snapshot["binding_fractions"] is None
                    else snapshot["binding_fractions"].tolist()
                ),
                "transfer_bands": snapshot["transfer_bands"].tolist(),
                "fine_flux": snapshot["fine_flux"],
            }
        )

        if arm_id in HELIX_ARMS and index in (0, len(times) - 1):
            label = "initial" if index == 0 else "final"
            helical[label] = {}
            for component, fields, stored_key in (
                ("Y", fields_y, "helix_y"),
                ("I", fields_i, "helix_i"),
            ):
                decomposition = helical_decomposition(fields[index], grid, stored["r_fit"])
                maxima["helical_vector_closure"] = max(
                    maxima["helical_vector_closure"], decomposition["vector_closure_error"]
                )
                maxima["stored_helical_magnitude"] = max(
                    maxima["stored_helical_magnitude"],
                    relative_error(decomposition["magnitude"], stored[stored_key]),
                )
                helical[label][component] = decomposition

    initial, final = rows[0], rows[-1]
    delta_mass = fine_fraction(final, "mass_fractions") - fine_fraction(initial, "mass_fractions")
    delta_kinetic = fine_fraction(final, "kinetic_fractions") - fine_fraction(initial, "kinetic_fractions")
    delta_binding = (
        0.0
        if g == 0.0
        else fine_fraction(final, "binding_fractions") - fine_fraction(initial, "binding_fractions")
    )
    flux_values = np.asarray([row["fine_flux"] for row in rows], dtype=np.float64)
    integrated_flux = float(
        np.sum(0.5 * (flux_values[1:] + flux_values[:-1]) * np.diff(times), dtype=np.float64)
    )
    interval_error = abs(delta_mass - integrated_flux)
    sign_agreement = (
        (abs(delta_mass) < 1e-8 and abs(integrated_flux) < 1e-8)
        or delta_mass * integrated_flux > 0.0
    )
    forward = bool(
        g != 0.0
        and delta_mass >= 0.05
        and delta_kinetic >= 0.10
        and delta_binding >= 0.10
        and integrated_flux >= 0.02
    )
    no_forward = bool(
        g == 0.0
        and abs(delta_mass) < 0.01
        and abs(delta_kinetic) < 0.01
        and np.all(flux_values == 0.0)
    )
    summary = {
        "delta_fine_mass_fraction": delta_mass,
        "delta_fine_kinetic_fraction": delta_kinetic,
        "delta_fine_binding_fraction": delta_binding,
        "integrated_fine_flux": integrated_flux,
        "interval_transfer_error": interval_error,
        "interval_sign_agreement": sign_agreement,
        "forward": forward,
        "no_forward": no_forward,
        "initial_fine_mass_fraction": fine_fraction(initial, "mass_fractions"),
        "final_fine_mass_fraction": fine_fraction(final, "mass_fractions"),
        "initial_fine_kinetic_fraction": fine_fraction(initial, "kinetic_fractions"),
        "final_fine_kinetic_fraction": fine_fraction(final, "kinetic_fractions"),
        "initial_fine_binding_fraction": (
            None if g == 0.0 else fine_fraction(initial, "binding_fractions")
        ),
        "final_fine_binding_fraction": (
            None if g == 0.0 else fine_fraction(final, "binding_fractions")
        ),
    }
    return (
        {
            "config": arm["config"],
            "fields_file": arm["fields_file"],
            "fields_sha256": sha256_file(fields_path),
            "dtype_ok": dtype_ok,
            "finite": finite,
            "series": rows,
            "helical": helical,
            "closure_maxima": maxima,
            "summary": summary,
        },
        maxima,
        finite and dtype_ok,
        sha256_file(fields_path),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, help="fresh receipt directory")
    args = parser.parse_args()
    input_dir = args.input.resolve()
    results_path = input_dir / "results.json"
    verification_path = input_dir / "verification.json"
    with results_path.open("r", encoding="utf-8") as handle:
        v5 = json.load(handle)
    with verification_path.open("r", encoding="utf-8") as handle:
        v5_verification = json.load(handle)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.output or ROOT / "runs" / f"{stamp}_toroidal_multiscale_transfer"
    run_dir.mkdir(parents=True, exist_ok=False)

    source_paths = (
        ROOT / "field-experience" / "toroidal-multiscale-transfer-pre-registration.md",
        Path(__file__).resolve(),
        ROOT / "field-experience" / "verify_toroidal_multiscale_transfer.py",
    )
    sources = {
        str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
        for path in source_paths
    }
    input_hashes = {
        str(results_path.relative_to(ROOT)).replace("\\", "/"): sha256_file(results_path),
        str(verification_path.relative_to(ROOT)).replace("\\", "/"): sha256_file(verification_path),
    }

    input_errors: list[str] = []
    if input_hashes[str(results_path.relative_to(ROOT)).replace("\\", "/")] != EXPECTED_RESULTS_SHA256:
        input_errors.append("canonical V5 results hash mismatch")
    if not v5_verification.get("pass") or v5_verification.get("errors"):
        input_errors.append("canonical V5 verification is not clean")
    if v5.get("verdict") != "DOES NOT EMERGE":
        input_errors.append("canonical V5 verdict mismatch")

    arms: dict[str, Any] = {}
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
    box_size = float(v5["constants"]["box_size"])
    for arm_id in SELECTED_ARMS:
        print(f"analyzing arm {arm_id}", flush=True)
        arm_result, maxima, valid_fields, actual_hash = analyze_arm(
            arm_id, v5["arms"][arm_id], input_dir, box_size
        )
        arms[arm_id] = arm_result
        if not valid_fields:
            input_errors.append(f"arm {arm_id}: field precision or finiteness failure")
        expected_hash = v5["arms"][arm_id]["fields_sha256"]
        if actual_hash != expected_hash:
            input_errors.append(f"arm {arm_id}: frozen field hash mismatch")
        relative_path = str((input_dir / v5["arms"][arm_id]["fields_file"]).relative_to(ROOT)).replace("\\", "/")
        input_hashes[relative_path] = actual_hash
        for key in global_maxima:
            global_maxima[key] = max(global_maxima[key], maxima[key])

    q1 = not input_errors
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
            "interval_transfer_error": arms[arm_id]["summary"]["interval_transfer_error"],
            "interval_sign_agreement": arms[arm_id]["summary"]["interval_sign_agreement"],
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
                arms[arm_id]["summary"]["delta_fine_mass_fraction"]
                - arms["A"]["summary"]["delta_fine_mass_fraction"]
            ),
            "delta_fine_kinetic_fraction": abs(
                arms[arm_id]["summary"]["delta_fine_kinetic_fraction"]
                - arms["A"]["summary"]["delta_fine_kinetic_fraction"]
            ),
            "delta_fine_binding_fraction": abs(
                arms[arm_id]["summary"]["delta_fine_binding_fraction"]
                - arms["A"]["summary"]["delta_fine_binding_fraction"]
            ),
            "integrated_fine_flux": abs(
                arms[arm_id]["summary"]["integrated_fine_flux"]
                - arms["A"]["summary"]["integrated_fine_flux"]
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
        "Q1_input_identity": {"pass": q1, "errors": input_errors},
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
    elif not arms["A"]["summary"]["forward"]:
        verdict = "CONTRADICTS FORWARD-TRANSFER HYPOTHESIS"
    elif not arms["B"]["summary"]["no_forward"]:
        verdict = "INCONCLUSIVE—GRAVITY ATTRIBUTION"
    elif arms["A"]["summary"]["forward"] and not arms["G"]["summary"]["forward"]:
        verdict = "INCONCLUSIVE—PERTURBATION SENSITIVITY"
    elif arms["F"]["summary"]["forward"]:
        verdict = "SUPPORTS GENERIC GRAVITATIONAL FOCUSING"
    else:
        verdict = "SUPPORTS TOROIDAL-SPECIFIC FORWARD TRANSFER"

    receipt = {
        "probe": "toroidal_multiscale_transfer",
        "diagnostic": "orthonormal_q_shell_transfer_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input_results": str(results_path.relative_to(ROOT)).replace("\\", "/"),
        "input_results_sha256": sha256_file(results_path),
        "input_hashes": input_hashes,
        "sources": sources,
        "selected_arms": list(SELECTED_ARMS),
        "bands": [
            {"name": name, "lower_q": lower, "upper_q": None if math.isinf(upper) else upper}
            for name, lower, upper in BANDS
        ],
        "fine_bands": ["B3", "B4"],
        "arms": arms,
        "gates": gates,
        "verdict": verdict,
    }
    output_path = run_dir / "transfer.json"
    with output_path.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "verdict": verdict,
                "gates": gates,
                "summaries": {arm_id: arms[arm_id]["summary"] for arm_id in SELECTED_ARMS},
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
