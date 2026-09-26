"""Explicit Qi-gated F5 Qwen provider.

This remains a separate, default-off experimental provider. The process must
be started with ``--enable-f5`` before any field request can run. Inside that
explicitly enabled process, omitted request mode means field mode for ordinary
OpenAI-compatible clients; ``cassi_field_mode: "baseline"`` remains available
for controlled comparisons. The loopback Qi v2 daemon owns the sole adaptive
field state persisted by this provider.
"""

from __future__ import annotations

import argparse
import hashlib
import http.server
import ipaddress
import json
import math
import socket
import sys
import tempfile
import threading
import time
import urllib.parse
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

try:
    from .cassi_field_daemon import FIELD_DAEMON_PROFILE, FIELD_DAEMON_PROTOCOL
    from .cassi_field_teacher import FrozenFieldTeacher
    from .l18_generated_token_trajectory import (
        EXPECTED_MODEL_SHA256,
        L18GeneratedTokenTrajectory,
        RuntimeConfig,
    )
except ImportError:  # pragma: no cover - direct script execution
    from cassi_field_daemon import FIELD_DAEMON_PROFILE, FIELD_DAEMON_PROTOCOL
    from cassi_field_teacher import FrozenFieldTeacher
    from l18_generated_token_trajectory import EXPECTED_MODEL_SHA256, L18GeneratedTokenTrajectory, RuntimeConfig


PROTOCOL = "cassi.field-f5-provider.v2"
VERSION = 2
F5_PROFILE = "cassi.qi.field-gated-rerank.v2"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8083
DEFAULT_FIELD_HOST = "127.0.0.1"
DEFAULT_FIELD_PORT = 7600
DEFAULT_MAX_TOKENS = 2048
MAX_TOKENS_LIMIT = 4096
MAX_REQUEST_BYTES = 4 * 1024 * 1024
MAX_CONTEXT_MESSAGES = 128
MAX_SESSION_ID = 256
TOP_K = 16
FIELD_MODE = "field"
BASELINE_MODE = "baseline"


class ProviderError(RuntimeError):
    """A checked provider, model, field, or request failure."""

    def __init__(self, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.status = int(status)


def _finite_json(value: Any, label: str = "JSON value") -> None:
    """Reject non-finite or unsupported values before serializing a receipt."""

    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProviderError(f"{label} contains a non-finite number", status=500)
        return
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ProviderError(f"{label} contains a non-string key", status=500)
            _finite_json(nested, f"{label}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _finite_json(nested, f"{label}[{index}]")
        return
    raise ProviderError(f"{label} contains unsupported value {type(value).__name__}", status=500)


def _sha256_file(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError as exc:
        raise ProviderError(f"could not hash file {path}: {exc}", status=500) from exc


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    _finite_json(value, "session metadata")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")
    temporary: str | None = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        with open(fd, "wb", closefd=True) as stream:
            stream.write(encoded)
            stream.flush()
        Path(temporary).replace(path)
        temporary = None
    except OSError as exc:
        raise ProviderError(f"could not atomically save metadata {path}: {exc}", status=500) from exc
    finally:
        if temporary is not None:
            try:
                Path(temporary).unlink()
            except OSError:
                pass


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise ProviderError(f"session metadata is not valid JSON: {path}: {exc}", status=500) from exc
    if not isinstance(value, dict):
        raise ProviderError(f"session metadata must be an object: {path}", status=500)
    _finite_json(value, "session metadata")
    return value


def _render_messages(messages: Any) -> str:
    if not isinstance(messages, list) or not messages or len(messages) > MAX_CONTEXT_MESSAGES:
        raise ProviderError(f"messages must contain 1..{MAX_CONTEXT_MESSAGES} entries")
    parts: list[str] = []
    for index, message in enumerate(messages):
        if not isinstance(message, Mapping):
            raise ProviderError(f"message {index} is not an object")
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or not role or not isinstance(content, str):
            raise ProviderError(f"message {index} requires string role/content")
        if role not in {"system", "user", "assistant", "tool"}:
            raise ProviderError(f"unsupported message role: {role!r}")
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
    parts.append("<|im_start|>assistant\n")
    return "".join(parts)


def _session_id(request: Mapping[str, Any]) -> str:
    value = request.get("user")
    if value is None and isinstance(request.get("metadata"), Mapping):
        value = request["metadata"].get("cassi_session_id")
    if value is None:
        return f"ephemeral-{uuid.uuid4().hex}"
    if not isinstance(value, str) or not value or len(value) > MAX_SESSION_ID:
        raise ProviderError("user/cassi_session_id must be non-empty bounded text")
    return value


def _requested_max_tokens(value: Any, maximum: int) -> int:
    if value is None:
        return maximum
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ProviderError(f"max_tokens must be an integer in [1, {maximum}]")
    return int(value)


def _fixed_boundary_symbol(piece: bytes | bytearray | memoryview) -> int | None:
    """Map a tokenizer piece to one fixed 8-bit boundary symbol.

    A literal one-byte piece keeps its byte identity. Longer pieces use a
    deterministic, parameter-free byte fingerprint so common leading-space
    markers do not collapse the candidate set onto one symbol.
    """

    raw = bytes(piece)
    if not raw:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        payload = raw
    else:
        if text.startswith(("Ġ", "Ċ", "ĉ", "Ģ")):
            text = text[1:]
        payload = text.encode("utf-8") or raw
    if len(payload) == 1:
        return int(payload[0])
    return int(hashlib.blake2b(payload, digest_size=1, person=b"CassiF5").digest()[0])


def _qi_scalar(metrics: Mapping[str, Any], name: str) -> float:
    """Extract one finite scalar from a daemon's single-batch Qi metrics."""

    value = metrics.get(name)
    if isinstance(value, list):
        if len(value) != 1:
            raise ProviderError(f"field daemon metric {name!r} is not single-batch", status=503)
        value = value[0]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProviderError(f"field daemon metric {name!r} is malformed", status=503)
    result = float(value)
    if not math.isfinite(result):
        raise ProviderError(f"field daemon metric {name!r} is non-finite", status=503)
    return result


def _qi_available(response: Mapping[str, Any]) -> bool:
    value = response.get("available")
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], bool):
        raise ProviderError("field daemon availability is malformed", status=503)
    return value[0]


def _rerank_candidates(
    rows: Sequence[Mapping[str, Any]],
    field_scores: Sequence[float],
    boundary_symbols: Sequence[int | None],
    *,
    field_weight: float,
) -> tuple[int, dict[str, Any]]:
    """Apply a fixed byte-probe score to an ordinary Qwen candidate set."""

    if len(rows) != len(boundary_symbols) or not rows:
        raise ProviderError("candidate rows and fixed-boundary symbols differ", status=500)
    scores = np.asarray(field_scores, dtype=np.float64)
    if scores.ndim != 1 or scores.size < 256 or not np.isfinite(scores).all():
        raise ProviderError("field resonance scores are malformed", status=500)
    if not math.isfinite(float(field_weight)) or field_weight < 0.0:
        raise ProviderError("field_weight must be finite and non-negative", status=500)

    raw_candidates: list[tuple[float, int, int, int | None, float]] = []
    covered = 0
    symbols: list[int] = []
    biases: list[float] = []
    for index, (row, symbol) in enumerate(zip(rows, boundary_symbols)):
        token_id = int(row["token_id"])
        logit = float(row["logit"])
        if not math.isfinite(logit):
            raise ProviderError("ordinary candidate logit is non-finite", status=500)
        if symbol is None:
            bias = 0.0
        else:
            if symbol < 0 or symbol >= scores.size:
                raise ProviderError("candidate byte is outside the fixed boundary alphabet", status=500)
            bias = float(scores[symbol])
            covered += 1
            symbols.append(symbol)
        biases.append(bias)
        raw_candidates.append((logit, token_id, index, symbol, bias))
    bias_array = np.asarray(biases, dtype=np.float64)
    bias_mean = float(np.mean(bias_array)) if bias_array.size else 0.0
    bias_std = float(np.std(bias_array)) if bias_array.size else 0.0
    if bias_std > 1.0e-12:
        normalized_biases = (bias_array - bias_mean) / bias_std
    else:
        normalized_biases = np.zeros_like(bias_array)
    adjusted = [
        (logit + float(field_weight) * float(normalized_biases[index]), token_id, index, symbol)
        for index, (logit, token_id, _row_index, symbol, _raw_bias) in enumerate(raw_candidates)
    ]
    adjusted.sort(key=lambda value: (-value[0], value[1]))
    selected_score, selected_id, selected_index, selected_symbol = adjusted[0]
    unique_symbols = len(set(symbols))
    field_score_min = min(biases) if biases else 0.0
    field_score_max = max(biases) if biases else 0.0
    detail = {
        "candidate_count": len(rows),
        "covered_count": covered,
        "coverage_fraction": covered / float(len(rows)),
        "unique_symbols": unique_symbols,
        "collision_count": len(symbols) - unique_symbols,
        "field_score_min": float(field_score_min),
        "field_score_max": float(field_score_max),
        "field_score_span": float(field_score_max - field_score_min),
        "selected_index": selected_index,
        "selected_token_id": selected_id,
        "selected_symbol": selected_symbol,
        "selected_adjusted_score": float(selected_score),
        "field_weight": float(field_weight),
    }
    _finite_json(detail, "candidate detail")
    return selected_id, detail


class F5FieldDaemonClient:
    """Strict single-connection client for the Qi v2 JSON-lines field owner."""

    def __init__(self, host: str, port: int, *, timeout_seconds: float = 30.0) -> None:
        self.host = host
        self.port = int(port)
        self.timeout_seconds = float(timeout_seconds)
        self._socket: socket.socket | None = None
        self._reader: Any | None = None
        self._writer: Any | None = None
        self._identity: dict[str, str] = {}

    def connect(self) -> dict[str, Any]:
        if self._socket is not None:
            raise ProviderError("field client is already connected", status=500)
        try:
            self._socket = socket.create_connection((self.host, self.port), timeout=self.timeout_seconds)
            self._socket.settimeout(self.timeout_seconds)
            self._reader = self._socket.makefile("rb")
            self._writer = self._socket.makefile("wb")
            response = self.request({"cmd": "ping"})
        except (OSError, ProviderError) as exc:
            self.close()
            raise ProviderError(f"could not connect to field daemon {self.host}:{self.port}: {exc}", status=503) from exc
        if response.get("profile") != FIELD_DAEMON_PROFILE:
            self.close()
            raise ProviderError("field daemon profile mismatch", status=503)
        for key, expected in {
            "scale_count": 4,
            "mode_count": 512,
            "wave_mode_count": 256,
            "alphabet_size": 260,
        }.items():
            if response.get(key) != expected:
                self.close()
                raise ProviderError(
                    f"field daemon {key} is incompatible with the frozen teacher",
                    status=503,
                )
        identity: dict[str, str] = {}
        for key in ("config_fingerprint", "codebook_fingerprint"):
            value = response.get(key)
            try:
                valid_digest = isinstance(value, str) and len(value) == 64 and int(value, 16) >= 0
            except ValueError:
                valid_digest = False
            if not valid_digest:
                self.close()
                raise ProviderError(f"field daemon {key} is malformed", status=503)
            identity[key] = value
        self._identity = identity
        return response

    @property
    def identity(self) -> dict[str, str]:
        if not self._identity:
            raise ProviderError("field client has no verified daemon identity", status=500)
        return dict(self._identity)

    def request(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if self._reader is None or self._writer is None:
            raise ProviderError("field client is not connected", status=503)
        try:
            raw = json.dumps(dict(payload), ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8") + b"\n"
            self._writer.write(raw)
            self._writer.flush()
            line = self._reader.readline()
        except (OSError, TypeError, ValueError) as exc:
            raise ProviderError(f"field daemon transport failed for {payload.get('cmd')!r}: {exc}", status=503) from exc
        if not line:
            raise ProviderError(f"field daemon closed for {payload.get('cmd')!r}", status=503)
        try:
            response = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError("field daemon returned invalid JSON", status=503) from exc
        if (
            not isinstance(response, dict)
            or response.get("protocol") != FIELD_DAEMON_PROTOCOL
            or response.get("profile") != FIELD_DAEMON_PROFILE
        ):
            raise ProviderError("field daemon protocol/profile mismatch", status=503)
        if response.get("ok") is not True:
            raise ProviderError(f"field daemon rejected {payload.get('cmd')!r}: {response.get('error')}", status=503)
        if response.get("finite") is False:
            raise ProviderError("field daemon reported a non-finite state", status=503)
        return response

    def clear(self, session: str) -> dict[str, Any]:
        return self.request({"cmd": "clear", "session": session})

    def load(self, session: str, path: Path) -> dict[str, Any]:
        return self.request({"cmd": "load", "session": session, "path": str(path)})

    def save(self, session: str, path: Path) -> dict[str, Any]:
        return self.request({"cmd": "save", "session": session, "path": str(path)})

    def sense(self, session: str, wave: np.ndarray) -> dict[str, Any]:
        array = np.asarray(wave, dtype=np.float32)
        if array.shape != (256, 2) or not np.isfinite(array).all():
            raise ProviderError("teacher wave does not match the fixed 256x2 boundary", status=500)
        return self.request(
            {
                "cmd": "sense",
                "session": session,
                "wave": [array.tolist()],
                "structured_source": 1.0,
            }
        )

    def step(self, session: str, steps: int = 1) -> dict[str, Any]:
        return self.request({"cmd": "step", "session": session, "steps": int(steps)})

    def consolidate(self, session: str) -> dict[str, Any]:
        return self.request({"cmd": "consolidate", "session": session})

    def emit(self, session: str) -> dict[str, Any]:
        return self.request({"cmd": "emit", "session": session})

    def diagnostics(self, session: str) -> dict[str, Any]:
        return self.request({"cmd": "diagnostics", "session": session})

    def correct(self, session: str, symbol: int) -> dict[str, Any]:
        return self.request({"cmd": "correct", "session": session, "target_symbols": [int(symbol)]})

    def close(self) -> None:
        for handle in (self._reader, self._writer):
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
        self._reader = None
        self._writer = None
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
        self._socket = None
        self._identity = {}


class SessionCheckpointStore:
    """Own only field checkpoints and non-sensitive fixed identity metadata."""

    def __init__(self, root: Path, *, model_sha256: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.model_sha256 = model_sha256
        self.checkpoint_identity = hashlib.sha256(
            f"{PROTOCOL}:{VERSION}:{F5_PROFILE}:{model_sha256}".encode("utf-8")
        ).hexdigest()

    def _digest(self, session: str) -> str:
        return hashlib.sha256(session.encode("utf-8")).hexdigest()

    def field_path(self, session: str) -> Path:
        return self.root / f"{self._digest(session)}.field.pt"

    def metadata_path(self, session: str) -> Path:
        return self.root / f"{self._digest(session)}.json"

    def load(self, session: str) -> dict[str, Any] | None:
        value = _load_json(self.metadata_path(session))
        field_path = self.field_path(session)
        if value is None:
            if field_path.is_file():
                raise ProviderError("field checkpoint exists without metadata", status=500)
            return None
        if value.get("protocol") != PROTOCOL or value.get("version") != VERSION:
            raise ProviderError("F5 session metadata protocol/version mismatch", status=500)
        if value.get("profile") != F5_PROFILE:
            raise ProviderError("F5 session metadata profile mismatch", status=500)
        if value.get("field_protocol") != FIELD_DAEMON_PROTOCOL or value.get("field_profile") != FIELD_DAEMON_PROFILE:
            raise ProviderError("F5 session metadata field protocol/profile mismatch", status=500)
        for key in (
            "field_config_fingerprint",
            "field_codebook_fingerprint",
            "field_checkpoint_sha256",
        ):
            digest = value.get(key)
            try:
                valid_digest = (
                    isinstance(digest, str)
                    and len(digest) == 64
                    and int(digest, 16) >= 0
                )
            except ValueError:
                valid_digest = False
            if not valid_digest:
                raise ProviderError(f"F5 session metadata {key} is malformed", status=500)
        if value.get("session_id") != session or value.get("model_sha256") != self.model_sha256:
            raise ProviderError("F5 session metadata identity/model mismatch", status=500)
        if value.get("field_checkpoint_path") != str(field_path):
            raise ProviderError("F5 field checkpoint path is not session-isolated", status=500)
        if value.get("checkpoint_identity") != self.checkpoint_identity:
            raise ProviderError("F5 checkpoint identity mismatch", status=500)
        if not field_path.is_file():
            raise ProviderError("F5 field metadata has no field checkpoint", status=500)
        if _sha256_file(field_path) != value["field_checkpoint_sha256"]:
            raise ProviderError("F5 field checkpoint hash mismatch", status=500)
        return value

    def save(self, session: str, value: Mapping[str, Any]) -> None:
        if value.get("protocol") != PROTOCOL or value.get("version") != VERSION:
            raise ProviderError("invalid F5 metadata protocol/version", status=500)
        if value.get("session_id") != session:
            raise ProviderError("invalid F5 metadata session identity", status=500)
        forbidden = {
            "prompt",
            "messages",
            "token",
            "token_ids",
            "token_pieces",
            "residual",
            "logits",
            "kv",
            "teacher",
            "teacher_state",
            "teacher_trace",
            "trace",
            "wave",
            "field_array",
            "raw_field",
        }

        def contains_forbidden(nested: Any) -> bool:
            if isinstance(nested, Mapping):
                return any(
                    str(key).lower() in forbidden or contains_forbidden(child)
                    for key, child in nested.items()
                )
            if isinstance(nested, (list, tuple)):
                return any(contains_forbidden(child) for child in nested)
            return False

        if contains_forbidden(value):
            raise ProviderError("F5 field metadata contains forbidden teacher/model state", status=500)
        _atomic_json(self.metadata_path(session), value)


def _field_session(session: str) -> str:
    """Use a bounded daemon session name without exposing the caller's ID."""

    return "f5-" + hashlib.sha256(session.encode("utf-8")).hexdigest()[:58]


@dataclass(frozen=True)
class ProviderConfig:
    model_path: Path
    dll_dir: Path
    state_dir: Path
    field_host: str = DEFAULT_FIELD_HOST
    field_port: int = DEFAULT_FIELD_PORT
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    context_size: int = 128
    n_batch: int = 64
    n_ubatch: int = 64
    gpu_layers: int = 99
    max_tokens: int = DEFAULT_MAX_TOKENS
    field_weight: float = 0.25
    layer_index: int = 32
    enable_f5: bool = False
    timeout_seconds: float = 60.0
    expected_model_sha256: str = EXPECTED_MODEL_SHA256

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_path", Path(self.model_path).resolve())
        object.__setattr__(self, "dll_dir", Path(self.dll_dir).resolve())
        object.__setattr__(self, "state_dir", Path(self.state_dir).resolve())
        for name in ("host", "field_host"):
            value = getattr(self, name)
            if value == "localhost":
                continue
            try:
                parsed = ipaddress.ip_address(value)
            except ValueError as exc:
                raise ProviderError(f"{name} must be a loopback address", status=2) from exc
            if not parsed.is_loopback:
                raise ProviderError(f"{name} must be loopback-only", status=2)
        for name in ("port", "field_port"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
                raise ProviderError(f"{name} must be an integer in [1, 65535]", status=2)
        for name in ("context_size", "n_batch", "n_ubatch"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ProviderError(f"{name} must be a positive integer", status=2)
        if isinstance(self.gpu_layers, bool) or not isinstance(self.gpu_layers, int) or self.gpu_layers < 0:
            raise ProviderError("gpu_layers must be a non-negative integer", status=2)
        if isinstance(self.max_tokens, bool) or not isinstance(self.max_tokens, int) or not 1 <= self.max_tokens <= MAX_TOKENS_LIMIT:
            raise ProviderError(f"max_tokens must be an integer in [1, {MAX_TOKENS_LIMIT}]", status=2)
        if isinstance(self.field_weight, bool) or not isinstance(self.field_weight, (int, float)) or not math.isfinite(float(self.field_weight)) or self.field_weight < 0.0:
            raise ProviderError("field_weight must be finite and non-negative", status=2)
        if isinstance(self.layer_index, bool) or not isinstance(self.layer_index, int) or not 0 <= self.layer_index < 64:
            raise ProviderError("layer_index must be in [0, 63]", status=2)
        if not isinstance(self.enable_f5, bool):
            raise ProviderError("enable_f5 must be boolean", status=2)
        if not math.isfinite(float(self.timeout_seconds)) or self.timeout_seconds <= 0.0:
            raise ProviderError("timeout_seconds must be finite and positive", status=2)
        if len(self.expected_model_sha256) != 64:
            raise ProviderError("expected_model_sha256 must be a 64-character digest", status=2)


class CassiF5Provider:
    """One frozen Qwen runtime with explicit baseline and field modes."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self._lock = threading.RLock()
        self._runtime: L18GeneratedTokenTrajectory | None = None
        self._teacher = FrozenFieldTeacher(layer_index=config.layer_index)
        self._started = False
        self._model_sha256 = config.expected_model_sha256
        self._store = SessionCheckpointStore(config.state_dir, model_sha256=self._model_sha256)

    @property
    def started(self) -> bool:
        return self._started

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            runtime = L18GeneratedTokenTrajectory(
                RuntimeConfig(
                    model_path=self.config.model_path,
                    dll_dir=self.config.dll_dir,
                    context_size=self.config.context_size,
                    n_batch=self.config.n_batch,
                    n_ubatch=self.config.n_ubatch,
                    gpu_layers=self.config.gpu_layers,
                    expected_model_sha256=self.config.expected_model_sha256,
                )
            )
            self._runtime = runtime
            self._started = True

    def close(self) -> None:
        with self._lock:
            runtime = self._runtime
            self._runtime = None
            self._started = False
            if runtime is not None:
                runtime.close(suppress=True)

    def _require_runtime(self) -> L18GeneratedTokenTrajectory:
        if not self._started or self._runtime is None:
            raise ProviderError("F5 provider is not started", status=500)
        return self._runtime

    def health(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ok": self._started,
                "protocol": PROTOCOL,
                "version": VERSION,
                "profile": F5_PROFILE,
                "model": self.config.model_path.name,
                "field_enabled": self.config.enable_f5,
                "field_protocol": FIELD_DAEMON_PROTOCOL,
                "field_profile": FIELD_DAEMON_PROFILE,
                "qi_gated": True,
                "field_host": self.config.field_host,
                "field_port": self.config.field_port,
                "finite": True,
            }

    def models(self) -> dict[str, Any]:
        return {
            "object": "list",
            "data": [
                {
                    "id": self.config.model_path.name,
                    "object": "model",
                    "owned_by": "cassi-experimental",
                    "cassi_field_modes": [BASELINE_MODE, FIELD_MODE],
                    "f5_enabled": self.config.enable_f5,
                }
            ],
        }

    def _prepare_field(self, session: str) -> tuple[F5FieldDaemonClient, str, dict[str, Any]]:
        client = F5FieldDaemonClient(
            self.config.field_host,
            self.config.field_port,
            timeout_seconds=self.config.timeout_seconds,
        )
        prepared = False
        try:
            client.connect()
            daemon_identity = client.identity
            daemon_session = _field_session(session)
            checkpoint = self._store.load(session)
            if checkpoint is None:
                client.clear(daemon_session)
                prepared = True
                return client, daemon_session, {
                    "restored": False,
                    "event_count": 0,
                    **daemon_identity,
                }
            for metadata_key, identity_key in (
                ("field_config_fingerprint", "config_fingerprint"),
                ("field_codebook_fingerprint", "codebook_fingerprint"),
            ):
                if checkpoint.get(metadata_key) != daemon_identity[identity_key]:
                    raise ProviderError(
                        "F5 checkpoint belongs to a different Qi field identity",
                        status=500,
                    )
            path = self._store.field_path(session)
            loaded = client.load(daemon_session, path)
            loaded_sha256 = str(loaded.get("sha256", ""))
            if loaded_sha256 != checkpoint.get("field_checkpoint_sha256"):
                raise ProviderError("F5 field checkpoint hash mismatch", status=500)
            prepared = True
            return client, daemon_session, {
                "restored": True,
                "event_count": int(checkpoint.get("event_count", 0)),
                "field_hash": loaded_sha256,
                **daemon_identity,
            }
        finally:
            if not prepared:
                client.close()

    def _commit_field_checkpoint(
        self,
        client: F5FieldDaemonClient,
        daemon_session: str,
        session: str,
        *,
        prompt_sha256: str,
        event_count: int,
    ) -> dict[str, Any]:
        path = self._store.field_path(session)
        saved = client.save(daemon_session, path)
        field_sha256 = str(saved.get("sha256", ""))
        if len(field_sha256) != 64:
            raise ProviderError("field daemon returned malformed checkpoint hash", status=500)
        daemon_identity = client.identity
        metadata = {
            "protocol": PROTOCOL,
            "version": VERSION,
            "profile": F5_PROFILE,
            "field_protocol": FIELD_DAEMON_PROTOCOL,
            "field_profile": FIELD_DAEMON_PROFILE,
            "field_config_fingerprint": daemon_identity["config_fingerprint"],
            "field_codebook_fingerprint": daemon_identity["codebook_fingerprint"],
            "session_id": session,
            "model_sha256": self._model_sha256,
            "field_checkpoint_path": str(path),
            "field_checkpoint_sha256": field_sha256,
            "checkpoint_identity": self._store.checkpoint_identity,
            "event_count": int(event_count),
            "last_prompt_sha256": prompt_sha256,
            "updated_at": float(time.time()),
        }
        self._store.save(session, metadata)
        return {
            "checkpoint_path": str(path),
            "checkpoint_sha256": field_sha256,
            "field_config_fingerprint": daemon_identity["config_fingerprint"],
            "field_codebook_fingerprint": daemon_identity["codebook_fingerprint"],
            "checkpoint_identity": self._store.checkpoint_identity,
            "event_count": int(event_count),
        }

    def complete(self, request: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            if not isinstance(request, Mapping):
                raise ProviderError("completion request must be an object")
            # The Harness OpenAI adapter requests SSE.  The provider still
            # computes one finite completion, then the HTTP handler exposes
            # that completion as a standards-compatible stream.
            temperature = request.get("temperature", 0.0)
            if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not math.isfinite(float(temperature)):
                raise ProviderError("temperature must be finite")
            if float(temperature) != 0.0:
                raise ProviderError("F5 demonstration requires temperature=0")
            # The Harness route is field-intelligence-first and cannot add
            # provider-specific JSON fields.  Keep explicit baseline available
            # for comparisons, while an omitted mode means field mode.
            mode = request.get("cassi_field_mode", FIELD_MODE)
            if mode not in {BASELINE_MODE, FIELD_MODE}:
                raise ProviderError('cassi_field_mode must be "baseline" or "field"')
            if mode == FIELD_MODE and not self.config.enable_f5:
                raise ProviderError("field mode is disabled; restart with --enable-f5", status=403)
            runtime = self._require_runtime()
            prompt = _render_messages(request.get("messages"))
            prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            session = _session_id(request)
            max_tokens = _requested_max_tokens(request.get("max_tokens"), self.config.max_tokens)
            field_client: F5FieldDaemonClient | None = None
            daemon_session: str | None = None
            field_state: dict[str, Any] = {"restored": False, "event_count": 0}
            try:
                # Do not hold the daemon socket open during native prefill:
                # the daemon's idle read timeout is shorter than a large
                # Harness prompt decode.
                runtime.reset_context()
                prompt_ids = runtime.tokenize(prompt)
                if not prompt_ids:
                    raise ProviderError("prompt tokenization produced no tokens")
                if len(prompt_ids) + max_tokens >= runtime.config.context_size:
                    raise ProviderError("prompt plus max_tokens exceeds context_size")
                current_record = runtime.decode_initial(prompt_ids)
                current_position = current_record.final_position
                if mode == FIELD_MODE:
                    field_client, daemon_session, field_state = self._prepare_field(session)
                generated_ids: list[int] = []
                generated_pieces: list[str] = []
                changed_tokens = 0
                teacher_events = 0
                coverage_count = 0
                candidate_count = 0
                collision_count = 0
                unique_symbol_count = 0
                field_score_span_sum = 0.0
                field_score_span_max = 0.0
                qi_metric_sums = {
                    "q": 0.0,
                    "chi": 0.0,
                    "cross_scale_coherence": 0.0,
                    "read_gate": 0.0,
                    "write_gate": 0.0,
                    "consolidation_gate": 0.0,
                    "j_temporal": 0.0,
                    "j_scale": 0.0,
                }
                qi_available_events = 0
                qi_abstention_count = 0
                effective_field_weight_sum = 0.0
                effective_field_weight_max = 0.0
                event_count = int(field_state.get("event_count", 0))
                for output_index in range(max_tokens):
                    rows = runtime.top_k_with_pieces(current_record.ordinary_logits, TOP_K)
                    baseline_id = int(rows[0]["token_id"])
                    selected_id = baseline_id
                    selected_detail = {
                        "candidate_count": len(rows),
                        "covered_count": 0,
                        "coverage_fraction": 0.0,
                        "unique_symbols": 0,
                        "collision_count": 0,
                        "field_score_min": 0.0,
                        "field_score_max": 0.0,
                        "field_score_span": 0.0,
                        "selected_index": 0,
                        "selected_token_id": baseline_id,
                        "selected_symbol": None,
                        "selected_adjusted_score": float(rows[0]["logit"]),
                        "field_weight": 0.0,
                    }
                    if mode == FIELD_MODE:
                        assert field_client is not None and daemon_session is not None
                        event = self._teacher.capture(
                            record=current_record,
                            runtime=runtime,
                            sequence_id=0,
                            event_index=event_count,
                        )
                        sense_receipt = field_client.sense(daemon_session, event.wave)
                        field_client.step(daemon_session, 1)
                        field_client.consolidate(daemon_session)
                        emission = field_client.emit(daemon_session)
                        qi_metrics = emission.get("metrics")
                        if not isinstance(qi_metrics, Mapping):
                            raise ProviderError("field daemon emission lacks Qi metrics", status=503)
                        field_available = _qi_available(emission)
                        event_metrics = {
                            name: _qi_scalar(qi_metrics, name)
                            for name in (
                                "q",
                                "chi",
                                "cross_scale_coherence",
                                "read_gate",
                                "consolidation_gate",
                                "j_temporal",
                                "j_scale",
                            )
                        }
                        event_metrics["write_gate"] = _qi_scalar(sense_receipt, "write_gate")
                        for bounded_name in (
                            "q",
                            "chi",
                            "cross_scale_coherence",
                            "read_gate",
                            "write_gate",
                            "consolidation_gate",
                        ):
                            if not 0.0 <= event_metrics[bounded_name] <= 1.0:
                                raise ProviderError(
                                    f"field daemon metric {bounded_name!r} is outside [0,1]",
                                    status=503,
                                )
                        for name, value in event_metrics.items():
                            qi_metric_sums[name] += value
                        effective_field_weight = (
                            float(self.config.field_weight) * event_metrics["read_gate"]
                            if field_available
                            else 0.0
                        )
                        effective_field_weight_sum += effective_field_weight
                        effective_field_weight_max = max(
                            effective_field_weight_max, effective_field_weight
                        )
                        teacher_events += 1
                        if field_available:
                            qi_available_events += 1
                        else:
                            qi_abstention_count += 1
                        if field_available and effective_field_weight > 0.0:
                            scores = emission.get("scores")
                            if (
                                isinstance(scores, list)
                                and scores
                                and isinstance(scores[0], list)
                            ):
                                if len(scores) != 1:
                                    raise ProviderError(
                                        "batched field resonance is unsupported", status=503
                                    )
                                scores = scores[0]
                            if not isinstance(scores, list):
                                raise ProviderError(
                                    "available field daemon emission lacks scores", status=503
                                )
                            symbols: list[int | None] = []
                            for row in rows:
                                token_id = int(row["token_id"])
                                symbols.append(
                                    _fixed_boundary_symbol(
                                        runtime.token_piece_bytes(token_id)
                                    )
                                )
                            selected_id, selected_detail = _rerank_candidates(
                                rows,
                                scores,
                                symbols,
                                field_weight=effective_field_weight,
                            )
                        coverage_count += int(selected_detail["covered_count"])
                        candidate_count += int(selected_detail["candidate_count"])
                        collision_count += int(selected_detail["collision_count"])
                        unique_symbol_count += int(selected_detail["unique_symbols"])
                        field_score_span = float(selected_detail["field_score_span"])
                        field_score_span_sum += field_score_span
                        field_score_span_max = max(
                            field_score_span_max, field_score_span
                        )
                    if selected_id != baseline_id:
                        changed_tokens += 1
                    selected_piece = runtime.token_piece(selected_id)
                    token_position = current_position + 1
                    committed = runtime.decode_token(selected_id, token_position)
                    generated_ids.append(selected_id)
                    generated_pieces.append(selected_piece)
                    if mode == FIELD_MODE:
                        assert field_client is not None and daemon_session is not None
                        observed_symbol = _fixed_boundary_symbol(runtime.token_piece_bytes(selected_id))
                        if observed_symbol is not None:
                            field_client.correct(daemon_session, observed_symbol)
                            field_client.step(daemon_session, 1)
                            field_client.consolidate(daemon_session)
                        event_count += 1
                    current_record = committed
                    current_position = token_position
                    if runtime.token_is_eog(selected_id):
                        break
                checkpoint: dict[str, Any] = {}
                if mode == FIELD_MODE:
                    assert field_client is not None and daemon_session is not None
                    checkpoint = self._commit_field_checkpoint(
                        field_client,
                        daemon_session,
                        session,
                        prompt_sha256=prompt_sha256,
                        event_count=event_count,
                    )
                output = "".join(generated_pieces)
                response = {
                    "id": f"cassi-f5-{uuid.uuid4().hex}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": self.config.model_path.name,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": output},
                            "finish_reason": "length",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": len(prompt_ids),
                        "completion_tokens": len(generated_ids),
                        "total_tokens": len(prompt_ids) + len(generated_ids),
                    },
                    "cassi": {
                        "protocol": PROTOCOL,
                        "version": VERSION,
                        "profile": F5_PROFILE,
                        "mode": mode,
                        "field_execution": FIELD_DAEMON_PROTOCOL if mode == FIELD_MODE else "disabled",
                        "field_step": event_count if mode == FIELD_MODE else 0,
                        "field_hash": checkpoint.get("checkpoint_sha256") if mode == FIELD_MODE else None,
                        "teacher_event_count": teacher_events,
                        "candidate_coverage_count": coverage_count,
                        "candidate_count": candidate_count,
                        "candidate_collision_count": collision_count,
                        "candidate_unique_symbol_count": unique_symbol_count,
                        "candidate_coverage": coverage_count / float(candidate_count) if candidate_count else 0.0,
                        "candidate_collision": collision_count / float(candidate_count) if candidate_count else 0.0,
                        "candidate_field_score_span_mean": field_score_span_sum / float(teacher_events) if teacher_events else 0.0,
                        "candidate_field_score_span_max": field_score_span_max,
                        "selected_token_changes": changed_tokens,
                        "checkpoint_path": checkpoint.get("checkpoint_path"),
                        "checkpoint_sha256": checkpoint.get("checkpoint_sha256"),
                        "checkpoint_identity": checkpoint.get("checkpoint_identity"),
                        "field_config_fingerprint": checkpoint.get("field_config_fingerprint"),
                        "field_codebook_fingerprint": checkpoint.get("field_codebook_fingerprint"),
                        "qi": {
                            "available_event_count": qi_available_events,
                            "abstention_count": qi_abstention_count,
                            "availability_fraction": (
                                qi_available_events / float(teacher_events)
                                if teacher_events
                                else 0.0
                            ),
                            "q_mean": (
                                qi_metric_sums["q"] / float(teacher_events)
                                if teacher_events
                                else 0.0
                            ),
                            "chi_mean": (
                                qi_metric_sums["chi"] / float(teacher_events)
                                if teacher_events
                                else 0.0
                            ),
                            "cross_scale_coherence_mean": (
                                qi_metric_sums["cross_scale_coherence"]
                                / float(teacher_events)
                                if teacher_events
                                else 0.0
                            ),
                            "read_gate_mean": (
                                qi_metric_sums["read_gate"] / float(teacher_events)
                                if teacher_events
                                else 0.0
                            ),
                            "write_gate_mean": (
                                qi_metric_sums["write_gate"] / float(teacher_events)
                                if teacher_events
                                else 0.0
                            ),
                            "consolidation_gate_mean": (
                                qi_metric_sums["consolidation_gate"]
                                / float(teacher_events)
                                if teacher_events
                                else 0.0
                            ),
                            "j_temporal_mean": (
                                qi_metric_sums["j_temporal"] / float(teacher_events)
                                if teacher_events
                                else 0.0
                            ),
                            "j_scale_mean": (
                                qi_metric_sums["j_scale"] / float(teacher_events)
                                if teacher_events
                                else 0.0
                            ),
                            "effective_field_weight_mean": (
                                effective_field_weight_sum / float(teacher_events)
                                if teacher_events
                                else 0.0
                            ),
                            "effective_field_weight_max": effective_field_weight_max,
                        },
                        "persistence": {
                            "restored": bool(field_state.get("restored", False)),
                            "saved": mode == FIELD_MODE,
                            "event_count": event_count if mode == FIELD_MODE else 0,
                        },
                        "no_teacher_persistence": True,
                        "finite": True,
                    },
                }
                _finite_json(response, "completion response")
                return response
            except ProviderError:
                raise
            except (OSError, RuntimeError, TypeError, ValueError, KeyError) as exc:
                raise ProviderError(f"F5 generation failed: {type(exc).__name__}: {exc}", status=500) from exc
            finally:
                if field_client is not None:
                    field_client.close()


class _ProviderHandler(http.server.BaseHTTPRequestHandler):
    provider: CassiF5Provider

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[cassi-f5] {format % args}", flush=True)
    def _send_json(self, status: int, value: Mapping[str, Any]) -> None:
        _finite_json(value, "HTTP response")
        raw = (json.dumps(dict(value), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)

    def _send_stream(self, value: Mapping[str, Any]) -> None:
        choices = value.get("choices")
        content = ""
        if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
            message = choices[0].get("message")
            if isinstance(message, Mapping) and isinstance(message.get("content"), str):
                content = message["content"]
        stream_id = value.get("id", "cassi-f5-stream")
        chunks = [
            {"id": stream_id, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]},
            {"id": stream_id, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]},
            {"id": stream_id, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": value.get("choices", [{}])[0].get("finish_reason", "stop")}]},
        ]
        raw = b"".join(
            ("data: " + json.dumps(chunk, ensure_ascii=False, allow_nan=False) + "\n\n").encode("utf-8")
            for chunk in chunks
        ) + b"data: [DONE]\n\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path == "/health":
            self._send_json(200, self.provider.health())
        elif path == "/v1/models":
            self._send_json(200, self.provider.models())
        else:
            self._send_json(404, {"error": {"message": "not found", "type": "invalid_request_error"}})

    def do_POST(self) -> None:
        if urllib.parse.urlsplit(self.path).path != "/v1/chat/completions":
            self._send_json(404, {"error": {"message": "not found", "type": "invalid_request_error"}})
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ProviderError(f"request body must be 1..{MAX_REQUEST_BYTES} bytes")
            raw = self.rfile.read(length)
            request = json.loads(raw.decode("utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
            if not isinstance(request, dict):
                raise ProviderError("request JSON must be an object")
            response = self.provider.complete(request)
            if bool(request.get("stream", False)):
                self._send_stream(response)
            else:
                self._send_json(200, response)
        except ProviderError as exc:
            self._send_json(exc.status, {"error": {"message": str(exc), "type": "cassi_f5_provider_error"}})
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, OSError) as exc:
            self._send_json(400, {"error": {"message": str(exc), "type": "invalid_request_error"}})
        except Exception as exc:  # Keep the provider finite on unexpected errors.
            self._send_json(500, {"error": {"message": str(exc), "type": "cassi_f5_provider_error"}})


class _ThreadingHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True


def build_parser() -> argparse.ArgumentParser:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=here / "Qwen3.8-27B-Q4_K_M.gguf")
    parser.add_argument("--dll-dir", type=Path, default=here)
    parser.add_argument("--state-dir", type=Path, default=here / "_diag" / "f5-provider")
    parser.add_argument("--field-host", default=DEFAULT_FIELD_HOST)
    parser.add_argument("--field-port", type=int, default=DEFAULT_FIELD_PORT)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--context-size", type=int, default=128)
    parser.add_argument("--n-batch", type=int, default=64)
    parser.add_argument("--n-ubatch", type=int, default=64)
    parser.add_argument("--gpu-layers", type=int, default=99)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--field-weight", type=float, default=0.25)
    parser.add_argument("--layer-index", type=int, default=32)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--enable-f5", action="store_true", help="enable field mode; explicit cassi_field_mode=baseline remains available")
    return parser


def serve(args: argparse.Namespace) -> int:
    config = ProviderConfig(
        model_path=args.model,
        dll_dir=args.dll_dir,
        state_dir=args.state_dir,
        field_host=args.field_host,
        field_port=args.field_port,
        host=args.host,
        port=args.port,
        context_size=args.context_size,
        n_batch=args.n_batch,
        n_ubatch=args.n_ubatch,
        gpu_layers=args.gpu_layers,
        max_tokens=args.max_tokens,
        field_weight=args.field_weight,
        layer_index=args.layer_index,
        enable_f5=args.enable_f5,
        timeout_seconds=args.timeout_seconds,
    )
    provider = CassiF5Provider(config)
    provider.start()
    handler = type("CassiF5ProviderHandler", (_ProviderHandler,), {"provider": provider})
    server = _ThreadingHTTPServer((config.host, config.port), handler)
    print(
        json.dumps(
            {
                "provider": "ready",
                "protocol": PROTOCOL,
                "version": VERSION,
                "profile": F5_PROFILE,
                "host": config.host,
                "port": config.port,
                "field_host": config.field_host,
                "field_port": config.field_port,
                "field_enabled": config.enable_f5,
                "model": config.model_path.name,
            },
            ensure_ascii=False,
            allow_nan=False,
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
        provider.close()
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    try:
        return serve(build_parser().parse_args(list(argv) if argv is not None else None))
    except ProviderError as exc:
        print(json.dumps({"error": {"message": str(exc), "type": "cassi_f5_provider_error"}}), file=sys.stderr)
        return 2
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print(json.dumps({"error": {"message": str(exc), "type": "cassi_f5_provider_error"}}), file=sys.stderr)
        return 2


__all__ = [
    "BASELINE_MODE",
    "CassiF5Provider",
    "DEFAULT_FIELD_PORT",
    "DEFAULT_PORT",
    "F5FieldDaemonClient",
    "F5_PROFILE",
    "FIELD_MODE",
    "ProviderConfig",
    "ProviderError",
    "PROTOCOL",
    "TOP_K",
    "VERSION",
    "_fixed_boundary_symbol",
    "_rerank_candidates",
    "build_parser",
    "main",
    "serve",
]


if __name__ == "__main__":
    raise SystemExit(main())
