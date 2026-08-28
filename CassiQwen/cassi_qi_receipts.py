"""Exact registry-backed builders and validators for indexed Cassi receipts.

Only registry entries classified as ``indexed-receipt`` are accepted here.  The
module first validates the complete frozen schema registry (including each
schema document, fixture set, and mutation-control hash), then applies that
registered schema recursively to a receipt before deriving or checking either
of its identities.
"""

from __future__ import annotations

import base64
import math
import re
import struct
from collections.abc import Mapping, Sequence
from typing import Any

from cassi_qi_bootstrap import (
    MAX_CANONICAL_BYTES,
    MAX_CANONICAL_DEPTH,
    MAX_CANONICAL_INTEGER,
    CanonicalCodecError,
)
from cassi_qi_profile import (
    CONTRACT_ROOT_SCHEMA,
    PROFILE_MISMATCH,
    SCHEMA_REGISTRY,
    SCHEMA_REGISTRY_MANIFEST,
    canonical_hash,
    canonical_json_bytes,
    canonical_json_loads,
    validate_contract_root,
    validate_profile,
)

SCHEMA_DOCUMENT_SCHEMA = "cassi.qi-flow-schema-document.v1"
SCHEMA_REGISTRY_SCHEMA = "cassi.qi-flow-schema-registry.v1"
SCHEMA_FIXTURE_SET_HASH_DOMAIN = "cassi.qi-flow-schema-fixture-set.v1"
SCHEMA_MUTATION_CONTROLS_HASH_DOMAIN = "cassi.qi-flow-schema-mutation-controls.v1"

# Registry parent names deliberately differ from the profile-projection field
# spelling.  The suffix exists only at the selected-profile seam.
SEMANTIC_PARENT_ORDER = (
    "state_contract",
    "boundary_action",
    "world_protocol",
    "session_storage",
    "provider_api",
    "backend_capacity",
    "security_evidence",
)
_PROFILE_PARENT_FIELDS = {name: f"{name}_sha256" for name in SEMANTIC_PARENT_ORDER}

_ENTRY_KEYS = frozenset(
    {
        "schema",
        "version",
        "object_class",
        "lifecycle",
        "max_encoded_bytes",
        "max_fanout",
        "semantic_parent_names",
        "schema_document",
        "schema_document_sha256",
        "fixture_id",
        "canonical_fixture_set",
        "canonical_fixture_set_sha256",
        "mutation_controls",
        "mutation_controls_sha256",
        "hash_domain",
        "self_hash_field",
        "independent_verifier",
        "migration_policy",
    }
)
_SCHEMA_DOCUMENT_REQUIRED_KEYS = frozenset(
    {
        "schema",
        "object_schema",
        "required_keys",
        "optional_keys",
        "nullable_keys",
        "properties",
        "invariants",
    }
)
_SCHEMA_DOCUMENT_KEYS = _SCHEMA_DOCUMENT_REQUIRED_KEYS | frozenset(
    {
        "type",
        "rules",
        "object_class",
        "lifecycle",
        "max_encoded_bytes",
        "max_fanout",
        "semantic_parent_names",
        "hash_domain",
        "self_hash_field",
        "version",
        "additional_properties",
        "consumed_semantic_subhashes",
    }
)
_REGISTRY_KEYS = frozenset({"schema", "registry_id", "entries", "self_sha256"})
_FIXTURE_SET_KEYS = frozenset({"minimal_valid", "maximal_valid", "nullable_valid"})
_MUTATION_CONTROL_KEYS = frozenset(
    {"control_id", "base_fixture", "operation", "pointer", "value", "expected_error"}
)
_RECEIPT_ENVELOPE_KEYS = frozenset(
    {
        "schema",
        "receipt_id",
        "contract_root_sha256",
        "profile_sha256",
        "consumed_semantic_subhashes",
        "self_sha256",
    }
)
_LEGACY_RECEIPT_KEYS = frozenset({"domain", "artifact_schema", "profile_state_sha256"})
_OBJECT_CLASSES = frozenset(
    {
        "bootstrap-object",
        "profile-contract",
        "immutable-spec",
        "runtime-state",
        "checkpoint",
        "protocol-object",
        "indexed-receipt",
        "manifest",
        "gate-artifact",
    }
)
_LIFECYCLES = frozenset(
    {
        "bootstrap",
        "immutable_spec",
        "run_frozen",
        "runtime_ephemeral",
        "content_addressed_frame",
        "transaction_evidence",
        "checkpoint_evidence",
        "gate_evidence",
        "release_evidence",
    }
)
_ERROR_CODES = frozenset(
    {
        "SCHEMA_LITERAL_MISMATCH",
        "UNKNOWN_KEY",
        "MISSING_REQUIRED_KEY",
        "FORBIDDEN_NULL",
        "NONCANONICAL_ENCODING",
        "BYTE_LIMIT_EXCEEDED",
        "FANOUT_LIMIT_EXCEEDED",
        "SELF_HASH_MISMATCH",
        "HASH_DOMAIN_MISMATCH",
        "SEMANTIC_PARENT_SET_MISMATCH",
        "SEMANTIC_PARENT_ORDER_MISMATCH",
        "SEMANTIC_PARENT_DIGEST_MISMATCH",
        "FIXTURE_SET_HASH_MISMATCH",
        "MUTATION_CONTROLS_HASH_MISMATCH",
        "OBJECT_CLASS_MISMATCH",
        "LIFECYCLE_MISMATCH",
        "RECEIPT_ID_MISMATCH",
        "RAW_IDENTITY_MISMATCH",
        "STATE_LAYOUT_MISMATCH",
        "CHECKPOINT_FRAME_MISMATCH",
        "UNRESOLVED_REFERENCE",
    }
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FLOAT_BITS = re.compile(r"^f(32|64):([0-9a-f]+)$")
_SCHEMA_VERSION = re.compile(r"\.v([1-9][0-9]*)$")


__all__ = [
    "CONTRACT_ROOT_SCHEMA",
    "SCHEMA_DOCUMENT_SCHEMA",
    "SCHEMA_REGISTRY_SCHEMA",
    "SCHEMA_FIXTURE_SET_HASH_DOMAIN",
    "SCHEMA_MUTATION_CONTROLS_HASH_DOMAIN",
    "RECEIPT_SCHEMAS",
    "receipt_fixture_payload",
    "build_receipt",
    "validate_receipt",
    "build_registered_object",
    "validate_registered_object",
    "receipt_bytes",
    "receipt_self_hash",
]


def _fail(code: str, message: str, cause: BaseException | None = None) -> None:
    error = PROFILE_MISMATCH(f"{code}: {message}")
    if cause is None:
        raise error
    raise error from cause


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        _fail(code, message)


def _safe_integer(value: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and -MAX_CANONICAL_INTEGER <= value <= MAX_CANONICAL_INTEGER
    )


def _digest(value: Any, context: str) -> str:
    _require(
        isinstance(value, str) and _SHA256.fullmatch(value) is not None,
        "SCHEMA_LITERAL_MISMATCH",
        f"{context} must be a lowercase SHA-256 digest",
    )
    return value


def _identifier(value: Any, context: str) -> str:
    _require(
        isinstance(value, str) and _ID.fullmatch(value) is not None,
        "SCHEMA_LITERAL_MISMATCH",
        f"{context} must be an ASCII identifier",
    )
    return value


def _tagged_finite_bits(value: Any, width: str | None, context: str) -> None:
    _require(isinstance(value, str), "SCHEMA_LITERAL_MISMATCH", f"{context} must be a finite-bit string")
    match = _FLOAT_BITS.fullmatch(value)
    _require(match is not None, "SCHEMA_LITERAL_MISMATCH", f"{context} has malformed finite bits")
    found_width, text = match.groups()
    _require(width is None or found_width == width.removeprefix("f"), "SCHEMA_LITERAL_MISMATCH", f"{context} has the wrong finite width")
    _require(len(text) == (8 if found_width == "32" else 16), "SCHEMA_LITERAL_MISMATCH", f"{context} has the wrong finite-bit length")
    try:
        scalar = struct.unpack(">f" if found_width == "32" else ">d", bytes.fromhex(text))[0]
    except ValueError as error:
        _fail("SCHEMA_LITERAL_MISMATCH", f"{context} has malformed finite bits", error)
    _require(math.isfinite(scalar), "SCHEMA_LITERAL_MISMATCH", f"{context} is nonfinite")
    sign_bit = 0x80000000 if found_width == "32" else 0x8000000000000000
    _require(not (int(text, 16) & sign_bit and scalar == 0.0), "SCHEMA_LITERAL_MISMATCH", f"{context} uses negative zero")


def _canonical_value(value: Any, context: str = "$", depth: int = 0) -> None:
    """Reject values the bootstrap serializer would otherwise normalize."""

    _require(depth <= MAX_CANONICAL_DEPTH, "NONCANONICAL_ENCODING", f"{context} exceeds canonical nesting depth")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        _require(_safe_integer(value), "NONCANONICAL_ENCODING", f"{context} integer is outside the exact JSON range")
        return
    if isinstance(value, float):
        _fail("NONCANONICAL_ENCODING", f"{context} uses a decimal float; finite-bit strings are required")
    if isinstance(value, str):
        if value.startswith(("f32:", "f64:")):
            _tagged_finite_bits(value, None, context)
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            _require(isinstance(key, str), "NONCANONICAL_ENCODING", f"{context} has a non-string key")
            _canonical_value(child, f"{context}/{key}", depth + 1)
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _canonical_value(child, f"{context}[{index}]", depth + 1)
        return
    _fail("NONCANONICAL_ENCODING", f"{context} has unsupported canonical value type {type(value).__name__}")


def _json_bytes(value: Any, context: str) -> bytes:
    _canonical_value(value, context)
    try:
        encoded = canonical_json_bytes(value)
    except (CanonicalCodecError, UnicodeError) as error:
        _fail("NONCANONICAL_ENCODING", f"{context} is not strict canonical JSON", error)
    _require(isinstance(encoded, bytes), "NONCANONICAL_ENCODING", f"{context} canonical codec returned non-bytes")
    _require(len(encoded) <= MAX_CANONICAL_BYTES, "BYTE_LIMIT_EXCEEDED", f"{context} exceeds the canonical byte limit")
    return encoded


def _source_bytes(value: bytes | str, context: str) -> bytes:
    if isinstance(value, bytes):
        encoded = value
    elif isinstance(value, str):
        try:
            encoded = value.encode("utf-8", "strict")
        except UnicodeError as error:
            _fail("NONCANONICAL_ENCODING", f"{context} is not strict UTF-8", error)
    else:
        _fail("NONCANONICAL_ENCODING", f"{context} must be bytes or text")
    _require(len(encoded) <= MAX_CANONICAL_BYTES, "BYTE_LIMIT_EXCEEDED", f"{context} exceeds the canonical byte limit")
    return encoded


def _json_loads(value: bytes | str, context: str) -> Any:
    encoded = _source_bytes(value, context)
    try:
        decoded = canonical_json_loads(encoded)
    except CanonicalCodecError as error:
        _fail("NONCANONICAL_ENCODING", f"{context} is not strict canonical JSON", error)
    _canonical_value(decoded, context)
    return decoded


def _hash(value: Any, domain: str, context: str) -> str:
    _json_bytes(value, context)
    try:
        return _digest(canonical_hash(value, domain), f"{context} hash")
    except CanonicalCodecError as error:
        _fail("NONCANONICAL_ENCODING", f"{context} cannot be canonically hashed", error)


def _object(value: Any, context: str) -> dict[str, Any]:
    _require(isinstance(value, Mapping), "SCHEMA_LITERAL_MISMATCH", f"{context} must be an object")
    result = dict(value)
    _json_bytes(result, context)
    return result


def _array(value: Any, context: str) -> list[Any]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray, memoryview)),
        "SCHEMA_LITERAL_MISMATCH",
        f"{context} must be a JSON array",
    )
    result = list(value)
    _json_bytes(result, context)
    return result


def _field_names(value: Any, context: str) -> tuple[str, ...]:
    names = _array(value, context)
    result: list[str] = []
    for name in names:
        result.append(_identifier(name, context))
    _require(len(result) == len(set(result)), "SCHEMA_LITERAL_MISMATCH", f"{context} has duplicate keys")
    return tuple(result)


def _utf8_sorted(names: Sequence[str], context: str) -> tuple[str, ...]:
    result = tuple(names)
    _require(
        result == tuple(sorted(result, key=lambda name: name.encode("utf-8"))),
        "NONCANONICAL_ENCODING",
        f"{context} is not sorted by UTF-8 bytes",
    )
    return result


def _field_contract(record: Mapping[str, Any], context: str) -> dict[str, Any]:
    required = _field_names(record.get("required_keys"), f"{context}/required_keys")
    optional = _field_names(record.get("optional_keys"), f"{context}/optional_keys")
    nullable = _field_names(record.get("nullable_keys"), f"{context}/nullable_keys")
    _require(
        len(required) == len(set(required))
        and len(optional) == len(set(optional))
        and len(nullable) == len(set(nullable)),
        "SCHEMA_LITERAL_MISMATCH",
        f"{context} contains duplicate field names",
    )
    required_set = frozenset(required)
    optional_set = frozenset(optional)
    nullable_set = frozenset(nullable)
    _require(required_set.isdisjoint(optional_set), "SCHEMA_LITERAL_MISMATCH", f"{context} overlaps required and optional keys")
    known = required_set | optional_set
    _require(nullable_set <= known, "SCHEMA_LITERAL_MISMATCH", f"{context} marks an undeclared key nullable")
    nullable_fixture_order = tuple(name for name in (*required, *optional) if name in nullable_set)
    properties = _object(record.get("properties"), f"{context}/properties")
    _require(set(properties) == known, "SCHEMA_LITERAL_MISMATCH", f"{context} properties do not exactly cover declared keys")
    return {
        "required": required_set,
        "optional": optional_set,
        "nullable": nullable_set,
        "nullable_fixture_order": nullable_fixture_order,
        "known": known,
        "properties": properties,
    }

def _invariants(value: Any, context: str) -> tuple[str, ...]:
    invariants = _array(value, context)
    _require(len(invariants) <= 4096, "FANOUT_LIMIT_EXCEEDED", f"{context} has too many invariants")
    result: list[str] = []
    for index, invariant in enumerate(invariants):
        _require(isinstance(invariant, str), "SCHEMA_LITERAL_MISMATCH", f"{context}[{index}] must be prose")
        _string_bytes(invariant, f"{context}[{index}]")
        result.append(invariant)
    return tuple(result)


def _canonical_scalar(value: Any, context: str) -> None:
    _canonical_value(value, context)
    _require(
        value is None or isinstance(value, (str, bool)) or _safe_integer(value),
        "SCHEMA_LITERAL_MISMATCH",
        f"{context} must be a canonical scalar",
    )


def _string_bytes(value: str, context: str) -> int:
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as error:
        _fail("NONCANONICAL_ENCODING", f"{context} is not strict UTF-8", error)
    return len(encoded)


def _json_pointer(value: str, context: str) -> None:
    _require(value == "" or value.startswith("/"), "SCHEMA_LITERAL_MISMATCH", f"{context} is not an RFC-6901 pointer")
    index = 0
    while index < len(value):
        if value[index] == "~":
            _require(index + 1 < len(value) and value[index + 1] in "01", "SCHEMA_LITERAL_MISMATCH", f"{context} has an invalid RFC-6901 escape")
            index += 2
        else:
            index += 1


def _string_format(value: str, descriptor_format: str, context: str) -> None:
    if descriptor_format == "plain" or descriptor_format == "path":
        return
    if descriptor_format == "id":
        _identifier(value, context)
        return
    if descriptor_format == "sha256":
        _digest(value, context)
        return
    if descriptor_format == "json-pointer":
        _json_pointer(value, context)
        return
    _fail("SCHEMA_LITERAL_MISMATCH", f"{context} has unsupported string format {descriptor_format!r}")


def _descriptor(record_value: Any, context: str, max_fanout: int, depth: int) -> None:
    _require(depth <= MAX_CANONICAL_DEPTH, "SCHEMA_LITERAL_MISMATCH", f"{context} exceeds descriptor nesting depth")
    record = _object(record_value, context)
    if "one_of" in record:
        _require(set(record) == {"one_of"}, "UNKNOWN_KEY", f"{context} union descriptor fields are not exact")
        alternatives = _array(record["one_of"], f"{context}/one_of")
        _require(0 < len(alternatives) <= max_fanout, "FANOUT_LIMIT_EXCEEDED", f"{context} union cardinality is invalid")
        for index, alternative in enumerate(alternatives):
            _descriptor(alternative, f"{context}/one_of[{index}]", max_fanout, depth + 1)
        return
    if "const" in record and "type" not in record:
        _require(set(record) == {"const"}, "UNKNOWN_KEY", f"{context} constant descriptor fields are not exact")
        _canonical_value(record["const"], f"{context}/const")
        return
    kind = record.get("type")
    _require(isinstance(kind, str), "SCHEMA_LITERAL_MISMATCH", f"{context} type is missing")
    if kind == "string":
        allowed = {
            "type",
            "format",
            "enum",
            "const",
            "pattern",
            "min_length",
            "max_length",
            "min_bytes",
            "max_bytes",
            "max_decoded_bytes",
            "charset",
        }
        _require(set(record) <= allowed, "UNKNOWN_KEY", f"{context} string descriptor fields are not exact")
        descriptor_format = record.get("format")
        _require(
            descriptor_format
            in {
                None,
                "sha256",
                "finite-bits",
                "finite-f64",
                "finite-f64-bits",
                "finite_bits",
                "base64",
                "identifier-v1",
            },
            "SCHEMA_LITERAL_MISMATCH",
            f"{context} has an unsupported string format",
        )
        enum = record.get("enum")
        if enum is not None:
            values = _array(enum, f"{context}/enum")
            _require(values and all(isinstance(item, str) for item in values), "SCHEMA_LITERAL_MISMATCH", f"{context} string enum is invalid")
            _require(len(values) == len(set(values)), "SCHEMA_LITERAL_MISMATCH", f"{context} string enum has duplicates")
        if "const" in record:
            _require(isinstance(record["const"], str), "SCHEMA_LITERAL_MISMATCH", f"{context} string const is invalid")
        if "pattern" in record:
            _require(isinstance(record["pattern"], str), "SCHEMA_LITERAL_MISMATCH", f"{context} pattern is invalid")
            try:
                re.compile(record["pattern"])
            except re.error as error:
                _fail("SCHEMA_LITERAL_MISMATCH", f"{context} pattern is invalid", error)
        for suffix in ("length", "bytes"):
            lower = record.get(f"min_{suffix}", 0)
            upper = record.get(f"max_{suffix}", MAX_CANONICAL_BYTES)
            _require(
                _safe_integer(lower)
                and _safe_integer(upper)
                and 0 <= lower <= upper <= MAX_CANONICAL_BYTES,
                "BYTE_LIMIT_EXCEEDED",
                f"{context} has invalid {suffix} bounds",
            )
        if "max_decoded_bytes" in record:
            bound = record["max_decoded_bytes"]
            _require(_safe_integer(bound) and 0 <= bound <= MAX_CANONICAL_BYTES, "BYTE_LIMIT_EXCEEDED", f"{context} has invalid decoded-byte bound")
        _require(record.get("charset") in {None, "ascii", "utf8"}, "SCHEMA_LITERAL_MISMATCH", f"{context} has an unsupported charset")
        return
    if kind == "integer":
        _require(set(record) <= {"type", "minimum", "maximum", "const", "enum"}, "UNKNOWN_KEY", f"{context} integer descriptor fields are not exact")
        lower = record.get("minimum", -MAX_CANONICAL_INTEGER)
        upper = record.get("maximum", MAX_CANONICAL_INTEGER)
        _require(_safe_integer(lower) and _safe_integer(upper) and lower <= upper, "SCHEMA_LITERAL_MISMATCH", f"{context} integer bounds are invalid")
        if "const" in record:
            _require(_safe_integer(record["const"]) and lower <= record["const"] <= upper, "SCHEMA_LITERAL_MISMATCH", f"{context} integer const is invalid")
        if "enum" in record:
            values = _array(record["enum"], f"{context}/enum")
            _require(values and all(_safe_integer(item) and lower <= item <= upper for item in values), "SCHEMA_LITERAL_MISMATCH", f"{context} integer enum is invalid")
            _require(len(values) == len(set(values)), "SCHEMA_LITERAL_MISMATCH", f"{context} integer enum has duplicates")
        return
    if kind == "boolean":
        _require(set(record) <= {"type", "const", "enum"}, "UNKNOWN_KEY", f"{context} boolean descriptor fields are not exact")
        if "const" in record:
            _require(isinstance(record["const"], bool), "SCHEMA_LITERAL_MISMATCH", f"{context} boolean const is invalid")
        if "enum" in record:
            values = _array(record["enum"], f"{context}/enum")
            _require(values and all(isinstance(item, bool) for item in values), "SCHEMA_LITERAL_MISMATCH", f"{context} boolean enum is invalid")
            _require(len(values) == len(set(values)), "SCHEMA_LITERAL_MISMATCH", f"{context} boolean enum has duplicates")
        return
    if kind in {"null", "nullable-sha256", "canonical-object", "canonical-value"}:
        _require(set(record) == {"type"}, "UNKNOWN_KEY", f"{context} {kind} descriptor fields are not exact")
        return
    if kind == "finite-f64-bits":
        _require(set(record) <= {"type", "pattern"}, "UNKNOWN_KEY", f"{context} finite descriptor fields are not exact")
        if "pattern" in record:
            _require(isinstance(record["pattern"], str), "SCHEMA_LITERAL_MISMATCH", f"{context} finite pattern is invalid")
        return
    if kind == "array":
        allowed = {"type", "min_items", "max_items", "items", "tuple_items", "ordered_name_enum"}
        _require(set(record) <= allowed, "UNKNOWN_KEY", f"{context} array descriptor fields are not exact")
        _require(("items" in record) != ("tuple_items" in record), "SCHEMA_LITERAL_MISMATCH", f"{context} array must declare one item form")
        lower = record.get("min_items", 0)
        upper = record.get("max_items", max_fanout)
        _require(
            _safe_integer(lower)
            and _safe_integer(upper)
            and 0 <= lower <= upper <= max_fanout,
            "FANOUT_LIMIT_EXCEEDED",
            f"{context} array bounds are invalid",
        )
        if "items" in record:
            _descriptor(record["items"], f"{context}/items", max_fanout, depth + 1)
        else:
            items = _array(record["tuple_items"], f"{context}/tuple_items")
            _require(lower <= len(items) <= upper, "FANOUT_LIMIT_EXCEEDED", f"{context} tuple cardinality is invalid")
            for index, item in enumerate(items):
                _descriptor(item, f"{context}/tuple_items[{index}]", max_fanout, depth + 1)
        ordered = record.get("ordered_name_enum")
        if ordered is not None:
            names = _array(ordered, f"{context}/ordered_name_enum")
            _require(all(isinstance(name, str) for name in names) and len(names) == len(set(names)), "SCHEMA_LITERAL_MISMATCH", f"{context} ordered names are invalid")
        return
    if kind == "object":
        allowed = {
            "type",
            "required_keys",
            "optional_keys",
            "nullable_keys",
            "properties",
            "additional_properties",
            "invariants",
            "rules",
        }
        _require(set(record) <= allowed, "UNKNOWN_KEY", f"{context} object descriptor fields are not exact")
        _require(record.get("additional_properties", False) is False, "UNKNOWN_KEY", f"{context} permits additional properties")
        contract = _field_contract(record, context)
        for name, descriptor in contract["properties"].items():
            _descriptor(descriptor, f"{context}/properties/{name}", max_fanout, depth + 1)
        return
    _fail("SCHEMA_LITERAL_MISMATCH", f"{context} has unsupported descriptor type {kind!r}")


def _digest_descriptor(value: Any) -> bool:
    return isinstance(value, Mapping) and value.get("type") == "string" and (
        value.get("format") == "sha256"
        or value.get("pattern") == "^[0-9a-f]{64}$"
        or (
            value.get("min_length") == 64
            and value.get("max_length") == 64
            and value.get("charset") == "ascii"
        )
    )


def _schema_descriptor(value: Any, schema: str) -> bool:
    return isinstance(value, Mapping) and (
        value.get("const") == schema
        or value.get("enum") == [schema]
        or value.get("values") == [schema]
    )


def _schema_document(
    value: Any,
    entry: Mapping[str, Any],
    max_fanout: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    schema = entry["schema"]
    document = _object(value, "registered schema document")
    _require(
        _SCHEMA_DOCUMENT_REQUIRED_KEYS <= set(document)
        and set(document) <= _SCHEMA_DOCUMENT_KEYS,
        "UNKNOWN_KEY",
        "registered schema document fields are not exact",
    )
    _require(document.get("schema") == SCHEMA_DOCUMENT_SCHEMA, "SCHEMA_LITERAL_MISMATCH", "registered schema document has the wrong schema literal")
    _require(document.get("object_schema") == schema, "SCHEMA_LITERAL_MISMATCH", "registered schema document targets the wrong object schema")
    _require(document.get("type", "object") == "object", "SCHEMA_LITERAL_MISMATCH", "registered schema document root is not an object")
    _require(document.get("additional_properties", False) is False, "UNKNOWN_KEY", "registered schema document permits additional properties")
    if "consumed_semantic_subhashes" in document:
        consumed = _array(
            document["consumed_semantic_subhashes"],
            "registered schema document consumed semantic subhashes",
        )
        names: list[str] = []
        for index, raw_row in enumerate(consumed):
            row = _object(
                raw_row,
                f"registered schema document consumed semantic subhashes[{index}]",
            )
            _require(
                set(row) == {"name", "required"} and row["required"] is True,
                "SCHEMA_LITERAL_MISMATCH",
                "registered schema document has invalid consumed semantic subhash metadata",
            )
            names.append(row["name"])
        _require(
            names == entry["semantic_parent_names"],
            "SEMANTIC_PARENT_ORDER_MISMATCH",
            "registered schema document semantic subhash metadata disagrees with its entry",
        )
    contract = _field_contract(document, "registered schema document")
    _invariants(document.get("invariants"), "registered schema document/invariants")
    if "rules" in document:
        _invariants(document["rules"], "registered schema document/rules")
    for name, descriptor in contract["properties"].items():
        _descriptor(descriptor, f"registered schema document/properties/{name}", max_fanout, 0)
    _require("schema" in contract["required"], "MISSING_REQUIRED_KEY", "registered schema document does not require object schema")
    return document, contract


def _registered_parents(value: Any) -> tuple[str, ...]:
    raw_parents = tuple(_field_names(value, "registered semantic parent names"))
    parents = tuple(
        name.removesuffix("_sha256") if name.endswith("_sha256") else name
        for name in raw_parents
    )
    indices = {name: index for index, name in enumerate(SEMANTIC_PARENT_ORDER)}
    _require(all(name in indices for name in parents), "SEMANTIC_PARENT_SET_MISMATCH", "registered semantic parent is unknown")
    _require(len(parents) == len(set(parents)), "SEMANTIC_PARENT_SET_MISMATCH", "registered semantic parents are duplicated")
    _require(parents == tuple(sorted(parents, key=indices.__getitem__)), "SEMANTIC_PARENT_ORDER_MISMATCH", "registered semantic parents are reordered")
    return parents


def _validate_indexed_receipt_contract(registration: Mapping[str, Any]) -> None:
    contract = registration["field_contract"]
    required = contract["required"]
    nullable = contract["nullable"]
    properties = contract["properties"]
    _require(_RECEIPT_ENVELOPE_KEYS <= required, "MISSING_REQUIRED_KEY", "indexed receipt schema omits a required envelope field")
    _require(not (_RECEIPT_ENVELOPE_KEYS & nullable), "FORBIDDEN_NULL", "indexed receipt schema makes an envelope field nullable")
    _require(registration["self_hash_field"] == "self_sha256", "HASH_DOMAIN_MISMATCH", "indexed receipt self hash field must be self_sha256")
    _require(registration["hash_domain"] == registration["schema"], "HASH_DOMAIN_MISMATCH", "indexed receipt hash domain must equal its schema")
    _require(_schema_descriptor(properties.get("schema"), registration["schema"]), "SCHEMA_LITERAL_MISMATCH", "indexed receipt schema field is not fixed")
    for name in ("contract_root_sha256", "profile_sha256", "self_sha256"):
        _require(_digest_descriptor(properties.get(name)), "SCHEMA_LITERAL_MISMATCH", f"indexed receipt {name} must be a SHA-256 string")
    receipt_id_descriptor = properties.get("receipt_id")
    _require(isinstance(receipt_id_descriptor, Mapping), "SCHEMA_LITERAL_MISMATCH", "indexed receipt receipt_id descriptor is invalid")
    _validate_value("0" * 64, receipt_id_descriptor, "indexed receipt receipt_id descriptor", 0)
    _require(not (_LEGACY_RECEIPT_KEYS & contract["known"]), "UNKNOWN_KEY", "indexed receipt schema accepts legacy receipt fields")
    parents = properties.get("consumed_semantic_subhashes")
    _require(isinstance(parents, Mapping) and parents.get("type") == "array", "SCHEMA_LITERAL_MISMATCH", "indexed receipt parents must be an array")
    count = len(registration["semantic_parent_names"])
    _require(
        parents.get("min_items", 0) <= count <= parents.get("max_items", registration["max_fanout"]),
        "SEMANTIC_PARENT_SET_MISMATCH",
        "indexed receipt parent descriptor cannot represent the registered parent set",
    )
    row = parents.get("items")
    _require(isinstance(row, Mapping) and row.get("type") == "object", "SCHEMA_LITERAL_MISMATCH", "indexed receipt parent rows must be objects")
    row_contract = _field_contract(row, "indexed receipt parent descriptor")
    _require(
        row_contract["required"] == {"name", "sha256"}
        and not row_contract["optional"]
        and not row_contract["nullable"],
        "SCHEMA_LITERAL_MISMATCH",
        "indexed receipt parent row fields are not exact",
    )
    _require(_digest_descriptor(row_contract["properties"].get("sha256")), "SCHEMA_LITERAL_MISMATCH", "indexed receipt parent digest must be SHA-256")


def _validate_value(value: Any, descriptor: Mapping[str, Any], context: str, depth: int) -> None:
    _require(depth <= MAX_CANONICAL_DEPTH, "NONCANONICAL_ENCODING", f"{context} exceeds receipt nesting depth")
    if "one_of" in descriptor:
        accepted = 0
        for alternative in descriptor["one_of"]:
            try:
                _validate_value(value, alternative, context, depth + 1)
            except PROFILE_MISMATCH:
                continue
            accepted += 1
        _require(accepted == 1, "SCHEMA_LITERAL_MISMATCH", f"{context} does not match exactly one union alternative")
        return
    if "const" in descriptor and "type" not in descriptor:
        expected = descriptor["const"]
        _require(type(value) is type(expected) and value == expected, "SCHEMA_LITERAL_MISMATCH", f"{context} does not equal its constant")
        return
    kind = descriptor.get("type")
    if kind in {"string", "finite-f64-bits"}:
        _require(isinstance(value, str), "SCHEMA_LITERAL_MISMATCH", f"{context} must be a string")
        _require(value in descriptor.get("enum", [value]), "SCHEMA_LITERAL_MISMATCH", f"{context} is outside its string enum")
        if "const" in descriptor:
            _require(value == descriptor["const"], "SCHEMA_LITERAL_MISMATCH", f"{context} does not equal its string constant")
        _require(
            descriptor.get("min_length", 0) <= len(value) <= descriptor.get("max_length", MAX_CANONICAL_BYTES),
            "BYTE_LIMIT_EXCEEDED",
            f"{context} exceeds its string length limit",
        )
        encoded = value.encode("utf-8", "strict")
        _require(
            descriptor.get("min_bytes", 0) <= len(encoded) <= descriptor.get("max_bytes", MAX_CANONICAL_BYTES),
            "BYTE_LIMIT_EXCEEDED",
            f"{context} exceeds its string byte limit",
        )
        if descriptor.get("charset") == "ascii":
            try:
                value.encode("ascii", "strict")
            except UnicodeEncodeError as error:
                _fail("SCHEMA_LITERAL_MISMATCH", f"{context} is not ASCII", error)
        pattern = descriptor.get("pattern")
        _require(pattern is None or re.fullmatch(pattern, value) is not None, "SCHEMA_LITERAL_MISMATCH", f"{context} does not match its pattern")
        descriptor_format = descriptor.get("format")
        if descriptor_format == "sha256":
            _digest(value, context)
        elif kind == "finite-f64-bits" or descriptor_format in {"finite-bits", "finite-f64", "finite-f64-bits", "finite_bits"}:
            _tagged_finite_bits(value, None, context)
        elif descriptor_format == "base64":
            try:
                decoded = base64.b64decode(value, validate=True)
            except (ValueError, TypeError) as error:
                _fail("SCHEMA_LITERAL_MISMATCH", f"{context} is not base64", error)
            _require(base64.b64encode(decoded).decode("ascii") == value, "NONCANONICAL_ENCODING", f"{context} base64 is not canonical")
            _require(len(decoded) <= descriptor.get("max_decoded_bytes", MAX_CANONICAL_BYTES), "BYTE_LIMIT_EXCEEDED", f"{context} decoded bytes exceed their limit")
        elif descriptor_format == "identifier-v1":
            _identifier(value, context)
        return
    if kind == "integer":
        _require(_safe_integer(value), "SCHEMA_LITERAL_MISMATCH", f"{context} must be an integer")
        _require(descriptor.get("minimum", -MAX_CANONICAL_INTEGER) <= value <= descriptor.get("maximum", MAX_CANONICAL_INTEGER), "SCHEMA_LITERAL_MISMATCH", f"{context} integer is outside its bounds")
        _require(value in descriptor.get("enum", [value]), "SCHEMA_LITERAL_MISMATCH", f"{context} is outside its integer enum")
        if "const" in descriptor:
            _require(value == descriptor["const"], "SCHEMA_LITERAL_MISMATCH", f"{context} does not equal its integer constant")
        return
    if kind == "boolean":
        _require(isinstance(value, bool), "SCHEMA_LITERAL_MISMATCH", f"{context} must be boolean")
        _require(value in descriptor.get("enum", [value]), "SCHEMA_LITERAL_MISMATCH", f"{context} is outside its boolean enum")
        if "const" in descriptor:
            _require(value is descriptor["const"], "SCHEMA_LITERAL_MISMATCH", f"{context} does not equal its boolean constant")
        return
    if kind == "null":
        _require(value is None, "SCHEMA_LITERAL_MISMATCH", f"{context} must be null")
        return
    if kind == "nullable-sha256":
        if value is not None:
            _digest(value, context)
        return
    if kind == "canonical-object":
        _require(isinstance(value, Mapping), "SCHEMA_LITERAL_MISMATCH", f"{context} must be an object")
        _json_bytes(value, context)
        return
    if kind == "canonical-value":
        _json_bytes(value, context)
        return
    if kind == "array":
        items = _array(value, context)
        _require(
            descriptor.get("min_items", 0) <= len(items) <= descriptor.get("max_items", registration_fanout := 4096),
            "FANOUT_LIMIT_EXCEEDED",
            f"{context} array length is outside declared bounds",
        )
        if "tuple_items" in descriptor:
            expected = _array(descriptor["tuple_items"], f"{context} tuple descriptor")
            _require(len(items) == len(expected), "FANOUT_LIMIT_EXCEEDED", f"{context} tuple length is wrong")
            rows = zip(items, expected, strict=True)
        else:
            rows = ((child, descriptor["items"]) for child in items)
        for index, (child, child_descriptor) in enumerate(rows):
            _validate_value(child, _object(child_descriptor, f"{context} item descriptor"), f"{context}[{index}]", depth + 1)
        ordered = descriptor.get("ordered_name_enum")
        if ordered is not None:
            names = [item.get("name") if isinstance(item, Mapping) else None for item in items]
            expected_names = [name for name in ordered if name in names]
            _require(len(names) == len(set(names)) and all(name in ordered for name in names) and names == expected_names, "SEMANTIC_PARENT_ORDER_MISMATCH", f"{context} ordered names differ")
        del registration_fanout
        return
    if kind == "object":
        contract = _field_contract(descriptor, f"{context} descriptor")
        _validate_object_contract(value, contract, context, depth + 1)
        return
    _fail("SCHEMA_LITERAL_MISMATCH", f"{context} has unsupported descriptor type {kind!r}")


def _validate_object_contract(value: Any, contract: Mapping[str, Any], context: str, depth: int = 0) -> dict[str, Any]:
    record = _object(value, context)
    _require(depth <= MAX_CANONICAL_DEPTH, "NONCANONICAL_ENCODING", f"{context} exceeds receipt nesting depth")
    actual = frozenset(record)
    unknown = actual - contract["known"]
    missing = contract["required"] - actual
    _require(not unknown, "UNKNOWN_KEY", f"{context} has undeclared fields {sorted(unknown)!r}")
    _require(not missing, "MISSING_REQUIRED_KEY", f"{context} omits required fields {sorted(missing)!r}")
    for name, child in record.items():
        if child is None:
            _require(name in contract["nullable"], "FORBIDDEN_NULL", f"{context}/{name} is not nullable")
        else:
            _validate_value(child, _object(contract["properties"][name], f"{context}/{name} descriptor"), f"{context}/{name}", depth + 1)
    return record


def _receipt_id(record: Mapping[str, Any], schema: str) -> str:
    material = {name: value for name, value in record.items() if name not in {"receipt_id", "self_sha256"}}
    return _hash(material, f"{schema}.receipt-id", "receipt identifier")


def _object_self_hash(record: Mapping[str, Any], registration: Mapping[str, Any]) -> str:
    if registration["inline_schema_document"]:
        return _hash(record, registration["hash_domain"], "registered schema document")
    field = registration["self_hash_field"]
    _require(field in record, "MISSING_REQUIRED_KEY", f"registered object omits {field}")
    material = {name: value for name, value in record.items() if name != field}
    return _hash(material, registration["hash_domain"], "registered object")


def _validate_receipt_envelope(
    record: Mapping[str, Any],
    registration: Mapping[str, Any],
    *,
    expected_root: str | None = None,
    expected_profile: str | None = None,
    parent_values: Mapping[str, str] | None = None,
) -> None:
    schema = registration["schema"]
    _require(record.get("schema") == schema, "SCHEMA_LITERAL_MISMATCH", "indexed receipt schema is wrong")
    root = _digest(record.get("contract_root_sha256"), "receipt contract_root_sha256")
    profile = _digest(record.get("profile_sha256"), "receipt profile_sha256")
    if expected_root is not None:
        _require(root == expected_root, "HASH_DOMAIN_MISMATCH", "receipt contract root does not match the selected root")
    if expected_profile is not None:
        _require(profile == expected_profile, "HASH_DOMAIN_MISMATCH", "receipt profile does not match the selected profile")
    rows = _array(record.get("consumed_semantic_subhashes"), "receipt consumed semantic subhashes")
    names = registration["semantic_parent_names"]
    _require(len(rows) == len(names), "SEMANTIC_PARENT_SET_MISMATCH", "receipt semantic parent count is wrong")
    found: list[str] = []
    for row in rows:
        parent = _object(row, "receipt semantic parent")
        _require(set(parent) == {"name", "sha256"}, "UNKNOWN_KEY", "receipt semantic parent fields are not exact")
        raw_name = parent.get("name")
        name = _normalise_parent_name(raw_name, "receipt semantic parent")
        found.append(name)
        digest = _digest(parent.get("sha256"), f"receipt semantic parent {name}")
        if parent_values is not None:
            _require(parent_values.get(name) == digest, "SEMANTIC_PARENT_DIGEST_MISMATCH", f"receipt semantic parent digest is wrong for {name}")
    _require(frozenset(found) == frozenset(names), "SEMANTIC_PARENT_SET_MISMATCH", "receipt semantic parents are missing or duplicated")
    _require(tuple(found) == tuple(names), "SEMANTIC_PARENT_ORDER_MISMATCH", "receipt semantic parents are reordered")


def _validate_registered_object(value: Any, registration: Mapping[str, Any], context: str) -> dict[str, Any]:
    record = _validate_object_contract(value, registration["field_contract"], context)
    _require(record.get("schema") == registration["schema"], "SCHEMA_LITERAL_MISMATCH", f"{context} schema is wrong")
    _require(len(_json_bytes(record, context)) <= registration["max_encoded_bytes"], "BYTE_LIMIT_EXCEEDED", f"{context} exceeds registered byte limit")
    return record


def _validate_fixture_set(registration: Mapping[str, Any]) -> None:
    fixture_set = _object(registration["canonical_fixture_set"], "registered canonical fixture set")
    _require(set(fixture_set) == _FIXTURE_SET_KEYS, "UNKNOWN_KEY", "registered fixture-set fields are not exact")
    minimal = _validate_registered_object(fixture_set["minimal_valid"], registration, "minimal fixture")
    maximal = _validate_registered_object(fixture_set["maximal_valid"], registration, "maximal fixture")
    contract = registration["field_contract"]
    _require(not (set(minimal) & contract["optional"]), "SCHEMA_LITERAL_MISMATCH", "minimal fixture includes optional fields")
    _require(contract["optional"] <= set(maximal), "MISSING_REQUIRED_KEY", "maximal fixture omits optional fields")
    nullable_fixtures = _array(fixture_set["nullable_valid"], "nullable fixture set")
    nullable_keys = tuple(registration["nullable_keys"])
    exercised: set[str] = set()
    for index, fixture in enumerate(nullable_fixtures):
        candidate = _validate_registered_object(fixture, registration, f"nullable fixture {index}")
        null_fields = {
            name for name in nullable_keys if candidate.get(name) is None
        }
        _require(null_fields, "FORBIDDEN_NULL", f"nullable fixture {index} exercises no nullable field")
        exercised.update(null_fields)
    _require(
        exercised == set(nullable_keys),
        "FANOUT_LIMIT_EXCEEDED",
        "nullable fixtures do not exercise every nullable field",
    )
    if "fixture_id" in contract["known"]:
        for label, fixture in (("minimal", minimal), ("maximal", maximal)):
            if "fixture_id" in fixture:
                _require(fixture["fixture_id"] == fixture_id, "SCHEMA_LITERAL_MISMATCH", f"{label} fixture_id does not match registry fixture_id")
        for fixture in nullable_fixtures:
            if isinstance(fixture, Mapping) and "fixture_id" in fixture:
                _require(fixture["fixture_id"] == fixture_id, "SCHEMA_LITERAL_MISMATCH", "nullable fixture_id does not match registry fixture_id")
    else:
        _require(
            all("fixture_id" not in fixture for fixture in (minimal, maximal, *nullable_fixtures)),
            "UNKNOWN_KEY",
            "fixture set injects an undeclared fixture_id",
        )
    declared = _digest(registration["canonical_fixture_set_sha256"], "registered canonical_fixture_set_sha256")
    computed = _hash(
        fixture_set,
        SCHEMA_FIXTURE_SET_HASH_DOMAIN,
        "registered canonical fixture set",
    )
    _require(computed == declared, "FIXTURE_SET_HASH_MISMATCH", "registered canonical fixture-set hash does not match")


def _validate_mutation_controls(registration: Mapping[str, Any]) -> None:
    raw_controls = registration["mutation_controls"]
    declared = _digest(registration["mutation_controls_sha256"], "registered mutation_controls_sha256")
    computed = _hash(
        raw_controls,
        SCHEMA_MUTATION_CONTROLS_HASH_DOMAIN,
        "registered mutation controls",
    )
    _require(computed == declared, "MUTATION_CONTROLS_HASH_MISMATCH", "registered mutation-control hash does not match")
    if isinstance(raw_controls, Mapping):
        wrapper = _object(raw_controls, "registered mutation controls")
        _require(
            set(wrapper) == {"schema_under_test", "controls"},
            "UNKNOWN_KEY",
            "registered mutation-control wrapper fields are not exact",
        )
        _require(
            wrapper.get("schema_under_test") == registration["schema"],
            "SCHEMA_LITERAL_MISMATCH",
            "registered mutation-control wrapper schema is wrong",
        )
        wrapped_controls = _array(wrapper.get("controls"), "registered mutation-control wrapper controls")
        controls: list[dict[str, Any]] = []
        for index, item in enumerate(wrapped_controls):
            wrapped = _object(item, f"registered mutation controls[{index}]")
            _require(
                set(wrapped) == {"control_id", "base_fixture", "mutation", "expected_error_code"},
                "UNKNOWN_KEY",
                f"registered mutation control {index} fields are not exact",
            )
            mutation = _object(wrapped.get("mutation"), f"registered mutation control {index} mutation")
            _require(
                set(mutation) == {"op", "path", "value"},
                "UNKNOWN_KEY",
                f"registered mutation control {index} mutation fields are not exact",
            )
            operation = mutation.get("op")
            _require(
                operation in {"add", "insert", "delete", "replace", "reorder"},
                "SCHEMA_LITERAL_MISMATCH",
                f"registered mutation control {index} has an invalid operation",
            )
            controls.append(
                {
                    "control_id": wrapped.get("control_id"),
                    "base_fixture": wrapped.get("base_fixture"),
                    "operation": "insert" if operation == "add" else operation,
                    "pointer": mutation.get("path"),
                    "value": mutation.get("value"),
                    "expected_error": wrapped.get("expected_error_code"),
                }
            )
    else:
        controls = _array(raw_controls, "registered mutation controls")
    _require(0 < len(controls) <= 4096, "FANOUT_LIMIT_EXCEEDED", "registered mutation controls have invalid cardinality")
    identifiers: set[str] = set()
    for index, item in enumerate(controls):
        control = _object(item, f"registered mutation controls[{index}]")
        _require(set(control) == _MUTATION_CONTROL_KEYS, "UNKNOWN_KEY", f"registered mutation control {index} fields are not exact")
        control_id = _identifier(control.get("control_id"), f"registered mutation control {index} id")
        _require(control_id not in identifiers, "SCHEMA_LITERAL_MISMATCH", "registered mutation controls have duplicate IDs")
        identifiers.add(control_id)
        _require(control.get("base_fixture") in {"minimal_valid", "maximal_valid", "nullable_valid"}, "SCHEMA_LITERAL_MISMATCH", f"registered mutation control {control_id} has an invalid base fixture")
        _require(control.get("operation") in {"insert", "delete", "replace", "reorder"}, "SCHEMA_LITERAL_MISMATCH", f"registered mutation control {control_id} has an invalid operation")
        pointer = control.get("pointer")
        _require(isinstance(pointer, str), "SCHEMA_LITERAL_MISMATCH", f"registered mutation control {control_id} pointer is invalid")
        _json_pointer(pointer, f"registered mutation control {control_id} pointer")
        _canonical_value(control.get("value"), f"registered mutation control {control_id} value")
        _require(isinstance(control.get("expected_error"), str) and control["expected_error"], "SCHEMA_LITERAL_MISMATCH", f"registered mutation control {control_id} expected error is invalid")


def _registered_registration(
    schema: str,
    registry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    _identifier(schema, "registered object schema")
    registration = _registry_records(registry).get(schema)
    _require(registration is not None, "OBJECT_CLASS_MISMATCH", f"schema is not registered: {schema}")
    _require(
        not registration["indexed_envelope"],
        "OBJECT_CLASS_MISMATCH",
        f"schema uses the standard indexed-receipt envelope: {schema}",
    )
    return registration


def _registered_object_source(value: Mapping[str, Any] | bytes | str) -> dict[str, Any]:
    if isinstance(value, (bytes, str)):
        raw = _source_bytes(value, "registered object")
        decoded = _json_loads(raw, "registered object")
        _require(
            _json_bytes(decoded, "registered object") == raw,
            "NONCANONICAL_ENCODING",
            "registered object bytes are not canonical",
        )
        return _object(decoded, "registered object")
    return _object(value, "registered object")


def _registered_root_identity(contract_root: Any | None) -> str | None:
    if contract_root is None:
        return None
    try:
        root = validate_contract_root(contract_root)
    except (CanonicalCodecError, PROFILE_MISMATCH, TypeError, ValueError) as error:
        _fail("HASH_DOMAIN_MISMATCH", "selected contract root is invalid", error)
    return _digest(root.sha256, "selected contract root identity")


def _validate_registered_parents(
    record: Mapping[str, Any],
    registration: Mapping[str, Any],
    context: str,
) -> None:
    field = "consumed_semantic_subhashes"
    if field not in registration["field_contract"]["known"] or field not in record:
        return
    rows = _array(record[field], f"{context} semantic parents")
    names = registration["semantic_parent_names"]
    _require(len(rows) == len(names), "SEMANTIC_PARENT_SET_MISMATCH", f"{context} semantic parent count is wrong")
    found: list[str] = []
    for row in rows:
        parent = _object(row, f"{context} semantic parent")
        _require(set(parent) == {"name", "sha256"}, "UNKNOWN_KEY", f"{context} semantic parent fields are not exact")
        name = _normalise_parent_name(parent.get("name"), f"{context} semantic parent")
        found.append(name)
        _digest(parent.get("sha256"), f"{context} semantic parent {name}")
    _require(frozenset(found) == frozenset(names), "SEMANTIC_PARENT_SET_MISMATCH", f"{context} semantic parents are missing or duplicated")
    _require(tuple(found) == tuple(names), "SEMANTIC_PARENT_ORDER_MISMATCH", f"{context} semantic parents are reordered")


def _validate_registered_root(
    record: Mapping[str, Any],
    registration: Mapping[str, Any],
    expected_root: str | None,
    context: str,
) -> None:
    field = "contract_root_sha256"
    if expected_root is not None and field in record:
        _require(
            record[field] == expected_root,
            "HASH_DOMAIN_MISMATCH",
            f"{context} contract root does not match the selected root",
        )


def _registered_self_hash(record: Mapping[str, Any], registration: Mapping[str, Any], context: str) -> str | None:
    field = registration["self_hash_field"]
    if registration["inline_schema_document"] or field not in registration["field_contract"]["known"]:
        return None
    declared = _digest(record.get(field), f"{context} {field}")
    _require(
        _object_self_hash(record, registration) == declared,
        "SELF_HASH_MISMATCH",
        f"{context} self hash does not match",
    )
    return declared


def build_registered_object(
    schema: str,
    payload: Mapping[str, Any] | None = None,
    *,
    contract_root: Any | None = None,
) -> dict[str, Any]:
    """Build one exact non-receipt object from a registered schema."""

    registration = _registered_registration(schema, None)
    record = {} if payload is None else dict(_object(payload, "registered object payload"))
    if "schema" in record:
        _require(record["schema"] == schema, "SCHEMA_LITERAL_MISMATCH", "registered object schema is wrong")
    else:
        record["schema"] = schema
    field = registration["self_hash_field"]
    if not registration["inline_schema_document"] and field in registration["field_contract"]["known"] and field not in record:
        record[field] = "0" * 64
    _validate_registered_object(record, registration, "registered object")
    expected_root = _registered_root_identity(contract_root)
    _validate_registered_root(record, registration, expected_root, "registered object")
    _validate_registered_parents(record, registration, "registered object")
    if field in registration["field_contract"]["known"]:
        record[field] = _object_self_hash(record, registration)
    _validate_registered_object(record, registration, "registered object")
    _validate_registered_root(record, registration, expected_root, "registered object")
    _validate_registered_parents(record, registration, "registered object")
    _registered_self_hash(record, registration, "registered object")
    return record


def validate_registered_object(
    value: Mapping[str, Any] | bytes | str,
    *,
    expected_schema: str | None = None,
    contract_root: Any | None = None,
) -> dict[str, Any]:
    """Validate one canonical non-receipt object from a registered schema."""

    record = _registered_object_source(value)
    schema = _identifier(record.get("schema"), "registered object schema")
    if expected_schema is not None:
        _require(schema == expected_schema, "SCHEMA_LITERAL_MISMATCH", f"registered object schema is {schema}, not {expected_schema}")
    registration = _registered_registration(schema, None)
    record = _validate_registered_object(record, registration, "registered object")
    expected_root = _registered_root_identity(contract_root)
    _validate_registered_root(record, registration, expected_root, "registered object")
    _validate_registered_parents(record, registration, "registered object")
    _registered_self_hash(record, registration, "registered object")
    return dict(record)

def _entry(raw_entry: Any) -> dict[str, Any]:
    entry = _object(raw_entry, "schema registry entry")
    _require(set(entry) == _ENTRY_KEYS, "UNKNOWN_KEY", "schema registry entry fields are not exact")
    schema = _identifier(entry.get("schema"), "registered schema")
    version = entry.get("version")
    _require(_safe_integer(version) and version > 0, "SCHEMA_LITERAL_MISMATCH", "registered schema version is invalid")
    version_match = _SCHEMA_VERSION.search(schema)
    _require(version_match is not None and int(version_match.group(1)) == version, "SCHEMA_LITERAL_MISMATCH", "registered schema version does not match its literal")
    object_class = entry.get("object_class")
    _require(object_class in _OBJECT_CLASSES, "OBJECT_CLASS_MISMATCH", "registered object class is invalid")
    lifecycle = entry.get("lifecycle")
    _require(
        isinstance(lifecycle, (str, Mapping)),
        "LIFECYCLE_MISMATCH",
        "registered lifecycle is invalid",
    )
    _canonical_value(lifecycle, "registered lifecycle")
    max_encoded_bytes = entry.get("max_encoded_bytes")
    _require(_safe_integer(max_encoded_bytes) and 0 < max_encoded_bytes <= MAX_CANONICAL_BYTES, "BYTE_LIMIT_EXCEEDED", "registered byte limit is invalid")
    max_fanout = entry.get("max_fanout")
    _require(_safe_integer(max_fanout) and 0 <= max_fanout <= 4096, "FANOUT_LIMIT_EXCEEDED", "registered fanout limit is invalid")
    parents = _registered_parents(entry.get("semantic_parent_names"))
    document, contract = _schema_document(entry.get("schema_document"), entry, max_fanout)
    declared_document_hash = _digest(entry.get("schema_document_sha256"), "registered schema_document_sha256")
    computed_document_hash = _hash(document, SCHEMA_DOCUMENT_SCHEMA, "registered schema document")
    _require(computed_document_hash == declared_document_hash, "SELF_HASH_MISMATCH", "entry schema-document hash does not match")
    fixture_id = entry.get("fixture_id")
    _require(
        isinstance(fixture_id, str)
        and 0 < _string_bytes(fixture_id, "registered fixture_id") <= 4096,
        "SCHEMA_LITERAL_MISMATCH",
        "registered fixture_id is invalid",
    )
    hash_domain = _identifier(entry.get("hash_domain"), "registered hash_domain")
    self_hash_field = _identifier(entry.get("self_hash_field"), "registered self_hash_field")
    inline_schema_document = schema == SCHEMA_DOCUMENT_SCHEMA
    if inline_schema_document:
        _require(self_hash_field == "schema_document_sha256", "HASH_DOMAIN_MISMATCH", "inline schema-document identity field is wrong")
        _require(hash_domain == SCHEMA_DOCUMENT_SCHEMA, "HASH_DOMAIN_MISMATCH", "inline schema-document hash domain is wrong")
        _require(self_hash_field not in contract["known"], "UNKNOWN_KEY", "inline schema document exposes its enclosing identity")
    else:
        _require(self_hash_field in contract["required"], "MISSING_REQUIRED_KEY", "registered self hash field is not required")
        _require(self_hash_field not in contract["nullable"], "FORBIDDEN_NULL", "registered self hash field is nullable")
        _require(_digest_descriptor(contract["properties"].get(self_hash_field)), "SCHEMA_LITERAL_MISMATCH", "registered self hash field is not a SHA-256 string")
    indexed_envelope = (
        object_class == "indexed-receipt"
        and _RECEIPT_ENVELOPE_KEYS <= contract["required"]
    )
    _require(entry.get("independent_verifier") == "stdlib-schema-replay-v1", "SCHEMA_LITERAL_MISMATCH", "registered independent verifier is invalid")
    _require(entry.get("migration_policy") == "new-schema-version-and-contract-root-v1", "SCHEMA_LITERAL_MISMATCH", "registered migration policy is invalid")
    registration = {
        "schema": schema,
        "version": version,
        "object_class": object_class,
        "lifecycle": lifecycle,
        "max_encoded_bytes": max_encoded_bytes,
        "max_fanout": max_fanout,
        "semantic_parent_names": parents,
        "schema_document": document,
        "schema_document_sha256": declared_document_hash,
        "fixture_id": fixture_id,
        "canonical_fixture_set": entry.get("canonical_fixture_set"),
        "canonical_fixture_set_sha256": entry.get("canonical_fixture_set_sha256"),
        "mutation_controls": entry.get("mutation_controls"),
        "mutation_controls_sha256": entry.get("mutation_controls_sha256"),
        "hash_domain": hash_domain,
        "self_hash_field": self_hash_field,
        "inline_schema_document": inline_schema_document,
        "indexed_envelope": indexed_envelope,
        "field_contract": contract,
        "nullable_keys": contract["nullable_fixture_order"],
    }
    if indexed_envelope:
        _validate_indexed_receipt_contract(registration)
    _validate_fixture_set(registration)
    _validate_mutation_controls(registration)
    return registration


def _referenced_schemas(descriptor: Mapping[str, Any]) -> tuple[tuple[str, int], ...]:
    if "one_of" in descriptor:
        return tuple(
            reference
            for alternative in descriptor["one_of"]
            for reference in _referenced_schemas(alternative)
        )
    kind = descriptor.get("type")
    if kind == "ref":
        return ((descriptor["schema"], descriptor["max_encoded_bytes"]),)
    if kind == "object":
        return tuple(
            reference
            for child in descriptor["properties"].values()
            for reference in _referenced_schemas(child)
        )
    if kind == "array":
        descriptors = (
            descriptor.get("tuple_items", [])
            if "tuple_items" in descriptor
            else [descriptor["items"]]
        )
        return tuple(
            reference
            for child in descriptors
            for reference in _referenced_schemas(child)
        )
    return ()


_DEFAULT_REGISTRY_CACHE: dict[str, dict[str, Any]] | None = None


def _registry_records(source: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    global _DEFAULT_REGISTRY_CACHE
    if source is None and _DEFAULT_REGISTRY_CACHE is not None:
        return _DEFAULT_REGISTRY_CACHE
    raw = SCHEMA_REGISTRY if source is None else source
    _require(isinstance(raw, Mapping), "SCHEMA_LITERAL_MISMATCH", "schema registry must be an object")
    registry = dict(raw)
    _require(set(registry) == _REGISTRY_KEYS, "UNKNOWN_KEY", "schema registry fields are not exact")
    _require(registry.get("schema") == SCHEMA_REGISTRY_SCHEMA, "SCHEMA_LITERAL_MISMATCH", "schema registry has the wrong schema literal")
    _require(registry.get("registry_id") == "qi-flow-schema-registry-v1", "SCHEMA_LITERAL_MISMATCH", "schema registry has the wrong registry_id")
    raw_entries = registry.get("entries")
    _require(
        isinstance(raw_entries, Sequence)
        and not isinstance(raw_entries, (str, bytes, bytearray, memoryview)),
        "SCHEMA_LITERAL_MISMATCH",
        "schema registry entries must be an array",
    )
    entries = list(raw_entries)
    _require(0 < len(entries) <= 4096, "FANOUT_LIMIT_EXCEEDED", "schema registry entry count is invalid")
    declared_self = _digest(registry.get("self_sha256"), "schema registry self_sha256")
    if source is None:
        _require(
            declared_self == SCHEMA_REGISTRY_MANIFEST["self_sha256"],
            "SELF_HASH_MISMATCH",
            "schema registry identity does not match its verified shard manifest",
        )
    else:
        computed_self = _hash(
            {name: value for name, value in registry.items() if name != "self_sha256"},
            SCHEMA_REGISTRY_SCHEMA,
            "schema registry",
        )
        _require(computed_self == declared_self, "SELF_HASH_MISMATCH", "schema registry self hash does not match")
    result: dict[str, dict[str, Any]] = {}
    entry_order: list[str] = []
    for raw_entry in entries:
        registration = _entry(raw_entry)
        _require(registration["schema"] not in result, "SCHEMA_LITERAL_MISMATCH", "schema registry has duplicate schemas")
        entry_order.append(registration["schema"])
        result[registration["schema"]] = registration
    _utf8_sorted(entry_order, "schema registry entries")
    for registration in result.values():
        for descriptor in registration["field_contract"]["properties"].values():
            for target_schema, target_limit in _referenced_schemas(_object(descriptor, "registered reference descriptor")):
                target = result.get(target_schema)
                _require(target is not None, "UNRESOLVED_REFERENCE", f"registered reference targets unknown schema {target_schema}")
                _require(target_limit <= target["max_encoded_bytes"], "BYTE_LIMIT_EXCEEDED", f"registered reference limit exceeds {target_schema}")
    if source is None:
        _DEFAULT_REGISTRY_CACHE = result
    return result


def _registration(schema: str, registry: Mapping[str, Any] | None) -> dict[str, Any]:
    _identifier(schema, "receipt schema")
    parsed = _registry_records(registry)
    registration = parsed.get(schema)
    _require(registration is not None, "OBJECT_CLASS_MISMATCH", f"schema is not registered: {schema}")
    _require(registration["indexed_envelope"], "OBJECT_CLASS_MISMATCH", f"schema does not use the standard indexed-receipt envelope: {schema}")
    _require(registration["object_class"] == "indexed-receipt", "OBJECT_CLASS_MISMATCH", f"schema is not an indexed receipt: {schema}")
    return registration


def _normalise_parent_name(value: Any, context: str) -> str:
    _require(isinstance(value, str), "SEMANTIC_PARENT_SET_MISMATCH", f"{context} parent name is invalid")
    if value in SEMANTIC_PARENT_ORDER:
        return value
    for name, profile_field in _PROFILE_PARENT_FIELDS.items():
        if value == profile_field:
            return name
    _fail("SEMANTIC_PARENT_SET_MISMATCH", f"{context} parent name is unknown: {value!r}")


def _semantic_values(value: Any, context: str) -> dict[str, str]:
    if isinstance(value, Mapping):
        result: dict[str, str] = {}
        for name, profile_field in _PROFILE_PARENT_FIELDS.items():
            matches = [key for key in (name, profile_field) if key in value]
            _require(len(matches) == 1, "SEMANTIC_PARENT_SET_MISMATCH", f"{context} omits or aliases {name}")
            raw = value[matches[0]]
            digest = raw.get("sha256") if isinstance(raw, Mapping) else raw
            result[name] = _digest(digest, f"{context} {name}")
        _require(len(value) == len(SEMANTIC_PARENT_ORDER), "SEMANTIC_PARENT_SET_MISMATCH", f"{context} has unknown semantic parents")
        return result
    rows = _array(value, context)
    _require(len(rows) == len(SEMANTIC_PARENT_ORDER), "SEMANTIC_PARENT_SET_MISMATCH", f"{context} parent count is wrong")
    result = {}
    order: list[str] = []
    for row in rows:
        item = _object(row, f"{context} parent")
        _require(set(item) == {"name", "sha256"}, "UNKNOWN_KEY", f"{context} parent row fields are not exact")
        name = _normalise_parent_name(item.get("name"), context)
        order.append(name)
        result[name] = _digest(item.get("sha256"), f"{context} {name}")
    _require(frozenset(order) == frozenset(SEMANTIC_PARENT_ORDER), "SEMANTIC_PARENT_SET_MISMATCH", f"{context} parent set is wrong")
    _require(tuple(order) == SEMANTIC_PARENT_ORDER, "SEMANTIC_PARENT_ORDER_MISMATCH", f"{context} parent order is wrong")
    return result


def _resolved_context(
    *,
    contract_root: Any | None,
    contract_root_sha256: str | None,
    profile: Any,
    profile_sha256: str | None,
    semantic_subhashes: Any,
) -> tuple[str, str, dict[str, str]]:
    _require(profile is not None, "HASH_DOMAIN_MISMATCH", "a selected profile is required")
    try:
        selected_profile = validate_profile(profile)
    except (CanonicalCodecError, PROFILE_MISMATCH, TypeError, ValueError) as error:
        _fail("HASH_DOMAIN_MISMATCH", "selected profile is invalid", error)
    selected_root = selected_profile.contract_root if contract_root is None else contract_root
    try:
        root = validate_contract_root(selected_root)
    except (CanonicalCodecError, PROFILE_MISMATCH, TypeError, ValueError) as error:
        _fail("HASH_DOMAIN_MISMATCH", "selected contract root is invalid", error)
    root_id = _digest(root.sha256, "selected contract root identity")
    profile_id = _digest(selected_profile.profile_sha256, "selected profile identity")
    _require(selected_profile.contract_root_sha256 == root_id, "HASH_DOMAIN_MISMATCH", "selected profile/root identities do not agree")
    if contract_root_sha256 is not None:
        _require(_digest(contract_root_sha256, "explicit contract root identity") == root_id, "HASH_DOMAIN_MISMATCH", "explicit contract root identity does not match")
    if profile_sha256 is not None:
        _require(_digest(profile_sha256, "explicit profile identity") == profile_id, "HASH_DOMAIN_MISMATCH", "explicit profile identity does not match")
    actual_parents = _semantic_values(selected_profile.semantic_subhashes, "selected profile semantic subhashes")
    if semantic_subhashes is not None:
        supplied = _semantic_values(semantic_subhashes, "supplied semantic subhashes")
        _require(supplied == actual_parents, "SEMANTIC_PARENT_DIGEST_MISMATCH", "supplied semantic subhashes do not match the selected profile")
    return root_id, profile_id, actual_parents


def _parent_records(names: Sequence[str], values: Mapping[str, str]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for name in names:
        _require(name in values, "SEMANTIC_PARENT_SET_MISMATCH", f"selected profile omits semantic parent {name}")
        result.append({"name": f"{name}_sha256", "sha256": _digest(values[name], f"selected profile semantic parent {name}")})
    return result


def _payload(payload: Mapping[str, Any] | None, fields: Mapping[str, Any]) -> dict[str, Any]:
    result = {} if payload is None else _object(payload, "receipt payload")
    duplicate = set(result) & set(fields)
    _require(not duplicate, "UNKNOWN_KEY", f"receipt payload repeats fields {sorted(duplicate)!r}")
    result.update(fields)
    reserved = _RECEIPT_ENVELOPE_KEYS & set(result)
    _require(not reserved, "UNKNOWN_KEY", f"receipt payload sets reserved fields {sorted(reserved)!r}")
    legacy = _LEGACY_RECEIPT_KEYS & set(result)
    _require(not legacy, "UNKNOWN_KEY", f"receipt payload uses removed fields {sorted(legacy)!r}")
    _json_bytes(result, "receipt payload")
    return result


def _validate_receipt_shape(record: Any, registration: Mapping[str, Any]) -> dict[str, Any]:
    result = _validate_object_contract(record, registration["field_contract"], "receipt")
    _require(not (_LEGACY_RECEIPT_KEYS & set(result)), "UNKNOWN_KEY", "receipt uses removed generic receipt fields")
    _require(result.get("schema") == registration["schema"], "SCHEMA_LITERAL_MISMATCH", "receipt schema does not match the registry")
    return result


def _receipt_self_hash(record: Mapping[str, Any], registration: Mapping[str, Any]) -> str:
    return _object_self_hash(record, registration)


def receipt_self_hash(
    receipt: Mapping[str, Any],
    *,
    schema_registry: Mapping[str, Any] | None = None,
) -> str:
    """Return the registered self hash for a fully shaped indexed receipt."""

    record = _object(receipt, "receipt")
    schema = _identifier(record.get("schema"), "receipt schema")
    registration = _registration(schema, schema_registry)
    _validate_receipt_shape(record, registration)
    return _receipt_self_hash(record, registration)


def build_receipt(
    schema: str,
    payload: Mapping[str, Any] | None = None,
    *,
    contract_root: Any | None = None,
    contract_root_sha256: str | None = None,
    profile: Any = None,
    profile_sha256: str | None = None,
    semantic_subhashes: Any = None,
    schema_registry: Mapping[str, Any] | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Build one root/profile-bound receipt from a registered exact payload."""

    registration = _registration(schema, schema_registry)
    root_id, profile_id, parent_values = _resolved_context(
        contract_root=contract_root,
        contract_root_sha256=contract_root_sha256,
        profile=profile,
        profile_sha256=profile_sha256,
        semantic_subhashes=semantic_subhashes,
    )
    record: dict[str, Any] = {
        "schema": registration["schema"],
        "receipt_id": "0" * 64,
        "contract_root_sha256": root_id,
        "profile_sha256": profile_id,
        "consumed_semantic_subhashes": _parent_records(registration["semantic_parent_names"], parent_values),
        **_payload(payload, fields),
        "self_sha256": "0" * 64,
    }
    _validate_receipt_shape(record, registration)
    _validate_receipt_envelope(
        record,
        registration,
        expected_root=root_id,
        expected_profile=profile_id,
        parent_values=parent_values,
    )
    _require(len(_json_bytes(record, "receipt")) <= registration["max_encoded_bytes"], "BYTE_LIMIT_EXCEEDED", "receipt exceeds registered byte limit")
    record["receipt_id"] = _receipt_id(record, registration["schema"])
    record["self_sha256"] = _receipt_self_hash(record, registration)
    _validate_receipt_shape(record, registration)
    _validate_receipt_envelope(
        record,
        registration,
        expected_root=root_id,
        expected_profile=profile_id,
        parent_values=parent_values,
    )
    _require(_receipt_id(record, registration["schema"]) == record["receipt_id"], "RECEIPT_ID_MISMATCH", "built receipt_id does not match")
    _require(_receipt_self_hash(record, registration) == record["self_sha256"], "SELF_HASH_MISMATCH", "built receipt self hash does not match")
    return record


def validate_receipt(
    receipt: Mapping[str, Any] | bytes | str,
    *,
    contract_root: Any | None = None,
    contract_root_sha256: str | None = None,
    profile: Any = None,
    profile_sha256: str | None = None,
    semantic_subhashes: Any = None,
    schema_registry: Mapping[str, Any] | None = None,
    expected_schema: str | None = None,
) -> dict[str, Any]:
    """Validate a canonical, root/profile-resolved indexed receipt."""

    if isinstance(receipt, (bytes, str)):
        raw = _source_bytes(receipt, "receipt")
        decoded = _json_loads(raw, "receipt")
        _require(_json_bytes(decoded, "receipt") == raw, "NONCANONICAL_ENCODING", "receipt bytes are not canonical")
        record = _object(decoded, "receipt")
    else:
        record = _object(receipt, "receipt")
    schema = _identifier(record.get("schema"), "receipt schema")
    if expected_schema is not None:
        _require(schema == expected_schema, "SCHEMA_LITERAL_MISMATCH", f"receipt schema is {schema}, not {expected_schema}")
    registration = _registration(schema, schema_registry)
    record = _validate_receipt_shape(record, registration)
    root_id, profile_id, parent_values = _resolved_context(
        contract_root=contract_root,
        contract_root_sha256=contract_root_sha256,
        profile=profile,
        profile_sha256=profile_sha256,
        semantic_subhashes=semantic_subhashes,
    )
    _validate_receipt_envelope(
        record,
        registration,
        expected_root=root_id,
        expected_profile=profile_id,
        parent_values=parent_values,
    )
    declared_receipt_id = _digest(record.get("receipt_id"), "receipt receipt_id")
    _require(_receipt_id(record, schema) == declared_receipt_id, "RECEIPT_ID_MISMATCH", "receipt_id does not match")
    declared_self = _digest(record.get("self_sha256"), "receipt self_sha256")
    _require(_receipt_self_hash(record, registration) == declared_self, "SELF_HASH_MISMATCH", "receipt self hash does not match")
    _require(len(_json_bytes(record, "receipt")) <= registration["max_encoded_bytes"], "BYTE_LIMIT_EXCEEDED", "receipt exceeds registered byte limit")
    return dict(record)


def receipt_bytes(receipt: Mapping[str, Any], **kwargs: Any) -> bytes:
    """Return canonical receipt bytes only after full root/profile validation."""

    validated = validate_receipt(receipt, **kwargs)
    return _json_bytes(validated, "receipt")


def _receipt_schema_map(registry: Mapping[str, Any]) -> dict[str, str]:
    """Derive public builder names without trusting malformed entries at import."""

    try:
        entries = registry.get("entries")
    except AttributeError:
        return {}
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes, bytearray, memoryview)):
        return {}
    result: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, Mapping) or entry.get("object_class") != "indexed-receipt":
            continue
        document = entry.get("schema_document")
        required = document.get("required_keys") if isinstance(document, Mapping) else None
        if not isinstance(required, list) or not _RECEIPT_ENVELOPE_KEYS <= set(required):
            continue
        schema = entry.get("schema")
        if not isinstance(schema, str):
            continue
        stem = _SCHEMA_VERSION.sub("", schema.removeprefix("cassi.qi-flow-"))
        if stem.endswith("-receipt"):
            stem = stem[: -len("-receipt")]
        kind = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
        if not kind or kind in result:
            return {}
        result[kind] = schema
    return result


RECEIPT_SCHEMAS = _receipt_schema_map(SCHEMA_REGISTRY)


def receipt_fixture_payload(
    schema: str,
    *,
    schema_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the canonical minimal payload for one standard receipt envelope."""

    registration = _registration(schema, schema_registry)
    fixture_set = _object(
        registration["canonical_fixture_set"],
        "registered canonical fixture set",
    )
    fixture = _object(fixture_set["minimal_valid"], "minimal receipt fixture")
    payload = {
        name: value
        for name, value in fixture.items()
        if name not in _RECEIPT_ENVELOPE_KEYS
    }
    return _object(
        canonical_json_loads(canonical_json_bytes(payload)),
        "minimal receipt payload",
    )


def _builder(kind: str):
    def build(payload: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        return build_receipt(RECEIPT_SCHEMAS[kind], payload, **kwargs)

    build.__name__ = f"build_{kind}_receipt"
    build.__qualname__ = build.__name__
    return build


def _validator(kind: str):
    def validate(receipt: Mapping[str, Any] | bytes | str, **kwargs: Any) -> dict[str, Any]:
        return validate_receipt(receipt, expected_schema=RECEIPT_SCHEMAS[kind], **kwargs)

    validate.__name__ = f"validate_{kind}_receipt"
    validate.__qualname__ = validate.__name__
    return validate


for _kind in RECEIPT_SCHEMAS:
    _build_name = f"build_{_kind}_receipt"
    _validate_name = f"validate_{_kind}_receipt"
    globals()[_build_name] = _builder(_kind)
    globals()[_validate_name] = _validator(_kind)
    __all__.extend((_build_name, _validate_name))
