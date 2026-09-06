#!/usr/bin/env python3
"""Frozen finite-grid stability calculation for the qualified Q_C=16 branch.

The radial NPZ artifacts are treated as immutable source fields.  This driver
assembles the cell-centred stiffness and all mass-weighted Hessians locally,
then writes one receipt containing the source identities, eigenpairs, symmetry
checks, and the preregistered finite-grid decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "runs" / "20260906_matter_formation_radial"
DEFAULT_OUTPUT_DIR = ROOT / "runs" / "20260906_matter_formation_stability"
PREREG_PATH = ROOT / "computations" / "matter-formation-stability-prereg.md"
SCHEMA = "matter-formation-stability-v1"

COEFFICIENTS = {
    "u_rho": 4.0,
    "u_phi": 4.0,
    "u_H": 4.0,
    "gamma_x": 1.0,
    "k_Cx": 1.0,
    "u_C": 1.0,
    "e_C": 0.75,
    "h_C": 2.9598260763447164,
}

ARTIFACT_SHA256 = {
    "q16_R12_n192_w2": "52540cf2cc11fcb313ecf689ffb5115c72480813cb7c866f348050bee33ad777",
    "q16_R12_n384_refine": "2e21fa2158d7fc7f9bff65bf337558af1bc0ca76520ea441611b37ab91e9d770",
    "q16_R12_n768_refine": "335364c4e655de4a34b51c0558c3a7559f45311d7f2973b262de4fd2c61db7be",
    "q16_R24_n768_refine": "92c49919d8fb748dffb7a9e3d4ba497214beb883fb837195dcc8a321ec06096b",
}


def canonical_sha256(path: Path) -> str:
    """Hash text after the preregistered CRLF-to-LF normalization."""
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return os.path.relpath(path.resolve(), ROOT).replace("\\", "/")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    os.replace(temporary, path)


def _scalar(archive: Any, key: str) -> float:
    value = np.asarray(archive[key], dtype=np.float64)
    if value.size != 1:
        raise ValueError(f"NPZ field {key!r} is not scalar")
    result = float(value.reshape(()))
    if not math.isfinite(result):
        raise ValueError(f"NPZ field {key!r} is not finite")
    return result


def _assemble_stiffness(volumes: np.ndarray, R: float, n: int) -> tuple[np.ndarray, float, float]:
    """Return exact radial K, dr, and outer half-cell conductance."""
    dr = float(R) / n
    faces = np.arange(n + 1, dtype=np.float64) * dr
    expected = (4.0 * math.pi / 3.0) * (faces[1:] ** 3 - faces[:-1] ** 3)
    if not np.allclose(volumes, expected, rtol=2.0e-13, atol=2.0e-15):
        raise ValueError("NPZ volumes do not match exact spherical cell volumes")
    conductance = 4.0 * math.pi * faces[1:-1] ** 2 / dr
    outer = 8.0 * math.pi * R * R / dr
    K = np.zeros((n, n), dtype=np.float64)
    if n > 1:
        indices = np.arange(n - 1)
        K[indices, indices] += conductance
        K[indices + 1, indices + 1] += conductance
        K[indices, indices + 1] -= conductance
        K[indices + 1, indices] -= conductance
    K[-1, -1] += outer
    return K, dr, outer


def _load_artifact(identifier: str, input_dir: Path) -> dict[str, Any]:
    if identifier not in ARTIFACT_SHA256:
        raise KeyError(f"unregistered artifact {identifier}")
    path = input_dir / f"{identifier}.npz"
    if not path.is_file():
        raise FileNotFoundError(path)
    artifact_sha256 = raw_sha256(path)
    expected = ARTIFACT_SHA256[identifier]
    if artifact_sha256 != expected:
        raise ValueError(f"byte hash mismatch for {identifier}: {artifact_sha256}")
    with np.load(path, allow_pickle=False) as archive:
        required = {"r", "volumes", "f", "c", "R", "q"}
        if not required.issubset(archive.files):
            raise ValueError(f"{identifier} is missing required NPZ fields")
        r = np.asarray(archive["r"], dtype=np.float64)
        volumes = np.asarray(archive["volumes"], dtype=np.float64)
        f = np.asarray(archive["f"], dtype=np.float64)
        c = np.asarray(archive["c"], dtype=np.float64)
        R = _scalar(archive, "R")
        q = _scalar(archive, "q")
    if any(a.ndim != 1 for a in (r, volumes, f, c)) or not (r.size == volumes.size == f.size == c.size):
        raise ValueError(f"{identifier} has inconsistent radial array shapes")
    n = int(r.size)
    if n < 3 or q != 16.0 or not (R > 0.0):
        raise ValueError(f"{identifier} has invalid frozen grid metadata")
    dr = R / n
    expected_r = (np.arange(n, dtype=np.float64) + 0.5) * dr
    if not np.allclose(r, expected_r, rtol=2.0e-13, atol=2.0e-15):
        raise ValueError(f"{identifier} radius centres are not cell-centred")
    if not (np.all(np.isfinite(f)) and np.all(np.isfinite(c))):
        raise ValueError(f"{identifier} contains nonfinite source fields")
    K, dr, outer = _assemble_stiffness(volumes, R, n)
    return {
        "id": identifier,
        "path": path,
        "artifact_sha256": artifact_sha256,
        "r": r,
        "volumes": volumes,
        "f": f,
        "c": c,
        "R": R,
        "q": q,
        "n": n,
        "dr": dr,
        "K": K,
        "outer_conductance": outer,
    }


def _source_diagnostics(source: dict[str, Any]) -> dict[str, float]:
    f, c, V, K = source["f"], source["c"], source["volumes"], source["K"]
    g_f = K @ f
    g_c = K @ c
    g_f[-1] -= source["outer_conductance"]
    rho = f * f - 1.0
    carrier_potential = COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f)
    g_f += V * (COEFFICIENTS["u_rho"] * f * rho + 2.0 * COEFFICIENTS["h_C"] * f * c * c)
    g_c += V * (2.0 * carrier_potential * c + 2.0 * COEFFICIENTS["u_C"] * c**3)
    charge = float(np.dot(V, c * c))
    if charge <= 0.0 or not math.isfinite(charge):
        raise ValueError(f"{source['id']} has nonpositive carrier charge")
    omega = float(np.dot(c, g_c) / (2.0 * charge))
    residual_f_field = g_f / V
    residual_c_field = g_c / (2.0 * V) - omega * c
    f_scale = max(1.0, math.sqrt(float(np.dot(V, (1.0 - f) ** 2))))
    residual_f = math.sqrt(float(np.dot(V, residual_f_field**2))) / f_scale
    residual_c = math.sqrt(float(np.dot(V, residual_c_field**2))) / math.sqrt(charge)
    gradient = 0.5 * float(np.dot(source["K"] @ f, f)) - source["outer_conductance"] * f[-1]
    gradient += 0.5 * source["outer_conductance"]
    gradient += 0.5 * float(np.dot(source["K"] @ c, c))
    potential = (
        COEFFICIENTS["u_rho"] / 4.0 * rho * rho
        + carrier_potential * c * c
        + COEFFICIENTS["u_C"] / 2.0 * c**4
    )
    energy = gradient + float(np.dot(V, potential))
    return {
        "energy": float(energy),
        "charge": charge,
        "charge_relative_error": abs(charge - 16.0) / 16.0,
        "omega": omega,
        "residual_f": float(residual_f),
        "residual_c": float(residual_c),
    }


def _mass_weighted_hessians(source: dict[str, Any], omega: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    f, c, V, K = source["f"], source["c"], source["volumes"], source["K"]
    n, dr = source["n"], source["dr"]
    inv_sqrt_V = 1.0 / np.sqrt(V)
    D0 = inv_sqrt_V[:, None] * K * inv_sqrt_V[None, :]
    angular = 4.0 * math.pi * dr / V
    def D_l(ell: int) -> np.ndarray:
        D = D0.copy()
        D[np.diag_indices(n)] += ell * (ell + 1.0) * angular
        return D
    diagonal_f = COEFFICIENTS["u_rho"] * (3.0 * f * f - 1.0) + 2.0 * COEFFICIENTS["h_C"] * c * c
    diagonal_c = 2.0 * (
        COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f) - omega
    ) + 6.0 * COEFFICIENTS["u_C"] * c * c
    off_diagonal = 4.0 * COEFFICIENTS["h_C"] * f * c
    def amplitude(ell: int) -> np.ndarray:
        D = D_l(ell)
        H = np.zeros((2 * n, 2 * n), dtype=np.float64)
        H[:n, :n] = D
        H[n:, n:] = D
        H[np.diag_indices(n)] += diagonal_f
        H[n + np.arange(n), n + np.arange(n)] += diagonal_c
        H[np.arange(n), n + np.arange(n)] = off_diagonal
        H[n + np.arange(n), np.arange(n)] = off_diagonal
        return H
    phase = D0.copy()
    phase[np.diag_indices(n)] += 2.0 * (
        COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f) - omega
    ) + 2.0 * COEFFICIENTS["u_C"] * c * c
    return amplitude(0), amplitude(1), phase


def _householder_null_basis(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float64)
    norm = float(np.linalg.norm(vector))
    if not math.isfinite(norm) or norm == 0.0:
        raise ValueError("constraint vector has zero norm")
    u = vector.copy()
    u[0] += math.copysign(norm, vector[0] if vector[0] != 0.0 else 1.0)
    u_norm = float(np.linalg.norm(u))
    if u_norm == 0.0:
        raise ValueError("Householder reflector is singular")
    u /= u_norm
    reflector = np.eye(vector.size, dtype=np.float64) - 2.0 * np.outer(u, u)
    basis = reflector[:, 1:]
    if not np.allclose(basis.T @ vector, 0.0, rtol=0.0, atol=2.0e-13):
        raise ArithmeticError("Householder basis failed the charge tangent check")
    return basis


def _eigen_receipt(H: np.ndarray, count: int = 6, basis: np.ndarray | None = None) -> tuple[dict[str, Any], np.ndarray]:
    reduced = H if basis is None else basis.T @ H @ basis
    eigenvalues, eigenvectors = np.linalg.eigh(reduced)
    if eigenvalues.size < count:
        raise ValueError("operator has fewer than six eigenvalues")
    values = eigenvalues[:count]
    vectors_reduced = eigenvectors[:, :count]
    residuals = []
    for index in range(count):
        vector = vectors_reduced[:, index]
        residuals.append(float(np.linalg.norm(reduced @ vector - values[index] * vector) / max(1.0, abs(values[index]))))
    vectors = vectors_reduced if basis is None else basis @ vectors_reduced
    return {"eigenvalues": [float(x) for x in values], "residuals": residuals}, vectors


def _overlaps(source: dict[str, Any], phase_vectors: np.ndarray, h1_vectors: np.ndarray) -> tuple[float, float]:
    V, c, f, dr = source["volumes"], source["c"], source["f"], source["dr"]
    phase_symmetry = np.sqrt(V) * c
    phase_symmetry /= np.linalg.norm(phase_symmetry)
    phase_overlap = abs(float(np.dot(phase_vectors[:, 0], phase_symmetry)))
    f_prime = np.gradient(f, dr, edge_order=2)
    c_prime = np.gradient(c, dr, edge_order=2)
    translation = np.concatenate((np.sqrt(V) * f_prime, np.sqrt(V) * c_prime))
    translation_norm = float(np.linalg.norm(translation))
    if translation_norm == 0.0:
        raise ValueError("translation sample has zero norm")
    translation /= translation_norm
    translation_overlap = abs(float(np.dot(h1_vectors[:, 0], translation)))
    return float(phase_overlap), float(translation_overlap)


def _field_row(source: dict[str, Any]) -> dict[str, Any]:
    diagnostics = _source_diagnostics(source)
    H0, H1, Hphase = _mass_weighted_hessians(source, diagnostics["omega"])
    V, c = source["volumes"], source["c"]
    constraint = np.concatenate((np.zeros(source["n"], dtype=np.float64), np.sqrt(V) * c))
    tangent = _householder_null_basis(constraint)
    amplitude0, h0_vectors = _eigen_receipt(H0, basis=tangent)
    amplitude1, h1_vectors = _eigen_receipt(H1)
    phase, phase_vectors = _eigen_receipt(Hphase)
    phase_overlap, translation_overlap = _overlaps(source, phase_vectors, h1_vectors)
    all_eigenvalues = amplitude0["eigenvalues"] + amplitude1["eigenvalues"] + phase["eigenvalues"]
    all_residuals = amplitude0["residuals"] + amplitude1["residuals"] + phase["residuals"]
    if not np.all(np.isfinite(all_eigenvalues)):
        raise ArithmeticError(f"nonfinite eigenvalues for {source['id']}")
    if not np.all(np.isfinite(all_residuals)):
        raise ArithmeticError(f"nonfinite eigenpair residual for {source['id']}")
    eta = max(5.0e-4, 10.0 * diagnostics["residual_f"], 10.0 * diagnostics["residual_c"])
    residual_gate = max(all_residuals) < 1.0e-8
    source_gate = (
        diagnostics["charge_relative_error"] < 1.0e-10
        and diagnostics["residual_f"] < 1.0e-4
        and diagnostics["residual_c"] < 1.0e-4
    )
    symmetry_gate = (
        abs(phase["eigenvalues"][0]) <= eta
        and abs(amplitude1["eigenvalues"][0]) <= eta
        and phase_overlap > 0.99
        and translation_overlap > 0.99
    )
    hessian_gate = (
        amplitude0["eigenvalues"][0] > eta
        and amplitude1["eigenvalues"][0] >= -eta
        and phase["eigenvalues"][0] >= -eta
    )
    negative_below_eta = any(
        value < -eta
        for value in (
            amplitude0["eigenvalues"][0],
            amplitude1["eigenvalues"][0],
            phase["eigenvalues"][0],
        )
    )
    contradiction = bool(source_gate and negative_below_eta)
    qualified = bool(source_gate and residual_gate and symmetry_gate and hessian_gate)
    verdict = "CONTRADICTS" if contradiction else ("SUPPORTS" if qualified else "INCONCLUSIVE")
    row: dict[str, Any] = {
        "id": source["id"],
        "artifact": relative_path(source["path"]),
        "artifact_sha256": source["artifact_sha256"],
        "R": source["R"],
        "n": source["n"],
        "dr": source["dr"],
        "q": source["q"],
        "omega": diagnostics["omega"],
        "residual_f": diagnostics["residual_f"],
        "residual_c": diagnostics["residual_c"],
        "eta": eta,
        "amplitude0": amplitude0,
        "amplitude1": amplitude1,
        "phase": phase,
        "phase_overlap": phase_overlap,
        "translation_overlap": translation_overlap,
        "energy": diagnostics["energy"],
        "charge": diagnostics["charge"],
        "charge_relative_error": diagnostics["charge_relative_error"],
        "gates": {
            "source": source_gate,
            "eigenpair_residual": residual_gate,
            "symmetry": symmetry_gate,
            "hessian": hessian_gate,
            "contradiction": contradiction,
        },
        "verdict": verdict,
    }
    return row




def _comparison(name: str, a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    x = float(a["amplitude0"]["eigenvalues"][0])
    y = float(b["amplitude0"]["eigenvalues"][0])
    eta_a = float(a["eta"])
    eta_b = float(b["eta"])
    scale = max(abs(x), abs(y))
    tolerance = max(0.01 * scale, eta_a, eta_b)
    difference = abs(x - y)
    return {
        "name": name,
        "a": a["id"],
        "b": b["id"],
        "lambda_a": x,
        "lambda_b": y,
        "eta_a": eta_a,
        "eta_b": eta_b,
        "absolute_difference": difference,
        "relative_difference": difference / max(1.0, scale),
        "tolerance": tolerance,
        "criterion": "abs(lambda_a-lambda_b)<=max(0.01*max(abs(lambda_a),abs(lambda_b)),eta_a,eta_b)",
        "pass": bool(difference <= tolerance),
    }


def run(output_dir: Path = DEFAULT_OUTPUT_DIR, input_dir: Path = DEFAULT_INPUT_DIR) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing existing output receipts: {output_dir}")
    sources = [_load_artifact(identifier, input_dir) for identifier in ARTIFACT_SHA256]
    rows = [_field_row(source) for source in sources]
    by_id = {row["id"]: row for row in rows}
    comparisons = [
        _comparison("R12_n384_vs_R12_n768", by_id["q16_R12_n384_refine"], by_id["q16_R12_n768_refine"]),
        _comparison("R12_n384_vs_R24_n768_same_spacing", by_id["q16_R12_n384_refine"], by_id["q16_R24_n768_refine"]),
    ]
    any_contradiction = any(row["verdict"] == "CONTRADICTS" for row in rows)
    all_rows_support = all(row["verdict"] == "SUPPORTS" for row in rows)
    all_comparisons_pass = all(item["pass"] for item in comparisons)
    verdict = "CONTRADICTS" if any_contradiction else ("SUPPORTS" if all_rows_support and all_comparisons_pass else "INCONCLUSIVE")
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "prereg_sha256": canonical_sha256(PREREG_PATH),
        "source_sha256": canonical_sha256(Path(__file__).resolve()),
        "rows": rows,
        "comparisons": comparisons,
        "verdict": verdict,
    }
    write_json(output_dir / "results.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    receipt = run(args.output_dir.resolve(), args.input_dir.resolve())
    print("id                              lambda0       lambda1       phase       overlap  trans    verdict")
    for row in receipt["rows"]:
        print(
            f"{row['id']:<31} {row['amplitude0']['eigenvalues'][0]: .6e} "
            f"{row['amplitude1']['eigenvalues'][0]: .6e} {row['phase']['eigenvalues'][0]: .6e} "
            f"{row['phase_overlap']:.6f} {row['translation_overlap']:.6f} {row['verdict']}"
        )
    print(f"combined verdict: {receipt['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
