from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from cassi_field_qwen_workbench import WorkMemoryRecord

PROGRAM_SCHEMA = "cassi.entity.research-program.v1"
OPERATION_SCHEMA = "cassi.entity.research-operation.v1"
EVENT_SCHEMA = "cassi.entity.research-event.v1"
ARTIFACT_SCHEMA = "cassi.entity.research-artifact.v1"
CAPABILITY_SCHEMA = "cassi.entity.research-capabilities.v1"
PROGRAM_STATUSES = {"active", "paused", "blocked", "completed", "canceled"}
TERMINAL_PROGRAM_STATUSES = {"completed", "canceled"}
SAFE_DEFAULT_TOOLS = (
    "list_files",
    "read_file",
    "search_text",
    "write_artifact",
    "inspect_artifact",
)
ALL_TOOLS = SAFE_DEFAULT_TOOLS + ("fetch_url", "run_existing_python")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
    data = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    temporary.write_text(data, encoding="utf-8")
    os.replace(temporary, path)


def _plain(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _identifier(value: str, *, label: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 160 or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", normalized) is None:
        raise ValueError(f"{label} must be 1-160 characters using letters, digits, dot, underscore, colon, or hyphen")
    return normalized


def _text(value: Any, *, label: str, maximum: int = 100_000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return value.strip()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

def _serialized(method: Any) -> Any:
    @functools.wraps(method)
    def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
        with self._cycle_lock:
            return method(self, *args, **kwargs)

    return wrapped


class BrainClient(Protocol):
    model_id: str
    model_sha256: str

    def complete(
        self,
        *,
        prompt: str,
        max_tokens: int,
        thinking: bool = False,
        response_format: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]: ...


class FieldMemory(Protocol):
    def learn(self, record: WorkMemoryRecord) -> Mapping[str, Any]: ...


class ResearchError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


class ProgramNotFound(ResearchError):
    pass


class ProgramConflict(ResearchError):
    pass


class CapabilityDenied(ResearchError):
    pass


class ResearchBrainUnavailable(ResearchError):
    pass


@dataclass(frozen=True)
class ResearchRuntimeConfig:
    home: Path
    allowed_roots: tuple[Path, ...]
    allowed_network_hosts: tuple[str, ...] = ()
    python_executable: str = sys.executable
    cycle_interval_seconds: float = 1.0
    max_read_bytes: int = 512 * 1024
    max_output_bytes: int = 512 * 1024
    max_process_seconds: int = 900
    default_tools: tuple[str, ...] = SAFE_DEFAULT_TOOLS

    def normalized(self) -> "ResearchRuntimeConfig":
        roots = tuple(dict.fromkeys(path.resolve() for path in self.allowed_roots))
        if not roots:
            raise ValueError("autonomous research requires at least one allowed root")
        tools = tuple(dict.fromkeys(self.default_tools))
        unknown = sorted(set(tools) - set(ALL_TOOLS))
        if unknown:
            raise ValueError(f"unknown default research tools: {', '.join(unknown)}")
        hosts = tuple(dict.fromkeys(host.lower().strip() for host in self.allowed_network_hosts if host.strip()))
        return ResearchRuntimeConfig(
            home=self.home.resolve(),
            allowed_roots=roots,
            allowed_network_hosts=hosts,
            python_executable=self.python_executable,
            cycle_interval_seconds=max(0.05, float(self.cycle_interval_seconds)),
            max_read_bytes=max(1024, int(self.max_read_bytes)),
            max_output_bytes=max(1024, int(self.max_output_bytes)),
            max_process_seconds=max(1, int(self.max_process_seconds)),
            default_tools=tools,
        )


class ResearchStore:
    """Durable operational mirror for field-owned programs and recoverable effects."""

    def __init__(self, home: Path) -> None:
        self.home = home.resolve()
        self.programs_dir = self.home / "programs"
        self.operations_dir = self.home / "operations"
        self.artifacts_dir = self.home / "artifacts" / "sha256"
        self.workspaces_dir = self.home / "workspaces"
        self.events_path = self.home / "events.jsonl"
        self.state_path = self.home / "runtime.json"
        self._lock = threading.RLock()
        for path in (self.programs_dir, self.operations_dir, self.artifacts_dir, self.workspaces_dir):
            path.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            _atomic_json(self.state_path, {"schema": "cassi.entity.research-runtime.v1", "agenda_sequence": 0, "event_sequence": 0})
        events = self.events_after(0)
        state = self._runtime()
        journal_sequence = int(events[-1]["sequence"]) if events else 0
        journal_digest = str(events[-1]["digest"]) if events else ""
        if int(state.get("event_sequence", 0)) > journal_sequence:
            raise ResearchError("research runtime event cursor is ahead of its journal")
        if int(state.get("event_sequence", 0)) != journal_sequence or str(state.get("last_event_digest", "")) != journal_digest:
            state["event_sequence"] = journal_sequence
            state["last_event_digest"] = journal_digest
            _atomic_json(self.state_path, state)

    @staticmethod
    def _file_name(identity: str) -> str:
        return hashlib.sha256(identity.encode("utf-8")).hexdigest() + ".json"

    def _program_path(self, program_id: str) -> Path:
        return self.programs_dir / self._file_name(program_id)

    def _operation_path(self, operation_id: str) -> Path:
        return self.operations_dir / self._file_name(operation_id)

    def _runtime(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ResearchError("research runtime state is unreadable") from exc
        if value.get("schema") != "cassi.entity.research-runtime.v1":
            raise ResearchError("research runtime state has an incompatible schema")
        return value

    def next_agenda_sequence(self) -> int:
        with self._lock:
            state = self._runtime()
            state["agenda_sequence"] = int(state.get("agenda_sequence", 0)) + 1
            _atomic_json(self.state_path, state)
            return int(state["agenda_sequence"])

    def append_event(
        self,
        kind: str,
        program_id: str | None,
        payload: Mapping[str, Any],
        *,
        event_id: str | None = None,
    ) -> Mapping[str, Any]:
        with self._lock:
            state = self._runtime()
            sequence = int(state.get("event_sequence", 0)) + 1
            prior_digest = str(state.get("last_event_digest", ""))
            body = {
                "schema": EVENT_SCHEMA,
                "sequence": sequence,
                "event_id": event_id,
                "kind": kind,
                "program_id": program_id,
                "recorded_at": _utc_now(),
                "payload": _plain(payload),
                "prior_digest": prior_digest,
            }
            event = {**body, "digest": _digest(body)}
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            with self.events_path.open("ab") as stream:
                stream.write(_canonical(event) + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            state["event_sequence"] = sequence
            state["last_event_digest"] = event["digest"]
            _atomic_json(self.state_path, state)
            return event

    def append_event_once(
        self,
        event_id: str,
        kind: str,
        program_id: str | None,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        identity = _identifier(event_id, label="event_id")
        with self._lock:
            existing = next(
                (event for event in self.events_after(0) if event.get("event_id") == identity),
                None,
            )
            if existing is not None:
                if (
                    existing.get("kind") != kind
                    or existing.get("program_id") != program_id
                    or existing.get("payload") != _plain(payload)
                ):
                    raise ProgramConflict("event_id is already bound to different event content")
                return existing
            return self.append_event(
                kind,
                program_id,
                payload,
                event_id=identity,
            )

    def events_after(self, sequence: int, *, program_id: str | None = None) -> list[Mapping[str, Any]]:
        if sequence < 0:
            raise ValueError("event sequence cannot be negative")
        if not self.events_path.exists():
            return []
        raw = self.events_path.read_bytes()
        lines = raw.splitlines()
        events: list[Mapping[str, Any]] = []
        prior_digest = ""
        expected = 1
        for index, line in enumerate(lines):
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                if index == len(lines) - 1 and not raw.endswith(b"\n"):
                    break
                raise ResearchError("research event journal is corrupt")
            body = {key: value for key, value in event.items() if key != "digest"}
            if event.get("sequence") != expected or event.get("prior_digest") != prior_digest or event.get("digest") != _digest(body):
                raise ResearchError("research event journal integrity check failed")
            expected += 1
            prior_digest = str(event["digest"])
            if int(event["sequence"]) > sequence and (program_id is None or event.get("program_id") == program_id):
                events.append(event)
        return events

    def save_operation(self, operation: Mapping[str, Any]) -> Mapping[str, Any]:
        operation_id = _identifier(str(operation.get("operation_id", "")), label="operation_id")
        value = _plain(operation)
        value["schema"] = OPERATION_SCHEMA
        value["updated_at"] = _utc_now()
        _atomic_json(self._operation_path(operation_id), value)
        return value

    def operation(self, operation_id: str) -> Mapping[str, Any] | None:
        path = self._operation_path(operation_id)
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema") != OPERATION_SCHEMA or value.get("operation_id") != operation_id:
            raise ResearchError("research operation identity check failed")
        return value

    def pending_operations(self) -> list[Mapping[str, Any]]:
        values: list[Mapping[str, Any]] = []
        for path in sorted(self.operations_dir.glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("schema") != OPERATION_SCHEMA:
                raise ResearchError(f"incompatible research operation: {path.name}")
            if value.get("status") not in {"committed", "failed", "unknown-effect"}:
                values.append(value)
        return values

    def save_program(self, program: Mapping[str, Any]) -> Mapping[str, Any]:
        value = _plain(program)
        if value.get("schema") != PROGRAM_SCHEMA:
            raise ResearchError("cannot persist an incompatible research program")
        program_id = _identifier(str(value.get("program_id", "")), label="program_id")
        _atomic_json(self._program_path(program_id), value)
        return value

    def program(self, program_id: str) -> Mapping[str, Any]:
        path = self._program_path(_identifier(program_id, label="program_id"))
        if not path.exists():
            raise ProgramNotFound(f"unknown research program: {program_id}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema") != PROGRAM_SCHEMA or value.get("program_id") != program_id:
            raise ResearchError("research program identity check failed")
        return value

    def programs(self) -> list[Mapping[str, Any]]:
        values: list[Mapping[str, Any]] = []
        for path in sorted(self.programs_dir.glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("schema") != PROGRAM_SCHEMA:
                raise ResearchError(f"incompatible research program: {path.name}")
            values.append(value)
        values.sort(key=lambda value: (str(value.get("created_at", "")), str(value.get("program_id", ""))))
        return values

    def workspace(self, program_id: str) -> Path:
        path = self.workspaces_dir / self._file_name(_identifier(program_id, label="program_id")).removesuffix(".json")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def put_artifact(
        self,
        data: bytes,
        *,
        media_type: str,
        label: str,
        program_id: str,
        operation_id: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        digest = hashlib.sha256(data).hexdigest()
        blob = self.artifacts_dir / digest[:2] / digest
        blob.parent.mkdir(parents=True, exist_ok=True)
        if not blob.exists():
            temporary = blob.with_name(blob.name + f".{os.getpid()}.tmp")
            temporary.write_bytes(data)
            try:
                os.replace(temporary, blob)
            finally:
                if temporary.exists():
                    temporary.unlink()
        elif blob.read_bytes() != data:
            raise ResearchError("artifact digest collision")
        return {
            "schema": ARTIFACT_SCHEMA,
            "sha256": digest,
            "size": len(data),
            "media_type": media_type,
            "label": label,
            "program_id": program_id,
            "operation_id": operation_id,
            "metadata": _plain(metadata or {}),
        }

    def artifact_bytes(self, digest: str) -> bytes:
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("artifact digest must be lowercase SHA-256")
        path = self.artifacts_dir / digest[:2] / digest
        if not path.exists():
            raise ProgramNotFound(f"unknown research artifact: {digest}")
        return path.read_bytes()


class ResearchCapabilities:
    """Scoped, auditable source, artifact, network, and existing-script tools."""

    def __init__(self, config: ResearchRuntimeConfig, store: ResearchStore) -> None:
        self.config = config.normalized()
        self.store = store

    def descriptor(self) -> Mapping[str, Any]:
        return {
            "schema": CAPABILITY_SCHEMA,
            "tools": {
                "list_files": {"effect": "read", "arguments": {"root": "path", "pattern": "optional glob", "max_results": "1..2000"}},
                "read_file": {"effect": "read", "arguments": {"path": "path", "start_byte": "optional integer", "max_bytes": "optional integer"}},
                "search_text": {"effect": "read", "arguments": {"root": "path", "pattern": "regular expression", "file_glob": "optional glob"}},
                "write_artifact": {"effect": "program-workspace-write", "arguments": {"path": "relative path", "content": "text", "media_type": "optional"}},
                "inspect_artifact": {"effect": "read", "arguments": {"sha256": "digest", "max_bytes": "optional integer"}},
                "fetch_url": {"effect": "network-read", "configured_hosts": list(self.config.allowed_network_hosts)},
                "run_existing_python": {"effect": "trusted-workspace-process", "arguments": {"script": "existing .py under a program root", "args": "string list", "timeout_seconds": "optional"}},
            },
            "allowed_roots": [str(path) for path in self.config.allowed_roots],
            "python_executable": self.config.python_executable,
            "generated_code_execution": False,
        }

    def _program_roots(self, program: Mapping[str, Any]) -> tuple[Path, ...]:
        roots: list[Path] = []
        for raw in program.get("allowed_roots", []):
            path = Path(str(raw)).resolve()
            if not any(_inside(path, configured) for configured in self.config.allowed_roots):
                raise CapabilityDenied(f"program root is outside runtime scope: {path}")
            roots.append(path)
        if not roots:
            raise CapabilityDenied("research program has no allowed roots")
        return tuple(roots)

    def _resolve_source(self, raw: Any, program: Mapping[str, Any], *, must_exist: bool = True) -> Path:
        text = _text(raw, label="path", maximum=4096)
        roots = self._program_roots(program)
        candidate = Path(text)
        if candidate.is_absolute():
            path = candidate.resolve()
            if not any(_inside(path, root) for root in roots):
                raise CapabilityDenied(f"path is outside program scope: {path}")
        else:
            matches = [(root / candidate).resolve() for root in roots]
            valid = [path for path in matches if _inside(path, roots[matches.index(path)]) and (path.exists() or not must_exist)]
            if not valid:
                raise CapabilityDenied(f"path is unavailable in program scope: {text}")
            if len(valid) > 1:
                existing = [path for path in valid if path.exists()]
                valid = existing or valid
            if len(valid) != 1:
                raise CapabilityDenied(f"relative path is ambiguous across program roots: {text}")
            path = valid[0]
        if must_exist and not path.exists():
            raise CapabilityDenied(f"path does not exist: {path}")
        return path

    def _require_tool(self, name: str, program: Mapping[str, Any]) -> None:
        if name not in ALL_TOOLS:
            raise CapabilityDenied(f"unknown research capability: {name}")
        if name not in program.get("allowed_tools", []):
            raise CapabilityDenied(f"research program does not authorize {name}")

    def execute(
        self,
        name: str,
        arguments: Mapping[str, Any],
        *,
        program: Mapping[str, Any],
        operation_id: str,
    ) -> Mapping[str, Any]:
        self._require_tool(name, program)
        handler = getattr(self, f"_tool_{name}")
        result = handler(arguments, program=program, operation_id=operation_id)
        return {"tool": name, "arguments": _plain(arguments), "result": result}

    def is_replay_safe(self, name: str) -> bool:
        return name != "run_existing_python"

    def _tool_list_files(self, arguments: Mapping[str, Any], *, program: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        root = self._resolve_source(arguments.get("root", "."), program)
        if not root.is_dir():
            raise CapabilityDenied("list_files root must be a directory")
        pattern = str(arguments.get("pattern", "**/*"))
        maximum = max(1, min(int(arguments.get("max_results", 500)), 2000))
        excluded = {".git", ".godot", "node_modules", "__pycache__"}
        values: list[Mapping[str, Any]] = []
        for path in sorted(root.glob(pattern)):
            relative = path.relative_to(root)
            if any(part in excluded for part in relative.parts):
                continue
            values.append({"path": relative.as_posix(), "kind": "directory" if path.is_dir() else "file", "size": path.stat().st_size if path.is_file() else None})
            if len(values) >= maximum:
                break
        data = _canonical(values)
        artifact = self.store.put_artifact(data, media_type="application/json", label="file-list", program_id=str(program["program_id"]), operation_id=operation_id, metadata={"root": str(root), "pattern": pattern})
        return {"root": str(root), "pattern": pattern, "count": len(values), "truncated": len(values) >= maximum, "entries": values[:100], "artifact": artifact}

    def _tool_read_file(self, arguments: Mapping[str, Any], *, program: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        path = self._resolve_source(arguments.get("path"), program)
        if not path.is_file():
            raise CapabilityDenied("read_file path must be a file")
        start = max(0, int(arguments.get("start_byte", 0)))
        maximum = max(1, min(int(arguments.get("max_bytes", self.config.max_read_bytes)), self.config.max_read_bytes))
        with path.open("rb") as stream:
            stream.seek(start)
            data = stream.read(maximum + 1)
        truncated = len(data) > maximum
        data = data[:maximum]
        artifact = self.store.put_artifact(data, media_type="application/octet-stream", label=path.name, program_id=str(program["program_id"]), operation_id=operation_id, metadata={"source_path": str(path), "start_byte": start})
        return {"path": str(path), "start_byte": start, "bytes_read": len(data), "truncated": truncated, "text": data.decode("utf-8", errors="replace"), "artifact": artifact}

    def _tool_search_text(self, arguments: Mapping[str, Any], *, program: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        root = self._resolve_source(arguments.get("root", "."), program)
        if not root.is_dir():
            raise CapabilityDenied("search_text root must be a directory")
        expression = _text(arguments.get("pattern"), label="search pattern", maximum=2048)
        try:
            regex = re.compile(expression)
        except re.error as exc:
            raise CapabilityDenied(f"invalid search regular expression: {exc}") from exc
        file_glob = str(arguments.get("file_glob", "**/*"))
        maximum = max(1, min(int(arguments.get("max_results", 200)), 1000))
        matches: list[Mapping[str, Any]] = []
        scanned = 0
        excluded = {".git", ".godot", "node_modules", "__pycache__"}
        for path in sorted(root.glob(file_glob)):
            if not path.is_file() or any(part in excluded for part in path.relative_to(root).parts):
                continue
            if path.stat().st_size > 4 * self.config.max_read_bytes:
                continue
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    matches.append({"path": path.relative_to(root).as_posix(), "line": line_number, "text": line[:1000]})
                    if len(matches) >= maximum:
                        break
            if len(matches) >= maximum:
                break
        artifact = self.store.put_artifact(_canonical(matches), media_type="application/json", label="text-search", program_id=str(program["program_id"]), operation_id=operation_id, metadata={"root": str(root), "pattern": expression, "file_glob": file_glob})
        return {"root": str(root), "pattern": expression, "scanned_files": scanned, "match_count": len(matches), "truncated": len(matches) >= maximum, "matches": matches[:100], "artifact": artifact}

    def _tool_write_artifact(self, arguments: Mapping[str, Any], *, program: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        relative = Path(_text(arguments.get("path"), label="artifact path", maximum=4096))
        if relative.is_absolute() or ".." in relative.parts:
            raise CapabilityDenied("write_artifact path must stay inside the program workspace")
        content = arguments.get("content")
        if not isinstance(content, str) or not content or len(content) > 2_000_000:
            raise CapabilityDenied("artifact content must be 1-2000000 characters")
        data = content.encode("utf-8")
        workspace = self.store.workspace(str(program["program_id"]))
        target = (workspace / relative).resolve()
        if not _inside(target, workspace):
            raise CapabilityDenied("write_artifact path escapes the program workspace")
        previous_sha256 = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + f".{os.getpid()}.tmp")
        temporary.write_bytes(data)
        os.replace(temporary, target)
        media_type = str(arguments.get("media_type", "text/plain; charset=utf-8"))
        artifact = self.store.put_artifact(data, media_type=media_type, label=relative.as_posix(), program_id=str(program["program_id"]), operation_id=operation_id, metadata={"workspace_path": str(target), "previous_sha256": previous_sha256})
        return {"workspace_path": str(target), "previous_sha256": previous_sha256, "artifact": artifact}

    def _tool_inspect_artifact(self, arguments: Mapping[str, Any], *, program: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        digest = str(arguments.get("sha256", ""))
        data = self.store.artifact_bytes(digest)
        maximum = max(1, min(int(arguments.get("max_bytes", self.config.max_read_bytes)), self.config.max_read_bytes))
        selected = data[:maximum]
        return {"sha256": digest, "size": len(data), "bytes_read": len(selected), "truncated": len(data) > maximum, "text": selected.decode("utf-8", errors="replace")}

    def _tool_fetch_url(self, arguments: Mapping[str, Any], *, program: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        url = _text(arguments.get("url"), label="url", maximum=8192)
        parsed = urllib.parse.urlparse(url)
        host = (parsed.hostname or "").lower()
        program_hosts = {str(value).lower() for value in program.get("network_hosts", [])}
        configured = set(self.config.allowed_network_hosts)
        if parsed.scheme != "https" or not host or host not in configured or host not in program_hosts:
            raise CapabilityDenied("fetch_url requires HTTPS and a host allowed by both runtime and program scope")
        maximum = max(1, min(int(arguments.get("max_bytes", self.config.max_read_bytes)), self.config.max_read_bytes))
        request = urllib.request.Request(url, headers={"User-Agent": "CassiAutonomousResearcher/1"})
        opener = urllib.request.build_opener(_NoRedirect())
        try:
            response_context = opener.open(request, timeout=30)
        except urllib.error.HTTPError as exc:
            if 300 <= exc.code < 400:
                raise CapabilityDenied("fetch_url redirects are refused; admit the destination host and request its exact URL") from exc
            raise
        with response_context as response:
            data = response.read(maximum + 1)
            media_type = response.headers.get_content_type()
            status = int(response.status)
        truncated = len(data) > maximum
        data = data[:maximum]
        artifact = self.store.put_artifact(data, media_type=media_type, label=url, program_id=str(program["program_id"]), operation_id=operation_id, metadata={"url": url, "status": status})
        return {"url": url, "status": status, "media_type": media_type, "bytes_read": len(data), "truncated": truncated, "text": data.decode("utf-8", errors="replace"), "artifact": artifact}

    def _tool_run_existing_python(self, arguments: Mapping[str, Any], *, program: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        script = self._resolve_source(arguments.get("script"), program)
        if not script.is_file() or script.suffix.lower() != ".py":
            raise CapabilityDenied("run_existing_python requires an existing .py source file")
        if _inside(script, self.store.home):
            raise CapabilityDenied("generated program-workspace code cannot execute without real containment")
        raw_args = arguments.get("args", [])
        if not isinstance(raw_args, list) or any(not isinstance(value, str) or len(value) > 4096 for value in raw_args) or len(raw_args) > 64:
            raise CapabilityDenied("run_existing_python args must be at most 64 bounded strings")
        timeout = max(1, min(int(arguments.get("timeout_seconds", self.config.max_process_seconds)), self.config.max_process_seconds))
        cwd = script.parent
        if arguments.get("cwd") is not None:
            candidate = self._resolve_source(arguments.get("cwd"), program)
            if not candidate.is_dir():
                raise CapabilityDenied("run_existing_python cwd must be a directory")
            cwd = candidate
        env_keys = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "CUDA_VISIBLE_DEVICES", "PYTORCH_HIP_ALLOC_CONF", "HSA_ENABLE_SDMA")
        environment = {key: os.environ[key] for key in env_keys if key in os.environ}
        command = [self.config.python_executable, str(script), *raw_args]
        started = time.monotonic()
        try:
            completed = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, timeout=timeout, check=False)
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or b"") if isinstance(exc.stdout, bytes) else str(exc.stdout or "").encode()
            stderr = (exc.stderr or b"") if isinstance(exc.stderr, bytes) else str(exc.stderr or "").encode()
            completed = subprocess.CompletedProcess(command, 124, stdout=stdout, stderr=stderr)
            timed_out = True
        elapsed = time.monotonic() - started
        stdout = bytes(completed.stdout)[: self.config.max_output_bytes]
        stderr = bytes(completed.stderr)[: self.config.max_output_bytes]
        transcript = _canonical({"command": command, "cwd": str(cwd), "returncode": completed.returncode, "timed_out": timed_out, "stdout": stdout.decode("utf-8", errors="replace"), "stderr": stderr.decode("utf-8", errors="replace")})
        artifact = self.store.put_artifact(transcript, media_type="application/json", label=f"process:{script.name}", program_id=str(program["program_id"]), operation_id=operation_id, metadata={"script": str(script), "returncode": completed.returncode, "timed_out": timed_out})
        return {"script": str(script), "cwd": str(cwd), "returncode": int(completed.returncode), "timed_out": timed_out, "elapsed_seconds": elapsed, "stdout": stdout.decode("utf-8", errors="replace"), "stderr": stderr.decode("utf-8", errors="replace"), "artifact": artifact}


class AutonomousResearchDirector:
    """Resident field agenda → Qwen plan → scoped effect → field admission loop."""

    def __init__(
        self,
        config: ResearchRuntimeConfig,
        *,
        brain: BrainClient,
        memory: FieldMemory,
    ) -> None:
        self.config = config.normalized()
        self.brain = brain
        self.memory = memory
        self.store = ResearchStore(self.config.home)
        self.capabilities = ResearchCapabilities(self.config, self.store)
        self._cycle_lock = threading.RLock()
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._recovered = False

    def capability_map(self) -> Mapping[str, Any]:
        return self.capabilities.descriptor()

    def _validate_roots(self, raw_roots: Sequence[Any] | None) -> list[str]:
        if raw_roots is None:
            return [str(path) for path in self.config.allowed_roots]
        roots: list[str] = []
        for raw in raw_roots:
            candidate = Path(_text(raw, label="allowed root", maximum=4096))
            if not candidate.is_absolute():
                candidate = self.config.allowed_roots[0] / candidate
            path = candidate.resolve()
            if not any(_inside(path, configured) for configured in self.config.allowed_roots):
                raise CapabilityDenied(f"program root is outside runtime scope: {path}")
            if not path.exists() or not path.is_dir():
                raise CapabilityDenied(f"program root is not an existing directory: {path}")
            roots.append(str(path))
        if not roots:
            raise CapabilityDenied("research program must have at least one root")
        return list(dict.fromkeys(roots))

    def _validate_tools(self, raw_tools: Sequence[Any] | None) -> list[str]:
        values = list(self.config.default_tools if raw_tools is None else raw_tools)
        if any(not isinstance(value, str) for value in values):
            raise CapabilityDenied("allowed_tools must contain strings")
        unknown = sorted(set(values) - set(ALL_TOOLS))
        if unknown:
            raise CapabilityDenied(f"unknown research tools: {', '.join(unknown)}")
        if "fetch_url" in values and not self.config.allowed_network_hosts:
            raise CapabilityDenied("fetch_url is unavailable because the runtime has no network host allowlist")
        return list(dict.fromkeys(values))

    def _validate_hosts(self, raw_hosts: Sequence[Any] | None) -> list[str]:
        values = [] if raw_hosts is None else [str(value).lower().strip() for value in raw_hosts]
        unknown = sorted(set(values) - set(self.config.allowed_network_hosts))
        if unknown:
            raise CapabilityDenied(f"program network hosts exceed runtime scope: {', '.join(unknown)}")
        return list(dict.fromkeys(value for value in values if value))

    @_serialized
    def create_program(
        self,
        *,
        request_id: str,
        program_id: str,
        project_id: str,
        title: str,
        mission: str,
        initial_question: str,
        observed_at: str,
        priority: float = 0.5,
        cycle_limit: int | None = None,
        allowed_roots: Sequence[Any] | None = None,
        allowed_tools: Sequence[Any] | None = None,
        network_hosts: Sequence[Any] | None = None,
    ) -> Mapping[str, Any]:
        request_id = _identifier(request_id, label="request_id")
        program_id = _identifier(program_id, label="program_id")
        project_id = _identifier(project_id, label="project_id")
        request_sha256 = _digest(
            {
                "kind": "create-program",
                "program_id": program_id,
                "project_id": project_id,
                "title": title,
                "mission": mission,
                "initial_question": initial_question,
                "observed_at": observed_at,
                "priority": priority,
                "cycle_limit": cycle_limit,
                "allowed_roots": (
                    None
                    if allowed_roots is None
                    else [str(value) for value in allowed_roots]
                ),
                "allowed_tools": (
                    None if allowed_tools is None else list(allowed_tools)
                ),
                "network_hosts": (
                    None if network_hosts is None else list(network_hosts)
                ),
            }
        )
        existing_operation = self.store.operation(request_id)
        if existing_operation is not None:
            if (
                existing_operation.get("kind") != "create-program"
                or existing_operation.get("program_id") != program_id
                or existing_operation.get("request_sha256") != request_sha256
            ):
                raise ProgramConflict(
                    "request_id is already bound to different research content"
                )
            if existing_operation.get("status") == "admitting":
                return self._admit_candidate(existing_operation)
            if existing_operation.get("status") == "committed":
                return self.store.program(program_id)
            raise ProgramConflict(
                f"create-program request is {existing_operation.get('status')}"
            )
        try:
            existing = self.store.program(program_id)
        except ProgramNotFound:
            existing = None
        if existing is not None:
            raise ProgramConflict(f"research program already exists: {program_id}")
        if (
            isinstance(priority, bool)
            or not 0.0 <= float(priority) <= 1.0
        ):
            raise ValueError("priority must be between 0 and 1")
        if (
            cycle_limit is not None
            and (
                isinstance(cycle_limit, bool)
                or int(cycle_limit) < 1
            )
        ):
            raise ValueError("cycle_limit must be a positive integer or null")
        now = _text(observed_at, label="observed_at", maximum=128)
        question = _text(initial_question, label="initial_question")
        program = {
            "schema": PROGRAM_SCHEMA,
            "program_id": program_id,
            "project_id": project_id,
            "title": _text(title, label="title", maximum=1000),
            "mission": _text(mission, label="mission"),
            "status": "active",
            "priority": float(priority),
            "generation": 0,
            "created_at": now,
            "updated_at": now,
            "allowed_roots": self._validate_roots(allowed_roots),
            "allowed_tools": self._validate_tools(allowed_tools),
            "network_hosts": self._validate_hosts(network_hosts),
            "cycle_limit": int(cycle_limit) if cycle_limit is not None else None,
            "cycles_completed": 0,
            "frontier": [
                {
                    "question_id": "q-000001",
                    "question": question,
                    "state": "active",
                    "priority": 1.0,
                }
            ],
            "current_question_id": "q-000001",
            "claims": [],
            "methods": [],
            "messages": [],
            "recent_operations": [],
            "report": "",
            "last_error": None,
            "field_source_revision_id": None,
            "field_state_sha256": None,
        }
        operation = {
            "schema": OPERATION_SCHEMA,
            "operation_id": request_id,
            "request_sha256": request_sha256,
            "program_id": program_id,
            "kind": "create-program",
            "status": "admitting",
            "candidate_program": program,
            "created_at": now,
            "completion_event": {
                "event_id": f"{request_id}:program-created",
                "kind": "program-created",
                "payload": {
                    "request_id": request_id,
                    "generation": program["generation"],
                    "mission": program["mission"],
                },
            },
        }
        self.store.save_operation(operation)
        committed = self._admit_candidate(operation)
        self._notify()
        return committed

    def programs(self) -> list[Mapping[str, Any]]:
        return self.store.programs()

    def program(self, program_id: str) -> Mapping[str, Any]:
        return self.store.program(program_id)

    def events_after(
        self,
        sequence: int,
        *,
        program_id: str | None = None,
    ) -> list[Mapping[str, Any]]:
        return self.store.events_after(sequence, program_id=program_id)

    def wait_events(
        self,
        sequence: int,
        *,
        program_id: str | None = None,
        timeout: float = 30.0,
    ) -> list[Mapping[str, Any]]:
        deadline = time.monotonic() + max(0.0, min(timeout, 60.0))
        while True:
            events = self.events_after(sequence, program_id=program_id)
            if events:
                return events
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return []
            with self._condition:
                self._condition.wait(timeout=remaining)

    def _notify(self) -> None:
        with self._condition:
            self._condition.notify_all()

    def _program_record(
        self,
        program: Mapping[str, Any],
    ) -> WorkMemoryRecord:
        return WorkMemoryRecord(
            source_id=f"entity:research-program:{program['program_id']}",
            payload={
                "kind": "research-program",
                "program": _plain(program),
            },
            context={
                "adapter": "cassi-field-brain-entity",
                "kind": "research-program",
                "program_id": program["program_id"],
                "project_id": program["project_id"],
            },
            observed_timestamp=str(program["updated_at"]),
            labels=(
                "field-brain",
                "autonomous-research",
                str(program["program_id"]),
            ),
        )

    def _register_obligation(
        self,
        program: Mapping[str, Any],
    ) -> None:
        semantic = getattr(self.memory, "semantic", None)
        if semantic is None:
            return
        status = "active" if program["status"] == "active" else "resolved"
        frontier = next(
            (
                row
                for row in program.get("frontier", [])
                if row.get("question_id") == program.get("current_question_id")
            ),
            None,
        )
        request = {
            "operation": "register",
            "operation_id": (
                f"entity:research-program:{program['program_id']}:"
                f"obligation:{int(program['generation']):08d}"
            ),
            "record_id": (
                f"entity:research-program-obligation:{program['program_id']}"
            ),
            "kind": "Obligation",
            "payload": {
                "purpose": "autonomous-research-program",
                "state": "pending" if status == "active" else "resolved",
                "priority": float(program["priority"]),
                "program_id": program["program_id"],
                "mission": program["mission"],
                "question": (
                    frontier.get("question")
                    if isinstance(frontier, Mapping)
                    else None
                ),
                "generation": int(program["generation"]),
            },
            "status": status,
            "epistemic_kind": "asserted",
        }
        semantic(
            request,
            operation_label=str(request["operation_id"]),
        )

    def _admit_candidate(
        self,
        operation: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        candidate = _plain(operation["candidate_program"])
        receipt = self.memory.learn(self._program_record(candidate))
        candidate["field_source_revision_id"] = receipt.get(
            "source_revision_id"
        )
        candidate["field_state_sha256"] = receipt.get(
            "field_state_sha256",
            receipt.get("state_sha256"),
        )
        self._register_obligation(candidate)
        self.store.save_program(candidate)
        delivery = None
        completion_event = operation.get("completion_event")
        if isinstance(completion_event, Mapping):
            delivery = self.store.append_event_once(
                str(completion_event["event_id"]),
                str(completion_event["kind"]),
                str(candidate["program_id"]),
                completion_event.get("payload", {}),
            )
        self.store.save_operation(
            {
                **operation,
                "status": "committed",
                "candidate_program": candidate,
                "field_receipt": _plain(receipt),
                "delivery_event": (
                    _plain(delivery)
                    if delivery is not None
                    else None
                ),
            }
        )
        return candidate

    @_serialized
    def control_program(
        self,
        *,
        request_id: str,
        program_id: str,
        action: str,
        observed_at: str,
        message: str | None = None,
    ) -> Mapping[str, Any]:
        request_id = _identifier(request_id, label="request_id")
        program_id = _identifier(program_id, label="program_id")
        action = action.strip().lower()
        if action not in {
            "pause",
            "resume",
            "cancel",
            "complete",
            "wake",
        }:
            raise ValueError(
                "research program action must be pause, resume, cancel, "
                "complete, or wake"
            )
        request_sha256 = _digest(
            {
                "kind": f"control:{action}",
                "program_id": program_id,
                "observed_at": observed_at,
                "message": message,
            }
        )
        prior = self.store.operation(request_id)
        if prior is not None:
            if (
                prior.get("program_id") != program_id
                or prior.get("kind") != f"control:{action}"
                or prior.get("request_sha256") != request_sha256
            ):
                raise ProgramConflict(
                    "request_id is already bound to different research content"
                )
            if prior.get("status") == "admitting":
                return self._admit_candidate(prior)
            if prior.get("status") == "delivering":
                event = prior["completion_event"]
                delivery = self.store.append_event_once(
                    str(event["event_id"]),
                    str(event["kind"]),
                    program_id,
                    event.get("payload", {}),
                )
                self.store.save_operation(
                    {
                        **prior,
                        "status": "committed",
                        "delivery_event": delivery,
                    }
                )
                return self.store.program(program_id)
            if prior.get("status") == "committed":
                return self.store.program(program_id)
            raise ProgramConflict(
                f"control request is {prior.get('status')}"
            )
        program = _plain(self.store.program(program_id))
        if action == "wake":
            completion_event = {
                "event_id": f"{request_id}:program-woken",
                "kind": "program-woken",
                "payload": {"request_id": request_id},
            }
            operation = {
                "operation_id": request_id,
                "request_sha256": request_sha256,
                "program_id": program_id,
                "kind": "control:wake",
                "status": "delivering",
                "completion_event": completion_event,
                "created_at": observed_at,
            }
            self.store.save_operation(operation)
            delivery = self.store.append_event_once(
                str(completion_event["event_id"]),
                str(completion_event["kind"]),
                program_id,
                completion_event["payload"],
            )
            self.store.save_operation(
                {
                    **operation,
                    "status": "committed",
                    "delivery_event": delivery,
                }
            )
            self._notify()
            return program
        if (
            program["status"] in TERMINAL_PROGRAM_STATUSES
            and action not in {"complete", "cancel"}
        ):
            raise ProgramConflict(
                "terminal research programs cannot resume"
            )
        target = {
            "pause": "paused",
            "resume": "active",
            "cancel": "canceled",
            "complete": "completed",
        }[action]
        program["status"] = target
        program["generation"] = int(program["generation"]) + 1
        program["updated_at"] = _text(
            observed_at,
            label="observed_at",
            maximum=128,
        )
        if message:
            program["messages"] = [
                *program.get("messages", []),
                {
                    "kind": "control",
                    "content": _text(message, label="message"),
                    "observed_at": observed_at,
                },
            ][-50:]
        operation = {
            "operation_id": request_id,
            "request_sha256": request_sha256,
            "program_id": program_id,
            "kind": f"control:{action}",
            "status": "admitting",
            "candidate_program": program,
            "created_at": observed_at,
            "completion_event": {
                "event_id": f"{request_id}:program-{target}",
                "kind": f"program-{target}",
                "payload": {
                    "request_id": request_id,
                    "generation": program["generation"],
                },
            },
        }
        self.store.save_operation(operation)
        committed = self._admit_candidate(operation)
        self._notify()
        return committed

    @_serialized
    def guide_program(
        self,
        *,
        request_id: str,
        program_id: str,
        content: str,
        observed_at: str,
    ) -> Mapping[str, Any]:
        request_id = _identifier(request_id, label="request_id")
        program_id = _identifier(program_id, label="program_id")
        request_sha256 = _digest(
            {
                "kind": "guidance",
                "program_id": program_id,
                "content": content,
                "observed_at": observed_at,
            }
        )
        prior = self.store.operation(request_id)
        if prior is not None:
            if (
                prior.get("program_id") != program_id
                or prior.get("kind") != "guidance"
                or prior.get("request_sha256") != request_sha256
            ):
                raise ProgramConflict(
                    "request_id is already bound to different research content"
                )
            if prior.get("status") == "admitting":
                return self._admit_candidate(prior)
            if prior.get("status") == "committed":
                return self.store.program(program_id)
            raise ProgramConflict(
                f"guidance request is {prior.get('status')}"
            )
        program = _plain(self.store.program(program_id))
        program["messages"] = [
            *program.get("messages", []),
            {
                "kind": "guidance",
                "content": _text(content, label="content"),
                "observed_at": observed_at,
            },
        ][-50:]
        program["generation"] = int(program["generation"]) + 1
        program["updated_at"] = _text(
            observed_at,
            label="observed_at",
            maximum=128,
        )
        operation = {
            "operation_id": request_id,
            "request_sha256": request_sha256,
            "program_id": program_id,
            "kind": "guidance",
            "status": "admitting",
            "candidate_program": program,
            "created_at": observed_at,
            "completion_event": {
                "event_id": f"{request_id}:program-guidance",
                "kind": "program-guidance",
                "payload": {
                    "request_id": request_id,
                    "generation": program["generation"],
                    "content": content,
                },
            },
        }
        self.store.save_operation(operation)
        committed = self._admit_candidate(operation)
        self._notify()
        return committed

    def _field_select(
        self,
        active: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any] | None:
        if not active:
            return None
        semantic = getattr(self.memory, "semantic", None)
        if semantic is None:
            return min(
                active,
                key=lambda row: (
                    int(row.get("cycles_completed", 0)),
                    str(row["updated_at"]),
                    str(row["program_id"]),
                ),
            )
        sequence = self.store.next_agenda_sequence()
        response = semantic(
            {
                "operation": "autonomous-agenda",
                "operation_id": (
                    f"entity:research-agenda:{sequence:016d}"
                ),
                "goal": {
                    "kind": "resident-research",
                    "objective": (
                        "advance the most valuable unresolved autonomous "
                        "research program"
                    ),
                },
                "obligation_prefix": (
                    "entity:research-program-obligation:"
                ),
                "max_items": max(1, len(active)),
            },
            operation_label=f"entity:research-agenda:{sequence:016d}",
        )
        result = response.get("result", {})
        selected = (
            result.get("selected", {})
            if isinstance(result, Mapping)
            else {}
        )
        obligation = (
            selected.get("obligation", {})
            if isinstance(selected, Mapping)
            else {}
        )
        record_id = (
            obligation.get("id")
            if isinstance(obligation, Mapping)
            else None
        )
        prefix = "entity:research-program-obligation:"
        if isinstance(record_id, str) and record_id.startswith(prefix):
            selected_program_id = record_id[len(prefix):]
            return next(
                (
                    row
                    for row in active
                    if row["program_id"] == selected_program_id
                ),
                None,
            )
        self.store.append_event(
            "field-agenda-no-selection",
            None,
            {
                "agenda_sequence": sequence,
                "result": _plain(result),
            },
        )
        return None

    def _brain_json(self, *, prompt: str, schema_name: str, schema: Mapping[str, Any], max_tokens: int) -> Mapping[str, Any]:
        try:
            response = self.brain.complete(
                prompt=prompt,
                max_tokens=max_tokens,
                thinking=True,
                response_format={"type": "json_schema", "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
            )
        except Exception as exc:
            raise ResearchBrainUnavailable(str(exc)) from exc
        content = response.get("content")
        if not isinstance(content, str):
            raise ResearchBrainUnavailable("research brain returned no textual content")
        try:
            value = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ResearchBrainUnavailable("research brain returned invalid JSON") from exc
        if not isinstance(value, Mapping):
            raise ResearchBrainUnavailable("research brain returned a non-object")
        return value

    @staticmethod
    def _active_question(program: Mapping[str, Any]) -> str:
        current = program.get("current_question_id")
        for row in program.get("frontier", []):
            if row.get("question_id") == current:
                return str(row.get("question", ""))
        return str(program.get("mission", ""))

    def _plan(self, program: Mapping[str, Any]) -> Mapping[str, Any]:
        allowed_tools = list(program.get("allowed_tools", []))
        actions = [*allowed_tools, "reason", "complete", "wait"]
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "minLength": 1, "maxLength": 512},
                "action": {"type": "string", "enum": actions},
                "arguments": {"type": "object"},
                "expected_information": {"type": "string", "minLength": 1, "maxLength": 512},
            },
            "required": ["summary", "action", "arguments", "expected_information"],
            "additionalProperties": False,
        }
        compact = {
            "program_id": program["program_id"],
            "mission": program["mission"],
            "current_question": self._active_question(program),
            "claims": program.get("claims", [])[-20:],
            "methods": program.get("methods", [])[-10:],
            "guidance": program.get("messages", [])[-10:],
            "recent_operations": program.get("recent_operations", [])[-8:],
            "allowed_roots": program.get("allowed_roots", []),
            "allowed_tools": allowed_tools,
            "network_hosts": program.get("network_hosts", []),
        }
        prompt = (
            "AUTONOMOUS RESEARCH ACTION\n"
            "You are the active reasoning brain of one continuing Cassi field-owned researcher. "
            "Choose exactly one concrete action that advances the current question. Keep the summary and expected information concise. Use source or execution tools when evidence is missing; reason only when the available evidence is sufficient. "
            "Never invent a path, artifact, source result, or measurement. Tool arguments must match the capability map.\n\n"
            f"PROGRAM\n{json.dumps(compact, ensure_ascii=False)}\n\n"
            f"CAPABILITIES\n{json.dumps(self.capability_map(), ensure_ascii=False)}"
        )
        return self._brain_json(prompt=prompt, schema_name="cassi_research_action", schema=schema, max_tokens=1800)

    def _synthesize(self, program: Mapping[str, Any], plan: Mapping[str, Any], result: Mapping[str, Any]) -> Mapping[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                "finding": {"type": "string", "minLength": 1, "maxLength": 1024},
                "support_status": {"type": "string", "enum": ["observed", "derived", "hypothesis", "no-result", "contradicted"]},
                "uncertainty": {"type": "string", "minLength": 1, "maxLength": 512},
                "method": {"type": "string", "minLength": 1, "maxLength": 512},
                "next_question": {"type": "string", "minLength": 1, "maxLength": 512},
                "program_status": {"type": "string", "enum": ["active", "blocked", "completed"]},
                "report": {"type": "string", "maxLength": 2048},
            },
            "required": ["finding", "support_status", "uncertainty", "method", "next_question", "program_status", "report"],
            "additionalProperties": False,
        }
        result_text = json.dumps(result, ensure_ascii=False)
        if len(result_text) > 120_000:
            result_text = result_text[:120_000] + "\n[truncated from prompt; full result is retained as an artifact]"
        prompt = (
            "AUTONOMOUS RESEARCH SYNTHESIS\n"
            "Interpret one completed research action for the continuing Cassi program. Distinguish observation, derivation, hypothesis, contradiction, and no-result. "
            "Keep each field concise; cite source paths or locations once rather than reproducing metadata inventories. Do not claim more than the action result supports. Choose the next question that most directly advances the mission. Mark completed only when the mission is actually answered; blocked only when no authorized next action exists.\n\n"
            f"MISSION\n{program['mission']}\n\nCURRENT QUESTION\n{self._active_question(program)}\n\n"
            f"ACTION\n{json.dumps(plan, ensure_ascii=False)}\n\nRESULT\n{result_text}"
        )
        return self._brain_json(prompt=prompt, schema_name="cassi_research_synthesis", schema=schema, max_tokens=4096)

    def _operation_id(self, program: Mapping[str, Any]) -> str:
        return f"entity:research-cycle:{program['program_id']}:{int(program['generation']) + 1:08d}"

    def _execute_planned(self, operation: Mapping[str, Any]) -> Mapping[str, Any]:
        program = self.store.program(str(operation["program_id"]))
        plan = operation["plan"]
        action = str(plan["action"])
        if action == "reason":
            result = {"kind": "reasoning", "content": plan.get("summary", ""), "expected_information": plan.get("expected_information", "")}
        elif action == "complete":
            result = {"kind": "completion-proposal", "content": plan.get("summary", "")}
        elif action == "wait":
            result = {"kind": "wait", "content": plan.get("summary", "")}
        else:
            arguments = plan.get("arguments", {})
            if not isinstance(arguments, Mapping):
                result = {
                    "kind": "capability-refusal",
                    "error": "research action arguments must be an object",
                }
            else:
                try:
                    result = self.capabilities.execute(
                        action,
                        arguments,
                        program=program,
                        operation_id=str(operation["operation_id"]),
                    )
                except (CapabilityDenied, ValueError, OSError, UnicodeError) as exc:
                    result = {
                        "kind": "capability-refusal",
                        "capability": action,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
        executed = {
            **operation,
            "status": "executed",
            "result": _plain(result),
        }
        self.store.save_operation(executed)
        self.store.append_event_once(
            f"{operation['operation_id']}:operation-executed",
            "operation-executed",
            str(program["program_id"]),
            {
                "operation_id": operation["operation_id"],
                "action": action,
                "result": result,
            },
        )
        return executed

    def _complete_executed(self, operation: Mapping[str, Any]) -> Mapping[str, Any]:
        program = _plain(self.store.program(str(operation["program_id"])))
        self.store.append_event_once(
            f"{operation['operation_id']}:operation-executed",
            "operation-executed",
            str(program["program_id"]),
            {
                "operation_id": operation["operation_id"],
                "action": str(operation["plan"]["action"]),
                "result": operation["result"],
            },
        )
        synthesis = self._synthesize(program, operation["plan"], operation["result"])
        operation_id = str(operation["operation_id"])
        now = _utc_now()
        next_generation = int(program["generation"]) + 1
        finding = _text(synthesis.get("finding"), label="finding")
        uncertainty = _text(synthesis.get("uncertainty"), label="uncertainty")
        method = _text(synthesis.get("method"), label="method")
        next_question = _text(synthesis.get("next_question"), label="next_question")
        status = str(synthesis.get("program_status"))
        if status not in {"active", "blocked", "completed"}:
            raise ResearchBrainUnavailable("research synthesis returned an invalid status")
        action = str(operation["plan"]["action"])
        if action == "wait" and status == "active":
            status = "blocked"
        if action == "complete" and status == "active":
            status = "completed"
        current_id = str(program.get("current_question_id"))
        frontier = []
        for row in program.get("frontier", []):
            value = dict(row)
            if value.get("question_id") == current_id:
                value["state"] = "answered" if status == "completed" else "advanced"
            frontier.append(value)
        question_id = f"q-{next_generation + 1:06d}"
        if status != "completed":
            frontier.append({"question_id": question_id, "question": next_question, "state": "active", "priority": 1.0})
            current_id = question_id
        claim = {
            "claim_id": f"claim-{next_generation:06d}",
            "finding": finding,
            "support_status": str(synthesis["support_status"]),
            "uncertainty": uncertainty,
            "operation_id": operation_id,
            "action": action,
            "artifact_sha256": self._result_artifact_digest(operation["result"]),
        }
        program.update(
            {
                "status": status,
                "generation": next_generation,
                "updated_at": now,
                "cycles_completed": int(program.get("cycles_completed", 0)) + 1,
                "frontier": frontier[-100:],
                "current_question_id": current_id,
                "claims": [*program.get("claims", []), claim][-200:],
                "methods": [*program.get("methods", []), {"generation": next_generation, "method": method, "operation_id": operation_id}][-100:],
                "recent_operations": [*program.get("recent_operations", []), {"operation_id": operation_id, "action": action, "finding": finding, "support_status": synthesis["support_status"]}][-30:],
                "report": str(synthesis.get("report", "")),
                "last_error": None,
            }
        )
        cycle_limit = program.get("cycle_limit")
        if cycle_limit is not None and int(program["cycles_completed"]) >= int(cycle_limit) and program["status"] == "active":
            program["status"] = "paused"
            program["last_error"] = "cycle-limit-reached"
        completion_event = {
            "event_id": f"{operation_id}:program-advanced",
            "kind": "program-advanced",
            "payload": {
                "operation_id": operation_id,
                "generation": program["generation"],
                "status": program["status"],
                "finding": finding,
                "next_question": next_question,
            },
        }
        admitting = {
            **operation,
            "status": "admitting",
            "synthesis": _plain(synthesis),
            "candidate_program": program,
            "completion_event": completion_event,
        }
        self.store.save_operation(admitting)
        return self._admit_candidate(admitting)

    @staticmethod
    def _result_artifact_digest(result: Mapping[str, Any]) -> str | None:
        nested = result.get("result") if isinstance(result.get("result"), Mapping) else result
        artifact = nested.get("artifact") if isinstance(nested, Mapping) else None
        return str(artifact.get("sha256")) if isinstance(artifact, Mapping) and artifact.get("sha256") else None

    def recover(self) -> None:
        with self._cycle_lock:
            if self._recovered:
                return
            for operation in self.store.pending_operations():
                status = operation.get("status")
                operation_id = str(operation["operation_id"])
                program_id = str(operation["program_id"])
                if status == "admitting":
                    self._admit_candidate(operation)
                elif status == "delivering":
                    event = operation.get("completion_event")
                    if not isinstance(event, Mapping):
                        raise ResearchError(
                            "delivering operation has no completion event"
                        )
                    delivery = self.store.append_event_once(
                        str(event["event_id"]),
                        str(event["kind"]),
                        program_id,
                        event.get("payload", {}),
                    )
                    self.store.save_operation(
                        {
                            **operation,
                            "status": "committed",
                            "delivery_event": delivery,
                        }
                    )
                elif status == "executed":
                    self._complete_executed(operation)
                elif status == "planned":
                    action = str(operation.get("plan", {}).get("action", ""))
                    if self.capabilities.is_replay_safe(action):
                        self._complete_executed(
                            self._execute_planned(operation)
                        )
                    else:
                        unknown = {
                            **operation,
                            "status": "unknown-effect",
                            "error": (
                                "process outcome was not durably acknowledged "
                                "before restart"
                            ),
                        }
                        self.store.save_operation(unknown)
                        program = _plain(self.store.program(program_id))
                        program["status"] = "blocked"
                        program["generation"] = int(program["generation"]) + 1
                        program["updated_at"] = _utc_now()
                        program["last_error"] = "unknown-process-effect"
                        admitting = {
                            "operation_id": f"{operation_id}:recovery-block",
                            "program_id": program["program_id"],
                            "kind": "recovery-block",
                            "status": "admitting",
                            "candidate_program": program,
                            "created_at": _utc_now(),
                            "completion_event": {
                                "event_id": (
                                    f"{operation_id}:operation-unknown-effect"
                                ),
                                "kind": "operation-unknown-effect",
                                "payload": {
                                    "operation_id": operation_id,
                                },
                            },
                        }
                        self.store.save_operation(admitting)
                        self._admit_candidate(admitting)
                self.store.append_event_once(
                    f"{operation_id}:operation-recovered:{status}",
                    "operation-recovered",
                    program_id,
                    {
                        "operation_id": operation_id,
                        "from_status": status,
                    },
                )
            self._recovered = True

    def run_one(self, *, program_id: str | None = None) -> Mapping[str, Any] | None:
        with self._cycle_lock:
            self.recover()
            active = [row for row in self.store.programs() if row.get("status") == "active"]
            if program_id is not None:
                active = [row for row in active if row.get("program_id") == program_id]
                if not active:
                    program = self.store.program(program_id)
                    if program.get("status") != "active":
                        raise ProgramConflict(f"research program is {program.get('status')}")
            selected = active[0] if program_id is not None and active else self._field_select(active)
            if selected is None:
                return None
            operation_id = self._operation_id(selected)
            existing = self.store.operation(operation_id)
            if existing is not None:
                if existing.get("status") == "committed":
                    return self.store.program(str(selected["program_id"]))
                if existing.get("status") == "executed":
                    return self._complete_executed(existing)
                if existing.get("status") == "planned":
                    return self._complete_executed(self._execute_planned(existing))
                if existing.get("status") == "admitting":
                    return self._admit_candidate(existing)
                raise ProgramConflict(f"research operation is not replayable: {existing.get('status')}")
            plan = self._plan(selected)
            action = str(plan.get("action", ""))
            if action not in {*selected.get("allowed_tools", []), "reason", "complete", "wait"}:
                raise CapabilityDenied(f"research brain selected unauthorized action: {action}")
            operation = {
                "schema": OPERATION_SCHEMA,
                "operation_id": operation_id,
                "program_id": selected["program_id"],
                "kind": "research-cycle",
                "status": "planned",
                "plan": _plain(plan),
                "created_at": _utc_now(),
                "program_generation": selected["generation"],
            }
            self.store.save_operation(operation)
            self.store.append_event_once(
                f"{operation_id}:operation-planned",
                "operation-planned",
                str(selected["program_id"]),
                {
                    "operation_id": operation_id,
                    "action": action,
                    "summary": plan.get("summary"),
                },
            )
            try:
                return self._complete_executed(self._execute_planned(operation))
            except Exception as exc:
                current = self.store.operation(operation_id) or operation
                error = f"{type(exc).__name__}: {exc}"
                current_status = str(current.get("status"))
                action = str(current.get("plan", {}).get("action", ""))
                if current_status == "planned" and not self.capabilities.is_replay_safe(action):
                    deferred = {**current, "status": "unknown-effect", "last_error": error}
                    self.store.save_operation(deferred)
                    program = _plain(self.store.program(str(selected["program_id"])))
                    program["status"] = "blocked"
                    program["generation"] = int(program["generation"]) + 1
                    program["updated_at"] = _utc_now()
                    program["last_error"] = "unknown-process-effect"
                    blocking = {
                        "operation_id": f"{operation_id}:unknown-effect",
                        "program_id": program["program_id"],
                        "kind": "unknown-effect-block",
                        "status": "admitting",
                        "candidate_program": program,
                        "created_at": _utc_now(),
                    }
                    self.store.save_operation(blocking)
                    self._admit_candidate(blocking)
                    event_kind = "operation-unknown-effect"
                else:
                    deferred = {**current, "status": current_status, "last_error": error}
                    self.store.save_operation(deferred)
                    event_kind = "operation-deferred"
                self.store.append_event(event_kind, str(selected["program_id"]), {"operation_id": operation_id, "error": error})
                raise
            finally:
                self._notify()

    def start(self) -> None:
        with self._cycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._resident_loop, name="cassi-autonomous-researcher", daemon=True)
            self._thread.start()
            self.store.append_event("director-started", None, {"cycle_interval_seconds": self.config.cycle_interval_seconds})
            self._notify()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        self._notify()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        if thread is not None and thread.is_alive():
            raise ResearchError("autonomous research director did not stop")
        self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _resident_loop(self) -> None:
        try:
            self.recover()
        except Exception as exc:
            self.store.append_event("director-recovery-failed", None, {"error": f"{type(exc).__name__}: {exc}"})
        while not self._stop.is_set():
            try:
                advanced = self.run_one()
                if advanced is None:
                    self._stop.wait(self.config.cycle_interval_seconds)
            except Exception as exc:
                self.store.append_event("director-cycle-failed", None, {"error": f"{type(exc).__name__}: {exc}"})
                self._stop.wait(self.config.cycle_interval_seconds)

    def status(self) -> Mapping[str, Any]:
        programs = self.store.programs()
        counts = {status: sum(1 for row in programs if row.get("status") == status) for status in sorted(PROGRAM_STATUSES)}
        return {
            "schema": "cassi.entity.research-director-state.v1",
            "running": self.running,
            "program_count": len(programs),
            "status_counts": counts,
            "latest_event_sequence": int(self.store._runtime().get("event_sequence", 0)),
            "capabilities": self.capability_map(),
        }
