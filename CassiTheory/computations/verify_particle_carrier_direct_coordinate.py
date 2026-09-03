#!/usr/bin/env python3
"""Independently verify the direct-coordinate carrier recovery campaign."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import verify_particle_carrier_localization as prior  # pyright: ignore[reportMissingImports]


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runs" / "20260902_particle_carrier_direct_coordinate"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
RESULTS_PATH = RUN_DIR / "results.json"
VERIFICATION_PATH = RUN_DIR / "verification.json"
MANIFEST_PATH = ROOT / "computations" / "particle_carrier_direct_coordinate_manifest.json"
SOURCE_DIR = ROOT / "runs" / "20260902_particle_carrier_localization"
SOURCE_RESULTS = SOURCE_DIR / "results.json"
SOURCE_VERIFICATION = SOURCE_DIR / "verification.json"
SOURCE_RESULTS_SHA256 = "5a90e405d9d6851a1e445633adc0523de9c94d64e9ed27c139f177f92432a2d0"
SOURCE_VERIFICATION_SHA256 = "f30f95e71ab8a66b6aac1fd84001dba82771257a3ead73e200fd32c85eb5d4ad"
SOURCE_ARTIFACTS = (
    {
        "label": "half_reference",
        "h_C": 2.9598260763447164,
        "artifact": "fields_primary_half_reference_block04.npz",
        "artifact_sha256": "9f9c37cd75d0b6ccbe427c2afaa10aa8659c9cb532868cbe41183a11bddfea83",
        "source_block": 4,
    },
    {
        "label": "three_quarters_reference",
        "h_C": 4.439739114517074,
        "artifact": "fields_primary_three_quarters_reference_block04.npz",
        "artifact_sha256": "534bbe5a6ce04b7ad36975a97e507388b15a2fe7533312a81ee1e15202c742b5",
        "source_block": 4,
    },
    {
        "label": "reference",
        "h_C": 5.919652152689433,
        "artifact": "fields_primary_reference_block04.npz",
        "artifact_sha256": "fea3d1dc1e40817d65b68c13edd52f18e163ef6ca0cc0e48ce05932f99fde8d2",
        "source_block": 4,
    },
    {
        "label": "five_quarters_reference",
        "h_C": 7.399565190861791,
        "artifact": "fields_primary_five_quarters_reference_block04.npz",
        "artifact_sha256": "3241d9b5ee33765a867073231c0cd55f614e7b33ade41a3c0fa2e622fa3f8232",
        "source_block": 4,
    },
    {
        "label": "three_halves_reference",
        "h_C": 8.879478229034149,
        "artifact": "fields_primary_three_halves_reference_block04.npz",
        "artifact_sha256": "262e5bb08c15a26970f7095b1477ac9d782c9fba864a41ced498b003ec7f44d7",
        "source_block": 4,
    },
)
PARAMETERIZATION = "direct_shell_masked_fixed_charge"
ROUNDTRIP_TOL = 5.0e-12
NEGATIVE_NORM_LIMIT = 1.0e-12
PRIMARY_MAX_BLOCKS = 8
COMPARISON_MAX_BLOCKS = 8


def coefficient_vector(h_c: float) -> dict[str, float]:
    return {**prior.FIXED_COEFFICIENTS, "h_C": float(h_c)}


def expected_source_manifest() -> dict[str, Any]:
    return {
        "results": str(SOURCE_RESULTS.relative_to(ROOT)).replace("\\", "/"),
        "results_sha256": SOURCE_RESULTS_SHA256,
        "verification": str(SOURCE_VERIFICATION.relative_to(ROOT)).replace("\\", "/"),
        "verification_sha256": SOURCE_VERIFICATION_SHA256,
        "source_verification_pass": True,
        "source_verdict": "INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION",
        "artifacts": list(SOURCE_ARTIFACTS),
    }


def expected_schedule() -> dict[str, Any]:
    return {
        "precision_gradient_limit": prior.PRECISION_GRADIENT_LIMIT,
        "omega_limit": prior.OMEGA_LIMIT,
        "primary_max_blocks": PRIMARY_MAX_BLOCKS,
        "comparison_max_blocks": COMPARISON_MAX_BLOCKS,
        "primary_families": ["P"],
        "comparison_families": ["D", "H"],
        "comparison_basin": "separated_core",
        "continuation": prior.independent.CONTINUATION,
    }


def verify_manifest(
    out: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        manifest = prior.read_json(MANIFEST_PATH)
    except Exception as error:
        prior.independent.mismatch(
            out, "manifest", "readable JSON object", repr(error), "read"
        )
        return None, None
    prior.independent.compare_tree(
        out,
        "manifest.schema",
        manifest.get("schema"),
        "cassi.particle-carrier-direct-coordinate.manifest.v1",
    )
    prior.independent.compare_tree(
        out, "manifest.source", manifest.get("source"), expected_source_manifest()
    )
    prior.independent.compare_tree(
        out,
        "manifest.fixed_coefficients",
        manifest.get("fixed_coefficients"),
        prior.FIXED_COEFFICIENTS,
    )
    prior.independent.compare_tree(
        out,
        "manifest.parameterization",
        manifest.get("parameterization"),
        {
            "name": PARAMETERIZATION,
            "roundtrip_tolerance": ROUNDTRIP_TOL,
            "negative_norm_fraction_limit": NEGATIVE_NORM_LIMIT,
        },
    )
    prior.independent.compare_tree(
        out, "manifest.schedule", manifest.get("schedule"), expected_schedule()
    )
    hashes = manifest.get("sha256")
    if not isinstance(hashes, dict) or not hashes:
        prior.independent.mismatch(
            out, "manifest.sha256", "nonempty object", hashes, "schema"
        )
    else:
        for relative, expected in hashes.items():
            path = ROOT / relative
            actual = prior.sha256_file(path) if path.is_file() else "MISSING"
            if actual != expected:
                prior.independent.mismatch(
                    out, f"manifest.sha256.{relative}", expected, actual, "hash"
                )
    return manifest, prior.sha256_file(MANIFEST_PATH)


def physical_diagnostics_only(diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in diagnostics.items()
        if key not in {"objective_raw_gradient_rms", "objective_raw_gradient_max"}
    }


def direct_roundtrip(fields: Mapping[str, np.ndarray]) -> dict[str, Any]:
    x = fields["x"]
    dx = float(x[1] - x[0])
    n = int(x.shape[0])
    mask = np.zeros((n, n, n), dtype=np.float64)
    mask[1:-1, 1:-1, 1:-1] = 1.0
    source = fields["c"]
    shape = mask * source
    norm = math.sqrt(float(np.sum(shape**2)) * dx**3)
    reconstructed = math.sqrt(prior.FIXED_COEFFICIENTS["q_C"]) * shape / norm
    scale = max(float(np.max(np.abs(source))), 1.0e-12)
    residual = float(np.max(np.abs(reconstructed - source))) / scale
    return {
        "parameterization": PARAMETERIZATION,
        "carrier_relative_infimum": residual,
        "roundtrip_tolerance": ROUNDTRIP_TOL,
        "roundtrip_pass": residual <= ROUNDTRIP_TOL,
    }


def negative_norm_receipt(fields: Mapping[str, np.ndarray]) -> dict[str, Any]:
    x = fields["x"]
    dx = float(x[1] - x[0])
    dv = dx**3
    carrier = fields["c"]
    signed_integral = float(np.sum(carrier)) * dv
    orientation = 1.0 if signed_integral >= 0.0 else -1.0
    oriented = orientation * carrier
    negative_norm = float(np.sum(np.minimum(oriented, 0.0) ** 2)) * dv
    charge = float(np.sum(carrier**2)) * dv
    fraction = negative_norm / max(charge, 1.0e-30)
    return {
        "signed_integral": signed_integral,
        "orientation": orientation,
        "negative_norm": negative_norm,
        "charge": charge,
        "negative_norm_fraction": fraction,
        "limit": NEGATIVE_NORM_LIMIT,
        "pass": fraction <= NEGATIVE_NORM_LIMIT,
    }


def verify_sources(out: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for name, path, expected in (
        ("source.results", SOURCE_RESULTS, SOURCE_RESULTS_SHA256),
        ("source.verification", SOURCE_VERIFICATION, SOURCE_VERIFICATION_SHA256),
    ):
        actual = prior.sha256_file(path) if path.is_file() else "MISSING"
        if actual != expected:
            prior.independent.mismatch(out, name, expected, actual, "hash")
    try:
        results = prior.read_json(SOURCE_RESULTS)
        verification = prior.read_json(SOURCE_VERIFICATION)
    except Exception as error:
        prior.independent.mismatch(
            out, "source.receipts", "readable JSON", repr(error), "read"
        )
        return []
    prior.independent.compare_tree(
        out,
        "source.results.primary_verdict",
        results.get("primary_verdict"),
        "INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION",
    )
    prior.independent.compare_tree(
        out, "source.verification.pass", verification.get("pass"), True
    )
    prior.independent.compare_tree(
        out, "source.verification.mismatches", verification.get("mismatches"), []
    )
    scan = results.get("primary_scan")
    if not isinstance(scan, list) or len(scan) != len(SOURCE_ARTIFACTS):
        prior.independent.mismatch(
            out,
            "source.results.primary_scan",
            f"list length {len(SOURCE_ARTIFACTS)}",
            scan,
            "schema",
        )
        return []
    verified: list[dict[str, Any]] = []
    for index, source in enumerate(SOURCE_ARTIFACTS):
        arm = scan[index]
        path = f"source.primary_scan[{index}]"
        exact = {
            "label": f"primary_{source['label']}",
            "family": "P",
            "h_C": source["h_C"],
            "terminal_block": source["source_block"],
            "terminal_artifact": source["artifact"],
            "terminal_artifact_sha256": source["artifact_sha256"],
            "numerically_qualified": False,
        }
        for name, expected in exact.items():
            prior.independent.compare_tree(
                out, f"{path}.{name}", arm.get(name), expected
            )
        artifact_path = SOURCE_DIR / source["artifact"]
        actual_hash = (
            prior.sha256_file(artifact_path) if artifact_path.is_file() else "MISSING"
        )
        prior.independent.compare_tree(
            out, f"{path}.artifact_sha256", actual_hash, source["artifact_sha256"]
        )
        fields = prior.independent.load_fields(
            artifact_path, "P", out, f"{path}.artifact"
        )
        if fields is None:
            continue
        fresh = prior.recompute_diagnostics(fields, float(source["h_C"]))
        reported = arm.get("diagnostics")
        if not isinstance(reported, dict):
            prior.independent.mismatch(
                out, f"{path}.diagnostics", "object", reported, "schema"
            )
            continue
        prior.independent.compare_tree(
            out,
            f"{path}.diagnostics",
            fresh,
            physical_diagnostics_only(reported),
        )
        quality = prior.quality_checks(fresh)
        localization = prior.localization_checks(fresh, 2.0)
        roundtrip = direct_roundtrip(fields)
        nodeless = negative_norm_receipt(fields)
        prior.independent.compare_tree(
            out, f"{path}.localization", localization, {name: True for name in localization}
        )
        prior.independent.compare_tree(
            out, f"{path}.quality.physical_stationarity", quality["physical_stationarity"], False
        )
        prior.independent.compare_tree(
            out, f"{path}.direct_roundtrip_pass", roundtrip["roundtrip_pass"], True
        )
        prior.independent.compare_tree(
            out, f"{path}.nodeless_pass", nodeless["pass"], True
        )
        verified.append(
            {
                **source,
                "diagnostics": fresh,
                "quality_checks": quality,
                "localization_checks": localization,
                "direct_roundtrip": roundtrip,
                "nodeless_check": nodeless,
            }
        )
    return verified


def run_preflight() -> int:
    mismatches: list[dict[str, Any]] = []
    if RUN_DIR.exists():
        existing = sorted(path.name for path in RUN_DIR.iterdir())
        if existing:
            prior.independent.mismatch(
                mismatches, "output_freshness", [], existing, "immutable_output"
            )
    manifest, manifest_sha256 = verify_manifest(mismatches)
    sources = verify_sources(mismatches)
    report = {
        "schema": "cassi.particle-carrier-direct-coordinate.preflight.v1",
        "pass": not mismatches
        and manifest is not None
        and len(sources) == len(SOURCE_ARTIFACTS),
        "manifest_sha256": manifest_sha256,
        "mismatches": mismatches,
        "verified_sources": sources,
    }
    prior.write_json(PREFLIGHT_PATH, report)
    print(
        json.dumps(
            {"pass": report["pass"], "mismatches": len(mismatches)}, sort_keys=True
        )
    )
    return 0 if report["pass"] else 1


def validate_block(
    out: list[dict[str, Any]],
    path: str,
    block: Any,
    family: str,
    h_c: float,
    expected_index: int,
    allowed_artifacts: set[str],
) -> dict[str, Any] | None:
    if not isinstance(block, dict):
        prior.independent.mismatch(out, path, "block object", block, "schema")
        return None
    prior.independent.compare_tree(
        out, f"{path}.block", block.get("block"), expected_index
    )
    prior.independent.compare_tree(
        out,
        f"{path}.coefficient_vector",
        block.get("coefficient_vector"),
        coefficient_vector(h_c),
    )
    prior.independent.compare_tree(
        out, f"{path}.parameterization", block.get("parameterization"), PARAMETERIZATION
    )
    prior.independent.validate_continuation(
        block.get("optimizer"), f"{path}.optimizer", out
    )
    if not prior.independent.finite_nonnegative(block.get("wall_seconds_total")):
        prior.independent.mismatch(
            out,
            f"{path}.wall_seconds_total",
            "finite nonnegative number",
            block.get("wall_seconds_total"),
            "schema",
        )
    artifact = block.get("artifact")
    if not isinstance(artifact, str) or Path(artifact).name != artifact:
        prior.independent.mismatch(
            out, f"{path}.artifact", "local NPZ filename", artifact, "path"
        )
        return None
    allowed_artifacts.add(artifact)
    artifact_path = RUN_DIR / artifact
    actual_hash = (
        prior.sha256_file(artifact_path) if artifact_path.is_file() else "MISSING"
    )
    prior.independent.compare_tree(
        out, f"{path}.artifact_sha256", block.get("artifact_sha256"), actual_hash
    )
    fields = prior.independent.load_fields(
        artifact_path, family, out, f"{path}.artifact"
    )
    if fields is None:
        return None
    fresh = prior.recompute_diagnostics(fields, h_c)
    reported = block.get("diagnostics")
    if not isinstance(reported, dict):
        prior.independent.mismatch(
            out, f"{path}.diagnostics", "object", reported, "schema"
        )
        return None
    prior.independent.compare_tree(
        out, f"{path}.diagnostics", fresh, physical_diagnostics_only(reported)
    )
    radius_limit = (4.0 if family in ("P", "H") else 5.0) / 2.0
    quality = prior.quality_checks(fresh)
    localization = prior.localization_checks(fresh, radius_limit)
    nodeless = negative_norm_receipt(fields)
    qualified = all(quality.values())
    selected_branch = qualified and all(localization.values()) and bool(nodeless["pass"])
    prior.independent.compare_tree(
        out, f"{path}.quality_checks", block.get("quality_checks"), quality
    )
    prior.independent.compare_tree(
        out,
        f"{path}.localization_checks",
        block.get("localization_checks"),
        localization,
    )
    prior.independent.compare_tree(
        out, f"{path}.nodeless_check", block.get("nodeless_check"), nodeless
    )
    prior.independent.compare_tree(
        out,
        f"{path}.numerically_qualified",
        block.get("numerically_qualified"),
        qualified,
    )
    prior.independent.compare_tree(
        out,
        f"{path}.nodeless_localized_and_retained",
        block.get("nodeless_localized_and_retained"),
        selected_branch,
    )
    return {
        "artifact": artifact,
        "artifact_sha256": actual_hash,
        "diagnostics": fresh,
        "quality_checks": quality,
        "localization_checks": localization,
        "nodeless_check": nodeless,
        "numerically_qualified": qualified,
        "nodeless_localized_and_retained": selected_branch,
    }


def validate_arm(
    out: list[dict[str, Any]],
    path: str,
    arm: Any,
    family: str,
    h_c: float,
    max_blocks: int,
    allowed_artifacts: set[str],
    require_initial_optimizer: bool,
) -> dict[str, Any] | None:
    if not isinstance(arm, dict):
        prior.independent.mismatch(out, path, "arm object", arm, "schema")
        return None
    r_box, n = prior.independent.GRIDS[family]
    exact = {
        "family": family,
        "basin": "separated_core",
        "R": r_box,
        "N": n,
        "dx": 2.0 * r_box / (n - 1),
        "h_C": h_c,
        "coefficient_vector": coefficient_vector(h_c),
        "parameterization": PARAMETERIZATION,
        "max_blocks": max_blocks,
    }
    for name, expected in exact.items():
        prior.independent.compare_tree(
            out, f"{path}.{name}", arm.get(name), expected
        )
    if require_initial_optimizer:
        prior.independent.validate_initial_optimizer(
            arm.get("initial_optimizer"), f"{path}.initial_optimizer", out
        )
    else:
        prior.independent.compare_tree(
            out, f"{path}.initial_optimizer", arm.get("initial_optimizer"), None
        )
    blocks = arm.get("blocks")
    if not isinstance(blocks, list) or not (1 <= len(blocks) <= max_blocks):
        prior.independent.mismatch(
            out,
            f"{path}.blocks",
            f"list length in [1, {max_blocks}]",
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
            h_c,
            index,
            allowed_artifacts,
        )
        if verified is not None:
            verified_blocks.append(verified)
    for block in verified_blocks[:-1]:
        if block["numerically_qualified"]:
            prior.independent.mismatch(
                out,
                f"{path}.stopping_rule",
                "stop at first numerically qualified block",
                "later block present",
                "selection",
            )
    if not verified_blocks:
        return None
    terminal = verified_blocks[-1]
    prior.independent.compare_tree(
        out, f"{path}.terminal_block", arm.get("terminal_block"), len(blocks)
    )
    prior.independent.compare_tree(
        out,
        f"{path}.terminal_artifact",
        arm.get("terminal_artifact"),
        terminal["artifact"],
    )
    prior.independent.compare_tree(
        out,
        f"{path}.terminal_artifact_sha256",
        arm.get("terminal_artifact_sha256"),
        terminal["artifact_sha256"],
    )
    prior.independent.compare_tree(
        out,
        f"{path}.diagnostics",
        physical_diagnostics_only(arm.get("diagnostics", {})),
        terminal["diagnostics"],
    )
    for name in (
        "quality_checks",
        "localization_checks",
        "nodeless_check",
        "numerically_qualified",
        "nodeless_localized_and_retained",
    ):
        prior.independent.compare_tree(
            out, f"{path}.{name}", arm.get(name), terminal[name]
        )
    prior.independent.compare_tree(out, f"{path}.completed", arm.get("completed"), True)
    prior.independent.compare_tree(out, f"{path}.error", arm.get("error"), None)
    return {
        **terminal,
        "family": family,
        "R": r_box,
        "N": n,
        "h_C": h_c,
        "block_count": len(blocks),
    }


def run_final_verification() -> int:
    mismatches: list[dict[str, Any]] = []
    manifest, manifest_sha256 = verify_manifest(mismatches)
    if not PREFLIGHT_PATH.is_file():
        prior.independent.mismatch(
            mismatches, "preflight", "existing receipt", "MISSING", "read"
        )
    else:
        preflight = prior.read_json(PREFLIGHT_PATH)
        prior.independent.compare_tree(
            mismatches, "preflight.pass", preflight.get("pass"), True
        )
        prior.independent.compare_tree(
            mismatches,
            "preflight.manifest_sha256",
            preflight.get("manifest_sha256"),
            manifest_sha256,
        )
    sources = verify_sources(mismatches)
    try:
        results = prior.read_json(RESULTS_PATH)
    except Exception as error:
        prior.independent.mismatch(
            mismatches, "results", "readable JSON", repr(error), "read"
        )
        results = {}
    prior.independent.compare_tree(
        mismatches,
        "results.schema",
        results.get("schema"),
        "cassi.particle-carrier-direct-coordinate.results.v1",
    )
    prior.independent.compare_tree(
        mismatches, "results.status", results.get("status"), "complete"
    )
    prior.independent.compare_tree(
        mismatches,
        "results.manifest_sha256",
        results.get("manifest_sha256"),
        manifest_sha256,
    )
    if manifest is not None:
        prior.independent.compare_tree(
            mismatches, "results.manifest", results.get("manifest"), manifest
        )
    prior.independent.compare_tree(
        mismatches,
        "results.source_results_sha256",
        results.get("source_results_sha256"),
        SOURCE_RESULTS_SHA256,
    )
    prior.independent.compare_tree(
        mismatches,
        "results.source_verification_sha256",
        results.get("source_verification_sha256"),
        SOURCE_VERIFICATION_SHA256,
    )
    prior.independent.compare_tree(
        mismatches,
        "results.candidate_order",
        results.get("candidate_order"),
        [row["label"] for row in SOURCE_ARTIFACTS],
    )

    allowed_artifacts: set[str] = set()
    scan = results.get("primary_scan")
    verified_scan: list[dict[str, Any]] = []
    if not isinstance(scan, list) or not (1 <= len(scan) <= len(SOURCE_ARTIFACTS)):
        prior.independent.mismatch(
            mismatches,
            "results.primary_scan",
            f"list length in [1, {len(SOURCE_ARTIFACTS)}]",
            scan,
            "bound",
        )
        scan = []
    for index, arm in enumerate(scan):
        source = SOURCE_ARTIFACTS[index]
        prior.independent.compare_tree(
            mismatches,
            f"results.primary_scan[{index}].label",
            arm.get("label") if isinstance(arm, dict) else None,
            f"primary_{source['label']}",
        )
        verified = validate_arm(
            mismatches,
            f"results.primary_scan[{index}]",
            arm,
            "P",
            float(source["h_C"]),
            PRIMARY_MAX_BLOCKS,
            allowed_artifacts,
            False,
        )
        if verified is not None:
            verified_scan.append(verified)

    selected_indices = [
        index
        for index, arm in enumerate(verified_scan)
        if arm["nodeless_localized_and_retained"]
    ]
    selected_expected: dict[str, Any] | None = None
    if selected_indices:
        selected_index = selected_indices[0]
        if len(scan) != selected_index + 1:
            prior.independent.mismatch(
                mismatches,
                "results.primary_scan.stopping_rule",
                selected_index + 1,
                len(scan),
                "selection",
            )
        source = SOURCE_ARTIFACTS[selected_index]
        arm = verified_scan[selected_index]
        selected_expected = {
            "label": source["label"],
            "h_C": source["h_C"],
            "scan_index": selected_index,
            "artifact": arm["artifact"],
            "artifact_sha256": arm["artifact_sha256"],
        }
    elif len(scan) != len(SOURCE_ARTIFACTS):
        prior.independent.mismatch(
            mismatches,
            "results.primary_scan.stopping_rule",
            len(SOURCE_ARTIFACTS),
            len(scan),
            "selection",
        )
    prior.independent.compare_tree(
        mismatches,
        "results.selected_primary",
        results.get("selected_primary"),
        selected_expected,
    )

    comparison_verified: dict[str, dict[str, Any]] = {}
    if selected_expected is None:
        prior.independent.compare_tree(
            mismatches, "results.comparison_order", results.get("comparison_order"), []
        )
        prior.independent.compare_tree(
            mismatches, "results.comparison_arms", results.get("comparison_arms"), {}
        )
        prior.independent.compare_tree(
            mismatches, "results.comparisons", results.get("comparisons"), {}
        )
    else:
        prior.independent.compare_tree(
            mismatches,
            "results.comparison_order",
            results.get("comparison_order"),
            ["D", "H"],
        )
        comparison_arms = results.get("comparison_arms")
        if not isinstance(comparison_arms, dict):
            prior.independent.mismatch(
                mismatches,
                "results.comparison_arms",
                "object",
                comparison_arms,
                "schema",
            )
            comparison_arms = {}
        for family in ("D", "H"):
            arm = comparison_arms.get(family)
            prior.independent.compare_tree(
                mismatches,
                f"results.comparison_arms.{family}.label",
                arm.get("label") if isinstance(arm, dict) else None,
                f"comparison_{family}",
            )
            verified = validate_arm(
                mismatches,
                f"results.comparison_arms.{family}",
                arm,
                family,
                float(selected_expected["h_C"]),
                COMPARISON_MAX_BLOCKS,
                allowed_artifacts,
                True,
            )
            if verified is not None:
                comparison_verified[family] = verified

    comparison_qualified = (
        selected_expected is not None
        and set(comparison_verified) == {"D", "H"}
        and all(row["numerically_qualified"] for row in comparison_verified.values())
    )
    fresh_comparisons: dict[str, Any] = {}
    comparisons_selected: bool | None = None
    domain_match: bool | None = None
    if comparison_qualified and selected_expected is not None:
        primary_arm = verified_scan[int(selected_expected["scan_index"])]
        fresh_comparisons = {
            family: prior.compare_metrics(primary_arm, comparison_verified[family])
            for family in ("D", "H")
        }
        prior.independent.compare_tree(
            mismatches,
            "results.comparisons",
            results.get("comparisons"),
            fresh_comparisons,
        )
        comparisons_selected = all(
            row["nodeless_localized_and_retained"]
            for row in comparison_verified.values()
        )
        domain_match = comparisons_selected and all(
            row["pass"] for row in fresh_comparisons.values()
        )

    any_primary_unqualified = any(
        not row["numerically_qualified"] for row in verified_scan
    ) or len(verified_scan) != len(scan)
    if selected_expected is None:
        expected_verdict = (
            "INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION"
            if any_primary_unqualified
            else "DOES NOT EMERGE—NO NODELESS LOCALIZED RETAINED PRIMARY IN FROZEN BRACKET"
        )
    elif not comparison_qualified:
        expected_verdict = "INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION"
    else:
        expected_verdict = (
            "EMERGES—DOMAIN-AND-RESOLUTION-MATCHED LOCALIZED RETAINED BRANCH"
            if domain_match
            else "EMERGES—FINITE-GRID LOCALIZED RETAINED BRANCH ONLY"
        )
    prior.independent.compare_tree(
        mismatches,
        "results.primary_verdict",
        results.get("primary_verdict"),
        expected_verdict,
    )

    expected_checks = {
        "source_chain_reproduced": True,
        "planned_primary_scan_completed": selected_expected is not None
        or len(scan) == len(SOURCE_ARTIFACTS),
        "nodeless_localized_primary_found": selected_expected is not None,
        "comparison_grids_numerically_qualified": (
            comparison_qualified if selected_expected is not None else None
        ),
        "comparison_grids_nodeless_localized_and_retained": (
            comparisons_selected if comparison_qualified else None
        ),
        "domain_and_resolution_match": domain_match,
    }
    prior.independent.compare_tree(
        mismatches,
        "results.campaign_checks",
        results.get("campaign_checks"),
        expected_checks,
    )

    expected_files = {"preflight_verification.json", "results.json", *allowed_artifacts}
    actual_files = (
        {
            path.name
            for path in RUN_DIR.iterdir()
            if path.is_file() and path != VERIFICATION_PATH
        }
        if RUN_DIR.is_dir()
        else set()
    )
    if actual_files != expected_files:
        prior.independent.mismatch(
            mismatches,
            "output_files",
            sorted(expected_files),
            sorted(actual_files),
            "immutable_output",
        )

    report = {
        "schema": "cassi.particle-carrier-direct-coordinate.verification.v1",
        "pass": not mismatches,
        "manifest_sha256": manifest_sha256,
        "mismatches": mismatches,
        "verified_source_count": len(sources),
        "verified_primary_scan": verified_scan,
        "verified_comparison_arms": comparison_verified,
        "verified_comparisons": fresh_comparisons,
        "selected_primary": selected_expected,
        "scientific_verdict": (
            expected_verdict
            if not mismatches
            else "INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION"
        ),
    }
    prior.write_json(VERIFICATION_PATH, report)
    print(
        json.dumps(
            {
                "pass": report["pass"],
                "mismatches": len(mismatches),
                "verdict": report["scientific_verdict"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["pass"] else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    arguments = parser.parse_args(argv)
    return run_preflight() if arguments.preflight else run_final_verification()


if __name__ == "__main__":
    raise SystemExit(main())
