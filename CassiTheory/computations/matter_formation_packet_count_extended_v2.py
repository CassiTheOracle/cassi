#!/usr/bin/env python3
"""Run the frozen axisymmetric four-to-six packet formation extension."""
from __future__ import annotations

import argparse
import math
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
if str(COMPUTATIONS) not in sys.path:
    sys.path.insert(0, str(COMPUTATIONS))

import matter_formation_packet_count as lower  # noqa: E402
import matter_formation_wave_capture as dynamics  # noqa: E402
from matter_formation_neutral_packets import CylindricalGrid  # noqa: E402
from matter_formation_packet_count_extended_spec import (  # noqa: E402
    ARM_SPECS,
    ARMS,
    CANDIDATE_ARMS,
    COMPARISON_OBSERVABLES,
    CONTROL_ARMS,
    GEOMETRIES,
    GRID_SPECS,
    INITIAL_CORE_FRACTION_MAX,
    INITIAL_OVERLAP_MAX,
    LATE_START,
    LOWER_PRIMARY_RECEIPT_SHA256,
    LOWER_VERIFICATION_RECEIPT_SHA256,
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
PREREG = COMPUTATIONS / "matter_formation_packet_count_extended_v2_prereg.md"
SPEC_SOURCE = COMPUTATIONS / "matter_formation_packet_count_extended_spec.py"
VERIFIER_SOURCE = COMPUTATIONS / "verify_matter_formation_packet_count_extended_v2.py"
BASE_PRIMARY_SOURCE = COMPUTATIONS / "matter_formation_packet_count.py"
BASE_PREREG = COMPUTATIONS / "matter_formation_packet_count_prereg.md"
BASE_SPEC = COMPUTATIONS / "matter_formation_packet_count_spec.py"
BASE_VERIFIER = COMPUTATIONS / "verify_matter_formation_packet_count.py"
NEUTRAL_SOURCE = COMPUTATIONS / "matter_formation_neutral_packets.py"
CLOUD_SOURCE = COMPUTATIONS / "matter_formation_radial_cloud.py"
WAVE_SOURCE = COMPUTATIONS / "matter_formation_wave_capture.py"
INDEPENDENT_WAVE_SOURCE = COMPUTATIONS / "verify_matter_formation_wave_capture.py"
SCHEMA = "matter-formation-packet-count-extended-v2-primary-v1"


def sha256(path: Path) -> str:
    return dynamics.sha256(path)


def finite_number(value: Any) -> bool:
    return dynamics.finite_number(value)


def write_json(path: Path, value: dict[str, Any]) -> None:
    dynamics.write_json(path, value)


def packet_directions(count: int, phase_sign: float) -> tuple[tuple[float, float], ...]:
    result = []
    for radial, axial in GEOMETRIES[count]:
        norm = math.hypot(float(radial), float(axial))
        if norm <= 0.0:
            raise RuntimeError("moving packet centre cannot be at the origin")
        result.append((phase_sign * -float(radial) / norm, phase_sign * -float(axial) / norm))
    return tuple(result)


def assemble_primary(grid: CylindricalGrid, arm: str) -> tuple[torch.Tensor, torch.Tensor, float, dict[str, Any]]:
    config = ARM_SPECS[arm]
    count = int(config["count"])
    centers = GEOMETRIES[count]
    phase_sign = float(config["phase_sign"])
    omega = math.sqrt(dynamics.OMEGA_INF**2 + 8.0 * WAVE_NUMBER**2)
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
    norm_value = float(torch.sum(grid.volume * (complex_field.real.square() + complex_field.imag.square())))
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
            pairwise_overlaps.append(
                float(
                    torch.abs(torch.sum(grid.volume * envelopes[index] * envelopes[other]))
                    / math.sqrt(integrals[index] * integrals[other])
                )
            )
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
        "wave_number": WAVE_NUMBER,
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
            max(pairwise_overlaps, default=math.inf) <= INITIAL_OVERLAP_MAX
            and initial_core_fraction <= INITIAL_CORE_FRACTION_MAX
        ),
    }
    return q, v, (dynamics.HC if bool(config["coupled"]) else 0.0), metadata


def patch_lower_runtime() -> None:
    """Reuse only the lower row integrator after replacing every schedule global."""
    lower.assemble_primary = assemble_primary
    lower.ARMS = ARMS
    lower.ARM_SPECS = ARM_SPECS
    lower.GRID_SPECS = GRID_SPECS
    lower.GEOMETRIES = GEOMETRIES
    lower.COMPARISON_OBSERVABLES = COMPARISON_OBSERVABLES
    lower.INITIAL_OVERLAP_MAX = INITIAL_OVERLAP_MAX
    lower.INITIAL_CORE_FRACTION_MAX = INITIAL_CORE_FRACTION_MAX
    lower.LATE_START = LATE_START
    lower.RETAINED_FRACTION = RETAINED_FRACTION
    lower.BINDING_RATIO_MAX = BINDING_RATIO_MAX
    lower.SAMPLE_DT = SAMPLE_DT
    lower.SNAPSHOTS_TIMES = SNAPSHOT_TIMES
    lower.T_FINAL = T_FINAL
    lower.TOTAL_CHARGE = TOTAL_CHARGE
    lower.R0 = R0
    lower.WIDTH = WIDTH
    lower.WAVE_NUMBER = WAVE_NUMBER
    lower.SHARE_TOL = SHARE_TOL


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=True, exist_ok=False)
    paths = (
        SELF,
        PREREG,
        SPEC_SOURCE,
        VERIFIER_SOURCE,
        BASE_PRIMARY_SOURCE,
        BASE_PREREG,
        BASE_SPEC,
        BASE_VERIFIER,
        NEUTRAL_SOURCE,
        CLOUD_SOURCE,
        WAVE_SOURCE,
        INDEPENDENT_WAVE_SOURCE,
    )
    result: dict[str, str] = {}
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        destination = source_dir / relative.replace("/", "__")
        shutil.copyfile(path, destination)
        result[relative] = sha256(path)
    return result


def lower_lineage_context() -> dict[str, Any]:
    primary_path = ROOT / "runs" / "20260912_matter_formation_packet_count" / "result.json"
    verification_path = primary_path.parent / "verification.json"
    observed_primary = sha256(primary_path) if primary_path.is_file() else None
    observed_verification = sha256(verification_path) if verification_path.is_file() else None
    return {
        "historical_primary_expected": LOWER_PRIMARY_RECEIPT_SHA256,
        "historical_verification_expected": LOWER_VERIFICATION_RECEIPT_SHA256,
        "observed_primary": observed_primary,
        "observed_verification": observed_verification,
        "historical_lineage_accepted": bool(
            observed_primary == LOWER_PRIMARY_RECEIPT_SHA256
            and observed_verification == LOWER_VERIFICATION_RECEIPT_SHA256
        ),
        "use": "diagnostic_context_only",
    }


def first_new_forming_count(indexed: dict[tuple[str, str], dict[str, Any]], numerical_pass: bool) -> int | None:
    if not numerical_pass:
        return None
    for count in (4, 5, 6):
        arm = f"n{count}_inward"
        rows = [indexed.get((grid_name, arm)) for grid_name in GRID_SPECS]
        if all(isinstance(row, dict) and row.get("formation") is True for row in rows):
            return count
    return None


def run_smoke() -> int:
    grid = CylindricalGrid(48, 1.0)
    records = []
    for arm in ARMS:
        q, v, coupling, metadata = assemble_primary(grid, arm)
        charge = float((grid.volume * (-2.0 * dynamics.A * (q[1] * v[2] - q[2] * v[1]))).sum())
        assert abs(charge - TOTAL_CHARGE) / TOTAL_CHARGE < SHARE_TOL
        assert metadata["packet_count"] == ARM_SPECS[arm]["count"]
        assert metadata["core_radius"] == dynamics.CORE_RADIUS
        records.append({"arm": arm, "packet_count": metadata["packet_count"], "charge": charge, "coupling": coupling})
    print(dynamics.json.dumps({"smoke": "PASS", "arms": records}))
    return 0


def run_campaign(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    patch_lower_runtime()
    output.mkdir(parents=True)
    source_hashes = snapshot_sources(output)
    primary = output / "primary"
    primary.mkdir()
    rows: list[dict[str, Any]] = []
    for grid_name, (radius, spacing, dt) in GRID_SPECS.items():
        grid = CylindricalGrid(radius, spacing)
        for arm in ARMS:
            rows.append(lower.run_row(primary, grid_name, grid, dt, arm))
    indexed = {(row["grid"], row["arm"]): row for row in rows}
    comparisons = []
    for arm in ARMS:
        comparisons.append(lower.compare_rows_robust(indexed[("G0", arm)], indexed[("G1", arm)], "space"))
        comparisons.append(lower.compare_rows_robust(indexed[("G0", arm)], indexed[("T1", arm)], "time"))
    comparison_pass = bool(len(comparisons) == 2 * len(ARMS) and all(item.get("pass") is True for item in comparisons))
    row_qualification_pass = bool(all(row.get("numerically_qualified") is True for row in rows))
    numerical_pass = bool(comparison_pass and row_qualification_pass)
    first_count = first_new_forming_count(indexed, numerical_pass)
    if not numerical_pass:
        verdict = "INCONCLUSIVE"
    elif first_count is not None:
        verdict = f"EMERGES—conditional N={first_count} ring-family formation in the four-to-six extension"
    else:
        verdict = "DOES NOT EMERGE in the specified four-to-six ring-family extension"
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
        "lower_lineage_context": lower_lineage_context(),
        "rows": rows,
        "comparisons": comparisons,
        "first_new_forming_count": first_count,
        "minimum_packet_count": None,
        "packet_count_minimum_established": False,
        "comparison_pass": comparison_pass,
        "row_qualification_pass": row_qualification_pass,
        "numerical_pass": numerical_pass,
        "verdict": verdict,
        "complete_physical_matter_formation": False,
        "gravitational_capture_established": False,
        "physical_size_map_established": False,
        "library_versions": {"python": platform.python_version(), "torch": torch.__version__},
    }
    write_json(output / "result.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "20260912_matter_formation_packet_count_extended_v2")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    receipt = run_campaign(args.output.resolve())
    print(dynamics.json.dumps({
        "output": str(args.output.resolve()),
        "verdict": receipt["verdict"],
        "first_new_forming_count": receipt["first_new_forming_count"],
        "minimum_packet_count": receipt["minimum_packet_count"],
        "numerical_pass": receipt["numerical_pass"],
    }), flush=True)
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
