"""Independent verifier for the opt-in materialized composition receipt."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "cassifi.temporal-materialized-composition.v1"
TIMING_KEYS = frozenset({"runtime_seconds", "elapsed_seconds", "content_digest", "receipt_digest", "self_check"})

def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

def strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): strip_timing(v) for k, v in value.items() if str(k) not in TIMING_KEYS}
    if isinstance(value, list):
        return [strip_timing(v) for v in value]
    return value

def digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(strip_timing(value)).encode()).hexdigest()

def steps(source: Mapping[str, Any]) -> list[dict[str, str]] | None:
    try:
        raw = base64.b64decode(source["content_base64"], validate=True)
        data = json.loads(raw.decode())
        result = data["steps"]
        if data.get("schema") != "cassifi.temporal-episode.v1" or not isinstance(result, list):
            return None
        return [dict(item) for item in result]
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None

def verify(receipt: Mapping[str, Any]) -> dict[str, Any]:
    rows = receipt.get("rows")
    success = rows[0] if isinstance(rows, list) and len(rows) == 2 else {}
    denied = rows[1] if isinstance(rows, list) and len(rows) == 2 else {}
    training = success.get("training", {}) if isinstance(success, Mapping) else {}
    learning = training.get("learning", []) if isinstance(training, Mapping) else []
    decoded = [steps(item.get("source", {})) for item in learning if isinstance(item, Mapping)]
    edge_absent = len(decoded) == 2 and all(item is not None and len(item) == 1 for item in decoded) and {tuple(item[0].get(k) for k in ("action", "observation")) for item in decoded if item} == {("left-step", "left-goal"), ("right-step", "right-goal")}
    pre = success.get("precommit", {}) if isinstance(success, Mapping) else {}
    prediction = pre.get("prediction", {}) if isinstance(pre, Mapping) else {}
    support = prediction.get("support", {}) if isinstance(prediction, Mapping) else {}
    material = success.get("materialization", {}) if isinstance(success, Mapping) else {}
    checks = {
        "schema": receipt.get("schema") == SCHEMA,
        "content_digest": receipt.get("content_digest") == digest(receipt),
        "receipt_digest": receipt.get("receipt_digest") == digest(receipt),
        "self_check": receipt.get("self_check") is True,
        "held_out_sources": edge_absent,
        "precommit_missing_edge": prediction.get("supported") is False and support.get("exposure") == 0 and support.get("missing_states") == [1],
        "derived_not_canonical": success.get("proposal", {}).get("canonical_support") is False and success.get("proposal", {}).get("evidence_class") == "derived-hypothesis",
        "canonical_commit": material.get("support_origin") == "state-conditioned-materialization" and material.get("evidence_class") == "canonical-materialized-support" and material.get("supported") is True,
        "digest_changed": material.get("previous_state_sha256") != material.get("state_sha256") and success.get("precommit", {}).get("state_sha256") != material.get("state_sha256"),
        "observed_not_training": material.get("observed_outcome") is True and material.get("training_source_admitted") is False,
        "mismatch_denied": denied.get("status") == "DENIED",
        "replay_denied": isinstance(success.get("replay_denied"), str) and bool(success.get("replay_denied")),
        "replay_unchanged": success.get("after", {}).get("state_sha256") == material.get("state_sha256") and success.get("after", {}).get("memory_sha256") == material.get("memory_sha256"),
    }
    return {"schema": SCHEMA, "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "receipt_digest": receipt.get("receipt_digest")}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    result = verify(receipt)
    print(json.dumps(result, sort_keys=True))
    if result["status"] != "PASS":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
