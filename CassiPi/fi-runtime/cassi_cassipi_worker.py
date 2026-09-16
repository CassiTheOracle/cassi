from __future__ import annotations

import argparse
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import signal
import sys
import threading
import time
from typing import Any, Mapping, Sequence
import uuid

_RUNTIME_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_RUNTIME_ROOT))
try:
    from cassi_cassipi_v2 import (
        CanonicalOwnerAdapter,
        OwnerAdapterError,
        PROTOCOL_ID,
    )
    from cassi_cassipi_import import CassiPiLegacyImporter, ImportError as CassiPiImportError
    from cassi_field_owner import CapacityLimits, FieldIntelligenceError, FieldIntelligenceOwner
    from cassi_resonant_view import content_type, html, snapshot
except ModuleNotFoundError as exc:
    print(
        json.dumps(
            {
                "error": {
                    "code": "DEPENDENCY_MISSING",
                    "dependency": exc.name,
                    "message": "required canonical runtime dependency is unavailable",
                },
                "schema": "cassifi.cassipi-owner-error.v1",
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        file=sys.stderr,
        flush=True,
    )
    raise SystemExit(2) from None


REQUEST_SCHEMA = "cassifi.cassipi-owner-request.v1"
RESPONSE_SCHEMA = "cassifi.cassipi-owner-response.v1"
DESCRIPTOR_SCHEMA = "cassifi.cassipi-owner-descriptor.v1"
READY_SCHEMA = "cassifi.cassipi-owner-ready.v1"
ERROR_SCHEMA = "cassifi.cassipi-owner-error.v1"
ENDPOINT_PATH = "/v1/owner"
VIEW_PATH = "/view"
SNAPSHOT_PATH = "/v1/view/snapshot"
DESCRIPTOR_NAME = "runtime.json"
LOCK_NAME = "owner.lock"
MAX_REQUEST_BYTES = 1 << 20
_SCOPE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")


class OwnerWorkerError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 500,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = dict(details or {})


def _canonical_json(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise OwnerWorkerError("INTERNAL_ERROR", "response is not canonical JSON") from exc


def _pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in rows:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_json(payload: bytes) -> Mapping[str, Any]:
    try:
        value = json.loads(payload, object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise OwnerWorkerError(
            "INVALID_REQUEST", f"request is not canonical JSON: {exc}", status=400
        ) from exc
    if not isinstance(value, dict):
        raise OwnerWorkerError("INVALID_REQUEST", "request must be an object", status=400)
    return value


def _scope(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SCOPE_RE.fullmatch(value) is None:
        raise OwnerWorkerError(
            "INVALID_REQUEST", f"{label} must be a bounded canonical identifier", status=400
        )
    return value


def _exact_keys(value: Mapping[str, Any], required: set[str], optional: set[str] = set()) -> None:
    keys = set(value)
    missing = required - keys
    unknown = keys - required - optional
    if missing or unknown:
        raise OwnerWorkerError(
            "INVALID_REQUEST",
            f"request fields mismatch: missing={sorted(missing)!r}, unknown={sorted(unknown)!r}",
            status=400,
        )


def _atomic_private_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = -1
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _prepare_data_home(value: Path) -> Path:
    if value.exists() and value.is_symlink():
        raise OwnerWorkerError(
            "DATA_HOME_PERMISSIONS", "data home must not be a symbolic link"
        )
    created = not value.exists()
    try:
        value.mkdir(parents=True, mode=0o700, exist_ok=True)
        home = value.resolve(strict=True)
    except OSError as exc:
        raise OwnerWorkerError(
            "DATA_HOME_PERMISSIONS", f"cannot create or resolve data home: {exc}"
        ) from exc
    if not home.is_dir():
        raise OwnerWorkerError("DATA_HOME_PERMISSIONS", "data home is not a directory")
    if created and os.name != "nt":
        os.chmod(home, 0o700)
    if os.name != "nt" and home.stat().st_mode & 0o077:
        raise OwnerWorkerError(
            "DATA_HOME_PERMISSIONS", "data home must not grant group or other access"
        )
    first = home / f".write-probe-{uuid.uuid4().hex}"
    second = first.with_suffix(".committed")
    try:
        _atomic_private_write(first, b"cassipi-owner-probe\n")
        os.replace(first, second)
        if second.read_bytes() != b"cassipi-owner-probe\n":
            raise OSError("probe bytes changed")
    except OSError as exc:
        raise OwnerWorkerError(
            "DATA_HOME_PERMISSIONS", f"data home is not durably writable: {exc}"
        ) from exc
    finally:
        for path in (first, second):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
    return home


class OwnerProcessLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: Any = None

    def acquire(self) -> None:
        handle: Any = None
        try:
            handle = self.path.open("a+b")
            if handle.seek(0, os.SEEK_END) == 0:
                handle.write(b"\0")
                handle.flush()
                os.fsync(handle.fileno())
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
            raise OwnerWorkerError(
                "OWNER_CONTENTION", "another canonical owner holds this data home", status=409
            ) from exc
        self._handle = handle

    def release(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _stale_descriptor(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {"status": "absent"}
    try:
        payload = path.read_bytes()
        value = json.loads(payload, object_pairs_hook=_pairs)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return {"status": "replaced-invalid"}
    if (
        not isinstance(value, dict)
        or value.get("schema") != DESCRIPTOR_SCHEMA
        or not isinstance(value.get("launch_id"), str)
    ):
        return {"status": "replaced-invalid"}
    return {"status": "replaced-stale", "previous_launch_id": value["launch_id"]}


class OrderedMutationExecutor:
    """One bounded ordered executor for every owner operation."""

    def __init__(self, *, max_backlog: int = 128) -> None:
        from collections import deque

        self._queue = deque()
        self._condition = threading.Condition()
        self._max_backlog = max_backlog
        self._stopping = False
        self._thread = threading.Thread(target=self._run, name="cassipi-owner-mutations", daemon=False)
        self._thread.start()
    def metrics(self) -> Mapping[str, int]:
        """Return bounded queue telemetry without waiting on the worker."""
        with self._condition:
            return {
                "queue_count": len(self._queue),
                "backlog_limit": self._max_backlog,
            }

    def submit(self, operation: Any) -> Any:
        event = threading.Event()
        result: list[Any] = []
        with self._condition:
            if self._stopping or len(self._queue) >= self._max_backlog:
                raise OwnerWorkerError(
                    "OWNER_BACKLOG_LIMIT",
                    "owner mutation backlog is full",
                    status=429,
                    details={"max_backlog": self._max_backlog},
                )
            self._queue.append((operation, event, result))
            self._condition.notify()
        event.wait()
        value = result[0]
        if isinstance(value, BaseException):
            raise value
        return value

    def _run(self) -> None:
        while True:
            with self._condition:
                while not self._queue and not self._stopping:
                    self._condition.wait()
                if not self._queue and self._stopping:
                    return
                operation, event, result = self._queue.popleft()
            try:
                result.append(operation())
            except BaseException as exc:
                result.append(exc)
            finally:
                event.set()

    def close(self) -> None:
        with self._condition:
            self._stopping = True
            self._condition.notify_all()
        self._thread.join(timeout=5.0)
        if self._thread.is_alive():
            raise OwnerWorkerError("OWNER_STOP_TIMEOUT", "owner mutation executor did not stop", status=503)

class OwnerRuntime:
    def __init__(
        self,
        adapter: CanonicalOwnerAdapter,
        *,
        launch_id: str,
        bearer_secret: str,
        recovery: Mapping[str, Any],
        data_home: Path,
        realtime: bool = False,
        keep_alive: bool = False,
    ) -> None:
        self.adapter = adapter
        self.launch_id = launch_id
        self.bearer_secret = bearer_secret
        self.recovery = dict(recovery)
        self._realtime = bool(realtime)
        self._keep_alive = bool(keep_alive)
        self.clients: set[str] = set()
        self._lock = threading.RLock()
        self._server: ThreadingHTTPServer | None = None
        self._stopping = False
        self._closed = False
        self._scope_tokens: dict[str, Mapping[str, str]] = {}
        self._view_tokens: set[str] = set()
        self._scheduler_state = "running"
        self._scheduler_stop = threading.Event()
        self._scheduler_thread: threading.Thread | None = None
        self._shutdown_timer: threading.Timer | None = None
        self._descriptor_path = data_home / DESCRIPTOR_NAME
        self._descriptor: dict[str, Any] | None = None
        self._tick_epoch = 0
        self._scheduler_started = time.monotonic()
        self._scheduler_ticks = 0
        self._scheduler_last_tick: float | None = None
        self._scheduler_skipped = 0
        self._scheduler_backlogged = 0
        self._scheduler_last_failure: Mapping[str, Any] | None = None
        self._capture_path = data_home / "capture-control.json"
        self._capture = self._load_capture()
        if self._capture["paused"]:
            self._scheduler_state = "paused"
        self._forget_tokens: dict[str, Mapping[str, Any]] = {}
        self._importer = CassiPiLegacyImporter(adapter, data_home)
        self._executor = OrderedMutationExecutor()
        if self._realtime:
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                name="cassipi-owner-heartbeat",
                daemon=False,
            )
            self._scheduler_thread.start()

    def _scheduler_loop(self) -> None:
        with self._lock:
            interval_epoch = self._tick_epoch
        while not self._scheduler_stop.wait(0.25):
            with self._lock:
                current_epoch = self._tick_epoch
                if self._scheduler_state != "running" or self._stopping or self._capture["paused"]:
                    self._scheduler_skipped += 1
                    interval_epoch = current_epoch
                    continue
                if current_epoch != interval_epoch:
                    self._scheduler_skipped += 1
                    interval_epoch = current_epoch
                    continue
                tick_epoch = current_epoch
            queue_count = self._executor.metrics()["queue_count"]
            if queue_count:
                with self._lock:
                    self._scheduler_backlogged += queue_count
            try:
                self._executor.submit(
                    lambda epoch=tick_epoch: self._scheduled_advance(epoch)
                )
            except (OwnerWorkerError, OwnerAdapterError) as exc:
                with self._lock:
                    if exc.code == "OWNER_BACKLOG_LIMIT":
                        self._scheduler_backlogged += 1
                    self._scheduler_last_failure = {
                        "code": exc.code,
                        "message": str(exc),
                        "wall_time": time.time(),
                    }
            except Exception as exc:
                with self._lock:
                    self._scheduler_last_failure = {
                        "code": type(exc).__name__,
                        "message": str(exc),
                        "wall_time": time.time(),
                    }
            with self._lock:
                interval_epoch = self._tick_epoch

    def _scheduled_advance(self, tick_epoch: int) -> Mapping[str, Any] | None:
        """Run one timer batch after rechecking its admission fence."""
        with self._lock:
            if (
                self._stopping
                or self._scheduler_state != "running"
                or self._capture["paused"]
                or tick_epoch != self._tick_epoch
            ):
                self._scheduler_skipped += 1
                return None
            operation_id = f"heartbeat:{self.adapter.owner.state.generation + 1}"
        result = self.adapter.advance(
            operation_id=operation_id,
            ticks=1,
            source_enabled=True,
        )
        with self._lock:
            self._tick_epoch += 1
            self._scheduler_ticks += 1
            self._scheduler_last_tick = time.monotonic()
        return result

    def _scheduler_metadata(self) -> Mapping[str, Any]:
        queue = self._executor.metrics()
        elapsed = max(0.0, time.monotonic() - self._scheduler_started)
        achieved = self._scheduler_ticks / elapsed if elapsed > 0.0 else 0.0
        workspace = self.adapter.owner.state.resonant_workspace
        assert workspace is not None
        return {
            "mode": "realtime" if self._realtime else "logical",
            "state": self._scheduler_state,
            "cadence_seconds": 0.25,
            "target_field_time_wall_time_ratio": workspace.profile.time_step / 0.25,
            "maximum_batch_frequency_hz": 4.0,
            "achieved_cadence_hz": achieved,
            "ticks_completed": self._scheduler_ticks,
            "skipped_work": self._scheduler_skipped,
            "backlogged_work": self._scheduler_backlogged,
            "queue_count": queue["queue_count"],
            "backlog_limit": queue["backlog_limit"],
            "last_numerical_failure": self._scheduler_last_failure,
        }

    def bind_descriptor(self, descriptor: Mapping[str, Any]) -> None:
        with self._lock:
            self._descriptor = dict(descriptor)
            self._persist_descriptor_locked()

    def _persist_descriptor_locked(self) -> None:
        if self._descriptor is None:
            return
        descriptor = dict(self._descriptor)
        descriptor.update(
            {
                "state": self._scheduler_state,
                "body_state": self._scheduler_state,
                "detach_policy": (
                    "keep-alive" if self._keep_alive else "shutdown-on-last-detach"
                ),
                "capture": dict(self._capture),
                "scheduler": dict(self._scheduler_metadata()),
                "recovery": dict(self.recovery),
            }
        )
        self._descriptor = descriptor
        _atomic_private_write(self._descriptor_path, _canonical_json(descriptor))

    def view_snapshot(self) -> Mapping[str, Any]:
        """Serialize one coherent owner snapshot through the mutation queue."""
        encoded = self._executor.submit(lambda: _canonical_json(snapshot(self.adapter)))
        return _parse_json(encoded)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._stopping = True
            self._scheduler_state = "stopping"
            if self._shutdown_timer is not None:
                self._shutdown_timer.cancel()
                self._shutdown_timer = None
            self._persist_descriptor_locked()
        self._scheduler_stop.set()
        scheduler_thread = self._scheduler_thread
        if scheduler_thread is not None:
            scheduler_thread.join(timeout=5.0)
        if scheduler_thread is not None and scheduler_thread.is_alive():
            raise OwnerWorkerError("OWNER_STOP_TIMEOUT", "owner heartbeat did not stop", status=503)
        self._executor.close()
        self.adapter.close()

    def _load_capture(self) -> Mapping[str, Any]:
        if not self._capture_path.exists():
            return {
                "schema": "cassipi.capture-control.v1",
                "paused": False,
                "operation_id": None,
                "profile_id": None,
            }
        try:
            encoded = self._capture_path.read_bytes()
            value = json.loads(encoded, object_pairs_hook=_pairs)
            if _canonical_json(value) != encoded:
                raise ValueError("capture control is not canonical JSON")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise OwnerWorkerError(
                "CAPTURE_STATE_CORRUPT",
                "capture control state is unreadable",
                status=503,
            ) from exc
        if (
            not isinstance(value, dict)
            or set(value) != {"schema", "paused", "operation_id", "profile_id"}
            or value["schema"] != "cassipi.capture-control.v1"
            or not isinstance(value["paused"], bool)
            or not isinstance(value["operation_id"], str)
            or _SCOPE_RE.fullmatch(value["operation_id"]) is None
            or not isinstance(value["profile_id"], str)
            or _SCOPE_RE.fullmatch(value["profile_id"]) is None
        ):
            raise OwnerWorkerError(
                "CAPTURE_STATE_CORRUPT",
                "capture control state violates its closed schema",
                status=503,
            )
        return value

    def _capture_request(self, params: Mapping[str, Any], *, mutation: bool) -> Mapping[str, Any]:
        request = self._attached_request(params)
        required = {
            "schema",
            "profile_id",
            "project_id",
            "session_id",
            "branch_id",
            "task_scope",
        }
        if mutation:
            required.update({"operation_id", "paused"})
        _exact_keys(request, required)
        expected_schema = "cassipi.capture-set.v1" if mutation else "cassipi.capture-status.v1"
        if request["schema"] != expected_schema:
            raise OwnerWorkerError(
                "PROTOCOL_MISMATCH",
                "capture control schema is incompatible",
                status=409,
            )
        return request

    def _capture_status(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        request = self._capture_request(params, mutation=False)
        stored_profile = self._capture["profile_id"]
        if stored_profile is not None and stored_profile != request["profile_id"]:
            raise OwnerWorkerError(
                "PROFILE_SCOPE_CONFLICT",
                "capture control belongs to a different owner profile",
                status=403,
            )
        return dict(self._capture)

    def _capture_set(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        request = self._capture_request(params, mutation=True)
        paused = request["paused"]
        if not isinstance(paused, bool):
            raise OwnerWorkerError("INVALID_REQUEST", "paused must be boolean", status=400)
        operation_id = _scope(request["operation_id"], "operation_id")
        if self._capture["operation_id"] == operation_id:
            if self._capture["paused"] != paused:
                raise OwnerWorkerError(
                    "OPERATION_CONFLICT",
                    "capture operation identity was reused with different semantics",
                    status=409,
                )
            return {**dict(self._capture), "replayed": True}
        capture = {
            "schema": "cassipi.capture-control.v1",
            "paused": paused,
            "operation_id": operation_id,
            "profile_id": request["profile_id"],
        }
        _atomic_private_write(self._capture_path, _canonical_json(capture))
        self._capture = capture
        self._scheduler_state = "paused" if paused else "running"
        if not paused and self._shutdown_timer is not None:
            self._shutdown_timer.cancel()
            self._shutdown_timer = None
        self._persist_descriptor_locked()
        return {**capture, "replayed": False}

    def _forget_authorize(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        request = self._attached_request(params)
        _exact_keys(
            request,
            {
                "schema",
                "profile_id",
                "project_id",
                "session_id",
                "branch_id",
                "task_scope",
                "memory_scope",
                "revision_ids",
                "preview_id",
            },
        )
        if request["schema"] != "cassipi.forget-authorize.v1":
            raise OwnerWorkerError(
                "PROTOCOL_MISMATCH",
                "forget authorization schema is incompatible",
                status=409,
            )
        preview = self.adapter.forget_preview(
            {
                "schema": "cassipi.forget-preview.v1",
                "profile_id": request["profile_id"],
                "project_id": request["project_id"],
                "session_id": request["session_id"],
                "branch_id": request["branch_id"],
                "task_scope": request["task_scope"],
                "memory_scope": request["memory_scope"],
                "revision_ids": request["revision_ids"],
            }
        )
        if preview["preview_id"] != request["preview_id"]:
            raise OwnerWorkerError(
                "FORGET_PREVIEW_STALE",
                "forget preview no longer matches the current owner state",
                status=409,
            )
        token = f"forget-{secrets.token_urlsafe(48)}"
        self._forget_tokens[token] = {
            "client_id": _scope(params["client_id"], "client_id"),
            "preview_id": preview["preview_id"],
            "profile_id": request["profile_id"],
            "project_id": request["project_id"],
            "session_id": request["session_id"],
            "branch_id": request["branch_id"],
            "task_scope": request["task_scope"],
            "memory_scope": request["memory_scope"],
            "revision_ids": list(request["revision_ids"]),
        }
        return {
            "schema": "cassipi.forget-authorization.v1",
            "preview_id": preview["preview_id"],
            "authorization_token": token,
            "one_use": True,
        }

    def _forget_execute(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        request = self._attached_request(params)
        _exact_keys(
            request,
            {
                "schema",
                "operation_id",
                "native_identity",
                "producer_id",
                "producer_sequence",
                "predecessor_event_id",
                "profile_id",
                "project_id",
                "session_id",
                "branch_id",
                "task_scope",
                "parent_head_id",
                "memory_scope",
                "revision_ids",
                "preview_id",
                "authorization_token",
            },
        )
        if request["schema"] != "cassipi.forget-execute.v1":
            raise OwnerWorkerError(
                "PROTOCOL_MISMATCH",
                "forget execution schema is incompatible",
                status=409,
            )
        token = _scope(request["authorization_token"], "authorization_token")
        authorization = self._forget_tokens.pop(token, None)
        if authorization is None:
            raise OwnerWorkerError(
                "FORGET_AUTHORIZATION_INVALID",
                "forget authorization is missing, expired, or already consumed",
                status=403,
            )
        expected = {
            "client_id": _scope(params["client_id"], "client_id"),
            "preview_id": request["preview_id"],
            "profile_id": request["profile_id"],
            "project_id": request["project_id"],
            "session_id": request["session_id"],
            "branch_id": request["branch_id"],
            "task_scope": request["task_scope"],
            "memory_scope": request["memory_scope"],
            "revision_ids": (
                list(request["revision_ids"])
                if isinstance(request["revision_ids"], list)
                else request["revision_ids"]
            ),
        }
        if authorization != expected:
            raise OwnerWorkerError(
                "FORGET_AUTHORIZATION_CONFLICT",
                "forget authorization does not match the exact target and scope",
                status=403,
            )
        preview = self.adapter.forget_preview(
            {
                "schema": "cassipi.forget-preview.v1",
                "profile_id": request["profile_id"],
                "project_id": request["project_id"],
                "session_id": request["session_id"],
                "branch_id": request["branch_id"],
                "task_scope": request["task_scope"],
                "memory_scope": request["memory_scope"],
                "revision_ids": request["revision_ids"],
            }
        )
        if preview["preview_id"] != request["preview_id"]:
            raise OwnerWorkerError(
                "FORGET_PREVIEW_STALE",
                "owner state changed after interactive approval",
                status=409,
            )
        result = dict(
            self.adapter.forget_generation(
                {
                    "schema": "cassipi.rebuild.v1",
                    "operation_id": request["operation_id"],
                    "native_identity": request["native_identity"],
                    "producer_id": request["producer_id"],
                    "producer_sequence": request["producer_sequence"],
                    "predecessor_event_id": request["predecessor_event_id"],
                    "profile_id": request["profile_id"],
                    "project_id": request["project_id"],
                    "session_id": request["session_id"],
                    "branch_id": request["branch_id"],
                    "task_scope": request["task_scope"],
                    "parent_head_id": request["parent_head_id"],
                    "allowed_memory_scopes": [request["memory_scope"]],
                    "confirmation_id": request["preview_id"],
                    "revoked_revision_ids": preview["binding"]["revision_ids"],
                    "reason": "direct-user-approved-forget",
                }
            )
        )
        result["schema"] = "cassipi.forget-result.v1"
        result["preview_id"] = request["preview_id"]
        result["authorization_consumed"] = True
        return result

    def bind_server(self, server: ThreadingHTTPServer) -> None:
        self._server = server

    def authorized(self, header: str | None) -> bool:
        expected = f"Bearer {self.bearer_secret}"
        return isinstance(header, str) and hmac.compare_digest(header, expected)

    def authorized_view(self, header: str | None, cookie_header: str | None) -> bool:
        if self.authorized(header):
            return True
        if not isinstance(cookie_header, str):
            return False
        with self._lock:
            view_tokens = set(self._view_tokens)
        for part in cookie_header.split(";"):
            name, separator, value = part.strip().partition("=")
            if separator and name == "cassipi_view" and value in view_tokens:
                return True
        return False

    def _shutdown_callback(self, force: bool) -> None:
        with self._lock:
            self._shutdown_timer = None
            if self._stopping:
                should_stop = True
            elif not force and (self.clients or self._keep_alive):
                return
            else:
                self._stopping = True
                self._scheduler_state = "stopping"
                self._persist_descriptor_locked()
                should_stop = True
            server = self._server
        if should_stop and server is not None:
            server.shutdown()

    def _schedule_shutdown(self, *, force: bool = False) -> None:
        with self._lock:
            if self._server is None:
                return
            if self._shutdown_timer is not None:
                if not force:
                    return
                self._shutdown_timer.cancel()
            delay = 0.01 if force else 0.10
            timer = threading.Timer(delay, self._shutdown_callback, args=(force,))
            timer.daemon = True
            self._shutdown_timer = timer
            timer.start()

    def _attached_client(self, client_id_value: Any) -> str:
        client_id = _scope(client_id_value, "client_id")
        if client_id not in self.clients:
            raise OwnerWorkerError(
                "CLIENT_NOT_ATTACHED",
                "owner operation requires an attached client",
                status=409,
                details={"client_id": client_id},
            )
        return client_id

    def _bind_scope(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        _exact_keys(params, {"client_id", "scope"})
        client_id = self._attached_client(params["client_id"])
        raw_scope = params["scope"]
        if not isinstance(raw_scope, dict):
            raise OwnerWorkerError("INVALID_REQUEST", "host scope must be an object", status=400)
        _exact_keys(
            raw_scope,
            {
                "schema",
                "profile_id",
                "project_id",
                "session_id",
                "branch_id",
                "task_scope",
            },
        )
        if raw_scope["schema"] != "cassipi.authenticated-host-scope.v1":
            raise OwnerWorkerError(
                "PROTOCOL_MISMATCH",
                "authenticated host scope schema is incompatible",
                status=409,
            )
        scope = {
            name: _scope(raw_scope[name], name)
            for name in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")
        }
        owner_profile = self.adapter.owner_status().get("profile_id")
        if owner_profile is not None and owner_profile != scope["profile_id"]:
            raise OwnerWorkerError(
                "PROFILE_SCOPE_CONFLICT",
                "host scope does not match the persistent owner profile",
                status=403,
            )
        token = f"scope-{secrets.token_urlsafe(32)}"
        self._scope_tokens[token] = {"client_id": client_id, **scope}
        return {
            "schema": "cassipi.authenticated-host-scope.v1",
            "scope_token": token,
            "binding_sha256": hashlib.sha256(
                _canonical_json(
                    {
                        "client_id": client_id,
                        **scope,
                        "schema": "cassipi.authenticated-host-scope-binding.v1",
                    }
                )
            ).hexdigest(),
        }

    @staticmethod
    def _request_scope(value: Mapping[str, Any]) -> Mapping[str, Any]:
        nested = value.get("scope")
        return nested if isinstance(nested, Mapping) else value

    def _attached_request(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        _exact_keys(params, {"client_id", "scope_token", "request"})
        client_id = self._attached_client(params["client_id"])
        token = _scope(params["scope_token"], "scope_token")
        bound = self._scope_tokens.get(token)
        if bound is None or bound["client_id"] != client_id:
            raise OwnerWorkerError(
                "HOST_SCOPE_UNAUTHORIZED",
                "owner operation requires a live authenticated host scope",
                status=403,
            )
        value = params["request"]
        if not isinstance(value, dict):
            raise OwnerWorkerError(
                "INVALID_REQUEST", "operation request must be an object", status=400
            )
        requested_scope = self._request_scope(value)
        for name in ("profile_id", "project_id", "session_id", "branch_id", "task_scope"):
            requested = requested_scope.get(name)
            if requested is not None and requested != bound[name]:
                raise OwnerWorkerError(
                    "HOST_SCOPE_CONFLICT",
                    f"request {name} does not match the authenticated host scope",
                    status=403,
                )
        return value

    def dispatch(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        def ordered() -> Mapping[str, Any]:
            workspace = self.adapter.owner.state.resonant_workspace
            if workspace is None:
                raise OwnerWorkerError(
                    "INCOMPATIBLE_STATE",
                    "canonical owner lacks its resonant workspace",
                    status=503,
                )
            before = workspace.field_ticks
            try:
                return self._dispatch_impl(request)
            finally:
                workspace = self.adapter.owner.state.resonant_workspace
                if workspace is None:
                    raise OwnerWorkerError(
                        "INCOMPATIBLE_STATE",
                        "canonical owner lost its resonant workspace",
                        status=503,
                    )
                after = workspace.field_ticks
                if after != before:
                    with self._lock:
                        self._tick_epoch += 1
        return self._executor.submit(ordered)

    def _dispatch_impl(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        _exact_keys(
            request,
            {"schema", "request_id", "operation", "params"},
        )
        if request["schema"] != REQUEST_SCHEMA:
            raise OwnerWorkerError(
                "PROTOCOL_MISMATCH", "request protocol schema is incompatible", status=409
            )
        request_id = _scope(request["request_id"], "request_id")
        operation = _scope(request["operation"], "operation")
        params = request["params"]
        if not isinstance(params, dict):
            raise OwnerWorkerError("INVALID_REQUEST", "params must be an object", status=400)

        with self._lock:
            if self._stopping:
                raise OwnerWorkerError("OWNER_STOPPING", "owner is shutting down", status=503)
            if operation == "handshake":
                _exact_keys(params, set(), {"expected"})
                result = {
                    "launch_id": self.launch_id,
                    "compatibility": self.adapter.handshake(params.get("expected")),
                    "owner": self.adapter.owner_status(),
                    "recovery": self.recovery,
                }
            elif operation == "attach":
                _exact_keys(params, {"client_id"}, {"expected"})
                client_id = _scope(params["client_id"], "client_id")
                compatibility = self.adapter.handshake(params.get("expected"))
                self.clients.add(client_id)
                if self._shutdown_timer is not None:
                    self._shutdown_timer.cancel()
                    self._shutdown_timer = None
                result = {
                    "client_id": client_id,
                    "client_count": len(self.clients),
                    "launch_id": self.launch_id,
                    "compatibility": compatibility,
                    "owner": self.adapter.owner_status(),
                }
            elif operation == "bind_scope":
                result = self._bind_scope(params)
            elif operation == "detach":
                _exact_keys(params, {"client_id"})
                client_id = _scope(params["client_id"], "client_id")
                was_attached = client_id in self.clients
                self.clients.discard(client_id)
                self._scope_tokens = {
                    token: binding
                    for token, binding in self._scope_tokens.items()
                    if binding["client_id"] != client_id
                }
                result = {
                    "client_id": client_id,
                    "was_attached": was_attached,
                    "client_count": len(self.clients),
                }
                if was_attached and not self.clients and not self._keep_alive:
                    self._schedule_shutdown()
            elif operation == "keepalive":
                _exact_keys(params, {"client_id"})
                client_id = self._attached_client(params["client_id"])
                result = {
                    "client_id": client_id,
                    "state": self._scheduler_state,
                    "client_count": len(self.clients),
                    "mode": "realtime" if self._realtime else "logical",
                    "detach_policy": (
                        "keep-alive" if self._keep_alive else "shutdown-on-last-detach"
                    ),
                }
            elif operation == "status":
                _exact_keys(params, set())
                result = {
                    "launch_id": self.launch_id,
                    "client_count": len(self.clients),
                    "runtime_id": self.adapter.compatibility["runtime_id"],
                    "owner": self.adapter.owner_status(),
                    "capture": dict(self._capture),
                    "scheduler": self._scheduler_metadata(),
                    "runtime": {
                        "mode": "realtime" if self._realtime else "logical",
                        "state": self._scheduler_state,
                        "detach_policy": (
                            "keep-alive" if self._keep_alive else "shutdown-on-last-detach"
                        ),
                        "recovery": dict(self.recovery),
                    },
                }
            elif operation == "think":
                think_request = self._attached_request(params)
                if self._capture["paused"]:
                    raise OwnerWorkerError(
                        "CAPTURE_PAUSED",
                        "capture is paused; explicit think is not admitted",
                        status=409,
                    )
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.think(
                    think_request,
                    scope={
                        key: binding[key]
                        for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")
                    },
                )
            elif operation == "advance":
                request = self._attached_request(params)
                _exact_keys(
                    request,
                    {"operation_id", "ticks"},
                    {"expected_state_sha256", "source_enabled"},
                )
                if self._capture["paused"]:
                    raise OwnerWorkerError(
                        "CAPTURE_PAUSED",
                        "capture is paused; explicit advance is not admitted",
                        status=409,
                    )
                result = self.adapter.advance(
                    operation_id=_scope(request["operation_id"], "operation_id"),
                    ticks=request["ticks"],
                    source_enabled=request.get("source_enabled", True),
                    expected_state_sha256=request.get("expected_state_sha256"),
                )
            elif operation == "condense_transceiver":
                request = self._attached_request(params)
                _exact_keys(
                    request,
                    {
                        "schema", "operation_id", "transceiver_id", "chart_ids",
                        "input_ids", "output_ids", "context",
                    },
                    {
                        "observed", "rank", "error_allowance", "input_bound",
                        "horizon_ticks", "expected_state_sha256",
                    },
                )
                if request["schema"] != "cassipi.condense-transceiver.v1":
                    raise OwnerWorkerError(
                        "PROTOCOL_MISMATCH", "transceiver condensation schema is incompatible", status=409
                    )
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.condense_transceiver(
                    request,
                    scope={key: binding[key] for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")},
                )
            elif operation == "configure_temporal":
                request = self._attached_request(params)
                _exact_keys(
                    request,
                    {"schema", "operation_id", "memory_id", "action_ids", "observation_ids"},
                    {"max_states", "context", "expected_state_sha256"},
                )
                if request["schema"] != "cassipi.configure-temporal.v1":
                    raise OwnerWorkerError(
                        "PROTOCOL_MISMATCH", "temporal configuration schema is incompatible", status=409
                    )
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.configure_temporal(
                    request,
                    scope={key: binding[key] for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")},
                )
            elif operation == "learn_temporal":
                request = self._attached_request(params)
                _exact_keys(
                    request,
                    {"schema", "operation_id", "memory_id", "source"},
                    {"context", "expected_state_sha256"},
                )
                if request["schema"] != "cassipi.learn-temporal.v1":
                    raise OwnerWorkerError(
                        "PROTOCOL_MISMATCH", "temporal learning schema is incompatible", status=409
                    )
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.learn_temporal(
                    request,
                    scope={key: binding[key] for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")},
                )
            elif operation == "advance_temporal":
                request = self._attached_request(params)
                _exact_keys(
                    request,
                    {"schema", "operation_id", "memory_id", "action", "observation"},
                    {"participant_id", "expected_state_sha256"},
                )
                if request["schema"] != "cassipi.advance-temporal.v1":
                    raise OwnerWorkerError(
                        "PROTOCOL_MISMATCH", "temporal advance schema is incompatible", status=409
                    )
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.advance_temporal(
                    request,
                    scope={key: binding[key] for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")},
                )
            elif operation == "reset_temporal":
                request = self._attached_request(params)
                _exact_keys(
                    request,
                    {"schema", "operation_id", "memory_id"},
                    {"participant_id", "known_start", "expected_state_sha256"},
                )
                if request["schema"] != "cassipi.reset-temporal.v1":
                    raise OwnerWorkerError(
                        "PROTOCOL_MISMATCH", "temporal reset schema is incompatible", status=409
                    )
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.reset_temporal(
                    request,
                    scope={key: binding[key] for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")},
                )
            elif operation == "condense_temporal_skill":
                request = self._attached_request(params)
                _exact_keys(
                    request,
                    {"schema", "operation_id", "memory_id", "skill_id", "goal_observations"},
                    {"forbidden_observations", "expected_state_sha256"},
                )
                if request["schema"] != "cassipi.condense-temporal-skill.v1":
                    raise OwnerWorkerError(
                        "PROTOCOL_MISMATCH", "temporal skill schema is incompatible", status=409
                    )
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.condense_temporal_skill(
                    request,
                    scope={key: binding[key] for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")},
                )
            elif operation == "inspect_temporal":
                request = self._attached_request(params)
                _exact_keys(request, {"schema", "memory_id"}, {"action", "skill_id", "participant_id"})
                if request["schema"] != "cassipi.inspect-temporal.v1":
                    raise OwnerWorkerError(
                        "PROTOCOL_MISMATCH", "temporal inspection schema is incompatible", status=409
                    )
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.inspect_temporal(
                    request,
                    scope={key: binding[key] for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")},
                )
            elif operation == "select_temporal_action":
                request = self._attached_request(params)
                _exact_keys(
                    request,
                    {"schema", "memory_id", "skill_ids", "operations"},
                    {
                        "participant_id", "minimum_margin",
                        "expected_state_sha256",
                    },
                )
                if request["schema"] != "cassipi.select-temporal-action.v1":
                    raise OwnerWorkerError(
                        "PROTOCOL_MISMATCH",
                        "temporal action-selection schema is incompatible",
                        status=409,
                    )
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.select_temporal_action(
                    request,
                    scope={
                        key: binding[key]
                        for key in (
                            "profile_id", "project_id", "session_id",
                            "branch_id", "task_scope",
                        )
                    },
                )
            elif operation == "bind_temporal":
                request = self._attached_request(params)
                _exact_keys(request, {"schema", "operation_id", "memory_id", "participant_id"}, {"known_start", "expected_state_sha256"})
                if request["schema"] != "cassipi.bind-temporal.v1":
                    raise OwnerWorkerError("PROTOCOL_MISMATCH", "temporal binding schema is incompatible", status=409)
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.bind_temporal(request, scope={key: binding[key] for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")})
            elif operation == "inquire_temporal":
                request = self._attached_request(params)
                _exact_keys(request, {"schema", "memory_id", "operations"}, {"participant_id", "skill_id", "goal_observations", "horizon", "max_nodes", "forbidden_observations"})
                if request["schema"] != "cassipi.inquire-temporal.v1":
                    raise OwnerWorkerError("PROTOCOL_MISMATCH", "temporal inquiry schema is incompatible", status=409)
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.inquire_temporal(request, scope={key: binding[key] for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")})
            elif operation == "compose_temporal_task":
                request = self._attached_request(params)
                _exact_keys(request, {"schema", "operation_id", "task_id", "steps"}, {"context", "expected_state_sha256"})
                if request["schema"] != "cassipi.compose-temporal-task.v1":
                    raise OwnerWorkerError("PROTOCOL_MISMATCH", "temporal task composition schema is incompatible", status=409)
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.compose_temporal_task(request, scope={key: binding[key] for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")})
            elif operation == "inspect_temporal_task":
                request = self._attached_request(params)
                _exact_keys(request, {"schema", "task_id"})
                if request["schema"] != "cassipi.inspect-temporal-task.v1":
                    raise OwnerWorkerError("PROTOCOL_MISMATCH", "temporal task inspection schema is incompatible", status=409)
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.inspect_temporal_task(request, scope={key: binding[key] for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")})
            elif operation == "propose_temporal_task":
                request = self._attached_request(params)
                _exact_keys(request, {"schema", "operation_id", "task_id", "allowed_actions"}, {"expected_state_sha256"})
                if request["schema"] != "cassipi.propose-temporal-task.v1":
                    raise OwnerWorkerError("PROTOCOL_MISMATCH", "temporal task proposal schema is incompatible", status=409)
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.propose_temporal_task(request, scope={key: binding[key] for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")})
            elif operation == "acknowledge_temporal_task":
                request = self._attached_request(params)
                _exact_keys(request, {"schema", "operation_id", "task_id", "proposal_id", "participant_id", "action", "observation"}, {"expected_state_sha256"})
                if request["schema"] != "cassipi.acknowledge-temporal-task.v1":
                    raise OwnerWorkerError("PROTOCOL_MISMATCH", "temporal task acknowledgement schema is incompatible", status=409)
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.acknowledge_temporal_task(request, scope={key: binding[key] for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")})


            elif operation == "advance_transceivers":
                request = self._attached_request(params)
                _exact_keys(
                    request,
                    {"schema", "operation_id", "stimuli", "context"},
                    {"ticks", "connections", "force_full", "expected_state_sha256"},
                )
                if request["schema"] != "cassipi.advance-transceivers.v1":
                    raise OwnerWorkerError(
                        "PROTOCOL_MISMATCH", "transceiver advance schema is incompatible", status=409
                    )
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.advance_transceivers(
                    request,
                    scope={key: binding[key] for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")},
                )
            elif operation == "reset_transceiver":
                request = self._attached_request(params)
                _exact_keys(
                    request,
                    {"schema", "operation_id", "transceiver_id"},
                    {"expected_state_sha256"},
                )
                if request["schema"] != "cassipi.reset-transceiver.v1":
                    raise OwnerWorkerError(
                        "PROTOCOL_MISMATCH", "transceiver reset schema is incompatible", status=409
                    )
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.reset_transceiver(
                    request,
                    scope={key: binding[key] for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")},
                )
            elif operation == "inspect_transceivers":
                request = self._attached_request(params)
                _exact_keys(request, set())
                binding = self._scope_tokens[params["scope_token"]]
                result = self.adapter.inspect_transceivers(
                    scope={
                        key: binding[key]
                        for key in ("profile_id", "project_id", "session_id", "branch_id", "task_scope")
                    }
                )
            elif operation == "query":
                request = self._attached_request(params)
                _exact_keys(request, {"query_id"})
                result = self.adapter.query(request["query_id"])
            elif operation == "inspect_resonance":
                _exact_keys(params, set())
                result = self.adapter.inspect_resonance()
            elif operation == "bindings":
                result = self.adapter.bindings(self._attached_request(params))
            elif operation == "observe":
                result = self.adapter.observe(self._attached_request(params))
            elif operation == "memory_remember":
                result = self.adapter.remember(self._attached_request(params))
            elif operation == "memory_correct":
                result = self.adapter.correct(self._attached_request(params))
            elif operation == "forget_preview":
                result = self.adapter.forget_preview(self._attached_request(params))
            elif operation == "import_preview":
                result = self._importer.preview(self._attached_request(params))
            elif operation == "import_commit":
                result = self._importer.commit(self._attached_request(params))
            elif operation == "capture_status":
                result = self._capture_status(params)
            elif operation == "capture_set":
                result = self._capture_set(params)
            elif operation == "forget_authorize":
                result = self._forget_authorize(params)
            elif operation == "forget_execute":
                result = self._forget_execute(params)
            elif operation == "projection_inventory":
                result = self.adapter.projection_inventory(self._attached_request(params))
            elif operation == "project":
                result = self.adapter.project(self._attached_request(params))
            elif operation == "activate":
                result = self.adapter.activate(self._attached_request(params))
            elif operation == "rebuild":
                result = self.adapter.rebuild(self._attached_request(params))
            elif operation == "lineage_lookup":
                result = self.adapter.lineage_lookup(self._attached_request(params))
            elif operation == "lifecycle_prepare":
                result = self.adapter.lifecycle_prepare(self._attached_request(params))
            elif operation == "lifecycle_commit":
                result = self.adapter.lifecycle_commit(self._attached_request(params))
            elif operation == "lifecycle_cancel":
                result = self.adapter.lifecycle_cancel(self._attached_request(params))
            elif operation == "lifecycle_pending":
                result = self.adapter.lifecycle_pending(self._attached_request(params))
            elif operation == "shutdown":
                _exact_keys(params, {"if_idle"})
                if params["if_idle"] is not True:
                    raise OwnerWorkerError(
                        "INVALID_REQUEST", "shutdown requires if_idle=true", status=400
                    )
                if self.clients:
                    raise OwnerWorkerError(
                        "OWNER_BUSY",
                        "owner still has attached clients",
                        status=409,
                        details={"client_count": len(self.clients)},
                    )
                self._stopping = True
                self._scheduler_state = "stopping"
                self._persist_descriptor_locked()
                result = {"stopping": True, "pending_operations": self._executor.metrics()["queue_count"]}
                self._schedule_shutdown(force=True)
            else:
                raise OwnerWorkerError(
                    "UNSUPPORTED_OPERATION",
                    f"unsupported owner operation: {operation}",
                    status=404,
                )
        return {
            "schema": RESPONSE_SCHEMA,
            "request_id": request_id,
            "ok": True,
            "result": result,
        }


def _error_response(
    request_id: str,
    error: OwnerWorkerError | OwnerAdapterError | CassiPiImportError | FieldIntelligenceError,
) -> Mapping[str, Any]:
    details = dict(getattr(error, "details", {}))
    payload: dict[str, Any] = {
        "schema": RESPONSE_SCHEMA,
        "request_id": request_id,
        "ok": False,
        "error": {"code": error.code, "message": str(error)},
    }
    if details:
        payload["error"]["details"] = details
    return payload


def _handler(runtime: OwnerRuntime) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "CassiPi"
        sys_version = ""

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_bytes(
            self,
            status: int,
            encoded: bytes,
            mime: str,
            *,
            extra_headers: Mapping[str, str] | None = None,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            for name, value in (extra_headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(encoded)

        def _send(self, status: int, payload: Mapping[str, Any]) -> None:
            self._send_bytes(status, _canonical_json(payload), "application/json; charset=utf-8")

        def do_GET(self) -> None:
            try:
                if self.path not in {VIEW_PATH, SNAPSHOT_PATH}:
                    raise OwnerWorkerError("ENDPOINT_NOT_FOUND", "view endpoint does not exist", status=404)
                cookie = self.headers.get("Cookie")
                if not runtime.authorized_view(self.headers.get("Authorization"), cookie):
                    raise OwnerWorkerError("AUTHENTICATION_FAILED", "bearer authentication failed", status=401)
                if self.path == VIEW_PATH:
                    token = secrets.token_urlsafe(32)
                    with runtime._lock:
                        if len(runtime._view_tokens) >= 32:
                            runtime._view_tokens.clear()
                        runtime._view_tokens.add(token)
                    self._send_bytes(
                        200,
                        html(),
                        content_type(self.path),
                        extra_headers={"Set-Cookie": f"cassipi_view={token}; HttpOnly; SameSite=Strict; Path=/"},
                    )
                else:
                    self._send_bytes(200, _canonical_json(runtime.view_snapshot()), content_type(self.path))
            except OwnerWorkerError as exc:
                self._send(exc.status, _error_response("invalid", exc))
            except Exception:
                self._send(500, _error_response("invalid", OwnerWorkerError("INTERNAL_ERROR", "view request failed")))
        def do_POST(self) -> None:
            request_id = "invalid"
            try:
                if self.path != ENDPOINT_PATH:
                    raise OwnerWorkerError(
                        "ENDPOINT_NOT_FOUND", "owner endpoint does not exist", status=404
                    )
                if not runtime.authorized(self.headers.get("Authorization")):
                    raise OwnerWorkerError(
                        "AUTHENTICATION_FAILED", "bearer authentication failed", status=401
                    )
                if self.headers.get("Transfer-Encoding") is not None:
                    raise OwnerWorkerError(
                        "INVALID_REQUEST", "transfer encoding is not supported", status=400
                    )
                content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if content_type != "application/json":
                    raise OwnerWorkerError(
                        "INVALID_REQUEST", "content type must be application/json", status=400
                    )
                raw_length = self.headers.get("Content-Length")
                try:
                    length = int(raw_length or "")
                except ValueError as exc:
                    raise OwnerWorkerError(
                        "INVALID_REQUEST", "content length is missing or invalid", status=400
                    ) from exc
                if length < 1 or length > MAX_REQUEST_BYTES:
                    raise OwnerWorkerError(
                        "PAYLOAD_TOO_LARGE",
                        f"request must contain 1..{MAX_REQUEST_BYTES} bytes",
                        status=413,
                    )
                request = _parse_json(self.rfile.read(length))
                if isinstance(request.get("request_id"), str) and _SCOPE_RE.fullmatch(request["request_id"]):
                    request_id = request["request_id"]
                response = runtime.dispatch(request)
                self._send(200, response)
            except OwnerAdapterError as exc:
                self._send(exc.status, _error_response(request_id, exc))
            except FieldIntelligenceError as exc:
                self._send(409, _error_response(request_id, exc))
            except CassiPiImportError as exc:
                self._send(409, _error_response(request_id, exc))
            except OwnerWorkerError as exc:
                self._send(exc.status, _error_response(request_id, exc))
            except Exception:
                self._send(
                    500,
                    _error_response(
                        request_id,
                        OwnerWorkerError("INTERNAL_ERROR", "owner request failed"),
                    ),
                )

    return Handler


def _remove_own_descriptor(path: Path, launch_id: str) -> None:
    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=_pairs)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return
    if isinstance(value, dict) and value.get("launch_id") == launch_id:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def run(data_home: Path, *, realtime: bool = False, keep_alive: bool = False) -> int:
    home = _prepare_data_home(data_home)
    process_lock = OwnerProcessLock(home / LOCK_NAME)
    process_lock.acquire()
    descriptor_path = home / DESCRIPTOR_NAME
    launch_id = uuid.uuid4().hex
    server: ThreadingHTTPServer | None = None
    runtime: OwnerRuntime | None = None
    adapter: CanonicalOwnerAdapter | None = None
    try:
        recovery = _stale_descriptor(descriptor_path)
        adapter = CanonicalOwnerAdapter(data_home=home)
        bearer_secret = secrets.token_urlsafe(32)
        runtime = OwnerRuntime(
            adapter,
            launch_id=launch_id,
            bearer_secret=bearer_secret,
            recovery=recovery,
            data_home=home,
            realtime=realtime,
            keep_alive=keep_alive,
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(runtime))
        server.daemon_threads = False
        runtime.bind_server(server)
        endpoint = f"http://127.0.0.1:{server.server_address[1]}{ENDPOINT_PATH}"
        assert adapter is not None
        descriptor = {
            "schema": DESCRIPTOR_SCHEMA,
            "protocol_id": PROTOCOL_ID,
            "runtime_id": adapter.compatibility["runtime_id"],
            "launch_id": launch_id,
            "pid": os.getpid(),
            "endpoint": endpoint,
            "bearer_secret": bearer_secret,
            "compatibility": adapter.compatibility,
            "mode": "realtime" if realtime else "logical",
        }
        runtime.bind_descriptor(descriptor)
        print(
            _canonical_json(
                {
                    "schema": READY_SCHEMA,
                    "launch_id": launch_id,
                    "pid": os.getpid(),
                    "descriptor": str(descriptor_path),
                }
            ).decode("utf-8").rstrip(),
            flush=True,
        )

        def request_stop(signum: int, frame: Any) -> None:
            runtime._schedule_shutdown(force=True)

        for signum in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
            if signum is not None:
                signal.signal(signum, request_stop)
        server.serve_forever(poll_interval=0.05)
        return 0
    finally:
        if runtime is not None:
            runtime.close()
        elif adapter is not None:
            adapter.close()
        if server is not None:
            server.server_close()
        _remove_own_descriptor(descriptor_path, launch_id)
        process_lock.release()


def _migrate_v1(data_home: Path) -> Mapping[str, Any]:
    return FieldIntelligenceOwner.migrate_v1(Path(data_home), limits=CapacityLimits())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the private canonical CassiPi FI owner")
    parser.add_argument("--data-home", type=Path, required=True)
    parser.add_argument(
        "--realtime",
        action="store_true",
        help="enable the bounded 0.25-second physiological scheduler",
    )
    parser.add_argument(
        "--keep-alive",
        action="store_true",
        help="keep serving after the last attached client detaches",
    )
    parser.add_argument("--migrate-v1", action="store_true")
    args = parser.parse_args(argv)
    if args.migrate_v1:
        try:
            print(_canonical_json(_migrate_v1(args.data_home)).decode("utf-8").rstrip(), flush=True)
            return 0
        except Exception as exc:
            print(
                _canonical_json(
                    {"schema": ERROR_SCHEMA, "error": {"code": "MIGRATION_FAILED", "message": str(exc)}}
                ).decode("utf-8").rstrip(),
                file=sys.stderr,
                flush=True,
            )
            return 2
    try:
        return run(args.data_home, realtime=args.realtime, keep_alive=args.keep_alive)
    except (OwnerWorkerError, OwnerAdapterError) as exc:
        print(
            _canonical_json(
                {
                    "schema": ERROR_SCHEMA,
                    "error": {"code": exc.code, "message": str(exc)},
                }
            ).decode("utf-8").rstrip(),
            file=sys.stderr,
            flush=True,
        )
        return 2



if __name__ == "__main__":
    raise SystemExit(main())
