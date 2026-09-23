"""Bounded GGUF inspection and immutable model-package import.

The importer reads GGUF metadata and tensor descriptors without materialising
weights.  Every tensor view is bound to the exact bytes of its file region and
the package records the tokenizer and source identities independently.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import struct
import threading
from typing import Any, BinaryIO, Mapping, Sequence

from programs.python.records import canonical_json_bytes, digest_value

from .records import ModelPackage, ModelRecordError, build_model_package


GGUF_MANIFEST_SCHEMA = "cassifi.gguf-manifest.v1"
GGUF_BACKING_SCHEMA = "cassifi.gguf-region.v1"
GGUF_TOKENIZER_SCHEMA = "cassifi.gguf-tokenizer.v1"
_MAGIC = b"GGUF"
_MAX_STRING_BYTES = 256 << 20
_MAX_ARRAY_ITEMS = 4_000_000
_MAX_METADATA_ITEMS = 1_000_000
_MAX_TENSORS = 1_000_000
_MAX_DIMS = 8
_VERIFIED_MANIFEST_LIMIT = 32
_VERIFIED_MANIFESTS: dict[str, tuple[str, int, int, int]] = {}
_VERIFIED_MANIFESTS_LOCK = threading.Lock()

_VALUE_TYPES = {
    0: "u8",
    1: "i8",
    2: "u16",
    3: "i16",
    4: "u32",
    5: "i32",
    6: "f32",
    7: "bool",
    8: "string",
    9: "array",
    10: "u64",
    11: "i64",
    12: "f64",
}
_SCALARS: Mapping[int, struct.Struct] = {
    0: struct.Struct("<B"),
    1: struct.Struct("<b"),
    2: struct.Struct("<H"),
    3: struct.Struct("<h"),
    4: struct.Struct("<I"),
    5: struct.Struct("<i"),
    6: struct.Struct("<f"),
    7: struct.Struct("<B"),
    10: struct.Struct("<Q"),
    11: struct.Struct("<q"),
    12: struct.Struct("<d"),
}
_GGML_TYPES = {
    0: "f32",
    1: "f16",
    2: "q4_0",
    3: "q4_1",
    6: "q5_0",
    7: "q5_1",
    8: "q8_0",
    9: "q8_1",
    10: "q2_k",
    11: "q3_k",
    12: "q4_k",
    13: "q5_k",
    14: "q6_k",
    15: "q8_k",
    16: "iq2_xxs",
    17: "iq2_xs",
    18: "iq3_xxs",
    19: "iq1_s",
    20: "iq4_nl",
    21: "iq3_s",
    22: "iq2_s",
    23: "iq4_xs",
    24: "i8",
    25: "i16",
    26: "i32",
    27: "i64",
    28: "f64",
    29: "iq1_m",
    30: "bf16",
    34: "tq1_0",
    35: "tq2_0",
    39: "mxfp4",
    40: "nvfp4",
    41: "q1_0",
    42: "q2_0",
}
_TOKENIZER_KEYS = {
    "tokenizer.ggml.model",
    "tokenizer.ggml.pre",
    "tokenizer.ggml.tokens",
    "tokenizer.ggml.scores",
    "tokenizer.ggml.token_type",
    "tokenizer.ggml.merges",
    "tokenizer.ggml.added_tokens",
    "tokenizer.ggml.bos_token_id",
    "tokenizer.ggml.eos_token_id",
    "tokenizer.ggml.unknown_token_id",
    "tokenizer.ggml.padding_token_id",
    "tokenizer.ggml.add_bos_token",
    "tokenizer.ggml.add_eos_token",
    "tokenizer.chat_template",
}
_RETAINED_METADATA_KEYS = {
    "general.architecture",
    "general.name",
    "general.basename",
    "general.size_label",
    "general.file_type",
    "general.quantization_version",
    "general.alignment",
}


class GgufImportError(ModelRecordError):
    """The GGUF container is malformed, unsupported, or changed while read."""


def _metadata_int(metadata: Mapping[str, Any], architecture: str, suffix: str) -> int | None:
    """Read one architecture-scoped integer without inventing model dimensions."""
    for key in (
        f"{architecture}.{suffix}",
        f"{architecture.replace('moe', '')}.{suffix}",
        f"qwen35.{suffix}",
        f"general.{suffix}",
    ):
        value = metadata.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value > 0:
            return value
    return None


def _tensor_name(tensor_names: set[str], *candidates: str) -> str | None:
    for candidate in candidates:
        if candidate in tensor_names:
            return candidate
    return None


def _qwen_graph(
    *,
    architecture: str,
    metadata: Mapping[str, Any],
    tensors: Sequence[Mapping[str, Any]],
    source_id: str,
    source_sha256: str,
    manifest_sha256: str,
) -> list[Mapping[str, Any]]:
    """Lower Qwen35/Qwen35MoE into one scheduler-visible stage per operation.

    The executor receives tensor names and immutable GGUF identity, not a
    serialized llama graph.  Names are resolved against the manifest so dense
    and MoE variants can share the stage contract.
    """
    tensor_names = {str(item["name"]) for item in tensors}
    layer_ids: set[int] = set()
    for name in tensor_names:
        if name.startswith("blk.") and "." in name[4:]:
            try:
                layer_ids.add(int(name[4:].split(".", 1)[0]))
            except ValueError:
                pass
    layer_count = _metadata_int(metadata, architecture, "block_count")
    if layer_count is None:
        layer_count = (max(layer_ids) + 1) if layer_ids else 0
    if layer_count <= 0:
        raise GgufImportError("Qwen GGUF does not declare any transformer layers")

    def names_for_layer(layer: int, *, moe: bool) -> dict[str, Any]:
        prefix = f"blk.{layer}."
        result: dict[str, Any] = {}
        candidates = {
            "attn_norm": (f"{prefix}attn_norm.weight",),
            "q": (f"{prefix}attn_q.weight", f"{prefix}attn_qkv.weight"),
            "k": (f"{prefix}attn_k.weight",),
            "v": (f"{prefix}attn_v.weight",),
            "q_norm": (f"{prefix}attn_q_norm.weight",),
            "k_norm": (f"{prefix}attn_k_norm.weight",),
            "attn_output": (f"{prefix}attn_output.weight",),
            "attn_gate": (f"{prefix}attn_gate.weight",),
            "ssm_a": (f"{prefix}ssm_a", f"{prefix}ssm_a.weight"),
            "ssm_alpha": (f"{prefix}ssm_alpha.weight",),
            "ssm_beta": (f"{prefix}ssm_beta.weight",),
            "ssm_conv1d": (f"{prefix}ssm_conv1d.weight",),
            "ssm_dt": (f"{prefix}ssm_dt.bias", f"{prefix}ssm_dt"),
            "ssm_norm": (f"{prefix}ssm_norm.weight",),
            "ssm_out": (f"{prefix}ssm_out.weight",),
            "ffn_norm": (f"{prefix}ffn_norm.weight", f"{prefix}post_attention_norm.weight"),
            "ffn_gate": (f"{prefix}ffn_gate.weight",),
            "ffn_down": (f"{prefix}ffn_down.weight",),
            "ffn_up": (f"{prefix}ffn_up.weight",),
            "ffn_gate_inp": (f"{prefix}ffn_gate_inp.weight",),
            "ffn_gate_exps": (f"{prefix}ffn_gate_exps.weight",),
            "ffn_down_exps": (f"{prefix}ffn_down_exps.weight",),
            "ffn_up_exps": (f"{prefix}ffn_up_exps.weight",),
        }
        for key, options in candidates.items():
            found = _tensor_name(tensor_names, *options)
            if found is not None:
                result[key] = found
        recurrent = "attn_output" not in result and "ssm_out" in result
        required = ("attn_norm", "q", "ffn_norm")
        missing = [key for key in required if key not in result]
        if recurrent:
            missing.extend(key for key in ("attn_gate", "ssm_out") if key not in result)
        elif "attn_output" not in result:
            missing.append("attn_output")
        fused = result.get("q", "").endswith("attn_qkv.weight")
        if not recurrent and ("k" not in result or "v" not in result) and not fused:
            missing.extend(key for key in ("k", "v") if key not in result)
        if missing:
            raise GgufImportError(
                f"Qwen layer {layer} is missing required tensors: {', '.join(sorted(set(missing)))}"
            )
        ffn_required = ("ffn_gate", "ffn_down", "ffn_up")
        if not moe and not all(key in result for key in ffn_required):
            raise GgufImportError(f"Qwen dense layer {layer} is missing FFN tensors")
        if moe and not all(
            key in result for key in ("ffn_gate_inp", "ffn_gate_exps", "ffn_down_exps", "ffn_up_exps")
        ):
            raise GgufImportError(f"Qwen MoE layer {layer} is missing expert tensors")
        result["recurrent"] = recurrent
        return result
    embedding = _tensor_name(tensor_names, "token_embd.weight")
    head = _tensor_name(tensor_names, "output.weight") or embedding
    output_norm = _tensor_name(tensor_names, "output_norm.weight")
    if embedding is None or head is None or output_norm is None:
        raise GgufImportError("Qwen GGUF is missing embedding or output norm tensors")
    moe = architecture.lower().replace(".", "") == "qwen35moe" or any(
        name.endswith(".ffn_gate_inp.weight") for name in tensor_names
    )
    common = {
        "source_id": source_id,
        "source_sha256": source_sha256,
        "manifest_sha256": manifest_sha256,
        "architecture": architecture,
        "metadata_sha256": digest_value(metadata),
    }
    graph: list[Mapping[str, Any]] = [
        {
            "operation_id": "qwen-embedding",
            "stage": "qwen-embedding",
            "op": "qwen-embedding",
            "inputs": [],
            "output": None,
            "parameters": {**common, "tensor_names": {"embedding": embedding}},
            "state_effects": ["resident-token-embedding", "resident-snapshot"],
        }
    ]
    for layer in range(layer_count):
        layer_names = names_for_layer(layer, moe=moe)
        recurrent = bool(layer_names.pop("recurrent", False))
        if moe:
            graph.append(
                {
                    "operation_id": f"qwen-attention-route-{layer}",
                    "stage": "qwen-attention-route",
                    "op": "qwen-attention-route",
                    "inputs": [],
                    "output": None,
                    "parameters": {
                        **common,
                        "layer": layer,
                        "recurrent": recurrent,
                        "route_only": True,
                        "expert": -1,
                        "tensor_names": layer_names,
                    },
                    "state_effects": [
                        "resident-attention-memory",
                        "resident-expert-route",
                        "resident-snapshot",
                    ],
                }
            )
            graph.append(
                {
                    "operation_id": f"qwen-experts-{layer}",
                    "stage": "qwen-experts",
                    "op": "qwen-experts",
                    "inputs": [],
                    "output": None,
                    "parameters": {
                        **common,
                        "layer": layer,
                        "expert": -1,
                        "tensor_names": layer_names,
                    },
                    "state_effects": [
                        "resident-expert-compute",
                        "resident-snapshot",
                    ],
                }
            )
        else:
            graph.append(
                {
                    "operation_id": f"qwen-layer-{layer}",
                    "stage": "qwen-layer",
                    "op": "qwen-layer",
                    "inputs": [],
                    "output": None,
                    "parameters": {
                        **common,
                        "layer": layer,
                        "recurrent": recurrent,
                        "expert": -1,
                        "tensor_names": layer_names,
                    },
                    "state_effects": [
                        "resident-attention-memory",
                        "resident-ffn-memory",
                        "resident-snapshot",
                    ],
                }
            )
    graph.append(
        {
            "operation_id": "qwen-head",
            "stage": "qwen-head",
            "op": "qwen-head",
            "inputs": [],
            "output": None,
            "parameters": {
                **common,
                "layer": None,
                "tensor_names": {"output_norm": output_norm, "output": head},
            },
            "state_effects": ["resident-token-head", "resident-snapshot"],
        }
    )
    return graph

def _read_exact(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise GgufImportError("GGUF input is truncated")
    return data


def _u32(stream: BinaryIO) -> int:
    return struct.unpack("<I", _read_exact(stream, 4))[0]


def _u64(stream: BinaryIO) -> int:
    return struct.unpack("<Q", _read_exact(stream, 8))[0]


def _string(stream: BinaryIO) -> str:
    length = _u64(stream)
    if length > _MAX_STRING_BYTES:
        raise GgufImportError("GGUF string exceeds its bound")
    try:
        return _read_exact(stream, length).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GgufImportError("GGUF string is not UTF-8") from exc


def _value(stream: BinaryIO, value_type: int) -> Any:
    if value_type in _SCALARS:
        value = _SCALARS[value_type].unpack(_read_exact(stream, _SCALARS[value_type].size))[0]
        if value_type == 7:
            if value not in {0, 1}:
                raise GgufImportError("GGUF boolean is invalid")
            return bool(value)
        if isinstance(value, float) and not math.isfinite(value):
            raise GgufImportError("GGUF metadata contains a non-finite number")
        return value
    if value_type == 8:
        return _string(stream)
    if value_type == 9:
        item_type = _u32(stream)
        if item_type not in _VALUE_TYPES or item_type == 9:
            raise GgufImportError("GGUF array element type is unsupported")
        count = _u64(stream)
        if count > _MAX_ARRAY_ITEMS:
            raise GgufImportError("GGUF array exceeds its bound")
        return [_value(stream, item_type) for _ in range(count)]
    raise GgufImportError(f"GGUF metadata type {value_type} is unsupported")


def _hash_source_and_regions(
    path: Path,
    regions: list[tuple[str, int, int]],
) -> tuple[str, dict[str, str]]:
    source_hash = hashlib.sha256()
    region_hashes: dict[str, str] = {}
    region_index = 0
    region_hash = hashlib.sha256() if regions else None
    position = 0
    with path.open("rb") as stream:
        while chunk := stream.read(8 << 20):
            source_hash.update(chunk)
            local = 0
            while local < len(chunk) and region_index < len(regions):
                name, start, end = regions[region_index]
                absolute = position + local
                if absolute < start:
                    local += min(len(chunk) - local, start - absolute)
                    continue
                take = min(len(chunk) - local, end - absolute)
                if take <= 0:
                    raise GgufImportError("GGUF tensor regions overlap or are unordered")
                assert region_hash is not None
                region_hash.update(chunk[local : local + take])
                local += take
                if absolute + take == end:
                    region_hashes[name] = region_hash.hexdigest()
                    region_index += 1
                    region_hash = hashlib.sha256() if region_index < len(regions) else None
            position += len(chunk)
    if region_index != len(regions):
        raise GgufImportError("GGUF tensor data is truncated")
    return source_hash.hexdigest(), region_hashes


def _source_stat(path: Path) -> tuple[str, int, int, int]:
    try:
        stat = path.stat()
    except OSError as exc:
        raise GgufImportError("GGUF source is unavailable") from exc
    return (
        str(path),
        int(stat.st_size),
        int(stat.st_mtime_ns),
        int(getattr(stat, "st_ino", 0)),
    )


def _remember_verified_manifest(
    path: Path,
    manifest_sha256: str,
) -> None:
    fingerprint = _source_stat(path)
    with _VERIFIED_MANIFESTS_LOCK:
        if (
            manifest_sha256 not in _VERIFIED_MANIFESTS
            and len(_VERIFIED_MANIFESTS) >= _VERIFIED_MANIFEST_LIMIT
        ):
            _VERIFIED_MANIFESTS.pop(next(iter(_VERIFIED_MANIFESTS)))
        _VERIFIED_MANIFESTS[manifest_sha256] = fingerprint


def reuse_verified_manifest(
    path: str | Path,
    manifest: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Reuse a manifest only while its already-hashed source is unchanged."""

    source = Path(path).resolve(strict=True)
    if not source.is_file():
        raise GgufImportError("GGUF source is not a regular file")
    if not isinstance(manifest, Mapping):
        raise GgufImportError("GGUF manifest must be a mapping")
    if manifest.get("schema") != GGUF_MANIFEST_SCHEMA:
        raise GgufImportError("GGUF manifest schema is invalid")
    source_sha256 = manifest.get("source_sha256")
    if not isinstance(source_sha256, str) or len(source_sha256) != 64:
        raise GgufImportError("GGUF manifest source identity is invalid")
    fingerprint = _source_stat(source)
    if manifest.get("file_size") != fingerprint[1]:
        raise GgufImportError("GGUF manifest file size does not match its source")
    manifest_sha256 = digest_value(manifest)
    with _VERIFIED_MANIFESTS_LOCK:
        expected = _VERIFIED_MANIFESTS.get(manifest_sha256)
    if expected != fingerprint:
        raise GgufImportError(
            "GGUF manifest was not verified for the current source file state"
        )
    return manifest


def inspect_gguf(
    path: str | Path,
    *,
    source_id: str | None = None,
    expected_source_sha256: str | None = None,
) -> Mapping[str, Any]:
    """Return a canonical manifest bound to every byte of one GGUF file."""

    source = Path(path).resolve(strict=True)
    if not source.is_file():
        raise GgufImportError("GGUF source is not a regular file")
    source_fingerprint = _source_stat(source)
    file_size = source_fingerprint[1]
    metadata: dict[str, Any] = {}
    metadata_entries: list[dict[str, Any]] = []
    tensors: list[dict[str, Any]] = []
    tensor_names: set[str] = set()
    with source.open("rb") as stream:
        if _read_exact(stream, 4) != _MAGIC:
            raise GgufImportError("GGUF magic is invalid")
        version = _u32(stream)
        if version not in {2, 3}:
            raise GgufImportError(f"GGUF version {version} is unsupported")
        tensor_count = _u64(stream)
        metadata_count = _u64(stream)
        if tensor_count > _MAX_TENSORS or metadata_count > _MAX_METADATA_ITEMS:
            raise GgufImportError("GGUF descriptor count exceeds its bound")
        for _ in range(metadata_count):
            key = _string(stream)
            if not key or key in metadata:
                raise GgufImportError("GGUF metadata key is empty or duplicated")
            value_type = _u32(stream)
            if value_type not in _VALUE_TYPES:
                raise GgufImportError(f"GGUF metadata type {value_type} is unsupported")
            item = _value(stream, value_type)
            metadata[key] = item
            entry = {
                "key": key,
                "type": _VALUE_TYPES[value_type],
                "value_sha256": digest_value(item),
            }
            if isinstance(item, list):
                entry["length"] = len(item)
            metadata_entries.append(entry)
        for _ in range(tensor_count):
            name = _string(stream)
            if not name or name in tensor_names:
                raise GgufImportError("GGUF tensor name is empty or duplicated")
            tensor_names.add(name)
            dimension_count = _u32(stream)
            if not 0 < dimension_count <= _MAX_DIMS:
                raise GgufImportError("GGUF tensor rank is outside its bound")
            dimensions = [_u64(stream) for _ in range(dimension_count)]
            if any(not extent for extent in dimensions) or math.prod(dimensions) >= 1 << 63:
                raise GgufImportError("GGUF tensor shape is outside its bound")
            type_id = _u32(stream)
            if type_id not in _GGML_TYPES:
                raise GgufImportError(f"GGML tensor type {type_id} is unsupported")
            tensors.append(
                {
                    "name": name,
                    "ggml_type_id": type_id,
                    "dtype": _GGML_TYPES[type_id],
                    "gguf_dimensions": dimensions,
                    "shape": list(reversed(dimensions)),
                    "relative_offset": _u64(stream),
                }
            )
        alignment = metadata.get("general.alignment", 32)
        if isinstance(alignment, bool) or not isinstance(alignment, int) or alignment <= 0 or alignment > 1 << 20:
            raise GgufImportError("GGUF alignment is invalid")
        descriptor_end = stream.tell()
        data_offset = ((descriptor_end + alignment - 1) // alignment) * alignment
    ordered = sorted(tensors, key=lambda item: int(item["relative_offset"]))
    if len({int(item["relative_offset"]) for item in ordered}) != len(ordered):
        raise GgufImportError("GGUF tensor offsets are duplicated")
    regions: list[tuple[str, int, int]] = []
    for index, tensor in enumerate(ordered):
        start = data_offset + int(tensor["relative_offset"])
        end = data_offset + int(ordered[index + 1]["relative_offset"]) if index + 1 < len(ordered) else file_size
        if start < data_offset or end <= start or end > file_size:
            raise GgufImportError("GGUF tensor region is outside the source file")
        tensor["absolute_offset"] = start
        tensor["byte_length"] = end - start
        regions.append((str(tensor["name"]), start, end))
    source_sha256, region_hashes = _hash_source_and_regions(source, regions)
    if expected_source_sha256 is not None and source_sha256 != expected_source_sha256:
        raise GgufImportError("GGUF source digest does not match the expected identity")
    for tensor in tensors:
        tensor["region_sha256"] = region_hashes[str(tensor["name"])]
    tokenizer_entries = [entry for entry in metadata_entries if entry["key"] in _TOKENIZER_KEYS]
    tokens = metadata.get("tokenizer.ggml.tokens")
    merges = metadata.get("tokenizer.ggml.merges")
    tokenizer = {
        "schema": GGUF_TOKENIZER_SCHEMA,
        "source_sha256": source_sha256,
        "metadata_sha256": digest_value(tokenizer_entries),
        "model": metadata.get("tokenizer.ggml.model"),
        "pre": metadata.get("tokenizer.ggml.pre"),
        "token_count": len(tokens) if isinstance(tokens, list) else None,
        "merge_count": len(merges) if isinstance(merges, list) else None,
        "bos_token_id": metadata.get("tokenizer.ggml.bos_token_id"),
        "eos_token_id": metadata.get("tokenizer.ggml.eos_token_id"),
        "unknown_token_id": metadata.get("tokenizer.ggml.unknown_token_id"),
        "padding_token_id": metadata.get("tokenizer.ggml.padding_token_id"),
        "add_bos_token": metadata.get("tokenizer.ggml.add_bos_token"),
        "add_eos_token": metadata.get("tokenizer.ggml.add_eos_token"),
    }
    manifest = {
        "schema": GGUF_MANIFEST_SCHEMA,
        "version": version,
        "source_id": source_id or source.name,
        "source_sha256": source_sha256,
        "file_size": file_size,
        "descriptor_end": descriptor_end,
        "data_offset": data_offset,
        "alignment": alignment,
        "metadata_sha256": digest_value(metadata_entries),
        "metadata_entries": metadata_entries,
        "metadata": {key: metadata[key] for key in sorted(_RETAINED_METADATA_KEYS & metadata.keys())},
        "model_metadata": {key: metadata[key] for key in sorted(metadata)},
        "tokenizer": tokenizer,
        "tensors": sorted(tensors, key=lambda item: str(item["name"])),
    }
    manifest_sha256 = hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()
    if _source_stat(source) != source_fingerprint:
        raise GgufImportError("GGUF source changed while it was being inspected")
    _remember_verified_manifest(source, manifest_sha256)
    return manifest


def build_gguf_model_package(
    path: str | Path,
    *,
    program_id: str,
    owner_id: str = "shared-import",
    scope_id: str = "model",
    source_id: str | None = None,
    expected_source_sha256: str | None = None,
    execution: str = "resident-qwen",
    manifest: Mapping[str, Any] | None = None,
) -> ModelPackage:
    """Import an immutable GGUF into explicit resident Qwen stages.

    ``external-model`` is the only GGUF import mode that intentionally leaves
    execution to an explicitly selected external lane.
    """

    if execution not in {"resident-qwen", "external-model"}:
        raise GgufImportError("GGUF execution mode is unsupported; use resident-qwen or external-model")

    if manifest is None:
        manifest = inspect_gguf(
            path,
            source_id=source_id,
            expected_source_sha256=expected_source_sha256,
        )
    else:
        manifest = dict(reuse_verified_manifest(path, manifest))
        if (
            expected_source_sha256 is not None
            and manifest.get("source_sha256") != expected_source_sha256
        ):
            raise GgufImportError(
                "GGUF source digest does not match the expected identity"
            )
    architecture = manifest["metadata"].get("general.architecture")
    if not isinstance(architecture, str) or not architecture:
        raise GgufImportError("GGUF does not declare general.architecture")
    source_sha256 = str(manifest["source_sha256"])
    tensors: dict[str, Mapping[str, Any]] = {}
    for tensor in manifest["tensors"]:
        backing = {
            "schema": GGUF_BACKING_SCHEMA,
            "source_id": manifest["source_id"],
            "source_sha256": source_sha256,
            "offset": tensor["absolute_offset"],
            "byte_length": tensor["byte_length"],
            "region_sha256": tensor["region_sha256"],
        }
        tensors[str(tensor["name"])] = {
            "tensor_id": f"{source_sha256}:{tensor['name']}",
            "dtype": tensor["dtype"],
            "shape": tensor["shape"],
            "immutable": True,
            "backing_sha256": tensor["region_sha256"],
            "backing": backing,
            "quantization": {
                "schema": "cassifi.gguf-tensor-layout.v1",
                "ggml_type_id": tensor["ggml_type_id"],
                "ggml_type": tensor["dtype"],
                "gguf_dimensions": tensor["gguf_dimensions"],
            },
            "dependencies": [source_sha256],
            "placement": "immutable-gguf",
        }
    if execution == "external-model":
        graph = [
            {
                "operation_id": "external-model",
                "stage": "model",
                "op": "external-model",
                "inputs": [],
                "output": None,
                "parameters": {
                    "adapter": "field-brain",
                    "source_id": manifest["source_id"],
                    "source_sha256": source_sha256,
                    "manifest_sha256": digest_value(manifest),
                    "architecture": architecture,
                },
                "state_effects": ["external-model-continuation"],
            }
        ]
    else:
        normalized_architecture = architecture.lower().replace(".", "")
        if normalized_architecture not in {"qwen35moe", "qwen35"}:
            raise GgufImportError(
                f"resident GGUF architecture {architecture!r} has no explicit lowering"
            )
        graph = _qwen_graph(
            architecture=architecture,
            metadata=manifest["model_metadata"],
            tensors=manifest["tensors"],
            source_id=str(manifest["source_id"]),
            source_sha256=source_sha256,
            manifest_sha256=digest_value(manifest),
        )
        
    return build_model_package(
        program_id=program_id,
        architecture=architecture,
        graph=graph,
        tensors=tensors,
        tokenizer=manifest["tokenizer"],
        owner_id=owner_id,
        scope_id=scope_id,
        quantization_profile={
            "format": "gguf",
            "source_sha256": source_sha256,
            "tensor_count": len(tensors),
            "types": sorted({str(item["dtype"]) for item in manifest["tensors"]}),
        },
        operation_versions={
            str(operation["op"]): "resident-qwen-stage-v1"
            for operation in graph
        },
        assessment={
            "origin": "gguf-import",
            "status": "admitted",
            "source_sha256": source_sha256,
            "manifest_sha256": digest_value(manifest),
        },
        primitive_contracts=("immutable-gguf-v1", "model-continuation-v1"),
        numerical_profile={
            "arithmetic": "ggml-kernel-f32",
            "fast_math": False,
            "source_file_size": manifest["file_size"],
            "model_metadata": {
                key: value
                for key, value in manifest["model_metadata"].items()
                if not isinstance(value, (list, dict))
            },
            "tensor_manifest_sha256": digest_value(manifest["tensors"]),
        },
    )


__all__ = [
    "GGUF_BACKING_SCHEMA",
    "GGUF_MANIFEST_SCHEMA",
    "GGUF_TOKENIZER_SCHEMA",
    "GgufImportError",
    "build_gguf_model_package",
    "inspect_gguf",
]
