#!/usr/bin/env python3
"""Primary finite-period population-redistribution energy calculation.

This program consumes the eight individually qualified ``n=64`` profiles and
responses retained by sections 46--47, evaluates the source radial energy at
finite periodic trials, and writes the complete section-48 primary receipt.
The calculation is intentionally a direct finite-energy comparison; it does
not perform a new minimization or response solve.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any

import numpy as np
import torch

import matter_formation_vortex_core as core


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "matter-formation-vortex-axial-energy-v1"
MANIFEST_SCHEMA = "matter-formation-vortex-axial-energy-manifest-v1"
NOTEBOOK = "computations/matter-formation-continuum-report.md"
HEADING = "## 48. Working notes:"
CAPS = ("plus", "minus")
EPSILONS = {"plus": 1, "minus": -1}
SCHEDULE = ((32, 256), (32, 512), (64, 512), (64, 1024))
AMPLITUDES = (0.25, 0.125, 0.0625)
QUADRATURES = (32, 64)
WAVE_FACTORS = (0.5, 2.0)
WINDINGS = (0, 1)
LAMBDA_C = 1.0
ENERGY_COMPONENTS = (
    "fundamental_radial",
    "adjoint_radial",
    "fundamental_angular",
    "adjoint_angular",
    "magnetic",
    "potential",
    "carrier_gradient",
    "carrier_interaction",
    "carrier_quartic",
)
B_COMPONENTS = ("fundamental", "adjoint", "radial_connection", "angular_connection", "carrier")
REQUIRED_SOURCES = {
    "computations/matter_formation_vortex_core.py",
    "computations/verify_matter_formation_vortex_core.py",
    "computations/matter_formation_vortex_loaded.py",
    "computations/verify_matter_formation_vortex_loaded.py",
    "computations/matter_formation_vortex_compressibility.py",
    "computations/verify_matter_formation_vortex_compressibility.py",
    "computations/matter_formation_vortex_axial_energy.py",
    "computations/verify_matter_formation_vortex_axial_energy.py",
}
REQUIRED_EVIDENCE = {
    "runs/20260908_matter_formation_vortex_loaded/primary/summary.json",
    "runs/20260908_matter_formation_vortex_loaded/verification/verification.json",
    "runs/20260908_matter_formation_vortex_compressibility/primary/summary.json",
    "runs/20260908_matter_formation_vortex_compressibility/verification/verification.json",
}


def finite(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, np.bool_)):
        return True
    if isinstance(value, (int, float, np.integer, np.floating)):
        return bool(np.isfinite(value))
    if isinstance(value, np.ndarray):
        return bool(np.all(np.isfinite(value)))
    if isinstance(value, (list, tuple)):
        return all(finite(item) for item in value)
    if isinstance(value, dict):
        return all(finite(item) for item in value.values())
    return False


def strict_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): strict_value(v) for k, v in value.items()}
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (list, tuple)):
        return [strict_value(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        return result if math.isfinite(result) else None
    if isinstance(value, np.ndarray):
        return strict_value(value.tolist())
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(strict_value(value), handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def strict_json(path: Path) -> dict[str, Any]:
    def reject(token: str) -> None:
        raise ValueError(f"nonfinite JSON token: {token}")

    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)
    if not isinstance(value, dict) or not finite(value):
        raise ValueError("JSON root must be a finite object")
    return value


def safe_relative(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f"invalid relative path: {value!r}")
    resolved = (root / value).resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(f"path escapes root: {value}")
    return resolved


def expected_keys() -> set[tuple[str, int, int, int]]:
    return {(cap, R, N, EPSILONS[cap]) for cap in CAPS for R, N in SCHEDULE}


def _parent_row(rows: list[Any], cap: str, R: int, N: int) -> dict[str, Any]:
    for row in rows:
        if isinstance(row, dict) and row.get("cap") == cap and int(row.get("N", -1)) == N and int(float(row.get("R", -1))) == R and float(row.get("n", -1)) == 64.0:
            return row
    raise ValueError(f"parent row missing for {cap}, n=64, R={R}, N={N}")


def validate_manifest(manifest_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    manifest = strict_json(manifest_path)
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("manifest schema mismatch")

    section = manifest.get("section")
    if not isinstance(section, dict) or section.get("path") != NOTEBOOK or section.get("heading") != HEADING:
        raise ValueError("section identity mismatch")
    snapshot = safe_relative(manifest_path.parent, section.get("snapshot"))
    report = safe_relative(ROOT, section.get("path"))
    expected_section_hash = section.get("sha256")
    if not isinstance(expected_section_hash, str) or sha256(snapshot) != expected_section_hash:
        raise ValueError("frozen section snapshot hash mismatch")
    snapshot_text = snapshot.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    report_text = report.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    if not snapshot_text.startswith(HEADING):
        raise ValueError("frozen section does not begin at its heading")
    position = report_text.find(HEADING)
    if position < 0 or report_text[position : position + len(snapshot_text)] != snapshot_text:
        raise ValueError("live report does not contain the exact frozen section")

    sources = manifest.get("sources")
    if not isinstance(sources, list) or {item.get("path") for item in sources if isinstance(item, dict)} != REQUIRED_SOURCES:
        raise ValueError("manifest sources do not exactly match the eight programs")
    seen: set[str] = set()
    for item in sources:
        if not isinstance(item, dict):
            raise ValueError("malformed source record")
        rel = item.get("path")
        if not isinstance(rel, str) or rel in seen:
            raise ValueError("duplicate or malformed source record")
        seen.add(rel)
        source = safe_relative(ROOT, rel)
        frozen = safe_relative(manifest_path.parent, item.get("snapshot"))
        expected = item.get("sha256")
        if not isinstance(expected, str) or sha256(source) != expected or sha256(frozen) != expected:
            raise ValueError(f"source hash mismatch: {rel}")
        if item.get("bytes") != source.stat().st_size or item.get("bytes") != frozen.stat().st_size:
            raise ValueError(f"source byte-count mismatch: {rel}")

    evidence = manifest.get("evidence")
    if not isinstance(evidence, list) or {item.get("path") for item in evidence if isinstance(item, dict)} != REQUIRED_EVIDENCE:
        raise ValueError("manifest evidence does not exactly match both parent calculations")
    evidence_paths: dict[str, Path] = {}
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError("malformed evidence record")
        rel = item.get("path")
        path = safe_relative(ROOT, rel)
        if not isinstance(item.get("sha256"), str) or sha256(path) != item["sha256"]:
            raise ValueError(f"evidence hash mismatch: {rel}")
        evidence_paths[rel] = path
    loaded_primary = strict_json(evidence_paths["runs/20260908_matter_formation_vortex_loaded/primary/summary.json"])
    loaded_verification = strict_json(evidence_paths["runs/20260908_matter_formation_vortex_loaded/verification/verification.json"])
    response_primary = strict_json(evidence_paths["runs/20260908_matter_formation_vortex_compressibility/primary/summary.json"])
    response_verification = strict_json(evidence_paths["runs/20260908_matter_formation_vortex_compressibility/verification/verification.json"])
    if loaded_primary.get("schema") != "matter-formation-loaded-vortex-v1" or loaded_primary.get("all_rows_numerically_qualified") is not True:
        raise ValueError("loaded parent primary is not accepted")
    if loaded_primary.get("complete_physical_matter_formation") is not False or loaded_verification.get("complete_physical_matter_formation") is not False:
        raise ValueError("loaded parent physical-formation flag is not false")
    if loaded_verification.get("numerical_pass") is not True:
        raise ValueError("loaded parent independent verification is not accepted")
    if response_primary.get("schema") != "matter-formation-vortex-compressibility-v1" or response_primary.get("numerical_pass") is not True:
        raise ValueError("response parent primary is not accepted")
    if response_primary.get("complete_physical_matter_formation") is not False or response_verification.get("complete_physical_matter_formation") is not False:
        raise ValueError("response parent physical-formation flag is not false")
    if response_verification.get("numerical_pass") is not False or response_verification.get("verdict") != "INCONCLUSIVE":
        raise ValueError("response parent aggregate must remain inconclusive")

    inputs = manifest.get("inputs")
    if not isinstance(inputs, list) or len(inputs) != 8:
        raise ValueError("manifest must contain exactly eight selected inputs")
    records: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int, int, int]] = set()
    loaded_rows = loaded_primary.get("rows")
    response_rows = response_primary.get("rows")
    verification_rows = response_verification.get("rows")
    if not isinstance(loaded_rows, list) or not isinstance(response_rows, list) or not isinstance(verification_rows, list):
        raise ValueError("parent rows are missing")
    for item in inputs:
        if not isinstance(item, dict):
            raise ValueError("malformed input record")
        cap, epsilon = item.get("cap"), item.get("epsilon")
        R, N = item.get("R"), item.get("N")
        key = (cap, int(R), int(N), int(epsilon)) if cap in CAPS and isinstance(R, (int, float)) and isinstance(N, int) else None
        if key is None or key not in expected_keys() or key in seen_keys or item.get("n") != 64:
            raise ValueError(f"input schedule metadata mismatch: {item}")
        seen_keys.add(key)
        profile = safe_relative(ROOT, item.get("path"))
        response = safe_relative(ROOT, item.get("response_path"))
        profile_hash, response_hash = item.get("sha256"), item.get("response_sha256")
        if not isinstance(profile_hash, str) or sha256(profile) != profile_hash:
            raise ValueError(f"profile hash mismatch: {item.get('path')}")
        if not isinstance(response_hash, str) or sha256(response) != response_hash:
            raise ValueError(f"response hash mismatch: {item.get('response_path')}")
        loaded_row = _parent_row(loaded_rows, cap, int(R), N)
        response_row = _parent_row(response_rows, cap, int(R), N)
        if loaded_row.get("stationary") is not True or loaded_row.get("exception") is not None or response_row.get("qualified") is not True:
            raise ValueError(f"selected parent row is not qualified: {cap}, {R}, {N}")
        selected_verification = _parent_row(verification_rows, cap, int(R), N)
        if selected_verification.get("pass") is not True or len(selected_verification.get("fd", [])) != 3 or not all(row.get("pass") is True for row in selected_verification["fd"]):
            raise ValueError(f"selected response verification row is not qualified: {cap}, {R}, {N}")
        if item["path"] != f"runs/20260908_matter_formation_vortex_loaded/primary/{loaded_row['npz']}" or item["response_path"] != f"runs/20260908_matter_formation_vortex_compressibility/primary/{response_row['npz']}":
            raise ValueError("input paths do not match the accepted parent rows")
        records.append({
            "cap": cap,
            "epsilon": int(epsilon),
            "R": int(R),
            "N": N,
            "n": 64.0,
            "profile": profile,
            "profile_text": item["path"],
            "response": response,
            "response_text": item["response_path"],
            "loaded_row": loaded_row,
            "response_row": response_row,
        })
    if seen_keys != expected_keys():
        raise ValueError("input schedule is incomplete")
    order = {(cap, R, N): index for index, (cap, (R, N)) in enumerate((
        (cap, schedule) for cap in CAPS for schedule in SCHEDULE
    ))}
    records.sort(key=lambda item: order[(item["cap"], item["R"], item["N"])])
    return manifest, records, loaded_primary, response_primary


def population(model: core.RadialModel, f: np.ndarray) -> float:
    fq = (1.0 - model.t[None, :]) * f[:-1, None] + model.t[None, :] * f[1:, None]
    return float(np.sum(model.qweight * fq * fq))


def h_direction(model: core.RadialModel, y: np.ndarray, direction: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    def reduced_h(value: torch.Tensor) -> torch.Tensor:
        _, _, _, H, L = model.torch_energy(value)
        return -L / H

    h, dh = torch.autograd.functional.jvp(
        reduced_h,
        torch.as_tensor(y, dtype=torch.float64),
        torch.as_tensor(direction, dtype=torch.float64),
        strict=True,
    )
    return h.detach().numpy(), dh.detach().numpy()


def profile_energy(model: core.RadialModel, y: np.ndarray, f: np.ndarray) -> tuple[float, np.ndarray, float, np.ndarray]:
    fields = model._numpy_fields(y)
    p, q, u, b1, b3, dp, dq, du, db1, db3 = fields
    total, components, h, H, L = core.radial_density(p, q, u, b1, b3, dp, dq, du, db1, db3, model.qr, None, model.epsilon, np)
    fq = (1.0 - model.t[None, :]) * f[:-1, None] + model.t[None, :] * f[1:, None]
    dfq = (f[1:] - f[:-1])[:, None] / model.dr
    rho = p * p + q * q
    carrier = {
        "carrier_gradient": core.K_CX * dfq * dfq / 2.0,
        "carrier_interaction": -core.ETA_C * (core.RHO0 - rho) * fq * fq,
        "carrier_quartic": LAMBDA_C * fq**4 / 2.0,
    }
    values = np.array([
        np.sum(model.qweight * components["psi_radial"]),
        np.sum(model.qweight * components["phi_radial"]),
        np.sum(model.qweight * components["psi_angular"]),
        np.sum(model.qweight * components["phi_angular"]),
        np.sum(model.qweight * components["gauge"]),
        np.sum(model.qweight * (components["density_potential"] + components["composition_potential"] + components["higgs_potential"])),
        np.sum(model.qweight * carrier["carrier_gradient"]),
        np.sum(model.qweight * carrier["carrier_interaction"]),
        np.sum(model.qweight * carrier["carrier_quartic"]),
    ], dtype=np.float64)
    return float(np.sum(values)), values, float(np.sum(model.qweight * fq * fq)), h


def axial_b(
    model: core.RadialModel,
    y: np.ndarray,
    dy: np.ndarray,
    df: np.ndarray,
    half: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    variation = model._numpy_fields(dy)
    vp, vq, vu, vb1, vb3 = variation[:5]
    _, vh = h_direction(model, y, dy)
    vfq = (1.0 - model.t[None, :]) * df[:-1, None] + model.t[None, :] * df[1:, None]
    factor = 0.5 if half else 1.0
    components = np.array([
        factor * np.sum(model.qweight * core.A * (vp * vp + vq * vq)),
        factor * np.sum(model.qweight * core.D * vu * vu),
        factor * np.sum(model.qweight * core.D / (core.G * core.G) * vh * vh),
        factor * np.sum(model.qweight * core.D / (core.G * core.G * model.qr * model.qr) * (vb1 * vb1 + vb3 * vb3)),
        factor * np.sum(model.qweight * core.K_CX * vfq * vfq),
    ], dtype=np.float64)
    return components, np.stack((vp, vq, vu, vb1, vb3), axis=-1), vh




def _sample_trial(model: core.RadialModel, y0: np.ndarray, f0: np.ndarray, dy: np.ndarray, df: np.ndarray, population0: float, amplitude: float, Q: int) -> dict[str, np.ndarray | float]:
    theta = 2.0 * math.pi * np.arange(Q, dtype=np.float64) / Q
    p_df = population(model, df)
    normalization = math.sqrt(population0 / (population0 + amplitude * amplitude * p_df / 2.0))
    energies = np.empty((Q, 9), dtype=np.float64)
    axials = np.empty((Q, 5), dtype=np.float64)
    populations = np.empty(Q, dtype=np.float64)
    for index, angle in enumerate(theta):
        cosine, sine = math.cos(float(angle)), math.sin(float(angle))
        y = y0 + amplitude * dy * cosine
        f = normalization * (f0 + amplitude * df * cosine)
        _, components, pop, _ = profile_energy(model, y, f)
        ytheta = -amplitude * dy * sine
        ftheta = -normalization * amplitude * df * sine
        axial, _, _ = axial_b(model, y, ytheta, ftheta, half=True)
        energies[index] = components
        axials[index] = axial
        populations[index] = pop
    stem_data = {"theta": theta, "energy_components": energies, "axial_components": axials, "population": populations, "normalization": normalization}
    return stem_data


def failed_row(record: dict[str, Any], exception: str) -> dict[str, Any]:
    return {
        "cap": record["cap"], "epsilon": record["epsilon"], "n": 64.0, "R": record["R"], "N": record["N"],
        "base_npz": None,
        "base_energy": None, "population": None, "zeta": None, "B": None, "B_components": [], "L_star": None, "p_star": None,
        "trials": [], "qualified": False, "checks": [], "failures": [exception], "exception": exception,
        "complete_physical_matter_formation": False,
    }


def solve_row(output: Path, record: dict[str, Any]) -> dict[str, Any]:
    N, R, epsilon = record["N"], record["R"], record["epsilon"]
    stem = f"cap_{record['cap']}_n64_N{N}_R{R}"
    base_name = stem + "_axial.npz"
    with np.load(record["profile"], allow_pickle=False) as profile:
        required = {"r", "y", "f"}
        if not required.issubset(profile.files):
            raise ValueError(f"profile NPZ missing arrays: {sorted(required - set(profile.files))}")
        r = np.asarray(profile["r"], dtype=np.float64)
        y0 = np.asarray(profile["y"], dtype=np.float64)
        f0 = np.asarray(profile["f"], dtype=np.float64)
    with np.load(record["response"], allow_pickle=False) as response_data:
        required = {"response", "lump", "zeta"}
        if not required.issubset(response_data.files):
            raise ValueError(f"response NPZ missing arrays: {sorted(required - set(response_data.files))}")
        response = np.asarray(response_data["response"], dtype=np.float64)
        lump = np.asarray(response_data["lump"], dtype=np.float64)
        zeta = float(np.asarray(response_data["zeta"], dtype=np.float64).reshape(()))
    model = core.RadialModel(float(R), N, epsilon)
    if r.shape != (N + 1,) or y0.shape != (N + 1, 5) or f0.shape != (N + 1,) or response.shape != (6 * N,) or lump.shape != (N + 1,):
        raise ValueError("profile or response shape mismatch")
    if not (np.all(np.isfinite(r)) and np.all(np.isfinite(y0)) and np.all(np.isfinite(f0)) and np.all(np.isfinite(response)) and np.all(np.isfinite(lump)) and math.isfinite(zeta)):
        raise ValueError("profile or response contains nonfinite values")
    if not np.allclose(r, model.r, rtol=0.0, atol=1e-12):
        raise ValueError("profile radial grid differs from declared model")
    if np.any(lump <= 0.0):
        raise ValueError("response lumped masses must be positive")
    free_tangent = response.reshape(N, 6) / np.sqrt(lump[:-1, None])
    tangent = np.zeros((N + 1, 6), dtype=np.float64)
    tangent[:-1] = free_tangent
    dy, df = tangent[:, :5], tangent[:, 5]
    base_energy, base_components, P0, h0 = profile_energy(model, y0, f0)
    B_values, field_variation, h_direction0 = axial_b(model, y0, dy, df)
    B = float(np.sum(B_values))
    if not math.isfinite(B) or B <= 0.0 or not math.isfinite(zeta) or zeta >= 0.0:
        raise ValueError("section-48 sign prerequisite failed: require B>0 and zeta<0")
    p_star = math.sqrt(-zeta / B)
    L_star = 2.0 * math.pi / p_star
    base_parent_error = abs(base_energy - float(record["loaded_row"].get("energy"))) / max(1.0, abs(base_energy))
    population_parent_error = abs(P0 - 64.0) / 64.0
    samples: dict[tuple[int, int], dict[str, np.ndarray | float]] = {}
    trial_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    checks: list[dict[str, Any]] = [
        {"name": "base_parent_energy", "error": base_parent_error, "pass": base_parent_error < 1e-8},
        {"name": "population_parent_target", "error": population_parent_error, "pass": population_parent_error < 1e-10},
        {"name": "B_positive", "value": B, "pass": B > 0.0},
        {"name": "zeta_negative", "value": zeta, "pass": zeta < 0.0},
    ]
    if base_parent_error >= 1e-8 or population_parent_error >= 1e-10:
        failures.append("source-bound parent identity")
    for amplitude_index, amplitude in enumerate(AMPLITUDES):
        for Q in QUADRATURES:
            samples[(amplitude_index, Q)] = _sample_trial(model, y0, f0, dy, df, P0, amplitude, Q)
            sample_name = f"{stem}_a{amplitude_index}_Q{Q}.npz"
            sample = samples[(amplitude_index, Q)]
            np.savez_compressed(output / sample_name, **{key: np.asarray(value) for key, value in sample.items()})
    for amplitude_index, amplitude in enumerate(AMPLITUDES):
        for Q in QUADRATURES:
            sample = samples[(amplitude_index, Q)]
            energies = np.asarray(sample["energy_components"])
            axials = np.asarray(sample["axial_components"])
            pops = np.asarray(sample["population"])
            mean_transverse = np.mean(np.sum(energies, axis=1))
            mean_axial = np.mean(np.sum(axials, axis=1))
            mean_population = float(np.mean(pops))
            sample_name = f"{stem}_a{amplitude_index}_Q{Q}.npz"
            for wave_factor in WAVE_FACTORS:
                p = float(wave_factor * p_star)
                for winding in WINDINGS:
                    trial_energy = mean_transverse + p * p * mean_axial + core.K_CX / 2.0 * (winding * p) ** 2 * mean_population
                    baseline = base_energy + core.K_CX / 2.0 * (winding * p) ** 2 * P0
                    delta = float(trial_energy - baseline)
                    Q_A = float(4.0 * delta / (amplitude * amplitude))
                    prediction = float(zeta + B * p * p)
                    prediction_error = abs(Q_A - prediction) / max(1e-10, abs(prediction))
                    population_error = abs(mean_population - P0) / max(1.0, abs(P0))
                    trial = {
                        "amplitude": float(amplitude), "amplitude_index": amplitude_index, "quadrature": Q,
                        "wave_factor": float(wave_factor), "winding": winding, "p": p,
                        "delta_energy_per_length": delta, "Q": Q_A, "quadratic_prediction": prediction,
                        "relative_prediction_error": float(prediction_error), "population_error": float(population_error),
                        "samples_npz": sample_name,
                    }
                    trial_rows.append(trial)
                    if not finite(trial) or prediction_error >= 0.02 or population_error >= 1e-10:
                        failures.append(f"trial_a{amplitude_index}_Q{Q}_wave{wave_factor:g}_w{winding}")
    if len(trial_rows) != 24:
        failures.append("incomplete 24-trial schedule")
    for trial in trial_rows:
        checks.append({"name": f"trial_{trial['amplitude_index']}_{trial['quadrature']}_{trial['wave_factor']}_{trial['winding']}", "prediction_error": trial["relative_prediction_error"], "population_error": trial["population_error"], "pass": trial["relative_prediction_error"] < 0.02 and trial["population_error"] < 1e-10})
    base_arrays = {
        "r": r, "y": y0, "f": f0, "dy": dy, "df": df,
        "field_variation": field_variation,
        "h": h0, "h_direction": h_direction0,
        "B_components": B_values, "B": np.asarray(B), "L_star": np.asarray(L_star), "p_star": np.asarray(p_star),
        "base_components": base_components, "population": np.asarray(P0), "zeta": np.asarray(zeta),
    }
    np.savez_compressed(output / base_name, **base_arrays)
    row = {
        "cap": record["cap"], "epsilon": epsilon, "n": 64.0, "R": R, "N": N, "base_npz": base_name,
        "base_energy": base_energy, "population": P0, "zeta": zeta, "B": B, "B_components": B_values.tolist(),
        "L_star": L_star, "p_star": p_star, "trials": trial_rows, "qualified": not failures,
        "checks": checks, "failures": failures, "exception": None, "complete_physical_matter_formation": False,
    }
    write_json(output / (stem + "_axial.json"), row)
    return row


def run(manifest_path: Path, output: Path) -> int:
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    output.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, Any]] = []
    try:
        _, records, _, _ = validate_manifest(manifest_path)
        for record in records:
            try:
                rows.append(solve_row(output, record))
            except Exception as exc:  # retain a scalar failure receipt for each selected profile
                text = f"{type(exc).__name__}: {exc}"
                row = failed_row(record, text)
                rows.append(row)
                write_json(output / (f"cap_{record['cap']}_n64_N{record['N']}_R{record['R']}_axial.json"), row)
    except Exception as exc:
        rows = []
        error = f"{type(exc).__name__}: {exc}"
        receipt = {
            "schema": SCHEMA, "source": "computations/matter_formation_vortex_axial_energy.py",
            "platform": platform.platform(), "rows": rows, "numerical_pass": False,
            "failures": [error], "exception": error, "complete_physical_matter_formation": False,
        }
        write_json(output / "summary.json", receipt)
        return 1
    numerical_pass = bool(len(rows) == 8 and all(row.get("qualified") is True and row.get("exception") is None for row in rows))
    summary = {
        "schema": SCHEMA, "source": "computations/matter_formation_vortex_axial_energy.py", "platform": platform.platform(),
        "fixed_schedule": [[R, N] for R, N in SCHEDULE], "amplitudes": list(AMPLITUDES),
        "quadratures": list(QUADRATURES), "wave_factors": list(WAVE_FACTORS), "windings": list(WINDINGS),
        "energy_components": list(ENERGY_COMPONENTS), "B_components": list(B_COMPONENTS),
        "rows": rows, "numerical_pass": numerical_pass,
        "complete_physical_matter_formation": False,
    }
    write_json(output / "summary.json", summary)
    return 0 if numerical_pass else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        return run(args.manifest.resolve(), args.output.resolve())
    except Exception as exc:
        print(json.dumps({"schema": SCHEMA, "numerical_pass": False, "exception": f"{type(exc).__name__}: {exc}", "complete_physical_matter_formation": False}, sort_keys=True), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
