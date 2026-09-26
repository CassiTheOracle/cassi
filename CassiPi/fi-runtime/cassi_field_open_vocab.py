"""Bounded, deterministic open-vocabulary relational semantic kernel."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence
OPEN_VOCAB_CODEC_SCHEMA = "cassifi.open-vocab-byte-symbol.v1"
OPEN_VOCAB_LAYOUT_SCHEMA = "cassifi.open-vocab-term-layout.v1"


class OpenVocabError(ValueError):
    """Typed refusal from the fixed representation or bounded semantic kernel."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


def _json(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise OpenVocabError("representation-insufficient", "canonical JSON rejects unsupported or nonfinite values") from exc
def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _fail(code: str, message: str, **details: Any) -> None:
    raise OpenVocabError(code, message, details=details)


def encode_lexeme(value: str | bytes | bytearray | Mapping[str, Any]) -> dict[str, Any]:
    """Encode an opaque lexical atom using the exact 0..255 byte alphabet."""
    if isinstance(value, Mapping):
        if set(value) != {"bytes", "length", "schema"}:
            _fail("representation-insufficient", "lexeme object has the wrong closed shape")
        raw = value.get("bytes")
        if value.get("schema") != OPEN_VOCAB_CODEC_SCHEMA or not isinstance(raw, list):
            _fail("representation-insufficient", "lexeme codec schema is unsupported")
        if any(isinstance(item, bool) or not isinstance(item, int) or not 0 <= item <= 255 for item in raw):
            _fail("representation-insufficient", "lexeme bytes must be integers in 0..255")
        if value.get("length") != len(raw):
            _fail("representation-insufficient", "lexeme length does not match bytes")
        value = bytes(raw)
    elif isinstance(value, str):
        value = value.encode("utf-8")
    elif isinstance(value, (bytes, bytearray)):
        value = bytes(value)
    else:
        _fail("representation-insufficient", "lexeme must be UTF-8 text or raw bytes")
    if not value:
        _fail("representation-insufficient", "lexeme cannot be empty")
    if len(value) > 4096:
        _fail("resource-exhausted", "lexeme exceeds fixed byte bound", limit=4096)
    return {"bytes": list(value), "length": len(value), "schema": OPEN_VOCAB_CODEC_SCHEMA}


def decode_lexeme(value: Mapping[str, Any] | str | bytes) -> bytes:
    encoded = encode_lexeme(value)
    return bytes(encoded["bytes"])


def canonical_symbols(value: Any) -> dict[str, Any]:
    return encode_lexeme(value)


def codec_descriptor() -> dict[str, Any]:
    return {"alphabet": {"min": 0, "max": 255}, "encoding": "utf-8", "schema": OPEN_VOCAB_CODEC_SCHEMA}


def canonical_type(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        if value in {"lexeme", "bytes", "boolean", "integer", "number"}:
            return {"kind": "atom", "name": value}
        if not value or len(value) > 128:
            _fail("representation-insufficient", "type atom name is invalid")
        return {"kind": "named", "name": value}
    if not isinstance(value, Mapping):
        _fail("representation-insufficient", "type must be a string or typed object")
    kind = value.get("kind")
    allowed = {"kind", "name", "scope", "item", "items", "fields"}
    if kind not in {"atom", "named", "variable", "list", "option", "tuple", "record"} or set(value) - allowed:
        _fail("representation-insufficient", "type contains unknown keys")
    if kind in {"atom", "named"}:
        name = value.get("name")
        if not isinstance(name, str) or not name:
            _fail("representation-insufficient", "type name is invalid")
        return {"kind": kind, "name": name}
    if kind == "variable":
        scope = value.get("scope", "schema")
        name = value.get("name")
        if not isinstance(scope, str) or not scope or not isinstance(name, str) or not name:
            _fail("representation-insufficient", "type variable is invalid")
        return {"kind": "variable", "name": name, "scope": scope}
    if kind in {"list", "option"}:
        return {"kind": kind, "item": canonical_type(value.get("item"))}
    if kind == "tuple":
        items = value.get("items")
        if not isinstance(items, list) or len(items) > 64:
            _fail("representation-insufficient", "tuple type is invalid")
        return {"kind": "tuple", "items": [canonical_type(item) for item in items]}
    if kind == "record":
        fields = value.get("fields")
        if not isinstance(fields, Mapping) or len(set(fields)) != len(fields):
            _fail("representation-insufficient", "record type fields are invalid")
        return {"kind": "record", "fields": {str(k): canonical_type(fields[k]) for k in sorted(fields)}}
    _fail("representation-insufficient", "unknown type constructor")


def _canonical_value(typ: Mapping[str, Any], value: Any) -> Any:
    name = typ.get("name")
    if typ["kind"] == "atom":
        if name == "lexeme":
            return encode_lexeme(value)
        if name == "bytes":
            return encode_lexeme(value)
        if name == "boolean":
            if not isinstance(value, bool):
                _fail("representation-insufficient", "boolean atom has wrong value")
            return value
        if name == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                _fail("representation-insufficient", "integer atom has wrong value")
            return value
        if name == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                _fail("representation-insufficient", "number atom has wrong value")
            numeric = float(value)
            if not math.isfinite(numeric):
                _fail("representation-insufficient", "number atom must be finite")
            return numeric
    if typ["kind"] == "list":
        if not isinstance(value, list) or len(value) > 256:
            _fail("representation-insufficient", "list value is invalid")
        return [_canonical_value(typ["item"], item) for item in value]
    if typ["kind"] == "tuple":
        if not isinstance(value, list) or len(value) != len(typ["items"]):
            _fail("representation-insufficient", "tuple value is invalid")
        return [_canonical_value(item_type, item) for item_type, item in zip(typ["items"], value)]
    if typ["kind"] == "record":
        if not isinstance(value, Mapping) or set(value) != set(typ["fields"]):
            _fail("representation-insufficient", "record value has wrong field coverage")
        return {k: _canonical_value(typ["fields"][k], value[k]) for k in sorted(typ["fields"])}
    return value


def canonical_term(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("representation-insufficient", "term must be a closed tagged object")
    kind = value.get("kind")
    allowed_by_kind = {
        "variable": {"kind", "name", "scope", "type"},
        "var": {"kind", "name", "scope", "type"},
        "atom": {"kind", "type", "value"},
        "literal": {"kind", "type", "value"},
        "value": {"kind", "type", "value"},
        "constructor": {"kind", "name", "args", "type", "unit", "frame"},
        "application": {"kind", "head", "arguments", "type", "unit", "frame"},
        "relation": {"kind", "name", "args", "type", "unit", "frame"},
        "sequence": {"kind", "items", "type"},
        "record": {"kind", "fields", "type"},
    }
    if kind not in allowed_by_kind or set(value) - allowed_by_kind[kind]:
        _fail("representation-insufficient", "term contains unknown keys")
    if kind in {"variable", "var"}:
        name, scope = value.get("name"), value.get("scope", "free")
        typ = canonical_type(value.get("type", "named:unknown")) if value.get("type") != "named:unknown" else {"kind": "named", "name": "unknown"}
        if not isinstance(name, str) or not name or not isinstance(scope, str) or not scope:
            _fail("representation-insufficient", "term variable is invalid")
        return {"kind": "variable", "name": name, "scope": scope, "type": typ}
    if kind in {"atom", "literal", "value"}:
        typ = canonical_type(value.get("type", "named:unknown"))
        return {"kind": "atom", "type": typ, "value": _canonical_value(typ, value.get("value"))}
    if kind in {"constructor", "application", "relation"}:
        name = value.get("name") or value.get("head")
        args = value.get("args", value.get("arguments", []))
        if not isinstance(name, str) or not name or not isinstance(args, list) or len(args) > 64:
            _fail("representation-insufficient", "constructor term is invalid")
        result = {"kind": "constructor", "name": name, "args": [canonical_term(arg) for arg in args]}
        if value.get("type") is not None:
            result["type"] = canonical_type(value["type"])
        if value.get("unit") is not None:
            result["unit"] = str(value["unit"])
        if value.get("frame") is not None:
            result["frame"] = str(value["frame"])
        return result
    if kind == "sequence":
        items = value.get("items")
        if not isinstance(items, list) or len(items) > 256:
            _fail("representation-insufficient", "sequence term is invalid")
        result = {"kind": "sequence", "items": [canonical_term(item) for item in items]}
        if value.get("type") is not None:
            result["type"] = canonical_type(value["type"])
        return result
    if kind == "record":
        fields = value.get("fields")
        if not isinstance(fields, Mapping) or len(fields) > 128:
            _fail("representation-insufficient", "record term is invalid")
        result = {"kind": "record", "fields": {str(k): canonical_term(fields[k]) for k in sorted(fields)}}
        if value.get("type") is not None:
            result["type"] = canonical_type(value["type"])
        return result
    _fail("representation-insufficient", "unknown term constructor")
def instantiate_template(
    template: Mapping[str, Any],
    bindings: Mapping[str, Any],
    *,
    constructors: Sequence[str] = (),
) -> dict[str, Any]:
    """Instantiate one closed relational term template without learned state.

    A template is either a canonical term or the explicit envelope
    ``{"schema": "cassifi.open-vocab-template.v1", "term": ...,
    "constructors": [...]}``. Role variables use ``scope == "role"``.
    """
    if not isinstance(template, Mapping) or not isinstance(bindings, Mapping):
        _fail("representation-insufficient", "template and role bindings must be objects")
    if "term" in template or "constructors" in template or template.get("schema"):
        if (
            set(template) != {"schema", "term", "constructors"}
            or template.get("schema") != "cassifi.open-vocab-template.v1"
        ):
            _fail("representation-insufficient", "template envelope is not closed")
        raw_term = template["term"]
        declared = template["constructors"]
        if (
            not isinstance(declared, list)
            or not declared
            or any(not isinstance(name, str) or not name for name in declared)
            or len(set(declared)) != len(declared)
        ):
            _fail("representation-insufficient", "template constructor vocabulary is invalid")
        allowed_constructors = frozenset(declared)
    else:
        raw_term = template
        allowed_constructors = frozenset(constructors)
    term = canonical_term(raw_term)
    supplied = {str(name): value for name, value in bindings.items()}
    role_names: set[str] = set()
    constructor_names: set[str] = set()

    def collect(node: Mapping[str, Any]) -> None:
        kind = node["kind"]
        if kind == "variable":
            if node["scope"] != "role":
                _fail("representation-insufficient", "template contains an unbound variable")
            role_names.add(node["name"])
        elif kind == "constructor":
            constructor_names.add(node["name"])
            for child in node["args"]:
                collect(child)
        elif kind == "sequence":
            for child in node["items"]:
                collect(child)
        elif kind == "record":
            for child in node["fields"].values():
                collect(child)

    collect(term)
    if set(supplied) != role_names:
        _fail(
            "representation-insufficient",
            "template role bindings do not exactly match its roles",
            missing=sorted(role_names - set(supplied)),
            extra=sorted(set(supplied) - role_names),
        )
    if not allowed_constructors or not constructor_names.issubset(allowed_constructors):
        _fail("representation-insufficient", "template contains an unknown constructor")

    def binding_term(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return canonical_term(value)
        if isinstance(value, bool):
            return {"kind": "atom", "type": "boolean", "value": value}
        if isinstance(value, int) and not isinstance(value, bool):
            return {"kind": "atom", "type": "integer", "value": value}
        if isinstance(value, float):
            if not math.isfinite(value):
                _fail("representation-insufficient", "role binding number must be finite")
            return {"kind": "atom", "type": "number", "value": value}
        if isinstance(value, str):
            return {"kind": "atom", "type": "lexeme", "value": value}
        _fail("representation-insufficient", "role binding is not a typed value")

    normalized_bindings = {name: binding_term(value) for name, value in supplied.items()}

    def substitute(node: Mapping[str, Any]) -> dict[str, Any]:
        if node["kind"] == "variable":
            return normalized_bindings[node["name"]]
        if node["kind"] == "constructor":
            return {**node, "args": [substitute(child) for child in node["args"]]}
        if node["kind"] == "sequence":
            return {**node, "items": [substitute(child) for child in node["items"]]}
        if node["kind"] == "record":
            return {
                **node,
                "fields": {
                    key: substitute(child) for key, child in node["fields"].items()
                },
            }
        return dict(node)

    result = canonical_term(substitute(term))
    if _term_variables(result):
        _fail("representation-insufficient", "template instantiation left unbound variables")
    return result



def term_digest(term: Mapping[str, Any]) -> str:
    return _digest(canonical_term(term))


def _alpha(term: Mapping[str, Any], bound: dict[tuple[str, str], int], counter: list[int]) -> dict[str, Any]:
    term = canonical_term(term)
    if term["kind"] == "variable":
        key = (term["scope"], term["name"])
        if term["scope"] in {"schema", "bound", "local"}:
            if key not in bound:
                bound[key] = counter[0]
                counter[0] += 1
            return {**term, "name": f"v{bound[key]}", "scope": "bound"}
        return term
    if term["kind"] == "constructor":
        return {**term, "args": [_alpha(arg, bound, counter) for arg in term["args"]]}
    if term["kind"] in {"sequence"}:
        return {**term, "items": [_alpha(arg, bound, counter) for arg in term["items"]]}
    if term["kind"] == "record":
        return {**term, "fields": {k: _alpha(v, bound, counter) for k, v in term["fields"].items()}}
    return term


def alpha_normalize(term: Mapping[str, Any]) -> dict[str, Any]:
    return _alpha(term, {}, [0])


def alpha_equivalent(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return alpha_normalize(left) == alpha_normalize(right)


def _type_of(term: Mapping[str, Any]) -> Mapping[str, Any] | None:
    if term.get("kind") in {"atom", "variable"}:
        return term.get("type")
    return term.get("type")


def _occurs(var: tuple[str, str], term: Mapping[str, Any], substitution: Mapping[tuple[str, str], Mapping[str, Any]]) -> bool:
    term = substitution.get((term.get("scope"), term.get("name")), term)
    if term.get("kind") == "variable":
        return (term.get("scope"), term.get("name")) == var
    return any(_occurs(var, child, substitution) for child in _children(term))


def _children(term: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    if term.get("kind") == "constructor":
        yield from term["args"]
    elif term.get("kind") == "sequence":
        yield from term["items"]
    elif term.get("kind") == "record":
        yield from term["fields"].values()


def apply_substitution(term: Mapping[str, Any], substitution: Mapping[str, Any] | "Substitution") -> dict[str, Any]:
    mapping = substitution.mapping if isinstance(substitution, Substitution) else substitution
    if isinstance(mapping, Mapping) and mapping.get("schema") == "cassifi.open-vocab-substitution.v1":
        bindings = mapping.get("bindings")
        if not isinstance(bindings, list):
            _fail("representation-insufficient", "substitution envelope bindings are invalid")
        normalized_mapping = {}
        for binding in bindings:
            if not isinstance(binding, Mapping) or not isinstance(binding.get("variable"), str) or not isinstance(binding.get("term"), Mapping):
                _fail("representation-insufficient", "substitution envelope binding is invalid")
            normalized_mapping[binding["variable"]] = canonical_term(binding["term"])
        mapping = normalized_mapping
    def visit(value: Mapping[str, Any], active: frozenset[str]) -> dict[str, Any]:
        value = canonical_term(value)
        if value["kind"] == "variable":
            key = f"{value['scope']}:{value['name']}"
            candidate = mapping.get((value["scope"], value["name"])) or mapping.get(key)
            if candidate is not None:
                if key in active:
                    _fail("representation-insufficient", "substitution contains a cycle")
                return visit(candidate, active | {key})
            return value
        if value["kind"] == "constructor":
            return {**value, "args": [visit(arg, active) for arg in value["args"]]}
        if value["kind"] == "sequence":
            return {**value, "items": [visit(arg, active) for arg in value["items"]]}
        if value["kind"] == "record":
            return {**value, "fields": {k: visit(v, active) for k, v in value["fields"].items()}}
        return value

    return visit(term, frozenset())


@dataclass(frozen=True)
class Substitution:
    mapping: Mapping[Any, Mapping[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        rows = []
        for key, value in self.mapping.items():
            k = key if isinstance(key, str) else f"{key[0]}:{key[1]}"
            rows.append({"variable": k, "term": canonical_term(value)})
        return {"schema": "cassifi.open-vocab-substitution.v1", "bindings": sorted(rows, key=lambda x: x["variable"])}
@dataclass(frozen=True)
class UnificationAlternative:
    substitution: Substitution
    digest: str

def check_guards(guards: Sequence[Mapping[str, Any]], substitution: Mapping[Any, Mapping[str, Any]] | Substitution = ()) -> tuple[bool, str | None]:
    mapping = substitution.mapping if isinstance(substitution, Substitution) else dict(substitution)
    for guard in guards:
        if not isinstance(guard, Mapping):
            return False, "invalid-guard"
        kind = guard.get("kind")
        if kind not in {"eq", "neq", "membership", "sort", "unit", "frame", "applicable"}:
            return False, "invalid-guard"
        if kind in {"eq", "neq"}:
            left, right = guard.get("left"), guard.get("right")
            if not isinstance(left, Mapping) or not isinstance(right, Mapping):
                return False, "invalid-guard"
            equal = alpha_equivalent(apply_substitution(left, mapping), apply_substitution(right, mapping))
            if (kind == "eq" and not equal) or (kind == "neq" and equal):
                return False, "guard-contradiction"
        elif kind == "membership":
            item = guard.get("item", guard.get("left"))
            members = guard.get("members", guard.get("right"))
            if not isinstance(item, Mapping) or not isinstance(members, list):
                return False, "invalid-guard"
            item = apply_substitution(item, mapping)
            if not any(alpha_equivalent(item, apply_substitution(member, mapping)) for member in members if isinstance(member, Mapping)):
                return False, "guard-contradiction"
        elif kind == "sort":
            term = guard.get("term", guard.get("left"))
            expected = guard.get("type", guard.get("right"))
            if not isinstance(term, Mapping) or expected is None:
                return False, "invalid-guard"
            if canonical_term(apply_substitution(term, mapping)).get("type") != canonical_type(expected):
                return False, "guard-contradiction"
        elif kind in {"unit", "frame"}:
            left, right = guard.get("left"), guard.get("right")
            if not isinstance(left, Mapping) or not isinstance(right, Mapping):
                return False, "invalid-guard"
            left_term, right_term = apply_substitution(left, mapping), apply_substitution(right, mapping)
            key = "unit" if kind == "unit" else "frame"
            if left_term.get(key) != right_term.get(key):
                return False, "guard-contradiction"
        elif kind == "applicable":
            value = guard.get("value", guard.get("allowed"))
            if not isinstance(value, bool):
                return False, "invalid-guard"
            if not value:
                return False, "guard-contradiction"
    return True, None


def unify_terms(left: Mapping[str, Any], right: Mapping[str, Any], *, guards: Sequence[Mapping[str, Any]] = (), max_alternatives: int = 8, max_work: int = 4096, max_depth: int = 64) -> dict[str, Any]:
    if max_alternatives < 1 or max_work < 1 or max_depth < 1:
        _fail("resource-exhausted", "unification bounds must be positive")
    a, b = canonical_term(left), canonical_term(right)
    work: list[tuple[dict[str, Any], dict[str, Any], int]] = [(a, b, 0)]
    subst: dict[tuple[str, str], dict[str, Any]] = {}
    steps = 0
    while work:
        if len(work) + steps > max_work:
            return {"status": "resource-exhausted", "reason": "unification-work-bound", "alternatives": [], "work": steps}
        x, y, depth = work.pop(0)
        if depth > max_depth:
            return {"status": "resource-exhausted", "reason": "unification-depth-bound", "alternatives": [], "work": steps}
        x, y = apply_substitution(x, subst), apply_substitution(y, subst)
        steps += 1
        if x == y:
            continue
        if x.get("kind") == "variable":
            if y.get("kind") == "variable" and x.get("scope") != y.get("scope") and "schema" not in {x.get("scope"), y.get("scope")}:
                return {"status": "unresolved", "reason": "scope-mismatch", "alternatives": [], "work": steps}
            key = (x["scope"], x["name"])
            if _occurs(key, y, subst):
                return {"status": "unresolved", "reason": "occurs-check", "alternatives": [], "work": steps}
            if x.get("type") and _type_of(y) and x["type"] != _type_of(y):
                return {"status": "unresolved", "reason": "type-mismatch", "alternatives": [], "work": steps}
            subst[key] = y
            continue
        if y.get("kind") == "variable":
            if x.get("scope") != y.get("scope") and "schema" not in {x.get("scope"), y.get("scope")}:
                return {"status": "unresolved", "reason": "scope-mismatch", "alternatives": [], "work": steps}
            work.insert(0, (y, x, depth))
            continue
        if x.get("kind") != y.get("kind"):
            return {"status": "unresolved", "reason": "constructor-mismatch", "alternatives": [], "work": steps}
        if x.get("kind") == "atom":
            if x.get("type") != y.get("type") or x.get("value") != y.get("value"):
                return {"status": "unresolved", "reason": "atom-mismatch", "alternatives": [], "work": steps}
        elif x.get("kind") == "constructor":
            if x.get("name") != y.get("name") or len(x["args"]) != len(y["args"]):
                return {"status": "unresolved", "reason": "constructor-mismatch", "alternatives": [], "work": steps}
            if x.get("unit") != y.get("unit") or x.get("frame") != y.get("frame"):
                return {"status": "unresolved", "reason": "unit-frame-mismatch", "alternatives": [], "work": steps}
            work[0:0] = [(u, v, depth + 1) for u, v in zip(x["args"], y["args"])]
        elif x.get("kind") == "sequence":
            if len(x["items"]) != len(y["items"]):
                return {"status": "unresolved", "reason": "sequence-length-mismatch", "alternatives": [], "work": steps}
            work[0:0] = [(u, v, depth + 1) for u, v in zip(x["items"], y["items"])]
        elif x.get("kind") == "record":
            if list(x["fields"]) != list(y["fields"]):
                return {"status": "unresolved", "reason": "record-field-mismatch", "alternatives": [], "work": steps}
            work[0:0] = [(x["fields"][k], y["fields"][k], depth + 1) for k in x["fields"]]
    ok, reason = check_guards(guards, subst)
    if not ok:
        return {"status": "unresolved", "reason": reason or "guard-contradiction", "alternatives": [], "work": steps}
    normalized = {f"{scope}:{name}": apply_substitution(value, subst) for (scope, name), value in sorted(subst.items())}
    alternative = {"substitution": {"schema": "cassifi.open-vocab-substitution.v1", "bindings": [{"variable": key, "term": value} for key, value in normalized.items()]}, "digest": _digest(normalized)}
    return {"status": "supported", "alternatives": [alternative][:max_alternatives], "substitution": alternative["substitution"], "work": steps}


def _episode_id(value: Mapping[str, Any]) -> str:
    for key in ("event_id", "episode_id", "id"):
        if isinstance(value.get(key), str) and value[key]:
            return value[key]
    _fail("representation-insufficient", "grounded episode lacks identity")


def canonical_grounded_episode(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("representation-insufficient", "grounded episode must be an object")
    source_ids = value.get("source_revision_ids", [value.get("source_revision_id")])
    if not isinstance(source_ids, list) or not source_ids or any(not isinstance(x, str) or not x for x in source_ids):
        _fail("support-gap", "grounded episode lacks active source revision")
    trajectory_id = value.get("trajectory_id")
    trajectory_index = value.get("trajectory_index")
    if (trajectory_id is None) != (trajectory_index is None):
        _fail(
            "representation-insufficient",
            "trajectory identity and index must be supplied together",
        )
    if trajectory_id is not None and (
        not isinstance(trajectory_id, str) or not trajectory_id
    ):
        _fail("representation-insufficient", "trajectory identity is invalid")
    if trajectory_index is not None and (
        isinstance(trajectory_index, bool)
        or not isinstance(trajectory_index, int)
        or trajectory_index < 0
    ):
        _fail("representation-insufficient", "trajectory index is invalid")
    required = {
        "event_id": _episode_id(value),
        "source_revision_ids": sorted(set(source_ids)),
        "pre_state": canonical_term(value.get("pre_state", value.get("state", {"kind": "record", "fields": {}}))),
        "action": canonical_term(value.get("action")),
        "post_state": canonical_term(value.get("post_state", value.get("outcome", {"kind": "record", "fields": {}}))),
        "bindings": value.get("bindings", {}),
        "observation": value.get("observation", {"success": True}),
    }
    if trajectory_id is not None:
        required["trajectory_id"] = trajectory_id
        required["trajectory_index"] = trajectory_index
    if not isinstance(required["bindings"], Mapping) or not isinstance(required["observation"], Mapping):
        _fail("representation-insufficient", "episode binding or observation is invalid")
    normalized_bindings: dict[str, dict[str, Any]] = {}
    for role, term in required["bindings"].items():
        if not isinstance(role, str) or not role or not isinstance(term, Mapping):
            _fail("representation-insufficient", "episode bindings must be role-to-term")
        normalized_bindings[role] = canonical_term(term)
    required["bindings"] = normalized_bindings
    observation = dict(required["observation"])
    if "success" not in observation or not isinstance(observation["success"], bool):
        _fail("representation-insufficient", "episode observation must close success/failure")
    required["observation"] = json.loads(_json(observation))
    required["codec"] = codec_descriptor()
    required["layout_schema"] = OPEN_VOCAB_LAYOUT_SCHEMA
    required["episode_digest"] = _digest({k: required[k] for k in sorted(required)})
    return required

def episode_source_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    """Canonical bytes archived as the exact external source for one episode."""
    episode = canonical_grounded_episode(value)
    payload = {
        "event_id": episode["event_id"],
        "pre_state": episode["pre_state"],
        "action": episode["action"],
        "post_state": episode["post_state"],
        "observation": episode["observation"],
        "bindings": episode["bindings"],
    }
    for key in ("trajectory_id", "trajectory_index"):
        if key in episode:
            payload[key] = episode[key]
    return payload


def _anti_unify(a: Any, b: Any, params: list[dict[str, Any]], path: str = "") -> Any:
    if a == b:
        return a
    if isinstance(a, Mapping) and isinstance(b, Mapping) and a.get("kind") == b.get("kind"):
        if a.get("kind") == "constructor" and a.get("name") == b.get("name") and len(a.get("args", [])) == len(b.get("args", [])):
            out = dict(a)
            out["args"] = [_anti_unify(x, y, params, f"{path}/{i}") for i, (x, y) in enumerate(zip(a["args"], b["args"]))]
            return out
        if a.get("kind") == "record" and list(a.get("fields", {})) == list(b.get("fields", {})):
            return {**a, "fields": {k: _anti_unify(a["fields"][k], b["fields"][k], params, f"{path}/{k}") for k in a["fields"]}}
    typ = a.get("type", b.get("type", {"kind": "named", "name": "unknown"})) if isinstance(a, Mapping) and isinstance(b, Mapping) else {"kind": "named", "name": "unknown"}
    index = len(params)
    params.append({"name": f"p{index}", "type": canonical_type(typ), "path": path})
    return {"kind": "variable", "name": f"p{index}", "scope": "schema", "type": canonical_type(typ)}
def _anti_unify_shared(values: Sequence[Any], params: list[dict[str, Any]], shared: dict[str, dict[str, Any]], path: str = "") -> Any:
    if not values:
        _fail("representation-insufficient", "anti-unification received no values")
    if all(value == values[0] for value in values[1:]):
        return values[0]
    if all(isinstance(value, Mapping) for value in values):
        kinds = {value.get("kind") for value in values}
        if len(kinds) == 1 and next(iter(kinds)) == "constructor":
            names = {value.get("name") for value in values}
            arities = {len(value.get("args", [])) for value in values}
            if len(names) == 1 and len(arities) == 1:
                base = dict(values[0])
                base["args"] = [_anti_unify_shared([value["args"][index] for value in values], params, shared, f"{path}/{index}") for index in range(len(base["args"]))]
                return base
        if len(kinds) == 1 and next(iter(kinds)) == "record":
            fields = list(values[0].get("fields", {}))
            if all(list(value.get("fields", {})) == fields for value in values):
                base = dict(values[0])
                base["fields"] = {key: _anti_unify_shared([value["fields"][key] for value in values], params, shared, f"{path}/{key}") for key in fields}
                return base
    typed = [value.get("type") for value in values if isinstance(value, Mapping) and value.get("type") is not None]
    if typed and len({_json(canonical_type(item)) for item in typed}) != 1:
        _fail("representation-insufficient", "anti-unification encountered incompatible types")
    key = _digest(values)
    if key in shared:
        return shared[key]["term"]
    first = values[0]
    typ = first.get("type", {"kind": "named", "name": "unknown"}) if isinstance(first, Mapping) else {"kind": "named", "name": "unknown"}
    parameter = {"name": f"p{len(params)}", "type": canonical_type(typ), "path": path}
    term = {"kind": "variable", "name": parameter["name"], "scope": "schema", "type": parameter["type"]}
    parameter["term"] = term
    params.append(parameter)
    shared[key] = parameter
    return term


def canonical_action_schema(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("representation-insufficient", "action schema must be an object")
    action = canonical_term(value.get("action", value.get("action_pattern")))
    pre = value.get("preconditions", [])
    effects = value.get("effects", value.get("postconditions", []))
    guards = value.get("guards", [])
    params = value.get("parameters", value.get("parameter_roles", []))
    if not isinstance(pre, list) or not isinstance(effects, list) or not isinstance(guards, list) or not isinstance(params, list):
        _fail("representation-insufficient", "schema rows must be lists")
    pre = [canonical_term(x) for x in pre]
    effects = [canonical_term(x) for x in effects]
    normalized_params = []
    names = set()
    for row in params:
        if not isinstance(row, Mapping) or not isinstance(row.get("name"), str) or not row["name"] or row["name"] in names:
            _fail("representation-insufficient", "schema parameter row is invalid")
        if "type" not in row:
            _fail("representation-insufficient", "schema parameter type is missing")
        normalized = {"name": row["name"], "type": canonical_type(row["type"]), "path": row.get("path", "")}
        if not isinstance(normalized["path"], str):
            _fail("representation-insufficient", "schema parameter path is invalid")
        if "term" in row:
            normalized["term"] = canonical_term(row["term"])
        normalized_params.append(normalized)
        names.add(row["name"])
    normalized_guards = []
    for guard in guards:
        if not isinstance(guard, Mapping) or guard.get("kind") not in {"eq", "neq", "membership", "sort", "unit", "frame", "applicable"}:
            _fail("representation-insufficient", "schema guard row is invalid")
        normalized_guards.append(json.loads(_json(dict(guard))))
    used_variables = set().union(*(_term_variables(term) for term in [action, *pre, *effects])) if (pre or effects) else _term_variables(action)
    for guard in normalized_guards:
        for key in ("left", "right", "item", "term"):
            if isinstance(guard.get(key), Mapping):
                used_variables |= _term_variables(canonical_term(guard[key]))
    if {name for scope, name in used_variables if scope == "schema"} != names:
        _fail("representation-insufficient", "schema parameters do not match used variables")
    bounds = value.get("bounds", {})
    if not isinstance(bounds, Mapping):
        _fail("representation-insufficient", "schema bounds are invalid")
    max_horizon, max_work = bounds.get("max_horizon", 4), bounds.get("max_work", 4096)
    if any(isinstance(x, bool) or not isinstance(x, int) or x < 1 for x in (max_horizon, max_work)):
        _fail("representation-insufficient", "schema bounds must be positive integers")
    event_refs = value.get("support_event_refs", value.get("support_events", []))
    binding_refs = value.get("support_binding_refs", value.get("binding_refs", []))
    roots = value.get("source_roots", [])
    if any(not isinstance(row, list) or any(not isinstance(x, str) or not x for x in row) for row in (event_refs, binding_refs, roots)):
        _fail("representation-insufficient", "schema support references are invalid")
    row = {"schema": "cassifi.open-vocab-action-schema.v1", "action": action, "preconditions": pre, "effects": effects, "parameters": normalized_params, "guards": normalized_guards, "bounds": {"max_horizon": max_horizon, "max_work": max_work}, "support_event_refs": sorted(event_refs), "support_binding_refs": sorted(binding_refs), "source_roots": sorted(set(roots)), "codec": codec_descriptor(), "layout_schema": OPEN_VOCAB_LAYOUT_SCHEMA}
    if "holdout" in value:
        if not isinstance(value["holdout"], Mapping):
            _fail("representation-insufficient", "schema holdout metadata is invalid")
        row["holdout"] = json.loads(_json(value["holdout"]))
    row["schema_digest"] = _digest({k: row[k] for k in row if k != "schema_digest"})
    return row


def candidate_digest(candidate: Mapping[str, Any]) -> str:
    return canonical_action_schema(candidate)["schema_digest"]
def induce_action_schema_candidates(training_episodes: Sequence[Mapping[str, Any]], holdout_episodes: Sequence[Mapping[str, Any]] = (), *, max_candidates: int = 8, max_work: int = 4096) -> dict[str, Any]:
    if not training_episodes:
        _fail("support-gap", "schema induction requires grounded demonstrations")
    train = [canonical_grounded_episode(x) for x in training_episodes]
    holdout = [canonical_grounded_episode(x) for x in holdout_episodes]
    if set(x["event_id"] for x in train) & set(x["event_id"] for x in holdout):
        _fail("support-gap", "training and holdout episodes must be disjoint")
    if any(not ep["observation"]["success"] for ep in train):
        return {"status": "unresolved", "reason": "negative-demonstration", "candidates": []}
    if len(train) > max_work:
        return {"status": "resource-exhausted", "reason": "induction-work-bound", "candidates": []}
    params: list[dict[str, Any]] = []
    shared: dict[str, dict[str, Any]] = {}
    action = _anti_unify_shared([ep["action"] for ep in train], params, shared, "/action")
    pre = _anti_unify_shared([ep["pre_state"] for ep in train], params, shared, "/pre")
    post = _anti_unify_shared([ep["post_state"] for ep in train], params, shared, "/post")
    candidate = canonical_action_schema({"action": action, "preconditions": [pre], "effects": [post], "parameters": params, "support_event_refs": [x["event_id"] for x in train], "source_roots": sorted({s for x in train for s in x["source_revision_ids"]}), "holdout": {"count": len(holdout), "disjoint": True}})
    holdout_rows = []
    for episode_row in holdout:
        match = unify_terms(candidate["preconditions"][0], episode_row["pre_state"], guards=candidate["guards"])
        predicted = False
        if match.get("status") == "supported":
            instantiated = instantiate_schema(candidate, match.get("substitution", {}))
            predicted = _ground(instantiated["action"]) and _ground(instantiated["effects"][0]) and alpha_equivalent(instantiated["effects"][0], episode_row["post_state"])
        holdout_rows.append({"event_id": episode_row["event_id"], "predicted": predicted})
    if any(not row["predicted"] for row in holdout_rows):
        return {"status": "unresolved", "reason": "holdout-contradiction", "candidates": [], "holdout": holdout_rows}
    candidate["holdout"] = {"count": len(holdout_rows), "identities": [row["event_id"] for row in holdout_rows], "predictions": holdout_rows}
    candidate["schema_digest"] = _digest({k: candidate[k] for k in candidate if k != "schema_digest"})
    return {"status": "supported", "candidates": [candidate][:max_candidates], "training_event_refs": [x["event_id"] for x in train], "holdout_event_refs": [x["event_id"] for x in holdout]}


def instantiate_schema(schema: Mapping[str, Any], substitution: Mapping[str, Any] | Substitution) -> dict[str, Any]:
    schema = canonical_action_schema(schema)
    mapping = substitution.mapping if isinstance(substitution, Substitution) else substitution
    return {**schema, "action": apply_substitution(schema["action"], mapping), "preconditions": [apply_substitution(x, mapping) for x in schema["preconditions"]], "effects": [apply_substitution(x, mapping) for x in schema["effects"]], "guards": schema["guards"]}

def _term_variables(term: Mapping[str, Any]) -> set[tuple[str, str]]:
    if term["kind"] == "variable":
        return {(term["scope"], term["name"])}
    if term["kind"] == "constructor":
        return set().union(*(_term_variables(x) for x in term["args"])) if term["args"] else set()
    if term["kind"] == "sequence":
        return set().union(*(_term_variables(x) for x in term["items"])) if term["items"] else set()
    if term["kind"] == "record":
        return set().union(*(_term_variables(x) for x in term["fields"].values())) if term["fields"] else set()
    return set()


def _ground(term: Mapping[str, Any]) -> bool:
    return not _term_variables(term)


def _matches(goal: Mapping[str, Any], value: Mapping[str, Any]) -> bool:
    return _ground(value) and unify_terms(goal, value).get("status") == "supported"


def _state_facts(term: Mapping[str, Any]) -> list[dict[str, Any]]:
    state = canonical_term(term)
    if state["kind"] == "record":
        return [state]
    if state["kind"] == "sequence":
        return list(state["items"])
    _fail("representation-insufficient", "state must be a record fact or sequence of facts")


def _state_term(facts: Sequence[Mapping[str, Any]], original: Mapping[str, Any]) -> dict[str, Any]:
    if canonical_term(original)["kind"] == "record" and len(facts) == 1:
        return canonical_term(facts[0])
    return canonical_term({"kind": "sequence", "items": list(facts)})


def _merge_substitutions(base: Mapping[Any, Mapping[str, Any]], extra: Mapping[Any, Mapping[str, Any]]) -> dict[Any, Mapping[str, Any]] | None:
    merged = dict(base)
    for key, value in extra.items():
        value = apply_substitution(value, merged)
        if key in merged and not alpha_equivalent(apply_substitution(merged[key], merged), value):
            return None
        merged[key] = value
    return merged


def _match_state_preconditions(preconditions: Sequence[Mapping[str, Any]], facts: Sequence[Mapping[str, Any]], guards: Sequence[Mapping[str, Any]]) -> tuple[dict[Any, Mapping[str, Any]], tuple[int, ...]] | None:
    def visit(index: int, subst: Mapping[Any, Mapping[str, Any]], used: tuple[int, ...]):
        if index == len(preconditions):
            return dict(subst), used
        goal = apply_substitution(preconditions[index], subst)
        for fact_index, fact in enumerate(facts):
            if fact_index in used:
                continue
            result = unify_terms(goal, fact, guards=(), max_alternatives=1)
            if result.get("status") != "supported":
                continue
            raw_substitution = result["substitution"]
            extra = {}
            for binding in raw_substitution.get("bindings", []):
                variable = str(binding["variable"])
                scope, name = variable.split(":", 1)
                extra[(scope, name)] = binding["term"]
            merged = _merge_substitutions(subst, extra)
            if merged is None:
                continue
            checked, reason = check_guards(guards, merged)
            if checked:
                found = visit(index + 1, merged, used + (fact_index,))
                if found is not None:
                    return found
        return None
    return visit(0, {}, ())


def _state_satisfies_goal(facts: Sequence[Mapping[str, Any]], goal: Mapping[str, Any]) -> bool:
    goals = _state_facts(goal)
    return _match_state_preconditions(goals, facts, ()) is not None


def generate_relational_plan(initial_state: Mapping[str, Any], goal: Mapping[str, Any], schemas: Sequence[Mapping[str, Any]], *, limits: Mapping[str, Any] | None = None, basis_field_sha256: str | None = None) -> dict[str, Any]:
    lim = {"max_depth": 4, "max_work": 1024, "max_branches": 64, **dict(limits or {})}
    start, target = canonical_term(initial_state), canonical_term(goal)
    rows_by_digest = {canonical_action_schema(s)["schema_digest"]: canonical_action_schema(s) for s in schemas}
    rows = list(rows_by_digest.values())
    frontier: list[tuple[list[dict[str, Any]], list[dict[str, Any]], int, frozenset[str]]] = [(_state_facts(start), [], 0, frozenset())]
    visited: set[str] = set()
    work = 0
    solutions: list[dict[str, Any]] = []
    while frontier:
        if len(frontier) > int(lim["max_branches"]):
            return {"status": "resource-exhausted", "reason": "plan-branch-bound", "alternatives": [], "work": work, "plan_id": _digest({"initial": start, "goal": target, "basis": basis_field_sha256})}
        facts, segments, depth, used = frontier.pop(0)
        state = _state_term(facts, start)
        work += 1
        if work > int(lim["max_work"]):
            return {"status": "resource-exhausted", "reason": "plan-work-bound", "work": work, "alternatives": [], "plan_id": _digest({"initial": start, "goal": target, "basis": basis_field_sha256, "work": work})}
        if _state_satisfies_goal(facts, target):
            solutions.append({"segments": segments, "state": state, "used": sorted(used)})
            continue
        state_digest = _digest(facts)
        if state_digest in visited:
            continue
        visited.add(state_digest)
        if depth >= int(lim["max_depth"]):
            continue
        for schema in sorted(rows, key=lambda s: s["schema_digest"]):
            if depth >= int(schema["bounds"]["max_horizon"]):
                continue
            matched = _match_state_preconditions(schema["preconditions"], facts, schema["guards"])
            if matched is None:
                continue
            substitution, consumed = matched
            instantiated = instantiate_schema(schema, substitution)
            effect_goal = unify_terms(instantiated["effects"][0], target, guards=schema["guards"], max_alternatives=1) if len(instantiated["effects"]) == 1 else {"status": "unresolved"}
            if effect_goal.get("status") == "supported":
                raw_goal_substitution = effect_goal["substitution"]
                goal_extra = {}
                for binding in raw_goal_substitution.get("bindings", []):
                    scope, name = str(binding["variable"]).split(":", 1)
                    goal_extra[(scope, name)] = binding["term"]
                merged = _merge_substitutions(substitution, goal_extra)
                if merged is not None:
                    instantiated = instantiate_schema(schema, merged)
                    substitution = merged
            if not _ground(instantiated["action"]) or any(not _ground(effect) for effect in instantiated["effects"]):
                continue
            next_facts = [fact for i, fact in enumerate(facts) if i not in consumed]
            next_facts.extend(instantiated["effects"])
            segment = {"level": "strategic" if depth == 0 else "tactical", "kind": "action", "action": instantiated["action"], "schema_digest": schema["schema_digest"], "substitution": {"bindings": [{"variable": f"{k[0]}:{k[1]}" if isinstance(k, tuple) else str(k), "term": v} for k, v in sorted(substitution.items(), key=lambda item: str(item[0]))]}}
            if len(frontier) >= int(lim["max_branches"]):
                return {"status": "resource-exhausted", "reason": "plan-branch-bound", "alternatives": [], "work": work, "plan_id": _digest({"initial": start, "goal": target, "basis": basis_field_sha256})}
            frontier.append((next_facts, segments + [segment], depth + 1, used | {schema["schema_digest"]}))
    unique = {}
    for solution in solutions:
        unique[_digest(solution["segments"])] = solution
    solutions = list(unique.values())
    if not solutions:
        return {"status": "unresolved", "reason": "inconsistent-constraints", "alternatives": [], "work": work, "plan_id": _digest({"initial": start, "goal": target, "basis": basis_field_sha256, "work": work})}
    alternatives = [{"segments": x["segments"]} for x in solutions]
    if len(solutions) != 1:
        return {"status": "alternatives", "reason": "multiple-relational-plans", "alternatives": alternatives, "work": work, "plan_id": _digest(alternatives)}
    return {"schema": "cassifi.open-vocab-plan.v1", "plan_id": _digest({"initial": start, "goal": target, "basis": basis_field_sha256, "segments": solutions[0]["segments"]}), "basis_field_sha256": basis_field_sha256, "goal": target, "initial_state": start, "segments": solutions[0]["segments"], "remaining_dependencies": solutions[0]["used"], "source_roots": sorted({root for schema in rows for root in schema["source_roots"] if schema["schema_digest"] in solutions[0]["used"]}), "status": "supported", "alternatives": [], "work": work}

def repair_relational_plan(plan: Mapping[str, Any], observation: Mapping[str, Any], schemas: Sequence[Mapping[str, Any]], *, limits: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(plan, Mapping) or plan.get("schema") != "cassifi.open-vocab-plan.v1":
        _fail("representation-insufficient", "plan is not a canonical open-vocabulary plan")
    expected_plan_id = _digest({"initial": canonical_term(plan["initial_state"]), "goal": canonical_term(plan["goal"]), "basis": plan.get("basis_field_sha256"), "segments": list(plan.get("segments", []))})
    if plan.get("plan_id") != expected_plan_id:
        return {"status": "support-gap", "reason": "plan-digest-mismatch", "segments": []}
    obs = canonical_grounded_episode(observation)
    if not obs["observation"]["success"]:
        return {"status": "support-gap", "reason": "observation-failed", "segments": []}
    segments = list(plan.get("segments", []))
    completed = observation.get("completed_segments", observation.get("completed", 1))
    if isinstance(completed, bool) or not isinstance(completed, int) or not 0 <= completed <= len(segments):
        _fail("representation-insufficient", "completed segment count is invalid")
    schema_map = {canonical_action_schema(s)["schema_digest"]: canonical_action_schema(s) for s in schemas}
    facts = _state_facts(plan["initial_state"])
    prefix_before_observation = _state_term(facts, plan["initial_state"])
    for index, segment in enumerate(segments[:completed]):
        schema = schema_map.get(segment.get("schema_digest"))
        if schema is None:
            return {"status": "support-gap", "reason": "missing-completed-schema", "segments": segments[:index]}
        matched = _match_state_preconditions(schema["preconditions"], facts, schema["guards"])
        if matched is None:
            return {"status": "support-gap", "reason": "completed-prefix-unreplayable", "segments": segments[:index]}
        substitution, consumed = matched
        instantiated = instantiate_schema(schema, substitution)
        if not _ground(instantiated["action"]) or any(not _ground(effect) for effect in instantiated["effects"]):
            return {"status": "support-gap", "reason": "completed-prefix-not-ground", "segments": segments[:index]}
        if not alpha_equivalent(instantiated["action"], segment.get("action")):
            return {"status": "support-gap", "reason": "completed-action-mismatch", "segments": segments[:index]}
        if index == completed - 1:
            prefix_before_observation = _state_term(facts, plan["initial_state"])
        facts = [fact for i, fact in enumerate(facts) if i not in consumed] + instantiated["effects"]
    if completed and not alpha_equivalent(obs["action"], segments[completed - 1].get("action")):
        return {"status": "support-gap", "reason": "observation-action-mismatch", "segments": segments[:completed]}
    state = _state_term(facts, plan["initial_state"])
    if not alpha_equivalent(obs["pre_state"], prefix_before_observation) or not alpha_equivalent(obs["post_state"], state):
        return {"status": "support-gap", "reason": "observation-prefix-mismatch", "segments": segments[:completed]}
    suffix = generate_relational_plan(obs["post_state"], plan["goal"], schemas, limits=limits, basis_field_sha256=plan.get("basis_field_sha256"))
    if suffix.get("status") == "supported":
        suffix["segments"] = segments[:completed] + suffix.get("segments", [])
        suffix["repaired_from"] = plan["plan_id"]
        suffix["affected_frontier"] = completed
        suffix["plan_id"] = _digest({"repaired_from": plan["plan_id"], "segments": suffix["segments"]})
    return suffix

__all__ = ["OPEN_VOCAB_CODEC_SCHEMA", "OPEN_VOCAB_LAYOUT_SCHEMA", "OpenVocabError", "Substitution", "UnificationAlternative", "encode_lexeme", "decode_lexeme", "canonical_symbols", "codec_descriptor", "canonical_type", "canonical_term", "instantiate_template", "term_digest", "alpha_normalize", "alpha_equivalent", "apply_substitution", "check_guards", "unify_terms", "canonical_grounded_episode", "episode_source_payload", "canonical_action_schema", "candidate_digest", "induce_action_schema_candidates", "instantiate_schema", "generate_relational_plan", "repair_relational_plan"]
