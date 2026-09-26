#!/usr/bin/env python3
"""A model-agnostic observatory and field-owned LLM interpreter.

The module is deliberately split at the model boundary:

* :class:`ActivationTrace` and :class:`GGUFWeightObservatory` are read-only
  evidence surfaces.  They never become adaptive state.
* :class:`FieldCoordinateCodec` is a fixed, deterministic boundary codec.
* :class:`UniversalLLMInterpreter` puts observations, corrections, and
  predictions through one persisted ``QiFieldState.field`` using the existing
  raw-event learner/store.
* :class:`CausalPair` evaluates paired intervention receipts without calling a
  model or pretending that an offline activation edit is a graph intervention.
* An optional role registry and independent native-role manifest authenticate
  task/source role coordinates before any field event is admitted and reject
  tampered or semantically misbound provenance at the seam.

No learned embedding, projection head, optimizer, model fallback, or second
adaptive store is introduced here.  The field store's journal and the meaning
ledger are exact provenance/evidence; only its Qi tensor is adaptive.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_raw_event_field import AcquisitionProfile, RawEvent, encode_packet
from cassi_raw_event_store import RawEventStore


INTERPRETER_SCHEMA = "cassi.universal-llm-interpreter.v1"
MODEL_SCHEMA = "cassi.universal-llm-model-identity.v1"
TRACE_SCHEMA = "cassi.universal-llm-activation-trace.v1"
READOUT_SCHEMA = "cassi.universal-llm-model-readout.v1"
WEIGHT_SCHEMA = "cassi.universal-llm-weight-slice.v1"
CAUSAL_SCHEMA = "cassi.universal-llm-causal-pair.v1"
OWNERSHIP_SCHEMA = "cassi.universal-llm-ownership-receipt.v1"
LEDGER_SCHEMA = "cassi.universal-llm-meaning-ledger.v1"
ROLE_ATTESTATION_SCHEMA = "cassi.native-role-attestation.v1"
ROLE_EVIDENCE_SCHEMA = "cassi.native-role-evidence.v1"

_MAX_VECTOR_ELEMENTS = 1_048_576
_MAX_QUESTION_BYTES = 16_384
_MAX_MEANING_BYTES = 1 << 20
_PACKET_DIGEST_BYTES = 8


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha_path(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    if any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _bounded_text(value: Any, label: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError(f"{label} must be a nonempty bounded string")
    return value


def _positive_int(value: Any, label: str, maximum: int = 1_000_000_000) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError(f"{label} must be an integer in [0, {maximum}]")
    return int(value)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    """Atomically write a small provenance manifest."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        payload = _canonical(dict(value))
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _readonly_f32(values: Sequence[float] | np.ndarray, label: str) -> np.ndarray:
    array = np.ascontiguousarray(np.asarray(values, dtype=np.float32))
    if array.ndim != 1 or not 1 <= array.size <= _MAX_VECTOR_ELEMENTS:
        raise ValueError(f"{label} must be one bounded nonempty vector")
    if not bool(np.isfinite(array).all()):
        raise ValueError(f"{label} contains non-finite values")
    owned = array.copy()
    owned.setflags(write=False)
    return owned


def _f32_digest(values: np.ndarray) -> str:
    return _sha(np.ascontiguousarray(values, dtype=np.float32).tobytes(order="C"))


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    """Hash-bound identity of one model/adapter/runtime combination."""

    model_id: str
    model_sha256: str
    architecture: str
    quantization: str
    tokenizer_sha256: str
    runtime_id: str
    runtime_sha256: str
    context_tokens: int
    embedding_width: int
    layer_count: int
    backend: str
    hook_sites: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _bounded_text(self.model_id, "model_id")
        _bounded_text(self.architecture, "architecture")
        _bounded_text(self.quantization, "quantization")
        _bounded_text(self.runtime_id, "runtime_id")
        _bounded_text(self.backend, "backend")
        for name in ("model_sha256", "tokenizer_sha256", "runtime_sha256"):
            _digest(getattr(self, name), name)
        for name in ("context_tokens", "embedding_width", "layer_count"):
            value = _positive_int(getattr(self, name), name, maximum=10_000_000)
            if value == 0:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, value)
        sites = tuple(_bounded_text(site, "hook site") for site in self.hook_sites)
        if len(set(sites)) != len(sites):
            raise ValueError("hook_sites must be unique")
        object.__setattr__(self, "hook_sites", sites)

    @property
    def fingerprint(self) -> str:
        return _sha(_canonical(self.as_dict()))

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": MODEL_SCHEMA,
            "model_id": self.model_id,
            "model_sha256": self.model_sha256,
            "architecture": self.architecture,
            "quantization": self.quantization,
            "tokenizer_sha256": self.tokenizer_sha256,
            "runtime_id": self.runtime_id,
            "runtime_sha256": self.runtime_sha256,
            "context_tokens": self.context_tokens,
            "embedding_width": self.embedding_width,
            "layer_count": self.layer_count,
            "backend": self.backend,
            "hook_sites": list(self.hook_sites),
        }

    @classmethod
    def from_gguf(
        cls,
        model_path: Path | str,
        *,
        runtime_id: str,
        runtime_sha256: str,
        tokenizer_sha256: str,
        architecture: str,
        quantization: str,
        context_tokens: int,
        embedding_width: int,
        layer_count: int,
        backend: str,
        hook_sites: Sequence[str] = (),
    ) -> "ModelIdentity":
        path = Path(model_path)
        return cls(
            model_id=path.name,
            model_sha256=_sha_path(path),
            architecture=architecture,
            quantization=quantization,
            tokenizer_sha256=tokenizer_sha256,
            runtime_id=runtime_id,
            runtime_sha256=runtime_sha256,
            context_tokens=context_tokens,
            embedding_width=embedding_width,
            layer_count=layer_count,
            backend=backend,
            hook_sites=tuple(hook_sites),
        )


@dataclass(frozen=True, slots=True)
class ModelReadout:
    """The model-side output evidence available beside one hidden-state row."""

    top_token_id: int
    top_logit: float
    second_token_id: int | None
    second_logit: float | None
    decision_gap: float | None
    entropy_nats: float
    logits_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": READOUT_SCHEMA,
            "top_token_id": self.top_token_id,
            "top_logit": self.top_logit,
            "second_token_id": self.second_token_id,
            "second_logit": self.second_logit,
            "decision_gap": self.decision_gap,
            "entropy_nats": self.entropy_nats,
            "logits_sha256": self.logits_sha256,
        }


def summarize_logits(logits: Sequence[float] | np.ndarray) -> ModelReadout:
    values = _readonly_f32(logits, "logits")
    order = np.argsort(values)[::-1]
    top_index = int(order[0])
    top_logit = float(values[top_index])
    if values.size > 1:
        second_index = int(order[1])
        second_logit = float(values[second_index])
        gap = top_logit - second_logit
    else:
        second_index = None
        second_logit = None
        gap = None
    shifted = values.astype(np.float64) - float(np.max(values))
    probabilities = np.exp(shifted)
    probabilities /= float(probabilities.sum())
    entropy = float(-np.sum(probabilities * np.log(np.maximum(probabilities, 1.0e-300))))
    return ModelReadout(
        top_token_id=top_index,
        top_logit=top_logit,
        second_token_id=second_index,
        second_logit=second_logit,
        decision_gap=gap,
        entropy_nats=entropy,
        logits_sha256=_f32_digest(values),
    )


@dataclass(frozen=True, slots=True)
class ActivationTrace:
    """One immutable, provenance-bound hidden-state capture."""

    model: ModelIdentity
    site: str
    layer: int
    sequence_id: str
    position: int
    values: np.ndarray
    token_id: int | None = None
    expected_token_id: int | None = None
    logits: np.ndarray | None = None
    adapter_key: str | None = None
    prompt_sha256: str | None = None
    capture_sha256: str | None = None
    source_id: str = ""
    native_role: str | None = None
    role_attestation: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.model, ModelIdentity):
            raise ValueError("model must be a ModelIdentity")
        _bounded_text(self.site, "site")
        layer = _positive_int(self.layer, "layer", maximum=self.model.layer_count - 1)
        position = _positive_int(self.position, "position", maximum=self.model.context_tokens - 1)
        object.__setattr__(self, "layer", layer)
        object.__setattr__(self, "position", position)
        _bounded_text(self.sequence_id, "sequence_id")
        values = _readonly_f32(self.values, "activation values")
        object.__setattr__(self, "values", values)
        for name in ("token_id", "expected_token_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _positive_int(value, name, maximum=10_000_000))
        if self.logits is not None:
            object.__setattr__(self, "logits", _readonly_f32(self.logits, "logits"))
        if self.adapter_key is not None:
            _bounded_text(self.adapter_key, "adapter_key", maximum=256)
        for name in ("prompt_sha256", "capture_sha256"):
            value = getattr(self, name)
            if value is not None:
                _digest(value, name)
        if self.source_id:
            _bounded_text(self.source_id, "source_id", maximum=1024)
        if self.native_role is not None:
            _bounded_text(self.native_role, "native_role", maximum=128)
        if self.role_attestation is not None:
            if self.native_role is None:
                raise ValueError("role_attestation requires native_role")
            _digest(self.role_attestation, "role_attestation")

    def role_attestation_for(self, native_role: str | None = None) -> str:
        """Return the deterministic attestation for this trace's role claim."""

        role = self.native_role if native_role is None else native_role
        role = _bounded_text(role, "native_role", maximum=128)
        return _sha(
            _canonical(
                {
                    "schema": ROLE_ATTESTATION_SCHEMA,
                    "model_fingerprint": self.model.fingerprint,
                    "native_role": role,
                    "site": self.site,
                    "layer": self.layer,
                    "sequence_id": self.sequence_id,
                    "position": self.position,
                    "values_sha256": self.values_sha256,
                    "prompt_sha256": self.prompt_sha256,
                    "capture_sha256": self.capture_sha256,
                }
            )
        )

    def with_role_attestation(self, native_role: str | None = None) -> "ActivationTrace":
        """Attach a role attestation without changing the captured values."""

        role = self.native_role if native_role is None else native_role
        role = _bounded_text(role, "native_role", maximum=128)
        return replace(
            self,
            native_role=role,
            role_attestation=self.role_attestation_for(role),
        )


    @property
    def values_sha256(self) -> str:
        return _f32_digest(self.values)

    @property
    def trace_sha256(self) -> str:
        metadata = {
            "schema": TRACE_SCHEMA,
            "model": self.model.fingerprint,
            "site": self.site,
            "layer": self.layer,
            "sequence_id": self.sequence_id,
            "position": self.position,
            "values_sha256": self.values_sha256,
            "token_id": self.token_id,
            "expected_token_id": self.expected_token_id,
            "logits_sha256": None if self.logits is None else _f32_digest(self.logits),
            "adapter_key": self.adapter_key,
            "prompt_sha256": self.prompt_sha256,
            "capture_sha256": self.capture_sha256,
        }
        if self.native_role is not None or self.role_attestation is not None:
            metadata["native_role"] = self.native_role
            metadata["role_attestation"] = self.role_attestation
        return _sha(_canonical(metadata))

    @property
    def model_next_token_id(self) -> int | None:
        if self.expected_token_id is not None:
            return self.expected_token_id
        if self.logits is not None:
            return summarize_logits(self.logits).top_token_id
        return None

    def readout(self) -> ModelReadout | None:
        return None if self.logits is None else summarize_logits(self.logits)

    def field_coordinate_descriptor(self) -> dict[str, Any]:
        """Describe the fixed coordinate supplied to the field boundary.

        An adapter key is an explicit, nonadaptive model translation.  Without
        one, the exact f32 row digest is used and the coordinate is model/site
        specific.  This distinction is retained in every receipt.
        """

        return {
            "schema": TRACE_SCHEMA,
            "site": self.site,
            "layer": self.layer,
            "coordinate_source": (
                "adapter-key" if self.adapter_key is not None else "activation-f32-digest"
            ),
            "adapter_key": self.adapter_key,
            "values_sha256": None if self.adapter_key is not None else self.values_sha256,
        }

    def as_dict(self, *, include_values: bool = False) -> dict[str, Any]:
        row: dict[str, Any] = {
            "schema": TRACE_SCHEMA,
            "model": self.model.as_dict(),
            "model_fingerprint": self.model.fingerprint,
            "site": self.site,
            "layer": self.layer,
            "sequence_id": self.sequence_id,
            "position": self.position,
            "token_id": self.token_id,
            "expected_token_id": self.expected_token_id,
            "adapter_key": self.adapter_key,
            "prompt_sha256": self.prompt_sha256,
            "capture_sha256": self.capture_sha256,
            "native_role": self.native_role,
            "role_attestation": self.role_attestation,
            "values_sha256": self.values_sha256,
            "values_l2": float(np.linalg.norm(self.values.astype(np.float64))),
            "values_max_abs": float(np.max(np.abs(self.values))),
            "trace_sha256": self.trace_sha256,
            "field_coordinate": self.field_coordinate_descriptor(),
        }
        if self.logits is not None:
            row["logits_shape"] = [int(self.logits.size)]
            row["logits_sha256"] = _f32_digest(self.logits)
            row["model_readout"] = self.readout().as_dict() if self.readout() else None
        else:
            row["logits_shape"] = None
            row["logits_sha256"] = None
            row["model_readout"] = None
        if include_values:
            row["values"] = self.values.tolist()
            if self.logits is not None:
                row["logits"] = self.logits.tolist()
        return row

    @classmethod
    def from_f32_file(
        cls,
        path: Path | str,
        *,
        model: ModelIdentity,
        site: str,
        layer: int,
        sequence_id: str,
        position: int,
        shape: Sequence[int],
        token_id: int | None = None,
        expected_token_id: int | None = None,
        adapter_key: str | None = None,
        prompt_sha256: str | None = None,
        native_role: str | None = None,
        role_attestation: str | None = None,
    ) -> "ActivationTrace":
        source = Path(path)
        raw = source.read_bytes()
        if len(raw) % 4:
            raise ValueError("float32 activation file has a partial element")
        dimensions = tuple(int(value) for value in shape)
        if not dimensions or any(value <= 0 for value in dimensions):
            raise ValueError("activation shape must contain positive dimensions")
        if math.prod(dimensions) * 4 != len(raw):
            raise ValueError("activation shape does not match its file")
        values = np.frombuffer(raw, dtype="<f4").copy().reshape(-1)
        return cls(
            model=model,
            site=site,
            layer=layer,
            sequence_id=sequence_id,
            position=position,
            values=values,
            token_id=token_id,
            expected_token_id=expected_token_id,
            adapter_key=adapter_key,
            prompt_sha256=prompt_sha256,
            capture_sha256=_sha(raw),
            source_id=str(source),
            native_role=native_role,
            role_attestation=role_attestation,
        )


class FieldCoordinateCodec:
    """Fixed phase-boundary packet codec; it has no adaptive parameters."""

    schema = "cassi.universal-llm-fixed-coordinate-codec.v1"

    @staticmethod
    def _packet(descriptor: Mapping[str, Any]) -> bytes:
        digest = _sha(_canonical(dict(descriptor)))
        return encode_packet((bytes.fromhex(digest[: _PACKET_DIGEST_BYTES * 2]),))

    def observation_packet(self, trace: ActivationTrace) -> bytes:
        return self._packet(trace.field_coordinate_descriptor())

    def action_packet(self, question: str) -> bytes:
        question = _bounded_text(question, "question", maximum=_MAX_QUESTION_BYTES)
        return self._packet(
            {
                "schema": self.schema,
                "kind": "question",
                "question": question,
            }
        )

    def meaning_packet(self, meaning: Mapping[str, Any]) -> bytes:
        encoded = _canonical(dict(meaning))
        if not encoded or len(encoded) > _MAX_MEANING_BYTES:
            raise ValueError("meaning is empty or exceeds the fixed bound")
        return self._packet(
            {
                "schema": self.schema,
                "kind": "meaning",
                "meaning": json.loads(encoded.decode("utf-8")),
            }
        )

    @staticmethod
    def packet_hex(packet: bytes) -> str:
        return bytes(packet).hex()


@dataclass(frozen=True, slots=True)
class WeightSlice:
    """A bounded dequantized weight read plus its raw bytes identity."""

    model: ModelIdentity
    tensor_name: str
    tensor_shape: tuple[int, ...]
    tensor_type: str
    row_start: int
    row_stop: int
    column_start: int
    column_stop: int
    raw_bytes_touched: int
    raw_sha256: str
    values: np.ndarray

    def __post_init__(self) -> None:
        _bounded_text(self.tensor_name, "tensor_name")
        _bounded_text(self.tensor_type, "tensor_type")
        shape = tuple(_positive_int(value, "tensor dimension", maximum=10_000_000) for value in self.tensor_shape)
        if len(shape) != 2:
            raise ValueError("weight slices currently require a matrix tensor")
        object.__setattr__(self, "tensor_shape", shape)
        for name in ("row_start", "row_stop", "column_start", "column_stop"):
            object.__setattr__(self, name, _positive_int(getattr(self, name), name, maximum=10_000_000))
        if not self.row_start < self.row_stop <= shape[1]:
            raise ValueError("weight row bounds are invalid")
        if not self.column_start < self.column_stop <= shape[0]:
            raise ValueError("weight column bounds are invalid")
        if isinstance(self.raw_bytes_touched, bool) or self.raw_bytes_touched <= 0:
            raise ValueError("raw_bytes_touched must be positive")
        _digest(self.raw_sha256, "raw_sha256")
        values = _readonly_f32(self.values.reshape(-1), "weight values")
        expected = (self.row_stop - self.row_start) * (self.column_stop - self.column_start)
        if values.size != expected:
            raise ValueError("weight value shape does not match slice bounds")
        object.__setattr__(self, "values", values.reshape(expected // (self.column_stop - self.column_start), self.column_stop - self.column_start))

    def _fingerprint_body(self) -> dict[str, Any]:
        return {
            "schema": WEIGHT_SCHEMA,
            "model_fingerprint": self.model.fingerprint,
            "tensor_name": self.tensor_name,
            "tensor_shape": list(self.tensor_shape),
            "tensor_type": self.tensor_type,
            "row_start": self.row_start,
            "row_stop": self.row_stop,
            "column_start": self.column_start,
            "column_stop": self.column_stop,
            "raw_bytes_touched": self.raw_bytes_touched,
            "raw_sha256": self.raw_sha256,
            "values_shape": list(self.values.shape),
            "values_sha256": _f32_digest(self.values.reshape(-1)),
        }

    @property
    def fingerprint(self) -> str:
        return _sha(_canonical(self._fingerprint_body()))

    def as_dict(self, *, include_values: bool = False) -> dict[str, Any]:
        row = {
            **self._fingerprint_body(),
            "fingerprint": self.fingerprint,
        }
        if include_values:
            row["values"] = self.values.tolist()
        return row

    @classmethod
    def from_array(
        cls,
        values: Sequence[Sequence[float]] | np.ndarray,
        *,
        model: ModelIdentity,
        tensor_name: str,
        tensor_shape: Sequence[int],
        tensor_type: str = "fixture-f32",
        row_start: int = 0,
        column_start: int = 0,
        raw_bytes: bytes | None = None,
    ) -> "WeightSlice":
        array = np.ascontiguousarray(np.asarray(values, dtype=np.float32))
        if array.ndim != 2:
            raise ValueError("weight fixture must be a matrix")
        raw = array.tobytes(order="C") if raw_bytes is None else bytes(raw_bytes)
        return cls(
            model=model,
            tensor_name=tensor_name,
            tensor_shape=tuple(int(value) for value in tensor_shape),
            tensor_type=tensor_type,
            row_start=row_start,
            row_stop=row_start + array.shape[0],
            column_start=column_start,
            column_stop=column_start + array.shape[1],
            raw_bytes_touched=len(raw),
            raw_sha256=_sha(raw),
            values=array.reshape(-1),
        )


class GGUFWeightObservatory:
    """Read bounded matrix slices from the pinned GGUF without model execution."""

    def __init__(
        self,
        model_path: Path | str,
        *,
        model: ModelIdentity | None = None,
        max_cells: int = 262_144,
    ) -> None:
        path = Path(model_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        if isinstance(max_cells, bool) or not 1 <= max_cells <= _MAX_VECTOR_ELEMENTS:
            raise ValueError("max_cells is outside the bounded observatory limit")
        gguf_root = Path(__file__).resolve().parents[1] / "native" / "llama.cpp" / "gguf-py"
        if str(gguf_root) not in sys.path:
            sys.path.insert(0, str(gguf_root))
        from gguf import GGUFReader  # type: ignore[import-not-found]

        if model is not None and model.model_sha256 != _sha_path(path):
            raise ValueError("supplied model identity does not match the GGUF bytes")
        self.path = path
        self.model = model
        self.max_cells = int(max_cells)
        self._reader = GGUFReader(str(path))
        self._tensors = {tensor.name: tensor for tensor in self._reader.tensors}

    def inventory(self, *, names: Sequence[str] | None = None) -> list[dict[str, Any]]:
        selected = self._tensors if names is None else {name: self._tensors[name] for name in names}
        rows: list[dict[str, Any]] = []
        for name in sorted(selected):
            tensor = selected[name]
            rows.append(
                {
                    "name": name,
                    "shape": [int(value) for value in tensor.shape],
                    "tensor_type": str(tensor.tensor_type.name),
                    "bytes": int(tensor.n_bytes),
                    "data_offset": int(tensor.data_offset),
                }
            )
        return rows

    def read_slice(
        self,
        tensor_name: str,
        *,
        row_start: int,
        row_stop: int,
        column_start: int,
        column_stop: int,
    ) -> WeightSlice:
        if tensor_name not in self._tensors:
            raise KeyError(tensor_name)
        tensor = self._tensors[tensor_name]
        shape = tuple(int(value) for value in tensor.shape)
        if len(shape) != 2:
            raise ValueError("weight observatory requires a two-dimensional tensor")
        # GGUF stores matrix metadata as [columns, rows], while ReaderTensor.data
        # is reshaped into [rows, columns], matching the existing lens helper.
        rows, columns = shape[1], shape[0]
        row_start = _positive_int(row_start, "row_start", maximum=rows)
        row_stop = _positive_int(row_stop, "row_stop", maximum=rows)
        column_start = _positive_int(column_start, "column_start", maximum=columns)
        column_stop = _positive_int(column_stop, "column_stop", maximum=columns)
        if not row_start < row_stop <= rows or not column_start < column_stop <= columns:
            raise ValueError("weight slice bounds are invalid")
        cells = (row_stop - row_start) * (column_stop - column_start)
        if cells > self.max_cells:
            raise ValueError("weight slice exceeds the bounded cell allocation")
        if self.model is None:
            raise ValueError(
                "read_slice requires a ModelIdentity so weight provenance is explicit"
            )
        raw_rows = tensor.data.reshape(rows, -1)
        raw_chunk = np.ascontiguousarray(raw_rows[row_start:row_stop])
        from gguf import quants  # type: ignore[import-not-found]
        from gguf.constants import GGMLQuantizationType as QType  # type: ignore[import-not-found]

        dequantized = quants.dequantize(raw_chunk, QType(tensor.tensor_type))
        matrix = np.ascontiguousarray(dequantized, dtype=np.float32).reshape(
            row_stop - row_start, columns
        )
        return WeightSlice(
            model=self.model,
            tensor_name=tensor_name,
            tensor_shape=shape,
            tensor_type=str(tensor.tensor_type.name),
            row_start=row_start,
            row_stop=row_stop,
            column_start=column_start,
            column_stop=column_stop,
            raw_bytes_touched=int(raw_chunk.nbytes),
            raw_sha256=_sha(raw_chunk.tobytes(order="C")),
            values=matrix[:, column_start:column_stop].reshape(-1),
        )

    def close(self) -> None:
        self._tensors = {}
        self._reader = None

    def __enter__(self) -> "GGUFWeightObservatory":
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        self.close()


class MeaningLedger:
    """Exact source-to-boundary labels; not an adaptive representation."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._rows: dict[str, dict[str, Any]] = {}
        if self.path.is_file():
            for line_number, line in enumerate(self.path.read_bytes().splitlines(), start=1):
                if not line:
                    continue
                try:
                    row = json.loads(line.decode("utf-8"))
                except Exception as exc:
                    raise ValueError(f"meaning ledger line {line_number} is invalid") from exc
                if not isinstance(row, Mapping) or row.get("schema") != LEDGER_SCHEMA:
                    raise ValueError("meaning ledger schema mismatch")
                packet_hex = row.get("packet_hex")
                meaning = row.get("meaning")
                if not isinstance(packet_hex, str) or not isinstance(meaning, Mapping):
                    raise ValueError("meaning ledger row is malformed")
                if packet_hex in self._rows and self._rows[packet_hex]["meaning"] != dict(meaning):
                    raise ValueError("meaning ledger contains a packet collision")
                self._rows[packet_hex] = dict(row)

    def check(self, packet: bytes, meaning: Mapping[str, Any]) -> None:
        packet_hex = bytes(packet).hex()
        encoded = _canonical(dict(meaning))
        if len(encoded) > _MAX_MEANING_BYTES:
            raise ValueError("meaning exceeds the ledger bound")
        prior = self._rows.get(packet_hex)
        if prior is not None and prior.get("meaning") != json.loads(encoded.decode("utf-8")):
            raise ValueError("one field packet cannot name two meanings")

    def put(
        self,
        packet: bytes,
        meaning: Mapping[str, Any],
        *,
        trace: ActivationTrace,
        question: str,
    ) -> dict[str, Any]:
        self.check(packet, meaning)
        packet_hex = bytes(packet).hex()
        normalized = json.loads(_canonical(dict(meaning)).decode("utf-8"))
        prior = self._rows.get(packet_hex)
        if prior is not None:
            return dict(prior)
        row = {
            "schema": LEDGER_SCHEMA,
            "packet_hex": packet_hex,
            "meaning": normalized,
            "trace_sha256": trace.trace_sha256,
            "model_fingerprint": trace.model.fingerprint,
            "question": question,
        }
        with self.path.open("ab") as stream:
            stream.write(_canonical(row) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        self._rows[packet_hex] = row
        return dict(row)

    def resolve(self, packet: bytes | str | None) -> Mapping[str, Any] | None:
        if packet is None:
            return None
        packet_hex = packet if isinstance(packet, str) else bytes(packet).hex()
        row = self._rows.get(packet_hex)
        if row is None:
            return None
        meaning = row.get("meaning")
        return dict(meaning) if isinstance(meaning, Mapping) else None

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": LEDGER_SCHEMA,
            "entry_count": len(self._rows),
            "packet_sha256": _sha(_canonical(sorted(self._rows))),
            "entries": [
                {
                    "packet_hex": key,
                    "meaning_sha256": _sha(_canonical(row["meaning"])),
                    "trace_sha256": row["trace_sha256"],
                    "model_fingerprint": row["model_fingerprint"],
                }
                for key, row in sorted(self._rows.items())
            ],
        }


def _native_role_evidence_key(
    model_fingerprint: str,
    prompt_sha256: str,
    capture_sha256: str,
) -> str:
    return _sha(
        _canonical(
            {
                "schema": ROLE_EVIDENCE_SCHEMA,
                "model_fingerprint": model_fingerprint,
                "prompt_sha256": prompt_sha256,
                "capture_sha256": capture_sha256,
            }
        )
    )


def _normalize_native_role_manifest(
    value: Sequence[Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]] | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("native_role_manifest must be a sequence")
    normalized: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("native role manifest rows must be mappings")
        try:
            row = json.loads(_canonical(dict(item)).decode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError("native role manifest rows must be JSON-compatible") from exc
        if not isinstance(row, dict):
            raise ValueError("native role manifest rows must be mappings")
        row["model_fingerprint"] = _digest(
            row.get("model_fingerprint"),
            "native role evidence model_fingerprint",
        )
        row["prompt_sha256"] = _digest(
            row.get("prompt_sha256"),
            "native role evidence prompt_sha256",
        )
        row["capture_sha256"] = _digest(
            row.get("capture_sha256"),
            "native role evidence capture_sha256",
        )
        row["native_role"] = _bounded_text(
            row.get("native_role"),
            "native role evidence native_role",
            maximum=128,
        )
        key = _native_role_evidence_key(
            row["model_fingerprint"],
            row["prompt_sha256"],
            row["capture_sha256"],
        )
        prior = normalized.get(key)
        if prior is not None and prior != row:
            raise ValueError("native role manifest contains conflicting duplicate")
        normalized[key] = row
    return {key: normalized[key] for key in sorted(normalized)}


def _normalize_role_registry(
    value: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("role_registry must be a mapping")
    normalized: dict[str, dict[str, Any]] = {}
    for key, descriptor in value.items():
        coordinate = _bounded_text(key, "role coordinate", maximum=256)
        if not isinstance(descriptor, Mapping):
            raise ValueError("role registry descriptors must be mappings")
        try:
            row = json.loads(_canonical(dict(descriptor)).decode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError("role registry descriptors must be JSON-compatible") from exc
        if not isinstance(row, dict):
            raise ValueError("role registry descriptors must be mappings")
        row["semantic_role"] = _bounded_text(
            row.get("semantic_role"),
            "semantic_role",
            maximum=128,
        )
        row["model_fingerprint"] = _digest(
            row.get("model_fingerprint"),
            "role model_fingerprint",
        )
        normalized[coordinate] = row
    return {key: normalized[key] for key in sorted(normalized)}


class UniversalLLMInterpreter:
    """One field-owned interpreter spanning arbitrary model adapters."""

    def __init__(
        self,
        root: Path | str,
        *,
        model: ModelIdentity,
        profile: AcquisitionProfile | None = None,
        role_registry: Mapping[str, Mapping[str, Any]] | None = None,
        native_role_manifest: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        if not isinstance(model, ModelIdentity):
            raise ValueError("model must be a ModelIdentity")
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._registry_path = self.root / "model-registry.json"
        self._registry = self._load_registry()
        self._register_model(model, require_adapter_key=False)
        self.model = model
        self._role_registry = _normalize_role_registry(role_registry)
        self._native_role_manifest = _normalize_native_role_manifest(native_role_manifest)
        if self._native_role_manifest is not None and self._role_registry is None:
            raise ValueError("native_role_manifest requires role_registry")
        self.codec = FieldCoordinateCodec()
        self.store = RawEventStore(self.root / "field", profile=profile)
        self.ledger = MeaningLedger(self.root / "meaning-ledger.jsonl")
        self._closed = False

    def _load_registry(self) -> dict[str, Any]:
        if not self._registry_path.is_file():
            return {"schema": "cassi.universal-llm-model-registry.v1", "models": []}
        value = json.loads(self._registry_path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping) or value.get("schema") != "cassi.universal-llm-model-registry.v1":
            raise ValueError("model registry schema mismatch")
        models = value.get("models")
        if not isinstance(models, list) or any(not isinstance(row, Mapping) for row in models):
            raise ValueError("model registry models are malformed")
        return {"schema": value["schema"], "models": [dict(row) for row in models]}

    def _register_model(self, model: ModelIdentity, *, require_adapter_key: bool) -> None:
        fingerprint = model.fingerprint
        known = {str(row.get("fingerprint")): row for row in self._registry["models"]}
        if fingerprint in known:
            if known[fingerprint].get("identity") != model.as_dict():
                raise ValueError("model registry identity collision")
            return
        if require_adapter_key:
            raise ValueError("a new model requires an explicit fixed adapter_key")
        self._registry["models"].append(
            {
                "fingerprint": fingerprint,
                "identity": model.as_dict(),
            }
        )
        self._registry["models"].sort(key=lambda row: str(row["fingerprint"]))
        _atomic_json(self._registry_path, self._registry)

    def _require_role_binding(self, trace: ActivationTrace) -> None:
        if self._role_registry is None:
            return
        if trace.adapter_key is None:
            raise ValueError("role gate requires adapter_key")
        descriptor = self._role_registry.get(trace.adapter_key)
        if descriptor is None:
            raise ValueError("unregistered role coordinate")
        if trace.native_role is None or trace.role_attestation is None:
            raise ValueError("role attestation is required")
        if trace.prompt_sha256 is None or trace.capture_sha256 is None:
            raise ValueError("role attestation requires prompt_sha256 and capture_sha256")
        if trace.model.fingerprint != descriptor["model_fingerprint"]:
            raise ValueError("role coordinate model mismatch")
        if trace.native_role != descriptor["semantic_role"]:
            raise ValueError("native role-coordinate mismatch")
        if trace.role_attestation != trace.role_attestation_for(trace.native_role):
            raise ValueError("invalid role attestation")
        if self._native_role_manifest is not None:
            evidence_key = _native_role_evidence_key(
                trace.model.fingerprint,
                trace.prompt_sha256,
                trace.capture_sha256,
            )
            evidence = self._native_role_manifest.get(evidence_key)
            if evidence is None:
                raise ValueError("unregistered native role evidence")
            if evidence["native_role"] != trace.native_role:
                raise ValueError("native role evidence mismatch")

    def _require_trace(self, trace: ActivationTrace) -> None:
        if not isinstance(trace, ActivationTrace):
            raise ValueError("trace must be an ActivationTrace")
        if trace.site not in trace.model.hook_sites and trace.model.hook_sites:
            raise ValueError("trace site is not declared by the model identity")
        self._require_role_binding(trace)
        known = {str(row.get("fingerprint")) for row in self._registry["models"]}
        if trace.model.fingerprint not in known:
            if trace.adapter_key is None:
                raise ValueError("unregistered model requires an explicit fixed adapter_key")
            self._register_model(trace.model, require_adapter_key=False)

    def _next_sequence(self) -> int:
        return int(self.store.snapshot()["last_sequence"]) + 1

    def _admit(self, kind: str, payload: bytes = b"", *, learn: bool, promote: bool) -> dict[str, Any]:
        event = RawEvent(self._next_sequence(), kind, payload)
        return self.store.admit(event, learn=learn, promote=promote)

    def _begin(self, trace: ActivationTrace, question: str) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
        self._require_trace(trace)
        question = _bounded_text(question, "question", maximum=_MAX_QUESTION_BYTES)
        reset = self._admit("reset", learn=False, promote=False)
        observation_packet = self.codec.observation_packet(trace)
        observation = self._admit("observation", observation_packet, learn=False, promote=False)
        return observation_packet, reset, observation

    @staticmethod
    def _prediction_from_transition(
        transition: Mapping[str, Any],
        *,
        trace: ActivationTrace,
        question: str,
        ledger: MeaningLedger,
    ) -> dict[str, Any]:
        raw = transition.get("transition")
        if not isinstance(raw, Mapping):
            raw = transition
        prediction = raw.get("prediction_before_outcome")
        if not isinstance(prediction, Mapping):
            prediction = {"status": "unresolved", "reason": "no-field-prediction"}
        result = dict(prediction)
        payload_hex = result.get("payload_hex")
        meaning = ledger.resolve(payload_hex if isinstance(payload_hex, str) else None)
        result["meaning"] = meaning
        result["field_owned"] = bool(result.get("status") == "supported" and meaning is not None)
        result["question"] = question
        result["trace_sha256"] = trace.trace_sha256
        target = trace.model_next_token_id
        result["model_target_token_id"] = target
        if target is not None and isinstance(meaning, Mapping):
            result["target_token_match"] = meaning.get("next_token_id") == target
        else:
            result["target_token_match"] = None
        return result

    def inspect(self, trace: ActivationTrace) -> dict[str, Any]:
        """Read model evidence and the fixed field coordinate without mutation."""

        self._require_trace(trace)
        before = self.store.learner.fingerprint()
        result = {
            "schema": "cassi.universal-llm-inspection.v1",
            "model": trace.model.as_dict(),
            "trace": trace.as_dict(),
            "model_readout": None if trace.readout() is None else trace.readout().as_dict(),
            "field_coordinate": trace.field_coordinate_descriptor(),
            "field_state_sha256": before,
            "field_mutated": False,
        }
        if self.store.learner.fingerprint() != before:
            raise RuntimeError("inspection mutated the adaptive field")
        return result

    def learn(
        self,
        trace: ActivationTrace,
        *,
        question: str,
        meaning: Mapping[str, Any],
        promote: bool = True,
    ) -> dict[str, Any]:
        """Admit one observed correction into the field and exact ledger."""

        if not isinstance(meaning, Mapping) or not meaning:
            raise ValueError("meaning must be a nonempty mapping")
        question = _bounded_text(question, "question", maximum=_MAX_QUESTION_BYTES)
        observation_packet, reset, observation = self._begin(trace, question)
        action_packet = self.codec.action_packet(question)
        # Check collisions before changing the adaptive field.
        meaning_packet = self.codec.meaning_packet(meaning)
        self.ledger.check(meaning_packet, meaning)
        action = self._admit("action", action_packet, learn=False, promote=False)
        outcome = self._admit(
            "observation",
            meaning_packet,
            learn=True,
            promote=bool(promote),
        )
        ledger_row = self.ledger.put(
            meaning_packet,
            meaning,
            trace=trace,
            question=question,
        )
        return {
            "schema": "cassi.universal-llm-learning-receipt.v1",
            "status": "learned" if outcome.get("mutated") else "replayed",
            "model_fingerprint": trace.model.fingerprint,
            "trace_sha256": trace.trace_sha256,
            "observation_packet_hex": observation_packet.hex(),
            "action_packet_hex": action_packet.hex(),
            "meaning_packet_hex": meaning_packet.hex(),
            "reset": reset,
            "observation": observation,
            "action": action,
            "outcome": outcome,
            "ledger": ledger_row,
            "field_state_sha256": self.store.learner.fingerprint(),
            "field_owned_adaptive_state": "QiFieldState.field",
        }

    def query(self, trace: ActivationTrace, *, question: str) -> dict[str, Any]:
        """Predict and deliver a meaning without mutating the field."""

        question = _bounded_text(question, "question", maximum=_MAX_QUESTION_BYTES)
        observation_packet, reset, observation = self._begin(trace, question)
        before_action = self.store.learner.fingerprint()
        action_packet = self.codec.action_packet(question)
        action = self._admit("action", action_packet, learn=False, promote=False)
        prediction = self._prediction_from_transition(
            action,
            trace=trace,
            question=question,
            ledger=self.ledger,
        )
        after_action = self.store.learner.fingerprint()
        if before_action != after_action:
            raise RuntimeError("field prediction mutated the adaptive field")
        return {
            "schema": "cassi.universal-llm-query-receipt.v1",
            "status": "field-owned" if prediction["field_owned"] else "unresolved",
            "model_fingerprint": trace.model.fingerprint,
            "trace_sha256": trace.trace_sha256,
            "observation_packet_hex": observation_packet.hex(),
            "action_packet_hex": action_packet.hex(),
            "reset": reset,
            "observation": observation,
            "action": action,
            "prediction": prediction,
            "field_state_sha256": after_action,
            "field_mutated": False,
            "native_fallback": False,
        }

    def explain(self, trace: ActivationTrace, *, question: str) -> dict[str, Any]:
        """Return an evidence-linked explanation at the fixed boundary."""

        query = self.query(trace, question=question)
        prediction = query["prediction"]
        return {
            "schema": "cassi.universal-llm-explanation.v1",
            "claim": (
                "field-owned meaning delivered"
                if query["status"] == "field-owned"
                else "field has no supported meaning for this coordinate"
            ),
            "evidence": {
                "model_fingerprint": trace.model.fingerprint,
                "trace_sha256": trace.trace_sha256,
                "site": trace.site,
                "layer": trace.layer,
                "position": trace.position,
                "field_coordinate": trace.field_coordinate_descriptor(),
                "field_state_sha256": query["field_state_sha256"],
                "field_prediction": prediction,
            },
            "model_evidence": trace.readout().as_dict() if trace.readout() else None,
            "native_displacement": "none in this offline field-boundary path",
        }

    def state_receipt(self) -> dict[str, Any]:
        snapshot = self.store.snapshot()
        field = snapshot["field"]
        return {
            "schema": "cassi.universal-llm-state-receipt.v1",
            "field_state_sha256": self.store.learner.fingerprint(),
            "field_profile_sha256": self.store.profile.fingerprint,
            "field_snapshot": field,
            "event_count": snapshot["event_count"],
            "active_event_count": snapshot["active_event_count"],
            "model_count": len(self._registry["models"]),
            "meaning_count": self.ledger.snapshot()["entry_count"],
            "field_only_adaptive_state": True,
            "role_gate": {
                "enabled": self._role_registry is not None,
                "registry_sha256": (
                    None
                    if self._role_registry is None
                    else _sha(_canonical(self._role_registry))
                ),
                "entry_count": (
                    0 if self._role_registry is None else len(self._role_registry)
                ),
                "native_role_manifest_sha256": (
                    None
                    if self._native_role_manifest is None
                    else _sha(_canonical(self._native_role_manifest))
                ),
                "native_role_manifest_entry_count": (
                    0
                    if self._native_role_manifest is None
                    else len(self._native_role_manifest)
                ),
            },
        }

    def ownership_receipt(self) -> dict[str, Any]:
        """Report ownership and displacement for this actual execution path."""

        state = self.state_receipt()
        events = int(state["event_count"])
        meanings = int(state["meaning_count"])
        return {
            "schema": OWNERSHIP_SCHEMA,
            "interpreter_schema": INTERPRETER_SCHEMA,
            "execution": "offline-observatory-plus-field-owned-boundary",
            "actual_execution": True,
            "field_state_sha256": state["field_state_sha256"],
            "field_adaptive_object": "QiFieldState.field",
            "decisions": {
                "field_meaning_deliveries": meanings,
                "field_token_selections": 0,
                "model_token_selections": 0,
                "model_observation_events": events,
            },
            "native_displacement": {
                "status": "none-measured-in-this-path",
                "native_dynamic_state_bytes_removed": 0,
                "native_dynamic_state_footprint_bytes": None,
                "native_ops_skipped": 0,
                "native_output_rows_skipped": 0,
                "qwen_weight_bytes_touched_per_token": 0,
                "reason": "the universal boundary consumed captured evidence; it did not execute Qwen",
            },
            "fallback": "none",
            "checkpoint_identity": state["field_state_sha256"],
        }

    def close(self) -> None:
        if not self._closed:
            self.store.close()
            self._closed = True

    def __enter__(self) -> "UniversalLLMInterpreter":
        if self._closed:
            raise RuntimeError("interpreter is closed")
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        self.close()


@dataclass(frozen=True, slots=True)
class OutputSnapshot:
    """One captured output vector at one intervention coordinate."""

    model: ModelIdentity
    site: str
    layer: int
    sequence_id: str
    position: int
    prompt_sha256: str
    logits: np.ndarray
    route: str
    executed: bool
    capture_id: str

    def __post_init__(self) -> None:
        _bounded_text(self.site, "site")
        _positive_int(self.layer, "layer", maximum=self.model.layer_count - 1)
        _bounded_text(self.sequence_id, "sequence_id")
        _positive_int(self.position, "position", maximum=self.model.context_tokens - 1)
        _digest(self.prompt_sha256, "prompt_sha256")
        _bounded_text(self.route, "route")
        if not isinstance(self.executed, bool):
            raise ValueError("executed must be boolean")
        _bounded_text(self.capture_id, "capture_id", maximum=1024)
        object.__setattr__(self, "logits", _readonly_f32(self.logits, "output logits"))

    @property
    def top_token_id(self) -> int:
        return summarize_logits(self.logits).top_token_id

    @property
    def logits_sha256(self) -> str:
        return _f32_digest(self.logits)

    def coordinate(self) -> tuple[Any, ...]:
        return (
            self.model.fingerprint,
            self.site,
            self.layer,
            self.sequence_id,
            self.position,
            self.prompt_sha256,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_fingerprint": self.model.fingerprint,
            "site": self.site,
            "layer": self.layer,
            "sequence_id": self.sequence_id,
            "position": self.position,
            "prompt_sha256": self.prompt_sha256,
            "logits_shape": [int(self.logits.size)],
            "logits_sha256": self.logits_sha256,
            "top_token_id": self.top_token_id,
            "route": self.route,
            "executed": self.executed,
            "capture_id": self.capture_id,
        }


@dataclass(frozen=True, slots=True)
class CausalPair:
    """Baseline/lesion/donor comparison with honest route classification."""

    baseline: OutputSnapshot
    lesion: OutputSnapshot
    donor: OutputSnapshot | None = None
    intervention_kind: str = "lesion"
    tolerance: float = 1.0e-6

    def __post_init__(self) -> None:
        if self.baseline.coordinate() != self.lesion.coordinate():
            raise ValueError("baseline and lesion coordinates differ")
        if self.donor is not None and self.donor.coordinate() != self.baseline.coordinate():
            raise ValueError("donor coordinate differs from baseline")
        _bounded_text(self.intervention_kind, "intervention_kind")
        if isinstance(self.tolerance, bool) or not math.isfinite(float(self.tolerance)) or self.tolerance < 0.0:
            raise ValueError("tolerance must be a finite nonnegative number")

    def assess(self) -> dict[str, Any]:
        delta = self.lesion.logits.astype(np.float64) - self.baseline.logits.astype(np.float64)
        max_abs = float(np.max(np.abs(delta)))
        l2 = float(np.linalg.norm(delta))
        changed = max_abs > float(self.tolerance)
        decision_flip = self.baseline.top_token_id != self.lesion.top_token_id
        graph_native = (
            self.baseline.route == "graph-native"
            and self.lesion.route == "graph-native"
            and self.baseline.executed
            and self.lesion.executed
        )
        status = (
            "causal-effect"
            if graph_native and changed
            else "causal-null"
            if graph_native
            else "counterfactual-only"
            if changed
            else "counterfactual-null"
        )
        donor_restores = None
        donor_delta_l2 = None
        if self.donor is not None:
            donor_delta = self.donor.logits.astype(np.float64) - self.baseline.logits.astype(np.float64)
            donor_delta_l2 = float(np.linalg.norm(donor_delta))
            donor_restores = (
                self.donor.top_token_id == self.baseline.top_token_id
                and donor_delta_l2 <= l2
            )
        return {
            "schema": CAUSAL_SCHEMA,
            "status": status,
            "intervention_kind": self.intervention_kind,
            "coordinate": {
                "model_fingerprint": self.baseline.model.fingerprint,
                "site": self.baseline.site,
                "layer": self.baseline.layer,
                "sequence_id": self.baseline.sequence_id,
                "position": self.baseline.position,
                "prompt_sha256": self.baseline.prompt_sha256,
            },
            "baseline": self.baseline.as_dict(),
            "lesion": self.lesion.as_dict(),
            "donor": None if self.donor is None else self.donor.as_dict(),
            "max_abs_logit_delta": max_abs,
            "l2_logit_delta": l2,
            "decision_flip": decision_flip,
            "changed_beyond_tolerance": changed,
            "graph_native_executed": graph_native,
            "donor_restores_baseline_decision": donor_restores,
            "donor_l2_from_baseline": donor_delta_l2,
            "claim_boundary": (
                "paired graph execution supports a causal effect"
                if graph_native and changed
                else "activation-space comparison is not a graph-causal claim"
                if not graph_native
                else "paired graph execution found no effect above tolerance"
            ),
        }


def receipt_digest(value: Mapping[str, Any]) -> str:
    """Digest a receipt body while excluding only its own digest leaf."""

    body = dict(value)
    body.pop("content_sha256", None)
    return _sha(_canonical(body))


__all__ = [
    "ActivationTrace",
    "CausalPair",
    "FieldCoordinateCodec",
    "GGUFWeightObservatory",
    "MeaningLedger",
    "ModelIdentity",
    "ModelReadout",
    "OutputSnapshot",
    "UniversalLLMInterpreter",
    "WeightSlice",
    "receipt_digest",
    "summarize_logits",
]
