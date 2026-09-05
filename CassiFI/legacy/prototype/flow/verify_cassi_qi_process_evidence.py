"""Independently verify the bounded G12E process/source evidence artifact.

The verifier intentionally imports neither a runtime/provider nor a receipt
builder.  It treats every retained observation as untrusted input, derives
Qwen/GGUF/llama/KV counters from native records, and fails closed when ETW or a
required Win32 observation is absent.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
from typing import Any, Iterable, Mapping

from cassi_qi_bootstrap import canonical_hash, canonical_json_bytes, canonical_json_loads


PROCESS_EVIDENCE_SCHEMA = "cassi.qi-flow-process-evidence.v1"
COMMANDS_SCHEMA = "cassi.qi-flow-process-evidence-commands.v1"
RAW_INDEX_SCHEMA = "cassi.qi-flow-process-evidence-raw-index.v1"
PARSER_SCHEMA = "cassi.qi-flow-process-evidence-parser.v1"
STATUS_SCHEMA = "cassi.qi-flow-g12e-status.v1"
PROCESS_SNAPSHOT_SCHEMA = "cassi.qi-flow-process-evidence-processes.v1"
MODULE_SNAPSHOT_SCHEMA = "cassi.qi-flow-process-evidence-modules.v1"
SOCKET_SNAPSHOT_SCHEMA = "cassi.qi-flow-process-evidence-sockets.v1"
FILE_READ_SCHEMA = "cassi.qi-flow-process-evidence-file-reads.v1"
SYS_MODULES_SCHEMA = "cassi.qi-flow-process-evidence-sys-modules.v1"
JOB_MEMORY_SCHEMA = "cassi.qi-flow-process-evidence-job-memory.v1"
TRACE_SCHEMA = "cassi.qi-flow-process-evidence-trace.v1"
MANIFEST_SCHEMA = "cassi.qi-flow-process-capture-manifest.v1"
RAW_BYTES_DOMAIN = "cassi.qi-flow-raw-bytes.v1"

MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_TRACE_BYTES = 256 * 1024 * 1024
MAX_IDENTITY_FILE_BYTES = 64 * 1024 * 1024
MAX_CHUNK_BYTES = 1 * 1024 * 1024
MAX_CHUNKS = 4096
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")

# These are basenames/components, not arbitrary path substrings.  The
# repository itself is named CassiQwen, which must not make every Python path a
# false positive.
_FORBIDDEN_BASENAME_TERMS = (
    "qwen",
    "gguf",
    "llama",
    "teacher",
    "baseline",
    "kv-cache",
    "kv_cache",
    "native-kv",
    "native_kv",
)


class VerificationError(RuntimeError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _obj_hash(value: Any, schema: str) -> str:
    return canonical_hash(value, schema)
def _frame(payload: bytes) -> bytes:
    return len(payload).to_bytes(8, "big") + payload


def _raw_bytes_sha256(payload: bytes) -> str:
    return _sha256(_frame(RAW_BYTES_DOMAIN.encode("utf-8")) + _frame(payload))


def _manifest_hash(value: Mapping[str, Any]) -> str:
    return _sha256(_frame(MANIFEST_SCHEMA.encode("utf-8")) + _frame(canonical_json_bytes(value)))


def _write_json(path: Path, value: Any) -> bytes:
    payload = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def _load_json(path: Path, limit: int = MAX_JSON_BYTES) -> tuple[Any, bytes]:
    try:
        if path.stat().st_size > limit:
            raise VerificationError(f"JSON exceeds bounded limit: {path}")
        raw = path.read_bytes()
        value = canonical_json_loads(raw)
    except (OSError, UnicodeError, ValueError) as exc:
        raise VerificationError(f"cannot load canonical JSON {path}: {exc}") from exc
    return value, raw


def _digest(value: Any, name: str) -> str | None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        return None
    return value.lower()


def _safe_artifact_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise VerificationError(f"artifact path is not relative: {relative!r}")
    candidate = (root / relative).resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise VerificationError(f"artifact path escapes run root: {relative!r}") from exc
    if candidate.exists() and candidate.is_symlink():
        raise VerificationError(f"symlink evidence path is not accepted: {relative!r}")
    return candidate


def _plain_name(value: Any) -> str:
    text = str(value or "").replace("\\", "/")
    return text.rsplit("/", 1)[-1].casefold()


def _forbidden_path(value: Any) -> bool:
    text = str(value or "").replace("\\", "/").casefold()
    for component in (part for part in text.split("/") if part):
        if component in _FORBIDDEN_BASENAME_TERMS:
            return True
        if any(component.startswith(term + suffix) for term in _FORBIDDEN_BASENAME_TERMS for suffix in (".", "-", "_")):
            return True
    return False
def _forbidden_basename(value: Any) -> bool:
    name = _plain_name(value)
    return any(term in name for term in _FORBIDDEN_BASENAME_TERMS)


def _command_first_basename(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text:
        return ""
    try:
        parts = shlex.split(text, posix=False)
    except ValueError:
        parts = [text]
    return _plain_name(parts[0] if parts else "")


def _find_path_rows(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
            rows.append(dict(value))
        for child in value.values():
            rows.extend(_find_path_rows(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(_find_path_rows(child))
    return rows


def _find_path_strings(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_name = str(key).casefold()
            if isinstance(child, str) and ("path" in key_name or "file" in key_name or "model" in key_name or "weight" in key_name):
                result.append(child)
            elif isinstance(child, list) and ("path" in key_name or "file" in key_name):
                result.extend(item for item in child if isinstance(item, str))
            else:
                result.extend(_find_path_strings(child))
    elif isinstance(value, list):
        result.extend(item for child in value for item in (_find_path_strings(child) if not isinstance(child, str) else [child]))
    return result


def _canonical_path(value: str, source_root: Path) -> str:
    path = Path(value)
    if not path.is_absolute():
        path = source_root / path
    return os.path.normcase(str(path.resolve(strict=False))).replace("\\", "/")


def _check_self_hash(value: Mapping[str, Any], schema: str) -> bool:
    observed = value.get("self_sha256")
    if not isinstance(observed, str):
        return False
    body = {key: item for key, item in value.items() if key != "self_sha256"}
    return observed == _obj_hash(body, schema)


def _check(checks: list[dict[str, Any]], name: str, ok: bool, detail: str, severity: str = "fail") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail, "severity": severity})


def _load_required(
    gate_root: Path,
    relative: str,
    checks: list[dict[str, Any]],
    required: bool = True,
    limit: int = MAX_JSON_BYTES,
) -> tuple[Any | None, bytes | None]:
    try:
        path = _safe_artifact_path(gate_root, relative)
        if not path.exists():
            _check(checks, f"present:{relative}", False, "missing evidence", "blocked" if required else "fail")
            return None, None
        value, raw = _load_json(path, limit)
        _check(checks, f"read:{relative}", True, "loaded")
        return value, raw
    except VerificationError as exc:
        _check(checks, f"read:{relative}", False, str(exc), "blocked")
        return None, None


def _verify_raw_index(gate_root: Path, root: Mapping[str, Any], checks: list[dict[str, Any]]) -> tuple[Mapping[str, Any] | None, dict[str, bytes]]:
    index_path = gate_root / "process-evidence-raw-index.json"
    if not index_path.exists():
        _check(checks, "raw-index-present", False, "missing process-evidence-raw-index.json", "blocked")
        return None, {}
    try:
        index, raw = _load_json(index_path)
    except VerificationError as exc:
        _check(checks, "raw-index-readable", False, str(exc), "blocked")
        return None, {}
    if not isinstance(index, Mapping):
        _check(checks, "raw-index-object", False, "raw index is not an object", "blocked")
        return None, {}
    _check(checks, "raw-index-schema", index.get("schema") == RAW_INDEX_SCHEMA, "schema mismatch" if index.get("schema") != RAW_INDEX_SCHEMA else "schema ok")
    _check(checks, "raw-index-self-hash", _check_self_hash(index, RAW_INDEX_SCHEMA), "self hash mismatch" if not _check_self_hash(index, RAW_INDEX_SCHEMA) else "self hash ok")
    _check(
        checks,
        "raw-index-capture-binding",
        index.get("capture_id") == root.get("capture_id"),
        "capture_id binding ok" if index.get("capture_id") == root.get("capture_id") else "raw index capture_id mismatch",
        "blocked",
    )
    _check(
        checks,
        "raw-index-receipt-binding",
        index.get("receipt_id") == root.get("receipt_id"),
        "receipt_id binding ok" if index.get("receipt_id") == root.get("receipt_id") else "raw index receipt_id mismatch",
        "blocked",
    )
    blobs: dict[str, bytes] = {}
    rows = index.get("raw_files")
    if not isinstance(rows, list) or not rows:
        _check(checks, "raw-index-files", False, "raw_files is missing or empty", "blocked")
        return index, blobs
    for row in rows:
        if not isinstance(row, Mapping):
            _check(checks, "raw-index-row", False, "malformed raw file row")
            continue
        relative = row.get("path")
        expected = row.get("sha256")
        expected_count = row.get("byte_count")
        try:
            path = _safe_artifact_path(gate_root, relative)
            payload = path.read_bytes()
            ok = _digest(expected, "raw file hash") == _sha256(payload) and expected_count == len(payload)
            if ok:
                blobs[str(relative)] = payload
            _check(checks, f"raw:{relative}", ok, "digest/size ok" if ok else "digest or size mismatch")
        except (OSError, VerificationError) as exc:
            _check(checks, f"raw:{relative}", False, str(exc), "blocked")
    return index, blobs
def _decode_blob(value: Any, checks: list[dict[str, Any]], name: str) -> bytes | None:
    if not isinstance(value, Mapping):
        _check(checks, f"{name}-blob", False, "byte blob is not an object", "blocked")
        return None
    if value.get("encoding") != "base64url-unpadded-v1":
        _check(checks, f"{name}-blob", False, "unsupported byte-blob encoding", "blocked")
        return None
    encoded = value.get("base64url")
    if not isinstance(encoded, str) or "=" in encoded:
        _check(checks, f"{name}-blob", False, "base64url blob is not unpadded text", "blocked")
        return None
    try:
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (ValueError, UnicodeError) as exc:
        _check(checks, f"{name}-blob", False, f"invalid base64url blob: {exc}", "blocked")
        return None
    ok = (
        isinstance(value.get("byte_count"), int)
        and not isinstance(value.get("byte_count"), bool)
        and value["byte_count"] == len(payload)
        and value.get("bytes_sha256") == _raw_bytes_sha256(payload)
    )
    _check(checks, f"{name}-blob", ok, "byte blob digest ok" if ok else "byte blob digest/size mismatch", "blocked" if not ok else "fail")
    return payload if ok else None


def _verify_capture_manifest(
    gate_root: Path,
    root: Mapping[str, Any],
    checks: list[dict[str, Any]],
    expected_hash: Any,
    role: str,
    window: str,
) -> tuple[Mapping[str, Any] | None, bytes]:
    expected = _digest(expected_hash, f"{role}.artifact_sha256")
    if expected is None:
        _check(checks, f"manifest-ref:{role}:{window}", False, "invalid manifest digest reference", "blocked")
        return None, b""
    manifest_dir = gate_root / "raw" / "manifests"
    try:
        candidates = sorted(manifest_dir.glob("*.json"))
    except OSError as exc:
        _check(checks, f"manifest-dir:{role}:{window}", False, str(exc), "blocked")
        return None, b""
    for path in candidates:
        try:
            value, raw = _load_json(path, MAX_JSON_BYTES)
        except VerificationError:
            continue
        if not isinstance(value, Mapping) or value.get("artifact_sha256") != expected:
            continue
        body = {key: item for key, item in value.items() if key != "artifact_sha256"}
        hash_ok = _manifest_hash(body) == expected
        role_ok = value.get("capture_role") == role
        window_ok = value.get("capture_window") == window
        capture_ok = value.get("capture_id") == root.get("capture_id")
        _check(checks, f"manifest-hash:{role}:{window}", hash_ok, "manifest digest ok" if hash_ok else "manifest digest mismatch", "blocked" if not hash_ok else "fail")
        _check(checks, f"manifest-role:{role}:{window}", role_ok and window_ok and capture_ok, "capture identity ok" if role_ok and window_ok and capture_ok else "capture identity mismatch", "blocked" if not role_ok or not window_ok or not capture_ok else "fail")
        chunks = value.get("chunks")
        payload = bytearray()
        chunks_ok = isinstance(chunks, list) and len(chunks) <= MAX_CHUNKS
        if not chunks_ok:
            _check(checks, f"manifest-chunks:{role}:{window}", False, "chunk list missing or exceeds bound", "blocked")
            chunks = []
        for ordinal, row in enumerate(chunks):
            if not isinstance(row, Mapping) or row.get("ordinal") != ordinal:
                chunks_ok = False
                _check(checks, f"manifest-chunk-order:{role}:{window}:{ordinal}", False, "chunk ordinal is not contiguous", "blocked")
                continue
            byte_count = row.get("byte_count")
            digest = _digest(row.get("raw_bytes_sha256"), "chunk.raw_bytes_sha256")
            chunk_name = f"{path.stem}-{ordinal:04d}.bin"
            relative = f"raw/chunks/{chunk_name}"
            try:
                chunk_path = _safe_artifact_path(gate_root, relative)
                chunk = chunk_path.read_bytes()
            except (OSError, VerificationError) as exc:
                chunks_ok = False
                _check(checks, f"manifest-chunk:{role}:{window}:{ordinal}", False, str(exc), "blocked")
                continue
            chunk_ok = digest is not None and isinstance(byte_count, int) and not isinstance(byte_count, bool) and 0 <= byte_count <= MAX_CHUNK_BYTES and byte_count == len(chunk) and digest == _raw_bytes_sha256(chunk)
            _check(checks, f"manifest-chunk:{role}:{window}:{ordinal}", chunk_ok, "chunk digest ok" if chunk_ok else "chunk digest/size mismatch", "blocked" if not chunk_ok else "fail")
            if chunk_ok:
                payload.extend(chunk)
        total_ok = value.get("total_raw_byte_count") == len(payload) and value.get("concatenated_raw_bytes_sha256") == _raw_bytes_sha256(bytes(payload))
        _check(checks, f"manifest-total:{role}:{window}", chunks_ok and total_ok, "capture bytes reconcile" if chunks_ok and total_ok else "capture byte reconciliation failed", "blocked" if not chunks_ok or not total_ok else "fail")
        producer = value.get("producer")
        producer_ok = isinstance(producer, Mapping) and isinstance(producer.get("tool_name"), str) and isinstance(producer.get("tool_version"), str)
        _check(checks, f"manifest-producer:{role}:{window}", producer_ok, "producer identity present" if producer_ok else "producer identity missing", "blocked" if not producer_ok else "fail")
        if isinstance(producer, Mapping):
            _decode_blob(producer.get("command"), checks, f"manifest-producer:{role}:{window}")
        return value, bytes(payload)
    _check(checks, f"manifest-present:{role}:{window}", False, "referenced capture manifest is missing", "blocked")
    return None, b""


def _verify_capture_manifests(
    gate_root: Path,
    root: Mapping[str, Any],
    checks: list[dict[str, Any]],
) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    refs: list[tuple[str, str, Any]] = [("provider-command", "whole-lifetime", root.get("provider_command_sha256")), ("etw-trace", "whole-lifetime", root.get("etw_trace_manifest_sha256")), ("sys-modules", "during", root.get("sys_modules_manifest_sha256")), ("file-read-summary", "whole-lifetime", root.get("file_read_summary_sha256"))]
    for phase, digest in zip(("before", "during", "after"), root.get("toolhelp_inventory_sha256s", []) if isinstance(root.get("toolhelp_inventory_sha256s"), list) else []):
        refs.append(("toolhelp-inventory", phase, digest))
    for phase, digest in zip(("before", "during", "after"), root.get("socket_inventory_sha256s", []) if isinstance(root.get("socket_inventory_sha256s"), list) else []):
        refs.append(("socket-inventory", phase, digest))
    expected_names = {"provider-command", "etw-trace", "sys-modules", "file-reads", *(f"toolhelp-{phase}" for phase in ("before", "during", "after")), *(f"socket-{phase}" for phase in ("before", "during", "after"))}
    # Manifest filenames are producer-selected but the runner's names are
    # stable; reject extra capture files so an unreferenced observation cannot
    # silently satisfy a required family.
    manifest_dir = gate_root / "raw" / "manifests"
    try:
        manifest_names = {path.stem for path in manifest_dir.glob("*.json")}
        _check(checks, "manifest-set", manifest_names == expected_names, "manifest set is exact" if manifest_names == expected_names else "unexpected or missing manifest file", "blocked" if manifest_names != expected_names else "fail")
    except OSError as exc:
        _check(checks, "manifest-set", False, str(exc), "blocked")
    for role, window, digest in refs:
        key = f"{role}:{window}"
        manifest, payload = _verify_capture_manifest(gate_root, root, checks, digest, role, window)
        payloads[key] = payload
        if manifest is not None and role == "provider-command":
            commands = manifest.get("commands")
            results = manifest.get("results")
            _check(checks, "manifest-provider-commands", isinstance(commands, list) and bool(commands), "provider command rows present" if isinstance(commands, list) and commands else "provider command rows missing", "blocked" if not isinstance(commands, list) or not commands else "fail")
            _check(checks, "manifest-provider-results", isinstance(results, list) and bool(results), "provider lifecycle results present" if isinstance(results, list) and results else "provider lifecycle results missing", "blocked" if not isinstance(results, list) or not results else "fail")
    lifetime = root.get("lifetime")
    if not isinstance(lifetime, Mapping):
        _check(checks, "lifetime-object", False, "lifetime markers missing", "blocked")
    else:
        for marker_name, event in (("start", "job-created"), ("end", "job-exited")):
            relative = f"raw/markers/{marker_name}.json"
            value, raw = _load_required(gate_root, relative, checks)
            expected = lifetime.get(f"{marker_name}_marker_sha256")
            marker_ok = isinstance(value, Mapping) and expected == _sha256(raw or b"") and value.get("event") == event and value.get("capture_id") == root.get("capture_id")
            _check(checks, f"lifetime-marker:{marker_name}", marker_ok, "lifetime marker identity ok" if marker_ok else "lifetime marker missing/mutated", "blocked" if not marker_ok else "fail")
    return payloads


def _verify_identity_manifest(
    label: str,
    value: Any,
    source_root: Path | None,
    checks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[str]]:
    rows = _find_path_rows(value)
    _check(checks, f"{label}-rows", bool(rows), f"{len(rows)} hashed path rows", "blocked" if not rows else "fail")
    seen: set[str] = set()
    paths: set[str] = set()
    if source_root is None:
        _check(checks, f"{label}-source-root", False, "source root unavailable", "blocked")
        return rows, paths
    for index, row in enumerate(rows):
        path_value = row.get("path")
        expected = _digest(row.get("sha256"), f"{label}[{index}].sha256")
        if expected is None:
            _check(checks, f"{label}-digest:{index}", False, "invalid SHA-256 digest")
            continue
        canonical = _canonical_path(str(path_value), source_root)
        if canonical in seen:
            _check(checks, f"{label}-unique:{index}", False, "duplicate canonical path")
            continue
        seen.add(canonical)
        paths.add(canonical)
        path = Path(canonical)
        try:
            if not path.exists() or not path.is_file():
                _check(checks, f"{label}-exists:{index}", False, "source path is absent", "blocked")
                continue
            if path.stat().st_size > MAX_IDENTITY_FILE_BYTES:
                _check(checks, f"{label}-bounded:{index}", False, "source path exceeds verifier bound", "blocked")
                continue
            observed = _sha256(path.read_bytes())
            _check(checks, f"{label}-digest:{index}", observed == expected, "digest ok" if observed == expected else "source mutation")
        except OSError as exc:
            _check(checks, f"{label}-read:{index}", False, str(exc), "blocked")
    return rows, paths


def _verify_command_files(
    gate_root: Path,
    commands: Any,
    checks: list[dict[str, Any]],
) -> set[str]:
    if not isinstance(commands, Mapping):
        _check(checks, "commands-object", False, "commands record is not an object", "blocked")
        return set()
    _check(checks, "commands-schema", commands.get("schema") == COMMANDS_SCHEMA, "schema mismatch" if commands.get("schema") != COMMANDS_SCHEMA else "schema ok")
    _check(checks, "commands-self-hash", _check_self_hash(commands, COMMANDS_SCHEMA), "self hash mismatch" if not _check_self_hash(commands, COMMANDS_SCHEMA) else "self hash ok")
    _check(checks, "commands-shell", commands.get("shell") is False, "shell execution is forbidden" if commands.get("shell") is not False else "shell disabled")
    entries: list[Mapping[str, Any]] = []
    runtime = commands.get("runtime")
    if isinstance(runtime, Mapping):
        entries.append(runtime)
    scenarios = commands.get("scenarios")
    if isinstance(scenarios, list):
        entries.extend(item for item in scenarios if isinstance(item, Mapping))
    required = {"runtime", "startup", "fresh_request", "restart", "retry", "shutdown"}
    observed_names = {str(row.get("name")) for row in entries}
    _check(checks, "commands-complete", required <= observed_names, "missing frozen command" if not required <= observed_names else "all frozen commands present", "blocked" if not required <= observed_names else "fail")
    command_paths: set[str] = set()
    for row in entries:
        name = str(row.get("name"))
        relative = row.get("path")
        try:
            path = _safe_artifact_path(gate_root, relative)
            raw = path.read_bytes()
            expected = _digest(row.get("source_sha256"), f"command {name}")
            digest_ok = expected == _sha256(raw) and row.get("source_byte_count") == len(raw)
            _check(checks, f"command-source:{name}", digest_ok, "source digest ok" if digest_ok else "command source mutated")
            command_paths.add(str(relative))
            source = json.loads(raw.decode("utf-8"))
            if isinstance(source, list):
                source = {"argv": source}
            argv = source.get("argv", source.get("command")) if isinstance(source, Mapping) else None
            argv_ok = isinstance(argv, list) and list(argv) == list(row.get("argv", [])) and all(isinstance(item, str) and item for item in argv)
            _check(checks, f"command-argv:{name}", argv_ok, "argv ok" if argv_ok else "argv mutation or invalid argv")
            env = source.get("env", {}) if isinstance(source, Mapping) else {}
            env_ok = isinstance(env, Mapping) and row.get("env_sha256") == _sha256(canonical_json_bytes({str(k): str(v) for k, v in sorted(env.items())}))
            _check(checks, f"command-env:{name}", env_ok, "environment identity ok" if env_ok else "environment mutation")
        except (OSError, UnicodeError, json.JSONDecodeError, VerificationError) as exc:
            _check(checks, f"command-source:{name}", False, str(exc), "blocked")
    return command_paths


def _verify_command_results(value: Any, checks: list[dict[str, Any]]) -> None:
    required = {"terminal-provider-startup", "fresh-request", "restart", "retry", "shutdown"}
    if not isinstance(value, Mapping) or not isinstance(value.get("results"), list):
        _check(checks, "command-results", False, "command result list missing", "blocked")
        return
    rows = [row for row in value["results"] if isinstance(row, Mapping)]
    phases = {str(row.get("phase")) for row in rows}
    _check(checks, "command-results-complete", required <= phases, "missing lifecycle result" if not required <= phases else "lifecycle results present", "blocked" if not required <= phases else "fail")
    for row in rows:
        phase = str(row.get("phase"))
        ok = row.get("returncode") == 0 and not row.get("timed_out") and not row.get("stdout_truncated") and not row.get("stderr_truncated")
        _check(checks, f"command-result:{phase}", ok, "completed without truncation" if ok else "command failed, timed out, or exceeded output bound", "fail")


def _verify_snapshots(
    gate_root: Path,
    checks: list[dict[str, Any]],
    kind: str,
) -> tuple[list[Mapping[str, Any]], set[int]]:
    schema = PROCESS_SNAPSHOT_SCHEMA if kind == "processes" else MODULE_SNAPSHOT_SCHEMA
    all_rows: list[Mapping[str, Any]] = []
    pids: set[int] = set()
    for phase in ("before", "during", "after"):
        value, _ = _load_required(gate_root, f"raw/{kind}-{phase}.json", checks)
        if not isinstance(value, Mapping):
            continue
        schema_ok = value.get("schema") == schema
        api_ok = value.get("api") == "CreateToolhelp32Snapshot"
        coverage_ok = value.get("coverage") is True
        _check(checks, f"{kind}-schema:{phase}", schema_ok, "schema ok" if schema_ok else "schema mismatch")
        _check(checks, f"{kind}-api:{phase}", api_ok, "native API recorded" if api_ok else "native API missing", "blocked" if not api_ok else "fail")
        rows = value.get(kind)
        if not isinstance(rows, list):
            _check(checks, f"{kind}-rows:{phase}", False, "row list missing", "blocked")
            continue
        for row in rows:
            if isinstance(row, Mapping):
                all_rows.append(row)
                try:
                    pids.add(int(row.get("pid", row.get("process_id"))))
                except (TypeError, ValueError):
                    pass
    return all_rows, pids


def _verify_sockets(gate_root: Path, checks: list[dict[str, Any]]) -> tuple[list[Mapping[str, Any]], set[int]]:
    rows: list[Mapping[str, Any]] = []
    pids: set[int] = set()
    allowed_remote = {None, "", "0.0.0.0", "::", "0:0:0:0:0:0:0:0", "127.0.0.1", "::1", "::ffff:127.0.0.1"}
    for phase in ("before", "during", "after"):
        value, _ = _load_required(gate_root, f"raw/sockets-{phase}.json", checks)
        if not isinstance(value, Mapping):
            continue
        schema_ok = value.get("schema") == SOCKET_SNAPSHOT_SCHEMA
        api_ok = value.get("api") == "GetExtendedTcpTable"
        coverage_ok = value.get("coverage") is True
        _check(checks, f"sockets-schema:{phase}", schema_ok, "schema ok" if schema_ok else "schema mismatch")
        _check(checks, f"sockets-api:{phase}", api_ok, "native API recorded" if api_ok else "native API missing", "blocked" if not api_ok else "fail")
        _check(checks, f"sockets-coverage:{phase}", coverage_ok, "coverage ok" if coverage_ok else "native observation incomplete", "blocked" if not coverage_ok else "fail")
        socket_rows = value.get("sockets")
        if not isinstance(socket_rows, list):
            _check(checks, f"sockets-rows:{phase}", False, "socket row list missing", "blocked")
            continue
        for row in socket_rows:
            if not isinstance(row, Mapping):
                continue
            rows.append(row)
            try:
                pids.add(int(row.get("pid")))
            except (TypeError, ValueError):
                pass
            local = row.get("local_address")
            remote = row.get("remote_address")
            # Provider sockets must bind and connect on loopback.  A wildcard
            # listener is not loopback-only and is therefore a failure.
            if local not in {None, "", "127.0.0.1", "::1", "::ffff:127.0.0.1"} or remote not in allowed_remote:
                _check(checks, f"socket-loopback:{phase}", False, f"non-loopback endpoint {local!r}->{remote!r}")
    return rows, pids


def _verify_path_allowlist(value: Any, source_root: Path | None, checks: list[dict[str, Any]]) -> set[str]:
    if not isinstance(value, Mapping):
        _check(checks, "path-allowlist-object", False, "path allowlist is not an object", "blocked")
        return set()
    body = value.get("value", value)
    paths: list[str] = []
    if isinstance(body, Mapping):
        candidate = body.get("paths", body.get("allowlist", body.get("canonical_paths")))
        if isinstance(candidate, list):
            paths.extend(item for item in candidate if isinstance(item, str))
        paths.extend(row.get("path") for row in _find_path_rows(body) if isinstance(row.get("path"), str))
    elif isinstance(body, list):
        paths.extend(item for item in body if isinstance(item, str))
    if not paths or source_root is None:
        _check(checks, "path-allowlist-coverage", False, "canonical path allowlist is unavailable", "blocked")
        return set()
    canonical = {_canonical_path(path, source_root) for path in paths}
    _check(checks, "path-allowlist-coverage", bool(canonical), f"{len(canonical)} canonical paths")
    _check(checks, "path-allowlist-canonical", body.get("canonical", True) is not False if isinstance(body, Mapping) else True, "canonical paths required")
    return canonical


def _verify_trace(gate_root: Path, root: Mapping[str, Any], checks: list[dict[str, Any]], blobs: Mapping[str, bytes]) -> Mapping[str, Any] | None:
    value, _ = _load_required(gate_root, "raw/trace.json", checks)
    if not isinstance(value, Mapping):
        return None
    schema_ok = value.get("schema") == TRACE_SCHEMA
    coverage_ok = value.get("coverage") is True
    _check(checks, "trace-schema", schema_ok, "schema ok" if schema_ok else "schema mismatch")
    _check(checks, "trace-coverage", coverage_ok, "ETW coverage declared" if coverage_ok else "ETW coverage missing", "blocked" if not coverage_ok else "fail")
    etl_relative = value.get("trace_path", "raw/cassi-qi-flow.etl")
    try:
        etl_path = _safe_artifact_path(gate_root, etl_relative)
        etl = etl_path.read_bytes()
        _check(checks, "trace-etl-present", bool(etl) and len(etl) <= MAX_TRACE_BYTES, "bounded ETL present" if etl and len(etl) <= MAX_TRACE_BYTES else "ETL missing/empty/oversize", "blocked")
    except (OSError, VerificationError) as exc:
        _check(checks, "trace-etl-present", False, str(exc), "blocked")
    profile_path = gate_root / "raw" / "cassi-qi-flow-etw.wprp"
    expected_profile = root.get("identities", {}).get("etw_profile_sha256") if isinstance(root.get("identities"), Mapping) else None
    try:
        observed_profile = _sha256(profile_path.read_bytes())
        _check(checks, "trace-profile-identity", observed_profile == expected_profile and value.get("profile_sha256") == expected_profile, "WPR profile identity ok" if observed_profile == expected_profile and value.get("profile_sha256") == expected_profile else "WPR profile mutated")
    except OSError as exc:
        _check(checks, "trace-profile-identity", False, str(exc), "blocked")
    start = value.get("start")
    stop = value.get("stop")
    _check(checks, "trace-start-command", isinstance(start, Mapping) and start.get("returncode") == 0, "trace started" if isinstance(start, Mapping) and start.get("returncode") == 0 else "trace start failed", "blocked")
    _check(checks, "trace-stop-command", isinstance(stop, Mapping) and stop.get("returncode") == 0, "trace stopped" if isinstance(stop, Mapping) and stop.get("returncode") == 0 else "trace stop failed", "blocked")
    return value


def _verify_file_reads(
    value: Any,
    source_root: Path | None,
    allowlist: set[str],
    checks: list[dict[str, Any]],
) -> dict[str, int]:
    if not isinstance(value, Mapping):
        _check(checks, "file-reads-object", False, "file-read evidence is not an object", "blocked")
        return {}
    schema_ok = value.get("schema") == FILE_READ_SCHEMA
    coverage_ok = value.get("coverage") is True
    _check(checks, "file-reads-schema", schema_ok, "schema ok" if schema_ok else "schema mismatch")
    _check(checks, "file-reads-coverage", coverage_ok, "file-read coverage ok" if coverage_ok else "file-read coverage missing", "blocked" if not coverage_ok else "fail")
    grouped = value.get("grouped_bytes", {})
    if not isinstance(grouped, Mapping):
        rows = value.get("rows")
        grouped = {}
        if isinstance(rows, list) and source_root is not None:
            for row in rows:
                if isinstance(row, Mapping) and isinstance(row.get("path"), str):
                    try:
                        amount = int(row.get("bytes"))
                    except (TypeError, ValueError):
                        amount = -1
                    if amount >= 0:
                        path = _canonical_path(row["path"], source_root)
                        grouped[path] = grouped.get(path, 0) + amount
    result: dict[str, int] = {}
    for path, amount in grouped.items() if isinstance(grouped, Mapping) else ():
        if not isinstance(path, str) or isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            _check(checks, "file-read-row", False, "invalid file-read row")
            continue
        canonical = _canonical_path(path, source_root) if source_root is not None else path
        result[canonical] = result.get(canonical, 0) + amount
        if allowlist and canonical not in allowlist:
            _check(checks, "file-read-allowlist", False, f"read path outside canonical allowlist: {canonical}")
        if _forbidden_path(path):
            _check(checks, "file-read-forbidden", False, f"forbidden model/Qwen path read: {path}")
    return result


def _verify_sys_modules(value: Any, checks: list[dict[str, Any]]) -> None:
    if not isinstance(value, Mapping):
        _check(checks, "sys-modules-object", False, "sys.modules manifest is not an object", "blocked")
        return
    schema_ok = value.get("schema") == SYS_MODULES_SCHEMA
    coverage_ok = value.get("coverage") is True
    _check(checks, "sys-modules-schema", schema_ok, "schema ok" if schema_ok else "schema mismatch")
    _check(checks, "sys-modules-coverage", coverage_ok, "manifest supplied" if coverage_ok else "provider sys.modules manifest missing", "blocked" if not coverage_ok else "fail")
    modules = value.get("modules", value.get("names", value.get("rows", [])))
    if isinstance(modules, list):
        for item in modules:
            module = item.get("name") if isinstance(item, Mapping) else item
            if _forbidden_basename(module):
                _check(checks, "sys-modules-forbidden", False, f"forbidden module observed: {module}")


def _verify_memory(value: Any, checks: list[dict[str, Any]]) -> int:
    if not isinstance(value, Mapping):
        _check(checks, "job-memory-object", False, "job memory record is not an object", "blocked")
        return 0
    schema_ok = value.get("schema") == JOB_MEMORY_SCHEMA
    api_ok = value.get("api") == "QueryInformationJobObject"
    coverage_ok = value.get("coverage") is True
    _check(checks, "job-memory-schema", schema_ok, "schema ok" if schema_ok else "schema mismatch")
    _check(checks, "job-memory-api", api_ok, "native API recorded" if api_ok else "native API missing", "blocked")
    _check(checks, "job-memory-coverage", coverage_ok, "memory coverage ok" if coverage_ok else "Job memory observation incomplete", "blocked" if not coverage_ok else "fail")
    peaks: list[int] = []
    samples = value.get("samples")
    if isinstance(samples, list):
        for row in samples:
            if isinstance(row, Mapping):
                for key in ("peak_job_memory_bytes", "peak_process_memory_bytes", "private_bytes", "working_set_bytes"):
                    amount = row.get(key)
                    if isinstance(amount, int) and not isinstance(amount, bool) and amount >= 0:
                        peaks.append(amount)
    _check(checks, "job-memory-samples", bool(peaks), "memory samples present" if peaks else "memory samples missing", "blocked" if not peaks else "fail")
    return max(peaks, default=0)


def _verify_allocation(value: Any, checks: list[dict[str, Any]]) -> tuple[int, int, int] | None:
    if not isinstance(value, Mapping):
        _check(checks, "allocation-object", False, "allocation formula is not an object", "blocked")
        return None
    coverage = value.get("coverage") is True
    _check(checks, "allocation-coverage", coverage, "allocation formula supplied" if coverage else "independently recomputable allocation formula missing", "blocked" if not coverage else "fail")
    if not coverage:
        return None
    field = value.get("field_bytes", value.get("field_allocation_bytes"))
    scratch = value.get("scratch_bytes", value.get("scratch_allocation_bytes"))
    total = value.get("total_bytes", value.get("expected_total_bytes"))
    if not all(isinstance(item, int) and not isinstance(item, bool) and item >= 0 for item in (field, scratch, total)):
        _check(checks, "allocation-values", False, "field/scratch/total byte values missing", "blocked")
        return None
    ok = int(field) + int(scratch) == int(total)
    _check(checks, "allocation-recompute", ok, "field + scratch = total" if ok else "allocation formula mismatch")
    return int(field), int(scratch), int(total)


def _derive_counters(
    process_rows: Iterable[Mapping[str, Any]],
    module_rows: Iterable[Mapping[str, Any]],
    socket_rows: Iterable[Mapping[str, Any]],
    file_reads: Mapping[str, int],
    provider_pids: set[int],
    checks: list[dict[str, Any]],
) -> dict[str, int]:
    counters = {
        "baseline_artifacts_loaded": 0,
        "gguf_files_opened": 0,
        "llama_contexts": 0,
        "llama_modules_loaded": 0,
        "qwen_kv_bytes": 0,
        "qwen_lm_head_rows": 0,
        "qwen_modules_loaded": 0,
        "qwen_processes": 0,
        "qwen_requests": 0,
        "qwen_sampler_decisions": 0,
        "qwen_weight_bytes_touched": 0,
        "teacher_imports": 0,
    }

    for row in process_rows:
        try:
            owned = int(row.get("pid")) in provider_pids
        except (TypeError, ValueError):
            owned = not provider_pids
        if not owned:
            continue
        names = (row.get("exe_name"), row.get("image_path"), _command_first_basename(row.get("command_line")))
        if any(_forbidden_basename(name) for name in names):
            counters["qwen_processes"] += 1

    for row in module_rows:
        try:
            owned = int(row.get("pid")) in provider_pids
        except (TypeError, ValueError):
            owned = not provider_pids
        if not owned:
            continue
        names = (row.get("module_name"), row.get("module_path"))
        text = " ".join(str(name or "").casefold() for name in names)
        if any(term in text for term in ("qwen", "gguf")):
            counters["qwen_modules_loaded"] += 1
        if "llama" in text:
            counters["llama_modules_loaded"] += 1
        if "context" in text:
            counters["llama_contexts"] += 1

    for row in socket_rows:
        try:
            owned = int(row.get("pid")) in provider_pids
        except (TypeError, ValueError):
            owned = False
        if not owned:
            continue
        for key in ("request_count", "requests", "qwen_requests"):
            amount = row.get(key)
            if isinstance(amount, int) and not isinstance(amount, bool) and amount >= 0:
                counters["qwen_requests"] += amount
                break
        if any(_forbidden_path(row.get(key)) for key in ("process", "image_path", "module", "provider", "command_line")):
            counters["qwen_requests"] += 1

    for path, amount in file_reads.items():
        normalized = str(path).replace("\\", "/").casefold()
        components = {part for part in normalized.split("/") if part}
        name = components and normalized.rsplit("/", 1)[-1] or normalized
        model_path = _forbidden_path(path) or any(part == "model" or part == "weights" or part.startswith("model.") or part.startswith("weight.") for part in components)
        if model_path:
            counters["qwen_weight_bytes_touched"] += amount
        if name.endswith(".gguf") or ".gguf." in name:
            counters["gguf_files_opened"] += 1
        if any(part in {"kv", "kv-cache", "kv_cache", "native-kv", "native_kv"} for part in components):
            counters["qwen_kv_bytes"] += amount
        if any(part == "lm_head" or part.startswith("lm_head.") for part in components):
            counters["qwen_lm_head_rows"] += 1
        if any(part == "teacher" or part.startswith("teacher.") for part in components):
            counters["teacher_imports"] += 1
        if any(part == "baseline" or part.startswith("baseline.") for part in components):
            counters["baseline_artifacts_loaded"] += 1

    for key, amount in counters.items():
        _check(checks, f"counter-zero:{key}", amount == 0, f"derived {key}={amount}")
    return counters


def _verify_runtime_identity(root: Mapping[str, Any], gate_root: Path, checks: list[dict[str, Any]]) -> None:
    identities = root.get("identities")
    if not isinstance(identities, Mapping):
        _check(checks, "identity-object", False, "root identities missing", "blocked")
        return
    required = (
        "profile_sha256",
        "backend_capacity_sha256",
        "checkpoint_sha256",
        "source_identity_sha256",
        "dependency_manifest_sha256",
        "path_allowlist_sha256",
        "runtime_command_sha256",
        "commands_sha256",
        "etw_profile_sha256",
        "toolchain_sha256",
        "allocation_formula_sha256",
        "sys_modules_sha256",
    )
    for key in required:
        _check(checks, f"identity:{key}", _digest(identities.get(key), key) is not None, "digest present" if _digest(identities.get(key), key) is not None else "digest missing/invalid", "blocked")
    for key, relative in (
        ("source_identity_sha256", "raw/source-identity.json"),
        ("dependency_manifest_sha256", "raw/dependency-manifest.json"),
        ("path_allowlist_sha256", "raw/path-allowlist.json"),
        ("runtime_command_sha256", "raw/runtime-command.json"),
        ("etw_profile_sha256", "raw/cassi-qi-flow-etw.wprp"),
        ("toolchain_sha256", "raw/toolchain.json"),
        ("allocation_formula_sha256", "raw/allocation-formula.json"),
        ("commands_sha256", "raw/commands.json"),
        ("sys_modules_sha256", "raw/sys-modules.json"),
    ):
        try:
            observed = _sha256(_safe_artifact_path(gate_root, relative).read_bytes())
            _check(checks, f"identity-file:{key}", observed == identities.get(key), "identity file digest ok" if observed == identities.get(key) else "identity file mutated")
        except (OSError, VerificationError) as exc:
            _check(checks, f"identity-file:{key}", False, str(exc), "blocked")
    checkpoint_path = gate_root / "raw" / "checkpoint-identity.json"
    try:
        checkpoint, _ = _load_json(checkpoint_path)
        ok = isinstance(checkpoint, Mapping) and checkpoint.get("checkpoint_sha256") == identities.get("checkpoint_sha256")
        _check(checks, "checkpoint-identity", ok, "checkpoint identity retained" if ok else "checkpoint identity missing/mutated", "blocked" if not ok else "fail")
    except VerificationError as exc:
        _check(checks, "checkpoint-identity", False, str(exc), "blocked")
    try:
        job_payload = _safe_artifact_path(gate_root, "raw/job-object-identity.json").read_bytes()
        job_value, _ = _load_json(gate_root / "raw" / "job-object-identity.json")
        job_ok = isinstance(job_value, Mapping) and job_value.get("kill_on_job_close") is True and _sha256(job_payload) == root.get("job_object_identity_sha256")
        _check(checks, "job-object-identity", job_ok, "named Job object identity retained" if job_ok else "Job object identity missing/mutated", "blocked" if not job_ok else "fail")
    except (OSError, VerificationError) as exc:
        _check(checks, "job-object-identity", False, str(exc), "blocked")

def _verify_root_contract(root: Mapping[str, Any], checks: list[dict[str, Any]]) -> None:
    for key in ("run_id", "capture_id", "receipt_id"):
        value = root.get(key)
        _check(checks, f"root:{key}", isinstance(value, str) and bool(value) and len(value) <= 128, f"{key} present" if isinstance(value, str) and value else f"{key} missing/invalid", "blocked")
    for key in ("contract_root_sha256", "profile_sha256"):
        ok = _digest(root.get(key), key) is not None
        _check(checks, f"root:{key}", ok, "digest present" if ok else "digest missing/invalid", "blocked")
    semantic = root.get("consumed_semantic_subhashes")
    required_semantic = {"provider_api_sha256", "backend_capacity_sha256", "security_evidence_sha256"}
    semantic_names = {str(row.get("name")) for row in semantic if isinstance(row, Mapping)} if isinstance(semantic, list) else set()
    semantic_ok = isinstance(semantic, list) and semantic_names == required_semantic and all(_digest(row.get("sha256"), str(row.get("name"))) is not None for row in semantic if isinstance(row, Mapping) and row.get("name") in required_semantic)
    _check(checks, "root:semantic-subhashes", semantic_ok, "required semantic identities present" if semantic_ok else "semantic identity set missing/malformed", "blocked")
    lifetime = root.get("lifetime")
    lifetime_ok = isinstance(lifetime, Mapping) and _digest(lifetime.get("start_marker_sha256"), "start_marker_sha256") is not None and _digest(lifetime.get("end_marker_sha256"), "end_marker_sha256") is not None and isinstance(lifetime.get("request_id"), str) and isinstance(lifetime.get("restart_ordinal"), int) and not isinstance(lifetime.get("restart_ordinal"), bool) and lifetime["restart_ordinal"] >= 0
    _check(checks, "root:lifetime", lifetime_ok, "bounded lifetime identity present" if lifetime_ok else "lifetime identity missing/malformed", "blocked")
    refs = ("provider_command_sha256", "etw_trace_manifest_sha256", "sys_modules_manifest_sha256", "file_read_summary_sha256", "field_allocation_formula_sha256", "mutation_control_manifest_sha256", "job_object_identity_sha256")
    for key in refs:
        ok = _digest(root.get(key), key) is not None
        _check(checks, f"root:{key}", ok, "digest present" if ok else "digest missing/invalid", "blocked")
    for key in ("toolhelp_inventory_sha256s", "socket_inventory_sha256s"):
        value = root.get(key)
        ok = isinstance(value, list) and len(value) == 3 and all(_digest(item, key) is not None for item in value)
        _check(checks, f"root:{key}", ok, "three phase manifest identities present" if ok else "phase manifest identities missing/malformed", "blocked")


def _verify_parser_inputs(gate_root: Path, root: Mapping[str, Any], checks: list[dict[str, Any]], source_root: Path | None = None) -> None:
    parser_identity, parser_identity_raw = _load_required(gate_root, "raw/parser-identity.json", checks)
    parser_input, parser_input_raw = _load_required(gate_root, "raw/parser-result-input.json", checks)
    parser = root.get("independent_parser")
    parser_ok = isinstance(parser, Mapping)
    if parser_ok:
        parser_ok = parser.get("parser_identity_sha256") == _sha256(parser_identity_raw or b"") and parser.get("parser_result_sha256") == _sha256(parser_input_raw or b"")
    _check(checks, "parser-input-identities", parser_ok, "independent parser inputs retained" if parser_ok else "parser input identity missing/mutated", "blocked")
    if isinstance(parser_identity, Mapping):
        code_hash = _digest(parser_identity.get("parser_code_sha256"), "parser_code_sha256")
        _check(checks, "parser-code-identity", code_hash is not None, "parser code identity present" if code_hash else "parser code identity missing", "blocked")
        if code_hash:
            parser_path = (source_root or gate_root.parents[2]) / "verify_cassi_qi_process_evidence.py"
            try:
                observed_parser_hash = _sha256(parser_path.read_bytes())
                _check(checks, "parser-code-source", observed_parser_hash == code_hash, "parser source identity ok" if observed_parser_hash == code_hash else "parser source mutated")
            except OSError as exc:
                _check(checks, "parser-code-source", False, str(exc), "blocked")
    if isinstance(parser_input, Mapping):
        _check(checks, "parser-input-capture", parser_input.get("capture_id") == root.get("capture_id"), "parser capture identity ok" if parser_input.get("capture_id") == root.get("capture_id") else "parser capture identity mismatch", "blocked")
        _check(checks, "parser-input-complete", parser_input.get("complete") is False, "pre-verification parser input is incomplete" if parser_input.get("complete") is False else "parser input falsely claims completion", "blocked")
def verify_artifact(run_root: str | Path, *, source_root: str | Path | None = None, write_outputs: bool = False) -> dict[str, Any]:
    run_root_path = Path(run_root).resolve()
    gate_root = run_root_path / "gates" / "g12e-process-evidence"
    checks: list[dict[str, Any]] = []
    root_path = gate_root / "process-evidence.json"
    try:
        root, _ = _load_json(root_path)
    except VerificationError as exc:
        result = {
            "schema": PARSER_SCHEMA,
            "gate": "G12E",
            "status": "BLOCKED",
            "engineering_ready": False,
            "checks": [{"name": "root", "ok": False, "detail": str(exc), "severity": "blocked"}],
            "derived": {},
        }
        result["self_sha256"] = _obj_hash({key: value for key, value in result.items() if key != "self_sha256"}, PARSER_SCHEMA)
        if write_outputs:
            gate_root.mkdir(parents=True, exist_ok=True)
            _write_json(gate_root / "parser-result.json", result)
            status = {"schema": STATUS_SCHEMA, "gate": "G12E", "status": "BLOCKED", "engineering_ready": False, "parser_result_sha256": result["self_sha256"]}
            status["self_sha256"] = _obj_hash({key: value for key, value in status.items() if key != "self_sha256"}, STATUS_SCHEMA)
            _write_json(gate_root / "status.json", status)
        return result
    if not isinstance(root, Mapping):
        raise VerificationError("process-evidence root is not an object")
    _verify_root_contract(root, checks)
    schema_ok = root.get("schema") == PROCESS_EVIDENCE_SCHEMA
    _check(checks, "root-schema", schema_ok, "schema ok" if schema_ok else "schema mismatch")
    root_self_ok = _check_self_hash(root, PROCESS_EVIDENCE_SCHEMA)
    _check(checks, "root-self-hash", root_self_ok, "self hash ok" if root_self_ok else "root self hash mismatch")
    raw_index, blobs = _verify_raw_index(gate_root, root, checks)
    _verify_capture_manifests(gate_root, root, checks)
    source_root_path = Path(source_root).resolve() if source_root is not None else None
    if source_root_path is None and isinstance(root.get("source_root"), str):
        candidate = Path(root["source_root"])
        if candidate.exists():
            source_root_path = candidate.resolve()
    _verify_parser_inputs(gate_root, root, checks, source_root_path)
    _check(checks, "source-root", source_root_path is not None, "source root available" if source_root_path is not None else "source root unavailable", "blocked")
    _verify_runtime_identity(root, gate_root, checks)

    source_value, _ = _load_required(gate_root, "raw/source-identity.json", checks)
    dependency_value, _ = _load_required(gate_root, "raw/dependency-manifest.json", checks)
    allowlist_value, _ = _load_required(gate_root, "raw/path-allowlist-observed.json", checks)
    source_rows, source_paths = _verify_identity_manifest("source", source_value, source_root_path, checks)
    dependency_rows, dependency_paths = _verify_identity_manifest("dependency", dependency_value, source_root_path, checks)
    allowlist = _verify_path_allowlist(allowlist_value, source_root_path, checks)

    commands, _ = _load_required(gate_root, "raw/commands.json", checks)
    _verify_command_files(gate_root, commands, checks)
    command_results, _ = _load_required(gate_root, "raw/command-results.json", checks)
    _verify_command_results(command_results, checks)
    trace = _verify_trace(gate_root, root, checks, blobs)
    process_rows, process_pids = _verify_snapshots(gate_root, checks, "processes")
    module_rows, module_pids = _verify_snapshots(gate_root, checks, "modules")
    socket_rows, socket_pids = _verify_sockets(gate_root, checks)
    file_read_value, _ = _load_required(gate_root, "raw/file-reads.json", checks)
    file_reads = _verify_file_reads(file_read_value, source_root_path, allowlist, checks)
    sys_modules, _ = _load_required(gate_root, "raw/sys-modules.json", checks)
    _verify_sys_modules(sys_modules, checks)
    memory, _ = _load_required(gate_root, "raw/job-memory.json", checks)
    peak_memory = _verify_memory(memory, checks)
    allocation, _ = _load_required(gate_root, "raw/allocation-formula.json", checks)
    allocation_values = _verify_allocation(allocation, checks)

    runtime_pids: set[int] = set()
    instances = root.get("runtime_instances")
    if isinstance(instances, list):
        for row in instances:
            if isinstance(row, Mapping) and row.get("started") is True:
                try:
                    runtime_pids.add(int(row.get("pid")))
                except (TypeError, ValueError):
                    pass
    during_pids = {int(row.get("pid")) for row in process_rows if isinstance(row.get("pid"), int)}
    _check(checks, "provider-process-observed", bool(runtime_pids & during_pids), "provider process observed during request" if runtime_pids & during_pids else "provider process absent from during inventory", "blocked")
    for pid in runtime_pids:
        matching = [row for row in process_rows if row.get("pid") == pid]
        _check(checks, f"process-identity:{pid}", bool(matching) and all(row.get("process_creation_id") for row in matching), "process creation identity present" if matching and all(row.get("process_creation_id") for row in matching) else "process creation identity missing", "blocked")
        _check(checks, f"process-command-line:{pid}", bool(matching) and all(row.get("command_line") for row in matching), "command line present" if matching and all(row.get("command_line") for row in matching) else "command line missing", "blocked")
    provider_pids = runtime_pids or (process_pids & module_pids)
    counters = _derive_counters(process_rows, module_rows, socket_rows, file_reads, provider_pids, checks)

    # Any explicit forbidden evidence is a FAIL; inability to observe it is a
    # BLOCKED check above.  Runtime self-reported zeros never affect counters.
    allocation_upper_bound: int | None = None
    if allocation_values is not None:
        allocation_upper_bound = max(0, peak_memory - allocation_values[2])
    derived = {
        **counters,
        "provider_pids": sorted(provider_pids),
        "observed_process_count": len(process_rows),
        "observed_module_count": len(module_rows),
        "observed_socket_count": len(socket_rows),
        "file_read_path_count": len(file_reads),
        "peak_job_memory_bytes": peak_memory,
        "field_allocation_bytes": allocation_values[0] if allocation_values else None,
        "scratch_allocation_bytes": allocation_values[1] if allocation_values else None,
        "unexplained_native_state_upper_bound_bytes": allocation_upper_bound,
        "source_file_count": len(source_rows),
        "dependency_file_count": len(dependency_rows),
    }
    failed = [row for row in checks if not row.get("ok") and row.get("severity", "fail") == "fail"]
    blocked = [row for row in checks if not row.get("ok") and row.get("severity") == "blocked"]
    status = "FAIL" if failed else "BLOCKED" if blocked else "PASS"
    result = {
        "schema": PARSER_SCHEMA,
        "gate": "G12E",
        "run_id": root.get("run_id"),
        "status": status,
        "engineering_ready": status == "PASS",
        "checks": checks,
        "derived": derived,
        "identities": root.get("identities", {}),
    }
    result["self_sha256"] = _obj_hash({key: value for key, value in result.items() if key != "self_sha256"}, PARSER_SCHEMA)
    if write_outputs:
        parser_payload = _write_json(gate_root / "parser-result.json", result)
        status_obj = {
            "schema": STATUS_SCHEMA,
            "gate": "G12E",
            "run_id": root.get("run_id"),
            "status": status,
            "engineering_ready": status == "PASS",
            "parser_result_sha256": _sha256(parser_payload),
            "failed_check_count": len(failed),
            "blocked_check_count": len(blocked),
        }
        status_obj["self_sha256"] = _obj_hash({key: value for key, value in status_obj.items() if key != "self_sha256"}, STATUS_SCHEMA)
        _write_json(gate_root / "status.json", status_obj)
        updated_root = dict(root)
        updated_root["status"] = status
        updated_root["parser_result_sha256"] = result["self_sha256"]
        updated_root["status_sha256"] = _obj_hash(status_obj, STATUS_SCHEMA)
        updated_root["self_sha256"] = _obj_hash({key: value for key, value in updated_root.items() if key != "self_sha256"}, PROCESS_EVIDENCE_SCHEMA)
        _write_json(root_path, updated_root)
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--source-root", type=Path, default=None)
    parser.add_argument("--write", action="store_true", help="write parser-result.json and status.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = verify_artifact(args.run_root, source_root=args.source_root, write_outputs=args.write or True)
    print(canonical_json_bytes(result).decode("utf-8"))
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}.get(str(result.get("status")), 2)


if __name__ == "__main__":
    raise SystemExit(main())
