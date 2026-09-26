#!/usr/bin/env python3
"""Independent verifier for the conditional hyperbolic carrier-parent calculation.

This program deliberately does not import or inspect the primary implementation.
It reconstructs the frozen schedule, raw input qualifications, mode projections,
Wronskians, energies, analytic tanh benchmark, dispersion identities, stationary
embedding and source-work quadrature from the preregistered artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.integrate import simpson

ROOT = Path(__file__).resolve().parents[1]
RADIAL_ARTIFACTS = {
    "q16_R12_n768_refine": (
        "runs/20260906_matter_formation_radial/q16_R12_n768_refine.npz",
        "335364c4e655de4a34b51c0558c3a7559f45311d7f2973b262de4fd2c61db7be",
    ),
    "q256_R12_n768_refine": (
        "runs/20260906_matter_formation_radial/q256_R12_n768_refine.npz",
        "95df301fcea98304434b95e9dd63a9cec987495ddda9af46e5940891672dc77a",
    ),
}
PREREG_PATH = ROOT / "computations" / "matter-formation-hyperbolic-parent-prereg.md"
PRIMARY_PATH = ROOT / "computations" / "matter_formation_hyperbolic_parent.py"
INPUT_DEFAULT = ROOT / "runs" / "20260906_matter_formation_hyperbolic_parent"
RADIAL_RESULTS = ROOT / "runs" / "20260906_matter_formation_radial" / "results.json"
RADIAL_RESULTS_SHA256 = "3ac6ec265c11d8eed2040c372d8862084be084ad0a640bbe0d8655e06e19a313"

SCHEMA = "cassi.matter-formation.hyperbolic-parent.v1"
VERIFY_SCHEMA = "cassi.matter-formation.hyperbolic-parent.verification.v1"
A_VALUES = (1.0 / 16.0, 1.0 / 32.0, 1.0 / 64.0)
A_DENOMINATORS = (16, 32, 64)
K_VALUES = (0, 1, 2)
T_VALUES = (0.05, 0.25, 1.0)
E_VALUES = (-0.5, 0.0, 0.75, 2.0)
COEFFICIENTS = {"k_Cx": 1.0, "u_C": 1.0, "u_rho": 4.0, "e_C": 0.75, "h_C": 2.9598260763447164}
REQUIRED_NPZ = ("t", "u", "v", "work", "omega2")
REQUIRED_MEASUREMENTS = (
    "omega_in", "omega_out", "alpha_re", "alpha_im", "beta_re", "beta_im",
    "occupation", "occupation_exact", "wronskian_defect", "bogoliubov_defect",
    "energy_initial", "energy_final", "work_final", "energy_work_defect",
)
NUM_TOL = 1.0e-10


def json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def canonical_sha256(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def byte_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float, np.number)) and not isinstance(value, bool) and math.isfinite(float(value))


def close(actual: Any, expected: float, tol: float = NUM_TOL) -> bool:
    return finite_number(actual) and abs(float(actual) - expected) <= tol * max(1.0, abs(expected))


def mismatch(failures: list[dict[str, Any]], path: str, expected: Any, actual: Any, reason: str) -> None:
    failures.append({"path": path, "expected": json_safe(expected), "actual": json_safe(actual), "reason": reason})


def safe_artifact_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        return None
    candidate = (ROOT / path).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return candidate


def expected_id(a_index: int, k: int, T: float, half_span: int, amplitude: int) -> str:
    return f"a{A_DENOMINATORS[a_index]}_k{k}_T{int(round(1000.0 * T))}_L{half_span}_A{amplitude}"


def expected_schedule() -> dict[str, dict[str, Any]]:
    schedule: dict[str, dict[str, Any]] = {}
    for ia, (a, denominator) in enumerate(zip(A_VALUES, A_DENOMINATORS)):
        for k in K_VALUES:
            for T in T_VALUES:
                key = expected_id(ia, k, T, 16, 1)
                schedule[key] = {"a": a, "k": k, "T": T, "amplitude": 1, "half_span": 16}
        key = expected_id(ia, 0, 0.25, 16, 0)
        schedule[key] = {"a": a, "k": 0, "T": 0.25, "amplitude": 0, "half_span": 16}
    key = expected_id(0, 0, 0.05, 24, 1)
    schedule[key] = {"a": A_VALUES[0], "k": 0, "T": 0.05, "amplitude": 1, "half_span": 24}
    return schedule


def omega_limits(a: float, k: int, amplitude: int) -> tuple[float, float]:
    # U_in=e_C and U_out=e_C-h_C A for the declared tanh history.
    base = COEFFICIENTS["k_Cx"] * k * k / (2.0 * a) + 1.0 / (4.0 * a * a)
    return math.sqrt(base + COEFFICIENTS["e_C"] / a), math.sqrt(
        base + (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * amplitude) / a
    )


def analytic_occupation(omega_in: float, omega_out: float, T: float) -> float:
    numerator = math.sinh(math.pi * T * (omega_out - omega_in) / 2.0) ** 2
    denominator = math.sinh(math.pi * T * omega_in) * math.sinh(math.pi * T * omega_out)
    return numerator / denominator


def dispersion_rows() -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for a in A_VALUES:
        for epsilon in E_VALUES:
            root = math.sqrt(1.0 + 4.0 * a * epsilon)
            low = 2.0 * epsilon / (1.0 + root) if epsilon else 0.0
            high = (-1.0 - root) / (2.0 * a)
            rows.append({
                "a": a, "epsilon": epsilon, "omega_low": low, "omega_high": high,
                "norm_low": 1.0 + 2.0 * a * low, "norm_high": 1.0 + 2.0 * a * high,
                "residual_low": a * low * low + low - epsilon,
                "residual_high": a * high * high + high - epsilon,
            })
    return rows


def radial_diagnostics(arrays: Mapping[str, np.ndarray], R: float, q_target: float) -> dict[str, float | bool]:
    r, volumes, f, c = (arrays[name] for name in ("r", "volumes", "f", "c"))
    n = len(r)
    dr = R / n
    conductance = 4.0 * math.pi * (np.arange(1, n, dtype=np.float64) * dr) ** 2 / dr
    outer_conductance = 8.0 * math.pi * R * R / dr
    ef = 0.5 * float(np.sum(conductance * np.diff(f) ** 2))
    ec = 0.5 * float(np.sum(conductance * np.diff(c) ** 2))
    ef += 0.5 * outer_conductance * float((1.0 - f[-1]) ** 2)
    ec += 0.5 * outer_conductance * float(c[-1] ** 2)
    potential = COEFFICIENTS["u_rho"] / 4.0 * (f * f - 1.0) ** 2 + (
        COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f)
    ) * c * c + COEFFICIENTS["u_C"] / 2.0 * c**4
    energy = ef + ec + float(np.dot(volumes, potential))
    charge = float(np.dot(volumes, c * c))
    radius = math.sqrt(max(0.0, float(np.dot(volumes, r * r * c * c)) / charge)) if charge > 0 else math.inf
    outer = float(np.dot(volumes[r > R / 2.0], c[r > R / 2.0] ** 2) / charge) if charge > 0 else math.inf
    grad_f = np.zeros(n, dtype=np.float64)
    grad_c = np.zeros(n, dtype=np.float64)
    if n > 1:
        flux_f, flux_c = conductance * np.diff(f), conductance * np.diff(c)
        grad_f[:-1] -= flux_f; grad_f[1:] += flux_f
        grad_c[:-1] -= flux_c; grad_c[1:] += flux_c
    grad_f[-1] += outer_conductance * (f[-1] - 1.0)
    grad_c[-1] += outer_conductance * c[-1]
    grad_f += volumes * (COEFFICIENTS["u_rho"] * (f * f - 1.0) * f + 2.0 * COEFFICIENTS["h_C"] * c * c * f)
    grad_c += volumes * (2.0 * (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f)) * c + 2.0 * COEFFICIENTS["u_C"] * c**3)
    omega = float(np.dot(c, grad_c) / (2.0 * charge)) if charge > 0 else math.nan
    residual_f, residual_c = grad_f / volumes, grad_c / (2.0 * volumes) - omega * c
    f_scale = math.sqrt(float(np.dot(volumes, (1.0 - f) ** 2)))
    rf_norm = math.sqrt(float(np.dot(volumes, residual_f**2))) / max(1.0, f_scale)
    rc_norm = math.sqrt(float(np.dot(volumes, residual_c**2))) / math.sqrt(charge) if charge > 0 else math.inf
    charge_error = abs(charge - q_target) / max(abs(q_target), 1.0)
    qualified = all(math.isfinite(x) for x in (energy, charge, omega, radius, outer, rf_norm, rc_norm, charge_error)) and charge_error < 1.0e-10 and rf_norm < 1.0e-4 and rc_norm < 1.0e-4
    return {"energy": energy, "charge": charge, "charge_relative_error": charge_error, "omega": omega, "carrier_radius": radius, "outer_fraction": outer, "residual_f": rf_norm, "residual_c": rc_norm, "qualified": bool(qualified), "bound": bool(qualified and energy < COEFFICIENTS["e_C"] * q_target - 1.0e-3 and omega < COEFFICIENTS["e_C"] - 1.0e-3 and outer < 1.0e-3)}


def verify_radial_inputs(failures: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    if not RADIAL_RESULTS.exists():
        mismatch(failures, "radial.results", str(RADIAL_RESULTS), "missing", "infrastructure")
        return selected
    if byte_sha256(RADIAL_RESULTS) != RADIAL_RESULTS_SHA256:
        mismatch(failures, "radial.results_sha256", RADIAL_RESULTS_SHA256, byte_sha256(RADIAL_RESULTS), "hash")
    try:
        payload = json.loads(RADIAL_RESULTS.read_text(encoding="utf-8"))
    except Exception as exc:
        mismatch(failures, "radial.results", "valid JSON", repr(exc), "infrastructure")
        return selected
    if not isinstance(payload, dict):
        mismatch(failures, "radial.results", "object", payload, "schema")
        return selected
    rows = payload.get("arms")
    if not isinstance(rows, list):
        mismatch(failures, "radial.arms", "list", rows, "schema")
        return selected
    by_id: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            mismatch(failures, f"radial.arms[{index}]", "row with string id", row, "schema")
            continue
        if row["id"] in by_id:
            mismatch(failures, f"radial.arms[{index}].id", "unique", row["id"], "identity")
        by_id[row["id"]] = row
    for source_id in RADIAL_ARTIFACTS:
        row = by_id.get(source_id)
        if row is None:
            mismatch(failures, f"radial.{source_id}", "present", "missing", "input qualification")
            continue
        expected_path, expected_hash = RADIAL_ARTIFACTS[source_id]
        if row.get("artifact") != expected_path:
            mismatch(failures, f"radial.{source_id}.artifact", expected_path, row.get("artifact"), "identity")
        artifact = safe_artifact_path(row.get("artifact"))
        if artifact is None or not artifact.exists():
            mismatch(failures, f"radial.{source_id}.artifact", "existing NPZ", row.get("artifact"), "infrastructure")
            continue
        digest = byte_sha256(artifact)
        if expected_hash and digest != expected_hash:
            mismatch(failures, f"radial.{source_id}.artifact_sha256", expected_hash, digest, "hash")
        if row.get("artifact_sha256") != digest:
            mismatch(failures, f"radial.{source_id}.reported_hash", digest, row.get("artifact_sha256"), "hash")
        try:
            with np.load(artifact, allow_pickle=False) as loaded:
                required = ("r", "volumes", "f", "c", "R", "q")
                if any(key not in loaded for key in required):
                    mismatch(failures, f"radial.{source_id}.npz", required, list(loaded.files), "schema")
                    continue
                arrays = {key: np.asarray(loaded[key]) for key in required}
        except Exception as exc:
            mismatch(failures, f"radial.{source_id}.npz", "readable", repr(exc), "infrastructure")
            continue
        if any(arrays[key].ndim != 1 for key in ("r", "volumes", "f", "c")) or len({len(arrays[key]) for key in ("r", "volumes", "f", "c")}) != 1 or any(not np.all(np.isfinite(arrays[key])) for key in ("r", "volumes", "f", "c")) or arrays["R"].ndim != 0 or arrays["q"].ndim != 0 or not np.isfinite(arrays["R"]) or not np.isfinite(arrays["q"]):
            mismatch(failures, f"radial.{source_id}.npz", "finite aligned vectors and scalar R,q", "invalid", "schema/numeric")
            continue
        q_target = 16.0 if source_id.startswith("q16_") else 256.0
        if not close(float(arrays["R"]), 12.0) or not close(float(arrays["q"]), q_target):
            mismatch(failures, f"radial.{source_id}.npz.identity", {"R": 12.0, "q": q_target}, {"R": float(arrays["R"]), "q": float(arrays["q"])}, "identity")
            continue
        diagnostics = radial_diagnostics(arrays, 12.0, q_target)
        reported = row.get("diagnostics")
        if not isinstance(reported, dict):
            mismatch(failures, f"radial.{source_id}.diagnostics", "object", reported, "schema")
        else:
            for key, value in diagnostics.items():
                if key not in reported or (isinstance(value, bool) and reported[key] is not value) or (not isinstance(value, bool) and not close(reported[key], float(value))):
                    mismatch(failures, f"radial.{source_id}.diagnostics.{key}", value, reported.get(key), "recompute")
        if not diagnostics["qualified"] or not diagnostics["bound"]:
            mismatch(failures, f"radial.{source_id}", "qualified bound endpoint", diagnostics, "input qualification")
        selected[source_id] = {"row": row, "diagnostics": diagnostics, "artifact": artifact}
    return selected


def trajectory_measurements(row: Mapping[str, Any], schedule: Mapping[str, Any], artifact: Path, failures: list[dict[str, Any]], label: str) -> dict[str, Any] | None:
    try:
        with np.load(artifact, allow_pickle=False) as loaded:
            missing = [key for key in REQUIRED_NPZ if key not in loaded]
            if missing:
                mismatch(failures, f"{label}.npz.keys", REQUIRED_NPZ, missing, "schema")
                return None
            arrays = {key: np.asarray(loaded[key]) for key in REQUIRED_NPZ}
    except Exception as exc:
        mismatch(failures, f"{label}.artifact", "readable NPZ", repr(exc), "infrastructure")
        return None
    n = 2 * 256 * int(schedule["half_span"]) + 1
    expected_dtype = {"t": np.dtype("float64"), "u": np.dtype("complex128"), "v": np.dtype("complex128"), "work": np.dtype("float64"), "omega2": np.dtype("float64")}
    for key, values in arrays.items():
        if values.ndim != 1 or len(values) != n or values.dtype != expected_dtype[key] or not np.all(np.isfinite(values)):
            mismatch(failures, f"{label}.npz.{key}", {"shape": [n], "dtype": str(expected_dtype[key]), "finite": True}, {"shape": list(values.shape), "dtype": str(values.dtype)}, "schema/numeric")
            return None
    a, k, T, A, half = (float(schedule[x]) for x in ("a", "k", "T", "amplitude", "half_span"))
    t_expected = np.linspace(-half * T, half * T, n, dtype=np.float64)
    if not np.allclose(arrays["t"], t_expected, rtol=0.0, atol=1.0e-14):
        mismatch(failures, f"{label}.t", "uniform preregistered grid", "different", "identity")
    omega2_expected = COEFFICIENTS["k_Cx"] * k * k / (2.0 * a) + 1.0 / (4.0 * a * a) + (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * A * (1.0 + np.tanh(arrays["t"] / T)) / 2.0) / a
    if np.any(omega2_expected <= 0.0) or not np.allclose(arrays["omega2"], omega2_expected, rtol=1.0e-10, atol=1.0e-12):
        mismatch(failures, f"{label}.omega2", "positive declared tanh frequency", "different or nonpositive", "recompute")
    omega_in, omega_out = omega_limits(a, int(k), int(A))
    u0 = np.exp(-1j * omega_in * arrays["t"][0]) / math.sqrt(2.0 * omega_in)
    v0 = -1j * omega_in * u0
    if abs(arrays["u"][0] - u0) > 1.0e-10 * max(1.0, abs(u0)) or abs(arrays["v"][0] - v0) > 1.0e-10 * max(1.0, abs(v0)) or abs(arrays["work"][0]) > 1.0e-12:
        mismatch(failures, f"{label}.initial", "finite-start in-vacuum data and zero work", "different", "recompute")
    u, v = arrays["u"], arrays["v"]
    alpha = np.exp(1j * omega_out * arrays["t"][-1]) * (math.sqrt(omega_out / 2.0) * u[-1] + 1j * v[-1] / math.sqrt(2.0 * omega_out))
    beta = np.exp(-1j * omega_out * arrays["t"][-1]) * (math.sqrt(omega_out / 2.0) * u[-1] - 1j * v[-1] / math.sqrt(2.0 * omega_out))
    occupation = float(abs(beta) ** 2)
    exact = analytic_occupation(omega_in, omega_out, T)
    wronskian = float(np.max(np.abs(1j * (np.conj(u) * v - np.conj(v) * u) - 1.0)))
    bogoliubov = float(abs(abs(alpha) ** 2 - abs(beta) ** 2 - 1.0))
    energy_initial = float(abs(v[0]) ** 2 + arrays["omega2"][0] * abs(u[0]) ** 2)
    energy_final = float(abs(v[-1]) ** 2 + arrays["omega2"][-1] * abs(u[-1]) ** 2)
    work_final = float(arrays["work"][-1])
    domega2 = -COEFFICIENTS["h_C"] * A / (2.0 * a * T) / np.cosh(arrays["t"] / T) ** 2
    work_simpson = float(simpson(domega2 * abs(u) ** 2, x=arrays["t"]))
    energy_work_defect = float(abs(energy_final - energy_initial - work_final))
    if abs(work_simpson - work_final) > 1.0e-7 * max(1.0, abs(work_final)):
        mismatch(failures, f"{label}.work_quadrature", work_final, work_simpson, "independent Simpson mismatch")
    measured = {
        "omega_in": omega_in, "omega_out": omega_out, "alpha_re": float(alpha.real), "alpha_im": float(alpha.imag),
        "beta_re": float(beta.real), "beta_im": float(beta.imag), "occupation": occupation, "occupation_exact": exact,
        "wronskian_defect": wronskian, "bogoliubov_defect": bogoliubov, "energy_initial": energy_initial,
        "energy_final": energy_final, "work_final": work_final, "energy_work_defect": energy_work_defect,
    }
    reported = row.get("measurements")
    if A == 0 and occupation > 1.0e-12:
        mismatch(failures, f"{label}.constant_control", "<=1e-12", occupation, "threshold")
    if not isinstance(reported, dict):
        mismatch(failures, f"{label}.measurements", "object", reported, "schema")
    else:
        for key in REQUIRED_MEASUREMENTS:
            if key not in reported or not close(reported[key], measured[key], 1.0e-10):
                mismatch(failures, f"{label}.measurements.{key}", measured[key], reported.get(key), "recompute")
    if abs(occupation - exact) > 1.0e-10 + 1.0e-7 * exact:
        mismatch(failures, f"{label}.occupation", "analytic agreement", occupation - exact, "threshold")
    if wronskian > 1.0e-8 or bogoliubov > 1.0e-8:
        mismatch(failures, f"{label}.identities", "<=1e-8", {"wronskian": wronskian, "bogoliubov": bogoliubov}, "threshold")
    if abs(energy_work_defect) > 1.0e-8 * max(1.0, abs(energy_initial), abs(energy_final), abs(work_final)):
        mismatch(failures, f"{label}.energy_work", "<= frozen tolerance", energy_work_defect, "threshold")
    return {"id": row.get("id"), **measured, "work_simpson": work_simpson}

def verify(input_dir: Path, output_dir: Path) -> tuple[dict[str, Any], int]:
    failures: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "schema": VERIFY_SCHEMA,
        "input_dir": str(input_dir),
        "algebra": {
            "euler_lagrange": "a*ddot(chi) - i*dot(chi) - (k_Cx/2)*Delta(chi) + (U_C + u_C*|chi|^2)*chi = 0",
            "noether_density": "|chi|^2 - 2*a*Im(conj(chi)*dot(chi))",
            "phase_rotation": "chi = a^(-1/2)*exp(+i*t/(2*a))*phi",
            "canonical_mass_squared": "1/(4*a^2) + U_C/a",
            "canonical_speed_squared": "k_Cx/(2*a)",
            "stationary_embedding": "omega + a*omega^2 = omega_C",
            "signed_charge_factor": "1 + 2*a*omega",
        },
        "failures": failures,
    }
    output_path = output_dir / "verification.json"
    if output_path.exists():
        mismatch(failures, "verification.json", "absent (refuse overwrite)", str(output_path), "infrastructure")
        report.update({"verdict": "FAIL", "pass": False})
        return report, 1
    results_path = input_dir / "results.json"
    if not results_path.exists():
        mismatch(failures, "results.json", "existing primary receipt", str(results_path), "infrastructure")
        report.update({"verdict": "FAIL", "pass": False})
        output_dir.mkdir(parents=True, exist_ok=True)
        with output_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(json_safe(report), stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        return report, 1
    try:
        source = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception as exc:
        mismatch(failures, "results.json", "valid JSON object", repr(exc), "infrastructure")
        source = {}
    if not isinstance(source, dict):
        mismatch(failures, "results", "object", source, "schema")
        source = {}
    if source.get("schema") != SCHEMA:
        mismatch(failures, "schema", SCHEMA, source.get("schema"), "schema")
    expected_prereg = canonical_sha256(PREREG_PATH) if PREREG_PATH.exists() else None
    if source.get("prereg_sha256") != expected_prereg:
        mismatch(failures, "prereg_sha256", expected_prereg, source.get("prereg_sha256"), "hash")
    if not PRIMARY_PATH.exists():
        mismatch(failures, "source_sha256", str(PRIMARY_PATH), "missing", "infrastructure")
    else:
        expected_source = canonical_sha256(PRIMARY_PATH)
        if source.get("source_sha256") != expected_source:
            mismatch(failures, "source_sha256", expected_source, source.get("source_sha256"), "hash")
    if source.get("input_sha256") != RADIAL_RESULTS_SHA256:
        mismatch(failures, "input_sha256", RADIAL_RESULTS_SHA256, source.get("input_sha256"), "hash")
    report["verifier_sha256"] = canonical_sha256(Path(__file__))
    if source.get("verifier_sha256") != report["verifier_sha256"]:
        mismatch(failures, "verifier_sha256", report["verifier_sha256"], source.get("verifier_sha256"), "hash")
    report["versions"] = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": __import__("scipy").__version__,
    }
    report["input_sha256"] = byte_sha256(results_path)
    report["raw_primary_result_sha256"] = report["input_sha256"]
    for key, expected in COEFFICIENTS.items():
        actual = source.get("coefficients", {}).get(key) if isinstance(source.get("coefficients"), dict) else None
        if not close(actual, expected):
            mismatch(failures, f"coefficients.{key}", expected, actual, "frozen coefficient")
    settings = source.get("settings")
    expected_settings = {
        "a_values": list(A_VALUES),
        "k_values": list(K_VALUES),
        "T_values": list(T_VALUES),
        "amplitude": 1.0,
        "half_span": 16.0,
        "window_half_span": 24.0,
        "sample_spacing_factor": 256.0,
        "rtol": 1.0e-11,
        "atol": 1.0e-13,
        "method": "DOP853",
    }
    if not isinstance(settings, dict):
        mismatch(failures, "settings", "object", settings, "schema")
    else:
        for key, expected in expected_settings.items():
            actual = settings.get(key)
            if isinstance(expected, str):
                if actual != expected:
                    mismatch(failures, f"settings.{key}", expected, actual, "frozen setting")
            elif isinstance(expected, list):
                if not isinstance(actual, list) or len(actual) != len(expected) or any(not close(x, y, 1.0e-12) for x, y in zip(actual, expected)):
                    mismatch(failures, f"settings.{key}", expected, actual, "frozen setting")
            elif not close(actual, expected, 1.0e-12):
                mismatch(failures, f"settings.{key}", expected, actual, "frozen setting")
    if not isinstance(source.get("failures"), list):
        mismatch(failures, "failures", "list", source.get("failures"), "schema")
    if not isinstance(source.get("pass"), bool) or not isinstance(source.get("verdict"), str):
        mismatch(failures, "reported_decision", "boolean pass and string verdict", {"pass": source.get("pass"), "verdict": source.get("verdict")}, "schema")
    schedule = expected_schedule()
    rows = source.get("rows")
    if not isinstance(rows, list):
        mismatch(failures, "rows", "list", rows, "schema")
        rows = []
    by_id: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(rows):
        label = f"rows[{index}]"
        if not isinstance(row, dict):
            mismatch(failures, label, "object", row, "schema")
            continue
        rid = row.get("id")
        if rid in by_id:
            mismatch(failures, f"{label}.id", "unique", rid, "identity")
            continue
        by_id[rid] = row
        if rid not in schedule:
            mismatch(failures, f"{label}.id", "expected schedule id", rid, "identity")
            continue
        expected = schedule[rid]
        for key in ("a", "k", "T", "amplitude", "half_span"):
            if not close(row.get(key), float(expected[key])):
                mismatch(failures, f"{label}.{key}", expected[key], row.get(key), "identity")
        artifact = safe_artifact_path(row.get("artifact"))
        if artifact is None or not artifact.exists():
            mismatch(failures, f"{label}.artifact", "existing repo-relative NPZ", row.get("artifact"), "infrastructure")
            continue
        digest = byte_sha256(artifact)
        if row.get("artifact_sha256") != digest:
            mismatch(failures, f"{label}.artifact_sha256", digest, row.get("artifact_sha256"), "hash")
            continue
        reconstructed = trajectory_measurements(row, expected, artifact, failures, label)
        if reconstructed is not None:
            report.setdefault("rows", []).append(reconstructed)
    missing = sorted(set(schedule) - set(by_id))
    extra = sorted(set(by_id) - set(schedule))
    if missing:
        mismatch(failures, "rows.missing", [], missing, "incomplete row set")
    if extra:
        mismatch(failures, "rows.extra", [], extra, "unexpected row set")
    dispersion = source.get("dispersion")
    report["dispersion"] = dispersion_rows()
    if not isinstance(dispersion, list) or len(dispersion) != len(report["dispersion"]):
        mismatch(failures, "dispersion", len(report["dispersion"]), dispersion, "identity")
    else:
        for index, (actual, expected) in enumerate(zip(dispersion, report["dispersion"])):
            if not isinstance(actual, dict):
                mismatch(failures, f"dispersion[{index}]", expected, actual, "schema")
                continue
            for key, value in expected.items():
                if not close(actual.get(key), value, 1.0e-12):
                    mismatch(failures, f"dispersion[{index}].{key}", value, actual.get(key), "recompute")
            if abs(expected["residual_low"]) > 1.0e-12 or abs(expected["residual_high"]) > 1.0e-12 or expected["norm_low"] * expected["norm_high"] >= 0.0:
                mismatch(failures, f"dispersion[{index}]", "quadratic identities and opposite norms", expected, "algebra")
    selected = verify_radial_inputs(failures)
    embeddings = source.get("stationary_embeddings")
    report["stationary_embeddings"] = []
    expected_embeddings = []
    for a in A_VALUES:
        for source_id in RADIAL_ARTIFACTS:
            data = selected.get(source_id)
            if data is None:
                continue
            if data:
                row = data["row"]
                q = 16.0 if source_id.startswith("q16_") else 256.0
                omega_c = float(data["diagnostics"]["omega"])
                omega_parent = 2.0 * omega_c / (1.0 + math.sqrt(1.0 + 4.0 * a * omega_c))
                expected_embeddings.append({
                    "source_id": source_id, "artifact": row.get("artifact"),
                    "artifact_sha256": row.get("artifact_sha256"), "a": a,
                    "Q_C": q, "omega_C": omega_c, "omega_parent": omega_parent,
                    "signed_charge": (1.0 + 2.0 * a * omega_parent) * q,
                })
    if not isinstance(embeddings, list) or len(embeddings) != len(expected_embeddings):
        mismatch(failures, "stationary_embeddings", len(expected_embeddings), embeddings, "schema/identity")
    else:
        expected_map = {(entry["source_id"], entry["a"]): entry for entry in expected_embeddings}
        actual_map = {(entry.get("source_id"), entry.get("a")): entry for entry in embeddings if isinstance(entry, dict)}
        if set(actual_map) != set(expected_map):
            mismatch(failures, "stationary_embeddings.identities", sorted(expected_map), sorted(actual_map), "identity")
        for identity, expected in expected_map.items():
            actual = actual_map.get(identity, {})
            for key, value in expected.items():
                if isinstance(value, str):
                    if actual.get(key) != value:
                        mismatch(failures, f"stationary_embeddings[{identity}].{key}", value, actual.get(key), "identity")
                elif not close(actual.get(key), value, 1.0e-10):
                    mismatch(failures, f"stationary_embeddings[{identity}].{key}", value, actual.get(key), "recompute")
        report["stationary_embeddings"] = expected_embeddings
    comparisons = source.get("comparisons")
    report["comparisons"] = {}
    if not isinstance(comparisons, dict):
        mismatch(failures, "comparisons", "object", comparisons, "schema")
    else:
        fast_id = expected_id(0, 0, 0.05, 16, 1)
        slow_id = expected_id(0, 0, 0.05, 24, 1)
        values = {entry.get("id"): entry for entry in report.get("rows", [])}
        fast = values.get(fast_id, {}).get("occupation")
        slow = values.get(slow_id, {}).get("occupation")
        if finite_number(fast) and finite_number(slow):
            twodiff = abs(float(fast) - float(slow))
            report["comparisons"]["time_window_occupation_difference"] = twodiff
            if not close(comparisons.get("time_window_occupation_difference"), twodiff, 1.0e-10) or twodiff > 1.0e-9:
                mismatch(failures, "comparisons.time_window_occupation_difference", twodiff, comparisons.get("time_window_occupation_difference"), "threshold/recompute")
        for key in ("fast_witness_occupation",):
            value = values.get(expected_id(0, 0, 0.05, 16, 1), {}).get("occupation")
            report["comparisons"][key] = value
            if finite_number(value) and (not close(comparisons.get(key), float(value), 1.0e-10) or float(value) <= 1.0e-4):
                mismatch(failures, f"comparisons.{key}", value, comparisons.get(key), "threshold/recompute")
        adiabatic = []
        for a_index, a in enumerate(A_VALUES):
            for k in K_VALUES:
                fast_row = values.get(expected_id(a_index, k, 0.05, 16, 1), {})
                slow_row = values.get(expected_id(a_index, k, 1.0, 16, 1), {})
                difference = float(fast_row.get("occupation", math.nan) - slow_row.get("occupation", math.nan))
                adiabatic.append({"a": a, "k": k, "fast_minus_slow": difference})
                if not (difference > 1.0e-9): mismatch(failures, f"comparisons.adiabatic[{a},{k}]", ">1e-9", difference, "threshold")
        report["comparisons"]["adiabatic_differences"] = adiabatic
        reported_adiabatic = comparisons.get("adiabatic_differences")
        if not isinstance(reported_adiabatic, list) or len(reported_adiabatic) != len(adiabatic):
            mismatch(failures, "comparisons.adiabatic_differences", adiabatic, reported_adiabatic, "schema")
        else:
            for index, (actual, expected) in enumerate(zip(reported_adiabatic, adiabatic)):
                if not isinstance(actual, dict) or any(
                    not close(actual.get(key), value) for key, value in expected.items()
                ):
                    mismatch(failures, f"comparisons.adiabatic_differences[{index}]", expected, actual, "recompute")
    if source.get("pass") is True and source.get("failures"):
        mismatch(failures, "reported.failures", [], source.get("failures"), "false pass flag")
    independent_pass = not failures
    expected_verdict = "PASS" if independent_pass else "FAIL"
    if source.get("verdict") != expected_verdict:
        mismatch(failures, "reported.verdict", expected_verdict, source.get("verdict"), "false pass flag")
    if source.get("pass") is not independent_pass:
        mismatch(failures, "reported.pass", independent_pass, source.get("pass"), "false pass flag")
    report["verdict"] = "PASS" if not failures else "FAIL"
    report["pass"] = not failures
    output_dir.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(json_safe(report), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return report, 0 if report["pass"] else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=INPUT_DEFAULT)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    output_dir = args.output_dir if args.output_dir is not None else args.input_dir
    return verify(args.input_dir.resolve(), output_dir.resolve())[1]


if __name__ == "__main__":
    raise SystemExit(main())
