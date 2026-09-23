#!/usr/bin/env python3
"""Independently verify a continuing-world interpreter program receipt.

The verifier does not import or rerun the program.  It recomputes the receipt
digest, model and activation identities, checks the packet-to-interpreter
handoff, and inspects the persisted field generation and meaning ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import sys
from pathlib import Path
from typing import Any, Mapping


PROGRAM_SCHEMA = "cassi.universal-interpreter-program.v1"
HANDOFF_SCHEMA = "cassi.universal-interpreter-task-handoff.v1"
TASK_ID = "universal-interpreter-workshop"
TASK_QUESTION = "Determine the corrected workshop load and emit its correction."
ADAPTER_KEY = "arithmetic/correction/quotient-v1"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
def _f32_digest(values: Any, label: str) -> str:
    _require(isinstance(values, list) and values, f"{label} is not a nonempty list")
    packed: list[bytes] = []
    for value in values:
        _require(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value)),
            f"{label} contains a non-finite value",
        )
        packed.append(struct.pack("<f", float(value)))
    return _sha(b"".join(packed))




def _require(condition: Any, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{label} is not an object")
    return value


def _digest(value: Any, label: str) -> str:
    _require(
        isinstance(value, str)
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        f"{label} is not a lowercase SHA-256 digest",
    )
    return value


def _model_fingerprint(model: Mapping[str, Any]) -> str:
    data = dict(model)
    _require(data.pop("schema", None) == "cassi.universal-llm-model-identity.v1", "model schema is invalid")
    payload = {"schema": "cassi.universal-llm-model-identity.v1", **data}
    return _sha(_canonical(payload))


def _trace_fingerprint(trace: Mapping[str, Any]) -> str:
    model = _mapping(trace.get("model"), "trace model")
    model_fingerprint = _model_fingerprint(model)
    _require(trace.get("model_fingerprint") == model_fingerprint, "trace model fingerprint mismatch")
    logits_sha = trace.get("logits_sha256")
    if logits_sha is not None:
        _digest(logits_sha, "trace logits_sha256")
    metadata = {
        "schema": "cassi.universal-llm-activation-trace.v1",
        "model": model_fingerprint,
        "site": trace.get("site"),
        "layer": trace.get("layer"),
        "sequence_id": trace.get("sequence_id"),
        "position": trace.get("position"),
        "values_sha256": trace.get("values_sha256"),
        "token_id": trace.get("token_id"),
        "expected_token_id": trace.get("expected_token_id"),
        "logits_sha256": logits_sha,
        "adapter_key": trace.get("adapter_key"),
        "prompt_sha256": trace.get("prompt_sha256"),
        "capture_sha256": trace.get("capture_sha256"),
    }
    _digest(metadata["values_sha256"], "trace values_sha256")
    _digest(metadata["prompt_sha256"], "trace prompt_sha256")
    coordinate = _mapping(trace.get("field_coordinate"), "trace field coordinate")
    expected_coordinate = {
        "schema": "cassi.universal-llm-activation-trace.v1",
        "site": trace.get("site"),
        "layer": trace.get("layer"),
        "coordinate_source": "adapter-key",
        "adapter_key": trace.get("adapter_key"),
        "values_sha256": None,
    }
    _require(coordinate == expected_coordinate, "trace fixed coordinate is inconsistent")
    return _sha(_canonical(metadata))


def _verify_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    _require(
        packet.get("schema") == "cassi.universal-interpreter-packet-world.v1",
        "packet schema mismatch",
    )
    stages = _mapping(packet.get("stages"), "packet stages")
    required = {
        "s1_world",
        "s2_open_episode",
        "s3_correction_and_reopen",
        "s4_selection_methods",
        "s5_source_bound_composition",
        "s6_refinement",
        "s7_source_binding",
    }
    _require(set(stages) == required, "packet stage set is incomplete or has extras")
    s1 = _mapping(stages["s1_world"], "packet s1")
    s2 = _mapping(stages["s2_open_episode"], "packet s2")
    s3 = _mapping(stages["s3_correction_and_reopen"], "packet s3")
    s4 = _mapping(stages["s4_selection_methods"], "packet s4")
    s5 = _mapping(stages["s5_source_bound_composition"], "packet s5")
    s6 = _mapping(stages["s6_refinement"], "packet s6")
    s7 = _mapping(stages["s7_source_binding"], "packet s7")
    question = _mapping(s2.get("question"), "packet question")
    _require(question.get("task_id") == TASK_ID, "packet task id mismatch")
    _require(question.get("prompt") == TASK_QUESTION, "packet question mismatch")
    _require(s1.get("premise") == 2.0, "packet premise baseline changed")
    _require(s3.get("premise_after") == 5.0, "packet correction did not settle")
    _require(s3.get("phase") == "terminal", "packet episode did not finish")
    _require(
        int(s3.get("transports_after_reopen", 0)) >= 1,
        "packet episode was not reopened",
    )
    _require(bool(s3.get("repairs")), "packet correction has no repair record")
    methods = _mapping(s4.get("scheduler_methods"), "packet scheduler methods")
    _require(
        set(methods.values())
        == {"baseline", "hierarchy", "static", "live", "shuffled", "acquired"},
        "packet selection methods are incomplete",
    )
    _require(bool(s5.get("refused")), "packet source composition did not refuse")
    _require(
        s6.get("refinement_status") == "refined",
        "packet refinement did not run",
    )
    _require(
        int(_mapping(s6.get("item_kinds"), "packet item kinds").get("refine", 0))
        == 1,
        "packet refine item missing",
    )
    refusals = _mapping(s7.get("refusals"), "packet source refusals")
    _require(
        set(refusals)
        == {"unadmitted_source", "span_outside_source", "unknown_revision"},
        "packet source controls are incomplete",
    )
    source_revision = _digest(s7.get("source_revision_id"), "packet source revision")
    packet_trace = _mapping(packet.get("packet_trace"), "packet trace")
    trace_values = packet_trace.get("values")
    _require(
        isinstance(trace_values, list) and len(trace_values) == 16,
        "packet trace is not the bounded sixteen-value row",
    )
    trace_digest = _f32_digest(trace_values, "packet trace values")
    _require(
        trace_digest == packet_trace.get("values_sha256"),
        "packet trace digest mismatch",
    )
    return {
        "source_revision_id": source_revision,
        "question": dict(question),
        "premise_before": s1["premise"],
        "premise_after": s3["premise_after"],
        "selection_methods": sorted(str(value) for value in methods.values()),
        "refinement_status": s6["refinement_status"],
        "source_refusal_controls": sorted(refusals),
        "trace_values_sha256": trace_digest,
    }


def _verify_native(native: Mapping[str, Any]) -> dict[str, Any]:
    _require(
        native.get("schema") == "cassi.universal-interpreter-boundary.v1",
        "native boundary schema mismatch",
    )
    _require(
        native.get("task_id") == TASK_ID
        and native.get("question") == TASK_QUESTION,
        "native task identity mismatch",
    )
    _require(native.get("adapter_key") == ADAPTER_KEY, "native adapter coordinate mismatch")
    packet_trace_sha = _digest(
        native.get("packet_trace_sha256"), "native packet trace"
    )
    training_values_sha = _digest(
        native.get("training_values_sha256"), "native training values"
    )
    held_out_values_sha = _digest(
        native.get("held_out_values_sha256"), "native held-out values"
    )
    training = _mapping(native.get("training_trace"), "training trace")
    held_out = _mapping(native.get("held_out_trace"), "held-out trace")
    alternate = _mapping(native.get("alternate_trace"), "alternate trace")
    for label, trace in (
        ("training", training),
        ("held_out", held_out),
        ("alternate", alternate),
    ):
        _require(
            _trace_fingerprint(trace) == trace.get("trace_sha256"),
            f"{label} trace digest mismatch",
        )
        _require(
            trace.get("adapter_key") == ADAPTER_KEY,
            f"{label} adapter coordinate mismatch",
        )
    _require(
        training_values_sha == training.get("values_sha256"),
        "training trace values digest differs from bridge receipt",
    )
    _require(
        held_out_values_sha == held_out.get("values_sha256"),
        "held-out trace values digest differs from bridge receipt",
    )
    _require(
        training.get("model_fingerprint") != alternate.get("model_fingerprint"),
        "alternate model is not distinct",
    )
    _require(
        training.get("field_coordinate") == alternate.get("field_coordinate"),
        "portable coordinates differ",
    )

    query = _mapping(native.get("query"), "native query")
    alternate_query = _mapping(native.get("alternate_query"), "alternate query")
    restart_query = _mapping(native.get("restart_query"), "restart query")
    meaning = _mapping(
        _mapping(query.get("prediction"), "query prediction").get("meaning"),
        "query meaning",
    )
    for label, result in (
        ("query", query),
        ("alternate query", alternate_query),
        ("restart query", restart_query),
    ):
        _require(result.get("status") == "field-owned", f"{label} is not field-owned")
        _require(
            result.get("native_fallback") is False,
            f"{label} used native fallback",
        )
        prediction = _mapping(result.get("prediction"), f"{label} prediction")
        _require(
            prediction.get("target_token_match") is True,
            f"{label} target did not match",
        )
        _require(prediction.get("meaning") == meaning, f"{label} meaning differs")
    _require(
        meaning.get("task_id") == TASK_ID and meaning.get("corrected_load") == 5.0,
        "native meaning is not the corrected task",
    )
    _require(
        _digest(meaning.get("source_revision_id"), "native meaning source")
        == meaning.get("source_revision_id"),
        "native source binding is malformed",
    )

    checks = _mapping(native.get("checks"), "native checks")
    _require(
        set(checks)
        == {
            "inspection_non_mutating",
            "trace_values_are_packet_derived",
            "held_out_trace_is_distinct",
            "field_prediction_supported",
            "field_prediction_matches_target",
            "alternate_model_reuses_fixed_coordinate",
            "restart_preserves_field",
            "restart_replays_meaning",
            "no_native_fallback",
            "one_adaptive_field",
        },
        "native check set is incomplete",
    )
    _require(
        all(value is True for value in checks.values()),
        "native boundary checks contain a failure",
    )
    ownership = _mapping(native.get("ownership"), "native ownership")
    _require(
        ownership.get("field_adaptive_object") == "QiFieldState.field",
        "native adaptive owner changed",
    )
    _require(ownership.get("fallback") == "none", "native ownership fallback changed")
    return {
        "packet_trace_sha256": packet_trace_sha,
        "training_values_sha256": training_values_sha,
        "held_out_values_sha256": held_out_values_sha,
        "training_trace_sha256": training["trace_sha256"],
        "held_out_trace_sha256": held_out["trace_sha256"],
        "alternate_trace_sha256": alternate["trace_sha256"],
        "model_fingerprints": sorted(
            {str(training["model_fingerprint"]), str(alternate["model_fingerprint"])}
        ),
        "meaning": dict(meaning),
        "checks": dict(checks),
    }


def _verify_persistence(root: Path, native: Mapping[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    native_root = root / "field-interpreter"
    current_path = native_root / "field" / "CURRENT"
    registry_path = native_root / "model-registry.json"
    ledger_path = native_root / "meaning-ledger.jsonl"
    for path in (current_path, registry_path, ledger_path):
        _require(path.is_file(), f"missing persisted interpreter artifact: {path}")
    generation = current_path.read_text(encoding="utf-8").strip()
    _require(re.fullmatch(r"gen-[0-9]{8}", generation) is not None, "persisted CURRENT is malformed")
    manifest_path = native_root / "field" / "generations" / generation / "manifest.json"
    _require(manifest_path.is_file(), "persisted current generation is missing its manifest")
    manifest = _mapping(json.loads(manifest_path.read_text(encoding="utf-8")), "persisted generation manifest")
    state_sha = _digest(manifest.get("state_sha256"), "persisted field state")
    restarted_state = _mapping(native.get("restarted_state"), "restarted state")
    _require(state_sha == restarted_state.get("field_state_sha256"), "persisted state differs from restart receipt")
    registry = _mapping(json.loads(registry_path.read_text(encoding="utf-8")), "model registry")
    _require(registry.get("schema") == "cassi.universal-llm-model-registry.v1", "model registry schema mismatch")
    packet_root = root / "packet-world"
    _require(
        (packet_root / "authority-control.json").is_file(),
        "missing persisted packet authority manifest",
    )
    _require(
        (packet_root / "field" / "CURRENT").is_file(),
        "missing persisted packet field head",
    )
    models = registry.get("models")
    _require(
        isinstance(models, list) and len(models) == 2,
        "model registry does not retain both identities",
    )
    models_list = models if isinstance(models, list) else []
    registered = {
        str(_mapping(row, "model registry row").get("fingerprint"))
        for row in models_list
    }
    _require(registered == {
        str(native["training_trace"]["model_fingerprint"]),
        str(native["alternate_trace"]["model_fingerprint"]),
    }, "model registry identities differ from receipt")
    lines = [line for line in ledger_path.read_text(encoding="utf-8").splitlines() if line]
    _require(len(lines) == 1, "meaning ledger is not exactly-once")
    ledger = _mapping(json.loads(lines[0]), "meaning ledger row")
    _require(ledger.get("meaning") == _mapping(native["query"]["prediction"], "query prediction").get("meaning"), "ledger meaning differs from query")
    return {
        "current_generation": generation,
        "state_sha256": state_sha,
        "registered_model_count": len(models_list),
        "ledger_rows": len(lines),
        "packet_head_present": True,
    }


def verify(receipt_path: Path, root: Path | None = None) -> dict[str, Any]:
    value = _mapping(
        json.loads(receipt_path.read_text(encoding="utf-8")),
        "program receipt",
    )
    _require(value.get("schema") == PROGRAM_SCHEMA, "program schema mismatch")
    _require(value.get("status") == "PASS", "program receipt is not passing")
    declared_digest = _digest(
        value.get("content_sha256"), "program content digest"
    )
    body = dict(value)
    body.pop("content_sha256", None)
    _require(
        _sha(_canonical(body)) == declared_digest,
        "program content digest mismatch",
    )
    packet = _verify_packet(
        _mapping(value.get("packet_world"), "packet world")
    )
    handoff = _mapping(value.get("task_handoff"), "task handoff")
    _require(handoff.get("schema") == HANDOFF_SCHEMA, "handoff schema mismatch")
    _require(
        handoff.get("task_id") == TASK_ID
        and handoff.get("question") == TASK_QUESTION,
        "handoff identity mismatch",
    )
    _require(
        handoff.get("packet_question") == packet["question"],
        "handoff packet question differs",
    )
    _require(
        _digest(handoff.get("source_revision_id"), "handoff source revision")
        == packet["source_revision_id"],
        "handoff source differs",
    )
    _require(
        handoff.get("premise_before") == 2.0
        and handoff.get("premise_after") == 5.0,
        "handoff correction differs",
    )
    _require(
        handoff.get("packet_trace_sha256") == packet["trace_values_sha256"],
        "handoff packet trace differs",
    )
    _require(
        handoff.get("native_packet_trace_sha256")
        == handoff.get("packet_trace_sha256"),
        "handoff native trace differs",
    )
    native_receipt = _mapping(value.get("native_boundary"), "native boundary")
    native = _verify_native(native_receipt)
    _require(
        handoff.get("native_packet_trace_sha256")
        == native["packet_trace_sha256"],
        "native packet trace is not the packet trace",
    )
    _require(
        handoff.get("native_model_fingerprint")
        == _mapping(
            native_receipt["training_trace"], "training trace"
        ).get("model_fingerprint"),
        "handoff model differs",
    )
    _require(
        handoff.get("native_adapter_key") == ADAPTER_KEY,
        "handoff adapter differs",
    )
    _require(
        handoff.get("meaning_source_revision_id")
        == native["meaning"]["source_revision_id"],
        "handoff meaning source differs",
    )
    expected_checks = {
        "packet_resident_episode_reopened",
        "packet_correction_applied",
        "packet_selection_frontier_exercised",
        "packet_refinement_exercised",
        "packet_source_binding_enforced",
        "semantic_question_handoff",
        "corrected_meaning_handoff",
        "source_handoff_preserved",
        "packet_to_native_trace_handoff",
        "native_boundary_passed",
        "cross_model_portability_passed",
    }
    checks = _mapping(value.get("checks"), "program checks")
    _require(set(checks) == expected_checks, "program check set is incomplete")
    _require(
        all(value is True for value in checks.values()),
        "program checks contain a failure",
    )
    persistence = _verify_persistence(
        receipt_path.with_suffix("") if root is None else root,
        native_receipt,
    )
    return {
        "schema": PROGRAM_SCHEMA,
        "status": "PASS",
        "content_sha256": declared_digest,
        "program_checks": dict(checks),
        "packet": packet,
        "native": native,
        "persistence": persistence,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path, help="integrated program receipt JSON")
    parser.add_argument("--root", type=Path, help="program directory when it is not receipt.with_suffix('')")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = verify(args.receipt, args.root)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
