#!/usr/bin/env python3
"""Run the preregistered higher-precision particle continuation campaign."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch

import particle_stationary_bvp as stationary
import particle_stationary_q2_recovery_v2 as recovery


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "runs" / "20260902_particle_stationary_q2_recovery_v2"
SOURCE_ARTIFACT = SOURCE_DIR / "fields_P_separated_core.npz"
SOURCE_RESULTS = SOURCE_DIR / "results.json"
SOURCE_VERIFICATION = SOURCE_DIR / "verification.json"
RUN_DIR = ROOT / "runs" / "20260902_particle_stationary_precision_v3"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
RESULTS_PATH = RUN_DIR / "results.json"
MANIFEST_PATH = ROOT / "computations" / "particle_stationary_precision_v3_manifest.json"
SOURCE_ARTIFACT_SHA256 = "99766cddb04107bb0c103c8f96254df651094054578867d37662ee7bff7e2550"
SOURCE_SCALARS = {
    "physical_energy": 3.8542001269281165,
    "physical_gradient_rms": 1.936974511462466e-4,
    "cutoff_virial": 1.8910102042201137e-3,
    "omega_c": 0.9619135625713447,
    "charge": 4.0,
}
SOURCE_BASIN = "separated_core"
TARGET_GRADIENT_RMS = 1.20e-4
MAX_BLOCKS = 8
TEXT_SUFFIXES = {".json", ".md", ".py"}


class PrecisionFailure(RuntimeError):
    """Raised when a frozen precision-campaign requirement fails."""


def sha256_file(path: Path) -> str:
    payload = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        payload = payload.replace(b"\r\n", b"\n")
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PrecisionFailure(f"{path} does not contain a JSON object")
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, newline="\n"
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def verify_manifest() -> tuple[dict[str, Any], str]:
    manifest = read_json(MANIFEST_PATH)
    if manifest.get("schema") != "cassi.particle-stationary-precision.manifest.v1":
        raise PrecisionFailure("precision manifest schema mismatch")
    hashes = manifest.get("sha256")
    if not isinstance(hashes, dict) or not hashes:
        raise PrecisionFailure("precision manifest has no source hashes")
    mismatches: list[dict[str, str]] = []
    for relative, expected in hashes.items():
        path = ROOT / relative
        actual = sha256_file(path) if path.is_file() else "MISSING"
        if actual != expected:
            mismatches.append({"path": relative, "expected": str(expected), "actual": actual})
    if mismatches:
        raise PrecisionFailure(f"precision manifest mismatch: {mismatches}")
    return manifest, sha256_file(MANIFEST_PATH)


def configure_torch() -> torch.device:
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "0":
        raise PrecisionFailure("CUDA_VISIBLE_DEVICES must equal 0")
    if not torch.cuda.is_available():
        raise PrecisionFailure("ROCm device exposed as cuda:0 is unavailable")
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


def load_source(device: torch.device) -> tuple[dict[str, torch.nn.Parameter], dict[str, Any]]:
    if sha256_file(SOURCE_ARTIFACT) != SOURCE_ARTIFACT_SHA256:
        raise PrecisionFailure("source artifact hash mismatch")
    source_results = read_json(SOURCE_RESULTS)
    source_verification = read_json(SOURCE_VERIFICATION)
    source_arm = source_results.get("arms", {}).get(f"P:{SOURCE_BASIN}")
    if not isinstance(source_arm, dict):
        raise PrecisionFailure("selected source arm is absent")
    if source_arm.get("artifact_sha256") != SOURCE_ARTIFACT_SHA256:
        raise PrecisionFailure("selected source receipt hash mismatch")
    if source_results.get("primary_verdict") != "PASS—Q2-QUALIFIED PRIMARY BACKGROUND":
        raise PrecisionFailure("selected source receipt verdict mismatch")
    if source_verification.get("pass") is not True or source_verification.get("mismatches"):
        raise PrecisionFailure("selected source verification is not clean")

    arrays = recovery.load_arrays(SOURCE_ARTIFACT)
    schema_failures = recovery.validate_npz_arrays(arrays, "P")
    if schema_failures:
        raise PrecisionFailure(f"source artifact schema failure: {schema_failures}")
    grid = stationary.make_grid("P", device)
    raw, reconstruction = recovery.reconstruct_raw(arrays, grid)
    if not reconstruction["raw_finite"] or reconstruction["maximum_relative_inf"] > recovery.ROUNDTRIP_TOL:
        raise PrecisionFailure(f"source reconstruction failure: {reconstruction}")
    diagnostics, _ = stationary.diagnostics(raw, grid)
    scalar_checks: dict[str, Any] = {}
    for name, frozen in SOURCE_SCALARS.items():
        measured = float(diagnostics[name])
        tolerance = 1.0e-11 + 1.0e-9 * abs(frozen)
        error = abs(measured - frozen)
        scalar_checks[name] = {
            "measured": measured,
            "frozen": frozen,
            "error": error,
            "tolerance": tolerance,
            "pass": error <= tolerance,
        }
    if not all(row["pass"] for row in scalar_checks.values()):
        raise PrecisionFailure(f"source scalar mismatch: {scalar_checks}")
    return raw, {
        "artifact": str(SOURCE_ARTIFACT.relative_to(ROOT)).replace("\\", "/"),
        "artifact_sha256": SOURCE_ARTIFACT_SHA256,
        "schema": {
            name: {
                "shape": list(value.shape),
                "dtype": str(value.dtype),
                "c_contiguous": bool(value.flags.c_contiguous),
                "finite": bool(np.all(np.isfinite(value))),
            }
            for name, value in arrays.items()
        },
        "reconstruction": reconstruction,
        "scalars": scalar_checks,
    }


def finite_tree(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(finite_tree(item) for item in value.values())
    if isinstance(value, list):
        return all(finite_tree(item) for item in value)
    return False


def run() -> dict[str, Any]:
    if RUN_DIR.is_dir():
        unexpected = sorted(
            path.name for path in RUN_DIR.iterdir() if path != PREFLIGHT_PATH
        )
        if unexpected:
            raise PrecisionFailure(
                f"precision output path is immutable and not fresh: {unexpected}"
            )
    device = configure_torch()
    manifest, manifest_sha256 = verify_manifest()
    if not PREFLIGHT_PATH.is_file():
        raise PrecisionFailure("run verify_particle_stationary_precision_v3.py --preflight first")
    independent_preflight = read_json(PREFLIGHT_PATH)
    if independent_preflight.get("pass") is not True:
        raise PrecisionFailure("independent precision preflight did not pass")
    if independent_preflight.get("manifest_sha256") != manifest_sha256:
        raise PrecisionFailure("independent preflight manifest hash mismatch")

    raw, source_info = load_source(device)
    grid = stationary.make_grid("P", device)
    receipt: dict[str, Any] = {
        "schema": "cassi.particle-stationary-precision.results.v1",
        "status": "in_progress",
        "manifest": manifest,
        "manifest_sha256": manifest_sha256,
        "environment": environment_receipt(device),
        "source": source_info,
        "target_gradient_rms": TARGET_GRADIENT_RMS,
        "max_blocks": MAX_BLOCKS,
        "continuation": recovery.CONTINUATION,
        "blocks": [],
        "selected_block": None,
        "selected_artifact": None,
        "selected_artifact_sha256": None,
        "gates": {"HP-A": True, "HP-B": None, "HP-C": None, "HP-D": None},
        "primary_verdict": None,
    }
    write_json(RESULTS_PATH, receipt)

    execution_failed = False
    for block_index in range(1, MAX_BLOCKS + 1):
        print(f"RUN precision block {block_index}/{MAX_BLOCKS}", flush=True)
        row: dict[str, Any]
        started = time.perf_counter()
        try:
            optimizer = recovery.continue_lbfgs(raw, grid)
            diagnostics, fields = stationary.diagnostics(raw, grid)
            artifact_name = f"fields_block{block_index:02d}.npz"
            artifact_path = RUN_DIR / artifact_name
            stationary.save_fields(artifact_path, fields, grid)
            artifact_hash = sha256_file(artifact_path)
            gates = stationary.q1_q4(True, diagnostics)
            completed = finite_tree(optimizer) and finite_tree(diagnostics)
            qualified = (
                completed
                and all(gates.values())
                and float(diagnostics["physical_gradient_rms"]) <= TARGET_GRADIENT_RMS
            )
            row = {
                "block": block_index,
                "completed": completed,
                "error": None,
                "wall_seconds_total": time.perf_counter() - started,
                "optimizer": optimizer,
                "artifact": artifact_name,
                "artifact_sha256": artifact_hash,
                "diagnostics": diagnostics,
                "gates": gates,
                "precision_target_pass": qualified,
            }
        except Exception as error:
            execution_failed = True
            row = {
                "block": block_index,
                "completed": False,
                "error": f"{type(error).__name__}: {error}",
                "wall_seconds_total": time.perf_counter() - started,
                "optimizer": None,
                "artifact": None,
                "artifact_sha256": None,
                "diagnostics": None,
                "gates": None,
                "precision_target_pass": False,
            }
        receipt["blocks"].append(row)
        write_json(RESULTS_PATH, receipt)
        if execution_failed:
            break
        diagnostics_row = row["diagnostics"]
        if not isinstance(diagnostics_row, dict):
            raise PrecisionFailure("completed block has no diagnostics")
        print(
            f"DONE block {block_index}: "
            f"E={diagnostics_row['physical_energy']:.12g} "
            f"grad={diagnostics_row['physical_gradient_rms']:.12g} "
            f"virial={diagnostics_row['cutoff_virial']:.12g}",
            flush=True,
        )
        if row["precision_target_pass"]:
            receipt["selected_block"] = block_index
            receipt["selected_artifact"] = row["artifact"]
            receipt["selected_artifact_sha256"] = row["artifact_sha256"]
            break

    hp_b = not execution_failed and all(row["completed"] for row in receipt["blocks"])
    hp_c = receipt["selected_block"] is not None
    receipt["gates"].update({"HP-B": hp_b, "HP-C": hp_c})
    if not hp_b:
        verdict = "INCONCLUSIVE—EXECUTION OR VERIFICATION"
    elif not hp_c:
        verdict = "INCONCLUSIVE—PRECISION CAP"
    else:
        verdict = "PASS—HIGHER-PRECISION BACKGROUND"
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
                "selected_block": receipt["selected_block"],
                "selected_artifact": receipt["selected_artifact"],
                "results": str(RESULTS_PATH),
            },
            sort_keys=True,
        )
    )
    return 0 if receipt["primary_verdict"] == "PASS—HIGHER-PRECISION BACKGROUND" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"PRECISION CAMPAIGN ERROR: {type(error).__name__}: {error}", flush=True)
        raise SystemExit(1)
