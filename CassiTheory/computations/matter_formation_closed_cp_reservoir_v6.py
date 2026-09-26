"""Run the preregistered autonomous complex-reservoir formation calculation.

Run from the CassiTheory root:
    python computations/matter_formation_closed_cp_reservoir_v6.py \
        --output-dir runs/20260912_matter_formation_closed_cp_reservoir_v6
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
PROTOCOL = ROOT / "computations/matter-formation-closed-cp-reservoir-v6-prereg.md"
SOURCE = Path(__file__).resolve()
DEFAULT_OUTPUT = ROOT / "runs/20260912_matter_formation_closed_cp_reservoir_v6"
SCHEMA = "cassi.matter-formation.closed-cp-reservoir.v6"

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
M_A = 1.0
RESERVOIR_WAVENUMBER = 1.0
RESERVOIR_FREQUENCY = math.sqrt(M_A * M_A + RESERVOIR_WAVENUMBER * RESERVOIR_WAVENUMBER)
KAPPA = 0.5
RESERVOIR_AMPLITUDE = 0.8
RESERVOIR_WIDTH = 8.0
CORE_RADIUS = 12.0
EXTERIOR_RADIUS = 20.0
OVERLAP_END = 24.0
LATE_START = 60.0


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
    xi_x, xi_y, pi_x, pi_y = (rng.normal(size=MODES) for _ in range(4))
    basis = math.sqrt(2.0 / RADIUS) * np.sin(modes[:, None] * math.pi * r[None, :] / RADIUS)
    return (
        (xi_x / np.sqrt(4.0 * omega)) @ basis,
        (xi_y / np.sqrt(4.0 * omega)) @ basis,
        (np.sqrt(omega / 4.0) * pi_x) @ basis,
        (np.sqrt(omega / 4.0) * pi_y) @ basis,
    )


def initial_state(
    count: int, sign: int, reservoir_amplitude: float, coupling: float
) -> tuple[np.ndarray, ...]:
    r, _ = radial_grid(count)
    ux, uy, px, py = vacuum_draw(r)
    if sign < 0:
        uy = -uy
        py = -py
    envelope = np.exp(-0.5 * (r / RESERVOIR_WIDTH) ** 2)
    carrier = reservoir_amplitude * envelope * np.cos(RESERVOIR_WAVENUMBER * r) * r
    carrier_derivative = reservoir_amplitude * envelope * (
        (1.0 - (r / RESERVOIR_WIDTH) ** 2) * np.cos(RESERVOIR_WAVENUMBER * r)
        - RESERVOIR_WAVENUMBER * r * np.sin(RESERVOIR_WAVENUMBER * r)
    )
    wr = carrier
    wi = np.zeros_like(r)
    pwr = -carrier_derivative
    pwi = sign * RESERVOIR_FREQUENCY * carrier
    return ux, uy, wr, wi, px, py, pwr, pwi


def static_laplacian(values: np.ndarray, spacing: float) -> np.ndarray:
    extended = np.empty(values.size + 2, dtype=np.float64)
    extended[1:-1] = values
    extended[0] = -values[0]
    extended[-1] = values[-1]
    return (extended[2:] - 2.0 * extended[1:-1] + extended[:-2]) / (spacing * spacing)


def outgoing_laplacian(values: np.ndarray, momentum: np.ndarray, spacing: float) -> np.ndarray:
    result = static_laplacian(values, spacing)
    result[-1] -= momentum[-1] / spacing
    return result


def rhs(
    state: tuple[np.ndarray, ...], r: np.ndarray, spacing: float, coupling: float
) -> tuple[np.ndarray, ...]:
    ux, uy, wr, wi, px, py, pwr, pwi = state
    rho = ux * ux + uy * uy
    physical_s = rho / (r * r)
    coefficient = M * M - 2.0 * LAMBDA * physical_s + 3.0 * G * physical_s * physical_s
    ar = wr / r
    ai = wi / r
    ax = outgoing_laplacian(ux, px, spacing) - coefficient * ux + 2.0 * coupling * (ar * ux - ai * uy)
    ay = outgoing_laplacian(uy, py, spacing) - coefficient * uy + 2.0 * coupling * (-ar * uy - ai * ux)
    awr = outgoing_laplacian(wr, pwr, spacing) - M_A * M_A * wr + coupling * (ux * ux - uy * uy) / r
    awi = outgoing_laplacian(wi, pwi, spacing) - M_A * M_A * wi - 2.0 * coupling * ux * uy / r
    return px, py, pwr, pwi, ax, ay, awr, awi


def state_add(
    state: tuple[np.ndarray, ...], other: tuple[np.ndarray, ...], factor: float
) -> tuple[np.ndarray, ...]:
    return tuple(a + factor * b for a, b in zip(state, other))  # type: ignore[return-value]


def state_rk4_step(
    state: tuple[np.ndarray, ...], r: np.ndarray, spacing: float, dt: float, coupling: float
) -> tuple[np.ndarray, ...]:
    k1 = rhs(state, r, spacing, coupling)
    k2 = rhs(state_add(state, k1, 0.5 * dt), r, spacing, coupling)
    k3 = rhs(state_add(state, k2, 0.5 * dt), r, spacing, coupling)
    k4 = rhs(state_add(state, k3, dt), r, spacing, coupling)
    return tuple(
        a + (dt / 6.0) * (b + 2.0 * c + 2.0 * d + e)
        for a, b, c, d, e in zip(state, k1, k2, k3, k4)
    )  # type: ignore[return-value]


def gradient(values: np.ndarray, spacing: float) -> np.ndarray:
    extended = np.empty(values.size + 2, dtype=np.float64)
    extended[1:-1] = values
    extended[0] = -values[0]
    extended[-1] = values[-1]
    return (extended[2:] - extended[:-2]) / (2.0 * spacing)


def energy(state: tuple[np.ndarray, ...], r: np.ndarray, spacing: float, coupling: float) -> float:
    ux, uy, wr, wi, px, py, pwr, pwi = state
    rho = ux * ux + uy * uy
    ah_x = static_laplacian(ux, spacing)
    ah_y = static_laplacian(uy, spacing)
    ah_wr = static_laplacian(wr, spacing)
    ah_wi = static_laplacian(wi, spacing)
    gradient_energy = -0.5 * spacing * float(
        ux @ ah_x + uy @ ah_y + wr @ ah_wr + wi @ ah_wi
    )
    local = (
        0.5 * (px * px + py * py + pwr * pwr + pwi * pwi)
        + 0.5 * M * M * rho
        - 0.5 * LAMBDA * rho * rho / (r**2)
        + 0.5 * G * rho * rho * rho / (r**4)
        + 0.5 * M_A * M_A * (wr * wr + wi * wi)
        - coupling * (wr / r) * (ux * ux - uy * uy)
        + 2.0 * coupling * (wi / r) * ux * uy
    )
    return float(4.0 * math.pi * (gradient_energy + spacing * np.sum(local)))


def instantaneous_metrics(
    state: tuple[np.ndarray, ...], r: np.ndarray, spacing: float, coupling: float
) -> dict[str, float]:
    ux, uy, wr, wi, px, py, pwr, pwi = state
    rho = ux * ux + uy * uy
    gx = gradient(ux, spacing)
    gy = gradient(uy, spacing)
    e_carrier_density = (
        0.5 * (px * px + py * py + gx * gx + gy * gy)
        + 0.5 * M * M * rho
        - 0.5 * LAMBDA * rho * rho / (r**2)
        + 0.5 * G * rho * rho * rho / (r**4)
    )
    support_density = (
        0.5 * (px * px + py * py + gx * gx + gy * gy + M * M * rho)
        + 0.5 * G * rho * rho * rho / (r**4)
    )
    core = r <= CORE_RADIUS
    exterior = r >= EXTERIOR_RADIUS
    charge_density = ux * py - uy * px
    charge = float(4.0 * math.pi * np.sum(charge_density) * spacing)
    core_charge = float(4.0 * math.pi * np.sum(charge_density[core]) * spacing)
    number_total = float(4.0 * math.pi * np.sum(rho) * spacing)
    number_core = float(4.0 * math.pi * np.sum(rho[core]) * spacing)
    support_total = float(4.0 * math.pi * np.sum(support_density) * spacing)
    return {
        "carrier_energy": float(4.0 * math.pi * np.sum(e_carrier_density) * spacing),
        "core_energy": float(4.0 * math.pi * np.sum(e_carrier_density[core]) * spacing),
        "full_energy": energy(state, r, spacing, coupling),
        "number_total": number_total,
        "number_core": number_core,
        "core_fraction": number_core / max(number_total, np.finfo(float).tiny),
        "charge": charge,
        "core_charge": core_charge,
        "rms_radius": math.sqrt(float(np.sum(r * r * rho) / max(np.sum(rho), np.finfo(float).tiny))),
        "core_density": 3.0 * float(np.sum(rho[core]) * spacing) / (CORE_RADIUS**3),
        "exterior_support_fraction": float(
            np.sum(support_density[exterior]) / max(np.sum(support_density), np.finfo(float).tiny)
        ),
        "source_rate": float(
            4.0
            * math.pi
            * coupling
            * np.sum((-4.0 * (wr / r) * ux * uy - 2.0 * (wi / r) * (ux * ux - uy * uy)))
            * spacing
        ),
        "boundary_charge_rate": float(
            4.0 * math.pi * (-ux[-1] * py[-1] + uy[-1] * px[-1])
        ),
        "boundary_energy_rate": float(
            -4.0 * math.pi * (px[-1] ** 2 + py[-1] ** 2 + pwr[-1] ** 2 + pwi[-1] ** 2)
        ),
    }


def archive_run(
    output: Path,
    name: str,
    count: int,
    dt: float,
    sign: int,
    reservoir_amplitude: float,
    coupling: float,
    capture_arrays: bool = True,
) -> dict[str, Any]:
    r, spacing = radial_grid(count)
    state = initial_state(count, sign, reservoir_amplitude, coupling)
    checkpoints = np.arange(0.0, T_FINAL + 0.5 * SAVE_INTERVAL, SAVE_INTERVAL)
    checkpoint_rows: list[dict[str, Any]] = []
    archive: dict[str, list[np.ndarray]] = {
        key: [] for key in ("ux", "uy", "wr", "wi", "px", "py", "pwr", "pwi")
    }
    steps_per_checkpoint = round(SAVE_INTERVAL / dt)
    total_steps = round(T_FINAL / dt)
    if steps_per_checkpoint * (len(checkpoints) - 1) != total_steps:
        raise FormationError("checkpoint schedule is not integral")
    q_initial = instantaneous_metrics(state, r, spacing, coupling)["charge"]
    e_initial = energy(state, r, spacing, coupling)
    q_source_cumulative = 0.0
    q_boundary_cumulative = 0.0
    q_source_abs_cumulative = 0.0
    e_boundary_cumulative = 0.0
    start = time.perf_counter()
    checkpoint_index = 0
    previous_rates = instantaneous_metrics(state, r, spacing, coupling)
    for step_index in range(total_steps + 1):
        if step_index == checkpoint_index * steps_per_checkpoint:
            metrics = instantaneous_metrics(state, r, spacing, coupling)
            row = {
                "time": float(checkpoints[checkpoint_index]),
                **metrics,
                "charge_ledger_residual": metrics["charge"] - q_initial - q_source_cumulative - q_boundary_cumulative,
                "energy_ledger_residual": metrics["full_energy"] - e_initial - e_boundary_cumulative,
                "source_cumulative": q_source_cumulative,
                "boundary_charge_cumulative": q_boundary_cumulative,
                "source_abs_cumulative": q_source_abs_cumulative,
                "boundary_energy_cumulative": e_boundary_cumulative,
            }
            checkpoint_rows.append(row)
            if capture_arrays:
                for key, value in zip(archive, state):
                    archive[key].append(value.copy())
            checkpoint_index += 1
        if step_index == total_steps:
            break
        state = state_rk4_step(state, r, spacing, dt, coupling)
        if not all(np.all(np.isfinite(value)) for value in state):
            raise FormationError(f"nonfinite state in {name} at step {step_index + 1}")
        current_rates = instantaneous_metrics(state, r, spacing, coupling)
        q_source_cumulative += 0.5 * dt * (previous_rates["source_rate"] + current_rates["source_rate"])
        q_boundary_cumulative += 0.5 * dt * (
            previous_rates["boundary_charge_rate"] + current_rates["boundary_charge_rate"]
        )
        q_source_abs_cumulative += 0.5 * dt * (
            abs(previous_rates["source_rate"]) + abs(current_rates["source_rate"])
        )
        e_boundary_cumulative += 0.5 * dt * (
            previous_rates["boundary_energy_rate"] + current_rates["boundary_energy_rate"]
        )
        previous_rates = current_rates
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
        "dt": dt,
        "sign": sign,
        "reservoir_amplitude": reservoir_amplitude,
        "coupling": coupling,
        "steps": total_steps,
        "elapsed_seconds": time.perf_counter() - start,
        "archive": output_path.name,
        "rows": checkpoint_rows,
    }


def late_mean(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row[key]) for row in rows if row["time"] >= LATE_START]
    return float(np.mean(values))


def relative_difference(a: float, b: float) -> float:
    return abs(a - b) / max(1.0, abs(a), abs(b))


def arm_observables(rows: list[dict[str, Any]]) -> dict[str, float]:
    late = [row for row in rows if row["time"] >= LATE_START]
    return {
        "core_energy": float(np.mean([row["core_energy"] for row in late])),
        "absolute_core_charge": float(np.mean([abs(row["core_charge"]) for row in late])),
        "core_fraction": float(np.mean([row["core_fraction"] for row in late])),
        "exterior_support_fraction": float(np.mean([row["exterior_support_fraction"] for row in late])),
        "rms_radius": float(np.mean([row["rms_radius"] for row in late])),
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
        "vacuum_control": archive_run(output, "vacuum_control", N_PRIMARY, DT_PRIMARY, +1, 0.0, 0.0),
        "reservoir_control": archive_run(
            output, "reservoir_control", N_PRIMARY, DT_PRIMARY, +1, RESERVOIR_AMPLITUDE, 0.0
        ),
        "positive": archive_run(
            output, "positive", N_PRIMARY, DT_PRIMARY, +1, RESERVOIR_AMPLITUDE, KAPPA
        ),
        "negative": archive_run(
            output, "negative", N_PRIMARY, DT_PRIMARY, -1, RESERVOIR_AMPLITUDE, KAPPA
        ),
        "positive_fine": archive_run(
            output, "positive_fine", N_FINE, DT_FINE, +1, RESERVOIR_AMPLITUDE, KAPPA
        ),
    }

    vacuum_rows = runs["vacuum_control"]["rows"]
    reservoir_rows = runs["reservoir_control"]["rows"]
    positive_rows = runs["positive"]["rows"]
    negative_rows = runs["negative"]["rows"]
    fine_rows = runs["positive_fine"]["rows"]
    late_positive = [row for row in positive_rows if row["time"] >= LATE_START]
    late_vacuum = [row for row in vacuum_rows if row["time"] >= LATE_START]
    vacuum_density = float(np.mean([row["core_density"] for row in late_vacuum]))
    positive_observables = arm_observables(positive_rows)
    fine_observables = arm_observables(fine_rows)
    resolution = {
        key: relative_difference(positive_observables[key], fine_observables[key])
        for key in positive_observables
    }
    late_charge = np.asarray([row["charge"] for row in late_positive], dtype=np.float64)
    corrected_charge = np.asarray(
        [row["charge"] - row["source_cumulative"] - row["boundary_charge_cumulative"] for row in late_positive],
        dtype=np.float64,
    )
    corrected_charge_drift = float(np.max(corrected_charge) - np.min(corrected_charge)) / max(
        float(np.max(np.abs(corrected_charge))), np.finfo(float).tiny
    )
    overlap_row = next(row for row in positive_rows if abs(row["time"] - OVERLAP_END) < 1.0e-12)
    final_positive = positive_rows[-1]
    source_abs_total = final_positive["source_abs_cumulative"]
    source_abs_at_overlap = overlap_row["source_abs_cumulative"]
    source_tail_ratio = (source_abs_total - source_abs_at_overlap) / max(1.0, source_abs_total)
    resolution_pass = all(value < 0.05 for value in resolution.values())
    cp_even_keys = ("carrier_energy", "full_energy", "number_total", "rms_radius", "core_density")
    cp_metric_error = max(
        abs(positive_rows[index][key] - negative_rows[index][key])
        for index in range(len(positive_rows))
        for key in cp_even_keys
    )
    cp_charge_error = max(
        abs(positive_rows[index]["charge"] + negative_rows[index]["charge"])
        for index in range(len(positive_rows))
    )
    with np.load(output / runs["positive"]["archive"]) as positive_archive, np.load(
        output / runs["negative"]["archive"]
    ) as negative_archive:
        cp_raw_error = max(
            float(np.max(np.abs(positive_archive[key] - sign * negative_archive[key])))
            for key, sign in (
                ("ux", 1.0),
                ("uy", -1.0),
                ("wr", 1.0),
                ("wi", -1.0),
                ("px", 1.0),
                ("py", -1.0),
                ("pwr", 1.0),
                ("pwi", -1.0),
            )
        )
    reservoir_control_error = max(
        abs(vacuum_rows[index][key] - reservoir_rows[index][key])
        for index in range(len(vacuum_rows))
        for key in ("number_total", "core_density", "rms_radius")
    )
    max_charge_ledger = max(abs(row["charge_ledger_residual"]) for row in positive_rows)
    max_energy_ledger = max(abs(row["energy_ledger_residual"]) for row in positive_rows)
    charge_scale = max(
        1.0,
        max(abs(row["charge"]) for row in positive_rows),
        max(abs(row["source_cumulative"]) for row in positive_rows),
        max(abs(row["boundary_charge_cumulative"]) for row in positive_rows),
    )
    energy_scale = max(
        1.0,
        max(abs(row["full_energy"]) for row in positive_rows),
        max(abs(row["boundary_energy_cumulative"]) for row in positive_rows),
    )
    late_core_charge = [abs(row["core_charge"]) for row in late_positive]
    late_energy_per_charge = [
        row["core_energy"] / max(abs(row["core_charge"]), np.finfo(float).tiny) for row in late_positive
    ]
    predicates = {
        "core_density_amplified": late_mean(positive_rows, "core_density") >= 4.0 * vacuum_density,
        "core_retention": min(row["core_fraction"] for row in late_positive) >= 0.80,
        "localized_support_max": max(row["exterior_support_fraction"] for row in late_positive) < 0.25,
        "localized_support_mean": late_mean(positive_rows, "exterior_support_fraction") < 0.20,
        "charge_magnitude": min(late_core_charge) > 200.0,
        "corrected_post_overlap_charge_drift": corrected_charge_drift < 0.05,
        "subthreshold_core_energy_per_charge": max(late_energy_per_charge) < M,
        "source_decoupling": source_tail_ratio < 0.15,
        "cp_conjugacy": cp_metric_error < 1.0e-8 and cp_charge_error < 1.0e-8 and final_positive["charge"] * negative_rows[-1]["charge"] < 0.0,
        "cp_raw_state": cp_raw_error < 1.0e-8,
        "resolution": resolution_pass,
        "charge_ledger": max_charge_ledger / charge_scale < 1.0e-5,
        "energy_ledger": max_energy_ledger / energy_scale < 1.0e-5,
        "reservoir_control": reservoir_control_error < 1.0e-8,
        "finite_state": all(np.isfinite(value) for row in positive_rows for value in row.values() if isinstance(value, (float, int))),
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
            "dt_primary": DT_PRIMARY,
            "dt_fine": DT_FINE,
            "T_final": T_FINAL,
            "save_interval": SAVE_INTERVAL,
            "modes": MODES,
            "seed": SEED,
            "m": M,
            "lambda": LAMBDA,
            "g": G,
            "m_a": M_A,
            "reservoir_wavenumber": RESERVOIR_WAVENUMBER,
            "reservoir_frequency": RESERVOIR_FREQUENCY,
            "kappa": KAPPA,
            "reservoir_amplitude": RESERVOIR_AMPLITUDE,
            "reservoir_width": RESERVOIR_WIDTH,
            "core_radius": CORE_RADIUS,
            "exterior_radius": EXTERIOR_RADIUS,
            "overlap_end": OVERLAP_END,
            "late_start": LATE_START,
        },
        "runs": runs,
        "controls": {
            "vacuum_late_core_density": vacuum_density,
            "resolution_relative_errors": resolution,
            "cp_max_even_metric_error": cp_metric_error,
            "cp_max_charge_sum_error": cp_charge_error,
            "cp_max_raw_state_error": cp_raw_error,
            "reservoir_control_max_error": reservoir_control_error,
            "source_tail_ratio": source_tail_ratio,
            "corrected_post_overlap_charge_drift": corrected_charge_drift,
            "max_charge_ledger_residual": max_charge_ledger,
            "max_energy_ledger_residual": max_energy_ledger,
            "charge_ledger_scale": charge_scale,
            "energy_ledger_scale": energy_scale,
            "late_mean_core_density": late_mean(positive_rows, "core_density"),
            "late_min_abs_core_charge": min(late_core_charge),
            "late_max_core_energy_per_charge": max(late_energy_per_charge),
        },
        "predicates": predicates,
        "numerical_pass": True,
        "scientific_verdict": (
            "CAPTURED—conditional closed CP-odd-reservoir vacuum-to-carrier formation"
            if scientific_pass
            else "DOES NOT EMERGE—conditional closed CP-odd-reservoir vacuum-to-carrier formation"
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
