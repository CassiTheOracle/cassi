"""Loopback OpenAI-compatible native-Qi CassiQwen provider.

The live server owns only one :class:`cassi_qi_field.QiFieldController` and one
:class:`cassi_field_language.CassiQiTextEngine`.  The sole adaptive persistent
object is :class:`cassi_qi_field.QiFieldState` laid out ``[S, 9M, B]``; new
sessions start from :meth:`CassiQiTextEngine.initial_state` and are persisted
through :class:`cassi_field_language.CassiQiSessionStore`.

Qwen, llama.cpp, GGUF, tokenizers, KV/recurrent state, native samplers, shadow
students, teacher traces, learned language heads, sampling/session seeds, and
organism checkpoints are intentionally unreachable from this module.  Every
completion commits a deterministic field successor and atomically checkpoints
that successor with a native-Qi displacement receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import math
import os
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

from cassi_field_language import (
    CassiFieldLanguageError,
    CassiQiSessionStore,
    CassiQiTextEngine,
)
from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldState
from cassi_qwen_displacement import (
    build_qi_native_displacement_receipt,
    load_qwen_displacement_baseline,
)


PROTOCOL = "CassiQwen native-Qi provider"
VERSION = 1
MODEL_NAME = "cassi-qi-language-v1"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8086
DEFAULT_MAX_OUTPUT_SYMBOLS = 2048
MAX_CONTEXT_MESSAGES = 128
MAX_SESSION_ID = 256
MAX_REQUEST_BYTES = 4 * 1024 * 1024


class ProviderError(RuntimeError):
    """A concrete provider/configuration/Qi failure."""


@dataclass(frozen=True)
class ProviderConfig:
    qi_config_path: Path
    baseline_receipt_path: Path
    state_dir: Path
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    max_output_symbols: int = DEFAULT_MAX_OUTPUT_SYMBOLS
    device: str = "cpu"

    def __post_init__(self) -> None:
        for name in ("qi_config_path", "baseline_receipt_path"):
            path = getattr(self, name)
            if not isinstance(path, Path) or not path.is_file():
                raise ProviderError(f"{name} must point to an existing file")
        if not isinstance(self.state_dir, Path):
            raise ProviderError("state_dir must be a pathlib.Path")
        if not isinstance(self.host, str) or not self.host:
            raise ProviderError("host must be nonempty")
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise ProviderError("port must be in [1, 65535]")
        if isinstance(self.max_output_symbols, bool) or not isinstance(self.max_output_symbols, int) or not 1 <= self.max_output_symbols <= 4096:
            raise ProviderError("max_output_symbols must be in [1, 4096]")


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ProviderError(f"value is not canonical JSON: {error}") from error


def _sha256(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise ProviderError(f"invalid JSON artifact: {path}") from error
    if not isinstance(value, dict):
        raise ProviderError(f"JSON artifact must be an object: {path}")
    return value


def _session_id(request: Mapping[str, Any]) -> str:
    value = request.get("user")
    metadata = request.get("metadata")
    if value is None and isinstance(metadata, Mapping):
        value = metadata.get("cassi_session_id")
    if value is None:
        return f"ephemeral-{uuid.uuid4().hex}"
    if not isinstance(value, str) or not value or len(value) > MAX_SESSION_ID:
        raise ProviderError("user/cassi_session_id must be bounded nonempty text")
    return value


def _validate_messages(messages: Any) -> None:
    if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)):
        raise ProviderError("messages must be a list")
    if not 1 <= len(messages) <= MAX_CONTEXT_MESSAGES:
        raise ProviderError(f"messages must contain 1..{MAX_CONTEXT_MESSAGES} entries")
    for index, message in enumerate(messages):
        if not isinstance(message, Mapping):
            raise ProviderError(f"message {index} must be an object")
        role, content = message.get("role"), message.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            raise ProviderError(f"message {index} requires string role/content")
        if role not in {"system", "user", "assistant"}:
            raise ProviderError(f"unsupported message role: {role!r}")


def _validate_determinism(request: Mapping[str, Any]) -> None:
    """Only the deterministic zero-temperature field path is accepted.

    Sampling parameters are unreachable in the native-Qi runtime: reject
    ``top_k``/``top_p`` and any nonzero temperature outright.  A session or
    request seed is likewise meaningless without a sampler.
    """
    temperature = request.get("temperature", 0.0)
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not math.isfinite(float(temperature)) or float(temperature) < 0:
        raise ProviderError("temperature must be a finite nonnegative number")
    if float(temperature) != 0.0:
        raise ProviderError("only deterministic temperature 0 is accepted; sampling is disabled")
    if "top_k" in request:
        raise ProviderError("top_k is not accepted; sampling is disabled")
    if "top_p" in request:
        raise ProviderError("top_p is not accepted; sampling is disabled")
    if "seed" in request or "cassi_session_seed" in request:
        raise ProviderError("sampling seeds are not accepted; the field path is fully deterministic")


class PersistentFieldProvider:
    """Hash-pinned native-Qi engine with deterministic per-session continuation."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.qi_config: QiFieldConfig | None = None
        self.baseline: Mapping[str, Any] | None = None
        self.controller: QiFieldController | None = None
        self.engine: CassiQiTextEngine | None = None
        self.store: CassiQiSessionStore | None = None
        self.initial_state: QiFieldState | None = None
        self._started = False
        self._lock = threading.RLock()
        self._session_locks: dict[str, threading.RLock] = {}

    @property
    def started(self) -> bool:
        return self._started

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            torch.set_num_threads(1)
            torch.set_num_interop_threads(1)
            qi_config = QiFieldConfig.from_dict(_load_json(self.config.qi_config_path))
            baseline = load_qwen_displacement_baseline(self.config.baseline_receipt_path)
            controller = QiFieldController(qi_config)
            engine = CassiQiTextEngine(controller, max_output_symbols=self.config.max_output_symbols)
            store = CassiQiSessionStore(self.config.state_dir, controller, engine_fingerprint=engine.fingerprint)
            self.qi_config = qi_config
            self.baseline = baseline
            self.controller = controller
            self.engine = engine
            self.store = store
            self.initial_state = engine.initial_state(device=self.config.device)
            self._started = True

    def close(self) -> None:
        with self._lock:
            self._started = False
            self.engine = None
            self.controller = None
            self.initial_state = None
            self.store = None

    def _session_lock(self, session_id: str) -> threading.RLock:
        with self._lock:
            return self._session_locks.setdefault(session_id, threading.RLock())

    def _require(self) -> tuple[QiFieldController, CassiQiTextEngine, Mapping[str, Any], QiFieldState, CassiQiSessionStore]:
        if (
            not self._started
            or self.controller is None
            or self.engine is None
            or self.baseline is None
            or self.initial_state is None
            or self.store is None
        ):
            raise ProviderError("persistent field provider is not started")
        return self.controller, self.engine, self.baseline, self.initial_state, self.store

    def _response(self, *, request_id: str, session_id: str, result: Any, displacement: Mapping[str, Any], checkpoint: Path, checkpoint_sha: str) -> dict[str, Any]:
        finish_reason = "length" if result.stop_reason == "max_output_symbols" else "stop"
        receipt = result.receipt_dict()
        return {
            "id": request_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": MODEL_NAME,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": result.text}, "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": len(result.prompt_symbols), "completion_tokens": len(result.output_symbols), "total_tokens": len(result.prompt_symbols) + len(result.output_symbols)},
            "cassi": {
                "protocol": PROTOCOL,
                "version": VERSION,
                "model": MODEL_NAME,
                "session_id": session_id,
                "request_id": request_id,
                "state_in_sha256": result.initial_state_sha256,
                "state_out_sha256": result.final_state_sha256,
                "stop_reason": result.stop_reason,
                "field_text_receipt": receipt,
                "field_text_receipt_sha256": result.receipt_sha256,
                "displacement_receipt": displacement,
                "displacement_receipt_sha256": displacement["receipt_sha256"],
                "checkpoint": str(checkpoint),
                "checkpoint_sha256": checkpoint_sha,
            },
        }

    def complete(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request, Mapping):
            raise ProviderError("completion request must be an object")
        requested_model = request.get("model", MODEL_NAME)
        if requested_model != MODEL_NAME:
            raise ProviderError(f"unsupported model: {requested_model!r}")
        _validate_messages(request.get("messages"))
        stream = request.get("stream", False)
        if not isinstance(stream, bool):
            raise ProviderError("stream must be boolean")
        _validate_determinism(request)
        controller, engine, baseline, initial, store = self._require()
        session_id = _session_id(request)
        request_id = request.get("id", f"cassi-{uuid.uuid4().hex}")
        if not isinstance(request_id, str) or not request_id or len(request_id) > MAX_SESSION_ID:
            raise ProviderError("request id must be bounded nonempty text")
        max_output = request.get("max_tokens", self.config.max_output_symbols)
        if isinstance(max_output, bool) or not isinstance(max_output, int) or not 1 <= max_output <= self.config.max_output_symbols:
            raise ProviderError("max_tokens exceeds the bounded field output limit")
        lock = self._session_lock(session_id)
        with lock:
            loaded = store.load(session_id)
            state = initial if loaded is None else loaded[0]
            try:
                result = engine.generate(state, request["messages"], max_output_symbols=max_output)
                displacement = build_qi_native_displacement_receipt(
                    baseline=baseline,
                    config_fingerprint=controller.config_fingerprint,
                    codebook_fingerprint=controller.codebook_fingerprint,
                    engine_fingerprint=engine.fingerprint,
                    field_text_receipt_sha256=result.receipt_sha256,
                    committed_output_count=len(result.output_symbols),
                )
                metadata = {
                    "protocol": PROTOCOL,
                    "version": VERSION,
                    "session_id": session_id,
                    "request_id": request_id,
                    "model": MODEL_NAME,
                    "state_in_sha256": result.initial_state_sha256,
                    "state_out_sha256": result.final_state_sha256,
                    "field_text_receipt": result.receipt_dict(),
                    "field_text_receipt_sha256": result.receipt_sha256,
                    "displacement_receipt": displacement,
                    "displacement_receipt_sha256": displacement["receipt_sha256"],
                    "messages_sha256": _sha256(request["messages"]),
                    "updated_at": int(time.time()),
                }
                checkpoint, checkpoint_sha = store.save(session_id, result.state, metadata)
            except ProviderError:
                raise
            except CassiFieldLanguageError as error:
                raise ProviderError(f"native-Qi generation/checkpoint failed; prior checkpoint retained: {error}") from error
            except Exception as error:
                raise ProviderError(f"native-Qi generation/checkpoint failed; prior checkpoint retained: {error}") from error
            return self._response(request_id=request_id, session_id=session_id, result=result, displacement=displacement, checkpoint=checkpoint, checkpoint_sha=checkpoint_sha)


class _Handler(http.server.BaseHTTPRequestHandler):
    provider: PersistentFieldProvider

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, status: int, value: Mapping[str, Any]) -> None:
        raw = _canonical(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/health":
            config = self.provider.qi_config
            self._send_json(200, {"ok": self.provider.started, "protocol": PROTOCOL, "version": VERSION, "model": MODEL_NAME, "field": True, "config_fingerprint": None if config is None else config.fingerprint})
        elif self.path == "/v1/models":
            self._send_json(200, {"object": "list", "data": [{"id": MODEL_NAME, "object": "model", "owned_by": "cassi-field"}]})
        else:
            self._send_json(404, {"error": {"message": "not found", "type": "invalid_request_error"}})

    def _stream(self, result: Mapping[str, Any]) -> None:
        choice = result["choices"][0]
        body = result["cassi"]
        chunks = [
            {"id": result["id"], "object": "chat.completion.chunk", "created": result["created"], "model": MODEL_NAME, "choices": [{"index": 0, "delta": {"role": "assistant", "content": choice["message"]["content"]}, "finish_reason": None}]},
            {"id": result["id"], "object": "chat.completion.chunk", "created": result["created"], "model": MODEL_NAME, "choices": [{"index": 0, "delta": {}, "finish_reason": choice["finish_reason"]}], "cassi": body},
        ]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        for chunk in chunks:
            self.wfile.write(b"data: " + _canonical(chunk) + b"\n\n")
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self._send_json(404, {"error": {"message": "not found", "type": "invalid_request_error"}})
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if length < 0 or length > MAX_REQUEST_BYTES:
                raise ProviderError("request body is missing or exceeds 4 MiB")
            request = json.loads(self.rfile.read(length), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
            if not isinstance(request, dict):
                raise ProviderError("request JSON must be an object")
            response = self.provider.complete(request)
            stream = request.get("stream", False)
            if stream:
                self._stream(response)
            else:
                self._send_json(200, response)
        except (ProviderError, ValueError, KeyError, TypeError) as error:
            self._send_json(400, {"error": {"message": str(error), "type": "invalid_request_error"}})
        except Exception as error:
            self._send_json(500, {"error": {"message": str(error), "type": "cassi_provider_error"}})


def build_parser() -> argparse.ArgumentParser:
    base = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qi-config", type=Path, default=base / "cassi-qi-language.json")
    parser.add_argument("--baseline-receipt", type=Path, default=base / "_diag" / "qwen-displacement" / "baseline-receipt.json")
    parser.add_argument("--state-dir", type=Path, default=base / "_diag" / "cassi-qi-native" / "provider-sessions")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--max-output-symbols", type=int, default=DEFAULT_MAX_OUTPUT_SYMBOLS)
    parser.add_argument("--device", default="cpu")
    return parser


def serve(config: ProviderConfig) -> None:
    provider = PersistentFieldProvider(config)
    provider.start()
    handler = type("CassiFieldProviderHandler", (_Handler,), {"provider": provider})
    server = http.server.ThreadingHTTPServer((config.host, config.port), handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        provider.close()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = ProviderConfig(
        qi_config_path=args.qi_config,
        baseline_receipt_path=args.baseline_receipt,
        state_dir=args.state_dir,
        host=args.host,
        port=args.port,
        max_output_symbols=args.max_output_symbols,
        device=args.device,
    )
    serve(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
