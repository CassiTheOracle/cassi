#!/usr/bin/env python3
"""Independently reconstruct the pair-frequency-resonant incoming-shell receipt."""
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
PRIMARY = ROOT / "computations/matter_formation_closed_cp_incoming_reservoir_v11.py"
PROTOCOL = ROOT / "computations/matter-formation-closed-cp-incoming-reservoir-v11-prereg.md"
SCHEMA = "cassi.matter-formation.closed-cp-incoming-reservoir.v11.verification"
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
M_A = 0.5
RESERVOIR_WAVENUMBER = math.sqrt(15.0) / 2.0
RESERVOIR_FREQUENCY = 2.0 * M
KAPPA = 0.5
RESERVOIR_AMPLITUDE = 0.8
RESERVOIR_WIDTH = 6.0
RESERVOIR_CENTER = 16.0
CORE_RADIUS = 12.0
EXTERIOR_RADIUS = 20.0
OVERLAP_END = 30.0
LATE_START = 60.0


class VerificationError(RuntimeError):
    """Typed failure of the independent verification contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def finite(value: Any) -> bool:
    if isinstance(value, dict):
        return all(finite(item) for item in value.values())
    if isinstance(value, list):
        return all(finite(item) for item in value)
    if isinstance(value, (float, int)):
        return math.isfinite(float(value))
    return True


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, float):
        if not math.isfinite(value):
            raise VerificationError(f"nonfinite receipt value: {value}")
        return value
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(json_ready(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def grid(count: int) -> tuple[np.ndarray, float]:
    dr = RADIUS / count
    return (np.arange(count, dtype=np.float64) + 0.5) * dr, dr


def draw_vacuum(r: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    modes = np.arange(1, MODES + 1, dtype=np.float64)
    omega = np.sqrt(M * M + (modes * math.pi / RADIUS) ** 2)
    generator = np.random.Generator(np.random.PCG64(SEED))
    samples = [generator.normal(size=MODES) for _ in range(4)]
    basis = math.sqrt(2.0 / RADIUS) * np.sin(modes[:, None] * math.pi * r[None, :] / RADIUS)
    return (
        (samples[0] / np.sqrt(4.0 * omega)) @ basis,
        (samples[1] / np.sqrt(4.0 * omega)) @ basis,
        (np.sqrt(omega / 4.0) * samples[2]) @ basis,
        (np.sqrt(omega / 4.0) * samples[3]) @ basis,
    )


def make_initial(
    count: int, sign: int, amplitude: float
) -> tuple[np.ndarray, ...]:
    r, _ = grid(count)
    ux, uy, px, py = draw_vacuum(r)
    if sign == -1:
        uy = -uy
        py = -py
    rho = r - RESERVOIR_CENTER
    envelope = np.exp(-0.5 * (rho / RESERVOIR_WIDTH) ** 2)
    phase = RESERVOIR_WAVENUMBER * rho
    carrier = amplitude * envelope * np.cos(phase) * r
    carrier_derivative = amplitude * envelope * (
        np.cos(phase)
        - (r * rho / (RESERVOIR_WIDTH * RESERVOIR_WIDTH)) * np.cos(phase)
        - r * RESERVOIR_WAVENUMBER * np.sin(phase)
    )
    wr = carrier
    wi = np.zeros_like(r)
    pwr = carrier_derivative
    pwi = sign * RESERVOIR_FREQUENCY * carrier
    return ux, uy, wr, wi, px, py, pwr, pwi


def static_operator(values: np.ndarray, dr: float) -> np.ndarray:
    ghost = np.empty(values.size + 2, dtype=np.float64)
    ghost[1:-1] = values
    ghost[0] = -values[0]
    ghost[-1] = values[-1]
    return (ghost[2:] - 2.0 * ghost[1:-1] + ghost[:-2]) / (dr * dr)


def wave_operator(values: np.ndarray, momentum: np.ndarray, dr: float) -> np.ndarray:
    result = static_operator(values, dr)
    result[-1] -= momentum[-1] / dr
    return result


def derivative(
    state: tuple[np.ndarray, ...], r: np.ndarray, dr: float, coupling: float
) -> tuple[np.ndarray, ...]:
    ux, uy, wr, wi, px, py, pwr, pwi = state
    norm = ux * ux + uy * uy
    s = norm / (r * r)
    coefficient = M * M - 2.0 * LAMBDA * s + 3.0 * G * s * s
    ar = wr / r
    ai = wi / r
    ax = wave_operator(ux, px, dr) - coefficient * ux + 2.0 * coupling * (ar * ux - ai * uy)
    ay = wave_operator(uy, py, dr) - coefficient * uy + 2.0 * coupling * (-ar * uy - ai * ux)
    awr = wave_operator(wr, pwr, dr) - M_A * M_A * wr + coupling * (ux * ux - uy * uy) / r
    awi = wave_operator(wi, pwi, dr) - M_A * M_A * wi - 2.0 * coupling * ux * uy / r
    return px, py, pwr, pwi, ax, ay, awr, awi


def combine(
    state: tuple[np.ndarray, ...], delta: tuple[np.ndarray, ...], scale: float
) -> tuple[np.ndarray, ...]:
    return tuple(a + scale * b for a, b in zip(state, delta))  # type: ignore[return-value]


def rk4(
    state: tuple[np.ndarray, ...], r: np.ndarray, dr: float, dt: float, coupling: float
) -> tuple[np.ndarray, ...]:
    k1 = derivative(state, r, dr, coupling)
    k2 = derivative(combine(state, k1, 0.5 * dt), r, dr, coupling)
    k3 = derivative(combine(state, k2, 0.5 * dt), r, dr, coupling)
    k4 = derivative(combine(state, k3, dt), r, dr, coupling)
    return tuple(
        value + (dt / 6.0) * (a + 2.0 * b + 2.0 * c + d)
        for value, a, b, c, d in zip(state, k1, k2, k3, k4)
    )  # type: ignore[return-value]


def centered_gradient(values: np.ndarray, dr: float) -> np.ndarray:
    ghost = np.empty(values.size + 2, dtype=np.float64)
    ghost[1:-1] = values
    ghost[0] = -values[0]
    ghost[-1] = values[-1]
    return (ghost[2:] - ghost[:-2]) / (2.0 * dr)


def total_energy(
    state: tuple[np.ndarray, ...], r: np.ndarray, dr: float, coupling: float
) -> float:
    ux, uy, wr, wi, px, py, pwr, pwi = state
    rho = ux * ux + uy * uy
    quadratic = -0.5 * dr * float(
        ux @ static_operator(ux, dr)
        + uy @ static_operator(uy, dr)
        + wr @ static_operator(wr, dr)
        + wi @ static_operator(wi, dr)
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
    return float(4.0 * math.pi * (quadratic + dr * np.sum(local)))


def metrics(
    state: tuple[np.ndarray, ...], r: np.ndarray, dr: float, coupling: float
) -> dict[str, float]:
    ux, uy, wr, wi, px, py, pwr, pwi = state
    rho = ux * ux + uy * uy
    gx = centered_gradient(ux, dr)
    gy = centered_gradient(uy, dr)
    carrier_density = (
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
    outer = r >= EXTERIOR_RADIUS
    charge_density = ux * py - uy * px
    number = 4.0 * math.pi * float(np.sum(rho) * dr)
    core_number = 4.0 * math.pi * float(np.sum(rho[core]) * dr)
    reservoir_gradient_r = centered_gradient(wr, dr)
    reservoir_gradient_i = centered_gradient(wi, dr)
    reservoir_energy_density = 0.5 * (
        pwr * pwr
        + pwi * pwi
        + reservoir_gradient_r * reservoir_gradient_r
        + reservoir_gradient_i * reservoir_gradient_i
        + M_A * M_A * (wr * wr + wi * wi)
    )
    reservoir_energy = 4.0 * math.pi * float(np.sum(reservoir_energy_density) * dr)
    reservoir_energy_centroid = float(
        np.sum(r * reservoir_energy_density)
        / max(np.sum(reservoir_energy_density), np.finfo(float).tiny)
    )
    return {
        "carrier_energy": 4.0 * math.pi * float(np.sum(carrier_density) * dr),
        "core_energy": 4.0 * math.pi * float(np.sum(carrier_density[core]) * dr),
        "full_energy": total_energy(state, r, dr, coupling),
        "reservoir_energy": reservoir_energy,
        "reservoir_energy_centroid": reservoir_energy_centroid,
        "number_total": number,
        "number_core": core_number,
        "core_fraction": core_number / max(number, np.finfo(float).tiny),
        "charge": 4.0 * math.pi * float(np.sum(charge_density) * dr),
        "core_charge": 4.0 * math.pi * float(np.sum(charge_density[core]) * dr),
        "rms_radius": math.sqrt(float(np.sum(r * r * rho) / max(np.sum(rho), np.finfo(float).tiny))),
        "core_density": 3.0 * float(np.sum(rho[core]) * dr) / (CORE_RADIUS**3),
        "exterior_support_fraction": float(
            np.sum(support_density[outer]) / max(np.sum(support_density), np.finfo(float).tiny)
        ),
        "source_rate": 4.0
        * math.pi
        * coupling
        * float(
            np.sum(
                -4.0 * (wr / r) * ux * uy
                - 2.0 * (wi / r) * (ux * ux - uy * uy)
            )
            * dr
        ),
        "boundary_charge_rate": 4.0 * math.pi * float(-ux[-1] * py[-1] + uy[-1] * px[-1]),
        "boundary_energy_rate": -4.0
        * math.pi
        * float(px[-1] ** 2 + py[-1] ** 2 + pwr[-1] ** 2 + pwi[-1] ** 2),
    }


def rerun(
    name: str, count: int, dt: float, sign: int, amplitude: float, coupling: float
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    r, dr = grid(count)
    state = make_initial(count, sign, amplitude)
    times = np.arange(0.0, T_FINAL + SAVE_INTERVAL / 2.0, SAVE_INTERVAL)
    stride = round(SAVE_INTERVAL / dt)
    total_steps = round(T_FINAL / dt)
    if stride * (len(times) - 1) != total_steps:
        raise VerificationError(f"nonintegral schedule: {name}")
    archive = {key: [] for key in ("ux", "uy", "wr", "wi", "px", "py", "pwr", "pwi")}
    rows: list[dict[str, Any]] = []
    first = metrics(state, r, dr, coupling)
    q0 = first["charge"]
    e0 = first["full_energy"]
    qsrc = qout = qabs = eout = 0.0
    previous = first
    for index in range(total_steps + 1):
        if index % stride == 0:
            current = metrics(state, r, dr, coupling)
            rows.append({
                "time": float(times[len(rows)]),
                **current,
                "charge_ledger_residual": current["charge"] - q0 - qsrc - qout,
                "energy_ledger_residual": current["full_energy"] - e0 - eout,
                "source_cumulative": qsrc,
                "boundary_charge_cumulative": qout,
                "source_abs_cumulative": qabs,
                "boundary_energy_cumulative": eout,
            })
            for key, value in zip(archive, state):
                archive[key].append(value.copy())
        if index == total_steps:
            break
        state = rk4(state, r, dr, dt, coupling)
        if not all(np.all(np.isfinite(value)) for value in state):
            raise VerificationError(f"nonfinite independent state: {name}:{index}")
        current = metrics(state, r, dr, coupling)
        qsrc += dt * 0.5 * (previous["source_rate"] + current["source_rate"])
        qout += dt * 0.5 * (previous["boundary_charge_rate"] + current["boundary_charge_rate"])
        qabs += dt * 0.5 * (abs(previous["source_rate"]) + abs(current["source_rate"]))
        eout += dt * 0.5 * (previous["boundary_energy_rate"] + current["boundary_energy_rate"])
        previous = current
    return {"name": name, "count": count, "dt": dt, "rows": rows}, {
        key: np.asarray(value) for key, value in archive.items()
    } | {
        "r": r,
        "times": times,
        "reservoir_energy": np.asarray([row["reservoir_energy"] for row in rows]),
        "reservoir_energy_centroid": np.asarray(
            [row["reservoir_energy_centroid"] for row in rows]
        ),
    }


def close(a: float, b: float, tolerance: float = 2.0e-8) -> bool:
    return abs(a - b) <= tolerance * max(1.0, abs(a), abs(b))


def late_average(rows: list[dict[str, Any]], key: str) -> float:
    return float(np.mean([row[key] for row in rows if row["time"] >= LATE_START]))


def arm_means(rows: list[dict[str, Any]]) -> dict[str, float]:
    late = [row for row in rows if row["time"] >= LATE_START]
    return {
        "core_energy": float(np.mean([row["core_energy"] for row in late])),
        "absolute_core_charge": float(np.mean([abs(row["core_charge"]) for row in late])),
        "core_fraction": float(np.mean([row["core_fraction"] for row in late])),
        "exterior_support_fraction": float(np.mean([row["exterior_support_fraction"] for row in late])),
        "rms_radius": float(np.mean([row["rms_radius"] for row in late])),
    }


def scientific_predicates(runs: dict[str, dict[str, Any]]) -> tuple[dict[str, bool], dict[str, Any]]:
    vacuum = runs["vacuum_control"]["rows"]
    reservoir = runs["reservoir_control"]["rows"]
    positive = runs["positive"]["rows"]
    negative = runs["negative"]["rows"]
    fine = runs["positive_fine"]["rows"]
    late = [row for row in positive if row["time"] >= LATE_START]
    vacuum_density = late_average(vacuum, "core_density")
    reservoir_centroid_initial = positive[0]["reservoir_energy_centroid"]
    reservoir_centroid_min = min(
        row["reservoir_energy_centroid"] for row in positive if row["time"] <= OVERLAP_END
    )
    incoming_shell_reaches_core = 14.0 <= reservoir_centroid_initial <= 18.0 and reservoir_centroid_min <= 8.0
    primary_means = arm_means(positive)
    fine_means = arm_means(fine)
    resolution = {
        key: abs(primary_means[key] - fine_means[key]) / max(1.0, abs(primary_means[key]), abs(fine_means[key]))
        for key in primary_means
    }
    corrected = np.asarray(
        [row["charge"] - row["source_cumulative"] - row["boundary_charge_cumulative"] for row in late],
        dtype=np.float64,
    )
    drift = float(np.ptp(corrected)) / max(float(np.max(np.abs(corrected))), np.finfo(float).tiny)
    at_overlap = next(row for row in positive if abs(row["time"] - OVERLAP_END) < 1.0e-12)
    source_total = positive[-1]["source_abs_cumulative"]
    tail_ratio = (source_total - at_overlap["source_abs_cumulative"]) / max(1.0, source_total)
    even = ("carrier_energy", "full_energy", "number_total", "rms_radius", "core_density")
    cp_even_error = max(
        abs(positive[i][key] - negative[i][key]) for i in range(len(positive)) for key in even
    )
    cp_charge_error = max(abs(positive[i]["charge"] + negative[i]["charge"]) for i in range(len(positive)))
    reservoir_control_error = max(
        abs(vacuum[i][key] - reservoir[i][key])
        for i in range(len(vacuum))
        for key in ("number_total", "core_density", "rms_radius")
    )
    q_residual = max(abs(row["charge_ledger_residual"]) for row in positive)
    e_residual = max(abs(row["energy_ledger_residual"]) for row in positive)
    q_scale = max(
        1.0,
        max(abs(row["charge"]) for row in positive),
        max(abs(row["source_cumulative"]) for row in positive),
        max(abs(row["boundary_charge_cumulative"]) for row in positive),
    )
    e_scale = max(
        1.0,
        max(abs(row["full_energy"]) for row in positive),
        max(abs(row["boundary_energy_cumulative"]) for row in positive),
    )
    predicates = {
        "core_density_amplified": late_average(positive, "core_density") >= 4.0 * vacuum_density,
        "core_retention": min(row["core_fraction"] for row in late) >= 0.80,
        "localized_support_max": max(row["exterior_support_fraction"] for row in late) < 0.25,
        "localized_support_mean": late_average(positive, "exterior_support_fraction") < 0.20,
        "charge_magnitude": min(abs(row["core_charge"]) for row in late) > 200.0,
        "corrected_post_overlap_charge_drift": drift < 0.05,
        "subthreshold_core_energy_per_charge": max(
            row["core_energy"] / max(abs(row["core_charge"]), np.finfo(float).tiny) for row in late
        ) < M,
        "source_decoupling": tail_ratio < 0.15,
        "cp_conjugacy": cp_even_error < 1.0e-8 and cp_charge_error < 1.0e-8 and positive[-1]["charge"] * negative[-1]["charge"] < 0.0,
        "resolution": all(value < 0.05 for value in resolution.values()),
        "charge_ledger": q_residual / q_scale < 1.0e-5,
        "energy_ledger": e_residual / e_scale < 1.0e-5,
        "reservoir_control": reservoir_control_error < 1.0e-8,
        "incoming_shell_reaches_core": incoming_shell_reaches_core,
        "finite_state": finite(runs),
    }
    controls = {
        "vacuum_late_core_density": vacuum_density,
        "resolution_relative_errors": resolution,
        "cp_max_even_metric_error": cp_even_error,
        "cp_max_charge_sum_error": cp_charge_error,
        "reservoir_control_max_error": reservoir_control_error,
        "source_tail_ratio": tail_ratio,
        "corrected_post_overlap_charge_drift": drift,
        "max_charge_ledger_residual": q_residual,
        "max_energy_ledger_residual": e_residual,
        "charge_ledger_scale": q_scale,
        "energy_ledger_scale": e_scale,
        "late_mean_core_density": late_average(positive, "core_density"),
        "late_min_abs_core_charge": min(abs(row["core_charge"]) for row in late),
        "late_max_core_energy_per_charge": max(
            row["core_energy"] / max(abs(row["core_charge"]), np.finfo(float).tiny) for row in late
        ),
        "reservoir_centroid_initial": reservoir_centroid_initial,
        "reservoir_centroid_min_before_overlap": reservoir_centroid_min,
    }
    return predicates, controls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    primary_dir = args.primary_dir.resolve()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise VerificationError(f"refusing to overwrite nonempty output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    primary_path = primary_dir / "result.json"
    if not primary_path.is_file():
        raise VerificationError("missing primary result.json")
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    if primary.get("schema") != "cassi.matter-formation.closed-cp-incoming-reservoir.v11":
        raise VerificationError("unexpected primary schema")
    if primary.get("protocol_sha256") != sha256(PROTOCOL):
        raise VerificationError("primary protocol hash mismatch")
    expected_parameters = {
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
        "reservoir_center": RESERVOIR_CENTER,
        "core_radius": CORE_RADIUS,
        "exterior_radius": EXTERIOR_RADIUS,
        "overlap_end": OVERLAP_END,
        "late_start": LATE_START,
    }
    actual_parameters = primary.get("parameters")
    if not isinstance(actual_parameters, dict):
        raise VerificationError("primary parameters missing")
    for key, expected_value in expected_parameters.items():
        actual_value = actual_parameters.get(key)
        if actual_value is None or not math.isclose(
            float(actual_value), float(expected_value), rel_tol=0.0, abs_tol=1.0e-12
        ):
            raise VerificationError(f"primary parameter mismatch: {key}")
    for record in primary.get("source_records", []):
        source = ROOT / record["path"]
        copied = primary_dir / "sources" / record["path"]
        if not source.is_file() or sha256(source) != record["sha256"]:
            raise VerificationError(f"current source identity mismatch: {record['path']}")
        if not copied.is_file() or sha256(copied) != record["sha256"]:
            raise VerificationError(f"retained source identity mismatch: {record['path']}")
    expected = {
        "vacuum_control": (N_PRIMARY, DT_PRIMARY, +1, 0.0, 0.0),
        "reservoir_control": (N_PRIMARY, DT_PRIMARY, +1, RESERVOIR_AMPLITUDE, 0.0),
        "positive": (N_PRIMARY, DT_PRIMARY, +1, RESERVOIR_AMPLITUDE, KAPPA),
        "negative": (N_PRIMARY, DT_PRIMARY, -1, RESERVOIR_AMPLITUDE, KAPPA),
        "positive_fine": (N_FINE, DT_FINE, +1, RESERVOIR_AMPLITUDE, KAPPA),
    }
    independent: dict[str, dict[str, Any]] = {}
    independent_arrays: dict[str, dict[str, np.ndarray]] = {}
    raw_errors: dict[str, float] = {}
    archive_checks: dict[str, bool] = {}
    summary_checks: dict[str, bool] = {}
    for name, (count, dt, sign, amplitude, coupling) in expected.items():
        run, arrays = rerun(name, count, dt, sign, amplitude, coupling)
        independent[name] = run
        independent_arrays[name] = arrays
        primary_run = primary["runs"][name]
        if len(run["rows"]) != len(primary_run["rows"]):
            raise VerificationError(f"checkpoint count mismatch: {name}")
        row_ok = True
        for left, right in zip(run["rows"], primary_run["rows"]):
            for key, value in left.items():
                if not close(float(value), float(right[key])):
                    row_ok = False
                    break
        summary_checks[name] = row_ok
        archive_path = primary_dir / primary_run["archive"]
        if not archive_path.is_file():
            raise VerificationError(f"missing primary archive: {name}")
        with np.load(archive_path) as stored:
            maximum = 0.0
            for key, values in arrays.items():
                if key not in stored:
                    raise VerificationError(f"missing primary archive array: {name}:{key}")
                actual = np.asarray(stored[key])
                if actual.shape != values.shape:
                    raise VerificationError(f"archive shape mismatch: {name}:{key}")
                maximum = max(maximum, float(np.max(np.abs(actual - values))))
            raw_errors[name] = maximum
            archive_checks[name] = maximum < 2.0e-8
    cp_raw_error = max(
        float(np.max(np.abs(independent_arrays["positive"][key] - sign * independent_arrays["negative"][key])))
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
    predicates, controls = scientific_predicates(independent)
    predicates["cp_raw_state"] = cp_raw_error < 1.0e-8
    controls["cp_max_raw_state_error"] = cp_raw_error
    numerical_pass = bool(all(archive_checks.values()) and all(summary_checks.values()) and finite(independent))
    scientific_pass = numerical_pass and all(predicates.values())
    payload = {
        "schema": SCHEMA,
        "primary_receipt": {"path": relative(primary_path), "sha256": sha256(primary_path)},
        "protocol_sha256": sha256(PROTOCOL),
        "independent_sources": {
            "primary_solver": {"path": relative(PRIMARY), "sha256": sha256(PRIMARY)},
            "protocol": {"path": relative(PROTOCOL), "sha256": sha256(PROTOCOL)},
        },
        "raw_archive_max_abs_error": raw_errors,
        "raw_archive_checks": archive_checks,
        "summary_checks": summary_checks,
        "controls": controls,
        "predicates": predicates,
        "numerical_pass": numerical_pass,
        "reproduced_primary_verdict": (
            "CAPTURED—conditional pair-frequency-resonant incoming-shell formation"
            if scientific_pass
            else "DOES NOT EMERGE—conditional pair-frequency-resonant incoming-shell formation"
        ),
        "elapsed_seconds": time.perf_counter() - started,
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
    }
    if not numerical_pass:
        payload["reproduced_primary_verdict"] = "INCONCLUSIVE"
    shutil.copyfile(PROTOCOL, output / PROTOCOL.name)
    write_json(output / "verification.json", payload)
    print(json.dumps({"failed_archive_checks": [k for k, v in archive_checks.items() if not v], "summary_checks": summary_checks, "reproduced_primary_verdict": payload["reproduced_primary_verdict"], "predicates": predicates}, indent=2))
    return 0 if numerical_pass else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"independent verification failed: {exc}", file=sys.stderr)
        raise
