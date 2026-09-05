"""Loopback OpenAI-compatible provider for the native seven-pool Phi field."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import http.server
import json
import math
import os
import threading
import hmac
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from fractions import Fraction
from pathlib import Path
from typing import Any, Final

import torch
from cassi_canonical_runtime import (
    CanonicalActionJournal,
    CanonicalRuntimeError,
    FieldAgencyController,
    TransitionReceiptStore,
    receipt_payload,
)

from cassi_mnemic_condensation import (
    MnemicCondensationConfig,
    MnemicCondensationController,
)
from cassi_counterflow_runtime import DerivedCounterflowRuntime
from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR
from cassi_phi_harmonic_language import (
    PHI_HARMONIC_TEXT_RECEIPT_SCHEMA,
    PhiHarmonicLanguageConfig,
    PhiHarmonicLanguageController,
    PhiHarmonicTextEngine,
    PhiHarmonicTextResult,
)
from cassi_particle_program import (
    ParticleProgramError,
    compile_particle_program,
    normalize_program,
    program_digest,
)
from cassi_qi_world import (
    QiActionCommand,
    QiWorldError,
    QiWorldPort,
    QiWorldTickAck,
    QiWorldTickIntent,
)
from cassi_qi_field import QiFieldError, QiFieldState
from cassi_text_codec import CassiFieldLanguageError
from cassi_universal_data import (
    BoundaryIdentity,
    BoundaryPacket,
    BoundaryResult,
    CODEC_AUDIO,
    CODEC_CODE,
    CODEC_JSON,
    CODEC_OPAQUE,
    CODEC_RASTER,
    CODEC_TENSOR,
    CODEC_TEXT,
    JournalReference,
    ObservationView,
    QiIngressJournal,
    UniversalDataError,
    ZERO_SHA256,
    adapt,
    descriptor_sha256,
)

PROTOCOL = "Cassi Phi-harmonic field provider"
VERSION = 9
MODEL_NAME = "cassi-phi-harmonic-language-v1"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8086
DEFAULT_MAX_OUTPUT_SYMBOLS = 512
MAX_CONTEXT_MESSAGES = 128
MAX_SESSION_ID = 256
MAX_REQUEST_BYTES = 4 * 1024 * 1024
DEFAULT_INGRESS_MAX_BYTES = 64 * 1024 * 1024
LEGACY_PROVIDER_VERSION = 7
PREVIOUS_PROVIDER_VERSION = 8
LEGACY_SHARED_FIELD_SESSION_SCHEMA = "cassi.shared-field-provider-session.v3"
LEGACY_SHARED_FIELD_LAYOUT_SCHEMA = "cassi.shared-field-layout.v1"
LEGACY_CONTEXT_ASSOCIATION_FORMAT = "cassi.context.association.v2"
_INGRESS_REQUEST_METADATA_BYTES = 64 * 1024
MAX_INGRESS_REPLAY_ENTRIES = 1024
MAX_CONTEXT_CANDIDATES = 32
MAX_CONTEXT_QUERY_BYTES = 16 * 1024
MAX_CONTEXT_CANDIDATE_BYTES = 16 * 1024
MAX_CONTEXT_FEEDBACK_CANDIDATES = 8
MAX_CONTEXT_STREAMS = 16
MAX_CONTEXT_EVENT_BYTES = 256 * 1024
MAX_MNEMIC_RECALL_ADDRESSES = 65_536
MAX_SESSION_METADATA_BYTES = 3 * 1024 * 1024
EMPTY_CONTEXT_EVENT_ID = "0" * 64

PHI_PROVIDER_CONFIG_SCHEMA = "cassi.phi-harmonic-language-config.v1"
SHARED_FIELD_SESSION_SCHEMA = "cassi.shared-field-provider-session.v4"
SHARED_FIELD_LAYOUT_SCHEMA = "cassi.shared-field-layout.v2"
CONTEXT_STREAM_METADATA_KEY = "context_streams_v1"
COUNTERFLOW_COMMIT_METADATA_KEY = "counterflow_commits_v1"
WORLD_TURNS_METADATA_KEY = "particle_world_turns_v1"
WORLD_RESULTS_METADATA_KEY = "particle_world_results_v1"
WORLD_EXCHANGES_METADATA_KEY = "particle_world_exchanges_v1"
WORLD_LEDGER_LIMIT = 32
LAST_COMPLETION_METADATA_KEY = "last_completion_v1"
INGRESS_RECEIPT_SCHEMA = "cassi.provider.ingress-receipt.v1"
INGRESS_REPLAY_SCHEMA = "cassi.provider.ingress-replay.v1"
_INGRESS_CODECS: Final[tuple[str, ...]] = (
    CODEC_JSON,
    CODEC_RASTER,
    CODEC_TEXT,
    CODEC_CODE,
    CODEC_AUDIO,
    CODEC_TENSOR,
    CODEC_OPAQUE,
)
_INGRESS_CODEC_BY_DESCRIPTOR: Final[dict[str, str]] = {
    descriptor_sha256(codec_id): codec_id for codec_id in _INGRESS_CODECS
}
_INGRESS_REQUEST_KEYS: Final[frozenset[str]] = frozenset(
    {"codec_id", "packet", "payload_base64", "record_id"}
)
_INGRESS_PACKET_REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "run_id",
        "episode_id",
        "world_id",
        "session_id",
        "profile_sha256",
        "clock_sha256",
        "request_id",
        "logical_tick",
        "logical_time",
        "capture_start",
        "capture_end",
        "source_epoch",
        "source_stream_id",
        "source_sequence",
        "ingress_journal_sha256",
        "body_frame_id",
        "payload_shape",
        "payload_dtype",
    }
)
_INGRESS_PACKET_OPTIONAL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "source_timestamp_ns_telemetry",
        "arrival_sequence_telemetry",
        "watermark_sha256",
        "antialias_receipt_sha256",
        "causal_parent_event_id",
        "causal_parent_action_id",
        "valid",
    }
)
_JOURNAL_REFERENCE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "packet_sha256",
        "packet_object_sha256",
        "payload_manifest_sha256",
        "journal_head_sha256",
        "source_stream_id",
        "source_sequence",
    }
)

_SESSION_MAGIC: Final[bytes] = b"CASSI-SHARED-FIELD-SESSION\x00"
_SESSION_DIGEST_BYTES: Final[int] = hashlib.sha256().digest_size
_SESSION_HEADER_LIMIT: Final[int] = 64 * 1024
_SESSION_FILE_LIMIT: Final[int] = 64 * 1024 * 1024
_ALLOWED_METADATA_KEYS: Final[frozenset[str]] = frozenset(
    {
        CONTEXT_STREAM_METADATA_KEY,
        COUNTERFLOW_COMMIT_METADATA_KEY,
        LAST_COMPLETION_METADATA_KEY,
        WORLD_TURNS_METADATA_KEY,
        WORLD_RESULTS_METADATA_KEY,
        WORLD_EXCHANGES_METADATA_KEY,
    }
)
_TORCH_THREADS_CONFIGURED = False
_TORCH_THREADS_LOCK = threading.Lock()


class ProviderError(RuntimeError):
    """A concrete provider, persistence, or native-field failure."""


@dataclass(frozen=True)
class ProviderConfig:
    phi_config_path: Path
    corpus_checkpoint_path: Path
    state_dir: Path
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    max_output_symbols: int = DEFAULT_MAX_OUTPUT_SYMBOLS
    ingress_max_bytes: int = DEFAULT_INGRESS_MAX_BYTES
    device: str = "cpu"

    def __post_init__(self) -> None:
        object.__setattr__(self, "phi_config_path", Path(self.phi_config_path))
        object.__setattr__(
            self, "corpus_checkpoint_path", Path(self.corpus_checkpoint_path)
        )
        object.__setattr__(self, "state_dir", Path(self.state_dir))
        if self.host not in {"127.0.0.1", "localhost", "::1"}:
            raise ProviderError("the field provider must bind to loopback")
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise ProviderError("port must lie in [1, 65535]")
        if (
            isinstance(self.max_output_symbols, bool)
            or not isinstance(self.max_output_symbols, int)
            or not 1 <= self.max_output_symbols <= 4096
        ):
            raise ProviderError("max_output_symbols must lie in [1, 4096]")
        if (
            isinstance(self.ingress_max_bytes, bool)
            or not isinstance(self.ingress_max_bytes, int)
            or not 1 <= self.ingress_max_bytes <= DEFAULT_INGRESS_MAX_BYTES
        ):
            raise ProviderError(
                "ingress_max_bytes must lie in [1, 67108864]"
            )
        if not isinstance(self.device, str) or not self.device:
            raise ProviderError("device must be nonempty text")



def _javascript_json_numbers(value: Any) -> Any:
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [_javascript_json_numbers(item) for item in value]
    if isinstance(value, tuple):
        return [_javascript_json_numbers(item) for item in value]
    if isinstance(value, Mapping):
        return {
            key: _javascript_json_numbers(item)
            for key, item in value.items()
        }
    return value




def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            _javascript_json_numbers(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ProviderError(f"value is not canonical JSON: {error}") from error
def _sha256(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canonical(value)
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class SharedFieldLayout:
    """Fixed views of one canonical QiFieldState tensor."""

    phi_shape: tuple[int, int, int]
    counterflow_shape: tuple[int, int, int]
    mnemic_shape: tuple[int, int, int]

    def __post_init__(self) -> None:
        for name, shape in (
            ("phi_shape", self.phi_shape),
            ("counterflow_shape", self.counterflow_shape),
            ("mnemic_shape", self.mnemic_shape),
        ):
            if (
                not isinstance(shape, tuple)
                or len(shape) != 3
                or any(
                    isinstance(size, bool)
                    or not isinstance(size, int)
                    or size < 1
                    for size in shape
                )
                or shape[1] % 9 != 0
                or shape[2] != 1
            ):
                raise ProviderError(f"{name} must be a positive [S, 9*M, 1] shape")

    @classmethod
    def from_states(
        cls,
        phi: QiFieldState,
        counterflow: QiFieldState,
        mnemic: QiFieldState,
    ) -> "SharedFieldLayout":
        return cls(
            phi_shape=cls._state_shape(phi, label="Phi"),
            counterflow_shape=cls._state_shape(counterflow, label="counterflow"),
            mnemic_shape=cls._state_shape(mnemic, label="mnemic"),
        )

    @staticmethod
    def _state_shape(
        state: QiFieldState,
        *,
        label: str,
    ) -> tuple[int, int, int]:
        if not isinstance(state, QiFieldState) or not torch.is_tensor(state.field):
            raise ProviderError(f"{label} component must be a QiFieldState")
        if state.field.ndim != 3:
            raise ProviderError(f"{label} component must have three dimensions")
        shape = tuple(int(size) for size in state.field.shape)
        return (shape[0], shape[1], shape[2])

    @property
    def phi_size(self) -> int:
        return math.prod(self.phi_shape)

    @property
    def counterflow_size(self) -> int:
        return math.prod(self.counterflow_shape)

    @property
    def mnemic_size(self) -> int:
        return math.prod(self.mnemic_shape)

    @property
    def counterflow_offset(self) -> int:
        return self.phi_size

    @property
    def mnemic_offset(self) -> int:
        return self.phi_size + self.counterflow_size

    @property
    def shared_shape(self) -> tuple[int, int, int]:
        return (1, self.phi_size + self.counterflow_size + self.mnemic_size, 1)

    @property
    def legacy_shared_shape(self) -> tuple[int, int, int]:
        return (1, self.phi_size + self.counterflow_size, 1)

    @property
    def fingerprint(self) -> str:
        return _sha256(
            {
                "schema": SHARED_FIELD_LAYOUT_SCHEMA,
                "phi_shape": self.phi_shape,
                "counterflow_shape": self.counterflow_shape,
                "mnemic_shape": self.mnemic_shape,
                "packing": "flat-contiguous-phi-then-counterflow-then-mnemic",
            }
        )

    @property
    def legacy_fingerprint(self) -> str:
        return _sha256(
            {
                "schema": LEGACY_SHARED_FIELD_LAYOUT_SCHEMA,
                "phi_shape": self.phi_shape,
                "counterflow_shape": self.counterflow_shape,
                "packing": "flat-contiguous-phi-then-counterflow",
            }
        )

    def validate(self, state: QiFieldState) -> None:
        if not isinstance(state, QiFieldState) or not torch.is_tensor(state.field):
            raise ProviderError("shared state must be a QiFieldState")
        if (
            state.field.layout != torch.strided
            or tuple(state.field.shape) != self.shared_shape
            or not state.field.is_contiguous()
            or state.field.dtype not in (torch.float32, torch.float64)
        ):
            raise ProviderError(
                f"shared field must be contiguous {self.shared_shape} float32 or float64"
            )
        if not bool(torch.isfinite(state.field).all().item()):
            raise ProviderError("shared field contains non-finite values")

    def validate_legacy(self, state: QiFieldState) -> None:
        if not isinstance(state, QiFieldState) or not torch.is_tensor(state.field):
            raise ProviderError("legacy shared state must be a QiFieldState")
        if (
            state.field.layout != torch.strided
            or tuple(state.field.shape) != self.legacy_shared_shape
            or not state.field.is_contiguous()
            or state.field.dtype not in (torch.float32, torch.float64)
        ):
            raise ProviderError(
                "legacy shared field must be contiguous "
                f"{self.legacy_shared_shape} float32 or float64"
            )
        if not bool(torch.isfinite(state.field).all().item()):
            raise ProviderError("legacy shared field contains non-finite values")

    @staticmethod
    def _validate_component(
        component: QiFieldState,
        shape: tuple[int, int, int],
        shared: QiFieldState | None = None,
    ) -> None:
        if (
            not isinstance(component, QiFieldState)
            or not torch.is_tensor(component.field)
            or tuple(component.field.shape) != shape
            or component.field.dtype not in (torch.float32, torch.float64)
            or not bool(torch.isfinite(component.field).all().item())
        ):
            raise ProviderError(f"field component must be finite with shape {shape}")
        if shared is not None and (
            component.field.device != shared.field.device
            or component.field.dtype != shared.field.dtype
        ):
            raise ProviderError("field component device or dtype does not match shared state")

    def join(
        self,
        phi: QiFieldState,
        counterflow: QiFieldState,
        mnemic: QiFieldState,
    ) -> QiFieldState:
        self._validate_component(phi, self.phi_shape)
        self._validate_component(counterflow, self.counterflow_shape)
        self._validate_component(mnemic, self.mnemic_shape)
        if (
            phi.field.device != counterflow.field.device
            or phi.field.device != mnemic.field.device
            or phi.field.dtype != counterflow.field.dtype
            or phi.field.dtype != mnemic.field.dtype
        ):
            raise ProviderError("field components must share one device and dtype")
        state = QiFieldState(
            field=torch.cat(
                (
                    phi.field.reshape(-1),
                    counterflow.field.reshape(-1),
                    mnemic.field.reshape(-1),
                )
            ).reshape(self.shared_shape)
        )
        self.validate(state)
        return state

    def legacy_join(
        self,
        phi: QiFieldState,
        counterflow: QiFieldState,
    ) -> QiFieldState:
        self._validate_component(phi, self.phi_shape)
        self._validate_component(counterflow, self.counterflow_shape)
        if (
            phi.field.device != counterflow.field.device
            or phi.field.dtype != counterflow.field.dtype
        ):
            raise ProviderError("legacy field components must share one device and dtype")
        state = QiFieldState(
            field=torch.cat(
                (phi.field.reshape(-1), counterflow.field.reshape(-1))
            ).reshape(self.legacy_shared_shape)
        )
        self.validate_legacy(state)
        return state

    def _component(
        self,
        state: QiFieldState,
        *,
        offset: int,
        shape: tuple[int, int, int],
    ) -> QiFieldState:
        self.validate(state)
        return QiFieldState(
            field=state.field.reshape(-1).narrow(0, offset, math.prod(shape)).view(shape)
        )

    def phi(self, state: QiFieldState) -> QiFieldState:
        return self._component(state, offset=0, shape=self.phi_shape)

    def counterflow(self, state: QiFieldState) -> QiFieldState:
        return self._component(
            state,
            offset=self.counterflow_offset,
            shape=self.counterflow_shape,
        )

    def mnemic(self, state: QiFieldState) -> QiFieldState:
        return self._component(
            state,
            offset=self.mnemic_offset,
            shape=self.mnemic_shape,
        )

    def legacy_phi(self, state: QiFieldState) -> QiFieldState:
        self.validate_legacy(state)
        return QiFieldState(
            field=state.field.reshape(-1).narrow(0, 0, self.phi_size).view(
                self.phi_shape
            )
        )

    def legacy_counterflow(self, state: QiFieldState) -> QiFieldState:
        self.validate_legacy(state)
        return QiFieldState(
            field=state.field.reshape(-1).narrow(
                0,
                self.counterflow_offset,
                self.counterflow_size,
            ).view(self.counterflow_shape)
        )

    def _replace(
        self,
        state: QiFieldState,
        component: QiFieldState,
        *,
        offset: int,
        shape: tuple[int, int, int],
    ) -> QiFieldState:
        self.validate(state)
        self._validate_component(component, shape, state)
        field = state.field.clone()
        field.reshape(-1).narrow(0, offset, math.prod(shape)).copy_(
            component.field.reshape(-1)
        )
        return QiFieldState(field=field)

    def with_phi(
        self,
        state: QiFieldState,
        phi: QiFieldState,
    ) -> QiFieldState:
        return self._replace(state, phi, offset=0, shape=self.phi_shape)

    def with_counterflow(
        self,
        state: QiFieldState,
        counterflow: QiFieldState,
    ) -> QiFieldState:
        return self._replace(
            state,
            counterflow,
            offset=self.counterflow_offset,
            shape=self.counterflow_shape,
        )

    def with_mnemic(
        self,
        state: QiFieldState,
        mnemic: QiFieldState,
    ) -> QiFieldState:
        return self._replace(
            state,
            mnemic,
            offset=self.mnemic_offset,
            shape=self.mnemic_shape,
        )

    def state_sha256(self, state: QiFieldState) -> str:
        self.validate(state)
        owned = state.field.detach().cpu().contiguous()
        digest = hashlib.sha256(
            _canonical(
                {
                    "layout_fingerprint": self.fingerprint,
                    "dtype": str(owned.dtype),
                    "shape": tuple(owned.shape),
                }
            )
        )
        digest.update(b"\x00")
        digest.update(owned.numpy().tobytes(order="C"))
        return digest.hexdigest()

    def legacy_state_sha256(self, state: QiFieldState) -> str:
        self.validate_legacy(state)
        owned = state.field.detach().cpu().contiguous()
        digest = hashlib.sha256(
            _canonical(
                {
                    "layout_fingerprint": self.legacy_fingerprint,
                    "dtype": str(owned.dtype),
                    "shape": tuple(owned.shape),
                }
            )
        )
        digest.update(b"\x00")
        digest.update(owned.numpy().tobytes(order="C"))
        return digest.hexdigest()


def _is_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderError(f"could not read {path}: {error}") from error
    if not isinstance(value, dict):
        raise ProviderError(f"{path} must contain a JSON object")
    return value


def _load_phi_config(path: Path) -> PhiHarmonicLanguageConfig:
    value = _load_json(path)
    schema = value.pop("schema", None)
    expected = {field.name for field in fields(PhiHarmonicLanguageConfig)}
    if schema != PHI_PROVIDER_CONFIG_SCHEMA or set(value) != expected:
        raise ProviderError("Phi language config schema or key set is invalid")
    try:
        return PhiHarmonicLanguageConfig(**value)
    except (QiFieldError, TypeError, ValueError) as error:
        raise ProviderError(f"Phi language config is invalid: {error}") from error


def _session_id(request: Mapping[str, Any]) -> str:
    value = request.get("user")
    if value is None:
        metadata = request.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ProviderError("metadata must be an object")
        value = metadata.get("cassi_session_id")
    if value is None:
        value = f"ephemeral-{uuid.uuid4().hex}"
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > MAX_SESSION_ID
    ):
        raise ProviderError("session id must be bounded nonempty UTF-8 text")
    return value


def _validate_messages(messages: Any) -> None:
    if (
        not isinstance(messages, Sequence)
        or isinstance(messages, (str, bytes, bytearray))
        or not 1 <= len(messages) <= MAX_CONTEXT_MESSAGES
    ):
        raise ProviderError(
            f"messages must contain 1..{MAX_CONTEXT_MESSAGES} entries"
        )
    for index, message in enumerate(messages):
        if not isinstance(message, Mapping):
            raise ProviderError(f"message {index} must be an object")
        if set(message) != {"role", "content"}:
            raise ProviderError(f"message {index} must contain only role/content")
        if message.get("role") not in {"system", "user", "assistant"} or not isinstance(
            message.get("content"), str
        ):
            raise ProviderError(f"message {index} has invalid role/content")
    if messages[-1].get("role") != "user":
        raise ProviderError("the final message must have role 'user'")


def _validate_determinism(request: Mapping[str, Any]) -> None:
    temperature = request.get("temperature", 0)
    if (
        isinstance(temperature, bool)
        or not isinstance(temperature, (int, float))
        or not math.isfinite(float(temperature))
        or float(temperature) != 0.0
    ):
        raise ProviderError("temperature must be exactly 0")
    for key in ("top_k", "top_p", "seed", "cassi_session_seed"):
        if key in request:
            raise ProviderError(
                "sampling controls are not accepted; the field path is deterministic"
            )


def _validate_completion_metadata(value: Any) -> dict[str, Any]:
    expected_keys = {
        "protocol",
        "version",
        "model",
        "session_id",
        "request_id",
        "messages_sha256",
        "state_in_sha256",
        "state_out_sha256",
        "field_text_receipt",
        "field_text_receipt_sha256",
        "output_bytes_sha256",
        "updated_at",
    }
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise ProviderError("stored completion metadata has an invalid key set")
    if (
        value.get("protocol") != PROTOCOL
        or value.get("version") != VERSION
        or value.get("model") != MODEL_NAME
    ):
        raise ProviderError("stored completion metadata identity is invalid")
    for key in ("session_id", "request_id"):
        text = value.get(key)
        if (
            not isinstance(text, str)
            or not text
            or len(text.encode("utf-8")) > MAX_SESSION_ID
        ):
            raise ProviderError(f"stored completion {key} is invalid")
    for key in (
        "messages_sha256",
        "state_in_sha256",
        "state_out_sha256",
        "field_text_receipt_sha256",
        "output_bytes_sha256",
    ):
        if not _is_digest(value.get(key)):
            raise ProviderError(f"stored completion {key} is invalid")
    updated_at = value.get("updated_at")
    if (
        isinstance(updated_at, bool)
        or not isinstance(updated_at, int)
        or updated_at < 0
    ):
        raise ProviderError("stored completion timestamp is invalid")

    receipt_value = value.get("field_text_receipt")
    receipt_keys = {
        "schema",
        "engine_fingerprint",
        "initial_state_sha256",
        "final_state_sha256",
        "tape_sha256",
        "prompt_symbols",
        "output_symbols",
        "reply_sha256",
        "stop_reason",
    }
    if not isinstance(receipt_value, Mapping) or set(receipt_value) != receipt_keys:
        raise ProviderError("stored field text receipt has an invalid key set")
    receipt = dict(receipt_value)
    if receipt.get("schema") != PHI_HARMONIC_TEXT_RECEIPT_SCHEMA:
        raise ProviderError("stored field text receipt schema is invalid")
    for key in (
        "engine_fingerprint",
        "initial_state_sha256",
        "final_state_sha256",
        "tape_sha256",
        "reply_sha256",
    ):
        if not _is_digest(receipt.get(key)):
            raise ProviderError(f"stored field text receipt {key} is invalid")
    if (
        receipt["initial_state_sha256"] != value["state_in_sha256"]
        or receipt["final_state_sha256"] != value["state_out_sha256"]
    ):
        raise ProviderError("stored completion state lineage is inconsistent")
    for key, maximum in (
        ("prompt_symbols", MAX_REQUEST_BYTES),
        ("output_symbols", 4097),
    ):
        symbols = receipt.get(key)
        if (
            not isinstance(symbols, list)
            or len(symbols) > maximum
            or any(
                isinstance(symbol, bool)
                or not isinstance(symbol, int)
                or not 0 <= symbol < 260
                for symbol in symbols
            )
        ):
            raise ProviderError(f"stored field text receipt {key} is invalid")
        receipt[key] = list(symbols)
    if receipt.get("stop_reason") not in {"end_turn", "max_output_symbols"}:
        raise ProviderError("stored field text stop reason is invalid")
    if receipt["reply_sha256"] != value["output_bytes_sha256"]:
        raise ProviderError("stored completion output hash is inconsistent")
    if _sha256(receipt) != value["field_text_receipt_sha256"]:
        raise ProviderError("stored field text receipt hash is inconsistent")
    normalized = dict(value)
    normalized["field_text_receipt"] = receipt
    if len(_canonical(normalized)) > MAX_SESSION_METADATA_BYTES:
        raise ProviderError("stored completion metadata exceeds the bounded limit")
    return normalized


def _normalize_stream_watermarks(value: Any, *, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping) or len(value) > MAX_CONTEXT_STREAMS:
        raise ProviderError(f"stored {label} streams are malformed or over limit")
    streams: dict[str, dict[str, Any]] = {}
    for raw_stream_id, raw_watermark in value.items():
        stream_id = PersistentFieldProvider._validate_stream_id(raw_stream_id)
        if (
            not isinstance(raw_watermark, Mapping)
            or set(raw_watermark) != {"sequence", "event_id"}
        ):
            raise ProviderError(f"stored {label} stream watermark is malformed")
        sequence = raw_watermark.get("sequence")
        event_id = raw_watermark.get("event_id")
        if (
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence < 1
            or not _is_digest(event_id)
        ):
            raise ProviderError(f"stored {label} stream watermark is malformed")
        streams[stream_id] = {
            "sequence": sequence,
            "event_id": str(event_id),
        }
    return streams


def _normalize_world_ledger(value: Any, *, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping) or len(value) > WORLD_LEDGER_LIMIT:
        raise ProviderError(f"stored {label} ledger is malformed or over limit")
    ledger: dict[str, dict[str, Any]] = {}
    for request_id, entry in value.items():
        if (
            not isinstance(request_id, str)
            or not 1 <= len(request_id) <= 128
            or any(
                character
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-"
                for character in request_id
            )
            or not isinstance(entry, Mapping)
        ):
            raise ProviderError(f"stored {label} ledger entry is malformed")
        normalized_entry = dict(entry)
        if len(_canonical(normalized_entry)) > 128 * 1024:
            raise ProviderError(f"stored {label} ledger entry exceeds the limit")
        ledger[request_id] = normalized_entry
    return ledger


def _metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    result = {} if value is None else dict(value)
    unexpected = set(result) - _ALLOWED_METADATA_KEYS
    if unexpected:
        raise ProviderError(
            f"session metadata contains unsupported keys: {sorted(unexpected)}"
        )

    streams = _normalize_stream_watermarks(
        result.get(CONTEXT_STREAM_METADATA_KEY, {}),
        label="context",
    )
    counterflow_commits = _normalize_stream_watermarks(
        result.get(COUNTERFLOW_COMMIT_METADATA_KEY, {}),
        label="counterflow commit",
    )

    completion_value = result.get(LAST_COMPLETION_METADATA_KEY)
    completion = (
        None
        if completion_value is None
        else _validate_completion_metadata(completion_value)
    )
    world_turns = _normalize_world_ledger(
        result.get(WORLD_TURNS_METADATA_KEY, {}), label="world turn"
    )
    world_results = _normalize_world_ledger(
        result.get(WORLD_RESULTS_METADATA_KEY, {}), label="world result"
    )
    world_exchanges = _normalize_world_ledger(
        result.get(WORLD_EXCHANGES_METADATA_KEY, {}), label="world exchange"
    )
    normalized: dict[str, Any] = {CONTEXT_STREAM_METADATA_KEY: streams}
    if counterflow_commits:
        normalized[COUNTERFLOW_COMMIT_METADATA_KEY] = counterflow_commits
    if completion is not None:
        normalized[LAST_COMPLETION_METADATA_KEY] = completion
    if world_turns:
        normalized[WORLD_TURNS_METADATA_KEY] = world_turns
    if world_results:
        normalized[WORLD_RESULTS_METADATA_KEY] = world_results
    if world_exchanges:
        normalized[WORLD_EXCHANGES_METADATA_KEY] = world_exchanges
    if len(_canonical(normalized)) > MAX_SESSION_METADATA_BYTES:
        raise ProviderError("session metadata exceeds the bounded limit")
    return normalized


class SharedFieldSessionStore:
    """Atomic storage for one versioned native QiFieldState."""

    def __init__(
        self,
        root: Path,
        controller: PhiHarmonicLanguageController,
        counterflow_runtime: DerivedCounterflowRuntime,
        mnemic_controller: MnemicCondensationController,
        initial_mnemic_state: QiFieldState,
        layout: SharedFieldLayout,
        *,
        provider_fingerprint: str,
        previous_provider_fingerprint: str,
        legacy_provider_fingerprint: str,
        engine_fingerprint: str,
        device: torch.device,
    ) -> None:
        if not _is_digest(provider_fingerprint):
            raise ProviderError("provider fingerprint must be a SHA-256 digest")
        if not _is_digest(previous_provider_fingerprint):
            raise ProviderError("previous provider fingerprint must be a SHA-256 digest")
        if not _is_digest(legacy_provider_fingerprint):
            raise ProviderError("legacy provider fingerprint must be a SHA-256 digest")
        if not _is_digest(engine_fingerprint):
            raise ProviderError("engine fingerprint must be a SHA-256 digest")
        if not isinstance(layout, SharedFieldLayout):
            raise ProviderError("layout must be a SharedFieldLayout")
        try:
            mnemic_controller.validate_state(initial_mnemic_state)
        except QiFieldError as error:
            raise ProviderError(f"initial mnemic field is invalid: {error}") from error
        self.root = Path(root)
        self.controller = controller
        self.provider_fingerprint = provider_fingerprint
        self.previous_provider_fingerprint = previous_provider_fingerprint
        self.legacy_provider_fingerprint = legacy_provider_fingerprint
        self.engine_fingerprint = engine_fingerprint
        self.counterflow_runtime = counterflow_runtime
        self.initial_counterflow_state = counterflow_runtime.initial_state()
        self.mnemic_controller = mnemic_controller
        self.initial_mnemic_state = initial_mnemic_state.clone()
        self.layout = layout
        self.device = device
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_session_id(session_id: str) -> str:
        if (
            not isinstance(session_id, str)
            or not session_id
            or len(session_id.encode("utf-8")) > MAX_SESSION_ID
        ):
            raise ProviderError("session id must be bounded nonempty UTF-8 text")
        return session_id

    def _validate_metadata_identity(
        self, session_id: str, metadata: Mapping[str, Any]
    ) -> None:
        completion = metadata.get(LAST_COMPLETION_METADATA_KEY)
        if completion is None:
            return
        if (
            not isinstance(completion, Mapping)
            or completion.get("session_id") != session_id
        ):
            raise ProviderError("stored completion session identity mismatch")
        receipt = completion.get("field_text_receipt")
        if (
            not isinstance(receipt, Mapping)
            or receipt.get("engine_fingerprint") != self.engine_fingerprint
        ):
            raise ProviderError("stored completion engine identity mismatch")

    def path_for(self, session_id: str) -> Path:
        value = self._validate_session_id(session_id)
        return self.root / f"{hashlib.sha256(value.encode('utf-8')).hexdigest()}.pt"

    @staticmethod
    def _decode_frame(raw: bytes) -> tuple[dict[str, Any], bytes, bytes]:
        minimum = len(_SESSION_MAGIC) + 8 + _SESSION_DIGEST_BYTES
        if len(raw) < minimum or not raw.startswith(_SESSION_MAGIC):
            raise ProviderError("shared field session frame is invalid")
        offset = len(_SESSION_MAGIC)
        header_length = int.from_bytes(raw[offset : offset + 8], "big")
        if not 1 <= header_length <= _SESSION_HEADER_LIMIT:
            raise ProviderError("shared field session header length is invalid")
        header_start = offset + 8
        header_end = header_start + header_length
        if header_end > len(raw) - _SESSION_DIGEST_BYTES:
            raise ProviderError("shared field session frame is truncated")
        try:
            header = json.loads(raw[header_start:header_end].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProviderError(f"shared field session header is invalid: {error}") from error
        current_keys = {
            "codebook_fingerprint",
            "config_fingerprint",
            "counterflow_config_fingerprint",
            "counterflow_state_sha256",
            "mnemic_config_fingerprint",
            "mnemic_state_sha256",
            "field_bytes",
            "field_dtype",
            "field_payload_sha256",
            "field_shape",
            "layout_fingerprint",
            "metadata_bytes",
            "metadata_sha256",
            "phi_state_sha256",
            "provider_fingerprint",
            "schema",
            "session_id",
            "shared_state_sha256",
        }
        legacy_keys = current_keys - {
            "mnemic_config_fingerprint",
            "mnemic_state_sha256",
        }
        if not isinstance(header, dict):
            raise ProviderError("shared field session header must be an object")
        expected_keys = (
            current_keys
            if header.get("schema") == SHARED_FIELD_SESSION_SCHEMA
            else legacy_keys
            if header.get("schema") == LEGACY_SHARED_FIELD_SESSION_SCHEMA
            else set()
        )
        if set(header) != expected_keys:
            raise ProviderError("shared field session header key set is invalid")
        field_length = header.get("field_bytes")
        metadata_length = header.get("metadata_bytes")
        if (
            isinstance(field_length, bool)
            or not isinstance(field_length, int)
            or field_length < 1
            or isinstance(metadata_length, bool)
            or not isinstance(metadata_length, int)
            or not 2 <= metadata_length <= MAX_SESSION_METADATA_BYTES
        ):
            raise ProviderError("shared field session payload lengths are invalid")
        field_end = header_end + field_length
        metadata_end = field_end + metadata_length
        if len(raw) != metadata_end + _SESSION_DIGEST_BYTES:
            raise ProviderError("shared field session exact frame length is invalid")
        body = raw[:metadata_end]
        if hashlib.sha256(body).digest() != raw[metadata_end:]:
            raise ProviderError("shared field session frame checksum mismatch")
        field_payload = raw[header_end:field_end]
        metadata_payload = raw[field_end:metadata_end]
        if _sha256(field_payload) != header.get("field_payload_sha256"):
            raise ProviderError("shared field payload checksum mismatch")
        if _sha256(metadata_payload) != header.get("metadata_sha256"):
            raise ProviderError("shared field metadata checksum mismatch")
        return header, field_payload, metadata_payload

    def inspect(self, session_id: str) -> tuple[Path, str, str]:
        path = self.path_for(session_id)
        try:
            if path.stat().st_size > _SESSION_FILE_LIMIT:
                raise ProviderError("session checkpoint exceeds the bounded limit")
            raw = path.read_bytes()
        except OSError as error:
            raise ProviderError(f"could not read session checkpoint: {error}") from error
        header, _, _ = self._decode_frame(raw)
        fingerprint = header.get("provider_fingerprint")
        if not _is_digest(fingerprint):
            raise ProviderError("session checkpoint engine identity is invalid")
        return path, _sha256(raw), str(fingerprint)


    def is_compatible_provider_fingerprint(self, value: str) -> bool:
        return value in {
            self.provider_fingerprint,
            self.previous_provider_fingerprint,
            self.legacy_provider_fingerprint,
        }
    def initial(self, phi: QiFieldState) -> QiFieldState:
        return self.layout.join(
            phi,
            QiFieldState(field=self.initial_counterflow_state.field.clone()),
            self.initial_mnemic_state.clone(),
        )

    def load(
        self, session_id: str
    ) -> tuple[QiFieldState, dict[str, Any], Path, str] | None:
        path = self.path_for(session_id)
        if not path.is_file():
            return None
        try:
            if path.stat().st_size > _SESSION_FILE_LIMIT:
                raise ProviderError("session checkpoint exceeds the bounded limit")
            raw = path.read_bytes()
        except OSError as error:
            raise ProviderError(f"could not read session checkpoint: {error}") from error
        header, field_payload, metadata_payload = self._decode_frame(raw)
        schema = header.get("schema")
        legacy = schema == LEGACY_SHARED_FIELD_SESSION_SCHEMA
        if schema not in {
            SHARED_FIELD_SESSION_SCHEMA,
            LEGACY_SHARED_FIELD_SESSION_SCHEMA,
        }:
            raise ProviderError("shared field session schema mismatch")
        if header.get("session_id") != session_id:
            raise ProviderError("shared field session identity mismatch")
        actual_provider_fingerprint = header.get("provider_fingerprint")
        if legacy:
            compatible_provider_fingerprints = {self.legacy_provider_fingerprint}
        else:
            compatible_provider_fingerprints = {
                self.provider_fingerprint,
                self.previous_provider_fingerprint,
            }
        if actual_provider_fingerprint not in compatible_provider_fingerprints:
            raise ProviderError("shared field session provider fingerprint mismatch")
        if header.get("config_fingerprint") != self.controller.config_fingerprint:
            raise ProviderError("Phi component config fingerprint mismatch")
        if header.get("codebook_fingerprint") != self.controller.codebook_fingerprint:
            raise ProviderError("Phi component codebook fingerprint mismatch")
        if (
            header.get("counterflow_config_fingerprint")
            != self.counterflow_runtime.config_fingerprint
        ):
            raise ProviderError("counterflow component config fingerprint mismatch")
        if not legacy and (
            header.get("mnemic_config_fingerprint")
            != self.mnemic_controller.config_fingerprint
        ):
            raise ProviderError("mnemic component config fingerprint mismatch")
        expected_layout_fingerprint = (
            self.layout.legacy_fingerprint if legacy else self.layout.fingerprint
        )
        expected_shape = (
            self.layout.legacy_shared_shape
            if legacy
            else self.layout.shared_shape
        )
        if header.get("layout_fingerprint") != expected_layout_fingerprint:
            raise ProviderError("shared field layout fingerprint mismatch")
        if header.get("field_shape") != list(expected_shape):
            raise ProviderError("shared field shape mismatch")
        dtype_name = header.get("field_dtype")
        if not isinstance(dtype_name, str):
            raise ProviderError("shared field dtype is invalid")
        dtype = {
            "torch.float32": torch.float32,
            "torch.float64": torch.float64,
        }.get(dtype_name)
        if dtype is None:
            raise ProviderError("shared field dtype is invalid")
        expected_bytes = math.prod(expected_shape) * torch.empty(
            (), dtype=dtype
        ).element_size()
        if len(field_payload) != expected_bytes:
            raise ProviderError("shared field payload length is invalid")
        try:
            decoded_metadata = json.loads(metadata_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProviderError(f"shared field metadata is invalid: {error}") from error
        if not isinstance(decoded_metadata, dict):
            raise ProviderError("shared field metadata must be an object")
        try:
            field = (
                torch.frombuffer(bytearray(field_payload), dtype=dtype)
                .clone()
                .reshape(expected_shape)
                .to(self.device)
            )
            packed = QiFieldState(field=field)
            if legacy:
                self.layout.validate_legacy(packed)
                phi = self.layout.legacy_phi(packed)
                counterflow = self.layout.legacy_counterflow(packed)
                packed_sha256 = self.layout.legacy_state_sha256(packed)
                initial_mnemic = QiFieldState(
                    field=self.initial_mnemic_state.field.to(
                        device=self.device,
                        dtype=dtype,
                    ).clone()
                )
                state = self.layout.join(phi, counterflow, initial_mnemic)
                mnemic_sha256 = self.mnemic_controller.state_sha256(
                    initial_mnemic
                )
            else:
                self.layout.validate(packed)
                state = packed
                phi = self.layout.phi(state)
                counterflow = self.layout.counterflow(state)
                mnemic = self.layout.mnemic(state)
                packed_sha256 = self.layout.state_sha256(state)
                mnemic_sha256 = self.mnemic_controller.state_sha256(mnemic)
            phi_sha256 = self.controller.state_sha256(phi)
            counterflow_sha256 = self.counterflow_runtime.state_sha256(counterflow)
        except (ProviderError, QiFieldError, RuntimeError) as error:
            raise ProviderError(f"shared field state is invalid: {error}") from error
        if packed_sha256 != header.get("shared_state_sha256"):
            raise ProviderError("shared field state hash mismatch")
        if phi_sha256 != header.get("phi_state_sha256"):
            raise ProviderError("Phi component state hash mismatch")
        if counterflow_sha256 != header.get("counterflow_state_sha256"):
            raise ProviderError("counterflow component state hash mismatch")
        if not legacy and mnemic_sha256 != header.get("mnemic_state_sha256"):
            raise ProviderError("mnemic component state hash mismatch")
        normalized_metadata = _metadata(decoded_metadata)
        self._validate_metadata_identity(session_id, normalized_metadata)
        return state, normalized_metadata, path, _sha256(raw)

    def save(
        self,
        session_id: str,
        state: QiFieldState,
        metadata: Mapping[str, Any],
    ) -> tuple[Path, str]:
        value = self._validate_session_id(session_id)
        self.layout.validate(state)
        normalized_metadata = _metadata(metadata)
        self._validate_metadata_identity(value, normalized_metadata)
        metadata_payload = _canonical(normalized_metadata)
        if len(metadata_payload) > MAX_SESSION_METADATA_BYTES:
            raise ProviderError("shared field metadata exceeds the bounded limit")
        try:
            phi = self.layout.phi(state)
            counterflow = self.layout.counterflow(state)
            mnemic = self.layout.mnemic(state)
            phi_sha256 = self.controller.state_sha256(phi)
            counterflow_sha256 = self.counterflow_runtime.state_sha256(counterflow)
            mnemic_sha256 = self.mnemic_controller.state_sha256(mnemic)
        except (ProviderError, QiFieldError) as error:
            raise ProviderError(f"could not validate shared field state: {error}") from error
        owned = state.field.detach().cpu().contiguous()
        field_payload = owned.numpy().tobytes(order="C")
        header = {
            "schema": SHARED_FIELD_SESSION_SCHEMA,
            "session_id": value,
            "provider_fingerprint": self.provider_fingerprint,
            "config_fingerprint": self.controller.config_fingerprint,
            "codebook_fingerprint": self.controller.codebook_fingerprint,
            "counterflow_config_fingerprint": (
                self.counterflow_runtime.config_fingerprint
            ),
            "mnemic_config_fingerprint": self.mnemic_controller.config_fingerprint,
            "layout_fingerprint": self.layout.fingerprint,
            "shared_state_sha256": self.layout.state_sha256(state),
            "phi_state_sha256": phi_sha256,
            "counterflow_state_sha256": counterflow_sha256,
            "mnemic_state_sha256": mnemic_sha256,
            "field_dtype": str(owned.dtype),
            "field_shape": list(owned.shape),
            "field_payload_sha256": _sha256(field_payload),
            "field_bytes": len(field_payload),
            "metadata_sha256": _sha256(metadata_payload),
            "metadata_bytes": len(metadata_payload),
        }
        header_payload = _canonical(header)
        body = (
            _SESSION_MAGIC
            + len(header_payload).to_bytes(8, "big")
            + header_payload
            + field_payload
            + metadata_payload
        )
        serialized = body + hashlib.sha256(body).digest()
        if len(serialized) > _SESSION_FILE_LIMIT:
            raise ProviderError("shared field checkpoint exceeds the bounded limit")
        path = self.path_for(value)
        try:
            _atomic_write(path, serialized)
        except OSError as error:
            raise ProviderError(f"could not commit shared field checkpoint: {error}") from error
        return path, _sha256(serialized)




class PersistentFieldProvider:
    """Hash-pinned engine with one canonical multi-band Qi field tensor."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.phi_config: PhiHarmonicLanguageConfig | None = None
        self.controller: PhiHarmonicLanguageController | None = None
        self.engine: PhiHarmonicTextEngine | None = None
        self.store: SharedFieldSessionStore | None = None
        self.counterflow_runtime: DerivedCounterflowRuntime | None = None
        self.mnemic_controller: MnemicCondensationController | None = None
        self.ingress_journal: QiIngressJournal | None = None
        self.agency_controller: FieldAgencyController | None = None
        self.transition_receipts: TransitionReceiptStore | None = None
        self.action_journal: CanonicalActionJournal | None = None
        self.initial_state: QiFieldState | None = None
        self.initial_checkpoint_sha256: str | None = None
        self.provider_fingerprint: str | None = None
        self.previous_provider_fingerprint: str | None = None
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
            global _TORCH_THREADS_CONFIGURED
            with _TORCH_THREADS_LOCK:
                if not _TORCH_THREADS_CONFIGURED:
                    torch.set_num_threads(1)
                    torch.set_num_interop_threads(1)
                    _TORCH_THREADS_CONFIGURED = True
            phi_config = _load_phi_config(self.config.phi_config_path)
            controller = PhiHarmonicLanguageController(phi_config)
            try:
                checkpoint_payload = self.config.corpus_checkpoint_path.read_bytes()
            except OSError as error:
                raise ProviderError(
                    f"could not read Phi corpus checkpoint: {error}"
                ) from error
            try:
                device = torch.device(self.config.device)
                initial_state = controller.load_state_bytes(
                    checkpoint_payload,
                    device=device,
                    dtype=torch.float32,
                )
                learned_events = controller.learned_events(initial_state)
            except (QiFieldError, RuntimeError) as error:
                raise ProviderError(f"Phi corpus checkpoint is invalid: {error}") from error
            if len(learned_events) < 2:
                raise ProviderError("Phi corpus checkpoint contains no learned exchange")
            engine = PhiHarmonicTextEngine(
                controller, max_output_symbols=self.config.max_output_symbols
            )
            checkpoint_sha256 = _sha256(checkpoint_payload)
            counterflow_runtime = DerivedCounterflowRuntime(device=device)
            initial_counterflow_state = counterflow_runtime.initial_state()
            mnemic_controller = MnemicCondensationController(
                MnemicCondensationConfig(cue_dimensions=256)
            )
            initial_mnemic_state = mnemic_controller.initial_state(
                device=device,
                dtype=initial_state.field.dtype,
            )
            layout = SharedFieldLayout.from_states(
                initial_state,
                initial_counterflow_state,
                initial_mnemic_state,
            )
            initial_shared_state = layout.join(
                initial_state,
                initial_counterflow_state,
                initial_mnemic_state,
            )
            initial_legacy_shared_state = layout.legacy_join(
                initial_state,
                initial_counterflow_state,
            )
            legacy_provider_fingerprint = _sha256(
                {
                    "protocol": PROTOCOL,
                    "version": LEGACY_PROVIDER_VERSION,
                    "model": MODEL_NAME,
                    "engine_fingerprint": engine.fingerprint,
                    "initial_checkpoint_sha256": checkpoint_sha256,
                    "initial_state_sha256": controller.state_sha256(initial_state),
                    "initial_tape_sha256": controller.tape_sha256(initial_state),
                    "context_association_format": (
                        LEGACY_CONTEXT_ASSOCIATION_FORMAT
                    ),
                    "session_schema": LEGACY_SHARED_FIELD_SESSION_SCHEMA,
                    "shared_layout_fingerprint": layout.legacy_fingerprint,
                    "initial_shared_state_sha256": layout.legacy_state_sha256(
                        initial_legacy_shared_state
                    ),
                    "counterflow_config_fingerprint": (
                        counterflow_runtime.config_fingerprint
                    ),
                    "initial_counterflow_state_sha256": (
                        counterflow_runtime.state_sha256(
                            initial_counterflow_state
                        )
                    ),
                }
            )
            agency_controller = FieldAgencyController(initial_mnemic_state)
            previous_provider_fingerprint = _sha256(
                {
                    "protocol": PROTOCOL,
                    "version": PREVIOUS_PROVIDER_VERSION,
                    "model": MODEL_NAME,
                    "engine_fingerprint": engine.fingerprint,
                    "initial_checkpoint_sha256": checkpoint_sha256,
                    "initial_state_sha256": controller.state_sha256(initial_state),
                    "initial_tape_sha256": controller.tape_sha256(initial_state),
                    "session_schema": SHARED_FIELD_SESSION_SCHEMA,
                    "shared_layout_fingerprint": layout.fingerprint,
                    "initial_shared_state_sha256": layout.state_sha256(
                        initial_shared_state
                    ),
                    "counterflow_config_fingerprint": (
                        counterflow_runtime.config_fingerprint
                    ),
                    "initial_counterflow_state_sha256": (
                        counterflow_runtime.state_sha256(initial_counterflow_state)
                    ),
                    "mnemic_config_fingerprint": (
                        mnemic_controller.config_fingerprint
                    ),
                    "initial_mnemic_state_sha256": (
                        mnemic_controller.state_sha256(initial_mnemic_state)
                    ),
                }
            )
            provider_fingerprint = _sha256(
                {
                    "protocol": PROTOCOL,
                    "version": VERSION,
                    "model": MODEL_NAME,
                    "engine_fingerprint": engine.fingerprint,
                    "initial_checkpoint_sha256": checkpoint_sha256,
                    "initial_state_sha256": controller.state_sha256(initial_state),
                    "initial_tape_sha256": controller.tape_sha256(initial_state),
                    "session_schema": SHARED_FIELD_SESSION_SCHEMA,
                    "shared_layout_fingerprint": layout.fingerprint,
                    "initial_shared_state_sha256": layout.state_sha256(
                        initial_shared_state
                    ),
                    "counterflow_config_fingerprint": (
                        counterflow_runtime.config_fingerprint
                    ),
                    "initial_counterflow_state_sha256": (
                        counterflow_runtime.state_sha256(initial_counterflow_state)
                    ),
                    "mnemic_config_fingerprint": (
                        mnemic_controller.config_fingerprint
                    ),
                    "initial_mnemic_state_sha256": (
                        mnemic_controller.state_sha256(initial_mnemic_state)
                    ),
                    "agency_codec_fingerprint": agency_controller.fingerprint,
                }
            )
            store = SharedFieldSessionStore(
                self.config.state_dir,
                controller,
                counterflow_runtime,
                mnemic_controller,
                initial_mnemic_state,
                layout,
                provider_fingerprint=provider_fingerprint,
                previous_provider_fingerprint=previous_provider_fingerprint,
                legacy_provider_fingerprint=legacy_provider_fingerprint,
                engine_fingerprint=engine.fingerprint,
                device=device,
            )
            try:
                ingress_journal = QiIngressJournal(
                    self.config.state_dir / "ingress",
                    max_bytes=self.config.ingress_max_bytes,
                )
            except (OSError, UniversalDataError) as error:
                raise ProviderError(
                    f"could not open exact ingress journal: {error}"
                ) from error
            transition_receipts = TransitionReceiptStore(
                self.config.state_dir / "canonical-receipts"
            )
            action_journal = CanonicalActionJournal(
                self.config.state_dir / "action-journal"
            )
            self.phi_config = phi_config
            self.controller = controller
            self.engine = engine
            self.initial_state = initial_state
            self.initial_checkpoint_sha256 = checkpoint_sha256
            self.provider_fingerprint = provider_fingerprint
            self.previous_provider_fingerprint = previous_provider_fingerprint
            self.store = store
            self.counterflow_runtime = counterflow_runtime
            self.mnemic_controller = mnemic_controller
            self.ingress_journal = ingress_journal
            self.agency_controller = agency_controller
            self.transition_receipts = transition_receipts
            self.action_journal = action_journal
            self._started = True

    def close(self) -> None:
        with self._lock:
            self._started = False
            self.action_journal = None
            self.transition_receipts = None
            self.agency_controller = None
            self.store = None
            self.ingress_journal = None
            self.counterflow_runtime = None
            self.mnemic_controller = None
            self.engine = None
            self.controller = None
            self.initial_state = None
            self.phi_config = None
            self.initial_checkpoint_sha256 = None
            self.provider_fingerprint = None
            self.previous_provider_fingerprint = None

    def _session_lock(self, session_id: str) -> threading.RLock:
        with self._lock:
            return self._session_locks.setdefault(session_id, threading.RLock())

    def _require(
        self,
    ) -> tuple[
        PhiHarmonicLanguageController,
        PhiHarmonicTextEngine,
        QiFieldState,
        SharedFieldSessionStore,
        str,
    ]:
        if (
            not self._started
            or self.controller is None
            or self.engine is None
            or self.initial_state is None
            or self.store is None
            or self.provider_fingerprint is None
        ):
            raise ProviderError("persistent field provider is not started")
        return (
            self.controller,
            self.engine,
            self.initial_state,
            self.store,
            self.provider_fingerprint,
        )

    def _require_ingress(self) -> QiIngressJournal:
        if not self._started or self.ingress_journal is None:
            raise ProviderError("persistent field provider is not started")
        return self.ingress_journal

    @staticmethod
    def _ingress_fraction(value: Any, label: str) -> Fraction:
        if (
            not isinstance(value, Mapping)
            or set(value) != {"numerator", "denominator"}
            or isinstance(value["numerator"], bool)
            or not isinstance(value["numerator"], int)
            or isinstance(value["denominator"], bool)
            or not isinstance(value["denominator"], int)
            or value["denominator"] <= 0
        ):
            raise ProviderError(f"{label} must be a canonical rational time")
        return Fraction(value["numerator"], value["denominator"])

    @staticmethod
    def _ingress_codec(value: Any) -> str:
        if not isinstance(value, str) or value not in _INGRESS_CODECS:
            raise ProviderError(
                f"codec_id must be one of {', '.join(_INGRESS_CODECS)}"
            )
        return value

    @staticmethod
    def _reference_payload(reference: JournalReference) -> dict[str, Any]:
        return {
            "packet_sha256": reference.packet_sha256,
            "packet_object_sha256": reference.packet_object_sha256,
            "payload_manifest_sha256": reference.payload_manifest_sha256,
            "journal_head_sha256": reference.journal_head_sha256,
            "source_stream_id": reference.source_stream_id,
            "source_sequence": reference.source_sequence,
        }

    @staticmethod
    def _journal_reference(value: Any) -> JournalReference:
        if not isinstance(value, Mapping) or set(value) != _JOURNAL_REFERENCE_KEYS:
            raise ProviderError("ingress journal reference is invalid")
        try:
            return JournalReference(
                packet_sha256=value["packet_sha256"],
                packet_object_sha256=value["packet_object_sha256"],
                payload_manifest_sha256=value["payload_manifest_sha256"],
                journal_head_sha256=value["journal_head_sha256"],
                source_stream_id=value["source_stream_id"],
                source_sequence=value["source_sequence"],
            )
        except UniversalDataError as error:
            raise ProviderError(f"ingress journal reference is invalid: {error}") from error

    @staticmethod
    def _ingress_record_id(value: Any, *, default: str) -> str:
        if value is None:
            return default
        if (
            not isinstance(value, str)
            or not value
            or len(value.encode("utf-8")) > MAX_SESSION_ID
        ):
            raise ProviderError(
                f"record_id must be nonempty and at most {MAX_SESSION_ID} UTF-8 bytes"
            )
        return value

    def _packet_from_ingress(
        self, request: Mapping[str, Any]
    ) -> tuple[BoundaryPacket, str, str]:
        keys = frozenset(request)
        if (
            not {"codec_id", "packet", "payload_base64"} <= keys
            or not keys <= _INGRESS_REQUEST_KEYS
        ):
            raise ProviderError("ingress append request has unexpected or missing keys")
        codec_id = self._ingress_codec(request["codec_id"])
        packet_value = request["packet"]
        if not isinstance(packet_value, Mapping):
            raise ProviderError("ingress packet must be an object")
        packet_keys = frozenset(packet_value)
        if (
            not _INGRESS_PACKET_REQUIRED_KEYS <= packet_keys
            or not packet_keys
            <= _INGRESS_PACKET_REQUIRED_KEYS | _INGRESS_PACKET_OPTIONAL_KEYS
        ):
            raise ProviderError("ingress packet has unexpected or missing keys")
        encoded = request["payload_base64"]
        if not isinstance(encoded, str):
            raise ProviderError("payload_base64 must be text")
        max_encoded = ((self.config.ingress_max_bytes + 2) // 3) * 4
        if len(encoded) > max_encoded:
            raise ProviderError("decoded ingress payload exceeds the journal capacity")
        try:
            payload = base64.b64decode(encoded, validate=True)
        except (binascii.Error, UnicodeEncodeError, ValueError) as error:
            raise ProviderError("payload_base64 is not canonical base64") from error
        if len(payload) > self.config.ingress_max_bytes:
            raise ProviderError("decoded ingress payload exceeds the journal capacity")
        if base64.b64encode(payload).decode("ascii") != encoded:
            raise ProviderError("payload_base64 is not canonical base64")
        try:
            packet = BoundaryPacket.create(
                identity=BoundaryIdentity(
                    run_id=packet_value["run_id"],
                    episode_id=packet_value["episode_id"],
                    world_id=packet_value["world_id"],
                    session_id=packet_value["session_id"],
                    profile_sha256=packet_value["profile_sha256"],
                    clock_sha256=packet_value["clock_sha256"],
                    source_epoch=packet_value["source_epoch"],
                    source_stream_id=packet_value["source_stream_id"],
                    body_frame_id=packet_value["body_frame_id"],
                ),
                codec_id=codec_id,
                request_id=packet_value["request_id"],
                logical_tick=packet_value["logical_tick"],
                logical_time=self._ingress_fraction(
                    packet_value["logical_time"], "logical_time"
                ),
                capture_start=self._ingress_fraction(
                    packet_value["capture_start"], "capture_start"
                ),
                capture_end=self._ingress_fraction(
                    packet_value["capture_end"], "capture_end"
                ),
                source_sequence=packet_value["source_sequence"],
                payload_shape=tuple(packet_value["payload_shape"]),
                payload_dtype=packet_value["payload_dtype"],
                payload=payload,
                source_timestamp_ns_telemetry=packet_value.get(
                    "source_timestamp_ns_telemetry"
                ),
                arrival_sequence_telemetry=packet_value.get(
                    "arrival_sequence_telemetry"
                ),
                watermark_sha256=packet_value.get(
                    "watermark_sha256", ZERO_SHA256
                ),
                ingress_journal_sha256=packet_value["ingress_journal_sha256"],
                antialias_receipt_sha256=packet_value.get(
                    "antialias_receipt_sha256"
                ),
                causal_parent_event_id=packet_value.get(
                    "causal_parent_event_id"
                ),
                causal_parent_action_id=packet_value.get(
                    "causal_parent_action_id"
                ),
                valid=packet_value.get("valid", True),
            )
        except (TypeError, UniversalDataError) as error:
            raise ProviderError(f"ingress packet is invalid: {error}") from error
        return (
            packet,
            codec_id,
            self._ingress_record_id(
                request.get("record_id"), default=packet.event_id
            ),
        )

    def _ingress_receipt(
        self,
        *,
        operation: str,
        packet: BoundaryPacket,
        codec_id: str,
        reference: JournalReference,
        result: BoundaryResult[ObservationView],
        record_id: str,
        payload_base64: str | None = None,
    ) -> dict[str, Any]:
        view = result.value
        adapter: dict[str, Any] = {
            "status": result.status,
            "reason": result.reason,
            "view_sha256": None,
            "modality": None,
            "root_constructor": None,
        }
        mnemic_input: dict[str, Any] | None = None
        if view is not None:
            source = view.root.source
            adapter.update(
                {
                    "view_sha256": view.view_sha256,
                    "modality": view.modality,
                    "root_constructor": type(view.root).__name__,
                }
            )
            mnemic_input = {
                "contextSessionId": packet.identity.session_id,
                "recordId": record_id,
                "packetSha256": reference.packet_sha256,
                "packetObjectSha256": reference.packet_object_sha256,
                "payloadManifestSha256": reference.payload_manifest_sha256,
                "journalHeadSha256": reference.journal_head_sha256,
                "viewSha256": view.view_sha256,
                "codecId": codec_id,
                "sourceStreamId": reference.source_stream_id,
                "sourceSequence": reference.source_sequence,
                "sourcePath": list(source.path),
            }
            if source.span is not None:
                mnemic_input["sourceSpan"] = list(source.span)
        receipt: dict[str, Any] = {
            "schema": INGRESS_RECEIPT_SCHEMA,
            "operation": operation,
            "codec_id": codec_id,
            "packet": packet.metadata(),
            "journal": self._reference_payload(reference),
            "adapter": adapter,
            "mnemic_observation_input": mnemic_input,
            "semantic_status": "unsupported",
            "semantic_reason": "no_semantic_task",
            "thalamus_admission": "policy_required",
            "adaptive_state_changed": False,
        }
        if payload_base64 is not None:
            receipt["payload_base64"] = payload_base64
        return receipt

    def append_ingress(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request, Mapping):
            raise ProviderError("ingress append request must be an object")
        journal = self._require_ingress()
        packet, codec_id, record_id = self._packet_from_ingress(request)
        try:
            reference = journal.append(packet)
            result = adapt(packet, codec_id, evidence=(reference,))
        except UniversalDataError as error:
            raise ProviderError(f"exact ingress append failed: {error}") from error
        return self._ingress_receipt(
            operation="append",
            packet=packet,
            codec_id=codec_id,
            reference=reference,
            result=result,
            record_id=record_id,
        )

    def read_ingress(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request, Mapping):
            raise ProviderError("ingress read request must be an object")
        if not {"codec_id", "reference"} <= set(request) or not set(request) <= {
            "codec_id",
            "reference",
            "record_id",
        }:
            raise ProviderError("ingress read request has unexpected or missing keys")
        journal = self._require_ingress()
        codec_id = self._ingress_codec(request["codec_id"])
        reference = self._journal_reference(request["reference"])
        try:
            if reference not in journal.replay():
                raise ProviderError("ingress reference is not in the current journal")
            packet = journal.read_packet(reference)
            if descriptor_sha256(codec_id) != packet.descriptor_sha256:
                raise ProviderError("codec_id does not match the journaled packet")
            result = adapt(packet, codec_id, evidence=(reference,))
        except UniversalDataError as error:
            raise ProviderError(f"exact ingress read failed: {error}") from error
        return self._ingress_receipt(
            operation="read",
            packet=packet,
            codec_id=codec_id,
            reference=reference,
            result=result,
            record_id=self._ingress_record_id(
                request.get("record_id"), default=packet.event_id
            ),
            payload_base64=base64.b64encode(packet.payload).decode("ascii"),
        )

    def replay_ingress(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request, Mapping) or not set(request) <= {"limit"}:
            raise ProviderError("ingress replay request must contain only limit")
        limit = request.get("limit", 128)
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_INGRESS_REPLAY_ENTRIES
        ):
            raise ProviderError(
                f"ingress replay limit must lie in [1, {MAX_INGRESS_REPLAY_ENTRIES}]"
            )
        journal = self._require_ingress()
        entries: list[dict[str, Any]] = []
        try:
            references = journal.replay()
            first_returned = max(0, len(references) - limit)
            previous_head = ZERO_SHA256
            for index, reference in enumerate(references):
                packet = journal.read_packet(reference)
                if (
                    packet.ingress_journal_sha256 != previous_head
                    or packet.identity.source_stream_id
                    != reference.source_stream_id
                    or packet.source_sequence != reference.source_sequence
                ):
                    raise UniversalDataError(
                        "replayed packet does not match its journal chain"
                    )
                previous_head = reference.journal_head_sha256
                codec_id = _INGRESS_CODEC_BY_DESCRIPTOR.get(
                    packet.descriptor_sha256
                )
                if codec_id is None:
                    raise UniversalDataError(
                        "replayed packet uses an unsupported codec descriptor"
                    )
                result = adapt(packet, codec_id, evidence=(reference,))
                if index >= first_returned:
                    entries.append(
                        self._ingress_receipt(
                            operation="replay",
                            packet=packet,
                            codec_id=codec_id,
                            reference=reference,
                            result=result,
                            record_id=packet.event_id,
                        )
                    )
        except UniversalDataError as error:
            raise ProviderError(f"exact ingress replay failed: {error}") from error
        return {
            "schema": INGRESS_REPLAY_SCHEMA,
            "head_sha256": journal.head_sha256,
            "max_bytes": self.config.ingress_max_bytes,
            "total_entries": len(references),
            "returned_entries": len(entries),
            "truncated": len(entries) != len(references),
            "entries": entries,
            "adaptive_state_changed": False,
        }


    def _response(
        self,
        *,
        request_id: str,
        session_id: str,
        result: PhiHarmonicTextResult,
        reply_kind: str,
        checkpoint: Path,
        checkpoint_sha256: str,
    ) -> dict[str, Any]:
        _, engine, _, _, provider_fingerprint = self._require()
        finish_reason = (
            "length" if result.stop_reason == "max_output_symbols" else "stop"
        )
        receipt = result.receipt_dict()
        return {
            "id": request_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": MODEL_NAME,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": result.reply},
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": len(result.prompt_symbols),
                "completion_tokens": len(result.output_symbols),
                "total_tokens": len(result.prompt_symbols)
                + len(result.output_symbols),
            },
            "cassi": {
                "protocol": PROTOCOL,
                "version": VERSION,
                "model": MODEL_NAME,
                "session_id": session_id,
                "request_id": request_id,
                "provider_fingerprint": provider_fingerprint,
                "engine_fingerprint": engine.fingerprint,
                "initial_checkpoint_sha256": self.initial_checkpoint_sha256,
                "state_in_sha256": result.initial_state_sha256,
                "state_out_sha256": result.final_state_sha256,
                "tape_sha256": result.tape_sha256,
                "trained_tape_preserved": True,
                "stop_reason": result.stop_reason,
                "reply_kind": reply_kind,
                "output_bytes_sha256": _sha256(result.reply.encode("utf-8")),
                "field_text_receipt": receipt,
                "field_text_receipt_sha256": result.receipt_sha256,
                "checkpoint": str(checkpoint),
                "checkpoint_sha256": checkpoint_sha256,
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
        _, engine, initial, store, _ = self._require()
        session_id = _session_id(request)
        request_id = request.get("id", f"cassi-{uuid.uuid4().hex}")
        if (
            not isinstance(request_id, str)
            or not request_id
            or len(request_id.encode("utf-8")) > MAX_SESSION_ID
        ):
            raise ProviderError("request id must be bounded nonempty UTF-8 text")
        max_output = request.get("max_tokens", self.config.max_output_symbols)
        if (
            isinstance(max_output, bool)
            or not isinstance(max_output, int)
            or not 1 <= max_output <= self.config.max_output_symbols
        ):
            raise ProviderError("max_tokens exceeds the bounded field output limit")
        with self._session_lock(session_id):
            loaded = store.load(session_id)
            shared = store.initial(initial) if loaded is None else loaded[0]
            state = store.layout.phi(shared)
            metadata = _metadata(None if loaded is None else loaded[1])
            messages = request["messages"] if loaded is None else [request["messages"][-1]]
            try:
                result = engine.generate(
                    state, messages, max_output_symbols=max_output
                )
                _, reply_kind = result.render_text()
                metadata[LAST_COMPLETION_METADATA_KEY] = {
                    "protocol": PROTOCOL,
                    "version": VERSION,
                    "model": MODEL_NAME,
                    "session_id": session_id,
                    "request_id": request_id,
                    "messages_sha256": _sha256(request["messages"]),
                    "state_in_sha256": result.initial_state_sha256,
                    "state_out_sha256": result.final_state_sha256,
                    "field_text_receipt": result.receipt_dict(),
                    "field_text_receipt_sha256": result.receipt_sha256,
                    "output_bytes_sha256": _sha256(result.reply.encode("utf-8")),
                    "updated_at": int(time.time()),
                }
                checkpoint, checkpoint_sha256 = store.save(
                    session_id,
                    store.layout.with_phi(shared, result.state),
                    metadata,
                )
            except ProviderError:
                raise
            except (QiFieldError, CassiFieldLanguageError) as error:
                raise ProviderError(
                    "Phi generation/checkpoint failed; prior checkpoint retained: "
                    f"{error}"
                ) from error
            except Exception as error:
                raise ProviderError(
                    "Phi generation/checkpoint failed; prior checkpoint retained: "
                    f"{type(error).__name__}: {error}"
                ) from error
            return self._response(
                request_id=request_id,
                session_id=session_id,
                result=result,
                reply_kind=reply_kind,
                checkpoint=checkpoint,
                checkpoint_sha256=checkpoint_sha256,
            )

    def _require_canonical(
        self,
    ) -> tuple[
        FieldAgencyController,
        TransitionReceiptStore,
        CanonicalActionJournal,
        MnemicCondensationController,
        SharedFieldSessionStore,
        QiFieldState,
    ]:
        _, _, initial, store, _ = self._require()
        if (
            self.agency_controller is None
            or self.transition_receipts is None
            or self.action_journal is None
            or self.mnemic_controller is None
        ):
            raise ProviderError("canonical field runtime is not started")
        return (
            self.agency_controller,
            self.transition_receipts,
            self.action_journal,
            self.mnemic_controller,
            store,
            initial,
        )

    @staticmethod
    def _canonical_scopes(
        request: Mapping[str, Any],
    ) -> tuple[str, str, str, str]:
        session_id = _session_id(request)
        identity_scope = request.get("identity_scope")
        task_scope = request.get("task_scope")
        request_id = request.get("request_id")
        for label, value in (
            ("identity_scope", identity_scope),
            ("task_scope", task_scope),
            ("request_id", request_id),
        ):
            PersistentFieldProvider._world_identifier(value, label)
        if identity_scope != session_id:
            raise ProviderError("identity_scope must equal the provider user")
        return session_id, str(identity_scope), str(task_scope), str(request_id)

    def _store_transition_receipt(
        self,
        *,
        operation: str,
        identity_scope: str,
        task_scope: str,
        request_id: str,
        state_in_sha256: str,
        state_out_sha256: str,
        component_in_sha256: str,
        component_out_sha256: str,
        component: str,
        request_payload: Mapping[str, Any],
        result: Mapping[str, Any],
        checkpoint_sha256: str | None,
    ) -> tuple[dict[str, Any], str, Path]:
        _, receipt_store, _, _, _, _ = self._require_canonical()
        try:
            receipt = receipt_payload(
                operation=operation,
                identity_scope=identity_scope,
                task_scope=task_scope,
                request_id=request_id,
                state_in_sha256=state_in_sha256,
                state_out_sha256=state_out_sha256,
                component_in_sha256=component_in_sha256,
                component_out_sha256=component_out_sha256,
                component=component,
                request_payload=request_payload,
                result=result,
                checkpoint_sha256=checkpoint_sha256,
            )
            digest, path = receipt_store.put(receipt)
        except (CanonicalRuntimeError, OSError) as error:
            raise ProviderError(f"could not commit canonical receipt: {error}") from error
        return receipt, digest, path

    def canonical_transition(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Run a scoped chat, teach, recall, plan, or correction transition."""

        if not isinstance(request, Mapping):
            raise ProviderError("canonical transition request must be an object")
        operation = request.get("operation")
        operation_name = operation if isinstance(operation, str) else ""
        common = {
            "operation",
            "user",
            "identity_scope",
            "task_scope",
            "request_id",
        }
        operation_keys = {
            "chat": common | {"messages", "max_tokens"},
            "teach": common | {"text", "action"},
            "recall": common | {"text", "candidates"},
            "plan": common | {"text", "candidates"},
            "correct": common | {"text", "previous_action", "action"},
        }
        expected = operation_keys.get(operation_name)
        if expected is None or set(request) != expected:
            raise ProviderError(
                "canonical transition operation or key set is invalid"
            )
        session_id, identity_scope, task_scope, request_id = (
            self._canonical_scopes(request)
        )
        agency, _, _, mnemic_controller, store, initial = (
            self._require_canonical()
        )

        if operation_name == "chat":
            with self._session_lock(session_id):
                loaded_in = store.load(session_id)
                shared_in = (
                    store.initial(initial) if loaded_in is None else loaded_in[0]
                )
                response = self.complete(
                    {
                        "model": MODEL_NAME,
                        "messages": request["messages"],
                        "user": session_id,
                        "id": request_id,
                        "temperature": 0,
                        "max_tokens": request["max_tokens"],
                    }
                )
                loaded_out = store.load(session_id)
                if loaded_out is None:
                    raise ProviderError("chat transition did not commit a checkpoint")
                shared_out = loaded_out[0]
            result = {
                "reply": response["choices"][0]["message"]["content"],
                "reply_sha256": _sha256(
                    response["choices"][0]["message"]["content"].encode("utf-8")
                ),
            }
            receipt, receipt_sha256, receipt_path = (
                self._store_transition_receipt(
                    operation="chat",
                    identity_scope=identity_scope,
                    task_scope=task_scope,
                    request_id=request_id,
                    state_in_sha256=store.layout.state_sha256(shared_in),
                    state_out_sha256=store.layout.state_sha256(shared_out),
                    component_in_sha256=response["cassi"]["state_in_sha256"],
                    component_out_sha256=response["cassi"]["state_out_sha256"],
                    component="shared-field.phi",
                    request_payload=request,
                    result=result,
                    checkpoint_sha256=loaded_out[3],
                )
            )
            return {
                "schema": "cassi.canonical-transition-result.v1",
                "operation": operation_name,
                **result,
                "receipt": receipt,
                "receipt_sha256": receipt_sha256,
                "receipt_path": str(receipt_path),
            }

        text = request.get("text")
        if not isinstance(text, str):
            raise ProviderError("canonical field text must be a string")
        with self._session_lock(session_id):
            loaded = store.load(session_id)
            shared_in = store.initial(initial) if loaded is None else loaded[0]
            metadata = _metadata(None if loaded is None else loaded[1])
            mnemic_in = store.layout.mnemic(shared_in)
            component_in_sha256 = mnemic_controller.state_sha256(mnemic_in)
            checkpoint_sha256 = None if loaded is None else loaded[3]
            detail: dict[str, Any]
            shared_out = shared_in

            try:
                if operation_name == "teach":
                    mnemic_out, detail = agency.teach(
                        mnemic_in,
                        identity_scope=identity_scope,
                        text=text,
                        action=request["action"],
                    )
                    shared_out = store.layout.with_mnemic(shared_in, mnemic_out)
                elif operation_name == "correct":
                    inhibited, prior_detail = agency.teach(
                        mnemic_in,
                        identity_scope=identity_scope,
                        text=text,
                        action=request["previous_action"],
                        polarity=-1.0,
                    )
                    mnemic_out, learned_detail = agency.teach(
                        inhibited,
                        identity_scope=identity_scope,
                        text=text,
                        action=request["action"],
                    )
                    detail = {
                        "previous_action": request["previous_action"],
                        "action": request["action"],
                        "inhibition": prior_detail,
                        "learning": learned_detail,
                    }
                    shared_out = store.layout.with_mnemic(shared_in, mnemic_out)
                else:
                    decision = agency.decide(
                        mnemic_in,
                        identity_scope=identity_scope,
                        text=text,
                        candidates=request["candidates"],
                    )
                    detail = {"decision": decision.payload()}
            except CanonicalRuntimeError as error:
                raise ProviderError(f"canonical field transition failed: {error}") from error

            if operation_name in {"teach", "correct"}:
                try:
                    _, checkpoint_sha256 = store.save(
                        session_id,
                        shared_out,
                        metadata,
                    )
                except (ProviderError, QiFieldError) as error:
                    raise ProviderError(
                        "canonical field transition failed; prior checkpoint retained: "
                        f"{error}"
                    ) from error

            component_out_sha256 = mnemic_controller.state_sha256(
                store.layout.mnemic(shared_out)
            )
            state_in_sha256 = store.layout.state_sha256(shared_in)
            state_out_sha256 = store.layout.state_sha256(shared_out)

        receipt, receipt_sha256, receipt_path = self._store_transition_receipt(
            operation=operation_name,
            identity_scope=identity_scope,
            task_scope=task_scope,
            request_id=request_id,
            state_in_sha256=state_in_sha256,
            state_out_sha256=state_out_sha256,
            component_in_sha256=component_in_sha256,
            component_out_sha256=component_out_sha256,
            component="shared-field.mnemic",
            request_payload=request,
            result=detail,
            checkpoint_sha256=checkpoint_sha256,
        )
        return {
            "schema": "cassi.canonical-transition-result.v1",
            "operation": operation_name,
            **detail,
            "receipt": receipt,
            "receipt_sha256": receipt_sha256,
            "receipt_path": str(receipt_path),
        }

    @staticmethod
    def _action_stage(record: Mapping[str, Any]) -> str:
        events = record.get("events")
        if not isinstance(events, list) or not events:
            raise ProviderError("action journal record has no lifecycle")
        stage = events[-1].get("stage")
        if not isinstance(stage, str):
            raise ProviderError("action journal stage is invalid")
        return stage

    @staticmethod
    def _action_event(
        record: Mapping[str, Any], stage: str
    ) -> Mapping[str, Any] | None:
        events = record.get("events")
        if not isinstance(events, list):
            raise ProviderError("action journal record has no lifecycle")
        for event in reversed(events):
            if event.get("stage") == stage:
                payload = event.get("payload")
                if not isinstance(payload, Mapping):
                    raise ProviderError("action journal event payload is invalid")
                return payload
        return None

    def _mark_action_unresolved(
        self,
        record: Mapping[str, Any],
        *,
        reason: str,
    ) -> None:
        _, _, journal, _, _, _ = self._require_canonical()
        stage = self._action_stage(record)
        if stage == "unresolved":
            return
        try:
            journal.append(
                str(record["action_instance_id"]),
                expected=(stage,),
                stage="unresolved",
                payload={"reason": reason[:512]},
            )
        except CanonicalRuntimeError as error:
            raise ProviderError(f"could not record unresolved action: {error}") from error

    def _consolidate_action(
        self,
        record: Mapping[str, Any],
    ) -> dict[str, Any]:
        agency, _, journal, mnemic_controller, store, initial = (
            self._require_canonical()
        )
        proposal = self._action_event(record, "proposed")
        outcome = self._action_event(record, "outcome_pending")
        if proposal is None or outcome is None:
            raise ProviderError("action cannot consolidate without proposal and outcome")
        session_id = str(record["identity_scope"])
        action_instance_id = str(record["action_instance_id"])
        ack = QiWorldTickAck.from_payload(outcome["ack"])
        with self._session_lock(session_id):
            loaded = store.load(session_id)
            shared = store.initial(initial) if loaded is None else loaded[0]
            metadata = _metadata(None if loaded is None else loaded[1])
            current_sha256 = store.layout.state_sha256(shared)
            consolidating = self._action_event(record, "consolidating")
            if consolidating is None:
                expected_in = str(proposal["predecessor_field_sha256"])
                if current_sha256 != expected_in:
                    self._mark_action_unresolved(
                        record,
                        reason="field predecessor changed before observed consolidation",
                    )
                    raise ProviderError(
                        "action outcome is unresolved because the field predecessor changed"
                    )
                mnemic_in = store.layout.mnemic(shared)
                try:
                    mnemic_out, agency_detail = agency.teach(
                        mnemic_in,
                        identity_scope=session_id,
                        text=str(proposal["text"]),
                        action=str(proposal["selected_action"]),
                        polarity=1.0 if ack.status == "applied" else -1.0,
                    )
                except CanonicalRuntimeError as error:
                    raise ProviderError(
                        f"action observation could not enter the field: {error}"
                    ) from error
                shared_out = store.layout.with_mnemic(shared, mnemic_out)
                consolidation_payload = {
                    "ack_sha256": ack.tick_ack_sha256,
                    "observation_sha256": _sha256(ack.payload()),
                    "state_in_sha256": current_sha256,
                    "state_out_sha256": store.layout.state_sha256(shared_out),
                    "component_state_in_sha256": (
                        mnemic_controller.state_sha256(mnemic_in)
                    ),
                    "component_state_out_sha256": (
                        mnemic_controller.state_sha256(mnemic_out)
                    ),
                    "agency_transition": agency_detail,
                }
                try:
                    record = journal.append(
                        action_instance_id,
                        expected=("outcome_pending",),
                        stage="consolidating",
                        payload=consolidation_payload,
                    )
                except CanonicalRuntimeError as error:
                    raise ProviderError(
                        f"could not journal field consolidation intent: {error}"
                    ) from error
                consolidating = consolidation_payload
            expected_in = str(consolidating["state_in_sha256"])
            expected_out = str(consolidating["state_out_sha256"])
            current_sha256 = store.layout.state_sha256(shared)
            if current_sha256 == expected_in:
                mnemic_in = store.layout.mnemic(shared)
                try:
                    mnemic_out, _ = agency.teach(
                        mnemic_in,
                        identity_scope=session_id,
                        text=str(proposal["text"]),
                        action=str(proposal["selected_action"]),
                        polarity=1.0 if ack.status == "applied" else -1.0,
                    )
                except CanonicalRuntimeError as error:
                    raise ProviderError(
                        f"could not replay pending field consolidation: {error}"
                    ) from error
                shared_out = store.layout.with_mnemic(shared, mnemic_out)
                if (
                    store.layout.state_sha256(shared_out) != expected_out
                    or mnemic_controller.state_sha256(mnemic_out)
                    != consolidating["component_state_out_sha256"]
                ):
                    self._mark_action_unresolved(
                        record,
                        reason="replayed field consolidation hash mismatch",
                    )
                    raise ProviderError(
                        "action outcome is unresolved because consolidation diverged"
                    )
                _, checkpoint_sha256 = store.save(
                    session_id,
                    shared_out,
                    metadata,
                )
            elif current_sha256 == expected_out:
                if loaded is None:
                    raise ProviderError("consolidated field checkpoint is missing")
                _, checkpoint_sha256 = loaded[2], loaded[3]
            else:
                self._mark_action_unresolved(
                    record,
                    reason="field state matches neither side of pending consolidation",
                )
                raise ProviderError(
                    "action outcome is unresolved against the current field state"
                )

        result = {
            "action_instance_id": action_instance_id,
            "stage": "observed",
            "status": ack.status,
            "world_effect": ack.world_effect,
            "ack_sha256": ack.tick_ack_sha256,
            "observation_sha256": consolidating["observation_sha256"],
            "state_in_sha256": expected_in,
            "state_out_sha256": expected_out,
            "checkpoint_sha256": checkpoint_sha256,
            "consolidated_once": True,
        }
        receipt, receipt_sha256, _ = self._store_transition_receipt(
            operation="world-observe",
            identity_scope=session_id,
            task_scope=str(record["task_scope"]),
            request_id=str(record["request_id"]),
            state_in_sha256=expected_in,
            state_out_sha256=expected_out,
            component_in_sha256=str(
                consolidating["component_state_in_sha256"]
            ),
            component_out_sha256=str(
                consolidating["component_state_out_sha256"]
            ),
            component="shared-field.mnemic",
            request_payload=proposal,
            result=result,
            checkpoint_sha256=checkpoint_sha256,
        )
        response = {
            "schema": "cassi.canonical-action-result.v1",
            **result,
            "receipt": receipt,
            "receipt_sha256": receipt_sha256,
        }
        try:
            journal.append(
                action_instance_id,
                expected=("consolidating",),
                stage="observed",
                payload={"response": response},
            )
        except CanonicalRuntimeError as error:
            raise ProviderError(f"could not finalize observed action: {error}") from error
        return response

    def _resume_action(
        self,
        record: Mapping[str, Any],
        world: QiWorldPort,
        *,
        withhold_observation: bool = False,
    ) -> dict[str, Any]:
        _, _, journal, _, _, _ = self._require_canonical()
        stage = self._action_stage(record)
        if stage == "observed":
            event = self._action_event(record, "observed")
            if event is None or not isinstance(event.get("response"), Mapping):
                raise ProviderError("observed action response is missing")
            return dict(event["response"])
        if stage == "unresolved":
            event = self._action_event(record, "unresolved")
            raise ProviderError(
                "action outcome is unresolved"
                + ("" if event is None else f": {event.get('reason', '')}")
            )
        if stage == "dispatch_intent":
            intent_payload = self._action_event(record, "dispatch_intent")
            if intent_payload is None:
                raise ProviderError("dispatch intent payload is missing")
            try:
                intent = QiWorldTickIntent.from_payload(intent_payload["intent"])
                ack = world.resolve_tick(intent)
            except (CanonicalRuntimeError, QiWorldError, KeyError, TypeError) as error:
                self._mark_action_unresolved(
                    record,
                    reason=f"world could not resolve durable dispatch intent: {error}",
                )
                raise ProviderError(
                    "action dispatch is unresolved; the provider did not retry it"
                ) from error
            try:
                record = journal.append(
                    str(record["action_instance_id"]),
                    expected=("dispatch_intent",),
                    stage="outcome_pending",
                    payload={"ack": ack.payload()},
                )
            except CanonicalRuntimeError as error:
                raise ProviderError(f"could not journal resolved world outcome: {error}") from error
            stage = "outcome_pending"
        if stage == "outcome_pending" and withhold_observation:
            return {
                "schema": "cassi.canonical-action-result.v1",
                "action_instance_id": record["action_instance_id"],
                "stage": "outcome_pending",
                "consolidated_once": False,
            }
        if stage in {"outcome_pending", "consolidating"}:
            return self._consolidate_action(record)
        raise ProviderError(f"action lifecycle cannot resume from {stage!r}")

    def execute_canonical_action(
        self,
        request: Mapping[str, Any],
        world: QiWorldPort,
        *,
        crash_after_dispatch: bool = False,
        withhold_observation: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(request, Mapping):
            raise ProviderError("canonical action request must be an object")
        session_id, identity_scope, _, _ = self._canonical_scopes(request)
        _, _, journal, _, _, _ = self._require_canonical()
        with self._session_lock(session_id), journal.identity_transition(identity_scope):
            return self._execute_canonical_action_locked(
                request,
                world,
                crash_after_dispatch=crash_after_dispatch,
                withhold_observation=withhold_observation,
            )

    def _execute_canonical_action_locked(
        self,
        request: Mapping[str, Any],
        world: QiWorldPort,
        *,
        crash_after_dispatch: bool = False,
        withhold_observation: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(request, Mapping) or set(request) != {
            "user",
            "identity_scope",
            "task_scope",
            "request_id",
            "text",
            "selected_action",
            "value",
            "authority",
            "required_authority",
            "authorization_path",
            "plan_receipt_sha256",
        }:
            raise ProviderError("canonical action request key set is invalid")
        session_id, identity_scope, task_scope, request_id = (
            self._canonical_scopes(request)
        )
        _, receipt_store, journal, _, store, initial = self._require_canonical()
        try:
            plan_receipt = receipt_store.get(str(request["plan_receipt_sha256"]))
        except CanonicalRuntimeError as error:
            raise ProviderError(f"canonical plan receipt is invalid: {error}") from error
        decision = plan_receipt.get("result", {}).get("decision", {})
        if (
            plan_receipt.get("operation") != "plan"
            or plan_receipt.get("identity_scope") != identity_scope
            or plan_receipt.get("task_scope") != task_scope
            or decision.get("selected_action") != request.get("selected_action")
        ):
            raise ProviderError("action is not authorized by the scoped field plan")
        text = request.get("text")
        if not isinstance(text, str):
            raise ProviderError("action text is invalid")
        value = request.get("value")
        authority = request.get("authority")
        required_authority = request.get("required_authority")
        authorization_path = request.get("authorization_path")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or not -1.0 <= float(value) <= 1.0
            or isinstance(authority, bool)
            or not isinstance(authority, (int, float))
            or not math.isfinite(float(authority))
            or isinstance(required_authority, bool)
            or not isinstance(required_authority, (int, float))
            or not math.isfinite(float(required_authority))
            or not 0.0 <= float(authority) <= 1.0
            or not 0.0 <= float(required_authority) <= 1.0
            or not isinstance(authorization_path, Sequence)
            or isinstance(authorization_path, (str, bytes, bytearray))
            or not 1 <= len(authorization_path) <= 8
            or any(
                not isinstance(item, str)
                or not item
                or len(item.encode("utf-8")) > MAX_SESSION_ID
                for item in authorization_path
            )
        ):
            raise ProviderError("canonical action authorization is invalid")
        if float(authority) < float(required_authority):
            raise ProviderError("action proposal lacks the required authority")
        action_instance_id = journal.action_instance_id(
            identity_scope=identity_scope,
            task_scope=task_scope,
            request_id=request_id,
        )
        request_sha256 = _sha256(request)
        existing = journal.load(action_instance_id)
        if existing is not None:
            proposal = self._action_event(existing, "proposed")
            if proposal is None or proposal.get("request_sha256") != request_sha256:
                raise ProviderError("action request identity was reused with new content")
            return self._resume_action(
                existing,
                world,
                withhold_observation=withhold_observation,
            )

        try:
            descriptors = world.describe_actions(world.logical_tick)
            descriptor = next(
                (
                    item
                    for item in descriptors
                    if item.action_id == request["selected_action"]
                ),
                None,
            )
        except (AttributeError, QiWorldError) as error:
            raise ProviderError(f"world action descriptors are unavailable: {error}") from error
        if descriptor is None:
            raise ProviderError("selected action is not available in the current world")

        with self._session_lock(session_id):
            loaded = store.load(session_id)
            shared = store.initial(initial) if loaded is None else loaded[0]
            field_sha256 = store.layout.state_sha256(shared)
            if plan_receipt["state_out_sha256"] != field_sha256:
                raise ProviderError("field changed after the action plan")
            world_sha256 = world.state_sha256
            tick = world.logical_tick
            proposal_id = "proposal." + action_instance_id[4:36]
            idempotency_key = _sha256(
                {
                    "action_instance_id": action_instance_id,
                    "world_id": world.world_id,
                    "episode_id": world.episode_id,
                    "world_state_sha256": world_sha256,
                    "world_revision": tick,
                }
            )
            selected_action = str(request["selected_action"])
            requested_values: Sequence[tuple[str, float]] = (
                ()
                if selected_action == "action.hold"
                else (
                    (
                        "gaze.pitch"
                        if selected_action.endswith(("up", "down"))
                        else "gaze.yaw",
                        float(value),
                    ),
                )
            )
            try:
                action = QiActionCommand.make(
                    world_id=world.world_id,
                    episode_id=world.episode_id,
                    action_id=str(request["selected_action"]),
                    logical_tick=tick,
                    requested_values=requested_values,
                    profile_sha256=world.profile_sha256,
                    descriptor_sha256=descriptor.descriptor_sha256,
                    state_before_sha256=world_sha256,
                    current_sha256=world_sha256,
                    idempotency_key=idempotency_key,
                    parent_step_id=f"step.{tick}",
                    proposal_id=proposal_id,
                    target_actuator=descriptor.target_actuator,
                    body_frame_id=descriptor.body_frame_id,
                    session_id=world.session_id,
                    cycle_number=tick,
                    committed_prior_head_sha256=world_sha256,
                )
                intent = QiWorldTickIntent.make(
                    world_id=world.world_id,
                    episode_id=world.episode_id,
                    profile_sha256=world.profile_sha256,
                    session_id=world.session_id,
                    cycle_number=tick,
                    from_tick=tick,
                    committed_prior_head_sha256=world_sha256,
                    body_frame_id=world.body_frame_id,
                    action=action,
                    idempotency_key=idempotency_key,
                )
            except QiWorldError as error:
                raise ProviderError(f"canonical world action is invalid: {error}") from error
            proposal_payload = {
                "request_sha256": request_sha256,
                "text": text,
                "selected_action": request["selected_action"],
                "value": float(value),
                "identity_scope": identity_scope,
                "task_scope": task_scope,
                "predecessor_field_sha256": field_sha256,
                "predecessor_world_sha256": world_sha256,
                "world_revision": tick,
                "command_sha256": action.command_sha256,
                "plan_receipt_sha256": request["plan_receipt_sha256"],
                "required_authority": float(required_authority),
                "valid_from_revision": tick,
                "valid_until_revision": tick + 1,
                "action": action.payload(),
            }
            try:
                record = journal.propose(
                    identity_scope=identity_scope,
                    task_scope=task_scope,
                    request_id=request_id,
                    payload=proposal_payload,
                )
            except CanonicalRuntimeError as error:
                raise ProviderError(f"could not persist action proposal: {error}") from error
            try:
                record = journal.append(
                    action_instance_id,
                    expected=("proposed",),
                    stage="authorized",
                    payload={
                        "authority": float(authority),
                        "required_authority": float(required_authority),
                        "authorization_path": list(authorization_path),
                    },
                )
                record = journal.append(
                    action_instance_id,
                    expected=("authorized",),
                    stage="dispatch_intent",
                    payload={"intent": intent.payload()},
                )
            except CanonicalRuntimeError as error:
                raise ProviderError(f"could not journal dispatch intent: {error}") from error
            try:
                ack = world.advance_tick(intent)
            except QiWorldError as error:
                self._mark_action_unresolved(
                    record,
                    reason=f"world dispatch result is unknown: {error}",
                )
                raise ProviderError(
                    "world dispatch is unresolved; the provider will not retry blindly"
                ) from error
            if crash_after_dispatch:
                raise ProviderError("simulated crash after world effect before outcome write")
            try:
                record = journal.append(
                    action_instance_id,
                    expected=("dispatch_intent",),
                    stage="outcome_pending",
                    payload={"ack": ack.payload()},
                )
            except CanonicalRuntimeError as error:
                raise ProviderError(f"could not journal world outcome: {error}") from error
        if withhold_observation:
            return {
                "schema": "cassi.canonical-action-result.v1",
                "action_instance_id": action_instance_id,
                "stage": "outcome_pending",
                "consolidated_once": False,
            }
        return self._consolidate_action(record)

    def reconcile_canonical_actions(
        self,
        *,
        identity_scope: str,
        world: QiWorldPort,
    ) -> list[dict[str, Any]]:
        _, _, journal, _, _, _ = self._require_canonical()
        results: list[dict[str, Any]] = []
        with self._session_lock(identity_scope), journal.identity_transition(identity_scope):
            try:
                records = journal.records()
            except CanonicalRuntimeError as error:
                raise ProviderError(f"could not scan action journal: {error}") from error
            for record in records:
                if record["identity_scope"] != identity_scope:
                    continue
                if self._action_stage(record) in {"observed", "unresolved"}:
                    continue
                results.append(self._resume_action(record, world))
        return results

    @staticmethod
    def _world_identifier(value: Any, label: str) -> str:
        if (
            not isinstance(value, str)
            or not 1 <= len(value) <= 128
            or any(
                character
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-"
                for character in value
            )
        ):
            raise ProviderError(f"{label} is invalid")
        return value

    @staticmethod
    def _world_ledger(
        metadata: Mapping[str, Any], key: str
    ) -> dict[str, dict[str, Any]]:
        raw = metadata.get(key, {})
        if not isinstance(raw, Mapping):
            raise ProviderError("stored world ledger is malformed")
        ledger: dict[str, dict[str, Any]] = {}
        for request_id, entry in raw.items():
            if not isinstance(request_id, str) or not isinstance(entry, Mapping):
                raise ProviderError("stored world ledger entry is malformed")
            ledger[request_id] = dict(entry)
        return ledger

    @staticmethod
    def _bounded_world_ledger(
        ledger: Mapping[str, Mapping[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        bounded = {str(key): dict(value) for key, value in ledger.items()}
        while len(bounded) > WORLD_LEDGER_LIMIT:
            del bounded[next(iter(bounded))]
        return bounded

    @staticmethod
    def _world_turn_assistant(
        program: Mapping[str, Any] | None, clarification: str | None
    ) -> str:
        if program is None:
            return (
                "I need clarification before staging a particle program: "
                + str(clarification)
            )
        target = str(program["target"]["type"]).replace("_", " ")
        selection = str(program["selection"]["type"]).replace("_", " ")
        return (
            f"Staged a {target} arrangement for the {selection} selection. "
            "Preview it before Apply; the world has not changed."
        )

    @staticmethod
    def _world_result_assistant(
        request_id: str, outcome: Mapping[str, Any]
    ) -> str:
        raw_status = outcome.get("status")
        if isinstance(raw_status, str) and raw_status:
            status = raw_status
        else:
            status = "applied" if outcome.get("ok") is True else "rejected"
        backend = outcome.get("backend")
        suffix = (
            f" through {backend}"
            if isinstance(backend, str) and backend
            else ""
        )
        return f"Observed the {status} result for request {request_id}{suffix}."

    def _observe_world_exchange(
        self,
        *,
        session_id: str,
        event_id: str,
        prompt: str,
        continuation: str,
        shared: QiFieldState,
        metadata: Mapping[str, Any],
    ) -> tuple[QiFieldState, dict[str, Any], dict[str, Any]]:
        controller, _, initial, store, _ = self._require()
        exchange_digest = _sha256(
            {"prompt": prompt, "continuation": continuation}
        )
        exchanges = self._world_ledger(
            metadata, WORLD_EXCHANGES_METADATA_KEY
        )
        prior = exchanges.get(event_id)
        if prior is not None and prior.get("exchange_digest") != exchange_digest:
            raise ProviderError("world field observation event conflict")
        exchanges[event_id] = {
            "prompt": prompt,
            "continuation": continuation,
            "exchange_digest": exchange_digest,
        }
        exchanges = self._bounded_world_ledger(exchanges)

        encoded: list[tuple[bytes, bytes]] = []
        while exchanges:
            encoded = [
                (
                    str(entry["prompt"]).encode("utf-8"),
                    str(entry["continuation"]).encode("utf-8"),
                )
                for entry in exchanges.values()
            ]
            event_count = sum(
                len(controller.codec.encode_training_exchange(prompt_bytes, reply_bytes))
                for prompt_bytes, reply_bytes in encoded
            )
            if event_count <= controller.config.trajectory_capacity:
                break
            del exchanges[next(iter(exchanges))]
        if event_id not in exchanges:
            raise ProviderError("world field observation exceeds trajectory capacity")
        phi = store.layout.phi(shared)
        state_in_sha256 = controller.state_sha256(phi)
        tape_in_sha256 = controller.tape_sha256(phi)
        try:
            observed = controller.rebuild_exchanges(phi, initial, encoded)
        except (QiFieldError, CassiFieldLanguageError) as error:
            raise ProviderError(
                "world field observation failed; prior checkpoint retained: "
                f"{error}"
            ) from error
        state_out_sha256 = controller.state_sha256(observed)
        tape_out_sha256 = controller.tape_sha256(observed)
        updated_metadata = dict(metadata)
        updated_metadata[WORLD_EXCHANGES_METADATA_KEY] = exchanges
        updated_shared = store.layout.with_phi(shared, observed)
        checkpoint, checkpoint_sha256 = store.save(
            session_id, updated_shared, updated_metadata
        )
        return updated_shared, updated_metadata, {
            "schema": "cassi.world-field-observation.v1",
            "event_id": event_id,
            "exchange_digest": exchange_digest,
            "exchange_count": len(exchanges),
            "state_in_sha256": state_in_sha256,
            "state_out_sha256": state_out_sha256,
            "tape_in_sha256": tape_in_sha256,
            "tape_out_sha256": tape_out_sha256,
            "checkpoint": str(checkpoint),
            "checkpoint_sha256": checkpoint_sha256,
        }

    def world_turn(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request, Mapping) or not set(request) <= {
            "user",
            "world_id",
            "message",
            "context",
            "program",
            "request_id",
            "max_tokens",
        }:
            raise ProviderError("world turn request keys are invalid")
        session_id = _session_id(request)
        world_id = self._world_identifier(request.get("world_id"), "world_id")
        message = request.get("message")
        if (
            not isinstance(message, str)
            or not message.strip()
            or len(message.encode("utf-8")) > 16 * 1024
        ):
            raise ProviderError("world turn message is invalid")
        context = request.get("context", {})
        if not isinstance(context, Mapping) or len(_canonical(context)) > 64 * 1024:
            raise ProviderError("world turn context is invalid")
        raw_request_id = request.get("request_id", uuid.uuid4().hex)
        request_id = self._world_identifier(raw_request_id, "request_id")

        explicit = request.get("program")
        planner = "explicit"
        program: dict[str, Any] | None
        clarification: str | None = None
        if explicit is not None:
            if not isinstance(explicit, Mapping):
                raise ProviderError("world turn program must be an object")
            try:
                normalized_program = normalize_program(explicit)
            except ParticleProgramError as error:
                raise ProviderError(f"world turn program is invalid: {error}") from error
            program = normalized_program
            if normalized_program["request_id"] != request_id:
                raise ProviderError("world turn program request_id mismatch")
        else:
            try:
                program, planner = compile_particle_program(
                    message,
                    context,
                    request_id=request_id,
                )
            except ParticleProgramError as error:
                program = None
                planner = "clarification"
                clarification = str(error)

        input_digest = _sha256(
            {
                "world_id": world_id,
                "message": message,
                "context": context,
                "program": program,
            }
        )
        controller, _, initial, store, _ = self._require()
        with self._session_lock(session_id):
            loaded = store.load(session_id)
            if loaded is not None:
                prior_turns = self._world_ledger(
                    loaded[1], WORLD_TURNS_METADATA_KEY
                )
                prior = prior_turns.get(request_id)
                if prior is not None:
                    if prior.get("input_digest") != input_digest:
                        raise ProviderError("world turn request_id conflict")
                    response = prior.get("response")
                    if not isinstance(response, Mapping):
                        raise ProviderError("stored world turn response is malformed")
                    return dict(response)

            shared = store.initial(initial) if loaded is None else loaded[0]
            metadata = _metadata(None if loaded is None else loaded[1])
            assistant = self._world_turn_assistant(program, clarification)
            shared, metadata, field_receipt = self._observe_world_exchange(
                session_id=session_id,
                event_id=f"turn:{request_id}",
                prompt=message,
                continuation=assistant,
                shared=shared,
                metadata=metadata,
            )
            response = {
                "schema": "cassi.world-turn.v1",
                "world_id": world_id,
                "session_id": session_id,
                "request_id": request_id,
                "assistant": assistant,
                "staged_program": program,
                "program_digest": (
                    program_digest(program) if program is not None else None
                ),
                "planner": planner,
                "clarification": clarification,
                "field_receipt": field_receipt,
            }
            turns = self._world_ledger(metadata, WORLD_TURNS_METADATA_KEY)
            turns[request_id] = {
                "input_digest": input_digest,
                "response": response,
            }
            metadata[WORLD_TURNS_METADATA_KEY] = self._bounded_world_ledger(
                turns
            )
            store.save(session_id, shared, metadata)
            return response

    def world_result(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request, Mapping) or set(request) != {
            "user",
            "world_id",
            "request_id",
            "program_digest",
            "outcome",
        }:
            raise ProviderError("world result request keys are invalid")
        session_id = _session_id(request)
        world_id = self._world_identifier(request.get("world_id"), "world_id")
        request_id = self._world_identifier(
            request.get("request_id"), "request_id"
        )
        expected_program_digest = request.get("program_digest")
        if not _is_digest(expected_program_digest):
            raise ProviderError("world result program digest is invalid")
        outcome = request.get("outcome")
        if not isinstance(outcome, Mapping) or len(_canonical(outcome)) > 64 * 1024:
            raise ProviderError("world result outcome is invalid")
        result_digest = _sha256(
            {
                "world_id": world_id,
                "request_id": request_id,
                "program_digest": expected_program_digest,
                "outcome": outcome,
            }
        )
        _, _, _, store, _ = self._require()
        with self._session_lock(session_id):
            loaded = store.load(session_id)
            if loaded is None:
                raise ProviderError("world result has no field session")
            shared, metadata = loaded[0], dict(loaded[1])
            turns = self._world_ledger(metadata, WORLD_TURNS_METADATA_KEY)
            turn = turns.get(request_id)
            if turn is None:
                raise ProviderError("world result has no staged turn")
            turn_response = turn.get("response")
            if not isinstance(turn_response, Mapping):
                raise ProviderError("stored world turn response is malformed")
            if turn_response.get("program_digest") != expected_program_digest:
                raise ProviderError("world result program digest mismatch")
            results = self._world_ledger(metadata, WORLD_RESULTS_METADATA_KEY)
            prior = results.get(request_id)
            if prior is not None:
                if prior.get("result_digest") != result_digest:
                    raise ProviderError("world result request_id conflict")
                response = prior.get("response")
                if not isinstance(response, Mapping):
                    raise ProviderError("stored world result response is malformed")
                return dict(response)

            result_summary = {
                "request_id": request_id,
                "program_digest": expected_program_digest,
                "result_digest": result_digest,
                "status": outcome.get("status"),
                "ok": outcome.get("ok"),
                "backend": outcome.get("backend"),
                "applied": outcome.get("applied"),
                "error": outcome.get("error"),
            }
            result_text = (
                "World execution result: "
                + _canonical(result_summary).decode("utf-8")
            )
            assistant = self._world_result_assistant(request_id, outcome)
            shared, metadata, field_receipt = self._observe_world_exchange(
                session_id=session_id,
                event_id=f"result:{request_id}",
                prompt=result_text,
                continuation=assistant,
                shared=shared,
                metadata=metadata,
            )
            observed_status = (
                str(outcome["status"])
                if isinstance(outcome.get("status"), str) and outcome["status"]
                else ("applied" if outcome.get("ok") is True else "rejected")
            )
            response = {
                "schema": "cassi.world-result.v1",
                "world_id": world_id,
                "session_id": session_id,
                "request_id": request_id,
                "program_digest": expected_program_digest,
                "result_digest": result_digest,
                "assistant": assistant,
                "field_receipt": field_receipt,
                "observed_once": True,
                "status": observed_status,
            }
            results = self._world_ledger(metadata, WORLD_RESULTS_METADATA_KEY)
            results[request_id] = {
                "result_digest": result_digest,
                "response": response,
            }
            metadata[WORLD_RESULTS_METADATA_KEY] = (
                self._bounded_world_ledger(results)
            )
            store.save(session_id, shared, metadata)
            return response

    @staticmethod
    def _validate_stream_id(value: Any) -> str:
        if (
            not isinstance(value, str)
            or not 1 <= len(value) <= 128
            or any(
                character
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-"
                for character in value
            )
        ):
            raise ProviderError("stream_id is invalid")
        return value

    @staticmethod
    def _stream_watermark(
        metadata: Mapping[str, Any],
        stream_id: str,
        *,
        key: str = CONTEXT_STREAM_METADATA_KEY,
    ) -> tuple[int, str]:
        streams = metadata.get(key, {})
        if not isinstance(streams, Mapping):
            raise ProviderError("stored stream watermarks are malformed")
        value = streams.get(stream_id)
        if value is None:
            return 0, EMPTY_CONTEXT_EVENT_ID
        if not isinstance(value, Mapping) or set(value) != {"sequence", "event_id"}:
            raise ProviderError("stored context stream watermark is malformed")
        sequence = value.get("sequence")
        event_id = value.get("event_id")
        if (
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence < 0
            or not _is_digest(event_id)
        ):
            raise ProviderError("stored context stream watermark is malformed")
        return sequence, str(event_id)

    @staticmethod
    def _validate_record(record: Any) -> dict[str, str]:
        required_keys = {"id", "content", "node_type", "revision"}
        if (
            not isinstance(record, Mapping)
            or not required_keys <= set(record)
            or not set(record) <= required_keys | {"field_address"}
        ):
            raise ProviderError("memory record is invalid")
        record_id = record.get("id")
        content = record.get("content")
        node_type = record.get("node_type")
        revision = record.get("revision")
        field_address = record.get("field_address")
        if (
            not isinstance(record_id, str)
            or not record_id
            or len(record_id.encode("utf-8")) > MAX_SESSION_ID
        ):
            raise ProviderError("memory record id is invalid")
        if (
            not isinstance(content, str)
            or len(content.encode("utf-8")) > MAX_CONTEXT_CANDIDATE_BYTES
        ):
            raise ProviderError("memory record content is invalid")
        if not isinstance(node_type, str) or len(node_type.encode("utf-8")) > 64:
            raise ProviderError("memory node_type is invalid")
        if not _is_digest(revision):
            raise ProviderError("memory record revision is invalid")
        if field_address is not None and (
            not isinstance(field_address, str)
            or len(field_address) != 32
            or any(character not in "0123456789abcdef" for character in field_address)
        ):
            raise ProviderError("memory record field_address is invalid")
        normalized = {
            "id": record_id,
            "content": content,
            "node_type": node_type,
            "revision": str(revision),
        }
        if field_address is not None:
            normalized["field_address"] = field_address
        return normalized

    @staticmethod
    def _validate_candidates(
        candidates: Any, *, limit: int, label: str
    ) -> list[dict[str, Any]]:
        if (
            not isinstance(candidates, Sequence)
            or isinstance(candidates, (str, bytes, bytearray))
            or len(candidates) > limit
        ):
            raise ProviderError(f"{label} candidates are invalid")
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        required_keys = {
            "id",
            "record_id",
            "revision",
            "start_byte",
            "end_byte",
            "text",
        }
        for index, candidate in enumerate(candidates):
            if (
                not isinstance(candidate, Mapping)
                or not required_keys <= set(candidate)
                or not set(candidate) <= required_keys | {"field_address"}
            ):
                raise ProviderError(f"{label} candidate {index} has an unexpected key set")
            candidate_id = candidate.get("id")
            record_id = candidate.get("record_id")
            revision = candidate.get("revision")
            start_byte = candidate.get("start_byte")
            end_byte = candidate.get("end_byte")
            text = candidate.get("text")
            field_address = candidate.get("field_address")
            text_bytes = text.encode("utf-8") if isinstance(text, str) else b""
            if (
                not isinstance(candidate_id, str)
                or not candidate_id
                or len(candidate_id.encode("utf-8")) > MAX_SESSION_ID
                or candidate_id in seen
                or not isinstance(record_id, str)
                or not record_id
                or len(record_id.encode("utf-8")) > MAX_SESSION_ID
                or not _is_digest(revision)
                or isinstance(start_byte, bool)
                or not isinstance(start_byte, int)
                or start_byte < 0
                or isinstance(end_byte, bool)
                or not isinstance(end_byte, int)
                or end_byte <= start_byte
                or end_byte - start_byte != len(text_bytes)
                or not text_bytes
                or len(text_bytes) > MAX_CONTEXT_CANDIDATE_BYTES
                or (
                    field_address is not None
                    and (
                        not isinstance(field_address, str)
                        or len(field_address) != 32
                        or any(
                            character not in "0123456789abcdef"
                            for character in field_address
                        )
                    )
                )
            ):
                raise ProviderError(f"{label} candidate {index} is invalid")
            seen.add(candidate_id)
            item = {
                "id": candidate_id,
                "record_id": record_id,
                "revision": str(revision),
                "start_byte": start_byte,
                "end_byte": end_byte,
                "text": text,
            }
            if field_address is not None:
                item["field_address"] = field_address
            normalized.append(item)
        return normalized

    @staticmethod
    def _validate_context_session_id(value: Any) -> str:
        if (
            not isinstance(value, str)
            or len(value.encode("utf-8")) > MAX_SESSION_ID
        ):
            raise ProviderError("context_session_id is invalid")
        return value

    @staticmethod
    def _validate_action_event(value: Any) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise ProviderError("action event must be an object")
        base_keys = {
            "episode_id",
            "action_id",
            "kind",
            "stage",
            "required_authority",
            "reversible",
            "authorization_path",
        }
        stage = value.get("stage")
        required_keys = base_keys | ({"outcome"} if stage == "outcome" else set())
        allowed_keys = required_keys | ({"effects"} if stage == "outcome" else set())
        authority = value.get("required_authority")
        authorization_path = value.get("authorization_path")
        effects = value.get("effects", ())
        if (
            set(value) - allowed_keys
            or required_keys - set(value)
            or stage not in {"start", "outcome"}
            or any(
                not isinstance(value.get(key), str)
                or not value[key]
                or len(value[key].encode("utf-8")) > MAX_SESSION_ID
                for key in ("episode_id", "action_id", "kind")
            )
            or isinstance(authority, bool)
            or not isinstance(authority, (int, float))
            or not math.isfinite(float(authority))
            or not 0.0 <= float(authority) <= 1.0
            or not isinstance(value.get("reversible"), bool)
            or not isinstance(authorization_path, Sequence)
            or isinstance(authorization_path, (str, bytes, bytearray))
            or not 1 <= len(authorization_path) <= 8
            or any(
                not isinstance(item, str)
                or not item
                or len(item.encode("utf-8")) > MAX_SESSION_ID
                for item in authorization_path
            )
            or (
                stage == "outcome"
                and value.get("outcome") not in {"completed", "error"}
            )
            or not isinstance(effects, Sequence)
            or isinstance(effects, (str, bytes, bytearray))
            or len(effects) > 32
        ):
            raise ProviderError("action event is invalid")
        normalized_effects: list[dict[str, Any]] = []
        effect_keys = {
            "record_id",
            "before_revision",
            "after_revision",
            "semantic_kind",
            "start_byte",
            "end_byte",
        }
        for effect in effects:
            if not isinstance(effect, Mapping) or set(effect) != effect_keys:
                raise ProviderError("action effect is invalid")
            start = effect["start_byte"]
            end = effect["end_byte"]
            if (
                not isinstance(effect["record_id"], str)
                or not effect["record_id"]
                or len(effect["record_id"].encode("utf-8")) > MAX_SESSION_ID
                or not _is_digest(effect["before_revision"])
                or not _is_digest(effect["after_revision"])
                or not isinstance(effect["semantic_kind"], str)
                or not effect["semantic_kind"]
                or len(effect["semantic_kind"].encode("utf-8")) > MAX_SESSION_ID
                or isinstance(start, bool)
                or isinstance(end, bool)
                or not isinstance(start, int)
                or not isinstance(end, int)
                or start < 0
                or end < start
            ):
                raise ProviderError("action effect is invalid")
            normalized_effects.append(dict(effect))
        normalized = {
            "episode_id": value["episode_id"],
            "action_id": value["action_id"],
            "kind": value["kind"],
            "stage": stage,
            "required_authority": authority,
            "reversible": value["reversible"],
            "authorization_path": list(authorization_path),
        }
        if stage == "outcome":
            normalized["outcome"] = value["outcome"]
            if normalized_effects:
                normalized["effects"] = normalized_effects
        return normalized


    @classmethod
    def _validate_context_payload(
        cls, payload: Any
    ) -> tuple[dict[str, Any], bool, list[str]]:
        if not isinstance(payload, Mapping):
            raise ProviderError("context journal payload must be an object")
        kind = payload.get("kind")
        context_session_id = cls._validate_context_session_id(
            payload.get("context_session_id", "")
        )
        if kind == "memory":
            memory_keys = {
                "kind",
                "context_session_id",
                "operation",
                "record",
            }
            keys = set(payload)
            if not memory_keys <= keys or not keys <= memory_keys | {
                "previous_record",
                "action",
            }:
                raise ProviderError("memory payload has an unexpected key set")
            operation = payload.get("operation")
            if operation not in {
                "store",
                "update",
                "delete",
                "connect",
                "disconnect",
            }:
                raise ProviderError("memory operation is invalid")
            normalized: dict[str, Any] = {
                "kind": "memory",
                "context_session_id": context_session_id,
                "operation": operation,
                "record": cls._validate_record(payload.get("record")),
            }
            if "previous_record" in payload:
                previous_record = cls._validate_record(
                    payload.get("previous_record")
                )
                if (
                    operation != "update"
                    or previous_record["id"] != normalized["record"]["id"]
                ):
                    raise ProviderError(
                        "previous_record is valid only for the same updated record"
                    )
                normalized["previous_record"] = previous_record
            if "action" in payload:
                action = cls._validate_action_event(payload.get("action"))
                if (
                    action["stage"] == "outcome"
                    and (
                        operation != "update"
                        or "previous_record" not in normalized
                    )
                ):
                    raise ProviderError(
                        "action outcomes require one exact record update"
                    )
                normalized["action"] = action
            return normalized, False, []
        feedback_keys = {
            "kind",
            "context_session_id",
            "turn_id",
            "query",
            "candidates",
            "outcome",
        }
        if (
            kind != "feedback"
            or frozenset(payload) not in {
                frozenset(feedback_keys),
                frozenset(feedback_keys | {"tool_result"}),
            }
        ):
            raise ProviderError("feedback payload has an unexpected key set")
        turn_id = payload.get("turn_id")
        query = payload.get("query")
        outcome = payload.get("outcome")
        if isinstance(turn_id, bool) or not isinstance(turn_id, int) or turn_id < 0:
            raise ProviderError("feedback turn_id is invalid")
        if (
            not isinstance(query, str)
            or not query
            or len(query.encode("utf-8")) > MAX_CONTEXT_QUERY_BYTES
        ):
            raise ProviderError("feedback query is invalid")
        if outcome not in {"completed", "error", "cancelled", "unknown"}:
            raise ProviderError("feedback outcome is invalid")
        normalized_candidates = cls._validate_candidates(
            payload.get("candidates"),
            limit=MAX_CONTEXT_FEEDBACK_CANDIDATES,
            label="feedback",
        )
        normalized = {
            "kind": "feedback",
            "context_session_id": context_session_id,
            "turn_id": turn_id,
            "query": query,
            "candidates": normalized_candidates,
            "outcome": outcome,
        }
        if "tool_result" in payload:
            tool_result = payload.get("tool_result")
            if (
                not isinstance(tool_result, Mapping)
                or set(tool_result) != {"id", "name", "is_error"}
                or not isinstance(tool_result.get("id"), str)
                or not tool_result["id"]
                or len(tool_result["id"].encode("utf-8")) > MAX_SESSION_ID
                or not isinstance(tool_result.get("name"), str)
                or not tool_result["name"]
                or len(tool_result["name"].encode("utf-8")) > MAX_SESSION_ID
                or not isinstance(tool_result.get("is_error"), bool)
                or outcome not in {"completed", "error"}
                or tool_result["is_error"] != (outcome == "error")
            ):
                raise ProviderError("feedback tool_result is invalid")
            normalized["tool_result"] = {
                "id": tool_result["id"],
                "name": tool_result["name"],
                "is_error": tool_result["is_error"],
            }
        return (
            normalized,
            outcome == "completed" and bool(normalized_candidates),
            [candidate["id"] for candidate in normalized_candidates],
        )






    def recall_context(self, request: Mapping[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        if not isinstance(request, Mapping):
            raise ProviderError("context recall request must be an object")
        query = request.get("query")
        if (
            not isinstance(query, str)
            or not query.strip()
            or len(query.encode("utf-8")) > MAX_CONTEXT_QUERY_BYTES
        ):
            raise ProviderError("query must be bounded nonempty text")
        context_session_id = self._validate_context_session_id(
            request.get("context_session_id")
        )
        raw_addresses = request.get("addresses")
        if (
            not isinstance(raw_addresses, Sequence)
            or isinstance(raw_addresses, (str, bytes, bytearray))
            or len(raw_addresses) > MAX_MNEMIC_RECALL_ADDRESSES
        ):
            raise ProviderError("field address manifest is invalid")
        addresses: list[bytes] = []
        seen: set[str] = set()
        for index, value in enumerate(raw_addresses):
            if (
                not isinstance(value, str)
                or len(value) != 32
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise ProviderError(f"field address {index} is invalid")
            if value in seen:
                continue
            seen.add(value)
            addresses.append(bytes.fromhex(value))
        session_id = _session_id(request)
        _controller, _, initial, store, _ = self._require()
        mnemic_controller = self.mnemic_controller
        if mnemic_controller is None:
            raise ProviderError("persistent field provider is not started")
        with self._session_lock(session_id):
            load_started = time.perf_counter()
            loaded = store.load(session_id)
            shared = store.initial(initial) if loaded is None else loaded[0]
            mnemic = store.layout.mnemic(shared)
            load_ms = (time.perf_counter() - load_started) * 1_000
            scoring_started = time.perf_counter()
            try:
                recall = mnemic_controller.recall(
                    mnemic,
                    query,
                    candidate_addresses=addresses,
                )
            except QiFieldError as error:
                raise ProviderError(f"mnemic field recall failed: {error}") from error
            scoring_ms = (time.perf_counter() - scoring_started) * 1_000
        return {
            "schema": "cassi.mnemic.field-recall.v1",
            "session_id": session_id,
            "context_session_id": context_session_id,
            "address": None if recall.address is None else recall.address.hex(),
            "signal": recall.signal,
            "selection_margin": recall.selection_margin,
            "availability": recall.availability,
            "minimum_bit_margin": recall.minimum_bit_margin,
            "mean_bit_margin": recall.mean_bit_margin,
            "state_sha256": store.layout.state_sha256(shared),
            "mnemic_state_sha256": recall.state_sha256,
            "candidate_count": len(addresses),
            "timings_ms": {
                "load": load_ms,
                "scoring": scoring_ms,
                "total": (time.perf_counter() - started) * 1_000,
            },
        }

    def observe_context(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request, Mapping):
            raise ProviderError("context observation request must be an object")
        stream_id = self._validate_stream_id(request.get("stream_id"))
        sequence = request.get("sequence")
        previous_event_id = request.get("previous_event_id")
        event_id = request.get("event_id")
        if (
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence < 1
            or not _is_digest(previous_event_id)
            or not _is_digest(event_id)
        ):
            raise ProviderError("context journal event identity is invalid")
        payload, completed, requested_ids = self._validate_context_payload(
            request.get("payload")
        )
        expected_event_id = _sha256(
            {
                "stream_id": stream_id,
                "sequence": sequence,
                "previous_event_id": previous_event_id,
                "payload": payload,
            }
        )
        if event_id != expected_event_id:
            raise ProviderError("context journal event hash mismatch")
        if len(_canonical(request)) > MAX_CONTEXT_EVENT_BYTES:
            raise ProviderError("context journal event exceeds the bounded limit")
        event_id_text = str(event_id)
        _controller, _, initial, store, _ = self._require()
        mnemic_controller = self.mnemic_controller
        if mnemic_controller is None:
            raise ProviderError("persistent field provider is not started")
        session_id = _session_id(request)
        with self._session_lock(session_id):
            loaded = store.load(session_id)
            shared = store.initial(initial) if loaded is None else loaded[0]
            metadata = _metadata(None if loaded is None else loaded[1])
            committed_sequence, committed_event_id = self._stream_watermark(
                metadata, stream_id
            )
            mnemic = store.layout.mnemic(shared)
            state_in_sha256 = store.layout.state_sha256(shared)
            mnemic_in_sha256 = mnemic_controller.state_sha256(mnemic)
            if sequence == committed_sequence and event_id == committed_event_id:
                path = store.path_for(session_id)
                if not path.is_file():
                    raise ProviderError("committed context checkpoint is missing")
                return {
                    "schema": "cassi.mnemic.field-observation.v1",
                    "session_id": session_id,
                    "state_in_sha256": state_in_sha256,
                    "state_out_sha256": state_in_sha256,
                    "mnemic_state_in_sha256": mnemic_in_sha256,
                    "mnemic_state_out_sha256": mnemic_in_sha256,
                    "condensed": False,
                    "selected_ids": requested_ids,
                    "duplicate": True,
                    "stream": {
                        "stream_id": stream_id,
                        "sequence": sequence,
                        "event_id": event_id_text,
                    },
                    "checkpoint": str(path),
                    "checkpoint_sha256": _sha256(path.read_bytes()),
                }
            if (
                sequence != committed_sequence + 1
                or previous_event_id != committed_event_id
            ):
                raise ProviderError(
                    "context journal sequence or predecessor mismatch"
                )
            streams = dict(metadata[CONTEXT_STREAM_METADATA_KEY])
            if stream_id not in streams and len(streams) >= MAX_CONTEXT_STREAMS:
                raise ProviderError("context stream limit reached")

            working = mnemic
            transitions: list[dict[str, Any]] = []

            def inhibit(cue: str, address: str) -> None:
                nonlocal working
                if not cue.strip():
                    return
                working = mnemic_controller.inhibit(
                    working,
                    cue=cue,
                    address=bytes.fromhex(address),
                )
                transitions.append(
                    {"operation": "inhibit", "address": address}
                )

            def condense(cue: str, address: str) -> None:
                nonlocal working
                if not cue.strip():
                    return
                working, receipt = mnemic_controller.condense(
                    working,
                    cue=cue,
                    address=bytes.fromhex(address),
                )
                transitions.append(
                    {
                        "operation": "condense",
                        "address": address,
                        "prediction_signal": receipt.prediction_signal,
                        "residual_rms": receipt.residual_rms,
                        "slow_energy_before": receipt.slow_energy_before,
                        "slow_energy_after": receipt.slow_energy_after,
                    }
                )

            try:
                if payload["kind"] == "memory":
                    operation = payload["operation"]
                    record = payload["record"]
                    field_address = record.get("field_address")
                    if operation == "update":
                        previous_record = payload.get("previous_record")
                        if (
                            isinstance(previous_record, Mapping)
                            and isinstance(previous_record.get("field_address"), str)
                        ):
                            inhibit(
                                str(previous_record["content"]),
                                str(previous_record["field_address"]),
                            )
                    if operation == "delete" and isinstance(field_address, str):
                        inhibit(record["content"], field_address)
                    elif (
                        operation in {"store", "update"}
                        and isinstance(field_address, str)
                    ):
                        condense(record["content"], field_address)
                elif payload["kind"] == "feedback" and completed:
                    for candidate in payload["candidates"]:
                        field_address = candidate.get("field_address")
                        if isinstance(field_address, str):
                            condense(payload["query"], field_address)

                shared_out = store.layout.with_mnemic(shared, working)
                streams[stream_id] = {
                    "sequence": sequence,
                    "event_id": event_id_text,
                }
                metadata[CONTEXT_STREAM_METADATA_KEY] = streams
                checkpoint, checkpoint_sha256 = store.save(
                    session_id,
                    shared_out,
                    metadata,
                )
            except (ProviderError, QiFieldError, OSError) as error:
                raise ProviderError(
                    "mnemic context observation failed; prior checkpoint retained: "
                    f"{error}"
                ) from error
        return {
            "schema": "cassi.mnemic.field-observation.v1",
            "session_id": session_id,
            "state_in_sha256": state_in_sha256,
            "state_out_sha256": store.layout.state_sha256(shared_out),
            "mnemic_state_in_sha256": mnemic_in_sha256,
            "mnemic_state_out_sha256": mnemic_controller.state_sha256(working),
            "condensed": any(
                transition["operation"] == "condense"
                for transition in transitions
            ),
            "selected_ids": requested_ids,
            "transitions": transitions,
            "duplicate": False,
            "stream": {
                "stream_id": stream_id,
                "sequence": sequence,
                "event_id": event_id_text,
            },
            "checkpoint": str(checkpoint),
            "checkpoint_sha256": checkpoint_sha256,
        }

    def context_status(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request, Mapping):
            raise ProviderError("context status request must be an object")
        stream_id = self._validate_stream_id(request.get("stream_id"))
        controller, _, _, store, provider_fingerprint = self._require()
        session_id = _session_id(request)
        with self._session_lock(session_id):
            path = store.path_for(session_id)
            if not path.is_file():
                return {
                    "session_id": session_id,
                    "engine_fingerprint": provider_fingerprint,
                    "checkpoint": {
                        "status": "missing",
                        "sha256": None,
                        "engine_fingerprint": None,
                    },
                    "stream": {
                        "stream_id": stream_id,
                        "sequence": 0,
                        "event_id": EMPTY_CONTEXT_EVENT_ID,
                    },
                }
            _, checkpoint_sha256, checkpoint_fingerprint = store.inspect(session_id)
            if not store.is_compatible_provider_fingerprint(checkpoint_fingerprint):
                return {
                    "session_id": session_id,
                    "engine_fingerprint": provider_fingerprint,
                    "checkpoint": {
                        "status": "incompatible",
                        "sha256": checkpoint_sha256,
                        "engine_fingerprint": checkpoint_fingerprint,
                    },
                    "stream": {
                        "stream_id": stream_id,
                        "sequence": 0,
                        "event_id": EMPTY_CONTEXT_EVENT_ID,
                    },
                }
            loaded = store.load(session_id)
            if loaded is None:
                raise ProviderError("context checkpoint disappeared during status")
            shared, metadata, _, _ = loaded
            state = store.layout.phi(shared)
            sequence, event_id = self._stream_watermark(metadata, stream_id)
            return {
                "session_id": session_id,
                "engine_fingerprint": provider_fingerprint,
                "checkpoint": {
                    "status": "compatible",
                    "sha256": checkpoint_sha256,
                    "engine_fingerprint": provider_fingerprint,
                },
                "stream": {
                    "stream_id": stream_id,
                    "sequence": sequence,
                    "event_id": event_id,
                },
                "state_sha256": controller.state_sha256(state),
                "tape_sha256": controller.tape_sha256(state),
                "config_fingerprint": controller.config_fingerprint,
            }

    def plan_counterflow(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request, Mapping):
            raise ProviderError("counterflow request must be an object")
        session_id = _session_id(request)
        runtime = self.counterflow_runtime
        if runtime is None:
            raise ProviderError("persistent field provider is not started")
        controller, _, initial, store, _ = self._require()
        runtime_request = {
            key: value
            for key, value in request.items()
            if key not in {"session_id", "user", "metadata"}
        }
        with self._session_lock(session_id):
            loaded = store.load(session_id)
            shared = store.initial(initial) if loaded is None else loaded[0]
            phi = store.layout.phi(shared)
            counterflow = store.layout.counterflow(shared)
            primary_sha256 = controller.state_sha256(phi)
            counterflow_sha256 = runtime.state_sha256(counterflow)
            try:
                result = runtime.plan(
                    runtime_request,
                    primary_field_sha256=primary_sha256,
                    counterflow_state=counterflow,
                )
            except QiFieldError as error:
                raise ProviderError(f"counterflow request is invalid: {error}") from error
            if (
                controller.state_sha256(phi) != primary_sha256
                or runtime.state_sha256(counterflow) != counterflow_sha256
            ):
                raise ProviderError("counterflow planning mutated a canonical field component")
            return {
                "session_id": session_id,
                "state_sha256": primary_sha256,
                "counterflow_state_sha256": counterflow_sha256,
                **result,
            }


    def commit_counterflow(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request, Mapping):
            raise ProviderError("counterflow commit request must be an object")
        session_id = _session_id(request)
        runtime = self.counterflow_runtime
        if runtime is None:
            raise ProviderError("persistent field provider is not started")
        controller, _, initial, store, _ = self._require()
        runtime_request = {
            key: value
            for key, value in request.items()
            if key not in {"session_id", "user", "metadata"}
        }
        try:
            commit = runtime.observed_commit(runtime_request)
        except QiFieldError as error:
            raise ProviderError(f"counterflow commit is invalid: {error}") from error

        with self._session_lock(session_id):
            loaded = store.load(session_id)
            shared = store.initial(initial) if loaded is None else loaded[0]
            metadata = _metadata(None if loaded is None else loaded[1])
            committed_sequence, committed_event_id = self._stream_watermark(
                metadata,
                commit.stream_id,
                key=COUNTERFLOW_COMMIT_METADATA_KEY,
            )
            phi = store.layout.phi(shared)
            counterflow = store.layout.counterflow(shared)
            phi_sha256 = controller.state_sha256(phi)
            counterflow_in_sha256 = runtime.state_sha256(counterflow)
            if (
                commit.sequence == committed_sequence
                and commit.event_id == committed_event_id
            ):
                if loaded is None:
                    raise ProviderError("counterflow commit watermark has no checkpoint")
                return {
                    "schema": "cassi.counterflow.observed-commit-receipt.v1",
                    "session_id": session_id,
                    "stream_id": commit.stream_id,
                    "sequence": commit.sequence,
                    "event_id": commit.event_id,
                    "status": "duplicate",
                    "consolidated": False,
                    "state_sha256": phi_sha256,
                    "counterflow_state_in_sha256": counterflow_in_sha256,
                    "counterflow_state_out_sha256": counterflow_in_sha256,
                    "checkpoint": str(loaded[2]),
                    "checkpoint_sha256": loaded[3],
                }
            if commit.sequence <= committed_sequence:
                raise ProviderError("counterflow commit sequence is stale or conflicting")

            try:
                counterflow_out, receipt = runtime.consolidate_observed(
                    counterflow,
                    commit,
                )
                streams = dict(
                    metadata.get(COUNTERFLOW_COMMIT_METADATA_KEY, {})
                )
                streams[commit.stream_id] = {
                    "sequence": commit.sequence,
                    "event_id": commit.event_id,
                }
                metadata[COUNTERFLOW_COMMIT_METADATA_KEY] = streams
                checkpoint, checkpoint_sha256 = store.save(
                    session_id,
                    store.layout.with_counterflow(shared, counterflow_out),
                    metadata,
                )
            except (ProviderError, QiFieldError) as error:
                raise ProviderError(
                    "counterflow consolidation failed; prior shared checkpoint retained: "
                    f"{error}"
                ) from error

            if controller.state_sha256(phi) != phi_sha256:
                raise ProviderError("counterflow consolidation mutated the Phi component")
            return {
                "session_id": session_id,
                "consolidated": True,
                "state_sha256": phi_sha256,
                "checkpoint": str(checkpoint),
                "checkpoint_sha256": checkpoint_sha256,
                **receipt,
            }

    def reset_context(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request, Mapping):
            raise ProviderError("context reset request must be an object")
        stream_id = self._validate_stream_id(request.get("stream_id"))
        expected_sha256 = request.get("checkpoint_sha256")
        expected_engine = request.get("checkpoint_engine_fingerprint")
        if not _is_digest(expected_sha256) or not _is_digest(expected_engine):
            raise ProviderError("context reset checkpoint identity is invalid")
        _, _, _, store, provider_fingerprint = self._require()
        session_id = _session_id(request)
        with self._session_lock(session_id):
            path = store.path_for(session_id)
            if not path.is_file():
                raise ProviderError("context reset checkpoint is missing")
            _, actual_sha256, actual_engine = store.inspect(session_id)
            if (
                actual_sha256 != expected_sha256
                or actual_engine != expected_engine
                or actual_engine == provider_fingerprint
            ):
                raise ProviderError(
                    "context reset checkpoint identity changed or is compatible"
                )
            archive = path.with_name(
                f"{path.stem}.{actual_sha256}.incompatible{path.suffix}"
            )
            if archive.exists():
                raise ProviderError("context reset archive already exists")
            try:
                path.replace(archive)
            except OSError as error:
                raise ProviderError(
                    f"could not archive incompatible checkpoint: {error}"
                ) from error
            return {
                "session_id": session_id,
                "engine_fingerprint": provider_fingerprint,
                "checkpoint": {
                    "status": "missing",
                    "sha256": None,
                    "engine_fingerprint": None,
                    "archived": str(archive),
                },
                "stream": {
                    "stream_id": stream_id,
                    "sequence": 0,
                    "event_id": EMPTY_CONTEXT_EVENT_ID,
                },
            }


class _Handler(http.server.BaseHTTPRequestHandler):
    provider: PersistentFieldProvider
    world_token: str | None = None

    def _authorize_world(self) -> bool:
        if not self.world_token:
            self._send_json(
                503,
                {
                    "error": {
                        "message": "world adapter is disabled until a bearer token is configured",
                        "type": "world_adapter_disabled",
                    }
                },
            )
            return False
        authorization = self.headers.get("Authorization", "")
        prefix = "Bearer "
        supplied = authorization[len(prefix) :] if authorization.startswith(prefix) else ""
        if not supplied or not hmac.compare_digest(supplied, self.world_token):
            self._send_json(
                401,
                {
                    "error": {
                        "message": "world adapter bearer token is invalid",
                        "type": "authentication_error",
                    }
                },
            )
            return False
        return True


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
            controller = self.provider.controller
            self._send_json(
                200,
                {
                    "ok": self.provider.started,
                    "protocol": PROTOCOL,
                    "version": VERSION,
                    "model": MODEL_NAME,
                    "field": True,
                    "config_fingerprint": (
                        None if controller is None else controller.config_fingerprint
                    ),
                    "provider_fingerprint": self.provider.provider_fingerprint,
                    "initial_checkpoint_sha256": self.provider.initial_checkpoint_sha256,
                    "counterflow": (
                        None
                        if self.provider.counterflow_runtime is None
                        else self.provider.counterflow_runtime.status()
                    ),
                    "ingress": (
                        None
                        if self.provider.ingress_journal is None
                        else {
                            "head_sha256": (
                                self.provider.ingress_journal.head_sha256
                            ),
                            "max_bytes": self.provider.config.ingress_max_bytes,
                            "codecs": list(_INGRESS_CODECS),
                            "adaptive_state": False,
                        }
                    ),
                },
            )
        elif self.path == "/v1/models":
            self._send_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": MODEL_NAME,
                            "object": "model",
                            "owned_by": "cassi-field",
                        }
                    ],
                },
            )
        else:
            self._send_json(
                404,
                {
                    "error": {
                        "message": "not found",
                        "type": "invalid_request_error",
                    }
                },
            )

    def _stream(self, result: Mapping[str, Any]) -> None:
        choice = result["choices"][0]
        chunks = [
            {
                "id": result["id"],
                "object": "chat.completion.chunk",
                "created": result["created"],
                "model": MODEL_NAME,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": choice["message"]["content"],
                        },
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": result["id"],
                "object": "chat.completion.chunk",
                "created": result["created"],
                "model": MODEL_NAME,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": choice["finish_reason"],
                    }
                ],
                "cassi": result["cassi"],
            },
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
        routes = {
            "/v1/chat/completions",
            "/v1/context/recall",
            "/v1/context/observe",
            "/v1/context/status",
            "/v1/context/reset",
            "/v1/counterflow/plan",
            "/v1/counterflow/commit",
            "/v1/ingress/append",
            "/v1/ingress/read",
            "/v1/ingress/replay",
            "/v1/world/turn",
            "/v1/world/result",
        }
        if self.path not in routes:
            self._send_json(
                404,
                {
                    "error": {
                        "message": "not found",
                        "type": "invalid_request_error",
                    }
                },
            )
            return
        if self.path in {"/v1/world/turn", "/v1/world/result"} and not self._authorize_world():
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            request_limit = (
                (
                    (self.provider.config.ingress_max_bytes + 2) // 3
                )
                * 4
                + _INGRESS_REQUEST_METADATA_BYTES
                if self.path == "/v1/ingress/append"
                else MAX_REQUEST_BYTES
            )
            if length < 0 or length > request_limit:
                raise ProviderError(
                    "request body is missing or exceeds the route limit"
                )
            request = json.loads(
                self.rfile.read(length),
                parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
            )
            if not isinstance(request, dict):
                raise ProviderError("request JSON must be an object")
            if self.path == "/v1/world/turn":
                self._send_json(200, self.provider.world_turn(request))
                return
            if self.path == "/v1/world/result":
                self._send_json(200, self.provider.world_result(request))
                return
            if self.path == "/v1/ingress/append":
                self._send_json(200, self.provider.append_ingress(request))
                return
            if self.path == "/v1/ingress/read":
                self._send_json(200, self.provider.read_ingress(request))
                return
            if self.path == "/v1/ingress/replay":
                self._send_json(200, self.provider.replay_ingress(request))
                return
            if self.path == "/v1/counterflow/commit":
                self._send_json(200, self.provider.commit_counterflow(request))
                return
            if self.path == "/v1/counterflow/plan":
                self._send_json(200, self.provider.plan_counterflow(request))
                return
            if self.path == "/v1/context/status":
                self._send_json(200, self.provider.context_status(request))
            elif self.path == "/v1/context/reset":
                self._send_json(200, self.provider.reset_context(request))
            elif self.path == "/v1/context/recall":
                self._send_json(200, self.provider.recall_context(request))
            elif self.path == "/v1/context/observe":
                self._send_json(200, self.provider.observe_context(request))
            else:
                response = self.provider.complete(request)
                if request.get("stream", False):
                    self._stream(response)
                else:
                    self._send_json(200, response)
        except (ProviderError, ValueError, KeyError, TypeError) as error:
            self._send_json(
                400,
                {
                    "error": {
                        "message": str(error),
                        "type": "invalid_request_error",
                    }
                },
            )
        except Exception as error:
            self._send_json(
                500,
                {
                    "error": {
                        "message": str(error),
                        "type": "cassi_provider_error",
                    }
                },
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phi-config",
        type=Path,
        default=CONFIG_DIR / "cassi-phi-harmonic-language.json",
    )
    parser.add_argument(
        "--corpus-checkpoint",
        type=Path,
        default=ARTIFACT_DIR / "cassi-phi-harmonic-language" / "field-state.pt",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=ARTIFACT_DIR
        / "cassi-phi-harmonic-language"
        / "provider-sessions",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--max-output-symbols",
        type=int,
        default=DEFAULT_MAX_OUTPUT_SYMBOLS,
    )
    parser.add_argument(
        "--ingress-max-bytes",
        type=int,
        default=DEFAULT_INGRESS_MAX_BYTES,
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument(
        "--world-token",
        default=os.environ.get("CASSI_WORLD_TOKEN"),
        help="Bearer token required by /v1/world/* (or CASSI_WORLD_TOKEN)",
    )
    return parser


def serve(
    config: ProviderConfig,
    *,
    world_token: str | None = None,
) -> None:
    if world_token is not None and len(world_token.encode("utf-8")) < 16:
        raise ProviderError("world adapter bearer token must contain at least 16 UTF-8 bytes")
    provider = PersistentFieldProvider(config)
    provider.start()
    handler = type(
        "CassiFieldProviderHandler",
        (_Handler,),
        {"provider": provider, "world_token": world_token},
    )
    server = http.server.ThreadingHTTPServer((config.host, config.port), handler)
    print(
        f"CASSI_PROVIDER_READY host={config.host} port={config.port}",
        flush=True,
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
        provider.close()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    serve(
        ProviderConfig(
            phi_config_path=args.phi_config,
            corpus_checkpoint_path=args.corpus_checkpoint,
            state_dir=args.state_dir,
            host=args.host,
            port=args.port,
            max_output_symbols=args.max_output_symbols,
            ingress_max_bytes=args.ingress_max_bytes,
            device=args.device,
        ),
        world_token=args.world_token,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
