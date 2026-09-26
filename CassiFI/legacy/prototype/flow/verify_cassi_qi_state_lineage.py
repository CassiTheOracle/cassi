"""Independently verify G12L state-lineage receipts and gate artifacts.

This verifier intentionally does not import the runtime profile, field, or
lineage implementation.  It recomputes the canonical codec hash and checks
only the sealed receipt/proof contract, so a runtime self-assertion cannot
serve as its own witness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any, Mapping


LINEAGE_RECEIPT_SCHEMA = "cassi.qi-flow-state-lineage-fork-receipt.v1"
LINEAGE_PROOF_SCHEMA = "cassi.qi-flow-state-lineage-compatibility-proof.v1"
LINEAGE_ARTIFACT_SCHEMA = "cassi.qi-flow-g12l-state-lineage.v1"
LINEAGE_RUN_SCHEMA = "cassi.qi-flow-g12l-state-lineage-run.v1"
MAX_SAFE_INTEGER = 9_007_199_254_740_991
STATE_CONSUMING_ORDER = (
    "state_contract_sha256",
    "boundary_action_sha256",
    "backend_capacity_sha256",
)


class LineageVerificationError(ValueError):
    """Raised when a lineage receipt or artifact fails closed."""


def _quote(value: str) -> str:
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise LineageVerificationError("surrogate in canonical string")
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


def _normalise(value: Any) -> Any:
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise LineageVerificationError("integer exceeds canonical range")
        return value
    if type(value) is float:
        if not math.isfinite(value) or (value == 0.0 and math.copysign(1.0, value) < 0.0):
            raise LineageVerificationError("invalid canonical float")
        return "f64:" + struct.pack(">d", value).hex()
    if type(value) is str:
        if value.startswith(("f32:", "f64:")):
            # Receipt values are identifiers, not float tags.  Reject malformed
            # tags while preserving ordinary strings beginning with another text.
            prefix, encoded = value[:4], value[4:]
            width = 16 if prefix == "f64:" else 8
            if len(encoded) != width or encoded.lower() != encoded:
                raise LineageVerificationError("invalid finite-bit tag")
            try:
                number = struct.unpack(">d" if prefix == "f64:" else ">f", bytes.fromhex(encoded))[0]
            except (ValueError, struct.error) as exc:
                raise LineageVerificationError("invalid finite-bit tag") from exc
            if not math.isfinite(number) or (number == 0.0 and math.copysign(1.0, number) < 0.0):
                raise LineageVerificationError("invalid finite-bit tag")
        return value
    if type(value) is list:
        return [_normalise(item) for item in value]
    if type(value) is dict:
        result: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str or key in result:
                raise LineageVerificationError("invalid canonical object key")
            result[key] = _normalise(item)
        return result
    raise LineageVerificationError(f"unsupported canonical value: {type(value).__name__}")


def _encode(value: Any) -> str:
    value = _normalise(value)
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if type(value) is int:
        return str(value)
    if type(value) is str:
        return _quote(value)
    if type(value) is list:
        return "[" + ",".join(_encode(item) for item in value) + "]"
    if type(value) is dict:
        return "{" + ",".join(
            _quote(key) + ":" + _encode(value[key])
            for key in sorted(value, key=lambda item: item.encode("utf-8"))
        ) + "}"
    raise LineageVerificationError("unsupported canonical value")


def canonical_json_bytes(value: Any) -> bytes:
    return _encode(value).encode("utf-8", "strict")


def canonical_hash(value: Any, domain: str) -> str:
    domain_bytes = domain.encode("utf-8", "strict")
    payload = canonical_json_bytes(value)
    framed = len(domain_bytes).to_bytes(8, "big") + domain_bytes + len(payload).to_bytes(8, "big") + payload
    return hashlib.sha256(framed).hexdigest()
def _hashlib_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()



def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LineageVerificationError(message)


def _hash(value: Any, name: str) -> str:
    _require(type(value) is str and len(value) == 64, f"{name} is not SHA-256")
    _require(value == value.lower(), f"{name} is not lowercase SHA-256")
    try:
        int(value, 16)
    except ValueError as exc:
        raise LineageVerificationError(f"{name} is not SHA-256") from exc
    return value


def _text(value: Any, name: str, maximum: int = 256) -> str:
    _require(type(value) is str and 0 < len(value) <= maximum, f"{name} is invalid")
    return value


def _checkpoint_identity(receipt: Mapping[str, Any]) -> str:
    return canonical_hash(
        {
            "state_contract_sha256": receipt["parent_state_contract_sha256"],
            "state_object_sha256": receipt["parent_state_object_sha256"],
            "state_byte_count": receipt["parent_state_byte_count"],
        },
        "cassi.qi-flow-state-lineage-checkpoint.v1",
    )


def _proof_for(receipt: Mapping[str, Any]) -> dict[str, Any]:
    rows = receipt["state_consuming_subhashes"]
    differences = receipt["differing_profile_leaves"]
    identity_fields = (
        "layout_identity_sha256",
        "operator_identity_sha256",
        "schema_identity_sha256",
        "backend_identity_sha256",
        "source_profile_identity_sha256",
    )
    return {
        "schema": LINEAGE_PROOF_SCHEMA,
        "state_contract_sha256": {
            "parent": receipt["parent_state_contract_sha256"],
            "child": receipt["child_state_contract_sha256"],
            "equal": receipt["parent_state_contract_sha256"] == receipt["child_state_contract_sha256"],
        },
        "state_consuming_subhashes": rows,
        **{
            name: {"parent": receipt[name], "child": receipt[name], "equal": True}
            for name in identity_fields
        },
        "checkpoint": {
            "parent_state_object_sha256": receipt["parent_state_object_sha256"],
            "child_state_object_sha256": receipt["child_state_object_sha256"],
            "parent_state_byte_count": receipt["parent_state_byte_count"],
            "child_state_byte_count": receipt["child_state_byte_count"],
            "exact_bytes": receipt["parent_state_object_sha256"] == receipt["child_state_object_sha256"]
            and receipt["parent_state_byte_count"] == receipt["child_state_byte_count"],
            "checkpoint_identity_sha256": receipt["checkpoint_identity_sha256"],
        },
        "differing_profile_leaves": differences,
        "profile_sha256_differs": receipt["parent_profile_sha256"] != receipt["new_profile_sha256"],
        "fresh_session_identity": receipt["parent_session_id"] != receipt["new_session_id"],
        "fresh_source_identity": receipt["old_source_identity_sha256"] != receipt["new_source_identity_sha256"],
        "fresh_clock_identity": receipt["old_clock_sha256"] != receipt["new_clock_sha256"],
        "fresh_protocol_epoch": True,
        "fresh_world_identity": True,
        "fresh_episode_identity": True,
    }


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one receipt without importing the runtime implementation."""

    _require(type(receipt) is dict, "receipt must be an object")
    required = {
        "schema",
        "receipt_id",
        "parent_session_id",
        "new_session_id",
        "parent_head_sha256",
        "parent_profile_sha256",
        "new_profile_sha256",
        "state_consuming_subhashes",
        "differing_profile_leaves",
        "parent_state_object_sha256",
        "child_state_object_sha256",
        "parent_state_byte_count",
        "child_state_byte_count",
        "parent_state_contract_sha256",
        "child_state_contract_sha256",
        "old_source_identity_sha256",
        "new_source_identity_sha256",
        "old_clock_sha256",
        "new_clock_sha256",
        "new_protocol_epoch_sha256",
        "new_world_id",
        "new_episode_id",
        "reset_reason",
        "operator_id",
        "creation_timestamp_ns_telemetry",
        "copied_state_exact",
        "continuity_reused",
        "parent_lineage_status",
        "logical_tick",
        "cycle_number",
        "new_protocol_epoch",
        "operator_identity_sha256",
        "layout_identity_sha256",
        "schema_identity_sha256",
        "backend_identity_sha256",
        "source_profile_identity_sha256",
        "checkpoint_identity_sha256",
        "exact_state_object_copy",
        "copied_protocol_or_world_continuity",
        "compatibility_proof",
        "self_sha256",
    }
    _require(set(receipt) == required, "receipt key set is invalid")
    _require(receipt["schema"] == LINEAGE_RECEIPT_SCHEMA, "receipt schema mismatch")
    for name in (
        "parent_session_id", "new_session_id", "new_world_id", "new_episode_id", "operator_id",
        "new_protocol_epoch", "old_source_identity_sha256", "new_source_identity_sha256",
        "old_clock_sha256", "new_clock_sha256",
    ):
        _text(receipt[name], name)
    for name in (
        "receipt_id", "parent_profile_sha256", "new_profile_sha256", "parent_state_object_sha256",
        "child_state_object_sha256", "parent_state_contract_sha256", "child_state_contract_sha256",
        "old_source_identity_sha256", "new_source_identity_sha256", "old_clock_sha256",
        "new_clock_sha256", "new_protocol_epoch_sha256", "layout_identity_sha256",
        "operator_identity_sha256", "schema_identity_sha256", "backend_identity_sha256",
        "source_profile_identity_sha256", "checkpoint_identity_sha256", "self_sha256",
    ):
        _hash(receipt[name], name)
    _hash(receipt["parent_head_sha256"], "parent_head_sha256")
    _require(type(receipt["reset_reason"]) is str and len(receipt["reset_reason"]) <= 512, "reset_reason is invalid")
    for name in ("parent_state_byte_count", "child_state_byte_count", "creation_timestamp_ns_telemetry", "logical_tick", "cycle_number"):
        _require(type(receipt[name]) is int and 0 <= receipt[name] <= MAX_SAFE_INTEGER, f"{name} is invalid")
    _require(receipt["parent_lineage_status"] in {"open", "indeterminate_sealed"}, "parent lineage status is invalid")
    _require(receipt["copied_state_exact"] is True and receipt["exact_state_object_copy"] is True, "state copy is not exact")
    _require(receipt["continuity_reused"] is False and receipt["copied_protocol_or_world_continuity"] is False, "continuity was copied")
    _require(receipt["parent_session_id"] != receipt["new_session_id"], "session identity was reused")
    _require(receipt["parent_profile_sha256"] != receipt["new_profile_sha256"], "complete profile identity did not change")
    _require(receipt["parent_state_contract_sha256"] == receipt["child_state_contract_sha256"], "state contract changed")
    _require(receipt["parent_state_object_sha256"] == receipt["child_state_object_sha256"], "state checkpoint hash changed")
    _require(receipt["parent_state_byte_count"] == receipt["child_state_byte_count"], "state checkpoint size changed")
    _require(receipt["old_source_identity_sha256"] != receipt["new_source_identity_sha256"], "source identity was reused")
    _require(receipt["old_clock_sha256"] != receipt["new_clock_sha256"], "clock identity was reused")
    _require(receipt["new_protocol_epoch_sha256"] == hashlib.sha256(receipt["new_protocol_epoch"].encode("utf-8")).hexdigest(), "protocol identity mismatch")
    rows = receipt["state_consuming_subhashes"]
    _require(type(rows) is list and len(rows) == len(STATE_CONSUMING_ORDER), "state-consuming vector cardinality mismatch")
    names = []
    for row in rows:
        _require(type(row) is dict and set(row) == {"name", "parent_sha256", "child_sha256"}, "state-consuming row is invalid")
        _text(row["name"], "state-consuming name")
        _hash(row["parent_sha256"], "state-consuming parent hash")
        _hash(row["child_sha256"], "state-consuming child hash")
        _require(row["parent_sha256"] == row["child_sha256"], "state-consuming hash changed")
        names.append(row["name"])
    _require(tuple(names) == STATE_CONSUMING_ORDER, "state-consuming registry order changed")
    differences = receipt["differing_profile_leaves"]
    _require(type(differences) is list, "profile difference projection is invalid")
    for row in differences:
        _require(type(row) is dict and set(row) == {"json_pointer", "old", "new"}, "profile difference row is invalid")
        _require(type(row["json_pointer"]) is str and row["json_pointer"].startswith("/"), "profile difference pointer is invalid")
        _require(row["old"] != row["new"], "profile difference row is not a difference")
    _require(receipt["checkpoint_identity_sha256"] == _checkpoint_identity(receipt), "checkpoint identity mismatch")
    _require(receipt["compatibility_proof"] == _proof_for(receipt), "compatibility proof mismatch")
    material = {key: value for key, value in receipt.items() if key not in {"receipt_id", "self_sha256"}}
    _require(receipt["receipt_id"] == canonical_hash(material, LINEAGE_RECEIPT_SCHEMA + ".receipt-id"), "receipt id mismatch")
    without_self = dict(receipt)
    without_self.pop("self_sha256")
    _require(receipt["self_sha256"] == canonical_hash(without_self, LINEAGE_RECEIPT_SCHEMA), "receipt self hash mismatch")
    return {
        "status": "PASS_G12L_RECEIPT",
        "receipt_id": receipt["receipt_id"],
        "self_sha256": receipt["self_sha256"],
    }


def verify_artifact(path_or_payload: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    """Verify a runner directory or a decoded lineage artifact."""

    root: Path | None = None
    if isinstance(path_or_payload, (str, Path)):
        root = Path(path_or_payload)
        if root.is_dir():
            candidate = root / "gates" / "g12l-state-lineage" / "lineage.json"
            if not candidate.exists():
                candidate = root / "lineage.json"
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        else:
            payload = json.loads(root.read_text(encoding="utf-8"))
    else:
        payload = dict(path_or_payload)
    _require(type(payload) is dict, "lineage artifact must be an object")
    required = {
        "schema", "run_id", "parent_session_id", "new_session_id", "parent_head_sha256",
        "receipt", "profile_difference_projection", "compatibility_proof", "mutation_controls",
        "status", "self_sha256",
    }
    _require(set(payload) == required, "lineage artifact key set is invalid")
    _require(payload["schema"] == LINEAGE_ARTIFACT_SCHEMA, "lineage artifact schema mismatch")
    receipt = payload["receipt"]
    receipt_result = verify_receipt(receipt)
    _require(payload["parent_session_id"] == receipt["parent_session_id"], "parent session linkage mismatch")
    _require(payload["new_session_id"] == receipt["new_session_id"], "new session linkage mismatch")
    _require(payload["parent_head_sha256"] == receipt["parent_head_sha256"], "parent head linkage mismatch")
    _require(payload["profile_difference_projection"] == receipt["differing_profile_leaves"], "profile projection mismatch")
    _require(payload["compatibility_proof"] == receipt["compatibility_proof"], "artifact proof mismatch")
    _require(payload["status"] == "PASS", "lineage artifact is not passing")
    controls = payload["mutation_controls"]
    _require(type(controls) is list and controls, "mutation controls are missing")
    for control in controls:
        _require(
            type(control) is dict
            and set(control) == {"control_id", "mutation", "expected", "observed"}
            and control["expected"] == "REJECT"
            and control["observed"] == "REJECT",
            "mutation control did not reject",
        )
    without_self = dict(payload)
    without_self.pop("self_sha256")
    _require(payload["self_sha256"] == canonical_hash(without_self, LINEAGE_ARTIFACT_SCHEMA), "lineage artifact self hash mismatch")
    without_run_id = {key: value for key, value in without_self.items() if key != "run_id"}
    _require(payload["run_id"] == canonical_hash(without_run_id, LINEAGE_RUN_SCHEMA + ".id"), "run id is not content-addressed")
    if root is not None and root.is_dir():
        gate = root / "gates" / "g12l-state-lineage"
        parent_state_path = gate / "state" / "parent-state.bin"
        child_state_path = gate / "state" / "child-state.bin"
        _require(parent_state_path.is_file() and child_state_path.is_file(), "exact state artifacts are missing")
        parent_state = parent_state_path.read_bytes()
        child_state = child_state_path.read_bytes()
        _require(parent_state == child_state, "state artifact bytes differ")
        _require(_hashlib_sha256(parent_state) == receipt["parent_state_object_sha256"], "parent state artifact hash mismatch")
        _require(_hashlib_sha256(child_state) == receipt["child_state_object_sha256"], "child state artifact hash mismatch")
        _require(len(parent_state) == receipt["parent_state_byte_count"], "parent state artifact size mismatch")
        _require(len(child_state) == receipt["child_state_byte_count"], "child state artifact size mismatch")
        status_path = gate / "status.json"
        _require(status_path.is_file(), "status.json is missing")
        status = json.loads(status_path.read_text(encoding="utf-8"))
        _require(
            type(status) is dict
            and status.get("schema") == "cassi.qi-flow-g12l-state-lineage-status.v1"
            and status.get("status") == "PASS"
            and status.get("lineage_sha256") == payload["self_sha256"]
            and status.get("receipt_sha256") == receipt["self_sha256"],
            "status.json is not passing",
        )
        index_path = root / "index.json"
        _require(index_path.is_file(), "content-addressed index is missing")
        index = json.loads(index_path.read_text(encoding="utf-8"))
        _require(type(index) is dict and index.get("schema") == LINEAGE_RUN_SCHEMA, "run index schema mismatch")
        _require(index.get("run_id") == payload["run_id"], "run index identity mismatch")
        _require(index.get("status") == "PASS", "run index is not passing")
        _require(index.get("lineage_sha256") == payload["self_sha256"], "run index lineage mismatch")
        index_self = index.get("self_sha256")
        _hash(index_self, "run index self hash")
        index_without_self = dict(index)
        index_without_self.pop("self_sha256")
        _require(index_self == canonical_hash(index_without_self, LINEAGE_RUN_SCHEMA), "run index self hash mismatch")
    return {
        "status": "PASS_G12L",
        "run_id": payload["run_id"],
        "lineage_sha256": payload["self_sha256"],
        "receipt": receipt_result,
        "mutation_control_count": len(controls),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = verify_artifact(args.artifact)
    if args.json:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    else:
        print(f"PASS_G12L {result['run_id']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LineageVerificationError, OSError, json.JSONDecodeError) as exc:
        print(f"FAIL_G12L {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
