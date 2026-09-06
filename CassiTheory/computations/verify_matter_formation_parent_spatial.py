#!/usr/bin/env python3
"""Independent verifier for the frozen scalar-parent angular/phase receipt.

This file intentionally contains no imports from the primary or any earlier
campaign.  It reconstructs the spherical finite-volume geometry, solves the
interleaved amplitude operators with ``eig_banded``, solves phase operators
with ``eigh_tridiagonal``, and audits the primary receipt and inherited radial
chain before assigning scientific verdicts.
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
from scipy.linalg import eig_banded, eigh_tridiagonal

ROOT = Path(__file__).resolve().parents[1]
PREREG_PATH = ROOT / "computations" / "matter-formation-parent-spatial-prereg.md"
SELF_PATH = ROOT / "computations" / "verify_matter_formation_parent_spatial.py"
PRIMARY_PATH = ROOT / "computations" / "matter_formation_parent_spatial.py"
DEFAULT_INPUT_DIR = ROOT / "runs" / "20260906_matter_formation_parent_spatial"
DEFAULT_SOURCE_DIR = ROOT / "runs" / "20260906_matter_formation_radial"
DEFAULT_RADIAL_DIR = ROOT / "runs" / "20260906_matter_formation_charged_stability"
DEFAULT_OUTPUT_DIR = ROOT / "runs" / "20260906_matter_formation_parent_spatial"
SCHEMA = "cassi.matter-formation.parent-spatial.v1"
VERIFY_SCHEMA = "cassi.matter-formation.parent-spatial.verification.v1"
COEFFICIENTS = {"u_rho": 4.0, "u_C": 1.0, "k_Cx": 1.0, "e_C": 0.75, "h_C": 2.9598260763447164}
A_VALUES = (1.0 / 64.0, 1.0 / 32.0, 1.0 / 16.0)
SOURCE_IDS = ("q256_R12_n192_w2", "q256_R12_n384_refine", "q256_R12_n768_refine", "q256_R24_n768_refine")
SOURCE_HASHES = {
    "q256_R12_n192_w2": "ce3d7efcf133fd2fd5776203a86d53469f4b91b4919ca1bbdcce054dc02233ba",
    "q256_R12_n384_refine": "e450c22a6baf8312fa67ca58745ad593879bf6d18615a83ad0cbe8dacabb11d5",
    "q256_R12_n768_refine": "95df301fcea98304434b95e9dd63a9cec987495ddda9af46e5940891672dc77a",
    "q256_R24_n768_refine": "7f839b59fa3a0a4c9ca6897ec3962aec2b7f62d20a1751968482349a22742b66",
}
RAW_KEYS = ("r", "volumes", "f", "c", "R", "q")
OPERATORS = ("amp1", "amp2", "phase0", "phase1")
EIGEN_COUNT = 6
NUM_TOL = 1.0e-8
EIG_MATCH_FACTOR = 1.0e-7
EIG_RESIDUAL_TOL = 1.0e-8
SOURCE_POP_TOL = 1.0e-10
SOURCE_RES_TOL = 1.0e-4
SUPPORT_SECTOR = "SUPPORTS—finite-grid scalar angular and phase energetic qualification"
CONTRADICT_SECTOR = "CONTRADICTS—finite-grid scalar angular and phase energetic qualification"
INCONCLUSIVE_SECTOR = "INCONCLUSIVE—finite-grid scalar angular and phase energetic qualification"
SUPPORT_COMPARE = "SUPPORTS—scalar spatial domain/resolution qualification"
INCONCLUSIVE_COMPARE = "INCONCLUSIVE—scalar spatial domain/resolution qualification"
SUPPORT_PARENT = "SUPPORTS—finite-grid scalar parent spatial energetic qualification"
CONTRADICT_PARENT = "CONTRADICTS—finite-grid scalar parent spatial energetic qualification"
INCONCLUSIVE_PARENT = "INCONCLUSIVE—finite-grid scalar parent spatial energetic qualification"
RADIAL_SUPPORT = "SUPPORTS—finite-grid radial fixed-charge energetic stability"


def byte_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def relpath(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return os.path.relpath(path.resolve(), ROOT.resolve()).replace("\\", "/")


def finite(x: Any) -> bool:
    return isinstance(x, (int, float, np.number)) and not isinstance(x, bool) and math.isfinite(float(x))


def close(a: Any, b: Any, factor: float = NUM_TOL) -> bool:
    return finite(a) and finite(b) and abs(float(a) - float(b)) <= factor * max(1.0, abs(float(a)), abs(float(b)))


def safe(path_value: Any) -> Path | None:
    if not isinstance(path_value, str) or not path_value:
        return None
    p = Path(path_value)
    if p.is_absolute() or any(part in ("", "..") for part in p.parts):
        return None
    return p


def json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def write_receipt(path: Path, payload: Mapping[str, Any]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    if path.exists() or tmp.exists():
        raise FileExistsError(f"refusing existing verification receipt or temporary artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(json_safe(payload), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    os.replace(tmp, path)


def fail(failures: list[str], text: str) -> None:
    failures.append(str(text))


def geometry(R: float, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dr = R / n
    faces = np.arange(n + 1, dtype=np.float64) * dr
    centres = (np.arange(n, dtype=np.float64) + 0.5) * dr
    volumes = (4.0 * math.pi / 3.0) * (faces[1:] ** 3 - faces[:-1] ** 3)
    return centres, volumes, faces


def tridiagonal_matvec(diagonal: np.ndarray, off: np.ndarray, x: np.ndarray) -> np.ndarray:
    result = diagonal * x
    result[1:] += off * x[:-1]
    result[:-1] += off * x[1:]
    return result


def source_diagnostics(arrays: Mapping[str, np.ndarray], R: float, q: float) -> dict[str, Any]:
    r, V, f, c = (arrays[key] for key in RAW_KEYS[:4])
    n = len(f)
    dr = R / n
    conductance = 4.0 * math.pi * (np.arange(1, n, dtype=np.float64) * dr) ** 2 / dr
    outer = 8.0 * math.pi * R * R / dr
    diagonal = np.zeros(n, dtype=np.float64)
    diagonal[:-1] += conductance
    diagonal[1:] += conductance
    diagonal[-1] += outer
    off = -conductance
    gf = tridiagonal_matvec(diagonal, off, f)
    gf[-1] -= outer
    gc = COEFFICIENTS["k_Cx"] * tridiagonal_matvec(diagonal, off, c)
    U = COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f)
    gf += V * (COEFFICIENTS["u_rho"] * f * (f * f - 1.0) + 2.0 * COEFFICIENTS["h_C"] * f * c * c)
    gc += V * (2.0 * U * c + 2.0 * COEFFICIENTS["u_C"] * c ** 3)
    N = float(np.dot(V, c * c))
    if not math.isfinite(N) or N <= 0.0:
        raise ValueError("nonpositive or nonfinite carrier population")
    omega = float(np.dot(c, gc) / (2.0 * N))
    rf = float(np.linalg.norm(gf / np.sqrt(V)) / max(1.0, np.linalg.norm(np.sqrt(V) * (1.0 - f))))
    rc = float(np.linalg.norm(np.sqrt(V) * (gc / (2.0 * V) - omega * c)) / math.sqrt(N))
    poperr = abs(N - q) / abs(q)
    qualified = bool(all(math.isfinite(x) for x in (N, omega, rf, rc, poperr)) and poperr < SOURCE_POP_TOL and rf < SOURCE_RES_TOL and rc < SOURCE_RES_TOL and np.all(f >= 0.0) and np.all(c >= 0.0))
    return {
        "r": r, "V": V, "f": f, "c": c,
        "stiffness_diagonal": diagonal, "stiffness_off": off,
        "N": N, "omega_C": omega, "residual_f": rf, "residual_c": rc,
        "population_relative_error": poperr, "eta": max(5.0e-4, 10.0 * rf, 10.0 * rc),
        "source_qualified": qualified,
        "profile": {"min_f": float(np.min(f)), "min_c": float(np.min(c)), "min_f_difference": float(np.min(np.diff(f))), "max_c_difference": float(np.max(np.diff(c)))},
    }


def load_source(source_dir: Path, ident: str) -> dict[str, Any]:
    path = source_dir / f"{ident}.npz"
    if not path.is_file():
        raise ValueError(f"{ident}: missing source artifact")
    actual = byte_sha256(path)
    if actual != SOURCE_HASHES[ident]:
        raise ValueError(f"{ident}: raw source hash mismatch")
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != set(RAW_KEYS):
            raise ValueError(f"{ident}: source keys mismatch")
        arrays = {k: np.asarray(archive[k]) for k in RAW_KEYS}
    if any(arrays[k].dtype != np.dtype("float64") for k in RAW_KEYS):
        raise ValueError(f"{ident}: source dtype mismatch")
    if any(arrays[k].ndim != 1 for k in RAW_KEYS[:4]) or arrays["R"].ndim != 0 or arrays["q"].ndim != 0:
        raise ValueError(f"{ident}: source shape mismatch")
    n = arrays["f"].size; R = float(arrays["R"]); q = float(arrays["q"])
    expected = {"q256_R12_n192_w2": (12.0, 192), "q256_R12_n384_refine": (12.0, 384), "q256_R12_n768_refine": (12.0, 768), "q256_R24_n768_refine": (24.0, 768)}[ident]
    er, ev, _ = geometry(R, n)
    if (arrays["r"].shape != (n,) or arrays["volumes"].shape != (n,) or arrays["c"].shape != (n,) or not finite(R) or not finite(q) or (R, n) != expected or q != 256.0 or R <= 0.0 or not np.all(np.isfinite(np.concatenate([arrays[k] for k in RAW_KEYS[:4]]))) or not np.array_equal(arrays["r"], er) or not np.array_equal(arrays["volumes"], ev)):
        raise ValueError(f"{ident}: malformed source geometry/metadata")
    d = source_diagnostics(arrays, R, q)
    if not all(finite(d[k]) for k in ("N", "omega_C", "residual_f", "residual_c", "population_relative_error", "eta")): raise ValueError(f"{ident}: nonfinite source diagnostics")
    d.update({"id": ident, "path": path, "R": R, "n": n, "q": q})
    return d


def banded_matvec(ab: np.ndarray, x: np.ndarray) -> np.ndarray:
    u = 2; y = ab[u] * x
    y[1:] += ab[u + 1, :-1] * x[:-1]; y[:-1] += ab[u - 1, 1:] * x[1:]
    y[2:] += ab[u + 2, :-2] * x[:-2]; y[:-2] += ab[u - 2, 2:] * x[2:]
    return y


def operators(d: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    f, c, V, n, R = d["f"], d["c"], d["V"], d["n"], d["R"]
    diagonal = d["stiffness_diagonal"] / V
    off = d["stiffness_off"] / np.sqrt(V[:-1] * V[1:])
    k = COEFFICIENTS["k_Cx"]
    angular = 4.0 * math.pi * (R / n) / V
    U = COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f)
    hff = diagonal + COEFFICIENTS["u_rho"] * (3.0 * f * f - 1.0) + 2.0 * COEFFICIENTS["h_C"] * c * c
    hcc = k * diagonal + 2.0 * (U - d["omega_C"]) + 6.0 * COEFFICIENTS["u_C"] * c * c
    mixed = 4.0 * COEFFICIENTS["h_C"] * f * c
    phase_potential = 2.0 * (U - d["omega_C"]) + 2.0 * COEFFICIENTS["u_C"] * c * c
    result: dict[str, Any] = {}
    for name, ell in (("amp1", 1), ("amp2", 2)):
        ab = np.zeros((5, 2 * n), dtype=np.float64)
        ab[2, 0::2] = hff + ell * (ell + 1) * angular
        ab[2, 1::2] = hcc + k * ell * (ell + 1) * angular
        ab[1, 1::2] = mixed
        ab[3, 0::2] = mixed
        ab[0, 2::2] = off
        ab[0, 3::2] = k * off
        ab[4, :-2:2] = off
        ab[4, 1:-2:2] = k * off
        result[name] = ab
    phase_off = k * off
    phase = {
        name: (k * diagonal + phase_potential + k * ell * (ell + 1) * angular, phase_off)
        for name, ell in (("phase0", 0), ("phase1", 1))
    }
    return result, phase


def solve_spectrum(ab: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    values, vectors = eig_banded(ab[:3], lower=False, select="i", select_range=(0, 5), check_finite=True)
    values = np.asarray(values, dtype=np.float64); vectors = np.asarray(vectors, dtype=np.float64)
    residuals = np.asarray([np.linalg.norm(banded_matvec(ab, vectors[:, j]) - values[j] * vectors[:, j]) / max(1.0, abs(float(values[j]))) for j in range(6)])
    orth = float(np.max(np.abs(vectors.T @ vectors - np.eye(6))))
    return values, vectors, residuals, orth


def solve_phase(diag: np.ndarray, off: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    values, vectors = eigh_tridiagonal(diag, off, select="i", select_range=(0, 5), check_finite=True)
    values = np.asarray(values, dtype=np.float64); vectors = np.asarray(vectors, dtype=np.float64)
    residuals = np.asarray([np.linalg.norm(tridiagonal_matvec(diag, off, vectors[:, j]) - values[j] * vectors[:, j]) / max(1.0, abs(float(values[j]))) for j in range(6)])
    orth = float(np.max(np.abs(vectors.T @ vectors - np.eye(6))))
    return values, vectors, residuals, orth


def derivative(x: np.ndarray, dr: float) -> np.ndarray:
    z = np.empty_like(x)
    z[0] = (-3.0 * x[0] + 4.0 * x[1] - x[2]) / (2.0 * dr)
    z[-1] = (3.0 * x[-1] - 4.0 * x[-2] + x[-3]) / (2.0 * dr)
    z[1:-1] = (x[2:] - x[:-2]) / (2.0 * dr)
    return z


def primary_spectra(row: Mapping[str, Any], input_dir: Path, n: int) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    ident = row["id"]
    info = row.get("spectra", {})
    relative = safe(info.get("path"))
    if relative is None or relative.parts != (f"spectra_{ident}.npz",):
        raise ValueError(f"{ident}: invalid primary spectral path")
    path = input_dir / relative
    digest = byte_sha256(path)
    if info.get("sha256") != digest:
        raise ValueError(f"{ident}: primary spectral hash mismatch")
    expected = {name + suffix for name in OPERATORS for suffix in ("_values", "_vectors")}
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != expected:
            raise ValueError(f"{ident}: primary spectral key mismatch")
        arrays = {name: np.asarray(archive[name]) for name in expected}
    for name in OPERATORS:
        values, vectors = arrays[name + "_values"], arrays[name + "_vectors"]
        shape = (2 * n, 6) if name.startswith("amp") else (n, 6)
        if values.dtype != np.dtype("float64") or vectors.dtype != np.dtype("float64") or values.shape != (6,) or vectors.shape != shape or not np.all(np.isfinite(values)) or not np.all(np.isfinite(vectors)):
            raise ValueError(f"{ident}: primary {name} dtype, shape or finite-value failure")
    return arrays, {"path": relative.name, "sha256": digest}


def independent_row(d: Mapping[str, Any], arrays: Mapping[str, np.ndarray], spectral_info: Mapping[str, str], failures: list[str], radial_rows: Mapping[str, Any]) -> dict[str, Any]:
    dops, phases = operators(d)
    spectra: dict[str, Any] = {}
    checks: dict[str, Any] = {}
    numerical = bool(d["source_qualified"])
    if not numerical:
        fail(failures, f"{d['id']}: independent source qualification failed")
    p = np.sqrt(d["V"]) * d["c"]
    dr = d["R"] / d["n"]
    t = np.empty(2 * d["n"], dtype=np.float64)
    t[0::2] = np.sqrt(d["V"]) * derivative(d["f"], dr)
    t[1::2] = np.sqrt(d["V"]) * derivative(d["c"], dr)
    p_norm, t_norm = float(np.linalg.norm(p)), float(np.linalg.norm(t))
    if not all(math.isfinite(x) and x > 0.0 for x in (p_norm, t_norm)):
        raise ValueError(f"{d['id']}: invalid symmetry-vector norm")
    p /= p_norm
    t /= t_norm
    for name in OPERATORS:
        if name.startswith("amp"):
            values, vectors, residuals, orth = solve_spectrum(dops[name])
        else:
            values, vectors, residuals, orth = solve_phase(*phases[name])
        if not all(np.all(np.isfinite(x)) for x in (values, vectors, residuals, orth)):
            raise ValueError(f"{d['id']}: nonfinite independent {name} spectrum")
        spectra[name] = {"eigenvalues": values, "vectors": vectors, "eigenpair_residuals": residuals, "orthonormality_error": orth}
        own_ok = bool(np.max(residuals) < EIG_RESIDUAL_TOL and orth < EIG_RESIDUAL_TOL)
        if not own_ok:
            fail(failures, f"{d['id']}: independent {name} numerical qualification failed")
        values_primary = arrays[name + "_values"]
        vectors_primary = arrays[name + "_vectors"]
        eigenvalues_match = bool(np.all(np.abs(values_primary - values) <= EIG_MATCH_FACTOR * np.maximum(1.0, np.abs(values_primary))))
        if name.startswith("amp"):
            interleaved = np.empty_like(vectors_primary)
            interleaved[0::2] = vectors_primary[:d["n"]]
            interleaved[1::2] = vectors_primary[d["n"]:]
            primary_residuals = np.asarray([
                np.linalg.norm(banded_matvec(dops[name], interleaved[:, j]) - values_primary[j] * interleaved[:, j]) / max(1.0, abs(float(values_primary[j])))
                for j in range(6)
            ])
        else:
            interleaved = vectors_primary
            primary_residuals = np.asarray([
                np.linalg.norm(tridiagonal_matvec(*phases[name], interleaved[:, j]) - values_primary[j] * interleaved[:, j]) / max(1.0, abs(float(values_primary[j])))
                for j in range(6)
            ])
        primary_orth = float(np.max(np.abs(interleaved.T @ interleaved - np.eye(6))))
        primary_ok = bool(eigenvalues_match and np.all(np.isfinite(primary_residuals)) and np.max(primary_residuals) < EIG_RESIDUAL_TOL and primary_orth < EIG_RESIDUAL_TOL)
        if not primary_ok:
            fail(failures, f"{d['id']}: primary {name} independent spectral check failed")
        checks[name] = {"eigenvalues_match": eigenvalues_match, "primary_residuals": primary_residuals.tolist(), "primary_orthonormality_error": primary_orth}
        numerical = numerical and own_ok and primary_ok
    overlaps_t = np.abs(spectra["amp1"]["vectors"].T @ t)
    overlaps_p = np.abs(spectra["phase0"]["vectors"].T @ p)
    ti, pi = int(np.argmax(overlaps_t)), int(np.argmax(overlaps_p))
    symmetries = {
        "translation": {"index": ti, "overlap": float(overlaps_t[ti]), "eigenvalue": float(spectra["amp1"]["eigenvalues"][ti]), "operator_residual": float(np.linalg.norm(banded_matvec(dops["amp1"], t)))},
        "phase": {"index": pi, "overlap": float(overlaps_p[pi]), "eigenvalue": float(spectra["phase0"]["eigenvalues"][pi]), "operator_residual": float(np.linalg.norm(tridiagonal_matvec(*phases["phase0"], p)))},
    }
    metrics = {
        "amp1_gap": float(min(x for j, x in enumerate(spectra["amp1"]["eigenvalues"]) if j != ti)),
        "amp2_minimum": float(spectra["amp2"]["eigenvalues"][0]),
        "phase0_gap": float(min(x for j, x in enumerate(spectra["phase0"]["eigenvalues"]) if j != pi)),
        "phase1_minimum": float(spectra["phase1"]["eigenvalues"][0]),
    }
    parents = []
    for inherited in radial_rows[d["id"]]["parents"]:
        a = float(inherited["a"])
        discriminant = 1.0 + 4.0 * a * d["omega_C"]
        if not math.isfinite(discriminant) or discriminant <= 0.0:
            raise ValueError(f"{d['id']}: nonpositive canonical discriminant")
        root = math.sqrt(discriminant)
        parents.append({
            "a": a, "radial_minimum": float(inherited["eigenvalues"][0]), "radial_verdict": inherited["radial_verdict"],
            "omega": 2.0 * d["omega_C"] / (1.0 + root), "canonical_frequency": root / (2.0 * a),
            "exterior_mass_squared": 1.0 / (4.0 * a * a) + COEFFICIENTS["e_C"] / a,
            "exterior_frequency_gap_squared": (COEFFICIENTS["e_C"] - d["omega_C"]) / a,
            "depleted_mass_squared": 1.0 / (4.0 * a * a) + (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"]) / a,
        })
    eta = d["eta"]
    if not numerical:
        verdict = INCONCLUSIVE_SECTOR
    elif any(spectra[name]["eigenvalues"][0] < -eta for name in OPERATORS):
        verdict = CONTRADICT_SECTOR
    elif all(sym["overlap"] > 0.99 and abs(sym["eigenvalue"]) <= eta for sym in symmetries.values()) and all(value > eta for value in metrics.values()):
        verdict = SUPPORT_SECTOR
    else:
        verdict = INCONCLUSIVE_SECTOR
    return {
        "id": d["id"], "artifact": relpath(d["path"]), "artifact_sha256": SOURCE_HASHES[d["id"]],
        "R": float(d["R"]), "n": int(d["n"]), "target_population": 256.0, "population": d["N"], "omega_C": d["omega_C"],
        "population_relative_error": d["population_relative_error"], "residual_f": d["residual_f"], "residual_c": d["residual_c"],
        "eta": eta, "source_qualified": bool(d["source_qualified"]), "profile": d["profile"],
        "asymptotic": {"mediator_spatial_gap": 2.0 * COEFFICIENTS["u_rho"], "carrier_spatial_gap": 2.0 * (COEFFICIENTS["e_C"] - d["omega_C"])},
        "parents": parents,
        "operators": {name: {"eigenvalues": spectra[name]["eigenvalues"].tolist(), "eigenpair_residuals": spectra[name]["eigenpair_residuals"].tolist(), "orthonormality_error": spectra[name]["orthonormality_error"]} for name in OPERATORS},
        "symmetries": symmetries, "metrics": metrics, "spectra": dict(spectral_info),
        "primary_checks": checks, "sector_verdict": verdict,
    }


def inherited_radial(radial_dir: Path, failures: list[str]) -> tuple[bool, dict[str, Any], dict[str, Any]]:
    result_path, verify_path = radial_dir / "results.json", radial_dir / "verification.json"
    expected_r = "540bf259441b42ac476189dcd8593ae3b57a4fe25bb8fe17c846d5465068b0bc"
    expected_v = "7f299ed6401014760b174895781d253ffebe6fad3c2a11e801506c9759e2d255"
    public = {"results": {"path": relpath(result_path), "sha256": ""}, "verification": {"path": relpath(verify_path), "sha256": ""}, "qualified": False}
    try:
        if byte_sha256(result_path) != expected_r or byte_sha256(verify_path) != expected_v:
            raise ValueError("accepted radial raw identity mismatch")
        public["results"]["sha256"], public["verification"]["sha256"] = expected_r, expected_v
        rj = json.loads(result_path.read_text(encoding="utf-8"))
        vj = json.loads(verify_path.read_text(encoding="utf-8"))
        if rj.get("schema") != "cassi.matter-formation.charged-stability.v1" or vj.get("schema") != "cassi.matter-formation.charged-stability.verification.v1":
            raise ValueError("accepted radial schema mismatch")
        if vj.get("input_sha256") != expected_r or any(receipt.get("numerical_pass") is not True or receipt.get("failures") != [] for receipt in (rj, vj)):
            raise ValueError("accepted radial verification link or numerical gate failed")
        paths = {
            "primary": ROOT / "computations/matter_formation_charged_stability.py",
            "verifier": ROOT / "computations/verify_matter_formation_charged_stability.py",
            "preregistration": ROOT / "computations/matter-formation-charged-stability-prereg.md",
        }
        for key, path in paths.items():
            if rj.get("identities", {}).get(key) != {"path": relpath(path), "sha256": canonical_sha256(path)}:
                raise ValueError(f"accepted radial canonical source identity mismatch: {key}")
        primary_rows = {}
        for label, receipt in (("primary", rj), ("independent", vj)):
            selected = [row for row in receipt.get("rows", []) if row.get("id") in SOURCE_IDS]
            if len(selected) != 4 or {row["id"] for row in selected} != set(SOURCE_IDS):
                raise ValueError(f"accepted radial {label} source schedule mismatch")
            for row in selected:
                parents = row.get("parents", [])
                if row.get("source_qualified") is not True or len(parents) != 3:
                    raise ValueError(f"accepted radial {label} source qualification failed")
                for parent, a in zip(parents, A_VALUES):
                    if parent.get("a") != a or parent.get("radial_verdict") != RADIAL_SUPPORT or not finite(parent.get("eigenvalues", [None])[0]) or parent["eigenvalues"][0] <= row["eta"]:
                        raise ValueError(f"accepted radial {label} parent qualification failed")
            comparisons = [item for item in receipt.get("comparisons", []) if item.get("population") == 256.0]
            expected = {(a, pair, "q256_R12_n384_refine", right) for a in A_VALUES for pair, right in (("resolution", "q256_R12_n768_refine"), ("domain", "q256_R24_n768_refine"))}
            actual = {(item.get("a"), item.get("pair"), item.get("left"), item.get("right")) for item in comparisons}
            if len(comparisons) != 6 or actual != expected or not all(item.get("pass") is True for item in comparisons):
                raise ValueError(f"accepted radial {label} comparison qualification failed")
            if label == "primary":
                primary_rows = {row["id"]: row for row in selected}
        public["qualified"] = True
        return True, public, primary_rows
    except Exception as exc:
        fail(failures, f"inherited radial validation: {type(exc).__name__}: {exc}")
        return False, public, {}


def compare_primary_value(failures: list[str], label: str, actual: Any, expected: Any, factor: float = NUM_TOL) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            fail(failures, f"primary schema mismatch: {label}")
            return
        for key, value in expected.items():
            compare_primary_value(failures, f"{label}.{key}", actual[key], value, EIG_MATCH_FACTOR if key == "eigenvalues" else factor)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            fail(failures, f"primary list shape mismatch: {label}")
            return
        for index, value in enumerate(expected):
            compare_primary_value(failures, f"{label}[{index}]", actual[index], value, factor)
    elif isinstance(expected, bool):
        if actual is not expected:
            fail(failures, f"primary boolean mismatch: {label}")
    elif isinstance(expected, int):
        if type(actual) is not int or actual != expected:
            fail(failures, f"primary integer mismatch: {label}")
    elif isinstance(expected, (float, np.number)):
        if not close(actual, expected, factor):
            fail(failures, f"primary numeric mismatch: {label}")
    elif actual != expected:
        fail(failures, f"primary value mismatch: {label}")


def run(input_dir: Path, source_dir: Path, radial_dir: Path, output_dir: Path) -> tuple[dict[str, Any], int]:
    output_dir, input_dir = output_dir.resolve(), input_dir.resolve()
    source_dir, radial_dir = source_dir.resolve(), radial_dir.resolve()
    receipt_path = output_dir / "verification.json"
    if receipt_path.exists() or receipt_path.with_name(receipt_path.name + ".tmp").exists():
        raise FileExistsError(f"refusing existing verification receipt: {output_dir}")
    failures: list[str] = []
    identities = {}
    for label, path in (("primary", PRIMARY_PATH), ("verifier", SELF_PATH), ("prereg", PREREG_PATH)):
        identities[label] = {"path": relpath(path), "sha256": ""}
        try:
            identities[label]["sha256"] = canonical_sha256(path)
        except Exception as exc:
            fail(failures, f"{label} canonical identity: {type(exc).__name__}: {exc}")
    primary_path = input_dir / "results.json"
    primary = {}
    input_hash = ""
    try:
        input_hash = byte_sha256(primary_path)
        primary = json.loads(primary_path.read_text(encoding="utf-8"))
        if not isinstance(primary, dict):
            raise ValueError("primary receipt must be a JSON object")
    except Exception as exc:
        fail(failures, f"primary receipt: {type(exc).__name__}: {exc}")
        primary = {}
    bounds = {
        "a_dep": 1.0 / (4.0 * (COEFFICIENTS["h_C"] - COEFFICIENTS["e_C"])),
        "a_vac": 1.0 / (4.0 * (COEFFICIENTS["h_C"] - COEFFICIENTS["e_C"] - math.sqrt(COEFFICIENTS["u_rho"] * COEFFICIENTS["u_C"] / 2.0))),
    }
    for key, expected in (("schema", SCHEMA), ("identities", identities), ("coefficients", COEFFICIENTS), ("temporal_bounds", bounds)):
        compare_primary_value(failures, key, primary.get(key), expected)
    if primary.get("numerical_pass") is not True:
        fail(failures, "primary numerical_pass is not true")
    if primary.get("failures") != []:
        fail(failures, f"primary failures are not empty: {primary.get('failures')!r}")
    radial_ok, radial_public, radial_rows = inherited_radial(radial_dir, failures)
    compare_primary_value(failures, "inherited_radial", primary.get("inherited_radial"), radial_public)
    claimed_rows = primary.get("rows", [])
    if not isinstance(claimed_rows, list) or len(claimed_rows) != 4 or any(not isinstance(row, dict) for row in claimed_rows) or [row.get("id") for row in claimed_rows] != list(SOURCE_IDS):
        fail(failures, "primary source schedule mismatch")
        claimed_by = {}
    else:
        claimed_by = {row["id"]: row for row in claimed_rows}
    report = {
        "schema": VERIFY_SCHEMA, "input_sha256": input_hash, "identities": identities,
        "inherited_radial": radial_public, "coefficients": COEFFICIENTS.copy(), "temporal_bounds": bounds,
        "rows": [], "comparisons": [], "numerical_pass": False,
        "sector_verdict": INCONCLUSIVE_SECTOR, "comparison_verdict": INCONCLUSIVE_COMPARE,
        "parent_verdict": INCONCLUSIVE_PARENT, "failures": failures,
    }
    sources, spectral_inputs = {}, {}
    if not failures:
        for ident in SOURCE_IDS:
            try:
                sources[ident] = load_source(source_dir, ident)
                spectral_inputs[ident] = primary_spectra(claimed_by[ident], input_dir, sources[ident]["n"])
            except Exception as exc:
                fail(failures, f"{ident} input preflight: {type(exc).__name__}: {exc}")
    if failures:
        write_receipt(receipt_path, report)
        return report, 1
    for ident in SOURCE_IDS:
        try:
            arrays, spectral_info = spectral_inputs[ident]
            row = independent_row(sources[ident], arrays, spectral_info, failures, radial_rows)
            compare_primary_value(failures, ident, claimed_by[ident], {key: value for key, value in row.items() if key != "primary_checks"})
            report["rows"].append(row)
        except Exception as exc:
            fail(failures, f"{ident} independent calculation: {type(exc).__name__}: {exc}")
    if len(report["rows"]) != 4:
        fail(failures, f"incomplete independent source schedule: {len(report['rows'])} of 4")
    by_id = {row["id"]: row for row in report["rows"]}
    for metric in ("amp1_gap", "amp2_minimum", "phase0_gap", "phase1_minimum"):
        for pair, right_id in (("resolution", "q256_R12_n768_refine"), ("domain", "q256_R24_n768_refine")):
            left = by_id.get("q256_R12_n384_refine")
            right = by_id.get(right_id)
            if left is None or right is None:
                fail(failures, f"missing independent comparison: {metric} {pair}")
                continue
            lv, rv = left["metrics"][metric], right["metrics"][metric]
            tolerance = max(0.01 * max(abs(lv), abs(rv)), left["eta"], right["eta"])
            report["comparisons"].append({"metric": metric, "pair": pair, "left": left["id"], "right": right["id"], "absolute_difference": abs(lv - rv), "tolerance": tolerance, "pass": bool(abs(lv - rv) <= tolerance)})
    compare_primary_value(failures, "comparisons", primary.get("comparisons"), report["comparisons"])
    verdicts = [row["sector_verdict"] for row in report["rows"]]
    contradiction = CONTRADICT_SECTOR in verdicts
    all_support = len(verdicts) == 4 and all(value == SUPPORT_SECTOR for value in verdicts)
    report["sector_verdict"] = CONTRADICT_SECTOR if contradiction else (SUPPORT_SECTOR if all_support else INCONCLUSIVE_SECTOR)
    report["comparison_verdict"] = SUPPORT_COMPARE if len(report["comparisons"]) == 8 and all(item["pass"] for item in report["comparisons"]) else INCONCLUSIVE_COMPARE
    report["parent_verdict"] = CONTRADICT_PARENT if contradiction else (SUPPORT_PARENT if radial_ok and all_support and report["comparison_verdict"] == SUPPORT_COMPARE else INCONCLUSIVE_PARENT)
    for key in ("sector_verdict", "comparison_verdict", "parent_verdict"):
        compare_primary_value(failures, key, primary.get(key), report[key])
    report["numerical_pass"] = bool(not failures and len(report["rows"]) == 4 and len(report["comparisons"]) == 8)
    write_receipt(receipt_path, report)
    return report, 0 if report["numerical_pass"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--radial-dir", type=Path, default=DEFAULT_RADIAL_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    try:
        report, code = run(args.input_dir, args.source_dir, args.radial_dir, args.output_dir)
        print(json.dumps({"numerical_pass": report["numerical_pass"], "sector_verdict": report["sector_verdict"], "comparison_verdict": report["comparison_verdict"], "parent_verdict": report["parent_verdict"]}, sort_keys=True))
        return code
    except Exception as exc:
        print(json.dumps({"schema": VERIFY_SCHEMA, "numerical_pass": False, "error": f"{type(exc).__name__}: {exc}"}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
