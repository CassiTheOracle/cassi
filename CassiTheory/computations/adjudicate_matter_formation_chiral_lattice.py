#!/usr/bin/env python3
"""Fail-closed adjudication of the frozen §32.3 chiral-lattice first schedule.

This program reconciles the retained primary and independent receipts.  It
never imports the primary solver, runs no trajectory, and never mutates input
receipts or arrays.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.interpolate import CubicHermiteSpline, CubicSpline

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO_ROOT / "runs" / "20260907_matter_formation_chiral_lattice" / "execution_cpu1"
REPORT = REPO_ROOT / "computations" / "matter-formation-continuum-report.md"
SOLVER = REPO_ROOT / "computations" / "matter_formation_chiral_lattice.py"
VERIFIER = REPO_ROOT / "computations" / "verify_matter_formation_chiral_lattice.py"
STRUCTURE = REPO_ROOT / "computations" / "matter_formation_chiral_lattice_structure.py"
PROTOCOL_SHA256 = "2dd27b5947ce9a7d34cd0bf2bb84527ef610038376d6a2d9be5600db121242a7"
PRIMARY_SCHEMA = "matter-formation-chiral-lattice-v1"
VERIFICATION_SCHEMA = "matter-formation-chiral-lattice-verification-v1"
STRUCTURE_SCHEMA = "matter-formation-chiral-lattice-structure-v1"
SCHEMA = "matter-formation-chiral-lattice-adjudication-v1"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
MU = 0.5266577616452649
KAPPA = 1.0
P_PRIMITIVE = 2.0
PI = math.pi

ARMS: dict[str, dict[str, Any]] = {
    "vacuum": {"mode": "vacuum", "N": 16, "L": 18.0, "dt": 0.002, "T": 0.2, "speed": 2.0},
    "impulse_N32": {"mode": "impulse", "N": 32, "L": 18.0, "dt": 0.002, "T": 4.0, "speed": 2.0},
    "impulse_N48": {"mode": "impulse", "N": 48, "L": 18.0, "dt": 0.002, "T": 4.0, "speed": 2.0},
    "impulse_N64": {"mode": "impulse", "N": 64, "L": 18.0, "dt": 0.002, "T": 4.0, "speed": 2.0},
    "impulse_N48_halfdt": {"mode": "impulse", "N": 48, "L": 18.0, "dt": 0.001, "T": 4.0, "speed": 2.0},
    "prepared_N48": {"mode": "prepared", "N": 48, "L": 18.0, "dt": 0.002, "T": 4.0, "speed": 2.0},
}


class AdjudicationError(RuntimeError):
    """A missing, corrupt, or contract-incompatible evidence receipt."""


def raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def finite(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return safe(value.item())
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(safe(payload), indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def prepare_output(path: Path) -> None:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise AdjudicationError(f"--output must name a fresh or empty directory: {path}")
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AdjudicationError(f"missing JSON receipt: {repo_rel(path)}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AdjudicationError(f"corrupt JSON receipt {repo_rel(path)}: {exc}") from exc
    if not isinstance(value, dict):
        raise AdjudicationError(f"JSON receipt is not an object: {repo_rel(path)}")
    return value


def protocol_sha256() -> str:
    if not REPORT.is_file():
        raise AdjudicationError(f"missing protocol: {repo_rel(REPORT)}")
    text = canonical_bytes(REPORT).decode("utf-8")
    start_marker = "<!-- chiral-lattice-protocol:start -->"
    end_marker = "<!-- chiral-lattice-protocol:end -->"
    start = text.find(start_marker)
    if start < 0:
        raise AdjudicationError("protocol start marker missing")
    start += len(start_marker)
    end = text.find(end_marker, start)
    if end < 0 or text.find(start_marker, start) >= 0:
        raise AdjudicationError("protocol markers are missing or duplicated")
    return hashlib.sha256(text[start:end].encode("utf-8")).hexdigest()


def same_path(value: Any, expected: Path) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        return candidate.resolve() == expected.resolve()
    except (OSError, ValueError):
        return False


def primitive_basis(nsites: int, length: float) -> np.ndarray:
    a0 = np.asarray(((0.5, 1.0 / (2.0 * PHI), 0.0), (0.5, 0.0, P_PRIMITIVE / 2.0), (0.0, 1.0 / (2.0 * PHI), P_PRIMITIVE / 2.0)), dtype=np.float64).T
    return (float(length) / float(nsites)) * a0


def npz_path(base: Path, name: Any) -> Path:
    if not isinstance(name, str) or not name or not name.lower().endswith(".npz"):
        raise AdjudicationError(f"invalid NPZ artifact name in {repo_rel(base)}: {name!r}")
    candidate = Path(name)
    path = candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError as exc:
        raise AdjudicationError(f"NPZ artifact escapes receipt directory: {name}") from exc
    if not path.is_file():
        raise AdjudicationError(f"missing NPZ artifact: {repo_rel(path)}")
    return path


def collect_npz_refs(value: Any, base: Path, refs: dict[Path, dict[str, Any]], where: str) -> None:
    if isinstance(value, dict):
        name = value.get("file")
        if isinstance(name, str) and name.lower().endswith(".npz"):
            path = npz_path(base, name)
            declared = value.get("sha256")
            if not isinstance(declared, str):
                raise AdjudicationError(f"missing NPZ hash at {where}")
            actual = raw_sha256(path)
            if declared != actual:
                raise AdjudicationError(f"NPZ hash mismatch at {where}: {repo_rel(path)}")
            previous = refs.get(path)
            if previous is not None and previous["sha256"] != declared:
                raise AdjudicationError(f"conflicting NPZ hashes for {repo_rel(path)}")
            refs[path] = {"path": repo_rel(path), "sha256": actual, "where": where}
        for key, child in value.items():
            collect_npz_refs(child, base, refs, f"{where}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            collect_npz_refs(child, base, refs, f"{where}[{index}]")


def array_hashes(path: Path) -> dict[str, Any]:
    try:
        with np.load(path, allow_pickle=False) as loaded:
            result: dict[str, Any] = {}
            for key in loaded.files:
                array = np.asarray(loaded[key])
                if array.dtype.hasobject:
                    raise AdjudicationError(f"object array is forbidden in {repo_rel(path)}:{key}")
                contiguous = np.ascontiguousarray(array)
                result[key] = {"shape": list(array.shape), "dtype": str(array.dtype), "sha256": hashlib.sha256(contiguous.tobytes(order="C")).hexdigest()}
            return result
    except AdjudicationError:
        raise
    except Exception as exc:
        raise AdjudicationError(f"corrupt NPZ {repo_rel(path)}: {exc}") from exc


def check_row(checks: list[dict[str, Any]], name: str, passed: bool, measured: Any = None, threshold: Any = None, **extra: Any) -> None:
    row: dict[str, Any] = {"name": name, "pass": bool(passed)}
    if measured is not None:
        row["measured"] = safe(measured)
    if threshold is not None:
        row["threshold"] = safe(threshold)
    row.update(safe(extra))
    checks.append(row)


def close_scalar(a: Any, b: Any, tolerance: float = 1.0e-12) -> bool:
    return finite(a) and finite(b) and abs(float(a) - float(b)) <= tolerance * max(1.0, abs(float(a)), abs(float(b)))


def resolve_record_npz(base: Path, snapshot: dict[str, Any]) -> Path:
    return npz_path(base, snapshot.get("file"))


def delta(field: np.ndarray, axis: int, kind: str) -> np.ndarray:
    if kind == "plus":
        return np.roll(field, -1, axis=axis + 1) - field
    if kind == "minus":
        return field - np.roll(field, 1, axis=axis + 1)
    if kind == "central":
        return 0.5 * (np.roll(field, -1, axis=axis + 1) - np.roll(field, 1, axis=axis + 1))
    raise ValueError(kind)


def physical_gradient(field: np.ndarray, basis: np.ndarray, kind: str) -> np.ndarray:
    inv = np.linalg.inv(np.asarray(basis, dtype=np.float64))
    differences = np.stack([delta(field, axis, kind) for axis in range(3)], axis=1)
    return np.einsum("ia,ci...->ca...", inv, differences, optimize=True)


def raw_observables(data: dict[str, np.ndarray], mu: float, kappa: float, t: float) -> dict[str, Any]:
    n, pfield, basis = data["n"], data["p"], data["basis"]
    if n.ndim != 4 or n.shape[0] != 4 or pfield.shape != n.shape or basis.shape != (3, 3):
        raise AdjudicationError("invalid n/p/basis NPZ shape")
    if not (np.all(np.isfinite(n)) and np.all(np.isfinite(pfield)) and np.all(np.isfinite(basis))):
        raise AdjudicationError("non-finite n/p/basis NPZ array")
    c = physical_gradient(n, basis, "central")
    d = c - n[:, None] * np.sum(n[:, None] * c, axis=0, keepdims=True)
    s = np.sum(d * d, axis=(0, 1))
    matrix = np.broadcast_to(np.eye(4, dtype=np.float64), s.shape + (4, 4)).copy()
    matrix *= (1.0 + kappa * s)[..., None, None]
    for axis in range(3):
        da = d[:, axis]
        matrix -= kappa * np.einsum("i...,j...->...ij", da, da, optimize=True)
    p_last = np.moveaxis(pfield, 0, -1)
    velocity = np.moveaxis(np.linalg.solve(matrix, p_last[..., None])[..., 0], -1, 0)
    kinetic = 0.5 * np.sum(pfield * velocity, axis=0)
    forward, backward = physical_gradient(n, basis, "plus"), physical_gradient(n, basis, "minus")
    e2 = 0.25 * (np.sum(forward * forward, axis=(0, 1)) + np.sum(backward * backward, axis=(0, 1)))
    e4 = np.zeros_like(e2)
    for a in range(3):
        for b in range(a + 1, 3):
            da, db = d[:, a], d[:, b]
            e4 += 0.5 * kappa * (np.sum(da * da, axis=0) * np.sum(db * db, axis=0) - np.sum(da * db, axis=0) ** 2)
    potential = mu * mu * (1.0 - n[0])
    density = np.linalg.det(np.moveaxis(np.stack([n, d[:, 0], d[:, 1], d[:, 2]], axis=-1), 0, -2)) / (2.0 * PI * PI)
    volume = abs(float(np.linalg.det(basis)))
    edge_angle = 0.0
    for axis in range(3):
        dot = np.sum(n * np.roll(n, -1, axis=axis + 1), axis=0)
        edge_angle = max(edge_angle, float(np.arccos(np.clip(dot, -1.0, 1.0)).max()))
    torque_density = np.cross(n[1:], pfield[1:], axisa=0, axisb=0, axisc=0)
    energy_parts = [volume * float(piece.sum()) for piece in (kinetic, e2, e4, potential)]
    return {
        "t": float(t), "energy": sum(energy_parts), "kinetic": energy_parts[0], "e2": energy_parts[1], "e4": energy_parts[2], "potential": energy_parts[3],
        "B": volume * float(density.sum()), "Bpos": volume * float(np.maximum(density, 0.0).sum()), "Bneg": volume * float(np.maximum(-density, 0.0).sum()),
        "unit_error": float(np.max(np.abs(np.sum(n * n, axis=0) - 1.0))), "tangent_error": float(np.max(np.abs(np.sum(n * pfield, axis=0)))),
        "edge_angle_max": float(edge_angle), "torque": [float(x) for x in volume * np.sum(torque_density, axis=(1, 2, 3))],
    }


def validate_source_entries(entries: Any, expected: dict[str, Path], checks: list[dict[str, Any]], prefix: str, canonical: bool = False) -> None:
    if not isinstance(entries, dict):
        raise AdjudicationError(f"{prefix} source entries are missing")
    for rel, path in expected.items():
        declared = entries.get(rel)
        actual = canonical_sha256(path) if canonical else raw_sha256(path)
        check_row(checks, f"{prefix}.source.{rel}", declared == actual, declared, actual, path=repo_rel(path))
        if declared != actual:
            raise AdjudicationError(f"{prefix} source hash mismatch: {rel}")


def validate_primary_and_verifier(name: str, root: Path, spec: dict[str, Any], checks: list[dict[str, Any]], refs: dict[Path, dict[str, Any]], scalar_hashes: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any], Path, Path, list[dict[str, Any]]]:
    primary_path = root / name / "results.json"
    verification_path = root / f"{name}_verified" / "verification.json"
    primary = load_json(primary_path)
    verification = load_json(verification_path)
    scalar_hashes[f"{name}.primary"] = raw_sha256(primary_path)
    scalar_hashes[f"{name}.verification"] = raw_sha256(verification_path)
    check_row(checks, f"{name}.primary_schema", primary.get("schema") == PRIMARY_SCHEMA, primary.get("schema"), PRIMARY_SCHEMA)
    check_row(checks, f"{name}.verification_schema", verification.get("schema") == VERIFICATION_SCHEMA, verification.get("schema"), VERIFICATION_SCHEMA)
    if primary.get("schema") != PRIMARY_SCHEMA or verification.get("schema") != VERIFICATION_SCHEMA:
        raise AdjudicationError(f"{name}: wrong receipt schema")
    params = primary.get("parameters")
    if not isinstance(params, dict):
        raise AdjudicationError(f"{name}: parameters missing")
    parameter_ok = primary.get("mode") == spec["mode"] and all(close_scalar(params.get(key), spec[key]) for key in ("N", "L", "dt", "T", "speed")) and close_scalar(params.get("mu"), MU, 1.0e-14) and close_scalar(params.get("kappa"), KAPPA, 1.0e-14) and close_scalar(params.get("p_parallel"), P_PRIMITIVE, 1.0e-14)
    check_row(checks, f"{name}.parameters", parameter_ok, {"mode": primary.get("mode"), **params}, spec)
    if not parameter_ok:
        raise AdjudicationError(f"{name}: parameters do not match frozen schedule")
    check_row(checks, f"{name}.completed", primary.get("completed") is True and primary.get("scientific_execution_started") is True, {"completed": primary.get("completed"), "scientific_execution_started": primary.get("scientific_execution_started")}, True)
    if primary.get("completed") is not True or primary.get("scientific_execution_started") is not True:
        raise AdjudicationError(f"{name}: primary execution is not complete")
    protocol_ok = primary.get("protocol_file") == repo_rel(REPORT) and primary.get("protocol_sha256") == PROTOCOL_SHA256
    check_row(checks, f"{name}.primary_protocol_identity", protocol_ok, {"path": primary.get("protocol_file"), "sha256": primary.get("protocol_sha256")}, {"path": repo_rel(REPORT), "sha256": PROTOCOL_SHA256})
    if not protocol_ok:
        raise AdjudicationError(f"{name}: primary protocol identity mismatch")
    expected_sources = {repo_rel(SOLVER): SOLVER, repo_rel(VERIFIER): VERIFIER, repo_rel(STRUCTURE): STRUCTURE}
    source_ok = primary.get("source_file") == repo_rel(SOLVER) and primary.get("primary_source") == repo_rel(SOLVER) and primary.get("source_sha256") == raw_sha256(SOLVER)
    check_row(checks, f"{name}.primary_source_identity", source_ok, {"source_file": primary.get("source_file"), "source_sha256": primary.get("source_sha256")}, {"source_file": repo_rel(SOLVER), "source_sha256": raw_sha256(SOLVER)})
    if not source_ok:
        raise AdjudicationError(f"{name}: primary source identity mismatch")
    validate_source_entries(primary.get("sources"), expected_sources, checks, name)
    verifier_identity = verification.get("source_identity")
    verifier_artifacts = verification.get("artifact_identity")
    verifier_primary_ok = same_path(verification.get("primary"), primary_path)
    verifier_source_ok = isinstance(verifier_identity, dict) and same_path(verifier_identity.get("path"), SOLVER) and verifier_identity.get("sha256") == raw_sha256(SOLVER)
    primary_binding_ok = isinstance(verifier_artifacts, dict) and verifier_artifacts.get("primary_results_sha256") == raw_sha256(primary_path)
    verifier_hash_ok = isinstance(verifier_artifacts, dict) and verifier_artifacts.get("verifier_sha256") == raw_sha256(VERIFIER)
    check_row(checks, f"{name}.verification_primary_path", verifier_primary_ok, verification.get("primary"), repo_rel(primary_path))
    check_row(checks, f"{name}.verification_source_identity", verifier_source_ok, verifier_identity, {"path": repo_rel(SOLVER), "sha256": raw_sha256(SOLVER)})
    check_row(checks, f"{name}.verification_primary_binding", primary_binding_ok, verifier_artifacts.get("primary_results_sha256") if isinstance(verifier_artifacts, dict) else None, raw_sha256(primary_path))
    check_row(checks, f"{name}.verification_source_binding", verifier_hash_ok, verifier_artifacts.get("verifier_sha256") if isinstance(verifier_artifacts, dict) else None, raw_sha256(VERIFIER))
    if not (verifier_primary_ok and verifier_source_ok and primary_binding_ok and verifier_hash_ok):
        raise AdjudicationError(f"{name}: verifier identity binding mismatch")
    verification_checks = verification.get("checks")
    all_checks_pass = isinstance(verification_checks, list) and bool(verification_checks) and all(isinstance(row, dict) and row.get("pass") is True for row in verification_checks)
    all_pass = verification.get("all_pass") is True and verification.get("failures") == [] and all_checks_pass
    check_row(checks, f"{name}.verification_all_pass", all_pass, {"all_pass": verification.get("all_pass"), "failures": verification.get("failures")}, True)
    if not all_pass:
        raise AdjudicationError(f"{name}: independent verification is not all_pass")
    snapshots, records = primary.get("snapshots"), primary.get("records")
    expected_count = 2 if name == "vacuum" else 9
    expected_times = [0.0, 0.2] if name == "vacuum" else [0.5 * i for i in range(9)]
    schedule_ok = isinstance(snapshots, list) and isinstance(records, list) and len(snapshots) == len(records) == expected_count
    if schedule_ok:
        for index, expected_time in enumerate(expected_times):
            schedule_ok = schedule_ok and isinstance(snapshots[index], dict) and close_scalar(snapshots[index].get("t"), expected_time, 1.0e-12) and isinstance(records[index], dict) and close_scalar(records[index].get("t"), expected_time, 1.0e-12)
    check_row(checks, f"{name}.completed_schedule", schedule_ok, {"snapshot_count": len(snapshots) if isinstance(snapshots, list) else None, "times": [row.get("t") for row in snapshots] if isinstance(snapshots, list) else None}, {"count": expected_count, "times": expected_times})
    if not schedule_ok:
        raise AdjudicationError(f"{name}: completed schedule samples are missing or wrong")
    collect_npz_refs(primary, primary_path.parent, refs, f"{name}.primary")
    return primary, verification, primary_path, primary_path.parent, records
def validate_controls(root: Path, checks: list[dict[str, Any]], refs: dict[Path, dict[str, Any]], scalar_hashes: dict[str, str]) -> None:
    primary_path = root / "controls" / "results.json"
    verification_path = root / "controls_verified" / "verification.json"
    primary = load_json(primary_path)
    verification = load_json(verification_path)
    scalar_hashes["controls.primary"] = raw_sha256(primary_path)
    scalar_hashes["controls.verification"] = raw_sha256(verification_path)
    schema_ok = primary.get("schema") == PRIMARY_SCHEMA and verification.get("schema") == VERIFICATION_SCHEMA
    check_row(checks, "controls.schemas", schema_ok, {"primary": primary.get("schema"), "verification": verification.get("schema")}, {"primary": PRIMARY_SCHEMA, "verification": VERIFICATION_SCHEMA})
    params = primary.get("parameters")
    expected = {"mode": "controls", "N": 6, "L": 6.0, "dt": 0.001, "T": 0.02, "speed": 2.0}
    parameters_ok = isinstance(params, dict) and primary.get("mode") == "controls" and all(close_scalar(params.get(key), value) for key, value in expected.items() if key != "mode") and close_scalar(params.get("mu"), MU, 1.0e-14) and close_scalar(params.get("kappa"), KAPPA, 1.0e-14) and close_scalar(params.get("p_parallel"), P_PRIMITIVE, 1.0e-14)
    check_row(checks, "controls.parameters", parameters_ok, {"mode": primary.get("mode"), **(params if isinstance(params, dict) else {})}, expected)
    complete_ok = primary.get("completed") is True and primary.get("scientific_execution_started") is False
    check_row(checks, "controls.completed", complete_ok, {"completed": primary.get("completed"), "scientific_execution_started": primary.get("scientific_execution_started")}, {"completed": True, "scientific_execution_started": False})
    protocol_ok = primary.get("protocol_file") == repo_rel(REPORT) and primary.get("protocol_sha256") == PROTOCOL_SHA256
    check_row(checks, "controls.primary_protocol_identity", protocol_ok, {"path": primary.get("protocol_file"), "sha256": primary.get("protocol_sha256")}, {"path": repo_rel(REPORT), "sha256": PROTOCOL_SHA256})
    expected_sources = {repo_rel(SOLVER): SOLVER, repo_rel(VERIFIER): VERIFIER, repo_rel(STRUCTURE): STRUCTURE}
    source_ok = primary.get("source_file") == repo_rel(SOLVER) and primary.get("primary_source") == repo_rel(SOLVER) and primary.get("source_sha256") == raw_sha256(SOLVER)
    check_row(checks, "controls.primary_source_identity", source_ok, {"source_file": primary.get("source_file"), "source_sha256": primary.get("source_sha256")}, {"source_file": repo_rel(SOLVER), "source_sha256": raw_sha256(SOLVER)})
    if not (schema_ok and parameters_ok and complete_ok and protocol_ok and source_ok):
        raise AdjudicationError("controls receipt does not match frozen control")
    validate_source_entries(primary.get("sources"), expected_sources, checks, "controls")
    identity, artifacts = verification.get("source_identity"), verification.get("artifact_identity")
    verifier_primary_ok = same_path(verification.get("primary"), primary_path)
    verifier_source_ok = isinstance(identity, dict) and same_path(identity.get("path"), SOLVER) and identity.get("sha256") == raw_sha256(SOLVER)
    primary_binding_ok = isinstance(artifacts, dict) and artifacts.get("primary_results_sha256") == raw_sha256(primary_path)
    verifier_hash_ok = isinstance(artifacts, dict) and artifacts.get("verifier_sha256") == raw_sha256(VERIFIER)
    check_row(checks, "controls.verification_primary_path", verifier_primary_ok, verification.get("primary"), repo_rel(primary_path))
    check_row(checks, "controls.verification_source_identity", verifier_source_ok, identity, {"path": repo_rel(SOLVER), "sha256": raw_sha256(SOLVER)})
    check_row(checks, "controls.verification_primary_binding", primary_binding_ok, artifacts.get("primary_results_sha256") if isinstance(artifacts, dict) else None, raw_sha256(primary_path))
    check_row(checks, "controls.verification_source_binding", verifier_hash_ok, artifacts.get("verifier_sha256") if isinstance(artifacts, dict) else None, raw_sha256(VERIFIER))
    verification_checks = verification.get("checks")
    all_pass = verification.get("all_pass") is True and verification.get("failures") == [] and isinstance(verification_checks, list) and bool(verification_checks) and all(isinstance(row, dict) and row.get("pass") is True for row in verification_checks)
    check_row(checks, "controls.verification_all_pass", all_pass, {"all_pass": verification.get("all_pass"), "failures": verification.get("failures")}, True)
    if not (verifier_primary_ok and verifier_source_ok and primary_binding_ok and verifier_hash_ok and all_pass):
        raise AdjudicationError("controls independent verification is not all_pass or identity-bound")
    snapshots, records = primary.get("snapshots"), primary.get("records")
    expected_times = (0.0, 0.02)
    schedule_ok = isinstance(snapshots, list) and isinstance(records, list) and len(snapshots) == len(records) == 2 and all(isinstance(snapshots[index], dict) and isinstance(records[index], dict) and close_scalar(snapshots[index].get("t"), expected_times[index], 1.0e-12) and close_scalar(records[index].get("t"), expected_times[index], 1.0e-12) for index in range(2))
    check_row(checks, "controls.completed_schedule", schedule_ok, {"snapshot_count": len(snapshots) if isinstance(snapshots, list) else None, "times": [row.get("t") for row in snapshots] if isinstance(snapshots, list) else None}, {"count": 2, "times": list(expected_times)})
    if not schedule_ok:
        raise AdjudicationError("controls schedule samples are missing or wrong")
    collect_npz_refs(primary, primary_path.parent, refs, "controls.primary")
    checkerboard = primary.get("checkerboard")
    basis = primitive_basis(6, 6.0)
    expected_edge = 2.0 * math.sin(0.4) ** 2 * float(np.linalg.norm(np.linalg.inv(basis)[0]) ** 2) * abs(float(np.linalg.det(basis))) * 6 ** 3
    checker_ok = isinstance(checkerboard, dict) and close_scalar(checkerboard.get("angle"), 0.4) and close_scalar(checkerboard.get("central_e2"), 0.0) and close_scalar(checkerboard.get("edge_e2"), expected_edge, 1.0e-9)
    check_row(checks, "controls.checkerboard_energies", checker_ok, checkerboard, {"central_e2": 0.0, "edge_e2": expected_edge})


def raw_formation(data: dict[str, np.ndarray]) -> dict[str, Any]:
    """Reconstruct endpoint centroids and localization from one raw state."""
    if not {"n", "p", "basis"}.issubset(data):
        raise AdjudicationError("formation reconstruction requires n, p, and basis arrays")
    n, basis = data["n"], data["basis"]
    if n.ndim != 4 or n.shape[0] != 4 or basis.shape != (3, 3):
        raise AdjudicationError("invalid formation reconstruction shape")
    if not (np.all(np.isfinite(n)) and np.all(np.isfinite(basis))):
        raise AdjudicationError("non-finite formation reconstruction input")
    central = physical_gradient(n, basis, "central")
    d = central - n[:, None] * np.sum(n[:, None] * central, axis=0, keepdims=True)
    density = np.linalg.det(np.moveaxis(np.stack([n, d[:, 0], d[:, 1], d[:, 2]], axis=-1), 0, -2)) / (2.0 * PI * PI)
    volume = abs(float(np.linalg.det(basis)))
    if not finite(volume) or volume <= 0.0 or not np.all(np.isfinite(density)):
        raise AdjudicationError("invalid formation density or site volume")
    nsites = n.shape[1]
    index = np.arange(nsites, dtype=np.float64) - nsites / 2.0 + 0.5
    index_grid = np.stack(np.meshgrid(index, index, index, indexing="ij"))
    centres: list[list[float]] = []
    fractions: list[float] = []
    for sign_density in (np.maximum(density, 0.0), np.maximum(-density, 0.0)):
        total = float(sign_density.sum())
        if not finite(total):
            raise AdjudicationError("non-finite endpoint density integral")
        if total <= 1.0e-30:
            centres.append([0.0, 0.0, 0.0])
            fractions.append(0.0)
            continue
        angles = 2.0 * PI * index_grid / float(nsites)
        zreal = (np.cos(angles) * sign_density[None]).sum(axis=(1, 2, 3))
        zimag = (np.sin(angles) * sign_density[None]).sum(axis=(1, 2, 3))
        centre_index = np.arctan2(zimag, zreal) * float(nsites) / (2.0 * PI)
        delta_index = index_grid - centre_index[:, None, None, None]
        delta_index -= float(nsites) * np.round(delta_index / float(nsites))
        physical = np.einsum("ai,ixyz->axyz", basis, delta_index)
        radius = np.linalg.norm(physical, axis=0)
        fraction = float(sign_density[radius <= 2.0].sum()) / total
        centre = basis @ centre_index
        if not (np.all(np.isfinite(centre)) and finite(fraction)):
            raise AdjudicationError("non-finite endpoint centroid or local fraction")
        centres.append([float(value) for value in centre])
        fractions.append(fraction)
    delta_centres = np.linalg.solve(basis, np.asarray(centres[0]) - np.asarray(centres[1]))
    delta_centres -= float(nsites) * np.round(delta_centres / float(nsites))
    separation = float(np.linalg.norm(basis @ delta_centres))
    if not finite(separation):
        raise AdjudicationError("non-finite endpoint centroid separation")
    return {"centres": centres, "separation": separation, "local_fractions": fractions}


def reconstruct_radial_profiles(root: Path, structure: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    """Use composite Gauss quadrature on the two independently solved profiles."""
    nodes, weights = np.polynomial.legendre.leggauss(8)
    for label, relative in (
        ("structure", "structure_recovery1/massive_profile.npz"),
        ("primary", "impulse_N32/radial_profile.npz"),
    ):
        with np.load(root / relative, allow_pickle=False) as data:
            radius = data["r"] if "r" in data else data["R"]
            field = data["F"]
            spline = CubicHermiteSpline(radius, field, data["Fp"]) if "Fp" in data else CubicSpline(radius, field)
        edges = np.unique(np.r_[0.0, radius])
        half_width = (edges[1:, None] - edges[:-1, None]) / 2.0
        r = (edges[1:, None] + edges[:-1, None]) / 2.0 + half_width * nodes
        quadrature_weights = half_width * weights
        f, fp = spline(r), spline(r, 1)
        sine, sine2 = np.sin(f), np.sin(2.0 * f)

        def integral(value: np.ndarray) -> float:
            return float(np.sum(quadrature_weights * value))

        e2 = 4.0 * PI * integral(r * r * fp * fp + 2.0 * sine * sine)
        e4 = 4.0 * PI * integral(2.0 * sine * sine * fp * fp + sine ** 4 / r ** 2)
        em = 8.0 * PI * MU ** 2 * integral(r * r * (1.0 - np.cos(f)))
        energy = e2 + e4 + em
        degree = -2.0 / PI * integral(fp * sine * sine)
        # Lambda includes the inherited factor 8; E_radial is twice H_primary.
        inertia = 8.0 * integral(r * r * sine * sine * (1.0 + fp * fp + sine * sine / r ** 2))
        axial = 4.0 * integral(r * r * fp + r * sine2 + sine * sine * sine2 / r + 2.0 * sine * sine * fp + r * fp * fp * sine2)
        scale = ((5.0 * 938.918754 - 1232.0) / 4.0) / (energy / 2.0)
        e_b = (2.0 * PI * inertia * (1232.0 - 938.918754) / (9.0 * scale)) ** 0.25
        f_b = scale * e_b
        calibration = structure["massive_calibration"]
        comparisons = {
            "energy": (energy, structure["massive_static"]["energy_total"]),
            "degree": (degree, 1.0),
            "e_B": (e_b, calibration["e_B"]),
            "f_B": (f_b, calibration["f_B_MeV"]),
            "length_unit": (197.3269804 / (e_b * f_b), calibration["length_unit_fm"]),
            "g_A": (-PI * axial / (3.0 * e_b * e_b), structure["massive_observables"]["axial_coupling_g_A"]["value"]),
        }
        for name, (actual, expected) in comparisons.items():
            check_row(checks, f"radial_reconstruction.{label}.{name}", close_scalar(actual, expected, 1.0e-7), actual, expected, relative_tolerance=1.0e-7)
        virial = abs(e2 - e4 + 3.0 * em) / energy
        check_row(checks, f"radial_reconstruction.{label}.virial", finite(virial) and virial <= 1.0e-7, virial, 1.0e-7)




def validate_structure(root: Path, checks: list[dict[str, Any]], refs: dict[Path, dict[str, Any]], scalar_hashes: dict[str, str]) -> dict[str, Any]:
    structure_path = root / "structure_recovery1" / "results.json"
    failed_path = root / "structure" / "results.json"
    structure = load_json(structure_path)
    scalar_hashes["structure_recovery1"] = raw_sha256(structure_path)
    check_row(checks, "structure_recovery1.schema", structure.get("schema") == STRUCTURE_SCHEMA, structure.get("schema"), STRUCTURE_SCHEMA)
    check_row(checks, "structure_recovery1.verdict", structure.get("scientific_verdict") == "QUALIFIED_CONDITIONAL_STRUCTURE_ONLY", structure.get("scientific_verdict"), "QUALIFIED_CONDITIONAL_STRUCTURE_ONLY")
    if failed_path.is_file():
        failed = load_json(failed_path)
        scalar_hashes["structure"] = raw_sha256(failed_path)
        preserved = failed.get("schema") == STRUCTURE_SCHEMA and failed.get("scientific_verdict") == "INCONCLUSIVE" and failed.get("failure_type") == "NumericalFailure"
        check_row(checks, "structure.failed_receipt_preserved", preserved, {"schema": failed.get("schema"), "scientific_verdict": failed.get("scientific_verdict"), "failure_type": failed.get("failure_type")}, True)
    else:
        check_row(checks, "structure.failed_receipt_preserved", True, "not present in self-contained execution root", "optional preserved historical receipt")
    protocol_ok = structure.get("protocol_path") == repo_rel(REPORT) and structure.get("protocol_sha256") == PROTOCOL_SHA256
    check_row(checks, "structure_recovery1.protocol_identity", protocol_ok, {"path": structure.get("protocol_path"), "sha256": structure.get("protocol_sha256")}, {"path": repo_rel(REPORT), "sha256": PROTOCOL_SHA256})
    source_ok = structure.get("source_sha256") == raw_sha256(STRUCTURE)
    check_row(checks, "structure_recovery1.source_identity", source_ok, structure.get("source_sha256"), raw_sha256(STRUCTURE))
    provenance = structure.get("source_provenance")
    if isinstance(provenance, dict):
        for key, expected in (("conditional_baryon_script", REPO_ROOT / "computations" / "matter_formation_conditional_baryon.py"), ("conditional_baryon_prereg", REPO_ROOT / "computations" / "matter-formation-conditional-baryon-prereg.md")):
            row = provenance.get(key)
            declared_path = row.get("path") if isinstance(row, dict) else None
            declared_hash = row.get("canonical_text_sha256") if isinstance(row, dict) else None
            actual = canonical_sha256(expected)
            ok = declared_path == repo_rel(expected) and declared_hash == actual
            check_row(checks, f"structure_recovery1.provenance.{key}", ok, {"path": declared_path, "sha256": declared_hash}, {"path": repo_rel(expected), "sha256": actual})
            if not ok:
                raise AdjudicationError(f"structure provenance mismatch: {key}")
    else:
        raise AdjudicationError("structure source provenance missing")
    solver = structure.get("massive_bvp_solver")
    structural_checks = structure.get("checks")
    bvp_ok = isinstance(solver, dict) and solver.get("status") == 0 and isinstance(structural_checks, dict) and bool(structural_checks) and all(value is True for value in structural_checks.values())
    check_row(checks, "structure_recovery1.accepted_checks", bvp_ok, {"bvp_status": solver.get("status") if isinstance(solver, dict) else None, "checks": structural_checks}, True)
    if not (structure.get("schema") == STRUCTURE_SCHEMA and structure.get("scientific_verdict") == "QUALIFIED_CONDITIONAL_STRUCTURE_ONLY" and protocol_ok and source_ok and bvp_ok):
        raise AdjudicationError("accepted structure receipt is not valid")
    collect_npz_refs(structure, structure_path.parent, refs, "structure_recovery1")
    reconstruct_radial_profiles(root, structure, checks)
    return structure


def completion_ledger(first_verdict: str | None, first_schedule_passed: bool | None) -> list[dict[str, Any]]:
    evaluated = first_schedule_passed is not None
    return [
        {"requirement": 1, "name": "canonical microscopic action, coupling, and complete conserved stress", "status": "UNMET", "evidence": "This is an added O(4) chiral action; no canonical Cassi coupling or stress exchange is supplied."},
        {"requirement": 2, "name": "regulator-compatible quantum state selection", "status": "UNMET", "evidence": "The finite-site Q=(S^3)^Ns regulator is simply connected; no quantum state, density operator, renormalization, or odd FR character is selected."},
        {"requirement": 3, "name": "physical normalization with empirical inputs ledgered", "status": "MET_CONDITIONAL" if evaluated else "NOT_EVALUATED", "evidence": "mu is selected from the pion normalization and e_B/f_B are calibrated to nucleon/Delta targets; this is not a canonical Cassi normalization."},
        {"requirement": 4, "name": "infinite-domain existence and all-sector stability", "status": "PARTIAL" if evaluated else "NOT_EVALUATED", "evidence": "The recovered finite radial BVP supplies a stationary comparison profile; infinite-domain, nonradial, and all-sector stability remain open."},
        {"requirement": 5, "name": "physically normalized localized production and persistence", "status": "PARTIAL" if evaluated else "NOT_EVALUATED", "evidence": f"First-schedule formation verdict: {first_verdict or 'not evaluated'}. Extended persistence has not been run; a first-schedule pass only authorizes that continuation. No quantum production rate is calculated."},
        {"requirement": 6, "name": "derived particle identity, spin, statistics, and discriminators", "status": "UNMET", "evidence": "The finite-site topology enforces no integer degree or odd FR exchange character; all six target-bearing massive-model diagnostics miss their specified thresholds."},
    ]


def adjudicate(root: Path, output: Path) -> tuple[dict[str, Any], int]:
    checks: list[dict[str, Any]] = []
    refs: dict[Path, dict[str, Any]] = {}
    scalar_hashes: dict[str, str] = {}
    identity = {"path": repo_rel(Path(__file__)), "sha256": raw_sha256(Path(__file__))}
    actual_protocol = protocol_sha256()
    check_row(checks, "protocol.hash", actual_protocol == PROTOCOL_SHA256, actual_protocol, PROTOCOL_SHA256, path=repo_rel(REPORT), normalization="CRLF/CR converted to LF before UTF-8 hashing")
    if actual_protocol != PROTOCOL_SHA256:
        raise AdjudicationError("frozen protocol hash mismatch")
    primary_rows: dict[str, tuple[dict[str, Any], Path, Path, list[dict[str, Any]]]] = {}
    for name, spec in ARMS.items():
        primary, verification, primary_path, base, records = validate_primary_and_verifier(name, root, spec, checks, refs, scalar_hashes)
        primary_rows[name] = (primary, primary_path, base, records)
    validate_controls(root, checks, refs, scalar_hashes)
    structure = validate_structure(root, checks, refs, scalar_hashes)
    npz_arrays: dict[Path, dict[str, np.ndarray]] = {}
    array_hash_receipt: dict[str, Any] = {}
    for path, reference in refs.items():
        array_hash_receipt[reference["path"]] = {"raw_sha256": reference["sha256"], "where": reference["where"], "arrays": array_hashes(path)}
        with np.load(path, allow_pickle=False) as loaded:
            npz_arrays[path] = {key: np.asarray(loaded[key], dtype=np.float64) for key in loaded.files}
    endpoint_metrics: dict[str, dict[str, Any]] = {}
    energy_drifts: dict[str, float] = {}
    constraint_maxima: dict[str, dict[str, float]] = {}
    for name, (primary, _primary_path, base, records) in primary_rows.items():
        snapshots = primary["snapshots"]
        values: list[dict[str, Any]] = []
        for index, (snapshot, record) in enumerate(zip(snapshots, records)):
            path = resolve_record_npz(base, snapshot)
            data = npz_arrays[path]
            measured = raw_observables(data, MU, KAPPA, float(snapshot["t"]))
            for key in ("t", "energy", "B", "Bpos", "Bneg", "unit_error", "tangent_error", "edge_angle_max"):
                if not close_scalar(measured[key], record.get(key), 2.0e-9):
                    raise AdjudicationError(f"{name}: scalar metric mismatch at snapshot {index}: {key}")
            check_row(checks, f"{name}.snapshot[{index}].raw_metric_binding", True, {key: measured[key] for key in ("energy", "B", "Bpos", "Bneg", "unit_error", "tangent_error")}, 2.0e-9)
            values.append(measured)
        energy0 = values[0]["energy"]
        drift = max(abs(row["energy"] - energy0) for row in values) / max(1.0, abs(energy0))
        energy_drifts[name] = drift
        unit_max = max(row["unit_error"] for row in values)
        tangent_max = max(row["tangent_error"] for row in values)
        constraint_maxima[name] = {"unit_error": unit_max, "tangent_error": tangent_max}
        check_row(checks, f"{name}.energy_drift", drift <= 1.0e-4, drift, 1.0e-4)
        check_row(checks, f"{name}.unit_constraint", unit_max <= 1.0e-9, unit_max, 1.0e-9)
        check_row(checks, f"{name}.tangent_constraint", tangent_max <= 1.0e-9, tangent_max, 1.0e-9)
        if name in ("impulse_N48", "impulse_N64"):
            formation = raw_formation(npz_arrays[path])
            endpoint_metrics[name] = {
                "Bpos": values[-1]["Bpos"], "Bneg": values[-1]["Bneg"], "B": values[-1]["B"],
                "edge_angle_max": values[-1]["edge_angle_max"],
                "centres": formation["centres"], "separation": formation["separation"],
                "local_fractions": formation["local_fractions"],
                "primary_record_comparison": {
                    "centres": records[-1].get("centres"), "separation": records[-1].get("separation"),
                    "local_fractions": records[-1].get("local_fractions"),
                },
            }
    n48_primary, n48_path, n48_base, _n48_records = primary_rows["impulse_N48"]
    n48_half_primary, n48_half_path, n48_half_base, _n48_half_records = primary_rows["impulse_N48_halfdt"]
    n48_final = raw_observables(npz_arrays[resolve_record_npz(n48_base, n48_primary["snapshots"][-1])], MU, KAPPA, 4.0)
    n48_half_final = raw_observables(npz_arrays[resolve_record_npz(n48_half_base, n48_half_primary["snapshots"][-1])], MU, KAPPA, 4.0)
    for key in ("B", "Bpos", "Bneg"):
        pair_half = abs(n48_final[key] - n48_half_final[key])
        check_row(checks, f"time_step_pair.final_{key}_difference", pair_half <= 1.0e-4, pair_half, 1.0e-4)
    n48, n64 = endpoint_metrics["impulse_N48"], endpoint_metrics["impulse_N64"]
    bpos_diff, bneg_diff = abs(n48["Bpos"] - n64["Bpos"]), abs(n48["Bneg"] - n64["Bneg"])
    check_row(checks, "spatial_pair.final_Bpos_difference", bpos_diff <= 0.05, bpos_diff, 0.05)
    check_row(checks, "spatial_pair.final_Bneg_difference", bneg_diff <= 0.05, bneg_diff, 0.05)
    check_row(checks, "spatial_pair.N48_total_B", abs(n48["B"]) <= 0.05, n48["B"], 0.05)
    check_row(checks, "spatial_pair.N64_total_B", abs(n64["B"]) <= 0.05, n64["B"], 0.05)
    formation_pass = True
    for name, endpoint in (("impulse_N48", n48), ("impulse_N64", n64)):
        for sign in ("Bpos", "Bneg"):
            ok = 0.9 <= endpoint[sign] <= 1.1
            formation_pass = formation_pass and ok
            check_row(checks, f"{name}.formation.{sign}", ok, endpoint[sign], "0.9 <= value <= 1.1")
        separation = endpoint["separation"]
        ok = finite(separation) and float(separation) >= 4.0
        formation_pass = formation_pass and ok
        check_row(checks, f"{name}.formation.centroid_separation", ok, separation, 4.0)
        fractions = endpoint["local_fractions"]
        fraction_ok = len(fractions) == 2 and all(finite(value) and float(value) >= 0.8 for value in fractions)
        formation_pass = formation_pass and fraction_ok
        check_row(checks, f"{name}.formation.local_fractions", fraction_ok, fractions, 0.8, expected_signs=2)
        edge_ok = finite(endpoint["edge_angle_max"]) and float(endpoint["edge_angle_max"]) <= PI / 3.0
        formation_pass = formation_pass and edge_ok
        check_row(checks, f"{name}.formation.edge_angle_max", edge_ok, endpoint["edge_angle_max"], PI / 3.0)
    numerical_pass = all(row["pass"] for row in checks if ".formation." not in row["name"])
    first_verdict = "PASS" if numerical_pass and formation_pass else ("INCONCLUSIVE" if not numerical_pass else "DOES NOT EMERGE")
    persistence = bool(numerical_pass and formation_pass)
    ledger = completion_ledger(first_verdict, persistence)
    structure_failed_input = (
        {"path": repo_rel(root / "structure" / "results.json"), "sha256": scalar_hashes["structure"]}
        if "structure" in scalar_hashes
        else {"path": repo_rel(root / "structure" / "results.json"), "sha256": None, "present": False}
    )
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "root": repo_rel(root),
        "adjudicator_source": identity,
        "protocol": {"path": repo_rel(REPORT), "sha256": actual_protocol, "expected_sha256": PROTOCOL_SHA256},
        "status": "ADJUDICATED",
        "inputs": {"arms": {name: {"primary": {"path": repo_rel(row[1]), "sha256": scalar_hashes[f"{name}.primary"]}, "verification": {"path": repo_rel(root / f"{name}_verified" / "verification.json"), "sha256": scalar_hashes[f"{name}.verification"]}} for name, row in primary_rows.items()}, "controls": {"primary": {"path": repo_rel(root / "controls" / "results.json"), "sha256": scalar_hashes["controls.primary"]}, "verification": {"path": repo_rel(root / "controls_verified" / "verification.json"), "sha256": scalar_hashes["controls.verification"]}}, "structure_recovery1": {"path": repo_rel(root / "structure_recovery1" / "results.json"), "sha256": scalar_hashes["structure_recovery1"]}, "structure_failed_preserved": structure_failed_input},
        "raw_npz": array_hash_receipt,
        "scalar_hashes": scalar_hashes,
        "checks": checks,
        "numerical_qualification_passed": bool(numerical_pass),
        "energy_drifts": energy_drifts,
        "constraint_maxima": constraint_maxima,
        "formation_prerequisites_passed": bool(formation_pass),
        "first_schedule_verdict": first_verdict,
        "persistence_prerequisites_passed": persistence,
        "continuation_required": bool(persistence),
        "continuation_status": "REQUIRED—run only the frozen persistence branch" if persistence else "STOP_AT_FIRST_SCHEDULE_BRANCH",
        "endpoint_metrics": endpoint_metrics,
        "completion_requirements": ledger,
        "scientific_scope": "This adjudicates only the frozen finite-resolution classical first schedule of the added massive chiral field; it does not establish quantum matter or physical Cassi particle identity.",
    }
    return payload, 0 if numerical_pass else 1


def error_payload(root: Path, error: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "root": repo_rel(root), "adjudicator_source": {"path": repo_rel(Path(__file__)), "sha256": raw_sha256(Path(__file__))}, "status": "INCONCLUSIVE", "first_schedule_verdict": "INCONCLUSIVE", "persistence_prerequisites_passed": False, "continuation_required": False, "error": error, "completion_requirements": completion_ledger("INCONCLUSIVE", None), "checks": [{"name": "fatal", "pass": False, "error": error}]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="frozen execution root")
    parser.add_argument("--output", type=Path, required=True, help="fresh directory receiving adjudication.json")
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    output = args.output.expanduser().resolve()
    try:
        prepare_output(output)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    try:
        payload, code = adjudicate(root, output)
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        payload, code = error_payload(root, message), 2
    write_json(output / "adjudication.json", payload)
    print(json.dumps({"status": payload.get("status", "ADJUDICATED"), "first_schedule_verdict": payload.get("first_schedule_verdict"), "persistence_prerequisites_passed": payload.get("persistence_prerequisites_passed"), "output": str(output)}, ensure_ascii=False))
    if code == 2 and payload.get("status") != "INCONCLUSIVE":
        return 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
