from __future__ import annotations

"""Deterministic, bounded source views for the resident cognition field."""

import ast
import base64
import hashlib
import json
import math
import operator
import struct
from collections import OrderedDict
from functools import reduce
from threading import RLock
from types import SimpleNamespace
from typing import Any, Mapping, Sequence


_DECODE_CACHE_MAX_BYTES = 4 * 1024 * 1024
_DECODE_CACHE_MAX_ENTRY_BYTES = 512 * 1024
_DECODE_CACHE_MAX_ENTRIES = 64
_decode_cache: OrderedDict[
    tuple[Any, ...],
    tuple[list[tuple[tuple[str | int, ...], dict[str, Any]]], str, tuple[int, ...], int],
] = OrderedDict()
_decode_cache_bytes = 0
_decode_cache_lock = RLock()


SOURCE_VIEW_SCHEMA = "cassifi.source-observation-page.v1"
CODEC_JSON = "cassi.codec.json-utf8.v1"
CODEC_RASTER = "cassi.codec.raster-u8-c.v1"
CODEC_TEXT = "cassi.codec.utf8.v1"
CODEC_CODE = "cassi.codec.python-utf8.v1"
CODEC_AUDIO = "cassi.codec.audio-f64le.v1"
CODEC_TENSOR = "cassi.codec.tensor-c.v1"
CODEC_OPAQUE = "cassi.codec.opaque-bytes.v1"
SUPPORTED_CODECS = frozenset(
    {
        CODEC_JSON,
        CODEC_RASTER,
        CODEC_TEXT,
        CODEC_CODE,
        CODEC_AUDIO,
        CODEC_TENSOR,
        CODEC_OPAQUE,
    }
)
_CODEC_MODALITY = {
    CODEC_JSON: "json",
    CODEC_RASTER: "raster",
    CODEC_TEXT: "text",
    CODEC_CODE: "code",
    CODEC_AUDIO: "audio",
    CODEC_TENSOR: "scientific_tensor",
    CODEC_OPAQUE: "opaque",
}
_UTF8_ALIASES = frozenset({"utf-8", "utf8"})
_OPAQUE_ALIASES = frozenset({"binary", "bytes", "opaque"})


def _decoder_codec(codec: str, media_type: str) -> str:
    if codec in SUPPORTED_CODECS:
        return codec
    normalized = codec.strip().lower()
    media = media_type.split(";", 1)[0].strip().lower()
    if normalized in _UTF8_ALIASES:
        if media == "application/json" or media.endswith("+json"):
            return CODEC_JSON
        if media in {
            "application/x-python",
            "text/x-python",
            "text/x-python-script",
        }:
            return CODEC_CODE
        return CODEC_TEXT
    if normalized in _OPAQUE_ALIASES:
        return CODEC_OPAQUE
    return codec
_DTYPE_FORMATS = {
    "bool8": ("?", 1),
    "f32le": ("<f", 4),
    "f64le": ("<d", 8),
    "i8": ("b", 1),
    "i16le": ("<h", 2),
    "i32le": ("<i", 4),
    "i64le": ("<q", 8),
    "u8": ("B", 1),
    "u16le": ("<H", 2),
    "u32le": ("<I", 4),
    "u64le": ("<Q", 8),
}
_MAX_PAGE_ITEMS = 256
_MAX_TEXT_ITEM_BYTES = 1024
_OPAQUE_ITEM_BYTES = 64


class SourceViewError(ValueError):
    """The requested fixed codec or page description is invalid."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SourceViewError("source view is not canonical JSON") from exc


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _integer(value: Any, name: str, *, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise SourceViewError(f"{name} must be an integer >= {minimum}")
    if maximum is not None and value > maximum:
        raise SourceViewError(f"{name} exceeds {maximum}")
    return value


def _shape(value: Sequence[int] | None) -> tuple[int, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise SourceViewError("shape must be a sequence of positive integers")
    shape = tuple(_integer(item, "shape dimension", minimum=1) for item in value)
    if len(shape) > 16:
        raise SourceViewError("shape exceeds sixteen dimensions")
    return shape


def _units(value: Sequence[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise SourceViewError("units must be a sequence")
    units = tuple(value)
    if len(units) > 16 or any(not isinstance(item, str) or len(item) > 128 for item in units):
        raise SourceViewError("units are invalid")
    return units


def _path_text(path: Sequence[str | int]) -> str:
    if not path:
        return "$"
    text = "$"
    for segment in path:
        if isinstance(segment, int):
            text += f"[{segment}]"
        else:
            text += "." + segment.replace("~", "~0").replace("/", "~1")
    return text


def _observation(
    *,
    revision_id: str,
    source_id: str,
    ordinal: int,
    path: Sequence[str | int],
    value: Mapping[str, Any],
    units: Sequence[str] = (),
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "attribute": _path_text(path),
        "binding_id": f"source:{revision_id[:24]}:{ordinal}",
        "epistemic_kind": "observed",
        "status": "active",
        "subject": source_id,
        "value": dict(value),
    }
    if units:
        row["units"] = (
            units[0] if len(units) == 1 else {"axes": list(units)}
        )
    return row


def _json_items(content: bytes) -> tuple[list[tuple[tuple[str | int, ...], dict[str, Any]]], str, tuple[int, ...]]:
    try:
        value = json.loads(
            content.decode("utf-8", errors="strict"),
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise SourceViewError("JSON source is not strict UTF-8 JSON") from exc
    items: list[tuple[tuple[str | int, ...], dict[str, Any]]] = []

    def visit(node: Any, path: tuple[str | int, ...]) -> None:
        if isinstance(node, dict):
            items.append((path, {"kind": "collection", "collection_type": "map", "size": len(node)}))
            for key in sorted(node):
                if not isinstance(key, str):
                    raise SourceViewError("JSON object key is not text")
                visit(node[key], (*path, key))
            return
        if isinstance(node, list):
            items.append((path, {"kind": "collection", "collection_type": "sequence", "size": len(node)}))
            for index, child in enumerate(node):
                visit(child, (*path, index))
            return
        primitive = (
            "null" if node is None else "bool" if isinstance(node, bool) else
            "int" if isinstance(node, int) else "float" if isinstance(node, float) else "utf8"
        )
        if isinstance(node, float) and not math.isfinite(node):
            raise SourceViewError("JSON source contains a non-finite number")
        items.append((path, {"kind": "atom", "primitive_type": primitive, "value": node}))

    visit(value, ())
    return items, "json", ()


def _text_items(content: bytes) -> tuple[list[tuple[tuple[str | int, ...], dict[str, Any]]], str, tuple[int, ...]]:
    try:
        content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SourceViewError("text source is not valid UTF-8") from exc
    items: list[tuple[tuple[str | int, ...], dict[str, Any]]] = []
    offset = 0
    ordinal = 0
    while offset < len(content):
        end = min(len(content), offset + _MAX_TEXT_ITEM_BYTES)
        if end < len(content):
            newline = content.rfind(b"\n", offset, end)
            if newline >= offset:
                end = newline + 1
            else:
                while end > offset and (content[end] & 0xC0) == 0x80:
                    end -= 1
                if end == offset:
                    end = min(len(content), offset + _MAX_TEXT_ITEM_BYTES + 4)
        chunk = content[offset:end]
        text = chunk.decode("utf-8", errors="strict")
        items.append(((ordinal,), {
            "kind": "atom",
            "primitive_type": "utf8",
            "source_span": [offset, end],
            "value": text,
        }))
        offset = end
        ordinal += 1
    if not items:
        items.append(((0,), {"kind": "atom", "primitive_type": "utf8", "source_span": [0, 0], "value": ""}))
    return items, "utf8", (len(content),)


def _code_items(content: bytes) -> tuple[list[tuple[tuple[str | int, ...], dict[str, Any]]], str, tuple[int, ...]]:
    try:
        text = content.decode("utf-8", errors="strict")
        tree = ast.parse(text)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise SourceViewError("Python source cannot be parsed") from exc
    line_offsets = [0]
    for line in content.splitlines(keepends=True):
        line_offsets.append(line_offsets[-1] + len(line))
    nodes: list[tuple[tuple[str | int, ...], dict[str, Any]]] = []
    stack: list[tuple[ast.AST, tuple[str | int, ...]]] = [(tree, ())]
    while stack:
        node, path = stack.pop()
        start = None
        end = None
        if hasattr(node, "lineno") and hasattr(node, "col_offset"):
            line = max(1, int(getattr(node, "lineno")))
            end_line = max(line, int(getattr(node, "end_lineno", line)))
            start = line_offsets[min(line - 1, len(line_offsets) - 1)] + int(getattr(node, "col_offset"))
            end = line_offsets[min(end_line - 1, len(line_offsets) - 1)] + int(getattr(node, "end_col_offset", 0))
            start = min(start, len(content))
            end = min(max(start, end), len(content))
        descriptor: dict[str, Any] = {"kind": "syntax", "node_type": type(node).__name__}
        for name in ("id", "name", "arg", "attr"):
            raw = getattr(node, name, None)
            if isinstance(raw, str):
                descriptor[name] = raw
        if isinstance(node, ast.Constant) and isinstance(
            node.value, (type(None), bool, int, float, str)
        ):
            if isinstance(node.value, float) and not math.isfinite(node.value):
                raise SourceViewError(
                    "Python source contains a non-finite numeric literal"
                )
            descriptor["literal"] = node.value
        if start is not None and end is not None:
            descriptor["source_span"] = [start, end]
        nodes.append((path, descriptor))
        children = list(ast.iter_child_nodes(node))
        for index in range(len(children) - 1, -1, -1):
            stack.append((children[index], (*path, index)))
    return nodes, "python-ast", ()


def _flat_index(index: int, shape: tuple[int, ...]) -> list[int]:
    coordinates = [0] * len(shape)
    for axis in range(len(shape) - 1, -1, -1):
        index, coordinates[axis] = divmod(index, shape[axis])
    return coordinates


def _numeric_items(
    content: bytes,
    *,
    codec: str,
    dtype: str | None,
    shape: tuple[int, ...],
    units: tuple[str, ...],
) -> tuple[list[tuple[tuple[str | int, ...], dict[str, Any]]], str, tuple[int, ...], str]:
    if codec == CODEC_RASTER:
        actual_dtype = "u8"
    elif codec == CODEC_AUDIO:
        actual_dtype = "f64le"
    else:
        actual_dtype = dtype or ""
    if actual_dtype not in _DTYPE_FORMATS:
        raise SourceViewError("numeric source dtype is unsupported")
    fmt, item_bytes = _DTYPE_FORMATS[actual_dtype]
    if len(content) % item_bytes:
        raise SourceViewError("numeric source byte length is not aligned to dtype")
    count = len(content) // item_bytes
    actual_shape = shape or (count,)
    expected = reduce(operator.mul, actual_shape, 1)
    if expected != count:
        raise SourceViewError("numeric source shape does not match its exact bytes")
    if codec == CODEC_RASTER and len(actual_shape) not in {2, 3}:
        raise SourceViewError("raster shape must be [height,width] or [height,width,channels]")
    if codec == CODEC_AUDIO and len(actual_shape) not in {1, 2}:
        raise SourceViewError("audio shape must be [frames] or [frames,channels]")
    items: list[tuple[tuple[str | int, ...], dict[str, Any]]] = []
    for index in range(count):
        value = struct.unpack_from(fmt, content, index * item_bytes)[0]
        if isinstance(value, float) and not math.isfinite(value):
            raise SourceViewError("numeric source contains a non-finite value")
        coordinates = _flat_index(index, actual_shape)
        items.append((tuple(coordinates), {
            "dtype": actual_dtype,
            "flat_index": index,
            "index": coordinates,
            "kind": "tensor-element",
            "source_span": [index * item_bytes, (index + 1) * item_bytes],
            "value": value,
        }))
    return items, actual_dtype, actual_shape, ",".join(units)


def _opaque_items(content: bytes) -> tuple[list[tuple[tuple[str | int, ...], dict[str, Any]]], str, tuple[int, ...]]:
    items = []
    for index, start in enumerate(range(0, len(content), _OPAQUE_ITEM_BYTES)):
        end = min(len(content), start + _OPAQUE_ITEM_BYTES)
        items.append(((index,), {
            "encoding": "base64",
            "kind": "bytes",
            "source_span": [start, end],
            "value": base64.b64encode(content[start:end]).decode("ascii"),
        }))
    if not items:
        items.append(((0,), {"encoding": "base64", "kind": "bytes", "source_span": [0, 0], "value": ""}))
    return items, "bytes", (len(content),)


def _decode_items(
    content: bytes,
    *,
    content_sha256: str,
    decoder_codec: str,
    dtype: str | None,
    shape: tuple[int, ...],
    units: tuple[str, ...],
) -> tuple[list[tuple[tuple[str | int, ...], dict[str, Any]]], str, tuple[int, ...]]:
    global _decode_cache_bytes
    key = (content_sha256, decoder_codec, dtype, shape, units)
    with _decode_cache_lock:
        cached = _decode_cache.get(key)
        if cached is not None:
            _decode_cache.move_to_end(key)
            return cached[0], cached[1], cached[2]

    if decoder_codec == CODEC_JSON:
        items, actual_dtype, actual_shape = _json_items(content)
    elif decoder_codec == CODEC_TEXT:
        items, actual_dtype, actual_shape = _text_items(content)
    elif decoder_codec == CODEC_CODE:
        items, actual_dtype, actual_shape = _code_items(content)
    elif decoder_codec == CODEC_OPAQUE:
        items, actual_dtype, actual_shape = _opaque_items(content)
    else:
        items, actual_dtype, actual_shape, _ = _numeric_items(
            content,
            codec=decoder_codec,
            dtype=dtype,
            shape=shape,
            units=units,
        )

    estimate = len(content) * 4 + sum(
        512 + len(path) * 16 for path, _ in items
    )
    if estimate <= _DECODE_CACHE_MAX_ENTRY_BYTES:
        with _decode_cache_lock:
            previous = _decode_cache.pop(key, None)
            if previous is not None:
                _decode_cache_bytes -= previous[3]
            _decode_cache[key] = (items, actual_dtype, actual_shape, estimate)
            _decode_cache_bytes += estimate
            while (
                _decode_cache_bytes > _DECODE_CACHE_MAX_BYTES
                or len(_decode_cache) > _DECODE_CACHE_MAX_ENTRIES
            ):
                _, evicted = _decode_cache.popitem(last=False)
                _decode_cache_bytes -= evicted[3]
    return items, actual_dtype, actual_shape


def _copy_value(value: dict[str, Any]) -> dict[str, Any]:
    # Cached nested coordinates/spans must not be mutable through returned pages.
    return {
        key: list(item) if isinstance(item, list) else item
        for key, item in value.items()
    }


def source_observation_page(
    source: Any,
    *,
    cursor: int = 0,
    page_size: int = 128,
    shape: Sequence[int] | None = None,
    dtype: str | None = None,
    units: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Decode one exact source into a canonical, bounded semantic observation page."""

    cursor = _integer(cursor, "cursor", minimum=0)
    page_size = _integer(page_size, "page_size", minimum=1, maximum=_MAX_PAGE_ITEMS)
    normalized_shape = _shape(shape)
    normalized_units = _units(units)
    content = getattr(source, "content", None)
    codec = getattr(source, "codec", None)
    revision_id = getattr(source, "revision_id", None)
    source_id = getattr(source, "source_id", None)
    media_type = getattr(source, "media_type", None)
    source_span = getattr(source, "span", None)
    if (
        not isinstance(content, bytes)
        or not isinstance(codec, str)
        or not codec
        or not isinstance(revision_id, str)
        or not revision_id
        or not isinstance(source_id, str)
        or not source_id
        or not isinstance(media_type, str)
        or not media_type
    ):
        raise SourceViewError(
            "source view requires an exact SourceInput-like value"
        )
    decoder_codec = _decoder_codec(codec, media_type)
    base = {
        "byte_length": len(content),
        "codec": codec,
        "decoder_codec": decoder_codec,
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "cursor": cursor,
        "media_type": media_type,
        "modality": _CODEC_MODALITY.get(decoder_codec, "unsupported"),
        "page_size": page_size,
        "schema": SOURCE_VIEW_SCHEMA,
        "source_id": source_id,
        "source_revision_id": revision_id,
        "source_span": None if source_span is None else list(source_span),
    }
    if decoder_codec not in SUPPORTED_CODECS:
        result = {
            **base,
            "complete": True,
            "dtype": dtype,
            "item_count": 0,
            "next_cursor": None,
            "observations": [],
            "reason": "unsupported-codec",
            "shape": list(normalized_shape),
            "status": "unsupported",
            "total_items": 0,
            "units": list(normalized_units),
        }
        return {**result, "view_sha256": _digest(result)}
    try:
        items, actual_dtype, actual_shape = _decode_items(
            content,
            content_sha256=base["content_sha256"],
            decoder_codec=decoder_codec,
            dtype=dtype,
            shape=normalized_shape,
            units=normalized_units,
        )
    except SourceViewError as exc:
        result = {
            **base,
            "complete": True,
            "dtype": dtype,
            "item_count": 0,
            "next_cursor": None,
            "observations": [],
            "reason": str(exc),
            "shape": list(normalized_shape),
            "status": "unsupported",
            "total_items": 0,
            "units": list(normalized_units),
        }
        return {**result, "view_sha256": _digest(result)}
    total = len(items)
    if cursor > total:
        raise SourceViewError("cursor exceeds the decoded source length")
    selected = items[cursor : cursor + page_size]
    observations = [
        _observation(
            revision_id=revision_id,
            source_id=source_id,
            ordinal=cursor + offset,
            path=path,
            value=_copy_value(value),
        )
        for offset, (path, value) in enumerate(selected)
    ]
    next_cursor = cursor + len(selected)
    complete = next_cursor >= total
    result = {
        **base,
        "complete": complete,
        "dtype": actual_dtype,
        "item_count": len(observations),
        "next_cursor": None if complete else next_cursor,
        "observations": observations,
        "reason": None,
        "shape": list(actual_shape),
        "status": "supported",
        "total_items": total,
        "units": list(normalized_units),
    }
    return {**result, "view_sha256": _digest(result)}


def semantic_observe_request(
    page: Mapping[str, Any],
    *,
    operation_id: str,
    event_id: str,
    delivery_id: str,
    stream_id: str | None = None,
    chunk_index: int | None = None,
) -> dict[str, Any]:
    if page.get("schema") != SOURCE_VIEW_SCHEMA or page.get("status") != "supported":
        raise SourceViewError("only a supported source page can enter cognition")
    request: dict[str, Any] = {
        "operation": "observe",
        "operation_id": operation_id,
        "delivery_id": delivery_id,
        "event_id": event_id,
        "observations": list(page["observations"]),
        "source": {
            "byte_length": page["byte_length"],
            "codec": page["codec"],
            "decoder_codec": page["decoder_codec"],
            "content_sha256": page["content_sha256"],
            "cursor": page["cursor"],
            "media_type": page["media_type"],
            "next_cursor": page["next_cursor"],
            "source_id": page["source_id"],
            "source_revision_id": page["source_revision_id"],
            "view_sha256": page["view_sha256"],
        },
        "support_roots": [page["source_revision_id"]],
    }
    if (stream_id is None) != (chunk_index is None):
        raise SourceViewError("stream_id and chunk_index must be supplied together")
    if stream_id is not None:
        request["stream_id"] = stream_id
        request["chunk_index"] = _integer(chunk_index, "chunk_index", minimum=0)
    return request


LIVE_SURFACE_PAGE_SCHEMA = "cassifi.live-surface-observation-page.v1"
_MAX_SURFACE_PAGE_BYTES = 1024 * 1024
LIVE_SURFACE_STRUCTURE_PAGE_SCHEMA = "cassifi.live-surface-structure-page.v1"
_MAX_SURFACE_STRUCTURE_BYTES = 1024 * 1024


def normalize_surface_coverage(
    value: Any, *, width: int, height: int
) -> dict[str, Any]:
    """Detach bounded coverage metadata and make unlocalized gaps explicit."""

    width = _integer(width, "surface width", minimum=1)
    height = _integer(height, "surface height", minimum=1)
    if not isinstance(value, Mapping):
        return {
            "complete": False,
            "coverage_reported": False,
            "missing_regions": [],
            "redacted_regions": [],
            "skipped_intervals": [],
            "unknown_regions": [{"reason": "coverage-not-reported"}],
        }
    try:
        encoded = _canonical(dict(value))
        if len(encoded) > 64 * 1024:
            raise SourceViewError("surface coverage exceeds the metadata limit")
        coverage = json.loads(encoded.decode("utf-8"))
    except (SourceViewError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceViewError("surface coverage is not bounded canonical JSON") from exc

    invalid = False
    complete = coverage.get("complete")
    if not isinstance(complete, bool):
        complete = False
        invalid = True

    def regions(name: str) -> list[dict[str, Any]]:
        nonlocal invalid
        raw = coverage.get(name, [])
        if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence) or len(raw) > 4096:
            invalid = True
            return []
        normalized: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, Mapping):
                invalid = True
                continue
            normalized_item = regions_from_one(item, width, height)
            if normalized_item is None:
                invalid = True
                continue
            normalized.append(normalized_item)
        return normalized

    missing = regions("missing_regions")
    redacted = regions("redacted_regions")
    unknown_raw = coverage.get("unknown_regions", [])
    if (
        isinstance(unknown_raw, (str, bytes))
        or not isinstance(unknown_raw, Sequence)
        or len(unknown_raw) > 4096
    ):
        invalid = True
        unknown = []
    else:
        unknown = []
        for item in unknown_raw:
            if (
                isinstance(item, Mapping)
                and all(key in item for key in ("x", "y", "width", "height"))
            ):
                normalized = regions_from_one(item, width, height)
                if normalized is None:
                    invalid = True
                else:
                    unknown.append(normalized)
            else:
                unknown.append(dict(item) if isinstance(item, Mapping) else item)

    skipped = coverage.get("skipped_intervals", [])
    if (
        isinstance(skipped, (str, bytes))
        or not isinstance(skipped, Sequence)
        or len(skipped) > 4096
    ):
        invalid = True
        skipped = []
    if complete and (missing or redacted or unknown):
        complete = False
    if invalid:
        unknown = [{"reason": "unlocalized-coverage"}]
        complete = False
    if not complete and not missing and not redacted and not unknown:
        unknown = [{"reason": "coverage-incomplete-without-region"}]
    result = {
        **coverage,
        "complete": complete,
        "coverage_reported": True,
        "missing_regions": missing,
        "redacted_regions": redacted,
        "skipped_intervals": list(skipped),
        "unknown_regions": unknown,
    }
    try:
        encoded = _canonical(result)
    except SourceViewError as exc:
        raise SourceViewError("surface coverage cannot be normalized") from exc
    if len(encoded) > 64 * 1024:
        raise SourceViewError("normalized surface coverage exceeds the metadata limit")
    return json.loads(encoded.decode("utf-8"))

def normalize_surface_structure_coverage(value: Any) -> dict[str, Any]:
    """Detach bounded structural coverage without inventing screen geometry."""

    if not isinstance(value, Mapping):
        return {
            "complete": False,
            "coverage_reported": False,
            "missing_regions": [],
            "redacted_regions": [],
            "skipped_intervals": [],
            "unknown_regions": [{"reason": "coverage-not-reported"}],
        }
    try:
        encoded = _canonical(dict(value))
        if len(encoded) > 64 * 1024:
            raise SourceViewError("surface coverage exceeds the metadata limit")
        coverage = json.loads(encoded.decode("utf-8"))
    except (SourceViewError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceViewError(
            "surface coverage is not bounded canonical JSON"
        ) from exc
    invalid = False
    complete = coverage.get("complete")
    if not isinstance(complete, bool):
        complete = False
        invalid = True
    normalized: dict[str, list[Any]] = {}
    for name in (
        "missing_regions",
        "redacted_regions",
        "skipped_intervals",
        "unknown_regions",
    ):
        raw = coverage.get(name, [])
        if (
            isinstance(raw, (str, bytes))
            or not isinstance(raw, Sequence)
            or len(raw) > 4096
        ):
            normalized[name] = []
            invalid = True
        else:
            normalized[name] = list(raw)
    if complete and (
        normalized["missing_regions"]
        or normalized["redacted_regions"]
        or normalized["unknown_regions"]
    ):
        complete = False
    if invalid:
        normalized["unknown_regions"] = [{"reason": "unlocalized-coverage"}]
        complete = False
    if not complete and not any(
        normalized[name]
        for name in ("missing_regions", "redacted_regions", "unknown_regions")
    ):
        normalized["unknown_regions"] = [
            {"reason": "coverage-incomplete-without-region"}
        ]
    result = {
        **coverage,
        "complete": complete,
        "coverage_reported": True,
        **normalized,
    }
    try:
        encoded = _canonical(result)
    except SourceViewError as exc:
        raise SourceViewError("surface coverage cannot be normalized") from exc
    if len(encoded) > 64 * 1024:
        raise SourceViewError("normalized surface coverage exceeds the metadata limit")
    return json.loads(encoded.decode("utf-8"))


def regions_from_one(
    item: Mapping[str, Any], width: int, height: int
) -> dict[str, Any] | None:
    if all(key in item for key in ("x", "y", "width", "height")):
        try:
            x = _integer(item.get("x"), "surface region x", minimum=0)
            y = _integer(item.get("y"), "surface region y", minimum=0)
            region_width = _integer(item.get("width"), "surface region width", minimum=1)
            region_height = _integer(item.get("height"), "surface region height", minimum=1)
        except SourceViewError:
            return None
        if x + region_width > width or y + region_height > height:
            return None
        return {
            **dict(item),
            "height": region_height,
            "width": region_width,
            "x": x,
            "y": y,
        }
    if "start_sample" in item and "sample_count" in item:
        try:
            start_sample = _integer(
                item.get("start_sample"), "surface sample start", minimum=0
            )
            sample_count = _integer(
                item.get("sample_count"), "surface sample count", minimum=1
            )
        except SourceViewError:
            return None
        if start_sample + sample_count > width:
            return None
        return {
            **dict(item),
            "sample_count": sample_count,
            "start_sample": start_sample,
        }
    return None


def _surface_format(pixel_format: str) -> tuple[str, str, int | None] | None:
    normalized = pixel_format.strip().lower().replace("_", "-")
    token = normalized.rsplit("/", 1)[-1]
    audio_token = token.removeprefix("audio-").removeprefix("pcm-")
    audio_types = {
        "f32le": "f32le",
        "f64le": "f64le",
        "i16le": "i16le",
        "i32le": "i32le",
        "s16le": "i16le",
        "s32le": "i32le",
        "u8": "u8",
    }
    if audio_token in audio_types:
        return audio_types[audio_token], "audio", None
    raster = {
        "gray8": 1,
        "grey8": 1,
        "gray": 1,
        "grayscale8": 1,
        "grey-scale8": 1,
        "gray-alpha8": 2,
        "graya8": 2,
        "la8": 2,
        "l8": 1,
        "y8": 1,
        "rgb8": 3,
        "bgr8": 3,
        "rgba8": 4,
        "bgra8": 4,
        "argb8": 4,
        "abgr8": 4,
    }
    channels = raster.get(token)
    if channels is not None:
        return "u8", "raster", channels
    return None


def _surface_hidden_regions(
    coverage: Mapping[str, Any],
    *,
    modality: str,
    width: int,
    height: int,
) -> tuple[list[Mapping[str, Any]], bool]:
    missing = coverage.get("missing_regions", [])
    redacted = coverage.get("redacted_regions", [])
    unknown = coverage.get("unknown_regions", [])
    hidden: list[Mapping[str, Any]] = []
    for collection in (missing, redacted, unknown):
        if isinstance(collection, (str, bytes)) or not isinstance(collection, Sequence):
            return [], True
        for item in collection:
            if not isinstance(item, Mapping):
                return [], True
            if modality == "raster":
                if not all(key in item for key in ("x", "y", "width", "height")):
                    return [], True
                normalized = regions_from_one(item, width, height)
                if normalized is None or "x" not in normalized:
                    return [], True
            elif "start_sample" in item and "sample_count" in item:
                if (
                    any(
                        isinstance(item[key], bool)
                        or not isinstance(item[key], int)
                        for key in ("start_sample", "sample_count")
                    )
                    or item["start_sample"] < 0
                    or item["sample_count"] <= 0
                    or item["start_sample"] + item["sample_count"] > width
                ):
                    return [], True
                normalized = item
            elif all(key in item for key in ("x", "y", "width", "height")):
                normalized = regions_from_one(item, width, height)
                if normalized is None or "x" not in normalized:
                    return [], True
            else:
                return [], True
            hidden.append(normalized)
    complete = coverage.get("complete")
    if not isinstance(complete, bool) or (
        not complete
        and not missing
        and not redacted
        and not unknown
    ):
        return [], True
    return hidden, False


def surface_observation_page(
    publication: Mapping[str, Any],
    pixels: bytes,
    *,
    byte_offset: int,
    page_size: int = 128,
) -> dict[str, Any]:
    """Decode at most one bounded live pixel/audio window into fixed observations."""

    if not isinstance(publication, Mapping):
        raise SourceViewError("surface publication must be a mapping")
    if not isinstance(pixels, bytes) or len(pixels) > _MAX_SURFACE_PAGE_BYTES:
        raise SourceViewError("surface input must be a bounded exact byte window")
    page_size = _integer(page_size, "page_size", minimum=1, maximum=_MAX_PAGE_ITEMS)
    byte_offset = _integer(byte_offset, "byte_offset", minimum=0)
    binding_id = publication.get("binding_id")
    generation = publication.get("generation")
    source_id = publication.get("source_id")
    source_revision_id = publication.get("sha256")
    width = _integer(publication.get("width"), "surface width", minimum=1)
    height = _integer(publication.get("height"), "surface height", minimum=1)
    byte_length = _integer(publication.get("byte_length"), "surface byte length", minimum=1)
    sequence = _integer(
        publication.get("sequence"),
        "surface sequence",
        minimum=0,
        maximum=2**64 - 1,
    )
    sample_time_ns = publication.get("sample_time_ns")
    if sample_time_ns is not None:
        sample_time_ns = _integer(sample_time_ns, "surface sample time", minimum=0)
    sample_time_uncertainty_ns = publication.get("sample_time_uncertainty_ns")
    if sample_time_uncertainty_ns is not None:
        sample_time_uncertainty_ns = _integer(
            sample_time_uncertainty_ns, "surface sample time uncertainty", minimum=0
        )
    receipt_time_ns = _integer(
        publication.get("receipt_time_ns"), "surface receipt time", minimum=0
    )
    sample_clock_domain = publication.get("sample_clock_domain")
    receipt_clock_domain = publication.get("receipt_clock_domain")
    if sample_clock_domain is not None and not isinstance(sample_clock_domain, str):
        raise SourceViewError("surface sample clock domain is invalid")
    if not isinstance(receipt_clock_domain, str) or not receipt_clock_domain:
        raise SourceViewError("surface receipt clock domain is invalid")
    for name, value in (
        ("binding_id", binding_id),
        ("source_id", source_id),
        ("source_revision_id", source_revision_id),
    ):
        if not isinstance(value, str) or not value:
            raise SourceViewError(f"{name} must be nonempty text")
    generation = _integer(generation, "surface generation", minimum=1)
    if len(source_revision_id) != 64 or any(
        character not in "0123456789abcdef" for character in source_revision_id
    ):
        raise SourceViewError("surface content digest is invalid")
    if byte_offset + len(pixels) > byte_length:
        raise SourceViewError("surface byte window exceeds the publication extent")

    pixel_format = publication.get("pixel_format")
    if not isinstance(pixel_format, str) or not pixel_format:
        raise SourceViewError("surface pixel_format must be nonempty text")
    spec = _surface_format(pixel_format)
    if spec is None:
        raise SourceViewError("surface pixel_format has no fixed decoder")
    dtype, modality, channels = spec
    fmt, item_bytes = _DTYPE_FORMATS[dtype]
    if byte_offset % item_bytes or len(pixels) % item_bytes:
        raise SourceViewError("surface byte window is not aligned to its fixed codec")
    shape = (
        (height, width, channels)
        if modality == "raster"
        else ((width,) if height == 1 else (width, height))
    )
    total_items = math.prod(shape)
    if total_items * item_bytes != byte_length:
        raise SourceViewError("surface dimensions do not match its exact byte extent")

    coverage = publication.get("coverage")
    if not isinstance(coverage, Mapping):
        coverage = {
            "complete": False,
            "unknown_regions": [{"reason": "coverage-not-reported"}],
        }
    hidden, hide_all = _surface_hidden_regions(
        coverage, modality=modality, width=width, height=height
    )
    item_cursor = byte_offset // item_bytes
    available_items = len(pixels) // item_bytes
    scan_count = min(available_items, max(page_size * 16, page_size))
    scan_end = min(total_items, item_cursor + scan_count)
    observations: list[dict[str, Any]] = []
    if not hide_all:
        for index in range(item_cursor, scan_end):
            if modality == "raster":
                pixel = index // channels
                x, y = pixel % width, pixel // width
                hidden_item = any(
                    item["x"] <= x < item["x"] + item["width"]
                    and item["y"] <= y < item["y"] + item["height"]
                    for item in hidden
                )
                coordinates = (y, x, index % channels)
            else:
                frame, channel = divmod(index, height)
                hidden_item = any(
                    (
                        item["start_sample"] <= frame
                        < item["start_sample"] + item["sample_count"]
                    )
                    if "start_sample" in item
                    else (
                        item["x"] <= frame < item["x"] + item["width"]
                        and item["y"] <= channel < item["y"] + item["height"]
                    )
                    for item in hidden
                )
                coordinates = (index,) if height == 1 else (frame, channel)
            if hidden_item:
                continue
            local_index = index - item_cursor
            value = struct.unpack_from(fmt, pixels, local_index * item_bytes)[0]
            if isinstance(value, float) and not math.isfinite(value):
                raise SourceViewError("surface page contains a non-finite sample")
            descriptor = {
                "dtype": dtype,
                "flat_index": index,
                "index": list(coordinates),
                "kind": "tensor-element",
                "source_span": [index * item_bytes, (index + 1) * item_bytes],
                "value": value,
            }
            observations.append(
                {
                    "attribute": _path_text(coordinates),
                    "binding_id": f"surface:{binding_id}:{generation}:{index}",
                    "epistemic_kind": "observed",
                    "status": "active",
                    "subject": source_id,
                    "value": descriptor,
                }
            )
            if len(observations) >= page_size:
                break
    scanned_end = (
        min(scan_end, observations[-1]["value"]["flat_index"] + 1)
        if observations and len(observations) == page_size
        else scan_end
    )
    coverage_view = _canonical(dict(coverage))
    result: dict[str, Any] = {
        "schema": LIVE_SURFACE_PAGE_SCHEMA,
        "status": "limited" if hide_all else "supported",
        "source_id": source_id,
        "source_instance": publication.get("source_instance"),
        "source_epoch": publication.get("source_epoch"),
        "environment_incarnation": publication.get("environment_incarnation"),
        "geometry_revision": publication.get("geometry_revision"),
        "source_revision_id": source_revision_id,
        "binding_id": binding_id,
        "generation": generation,
        "sequence": sequence,
        "pixel_format": pixel_format,
        "dtype": dtype,
        "shape": list(shape),
        "byte_length": byte_length,
        "byte_offset": byte_offset,
        "byte_window_length": len(pixels),
        "content_sha256": source_revision_id,
        "coverage": json.loads(coverage_view.decode("utf-8")),
        "sample_time_ns": sample_time_ns,
        "sample_clock_domain": sample_clock_domain,
        "sample_time_uncertainty_ns": sample_time_uncertainty_ns,
        "receipt_time_ns": receipt_time_ns,
        "receipt_clock_domain": receipt_clock_domain,
        "provenance": publication.get("provenance"),
        "cursor": item_cursor,
        "item_count": len(observations),
        "total_items": total_items,
        "complete": scanned_end >= total_items,
        "next_cursor": None if scanned_end >= total_items else scanned_end,
        "observations": observations,
    }
    return {**result, "view_sha256": _digest(result)}


def surface_structure_observation_page(
    publication: Mapping[str, Any],
    content: bytes,
    *,
    cursor: int = 0,
    page_size: int = 128,
) -> dict[str, Any]:
    """Decode one bounded text/accessibility page through the existing field codecs."""

    if not isinstance(publication, Mapping):
        raise SourceViewError("surface structure publication must be a mapping")
    if not isinstance(content, bytes) or len(content) > _MAX_SURFACE_STRUCTURE_BYTES:
        raise SourceViewError("surface structure must be bounded immutable bytes")
    cursor = _integer(cursor, "cursor", minimum=0)
    page_size = _integer(page_size, "page_size", minimum=1, maximum=_MAX_PAGE_ITEMS)
    source_id = publication.get("source_id")
    source_revision_id = publication.get("sha256")
    binding_id = publication.get("binding_id")
    generation = _integer(publication.get("generation"), "generation", minimum=1)
    for name, value in (
        ("source_id", source_id),
        ("source_revision_id", source_revision_id),
        ("binding_id", binding_id),
    ):
        if not isinstance(value, str) or not value:
            raise SourceViewError(f"{name} must be nonempty text")
    if hashlib.sha256(content).hexdigest() != source_revision_id:
        raise SourceViewError("surface structure digest does not match its bytes")
    codec = publication.get("codec")
    if codec not in (CODEC_JSON, CODEC_TEXT):
        raise SourceViewError("surface structure codec is unsupported")
    coverage = publication.get("coverage")
    if not isinstance(coverage, Mapping):
        coverage = normalize_surface_structure_coverage(None)
    else:
        coverage = normalize_surface_structure_coverage(coverage)
    incomplete = (
        coverage.get("complete") is not True
        or bool(coverage.get("missing_regions"))
        or bool(coverage.get("redacted_regions"))
        or bool(coverage.get("unknown_regions"))
    )
    if incomplete:
        source_page: dict[str, Any] = {
            "byte_length": len(content),
            "codec": codec,
            "decoder_codec": codec,
            "content_sha256": source_revision_id,
            "cursor": cursor,
            "media_type": (
                "application/json" if codec == CODEC_JSON else "text/plain"
            ),
            "modality": "structure",
            "page_size": page_size,
            "schema": SOURCE_VIEW_SCHEMA,
            "source_id": source_id,
            "source_revision_id": source_revision_id,
            "source_span": None,
            "complete": False,
            "dtype": "json" if codec == CODEC_JSON else "utf8",
            "item_count": 0,
            "next_cursor": None,
            "observations": [],
            "reason": "surface-coverage-incomplete",
            "shape": [],
            "status": "limited",
            "total_items": 0,
            "units": [],
        }
    else:
        source = SimpleNamespace(
            content=content,
            codec=codec,
            revision_id=source_revision_id,
            source_id=source_id,
            media_type=(
                "application/json" if codec == CODEC_JSON else "text/plain"
            ),
            span=None,
        )
        try:
            source_page = source_observation_page(
                source, cursor=cursor, page_size=page_size
            )
        except (RecursionError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceViewError("surface structure could not be decoded") from exc
    sample_time_ns = publication.get("sample_time_ns")
    if sample_time_ns is not None:
        sample_time_ns = _integer(sample_time_ns, "surface sample time", minimum=0)
    sample_time_uncertainty_ns = publication.get("sample_time_uncertainty_ns")
    if sample_time_uncertainty_ns is not None:
        sample_time_uncertainty_ns = _integer(
            sample_time_uncertainty_ns, "surface sample time uncertainty", minimum=0
        )
    receipt_time_ns = _integer(
        publication.get("receipt_time_ns"), "surface receipt time", minimum=0
    )
    sample_clock_domain = publication.get("sample_clock_domain")
    receipt_clock_domain = publication.get("receipt_clock_domain")
    if sample_clock_domain is not None and not isinstance(sample_clock_domain, str):
        raise SourceViewError("surface sample clock domain is invalid")
    if not isinstance(receipt_clock_domain, str) or not receipt_clock_domain:
        raise SourceViewError("surface receipt clock domain is invalid")
    result = {
        **source_page,
        "schema": LIVE_SURFACE_STRUCTURE_PAGE_SCHEMA,
        "modality": "structure",
        "binding_id": binding_id,
        "generation": generation,
        "source_id": source_id,
        "source_instance": publication.get("source_instance"),
        "source_epoch": publication.get("source_epoch"),
        "environment_incarnation": publication.get("environment_incarnation"),
        "geometry_revision": publication.get("geometry_revision"),
        "sequence": publication.get("sequence"),
        "coverage": coverage,
        "sample_time_ns": sample_time_ns,
        "sample_clock_domain": sample_clock_domain,
        "sample_time_uncertainty_ns": sample_time_uncertainty_ns,
        "receipt_time_ns": receipt_time_ns,
        "receipt_clock_domain": receipt_clock_domain,
        "provenance": publication.get("provenance"),
    }
    return {**result, "view_sha256": _digest(result)}


__all__ = [
    "CODEC_AUDIO",
    "CODEC_CODE",
    "CODEC_JSON",
    "CODEC_OPAQUE",
    "CODEC_RASTER",
    "CODEC_TENSOR",
    "CODEC_TEXT",
    "LIVE_SURFACE_PAGE_SCHEMA",
    "LIVE_SURFACE_STRUCTURE_PAGE_SCHEMA",
    "SOURCE_VIEW_SCHEMA",
    "SUPPORTED_CODECS",
    "SourceViewError",
    "normalize_surface_coverage",
    "normalize_surface_structure_coverage",
    "semantic_observe_request",
    "source_observation_page",
    "surface_observation_page",
    "surface_structure_observation_page",
]
