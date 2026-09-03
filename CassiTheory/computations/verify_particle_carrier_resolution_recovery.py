#!/usr/bin/env python3
"""Independently verify the carrier spatial-resolution recovery campaign."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

import numpy as np

import verify_particle_carrier_direct_coordinate as direct_verify  # pyright: ignore[reportMissingImports]


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runs" / "20260902_particle_carrier_resolution_recovery"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
RESULTS_PATH = RUN_DIR / "results.json"
VERIFICATION_PATH = RUN_DIR / "verification.json"
MANIFEST_PATH = ROOT / "computations" / "particle_carrier_resolution_recovery_manifest.json"
SOURCE_DIR = ROOT / "runs" / "20260902_particle_carrier_direct_coordinate_v2"
SOURCE_RESULTS = SOURCE_DIR / "results.json"
SOURCE_VERIFICATION = SOURCE_DIR / "verification.json"
SOURCE_RESULTS_SHA256 = "59f39d6e565ab24faab705094ea5ee1001d7ab3939d8a923db091dc903e44c73"
SOURCE_VERIFICATION_SHA256 = "b858d05df7db577896f6f5ff325efba2922d90cc9359c9a7264631ad1c314629"
SOURCE_VERDICT = "EMERGES—FINITE-GRID LOCALIZED RETAINED BRANCH ONLY"
H_C = 2.9598260763447164
MAX_BLOCKS = 8
NEW_GRIDS = {
    "X1": (4.0, 25),
    "X2": (4.0, 29),
}
SOURCE_LEVELS = {
    "P": {
        "R": 4.0,
        "N": 17,
        "dx": 0.5,
        "artifact": "fields_primary_half_reference_block01.npz",
        "artifact_sha256": "c32beb4ee7bc7746a4fc18b63bc04ef7db12cc18505c9bee8ce2d298ddc25837",
    },
    "H": {
        "R": 4.0,
        "N": 21,
        "dx": 0.4,
        "artifact": "fields_comparison_H_block01.npz",
        "artifact_sha256": "8aa65f3c08167c902660f9e8d09c0ce921d43c7f0af152b31aae79db6875810f",
    },
}
COMPARISON_PROTOCOL = {
    "energy_relative_limit": 0.05,
    "core_length_absolute_limit": 0.75,
    "omega_absolute_limit": 0.10,
    "radius_relative_limit": 0.10,
    "relative_denominator_floor": 1.0e-30,
    "energy_contraction": "strict_twice",
}
VERDICTS = {
    "inconclusive": "INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION",
    "no_refined": "DOES NOT EMERGE—NO QUALIFIED REFINED-GRID BRANCH",
    "finite_grid": "EMERGES—FINITE-GRID LOCALIZED RETAINED BRANCH ONLY",
    "resolved": "EMERGES—THREE-LEVEL RESOLUTION-CONSISTENT LOCALIZED RETAINED BRANCH",
}
PARAMETERIZATION = "direct_shell_masked_fixed_charge"
ROUNDTRIP_TOLERANCE = 5.0e-12
NEGATIVE_NORM_LIMIT = 1.0e-12
BASE = direct_verify.prior.independent
REQUIRED_HASH_PATHS = (
    "computations/particle-carrier-resolution-recovery-prereg.md",
    "computations/particle_carrier_resolution_recovery.py",
    "computations/verify_particle_carrier_resolution_recovery.py",
    "computations/particle-carrier-direct-coordinate-prereg.md",
    "computations/particle-carrier-direct-coordinate-execution-amendment.md",
    "computations/particle-carrier-direct-coordinate-receipt-binding.md",
    "computations/particle_carrier_direct_coordinate.py",
    "computations/verify_particle_carrier_direct_coordinate.py",
    "computations/particle_carrier_direct_coordinate_manifest.json",
    "computations/particle_carrier_localization.py",
    "computations/verify_particle_carrier_localization.py",
    "computations/particle_stationary_bvp.py",
    "computations/particle_stationary_q2_recovery_v2.py",
    "computations/verify_particle_stationary_q2_recovery_v2.py",
    "runs/20260902_particle_carrier_direct_coordinate_v2/results.json",
    "runs/20260902_particle_carrier_direct_coordinate_v2/verification.json",
    "runs/20260902_particle_carrier_direct_coordinate_v2/fields_primary_half_reference_block01.npz",
    "runs/20260902_particle_carrier_direct_coordinate_v2/fields_comparison_H_block01.npz",
)




def sha256_file(path: Path) -> str:
    return direct_verify.prior.sha256_file(path)


def read_json(path: Path) -> dict[str, Any]:
    return direct_verify.prior.read_json(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def coefficient_vector() -> dict[str, float]:
    return direct_verify.coefficient_vector(H_C)


def expected_source_arm(results: Mapping[str, Any], family: str) -> Mapping[str, Any]:
    if family == "P":
        return results["primary_scan"][0]
    return results["comparison_arms"]["H"]


def direct_roundtrip(fields: Mapping[str, np.ndarray]) -> dict[str, Any]:
    c = fields["c"]
    x = fields["x"]
    dx = float(x[1] - x[0])
    charge = float(np.sum(c * c) * dx**3)
    normalized = math.sqrt(4.0) * c / math.sqrt(charge)
    maximum = float(np.max(np.abs(normalized - c)))
    return {
        "charge": charge,
        "maximum_absolute_infimum": maximum,
        "tolerance": ROUNDTRIP_TOLERANCE,
        "pass": maximum <= ROUNDTRIP_TOLERANCE,
    }


def verify_manifest(out: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    try:
        manifest = read_json(MANIFEST_PATH)
    except Exception as error:
        BASE.mismatch(out, "manifest", "readable JSON", repr(error), "read")
        return None, "MISSING"
    manifest_sha256 = sha256_file(MANIFEST_PATH)
    BASE.compare_tree(
        out,
        "manifest.schema",
        manifest.get("schema"),
        "cassi.particle-carrier-resolution-recovery.manifest.v1",
    )
    hashes = manifest.get("sha256")
    if not isinstance(hashes, dict):
        BASE.mismatch(out, "manifest.sha256", "object", hashes, "schema")
    elif set(hashes) != set(REQUIRED_HASH_PATHS):
        BASE.mismatch(
            out,
            "manifest.sha256.keys",
            sorted(REQUIRED_HASH_PATHS),
            sorted(hashes),
            "exact",
        )
    else:
        for relative, expected in hashes.items():
            path = ROOT / relative
            actual = sha256_file(path) if path.is_file() else "MISSING"
            BASE.compare_tree(out, f"manifest.sha256.{relative}", actual, expected)
    expected_source = {
        "results": SOURCE_RESULTS.relative_to(ROOT).as_posix(),
        "results_sha256": SOURCE_RESULTS_SHA256,
        "verification": SOURCE_VERIFICATION.relative_to(ROOT).as_posix(),
        "verification_sha256": SOURCE_VERIFICATION_SHA256,
        "source_verification_pass": True,
        "source_verdict": SOURCE_VERDICT,
        "levels": SOURCE_LEVELS,
    }
    BASE.compare_tree(out, "manifest.source", manifest.get("source"), expected_source)
    BASE.compare_tree(
        out,
        "manifest.fixed_coefficients",
        manifest.get("fixed_coefficients"),
        direct_verify.prior.FIXED_COEFFICIENTS,
    )
    BASE.compare_tree(out, "manifest.h_C", manifest.get("h_C"), H_C)
    BASE.compare_tree(
        out,
        "manifest.parameterization",
        manifest.get("parameterization"),
        {
            "name": PARAMETERIZATION,
            "roundtrip_tolerance": ROUNDTRIP_TOLERANCE,
            "negative_norm_fraction_limit": NEGATIVE_NORM_LIMIT,
        },
    )
    expected_grids = {
        family: {"R": r_box, "N": n, "dx": 2.0 * r_box / (n - 1)}
        for family, (r_box, n) in NEW_GRIDS.items()
    }
    BASE.compare_tree(out, "manifest.new_grids", manifest.get("new_grids"), expected_grids)
    BASE.compare_tree(
        out,
        "manifest.schedule",
        manifest.get("schedule"),
        {
            "order": list(NEW_GRIDS),
            "max_blocks": MAX_BLOCKS,
            "initial_optimizer": {"adam_steps": 800, "lbfgs_max_iter": 120},
            "continuation": direct_verify.prior.independent.CONTINUATION,
        },
    )
    BASE.compare_tree(
        out, "manifest.comparison", manifest.get("comparison"), COMPARISON_PROTOCOL
    )
    return manifest, manifest_sha256


def verify_sources(
    out: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    actual_result_hash = sha256_file(SOURCE_RESULTS) if SOURCE_RESULTS.is_file() else "MISSING"
    actual_verification_hash = (
        sha256_file(SOURCE_VERIFICATION) if SOURCE_VERIFICATION.is_file() else "MISSING"
    )
    BASE.compare_tree(out, "source.results_sha256", actual_result_hash, SOURCE_RESULTS_SHA256)
    BASE.compare_tree(
        out,
        "source.verification_sha256",
        actual_verification_hash,
        SOURCE_VERIFICATION_SHA256,
    )
    try:
        results = read_json(SOURCE_RESULTS)
        verification = read_json(SOURCE_VERIFICATION)
    except Exception as error:
        BASE.mismatch(out, "source.receipts", "readable JSON", repr(error), "read")
        return {}, {}
    BASE.compare_tree(out, "source.results.status", results.get("status"), "complete")
    BASE.compare_tree(
        out, "source.results.primary_verdict", results.get("primary_verdict"), SOURCE_VERDICT
    )
    BASE.compare_tree(out, "source.verification.pass", verification.get("pass"), True)
    BASE.compare_tree(out, "source.verification.mismatches", verification.get("mismatches"), [])

    receipts: dict[str, dict[str, Any]] = {}
    roundtrips: dict[str, dict[str, Any]] = {}
    for family, expected in SOURCE_LEVELS.items():
        arm = expected_source_arm(results, family)
        BASE.compare_tree(out, f"source.{family}.h_C", arm.get("h_C"), H_C)
        BASE.compare_tree(
            out,
            f"source.{family}.terminal_artifact",
            arm.get("terminal_artifact"),
            expected["artifact"],
        )
        BASE.compare_tree(
            out,
            f"source.{family}.terminal_artifact_sha256",
            arm.get("terminal_artifact_sha256"),
            expected["artifact_sha256"],
        )
        artifact_path = SOURCE_DIR / expected["artifact"]
        actual_hash = sha256_file(artifact_path) if artifact_path.is_file() else "MISSING"
        BASE.compare_tree(out, f"source.{family}.artifact_sha256", actual_hash, expected["artifact_sha256"])
        fields = BASE.load_fields(artifact_path, family, out, f"source.{family}.artifact")
        if fields is None:
            continue
        fresh = direct_verify.prior.recompute_diagnostics(fields, H_C)
        BASE.compare_tree(
            out,
            f"source.{family}.diagnostics",
            fresh,
            direct_verify.physical_diagnostics_only(arm.get("diagnostics", {})),
        )
        quality = direct_verify.prior.quality_checks(fresh)
        localization = direct_verify.prior.localization_checks(fresh, 2.0)
        nodeless = direct_verify.negative_norm_receipt(fields)
        qualified = all(quality.values())
        selected = qualified and all(localization.values()) and bool(nodeless["pass"])
        receipt = {
            "family": family,
            "R": expected["R"],
            "N": expected["N"],
            "dx": expected["dx"],
            "h_C": H_C,
            "terminal_block": arm["terminal_block"],
            "terminal_artifact": expected["artifact"],
            "terminal_artifact_sha256": actual_hash,
            "diagnostics": fresh,
            "quality_checks": quality,
            "localization_checks": localization,
            "nodeless_check": nodeless,
            "numerically_qualified": qualified,
            "nodeless_localized_and_retained": selected,
        }
        receipts[family] = receipt
        roundtrips[family] = direct_roundtrip(fields)
        BASE.compare_tree(out, f"source.{family}.quality_checks", arm.get("quality_checks"), quality)
        BASE.compare_tree(
            out, f"source.{family}.localization_checks", arm.get("localization_checks"), localization
        )
        BASE.compare_tree(out, f"source.{family}.nodeless_check", arm.get("nodeless_check"), nodeless)
        BASE.compare_tree(out, f"source.{family}.numerically_qualified", arm.get("numerically_qualified"), qualified)
        BASE.compare_tree(
            out,
            f"source.{family}.nodeless_localized_and_retained",
            arm.get("nodeless_localized_and_retained"),
            selected,
        )
        BASE.compare_tree(out, f"source.{family}.direct_roundtrip.pass", roundtrips[family]["pass"], True)
    return receipts, roundtrips


def relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(
        abs(left), abs(right), COMPARISON_PROTOCOL["relative_denominator_floor"]
    )


def comparison_metrics(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> dict[str, Any]:
    left_values = left["diagnostics"]
    right_values = right["diagnostics"]
    result = {
        "energy_relative_difference": relative_difference(
            left_values["physical_energy"], right_values["physical_energy"]
        ),
        "core_length_absolute_difference": abs(
            left_values["core_length"] - right_values["core_length"]
        ),
        "omega_absolute_difference": abs(
            left_values["omega_c"] - right_values["omega_c"]
        ),
        "radius_relative_difference": relative_difference(
            left_values["carrier_radius"], right_values["carrier_radius"]
        ),
    }
    result["pass"] = (
        result["energy_relative_difference"]
        <= COMPARISON_PROTOCOL["energy_relative_limit"]
        and result["core_length_absolute_difference"]
        <= COMPARISON_PROTOCOL["core_length_absolute_limit"]
        and result["omega_absolute_difference"]
        <= COMPARISON_PROTOCOL["omega_absolute_limit"]
        and result["radius_relative_difference"]
        <= COMPARISON_PROTOCOL["radius_relative_limit"]
    )
    return result


def validate_reconstruction(
    out: list[dict[str, Any]], path: str, receipt: Any
) -> None:
    if not isinstance(receipt, dict):
        BASE.mismatch(out, path, "object", receipt, "schema")
        return
    BASE.compare_tree(out, f"{path}.parameterization", receipt.get("parameterization"), PARAMETERIZATION)
    BASE.compare_tree(out, f"{path}.basin", receipt.get("basin"), "separated_core")
    BASE.compare_tree(out, f"{path}.roundtrip_tolerance", receipt.get("roundtrip_tolerance"), ROUNDTRIP_TOLERANCE)
    BASE.compare_tree(out, f"{path}.roundtrip_pass", receipt.get("roundtrip_pass"), True)
    BASE.compare_tree(
        out,
        f"{path}.absolute_roundtrip_tolerance",
        receipt.get("absolute_roundtrip_tolerance"),
        ROUNDTRIP_TOLERANCE,
    )
    absolute = receipt.get("carrier_absolute_infimum")
    if (
        not isinstance(absolute, (int, float))
        or not math.isfinite(float(absolute))
        or float(absolute) < 0.0
        or float(absolute) > ROUNDTRIP_TOLERANCE
    ):
        BASE.mismatch(
            out,
            f"{path}.carrier_absolute_infimum",
            f"finite value <= {ROUNDTRIP_TOLERANCE}",
            absolute,
            "bound",
        )
    BASE.compare_tree(
        out, f"{path}.absolute_roundtrip_pass", receipt.get("absolute_roundtrip_pass"), True
    )


def validate_block(
    out: list[dict[str, Any]],
    path: str,
    block: Any,
    family: str,
    expected_index: int,
    allowed_artifacts: set[str],
) -> dict[str, Any] | None:
    if not isinstance(block, dict):
        BASE.mismatch(out, path, "block object", block, "schema")
        return None
    BASE.compare_tree(out, f"{path}.block", block.get("block"), expected_index)
    BASE.compare_tree(out, f"{path}.coefficient_vector", block.get("coefficient_vector"), coefficient_vector())
    BASE.compare_tree(out, f"{path}.parameterization", block.get("parameterization"), PARAMETERIZATION)
    BASE.validate_continuation(block.get("optimizer"), f"{path}.optimizer", out)
    if not BASE.finite_nonnegative(block.get("wall_seconds_total")):
        BASE.mismatch(
            out,
            f"{path}.wall_seconds_total",
            "finite nonnegative number",
            block.get("wall_seconds_total"),
            "schema",
        )
    artifact = block.get("artifact")
    if not isinstance(artifact, str) or Path(artifact).name != artifact:
        BASE.mismatch(out, f"{path}.artifact", "local NPZ filename", artifact, "path")
        return None
    allowed_artifacts.add(artifact)
    artifact_path = RUN_DIR / artifact
    actual_hash = sha256_file(artifact_path) if artifact_path.is_file() else "MISSING"
    BASE.compare_tree(out, f"{path}.artifact_sha256", block.get("artifact_sha256"), actual_hash)
    fields = BASE.load_fields(artifact_path, family, out, f"{path}.artifact")
    if fields is None:
        return None
    fresh = direct_verify.prior.recompute_diagnostics(fields, H_C)
    reported = block.get("diagnostics")
    if not isinstance(reported, dict):
        BASE.mismatch(out, f"{path}.diagnostics", "object", reported, "schema")
        return None
    BASE.compare_tree(
        out,
        f"{path}.diagnostics",
        fresh,
        direct_verify.physical_diagnostics_only(reported),
    )
    quality = direct_verify.prior.quality_checks(fresh)
    localization = direct_verify.prior.localization_checks(fresh, 2.0)
    nodeless = direct_verify.negative_norm_receipt(fields)
    qualified = all(quality.values())
    selected = qualified and all(localization.values()) and bool(nodeless["pass"])
    BASE.compare_tree(out, f"{path}.quality_checks", block.get("quality_checks"), quality)
    BASE.compare_tree(out, f"{path}.localization_checks", block.get("localization_checks"), localization)
    BASE.compare_tree(out, f"{path}.nodeless_check", block.get("nodeless_check"), nodeless)
    BASE.compare_tree(out, f"{path}.numerically_qualified", block.get("numerically_qualified"), qualified)
    BASE.compare_tree(
        out,
        f"{path}.nodeless_localized_and_retained",
        block.get("nodeless_localized_and_retained"),
        selected,
    )
    return {
        "artifact": artifact,
        "artifact_sha256": actual_hash,
        "diagnostics": fresh,
        "quality_checks": quality,
        "localization_checks": localization,
        "nodeless_check": nodeless,
        "numerically_qualified": qualified,
        "nodeless_localized_and_retained": selected,
    }


def validate_arm(
    out: list[dict[str, Any]],
    path: str,
    arm: Any,
    family: str,
    allowed_artifacts: set[str],
) -> dict[str, Any] | None:
    if not isinstance(arm, dict):
        BASE.mismatch(out, path, "arm object", arm, "schema")
        return None
    r_box, n = NEW_GRIDS[family]
    exact = {
        "family": family,
        "basin": "separated_core",
        "R": r_box,
        "N": n,
        "dx": 2.0 * r_box / (n - 1),
        "h_C": H_C,
        "coefficient_vector": coefficient_vector(),
        "parameterization": PARAMETERIZATION,
        "max_blocks": MAX_BLOCKS,
    }
    for name, expected in exact.items():
        BASE.compare_tree(out, f"{path}.{name}", arm.get(name), expected)
    validate_reconstruction(out, f"{path}.reconstruction", arm.get("reconstruction"))
    BASE.validate_initial_optimizer(arm.get("initial_optimizer"), f"{path}.initial_optimizer", out)
    blocks = arm.get("blocks")
    if not isinstance(blocks, list) or not (1 <= len(blocks) <= MAX_BLOCKS):
        BASE.mismatch(
            out,
            f"{path}.blocks",
            f"list length in [1, {MAX_BLOCKS}]",
            blocks,
            "bound",
        )
        return None
    verified_blocks: list[dict[str, Any]] = []
    for index, block in enumerate(blocks, start=1):
        verified = validate_block(
            out,
            f"{path}.blocks[{index - 1}]",
            block,
            family,
            index,
            allowed_artifacts,
        )
        if verified is not None:
            verified_blocks.append(verified)
    for block in verified_blocks[:-1]:
        if block["numerically_qualified"]:
            BASE.mismatch(
                out,
                f"{path}.stopping_rule",
                "stop at first numerically qualified block",
                "later block present",
                "selection",
            )
    if not verified_blocks:
        return None
    terminal = verified_blocks[-1]
    if not terminal["numerically_qualified"] and len(blocks) != MAX_BLOCKS:
        BASE.mismatch(
            out,
            f"{path}.stopping_rule",
            MAX_BLOCKS,
            len(blocks),
            "unqualified_budget",
        )
    BASE.compare_tree(out, f"{path}.terminal_block", arm.get("terminal_block"), len(blocks))
    BASE.compare_tree(out, f"{path}.terminal_artifact", arm.get("terminal_artifact"), terminal["artifact"])
    BASE.compare_tree(
        out,
        f"{path}.terminal_artifact_sha256",
        arm.get("terminal_artifact_sha256"),
        terminal["artifact_sha256"],
    )
    BASE.compare_tree(
        out,
        f"{path}.diagnostics",
        direct_verify.physical_diagnostics_only(arm.get("diagnostics", {})),
        terminal["diagnostics"],
    )
    for name in (
        "quality_checks",
        "localization_checks",
        "nodeless_check",
        "numerically_qualified",
        "nodeless_localized_and_retained",
    ):
        BASE.compare_tree(out, f"{path}.{name}", arm.get(name), terminal[name])
    BASE.compare_tree(out, f"{path}.completed", arm.get("completed"), True)
    BASE.compare_tree(out, f"{path}.error", arm.get("error"), None)
    return {
        **terminal,
        "family": family,
        "R": r_box,
        "N": n,
        "h_C": H_C,
        "block_count": len(blocks),
    }


def run_preflight() -> int:
    if PREFLIGHT_PATH.exists():
        raise RuntimeError(f"preflight receipt is immutable: {PREFLIGHT_PATH}")
    mismatches: list[dict[str, Any]] = []
    manifest, manifest_sha256 = verify_manifest(mismatches)
    source_levels, roundtrips = verify_sources(mismatches)
    report = {
        "schema": "cassi.particle-carrier-resolution-recovery.preflight.v1",
        "pass": not mismatches,
        "manifest_sha256": manifest_sha256,
        "manifest": manifest,
        "source_levels": source_levels,
        "source_roundtrips": roundtrips,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }
    write_json(PREFLIGHT_PATH, report)
    print(
        json.dumps(
            {
                "preflight": str(PREFLIGHT_PATH),
                "pass": report["pass"],
                "mismatch_count": report["mismatch_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["pass"] else 1


def run_final_verification() -> int:
    if VERIFICATION_PATH.exists():
        raise RuntimeError(f"verification receipt is immutable: {VERIFICATION_PATH}")
    mismatches: list[dict[str, Any]] = []
    manifest, manifest_sha256 = verify_manifest(mismatches)
    source_levels, source_roundtrips = verify_sources(mismatches)
    if not PREFLIGHT_PATH.is_file():
        BASE.mismatch(mismatches, "preflight", "existing receipt", "MISSING", "read")
    else:
        preflight = read_json(PREFLIGHT_PATH)
        BASE.compare_tree(mismatches, "preflight.pass", preflight.get("pass"), True)
        BASE.compare_tree(
            mismatches,
            "preflight.manifest_sha256",
            preflight.get("manifest_sha256"),
            manifest_sha256,
        )
    try:
        results = read_json(RESULTS_PATH)
    except Exception as error:
        BASE.mismatch(mismatches, "results", "readable JSON", repr(error), "read")
        results = {}
    BASE.compare_tree(
        mismatches,
        "results.schema",
        results.get("schema"),
        "cassi.particle-carrier-resolution-recovery.results.v1",
    )
    BASE.compare_tree(mismatches, "results.status", results.get("status"), "complete")
    BASE.compare_tree(
        mismatches, "results.manifest_sha256", results.get("manifest_sha256"), manifest_sha256
    )
    if manifest is not None:
        BASE.compare_tree(mismatches, "results.manifest", results.get("manifest"), manifest)
    BASE.compare_tree(
        mismatches,
        "results.source_results_sha256",
        results.get("source_results_sha256"),
        SOURCE_RESULTS_SHA256,
    )
    BASE.compare_tree(
        mismatches,
        "results.source_verification_sha256",
        results.get("source_verification_sha256"),
        SOURCE_VERIFICATION_SHA256,
    )
    BASE.compare_tree(mismatches, "results.h_C", results.get("h_C"), H_C)
    BASE.compare_tree(
        mismatches, "results.coefficient_vector", results.get("coefficient_vector"), coefficient_vector()
    )
    BASE.compare_tree(
        mismatches, "results.parameterization", results.get("parameterization"), PARAMETERIZATION
    )
    BASE.compare_tree(mismatches, "results.source_levels", results.get("source_levels"), source_levels)
    BASE.compare_tree(
        mismatches, "results.refinement_order", results.get("refinement_order"), list(NEW_GRIDS)
    )

    BASE.GRIDS.update(NEW_GRIDS)
    allowed_artifacts: set[str] = set()
    arms = results.get("refinement_arms")
    if not isinstance(arms, dict):
        BASE.mismatch(mismatches, "results.refinement_arms", "object", arms, "schema")
        arms = {}
    verified: dict[str, dict[str, Any]] = {}
    for family in NEW_GRIDS:
        arm = arms.get(family)
        BASE.compare_tree(
            mismatches,
            f"results.refinement_arms.{family}.label",
            arm.get("label") if isinstance(arm, dict) else None,
            f"resolution_{family}",
        )
        checked = validate_arm(
            mismatches,
            f"results.refinement_arms.{family}",
            arm,
            family,
            allowed_artifacts,
        )
        if checked is not None:
            verified[family] = checked

    actual_artifacts = {path.name for path in RUN_DIR.glob("*.npz")}
    BASE.compare_tree(
        mismatches, "results.artifact_set", sorted(actual_artifacts), sorted(allowed_artifacts)
    )
    if (RUN_DIR / "failure.json").exists():
        BASE.mismatch(
            mismatches,
            "results.failure_receipt",
            "absent",
            "present",
            "execution",
        )

    execution_complete = len(verified) == len(NEW_GRIDS)
    qualified = execution_complete and all(
        verified[family]["numerically_qualified"] for family in NEW_GRIDS
    )
    selected = qualified and all(
        verified[family]["nodeless_localized_and_retained"] for family in NEW_GRIDS
    )
    comparisons: dict[str, dict[str, Any]] = {}
    energy_differences: dict[str, Any] = {}
    comparisons_pass = False
    contracts = False
    if selected and set(source_levels) == {"P", "H"}:
        levels = {
            "P": source_levels["P"],
            "H": source_levels["H"],
            "X1": verified["X1"],
            "X2": verified["X2"],
        }
        for left, right in (("H", "X1"), ("X1", "X2")):
            comparisons[f"{left}_{right}"] = comparison_metrics(levels[left], levels[right])
        comparisons_pass = all(row["pass"] for row in comparisons.values())
        energies = {
            label: float(levels[label]["diagnostics"]["physical_energy"])
            for label in ("P", "H", "X1", "X2")
        }
        d0 = abs(energies["P"] - energies["H"])
        d1 = abs(energies["H"] - energies["X1"])
        d2 = abs(energies["X1"] - energies["X2"])
        contracts = d1 < d0 and d2 < d1
        energy_differences = {
            "P_H": d0,
            "H_X1": d1,
            "X1_X2": d2,
            "H_X1_less_than_P_H": d1 < d0,
            "X1_X2_less_than_H_X1": d2 < d1,
        }

    BASE.compare_tree(
        mismatches,
        "results.adjacent_comparisons",
        results.get("adjacent_comparisons"),
        comparisons,
    )
    BASE.compare_tree(
        mismatches,
        "results.energy_differences",
        results.get("energy_differences"),
        energy_differences,
    )
    expected_checks = {
        "source_chain_reproduced": True,
        "refinement_execution_complete": execution_complete,
        "refined_grids_numerically_qualified": qualified,
        "refined_grids_nodeless_localized_and_retained": selected,
        "adjacent_comparisons_pass": comparisons_pass,
        "energy_differences_contract_twice": contracts,
    }
    BASE.compare_tree(
        mismatches,
        "results.campaign_checks",
        results.get("campaign_checks"),
        expected_checks,
    )
    if not execution_complete:
        expected_verdict = VERDICTS["inconclusive"]
    elif not qualified or not selected:
        expected_verdict = VERDICTS["no_refined"]
    elif comparisons_pass and contracts:
        expected_verdict = VERDICTS["resolved"]
    else:
        expected_verdict = VERDICTS["finite_grid"]
    BASE.compare_tree(
        mismatches,
        "results.primary_verdict",
        results.get("primary_verdict"),
        expected_verdict,
    )

    report = {
        "schema": "cassi.particle-carrier-resolution-recovery.verification.v1",
        "pass": not mismatches,
        "manifest_sha256": manifest_sha256,
        "results_sha256": sha256_file(RESULTS_PATH) if RESULTS_PATH.is_file() else "MISSING",
        "source_results_sha256": SOURCE_RESULTS_SHA256,
        "source_verification_sha256": SOURCE_VERIFICATION_SHA256,
        "source_roundtrips": source_roundtrips,
        "verified_refinement_arms": verified,
        "adjacent_comparisons": comparisons,
        "energy_differences": energy_differences,
        "reconstructed_checks": expected_checks,
        "reconstructed_verdict": expected_verdict,
        "scientific_verdict": (
            expected_verdict if not mismatches else VERDICTS["inconclusive"]
        ),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }
    write_json(VERIFICATION_PATH, report)
    print(
        json.dumps(
            {
                "verification": str(VERIFICATION_PATH),
                "pass": report["pass"],
                "mismatch_count": report["mismatch_count"],
                "scientific_verdict": report["scientific_verdict"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    return run_preflight() if args.preflight else run_final_verification()


if __name__ == "__main__":
    raise SystemExit(main())
