#!/usr/bin/env python3
"""Run the preregistered compact CP-pump carrier-formation calculation."""
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
PROTOCOL = ROOT / "computations" / "matter-formation-compact-cp-pump-qball-v3b-prereg.md"
SOURCE = Path(__file__).resolve()
DEFAULT_OUTPUT = ROOT / "runs" / "20260912_matter_formation_compact_cp_pump_qball_v3c"
SCHEMA = "cassi.matter-formation.compact-cp-pump-qball.v3b"

RADIUS = 48.0
N_PRIMARY = 384
N_FINE = 768
DT_PRIMARY = 0.003
DT_FINE = 0.0015
T_FINAL = 78.0
SAVE_INTERVAL = 6.0
MODES = 64
SEED = 20260912
M = 1.0
LAMBDA = 2.0
G = 1.25
KAPPA = 0.5
PULSE_AMPLITUDE = 0.8
PULSE_WIDTH = 8.0
PULSE_FREQUENCY = 1.0
PULSE_DURATION = 24.0
CORE_RADIUS = 12.0
EXTERIOR_RADIUS = 20.0
LATE_START = 60.0

State = tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]


class FormationError(RuntimeError):
    """Typed failure of the frozen execution contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
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
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def write_json(path: Path, payload: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(json_ready(payload), stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


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
    return (
        (xi_x / np.sqrt(4.0 * omega)) @ basis,
        (xi_y / np.sqrt(4.0 * omega)) @ basis,
        (np.sqrt(omega / 4.0) * pi_x) @ basis,
        (np.sqrt(omega / 4.0) * pi_y) @ basis,
    )


def initial_state(count: int, arm: int) -> State:
    r, _ = radial_grid(count)
    ux, uy, px, py = vacuum_draw(r)
    if arm < 0:
        uy = -uy
        py = -py
    return ux, uy, px, py


def pump_components(
    t: float, r: np.ndarray, arm: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if arm == 0 or t < 0.0 or t >= PULSE_DURATION:
        zeros = np.zeros_like(r)
        return zeros, zeros, zeros, zeros
    phase_sign = -1.0 if arm < 0 else 1.0
    envelope = math.sin(math.pi * t / PULSE_DURATION) ** 2
    envelope_dot = (
        math.pi / PULSE_DURATION * math.sin(2.0 * math.pi * t / PULSE_DURATION)
    )
    profile = np.exp(-0.5 * (r / PULSE_WIDTH) ** 2)
    amplitude = PULSE_AMPLITUDE * profile
    phase = PULSE_FREQUENCY * t
    cos_phase = math.cos(phase)
    sin_phase = math.sin(phase)
    jr = amplitude * envelope * cos_phase
    ji = phase_sign * amplitude * envelope * sin_phase
    jr_dot = amplitude * (envelope_dot * cos_phase - envelope * PULSE_FREQUENCY * sin_phase)
    ji_dot = phase_sign * amplitude * (
        envelope_dot * sin_phase + envelope * PULSE_FREQUENCY * cos_phase
    )
    return jr, ji, jr_dot, ji_dot


def laplacian_open(values: np.ndarray, momenta: np.ndarray, spacing: float) -> np.ndarray:
    extended = np.empty(values.size + 2, dtype=np.float64)
    extended[1:-1] = values
    extended[0] = -values[0]
    extended[-1] = values[-1] - spacing * momenta[-1]
    return (extended[2:] - 2.0 * extended[1:-1] + extended[:-2]) / (spacing * spacing)
 
def laplacian_static(values: np.ndarray, spacing: float) -> np.ndarray:
    extended = np.empty(values.size + 2, dtype=np.float64)
    extended[1:-1] = values
    extended[0] = -values[0]
    extended[-1] = values[-1]
    return (extended[2:] - 2.0 * extended[1:-1] + extended[:-2]) / (spacing * spacing)


def compatible_carrier_energy(state: State, r: np.ndarray, spacing: float) -> float:
    ux, uy, px, py = state
    rho = ux * ux + uy * uy
    static_lap_x = laplacian_static(ux, spacing)
    static_lap_y = laplacian_static(uy, spacing)
    compatible_gradient = -0.5 * (ux * static_lap_x + uy * static_lap_y)
    local_terms = (
        0.5 * (px * px + py * py)
        + 0.5 * M * M * rho
        - 0.5 * LAMBDA * rho * rho / (r * r)
        + 0.5 * G * rho * rho * rho / (r**4)
    )
    return float(4.0 * math.pi * np.sum(local_terms + compatible_gradient) * spacing)


 


def gradient_open(values: np.ndarray, momenta: np.ndarray, spacing: float) -> np.ndarray:
    extended = np.empty(values.size + 2, dtype=np.float64)
    extended[1:-1] = values
    extended[0] = -values[0]
    extended[-1] = values[-1] - spacing * momenta[-1]
    return (extended[2:] - extended[:-2]) / (2.0 * spacing)


def rhs(state: State, t: float, r: np.ndarray, spacing: float, arm: int) -> State:
    ux, uy, px, py = state
    rho = ux * ux + uy * uy
    physical_s = rho / (r * r)
    coefficient = M * M - 2.0 * LAMBDA * physical_s + 3.0 * G * physical_s * physical_s
    jr, ji, _jr_dot, _ji_dot = pump_components(t, r, arm)
    return (
        px,
        py,
        laplacian_open(ux, px, spacing) - coefficient * ux + 2.0 * KAPPA * (jr * ux - ji * uy),
        laplacian_open(uy, py, spacing) - coefficient * uy + 2.0 * KAPPA * (-jr * uy - ji * ux),
    )


def state_add(state: State, other: State, factor: float) -> State:
    return tuple(a + factor * b for a, b in zip(state, other))  # type: ignore[return-value]


def rk4_step(state: State, t: float, r: np.ndarray, spacing: float, dt: float, arm: int) -> State:
    k1 = rhs(state, t, r, spacing, arm)
    k2 = rhs(state_add(state, k1, 0.5 * dt), t + 0.5 * dt, r, spacing, arm)
    k3 = rhs(state_add(state, k2, 0.5 * dt), t + 0.5 * dt, r, spacing, arm)
    k4 = rhs(state_add(state, k3, dt), t + dt, r, spacing, arm)
    return tuple(
        a + (dt / 6.0) * (b + 2.0 * c + 2.0 * d + e)
        for a, b, c, d, e in zip(state, k1, k2, k3, k4)
    )  # type: ignore[return-value]


def rates(
    state: State, t: float, r: np.ndarray, spacing: float, arm: int
) -> dict[str, float]:
    ux, uy, px, py = state
    jr, ji, jr_dot, ji_dot = pump_components(t, r, arm)
    source_charge_density = -4.0 * KAPPA * jr * ux * uy - 2.0 * KAPPA * ji * (ux * ux - uy * uy)
    source_charge = float(4.0 * math.pi * np.sum(source_charge_density) * spacing)
    ghost_x = ux[-1] - spacing * px[-1]
    ghost_y = uy[-1] - spacing * py[-1]
    boundary_charge = float(
        4.0 * math.pi * (ux[-1] * ghost_y - uy[-1] * ghost_x) / spacing
    )
    pair_work_density = -KAPPA * (
        jr_dot * (ux * ux - uy * uy) - 2.0 * ji_dot * ux * uy
    )
    pump_work = float(4.0 * math.pi * np.sum(pair_work_density) * spacing)
    boundary_energy = float(-4.0 * math.pi * (px[-1] * px[-1] + py[-1] * py[-1]))
    return {
        "source_charge_rate": source_charge,
        "boundary_charge_flux": boundary_charge,
        "pump_work_rate": pump_work,
        "boundary_energy_flux": boundary_energy,
    }


def observables(
    state: State,
    t: float,
    r: np.ndarray,
    spacing: float,
    arm: int,
    ledger: dict[str, float],
    initial_full_energy: float,
) -> dict[str, float]:
    ux, uy, px, py = state
    rho = ux * ux + uy * uy
    grad_x = gradient_open(ux, px, spacing)
    grad_y = gradient_open(uy, py, spacing)
    carrier_density = (
        0.5 * (px * px + py * py + grad_x * grad_x + grad_y * grad_y)
        + 0.5 * M * M * rho
        - 0.5 * LAMBDA * rho * rho / (r * r)
        + 0.5 * G * rho * rho * rho / (r**4)
    )
    support_density = (
        0.5 * (px * px + py * py + grad_x * grad_x + grad_y * grad_y + M * M * rho)
        + 0.5 * G * rho * rho * rho / (r**4)
    )
    jr, ji, _jr_dot, _ji_dot = pump_components(t, r, arm)
    pair_density = -KAPPA * (jr * (ux * ux - uy * uy) - 2.0 * ji * ux * uy)
    core = r <= CORE_RADIUS
    outside = r >= EXTERIOR_RADIUS
    carrier_energy = compatible_carrier_energy(state, r, spacing)
    full_energy = carrier_energy + float(4.0 * math.pi * np.sum(pair_density) * spacing)
    number_total = float(4.0 * math.pi * np.sum(rho) * spacing)
    number_core = float(4.0 * math.pi * np.sum(rho[core]) * spacing)
    charge = float(4.0 * math.pi * np.sum(ux * py - uy * px) * spacing)
    core_charge = float(4.0 * math.pi * np.sum((ux * py - uy * px)[core]) * spacing)
    core_energy = float(4.0 * math.pi * np.sum(carrier_density[core]) * spacing)
    core_density = float(3.0 * np.sum(rho[core]) * spacing / (CORE_RADIUS**3))
    rms_radius = math.sqrt(float(np.sum(r * r * rho) / max(np.sum(rho), np.finfo(float).tiny)))
    ext_support = float(
        np.sum(support_density[outside]) / max(np.sum(support_density), np.finfo(float).tiny)
    )
    current_rates = rates(state, t, r, spacing, arm)
    charge_balance = charge - (
        ledger["initial_charge"]
        + ledger["source_charge_cumulative"]
        + ledger["boundary_charge_cumulative"]
    )
    energy_balance = full_energy - (
        initial_full_energy
        + ledger["pump_work_cumulative"]
        + ledger["boundary_energy_cumulative"]
    )
    return {
        "time": float(t),
        "carrier_energy": carrier_energy,
        "full_energy": full_energy,
        "number_total": number_total,
        "number_core": number_core,
        "core_fraction": number_core / max(number_total, np.finfo(float).tiny),
        "charge": charge,
        "core_charge": core_charge,
        "core_energy": core_energy,
        "core_energy_per_charge": core_energy / max(abs(core_charge), np.finfo(float).tiny),
        "core_density": core_density,
        "exterior_support_fraction": ext_support,
        "rms_radius": rms_radius,
        "source_charge_rate": current_rates["source_charge_rate"],
        "boundary_charge_flux": current_rates["boundary_charge_flux"],
        "pump_work_rate": current_rates["pump_work_rate"],
        "boundary_energy_flux": current_rates["boundary_energy_flux"],
        "source_charge_cumulative": ledger["source_charge_cumulative"],
        "boundary_charge_cumulative": ledger["boundary_charge_cumulative"],
        "pump_work_cumulative": ledger["pump_work_cumulative"],
        "boundary_energy_cumulative": ledger["boundary_energy_cumulative"],
        "charge_balance_residual": charge_balance,
        "energy_balance_residual": energy_balance,
    }


def advance_ledger(
    ledger: dict[str, float], left: dict[str, float], right: dict[str, float], dt: float
) -> None:
    for rate_name, cumulative_name in (
        ("source_charge_rate", "source_charge_cumulative"),
        ("boundary_charge_flux", "boundary_charge_cumulative"),
        ("pump_work_rate", "pump_work_cumulative"),
        ("boundary_energy_flux", "boundary_energy_cumulative"),
    ):
        ledger[cumulative_name] += 0.5 * (left[rate_name] + right[rate_name]) * dt


def archive_run(
    output: Path, name: str, count: int, dt: float, arm: int
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    r, spacing = radial_grid(count)
    state = initial_state(count, arm)
    total_steps = round(T_FINAL / dt)
    steps_per_checkpoint = round(SAVE_INTERVAL / dt)
    if steps_per_checkpoint * round(T_FINAL / SAVE_INTERVAL) != total_steps:
        raise FormationError("checkpoint schedule is not integral")
    checkpoints = np.arange(0.0, T_FINAL + 0.5 * SAVE_INTERVAL, SAVE_INTERVAL)
    ledger = {
        "initial_charge": float(4.0 * math.pi * np.sum(state[0] * state[3] - state[1] * state[2]) * spacing),
        "source_charge_cumulative": 0.0,
        "boundary_charge_cumulative": 0.0,
        "pump_work_cumulative": 0.0,
        "boundary_energy_cumulative": 0.0,
    }
    initial_rates = rates(state, 0.0, r, spacing, arm)
    ux, uy, px, py = state
    initial_full_energy = compatible_carrier_energy(state, r, spacing)
    rows: list[dict[str, Any]] = []
    archive: dict[str, list[np.ndarray]] = {key: [] for key in ("ux", "uy", "px", "py")}
    start = time.perf_counter()
    checkpoint_index = 0
    for step_index in range(total_steps + 1):
        t = step_index * dt
        if step_index == checkpoint_index * steps_per_checkpoint:
            rows.append(observables(state, t, r, spacing, arm, ledger, initial_full_energy))
            for key, value in zip(archive, state):
                archive[key].append(value.copy())
            checkpoint_index += 1
        if step_index == total_steps:
            break
        state_next = rk4_step(state, t, r, spacing, dt, arm)
        if not all(np.all(np.isfinite(value)) for value in state_next):
            raise FormationError(f"nonfinite state in {name} at step {step_index + 1}")
        right_rates = rates(state_next, t + dt, r, spacing, arm)
        advance_ledger(ledger, initial_rates, right_rates, dt)
        state = state_next
        initial_rates = right_rates
    archive_arrays = {key: np.asarray(values) for key, values in archive.items()}
    archive_arrays["r"] = r
    archive_arrays["times"] = checkpoints
    archive_path = output / f"{name}.npz"
    np.savez_compressed(archive_path, **archive_arrays)
    record = {
        "name": name,
        "count": count,
        "spacing": spacing,
        "dt": dt,
        "arm": arm,
        "steps": total_steps,
        "archive": archive_path.name,
        "rows": rows,
        "final": rows[-1],
        "elapsed_seconds": time.perf_counter() - start,
    }
    return record, archive_arrays


def late_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
    late = [row for row in rows if row["time"] >= LATE_START]
    if not late:
        raise FormationError("late window is empty")
    def mean(key: str) -> float:
        return float(np.mean([row[key] for row in late]))
    def minimum(key: str) -> float:
        return float(np.min([row[key] for row in late]))
    def maximum(key: str) -> float:
        return float(np.max([row[key] for row in late]))
    return {
        "count": float(len(late)),
        "mean_core_density": mean("core_density"),
        "mean_core_fraction": mean("core_fraction"),
        "minimum_core_fraction": minimum("core_fraction"),
        "mean_exterior_support_fraction": mean("exterior_support_fraction"),
        "maximum_exterior_support_fraction": maximum("exterior_support_fraction"),
        "mean_core_energy": mean("core_energy"),
        "mean_abs_core_charge": float(np.mean([abs(row["core_charge"]) for row in late])),
        "minimum_abs_core_charge": float(np.min([abs(row["core_charge"]) for row in late])),
        "maximum_core_energy_per_charge": maximum("core_energy_per_charge"),
        "mean_rms_radius": mean("rms_radius"),
        "maximum_charge_balance_residual": maximum("charge_balance_residual"),
        "maximum_energy_balance_residual": maximum("energy_balance_residual"),
    }


def relative_error(left: float, right: float) -> float:
    return abs(left - right) / max(1.0, abs(left), abs(right))


def evaluate(
    runs: dict[str, dict[str, Any]], archives: dict[str, dict[str, np.ndarray]]
) -> tuple[dict[str, Any], dict[str, bool]]:
    positive_rows = runs["positive"]["rows"]
    vacuum_rows = runs["vacuum_control"]["rows"]
    negative_rows = runs["negative"]["rows"]
    fine_rows = runs["positive_fine"]["rows"]
    positive_late = late_summary(positive_rows)
    fine_late = late_summary(fine_rows)
    vacuum_late_density = float(np.mean([
        row["core_density"] for row in vacuum_rows if row["time"] >= LATE_START
    ]))
    post_rows = [row for row in positive_rows if row["time"] >= PULSE_DURATION]
    if not post_rows:
        raise FormationError("post-pulse window is empty")
    pulse_end = next(row for row in positive_rows if abs(row["time"] - PULSE_DURATION) < 1.0e-12)
    corrected = np.asarray([
        row["charge"] - (row["boundary_charge_cumulative"] - pulse_end["boundary_charge_cumulative"])
        for row in post_rows if row["time"] >= LATE_START
    ], dtype=np.float64)
    corrected_charge_drift = float(np.max(corrected) - np.min(corrected)) / max(
        float(np.max(np.abs(corrected))), np.finfo(float).tiny
    )
    source_after_pulse = max(abs(row["source_charge_rate"]) for row in post_rows)
    positive_archive = archives["positive"]
    negative_archive = archives["negative"]
    cp_error = max(
        float(np.max(np.abs(positive_archive["ux"] - negative_archive["ux"]))),
        float(np.max(np.abs(positive_archive["uy"] + negative_archive["uy"]))),
        float(np.max(np.abs(positive_archive["px"] - negative_archive["px"]))),
        float(np.max(np.abs(positive_archive["py"] + negative_archive["py"]))),
    )
    negative_late = late_summary(negative_rows)
    resolution = {
        key: relative_error(positive_late[key], fine_late[key])
        for key in (
            "mean_core_energy",
            "mean_abs_core_charge",
            "mean_core_fraction",
            "mean_exterior_support_fraction",
            "mean_rms_radius",
        )
    }
    cp_metrics = {
        key: relative_error(positive_late[key], negative_late[key])
        for key in (
            "mean_core_energy",
            "mean_core_fraction",
            "mean_exterior_support_fraction",
            "mean_rms_radius",
        )
    }
    positive_charge = positive_late["mean_abs_core_charge"]
    negative_charge = negative_late["mean_abs_core_charge"]
    ledger_rows = positive_rows
    charge_scale = max(
        [1.0]
        + [abs(row[key]) for row in ledger_rows for key in ("charge", "source_charge_cumulative", "boundary_charge_cumulative")]
    )
    energy_scale = max(
        [1.0]
        + [abs(row[key]) for row in ledger_rows for key in ("full_energy", "pump_work_cumulative", "boundary_energy_cumulative")]
    )
    maximum_charge_balance = max(abs(row["charge_balance_residual"]) for row in ledger_rows)
    maximum_energy_balance = max(abs(row["energy_balance_residual"]) for row in ledger_rows)
    ledger_relative_charge = maximum_charge_balance / charge_scale
    ledger_relative_energy = maximum_energy_balance / energy_scale
    predicates = {
        "core_density_amplified": positive_late["mean_core_density"] >= 4.0 * vacuum_late_density,
        "core_retention": positive_late["minimum_core_fraction"] >= 0.80,
        "localized_support": (
            positive_late["maximum_exterior_support_fraction"] < 0.25
            and positive_late["mean_exterior_support_fraction"] < 0.20
        ),
        "charge_and_post_pulse_continuity": (
            positive_late["minimum_abs_core_charge"] >= 200.0
            and corrected_charge_drift < 0.05
            and source_after_pulse <= 1.0e-12
        ),
        "subthreshold_core": positive_late["maximum_core_energy_per_charge"] < M,
        "cp_and_resolution": (
            cp_error < 1.0e-9
            and positive_charge >= 200.0
            and negative_charge >= 200.0
            and all(value < 0.05 for value in resolution.values())
            and all(value < 1.0e-9 for value in cp_metrics.values())
            and positive_rows[-1]["core_charge"] * negative_rows[-1]["core_charge"] < 0.0
        ),
        "flux_energy_ledger": ledger_relative_charge <= 1.0e-6 and ledger_relative_energy <= 1.0e-6,
    }
    controls = {
        "vacuum_late_core_density": vacuum_late_density,
        "post_pulse_corrected_charge_drift": corrected_charge_drift,
        "post_pulse_source_max_abs": source_after_pulse,
        "cp_max_raw_state_error": cp_error,
        "resolution_relative_errors": resolution,
        "cp_metric_relative_errors": cp_metrics,
        "positive_late_summary": positive_late,
        "negative_late_summary": negative_late,
        "fine_late_summary": fine_late,
        "positive_negative_charge_signs": [
            float(positive_rows[-1]["core_charge"]),
            float(negative_rows[-1]["core_charge"]),
        ],
        "maximum_charge_balance_residual": maximum_charge_balance,
        "maximum_energy_balance_residual": maximum_energy_balance,
        "ledger_relative_charge": ledger_relative_charge,
        "ledger_relative_energy": ledger_relative_energy,
        "ledger_charge_scale": charge_scale,
        "ledger_energy_scale": energy_scale,
    }
    return controls, predicates


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
    runs: dict[str, dict[str, Any]] = {}
    archives: dict[str, dict[str, np.ndarray]] = {}
    specs = (
        ("vacuum_control", N_PRIMARY, DT_PRIMARY, 0),
        ("positive", N_PRIMARY, DT_PRIMARY, 1),
        ("negative", N_PRIMARY, DT_PRIMARY, -1),
        ("positive_fine", N_FINE, DT_FINE, 1),
    )
    for name, count, dt, arm in specs:
        record, arrays = archive_run(output, name, count, dt, arm)
        runs[name] = record
        archives[name] = arrays
    controls, predicates = evaluate(runs, archives)
    payload = {
        "schema": SCHEMA,
        "protocol": relative(PROTOCOL),
        "protocol_sha256": sha256(PROTOCOL),
        "source_records": source_records,
        "parameters": {
            "radius": RADIUS,
            "primary_grid": N_PRIMARY,
            "fine_grid": N_FINE,
            "dt_primary": DT_PRIMARY,
            "dt_fine": DT_FINE,
            "T_final": T_FINAL,
            "save_interval": SAVE_INTERVAL,
            "modes": MODES,
            "seed": SEED,
            "m": M,
            "lambda": LAMBDA,
            "g": G,
            "kappa": KAPPA,
            "pulse_amplitude": PULSE_AMPLITUDE,
            "pulse_width": PULSE_WIDTH,
            "pulse_frequency": PULSE_FREQUENCY,
            "pulse_duration": PULSE_DURATION,
            "core_radius": CORE_RADIUS,
            "exterior_radius": EXTERIOR_RADIUS,
            "late_start": LATE_START,
        },
        "runs": runs,
        "controls": controls,
        "predicates": predicates,
        "numerical_pass": True,
        "scientific_verdict": (
            "INCONCLUSIVE—compact CP-pump formation ledger failure"
            if not predicates["flux_energy_ledger"]
            else "CAPTURED—conditional compact CP-pump vacuum-to-carrier formation"
            if all(predicates.values())
            else "DOES NOT EMERGE—conditional compact CP-pump vacuum-to-carrier formation"
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
        print(f"formation run failed: {exc}")
        raise
