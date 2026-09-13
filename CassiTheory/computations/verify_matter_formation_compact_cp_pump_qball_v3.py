#!/usr/bin/env python3
"""Independently rebuild and verify the compact CP-pump formation receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "matter-formation-compact-cp-pump-qball-v3b-prereg.md"
SOLVER = ROOT / "computations" / "matter_formation_compact_cp_pump_qball_v3.py"
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


class VerificationError(RuntimeError):
    pass


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def finite(value: Any) -> bool:
    if isinstance(value, dict):
        return all(finite(item) for item in value.values())
    if isinstance(value, list):
        return all(finite(item) for item in value)
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    return True


def grid(count: int) -> tuple[np.ndarray, float]:
    spacing = RADIUS / count
    return (np.arange(count, dtype=np.float64) + 0.5) * spacing, spacing


def vacuum(r: np.ndarray) -> State:
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


def initial(count: int, arm: int) -> State:
    r, _ = grid(count)
    ux, uy, px, py = vacuum(r)
    if arm < 0:
        uy, py = -uy, -py
    return ux, uy, px, py


def pump(t: float, r: np.ndarray, arm: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if arm == 0 or t < 0.0 or t >= PULSE_DURATION:
        zeros = np.zeros_like(r)
        return zeros, zeros, zeros, zeros
    sign = -1.0 if arm < 0 else 1.0
    envelope = math.sin(math.pi * t / PULSE_DURATION) ** 2
    envelope_dot = math.pi / PULSE_DURATION * math.sin(2.0 * math.pi * t / PULSE_DURATION)
    profile = np.exp(-0.5 * (r / PULSE_WIDTH) ** 2)
    amplitude = PULSE_AMPLITUDE * profile
    phase = PULSE_FREQUENCY * t
    cp, sp = math.cos(phase), math.sin(phase)
    jr, ji = amplitude * envelope * cp, sign * amplitude * envelope * sp
    jr_dot = amplitude * (envelope_dot * cp - envelope * PULSE_FREQUENCY * sp)
    ji_dot = sign * amplitude * (envelope_dot * sp + envelope * PULSE_FREQUENCY * cp)
    return jr, ji, jr_dot, ji_dot


def lap(values: np.ndarray, momenta: np.ndarray, spacing: float) -> np.ndarray:
    padded = np.empty(values.size + 2, dtype=np.float64)
    padded[1:-1], padded[0], padded[-1] = values, -values[0], values[-1] - spacing * momenta[-1]
    return (padded[2:] - 2.0 * padded[1:-1] + padded[:-2]) / spacing**2


def grad(values: np.ndarray, momenta: np.ndarray, spacing: float) -> np.ndarray:
    padded = np.empty(values.size + 2, dtype=np.float64)
    padded[1:-1], padded[0], padded[-1] = values, -values[0], values[-1] - spacing * momenta[-1]
    return (padded[2:] - padded[:-2]) / (2.0 * spacing)
 
def lap_static(values: np.ndarray, spacing: float) -> np.ndarray:
    padded = np.empty(values.size + 2, dtype=np.float64)
    padded[1:-1], padded[0], padded[-1] = values, -values[0], values[-1]
    return (padded[2:] - 2.0 * padded[1:-1] + padded[:-2]) / spacing**2


def compatible_energy(state: State, r: np.ndarray, spacing: float) -> float:
    ux, uy, px, py = state
    rho = ux * ux + uy * uy
    gradient_energy = -0.5 * (ux * lap_static(ux, spacing) + uy * lap_static(uy, spacing))
    local_terms = (
        0.5 * (px * px + py * py)
        + 0.5 * M * M * rho
        - 0.5 * LAMBDA * rho * rho / r**2
        + 0.5 * G * rho**3 / r**4
    )
    return float(4.0 * math.pi * np.sum(local_terms + gradient_energy) * spacing)


 


def derivative(state: State, t: float, r: np.ndarray, spacing: float, arm: int) -> State:
    ux, uy, px, py = state
    rho = ux * ux + uy * uy
    s = rho / r**2
    coeff = M * M - 2.0 * LAMBDA * s + 3.0 * G * s * s
    jr, ji, _jr_dot, _ji_dot = pump(t, r, arm)
    return (
        px,
        py,
        lap(ux, px, spacing) - coeff * ux + 2.0 * KAPPA * (jr * ux - ji * uy),
        lap(uy, py, spacing) - coeff * uy + 2.0 * KAPPA * (-jr * uy - ji * ux),
    )


def add(state: State, derivative_state: State, scale: float) -> State:
    return tuple(a + scale * b for a, b in zip(state, derivative_state))  # type: ignore[return-value]


def step(state: State, t: float, r: np.ndarray, spacing: float, dt: float, arm: int) -> State:
    first = derivative(state, t, r, spacing, arm)
    second = derivative(add(state, first, dt / 2.0), t + dt / 2.0, r, spacing, arm)
    third = derivative(add(state, second, dt / 2.0), t + dt / 2.0, r, spacing, arm)
    fourth = derivative(add(state, third, dt), t + dt, r, spacing, arm)
    return tuple(
        a + dt * (b + 2.0 * c + 2.0 * d + e) / 6.0
        for a, b, c, d, e in zip(state, first, second, third, fourth)
    )  # type: ignore[return-value]


def flux_rates(state: State, t: float, r: np.ndarray, spacing: float, arm: int) -> dict[str, float]:
    ux, uy, px, py = state
    jr, ji, jr_dot, ji_dot = pump(t, r, arm)
    q_source = float(
        4.0 * math.pi * np.sum((-4.0 * KAPPA * jr * ux * uy - 2.0 * KAPPA * ji * (ux * ux - uy * uy))) * spacing
    )
    ghost_x, ghost_y = ux[-1] - spacing * px[-1], uy[-1] - spacing * py[-1]
    q_flux = float(4.0 * math.pi * (ux[-1] * ghost_y - uy[-1] * ghost_x) / spacing)
    work = float(
        4.0
        * math.pi
        * np.sum(-KAPPA * (jr_dot * (ux * ux - uy * uy) - 2.0 * ji_dot * ux * uy))
        * spacing
    )
    energy_flux = float(-4.0 * math.pi * (px[-1] * px[-1] + py[-1] * py[-1]))
    return {
        "source_charge_rate": q_source,
        "boundary_charge_flux": q_flux,
        "pump_work_rate": work,
        "boundary_energy_flux": energy_flux,
    }


def observables(
    state: State,
    t: float,
    r: np.ndarray,
    spacing: float,
    arm: int,
    ledger: dict[str, float],
    initial_energy: float,
) -> dict[str, float]:
    ux, uy, px, py = state
    rho = ux * ux + uy * uy
    gx, gy = grad(ux, px, spacing), grad(uy, py, spacing)
    density = (
        0.5 * (px * px + py * py + gx * gx + gy * gy)
        + 0.5 * M * M * rho
        - 0.5 * LAMBDA * rho * rho / r**2
        + 0.5 * G * rho**3 / r**4
    )
    support = 0.5 * (px * px + py * py + gx * gx + gy * gy + M * M * rho) + 0.5 * G * rho**3 / r**4
    jr, ji, _jr_dot, _ji_dot = pump(t, r, arm)
    pair = -KAPPA * (jr * (ux * ux - uy * uy) - 2.0 * ji * ux * uy)
    core, exterior = r <= CORE_RADIUS, r >= EXTERIOR_RADIUS
    number = 4.0 * math.pi * float(np.sum(rho) * spacing)
    core_number = 4.0 * math.pi * float(np.sum(rho[core]) * spacing)
    charge_density = ux * py - uy * px
    charge = 4.0 * math.pi * float(np.sum(charge_density) * spacing)
    core_charge = 4.0 * math.pi * float(np.sum(charge_density[core]) * spacing)
    carrier_energy = compatible_energy(state, r, spacing)
    full_energy = carrier_energy + 4.0 * math.pi * float(np.sum(pair) * spacing)
    core_energy = 4.0 * math.pi * float(np.sum(density[core]) * spacing)
    current = flux_rates(state, t, r, spacing, arm)
    balance_q = charge - ledger["initial_charge"] - ledger["source_charge_cumulative"] - ledger["boundary_charge_cumulative"]
    balance_e = full_energy - initial_energy - ledger["pump_work_cumulative"] - ledger["boundary_energy_cumulative"]
    return {
        "time": float(t),
        "carrier_energy": carrier_energy,
        "full_energy": full_energy,
        "number_total": number,
        "number_core": core_number,
        "core_fraction": core_number / max(number, np.finfo(float).tiny),
        "charge": charge,
        "core_charge": core_charge,
        "core_energy": core_energy,
        "core_energy_per_charge": core_energy / max(abs(core_charge), np.finfo(float).tiny),
        "core_density": 3.0 * float(np.sum(rho[core]) * spacing) / CORE_RADIUS**3,
        "exterior_support_fraction": float(np.sum(support[exterior]) / max(np.sum(support), np.finfo(float).tiny)),
        "rms_radius": math.sqrt(float(np.sum(r * r * rho) / max(np.sum(rho), np.finfo(float).tiny))),
        **current,
        "source_charge_cumulative": ledger["source_charge_cumulative"],
        "boundary_charge_cumulative": ledger["boundary_charge_cumulative"],
        "pump_work_cumulative": ledger["pump_work_cumulative"],
        "boundary_energy_cumulative": ledger["boundary_energy_cumulative"],
        "charge_balance_residual": balance_q,
        "energy_balance_residual": balance_e,
    }


def integrate_ledger(ledger: dict[str, float], left: dict[str, float], right: dict[str, float], dt: float) -> None:
    for rate, cumulative in (
        ("source_charge_rate", "source_charge_cumulative"),
        ("boundary_charge_flux", "boundary_charge_cumulative"),
        ("pump_work_rate", "pump_work_cumulative"),
        ("boundary_energy_flux", "boundary_energy_cumulative"),
    ):
        ledger[cumulative] += 0.5 * (left[rate] + right[rate]) * dt


def run(count: int, dt: float, arm: int) -> tuple[list[dict[str, float]], dict[str, np.ndarray]]:
    r, spacing = grid(count)
    state = initial(count, arm)
    total_steps, checkpoint_steps = round(T_FINAL / dt), round(SAVE_INTERVAL / dt)
    ledger = {
        "initial_charge": 4.0 * math.pi * float(np.sum(state[0] * state[3] - state[1] * state[2]) * spacing),
        "source_charge_cumulative": 0.0,
        "boundary_charge_cumulative": 0.0,
        "pump_work_cumulative": 0.0,
        "boundary_energy_cumulative": 0.0,
    }
    initial_energy = compatible_energy(state, r, spacing)
    rows: list[dict[str, float]] = []
    arrays: dict[str, list[np.ndarray]] = {key: [] for key in ("ux", "uy", "px", "py")}
    left_rates = flux_rates(state, 0.0, r, spacing, arm)
    for index in range(total_steps + 1):
        if index % checkpoint_steps == 0:
            rows.append(observables(state, index * dt, r, spacing, arm, ledger, initial_energy))
            for key, value in zip(arrays, state):
                arrays[key].append(value.copy())
        if index == total_steps:
            break
        next_state = step(state, index * dt, r, spacing, dt, arm)
        if not all(np.all(np.isfinite(value)) for value in next_state):
            raise VerificationError(f"nonfinite rebuilt state at step {index + 1}")
        right_rates = flux_rates(next_state, (index + 1) * dt, r, spacing, arm)
        integrate_ledger(ledger, left_rates, right_rates, dt)
        state, left_rates = next_state, right_rates
    result_arrays = {key: np.asarray(value) for key, value in arrays.items()}
    result_arrays["r"] = r
    result_arrays["times"] = np.arange(0.0, T_FINAL + 0.5 * SAVE_INTERVAL, SAVE_INTERVAL)
    return rows, result_arrays


def summary(rows: list[dict[str, float]]) -> dict[str, float]:
    late = [row for row in rows if row["time"] >= LATE_START]
    if not late:
        raise VerificationError("rebuilt late window is empty")
    def avg(key: str) -> float:
        return float(np.mean([row[key] for row in late]))
    return {
        "mean_core_density": avg("core_density"),
        "mean_core_fraction": avg("core_fraction"),
        "minimum_core_fraction": float(min(row["core_fraction"] for row in late)),
        "mean_exterior_support_fraction": avg("exterior_support_fraction"),
        "maximum_exterior_support_fraction": float(max(row["exterior_support_fraction"] for row in late)),
        "mean_core_energy": avg("core_energy"),
        "mean_abs_core_charge": float(np.mean([abs(row["core_charge"]) for row in late])),
        "minimum_abs_core_charge": float(min(abs(row["core_charge"]) for row in late)),
        "maximum_core_energy_per_charge": float(max(row["core_energy_per_charge"] for row in late)),
        "mean_rms_radius": avg("rms_radius"),
    }


def rel_error(left: float, right: float) -> float:
    return abs(left - right) / max(1.0, abs(left), abs(right))


def independent_predicates(
    rebuilt: dict[str, list[dict[str, float]]], rebuilt_arrays: dict[str, dict[str, np.ndarray]]
) -> tuple[dict[str, bool], dict[str, Any]]:
    positive = summary(rebuilt["positive"])
    fine = summary(rebuilt["positive_fine"])
    negative = summary(rebuilt["negative"])
    vacuum_rows = [row for row in rebuilt["vacuum_control"] if row["time"] >= LATE_START]
    vacuum_density = float(np.mean([row["core_density"] for row in vacuum_rows]))
    positive_rows = rebuilt["positive"]
    after = [row for row in positive_rows if row["time"] >= LATE_START]
    pulse = next(row for row in positive_rows if abs(row["time"] - PULSE_DURATION) < 1e-12)
    corrected = np.asarray([
        row["charge"] - row["boundary_charge_cumulative"] + pulse["boundary_charge_cumulative"]
        for row in after
    ])
    charge_drift = float(np.ptp(corrected) / max(np.max(np.abs(corrected)), np.finfo(float).tiny))
    source_after = max(abs(row["source_charge_rate"]) for row in positive_rows if row["time"] >= PULSE_DURATION)
    cp = rebuilt_arrays["positive"], rebuilt_arrays["negative"]
    cp_error = max(
        float(np.max(np.abs(cp[0]["ux"] - cp[1]["ux"]))),
        float(np.max(np.abs(cp[0]["uy"] + cp[1]["uy"]))),
        float(np.max(np.abs(cp[0]["px"] - cp[1]["px"]))),
        float(np.max(np.abs(cp[0]["py"] + cp[1]["py"]))),
    )
    resolution = {
        key: rel_error(positive[key], fine[key])
        for key in ("mean_core_energy", "mean_abs_core_charge", "mean_core_fraction", "mean_exterior_support_fraction", "mean_rms_radius")
    }
    cp_metrics = {
        key: rel_error(positive[key], negative[key])
        for key in ("mean_core_energy", "mean_core_fraction", "mean_exterior_support_fraction", "mean_rms_radius")
    }
    if not all(finite(row) for rows in rebuilt.values() for row in rows):
        raise VerificationError("rebuilt observables contain a nonfinite value")
    ledger_rows = rebuilt["positive"]
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
        "core_density_amplified": positive["mean_core_density"] >= 4.0 * vacuum_density,
        "core_retention": positive["minimum_core_fraction"] >= 0.80,
        "localized_support": positive["maximum_exterior_support_fraction"] < 0.25 and positive["mean_exterior_support_fraction"] < 0.20,
        "charge_and_post_pulse_continuity": positive["minimum_abs_core_charge"] >= 200.0 and charge_drift < 0.05 and source_after <= 1.0e-12,
        "subthreshold_core": positive["maximum_core_energy_per_charge"] < M,
        "cp_and_resolution": (
            cp_error < 1e-9
            and positive["mean_abs_core_charge"] >= 200.0
            and negative["mean_abs_core_charge"] >= 200.0
            and all(value < 0.05 for value in resolution.values())
            and all(value < 1e-9 for value in cp_metrics.values())
            and rebuilt["positive"][-1]["core_charge"] * rebuilt["negative"][-1]["core_charge"] < 0.0
        ),
        "flux_energy_ledger": ledger_relative_charge <= 1.0e-6 and ledger_relative_energy <= 1.0e-6,
    }
    evidence = {
        "vacuum_late_core_density": vacuum_density,
        "post_pulse_corrected_charge_drift": charge_drift,
        "post_pulse_source_max_abs": source_after,
        "cp_max_raw_state_error": cp_error,
        "resolution_relative_errors": resolution,
        "cp_metric_relative_errors": cp_metrics,
        "summaries": {"positive": positive, "negative": negative, "positive_fine": fine},
        "maximum_charge_balance_residual": maximum_charge_balance,
        "maximum_energy_balance_residual": maximum_energy_balance,
        "ledger_relative_charge": ledger_relative_charge,
        "ledger_relative_energy": ledger_relative_energy,
        "ledger_charge_scale": charge_scale,
        "ledger_energy_scale": energy_scale,
    }
    return predicates, evidence


def close_number(left: Any, right: Any, tolerance: float, label: str) -> None:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if not math.isclose(float(left), float(right), rel_tol=tolerance, abs_tol=tolerance):
            raise VerificationError(f"{label}: {left!r} != {right!r}")
        return
    if left != right:
        raise VerificationError(f"{label}: {left!r} != {right!r}")


def compare_rows(receipt_rows: list[dict[str, Any]], rebuilt_rows: list[dict[str, float]], name: str) -> None:
    if len(receipt_rows) != len(rebuilt_rows):
        raise VerificationError(f"{name}: checkpoint count mismatch")
    for index, (receipt, rebuilt) in enumerate(zip(receipt_rows, rebuilt_rows)):
        if set(receipt) != set(rebuilt):
            raise VerificationError(f"{name}[{index}]: observable key mismatch")
        for key in rebuilt:
            close_number(receipt[key], rebuilt[key], 2e-10, f"{name}[{index}].{key}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    result_path = output / "result.json"
    if not result_path.is_file():
        raise VerificationError(f"missing primary result: {result_path}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema") != SCHEMA:
        raise VerificationError("schema mismatch")
    if result.get("protocol") != rel(PROTOCOL) or result.get("protocol_sha256") != digest(PROTOCOL):
        raise VerificationError("protocol provenance mismatch")
    expected_sources = {
        rel(PROTOCOL): digest(PROTOCOL),
        rel(SOLVER): digest(SOLVER),
    }
    for source in result.get("source_records", []):
        path = str(source.get("path"))
        if path not in expected_sources or source.get("sha256") != expected_sources[path]:
            raise VerificationError(f"source record mismatch: {path}")
        copied = output / "sources" / path
        if not copied.is_file() or digest(copied) != expected_sources[path]:
            raise VerificationError(f"source snapshot mismatch: {path}")
    expected_parameters = {
        "radius": RADIUS, "primary_grid": N_PRIMARY, "fine_grid": N_FINE,
        "dt_primary": DT_PRIMARY, "dt_fine": DT_FINE, "T_final": T_FINAL,
        "save_interval": SAVE_INTERVAL, "modes": MODES, "seed": SEED, "m": M,
        "lambda": LAMBDA, "g": G, "kappa": KAPPA, "pulse_amplitude": PULSE_AMPLITUDE,
        "pulse_width": PULSE_WIDTH, "pulse_frequency": PULSE_FREQUENCY,
        "pulse_duration": PULSE_DURATION, "core_radius": CORE_RADIUS,
        "exterior_radius": EXTERIOR_RADIUS, "late_start": LATE_START,
    }
    if result.get("parameters") != expected_parameters:
        raise VerificationError("parameter block differs from the preregistered values")
    if not finite(result):
        raise VerificationError("primary receipt contains a nonfinite JSON value")
    specs = {
        "vacuum_control": (N_PRIMARY, DT_PRIMARY, 0),
        "positive": (N_PRIMARY, DT_PRIMARY, 1),
        "negative": (N_PRIMARY, DT_PRIMARY, -1),
        "positive_fine": (N_FINE, DT_FINE, 1),
    }
    rebuilt: dict[str, list[dict[str, float]]] = {}
    rebuilt_arrays: dict[str, dict[str, np.ndarray]] = {}
    archive_diffs: dict[str, float] = {}
    for name, (count, dt, arm) in specs.items():
        receipt_run = result["runs"].get(name)
        if receipt_run is None:
            raise VerificationError(f"missing run {name}")
        rows, arrays = run(count, dt, arm)
        compare_rows(receipt_run["rows"], rows, name)
        archive_path = output / str(receipt_run["archive"])
        if not archive_path.is_file():
            raise VerificationError(f"missing archive {archive_path}")
        saved = np.load(archive_path)
        max_diff = 0.0
        for key in ("ux", "uy", "px", "py", "r", "times"):
            if saved[key].shape != arrays[key].shape:
                raise VerificationError(f"{name}.{key}: archive shape mismatch")
            max_diff = max(max_diff, float(np.max(np.abs(saved[key] - arrays[key]))))
        if max_diff > 2e-12:
            raise VerificationError(f"{name}: archive reconstruction differs by {max_diff}")
        archive_diffs[name] = max_diff
        rebuilt[name], rebuilt_arrays[name] = rows, arrays
    predicates, evidence = independent_predicates(rebuilt, rebuilt_arrays)
    if result.get("predicates") != predicates:
        raise VerificationError("primary predicates differ from independent predicates")
    if bool(result.get("complete_physical_matter_formation")):
        raise VerificationError("scope boundary was overstated")
    expected_verdict = (
        "INCONCLUSIVE—compact CP-pump formation ledger failure"
        if not predicates["flux_energy_ledger"]
        else "CAPTURED—conditional compact CP-pump vacuum-to-carrier formation"
        if all(predicates.values())
        else "DOES NOT EMERGE—conditional compact CP-pump vacuum-to-carrier formation"
    )
    if result.get("scientific_verdict") != expected_verdict:
        raise VerificationError("verdict does not follow the independent predicates")
    verification = {
        "schema": SCHEMA + ".verification",
        "primary_result": "result.json",
        "solver_sha256": digest(SOLVER),
        "protocol_sha256": digest(PROTOCOL),
        "rebuild": "independent finite-volume implementation; no import from primary solver",
        "archive_max_abs_differences": archive_diffs,
        "predicates": predicates,
        "evidence": evidence,
        "status": "PASS",
        "scientific_verdict": expected_verdict,
        "complete_physical_matter_formation": False,
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform()},
    }
    (output / "verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "scientific_verdict": expected_verdict, "predicates": predicates}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"verification failed: {exc}")
        raise
