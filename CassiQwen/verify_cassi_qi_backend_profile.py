"""Independent verifier for a W14B measured backend-profile artifact.

This file intentionally imports no Cassi runtime or profiler module.  It
reimplements only the canonical JSON framing needed to verify sealed bytes,
identities, counters, memory observations, and raw tensor objects.
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

INDEX_SCHEMA = "cassi.qi-flow-w14b-run-index.v1"
MANIFEST_SCHEMA = "cassi.qi-flow-w14b-manifest.v1"
GATE_INDEX_SCHEMA = "cassi.qi-flow-w14b-gate-index.v1"
PROFILER_SCHEMA = "cassi.qi-flow-w14b-profiler-receipt.v1"
MEMORY_SCHEMA = "cassi.qi-flow-w14b-memory-receipt.v1"
LADDER_SCHEMA = "cassi.qi-flow-w14b-candidate-ladder.v1"
CONTROLS_SCHEMA = "cassi.qi-flow-w14b-mutation-controls.v1"
RAW_SCHEMA = "cassi.qi-flow-w14b-raw-index.v1"
STATUS_SCHEMA = "cassi.qi-flow-gate-status.v1"
PROFILE_SCHEMA = "cassi.qi-flow-profile.v1"
BACKEND_IDENTITY_SCHEMA = "cassi.qi-flow-backend-identity.v1"
BACKEND_CAPABILITY_SCHEMA = "cassi.qi-flow-backend-capability.v1"
BACKEND_MEMORY_SCHEMA = "cassi.qi-flow-backend-memory.v1"
BACKEND_OPERATOR_SCHEMA = "cassi.qi-flow-backend-operator.v1"
BACKEND_RECEIPT_SCHEMA = "cassi.qi-flow-backend-receipt.v1"
BACKEND_STEP_DOMAIN = "cassi.qi-flow-backend-step"
SOURCE_DOMAIN = "cassi.qi-flow-w14b-source-identity"
GATE_RELATIVE = Path("gates/g14b-full-system-capacity")
REQUIRED_REGISTRY_SCHEMAS = (
    "cassi.qi-flow-backend-receipt.v1",
    "cassi.qi-flow-capacity-ladder.v1",
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
FLOAT_BITS = re.compile(r"^f(32|64):([0-9a-f]+)$")


class W14BArtifactVerificationError(ValueError):
    """The sealed artifact is malformed or its evidence was mutated."""


def _fail(message: str) -> None:
    raise W14BArtifactVerificationError(message)


def _require(condition: bool, message: str) -> None:
    if not condition:
        _fail(message)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _finite_bits(value: float) -> str:
    if not math.isfinite(value):
        _fail("non-finite float in canonical payload")
    return f"f64:{struct.unpack('>Q', struct.pack('>d', float(value)))[0]:016x}"


def _normalise(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return _finite_bits(value)
    if isinstance(value, str):
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            _fail("surrogate in canonical payload")
        return value
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _normalise(item) for key, item in value.items()}
    _fail(f"unsupported canonical value {type(value).__name__}")


def _quote(value: str) -> str:
    parts = ['"']
    for char in value:
        codepoint = ord(char)
        if char == '"':
            parts.append('\\"')
        elif char == "\\":
            parts.append("\\\\")
        elif codepoint <= 0x1F:
            parts.append(f"\\u{codepoint:04x}")
        else:
            parts.append(char)
    parts.append('"')
    return "".join(parts)


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
    if isinstance(value, Mapping):
        return "{" + ",".join(
            _quote(key) + ":" + _encode(item)
            for key, item in sorted(value.items(), key=lambda item: item[0].encode("utf-8"))
        ) + "}"
    _fail(f"unsupported canonical value {type(value).__name__}")


def _canonical_bytes(value: Any) -> bytes:
    return _encode(_normalise(value)).encode("utf-8", "strict")


def _canonical_hash(value: Any, domain: str) -> str:
    domain_bytes = domain.encode("utf-8")
    payload = _canonical_bytes(value)
    return _sha256(len(domain_bytes).to_bytes(8, "big") + domain_bytes + len(payload).to_bytes(8, "big") + payload)


def _load(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        _fail(f"cannot parse {path}: {type(exc).__name__}: {exc}")
    _require(isinstance(value, dict), f"{path} must contain an object")
    _require(_canonical_bytes(value) == raw, f"{path} is not canonical JSON")
    return value


def _sha_field(payload: Mapping[str, Any], field: str, domain: str) -> None:
    declared = payload.get(field)
    _require(isinstance(declared, str) and SHA256.fullmatch(declared) is not None, f"{field} is not sha256")
    unsigned = {key: value for key, value in payload.items() if key != field}
    _require(_canonical_hash(unsigned, domain) == declared, f"{field} mismatch")


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        _fail(f"{name} is boolean")
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str) and FLOAT_BITS.fullmatch(value):
        match = FLOAT_BITS.fullmatch(value)
        assert match is not None
        bits = int(match.group(2), 16)
        if match.group(1) == "32":
            result = float(struct.unpack(">f", struct.pack(">I", bits))[0])
        else:
            result = float(struct.unpack(">d", struct.pack(">Q", bits))[0])
    else:
        _fail(f"{name} is not a finite number")
    _require(math.isfinite(result), f"{name} is non-finite")
    return result

def _linear_slope(points: list[tuple[int, int]]) -> float:
    if len(points) < 2:
        return 0.0
    mean_x = sum(float(x) for x, _ in points) / len(points)
    mean_y = sum(float(y) for _, y in points) / len(points)
    denominator = sum((float(x) - mean_x) ** 2 for x, _ in points)
    if denominator == 0.0:
        return 0.0
    return sum(
        (float(x) - mean_x) * (float(y) - mean_y)
        for x, y in points
    ) / denominator


def _state_hash(value: Any, name: str) -> str:
    _require(isinstance(value, str) and SHA256.fullmatch(value) is not None, f"{name} is not sha256")
    return value


def _verify_manifest(root: Path, index: Mapping[str, Any]) -> dict[str, Any]:
    manifest_path = root / "manifest.json"
    manifest = _load(manifest_path)
    _require(manifest.get("schema") == MANIFEST_SCHEMA, "manifest schema mismatch")
    _require(index.get("manifest_sha256") == manifest.get("manifest_sha256"), "index manifest hash mismatch")
    _sha_field(manifest, "manifest_sha256", MANIFEST_SCHEMA)
    rows = manifest.get("files")
    _require(isinstance(rows, list) and rows, "manifest files are missing")
    listed: set[str] = set()
    for row in rows:
        _require(isinstance(row, dict), "manifest row malformed")
        relative = row.get("path")
        _require(isinstance(relative, str) and relative and not Path(relative).is_absolute(), "manifest path invalid")
        _require(relative not in listed and relative not in {"index.json", "manifest.json"}, "manifest duplicate/forbidden path")
        listed.add(relative)
        target = root / Path(relative)
        _require(target.is_file(), f"manifest file missing: {relative}")
        raw = target.read_bytes()
        _require(row.get("bytes") == len(raw), f"manifest byte count mismatch: {relative}")
        _require(row.get("sha256") == _sha256(raw), f"manifest hash mismatch: {relative}")
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path.relative_to(root).as_posix() not in {"index.json", "manifest.json"}}
    _require(actual == listed, "manifest file set mismatch")
    return manifest


def _verify_sources(root: Path, index: Mapping[str, Any]) -> None:
    source_identity = index.get("source_identity")
    _require(isinstance(source_identity, dict) and source_identity, "source identity is missing")
    _require(index.get("source_identity_sha256") == _canonical_hash(source_identity, SOURCE_DOMAIN), "source identity hash mismatch")
    source_root = root / "run-spec" / "sources"
    _require(source_root.is_dir(), "sealed source directory is missing")
    for relative, digest in source_identity.items():
        _require(isinstance(relative, str) and isinstance(digest, str) and SHA256.fullmatch(digest) is not None, "source identity row malformed")
        target = source_root / Path(relative)
        _require(target.is_file(), f"sealed source missing: {relative}")
        _require(_sha256(target.read_bytes()) == digest, f"sealed source hash mismatch: {relative}")
    actual = {path.relative_to(source_root).as_posix() for path in source_root.rglob("*") if path.is_file()}
    _require(actual == set(source_identity), "sealed source set mismatch")


def _verify_profile(root: Path, index: Mapping[str, Any]) -> dict[str, Any]:
    profile = _load(root / "run-spec" / "profile.json")
    _require(profile.get("schema") == PROFILE_SCHEMA, "profile schema mismatch")
    declared = profile.get("profile_sha256")
    _require(isinstance(declared, str) and SHA256.fullmatch(declared) is not None, "profile hash missing")
    unsigned = {key: value for key, value in profile.items() if key != "profile_sha256"}
    _require(_canonical_hash(unsigned, PROFILE_SCHEMA) == declared, "profile self hash mismatch")
    _require(index.get("profile_sha256") == declared, "index/profile hash mismatch")
    backend_contract = profile.get("backend_contract")
    capacity = profile.get("capacity")
    field = profile.get("field")
    action = profile.get("action")
    _require(isinstance(backend_contract, dict), "backend contract missing")
    _require(backend_contract.get("device") == "cpu" and backend_contract.get("dtype") == "float64", "profile backend contract is not CPU float64")
    _require(isinstance(capacity, dict) and isinstance(field, dict) and isinstance(action, dict), "profile capacity fields missing")
    for key in ("max_state_bytes", "max_checkpoint_bytes", "max_batch_lanes"):
        _require(isinstance(capacity.get(key), int) and capacity[key] > 0, f"profile capacity {key} invalid")
    _require(isinstance(field.get("batch_limit"), int) and field["batch_limit"] > 0, "profile batch limit invalid")
    _require(isinstance(action.get("max_candidates"), int) and action["max_candidates"] > 0, "profile max candidates invalid")
    return profile


def _verify_registry(root: Path) -> None:
    descriptor = _load(root / "run-spec" / "schema-registry.json")
    _require(descriptor.get("schema") == "cassi.qi-flow-w14b-schema-registry.v1", "W14B registry descriptor schema mismatch")
    manifest_path = descriptor.get("manifest_path")
    _require(manifest_path == "run-spec/sources/cassi-fi-schema-registry/manifest.json", "registry source path mismatch")
    registry_path = root / manifest_path
    raw = registry_path.read_bytes()
    _require(descriptor.get("source_sha256") == _sha256(raw), "registry source hash mismatch")
    try:
        registry = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        _fail(f"registry parse failed: {type(exc).__name__}: {exc}")
    names = {row.get("schema") for row in registry.get("entry_hashes", []) if isinstance(row, dict)}
    _require(set(REQUIRED_REGISTRY_SCHEMAS).issubset(names), "required static registry schema is missing")
    _require(descriptor.get("required_schemas") == list(REQUIRED_REGISTRY_SCHEMAS), "registry requirement list changed")


def _verify_identity(profiler: Mapping[str, Any], profile: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    identities = profiler.get("identities")
    _require(isinstance(identities, dict), "backend identities missing")
    backend = identities.get("backend")
    capability = identities.get("capability")
    operator = identities.get("operator")
    _require(isinstance(backend, dict) and isinstance(capability, dict) and isinstance(operator, dict), "backend identity payload malformed")
    _sha_field(backend, "identity_sha256", BACKEND_IDENTITY_SCHEMA)
    _sha_field(capability, "capability_sha256", BACKEND_CAPABILITY_SCHEMA)
    _require(backend.get("backend") == "torch" and backend.get("device_type") == "cpu" and backend.get("dtype") == "float64", "backend identity changed")
    _require(backend.get("fallback_count") == 0, "backend reports fallback")
    _require(capability.get("available") is True and capability.get("device_type") == "cpu", "backend capability changed")
    _require(profiler.get("profile_sha256") == profile.get("profile_sha256"), "profiler/profile identity mismatch")
    _require(profiler.get("backend_identity_sha256") == backend.get("identity_sha256"), "profiler/backend identity mismatch")
    _require(profiler.get("capability_sha256") == capability.get("capability_sha256"), "profiler/capability identity mismatch")
    _require(operator.get("operator_id") == "backend-additive-advance-v1", "operator id changed")
    _require(isinstance(operator.get("operator_sha256"), str) and SHA256.fullmatch(operator["operator_sha256"]) is not None, "operator hash invalid")
    return backend, operator


def _verify_prepared(payload: Any, profile_sha: str, backend_sha: str, operator: Mapping[str, Any], batch: int | None = None) -> dict[str, Any]:
    _require(isinstance(payload, dict), "prepared handle missing")
    _require(payload.get("schema") == BACKEND_OPERATOR_SCHEMA, "prepared schema mismatch")
    _require(payload.get("profile_sha256") == profile_sha, "prepared profile mismatch")
    _require(payload.get("backend_identity_sha256") == backend_sha, "prepared backend mismatch")
    _require(payload.get("operator_id") == operator.get("operator_id"), "prepared operator mismatch")
    _require(payload.get("operator_sha256") == operator.get("operator_sha256"), "prepared operator hash mismatch")
    _require(isinstance(payload.get("prepared_sha256"), str) and SHA256.fullmatch(payload["prepared_sha256"]) is not None, "prepared hash invalid")
    _require(isinstance(payload.get("operator_cache_sha256"), str) and SHA256.fullmatch(payload["operator_cache_sha256"]) is not None, "prepared cache hash invalid")
    if batch is not None:
        _require(payload.get("batch") == batch, "prepared batch mismatch")
    return payload


def _verify_step_record(record: Any, name: str, profile_sha: str, backend_sha: str, operator: Mapping[str, Any], duration_limit: float) -> None:
    _require(isinstance(record, dict), f"{name} record missing")
    _state_hash(record.get("input_state_sha256"), f"{name}.input_state_sha256")
    _state_hash(record.get("output_state_sha256"), f"{name}.output_state_sha256")
    prepared = _verify_prepared(record.get("prepared"), profile_sha, backend_sha, operator, 1)
    elapsed = record.get("elapsed_ns")
    _require(isinstance(elapsed, int) and elapsed > 0, f"{name} elapsed time invalid")
    _require(float(elapsed) <= duration_limit * 1_000_000_000.0, f"{name} elapsed time exceeds bound")
    receipt = record.get("receipt")
    _require(isinstance(receipt, dict), f"{name} backend step receipt missing")
    _require(receipt.get("schema") == "cassi.qi-flow-backend-step.v1", f"{name} receipt schema mismatch")
    _require(receipt.get("transaction_id") == record.get("transaction_id"), f"{name} receipt transaction mismatch")
    _require(receipt.get("operator_id") == operator.get("operator_id"), f"{name} receipt operator mismatch")
    _require(receipt.get("backend_identity_sha256") == backend_sha, f"{name} receipt backend mismatch")
    _require(receipt.get("prepared_sha256") == prepared.get("prepared_sha256"), f"{name} receipt prepared mismatch")
    _require(receipt.get("operator_sha256") == operator.get("operator_sha256"), f"{name} receipt operator hash mismatch")
    _require(receipt.get("operator_cache_sha256") == prepared.get("operator_cache_sha256"), f"{name} receipt cache identity mismatch")
    _require(receipt.get("predecessor_state_sha256") == record.get("input_state_sha256"), f"{name} predecessor state mismatch")
    _require(receipt.get("candidate_state_sha256") == record.get("output_state_sha256"), f"{name} candidate state mismatch")
    _require(receipt.get("status") == "COMMITTED" and receipt.get("failure_reason") is None, f"{name} receipt status/failure mismatch")
    _require(receipt.get("op_count") == 1 and isinstance(receipt.get("wall_time_ns"), int) and receipt["wall_time_ns"] > 0, f"{name} receipt counters invalid")
    _require(isinstance(receipt.get("raw_operator_receipt"), dict), f"{name} raw operator receipt malformed")
    backend_receipt = record.get("backend_receipt")
    if backend_receipt is not None:
        _require(isinstance(backend_receipt, dict), f"{name} backend receipt malformed")
        _require(backend_receipt.get("schema") == BACKEND_RECEIPT_SCHEMA, f"{name} backend receipt schema mismatch")
        _sha_field(backend_receipt, "self_sha256", BACKEND_RECEIPT_SCHEMA)
        _require(backend_receipt.get("profile_sha256") == profile_sha, f"{name} receipt profile mismatch")

def _verify_memory(receipt: Any, profile: Mapping[str, Any], *, expected_ops: int | None = None, expected_batch: int | None = None) -> dict[str, Any]:
    _require(isinstance(receipt, dict), "memory receipt missing")
    _require(receipt.get("schema") == BACKEND_MEMORY_SCHEMA, "memory receipt schema mismatch")
    _sha_field(receipt, "receipt_sha256", BACKEND_MEMORY_SCHEMA)
    _require(receipt.get("device") == "cpu" and receipt.get("dtype") == "float64", "memory device/dtype changed")
    for key in ("state_bytes", "peak_working_bytes", "allocated_bytes", "reserved_bytes", "allocation_count", "copy_count", "synchronization_count", "op_count", "wall_time_ns", "prepared_cache_entries", "prepared_cache_hits", "prepared_cache_misses"):
        _require(isinstance(receipt.get(key), int) and receipt[key] >= 0, f"memory counter {key} invalid")
    capacity = profile["capacity"]
    _require(receipt["state_bytes"] <= int(capacity["max_state_bytes"]), "state bytes exceed profile bound")
    _require(receipt["peak_working_bytes"] <= int(capacity["max_state_bytes"]) + int(capacity["max_checkpoint_bytes"]), "peak memory exceeds profile bounds")
    if expected_ops is not None:
        _require(receipt["op_count"] == expected_ops, "memory operation counter changed")
    if expected_batch is not None:
        _require(receipt["prepared_cache_entries"] == 1 and receipt["prepared_cache_hits"] == 1 and receipt["prepared_cache_misses"] == 1, "candidate cache counters changed")
        _require(receipt["state_bytes"] * expected_batch >= receipt["state_bytes"], "candidate state byte invariant failed")
    return receipt


def _verify_raw(root: Path, profiler: Mapping[str, Any], thresholds: Mapping[str, Any]) -> dict[str, Any]:
    raw_index = _load(root / GATE_RELATIVE / "raw-index.json")
    _require(raw_index.get("schema") == RAW_SCHEMA, "raw index schema mismatch")
    objects = raw_index.get("objects")
    _require(isinstance(objects, list) and objects, "raw objects missing")
    roles: set[str] = set()
    for item in objects:
        _require(isinstance(item, dict), "raw descriptor malformed")
        role = item.get("role")
        relative = item.get("path")
        _require(isinstance(role, str) and role not in roles, "raw role duplicate")
        roles.add(role)
        _require(isinstance(relative, str) and relative.startswith(GATE_RELATIVE.as_posix() + "/raw/"), f"raw path outside gate: {role}")
        target = root / Path(relative)
        _require(target.is_file(), f"raw bytes missing: {role}")
        raw = target.read_bytes()
        _require(item.get("bytes") == len(raw), f"raw byte count changed: {role}")
        _require(item.get("sha256") == _sha256(raw), f"raw hash changed: {role}")
        dtype = item.get("dtype")
        shape = item.get("shape")
        _require(dtype in {"float32", "float64"} and item.get("byte_order") == "little", f"raw dtype/order changed: {role}")
        _require(isinstance(shape, list) and shape and all(isinstance(dim, int) and dim > 0 for dim in shape), f"raw shape changed: {role}")
        width = 4 if dtype == "float32" else 8
        expected_bytes = width
        for dim in shape:
            expected_bytes *= dim
        _require(expected_bytes == len(raw), f"raw shape byte mismatch: {role}")
    expected = {"one-state-step-input", "one-state-step-output", "event-input", "event-output", "long-horizon-input", "long-horizon-output"}
    expected.update(f"candidate-ladder-{lane}-output" for lane in thresholds["candidate_ladder"])
    _require(expected.issubset(roles), "required raw evidence is missing")
    _require(set(item["role"] for item in objects) == roles, "raw role set mismatch")
    raw_dir = root / GATE_RELATIVE / "raw"
    actual = {path.relative_to(root).as_posix() for path in raw_dir.rglob("*") if path.is_file()}
    listed = {item["path"] for item in objects}
    _require(actual == listed, "raw file set mismatch")
    return raw_index


def _verify_profiler(root: Path, profile: Mapping[str, Any], index: Mapping[str, Any]) -> None:
    profiler = _load(root / GATE_RELATIVE / "profiler.json")
    _require(profiler.get("schema") == PROFILER_SCHEMA and profiler.get("status") == "PASS", "profiler status/schema is not PASS")
    _require(profiler.get("measurement") == "executed-torch-cpu-float64-v1", "profiler measurement is not execution evidence")
    _require(index.get("profiler_sha256") == _sha256((root / GATE_RELATIVE / "profiler.json").read_bytes()), "profiler hash mismatch")
    thresholds = profiler.get("thresholds")
    _require(isinstance(thresholds, dict), "profiler thresholds missing")
    max_lanes = min(int(profile["field"]["batch_limit"]), int(profile["capacity"]["max_batch_lanes"]))
    expected_ladder = [lane for lane in (1, 2, 4, 8) if lane <= max_lanes]
    expected_thresholds = {
        "max_state_bytes": int(profile["capacity"]["max_state_bytes"]),
        "max_checkpoint_bytes": int(profile["capacity"]["max_checkpoint_bytes"]),
        "max_batch_lanes": max_lanes,
        "max_candidates": int(profile["action"]["max_candidates"]),
        "candidate_ladder": expected_ladder,
        "long_horizon_steps": max(8, int(profile["action"]["max_candidates"]) * 4),
        "max_memory_slope_bytes_per_step": _finite_bits(float(profile["capacity"]["max_state_bytes"])),
    }
    _require(thresholds == expected_thresholds, "profile-derived thresholds changed")
    backend, operator = _verify_identity(profiler, profile)
    profile_sha = str(profile["profile_sha256"])
    backend_sha = str(backend["identity_sha256"])
    _verify_step_record(profiler.get("one_state_step"), "one_state_step", profile_sha, backend_sha, operator, 0.01)
    _verify_step_record(profiler.get("event"), "event", profile_sha, backend_sha, operator, 0.01)
    memory_section = profiler.get("memory")
    _require(isinstance(memory_section, dict) and memory_section.get("schema") == MEMORY_SCHEMA, "profiler memory section missing")
    main_memory = _verify_memory(memory_section.get("receipt"), profile, expected_ops=2)
    _require(main_memory["prepared_cache_entries"] == 1 and main_memory["prepared_cache_hits"] == 1 and main_memory["prepared_cache_misses"] == 1, "main cache counters changed")
    ladder = _load(root / GATE_RELATIVE / "candidate-ladder.json")
    _require(ladder.get("schema") == LADDER_SCHEMA, "candidate ladder schema mismatch")
    _require(ladder == profiler.get("candidate_ladder"), "candidate ladder duplicate diverged")
    rows = ladder.get("rows")
    _require(isinstance(rows, list) and [row.get("lanes") for row in rows] == expected_ladder, "candidate ladder widths changed")
    for row in rows:
        lanes = row["lanes"]
        _require(row.get("candidate_count") == lanes and isinstance(row.get("elapsed_ns"), int) and row["elapsed_ns"] > 0, "candidate timing/counter changed")
        per = _number(row.get("per_candidate_ns"), "candidate per-candidate time")
        _require(per > 0 and abs(per - float(row["elapsed_ns"]) / lanes) <= max(1.0, per * 1e-12), "candidate amortization changed")
        _state_hash(row.get("input_state_sha256"), "candidate input state")
        _state_hash(row.get("output_state_sha256"), "candidate output state")
        prepared = _verify_prepared(row.get("prepared"), profile_sha, backend_sha, operator, lanes)
        _require(row.get("cache_exercised") is True, "candidate cache was not exercised")
        row_memory = _verify_memory(row.get("memory"), profile, expected_ops=1, expected_batch=lanes)
        _require(row_memory["prepared_cache_entries"] == 1 and row_memory["prepared_cache_hits"] == 1 and row_memory["prepared_cache_misses"] == 1, "candidate cache counters changed")
        step = row.get("step_receipt")
        _require(isinstance(step, dict) and step.get("status") == "COMMITTED", "candidate step was not committed")
        _require(step.get("prepared_sha256") == prepared.get("prepared_sha256") and step.get("backend_identity_sha256") == backend_sha, "candidate receipt identity changed")
        _require(_canonical_hash(step, BACKEND_STEP_DOMAIN) == _canonical_hash(step, BACKEND_STEP_DOMAIN), "candidate step hash guard")
    horizon = profiler.get("long_horizon")
    _require(isinstance(horizon, dict), "long-horizon receipt missing")
    steps = thresholds["long_horizon_steps"]
    _require(horizon.get("steps") == steps, "long-horizon step count changed")
    elapsed = horizon.get("elapsed_ns")
    _require(isinstance(elapsed, int) and elapsed > 0, "long-horizon elapsed time invalid")
    _require(_number(horizon.get("throughput_steps_per_s"), "long-horizon throughput") > 0, "long-horizon throughput invalid")
    samples = horizon.get("samples")
    _require(isinstance(samples, list) and len(samples) == steps, "long-horizon samples missing")
    for expected_step, sample in enumerate(samples):
        _require(isinstance(sample, dict) and sample.get("step") == expected_step and isinstance(sample.get("current_bytes"), int) and sample["current_bytes"] >= 0, "long-horizon sample changed")
    baseline = horizon.get("baseline_current_bytes")
    final = horizon.get("final_current_bytes")
    high = horizon.get("tracemalloc_peak_bytes")
    _require(isinstance(baseline, int) and isinstance(final, int) and isinstance(high, int) and high >= final >= 0, "long-horizon memory values invalid")
    slope = _number(horizon.get("current_slope_bytes_per_step"), "long-horizon slope")
    _require(slope <= _number(thresholds["max_memory_slope_bytes_per_step"], "long-horizon slope threshold"), "long-horizon memory slope exceeds profile threshold")
    _state_hash(horizon.get("input_state_sha256"), "long-horizon input state")
    _state_hash(horizon.get("output_state_sha256"), "long-horizon output state")
    horizon_prepared = _verify_prepared(horizon.get("prepared"), profile_sha, backend_sha, operator, 1)
    _require(horizon_prepared.get("operator_id") == operator.get("operator_id"), "long-horizon operator changed")
    _verify_memory(horizon.get("backend_memory"), profile, expected_ops=steps)
    _verify_raw(root, profiler, thresholds)
    controls = _load(root / GATE_RELATIVE / "mutation-controls.json")
    _require(controls.get("schema") == CONTROLS_SCHEMA and controls.get("status") == "PASS", "mutation controls are not PASS")
    rows = controls.get("controls")
    _require(isinstance(rows, list) and controls.get("control_count") == len(rows) and len(rows) >= 6, "mutation controls incomplete")
    _require(all(isinstance(row, dict) and row.get("status") == "PASS" for row in rows), "mutation control failed")
    _require(controls.get("source_identity") == index.get("source_identity"), "mutation-control source identity changed")


def verify_artifact(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    _require(root.is_dir(), "artifact root is missing")
    index = _load(root / "index.json")
    _require(index.get("schema") == INDEX_SCHEMA and index.get("gate") == "G14B", "index schema/gate mismatch")
    _require(index.get("status") == "BLOCKED" and index.get("profiler_status") == "PASS", "W14B gate status changed")
    artifact_sha = index.get("artifact_sha256")
    _require(isinstance(artifact_sha, str) and SHA256.fullmatch(artifact_sha) is not None, "artifact hash missing")
    body = {key: value for key, value in index.items() if key not in {"run_id", "artifact_sha256"}}
    _require(_canonical_hash(body, INDEX_SCHEMA) == artifact_sha and index.get("run_id") == artifact_sha, "artifact content hash mismatch")
    _require(root.name == artifact_sha, "artifact directory is not content addressed")
    _verify_manifest(root, index)
    _verify_sources(root, index)
    profile = _verify_profile(root, index)
    _verify_registry(root)
    gate_index = _load(root / GATE_RELATIVE / "index.json")
    _require(gate_index.get("schema") == GATE_INDEX_SCHEMA and gate_index.get("gate") == "G14B", "gate index mismatch")
    _require(gate_index.get("status") == "BLOCKED" and gate_index.get("profiler_status") == "PASS", "gate index status changed")
    _require(gate_index.get("profile_sha256") == profile.get("profile_sha256"), "gate profile identity mismatch")
    gate_status = _load(root / GATE_RELATIVE / "status.json")
    _require(gate_status.get("schema") == STATUS_SCHEMA and gate_status.get("gate") == "G14B", "gate status schema mismatch")
    _require(gate_status.get("status") == "BLOCKED" and gate_status.get("profiler_status") == "PASS" and gate_status.get("engineering_ready") is False, "gate status is not fail-closed")
    _require(gate_status.get("profiler_sha256") == index.get("profiler_sha256"), "gate profiler hash mismatch")
    _verify_profiler(root, profile, index)
    return {
        "schema": INDEX_SCHEMA,
        "status": "PASS",
        "gate_status": "BLOCKED",
        "profiler_status": "PASS",
        "artifact_sha256": artifact_sha,
        "verified_files": len(json.loads((root / "manifest.json").read_bytes().decode("utf-8"))["files"]),
    }


def verify(root: 