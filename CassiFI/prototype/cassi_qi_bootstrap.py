"""Frozen canonical bootstrap for Cassi Qi Flow contract identities.

This module deliberately contains only the bounded byte codec, hashing primitive,
and their cross-implementation fixtures.  Profile instances and runtime laws do
not live here, so ordinary profile revisions cannot reinterpret a sealed root.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import struct
from typing import Any, Mapping

CANONICAL_CODEC_SCHEMA = "cassi.canonical-json.v1"
CONTRACT_ROOT_BOOTSTRAP_SCHEMA = "cassi.qi-flow-contract-root-bootstrap.v1"
CANONICAL_FIXTURE_SCHEMA = "cassi.qi-flow-canonical-fixtures.v1"
MAX_CANONICAL_BYTES = 1 << 20
MAX_CANONICAL_DEPTH = 64
MAX_CANONICAL_INTEGER = (1 << 53) - 1


class CanonicalCodecError(ValueError):
    """Raised when bytes or values violate the frozen canonical codec."""


def _reject_surrogates(value: str) -> str:
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise CanonicalCodecError("unpaired surrogate is not canonical UTF-8") from exc
    if value.startswith("\ufeff"):
        raise CanonicalCodecError("canonical string must not begin with a BOM")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise CanonicalCodecError("unpaired surrogate is not canonical UTF-8")
    if len(encoded) > MAX_CANONICAL_BYTES:
        raise CanonicalCodecError("canonical string exceeds byte budget")
    return value


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CanonicalCodecError(f"duplicate JSON key: {key}")
        _reject_surrogates(key)
        result[key] = value
    return result


def _bad_constant(value: str) -> None:
    raise CanonicalCodecError(f"non-finite JSON scalar: {value}")


def _parse_integer(value: str) -> int:
    if value == "-0":
        raise CanonicalCodecError("negative-zero JSON integer is forbidden")
    result = int(value, 10)
    if not -MAX_CANONICAL_INTEGER <= result <= MAX_CANONICAL_INTEGER:
        raise CanonicalCodecError("JSON integer exceeds the canonical exact range")
    return result


def _bad_decimal(value: str) -> None:
    raise CanonicalCodecError(f"decimal JSON scalar is forbidden: {value}")


def finite_bits(value: float, *, width: int = 64) -> str:
    if not math.isfinite(value):
        raise CanonicalCodecError("non-finite scalar")
    if value == 0.0 and math.copysign(1.0, value) < 0.0:
        raise CanonicalCodecError("negative zero is forbidden")
    if width == 64:
        return "f64:" + struct.pack(">d", float(value)).hex()
    if width == 32:
        narrowed = struct.unpack(">f", struct.pack(">f", float(value)))[0]
        if not math.isfinite(narrowed):
            raise CanonicalCodecError("non-finite f32 scalar")
        return "f32:" + struct.pack(">f", narrowed).hex()
    raise CanonicalCodecError("finite-bit width must be 32 or 64")


def _tagged_finite_float(value: str, *, name: str) -> float:
    if value.startswith("f64:"):
        unpack, width, encoded = ">d", 16, value[4:]
    elif value.startswith("f32:"):
        unpack, width, encoded = ">f", 8, value[4:]
    else:
        raise CanonicalCodecError(f"{name} must use a finite-bit tag")
    if len(encoded) != width or encoded.lower() != encoded:
        raise CanonicalCodecError(f"{name} has invalid finite-bit width or case")
    try:
        result = struct.unpack(unpack, bytes.fromhex(encoded))[0]
    except ValueError as exc:
        raise CanonicalCodecError(f"{name} has invalid finite-bit payload") from exc
    if result == 0.0 and math.copysign(1.0, result) < 0.0:
        raise CanonicalCodecError(f"{name} negative zero is forbidden")
    if not math.isfinite(result):
        raise CanonicalCodecError(f"{name} is a non-finite scalar")
    return result


def finite_float(value: Any, *, name: str = "scalar") -> float:
    if isinstance(value, bool):
        raise CanonicalCodecError(f"{name} must be a finite scalar")
    if isinstance(value, str):
        return _tagged_finite_float(value, name=name)
    if isinstance(value, (int, float)):
        result = float(value)
    else:
        raise CanonicalCodecError(f"{name} must be a finite scalar")
    if result == 0.0 and math.copysign(1.0, result) < 0.0:
        raise CanonicalCodecError(f"{name} negative zero is forbidden")
    if not math.isfinite(result):
        raise CanonicalCodecError(f"{name} is a non-finite scalar")
    return result


def _normalise(value: Any, *, depth: int = 0) -> Any:
    if depth > MAX_CANONICAL_DEPTH:
        raise CanonicalCodecError("canonical JSON nesting limit exceeded")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        if not -MAX_CANONICAL_INTEGER <= value <= MAX_CANONICAL_INTEGER:
            raise CanonicalCodecError("JSON integer exceeds the canonical exact range")
        return value
    if isinstance(value, float):
        return finite_bits(value)
    if isinstance(value, str):
        _reject_surrogates(value)
        if value.startswith(("f32:", "f64:")):
            _tagged_finite_float(value, name="canonical finite-bit scalar")
        return value
    if isinstance(value, (list, tuple)):
        return [_normalise(item, depth=depth + 1) for item in value]
    if isinstance(value, Mapping):
        converted: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalCodecError("canonical object key is not string")
            _reject_surrogates(key)
            if key in converted:
                raise CanonicalCodecError(f"duplicate object key: {key}")
            converted[key] = _normalise(item, depth=depth + 1)
        return converted
    raise CanonicalCodecError(f"unsupported canonical type: {type(value).__name__}")


def _quote_string(value: str) -> str:
    _reject_surrogates(value)
    pieces = ['"']
    for scalar in value:
        codepoint = ord(scalar)
        if scalar == '"':
            pieces.append('\\"')
        elif scalar == "\\":
            pieces.append("\\\\")
        elif codepoint <= 0x1F:
            pieces.append(f"\\u{codepoint:04x}")
        else:
            pieces.append(scalar)
    pieces.append('"')
    return "".join(pieces)


def _encode_canonical(value: Any, *, depth: int = 0) -> str:
    if depth > MAX_CANONICAL_DEPTH:
        raise CanonicalCodecError("canonical JSON nesting limit exceeded")
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int) and not isinstance(value, bool):
        if not -MAX_CANONICAL_INTEGER <= value <= MAX_CANONICAL_INTEGER:
            raise CanonicalCodecError("JSON integer exceeds the canonical exact range")
        return str(value)
    if isinstance(value, str):
        return _quote_string(value)
    if isinstance(value, list):
        return "[" + ",".join(_encode_canonical(item, depth=depth + 1) for item in value) + "]"
    if isinstance(value, Mapping):
        items = sorted(value.items(), key=lambda item: item[0].encode("utf-8", "strict"))
        return "{" + ",".join(
            _quote_string(key) + ":" + _encode_canonical(item, depth=depth + 1)
            for key, item in items
        ) + "}"
    raise CanonicalCodecError(f"unsupported canonical type: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    normalised = _normalise(value)
    body = _encode_canonical(normalised).encode("utf-8", "strict")
    if len(body) > MAX_CANONICAL_BYTES:
        raise CanonicalCodecError("canonical JSON exceeds byte budget")
    return body


def canonical_json_loads(payload: bytes | bytearray | memoryview | str) -> Any:
    if isinstance(payload, str):
        try:
            raw = payload.encode("utf-8", "strict")
        except UnicodeEncodeError as exc:
            raise CanonicalCodecError("canonical JSON must be strict UTF-8") from exc
    elif isinstance(payload, (bytes, bytearray, memoryview)):
        raw = bytes(payload)
    else:
        raise CanonicalCodecError("canonical JSON payload must be bytes or str")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise CanonicalCodecError("canonical JSON must not begin with a UTF-8 BOM")
    if len(raw) > MAX_CANONICAL_BYTES:
        raise CanonicalCodecError("canonical JSON exceeds byte budget")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise CanonicalCodecError("canonical JSON must be strict UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_int=_parse_integer,
            parse_float=_bad_decimal,
            parse_constant=_bad_constant,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, CanonicalCodecError):
            raise
        raise CanonicalCodecError(f"invalid canonical JSON: {exc}") from exc
    _normalise(value)
    if canonical_json_bytes(value) != raw:
        raise CanonicalCodecError("JSON bytes are valid but not canonical")
    return value


def canonical_hash(value: Any, domain: str = "cassi.qi-flow") -> str:
    if not isinstance(domain, str) or not domain:
        raise CanonicalCodecError("hash domain must be nonempty string")
    _reject_surrogates(domain)
    domain_bytes = domain.encode("utf-8")
    payload_bytes = canonical_json_bytes(value)
    framed = (
        len(domain_bytes).to_bytes(8, "big")
        + domain_bytes
        + len(payload_bytes).to_bytes(8, "big")
        + payload_bytes
    )
    return hashlib.sha256(framed).hexdigest()


def _fixture_rows() -> list[dict[str, str]]:
    depth_payload = ("[" * 66 + "0" + "]" * 66).encode("ascii")
    rows = [
        ("canonical-empty", b"{}", "ACCEPT"),
        ("canonical-control", b'{"x":"\\u0000\\u0009\\u000a\\u001f"}', "ACCEPT"),
        ("unicode-lookalikes", '{"K":"latin","K":"kelvin"}'.encode("utf-8"), "ACCEPT"),
        ("duplicate-key", b'{"x":1,"x":2}', "REJECT_DUPLICATE_KEY"),
        ("reordered-key", b'{"z":0,"a":0}', "REJECT_NONCANONICAL"),
        ("short-control-escape", b'{"x":"\\n"}', "REJECT_NONCANONICAL"),
        ("uppercase-control-escape", b'{"x":"\\u000A"}', "REJECT_NONCANONICAL"),
        ("whitespace", b'{ "x":0}', "REJECT_NONCANONICAL"),
        ("decimal", b'{"x":1.0}', "REJECT_DECIMAL"),
        ("exponent", b'{"x":1e0}', "REJECT_DECIMAL"),
        ("nan-token", b'{"x":NaN}', "REJECT_NONFINITE"),
        ("infinity-token", b'{"x":Infinity}', "REJECT_NONFINITE"),
        ("invalid-utf8", b"\xff", "REJECT_UTF8"),
        ("bom", b"\xef\xbb\xbf{}", "REJECT_UTF8"),
        ("negative-zero-integer", b'{"x":-0}', "REJECT_NEGATIVE_ZERO"),
        ("negative-zero-tag", b'{"x":"f64:8000000000000000"}', "REJECT_NEGATIVE_ZERO"),
        ("nan-tag", b'{"x":"f64:7ff8000000000000"}', "REJECT_NONFINITE"),
        ("short-tag", b'{"x":"f64:0000"}', "REJECT_TAG"),
        ("uppercase-tag", b'{"x":"f64:3FF0000000000000"}', "REJECT_TAG"),
        ("integer-too-large", b'{"x":9007199254740992}', "REJECT_INTEGER_RANGE"),
        ("integer-too-small", b'{"x":-9007199254740992}', "REJECT_INTEGER_RANGE"),
        ("surrogate", b'{"x":"\\ud800"}', "REJECT_SURROGATE"),
        ("excessive-depth", depth_payload, "REJECT_DEPTH"),
    ]
    return [
        {
            "fixture_id": fixture_id,
            "payload_base64": base64.b64encode(payload).decode("ascii"),
            "expected": expected,
        }
        for fixture_id, payload, expected in rows
    ]


def canonical_fixture_corpus() -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": CANONICAL_FIXTURE_SCHEMA,
        "codec_schema": CANONICAL_CODEC_SCHEMA,
        "fixtures": _fixture_rows(),
    }
    body["self_sha256"] = canonical_hash(body, CANONICAL_FIXTURE_SCHEMA)
    return body


def canonical_codec_descriptor() -> dict[str, Any]:
    corpus = canonical_fixture_corpus()
    return {
        "schema": CANONICAL_CODEC_SCHEMA,
        "version": 1,
        "encoding": "strict-utf8-no-bom",
        "key_order": "utf8-byte-lexicographic",
        "control_escape": "lowercase-u00xx",
        "integer_range": {
            "minimum": -MAX_CANONICAL_INTEGER,
            "maximum": MAX_CANONICAL_INTEGER,
        },
        "decimal_numbers": "forbidden-use-f32-f64-bit-tags",
        "finite_bit_tags": [{"tag": "f32", "hex_digits": 8}, {"tag": "f64", "hex_digits": 16}],
        "negative_zero": "forbidden",
        "max_bytes": MAX_CANONICAL_BYTES,
        "max_depth": MAX_CANONICAL_DEPTH,
        "fixture_corpus_schema": CANONICAL_FIXTURE_SCHEMA,
        "fixture_corpus_sha256": corpus["self_sha256"],
    }


def bootstrap_fixture_set_sha256() -> str:
    return str(canonical_fixture_corpus()["self_sha256"])


def bootstrap_self_test() -> None:
    classifications = {
        "duplicate": "REJECT_DUPLICATE_KEY",
        "non-finite": "REJECT_NONFINITE",
        "surrogate": "REJECT_SURROGATE",
        "bom": "REJECT_UTF8",
        "utf-8": "REJECT_UTF8",
        "negative-zero": "REJECT_NEGATIVE_ZERO",
        "negative zero": "REJECT_NEGATIVE_ZERO",
        "integer exceeds": "REJECT_INTEGER_RANGE",
        "nesting": "REJECT_DEPTH",
        "finite-bit": "REJECT_TAG",
        "decimal": "REJECT_DECIMAL",
        "not canonical": "REJECT_NONCANONICAL",
    }
    for fixture in canonical_fixture_corpus()["fixtures"]:
        payload = base64.b64decode(fixture["payload_base64"], validate=True)
        try:
            canonical_json_loads(payload)
            observed = "ACCEPT"
        except CanonicalCodecError as error:
            message = str(error).lower()
            observed = next((kind for fragment, kind in classifications.items() if fragment in message), "REJECT")
        if observed != fixture["expected"]:
            raise CanonicalCodecError(
                f"bootstrap fixture mismatch: {fixture['fixture_id']}: {observed}"
            )


__all__ = [
    "CANONICAL_CODEC_SCHEMA",
    "CONTRACT_ROOT_BOOTSTRAP_SCHEMA",
    "CANONICAL_FIXTURE_SCHEMA",
    "MAX_CANONICAL_BYTES",
    "MAX_CANONICAL_DEPTH",
    "MAX_CANONICAL_INTEGER",
    "CanonicalCodecError",
    "finite_bits",
    "finite_float",
    "canonical_json_bytes",
    "canonical_json_loads",
    "canonical_hash",
    "canonical_fixture_corpus",
    "canonical_codec_descriptor",
    "bootstrap_fixture_set_sha256",
    "bootstrap_self_test",
]
