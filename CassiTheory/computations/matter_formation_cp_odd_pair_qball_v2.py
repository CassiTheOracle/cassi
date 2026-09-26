#!/usr/bin/env python3
"""Run the preregistered CP-odd vacuum-to-carrier calculation.

Run from the CassiTheory root:
    python computations/matter_formation_cp_odd_pair_qball_v2.py \
        --output-dir runs/20260912_matter_formation_cp_odd_pair_qball_v2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "matter-formation-cp-odd-pair-qball-v2-prereg.md"
SOURCE = Path(__file__).resolve()
DEFAULT_OUTPUT = ROOT / "runs" / "20260912_matter_formation_cp_odd_pair_qball_v2"
SCHEMA = "cassi.matter-formation.cp-odd-pair-qball.v2"
RADIUS = 32.0
N_PRIMARY = 512
N_FINE = 1024
DT = 0.002
T_FINAL = 48.0
SAVE_INTERVAL = 4.0
MODES = 32
SEED = 20260912
M = 1.0
LAMBDA = 2.0
G = 1.25
M_A = 2.0
KAPPA = 0.8
PULSE_AMPLITUDE = 4.0
PULSE_RADIUS = 4.0
PULSE_WIDTH = 1.5
CORE_RADIUS = 6.0
EXTERIOR_RADIUS = 12.0


class FormationError(RuntimeError):
    """Typed failure of the frozen execution contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def source_record(path: Path) -> dict[str, Any]:
    return {"path": relative(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        raise FormationError(f"nonfinite value in receipt: {value}")
    return value


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(json_ready(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def prepare_output(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise FormationError(f"refusing to overwrite nonempty output: {path}")
    path.mkdir(parents=True, exist_ok=True)


def radial_grid(count: int) -> tuple[np.ndarray, float]:
    spacing = RADIUS / count
    return (np.arange(count, dtype=np.float64) + 0.5) * spacing, spacing


def vacuum_draw(r: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    modes = np.arange(1, MODES + 1, dtype=np.float64)
    omega = np.sqrt(M * M + (modes * math.pi / RADIUS) ** 2)
    rng = np.random.Generator(np.random.PCG64(SEED))
    xi_x = rng.normal(size=MODES)
    xi_y = rng.normal(size=MODES)
    pi_x = rng.normal(size=MODES)
    pi_y = rng.normal(size=MODES)
    basis = math.sqrt(2.0 / RADIUS) * np.sin(
        modes[:, None] * math.pi * r[None, :] / RADIUS
    )
    q_x = xi_x / np.sqrt(4.0 * omega)
    q_y = xi_y / np.sqrt(4.0 * omega)
    p_x = np.sqrt(omega / 4.0) * pi_x
    p_y = np.sqrt(omega / 4.0) * pi_y
    return q_x @ basis, q_y @ basis, p_x @ basis, p_y @ basis


def initial_state(count: int, pulse_sign: int) -> tuple[np.ndarray, ...]:
    r, _ = radial_grid(count)
    ux, uy, px, py = vacuum_draw(r)
    if pulse_sign < 0:
        uy = -uy
        py = -py
    pulse = pulse_sign * PULSE_AMPLITUDE * np.exp(
        -0.5 * ((r - PULSE_RADIUS) / PULSE_WIDTH) ** 2
    )
    return ux, uy, pulse * r, px, py, np.zeros_like(r)


def laplacian_reduced(values: np.ndarray, spacing: float) -> np.ndarray:
    extended = np.empty(values.size + 2, dtype=np.float64)
    extended[1:-1] = values
    extended[0] = -values[0]
    extended[-1] = -values[-1]
    return (extended[2:] - 2.0 * extended[1:-1] + extended[:-2]) / (spacing * spacing)


def rhs(state: tuple[np.ndarray, ...], r: np.ndarray, spacing: float) -> tuple[np.ndarray, ...]:
    ux, uy, v, px, py, pv = state
    rho_u = ux * ux + uy * uy
    physical_s = rho_u / (r * r)
    coefficient = M * M - 2.0 * LAMBDA * physical_s + 3.0 * G * physical_s * physical_s
    ax = laplacian_reduced(ux, spacing) - coefficient * ux + KAPPA * (v / r) * uy
    ay = laplacian_reduced(uy, spacing) - coefficient * uy + KAPPA * (v / r) * ux
    av = laplacian_reduced(v, spacing) - M_A * M_A * v + KAPPA * ux * uy / r
    return px, py, pv, ax, ay, av


def state_add(
    state: tuple[np.ndarray, ...], other: tuple[np.ndarray, ...], factor: float
) -> tuple[np.ndarray, ...]:
    return tuple(a + factor * b for a, b in zip(state, other))  # type: ignore[return-value]


def state_rk4_step(
    state: tuple[np.ndarray, ...], r: np.ndarray, spacing: float, dt: float
) -> tuple[np.ndarray, ...]:
    k1 = rhs(state, r, spacing)
    k2 = rhs(state_add(state, k1, 0.5 * dt), r, spacing)
    k3 = rhs(state_add(state, k2, 0.5 * dt), r, spacing)
    k4 = rhs(state_add(state, k3, dt), r, spacing)
    return tuple(
        a + (dt / 6.0) * (b + 2.0 * c + 2.0 * d + e)
        for a, b, c, d, e in zip(state, k1, k2, k3, k4)
    )  # type: ignore[return-value]


def gradient(values: np.ndarray, spacing: float) -> np.ndarray:
    extended = np.empty(values.size + 2, dtype=np.float64)
    extended[1:-1] = values
    extended[0] = -values[0]
    extended[-1] = -values[-1]
    return (extended[2:] - extended[:-2]) / (2.0 * spacing)


def observables(
    state: tuple[np.ndarray, ...], r: np.ndarray, spacing: float
) -> dict[str, float]:
    ux, uy, v, px, py, pv = state
    rho_u = ux * ux + uy * uy
    physical_s = rho_u / (r * r)
    grad_x = gradient(ux, spacing)
    grad_y = gradient(uy, spacing)
    grad_v = gradient(v, spacing)
    e_carrier_density = (
        0.5 * (px * px + py * py + grad_x * grad_x + grad_y * grad_y)
        + 0.5 * M * M * rho_u
        - 0.5 * LAMBDA * rho_u * rho_u / (r * r)
        + 0.5 * G * rho_u * rho_u * rho_u / (r**4)
    )
    e_support_density = (
        0.5 * (px * px + py * py + grad_x * grad_x + grad_y * grad_y)
        + 0.5 * M * M * rho_u
        + 0.5 * G * rho_u * rho_u * rho_u / (r**4)
    )
    e_source = -KAPPA * v * ux * uy / r
    e_auxiliary = 0.5 * (pv * pv + grad_v * grad_v + M_A * M_A * v * v)
    e_carrier = float(4.0 * math.pi * np.sum(e_carrier_density) * spacing)
    e_support = float(4.0 * math.pi * np.sum(e_support_density) * spacing)
    e_full = float(4.0 * math.pi * np.sum(e_carrier_density + e_auxiliary + e_source) * spacing)
    number_total = float(4.0 * math.pi * np.sum(rho_u) * spacing)
    core_mask = r <= CORE_RADIUS
    exterior_mask = r >= EXTERIOR_RADIUS
    number_core = float(4.0 * math.pi * np.sum(rho_u[core_mask]) * spacing)
    charge = float(4.0 * math.pi * np.sum((ux * py - uy * px)) * spacing)
    rms = float(
        math.sqrt(
            np.sum(r * r * rho_u) / max(np.sum(rho_u), np.finfo(float).tiny)
        )
    )
    core_density = float(
        3.0 * np.sum(rho_u[core_mask]) * spacing / (CORE_RADIUS**3)
    )
    exterior_support = float(
        np.sum(e_support_density[exterior_mask])
        / max(np.sum(e_support_density), np.finfo(float).tiny)
    )
    return {
        "carrier_energy": e_carrier,
        "support_energy_diagnostic": e_support,
        "full_energy": e_full,
        "number_total": number_total,
        "number_core": number_core,
        "core_fraction": number_core / max(number_total, np.finfo(float).tiny),
        "charge": charge,
        "rms_radius": rms,
        "core_density": core_density,
        "exterior_support_fraction": exterior_support,
        "pulse_core_max": float(np.max(np.abs(v[core_mask] / r[core_mask]))),
    }


def archive_run(
    output: Path,
    name: str,
    count: int,
    pulse_sign: int,
    capture_arrays: bool = True,
) -> dict[str, Any]:
    r, spacing = radial_grid(count)
    state = initial_state(count, pulse_sign)
    checkpoints = np.arange(0.0, T_FINAL + 0.5 * SAVE_INTERVAL, SAVE_INTERVAL)
    checkpoint_rows: list[dict[str, Any]] = []
    archive: dict[str, list[np.ndarray]] = {key: [] for key in ("ux", "uy", "v", "px", "py", "pv")}
    steps_per_checkpoint = round(SAVE_INTERVAL / DT)
    total_steps = round(T_FINAL / DT)
    if steps_per_checkpoint * len(checkpoints[:-1]) != total_steps:
        raise FormationError("checkpoint schedule is not integral")
    start = time.perf_counter()
    checkpoint_index = 0
    for step in range(total_steps + 1):
        if step == checkpoint_index * steps_per_checkpoint:
            row = {"time": float(checkpoints[checkpoint_index]), **observables(state, r, spacing)}
            checkpoint_rows.append(row)
            if capture_arrays:
                for key, value in zip(archive, state):
                    archive[key].append(value.copy())
            checkpoint_index += 1
        if step == total_steps:
            break
        state = state_rk4_step(state, r, spacing, DT)
        if not all(np.all(np.isfinite(value)) for value in state):
            raise FormationError(f"nonfinite state in {name} at step {step + 1}")
    final = checkpoint_rows[-1]
    output_path = output / f"{name}.npz"
    np.savez_compressed(
        output_path,
        r=r,
        times=checkpoints,
        **{key: np.asarray(values) for key, values in archive.items()},
    )
    return {
        "name": name,
        "count": count,
        "spacing": spacing,
        "pulse_sign": pulse_sign,
        "steps": total_steps,
        "dt": DT,
        "elapsed_seconds": time.perf_counter() - start,
        "archive": output_path.name,
        "rows": checkpoint_rows,
        "final": final,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    prepare_output(output)
    started = time.perf_counter()
    source_paths = (PROTOCOL, SOURCE)
    source_records = [source_record(path) for path in source_paths]
    for path in source_paths:
        destination = output / "sources" / relative(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)

    runs = {
        "vacuum_control": archive_run(output, "vacuum_control", N_PRIMARY, 0),
        "positive": archive_run(output, "positive", N_PRIMARY, +1),
        "negative": archive_run(output, "negative", N_PRIMARY, -1),
        "positive_fine": archive_run(output, "positive_fine", N_FINE, +1),
    }
    positive_rows = runs["positive"]["rows"]
    vacuum_rows = runs["vacuum_control"]["rows"]
    late_positive = [row for row in positive_rows if row["time"] >= 24.0]
    late_vacuum = [row for row in vacuum_rows if row["time"] >= 24.0]
    late_q = np.asarray([row["charge"] for row in late_positive], dtype=np.float64)
    late_q_drift = float(np.max(late_q) - np.min(late_q)) / max(
        float(np.max(np.abs(late_q))), np.finfo(float).tiny
    )
    vacuum_density = float(np.mean([row["core_density"] for row in late_vacuum]))
    final = runs["positive"]["final"]
    fine = runs["positive_fine"]["final"]
    negative = runs["negative"]["final"]
    resolution = {
        key: abs(float(fine[key]) - float(final[key]))
        / max(1.0, abs(float(final[key])), abs(float(fine[key])))
        for key in ("carrier_energy", "charge", "rms_radius", "core_density", "exterior_support_fraction")
    }
    cp_error = max(
        abs(positive_rows[index][key] - runs["negative"]["rows"][index][key])
        for index in range(len(positive_rows))
        for key in ("carrier_energy", "full_energy", "number_total", "rms_radius")
    )
    predicates = {
        "core_density_amplified": final["core_density"] >= 4.0 * vacuum_density,
        "core_retention": final["core_fraction"] >= 0.80,
        "localized_support": final["exterior_support_fraction"] < 0.20,
        "charge_magnitude": abs(final["charge"]) >= 0.5,
        "post_pulse_charge_drift": late_q_drift < 0.05,
        "subthreshold_energy_per_charge": final["carrier_energy"] / max(abs(final["charge"]), np.finfo(float).tiny) < M,
        "resolution": all(value < 0.05 for value in resolution.values()),
        "cp_conjugacy": cp_error < 1.0e-10 and final["charge"] * negative["charge"] < 0.0,
    }
    scientific_pass = all(predicates.values())
    payload = {
        "schema": SCHEMA,
        "protocol": relative(PROTOCOL),
        "protocol_sha256": sha256(PROTOCOL),
        "source_records": source_records,
        "parameters": {
            "radius": RADIUS,
            "primary_grid": N_PRIMARY,
            "fine_grid": N_FINE,
            "dt": DT,
            "T_final": T_FINAL,
            "save_interval": SAVE_INTERVAL,
            "modes": MODES,
            "seed": SEED,
            "m": M,
            "lambda": LAMBDA,
            "g": G,
            "m_a": M_A,
            "kappa": KAPPA,
            "pulse_amplitude": PULSE_AMPLITUDE,
            "pulse_radius": PULSE_RADIUS,
            "pulse_width": PULSE_WIDTH,
        },
        "runs": runs,
        "controls": {
            "vacuum_late_core_density": vacuum_density,
            "late_charge_relative_drift": late_q_drift,
            "cp_max_metric_error": cp_error,
            "resolution_relative_errors": resolution,
        },
        "predicates": predicates,
        "numerical_pass": True,
        "scientific_verdict": (
            "CAPTURED—conditional CP-odd vacuum-to-carrier formation"
            if scientific_pass
            else "DOES NOT EMERGE—conditional CP-odd vacuum-to-carrier formation"
        ),
        "complete_physical_matter_formation": False,
        "elapsed_seconds": time.perf_counter() - started,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
    }
    write_json(output / "result.json", payload)
    print(json.dumps({"scientific_verdict": payload["scientific_verdict"], "predicates": predicates}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"formation primary failed: {exc}", file=sys.stderr)
        raise
