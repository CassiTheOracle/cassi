"""Bounded direct reader for Qwen4Exp PLE n-gram embeddings.

The table remains on its immutable GGUF shard. A lookup reads and dequantizes
only the 16 selected Q5_0 rows; no table-sized mapping or allocation is made.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import struct
from collections.abc import Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any, BinaryIO, Mapping

import numpy as np

from .gguf import (
    _GGML_TYPES,
    _MAGIC,
    _MAX_ARRAY_ITEMS,
    _MAX_DIMS,
    _MAX_METADATA_ITEMS,
    _MAX_STRING_BYTES,
    _MAX_TENSORS,
    _SCALARS,
    _VALUE_TYPES,
    _read_exact,
    _string,
    _u32,
    _u64,
    _value,
)
from .tokenizer import GGUFTokenizer, TokenizerError


class Qwen4NgramTableError(ValueError):
    """The GGUF source or Qwen4 PLE layout is invalid or has changed."""


_U64_MASK = (1 << 64) - 1
_Q5_0_BLOCK_VALUES = 32
_Q5_0_BLOCK_BYTES = 22  # fp16 scale (2) + 32 high bits (4) + 32 low nibbles (16)
_QWEN4_ARCHITECTURE = "qwen4exp"
_PLE_PREFIX = "qwen4exp.ple."
_TABLE_NAME = "per_layer_token_embd.weight"
_TABLE_TYPE_ID = 6  # GGML_TYPE_Q5_0
_TABLE_WIDTH = 160
_TABLE_ROWS = 320_001_536
_HASH_SCHEMA = "qwen4exp.ple.u64-multiply-xor-mod.v1"
_SPLIT_NAME = re.compile(r"(?P<prefix>.+)-(?P<index>\d{5})-of-(?P<count>\d{5})(?P<suffix>\.gguf)", re.IGNORECASE)

_METADATA_KEYS = {
    "general.architecture",
    "general.alignment",
    "split.no",
    "split.count",
    "split.tensors.count",
    "tokenizer.ggml.model",
    "tokenizer.ggml.pre",
    "qwen4exp.block_count",
    "qwen4exp.embedding_length_per_layer_input",
    "qwen4exp.ple.layers",
    "qwen4exp.ple.ngram_size",
    "qwen4exp.ple.heads_per_ngram",
    "qwen4exp.ple.eos_token_id",
    "qwen4exp.ple.layer_multipliers",
    "qwen4exp.ple.head_offsets",
    "qwen4exp.ple.head_vocab_sizes",
}


def _fingerprint(path: Path) -> tuple[int, int, int, int, int]:
    try:
        stat = path.stat()
    except OSError as exc:
        raise Qwen4NgramTableError(f"GGUF shard is unavailable: {path}") from exc
    if not path.is_file():
        raise Qwen4NgramTableError(f"GGUF shard is not a regular file: {path}")
    return (
        int(stat.st_size),
        int(stat.st_mtime_ns),
        int(getattr(stat, "st_ctime_ns", 0)),
        int(getattr(stat, "st_ino", 0)),
        int(getattr(stat, "st_dev", 0)),
    )


def _skip_bytes(stream: BinaryIO, size: int, file_size: int) -> None:
    if size < 0 or stream.tell() + size > file_size:
        raise Qwen4NgramTableError("GGUF metadata value extends beyond its shard")
    stream.seek(size, os.SEEK_CUR)


def _skip_value(stream: BinaryIO, value_type: int, file_size: int) -> None:
    """Skip an unneeded metadata value without materializing large arrays."""
    if value_type in _SCALARS:
        _skip_bytes(stream, _SCALARS[value_type].size, file_size)
        return
    if value_type == 8:
        length = _u64(stream)
        if length > _MAX_STRING_BYTES:
            raise Qwen4NgramTableError("GGUF metadata string exceeds its bound")
        _skip_bytes(stream, length, file_size)
        return
    if value_type != 9:
        raise Qwen4NgramTableError(f"GGUF metadata type {value_type} is unsupported")

    item_type = _u32(stream)
    count = _u64(stream)
    if item_type not in _VALUE_TYPES or item_type == 9 or count > _MAX_ARRAY_ITEMS:
        raise Qwen4NgramTableError("GGUF metadata array type or length is unsupported")
    if item_type in _SCALARS:
        _skip_bytes(stream, _SCALARS[item_type].size * count, file_size)
        return
    if item_type != 8:
        raise Qwen4NgramTableError("GGUF metadata array element type is unsupported")
    for _ in range(count):
        length = _u64(stream)
        if length > _MAX_STRING_BYTES:
            raise Qwen4NgramTableError("GGUF metadata array string exceeds its bound")
        _skip_bytes(stream, length, file_size)


def _read_shard(path: Path) -> dict[str, Any]:
    """Read bounded GGUF metadata and tensor descriptors, never tensor payloads."""
    fingerprint = _fingerprint(path)
    file_size = fingerprint[0]
    try:
        with path.open("rb") as stream:
            if _read_exact(stream, 4) != _MAGIC:
                raise Qwen4NgramTableError("GGUF magic is invalid")
            version = _u32(stream)
            if version not in {2, 3}:
                raise Qwen4NgramTableError(f"GGUF version {version} is unsupported")
            tensor_count = _u64(stream)
            metadata_count = _u64(stream)
            if tensor_count > _MAX_TENSORS or metadata_count > _MAX_METADATA_ITEMS:
                raise Qwen4NgramTableError("GGUF descriptor count exceeds its bound")

            metadata: dict[str, Any] = {}
            for _ in range(metadata_count):
                key = _string(stream)
                if not key or key in metadata:
                    raise Qwen4NgramTableError("GGUF metadata key is empty or duplicated")
                value_type = _u32(stream)
                if value_type not in _VALUE_TYPES:
                    raise Qwen4NgramTableError(f"GGUF metadata type {value_type} is unsupported")
                if key in _METADATA_KEYS:
                    metadata[key] = _value(stream, value_type)
                else:
                    _skip_value(stream, value_type, file_size)

            descriptors: list[tuple[str, tuple[int, ...], int, int]] = []
            names: set[str] = set()
            for _ in range(tensor_count):
                name = _string(stream)
                if not name or name in names:
                    raise Qwen4NgramTableError("GGUF tensor name is empty or duplicated")
                names.add(name)
                dimension_count = _u32(stream)
                if not 0 < dimension_count <= _MAX_DIMS:
                    raise Qwen4NgramTableError("GGUF tensor rank is outside its bound")
                dimensions = tuple(_u64(stream) for _ in range(dimension_count))
                if any(not extent for extent in dimensions) or math.prod(dimensions) >= 1 << 63:
                    raise Qwen4NgramTableError("GGUF tensor shape is outside its bound")
                type_id = _u32(stream)
                if type_id not in _GGML_TYPES:
                    raise Qwen4NgramTableError(f"GGML tensor type {type_id} is unsupported")
                relative_offset = _u64(stream)
                descriptors.append((name, dimensions, type_id, relative_offset))

            alignment = metadata.get("general.alignment", 32)
            if isinstance(alignment, bool) or not isinstance(alignment, int) or not 0 < alignment <= 1 << 20:
                raise Qwen4NgramTableError("GGUF alignment is invalid")
            descriptor_end = stream.tell()
            data_offset = ((descriptor_end + alignment - 1) // alignment) * alignment
            if data_offset > file_size:
                raise Qwen4NgramTableError("GGUF data section begins beyond the shard")

            ordered = sorted(descriptors, key=lambda item: item[3])
            relatives = [item[3] for item in ordered]
            if len(set(relatives)) != len(relatives):
                raise Qwen4NgramTableError("GGUF tensor offsets are duplicated")
            if any(offset >= file_size - data_offset for offset in relatives):
                raise Qwen4NgramTableError("GGUF tensor offset is outside its shard")

            # Bind the complete descriptor/header but deliberately do not hash or
            # touch the multi-gigabyte tensor payloads.
            stream.seek(0)
            descriptor_hash = hashlib.sha256()
            remaining = data_offset
            while remaining:
                chunk = stream.read(min(8 << 20, remaining))
                if not chunk:
                    raise Qwen4NgramTableError("GGUF descriptor changed or was truncated")
                descriptor_hash.update(chunk)
                remaining -= len(chunk)

        if _fingerprint(path) != fingerprint:
            raise Qwen4NgramTableError(f"GGUF shard changed while its descriptor was read: {path}")
        return {
            "path": path,
            "fingerprint": fingerprint,
            "version": int(version),
            "metadata": metadata,
            "descriptors": descriptors,
            "data_offset": int(data_offset),
            "descriptor_sha256": descriptor_hash.hexdigest(),
            "tensor_count": int(tensor_count),
        }
    except Qwen4NgramTableError:
        raise
    except (OSError, ValueError, struct.error) as exc:
        raise Qwen4NgramTableError(f"cannot read GGUF shard descriptor: {path}") from exc


def _integer(value: Any, key: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise Qwen4NgramTableError(f"GGUF metadata {key} must be an integer")
    return int(value)


def _integer_array(value: Any, key: str, expected_length: int) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) != expected_length:
        raise Qwen4NgramTableError(
            f"GGUF metadata {key} must contain exactly {expected_length} integers"
        )
    if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        raise Qwen4NgramTableError(f"GGUF metadata {key} contains a non-integer")
    return tuple(int(item) for item in value)


def _dequantize_q5_0_row(encoded: bytes, width: int) -> np.ndarray:
    if width % _Q5_0_BLOCK_VALUES:
        raise Qwen4NgramTableError("Q5_0 row width is not a multiple of 32")
    blocks = width // _Q5_0_BLOCK_VALUES
    if len(encoded) != blocks * _Q5_0_BLOCK_BYTES:
        raise Qwen4NgramTableError("Q5_0 row has an unexpected byte length")
    result = np.empty(width, dtype=np.float32)
    for block in range(blocks):
        base = block * _Q5_0_BLOCK_BYTES
        scale = float(np.frombuffer(encoded, dtype="<f2", count=1, offset=base)[0])
        high_bits = encoded[base + 2 : base + 6]
        low_nibbles = encoded[base + 6 : base + _Q5_0_BLOCK_BYTES]
        out = block * _Q5_0_BLOCK_VALUES
        for index in range(_Q5_0_BLOCK_VALUES // 2):
            high0 = (high_bits[index // 8] >> (index % 8)) & 1
            second = index + _Q5_0_BLOCK_VALUES // 2
            high1 = (high_bits[second // 8] >> (second % 8)) & 1
            q0 = (low_nibbles[index] & 0x0F) | (high0 << 4)
            q1 = (low_nibbles[index] >> 4) | (high1 << 4)
            result[out + index] = (q0 - 16) * scale
            result[out + second] = (q1 - 16) * scale
    return result


class Qwen4NgramTable:
    """Directly read the local three-shard Qwen3.8/Qwen4Exp PLE Q5_0 table."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        source = Path(path).expanduser().resolve(strict=True)
        match = _SPLIT_NAME.fullmatch(source.name)
        if match is None or match.group("index") != "00001" or match.group("count") != "00003":
            raise Qwen4NgramTableError(
                "path must name shard 00001-of-00003 of a split Qwen4 GGUF"
            )
        prefix = match.group("prefix")
        suffix = match.group("suffix")
        shard_paths = tuple(
            source.with_name(f"{prefix}-{index:05d}-of-00003{suffix}")
            for index in range(1, 4)
        )
        before = tuple(_fingerprint(shard) for shard in shard_paths)

        try:
            tokenizer = GGUFTokenizer(source)
        except (OSError, TokenizerError, ValueError) as exc:
            raise Qwen4NgramTableError(f"cannot load the GGUF tokenizer: {source}") from exc
        shards = tuple(_read_shard(shard) for shard in shard_paths)
        after = tuple(_fingerprint(shard) for shard in shard_paths)
        if before != after or after != tuple(item["fingerprint"] for item in shards):
            raise Qwen4NgramTableError("GGUF split changed while it was being inspected")

        shared_metadata = shards[0]["metadata"]
        if shared_metadata.get("general.architecture") != _QWEN4_ARCHITECTURE:
            raise Qwen4NgramTableError("GGUF architecture is not qwen4exp")
        for key in ("split.count", "split.tensors.count"):
            if key not in shared_metadata:
                raise Qwen4NgramTableError(f"GGUF split metadata {key} is missing")
        if _integer(shared_metadata["split.count"], "split.count") != 3:
            raise Qwen4NgramTableError("GGUF split.count must be three")
        expected_tensor_count = _integer(shared_metadata["split.tensors.count"], "split.tensors.count")
        if expected_tensor_count <= 0 or expected_tensor_count != sum(item["tensor_count"] for item in shards):
            raise Qwen4NgramTableError("GGUF split tensor count does not match the three shards")

        found_table: list[tuple[dict[str, Any], tuple[str, tuple[int, ...], int, int]]] = []
        names: set[str] = set()
        for shard_no, shard in enumerate(shards):
            metadata = shard["metadata"]
            if _integer(metadata.get("split.no"), "split.no") != shard_no:
                raise Qwen4NgramTableError("GGUF shard split.no values are missing, duplicated, or unordered")
            if _integer(metadata.get("split.count"), "split.count") != 3:
                raise Qwen4NgramTableError("GGUF shard split.count values disagree")
            if _integer(metadata.get("split.tensors.count"), "split.tensors.count") != expected_tensor_count:
                raise Qwen4NgramTableError("GGUF shards disagree on split tensor count")
            for key in _METADATA_KEYS - {"split.no"}:
                if key in metadata and metadata[key] != shared_metadata.get(key):
                    raise Qwen4NgramTableError("GGUF split shards disagree on shared model metadata")
            for descriptor in shard["descriptors"]:
                if descriptor[0] in names:
                    raise Qwen4NgramTableError("GGUF tensor name occurs in more than one shard")
                names.add(descriptor[0])
                if descriptor[0] == _TABLE_NAME:
                    found_table.append((shard, descriptor))
        if len(found_table) != 1 or found_table[0][0] is not shards[0]:
            raise Qwen4NgramTableError("the PLE tensor must occur exactly once in shard 00001")

        if shared_metadata.get("tokenizer.ggml.model") != "gpt2" or shared_metadata.get("tokenizer.ggml.pre") != "qwen35":
            raise Qwen4NgramTableError("GGUF tokenizer metadata is not the supported Qwen byte-BPE layout")
        if tokenizer.model != "gpt2":
            raise Qwen4NgramTableError("GGUF tokenizer does not use the supported GPT-2 byte-BPE model")
        if _integer(shared_metadata.get("qwen4exp.embedding_length_per_layer_input"), "qwen4exp.embedding_length_per_layer_input") != _TABLE_WIDTH:
            raise Qwen4NgramTableError("Qwen4 PLE row width is unsupported")
        block_count = _integer(shared_metadata.get("qwen4exp.block_count"), "qwen4exp.block_count")
        layers = shared_metadata.get("qwen4exp.ple.layers")
        if (
            not isinstance(layers, list)
            or len(layers) != 1
            or isinstance(layers[0], bool)
            or not isinstance(layers[0], int)
            or not 0 <= layers[0] < block_count
        ):
            raise Qwen4NgramTableError("Qwen4 PLE layer metadata is missing or unsupported")
        ngram_size = _integer(shared_metadata.get("qwen4exp.ple.ngram_size"), "qwen4exp.ple.ngram_size")
        heads_per_ngram = _integer(shared_metadata.get("qwen4exp.ple.heads_per_ngram"), "qwen4exp.ple.heads_per_ngram")
        if ngram_size != 3 or heads_per_ngram != 8:
            raise Qwen4NgramTableError("only Qwen4 PLE with 2- and 3-gram groups of eight heads is supported")
        eos_id = _integer(shared_metadata.get("qwen4exp.ple.eos_token_id"), "qwen4exp.ple.eos_token_id")
        if not 0 <= eos_id < len(tokenizer.tokens):
            raise Qwen4NgramTableError("Qwen4 PLE EOS token is outside the GGUF tokenizer vocabulary")
        multipliers = _integer_array(
            shared_metadata.get("qwen4exp.ple.layer_multipliers"),
            "qwen4exp.ple.layer_multipliers",
            ngram_size,
        )
        if any(value == 0 or value < -(1 << 63) or value > _U64_MASK for value in multipliers):
            raise Qwen4NgramTableError("Qwen4 PLE hash multipliers are outside uint64 range")
        multipliers = tuple(value & _U64_MASK for value in multipliers)
        offsets = _integer_array(
            shared_metadata.get("qwen4exp.ple.head_offsets"),
            "qwen4exp.ple.head_offsets",
            16,
        )
        vocab_sizes = _integer_array(
            shared_metadata.get("qwen4exp.ple.head_vocab_sizes"),
            "qwen4exp.ple.head_vocab_sizes",
            16,
        )
        next_offset = 0
        for head_offset, vocab_size in zip(offsets, vocab_sizes, strict=True):
            if (
                head_offset != next_offset
                or vocab_size <= 0
                or head_offset > (1 << 31) - 1
                or vocab_size > (1 << 31) - 1
            ):
                raise Qwen4NgramTableError("Qwen4 PLE head ranges are invalid or non-contiguous")
            next_offset += vocab_size
        if not 0 < next_offset <= _TABLE_ROWS:
            raise Qwen4NgramTableError("Qwen4 PLE head ranges are empty or exceed the table")

        table_shard, table_descriptor = found_table[0]
        _, dimensions, type_id, relative_offset = table_descriptor
        if dimensions != (_TABLE_WIDTH, _TABLE_ROWS) or type_id != _TABLE_TYPE_ID:
            raise Qwen4NgramTableError("PLE tensor is not the expected 160-by-320001536 Q5_0 table")
        row_bytes = (_TABLE_WIDTH // _Q5_0_BLOCK_VALUES) * _Q5_0_BLOCK_BYTES
        table_bytes = _TABLE_ROWS * row_bytes
        table_end = relative_offset + table_bytes
        ordered = sorted(table_shard["descriptors"], key=lambda item: item[3])
        descriptor_index = next(index for index, item in enumerate(ordered) if item[0] == _TABLE_NAME)
        next_tensor_offset = (
            ordered[descriptor_index + 1][3]
            if descriptor_index + 1 < len(ordered)
            else table_shard["fingerprint"][0] - table_shard["data_offset"]
        )
        if (
            relative_offset < 0
            or table_end > next_tensor_offset
            or table_shard["data_offset"] + table_end > table_shard["fingerprint"][0]
        ):
            raise Qwen4NgramTableError("PLE Q5_0 tensor bytes are truncated or overlap another tensor")

        if _fingerprint(source) != before[0]:
            raise Qwen4NgramTableError("GGUF source changed while tokenizer metadata was read")
        descriptor_digest = hashlib.sha256(
            b"".join(bytes.fromhex(shard["descriptor_sha256"]) for shard in shards)
        ).hexdigest()
        file_stats = tuple(
            (
                str(shard_path),
                int(fingerprint[0]),
                int(fingerprint[1]),
                int(fingerprint[2]),
                int(fingerprint[3]),
                int(fingerprint[4]),
            )
            for shard_path, fingerprint in zip(shard_paths, before, strict=True)
        )
        identity_data: dict[str, Any] = {
            "schema": "cassifi.qwen4-ngram-source.v1",
            "source_id": source.name,
            "source_path": str(source),
            "descriptor_sha256": descriptor_digest,
            "tokenizer_metadata_sha256": str(tokenizer.provenance["tokenizer_metadata_sha256"]),
            "file_stats": file_stats,
            "hash_schema": _HASH_SCHEMA,
            "table_name": _TABLE_NAME,
            "table_type": "q5_0",
            "table_shape": dimensions,
            "table_absolute_offset": table_shard["data_offset"] + relative_offset,
            "table_byte_length": table_bytes,
            "addressable_rows": next_offset,
            "row_byte_length": row_bytes,
        }
        identity_digest = hashlib.sha256(
            json.dumps(identity_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        identity_data["sha256"] = identity_digest

        self.model_path = source
        self.tokenizer = tokenizer
        self.identity: Mapping[str, Any] = MappingProxyType(identity_data)
        self.table_id = identity_digest
        self._shard_paths = shard_paths
        self._fingerprints = before
        self._table_path = source
        self._table_base = table_shard["data_offset"] + relative_offset
        self._row_bytes = row_bytes
        self._width = _TABLE_WIDTH
        self._rows = next_offset
        self._eos_id = eos_id
        self._multipliers = multipliers
        self._offsets = offsets
        self._vocab_sizes = vocab_sizes

    def _assert_source_stable(self) -> None:
        current = tuple(_fingerprint(path) for path in self._shard_paths)
        if current != self._fingerprints:
            raise Qwen4NgramTableError("GGUF source split changed after table initialization")

    def lookup(self, token_ids: Sequence[int]) -> tuple[np.ndarray, tuple[int, ...]]:
        """Return the final prefix token's 16 addressed rows as float32."""
        if isinstance(token_ids, (str, bytes, bytearray)) or not isinstance(token_ids, Sequence):
            raise Qwen4NgramTableError("token_ids must be a sequence of integer token ids")
        length = len(token_ids)
        if length == 0:
            raise Qwen4NgramTableError("token_ids must contain the current token")

        token_count = len(self.tokenizer.tokens)
        context: list[int] = []
        first = max(0, length - 3)
        for index in range(length - 1, first - 1, -1):
            token_id = token_ids[index]
            if isinstance(token_id, bool) or not isinstance(token_id, (int, np.integer)):
                raise Qwen4NgramTableError("token_ids contains a non-integer token id")
            value = int(token_id)
            if not 0 <= value < token_count:
                raise Qwen4NgramTableError(f"token id {value} is outside the GGUF vocabulary")
            context.append(value)
        current = context[0]

        # The upstream PLE input fills absent history with EOS and cuts the
        # context at the nearest earlier EOS. The current token itself does not
        # reset its own n-gram context.
        previous: list[int] = []
        cut = False
        for distance in range(1, 3):
            if cut or distance >= len(context):
                previous.append(self._eos_id)
                cut = True
                continue
            token = context[distance]
            if token == self._eos_id:
                previous.append(self._eos_id)
                cut = True
            else:
                previous.append(token)

        values = (current, previous[0], previous[1])
        mixed_by_ngram: list[int] = []
        for ngram in (2, 3):
            mixed = (values[0] * self._multipliers[0]) & _U64_MASK
            for position in range(1, ngram):
                mixed ^= (values[position] * self._multipliers[position]) & _U64_MASK
            mixed_by_ngram.append(mixed)

        row_ids = [0] * 16
        for ngram_index, mixed in enumerate(mixed_by_ngram):
            base = ngram_index * 8
            for head in range(8):
                head_index = base + head
                row_ids[head_index] = (
                    mixed % self._vocab_sizes[head_index] + self._offsets[head_index]
                )
        if any(row_id < 0 or row_id >= self._rows for row_id in row_ids):
            raise Qwen4NgramTableError("Qwen4 PLE hash resolved outside the table")

        self._assert_source_stable()
        output = np.empty(16 * self._width, dtype=np.float32)
        try:
            with self._table_path.open("rb") as stream:
                for index, row_id in enumerate(row_ids):
                    stream.seek(self._table_base + row_id * self._row_bytes)
                    encoded = stream.read(self._row_bytes)
                    if len(encoded) != self._row_bytes:
                        raise Qwen4NgramTableError(f"Qwen4 PLE row {row_id} is missing or truncated")
                    start = index * self._width
                    output[start : start + self._width] = _dequantize_q5_0_row(encoded, self._width)
        except OSError as exc:
            raise Qwen4NgramTableError(f"cannot read Qwen4 PLE row data from {self._table_path}") from exc
        self._assert_source_stable()
        return output, tuple(row_ids)


__all__ = ["Qwen4NgramTable", "Qwen4NgramTableError"]
