#!/usr/bin/env python3
"""Run the preregistered axisymmetric one-to-three packet collision probe."""
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
from matter_formation_packet_count_spec import (  # noqa: E402
    ARM_SPECS,
    ARMS,
    COMPARISON_OBSERVABLES,
    GEOMETRIES,
    GRID_SPECS,
    INITIAL_CORE_FRACTION_MAX,
    INITIAL_OVERLAP_MAX,
    LATE_START,
    PACKET_COUNT_CANDIDATES,
    R0,
    RETAINED_FRACTION,
    SAMPLE_DT,
    SHARE_TOL,
    SNAPSHOT_TIMES,
    T_FINAL,
    TOTAL_CHARGE,
    WAVE_NUMBER,
    WIDTH,
    BINDING_RATIO_MAX,
)

SELF = Path(__file__).resolve()
PREREG = COMPUTATIONS / "matter_formation_packet_count_prereg.md"
SPEC_SOURCE = COMPUTATIONS / "matter_formation_packet_count_spec.py"
NEUTRAL_SOURCE = COMPUTATIONS / "matter_formation_neutral_packets.py"
CLOUD_SOURCE = COMPUTATIONS / "matter_formation_radial_cloud.py"
WAVE_SOURCE = COMPUTATIONS / "matter_formation_wave_capture.py"
INDEPENDENT_WAVE_SOURCE = COMPUTATIONS / "verify_matter_formation_wave_capture.py"
VERIFIER_SOURCE = COMPUTATIONS / "verify_matter_formation_packet_count.py"
SCHEMA = "matter-formation-packet-count-primary-v1"


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
    for path in (
        SELF,
        PREREG,
        SPEC_SOURCE,
        NEUTRAL_SOURCE,
        CLOUD_SOURCE,
        WAVE_SOURCE,
        INDEPENDENT_WAVE_SOURCE,
        VERIFIER_SOURCE,
    ):
        relative = path.relative_to(ROOT).as_posix()
        destination = source_dir / relative.replace("/", "__")
        shutil.copyfile(path, destination)
        result[relative] = sha256(path)
    return result


def packet_directions(count: int, phase_sign: float) -> tuple[tuple[float, float], ...]:
    centers = GEOMETRIES[count]
    if count == 1:
        return ((0.0, 0.0),)
    result = []
    for radial, axial in centers:
        norm = math.hypot(float(radial), float(axial))
        if norm <= 0.0:
            raise RuntimeError("moving packet centre cannot be at the origin")
        result.append((phase_sign * -float(radial) / norm, phase_sign * -float(axial) / norm))
    return tuple(result)


def assemble_primary(
    grid: CylindricalGrid, arm: str
) -> tuple[torch.Tensor, torch.Tensor, float, dict[str, Any]]:
    config = ARM_SPECS[arm]
    count = int(config["count"])
    centers = GEOMETRIES[count]
    phase_sign = float(config["phase_sign"])
    moving = count > 1
    omega = math.sqrt(dynamics.OMEGA_INF**2 + 8.0 * WAVE_NUMBER**2) if moving else dynamics.OMEGA_INF
    radial = grid.r[:, None]
    axial = grid.axial[None, :]
    directions = packet_directions(count, phase_sign)
    envelopes: list[torch.Tensor] = []
    terms: list[torch.Tensor] = []
    integrals: list[float] = []
    for (center_r, center_z), (direction_r, direction_z) in zip(centers, directions):
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
        integral = float((grid.volume * envelope.square()).sum())
        if not finite_number(integral) or integral <= 0.0:
            raise RuntimeError(f"invalid packet envelope integral for {arm}")
        integrals.append(integral)
    weights = [math.sqrt((1.0 / count) / integral) for integral in integrals]
    complex_field = torch.zeros_like(terms[0], dtype=torch.complex128)
    for weight, term in zip(weights, terms):
        complex_field = complex_field + weight * term
    norm = torch.sum(grid.volume * (complex_field.real.square() + complex_field.imag.square()))
    norm_value = float(norm)
    if not finite_number(norm_value) or norm_value <= 0.0:
        raise RuntimeError(f"invalid coherent normalization for {arm}")
    scale_squared = TOTAL_CHARGE / (2.0 * dynamics.A * omega * norm_value)
    complex_field = complex_field * math.sqrt(scale_squared)
    isolated_charges = [
        2.0 * dynamics.A * omega * weight**2 * integral * scale_squared
        for weight, integral in zip(weights, integrals)
    ]
    isolated_total = sum(isolated_charges)
    isolated_fractions = [value / isolated_total for value in isolated_charges]
    if any(abs(value - 1.0 / count) > SHARE_TOL for value in isolated_fractions):
        raise RuntimeError(f"equal isolated packet shares failed for {arm}")
    pairwise_overlaps: list[float] = []
    for index in range(count):
        for other in range(index + 1, count):
            overlap = float(
                torch.abs(torch.sum(grid.volume * envelopes[index] * envelopes[other]))
                / math.sqrt(integrals[index] * integrals[other])
            )
            pairwise_overlaps.append(overlap)
    q = torch.zeros((3, grid.nr, grid.nz), dtype=torch.float64, device="cuda")
    q[1], q[2] = complex_field.real, complex_field.imag
    v = torch.zeros_like(q)
    v[1], v[2] = omega * q[2], -omega * q[1]
    rho = 2.0 * dynamics.A * omega * (q[1].square() + q[2].square())
    distance = torch.sqrt(grid.r2 + grid.axial[None, :].square())
    initial_core_fraction = float(
        (grid.volume * rho * (distance < dynamics.CORE_RADIUS).to(rho.dtype)).sum()
    ) / TOTAL_CHARGE
    metadata: dict[str, Any] = {
        "charge": TOTAL_CHARGE,
        "packet_count": count,
        "centers": [[float(radial_value), float(axial_value)] for radial_value, axial_value in centers],
        "phase_directions": [[float(radial_value), float(axial_value)] for radial_value, axial_value in directions],
        "width": WIDTH,
        "core_radius": dynamics.CORE_RADIUS,
        "reference_radius": R0,
        "wave_number": WAVE_NUMBER if moving else 0.0,
        "omega": omega,
        "relative_phase": 0.0,
        "phase_sign": phase_sign,
        "orientation": config["orientation"],
        "coupled": bool(config["coupled"]),
        "candidate": bool(config["candidate"]),
        "uncoupled": bool(config["uncoupled"]),
        "raw_packet_weights": weights,
        "isolated_packet_charge_contributions": isolated_charges,
        "isolated_packet_charge_fractions": isolated_fractions,
        "pairwise_envelope_overlaps": pairwise_overlaps,
        "maximum_pairwise_overlap": max(pairwise_overlaps, default=0.0),
        "initial_core_fraction": initial_core_fraction,
        "initially_unbound": bool(
            count == 1
            or (
                max(pairwise_overlaps, default=math.inf) <= INITIAL_OVERLAP_MAX
                and initial_core_fraction <= INITIAL_CORE_FRACTION_MAX
            )
        ),
    }
    return q, v, (dynamics.HC if bool(config["coupled"]) else 0.0), metadata


def compare_rows_robust(left: dict[str, Any], right: dict[str, Any], kind: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "kind": kind,
        "left": f"{left['grid']}_{left['arm']}",
        "right": f"{right['grid']}_{right['arm']}",
        "errors": {},
        "comparison_observables": list(COMPARISON_OBSERVABLES),
        "pass": False,
    }
    if not left.get("numerically_qualified", False) or not right.get("numerically_qualified", False):
        result["reason"] = "both rows must pass numerical qualification"
        return result
    left_late = [row for index, row in enumerate(left["trace"]) if left["times"][index] >= LATE_START]
    right_late = [row for index, row in enumerate(right["trace"]) if right["times"][index] >= LATE_START]
    if not left_late or not right_late:
        result["reason"] = "late trace missing"
        return result
    if any(
        not finite_number(row.get(name))
        for row in left_late + right_late
        for name in dynamics.REQUIRED_OBSERVABLES
    ):
        result["reason"] = "nonfinite required observable"
        return result
    scales = {
        "energy": max(1.0, abs(float(left["initial"]["energy"])), abs(float(right["initial"]["energy"]))),
        "charge": max(1.0, abs(float(left["initial"]["charge"])), abs(float(right["initial"]["charge"]))),
        "core_fraction": 1.0,
        "core_rms": dynamics.CORE_RADIUS,
        "core_energy": max(1.0, abs(float(left["initial"]["energy"])), abs(float(right["initial"]["energy"]))),
        "shell_energy_fraction": 1.0,
    }
    left_means = {name: float(np.mean([row[name] for row in left_late])) for name in COMPARISON_OBSERVABLES}
    right_means = {name: float(np.mean([row[name] for row in right_late])) for name in COMPARISON_OBSERVABLES}
    result["errors"] = {
        name: abs(left_means[name] - right_means[name]) / scales[name]
        for name in COMPARISON_OBSERVABLES
    }
    result["pass"] = bool(
        all(finite_number(value) for value in result["errors"].values())
        and max(result["errors"].values()) < dynamics.COMPARISON_TOL
    )
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
    trace: list[dict[str, Any]] = [
        dynamics.diagnostics(grid, q, v, coupling, initial_charge, initial_energy, acc)
    ]
    states: list[dict[str, Any]] = [
        dynamics.write_state(output / f"{grid_name}_{arm}_t000.npz", grid, q, v, 0.0)
    ]
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
                states.append(
                    dynamics.write_state(
                        output / f"{grid_name}_{arm}_t{int(round(current)):03d}.npz",
                        grid,
                        q,
                        v,
                        current,
                    )
                )
    energy_values = [row.get("energy") for row in trace]
    charge_values = [row.get("charge") for row in trace]
    energy_drift = (
        max(abs(float(value) - initial_energy) for value in energy_values) / max(1.0, abs(initial_energy))
        if all(finite_number(value) for value in energy_values)
        else math.inf
    )
    charge_drift = (
        max(abs(float(value) - initial_charge) for value in charge_values) / max(1.0, abs(initial_charge))
        if all(finite_number(value) for value in charge_values)
        else math.inf
    )
    late = [row for index, row in enumerate(trace) if times[index] >= LATE_START]
    core_values = [row.get("core_fraction") for row in late]
    binding_values = [row.get("binding_ratio") for row in late]
    finite_trace = all(dynamics.finite(row) for row in trace)
    complete_observables = bool(
        trace
        and all(
            finite_number(row.get(name))
            for row in trace
            for name in dynamics.REQUIRED_OBSERVABLES
        )
    )
    balance_error = (
        max(
            max(float(row["core_energy_balance_error"]) for row in trace),
            max(float(row["core_charge_balance_error"]) for row in trace),
        )
        if complete_observables
        else math.inf
    )
    numerically_qualified = bool(
        finite_trace
        and complete_observables
        and energy_drift < dynamics.ENERGY_DRIFT_TOL
        and charge_drift < dynamics.CHARGE_DRIFT_TOL
        and max(float(row["boundary_energy_fraction"]) for row in trace) < dynamics.BOUNDARY_ENERGY_TOL
        and balance_error <= dynamics.LOCAL_BALANCE_TOL
    )
    eligibility = bool(
        metadata["candidate"]
        and metadata["initially_unbound"]
        and initial_energy >= dynamics.OMEGA_INF * abs(initial_charge)
    )
    late_variation = math.inf
    if late and abs(initial_charge) > 1.0e-30 and all(finite_number(row.get("core_charge")) for row in late):
        late_variation = (
            max(float(row["core_charge"]) for row in late)
            - min(float(row["core_charge"]) for row in late)
        ) / abs(initial_charge)
    late_core_fraction_min = (
        min(float(value) for value in core_values)
        if late and all(finite_number(value) for value in core_values)
        else math.inf
    )
    binding_gate_evaluated = bool(late and complete_observables and late_core_fraction_min >= RETAINED_FRACTION)
    binding_gate_excluded = bool(late and complete_observables and late_core_fraction_min < RETAINED_FRACTION)
    binding_gate_pass = bool(
        binding_gate_evaluated
        and all(float(value) < BINDING_RATIO_MAX for value in binding_values)
    )
    persistent = bool(
        late
        and complete_observables
        and late_core_fraction_min >= RETAINED_FRACTION
        and binding_gate_pass
        and max(float(row["core_rms"]) for row in late) <= dynamics.CORE_RMS_MAX
        and max(float(row["shell_energy_fraction"]) for row in late) <= dynamics.SHELL_ENERGY_FRACTION
        and late_variation <= dynamics.LATE_CORE_VARIATION
    )
    formation = bool(
        metadata["candidate"]
        and metadata["coupled"]
        and eligibility
        and numerically_qualified
        and persistent
    )
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
        "binding_gate_excluded_near_zero": binding_gate_excluded,
        "binding_gate_pass": binding_gate_pass,
        "numerically_qualified": numerically_qualified,
        "preparation_eligible": eligibility,
        "persistent_remnant": persistent,
        "formation": formation,
        "self_localized": bool((not metadata["candidate"]) and numerically_qualified and persistent),
        "complete_physical_matter_formation": False,
        "gravitational_capture_established": False,
        "packet_count_minimum_established": False,
        "elapsed_seconds": time.perf_counter() - started,
    }
    write_json(output / f"{grid_name}_{arm}.json", row)
    return row


def fully_compared(indexed: dict[tuple[str, str], dict[str, Any]], comparisons: list[dict[str, Any]], arm: str) -> bool:
    rows = [indexed.get((grid_name, arm)) for grid_name in GRID_SPECS]
    if not all(isinstance(row, dict) and row.get("numerically_qualified") is True for row in rows):
        return False
    relevant = [item for item in comparisons if item["left"].endswith(f"_{arm}") or item["right"].endswith(f"_{arm}")]
    return bool(len(relevant) == 2 and all(item.get("pass") is True for item in relevant))


def derive_packet_count(indexed: dict[tuple[str, str], dict[str, Any]], comparisons: list[dict[str, Any]], numerical_pass: bool) -> tuple[int | None, dict[str, Any]]:
    single_rows = [indexed.get((grid_name, "single_center")) for grid_name in GRID_SPECS]
    pair_rows = [indexed.get((grid_name, "pair_inward")) for grid_name in GRID_SPECS]
    triple_rows = [indexed.get((grid_name, "triple_inward")) for grid_name in GRID_SPECS]
    single_nonpersistent = bool(
        all(isinstance(row, dict) and row.get("numerically_qualified") is True for row in single_rows)
        and all(not bool(row.get("persistent_remnant")) for row in single_rows if isinstance(row, dict))
    )
    pair_full = fully_compared(indexed, comparisons, "pair_inward")
    triple_full = fully_compared(indexed, comparisons, "triple_inward")
    pair_forms = bool(pair_full and all(bool(row.get("formation")) for row in pair_rows if isinstance(row, dict)))
    triple_forms = bool(triple_full and all(bool(row.get("formation")) for row in triple_rows if isinstance(row, dict)))
    pair_nonformation = bool(pair_full and all(not bool(row.get("formation")) for row in pair_rows if isinstance(row, dict)))
    minimum: int | None = None
    if numerical_pass and single_nonpersistent and pair_forms:
        minimum = 2
    elif numerical_pass and single_nonpersistent and pair_nonformation and triple_forms:
        minimum = 3
    details = {
        "single_nonpersistent": single_nonpersistent,
        "pair_fully_compared": pair_full,
        "triple_fully_compared": triple_full,
        "pair_forms": pair_forms,
        "triple_forms": triple_forms,
        "pair_nonformation": pair_nonformation,
        "minimum_packet_count": minimum,
        "packet_count_minimum_established": minimum is not None,
    }
    return minimum, details


def run_smoke() -> int:
    grid = CylindricalGrid(48, 1.0)
    records = []
    for arm in ARMS:
        q, v, coupling, metadata = assemble_primary(grid, arm)
        charge = float((grid.volume * (-2.0 * dynamics.A * (q[1] * v[2] - q[2] * v[1]))).sum())
        assert abs(charge - TOTAL_CHARGE) / TOTAL_CHARGE < SHARE_TOL
        assert metadata["packet_count"] == ARM_SPECS[arm]["count"]
        assert metadata["core_radius"] == dynamics.CORE_RADIUS
        assert len(metadata["centers"]) == ARM_SPECS[arm]["count"]
        assert len(metadata["isolated_packet_charge_fractions"]) == ARM_SPECS[arm]["count"]
        assert all(
            abs(float(value) - 1.0 / metadata["packet_count"]) <= SHARE_TOL
            for value in metadata["isolated_packet_charge_fractions"]
        )
        records.append(
            {
                "arm": arm,
                "packet_count": metadata["packet_count"],
                "charge": charge,
                "maximum_pairwise_overlap": metadata["maximum_pairwise_overlap"],
                "initial_core_fraction": metadata["initial_core_fraction"],
                "coupling": coupling,
            }
        )
    print(dynamics.json.dumps({"smoke": "PASS", "arms": records}))
    return 0


def run_campaign(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True)
    source_hashes = snapshot_sources(output)
    primary = output / "primary"
    primary.mkdir()
    rows: list[dict[str, Any]] = []
    radius, spacing, dt = GRID_SPECS["G0"]
    for arm in ARMS:
        rows.append(run_row(primary, "G0", CylindricalGrid(radius, spacing), dt, arm))
    for grid_name in ("G1", "T1"):
        radius, spacing, dt = GRID_SPECS[grid_name]
        for arm in ARMS:
            rows.append(run_row(primary, grid_name, CylindricalGrid(radius, spacing), dt, arm))
    indexed = {(row["grid"], row["arm"]): row for row in rows}
    comparisons = []
    for arm in ARMS:
        comparisons.append(compare_rows_robust(indexed[("G0", arm)], indexed[("G1", arm)], "space"))
        comparisons.append(compare_rows_robust(indexed[("G0", arm)], indexed[("T1", arm)], "time"))
    comparison_pass = bool(len(comparisons) == 2 * len(ARMS) and all(item.get("pass") is True for item in comparisons))
    row_qualification_pass = bool(all(row.get("numerically_qualified") is True for row in rows))
    numerical_pass = bool(comparison_pass and row_qualification_pass)
    minimum, minimum_details = derive_packet_count(indexed, comparisons, numerical_pass)
    if not numerical_pass:
        verdict = "INCONCLUSIVE"
    elif minimum is not None:
        verdict = f"EMERGES—conditional packet-count minimum {minimum} in the declared axisymmetric family"
    else:
        verdict = "DOES NOT EMERGE in the specified one-to-three packet schedule"
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
            "reference_radius": R0,
            "width": WIDTH,
            "wave_number": WAVE_NUMBER,
            "initial_overlap_max": INITIAL_OVERLAP_MAX,
            "initial_core_fraction_max": INITIAL_CORE_FRACTION_MAX,
            "share_tolerance": SHARE_TOL,
            "geometries": {str(count): [list(center) for center in centers] for count, centers in GEOMETRIES.items()},
            "arm_specs": ARM_SPECS,
            "comparison_observables": list(COMPARISON_OBSERVABLES),
            "binding_gate": {
                "retained_core_fraction": RETAINED_FRACTION,
                "binding_ratio_max": BINDING_RATIO_MAX,
                "near_zero_rule": "exclude binding comparison below retained-core threshold; nonpersistent",
            },
        },
        "rows": rows,
        "comparisons": comparisons,
        "minimum_packet_count": minimum,
        "minimum_packet_count_details": minimum_details,
        "numerical_pass": numerical_pass,
        "verdict": verdict,
        "complete_physical_matter_formation": False,
        "gravitational_capture_established": False,
        "physical_size_map_established": False,
        "packet_count_minimum_established": bool(minimum_details["packet_count_minimum_established"]),
        "library_versions": {"python": platform.python_version(), "torch": torch.__version__},
    }
    write_json(output / "result.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "20260912_matter_formation_packet_count")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    receipt = run_campaign(args.output.resolve())
    print(dynamics.json.dumps({
        "output": str(args.output.resolve()),
        "verdict": receipt["verdict"],
        "minimum_packet_count": receipt["minimum_packet_count"],
        "numerical_pass": receipt["numerical_pass"],
    }))
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
