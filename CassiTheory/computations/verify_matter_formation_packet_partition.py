#!/usr/bin/env python3
"""Independently verify the fixed-charge packet charge-partition basin probe."""
from __future__ import annotations

import argparse
import copy
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"

import verify_matter_formation_wave_capture as independent_dynamics  # noqa: E402
from matter_formation_packet_partition_spec import (
    ARM_SPECS,
    ARMS,
    GRID_SPECS,
    OMEGA_OFFSET_SQUARED,
    SNAPSHOT_TIMES,
    T_FINAL,
    TOTAL_CHARGE,
    ROBUST_COMPARISON_OBSERVABLES,
    RETAINED_FRACTION,
    BINDING_RATIO_MAX,
    RULE_CONTROL_ARM,
    WIDTH,
    ETA_PLUS_VALUES,
    SIGNED_SHARE_TOL,
    MIRROR_SWAP_TOL,
    MIRROR_TRANSFORM,
    MIRROR_TRACE_PARITY,
)

SELF = Path(__file__).resolve()
PREREG = COMPUTATIONS / "matter_formation_packet_partition_prereg.md"
PRIMARY_SOURCE = COMPUTATIONS / "matter_formation_packet_partition.py"
SPEC_SOURCE = COMPUTATIONS / "matter_formation_packet_partition_spec.py"
NEUTRAL_SOURCE = COMPUTATIONS / "matter_formation_neutral_packets.py"
CLOUD_SOURCE = COMPUTATIONS / "matter_formation_radial_cloud.py"
SCHEMA = "matter-formation-packet-charge-partition-verification-v3"
PRIMARY_SCHEMA = "matter-formation-packet-charge-partition-primary-v3"


def sha256(path: Path) -> str:
    return independent_dynamics.sha256(path)


def write_json(path: Path, value: dict[str, Any]) -> None:
    independent_dynamics.write_json(path, value)


def strict_json(path: Path) -> dict[str, Any]:
    return independent_dynamics.strict_json(path)


def assemble_independent(grid: independent_dynamics.IndependentGrid, arm: str) -> tuple[torch.Tensor, torch.Tensor, float, float]:
    """Assemble one independent preparation from the declarative specification."""
    config = ARM_SPECS[arm]
    pair = bool(config["pair"])
    uncoupled = bool(config["uncoupled"])
    center = float(config["center"])
    width = float(config["width"])
    wave_number = float(config["wave_number"])
    phase_sign = float(config["phase_sign"])
    eta_plus = config.get("eta_plus")
    omega = independent_dynamics.OMEGA_INF if not pair else math.sqrt(independent_dynamics.OMEGA_INF**2 + OMEGA_OFFSET_SQUARED * wave_number**2)
    if config["kind"] == "single":
        envelope = torch.exp(-(grid.r2 + grid.axial[None, :].square()) / (2.0 * width**2))
        complex_field = envelope.to(torch.complex128)
    else:
        envelope_negative = torch.exp(-(grid.r2 + (grid.axial[None, :] + center).square()) / (2.0 * width**2))
        envelope_positive = torch.exp(-(grid.r2 + (grid.axial[None, :] - center).square()) / (2.0 * width**2))
        phase_negative = phase_sign * wave_number * (grid.axial[None, :] + center)
        phase_positive = -phase_sign * wave_number * (grid.axial[None, :] - center)
        if eta_plus is None or not 0.0 < float(eta_plus) < 1.0:
            raise independent_dynamics.VerificationError(f"invalid signed charge share for {arm}")
        negative_weight = math.sqrt(1.0 - float(eta_plus))
        positive_weight = math.sqrt(float(eta_plus))
        negative_integral = float((grid.volume * envelope_negative.square()).sum())
        positive_integral = float((grid.volume * envelope_positive.square()).sum())
        complex_field = negative_weight * envelope_negative * torch.exp(1j * phase_negative) + positive_weight * envelope_positive * torch.exp(1j * phase_positive)
    norm = torch.sum(grid.volume * (complex_field.real.square() + complex_field.imag.square()))
    norm_value = float(norm)
    if not math.isfinite(norm_value) or norm_value <= 0.0:
        raise independent_dynamics.VerificationError(f"invalid independent normalization for {arm}")
    scale_squared = TOTAL_CHARGE / (2.0 * independent_dynamics.A * omega * norm_value)
    complex_field = complex_field * math.sqrt(scale_squared)
    if pair:
        isolated_packet_charges = [
            2.0 * independent_dynamics.A * omega * negative_weight**2 * negative_integral * scale_squared,
            2.0 * independent_dynamics.A * omega * positive_weight**2 * positive_integral * scale_squared,
        ]
        isolated_total = sum(isolated_packet_charges)
        isolated_packet_fractions = [value / isolated_total for value in isolated_packet_charges]
        if (
            abs(isolated_packet_fractions[0] - (1.0 - float(eta_plus))) > SIGNED_SHARE_TOL
            or abs(isolated_packet_fractions[1] - float(eta_plus)) > SIGNED_SHARE_TOL
        ):
            raise independent_dynamics.VerificationError(f"independent isolated signed charge share mismatch for {arm}")
    q = torch.zeros((3, grid.nr, grid.nz), dtype=torch.float64, device="cuda")
    q[1], q[2] = complex_field.real, complex_field.imag
    v = torch.zeros_like(q)
    v[1], v[2] = omega * q[2], -omega * q[1]
    return q, v, (0.0 if uncoupled else independent_dynamics.HC), TOTAL_CHARGE


def write_independent_state(
    archive_dir: Path,
    arm: str,
    grid: independent_dynamics.IndependentGrid,
    q: torch.Tensor,
    v: torch.Tensor,
    time_value: float,
) -> dict[str, str | float]:
    path = archive_dir / f"{arm}_t{int(round(time_value)):03d}.npz"
    with path.open("xb") as stream:
        np.savez_compressed(
            stream,
            fields=q.detach().cpu().numpy(),
            velocities=v.detach().cpu().numpy(),
            r=grid.r.detach().cpu().numpy(),
            axial=grid.axial.detach().cpu().numpy(),
            volume=grid.volume.detach().cpu().numpy(),
            time=np.asarray(time_value),
        )
    return {"path": path.name, "sha256": sha256(path), "time": float(time_value)}


def independent_evolution(arm: str, radius: int, spacing: float, dt: float, archive_dir: Path) -> dict[str, Any]:
    grid = independent_dynamics.IndependentGrid(radius, spacing)
    q, v, coupling, declared_charge = assemble_independent(grid, arm)
    initial_rho = -2.0 * independent_dynamics.A * (q[1] * v[2] - q[2] * v[1])
    charge_reference = float((grid.volume * initial_rho).sum())
    energy_reference = float(grid.energy(q, v, coupling))
    if not independent_dynamics.finite_number(charge_reference) or not independent_dynamics.finite_number(energy_reference):
        raise independent_dynamics.VerificationError(f"nonfinite independent initial reference for {arm}")
    charge_error = abs(charge_reference - declared_charge) / declared_charge
    if charge_error > 1.0e-12:
        raise independent_dynamics.VerificationError(f"independent charge normalization mismatch for {arm}: {charge_error}")
    results: dict[float, dict[str, Any]] = {0.0: independent_dynamics.metric(grid, q, v, coupling, charge_reference, energy_reference)}
    states = [write_independent_state(archive_dir, arm, grid, q, v, 0.0)]
    targets = {int(round(t / dt)): t for t in SNAPSHOT_TIMES[1:]}
    for step in range(1, int(round(T_FINAL / dt)) + 1):
        q, v = independent_dynamics.rk4_step(grid, q, v, dt, coupling)
        if step in targets:
            t = targets[step]
            results[t] = independent_dynamics.metric(grid, q, v, coupling, charge_reference, energy_reference)
            states.append(write_independent_state(archive_dir, arm, grid, q, v, t))
    if len(results) != len(SNAPSHOT_TIMES) or len(states) != len(SNAPSHOT_TIMES):
        raise independent_dynamics.VerificationError(f"independent evolution missed snapshot for {arm}")
    finite_snapshots = bool(results) and all(
        independent_dynamics.finite_number(values.get(name)) for values in results.values() for name in independent_dynamics.REQUIRED_OBSERVABLES
    )
    if finite_snapshots:
        energy_drift = max(abs(float(values["energy"]) - energy_reference) for values in results.values()) / max(1.0, abs(energy_reference))
        charge_drift = max(abs(float(values["charge"]) - charge_reference) for values in results.values()) / max(1.0, abs(charge_reference))
    else:
        energy_drift = math.inf
        charge_drift = math.inf
    return {
        "arm": arm,
        "grid": radius,
        "spacing": spacing,
        "dt": dt,
        "charge_reference": charge_reference,
        "energy_reference": energy_reference,
        "snapshots": {str(t): values for t, values in results.items()},
        "states": states,
        "energy_drift": energy_drift,
        "charge_drift": charge_drift,
        "finite_snapshots": finite_snapshots,
        "conservation_pass": bool(
            finite_snapshots
            and energy_drift <= independent_dynamics.ENERGY_DRIFT_TOL
            and charge_drift <= independent_dynamics.CHARGE_DRIFT_TOL
        ),
        "raw_state_archive_complete": False,
        "charge_normalization_relative_error": charge_error,
        "source": "fresh independent RK4 integration",
    }


def source_checks(input_dir: Path, receipt: dict[str, Any]) -> dict[str, bool]:
    required = (PREREG, PRIMARY_SOURCE, SPEC_SOURCE, NEUTRAL_SOURCE, CLOUD_SOURCE, SELF)
    recorded = receipt.get("source_sha256", {})
    checks: dict[str, bool] = {"protocol_live": receipt.get("protocol_sha256") == sha256(PREREG)}
    for path in required:
        key = path.relative_to(ROOT).as_posix()
        archived = input_dir / "sources" / key.replace("/", "__")
        expected = recorded.get(key)
        present = archived.is_file()
        archive_hash = sha256(archived) if present else ""
        checks[key] = bool(present and isinstance(expected, str) and archive_hash == expected)
        checks[f"live_{key}"] = bool(checks[key] and sha256(path) == archive_hash)
    checks["archive_bytes"] = bool(all(checks[key] for key in checks if key != "protocol_live" and not key.startswith("live_")))
    checks["live_source_bytes"] = bool(all(checks[key] for key in checks if key.startswith("live_")))
    return checks


def mutation_control(input_dir: Path, row: dict[str, Any]) -> bool:
    state = row["states"][0]
    grid, original_q, velocity_tensor = independent_dynamics._validate_state_archive(input_dir, row, state)
    original_fields = original_q.detach().cpu().numpy()
    before_energy = float(grid.energy(original_q, velocity_tensor, float(row["coupling"])))
    mutated_fields = np.array(original_fields, copy=True)
    mutated_fields[0, 0, 0] += 0.1
    mutated_q = torch.as_tensor(mutated_fields, dtype=torch.float64, device="cuda")
    after_energy = float(grid.energy(mutated_q, velocity_tensor, float(row["coupling"])))
    return bool(not np.array_equal(mutated_fields, original_fields) and abs(after_energy - before_energy) > 1.0e-8 and abs(after_energy - float(row["trace"][0]["energy"])) > 1.0e-8)


def corrupted_hash_control(input_dir: Path, receipt: dict[str, Any]) -> bool:
    mutated = copy.deepcopy(receipt)
    row = next(iter(mutated["rows"]))
    row["states"][0]["sha256"] = "0" * 64
    details = independent_dynamics.verify_primary_rows(input_dir, mutated)
    return bool(not details["pass"] and any("hash mismatch" in failure for item in details["details"] for failure in item["failures"]))


def preparation_contract(receipt: dict[str, Any]) -> dict[str, Any]:
    rows = receipt.get("rows", [])
    expected = {(grid, arm) for grid in GRID_SPECS for arm in ARMS}
    observed = {(row.get("grid"), row.get("arm")) for row in rows if isinstance(row, dict)}
    preparation = receipt.get("preparation", {}) if isinstance(receipt.get("preparation", {}), dict) else {}
    top_eta_values = preparation.get("eta_plus_values")
    top_tolerance = preparation.get("signed_share_tolerance")
    top_mirror_tolerance = preparation.get("mirror_swap_tolerance")
    top_mirror_transform = preparation.get("mirror_transform")
    top_trace_parity = preparation.get("mirror_trace_parity")
    top_arm_specs = preparation.get("arm_specs")
    checks = {
        "row_key_set": observed == expected,
        "row_count": len(rows) == len(expected),
        "top_level_schedule": bool(
            preparation.get("total_charge") == TOTAL_CHARGE
            and isinstance(top_eta_values, list)
            and top_eta_values == list(ETA_PLUS_VALUES)
            and isinstance(top_arm_specs, dict)
            and set(top_arm_specs) == set(ARM_SPECS)
            and isinstance(top_tolerance, (int, float))
            and abs(float(top_tolerance) - SIGNED_SHARE_TOL) <= SIGNED_SHARE_TOL
            and isinstance(top_mirror_tolerance, (int, float))
            and abs(float(top_mirror_tolerance) - MIRROR_SWAP_TOL) <= SIGNED_SHARE_TOL
            and top_mirror_transform == MIRROR_TRANSFORM
            and top_trace_parity == MIRROR_TRACE_PARITY
        ),
        "total_charge": True,
        "nominal_packet_charge": True,
        "partition_metadata": True,
        "arm_metadata": True,
        "center_metadata": True,
        "width_metadata": True,
        "wave_metadata": True,
        "phase_metadata": True,
        "relative_phase_metadata": True,
        "orientation_metadata": True,
        "rule_control_metadata": True,
    }
    for row in rows:
        metadata = row.get("metadata", {}) if isinstance(row, dict) else {}
        checks["total_charge"] = checks["total_charge"] and abs(float(metadata.get("charge", math.nan)) - TOTAL_CHARGE) <= SIGNED_SHARE_TOL
        expected_nominal = TOTAL_CHARGE / 2.0 if bool(metadata.get("pair")) else None
        observed_nominal = metadata.get("nominal_packet_charge")
        checks["nominal_packet_charge"] = checks["nominal_packet_charge"] and ((expected_nominal is None and observed_nominal is None) or (observed_nominal is not None and abs(float(observed_nominal) - expected_nominal) <= SIGNED_SHARE_TOL))
        arm = row.get("arm")
        spec = ARM_SPECS.get(arm, {})
        checks["arm_metadata"] = checks["arm_metadata"] and arm in ARM_SPECS and bool(metadata.get("pair")) == bool(spec.get("pair"))
        checks["center_metadata"] = checks["center_metadata"] and arm in ARM_SPECS and abs(float(metadata.get("center", math.nan)) - float(spec.get("center", math.nan))) <= SIGNED_SHARE_TOL
        checks["width_metadata"] = checks["width_metadata"] and arm in ARM_SPECS and abs(float(metadata.get("width", math.nan)) - float(spec.get("width", math.nan))) <= SIGNED_SHARE_TOL
        checks["relative_phase_metadata"] = checks["relative_phase_metadata"] and arm in ARM_SPECS and abs(float(metadata.get("relative_phase", math.nan)) - float(spec.get("relative_phase", math.nan))) <= SIGNED_SHARE_TOL
        expected_eta = spec.get("eta_plus") if arm in ARM_SPECS else None
        observed_eta = metadata.get("eta_plus")
        observed_eta_minus = metadata.get("eta_minus")
        isolated_contributions = metadata.get("isolated_packet_charge_contributions")
        isolated_fractions = metadata.get("isolated_packet_charge_fractions")
        if expected_eta is None:
            partition_ok = observed_eta is None and observed_eta_minus is None and isolated_contributions is None and isolated_fractions is None
        else:
            try:
                contribution_sum = sum(float(value) for value in isolated_contributions)
                reconstructed_fractions = [float(value) / contribution_sum for value in isolated_contributions]
                partition_ok = bool(
                    len(isolated_contributions) == 2
                    and len(isolated_fractions) == 2
                    and all(math.isfinite(float(value)) and float(value) > 0.0 for value in isolated_contributions)
                    and all(math.isfinite(float(value)) and float(value) > 0.0 for value in isolated_fractions)
                    and abs(float(observed_eta) - float(expected_eta)) <= SIGNED_SHARE_TOL
                    and abs(float(observed_eta_minus) - (1.0 - float(expected_eta))) <= SIGNED_SHARE_TOL
                    and abs(float(isolated_fractions[0]) - (1.0 - float(expected_eta))) <= SIGNED_SHARE_TOL
                    and abs(float(isolated_fractions[1]) - float(expected_eta)) <= SIGNED_SHARE_TOL
                    and all(abs(reconstructed_fractions[index] - float(isolated_fractions[index])) <= SIGNED_SHARE_TOL for index in range(2))
                )
            except (TypeError, ValueError, IndexError, ZeroDivisionError):
                partition_ok = False
        checks["partition_metadata"] = checks["partition_metadata"] and partition_ok
        checks["wave_metadata"] = checks["wave_metadata"] and arm in ARM_SPECS and abs(float(metadata.get("wave_number", math.nan)) - float(spec.get("wave_number", math.nan))) <= SIGNED_SHARE_TOL
        checks["phase_metadata"] = checks["phase_metadata"] and arm in ARM_SPECS and abs(float(metadata.get("phase_sign", math.nan)) - float(spec.get("phase_sign", math.nan))) <= SIGNED_SHARE_TOL
        checks["orientation_metadata"] = checks["orientation_metadata"] and arm in ARM_SPECS and metadata.get("orientation") == spec.get("orientation")
        checks["rule_control_metadata"] = checks["rule_control_metadata"] and arm in ARM_SPECS and bool(metadata.get("rule_control")) == bool(spec.get("rule_control"))
    checks["pass"] = all(checks.values())
    return checks


def mirrored_swap_control(input_dir: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    rows = {(row.get("grid"), row.get("arm")): row for row in receipt.get("rows", []) if isinstance(row, dict)}
    grid_checks: dict[str, Any] = {}

    def charge_of(grid: Any, q: torch.Tensor, v: torch.Tensor) -> float:
        rho = -2.0 * independent_dynamics.A * (q[1] * v[2] - q[2] * v[1])
        return float((grid.volume * rho).sum())

    def normalized_tensor_error(left: torch.Tensor, right: torch.Tensor) -> tuple[float, float]:
        absolute = float(torch.max(torch.abs(left - right)).item())
        scale = max(1.0, float(torch.max(torch.abs(left)).item()), float(torch.max(torch.abs(right)).item()))
        return absolute / scale, absolute

    def normalized_scalar_error(left: float, right: float) -> float:
        return abs(float(left) - float(right)) / max(1.0, abs(float(left)), abs(float(right)))

    for grid_name in GRID_SPECS:
        lower = rows.get((grid_name, "pair_split25"))
        upper = rows.get((grid_name, "pair_split75"))
        if not isinstance(lower, dict) or not isinstance(upper, dict):
            grid_checks[grid_name] = {"pass": False, "reason": "complementary partition rows missing"}
            continue
        try:
            lower_metadata = lower["metadata"]
            upper_metadata = upper["metadata"]
            lower_fraction = lower_metadata["isolated_packet_charge_fractions"]
            upper_fraction = upper_metadata["isolated_packet_charge_fractions"]
            eta_swap = abs(float(lower_metadata["eta_plus"]) + float(upper_metadata["eta_plus"]) - 1.0) <= SIGNED_SHARE_TOL
            fraction_swap = bool(
                len(lower_fraction) == 2
                and len(upper_fraction) == 2
                and abs(float(lower_fraction[0]) - float(upper_fraction[1])) <= SIGNED_SHARE_TOL
                and abs(float(lower_fraction[1]) - float(upper_fraction[0])) <= SIGNED_SHARE_TOL
            )
            phase_metadata_pass = bool(
                abs(float(lower_metadata["wave_number"]) - float(upper_metadata["wave_number"])) <= SIGNED_SHARE_TOL
                and abs(float(lower_metadata["phase_sign"]) - float(upper_metadata["phase_sign"])) <= SIGNED_SHARE_TOL
                and abs(float(lower_metadata["relative_phase"]) - float(upper_metadata["relative_phase"])) <= SIGNED_SHARE_TOL
            )
            lower_states = lower["states"]
            upper_states = upper["states"]
            state_checks: list[dict[str, Any]] = []
            if len(lower_states) != len(upper_states):
                raise independent_dynamics.VerificationError("complementary state counts differ")
            for lower_state, upper_state in zip(lower_states, upper_states):
                lower_grid, lower_q, lower_v = independent_dynamics._validate_state_archive(input_dir, lower, lower_state)
                _upper_grid, upper_q, upper_v = independent_dynamics._validate_state_archive(input_dir, upper, upper_state)
                lower_time = float(lower_state["time"])
                upper_time = float(upper_state["time"])
                reflected_q = torch.flip(upper_q, dims=[2])
                reflected_v = torch.flip(upper_v, dims=[2])
                field_error, field_absolute = normalized_tensor_error(lower_q, reflected_q)
                velocity_error, velocity_absolute = normalized_tensor_error(lower_v, reflected_v)
                lower_charge = charge_of(lower_grid, lower_q, lower_v)
                reflected_upper_charge = charge_of(lower_grid, reflected_q, reflected_v)
                lower_energy = float(lower_grid.energy(lower_q, lower_v, float(lower["coupling"])))
                reflected_upper_energy = float(lower_grid.energy(reflected_q, reflected_v, float(upper["coupling"])))
                charge_error = normalized_scalar_error(lower_charge, reflected_upper_charge)
                energy_error = normalized_scalar_error(lower_energy, reflected_upper_energy)
                state_checks.append(
                    {
                        "time": lower_time,
                        "time_match": abs(lower_time - upper_time) <= SIGNED_SHARE_TOL,
                        "field_reflection_normalized_error": field_error,
                        "field_reflection_absolute_error": field_absolute,
                        "velocity_reflection_normalized_error": velocity_error,
                        "velocity_reflection_absolute_error": velocity_absolute,
                        "lower_charge": lower_charge,
                        "reflected_upper_charge": reflected_upper_charge,
                        "charge_error": charge_error,
                        "lower_energy": lower_energy,
                        "reflected_upper_energy": reflected_upper_energy,
                        "energy_error": energy_error,
                        "pass": bool(
                            abs(lower_time - upper_time) <= SIGNED_SHARE_TOL
                            and field_error <= MIRROR_SWAP_TOL
                            and velocity_error <= MIRROR_SWAP_TOL
                            and charge_error <= MIRROR_SWAP_TOL
                            and energy_error <= MIRROR_SWAP_TOL
                        ),
                    }
                )
            trace_errors = {name: 0.0 for name in independent_dynamics.REQUIRED_OBSERVABLES}
            trace_times_pass = len(lower["times"]) == len(upper["times"]) == len(lower["trace"]) == len(upper["trace"])
            if trace_times_pass:
                for lower_time, upper_time in zip(lower["times"], upper["times"]):
                    trace_times_pass = trace_times_pass and abs(float(lower_time) - float(upper_time)) <= SIGNED_SHARE_TOL
            if trace_times_pass:
                for lower_trace, upper_trace in zip(lower["trace"], upper["trace"]):
                    for name in independent_dynamics.REQUIRED_OBSERVABLES:
                        left = lower_trace.get(name)
                        right = upper_trace.get(name)
                        if left is None or right is None:
                            error = 0.0 if left is None and right is None else math.inf
                        else:
                            error = normalized_scalar_error(float(left), float(MIRROR_TRACE_PARITY.get(name, 1.0)) * float(right))
                        trace_errors[name] = max(trace_errors[name], error)
            max_trace_error = max(trace_errors.values(), default=math.inf)
            state_pass = bool(state_checks and all(item["pass"] for item in state_checks))
            trace_pass = bool(trace_times_pass and max_trace_error <= MIRROR_SWAP_TOL)
            max_field_error = max((item["field_reflection_normalized_error"] for item in state_checks), default=math.inf)
            max_velocity_error = max((item["velocity_reflection_normalized_error"] for item in state_checks), default=math.inf)
            max_charge_error = max((item["charge_error"] for item in state_checks), default=math.inf)
            max_energy_error = max((item["energy_error"] for item in state_checks), default=math.inf)
            grid_checks[grid_name] = {
                "lower_arm": "pair_split25",
                "upper_arm": "pair_split75",
                "transform": MIRROR_TRANSFORM,
                "trace_parity": MIRROR_TRACE_PARITY,
                "eta_swap_pass": eta_swap,
                "fraction_swap_pass": fraction_swap,
                "phase_metadata_pass": phase_metadata_pass,
                "state_checks": state_checks,
                "field_reflection_max_normalized_error": max_field_error,
                "velocity_reflection_max_normalized_error": max_velocity_error,
                "charge_max_normalized_error": max_charge_error,
                "energy_max_normalized_error": max_energy_error,
                "trace_max_normalized_error": max_trace_error,
                "trace_errors": trace_errors,
                "trace_times_pass": trace_times_pass,
                "field_reflection_pass": max_field_error <= MIRROR_SWAP_TOL,
                "velocity_reflection_pass": max_velocity_error <= MIRROR_SWAP_TOL,
                "charge_pass": max_charge_error <= MIRROR_SWAP_TOL,
                "energy_pass": max_energy_error <= MIRROR_SWAP_TOL,
                "trace_pass": trace_pass,
                "pass": bool(
                    eta_swap
                    and fraction_swap
                    and phase_metadata_pass
                    and state_pass
                    and trace_pass
                ),
            }
        except (KeyError, IndexError, TypeError, ValueError, RuntimeError):
            grid_checks[grid_name] = {"pass": False, "reason": "complementary transformed-state check failed"}
    return {
        "lower_arm": "pair_split25",
        "upper_arm": "pair_split75",
        "transform": MIRROR_TRANSFORM,
        "trace_parity": MIRROR_TRACE_PARITY,
        "grids": grid_checks,
        "pass": bool(grid_checks and all(item.get("pass") is True for item in grid_checks.values())),
    }


def independent_preparation_checks() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    charges: dict[str, float] = {}
    for grid_name, (radius, spacing, _dt) in GRID_SPECS.items():
        grid = independent_dynamics.IndependentGrid(radius, spacing)
        for arm in ARMS:
            q, v, _coupling, declared_charge = assemble_independent(grid, arm)
            charge = float((grid.volume * (-2.0 * independent_dynamics.A * (q[1] * v[2] - q[2] * v[1]))).sum())
            key = f"{grid_name}_{arm}"
            charges[key] = charge
            checks[key] = bool(independent_dynamics.finite_number(charge) and abs(charge - declared_charge) / TOTAL_CHARGE <= SIGNED_SHARE_TOL)
    return {"checks": checks, "charges": charges, "pass": bool(checks and all(checks.values()))}


def method_comparison_robust(primary_row: dict[str, Any] | None, independent: dict[str, Any]) -> dict[str, Any]:
    arm = independent.get("arm")
    result: dict[str, Any] = {"arm": arm, "errors": {}, "failures": [], "pass": False, "comparison_observables": list(ROBUST_COMPARISON_OBSERVABLES)}
    if primary_row is None:
        result["failures"].append("primary T1 row missing")
        return result
    snapshots = independent.get("snapshots", {})
    for time_value in independent_dynamics.SAMPLE_TIMES:
        values = snapshots.get(str(time_value), snapshots.get(time_value)) if isinstance(snapshots, dict) else None
        index = int(round(time_value / 0.5))
        trace = primary_row.get("trace", [])
        if not isinstance(values, dict) or not isinstance(trace, list) or index < 0 or index >= len(trace):
            result["failures"].append(f"missing snapshot {time_value}")
            continue
        observed = trace[index] if isinstance(trace[index], dict) else {}
        if any(
            not independent_dynamics.finite_number(observed.get(name)) or not independent_dynamics.finite_number(values.get(name))
            for name in independent_dynamics.REQUIRED_OBSERVABLES
        ):
            result["failures"].append(f"{time_value}:required observable missing or invalid")
            continue
        for name in ROBUST_COMPARISON_OBSERVABLES:
            observed_float = float(observed[name])
            rebuilt_float = float(values[name])
            result["errors"][f"{time_value}:{name}"] = abs(observed_float - rebuilt_float) / max(1.0, abs(observed_float), abs(rebuilt_float))
    result["pass"] = bool(result["errors"]) and not result["failures"] and max(result["errors"].values()) < independent_dynamics.METHOD_TOL
    return result


def independent_binding_rule_control(receipt: dict[str, Any], primary_comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    rows = {(row.get("grid"), row.get("arm")): row for row in receipt.get("rows", []) if isinstance(row, dict)}
    arm = RULE_CONTROL_ARM
    control = rows.get(("G0", arm))
    if not isinstance(control, dict):
        return {"arm": arm, "pass": False, "reason": "rule-control G0 row missing"}
    def late_values(row: dict[str, Any], name: str) -> list[float]:
        return [float(item[name]) for index, item in enumerate(row.get("trace", [])) if float(row.get("times", [])[index]) >= 32.0]
    try:
        core_values = late_values(control, "core_fraction")
        core_min = min(core_values)
        errors: dict[str, float] = {}
        for target in ("G1", "T1"):
            left = float(np.mean(late_values(rows[("G0", arm)], "binding_ratio")))
            right = float(np.mean(late_values(rows[(target, arm)], "binding_ratio")))
            errors[f"G0-{target}"] = abs(left - right) / max(1.0, abs(left), abs(right))
    except (KeyError, IndexError, TypeError, ValueError):
        return {"arm": arm, "pass": False, "reason": "rule-control observables missing"}
    relevant = [item for item in primary_comparisons if arm in {str(item.get("left", "")).split("_", 1)[-1], str(item.get("right", "")).split("_", 1)[-1]}]
    stable_pass = bool(relevant and all(item.get("pass") is True for item in relevant))
    gate_excluded = bool(core_min < RETAINED_FRACTION)
    passed = bool(gate_excluded and errors and max(errors.values()) > independent_dynamics.METHOD_TOL and stable_pass and control.get("binding_gate_excluded_near_zero") is True and control.get("persistent_remnant") is False)
    return {"arm": arm, "late_core_fraction_min": core_min, "retained_core_fraction": RETAINED_FRACTION, "binding_ratio_max": BINDING_RATIO_MAX, "legacy_binding_errors": errors, "legacy_binding_threshold": independent_dynamics.METHOD_TOL, "stable_comparisons_pass": stable_pass, "binding_gate_excluded_near_zero": gate_excluded, "primary_gate_excluded_near_zero": bool(control.get("binding_gate_excluded_near_zero")), "persistent_remnant": bool(control.get("persistent_remnant")), "pass": passed}


def run(input_dir: Path, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise independent_dynamics.VerificationError(f"refusing to overwrite existing verifier output: {output_path}")
    receipt = strict_json(input_dir / "result.json")
    if receipt.get("schema") != PRIMARY_SCHEMA:
        raise independent_dynamics.VerificationError("primary schema mismatch")
    source_identity = source_checks(input_dir, receipt)
    contract = preparation_contract(receipt)
    snapshot_details = independent_dynamics.verify_primary_rows(input_dir, receipt)
    mirrored_swap = mirrored_swap_control(input_dir, receipt)
    independent_preparation = independent_preparation_checks()
    mutation = mutation_control(input_dir, receipt["rows"][0])
    corrupted_hash_rejected = corrupted_hash_control(input_dir, receipt)
    radius, spacing, dt = GRID_SPECS["T1"]
    archive_dir = output_path.parent / f"{output_path.stem}_independent_states"
    if archive_dir.exists():
        raise independent_dynamics.VerificationError(f"refusing to overwrite independent archive: {archive_dir}")
    archive_dir.mkdir(parents=True, exist_ok=False)
    independent = [independent_evolution(arm, radius, spacing, dt, archive_dir) for arm in ARMS]
    independent_complete, archive_validation = independent_dynamics._validate_independent_archive(archive_dir, independent)
    rows_by_arm = {row.get("arm"): row for row in receipt.get("rows", []) if row.get("grid") == "T1"}
    method_comparisons = [method_comparison_robust(rows_by_arm.get(item.get("arm")), item) for item in independent]
    conservation_checks = [{"arm": item.get("arm"), "energy_drift": item.get("energy_drift"), "charge_drift": item.get("charge_drift"), "pass": bool(item.get("conservation_pass", False)), "raw_state_archive_complete": bool(item.get("raw_state_archive_complete", False))} for item in independent]
    primary_comparisons = receipt.get("comparisons", [])
    rule_control = independent_binding_rule_control(receipt, primary_comparisons)
    primary_comparison_pass = bool(receipt.get("numerical_pass") is True and isinstance(primary_comparisons, list) and len(primary_comparisons) == len(ARMS) * 2 and all(isinstance(item, dict) and item.get("pass") is True for item in primary_comparisons))
    result = {
        "schema": SCHEMA,
        "primary": str(input_dir),
        "primary_schema": receipt.get("schema"),
        "source_checks": source_identity,
        "preparation_contract": contract,
        "snapshot_details": snapshot_details,
        "rejection_control_mutated_state_rejected": mutation,
        "rejection_control_corrupted_hash_rejected": corrupted_hash_rejected,
        "independent_evolution": independent,
        "independent_archive_validation": archive_validation,
        "conservation_checks": conservation_checks,
        "method_comparisons": method_comparisons,
        "primary_comparison_pass": primary_comparison_pass,
        "mirrored_partition_swap": mirrored_swap,
        "independent_preparation_checks": independent_preparation,
        "binding_rule_control": rule_control,
        "independent_raw_archive_complete": independent_complete,
        "scalar_snapshot_comparison_pass": bool(method_comparisons and all(item["pass"] for item in method_comparisons)),
        "independent_conservation_pass": bool(conservation_checks and all(item["pass"] for item in conservation_checks)),
        "complete_physical_matter_formation": False,
        "gravitational_capture_established": False,
        "physical_size_map_established": False,
        "packet_count_minimum_established": False,
    }
    result["numeric_pass"] = bool(all(source_identity.values()) and contract["pass"] and snapshot_details["pass"] and mirrored_swap["pass"] and independent_preparation["pass"] and primary_comparison_pass and rule_control["pass"] and mutation and corrupted_hash_rejected and result["scalar_snapshot_comparison_pass"] and result["independent_conservation_pass"] and independent_complete)
    write_json(output_path, result)
    return result


def run_smoke() -> int:
    grid = independent_dynamics.IndependentGrid(16, 1.0)
    records = []
    for arm in ARMS:
        config = ARM_SPECS[arm]
        assert math.isfinite(float(config["width"]))
        assert math.isfinite(float(config["relative_phase"]))
        assert bool(config["rule_control"]) == (arm == RULE_CONTROL_ARM)
        expected_eta = config.get("eta_plus")
        assert expected_eta is None or float(expected_eta) in ETA_PLUS_VALUES
        q, v, coupling, charge = assemble_independent(grid, arm)
        observed = float((grid.volume * (-2.0 * independent_dynamics.A * (q[1] * v[2] - q[2] * v[1]))).sum())
        assert abs(observed - charge) / charge <= SIGNED_SHARE_TOL
        records.append({"arm": arm, "charge": observed, "center": config["center"], "wave_number": config["wave_number"], "phase_sign": config["phase_sign"], "relative_phase": config["relative_phase"], "eta_plus": expected_eta, "eta_minus": None if expected_eta is None else 1.0 - float(expected_eta), "orientation": config["orientation"], "coupling": coupling})
    print(independent_dynamics.json.dumps({"smoke": "PASS", "arms": records}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "runs" / "20260912_matter_formation_packet_partition_field_reflection")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    input_dir = args.input.resolve()
    output = (args.output or (input_dir / "verification.json")).resolve()
    result = run(input_dir, output)
    print(independent_dynamics.json.dumps({"output": str(output), "numeric_pass": result["numeric_pass"], "snapshot_pass": result["snapshot_details"]["pass"], "conservation_pass": result["independent_conservation_pass"], "mirror_swap_pass": result["mirrored_partition_swap"]["pass"], "independent_preparation_pass": result["independent_preparation_checks"]["pass"]}))
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
