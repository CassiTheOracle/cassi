"""Regenerate the CassiFI implementation release receipts and byte manifest."""
from __future__ import annotations

import argparse
import ast
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "artifacts" / "portable-release"
MANIFEST_PATH = ROOT / "paper-version.json"
PARENT_MANIFEST_PATH = RELEASE_DIR / "paper-version-portable-2.json"
SOURCE_CLOSURE_PATH = RELEASE_DIR / "source-closure.json"
LICENSING_PATH = RELEASE_DIR / "licensing-receipt.json"
REPRODUCTION_PATH = RELEASE_DIR / "clean-process-reproduction.json"
RELEASE_DIGEST_PATH = RELEASE_DIR / "release-digest.json"
EVALUATION_PATH = RELEASE_DIR / "implementation-evaluation.json"
PUBLIC_REFERENCE_PATH = ROOT / "evidence" / "public-reference-evaluation.json"
PROVENANCE_PATH = ROOT / "data" / "corpus-provenance.json"
PUBLIC_PROVENANCE_PATH = ROOT / "data" / "corpus-provenance-public.json"
CODE_LICENSE_PATH = ROOT / "LICENSE"
PAPER_LICENSE_PATH = ROOT / "LICENSE-PAPER"

_GENERATED_OUTSIDE_MANIFEST = {
    "paper-version.json",
    "artifacts/portable-release/release-digest.json",
}
_IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".pi"}
_IGNORED_SUFFIXES = {".pyc", ".pyo"}
_ENVIRONMENT_KEYS = (
    "CUDA_VISIBLE_DEVICES",
    "HSA_ENABLE_SDMA",
    "PYTORCH_HIP_ALLOC_CONF",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(_canonical(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _sha_file(path: Path, cache: dict[Path, str]) -> str:
    resolved = path.resolve()
    if resolved not in cache:
        with path.open("rb") as stream:
            cache[resolved] = hashlib.file_digest(stream, "sha256").hexdigest()
    return cache[resolved]


def _files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if (
            not path.is_file()
            or path.is_symlink()
            or any(part in _IGNORED_PARTS for part in path.parts)
            or path.suffix in _IGNORED_SUFFIXES
        ):
            continue
        relative = path.relative_to(root).as_posix()
        if relative in _GENERATED_OUTSIDE_MANIFEST:
            continue
        yield path


def _classification(relative: str) -> str:
    if relative in {
        PUBLIC_REFERENCE_PATH.relative_to(ROOT).as_posix(),
        PUBLIC_PROVENANCE_PATH.relative_to(ROOT).as_posix(),
    }:
        return "public_evidence"
    if relative == PROVENANCE_PATH.relative_to(ROOT).as_posix():
        return "private_metadata"
    if relative.startswith("data/corpora/"):
        return "private_corpus"
    if relative.startswith("artifacts/portable-release/"):
        return "portable_evidence"
    if relative.startswith(("artifacts/", "_diag/", "evidence/")):
        return "historical_evidence"
    if relative.endswith(".py"):
        return "python_source"
    if relative.startswith("configs/"):
        return "configuration"
    if relative.startswith("schemas/"):
        return "schema"
    if relative.startswith("designs/"):
        return "design_or_historical_preregistration"
    if relative == "cassi-technical-paper.md":
        return "paper"
    if relative.endswith(".md"):
        return "documentation"
    return "asset"

def _publication_distribution(relative: str, classification: str) -> str:
    if classification == "private_corpus":
        return "excluded_rights_unresolved"
    if classification == "private_metadata":
        return "excluded_private_metadata"
    if classification in {"historical_evidence", "portable_evidence"}:
        return "excluded_from_public_candidate"
    if (
        relative in {"cassi-technical-paper.md", "cassi-technical-paper.pdf", "LICENSE-PAPER"}
        or relative.startswith("figures/")
    ):
        return "CC-BY-4.0"
    return "Apache-2.0"



def _inventory(
    cache: dict[Path, str], *, include_portable_evidence: bool
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in _files(ROOT):
        relative = path.relative_to(ROOT).as_posix()
        if (
            not include_portable_evidence
            and relative.startswith("artifacts/portable-release/")
        ):
            continue
        classification = _classification(relative)
        entries.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _sha_file(path, cache),
                "classification": classification,
                "publication_distribution": _publication_distribution(
                    relative, classification
                ),
            }
        )
    return entries


def _installed_version(module: str) -> dict[str, Any]:
    distributions = metadata.packages_distributions().get(module, ())
    if not distributions:
        return {"module": module, "distribution": None, "version": None}
    distribution = distributions[0]
    try:
        version = metadata.version(distribution)
    except metadata.PackageNotFoundError:
        version = None
    return {"module": module, "distribution": distribution, "version": version}


def _dependency_inventory(source_paths: Sequence[Path]) -> dict[str, Any]:
    local_modules = {path.stem for path in source_paths}
    local_modules.update(
        path.parent.name
        for path in source_paths
        if path.name == "__init__.py" and path.parent != ROOT
    )
    imported: set[str] = set()
    for path in source_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".", 1)[0])
    third_party = sorted(imported - local_modules - sys.stdlib_module_names)
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "execution_device": "cpu",
        "third_party_imports": [_installed_version(name) for name in third_party],
        "environment": {name: os.environ.get(name) for name in _ENVIRONMENT_KEYS},
    }


def _licensing_receipt(
    cache: dict[Path, str], *, verify_private_corpora: bool
) -> dict[str, Any]:
    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    sources: list[dict[str, Any]] = []
    for source in provenance["sources"]:
        relative = source["bundled_path"]
        path = ROOT / relative
        local_size_matches = path.is_file() and path.stat().st_size == source["size_bytes"]
        actual_sha256 = _sha_file(path, cache) if verify_private_corpora and path.is_file() else None
        hash_matches = (
            actual_sha256 == source["expected_sha256"]
            if actual_sha256 is not None
            else None
        )
        if verify_private_corpora and (not local_size_matches or hash_matches is not True):
            raise ValueError(f"private corpus bytes do not match provenance: {relative}")
        sources.append(
            {
                "id": source["id"],
                "local_path": relative,
                "bytes": source["size_bytes"],
                "sha256": source["expected_sha256"],
                "local_size_matches": local_size_matches,
                "local_hash_verified": hash_matches,
                "redistribution_status": source["redistribution_status"],
                "publication_authorization": source["publication_authorization"],
                "included_in_publication_bundle": False,
                "acquisition_instruction": (
                    "Obtain the exact bytes from a lawfully authorized source, place "
                    f"them at {relative}, and verify this SHA-256 before use."
                ),
            }
        )
    if not CODE_LICENSE_PATH.is_file() or "Apache License" not in CODE_LICENSE_PATH.read_text(encoding="utf-8"):
        raise ValueError("Apache-2.0 code license is missing or invalid")
    if not PAPER_LICENSE_PATH.is_file() or "CC BY 4.0" not in PAPER_LICENSE_PATH.read_text(encoding="utf-8"):
        raise ValueError("CC BY 4.0 manuscript license is missing or invalid")
    return {
        "schema": "cassi.fi.licensing-receipt.v1",
        "status": "blocked",
        "publication_authorized": False,
        "repository_license": {
            "status": "declared",
            "license_file_present": True,
            "spdx": "Apache-2.0",
            "path": CODE_LICENSE_PATH.relative_to(ROOT).as_posix(),
            "sha256": _sha_file(CODE_LICENSE_PATH, cache),
        },
        "manuscript_license": {
            "status": "declared",
            "license_file_present": True,
            "name": "CC BY 4.0",
            "path": PAPER_LICENSE_PATH.relative_to(ROOT).as_posix(),
            "sha256": _sha_file(PAPER_LICENSE_PATH, cache),
        },
        "corpus_redistribution": provenance["redistribution"],
        "private_corpus_hashes_verified": verify_private_corpora,
        "sources": sources,
        "publication_action": "none",
    }


def _copy_replay_tree(destination: Path) -> list[dict[str, Any]]:
    paths = [
        *_files_with_suffix(ROOT, ".py"),
        *(ROOT / "configs").rglob("*.json"),
        *(ROOT / "schemas").rglob("*.json"),
        *(ROOT / "artifacts" / "cassi-phi-harmonic-language").rglob("*"),
    ]
    copied: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for source in sorted(paths, key=lambda item: item.as_posix()):
        if not source.is_file() or source in seen:
            continue
        seen.add(source)
        relative = source.relative_to(ROOT)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied.append(
            {
                "path": relative.as_posix(),
                "bytes": target.stat().st_size,
                "sha256": _sha_file(target, {}),
            }
        )
    return copied


def _files_with_suffix(root: Path, suffix: str) -> list[Path]:
    return [
        path
        for path in root.rglob(f"*{suffix}")
        if path.is_file() and not any(part in _IGNORED_PARTS for part in path.parts)
    ]


def _run_relocated_copy(destination: Path, label: str) -> dict[str, Any]:
    copied = _copy_replay_tree(destination)
    output = destination / "artifacts" / "portable-release" / "evaluation.json"
    state = destination / "artifacts" / "portable-release" / "state"
    command = [
        sys.executable,
        str(destination / "verification" / "run_implementation_evaluation.py"),
        "--state-dir",
        str(state),
        "--output",
        str(output),
    ]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = ""
    environment["PYTHONNOUSERSITE"] = "1"
    completed = subprocess.run(
        command,
        cwd=destination.parent,
        env=environment,
        capture_output=True,
        timeout=600,
        check=False,
    )
    if completed.returncode != 0 or not output.is_file():
        raise RuntimeError(
            f"relocated evaluation {label} failed ({completed.returncode}): "
            + completed.stderr.decode("utf-8", errors="replace")[-2000:]
        )
    result = json.loads(output.read_text(encoding="utf-8"))
    original_forms = {
        str(ROOT).casefold(),
        ROOT.as_posix().casefold(),
    }
    emitted = (completed.stdout + completed.stderr + output.read_bytes()).decode(
        "utf-8", errors="replace"
    ).casefold()
    return {
        "label": label,
        "command": [
            "python",
            "verification/run_implementation_evaluation.py",
            "--state-dir",
            "artifacts/portable-release/state",
            "--output",
            "artifacts/portable-release/evaluation.json",
        ],
        "working_directory": "outside_original_checkout",
        "exit_code": completed.returncode,
        "copied_file_count": len(copied),
        "copied_closure_sha256": hashlib.sha256(_canonical(copied)).hexdigest(),
        "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
        "result_sha256": _sha_file(output, {}),
        "deterministic_sha256": result["deterministic_sha256"],
        "original_checkout_reference_detected": any(
            form in emitted for form in original_forms
        ),
    }


def _clean_process_reproduction() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cassifi-release-") as temporary:
        parent = Path(temporary)
        runs = [
            _run_relocated_copy(parent / "copy-a" / "prototype", "copy-a"),
            _run_relocated_copy(parent / "copy-b" / "prototype", "copy-b"),
        ]
    deterministic = {run["deterministic_sha256"] for run in runs}
    copied = {run["copied_closure_sha256"] for run in runs}
    original_access = any(run["original_checkout_reference_detected"] for run in runs)
    if len(deterministic) != 1 or len(copied) != 1 or original_access:
        raise RuntimeError("clean relocated process reproduction did not match")
    return {
        "schema": "cassi.fi.clean-process-reproduction.v1",
        "status": "verified",
        "same_machine": True,
        "independent_processes": 2,
        "corpus_bytes_copied": False,
        "deterministic_sha256": runs[0]["deterministic_sha256"],
        "copied_closure_sha256": runs[0]["copied_closure_sha256"],
        "runs": runs,
    }


def _historical_comparison(
    parent_manifest: Mapping[str, Any], inventory: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    parent = {entry["path"]: entry for entry in parent_manifest["files"]}
    compared = 0
    mismatches: list[str] = []
    for entry in inventory:
        if entry["classification"] not in {"historical_evidence", "private_corpus"}:
            continue
        previous = parent.get(entry["path"])
        if previous is None:
            continue
        compared += 1
        if (
            previous["bytes"] != entry["bytes"]
            or previous["sha256"] != entry["sha256"]
        ):
            mismatches.append(str(entry["path"]))
    if mismatches:
        raise ValueError(f"historical bytes changed: {mismatches}")
    return {"status": "byte_identical", "files_compared": compared, "mismatches": []}


def build(*, verify_private_corpora: bool) -> dict[str, Any]:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    if not PARENT_MANIFEST_PATH.exists():
        shutil.copyfile(MANIFEST_PATH, PARENT_MANIFEST_PATH)
    parent_bytes = PARENT_MANIFEST_PATH.read_bytes()
    parent_manifest = json.loads(parent_bytes)
    cache: dict[Path, str] = {}

    licensing = _licensing_receipt(
        cache, verify_private_corpora=verify_private_corpora
    )
    _write_json(LICENSING_PATH, licensing)
    reproduction = _clean_process_reproduction()
    _write_json(REPRODUCTION_PATH, reproduction)

    source_paths = _files_with_suffix(ROOT, ".py")
    dependencies = _dependency_inventory(source_paths)
    inventory = _inventory(cache, include_portable_evidence=False)
    historical = _historical_comparison(parent_manifest, inventory)
    evaluation = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
    source_closure = {
        "schema": "cassi.fi.source-closure.v1",
        "root": ".",
        "files": inventory,
        "file_count": len(inventory),
        "total_bytes": sum(entry["bytes"] for entry in inventory),
        "python_dependencies": dependencies,
        "historical_parent": {
            "path": PARENT_MANIFEST_PATH.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(parent_bytes).hexdigest(),
            **historical,
        },
        "archive_boundary": {
            "path": "../legacy/prototype",
            "canonical": False,
            "runtime_fallback": False,
        },
    }
    _write_json(SOURCE_CLOSURE_PATH, source_closure)

    inventory = _inventory(cache, include_portable_evidence=True)
    file_map = {entry["path"]: entry for entry in inventory}
    required = {
        "cassi-technical-paper.md",
        "IMPLEMENTATION-AND-PUBLICATION-PLAN.md",
        "cassi_canonical_runtime.py",
        "cassi_persistent_provider.py",
        "verification/run_implementation_evaluation.py",
        "cassi-technical-paper.pdf",
        "figures/field-intelligence-loop.svg",
        "LICENSE",
        "LICENSE-PAPER",
        "NOTICE",
        "CITATION.cff",
        ".zenodo.json",
        "public-release-policy.json",
        "verification/public_release.py",
        PUBLIC_REFERENCE_PATH.relative_to(ROOT).as_posix(),
        PUBLIC_PROVENANCE_PATH.relative_to(ROOT).as_posix(),
        "verification/render_paper.py",
        SOURCE_CLOSURE_PATH.relative_to(ROOT).as_posix(),
        LICENSING_PATH.relative_to(ROOT).as_posix(),
        REPRODUCTION_PATH.relative_to(ROOT).as_posix(),
        EVALUATION_PATH.relative_to(ROOT).as_posix(),
    }
    missing = sorted(required - file_map.keys())
    if missing:
        raise ValueError(f"release closure is missing required files: {missing}")

    manifest = {
        "schema": "cassi.fi.paper-bundle.v2",
        "release_id": "cassifi-implementation-portable-3",
        "root": ".",
        "paper": file_map["cassi-technical-paper.md"],
        "plan": file_map["IMPLEMENTATION-AND-PUBLICATION-PLAN.md"],
        "status": {
            "implementation": "not_ready",
            "implementation_blockers": evaluation["readiness"]["blocking_gaps"],
            "evaluation_reports": "all_eight_reported_with_explicit_blockers",
            "paper_rewrite_started": True,
            "publication_readiness": "not_ready",
            "publication_blockers": [
                "corpus redistribution rights unresolved for the complete local bundle",
                "real authenticated CassiFI-CassiCosmos adapter and windowed receipt absent",
                "energy and FLOP measurements unavailable",
            ],
        },
        "runtime_dependencies": dependencies,
        "entrypoints": [
            ["python", "verification/run_implementation_evaluation.py"],
            ["python", "verification/build_portable_release.py", "--verify-private-corpora"],
            ["python", "verification/verify_paper_bundle.py"],
        ],
        "lineage": {
            "parent_manifest": PARENT_MANIFEST_PATH.relative_to(ROOT).as_posix(),
            "parent_manifest_sha256": hashlib.sha256(parent_bytes).hexdigest(),
            "historical_bytes": historical,
            "historical_absolute_path_receipts": "preserved_byte_identically",
            "portable_receipts": "manifest_relative",
        },
        "evaluation": {
            "path": EVALUATION_PATH.relative_to(ROOT).as_posix(),
            "sha256": file_map[EVALUATION_PATH.relative_to(ROOT).as_posix()]["sha256"],
            "deterministic_sha256": evaluation["deterministic_sha256"],
            "gap_statuses": {
                key: value["status"] for key, value in evaluation["gaps"].items()
            },
        },
        "reproduction": {
            "path": REPRODUCTION_PATH.relative_to(ROOT).as_posix(),
            "status": reproduction["status"],
            "deterministic_sha256": reproduction["deterministic_sha256"],
        },
        "licensing": {
            "path": LICENSING_PATH.relative_to(ROOT).as_posix(),
            "status": licensing["status"],
            "publication_authorized": licensing["publication_authorized"],
        },
        "inventory_policy": {
            "sha256": "raw file bytes",
            "paths": "relative to prototype root",
            "manifest_excluded_from_own_inventory": True,
            "release_digest_excluded_from_manifest": True,
            "private_corpus_bytes_bound_but_excluded_from_publication": True,
            "ignored": ["**/__pycache__/**", "**/.pytest_cache/**", "*.pyc", ".pi/**"],
        },
        "files": inventory,
    }
    _write_json(MANIFEST_PATH, manifest)

    digest = {
        "schema": "cassi.fi.release-digest.v1",
        "release_id": manifest["release_id"],
        "paper_version_sha256": _sha_file(MANIFEST_PATH, {}),
        "source_closure_sha256": _sha_file(SOURCE_CLOSURE_PATH, {}),
        "licensing_receipt_sha256": _sha_file(LICENSING_PATH, {}),
        "reproduction_receipt_sha256": _sha_file(REPRODUCTION_PATH, {}),
        "evaluation_receipt_sha256": _sha_file(EVALUATION_PATH, {}),
        "publication_action": "none",
    }
    _write_json(RELEASE_DIGEST_PATH, digest)
    return {
        "release_id": manifest["release_id"],
        "files": len(inventory),
        "bytes": sum(entry["bytes"] for entry in inventory),
        "historical_files_verified": historical["files_compared"],
        "clean_process_reproduction": reproduction["status"],
        "deterministic_sha256": reproduction["deterministic_sha256"],
        "licensing": licensing["status"],
        "publication_readiness": manifest["status"]["publication_readiness"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-private-corpora",
        action="store_true",
        help="Hash all local private corpus bytes against their provenance entries.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(build(verify_private_corpora=args.verify_private_corpora), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
