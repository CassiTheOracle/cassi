#!/usr/bin/env python3
"""Primary self-consistent carrier loading of the qualified radial vortex cores.

The charged five-field action is provided by ``matter_formation_vortex_core``;
this program adds only the supplied neutral-carrier terms and solves the fixed
24-row population/grid schedule.  The carrier population is held fixed during
each minimization, and every receipt is conditional (never a complete physical
matter-formation claim).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import time
from pathlib import Path
from typing import Any

import numpy as np
import scipy.optimize as optimize
import scipy.sparse as sparse
import torch

import matter_formation_vortex_core as core


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "matter-formation-loaded-vortex-v1"
MANIFEST_SCHEMA = "matter-formation-loaded-vortex-manifest-v1"
HEADING = "## 46. Working notes:"
LAMBDA_C = 1.0
POPULATIONS = (1.0, 16.0, 64.0)
SCHEDULE = ((32.0, 256), (32.0, 512), (64.0, 512), (64.0, 1024))
ENERGY_COMPONENTS = (
    "fundamental_radial", "adjoint_radial", "fundamental_angular",
    "adjoint_angular", "magnetic", "potential", "carrier_gradient",
    "carrier_interaction", "carrier_quartic",
)


def finite(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)) or value is None:
        return True
    if isinstance(value, (int, float, np.integer, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, np.ndarray):
        return bool(np.all(np.isfinite(value)))
    if isinstance(value, (list, tuple)):
        return all(finite(x) for x in value)
    if isinstance(value, dict):
        return all(finite(x) for x in value.values())
    return True


def strict_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): strict_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [strict_value(v) for v in value]
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


def resolve_manifest_path(manifest_path: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else manifest_path.parent / path


def validate_manifest(manifest_path: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    """Validate the frozen notebook/source/array evidence before any solve."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected loaded-vortex manifest schema")
    section = manifest.get("section")
    if not isinstance(section, dict):
        raise ValueError("manifest section record is missing")
    report_path = ROOT / str(section.get("path", ""))
    snapshot_path = resolve_manifest_path(manifest_path, str(section.get("snapshot", "")))
    if not report_path.is_file() or not snapshot_path.is_file():
        raise ValueError("frozen notebook section or snapshot is missing")
    if sha256(snapshot_path) != section.get("sha256"):
        raise ValueError("frozen section snapshot hash mismatch")
    report_text = report_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    snapshot_text = snapshot_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    heading = str(section.get("heading", HEADING))
    if not snapshot_text.startswith(heading):
        raise ValueError("section snapshot does not start at the declared heading")
    position = report_text.find(heading)
    if position < 0 or report_text[position:position + len(snapshot_text)] != snapshot_text:
        raise ValueError("live report does not contain the exact frozen section snapshot")

    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("manifest source records are missing")
    seen_sources: set[str] = set()
    for record in sources:
        if not isinstance(record, dict):
            raise ValueError("malformed source record")
        rel = str(record.get("path", ""))
        if rel in seen_sources:
            raise ValueError(f"duplicate source record: {rel}")
        seen_sources.add(rel)
        source_path = ROOT / rel
        source_snapshot = resolve_manifest_path(manifest_path, str(record.get("snapshot", "")))
        if not source_path.is_file() or not source_snapshot.is_file():
            raise ValueError(f"missing frozen source or snapshot: {rel}")
        expected_hash = record.get("sha256")
        if sha256(source_path) != expected_hash or sha256(source_snapshot) != expected_hash:
            raise ValueError(f"source hash mismatch: {rel}")
    required_sources = {
        "computations/matter_formation_vortex_loaded.py",
        "computations/verify_matter_formation_vortex_loaded.py",
        "computations/matter_formation_vortex_core.py",
        "computations/verify_matter_formation_vortex_core.py",
    }
    if not required_sources.issubset(seen_sources):
        raise ValueError("manifest omits a required calculation source")

    arrays = manifest.get("arrays")
    if not isinstance(arrays, list):
        raise ValueError("manifest array records are missing")
    expected_names = {
        f"cap_{'plus' if eps == 1 else 'minus'}_N{N}_R{int(R)}.npz"
        for eps in (1, -1) for R, N in SCHEDULE
    }
    by_name: dict[str, Path] = {}
    for record in arrays:
        if not isinstance(record, dict):
            raise ValueError("malformed array record")
        rel = str(record.get("path", ""))
        array_path = ROOT / rel
        if not array_path.is_file() or sha256(array_path) != record.get("sha256"):
            raise ValueError(f"input array hash mismatch: {rel}")
        name = array_path.name
        if name in by_name:
            raise ValueError(f"duplicate input array: {name}")
        by_name[name] = array_path
    if set(by_name) != expected_names:
        raise ValueError("input arrays do not exactly match the eight qualified core rows")
    return manifest, by_name


def consistent_mass(model: core.RadialModel) -> sparse.csr_matrix:
    """Assemble the full consistent P1 mass before boundary elimination."""
    diagonal = np.zeros(model.N + 1, dtype=np.float64)
    off_diagonal = np.zeros(model.N, dtype=np.float64)
    left, right = 1.0 - model.t, model.t
    diagonal[:-1] += np.sum(model.qweight * left * left, axis=1)
    diagonal[1:] += np.sum(model.qweight * right * right, axis=1)
    off_diagonal[:] = np.sum(model.qweight * left * right, axis=1)
    return sparse.diags((off_diagonal, diagonal, off_diagonal), (-1, 0, 1), format="csr")


def carrier_quadrature_numpy(model: core.RadialModel, f: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    fq = (1.0 - model.t[None, :]) * f[:-1, None] + model.t[None, :] * f[1:, None]
    dfq = np.broadcast_to(((f[1:] - f[:-1]) / model.dr)[:, None], fq.shape).copy()
    return fq, dfq


def normalize_f(model: core.RadialModel, mass: sparse.csr_matrix, f: np.ndarray, population: float) -> np.ndarray:
    pop = float(f @ (mass @ f))
    if not math.isfinite(pop) or pop <= 0.0:
        raise ValueError("carrier normalization has nonpositive or nonfinite consistent population")
    result = np.asarray(f, dtype=np.float64) * math.sqrt(population / pop)
    result[-1] = 0.0
    return result


def continuation(model: core.RadialModel, previous: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    old_r = np.asarray(previous["r"], dtype=np.float64)
    old_y = np.asarray(previous["y"], dtype=np.float64)
    old_f = np.asarray(previous["f"], dtype=np.float64)
    if old_y.shape != (old_r.size, 5) or old_f.shape != old_r.shape:
        raise ValueError("invalid continuation state shape")
    y = np.empty((model.N + 1, 5), dtype=np.float64)
    for j in range(5):
        y[:, j] = np.interp(model.r, old_r, old_y[:, j], left=old_y[0, j], right=model.outer[j])
    y[0] = old_y[0]
    y[-1] = model.outer
    f = np.interp(model.r, old_r, old_f, left=old_f[0], right=0.0)
    f[-1] = 0.0
    return y, f


def initial_family(model: core.RadialModel, base: dict[str, Any], population: float) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(base["y"], dtype=np.float64).copy()
    eigenvectors = np.asarray(base["carrier_eigenvectors"], dtype=np.float64)
    if y.shape != (model.N + 1, 5) or eigenvectors.shape[0] != model.N + 1 or eigenvectors.shape[1] < 1:
        raise ValueError("base retained core has unexpected coefficient/eigenvector shape")
    f = eigenvectors[:, 0].copy()
    f[-1] = 0.0
    return y, normalize_f(model, consistent_mass(model), f, population)




def joint_energy(model: core.RadialModel, y: torch.Tensor, f: torch.Tensor) -> torch.Tensor:
    core_energy = model.torch_energy(y)[0]
    t = torch.as_tensor(model.t, dtype=torch.float64)
    weight = torch.as_tensor(model.qweight, dtype=torch.float64)
    fq = (1.0 - t[None, :]) * f[:-1, None] + t[None, :] * f[1:, None]
    dfq = (f[1:] - f[:-1])[:, None] / model.dr
    yq = (1.0 - t[None, :, None]) * y[:-1, None, :2] + t[None, :, None] * y[1:, None, :2]
    fields = yq * torch.as_tensor(model.basis[..., :2], dtype=torch.float64)
    rho = torch.sum(fields * fields, dim=-1)
    carrier = core.K_CX * dfq * dfq / 2.0 - core.ETA_C * (core.RHO0 - rho) * fq * fq + LAMBDA_C * fq**4 / 2.0
    return core_energy + torch.sum(weight * carrier)


def optimize_loaded(model: core.RadialModel, y0: np.ndarray, f0: np.ndarray, population: float) -> tuple[np.ndarray, np.ndarray, optimize.OptimizeResult]:
    sqrt_y_mass = np.sqrt(model.mass[:model.N, None])
    sqrt_f_mass = np.sqrt(model.mass[:model.N])
    y_weight = torch.as_tensor(sqrt_y_mass, dtype=torch.float64)
    f_weight = torch.as_tensor(sqrt_f_mass, dtype=torch.float64)
    boundary = torch.as_tensor(model.outer, dtype=torch.float64)
    outer_f = torch.zeros(1, dtype=torch.float64)
    t = torch.as_tensor(model.t, dtype=torch.float64)
    weight = torch.as_tensor(model.qweight, dtype=torch.float64)

    def unpack(zt: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        zy = zt[:model.N * 5].reshape(model.N, 5)
        zf = zt[model.N * 5:]
        y = torch.cat((zy / y_weight, boundary[None, :]), dim=0)
        raw = torch.cat((zf / f_weight, outer_f))
        raw_q = (1.0 - t[None, :]) * raw[:-1, None] + t[None, :] * raw[1:, None]
        raw_pop = torch.sum(weight * raw_q * raw_q)
        if not bool(torch.isfinite(raw_pop) and (raw_pop > 0.0)):
            raise ValueError("optimizer carrier normalization is nonfinite or nonpositive")
        return y, raw * torch.sqrt(population / raw_pop)

    def objective(z: np.ndarray) -> tuple[float, np.ndarray]:
        zt = torch.as_tensor(z, dtype=torch.float64).requires_grad_(True)
        y, f = unpack(zt)
        energy = joint_energy(model, y, f)
        grad = torch.autograd.grad(energy, zt)[0]
        return float(energy.detach()), grad.detach().numpy()

    z0 = np.concatenate(((y0[:-1] * sqrt_y_mass).reshape(-1), f0[:-1] * sqrt_f_mass))
    result = optimize.minimize(
        objective, z0, method="L-BFGS-B", jac=True, bounds=None,
        options={"maxiter": 8000, "maxfun": 16000, "maxls": 40, "maxcor": 30, "ftol": 5e-15, "gtol": 1e-9},
    )
    z = np.asarray(result.x, dtype=np.float64)
    y = np.empty_like(y0)
    y[:-1] = z[:model.N * 5].reshape(model.N, 5) / sqrt_y_mass
    y[-1] = model.outer
    raw_f = np.empty_like(f0)
    raw_f[:-1] = z[model.N * 5:] / sqrt_f_mass
    raw_f[-1] = 0.0
    f = normalize_f(model, consistent_mass(model), raw_f, population)
    return y, f, result


def evaluate_loaded(model: core.RadialModel, y: np.ndarray, f: np.ndarray, population: float) -> dict[str, Any]:
    eval_core = model.evaluate_numpy(y)
    fq, dfq = carrier_quadrature_numpy(model, f)
    fields = eval_core["quadrature_fields"]
    rho = fields[..., 0] ** 2 + fields[..., 1] ** 2
    weights = model.qweight
    carrier_values = np.array([
        float(np.sum(weights * (core.K_CX / 2.0) * dfq ** 2)),
        float(np.sum(weights * (-core.ETA_C * (core.RHO0 - rho) * fq ** 2))),
        float(np.sum(weights * (LAMBDA_C / 2.0) * fq ** 4)),
    ], dtype=np.float64)
    components = np.array([
        eval_core["components"]["psi_radial"], eval_core["components"]["phi_radial"],
        eval_core["components"]["psi_angular"], eval_core["components"]["phi_angular"],
        eval_core["components"]["gauge"], eval_core["components"]["density_potential"] + eval_core["components"]["composition_potential"] + eval_core["components"]["higgs_potential"],
        *carrier_values,
    ], dtype=np.float64)
    total = float(np.sum(components))
    mass = consistent_mass(model)
    population_actual = float(f @ (mass @ f))
    yt = torch.as_tensor(y, dtype=torch.float64).requires_grad_(True)
    ft = torch.as_tensor(f, dtype=torch.float64).requires_grad_(True)
    joint = joint_energy(model, yt, ft)
    gy, gf = torch.autograd.grad(joint, (yt, ft))
    gradient_y = gy.detach().cpu().numpy().astype(np.float64)
    gradient_f = gf.detach().cpu().numpy().astype(np.float64)
    mu_relative = float((carrier_values[0] + carrier_values[1] + 2.0 * carrier_values[2]) / population_actual)
    constrained = gradient_f - 2.0 * mu_relative * (mass @ f)
    h, H, hres = core.h_stationarity_data(
        fields[..., 0], fields[..., 1], fields[..., 2], fields[..., 3], fields[..., 4],
        eval_core["quadrature_derivatives"][..., 0], eval_core["quadrature_derivatives"][..., 1], eval_core["quadrature_derivatives"][..., 2], eval_core["quadrature_derivatives"][..., 3], eval_core["quadrature_derivatives"][..., 4], model.qr, model.epsilon,
    )
    core_free = gradient_y[:-1]
    carrier_free = constrained[:-1]
    denom = model.mass[:model.N]
    core_rms = math.sqrt(float(np.sum(core_free * core_free / denom[:, None]) / (5.0 * np.sum(denom))))
    carrier_rms = math.sqrt(float(np.sum(carrier_free * carrier_free / denom) / np.sum(denom)))
    core_max = float(np.max(np.abs(core_free) / denom[:, None]))
    carrier_max = float(np.max(np.abs(carrier_free) / denom))
    h_relative = np.abs(hres) / np.maximum(1.0, np.abs(eval_core["L"]))
    pop_error = abs(population_actual - population) / max(1.0, abs(population))
    return {
        "energy": total, "energy_components": components, "population": population_actual,
        "mu_relative": mu_relative, "tau0": total - population_actual * mu_relative,
        "k2": (total - population_actual * mu_relative + math.pi * core.J0 / 4.0) / (core.K_CX * population_actual),
        "escape_margin": -mu_relative - (total - population_actual * mu_relative + math.pi * core.J0 / 4.0) / (2.0 * population_actual),
        "quadrature_fields": fields, "quadrature_derivatives": eval_core["quadrature_derivatives"], "h": h,
        "H": H, "h_stationary_residual": hres, "f_q": fq, "df_q": dfq,
        "gradient_y": gradient_y, "gradient_f": gradient_f, "carrier_constrained_gradient": constrained,
        "gradient_rms": core_rms, "gradient_max": core_max,
        "carrier_gradient_rms": carrier_rms, "carrier_gradient_max": carrier_max,
        "h_stationarity_max": float(np.max(h_relative)), "h_stationarity_rms": float(np.sqrt(np.sum(weights * hres ** 2) / np.sum(weights))),
        "population_error": pop_error, "core_eval": eval_core,
        "stationary": bool(core_rms < 1e-6 and carrier_rms < 1e-6 and max(core_max, carrier_max) < 1e-3 and np.max(h_relative) < 1e-10 and pop_error < 1e-10 and np.all(np.isfinite(H)) and np.all(H > 0.0)),
    }


def blank_eval(model: core.RadialModel) -> dict[str, Any]:
    nan = float("nan")
    return {
        "energy": nan, "energy_components": np.full(9, nan), "population": nan, "mu_relative": nan, "tau0": nan, "k2": nan, "escape_margin": nan,
        "quadrature_fields": np.full((model.N, 2, 5), nan), "quadrature_derivatives": np.full((model.N, 2, 5), nan), "h": np.full((model.N, 2), nan),
        "H": np.full((model.N, 2), nan), "h_stationary_residual": np.full((model.N, 2), nan), "f_q": np.full((model.N, 2), nan), "df_q": np.full((model.N, 2), nan),
        "gradient_y": np.full((model.N + 1, 5), nan), "gradient_f": np.full(model.N + 1, nan), "carrier_constrained_gradient": np.full(model.N + 1, nan),
        "gradient_rms": nan, "gradient_max": nan, "carrier_gradient_rms": nan, "carrier_gradient_max": nan, "h_stationarity_max": nan, "h_stationarity_rms": nan, "population_error": nan, "stationary": False,
    }


def run_case(output: Path, epsilon: int, population: float, R: float, N: int, initial: tuple[np.ndarray, np.ndarray] | None, previous: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    model = core.RadialModel(R, N, epsilon)
    if previous is not None:
        y0, f0 = continuation(model, previous)
    else:
        if initial is None:
            raise ValueError("missing independent-family initialization")
        y0, f0 = initial
    f0 = normalize_f(model, consistent_mass(model), f0, population)
    y, f, result = y0.copy(), f0.copy(), None
    exception_text: str | None = None
    started = time.perf_counter()
    try:
        y, f, result = optimize_loaded(model, y0, f0, population)
    except Exception as exc:
        exception_text = f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started
    try:
        data = evaluate_loaded(model, y, f, population)
    except Exception as exc:
        exception_text = exception_text or f"{type(exc).__name__}: {exc}"
        data = blank_eval(model)
    status = "optimized" if result is not None and exception_text is None else "exception"
    optimizer = {
        "success": bool(result.success) if result is not None else False,
        "status": int(result.status) if result is not None else -1,
        "message": str(result.message) if result is not None else exception_text,
        "nit": int(result.nit) if result is not None else 0,
        "nfev": int(result.nfev) if result is not None else 0,
        "elapsed_seconds": elapsed,
        "z_gradient_norm": float(np.linalg.norm(result.jac)) if result is not None and result.jac is not None else float("nan"),
    }
    cap = "plus" if epsilon == 1 else "minus"
    stem = f"cap_{cap}_n{int(population)}_N{N}_R{int(R)}"
    npz_name = stem + ".npz"
    np.savez_compressed(
        output / npz_name, r=model.r, y=y, physical_fields=data["core_eval"]["physical_fields"] if "core_eval" in data else np.full((N + 1, 5), np.nan), f=f,
        quadrature_r=model.qr, quadrature_fields=data["quadrature_fields"], quadrature_derivatives=data["quadrature_derivatives"], f_q=data["f_q"], df_q=data["df_q"], h=data["h"],
        gradient_y=data["gradient_y"], gradient_f=data["gradient_f"], carrier_constrained_gradient=data["carrier_constrained_gradient"], energy=np.array(data["energy"]),
        energy_component_names=np.array(ENERGY_COMPONENTS), energy_component_values=data["energy_components"], optimizer_success=np.array(optimizer["success"]), optimizer_status=np.array(optimizer["status"]), optimizer_nit=np.array(optimizer["nit"]), optimizer_nfev=np.array(optimizer["nfev"]), optimizer_elapsed_seconds=np.array(elapsed),
    )
    component_map = dict(zip(ENERGY_COMPONENTS, data["energy_components"].tolist()))
    row = {
        "cap": cap, "epsilon": epsilon, "n": population, "R": R, "N": N, "npz": npz_name, "status": status, "exception": exception_text,
        "C": math.pi * core.J0 / 4.0, "complete_physical_matter_formation": False,
        "energy": data["energy"], "energy_components": component_map, "population": data["population"], "mu_relative": data["mu_relative"], "tau0": data["tau0"], "k2": data["k2"], "escape_margin": data["escape_margin"],
        "gradient_rms": data["gradient_rms"], "gradient_max": data["gradient_max"], "carrier_gradient_rms": data["carrier_gradient_rms"], "carrier_gradient_max": data["carrier_gradient_max"], "h_stationarity_max": data["h_stationarity_max"], "h_stationarity_rms": data["h_stationarity_rms"], "population_error": data["population_error"], "stationary": data["stationary"], "optimizer": optimizer,
    }
    state = {"r": model.r, "y": y, "f": f}
    return row, state


def run(manifest_path: Path, output: Path) -> int:
    _torch_single_thread()
    _, arrays = validate_manifest(manifest_path)
    output.mkdir(parents=True, exist_ok=False)
    base_by_cap: dict[int, dict[str, Any]] = {}
    for epsilon in (1, -1):
        name = f"cap_{'plus' if epsilon == 1 else 'minus'}_N256_R32.npz"
        with np.load(arrays[name], allow_pickle=False) as data:
            base = {key: np.asarray(data[key]).copy() for key in ("r", "y", "carrier_eigenvectors")}
        if base["r"].shape != (257,) or base["y"].shape != (257, 5) or not finite(base):
            raise ValueError(f"invalid retained base row: {name}")
        base_by_cap[epsilon] = base
    rows: list[dict[str, Any]] = []
    for epsilon in (1, -1):
        for population in POPULATIONS:
            previous: dict[str, Any] | None = None
            initial: tuple[np.ndarray, np.ndarray] | None = None
            for R, N in SCHEDULE:
                model = core.RadialModel(R, N, epsilon)
                if previous is None:
                    initial = initial_family(model, base_by_cap[epsilon], population)
                row, previous = run_case(output, epsilon, population, R, N, initial, previous)
                rows.append(row)
                write_json_exclusive(output / Path(row["npz"]).with_suffix(".json"), row)
                print(json.dumps(strict_value(row), sort_keys=True, allow_nan=False), flush=True)
    summary = {
        "schema": SCHEMA, "source": "computations/matter_formation_vortex_loaded.py", "platform": platform.platform(),
        "parameters": {"rho0": core.RHO0, "a": core.A, "d": core.D, "v": core.V, "g": core.G, "lambda_rho": core.LAMBDA_RHO, "lambda_phi": core.LAMBDA_PHI, "lambda_H": core.LAMBDA_H, "K_Cx": core.K_CX, "eta_C": core.ETA_C, "lambda_C": LAMBDA_C, "phi": core.PHI, "c0": core.C0, "m": core.M_WINDING, "J0": core.J0, "C": math.pi * core.J0 / 4.0, "epsilon_infinity_subtracted": True},
        "fixed_schedule": [[int(R), N] for R, N in SCHEDULE], "populations": list(POPULATIONS), "rows": rows,
        "all_rows_numerically_qualified": bool(len(rows) == 24 and all(bool(row["stationary"]) and row["exception"] is None and finite(row) for row in rows)),
        "complete_physical_matter_formation": False,
        "scope_caveats": ["Loaded stationary radial straight-core families only; no angular stability, formation history or three-dimensional loop is solved.", "lambda_C=1 is a supplied dimensionless witness, not a derived or physically selected constant.", "The zero reference subtracts epsilon_infinity; no physical mass, spin or statistics claim is made."],
    }
    write_json_exclusive(output / "summary.json", summary)
    return 0 if summary["all_rows_numerically_qualified"] else 1


def _torch_single_thread() -> None:
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        return run(args.manifest.resolve(), args.output.resolve())
    except Exception as exc:
        receipt = {"schema": SCHEMA, "verdict": "INCONCLUSIVE", "error": f"{type(exc).__name__}: {exc}", "complete_physical_matter_formation": False}
        print(json.dumps(receipt, sort_keys=True, allow_nan=False), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
