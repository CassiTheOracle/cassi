#!/usr/bin/env python3
"""Independently verify the axisymmetric one-to-three packet probe."""
from __future__ import annotations

import argparse
import copy
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch

import verify_matter_formation_wave_capture as independent_dynamics
from matter_formation_packet_count_spec import (
    ARM_SPECS,
    ARMS,
    COMPARISON_OBSERVABLES,
    GEOMETRIES,
    GRID_SPECS,
    INITIAL_CORE_FRACTION_MAX,
    INITIAL_OVERLAP_MAX,
    PACKET_COUNT_CANDIDATES,
    R0,
    SAMPLE_DT,
    SHARE_TOL,
    SNAPSHOT_TIMES,
    T_FINAL,
    TOTAL_CHARGE,
    WAVE_NUMBER,
    WIDTH,
    BINDING_RATIO_MAX,
    RETAINED_FRACTION,
)

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
SELF = Path(__file__).resolve()
PREREG = COMPUTATIONS / "matter_formation_packet_count_prereg.md"
PRIMARY_SOURCE = COMPUTATIONS / "matter_formation_packet_count.py"
SPEC_SOURCE = COMPUTATIONS / "matter_formation_packet_count_spec.py"
NEUTRAL_SOURCE = COMPUTATIONS / "matter_formation_neutral_packets.py"
CLOUD_SOURCE = COMPUTATIONS / "matter_formation_radial_cloud.py"
WAVE_SOURCE = COMPUTATIONS / "matter_formation_wave_capture.py"
INDEPENDENT_WAVE_SOURCE = COMPUTATIONS / "verify_matter_formation_wave_capture.py"
SCHEMA = "matter-formation-packet-count-verification-v1"
PRIMARY_SCHEMA = "matter-formation-packet-count-primary-v1"


def sha256(path: Path) -> str:
    return independent_dynamics.sha256(path)


def write_json(path: Path, value: dict[str, Any]) -> None:
    independent_dynamics.write_json(path, value)


def strict_json(path: Path) -> dict[str, Any]:
    return independent_dynamics.strict_json(path)


def packet_directions(count: int, phase_sign: float) -> tuple[tuple[float, float], ...]:
    result = []
    for radial, axial in GEOMETRIES[count]:
        if count == 1:
            result.append((0.0, 0.0))
            continue
        norm = math.hypot(float(radial), float(axial))
        if norm <= 0.0:
            raise independent_dynamics.VerificationError("moving centre at origin")
        result.append((phase_sign * -float(radial) / norm, phase_sign * -float(axial) / norm))
    return tuple(result)


def assemble_independent(
    grid: independent_dynamics.IndependentGrid, arm: str
) -> tuple[torch.Tensor, torch.Tensor, float, float, dict[str, Any]]:
    config = ARM_SPECS[arm]
    count = int(config["count"])
    moving = count > 1
    omega = math.sqrt(independent_dynamics.OMEGA_INF**2 + 8.0 * WAVE_NUMBER**2) if moving else independent_dynamics.OMEGA_INF
    directions = packet_directions(count, float(config["phase_sign"]))
    radial = grid.r[:, None]
    axial = grid.axial[None, :]
    envelopes: list[torch.Tensor] = []
    terms: list[torch.Tensor] = []
    integrals: list[float] = []
    for (center_r, center_z), (direction_r, direction_z) in zip(GEOMETRIES[count], directions):
        envelope = torch.exp(
            -((radial - float(center_r)).square() + (axial - float(center_z)).square())
            / (2.0 * WIDTH**2)
        )
        phase = WAVE_NUMBER * (
            direction_r * (radial - float(center_r))
            + direction_z * (axial - float(center_z))
        )
        envelopes.append(envelope)
        terms.append(envelope * torch.exp(1j * phase))
        integrals.append(float((grid.volume * envelope.square()).sum()))
    if not all(math.isfinite(value) and value > 0.0 for value in integrals):
        raise independent_dynamics.VerificationError(f"invalid independent packet integral for {arm}")
    weights = [math.sqrt((1.0 / count) / integral) for integral in integrals]
    complex_field = torch.zeros_like(terms[0], dtype=torch.complex128)
    for weight, term in zip(weights, terms):
        complex_field = complex_field + weight * term
    norm = float(torch.sum(grid.volume * (complex_field.real.square() + complex_field.imag.square())))
    if not math.isfinite(norm) or norm <= 0.0:
        raise independent_dynamics.VerificationError(f"invalid independent coherent norm for {arm}")
    scale_squared = TOTAL_CHARGE / (2.0 * independent_dynamics.A * omega * norm)
    complex_field = complex_field * math.sqrt(scale_squared)
    isolated = [
        2.0 * independent_dynamics.A * omega * weight**2 * integral * scale_squared
        for weight, integral in zip(weights, integrals)
    ]
    isolated_total = sum(isolated)
    fractions = [value / isolated_total for value in isolated]
    if any(abs(value - 1.0 / count) > SHARE_TOL for value in fractions):
        raise independent_dynamics.VerificationError(f"independent equal-share failure for {arm}")
    overlaps = []
    for index in range(count):
        for other in range(index + 1, count):
            overlaps.append(
                float(
                    torch.abs(torch.sum(grid.volume * envelopes[index] * envelopes[other]))
                    / math.sqrt(integrals[index] * integrals[other])
                )
            )
    q = torch.zeros((3, grid.nr, grid.nz), dtype=torch.float64, device="cuda")
    q[1], q[2] = complex_field.real, complex_field.imag
    v = torch.zeros_like(q)
    v[1], v[2] = omega * q[2], -omega * q[1]
    rho = 2.0 * independent_dynamics.A * omega * (q[1].square() + q[2].square())
    distance = torch.sqrt(grid.r2 + grid.axial[None, :].square())
    initial_core = float(
        (grid.volume * rho * (distance < independent_dynamics.CORE_RADIUS).to(rho.dtype)).sum()
    ) / TOTAL_CHARGE
    metadata = {
        "packet_count": count,
        "centers": [[float(r), float(z)] for r, z in GEOMETRIES[count]],
        "phase_directions": [[float(r), float(z)] for r, z in directions],
        "width": WIDTH,
        "core_radius": independent_dynamics.CORE_RADIUS,
        "reference_radius": R0,
        "wave_number": WAVE_NUMBER if moving else 0.0,
        "omega": omega,
        "phase_sign": float(config["phase_sign"]),
        "orientation": config["orientation"],
        "coupled": bool(config["coupled"]),
        "candidate": bool(config["candidate"]),
        "uncoupled": bool(config["uncoupled"]),
        "isolated_packet_charge_contributions": isolated,
        "isolated_packet_charge_fractions": fractions,
        "pairwise_envelope_overlaps": overlaps,
        "maximum_pairwise_overlap": max(overlaps, default=0.0),
        "initial_core_fraction": initial_core,
    }
    coupling = independent_dynamics.HC if bool(config["coupled"]) else 0.0
    return q, v, coupling, TOTAL_CHARGE, metadata


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


def independent_evolution(
    arm: str, radius: int, spacing: float, dt: float, archive_dir: Path
) -> dict[str, Any]:
    grid = independent_dynamics.IndependentGrid(radius, spacing)
    q, v, coupling, declared_charge, _metadata = assemble_independent(grid, arm)
    initial_rho = -2.0 * independent_dynamics.A * (q[1] * v[2] - q[2] * v[1])
    charge_reference = float((grid.volume * initial_rho).sum())
    energy_reference = float(grid.energy(q, v, coupling))
    if not math.isfinite(charge_reference) or not math.isfinite(energy_reference):
        raise independent_dynamics.VerificationError(f"nonfinite independent initial reference for {arm}")
    results: dict[float, dict[str, Any]] = {
        0.0: independent_dynamics.metric(grid, q, v, coupling, charge_reference, energy_reference)
    }
    states = [write_independent_state(archive_dir, arm, grid, q, v, 0.0)]
    targets = {int(round(t / dt)): t for t in SNAPSHOT_TIMES[1:]}
    for step in range(1, int(round(T_FINAL / dt)) + 1):
        q, v = independent_dynamics.rk4_step(grid, q, v, dt, coupling)
        if step in targets:
            time_value = targets[step]
            results[time_value] = independent_dynamics.metric(
                grid, q, v, coupling, charge_reference, energy_reference
            )
            states.append(write_independent_state(archive_dir, arm, grid, q, v, time_value))
    if len(results) != len(SNAPSHOT_TIMES) or len(states) != len(SNAPSHOT_TIMES):
        raise independent_dynamics.VerificationError(f"independent evolution missed snapshot for {arm}")
    finite_snapshots = all(
        independent_dynamics.finite(values)
        and all(
            independent_dynamics.finite_number(values.get(name))
            for name in independent_dynamics.REQUIRED_OBSERVABLES
        )
        for values in results.values()
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
        "declared_charge": declared_charge,
        "energy_reference": energy_reference,
        "snapshots": {str(time_value): values for time_value, values in results.items()},
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
        "source": "fresh independent RK4 integration and packet assembly",
    }


def source_checks(input_dir: Path, receipt: dict[str, Any]) -> dict[str, bool]:
    required = (
        PREREG,
        PRIMARY_SOURCE,
        SPEC_SOURCE,
        NEUTRAL_SOURCE,
        CLOUD_SOURCE,
        WAVE_SOURCE,
        INDEPENDENT_WAVE_SOURCE,
        SELF,
    )
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
    checks["archive_bytes"] = bool(
        all(value for key, value in checks.items() if key != "protocol_live" and not key.startswith("live_"))
    )
    checks["live_source_bytes"] = bool(all(value for key, value in checks.items() if key.startswith("live_")))
    return checks


def preparation_contract(receipt: dict[str, Any]) -> dict[str, Any]:
    rows = receipt.get("rows", [])
    expected = {(grid, arm) for grid in GRID_SPECS for arm in ARMS}
    observed = {(row.get("grid"), row.get("arm")) for row in rows if isinstance(row, dict)}
    preparation = receipt.get("preparation", {})
    checks: dict[str, bool] = {
        "row_key_set": observed == expected,
        "row_count": len(rows) == len(expected),
        "top_level_schedule": bool(
            isinstance(preparation, dict)
            and preparation.get("total_charge") == TOTAL_CHARGE
            and preparation.get("reference_radius") == R0
            and preparation.get("width") == WIDTH
            and preparation.get("wave_number") == WAVE_NUMBER
            and preparation.get("initial_overlap_max") == INITIAL_OVERLAP_MAX
            and preparation.get("initial_core_fraction_max") == INITIAL_CORE_FRACTION_MAX
            and preparation.get("share_tolerance") == SHARE_TOL
            and preparation.get("geometries") == {str(count): [list(center) for center in centers] for count, centers in GEOMETRIES.items()}
            and preparation.get("arm_specs") == ARM_SPECS
        ),
        "charge_metadata": True,
        "count_metadata": True,
        "geometry_metadata": True,
        "direction_metadata": True,
        "share_metadata": True,
        "overlap_metadata": True,
        "core_metadata": True,
        "coupling_metadata": True,
    }
    for row in rows:
        if not isinstance(row, dict):
            continue
        arm = row.get("arm")
        metadata = row.get("metadata", {})
        config = ARM_SPECS.get(arm, {})
        count = int(config.get("count", -1)) if config else -1
        expected_centers = [[float(r), float(z)] for r, z in GEOMETRIES.get(count, ())]
        expected_directions = [[float(r), float(z)] for r, z in packet_directions(count, float(config.get("phase_sign", 0.0)))] if config else []
        fractions = metadata.get("isolated_packet_charge_fractions")
        overlaps = metadata.get("pairwise_envelope_overlaps")
        try:
            checks["charge_metadata"] = checks["charge_metadata"] and abs(float(metadata.get("charge")) - TOTAL_CHARGE) <= SHARE_TOL
            checks["count_metadata"] = checks["count_metadata"] and metadata.get("packet_count") == count
            checks["geometry_metadata"] = checks["geometry_metadata"] and metadata.get("centers") == expected_centers
            checks["direction_metadata"] = checks["direction_metadata"] and metadata.get("phase_directions") == expected_directions
            checks["share_metadata"] = checks["share_metadata"] and (
                isinstance(fractions, list)
                and len(fractions) == count
                and all(abs(float(value) - 1.0 / count) <= SHARE_TOL for value in fractions)
            )
            checks["overlap_metadata"] = checks["overlap_metadata"] and (
                isinstance(overlaps, list)
                and len(overlaps) == count * (count - 1) // 2
                and all(math.isfinite(float(value)) and float(value) <= INITIAL_OVERLAP_MAX for value in overlaps)
                if count > 1
                else isinstance(overlaps, list) and len(overlaps) == 0
            )
            checks["core_metadata"] = checks["core_metadata"] and (
                abs(float(metadata.get("core_radius")) - independent_dynamics.CORE_RADIUS) <= SHARE_TOL
                and math.isfinite(float(metadata.get("initial_core_fraction")))
                and (count == 1 or float(metadata.get("initial_core_fraction")) <= INITIAL_CORE_FRACTION_MAX)
            )
            expected_coupled = bool(config.get("coupled"))
            checks["coupling_metadata"] = checks["coupling_metadata"] and (
                bool(metadata.get("coupled")) == expected_coupled
                and bool(metadata.get("candidate")) == bool(config.get("candidate"))
                and bool(metadata.get("uncoupled")) == bool(config.get("uncoupled"))
                and bool(row.get("coupling") == (independent_dynamics.HC if expected_coupled else 0.0))
            )
        except (TypeError, ValueError, ZeroDivisionError):
            for key in ("charge_metadata", "count_metadata", "geometry_metadata", "direction_metadata", "share_metadata", "overlap_metadata", "core_metadata", "coupling_metadata"):
                checks[key] = False
    checks["pass"] = bool(all(checks.values()))
    return checks


def mutation_control(input_dir: Path, receipt: dict[str, Any]) -> bool:
    row = receipt["rows"][0]
    state = row["states"][0]
    grid, original_q, velocity = independent_dynamics._validate_state_archive(input_dir, row, state)
    original_fields = original_q.detach().cpu().numpy()
    before = float(grid.energy(original_q, velocity, float(row["coupling"])))
    mutated_fields = np.array(original_fields, copy=True)
    mutated_fields[0, 0, 0] += 0.1
    mutated_q = torch.as_tensor(mutated_fields, dtype=torch.float64, device="cuda")
    after = float(grid.energy(mutated_q, velocity, float(row["coupling"])))
    return bool(
        not np.array_equal(mutated_fields, original_fields)
        and abs(after - before) > 1.0e-8
        and abs(after - float(row["trace"][0]["energy"])) > 1.0e-8
    )


def corrupted_hash_control(input_dir: Path, receipt: dict[str, Any]) -> bool:
    mutated = copy.deepcopy(receipt)
    mutated["rows"][0]["states"][0]["sha256"] = "0" * 64
    details = independent_dynamics.verify_primary_rows(input_dir, mutated)
    return bool(
        not details["pass"]
        and any("hash mismatch" in failure for item in details["details"] for failure in item["failures"])
    )


def independent_preparation_checks() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    charges: dict[str, float] = {}
    for grid_name, (radius, spacing, _dt) in GRID_SPECS.items():
        grid = independent_dynamics.IndependentGrid(radius, spacing)
        for arm in ARMS:
            q, v, _coupling, declared, metadata = assemble_independent(grid, arm)
            charge = float((grid.volume * (-2.0 * independent_dynamics.A * (q[1] * v[2] - q[2] * v[1]))).sum())
            key = f"{grid_name}_{arm}"
            charges[key] = charge
            checks[key] = bool(
                math.isfinite(charge)
                and abs(charge - declared) / TOTAL_CHARGE <= SHARE_TOL
                and metadata["packet_count"] == ARM_SPECS[arm]["count"]
            )
    return {"checks": checks, "charges": charges, "pass": bool(checks and all(checks.values()))}


def method_comparison(primary_row: dict[str, Any] | None, independent: dict[str, Any]) -> dict[str, Any]:
    arm = independent.get("arm")
    result: dict[str, Any] = {
        "arm": arm,
        "errors": {},
        "failures": [],
        "comparison_observables": list(COMPARISON_OBSERVABLES),
        "pass": False,
    }
    if primary_row is None:
        result["failures"].append("primary T1 row missing")
        return result
    snapshots = independent.get("snapshots", {})
    trace = primary_row.get("trace", [])
    for time_value in SNAPSHOT_TIMES:
        values = snapshots.get(str(time_value))
        index = int(round(time_value / SAMPLE_DT))
        if not isinstance(values, dict) or not isinstance(trace, list) or index >= len(trace):
            result["failures"].append(f"missing snapshot {time_value}")
            continue
        observed = trace[index] if isinstance(trace[index], dict) else {}
        if any(
            not independent_dynamics.finite_number(observed.get(name))
            or not independent_dynamics.finite_number(values.get(name))
            for name in independent_dynamics.REQUIRED_OBSERVABLES
        ):
            result["failures"].append(f"{time_value}:required observable missing or invalid")
            continue
        for name in COMPARISON_OBSERVABLES:
            result["errors"][f"{time_value}:{name}"] = abs(float(observed[name]) - float(values[name])) / max(1.0, abs(float(observed[name])), abs(float(values[name])))
    result["pass"] = bool(
        result["errors"]
        and not result["failures"]
        and max(result["errors"].values()) < independent_dynamics.METHOD_TOL
    )
    return result


def derive_packet_count(receipt: dict[str, Any], comparisons: list[dict[str, Any]], primary_ok: bool) -> dict[str, Any]:
    rows = {(row.get("grid"), row.get("arm")): row for row in receipt.get("rows", []) if isinstance(row, dict)}
    def full(arm: str) -> bool:
        return bool(
            all(rows.get((grid, arm), {}).get("numerically_qualified") is True for grid in GRID_SPECS)
            and len([item for item in comparisons if item.get("arm") == arm or item.get("left", "").endswith(f"_{arm}") or item.get("right", "").endswith(f"_{arm}")]) == 2
            and all(
                item.get("pass") is True
                for item in comparisons
                if item.get("left", "").endswith(f"_{arm}") or item.get("right", "").endswith(f"_{arm}")
            )
        )
    single_nonpersistent = bool(
        all(rows.get((grid, "single_center"), {}).get("numerically_qualified") is True for grid in GRID_SPECS)
        and all(not bool(rows.get((grid, "single_center"), {}).get("persistent_remnant")) for grid in GRID_SPECS)
    )
    pair_full = full("pair_inward")
    triple_full = full("triple_inward")
    pair_forms = bool(pair_full and all(bool(rows.get((grid, "pair_inward"), {}).get("formation")) for grid in GRID_SPECS))
    triple_forms = bool(triple_full and all(bool(rows.get((grid, "triple_inward"), {}).get("formation")) for grid in GRID_SPECS))
    pair_nonformation = bool(pair_full and all(not bool(rows.get((grid, "pair_inward"), {}).get("formation")) for grid in GRID_SPECS))
    minimum = None
    if primary_ok and single_nonpersistent and pair_forms:
        minimum = 2
    elif primary_ok and single_nonpersistent and pair_nonformation and triple_forms:
        minimum = 3
    return {
        "single_nonpersistent": single_nonpersistent,
        "pair_fully_compared": pair_full,
        "triple_fully_compared": triple_full,
        "pair_forms": pair_forms,
        "triple_forms": triple_forms,
        "pair_nonformation": pair_nonformation,
        "minimum_packet_count": minimum,
        "packet_count_minimum_established": minimum is not None,
        "pass": bool(primary_ok and (minimum is not None or (pair_full and triple_full and single_nonpersistent))),
    }


def run(input_dir: Path, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise independent_dynamics.VerificationError(f"refusing to overwrite verifier output: {output_path}")
    receipt = strict_json(input_dir / "result.json")
    if receipt.get("schema") != PRIMARY_SCHEMA:
        raise independent_dynamics.VerificationError("primary schema mismatch")
    source_identity = source_checks(input_dir, receipt)
    contract = preparation_contract(receipt)
    snapshot_details = independent_dynamics.verify_primary_rows(input_dir, receipt)
    mutation = mutation_control(input_dir, receipt)
    corrupted_hash_rejected = corrupted_hash_control(input_dir, receipt)
    independent_preparation = independent_preparation_checks()
    archive_dir = output_path.parent / f"{output_path.stem}_independent_states"
    if archive_dir.exists():
        raise independent_dynamics.VerificationError(f"refusing to overwrite independent archive: {archive_dir}")
    archive_dir.mkdir(parents=True, exist_ok=False)
    radius, spacing, dt = GRID_SPECS["T1"]
    independent = [independent_evolution(arm, radius, spacing, dt, archive_dir) for arm in ARMS]
    independent_complete, archive_validation = independent_dynamics._validate_independent_archive(archive_dir, independent)
    rows_by_arm = {row.get("arm"): row for row in receipt.get("rows", []) if row.get("grid") == "T1"}
    method_comparisons = [method_comparison(rows_by_arm.get(item.get("arm")), item) for item in independent]
    conservation_checks = [
        {
            "arm": item.get("arm"),
            "energy_drift": item.get("energy_drift"),
            "charge_drift": item.get("charge_drift"),
            "pass": bool(item.get("conservation_pass")),
            "raw_state_archive_complete": bool(item.get("raw_state_archive_complete")),
        }
        for item in independent
    ]
    primary_comparisons = receipt.get("comparisons", [])
    primary_comparison_pass = bool(
        receipt.get("numerical_pass") is True
        and isinstance(primary_comparisons, list)
        and len(primary_comparisons) == len(ARMS) * 2
        and all(isinstance(item, dict) and item.get("pass") is True for item in primary_comparisons)
    )
    independent_method_pass = bool(method_comparisons and all(item["pass"] for item in method_comparisons))
    independent_conservation_pass = bool(conservation_checks and all(item["pass"] for item in conservation_checks))
    qualification = bool(
        all(source_identity.values())
        and contract["pass"]
        and snapshot_details["pass"]
        and mutation
        and corrupted_hash_rejected
        and independent_preparation["pass"]
        and primary_comparison_pass
        and independent_method_pass
        and independent_conservation_pass
        and independent_complete
    )
    packet_count = derive_packet_count(receipt, primary_comparisons, qualification)
    result = {
        "schema": SCHEMA,
        "primary": str(input_dir),
        "primary_schema": receipt.get("schema"),
        "source_checks": source_identity,
        "preparation_contract": contract,
        "snapshot_details": snapshot_details,
        "rejection_control_mutated_state_rejected": mutation,
        "rejection_control_corrupted_hash_rejected": corrupted_hash_rejected,
        "independent_preparation_checks": independent_preparation,
        "independent_evolution": independent,
        "independent_archive_validation": archive_validation,
        "conservation_checks": conservation_checks,
        "method_comparisons": method_comparisons,
        "primary_comparison_pass": primary_comparison_pass,
        "independent_method_pass": independent_method_pass,
        "independent_conservation_pass": independent_conservation_pass,
        "independent_raw_archive_complete": independent_complete,
        "packet_count_reconstruction": packet_count,
        "numeric_pass": bool(qualification and packet_count["pass"]),
        "complete_physical_matter_formation": False,
        "gravitational_capture_established": False,
        "physical_size_map_established": False,
        "packet_count_minimum_established": bool(packet_count["packet_count_minimum_established"]),
    }
    write_json(output_path, result)
    return result


def run_smoke() -> int:
    grid = independent_dynamics.IndependentGrid(48, 1.0)
    records = []
    for arm in ARMS:
        q, v, coupling, declared, metadata = assemble_independent(grid, arm)
        observed = float((grid.volume * (-2.0 * independent_dynamics.A * (q[1] * v[2] - q[2] * v[1]))).sum())
        assert abs(observed - declared) / TOTAL_CHARGE <= SHARE_TOL
        assert metadata["core_radius"] == independent_dynamics.CORE_RADIUS
        records.append({"arm": arm, "packet_count": metadata["packet_count"], "charge": observed, "coupling": coupling})
    print(independent_dynamics.json.dumps({"smoke": "PASS", "arms": records}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "runs" / "20260912_matter_formation_packet_count")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    input_dir = args.input.resolve()
    output = (args.output or (input_dir / "verification.json")).resolve()
    result = run(input_dir, output)
    print(independent_dynamics.json.dumps({
        "output": str(output),
        "numeric_pass": result["numeric_pass"],
        "packet_count_minimum": result["packet_count_reconstruction"]["minimum_packet_count"],
        "archive_pass": result["independent_raw_archive_complete"],
        "method_pass": result["independent_method_pass"],
    }))
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
