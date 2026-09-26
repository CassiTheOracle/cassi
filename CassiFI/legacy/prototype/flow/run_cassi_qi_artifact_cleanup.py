"""Fail-closed inventory and quarantine planning for a CassiFI run tree.

The inventory and quarantine operator is deliberately boring: it never deletes
source bytes, never follows a reparse point, and never treats a filename or an
age as provenance. Names may nominate an object for review; a quarantine move
additionally needs explicit provenance saying that the object was generated,
unsealed, noncanonical, and outside the validated dependency/retention
closure. Quarantine is the only mutating mode and preserves every byte.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

from cassi_qi_bootstrap import canonical_hash as _canonical_hash
from cassi_qi_bootstrap import canonical_json_bytes as _canonical_json_bytes
from cassi_qi_bootstrap import canonical_json_loads as _canonical_json_loads


CLEANUP_SCHEMA = "cassi.qi-flow-artifact-cleanup.v1"
RUN_INDEX_SCHEMA = "cassi.qi-flow-run-index.v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

# Immutable control objects named by the artifact-tree contract.
REQUIRED_RUN_SPEC = (
    "manifest.json",
    "profile.json",
    "semantic-subhashes.json",
    "profile-projections.json",
    "schema-registry.json",
    "dependency-manifest.json",
    "contract-root.json",
    "source-identity.json",
    "raw-retention-policy.json",
    "capability-matrix.json",
    "toolchain.json",
    "command-inputs.json",
    "static-fixture-index.json",
)

# The fixture index names the source-pinned bootstrap corpus.  Keep the
# directory boundary exact: arbitrary run-spec descendants are not registered
# artifact roots.
ORACLE_FIXTURE_DIR = "oracle-fixtures"
# W16B/G15B release objects live at the run root rather than under a
# registered directory.  They remain index-bound and immutable.
ALLOWED_RUN_FILES = {
    "provisional-release-board.json",
    "provisional-release-result.json",
    "release-board.json",
    "release-result.json",
}


# These directories are registered roots, not an alternative object index. The
# index still governs every non-control byte below a sealed run root.
ALLOWED_RUN_DIRS = {
    "objects", "inputs", "states", "packets", "field-experience", "capacity",
    "sensory-openness", "action-discriminability", "delayed-influence", "forgetting",
    "text-ownership", "text-codebook-packing", "dynamic-port-frames", "scattering",
    "numerical-certificates", "lineage", "transaction-models", "adapter-off", "remaps",
    "ledgers", "steps", "stage-receipts", "space-scale", "hodge", "retention", "topology",
    "decisions", "actions", "acknowledgements", "checkpoints", "text-events", "text-results",
    "world-wire", "world", "provider", "process-evidence", "backend", "security", "gates",
    "candidate", "quarantine",
}
def _allowed_index_path(relative: str) -> bool:
    """Return whether an index path belongs to a registered run-root family."""
    if not isinstance(relative, str) or relative == "index.json" or not relative:
        return relative == "index.json"
    parts = relative.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        return False
    if len(parts) == 1 and parts[0] in ALLOWED_RUN_FILES:
        return True
    if parts[0] == "run-spec":
        return (
            len(parts) == 2 and parts[1] in REQUIRED_RUN_SPEC
        ) or (
            len(parts) == 3 and parts[1] == ORACLE_FIXTURE_DIR
        )
    return len(parts) > 1 and parts[0] in (ALLOWED_RUN_DIRS - {"quarantine"})



 

# Names only nominate an object. They never establish provenance or eligibility.
NOMINATION_RE = re.compile(
    r"(?:^|[._-])(stage|staging|tmp|temp|raw|partial|part|orphan)(?:$|[._-])",
    re.IGNORECASE,
)
HEX_TREE_RE = re.compile(r"^[0-9a-f]{64}$")

QUARANTINE_KEYS = {
    "approved_digests", "approved_for_quarantine", "quarantine_digests",
    "cleanup_digests", "disposable_digests", "generated_digests",
}
RETAIN_KEYS = {
    "retained_digests", "retain_digests", "required_digests", "keep_digests",
    "sealed_digests", "dependency_closure_digests",
}
PATH_KEYS = {"path", "relative_path", "object_path", "source_path", "frozen_path", "indexed_path", "target"}
HASH_KEYS = {"sha256", "digest", "artifact_sha256", "object_sha256", "file_sha256", "raw_sha256"}
SELF_KEYS = (
    "self_sha256", "profile_sha256", "contract_root_sha256", "source_identity_sha256",
    "raw_retention_policy_sha256", "dependency_manifest_sha256", "artifact_sha256",
)
PROVENANCE_NAMES = (".provenance.json", "provenance.json", ".artifact-provenance.json", "artifact-provenance.json")


class CleanupError(RuntimeError):
    """A malformed or unsafe artifact tree."""


class ConcurrentChangeError(CleanupError):
    """The tree changed after it was snapshotted."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return _canonical_json_bytes(value)


def _load_json(path: Path) -> tuple[Any, bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CleanupError(f"read failed: {path}: {exc}") from exc
    try:
        value = _canonical_json_loads(raw)
    except Exception as exc:
        raise CleanupError(f"invalid canonical JSON: {path}: {exc}") from exc
    if _json_bytes(value) != raw:
        raise CleanupError(f"noncanonical JSON bytes: {path}")
    return value, raw


def _safe_path(path: Path, root: Path) -> bool:
    try:
        path.absolute().relative_to(root.absolute())
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except (ValueError, OSError):
        return False
    return True


def _is_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        flags = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return bool(path.stat(follow_symlinks=False).st_file_attributes & flags)
    except (AttributeError, OSError):
        return path.is_symlink()


def _regular(path: Path) -> bool:
    try:
        return path.is_file() and not _is_reparse(path)
    except OSError:
        return False


def _directory(path: Path) -> bool:
    try:
        return path.is_dir() and not _is_reparse(path)
    except OSError:
        return False


def _relative(path: Path, root: Path) -> str:
    try:
        return path.absolute().relative_to(root.absolute()).as_posix()
    except ValueError as exc:
        raise CleanupError(f"path escapes root: {path}") from exc


def _path_from_relative(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise CleanupError(f"invalid relative path: {relative!r}")
    candidate = root.joinpath(*relative.split("/"))
    if not _safe_path(candidate, root):
        raise CleanupError(f"path escapes root: {relative!r}")
    return candidate


def _strip_self(value: Mapping[str, Any], field: str | None = None) -> dict[str, Any]:
    body = dict(value)
    body.pop("self_sha256", None)
    if field:
        body.pop(field, None)
    return body


def _declared_self_field(value: Mapping[str, Any], *, expected_name: str | None = None) -> str | None:
    if expected_name is not None:
        candidate = value.get(expected_name)
        return expected_name if isinstance(candidate, str) and SHA256_RE.fullmatch(candidate) else None
    for name in SELF_KEYS:
        candidate = value.get(name)
        if isinstance(candidate, str) and SHA256_RE.fullmatch(candidate):
            return name
    return None


def _verify_self_hash(value: Any, *, expected_schema: str | None = None, field: str | None = None) -> tuple[bool, str]:
    if not isinstance(value, Mapping):
        return False, "JSON object required"
    declared_name = _declared_self_field(value, expected_name=field)
    if declared_name is None:
        return False, "self-hash field is absent or malformed"
    declared = value[declared_name]
    body = _strip_self(value, declared_name)
    candidates = {sha256(_json_bytes(body))}
    schema = value.get("schema")
    if isinstance(schema, str):
        candidates.add(_canonical_hash(body, schema))
    if isinstance(expected_schema, str):
        candidates.add(_canonical_hash(body, expected_schema))
    if schema == "cassi.qi-flow-contract-root.v1" or expected_schema == "cassi.qi-flow-contract-root.v1":
        candidates.add(_canonical_hash(body, "cassi.qi-flow-contract-root-bootstrap.v1"))
    if declared not in candidates:
        return False, f"{declared_name} does not match canonical payload"
    return True, declared


def _schema_ok(value: Any, expected: str | Iterable[str]) -> bool:
    if not isinstance(value, Mapping) or not isinstance(value.get("schema"), str):
        return False
    expected_values = {expected} if isinstance(expected, str) else set(expected)
    return value["schema"] in expected_values


def _hashes(value: Any, *, key_names: Iterable[str] = HASH_KEYS) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in key_names and isinstance(item, str) and SHA256_RE.fullmatch(item):
                found.add(item)
            found.update(_hashes(item, key_names=key_names))
    elif isinstance(value, list):
        for item in value:
            found.update(_hashes(item, key_names=key_names))
    return found


def _paths(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in PATH_KEYS and isinstance(item, str) and item and not item.startswith(("/", "\\")):
                found.add(item.replace("\\", "/"))
            found.update(_paths(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_paths(item))
    return found


def _extract_digest_sets(value: Any) -> tuple[set[str], set[str]]:
    """Return (approved-for-quarantine, explicitly-retained) digests."""
    approved: set[str] = set()
    retained: set[str] = set()

    def walk(node: Any, key: str | None = None) -> None:
        if isinstance(node, Mapping):
            for child_key, child in node.items():
                walk(child, child_key)
            return
        if isinstance(node, list):
            for child in node:
                walk(child, key)
            return
        if isinstance(node, str) and SHA256_RE.fullmatch(node):
            if key in QUARANTINE_KEYS:
                approved.add(node)
            elif key in RETAIN_KEYS or key in HASH_KEYS:
                retained.add(node)

    walk(value)
    return approved, retained


def _tree_entries(root: Path, *, exclude: set[str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Snapshot regular files and reparse points without following links."""
    files: list[dict[str, Any]] = []
    reparses: list[dict[str, Any]] = []
    excluded = exclude or set()

    def visit(directory: Path) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise CleanupError(f"scan failed: {directory}: {exc}") from exc
        for entry in entries:
            path = Path(entry.path)
            rel = _relative(path, root)
            if rel in excluded or any(rel == item or rel.startswith(item + "/") for item in excluded):
                continue
            if entry.is_symlink() or _is_reparse(path):
                reparses.append({"path": rel, "kind": "reparse-point"})
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    visit(path)
                elif entry.is_file(follow_symlinks=False):
                    raw = path.read_bytes()
                    files.append({"path": rel, "sha256": sha256(raw), "byte_count": len(raw)})
                else:
                    reparses.append({"path": rel, "kind": "non-regular-entry"})
            except OSError as exc:
                raise CleanupError(f"snapshot failed: {path}: {exc}") from exc

    visit(root)
    files.sort(key=lambda item: item["path"])
    reparses.sort(key=lambda item: item["path"])
    return files, reparses

 


def _tree_directories(root: Path, *, exclude: set[str] | None = None) -> list[str]:
    """List safe directories, including empty ones, without following links."""
    excluded = exclude or set()
    result: list[str] = []

    def visit(directory: Path) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise CleanupError(f"scan failed: {directory}: {exc}") from exc
        for entry in entries:
            path = Path(entry.path)
            rel = _relative(path, root)
            if rel in excluded or any(rel == item or rel.startswith(item + "/") for item in excluded):
                continue
            if entry.is_symlink() or _is_reparse(path):
                continue
            if entry.is_dir(follow_symlinks=False):
                result.append(rel)
                visit(path)

    visit(root)
    return sorted(result)


def _snapshot_hash(files: list[dict[str, Any]], reparses: list[dict[str, Any]]) -> str:
    return sha256(_json_bytes({"files": files, "reparses": reparses}))


def _tree_digest(path: Path) -> tuple[str, int]:
    """Digest one regular file or a directory as sorted path/bytes records."""
    if _regular(path):
        raw = path.read_bytes()
        return sha256(raw), len(raw)
    files, reparses = _tree_entries(path, exclude=set(PROVENANCE_NAMES))
    if reparses:
        raise CleanupError(f"candidate contains reparse point: {path}")
    records = [{"path": item["path"], "sha256": item["sha256"], "byte_count": item["byte_count"]} for item in files]
    return sha256(_json_bytes({"files": records})), sum(int(item["byte_count"]) for item in files)


def _candidate_kind(relative: str, is_directory: bool) -> str | None:
    name = relative.rsplit("/", 1)[-1]
    if is_directory and (NOMINATION_RE.search(name) or name.lower().startswith("orphan")):
        return "abandoned-staging-dir"
    if HEX_TREE_RE.fullmatch(name) and is_directory:
        return "orphaned-content-addressed-tree"
    if not is_directory and (NOMINATION_RE.search(name) or name.lower().endswith((".raw", ".tmp", ".partial", ".part"))):
        return "stale-temp-raw-evidence"
    return None


def _provenance_candidates(path: Path, root: Path) -> list[Path]:
    result: list[Path] = []
    if _regular(path):
        result.extend(path.with_name(path.name + suffix) for suffix in PROVENANCE_NAMES)
    if _directory(path):
        result.extend(path / name for name in PROVENANCE_NAMES)
    parent = path.parent
    result.extend(parent / name for name in PROVENANCE_NAMES)
    if parent != root:
        result.extend(root / name for name in PROVENANCE_NAMES)
    unique: list[Path] = []
    seen: set[str] = set()
    for item in result:
        key = str(item.absolute()).casefold()
        if key not in seen and _safe_path(item, root):
            seen.add(key)
            unique.append(item)
    return unique


def _read_provenance(path: Path, root: Path, *, digest: str, relative: str) -> tuple[bool, dict[str, Any], str]:
    """Require explicit generated/unsealed/noncanonical/out-of-closure proof."""
    for candidate in _provenance_candidates(path, root):
        if not _regular(candidate):
            continue
        try:
            value, _ = _load_json(candidate)
        except CleanupError:
            continue
        if not isinstance(value, Mapping):
            continue
        provenance_ok, _ = _verify_self_hash(value, field="self_sha256")
        if not provenance_ok:
            continue
        records = value["artifacts"] if isinstance(value.get("artifacts"), list) else [value]
        for record in records:
            if not isinstance(record, Mapping):
                continue
            record_path = record.get("path", record.get("relative_path"))
            record_digest = record.get("sha256", record.get("artifact_sha256"))
            if record_path is None or record_digest is None:
                continue
            if str(record_path).replace("\\", "/") != relative or record_digest != digest:
                continue
            generated = record.get("generated") is True or record.get("generated_status") == "generated"
            unsealed = record.get("sealed") is False or record.get("lifecycle") in {"unsealed", "staging", "temporary"}
            noncanonical = record.get("canonical") is False or record.get("canonical_status") in {"noncanonical", "temporary", "orphan"}
            outside = record.get("dependency_closure") is False or record.get("in_dependency_closure") is False or record.get("retained") is False or record.get("retention") in {"not-retained", "disposable", "quarantine"}
            if generated and unsealed and noncanonical and outside:
                proof = {"path": _relative(candidate, root), "generated": True, "sealed": False, "canonical": False, "dependency_closure": False}
                return True, proof, "explicit-provenance"
    return False, {}, "explicit generated/unsealed/noncanonical/out-of-closure provenance is absent"


def _entry_map(index: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    objects = index.get("objects")
    if not isinstance(objects, list):
        return {}, ["index.objects must be an array"]
    result: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for item in objects:
        if not isinstance(item, Mapping):
            errors.append("index object entry is not an object")
            continue
        rel, digest, count = item.get("path"), item.get("sha256"), item.get("byte_count")
        if (
            not isinstance(rel, str)
            or not rel
            or rel.startswith(("/", "\\"))
            or "\\" in rel
            or any(part in {"", ".", ".."} for part in rel.split("/"))
        ):
            errors.append(f"invalid indexed path: {rel!r}")
            continue
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            errors.append(f"invalid indexed digest: {rel!r}")
            continue
        if not isinstance(count, int) or count < 0:
            errors.append(f"invalid indexed byte count: {rel!r}")
            continue
        if rel in result:
            errors.append(f"duplicate indexed path: {rel!r}")
            continue
        result[rel] = {"path": rel, "sha256": digest, "byte_count": count}
    if index.get("object_count") != len(objects):
        errors.append("index.object_count mismatch")
    return result, errors

def _validate_run(run_root: Path, *, outer_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": _relative(run_root, outer_root), "run_id": None, "sealed": False,
        "canonical": False, "errors": [], "indexed_paths": {}, "disallowed_indexed_paths": [],
        "closure_paths": set(),
        "closure_digests": set(), "retained_digests": set(), "approved_digests": set(),
        "index_sha256": None, "snapshot": [],
    }
    if not _directory(run_root):
        result["errors"].append("run root is not a safe directory")
        return result
    index_path = run_root / "index.json"
    if not _regular(index_path):
        result["errors"].append("index.json missing or unsafe")
        return result
    try:
        index, index_raw = _load_json(index_path)
    except CleanupError as exc:
        result["errors"].append(str(exc))
        return result
    result["index_sha256"] = sha256(index_raw)
    if not _schema_ok(index, RUN_INDEX_SCHEMA):
        result["errors"].append("index schema mismatch")
    if isinstance(index, Mapping):
        run_id = index.get("run_id")
        if isinstance(run_id, str) and RUN_ID_RE.fullmatch(run_id):
            result["run_id"] = run_id
        else:
            result["errors"].append("index.run_id missing or malformed")
    ok, error = _verify_self_hash(index, expected_schema=RUN_INDEX_SCHEMA, field="self_sha256")
    if not ok:
        result["errors"].append(error)
    entry_map, entry_errors = _entry_map(index if isinstance(index, Mapping) else {})
    result["indexed_paths"], result["errors"] = entry_map, result["errors"] + entry_errors
    disallowed = sorted(rel for rel in entry_map if not _allowed_index_path(rel))
    result["disallowed_indexed_paths"] = disallowed
    result["errors"].extend(f"indexed path outside allowed roots: {rel}" for rel in disallowed)
    for rel, indexed in sorted(entry_map.items()):
        if rel == "index.json":
            continue
        candidate = run_root.joinpath(*rel.split("/"))
        if not _safe_path(candidate, run_root) or not _regular(candidate):
            result["errors"].append(f"indexed object missing or unsafe: {rel}")

    loaded: dict[str, Any] = {}
    expected_schemas: dict[str, set[str]] = {
        "manifest.json": {"cassi.qi-flow-manifest.v1", "cassi.qi-flow-run-spec-manifest.v1"},
        "profile.json": {"cassi.qi-flow-profile.v1", "cassi.qi-flow-profile-handoff.v1"},
        "semantic-subhashes.json": {"cassi.qi-flow-semantic-subhashes.v1"},
        "profile-projections.json": {"cassi.qi-flow-profile-projections.v1"},
        "schema-registry.json": {"cassi.qi-flow-schema-registry.v1"},
        "dependency-manifest.json": {"cassi.qi-flow-dependency-manifest.v1"},
        "contract-root.json": {"cassi.qi-flow-contract-root.v1", "cassi.qi-flow-contract-root-bootstrap.v1"},
        "source-identity.json": {"cassi.qi-flow-source-identity.v1"},
        "raw-retention-policy.json": {"cassi.qi-flow-raw-retention-policy.v1"},
        "capability-matrix.json": {"cassi.qi-flow-capability-matrix.v1"},
        "toolchain.json": {"cassi.qi-flow-toolchain.v1"},
        "command-inputs.json": {"cassi.qi-flow-command-inputs.v1"},
        "static-fixture-index.json": {"cassi.qi-flow-static-fixture-index.v1"},
    }
    for name in REQUIRED_RUN_SPEC:
        path = run_root / "run-spec" / name
        if not _regular(path):
            result["errors"].append(f"missing required run-spec/{name}")
            continue
        try:
            value, raw = _load_json(path)
        except CleanupError as exc:
            result["errors"].append(str(exc))
            continue
        loaded[name] = value
        expected = expected_schemas[name]
        if not _schema_ok(value, expected):
            result["errors"].append(f"{name} schema mismatch")
        field = "profile_sha256" if name == "profile.json" else "self_sha256"
        self_ok, self_error = _verify_self_hash(value, expected_schema=next(iter(expected)), field=field)
        if not self_ok:
            result["errors"].append(f"{name}: {self_error}")
        rel = f"run-spec/{name}"
        indexed = entry_map.get(rel)
        actual_digest, actual_count = sha256(raw), len(raw)
        if indexed is None:
            result["errors"].append(f"{rel} is not indexed")
        elif indexed["sha256"] != actual_digest or indexed["byte_count"] != actual_count:
            result["errors"].append(f"{rel} index digest/byte count mismatch")

    status = index.get("status") if isinstance(index, Mapping) else None
    result["sealed"] = isinstance(status, str) and (status == "PASS" or status.startswith("PASS_") or status.startswith("SEALED"))
    if not result["sealed"]:
        result["errors"].append("index status is not sealed PASS")
    manifest, profile = loaded.get("manifest.json"), loaded.get("profile.json")
    if isinstance(manifest, Mapping) and manifest.get("run_id") != result["run_id"]:
        result["errors"].append("manifest.run_id does not match index.run_id")
    contract_root, source_identity = loaded.get("contract-root.json"), loaded.get("source-identity.json")
    retention, dependency = loaded.get("raw-retention-policy.json"), loaded.get("dependency-manifest.json")
    relation_fields = {
        "profile.json": (manifest, "profile_sha256", profile),
        "contract-root.json": (profile, "contract_root_sha256", contract_root),
        "source-identity.json": (profile, "source_identity_sha256", source_identity),
        "dependency-manifest.json": (manifest, "dependency_manifest_sha256", dependency),
    }
    def identity_values(value: Mapping[str, Any]) -> set[str]:
        return {
            item
            for key in SELF_KEYS
            if isinstance((item := value.get(key)), str) and SHA256_RE.fullmatch(item)
        }

    for name, (parent, key, child) in relation_fields.items():
        if isinstance(parent, Mapping) and key in parent and isinstance(child, Mapping):
            declared = parent.get(key)
            if not isinstance(declared, str) or not SHA256_RE.fullmatch(declared):
                result["errors"].append(f"{name} identity relation is malformed")
                continue
            # Semantic/self identities are distinct from the raw file digest
            # held by object-index entries.  A producer may additionally
            # publish the raw digest, so accept either verified identity.
            allowed = identity_values(child)
            indexed = entry_map.get(f"run-spec/{name}")
            if indexed:
                allowed.add(indexed["sha256"])
            if declared not in allowed:
                result["errors"].append(f"{name} identity relation mismatch")
    if isinstance(profile, Mapping) and isinstance(profile.get("execution"), Mapping) and isinstance(source_identity, Mapping):
        source_indexed = entry_map.get("run-spec/source-identity.json")
        allowed = identity_values(source_identity)
        if source_indexed:
            allowed.add(source_indexed["sha256"])
        if profile["execution"].get("source_identity_sha256") not in allowed:
            result["errors"].append("profile execution/source identity relation mismatch")
    if isinstance(index, Mapping):
        for key, rel in (("profile_sha256", "run-spec/profile.json"), ("dependency_manifest_sha256", "run-spec/dependency-manifest.json")):
            if key not in index or rel not in entry_map:
                continue
            child = loaded.get(Path(rel).name)
            allowed = {entry_map[rel]["sha256"]}
            if isinstance(child, Mapping):
                allowed.update(identity_values(child))
            if index[key] not in allowed:
                result["errors"].append(f"index.{key} mismatch")
    if isinstance(dependency, Mapping):
        result["closure_paths"].update(_paths(dependency))
        result["closure_digests"].update(_hashes(dependency))
    if isinstance(retention, Mapping):
        approved, retained = _extract_digest_sets(retention)
        result["approved_digests"].update(approved)
        result["retained_digests"].update(retained)
    result["closure_paths"].update(entry_map)
    result["closure_digests"].update(item["sha256"] for item in entry_map.values())
    result["retained_digests"].update(result["closure_digests"])

    files, reparses = _tree_entries(run_root, exclude={"quarantine"})
    result["snapshot"] = files
    for item in files:
        indexed = entry_map.get(item["path"])
        if indexed is not None:
            if indexed["sha256"] != item["sha256"] or indexed["byte_count"] != item["byte_count"]:
                result["errors"].append(f"indexed object drift: {item['path']}")
        elif item["path"] != "index.json":
            result["errors"].append(f"unindexed object: {item['path']}")
    if reparses:
        result["errors"].extend(f"undeclared reparse point: {item['path']}" for item in reparses)
    result["canonical"] = not result["errors"] and result["sealed"] and bool(result["run_id"])
    return result


def _read_run_id_quiet(run_root: Path) -> str | None:
    try:
        value, _ = _load_json(run_root / "index.json")
    except CleanupError:
        return None
    return value.get("run_id") if isinstance(value, Mapping) and isinstance(value.get("run_id"), str) else None


def _normalise_run_root(root: Path, *, run_id: str | None = None) -> tuple[Path, Path]:
    root = root.absolute()
    if not _directory(root):
        raise CleanupError(f"root is not a safe directory: {root}")
    if _regular(root / "index.json"):
        if run_id is None or _read_run_id_quiet(root) == run_id:
            return root, root
        raise CleanupError(f"run-id does not select exactly one run root: {run_id}")
    candidates: list[Path] = []
    try:
        for entry in sorted(os.scandir(root), key=lambda item: item.name):
            candidate = Path(entry.path)
            if entry.is_dir(follow_symlinks=False) and not _is_reparse(candidate) and _regular(candidate / "index.json"):
                candidates.append(candidate)
    except OSError as exc:
        raise CleanupError(f"scan failed: {root}: {exc}") from exc
    if run_id is not None:
        selected = [item for item in candidates if item.name == run_id or _read_run_id_quiet(item) == run_id]
        if len(selected) != 1:
            raise CleanupError(f"run-id does not select exactly one run root: {run_id}")
        return selected[0], root
    if len(candidates) == 1:
        return candidates[0], root
    return root, root


def inventory_artifacts(root: str | os.PathLike[str], *, run_id: str | None = None, exclude: Iterable[str] = ()) -> dict[str, Any]:
    """Return a deterministic, raw-byte-grounded artifact inventory."""
    requested = Path(root)
    run_root, outer_root = _normalise_run_root(requested, run_id=run_id)
    excluded = {str(item).replace("\\", "/").strip("/") for item in exclude if str(item)}
    files, reparses = _tree_entries(outer_root, exclude={"quarantine", *excluded})
    quarantine_path = outer_root / "quarantine"
    if _is_reparse(quarantine_path):
        reparses.append({"path": "quarantine", "kind": "reparse-point"})
    if _regular(outer_root / "index.json"):
        run_roots = [outer_root]
    else:
        try:
            run_roots = [Path(entry.path) for entry in sorted(os.scandir(outer_root), key=lambda item: item.name) if entry.is_dir(follow_symlinks=False) and not _is_reparse(Path(entry.path)) and _regular(Path(entry.path) / "index.json")]
        except OSError as exc:
            raise CleanupError(f"scan failed: {outer_root}: {exc}") from exc
    if run_root not in run_roots and _regular(run_root / "index.json"):
        run_roots.append(run_root)
    validations = [_validate_run(item, outer_root=outer_root) for item in sorted(set(run_roots), key=lambda item: item.as_posix())]
    by_id: dict[str, list[dict[str, Any]]] = {}
    for item in validations:
        if item.get("run_id"):
            by_id.setdefault(item["run_id"], []).append(item)
    duplicates = [{"run_id": rid, "roots": sorted(item["path"] for item in rows)} for rid, rows in sorted(by_id.items()) if len(rows) > 1]
    duplicate_paths = {path for row in duplicates for path in row["roots"]}
    indexed_paths: set[str] = set()
    indexed_directory_paths: set[str] = set()
    closure_digests: set[str] = set()
    retained_digests: set[str] = set()
    approved_digests: set[str] = set()
    disallowed_indexed_paths: list[dict[str, Any]] = []
    canonical_rows: list[dict[str, Any]] = []
    for item in validations:
        prefix = item["path"]
        for rel, indexed in item["indexed_paths"].items():
            full = f"{prefix}/{rel}" if prefix else rel
            indexed_paths.add(full)
            parts = full.split("/")
            for end in range(1, len(parts)):
                indexed_directory_paths.add("/".join(parts[:end]))
        for rel in item["disallowed_indexed_paths"]:
            full = f"{prefix}/{rel}" if prefix else rel
            indexed = item["indexed_paths"].get(rel, {})
            disallowed_indexed_paths.append({
                "path": full, "sha256": indexed.get("sha256"), "byte_count": indexed.get("byte_count"),
                "classification": "outside-allowed-root", "eligible_for_quarantine": False,
                "reason": "index path is outside registered artifact roots",
            })
        if item["canonical"]:
            closure_digests.update(item["closure_digests"])
            retained_digests.update(item["retained_digests"])
            approved_digests.update(item["approved_digests"])
            canonical_rows.append({
                "path": prefix, "run_id": item["run_id"], "index_sha256": item["index_sha256"],
                "status": "canonical-sealed-retained" if prefix not in duplicate_paths else "blocked-duplicate-run-id",
                "retained": prefix not in duplicate_paths, "release_ready": False,
            })
    uncertain_runs = [{"path": item["path"], "run_id": item["run_id"], "errors": sorted(set(item["errors"]))} for item in validations if not item["canonical"]]

    staging: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    orphaned: list[dict[str, Any]] = []
    outside: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    outside.extend(disallowed_indexed_paths)
    blocked.extend(disallowed_indexed_paths)
    indexed_file_paths = indexed_paths | {f"{item['path']}/index.json" if item["path"] else "index.json" for item in validations}
    file_map = {item["path"]: item for item in files}
    dirs = _tree_directories(outer_root, exclude={"quarantine", *excluded})
    for rel in dirs:
        if rel in indexed_directory_paths:
            continue
        kind = _candidate_kind(rel, True)
        if not kind:
            continue
        full = _path_from_relative(outer_root, rel)
        digest, count = _tree_digest(full)
        proof_ok, proof, proof_reason = _read_provenance(full, outer_root, digest=digest, relative=rel)
        row = {
            "path": rel, "sha256": digest, "byte_count": count, "classification": kind,
            "provenance": proof, "provenance_status": "proven" if proof_ok else "blocked", "reason": proof_reason,
            "in_dependency_closure": digest in closure_digests, "retained": digest in retained_digests,
            "eligible_for_quarantine": bool(proof_ok and digest not in closure_digests and digest not in retained_digests and digest in approved_digests),
        }
        staging.append(row)
        if kind == "orphaned-content-addressed-tree":
            orphaned.append(row)
        (candidates if row["eligible_for_quarantine"] else blocked).append(row)

    nominated_dirs = {row["path"] for row in staging}
    for rel, item in sorted(file_map.items()):
        if (
            rel in indexed_file_paths
            or rel == "index.json"
            or rel.startswith("quarantine/")
            or rel.rsplit("/", 1)[-1] in PROVENANCE_NAMES
            or any(rel.startswith(directory + "/") for directory in nominated_dirs)
        ):
            continue
        kind = _candidate_kind(rel, False)
        full = _path_from_relative(outer_root, rel)
        if kind:
            proof_ok, proof, proof_reason = _read_provenance(full, outer_root, digest=item["sha256"], relative=rel)
            row = {
                **item, "classification": kind, "provenance": proof,
                "provenance_status": "proven" if proof_ok else "blocked", "reason": proof_reason,
                "in_dependency_closure": item["sha256"] in closure_digests, "retained": item["sha256"] in retained_digests,
                "eligible_for_quarantine": bool(proof_ok and item["sha256"] not in closure_digests and item["sha256"] not in retained_digests and item["sha256"] in approved_digests),
            }
            stale.append(row)
            (candidates if row["eligible_for_quarantine"] else blocked).append(row)
        else:
            row = {**item, "classification": "outside-allowed-root", "eligible_for_quarantine": False, "reason": "not indexed under a canonical sealed root"}
            outside.append(row)
            blocked.append(row)
    for row in reparses:
        blocked.append({**row, "classification": "undeclared-reparse-point", "eligible_for_quarantine": False, "reason": "reparse points are never followed or moved"})
    for item in validations:
        if not item["canonical"] and item["errors"]:
            outside.append({"path": item["path"], "classification": "outside-allowed-root", "eligible_for_quarantine": False, "reason": "run root failed canonical seal validation"})

    def unique_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            result[str(row.get("path", ""))] = row
        return [result[key] for key in sorted(result)]

    staging, stale, orphaned, outside, candidates, blocked = (unique_rows(rows) for rows in (staging, stale, orphaned, outside, candidates, blocked))
    report: dict[str, Any] = {
        "schema": CLEANUP_SCHEMA, "mode": "report", "root": str(outer_root),
        "selected_run_root": _relative(run_root, outer_root), "excluded_paths": sorted(excluded),
        "canonical_sealed_roots": sorted(canonical_rows, key=lambda item: item["path"]),
        "abandoned_staging_dirs": staging, "stale_temp_raw_evidence": stale,
        "orphaned_content_addressed_trees": orphaned, "duplicated_run_ids": duplicates,
        "undeclared_reparse_points": sorted(reparses, key=lambda item: item["path"]),
        "artifacts_outside_allowed_roots": outside, "uncertain_runs": uncertain_runs,
        "quarantine_candidates": candidates, "blocked": blocked,
        "dependency_closure_sha256": sha256(_json_bytes(sorted(closure_digests))),
        "retained_digest_set_sha256": sha256(_json_bytes(sorted(retained_digests))),
        "approved_quarantine_digest_set_sha256": sha256(_json_bytes(sorted(approved_digests))),
        "snapshot_sha256": _snapshot_hash(files, reparses), "release_ready": False,
        "status": "BLOCKED" if (duplicates or reparses or uncertain_runs or blocked) else "PASS",
    }
    return report


def _with_self_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(value)
    body.pop("self_sha256", None)
    body["self_sha256"] = sha256(_json_bytes(body))
    return body


def build_cleanup_plan(report: Mapping[str, Any]) -> dict[str, Any]:
    """Turn an inventory report into a hash-bound, still non-mutating plan."""
    if report.get("schema") != CLEANUP_SCHEMA:
        raise CleanupError("cleanup report schema mismatch")
    candidates = report.get("quarantine_candidates")
    if not isinstance(candidates, list):
        raise CleanupError("cleanup report candidates are malformed")
    plan = {
        "schema": CLEANUP_SCHEMA, "mode": "plan", "root": report.get("root"),
        "excluded_paths": report.get("excluded_paths", []), "snapshot_sha256": report.get("snapshot_sha256"),
        "retained_digest_set_sha256": report.get("retained_digest_set_sha256"),
        "approved_quarantine_digest_set_sha256": report.get("approved_quarantine_digest_set_sha256"),
        "candidates": sorted(candidates, key=lambda item: str(item.get("path", ""))),
        "blocked_count": len(report.get("blocked", [])) if isinstance(report.get("blocked"), list) else None,
        "release_ready": False,
    }
    return _with_self_hash(plan)


def _verify_plan(plan: Mapping[str, Any], expected_sha256: str | None = None) -> None:
    if plan.get("schema") != CLEANUP_SCHEMA or plan.get("mode") != "plan":
        raise CleanupError("cleanup plan schema/mode mismatch")
    declared = plan.get("self_sha256")
    body = {key: value for key, value in plan.items() if key != "self_sha256"}
    if not isinstance(declared, str) or declared != sha256(_json_bytes(body)):
        raise CleanupError("cleanup plan self-hash mismatch")
    if expected_sha256 is not None and declared != expected_sha256:
        raise CleanupError("cleanup plan digest mismatch")


def _quarantine_root(root: Path, *, create: bool) -> Path:
    quarantine = root / "quarantine"
    if not _safe_path(quarantine, root) or _is_reparse(quarantine):
        raise CleanupError("quarantine root is unsafe")
    try:
        exists = quarantine.exists()
    except OSError as exc:
        raise CleanupError(f"quarantine root inspection failed: {quarantine}: {exc}") from exc
    if not exists:
        if not create:
            return quarantine
        try:
            quarantine.mkdir()
        except FileExistsError:
            pass
        except OSError as exc:
            raise CleanupError(f"quarantine root creation failed: {quarantine}: {exc}") from exc
    if not _directory(quarantine) or not _safe_path(quarantine, root):
        raise CleanupError("quarantine root is not a safe directory")
    return quarantine


def _rename_noreplace(source: Path, destination: Path) -> None:
    """Rename without replacing an object that appeared after our snapshot.

    ``os.rename`` is the no-replace primitive on Windows.  POSIX ``rename``
    replaces an existing destination, so use Linux ``renameat2`` where it is
    available and otherwise fail closed rather than risk overwriting a
    quarantine object.
    """
    if os.name == "nt":
        os.rename(source, destination)
        return
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
    except (AttributeError, OSError) as exc:
        raise CleanupError("atomic no-replace quarantine move is unavailable") from exc
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        -100,
        os.fsencode(source),
        -100,
        os.fsencode(destination),
        1,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), str(destination))


def _atomic_move(source: Path, destination: Path, root: Path) -> None:
    quarantine = _quarantine_root(root, create=True)
    if destination.parent != quarantine or not _safe_path(destination, root):
        raise CleanupError(f"quarantine destination escapes root: {destination}")
    if _is_reparse(destination.parent) or not _directory(destination.parent):
        raise CleanupError(f"quarantine destination parent is unsafe: {destination.parent}")
    if destination.exists() or _is_reparse(destination):
        raise CleanupError(f"quarantine destination already exists: {destination}")
    try:
        _rename_noreplace(source, destination)
    except (FileExistsError, OSError) as exc:
        if isinstance(exc, FileExistsError) or getattr(exc, "errno", None) == errno.EEXIST:
            raise ConcurrentChangeError(f"quarantine destination appeared during move: {destination}") from exc
        raise CleanupError(f"atomic quarantine move failed: {source}: {exc}") from exc


def quarantine_artifacts(root: str | os.PathLike[str], plan: Mapping[str, Any], *, expected_plan_sha256: str | None = None, approved: bool = True) -> dict[str, Any]:
    """Atomically move only already-proven candidates; never delete bytes."""
    if not approved:
        raise CleanupError("quarantine requires explicit operator approval")
    _verify_plan(plan, expected_plan_sha256)
    root_path = Path(root).absolute()
    excludes = plan.get("excluded_paths", [])
    if not isinstance(excludes, list):
        raise CleanupError("cleanup plan excluded paths malformed")
    report = inventory_artifacts(root_path, exclude=excludes)
    current_plan = build_cleanup_plan(report)
    if current_plan.get("snapshot_sha256") != plan.get("snapshot_sha256"):
        raise ConcurrentChangeError("artifact tree changed since cleanup plan")
    if current_plan.get("self_sha256") != plan.get("self_sha256"):
        raise ConcurrentChangeError("cleanup plan no longer matches current inventory")
    candidates = plan.get("candidates")
    if not isinstance(candidates, list):
        raise CleanupError("cleanup plan candidates malformed")
    quarantine_root = root_path / "quarantine"
    moved: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, Mapping):
            raise CleanupError("cleanup candidate is malformed")
        relative, digest = item.get("path"), item.get("sha256")
        if not isinstance(relative, str) or not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise CleanupError("cleanup candidate path/digest malformed")
        source = _path_from_relative(root_path, relative)
        if _is_reparse(source):
            raise ConcurrentChangeError(f"candidate became a reparse point: {relative}")
        actual_digest, actual_count = _tree_digest(source)
        if actual_digest != digest or actual_count != item.get("byte_count"):
            raise ConcurrentChangeError(f"candidate changed since cleanup plan: {relative}")
        destination = quarantine_root / digest
        _atomic_move(source, destination, root_path)
        moved.append({"source": relative, "destination": f"quarantine/{digest}", "sha256": digest, "byte_count": actual_count})
    for item in moved:
        destination = root_path / item["destination"]
        actual_digest, actual_count = _tree_digest(destination)
        if actual_digest != item["sha256"] or actual_count != item["byte_count"]:
            raise CleanupError(f"quarantine destination verification failed: {item['destination']}")
    return _with_self_hash({
        "schema": CLEANUP_SCHEMA, "mode": "quarantine", "root": str(root_path),
        "plan_sha256": plan["self_sha256"], "snapshot_sha256": plan.get("snapshot_sha256"),
        "moved": moved, "bytes_removed": 0, "release_ready": False, "status": "PASS",
    })




def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    body = _json_bytes(value)
    if path.exists() or _is_reparse(path):
        raise CleanupError(f"output already exists or is unsafe: {path}")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CleanupError(f"output directory creation failed: {path.parent}: {exc}") from exc
    if not _directory(path.parent):
        raise CleanupError(f"output parent is not a safe directory: {path.parent}")
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("xb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        # Never replace an existing artifact.  Windows rename is no-replace;
        # POSIX hard-linking gives the same atomic destination reservation.
        if os.name == "nt":
            os.rename(temporary, path)
        else:
            os.link(temporary, path)
            temporary.unlink()
        if path.read_bytes() != body:
            raise CleanupError(f"output reopen validation failed: {path}")
    except FileExistsError as exc:
        raise CleanupError(f"output already exists: {path}") from exc
    except OSError as exc:
        raise CleanupError(f"output write failed: {path}: {exc}") from exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _new_output_path(root: Path, raw: Path | str) -> Path:
    """Resolve a CLI output slot without permitting root escape or overwrite."""
    if not _directory(root):
        raise CleanupError(f"root is not a safe directory: {root}")
    path = _resolve_inside(root, str(raw))
    if path == root or path.exists() or _is_reparse(path):
        raise CleanupError(f"output already exists or is unsafe: {path}")
    relative = _relative(path, root)
    if relative == "quarantine" or relative.startswith("quarantine/"):
        raise CleanupError("output may not be written under quarantine")
    if not _safe_path(path.parent, root):
        raise CleanupError(f"output parent escapes root: {path.parent}")
    if path.parent.exists() and not _directory(path.parent):
        raise CleanupError(f"output parent is not a safe directory: {path.parent}")
    return path

def _load_digest_file(path: Path) -> str:
    value, raw = _load_json(path)
    if isinstance(value, Mapping):
        for key in ("sha256", "self_sha256", "result_sha256", "index_sha256"):
            item = value.get(key)
            if isinstance(item, str) and SHA256_RE.fullmatch(item):
                return item
    text = raw.decode("utf-8").strip()
    if SHA256_RE.fullmatch(text):
        return text
    raise CleanupError(f"digest file has no SHA-256 value: {path}")


def _resolve_inside(root: Path, raw: str) -> Path:
    candidate = Path(raw)
    resolved = candidate.absolute() if candidate.is_absolute() else (root / candidate).absolute()
    if not _safe_path(resolved, root):
        raise CleanupError(f"path escapes root: {raw}")
    return resolved


def _approval(expected: str, noun: str = "cleanup plan") -> None:
    if not sys.stdin.isatty():
        raise CleanupError(f"{noun} requires an interactive approval or direct API approval")
    typed = input(f"Type the exact {noun} SHA-256 to continue: ").strip()
    if typed != expected:
        raise CleanupError(f"{noun} approval digest mismatch")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inventory and fail-closed quarantine planning for CassiFI artifact trees")
    parser.add_argument("--mode", choices=("report", "plan", "quarantine", "apply"), default="report")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--expected-plan-sha256", type=str)
    parser.add_argument("--approved-digests", type=Path)
    parser.add_argument("--expected-index-sha256", type=str)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        root = args.root.absolute()
        output_path = _new_output_path(root, args.out) if args.out is not None else None
        exclude: set[str] = set()
        if output_path is not None:
            exclude.add(_relative(output_path, root))
        report = inventory_artifacts(root, run_id=args.run_id, exclude=exclude)
        if args.expected_index_sha256:
            selected = report.get("selected_run_root")
            index_path = root / selected / "index.json" if selected else root / "index.json"
            if not _regular(index_path) or sha256(index_path.read_bytes()) != args.expected_index_sha256:
                raise CleanupError("expected index digest mismatch")
        if args.approved_digests:
            policy_path = _resolve_inside(root, str(args.approved_digests))
            policy, raw = _load_json(policy_path)
            if not isinstance(policy, Mapping):
                raise CleanupError("approved digest policy must be a JSON object")
            approved, _ = _extract_digest_sets(policy)
            report["approved_quarantine_digest_set_sha256"] = sha256(_json_bytes(sorted(approved)))
            report["approved_digests_source"] = _relative(policy_path, root)
            report["approved_digests_source_sha256"] = sha256(raw)
            for item in report.get("quarantine_candidates", []):
                item["eligible_for_quarantine"] = item.get("sha256") in approved and not item.get("in_dependency_closure") and not item.get("retained")
            report["quarantine_candidates"] = [item for item in report.get("quarantine_candidates", []) if item.get("eligible_for_quarantine")]
        if args.mode == "report":
            output: Mapping[str, Any] = report
        elif args.mode == "plan":
            output = build_cleanup_plan(report)
        else:
            if args.plan:
                plan_value, _ = _load_json(_resolve_inside(root, str(args.plan)))
                if not isinstance(plan_value, Mapping):
                    raise CleanupError("cleanup plan must be a JSON object")
                plan: Mapping[str, Any] = plan_value
            else:
                plan = build_cleanup_plan(report)
            _verify_plan(plan, args.expected_plan_sha256)
            expected = plan["self_sha256"]
            _approval(expected)
            output = quarantine_artifacts(root, plan, expected_plan_sha256=expected)
        if output_path is not None:
            _write_json(output_path, output)
        else:
            sys.stdout.write(_json_bytes(output).decode("utf-8") + "\n")
        return 0
    except CleanupError as exc:
        sys.stderr.write(f"artifact cleanup blocked: {exc}\n")
        return 2


    "CLEANUP_SCHEMA", "CleanupError", "ConcurrentChangeError", "build_cleanup_plan",
    "inventory_artifacts", "main", "quarantine_artifacts", "sha256",


if __name__ == "__main__":
    raise SystemExit(main())
