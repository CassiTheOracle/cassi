#!/usr/bin/env python3
"""Primary fixed-signed-charge radial stability calculation.

The frozen radial fields are immutable inputs.  This program independently
assembles the spherical finite-volume operator, evaluates the source witness,
solves the unprojected amplitude problem and writes the preregistered receipt.
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
from scipy.linalg import eigh

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "runs" / "20260906_matter_formation_radial"
DEFAULT_OUTPUT_DIR = ROOT / "runs" / "20260906_matter_formation_charged_stability"
PREREG_PATH = ROOT / "computations" / "matter-formation-charged-stability-prereg.md"
VERIFIER_PATH = ROOT / "computations" / "verify_matter_formation_charged_stability.py"
SCHEMA = "cassi.matter-formation.charged-stability.v1"

COEFFICIENTS = {
    "u_rho": 4.0,
    "u_C": 1.0,
    "k_Cx": 1.0,
    "e_C": 0.75,
    "h_C": 2.9598260763447164,
}
ARTIFACT_SHA256 = {
    "q16_R12_n192_w2": "52540cf2cc11fcb313ecf689ffb5115c72480813cb7c866f348050bee33ad777",
    "q16_R12_n384_refine": "2e21fa2158d7fc7f9bff65bf337558af1bc0ca76520ea441611b37ab91e9d770",
    "q16_R12_n768_refine": "335364c4e655de4a34b51c0558c3a7559f45311d7f2973b262de4fd2c61db7be",
    "q16_R24_n768_refine": "92c49919d8fb748dffb7a9e3d4ba497214beb883fb837195dcc8a321ec06096b",
    "q256_R12_n192_w2": "ce3d7efcf133fd2fd5776203a86d53469f4b91b4919ca1bbdcce054dc02233ba",
    "q256_R12_n384_refine": "e450c22a6baf8312fa67ca58745ad593879bf6d18615a83ad0cbe8dacabb11d5",
    "q256_R12_n768_refine": "95df301fcea98304434b95e9dd63a9cec987495ddda9af46e5940891672dc77a",
    "q256_R24_n768_refine": "7f839b59fa3a0a4c9ca6897ec3962aec2b7f62d20a1751968482349a22742b66",
}
TARGET_POPULATIONS = {"q16": 16.0, "q256": 256.0}
A_VALUES = (1.0 / 64.0, 1.0 / 32.0, 1.0 / 16.0)
A_LABELS = {1.0 / 64.0: "a64", 1.0 / 32.0: "a32", 1.0 / 16.0: "a16"}
DILATION_VALUES = (0.5, 0.75, 1.0, 1.25, 1.5)

RADIAL_VERDICT_SUPPORT = "SUPPORTS—finite-grid radial fixed-charge energetic stability"
RADIAL_VERDICT_CONTRADICT = "CONTRADICTS—finite-grid radial fixed-charge energetic stability"
RADIAL_VERDICT_INCONCLUSIVE = "INCONCLUSIVE—finite-grid radial fixed-charge energetic stability"
COMPARISON_SUPPORT = "SUPPORTS—radial domain/resolution qualification"
COMPARISON_INCONCLUSIVE = "INCONCLUSIVE—radial domain/resolution qualification"


class ContractError(RuntimeError):
    """A frozen input, schema, or numerical contract violation."""


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return os.path.relpath(path.resolve(), ROOT).replace("\\", "/")


def finite_scalar(value: Any, label: str) -> float:
    array = np.asarray(value, dtype=np.float64)
    if array.size != 1:
        raise ContractError(f"{label} is not scalar")
    result = float(array.reshape(()))
    if not math.isfinite(result):
        raise ContractError(f"{label} is not finite")
    return result


def _assemble_stiffness(volumes: np.ndarray, radius: float, n: int) -> tuple[np.ndarray, float, float]:
    dr = float(radius) / int(n)
    faces = np.arange(n + 1, dtype=np.float64) * dr
    expected = (4.0 * math.pi / 3.0) * (faces[1:] ** 3 - faces[:-1] ** 3)
    if not np.allclose(volumes, expected, rtol=2.0e-13, atol=2.0e-15):
        raise ContractError("source volumes do not match exact spherical cells")
    conductance = 4.0 * math.pi * faces[1:-1] ** 2 / dr
    outer = 8.0 * math.pi * radius * radius / dr
    K = np.zeros((n, n), dtype=np.float64)
    if n > 1:
        indices = np.arange(n - 1)
        K[indices, indices] += conductance
        K[indices + 1, indices + 1] += conductance
        K[indices, indices + 1] -= conductance
        K[indices + 1, indices] -= conductance
    K[-1, -1] += outer
    return K, dr, outer


def _load_source(identifier: str, input_dir: Path) -> dict[str, Any]:
    if identifier not in ARTIFACT_SHA256:
        raise ContractError(f"unregistered source identifier {identifier}")
    path = input_dir / f"{identifier}.npz"
    if not path.is_file():
        raise ContractError(f"missing source artifact {path}")
    actual_hash = raw_sha256(path)
    if actual_hash != ARTIFACT_SHA256[identifier]:
        raise ContractError(f"source byte hash mismatch for {identifier}: {actual_hash}")
    with np.load(path, allow_pickle=False) as archive:
        required = {"r", "volumes", "f", "c", "R", "q"}
        if set(archive.files) != required:
            raise ContractError(f"source schema mismatch for {identifier}")
        r = np.asarray(archive["r"], dtype=np.float64)
        volumes = np.asarray(archive["volumes"], dtype=np.float64)
        f = np.asarray(archive["f"], dtype=np.float64)
        c = np.asarray(archive["c"], dtype=np.float64)
        radius = finite_scalar(archive["R"], f"{identifier}.R")
        population = finite_scalar(archive["q"], f"{identifier}.q")
    if any(array.ndim != 1 for array in (r, volumes, f, c)):
        raise ContractError(f"source arrays are not one-dimensional: {identifier}")
    if not (r.size == volumes.size == f.size == c.size) or r.size < 6:
        raise ContractError(f"source array shapes mismatch: {identifier}")
    prefix = identifier.split("_", 1)[0]
    if prefix not in TARGET_POPULATIONS or population != TARGET_POPULATIONS[prefix]:
        raise ContractError(f"source population mismatch: {identifier}")
    expected_grid = {"q16_R12_n192_w2": (12.0, 192), "q16_R12_n384_refine": (12.0, 384),
                     "q16_R12_n768_refine": (12.0, 768), "q16_R24_n768_refine": (24.0, 768),
                     "q256_R12_n192_w2": (12.0, 192), "q256_R12_n384_refine": (12.0, 384),
                     "q256_R12_n768_refine": (12.0, 768), "q256_R24_n768_refine": (24.0, 768)}[identifier]
    if radius != expected_grid[0] or r.size != expected_grid[1] or not radius > 0.0:
        raise ContractError(f"source grid metadata mismatch: {identifier}")
    dr = radius / r.size
    expected_r = (np.arange(r.size, dtype=np.float64) + 0.5) * dr
    if not np.allclose(r, expected_r, rtol=2.0e-13, atol=2.0e-15):
        raise ContractError(f"source centres are not exact cell centres: {identifier}")
    if not (np.all(np.isfinite(r)) and np.all(np.isfinite(volumes)) and np.all(np.isfinite(f)) and np.all(np.isfinite(c))):
        raise ContractError(f"source contains nonfinite values: {identifier}")
    K, dr, outer = _assemble_stiffness(volumes, radius, int(r.size))
    return {"id": identifier, "path": path, "artifact_sha256": actual_hash, "r": r,
            "volumes": volumes, "f": f, "c": c, "R": radius, "q": population,
            "n": int(r.size), "dr": dr, "K": K, "outer": outer}


def _source_diagnostics(source: dict[str, Any]) -> dict[str, float | bool]:
    f, c, V, K = source["f"], source["c"], source["volumes"], source["K"]
    outer = float(source["outer"])
    gf = K @ f
    gf[-1] -= outer
    gc = K @ c
    rho = f * f - 1.0
    carrier_potential = COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f)
    gf += V * (COEFFICIENTS["u_rho"] * f * rho + 2.0 * COEFFICIENTS["h_C"] * f * c * c)
    gc += V * (2.0 * carrier_potential * c + 2.0 * COEFFICIENTS["u_C"] * c ** 3)
    norm = float(np.dot(V, c * c))
    if not math.isfinite(norm) or norm <= 0.0:
        raise ContractError(f"nonpositive source population: {source['id']}")
    omega = float(np.dot(c, gc) / (2.0 * norm))
    f_residual_field = gf / np.sqrt(V)
    c_residual_field = np.sqrt(V) * (gc / (2.0 * V) - omega * c)
    f_scale = max(1.0, math.sqrt(float(np.dot(V, (1.0 - f) ** 2))))
    c_scale = max(1.0, math.sqrt(norm))
    residual_f = float(np.linalg.norm(f_residual_field) / f_scale)
    residual_c = float(np.linalg.norm(c_residual_field) / c_scale)
    charge_error = abs(norm - float(source["q"])) / float(source["q"])
    gradient = 0.5 * float(np.dot(f, K @ f)) - outer * float(f[-1]) + 0.5 * outer
    gradient += 0.5 * COEFFICIENTS["k_Cx"] * float(np.dot(c, K @ c))
    potential_density = COEFFICIENTS["u_rho"] / 4.0 * rho * rho + carrier_potential * c * c + COEFFICIENTS["u_C"] / 2.0 * c ** 4
    potential = float(np.dot(V, potential_density))
    values = (norm, omega, residual_f, residual_c, charge_error, gradient, potential)
    if not all(math.isfinite(value) for value in values):
        raise ContractError(f"nonfinite source diagnostic: {source['id']}")
    qualified = bool(charge_error < 1.0e-10 and residual_f < 1.0e-4 and residual_c < 1.0e-4)
    return {"norm": norm, "omega_C": omega, "residual_f": residual_f, "residual_c": residual_c,
            "charge_error": charge_error, "gradient": gradient, "potential": potential,
            "energy": gradient + potential, "source_qualified": qualified}


def _mass_weighted_hessian(source: dict[str, Any], omega_C: float) -> tuple[np.ndarray, np.ndarray]:
    f, c, V, K = source["f"], source["c"], source["volumes"], source["K"]
    inv_sqrt = 1.0 / np.sqrt(V)
    D0 = K * np.outer(inv_sqrt, inv_sqrt)
    diagonal_f = COEFFICIENTS["u_rho"] * (3.0 * f * f - 1.0) + 2.0 * COEFFICIENTS["h_C"] * c * c
    diagonal_c = 2.0 * (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f) - omega_C) + 6.0 * COEFFICIENTS["u_C"] * c * c
    off_diagonal = 4.0 * COEFFICIENTS["h_C"] * f * c
    H = np.zeros((2 * source["n"], 2 * source["n"]), dtype=np.float64)
    H[:source["n"], :source["n"]] = D0
    H[source["n"]:, source["n"]:] = COEFFICIENTS["k_Cx"] * D0
    indices = np.arange(source["n"])
    H[indices, indices] += diagonal_f
    H[source["n"] + indices, source["n"] + indices] += diagonal_c
    H[indices, source["n"] + indices] = off_diagonal
    H[source["n"] + indices, indices] = off_diagonal
    if not np.all(np.isfinite(H)) or not np.allclose(H, H.T, rtol=0.0, atol=0.0):
        raise ContractError(f"non-symmetric/nonfinite Hessian: {source['id']}")
    g = np.concatenate((np.zeros(source["n"], dtype=np.float64), 2.0 * np.sqrt(V) * c))
    return H, g


def _eigenpairs(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    values, vectors = eigh(matrix, driver="evr", subset_by_index=(0, 5), check_finite=True)
    values = np.asarray(values, dtype=np.float64)
    vectors = np.asarray(vectors, dtype=np.float64)
    residuals = np.asarray([np.linalg.norm(matrix @ vectors[:, j] - values[j] * vectors[:, j]) / max(1.0, abs(float(values[j]))) for j in range(6)], dtype=np.float64)
    orthogonality = float(np.max(np.abs(vectors.T @ vectors - np.eye(6, dtype=np.float64))))
    if not (np.all(np.isfinite(values)) and np.all(np.isfinite(vectors)) and np.all(np.isfinite(residuals)) and math.isfinite(orthogonality)):
        raise ContractError("nonfinite spectral witness")
    return values, vectors, residuals, orthogonality


def _dilation(source: dict[str, Any], signed_charge: float, a: float) -> list[dict[str, float]]:
    f, c, V, K = source["f"], source["c"], source["volumes"], source["K"]
    outer = float(source["outer"])
    result: list[dict[str, float]] = []
    rho = f * f - 1.0
    carrier_potential = COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f)
    for lam in DILATION_VALUES:
        K_scaled = lam * K
        V_scaled = (lam ** 3) * V
        outer_scaled = lam * outer
        gradient = 0.5 * float(np.dot(f, K_scaled @ f)) - outer_scaled * float(f[-1]) + 0.5 * outer_scaled
        gradient += 0.5 * COEFFICIENTS["k_Cx"] * float(np.dot(c, K_scaled @ c))
        potential_density = COEFFICIENTS["u_rho"] / 4.0 * rho * rho + carrier_potential * c * c + COEFFICIENTS["u_C"] / 2.0 * c ** 4
        potential = float(np.dot(V_scaled, potential_density))
        norm_scaled = float(np.dot(V_scaled, c * c))
        if not math.isfinite(norm_scaled) or norm_scaled <= 0.0:
            raise ContractError(f"invalid dilation norm: {source['id']}")
        temporal = (norm_scaled - signed_charge) ** 2 / (4.0 * a * norm_scaled)
        energy = gradient + potential + temporal
        if not math.isfinite(energy):
            raise ContractError(f"nonfinite dilation energy: {source['id']}")
        result.append({"lambda": float(lam), "energy": float(energy)})
    return result


def _write_npz_exclusive(path: Path, arrays: dict[str, np.ndarray]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        np.savez(handle, **{key: np.asarray(value, dtype=np.float64) for key, value in arrays.items()})
    return raw_sha256(path)


def _write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _comparison(population: float, a: float, pair: str, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_value = float(next(parent for parent in left["parents"] if parent["a"] == a)["eigenvalues"][0])
    right_value = float(next(parent for parent in right["parents"] if parent["a"] == a)["eigenvalues"][0])
    tolerance = max(0.01 * max(abs(left_value), abs(right_value)), float(left["eta"]), float(right["eta"]))
    difference = abs(left_value - right_value)
    return {"population": population, "a": float(a), "pair": pair, "left": left["id"], "right": right["id"],
            "absolute_difference": float(difference), "tolerance": float(tolerance), "pass": bool(difference <= tolerance)}


def run(output_dir: Path = DEFAULT_OUTPUT_DIR, input_dir: Path = DEFAULT_INPUT_DIR) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    input_dir = input_dir.resolve()
    if (output_dir / "results.json").exists() or any(output_dir.glob("spectra_*.npz")):
        raise FileExistsError(f"refusing existing charged-stability artifacts: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    if not PREREG_PATH.is_file() or not VERIFIER_PATH.is_file():
        raise ContractError("runtime identity source/spec is missing")
    primary_path = Path(__file__).resolve()
    identities = {
        "primary": {"path": relative_path(primary_path), "sha256": canonical_sha256(primary_path)},
        "verifier": {"path": relative_path(VERIFIER_PATH), "sha256": canonical_sha256(VERIFIER_PATH)},
        "preregistration": {"path": relative_path(PREREG_PATH), "sha256": canonical_sha256(PREREG_PATH)},
    }
    sources = [_load_source(identifier, input_dir) for identifier in ARTIFACT_SHA256]
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for source in sources:
        diagnostics = _source_diagnostics(source)
        H0, g = _mass_weighted_hessian(source, float(diagnostics["omega_C"]))
        base_values, base_vectors, base_residuals, base_orthogonality = _eigenpairs(H0)
        try:
            response = np.linalg.solve(H0, g)
        except np.linalg.LinAlgError as error:
            raise ContractError(f"singular base response: {source['id']}") from error
        response = np.asarray(response, dtype=np.float64)
        response_residual = float(np.linalg.norm(H0 @ response - g) / max(1.0, np.linalg.norm(g)))
        response_scalar = float(np.dot(g, response))
        if not (np.all(np.isfinite(response)) and math.isfinite(response_residual) and math.isfinite(response_scalar)):
            raise ContractError(f"nonfinite base response: {source['id']}")
        eta = max(5.0e-4, 10.0 * float(diagnostics["residual_f"]), 10.0 * float(diagnostics["residual_c"]))
        negative_count = int(np.count_nonzero(base_values < -eta))
        unresolved_count = int(np.count_nonzero(np.abs(base_values) <= eta))
        inertia_qualified = bool(base_values[5] > eta and unresolved_count == 0)
        base = {"eigenvalues": [float(x) for x in base_values], "eigenpair_residuals": [float(x) for x in base_residuals],
                "orthonormality_error": float(base_orthogonality), "negative_count": negative_count,
                "unresolved_count": unresolved_count, "inertia_qualified": inertia_qualified,
                "response_scalar": response_scalar, "response_residual": response_residual}
        base_numerical = bool(max(base_residuals) < 1.0e-8 and base_orthogonality < 1.0e-8 and response_residual < 1.0e-8)
        parents_by_a: dict[str, dict[str, Any]] = {}
        parent_arrays: dict[str, np.ndarray] = {}
        for a in A_VALUES:
            D = 1.0 + 4.0 * a * float(diagnostics["omega_C"])
            if not math.isfinite(D) or D <= 0.0:
                raise ContractError(f"nonpositive parent D for {source['id']} at {a}")
            radius = math.sqrt(D)
            omega = 2.0 * float(diagnostics["omega_C"]) / (1.0 + radius)
            signed_charge = radius * float(diagnostics["norm"])
            gamma = signed_charge * signed_charge / (2.0 * a * float(diagnostics["norm"]) ** 3)
            Hq = H0 + gamma * np.outer(g, g)
            parent_values, parent_vectors, parent_residuals, parent_orthogonality = _eigenpairs(Hq)
            slope_factor = 1.0 + gamma * response_scalar
            charge_derivative = 2.0 * a * float(diagnostics["norm"]) + D * response_scalar
            slope_applicable = bool(inertia_qualified and negative_count == 1)
            slope_predicts_positive = bool(slope_factor < 0.0) if slope_applicable else None
            slope_consistent = not (
                (parent_values[0] > eta and slope_applicable and slope_predicts_positive is False)
                or (parent_values[0] < -eta and slope_applicable and slope_predicts_positive is True)
            )
            if not slope_consistent:
                failures.append(f"slope prediction contradicts spectrum: {source['id']} at {a}")
            parent_numerical = bool(max(parent_residuals) < 1.0e-8 and parent_orthogonality < 1.0e-8)
            if not (diagnostics["source_qualified"] and inertia_qualified and base_numerical and parent_numerical and slope_consistent):
                radial_verdict = RADIAL_VERDICT_INCONCLUSIVE
            elif parent_values[0] > eta:
                radial_verdict = RADIAL_VERDICT_SUPPORT
            elif parent_values[0] < -eta:
                radial_verdict = RADIAL_VERDICT_CONTRADICT
            else:
                radial_verdict = RADIAL_VERDICT_INCONCLUSIVE
            label = A_LABELS[a]
            parent = {"a": float(a), "D": float(D), "r": float(radius), "omega": float(omega),
                      "signed_charge": float(signed_charge), "gamma": float(gamma), "slope_factor": float(slope_factor),
                      "charge_derivative": float(charge_derivative), "slope_applicable": slope_applicable,
                      "slope_predicts_positive": slope_predicts_positive, "eigenvalues": [float(x) for x in parent_values],
                      "eigenpair_residuals": [float(x) for x in parent_residuals], "orthonormality_error": float(parent_orthogonality),
                      "dilation": _dilation(source, signed_charge, a), "radial_verdict": radial_verdict}
            parents_by_a[label] = parent
            parent_arrays[f"parent_{label}_values"] = parent_values
            parent_arrays[f"parent_{label}_vectors"] = parent_vectors
        spectra_name = f"spectra_{source['id']}.npz"
        spectra_path = output_dir / spectra_name
        arrays = {"base_eigenvalues": base_values, "base_vectors": base_vectors, "response": response}
        arrays.update(parent_arrays)
        spectra_hash = _write_npz_exclusive(spectra_path, arrays)
        row = {"id": source["id"], "artifact": relative_path(source["path"]), "artifact_sha256": source["artifact_sha256"],
               "R": float(source["R"]), "n": int(source["n"]), "target_population": float(source["q"]),
               "norm": float(diagnostics["norm"]), "energy": float(diagnostics["energy"]), "gradient": float(diagnostics["gradient"]),
               "potential": float(diagnostics["potential"]), "omega_C": float(diagnostics["omega_C"]),
               "residual_f": float(diagnostics["residual_f"]), "residual_c": float(diagnostics["residual_c"]), "eta": float(eta),
               "source_qualified": bool(diagnostics["source_qualified"]), "base": base,
               "spectra": {"path": spectra_name, "sha256": spectra_hash}, "parents": [parents_by_a[A_LABELS[a]] for a in A_VALUES]}
        rows.append(row)
    by_id = {row["id"]: row for row in rows}
    comparisons: list[dict[str, Any]] = []
    for population, prefix in ((16.0, "q16"), (256.0, "q256")):
        for a in A_VALUES:
            left = by_id[f"{prefix}_R12_n384_refine"]
            right_resolution = by_id[f"{prefix}_R12_n768_refine"]
            right_domain = by_id[f"{prefix}_R24_n768_refine"]
            comparisons.append(_comparison(population, a, "resolution", left, right_resolution))
            comparisons.append(_comparison(population, a, "domain", left, right_domain))
    for row in rows:
        if not row["source_qualified"]:
            failures.append(f"source qualification failed: {row['id']}")
        base = row["base"]
        if max(base["eigenpair_residuals"]) >= 1.0e-8 or base["orthonormality_error"] >= 1.0e-8 or base["response_residual"] >= 1.0e-8:
            failures.append(f"base numerical qualification failed: {row['id']}")
        for parent in row["parents"]:
            if max(parent["eigenpair_residuals"]) >= 1.0e-8 or parent["orthonormality_error"] >= 1.0e-8:
                failures.append(f"parent numerical qualification failed: {row['id']} a={parent['a']}")
    contradiction = any(parent["radial_verdict"] == RADIAL_VERDICT_CONTRADICT for row in rows for parent in row["parents"])
    all_support = all(parent["radial_verdict"] == RADIAL_VERDICT_SUPPORT for row in rows for parent in row["parents"])
    radial_verdict = RADIAL_VERDICT_CONTRADICT if contradiction else (RADIAL_VERDICT_SUPPORT if all_support else RADIAL_VERDICT_INCONCLUSIVE)
    comparison_verdict = COMPARISON_SUPPORT if all(item["pass"] for item in comparisons) else COMPARISON_INCONCLUSIVE
    numerical_pass = bool(not failures)
    receipt = {"schema": SCHEMA, "coefficients": COEFFICIENTS.copy(), "identities": identities,
               "input_directory": relative_path(input_dir), "rows": rows, "comparisons": comparisons,
               "failures": failures, "numerical_pass": numerical_pass, "radial_verdict": radial_verdict,
               "comparison_verdict": comparison_verdict}
    _write_json_exclusive(output_dir / "results.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    receipt = run(args.output_dir, args.input_dir)
    print(json.dumps({"numerical_pass": receipt["numerical_pass"], "radial_verdict": receipt["radial_verdict"], "comparison_verdict": receipt["comparison_verdict"]}, sort_keys=True))
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
