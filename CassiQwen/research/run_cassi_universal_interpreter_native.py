#!/usr/bin/env python3
"""Run the universal LLM interpreter against the pinned native Qwen runtime.

This is the next vertical slice after the offline interpreter fixture.  It
captures a real layer-input residual and logits through llama.cpp's exported
C ABI, transfers the trace into one persisted ``QiFieldState.field``, then
runs field-only emission and graph-native baseline/lesion/donor arms.  Every
arm keeps raw float32 artifacts beside a compact receipt.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np
_CASSIQWEN_ROOT = Path(__file__).resolve().parent.parent
if str(_CASSIQWEN_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSIQWEN_ROOT))


from cassi_llama_capture import (
    NativeLlamaSession,
    causal_pair_from_trials,
    load_graph_trial,
    write_zero_state,
)
from cassi_model_instrument import QwenNativeInstrument, sha256_path
from cassi_raw_event_field import AcquisitionProfile
from cassi_universal_interpreter import (
    GGUFWeightObservatory,
    UniversalLLMInterpreter,
    receipt_digest,
)


HERE = Path(__file__).resolve().parent
_CASSIQWEN_ROOT = HERE.parent
NATIVE_TASK_MANIFEST_PATH = HERE / "native-role-manifest.json"
DEFAULT_MODEL = _CASSIQWEN_ROOT / "Qwen3.5-0.8B-Q4_0.gguf"
DEFAULT_RUNTIME = _CASSIQWEN_ROOT / "native/llama.cpp/b8/bin/Release"
DEFAULT_EXECUTABLE = DEFAULT_RUNTIME / "cassi-qwen.exe"
PROMPT = "Native task role=correction; intent=apply the captured correction; evidence=coherent token."
QUESTION = "Which field-owned meaning should be delivered for this native trace?"
NATIVE_ROLE = "correction"
DELAY_ROLE = "delay"
ADAPTER_KEY = "qwen35-0.8b/layer-input-mid-v1"
DEFAULT_QUANTIZATION = "Q4_0"

DELAY_ADAPTER_KEY = f"{ADAPTER_KEY}/delay-coordinate"
NATIVE_ROLE_SEMANTIC_SOURCE = "native-task-grammar-v2"
NATIVE_TASK_MANIFEST_SEMANTIC_SOURCE = "separately-authored-native-task-manifest-v1"
_NATIVE_ROLE_PATTERN = re.compile(
    r"^Native task role=(?P<role>correction|delay); "
    r"intent=(?P<intent>[^;]+); "
    r"evidence=(?P<evidence>[^.]+)\.\Z"
)
_NATIVE_ROLE_GRAMMAR = {
    "correction": {
        "intent": frozenset(
            {
                "apply the captured correction",
                "deliver the captured correction",
            }
        ),
        "evidence": frozenset({"coherent token", "stable token"}),
    },
    "delay": {
        "intent": frozenset(
            {
                "defer the captured correction",
                "postpone the captured correction",
            }
        ),
        "evidence": frozenset({"deferred token", "held token"}),
    },
}
CONTEXT_TOKENS = 256
GPU_LAYERS = 99
STATE_ELEMENTS = 4 * 9 * 6144



def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _parse_native_task_prompt(prompt: str) -> dict[str, str]:
    if not isinstance(prompt, str):
        raise RuntimeError("native prompt must be text")
    match = _NATIVE_ROLE_PATTERN.fullmatch(prompt)
    if match is None:
        raise RuntimeError("native prompt violates the role grammar")
    role = match.group("role")
    intent = match.group("intent")
    evidence = match.group("evidence")
    grammar = _NATIVE_ROLE_GRAMMAR[role]
    if intent not in grammar["intent"] or evidence not in grammar["evidence"]:
        raise RuntimeError("native prompt role semantics are contradictory")
    return {"role": role, "intent": intent, "evidence": evidence}

def _validate_behavior_probe_contract(
    document: Mapping[str, Any],
    entry: Mapping[str, Any],
) -> dict[str, Any]:
    contract = document.get("behavior_probe_contract")
    if not isinstance(contract, Mapping):
        raise RuntimeError("native task manifest behavior probe contract is missing")
    if contract.get("schema") != "cassi.native-role-behavior-contract.v1":
        raise RuntimeError("native task manifest behavior probe contract schema mismatch")
    required_ids = contract.get("required_probe_ids")
    negative_ids = contract.get("negative_control_ids")
    if (
        not isinstance(required_ids, list)
        or not required_ids
        or any(not isinstance(item, str) or not item for item in required_ids)
        or len(set(required_ids)) != len(required_ids)
        or not isinstance(negative_ids, list)
        or not negative_ids
        or any(item not in required_ids for item in negative_ids)
        or len(set(negative_ids)) != len(negative_ids)
    ):
        raise RuntimeError("native task manifest behavior probe contract IDs are invalid")
    probes = entry.get("behavior_probes")
    if not isinstance(probes, list):
        raise RuntimeError("native task manifest behavior probes are missing")
    probe_by_id: dict[str, dict[str, Any]] = {}
    for item in probes:
        if not isinstance(item, Mapping):
            raise RuntimeError("native task manifest behavior probe row is malformed")
        probe = dict(item)
        probe_id = probe.get("probe_id")
        if (
            not isinstance(probe_id, str)
            or not probe_id
            or re.fullmatch(r"[a-z0-9][a-z0-9_-]*", probe_id) is None
            or probe_id in probe_by_id
            or probe_id not in required_ids
        ):
            raise RuntimeError("native task manifest behavior probe IDs are invalid")
        for field in ("prompt", "expected_label", "contrast_label", "expected_outcome"):
            if not isinstance(probe.get(field), str) or not probe[field]:
                raise RuntimeError(f"native task manifest behavior probe field {field} is invalid")
        if (
            probe["expected_label"] not in {"correction", "delay"}
            or probe["contrast_label"] not in {"correction", "delay"}
            or probe["expected_label"] == probe["contrast_label"]
            or probe["expected_outcome"] not in {"pass", "fail"}
            or (
                probe_id in negative_ids
                and probe["expected_outcome"] != "fail"
            )
            or (
                probe_id not in negative_ids
                and probe["expected_outcome"] != "pass"
            )
        ):
            raise RuntimeError("native task manifest behavior probe outcome contract is invalid")
        probe_by_id[probe_id] = probe
    if set(probe_by_id) != set(required_ids):
        raise RuntimeError("native task manifest behavior probes do not cover the contract")
    return {
        "schema": contract["schema"],
        "required_probe_ids": list(required_ids),
        "negative_control_ids": list(negative_ids),
    }


def _ordered_behavior_probes(
    task_manifest: Mapping[str, Any],
) -> list[dict[str, Any]]:
    entry = task_manifest["entry"]
    probes = {probe["probe_id"]: probe for probe in entry["behavior_probes"]}
    return [probes[probe_id] for probe_id in task_manifest["probe_contract"]["required_probe_ids"]]


def _load_native_task_manifest(path: Path, prompt: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("native task manifest could not be loaded") from exc
    if not isinstance(document, Mapping):
        raise RuntimeError("native task manifest must be an object")
    if document.get("schema") != "cassi.native-task-role-manifest.v1":
        raise RuntimeError("native task manifest schema mismatch")
    if document.get("semantic_source") != NATIVE_TASK_MANIFEST_SEMANTIC_SOURCE:
        raise RuntimeError("native task manifest semantic source mismatch")
    entries = document.get("entries")
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("native task manifest has no entries")
    prompt_sha256 = _sha_bytes(prompt.encode("utf-8"))
    matches = [
        entry
        for entry in entries
        if isinstance(entry, Mapping)
        and entry.get("prompt_sha256") == prompt_sha256
    ]
    if len(matches) != 1:
        raise RuntimeError("native task manifest has no unique prompt binding")
    entry = dict(matches[0])
    for field in ("task_id", "role", "intent", "evidence"):
        if not isinstance(entry.get(field), str) or not entry[field]:
            raise RuntimeError(f"native task manifest field {field} is invalid")
    probe_contract = _validate_behavior_probe_contract(document, entry)
    return {
        "schema": document["schema"],
        "semantic_source": document["semantic_source"],
        "manifest_sha256": _sha_bytes(_canonical(document)),
        "path": path.name,
        "probe_contract": probe_contract,
        "entry": entry,
    }


def _resolve_native_task_manifest(
    prompt: str,
    path: Path = NATIVE_TASK_MANIFEST_PATH,
) -> dict[str, Any]:
    semantics = _parse_native_task_prompt(prompt)
    manifest = _load_native_task_manifest(path, prompt)
    entry = manifest["entry"]
    if any(entry[field] != semantics[field] for field in ("role", "intent", "evidence")):
        raise RuntimeError("native task manifest disagrees with prompt grammar")
    return {
        **manifest,
        "derived_native_role": semantics["role"],
        "prompt_semantics": semantics,
    }


def _sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _derive_native_role(prompt: str) -> str:
    """Derive a role from a closed native-task grammar."""

    return _parse_native_task_prompt(prompt)["role"]


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")


def _state_descriptor(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": _relative(path, root),
        "sha256": sha256_path(path),
        "bytes": path.stat().st_size,
        "elements": path.stat().st_size // 4,
    }

def _run_native_behavior_probes(
    native: NativeLlamaSession,
    task_manifest: Mapping[str, Any],
    *,
    output_dir: Path,
    root: Path,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for probe in _ordered_behavior_probes(task_manifest):
        probe_id = str(probe["probe_id"])
        prompt = str(probe["prompt"])
        expected_label = str(probe["expected_label"])
        contrast_label = str(probe["contrast_label"])
        tokens, logits = native.probe_logits(prompt)
        expected_tokens = native.tokenize_text(f" {expected_label}")
        contrast_tokens = native.tokenize_text(f" {contrast_label}")
        if len(expected_tokens) != 1 or len(contrast_tokens) != 1:
            raise RuntimeError(f"native behavior probe labels are not single tokens: {probe_id}")
        expected_token_id = int(expected_tokens[0])
        contrast_token_id = int(contrast_tokens[0])
        values = np.asarray(logits, dtype=np.float32)
        output_path = output_dir / f"{probe_id}.f32"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        values.tofile(output_path)
        expected_logit = float(values[expected_token_id])
        contrast_logit = float(values[contrast_token_id])
        margin = expected_logit - contrast_logit
        expected_label_won = bool(expected_logit > contrast_logit)
        expected_outcome = str(probe["expected_outcome"])
        control_passed = expected_label_won == (expected_outcome == "pass")
        if not control_passed:
            raise RuntimeError(f"native behavior probe outcome mismatch: {probe_id}")
        results.append(
            {
                "schema": "cassi.native-role-behavior-probe.v2",
                "probe_id": probe_id,
                "path": _relative(output_path, root),
                "sha256": sha256_path(output_path),
                "bytes": int(output_path.stat().st_size),
                "elements": int(values.size),
                "prompt_sha256": _sha_bytes(prompt.encode("utf-8")),
                "prompt_token_count": len(tokens),
                "expected_label": expected_label,
                "contrast_label": contrast_label,
                "expected_outcome": expected_outcome,
                "expected_token_id": expected_token_id,
                "contrast_token_id": contrast_token_id,
                "expected_logit": expected_logit,
                "contrast_logit": contrast_logit,
                "margin": margin,
                "top_token_id": int(np.argmax(values)),
                "expected_rank": int(np.count_nonzero(values > expected_logit)) + 1,
                "expected_label_won": expected_label_won,
                "control_passed": control_passed,
            }
        )
    return {
        "schema": "cassi.native-role-behavior-probe-matrix.v1",
        "probe_ids": [result["probe_id"] for result in results],
        "negative_control_ids": list(task_manifest["probe_contract"]["negative_control_ids"]),
        "probes": results,
        "result_sha256": _sha_bytes(_canonical(results)),
        "all_controls_passed": all(result["control_passed"] for result in results),
    }


def _field_result_view(result: Mapping[str, Any], root: Path) -> dict[str, Any]:
    receipt = result["receipt"]
    ownership = result["ownership"]
    successor = result["state_successor"]
    output = str(result.get("output", ""))
    return {
        "schema": result.get("schema"),
        "status": result.get("status"),
        "mode": result.get("mode"),
        "native_verdict": receipt.get("verdict"),
        "output_sha256": _sha_bytes(output.encode("utf-8")),
        "output_bytes": len(output.encode("utf-8")),
        "output_preview": output[:256],
        "identity_sha256": result.get("identity_sha256"),
        "continuation_class": result.get("continuation_class"),
        "state_predecessor": {
            "sha256": result["state_predecessor"]["sha256"],
            "bytes": result["state_predecessor"]["bytes"],
        },
        "state_successor": {
            "path": _relative(Path(successor["path"]), root),
            "sha256": successor["sha256"],
            "bytes": successor["bytes"],
            "kind": successor["kind"],
        },
        "ownership": dict(ownership),
        "receipt_counters": {
            name: receipt.get(name)
            for name in (
                "qwen_forward_passes",
                "model_logits_read",
                "field_logits_read",
                "lm_head_rows_computed",
                "lm_head_rows_skipped",
                "sampler_steps",
                "qwen_tensor_bytes_loaded",
            )
        },
    }


def _interpreter_view(
    *,
    inspection: Mapping[str, Any],
    learning: Mapping[str, Any],
    query: Mapping[str, Any],
    explanation: Mapping[str, Any],
    restart_query: Mapping[str, Any],
    state_before: Mapping[str, Any],
    state_after_learning: Mapping[str, Any],
    restarted_state: Mapping[str, Any],
    ownership: Mapping[str, Any],
    model_fingerprint: str,
) -> dict[str, Any]:
    return {
        "inspection": {
            "field_state_sha256": inspection["field_state_sha256"],
            "field_mutated": inspection["field_mutated"],
            "trace_sha256": inspection["trace"]["trace_sha256"],
            "model_fingerprint": model_fingerprint,
        },
        "learning": {
            "status": learning["status"],
            "field_state_sha256": learning["field_state_sha256"],
            "field_owned_adaptive_state": learning["field_owned_adaptive_state"],
            "meaning_packet_hex": learning["meaning_packet_hex"],
        },
        "query": {
            "status": query["status"],
            "field_state_sha256": query["field_state_sha256"],
            "field_mutated": query["field_mutated"],
            "native_fallback": query["native_fallback"],
            "prediction": query["prediction"],
        },
        "explanation": {
            "claim": explanation["claim"],
            "native_displacement": explanation["native_displacement"],
            "field_state_sha256": explanation["evidence"]["field_state_sha256"],
        },
        "restart_query": {
            "status": restart_query["status"],
            "field_state_sha256": restart_query["field_state_sha256"],
            "native_fallback": restart_query["native_fallback"],
            "prediction": restart_query["prediction"],
        },
        "state": {
            "before": state_before["field_state_sha256"],
            "after_learning": state_after_learning["field_state_sha256"],
            "restarted": restarted_state["field_state_sha256"],
        },
        "ownership": {
            "field_adaptive_object": ownership["field_adaptive_object"],
            "decisions": ownership["decisions"],
            "native_displacement": ownership["native_displacement"],
            "fallback": ownership["fallback"],
        },
    }


def _trial_with_path(receipt: Mapping[str, Any], receipt_path: Path) -> dict[str, Any]:
    row = dict(receipt)
    row["_receipt_path"] = str(receipt_path)
    return row


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)
def run(
    root: Path,
    *,
    model_path: Path = DEFAULT_MODEL,
    runtime_dir: Path = DEFAULT_RUNTIME,
    executable: Path = DEFAULT_EXECUTABLE,
    task_id: str = "native-universal-interpreter",
    question: str = QUESTION,
    source_revision_id: str | None = None,
    use_answer_bearing_target: bool = True,
    gpu_layers: int = GPU_LAYERS,
    quantization: str = DEFAULT_QUANTIZATION,
    adapter_key: str = ADAPTER_KEY,
    expected_model_sha256: str | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    if root.exists() and any(root.iterdir()):
        raise RuntimeError(f"refusing to reuse nonempty run root: {root}")
    root.mkdir(parents=True, exist_ok=False)
    model_path = Path(model_path).resolve()
    runtime_dir = Path(runtime_dir).resolve()
    executable = Path(executable).resolve()
    for path in (model_path, runtime_dir, executable):
        if not path.exists():
            raise FileNotFoundError(path)
    if expected_model_sha256 is not None:
        if not isinstance(expected_model_sha256, str) or len(expected_model_sha256) != 64:
            raise ValueError("expected_model_sha256 must be a 64-character digest")
        if sha256_path(model_path) != expected_model_sha256:
            raise RuntimeError("native role model digest contract mismatch")


    native_task_manifest = _resolve_native_task_manifest(PROMPT)
    derived_native_role = native_task_manifest["derived_native_role"]
    if not isinstance(gpu_layers, int) or isinstance(gpu_layers, bool) or not 0 <= gpu_layers <= 512:
        raise ValueError("gpu_layers must be in [0, 512]")
    if not isinstance(quantization, str) or not quantization:
        raise ValueError("quantization must be a nonempty identifier")
    if not isinstance(adapter_key, str) or not adapter_key:
        raise ValueError("adapter_key must be a nonempty identifier")
    delay_adapter_key = f"{adapter_key}/delay-coordinate"

    _require(
        derived_native_role == NATIVE_ROLE,
        "native task manifest role disagrees with declared role",
    )

    capture_dir = root / "native-capture"
    with NativeLlamaSession(
        runtime_dir,
        model_path,
        gpu_layers=gpu_layers,
        context_tokens=CONTEXT_TOKENS,
        quantization=quantization,
    ) as native:
        behavior_probes = _run_native_behavior_probes(
            native,
            native_task_manifest,
            output_dir=root / "native-role-behavior-probes",
            root=root,
        )
        capture = native.capture(
            prompt=PROMPT,
            sequence_id="native-capture",
            adapter_key=adapter_key,
            native_role=NATIVE_ROLE,
            output_dir=capture_dir,
        )
        native_model = capture.trace.model
        graph_layer = capture.trace.layer

    if capture.trace.prompt_sha256 is None or capture.trace.capture_sha256 is None:
        raise RuntimeError("native capture omitted role-evidence digests")
    role_registry = {
        adapter_key: {
            "semantic_role": NATIVE_ROLE,
            "model_fingerprint": native_model.fingerprint,
        },
        delay_adapter_key: {
            "semantic_role": DELAY_ROLE,
            "model_fingerprint": native_model.fingerprint,
        },
    }
    native_role_manifest = [
        {
            "model_fingerprint": native_model.fingerprint,
            "prompt_sha256": capture.trace.prompt_sha256,
            "capture_sha256": capture.trace.capture_sha256,
            "native_role": derived_native_role,
            "semantic_source": NATIVE_ROLE_SEMANTIC_SOURCE,
            "task_manifest_id": native_task_manifest["entry"]["task_id"],
            "task_manifest_sha256": native_task_manifest["manifest_sha256"],
            "task_manifest_source": native_task_manifest["semantic_source"],
            "behavior_probe_matrix_sha256": behavior_probes["result_sha256"],
            "behavior_probe_ids": behavior_probes["probe_ids"],
            "behavior_probe_negative_control_ids": behavior_probes["negative_control_ids"],
        }
    ]
    behavior_probe_by_id = {
        result["probe_id"]: result
        for result in behavior_probes["probes"]
    }

    graph_zero = root / "state-zero.f32"
    write_zero_state(graph_zero, elements=STATE_ELEMENTS)
    graph_donor_control = root / "state-donor-control.f32"
    shutil.copyfile(graph_zero, graph_donor_control)

    # Use the declared field-only executable to produce an independent
    # successor state. That state becomes the graph lesion donor.
    native_instrument = QwenNativeInstrument(
        executable=executable,
        model=model_path,
        state=graph_zero,
        backend="gpu" if gpu_layers > 0 else "cpu",
        quantization=quantization,
        coupling={
            "displacement": 0,
            "injection_scale": 1.0,
            "energy_floor": 1.0e-6,
            "read_floor": 0.05,
        },
    )
    field_seed = native_instrument.execute(
        mode="field",
        prompt=PROMPT,
        tokens=1,
        trial_dir=root / "field-seed",
        state_in=graph_zero,
        field_layer=graph_layer,
    )
    donor_state = Path(field_seed["state_successor"]["path"]).resolve()
    shutil.copyfile(donor_state, root / "state-donor.f32")
    field_output = native_instrument.execute(
        mode="field",
        prompt=PROMPT,
        tokens=4,
        trial_dir=root / "field-owned-emission",
        state_in=donor_state,
        field_layer=graph_layer,
    )
    _write_json(root / "field-seed" / "result.json", dict(field_seed))
    _write_json(root / "field-owned-emission" / "result.json", dict(field_output))

    graph_root = root / "graph-native"
    graph_root.mkdir()
    continuation_token = int(capture.receipt["prompt"]["token_ids"][-1])
    continuation_tokens = [continuation_token]
    with NativeLlamaSession(
        runtime_dir,
        model_path,
        gpu_layers=gpu_layers,
        context_tokens=CONTEXT_TOKENS,
        quantization=quantization,
    ) as native:
        native.graph_trial(
            prompt=PROMPT,
            sequence_id="graph-pair",
            state_path=graph_zero,
            output_dir=graph_root / "baseline-field-output",
            displacement=6,
            injection_scale=0.0,
            substitute=0.0,
            layer=graph_layer,
            capture_id="baseline-field-output",
            continuation_tokens=continuation_tokens,
        )
        graph_lesion = native.graph_trial(
            prompt=PROMPT,
            sequence_id="graph-pair",
            state_path=root / "state-donor.f32",
            output_dir=graph_root / "lesion-field-state",
            displacement=6,
            injection_scale=0.0,
            substitute=0.0,
            layer=graph_layer,
            capture_id="lesion-field-state",
            continuation_tokens=continuation_tokens,
        )
        native.graph_trial(
            prompt=PROMPT,
            sequence_id="graph-pair",
            state_path=graph_donor_control,
            output_dir=graph_root / "donor-baseline-state",
            displacement=6,
            injection_scale=0.0,
            substitute=0.0,
            layer=graph_layer,
            capture_id="donor-baseline-state",
            continuation_tokens=continuation_tokens,
        )
        native.graph_trial(
            prompt=PROMPT,
            sequence_id="recurrent-pair",
            state_path=graph_zero,
            output_dir=graph_root / "recurrent-model",
            displacement=0,
            injection_scale=0.0,
            substitute=0.0,
            layer=graph_layer,
            capture_id="recurrent-model",
            continuation_tokens=continuation_tokens,
        )
        native.graph_trial(
            prompt=PROMPT,
            sequence_id="recurrent-pair",
            state_path=graph_zero,
            output_dir=graph_root / "recurrent-suppressed",
            displacement=3,
            injection_scale=0.0,
            substitute=0.0,
            layer=graph_layer,
            capture_id="recurrent-suppressed",
            continuation_tokens=continuation_tokens,
        )
        native.graph_trial(
            prompt=PROMPT,
            sequence_id="recurrent-pair",
            state_path=graph_zero,
            output_dir=graph_root / "recurrent-field",
            displacement=3,
            injection_scale=0.0,
            substitute=1.0,
            layer=graph_layer,
            capture_id="recurrent-field",
            continuation_tokens=continuation_tokens,
        )


    graph_receipt_paths = {
        "baseline_field_output": graph_root / "baseline-field-output" / "graph-trial-receipt.json",
        "lesion_field_state": graph_root / "lesion-field-state" / "graph-trial-receipt.json",
        "donor_baseline_state": graph_root / "donor-baseline-state" / "graph-trial-receipt.json",
        "recurrent_model": graph_root / "recurrent-model" / "graph-trial-receipt.json",
        "recurrent_suppressed": graph_root / "recurrent-suppressed" / "graph-trial-receipt.json",
        "recurrent_field": graph_root / "recurrent-field" / "graph-trial-receipt.json",
    }

    capture_reloaded = capture.trace
    profile = AcquisitionProfile(
        wave_width=512,
        payload_limit=16,
        trace_horizon=2,
        minimum_score=0.58,
        minimum_margin=0.08,
    )
    if source_revision_id is None:
        source_revision_id = _sha_bytes(f"{task_id}\x00{question}".encode("utf-8"))
    meaning: dict[str, Any] = {
        "kind": "native-qwen-field-meaning",
        "rule": (
            "the captured native readout is the correction target; delivery is field-owned"
            if use_answer_bearing_target
            else "native trace is admitted without supplying its answer-bearing target"
        ),
        "evidence": "native-capture/capture-receipt.json",
        "task_id": task_id,
        "source_revision_id": source_revision_id,
    }
    if use_answer_bearing_target:
        meaning["next_token_id"] = int(capture.trace.model_next_token_id)
    interpreter_root = root / "interpreter"
    with UniversalLLMInterpreter(
        interpreter_root,
        model=native_model,
        profile=profile,
        role_registry=role_registry,
        native_role_manifest=native_role_manifest,
    ) as interpreter:
        state_before = interpreter.state_receipt()
        inspection = interpreter.inspect(capture.trace)
        learning = interpreter.learn(capture.trace, question=question, meaning=meaning)
        state_after_learning = interpreter.state_receipt()
        query = interpreter.query(capture_reloaded, question=question)
        explanation = interpreter.explain(capture_reloaded, question=question)
        ownership = interpreter.ownership_receipt()
        field_state_before_close = interpreter.store.learner.fingerprint()
        semantically_misbound = replace(
            capture_reloaded,
            adapter_key=delay_adapter_key,
            native_role=None,
            role_attestation=None,
        ).with_role_attestation(DELAY_ROLE)
        unregistered_evidence = replace(
            capture_reloaded,
            prompt_sha256=_sha_bytes(b"unregistered-native-prompt"),
            native_role=None,
            role_attestation=None,
        ).with_role_attestation(NATIVE_ROLE)

        def reject_role_attack(
            trace: Any,
            expected_message: str,
        ) -> dict[str, Any]:
            before = interpreter.state_receipt()
            try:
                interpreter.query(trace, question=question)
            except ValueError as exc:
                error = str(exc)
            else:
                raise RuntimeError("role attack was admitted")
            after = interpreter.state_receipt()
            _require(expected_message in error, f"unexpected role attack error: {error}")
            _require(after == before, "rejected role attack mutated field state")
            return {
                "rejected": True,
                "error": error,
                "state_unchanged": True,
            }

        role_attack_results = {
            "semantic_misbinding": reject_role_attack(
                semantically_misbound,
                "native role evidence mismatch",
            ),
            "unregistered_evidence": reject_role_attack(
                unregistered_evidence,
                "unregistered native role evidence",
            ),
        }


    with UniversalLLMInterpreter(
        interpreter_root,
        model=native_model,
        profile=profile,
        role_registry=role_registry,
        native_role_manifest=native_role_manifest,
    ) as restarted:
        restarted_state = restarted.state_receipt()
        restart_query = restarted.query(capture_reloaded, question=question)
        field_state_after_restart_query = restarted.store.learner.fingerprint()
    interpreter_view = _interpreter_view(
        inspection=inspection,
        learning=learning,
        query=query,
        explanation=explanation,
        restart_query=restart_query,
        state_before=state_before,
        state_after_learning=state_after_learning,
        restarted_state=restarted_state,
        ownership=ownership,
        model_fingerprint=native_model.fingerprint,
    )
    _write_json(interpreter_root / "native-interpreter-evidence.json", {
        "inspection": inspection,
        "learning": learning,
        "query": query,
        "explanation": explanation,
        "restart_query": restart_query,
        "state_before": state_before,
        "state_after_learning": state_after_learning,
        "restarted_state": restarted_state,
        "ownership": ownership,
    })

    with GGUFWeightObservatory(model_path, model=native_model, max_cells=16) as observatory:
        requested_tensors = ("token_embd.weight", "output.weight")
        available_tensors = tuple(name for name in requested_tensors if name in observatory._tensors)
        inventory = {
            "requested": list(requested_tensors),
            "available": observatory.inventory(names=available_tensors),
            "missing": [name for name in requested_tensors if name not in available_tensors],
            "output_binding": "Qwen3.5 GGUF omits output.weight; token_embd.weight is the tied output projection",
        }
        weight = observatory.read_slice(
            "token_embd.weight",
            row_start=0,
            row_stop=2,
            column_start=0,
            column_stop=2,
        )
    _write_json(root / "native-weight-evidence.json", {
        "inventory": inventory,
        "slice": weight.as_dict(),
    })

    graph_base_receipt = load_graph_trial(graph_receipt_paths["baseline_field_output"])
    graph_lesion_receipt = load_graph_trial(graph_receipt_paths["lesion_field_state"])
    graph_donor_receipt = load_graph_trial(graph_receipt_paths["donor_baseline_state"])
    recurrent_model_receipt = load_graph_trial(graph_receipt_paths["recurrent_model"])
    recurrent_suppressed_receipt = load_graph_trial(graph_receipt_paths["recurrent_suppressed"])
    recurrent_field_receipt = load_graph_trial(graph_receipt_paths["recurrent_field"])
    field_pair = causal_pair_from_trials(
        _trial_with_path(graph_base_receipt, graph_receipt_paths["baseline_field_output"]),
        _trial_with_path(graph_lesion_receipt, graph_receipt_paths["lesion_field_state"]),
        donor=_trial_with_path(graph_donor_receipt, graph_receipt_paths["donor_baseline_state"]),
        intervention_kind="field-owned-lm-head-state",
    )
    recurrent_pair = causal_pair_from_trials(
        _trial_with_path(recurrent_model_receipt, graph_receipt_paths["recurrent_model"]),
        _trial_with_path(recurrent_field_receipt, graph_receipt_paths["recurrent_field"]),
        intervention_kind="field-owned-recurrent-state-replacement",
    )
    recurrent_control_pair = causal_pair_from_trials(
        _trial_with_path(recurrent_suppressed_receipt, graph_receipt_paths["recurrent_suppressed"]),
        _trial_with_path(recurrent_field_receipt, graph_receipt_paths["recurrent_field"]),
        intervention_kind="suppressed-model-vs-field-recurrent-state",
    )

    field_view = _field_result_view(field_output, root)
    seed_view = _field_result_view(field_seed, root)
    graph_view = {
        "baseline_field_output": graph_base_receipt,
        "lesion_field_state": graph_lesion_receipt,
        "donor_baseline_state": graph_donor_receipt,
        "recurrent_model": recurrent_model_receipt,
        "recurrent_suppressed": recurrent_suppressed_receipt,
        "recurrent_field": recurrent_field_receipt,
        "field_owned_pair": field_pair,
        "recurrent_pair": recurrent_pair,
        "recurrent_control_pair": recurrent_control_pair,
        "continuation_tokens": continuation_tokens,
        "receipt_paths": {key: _relative(path, root) for key, path in graph_receipt_paths.items()},
    }

    role_authentication = {
        "schema": "cassi.native-role-authentication.v1",
        "semantic_source": NATIVE_ROLE_SEMANTIC_SOURCE,
        "task_manifest": native_task_manifest,
        "prompt": {
            "sha256": _sha_bytes(PROMPT.encode("utf-8")),
            "derived_native_role": derived_native_role,
        },
        "declared_native_role": capture.trace.native_role,
        "role_registry": role_registry,
        "native_role_manifest": native_role_manifest,
        "behavior_probes": behavior_probes,
        "state_role_gate": state_after_learning["role_gate"],
        "tamper_checks": role_attack_results,
    }


    checks = {
        "native_capture_parity": capture.receipt["parity"]["pass"] is True,
        "native_capture_nonzero": float(np.linalg.norm(capture.trace.values.astype(np.float64))) > 0.0,
        "native_role_manifest_semantic_binding": (
            capture.trace.native_role == derived_native_role
            and capture.trace.role_attestation is not None
            and native_task_manifest["entry"]["role"] == derived_native_role
            and native_task_manifest["entry"]["intent"] == native_task_manifest["prompt_semantics"]["intent"]
            and native_task_manifest["entry"]["evidence"] == native_task_manifest["prompt_semantics"]["evidence"]
            and role_authentication["state_role_gate"]["native_role_manifest_entry_count"] == 1
            and all(
                result["rejected"] and result["state_unchanged"]
                for result in role_attack_results.values()
            )
        ),
        "native_role_behavior_probes": (
            behavior_probes["all_controls_passed"] is True
            and behavior_probes["probe_ids"] == native_task_manifest["probe_contract"]["required_probe_ids"]
            and all(
                behavior_probe_by_id[probe_id]["control_passed"]
                for probe_id in native_task_manifest["probe_contract"]["required_probe_ids"]
            )
        ),
        "native_role_negative_control_fired": all(
            behavior_probe_by_id[probe_id]["expected_label_won"] is False
            for probe_id in native_task_manifest["probe_contract"]["negative_control_ids"]
        ),
        "weight_observation_bounded": weight.values.shape == (2, 2) and weight.raw_bytes_touched > 0,
        "interpreter_inspection_nonmutating": interpreter_view["inspection"]["field_mutated"] is False,
        "interpreter_field_owned": interpreter_view["query"]["status"] == "field-owned",
        "interpreter_restart_exact": field_state_before_close == restarted_state["field_state_sha256"] == field_state_after_restart_query,
        "interpreter_target_matches_native": (
            not use_answer_bearing_target
            or interpreter_view["query"]["prediction"]["target_token_match"] is True
        ),
        "interpreter_no_fallback": interpreter_view["query"]["native_fallback"] is False and interpreter_view["restart_query"]["native_fallback"] is False,
        "field_seed_owned": seed_view["native_verdict"] == "PASS" and seed_view["ownership"]["output_owner"] == "field" and seed_view["ownership"]["qwen_forward_passes"] == 0,
        "field_emission_owned": field_view["native_verdict"] == "PASS" and field_view["ownership"]["output_owner"] == "field" and field_view["ownership"]["sampler_owner"] == "field" and field_view["ownership"]["silent_native_fallback"] is False,
        "graph_field_pair_executed": field_pair["graph_native_executed"] is True and field_pair["status"] == "causal-effect",
        "graph_field_pair_donor_restores": field_pair["donor_restores_baseline_decision"] is True,
        "graph_field_output_owned": graph_base_receipt["graph"]["lm_head_owner"] == "field" and graph_base_receipt["graph"]["model_logits_read"] == 0 and graph_base_receipt["graph"]["field_logits_read"] == graph_base_receipt["graph"]["decode_steps"],
        "graph_recurrent_pair_executed": recurrent_pair["graph_native_executed"] is True and recurrent_pair["status"] == "causal-effect",
        "graph_recurrent_control_executed": recurrent_control_pair["graph_native_executed"] is True and recurrent_control_pair["status"] == "causal-effect",
        "graph_recurrent_ownership": recurrent_model_receipt["graph"]["qi_state_write_owner"] == "model" and recurrent_suppressed_receipt["graph"]["qi_state_write_owner"] == "suppressed-model" and recurrent_field_receipt["graph"]["qi_state_write_owner"] == "field",
        "graph_routes_not_counterfactual": all(row["graph"]["executed"] is True for row in (graph_base_receipt, graph_lesion_receipt, graph_donor_receipt, recurrent_model_receipt, recurrent_suppressed_receipt, recurrent_field_receipt)),
    }
    _require(all(checks.values()), f"native universal-interpreter checks failed: {checks}")

    body: dict[str, Any] = {
        "schema": "cassi.universal-llm-interpreter-native-program.v2",
        "status": "PASS",
        "model": native_model.as_dict(),
        "runtime": {
            "directory": runtime_dir.name,
            "executable": executable.name,
            "executable_sha256": sha256_path(executable),
        },
        "task_id": task_id,
        "question": question,
        "source_revision_id": source_revision_id,
        "answer_bearing_activation_supplied": bool(use_answer_bearing_target),
        "prompt": {"utf8": PROMPT, "sha256": _sha_bytes(PROMPT.encode("utf-8"))},
        "interpreter": interpreter_view,
        "role_authentication": role_authentication,
        "native_capture": capture.receipt,
        "weight_observatory": {
            "inventory": inventory,
            "slice": weight.as_dict(),
        },
        "field_owned_emission": field_view,
        "field_owned_seed": seed_view,
        "graph_native": graph_view,
        "program_dimensions": {
            "observatory": "real llama.cpp layer-input residual, logits, and bounded GGUF slice",
            "translation": "fixed adapter-key coordinate",
            "field_learning": "one QiFieldState.field through RawEventStore",
            "field_emission": "standalone fixed Qi vocabulary transducer",
            "graph_displacement": "LM-head replacement at displacement 6",
            "state_lesion": "two-step recurrent write ownership at displacement 3",
            "causal_reading": "graph-native output and recurrent baseline/lesion/control pairs",
            "persistence": "atomic field checkpoint and exact restart fingerprint",
        },
        "ownership": {
            "field_adaptive_object": "QiFieldState.field",
            "field_owned_decisions": [
                "field-only token emission",
                "displacement-6 LM-head logits",
                "displacement-3 recurrent field-state replacement",
            ],
            "native_displacement_status": "measured",
            "native_dynamic_state_bytes_removed": 0,
            "native_dynamic_state_footprint_bytes": recurrent_field_receipt["state_successor"]["bytes"],
            "native_dynamic_state_field_bytes_per_decode": recurrent_field_receipt["graph"]["qi_state_field_bytes"],
            "native_dynamic_state_remaining_model_bytes_per_decode": recurrent_field_receipt["graph"]["qi_state_remaining_model_bytes"],
            "native_dynamic_state_write_owner": recurrent_field_receipt["graph"]["qi_state_write_owner"],
            "native_ops_skipped_per_graph_decode": graph_base_receipt["graph"]["lm_head_rows_skipped"] // graph_base_receipt["graph"]["decode_steps"],
            "native_output_rows_skipped_per_graph_decode": graph_base_receipt["graph"]["lm_head_rows_skipped"] // graph_base_receipt["graph"]["decode_steps"],
            "qwen_weight_bytes_loaded": graph_base_receipt["graph"]["qwen_tensor_bytes_loaded"],
            "qwen_weight_bytes_touched_per_field_only_token": 0,
            "silent_native_fallback": False,
        },
        "checks": checks,
    }
    body["content_sha256"] = receipt_digest(body)
    _atomic_json(root / "native-program-receipt.json", body)
    return body


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_CASSIQWEN_ROOT / "_diag/universal-interpreter-native-program")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--executable", type=Path, default=DEFAULT_EXECUTABLE)
    parser.add_argument("--gpu-layers", type=int, default=GPU_LAYERS)
    parser.add_argument("--quantization", default=DEFAULT_QUANTIZATION)
    parser.add_argument("--adapter-key", default=ADAPTER_KEY)
    parser.add_argument("--expected-model-sha256")
    parser.add_argument("--output", type=Path, help="copy the compact receipt to this path")
    parser.add_argument("--task-id", default="native-universal-interpreter")
    parser.add_argument("--question", default=QUESTION)
    parser.add_argument("--source-revision-id")
    parser.add_argument(
        "--without-answer-bearing-target",
        action="store_true",
        help="capture the native trace without supplying its next-token target to the field",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt = run(
            args.root,
            model_path=args.model,
            runtime_dir=args.runtime_dir,
            executable=args.executable,
            task_id=args.task_id,
            question=args.question,
            source_revision_id=args.source_revision_id,
            use_answer_bearing_target=not args.without_answer_bearing_target,
            gpu_layers=args.gpu_layers,
            quantization=args.quantization,
            adapter_key=args.adapter_key,
            expected_model_sha256=args.expected_model_sha256,
        )
    except Exception as error:
        print(f"native universal interpreter failed: {error}", file=sys.stderr)
        return 1
    payload = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(json.dumps({
            "status": receipt["status"],
            "receipt": str((args.root / "native-program-receipt.json").resolve()),
            "content_sha256": receipt["content_sha256"],
        }, sort_keys=True))
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
