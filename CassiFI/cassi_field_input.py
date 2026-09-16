from __future__ import annotations

"""Deterministic, bounded source views for the resident cognition field."""

import ast
import base64
import hashlib
import json
import math
import operator
import struct
from functools import reduce
from typing import Any, Mapping, Sequence


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
            value=value,
            units=normalized_units,
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


__all__ = [
    "CODEC_AUDIO",
    "CODEC_CODE",
    "CODEC_JSON",
    "CODEC_OPAQUE",
    "CODEC_RASTER",
    "CODEC_TENSOR",
    "CODEC_TEXT",
    "SOURCE_VIEW_SCHEMA",
    "SUPPORTED_CODECS",
    "SourceViewError",
    "semantic_observe_request",
    "source_observation_page",
]
