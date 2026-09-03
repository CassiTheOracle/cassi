#!/usr/bin/env python3
"""Verify the fail-closed result shape of the first PA32 Q2 recovery protocol."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "runs" / "20260901_particle_stationary_bvp"
RUN_DIR = ROOT / "runs" / "20260902_particle_stationary_q2_recovery"
SOURCE_RESULTS_PATH = SOURCE_DIR / "results.json"
RESULTS_PATH = RUN_DIR / "results.json"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
V1_VERIFICATION_PATH = RUN_DIR / "verification.json"
OUTPUT_PATH = RUN_DIR / "v1_result_verification.json"
V1_PREREG_PATH = ROOT / "computations" / "particle_stationary_q2_recovery_prereg.md"
V1_PROGRAM_PATH = ROOT / "computations" / "particle_stationary_q2_recovery.py"
V1_VERIFIER_PATH = ROOT / "computations" / "verify_particle_stationary_q2_recovery.py"
SOURCE_PREREG_PATH = ROOT / "computations" / "particle-stationary-bvp-pre-registration.md"
SOURCE_PROGRAM_PATH = ROOT / "computations" / "particle_stationary_bvp.py"
SOURCE_VERIFIER_PATH = ROOT / "computations" / "verify_particle_stationary_bvp.py"
SOURCE_VERIFICATION_PATH = SOURCE_DIR / "verification.json"
SOURCE_REPORT_PATH = ROOT / "computations" / "particle-stationary-bvp-report.md"
AUTHORITY_PATHS = {
    "authority_action": ROOT / "foundations" / "particle-stationary-action-closure.md",
    "authority_core_support": ROOT / "foundations" / "core-trapped-charge-support.md",
    "authority_magnetic_boundary": ROOT / "foundations" / "nonabelian-magnetic-core-boundary.md",
    "authority_matter_boundary": ROOT / "foundations" / "matter-completion-boundary.md",
}
BASINS = (
    "separated_core",
    "merged_core",
    "closed_loop",
    "carrier_lump",
    "delocalized",
    "split_multicore",
)
EXPECTED_KEYS = {f"{family}:{basin}" for family in ("P", "D") for basin in BASINS}
RAW_FAILURE = re.compile(
    r"^(?P<key>[PD]:[a-z_]+)\.diagnostics\."
    r"objective_raw_gradient_(?:rms|max): expected "
    r"(?P<expected>[-+0-9.eE]+), got (?P<actual>[-+0-9.eE]+)$"
)
ORDERED_KEYS = tuple(
    f"{family}:{basin}" for family in ("P", "D") for basin in BASINS
)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"Expected a JSON object: {path}")
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_artifact_path(arm: Mapping[str, Any]) -> Path:
    artifact = arm.get("artifact")
    if not isinstance(artifact, str):
        raise ValueError("source arm has no artifact")
    candidate = Path(artifact)
    if candidate.is_absolute():
        return candidate
    by_name = SOURCE_DIR / candidate.name
    return by_name if by_name.exists() else ROOT / candidate


def manifest(source: Mapping[str, Any]) -> dict[str, Any]:
    immutable = {
        "source_results": sha256(SOURCE_RESULTS_PATH),
        "source_verification": sha256(SOURCE_VERIFICATION_PATH),
        "source_report": sha256(SOURCE_REPORT_PATH),
        "source_preregistration": sha256(SOURCE_PREREG_PATH),
        "source_program": sha256(SOURCE_PROGRAM_PATH),
        "source_verifier": sha256(SOURCE_VERIFIER_PATH),
    }
    required_mismatches: list[str] = []
    carried = {
        "source_preregistration": source["hashes"]["preregistration"],
        "source_program": source["hashes"]["primary_program"],
        "source_verifier": source["hashes"]["independent_verifier"],
    }
    for name, expected in carried.items():
        actual = immutable[name]
        if actual != expected:
            required_mismatches.append(
                f"{name}: source receipt {expected}, current bytes {actual}"
            )
    if set(source.get("arms", {})) != EXPECTED_KEYS:
        required_mismatches.append("source arm inventory differs from the frozen P/D set")
    artifacts: dict[str, str] = {}
    for key in sorted(EXPECTED_KEYS):
        arm = source.get("arms", {}).get(key)
        if not isinstance(arm, dict) or not arm.get("completed"):
            required_mismatches.append(f"{key}: source arm is missing or incomplete")
            continue
        path = source_artifact_path(arm)
        actual = sha256(path)
        artifacts[path.name] = actual
        expected = source["hashes"]["artifacts"].get(path.name)
        if actual != expected or actual != arm.get("artifact_sha256"):
            required_mismatches.append(f"{key}: source artifact hash mismatch")
    return {
        "immutable_source_snapshot": immutable,
        "source_artifacts": artifacts,
        "current_authority": {name: sha256(path) for name, path in AUTHORITY_PATHS.items()},
        "recovery_sources": {
            "preregistration": sha256(V1_PREREG_PATH),
            "primary_program": sha256(V1_PROGRAM_PATH),
            "independent_verifier": sha256(V1_VERIFIER_PATH),
        },
        "required_mismatches": required_mismatches,
    }


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def finite_nonnegative(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) >= 0.0
    )


def finite_within(value: Any, upper: float) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    numeric = float(value)
    return math.isfinite(numeric) and 0.0 <= numeric <= upper

def main() -> int:
    if OUTPUT_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite frozen receipt: {OUTPUT_PATH}")

    source = read_json(SOURCE_RESULTS_PATH)
    result = read_json(RESULTS_PATH)
    independent_preflight = read_json(PREFLIGHT_PATH)
    first_verification = read_json(V1_VERIFICATION_PATH)
    expected_manifest = manifest(source)
    failures: list[str] = []

    check(result.get("manifest") == expected_manifest, "result manifest mismatch", failures)
    check(not expected_manifest["required_mismatches"], "source manifest mismatch", failures)
    check(result.get("schema_version") == 1, "schema version mismatch", failures)
    check(result.get("status") == "complete", "result is not complete", failures)
    check(result.get("arms") == {}, "an optimization arm was recorded", failures)
    check(result.get("run_order") == [], "run order is not empty", failures)
    check(result.get("source_quality_gates") == {}, "quality gates were populated", failures)
    check(
        result.get("h_selection") == {"basin": None, "eligible": []},
        "H selection is not empty",
        failures,
    )
    expected_gates = {
        "R1": True,
        "R2": False,
        "R3": False,
        "R4": None,
        "R5": False,
        "R6": False,
    }
    check(result.get("recovery_gates") == expected_gates, "recovery gates mismatch", failures)
    check(
        result.get("primary_verdict") == "INCONCLUSIVE—IMPLEMENTATION PREFLIGHT",
        "primary verdict mismatch",
        failures,
    )

    preflight = result.get("preflight")
    if not isinstance(preflight, dict):
        failures.append("primary preflight is not an object")
    else:
        check(preflight.get("pass") is False, "primary preflight did not fail", failures)
        arms = preflight.get("arms")
        check(isinstance(arms, dict) and set(arms) == EXPECTED_KEYS, "primary preflight arm inventory mismatch", failures)
        flattened: list[str] = []
        if isinstance(arms, dict):
            for key in ORDERED_KEYS:
                row = arms.get(key)
                if not isinstance(row, dict):
                    failures.append(f"{key}: missing primary preflight row")
                    continue
                check(row.get("artifact") == f"fields_{key.replace(':', '_')}.npz", f"{key}: artifact name mismatch", failures)
                source_hash = source["arms"][key]["artifact_sha256"]
                check(row.get("artifact_sha256") == source_hash, f"{key}: artifact hash mismatch", failures)
                reconstruction = row.get("reconstruction")
                if not isinstance(reconstruction, dict):
                    failures.append(f"{key}: missing reconstruction receipt")
                else:
                    check(reconstruction.get("raw_finite") is True, f"{key}: raw reconstruction nonfinite", failures)
                    maximum = reconstruction.get("maximum_relative_inf")
                    check(finite_within(maximum, 5.0e-12), f"{key}: round-trip bound failed", failures)
                    errors = reconstruction.get("relative_inf")
                    if not isinstance(errors, dict) or set(errors) != {"psi_real", "psi_imag", "h", "a", "c"}:
                        failures.append(f"{key}: round-trip field inventory mismatch")
                    else:
                        for name, value in errors.items():
                            check(finite_within(value, 5.0e-12), f"{key}.{name}: round-trip bound failed", failures)
                row_failures = row.get("failures")
                if not isinstance(row_failures, list):
                    failures.append(f"{key}: failures are not a list")
                    continue
                check(row.get("pass") is (not row_failures), f"{key}: pass flag mismatch", failures)
                for text in row_failures:
                    if not isinstance(text, str):
                        failures.append(f"{key}: non-string failure")
                        continue
                    match = RAW_FAILURE.fullmatch(text)
                    if match is None or match.group("key") != key:
                        failures.append(f"{key}: non-raw-coordinate failure: {text!r}")
                        continue
                    check(finite_nonnegative(float(match.group("expected"))), f"{key}: invalid expected gradient", failures)
                    check(finite_nonnegative(float(match.group("actual"))), f"{key}: invalid reconstructed gradient", failures)
                    flattened.append(f"{key}: {text}")
        check(bool(flattened), "no raw-coordinate mismatch was recorded", failures)
        check(preflight.get("failures") == flattened, "flattened preflight failure list mismatch", failures)

    check(independent_preflight.get("pass") is True, "independent preflight receipt was not passing", failures)
    check(independent_preflight.get("manifest") == expected_manifest, "independent preflight manifest mismatch", failures)
    check(first_verification.get("pass") is False, "first final verifier unexpectedly passed", failures)
    check(
        first_verification.get("primary_verdict") == "INCONCLUSIVE—IMPLEMENTATION PREFLIGHT",
        "first verifier lost the primary verdict",
        failures,
    )

    report = {
        "schema_version": 1,
        "pass": not failures,
        "verdict": "INCONCLUSIVE—IMPLEMENTATION PREFLIGHT" if not failures else "INCONCLUSIVE—EXECUTION OR VERIFICATION",
        "manifest": expected_manifest,
        "v1_receipts": {
            "primary": sha256(RESULTS_PATH),
            "independent_preflight": sha256(PREFLIGHT_PATH),
            "first_final_verification": sha256(V1_VERIFICATION_PATH),
            "receipt_verifier": sha256(Path(__file__).resolve()),
        },
        "accepted_fail_closed_shape": {
            "R1": True,
            "R2": False,
            "run_order": [],
            "optimized_arms": [],
            "h_selected": False,
        },
        "failures": failures,
    }
    write_json(OUTPUT_PATH, report)
    print(json.dumps({"pass": report["pass"], "verdict": report["verdict"], "receipt": str(OUTPUT_PATH)}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
