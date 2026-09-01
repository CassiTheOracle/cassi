"""Bounded local terminal conversation served only by the Qi field engine.

The live call graph is strictly field-native: a :class:`QiFieldController` and
:class:`CassiQiTextEngine` generate every reply, and the sole adaptive value
persisted across turns is one :class:`QiFieldState` through
:class:`CassiQiSessionStore`.  There are no learned models, organism arenas,
classical samplers, event ledgers, or separate adaptive state in this module.
"""
from __future__ import annotations

import hashlib
import json
import msvcrt
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

import torch
from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR

from cassi_field_language import CassiQiSessionStore, CassiQiTextEngine

from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldError, QiFieldState

CHAT_CONFIG_SCHEMA = "cassi.qi-native-chat-config.v2"
CHAT_TURN_SCHEMA = "cassi.qi-native-chat-turn.v2"
_PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = CONFIG_DIR / "conscious-chat.json"
DEFAULT_STATE_DIR = ARTIFACT_DIR / "cassi-qi-native" / "chat"

_MAX_TRANSCRIPT_MESSAGES = 24
_MAX_INPUT_BYTES_CEILING = 1 << 20


class CassiConsciousChatError(RuntimeError):
    """Raised when the bounded Qi-native terminal contract cannot complete."""


def _strict_object(value: object, name: str, expected: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CassiConsciousChatError(f"{name} must be a JSON object")
    unknown, missing = set(value) - expected, expected - set(value)
    if unknown or missing:
        raise CassiConsciousChatError(
            f"{name} keys mismatch: missing={sorted(missing)!r}, unknown={sorted(unknown)!r}"
        )
    return dict(value)


def _positive_int(name: str, value: object, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise CassiConsciousChatError(f"{name} must be an integer in 1..{maximum}")
    return value


@dataclass(frozen=True)
class CassiConsciousChatConfig:
    """Validated Qi-native terminal configuration (schema ``cassi.qi-native-chat-config.v2``)."""

    qi_config_path: Path
    corpus_checkpoint_path: Path
    state_dir: Path
    session_id: str
    max_output_symbols: int
    device: str
    max_input_bytes: int

    def __post_init__(self) -> None:
        _positive_int("max_output_symbols", self.max_output_symbols, 4096)
        _positive_int("max_input_bytes", self.max_input_bytes, _MAX_INPUT_BYTES_CEILING)
        if not isinstance(self.session_id, str) or not self.session_id:
            raise CassiConsciousChatError("session_id must be nonempty text")
        if not isinstance(self.device, str) or not self.device:
            raise CassiConsciousChatError("device must be nonempty text")

    @classmethod
    def load(cls, path: Path | str) -> "CassiConsciousChatConfig":
        source = Path(path)
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CassiConsciousChatError(f"chat configuration cannot be read: {error}") from error
        root = _strict_object(
            raw,
            "chat configuration",
            {
                "schema",
                "qi_config_path",
                "corpus_checkpoint_path",
                "state_dir",
                "session_id",
                "max_output_symbols",
                "device",
                "runtime",
            },
        )
        if root["schema"] != CHAT_CONFIG_SCHEMA:
            raise CassiConsciousChatError("chat configuration schema mismatch")
        qi_path = root["qi_config_path"]
        if not isinstance(qi_path, str) or not qi_path:
            raise CassiConsciousChatError("qi_config_path must be a nonempty path")
        qi_absolute = Path(qi_path)
        if not qi_absolute.is_absolute():
            qi_absolute = source.parent / qi_absolute
        try:
            qi_raw = json.loads(qi_absolute.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CassiConsciousChatError(f"qi_config_path cannot be read: {error}") from error
        try:
            QiFieldConfig.from_dict(qi_raw)
        except (QiFieldError, TypeError, ValueError) as error:
            raise CassiConsciousChatError(f"qi_config_path is invalid: {error}") from error
        checkpoint_path = root["corpus_checkpoint_path"]
        if not isinstance(checkpoint_path, str) or not checkpoint_path:
            raise CassiConsciousChatError("corpus_checkpoint_path must be a nonempty path")
        checkpoint_absolute = Path(checkpoint_path)
        if not checkpoint_absolute.is_absolute():
            checkpoint_absolute = source.parent / checkpoint_absolute
        if not checkpoint_absolute.is_file():
            raise CassiConsciousChatError("corpus_checkpoint_path does not exist")
        state_dir = root["state_dir"]
        if not isinstance(state_dir, str) or not state_dir:
            raise CassiConsciousChatError("state_dir must be a nonempty path")
        state_absolute = Path(state_dir)
        if not state_absolute.is_absolute():
            state_absolute = source.parent / state_absolute
        runtime_raw = _strict_object(root["runtime"], "runtime", {"max_input_bytes"})
        try:
            return cls(
                qi_config_path=qi_absolute,
                corpus_checkpoint_path=checkpoint_absolute,
                state_dir=state_absolute,
                session_id=str(root["session_id"]),
                max_output_symbols=_positive_int(
                    "max_output_symbols", root["max_output_symbols"], 4096
                ),
                device=str(root["device"]),
                max_input_bytes=_positive_int(
                    "max_input_bytes", runtime_raw["max_input_bytes"], _MAX_INPUT_BYTES_CEILING
                ),
            )
        except (TypeError, ValueError) as error:
            raise CassiConsciousChatError(f"chat configuration is invalid: {error}") from error


class StateDirectoryLock:
    """An OS-held single-byte Windows lock for one state directory."""

    def __init__(self, directory: Path | str) -> None:
        self.path = Path(directory) / "runtime.lock"
        self._handle: Any | None = None

    def acquire(self) -> None:
        if self._handle is not None:
            raise CassiConsciousChatError("state directory lock is already held")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle: Any | None = None
        try:
            handle = self.path.open("a+b")
            handle.seek(0)
            handle.write(b"0")
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except (OSError, ImportError) as error:
            if handle is not None:
                handle.close()
            raise CassiConsciousChatError(
                f"state directory is already in use: {self.path.parent}"
            ) from error
        self._handle = handle

    def close(self) -> None:
        if self._handle is None:
            return
        try:
            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "StateDirectoryLock":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


@dataclass(frozen=True)
class CassiChatTurn:
    """One Qi-native reply and its zero-classical-architecture ownership receipt."""

    reply: str
    reply_kind: str
    initial_state_sha256: str
    final_state_sha256: str
    output_bytes_sha256: str
    field_text_receipt_sha256: str
    corpus_memory_sha256: str
    trained_memory_preserved: bool
    next_sequence: int
    stop_reason: str
    utf8_valid: bool
    replacement_count: int
    session_id: str
    architecture: Mapping[str, Any]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": CHAT_TURN_SCHEMA,
            "status": "ok",
            "session_id": self.session_id,
            "reply": self.reply,
            "reply_kind": self.reply_kind,
            "stop_reason": self.stop_reason,
            "utf8_valid": self.utf8_valid,
            "replacement_count": self.replacement_count,
            "field_text_receipt_sha256": self.field_text_receipt_sha256,
            "corpus_memory_sha256": self.corpus_memory_sha256,
            "trained_memory_preserved": self.trained_memory_preserved,
            "output_bytes_sha256": self.output_bytes_sha256,
            "initial_state_sha256": self.initial_state_sha256,
            "final_state_sha256": self.final_state_sha256,
            "next_sequence": self.next_sequence,
            "architecture": dict(self.architecture),
            "ownership": {
                "field_owned": True,
                "live_qwen_dynamic_state": 0,
                "live_qwen_graph_executions": 0,
                "live_qwen_output_rows": 0,
                "live_qwen_weight_bytes_loaded": 0,
                "learned_parameter_count": 0,
                "neural_layer_count": 0,
                "optimizer_state_bytes": 0,
                "engineered_feature_width": 0,
                "probabilistic_sampler": False,
            },
        }


class CassiConsciousChatRuntime:
    """Exclusive durable terminal runtime over one field-owned Qi state."""

    def __init__(
        self,
        *,
        config: CassiConsciousChatConfig,
        controller: QiFieldController,
        engine: CassiQiTextEngine,
        store: CassiQiSessionStore,
        state: QiFieldState,
        messages: list[dict[str, str]],
        lock: StateDirectoryLock,
    ) -> None:
        self.config = config
        self.controller = controller
        self.engine = engine
        self.store = store
        self.state = state
        self.messages = messages
        self.lock = lock
        self._closed = False
        self._mutex = threading.RLock()

    @classmethod
    def open(
        cls,
        *,
        config_path: Path | str = DEFAULT_CONFIG_PATH,
        state_dir: Path | str | None = None,
        device: str | None = None,
        session_id: str | None = None,
        max_output_symbols: int | None = None,
    ) -> "CassiConsciousChatRuntime":
        config = CassiConsciousChatConfig.load(config_path)
        state_root = Path(state_dir) if state_dir is not None else config.state_dir
        device = device or config.device
        session_id = session_id or config.session_id
        max_output_symbols = (
            max_output_symbols if max_output_symbols is not None else config.max_output_symbols
        )
        config = replace(
            config,
            state_dir=state_root,
            device=device,
            session_id=session_id,
            max_output_symbols=max_output_symbols,
        )
        # Bounded small-tensor latency: pin this process to a single CPU thread.
        torch.set_num_threads(1)
        lock = StateDirectoryLock(state_root)
        lock.acquire()
        try:
            qi_raw = json.loads(config.qi_config_path.read_text(encoding="utf-8"))
            controller = QiFieldController(QiFieldConfig.from_dict(qi_raw))
            engine = CassiQiTextEngine(
                controller,
                checkpoint_path=config.corpus_checkpoint_path,
                max_output_symbols=max_output_symbols,
            )
            store = CassiQiSessionStore(
                state_root,
                controller,
                engine_fingerprint=engine.fingerprint,
            )
            loaded = store.load(session_id)
            if loaded is None:
                initial = engine.initial_state(device=torch.device(device))
                messages: list[dict[str, str]] = []
                store.save(session_id, initial, {"messages": messages})
                qi_state = initial
            else:
                qi_state, metadata, _path = loaded
                messages = list(metadata.get("messages", []))
            return cls(
                config=config,
                controller=controller,
                engine=engine,
                store=store,
                state=qi_state,
                messages=messages,
                lock=lock,
            )
        except Exception:
            lock.close()
            raise

    def close(self) -> None:
        with self._mutex:
            if self._closed:
                return
            self._closed = True
            self.lock.close()

    def __enter__(self) -> "CassiConsciousChatRuntime":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _require_open(self) -> None:
        if self._closed:
            raise CassiConsciousChatError("chat runtime is closed")

    def _validated_input(self, user_text: object) -> str:
        if not isinstance(user_text, str) or not user_text:
            raise CassiConsciousChatError("chat input must be nonempty text")
        try:
            payload = user_text.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise CassiConsciousChatError("chat input is not valid UTF-8") from error
        if len(payload) > self.config.max_input_bytes:
            raise CassiConsciousChatError("chat input exceeds the configured byte bound")
        return user_text

    def _next_sequence(self) -> int:
        return sum(1 for message in self.messages if message.get("role") == "user")


    def chat(self, user_text: object) -> CassiChatTurn:
        with self._mutex:
            self._require_open()
            text = self._validated_input(user_text)
            result = self.engine.generate(
                self.state,
                [{"role": "user", "content": text}],
                max_output_symbols=self.config.max_output_symbols,
            )
            reply, reply_kind = result.render_text(self.controller, len(text.encode("utf-8")))
            candidate_messages = [
                *self.messages,
                {"role": "user", "content": text},
                {"role": "assistant", "content": reply},
            ][-_MAX_TRANSCRIPT_MESSAGES:]
            self.store.save(
                self.config.session_id,
                result.state,
                {"messages": candidate_messages},
            )
            self.state = result.state
            self.messages = candidate_messages
            reply_bytes = reply.encode("utf-8")
            return CassiChatTurn(
                reply=reply,
                reply_kind=reply_kind,
                initial_state_sha256=result.initial_state_sha256,
                final_state_sha256=result.final_state_sha256,
                output_bytes_sha256=hashlib.sha256(reply_bytes).hexdigest(),
                field_text_receipt_sha256=result.receipt_sha256,
                corpus_memory_sha256=result.corpus_memory_sha256,
                trained_memory_preserved=(
                    result.corpus_memory_sha256 == self.engine.corpus_memory_sha256
                ),
                next_sequence=self._next_sequence(),
                stop_reason=result.stop_reason,
                utf8_valid=True,
                replacement_count=result.replacement_count if reply_kind == "field-symbols" else 0,
                session_id=self.config.session_id,
                architecture=result.receipt_dict()["architecture"],
            )


__all__ = [
    "CHAT_CONFIG_SCHEMA",
    "CHAT_TURN_SCHEMA",
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_STATE_DIR",
    "CassiChatTurn",
    "CassiConsciousChatConfig",
    "CassiConsciousChatError",
    "CassiConsciousChatRuntime",
    "StateDirectoryLock",
]
