#!/usr/bin/env python3
"""Independent finite-difference verifier for the §33 interface calculation.

The verifier reconstructs all three one-dimensional operators from the displayed
energy and uses only the frozen schedule in §33.3.  It deliberately contains no
import or call into the primary implementation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
from pathlib import Path
from typing import Any

import numpy as np
import scipy
from scipy.linalg import eigh_tridiagonal

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "computations" / "matter-formation-continuum-report.md"
PARENT = ROOT / "foundations" / "particle-stationary-action-closure.md"
GRIDS = ((12, 512), (12, 1024), (12, 2048), (24, 4096))
A_VALUES = (1.0 / 16.0, 3.0 / 10.0, 1.0 / 2.0)
U_RHO = 4.0
K_CX = 1.0
U_C = 1.0
E_C = 3.0 / 4.0
H_C = 2.9598260763447164
PROTOCOL_HEADING = "### 33.3 Interface calculation: pre-execution criteria\n"
SECTION_HEADING = "## 33. Boundary-localized carrier modes and interface survival\n"
PROTOCOL_SHA256 = "158d575a616c47aaae8a543b007467e81e40c484c4e5b2f8e7391ab19511a391"
DERIVATION_SHA256 = "f7cb325c2b3ac5964c07814cf8dc3d51f9ebdb440de8606bb577b75aab6060f2"
PARENT_SHA256 = "4b00696501134487757f174eb08e4022609ceefe39f32e169d294f99a79f8956"
SCHEMA = "matter-formation-interface-verification-v1"
PRIMARY_SCHEMA = "matter-formation-interface-spectrum-v1"
VERDICT_SUPPORTS = "SUPPORTS—conditional interface trapping and sign-wall instability"
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"


def canonical_text(path: Path) -> str:
    # Canonical source identity changes line endings only.  Section snapshots
    # apply their separately declared rstrip-plus-LF rule at extraction time.
    return path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_text(path).encode("utf-8")).hexdigest()


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_json(path: Path) -> dict[str, Any]:
    def reject(token: str) -> None:
        raise ValueError(f"nonfinite JSON token: {token}")

    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)
    if not isinstance(value, dict):
        raise ValueError("receipt must be a JSON object")
    return value


def extract_sources(note: Path) -> tuple[str, str, str, dict[str, str]]:
    if not note.is_file() or not PARENT.is_file():
        raise FileNotFoundError("working report or PA12/PA16 source is missing")
    report = canonical_text(note)
    if report.count(SECTION_HEADING) != 1 or report.count(PROTOCOL_HEADING) != 1:
        raise ValueError("§33 or protocol heading is missing or duplicated")
    start = report.index(SECTION_HEADING)
    protocol_start = report.index(PROTOCOL_HEADING, start)
    # The derivation is exactly §33 before the protocol subsection.
    derivation = report[start:protocol_start].rstrip() + "\n"
    # The protocol ends at the next heading of level three or higher.
    tail = report[protocol_start + len(PROTOCOL_HEADING):]
    next_heading = re.search(r"(?m)^#{1,3}[^#].*\n", tail)
    protocol = (PROTOCOL_HEADING + (tail[: next_heading.start()] if next_heading else tail)).rstrip() + "\n"
    parent = canonical_text(PARENT)
    pa12_start = parent.index("### 3.2 Complete conditional action")
    pa12_end = parent.index("### 3.3 Source-unit dimensions", pa12_start)
    pa16_start = parent.index("### 4.2 Static Gauss-compatible sector")
    pa16_end = parent.index("\n---", pa16_start)
    snapshots = {
        "pa12": parent[pa12_start:pa12_end].rstrip() + "\n",
        "pa16": parent[pa16_start:pa16_end].rstrip() + "\n",
    }
    return protocol, derivation, parent, snapshots


def finite(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(finite(item) for item in value)
    if isinstance(value, dict):
        return all(finite(item) for item in value.values())
    return True


def check(result: dict[str, Any], name: str, passed: bool, evidence: Any) -> None:
    row = {"name": name, "pass": bool(passed), "evidence": evidence}
    result["checks"].append(row)
    if not passed:
        result["failures"].append(name)


def profile_normalize(values: np.ndarray, dx: float) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    norm = math.sqrt(float(dx * np.sum(values * values)))
    if not math.isfinite(norm) or norm == 0.0:
        raise ValueError("analytic profile has zero or nonfinite norm")
    return values / norm


def key_a(a: float) -> str:
    return f"a{a:.10g}".replace(".", "p")


def residual(diagonal: np.ndarray, off: np.ndarray, vector: np.ndarray, eigenvalue: float) -> float:
    # eigh_tridiagonal vectors are sum-normalized; vectors here are dx-weight normalized.
    hv = diagonal * vector
    if off.size:
        hv[:-1] += off * vector[1:]
        hv[1:] += off * vector[:-1]
    numerator = float(np.max(np.abs(hv - eigenvalue * vector)))
    denominator = max(1.0, abs(float(eigenvalue))) * float(np.max(np.abs(vector)))
    return numerator / denominator


def operator(diagonal_potential: np.ndarray, dx: float, kinetic: float) -> tuple[np.ndarray, np.ndarray]:
    n = diagonal_potential.size
    # kinetic is the coefficient c in -c*d^2/dx^2.  The centred stencil is
    # (2c/dx^2,-c/dx^2,-c/dx^2), with Dirichlet endpoints omitted.
    diagonal = diagonal_potential + 2.0 * kinetic / (dx * dx)
    off = np.full(n - 1, -kinetic / (dx * dx), dtype=np.float64)
    return diagonal, off


def solve(diagonal: np.ndarray, off: np.ndarray, count: int) -> tuple[np.ndarray, np.ndarray]:
    values, vectors = eigh_tridiagonal(diagonal, off, select="i", select_range=(0, count - 1))
    return np.asarray(values, dtype=np.float64), np.asarray(vectors, dtype=np.float64)


def analytic_data() -> tuple[float, float, float, float, float, list[dict[str, Any]], np.ndarray, np.ndarray]:
    delta = math.sqrt(2.0 / U_RHO)
    sigma = 2.0 * math.sqrt(2.0 * U_RHO) / 3.0
    K = K_CX * U_RHO / 4.0
    s = (-1.0 + math.sqrt(1.0 + 4.0 * H_C / K)) / 2.0
    a_wall = 1.0 / (4.0 * (K * s * s - E_C))
    a_vac = 1.0 / (4.0 * (H_C - E_C - math.sqrt(U_RHO * U_C / 2.0)))
    rows: list[dict[str, Any]] = []
    for a in A_VALUES:
        B = E_C + 1.0 / (4.0 * a)
        carrier = [B - K * s * s, B - K * (s - 1.0) ** 2]
        rows.append(
            {
                "a": a,
                "B": B,
                "carrier_eigenvalues": carrier,
                "surface_unstable": carrier[0] < 0.0,
                "bulk_nonnegative": B - H_C + math.sqrt(U_RHO * U_C / 2.0) >= 0.0,
            }
        )
    return s, a_wall, a_vac, delta, sigma, rows, np.array([-U_RHO / 2.0]), np.array([0.0, 3.0 * U_RHO / 2.0])


def analytical_review(phase_value: float) -> dict[str, Any]:
    return {
        "scope": "constant-composition zero-connection subspace of PA12, with the aligned constant adjoint held fixed",
        "base_field": {
            "path": "Psi=(f_w+i eta)v_0",
            "normalization": "v_0^dagger v_0=1",
            "density": "rho=f_w^2+eta^2",
            "composition_potential": "zero because both doublet components share the same complex factor",
        },
        "phase_path": [
            {"step": "variation", "equation": "delta Psi=i eta v_0", "admissible": True},
            {"step": "static_constraint", "equation": "partial_t Psi=partial_t Phi=A_0=0", "gauss_compatible": True},
            {"step": "quadratic_energy", "equation": "delta^2 E_perp=integral eta[-partial_x^2-u_rho sech^2(x/delta)]eta dx", "operator": "H_perp"},
            {"step": "localized_mode", "equation": "eta_0=sech(x/delta), H_perp eta_0=-(u_rho/2)eta_0", "eigenvalue": phase_value},
            {"step": "localization", "equation": "broad compact tangential envelope times eta_0", "conclusion": "retains a negative quadratic sign while becoming surface-localized"},
        ],
        "negative_direction_admissible": True,
        "negative_direction_reason": "The full complex doublet permits an imaginary displacement around the origin; the constant composition remains normalized and the displacement decays at both spatial ends.",
        "static_gauss_compatibility": True,
        "energetic_instability": True,
        "positive_root_vs_signed_real": {
            "positive_root_domain": "The canonical positive-root scalar domain has f>=0 and contains no negative-f sign branch.",
            "signed_real_wall": "The tanh wall is an added real-coordinate boundary condition with f(-infinity)=-1 and f(+infinity)=1.",
            "complex_field": "Restoring the shared complex phase adds the eta direction and makes the sign wall energetically unstable in the stated subspace.",
            "scope": "This conclusion does not promote the signed wall to a canonical positive-root solution.",
        },
        "gauge_dynamical_growth": {
            "inferred": False,
            "reason": "The negative second variation is static energetic information; no unconstrained temporal phase equation or gauge-field evolution is used to infer a growth rate.",
        },
        "conclusion": "Negative direction is admissible and gives a strict static energetic instability, while a gauge dynamical growth rate remains unclaimed.",
    }


def empty_result() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "library_versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "identities": {},
        "scalars": {},
        "analytic_rows": [],
        "phase_eigenvalues": [],
        "radial_eigenvalues": [],
        "grids": [],
        "comparisons": [],
        "artifacts": [],
        "analytical_review": {},
        "primary_comparison": [],
        "checks": [],
        "failures": [],
        "numerical_pass": False,
        "verdict": VERDICT_INCONCLUSIVE,
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
def validate_saved_arrays(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as loaded:
        keys = sorted(loaded.files)
        if not keys:
            raise ValueError(f"empty numerical artifact: {path.name}")
        shapes: dict[str, Any] = {}
        for key in keys:
            array = np.asarray(loaded[key])
            if array.dtype != np.dtype("float64") or not np.all(np.isfinite(array)):
                raise ValueError(f"nonfinite or non-float64 array in {path.name}: {key}")
            shapes[key] = list(array.shape)
    return {"keys": keys, "shapes": shapes}


def compare_primary(primary_path: Path, result: dict[str, Any], scalars: dict[str, float], rows: list[dict[str, Any]], phase: np.ndarray, radial: np.ndarray) -> None:
    primary = strict_json(primary_path)
    if primary.get("schema") != PRIMARY_SCHEMA:
        raise ValueError("primary schema mismatch")
    if not finite(primary):
        raise ValueError("primary contains nonfinite values")
    if primary.get("numerical_pass") is not True:
        raise ValueError("primary numerical_pass is not true")
    if primary.get("verdict") != VERDICT_SUPPORTS:
        raise ValueError("primary qualified verdict mismatch")
    primary_checks = primary.get("checks")
    if not isinstance(primary_checks, list) or not primary_checks or any(not isinstance(item, dict) or item.get("pass") is not True for item in primary_checks):
        raise ValueError("primary checks are missing or contain a failure")
    if primary.get("failures") != []:
        raise ValueError("primary failures are nonempty")
    # Validate every manifested primary artifact before using any primary quantity.
    artifacts = primary.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("primary artifact manifest is missing")
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str) or not isinstance(artifact.get("sha256"), str):
            raise ValueError("primary artifact manifest row is malformed")
        artifact_path = (primary_path.parent / artifact["path"]).resolve()
        if not artifact_path.is_file() or raw_sha256(artifact_path) != artifact["sha256"]:
            raise ValueError(f"primary artifact hash mismatch: {artifact.get('path')}")
    identities = primary.get("identities")
    if not isinstance(identities, dict):
        raise ValueError("primary identities are missing")
    expected = {"protocol": PROTOCOL_SHA256, "derivation": DERIVATION_SHA256, "parent": PARENT_SHA256}
    for name, digest in expected.items():
        item = identities.get(name)
        if not isinstance(item, dict) or item.get("sha256") != digest:
            raise ValueError(f"primary {name} identity mismatch")
    checks: list[dict[str, Any]] = []
    result["primary_comparison"] = checks

    def row(name: str, passed: bool, evidence: Any) -> None:
        checks.append({"name": name, "pass": bool(passed), "evidence": evidence})
        if not passed:
            result["failures"].append("primary:" + name)

    primary_scalars = primary.get("scalars")
    scalar_evidence: dict[str, Any] = {}
    scalar_ok = isinstance(primary_scalars, dict)
    if scalar_ok:
        for name, expected_value in scalars.items():
            actual = primary_scalars.get(name)
            good = isinstance(actual, (int, float)) and math.isfinite(float(actual)) and abs(float(actual) - expected_value) <= 1e-10 * max(1.0, abs(expected_value))
            scalar_evidence[name] = {"primary": actual, "independent": expected_value, "pass": good}
            scalar_ok = scalar_ok and good
    row("scalars", scalar_ok, scalar_evidence)
    primary_rows = primary.get("analytic_rows")
    rows_ok = isinstance(primary_rows, list) and len(primary_rows) == len(rows)
    row_evidence: list[Any] = []
    if rows_ok:
        for expected_row, actual_row in zip(rows, primary_rows):
            good = isinstance(actual_row, dict) and abs(float(actual_row.get("a", float("nan"))) - expected_row["a"]) <= 1e-12
            actual_values = actual_row.get("carrier_eigenvalues") if isinstance(actual_row, dict) else None
            good = good and isinstance(actual_values, list) and len(actual_values) == 2
            diffs = []
            if isinstance(actual_values, list) and len(actual_values) == 2:
                diffs = [abs(float(x) - float(y)) for x, y in zip(actual_values, expected_row["carrier_eigenvalues"])]
                good = good and all(d <= 1e-10 * max(1.0, abs(float(y))) for d, y in zip(diffs, expected_row["carrier_eigenvalues"]))
            good = good and actual_row.get("surface_unstable") is expected_row["surface_unstable"] and actual_row.get("bulk_nonnegative") is expected_row["bulk_nonnegative"]
            row_evidence.append({"a": expected_row["a"], "differences": diffs, "pass": good})
            rows_ok = rows_ok and good
    row("analytic_rows", rows_ok, row_evidence)
    def compare_array(name: str, expected_values: np.ndarray) -> None:
        actual = primary.get(name)
        good = isinstance(actual, list) and len(actual) == len(expected_values)
        diffs: list[float] = []
        if good:
            diffs = [abs(float(x) - float(y)) for x, y in zip(actual, expected_values)]
            good = all(d <= 1e-10 * max(1.0, abs(float(y))) for d, y in zip(diffs, expected_values))
        row(name, good, {"differences": diffs, "expected": expected_values.tolist(), "actual": actual})
    compare_array("phase_eigenvalues", phase)
    compare_array("radial_eigenvalues", radial)


def run(output: Path, note: Path, primary_path: Path | None) -> int:
    output.mkdir(parents=True, exist_ok=False)
    result = empty_result()
    result["identities"]["program"] = {"path": Path(__file__).resolve().relative_to(ROOT).as_posix(), "sha256": canonical_sha256(Path(__file__)), "raw_sha256": raw_sha256(Path(__file__)), "snapshot": canonical_text(Path(__file__))}
    try:
        protocol, derivation, parent, snapshots = extract_sources(note)
        protocol_hash = hashlib.sha256(protocol.encode("utf-8")).hexdigest()
        derivation_hash = hashlib.sha256(derivation.encode("utf-8")).hexdigest()
        parent_hash = hashlib.sha256(parent.encode("utf-8")).hexdigest()
        result["identities"].update({
            "protocol": {"path": note.resolve().relative_to(ROOT).as_posix(), "sha256": protocol_hash, "snapshot": protocol},
            "derivation": {"path": note.resolve().relative_to(ROOT).as_posix(), "sha256": derivation_hash, "snapshot": derivation},
            "parent": {"path": PARENT.resolve().relative_to(ROOT).as_posix(), "sha256": parent_hash, "snapshot": parent, "sections": snapshots},
        })
        check(result, "protocol_hash", protocol_hash == PROTOCOL_SHA256, {"actual": protocol_hash, "expected": PROTOCOL_SHA256})
        check(result, "derivation_hash", derivation_hash == DERIVATION_SHA256, {"actual": derivation_hash, "expected": DERIVATION_SHA256})
        check(result, "parent_hash", parent_hash == PARENT_SHA256, {"actual": parent_hash, "expected": PARENT_SHA256})
        if any(result["failures"]):
            raise ValueError("frozen prerequisite hash mismatch")
        snapshot_records: list[dict[str, Any]] = []
        snapshot_specs = {
            "snapshot_program.py": canonical_text(Path(__file__)),
            "snapshot_protocol.txt": protocol,
            "snapshot_derivation.txt": derivation,
            "snapshot_parent.md": parent,
        }
        for filename, text in snapshot_specs.items():
            snapshot_path = output / filename
            snapshot_path.write_bytes(text.encode("utf-8"))
            snapshot_records.append({"path": filename, "sha256": raw_sha256(snapshot_path), "kind": "source_snapshot"})

        s, a_wall, a_vac, delta, sigma, analytic_rows, phase_analytic, radial_analytic = analytic_data()
        result["scalars"] = {"s": s, "a_wall": a_wall, "a_vac": a_vac, "delta": delta, "sigma": sigma}
        result["analytic_rows"] = analytic_rows
        result["phase_eigenvalues"] = phase_analytic.tolist()
        result["radial_eigenvalues"] = radial_analytic.tolist()
        result["analytical_review"] = analytical_review(float(phase_analytic[0]))
        all_comparisons: list[dict[str, Any]] = []
        artifact_records: list[dict[str, Any]] = list(snapshot_records)
        grid_records: list[dict[str, Any]] = []
        result["artifacts"] = artifact_records
        result["grids"] = grid_records
        result["comparisons"] = all_comparisons
        for X, N in GRIDS:
            dx = 2.0 * X / N
            x = np.linspace(-X + dx, X - dx, N - 1, dtype=np.float64)
            f = np.tanh(x / delta)
            sech = 1.0 / np.cosh(x / delta)
            carrier_potentials: dict[str, np.ndarray] = {}
            carrier_values: dict[str, np.ndarray] = {}
            carrier_vectors: dict[str, np.ndarray] = {}
            carrier_profiles: dict[str, np.ndarray] = {}
            carrier_residuals: dict[str, list[float]] = {}
            carrier_overlaps: dict[str, list[float]] = {}
            for analytic_row in analytic_rows:
                a = float(analytic_row["a"])
                ak = key_a(a)
                B = float(analytic_row["B"])
                potential = B - H_C * sech * sech
                diagonal, off = operator(potential, dx, K_CX / 2.0)
                values, vectors = solve(diagonal, off, 2)
                vectors = vectors / math.sqrt(dx)
                profiles = np.vstack((profile_normalize(sech**s, dx), profile_normalize(f * sech ** (s - 1.0), dx))).T
                carrier_potentials[ak] = potential
                carrier_values[ak] = values
                carrier_vectors[ak] = vectors
                carrier_profiles[ak] = profiles
                carrier_residuals[ak] = [residual(diagonal, off, vectors[:, j], float(values[j])) for j in range(2)]
                carrier_overlaps[ak] = [abs(float(dx * np.dot(vectors[:, j], profiles[:, j]))) for j in range(2)]
                for mode in range(2):
                    all_comparisons.append({"grid": {"X": X, "N": N}, "kind": "carrier", "a": a, "mode": mode, "numerical": float(values[mode]), "analytic": float(analytic_row["carrier_eigenvalues"][mode]), "absolute_error": abs(float(values[mode] - analytic_row["carrier_eigenvalues"][mode])), "residual": carrier_residuals[ak][mode], "overlap": carrier_overlaps[ak][mode]})
            phase_potential = -U_RHO * sech * sech
            phase_diagonal, phase_off = operator(phase_potential, dx, 1.0)
            phase_values, phase_vectors = solve(phase_diagonal, phase_off, 1)
            phase_vectors = phase_vectors / math.sqrt(dx)
            phase_profile = profile_normalize(sech, dx)
            phase_residual = residual(phase_diagonal, phase_off, phase_vectors[:, 0], float(phase_values[0]))
            phase_overlap = abs(float(dx * np.dot(phase_vectors[:, 0], phase_profile)))
            radial_potential = U_RHO * (3.0 * f * f - 1.0)
            radial_diagonal, radial_off = operator(radial_potential, dx, 1.0)
            radial_values, radial_vectors = solve(radial_diagonal, radial_off, 2)
            radial_vectors = radial_vectors / math.sqrt(dx)
            radial_profiles = np.vstack((profile_normalize(sech * sech, dx), profile_normalize(f * sech, dx))).T
            radial_residuals = [residual(radial_diagonal, radial_off, radial_vectors[:, j], float(radial_values[j])) for j in range(2)]
            radial_overlaps = [abs(float(dx * np.dot(radial_vectors[:, j], radial_profiles[:, j]))) for j in range(2)]
            all_comparisons.append({"grid": {"X": X, "N": N}, "kind": "phase", "mode": 0, "numerical": float(phase_values[0]), "analytic": float(phase_analytic[0]), "absolute_error": abs(float(phase_values[0] - phase_analytic[0])), "residual": phase_residual, "overlap": phase_overlap})
            for mode in range(2):
                all_comparisons.append({"grid": {"X": X, "N": N}, "kind": "radial", "mode": mode, "numerical": float(radial_values[mode]), "analytic": float(radial_analytic[mode]), "absolute_error": abs(float(radial_values[mode] - radial_analytic[mode])), "residual": radial_residuals[mode], "overlap": radial_overlaps[mode]})
            arrays: dict[str, np.ndarray] = {"x": x, "phase_potential": phase_potential, "phase_eigenvalues": phase_values, "phase_eigenvectors": phase_vectors, "phase_analytic_profile": phase_profile, "radial_potential": radial_potential, "radial_eigenvalues": radial_values, "radial_eigenvectors": radial_vectors, "radial_analytic_profiles": radial_profiles}
            for ak in carrier_potentials:
                arrays.update({f"carrier_potential_{ak}": carrier_potentials[ak], f"carrier_eigenvalues_{ak}": carrier_values[ak], f"carrier_eigenvectors_{ak}": carrier_vectors[ak], f"carrier_analytic_profiles_{ak}": carrier_profiles[ak]})
            artifact_name = f"grid_X{X}_N{N}.npz"
            artifact_path = output / artifact_name
            np.savez_compressed(artifact_path, **arrays)
            array_manifest = validate_saved_arrays(artifact_path)
            artifact_records.append({"path": artifact_name, "sha256": raw_sha256(artifact_path), "X": X, "N": N, "arrays": array_manifest})
            grid_records.append({"X": X, "N": N, "dx": dx, "nodes": N - 1, "artifact": artifact_name, "carrier_eigenvalues": {k: v.tolist() for k, v in carrier_values.items()}, "phase_eigenvalues": phase_values.tolist(), "radial_eigenvalues": radial_values.tolist(), "residuals": {"carrier": carrier_residuals, "phase": [phase_residual], "radial": radial_residuals}, "overlaps": {"carrier": carrier_overlaps, "phase": [phase_overlap], "radial": radial_overlaps}, "spectral_count": 9})
        result["grids"] = grid_records
        result["comparisons"] = all_comparisons
        result["artifacts"] = artifact_records
        check(result, "exact_grid_schedule", len(grid_records) == 4 and [(r["X"], r["N"]) for r in grid_records] == list(GRIDS), [(r["X"], r["N"]) for r in grid_records])
        check(result, "all_nine_spectral_comparisons_per_grid", len(all_comparisons) == 36 and all(sum(1 for row in all_comparisons if row["grid"] == {"X": X, "N": N}) == 9 for X, N in GRIDS), {"total": len(all_comparisons), "per_grid": [sum(1 for row in all_comparisons if row["grid"] == {"X": X, "N": N}) for X, N in GRIDS]})
        finest = [row for row in all_comparisons if row["grid"] == {"X": 12, "N": 2048}]
        last = [row for row in all_comparisons if row["grid"] == {"X": 24, "N": 4096}]
        check(result, "finest_absolute_accuracy", all(row["absolute_error"] < 4e-4 for row in finest), [{"kind": r["kind"], "mode": r["mode"], "error": r["absolute_error"]} for r in finest])
        check(result, "finest_domain_convergence", len(finest) == 9 and len(last) == 9 and all(abs(a["numerical"] - b["numerical"]) < 1e-4 for a, b in zip(finest, last)), [{"kind": a["kind"], "mode": a["mode"], "difference": abs(a["numerical"] - b["numerical"]) } for a, b in zip(finest, last)])
        radial_finest = [row for row in finest if row["kind"] == "radial"]
        radial_last = [row for row in last if row["kind"] == "radial"]
        check(result, "near_zero_radial_absolute_comparisons", len(radial_finest) == 2 and all(row["absolute_error"] < 4e-4 for row in radial_finest) and len(radial_last) == 2 and all(abs(a["numerical"] - b["numerical"]) < 1e-4 for a, b in zip(radial_finest, radial_last)), {"criterion": "absolute errors and absolute domain differences; no division by eigenvalue", "finest_errors": [row["absolute_error"] for row in radial_finest], "domain_differences": [abs(a["numerical"] - b["numerical"]) for a, b in zip(radial_finest, radial_last)]})
        mid = [row for row in all_comparisons if row["grid"] == {"X": 12, "N": 1024}]
        coarse = [row for row in all_comparisons if row["grid"] == {"X": 12, "N": 512}]
        ratios = [abs(coarse[i]["numerical"] - mid[i]["numerical"]) / max(abs(mid[i]["numerical"] - finest[i]["numerical"]), 1e-300) for i in range(9)]
        check(result, "second_order_convergence_ratio", all(3.5 <= ratio <= 4.5 for ratio in ratios), ratios)
        check(result, "finest_equation_residuals", all(row["residual"] < 1e-8 for row in finest), {"formula": "||H v-lambda v||_infinity / (max(1,abs(lambda))*max(abs(v)))", "maximum": max(row["residual"] for row in finest)})
        check(result, "analytic_profile_overlaps", all(row["overlap"] > 0.999 for row in finest), {"minimum": min(row["overlap"] for row in finest), "inner_product": "dx * sum(v_numeric * v_analytic)"})
        check(result, "threshold_ordering", K_CX * U_RHO / 4.0 * s * s > E_C and a_wall < a_vac, {"a_wall": a_wall, "a_vac": a_vac, "ordering": "a_wall<a_vac"})
        check(result, "carrier_growth_signs", [r["surface_unstable"] for r in analytic_rows] == [False, True, True], [r["surface_unstable"] for r in analytic_rows])
        check(result, "bulk_potential_signs", [r["bulk_nonnegative"] for r in analytic_rows] == [True, True, False], [r["bulk_nonnegative"] for r in analytic_rows])
        if primary_path is not None:
            compare_primary(primary_path.resolve(), result, result["scalars"], analytic_rows, phase_analytic, radial_analytic)
        check(result, "finite_json_payload", finite(result), {"allow_nan": False, "saved_arrays_checked": True})
        result["numerical_pass"] = not result["failures"]
        result["verdict"] = VERDICT_SUPPORTS if result["numerical_pass"] else VERDICT_INCONCLUSIVE
    except Exception as error:
        result["failures"].append(f"{type(error).__name__}: {error}")
        result["numerical_pass"] = False
        result["verdict"] = VERDICT_INCONCLUSIVE
        # Prerequisite failures must not leave scientific values behind.
        if not result["grids"]:
            result["scalars"] = {}
            result["analytic_rows"] = []
            result["phase_eigenvalues"] = []
            result["radial_eigenvalues"] = []
            result["comparisons"] = []
            result["artifacts"] = []
            result["analytical_review"] = {}
    finally:
        write_json(output / "verification.json", result)
    print(json.dumps({"schema": SCHEMA, "numerical_pass": result["numerical_pass"], "verdict": result["verdict"], "failures": result["failures"]}, ensure_ascii=False, allow_nan=False))
    return 0 if result["numerical_pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--note", type=Path, default=REPORT)
    parser.add_argument("--primary", type=Path, default=None, help="optional primary results.json for post-reconstruction comparison")
    args = parser.parse_args()
    return run(args.output_dir.resolve(), args.note.resolve(), args.primary.resolve() if args.primary else None)


if __name__ == "__main__":
    raise SystemExit(main())
