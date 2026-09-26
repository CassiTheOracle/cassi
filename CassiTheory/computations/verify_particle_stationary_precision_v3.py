#!/usr/bin/env python3
"""Independently verify the higher-precision particle continuation campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import verify_particle_stationary_q2_recovery_v2 as independent


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "runs" / "20260902_particle_stationary_q2_recovery_v2"
SOURCE_ARTIFACT = SOURCE_DIR / "fields_P_separated_core.npz"
SOURCE_RESULTS = SOURCE_DIR / "results.json"
SOURCE_VERIFICATION = SOURCE_DIR / "verification.json"
RUN_DIR = ROOT / "runs" / "20260902_particle_stationary_precision_v3"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
RESULTS_PATH = RUN_DIR / "results.json"
VERIFICATION_PATH = RUN_DIR / "verification.json"
MANIFEST_PATH = ROOT / "computations" / "particle_stationary_precision_v3_manifest.json"
SOURCE_ARTIFACT_SHA256 = "99766cddb04107bb0c103c8f96254df651094054578867d37662ee7bff7e2550"
SOURCE_SCALARS = {
    "physical_energy": 3.8542001269281165,
    "physical_gradient_rms": 1.936974511462466e-4,
    "cutoff_virial": 1.8910102042201137e-3,
    "omega_c": 0.9619135625713447,
    "charge": 4.0,
}
CONTINUATION = {
    "max_iter": 880,
    "max_eval": 1100,
    "history_size": 20,
    "tolerance_grad": 1.0e-10,
    "tolerance_change": 1.0e-12,
    "line_search_fn": "strong_wolfe",
}
TARGET_GRADIENT_RMS = 1.20e-4
MAX_BLOCKS = 8
ABS_TOL = 1.0e-8
REL_TOL = 1.0e-6
TEXT_SUFFIXES = {".json", ".md", ".py"}


class VerificationFailure(RuntimeError):
    """Raised when a verifier prerequisite is unavailable."""


def sha256_file(path: Path) -> str:
    payload = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        payload = payload.replace(b"\r\n", b"\n")
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VerificationFailure(f"{path} does not contain a JSON object")
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


def mismatch(
    out: list[dict[str, Any]],
    path: str,
    expected: Any,
    actual: Any,
    kind: str = "mismatch",
    tolerance: float | None = None,
) -> None:
    row: dict[str, Any] = {
        "path": path,
        "kind": kind,
        "expected": independent.json_safe(expected),
        "actual": independent.json_safe(actual),
    }
    if tolerance is not None:
        row["tolerance"] = tolerance
    out.append(row)


def compare_scalar(
    out: list[dict[str, Any]], path: str, actual: Any, expected: float
) -> None:
    tolerance = ABS_TOL + REL_TOL * abs(expected)
    if (
        not isinstance(actual, (int, float))
        or isinstance(actual, bool)
        or not math.isfinite(float(actual))
        or abs(float(actual) - expected) > tolerance
    ):
        mismatch(out, path, expected, actual, "tolerance", tolerance)


def verify_manifest(out: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    try:
        manifest = read_json(MANIFEST_PATH)
    except Exception as error:
        mismatch(out, "manifest", "readable manifest", repr(error), "read")
        return {}, "MISSING"
    if manifest.get("schema") != "cassi.particle-stationary-precision.manifest.v1":
        mismatch(
            out,
            "manifest.schema",
            "cassi.particle-stationary-precision.manifest.v1",
            manifest.get("schema"),
            "exact",
        )
    hashes = manifest.get("sha256")
    if not isinstance(hashes, dict) or not hashes:
        mismatch(out, "manifest.sha256", "nonempty object", hashes, "schema")
        return manifest, sha256_file(MANIFEST_PATH)
    for relative, expected in hashes.items():
        path = ROOT / relative
        actual = sha256_file(path) if path.is_file() else "MISSING"
        if actual != expected:
            mismatch(out, f"manifest.sha256.{relative}", expected, actual, "hash")
    return manifest, sha256_file(MANIFEST_PATH)


def source_evidence(out: list[dict[str, Any]]) -> dict[str, Any]:
    actual_hash = sha256_file(SOURCE_ARTIFACT) if SOURCE_ARTIFACT.is_file() else "MISSING"
    if actual_hash != SOURCE_ARTIFACT_SHA256:
        mismatch(out, "source.artifact_sha256", SOURCE_ARTIFACT_SHA256, actual_hash, "hash")
    try:
        source_results = read_json(SOURCE_RESULTS)
        source_verification = read_json(SOURCE_VERIFICATION)
    except Exception as error:
        mismatch(out, "source.receipts", "readable receipts", repr(error), "read")
        return {"artifact_sha256": actual_hash}
    arm = source_results.get("arms", {}).get("P:separated_core")
    if not isinstance(arm, dict):
        mismatch(out, "source.arm", "P:separated_core", arm, "schema")
    else:
        if arm.get("artifact_sha256") != SOURCE_ARTIFACT_SHA256:
            mismatch(
                out,
                "source.arm.artifact_sha256",
                SOURCE_ARTIFACT_SHA256,
                arm.get("artifact_sha256"),
                "hash",
            )
    if source_results.get("primary_verdict") != "PASS—Q2-QUALIFIED PRIMARY BACKGROUND":
        mismatch(
            out,
            "source.primary_verdict",
            "PASS—Q2-QUALIFIED PRIMARY BACKGROUND",
            source_results.get("primary_verdict"),
            "exact",
        )
    if source_verification.get("pass") is not True or source_verification.get("mismatches"):
        mismatch(out, "source.verification", "clean PASS", source_verification, "evidence")

    fields = independent.load_fields(SOURCE_ARTIFACT, "P", out, "source.fields")
    if fields is None:
        return {"artifact_sha256": actual_hash}
    try:
        reconstructed, reconstruction = independent.reconstruct_endpoint(fields)
        diagnostics = independent.recompute_diagnostics(fields)
    except Exception as error:
        mismatch(out, "source.recomputation", "successful", repr(error), "exception")
        return {"artifact_sha256": actual_hash}
    if reconstruction["maximum_relative_inf"] > 5.0e-12 or not reconstruction["raw_finite"]:
        mismatch(out, "source.reconstruction", "round trip <= 5e-12", reconstruction, "roundtrip")
    for name in independent.FIELD_KEYS:
        if name != "x":
            residual = independent.relative_inf(reconstructed[name], fields[name])
            if residual > 5.0e-12:
                mismatch(out, f"source.reconstruction.{name}", 0.0, residual, "roundtrip", 5.0e-12)
    for name, frozen in SOURCE_SCALARS.items():
        compare_scalar(out, f"source.scalars.{name}", diagnostics.get(name), frozen)
    gates = independent.quality_gates(True, diagnostics)
    if not all(gates.values()):
        mismatch(out, "source.gates", {name: True for name in gates}, gates, "exact")
    return {
        "artifact": str(SOURCE_ARTIFACT.relative_to(ROOT)).replace("\\", "/"),
        "artifact_sha256": actual_hash,
        "schema": {
            name: {
                "shape": list(value.shape),
                "dtype": str(value.dtype),
                "c_contiguous": bool(value.flags.c_contiguous),
                "finite": bool(np.all(np.isfinite(value))),
            }
            for name, value in fields.items()
        },
        "reconstruction": reconstruction,
        "diagnostics": diagnostics,
        "gates": gates,
    }


def verify_embedded_source(
    out: list[dict[str, Any]], reported: Any, fresh: Mapping[str, Any]
) -> None:
    if not isinstance(reported, dict):
        mismatch(out, "results.source", "source object", reported, "schema")
        return
    for key in ("artifact", "artifact_sha256", "schema"):
        if reported.get(key) != fresh.get(key):
            mismatch(
                out,
                f"results.source.{key}",
                fresh.get(key),
                reported.get(key),
                "exact",
            )
    reconstruction = reported.get("reconstruction")
    if (
        not isinstance(reconstruction, dict)
        or reconstruction.get("raw_finite") is not True
        or not isinstance(reconstruction.get("maximum_relative_inf"), (int, float))
        or float(reconstruction["maximum_relative_inf"]) > 5.0e-12
    ):
        mismatch(
            out,
            "results.source.reconstruction",
            "finite round trip <= 5e-12",
            reconstruction,
            "roundtrip",
        )
    scalars = reported.get("scalars")
    if not isinstance(scalars, dict):
        mismatch(out, "results.source.scalars", "scalar-check object", scalars, "schema")
        return
    for name, frozen in SOURCE_SCALARS.items():
        row = scalars.get(name)
        if not isinstance(row, dict):
            mismatch(out, f"results.source.scalars.{name}", "check object", row, "schema")
            continue
        compare_scalar(out, f"results.source.scalars.{name}.measured", row.get("measured"), frozen)
        if row.get("frozen") != frozen or row.get("pass") is not True:
            mismatch(
                out,
                f"results.source.scalars.{name}.frozen_check",
                {"frozen": frozen, "pass": True},
                {"frozen": row.get("frozen"), "pass": row.get("pass")},
                "exact",
            )




def run_preflight() -> int:
    if RUN_DIR.exists() and any(RUN_DIR.iterdir()):
        raise VerificationFailure("precision run directory is not fresh")
    mismatches: list[dict[str, Any]] = []
    manifest, manifest_sha256 = verify_manifest(mismatches)
    source = source_evidence(mismatches)
    report = {
        "schema": "cassi.particle-stationary-precision.preflight.v1",
        "pass": not mismatches,
        "mismatches": mismatches,
        "manifest": manifest,
        "manifest_sha256": manifest_sha256,
        "source": source,
        "target_gradient_rms": TARGET_GRADIENT_RMS,
        "max_blocks": MAX_BLOCKS,
        "continuation": CONTINUATION,
    }
    write_json(PREFLIGHT_PATH, report)
    print(json.dumps({"pass": report["pass"], "mismatches": len(mismatches)}, sort_keys=True))
    return 0 if report["pass"] else 1


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


def validate_optimizer(
    out: list[dict[str, Any]], path: str, optimizer: Any
) -> None:
    if not isinstance(optimizer, dict):
        mismatch(out, path, "optimizer object", optimizer, "schema")
        return
    if optimizer.get("settings") != CONTINUATION:
        mismatch(out, f"{path}.settings", CONTINUATION, optimizer.get("settings"), "exact")
    history = optimizer.get("history")
    if not isinstance(history, list) or not history:
        mismatch(out, f"{path}.history", "nonempty list", history, "schema")
    elif not finite_tree(history):
        mismatch(out, f"{path}.history", "finite values", history, "nonfinite")
    for key, upper in (("iterations", 880), ("function_evaluations", 1100)):
        value = optimizer.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= upper:
            mismatch(out, f"{path}.{key}", f"integer in [0,{upper}]", value, "range")
    closures = optimizer.get("closure_calls")
    if not isinstance(closures, int) or isinstance(closures, bool) or closures < 1:
        mismatch(out, f"{path}.closure_calls", "positive integer", closures, "range")
    if isinstance(history, list) and isinstance(closures, int) and len(history) != closures:
        mismatch(out, f"{path}.history_length", closures, len(history), "exact")
    if not finite_tree(optimizer.get("final")):
        mismatch(out, f"{path}.final", "finite values", optimizer.get("final"), "nonfinite")


def verify_checkpoint(
    out: list[dict[str, Any]], row: Any, expected_block: int
) -> dict[str, Any] | None:
    path = f"blocks[{expected_block - 1}]"
    if not isinstance(row, dict):
        mismatch(out, path, "checkpoint object", row, "schema")
        return None
    if row.get("block") != expected_block:
        mismatch(out, f"{path}.block", expected_block, row.get("block"), "exact")
    if row.get("completed") is not True or row.get("error") is not None:
        mismatch(out, f"{path}.completed", True, row.get("completed"), "exact")
        return None
    validate_optimizer(out, f"{path}.optimizer", row.get("optimizer"))
    artifact = row.get("artifact")
    expected_artifact = f"fields_block{expected_block:02d}.npz"
    if artifact != expected_artifact:
        mismatch(out, f"{path}.artifact", expected_artifact, artifact, "exact")
        return None
    artifact_path = RUN_DIR / artifact
    actual_hash = sha256_file(artifact_path) if artifact_path.is_file() else "MISSING"
    if actual_hash != row.get("artifact_sha256"):
        mismatch(out, f"{path}.artifact_sha256", row.get("artifact_sha256"), actual_hash, "hash")
    fields = independent.load_fields(artifact_path, "P", out, f"{path}.fields")
    if fields is None:
        return None
    try:
        _, reconstruction = independent.reconstruct_endpoint(fields)
        diagnostics = independent.recompute_diagnostics(fields)
    except Exception as error:
        mismatch(out, f"{path}.recomputation", "successful", repr(error), "exception")
        return None
    if reconstruction["maximum_relative_inf"] > 5.0e-12 or not reconstruction["raw_finite"]:
        mismatch(out, f"{path}.reconstruction", "round trip <= 5e-12", reconstruction, "roundtrip")
    independent.compare_tree(out, f"{path}.diagnostics", row.get("diagnostics"), diagnostics)
    gates = independent.quality_gates(True, diagnostics)
    if row.get("gates") != gates:
        mismatch(out, f"{path}.gates", gates, row.get("gates"), "exact")
    qualified = all(gates.values()) and diagnostics["physical_gradient_rms"] <= TARGET_GRADIENT_RMS
    if row.get("precision_target_pass") is not qualified:
        mismatch(
            out,
            f"{path}.precision_target_pass",
            qualified,
            row.get("precision_target_pass"),
            "exact",
        )
    wall_seconds = row.get("wall_seconds_total")
    if (
        not isinstance(wall_seconds, (int, float))
        or isinstance(wall_seconds, bool)
        or not math.isfinite(float(wall_seconds))
        or float(wall_seconds) < 0.0
    ):
        mismatch(
            out,
            f"{path}.wall_seconds_total",
            "finite nonnegative scalar",
            wall_seconds,
            "range",
        )
    return {
        "block": expected_block,
        "artifact": artifact,
        "artifact_sha256": actual_hash,
        "reconstruction": reconstruction,
        "diagnostics": diagnostics,
        "gates": gates,
        "precision_target_pass": qualified,
    }


def run_final_verification() -> int:
    if VERIFICATION_PATH.exists():
        raise VerificationFailure("precision verification already exists; receipts are immutable")
    mismatches: list[dict[str, Any]] = []
    manifest, manifest_sha256 = verify_manifest(mismatches)
    fresh_source = source_evidence(mismatches)
    try:
        preflight = read_json(PREFLIGHT_PATH)
        results = read_json(RESULTS_PATH)
    except Exception as error:
        mismatch(mismatches, "receipts", "readable preflight and results", repr(error), "read")
        preflight, results = {}, {}
    if preflight.get("pass") is not True or preflight.get("mismatches"):
        mismatch(mismatches, "preflight", "clean PASS", preflight, "evidence")
    if preflight.get("manifest_sha256") != manifest_sha256:
        mismatch(
            mismatches,
            "preflight.manifest_sha256",
            manifest_sha256,
            preflight.get("manifest_sha256"),
            "hash",
        )
    if results.get("schema") != "cassi.particle-stationary-precision.results.v1":
        mismatch(
            mismatches,
            "results.schema",
            "cassi.particle-stationary-precision.results.v1",
            results.get("schema"),
            "exact",
        )
    if results.get("status") != "complete":
        mismatch(mismatches, "results.status", "complete", results.get("status"), "exact")
    if results.get("manifest") != manifest or results.get("manifest_sha256") != manifest_sha256:
        mismatch(mismatches, "results.manifest", manifest_sha256, results.get("manifest_sha256"), "hash")
    if results.get("continuation") != CONTINUATION:
        mismatch(mismatches, "results.continuation", CONTINUATION, results.get("continuation"), "exact")
    if results.get("target_gradient_rms") != TARGET_GRADIENT_RMS:
        mismatch(
            mismatches,
            "results.target_gradient_rms",
            TARGET_GRADIENT_RMS,
            results.get("target_gradient_rms"),
            "exact",
        )
    if results.get("max_blocks") != MAX_BLOCKS:
        mismatch(mismatches, "results.max_blocks", MAX_BLOCKS, results.get("max_blocks"), "exact")
    verify_embedded_source(mismatches, results.get("source"), fresh_source)

    rows = results.get("blocks")
    verified: list[dict[str, Any]] = []
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_BLOCKS:
        mismatch(mismatches, "results.blocks", f"1..{MAX_BLOCKS} blocks", rows, "schema")
        rows = []
    for index, row in enumerate(rows, start=1):
        checked = verify_checkpoint(mismatches, row, index)
        if checked is not None:
            verified.append(checked)
    expected_files = {"preflight_verification.json", "results.json"}
    expected_files.update(
        row["artifact"] for row in verified if isinstance(row.get("artifact"), str)
    )
    actual_files = {path.name for path in RUN_DIR.iterdir()} if RUN_DIR.is_dir() else set()
    if actual_files != expected_files:
        mismatch(
            mismatches,
            "run_directory.files",
            sorted(expected_files),
            sorted(actual_files),
            "exact",
        )

    first_qualified = next(
        (row["block"] for row in verified if row["precision_target_pass"]), None
    )
    if first_qualified is None and len(rows) != MAX_BLOCKS:
        mismatch(mismatches, "selection.block_count", MAX_BLOCKS, len(rows), "stopping_rule")
    if first_qualified is not None and len(rows) != first_qualified:
        mismatch(mismatches, "selection.stop_block", first_qualified, len(rows), "stopping_rule")
    if results.get("selected_block") != first_qualified:
        mismatch(
            mismatches,
            "selection.selected_block",
            first_qualified,
            results.get("selected_block"),
            "exact",
        )
    expected_artifact = None
    expected_hash = None
    if first_qualified is not None:
        selected = next(row for row in verified if row["block"] == first_qualified)
        expected_artifact = selected["artifact"]
        expected_hash = selected["artifact_sha256"]
    if results.get("selected_artifact") != expected_artifact:
        mismatch(
            mismatches,
            "selection.selected_artifact",
            expected_artifact,
            results.get("selected_artifact"),
            "exact",
        )
    if results.get("selected_artifact_sha256") != expected_hash:
        mismatch(
            mismatches,
            "selection.selected_artifact_sha256",
            expected_hash,
            results.get("selected_artifact_sha256"),
            "hash",
        )

    expected_primary = (
        "PASS—HIGHER-PRECISION BACKGROUND"
        if first_qualified is not None
        else "INCONCLUSIVE—PRECISION CAP"
    )
    if results.get("primary_verdict") != expected_primary:
        mismatch(
            mismatches,
            "results.primary_verdict",
            expected_primary,
            results.get("primary_verdict"),
            "exact",
        )
    expected_gates = {
        "HP-A": True,
        "HP-B": bool(rows) and len(verified) == len(rows),
        "HP-C": first_qualified is not None,
        "HP-D": None,
    }
    if results.get("gates") != expected_gates:
        mismatch(
            mismatches,
            "results.gates",
            expected_gates,
            results.get("gates"),
            "exact",
        )
    hp_a = preflight.get("pass") is True
    hp_b = bool(rows) and len(verified) == len(rows)
    hp_c = first_qualified is not None
    hp_d = not mismatches
    scientific_verdict = (
        expected_primary if hp_d else "INCONCLUSIVE—EXECUTION OR VERIFICATION"
    )
    report = {
        "schema": "cassi.particle-stationary-precision.verification.v1",
        "pass": hp_d,
        "mismatches": mismatches,
        "manifest_sha256": manifest_sha256,
        "gates": {"HP-A": hp_a, "HP-B": hp_b, "HP-C": hp_c, "HP-D": hp_d},
        "verified_blocks": verified,
        "selected_block": first_qualified,
        "selected_artifact": expected_artifact,
        "selected_artifact_sha256": expected_hash,
        "scientific_verdict": scientific_verdict,
    }
    write_json(VERIFICATION_PATH, report)
    print(
        json.dumps(
            {
                "pass": report["pass"],
                "mismatches": len(mismatches),
                "verdict": scientific_verdict,
                "selected_block": first_qualified,
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
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"PRECISION VERIFICATION ERROR: {type(error).__name__}: {error}", flush=True)
        raise SystemExit(1)
