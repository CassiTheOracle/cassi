"""Verify the exact CassiFI implementation bundle and release receipt chain."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
_IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".pi"}
_IGNORED_SUFFIXES = {".pyc", ".pyo"}
_UNINVENTORIED = {
    "paper-version.json",
    "artifacts/portable-release/release-digest.json",
}
_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _actual_files(root: Path) -> set[str]:
    files: set[str] = set()
    for path in root.rglob("*"):
        if (
            not path.is_file()
            or path.is_symlink()
            or any(part in _IGNORED_PARTS for part in path.parts)
            or path.suffix in _IGNORED_SUFFIXES
        ):
            continue
        relative = path.relative_to(root).as_posix()
        if relative not in _UNINVENTORIED:
            files.add(relative)
    return files


def _portable_strings(value: Any, location: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, str):
        if _DRIVE_PATH.match(value) or value.startswith(("/home/", "/Users/")):
            violations.append(f"{location}: {value}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            violations.extend(_portable_strings(item, f"{location}[{index}]"))
    elif isinstance(value, dict):
        for key, item in value.items():
            violations.extend(_portable_strings(item, f"{location}.{key}"))
    return violations


def _verify_receipts(
    root: Path, manifest: Mapping[str, Any], entries: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    closure_path = root / "artifacts" / "portable-release" / "source-closure.json"
    licensing_path = root / "artifacts" / "portable-release" / "licensing-receipt.json"
    reproduction_path = root / "artifacts" / "portable-release" / "clean-process-reproduction.json"
    evaluation_path = root / "artifacts" / "portable-release" / "implementation-evaluation.json"
    digest_path = root / "artifacts" / "portable-release" / "release-digest.json"

    closure = _load(closure_path)
    if closure.get("schema") != "cassi.fi.source-closure.v1":
        raise ValueError("unsupported source closure")
    if closure.get("file_count") != len(closure.get("files", [])):
        raise ValueError("source closure count mismatch")
    if closure.get("total_bytes") != sum(
        entry["bytes"] for entry in closure["files"]
    ):
        raise ValueError("source closure byte count mismatch")
    for entry in closure["files"]:
        bound = entries.get(entry["path"])
        if bound is None or any(
            bound[key] != entry[key] for key in ("bytes", "sha256", "classification")
        ):
            raise ValueError(f"source closure is not manifest-bound: {entry['path']}")
    historical = closure["historical_parent"]
    parent_path = root / historical["path"]
    if historical.get("status") != "byte_identical" or historical.get("mismatches"):
        raise ValueError("historical byte comparison did not pass")
    if _sha256(parent_path) != historical["sha256"]:
        raise ValueError("historical parent manifest hash mismatch")
    if closure["archive_boundary"] != {
        "path": "../legacy/prototype",
        "canonical": False,
        "runtime_fallback": False,
    }:
        raise ValueError("legacy archive boundary is not explicit")

    licensing = _load(licensing_path)
    if (
        licensing.get("schema") != "cassi.fi.licensing-receipt.v1"
        or licensing.get("status") != "blocked"
        or licensing.get("publication_authorized") is not False
        or licensing.get("private_corpus_hashes_verified") is not True
        or licensing.get("publication_action") != "none"
    ):
        raise ValueError("licensing receipt does not fail closed")
    repository_license = licensing.get("repository_license", {})
    manuscript_license = licensing.get("manuscript_license", {})
    for declared, expected_path, expected_name, expected_distribution in (
        (repository_license, "LICENSE", "Apache-2.0", "Apache-2.0"),
        (manuscript_license, "LICENSE-PAPER", "CC BY 4.0", "CC-BY-4.0"),
    ):
        bound = entries.get(expected_path)
        declared_name = declared.get("spdx") or declared.get("name")
        if (
            declared.get("status") != "declared"
            or declared.get("license_file_present") is not True
            or declared.get("path") != expected_path
            or declared_name != expected_name
            or bound is None
            or bound["sha256"] != declared.get("sha256")
            or bound["publication_distribution"] != expected_distribution
        ):
            raise ValueError(f"declared license is inconsistent: {expected_path}")
    for relative in (
        "cassi-technical-paper.md",
        "cassi-technical-paper.pdf",
        "figures/field-intelligence-loop.svg",
    ):
        if entries.get(relative, {}).get("publication_distribution") != "CC-BY-4.0":
            raise ValueError(f"manuscript material license is inconsistent: {relative}")
    for source in licensing.get("sources", []):
        if (
            source.get("included_in_publication_bundle") is not False
            or source.get("publication_authorization") != "none"
            or source.get("local_hash_verified") is not True
        ):
            raise ValueError(f"unsafe corpus publication state: {source.get('id')}")
        bound = entries.get(source["local_path"])
        if (
            bound is None
            or bound["sha256"] != source["sha256"]
            or bound["bytes"] != source["bytes"]
            or bound["publication_distribution"] != "excluded_rights_unresolved"
        ):
            raise ValueError(f"corpus is not safely manifest-bound: {source['id']}")

    evaluation = _load(evaluation_path)
    if evaluation.get("schema") != "cassi.implementation-evaluation.v2":
        raise ValueError("unsupported implementation evaluation schema")
    gaps = evaluation.get("gaps", {})
    if len(gaps) != 8 or not all("status" in value for value in gaps.values()):
        raise ValueError("evaluation does not report all eight gaps")
    gap_receipts = evaluation.get("gap_receipts", {})
    if (
        set(gap_receipts) != set(gaps)
        or any(
            receipt.get("present") is not True
            or receipt.get("status") != gaps[key]["status"]
            or not receipt.get("evidence_fields")
            for key, receipt in gap_receipts.items()
        )
    ):
        raise ValueError("evaluation gap receipts are incomplete")
    blockers = sorted(key for key, value in gaps.items() if value["status"] != "supported")
    readiness = evaluation["readiness"]
    # This retained evaluation predates the manuscript rewrite; the manifest
    # below owns current paper status, while this receipt keeps capture-time status.
    if (
        sorted(readiness.get("blocking_gaps", [])) != blockers
        or readiness.get("implementation_complete") is not (not blockers)
        or readiness.get("paper_rewrite_started") is not False
        or readiness.get("publication_status") != "not_ready"
        or readiness.get("gap_receipts_complete") is not True
        or readiness.get("evaluation_receipts_complete") is not True
    ):
        raise ValueError("evaluation readiness contradicts gap statuses")
    risk = gaps["3_risk_coverage_calibration"]
    if risk.get("probabilities_emitted") is not False or risk.get("ece") != "not_measured":
        raise ValueError("probability calibration is overstated")
    resources = gaps["6_matched_resource_benchmarks"]
    if resources.get("energy_measurement") != "not available from the Python runtime":
        raise ValueError("energy status is overstated")
    bridge = gaps["8_cassifi_cassicosmos_bridge"]
    if bridge.get("status") != "not_ready" or bridge.get("live_windowed_run_performed"):
        raise ValueError("CassiCosmos bridge status is overstated")

    scenario = evaluation["deterministic"]["scenario"]
    execution = evaluation["execution"]
    required_sources = {
        "cassi_canonical_runtime.py",
        "cassi_persistent_provider.py",
        "cassi_qi_world.py",
        "run_text_abstraction_comparison.py",
        "run_general_task_gauntlet.py",
        "verification/run_implementation_evaluation.py",
    }
    if set(execution["source_files"]) != required_sources:
        raise ValueError("evaluation source closure is incomplete")
    for relative, digest in execution["source_files"].items():
        if relative not in entries or entries[relative]["sha256"] != digest:
            raise ValueError(f"evaluation source identity mismatch: {relative}")
    raw_root = execution["state_root"]
    raw_relative = PurePosixPath(raw_root) if isinstance(raw_root, str) else None
    portable_root = (root / "artifacts" / "portable-release").resolve()
    if (
        raw_relative is None
        or raw_relative.is_absolute()
        or raw_root != raw_relative.as_posix()
        or not raw_relative.parts
        or any(part in {"", ".", ".."} for part in raw_relative.parts)
        or "\\" in raw_root
        or any(":" in part for part in raw_relative.parts)
    ):
        raise ValueError("evaluation raw state path is not a safe canonical POSIX path")
    raw_path = (root / Path(*raw_relative.parts)).resolve()
    if (
        raw_path == portable_root
        or not raw_path.is_relative_to(portable_root)
        or not raw_path.is_dir()
    ):
        raise ValueError("evaluation raw state is not retained below portable-release")
    raw_prefix = raw_relative.as_posix() + "/"
    raw_entries = [
        path for path in entries
        if path == raw_relative.as_posix() or path.startswith(raw_prefix)
    ]
    if not raw_entries or any(
        not PurePosixPath(path).is_relative_to(raw_relative)
        for path in raw_entries
    ):
        raise ValueError("evaluation raw state entries are outside the retained state")
    for relative in raw_entries:
        candidate = root / Path(*PurePosixPath(relative).parts)
        if candidate.is_symlink() or not candidate.resolve().is_relative_to(raw_path):
            raise ValueError("evaluation raw state entry escapes the retained state")

    def retained_path(*parts: str) -> tuple[str, Path]:
        if any(
            not isinstance(part, str)
            or not part
            or part in {".", ".."}
            or "/" in part
            or "\\" in part
            or ":" in part
            for part in parts
        ):
            raise ValueError("derived receipt path is not a safe child path")
        relative_path = raw_relative.joinpath(*parts)
        relative = relative_path.as_posix()
        candidate = root / Path(*relative_path.parts)
        resolved = candidate.resolve()
        if (
            candidate.is_symlink()
            or resolved == raw_path
            or not resolved.is_relative_to(raw_path)
        ):
            raise ValueError("derived receipt path escapes the retained state")
        return relative, resolved

    retained_receipts = []
    for expected in (
        scenario["teach_receipt_sha256"],
        scenario["correction_receipt_sha256"],
        scenario["action"]["receipt_sha256"],
    ):
        relative, receipt_path = retained_path(
            "canonical-receipts",
            f"{expected}.json",
        )
        if relative not in entries:
            raise ValueError(f"scenario receipt bytes were not retained: {expected}")
        envelope = _load(receipt_path)
        digest = hashlib.sha256(
            json.dumps(
                envelope["receipt"],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        if envelope.get("receipt_sha256") != expected or digest != expected:
            raise ValueError(f"retained scenario receipt identity mismatch: {expected}")
        retained_receipts.append(envelope)
    observed_action_id = retained_receipts[-1]["receipt"]["result"]["action_instance_id"]
    action_path, action_file = retained_path(
        "action-journal",
        f"{observed_action_id}.json",
    )
    if action_path not in entries:
        raise ValueError("observed action journal was not retained")
    action_journal = _load(action_file)
    stages = [event["stage"] for event in action_journal["events"]]
    if stages != [
        "proposed", "authorized", "dispatch_intent", "outcome_pending",
        "consolidating", "observed",
    ]:
        raise ValueError("retained observed action has an inconsistent lifecycle")

    reproduction = _load(reproduction_path)
    runs = reproduction.get("runs", [])
    if (
        reproduction.get("status") != "verified"
        or reproduction.get("independent_processes") != 2
        or reproduction.get("corpus_bytes_copied") is not False
        or len(runs) != 2
        or any(run.get("exit_code") != 0 for run in runs)
        or any(run.get("original_checkout_reference_detected") for run in runs)
        or len({run.get("copied_closure_sha256") for run in runs}) != 1
        or len({run.get("deterministic_sha256") for run in runs}) != 1
        or reproduction.get("deterministic_sha256") != evaluation["deterministic_sha256"]
    ):
        raise ValueError("clean-process reproduction is inconsistent")

    portable_receipts = [
        manifest, closure, licensing, reproduction, evaluation, *retained_receipts,
    ]
    violations = [
        violation
        for receipt in portable_receipts
        for violation in _portable_strings(receipt)
    ]
    if violations:
        raise ValueError(f"absolute path leaked into portable receipt: {violations[:3]}")

    digest = _load(digest_path)
    expected_digests = {
        "paper_version_sha256": _sha256(root / "paper-version.json"),
        "source_closure_sha256": _sha256(closure_path),
        "licensing_receipt_sha256": _sha256(licensing_path),
        "reproduction_receipt_sha256": _sha256(reproduction_path),
        "evaluation_receipt_sha256": _sha256(evaluation_path),
    }
    if (
        digest.get("schema") != "cassi.fi.release-digest.v1"
        or digest.get("release_id") != manifest["release_id"]
        or digest.get("publication_action") != "none"
        or any(digest.get(key) != value for key, value in expected_digests.items())
    ):
        raise ValueError("release digest chain mismatch")
    return {
        "gap_statuses": {key: value["status"] for key, value in gaps.items()},
        "historical_files_verified": historical["files_compared"],
        "reproduction": reproduction["status"],
        "licensing": licensing["status"],
    }


def verify(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = _load(root / "paper-version.json")
    if manifest.get("schema") != "cassi.fi.paper-bundle.v2" or not manifest.get("files"):
        raise ValueError("unsupported or empty paper bundle manifest")
    if manifest.get("root") != ".":
        raise ValueError("bundle root must be manifest-relative")

    entries: dict[str, Mapping[str, Any]] = {}
    total_bytes = 0
    for entry in manifest["files"]:
        relative = entry["path"]
        pure = PurePosixPath(relative)
        path = root / relative
        if (
            relative in entries
            or pure.is_absolute()
            or ".." in pure.parts
            or path.is_symlink()
            or not path.resolve().is_relative_to(root)
        ):
            raise ValueError(f"duplicate or out-of-bundle path: {relative}")
        if not path.is_file() or path.stat().st_size != entry["bytes"]:
            raise ValueError(f"missing or resized bundle file: {relative}")
        if _sha256(path) != entry["sha256"]:
            raise ValueError(f"bundle SHA-256 mismatch: {relative}")
        entries[relative] = entry
        total_bytes += entry["bytes"]

    actual = _actual_files(root)
    if actual != entries.keys():
        raise ValueError(
            "manifest file set mismatch: "
            f"missing={sorted(actual - entries.keys())}, "
            f"absent={sorted(entries.keys() - actual)}"
        )
    for name in ("paper", "plan"):
        bound = manifest[name]
        entry = entries.get(bound["path"])
        if entry is None or entry["sha256"] != bound["sha256"]:
            raise ValueError(f"{name} identity is not manifest-bound")
    status = manifest["status"]
    if (
        status.get("paper_rewrite_started") is not True
        or status.get("publication_readiness") != "not_ready"
    ):
        raise ValueError("current manuscript or publication status is inconsistent")

    receipts = _verify_receipts(root, manifest, entries)
    return {
        "release_id": manifest["release_id"],
        "files_verified": len(entries),
        "bytes_verified": total_bytes,
        **receipts,
        "publication_readiness": status["publication_readiness"],
        "status": "verified",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    print(json.dumps(verify(args.root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
