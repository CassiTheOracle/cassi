#!/usr/bin/env python3
"""Independent verifier for the finite-period axial energy comparison.

The verifier consumes a hash-bound manifest and the primary axial-energy output.
It reconstructs the radial action, carrier population, response tangent, radial
connection and all finite-period energies from ``verify_matter_formation_vortex_core``
only.  It intentionally imports no primary energy or differentiation code.
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

from verify_matter_formation_vortex_core import (
    GAUSS_X,
    K_CX,
    ETA_C,
    LAMBDA_RHO,
    RHO0,
    local_lambdas,
    gauss_reconstruct,
)
from verify_matter_formation_vortex_core import g as G_Q
from verify_matter_formation_vortex_core import a as A_COEFF
from verify_matter_formation_vortex_core import d as D_COEFF

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = "computations/matter-formation-continuum-report.md"
SECTION_HEADING = "## 48. Working notes:"
SCHEMA = "matter-formation-vortex-axial-energy-verification-v1"
PRIMARY_SCHEMA = "matter-formation-vortex-axial-energy-v1"
MANIFEST_SCHEMA = "matter-formation-vortex-axial-energy-manifest-v1"
INCONCLUSIVE = "INCONCLUSIVE"
CONTRADICTS = "CONTRADICTS-finite-period uniform-core energy minimum"
NO_EMERGENCE = "DOES NOT EMERGE in the specified trial family"
CAPS = ("plus", "minus")
EPSILONS = {"plus": 1, "minus": -1}
SCHEDULE = ((32.0, 256), (32.0, 512), (64.0, 512), (64.0, 1024))
AMPLITUDES = (0.25, 0.125, 0.0625)
QUADRATURES = (32, 64)
WAVE_FACTORS = (0.5, 2.0)
WINDINGS = (0, 1)
TRANSVERSE_COMPONENTS = (
    "fundamental_radial", "adjoint_radial", "fundamental_angular",
    "adjoint_angular", "magnetic", "potential", "carrier_gradient",
    "carrier_interaction", "carrier_quartic",
)
AXIAL_COMPONENTS = ("fundamental", "adjoint", "radial_connection", "angular_connection", "carrier")
REQUIRED_PROFILE = ("r", "y", "f")
REQUIRED_RESPONSE = ("response", "lump", "zeta")


def finite(value: Any) -> bool:
    if value is None or isinstance(value, (bool, np.bool_)):
        return True
    if isinstance(value, (int, float, np.integer, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, np.ndarray):
        return bool(np.all(np.isfinite(value)))
    if isinstance(value, (list, tuple)):
        return all(finite(item) for item in value)
    if isinstance(value, dict):
        return all(finite(item) for item in value.values())
    return True


def strict_json(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject(token: str) -> None:
        raise ValueError(f"nonfinite JSON token: {token}")

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=reject)
    if not isinstance(value, dict) or not finite(value):
        raise ValueError("JSON value must be a finite object")
    return value


def jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [jsonable(item) for item in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_relative_path(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f"invalid relative path: {value!r}")
    result = (root / value).resolve()
    root_resolved = root.resolve()
    if result != root_resolved and root_resolved not in result.parents:
        raise ValueError(f"path escapes root: {value}")
    return result


def close_value(actual: Any, expected: Any, tolerance: float, floor: float = 1.0) -> tuple[bool, float]:
    try:
        error = abs(float(actual) - float(expected)) / max(float(floor), abs(float(expected)))
    except (TypeError, ValueError, OverflowError):
        return False, math.inf
    return bool(math.isfinite(error) and error <= tolerance), float(error)


def close_array(actual: np.ndarray, expected: np.ndarray, tolerance: float, floor: float = 1.0) -> tuple[bool, float]:
    if actual.shape != expected.shape or not np.all(np.isfinite(actual)) or not np.all(np.isfinite(expected)):
        return False, math.inf
    error = np.max(np.abs(actual - expected) / np.maximum(float(floor), np.abs(expected))) if actual.size else 0.0
    return bool(np.isfinite(error) and error <= tolerance), float(error)


def check(bucket: dict[str, Any], name: str, passed: bool, evidence: Any = None) -> None:
    bucket.setdefault("checks", []).append({"name": name, "pass": bool(passed), "evidence": jsonable(evidence)})
    if not passed:
        bucket.setdefault("failures", []).append(name)


def expected_keys() -> list[tuple[str, int, int, float, int]]:
    return [(cap, EPSILONS[cap], 64, int(R), N) for cap in CAPS for R, N in SCHEDULE]


def expected_trials() -> list[tuple[float, int, int, float, int]]:
    return [(A, ai, Q, wf, w) for ai, A in enumerate(AMPLITUDES) for Q in QUADRATURES for wf in WAVE_FACTORS for w in WINDINGS]


def verify_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = strict_json(manifest_path)
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("manifest schema mismatch")
    section = manifest.get("section")
    if not isinstance(section, dict) or section.get("path") != NOTEBOOK or section.get("heading") != SECTION_HEADING:
        raise ValueError("manifest section identity mismatch")
    snapshot = safe_relative_path(manifest_path.parent, section.get("snapshot"))
    live = safe_relative_path(ROOT, section.get("path"))
    expected = section.get("sha256")
    if not isinstance(expected, str) or sha256(snapshot) != expected:
        raise ValueError("section snapshot hash mismatch")
    snapshot_text = snapshot.read_text(encoding="utf-8")
    live_text = live.read_text(encoding="utf-8")
    at = live_text.find(SECTION_HEADING)
    if at < 0 or live_text[at:at + len(snapshot_text)] != snapshot_text:
        raise ValueError("live report does not contain exact frozen section snapshot")

    source_receipts = manifest.get("sources")
    required_sources = {
        "computations/matter_formation_vortex_core.py",
        "computations/verify_matter_formation_vortex_core.py",
        "computations/matter_formation_vortex_loaded.py",
        "computations/verify_matter_formation_vortex_loaded.py",
        "computations/matter_formation_vortex_compressibility.py",
        "computations/verify_matter_formation_vortex_compressibility.py",
        "computations/matter_formation_vortex_axial_energy.py",
        "computations/verify_matter_formation_vortex_axial_energy.py",
    }
    if not isinstance(source_receipts, list) or {item.get("path") for item in source_receipts if isinstance(item, dict)} != required_sources:
        raise ValueError("manifest source set is incomplete or unexpected")
    sources: list[dict[str, Any]] = []
    for receipt in source_receipts:
        if not isinstance(receipt, dict):
            raise ValueError("malformed source receipt")
        path = safe_relative_path(ROOT, receipt.get("path"))
        frozen = safe_relative_path(manifest_path.parent, receipt.get("snapshot"))
        digest = receipt.get("sha256")
        size = receipt.get("bytes")
        if not isinstance(digest, str) or sha256(path) != digest or sha256(frozen) != digest or int(size) != path.stat().st_size or int(size) != frozen.stat().st_size:
            raise ValueError(f"source hash or byte-count mismatch: {receipt.get('path')}")
        sources.append({"path": receipt["path"], "snapshot": receipt["snapshot"], "sha256": digest, "bytes": int(size)})

    evidence = manifest.get("evidence")
    required_evidence = {
        "runs/20260908_matter_formation_vortex_loaded/primary/summary.json",
        "runs/20260908_matter_formation_vortex_loaded/verification/verification.json",
        "runs/20260908_matter_formation_vortex_compressibility/primary/summary.json",
        "runs/20260908_matter_formation_vortex_compressibility/verification/verification.json",
    }
    if not isinstance(evidence, list) or {item.get("path") for item in evidence if isinstance(item, dict)} != required_evidence:
        raise ValueError("manifest evidence set is incomplete")
    evidence_receipts: list[dict[str, Any]] = []
    for receipt in evidence:
        if not isinstance(receipt, dict):
            raise ValueError("malformed evidence receipt")
        path = safe_relative_path(ROOT, receipt.get("path"))
        digest = receipt.get("sha256")
        if not isinstance(digest, str) or sha256(path) != digest:
            raise ValueError(f"evidence hash mismatch: {receipt.get('path')}")
        evidence_receipts.append({"path": receipt["path"], "sha256": digest})

    inputs = manifest.get("inputs")
    if not isinstance(inputs, list) or len(inputs) != 8:
        raise ValueError("manifest must contain exactly eight inputs")
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int, float, int]] = set()
    for item in inputs:
        if not isinstance(item, dict):
            raise ValueError("malformed input record")
        cap = item.get("cap")
        key = (cap, int(item.get("epsilon", 0)), int(item.get("n", -1)), float(item.get("R", -1)), int(item.get("N", -1)))
        if key not in expected_keys() or key in seen:
            raise ValueError(f"input identity mismatch: {key}")
        seen.add(key)
        profile = safe_relative_path(ROOT, item.get("path"))
        response = safe_relative_path(ROOT, item.get("response_path"))
        if item.get("sha256") != sha256(profile) or item.get("response_sha256") != sha256(response):
            raise ValueError(f"input hash mismatch: {key}")
        records.append({**item, "path": profile, "response_path": response})
    if seen != set(expected_keys()):
        raise ValueError("input schedule is incomplete")
    records.sort(key=lambda item: expected_keys().index((item["cap"], int(item["epsilon"]), int(item["n"]), float(item["R"]), int(item["N"]))))
    return {"schema": manifest["schema"], "section": section, "sources": sources, "evidence": evidence_receipts, "inputs": records}


def parent_acceptance(manifest: dict[str, Any]) -> dict[str, Any]:
    paths = {item["path"]: ROOT / item["path"] for item in manifest["evidence"]}
    loaded_primary = strict_json(paths["runs/20260908_matter_formation_vortex_loaded/primary/summary.json"])
    loaded_verification = strict_json(paths["runs/20260908_matter_formation_vortex_loaded/verification/verification.json"])
    response_primary = strict_json(paths["runs/20260908_matter_formation_vortex_compressibility/primary/summary.json"])
    response_verification = strict_json(paths["runs/20260908_matter_formation_vortex_compressibility/verification/verification.json"])
    if loaded_primary.get("schema") != "matter-formation-loaded-vortex-v1" or loaded_primary.get("all_rows_numerically_qualified") is not True:
        raise ValueError("loaded primary parent is not accepted")
    if loaded_verification.get("schema") != "matter-formation-loaded-vortex-verification-v1" or loaded_verification.get("numerical_pass") is not True:
        raise ValueError("loaded verification parent is not accepted")
    if response_primary.get("schema") != "matter-formation-vortex-compressibility-v1" or response_primary.get("numerical_pass") is not True:
        raise ValueError("response primary parent is not accepted")
    if response_verification.get("schema") != "matter-formation-vortex-compressibility-verification-v1" or response_verification.get("numerical_pass") is not False or response_verification.get("verdict") != INCONCLUSIVE:
        raise ValueError("response aggregate must remain INCONCLUSIVE")
    loaded_rows = loaded_primary.get("rows")
    response_rows = response_primary.get("rows")
    response_vrows = response_verification.get("rows")
    if not isinstance(loaded_rows, list) or not isinstance(response_rows, list) or len(loaded_rows) != 24 or len(response_rows) != 24 or not isinstance(response_vrows, list):
        raise ValueError("parent schedules are incomplete")
    loaded_by_key = {(row.get("cap"), int(row.get("n", -1)), float(row.get("R", -1)), int(row.get("N", -1))): row for row in loaded_rows}
    response_by_key = {(row.get("cap"), int(row.get("n", -1)), float(row.get("R", -1)), int(row.get("N", -1))): row for row in response_rows}
    response_v_by_key = {(row.get("cap"), int(row.get("n", -1)), float(row.get("R", -1)), int(row.get("N", -1))): row for row in response_vrows}
    for cap, _, n, R, N in expected_keys():
        key = (cap, n, R, N)
        loaded_row = loaded_by_key.get(key)
        response_row = response_by_key.get(key)
        vrow = response_v_by_key.get(key)
        if loaded_row is None or response_row is None or vrow is None or loaded_row.get("stationary") is not True or loaded_row.get("exception") is not None or response_row.get("qualified") is not True or response_row.get("exception") is not None:
            raise ValueError(f"parent selected row is not qualified: {key}")
        if n == 64:
            if vrow.get("pass") is not True or len(vrow.get("fd", [])) != 3 or not all(item.get("pass") is True for item in vrow.get("fd", [])):
                raise ValueError(f"selected response row does not pass all three FD comparisons: {key}")
    return {"loaded_primary": loaded_primary, "loaded_verification": loaded_verification, "response_primary": response_primary, "response_verification": response_verification, "loaded_rows": loaded_by_key, "response_rows": response_by_key}


def nodal_lump(r: np.ndarray) -> np.ndarray:
    n = r.size - 1
    lump = np.zeros(n + 1, dtype=np.float64)
    for e, (left, right) in enumerate(zip(r[:-1], r[1:])):
        dr = right - left
        mid = 0.5 * (left + right)
        half = 0.5 * dr
        for xi in GAUSS_X:
            rq = mid + half * xi
            wt = 2.0 * math.pi * rq * half
            lump[e] += wt * (1.0 - xi) / 2.0
            lump[e + 1] += wt * (1.0 + xi) / 2.0
    return lump


def integrate_q(rq: np.ndarray, values: np.ndarray, r: np.ndarray) -> float:
    half = 0.5 * np.diff(r)
    return float(np.sum(2.0 * math.pi * rq * values * half[:, None]))


def h_and_direction(q: dict[str, np.ndarray], variation: dict[str, np.ndarray], epsilon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    fns = local_lambdas(epsilon)
    fields = q["fields"].reshape(-1, 5)
    derivs = q["derivatives"].reshape(-1, 5)
    rq = q["r"].reshape(-1)
    vf = variation["fields"].reshape(-1, 5)
    vd = variation["derivatives"].reshape(-1, 5)
    args0 = tuple(fields[:, j] for j in range(5)) + tuple(derivs[:, j] for j in range(5)) + (np.zeros(rq.size), rq)
    H = np.asarray(fns["H"](*args0), dtype=np.float64)
    L = np.asarray(fns["L"](*args0), dtype=np.float64)
    h = -L / H
    p, qv, u, b1, b3 = (fields[:, j] for j in range(5))
    pr, qr, ur, b1r, b3r = (derivs[:, j] for j in range(5))
    vp, vq, vu, vb1, vb3 = (vf[:, j] for j in range(5))
    vpr, vqr, vur, vb1r, vb3r = (vd[:, j] for j in range(5))
    dH = A_COEFF * (p * vp + qv * vq) / 2.0 + 2.0 * D_COEFF * u * vu + 2.0 * D_COEFF / (G_Q * G_Q * rq * rq) * ((b3 - epsilon) * vb3 + b1 * vb1)
    dL = A_COEFF * (vp * qr + p * vqr - vq * pr - qv * vpr) / 2.0 + D_COEFF / (G_Q * G_Q * rq * rq) * (vb3 * b1r + (b3 - epsilon) * vb1r - vb1 * b3r - b1 * vb3r)
    dh = -(dL * H - L * dH) / (H * H)
    return h, dh, H, L




def eval_fields(r: np.ndarray, y: np.ndarray, f: np.ndarray, epsilon: int, dy: np.ndarray | None = None) -> dict[str, Any]:
    q = gauss_reconstruct(r, y, epsilon)
    fq = 0.5 * (f[:-1, None] * (1.0 - GAUSS_X)[None, :] + f[1:, None] * (1.0 + GAUSS_X)[None, :])
    dfq = np.broadcast_to(((f[1:] - f[:-1]) / np.diff(r))[:, None], fq.shape)
    direction = gauss_reconstruct(r, np.zeros_like(y) if dy is None else dy, epsilon)
    h, dh, H, L = h_and_direction(q, direction, epsilon)
    n = r.size - 1
    flat_fields = q["fields"].reshape(-1, 5)
    flat_derivs = q["derivatives"].reshape(-1, 5)
    rq = q["r"].reshape(-1)
    args = tuple(flat_fields[:, j] for j in range(5)) + tuple(flat_derivs[:, j] for j in range(5)) + (h, rq)
    fns = local_lambdas(epsilon)
    core = np.column_stack([np.asarray(fn(*args), dtype=np.float64).reshape(-1) for fn in fns["components"]])
    rho = flat_fields[:, 0] ** 2 + flat_fields[:, 1] ** 2
    carrier = np.column_stack((K_CX * dfq.reshape(-1) ** 2 / 2.0, -ETA_C * (RHO0 - rho) * fq.reshape(-1) ** 2, fq.reshape(-1) ** 4 / 2.0))
    components = np.column_stack((core, carrier)).reshape(n, 2, 9)
    return {"q": q, "variation": direction, "fq": fq, "dfq": dfq, "h": h.reshape(n, 2), "h_direction": dh.reshape(n, 2), "H": H.reshape(n, 2), "L": L.reshape(n, 2), "components": components}


def population(r: np.ndarray, fq: np.ndarray) -> float:
    return integrate_q(np.asarray(0.5 * (r[:-1, None] + r[1:, None]) + 0.5 * np.diff(r)[:, None] * GAUSS_X[None, :]), fq * fq, r)


def base_evaluation(r: np.ndarray, y: np.ndarray, f: np.ndarray, dy: np.ndarray, df: np.ndarray, epsilon: int) -> dict[str, Any]:
    ev = eval_fields(r, y, f, epsilon, dy)
    q = ev["q"]
    variation = ev["variation"]
    rq = q["r"]
    values = ev["components"]
    half = 0.5 * np.diff(r)
    base_components = np.sum(2.0 * math.pi * rq[:, :, None] * values * half[:, None, None], axis=(0, 1))
    P0 = population(r, ev["fq"])
    Pdf = population(r, 0.5 * (df[:-1, None] * (1.0 - GAUSS_X)[None, :] + df[1:, None] * (1.0 + GAUSS_X)[None, :]))
    return {**ev, "variation": variation, "base_components": base_components, "base_energy": float(np.sum(base_components)), "population": P0, "population_df": Pdf, "dy_q": variation["fields"], "dy_dq": variation["derivatives"]}


def trial_samples(r: np.ndarray, y0: np.ndarray, f0: np.ndarray, dy: np.ndarray, df: np.ndarray, epsilon: int, amplitude: float, quadrature: int, P0: float, Pdf: float) -> dict[str, Any]:
    theta = 2.0 * math.pi * np.arange(quadrature, dtype=np.float64) / quadrature
    yq_arrays = []
    axial_arrays = []
    pop_values = np.empty(quadrature, dtype=np.float64)
    normalization = math.sqrt(P0 / (P0 + amplitude * amplitude * Pdf / 2.0))
    half = 0.5 * np.diff(r)
    for angle in theta:
        cosine, sine = math.cos(float(angle)), math.sin(float(angle))
        y = y0 + amplitude * dy * cosine
        f = normalization * (f0 + amplitude * df * cosine)
        ev = eval_fields(r, y, f, epsilon, dy)
        variation = ev["variation"]
        # eval_fields gives Dh at the perturbed y; its directional field is dy.
        htheta = -amplitude * sine * ev["h_direction"]
        dtheta_fields = -amplitude * sine * variation["fields"]
        dtheta_fq = -normalization * amplitude * sine * (0.5 * (df[:-1, None] * (1.0 - GAUSS_X)[None, :] + df[1:, None] * (1.0 + GAUSS_X)[None, :]))
        rq = ev["q"]["r"]
        transverse = ev["components"]
        axial_density = np.stack((
            A_COEFF * (dtheta_fields[..., 0] ** 2 + dtheta_fields[..., 1] ** 2) / 2.0,
            D_COEFF * dtheta_fields[..., 2] ** 2 / 2.0,
            D_COEFF * htheta * htheta / (2.0 * G_Q * G_Q),
            D_COEFF * (dtheta_fields[..., 3] ** 2 + dtheta_fields[..., 4] ** 2) / (2.0 * G_Q * G_Q * rq * rq),
            K_CX * dtheta_fq * dtheta_fq / 2.0,
        ), axis=-1)
        transverse_integrated = np.sum(2.0 * math.pi * rq[:, :, None] * transverse * half[:, None, None], axis=(0, 1))
        axial = np.sum(2.0 * math.pi * rq[:, :, None] * axial_density * half[:, None, None], axis=(0, 1))
        pop_values[len(yq_arrays)] = population(r, ev["fq"])
        yq_arrays.append(transverse_integrated)
        axial_arrays.append(axial)
    return {"theta": theta, "energy_components": np.asarray(yq_arrays), "axial_components": np.asarray(axial_arrays), "population": pop_values, "normalization": normalization}


def sample_path(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if path != root.resolve() and root.resolve() not in path.parents:
        raise ValueError(f"primary path escapes input root: {name}")
    return path


def compare_trials(row_out: dict[str, Any], primary_row: dict[str, Any], primary_dir: Path, base: dict[str, Any], profile_stem: str, samples_by_key: dict[tuple[int, int], dict[str, Any]]) -> None:
    primary_trials = primary_row.get("trials")
    if not isinstance(primary_trials, list) or len(primary_trials) != 24:
        check(row_out, "primary_trial_schedule", False, len(primary_trials) if isinstance(primary_trials, list) else None)
        return
    own_trials: dict[tuple[float, int, int, float, int], dict[str, Any]] = {}
    for amplitude, ai, Q, wf, winding in expected_trials():
        samples = samples_by_key[(ai, Q)]
        primary = next((item for item in primary_trials if float(item.get("amplitude", math.nan)) == amplitude and int(item.get("amplitude_index", -1)) == ai and int(item.get("quadrature", -1)) == Q and float(item.get("wave_factor", math.nan)) == wf and int(item.get("winding", -1)) == winding), None)
        if primary is None:
            check(row_out, f"trial_present_a{ai}_Q{Q}_f{wf}_w{winding}", False, None)
            continue
        p = float(primary.get("p", math.nan))
        expected_p = wf * math.sqrt(-base["zeta"] / base["B"]) if base["zeta"] < 0.0 and base["B"] > 0.0 else math.nan
        check(row_out, f"trial_p_formula_a{ai}_Q{Q}_f{wf}_w{winding}", close_value(p, expected_p, 1e-8, 1e-10)[0], {"primary": p, "expected": expected_p, "normalized_error": close_value(p, expected_p, 1e-8, 1e-10)[1]})
        transverse_mean = float(np.mean(np.sum(samples["energy_components"], axis=1)))
        axial_mean = float(np.mean(np.sum(samples["axial_components"], axis=1)))
        current_coefficient = K_CX * (winding * p) ** 2 / 2.0
        full = transverse_mean + p * p * axial_mean + current_coefficient * float(np.mean(samples["population"]))
        baseline = base["base_energy"] + current_coefficient * base["population"]
        delta = full - baseline
        Qvalue = 4.0 * delta / (amplitude * amplitude)
        prediction = base["zeta"] + base["B"] * p * p
        trial = {"amplitude": amplitude, "amplitude_index": ai, "quadrature": Q, "wave_factor": wf, "winding": winding, "p": p, "delta_energy_per_length": delta, "Q": Qvalue, "quadratic_prediction": prediction, "relative_prediction_error": abs(Qvalue - prediction) / max(1e-10, abs(prediction)), "population_error": abs(float(np.mean(samples["population"])) - base["population"]) / max(1.0, abs(base["population"])), "samples_npz": f"{profile_stem}_a{ai}_Q{Q}.npz", "sample_population_min": float(np.min(samples["population"])), "sample_population_max": float(np.max(samples["population"]))}
        own_trials[(amplitude, ai, Q, wf, winding)] = trial
        primary_q = float(primary.get("Q", math.nan))
        check(row_out, f"trial_Q_match_a{ai}_Q{Q}_f{wf}_w{winding}", close_value(Qvalue, primary_q, 1e-6, 1e-10)[0], {"derived": Qvalue, "primary": primary_q, "normalized_error": close_value(Qvalue, primary_q, 1e-6, 1e-10)[1]})
        check(row_out, f"trial_prediction_a{ai}_Q{Q}_f{wf}_w{winding}", trial["relative_prediction_error"] <= 0.02, trial["relative_prediction_error"])
        check(row_out, f"trial_population_a{ai}_Q{Q}_f{wf}_w{winding}", trial["population_error"] < 1e-10, trial["population_error"])
        primary_samples_name = primary.get("samples_npz")
        if not isinstance(primary_samples_name, str):
            check(row_out, f"primary_samples_name_a{ai}_Q{Q}", False, primary_samples_name)
        else:
            try:
                with np.load(sample_path(primary_dir, primary_samples_name), allow_pickle=False) as pdata:
                    for key in ("theta", "energy_components", "axial_components", "population", "normalization"):
                        if key not in pdata:
                            raise ValueError(f"missing {key}")
                        actual = np.asarray(pdata[key], dtype=np.float64)
                        expected = np.asarray(samples[key], dtype=np.float64)
                        ok, err = close_array(expected, actual, 1e-8)
                        check(row_out, f"sample_{key}_match_a{ai}_Q{Q}", ok, {"normalized_error": err})
            except Exception as exc:
                check(row_out, f"sample_load_a{ai}_Q{Q}", False, f"{type(exc).__name__}: {exc}")
    row_out["trials"] = [own_trials[key] for key in expected_trials() if key in own_trials]
    for ai, amplitude in enumerate(AMPLITUDES):
        for wf in WAVE_FACTORS:
            for winding in WINDINGS:
                q32 = own_trials.get((amplitude, ai, 32, wf, winding), {}).get("Q", math.nan)
                q64 = own_trials.get((amplitude, ai, 64, wf, winding), {}).get("Q", math.nan)
                check(row_out, f"quadrature_Q_agreement_a{ai}_f{wf}_w{winding}", close_value(q32, q64, 1e-6, 1e-10)[0], {"Q32": q32, "Q64": q64})
        for Q in QUADRATURES:
            slow0 = own_trials.get((amplitude, ai, Q, 0.5, 0), {}).get("Q", math.nan)
            slow1 = own_trials.get((amplitude, ai, Q, 0.5, 1), {}).get("Q", math.nan)
            fast0 = own_trials.get((amplitude, ai, Q, 2.0, 0), {}).get("Q", math.nan)
            fast1 = own_trials.get((amplitude, ai, Q, 2.0, 1), {}).get("Q", math.nan)
            check(row_out, f"winding_Q_agreement_slow_a{ai}_Q{Q}", close_value(slow0, slow1, 1e-6, 1e-10)[0], {"w0": slow0, "w1": slow1})
            check(row_out, f"winding_Q_agreement_fast_a{ai}_Q{Q}", close_value(fast0, fast1, 1e-6, 1e-10)[0], {"w0": fast0, "w1": fast1})


def verify_row(record: dict[str, Any], primary_row: dict[str, Any], primary_dir: Path, output: Path) -> dict[str, Any]:
    cap, epsilon, R, N = record["cap"], int(record["epsilon"]), float(record["R"]), int(record["N"])
    stem = f"cap_{cap}_n64_N{N}_R{int(R)}"
    out: dict[str, Any] = {"cap": cap, "epsilon": epsilon, "n": 64, "R": R, "N": N, "base_npz": stem + "_axial.npz", "checks": [], "failures": [], "trials": [], "exception": None, "complete_physical_matter_formation": False}
    try:
        with np.load(record["path"], allow_pickle=False) as pdata:
            missing = [key for key in REQUIRED_PROFILE if key not in pdata]
            check(out, "profile_arrays_present", not missing, missing)
            if missing:
                raise ValueError(f"profile arrays missing: {missing}")
            r, y, f = (np.asarray(pdata[key], dtype=np.float64) for key in REQUIRED_PROFILE)
        with np.load(record["response_path"], allow_pickle=False) as response:
            missing = [key for key in REQUIRED_RESPONSE if key not in response]
            check(out, "response_arrays_present", not missing, missing)
            if missing:
                raise ValueError(f"response arrays missing: {missing}")
            response_vec = np.asarray(response["response"], dtype=np.float64).reshape(-1)
            supplied_lump = np.asarray(response["lump"], dtype=np.float64).reshape(-1)
            zeta = float(np.asarray(response["zeta"]).reshape(-1)[0])
        check(out, "profile_shapes", r.shape == (N + 1,) and y.shape == (N + 1, 5) and f.shape == (N + 1,), {"r": r.shape, "y": y.shape, "f": f.shape})
        check(out, "finite_inputs", finite(r) and finite(y) and finite(f) and finite(response_vec) and finite(supplied_lump) and math.isfinite(zeta))
        check(out, "fixed_grid", close_array(r, np.linspace(0.0, R, N + 1), 1e-11)[0], None)
        if out["failures"]:
            raise ValueError("input qualification failed")
        lump = nodal_lump(r)
        check(out, "independent_lump", close_array(lump, supplied_lump, 1e-8)[0], {"normalized_error": close_array(lump, supplied_lump, 1e-8)[1]})
        tangent = response_vec.reshape(N, 6) / np.sqrt(lump[:-1, None])
        dy = np.zeros((N + 1, 5), dtype=np.float64); df = np.zeros(N + 1, dtype=np.float64)
        dy[:-1] = tangent[:, :5]; df[:-1] = tangent[:, 5]
        base = base_evaluation(r, y, f, dy, df, epsilon)
        base["r"], base["y"], base["f"], base["dy"], base["df"], base["zeta"] = r, y, f, dy, df, zeta
        B_components = np.array([
            integrate_q(base["q"]["r"], A_COEFF * (base["dy_q"][..., 0] ** 2 + base["dy_q"][..., 1] ** 2), r),
            integrate_q(base["q"]["r"], D_COEFF * base["dy_q"][..., 2] ** 2, r),
            integrate_q(base["q"]["r"], D_COEFF * base["h_direction"] ** 2 / (G_Q * G_Q), r),
            integrate_q(base["q"]["r"], D_COEFF * (base["dy_q"][..., 3] ** 2 + base["dy_q"][..., 4] ** 2) / (G_Q * G_Q * base["q"]["r"] ** 2), r),
            integrate_q(base["q"]["r"], K_CX * (0.5 * (df[:-1, None] * (1.0 - GAUSS_X)[None, :] + df[1:, None] * (1.0 + GAUSS_X)[None, :])) ** 2, r),
        ], dtype=np.float64)
        B = float(np.sum(B_components))
        base["B"] = B
        L_star = 2.0 * math.pi / math.sqrt(-zeta / B) if B > 0.0 and zeta < 0.0 else math.nan
        out.update({"population": base["population"], "zeta": zeta, "B": B, "B_components": B_components.tolist(), "L_star": L_star, "p_star": 2.0 * math.pi / L_star if math.isfinite(L_star) else math.nan, "base_energy": base["base_energy"], "base_components": base["base_components"].tolist(), "qualified": True})
        check(out, "positive_B", B > 0.0, B)
        check(out, "negative_zeta", zeta < 0.0, zeta)
        check(out, "parent_identity", primary_row.get("cap") == cap and int(primary_row.get("epsilon", 0)) == epsilon and int(primary_row.get("n", -1)) == 64 and float(primary_row.get("R", -1)) == R and int(primary_row.get("N", -1)) == N, primary_row)
        check(out, "base_energy_match", close_value(base["base_energy"], primary_row.get("base_energy"), 1e-8)[0], {"derived": base["base_energy"], "primary": primary_row.get("base_energy")})
        check(out, "population_match", close_value(base["population"], primary_row.get("population"), 1e-8)[0], {"derived": base["population"], "primary": primary_row.get("population")})
        check(out, "base_population_target", abs(base["population"] - 64.0) / 64.0 < 1e-10, base["population"])
        check(out, "B_components_match", isinstance(primary_row.get("B_components"), list) and close_array(B_components, np.asarray(primary_row["B_components"], dtype=np.float64), 1e-8)[0], None)
        check(out, "B_match", close_value(B, primary_row.get("B"), 1e-8)[0], {"derived": B, "primary": primary_row.get("B")})
        check(out, "L_star_match", close_value(L_star, primary_row.get("L_star"), 1e-8)[0], {"derived": L_star, "primary": primary_row.get("L_star")})
        np.savez_compressed(output / out["base_npz"], r=r, y=y, f=f, dy=dy, df=df, field_variation=base["dy_q"], h=base["h"], h_direction=base["h_direction"], B_components=B_components, B=np.asarray(B), L_star=np.asarray(L_star), p_star=np.asarray(out["p_star"]), base_components=base["base_components"], base_energy=np.asarray(base["base_energy"]), population=np.asarray(base["population"]), zeta=np.asarray(zeta))
        primary_base_name = primary_row.get("base_npz")
        if not isinstance(primary_base_name, str):
            check(out, "primary_base_name", False, primary_base_name)
        else:
            try:
                with np.load(sample_path(primary_dir, primary_base_name), allow_pickle=False) as pbase:
                    required_base = ("r", "y", "f", "dy", "df", "field_variation", "h", "h_direction", "B_components", "B", "L_star", "p_star", "base_components", "population", "zeta")
                    missing_base = [key for key in required_base if key not in pbase]
                    check(out, "primary_base_arrays_present", not missing_base, missing_base)
                    if not missing_base:
                        expected_base = {"r": r, "y": y, "f": f, "dy": dy, "df": df, "field_variation": base["dy_q"], "h": base["h"], "h_direction": base["h_direction"], "B_components": B_components, "B": np.asarray(B), "L_star": np.asarray(L_star), "p_star": np.asarray(out["p_star"]), "base_components": base["base_components"], "population": np.asarray(base["population"]), "zeta": np.asarray(zeta)}
                        for key, expected_array in expected_base.items():
                            actual_array = np.asarray(pbase[key], dtype=np.float64)
                            ok, err = close_array(expected_array, actual_array, 1e-8)
                            check(out, f"primary_base_{key}_match", ok, {"normalized_error": err})
            except Exception as exc:
                check(out, "primary_base_load", False, f"{type(exc).__name__}: {exc}")
        samples_by_key = {}
        for ai, amplitude in enumerate(AMPLITUDES):
            for Q in QUADRATURES:
                samples = trial_samples(r, y, f, dy, df, epsilon, amplitude, Q, base["population"], base["population_df"])
                samples_by_key[(ai, Q)] = samples
                np.savez_compressed(output / f"{stem}_a{ai}_Q{Q}.npz", theta=samples["theta"], energy_components=samples["energy_components"], axial_components=samples["axial_components"], population=samples["population"], normalization=np.asarray(samples["normalization"]))
        compare_trials(out, primary_row, primary_dir, base, stem, samples_by_key)
    except Exception as exc:
        check(out, "row_execution", False, f"{type(exc).__name__}: {exc}")
        out["qualified"] = False
        out["exception"] = f"{type(exc).__name__}: {exc}"
    return out


def refinement_checks(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    refinements: list[dict[str, Any]] = []
    domains: list[dict[str, Any]] = []
    for cap in CAPS:
        for R, coarse, fine in ((32.0, 256, 512), (64.0, 512, 1024)):
            pair = [row for row in rows if row.get("cap") == cap and row.get("R") == R and row.get("N") in (coarse, fine)]
            pair.sort(key=lambda row: row.get("N", 0))
            checks = []
            if len(pair) == 2:
                for key in ("B", "L_star"):
                    ok, err = close_value(pair[0].get(key), pair[1].get(key), 0.02, 1e-10)
                    checks.append({"quantity": key, "pass": ok, "normalized_error": err})
            refinements.append({"cap": cap, "R": R, "coarse_N": coarse, "fine_N": fine, "checks": checks, "pass": bool(checks) and all(item["pass"] for item in checks)})
        pair = [row for row in rows if row.get("cap") == cap and (row.get("R"), row.get("N")) in ((32.0, 512), (64.0, 1024))]
        pair.sort(key=lambda row: row.get("R", 0))
        checks = []
        if len(pair) == 2:
            for key in ("B", "L_star"):
                ok, err = close_value(pair[0].get(key), pair[1].get(key), 0.02, 1e-10)
                checks.append({"quantity": key, "pass": ok, "normalized_error": err})
        domains.append({"cap": cap, "checks": checks, "pass": bool(checks) and all(item["pass"] for item in checks)})
    return refinements, domains


def calculate(manifest_path: Path, primary_dir: Path, output: Path) -> dict[str, Any]:
    manifest = verify_manifest(manifest_path)
    parents = parent_acceptance(manifest)
    primary_summary = strict_json(primary_dir / "summary.json")
    if primary_summary.get("schema") != PRIMARY_SCHEMA or primary_summary.get("complete_physical_matter_formation") is not False:
        raise ValueError("primary axial-energy summary identity is not accepted")
    primary_rows = primary_summary.get("rows")
    if not isinstance(primary_rows, list) or len(primary_rows) != 8:
        raise ValueError("primary axial-energy summary must contain exactly eight rows")
    primary_by_key: dict[tuple[str, int, float, int], dict[str, Any]] = {}
    for row in primary_rows:
        if not isinstance(row, dict):
            raise ValueError("malformed primary axial-energy row")
        key = (row.get("cap"), int(row.get("n", -1)), float(row.get("R", -1)), int(row.get("N", -1)))
        if key in primary_by_key:
            raise ValueError(f"duplicate primary row: {key}")
        primary_by_key[key] = row
    loaded_rows = parents["loaded_rows"]
    response_rows = parents["response_rows"]
    records = manifest["inputs"]
    rows: list[dict[str, Any]] = []
    for record in records:
        key = (record["cap"], 64, float(record["R"]), int(record["N"]))
        parent_row = primary_by_key.get(key)
        if parent_row is None:
            raise ValueError(f"primary row missing: {key}")
        loaded_row = loaded_rows.get((record["cap"], 64, float(record["R"]), int(record["N"])))
        response_row = response_rows.get((record["cap"], 64, float(record["R"]), int(record["N"])))
        expected_profile = ROOT / "runs/20260908_matter_formation_vortex_loaded/primary" / str(loaded_row.get("npz")) if loaded_row is not None else None
        expected_response = ROOT / "runs/20260908_matter_formation_vortex_compressibility/primary" / str(response_row.get("npz")) if response_row is not None else None
        if loaded_row is None or response_row is None or int(record["epsilon"]) != int(loaded_row.get("epsilon", 0)) or int(record["epsilon"]) != int(response_row.get("epsilon", 0)) or record["path"].resolve() != expected_profile.resolve() or record["response_path"].resolve() != expected_response.resolve():
            raise ValueError(f"manifest input is not bound to exact parent rows: {key}")
        rows.append(verify_row(record, parent_row, primary_dir, output))
    refinements, domains = refinement_checks(rows)
    all_rows = all(row.get("qualified") is True and row.get("exception") is None and len(row.get("trials", [])) == 24 and not row.get("failures") for row in rows)
    all_checks = primary_summary.get("numerical_pass") is True and all_rows and all(item["pass"] for item in refinements) and all(item["pass"] for item in domains)
    slow = [trial.get("Q") for row in rows for trial in row.get("trials", []) if trial.get("wave_factor") == 0.5]
    fast = [trial.get("Q") for row in rows for trial in row.get("trials", []) if trial.get("wave_factor") == 2.0]
    slow_ok = bool(slow) and all(finite(q) and float(q) < -1e-6 for q in slow)
    fast_ok = bool(fast) and all(finite(q) and float(q) > 1e-6 for q in fast)
    verdict = CONTRADICTS if all_checks and slow_ok and fast_ok else (NO_EMERGENCE if all_checks else INCONCLUSIVE)
    failures = [f"{row.get('cap')}-R{row.get('R')}-N{row.get('N')}:{name}" for row in rows for name in row.get("failures", [])]
    if primary_summary.get("numerical_pass") is not True:
        failures.append("primary_numerical_qualification")
    failures.extend(f"refinement:{index}" for index, item in enumerate(refinements) if not item["pass"])
    failures.extend(f"domain:{index}" for index, item in enumerate(domains) if not item["pass"])
    return {"schema": SCHEMA, "manifest": manifest, "parents": {"loaded_primary_schema": parents["loaded_primary"].get("schema"), "response_primary_schema": parents["response_primary"].get("schema"), "response_verification_verdict": parents["response_verification"].get("verdict")}, "rows": rows, "refinements": refinements, "domains": domains, "failures": failures, "numerical_pass": bool(all_checks), "verdict": verdict, "slow_wave_Q_all_negative": slow_ok, "fast_wave_control_Q_all_positive": fast_ok, "platform": platform.platform(), "complete_physical_matter_formation": False, "scope": "Independent finite-period energy adjudication for the eight qualified n=64 profiles; section 47 remains INCONCLUSIVE."}

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    created = False
    try:
        output.mkdir(parents=True, exist_ok=False)
        created = True
        result = calculate(args.manifest.resolve(), args.input.resolve(), output)
        (output / "verification.json").write_text(json.dumps(jsonable(result), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"schema": SCHEMA, "numerical_pass": result["numerical_pass"], "verdict": result["verdict"], "complete_physical_matter_formation": False}, sort_keys=True, allow_nan=False))
        return 0 if result["numerical_pass"] else 1
    except Exception as exc:
        receipt = {"schema": SCHEMA, "numerical_pass": False, "verdict": INCONCLUSIVE, "complete_physical_matter_formation": False, "error": f"{type(exc).__name__}: {exc}"}
        if created:
            try:
                (output / "verification.json").write_text(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
            except OSError:
                pass
        print(json.dumps(receipt, sort_keys=True, allow_nan=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
