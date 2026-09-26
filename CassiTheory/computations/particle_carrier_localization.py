#!/usr/bin/env python3
"""Run the preregistered particle carrier localization campaign."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import time
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch

import particle_stationary_bvp as stationary  # pyright: ignore[reportMissingImports]
import particle_stationary_q2_recovery_v2 as recovery  # pyright: ignore[reportMissingImports]


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runs" / "20260902_particle_carrier_localization"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
RESULTS_PATH = RUN_DIR / "results.json"
MANIFEST_PATH = ROOT / "computations" / "particle_carrier_localization_manifest.json"
SOURCE_DIR = ROOT / "runs" / "20260902_particle_stationary_precision_v5"
SOURCE_ARTIFACT = SOURCE_DIR / "fields_block01.npz"
SOURCE_RESULTS = SOURCE_DIR / "results.json"
SOURCE_VERIFICATION = SOURCE_DIR / "verification.json"
SOURCE_HASHES = {
    "artifact": "ac4c54fa0e5ed61f73cb86b5e83d0061806fc2e5d1725894bad9e8e89457a61e",
    "results": "9decc9a751d7c833f92754eb3e5187da9056bc5ddda0c9bd125e188f4e90cfa5",
    "verification": "7667c9617c3e4bd237e77e84226c78805d224002a18a192f25cce24cd2ce4b32",
}
FIXED_COEFFICIENTS = {
    "phi": stationary.PHI,
    "alpha_s": 1.0,
    "u_rho": 4.0,
    "u_phi": 4.0,
    "gamma_x": 1.0,
    "gamma_s": 1.0,
    "u_H": 4.0,
    "k_Cx": 1.0,
    "k_Cs": 1.0,
    "e_C": 0.75,
    "u_C": 1.0,
    "q_C": 4.0,
    "L_s": 1.0,
    "xi_gf": 1.0,
}
SOURCE_H_C = 1.5
OMEGA_LIMIT = 0.73
PRECISION_GRADIENT_LIMIT = 1.20e-4
PRIMARY_MAX_BLOCKS = 4
COMPARISON_MAX_BLOCKS = 6
CANDIDATES = (
    {"label": "half_reference", "multiplier": 0.50, "h_C": 2.9598260763447164},
    {"label": "three_quarters_reference", "multiplier": 0.75, "h_C": 4.439739114517074},
    {"label": "reference", "multiplier": 1.00, "h_C": 5.919652152689433},
    {"label": "five_quarters_reference", "multiplier": 1.25, "h_C": 7.399565190861791},
    {"label": "three_halves_reference", "multiplier": 1.50, "h_C": 8.879478229034149},
)
SOURCE_COMPARE_ABS = 1.0e-8
SOURCE_COMPARE_REL = 1.0e-6


class CampaignFailure(RuntimeError):
    """Raised when a frozen campaign requirement is not met."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CampaignFailure(f"JSON root is not an object: {path}")
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def finite_tree(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, Mapping):
        return all(finite_tree(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(finite_tree(item) for item in value)
    return False


def coefficient_vector(h_c: float) -> dict[str, float]:
    return {**FIXED_COEFFICIENTS, "h_C": float(h_c)}


def configure_coefficients(h_c: float) -> dict[str, float]:
    vector = coefficient_vector(h_c)
    if set(stationary.COEFFICIENTS) != set(vector):
        raise CampaignFailure("stationary coefficient key set changed")
    stationary.COEFFICIENTS.clear()
    stationary.COEFFICIENTS.update(vector)
    return vector


def verify_manifest() -> tuple[dict[str, Any], str]:
    manifest = read_json(MANIFEST_PATH)
    if manifest.get("schema") != "cassi.particle-carrier-localization.manifest.v1":
        raise CampaignFailure("localization manifest schema mismatch")
    expected_source = {
        "artifact": str(SOURCE_ARTIFACT.relative_to(ROOT)).replace("\\", "/"),
        "artifact_sha256": SOURCE_HASHES["artifact"],
        "results": str(SOURCE_RESULTS.relative_to(ROOT)).replace("\\", "/"),
        "results_sha256": SOURCE_HASHES["results"],
        "verification": str(SOURCE_VERIFICATION.relative_to(ROOT)).replace("\\", "/"),
        "verification_sha256": SOURCE_HASHES["verification"],
        "selected_block": 1,
        "source_h_C": SOURCE_H_C,
    }
    if manifest.get("source") != expected_source:
        raise CampaignFailure("manifest source declaration changed")
    if manifest.get("fixed_coefficients") != FIXED_COEFFICIENTS:
        raise CampaignFailure("manifest fixed coefficient vector changed")
    if manifest.get("candidates") != list(CANDIDATES):
        raise CampaignFailure("manifest candidate grid changed")
    expected_schedule = {
        "precision_gradient_limit": PRECISION_GRADIENT_LIMIT,
        "omega_limit": OMEGA_LIMIT,
        "primary_max_blocks": PRIMARY_MAX_BLOCKS,
        "comparison_max_blocks": COMPARISON_MAX_BLOCKS,
        "primary_families": ["P"],
        "comparison_families": ["D", "H"],
        "comparison_basin": "separated_core",
        "continuation": recovery.CONTINUATION,
    }
    if manifest.get("schedule") != expected_schedule:
        raise CampaignFailure("manifest schedule changed")
    hashes = manifest.get("sha256")
    if not isinstance(hashes, dict) or not hashes:
        raise CampaignFailure("manifest has no source hashes")
    mismatches = []
    for relative, expected in hashes.items():
        path = ROOT / relative
        actual = sha256_file(path) if path.is_file() else "MISSING"
        if actual != expected:
            mismatches.append({"path": relative, "expected": expected, "actual": actual})
    if mismatches:
        raise CampaignFailure(f"manifest hash mismatch: {mismatches}")
    return manifest, sha256_file(MANIFEST_PATH)


def configure_torch() -> torch.device:
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "0":
        raise CampaignFailure("CUDA_VISIBLE_DEVICES must equal 0")
    if not torch.cuda.is_available():
        raise CampaignFailure("ROCm device exposed as cuda:0 is unavailable")
    torch.set_default_dtype(torch.float64)
    torch.use_deterministic_algorithms(True)
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
    }


def close(actual: float, expected: float) -> bool:
    return abs(actual - expected) <= SOURCE_COMPARE_ABS + SOURCE_COMPARE_REL * abs(expected)


def compare_numeric_tree(
    actual: Any, expected: Any, path: str, failures: list[str]
) -> None:
    if isinstance(expected, bool):
        if actual is not expected:
            failures.append(f"{path}: expected {expected!r}, got {actual!r}")
        return
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            failures.append(f"{path}: expected numeric value, got {actual!r}")
        elif not math.isfinite(float(actual)) or not close(float(actual), float(expected)):
            failures.append(f"{path}: expected {expected!r}, got {actual!r}")
        return
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping):
            failures.append(f"{path}: expected object, got {type(actual).__name__}")
            return
        if set(actual) != set(expected):
            failures.append(
                f"{path}: key mismatch expected {sorted(expected)}, got {sorted(actual)}"
            )
            return
        for key, value in expected.items():
            compare_numeric_tree(actual[key], value, f"{path}.{key}", failures)
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            failures.append(f"{path}: list shape mismatch")
            return
        for index, value in enumerate(expected):
            compare_numeric_tree(actual[index], value, f"{path}[{index}]", failures)
        return
    if actual != expected:
        failures.append(f"{path}: expected {expected!r}, got {actual!r}")


def source_balance(diagnostics: Mapping[str, Any]) -> dict[str, float]:
    components = diagnostics["energy_components"]
    charge = float(diagnostics["charge"])
    depletion_overlap = (
        FIXED_COEFFICIENTS["e_C"] * charge
        - float(components["carrier_quadratic"])
    ) / SOURCE_H_C
    quartic_integral = (
        2.0 * float(components["carrier_quartic"]) / FIXED_COEFFICIENTS["u_C"]
    )
    positive_cost = float(components["carrier_gradient"]) + (
        FIXED_COEFFICIENTS["u_C"] * quartic_integral
    )
    zero_margin_h_c = positive_cost / depletion_overlap
    reference_h_c = (
        positive_cost
        + charge * (FIXED_COEFFICIENTS["e_C"] - OMEGA_LIMIT)
    ) / depletion_overlap
    return {
        "depletion_overlap": depletion_overlap,
        "quartic_integral": quartic_integral,
        "positive_cost": positive_cost,
        "source_retention_margin": float(diagnostics["omega_c"])
        - FIXED_COEFFICIENTS["e_C"],
        "zero_margin_h_C": zero_margin_h_c,
        "reference_h_C": reference_h_c,
    }


def source_shell_receipt(arrays: Mapping[str, np.ndarray]) -> dict[str, Any]:
    n = int(arrays["x"].shape[0])
    shell = np.ones((n, n, n), dtype=np.bool_)
    shell[1:-1, 1:-1, 1:-1] = False
    psi_inf = np.array(
        (stationary.PHI**-0.5, stationary.PHI**-1.0), dtype=np.float64
    )
    h_inf = np.array((0.0, 0.0, 1.0), dtype=np.float64)
    residuals = {
        "psi_real": float(np.max(np.abs(arrays["psi_real"][shell] - psi_inf))),
        "psi_imag": float(np.max(np.abs(arrays["psi_imag"][shell]))),
        "h": float(np.max(np.abs(arrays["h"][shell] - h_inf))),
        "a": float(np.max(np.abs(arrays["a"][shell]))),
        "c": float(np.max(np.abs(arrays["c"][shell]))),
    }
    maximum = max(residuals.values())
    return {
        "residuals": residuals,
        "maximum": maximum,
        "tolerance": 1.0e-12,
        "pass": maximum <= 1.0e-12,
    }


def load_source(
    device: torch.device,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    paths = {
        "artifact": SOURCE_ARTIFACT,
        "results": SOURCE_RESULTS,
        "verification": SOURCE_VERIFICATION,
    }
    for name, path in paths.items():
        if sha256_file(path) != SOURCE_HASHES[name]:
            raise CampaignFailure(f"source {name} hash mismatch")
    results = read_json(SOURCE_RESULTS)
    verification = read_json(SOURCE_VERIFICATION)
    if results.get("primary_verdict") != "PASS—HIGHER-PRECISION BACKGROUND":
        raise CampaignFailure("source result verdict mismatch")
    if results.get("selected_block") != 1:
        raise CampaignFailure("source selected block mismatch")
    if results.get("selected_artifact_sha256") != SOURCE_HASHES["artifact"]:
        raise CampaignFailure("source result artifact hash mismatch")
    if verification.get("pass") is not True or verification.get("mismatches"):
        raise CampaignFailure("source independent verification is not clean")
    if verification.get("selected_artifact_sha256") != SOURCE_HASHES["artifact"]:
        raise CampaignFailure("source verification artifact hash mismatch")
    selected = next(
        (row for row in results.get("blocks", []) if row.get("block") == 1), None
    )
    if not isinstance(selected, dict) or selected.get("artifact_sha256") != SOURCE_HASHES["artifact"]:
        raise CampaignFailure("source selected block is absent or changed")

    arrays = recovery.load_arrays(SOURCE_ARTIFACT)
    schema_failures = recovery.validate_npz_arrays(arrays, "P")
    if schema_failures:
        raise CampaignFailure(f"source artifact schema failure: {schema_failures}")
    shell = source_shell_receipt(arrays)
    if not shell["pass"]:
        raise CampaignFailure(f"source shell mismatch: {shell}")
    configure_coefficients(SOURCE_H_C)
    grid = stationary.make_grid("P", device)
    raw, reconstruction = recovery.reconstruct_raw(arrays, grid)
    if (
        not reconstruction["raw_finite"]
        or reconstruction["maximum_relative_inf"] > recovery.ROUNDTRIP_TOL
    ):
        raise CampaignFailure(f"source reconstruction failure: {reconstruction}")
    diagnostics, _ = stationary.diagnostics(raw, grid)
    failures: list[str] = []
    compare_numeric_tree(
        diagnostics, selected.get("diagnostics"), "source.diagnostics", failures
    )
    if failures:
        raise CampaignFailure(f"source diagnostic mismatch: {failures}")
    balance = source_balance(diagnostics)
    if not close(balance["reference_h_C"], CANDIDATES[2]["h_C"]):
        raise CampaignFailure("source retention reference changed")
    for candidate in CANDIDATES:
        expected = candidate["multiplier"] * balance["reference_h_C"]
        if not close(candidate["h_C"], expected):
            raise CampaignFailure(f"candidate value changed: {candidate['label']}")
    return arrays, {
        "artifact": str(SOURCE_ARTIFACT.relative_to(ROOT)).replace("\\", "/"),
        "artifact_sha256": SOURCE_HASHES["artifact"],
        "results_sha256": SOURCE_HASHES["results"],
        "verification_sha256": SOURCE_HASHES["verification"],
        "selected_block": 1,
        "coefficient_vector": coefficient_vector(SOURCE_H_C),
        "schema": {
            name: {
                "shape": list(value.shape),
                "dtype": str(value.dtype),
                "c_contiguous": bool(value.flags.c_contiguous),
                "finite": bool(np.all(np.isfinite(value))),
            }
            for name, value in arrays.items()
        },
        "shell": shell,
        "reconstruction": reconstruction,
        "diagnostics": diagnostics,
        "retention_balance": balance,
    }


def quality_checks(diagnostics: Mapping[str, Any] | None) -> dict[str, bool]:
    if diagnostics is None:
        return {
            "charge_and_boundary": False,
            "physical_stationarity": False,
            "gauge_control": False,
            "outer_flux_control": False,
        }
    return {
        "charge_and_boundary": (
            float(diagnostics["charge_relative_error"]) <= 5.0e-12
            and float(diagnostics["boundary_residual"]) <= 1.0e-12
        ),
        "physical_stationarity": (
            float(diagnostics["physical_gradient_rms"]) <= PRECISION_GRADIENT_LIMIT
            and float(diagnostics["cutoff_virial"]) <= 0.08
        ),
        "gauge_control": (
            float(diagnostics["gauge_divergence_rms"]) <= 0.02
            and float(diagnostics["gauge_fixing_fraction"]) <= 0.01
        ),
        "outer_flux_control": (
            float(diagnostics["outer_flux_rms"]) <= 0.05
            and abs(float(diagnostics["outer_magnetic_number"])) <= 1.0e-10
        ),
    }


def localization_checks(
    diagnostics: Mapping[str, Any] | None, radius_limit: float
) -> dict[str, bool]:
    if diagnostics is None:
        return {
            "outer_carrier_fraction": False,
            "carrier_radius": False,
            "retention_margin": False,
            "density_depletion": False,
        }
    return {
        "outer_carrier_fraction": float(diagnostics["outer_carrier_fraction"])
        <= 1.0e-3,
        "carrier_radius": float(diagnostics["carrier_radius"]) < radius_limit,
        "retention_margin": float(diagnostics["omega_c"]) < OMEGA_LIMIT,
        "density_depletion": float(diagnostics["max_density_depletion"]) >= 0.10,
    }


def run_continuation_arm(
    *,
    label: str,
    family: str,
    h_c: float,
    raw: dict[str, torch.nn.Parameter],
    grid: stationary.Grid,
    max_blocks: int,
    initial_optimizer: dict[str, Any] | None,
    reconstruction: dict[str, Any] | None,
) -> dict[str, Any]:
    vector = configure_coefficients(h_c)
    arm: dict[str, Any] = {
        "label": label,
        "family": family,
        "basin": "separated_core",
        "R": grid.R,
        "N": grid.N,
        "dx": grid.dx,
        "h_C": h_c,
        "coefficient_vector": vector,
        "max_blocks": max_blocks,
        "initial_optimizer": initial_optimizer,
        "source_reconstruction": reconstruction,
        "blocks": [],
        "terminal_block": None,
        "terminal_artifact": None,
        "terminal_artifact_sha256": None,
        "diagnostics": None,
        "quality_checks": quality_checks(None),
        "localization_checks": localization_checks(None, grid.R / 2.0),
        "numerically_qualified": False,
        "localized_and_retained": False,
        "completed": False,
        "error": None,
    }
    try:
        for block_index in range(1, max_blocks + 1):
            started = time.perf_counter()
            optimizer = recovery.continue_lbfgs(raw, grid)
            diagnostics, fields = stationary.diagnostics(raw, grid)
            if not finite_tree(optimizer) or not finite_tree(diagnostics):
                raise CampaignFailure("nonfinite optimizer or diagnostic receipt")
            artifact_name = f"fields_{label}_block{block_index:02d}.npz"
            artifact_path = RUN_DIR / artifact_name
            stationary.save_fields(artifact_path, fields, grid)
            block_quality = quality_checks(diagnostics)
            block_localization = localization_checks(diagnostics, grid.R / 2.0)
            qualified = all(block_quality.values())
            localized = qualified and all(block_localization.values())
            block = {
                "block": block_index,
                "wall_seconds_total": time.perf_counter() - started,
                "optimizer": optimizer,
                "artifact": artifact_name,
                "artifact_sha256": sha256_file(artifact_path),
                "diagnostics": diagnostics,
                "quality_checks": block_quality,
                "localization_checks": block_localization,
                "numerically_qualified": qualified,
                "localized_and_retained": localized,
            }
            arm["blocks"].append(block)
            print(
                f"DONE {label} block {block_index}: "
                f"h_C={h_c:.12g} "
                f"grad={diagnostics['physical_gradient_rms']:.12g} "
                f"omega={diagnostics['omega_c']:.12g} "
                f"radius={diagnostics['carrier_radius']:.12g} "
                f"outer={diagnostics['outer_carrier_fraction']:.12g}",
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
                    "numerically_qualified": terminal["numerically_qualified"],
                    "localized_and_retained": terminal["localized_and_retained"],
                }
            )
        arm["completed"] = True
    except Exception as error:
        arm["error"] = f"{type(error).__name__}: {error}"
    return arm


def comparison_metrics(primary: Mapping[str, Any], other: Mapping[str, Any]) -> dict[str, Any]:
    p = primary["diagnostics"]
    o = other["diagnostics"]
    if not isinstance(p, Mapping) or not isinstance(o, Mapping):
        raise CampaignFailure("comparison arm has no diagnostics")

    def relative_difference(left: float, right: float) -> float:
        return abs(left - right) / max(abs(left), abs(right), 1.0e-12)

    metrics = {
        "energy_relative_difference": relative_difference(
            float(p["physical_energy"]), float(o["physical_energy"])
        ),
        "core_length_absolute_difference": abs(
            float(p["core_length"]) - float(o["core_length"])
        ),
        "omega_absolute_difference": abs(float(p["omega_c"]) - float(o["omega_c"])),
        "radius_relative_difference": relative_difference(
            float(p["carrier_radius"]), float(o["carrier_radius"])
        ),
    }
    metrics["pass"] = (
        metrics["energy_relative_difference"] <= 0.05
        and metrics["core_length_absolute_difference"] <= 0.75
        and metrics["omega_absolute_difference"] <= 0.10
        and metrics["radius_relative_difference"] <= 0.10
    )
    return metrics


def run() -> dict[str, Any]:
    if RUN_DIR.is_dir():
        unexpected = sorted(path.name for path in RUN_DIR.iterdir() if path != PREFLIGHT_PATH)
        if unexpected:
            raise CampaignFailure(
                f"localization output path is immutable and not fresh: {unexpected}"
            )
    device = configure_torch()
    manifest, manifest_sha256 = verify_manifest()
    if not PREFLIGHT_PATH.is_file():
        raise CampaignFailure(
            "run verify_particle_carrier_localization.py --preflight first"
        )
    preflight = read_json(PREFLIGHT_PATH)
    if preflight.get("pass") is not True:
        raise CampaignFailure("independent localization preflight did not pass")
    if preflight.get("manifest_sha256") != manifest_sha256:
        raise CampaignFailure("independent preflight manifest hash mismatch")

    source_arrays, source_info = load_source(device)
    source_quality = quality_checks(source_info["diagnostics"])
    source_localization = localization_checks(source_info["diagnostics"], 2.0)
    source_info["quality_checks"] = source_quality
    source_info["localization_checks"] = source_localization
    source_info["numerically_qualified"] = all(source_quality.values())
    source_info["localized_and_retained"] = all(source_quality.values()) and all(
        source_localization.values()
    )
    if not source_info["numerically_qualified"] or source_info["localized_and_retained"]:
        raise CampaignFailure("source control classification changed")

    receipt: dict[str, Any] = {
        "schema": "cassi.particle-carrier-localization.results.v1",
        "status": "in_progress",
        "manifest": manifest,
        "manifest_sha256": manifest_sha256,
        "environment": environment_receipt(device),
        "source": source_info,
        "candidate_order": [row["label"] for row in CANDIDATES],
        "primary_scan": [],
        "selected_primary": None,
        "comparison_order": [],
        "comparison_arms": {},
        "comparisons": {},
        "campaign_checks": {
            "source_control_reproduced": True,
            "planned_primary_scan_completed": None,
            "localized_primary_found": None,
            "comparison_grids_numerically_qualified": None,
            "comparison_grids_localized_and_retained": None,
            "domain_and_resolution_match": None,
        },
        "primary_verdict": None,
    }
    write_json(RESULTS_PATH, receipt)

    grid = stationary.make_grid("P", device)
    for candidate in CANDIDATES:
        raw, reconstruction = recovery.reconstruct_raw(source_arrays, grid)
        if (
            not reconstruction["raw_finite"]
            or reconstruction["maximum_relative_inf"] > recovery.ROUNDTRIP_TOL
        ):
            raise CampaignFailure(
                f"candidate reconstruction failure: {candidate['label']}"
            )
        print(
            f"RUN primary {candidate['label']} at h_C={candidate['h_C']:.15g}",
            flush=True,
        )
        arm = run_continuation_arm(
            label=f"primary_{candidate['label']}",
            family="P",
            h_c=float(candidate["h_C"]),
            raw=raw,
            grid=grid,
            max_blocks=PRIMARY_MAX_BLOCKS,
            initial_optimizer=None,
            reconstruction=reconstruction,
        )
        receipt["primary_scan"].append(arm)
        write_json(RESULTS_PATH, receipt)
        if arm["numerically_qualified"] and arm["localized_and_retained"]:
            receipt["selected_primary"] = {
                "label": candidate["label"],
                "h_C": candidate["h_C"],
                "scan_index": len(receipt["primary_scan"]) - 1,
                "artifact": arm["terminal_artifact"],
                "artifact_sha256": arm["terminal_artifact_sha256"],
            }
            break

    receipt["campaign_checks"]["planned_primary_scan_completed"] = (
        receipt["selected_primary"] is not None
        or len(receipt["primary_scan"]) == len(CANDIDATES)
    )
    receipt["campaign_checks"]["localized_primary_found"] = (
        receipt["selected_primary"] is not None
    )

    any_primary_unqualified = any(
        not arm["numerically_qualified"] for arm in receipt["primary_scan"]
    )
    if receipt["selected_primary"] is None:
        verdict = (
            "INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION"
            if any_primary_unqualified
            else "DOES NOT EMERGE—NO LOCALIZED RETAINED PRIMARY IN FROZEN BRACKET"
        )
    else:
        selected_index = int(receipt["selected_primary"]["scan_index"])
        primary = receipt["primary_scan"][selected_index]
        selected_h = float(receipt["selected_primary"]["h_C"])
        for family in ("D", "H"):
            configure_coefficients(selected_h)
            comparison_grid = stationary.make_grid(family, device)
            raw = stationary.raw_parameters("separated_core", comparison_grid)
            print(
                f"RUN {family} comparison from analytic separated-core seed at "
                f"h_C={selected_h:.15g}",
                flush=True,
            )
            try:
                initial_optimizer = stationary.optimize_arm(raw, comparison_grid)
                arm = run_continuation_arm(
                    label=f"comparison_{family}",
                    family=family,
                    h_c=selected_h,
                    raw=raw,
                    grid=comparison_grid,
                    max_blocks=COMPARISON_MAX_BLOCKS,
                    initial_optimizer=initial_optimizer,
                    reconstruction=None,
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
                    "max_blocks": COMPARISON_MAX_BLOCKS,
                    "initial_optimizer": None,
                    "source_reconstruction": None,
                    "blocks": [],
                    "terminal_block": None,
                    "terminal_artifact": None,
                    "terminal_artifact_sha256": None,
                    "diagnostics": None,
                    "quality_checks": quality_checks(None),
                    "localization_checks": localization_checks(
                        None, comparison_grid.R / 2.0
                    ),
                    "numerically_qualified": False,
                    "localized_and_retained": False,
                    "completed": False,
                    "error": f"{type(error).__name__}: {error}",
                }
            receipt["comparison_order"].append(family)
            receipt["comparison_arms"][family] = arm
            write_json(RESULTS_PATH, receipt)

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
            comparisons_localized = all(
                receipt["comparison_arms"][family]["localized_and_retained"]
                for family in ("D", "H")
            )
            receipt["campaign_checks"][
                "comparison_grids_localized_and_retained"
            ] = comparisons_localized
            for family in ("D", "H"):
                receipt["comparisons"][family] = comparison_metrics(
                    primary, receipt["comparison_arms"][family]
                )
            comparisons_match = all(
                row["pass"] for row in receipt["comparisons"].values()
            )
            domain_and_resolution_match = comparisons_localized and comparisons_match
            receipt["campaign_checks"][
                "domain_and_resolution_match"
            ] = domain_and_resolution_match
            verdict = (
                "EMERGES—DOMAIN-AND-RESOLUTION-MATCHED LOCALIZED RETAINED BRANCH"
                if domain_and_resolution_match
                else "EMERGES—FINITE-GRID LOCALIZED RETAINED BRANCH ONLY"
            )

    receipt["primary_verdict"] = verdict
    receipt["status"] = "complete"
    write_json(RESULTS_PATH, receipt)
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
        write_json(
            RUN_DIR / "failure.json",
            {
                "schema": "cassi.particle-carrier-localization.failure.v1",
                "error": f"{type(error).__name__}: {error}",
            },
        )
        raise
