"""Persistent generated-token trajectory capture for the frozen CassiQwen L18 lab.

This module is deliberately a library, not a runner.  Importing it only imports
ctypes/NumPy and the source-verified L16 ABI declarations; it never loads a DLL,
model, backend, or context.  ``L18GeneratedTokenTrajectory`` loads one local
b10472 Vulkan runtime and keeps one context alive for an initial token batch and
subsequent one-token decodes. The WIP layer-input hooks are capture-only:
indices 0..63 are field trunk inputs. The separate index-64 final-output
reference comes from the documented public output-embedding API.

Pinned ABI source: llama.cpp b10472, commit 60eeeb608.  The public layouts and
WIP export resolution are reused from :mod:`l16_hidden_state_probe`.
"""

from __future__ import annotations

import base64
import ctypes as ct
import hashlib
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np

from cassi_fi_paths import QWEN_DLL_DIR, QWEN_MODEL_PATH

try:  # Direct ``python CassiFI/...`` and package imports are both useful.
    from . import l16_hidden_state_probe as l16
except ImportError:  # pragma: no cover - exercised only for direct module use.
    import l16_hidden_state_probe as l16


__all__ = [
    "DecodeRecord",
    "GeneratedTokenTrajectory",
    "L18GeneratedTokenTrajectory",
    "RuntimeConfig",
    "TrajectoryError",
    "VectorCapture",
    "array_metadata",
    "deterministic_top_k",
    "float32_bytes",
    "l2_norm",
    "sha256_bytes",
]

PROTOCOL = "CassiQwen L18 generated-token field-output trajectory"
VERSION = 1
EXPECTED_LLAMA_VERSION = l16.EXPECTED_LLAMA_VERSION
EXPECTED_MODEL_SHA256 = l16.EXPECTED_MODEL_SHA256
HIDDEN_DIMENSION = 5120
TRUNK_LAYER_COUNT = 64
HEAD_OUTPUT_REFERENCE_INDEX = 64
CAPTURE_LAYER_INDICES = tuple(range(TRUNK_LAYER_COUNT))
DEFAULT_CONTEXT_SIZE = l16.CONTEXT_SIZE
DEFAULT_GPU_LAYERS = 99
DEFAULT_TOP_K = l16.TOP_K
MAX_TOKEN_PIECE_BYTES = 1 << 20


class TrajectoryError(RuntimeError):
    """A checked L18 runtime, ABI, shape, or lifecycle failure."""


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 digest of raw bytes."""

    return hashlib.sha256(data).hexdigest()


def _finite_c_array(values: Any, *, label: str, shape: tuple[int, ...] | None = None) -> np.ndarray:
    """Copy values to finite native float32 C-contiguous storage."""

    try:
        array = np.asarray(values, dtype=np.float32)
    except (TypeError, ValueError) as error:
        raise TrajectoryError(f"{label} is not a float32 array: {error}") from error
    if shape is not None and array.shape != shape:
        raise TrajectoryError(f"{label} shape must be {shape}, got {array.shape}")
    if not array.flags.c_contiguous:
        array = np.ascontiguousarray(array)
    if not np.isfinite(array).all():
        raise TrajectoryError(f"{label} contains non-finite values")
    if not array.flags.c_contiguous:
        raise TrajectoryError(f"{label} is not C-contiguous")
    return array


def float32_bytes(values: Any) -> bytes:
    """Return finite C-order little-endian float32 bytes for an array."""

    array = _finite_c_array(values, label="float32 values")
    little = array.astype("<f4", copy=False)
    if not little.flags.c_contiguous:
        little = np.ascontiguousarray(little)
    return little.tobytes(order="C")


def l2_norm(values: Any) -> float:
    """Return the finite float64 L2 norm of a numeric array."""

    array = _finite_c_array(values, label="norm values")
    norm = float(np.linalg.norm(array.astype(np.float64, copy=False).reshape(-1)))
    if not math.isfinite(norm):
        raise TrajectoryError("array L2 norm is non-finite")
    return norm


def array_metadata(values: Any, *, label: str = "array") -> dict[str, Any]:
    """Describe a finite float32 C-contiguous array without mutating it."""

    array = _finite_c_array(values, label=label)
    raw = float32_bytes(array)
    norm = float(np.linalg.norm(array.astype(np.float64, copy=False).reshape(-1)))
    maximum = float(np.max(np.abs(array))) if array.size else 0.0
    if not math.isfinite(norm) or not math.isfinite(maximum):
        raise TrajectoryError(f"{label} has non-finite norm or maximum")
    return {
        "dtype": "float32",
        "shape": list(array.shape),
        "layout": "C",
        "nbytes": len(raw),
        "sha256": sha256_bytes(raw),
        "l2_norm": norm,
        "max_abs": maximum,
    }


def deterministic_top_k(logits: Any, count: int = DEFAULT_TOP_K) -> list[dict[str, float | int]]:
    """Return deterministic descending-logit rows with token-id tie breaking."""

    array = _finite_c_array(logits, label="logits")
    if array.ndim != 1:
        raise TrajectoryError(f"logits must be one-dimensional, got {array.shape}")
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise TrajectoryError(f"top-k count must be a positive integer, got {count!r}")
    if count > array.size:
        raise TrajectoryError(f"top-k count {count} exceeds vocabulary size {array.size}")
    token_ids = np.arange(array.size, dtype=np.int64)
    # lexsort uses the last key as primary: descending float64 logit, then
    # ascending token ID for exact deterministic ties.
    order = np.lexsort((token_ids, -array.astype(np.float64, copy=False)))[:count]
    return [{"token_id": int(index), "logit": float(array[index])} for index in order]


@dataclass(frozen=True)
class RuntimeConfig:
    """Local pinned runtime paths and b10472 context settings."""

    model_path: Path = field(default_factory=lambda: QWEN_MODEL_PATH)
    dll_dir: Path = field(default_factory=lambda: QWEN_DLL_DIR)
    context_size: int = DEFAULT_CONTEXT_SIZE
    gpu_layers: int = DEFAULT_GPU_LAYERS
    n_batch: int | None = None
    n_ubatch: int | None = None
    expected_model_sha256: str = EXPECTED_MODEL_SHA256

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_path", Path(self.model_path))
        object.__setattr__(self, "dll_dir", Path(self.dll_dir))
        if self.context_size <= 0:
            raise TrajectoryError("context_size must be positive")
        if self.gpu_layers < 0:
            raise TrajectoryError("gpu_layers must be non-negative")
        if self.n_batch is not None and self.n_batch <= 0:
            raise TrajectoryError("n_batch must be positive when supplied")
        if self.n_ubatch is not None and self.n_ubatch <= 0:
            raise TrajectoryError("n_ubatch must be positive when supplied")
        if len(self.expected_model_sha256) != 64:
            raise TrajectoryError("expected_model_sha256 must be a 64-character digest")


@dataclass(frozen=True)
class VectorCapture:
    """One copied trunk or final-output vector and stable raw-data metadata.

    ``layer_index`` 0..63 means a field trunk vector.  Index 64 is a final
    output-feature reference returned by ``llama_get_embeddings_ith`` after
    Qwen's output RMS norm; it is never part of the field recurrence.
    """

    token_index: int
    token_position: int
    layer_index: int
    role: str
    values: np.ndarray = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.layer_index < 0 or self.layer_index > HEAD_OUTPUT_REFERENCE_INDEX:
            raise TrajectoryError(f"capture layer index is outside 0..64: {self.layer_index}")
        expected_role = "field_trunk" if self.layer_index < TRUNK_LAYER_COUNT else "head_output_reference"
        if self.role != expected_role:
            raise TrajectoryError(
                f"layer {self.layer_index} must have role {expected_role!r}, got {self.role!r}"
            )
        array = _finite_c_array(self.values, label=f"layer {self.layer_index} vector", shape=(HIDDEN_DIMENSION,))
        if float(np.linalg.norm(array.astype(np.float64, copy=False))) <= 0.0:
            raise TrajectoryError(f"layer {self.layer_index} vector has zero L2 norm")
        object.__setattr__(self, "values", array)

    @property
    def raw_bytes(self) -> bytes:
        return float32_bytes(self.values)

    @property
    def sha256(self) -> str:
        return sha256_bytes(self.raw_bytes)

    @property
    def l2_norm(self) -> float:
        return float(np.linalg.norm(self.values.astype(np.float64, copy=False)))

    def as_dict(self, *, include_values: bool = True, include_base64: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "token_index": self.token_index,
            "token_position": self.token_position,
            "layer_index": self.layer_index,
            "role": self.role,
            **array_metadata(self.values, label=f"layer {self.layer_index} vector"),
        }
        if include_values:
            result["values"] = self.values.copy()
        if include_base64:
            result["raw_f32_b64"] = base64.b64encode(self.raw_bytes).decode("ascii")
        return result


@dataclass(frozen=True)
class DecodeRecord:
    """Copied data from one initial, token, or virtual-embedding decode."""

    protocol: str
    version: int
    decode_index: int
    token_index: int
    mode: str
    token_ids: tuple[int, ...]
    token_positions: tuple[int, ...]
    token_pieces: tuple[str, ...]
    trunk: tuple[VectorCapture, ...]
    head_output_reference: VectorCapture
    ordinary_logits: np.ndarray = field(repr=False, compare=False)
    ordinary_top_k: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.mode not in {"initial_tokens", "token", "embedding"}:
            raise TrajectoryError(f"unknown decode mode {self.mode!r}")
        if len(self.trunk) != TRUNK_LAYER_COUNT:
            raise TrajectoryError(f"decode must contain 64 trunk captures, got {len(self.trunk)}")
        if tuple(c.layer_index for c in self.trunk) != tuple(range(TRUNK_LAYER_COUNT)):
            raise TrajectoryError("trunk captures are not in true ascending layer order")
        if self.head_output_reference.layer_index != HEAD_OUTPUT_REFERENCE_INDEX:
            raise TrajectoryError("head-output reference must use index 64")
        if self.head_output_reference.role != "head_output_reference":
            raise TrajectoryError("reference must come from the public output-embedding path")
        if self.mode == "embedding":
            if self.token_ids:
                raise TrajectoryError("embedding decode cannot carry token IDs")
            if len(self.token_positions) != 1:
                raise TrajectoryError("embedding decode requires exactly one position")
        else:
            if len(self.token_ids) != len(self.token_positions):
                raise TrajectoryError("token ID and position counts differ")
            if not self.token_ids:
                raise TrajectoryError("token decode requires token IDs")
        logits = _finite_c_array(self.ordinary_logits, label="ordinary logits")
        if logits.ndim != 1:
            raise TrajectoryError("ordinary logits must be one-dimensional")
        object.__setattr__(self, "ordinary_logits", logits)
        if not math.isfinite(float(self.decode_index)):
            raise TrajectoryError("decode index is not finite")

    @property
    def final_position(self) -> int:
        return self.token_positions[-1]

    @property
    def final_token_id(self) -> int | None:
        return self.token_ids[-1] if self.token_ids else None

    @property
    def final_logits(self) -> np.ndarray:
        """Alias emphasizing that these are the ordinary frozen-Qwen logits."""

        return self.ordinary_logits

    @property
    def head_output_vector(self) -> np.ndarray:
        """Final Qwen output features after output RMS norm, never a trunk vector."""

        return self.head_output_reference.values

    @property
    def head_output_raw(self) -> bytes:
        """Little-endian raw bytes for the public final-output reference."""

        return self.head_output_reference.raw_bytes

    @property
    def head_output_norm(self) -> float:
        """Float64 L2 norm of the public final-output reference."""

        return self.head_output_reference.l2_norm

    @property
    def all_layers(self) -> tuple[VectorCapture, ...]:
        """Return trunk 0..63 followed by the separate final-output reference."""

        return self.trunk + (self.head_output_reference,)

    def to_dict(
        self,
        *,
        include_vectors: bool = True,
        include_logits: bool = True,
        include_base64: bool = False,
    ) -> dict[str, Any]:
        """Convenience alias for :meth:`as_dict` used by JSON/event runners."""

        return self.as_dict(
            include_vectors=include_vectors,
            include_logits=include_logits,
            include_base64=include_base64,
        )

    def as_dict(
        self,
        *,
        include_vectors: bool = True,
        include_logits: bool = True,
        include_base64: bool = False,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "protocol": self.protocol,
            "version": self.version,
            "decode_index": self.decode_index,
            "token_index": self.token_index,
            "mode": self.mode,
            "token_ids": list(self.token_ids),
            "token_positions": list(self.token_positions),
            "token_pieces": list(self.token_pieces),
            "trunk_layer_indices": list(range(TRUNK_LAYER_COUNT)),
            "head_output_reference_index": HEAD_OUTPUT_REFERENCE_INDEX,
            "trunk": [
                capture.as_dict(include_values=include_vectors, include_base64=include_base64)
                for capture in self.trunk
            ],
            "head_output_reference": self.head_output_reference.as_dict(
                include_values=include_vectors, include_base64=include_base64
            ),
            "ordinary_logits_metadata": array_metadata(self.ordinary_logits, label="ordinary logits"),
            "ordinary_top_k": [dict(row) for row in self.ordinary_top_k],
        }
        if include_logits:
            result["ordinary_logits"] = self.ordinary_logits.copy()
        if include_base64:
            result["ordinary_logits_raw_f32_b64"] = base64.b64encode(float32_bytes(self.ordinary_logits)).decode("ascii")
        return result


@dataclass
class _BatchStorage:
    """Own every ctypes/NumPy allocation referenced by one LlamaBatch."""

    batch: l16.LlamaBatch
    token_values: Any | None
    embedding_values: Any | None
    embedding_array: np.ndarray | None
    position_values: Any
    n_seq_values: Any
    sequence_values: Any
    sequence_pointers: Any
    logit_values: Any


def _validate_token_ids(token_ids: Iterable[int], *, label: str = "token_ids") -> tuple[int, ...]:
    values = tuple(token_ids)
    if not values:
        raise TrajectoryError(f"{label} cannot be empty")
    for token_id in values:
        if isinstance(token_id, bool) or not isinstance(token_id, (int, np.integer)):
            raise TrajectoryError(f"{label} contains a non-integer token ID: {token_id!r}")
        if not -(1 << 31) <= int(token_id) < (1 << 31):
            raise TrajectoryError(f"{label} contains an int32-overflow token ID: {token_id!r}")
    return tuple(int(token_id) for token_id in values)


def _validate_positions(positions: Iterable[int], *, context_size: int) -> tuple[int, ...]:
    values = tuple(positions)
    if not values:
        raise TrajectoryError("positions cannot be empty")
    for position in values:
        if isinstance(position, bool) or not isinstance(position, (int, np.integer)):
            raise TrajectoryError(f"position is not an integer: {position!r}")
        if not 0 <= int(position) < context_size:
            raise TrajectoryError(f"position {position} is outside context range [0, {context_size})")
    return tuple(int(position) for position in values)


def _build_token_batch(token_ids: tuple[int, ...], positions: tuple[int, ...]) -> _BatchStorage:
    count = len(token_ids)
    if count != len(positions):
        raise TrajectoryError("token and position batch lengths differ")
    token_values = (ct.c_int32 * count)(*token_ids)
    embedding_values = None
    embedding_array = None
    position_values = (ct.c_int32 * count)(*positions)
    n_seq_values = (ct.c_int32 * count)(*([1] * count))
    sequence_values = (ct.c_int32 * count)(*([0] * count))
    sequence_pointers = (ct.POINTER(ct.c_int32) * count)()
    for index in range(count):
        sequence_pointers[index] = ct.cast(
            ct.byref(sequence_values, index * ct.sizeof(ct.c_int32)), ct.POINTER(ct.c_int32)
        )
    logit_values = (ct.c_int8 * count)()
    logit_values[count - 1] = 1
    batch = l16.LlamaBatch(
        n_tokens=count,
        token=token_values,
        embd=ct.POINTER(ct.c_float)(),
        pos=position_values,
        n_seq_id=n_seq_values,
        seq_id=sequence_pointers,
        logits=logit_values,
    )
    return _BatchStorage(
        batch,
        token_values,
        embedding_values,
        embedding_array,
        position_values,
        n_seq_values,
        sequence_values,
        sequence_pointers,
        logit_values,
    )


def _build_embedding_batch(vector: np.ndarray, position: int) -> _BatchStorage:
    # ``token`` is intentionally NULL: b10472 selects the embd path when the
    # one-row float32 embedding pointer is present.
    embedding_array = _finite_c_array(vector, label="embedding", shape=(HIDDEN_DIMENSION,))
    embedding_values = embedding_array.ctypes.data_as(ct.POINTER(ct.c_float))
    position_values = (ct.c_int32 * 1)(position)
    n_seq_values = (ct.c_int32 * 1)(1)
    sequence_values = (ct.c_int32 * 1)(0)
    sequence_pointers = (ct.POINTER(ct.c_int32) * 1)()
    sequence_pointers[0] = ct.cast(sequence_values, ct.POINTER(ct.c_int32))
    logit_values = (ct.c_int8 * 1)(1)
    batch = l16.LlamaBatch(
        n_tokens=1,
        token=ct.POINTER(ct.c_int32)(),
        embd=embedding_values,
        pos=position_values,
        n_seq_id=n_seq_values,
        seq_id=sequence_pointers,
        logits=logit_values,
    )
    return _BatchStorage(
        batch,
        None,
        embedding_values,
        embedding_array,
        position_values,
        n_seq_values,
        sequence_values,
        sequence_pointers,
        logit_values,
    )


class L18GeneratedTokenTrajectory:
    """One persistent local Qwen context with all-layer input capture enabled.

    Construction loads the pinned model/runtime by default.  Set ``autoload``
    false to construct an unloaded owner and call :meth:`load` explicitly.  A
    context manager or explicit :meth:`close` is required for deterministic
    cleanup; the destructor is a final best-effort fallback only.
    """

    def __init__(self, config: RuntimeConfig | None = None, *, autoload: bool = True) -> None:
        self.config = config or RuntimeConfig()
        self._cookie: Any | None = None
        self._dll_handles: list[Any] = []
        self._ggml: Any | None = None
        self._lib: Any | None = None
        self._set_layer: Callable[..., None] | None = None
        self._get_layer: Callable[..., Any] | None = None
        self._backend_initialized = False
        self._model = 0
        self._context = 0
        self._vocab = 0
        self.hidden_dimension = HIDDEN_DIMENSION
        self.layer_count = TRUNK_LAYER_COUNT
        self.vocabulary_size = 0
        self._closed = False
        self._hooks_enabled = False
        self._decode_index = 0
        self._generated_token_count = 0
        self._initial_decoded = False
        self._last_position: int | None = None
        if autoload:
            self.load()

    @property
    def loaded(self) -> bool:
        return bool(self._lib is not None and self._context and not self._closed)

    @property
    def context(self) -> int:
        self._require_loaded()
        return self._context

    @property
    def model(self) -> int:
        self._require_loaded()
        return self._model

    def _require_loaded(self) -> None:
        if not self.loaded:
            raise TrajectoryError("L18 trajectory is not loaded or has already been closed")

    def load(self) -> "L18GeneratedTokenTrajectory":
        """Load DLLs/model/context once; never reloads a live owner."""

        if self.loaded:
            return self
        if self._cookie is not None or self._model or self._context:
            raise TrajectoryError("trajectory load state is partially initialized")
        self._closed = False
        try:
            self._load_inner()
        except BaseException:
            self.close(suppress=True)
            raise
        return self

    def _load_inner(self) -> None:
        runtime_dir = self.config.dll_dir.resolve()
        model_path = self.config.model_path.resolve()
        llama_path = runtime_dir / "llama.dll"
        ggml_path = runtime_dir / "ggml.dll"
        ggml_base_path = runtime_dir / "ggml-base.dll"
        omp_path = runtime_dir / "libomp140.x86_64.dll"
        for path in (model_path, llama_path, ggml_path, ggml_base_path, omp_path):
            if not path.is_file():
                raise TrajectoryError(f"required local artifact is missing: {path}")
        model_hash = l16.sha256_file(model_path)
        if model_hash != self.config.expected_model_sha256:
            raise TrajectoryError(f"GGUF SHA-256 mismatch: {model_hash}")
        hook_names = l16.resolve_wip_hook_names(llama_path)

        # Keep this cookie alive through every sibling DLL load.  No global PATH
        # mutation is used, and no DLL/model work occurs at module import time.
        self._cookie = os.add_dll_directory(str(runtime_dir))
        self._dll_handles = [ct.WinDLL(str(omp_path)), ct.WinDLL(str(ggml_base_path))]
        self._ggml = ct.WinDLL(str(ggml_path))
        self._dll_handles.append(self._ggml)
        self._ggml.ggml_backend_load_all_from_path.argtypes = [ct.c_char_p]
        self._ggml.ggml_backend_load_all_from_path.restype = None
        self._ggml.ggml_backend_load_all_from_path(os.fsencode(runtime_dir))

        self._lib = ct.WinDLL(str(llama_path))
        self._dll_handles.append(self._lib)
        l16.configure_public_api(self._lib)
        self._configure_trajectory_api(self._lib)
        self._set_layer, self._get_layer = l16.configure_wip_hooks(self._lib, hook_names)
        version = (self._lib.llama_version() or b"").decode("utf-8")
        if version != EXPECTED_LLAMA_VERSION:
            raise TrajectoryError(f"llama_version mismatch: {version!r}")
        if not bool(self._lib.llama_supports_gpu_offload()):
            raise TrajectoryError("installed llama runtime does not report GPU offload support")
        self._lib.llama_backend_init()
        self._backend_initialized = True

        model_params = self._lib.llama_model_default_params()
        model_params.n_gpu_layers = self.config.gpu_layers
        self._model = int(self._lib.llama_model_load_from_file(os.fsencode(model_path), model_params) or 0)
        if not self._model:
            raise TrajectoryError("llama_model_load_from_file returned null")
        self.hidden_dimension = int(self._lib.llama_model_n_embd(self._model))
        self.layer_count = int(self._lib.llama_model_n_layer(self._model))
        if self.hidden_dimension != HIDDEN_DIMENSION:
            raise TrajectoryError(f"model hidden width mismatch: {self.hidden_dimension}")
        if self.layer_count != TRUNK_LAYER_COUNT:
            raise TrajectoryError(f"model layer count mismatch: {self.layer_count}; expected 64")
        output_dimension = int(self._lib.llama_model_n_embd_out(self._model))
        if output_dimension != HIDDEN_DIMENSION:
            raise TrajectoryError(f"model output width mismatch: {output_dimension}")
        self._vocab = int(self._lib.llama_model_get_vocab(self._model) or 0)
        if not self._vocab:
            raise TrajectoryError("llama_model_get_vocab returned null")
        self.vocabulary_size = int(self._lib.llama_vocab_n_tokens(self._vocab))
        if self.vocabulary_size <= 0:
            raise TrajectoryError(f"model vocabulary size is invalid: {self.vocabulary_size}")

        self._create_context()

    def _create_context(self) -> None:
        """Create one fresh context against the already-loaded model."""

        self._require_loaded_model()
        params = self._lib.llama_context_default_params()
        params.n_ctx = self.config.context_size
        params.n_batch = self.config.n_batch or self.config.context_size
        params.n_ubatch = self.config.n_ubatch or params.n_batch
        params.n_seq_max = 1
        self._context = int(self._lib.llama_init_from_model(self._model, params) or 0)
        if not self._context:
            raise TrajectoryError("llama_init_from_model returned null")
        self._lib.llama_set_embeddings(self._context, True)
        if self._set_layer is None:
            raise TrajectoryError("layer capture setter is unavailable")
        for layer_index in CAPTURE_LAYER_INDICES:
            self._set_layer(self._context, layer_index, True)
        self._hooks_enabled = True
        self._decode_index = 0
        self._generated_token_count = 0
        self._initial_decoded = False
        self._last_position = None

    def _require_loaded_model(self) -> None:
        if self._lib is None or not self._model or self._closed:
            raise TrajectoryError("llama model is not loaded")

    def reset_context(self) -> None:
        """Drop only the KV/context state and create a fresh capture context."""

        self._require_loaded()
        if self._context:
            if self._set_layer is not None:
                for layer_index in CAPTURE_LAYER_INDICES:
                    self._set_layer(self._context, layer_index, False)
            self._hooks_enabled = False
            self._lib.llama_set_embeddings(self._context, False)
            self._lib.llama_free(self._context)
            self._context = 0
        self._create_context()

    @staticmethod
    def _configure_trajectory_api(lib: Any) -> None:
        """Configure b10472 public token-piece, EOG, and output-embedding APIs."""

        lib.llama_token_to_piece.argtypes = [
            ct.c_void_p,
            ct.c_int32,
            ct.POINTER(ct.c_char),
            ct.c_int32,
            ct.c_int32,
            ct.c_bool,
        ]
        lib.llama_token_to_piece.restype = ct.c_int32
        lib.llama_vocab_is_eog.argtypes = [ct.c_void_p, ct.c_int32]
        lib.llama_vocab_is_eog.restype = ct.c_bool
        lib.llama_set_embeddings.argtypes = [ct.c_void_p, ct.c_bool]
        lib.llama_set_embeddings.restype = None
        lib.llama_get_embeddings_ith.argtypes = [ct.c_void_p, ct.c_int32]
        lib.llama_get_embeddings_ith.restype = ct.POINTER(ct.c_float)
        lib.llama_model_n_embd_out.argtypes = [ct.c_void_p]
        lib.llama_model_n_embd_out.restype = ct.c_int32

    def tokenize(self, prompt: str | bytes) -> tuple[int, ...]:
        """Tokenize UTF-8 prompt bytes with the pinned local vocabulary."""

        self._require_loaded()
        if isinstance(prompt, str):
            raw = prompt.encode("utf-8")
        elif isinstance(prompt, bytes):
            raw = prompt
        else:
            raise TrajectoryError("prompt must be text or UTF-8 bytes")
        return tuple(l16.tokenize(self._lib, self._vocab, raw))

    def token_piece_bytes(self, token_id: int, *, special: bool = False, lstrip: int = 0) -> bytes:
        """Return one tokenizer piece using the local pinned vocab API."""

        self._require_loaded()
        if isinstance(token_id, bool) or not isinstance(token_id, (int, np.integer)):
            raise TrajectoryError(f"token_id is not an integer: {token_id!r}")
        if not isinstance(lstrip, int) or isinstance(lstrip, bool) or lstrip < 0:
            raise TrajectoryError(f"lstrip must be a non-negative integer, got {lstrip!r}")
        capacity = 256
        while capacity <= MAX_TOKEN_PIECE_BYTES:
            buffer = (ct.c_char * capacity)()
            count = int(
                self._lib.llama_token_to_piece(
                    self._vocab, int(token_id), buffer, capacity, lstrip, bool(special)
                )
            )
            if count >= 0:
                if count > capacity:
                    raise TrajectoryError(f"token piece API returned oversized count {count}")
                return bytes(buffer[:count])
            required = -count
            if required <= capacity:
                required = capacity * 2
            capacity = required
        raise TrajectoryError("token piece exceeds the bounded local buffer")

    def token_piece(self, token_id: int, *, special: bool = False, lstrip: int = 0) -> str:
        """Return one tokenizer piece as deterministic replacement-decoded UTF-8."""

        return self.token_piece_bytes(token_id, special=special, lstrip=lstrip).decode("utf-8", errors="replace")
    token_to_piece = token_piece


    def token_is_eog(self, token_id: int) -> bool:
        """Return the local vocab's end-of-generation classification."""

        self._require_loaded()
        if isinstance(token_id, bool) or not isinstance(token_id, (int, np.integer)):
            raise TrajectoryError(f"token_id is not an integer: {token_id!r}")
        return bool(self._lib.llama_vocab_is_eog(self._vocab, int(token_id)))

    # Short public aliases useful to a runner while retaining explicit methods.
    is_eog = token_is_eog

    def top_k_with_pieces(self, logits: Any, count: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
        """Rank logits and attach local piece/EOG metadata to each row."""

        rows = deterministic_top_k(logits, count)
        for row in rows:
            token_id = int(row["token_id"])
            row["piece"] = self.token_piece(token_id)
            row["is_eog"] = self.token_is_eog(token_id)
        return rows

    def _copy_capture(self, layer_index: int, *, token_row: int, token_index: int, token_position: int) -> VectorCapture:
        assert self._get_layer is not None
        pointer = self._get_layer(self._context, layer_index)
        if not pointer:
            raise TrajectoryError(f"layer {layer_index} getter returned null")
        if token_row < 0:
            raise TrajectoryError(f"capture token row is negative: {token_row}")
        raw_address = ct.addressof(pointer.contents) + token_row * HIDDEN_DIMENSION * ct.sizeof(ct.c_float)
        final_pointer = ct.cast(raw_address, ct.POINTER(ct.c_float))
        values = np.ctypeslib.as_array(final_pointer, shape=(HIDDEN_DIMENSION,)).astype(np.float32, copy=True)
        values = _finite_c_array(values, label=f"layer {layer_index} capture", shape=(HIDDEN_DIMENSION,))
        return VectorCapture(token_index, token_position, layer_index, "field_trunk", values)

    def _copy_output_embedding(self, *, token_index: int, token_position: int) -> VectorCapture:
        pointer = self._lib.llama_get_embeddings_ith(self._context, -1)
        if not pointer:
            raise TrajectoryError("llama_get_embeddings_ith returned null")
        values = np.ctypeslib.as_array(pointer, shape=(HIDDEN_DIMENSION,)).astype(np.float32, copy=True)
        values = _finite_c_array(values, label="final output embedding", shape=(HIDDEN_DIMENSION,))
        return VectorCapture(token_index, token_position, HEAD_OUTPUT_REFERENCE_INDEX, "head_output_reference", values)

    def _decode_batch(
        self,
        storage: _BatchStorage,
        *,
        mode: str,
        token_ids: tuple[int, ...],
        token_positions: tuple[int, ...],
        token_index: int,
    ) -> DecodeRecord:
        self._require_loaded()
        status = int(self._lib.llama_decode(self._context, storage.batch))
        if status != 0:
            raise TrajectoryError(f"llama_decode returned {status}")
        logits_pointer = self._lib.llama_get_logits_ith(self._context, -1)
        if not logits_pointer:
            raise TrajectoryError("llama_get_logits_ith returned null")
        logits = np.ctypeslib.as_array(logits_pointer, shape=(self.vocabulary_size,)).astype(np.float32, copy=True)
        logits = _finite_c_array(logits, label="ordinary logits", shape=(self.vocabulary_size,))
        token_row = storage.batch.n_tokens - 1
        final_position = token_positions[-1]
        captures = tuple(
            self._copy_capture(
                layer_index,
                token_row=token_row,
                token_index=token_index,
                token_position=final_position,
            )
            for layer_index in CAPTURE_LAYER_INDICES
        )
        head_output = self._copy_output_embedding(
            token_index=token_index,
            token_position=final_position,
        )
        pieces = tuple(self.token_piece(token_id) for token_id in token_ids)
        ordinary_top_k = tuple(self.top_k_with_pieces(logits, DEFAULT_TOP_K))
        return DecodeRecord(
            protocol=PROTOCOL,
            version=VERSION,
            decode_index=self._decode_index,
            token_index=token_index,
            mode=mode,
            token_ids=token_ids,
            token_positions=token_positions,
            token_pieces=pieces,
            trunk=captures,
            head_output_reference=head_output,
            ordinary_logits=logits,
            ordinary_top_k=ordinary_top_k,
        )

    def _check_first_or_next_positions(self, positions: tuple[int, ...], *, initial: bool) -> None:
        if initial:
            if self._initial_decoded:
                raise TrajectoryError("initial token batch was already decoded")
            return
        if not self._initial_decoded:
            raise TrajectoryError("decode_initial must precede one-token decodes")
        if len(positions) != 1:
            raise TrajectoryError("subsequent decodes must contain exactly one position")
        if self._last_position is not None and positions[0] <= self._last_position:
            raise TrajectoryError(
                f"subsequent position {positions[0]} must exceed prior position {self._last_position}"
            )

    def decode_initial(self, token_ids: Sequence[int], positions: Sequence[int] | None = None) -> DecodeRecord:
        """Decode the initial prompt in bounded causal batches."""

        self._require_loaded()
        ids = _validate_token_ids(token_ids)
        actual_positions = _validate_positions(
            range(len(ids)) if positions is None else positions,
            context_size=self.config.context_size,
        )
        if len(ids) != len(actual_positions):
            raise TrajectoryError("initial token and position batch lengths differ")
        self._check_first_or_next_positions(actual_positions, initial=True)
        chunk_size = self.config.n_ubatch or self.config.n_batch or self.config.context_size
        record: DecodeRecord | None = None
        for start in range(0, len(ids), chunk_size):
            stop = min(start + chunk_size, len(ids))
            record = self._decode_batch(
                _build_token_batch(ids[start:stop], actual_positions[start:stop]),
                mode="initial_tokens",
                token_ids=ids[start:stop],
                token_positions=actual_positions[start:stop],
                token_index=-1,
            )
        assert record is not None
        self._initial_decoded = True
        self._last_position = actual_positions[-1]
        self._decode_index += 1
        return record

    def decode_token(
        self,
        token_id: int,
        position: int,
        *,
        token_index: int | None = None,
    ) -> DecodeRecord:
        """Decode one ordinary token at its caller-supplied absolute position.

        ``token_index`` defaults to the generated-token counter. Offline causal
        dataset builders may instead bind the capture to the token's index in
        their already-frozen source sequence.
        """

        self._require_loaded()
        ids = _validate_token_ids((token_id,))
        actual_positions = _validate_positions((position,), context_size=self.config.context_size)
        self._check_first_or_next_positions(actual_positions, initial=False)
        if token_index is None:
            record_token_index = self._generated_token_count
        elif isinstance(token_index, bool) or not isinstance(token_index, (int, np.integer)) or int(token_index) < 0:
            raise TrajectoryError(f"token_index is not a nonnegative integer: {token_index!r}")
        else:
            record_token_index = int(token_index)
        record = self._decode_batch(
            _build_token_batch(ids, actual_positions),
            mode="token",
            token_ids=ids,
            token_positions=actual_positions,
            token_index=record_token_index,
        )
        self._generated_token_count += 1
        self._last_position = actual_positions[-1]
        self._decode_index += 1
        return record

    def decode_embedding(self, vector: Any, position: int) -> DecodeRecord:
        """Run an optional one-row virtual embedding batch.

        The b10472 ABI requires ``LlamaBatch.token == NULL`` and a contiguous
        float32 ``embd`` pointer.  This is a full forward through the model,
        not a final-residual writeback hook; all WIP captures remain read-only.
        """

        self._require_loaded()
        actual_positions = _validate_positions((position,), context_size=self.config.context_size)
        self._check_first_or_next_positions(actual_positions, initial=False)
        embedding = _finite_c_array(vector, label="embedding", shape=(HIDDEN_DIMENSION,))
        generated_index = self._generated_token_count
        record = self._decode_batch(
            _build_embedding_batch(embedding, actual_positions[0]),
            mode="embedding",
            token_ids=(),
            token_positions=actual_positions,
            token_index=generated_index,
        )
        self._generated_token_count += 1
        self._last_position = actual_positions[-1]
        self._decode_index += 1
        return record

    def close(self, *, suppress: bool = False) -> None:
        """Disable every hook, then free context/model/backend and DLL cookie."""

        if self._closed and self._cookie is None and not self._context and not self._model:
            return
        errors: list[str] = []
        context = self._context
        lib = self._lib
        set_layer = self._set_layer
        if context and set_layer is not None:
            # Attempt every legal index even when an earlier disable fails.
            for layer_index in CAPTURE_LAYER_INDICES:
                try:
                    set_layer(context, layer_index, False)
                except BaseException as error:
                    errors.append(f"disable layer {layer_index}: {error}")
        self._hooks_enabled = False
        if context and lib is not None:
            try:
                lib.llama_set_embeddings(context, False)
            except BaseException as error:
                errors.append(f"disable output embeddings: {error}")
        if context and lib is not None:
            try:
                lib.llama_free(context)
            except BaseException as error:
                errors.append(f"llama_free: {error}")
        self._context = 0
        if self._model and lib is not None:
            try:
                lib.llama_model_free(self._model)
            except BaseException as error:
                errors.append(f"llama_model_free: {error}")
        self._model = 0
        if self._backend_initialized and lib is not None:
            try:
                lib.llama_backend_free()
            except BaseException as error:
                errors.append(f"llama_backend_free: {error}")
        self._backend_initialized = False
        cookie = self._cookie
        self._cookie = None
        if cookie is not None:
            try:
                cookie.close()
            except BaseException as error:
                errors.append(f"DLL directory cookie close: {error}")
        self._lib = None
        self._ggml = None
        self._set_layer = None
        self._get_layer = None
        self._dll_handles.clear()
        self._vocab = 0
        self._closed = True
        if errors and not suppress:
            raise TrajectoryError("; ".join(errors))

    def __enter__(self) -> "L18GeneratedTokenTrajectory":
        self._require_loaded()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close(suppress=exc_type is not None)

    def __del__(self) -> None:  # pragma: no cover - interpreter shutdown fallback.
        try:
            self.close(suppress=True)
        except BaseException:
            pass


GeneratedTokenTrajectory = L18GeneratedTokenTrajectory
