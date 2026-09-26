#!/usr/bin/env python3
"""Primary scalar-parent angular and phase spatial qualification."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.linalg import eigh

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "runs" / "20260906_matter_formation_radial"
DEFAULT_RADIAL_DIR = ROOT / "runs" / "20260906_matter_formation_charged_stability"
DEFAULT_OUTPUT_DIR = ROOT / "runs" / "20260906_matter_formation_parent_spatial"
PREREG_PATH = ROOT / "computations" / "matter-formation-parent-spatial-prereg.md"
VERIFIER_PATH = ROOT / "computations" / "verify_matter_formation_parent_spatial.py"
SCHEMA = "cassi.matter-formation.parent-spatial.v1"
COEFFICIENTS = {"u_rho": 4.0, "u_C": 1.0, "e_C": 0.75, "h_C": 2.9598260763447164, "k_Cx": 1.0}
SOURCE_IDS = ("q256_R12_n192_w2", "q256_R12_n384_refine", "q256_R12_n768_refine", "q256_R24_n768_refine")
SOURCE_HASHES = {
    "q256_R12_n192_w2": "ce3d7efcf133fd2fd5776203a86d53469f4b91b4919ca1bbdcce054dc02233ba",
    "q256_R12_n384_refine": "e450c22a6baf8312fa67ca58745ad593879bf6d18615a83ad0cbe8dacabb11d5",
    "q256_R12_n768_refine": "95df301fcea98304434b95e9dd63a9cec987495ddda9af46e5940891672dc77a",
    "q256_R24_n768_refine": "7f839b59fa3a0a4c9ca6897ec3962aec2b7f62d20a1751968482349a22742b66",
}
EXPECTED_GRID = {"q256_R12_n192_w2": (12.0, 192), "q256_R12_n384_refine": (12.0, 384), "q256_R12_n768_refine": (12.0, 768), "q256_R24_n768_refine": (24.0, 768)}
A_VALUES = (1.0 / 64.0, 1.0 / 32.0, 1.0 / 16.0)
RADIAL_RESULTS_HASH = "540bf259441b42ac476189dcd8593ae3b57a4fe25bb8fe17c846d5465068b0bc"
RADIAL_VERIFICATION_HASH = "7f299ed6401014760b174895781d253ffebe6fad3c2a11e801506c9759e2d255"
RADIAL_SUPPORT = "SUPPORTS—finite-grid radial fixed-charge energetic stability"
SECTOR_SUPPORT = "SUPPORTS—finite-grid scalar angular and phase energetic qualification"
SECTOR_CONTRADICT = "CONTRADICTS—finite-grid scalar angular and phase energetic qualification"
SECTOR_INCONCLUSIVE = "INCONCLUSIVE—finite-grid scalar angular and phase energetic qualification"
COMPARISON_SUPPORT = "SUPPORTS—scalar spatial domain/resolution qualification"
COMPARISON_INCONCLUSIVE = "INCONCLUSIVE—scalar spatial domain/resolution qualification"
PARENT_SUPPORT = "SUPPORTS—finite-grid scalar parent spatial energetic qualification"
PARENT_CONTRADICT = "CONTRADICTS—finite-grid scalar parent spatial energetic qualification"
PARENT_INCONCLUSIVE = "INCONCLUSIVE—finite-grid scalar parent spatial energetic qualification"
OPERATORS = ("amp1", "amp2", "phase0", "phase1")
METRICS = ("amp1_gap", "amp2_minimum", "phase0_gap", "phase1_minimum")


class ContractError(RuntimeError):
    pass


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return os.path.relpath(path.resolve(), ROOT.resolve()).replace("\\", "/")


def finite_scalar(value: Any, label: str) -> float:
    array = np.asarray(value, dtype=np.float64)
    if array.size != 1:
        raise ContractError(f"{label} is not scalar")
    result = float(array.reshape(()))
    if not math.isfinite(result):
        raise ContractError(f"{label} is not finite")
    return result


def require_finite_payload(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError("nonfinite successful-row field")
    if isinstance(value, Mapping):
        for item in value.values():
            require_finite_payload(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            require_finite_payload(item)


def write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if path.exists() or temporary.exists():
        raise FileExistsError(f"refusing existing receipt or temporary artifact: {path}")
    created = False
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    except Exception:
        if created:
            temporary.unlink(missing_ok=True)
        raise


def write_spectra(path: Path, arrays: Mapping[str, np.ndarray]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if path.exists() or temporary.exists():
        raise FileExistsError(f"refusing existing spectral or temporary artifact: {path}")
    created = False
    try:
        with temporary.open("xb") as stream:
            created = True
            np.savez(stream, **arrays)
        os.replace(temporary, path)
    except Exception:
        if created:
            temporary.unlink(missing_ok=True)
        raise
    return raw_sha256(path)


def _identity(path: Path, label: str, failures: list[str]) -> dict[str, str]:
    item = {"path": relative_path(path), "sha256": ""}
    try:
        item["sha256"] = canonical_sha256(path)
    except Exception as exc:
        failures.append(f"missing {label} identity: {type(exc).__name__}: {exc}")
    return item


def identities(failures: list[str]) -> dict[str, dict[str, str]]:
    return {
        "primary": _identity(Path(__file__).resolve(), "primary", failures),
        "verifier": _identity(VERIFIER_PATH, "verifier", failures),
        "prereg": _identity(PREREG_PATH, "preregistration", failures),
    }


def assemble_stiffness(volumes: np.ndarray, radius: float, n: int) -> tuple[np.ndarray, float, float]:
    dr = float(radius) / int(n)
    faces = np.arange(n + 1, dtype=np.float64) * dr
    expected = (4.0 * math.pi / 3.0) * (faces[1:] ** 3 - faces[:-1] ** 3)
    if not np.allclose(volumes, expected, rtol=2.0e-13, atol=2.0e-15):
        raise ContractError("source volumes do not match exact spherical cells")
    conductance = 4.0 * math.pi * faces[1:-1] ** 2 / dr
    outer = 8.0 * math.pi * radius * radius / dr
    K = np.zeros((n, n), dtype=np.float64)
    if n > 1:
        index = np.arange(n - 1)
        K[index, index] += conductance
        K[index + 1, index + 1] += conductance
        K[index, index + 1] -= conductance
        K[index + 1, index] -= conductance
    K[-1, -1] += outer
    return K, dr, outer


def load_source(identifier: str, source_dir: Path) -> dict[str, Any]:
    path = source_dir / f"{identifier}.npz"
    if identifier not in SOURCE_HASHES or not path.is_file():
        raise ContractError(f"missing source artifact {path}")
    actual = raw_sha256(path)
    if actual != SOURCE_HASHES[identifier]:
        raise ContractError(f"source byte hash mismatch for {identifier}: {actual}")
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != {"r", "volumes", "f", "c", "R", "q"}:
            raise ContractError(f"source schema mismatch for {identifier}")
        if any(archive[key].dtype != np.dtype("float64") for key in ("r", "volumes", "f", "c")):
            raise ContractError(f"source array dtype mismatch: {identifier}")
        r = np.asarray(archive["r"], dtype=np.float64)
        volumes = np.asarray(archive["volumes"], dtype=np.float64)
        f = np.asarray(archive["f"], dtype=np.float64)
        c = np.asarray(archive["c"], dtype=np.float64)
        radius = finite_scalar(archive["R"], f"{identifier}.R")
        population = finite_scalar(archive["q"], f"{identifier}.q")
    if any(item.ndim != 1 for item in (r, volumes, f, c)) or not (r.size == volumes.size == f.size == c.size):
        raise ContractError(f"source array shape mismatch: {identifier}")
    expected_R, expected_n = EXPECTED_GRID[identifier]
    if radius != expected_R or r.size != expected_n:
        raise ContractError(f"source grid metadata mismatch: {identifier}")
    if population != 256.0:
        raise ContractError(f"source population mismatch: {identifier}")
    dr = radius / r.size
    expected_r = (np.arange(r.size, dtype=np.float64) + 0.5) * dr
    if not np.allclose(r, expected_r, rtol=2.0e-13, atol=2.0e-15):
        raise ContractError(f"source centres are not exact cell centres: {identifier}")
    if not all(np.all(np.isfinite(item)) for item in (r, volumes, f, c)):
        raise ContractError(f"source contains nonfinite values: {identifier}")
    K, _, outer = assemble_stiffness(volumes, radius, int(r.size))
    return {"id": identifier, "path": path, "artifact_sha256": actual, "r": r, "volumes": volumes, "f": f, "c": c, "R": radius, "n": int(r.size), "q": population, "dr": dr, "K": K, "outer": outer}


def source_diagnostics(source: Mapping[str, Any]) -> dict[str, Any]:
    f, c, V, K = source["f"], source["c"], source["volumes"], source["K"]
    outer = float(source["outer"])
    gf = K @ f
    gf[-1] -= outer
    gc = COEFFICIENTS["k_Cx"] * (K @ c)
    rho = f * f - 1.0
    A = COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f)
    gf += V * (COEFFICIENTS["u_rho"] * f * rho + 2.0 * COEFFICIENTS["h_C"] * f * c * c)
    gc += V * (2.0 * A * c + 2.0 * COEFFICIENTS["u_C"] * c ** 3)
    N = float(np.dot(V, c * c))
    if not math.isfinite(N) or N <= 0.0:
        raise ContractError(f"nonpositive source population: {source['id']}")
    omega = float(np.dot(c, gc) / (2.0 * N))
    residual_f = float(np.linalg.norm(gf / np.sqrt(V)) / max(1.0, np.linalg.norm(np.sqrt(V) * (1.0 - f))))
    residual_c = float(np.linalg.norm(np.sqrt(V) * (gc / (2.0 * V) - omega * c)) / math.sqrt(N))
    population_error = abs(N - float(source["q"])) / float(source["q"])
    values = (N, omega, residual_f, residual_c, population_error)
    if not all(math.isfinite(item) for item in values):
        raise ContractError(f"nonfinite source diagnostic: {source['id']}")
    source_qualified = bool(population_error < 1.0e-10 and residual_f < 1.0e-4 and residual_c < 1.0e-4 and np.all(f >= 0.0) and np.all(c >= 0.0))
    return {"population": N, "omega_C": omega, "residual_f": residual_f, "residual_c": residual_c, "population_relative_error": population_error, "eta": max(5.0e-4, 10.0 * residual_f, 10.0 * residual_c), "source_qualified": source_qualified, "profile": {"min_f": float(np.min(f)), "min_c": float(np.min(c)), "min_f_difference": float(np.min(np.diff(f))), "max_c_difference": float(np.max(np.diff(c)))}}


def derivative(values: np.ndarray, dr: float) -> np.ndarray:
    result = np.empty_like(values, dtype=np.float64)
    result[1:-1] = (values[2:] - values[:-2]) / (2.0 * dr)
    result[0] = (-3.0 * values[0] + 4.0 * values[1] - values[2]) / (2.0 * dr)
    result[-1] = (3.0 * values[-1] - 4.0 * values[-2] + values[-3]) / (2.0 * dr)
    return result


def operators(source: Mapping[str, Any], omega: float) -> dict[str, np.ndarray]:
    f, c, V, K = source["f"], source["c"], source["volumes"], source["K"]
    n, dr = int(source["n"]), float(source["dr"])
    inv_sqrt = 1.0 / np.sqrt(V)
    D0 = K * np.outer(inv_sqrt, inv_sqrt)
    angular = 4.0 * math.pi * dr / V
    diagonal = np.arange(n)
    carrier_diagonal = n + diagonal
    potential = COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f) - omega
    def phase(ell: int) -> np.ndarray:
        matrix = COEFFICIENTS["k_Cx"] * D0
        matrix[diagonal, diagonal] += COEFFICIENTS["k_Cx"] * ell * (ell + 1) * angular + 2.0 * potential + 2.0 * COEFFICIENTS["u_C"] * c * c
        return matrix
    def amplitude(ell: int) -> np.ndarray:
        H = np.zeros((2 * n, 2 * n), dtype=np.float64)
        H[:n, :n] = D0
        H[n:, n:] = COEFFICIENTS["k_Cx"] * D0
        H[diagonal, diagonal] += ell * (ell + 1) * angular + COEFFICIENTS["u_rho"] * (3.0 * f * f - 1.0) + 2.0 * COEFFICIENTS["h_C"] * c * c
        H[carrier_diagonal, carrier_diagonal] += COEFFICIENTS["k_Cx"] * ell * (ell + 1) * angular + 2.0 * potential + 6.0 * COEFFICIENTS["u_C"] * c * c
        mixed = 4.0 * COEFFICIENTS["h_C"] * f * c
        H[diagonal, carrier_diagonal] = mixed
        H[carrier_diagonal, diagonal] = mixed
        return H
    return {"amp1": amplitude(1), "amp2": amplitude(2), "phase0": phase(0), "phase1": phase(1)}


def eigenpairs(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    values, vectors = eigh(matrix, driver="evr", subset_by_index=(0, 5), check_finite=True)
    values, vectors = np.asarray(values, dtype=np.float64), np.asarray(vectors, dtype=np.float64)
    residuals = np.asarray([np.linalg.norm(matrix @ vectors[:, j] - values[j] * vectors[:, j]) / max(1.0, abs(float(values[j]))) for j in range(6)], dtype=np.float64)
    orthogonality = float(np.max(np.abs(vectors.T @ vectors - np.eye(6, dtype=np.float64))))
    if not all(np.all(np.isfinite(item)) for item in (values, vectors, residuals)) or not math.isfinite(orthogonality):
        raise ContractError("nonfinite spectral witness")
    return values, vectors, residuals, orthogonality


def spectral_measurements(source: Mapping[str, Any], matrices: Mapping[str, np.ndarray]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    spectra: dict[str, Any] = {}
    arrays: dict[str, np.ndarray] = {}
    for name in OPERATORS:
        values, vectors, residuals, orthogonality = eigenpairs(matrices[name])
        spectra[name] = {"eigenvalues": [float(x) for x in values], "eigenpair_residuals": [float(x) for x in residuals], "orthonormality_error": float(orthogonality)}
        arrays[f"{name}_values"] = values
        arrays[f"{name}_vectors"] = vectors
    V, f, c = source["volumes"], source["f"], source["c"]
    p = np.sqrt(V) * c
    t = np.concatenate((np.sqrt(V) * derivative(f, float(source["dr"])), np.sqrt(V) * derivative(c, float(source["dr"]))))
    p_norm, t_norm = float(np.linalg.norm(p)), float(np.linalg.norm(t))
    if not all(math.isfinite(value) and value > 0.0 for value in (p_norm, t_norm)):
        raise ContractError(f"invalid symmetry-vector norm: {source['id']}")
    p /= p_norm
    t /= t_norm
    amp_values = np.asarray(spectra["amp1"]["eigenvalues"], dtype=np.float64)
    phase_values = np.asarray(spectra["phase0"]["eigenvalues"], dtype=np.float64)
    amp_overlaps = np.abs(np.asarray(arrays["amp1_vectors"]).T @ t)
    phase_overlaps = np.abs(np.asarray(arrays["phase0_vectors"]).T @ p)
    amp_index, phase_index = int(np.argmax(amp_overlaps)), int(np.argmax(phase_overlaps))
    amp_residual = float(np.linalg.norm(matrices["amp1"] @ t))
    phase_residual = float(np.linalg.norm(matrices["phase0"] @ p))
    spectra["symmetries"] = {"translation": {"index": amp_index, "overlap": float(amp_overlaps[amp_index]), "eigenvalue": float(amp_values[amp_index]), "operator_residual": amp_residual}, "phase": {"index": phase_index, "overlap": float(phase_overlaps[phase_index]), "eigenvalue": float(phase_values[phase_index]), "operator_residual": phase_residual}}
    spectra["metrics"] = {"amp1_gap": float(np.min(np.delete(amp_values, amp_index))), "amp2_minimum": float(spectra["amp2"]["eigenvalues"][0]), "phase0_gap": float(np.min(np.delete(phase_values, phase_index))), "phase1_minimum": float(spectra["phase1"]["eigenvalues"][0])}
    return spectra, arrays


def inherited_radial(radial_dir: Path, failures: list[str]) -> tuple[dict[str, Any], bool, dict[str, Any] | None]:
    result_path, verify_path = radial_dir / "results.json", radial_dir / "verification.json"
    info: dict[str, Any] = {"results": {"path": relative_path(result_path), "sha256": ""}, "verification": {"path": relative_path(verify_path), "sha256": ""}, "qualified": False}
    try:
        if raw_sha256(result_path) != RADIAL_RESULTS_HASH:
            raise ContractError("accepted radial results raw hash mismatch")
        if raw_sha256(verify_path) != RADIAL_VERIFICATION_HASH:
            raise ContractError("accepted radial verification raw hash mismatch")
        info["results"]["sha256"], info["verification"]["sha256"] = RADIAL_RESULTS_HASH, RADIAL_VERIFICATION_HASH
        results = json.loads(result_path.read_text(encoding="utf-8")); verification = json.loads(verify_path.read_text(encoding="utf-8"))
        if results.get("numerical_pass") is not True or results.get("failures") != [] or verification.get("numerical_pass") is not True or verification.get("failures") != []:
            raise ContractError("accepted radial receipts are not numerically clean")
        if verification.get("input_sha256") != RADIAL_RESULTS_HASH:
            raise ContractError("radial verification input identity link mismatch")
        expected = {"preregistration": (ROOT / "computations/matter-formation-charged-stability-prereg.md"), "primary": (ROOT / "computations/matter_formation_charged_stability.py"), "verifier": (ROOT / "computations/verify_matter_formation_charged_stability.py")}
        for key, path in expected.items():
            item = results.get("identities", {}).get(key, {})
            if item.get("path") != relative_path(path) or item.get("sha256") != canonical_sha256(path):
                raise ContractError(f"radial primary identity mismatch: {key}")
        qrows = {row.get("id"): row for row in results.get("rows", []) if row.get("id", "").startswith("q256_")}
        if set(qrows) != set(SOURCE_IDS) or any(len(row.get("parents", [])) != len(A_VALUES) for row in qrows.values()):
            raise ContractError("radial population-256 parent schedule mismatch")
        for identifier, row in qrows.items():
            if row.get("source_qualified") is not True:
                raise ContractError(f"radial source not qualified: {identifier}")
            eta = float(row["eta"])
            for parent, expected_a in zip(row["parents"], A_VALUES):
                if float(parent.get("a")) != expected_a:
                    raise ContractError(f"radial parent coefficient schedule mismatch: {identifier}")
                if parent.get("radial_verdict") != RADIAL_SUPPORT or float(parent["eigenvalues"][0]) <= eta:
                    raise ContractError(f"radial parent qualification failed: {identifier}")
        expected_comparisons = {
            (float(a), "resolution", "q256_R12_n384_refine", "q256_R12_n768_refine") for a in A_VALUES
        } | {
            (float(a), "domain", "q256_R12_n384_refine", "q256_R24_n768_refine") for a in A_VALUES
        }
        def check_comparisons(items: Any, label: str) -> None:
            qcomparisons = [item for item in items if float(item.get("population", -1)) == 256.0]
            actual_comparisons = {
                (float(item.get("a")), item.get("pair"), item.get("left"), item.get("right"))
                for item in qcomparisons
            }
            if len(qcomparisons) != 6 or actual_comparisons != expected_comparisons or not all(item.get("pass") is True for item in qcomparisons):
                raise ContractError(f"{label} population-256 comparison schedule failed")
        check_comparisons(results.get("comparisons", []), "radial primary")
        check_comparisons(verification.get("comparisons", []), "radial verification")
        info["qualified"] = True
        return info, True, results
    except Exception as exc:
        failures.append(f"inherited radial validation: {type(exc).__name__}: {exc}")
        return info, False, None


def parent_rows(source: Mapping[str, Any], diagnostics: Mapping[str, Any], radial: Mapping[str, Any], spectral: Mapping[str, Any]) -> dict[str, Any]:
    radial_row = next(row for row in radial["rows"] if row["id"] == source["id"])
    parents = []
    for a, radial_parent in zip(A_VALUES, radial_row["parents"]):
        omega_c = float(diagnostics["omega_C"])
        discriminant = 1.0 + 4.0 * a * omega_c
        if discriminant <= 0.0 or not math.isfinite(discriminant):
            raise ContractError(f"invalid canonical frequency at {source['id']} a={a}")
        canonical = math.sqrt(discriminant) / (2.0 * a)
        gap = (COEFFICIENTS["e_C"] - omega_c) / a
        parents.append({"a": float(a), "radial_minimum": float(radial_parent["eigenvalues"][0]), "radial_verdict": radial_parent["radial_verdict"], "omega": 2.0 * omega_c / (1.0 + math.sqrt(discriminant)), "canonical_frequency": canonical, "exterior_mass_squared": 1.0 / (4.0 * a * a) + COEFFICIENTS["e_C"] / a, "exterior_frequency_gap_squared": gap, "depleted_mass_squared": 1.0 / (4.0 * a * a) + (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"]) / a})
    sector = sector_verdict(diagnostics, spectral)
    return {"id": source["id"], "artifact": relative_path(source["path"]), "artifact_sha256": source["artifact_sha256"], "R": float(source["R"]), "n": int(source["n"]), "target_population": 256.0, "population": float(diagnostics["population"]), "omega_C": float(diagnostics["omega_C"]), "population_relative_error": float(diagnostics["population_relative_error"]), "residual_f": float(diagnostics["residual_f"]), "residual_c": float(diagnostics["residual_c"]), "eta": float(diagnostics["eta"]), "source_qualified": bool(diagnostics["source_qualified"]), "profile": diagnostics["profile"], "asymptotic": {"mediator_spatial_gap": 2.0 * COEFFICIENTS["u_rho"], "carrier_spatial_gap": 2.0 * (COEFFICIENTS["e_C"] - float(diagnostics["omega_C"]))}, "parents": parents, "operators": {name: spectral[name] for name in OPERATORS}, "symmetries": spectral["symmetries"], "metrics": spectral["metrics"], "spectra": {}, "sector_verdict": sector}


def sector_verdict(diagnostics: Mapping[str, Any], spectral: Mapping[str, Any]) -> str:
    if not diagnostics["source_qualified"]:
        return SECTOR_INCONCLUSIVE
    if any(max(spectral[name]["eigenpair_residuals"]) >= 1.0e-8 or spectral[name]["orthonormality_error"] >= 1.0e-8 for name in OPERATORS):
        return SECTOR_INCONCLUSIVE
    eta = float(diagnostics["eta"])
    if any(float(spectral[name]["eigenvalues"][0]) < -eta for name in OPERATORS):
        return SECTOR_CONTRADICT
    sym = spectral["symmetries"]
    met = spectral["metrics"]
    if not (sym["translation"]["overlap"] > 0.99 and sym["phase"]["overlap"] > 0.99 and abs(sym["translation"]["eigenvalue"]) <= eta and abs(sym["phase"]["eigenvalue"]) <= eta and met["amp1_gap"] > eta and met["phase0_gap"] > eta and met["amp2_minimum"] > eta and met["phase1_minimum"] > eta):
        return SECTOR_INCONCLUSIVE
    return SECTOR_SUPPORT


def comparisons(rows: list[Mapping[str, Any]], failures: list[str]) -> list[dict[str, Any]]:
    by_id = {row["id"]: row for row in rows}
    result: list[dict[str, Any]] = []
    for metric in METRICS:
        for pair, right_id in (("resolution", "q256_R12_n768_refine"), ("domain", "q256_R24_n768_refine")):
            left_id = "q256_R12_n384_refine"
            if left_id not in by_id or right_id not in by_id:
                failures.append(f"missing spatial comparison {metric} {pair}")
                continue
            left = float(by_id[left_id]["metrics"][metric])
            right = float(by_id[right_id]["metrics"][metric])
            eta = max(float(by_id[left_id]["eta"]), float(by_id[right_id]["eta"]))
            tolerance = max(0.01 * max(abs(left), abs(right)), eta)
            result.append({"metric": metric, "pair": pair, "left": left_id, "right": right_id, "absolute_difference": abs(left - right), "tolerance": tolerance, "pass": bool(abs(left - right) <= tolerance)})
    return result


def run(source_dir: Path = DEFAULT_SOURCE_DIR, radial_dir: Path = DEFAULT_RADIAL_DIR, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    source_dir, radial_dir, output_dir = source_dir.resolve(), radial_dir.resolve(), output_dir.resolve()
    if (output_dir / "results.json").exists() or (output_dir / "results.json.tmp").exists() or any(output_dir.glob("spectra_*.npz*")):
        raise FileExistsError(f"refusing existing parent-spatial artifacts: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    ids = identities(failures)
    inherited, radial_ok, radial_receipt = inherited_radial(radial_dir, failures)
    receipt: dict[str, Any] = {"schema": SCHEMA, "identities": ids, "inherited_radial": inherited, "coefficients": COEFFICIENTS.copy(), "temporal_bounds": {"a_dep": 1.0 / (4.0 * (COEFFICIENTS["h_C"] - COEFFICIENTS["e_C"])), "a_vac": 1.0 / (4.0 * (COEFFICIENTS["h_C"] - COEFFICIENTS["e_C"] - math.sqrt(COEFFICIENTS["u_rho"] * COEFFICIENTS["u_C"] / 2.0)))}, "rows": [], "comparisons": [], "numerical_pass": False, "sector_verdict": SECTOR_INCONCLUSIVE, "comparison_verdict": COMPARISON_INCONCLUSIVE, "parent_verdict": PARENT_INCONCLUSIVE, "failures": failures}
    if failures:
        write_json_exclusive(output_dir / "results.json", receipt)
        return receipt
    for identifier in SOURCE_IDS:
        try:
            source = load_source(identifier, source_dir)
            diagnostics = source_diagnostics(source)
            matrices = operators(source, float(diagnostics["omega_C"]))
            spectral, arrays = spectral_measurements(source, matrices)
            if not radial_ok or radial_receipt is None:
                raise ContractError("inherited radial qualification unavailable")
            row = parent_rows(source, diagnostics, radial_receipt, spectral)
            require_finite_payload(row)
            spectra_name = f"spectra_{identifier}.npz"
            spectra_hash = write_spectra(output_dir / spectra_name, arrays)
            row["spectra"] = {"path": spectra_name, "sha256": spectra_hash}
            receipt["rows"].append(row)
            if not bool(diagnostics["source_qualified"]):
                failures.append(f"source qualification failed: {identifier}")
            for name in OPERATORS:
                if max(spectral[name]["eigenpair_residuals"]) >= 1.0e-8 or spectral[name]["orthonormality_error"] >= 1.0e-8:
                    failures.append(f"spectral numerical qualification failed: {identifier} {name}")
        except Exception as exc:
            failures.append(f"source {identifier}: {type(exc).__name__}: {exc}")
    if len(receipt["rows"]) != len(SOURCE_IDS):
        failures.append(f"incomplete source schedule: {len(receipt['rows'])} of {len(SOURCE_IDS)} rows")
    receipt["comparisons"] = comparisons(receipt["rows"], failures)
    sectors = [row["sector_verdict"] for row in receipt["rows"]]
    receipt["sector_verdict"] = SECTOR_CONTRADICT if SECTOR_CONTRADICT in sectors else (SECTOR_SUPPORT if len(sectors) == 4 and all(item == SECTOR_SUPPORT for item in sectors) else SECTOR_INCONCLUSIVE)
    receipt["comparison_verdict"] = COMPARISON_SUPPORT if len(receipt["comparisons"]) == 8 and all(item["pass"] for item in receipt["comparisons"]) else COMPARISON_INCONCLUSIVE
    receipt["parent_verdict"] = PARENT_CONTRADICT if SECTOR_CONTRADICT in sectors else (PARENT_SUPPORT if radial_ok and receipt["sector_verdict"] == SECTOR_SUPPORT and receipt["comparison_verdict"] == COMPARISON_SUPPORT else PARENT_INCONCLUSIVE)
    receipt["failures"] = failures
    receipt["numerical_pass"] = bool(not failures and len(receipt["rows"]) == 4 and len(receipt["comparisons"]) == 8)
    write_json_exclusive(output_dir / "results.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--radial-dir", type=Path, default=DEFAULT_RADIAL_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    receipt = run(args.source_dir, args.radial_dir, args.output_dir)
    print(json.dumps({"numerical_pass": receipt["numerical_pass"], "sector_verdict": receipt["sector_verdict"], "comparison_verdict": receipt["comparison_verdict"], "parent_verdict": receipt["parent_verdict"]}, sort_keys=True))
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
