"""Independent standard-library verifier for temporal composition probe receipts."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA = "cassifi.temporal-composition-probe.v1"
TIMING_KEYS = frozenset({"runtime_seconds", "elapsed_seconds", "content_digest", "receipt_digest", "self_check"})
EXPECTED_PUBLIC_PATH = ["configure_temporal", "learn_temporal", "condense_temporal_skill", "bind_temporal", "compose_temporal_task", "propose_temporal_task", "acknowledge_temporal_task"]
EXPECTED_ORDER = [
    {"action": "left-step", "observation": "left-goal"},
    {"action": "right-step", "observation": "right-goal"},
]
EXPECTED_TASK_STEPS = [
    {"memory_id": "primitive-memory", "participant_id": "agent", "skill_id": "left-skill"},
    {"memory_id": "primitive-memory", "participant_id": "agent", "skill_id": "right-skill"},
]


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): strip_timing(item) for key, item in value.items() if str(key) not in TIMING_KEYS}
    if isinstance(value, list):
        return [strip_timing(item) for item in value]
    return value


def digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(strip_timing(value)).encode("utf-8")).hexdigest()


def source_bytes(source: Mapping[str, Any]) -> bytes | None:
    value = source.get("content_base64")
    if not isinstance(value, str):
        return None
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        return None


def source_steps(source: Mapping[str, Any]) -> list[dict[str, str]] | None:
    raw = source_bytes(source)
    if raw is None:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping) or payload.get("schema") != "cassifi.temporal-episode.v1":
        return None
    steps = payload.get("steps")
    if not isinstance(steps, list) or any(not isinstance(step, Mapping) or set(step) != {"action", "observation"} for step in steps):
        return None
    return [dict(step) for step in steps]


def contains_ordered(steps: Sequence[Mapping[str, str]], ordered: Sequence[Mapping[str, str]]) -> bool:
    if len(steps) < len(ordered):
        return False
    return any(list(steps[index:index + len(ordered)]) == list(ordered)
               for index in range(len(steps) - len(ordered) + 1))


def row_receipt(row: Mapping[str, Any], path: Sequence[str]) -> Mapping[str, Any] | None:
    value: Any = row
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value if isinstance(value, Mapping) else None


def predicates(receipt: Mapping[str, Any]) -> dict[str, bool]:
    rows = receipt.get("rows")
    by_name = {row.get("name"): row for row in rows if isinstance(row, Mapping)} if isinstance(rows, list) else {}
    unsupported = by_name.get("unseen-order-unsupported", {})
    denied = by_name.get("negative-denied-second", {})
    provenance = receipt.get("provenance", {})
    learning = unsupported.get("training", {}).get("learning", []) if isinstance(unsupported, Mapping) else []
    source_records: list[tuple[Mapping[str, Any], list[dict[str, str]]]] = []
    source_valid = isinstance(learning, list) and len(learning) == 2
    if source_valid:
        for item in learning:
            if not isinstance(item, Mapping) or not isinstance(item.get("source"), Mapping):
                source_valid = False
                break
            steps = source_steps(item["source"])
            if steps is None:
                source_valid = False
                break
            source_records.append((item["source"], steps))
    digests = [hashlib.sha256(source_bytes(source) or b"__invalid__").hexdigest() for source, _ in source_records]
    expected_sources = {("left-step", "left-goal"), ("right-step", "right-goal")}
    actual_sources = {(steps[0].get("action"), steps[0].get("observation")) for _, steps in source_records if len(steps) == 1}
    descriptor = provenance.get("held_out_descriptor") if isinstance(provenance, Mapping) else None
    source_sep = source_valid and len(set(digests)) == 2 and actual_sources == expected_sources and all(len(steps) == 1 for _, steps in source_records)
    absent = source_sep and all(not contains_ordered(steps, EXPECTED_ORDER) for _, steps in source_records)
    descriptor_ok = descriptor == {
        "task_id": unsupported.get("task_id"), "ordered_skills": ["left-skill", "right-skill"], "ordered_actions": EXPECTED_ORDER,
    }
    prov_digest = hashlib.sha256(canonical({"source_digests": digests, "held_out": descriptor}).encode()).hexdigest() if descriptor_ok else ""
    provenance_ok = (
        source_sep and absent and descriptor_ok and provenance.get("training_source_content_sha256") == digests
        and provenance.get("provenance_digest") == prov_digest
    )
    public_path = receipt.get("public_path") == EXPECTED_PUBLIC_PATH
    task_ok = all(
        isinstance(row, Mapping)
        and row.get("composition", {}).get("steps") == EXPECTED_TASK_STEPS
        for row in (unsupported, denied)
    )
    first = row_receipt(unsupported, ("execution", "first", "result", "receipt"))
    second = row_receipt(unsupported, ("execution", "second", "result", "receipt"))
    denied_second = row_receipt(denied, ("execution", "second", "result", "receipt"))
    final = unsupported.get("execution", {}).get("final_view", {}) if isinstance(unsupported, Mapping) else {}
    first_ok = isinstance(first, Mapping) and first.get("status") == "proposed" and first.get("action") == "left-step"
    second_unresolved = isinstance(second, Mapping) and second.get("status") == "unresolved" and second.get("action") is None
    denied_ok = isinstance(denied_second, Mapping) and denied_second.get("status") == "unresolved" and denied_second.get("action") is None and denied.get("status") != "complete"
    unsupported_ok = unsupported.get("status") == "unresolved" and final.get("status") == "unresolved" and first_ok and second_unresolved and unsupported.get("execution", {}).get("selected_after_first") is False
    supported_claim_guard = receipt.get("verdict") == "UNSUPPORTED" and receipt.get("evaluation", {}).get("ordered_composition_supported") is False
    evaluation_expected = {
        "primitive_sources_are_separate": source_sep,
        "held_out_composition_absent_from_training": absent,
        "first_primitive_selected": first_ok,
        "second_primitive_selected_after_first": False,
        "ordered_composition_supported": False,
        "ordered_composition_unresolved": second_unresolved and unsupported.get("status") != "complete",
        "negative_denied_second_abstains": denied_ok,
    }
    aggregate = receipt.get("summary") == {"row_count": 2, "training_source_count": 2, "unsupported_row_status": "unresolved", "negative_row_status": "unresolved"}
    return {
        "schema": receipt.get("schema") == SCHEMA,
        "status": receipt.get("status") == "MEASURED",
        "shape": isinstance(rows, list) and len(rows) == 2 and set(by_name) == {"unseen-order-unsupported", "negative-denied-second"},
        "public_path": public_path, "task_bindings": task_ok,
        "training_sources_are_singletons": source_sep,
        "held_out_absent": absent,
        "provenance_rebuilt": provenance_ok,
        "unsupported_path_observed": unsupported_ok,
        "negative_can_fail": denied_ok,
        "unsupported_verdict_guard": supported_claim_guard,
        "evaluation_rederived": receipt.get("evaluation") == evaluation_expected,
        "summary_rederived": aggregate,
        "digest": bool(receipt.get("content_digest")) and receipt.get("content_digest") == digest(receipt) and receipt.get("receipt_digest") == digest(receipt),
        "provenance_digest_separate": isinstance(provenance.get("provenance_digest"), str) and provenance.get("provenance_digest") != receipt.get("content_digest"),
    }


def verify(receipt: Mapping[str, Any]) -> dict[str, Any]:
    checks = predicates(receipt)
    mutated = copy.deepcopy(receipt)
    row = next((item for item in mutated.get("rows", []) if item.get("name") == "unseen-order-unsupported"), {})
    try:
        row["execution"]["second"]["result"]["receipt"]["status"] = "proposed"
        row["execution"]["second"]["result"]["receipt"]["action"] = "right-step"
    except (KeyError, TypeError):
        pass
    checks["second_selection_anchor_fires"] = not predicates(mutated).get("unsupported_path_observed", False)
    mutated = copy.deepcopy(receipt)
    try:
        source = mutated["rows"][0]["training"]["learning"][0]["source"]
        raw = source_bytes(source) or b""
        source["content_base64"] = base64.b64encode(raw + b"\n").decode("ascii")
    except (KeyError, TypeError):
        pass
    checks["provenance_anchor_fires"] = not predicates(mutated).get("provenance_rebuilt", False)
    mutated = copy.deepcopy(receipt)
    mutated["verdict"] = "SUPPORTED"
    checks["verdict_anchor_fires"] = not predicates(mutated).get("unsupported_verdict_guard", False)
    checks["evaluation_matches"] = all(receipt.get("evaluation", {}).get(key) is value for key, value in checks.items() if key in receipt.get("evaluation", {}))
    checks["verified"] = all(bool(value) for key, value in checks.items() if key != "verified")
    return {"status": "verified" if checks["verified"] else "failed", "content_digest": digest(receipt), "checks": checks}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=Path("_diag/temporal-composition-probe/receipt.json"))
    args = parser.parse_args()
    result = verify(json.loads(args.receipt.read_text(encoding="utf-8")))
    print(json.dumps(result, sort_keys=True))
    if result["status"] != "verified":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
