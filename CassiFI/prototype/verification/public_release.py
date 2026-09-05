"""Build, smoke, and verify a public-safe CassiFI paper candidate."""
from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Mapping, Sequence
import zipfile

SOURCE_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = SOURCE_ROOT / "public-release-policy.json"
MANIFEST_NAME = "public-manifest.json"
DIGEST_NAME = "public-release-digest.json"
SCHEMA = "cassi.fi.public-paper-bundle.v1"

_ROOT_FILES = (
    "cassi-technical-paper.md",
    "IMPLEMENTATION-AND-PUBLICATION-PLAN.md",
    "public-release-policy.json",
)
_OPTIONAL_FILES = ("cassi-technical-paper.pdf", "LICENSE", "LICENSE-PAPER", "NOTICE", "CITATION.cff", ".zenodo.json")
_SOURCE_DIRS = ("runtime", "training", "verification", "configs", "schemas", "figures")
_PUBLIC_REFERENCE_EVALUATION = Path("evidence/public-reference-evaluation.json")
_LOCAL_REFERENCE_EVALUATION = Path("artifacts/portable-release/implementation-evaluation.json")
_PUBLIC_CORPUS_PROVENANCE = Path("data/corpus-provenance-public.json")
_LOCAL_CORPUS_PROVENANCE = Path("data/corpus-provenance.json")
_FORBIDDEN_PREFIXES = ("data/corpora/", "artifacts/", "_diag/", "legacy/", ".git/", ".pi/")
_FORBIDDEN_SUFFIXES = (
    ".pt",
    ".pth",
    ".ckpt",
    ".safetensors",
    ".gguf",
    ".npz",
    ".npy",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".avi",
    ".mp4",
    ".pyc",
    ".pyo",
)
_TEXT_SUFFIXES = {".py", ".md", ".json", ".cff", ".txt", ".svg", ".toml", ".yaml", ".yml"}
_CORPUS_HASHES = {
    "f78dcc1d940fb15001936b143fa05e748be6777480850509eec02f1dcce1283c",
    "c2c667bc6b608509c0f02f1d5da1414a4b8810b99487fc525086ca664b6e8aa4",
    "1063fd685dc32af56a0c61af24a7efec627ed96a5c85ad684b205fb5b5cac189",
    "914d3830a5dc70d9866ba4cba2f5b4170df4df5f259344208f01589cbdd2a645",
}


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
    path.write_bytes(_canonical(value) + b"\n")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected an object in {path}")
    return value


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _load_reference_summary(path: Path, *, check_local: bool = False) -> dict[str, Any]:
    reference = _load_json(path)
    source = reference.get("source_receipt")
    statuses = reference.get("gap_statuses")
    readiness = reference.get("readiness")
    digest = reference.get("deterministic_sha256")
    if reference.get("schema") != "cassi.fi.public-reference-evaluation.v1":
        raise ValueError("unsupported public reference evaluation")
    if (
        not isinstance(source, dict)
        or source.get("local_path") != _LOCAL_REFERENCE_EVALUATION.as_posix()
        or source.get("included") is not False
        or not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256", "")))
    ):
        raise ValueError("public reference source identity is invalid")
    if (
        not isinstance(statuses, dict)
        or len(statuses) != 8
        or any(status not in {"supported", "not_ready"} for status in statuses.values())
        or not isinstance(readiness, dict)
    ):
        raise ValueError("public reference gap summary is invalid")
    blockers = [gap for gap, status in statuses.items() if status == "not_ready"]
    if (
        readiness.get("system_readiness") != "not_ready"
        or readiness.get("blocking_gaps") != blockers
        or not re.fullmatch(r"[0-9a-f]{64}", str(digest or ""))
    ):
        raise ValueError("public reference readiness is inconsistent")

    local_path = SOURCE_ROOT / _LOCAL_REFERENCE_EVALUATION
    if check_local and local_path.is_file():
        local = _load_json(local_path)
        local_gaps = local.get("gaps")
        local_readiness = local.get("readiness")
        if (
            source["sha256"] != _sha256(local_path)
            or local.get("deterministic_sha256") != digest
            or not isinstance(local_gaps, dict)
            or {gap: value.get("status") for gap, value in local_gaps.items()} != statuses
            or not isinstance(local_readiness, dict)
            or local_readiness.get("blocking_gaps") != blockers
            or local_readiness.get("publication_status") != readiness["system_readiness"]
        ):
            raise ValueError("public reference summary does not match the local receipt")
    return reference


def _load_public_corpus_provenance(path: Path, *, check_local: bool = False) -> dict[str, Any]:
    provenance = _load_json(path)
    sources = provenance.get("sources")
    if (
        provenance.get("schema") != "cassi.fi.public-corpus-provenance.v1"
        or provenance.get("corpus_bytes_included") is not False
        or not isinstance(sources, list)
        or len(sources) != len(_CORPUS_HASHES)
    ):
        raise ValueError("public corpus provenance is invalid")
    for source in sources:
        if (
            not isinstance(source, dict)
            or not isinstance(source.get("id"), str)
            or not source["id"]
            or not isinstance(source.get("bytes"), int)
            or source["bytes"] <= 0
            or source.get("sha256") not in _CORPUS_HASHES
            or source.get("included") is not False
            or source.get("redistribution_status") != "unknown"
            or source.get("publication_authorization") != "none"
        ):
            raise ValueError("public corpus source summary is invalid")
    if len({source["sha256"] for source in sources}) != len(_CORPUS_HASHES):
        raise ValueError("public corpus source identities are incomplete")

    local_path = SOURCE_ROOT / _LOCAL_CORPUS_PROVENANCE
    if check_local and local_path.is_file():
        local = _load_json(local_path)
        local_sources = local.get("sources")
        if not isinstance(local_sources, list):
            raise ValueError("local corpus provenance is invalid")
        expected = [
            {
                "id": source["id"],
                "bytes": source["size_bytes"],
                "sha256": source["expected_sha256"],
                "included": False,
                "redistribution_status": source["redistribution_status"],
                "publication_authorization": source["publication_authorization"],
            }
            for source in local_sources
        ]
        if sources != expected:
            raise ValueError("public corpus summary does not match the local provenance")
    return provenance


def _safe_relative(path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix()
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise ValueError(f"unsafe public path: {relative}")
    return relative


def _source_files() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for relative in _ROOT_FILES:
        source = SOURCE_ROOT / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        pairs.append((source, Path(relative)))
    public_readme = SOURCE_ROOT / "PUBLIC-RELEASE.md"
    if not public_readme.is_file():
        raise FileNotFoundError(public_readme)
    pairs.append((public_readme, Path("README.md")))

    for path in sorted(SOURCE_ROOT.glob("*.py")):
        if path.is_file():
            pairs.append((path, Path(path.name)))
    for directory in _SOURCE_DIRS:
        root = SOURCE_ROOT / directory
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if (
                path.is_file()
                and not path.is_symlink()
                and "__pycache__" not in path.parts
                and path.suffix not in {".pyc", ".pyo"}
            ):
                pairs.append((path, path.relative_to(SOURCE_ROOT)))
    for relative in _OPTIONAL_FILES:
        source = SOURCE_ROOT / relative
        if source.is_file():
            pairs.append((source, Path(relative)))

    seen: set[str] = set()
    unique: list[tuple[Path, Path]] = []
    for source, destination in pairs:
        key = destination.as_posix()
        if key in seen:
            continue
        seen.add(key)
        unique.append((source, destination))
    return unique


def _copy_public_sources(destination: Path) -> None:
    for source, relative in _source_files():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    reference = SOURCE_ROOT / _PUBLIC_REFERENCE_EVALUATION
    if not reference.is_file():
        raise FileNotFoundError(reference)
    _load_reference_summary(reference, check_local=True)
    target = destination / _PUBLIC_REFERENCE_EVALUATION
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(reference, target)

    provenance = SOURCE_ROOT / _PUBLIC_CORPUS_PROVENANCE
    if not provenance.is_file():
        raise FileNotFoundError(provenance)
    _load_public_corpus_provenance(provenance, check_local=True)
    target = destination / _PUBLIC_CORPUS_PROVENANCE
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(provenance, target)


def _installed_dependency(name: str) -> dict[str, Any]:
    try:
        distribution = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        return {"name": name, "version": None, "license": None, "bundled": False}
    license_value = distribution.metadata.get("License-Expression") or distribution.metadata.get("License")
    return {
        "name": name,
        "version": distribution.version,
        "license": license_value or None,
        "bundled": False,
    }


def _dependency_report() -> dict[str, Any]:
    return {
        "schema": "cassi.fi.public-dependencies.v1",
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "packages": [_installed_dependency(name) for name in ("numpy", "torch", "markdown-it-py")],
        "third_party_packages_bundled": False,
    }


def _synthetic_checkpoint(root: Path) -> dict[str, Any]:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from cassi_persistent_provider import _load_phi_config
    from cassi_phi_harmonic_language import PhiHarmonicLanguageController

    config = _load_phi_config(root / "configs" / "cassi-phi-harmonic-language.json")
    controller = PhiHarmonicLanguageController(config)
    initial = controller.new_state(device="cpu")
    prompt = b"public synthetic prompt"
    continuation = b"public synthetic response"
    state = controller.learn_exchange(initial, prompt, continuation)
    learned_events = controller.learned_events(state)
    if len(learned_events) < 2:
        raise RuntimeError("synthetic public fixture contains no learned exchange")
    payload = controller.dump_state_bytes(state)
    checkpoint = root / "artifacts" / "cassi-phi-harmonic-language" / "field-state.pt"
    checkpoint.parent.mkdir(parents=True, exist_ok=False)
    checkpoint.write_bytes(payload)
    return {
        "schema": "cassi.fi.synthetic-public-fixture.v1",
        "derived_from_corpus": False,
        "synthetic_exchange_count": 1,
        "learned_event_count": len(learned_events),
        "prompt_sha256": hashlib.sha256(prompt).hexdigest(),
        "continuation_sha256": hashlib.sha256(continuation).hexdigest(),
        "field_shape": list(state.field.shape),
        "field_dtype": str(state.field.dtype),
        "state_sha256": controller.state_sha256(state),
        "checkpoint_sha256": hashlib.sha256(payload).hexdigest(),
        "checkpoint_retained_in_public_bundle": False,
        "config_fingerprint": controller.config_fingerprint,
    }


def _run_public_evaluation(root: Path, output: Path) -> dict[str, Any]:
    artifact_root = root / "artifacts"
    if artifact_root.exists():
        raise ValueError("public evaluation requires an artifact-free candidate root")
    previous_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    receipt: dict[str, Any] | None = None
    try:
        receipt = _synthetic_checkpoint(root)
        output.parent.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment["PYTHONPATH"] = ""
        environment["PYTHONNOUSERSITE"] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "verification" / "run_implementation_evaluation.py"),
                "--output",
                str(output),
            ],
            cwd=root,
            env=environment,
            capture_output=True,
            timeout=600,
            check=False,
        )
        if completed.returncode != 0 or not output.is_file():
            raise RuntimeError(
                "public synthetic evaluation failed: "
                + completed.stderr.decode("utf-8", errors="replace")[-3000:]
            )
        result = _load_json(output)
        receipt["evaluation_deterministic_sha256"] = result["deterministic_sha256"]
        receipt["evaluation_stdout_sha256"] = hashlib.sha256(completed.stdout).hexdigest()
        receipt["evaluation_stderr_sha256"] = hashlib.sha256(completed.stderr).hexdigest()
        return receipt
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode
        if artifact_root.exists():
            shutil.rmtree(artifact_root)


def _scan_text(path: Path, relative: str) -> list[str]:
    if path.suffix.casefold() not in _TEXT_SUFFIXES:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [f"{relative}: text-classified file is not UTF-8"]

    violations: list[str] = []
    key_marker = "-----BEGIN " + "PRIVATE KEY-----"
    if key_marker in text or "-----BEGIN OPENSSH " + "PRIVATE KEY-----" in text:
        violations.append(f"{relative}: private-key material")
    token_patterns = (
        r"\bghp_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"\bsk-[A-Za-z0-9_-]{20,}\b",
        r"\bAKIA[0-9A-Z]{16}\b",
    )
    if any(re.search(pattern, text) for pattern in token_patterns):
        violations.append(f"{relative}: credential-shaped token")
    if re.search(r"[A-Za-z]:[\\/](?:Users|workspaces|datasets)[\\/]", text, re.IGNORECASE):
        violations.append(f"{relative}: personal Windows path")
    if re.search(r"/(?:home|Users)/[A-Za-z0-9._-]+/", text):
        violations.append(f"{relative}: personal POSIX path")
    return violations


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            yield path


def _file_license(relative: str) -> str:
    if (
        relative in {"cassi-technical-paper.md", "cassi-technical-paper.pdf", "LICENSE-PAPER"}
        or relative.startswith("figures/")
    ):
        return "CC-BY-4.0"
    return "Apache-2.0"


def _assert_public_tree(root: Path, *, generated: bool) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    violations: list[str] = []
    for path in _iter_files(root):
        relative = _safe_relative(path, root)
        if relative in {MANIFEST_NAME, DIGEST_NAME}:
            continue
        if path.is_symlink():
            violations.append(f"{relative}: symlink")
            continue
        folded = relative.casefold()
        if any(folded.startswith(prefix.casefold()) for prefix in _FORBIDDEN_PREFIXES):
            violations.append(f"{relative}: forbidden public path class")
        if "__pycache__" in PurePosixPath(relative).parts:
            violations.append(f"{relative}: bytecode cache path")
        if path.suffix.casefold() in _FORBIDDEN_SUFFIXES:
            violations.append(f"{relative}: forbidden binary/checkpoint suffix")
        digest = _sha256(path)
        if digest in _CORPUS_HASHES:
            violations.append(f"{relative}: matches a private corpus digest")
        violations.extend(_scan_text(path, relative))
        entries.append({
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": digest,
            "license": _file_license(relative),
        })
    if violations:
        raise ValueError("public disclosure audit failed:\n" + "\n".join(sorted(violations)))
    if generated and not entries:
        raise ValueError("public bundle contains no inventoried files")
    return entries


def _publication_blockers(root: Path, policy: Mapping[str, Any]) -> list[str]:
    paper = (root / "cassi-technical-paper.md").read_text(encoding="utf-8")
    blockers: list[str] = []
    if "[REQUIRED BEFORE PUBLICATION:" in paper:
        blockers.append("author metadata incomplete")
    if policy.get("author_approved") is not True:
        blockers.append("final author approval absent")
    if not policy.get("code_license") or not (root / "LICENSE").is_file():
        blockers.append("code license not declared")
    manuscript_license = policy.get("manuscript_license")
    if not manuscript_license or f"**Manuscript license:** {manuscript_license}" not in paper:
        blockers.append("manuscript license not declared in paper")
    return blockers


def _validate_policy(policy: Mapping[str, Any]) -> None:
    if policy.get("schema") != "cassi.fi.public-release-policy.v1":
        raise ValueError("unsupported public release policy")
    if policy.get("publication_action") != "none":
        raise ValueError("candidate build cannot perform a publication action")
    if policy.get("corpus_distribution", {}).get("policy") != "exclude_all_bytes":
        raise ValueError("public candidate must exclude all corpus bytes")
    if policy.get("checkpoint_distribution", {}).get("policy") != "synthetic_fixture_only":
        raise ValueError("public candidate must exclude trained and historical checkpoints")
    if policy.get("historical_evidence_distribution", {}).get("policy") != "exclude_raw_history":
        raise ValueError("public candidate must exclude raw historical evidence")
    if policy.get("third_party_packages_bundled") is not False:
        raise ValueError("public candidate cannot bundle third-party packages")


def build(output: Path, *, archive: bool) -> dict[str, Any]:
    output = output.resolve()
    if output == SOURCE_ROOT or output.is_relative_to(SOURCE_ROOT):
        raise ValueError("public output must be outside the source prototype")
    if output.exists():
        raise FileExistsError(f"public output already exists: {output}")
    output.mkdir(parents=True)
    try:
        _copy_public_sources(output)
        _write_json(output / "DEPENDENCIES.json", _dependency_report())
        synthetic_receipt = _run_public_evaluation(
            output,
            output / "evidence" / "public-synthetic-evaluation.json",
        )
        _write_json(output / "evidence" / "synthetic-public-fixture.json", synthetic_receipt)

        policy = _load_json(output / "public-release-policy.json")
        _validate_policy(policy)
        entries = _assert_public_tree(output, generated=True)
        reference = _load_reference_summary(output / _PUBLIC_REFERENCE_EVALUATION)
        public_evaluation = _load_json(output / "evidence" / "public-synthetic-evaluation.json")
        blockers = _publication_blockers(output, policy)
        manifest = {
            "schema": SCHEMA,
            "release_id": policy["release_id"],
            "publication_action": "none",
            "publication_readiness": "ready" if not blockers else "blocked",
            "publication_blockers": blockers,
            "licenses": {
                "code_and_metadata": {
                    "spdx": policy["code_license"],
                    "path": "LICENSE",
                },
                "manuscript_and_original_figures": {
                    "name": policy["manuscript_license"],
                    "path": "LICENSE-PAPER",
                },
            },
            "system_readiness": "not_ready",
            "system_blockers": reference["readiness"]["blocking_gaps"],
            "corpus_bytes_included": False,
            "trained_or_historical_checkpoints_included": False,
            "synthetic_checkpoint_retained": False,
            "raw_historical_evidence_included": False,
            "third_party_packages_bundled": False,
            "paper": next(entry for entry in entries if entry["path"] == "cassi-technical-paper.md"),
            "reference_evaluation": {
                "path": _PUBLIC_REFERENCE_EVALUATION.as_posix(),
                "deterministic_sha256": reference["deterministic_sha256"],
                "raw_local_state_included": False,
            },
            "public_synthetic_evaluation": {
                "path": "evidence/public-synthetic-evaluation.json",
                "deterministic_sha256": public_evaluation["deterministic_sha256"],
                "derived_from_corpus": False,
            },
            "files": entries,
        }
        _write_json(output / MANIFEST_NAME, manifest)
        digest = {
            "schema": "cassi.fi.public-paper-digest.v1",
            "release_id": manifest["release_id"],
            "manifest_sha256": _sha256(output / MANIFEST_NAME),
            "publication_action": "none",
        }
        _write_json(output / DIGEST_NAME, digest)
        verified = verify(output)
        archive_path = None
        if archive:
            archive_target = output.with_suffix(".zip")
            if archive_target.exists():
                raise FileExistsError(f"public archive already exists: {archive_target}")
            with zipfile.ZipFile(archive_target, "w", compression=zipfile.ZIP_DEFLATED) as stream:
                for path in _iter_files(output):
                    stream.write(path, path.relative_to(output).as_posix())
            archive_path = str(archive_target)
        return {**verified, "output": str(output), "archive": archive_path}
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise


def verify(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = _load_json(root / MANIFEST_NAME)
    digest = _load_json(root / DIGEST_NAME)
    if manifest.get("schema") != SCHEMA:
        raise ValueError("unsupported public manifest")
    if manifest.get("publication_action") != "none" or digest.get("publication_action") != "none":
        raise ValueError("candidate unexpectedly records a publication action")
    if digest.get("release_id") != manifest.get("release_id"):
        raise ValueError("public digest release identity mismatch")
    if digest.get("manifest_sha256") != _sha256(root / MANIFEST_NAME):
        raise ValueError("public manifest digest mismatch")
    if manifest.get("licenses") != {
        "code_and_metadata": {"spdx": "Apache-2.0", "path": "LICENSE"},
        "manuscript_and_original_figures": {"name": "CC BY 4.0", "path": "LICENSE-PAPER"},
    }:
        raise ValueError("public manifest license declarations are inconsistent")

    expected = {entry["path"]: entry for entry in manifest.get("files", [])}
    if len(expected) != len(manifest.get("files", [])):
        raise ValueError("duplicate public manifest path")
    observed = _assert_public_tree(root, generated=True)
    actual = {entry["path"]: entry for entry in observed}
    if actual != expected:
        raise ValueError("public file inventory or byte identity mismatch")
    if set(path.name for path in _iter_files(root)) and not {MANIFEST_NAME, DIGEST_NAME}.issubset(
        {path.name for path in _iter_files(root)}
    ):
        raise ValueError("public manifest or digest is missing")

    policy = _load_json(root / "public-release-policy.json")
    _validate_policy(policy)
    blockers = _publication_blockers(root, policy)
    expected_readiness = "ready" if not blockers else "blocked"
    if (
        manifest.get("publication_blockers") != blockers
        or manifest.get("publication_readiness") != expected_readiness
        or manifest.get("system_readiness") != "not_ready"
        or manifest.get("corpus_bytes_included") is not False
        or manifest.get("trained_or_historical_checkpoints_included") is not False
        or manifest.get("synthetic_checkpoint_retained") is not False
        or manifest.get("raw_historical_evidence_included") is not False
        or manifest.get("third_party_packages_bundled") is not False
    ):
        raise ValueError("public readiness status contradicts the candidate contents")

    _load_public_corpus_provenance(root / _PUBLIC_CORPUS_PROVENANCE)
    reference = _load_reference_summary(root / manifest["reference_evaluation"]["path"])
    public_evaluation = _load_json(root / manifest["public_synthetic_evaluation"]["path"])
    if reference.get("deterministic_sha256") != manifest["reference_evaluation"]["deterministic_sha256"]:
        raise ValueError("public reference evaluation identity mismatch")
    if public_evaluation.get("deterministic_sha256") != manifest["public_synthetic_evaluation"]["deterministic_sha256"]:
        raise ValueError("public synthetic evaluation identity mismatch")
    synthetic = _load_json(root / "evidence" / "synthetic-public-fixture.json")
    if (
        synthetic.get("derived_from_corpus") is not False
        or synthetic.get("synthetic_exchange_count") != 1
        or not isinstance(synthetic.get("learned_event_count"), int)
        or synthetic["learned_event_count"] < 2
        or synthetic.get("checkpoint_retained_in_public_bundle") is not False
        or synthetic.get("evaluation_deterministic_sha256") != public_evaluation["deterministic_sha256"]
    ):
        raise ValueError("synthetic public evaluation provenance is invalid")

    return {
        "release_id": manifest["release_id"],
        "status": "release_verified" if manifest["publication_readiness"] == "ready" else "candidate_verified",
        "publication_readiness": manifest["publication_readiness"],
        "publication_blockers": blockers,
        "system_readiness": manifest["system_readiness"],
        "system_blockers": manifest["system_blockers"],
        "files_verified": len(expected),
        "bytes_verified": sum(entry["bytes"] for entry in expected.values()),
        "corpus_bytes_included": False,
        "trained_or_historical_checkpoints_included": False,
        "raw_historical_evidence_included": False,
        "public_evaluation_deterministic_sha256": public_evaluation["deterministic_sha256"],
    }


def smoke(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = _load_json(root / MANIFEST_NAME)
    with tempfile.TemporaryDirectory(prefix="cassifi-public-smoke-") as temporary:
        output = Path(temporary) / "evaluation.json"
        receipt = _run_public_evaluation(root, output)
        result = _load_json(output)
    expected = manifest["public_synthetic_evaluation"]["deterministic_sha256"]
    if result.get("deterministic_sha256") != expected:
        raise ValueError("public synthetic evaluation did not reproduce its deterministic identity")
    return {
        "status": "reproduced",
        "deterministic_sha256": expected,
        "synthetic_fixture_state_sha256": receipt["state_sha256"],
        "corpus_bytes_used": False,
        "checkpoint_retained": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument("--archive", action="store_true")
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--root", type=Path, required=True)
    smoke_parser = commands.add_parser("smoke")
    smoke_parser.add_argument("--root", type=Path, required=True)
    internal = commands.add_parser("_evaluate")
    internal.add_argument("--root", type=Path, required=True)
    internal.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build":
        result = build(args.output, archive=args.archive)
    elif args.command == "verify":
        result = verify(args.root)
    elif args.command == "smoke":
        result = smoke(args.root)
    else:
        result = _run_public_evaluation(args.root.resolve(), args.output.resolve())
        _write_json(args.output.resolve().with_suffix(".synthetic.json"), result)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
