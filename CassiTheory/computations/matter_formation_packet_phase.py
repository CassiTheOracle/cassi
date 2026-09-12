#!/usr/bin/env python3
"""Run the preregistered fixed-charge relative-phase basin probe."""
from __future__ import annotations

import argparse
import math
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
if str(COMPUTATIONS) not in sys.path:
    sys.path.insert(0, str(COMPUTATIONS))

import matter_formation_wave_capture as dynamics  # noqa: E402
from matter_formation_neutral_packets import CylindricalGrid  # noqa: E402
from matter_formation_packet_phase_spec import (
    ARM_SPECS,
    ARMS,
    COUPLED_CANDIDATES,
    CENTER,
    CORE_RADIUS,
    GRID_SPECS,
    INITIAL_CORE_FRACTION_MAX,
    INITIAL_OVERLAP_MAX,
    LATE_START,
    NOMINAL_PACKET_CHARGE,
    OMEGA_OFFSET_SQUARED,
    SAMPLE_DT,
    SNAPSHOT_TIMES,
    T_FINAL,
    TOTAL_CHARGE,
    INWARD_PHASE_SIGN,
    OUTWARD_PHASE_SIGN,
    ROBUST_COMPARISON_OBSERVABLES,
    RETAINED_FRACTION,
    BINDING_RATIO_MAX,
    RULE_CONTROL_ARM,
    UNCOUPLED_CONTROL_ARM,
    WAVE_NUMBER,
    WIDTH,
    RELATIVE_PHASES,
)

SELF = Path(__file__).resolve()
PREREG = COMPUTATIONS / "matter_formation_packet_phase_prereg.md"
SPEC_SOURCE = COMPUTATIONS / "matter_formation_packet_phase_spec.py"
NEUTRAL_SOURCE = COMPUTATIONS / "matter_formation_neutral_packets.py"
CLOUD_SOURCE = COMPUTATIONS / "matter_formation_radial_cloud.py"
VERIFIER_SOURCE = COMPUTATIONS / "verify_matter_formation_packet_phase.py"
SCHEMA = "matter-formation-packet-relative-phase-primary-v1"


def sha256(path: Path) -> str:
    return dynamics.sha256(path)


def finite_number(value: Any) -> bool:
    return dynamics.finite_number(value)


def write_json(path: Path, value: dict[str, Any]) -> None:
    dynamics.write_json(path, value)


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=True, exist_ok=False)
    result: dict[str, str] = {}
    for path in (SELF, PREREG, SPEC_SOURCE, NEUTRAL_SOURCE, CLOUD_SOURCE, VERIFIER_SOURCE):
        relative = path.relative_to(ROOT).as_posix()
        destination = source_dir / relative.replace("/", "__")
        shutil.copyfile(path, destination)
        result[relative] = sha256(path)
    return result


def assemble_primary(grid: CylindricalGrid, arm: str) -> tuple[torch.Tensor, torch.Tensor, float, dict[str, Any]]:
    """Assemble one primary preparation from the declarative specification."""
    config = ARM_SPECS[arm]
    pair = bool(config["pair"])
    uncoupled = bool(config["uncoupled"])
    center = float(config["center"])
    width = float(config["width"])
    wave_number = float(config["wave_number"])
    phase_sign = float(config["phase_sign"])
    relative_phase = float(config["relative_phase"])
    omega = dynamics.OMEGA_INF if not pair else math.sqrt(dynamics.OMEGA_INF**2 + OMEGA_OFFSET_SQUARED * wave_number**2)
    zeta = grid.axial
    if config["kind"] == "single":
        envelope = torch.exp(-(grid.r2 + zeta[None, :].square()) / (2.0 * width**2))
        complex_field = envelope.to(dtype=torch.complex128)
        centers = (0.0,)
    else:
        envelope_right = torch.exp(-(grid.r2 + (zeta[None, :] + center).square()) / (2.0 * width**2))
        envelope_left = torch.exp(-(grid.r2 + (zeta[None, :] - center).square()) / (2.0 * width**2))
        phase_right = phase_sign * wave_number * (zeta[None, :] + center)
        phase_left = -phase_sign * wave_number * (zeta[None, :] - center)
        left_multiplier = complex(math.cos(relative_phase), math.sin(relative_phase))
        complex_field = envelope_right * torch.exp(1j * phase_right) + left_multiplier * envelope_left * torch.exp(1j * phase_left)
        centers = (-center, center)
    norm = torch.sum(grid.volume * (complex_field.real.square() + complex_field.imag.square()))
    norm_value = float(norm)
    if not math.isfinite(norm_value) or norm_value <= 0.0:
        raise RuntimeError(f"invalid initial normalization for {arm}")
    complex_field = complex_field * math.sqrt(TOTAL_CHARGE / (2.0 * dynamics.A * omega * norm_value))
    q = torch.zeros((3, grid.nr, grid.nz), dtype=torch.float64, device="cuda")
    q[1] = complex_field.real
    q[2] = complex_field.imag
    v = torch.zeros_like(q)
    v[1] = omega * q[2]
    v[2] = -omega * q[1]
    overlap = 0.0
    if pair:
        a = torch.exp(-(grid.r2 + (zeta[None, :] + center).square()) / (2.0 * width**2))
        b = torch.exp(-(grid.r2 + (zeta[None, :] - center).square()) / (2.0 * width**2))
        overlap = float(torch.abs(torch.sum(grid.volume * a * b)) / torch.sqrt(torch.sum(grid.volume * a.square()) * torch.sum(grid.volume * b.square())))
    rho = 2.0 * dynamics.A * omega * (q[1].square() + q[2].square())
    distance = torch.sqrt(grid.r2 + grid.axial[None, :].square())
    initial_core = float((grid.volume * rho * (distance < CORE_RADIUS)).sum()) / TOTAL_CHARGE
    metadata: dict[str, Any] = {
        "charge": TOTAL_CHARGE,
        "nominal_packet_charge": NOMINAL_PACKET_CHARGE if pair else None,
        "center": center,
        "width": width,
        "omega": omega,
        "wave_number": wave_number,
        "phase_sign": phase_sign,
        "relative_phase": relative_phase,
        "orientation": config["orientation"],
        "pair": pair,
        "uncoupled": uncoupled,
        "rule_control": bool(config["rule_control"]),
        "initial_overlap": overlap,
        "initial_core_fraction": initial_core,
        "centers": list(centers),
        "initially_unbound": bool((not pair) or (overlap <= INITIAL_OVERLAP_MAX and initial_core <= INITIAL_CORE_FRACTION_MAX)),
    }
    return q, v, (0.0 if uncoupled else dynamics.HC), metadata


def compare_rows_robust(left: dict[str, Any], right: dict[str, Any], kind: str) -> dict[str, Any]:
    key_left = left["grid"] + "_" + left["arm"]
    key_right = right["grid"] + "_" + right["arm"]
    names = ROBUST_COMPARISON_OBSERVABLES
    result: dict[str, Any] = {"kind": kind, "left": key_left, "right": key_right, "errors": {}, "pass": False, "comparison_observables": list(names)}
    if not left.get("numerically_qualified", False) or not right.get("numerically_qualified", False):
        result["reason"] = "both rows must pass numerical qualification"
        return result
    if len(left.get("times", [])) != len(left.get("trace", [])) or len(right.get("times", [])) != len(right.get("trace", [])):
        result["reason"] = "trace/time coverage mismatch"
        return result
    left_late = [row for index, row in enumerate(left["trace"]) if left["times"][index] >= LATE_START]
    right_late = [row for index, row in enumerate(right["trace"]) if right["times"][index] >= LATE_START]
    if not left_late or not right_late:
        result["reason"] = "late trace missing"
        return result
    if any(not finite_number(row.get(name)) for row in left_late + right_late for name in dynamics.REQUIRED_OBSERVABLES):
        result["reason"] = "nonfinite required observable"
        return result
    initial_values = (left.get("initial", {}).get("energy"), right.get("initial", {}).get("energy"), left.get("initial", {}).get("charge"), right.get("initial", {}).get("charge"))
    if not all(finite_number(value) for value in initial_values):
        result["reason"] = "nonfinite initial comparison scale"
        return result
    left_means = {name: float(np.mean([row[name] for row in left_late])) for name in names}
    right_means = {name: float(np.mean([row[name] for row in right_late])) for name in names}
    scales = {
        "energy": max(1.0, abs(float(left["initial"]["energy"])), abs(float(right["initial"]["energy"]))),
        "charge": max(1.0, abs(float(left["initial"]["charge"])), abs(float(right["initial"]["charge"]))),
        "core_fraction": 1.0,
        "core_rms": dynamics.CORE_RADIUS,
        "core_energy": max(1.0, abs(float(left["initial"]["energy"])), abs(float(right["initial"]["energy"]))),
        "shell_energy_fraction": 1.0,
    }
    errors = {name: abs(left_means[name] - right_means[name]) / scales[name] for name in names}
    result["errors"] = errors
    result["pass"] = bool(all(finite_number(value) for value in errors.values()) and max(errors.values()) < dynamics.COMPARISON_TOL)
    return result


def run_row(output: Path, grid_name: str, grid: CylindricalGrid, dt: float, arm: str) -> dict[str, Any]:
    started = time.perf_counter()
    q, v, coupling, metadata = assemble_primary(grid, arm)
    acc = grid.acceleration(q, coupling)
    initial_energy = float(grid.energy(q, v, coupling))
    initial_rho = -2.0 * dynamics.A * (q[1] * v[2] - q[2] * v[1])
    initial_charge = float((grid.volume * initial_rho).sum())
    metadata["actual_initial_charge"] = initial_charge
    metadata["charge_normalization_relative_error"] = abs(initial_charge - TOTAL_CHARGE) / TOTAL_CHARGE
    if not finite_number(initial_energy) or not finite_number(initial_charge):
        raise RuntimeError(f"nonfinite initial reference for {grid_name}_{arm}")
    times = np.arange(int(round(T_FINAL / SAMPLE_DT)) + 1, dtype=np.float64) * SAMPLE_DT
    trace: list[dict[str, Any]] = [dynamics.diagnostics(grid, q, v, coupling, initial_charge, initial_energy, acc)]
    states: list[dict[str, Any]] = [dynamics.write_state(output / f"{grid_name}_{arm}_t000.npz", grid, q, v, 0.0)]
    sample_step = int(round(SAMPLE_DT / dt))
    steps = int(round(T_FINAL / dt))
    for step in range(1, steps + 1):
        for weight in dynamics.YOSHIDA:
            h = weight * dt
            v.add_(acc, alpha=h / 2.0)
            q.add_(v, alpha=h)
            acc = grid.acceleration(q, coupling)
            v.add_(acc, alpha=h / 2.0)
        if step % sample_step == 0:
            current = step * dt
            trace.append(dynamics.diagnostics(grid, q, v, coupling, initial_charge, initial_energy, acc))
            if any(abs(current - target) < 1.0e-12 for target in SNAPSHOT_TIMES[1:]):
                states.append(dynamics.write_state(output / f"{grid_name}_{arm}_t{int(round(current)):03d}.npz", grid, q, v, current))
    energy_values = [row.get("energy") for row in trace]
    charge_values = [row.get("charge") for row in trace]
    energy_drift = max(abs(float(value) - initial_energy) for value in energy_values) / max(1.0, abs(initial_energy)) if all(finite_number(value) for value in energy_values) else math.inf
    charge_drift = max(abs(float(value) - initial_charge) for value in charge_values) / max(1.0, abs(initial_charge)) if all(finite_number(value) for value in charge_values) else math.inf
    late = [row for index, row in enumerate(trace) if times[index] >= LATE_START]
    core_fraction_values = [row.get("core_fraction") for row in late]
    binding_values = [row.get("binding_ratio") for row in late]
    finite_trace = all(dynamics.finite(row) for row in trace)
    complete_observables = bool(trace and all(finite_number(row.get(name)) for row in trace for name in dynamics.REQUIRED_OBSERVABLES))
    balance_error = max(max(float(row["core_energy_balance_error"]) for row in trace), max(float(row["core_charge_balance_error"]) for row in trace)) if complete_observables else math.inf
    numerically_qualified = bool(
        finite_trace
        and complete_observables
        and energy_drift < dynamics.ENERGY_DRIFT_TOL
        and charge_drift < dynamics.CHARGE_DRIFT_TOL
        and max(float(row["boundary_energy_fraction"]) for row in trace) < dynamics.BOUNDARY_ENERGY_TOL
        and balance_error <= dynamics.LOCAL_BALANCE_TOL
    )
    eligibility = bool(metadata["initially_unbound"] and initial_energy >= dynamics.OMEGA_INF * abs(initial_charge)) if metadata["pair"] else True
    late_variation = math.inf
    if late and abs(initial_charge) > 1.0e-30 and all(finite_number(row.get("core_charge")) for row in late):
        late_variation = (max(float(row["core_charge"]) for row in late) - min(float(row["core_charge"]) for row in late)) / abs(initial_charge)
    late_core_fraction_min = min(float(value) for value in core_fraction_values) if late and all(finite_number(value) for value in core_fraction_values) else math.inf
    binding_gate_evaluated = bool(late and complete_observables and late_core_fraction_min >= RETAINED_FRACTION)
    binding_gate_excluded_near_zero = bool(late and complete_observables and late_core_fraction_min < RETAINED_FRACTION)
    binding_gate_pass = bool(binding_gate_evaluated and max(float(value) for value in binding_values) < BINDING_RATIO_MAX)
    persistent = bool(
        late
        and complete_observables
        and late_core_fraction_min >= RETAINED_FRACTION
        and binding_gate_pass
        and max(float(row["core_rms"]) for row in late) <= dynamics.CORE_RMS_MAX
        and max(float(row["shell_energy_fraction"]) for row in late) <= dynamics.SHELL_ENERGY_FRACTION
        and late_variation <= dynamics.LATE_CORE_VARIATION
    )
    formation = bool(metadata["pair"] and not metadata["uncoupled"] and eligibility and numerically_qualified and persistent)
    row = {
        "grid": grid_name,
        "arm": arm,
        "R": grid.R,
        "spacing": grid.h,
        "dt": dt,
        "coupling": coupling,
        "metadata": metadata,
        "initial": trace[0],
        "times": times.tolist(),
        "trace": trace,
        "states": states,
        "energy_drift": energy_drift,
        "charge_drift": charge_drift,
        "local_balance_max_error": balance_error,
        "late_core_variation": late_variation,
        "late_core_fraction_min": late_core_fraction_min,
        "binding_gate_evaluated": binding_gate_evaluated,
        "binding_gate_excluded_near_zero": binding_gate_excluded_near_zero,
        "binding_gate_pass": binding_gate_pass,
        "numerically_qualified": numerically_qualified,
        "preparation_eligible": eligibility,
        "persistent_remnant": persistent,
        "formation": formation,
        "self_localized": bool((not metadata["pair"]) and numerically_qualified and persistent),
        "complete_physical_matter_formation": False,
        "gravitational_capture_established": False,
        "elapsed_seconds": time.perf_counter() - started,
    }
    write_json(output / f"{grid_name}_{arm}.json", row)
    return row


def run_smoke() -> int:
    grid = CylindricalGrid(32, 1.0)
    records = []
    for arm in ARMS:
        q, v, coupling, metadata = assemble_primary(grid, arm)
        charge = float((grid.volume * (-2.0 * dynamics.A * (q[1] * v[2] - q[2] * v[1]))).sum())
        records.append({"arm": arm, "charge": charge, "center": metadata["center"], "wave_number": metadata["wave_number"], "phase_sign": metadata["phase_sign"], "relative_phase": metadata["relative_phase"], "orientation": metadata["orientation"], "width": metadata["width"], "overlap": metadata["initial_overlap"]})
        assert abs(charge - TOTAL_CHARGE) / TOTAL_CHARGE < 1.0e-12
        assert abs(metadata["width"] - float(ARM_SPECS[arm]["width"])) <= 1.0e-12
        assert abs(metadata["relative_phase"] - float(ARM_SPECS[arm]["relative_phase"])) <= 1.0e-12
        assert metadata["rule_control"] == bool(ARM_SPECS[arm]["rule_control"])
        assert dynamics.finite(metadata)
    print(dynamics.json.dumps({"smoke": "PASS", "arms": records}))
    return 0


def _late_mean(row: dict[str, Any], name: str) -> float:
    late = [value for index, value in enumerate(row["trace"]) if row["times"][index] >= LATE_START]
    return float(np.mean([float(value[name]) for value in late]))


def binding_rule_control(indexed: dict[tuple[str, str], dict[str, Any]], comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    arm = RULE_CONTROL_ARM
    control = indexed[("G0", arm)]
    late_core_min = float(control["late_core_fraction_min"])
    errors: dict[str, float] = {}
    for target in ("G1", "T1"):
        left = _late_mean(indexed[("G0", arm)], "binding_ratio")
        right = _late_mean(indexed[(target, arm)], "binding_ratio")
        errors[f"G0-{target}"] = abs(left - right) / max(1.0, abs(left), abs(right))
    relevant = [item for item in comparisons if arm in {str(item.get("left", "")).split("_", 1)[-1], str(item.get("right", "")).split("_", 1)[-1]}]
    robust_pass = bool(relevant and all(item.get("pass") is True for item in relevant))
    passed = bool(late_core_min < RETAINED_FRACTION and errors and max(errors.values()) > dynamics.COMPARISON_TOL and robust_pass and control.get("binding_gate_excluded_near_zero") is True and control.get("persistent_remnant") is False)
    return {"arm": arm, "late_core_fraction_min": late_core_min, "legacy_binding_errors": errors, "legacy_binding_threshold": dynamics.COMPARISON_TOL, "stable_comparisons_pass": robust_pass, "binding_gate_excluded_near_zero": bool(control.get("binding_gate_excluded_near_zero")), "persistent_remnant": bool(control.get("persistent_remnant")), "pass": passed}


def run_campaign(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True)
    source_hashes = snapshot_sources(output)
    primary = output / "primary"
    primary.mkdir()
    rows: list[dict[str, Any]] = []
    for arm in ARMS:
        radius, spacing, dt = GRID_SPECS["G0"]
        rows.append(run_row(primary, "G0", CylindricalGrid(radius, spacing), dt, arm))
    for grid_name in ("G1", "T1"):
        radius, spacing, dt = GRID_SPECS[grid_name]
        for arm in ARMS:
            rows.append(run_row(primary, grid_name, CylindricalGrid(radius, spacing), dt, arm))
    indexed = {(row["grid"], row["arm"]): row for row in rows}
    comparisons: list[dict[str, Any]] = []
    for arm in ARMS:
        comparisons.append(compare_rows_robust(indexed[("G0", arm)], indexed[("G1", arm)], "space"))
        comparisons.append(compare_rows_robust(indexed[("G0", arm)], indexed[("T1", arm)], "time"))
    rule_control = binding_rule_control(indexed, comparisons)
    coupled_candidates = [indexed[("G0", arm)] for arm in COUPLED_CANDIDATES if indexed[("G0", arm)]["formation"]]
    fully_compared: list[str] = []
    for candidate in coupled_candidates:
        arm = candidate["arm"]
        required = [item for item in comparisons if item["left"] in {f"G0_{arm}", f"G1_{arm}", f"T1_{arm}"} or item["right"] in {f"G0_{arm}", f"G1_{arm}", f"T1_{arm}"}]
        if len(required) == 2 and all(item["pass"] for item in required) and all(indexed[(grid, arm)]["formation"] for grid in ("G0", "G1", "T1")):
            fully_compared.append(f"G0_{arm}")
    uncoupled = indexed[("G0", UNCOUPLED_CONTROL_ARM)]
    uncoupled_failed = bool(uncoupled["numerically_qualified"] and not uncoupled["formation"])
    comparison_pass = bool(len(comparisons) == len(ARMS) * 2 and all(item["pass"] for item in comparisons))
    numerical_pass = bool(comparison_pass and rule_control["pass"])
    if not comparison_pass or not rule_control["pass"]:
        verdict = "INCONCLUSIVE"
    elif fully_compared and uncoupled_failed:
        verdict = "EMERGES—conditional bound remnant in the declared relative-phase basin"
    else:
        verdict = "DOES NOT EMERGE in the specified relative-phase calculation"
    receipt = {
        "schema": SCHEMA,
        "protocol_sha256": sha256(PREREG),
        "source_sha256": source_hashes,
        "constants": {
            "a": dynamics.A,
            "c_psi": dynamics.CPSI,
            "u_rho": dynamics.URHO,
            "u_C": dynamics.UC,
            "k_Cx": dynamics.K,
            "h_C": dynamics.HC,
            "B": dynamics.B,
            "omega_inf": dynamics.OMEGA_INF,
            "v_star": dynamics.VSTAR,
        },
        "preparation": {
            "total_charge": TOTAL_CHARGE,
            "nominal_packet_charge": NOMINAL_PACKET_CHARGE,
            "width": WIDTH,
            "relative_phases": list(RELATIVE_PHASES),
            "arm_specs": ARM_SPECS,
            "center": CENTER,
            "wave_number": WAVE_NUMBER,
            "phase_signs": {"inward": INWARD_PHASE_SIGN, "outward": OUTWARD_PHASE_SIGN},
            "comparison_observables": list(ROBUST_COMPARISON_OBSERVABLES),
            "omega_offset_squared": OMEGA_OFFSET_SQUARED,
            "binding_gate": {"retained_core_fraction": RETAINED_FRACTION, "binding_ratio_max": BINDING_RATIO_MAX, "near_zero_rule": "exclude binding comparison below retained-core threshold; nonpersistent"},
        },
        "rows": rows,
        "comparisons": comparisons,
        "binding_rule_control": rule_control,
        "coupled_candidates": [row["grid"] + "_" + row["arm"] for row in coupled_candidates],
        "fully_compared_candidates": fully_compared,
        "uncoupled_control_failed": uncoupled_failed,
        "numerical_pass": numerical_pass,
        "verdict": verdict,
        "complete_physical_matter_formation": False,
        "gravitational_capture_established": False,
        "physical_size_map_established": False,
        "packet_count_minimum_established": False,
        "library_versions": {"python": platform.python_version(), "torch": torch.__version__},
    }
    write_json(output / "result.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "20260912_matter_formation_packet_phase")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    receipt = run_campaign(args.output.resolve())
    print(dynamics.json.dumps({"output": str(args.output.resolve()), "verdict": receipt["verdict"], "fully_compared_candidates": receipt["fully_compared_candidates"]}))
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
