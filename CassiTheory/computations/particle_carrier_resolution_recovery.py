#!/usr/bin/env python3
"""Run the preregistered carrier spatial-resolution recovery campaign."""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any, Mapping

import torch

import particle_carrier_direct_coordinate as direct  # pyright: ignore[reportMissingImports]


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runs" / "20260902_particle_carrier_resolution_recovery"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
RESULTS_PATH = RUN_DIR / "results.json"
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
        "result_path": ("primary_scan", 0),
        "R": 4.0,
        "N": 17,
        "dx": 0.5,
        "artifact": "fields_primary_half_reference_block01.npz",
        "artifact_sha256": "c32beb4ee7bc7746a4fc18b63bc04ef7db12cc18505c9bee8ce2d298ddc25837",
    },
    "H": {
        "result_path": ("comparison_arms", "H"),
        "R": 4.0,
        "N": 21,
        "dx": 0.4,
        "artifact": "fields_comparison_H_block01.npz",
        "artifact_sha256": "8aa65f3c08167c902660f9e8d09c0ce921d43c7f0af152b31aae79db6875810f",
    },
}
VERDICTS = {
    "inconclusive": "INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION",
    "no_refined": "DOES NOT EMERGE—NO QUALIFIED REFINED-GRID BRANCH",
    "finite_grid": "EMERGES—FINITE-GRID LOCALIZED RETAINED BRANCH ONLY",
    "resolved": "EMERGES—THREE-LEVEL RESOLUTION-CONSISTENT LOCALIZED RETAINED BRANCH",
}
COMPARISON_PROTOCOL = {
    "energy_relative_limit": 0.05,
    "core_length_absolute_limit": 0.75,
    "omega_absolute_limit": 0.10,
    "radius_relative_limit": 0.10,
    "relative_denominator_floor": 1.0e-30,
    "energy_contraction": "strict_twice",
}

REQUIRED_HASH_PATHS = (
    "computations/particle-carrier-resolution-recovery-prereg.md",
    "computations/particle-carrier-resolution-recovery-verification-amendment.md",
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





class CampaignFailure(RuntimeError):
    """Raised when a frozen campaign prerequisite is violated."""


def source_arm(results: Mapping[str, Any], family: str) -> Mapping[str, Any]:
    first, second = SOURCE_LEVELS[family]["result_path"]
    container = results[first]
    return container[second]
def source_manifest_levels() -> dict[str, dict[str, Any]]:
    return {
        family: {
            name: values[name]
            for name in ("R", "N", "dx", "artifact", "artifact_sha256")
        }
        for family, values in SOURCE_LEVELS.items()
    }




def source_level_receipt(results: Mapping[str, Any], family: str) -> dict[str, Any]:
    arm = source_arm(results, family)
    expected = SOURCE_LEVELS[family]
    if arm.get("terminal_artifact") != expected["artifact"]:
        raise CampaignFailure(f"source {family} artifact name mismatch")
    if arm.get("terminal_artifact_sha256") != expected["artifact_sha256"]:
        raise CampaignFailure(f"source {family} artifact receipt mismatch")
    artifact_path = SOURCE_DIR / expected["artifact"]
    if direct.prior.sha256_file(artifact_path) != expected["artifact_sha256"]:
        raise CampaignFailure(f"source {family} artifact hash mismatch")
    if arm.get("nodeless_localized_and_retained") is not True:
        raise CampaignFailure(f"source {family} branch is not qualified and localized")
    return {
        "family": family,
        "R": expected["R"],
        "N": expected["N"],
        "dx": expected["dx"],
        "h_C": arm["h_C"],
        "terminal_block": arm["terminal_block"],
        "terminal_artifact": expected["artifact"],
        "terminal_artifact_sha256": expected["artifact_sha256"],
        "diagnostics": direct.physical_diagnostics_only(arm["diagnostics"]),
        "quality_checks": arm["quality_checks"],
        "localization_checks": arm["localization_checks"],
        "nodeless_check": arm["nodeless_check"],
        "numerically_qualified": arm["numerically_qualified"],
        "nodeless_localized_and_retained": arm[
            "nodeless_localized_and_retained"
        ],
    }


def verify_manifest() -> tuple[dict[str, Any], str]:
    manifest = direct.prior.read_json(MANIFEST_PATH)
    if manifest.get("schema") != "cassi.particle-carrier-resolution-recovery.manifest.v1":
        raise CampaignFailure("resolution-recovery manifest schema mismatch")
    hashes = manifest.get("sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(REQUIRED_HASH_PATHS):
        raise CampaignFailure("manifest hash path set mismatch")
    for relative, expected in hashes.items():
        path = ROOT / relative
        if not path.is_file() or direct.prior.sha256_file(path) != expected:
            raise CampaignFailure(f"manifest hash mismatch: {relative}")
    source = manifest.get("source", {})
    if source.get("results") != SOURCE_RESULTS.relative_to(ROOT).as_posix():
        raise CampaignFailure("source results path mismatch")
    if source.get("results_sha256") != SOURCE_RESULTS_SHA256:
        raise CampaignFailure("source results hash mismatch")
    if source.get("verification") != SOURCE_VERIFICATION.relative_to(ROOT).as_posix():
        raise CampaignFailure("source verification path mismatch")
    if source.get("verification_sha256") != SOURCE_VERIFICATION_SHA256:
        raise CampaignFailure("source verification hash mismatch")
    if source.get("source_verdict") != SOURCE_VERDICT:
        raise CampaignFailure("source verdict mismatch")
    if source.get("source_verification_pass") is not True:
        raise CampaignFailure("source verification status mismatch")
    if source.get("levels") != source_manifest_levels():
        raise CampaignFailure("source level manifest mismatch")
    if manifest.get("fixed_coefficients") != direct.prior.FIXED_COEFFICIENTS:
        raise CampaignFailure("fixed coefficient vector mismatch")
    if manifest.get("h_C") != H_C:
        raise CampaignFailure("selected density-depletion coefficient mismatch")
    if manifest.get("parameterization") != {
        "name": direct.PARAMETERIZATION,
        "roundtrip_tolerance": direct.ROUNDTRIP_TOL,
        "negative_norm_fraction_limit": direct.NEGATIVE_NORM_LIMIT,
    }:
        raise CampaignFailure("direct parameterization mismatch")
    expected_grids = {
        family: {"R": r_box, "N": n, "dx": 2.0 * r_box / (n - 1)}
        for family, (r_box, n) in NEW_GRIDS.items()
    }
    if manifest.get("new_grids") != expected_grids:
        raise CampaignFailure("refinement grid mismatch")
    schedule = manifest.get("schedule", {})
    if schedule.get("max_blocks") != MAX_BLOCKS:
        raise CampaignFailure("continuation block limit mismatch")
    if schedule.get("order") != list(NEW_GRIDS):
        raise CampaignFailure("refinement order mismatch")
    if schedule.get("initial_optimizer") != {"adam_steps": 800, "lbfgs_max_iter": 120}:
        raise CampaignFailure("initial optimizer mismatch")
    if schedule.get("continuation") != direct.recovery.CONTINUATION:
        raise CampaignFailure("continuation schedule mismatch")
    if manifest.get("comparison") != COMPARISON_PROTOCOL:
        raise CampaignFailure("comparison protocol mismatch")
    return manifest, direct.prior.sha256_file(MANIFEST_PATH)


def configure_torch() -> torch.device:
    torch.set_default_dtype(torch.float64)
    if not torch.cuda.is_available():
        raise CampaignFailure("ROCm/CUDA device unavailable")
    return torch.device("cuda")


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


def error_arm(label: str, family: str, grid: direct.stationary.Grid, error: Exception) -> dict[str, Any]:
    return {
        "label": label,
        "family": family,
        "basin": "separated_core",
        "R": grid.R,
        "N": grid.N,
        "dx": grid.dx,
        "h_C": H_C,
        "coefficient_vector": direct.coefficient_vector(H_C),
        "parameterization": direct.PARAMETERIZATION,
        "max_blocks": MAX_BLOCKS,
        "reconstruction": None,
        "initial_optimizer": None,
        "blocks": [],
        "terminal_block": None,
        "terminal_artifact": None,
        "terminal_artifact_sha256": None,
        "diagnostics": None,
        "quality_checks": {},
        "localization_checks": {},
        "nodeless_check": None,
        "numerically_qualified": False,
        "nodeless_localized_and_retained": False,
        "completed": False,
        "error": f"{type(error).__name__}: {error}",
    }


def run() -> dict[str, Any]:
    if RUN_DIR.is_dir():
        unexpected = sorted(path.name for path in RUN_DIR.iterdir() if path != PREFLIGHT_PATH)
        if unexpected:
            raise CampaignFailure(
                f"resolution-recovery output path is immutable and not fresh: {unexpected}"
            )
    device = configure_torch()
    manifest, manifest_sha256 = verify_manifest()
    if not PREFLIGHT_PATH.is_file():
        raise CampaignFailure(
            "run verify_particle_carrier_resolution_recovery.py --preflight first"
        )
    preflight = direct.prior.read_json(PREFLIGHT_PATH)
    if preflight.get("pass") is not True:
        raise CampaignFailure("independent resolution-recovery preflight did not pass")
    if preflight.get("manifest_sha256") != manifest_sha256:
        raise CampaignFailure("independent preflight manifest hash mismatch")
    if direct.prior.sha256_file(SOURCE_RESULTS) != SOURCE_RESULTS_SHA256:
        raise CampaignFailure("source result changed")
    if direct.prior.sha256_file(SOURCE_VERIFICATION) != SOURCE_VERIFICATION_SHA256:
        raise CampaignFailure("source verification changed")
    source_results = direct.prior.read_json(SOURCE_RESULTS)
    source_verification = direct.prior.read_json(SOURCE_VERIFICATION)
    if source_results.get("status") != "complete":
        raise CampaignFailure("source result is incomplete")
    if source_results.get("primary_verdict") != SOURCE_VERDICT:
        raise CampaignFailure("source verdict changed")
    if source_verification.get("pass") is not True or source_verification.get("mismatches") != []:
        raise CampaignFailure("source independent verification did not pass")

    direct.RUN_DIR = RUN_DIR
    direct.stationary.GRIDS.update(NEW_GRIDS)
    direct.activate_direct_coordinate()
    source_levels = {
        family: source_level_receipt(source_results, family) for family in ("P", "H")
    }
    receipt: dict[str, Any] = {
        "schema": "cassi.particle-carrier-resolution-recovery.results.v1",
        "status": "in_progress",
        "campaign": "particle_carrier_resolution_recovery",
        "device": str(device),
        "torch_version": torch.__version__,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "rocm_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "manifest": manifest,
        "manifest_sha256": manifest_sha256,
        "preflight_sha256": direct.prior.sha256_file(PREFLIGHT_PATH),
        "source_results_sha256": SOURCE_RESULTS_SHA256,
        "source_verification_sha256": SOURCE_VERIFICATION_SHA256,
        "h_C": H_C,
        "coefficient_vector": direct.coefficient_vector(H_C),
        "parameterization": direct.PARAMETERIZATION,
        "source_levels": source_levels,
        "refinement_order": [],
        "refinement_arms": {},
        "adjacent_comparisons": {},
        "energy_differences": {},
        "campaign_checks": {
            "source_chain_reproduced": True,
            "refinement_execution_complete": False,
            "refined_grids_numerically_qualified": False,
            "refined_grids_nodeless_localized_and_retained": False,
            "adjacent_comparisons_pass": False,
            "energy_differences_contract_twice": False,
        },
        "primary_verdict": VERDICTS["inconclusive"],
    }
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    direct.prior.write_json(RESULTS_PATH, receipt)

    for family in NEW_GRIDS:
        direct.configure_coefficients(H_C)
        grid = direct.stationary.make_grid(family, device)
        print(
            f"RUN resolution {family}: R={grid.R:.15g} N={grid.N} dx={grid.dx:.15g}",
            flush=True,
        )
        try:
            raw, reconstruction = direct.directize_analytic_seed("separated_core", grid)
            with torch.no_grad():
                mapped_carrier = direct.direct_physical_fields(raw, grid)["c"]
                absolute_roundtrip = float(
                    torch.max(torch.abs(mapped_carrier - raw["w"])).detach().cpu()
                )
            reconstruction["carrier_absolute_infimum"] = absolute_roundtrip
            reconstruction["absolute_roundtrip_tolerance"] = direct.ROUNDTRIP_TOL
            reconstruction["absolute_roundtrip_pass"] = (
                absolute_roundtrip <= direct.ROUNDTRIP_TOL
            )
            if not (
                reconstruction["roundtrip_pass"]
                and reconstruction["absolute_roundtrip_pass"]
            ):
                raise CampaignFailure(f"direct analytic seed roundtrip failed: {family}")
            initial_optimizer = direct.stationary.optimize_arm(raw, grid)
            arm = direct.run_arm(
                label=f"resolution_{family}",
                family=family,
                h_c=H_C,
                raw=raw,
                grid=grid,
                max_blocks=MAX_BLOCKS,
                initial_optimizer=initial_optimizer,
                reconstruction=reconstruction,
            )
        except Exception as error:
            arm = error_arm(f"resolution_{family}", family, grid, error)
        receipt["refinement_order"].append(family)
        receipt["refinement_arms"][family] = arm
        direct.prior.write_json(RESULTS_PATH, receipt)

    arms = receipt["refinement_arms"]
    execution_complete = all(
        arms[family]["completed"]
        and arms[family]["error"] is None
        and bool(arms[family]["blocks"])
        for family in NEW_GRIDS
    )
    qualified = all(arms[family]["numerically_qualified"] for family in NEW_GRIDS)
    selected = qualified and all(
        arms[family]["nodeless_localized_and_retained"] for family in NEW_GRIDS
    )
    receipt["campaign_checks"]["refined_grids_numerically_qualified"] = qualified
    receipt["campaign_checks"]["refinement_execution_complete"] = execution_complete
    receipt["campaign_checks"][
        "refined_grids_nodeless_localized_and_retained"
    ] = selected

    if not execution_complete:
        verdict = VERDICTS["inconclusive"]
    elif not qualified or not selected:
        verdict = VERDICTS["no_refined"]
    else:
        levels = {
            "P": source_levels["P"],
            "H": source_levels["H"],
            "X1": arms["X1"],
            "X2": arms["X2"],
        }
        for left, right in (("H", "X1"), ("X1", "X2")):
            receipt["adjacent_comparisons"][f"{left}_{right}"] = (
                comparison_metrics(levels[left], levels[right])
            )
        comparisons_pass = all(
            row["pass"] for row in receipt["adjacent_comparisons"].values()
        )
        energies = {
            label: float(levels[label]["diagnostics"]["physical_energy"])
            for label in ("P", "H", "X1", "X2")
        }
        d0 = abs(energies["P"] - energies["H"])
        d1 = abs(energies["H"] - energies["X1"])
        d2 = abs(energies["X1"] - energies["X2"])
        contracts = d1 < d0 and d2 < d1
        receipt["energy_differences"] = {
            "P_H": d0,
            "H_X1": d1,
            "X1_X2": d2,
            "H_X1_less_than_P_H": d1 < d0,
            "X1_X2_less_than_H_X1": d2 < d1,
        }
        receipt["campaign_checks"]["adjacent_comparisons_pass"] = comparisons_pass
        receipt["campaign_checks"][
            "energy_differences_contract_twice"
        ] = contracts
        verdict = (
            VERDICTS["resolved"]
            if comparisons_pass and contracts
            else VERDICTS["finite_grid"]
        )

    receipt["primary_verdict"] = verdict
    receipt["status"] = "complete"
    direct.prior.write_json(RESULTS_PATH, receipt)
    return receipt


def main() -> int:
    try:
        receipt = run()
    except Exception as error:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        direct.prior.write_json(RUN_DIR / "failure.json", {
            "schema": "cassi.particle-carrier-resolution-recovery.failure.v1",
            "error": f"{type(error).__name__}: {error}",
        })
        raise
    print(
        json.dumps(
            {
                "results": str(RESULTS_PATH),
                "energy_differences": receipt["energy_differences"],
                "verdict": receipt["primary_verdict"],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
