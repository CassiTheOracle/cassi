#!/usr/bin/env python3
"""Primary smooth vacuum-to-bound-state formation calculation."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PREREG = ROOT / "computations" / "matter-formation-smooth-bag-transition-prereg.md"
SCHEMA = "cassi.matter-formation.smooth-bag-transition.v1"
V = 1.0
LAMBDA = 0.25
G = 6.0
RADIUS = 16.0
AMPLITUDE = 1.5
WIDTH = 2.5
SWITCH_TIME = 2.0
FINAL_TIME = 12.0
GRIDS = {
    "G0": (48, RADIUS / 48.0, 0.002),
    "G1": (72, RADIUS / 72.0, 0.001),
    "G2": (96, RADIUS / 96.0, 0.0005),
}


class FormationError(RuntimeError):
    pass


def canonical_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def raw_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return json_ready(value.item())
    if isinstance(value, float):
        if not math.isfinite(value):
            raise FormationError("nonfinite receipt value")
        return value
    return value


def write_exclusive(path: Path, payload: Any) -> None:
    if path.exists():
        raise FormationError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_ready(payload), indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def radial_grid(n: int) -> tuple[np.ndarray, float]:
    dr = RADIUS / n
    return (np.arange(n, dtype=np.float64) + 0.5) * dr, dr


def dense_hamiltonian(sigma: np.ndarray, dr: float) -> np.ndarray:
    n = sigma.size
    h = np.zeros((2 * n, 2 * n), dtype=np.complex128)
    idx = np.arange(n)
    h[idx, idx] = G * sigma
    h[n + idx, n + idx] = -G * sigma
    d = 1.0 / (2.0 * dr)
    for i in range(n - 1):
        h[i, n + i + 1] += -d
        h[i + 1, n + i] += d
        h[n + i, i + 1] += d
        h[n + i + 1, i] += -d
    radius = (np.arange(n, dtype=np.float64) + 0.5) * dr
    h[idx, n + idx] += -1.0 / radius
    h[n + idx, idx] += -1.0 / radius
    if np.max(np.abs(h - h.conj().T)) > 1.0e-13:
        raise FormationError("Hamiltonian is not Hermitian")
    return h


def smooth_bump(s: float) -> float:
    if s <= 0.0:
        return 0.0
    if s >= 1.0:
        return 1.0
    left = math.exp(-1.0 / s)
    right = math.exp(-1.0 / (1.0 - s))
    return left / (left + right)


def profile(t: float, radius: np.ndarray, amplitude: float = AMPLITUDE) -> np.ndarray:
    factor = smooth_bump(t / SWITCH_TIME)
    return V - amplitude * factor * np.exp(-0.5 * (radius / WIDTH) ** 2)


def vacuum_columns(h: np.ndarray, dr: float, negative: bool) -> tuple[np.ndarray, np.ndarray]:
    values, vectors = np.linalg.eigh(h)
    n = h.shape[0] // 2
    selected = values < -1.0e-10 if negative else values > 1.0e-10
    if int(np.count_nonzero(selected)) != n:
        raise FormationError("energy split does not contain exactly N states")
    columns = vectors[:, selected] / math.sqrt(dr)
    metric_error = float(np.max(np.abs(dr * (columns.conj().T @ columns) - np.eye(n))))
    if metric_error > 2.0e-12:
        raise FormationError(f"eigenvector metric error {metric_error}")
    return values[selected], columns


def rk4_step(u: np.ndarray, t: float, dt: float, radius: np.ndarray, dr: float) -> np.ndarray:
    def rhs(x: np.ndarray, at: float) -> np.ndarray:
        return -1j * (dense_hamiltonian(profile(at, radius), dr) @ x)
    k1 = rhs(u, t)
    k2 = rhs(u + 0.5 * dt * k1, t + 0.5 * dt)
    k3 = rhs(u + 0.5 * dt * k2, t + 0.5 * dt)
    k4 = rhs(u + dt * k3, t + dt)
    return u + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0


def spatial_metrics(bound: np.ndarray, radius: np.ndarray, dr: float) -> tuple[float, float]:
    n = radius.size
    density = np.abs(bound[:n, 0]) ** 2 + np.abs(bound[n:, 0]) ** 2
    norm = float(np.sum(density) * dr)
    core = radius < 4.0
    return float(np.sum(density[core]) * dr / norm), math.sqrt(float(np.sum(radius * radius * density) * dr / norm))


def final_metrics(u: np.ndarray, radius: np.ndarray, dr: float, final_vectors: np.ndarray, final_values: np.ndarray) -> dict[str, float]:
    n = radius.size
    positive = final_values > 1.0e-10
    negative = final_values < -1.0e-10
    p = final_vectors[:, positive] / math.sqrt(dr)
    q = final_vectors[:, negative] / math.sqrt(dr)
    pair_coeff = dr * (p.conj().T @ u)
    hole_coeff = dr * (q.conj().T @ u)
    positive_values = final_values[positive]
    negative_values = final_values[negative]
    bound = p[:, :1]
    bound_hole = q[:, -1:]
    bound_coeff = dr * (bound.conj().T @ u)
    hole_bound_coeff = dr * (bound_hole.conj().T @ u)
    core_probability, rms = spatial_metrics(bound, radius, dr)
    norm_error = float(np.max(np.abs(dr * (u.conj().T @ u) - np.eye(n))))
    return {
        "pair_number": float(np.sum(np.abs(pair_coeff) ** 2)),
        "bound_occupation": float(np.sum(np.abs(bound_coeff) ** 2)),
        "bound_hole_occupation": float(n - np.sum(np.abs(hole_bound_coeff) ** 2)),
        "pair_hole_gap": float(abs(np.sum(np.abs(pair_coeff) ** 2) - (n - np.sum(np.abs(hole_coeff) ** 2)))),
        "bound_energy": float(positive_values[0]),
        "negative_bound_energy": float(negative_values[-1]),
        "bound_core_probability": core_probability,
        "bound_rms_radius": rms,
        "mode_metric_error": norm_error,
        "final_profile_center_deficit": float(1.0 - profile(FINAL_TIME, radius)[0]),
    }


def evolve_grid(name: str, output: Path, amplitude: float = AMPLITUDE) -> dict[str, Any]:
    n, dr, dt = GRIDS[name]
    radius, _ = radial_grid(n)
    h0 = dense_hamiltonian(profile(0.0, radius, amplitude), dr)
    _, u = vacuum_columns(h0, dr, negative=True)
    steps = round(FINAL_TIME / dt)
    checkpoint_times = np.asarray((0.0, SWITCH_TIME, 4.0, 8.0, FINAL_TIME), dtype=np.float64)
    checkpoint_steps = [round(float(t) / dt) for t in checkpoint_times]
    states: list[np.ndarray] = [u.copy()]
    time_now = 0.0
    checkpoint_index = 1
    for step in range(1, steps + 1):
        u = rk4_step(u, time_now, dt, radius, dr)
        time_now += dt
        if checkpoint_index < len(checkpoint_steps) and step == checkpoint_steps[checkpoint_index]:
            states.append(u.copy())
            checkpoint_index += 1
    if checkpoint_index != len(checkpoint_steps):
        raise FormationError(f"checkpoint schedule failed for {name}")
    final_h = dense_hamiltonian(profile(FINAL_TIME, radius, amplitude), dr)
    final_values, final_vectors = np.linalg.eigh(final_h)
    metrics = final_metrics(u, radius, dr, final_vectors, final_values)
    metrics["amplitude"] = float(amplitude)
    metrics["grid"] = name
    metrics["N"] = n
    metrics["dr"] = dr
    metrics["dt"] = dt
    metrics["steps"] = steps
    metrics["duration"] = FINAL_TIME
    metrics["checkpoint_metric_errors"] = [
        float(np.max(np.abs(dr * (state.conj().T @ state) - np.eye(n)))) for state in states
    ]
    archive = output / f"{name}.npz"
    with archive.open("xb") as stream:
        np.savez_compressed(stream, time=checkpoint_times, u_re=np.asarray([x.real for x in states]), u_im=np.asarray([x.imag for x in states]))
    metrics["archive"] = archive.name
    metrics["archive_sha256"] = raw_sha(archive)
    return metrics


def static_control(output: Path) -> dict[str, float]:
    name = "G1"
    n, dr, _ = GRIDS[name]
    radius, _ = radial_grid(n)
    h0 = dense_hamiltonian(profile(0.0, radius, amplitude=0.0), dr)
    final_values, final_vectors = np.linalg.eigh(h0)
    _, u = vacuum_columns(h0, dr, negative=True)
    p = final_vectors[:, final_values > 0] / math.sqrt(dr)
    coeff = dr * (p.conj().T @ u)
    metrics = final_metrics(u, radius, dr, final_vectors, final_values)
    return {
        "pair_number": float(np.sum(np.abs(coeff) ** 2)),
        "bound_occupation": metrics["bound_occupation"],
        "mode_metric_error": metrics["mode_metric_error"],
    }



def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FormationError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    source_dir = output / "sources"
    source_dir.mkdir()
    for path in (SELF, PREREG):
        target = source_dir / relative(path).replace("/", "__")
        shutil.copyfile(path, target)
    runs = {name: evolve_grid(name, output) for name in GRIDS}
    control = static_control(output)
    checks = {
        "finite_grid_receipts": all(math.isfinite(float(value)) for row in runs.values() for value in row.values() if isinstance(value, (int, float))),
        "positive_pair_number": all(row["pair_number"] > 0.05 for row in runs.values()),
        "positive_bound_occupation": all(row["bound_occupation"] > 0.10 for row in runs.values()),
        "particle_hole_agreement": all(row["pair_hole_gap"] < 0.02 for row in runs.values()),
        "localized_bound_mode": all(row["bound_core_probability"] > 0.50 and row["bound_rms_radius"] < 5.0 for row in runs.values()),
        "mode_metric": all(max(row["checkpoint_metric_errors"]) < 1.0e-8 for row in runs.values()),
        "static_control": control["pair_number"] < 1.0e-10 and control["bound_occupation"] < 1.0e-10,
    }
    ordered = [runs[name] for name in GRIDS]
    checks["grid_pair_convergence"] = all(abs(ordered[i]["pair_number"] - ordered[i + 1]["pair_number"]) < 0.15 for i in range(2))
    checks["grid_bound_convergence"] = all(abs(ordered[i]["bound_occupation"] - ordered[i + 1]["bound_occupation"]) < 0.15 for i in range(2))
    checks["grid_spatial_convergence"] = all(
        abs(ordered[i]["bound_core_probability"] - ordered[i + 1]["bound_core_probability"]) < 0.10
        and abs(ordered[i]["bound_rms_radius"] - ordered[i + 1]["bound_rms_radius"]) < 0.25
        for i in range(2)
    )
    passed = all(checks.values())
    payload = {
        "schema": SCHEMA,
        "protocol": relative(PREREG),
        "protocol_sha256": canonical_sha(PREREG),
        "source": {"path": relative(SELF), "sha256": canonical_sha(SELF)},
        "parameters": {"v": V, "lambda": LAMBDA, "g": G, "radius": RADIUS, "amplitude": AMPLITUDE, "width": WIDTH, "switch_time": SWITCH_TIME, "final_time": FINAL_TIME, "grids": {name: {"N": row["N"], "dr": row["dr"], "dt": row["dt"]} for name, row in runs.items()}},
        "runs": runs,
        "static_control": control,
        "checks": [{"name": name, "pass": bool(value)} for name, value in checks.items()],
        "numerical_pass": passed,
        "scientific_verdict": "CAPTURED—conditional smooth vacuum-to-bound-state formation" if passed else "DOES NOT EMERGE—conditional smooth vacuum-to-bound-state formation",
        "complete_physical_matter_formation": False,
        "failures": [name for name, value in checks.items() if not value],
        "elapsed_seconds": time.perf_counter() - started,
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform()},
    }
    write_exclusive(output / "results.json", payload)
    print(json.dumps({"scientific_verdict": payload["scientific_verdict"], "checks": payload["checks"]}, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
