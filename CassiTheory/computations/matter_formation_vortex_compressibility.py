#!/usr/bin/env python3
"""Primary sparse longitudinal population-response calculation.

This is a fixed-response calculation on the 24 already-qualified loaded radial
profiles.  It does not perform a minimization or alter any supplied profile.
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
import scipy.sparse as sparse
import scipy.sparse.linalg as spla
import torch

import matter_formation_vortex_core as core


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "matter-formation-vortex-compressibility-v1"
MANIFEST_SCHEMA = "matter-formation-vortex-compressibility-manifest-v1"
NOTEBOOK = "computations/matter-formation-continuum-report.md"
HEADING = "## 47. Working notes:"
LAMBDA_C = 1.0
CAPS = ("plus", "minus")
EPSILONS = {"plus": 1, "minus": -1}
POPULATIONS = (1.0, 16.0, 64.0)
SCHEDULE = ((32.0, 256), (32.0, 512), (64.0, 512), (64.0, 1024))
REQUIRED_SOURCES = {
    "computations/matter_formation_vortex_core.py",
    "computations/verify_matter_formation_vortex_core.py",
    "computations/matter_formation_vortex_loaded.py",
    "computations/verify_matter_formation_vortex_loaded.py",
    "computations/matter_formation_vortex_compressibility.py",
    "computations/verify_matter_formation_vortex_compressibility.py",
}


def _torch_single_thread() -> None:
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)


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


def strict_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): strict_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [strict_value(item) for item in value]
    if isinstance(value, np.ndarray):
        return strict_value(value.tolist())
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(strict_value(value), handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


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


def safe_relative(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f"invalid relative path: {value!r}")
    result = (root / value).resolve()
    root_resolved = root.resolve()
    if result != root_resolved and root_resolved not in result.parents:
        raise ValueError(f"path escapes root: {value}")
    return result


def expected_keys() -> set[tuple[str, float, int, float]]:
    return {(cap, n, int(R), N) for cap in CAPS for n in POPULATIONS for R, N in SCHEDULE}


def validate_manifest(manifest_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    manifest = strict_json(manifest_path)
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("manifest schema mismatch")

    section = manifest.get("section")
    if not isinstance(section, dict) or section.get("path") != NOTEBOOK or section.get("heading") != HEADING:
        raise ValueError("manifest section identity mismatch")
    snapshot = safe_relative(manifest_path.parent, section.get("snapshot"))
    live = safe_relative(ROOT, section.get("path"))
    expected_hash = section.get("sha256")
    if not isinstance(expected_hash, str) or sha256(snapshot) != expected_hash:
        raise ValueError("frozen section snapshot hash mismatch")
    snapshot_text = snapshot.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    live_text = live.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    if not snapshot_text.startswith(HEADING):
        raise ValueError("frozen section snapshot does not start at heading")
    at = live_text.find(HEADING)
    if at < 0 or live_text[at : at + len(snapshot_text)] != snapshot_text:
        raise ValueError("live report does not contain exact frozen section snapshot")

    sources = manifest.get("sources")
    if not isinstance(sources, list) or {item.get("path") for item in sources if isinstance(item, dict)} != REQUIRED_SOURCES:
        raise ValueError("manifest sources do not exactly match the six calculation programs")
    seen_sources: set[str] = set()
    for item in sources:
        if not isinstance(item, dict):
            raise ValueError("malformed source record")
        rel = item.get("path")
        if rel in seen_sources:
            raise ValueError(f"duplicate source record: {rel}")
        seen_sources.add(rel)
        source_path = safe_relative(ROOT, rel)
        frozen = safe_relative(manifest_path.parent, item.get("snapshot"))
        expected = item.get("sha256")
        if not isinstance(expected, str) or sha256(source_path) != expected or sha256(frozen) != expected:
            raise ValueError(f"source hash mismatch: {rel}")

    evidence = manifest.get("evidence")
    if not isinstance(evidence, list) or len(evidence) != 2:
        raise ValueError("manifest evidence must contain parent summary and verification")
    evidence_paths: list[Path] = []
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError("malformed evidence record")
        path = safe_relative(ROOT, item.get("path"))
        expected = item.get("sha256")
        if not isinstance(expected, str) or sha256(path) != expected:
            raise ValueError(f"evidence hash mismatch: {item.get('path')}")
        evidence_paths.append(path)
    primary_path = next((path for path in evidence_paths if path.name == "summary.json"), None)
    verification_path = next((path for path in evidence_paths if path.name == "verification.json"), None)
    if primary_path is None or verification_path is None:
        raise ValueError("evidence must identify summary.json and verification.json")
    primary = strict_json(primary_path)
    verification = strict_json(verification_path)
    if primary.get("schema") != "matter-formation-loaded-vortex-v1":
        raise ValueError("parent primary schema mismatch")
    if primary.get("complete_physical_matter_formation") is not False:
        raise ValueError("parent primary physical-formation flag is not false")
    if primary.get("all_rows_numerically_qualified") is not True:
        raise ValueError("parent primary was not accepted")
    if verification.get("numerical_pass") is not True:
        raise ValueError("parent verification numerical_pass is not true")
    if verification.get("complete_physical_matter_formation") is not False:
        raise ValueError("parent verification physical-formation flag is not false")

    inputs = manifest.get("inputs")
    if not isinstance(inputs, list) or len(inputs) != 24:
        raise ValueError("manifest must contain exactly 24 input records")
    records: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, float, int, float]] = set()
    for item in inputs:
        if not isinstance(item, dict):
            raise ValueError("malformed input record")
        cap = item.get("cap")
        epsilon = item.get("epsilon")
        n = item.get("n")
        R = item.get("R")
        N = item.get("N")
        key = (cap, float(n), int(R), int(N)) if cap in CAPS else None
        if key is None or epsilon != EPSILONS[cap] or key in seen_keys or key not in expected_keys():
            raise ValueError(f"input schedule metadata mismatch: {item}")
        seen_keys.add(key)
        path = safe_relative(ROOT, item.get("path"))
        expected = item.get("sha256")
        if not isinstance(expected, str) or sha256(path) != expected:
            raise ValueError(f"input hash mismatch: {item.get('path')}")
        records.append({"path": path, "path_text": item["path"], "sha256": expected, "cap": cap, "epsilon": int(epsilon), "n": float(n), "R": float(R), "N": int(N)})
    if seen_keys != expected_keys():
        raise ValueError("input schedule is incomplete")
    order: dict[tuple[str, float, int, int], int] = {}
    for index, (cap, n, R, N) in enumerate(((
        cap, n, int(R), N
    ) for cap in CAPS for n in POPULATIONS for R, N in SCHEDULE)):
        order[(cap, n, R, N)] = index
    records.sort(key=lambda item: order[(item["cap"], item["n"], int(item["R"]), item["N"])])
    return manifest, records, primary, verification




def population_torch(model: core.RadialModel, f: torch.Tensor) -> torch.Tensor:
    t = torch.as_tensor(model.t, dtype=torch.float64)
    weight = torch.as_tensor(model.qweight, dtype=torch.float64)
    fq = (1.0 - t[None, :]) * f[:-1, None] + t[None, :] * f[1:, None]
    return torch.sum(weight * fq * fq)


def differentiable_joint_energy(model: core.RadialModel, y: torch.Tensor, f: torch.Tensor) -> torch.Tensor:
    """Evaluate the loaded energy with the algebraic h envelope kept differentiable.

    ``RadialModel.torch_energy`` deliberately detaches h for the first-gradient
    optimizer.  For this response Hessian the same reduced scalar is written
    explicitly as E(h=0)-L**2/(2*H), retaining the Schur-complement term.
    """
    t = torch.as_tensor(model.t, dtype=torch.float64)
    basis = torch.as_tensor(model.basis, dtype=torch.float64)
    dbasis = torch.as_tensor(model.dbasis, dtype=torch.float64)
    qr = torch.as_tensor(model.qr, dtype=torch.float64)
    yq = (1.0 - t[None, :, None]) * y[:-1, None, :] + t[None, :, None] * y[1:, None, :]
    dy = (y[1:] - y[:-1]) / model.dr
    fields = yq * basis
    derivatives = dy[:, None, :] * basis + yq * dbasis
    p, q, u, b1, b3 = (fields[..., j] for j in range(5))
    dp, dq, du, db1, db3 = (derivatives[..., j] for j in range(5))
    total_at_h0, _, _, h_quad, l_quad = core.radial_density(
        p, q, u, b1, b3, dp, dq, du, db1, db3, qr,
        torch.zeros_like(qr), model.epsilon, torch,
    )
    reduced_core = total_at_h0 - l_quad * l_quad / (2.0 * h_quad)
    fq = (1.0 - t[None, :]) * f[:-1, None] + t[None, :] * f[1:, None]
    dfq = (f[1:] - f[:-1])[:, None] / model.dr
    rho = p * p + q * q
    carrier = (
        core.K_CX * dfq * dfq / 2.0
        - core.ETA_C * (core.RHO0 - rho) * fq * fq
        + LAMBDA_C * fq**4 / 2.0
    )
    return torch.sum(torch.as_tensor(model.qweight, dtype=torch.float64) * (reduced_core + carrier))


def unpack(model: core.RadialModel, z: torch.Tensor, y_outer: np.ndarray, f_outer: float, lump: np.ndarray) -> tuple[torch.Tensor, torch.Tensor]:
    scale = torch.as_tensor(np.sqrt(lump[:-1]), dtype=torch.float64)
    free = z.reshape(model.N, 6) / scale[:, None]
    y = torch.cat((free[:, :5], torch.as_tensor(y_outer, dtype=torch.float64)[None, :]), dim=0)
    f = torch.cat((free[:, 5], torch.as_tensor([f_outer], dtype=torch.float64)), dim=0)
    return y, f


def assemble_colored_hessian(model: core.RadialModel, z: torch.Tensor, lagrangian: torch.Tensor) -> sparse.csr_matrix:
    """Assemble the nearest-neighbor Hessian from 18 colored HVPs."""
    gradient = torch.autograd.grad(lagrangian, z, create_graph=True)[0]
    size = 6 * model.N
    rows: list[int] = []
    cols: list[int] = []
    values: list[float] = []
    for color in range(3):
        nodes = list(range(color, model.N, 3))
        for component in range(6):
            selected_gradient = gradient.reshape(model.N, 6)[color::3, component].sum()
            hvp = torch.autograd.grad(selected_gradient, z, retain_graph=True)[0].detach().numpy()
            for node in nodes:
                col = 6 * node + component
                for support in (node - 1, node, node + 1):
                    if 0 <= support < model.N:
                        row0 = 6 * support
                        block = hvp[row0 : row0 + 6]
                        for offset, value in enumerate(block):
                            rows.append(row0 + offset)
                            cols.append(col)
                            values.append(float(value))
    return sparse.coo_matrix((np.asarray(values), (rows, cols)), shape=(size, size)).tocsr()


def solve_row(record: dict[str, Any], parent_row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    path = record["path"]
    with np.load(path, allow_pickle=False) as data:
        required = ("r", "y", "f")
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"input NPZ missing arrays: {missing}")
        r = np.asarray(data["r"], dtype=np.float64)
        y = np.asarray(data["y"], dtype=np.float64)
        f = np.asarray(data["f"], dtype=np.float64)
    N = record["N"]
    if r.shape != (N + 1,) or y.shape != (N + 1, 5) or f.shape != (N + 1,):
        raise ValueError("input profile shape mismatch")
    if not (finite(r) and finite(y) and finite(f)):
        raise ValueError("input profile contains nonfinite values")
    model = core.RadialModel(record["R"], N, record["epsilon"])
    if not np.allclose(r, model.r, rtol=0.0, atol=1e-12):
        raise ValueError("input radial grid differs from declared model")
    lump = model.mass
    x = np.column_stack((y, f))
    z0 = (np.sqrt(lump[:-1, None]) * x[:-1]).reshape(-1)
    z = torch.as_tensor(z0, dtype=torch.float64).requires_grad_(True)
    y_t, f_t = unpack(model, z, y[-1], float(f[-1]), lump)
    energy_t = differentiable_joint_energy(model, y_t, f_t)
    population_t = population_torch(model, f_t)
    mu = float(parent_row["mu_relative"])
    if not math.isfinite(mu):
        raise ValueError("parent chemical potential is nonfinite")
    grad_energy_t = torch.autograd.grad(energy_t, z, retain_graph=True)[0]
    grad_population_t = torch.autograd.grad(population_t, z, retain_graph=True)[0]
    lagrangian = energy_t - mu * population_t
    H = assemble_colored_hessian(model, z, lagrangian)
    energy = float(energy_t.detach().cpu().item())
    population = float(population_t.detach().cpu().item())
    gradient_energy = grad_energy_t.detach().cpu().numpy().astype(np.float64, copy=False)
    b = grad_population_t.detach().cpu().numpy().astype(np.float64, copy=False)
    if not finite(energy) or not finite(population) or not finite(gradient_energy) or not finite(b) or not np.all(np.isfinite(H.data)):
        raise ValueError("nonfinite response input or Hessian")
    bordered = sparse.bmat([[H, sparse.csr_matrix((-b[:, None]))], [sparse.csr_matrix(b[None, :]), sparse.csr_matrix((1, 1))]], format="csr")
    rhs = np.zeros(6 * N + 1, dtype=np.float64)
    rhs[-1] = 1.0
    solution = np.asarray(spla.spsolve(bordered, rhs), dtype=np.float64)
    response = solution[:-1]
    zeta = float(solution[-1])
    hu = H @ response
    asymmetry = H - H.T
    symmetry_error = float(np.max(np.abs(asymmetry.data)) / max(1.0, float(np.max(np.abs(H.data))))) if asymmetry.nnz else 0.0
    kkt_residual = float(np.linalg.norm(hu - b * zeta) / max(1.0, float(np.linalg.norm(b * zeta))))
    constraint_residual = float(abs(float(b @ response) - 1.0))
    curvature_residual = float(abs(float(response @ hu) - zeta) / max(1.0, abs(zeta)))
    qualified = bool(
        finite(solution)
        and symmetry_error < 1e-10
        and kkt_residual < 1e-8
        and constraint_residual < 1e-10
        and curvature_residual < 1e-8
    )
    stem = f"cap_{record['cap']}_n{int(record['n'])}_N{N}_R{int(record['R'])}"
    arrays = {
        "r": r, "y": y, "f": f, "lump": lump, "z": z0, "b": b,
        "gradient_energy": gradient_energy, "response": response,
        "H_data": H.data.astype(np.float64, copy=False), "H_indices": H.indices.astype(np.int64, copy=False),
        "H_indptr": H.indptr.astype(np.int64, copy=False), "H_shape": np.asarray(H.shape, dtype=np.int64),
        "energy": np.asarray(energy, dtype=np.float64), "population": np.asarray(population, dtype=np.float64),
        "mu_relative": np.asarray(mu, dtype=np.float64), "zeta": np.asarray(zeta, dtype=np.float64),
    }
    row = {
        "cap": record["cap"], "epsilon": record["epsilon"], "n": record["n"], "R": record["R"], "N": N,
        "input_npz": record["path_text"], "npz": stem + "_response.npz", "energy": energy, "population": population,
        "mu_relative": mu, "zeta": zeta, "symmetry_error": symmetry_error, "kkt_residual": kkt_residual,
        "constraint_residual": constraint_residual, "curvature_residual": curvature_residual, "qualified": qualified,
        "exception": None, "complete_physical_matter_formation": False,
    }
    return row, arrays


def toy_controls() -> dict[str, Any]:
    controls: list[dict[str, Any]] = []
    for lam in (0.5, 1.0, 2.0):
        point = torch.tensor([-3.0, math.sqrt(3.0)], dtype=torch.float64, requires_grad=True)
        x, f = point[0], point[1]
        energy = x * x / 2.0 + x * f * f + lam * f**4 / 2.0
        population = f * f
        mu = -3.0 + 3.0 * lam
        gradient = torch.autograd.grad(energy - mu * population, point, create_graph=True)[0]
        H = torch.autograd.functional.hessian(lambda q: q[0] ** 2 / 2.0 + q[0] * q[1] ** 2 + lam * q[1] ** 4 / 2.0 - mu * q[1] ** 2, point)
        b = torch.autograd.grad(population, point)[0].detach().numpy()
        K = np.block([[H.detach().numpy(), -b[:, None]], [b[None, :], np.zeros((1, 1))]])
        sol = np.linalg.solve(K, np.array([0.0, 0.0, 1.0]))
        expected = lam - 1.0
        error = abs(float(sol[-1]) - expected) / max(1.0, abs(expected))
        controls.append({"lambda_C": lam, "zeta": float(sol[-1]), "expected": expected, "error": error, "pass": bool(np.isfinite(error) and error < 1e-10), "stationary_gradient_norm": float(torch.linalg.norm(gradient).detach().cpu().item())})
    return {"rows": controls, "pass": bool(all(item["pass"] for item in controls))}


def run(manifest_path: Path, output: Path) -> int:
    _torch_single_thread()
    _, records, parent_primary, _ = validate_manifest(manifest_path)
    parent_rows = parent_primary.get("rows")
    if not isinstance(parent_rows, list) or len(parent_rows) != 24:
        raise ValueError("parent primary summary does not contain 24 rows")
    parent_by_key: dict[tuple[str, float, int, float], dict[str, Any]] = {}
    for row in parent_rows:
        if not isinstance(row, dict):
            raise ValueError("malformed parent row")
        key = (row.get("cap"), float(row.get("n")), int(row.get("R")), int(row.get("N")))
        if key in parent_by_key or key not in expected_keys() or row.get("exception") is not None or row.get("stationary") is not True:
            raise ValueError("parent rows do not match accepted fixed schedule")
        parent_by_key[key] = row
    output.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, Any]] = []
    for record in records:
        key = (record["cap"], record["n"], int(record["R"]), record["N"])
        stem = f"cap_{record['cap']}_n{int(record['n'])}_N{record['N']}_R{int(record['R'])}"
        try:
            row, arrays = solve_row(record, parent_by_key[key])
            np.savez_compressed(output / (stem + "_response.npz"), **arrays)
        except Exception as exc:
            row = {
                "cap": record["cap"], "epsilon": record["epsilon"], "n": record["n"], "R": record["R"], "N": record["N"],
                "input_npz": record["path_text"], "npz": None, "energy": None, "population": None,
                "mu_relative": None, "zeta": None, "symmetry_error": None, "kkt_residual": None,
                "constraint_residual": None, "curvature_residual": None, "qualified": False,
                "exception": f"{type(exc).__name__}: {exc}", "complete_physical_matter_formation": False,
            }
        rows.append(row)
        write_json_exclusive(output / (stem + "_response.json"), row)
        print(json.dumps(strict_value(row), sort_keys=True, allow_nan=False), flush=True)
    controls = toy_controls()
    numerical_pass = bool(len(rows) == 24 and controls["pass"] and all(row.get("qualified") is True and row.get("exception") is None and finite(row) for row in rows))
    summary = {
        "schema": SCHEMA, "source": "computations/matter_formation_vortex_compressibility.py", "platform": platform.platform(),
        "parameters": {"lambda_C": LAMBDA_C, "K_Cx": core.K_CX, "eta_C": core.ETA_C, "rho0": core.RHO0, "epsilon_infinity_subtracted": True},
        "fixed_schedule": [[int(R), N] for R, N in SCHEDULE], "populations": list(POPULATIONS), "rows": rows,
        "numerical_pass": numerical_pass, "controls": controls, "complete_physical_matter_formation": False,
        "scope_caveats": ["Population curvature is evaluated only in the existing conditional loaded straight-core class; no full matter formation, loop, or longitudinal evolution is solved.", "lambda_C=1 is the supplied dimensionless witness and is not newly selected by this calculation.", "The exterior and input stationary branch are held fixed as specified."],
    }
    write_json_exclusive(output / "summary.json", summary)
    return 0 if numerical_pass else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        return run(args.manifest.resolve(), args.output.resolve())
    except Exception as exc:
        receipt = {"schema": SCHEMA, "numerical_pass": False, "verdict": "INCONCLUSIVE", "error": f"{type(exc).__name__}: {exc}", "complete_physical_matter_formation": False}
        print(json.dumps(receipt, sort_keys=True, allow_nan=False), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
