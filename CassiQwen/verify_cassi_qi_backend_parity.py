"""Independently verify a W14A/G14A backend parity artifact.

This module deliberately imports no Cassi runtime module.  It parses the
canonical JSON and little-endian raw tensor bytes itself, then checks the
content-addressed manifest, backend identities, prepared handles, parity
receipts, counters, guard bands, and mutation controls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent
TERM_ORDER = ("current", "momentum", "work", "topology", "receipt", "state")
INDEX_SCHEMA = "cassi.qi-flow-w14a-run-index.v1"
MANIFEST_SCHEMA = "cassi.qi-flow-w14a-manifest.v1"
GATE_INDEX_SCHEMA = "cassi.qi-flow-w14a-gate-index.v1"
TERM_SCHEMA = "cassi.qi-flow-w14a-termwise-receipt.v1"
TRAJECTORY_SCHEMA = "cassi.qi-flow-w14a-trajectory-receipt.v1"
CONTROL_SCHEMA = "cassi.qi-flow-w14a-mutation-controls.v1"
RAW_SCHEMA = "cassi.qi-flow-w14a-raw-index.v1"
STATUS_SCHEMA = "cassi.qi-flow-gate-status.v1"
BACKEND_PROBE_SCHEMA = "cassi.qi-flow-backend-probe.v1"
BACKEND_IDENTITY_SCHEMA = "cassi.qi-flow-backend-identity.v1"
BACKEND_CAPABILITY_SCHEMA = "cassi.qi-flow-backend-capability.v1"
BACKEND_MEMORY_SCHEMA = "cassi.qi-flow-backend-memory.v1"
BACKEND_OPERATOR_SCHEMA = "cassi.qi-flow-backend-operator.v1"
BACKEND_RECEIPT_SCHEMA = "cassi.qi-flow-backend-receipt.v1"
BACKEND_STEP_SCHEMA = "cassi.qi-flow-backend-step.v1"

_SHA = re.compile(r"^[0-9a-f]{64}$")
_FLOAT_TAG = re.compile(r"^f(32|64):([0-9a-f]+)$")


class W14AArtifactVerificationError(RuntimeError):
    """The artifact is malformed, stale, mutated, or semantically inconsistent."""


# This is intentionally a small independent implementation of the frozen
# bootstrap codec.  No import of cassi_qi_bootstrap/profile/backend is allowed.
def _tagged_float(value: str) -> None:
    match = _FLOAT_TAG.fullmatch(value)
    if match is None:
        raise W14AArtifactVerificationError(f"invalid finite-bit scalar: {value!r}")
    width, encoded = match.groups()
    expected = 8 if width == "32" else 16
    if len(encoded) != expected or encoded.lower() != encoded:
        raise W14AArtifactVerificationError("finite-bit scalar has invalid width/case")
    try:
        number = struct.unpack(">f" if width == "32" else ">d", bytes.fromhex(encoded))[0]
    except (ValueError, struct.error) as exc:
        raise W14AArtifactVerificationError("finite-bit scalar has invalid payload") from exc
    if not math.isfinite(number) or (number == 0.0 and math.copysign(1.0, number) < 0.0):
        raise W14AArtifactVerificationError("finite-bit scalar is nonfinite or negative zero")


def _normalise(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        if abs(value) > (1 << 53) - 1:
            raise W14AArtifactVerificationError("integer exceeds canonical exact range")
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or (value == 0.0 and math.copysign(1.0, value) < 0.0):
            raise W14AArtifactVerificationError("decimal is nonfinite or negative zero")
        return "f64:" + struct.pack(">d", value).hex()
    if isinstance(value, str):
        if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
            raise W14AArtifactVerificationError("surrogate in canonical string")
        if value.startswith(("f32:", "f64:")):
            _tagged_float(value)
        return value
    if isinstance(value, list):
        return [_normalise(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalise(item) for key, item in value.items()}
    raise W14AArtifactVerificationError(f"unsupported canonical value {type(value).__name__}")


def _quote(value: str) -> str:
    pieces = ['"']
    for char in value:
        codepoint = ord(char)
        if char == '"':
            pieces.append('\\"')
        elif char == "\\":
            pieces.append("\\\\")
        elif codepoint <= 0x1F:
            pieces.append(f"\\u{codepoint:04x}")
        else:
            pieces.append(char)
    pieces.append('"')
    return "".join(pieces)


def _encode(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return _quote(value)
    if isinstance(value, list):
        return "[" + ",".join(_encode(item) for item in value) + "]"
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda item: item[0].encode("utf-8", "strict"))
        return "{" + ",".join(_quote(str(key)) + ":" + _encode(item) for key, item in items) + "}"
    raise W14AArtifactVerificationError(f"unsupported canonical value {type(value).__name__}")


def _canonical_bytes(value: Any) -> bytes:
    return _encode(_normalise(value)).encode("utf-8", "strict")


def _canonical_hash(value: Any, domain: str) -> str:
    domain_bytes = domain.encode("utf-8", "strict")
    payload = _canonical_bytes(value)
    frame = len(domain_bytes).to_bytes(8, "big") + domain_bytes + len(payload).to_bytes(8, "big") + payload
    return hashlib.sha256(frame).hexdigest()


def _stable_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise W14AArtifactVerificationError(message)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except Exception as exc:
        raise W14AArtifactVerificationError(f"invalid JSON: {path}") from exc
    _require(isinstance(value, dict), f"JSON object required: {path}")
    canonical = _canonical_bytes(value)
    accepted = {canonical, canonical + b"\n"}
    _require(raw in accepted, f"noncanonical JSON bytes: {path}")
    return value


def _safe_path(root: Path, relative: str) -> Path:
    _require(isinstance(relative, str) and relative and not Path(relative).is_absolute(), "relative artifact path required")
    path = (root / relative).resolve()
    _require(path == root.resolve() or root.resolve() in path.parents, f"artifact path escapes root: {relative}")
    return path


def _require_sha(value: Any, context: str) -> str:
    _require(isinstance(value, str) and _SHA.fullmatch(value) is not None, f"{context} is not a SHA-256 digest")
    return value


def _verify_hash_field(payload: Mapping[str, Any], field: str, domain: str, context: str) -> None:
    declared = _require_sha(payload.get(field), f"{context}.{field}")
    unsigned = {key: value for key, value in payload.items() if key != field}
    _require(_canonical_hash(unsigned, domain) == declared, f"{context} {field} mismatch")


def _verify_manifest(root: Path, index: Mapping[str, Any]) -> int:
    manifest_path = root / "manifest.json"
    manifest = _read_json(manifest_path)
    _require(manifest.get("schema") == MANIFEST_SCHEMA, "manifest schema mismatch")
    declared = _require_sha(manifest.get("manifest_sha256"), "manifest.manifest_sha256")
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    _require(_sha(_stable_bytes(body)) == declared, "manifest self hash mismatch")
    _require(index.get("manifest_sha256") == declared, "index manifest hash mismatch")
    rows = manifest.get("files")
    _require(isinstance(rows, list) and rows, "manifest file list is empty")
    expected: set[str] = set()
    for row in rows:
        _require(isinstance(row, dict), "manifest file row is not an object")
        relative = row.get("path")
        _require(isinstance(relative, str) and relative not in expected, "manifest path is duplicated")
        expected.add(relative)
        path = _safe_path(root, relative)
        _require(path.is_file(), f"manifest file is missing: {relative}")
        raw = path.read_bytes()
        _require(row.get("bytes") == len(raw), f"manifest byte count mismatch: {relative}")
        _require(row.get("sha256") == _sha(raw), f"manifest hash mismatch: {relative}")
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path.relative_to(root).as_posix() not in {"manifest.json", "index.json"}}
    _require(actual == expected, "manifest file set mismatch")
    return len(rows)


def _verify_index(root: Path) -> dict[str, Any]:
    index = _read_json(root / "index.json")
    _require(index.get("schema") == INDEX_SCHEMA, "run index schema mismatch")
    run_id = _require_sha(index.get("run_id"), "index.run_id")
    _require(run_id == root.name, "run_id does not equal content-addressed directory")
    artifact = _require_sha(index.get("artifact_sha256"), "index.artifact_sha256")
    body = {key: value for key, value in index.items() if key not in {"run_id", "artifact_sha256"}}
    _require(_sha(_stable_bytes(body)) == artifact == run_id, "index content hash mismatch")
    _require(index.get("gate") == "G14A", "index gate mismatch")
    _require(index.get("gate_relative_path") == "gates/g14a-operator-parity", "gate path mismatch")
    return index


def _verify_sources(root: Path, index: Mapping[str, Any]) -> None:
    sources = index.get("source_identity")
    _require(isinstance(sources, dict) and sources, "source identity is missing")
    _require(index.get("source_identity_sha256") == _sha(_stable_bytes(sources)), "source identity hash mismatch")
    for relative, digest in sources.items():
        _require_sha(digest, f"source identity {relative}")
        path = _safe_path(root, "run-spec/sources/" + relative)
        _require(path.is_file(), f"source snapshot missing: {relative}")
        _require(_sha(path.read_bytes()) == digest, f"source snapshot hash mismatch: {relative}")
        live = ROOT / relative
        if live.is_file():
            _require(_sha(live.read_bytes()) == digest, f"live source identity mismatch: {relative}")


def _verify_registry(root: Path, index: Mapping[str, Any]) -> None:
    registry = index.get("registry")
    _require(isinstance(registry, dict), "registry identity missing")
    relative = registry.get("manifest_path")
    path = _safe_path(root, str(relative))
    raw = path.read_bytes()
    _require(registry.get("source_sha256") == _sha(raw), "registry source hash mismatch")
    manifest = _read_json(path)
    _require(manifest.get("schema") == "cassi.qi-flow-schema-registry.v1", "static schema registry schema mismatch")
    entries = manifest.get("entry_hashes")
    _require(isinstance(entries, list) and manifest.get("entry_count") == len(entries), "static schema registry entry count mismatch")
    names = {row.get("schema") for row in entries if isinstance(row, dict)}
    required = registry.get("required_schemas")
    _require(isinstance(required, list) and required and all(name in names for name in required), "required backend schema is absent from registry")
    _require(_canonical_hash({key: value for key, value in manifest.items() if key != "self_sha256"}, "cassi.qi-flow-schema-registry.v1") == manifest.get("self_sha256"), "static schema registry self hash mismatch")


def _verify_profiles(root: Path, index: Mapping[str, Any]) -> None:
    identities = index.get("profile_identity")
    _require(isinstance(identities, dict), "profile identity missing")
    for name, identity in identities.items():
        _require(isinstance(identity, dict), f"profile identity {name} malformed")
        profile = _read_json(root / "run-spec" / "profiles" / f"{name}.json")
        declared = _require_sha(profile.get("profile_sha256"), f"profile {name}.profile_sha256")
        _require(identity.get("profile_sha256") == declared, f"profile identity mismatch: {name}")
        _require(identity.get("dtype") in {"float32", "float64"}, f"profile dtype missing: {name}")
        _require(identity.get("device") in {"cpu", "cuda"}, f"profile device missing: {name}")
        _require(profile.get("field", {}).get("dtype") == identity.get("dtype"), f"profile field dtype mismatch: {name}")
        _require(profile.get("backend_contract", {}).get("device") == identity.get("device"), f"profile backend device mismatch: {name}")
        # profile_sha256 is defined over the complete object before its own field is added.
        unsigned = {key: value for key, value in profile.items() if key != "profile_sha256"}
        _require(_canonical_hash(unsigned, "cassi.qi-flow-profile.v1") == declared, f"profile self hash mismatch: {name}")
    _require(identities.get("oracle", {}).get("dtype") == "float64" and identities.get("oracle", {}).get("device") == "cpu", "oracle is not CPU float64")
    _require(identities.get("cpu-f32", {}).get("dtype") == "float32" and identities.get("cpu-f32", {}).get("device") == "cpu", "CPU candidate is not float32")


def _verify_identity_payload(payload: Mapping[str, Any], label: str) -> None:
    if payload.get("status") == "NOT_RUN":
        _require(payload.get("fallback") is False, f"{label} unavailable path may not fallback")
        return
    _require(payload.get("schema") == BACKEND_IDENTITY_SCHEMA, f"{label} backend identity schema mismatch")
    _verify_hash_field(payload, "identity_sha256", BACKEND_IDENTITY_SCHEMA, label)
    _require(payload.get("backend") == "torch", f"{label} backend is not torch")
    _require(payload.get("fallback_count") == 0, f"{label} reports fallback")
    _require(payload.get("deterministic_algorithms") is True, f"{label} is not deterministic")
    _require(payload.get("same_backend_exact_replay") is True, f"{label} lacks exact replay")
    _require(payload.get("device_type") in {"cpu", "cuda"}, f"{label} device type invalid")
    _require(payload.get("dtype") in {"float32", "float64"}, f"{label} dtype invalid")


def _verify_capability_payload(payload: Mapping[str, Any], label: str) -> None:
    if payload.get("status") == "NOT_RUN":
        _require(payload.get("fallback") is False, f"{label} unavailable capability may not fallback")
        return
    _require(payload.get("schema") == BACKEND_CAPABILITY_SCHEMA, f"{label} capability schema mismatch")
    _verify_hash_field(payload, "capability_sha256", BACKEND_CAPABILITY_SCHEMA, label)
    _require(payload.get("available") is True, f"{label} capability is unavailable despite execution")


def _verify_memory_payload(payload: Mapping[str, Any], label: str) -> None:
    _require(payload.get("schema") == BACKEND_MEMORY_SCHEMA, f"{label} memory schema mismatch")
    _verify_hash_field(payload, "receipt_sha256", BACKEND_MEMORY_SCHEMA, label)
    for key in ("state_bytes", "peak_working_bytes", "allocated_bytes", "reserved_bytes", "allocation_count", "copy_count", "synchronization_count", "op_count", "wall_time_ns", "prepared_cache_entries", "prepared_cache_hits", "prepared_cache_misses"):
        _require(isinstance(payload.get(key), int) and not isinstance(payload.get(key), bool) and payload[key] >= 0, f"{label} counter {key} invalid")
    _require(payload["peak_working_bytes"] >= payload["allocated_bytes"] and payload["allocated_bytes"] >= payload["state_bytes"], f"{label} memory bounds are inconsistent")
    _require(payload["prepared_cache_hits"] + payload["prepared_cache_misses"] >= payload["prepared_cache_entries"], f"{label} cache counters are inconsistent")


def _verify_prepared(payload: Mapping[str, Any], label: str) -> None:
    _require(payload.get("schema") == BACKEND_OPERATOR_SCHEMA, f"{label} prepared schema mismatch")
    _require(payload.get("operator_id") in {"fixed-affine-scale-v1", "backend-additive-advance-v1"}, f"{label} operator id invalid")
    _require(payload.get("dtype") in {"float32", "float64"}, f"{label} prepared dtype invalid")
    for key in ("profile_sha256", "operator_sha256", "operator_cache_sha256", "backend_identity_sha256", "prepared_sha256"):
        _require_sha(payload.get(key), f"{label}.{key}")
    _require(isinstance(payload.get("batch"), int) and payload["batch"] >= 1, f"{label} prepared batch invalid")
    _require(isinstance(payload.get("allocation_bytes"), int) and payload["allocation_bytes"] >= 0, f"{label} prepared allocation invalid")
    unsigned = {key: value for key, value in payload.items() if key != "prepared_sha256"}
    _require(_canonical_hash(unsigned, BACKEND_OPERATOR_SCHEMA) == payload["prepared_sha256"], f"{label} prepared hash mismatch")


def _finite_tag_number(value: Any, context: str) -> float:
    if isinstance(value, str) and _FLOAT_TAG.fullmatch(value):
        width = value[1:3]
        raw = bytes.fromhex(value[4:])
        return struct.unpack(">f" if width == "32" else ">d", raw)[0]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raise W14AArtifactVerificationError(f"{context} is not numeric")


def _verify_term(term: Mapping[str, Any], expected_name: str, context: str) -> None:
    _require(term.get("name") == expected_name, f"{context} term order/name mismatch")
    _require_sha(term.get("reference_sha256"), f"{context}.reference_sha256")
    _require_sha(term.get("candidate_sha256"), f"{context}.candidate_sha256")
    status = term.get("status")
    _require(status in {"PASS", "FAIL", "ABSTAIN", "NOT_RUN"}, f"{context} term status invalid")
    _require(isinstance(term.get("compared_values"), int) and term["compared_values"] >= 0, f"{context} compared count invalid")
    _require(isinstance(term.get("mismatch_count"), int) and term["mismatch_count"] >= 0, f"{context} mismatch count invalid")
    tolerance = _finite_tag_number(term.get("tolerance"), f"{context}.tolerance")
    safe = _finite_tag_number(term.get("safe_tolerance"), f"{context}.safe_tolerance")
    _require(math.isfinite(tolerance) and tolerance > 0.0 and math.isfinite(safe) and safe > 0.0 and safe < tolerance, f"{context} guard band invalid")
    if status == "NOT_RUN":
        _require(term.get("max_abs_error") is None, f"{context} unexecuted term has error")
    else:
        error = _finite_tag_number(term.get("max_abs_error"), f"{context}.max_abs_error")
        _require(math.isfinite(error) and error >= 0.0, f"{context} error invalid")


def _verify_parity_receipt(payload: Mapping[str, Any], label: str, *, profile_sha: str, guard_sha: str, executed: bool) -> None:
    _require(payload.get("schema") == BACKEND_PROBE_SCHEMA, f"{label} parity schema mismatch")
    _verify_hash_field(payload, "receipt_sha256", BACKEND_PROBE_SCHEMA, label)
    _require(payload.get("oracle_profile_sha256") == profile_sha or payload.get("profile_sha256") == profile_sha, f"{label} profile identity mismatch")
    _require(payload.get("guard_sha256") == guard_sha, f"{label} guard identity mismatch")
    _require(payload.get("executed") is executed, f"{label} execution flag mismatch")
    terms = payload.get("terms")
    _require(isinstance(terms, list) and [term.get("name") for term in terms] == list(TERM_ORDER), f"{label} term order mismatch")
    for name, term in zip(TERM_ORDER, terms):
        _require(isinstance(term, dict), f"{label} malformed term")
        _verify_term(term, name, label)
    statuses = {term["status"] for term in terms}
    expected = "NOT_RUN" if not executed else "FAIL" if "FAIL" in statuses else "ABSTAIN" if "ABSTAIN" in statuses else "PASS"
    _require(payload.get("parity_status") == expected, f"{label} parity status mismatch")
    if executed:
        _require_sha(payload.get("prepared_sha256"), f"{label}.prepared_sha256")
        _require_sha(payload.get("candidate_prepared_sha256"), f"{label}.candidate_prepared_sha256")
    counters = payload.get("counter_delta")
    _require(isinstance(counters, dict), f"{label} counter delta missing")
    for key, value in counters.items():
        _require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, f"{label} counter delta invalid: {key}")


def _verify_gate(root: Path, index: Mapping[str, Any]) -> dict[str, Any]:
    gate = root / "gates" / "g14a-operator-parity"
    gate_index = _read_json(gate / "index.json")
    _require(gate_index.get("schema") == GATE_INDEX_SCHEMA and gate_index.get("gate") == "G14A", "gate index mismatch")
    _require(gate_index.get("term_order") == list(TERM_ORDER), "gate index term order mismatch")
    status = _read_json(gate / "status.json")
    _require(status.get("schema") == STATUS_SCHEMA and status.get("gate") == "G14A", "gate status schema mismatch")
    _require(status.get("status") == index.get("status"), "gate/index status mismatch")
    termwise = _read_json(gate / "termwise.json")
    _require(termwise.get("schema") == TERM_SCHEMA and termwise.get("term_order") == list(TERM_ORDER), "termwise schema/order mismatch")
    guards_wrapper = _read_json(gate / "guard-bands.json")
    guards = guards_wrapper.get("payload")
    _require(guards_wrapper.get("schema") == BACKEND_PROBE_SCHEMA and isinstance(guards, dict), "guard wrapper malformed")
    _require(guards.get("schema") == BACKEND_PROBE_SCHEMA, "guard payload schema mismatch")
    _verify_hash_field(guards, "guard_sha256", BACKEND_PROBE_SCHEMA, "guard bands")
    guard_sha = guards["guard_sha256"]
    _require(guards.get("profile_sha256") == index.get("profile_identity", {}).get("oracle", {}).get("profile_sha256"), "guard profile identity mismatch")
    _require(isinstance(guards.get("terms"), dict) and set(guards["terms"]) == set(TERM_ORDER), "guard terms are incomplete")
    for name, value in guards["terms"].items():
        number = _finite_tag_number(value, f"guard.{name}")
        _require(math.isfinite(number) and number > 0.0, f"guard.{name} invalid")
    margin = _finite_tag_number(guards.get("strict_safety_margin"), "guard.strict_safety_margin")
    _require(0.0 < margin < 1.0, "guard safety margin invalid")

    comparisons = termwise.get("comparisons")
    _require(isinstance(comparisons, dict) and set(comparisons) == {"cpu-f32", "rocm-f32"}, "termwise comparisons are incomplete")
    for label, record in comparisons.items():
        _require(isinstance(record, dict), f"{label} comparison malformed")
        _require(record.get("label") == label and record.get("schema") == TERM_SCHEMA, f"{label} comparison identity mismatch")
        _require(record.get("fallback", False) is False, f"{label} fallback is forbidden")
        executed = record.get("executed") is True
        if label == "rocm-f32" and not executed:
            _require(record.get("status") == "NOT_RUN", "unavailable ROCm must be NOT_RUN")
            _require(isinstance(record.get("reason"), str) and record["reason"], "unavailable ROCm reason is missing")
            _require(record.get("requested_device") == "cuda:0", "ROCm request identity missing")
        else:
            _require(executed, f"{label} execution missing")
            _require(record.get("term_order") == list(TERM_ORDER), f"{label} term order missing")
            for section in ("advance", "fixed"):
                section_payload = record.get(section)
                _require(isinstance(section_payload, dict), f"{label} {section} section missing")
                _verify_parity_receipt(section_payload.get("receipt", {}), f"{label}.{section}", profile_sha=index["profile_identity"]["oracle"]["profile_sha256"], guard_sha=guard_sha, executed=True)
            prepared = record.get("prepared")
            _require(isinstance(prepared, dict), f"{label} prepared handles missing")
            for name, payload in prepared.items():
                _verify_prepared(payload, f"{label}.{name}")
            step = record.get("advance", {}).get("step_receipt")
            _require(isinstance(step, dict) and step.get("schema") == BACKEND_STEP_SCHEMA, f"{label} backend step receipt missing")
            _require(step.get("status") == "COMMITTED", f"{label} step not committed")
    trajectory = _read_json(gate / "trajectory.json")
    _require(trajectory.get("schema") == TRAJECTORY_SCHEMA and trajectory.get("term_order") == list(TERM_ORDER), "trajectory schema/order mismatch")
    trajectory_receipt = trajectory.get("receipt")
    _require(isinstance(trajectory_receipt, dict), "trajectory receipt missing")
    _verify_parity_receipt(trajectory_receipt, "trajectory", profile_sha=index["profile_identity"]["oracle"]["profile_sha256"], guard_sha=guard_sha, executed=trajectory.get("executed") is True)
    _require(trajectory.get("batch_size") == trajectory.get("independent_count") == trajectory_receipt.get("candidate_count"), "trajectory cardinality mismatch")
    if trajectory.get("executed"):
        _verify_prepared(trajectory.get("batched_prepared", {}), "trajectory.batched_prepared")
    controls = _read_json(gate / "mutation-controls.json")
    _require(controls.get("schema") == CONTROL_SCHEMA and controls.get("status") == "PASS", "mutation controls did not pass")
    rows = controls.get("controls")
    _require(isinstance(rows, list) and controls.get("control_count") == len(rows) and rows, "mutation controls are empty")
    _require(len({row.get("control_id") for row in rows}) == len(rows), "mutation control ids are duplicated")
    for row in rows:
        _require(isinstance(row, dict) and row.get("expected") == "REJECT" and row.get("observed") == "REJECT" and row.get("status") == "PASS", "mutation control failed")
    execution = _read_json(gate / "execution-counters.json")
    for label, payload in execution.items():
        if payload is not None:
            _verify_memory_payload(payload, f"execution.{label}")
    backend_receipts = _read_json(gate / "backend-receipts.json")
    for label, value in backend_receipts.items():
        if isinstance(value, dict) and value.get("schema") == BACKEND_MEMORY_SCHEMA:
            _verify_memory_payload(value, f"backend-receipt.{label}")
        elif isinstance(value, dict) and value.get("schema") == BACKEND_RECEIPT_SCHEMA:
            _verify_hash_field(value, "self_sha256", BACKEND_RECEIPT_SCHEMA, f"backend-receipt.{label}")
    raw_index = _read_json(gate / "raw-index.json")
    _require(raw_index.get("schema") == RAW_SCHEMA, "raw index schema mismatch")
    objects = raw_index.get("objects")
    _require(isinstance(objects, list) and objects, "raw index is empty")
    for row in objects:
        _require(isinstance(row, dict), "raw descriptor malformed")
        path = _safe_path(root, str(row.get("path")))
        raw = path.read_bytes()
        _require(row.get("bytes") == len(raw) and row.get("sha256") == _sha(raw), f"raw object hash mismatch: {row.get('role')}")
        _require(row.get("dtype") in {"float32", "float64"} and row.get("byte_order") == "little", "raw dtype/byte order mismatch")
        shape = row.get("shape")
        _require(isinstance(shape, list) and shape and all(isinstance(dim, int) and dim >= 1 for dim in shape), "raw shape invalid")
        width = 4 if row["dtype"] == "float32" else 8
        count = 1
        for dim in shape:
            count *= dim
        _require(len(raw) == count * width, f"raw byte shape mismatch: {row.get('role')}")
    return {"gate_status": status.get("status"), "guard_sha256": guard_sha, "raw_objects": len(objects), "executed_comparisons": [name for name, row in comparisons.items() if row.get("executed") is True]}


def verify_artifact(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    if not (root / "index.json").is_file():
        candidates = sorted((item for item in root.iterdir() if item.is_dir() and (item / "index.json").is_file()), key=lambda item: item.name)
        _require(len(candidates) == 1, "verification requires one content-addressed artifact directory")
        root = candidates[0]
    index = _verify_index(root)
    files = _verify_manifest(root, index)
    _verify_sources(root, index)
    _verify_registry(root, index)
    _verify_profiles(root, index)
    identities = index.get("backend_identity")
    _require(isinstance(identities, dict), "backend identities missing")
    for label, payload in identities.items():
        _require(isinstance(payload, dict), f"backend identity {label} malformed")
        _verify_identity_payload(payload, label)
    gate = _verify_gate(root, index)
    executed = index.get("executed_backends")
    missing = index.get("missing_backends")
    _require(isinstance(executed, list) and "cpu-f64" in executed and "cpu-f32" in executed, "required CPU backends were not executed")
    _require(isinstance(missing, list), "missing backend list is malformed")
    if "rocm-f32" in missing:
        _require(index.get("status") == "NOT_RUN", "missing ROCm cannot claim overall PASS")
    if index.get("status") == "PASS":
        _require(not missing, "PASS artifact has missing backend")
    return {
        "schema": INDEX_SCHEMA,
        "status": "PASS",
        "gate_status": index.get("status"),
        "run_id": index["run_id"],
        "artifact": root.as_posix(),
        "verified_files": files,
        "executed_backends": executed,
        "missing_backends": missing,
        **gate,
    }


def verify(root: Path | str) -> dict[str, Any]:
    return verify_artifact(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify_artifact(args.artifact), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    except W14AArtifactVerificationError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
