#!/usr/bin/env python3
"""Independently verify the fixed-charge incoming-momentum basin probe."""
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
from matter_formation_momentum_basin_spec import (  # noqa: E402
    ARM_SPECS,
    ARMS,
    GRID_SPECS,
    NOMINAL_PACKET_CHARGE,
    OMEGA_OFFSET_SQUARED,
    SNAPSHOT_TIMES,
    T_FINAL,
    TOTAL_CHARGE,
    WIDTH,
)

SELF = Path(__file__).resolve()
PREREG = COMPUTATIONS / "matter_formation_momentum_basin_prereg.md"
PRIMARY_SOURCE = COMPUTATIONS / "matter_formation_momentum_basin.py"
SPEC_SOURCE = COMPUTATIONS / "matter_formation_momentum_basin_spec.py"
NEUTRAL_SOURCE = COMPUTATIONS / "matter_formation_neutral_packets.py"
CLOUD_SOURCE = COMPUTATIONS / "matter_formation_radial_cloud.py"
SCHEMA = "matter-formation-packet-momentum-verification-v1"
PRIMARY_SCHEMA = "matter-formation-packet-momentum-primary-v1"


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
    wave_number = float(config["wave_number"])
    omega = independent_dynamics.OMEGA_INF if not pair else math.sqrt(independent_dynamics.OMEGA_INF**2 + OMEGA_OFFSET_SQUARED * wave_number**2)
    if config["kind"] == "single":
        envelope = torch.exp(-(grid.r2 + grid.axial[None, :].square()) / (2.0 * WIDTH**2))
        complex_field = envelope.to(torch.complex128)
    else:
        right = torch.exp(-(grid.r2 + (grid.axial[None, :] + center).square()) / (2.0 * WIDTH**2))
        left = torch.exp(-(grid.r2 + (grid.axial[None, :] - center).square()) / (2.0 * WIDTH**2))
        phase_right = wave_number * (grid.axial[None, :] + center)
        phase_left = -wave_number * (grid.axial[None, :] - center)
        sign_left = -1.0 if config["kind"] == "antiphase" else 1.0
        complex_field = right * torch.exp(1j * phase_right) + sign_left * left * torch.exp(1j * phase_left)
    norm = torch.sum(grid.volume * (complex_field.real.square() + complex_field.imag.square()))
    norm_value = float(norm)
    if not math.isfinite(norm_value) or norm_value <= 0.0:
        raise independent_dynamics.VerificationError(f"invalid independent normalization for {arm}")
    complex_field = complex_field * math.sqrt(TOTAL_CHARGE / (2.0 * independent_dynamics.A * omega * norm_value))
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
    checks = {"row_key_set": observed == expected, "row_count": len(rows) == len(expected), "total_charge": True, "nominal_packet_charge": True, "arm_metadata": True, "center_metadata": True, "wave_metadata": True}
    for row in rows:
        metadata = row.get("metadata", {}) if isinstance(row, dict) else {}
        checks["total_charge"] = checks["total_charge"] and abs(float(metadata.get("charge", math.nan)) - TOTAL_CHARGE) <= 1.0e-12
        expected_nominal = NOMINAL_PACKET_CHARGE if bool(metadata.get("pair")) else None
        observed_nominal = metadata.get("nominal_packet_charge")
        checks["nominal_packet_charge"] = checks["nominal_packet_charge"] and ((expected_nominal is None and observed_nominal is None) or (observed_nominal is not None and abs(float(observed_nominal) - expected_nominal) <= 1.0e-12))
        arm = row.get("arm")
        checks["arm_metadata"] = checks["arm_metadata"] and arm in ARM_SPECS and bool(metadata.get("pair")) == bool(ARM_SPECS[arm]["pair"])
        checks["center_metadata"] = checks["center_metadata"] and arm in ARM_SPECS and abs(float(metadata.get("center", math.nan)) - float(ARM_SPECS[arm]["center"])) <= 1.0e-12
        checks["wave_metadata"] = checks["wave_metadata"] and arm in ARM_SPECS and abs(float(metadata.get("wave_number", math.nan)) - float(ARM_SPECS[arm]["wave_number"])) <= 1.0e-12
    checks["pass"] = all(checks.values())
    return checks


def run(input_dir: Path, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise independent_dynamics.VerificationError(f"refusing to overwrite existing verifier output: {output_path}")
    receipt = strict_json(input_dir / "result.json")
    if receipt.get("schema") != PRIMARY_SCHEMA:
        raise independent_dynamics.VerificationError("primary schema mismatch")
    source_identity = source_checks(input_dir, receipt)
    contract = preparation_contract(receipt)
    snapshot_details = independent_dynamics.verify_primary_rows(input_dir, receipt)
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
    method_comparisons = [independent_dynamics._method_comparison(rows_by_arm.get(item.get("arm")), item) for item in independent]
    conservation_checks = [{"arm": item.get("arm"), "energy_drift": item.get("energy_drift"), "charge_drift": item.get("charge_drift"), "pass": bool(item.get("conservation_pass", False)), "raw_state_archive_complete": bool(item.get("raw_state_archive_complete", False))} for item in independent]
    primary_comparisons = receipt.get("comparisons", [])
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
        "independent_raw_archive_complete": independent_complete,
        "scalar_snapshot_comparison_pass": bool(method_comparisons and all(item["pass"] for item in method_comparisons)),
        "independent_conservation_pass": bool(conservation_checks and all(item["pass"] for item in conservation_checks)),
        "complete_physical_matter_formation": False,
        "gravitational_capture_established": False,
        "physical_size_map_established": False,
        "packet_count_minimum_established": False,
    }
    result["numeric_pass"] = bool(all(source_identity.values()) and contract["pass"] and snapshot_details["pass"] and primary_comparison_pass and mutation and corrupted_hash_rejected and result["scalar_snapshot_comparison_pass"] and result["independent_conservation_pass"] and independent_complete)
    write_json(output_path, result)
    return result


def run_smoke() -> int:
    grid = independent_dynamics.IndependentGrid(16, 1.0)
    records = []
    for arm in ARMS:
        q, v, coupling, charge = assemble_independent(grid, arm)
        observed = float((grid.volume * (-2.0 * independent_dynamics.A * (q[1] * v[2] - q[2] * v[1]))).sum())
        assert abs(observed - charge) / charge < 1.0e-12
        records.append({"arm": arm, "charge": observed, "center": ARM_SPECS[arm]["center"], "wave_number": ARM_SPECS[arm]["wave_number"], "coupling": coupling})
    print(independent_dynamics.json.dumps({"smoke": "PASS", "arms": records}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "runs" / "20260911_matter_formation_momentum_basin")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    input_dir = args.input.resolve()
    output = (args.output or (input_dir / "verification.json")).resolve()
    result = run(input_dir, output)
    print(independent_dynamics.json.dumps({"output": str(output), "numeric_pass": result["numeric_pass"], "snapshot_pass": result["snapshot_details"]["pass"], "conservation_pass": result["independent_conservation_pass"]}))
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
