"""Offline Qwen3.5 field-language output head.

This module deliberately does not load a llama.cpp model.  It reads only the
GGUF header/descriptors, loads the frozen output RMS weights, and invokes the
pinned ggml-base Q6_K row dequantizer while evaluating contiguous vocabulary
rows.  It is an experimental L18 lab component; callers must opt in with
``enabled=True``.

The GGUF tensor dimensions are the on-disk GGML order used by the pinned
Qwen3.5 file: ``output.weight`` is ``[hidden_dimension, vocabulary_size]``.
The first dimension is contiguous, so each vocabulary column is one contiguous
row of ``hidden_dimension`` values in the quantized data stream.
"""

from __future__ import annotations

import ctypes as ct
import math
import os
import struct
import sys
from dataclasses import dataclass
from numbers import Integral
from pathlib import Path
from typing import Any, Callable, BinaryIO, Sequence

import numpy as np


GGUF_MAGIC = b"GGUF"
GGUF_VERSION = 3
GGML_TYPE_F32 = 0
GGML_TYPE_Q6_K = 14
Q6_K_BLOCK_VALUES = 256
Q6_K_BLOCK_BYTES = 210
EXPECTED_ARCHITECTURE = "qwen35"
EXPECTED_HIDDEN_DIMENSION = 5120
EXPECTED_VOCABULARY_SIZE = 248320
DEFAULT_CHUNK_TOKENS = 64
DEFAULT_ALIGNMENT = 32
MAX_METADATA_ENTRIES = 100_000
MAX_METADATA_ARRAY_VALUES = 1_000_000
MAX_STRING_BYTES = 16 * 1024 * 1024


class GGUFError(RuntimeError):
    """A checked GGUF/output-head contract failure."""


@dataclass(frozen=True)
class GGUFTensorDescriptor:
    name: str
    dimensions: tuple[int, ...]
    ggml_type: int
    offset: int

    @property
    def element_count(self) -> int:
        result = 1
        for dimension in self.dimensions:
            result *= dimension
        return result


@dataclass(frozen=True)
class GGUFLayout:
    version: int
    tensor_count: int
    metadata: dict[str, Any]
    tensors: dict[str, GGUFTensorDescriptor]
    data_start: int
    alignment: int
    file_size: int

    def tensor(self, name: str) -> GGUFTensorDescriptor:
        try:
            return self.tensors[name]
        except KeyError as error:
            raise GGUFError(f"GGUF tensor is missing: {name}") from error


class _GGUFStream:
    def __init__(self, handle: BinaryIO, path: Path):
        self.handle = handle
        self.path = path

    @property
    def position(self) -> int:
        return int(self.handle.tell())

    def read_exact(self, count: int, label: str) -> bytes:
        if count < 0:
            raise GGUFError(f"{self.path.name}: negative read size for {label}")
        data = self.handle.read(count)
        if len(data) != count:
            raise GGUFError(
                f"{self.path.name}: truncated {label} (wanted {count} bytes, got {len(data)})"
            )
        return data

    def unpack(self, format_string: str, label: str) -> Any:
        size = struct.calcsize(format_string)
        return struct.unpack(format_string, self.read_exact(size, label))[0]

    def string(self, label: str) -> str:
        length = int(self.unpack("<Q", f"{label} length"))
        if length > MAX_STRING_BYTES:
            raise GGUFError(f"{self.path.name}: {label} is too large ({length} bytes)")
        raw = self.read_exact(length, label)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise GGUFError(f"{self.path.name}: {label} is not UTF-8") from error


def _read_gguf_value(stream: _GGUFStream, value_type: int, label: str) -> Any:
    scalar_formats: dict[int, str] = {
        0: "<B",   # UINT8
        1: "<b",   # INT8
        2: "<H",   # UINT16
        3: "<h",   # INT16
        4: "<I",   # UINT32
        5: "<i",   # INT32
        6: "<f",   # FLOAT32
        7: "<?",   # BOOL
        10: "<Q",  # UINT64
        11: "<q",  # INT64
        12: "<d",  # FLOAT64
    }
    if value_type in scalar_formats:
        return stream.unpack(scalar_formats[value_type], label)
    if value_type == 8:  # STRING
        return stream.string(label)
    if value_type == 9:  # ARRAY
        element_type = int(stream.unpack("<I", f"{label} element type"))
        count = int(stream.unpack("<Q", f"{label} count"))
        if count > MAX_METADATA_ARRAY_VALUES:
            raise GGUFError(f"{stream.path.name}: {label} array is too large ({count} values)")
        return [
            _read_gguf_value(stream, element_type, f"{label}[{index}]")
            for index in range(count)
        ]
    raise GGUFError(f"{stream.path.name}: unsupported GGUF metadata type {value_type}")


def _checked_alignment(value: Any, path: Path) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GGUFError(f"{path.name}: general.alignment is not an integer")
    if value <= 0 or value > (1 << 30):
        raise GGUFError(f"{path.name}: invalid GGUF alignment {value}")
    return value


def _align_up(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def parse_gguf(path: str | os.PathLike[str]) -> GGUFLayout:
    """Read GGUF v3 metadata and tensor descriptors without reading tensor data."""
    model_path = Path(path)
    if not model_path.is_file():
        raise GGUFError(f"GGUF file does not exist: {model_path}")
    file_size = model_path.stat().st_size
    with model_path.open("rb") as handle:
        stream = _GGUFStream(handle, model_path)
        magic = stream.read_exact(4, "magic")
        if magic != GGUF_MAGIC:
            raise GGUFError(f"{model_path.name}: GGUF magic mismatch")
        version = int(stream.unpack("<I", "version"))
        if version != GGUF_VERSION:
            raise GGUFError(f"{model_path.name}: expected GGUF v3, got v{version}")
        tensor_count = int(stream.unpack("<Q", "tensor count"))
        metadata_count = int(stream.unpack("<Q", "metadata count"))
        if tensor_count <= 0:
            raise GGUFError(f"{model_path.name}: tensor count is empty")
        if metadata_count > MAX_METADATA_ENTRIES:
            raise GGUFError(f"{model_path.name}: metadata count is too large ({metadata_count})")

        metadata: dict[str, Any] = {}
        for index in range(metadata_count):
            key = stream.string(f"metadata key {index}")
            if key in metadata:
                raise GGUFError(f"{model_path.name}: duplicate metadata key {key!r}")
            value_type = int(stream.unpack("<I", f"metadata type {key!r}"))
            metadata[key] = _read_gguf_value(stream, value_type, f"metadata {key!r}")

        tensors: dict[str, GGUFTensorDescriptor] = {}
        for index in range(tensor_count):
            name = stream.string(f"tensor {index} name")
            if name in tensors:
                raise GGUFError(f"{model_path.name}: duplicate tensor name {name!r}")
            dimensions_count = int(stream.unpack("<I", f"tensor {name!r} dimension count"))
            if dimensions_count <= 0 or dimensions_count > 8:
                raise GGUFError(
                    f"{model_path.name}: tensor {name!r} has invalid dimension count {dimensions_count}"
                )
            dimensions = tuple(
                int(stream.unpack("<Q", f"tensor {name!r} dimension {dimension_index}"))
                for dimension_index in range(dimensions_count)
            )
            if any(dimension <= 0 for dimension in dimensions):
                raise GGUFError(f"{model_path.name}: tensor {name!r} has non-positive dimensions")
            ggml_type = int(stream.unpack("<I", f"tensor {name!r} type"))
            offset = int(stream.unpack("<Q", f"tensor {name!r} offset"))
            tensors[name] = GGUFTensorDescriptor(name, dimensions, ggml_type, offset)

        alignment_value = metadata.get("general.alignment", DEFAULT_ALIGNMENT)
        alignment = _checked_alignment(alignment_value, model_path)
        descriptors_end = stream.position
        data_start = _align_up(descriptors_end, alignment)
        if data_start > file_size:
            raise GGUFError(f"{model_path.name}: tensor data starts past end of file")
        return GGUFLayout(
            version=version,
            tensor_count=tensor_count,
            metadata=metadata,
            tensors=tensors,
            data_start=data_start,
            alignment=alignment,
            file_size=file_size,
        )


def _architecture_key(value: Any) -> str:
    if not isinstance(value, str):
        raise GGUFError("general.architecture is not a string")
    return value.lower().replace(".", "").replace("_", "").replace("-", "")


def _find_rms_epsilon(metadata: dict[str, Any], architecture: str) -> float:
    candidates = [
        f"{architecture}.attention.layer_norm_rms_epsilon",
        "qwen35.attention.layer_norm_rms_epsilon",
        "qwen3.5.attention.layer_norm_rms_epsilon",
        "qwen3.attention.layer_norm_rms_epsilon",
        "general.layer_norm_rms_epsilon",
    ]
    for key in candidates:
        if key not in metadata:
            continue
        value = metadata[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise GGUFError(f"{key} is not numeric")
        epsilon = float(value)
        if not math.isfinite(epsilon) or epsilon <= 0.0:
            raise GGUFError(f"{key} is not a finite positive RMS epsilon")
        return epsilon
    raise GGUFError("Qwen RMS epsilon metadata is missing")


def _tensor_byte_size(descriptor: GGUFTensorDescriptor) -> int:
    if descriptor.ggml_type == GGML_TYPE_Q6_K:
        if descriptor.element_count % Q6_K_BLOCK_VALUES:
            raise GGUFError(
                f"{descriptor.name}: Q6_K element count {descriptor.element_count} is not block aligned"
            )
        return descriptor.element_count // Q6_K_BLOCK_VALUES * Q6_K_BLOCK_BYTES
    if descriptor.ggml_type == GGML_TYPE_F32:
        return descriptor.element_count * 4
    raise GGUFError(f"{descriptor.name}: unsupported GGML tensor type {descriptor.ggml_type}")


def _validate_tensor_extent(layout: GGUFLayout, descriptor: GGUFTensorDescriptor) -> None:
    if descriptor.offset % layout.alignment:
        raise GGUFError(
            f"{descriptor.name}: tensor offset {descriptor.offset} is not aligned to {layout.alignment}"
        )
    byte_size = _tensor_byte_size(descriptor)
    start = layout.data_start + descriptor.offset
    end = start + byte_size
    if start < layout.data_start or end < start or end > layout.file_size:
        raise GGUFError(f"{descriptor.name}: tensor data extends past GGUF file")


def _finite_vector(values: Any, expected_size: int, label: str) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float32)
    if vector.ndim != 1 or vector.size != expected_size:
        raise GGUFError(f"{label} must have shape ({expected_size},), got {vector.shape}")
    if not np.isfinite(vector).all():
        raise GGUFError(f"{label} contains non-finite values")
    return np.ascontiguousarray(vector)


def _signed_byte(value: int) -> int:
    return value if value < 128 else value - 256

def _decode_q6_k_reference(raw: bytes) -> np.ndarray:
    """Decode Q6_K bytes for the pure unit test's fake DLL seam.

    Production evaluation always calls ``ggml-base.dll``.  This reference
    implementation is intentionally private and is not selected as a runtime
    fallback; it lets the unit test validate the on-disk block layout without
    loading a native library.
    """
    if len(raw) % Q6_K_BLOCK_BYTES:
        raise GGUFError("Q6_K reference input is not block aligned")
    output = np.empty(len(raw) // Q6_K_BLOCK_BYTES * Q6_K_BLOCK_VALUES, dtype=np.float32)
    for block_index in range(len(raw) // Q6_K_BLOCK_BYTES):
        block = raw[block_index * Q6_K_BLOCK_BYTES : (block_index + 1) * Q6_K_BLOCK_BYTES]
        ql = block[0:128]
        qh = block[128:192]
        scales = block[192:208]
        scale_half = struct.unpack_from("<e", block, 208)[0]
        values = output[block_index * Q6_K_BLOCK_VALUES : (block_index + 1) * Q6_K_BLOCK_VALUES]
        for base in (0, 128):
            ql_base = base // 2
            qh_base = base // 4
            scale_base = (base // 128) * 8
            for lane in range(32):
                high = qh[qh_base + lane]
                low_a = ql[ql_base + lane]
                low_b = ql[ql_base + lane + 32]
                q1 = (low_a & 0x0F) | ((high & 0x03) << 4)
                q2 = (low_b & 0x0F) | (((high >> 2) & 0x03) << 4)
                q3 = (low_a >> 4) | (((high >> 4) & 0x03) << 4)
                q4 = (low_b >> 4) | (((high >> 6) & 0x03) << 4)
                values[base + lane] = np.float32(float(scale_half) * _signed_byte(scales[scale_base + lane // 16]) * (q1 - 32))
                values[base + lane + 32] = np.float32(float(scale_half) * _signed_byte(scales[scale_base + lane // 16 + 2]) * (q2 - 32))
                values[base + lane + 64] = np.float32(float(scale_half) * _signed_byte(scales[scale_base + lane // 16 + 4]) * (q3 - 32))
                values[base + lane + 96] = np.float32(float(scale_half) * _signed_byte(scales[scale_base + lane // 16 + 6]) * (q4 - 32))
    return output


class FieldLanguageHead:
    """Frozen Qwen3.5 output head evaluated on one decoded field vector."""

    def __init__(
        self,
        model_path: str | os.PathLike[str],
        dll_path: str | os.PathLike[str] | None = None,
        *,
        enabled: bool = False,
        chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
        expected_hidden_dimension: int = EXPECTED_HIDDEN_DIMENSION,
        expected_vocabulary_size: int = EXPECTED_VOCABULARY_SIZE,
        dequantize_row: Callable[[Any, Any, int], None] | None = None,
    ) -> None:
        if not isinstance(chunk_tokens, int) or chunk_tokens <= 0:
            raise GGUFError("chunk_tokens must be a positive integer")
        if not isinstance(expected_hidden_dimension, int) or expected_hidden_dimension <= 0:
            raise GGUFError("expected_hidden_dimension must be positive")
        if not isinstance(expected_vocabulary_size, int) or expected_vocabulary_size <= 0:
            raise GGUFError("expected_vocabulary_size must be positive")
        self.enabled = bool(enabled)
        self.chunk_tokens = chunk_tokens
        self._closed = False
        self._model_path = Path(model_path)
        self._file: BinaryIO | None = None
        self._dll: Any = None
        self._dll_directory_cookie: Any = None
        self._dequantize_row: Callable[[Any, Any, int], None] | None = None
        self._layout = parse_gguf(self._model_path)
        self._expected_hidden_dimension = expected_hidden_dimension
        self._expected_vocabulary_size = expected_vocabulary_size
        self._architecture = _architecture_key(self._layout.metadata.get("general.architecture"))
        if self._architecture != EXPECTED_ARCHITECTURE:
            raise GGUFError(
                f"expected Qwen3.5 architecture ({EXPECTED_ARCHITECTURE}), got "
                f"{self._layout.metadata.get('general.architecture')!r}"
            )
        self._rms_epsilon = _find_rms_epsilon(self._layout.metadata, self._architecture)

        output = self._layout.tensor("output.weight")
        output_norm = self._layout.tensor("output_norm.weight")
        if output.dimensions != (expected_hidden_dimension, expected_vocabulary_size):
            raise GGUFError(
                f"output.weight dimensions must be "
                f"({expected_hidden_dimension}, {expected_vocabulary_size}), got {output.dimensions}"
            )
        if output.ggml_type != GGML_TYPE_Q6_K:
            raise GGUFError(f"output.weight must be Q6_K ({GGML_TYPE_Q6_K}), got {output.ggml_type}")
        if output_norm.dimensions != (expected_hidden_dimension,):
            raise GGUFError(
                f"output_norm.weight dimensions must be ({expected_hidden_dimension},), got {output_norm.dimensions}"
            )
        if output_norm.ggml_type != GGML_TYPE_F32:
            raise GGUFError(f"output_norm.weight must be F32 ({GGML_TYPE_F32}), got {output_norm.ggml_type}")
        _validate_tensor_extent(self._layout, output)
        _validate_tensor_extent(self._layout, output_norm)
        if expected_hidden_dimension % Q6_K_BLOCK_VALUES:
            raise GGUFError("output hidden dimension must be a multiple of 256 for Q6_K rows")
        self._output = output
        self._output_norm = output_norm
        self._row_bytes = expected_hidden_dimension // Q6_K_BLOCK_VALUES * Q6_K_BLOCK_BYTES

        try:
            self._file = self._model_path.open("rb")
            self._norm = self._read_output_norm()
            self._dequantize_row = dequantize_row or self._load_q6_k_dequantizer(dll_path)
        except Exception:
            self.close()
            raise

    @property
    def metadata(self) -> dict[str, Any]:
        return dict(self._layout.metadata)

    @property
    def architecture(self) -> str:
        return self._architecture

    @property
    def rms_epsilon(self) -> float:
        return self._rms_epsilon

    @property
    def hidden_dimension(self) -> int:
        return self._expected_hidden_dimension

    @property
    def vocabulary_size(self) -> int:
        return self._expected_vocabulary_size

    @property
    def output_norm(self) -> np.ndarray:
        self._ensure_open()
        return self._norm.copy()

    @property
    def tensor_descriptors(self) -> dict[str, GGUFTensorDescriptor]:
        return dict(self._layout.tensors)

    def _ensure_open(self) -> None:
        if self._closed:
            raise GGUFError("field language head is closed")

    def _read_at(self, offset: int, count: int, label: str) -> bytes:
        self._ensure_open()
        if self._file is None:
            raise GGUFError("GGUF file handle is unavailable")
        self._file.seek(offset)
        data = self._file.read(count)
        if len(data) != count:
            raise GGUFError(f"{label}: short read (wanted {count}, got {len(data)})")
        return data

    def _read_output_norm(self) -> np.ndarray:
        raw = self._read_at(
            self._layout.data_start + self._output_norm.offset,
            self._expected_hidden_dimension * 4,
            "output_norm.weight",
        )
        values = np.frombuffer(raw, dtype="<f4").astype(np.float32, copy=True)
        return _finite_vector(values, self._expected_hidden_dimension, "output_norm.weight")

    def _load_q6_k_dequantizer(
        self, dll_path: str | os.PathLike[str] | None
    ) -> Callable[[Any, Any, int], None]:
        if os.name != "nt":
            raise GGUFError("ggml-base.dll Q6_K dequantization requires Windows")
        path = (Path(dll_path) if dll_path is not None else self._model_path.with_name("ggml-base.dll")).resolve()
        if not path.is_file():
            raise GGUFError(f"ggml-base.dll is missing: {path}")
        add_dll_directory = getattr(os, "add_dll_directory", None)
        if add_dll_directory is not None:
            self._dll_directory_cookie = add_dll_directory(str(path.parent))
        try:
            self._dll = ct.WinDLL(str(path))
            function = getattr(self._dll, "dequantize_row_q6_K")
        except (AttributeError, OSError) as error:
            raise GGUFError(f"could not resolve dequantize_row_q6_K from {path}") from error
        function.argtypes = [ct.c_void_p, ct.POINTER(ct.c_float), ct.c_int64]
        function.restype = None
        return function

    def _rms_normalize(self, field_vector: Any) -> np.ndarray:
        vector = _finite_vector(field_vector, self._expected_hidden_dimension, "field vector")
        squares = np.multiply(vector, vector, dtype=np.float32)
        mean_square = np.asarray(np.sum(squares, dtype=np.float32) / self._expected_hidden_dimension, dtype=np.float32)
        rms_inverse = np.asarray(1.0 / math.sqrt(float(mean_square) + self._rms_epsilon), dtype=np.float32)
        normalized = np.multiply(vector, rms_inverse, dtype=np.float32)
        normalized = np.multiply(normalized, self._norm, dtype=np.float32)
        if not np.isfinite(normalized).all():
            raise GGUFError("RMS-normalized field vector contains non-finite values")
        return np.ascontiguousarray(normalized)

    def output_features(self, field_vector: Any) -> np.ndarray:
        """Apply Qwen's frozen output RMS norm and return 5,120 output features."""

        self._ensure_open()
        return self._rms_normalize(field_vector)

    def _dequantize_range(self, start: int, rows: int) -> np.ndarray:
        if self._dequantize_row is None:
            raise GGUFError("Q6_K dequantizer is unavailable")
        if start < 0 or rows <= 0 or start + rows > self._expected_vocabulary_size:
            raise GGUFError(f"invalid output.weight row range ({start}, {rows})")
        raw = self._read_at(
            self._layout.data_start + self._output.offset + start * self._row_bytes,
            rows * self._row_bytes,
            "output.weight chunk",
        )
        source = (ct.c_ubyte * len(raw)).from_buffer_copy(raw)
        dequantized = np.empty((rows, self._expected_hidden_dimension), dtype=np.float32)
        destination = dequantized.ctypes.data_as(ct.POINTER(ct.c_float))
        try:
            self._dequantize_row(
                ct.cast(source, ct.c_void_p),
                destination,
                rows * self._expected_hidden_dimension,
            )
        except Exception as error:
            raise GGUFError(f"Q6_K dequantization failed at vocabulary row {start}") from error
        if not np.isfinite(dequantized).all():
            raise GGUFError(f"output.weight chunk at row {start} is non-finite")
        return np.ascontiguousarray(dequantized)

    def _candidate_ids(self, token_ids: Sequence[int]) -> np.ndarray:
        try:
            ids = np.asarray(token_ids)
        except Exception as error:
            raise GGUFError("token_ids must be a nonempty one-dimensional integer sequence") from error
        if ids.ndim != 1 or ids.size == 0:
            raise GGUFError("token_ids must be a nonempty one-dimensional integer sequence")
        values = ids.tolist()
        if ids.dtype.kind == "b" or any(isinstance(value, bool) or not isinstance(value, Integral) for value in values):
            raise GGUFError("token_ids must contain only integer IDs")
        if any(int(value) < 0 or int(value) >= self._expected_vocabulary_size for value in values):
            raise GGUFError("token_ids contains an out-of-range vocabulary ID")
        return np.ascontiguousarray(np.asarray(values, dtype=np.int64))

    def candidate_rows(self, token_ids: Sequence[int]) -> np.ndarray:
        """Return frozen dequantized output rows for a bounded candidate set."""

        self._ensure_open()
        if not self.enabled:
            raise GGUFError("field language head is disabled (construct with enabled=True)")
        ids = self._candidate_ids(token_ids)
        unique = np.unique(ids)
        rows_by_id: dict[int, np.ndarray] = {}
        range_start = int(unique[0])
        previous = range_start
        for value in unique[1:]:
            current = int(value)
            if current != previous + 1:
                decoded = self._dequantize_range(range_start, previous - range_start + 1)
                for row_id, row in zip(range(range_start, previous + 1), decoded):
                    rows_by_id[row_id] = row
                range_start = current
            previous = current
        decoded = self._dequantize_range(range_start, previous - range_start + 1)
        for row_id, row in zip(range(range_start, previous + 1), decoded):
            rows_by_id[row_id] = row
        result = np.asarray([rows_by_id[int(value)] for value in ids], dtype=np.float32)
        return np.ascontiguousarray(result)

    def candidate_logits_from_output_features(
        self, output_features: Any, token_ids: Sequence[int]
    ) -> np.ndarray:
        """Score normalized output features against bounded candidate rows."""

        self._ensure_open()
        if not self.enabled:
            raise GGUFError("field language head is disabled (construct with enabled=True)")
        features = _finite_vector(output_features, self._expected_hidden_dimension, "output features")
        rows = self.candidate_rows(token_ids)
        logits = np.asarray(np.matmul(rows, features), dtype=np.float32)
        if logits.shape != (rows.shape[0],) or not np.isfinite(logits).all():
            raise GGUFError("candidate logits have invalid shape or non-finite values")
        return np.ascontiguousarray(logits)

    def candidate_logits(self, field_vector: Any, token_ids: Sequence[int]) -> np.ndarray:
        """Return bounded candidate logits after the output RMS norm."""

        return self.candidate_logits_from_output_features(self.output_features(field_vector), token_ids)

    def _logits_from_features(self, output_features: Any) -> np.ndarray:
        self._ensure_open()
        if not self.enabled:
            raise GGUFError("field language head is disabled (construct with enabled=True)")
        features = _finite_vector(output_features, self._expected_hidden_dimension, "output features")
        logits = np.empty(self._expected_vocabulary_size, dtype=np.float32)
        for start in range(0, self._expected_vocabulary_size, self.chunk_tokens):
            rows = min(self.chunk_tokens, self._expected_vocabulary_size - start)
            dequantized = self._dequantize_range(start, rows)
            logits[start : start + rows] = np.asarray(
                np.matmul(dequantized, features), dtype=np.float32
            )
        if logits.shape != (self._expected_vocabulary_size,) or not np.isfinite(logits).all():
            raise GGUFError("field-language logits have invalid shape or non-finite values")
        return logits

    def logits_from_output_features(self, output_features: Any) -> np.ndarray:
        """Apply frozen Qwen ``output.weight`` to already-normalized features."""

        return self._logits_from_features(output_features)

    def logits(self, field_vector: Any) -> np.ndarray:
        """Return frozen field-language logits after the Qwen output RMS norm."""

        return self._logits_from_features(self.output_features(field_vector))

    def close(self, *, unload_dll: bool = True) -> None:
        """Close the GGUF file and optionally release the native DLL handle."""
        if self._closed:
            return
        self._closed = True
        if self._file is not None:
            self._file.close()
            self._file = None
        self._dequantize_row = None
        if unload_dll and self._dll is not None:
            handle = int(getattr(self._dll, "_handle", 0) or 0)
            if handle and sys.platform == "win32":
                try:
                    import _ctypes

                    _ctypes.FreeLibrary(handle)
                    self._dll._handle = 0
                except (AttributeError, OSError):
                    pass
            self._dll = None
        if self._dll_directory_cookie is not None:
            self._dll_directory_cookie.close()
            self._dll_directory_cookie = None

    def __enter__(self) -> "FieldLanguageHead":
        self._ensure_open()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


__all__ = [
    "DEFAULT_CHUNK_TOKENS",
    "FieldLanguageHead",
    "GGML_TYPE_F32",
    "GGML_TYPE_Q6_K",
    "GGUFError",
    "GGUFLayout",
    "GGUFTensorDescriptor",
    "parse_gguf",
]
