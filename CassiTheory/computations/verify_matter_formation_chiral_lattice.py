#!/usr/bin/env python3
"""Independent verifier for the frozen SU(2) chiral bubble-lattice receipt.

This module deliberately contains its own lattice operators, Hamiltonian, and
analytic vector field.  It does not import the primary solver.  The primary
receipt is an input artifact only; every diagnostic below is reconstructed from
its NPZ snapshots.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "matter-formation-chiral-lattice-verification-v1"
PRIMARY_SCHEMA = "matter-formation-chiral-lattice-v1"
SOURCE_NAME = "matter_formation_chiral_lattice.py"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
P_PRIMITIVE = 2.0
MU = 0.5266577616452649
KAPPA = 1.0
TOL_METRIC = 1.0e-9
TOL_RHS = 1.0e-8
TOL_REPLAY = 1.0e-7
TOL_UNIT = 1.0e-8
TOL_BASIS = 1.0e-11


def raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


PROTOCOL_PATH = ROOT / "computations" / "matter-formation-continuum-report.md"
PROTOCOL_START = "<!-- chiral-lattice-protocol:start -->"
PROTOCOL_END = "<!-- chiral-lattice-protocol:end -->"


def protocol_sha256(path: Path = PROTOCOL_PATH) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.find(PROTOCOL_START)
    if start < 0:
        raise ValueError(f"protocol start marker missing in {path}")
    start += len(PROTOCOL_START)
    end = text.find(PROTOCOL_END, start)
    if end < 0:
        raise ValueError(f"protocol end marker missing in {path}")
    if text.find(PROTOCOL_START, start) >= 0:
        raise ValueError("multiple protocol start markers")
    return hashlib.sha256(text[start:end].encode("utf-8")).hexdigest()


def finite_array(value: Any, *, ndim: int | None = None) -> bool:
    arr = np.asarray(value)
    return (ndim is None or arr.ndim == ndim) and bool(np.all(np.isfinite(arr)))


def norm_max(value: Any) -> float:
    arr = np.asarray(value, dtype=np.float64)
    if arr.size == 0:
        return math.inf
    return float(np.max(np.abs(arr)))


def normalized_max(actual: Any, expected: Any) -> float:
    a = np.asarray(actual, dtype=np.float64)
    b = np.asarray(expected, dtype=np.float64)
    if a.shape != b.shape or a.size == 0 or not (np.all(np.isfinite(a)) and np.all(np.isfinite(b))):
        return math.inf
    scale = max(1.0, float(np.max(np.abs(a))), float(np.max(np.abs(b))))
    return float(np.max(np.abs(a - b)) / scale)


def close_scalar(actual: Any, expected: Any, tol: float = TOL_METRIC) -> bool:
    try:
        return normalized_max(np.asarray([actual]), np.asarray([expected])) <= tol
    except (TypeError, ValueError):
        return False


def as_float(value: Any) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError("boolean is not a scalar")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError("non-finite scalar")
    return out


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("primary receipt must be a JSON object")
    return value


def resolve_primary(value: str) -> tuple[Path, Path]:
    supplied = Path(value).expanduser().resolve()
    if supplied.is_dir():
        result = supplied / "results.json"
        base = supplied
    else:
        result = supplied
        base = supplied.parent
    if not result.is_file():
        raise FileNotFoundError(f"primary results.json not found: {result}")
    return result, base


def resolve_artifact(base: Path, name: Any) -> Path:
    if not isinstance(name, str) or not name:
        raise ValueError("artifact file must be a non-empty string")
    candidate = Path(name)
    if candidate.is_absolute():
        path = candidate.resolve()
    else:
        path = (base / candidate).resolve()
    # Receipt artifacts must stay within the primary output directory.  This
    # also prevents a receipt from making the verifier hash an unrelated file.
    try:
        path.relative_to(base.resolve())
    except ValueError as exc:
        raise ValueError(f"artifact escapes receipt directory: {name}") from exc
    if not path.is_file():
        raise FileNotFoundError(f"artifact not found: {path}")
    return path


def primitive_basis(N: int, L: float) -> np.ndarray:
    # A0 is given as three primitive *columns*; transpose the displayed rows
    # into a matrix whose column i is the i-th lattice primitive.
    A0 = np.asarray(
        (
            (0.5, 1.0 / (2.0 * PHI), 0.0),
            (0.5, 0.0, P_PRIMITIVE / 2.0),
            (0.0, 1.0 / (2.0 * PHI), P_PRIMITIVE / 2.0),
        ),
        dtype=np.float64,
    ).T
    return (float(L) / float(N)) * A0
def _axis_roll(field: np.ndarray, axis: int, shift: int) -> np.ndarray:
    return np.roll(field, shift, axis=1 + axis)

def delta(field: np.ndarray, axis: int, kind: str) -> np.ndarray:
    if kind == "plus":
        return _axis_roll(field, axis, -1) - field
    if kind == "minus":
        return field - _axis_roll(field, axis, 1)
    if kind == "central":
        return 0.5 * (_axis_roll(field, axis, -1) - _axis_roll(field, axis, 1))
    raise ValueError(f"unknown difference kind {kind!r}")


def delta_adjoint(field: np.ndarray, axis: int, kind: str) -> np.ndarray:
    # Periodic adjoints under the positive site-volume inner product.
    if kind == "plus":
        return _axis_roll(field, axis, 1) - field
    if kind == "minus":
        return field - _axis_roll(field, axis, -1)
    if kind == "central":
        return 0.5 * (_axis_roll(field, axis, 1) - _axis_roll(field, axis, -1))
    raise ValueError(f"unknown difference kind {kind!r}")


def physical_gradient(field: np.ndarray, basis: np.ndarray, kind: str) -> np.ndarray:
    """Return G_a field = sum_i (A^-1)_{ia} Delta_i field.

    ``field`` is (components, N, N, N), and the result is
    (components, physical-direction a, N, N, N).
    """
    inv = np.linalg.inv(np.asarray(basis, dtype=np.float64))
    differences = np.stack([delta(field, i, kind) for i in range(3)], axis=1)
    return np.einsum("ia,ci...->ca...", inv, differences, optimize=True)


def physical_adjoint(field: np.ndarray, basis: np.ndarray, kind: str) -> np.ndarray:
    """Adjoint of physical_gradient, including the periodic stencil adjoint."""
    inv = np.linalg.inv(np.asarray(basis, dtype=np.float64))
    result = np.zeros(field.shape[:1] + field.shape[2:], dtype=np.float64)
    for a in range(3):
        for i in range(3):
            result += inv[i, a] * delta_adjoint(field[:, a], i, kind)
    return result


def physical_adjoint_direction(
    field: np.ndarray, basis: np.ndarray, kind: str, direction: int
) -> np.ndarray:
    """Adjoint of one physical component G_direction."""
    inv = np.linalg.inv(np.asarray(basis, dtype=np.float64))
    result = np.zeros_like(field)
    for i in range(3):
        result += inv[i, direction] * delta_adjoint(field, i, kind)
    return result


def project_tangent(n: np.ndarray, value: np.ndarray) -> np.ndarray:
    return value - n * np.sum(n * value, axis=0, keepdims=True)


def hamiltonian_parts(n: np.ndarray, pfield: np.ndarray, basis: np.ndarray, mu: float, kappa: float) -> dict[str, Any]:
    c = physical_gradient(n, basis, "central")
    d = project_tangent(n[:, None, ...], c)
    # The axis dimension is at 1 for c/d; project_tangent broadcasts n.
    S = np.sum(d * d, axis=(0, 1))
    M = np.broadcast_to(np.eye(4, dtype=np.float64), S.shape + (4, 4)).copy()
    M *= (1.0 + kappa * S)[..., None, None]
    for a in range(3):
        da = d[:, a, ...]
        M -= kappa * np.einsum("i...,j...->...ij", da, da, optimize=True)
    p_last = np.moveaxis(pfield, 0, -1)
    v_last = np.linalg.solve(M, p_last[..., None])[..., 0]
    v = np.moveaxis(v_last, -1, 0)
    kinetic = 0.5 * np.sum(pfield * v, axis=0)
    gp = physical_gradient(n, basis, "plus")
    gm = physical_gradient(n, basis, "minus")
    e2 = 0.25 * (np.sum(gp * gp, axis=(0, 1)) + np.sum(gm * gm, axis=(0, 1)))
    e4 = np.zeros_like(S)
    for a in range(3):
        for b in range(a + 1, 3):
            da, db = d[:, a, ...], d[:, b, ...]
            e4 += 0.5 * kappa * (np.sum(da * da, axis=0) * np.sum(db * db, axis=0) - np.sum(da * db, axis=0) ** 2)
    potential = mu * mu * (1.0 - n[0])
    return {"c": c, "d": d, "S": S, "M": M, "v": v, "kinetic_density": kinetic,
            "e2_density": e2, "e4_density": e4, "potential_density": potential,
            "energy_density": kinetic + e2 + e4 + potential}


def analytic_rhs(n: np.ndarray, pfield: np.ndarray, basis: np.ndarray, mu: float = MU, kappa: float = KAPPA) -> tuple[np.ndarray, np.ndarray]:
    parts = hamiltonian_parts(n, pfield, basis, mu, kappa)
    c, d, v = parts["c"], parts["d"], parts["v"]
    W = np.zeros_like(d)
    for a in range(3):
        da = d[:, a, ...]
        for b in range(3):
            if a == b:
                continue
            db = d[:, b, ...]
            W[:, a, ...] += kappa * (np.sum(db * db, axis=0) * da - np.sum(da * db, axis=0) * db)
        W[:, a, ...] -= kappa * (np.sum(v * v, axis=0) * da - np.sum(v * da, axis=0) * v)
    grad_n = np.zeros_like(n)
    for a in range(3):
        wa = W[:, a, ...]
        ca = c[:, a, ...]
        grad_n += physical_adjoint_direction(project_tangent(n, wa), basis, "central", a)
        grad_n -= np.sum(n * ca, axis=0, keepdims=True) * wa
        grad_n -= np.sum(n * wa, axis=0, keepdims=True) * ca
    gp = physical_gradient(n, basis, "plus")
    gm = physical_gradient(n, basis, "minus")
    for a in range(3):
        grad_n += 0.5 * (
            physical_adjoint_direction(gp[:, a, ...], basis, "plus", a)
            + physical_adjoint_direction(gm[:, a, ...], basis, "minus", a)
        )
    grad_n[0] -= mu * mu
    grad_proj = project_tangent(n, grad_n)
    pdotv = np.sum(pfield * v, axis=0, keepdims=True)
    dp = -grad_proj - n * pdotv
    return v, dp




def metrics(n: np.ndarray, pfield: np.ndarray, basis: np.ndarray, mu: float, kappa: float, t: float, sitevol: float, localized: bool = False) -> dict[str, Any]:
    parts = hamiltonian_parts(n, pfield, basis, mu, kappa)
    d = parts["d"]
    frame = np.stack([n, d[:, 0, ...], d[:, 1, ...], d[:, 2, ...]], axis=-1)
    b_density = np.linalg.det(np.moveaxis(frame, 0, -2)) / (2.0 * math.pi * math.pi)
    torque_density = np.cross(n[1:, ...], pfield[1:, ...], axisa=0, axisb=0, axisc=0)
    edge_angle = 0.0
    for axis in range(3):
        dot = np.sum(n * _axis_roll(n, axis, -1), axis=0)
        edge_angle = max(edge_angle, float(np.max(np.arccos(np.clip(dot, -1.0, 1.0)))))
    localization: dict[str, Any] = {}
    if localized:
        size = n.shape[1]
        axis = np.arange(size, dtype=np.float64) - size / 2.0 + 0.5
        index_grid = np.stack(np.meshgrid(axis, axis, axis, indexing="ij"))
        phases = 2.0 * math.pi * index_grid / size
        centres, fractions = [], []
        for density in (np.maximum(b_density, 0.0), np.maximum(-b_density, 0.0)):
            weight = float(np.sum(density))
            if weight <= 1.0e-30:
                centres.append(np.zeros(3))
                fractions.append(0.0)
                continue
            moment = np.sum(np.exp(1j * phases) * density[None], axis=(1, 2, 3))
            centre_index = np.angle(moment) * size / (2.0 * math.pi)
            delta = index_grid - centre_index[:, None, None, None]
            delta -= size * np.rint(delta / size)
            physical = np.einsum("ai,ixyz->axyz", basis, delta)
            radii = np.linalg.norm(physical, axis=0)
            fractions.append(float(np.sum(density[radii <= 2.0])) / weight)
            centres.append(basis @ centre_index)
        centre_delta = np.linalg.solve(basis, centres[0] - centres[1])
        centre_delta -= size * np.rint(centre_delta / size)
        localization = {
            "centres": [c.tolist() for c in centres],
            "separation": float(np.linalg.norm(basis @ centre_delta)),
            "local_fractions": fractions,
        }
    return {
        "t": float(t),
        "energy": float(sitevol * np.sum(parts["energy_density"])),
        "kinetic": float(sitevol * np.sum(parts["kinetic_density"])),
        "e2": float(sitevol * np.sum(parts["e2_density"])),
        "e4": float(sitevol * np.sum(parts["e4_density"])),
        "potential": float(sitevol * np.sum(parts["potential_density"])),
        "B": float(sitevol * np.sum(b_density)),
        "Bpos": float(sitevol * np.sum(np.maximum(b_density, 0.0))),
        "Bneg": float(sitevol * np.sum(np.maximum(-b_density, 0.0))),
        "unit_error": float(np.max(np.abs(np.sum(n * n, axis=0) - 1.0))),
        "tangent_error": float(np.max(np.abs(np.sum(n * pfield, axis=0)))),
        "edge_angle_max": float(edge_angle),
        "torque": [float(x) for x in (sitevol * np.sum(torque_density, axis=(1, 2, 3)))],
        **localization,
    }


def check_metrics(expected: Mapping[str, Any], actual: Mapping[str, Any], tolerance: float, prefix: str, checks: list[dict[str, Any]]) -> None:
    keys = ("t", "energy", "kinetic", "e2", "e4", "potential", "B", "Bpos", "Bneg", "unit_error", "tangent_error", "edge_angle_max", "torque")
    if "local_fractions" in actual:
        keys += ("centres", "separation", "local_fractions")
    for key in keys:
        if key not in expected:
            checks.append({"name": f"{prefix}.{key}", "pass": False, "reason": "missing expected metric"})
            continue
        err = normalized_max(np.asarray(actual.get(key)), np.asarray(expected[key]))
        checks.append({"name": f"{prefix}.{key}", "pass": bool(err <= tolerance), "normalized_max": err, "tolerance": tolerance})


def load_npz(path: Path, required: tuple[str, ...]) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as loaded:
        missing = [key for key in required if key not in loaded]
        if missing:
            raise ValueError(f"{path.name}: missing NPZ arrays {missing}")
        result = {key: np.asarray(loaded[key], dtype=np.float64) for key in loaded.files}
    return result


def validate_state(data: Mapping[str, np.ndarray], prefix: str, checks: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n, pfield, basis = data["n"], data["p"], data["basis"]
    ok = n.shape == pfield.shape and n.ndim == 4 and n.shape[0] == 4 and len(set(n.shape[1:])) == 1
    checks.append({"name": f"{prefix}.shape", "pass": bool(ok), "n_shape": list(n.shape), "p_shape": list(pfield.shape)})
    finite = finite_array(n) and finite_array(pfield) and finite_array(basis)
    checks.append({"name": f"{prefix}.finite", "pass": bool(finite)})
    checks.append({"name": f"{prefix}.basis_shape", "pass": bool(basis.shape == (3, 3))})
    if not ok or not finite or basis.shape != (3, 3):
        raise ValueError(f"invalid state arrays in {prefix}")
    unit_error = float(np.max(np.abs(np.sum(n * n, axis=0) - 1.0)))
    tangent_error = float(np.max(np.abs(np.sum(n * pfield, axis=0))))
    checks.append({"name": f"{prefix}.constraints", "pass": unit_error <= TOL_UNIT and tangent_error <= TOL_UNIT, "unit_error": unit_error, "tangent_error": tangent_error})
    return n, pfield, basis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", required=True, help="primary results.json or its containing directory")
    parser.add_argument("--output", required=True, help="new directory receiving verification.json")
    args = parser.parse_args(argv)
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    output_dir = Path(args.output).expanduser().resolve()
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        parser.error(f"--output must name a fresh or empty directory: {output_dir}")
    try:
        result_path, base = resolve_primary(args.primary)
        primary = load_json(result_path)
        schema_ok = primary.get("schema") == PRIMARY_SCHEMA
        checks.append({"name": "primary.schema", "pass": schema_ok, "expected": PRIMARY_SCHEMA, "actual": primary.get("schema")})
        mode = primary.get("mode")
        mode_ok = mode in {"controls", "impulse", "prepared", "vacuum"}
        checks.append({"name": "primary.mode", "pass": mode_ok, "actual": mode})
        if not mode_ok:
            raise ValueError("primary mode is not recognized")
        if not schema_ok:
            raise ValueError("wrong primary schema")
        params = primary.get("parameters")
        if not isinstance(params, dict):
            raise ValueError("primary parameters missing")
        N = int(params["N"])
        L = float(params["L"])
        protocol_declared = primary.get("protocol_sha256")
        protocol_actual = protocol_sha256()
        protocol_ok = isinstance(protocol_declared, str) and protocol_declared == protocol_actual
        checks.append({"name": "primary.protocol_hash", "pass": protocol_ok, "path": str(PROTOCOL_PATH), "expected": protocol_declared, "actual": protocol_actual})
        if not protocol_ok:
            raise ValueError("primary protocol_sha256 is missing or does not match marker-delimited protocol")
        mu = float(params.get("mu", MU))
        kappa = float(params.get("kappa", KAPPA))
        if N < 2 or not (math.isfinite(L) and L > 0 and math.isfinite(mu) and math.isfinite(kappa)):
            raise ValueError("invalid primary parameters")
        checks.append({"name": "parameters", "pass": close_scalar(mu, MU, 1e-14) and close_scalar(kappa, KAPPA, 1e-14), "N": N, "L": L, "mu": mu, "kappa": kappa})
        controls_ok = mode != "controls" or (
            N == 6 and close_scalar(L, 6.0, 1e-14)
            and close_scalar(float(params.get("dt")), 0.001, 1e-14)
            and close_scalar(float(params.get("T")), 0.02, 1e-14)
        )
        checks.append({"name": "controls.parameters", "pass": controls_ok, "required": {"N": 6, "L": 6.0, "dt": 0.001, "T": 0.02} if mode == "controls" else None})
        if not controls_ok:
            raise ValueError("controls receipt parameters are not the frozen N=6,L=6,T=.02,dt=.001 control")

        source_rel = primary.get("source_file")
        expected_source_rel = f"computations/{SOURCE_NAME}"
        source = (ROOT / source_rel).resolve() if isinstance(source_rel, str) else ROOT / SOURCE_NAME
        source_rel_ok = source_rel == expected_source_rel
        source_hash = primary.get("source_sha256")
        sources = primary.get("sources")
        sources_hash = sources.get(expected_source_rel) if isinstance(sources, dict) else None
        source_ok = source_rel_ok and source.is_file() and isinstance(source_hash, str) and raw_sha256(source) == source_hash
        sources_ok = isinstance(sources, dict) and sources_hash == source_hash
        report_rel = PROTOCOL_PATH.relative_to(ROOT).as_posix()
        report_entry = sources.get(report_rel) if isinstance(sources, dict) else None
        report_entry_ok = report_entry is None or report_entry == protocol_actual
        checks.append({"name": "primary.source_identity", "pass": source_ok and sources_ok and report_entry_ok, "path": source.as_posix(), "source_file": source_rel, "expected": source_hash, "actual": raw_sha256(source) if source.is_file() else None, "sources_entry": sources_hash, "protocol_sources_entry": report_entry})
        if not source_ok or not sources_ok or not report_entry_ok:
            raise ValueError("primary source identity is missing or does not match raw source")

        expected_basis = primitive_basis(N, L)
        snapshots = primary.get("snapshots")
        if not isinstance(snapshots, list) or not snapshots:
            raise ValueError("primary snapshots must be a nonempty list")
        records = primary.get("records")
        if not isinstance(records, list) or not records:
            raise ValueError("primary records must be a nonempty list")
        if len(records) != len(snapshots):
            raise ValueError("records and snapshots must have equal length")
        sitevol = abs(float(np.linalg.det(expected_basis)))
        if not math.isfinite(sitevol) or sitevol <= 0:
            raise ValueError("invalid positive site volume")
        checks.append({"name": "geometry.site_volume", "pass": True, "site_volume": sitevol, "basis_convention": "A columns are the three displayed primitive columns; Delta is unit-index periodic"})

        for index, item in enumerate(snapshots):
            if not isinstance(item, dict):
                raise ValueError(f"snapshot {index} is not an object")
            path = resolve_artifact(base, item.get("file"))
            declared_hash = item.get("sha256")
            actual_hash = raw_sha256(path)
            hash_ok = isinstance(declared_hash, str) and declared_hash == actual_hash
            checks.append({"name": f"snapshot[{index}].raw_hash", "pass": hash_ok, "file": str(item.get("file")), "expected": declared_hash, "actual": actual_hash})
            if not hash_ok:
                raise ValueError(f"snapshot {index} hash mismatch")
            data = load_npz(path, ("n", "p", "basis"))
            n, pfield, basis = validate_state(data, f"snapshot[{index}]", checks)
            basis_err = normalized_max(basis, expected_basis)
            checks.append({"name": f"snapshot[{index}].basis", "pass": basis_err <= TOL_BASIS, "normalized_max": basis_err, "tolerance": TOL_BASIS})
            endpoint_localization = mode == "impulse" and index == len(snapshots) - 1
            state_metrics = metrics(n, pfield, basis, mu, kappa, float(item.get("t", 0.0)), abs(float(np.linalg.det(basis))), localized=endpoint_localization)
            expected_metrics = item.get("metrics")
            if not isinstance(expected_metrics, dict):
                raise ValueError(f"snapshot {index} metrics missing")
            check_metrics(expected_metrics, state_metrics, TOL_METRIC, f"snapshot[{index}].metrics", checks)
            if not isinstance(records[index], dict):
                raise ValueError(f"record {index} is not an object")
            check_metrics(records[index], state_metrics, TOL_METRIC, f"records[{index}]", checks)
            checks.append({"name": f"snapshot[{index}].constraints", "pass": state_metrics["unit_error"] <= TOL_UNIT and state_metrics["tangent_error"] <= TOL_UNIT, "unit_error": state_metrics["unit_error"], "tangent_error": state_metrics["tangent_error"]})

        if mode == "controls":
            probe = primary.get("rhs_probe")
            if not isinstance(probe, dict):
                raise ValueError("rhs_probe missing for controls mode")
            probe_path = resolve_artifact(base, probe.get("file"))
            probe_hash = raw_sha256(probe_path)
            probe_hash_ok = isinstance(probe.get("sha256"), str) and probe.get("sha256") == probe_hash
            checks.append({"name": "rhs_probe.raw_hash", "pass": probe_hash_ok, "expected": probe.get("sha256"), "actual": probe_hash})
            if not probe_hash_ok:
                raise ValueError("rhs probe hash mismatch")
            probe_data = load_npz(probe_path, ("n", "p", "basis", "dn", "dp"))
            n, pfield, basis = validate_state(probe_data, "rhs_probe", checks)
            dn, dp = probe_data["dn"], probe_data["dp"]
            calc_dn, calc_dp = analytic_rhs(n, pfield, basis, mu, kappa)
            dn_err = normalized_max(calc_dn, dn)
            dp_err = normalized_max(calc_dp, dp)
            checks.extend((
                {"name": "rhs_probe.dn", "pass": dn_err <= TOL_RHS, "normalized_max": dn_err, "tolerance": TOL_RHS},
                {"name": "rhs_probe.dp", "pass": dp_err <= TOL_RHS, "normalized_max": dp_err, "tolerance": TOL_RHS},
            ))
            if dn.shape != n.shape or dp.shape != pfield.shape:
                raise ValueError("rhs probe derivative shapes do not match state")

            replay = primary.get("replay")
            if not isinstance(replay, dict):
                raise ValueError("replay missing for controls mode")
            replay_path = resolve_artifact(base, replay.get("file"))
            replay_hash = raw_sha256(replay_path)
            replay_hash_ok = isinstance(replay.get("sha256"), str) and replay.get("sha256") == replay_hash
            checks.append({"name": "replay.raw_hash", "pass": replay_hash_ok, "expected": replay.get("sha256"), "actual": replay_hash})
            if not replay_hash_ok:
                raise ValueError("replay hash mismatch")
            replay_data = load_npz(replay_path, ("n0", "p0", "n1", "p1", "basis"))
            n0, p0, rbasis = replay_data["n0"], replay_data["p0"], replay_data["basis"]
            replay_shape_ok = n0.shape == p0.shape == replay_data["n1"].shape == replay_data["p1"].shape and n0.ndim == 4 and n0.shape[0] == 4 and rbasis.shape == (3, 3)
            replay_finite_ok = all(finite_array(replay_data[key]) for key in ("n0", "p0", "n1", "p1", "basis"))
            checks.append({"name": "replay.shapes", "pass": replay_shape_ok, "n0": list(n0.shape), "p0": list(p0.shape), "n1": list(replay_data["n1"].shape), "p1": list(replay_data["p1"].shape), "basis": list(rbasis.shape)})
            checks.append({"name": "replay.finite", "pass": replay_finite_ok})
            if not replay_shape_ok or not replay_finite_ok:
                raise ValueError("invalid replay shapes or non-finite arrays")
            replay_basis_err = normalized_max(rbasis, expected_basis)
            checks.append({"name": "replay.basis", "pass": replay_basis_err <= TOL_BASIS, "normalized_max": replay_basis_err, "tolerance": TOL_BASIS})
            replay_unit0 = norm_max(np.sum(n0 * n0, axis=0) - 1.0)
            replay_tangent0 = norm_max(np.sum(n0 * p0, axis=0))
            checks.append({"name": "replay.initial_constraints", "pass": replay_unit0 <= TOL_UNIT and replay_tangent0 <= TOL_UNIT, "unit_error": replay_unit0, "tangent_error": replay_tangent0})
            if replay_basis_err > TOL_BASIS:
                raise ValueError("replay basis does not match declared geometry")
            dt = float(replay.get("dt"))
            steps = int(replay.get("steps"))
            if not (math.isfinite(dt) and dt > 0 and steps > 0):
                raise ValueError("invalid replay dt/steps")
            y0 = np.concatenate((n0.ravel(), p0.ravel()))
            state_size = n0.size
            def rhs_ode(_time: float, y: np.ndarray) -> np.ndarray:
                nn = y[:state_size].reshape(n0.shape)
                pp = y[state_size:].reshape(p0.shape)
                dnn, dpp = analytic_rhs(nn, pp, rbasis, mu, kappa)
                return np.concatenate((dnn.ravel(), dpp.ravel()))
            integration = solve_ivp(rhs_ode, (0.0, dt * steps), y0, method="DOP853", atol=1.0e-11, rtol=1.0e-11, t_eval=(dt * steps,))
            solver_ok = bool(integration.success and integration.y.shape == (2 * state_size, 1) and np.all(np.isfinite(integration.y)))
            checks.append({"name": "replay.dop853", "pass": solver_ok, "message": integration.message, "nfev": int(integration.nfev)})
            if not solver_ok:
                raise ValueError("DOP853 replay failed")
            n1_calc = integration.y[:state_size, -1].reshape(n0.shape)
            p1_calc = integration.y[state_size:, -1].reshape(p0.shape)
            n1_err = normalized_max(n1_calc, replay_data["n1"])
            p1_err = normalized_max(p1_calc, replay_data["p1"])
            checks.extend((
                {"name": "replay.n1", "pass": n1_err <= TOL_REPLAY, "normalized_max": n1_err, "tolerance": TOL_REPLAY},
                {"name": "replay.p1", "pass": p1_err <= TOL_REPLAY, "normalized_max": p1_err, "tolerance": TOL_REPLAY},
            ))
            checks.append({"name": "replay.constraint_drift", "pass": norm_max(np.sum(n1_calc * n1_calc, axis=0) - 1.0) <= TOL_UNIT, "unit_error": norm_max(np.sum(n1_calc * n1_calc, axis=0) - 1.0)})
        else:
            checks.append({"name": "control_probes", "pass": True, "status": "not required for non-controls mode"})
    except Exception as exc:  # qualification must fail visibly, with a useful reason
        failures.append(f"{type(exc).__name__}: {exc}")
        checks.append({"name": "fatal", "pass": False, "error": failures[-1]})

    all_pass = not failures and all(bool(row.get("pass")) for row in checks)
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
    verification = {
        "schema": SCHEMA,
        "primary": str(result_path) if "result_path" in locals() else str(args.primary),
        "source_identity": {"path": str(source) if "source" in locals() else str(ROOT / "computations" / SOURCE_NAME), "sha256": primary.get("source_sha256") if "primary" in locals() and isinstance(primary, dict) else None},
        "artifact_identity": {"primary_results_sha256": raw_sha256(result_path) if "result_path" in locals() and result_path.is_file() else None, "verifier_sha256": raw_sha256(Path(__file__))},
        "conventions": {"difference": "periodic unit-index forward/backward/central", "gradient": "G_a=sum_i(A^-1)_{ia} Delta_i", "site_volume": "abs(det(A))", "topological_density": "det([n,d_x,d_y,d_z])/(2*pi^2)", "rhs": "analytic projected Hamiltonian vector field", "replay": "scipy DOP853 atol=rtol=1e-11 without projection"},
        "checks": checks,
        "failures": failures,
        "all_pass": bool(all_pass),
    }
    with (output_dir / "verification.json").open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(verification, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
