"""Bounded loopback JSON-lines daemon for the canonical multi-scale Qi field.

The daemon owns one fixed :class:`QiFieldController` and one field-only
``QiFieldState`` per session.  The sole adaptive payload is the controller's
``[S, 9*M, B]`` tensor.  Requests and responses never expose that tensor or a
teacher wave; only compact finite diagnostics and query scores cross the wire.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import socket
import socketserver
import sys
from pathlib import Path
from threading import RLock
from typing import Any, Mapping

import torch
from torch import Tensor

from cassi_qi_field import (
    QI_CODEBOOK_PROFILE_ID,
    QI_FIELD_LAYOUT_ID,
    QI_FIELD_OPERATOR_PROFILE_ID,
    QI_FIELD_STATE_SCHEMA,
    QiConsolidationResult,
    QiFieldConfig,
    QiFieldController,
    QiFieldDiagnostics,
    QiFieldError,
    QiFieldReadout,
    QiFieldState,
    QiSenseResult,
)


FIELD_DAEMON_PROTOCOL = "cassi.field-daemon.v2"
FIELD_DAEMON_PROFILE = "cassi.qi.multi-scale.v2"
FIELD_DAEMON_HOST = "127.0.0.1"
FIELD_DAEMON_PORT = 7600
PROTOCOL = FIELD_DAEMON_PROTOCOL
PROFILE = FIELD_DAEMON_PROFILE
HOST = FIELD_DAEMON_HOST
PORT = FIELD_DAEMON_PORT
DEFAULT_SESSION = "default"
MAX_PATH_LENGTH = 1024
MAX_STEPS = 256
MAX_BATCH_SIZE = 64
MAX_SESSIONS = 64
MAX_LINE_BYTES = 1 << 20
MAX_REQUESTS_PER_CONNECTION = 1024
REQUEST_TIMEOUT_SECONDS = 120.0
_SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_REQUEST_FIELDS: dict[str, frozenset[str]] = {
    "ping": frozenset({"cmd"}),
    "shutdown": frozenset({"cmd"}),
    "init": frozenset({"cmd", "session", "batch_size"}),
    "clear": frozenset({"cmd", "session", "batch_size"}),
    "load": frozenset({"cmd", "session", "path"}),
    "save": frozenset({"cmd", "session", "path"}),
    "reset": frozenset({"cmd", "session", "preserve_memory"}),
    "sense": frozenset({"cmd", "session", "wave", "structured_source", "source_trust"}),
    "sense_wave": frozenset({"cmd", "session", "wave", "structured_source", "source_trust"}),
    "step": frozenset({"cmd", "session", "steps"}),
    "evolve": frozenset({"cmd", "session", "steps"}),
    "consolidate": frozenset({"cmd", "session"}),
    "emit": frozenset({"cmd", "session"}),
    "diagnostics": frozenset({"cmd", "session", "structured_source", "source_trust"}),
    "correct": frozenset({"cmd", "session", "target_symbols"}),
    "state": frozenset({"cmd", "session"}),
}


class CassiFieldDaemonError(ValueError):
    """A request or field operation failure safe to return to a client."""


def _positive_int(name: str, value: Any, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > maximum:
        raise CassiFieldDaemonError(f"{name} must be an integer in [1, {maximum}]")
    return value


def _optional_bool(name: str, value: Any, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise CassiFieldDaemonError(f"{name} must be boolean")
    return value


def _session_id(value: Any) -> str:
    if not isinstance(value, str) or not _SESSION_PATTERN.fullmatch(value):
        raise CassiFieldDaemonError("session must match [A-Za-z0-9_.-]{1,64}")
    return value


def _path(value: Any) -> Path:
    if not isinstance(value, str) or not value or len(value) > MAX_PATH_LENGTH or "\x00" in value:
        raise CassiFieldDaemonError("path must be a non-empty bounded string")
    return Path(value)


def _finite_json(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _finite_json(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_finite_json(item) for item in value)
    return False


def _require_finite_numeric(value: Any, name: str) -> None:
    """Reject non-numeric JSON leaves before converting them with torch."""

    if isinstance(value, (list, tuple)):
        for item in value:
            _require_finite_numeric(item, name)
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CassiFieldDaemonError(f"{name} must contain only finite numbers")
    try:
        finite = math.isfinite(float(value))
    except (OverflowError, TypeError, ValueError) as exc:
        raise CassiFieldDaemonError(f"{name} must contain only finite numbers") from exc
    if not finite:
        raise CassiFieldDaemonError(f"{name} must contain only finite numbers")


def _tensor_list(value: Tensor) -> list[Any]:
    if not torch.is_tensor(value) or not bool(torch.isfinite(value).all().item()):
        raise CassiFieldDaemonError("field operation produced non-finite diagnostics")
    return value.detach().to(device="cpu").tolist()


def _batch_mean(value: Tensor, batch_size: int) -> Tensor:
    if value.ndim == 1 and value.shape[0] == batch_size:
        return value
    if value.ndim == 2 and value.shape[1] == batch_size:
        if value.shape[0] == 0:
            return value.new_zeros(batch_size)
        return value.mean(dim=0)
    raise CassiFieldDaemonError("field diagnostics have an invalid batch shape")


def _batch_max(value: Tensor, batch_size: int) -> Tensor:
    if value.ndim == 1 and value.shape[0] == batch_size:
        return value
    if value.ndim == 2 and value.shape[1] == batch_size:
        if value.shape[0] == 0:
            return value.new_zeros(batch_size)
        return value.max(dim=0).values
    raise CassiFieldDaemonError("field diagnostics have an invalid batch shape")


class CassiFieldDaemon:
    """Single-controller, bounded-session owner for the Qi v2 protocol."""

    def __init__(
        self,
        host: str = FIELD_DAEMON_HOST,
        port: int = FIELD_DAEMON_PORT,
        *,
        controller: QiFieldController | None = None,
        max_sessions: int = MAX_SESSIONS,
        max_batch_size: int = MAX_BATCH_SIZE,
    ) -> None:
        if host != FIELD_DAEMON_HOST:
            raise CassiFieldDaemonError("field daemon is loopback-only")
        if isinstance(port, bool) or not isinstance(port, int) or port < 1 or port > 65535:
            raise CassiFieldDaemonError("port must be an integer in [1, 65535]")
        self.host = host
        self.port = port
        self.controller = controller or QiFieldController(
            QiFieldConfig(scale_count=4, mode_count=512, alphabet_size=260)
        )
        if not isinstance(self.controller, QiFieldController):
            raise CassiFieldDaemonError("controller must be a QiFieldController")
        self.max_sessions = _positive_int("max_sessions", max_sessions, MAX_SESSIONS)
        self.max_batch_size = _positive_int("max_batch_size", max_batch_size, MAX_BATCH_SIZE)
        self._sessions: dict[str, QiFieldState] = {}
        self._lock = RLock()
        self.running = True

    @property
    def intelligence(self) -> QiFieldController:
        """Compatibility name for callers that inspect the fixed controller."""

        return self.controller

    def _base(self, *, ok: bool = True) -> dict[str, Any]:
        return {
            "ok": ok,
            "protocol": FIELD_DAEMON_PROTOCOL,
            "profile": FIELD_DAEMON_PROFILE,
            "finite": True,
        }

    def _error(self, message: str, *, state: QiFieldState | None = None) -> dict[str, Any]:
        response = self._base(ok=False)
        response["error"] = str(message) or "request failed"
        if state is not None:
            try:
                state.validate(self.controller.config)
            except (QiFieldError, RuntimeError, TypeError, ValueError):
                response["finite"] = False
        return response

    def _put_state(self, session: str, state: QiFieldState) -> None:
        state.validate(self.controller.config, device=torch.device("cpu"), dtype=torch.float32)
        if state.batch_size > self.max_batch_size:
            raise CassiFieldDaemonError("field state exceeds the configured batch limit")
        if session not in self._sessions and len(self._sessions) >= self.max_sessions:
            raise CassiFieldDaemonError("field session limit reached")
        self._sessions[session] = state

    def _state(self, session: str) -> QiFieldState:
        state = self._sessions.get(session)
        if state is None:
            raise CassiFieldDaemonError("field session is not initialized")
        return state

    def _state_info(self, session: str, state: QiFieldState) -> dict[str, Any]:
        state.validate(self.controller.config)
        response = self._base()
        response.update(
            {
                "session": session,
                "state_schema": QI_FIELD_STATE_SCHEMA,
                "layout_id": QI_FIELD_LAYOUT_ID,
                "operator_profile_id": QI_FIELD_OPERATOR_PROFILE_ID,
                "codebook_profile_id": QI_CODEBOOK_PROFILE_ID,
                "config_fingerprint": self.controller.config_fingerprint,
                "codebook_fingerprint": self.controller.codebook_fingerprint,
                "state_shape": list(state.field.shape),
                "batch_size": state.batch_size,
                "memory_bytes": state.field.numel() * state.field.element_size(),
            }
        )
        return response

    def _metrics(
        self,
        state: QiFieldState,
        diagnostics: QiFieldDiagnostics | None = None,
        readout: QiFieldReadout | None = None,
    ) -> dict[str, Any]:
        diagnostics = diagnostics or self.controller.diagnostics(state, structured_source=1.0)
        batch_size = state.batch_size
        if readout is None:
            available = diagnostics.available.any(dim=0)
            q = _batch_max(diagnostics.q, batch_size)
            q_max = _batch_max(diagnostics.q_max, batch_size)
            chi = _batch_max(diagnostics.chi, batch_size)
            cross = _batch_max(diagnostics.cross_scale_coherence, batch_size)
            read_gate = _batch_max(diagnostics.read_gate, batch_size)
        else:
            available = readout.available
            q = readout.q
            q_max = readout.q_max
            chi = readout.chi
            cross = readout.cross_scale_coherence
            read_gate = readout.read_gate
        metrics = {
            "available": available.detach().to(device="cpu").tolist(),
            "rho": _tensor_list(_batch_max(diagnostics.rho, batch_size)),
            "q": _tensor_list(q),
            "q_max": _tensor_list(q_max),
            "chi": _tensor_list(chi),
            "cross_scale_coherence": _tensor_list(cross),
            "read_gate": _tensor_list(read_gate),
            "write_gate": _tensor_list(_batch_max(diagnostics.write_gate, batch_size)),
            "consolidation_gate": _tensor_list(
                _batch_max(diagnostics.consolidation_gate, batch_size)
            ),
            "j_temporal": _tensor_list(_batch_mean(diagnostics.j_temporal, batch_size)),
            "j_scale": _tensor_list(_batch_mean(diagnostics.j_scale, batch_size)),
        }
        if not _finite_json(metrics):
            raise CassiFieldDaemonError("field metrics are not finite JSON")
        return metrics

    def _wave(self, value: Any, state: QiFieldState) -> Tensor:
        _require_finite_numeric(value, "wave")
        try:
            wave = torch.as_tensor(value, dtype=torch.float32, device="cpu")
        except (OverflowError, TypeError, ValueError, RuntimeError) as exc:
            raise CassiFieldDaemonError(f"wave must be a finite numeric array: {exc}") from exc
        expected = (state.batch_size, self.controller.wave_mode_count, 2)
        if tuple(wave.shape) != expected:
            raise CassiFieldDaemonError(
                f"wave must have shape [{state.batch_size}, {self.controller.wave_mode_count}, 2]"
            )
        if not bool(torch.isfinite(wave).all().item()):
            raise CassiFieldDaemonError("wave must be finite")
        return wave

    @staticmethod
    def _source(request: Mapping[str, Any]) -> tuple[Any | None, Any | None]:
        structured = request.get("structured_source")
        trust = request.get("source_trust")
        if structured is not None and trust is not None:
            raise CassiFieldDaemonError("provide structured_source or source_trust, not both")
        if structured is not None:
            _require_finite_numeric(structured, "structured_source")
        if trust is not None:
            _require_finite_numeric(trust, "source_trust")
        return structured, trust

    def _validate_request(self, request: Any) -> tuple[str, dict[str, Any]]:
        if not isinstance(request, dict):
            raise CassiFieldDaemonError("request must be a JSON object")
        if not _finite_json(request):
            raise CassiFieldDaemonError("request contains non-finite JSON")
        command = request.get("cmd")
        if not isinstance(command, str) or not command:
            raise CassiFieldDaemonError("cmd must be a non-empty string")
        allowed = _REQUEST_FIELDS.get(command)
        if allowed is None:
            raise CassiFieldDaemonError("unknown command")
        unexpected = set(request).difference(allowed)
        if unexpected:
            names = ", ".join(sorted(str(name) for name in unexpected))
            raise CassiFieldDaemonError(f"unexpected request field(s): {names}")
        return command, request

    def handle(self, request: Any) -> dict[str, Any]:
        """Validate and execute one request, returning strict JSON-safe data."""

        with self._lock:
            state: QiFieldState | None = None
            try:
                command, request = self._validate_request(request)
                if command == "ping":
                    response = self._base()
                    response.update(
                        {
                            "running": self.running,
                            "layout_id": QI_FIELD_LAYOUT_ID,
                            "operator_profile_id": QI_FIELD_OPERATOR_PROFILE_ID,
                            "codebook_profile_id": QI_CODEBOOK_PROFILE_ID,
                            "config_fingerprint": self.controller.config_fingerprint,
                            "codebook_fingerprint": self.controller.codebook_fingerprint,
                            "scale_count": self.controller.scale_count,
                            "mode_count": self.controller.mode_count,
                            "wave_mode_count": self.controller.wave_mode_count,
                            "alphabet_size": self.controller.config.alphabet_size,
                        }
                    )
                    return response
                if command == "shutdown":
                    self.running = False
                    response = self._base()
                    response["running"] = False
                    return response

                session = _session_id(request.get("session", DEFAULT_SESSION))
                if command in ("init", "clear"):
                    batch_size = _positive_int(
                        "batch_size", request.get("batch_size", 1), self.max_batch_size
                    )
                    state = self.controller.initial_state(batch_size, device="cpu", dtype=torch.float32)
                    self._put_state(session, state)
                    return self._state_info(session, state)
                if command == "load":
                    target = _path(request.get("path"))
                    state = self.controller.load(target, device="cpu", dtype=torch.float32)
                    self._put_state(session, state)
                    response = self._state_info(session, state)
                    response.update(
                        {
                            "path": str(target),
                            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                            "metrics": self._metrics(state),
                        }
                    )
                    return response

                state = self._state(session)
                if command == "reset":
                    preserve_memory = _optional_bool(
                        "preserve_memory", request.get("preserve_memory"), False
                    )
                    state = self.controller.reset(state, preserve_memory=preserve_memory)
                    self._put_state(session, state)
                    response = self._state_info(session, state)
                    response.update(
                        {
                            "preserve_memory": preserve_memory,
                            "metrics": self._metrics(state),
                        }
                    )
                    return response
                if command in ("sense", "sense_wave"):
                    wave = self._wave(request.get("wave"), state)
                    structured, trust = self._source(request)
                    sensed = self.controller.sense_wave(
                        state,
                        wave,
                        structured_source=structured,
                        source_trust=trust,
                        return_result=True,
                    )
                    if not isinstance(sensed, QiSenseResult):
                        raise CassiFieldDaemonError("Qi controller did not return a sense result")
                    state = sensed.state
                    self._put_state(session, state)
                    diagnostics = self.controller.diagnostics(
                        state, source_trust=sensed.source_trust
                    )
                    response = self._state_info(session, state)
                    response.update(
                        {
                            "write_gate": _tensor_list(sensed.write_gate),
                            "metrics": self._metrics(state, diagnostics=diagnostics),
                        }
                    )
                    return response
                if command in ("step", "evolve"):
                    steps = _positive_int("steps", request.get("steps", 1), MAX_STEPS)
                    state = self.controller.evolve(state, steps=steps)
                    self._put_state(session, state)
                    response = self._state_info(session, state)
                    response.update({"steps": steps, "metrics": self._metrics(state)})
                    return response
                if command == "consolidate":
                    consolidated = self.controller.consolidate(state, return_result=True)
                    if not isinstance(consolidated, QiConsolidationResult):
                        raise CassiFieldDaemonError("Qi controller did not return a consolidation result")
                    state = consolidated.state
                    self._put_state(session, state)
                    response = self._state_info(session, state)
                    response.update(
                        {
                            "consolidation_gate": _tensor_list(consolidated.consolidation_gate),
                            "metrics": self._metrics(state),
                        }
                    )
                    return response
                if command == "emit":
                    readout = self.controller.emit(state)
                    diagnostics = self.controller.diagnostics(state, structured_source=1.0)
                    response = self._state_info(session, state)
                    response.update(
                        {
                            "symbols": readout.symbols.detach().to(device="cpu").tolist(),
                            "available": readout.available.detach().to(device="cpu").tolist(),
                            "scores": _tensor_list(readout.scores),
                            "margin": _tensor_list(readout.margin),
                            "uncertainty": _tensor_list(readout.uncertainty),
                            "metrics": self._metrics(
                                state, diagnostics=diagnostics, readout=readout
                            ),
                        }
                    )
                    return response
                if command == "diagnostics":
                    structured, trust = self._source(request)
                    diagnostics = self.controller.diagnostics(
                        state,
                        structured_source=structured,
                        source_trust=trust,
                    )
                    response = self._state_info(session, state)
                    response["metrics"] = self._metrics(state, diagnostics=diagnostics)
                    return response
                if command == "correct":
                    targets = request.get("target_symbols")
                    if not isinstance(targets, list) or len(targets) != state.batch_size:
                        raise CassiFieldDaemonError("target_symbols must contain one integer per batch row")
                    state, correction_energy = self.controller.correct(state, targets)
                    self._put_state(session, state)
                    response = self._state_info(session, state)
                    response.update(
                        {
                            "correction_energy": _tensor_list(correction_energy),
                            "metrics": self._metrics(state),
                        }
                    )
                    return response
                if command == "state":
                    response = self._state_info(session, state)
                    response["metrics"] = self._metrics(state)
                    return response
                if command == "save":
                    target = _path(request.get("path"))
                    digest = self.controller.save(target, state)
                    response = self._state_info(session, state)
                    response.update({"path": str(target), "sha256": digest})
                    return response
                raise CassiFieldDaemonError("unknown command")
            except (
                CassiFieldDaemonError,
                QiFieldError,
                OSError,
                OverflowError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as exc:
                return self._error(str(exc) or "request failed", state=state)


class _FieldRequestHandler(socketserver.StreamRequestHandler):
    daemon: CassiFieldDaemon

    def handle(self) -> None:
        self.request.settimeout(REQUEST_TIMEOUT_SECONDS)
        for _ in range(MAX_REQUESTS_PER_CONNECTION):
            try:
                line = self.rfile.readline(MAX_LINE_BYTES + 1)
            except (OSError, socket.timeout):
                return
            if not line:
                return
            if len(line) > MAX_LINE_BYTES:
                self._write(self.daemon._error("request line exceeds size limit"))
                return
            if not line.endswith(b"\n"):
                self._write(self.daemon._error("request line must end with newline"))
                return
            try:
                request = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._write(self.daemon._error("request is not valid UTF-8 JSON"))
                continue
            response = self.daemon.handle(request)
            self._write(response)
            if not self.daemon.running:
                return

    def _write(self, response: Mapping[str, Any]) -> None:
        try:
            encoded = json.dumps(
                response, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
            self.wfile.write(encoded + b"\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError, TypeError, ValueError):
            return


class CassiFieldTCPServer(socketserver.TCPServer):
    """Single-worker bounded server; no unbounded client thread pool."""

    allow_reuse_address = True
    daemon_threads = False

    def __init__(self, daemon: CassiFieldDaemon) -> None:
        self.field_daemon = daemon
        handler_type = type(
            "CassiFieldRequestHandler", (_FieldRequestHandler,), {"daemon": daemon}
        )
        super().__init__((daemon.host, daemon.port), handler_type, bind_and_activate=True)
        self.timeout = 0.25

    def serve_forever_bounded(self) -> None:
        self._BaseServer__is_shut_down.clear()
        try:
            while self.field_daemon.running and not self._BaseServer__shutdown_request:
                self.handle_request()
        finally:
            self._BaseServer__is_shut_down.set()

    def serve_forever(self, poll_interval: float = 0.5) -> None:
        if not isinstance(poll_interval, (int, float)) or poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self.timeout = min(float(poll_interval), REQUEST_TIMEOUT_SECONDS)
        self.serve_forever_bounded()


def serve_field_daemon(daemon: CassiFieldDaemon | None = None) -> None:
    """Bind the loopback address and serve until shutdown is requested."""

    owner = daemon or CassiFieldDaemon()
    if owner.host != FIELD_DAEMON_HOST:
        raise CassiFieldDaemonError("field daemon is loopback-only")
    server = CassiFieldTCPServer(owner)
    try:
        server.serve_forever_bounded()
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cassi Qi field-only loopback daemon")
    parser.add_argument("--port", type=int, default=FIELD_DAEMON_PORT)
    args = parser.parse_args(argv)
    if args.port != FIELD_DAEMON_PORT:
        parser.error("the field daemon port is fixed at 7600")
    try:
        serve_field_daemon(CassiFieldDaemon(port=args.port))
    except (CassiFieldDaemonError, OSError) as exc:
        print(f"cassi field daemon: {exc}", file=sys.stderr)
        return 1
    return 0


__all__ = [
    "CassiFieldDaemon",
    "CassiFieldDaemonError",
    "CassiFieldTCPServer",
    "DEFAULT_SESSION",
    "FIELD_DAEMON_HOST",
    "FIELD_DAEMON_PORT",
    "FIELD_DAEMON_PROFILE",
    "FIELD_DAEMON_PROTOCOL",
    "HOST",
    "PORT",
    "PROFILE",
    "PROTOCOL",
    "serve_field_daemon",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
