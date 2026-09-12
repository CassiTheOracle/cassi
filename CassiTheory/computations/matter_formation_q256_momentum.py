#!/usr/bin/env python3
"""Run the preregistered Q=256 incoming-momentum formation probe."""
from __future__ import annotations

import argparse
import math
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
if str(COMPUTATIONS) not in sys.path:
    sys.path.insert(0, str(COMPUTATIONS))

import matter_formation_wave_capture as dynamics  # noqa: E402
from matter_formation_q256_momentum_spec import (  # noqa: E402
    ARM_SPECS,
    ARMS,
    COUPLED_CANDIDATES,
    CORE_RADIUS,
    INITIAL_CORE_FRACTION_MAX,
    INITIAL_OVERLAP_MAX,
    LATE_START,
    NOMINAL_PACKET_CHARGE,
    OMEGA_OFFSET_SQUARED,
    ROBUST_COMPARISON_OBSERVABLES,
    SAMPLE_DT,
    SNAPSHOT_TIMES,
    T_FINAL,
    TOTAL_CHARGE,
    WAVE_NUMBERS,
    WIDTH,
)

SELF = Path(__file__).resolve()
PREREG = COMPUTATIONS / "matter_formation_q256_momentum_prereg.md"
SPEC_SOURCE = COMPUTATIONS / "matter_formation_q256_momentum_spec.py"
BASE_SOURCE = COMPUTATIONS / "matter_formation_wave_capture.py"
NEUTRAL_SOURCE = COMPUTATIONS / "matter_formation_neutral_packets.py"
CLOUD_SOURCE = COMPUTATIONS / "matter_formation_radial_cloud.py"
INDEPENDENT_ACTION_SOURCE = COMPUTATIONS / "verify_matter_formation_wave_capture.py"
VERIFIER_SOURCE = COMPUTATIONS / "verify_matter_formation_q256_momentum.py"
SCHEMA = "matter-formation-q256-packet-momentum-primary-v1"


def assemble_primary(grid: Any, arm: str) -> tuple[torch.Tensor, torch.Tensor, float, dict[str, Any]]:
    """Assemble the Q=256 preparation from the frozen declarative schedule."""
    config = ARM_SPECS[arm]
    pair = bool(config["pair"])
    uncoupled = bool(config["uncoupled"])
    center = float(config["center"])
    wave_number = float(config["wave_number"])
    phase_sign = 1.0
    omega = dynamics.OMEGA_INF if not pair else math.sqrt(
        dynamics.OMEGA_INF**2 + OMEGA_OFFSET_SQUARED * wave_number**2
    )
    zeta = grid.axial
    if config["kind"] == "single":
        envelope = torch.exp(-(grid.r2 + zeta[None, :].square()) / (2.0 * WIDTH**2))
        complex_field = envelope.to(dtype=torch.complex128)
        centers = (0.0,)
    else:
        envelope_right = torch.exp(-(grid.r2 + (zeta[None, :] + center).square()) / (2.0 * WIDTH**2))
        envelope_left = torch.exp(-(grid.r2 + (zeta[None, :] - center).square()) / (2.0 * WIDTH**2))
        phase_right = phase_sign * wave_number * (zeta[None, :] + center)
        phase_left = -phase_sign * wave_number * (zeta[None, :] - center)
        sign_left = -1.0 if config["kind"] == "antiphase" else 1.0
        complex_field = envelope_right * torch.exp(1j * phase_right) + sign_left * envelope_left * torch.exp(1j * phase_left)
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
        a = torch.exp(-(grid.r2 + (zeta[None, :] + center).square()) / (2.0 * WIDTH**2))
        b = torch.exp(-(grid.r2 + (zeta[None, :] - center).square()) / (2.0 * WIDTH**2))
        overlap = float(torch.abs(torch.sum(grid.volume * a * b)) / torch.sqrt(torch.sum(grid.volume * a.square()) * torch.sum(grid.volume * b.square())))
    rho = 2.0 * dynamics.A * omega * (q[1].square() + q[2].square())
    distance = torch.sqrt(grid.r2 + grid.axial[None, :].square())
    initial_core = float((grid.volume * rho * (distance < CORE_RADIUS)).sum()) / TOTAL_CHARGE
    metadata: dict[str, Any] = {
        "charge": TOTAL_CHARGE,
        "nominal_packet_charge": NOMINAL_PACKET_CHARGE if pair else None,
        "center": center,
        "omega": omega,
        "wave_number": wave_number,
        "phase_sign": phase_sign,
        "pair": pair,
        "uncoupled": uncoupled,
        "initial_overlap": overlap,
        "initial_core_fraction": initial_core,
        "centers": list(centers),
        "initially_unbound": bool(overlap <= INITIAL_OVERLAP_MAX and initial_core <= INITIAL_CORE_FRACTION_MAX) if pair else True,
    }
    return q, v, (0.0 if uncoupled else dynamics.HC), metadata


def compare_rows_robust(left: dict[str, Any], right: dict[str, Any], kind: str) -> dict[str, Any]:
    key_left = left["grid"] + "_" + left["arm"]
    key_right = right["grid"] + "_" + right["arm"]
    result: dict[str, Any] = {
        "kind": kind,
        "left": key_left,
        "right": key_right,
        "errors": {},
        "pass": False,
        "comparison_observables": list(ROBUST_COMPARISON_OBSERVABLES),
    }
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
    if any(not dynamics.finite_number(row.get(name)) for row in left_late + right_late for name in dynamics.REQUIRED_OBSERVABLES):
        result["reason"] = "nonfinite required observable"
        return result
    initial_values = (
        left.get("initial", {}).get("energy"),
        right.get("initial", {}).get("energy"),
        left.get("initial", {}).get("charge"),
        right.get("initial", {}).get("charge"),
    )
    if not all(dynamics.finite_number(value) for value in initial_values):
        result["reason"] = "nonfinite initial comparison scale"
        return result
    left_means = {name: float(np.mean([row[name] for row in left_late])) for name in ROBUST_COMPARISON_OBSERVABLES}
    right_means = {name: float(np.mean([row[name] for row in right_late])) for name in ROBUST_COMPARISON_OBSERVABLES}
    scales = {
        "energy": max(1.0, abs(float(left["initial"]["energy"])), abs(float(right["initial"]["energy"]))),
        "charge": max(1.0, abs(float(left["initial"]["charge"])), abs(float(right["initial"]["charge"]))),
        "core_fraction": 1.0,
        "core_rms": dynamics.CORE_RADIUS,
        "core_energy": max(1.0, abs(float(left["initial"]["energy"])), abs(float(right["initial"]["energy"]))),
        "shell_energy_fraction": 1.0,
    }
    errors = {name: abs(left_means[name] - right_means[name]) / scales[name] for name in ROBUST_COMPARISON_OBSERVABLES}
    result["errors"] = errors
    result["pass"] = bool(all(dynamics.finite_number(value) for value in errors.values()) and max(errors.values()) < dynamics.COMPARISON_TOL)
    return result


def sha256(path: Path) -> str:
    return dynamics.sha256(path)


def write_json(path: Path, value: dict[str, Any]) -> None:
    dynamics.write_json(path, value)


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=True, exist_ok=False)
    result: dict[str, str] = {}
    for path in (SELF, PREREG, SPEC_SOURCE, BASE_SOURCE, NEUTRAL_SOURCE, CLOUD_SOURCE, INDEPENDENT_ACTION_SOURCE, VERIFIER_SOURCE):
        relative = path.relative_to(ROOT).as_posix()
        destination = source_dir / relative.replace("/", "__")
        shutil.copyfile(path, destination)
        result[relative] = sha256(path)
    return result


def run_smoke() -> int:
    grid = dynamics.CylindricalGrid(32, 1.0)
    records: list[dict[str, Any]] = []
    for arm in ARMS:
        q, v, coupling, metadata = assemble_primary(grid, arm)
        rho = -2.0 * dynamics.A * (q[1] * v[2] - q[2] * v[1])
        charge = float((grid.volume * rho).sum())
        records.append({"arm": arm, "charge": charge, "wave_number": metadata["wave_number"], "overlap": metadata["initial_overlap"]})
        assert abs(charge - TOTAL_CHARGE) / TOTAL_CHARGE < 1.0e-12
        assert dynamics.finite(metadata)
        del q, v
    print(dynamics.json.dumps({"smoke": "PASS", "arms": records}))
    return 0


def run_campaign(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True)
    source_hashes = snapshot_sources(output)
    primary = output / "primary"
    primary.mkdir()
    dynamics.initial_state = assemble_primary
    rows: list[dict[str, Any]] = []
    for grid_name in ("S1", "S2", "T1"):
        radius, spacing, dt = {"S1": (192, 0.25, 1.0 / 128.0), "S2": (192, 0.125, 1.0 / 256.0), "T1": (192, 0.25, 1.0 / 256.0)}[grid_name]
        for arm in ARMS:
            rows.append(dynamics.run_row(primary, grid_name, dynamics.CylindricalGrid(radius, spacing), dt, arm))
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    indexed = {(row["grid"], row["arm"]): row for row in rows}
    comparisons: list[dict[str, Any]] = []
    for arm in ARMS:
        comparisons.append(compare_rows_robust(indexed[("S1", arm)], indexed[("S2", arm)], "space"))
        comparisons.append(compare_rows_robust(indexed[("S1", arm)], indexed[("T1", arm)], "time"))
    coupled_candidates = [indexed[("S1", arm)] for arm in COUPLED_CANDIDATES if indexed[("S1", arm)]["formation"]]
    fully_compared: list[str] = []
    for candidate in coupled_candidates:
        arm = candidate["arm"]
        required = [item for item in comparisons if item["left"] in {f"S1_{arm}", f"S2_{arm}", f"T1_{arm}"} or item["right"] in {f"S1_{arm}", f"S2_{arm}", f"T1_{arm}"}]
        if len(required) == 2 and all(item["pass"] for item in required) and all(indexed[(grid, arm)]["formation"] for grid in ("S1", "S2", "T1")):
            fully_compared.append(f"S1_{arm}")
    uncoupled = indexed[("S1", "uncoupled_k05")]
    uncoupled_failed = bool(uncoupled["numerically_qualified"] and not uncoupled["formation"])
    comparison_pass = bool(len(comparisons) == len(ARMS) * 2 and all(item["pass"] for item in comparisons))
    if not comparison_pass:
        verdict = "INCONCLUSIVE"
    elif fully_compared and uncoupled_failed:
        verdict = "EMERGES—conditional Q=256 bound remnant in the declared incoming-momentum basin"
    else:
        verdict = "DOES NOT EMERGE in the specified Q=256 packet-momentum calculation"
    receipt = {
        "schema": SCHEMA,
        "protocol_sha256": sha256(PREREG),
        "source_sha256": source_hashes,
        "constants": {"a": dynamics.A, "c_psi": dynamics.CPSI, "u_rho": dynamics.URHO, "u_C": dynamics.UC, "k_Cx": dynamics.K, "h_C": dynamics.HC, "B": dynamics.B, "omega_inf": dynamics.OMEGA_INF, "v_star": dynamics.VSTAR},
        "preparation": {"total_charge": TOTAL_CHARGE, "nominal_packet_charge": NOMINAL_PACKET_CHARGE, "width": WIDTH, "center": 12.0, "wave_numbers": list(WAVE_NUMBERS), "comparison_observables": list(ROBUST_COMPARISON_OBSERVABLES), "omega_offset_squared": OMEGA_OFFSET_SQUARED},
        "rows": rows,
        "comparisons": comparisons,
        "coupled_candidates": [row["grid"] + "_" + row["arm"] for row in coupled_candidates],
        "fully_compared_candidates": fully_compared,
        "uncoupled_control_failed": uncoupled_failed,
        "numerical_pass": comparison_pass,
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
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "20260912_matter_formation_q256_momentum")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    receipt = run_campaign(args.output.resolve())
    print(dynamics.json.dumps({"output": str(args.output.resolve()), "verdict": receipt["verdict"], "fully_compared_candidates": receipt["fully_compared_candidates"]}))
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
