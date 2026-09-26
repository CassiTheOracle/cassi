#!/usr/bin/env python3
"""Independent verifier for fixed-signed-charge radial stability evidence.

The verifier has no dependency on the primary implementation.  It rebuilds the
finite-volume source diagnostics and the amplitude operator in interleaved
coordinates, then checks the primary's blocked-coordinate spectra and receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.linalg import eig_banded, solve_banded

ROOT = Path(__file__).resolve().parents[1]
PREREG_PATH = ROOT / "computations" / "matter-formation-charged-stability-prereg.md"
PRIMARY_PATH = ROOT / "computations" / "matter_formation_charged_stability.py"
SELF_PATH = ROOT / "computations" / "verify_matter_formation_charged_stability.py"
DEFAULT_SOURCE_DIR = ROOT / "runs" / "20260906_matter_formation_radial"
DEFAULT_OUTPUT_DIR = ROOT / "runs" / "20260906_matter_formation_charged_stability"
SCHEMA = "cassi.matter-formation.charged-stability.v1"
VERIFY_SCHEMA = "cassi.matter-formation.charged-stability.verification.v1"
COEFFICIENTS = {"u_rho": 4.0, "u_C": 1.0, "k_Cx": 1.0, "e_C": 0.75, "h_C": 2.9598260763447164}
A_VALUES = (1.0 / 64.0, 1.0 / 32.0, 1.0 / 16.0)
A_DENOMINATORS = (64, 32, 16)
DILATIONS = (0.5, 0.75, 1.0, 1.25, 1.5)
EIGEN_COUNT = 6
SOURCE_IDS = (
    "q16_R12_n192_w2", "q16_R12_n384_refine", "q16_R12_n768_refine", "q16_R24_n768_refine",
    "q256_R12_n192_w2", "q256_R12_n384_refine", "q256_R12_n768_refine", "q256_R24_n768_refine",
)
SOURCE_HASHES = {
    "q16_R12_n192_w2": "52540cf2cc11fcb313ecf689ffb5115c72480813cb7c866f348050bee33ad777",
    "q16_R12_n384_refine": "2e21fa2158d7fc7f9bff65bf337558af1bc0ca76520ea441611b37ab91e9d770",
    "q16_R12_n768_refine": "335364c4e655de4a34b51c0558c3a7559f45311d7f2973b262de4fd2c61db7be",
    "q16_R24_n768_refine": "92c49919d8fb748dffb7a9e3d4ba497214beb883fb837195dcc8a321ec06096b",
    "q256_R12_n192_w2": "ce3d7efcf133fd2fd5776203a86d53469f4b91b4919ca1bbdcce054dc02233ba",
    "q256_R12_n384_refine": "e450c22a6baf8312fa67ca58745ad593879bf6d18615a83ad0cbe8dacabb11d5",
    "q256_R12_n768_refine": "95df301fcea98304434b95e9dd63a9cec987495ddda9af46e5940891672dc77a",
    "q256_R24_n768_refine": "7f839b59fa3a0a4c9ca6897ec3962aec2b7f62d20a1751968482349a22742b66",
}
RAW_KEYS = ("r", "volumes", "f", "c", "R", "q")
SPECTRAL_KEYS = (
    "base_eigenvalues", "base_vectors", "response",
    "parent_a64_values", "parent_a64_vectors", "parent_a32_values", "parent_a32_vectors",
    "parent_a16_values", "parent_a16_vectors",
)
NUM_TOL = 1.0e-8
EIG_MATCH_FACTOR = 1.0e-7
EIG_RESIDUAL_TOL = 1.0e-8
RESPONSE_TOL = 1.0e-8
SOURCE_POP_TOL = 1.0e-10
SOURCE_RES_TOL = 1.0e-4


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def byte_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def relpath(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return os.path.relpath(path.resolve(), ROOT.resolve()).replace("\\", "/")


def safe_relpath(value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    p = Path(value)
    if p.is_absolute() or any(part in ("..", "") for part in p.parts):
        return None
    return p


def finite(value: Any) -> bool:
    return isinstance(value, (int, float, np.number)) and not isinstance(value, bool) and math.isfinite(float(value))


def close(a: Any, b: Any, tol: float = NUM_TOL) -> bool:
    return finite(a) and finite(b) and abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))


def json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_safe(v) for v in value]
    return value


def fail(failures: list[str], message: str) -> None:
    failures.append(str(message))


def write_receipt(path: Path, report: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing existing verification receipt: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(json_safe(dict(report)), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    os.replace(temporary, path)


def geometry(R: float, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dr = R / n
    faces = np.arange(n + 1, dtype=np.float64) * dr
    r = (np.arange(n, dtype=np.float64) + 0.5) * dr
    volumes = (4.0 * math.pi / 3.0) * (faces[1:] ** 3 - faces[:-1] ** 3)
    return r, volumes, faces


def source_metrics(arrays: Mapping[str, np.ndarray], R: float, q_target: float) -> dict[str, float | bool]:
    r, V, f, c = (arrays[k] for k in ("r", "volumes", "f", "c"))
    n = len(f)
    dr = R / n
    internal = 4.0 * math.pi * (np.arange(1, n, dtype=np.float64) * dr) ** 2 / dr
    outer = 8.0 * math.pi * R * R / dr
    df, dc = np.diff(f), np.diff(c)
    gradient = 0.5 * float(np.dot(internal, df * df + dc * dc)) + 0.5 * outer * ((f[-1] - 1.0) ** 2 + c[-1] ** 2)
    A = COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f)
    potential = float(np.dot(V, COEFFICIENTS["u_rho"] / 4.0 * (f * f - 1.0) ** 2 + A * c * c + COEFFICIENTS["u_C"] / 2.0 * c**4))
    energy = gradient + potential
    Kf = np.zeros(n, dtype=np.float64); Kc = np.zeros(n, dtype=np.float64)
    if n > 1:
        fluxf, fluxc = internal * np.diff(f), internal * np.diff(c)
        Kf[:-1] -= fluxf; Kf[1:] += fluxf; Kc[:-1] -= fluxc; Kc[1:] += fluxc
    Kf[-1] += outer * (f[-1] - 1.0); Kc[-1] += outer * c[-1]
    Kf += V * (COEFFICIENTS["u_rho"] * f * (f * f - 1.0) + 2.0 * COEFFICIENTS["h_C"] * f * c * c)
    Kc += V * (2.0 * A * c + 2.0 * COEFFICIENTS["u_C"] * c**3)
    N = float(np.dot(V, c * c))
    omega = float(np.dot(c, Kc) / (2.0 * N)) if N > 0.0 else math.nan
    rf, rc = Kf / V, Kc / (2.0 * V) - omega * c
    residual_f = math.sqrt(float(np.dot(V, rf * rf))) / max(1.0, math.sqrt(float(np.dot(V, (1.0 - f) ** 2))))
    residual_c = math.sqrt(float(np.dot(V, rc * rc))) / math.sqrt(N) if N > 0.0 else math.inf
    pop_error = abs(N - q_target) / max(abs(q_target), 1.0)
    source_qualified = bool(all(math.isfinite(x) for x in (N, omega, energy, gradient, potential, residual_f, residual_c, pop_error)) and pop_error < SOURCE_POP_TOL and residual_f < SOURCE_RES_TOL and residual_c < SOURCE_RES_TOL)
    return {"norm": N, "energy": energy, "gradient": gradient, "potential": potential, "omega_C": omega, "residual_f": residual_f, "residual_c": residual_c, "population_error": pop_error, "eta": max(5.0e-4, 10.0 * residual_f, 10.0 * residual_c), "source_qualified": source_qualified, "r": r, "V": V, "f": f, "c": c}


def banded_operator(metrics: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    f, c, V = metrics["f"], metrics["c"], metrics["V"]
    n = len(f); R = float(metrics["R"]); dr = R / n
    faces = np.arange(n + 1, dtype=np.float64) * dr
    conductance = 4.0 * math.pi * faces[1:-1] ** 2 / dr if n > 1 else np.empty(0)
    diagK = np.zeros(n, dtype=np.float64)
    if n > 1:
        diagK[:-1] += conductance; diagK[1:] += conductance
    diagK[-1] += 8.0 * math.pi * R * R / dr
    invsqrt = 1.0 / np.sqrt(V)
    d0 = diagK * invsqrt * invsqrt
    off = -conductance / (np.sqrt(V[:-1]) * np.sqrt(V[1:]))
    hff = d0 + COEFFICIENTS["u_rho"] * (3.0 * f * f - 1.0) + 2.0 * COEFFICIENTS["h_C"] * c * c
    hcc = COEFFICIENTS["k_Cx"] * d0 + 2.0 * (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f) - metrics["omega_C"]) + 6.0 * COEFFICIENTS["u_C"] * c * c
    mixed = 4.0 * COEFFICIENTS["h_C"] * f * c
    m = 2 * n
    ab = np.zeros((5, m), dtype=np.float64)
    ab[2, 0::2] = hff; ab[2, 1::2] = hcc
    ab[1, 1::2] = mixed; ab[3, 0::2] = mixed
    if n > 1:
        ab[0, 2::2] = off
        ab[0, 3::2] = off
        ab[4, 0:-2:2] = off
        ab[4, 1:-2:2] = off
    g = np.zeros(m, dtype=np.float64); g[1::2] = 2.0 * np.sqrt(V) * c
    return ab, g, off


def banded_mv(ab: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Multiply a symmetric five-diagonal ``solve_banded`` matrix."""
    m = x.size
    y = ab[2] * x
    if m > 1:
        y[1:] += ab[3, :-1] * x[:-1]
        y[:-1] += ab[1, 1:] * x[1:]
    if m > 2:
        y[2:] += ab[4, :-2] * x[:-2]
        y[:-2] += ab[0, 2:] * x[2:]
    return y


def bracket(
    ab: np.ndarray, g: np.ndarray, gamma: float, lam: float,
    base_values: np.ndarray, index: int,
) -> dict[str, Any]:
    delta = 1.0e-7 * max(1.0, abs(lam))
    details = []
    ok = True
    for side, shift in (("minus", lam - delta), ("plus", lam + delta)):
        shifted = np.array(ab, copy=True)
        shifted[2] -= shift
        try:
            sol = solve_banded((2, 2), shifted, g, check_finite=True)
            residual = float(np.linalg.norm(banded_mv(shifted, sol) - g) / max(1.0, np.linalg.norm(g)))
            factor = float(1.0 + gamma * np.dot(g, sol))
            count = int(np.count_nonzero(base_values < shift) - (1 if factor < 0.0 else 0))
            valid = (
                np.all(np.isfinite(sol)) and math.isfinite(factor)
                and factor != 0.0 and math.isfinite(residual)
                and residual < RESPONSE_TOL
            )
            ok = ok and valid
        except Exception as exc:
            residual, factor, count = math.inf, math.nan, -1
            ok = False
            details.append({
                "side": side, "shift": shift, "count": count,
                "factor": factor, "solve_residual": residual,
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue
        details.append({
            "side": side, "shift": shift, "count": count,
            "factor": factor, "solve_residual": residual,
        })
    if len(details) == 2:
        ok = ok and details[0]["count"] <= index and details[1]["count"] > index
    return {
        "lambda": lam, "delta": delta,
        "minus": details[0] if details else {},
        "plus": details[1] if len(details) > 1 else {},
        "pass": bool(ok),
    }


def load_raw(source_dir: Path, failures: list[str]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for ident in SOURCE_IDS:
        path = source_dir / f"{ident}.npz"
        expected_q = 16.0 if ident.startswith("q16_") else 256.0
        if not path.exists(): fail(failures, f"{ident}: missing source artifact"); continue
        actual = byte_sha256(path)
        if actual != SOURCE_HASHES[ident]: fail(failures, f"{ident}: raw artifact hash mismatch"); continue
        try:
            with np.load(path, allow_pickle=False) as archive:
                if tuple(archive.files) != RAW_KEYS: fail(failures, f"{ident}: raw NPZ keys mismatch"); continue
                arrays = {key: np.asarray(archive[key]) for key in RAW_KEYS}
        except Exception as exc:
            fail(failures, f"{ident}: unreadable source artifact ({exc})"); continue
        if any(arrays[k].dtype != np.dtype("float64") for k in RAW_KEYS) or any(arrays[k].ndim != 1 for k in ("r", "volumes", "f", "c")) or arrays["R"].ndim != 0 or arrays["q"].ndim != 0:
            fail(failures, f"{ident}: raw NPZ shape/dtype mismatch"); continue
        n = arrays["f"].size; R = float(arrays["R"])
        if arrays["r"].shape != (n,) or arrays["volumes"].shape != (n,) or arrays["c"].shape != (n,) or not all(np.all(np.isfinite(arrays[k])) for k in RAW_KEYS) or R not in (12.0, 24.0) or float(arrays["q"]) != expected_q:
            fail(failures, f"{ident}: malformed/nonfinite raw fields"); continue
        er, ev, _ = geometry(R, n)
        if not np.array_equal(arrays["r"], er) or not np.array_equal(arrays["volumes"], ev): fail(failures, f"{ident}: geometry mismatch"); continue
        metrics = source_metrics(arrays, R, expected_q); metrics["R"] = R; metrics["n"] = n; metrics["artifact"] = path
        selected[ident] = metrics
    return selected


def preflight_spectra(input_dir: Path, source_dir: Path, rows_by_id: Mapping[str, Any], failures: list[str]) -> None:
    """Reject primary spectral identity/schema defects before any eigensolve."""
    expected_n = {
        "q16_R12_n192_w2": 192, "q16_R12_n384_refine": 384,
        "q16_R12_n768_refine": 768, "q16_R24_n768_refine": 768,
        "q256_R12_n192_w2": 192, "q256_R12_n384_refine": 384,
        "q256_R12_n768_refine": 768, "q256_R24_n768_refine": 768,
    }
    for ident in SOURCE_IDS:
        row = rows_by_id.get(ident)
        if not isinstance(row, dict):
            fail(failures, f"{ident}: primary row missing")
            continue
        expected_artifact = relpath(source_dir / f"{ident}.npz")
        if row.get("artifact") != expected_artifact or row.get("artifact_sha256") != SOURCE_HASHES[ident]:
            fail(failures, f"{ident}: primary source identity schema mismatch")
        spec = row.get("spectra")
        path = safe_relpath(spec.get("path") if isinstance(spec, dict) else None)
        if path is None or path.parts != (f"spectra_{ident}.npz",):
            fail(failures, f"{ident}: spectra path schema mismatch")
            continue
        artifact = input_dir / path
        if not artifact.exists():
            fail(failures, f"{ident}: spectra artifact missing")
            continue
        digest = byte_sha256(artifact)
        if not isinstance(spec, dict) or spec.get("sha256") != digest:
            fail(failures, f"{ident}: spectra identity mismatch")
        try:
            with np.load(artifact, allow_pickle=False) as archive:
                if tuple(archive.files) != SPECTRAL_KEYS:
                    fail(failures, f"{ident}: spectra keys mismatch")
                    continue
                arrays = {key: np.asarray(archive[key]) for key in SPECTRAL_KEYS}
        except Exception as exc:
            fail(failures, f"{ident}: unreadable spectra ({exc})")
            continue
        n = expected_n[ident]; m = 2 * n
        expected_shapes = {
            "base_eigenvalues": (6,), "base_vectors": (m, 6), "response": (m,),
            "parent_a64_values": (6,), "parent_a64_vectors": (m, 6),
            "parent_a32_values": (6,), "parent_a32_vectors": (m, 6),
            "parent_a16_values": (6,), "parent_a16_vectors": (m, 6),
        }
        if any(arrays[k].dtype != np.dtype("float64") or arrays[k].shape != expected_shapes[k] for k in SPECTRAL_KEYS):
            fail(failures, f"{ident}: spectra shape/dtype mismatch")
        elif not all(np.all(np.isfinite(arrays[k])) for k in SPECTRAL_KEYS):
            fail(failures, f"{ident}: nonfinite spectra")
def compare_value(failures: list[str], label: str, expected: Any, actual: Any, tol: float = NUM_TOL) -> None:
    if not close(expected, actual, tol): fail(failures, f"{label}: primary={actual!r}, independent={expected!r}")


def verify(input_dir: Path, source_dir: Path, output_dir: Path) -> tuple[dict[str, Any], int]:
    receipt_path = output_dir / "verification.json"
    if receipt_path.exists() or receipt_path.with_name(receipt_path.name + ".tmp").exists():
        raise FileExistsError(f"refusing existing verification receipt: {receipt_path}")
    failures: list[str] = []; primary: Mapping[str, Any] = {}
    primary_receipt = input_dir / "results.json"
    if not primary_receipt.exists(): fail(failures, "primary results.json missing")
    else:
        try: loaded = json.loads(primary_receipt.read_text(encoding="utf-8")); primary = loaded if isinstance(loaded, dict) else {}
        except Exception as exc: fail(failures, f"primary receipt unreadable: {exc}")
    identities = primary.get("identities", {}) if isinstance(primary, dict) else {}
    expected_identities = {
        "primary": {"path": relpath(PRIMARY_PATH), "sha256": canonical_sha256(PRIMARY_PATH) if PRIMARY_PATH.exists() else ""},
        "verifier": {"path": relpath(SELF_PATH), "sha256": canonical_sha256(SELF_PATH)},
        "preregistration": {"path": relpath(PREREG_PATH), "sha256": canonical_sha256(PREREG_PATH) if PREREG_PATH.exists() else ""},
    }
    if primary.get("schema") != SCHEMA: fail(failures, "primary schema mismatch")
    if identities != expected_identities: fail(failures, "primary identity chain mismatch")
    expected_input = relpath(source_dir)
    try:
        source_dir.resolve().relative_to(ROOT.resolve())
    except ValueError:
        fail(failures, "source directory must be repository-relative")
    if primary.get("input_directory") != expected_input:
        fail(failures, "primary input_directory mismatch")
    if primary.get("coefficients") != COEFFICIENTS:
        fail(failures, "primary coefficients mismatch")
    rows_primary = primary.get("rows")
    if not isinstance(rows_primary, list) or tuple(row.get("id") for row in rows_primary if isinstance(row, dict)) != SOURCE_IDS:
        fail(failures, "primary row schedule mismatch")
    if not isinstance(primary.get("failures"), list) or primary["failures"] != [] or primary.get("numerical_pass") is not True:
        fail(failures, "primary receipt is not numerical PASS")
    rows_by_id = {row.get("id"): row for row in rows_primary if isinstance(row, dict)} if isinstance(rows_primary, list) else {}
    # Identity/schema failures are terminal before any source loading or eigensolve.
    if not failures:
        preflight_spectra(input_dir, source_dir, rows_by_id, failures)
    raw = load_raw(source_dir, failures) if not failures else {}
    independent_rows: list[dict[str, Any]] = []; row_data: dict[str, dict[str, Any]] = {}
    for ident in SOURCE_IDS:
        p = rows_by_id.get(ident); met = raw.get(ident)
        if p is None or met is None:
            continue
        row_start = len(failures)
        n = int(met["n"]); V = met["V"]; f = met["f"]; c = met["c"]
        expected_artifact = relpath(met["artifact"])
        if p.get("artifact") != expected_artifact or p.get("artifact_sha256") != SOURCE_HASHES[ident]:
            fail(failures, f"{ident}: primary source artifact identity mismatch")
        expected_population = 16 if ident.startswith("q16_") else 256
        if p.get("R") != float(met["R"]) or p.get("n") != n or p.get("target_population") != expected_population:
            fail(failures, f"{ident}: primary grid/population identity mismatch")
        for key in ("norm", "energy", "gradient", "potential", "omega_C", "residual_f", "residual_c", "eta"):
            compare_value(failures, f"{ident}.{key}", met[key], p.get(key))
        if p.get("source_qualified") is not bool(met["source_qualified"]):
            fail(failures, f"{ident}.source_qualified mismatch")
        ab, g, _ = banded_operator(met); m = 2 * n
        try:
            base_values, base_vectors_i = eig_banded(ab[:3], lower=False, eigvals_only=False, check_finite=True)
            response_i = solve_banded((2, 2), ab, g, check_finite=True)
            response_resid = float(np.linalg.norm(banded_mv(ab, response_i) - g) / max(1.0, np.linalg.norm(g)))
        except Exception as exc:
            fail(failures, f"{ident}: base/response solve failed ({exc})"); continue
        response_scalar = float(np.dot(g, response_i))
        base_res = [float(np.linalg.norm(banded_mv(ab, base_vectors_i[:, j]) - base_values[j] * base_vectors_i[:, j]) / max(1.0, abs(base_values[j]))) for j in range(6)]
        base = {"eigenvalues": base_values[:6].tolist(), "eigenpair_residuals": base_res, "orthonormality_error": float(np.max(np.abs(base_vectors_i[:, :6].T @ base_vectors_i[:, :6] - np.eye(6)))), "negative_count": int(np.count_nonzero(base_values[:6] < -float(met["eta"]))), "unresolved_count": int(np.count_nonzero(np.abs(base_values[:6]) <= float(met["eta"]))), "inertia_qualified": bool(base_values[5] > met["eta"] and np.count_nonzero(np.abs(base_values[:6]) <= met["eta"]) == 0), "response_scalar": response_scalar, "response_residual": response_resid}
        base_numerical = bool(max(base_res) < EIG_RESIDUAL_TOL and base["orthonormality_error"] < EIG_RESIDUAL_TOL and response_resid < RESPONSE_TOL)
        if not base_numerical:
            fail(failures, f"{ident}: independent base numerical qualification failed")
        for field, independent in base.items():
            actual = (p.get("base") or {}).get(field)
            if isinstance(independent, list):
                if not isinstance(actual, list) or len(actual) != len(independent):
                    fail(failures, f"{ident}.base.{field}: primary shape mismatch")
                else:
                    for j, value in enumerate(independent):
                        compare_value(failures, f"{ident}.base.{field}[{j}]", value, actual[j], EIG_MATCH_FACTOR if field == "eigenvalues" else NUM_TOL)
            elif isinstance(independent, bool):
                if actual is not independent:
                    fail(failures, f"{ident}.base.{field}: primary boolean mismatch")
            else:
                compare_value(failures, f"{ident}.base.{field}", independent, actual)
        spectra_path = safe_relpath((p.get("spectra") or {}).get("path"))
        if spectra_path is None or spectra_path.parts != (f"spectra_{ident}.npz",):
            fail(failures, f"{ident}: spectra path mismatch")
            continue
        spectrum_file = input_dir / spectra_path
        if not spectrum_file.exists(): fail(failures, f"{ident}: spectra artifact missing"); continue
        spectrum_hash = byte_sha256(spectrum_file)
        if (p.get("spectra") or {}).get("sha256") != spectrum_hash: fail(failures, f"{ident}: spectra hash mismatch")
        try:
            with np.load(spectrum_file, allow_pickle=False) as archive:
                if tuple(archive.files) != SPECTRAL_KEYS: fail(failures, f"{ident}: spectra keys mismatch"); continue
                sa = {key: np.asarray(archive[key]) for key in SPECTRAL_KEYS}
        except Exception as exc: fail(failures, f"{ident}: unreadable spectra ({exc})"); continue
        if any(a.dtype != np.dtype("float64") for a in sa.values()) or sa["base_eigenvalues"].shape != (6,) or sa["base_vectors"].shape != (m, 6) or sa["response"].shape != (m,): fail(failures, f"{ident}: spectra shape/dtype mismatch"); continue
        if not all(np.all(np.isfinite(a)) for a in sa.values()): fail(failures, f"{ident}: nonfinite spectra"); continue
        if not np.allclose(sa["base_vectors"].T @ sa["base_vectors"], np.eye(6), rtol=0.0, atol=1.0e-8): fail(failures, f"{ident}: primary base vectors not orthonormal")
        for j in range(6):
            v = np.empty(m); v[0::2] = sa["base_vectors"][:n, j]; v[1::2] = sa["base_vectors"][n:, j]
            compare_value(failures, f"{ident}.base_eigenvalues[{j}]", base_values[j], sa["base_eigenvalues"][j], EIG_MATCH_FACTOR)
            if np.linalg.norm(banded_mv(ab, v) - sa["base_eigenvalues"][j] * v) / max(1.0, abs(sa["base_eigenvalues"][j])) >= EIG_RESIDUAL_TOL: fail(failures, f"{ident}: primary base eigenpair residual")
        response_p = np.empty(m); response_p[0::2] = sa["response"][:n]; response_p[1::2] = sa["response"][n:]
        compare_value(failures, f"{ident}.response_scalar", response_scalar, p.get("base", {}).get("response_scalar"))
        if np.linalg.norm(response_p - response_i) / max(1.0, np.linalg.norm(response_i)) >= RESPONSE_TOL: fail(failures, f"{ident}: primary response mismatch")
        parent_rows = p.get("parents"); parent_data = []
        if not isinstance(parent_rows, list) or len(parent_rows) != 3: fail(failures, f"{ident}: parent schedule mismatch"); continue
        for ia, (a, den) in enumerate(zip(A_VALUES, A_DENOMINATORS)):
            pp = parent_rows[ia] if isinstance(parent_rows[ia], dict) else {}
            D = 1.0 + 4.0 * a * met["omega_C"]
            if not finite(D) or D <= 0.0 or not finite(met["norm"]) or float(met["norm"]) <= 0.0:
                fail(failures, f"{ident}.parent_a{den}: invalid positive-branch embedding")
                continue
            r = math.sqrt(D)
            Q = r * met["norm"]
            gamma = D / (2.0 * a * met["norm"])
            slope = 1.0 + gamma * response_scalar
            deriv = 2.0 * a * met["norm"] + D * response_scalar
            key = f"parent_a{den}"
            vals, vecs = sa[f"{key}_values"], sa[f"{key}_vectors"]
            if vals.shape != (6,) or vecs.shape != (m, 6):
                fail(failures, f"{ident}: {key} shape mismatch")
                continue
            vecs_i = np.empty_like(vecs)
            vecs_i[0::2, :] = vecs[:n, :]
            vecs_i[1::2, :] = vecs[n:, :]
            Hq = lambda x: banded_mv(ab, x) + gamma * g * float(np.dot(g, x))
            pres = [float(np.linalg.norm(Hq(vecs_i[:, j]) - vals[j] * vecs_i[:, j]) / max(1.0, abs(vals[j]))) for j in range(6)]
            orth = float(np.max(np.abs(vecs_i.T @ vecs_i - np.eye(6))))
            brackets = [bracket(ab, g, gamma, float(vals[j]), base_values, j) for j in range(6)]
            bracket_ok = all(b["pass"] for b in brackets)
            for field, value in (
                ("a", a), ("D", D), ("r", r),
                ("omega", 2.0 * met["omega_C"] / (1.0 + r)),
                ("signed_charge", Q), ("gamma", gamma),
                ("slope_factor", slope), ("charge_derivative", deriv),
            ):
                compare_value(failures, f"{ident}.{key}.{field}", value, pp.get(field))
            applicable = bool(base["inertia_qualified"] and base["negative_count"] == 1)
            predicts = (slope < 0.0) if applicable else None
            if pp.get("slope_applicable") is not applicable or pp.get("slope_predicts_positive") != predicts:
                fail(failures, f"{ident}.{key}: slope precondition mismatch")
            slope_consistent = not (
                (vals[0] > met["eta"] and applicable and predicts is False)
                or (vals[0] < -met["eta"] and applicable and predicts is True)
            )
            if not slope_consistent:
                fail(failures, f"{ident}.{key}: slope prediction contradicts spectrum")
            if not isinstance(pp.get("eigenvalues"), list) or len(pp["eigenvalues"]) != 6:
                fail(failures, f"{ident}.{key}.eigenvalues: primary shape mismatch")
            else:
                for j in range(6):
                    compare_value(failures, f"{ident}.{key}.eigenvalues[{j}]", vals[j], pp["eigenvalues"][j], EIG_MATCH_FACTOR)
            if not isinstance(pp.get("eigenpair_residuals"), list) or len(pp["eigenpair_residuals"]) != 6:
                fail(failures, f"{ident}.{key}.eigenpair_residuals: primary shape mismatch")
            else:
                for j in range(6):
                    compare_value(failures, f"{ident}.{key}.eigenpair_residuals[{j}]", pres[j], pp["eigenpair_residuals"][j])
            compare_value(failures, f"{ident}.{key}.orthonormality_error", orth, pp.get("orthonormality_error"))
            dilation = [{"lambda": lam, "energy": met["gradient"] * lam + lam**3 * (met["potential"] + met["norm"] / (4.0 * a)) - Q / (2.0 * a) + Q * Q / (4.0 * a * met["norm"]) * lam**-3} for lam in DILATIONS]
            if not isinstance(pp.get("dilation"), list) or len(pp["dilation"]) != 5:
                fail(failures, f"{ident}.{key}: dilation schema mismatch")
            else:
                for k, d in enumerate(dilation):
                    compare_value(failures, f"{ident}.{key}.dilation[{k}].lambda", d["lambda"], pp["dilation"][k].get("lambda"))
                    compare_value(failures, f"{ident}.{key}.dilation[{k}].energy", d["energy"], pp["dilation"][k].get("energy"))
            parent_numerical = bool(max(pres) < EIG_RESIDUAL_TOL and orth < EIG_RESIDUAL_TOL and bracket_ok)
            if not parent_numerical:
                fail(failures, f"{ident}.{key}: independent parent numerical qualification failed")
            pmin = float(vals[0])
            parent_ok = bool(met["source_qualified"] and base["inertia_qualified"] and base_numerical and parent_numerical and slope_consistent)
            parent_verdict = (
                "INCONCLUSIVE—finite-grid radial fixed-charge energetic stability"
                if not parent_ok or abs(pmin) <= float(met["eta"]) else
                ("SUPPORTS—finite-grid radial fixed-charge energetic stability" if pmin > float(met["eta"]) else "CONTRADICTS—finite-grid radial fixed-charge energetic stability")
            )
            if pp.get("radial_verdict") != parent_verdict:
                fail(failures, f"{ident}.{key}.radial_verdict mismatch")
            parent_data.append({
                "a": a, "D": D, "r": r, "omega": 2.0 * met["omega_C"] / (1.0 + r),
                "signed_charge": Q, "gamma": gamma, "slope_factor": slope,
                "charge_derivative": deriv, "slope_applicable": applicable,
                "slope_predicts_positive": predicts, "eigenvalues": vals.tolist(),
                "eigenpair_residuals": pres, "orthonormality_error": orth,
                "dilation": dilation, "brackets": brackets,
                "radial_verdict": parent_verdict,
            })
        parent_verdicts = [x["radial_verdict"] for x in parent_data]
        row_ok = bool(
            len(failures) == row_start and met["source_qualified"]
            and base["inertia_qualified"]
            and base_numerical
            and len(parent_data) == 3
        )
        if row_ok and any(v.startswith("CONTRADICTS") for v in parent_verdicts):
            verdict = "CONTRADICTS—finite-grid radial fixed-charge energetic stability"
        elif row_ok and len(parent_verdicts) == 3 and all(v.startswith("SUPPORTS") for v in parent_verdicts):
            verdict = "SUPPORTS—finite-grid radial fixed-charge energetic stability"
        else:
            verdict = "INCONCLUSIVE—finite-grid radial fixed-charge energetic stability"
        independent_rows.append({"id": ident, "artifact": relpath(met["artifact"]), "artifact_sha256": SOURCE_HASHES[ident], "R": float(met["R"]), "n": n, "target_population": 16 if ident.startswith("q16_") else 256, "norm": met["norm"], "energy": met["energy"], "gradient": met["gradient"], "potential": met["potential"], "omega_C": met["omega_C"], "residual_f": met["residual_f"], "residual_c": met["residual_c"], "eta": met["eta"], "source_qualified": met["source_qualified"], "base": base, "parents": parent_data, "operator_diagnostics": {"half_bandwidth": 2, "complete_base_eigenvalues": base_values.tolist(), "response_residual": response_resid}, "radial_verdict": verdict})
        if len(parent_data) == 3:
            row_data[ident] = {"row": independent_rows[-1], "primary": p}
    comparisons: list[dict[str, Any]] = []
    for population, prefix in ((16, "q16"), (256, "q256")):
        for ia, a in enumerate(A_VALUES):
            left, right = f"{prefix}_R12_n384_refine", f"{prefix}_R12_n768_refine"
            left2, right2 = left, f"{prefix}_R24_n768_refine"
            for pair, l, rgt in (("resolution", left, right), ("domain", left2, right2)):
                if l not in row_data or rgt not in row_data:
                    continue
                lv = float(row_data[l]["row"]["parents"][ia]["eigenvalues"][0])
                rv = float(row_data[rgt]["row"]["parents"][ia]["eigenvalues"][0])
                tol = max(0.01 * max(abs(lv), abs(rv)), float(row_data[l]["row"]["eta"]), float(row_data[rgt]["row"]["eta"]))
                comparisons.append({"population": population, "a": a, "pair": pair, "left": l, "right": rgt, "absolute_difference": abs(lv - rv), "tolerance": tol, "pass": bool(abs(lv - rv) <= tol)})
    primary_comparisons = primary.get("comparisons")
    if not isinstance(primary_comparisons, list) or len(primary_comparisons) != 12:
        fail(failures, "primary comparison schedule mismatch")
    else:
        for index, (independent, reported) in enumerate(zip(comparisons, primary_comparisons)):
            if not isinstance(reported, dict):
                fail(failures, f"primary comparisons[{index}] is not an object")
                continue
            for field in ("population", "pair", "left", "right"):
                if reported.get(field) != independent[field]:
                    fail(failures, f"primary comparisons[{index}].{field} mismatch")
            if reported.get("a") != independent["a"]:
                fail(failures, f"primary comparisons[{index}].a mismatch")
            for field in ("absolute_difference", "tolerance"):
                compare_value(failures, f"primary comparisons[{index}].{field}", independent[field], reported.get(field))
            if reported.get("pass") is not independent["pass"]:
                fail(failures, f"primary comparisons[{index}].pass mismatch")
    row_verdicts = [r["radial_verdict"] for r in independent_rows]
    if any(v.startswith("CONTRADICTS") for v in row_verdicts): radial_verdict = "CONTRADICTS—finite-grid radial fixed-charge energetic stability"
    elif len(row_verdicts) == len(SOURCE_IDS) and all(v.startswith("SUPPORTS") for v in row_verdicts): radial_verdict = "SUPPORTS—finite-grid radial fixed-charge energetic stability"
    else: radial_verdict = "INCONCLUSIVE—finite-grid radial fixed-charge energetic stability"
    comparison_verdict = "SUPPORTS—radial domain/resolution qualification" if len(comparisons) == 12 and all(c["pass"] for c in comparisons) else "INCONCLUSIVE—radial domain/resolution qualification"
    if primary.get("radial_verdict") != radial_verdict:
        fail(failures, "primary radial_verdict mismatch")
    if primary.get("comparison_verdict") != comparison_verdict:
        fail(failures, "primary comparison_verdict mismatch")
    numerical_pass = bool(not failures and len(independent_rows) == len(SOURCE_IDS) and len(comparisons) == 12)
    report = {"schema": VERIFY_SCHEMA, "input_sha256": byte_sha256(primary_receipt) if primary_receipt.exists() else "", "identities": expected_identities, "rows": independent_rows, "comparisons": comparisons, "failures": failures, "numerical_pass": numerical_pass, "radial_verdict": radial_verdict, "comparison_verdict": comparison_verdict}
    try:
        write_receipt(receipt_path, report)
    except Exception as exc:
        fail(failures, f"verification receipt write failed: {exc}")
        report["numerical_pass"] = False
        print(failures[-1], file=sys.stderr)
        return report, 1
    return report, 0 if numerical_pass else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    input_dir = args.input_dir.resolve(); source_dir = args.source_dir.resolve(); output_dir = (args.output_dir.resolve() if args.output_dir is not None else input_dir)
    try:
        _, code = verify(input_dir, source_dir, output_dir)
        return code
    except Exception as exc:
        print(json.dumps({"schema": VERIFY_SCHEMA, "numerical_pass": False, "error": f"{type(exc).__name__}: {exc}"}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
