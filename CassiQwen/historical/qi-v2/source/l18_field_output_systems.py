"""Pure NumPy systems for the experimental L18 field-output loop.

This module intentionally contains no llama.cpp, ctypes, Godot, network, or model
loading code.  It is the deterministic data seam used by the L18 integration:
canonical 5,120-dimensional Fourier directions are represented by the N=32
x-fastest two-fluid field, decoded states can be retained/retrieved, frozen
ordinary/field logits can be ranked, and token plans/events can be written.

The canonical mode allocation mirrors ``cassi-embedding-field-codec.mjs``:
all non-self-conjugate modes are sorted by ``(k2, kz, ky, kx, flat_index)`` and
then one member of each conjugate pair is retained.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


PROTOCOL = "CassiQwen L18 field-output loop"
VERSION = 1
GRID_N = 32
VOLUME_SIZE = GRID_N**3
DIMENSION = 5120
MODE_COUNT = DIMENSION // 2
PHI = 1.618033988749895
AMPLITUDE = 1.0
DTYPE = "float32-le"
LAYOUT = "x + N*(y + N*z)"


class L18Error(ValueError):
    """Raised when an L18 shape, finite-value, or configuration contract fails."""


@dataclass(frozen=True)
class FourierMode:
    """One positive member and its conjugate partner in the flattened field."""

    x: int
    y: int
    z: int
    kx: int
    ky: int
    kz: int
    k2: int
    index: int
    negative_index: int


@dataclass(frozen=True)
class DirectionField:
    """A float32 split field carrying one normalized 5,120-D direction."""

    ey: np.ndarray
    ei: np.ndarray
    signal: np.ndarray
    direction: np.ndarray
    input_l2_norm: float
    modes: tuple[FourierMode, ...]
    grid_n: int = GRID_N
    dimension: int = DIMENSION
    phi: float = PHI
    amplitude: float = AMPLITUDE
    dtype: str = DTYPE
    layout: str = LAYOUT

    def __post_init__(self) -> None:
        _validate_field(self.ey, "EY")
        _validate_field(self.ei, "EI")
        _validate_field(self.signal, "signed field")
        _validate_vector(self.direction, "direction", DIMENSION)
        _require_positive_finite(self.input_l2_norm, "input_l2_norm")
        if len(self.modes) != MODE_COUNT:
            raise L18Error(f"direction field requires {MODE_COUNT} modes")

    def raw_metadata(self) -> dict[str, Any]:
        """Return JSON-ready raw metadata for both field channels and the signal."""
        return field_raw_metadata(self.ey, self.ei, signal=self.signal)


@dataclass(frozen=True)
class FieldMemoryRecord:
    """One decoded field state retained for later cosine retrieval."""

    record_id: str
    token_index: int
    vector: np.ndarray
    token_id: int | None = None
    piece: str | None = None
    source: str = "token"

    def __post_init__(self) -> None:
        if not self.record_id:
            raise L18Error("memory record_id must be non-empty")
        if not isinstance(self.token_index, int) or isinstance(self.token_index, bool):
            raise L18Error("memory token_index must be an integer")
        _validate_vector(self.vector, "memory vector", DIMENSION)

    def to_dict(self, *, include_vector: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "record_id": self.record_id,
            "token_index": self.token_index,
            "token_id": self.token_id,
            "piece": self.piece,
            "source": self.source,
        }
        if include_vector:
            result["vector"] = self.vector.copy()
        return result


@dataclass(frozen=True)
class MemoryMatch:
    """A retrieved record and its cosine score."""

    record_id: str
    token_index: int
    score: float
    token_id: int | None
    piece: str | None
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "token_index": self.token_index,
            "score": self.score,
            "token_id": self.token_id,
            "piece": self.piece,
            "source": self.source,
        }


# ---------------------------------------------------------------------------
# Strict numeric and raw-byte helpers


def _as_float32(values: Any, label: str, *, shape: tuple[int, ...] | None = None) -> np.ndarray:
    array = np.asarray(values)
    if shape is not None and tuple(array.shape) != shape:
        raise L18Error(f"{label} must have shape {shape}, got {tuple(array.shape)}")
    if not np.issubdtype(array.dtype, np.number):
        raise L18Error(f"{label} must be numeric")
    result = np.asarray(array, dtype=np.float32)
    if not np.isfinite(result).all():
        raise L18Error(f"{label} contains non-finite values")
    if not np.isfinite(np.asarray(array, dtype=np.float64)).all():
        raise L18Error(f"{label} is outside finite float32 conversion")
    return np.ascontiguousarray(result)


def _validate_vector(values: Any, label: str, dimension: int = DIMENSION) -> np.ndarray:
    result = _as_float32(values, label, shape=(dimension,))
    # Keep zero vectors legal for memory/cosine diagnostics; direction encoding
    # itself rejects them because normalization is undefined.
    return result


def _validate_field(values: Any, label: str, grid_n: int = GRID_N) -> np.ndarray:
    return _as_float32(values, label, shape=(grid_n**3,))


def _require_positive_finite(value: float, label: str) -> float:
    if not isinstance(value, (int, float, np.integer, np.floating)) or not math.isfinite(float(value)):
        raise L18Error(f"{label} must be finite")
    value = float(value)
    if value <= 0.0:
        raise L18Error(f"{label} must be positive")
    return value


def float32_bytes(values: Any, *, shape: tuple[int, ...] | None = None, label: str = "float32 values") -> bytes:
    """Return finite values as canonical little-endian float32 C-order bytes."""
    array = _as_float32(values, label, shape=shape)
    return array.astype("<f4", copy=False).tobytes(order="C")


def float32_base64(values: Any, *, shape: tuple[int, ...] | None = None, label: str = "float32 values") -> str:
    """Encode canonical little-endian float32 bytes as padded base64."""
    return base64.b64encode(float32_bytes(values, shape=shape, label=label)).decode("ascii")


def base64_float32(text: str, *, expected_shape: tuple[int, ...] | None = None, label: str = "base64 float32") -> np.ndarray:
    """Decode canonical padded base64 into finite little-endian float32 values."""
    if not isinstance(text, str) or len(text) % 4 != 0:
        raise L18Error(f"{label} must be padded base64 text")
    try:
        raw = base64.b64decode(text.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as error:
        raise L18Error(f"{label} is not canonical base64") from error
    if base64.b64encode(raw).decode("ascii") != text:
        raise L18Error(f"{label} is not canonical padded base64")
    if len(raw) % 4:
        raise L18Error(f"{label} byte length is not a multiple of four")
    values = np.frombuffer(raw, dtype="<f4").copy()
    if expected_shape is not None:
        expected_size = math.prod(expected_shape)
        if values.size != expected_size:
            raise L18Error(f"{label} has {values.size} values; expected {expected_size}")
        values = values.reshape(expected_shape)
    if not np.isfinite(values).all():
        raise L18Error(f"{label} contains non-finite values")
    return np.ascontiguousarray(values)


def sha256_bytes(data: bytes) -> str:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise L18Error("sha256_bytes requires a bytes-like value")
    return hashlib.sha256(bytes(data)).hexdigest()


def sha256_float32(values: Any, *, shape: tuple[int, ...] | None = None, label: str = "float32 values") -> str:
    return sha256_bytes(float32_bytes(values, shape=shape, label=label))


def field_raw_metadata(ey: Any, ei: Any, *, signal: Any | None = None) -> dict[str, Any]:
    """Describe raw EY/EI bytes with shape/layout and stable hashes."""
    ey_array = _validate_field(ey, "EY field")
    ei_array = _validate_field(ei, "EI field")
    ey_raw = float32_bytes(ey_array, label="EY field")
    ei_raw = float32_bytes(ei_array, label="EI field")
    result: dict[str, Any] = {
        "dtype": DTYPE,
        "shape": [GRID_N**3],
        "layout": LAYOUT,
        "grid_n": GRID_N,
        "ey_b64": base64.b64encode(ey_raw).decode("ascii"),
        "ei_b64": base64.b64encode(ei_raw).decode("ascii"),
        "ey_sha256": sha256_bytes(ey_raw),
        "ei_sha256": sha256_bytes(ei_raw),
        "combined_shape": [2, GRID_N**3],
        "combined_layout": "[EY, EI] channels; x + N*(y + N*z) within each channel",
        "combined_sha256": sha256_bytes(ey_raw + ei_raw),
    }
    if signal is not None:
        signal_array = _validate_field(signal, "signed field")
        signal_raw = float32_bytes(signal_array, label="signed field")
        result.update(
            signal_b64=base64.b64encode(signal_raw).decode("ascii"),
            signal_sha256=sha256_bytes(signal_raw),
        )
    return result


# ---------------------------------------------------------------------------
# Canonical Fourier direction codec


def _wrapped_wave_number(index: int, grid_n: int) -> int:
    return index - grid_n if index > grid_n // 2 else index


def _flat_index(x: int, y: int, z: int, grid_n: int) -> int:
    return x + grid_n * (y + grid_n * z)


def _canonical_modes(grid_n: int = GRID_N) -> tuple[FourierMode, ...]:
    if grid_n != GRID_N:
        raise L18Error(f"L18 freezes grid_n={GRID_N}")
    candidates: list[FourierMode] = []
    for z in range(grid_n):
        for y in range(grid_n):
            for x in range(grid_n):
                index = _flat_index(x, y, z, grid_n)
                negative_index = _flat_index((0 if x == 0 else grid_n - x), (0 if y == 0 else grid_n - y), (0 if z == 0 else grid_n - z), grid_n)
                if index == negative_index:
                    continue
                kx = _wrapped_wave_number(x, grid_n)
                ky = _wrapped_wave_number(y, grid_n)
                kz = _wrapped_wave_number(z, grid_n)
                candidates.append(FourierMode(x, y, z, kx, ky, kz, kx * kx + ky * ky + kz * kz, index, negative_index))
    candidates.sort(key=lambda mode: (mode.k2, mode.kz, mode.ky, mode.kx, mode.index))
    seen = np.zeros(grid_n**3, dtype=np.uint8)
    selected: list[FourierMode] = []
    for mode in candidates:
        if seen[mode.index] != 0:
            continue
        seen[mode.index] = 1
        seen[mode.negative_index] = 1
        selected.append(mode)
    if len(selected) < MODE_COUNT:
        raise L18Error(f"grid has only {len(selected)} canonical conjugate pairs")
    return tuple(selected[:MODE_COUNT])


_CANONICAL_MODES = _canonical_modes()


def canonical_modes() -> tuple[FourierMode, ...]:
    """Return the exact frozen 2,560-mode canonical allocation."""
    return _CANONICAL_MODES


def _validate_direction(direction: Any) -> tuple[np.ndarray, float, np.ndarray]:
    source = np.asarray(direction)
    if tuple(source.shape) != (DIMENSION,):
        raise L18Error(f"direction must have shape ({DIMENSION},), got {tuple(source.shape)}")
    if not np.issubdtype(source.dtype, np.number):
        raise L18Error("direction must be numeric")
    source64 = np.asarray(source, dtype=np.float64)
    if not np.isfinite(source64).all():
        raise L18Error("direction contains non-finite values")
    norm = float(np.linalg.norm(source64))
    if not math.isfinite(norm) or norm <= 0.0:
        raise L18Error("direction must have a finite positive L2 norm")
    normalized = np.asarray(source64 / norm, dtype=np.float64)
    return source.astype(np.float32, copy=True), norm, normalized


def _split_signal(signal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    signal32 = _as_float32(signal, "signed field", shape=(VOLUME_SIZE,))
    ey = np.where(signal32 > 0.0, signal32, 0.0).astype(np.float32)
    # JavaScript divides the float32 value in Number (float64) precision and
    # rounds when assigning EI to Float32Array; retain that boundary here.
    ei64 = np.where(signal32 < 0.0, -signal32.astype(np.float64) / PHI, 0.0)
    ei = ei64.astype(np.float32)
    return np.ascontiguousarray(ey), np.ascontiguousarray(ei)


def _join_signal(ey: Any, ei: Any) -> np.ndarray:
    ey32 = _validate_field(ey, "EY field")
    ei32 = _validate_field(ei, "EI field")
    # Compute in float64 like the JS codec, then round only at the FFT input's
    # split-field boundary (the decoded field is allowed to retain that error).
    return np.asarray(ey32.astype(np.float64) - PHI * ei32.astype(np.float64), dtype=np.float64)


def encode_direction_field(direction: Any, *, amplitude: float = AMPLITUDE) -> DirectionField:
    """Fourier-lift one exact 5,120-D direction into split EY/EI float32 fields."""
    amplitude = _require_positive_finite(amplitude, "amplitude")
    _original, norm, normalized = _validate_direction(direction)
    spectrum = np.zeros((GRID_N, GRID_N, GRID_N), dtype=np.complex128)
    scale = amplitude * math.sqrt(VOLUME_SIZE / 2.0)
    for pair, mode in enumerate(_CANONICAL_MODES):
        a = normalized[2 * pair]
        b = normalized[2 * pair + 1]
        spectrum[mode.z, mode.y, mode.x] = scale * (a - 1j * b)
        spectrum[(0 if mode.z == 0 else GRID_N - mode.z), (0 if mode.y == 0 else GRID_N - mode.y), (0 if mode.x == 0 else GRID_N - mode.x)] = scale * (a + 1j * b)
    # numpy's inverse transform is normalized by volume, matching the JS FFT.
    signal = np.fft.ifftn(spectrum).real.reshape(-1).astype(np.float32)
    ey, ei = _split_signal(signal)
    return DirectionField(
        ey=ey,
        ei=ei,
        signal=np.ascontiguousarray(signal),
        direction=np.asarray(normalized, dtype=np.float32),
        input_l2_norm=norm,
        modes=_CANONICAL_MODES,
        amplitude=amplitude,
    )


def decode_direction_field(ey: Any, ei: Any, *, amplitude: float = AMPLITUDE) -> np.ndarray:
    """Decode split EY/EI fields to the normalized 5,120-D direction."""
    amplitude = _require_positive_finite(amplitude, "amplitude")
    epsilon = _join_signal(ey, ei).reshape((GRID_N, GRID_N, GRID_N))
    spectrum = np.fft.fftn(epsilon)
    scale = amplitude * math.sqrt(VOLUME_SIZE / 2.0)
    decoded = np.empty(DIMENSION, dtype=np.float64)
    for pair, mode in enumerate(_CANONICAL_MODES):
        coefficient = spectrum[mode.z, mode.y, mode.x]
        decoded[2 * pair] = coefficient.real / scale
        decoded[2 * pair + 1] = -coefficient.imag / scale
    if not np.isfinite(decoded).all():
        raise L18Error("decoded direction contains non-finite values")
    return np.ascontiguousarray(decoded.astype(np.float32))


def decode_direction_field_with_norm(ey: Any, ei: Any, input_l2_norm: float, *, amplitude: float = AMPLITUDE) -> np.ndarray:
    """Decode and restore the separately carried source L2 norm."""
    norm = _require_positive_finite(input_l2_norm, "input_l2_norm")
    return np.asarray(decode_direction_field(ey, ei, amplitude=amplitude) * np.float32(norm), dtype=np.float32)


# Friendly aliases used by integration code.
encode_direction = encode_direction_field
decode_direction = decode_direction_field
encode_field = encode_direction_field
decode_field = decode_direction_field
float32_to_base64 = float32_base64
base64_to_float32 = base64_float32


# ---------------------------------------------------------------------------
# Persistent decoded-field memory and cosine retrieval


class DecodedFieldMemory:
    """Persistent token-state memory with deterministic cosine retrieval."""

    def __init__(self, *, dimension: int = DIMENSION) -> None:
        if dimension != DIMENSION:
            raise L18Error(f"L18 freezes memory dimension={DIMENSION}")
        self.dimension = dimension
        self._records: list[FieldMemoryRecord] = []
        self._next_id = 0

    @property
    def records(self) -> tuple[FieldMemoryRecord, ...]:
        return tuple(self._records)

    def add(
        self,
        vector: Any,
        *,
        token_index: int,
        token_id: int | None = None,
        piece: str | None = None,
        record_id: str | None = None,
        source: str = "token",
    ) -> FieldMemoryRecord:
        if not isinstance(token_index, int) or isinstance(token_index, bool) or token_index < 0:
            raise L18Error("token_index must be a non-negative integer")
        if token_id is not None and (not isinstance(token_id, int) or isinstance(token_id, bool)):
            raise L18Error("token_id must be an integer or None")
        if piece is not None and not isinstance(piece, str):
            raise L18Error("piece must be a string or None")
        if not isinstance(source, str) or not source:
            raise L18Error("memory source must be non-empty text")
        vector32 = _validate_vector(vector, "decoded field vector", self.dimension)
        chosen_id = record_id if record_id is not None else f"token-{token_index}-{self._next_id}"
        if not isinstance(chosen_id, str) or not chosen_id:
            raise L18Error("record_id must be non-empty text")
        if any(existing.record_id == chosen_id for existing in self._records):
            raise L18Error(f"duplicate memory record_id: {chosen_id}")
        record = FieldMemoryRecord(chosen_id, token_index, vector32.copy(), token_id, piece, source)
        self._records.append(record)
        self._next_id += 1
        return record

    @staticmethod
    def _external_record(value: Any, index: int, dimension: int) -> FieldMemoryRecord:
        if isinstance(value, FieldMemoryRecord):
            return value
        if isinstance(value, Mapping):
            vector = None
            for key in ("vector", "decoded", "decoded_vector", "field_vector"):
                if key in value:
                    vector = value[key]
                    break
            if vector is None:
                raise L18Error(f"external memory record {index} has no decoded vector")
            record_id = str(value.get("record_id", value.get("id", f"external-{index}")))
            token_index = value.get("token_index", value.get("index", index))
            token_id = value.get("token_id")
            piece = value.get("piece")
            source = str(value.get("source", "external"))
            return FieldMemoryRecord(record_id, int(token_index), _validate_vector(vector, "external decoded vector", dimension), token_id, piece, source)
        return FieldMemoryRecord(f"external-{index}", index, _validate_vector(value, "external decoded vector", dimension), source="external")

    def retrieve(
        self,
        query: Any,
        *,
        top_k: int = 4,
        before_token_index: int | None = None,
        external_records: Iterable[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve earlier internal states plus optional external records.

        Ties are stable by score descending, then source (internal before
        external), token index ascending, record id, and insertion order.
        """
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 0:
            raise L18Error("top_k must be a non-negative integer")
        query32 = _validate_vector(query, "memory query", self.dimension)
        if before_token_index is not None and (not isinstance(before_token_index, int) or isinstance(before_token_index, bool) or before_token_index < 0):
            raise L18Error("before_token_index must be a non-negative integer or None")
        candidates: list[tuple[int, FieldMemoryRecord]] = []
        for insertion, record in enumerate(self._records):
            if before_token_index is not None and record.token_index >= before_token_index:
                continue
            candidates.append((insertion, record))
        if external_records is not None:
            for index, value in enumerate(external_records):
                record = self._external_record(value, index, self.dimension)
                candidates.append((len(self._records) + index, record))
        query64 = query32.astype(np.float64, copy=False)
        query_norm = float(np.linalg.norm(query64))
        matches: list[tuple[tuple[Any, ...], MemoryMatch]] = []
        for insertion, record in candidates:
            vector64 = record.vector.astype(np.float64, copy=False)
            denominator = query_norm * float(np.linalg.norm(vector64))
            score = 0.0 if denominator == 0.0 else float(np.dot(query64, vector64) / denominator)
            source_order = 0 if record.source == "token" else 1
            match = MemoryMatch(record.record_id, record.token_index, score, record.token_id, record.piece, record.source)
            matches.append(((-score, source_order, record.token_index, record.record_id, insertion), match))
        matches.sort(key=lambda item: item[0])
        return [match.to_dict() for _, match in matches[:top_k]]

    def clear(self) -> None:
        self._records.clear()
        self._next_id = 0


# ---------------------------------------------------------------------------
# Frozen output candidate ranking and token-level planning


def _validate_logits(values: Any, label: str) -> np.ndarray:
    array = np.asarray(values)
    if array.ndim != 1 or array.size == 0:
        raise L18Error(f"{label} must be a non-empty one-dimensional array")
    if not np.issubdtype(array.dtype, np.number):
        raise L18Error(f"{label} must be numeric")
    result = np.asarray(array, dtype=np.float64)
    if not np.isfinite(result).all():
        raise L18Error(f"{label} contains non-finite values")
    return result


def select_field_language_candidates(
    ordinary_logits: Any,
    field_logits: Any,
    *,
    gamma: float = 0.15,
    top_k: int = 16,
    enabled: bool = False,
    token_ids: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Blend frozen ordinary/field logits and return deterministic ranked rows.

    ``enabled`` is deliberately false by default at this public boundary.  In
    that mode the result is ordinary greedy ranking even if a non-zero gamma is
    supplied; callers must explicitly enable the experimental field seam.
    """
    ordinary = _validate_logits(ordinary_logits, "ordinary logits")
    field_logits_array = _validate_logits(field_logits, "field logits")
    if not isinstance(enabled, (bool, np.bool_)):
        raise L18Error("enabled must be boolean")
    if ordinary.shape != field_logits_array.shape:
        raise L18Error(f"ordinary and field logits shapes differ: {ordinary.shape} vs {field_logits_array.shape}")
    if not isinstance(gamma, (int, float, np.integer, np.floating)) or not math.isfinite(float(gamma)):
        raise L18Error("gamma must be finite")
    gamma_value = float(gamma)
    if not 0.0 <= gamma_value <= 1.0:
        raise L18Error("gamma must be in [0, 1]")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
        raise L18Error("top_k must be a positive integer")
    if token_ids is None:
        ids = np.arange(ordinary.size, dtype=np.int64)
    else:
        if len(token_ids) != ordinary.size:
            raise L18Error("token_ids length must equal logits length")
        if any(not isinstance(value, (int, np.integer)) or isinstance(value, bool) for value in token_ids):
            raise L18Error("token_ids must contain integers")
        ids = np.asarray(token_ids, dtype=np.int64)
        if np.unique(ids).size != ids.size:
            raise L18Error("token_ids must be unique")
    applied_gamma = gamma_value if enabled else 0.0
    blended = (1.0 - applied_gamma) * ordinary + applied_gamma * field_logits_array
    order = np.lexsort((ids, -blended))[: min(top_k, blended.size)]
    candidates: list[dict[str, Any]] = []
    for rank, index in enumerate(order, start=1):
        candidates.append(
            {
                "rank": rank,
                "token_id": int(ids[index]),
                "score": float(blended[index]),
                "ordinary_score": float(ordinary[index]),
                "field_score": float(field_logits_array[index]),
            }
        )
    return {
        "enabled": bool(enabled),
        "gamma": applied_gamma,
        "requested_gamma": gamma_value,
        "top_k": candidates,
        "candidates": candidates,
        "token_ids": [row["token_id"] for row in candidates],
        "scores": [row["score"] for row in candidates],
        "finite": True,
    }


class TokenLevelPlanner:
    """Record one token decision without exposing any external action interface."""

    def __init__(
        self,
        memory: DecodedFieldMemory | None = None,
        *,
        gamma: float = 0.15,
        top_k: int = 16,
        retrieval_k: int = 4,
        enabled: bool = False,
    ) -> None:
        if not isinstance(retrieval_k, int) or isinstance(retrieval_k, bool) or retrieval_k < 0:
            raise L18Error("retrieval_k must be a non-negative integer")
        self.memory = memory if memory is not None else DecodedFieldMemory()
        self.gamma = gamma
        self.top_k = top_k
        self.retrieval_k = retrieval_k
        if not isinstance(enabled, (bool, np.bool_)):
            raise L18Error("enabled must be boolean")
        self.enabled = bool(enabled)

    def plan(
        self,
        token_index: int,
        ordinary_logits: Any,
        field_logits: Any,
        *,
        decoded_vector: Any | None = None,
        token_ids: Sequence[int] | None = None,
        selected_token_id: int | None = None,
        selected_piece: str | None = None,
        position: int | None = None,
        external_records: Iterable[Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(token_index, int) or isinstance(token_index, bool) or token_index < 0:
            raise L18Error("token_index must be a non-negative integer")
        if position is not None and (not isinstance(position, int) or isinstance(position, bool) or position < 0):
            raise L18Error("position must be a non-negative integer or None")
        selection = select_field_language_candidates(
            ordinary_logits,
            field_logits,
            gamma=self.gamma,
            top_k=self.top_k,
            enabled=self.enabled,
            token_ids=token_ids,
        )
        query = None if decoded_vector is None else _validate_vector(decoded_vector, "decoded field vector", DIMENSION)
        retrieved = [] if query is None else self.memory.retrieve(query, top_k=self.retrieval_k, before_token_index=token_index, external_records=external_records)
        if selected_token_id is None:
            if not selection["top_k"]:
                raise L18Error("candidate selection returned no token")
            selected = selection["top_k"][0]
            selected_token_id = int(selected["token_id"])
            selected_score = float(selected["score"])
        else:
            if not isinstance(selected_token_id, (int, np.integer)) or isinstance(selected_token_id, bool):
                raise L18Error("selected_token_id must be an integer")
            selected_token_id = int(selected_token_id)
            selected_score = None
            for candidate in selection["top_k"]:
                if candidate["token_id"] == selected_token_id:
                    selected_score = candidate["score"]
                    break
            if selected_score is None:
                ids = np.asarray(token_ids if token_ids is not None else np.arange(_validate_logits(ordinary_logits, "ordinary logits").size))
                index = int(np.where(ids == selected_token_id)[0][0]) if np.any(ids == selected_token_id) else -1
                if index < 0:
                    raise L18Error("selected_token_id is absent from logits")
                selected_score = float((1.0 - selection["gamma"]) * np.asarray(ordinary_logits, dtype=np.float64)[index] + selection["gamma"] * np.asarray(field_logits, dtype=np.float64)[index])
        if selected_piece is not None and not isinstance(selected_piece, str):
            raise L18Error("selected_piece must be text or None")
        if query is not None:
            self.memory.add(query, token_index=token_index, token_id=selected_token_id, piece=selected_piece)
        return {
            "token_index": token_index,
            "position": position,
            "field_enabled": self.enabled,
            "ranked_candidates": selection["top_k"],
            "candidates": selection["top_k"],
            "retrieved_memory": retrieved,
            "memory": retrieved,
            "selected_token_id": selected_token_id,
            "selected_piece": selected_piece,
            "selected_score": selected_score,
            "external_actions": [],
            "actions": [],
            "finite": True,
        }


# ---------------------------------------------------------------------------
# JSONL live-event and receipt persistence


def _json_default(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        if not np.isfinite(value).all():
            raise ValueError("JSON event contains non-finite ndarray values")
        return value.tolist()
    if isinstance(value, np.generic):
        scalar = value.item()
        if isinstance(scalar, float) and not math.isfinite(scalar):
            raise ValueError("JSON event contains non-finite scalar")
        return scalar
    if isinstance(value, (Path,)):
        return str(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    raise TypeError(f"object of type {type(value).__name__} is not JSON serializable")


def _json_line(value: Mapping[str, Any]) -> str:
    if not isinstance(value, Mapping):
        raise L18Error("JSONL event must be a mapping")
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False, default=_json_default)
    except (TypeError, ValueError) as error:
        raise L18Error(f"event is not finite JSON: {error}") from error


class JsonlEventWriter:
    """Append live events and atomically write a final JSON receipt."""

    def __init__(self, path: str | os.PathLike[str], *, receipt_path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path)
        self.receipt_path = Path(receipt_path) if receipt_path is not None else self.path.with_suffix(".receipt.json")
        self._event_count = 0

    def write_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        line = _json_line(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
            handle.write("\n")
            handle.flush()
        self._event_count += 1
        raw = (line + "\n").encode("utf-8")
        return {"event_index": self._event_count - 1, "bytes": len(raw), "sha256": sha256_bytes(raw), "path": str(self.path)}

    def write_receipt(self, receipt: Mapping[str, Any]) -> dict[str, Any]:
        line = _json_line(receipt)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{self.receipt_path.name}.", suffix=".tmp", dir=str(self.receipt_path.parent))
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.receipt_path)
        except BaseException:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            raise
        raw = (line + "\n").encode("utf-8")
        return {"bytes": len(raw), "sha256": sha256_bytes(raw), "event_count": self._event_count, "path": str(self.receipt_path)}


# Conventional function aliases for small integrations.
write_jsonl_event = JsonlEventWriter.write_event
write_json_receipt = JsonlEventWriter.write_receipt


__all__ = [
    "AMPLITUDE",
    "DIMENSION",
    "DTYPE",
    "DecodedFieldMemory",
    "DirectionField",
    "FieldMemoryRecord",
    "FourierMode",
    "GRID_N",
    "LAYOUT",
    "L18Error",
    "MODE_COUNT",
    "PHI",
    "PROTOCOL",
    "VERSION",
    "JsonlEventWriter",
    "TokenLevelPlanner",
    "base64_float32",
    "base64_to_float32",
    "canonical_modes",
    "decode_direction",
    "decode_direction_field",
    "decode_direction_field_with_norm",
    "decode_field",
    "encode_direction",
    "encode_direction_field",
    "encode_field",
    "field_raw_metadata",
    "float32_base64",
    "float32_bytes",
    "float32_to_base64",
    "sha256_bytes",
    "sha256_float32",
    "select_field_language_candidates",
]
