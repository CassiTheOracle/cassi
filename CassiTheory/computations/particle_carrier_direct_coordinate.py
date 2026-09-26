#!/usr/bin/env python3
"""Run the preregistered direct-coordinate carrier recovery campaign."""

from __future__ import annotations

import json
import math
import os
import platform
import time
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch

import particle_carrier_localization as prior  # pyright: ignore[reportMissingImports]
import particle_stationary_bvp as stationary  # pyright: ignore[reportMissingImports]
import particle_stationary_q2_recovery_v2 as recovery  # pyright: ignore[reportMissingImports]


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runs" / "20260902_particle_carrier_direct_coordinate_v2"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
RESULTS_PATH = RUN_DIR / "results.json"
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
SOFTPLUS_PHYSICAL_FIELDS = stationary.physical_fields


class CampaignFailure(RuntimeError):
    """Raised when a frozen direct-coordinate requirement is not met."""


def coefficient_vector(h_c: float) -> dict[str, float]:
    return {**prior.FIXED_COEFFICIENTS, "h_C": float(h_c)}


def configure_coefficients(h_c: float) -> dict[str, float]:
    vector = coefficient_vector(h_c)
    if set(stationary.COEFFICIENTS) != set(vector):
        raise CampaignFailure("stationary coefficient key set changed")
    stationary.COEFFICIENTS.clear()
    stationary.COEFFICIENTS.update(vector)
    return vector


def direct_physical_fields(
    raw: Mapping[str, torch.Tensor],
    grid: stationary.Grid,
    charge: float = stationary.COEFFICIENTS["q_C"],
) -> dict[str, torch.Tensor]:
    fields = SOFTPLUS_PHYSICAL_FIELDS(raw, grid, charge)
    if charge == 0.0:
        fields["c"] = torch.zeros_like(grid.mask)
    else:
        carrier_shape = grid.mask * stationary.project_scalar(raw["w"])
        carrier_norm = torch.sqrt(torch.sum(carrier_shape**2) * grid.dv)
        fields["c"] = math.sqrt(charge) * carrier_shape / carrier_norm
    return fields


def activate_direct_coordinate() -> None:
    stationary.physical_fields = direct_physical_fields


def maximum_relative_infimum(
    actual: Mapping[str, torch.Tensor], expected: Mapping[str, np.ndarray]
) -> tuple[float, dict[str, float]]:
    residuals: dict[str, float] = {}
    for name in ("psi_real", "psi_imag", "h", "a", "c"):
        observed = actual[name].detach().cpu().numpy()
        target = expected[name]
        scale = max(float(np.max(np.abs(target))), 1.0e-12)
        residuals[name] = float(np.max(np.abs(observed - target))) / scale
    return max(residuals.values()), residuals


def reconstruct_direct_raw(
    arrays: Mapping[str, np.ndarray], grid: stationary.Grid
) -> tuple[dict[str, torch.nn.Parameter], dict[str, Any]]:
    stationary.physical_fields = SOFTPLUS_PHYSICAL_FIELDS
    try:
        raw, softplus_receipt = recovery.reconstruct_raw(arrays, grid)
    finally:
        activate_direct_coordinate()
    raw["w"] = torch.nn.Parameter(
        torch.tensor(arrays["c"], dtype=torch.float64, device=grid.x.device)
    )
    fields = direct_physical_fields(raw, grid)
    maximum, residuals = maximum_relative_infimum(fields, arrays)
    receipt = {
        "parameterization": PARAMETERIZATION,
        "softplus_reconstruction": softplus_receipt,
        "direct_relative_infimum": residuals,
        "direct_maximum_relative_infimum": maximum,
        "direct_roundtrip_tolerance": ROUNDTRIP_TOL,
        "direct_roundtrip_pass": maximum <= ROUNDTRIP_TOL,
        "raw_finite": all(bool(torch.all(torch.isfinite(value))) for value in raw.values()),
    }
    return raw, receipt


def directize_analytic_seed(
    basin: str, grid: stationary.Grid
) -> tuple[dict[str, torch.nn.Parameter], dict[str, Any]]:
    stationary.physical_fields = SOFTPLUS_PHYSICAL_FIELDS
    raw = stationary.raw_parameters(basin, grid)
    with torch.no_grad():
        source_fields = SOFTPLUS_PHYSICAL_FIELDS(raw, grid)
        source_carrier = source_fields["c"].detach().clone()
    raw["w"] = torch.nn.Parameter(source_carrier)
    activate_direct_coordinate()
    with torch.no_grad():
        direct_fields = direct_physical_fields(raw, grid)
        scale = max(float(torch.max(torch.abs(source_carrier))), 1.0e-12)
        residual = float(torch.max(torch.abs(direct_fields["c"] - source_carrier))) / scale
    return raw, {
        "parameterization": PARAMETERIZATION,
        "basin": basin,
        "carrier_relative_infimum": residual,
        "roundtrip_tolerance": ROUNDTRIP_TOL,
        "roundtrip_pass": residual <= ROUNDTRIP_TOL,
    }


def verify_manifest() -> tuple[dict[str, Any], str]:
    manifest = prior.read_json(MANIFEST_PATH)
    if manifest.get("schema") != "cassi.particle-carrier-direct-coordinate.manifest.v2":
        raise CampaignFailure("direct-coordinate manifest schema mismatch")
    expected_source = {
        "results": str(SOURCE_RESULTS.relative_to(ROOT)).replace("\\", "/"),
        "results_sha256": SOURCE_RESULTS_SHA256,
        "verification": str(SOURCE_VERIFICATION.relative_to(ROOT)).replace("\\", "/"),
        "verification_sha256": SOURCE_VERIFICATION_SHA256,
        "source_verification_pass": True,
        "source_verdict": "INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION",
        "artifacts": list(SOURCE_ARTIFACTS),
    }
    if manifest.get("source") != expected_source:
        raise CampaignFailure("manifest source chain changed")
    if manifest.get("fixed_coefficients") != prior.FIXED_COEFFICIENTS:
        raise CampaignFailure("manifest fixed coefficient vector changed")
    if manifest.get("parameterization") != {
        "name": PARAMETERIZATION,
        "roundtrip_tolerance": ROUNDTRIP_TOL,
        "negative_norm_fraction_limit": NEGATIVE_NORM_LIMIT,
    }:
        raise CampaignFailure("manifest carrier parameterization changed")
    expected_schedule = {
        "precision_gradient_limit": prior.PRECISION_GRADIENT_LIMIT,
        "omega_limit": prior.OMEGA_LIMIT,
        "primary_max_blocks": PRIMARY_MAX_BLOCKS,
        "comparison_max_blocks": COMPARISON_MAX_BLOCKS,
        "primary_families": ["P"],
        "comparison_families": ["D", "H"],
        "comparison_basin": "separated_core",
        "continuation": recovery.CONTINUATION,
    }
    if manifest.get("schedule") != expected_schedule:
        raise CampaignFailure("manifest optimization schedule changed")
    hashes = manifest.get("sha256")
    if not isinstance(hashes, dict) or not hashes:
        raise CampaignFailure("manifest has no source hashes")
    failures = []
    for relative, expected in hashes.items():
        path = ROOT / relative
        actual = prior.sha256_file(path) if path.is_file() else "MISSING"
        if actual != expected:
            failures.append({"path": relative, "expected": expected, "actual": actual})
    if failures:
        raise CampaignFailure(f"manifest hash mismatch: {failures}")
    return manifest, prior.sha256_file(MANIFEST_PATH)


def configure_torch() -> torch.device:
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "0":
        raise CampaignFailure("CUDA_VISIBLE_DEVICES must equal 0")
    if not torch.cuda.is_available():
        raise CampaignFailure("ROCm device exposed as cuda:0 is unavailable")
    torch.set_default_dtype(torch.float64)
    torch.use_deterministic_algorithms(True)
    activate_direct_coordinate()
    return torch.device("cuda:0")


def environment_receipt(device: torch.device) -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "torch": torch.__version__,
        "hip": getattr(torch.version, "hip", None),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "pytorch_hip_alloc_conf": os.environ.get("PYTORCH_HIP_ALLOC_CONF"),
        "hsa_enable_sdma": os.environ.get("HSA_ENABLE_SDMA"),
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "dtype": "float64",
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "carrier_parameterization": PARAMETERIZATION,
    }


def physical_diagnostics_only(diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in diagnostics.items()
        if key not in {"objective_raw_gradient_rms", "objective_raw_gradient_max"}
    }


def negative_norm_receipt(fields: Mapping[str, torch.Tensor], grid: stationary.Grid) -> dict[str, Any]:
    carrier = fields["c"]
    signed_integral = float(torch.sum(carrier).detach().cpu()) * grid.dv
    orientation = 1.0 if signed_integral >= 0.0 else -1.0
    oriented = orientation * carrier
    negative_norm = float(
        (torch.sum(torch.minimum(oriented, torch.zeros_like(oriented)) ** 2) * grid.dv)
        .detach()
        .cpu()
    )
    charge = float((torch.sum(carrier**2) * grid.dv).detach().cpu())
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


def load_source(
    source: Mapping[str, Any], device: torch.device
) -> tuple[dict[str, torch.nn.Parameter], dict[str, Any]]:
    results = prior.read_json(SOURCE_RESULTS)
    verification = prior.read_json(SOURCE_VERIFICATION)
    if prior.sha256_file(SOURCE_RESULTS) != SOURCE_RESULTS_SHA256:
        raise CampaignFailure("source result receipt hash mismatch")
    if prior.sha256_file(SOURCE_VERIFICATION) != SOURCE_VERIFICATION_SHA256:
        raise CampaignFailure("source verification receipt hash mismatch")
    if verification.get("pass") is not True or verification.get("mismatches"):
        raise CampaignFailure("source verification is not clean")
    if results.get("primary_verdict") != "INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION":
        raise CampaignFailure("source result verdict changed")
    source_index = next(
        (
            index
            for index, candidate in enumerate(SOURCE_ARTIFACTS)
            if candidate["label"] == source["label"]
        ),
        None,
    )
    if source_index is None:
        raise CampaignFailure(f"unknown source label: {source['label']}")
    source_arm = results["primary_scan"][source_index]
    for name, expected in (
        ("h_C", source["h_C"]),
        ("terminal_block", source["source_block"]),
        ("terminal_artifact", source["artifact"]),
        ("terminal_artifact_sha256", source["artifact_sha256"]),
    ):
        if source_arm.get(name) != expected:
            raise CampaignFailure(f"source arm field changed: {source['label']}.{name}")
    artifact_path = SOURCE_DIR / source["artifact"]
    if prior.sha256_file(artifact_path) != source["artifact_sha256"]:
        raise CampaignFailure(f"source artifact hash mismatch: {source['label']}")
    arrays = recovery.load_arrays(artifact_path)
    schema_failures = recovery.validate_npz_arrays(arrays, "P")
    if schema_failures:
        raise CampaignFailure(f"source artifact schema failure: {schema_failures}")
    configure_coefficients(float(source["h_C"]))
    grid = stationary.make_grid("P", device)
    raw, reconstruction = reconstruct_direct_raw(arrays, grid)
    if not reconstruction["raw_finite"] or not reconstruction["direct_roundtrip_pass"]:
        raise CampaignFailure(f"direct source reconstruction failure: {reconstruction}")
    diagnostics, fields = stationary.diagnostics(raw, grid)
    failures: list[str] = []
    prior.compare_numeric_tree(
        physical_diagnostics_only(diagnostics),
        physical_diagnostics_only(source_arm["diagnostics"]),
        f"source.{source['label']}.diagnostics",
        failures,
    )
    if failures:
        raise CampaignFailure(f"source diagnostics changed: {failures}")
    nodeless = negative_norm_receipt(fields, grid)
    return raw, {
        "label": source["label"],
        "h_C": source["h_C"],
        "artifact": str(artifact_path.relative_to(ROOT)).replace("\\", "/"),
        "artifact_sha256": source["artifact_sha256"],
        "source_block": source["source_block"],
        "coefficient_vector": coefficient_vector(float(source["h_C"])),
        "parameterization": PARAMETERIZATION,
        "reconstruction": reconstruction,
        "diagnostics": diagnostics,
        "quality_checks": prior.quality_checks(diagnostics),
        "localization_checks": prior.localization_checks(diagnostics, 2.0),
        "nodeless_check": nodeless,
    }


def endpoint_checks(
    diagnostics: Mapping[str, Any],
    fields: Mapping[str, torch.Tensor],
    grid: stationary.Grid,
) -> tuple[dict[str, bool], dict[str, bool], dict[str, Any], bool, bool]:
    quality = prior.quality_checks(diagnostics)
    localization = prior.localization_checks(diagnostics, grid.R / 2.0)
    nodeless = negative_norm_receipt(fields, grid)
    qualified = all(quality.values())
    selected_branch = qualified and all(localization.values()) and bool(nodeless["pass"])
    return quality, localization, nodeless, qualified, selected_branch


def run_arm(
    *,
    label: str,
    family: str,
    h_c: float,
    raw: dict[str, torch.nn.Parameter],
    grid: stationary.Grid,
    max_blocks: int,
    initial_optimizer: dict[str, Any] | None,
    reconstruction: dict[str, Any],
) -> dict[str, Any]:
    vector = configure_coefficients(h_c)
    activate_direct_coordinate()
    arm: dict[str, Any] = {
        "label": label,
        "family": family,
        "basin": "separated_core",
        "R": grid.R,
        "N": grid.N,
        "dx": grid.dx,
        "h_C": h_c,
        "coefficient_vector": vector,
        "parameterization": PARAMETERIZATION,
        "max_blocks": max_blocks,
        "initial_optimizer": initial_optimizer,
        "source_reconstruction": reconstruction,
        "blocks": [],
        "terminal_block": None,
        "terminal_artifact": None,
        "terminal_artifact_sha256": None,
        "diagnostics": None,
        "quality_checks": prior.quality_checks(None),
        "localization_checks": prior.localization_checks(None, grid.R / 2.0),
        "nodeless_check": None,
        "numerically_qualified": False,
        "nodeless_localized_and_retained": False,
        "completed": False,
        "error": None,
    }
    try:
        for block_index in range(1, max_blocks + 1):
            started = time.perf_counter()
            optimizer = recovery.continue_lbfgs(raw, grid)
            diagnostics, fields = stationary.diagnostics(raw, grid)
            if not prior.finite_tree(optimizer) or not prior.finite_tree(diagnostics):
                raise CampaignFailure("nonfinite optimizer or diagnostic receipt")
            quality, localization, nodeless, qualified, selected_branch = endpoint_checks(
                diagnostics, fields, grid
            )
            artifact_name = f"fields_{label}_block{block_index:02d}.npz"
            artifact_path = RUN_DIR / artifact_name
            stationary.save_fields(artifact_path, fields, grid)
            block = {
                "block": block_index,
                "wall_seconds_total": time.perf_counter() - started,
                "optimizer": optimizer,
                "artifact": artifact_name,
                "artifact_sha256": prior.sha256_file(artifact_path),
                "coefficient_vector": vector,
                "parameterization": PARAMETERIZATION,
                "diagnostics": diagnostics,
                "quality_checks": quality,
                "localization_checks": localization,
                "nodeless_check": nodeless,
                "numerically_qualified": qualified,
                "nodeless_localized_and_retained": selected_branch,
            }
            arm["blocks"].append(block)
            print(
                f"DONE {label} block {block_index}: "
                f"h_C={h_c:.12g} "
                f"grad={diagnostics['physical_gradient_rms']:.12g} "
                f"omega={diagnostics['omega_c']:.12g} "
                f"radius={diagnostics['carrier_radius']:.12g} "
                f"outer={diagnostics['outer_carrier_fraction']:.12g} "
                f"negative_norm={nodeless['negative_norm_fraction']:.12g}",
                flush=True,
            )
            if qualified:
                break
        if arm["blocks"]:
            terminal = arm["blocks"][-1]
            arm.update(
                {
                    "terminal_block": terminal["block"],
                    "terminal_artifact": terminal["artifact"],
                    "terminal_artifact_sha256": terminal["artifact_sha256"],
                    "diagnostics": terminal["diagnostics"],
                    "quality_checks": terminal["quality_checks"],
                    "localization_checks": terminal["localization_checks"],
                    "nodeless_check": terminal["nodeless_check"],
                    "numerically_qualified": terminal["numerically_qualified"],
                    "nodeless_localized_and_retained": terminal[
                        "nodeless_localized_and_retained"
                    ],
                }
            )
        arm["completed"] = True
    except Exception as error:
        arm["error"] = f"{type(error).__name__}: {error}"
    return arm


def run() -> dict[str, Any]:
    if RUN_DIR.is_dir():
        unexpected = sorted(path.name for path in RUN_DIR.iterdir() if path != PREFLIGHT_PATH)
        if unexpected:
            raise CampaignFailure(
                f"direct-coordinate output path is immutable and not fresh: {unexpected}"
            )
    device = configure_torch()
    manifest, manifest_sha256 = verify_manifest()
    if not PREFLIGHT_PATH.is_file():
        raise CampaignFailure(
            "run verify_particle_carrier_direct_coordinate.py --preflight first"
        )
    preflight = prior.read_json(PREFLIGHT_PATH)
    if preflight.get("pass") is not True:
        raise CampaignFailure("independent direct-coordinate preflight did not pass")
    if preflight.get("manifest_sha256") != manifest_sha256:
        raise CampaignFailure("independent preflight manifest hash mismatch")

    receipt: dict[str, Any] = {
        "schema": "cassi.particle-carrier-direct-coordinate.results.v2",
        "status": "in_progress",
        "manifest": manifest,
        "manifest_sha256": manifest_sha256,
        "environment": environment_receipt(device),
        "source_results_sha256": SOURCE_RESULTS_SHA256,
        "source_verification_sha256": SOURCE_VERIFICATION_SHA256,
        "candidate_order": [row["label"] for row in SOURCE_ARTIFACTS],
        "primary_scan": [],
        "selected_primary": None,
        "comparison_order": [],
        "comparison_arms": {},
        "comparisons": {},
        "campaign_checks": {
            "source_chain_reproduced": True,
            "planned_primary_scan_completed": None,
            "nodeless_localized_primary_found": None,
            "comparison_grids_numerically_qualified": None,
            "comparison_grids_nodeless_localized_and_retained": None,
            "domain_and_resolution_match": None,
        },
        "primary_verdict": None,
    }
    prior.write_json(RESULTS_PATH, receipt)

    for source in SOURCE_ARTIFACTS:
        raw, source_receipt = load_source(source, device)
        print(
            f"RUN primary {source['label']} at h_C={source['h_C']:.15g}",
            flush=True,
        )
        grid = stationary.make_grid("P", device)
        arm = run_arm(
            label=f"primary_{source['label']}",
            family="P",
            h_c=float(source["h_C"]),
            raw=raw,
            grid=grid,
            max_blocks=PRIMARY_MAX_BLOCKS,
            initial_optimizer=None,
            reconstruction=source_receipt,
        )
        receipt["primary_scan"].append(arm)
        prior.write_json(RESULTS_PATH, receipt)
        if arm["nodeless_localized_and_retained"]:
            receipt["selected_primary"] = {
                "label": source["label"],
                "h_C": source["h_C"],
                "scan_index": len(receipt["primary_scan"]) - 1,
                "artifact": arm["terminal_artifact"],
                "artifact_sha256": arm["terminal_artifact_sha256"],
            }
            break

    receipt["campaign_checks"]["planned_primary_scan_completed"] = (
        receipt["selected_primary"] is not None
        or len(receipt["primary_scan"]) == len(SOURCE_ARTIFACTS)
    )
    receipt["campaign_checks"]["nodeless_localized_primary_found"] = (
        receipt["selected_primary"] is not None
    )

    any_primary_unqualified = any(
        not arm["numerically_qualified"] for arm in receipt["primary_scan"]
    )
    if receipt["selected_primary"] is None:
        verdict = (
            "INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION"
            if any_primary_unqualified
            else "DOES NOT EMERGE—NO NODELESS LOCALIZED RETAINED PRIMARY IN FROZEN BRACKET"
        )
    else:
        selected_index = int(receipt["selected_primary"]["scan_index"])
        primary = receipt["primary_scan"][selected_index]
        selected_h = float(receipt["selected_primary"]["h_C"])
        for family in ("D", "H"):
            configure_coefficients(selected_h)
            comparison_grid = stationary.make_grid(family, device)
            raw, seed_receipt = directize_analytic_seed("separated_core", comparison_grid)
            if not seed_receipt["roundtrip_pass"]:
                raise CampaignFailure(f"direct analytic seed roundtrip failed: {family}")
            print(
                f"RUN {family} comparison from direct analytic seed at "
                f"h_C={selected_h:.15g}",
                flush=True,
            )
            try:
                initial_optimizer = stationary.optimize_arm(raw, comparison_grid)
                arm = run_arm(
                    label=f"comparison_{family}",
                    family=family,
                    h_c=selected_h,
                    raw=raw,
                    grid=comparison_grid,
                    max_blocks=COMPARISON_MAX_BLOCKS,
                    initial_optimizer=initial_optimizer,
                    reconstruction=seed_receipt,
                )
            except Exception as error:
                arm = {
                    "label": f"comparison_{family}",
                    "family": family,
                    "basin": "separated_core",
                    "R": comparison_grid.R,
                    "N": comparison_grid.N,
                    "dx": comparison_grid.dx,
                    "h_C": selected_h,
                    "coefficient_vector": coefficient_vector(selected_h),
                    "parameterization": PARAMETERIZATION,
                    "max_blocks": COMPARISON_MAX_BLOCKS,
                    "initial_optimizer": None,
                    "source_reconstruction": seed_receipt,
                    "blocks": [],
                    "terminal_block": None,
                    "terminal_artifact": None,
                    "terminal_artifact_sha256": None,
                    "diagnostics": None,
                    "quality_checks": prior.quality_checks(None),
                    "localization_checks": prior.localization_checks(
                        None, comparison_grid.R / 2.0
                    ),
                    "nodeless_check": None,
                    "numerically_qualified": False,
                    "nodeless_localized_and_retained": False,
                    "completed": False,
                    "error": f"{type(error).__name__}: {error}",
                }
            receipt["comparison_order"].append(family)
            receipt["comparison_arms"][family] = arm
            prior.write_json(RESULTS_PATH, receipt)

        comparison_qualified = (
            receipt["comparison_order"] == ["D", "H"]
            and all(
                receipt["comparison_arms"][family]["numerically_qualified"]
                for family in ("D", "H")
            )
        )
        receipt["campaign_checks"][
            "comparison_grids_numerically_qualified"
        ] = comparison_qualified
        if not comparison_qualified:
            verdict = "INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION"
        else:
            comparisons_selected = all(
                receipt["comparison_arms"][family][
                    "nodeless_localized_and_retained"
                ]
                for family in ("D", "H")
            )
            receipt["campaign_checks"][
                "comparison_grids_nodeless_localized_and_retained"
            ] = comparisons_selected
            for family in ("D", "H"):
                receipt["comparisons"][family] = prior.comparison_metrics(
                    primary, receipt["comparison_arms"][family]
                )
            comparisons_match = all(
                row["pass"] for row in receipt["comparisons"].values()
            )
            domain_match = comparisons_selected and comparisons_match
            receipt["campaign_checks"]["domain_and_resolution_match"] = domain_match
            verdict = (
                "EMERGES—DOMAIN-AND-RESOLUTION-MATCHED LOCALIZED RETAINED BRANCH"
                if domain_match
                else "EMERGES—FINITE-GRID LOCALIZED RETAINED BRANCH ONLY"
            )

    receipt["primary_verdict"] = verdict
    receipt["status"] = "complete"
    prior.write_json(RESULTS_PATH, receipt)
    return receipt


def main() -> int:
    receipt = run()
    print(
        json.dumps(
            {
                "verdict": receipt["primary_verdict"],
                "selected_primary": receipt["selected_primary"],
                "results": str(RESULTS_PATH),
            },
            sort_keys=True,
        )
    )
    return 2 if str(receipt["primary_verdict"]).startswith("INCONCLUSIVE") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        prior.write_json(
            RUN_DIR / "failure.json",
            {
                "schema": "cassi.particle-carrier-direct-coordinate.failure.v2",
                "error": f"{type(error).__name__}: {error}",
            },
        )
        raise
