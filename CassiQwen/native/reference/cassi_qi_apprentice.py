"""Executable NumPy reference for the native Cassi apprenticeship field.

This module defines the fixed field geometry, bounded context dynamics, and
field-resident associative engram law used by the native implementation. It is
an offline reference and fixture writer, not a runtime service.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


PHI = 1.618033988749895
SCALE_COUNT = 4
BATCH_COUNT = 1
COMPONENT_COUNT = 9
PROFILE_ID = "cassi.qi.apprentice-engram.v1"
LAYOUT_ID = "cassi.qi.native-linear-scale-component-mode.v2"
CODEBOOK_ID = "cassi.qi.scale-prime-quadratic-chirp.v2"
SENSE_ID = "sense-ema-oscillator-v1"
ENGRAM_ID = "bounded-common-engram-v1"
AUDIT_ID = "compact-kernel-audit-v1"
TOKEN_ID = "token-u32le-four-byte-v1"
COMPONENTS = (
    "Y_re",
    "Y_im",
    "I_re",
    "I_im",
    "VY_re",
    "VY_im",
    "VI_re",
    "VI_im",
    "epsilon2_ema",
)
PRIMES = (4093, 4099, 4127, 4133)
COEFFICIENTS = (
    (1, 1, 1, 3),
    (3, 5, 7, 11),
    (5, 9, 11, 17),
    (7, 13, 17, 23),
)
PERMUTATIONS = ((1, 0), (5, 1), (7, 3), (11, 5))

TEXT = 0
EMBED = 1
HEAD = 2
ATTENTION = 3
FFN = 4
KIND_NAMES = {
    TEXT: "TEXT",
    EMBED: "EMBED",
    HEAD: "HEAD",
    ATTENTION: "ATTENTION",
    FFN: "FFN",
}

END = 256
SYSTEM = 257
USER = 258
ASSISTANT = 259
ALPHABET_SIZE = 260

DT = 0.005
SCALE_RATIO = PHI**3
SENSING_GAIN = 0.25
FAST_OMEGA2 = 20.0
SLOW_OMEGA2 = 0.05
FAST_DAMPING = 0.5
SLOW_DAMPING = 0.01
MODE_SLOPE = 0.25
NONLINEAR_GAIN = 0.002
MAX_AMPLITUDE = 4.0
MAX_MEAN_ENERGY = 8.0
EPSILON_TAU = 1.0 / PHI
EPSILON_CLIP = 64.0
TEXT_RADIUS = 0.001
VECTOR_RADIUS = 1.0 / 16.0
EXACT_DISTANCE2 = 1.0e-10
MERGE_DISTANCE2 = 1.0e-6
WEIGHT_FLOOR = 1.0e-6
SCATTER_CEILING = 1.0e-4
BYTE_GUIDE_GAIN = 0.5
VECTOR_GUIDE_GAIN = 1.0
NORM_GUARD = 1.0e-6
VECTOR_SUCCESS = 0.01
GUIDED_VECTOR_TOLERANCE = 1.0e-4
ERROR_EMA_GAIN = 0.1
THRESHOLD_ABS_GUARD = 1.0e-12
THRESHOLD_REL_GUARD = 0.001
OCCUPANCY_FLOOR = 1.0e-6
COUNT_LIMIT = 255
MERGE_WINDOW = 16
TOKEN_BYTE_COUNT = 4
GUIDE_ROUNDS = 8
MIN_OBSERVATIONS = 2
MIN_EXACT_SUCCESSES = 1
MIN_NOVEL_SUCCESSES = 2

META_OCCUPANCY = 0
META_TEACHER_OBSERVATIONS = 1
META_EXACT_SUCCESSES = 2
META_NOVEL_SUCCESSES = 3
META_ERROR_EMA = 4
META_AGE = 5
META_COUNT = 6

NEEDS_TEACHER = "needs_teacher"
FIELD_EXACT = "field_exact"
FIELD_INTERPOLATED = "field_interpolated"


class ApprenticeError(ValueError):
    """Invalid apprenticeship geometry, field state, or boundary value."""


@dataclass(frozen=True, slots=True)
class PageDescriptor:
    kind: int
    layer: int
    width: int
    mode_offset: int
    entries: int

    @property
    def active_offset(self) -> int:
        return self.mode_offset

    @property
    def entry_stride(self) -> int:
        return 3 * self.width + META_COUNT

    @property
    def memory_offset(self) -> int:
        return self.mode_offset + self.width

    @property
    def mode_count(self) -> int:
        return self.width + self.entries * self.entry_stride


@dataclass(frozen=True, slots=True)
class FieldGeometry:
    layers: int
    embedding_width: int
    vocabulary_size: int
    memory_bytes: int
    modes: int
    field_bytes: int
    pages: tuple[PageDescriptor, ...]

    @staticmethod
    def _service_width(embedding_width: int) -> int:
        minimum = max(260, (embedding_width + 1) // 2)
        width = 256 * ((minimum + 255) // 256)
        while any(math.gcd(width, multiplier) != 1 for multiplier, _ in PERMUTATIONS):
            width += 256
        return width

    @classmethod
    def build(
        cls,
        *,
        layers: int,
        embedding_width: int,
        vocabulary_size: int,
        memory_bytes: int,
    ) -> "FieldGeometry":
        if isinstance(layers, bool) or not isinstance(layers, int) or layers < 1:
            raise ApprenticeError("layers must be a positive integer")
        if isinstance(embedding_width, bool) or not isinstance(embedding_width, int) or embedding_width < 1:
            raise ApprenticeError("embedding_width must be a positive integer")
        if isinstance(vocabulary_size, bool) or not isinstance(vocabulary_size, int) or vocabulary_size < 1:
            raise ApprenticeError("vocabulary_size must be a positive integer")
        if isinstance(memory_bytes, bool) or not isinstance(memory_bytes, int) or memory_bytes < 1:
            raise ApprenticeError("memory_bytes must be a positive integer")
        service_width = cls._service_width(embedding_width)
        specs: list[tuple[int, int, int]] = [
            (TEXT, -1, 512),
            (EMBED, -1, service_width),
            (HEAD, -1, service_width),
        ]
        for layer in range(layers):
            specs.append((ATTENTION, layer, service_width))
            specs.append((FFN, layer, service_width))
        entries = [2] * len(specs)
        minimum_modes = sum(width + 2 * (3 * width + META_COUNT) for _, _, width in specs)
        minimum_bytes = minimum_modes * SCALE_COUNT * COMPONENT_COUNT * BATCH_COUNT * 4
        if minimum_bytes > memory_bytes:
            raise ApprenticeError(f"apprentice_memory_budget_too_small:{minimum_bytes}")
        mode_budget = memory_bytes // (SCALE_COUNT * COMPONENT_COUNT * BATCH_COUNT * 4)
        modes = minimum_modes
        cycle = [0] * 16 + [1] * 4 + [2] + list(range(3, len(specs)))
        while True:
            added = 0
            for page_index in cycle:
                stride = 3 * specs[page_index][2] + META_COUNT
                if modes + stride <= mode_budget:
                    entries[page_index] += 1
                    modes += stride
                    added += 1
            if added == 0:
                break
        pages: list[PageDescriptor] = []
        offset = 0
        for (kind, layer, width), count in zip(specs, entries, strict=True):
            page = PageDescriptor(kind, layer, width, offset, count)
            pages.append(page)
            offset += page.mode_count
        if offset != modes:
            raise AssertionError("geometry mode accounting diverged")
        field_bytes = modes * SCALE_COUNT * COMPONENT_COUNT * BATCH_COUNT * 4
        return cls(layers, embedding_width, vocabulary_size, memory_bytes, modes, field_bytes, tuple(pages))

    @classmethod
    def fixture(
        cls,
        *,
        width: int = 512,
        entries: int = 8,
        kind: int = TEXT,
    ) -> "FieldGeometry":
        if width < 1 or entries < 1:
            raise ApprenticeError("fixture width and entries must be positive")
        if kind not in KIND_NAMES:
            raise ApprenticeError("fixture service kind is invalid")
        if any(math.gcd(width, multiplier) != 1 for multiplier, _ in PERMUTATIONS):
            raise ApprenticeError("fixture width must be coprime with every scale permutation")
        layer = 0 if kind in (ATTENTION, FFN) else -1
        page = PageDescriptor(kind, layer, width, 0, entries)
        modes = page.mode_count
        field_bytes = modes * SCALE_COUNT * COMPONENT_COUNT * BATCH_COUNT * 4
        layers = 1 if layer == 0 else 0
        return cls(layers, 2 * width, ALPHABET_SIZE, field_bytes, modes, field_bytes, (page,))


@dataclass(slots=True)
class ProbeResult:
    status: str
    encoded_target: np.ndarray | None
    byte: int | None
    vector: np.ndarray | None
    total_weight: float
    scatter: float
    minimum_distance2: float
    weights: np.ndarray
    distances2: np.ndarray
    supporting_entries: tuple[int, ...]


@dataclass(slots=True)
class ObserveResult:
    prediction: ProbeResult
    entry: int
    merged: bool
    evicted: int | None
    prediction_success: bool


class ApprenticeField:
    """One sole adaptive Qi tensor and its fixed boundary operations."""

    def __init__(self, geometry: FieldGeometry, state: np.ndarray | None = None):
        self.geometry = geometry
        expected = (SCALE_COUNT, COMPONENT_COUNT * geometry.modes, BATCH_COUNT)
        if state is None:
            self.field = np.zeros(expected, dtype=np.float32)
        else:
            value = np.asarray(state)
            if value.shape != expected or value.dtype != np.float32 or not value.flags.c_contiguous:
                raise ApprenticeError("field must be contiguous float32 [S,9M,1]")
            if not np.isfinite(value).all():
                raise ApprenticeError("field must be finite")
            self.field = value.copy()
        self.field_revision = 0
        self.engram_evictions = 0
        self._codebooks: dict[tuple[int, int], np.ndarray] = {}
        self._validate_complete_field()

    @property
    def parts(self) -> np.ndarray:
        return self.field[:, :, 0].reshape(SCALE_COUNT, COMPONENT_COUNT, self.geometry.modes)

    def copy(self) -> "ApprenticeField":
        result = ApprenticeField(self.geometry, self.field)
        result.field_revision = self.field_revision
        result.engram_evictions = self.engram_evictions
        return result

    def field_bytes(self) -> bytes:
        return np.asarray(self.field, dtype="<f4", order="C").tobytes(order="C")

    def field_sha256(self) -> str:
        return hashlib.sha256(self.field_bytes()).hexdigest()

    def page(self, page_index: int) -> PageDescriptor:
        if isinstance(page_index, bool) or not isinstance(page_index, int) or not 0 <= page_index < len(self.geometry.pages):
            raise ApprenticeError("page index is outside the field geometry")
        return self.geometry.pages[page_index]

    def codebook(self, scale: int, width: int) -> np.ndarray:
        if isinstance(scale, bool) or not isinstance(scale, int) or not 0 <= scale < SCALE_COUNT:
            raise ApprenticeError("scale is outside the fixed codebook")
        if width < 1 or any(math.gcd(width, multiplier) != 1 for multiplier, _ in PERMUTATIONS):
            raise ApprenticeError("codebook width is not permutation-safe")
        cached = self._codebooks.get((scale, width))
        if cached is not None:
            return cached
        symbols = np.arange(1, ALPHABET_SIZE + 1, dtype=np.uint64)[:, None]
        positions = np.arange(1, width + 1, dtype=np.uint64)[None, :]
        perm_a, perm_b = PERMUTATIONS[scale]
        prime = np.uint64(PRIMES[scale])
        permuted = ((positions * np.uint64(perm_a) + np.uint64(perm_b)) % np.uint64(width)) + np.uint64(1)
        c0, c1, c2, c3 = (np.uint64(value) for value in COEFFICIENTS[scale])
        symbol_mod = symbols % prime
        position_mod = permuted % prime
        phase_index = (
            c0 * ((symbol_mod * symbol_mod) % prime) * position_mod
            + c1 * symbol_mod * ((position_mod * position_mod) % prime)
            + c2 * ((position_mod * position_mod) % prime)
            + c3 * symbol_mod
        ) % prime
        phase = (2.0 * math.pi / float(PRIMES[scale])) * phase_index.astype(np.float64)
        values = (np.cos(phase) + 1j * np.sin(phase)).astype(np.complex64)
        values.setflags(write=False)
        self._codebooks[(scale, width)] = values
        return values

    @staticmethod
    def _permutation(scale: int, width: int) -> np.ndarray:
        perm_a, perm_b = PERMUTATIONS[scale]
        return (np.arange(width, dtype=np.int64) * perm_a + perm_b) % width

    def align(self, values: np.ndarray, scale: int) -> np.ndarray:
        source = np.asarray(values, dtype=np.complex64)
        if source.shape[-1] < 1:
            raise ApprenticeError("aligned value must have a nonempty final axis")
        result = np.empty_like(source)
        result[..., self._permutation(scale, source.shape[-1])] = source
        return result

    def unalign(self, values: np.ndarray, scale: int) -> np.ndarray:
        source = np.asarray(values, dtype=np.complex64)
        return np.ascontiguousarray(source[..., self._permutation(scale, source.shape[-1])])

    @staticmethod
    def bounded_serialize(vector: np.ndarray | Sequence[float], width: int) -> np.ndarray:
        values = np.asarray(vector, dtype=np.float64)
        if values.ndim != 1 or values.size > 2 * width or not np.isfinite(values).all():
            raise ApprenticeError("vector must be finite, one-dimensional, and fit the page width")
        norm = float(np.linalg.norm(values))
        bounded = (values / (1.0 + norm)).astype(np.float32)
        packed = np.zeros(2 * width, dtype=np.float32)
        packed[: bounded.size] = bounded
        return np.ascontiguousarray(packed[0::2] + 1j * packed[1::2], dtype=np.complex64)

    @staticmethod
    def bounded_deserialize(encoded: np.ndarray, length: int) -> np.ndarray:
        values = np.asarray(encoded, dtype=np.complex64)
        if values.ndim != 1 or isinstance(length, bool) or not isinstance(length, int) or not 0 <= length <= 2 * values.size:
            raise ApprenticeError("encoded vector shape or requested length is invalid")
        flat = np.empty(2 * values.size, dtype=np.float32)
        flat[0::2] = np.real(values)
        flat[1::2] = np.imag(values)
        norm = float(np.linalg.norm(flat.astype(np.float64)))
        if not np.isfinite(flat).all() or not math.isfinite(norm) or norm >= 1.0 - NORM_GUARD:
            raise ApprenticeError("encoded vector is unavailable")
        return np.ascontiguousarray((flat[:length].astype(np.float64) / (1.0 - norm)).astype(np.float32))

    @staticmethod
    def _common(parts: np.ndarray, start: int, count: int) -> np.ndarray:
        stop = start + count
        yang = parts[:, 0, start:stop] + 1j * parts[:, 1, start:stop]
        yin = parts[:, 2, start:stop] + 1j * parts[:, 3, start:stop]
        return np.ascontiguousarray((PHI * yang + yin) / (1.0 + PHI * PHI), dtype=np.complex64)

    @staticmethod
    def _set_common(parts: np.ndarray, start: int, values: np.ndarray) -> None:
        common = np.asarray(values, dtype=np.complex64)
        if common.ndim != 2 or common.shape[0] != SCALE_COUNT:
            raise ApprenticeError("common coordinates must have shape [S,N]")
        stop = start + common.shape[1]
        parts[:, 0, start:stop] = PHI * np.real(common)
        parts[:, 1, start:stop] = PHI * np.imag(common)
        parts[:, 2, start:stop] = np.real(common)
        parts[:, 3, start:stop] = np.imag(common)
        parts[:, 4:8, start:stop] = 0.0

    @staticmethod
    def _differential(parts: np.ndarray, start: int, count: int) -> tuple[np.ndarray, np.ndarray]:
        stop = start + count
        position = (
            parts[:, 0, start:stop]
            + 1j * parts[:, 1, start:stop]
            - PHI * (parts[:, 2, start:stop] + 1j * parts[:, 3, start:stop])
        )
        velocity = (
            parts[:, 4, start:stop]
            + 1j * parts[:, 5, start:stop]
            - PHI * (parts[:, 6, start:stop] + 1j * parts[:, 7, start:stop])
        )
        return np.ascontiguousarray(position, dtype=np.complex64), np.ascontiguousarray(velocity, dtype=np.complex64)

    @staticmethod
    def _set_differential(parts: np.ndarray, start: int, position: np.ndarray, velocity: np.ndarray) -> None:
        d_value = np.asarray(position, dtype=np.complex64)
        v_value = np.asarray(velocity, dtype=np.complex64)
        if d_value.shape != v_value.shape or d_value.ndim != 2 or d_value.shape[0] != SCALE_COUNT:
            raise ApprenticeError("differential coordinates must share shape [S,N]")
        stop = start + d_value.shape[1]
        denominator = 1.0 + PHI * PHI
        parts[:, 0, start:stop] = np.real(d_value) / denominator
        parts[:, 1, start:stop] = np.imag(d_value) / denominator
        parts[:, 2, start:stop] = -PHI * np.real(d_value) / denominator
        parts[:, 3, start:stop] = -PHI * np.imag(d_value) / denominator
        parts[:, 4, start:stop] = np.real(v_value) / denominator
        parts[:, 5, start:stop] = np.imag(v_value) / denominator
        parts[:, 6, start:stop] = -PHI * np.real(v_value) / denominator
        parts[:, 7, start:stop] = -PHI * np.imag(v_value) / denominator

    @staticmethod
    def _bound_differential(position: np.ndarray, velocity: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        d_value = np.asarray(position, dtype=np.complex128).copy()
        v_value = np.asarray(velocity, dtype=np.complex128).copy()
        denominator = 1.0 + PHI * PHI
        differential_cap = MAX_AMPLITUDE * denominator / PHI
        for values in (d_value, v_value):
            magnitudes = np.abs(values)
            scale = np.minimum(1.0, differential_cap / np.maximum(magnitudes, np.finfo(np.float64).tiny))
            values *= scale
        for scale_index in range(SCALE_COUNT):
            energy = float(np.mean((np.abs(d_value[scale_index]) ** 2 + np.abs(v_value[scale_index]) ** 2) / denominator))
            if energy > MAX_MEAN_ENERGY:
                factor = math.sqrt(MAX_MEAN_ENERGY / energy)
                d_value[scale_index] *= factor
                v_value[scale_index] *= factor
        return np.ascontiguousarray(d_value, dtype=np.complex64), np.ascontiguousarray(v_value, dtype=np.complex64)

    def _advance_context(self, position: np.ndarray, velocity: np.ndarray, width: int, symbol: int) -> tuple[np.ndarray, np.ndarray]:
        if isinstance(symbol, bool) or not isinstance(symbol, (int, np.integer)) or not 0 <= int(symbol) < ALPHABET_SIZE:
            raise ApprenticeError("context symbol is outside the fixed alphabet")
        d_value = np.asarray(position, dtype=np.complex64).copy()
        v_value = np.asarray(velocity, dtype=np.complex64).copy()
        if d_value.shape != (SCALE_COUNT, width) or v_value.shape != d_value.shape:
            raise ApprenticeError("context arrays have the wrong shape")
        profile = 1.0 + MODE_SLOPE * np.arange(width, dtype=np.float64) / max(width - 1, 1)
        for scale in range(SCALE_COUNT):
            scale_decay = SCALE_RATIO ** (-0.5 * scale)
            gain = SENSING_GAIN * scale_decay
            d_value[scale] += np.float32(gain) * (self.codebook(scale, width)[int(symbol)] - d_value[scale])
            omega2 = np.maximum(SLOW_OMEGA2, FAST_OMEGA2 * scale_decay * profile)
            damping = max(SLOW_DAMPING, FAST_DAMPING * scale_decay)
            damp = math.exp(-damping * DT)
            magnitude2 = np.abs(d_value[scale].astype(np.complex128)) ** 2
            v_value[scale] = (
                damp * v_value[scale]
                + DT * (-omega2 * d_value[scale] - NONLINEAR_GAIN * magnitude2 * d_value[scale])
            ).astype(np.complex64)
            d_value[scale] += np.float32(DT) * v_value[scale]
        return self._bound_differential(d_value, v_value)

    def _update_epsilon(self, parts: np.ndarray, start: int, count: int) -> None:
        stop = start + count
        yang2 = parts[:, 0, start:stop] ** 2 + parts[:, 1, start:stop] ** 2
        yin2 = parts[:, 2, start:stop] ** 2 + parts[:, 3, start:stop] ** 2
        target = np.minimum((yang2 - PHI * yin2) ** 2, EPSILON_CLIP)
        parts[:, 8, start:stop] = np.minimum(
            (1.0 - EPSILON_TAU) * parts[:, 8, start:stop] + EPSILON_TAU * target,
            EPSILON_CLIP,
        )

    def sense(self, page_index: int, symbols: Iterable[int]) -> None:
        page = self.page(page_index)
        parts = self.parts
        for symbol in symbols:
            position, velocity = self._differential(parts, page.active_offset, page.width)
            position, velocity = self._advance_context(position, velocity, page.width, int(symbol))
            self._set_differential(parts, page.active_offset, position, velocity)
            self._update_epsilon(parts, page.active_offset, page.width)
            self._validate_active(page)

    def reset_context(self) -> None:
        parts = self.parts
        for page in self.geometry.pages:
            start = page.active_offset
            stop = start + page.width
            parts[:, :, start:stop] = 0.0

    def _temporary_encoded(self, width: int, symbols: Iterable[int]) -> np.ndarray:
        position = np.zeros((SCALE_COUNT, width), dtype=np.complex64)
        velocity = np.zeros_like(position)
        for symbol in symbols:
            position, velocity = self._advance_context(position, velocity, width, int(symbol))
        result = np.empty_like(position)
        for scale in range(SCALE_COUNT):
            packed = self.bounded_serialize(self._complex_to_real(position[scale]), width)
            result[scale] = self.align(packed, scale)
        return result

    @staticmethod
    def _complex_to_real(values: np.ndarray) -> np.ndarray:
        source = np.asarray(values, dtype=np.complex64)
        result = np.empty(2 * source.size, dtype=np.float32)
        result[0::2] = np.real(source).reshape(-1)
        result[1::2] = np.imag(source).reshape(-1)
        return result

    def _active_encoded(self, page: PageDescriptor) -> np.ndarray:
        position, _ = self._differential(self.parts, page.active_offset, page.width)
        result = np.empty_like(position)
        for scale in range(SCALE_COUNT):
            result[scale] = self.align(
                self.bounded_serialize(self._complex_to_real(position[scale]), page.width),
                scale,
            )
        return result

    def make_text_key(self, page_index: int, byte_index: int, id_prefix: Sequence[int]) -> np.ndarray:
        page = self.page(page_index)
        if page.kind != TEXT or not 0 <= byte_index < TOKEN_BYTE_COUNT:
            raise ApprenticeError("TEXT key requires a TEXT page and byte index 0..3")
        prefix = tuple(int(value) for value in id_prefix)
        if len(prefix) != byte_index or any(not 0 <= value <= 255 for value in prefix):
            raise ApprenticeError("ID prefix must contain exactly the prior bytes")
        temporary = self._temporary_encoded(page.width, (SYSTEM, byte_index, END, ASSISTANT, *prefix))
        return np.ascontiguousarray(np.stack((self._active_encoded(page), temporary), axis=1) / math.sqrt(2.0), dtype=np.complex64)

    def make_embed_key(self, page_index: int, token: int, piece: bytes) -> np.ndarray:
        page = self.page(page_index)
        if page.kind != EMBED or not 0 <= token <= 0xFFFFFFFF or not isinstance(piece, bytes):
            raise ApprenticeError("EMBED key requires a token ID and byte piece")
        events = (SYSTEM, *int(token).to_bytes(4, "little"), END, *piece)
        temporary = self._temporary_encoded(page.width, events)
        return np.ascontiguousarray(np.stack((temporary, np.zeros_like(temporary)), axis=1) / math.sqrt(2.0), dtype=np.complex64)

    def make_vector_key(
        self,
        page_index: int,
        vector: np.ndarray,
        *,
        byte_index: int | None = None,
        id_prefix: Sequence[int] = (),
    ) -> np.ndarray:
        page = self.page(page_index)
        if page.kind not in (ATTENTION, FFN, HEAD):
            raise ApprenticeError("vector key requires ATTENTION, FFN, or HEAD page")
        first_canonical = self.bounded_serialize(vector, page.width)
        first = np.repeat(first_canonical[None, :], SCALE_COUNT, axis=0)
        if page.kind == ATTENTION:
            second = self._active_encoded(page)
        elif page.kind == HEAD:
            if byte_index is None or not 0 <= byte_index < TOKEN_BYTE_COUNT:
                raise ApprenticeError("HEAD key requires byte index 0..3")
            prefix = tuple(int(value) for value in id_prefix)
            if len(prefix) != byte_index or any(not 0 <= value <= 255 for value in prefix):
                raise ApprenticeError("HEAD ID prefix must contain exactly the prior bytes")
            second = self._temporary_encoded(page.width, (SYSTEM, byte_index, END, ASSISTANT, *prefix))
        else:
            if byte_index is not None or tuple(id_prefix):
                raise ApprenticeError("FFN key does not accept byte context")
            second = np.zeros_like(first)
        return np.ascontiguousarray(np.stack((first, second), axis=1) / math.sqrt(2.0), dtype=np.complex64)

    def encode_vector_target(self, page_index: int, vector: np.ndarray) -> np.ndarray:
        page = self.page(page_index)
        if page.kind in (TEXT, HEAD):
            raise ApprenticeError("TEXT and HEAD pages require byte targets")
        encoded = self.bounded_serialize(vector, page.width)
        return np.ascontiguousarray(np.repeat(encoded[None, :], SCALE_COUNT, axis=0))

    def encode_byte_target(self, page_index: int, byte: int) -> np.ndarray:
        page = self.page(page_index)
        if page.kind not in (TEXT, HEAD) or not 0 <= byte <= 255:
            raise ApprenticeError("byte target requires a TEXT/HEAD page and byte 0..255")
        canonical = self.align(self.codebook(0, page.width)[byte], 0) / math.sqrt(float(page.width))
        return np.ascontiguousarray(np.repeat(canonical[None, :], SCALE_COUNT, axis=0), dtype=np.complex64)

    def decode_byte(self, page_index: int, encoded: np.ndarray) -> int:
        page = self.page(page_index)
        target = np.asarray(encoded, dtype=np.complex64)
        if target.shape != (page.width,) or not np.isfinite(target).all():
            raise ApprenticeError("byte target has the wrong shape or nonfinite values")
        codebook = self.align(self.codebook(0, page.width), 0) / math.sqrt(float(page.width))
        scores = np.real(codebook.conj() @ target).astype(np.float64)
        return int(np.argmax(scores))

    @staticmethod
    def _metadata_from_common(common: np.ndarray) -> tuple[np.ndarray, int, int, int, float, int]:
        if common.shape != (SCALE_COUNT, META_COUNT):
            raise ApprenticeError("metadata common coordinates have the wrong shape")
        if np.max(np.abs(np.imag(common))) > 1.0e-5:
            raise ApprenticeError("metadata imaginary components must be zero")
        occupancy = np.real(common[:, META_OCCUPANCY]).astype(np.float64)
        replicated = np.real(common[:, 1:]).astype(np.float64)
        if np.max(np.abs(replicated - replicated[0:1])) > 1.0e-4:
            raise ApprenticeError("metadata counts, error, and age must match across scales")
        counts = np.rint(255.0 * replicated[0, [0, 1, 2, 4]]).astype(np.int64)
        if np.max(np.abs(255.0 * replicated[0, [0, 1, 2, 4]] - counts)) > 1.0e-4:
            raise ApprenticeError("metadata integer cells are not exactly encoded")
        teacher, exact, novel, age = (int(value) for value in counts)
        error = float(replicated[0, META_ERROR_EMA - 1])
        return occupancy, teacher, exact, novel, error, age

    @staticmethod
    def _metadata_common(
        occupancy: np.ndarray,
        teacher: int,
        exact: int,
        novel: int,
        error: float,
        age: int,
    ) -> np.ndarray:
        occ = np.asarray(occupancy, dtype=np.float64)
        if occ.shape != (SCALE_COUNT,) or not np.isfinite(occ).all() or np.any((occ < 0.0) | (occ > 1.0)):
            raise ApprenticeError("occupancy must be finite [S] values in [0,1]")
        integer_values = (teacher, exact, novel, age)
        if any(isinstance(value, bool) or not isinstance(value, (int, np.integer)) or not 0 <= int(value) <= COUNT_LIMIT for value in integer_values):
            raise ApprenticeError("metadata counts and age must be integers in [0,255]")
        if not math.isfinite(error) or not 0.0 <= error <= 1.0:
            raise ApprenticeError("metadata error EMA must be in [0,1]")
        result = np.zeros((SCALE_COUNT, META_COUNT), dtype=np.complex64)
        result[:, META_OCCUPANCY] = occ.astype(np.float32)
        result[:, META_TEACHER_OBSERVATIONS] = np.float32(teacher / 255.0)
        result[:, META_EXACT_SUCCESSES] = np.float32(exact / 255.0)
        result[:, META_NOVEL_SUCCESSES] = np.float32(novel / 255.0)
        result[:, META_ERROR_EMA] = np.float32(error)
        result[:, META_AGE] = np.float32(age / 255.0)
        return result

    @staticmethod
    def _entry_base(page: PageDescriptor, entry: int, *, local: bool = False) -> int:
        if not 0 <= entry < page.entries:
            raise ApprenticeError("engram entry is outside its page")
        return (0 if local else page.memory_offset) + entry * page.entry_stride

    def _read_entry(self, page: PageDescriptor, entry: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[np.ndarray, int, int, int, float, int]]:
        base = self._entry_base(page, entry)
        common = self._common(self.parts, base, page.entry_stride)
        key0 = common[:, : page.width]
        key1 = common[:, page.width : 2 * page.width]
        target = common[:, 2 * page.width : 3 * page.width]
        metadata = self._metadata_from_common(common[:, 3 * page.width :])
        return key0, key1, target, metadata

    @staticmethod
    def _threshold_band(value: float, threshold: float) -> bool:
        guard = max(THRESHOLD_ABS_GUARD, THRESHOLD_REL_GUARD * abs(threshold))
        return abs(value - threshold) <= guard

    @staticmethod
    def _relative_error(actual: np.ndarray, expected: np.ndarray) -> float:
        lhs = np.asarray(actual, dtype=np.float64)
        rhs = np.asarray(expected, dtype=np.float64)
        denominator = max(float(np.linalg.norm(rhs)), 1.0e-12)
        return float(np.linalg.norm(lhs - rhs) / denominator)

    def probe(self, page_index: int, key: np.ndarray, *, vector_length: int | None = None) -> ProbeResult:
        page = self.page(page_index)
        query = np.asarray(key, dtype=np.complex64)
        if query.shape != (SCALE_COUNT, 2, page.width) or not np.isfinite(query).all():
            raise ApprenticeError("query key must be finite complex64 [S,2,W]")
        weights = np.zeros(page.entries, dtype=np.float64)
        distances = np.full(page.entries, np.inf, dtype=np.float64)
        targets: list[np.ndarray | None] = [None] * page.entries
        metadata: list[tuple[np.ndarray, int, int, int, float, int] | None] = [None] * page.entries
        radius = TEXT_RADIUS if page.kind in (TEXT, EMBED) else VECTOR_RADIUS
        for entry in range(page.entries):
            key0, key1, target, meta = self._read_entry(page, entry)
            occupancy, _, _, _, error, _ = meta
            if occupancy[0] < OCCUPANCY_FLOOR:
                continue
            available = occupancy >= OCCUPANCY_FLOOR
            scale_distances = []
            scale_targets = []
            for scale in np.flatnonzero(available):
                stored0 = key0[scale] / occupancy[scale]
                stored1 = key1[scale] / occupancy[scale]
                difference0 = query[scale, 0] - stored0
                difference1 = query[scale, 1] - stored1
                scale_distances.append(float(np.real(np.vdot(difference0, difference0)) + np.real(np.vdot(difference1, difference1))))
                scale_targets.append(target[scale] / occupancy[scale])
            distance2 = float(np.mean(scale_distances))
            kernel = max(0.0, 1.0 - distance2 / (radius * radius)) ** 2
            weight = kernel * float(np.mean(occupancy[available])) / (1.0 + error)
            distances[entry] = distance2
            weights[entry] = weight
            targets[entry] = np.mean(np.stack(scale_targets, axis=0), axis=0).astype(np.complex64)
            metadata[entry] = meta
        supporting = tuple(int(index) for index in np.flatnonzero(weights > 0.0))
        total_weight = float(np.sum(weights))
        minimum_distance = float(np.min(distances)) if np.isfinite(distances).any() else math.inf
        empty = ProbeResult(NEEDS_TEACHER, None, None, None, total_weight, math.inf, minimum_distance, weights, distances, supporting)
        if not supporting or total_weight < WEIGHT_FLOOR or self._threshold_band(total_weight, WEIGHT_FLOOR):
            return empty
        target_values: dict[int, np.ndarray] = {}
        for index in supporting:
            entry_target = targets[index]
            if entry_target is None:
                raise AssertionError("supporting entry has no decoded target")
            target_values[index] = entry_target
        encoded = np.zeros(page.width, dtype=np.complex64)
        for index, entry_target in target_values.items():
            encoded += np.float32(weights[index]) * entry_target
        encoded = np.ascontiguousarray(encoded / total_weight, dtype=np.complex64)
        scatter = float(
            sum(
                weights[index] * float(np.real(np.vdot(entry_target - encoded, entry_target - encoded)))
                for index, entry_target in target_values.items()
            )
            / total_weight
        )
        if scatter > SCATTER_CEILING or self._threshold_band(scatter, SCATTER_CEILING):
            empty.encoded_target = encoded
            empty.scatter = scatter
            return empty
        exact_eligible = False
        novel_eligible = True
        for entry in supporting:
            meta = metadata[entry]
            if meta is None:
                continue
            _, teacher, exact, novel, error, _ = meta
            if distances[entry] <= EXACT_DISTANCE2 and teacher >= MIN_OBSERVATIONS and exact >= MIN_EXACT_SUCCESSES:
                exact_eligible = True
            if novel < MIN_NOVEL_SUCCESSES or error > VECTOR_SUCCESS:
                novel_eligible = False
            if distances[entry] > 0.0 and self._threshold_band(distances[entry], EXACT_DISTANCE2):
                return ProbeResult(NEEDS_TEACHER, encoded, None, None, total_weight, scatter, minimum_distance, weights, distances, supporting)
        if not exact_eligible and not novel_eligible:
            return ProbeResult(NEEDS_TEACHER, encoded, None, None, total_weight, scatter, minimum_distance, weights, distances, supporting)
        status = FIELD_EXACT if exact_eligible else FIELD_INTERPOLATED
        if page.kind in (TEXT, HEAD):
            byte = self.decode_byte(page_index, encoded)
            return ProbeResult(status, encoded, byte, None, total_weight, scatter, minimum_distance, weights, distances, supporting)
        if vector_length is None:
            raise ApprenticeError("vector probe requires its decoded length")
        try:
            vector = self.bounded_deserialize(encoded, vector_length)
        except ApprenticeError:
            return ProbeResult(NEEDS_TEACHER, encoded, None, None, total_weight, scatter, minimum_distance, weights, distances, supporting)
        return ProbeResult(status, encoded, None, vector, total_weight, scatter, minimum_distance, weights, distances, supporting)

    def _entry_target_matches(
        self,
        page_index: int,
        page: PageDescriptor,
        entry: int,
        *,
        byte: int | None,
        vector: np.ndarray | None,
    ) -> bool:
        _, _, stored, metadata = self._read_entry(page, entry)
        occupancy = metadata[0]
        available = occupancy >= OCCUPANCY_FLOOR
        if not np.any(available):
            return False
        decoded = np.mean(stored[available] / occupancy[available, None], axis=0).astype(np.complex64)
        if page.kind in (TEXT, HEAD):
            return byte is not None and self.decode_byte(page_index, decoded) == byte
        if vector is None:
            return False
        try:
            restored = self.bounded_deserialize(decoded, vector.size)
        except ApprenticeError:
            return False
        return self._relative_error(restored, vector) <= VECTOR_SUCCESS

    def observe(
        self,
        page_index: int,
        key: np.ndarray,
        *,
        byte: int | None = None,
        vector: np.ndarray | None = None,
    ) -> ObserveResult:
        page = self.page(page_index)
        query = np.asarray(key, dtype=np.complex64)
        if query.shape != (SCALE_COUNT, 2, page.width) or not np.isfinite(query).all():
            raise ApprenticeError("observation key must be finite complex64 [S,2,W]")
        if page.kind in (TEXT, HEAD):
            if byte is None or vector is not None:
                raise ApprenticeError("byte page observation requires only a byte target")
            target = self.encode_byte_target(page_index, byte)
            teacher_vector = None
            vector_length = None
        else:
            if vector is None or byte is not None:
                raise ApprenticeError("vector page observation requires only a vector target")
            teacher_vector = np.asarray(vector, dtype=np.float32)
            if teacher_vector.ndim != 1 or not np.isfinite(teacher_vector).all():
                raise ApprenticeError("teacher vector must be finite and one-dimensional")
            target = self.encode_vector_target(page_index, teacher_vector)
            vector_length = int(teacher_vector.size)
        prediction = self.probe(page_index, query, vector_length=vector_length)
        encoded_prediction = prediction.encoded_target
        if page.kind in (TEXT, HEAD):
            prediction_success = (
                encoded_prediction is not None
                and byte is not None
                and self.decode_byte(page_index, encoded_prediction) == byte
            )
            prediction_error = 0.0 if prediction_success else 1.0
        else:
            prediction_success = encoded_prediction is not None
            if encoded_prediction is not None and vector_length is not None and teacher_vector is not None:
                try:
                    predicted_vector = self.bounded_deserialize(encoded_prediction, vector_length)
                    prediction_error = self._relative_error(predicted_vector, teacher_vector)
                    prediction_success = prediction_error <= VECTOR_SUCCESS
                except ApprenticeError:
                    prediction_success = False
                    prediction_error = 1.0
            else:
                prediction_error = 1.0
        memory_start = page.memory_offset
        memory_count = page.entries * page.entry_stride
        candidate = self.parts[:, :, memory_start : memory_start + memory_count].copy()

        def read_candidate(entry: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[np.ndarray, int, int, int, float, int]]:
            base = self._entry_base(page, entry, local=True)
            common = self._common(candidate, base, page.entry_stride)
            return (
                common[:, : page.width],
                common[:, page.width : 2 * page.width],
                common[:, 2 * page.width : 3 * page.width],
                self._metadata_from_common(common[:, 3 * page.width :]),
            )

        def write_metadata(entry: int, metadata: tuple[np.ndarray, int, int, int, float, int]) -> None:
            base = self._entry_base(page, entry, local=True) + 3 * page.width
            self._set_common(candidate, base, self._metadata_common(*metadata))

        for entry in range(page.entries):
            _, _, _, meta = read_candidate(entry)
            occupancy, teacher, exact, novel, error, age = meta
            if occupancy[0] >= OCCUPANCY_FLOOR:
                write_metadata(entry, (occupancy, teacher, exact, novel, error, min(COUNT_LIMIT, age + 1)))
        for entry in prediction.supporting_entries:
            _, _, _, meta = read_candidate(entry)
            occupancy, teacher, exact, novel, error, age = meta
            if prediction_success:
                if prediction.distances2[entry] <= EXACT_DISTANCE2:
                    exact = min(COUNT_LIMIT, exact + 1)
                else:
                    novel = min(COUNT_LIMIT, novel + 1)
            else:
                novel = 0
                error = (1.0 - ERROR_EMA_GAIN) * error + ERROR_EMA_GAIN * min(1.0, prediction_error)
            write_metadata(entry, (occupancy, teacher, exact, novel, error, age))

        merge_entry = None
        merge_distance = math.inf
        for entry in range(page.entries):
            _, _, _, meta = self._read_entry(page, entry)
            if meta[0][0] < OCCUPANCY_FLOOR:
                continue
            distance = float(prediction.distances2[entry])
            if distance <= MERGE_DISTANCE2 and self._entry_target_matches(
                page_index,
                page,
                entry,
                byte=byte,
                vector=teacher_vector,
            ):
                if distance < merge_distance or (distance == merge_distance and (merge_entry is None or entry < merge_entry)):
                    merge_entry = entry
                    merge_distance = distance
        evicted = None
        if merge_entry is not None:
            selected = merge_entry
            merged = True
        else:
            free = [entry for entry in range(page.entries) if read_candidate(entry)[3][0][0] < OCCUPANCY_FLOOR]
            if free:
                selected = free[0]
            else:
                scores = []
                for entry in range(page.entries):
                    _, _, _, meta = read_candidate(entry)
                    _, teacher, exact, novel, _, age = meta
                    scores.append(((exact + 2 * novel + teacher) / (1.0 + age), entry))
                selected = min(scores)[1]
                evicted = selected
                self.engram_evictions += 1
            merged = False
            base = self._entry_base(page, selected, local=True)
            candidate[:, :, base : base + page.entry_stride] = 0.0

        base = self._entry_base(page, selected, local=True)
        old_key0, old_key1, old_target, old_meta = read_candidate(selected)
        old_occupancy, old_teacher, old_exact, old_novel, old_error, _ = old_meta
        if merged:
            new_teacher = min(COUNT_LIMIT, old_teacher + 1)
            gain0 = 1.0 / min(new_teacher, MERGE_WINDOW)
            new_key0 = old_key0.copy()
            new_key1 = old_key1.copy()
            new_target = old_target.copy()
            new_occupancy = old_occupancy.copy()
            old0 = max(float(old_occupancy[0]), OCCUPANCY_FLOOR)
            new_key0[0] = (1.0 - gain0) * (old_key0[0] / old0) + gain0 * query[0, 0]
            new_key1[0] = (1.0 - gain0) * (old_key1[0] / old0) + gain0 * query[0, 1]
            new_target[0] = (1.0 - gain0) * (old_target[0] / old0) + gain0 * target[0]
            new_occupancy[0] = 1.0
        else:
            new_teacher = 1
            old_exact = 0
            old_novel = 0
            old_error = 0.0
            new_key0 = np.zeros_like(old_key0)
            new_key1 = np.zeros_like(old_key1)
            new_target = np.zeros_like(old_target)
            new_occupancy = np.zeros_like(old_occupancy)
            new_key0[0] = query[0, 0]
            new_key1[0] = query[0, 1]
            new_target[0] = target[0]
            new_occupancy[0] = 1.0
        for scale in range(1, SCALE_COUNT):
            gain = min(0.5, SCALE_RATIO ** (-scale)) * float(new_occupancy[scale - 1])
            old_occ = float(old_occupancy[scale])
            updated_occupancy = (1.0 - gain) * old_occ + gain
            new_occupancy[scale] = updated_occupancy
            new_key0[scale] = (1.0 - gain) * old_key0[scale] + gain * query[scale, 0]
            new_key1[scale] = (1.0 - gain) * old_key1[scale] + gain * query[scale, 1]
            new_target[scale] = (1.0 - gain) * old_target[scale] + gain * target[scale]
        common = np.concatenate((new_key0, new_key1, new_target), axis=1)
        self._set_common(candidate, base, common)
        write_metadata(
            selected,
            (
                new_occupancy,
                new_teacher,
                old_exact,
                old_novel,
                old_error,
                0,
            ),
        )
        self._update_epsilon(candidate, base, page.entry_stride)
        self._validate_memory_candidate(candidate, page)
        self.parts[:, :, memory_start : memory_start + memory_count] = candidate
        if self.field_revision == 0xFFFFFFFFFFFFFFFF:
            raise ApprenticeError("field revision overflow")
        self.field_revision += 1
        return ObserveResult(prediction, selected, merged, evicted, prediction_success)

    def guide_byte(self, page_index: int, byte: int) -> int:
        page = self.page(page_index)
        if page.kind not in (TEXT, HEAD) or not 0 <= byte <= 255:
            raise ApprenticeError("guided byte requires a TEXT/HEAD page and byte 0..255")
        target = self.codebook(0, page.width)[byte]
        position = np.zeros(page.width, dtype=np.complex64)
        field_before = self.field_bytes()
        for _ in range(GUIDE_ROUNDS):
            position += np.float32(BYTE_GUIDE_GAIN) * (target - position)
            magnitude = np.abs(position)
            position *= np.minimum(1.0, MAX_AMPLITUDE / np.maximum(magnitude, np.finfo(np.float32).tiny))
            scores = np.real(self.codebook(0, page.width)[:256].conj() @ position) / float(page.width)
            emitted = int(np.argmax(scores))
            if emitted == byte:
                if self.field_bytes() != field_before:
                    raise AssertionError("ephemeral byte guide mutated retained field")
                return emitted
        raise ApprenticeError("apprentice_assimilation_failed")

    def guide_vector(self, page_index: int, vector: np.ndarray) -> np.ndarray:
        page = self.page(page_index)
        if page.kind in (TEXT, HEAD):
            raise ApprenticeError("guided vector requires a vector page")
        target = self.bounded_serialize(vector, page.width)
        port = np.zeros_like(target)
        port += np.float32(VECTOR_GUIDE_GAIN) * (target - port)
        restored = self.bounded_deserialize(port, int(np.asarray(vector).size))
        if self._relative_error(restored, np.asarray(vector, dtype=np.float32)) > GUIDED_VECTOR_TOLERANCE:
            raise ApprenticeError("apprentice_assimilation_failed")
        return restored

    def _validate_active(self, page: PageDescriptor) -> None:
        parts = self.parts[:, :, page.active_offset : page.active_offset + page.width]
        if not np.isfinite(parts).all():
            raise ApprenticeError("active field became nonfinite")
        for scale in range(SCALE_COUNT):
            for real_index in (0, 2, 4, 6):
                magnitude = np.hypot(parts[scale, real_index], parts[scale, real_index + 1])
                if np.any(magnitude > MAX_AMPLITUDE + 1.0e-5):
                    raise ApprenticeError("active physical amplitude exceeds its bound")
            energy = float(np.mean(np.sum(parts[scale, :8].astype(np.float64) ** 2, axis=0)))
            if energy > MAX_MEAN_ENERGY + 1.0e-5:
                raise ApprenticeError("active mean energy exceeds its bound")
        if np.any((parts[:, 8] < 0.0) | (parts[:, 8] > EPSILON_CLIP)):
            raise ApprenticeError("active epsilon2 EMA exceeds its bound")

    def _validate_memory_candidate(self, candidate: np.ndarray, page: PageDescriptor) -> None:
        if candidate.shape != (SCALE_COUNT, COMPONENT_COUNT, page.entries * page.entry_stride) or not np.isfinite(candidate).all():
            raise ApprenticeError("candidate memory page has the wrong shape or nonfinite values")
        for scale in range(SCALE_COUNT):
            for real_index in (0, 2, 4, 6):
                magnitude = np.hypot(candidate[scale, real_index], candidate[scale, real_index + 1])
                if np.any(magnitude > MAX_AMPLITUDE + 1.0e-5):
                    raise ApprenticeError("candidate memory amplitude exceeds its bound")
            energy = float(np.mean(np.sum(candidate[scale, :8].astype(np.float64) ** 2, axis=0)))
            if energy > MAX_MEAN_ENERGY + 1.0e-5:
                raise ApprenticeError("candidate memory energy exceeds its bound")
        if np.any((candidate[:, 8] < 0.0) | (candidate[:, 8] > EPSILON_CLIP)):
            raise ApprenticeError("candidate memory epsilon2 EMA exceeds its bound")
        for entry in range(page.entries):
            base = self._entry_base(page, entry, local=True) + 3 * page.width
            metadata = self._common(candidate, base, META_COUNT)
            self._metadata_from_common(metadata)

    def _validate_complete_field(self) -> None:
        if not np.isfinite(self.field).all():
            raise ApprenticeError("field contains nonfinite values")
        for page in self.geometry.pages:
            self._validate_active(page)
            start = page.memory_offset
            count = page.entries * page.entry_stride
            self._validate_memory_candidate(self.parts[:, :, start : start + count], page)


def profile_bytes(geometry: FieldGeometry) -> bytes:
    payload = bytearray()
    for value in (PROFILE_ID, LAYOUT_ID, CODEBOOK_ID, SENSE_ID, ENGRAM_ID, AUDIT_ID, TOKEN_ID, *COMPONENTS):
        payload.extend(value.encode("utf-8"))
        payload.append(0)
    payload.extend(struct.pack("<III", SCALE_COUNT, BATCH_COUNT, len(geometry.pages)))
    for page in geometry.pages:
        payload.extend(struct.pack("<IiIIQ", page.kind, page.layer, page.width, page.entries, page.mode_offset))
    widths = sorted({page.width for page in geometry.pages})
    payload.extend(struct.pack("<I", len(widths)))
    for width in widths:
        for scale in range(SCALE_COUNT):
            payload.extend(
                struct.pack(
                    "<IIIIIIIII",
                    width,
                    scale,
                    PRIMES[scale],
                    *COEFFICIENTS[scale],
                    *PERMUTATIONS[scale],
                )
            )
    float_values = (
        PHI,
        SCALE_RATIO,
        SENSING_GAIN,
        DT,
        FAST_OMEGA2,
        SLOW_OMEGA2,
        FAST_DAMPING,
        SLOW_DAMPING,
        MODE_SLOPE,
        NONLINEAR_GAIN,
        MAX_AMPLITUDE,
        MAX_MEAN_ENERGY,
        EPSILON_TAU,
        EPSILON_CLIP,
        TEXT_RADIUS,
        VECTOR_RADIUS,
        EXACT_DISTANCE2,
        MERGE_DISTANCE2,
        WEIGHT_FLOOR,
        SCATTER_CEILING,
        BYTE_GUIDE_GAIN,
        VECTOR_GUIDE_GAIN,
        NORM_GUARD,
        VECTOR_SUCCESS,
        GUIDED_VECTOR_TOLERANCE,
        ERROR_EMA_GAIN,
        THRESHOLD_ABS_GUARD,
        THRESHOLD_REL_GUARD,
        OCCUPANCY_FLOOR,
    )
    payload.extend(struct.pack("<" + "f" * len(float_values), *float_values))
    payload.extend(
        struct.pack(
            "<IIIIIII",
            COUNT_LIMIT,
            MERGE_WINDOW,
            TOKEN_BYTE_COUNT,
            GUIDE_ROUNDS,
            MIN_OBSERVATIONS,
            MIN_EXACT_SUCCESSES,
            MIN_NOVEL_SUCCESSES,
        )
    )
    return bytes(payload)


def profile_sha256(geometry: FieldGeometry) -> str:
    return hashlib.sha256(profile_bytes(geometry)).hexdigest()


def _deterministic_key(width: int, center: float, slope: float = 0.0) -> np.ndarray:
    coordinates = np.linspace(-1.0, 1.0, width, dtype=np.float64)
    result = np.zeros((SCALE_COUNT, 2, width), dtype=np.complex64)
    for scale in range(SCALE_COUNT):
        real = center + slope * coordinates + scale * 1.0e-5
        imag = 0.5 * center - 0.25 * slope * coordinates - scale * 5.0e-6
        result[scale, 0] = (real + 1j * imag).astype(np.complex64) / math.sqrt(2.0)
        result[scale, 1] = (0.25 * real - 0.5j * imag).astype(np.complex64) / math.sqrt(2.0)
    return result


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_self_test() -> dict[str, object]:
    geometry = FieldGeometry.fixture(width=512, entries=8)
    field = ApprenticeField(geometry)
    page = 0
    initial = field.field_bytes()
    empty = field.probe(page, _deterministic_key(512, 0.0))
    _assert(empty.status == NEEDS_TEACHER and field.field_bytes() == initial, "empty probe changed state or produced output")

    for norm in (0.0, 0.1, 1.0, 100.0):
        vector = np.zeros(17, dtype=np.float32)
        if norm:
            vector[0] = np.float32(norm)
        encoded = field.bounded_serialize(vector, 512)
        restored = field.bounded_deserialize(encoded, vector.size)
        tolerance = 1.0e-6 if norm == 0.0 else 1.0e-4
        _assert(field._relative_error(restored, vector) <= tolerance, f"bounded serialization failed at norm {norm}")
    for invalid in (
        np.full(512, np.complex64(1.0 / math.sqrt(512)), dtype=np.complex64),
        np.full(512, np.complex64(np.nan), dtype=np.complex64),
        np.full(512, np.complex64(np.inf), dtype=np.complex64),
    ):
        before = field.field_bytes()
        try:
            field.bounded_deserialize(invalid, 17)
        except ApprenticeError:
            pass
        else:
            raise AssertionError("invalid bounded vector was accepted")
        _assert(field.field_bytes() == before, "invalid decode changed state")

    key_a = _deterministic_key(512, -0.02, 0.0002)
    key_b = _deterministic_key(512, 0.02, -0.0002)
    target_a = 17
    target_b = 231
    field.observe(page, key_a, byte=target_a)
    field.observe(page, key_a, byte=target_a)
    field.observe(page, key_b, byte=target_b)
    field.observe(page, key_b, byte=target_b)
    probe_a = field.probe(page, key_a)
    probe_b = field.probe(page, key_b)
    _assert(probe_a.status == FIELD_EXACT and probe_a.byte == target_a, "first exact association did not mature")
    _assert(probe_b.status == FIELD_EXACT and probe_b.byte == target_b, "second exact association did not mature")
    unrelated = field.probe(page, _deterministic_key(512, 0.2))
    _assert(unrelated.status == NEEDS_TEACHER, "unrelated key did not request teacher")
    zeroed = field.copy()
    zeroed.field.fill(0.0)
    _assert(zeroed.probe(page, key_a).status == NEEDS_TEACHER, "zeroed field retained a learned answer")

    contradiction = ApprenticeField(FieldGeometry.fixture(width=512, entries=3))
    same_key = _deterministic_key(512, 0.0)
    contradiction.observe(0, same_key, byte=3)
    contradiction.observe(0, same_key, byte=249)
    conflict = contradiction.probe(0, same_key)
    _assert(conflict.status == NEEDS_TEACHER and conflict.scatter > SCATTER_CEILING, "contradictory targets selected an insertion winner")

    interpolation = ApprenticeField(FieldGeometry.fixture(width=512, entries=8, kind=FFN))
    interpolation_page = interpolation.page(0)
    interpolation_key_a = _deterministic_key(512, -0.0005)
    interpolation_key_b = _deterministic_key(512, 0.0005)
    interpolation_target_a = np.asarray([1.0], dtype=np.float32)
    interpolation_target_b = np.asarray([1.001], dtype=np.float32)
    interpolation.observe(0, interpolation_key_a, vector=interpolation_target_a)
    interpolation.observe(0, interpolation_key_a, vector=interpolation_target_a)
    interpolation.observe(0, interpolation_key_b, vector=interpolation_target_b)
    interpolation.observe(0, interpolation_key_b, vector=interpolation_target_b)
    interpolation.observe(
        0,
        _deterministic_key(512, -0.00049),
        vector=np.asarray([1.00001], dtype=np.float32),
    )
    interpolation.observe(
        0,
        _deterministic_key(512, -0.00048),
        vector=np.asarray([1.00002], dtype=np.float32),
    )
    interpolation_query = _deterministic_key(512, 0.0)
    interpolation_result = interpolation.probe(0, interpolation_query, vector_length=1)
    _assert(
        interpolation_result.status == FIELD_INTERPOLATED
        and interpolation_result.vector is not None,
        "non-identical audits did not enable interpolation",
    )
    expected_numerator = np.zeros(512, dtype=np.complex128)
    expected_weight = 0.0
    for entry in interpolation_result.supporting_entries:
        key0, key1, target, metadata = interpolation._read_entry(interpolation_page, entry)
        occupancy, _, _, novel, error, _ = metadata
        _assert(novel >= MIN_NOVEL_SUCCESSES, "interpolation support lacks two novel audits")
        available = occupancy >= OCCUPANCY_FLOOR
        distances = []
        targets = []
        for scale in np.flatnonzero(available):
            difference0 = interpolation_query[scale, 0] - key0[scale] / occupancy[scale]
            difference1 = interpolation_query[scale, 1] - key1[scale] / occupancy[scale]
            distances.append(float(np.real(np.vdot(difference0, difference0)) + np.real(np.vdot(difference1, difference1))))
            targets.append(target[scale] / occupancy[scale])
        distance2 = float(np.mean(distances))
        kernel = max(0.0, 1.0 - distance2 / (VECTOR_RADIUS * VECTOR_RADIUS)) ** 2
        weight = kernel * float(np.mean(occupancy[available])) / (1.0 + error)
        expected_numerator += weight * np.mean(np.stack(targets, axis=0), axis=0)
        expected_weight += weight
    expected_encoded = np.ascontiguousarray(expected_numerator / expected_weight, dtype=np.complex64)
    expected_vector = interpolation.bounded_deserialize(expected_encoded, 1)
    interpolated_vector = interpolation_result.vector
    if interpolated_vector is None:
        raise AssertionError("interpolated probe lost its decoded vector")
    _assert(
        np.allclose(interpolated_vector, expected_vector, rtol=1.0e-6, atol=1.0e-7)
        and 1.0 < float(interpolated_vector[0]) < 1.001,
        "interpolated target does not match the all-entry weighted result",
    )
    guided_vector = np.asarray([0.0, 0.1, -1.0, 100.0], dtype=np.float32)
    _assert(
        interpolation._relative_error(interpolation.guide_vector(0, guided_vector), guided_vector)
        <= GUIDED_VECTOR_TOLERANCE,
        "guided vector failed to preserve magnitude",
    )

    eviction = ApprenticeField(FieldGeometry.fixture(width=512, entries=2))
    eviction.observe(0, _deterministic_key(512, -0.2), byte=1)
    eviction.observe(0, _deterministic_key(512, 0.0), byte=2)
    eviction.observe(0, _deterministic_key(512, 0.2), byte=3)
    _assert(eviction.engram_evictions == 1, "capacity eviction was not counted")

    context_field = ApprenticeField(geometry)
    memory_before = context_field.parts[:, :, geometry.pages[0].memory_offset :].copy().tobytes()
    for index in range(10000):
        context_field.sense(0, (index % ALPHABET_SIZE,))
    memory_after = context_field.parts[:, :, geometry.pages[0].memory_offset :].copy().tobytes()
    _assert(memory_before == memory_after, "context sensing changed memory bytes")
    context_field._validate_complete_field()

    guided_field = ApprenticeField(geometry)
    guided_before = guided_field.field_bytes()
    for byte in range(256):
        _assert(guided_field.guide_byte(0, byte) == byte, f"guided byte {byte} failed")
    _assert(guided_before == guided_field.field_bytes(), "guided output changed retained memory")

    return {
        "schema": "cassi.apprentice.reference-self-test.v1",
        "profile": PROFILE_ID,
        "profile_sha256": profile_sha256(geometry),
        "field_layout": LAYOUT_ID,
        "checks": {
            "empty_probe": "pass",
            "bounded_serialization": "pass",
            "exact_associations": "pass",
            "contradiction": "pass",
            "novel_interpolation": "pass",
            "eviction": "pass",
            "context_steps": 10000,
            "guided_bytes": 256,
        },
    }


def _write_array(directory: Path, name: str, values: np.ndarray, files: list[dict[str, object]]) -> None:
    array = np.ascontiguousarray(values)
    if array.dtype.kind == "f":
        array = array.astype("<f4", copy=False)
        dtype = "f32le"
    elif array.dtype == np.dtype(np.int32):
        array = array.astype("<i4", copy=False)
        dtype = "i32le"
    else:
        raise ApprenticeError(f"unsupported fixture dtype for {name}")
    payload = array.tobytes(order="C")
    path = directory / name
    path.write_bytes(payload)
    files.append(
        {
            "name": name,
            "dtype": dtype,
            "shape": list(array.shape),
            "byte_count": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    )


def write_fixtures(directory: Path) -> dict[str, object]:
    directory.mkdir(parents=True, exist_ok=True)
    geometry = FieldGeometry.fixture(width=512, entries=8)
    field = ApprenticeField(geometry)
    files: list[dict[str, object]] = []
    codebooks = np.stack([field.codebook(scale, 512) for scale in range(SCALE_COUNT)], axis=0)
    codebook_real = np.stack((np.real(codebooks), np.imag(codebooks)), axis=-1)
    _write_array(directory, "codebooks.f32", codebook_real, files)

    sense_events = np.asarray([USER, 67, 97, 115, 115, 105, END, ASSISTANT], dtype=np.int32)
    field.sense(0, sense_events)
    _write_array(directory, "sense-events.i32", sense_events, files)
    _write_array(directory, "sense-state.f32", field.field, files)

    exact = ApprenticeField(geometry)
    exact.sense(0, sense_events)
    key = exact.make_text_key(0, 0, ())
    exact.observe(0, key, byte=73)
    exact.observe(0, key, byte=73)
    exact_probe = exact.probe(0, key)
    _assert(exact_probe.status == FIELD_EXACT and exact_probe.byte == 73, "fixture exact association failed")
    _write_array(directory, "exact-key.f32", np.stack((np.real(key), np.imag(key)), axis=-1), files)
    _write_array(directory, "exact-state.f32", exact.field, files)
    exact_encoded = exact_probe.encoded_target
    if exact_encoded is None:
        raise AssertionError("exact fixture probe has no encoded target")
    _write_array(
        directory,
        "exact-probe.f32",
        np.stack((np.real(exact_encoded), np.imag(exact_encoded)), axis=-1),
        files,
    )

    serialization_inputs = np.zeros((4, 200), dtype=np.float32)
    serialization_inputs[1, 0] = 0.1
    serialization_inputs[2, 0] = 1.0
    serialization_inputs[3, 0] = 100.0
    serialization_encoded = np.stack(
        [field.bounded_serialize(row, 512) for row in serialization_inputs],
        axis=0,
    )
    _write_array(directory, "serialization-inputs.f32", serialization_inputs, files)
    _write_array(
        directory,
        "serialization-encoded.f32",
        np.stack((np.real(serialization_encoded), np.imag(serialization_encoded)), axis=-1),
        files,
    )

    manifest = {
        "schema": "cassi.apprentice.fixtures.v1",
        "profile": PROFILE_ID,
        "field_layout": LAYOUT_ID,
        "profile_sha256": profile_sha256(geometry),
        "geometry": {
            "scales": SCALE_COUNT,
            "batch": BATCH_COUNT,
            "modes": geometry.modes,
            "field_bytes": geometry.field_bytes,
            "pages": [
                {
                    "kind": page.kind,
                    "layer": page.layer,
                    "width": page.width,
                    "mode_offset": page.mode_offset,
                    "entries": page.entries,
                }
                for page in geometry.pages
            ],
        },
        "cases": {
            "sense_events": int(sense_events.size),
            "exact_byte": 73,
            "exact_observations": 2,
            "serialization_lengths": [200, 200, 200, 200],
        },
        "files": files,
    }
    manifest_path = directory / "cases.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-fixtures", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    output: dict[str, object] = {}
    if args.write_fixtures is not None:
        output["fixtures"] = write_fixtures(args.write_fixtures)
    if args.self_test or args.write_fixtures is None:
        output["self_test"] = run_self_test()
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
