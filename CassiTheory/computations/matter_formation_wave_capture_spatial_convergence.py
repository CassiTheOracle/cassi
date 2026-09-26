#!/usr/bin/env python3
"""Spatial-convergence runner for the charged-wave capture observables."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
if str(COMPUTATIONS) not in sys.path:
    sys.path.insert(0, str(COMPUTATIONS))

import matter_formation_wave_capture as base  # noqa: E402

SELF = Path(__file__).resolve()
PREREG = COMPUTATIONS / "matter_formation_wave_capture_spatial_convergence_prereg.md"
SPATIAL_VERIFIER_SOURCE = COMPUTATIONS / "verify_matter_formation_wave_capture_spatial_convergence.py"
BASELINE_RECEIPT = ROOT / "runs" / "20260911_matter_formation_wave_capture_v2" / "result.json"
BASELINE_RECEIPT_SHA256 = "c380ecb40c9c3239534e8546389ebfbac312d60e0df4238e7ce38e3a1780a052"
BASELINE_PROTOCOL_SHA256 = "8c8cfb63e2e2ecb56a82864e7ff38468791d00318d5b7ef99317a8aa324747ba"
BASELINE_SOURCE_SHA256 = {
    "computations/matter_formation_wave_capture.py": "31ab56d40524c505d90431b65b0072b998c65635313955d057b4d6d4b8e35b83",
    "computations/matter_formation_wave_capture_v2_prereg.md": "8c8cfb63e2e2ecb56a82864e7ff38468791d00318d5b7ef99317a8aa324747ba",
    "computations/matter_formation_neutral_packets.py": "743e2e75e6b8bc5c5ffd6a75393a49b9da6e5481b9b0b4dee08b040b3f1b901f",
    "computations/matter_formation_radial_cloud.py": "7ed6029e878c6642ab22a6c2526b4a02b2107b1538b751a6c1ea66762f5f6cb4",
    "computations/verify_matter_formation_wave_capture.py": "a7bccd1c20904e43b05cc7559863747df2d8b61dca8ea61b216c29581545da8d",
}
BASELINE_SOURCE_ARCHIVE = BASELINE_RECEIPT.parent / "sources"
SCHEMA = "matter-formation-spatial-convergence-primary-20260911"
DEFAULT_OUTPUT = ROOT / "runs" / "20260911_matter_formation_wave_capture_spatial_convergence_20260911"
GRID_SPECS = {
    "S0": (192, 0.5, 0.015625),
    "S1": (192, 0.25, 0.0078125),
    "S2": (192, 0.125, 0.00390625),
    "D0": (256, 0.5, 0.015625),
}
TARGET_ARMS = ("pair256", "antiphase256")
CONTROL_ARMS = ("single256", "uncoupled256")
DIAGNOSTIC_COMPONENTS = (
    "mediator_potential",
    "carrier_potential",
    "kinetic_energy",
    "radial_gradient",
    "axial_gradient",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_json(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise RuntimeError(f"nonfinite JSON constant {value}: {path}")

    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError, RuntimeError) as error:
        if isinstance(error, RuntimeError):
            raise
        raise RuntimeError(f"invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"object required: {path}")
    return value
def baseline_source_archive_binding() -> bool:
    return all(
        (BASELINE_SOURCE_ARCHIVE / key.replace("/", "__")).is_file()
        and sha256(BASELINE_SOURCE_ARCHIVE / key.replace("/", "__")) == expected
        for key, expected in BASELINE_SOURCE_SHA256.items()
    )



def bind_baseline() -> dict[str, str]:
    if not BASELINE_RECEIPT.is_file():
        raise RuntimeError(f"missing baseline receipt: {BASELINE_RECEIPT}")
    receipt_hash = sha256(BASELINE_RECEIPT)
    if receipt_hash != BASELINE_RECEIPT_SHA256:
        raise RuntimeError("baseline receipt hash mismatch")
    receipt = strict_json(BASELINE_RECEIPT)
    if receipt.get("protocol_sha256") != BASELINE_PROTOCOL_SHA256:
        raise RuntimeError("baseline protocol hash mismatch")
    if receipt.get("source_sha256") != BASELINE_SOURCE_SHA256:
        raise RuntimeError("baseline source hash mismatch")
    if not baseline_source_archive_binding():
        raise RuntimeError("baseline source archive mismatch")
    return {
        "primary_receipt": BASELINE_RECEIPT.relative_to(ROOT).as_posix(),
        "primary_receipt_sha256": receipt_hash,
        "protocol_sha256": BASELINE_PROTOCOL_SHA256,
        "source_sha256": BASELINE_SOURCE_SHA256,
        "source_archive": BASELINE_SOURCE_ARCHIVE.relative_to(ROOT).as_posix(),
    }


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=True, exist_ok=False)
    result: dict[str, str] = {}
    paths = (
        SELF,
        PREREG,
        base.SELF,
        base.NEUTRAL_SOURCE,
        base.CLOUD_SOURCE,
        base.VERIFIER_SOURCE,
        SPATIAL_VERIFIER_SOURCE,
    )
    for path in paths:
        if not path.is_file():
            raise RuntimeError(f"missing declared source: {path}")
        relative = path.relative_to(ROOT).as_posix()
        destination = source_dir / relative.replace("/", "__")
        shutil.copyfile(path, destination)
        result[relative] = sha256(path)
    return result


def assert_diagnostic_components(row: dict[str, Any]) -> None:
    trace = row.get("trace", [])
    if not isinstance(trace, list) or not trace:
        raise RuntimeError(f"missing diagnostic trace: {row.get('grid')}_{row.get('arm')}")
    for sample in trace:
        if not isinstance(sample, dict) or any(
            not base.finite_number(sample.get(name)) for name in ("energy", *DIAGNOSTIC_COMPONENTS)
        ):
            raise RuntimeError(f"invalid diagnostic components: {row.get('grid')}_{row.get('arm')}")
        component_total = sum(float(sample[name]) for name in DIAGNOSTIC_COMPONENTS)
        energy = float(sample["energy"])
        if abs(component_total - energy) > 1.0e-8 * max(1.0, abs(energy)):
            raise RuntimeError(f"diagnostic energy identity mismatch: {row.get('grid')}_{row.get('arm')}")


def max_error(comparison: dict[str, Any]) -> float:
    errors = comparison.get("errors", {})
    values = [float(value) for value in errors.values() if base.finite_number(value)]
    return max(values) if values else float("inf")


def run_campaign(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    baseline = bind_baseline()
    output.mkdir(parents=True)
    source_hashes = snapshot_sources(output)
    primary = output / "primary"
    primary.mkdir()
    rows: list[dict[str, Any]] = []

    for grid_name in ("S0", "S1", "S2"):
        radius, spacing, dt = GRID_SPECS[grid_name]
        arms = TARGET_ARMS if grid_name == "S2" else TARGET_ARMS + CONTROL_ARMS
        for arm in arms:
            row = base.run_row(primary, grid_name, base.CylindricalGrid(radius, spacing), dt, arm)
            assert_diagnostic_components(row)
            rows.append(row)
    radius, spacing, dt = GRID_SPECS["D0"]
    for arm in TARGET_ARMS:
        row = base.run_row(primary, "D0", base.CylindricalGrid(radius, spacing), dt, arm)
        assert_diagnostic_components(row)
        rows.append(row)

    indexed = {(row["grid"], row["arm"]): row for row in rows}
    comparisons: list[dict[str, Any]] = []
    for arm in TARGET_ARMS:
        coarse = base.compare_rows(indexed[("S0", arm)], indexed[("S1", arm)], "space")
        coarse["arm"] = arm
        coarse["level_pair"] = "S0->S1"
        fine = base.compare_rows(indexed[("S1", arm)], indexed[("S2", arm)], "space")
        fine["arm"] = arm
        fine["level_pair"] = "S1->S2"
        fine_error = max_error(fine)
        coarse_error = max_error(coarse)
        fine["monotone_error_pass"] = bool(base.finite_number(fine_error) and base.finite_number(coarse_error) and fine_error <= coarse_error)
        fine["pass"] = bool(fine.get("pass") is True and fine["monotone_error_pass"])
        domain = base.compare_rows(indexed[("S0", arm)], indexed[("D0", arm)], "domain")
        domain["arm"] = arm
        domain["level_pair"] = "S0->D0"
        comparisons.extend((coarse, fine, domain))

    controls = [indexed[(grid, arm)] for grid in ("S0", "S1") for arm in CONTROL_ARMS]
    controls_pass = bool(controls and all(row.get("numerically_qualified") is True for row in controls))
    uncoupled = indexed[("S1", "uncoupled256")]
    uncoupled_control_failed = bool(controls_pass and not uncoupled.get("formation", False))
    target_comparisons = [item for item in comparisons if item["level_pair"] != "S0->S1"]
    spatial_comparison_pass = bool(target_comparisons and all(item.get("pass") is True for item in target_comparisons))
    numerical_pass = bool(spatial_comparison_pass and controls_pass and uncoupled_control_failed)
    verdict = (
        "SPATIAL CONVERGENCE ESTABLISHED for the declared wave-capture observables"
        if numerical_pass
        else "SPATIAL CONVERGENCE DOES NOT EMERGE in the declared resolution ladder"
    )
    receipt = {
        "schema": SCHEMA,
        "protocol_sha256": sha256(PREREG),
        "source_sha256": source_hashes,
        "baseline": baseline,
        "constants": {
            "a": base.A,
            "c_psi": base.CPSI,
            "u_rho": base.URHO,
            "u_C": base.UC,
            "k_Cx": base.K,
            "h_C": base.HC,
            "B": base.B,
            "omega_inf": base.OMEGA_INF,
            "v_star": base.VSTAR,
        },
        "rows": rows,
        "comparisons": comparisons,
        "controls_pass": controls_pass,
        "uncoupled_control_failed": uncoupled_control_failed,
        "spatial_comparison_pass": spatial_comparison_pass,
        "numerical_pass": numerical_pass,
        "verdict": verdict,
        "complete_physical_matter_formation": False,
        "gravitational_capture_established": False,
        "physical_size_map_established": False,
        "packet_count_minimum_established": False,
    }
    base.write_json(output / "result.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return base.run_smoke()
    receipt = run_campaign(args.output.resolve())
    print(json.dumps({"output": str(args.output.resolve()), "verdict": receipt["verdict"], "numerical_pass": receipt["numerical_pass"]}))
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
