#!/usr/bin/env python3
"""Independent verifier for the frozen §34 charged coexistence interface.

The independent solve uses only the displayed coexistence potential and the
analytic initial profile.  It never imports the primary collocation program.
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
from scipy.linalg import eig_banded, eigh_tridiagonal
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import spsolve

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "computations" / "matter-formation-continuum-report.md"
PARENT = ROOT / "foundations" / "particle-stationary-action-closure.md"

U_RHO = 4.0
U_C = 1.0
K_CX = 1.0
E_C = 3.0 / 4.0
H_C = 2.9598260763447164
A = 1.0 / 16.0
GRIDS = ((6.0, 1024), (9.0, 1536), (12.0, 2048), (12.0, 4096))

SECTION_HEADING = "## 34. Charged phase coexistence and a finite-interface balance\n"
DERIVATION_HEADING = "### 34.1 Carrier loading and mediator nodes\n"
PROTOCOL_HEADING = "### 34.4 Charged-interface calculation: pre-execution criteria\n"
PROTOCOL_SHA256 = "710b17d73ef225acde87dad2b45e16eb40aebe2fe2c7d223cd94430c49bf8300"
DERIVATION_SHA256 = "c235c44d800281b5c08a706179d64349d6055001b0bf27683e909a10307666a8"
PARENT_SHA256 = "4b00696501134487757f174eb08e4022609ceefe39f32e169d294f99a79f8956"
SCHEMA = "matter-formation-charged-interface-verification-v1"
PRIMARY_SCHEMA = "matter-formation-charged-interface-v1"
VERDICT_SUPPORTS = "SUPPORTS-conditional charged coexistence interface"
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def canonical_text(path: Path) -> str:
    return canonical_bytes(path).decode("utf-8")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def finite(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if value is None:
        return True
    if isinstance(value, (int, float, np.integer, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(finite(v) for v in value)
    if isinstance(value, dict):
        return all(finite(v) for v in value.values())
    return True


def strict_json(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise ValueError(f"duplicate JSON key: {key}")
            out[key] = value
        return out

    def reject(token: str) -> None:
        raise ValueError(f"nonfinite JSON token: {token}")

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=reject)
    if not isinstance(value, dict) or not finite(value):
        raise ValueError("receipt must be a finite JSON object")
    return value


def extract_sources(note: Path) -> tuple[str, str, str]:
    if not note.is_file() or not PARENT.is_file():
        raise FileNotFoundError("report or scalar-parent source is missing")
    report = canonical_text(note)
    if report.count(SECTION_HEADING) != 1 or report.count(DERIVATION_HEADING) != 1 or report.count(PROTOCOL_HEADING) != 1:
        raise ValueError("§34 headings are missing or duplicated")
    section_start = report.index(SECTION_HEADING)
    derivation_start = report.index(DERIVATION_HEADING, section_start)
    protocol_start = report.index(PROTOCOL_HEADING, derivation_start)
    derivation = report[derivation_start:protocol_start].rstrip() + "\n"
    tail = report[protocol_start + len(PROTOCOL_HEADING):]
    next_heading = re.search(r"(?m)^#{1,3}[^#].*\n", tail)
    protocol = (PROTOCOL_HEADING + (tail[: next_heading.start()] if next_heading else tail)).rstrip() + "\n"
    parent = canonical_text(PARENT)
    return protocol, derivation, parent


def source_identity(path: Path) -> dict[str, str]:
    return {"path": repo_path(path), "canonical_sha256": canonical_sha256(path), "raw_sha256": raw_sha256(path)}


def check(result: dict[str, Any], name: str, passed: bool, evidence: Any) -> None:
    result["checks"].append({"name": name, "pass": bool(passed), "evidence": evidence})
    if not passed:
        result["failures"].append(name)


def constants() -> dict[str, float]:
    B = E_C + 1.0 / (4.0 * A)
    S = math.sqrt(U_RHO * U_C / 2.0)
    D = H_C - S
    n0 = math.sqrt(U_RHO / (2.0 * U_C))
    omega0 = math.sqrt((B - H_C + S) / A)
    q0 = 2.0 * A * omega0 * n0
    alpha = min(1.0, math.sqrt(D * K_CX / (2.0 * U_C)))
    sigma_lower = math.sqrt(2.0 * U_RHO) * alpha / 3.0
    m = K_CX * n0
    quotient = 0.5 if abs(m - 1.0) < 1.0e-14 else (m ** 1.5 - 1.0) / (3.0 * (m - 1.0))
    sigma_upper = math.sqrt(2.0 * D * n0) * quotient
    return {"B": B, "S": S, "D": D, "n0": n0, "Omega0": omega0, "q0": q0, "alpha": alpha, "sigma_lower": sigma_lower, "sigma_upper": sigma_upper}


def profile(x: np.ndarray, n0: float) -> tuple[np.ndarray, np.ndarray]:
    t = np.tanh(x)
    f = np.sqrt(np.maximum(0.0, 0.5 * (1.0 + t)))
    c = np.sqrt(np.maximum(0.0, 0.5 * n0 * (1.0 - t)))
    return f, c


def potential(f: np.ndarray, c: np.ndarray, values: dict[str, float]) -> np.ndarray:
    term = math.sqrt(U_RHO) * 0.5 * (1.0 - f * f) - math.sqrt(U_C / 2.0) * c * c
    return term * term + values["D"] * f * f * c * c


def potential_derivatives(f: np.ndarray, c: np.ndarray, values: dict[str, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    uf = U_RHO * (f * f - 1.0) * f + 2.0 * H_C * f * c * c
    uc = 2.0 * (H_C * f * f - values["S"] + U_C * c * c) * c
    uff = U_RHO * (3.0 * f * f - 1.0) + 2.0 * H_C * c * c
    ucc = 2.0 * (H_C * f * f - values["S"]) + 6.0 * U_C * c * c
    ufc = 4.0 * H_C * f * c
    return uf, uc, uff, ucc, ufc


def energy(x: np.ndarray, f: np.ndarray, c: np.ndarray, values: dict[str, float]) -> float:
    h = float(x[1] - x[0])
    edge = 0.5 * ((np.diff(f) / h) ** 2 + K_CX * (np.diff(c) / h) ** 2)
    u = potential(f, c, values)
    return float(h * np.sum(edge) + h * (0.5 * u[0] + np.sum(u[1:-1]) + 0.5 * u[-1]))


def energy_change(x: np.ndarray, f: np.ndarray, c: np.ndarray, trial_f: np.ndarray, trial_c: np.ndarray, values: dict[str, float]) -> float:
    """Evaluate the same energy difference without subtracting two totals."""
    h = float(x[1] - x[0])
    df, dc = trial_f - f, trial_c - c
    edge_f, edge_c = np.diff(f) / h, np.diff(c) / h
    delta_f, delta_c = np.diff(df) / h, np.diff(dc) / h
    delta_edge = 0.5 * (delta_f * (2.0 * edge_f + delta_f) + K_CX * delta_c * (2.0 * edge_c + delta_c))
    p = math.sqrt(U_RHO) * 0.5
    q = math.sqrt(U_C / 2.0)
    square = p * (1.0 - f * f) - q * c * c
    delta_square = -p * df * (2.0 * f + df) - q * dc * (2.0 * c + dc)
    product = f * c
    delta_product = f * dc + c * df + df * dc
    delta_u = delta_square * (2.0 * square + delta_square) + values["D"] * delta_product * (2.0 * product + delta_product)
    return float(h * (np.sum(delta_edge) + 0.5 * delta_u[0] + np.sum(delta_u[1:-1]) + 0.5 * delta_u[-1]))


def full_gradient(x: np.ndarray, f: np.ndarray, c: np.ndarray, values: dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
    h = float(x[1] - x[0])
    uf, uc, _, _, _ = potential_derivatives(f, c, values)
    gf = (2.0 * f[1:-1] - f[:-2] - f[2:]) / h + h * uf[1:-1]
    gc = K_CX * (2.0 * c[1:-1] - c[:-2] - c[2:]) / h + h * uc[1:-1]
    return gf, gc


def free_layout(n_intervals: int) -> list[tuple[str, int]]:
    mid = n_intervals // 2
    return [("f", i) for i in range(1, n_intervals) if i != mid] + [("c", i) for i in range(1, n_intervals)]


def free_gradient(x: np.ndarray, f: np.ndarray, c: np.ndarray, values: dict[str, float], layout: list[tuple[str, int]]) -> np.ndarray:
    gf, gc = full_gradient(x, f, c, values)
    out = []
    for field, i in layout:
        out.append((gf if field == "f" else gc)[i - 1] / (x[1] - x[0]))
    return np.asarray(out, dtype=np.float64)


def free_hessian(x: np.ndarray, f: np.ndarray, c: np.ndarray, values: dict[str, float], layout: list[tuple[str, int]]) -> csc_matrix:
    h = float(x[1] - x[0])
    _, _, uff, ucc, ufc = potential_derivatives(f, c, values)
    pos = {item: j for j, item in enumerate(layout)}
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    for j, (field, i) in enumerate(layout):
        diag = (2.0 / (h * h) if field == "f" else 2.0 * K_CX / (h * h)) + (uff[i] if field == "f" else ucc[i])
        rows.append(j); cols.append(j); data.append(float(diag))
        for neighbor in (i - 1, i + 1):
            key = (field, neighbor)
            if key in pos:
                rows.append(j); cols.append(pos[key]); data.append(float(-1.0 / (h * h) if field == "f" else -K_CX / (h * h)))
        other = ("c" if field == "f" else "f", i)
        if other in pos:
            rows.append(j); cols.append(pos[other]); data.append(float(ufc[i]))
    return csc_matrix((data, (rows, cols)), shape=(len(layout), len(layout)))


def solve_row(L: float, intervals: int, values: dict[str, float]) -> dict[str, Any]:
    x = np.linspace(-L, L, intervals + 1, dtype=np.float64)
    h = float(x[1] - x[0])
    f, c = profile(x, values["n0"])
    f[0], f[-1] = 0.0, 1.0
    c[0], c[-1] = values["n0"] ** 0.5, 0.0
    midpoint = intervals // 2
    f[midpoint] = 1.0 / math.sqrt(2.0)
    layout = free_layout(intervals)
    attempts: list[dict[str, Any]] = []
    converged = False
    stop_reason = "maximum_newton_steps"
    for iteration in range(100):
        current_energy = energy(x, f, c, values)
        g = free_gradient(x, f, c, values, layout)
        residual = float(np.max(np.abs(g))) if g.size else 0.0
        attempt: dict[str, Any] = {"iteration": iteration, "energy": current_energy, "max_free_euler_residual": residual, "accepted": False, "halvings": None}
        if not math.isfinite(current_energy) or not np.all(np.isfinite(g)):
            attempt["failure"] = "nonfinite_energy_or_gradient"
            attempts.append(attempt)
            stop_reason = "nonfinite"
            break
        if residual < 1.0e-8:
            converged = True
            stop_reason = "free_euler_tolerance"
            attempt["accepted"] = True
            attempts.append(attempt)
            break
        H = free_hessian(x, f, c, values, layout)
        try:
            delta = np.asarray(spsolve(H, -g), dtype=np.float64)
        except Exception as exc:
            attempt["failure"] = f"linear_solve:{type(exc).__name__}"
            attempts.append(attempt)
            stop_reason = "linear_solve_failure"
            break
        if not np.all(np.isfinite(delta)):
            attempt["failure"] = "nonfinite_newton_step"
            attempts.append(attempt)
            stop_reason = "nonfinite_step"
            break
        accepted = False
        for halvings in range(41):
            trial_f = f.copy()
            trial_c = c.copy()
            scale = 0.5 ** halvings
            for value, (field, i) in zip(scale * delta, layout):
                if field == "f":
                    trial_f[i] += value
                else:
                    trial_c[i] += value
            trial_f[midpoint] = 1.0 / math.sqrt(2.0)
            trial_energy = energy(x, trial_f, trial_c, values)
            delta_energy = energy_change(x, f, c, trial_f, trial_c, values)
            if math.isfinite(trial_energy) and math.isfinite(delta_energy) and delta_energy < 0.0:
                f, c = trial_f, trial_c
                accepted = True
                attempt.update({"accepted": True, "halvings": halvings, "step_scale": scale, "trial_energy": trial_energy, "energy_change": delta_energy})
                break
        attempts.append(attempt)
        if not accepted:
            stop_reason = "line_search_failure"
            break
    gf, gc = full_gradient(x, f, c, values)
    midpoint_euler = float(abs(gf[midpoint - 1] / h))
    max_free = max(float(np.max(np.abs(gf[:midpoint - 1]))), float(np.max(np.abs(gf[midpoint:]))), float(np.max(np.abs(gc)))) / h
    amplitudes = {
        "f_min": float(np.min(f)), "f_max": float(np.max(f)),
        "c_min": float(np.min(c)), "c_max": float(np.max(c)),
        "f_pass": bool(np.min(f) >= -1.0e-9 and np.max(f) <= 1.0 + 1.0e-9),
        "c_pass": bool(np.min(c) >= -1.0e-9 and np.max(c) <= values["n0"] ** 0.5 + 1.0e-9),
    }
    row_pass = bool(converged and np.all(np.isfinite(f)) and np.all(np.isfinite(c)) and amplitudes["f_pass"] and amplitudes["c_pass"])
    return {"x": x, "f": f, "c": c, "energy": energy(x, f, c, values), "max_free_euler_residual": max_free, "midpoint_euler_residual": midpoint_euler, "converged": converged, "stop_reason": stop_reason, "attempts": attempts, "amplitudes": amplitudes, "pass": row_pass}


def amplitude_banded(f: np.ndarray, c: np.ndarray, h: float, values: dict[str, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    fi, ci = f[1:-1], c[1:-1]
    _, _, uff, ucc, ufc = potential_derivatives(fi, ci, values)
    n = fi.size
    size = 2 * n
    ab = np.zeros((3, size), dtype=np.float64)
    for i in range(n):
        j = 2 * i
        ab[2, j] = 2.0 / (h * h) + uff[i]
        ab[2, j + 1] = 2.0 * K_CX / (h * h) + ucc[i]
        ab[1, j + 1] = ufc[i]
        if i < n - 1:
            ab[0, j + 2] = -1.0 / (h * h)
            ab[0, j + 3] = -K_CX / (h * h)
    values_out, vectors = eig_banded(ab, lower=False, eigvals_only=False, select="i", select_range=(0, 2), check_finite=True)
    return np.asarray(values_out), np.asarray(vectors), ab


def phase_tridiagonal(f: np.ndarray, c: np.ndarray, h: float, values: dict[str, float], which: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    fi, ci = f[1:-1], c[1:-1]
    if which == "f":
        potential_values = U_RHO * (fi * fi - 1.0) + 2.0 * H_C * ci * ci
        kinetic = 1.0
    else:
        potential_values = 2.0 * (H_C * fi * fi - values["S"] + U_C * ci * ci)
        kinetic = K_CX
    diagonal = potential_values + 2.0 * kinetic / (h * h)
    off = np.full(fi.size - 1, -kinetic / (h * h), dtype=np.float64)
    eigvals, eigvecs = eigh_tridiagonal(diagonal, off, select="i", select_range=(0, 0), check_finite=True)
    return np.asarray(eigvals), np.asarray(eigvecs), diagonal, off


def normalized_banded_residual(bands: np.ndarray, vector: np.ndarray, eigenvalue: float) -> float:
    bandwidth = bands.shape[0] - 1
    applied = bands[bandwidth] * vector
    for offset in range(1, bandwidth + 1):
        diagonal = bands[bandwidth - offset, offset:]
        applied[:-offset] += diagonal * vector[offset:]
        applied[offset:] += diagonal * vector[:-offset]
    residual = applied - eigenvalue * vector
    return float(np.max(np.abs(residual)) / (max(1.0, abs(float(eigenvalue))) * max(1.0e-300, float(np.max(np.abs(vector))))))


def spectra(row: dict[str, Any], values: dict[str, float]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    f, c, x = row["f"], row["c"], row["x"]
    h = float(x[1] - x[0])
    amps, amp_vectors, ab = amplitude_banded(f, c, h, values)
    amp_vectors = amp_vectors / math.sqrt(h)
    amp_residuals = [normalized_banded_residual(ab, amp_vectors[:, j], float(amps[j])) for j in range(3)]
    phase_payload: dict[str, Any] = {}
    arrays: dict[str, np.ndarray] = {"amplitude_eigenvalues": amps, "amplitude_eigenvectors": amp_vectors}
    for label in ("f", "c"):
        eigvals, eigvecs, diagonal, off = phase_tridiagonal(f, c, h, values, label)
        vector = eigvecs[:, 0] / math.sqrt(h)
        bands = np.zeros((2, diagonal.size), dtype=np.float64)
        bands[1] = diagonal
        bands[0, 1:] = off
        phase_payload[label] = {"eigenvalue": float(eigvals[0]), "residual": normalized_banded_residual(bands, vector, float(eigvals[0]))}
        arrays[f"phase_{label}_eigenvalues"] = eigvals
        arrays[f"phase_{label}_eigenvectors"] = vector[:, None]
    payload = {"amplitude_eigenvalues": amps.tolist(), "amplitude_residuals": amp_residuals, "phase": phase_payload, "bandwidth": 2, "phase_solver": "eigh_tridiagonal select=i lowest", "amplitude_solver": "eig_banded select=i lowest three"}
    return payload, arrays


def analytical_review(values: dict[str, float]) -> dict[str, Any]:
    factorization = {"equation": "U0=[sqrt(u_rho)/2(1-f^2)-sqrt(u_C/2)c^2]^2+D f^2 c^2", "nonnegative": bool(values["D"] > 0.0), "vacua": [[1.0, 0.0], [0.0, values["n0"] ** 0.5]], "grand_potential_at_vacua": [0.0, 0.0]}
    nodal = {"argument": "|f| is a principal Dirichlet zero mode on a regular nodal domain; strict connected enlargement lowers its principal eigenvalue below zero", "regularity_assumption": "bounded regular nodal domain and locally bounded potential", "strict_enlargement": True, "scope": "conditional on existence of the stationary profile"}
    charge = {"temporal_square": "a|dot z+i Omega z|^2 >= 0", "Omega0_positive_finite": bool(math.isfinite(values["Omega0"]) and values["Omega0"] > 0.0), "q0_positive_finite": bool(math.isfinite(values["q0"]) and values["q0"] > 0.0), "static_gauss": True, "reason": "rotating carrier is gauge singlet and static mediator/adjoint momenta, temporal connection and electric curvature vanish"}
    positive_phase = {"identities": ["integral eta_f H_f eta_f = integral f^2 |grad(eta_f/f)|^2 >= 0", "integral eta_c H_c eta_c = k_Cx integral c^2 |grad(eta_c/c)|^2 >= 0"], "admissible_scope": "compactly supported phase perturbations where f and c are strictly positive", "pass": True, "remaining_scope": "Coupled-amplitude and finite-charge stability require separate calculations."}
    surface = {"D_k_less_than_2uC": bool(values["D"] * K_CX < 2.0 * U_C), "lower_bound": values["sigma_lower"], "upper_bound": values["sigma_upper"], "pass": bool(values["sigma_lower"] <= values["sigma_upper"] + 1.0e-14)}
    thin = {"scope": "The planar thin-interface expansion requires R much larger than the charged-interface width. A finite droplet, formation trajectory, spin, statistics, charge unit and completed matter mechanism require separate evidence.", "pass": True}
    checks = [factorization["nonnegative"], nodal["strict_enlargement"], charge["Omega0_positive_finite"] and charge["q0_positive_finite"] and charge["static_gauss"], positive_phase["pass"], surface["D_k_less_than_2uC"] and surface["pass"], thin["pass"]]
    return {"factorization": factorization, "nodal_domain": nodal, "charge_gauss": charge, "positive_phase_ground_state": positive_phase, "surface_bounds": surface, "thin_interface_scope": thin, "pass": bool(all(checks))}


def empty_result() -> dict[str, Any]:
    return {"schema": SCHEMA, "library_versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}, "identities": {}, "artifacts": [], "scalars": {}, "rows": [], "checks": [], "failures": [], "numerical_pass": False, "verdict": VERDICT_INCONCLUSIVE, "complete_physical_matter_formation": False, "analytical_review": {}, "spectral": {}, "primary_comparison": []}


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def save_array(path: Path, arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    np.savez_compressed(path, **arrays)
    with np.load(path, allow_pickle=False) as loaded:
        if sorted(loaded.files) != ["c", "f", "x"]:
            raise ValueError(f"unexpected independent field keys in {path.name}")
        shapes = {}
        for key in loaded.files:
            value = np.asarray(loaded[key])
            if value.dtype != np.dtype("float64") or value.ndim != 1 or not np.all(np.isfinite(value)):
                raise ValueError(f"nonfinite or malformed field array: {key}")
            shapes[key] = list(value.shape)
        if loaded["x"].size < 2 or np.any(np.diff(loaded["x"]) <= 0.0) or any(loaded[key].shape != loaded["x"].shape for key in ("f", "c")):
            raise ValueError("independent field coordinates or shapes are malformed")
    return {"path": path.name, "raw_sha256": raw_sha256(path), "bytes": path.stat().st_size, "arrays": shapes}


def safe_primary_path(base: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("primary artifact path is not relative")
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise ValueError("primary artifact escapes receipt directory") from exc
    return candidate


def compare_primary(path: Path, result: dict[str, Any], values: dict[str, float], independent_rows: list[dict[str, Any]]) -> None:
    primary = strict_json(path)
    if primary.get("schema") != PRIMARY_SCHEMA or primary.get("numerical_pass") is not True or primary.get("verdict") != VERDICT_SUPPORTS or primary.get("failures") != []:
        raise ValueError("primary is missing qualified charged-interface status")
    identities = primary.get("identities")
    if not isinstance(identities, dict):
        raise ValueError("primary identities are missing")
    program_identity = identities.get("program")
    if not isinstance(program_identity, dict) or not isinstance(program_identity.get("path"), str) or not isinstance(program_identity.get("canonical_sha256"), str):
        raise ValueError("primary program identity is missing")
    expected_identities = {"protocol": PROTOCOL_SHA256, "derivation": DERIVATION_SHA256, "parent": PARENT_SHA256}
    for name, expected in expected_identities.items():
        item = identities.get(name)
        actual = item.get("canonical_sha256") if isinstance(item, dict) else None
        if actual != expected:
            raise ValueError(f"primary {name} identity mismatch")
    artifacts = primary.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("primary artifact manifest is missing or not a list")
    artifact_items = [(str(i), item) for i, item in enumerate(artifacts)]
    manifest_paths: list[str] = []
    for _, item in artifact_items:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("raw_sha256"), str):
            raise ValueError("malformed primary artifact entry")
        artifact_path = safe_primary_path(path.parent, item["path"])
        if not artifact_path.is_file() or raw_sha256(artifact_path) != item["raw_sha256"]:
            raise ValueError(f"primary artifact hash mismatch: {item.get('path')}")
        manifest_paths.append(item["path"])
    if len(manifest_paths) != len(set(manifest_paths)):
        raise ValueError("duplicate primary artifact paths")
    required_snapshots = {"protocol.txt", "derivation.txt", "report_source.md", "parent_source.md", "program_source.py"}
    if not required_snapshots.issubset(set(manifest_paths)):
        raise ValueError("primary source snapshots are missing from artifact manifest")
    snapshot_expected = {"protocol.txt": PROTOCOL_SHA256, "derivation.txt": DERIVATION_SHA256, "parent_source.md": PARENT_SHA256, "program_source.py": program_identity["canonical_sha256"]}
    for snapshot_name, expected_hash in snapshot_expected.items():
        snapshot_path = safe_primary_path(path.parent, snapshot_name)
        if canonical_sha256(snapshot_path) != expected_hash:
            raise ValueError(f"primary source snapshot content mismatch: {snapshot_name}")
    report_protocol, report_derivation, _ = extract_sources(safe_primary_path(path.parent, "report_source.md"))
    if hashlib.sha256(report_protocol.encode("utf-8")).hexdigest() != PROTOCOL_SHA256 or hashlib.sha256(report_derivation.encode("utf-8")).hexdigest() != DERIVATION_SHA256:
        raise ValueError("primary report snapshot frozen sections differ")
    rows = primary.get("rows")
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError("primary rows are missing or incomplete")
    for expected, row in zip(((6.0, 2048), (9.0, 3072), (12.0, 4096)), rows):
        if not isinstance(row, dict) or float(row.get("L", float("nan"))) != expected[0] or int(row.get("intervals", -1)) != expected[1]:
            raise ValueError("primary row schedule mismatch")
    for index, row in enumerate(rows):
        if row.get("bvp_success") is not True or row.get("finite_arrays") is not True:
            raise ValueError("primary row has unsuccessful or nonfinite collocation")
        for key in ("sigma", "derivative_jump_abs", "max_first_integral_residual"):
            if not isinstance(row.get(key), (int, float)) or not math.isfinite(float(row[key])):
                raise ValueError("primary row diagnostic is missing or nonfinite")
        if index == 2 and (float(row["derivative_jump_abs"]) >= 1.0e-6 or float(row["max_first_integral_residual"]) >= 1.0e-6 or row.get("amplitude_bounds_pass") is not True):
            raise ValueError("primary finest diagnostic threshold failed")
    field_paths = {row.get("fields_file") for row in rows if isinstance(row, dict)}
    if len(field_paths) != 3 or not field_paths.issubset(manifest_paths):
        raise ValueError("primary field artifact set is incomplete")
    primary_scalars = primary.get("scalars")
    if not isinstance(primary_scalars, dict):
        raise ValueError("primary scalars missing")
    scalar_checks = []
    for name, expected in values.items():
        actual = primary_scalars.get(name)
        ok = isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(float(actual)) and abs(float(actual) - expected) <= 1.0e-10 * max(1.0, abs(expected))
        scalar_checks.append({"name": name, "pass": ok, "primary": actual, "independent": expected})
    if not all(item["pass"] for item in scalar_checks):
        raise ValueError("primary scalar mismatch")
    loaded_primary: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("bvp_success") is not True or row.get("finite_arrays") is not True or not isinstance(row.get("fields_file"), str):
            raise ValueError("primary row is unqualified or malformed")
        fields = safe_primary_path(path.parent, row["fields_file"])
        manifest = next((item for _, item in artifact_items if item.get("path") == row["fields_file"]), None)
        if not isinstance(manifest, dict) or not fields.is_file() or raw_sha256(fields) != manifest.get("raw_sha256"):
            raise ValueError("primary fields artifact is absent or not manifested")
        with np.load(fields, allow_pickle=False) as data:
            if sorted(data.files) != ["c", "cx", "f", "fx", "x"]:
                raise ValueError("primary fields artifact keys mismatch")
            arrays = [np.asarray(data[key]) for key in ("x", "f", "c", "fx", "cx")]
            if any(a.dtype != np.dtype("float64") or not np.all(np.isfinite(a)) for a in arrays):
                raise ValueError("nonfinite primary fields")
            if arrays[0].ndim != 1 or any(a.shape != arrays[0].shape for a in arrays[1:]) or np.any(np.diff(arrays[0]) <= 0.0):
                raise ValueError("primary fields coordinates malformed")
            loaded_primary.append((arrays[0], arrays[1], arrays[2]))
    independent_finest = independent_rows[3]
    primary_finest = loaded_primary[2]
    if primary_finest[0].shape != independent_finest["x"].shape or not np.allclose(primary_finest[0], independent_finest["x"], rtol=0.0, atol=0.0):
        raise ValueError("primary and independent finest coordinates differ")
    surface_values = [float(row.get("sigma", float("nan"))) for row in rows]
    if any(not math.isfinite(v) for v in surface_values):
        raise ValueError("primary surface values malformed")
    sigma_diff = abs(independent_finest["energy"] - surface_values[2])
    field_diff = max(float(np.max(np.abs(independent_finest["f"] - primary_finest[1]))), float(np.max(np.abs(independent_finest["c"] - primary_finest[2]))))
    coarse_error = abs(independent_rows[2]["energy"] - surface_values[2])
    refinement_ok = sigma_diff < coarse_error or (coarse_error < 1.0e-8 and sigma_diff < 1.0e-8)
    primary_domain_ok = abs(surface_values[1] - surface_values[2]) < 1.0e-5
    result["primary_comparison"] = [{"name": "surface_cost_finest", "pass": sigma_diff < 2.0e-4, "difference": sigma_diff}, {"name": "field_difference_finest", "pass": field_diff < 1.0e-3, "maximum": field_diff}, {"name": "same_domain_refinement", "pass": refinement_ok, "coarse_error": coarse_error, "fine_error": sigma_diff}, {"name": "primary_L9_L12_surface_difference", "pass": primary_domain_ok, "difference": abs(surface_values[1] - surface_values[2])}, {"name": "primary_scalar_identity", "pass": True, "scalars": scalar_checks}, {"name": "primary_artifact_hashes", "pass": True, "count": len(artifact_items)}]
    for row in result["primary_comparison"]:
        if not row["pass"]:
            result["failures"].append("primary:" + row["name"])


def run(output: Path, note: Path, primary_path: Path) -> int:
    output.mkdir(parents=False, exist_ok=False)
    result = empty_result()
    program = Path(__file__).resolve()
    result["identities"]["program"] = source_identity(program)
    try:
        protocol, derivation, parent = extract_sources(note)
        protocol_hash = hashlib.sha256(protocol.encode("utf-8")).hexdigest()
        derivation_hash = hashlib.sha256(derivation.encode("utf-8")).hexdigest()
        parent_hash = hashlib.sha256(parent.encode("utf-8")).hexdigest()
        result["identities"].update({"protocol": {"path": repo_path(note), "canonical_sha256": protocol_hash, "snapshot": protocol}, "derivation": {"path": repo_path(note), "canonical_sha256": derivation_hash, "snapshot": derivation}, "parent": {"path": repo_path(PARENT), "canonical_sha256": parent_hash, "snapshot": parent}})
        check(result, "protocol_hash", protocol_hash == PROTOCOL_SHA256, {"actual": protocol_hash, "expected": PROTOCOL_SHA256})
        check(result, "derivation_hash", derivation_hash == DERIVATION_SHA256, {"actual": derivation_hash, "expected": DERIVATION_SHA256})
        check(result, "parent_hash", parent_hash == PARENT_SHA256, {"actual": parent_hash, "expected": PARENT_SHA256})
        if result["failures"]:
            raise ValueError("frozen prerequisite hash mismatch")
        snapshots = [("snapshot_program.py", canonical_text(program)), ("snapshot_protocol.txt", protocol), ("snapshot_derivation.txt", derivation), ("snapshot_parent.md", parent)]
        for filename, text in snapshots:
            snapshot_path = output / filename
            snapshot_path.write_bytes(text.encode("utf-8"))
            result["artifacts"].append({"path": filename, "raw_sha256": raw_sha256(snapshot_path), "bytes": snapshot_path.stat().st_size, "kind": "source_snapshot"})
        values = constants()
        result["scalars"] = values
        result["analytical_review"] = analytical_review(values)
        rows: list[dict[str, Any]] = []
        raw_rows: list[dict[str, Any]] = []
        for L, intervals in GRIDS:
            solved = solve_row(L, intervals, values)
            raw_rows.append(solved)
            fields_name = f"fields_L{str(L).replace('.', 'p')}_N{intervals}.npz"
            field_manifest = save_array(output / fields_name, {"x": solved["x"], "f": solved["f"], "c": solved["c"]})
            result["artifacts"].append(field_manifest)
            row = {"L": L, "intervals": intervals, "sigma": solved["energy"], "fields_file": fields_name, "pass": solved["pass"], "diagnostics": {"max_free_euler_residual": solved["max_free_euler_residual"], "midpoint_euler_residual": solved["midpoint_euler_residual"], "converged": solved["converged"], "stop_reason": solved["stop_reason"], "amplitudes": solved["amplitudes"], "attempt_count": len(solved["attempts"]), "attempts": solved["attempts"]}}
            rows.append(row)
        result["rows"] = rows
        finest = raw_rows[-1]
        spectral_payload, spectral_arrays = spectra(finest, values)
        spectral_name = "spectra_finest.npz"
        np.savez_compressed(output / spectral_name, **spectral_arrays)
        result["artifacts"].append({"path": spectral_name, "raw_sha256": raw_sha256(output / spectral_name), "bytes": (output / spectral_name).stat().st_size})
        result["spectral"] = spectral_payload
        check(result, "all_four_rows_converged", all(row["pass"] for row in rows), [{"L": row["L"], "intervals": row["intervals"], "pass": row["pass"]} for row in rows])
        check(result, "finest_midpoint_euler_residual", finest["midpoint_euler_residual"] < 1.0e-6, finest["midpoint_euler_residual"])
        check(result, "finest_amplitude_bounds", finest["amplitudes"]["f_pass"] and finest["amplitudes"]["c_pass"], finest["amplitudes"])
        check(result, "surface_bounds", values["sigma_lower"] - 1.0e-6 <= finest["energy"] <= values["sigma_upper"] + 1.0e-6, {"sigma": finest["energy"], "lower": values["sigma_lower"], "upper": values["sigma_upper"]})
        eig_ok = all(float(x) > -2.0e-4 for x in spectral_payload["amplitude_eigenvalues"]) and all(float(x["eigenvalue"]) > -2.0e-4 and float(x["residual"]) < 1.0e-7 for x in spectral_payload["phase"].values()) and all(float(x) < 1.0e-7 for x in spectral_payload["amplitude_residuals"])
        check(result, "scalar_spectral_qualification", eig_ok, spectral_payload)
        check(result, "analytical_review", bool(result["analytical_review"].get("pass")), result["analytical_review"])
        compare_primary(primary_path.resolve(), result, values, raw_rows)
        check(result, "finite_json_payload", finite(result), {"allow_nan": False})
        result["numerical_pass"] = not result["failures"]
        result["verdict"] = VERDICT_SUPPORTS if result["numerical_pass"] else VERDICT_INCONCLUSIVE
    except Exception as exc:
        result["failures"].append(f"{type(exc).__name__}: {exc}")
        result["numerical_pass"] = False
        result["verdict"] = VERDICT_INCONCLUSIVE
        if not result["rows"]:
            result["scalars"] = {}
            result["rows"] = []
            result["checks"] = []
            result["artifacts"] = []
            result["analytical_review"] = {}
            result["spectral"] = {}
            result["primary_comparison"] = []
    finally:
        write_json(output / "verification.json", result)
    print(json.dumps({"schema": SCHEMA, "numerical_pass": result["numerical_pass"], "verdict": result["verdict"], "failures": result["failures"]}, ensure_ascii=False, allow_nan=False))
    return 0 if result["numerical_pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--note", type=Path, default=REPORT)
    parser.add_argument("--primary", type=Path, required=True)
    args = parser.parse_args()
    return run(args.output_dir.resolve(), args.note.resolve(), args.primary.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
