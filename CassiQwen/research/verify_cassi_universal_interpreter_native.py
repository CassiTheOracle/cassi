#!/usr/bin/env python3
"""Independently verify a native universal-interpreter run directory.

The verifier never launches llama.cpp and never trusts the runner's pair
assessment. It rehashes every linked float32 artifact, reconstructs graph
snapshots, reruns the causal comparison, and checks the field-ownership
counters and top-level receipt digest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import math
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from cassi_universal_interpreter import ActivationTrace, CausalPair, ModelIdentity, OutputSnapshot


CAPTURE_SCHEMA = "cassi.universal-llm-native-capture.v2"
GRAPH_SCHEMA = "cassi.universal-llm-graph-trial.v2"
MAX_STATE_BYTES = 4 * 9 * 6144 * 4
CAPTURE_KINDS = {
    "embedding": (3, None),
    "layer_input": (4, "layer"),
    "attention_output": (1, "layer"),
    "attention_probs": (2, "layer"),
    "ffn_input": (5, "layer"),
    "ffn_output": (6, "layer"),
    "head_input": (0, None),
    "head_output": (7, None),
}

def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

ROLE_EVIDENCE_SCHEMA = "cassi.native-role-evidence.v1"
NATIVE_ROLE_SEMANTIC_SOURCE = "native-task-grammar-v2"
NATIVE_TASK_MANIFEST_PATH = Path(__file__).resolve().parent / "native-role-manifest.json"
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


def _parse_native_task_prompt(prompt: str) -> dict[str, str]:
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
            or (probe_id in negative_ids and probe["expected_outcome"] != "fail")
            or (probe_id not in negative_ids and probe["expected_outcome"] != "pass")
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


def _ordered_behavior_probes(task_manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    probes = {probe["probe_id"]: probe for probe in task_manifest["entry"]["behavior_probes"]}
    return [probes[probe_id] for probe_id in task_manifest["probe_contract"]["required_probe_ids"]]
def _derive_native_role(prompt: str) -> str:
    return _parse_native_task_prompt(prompt)["role"]


def _load_native_task_manifest(prompt: str) -> dict[str, Any]:
    try:
        document = json.loads(NATIVE_TASK_MANIFEST_PATH.read_text(encoding="utf-8"))
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
        "path": NATIVE_TASK_MANIFEST_PATH.name,
        "probe_contract": probe_contract,
        "entry": entry,
    }


def _resolve_native_task_manifest(prompt: str) -> dict[str, Any]:
    semantics = _parse_native_task_prompt(prompt)
    manifest = _load_native_task_manifest(prompt)
    entry = manifest["entry"]
    if any(entry[field] != semantics[field] for field in ("role", "intent", "evidence")):
        raise RuntimeError("native task manifest disagrees with prompt grammar")
    return {
        **manifest,
        "derived_native_role": semantics["role"],
        "prompt_semantics": semantics,
    }


def _native_role_evidence_key(
    model_fingerprint: str,
    prompt_sha256: str,
    capture_sha256: str,
) -> str:
    return _sha_bytes(
        _canonical(
            {
                "schema": ROLE_EVIDENCE_SCHEMA,
                "model_fingerprint": model_fingerprint,
                "prompt_sha256": prompt_sha256,
                "capture_sha256": capture_sha256,
            }
        )
    )


def _normalize_role_manifest(rows: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for item in rows:
        row = dict(item)
        key = _native_role_evidence_key(
            str(row["model_fingerprint"]),
            str(row["prompt_sha256"]),
            str(row["capture_sha256"]),
        )
        prior = normalized.get(key)
        if prior is not None and prior != row:
            raise RuntimeError("native role manifest has conflicting duplicate")
        normalized[key] = row
    return {key: normalized[key] for key in sorted(normalized)}




def _safe(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise RuntimeError(f"linked artifact escapes run root: {relative}") from error
    return path


def _read_f32(path: Path, descriptor: Mapping[str, Any]) -> np.ndarray:
    raw = path.read_bytes()
    if len(raw) != int(descriptor["bytes"]) or len(raw) != int(descriptor["elements"]) * 4:
        raise RuntimeError(f"float32 size mismatch for {path}")
    if _sha_bytes(raw) != descriptor.get("sha256"):
        raise RuntimeError(f"float32 digest mismatch for {path}")
    values = np.frombuffer(raw, dtype="<f4").copy()
    if not bool(np.isfinite(values).all()):
        raise RuntimeError(f"non-finite values in {path}")
    return values


def _model(value: Mapping[str, Any]) -> ModelIdentity:
    data = {key: item for key, item in value.items() if key != "schema"}
    return ModelIdentity(**data)


def _verify_capture_site_bundle(
    root: Path,
    value: Mapping[str, Any],
    model: ModelIdentity,
    prompt: Mapping[str, Any],
) -> dict[str, Any]:
    contract = value.get("capture_contract")
    sites = value.get("capture_sites")
    if not isinstance(contract, Mapping) or not isinstance(sites, Mapping):
        raise RuntimeError("native capture omits its site bundle contract")
    selector_abi = contract.get("selector_abi")
    expected_selector_abi = {name: kind for name, (kind, _layer_mode) in CAPTURE_KINDS.items()}
    if selector_abi != expected_selector_abi:
        raise RuntimeError("native capture selector ABI differs from the declared contract")
    if int(contract.get("layer_count", -1)) != model.layer_count:
        raise RuntimeError("native capture layer count differs from model identity")
    if int(contract.get("shape_slots", -1)) != 4:
        raise RuntimeError("native capture shape ABI does not expose four slots")
    if contract.get("attention_probabilities_optional") is not True:
        raise RuntimeError("native capture does not declare attention-probability optionality")
    if set(sites) != set(CAPTURE_KINDS):
        raise RuntimeError("native capture site names are incomplete or unexpected")
    token_count = int(prompt["token_count"])
    expected_vector_shape = [model.embedding_width, token_count]
    directory = root / "native-capture"
    summaries: dict[str, Any] = {}
    for name, (kind, layer_mode) in CAPTURE_KINDS.items():
        rows = sites[name]
        if not isinstance(rows, list):
            raise RuntimeError(f"capture site {name} is not a list")
        expected_layers = [None] if layer_mode is None else list(range(model.layer_count))
        seen_layers: set[int | None] = set()
        digests: list[str] = []
        shapes: list[tuple[int, ...]] = []
        for descriptor in rows:
            if not isinstance(descriptor, Mapping):
                raise RuntimeError(f"capture site {name} contains a malformed descriptor")
            capture_layer = descriptor.get("layer")
            if layer_mode is None:
                if capture_layer is not None:
                    raise RuntimeError(f"global capture site {name} has a layer")
                normalized_layer: int | None = None
            else:
                if not isinstance(capture_layer, int) or not 0 <= capture_layer < model.layer_count:
                    raise RuntimeError(f"capture site {name} has an invalid layer")
                normalized_layer = int(capture_layer)
            if normalized_layer in seen_layers:
                raise RuntimeError(f"capture site {name} repeats layer {normalized_layer}")
            seen_layers.add(normalized_layer)
            if int(descriptor.get("kind", -1)) != kind or descriptor.get("site") != name:
                raise RuntimeError(f"capture site {name} descriptor identity is inconsistent")
            shape_value = descriptor.get("shape")
            if not isinstance(shape_value, list) or not 1 <= len(shape_value) <= 4:
                raise RuntimeError(f"capture site {name} has an invalid shape")
            shape = tuple(int(extent) for extent in shape_value)
            if any(extent <= 0 for extent in shape):
                raise RuntimeError(f"capture site {name} has a non-positive shape")
            if descriptor.get("rank") != len(shape) or descriptor.get("dtype") != "float32":
                raise RuntimeError(f"capture site {name} dtype/rank metadata is inconsistent")
            if descriptor.get("endianness") != "little" or descriptor.get("order") != "C":
                raise RuntimeError(f"capture site {name} storage metadata is inconsistent")
            if name == "attention_probs":
                if len(shape) != 3 or shape[1] != token_count:
                    raise RuntimeError(f"capture site {name} shape is not [n_kv, tokens, n_head]")
            elif name == "head_output":
                if len(shape) != 1:
                    raise RuntimeError("head output capture is not a one-dimensional logit vector")
            elif list(shape) != expected_vector_shape:
                raise RuntimeError(f"capture site {name} shape is not [embedding_width, token_count]")
            relative_path = f"native-capture/{descriptor.get('path', '')}"
            linked = _safe(root, str(relative_path))
            if linked.parent != directory.resolve():
                raise RuntimeError(f"capture site {name} does not link a flat native-capture artifact")
            values = _read_f32(linked, descriptor)
            if values.size != math.prod(shape):
                raise RuntimeError(f"capture site {name} shape does not match its raw element count")
            digests.append(str(descriptor["sha256"]))
            shapes.append(shape)
        if layer_mode is None and seen_layers != {None}:
            raise RuntimeError(f"global capture site {name} is missing its single tensor")
        if layer_mode is not None and name != "attention_probs" and seen_layers != set(expected_layers):
            raise RuntimeError(f"capture site {name} does not cover every model layer")
        summaries[name] = {
            "requested_layers": model.layer_count if layer_mode is not None else 1,
            "available_layers": len(rows),
            "layers": sorted(layer for layer in seen_layers if layer is not None),
            "optional": name == "attention_probs",
            "shapes": [list(shape) for shape in sorted(set(shapes))],
            "sha256": sorted(digests),
        }
    return summaries


def _verify_capture(root: Path, value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema") != CAPTURE_SCHEMA or value.get("verdict") != "PASS":
        raise RuntimeError("native capture receipt is not a passing capture")
    model = _model(value["model"])
    if value.get("model_fingerprint") != model.fingerprint:
        raise RuntimeError("capture model fingerprint mismatch")
    if tuple(model.hook_sites) != tuple(CAPTURE_KINDS):
        raise RuntimeError("capture model identity does not enumerate the site bundle")
    prompt = value.get("prompt")
    hook = value.get("hook")
    trace_data = value.get("trace")
    capture_sites = value.get("capture_sites")
    if (
        not isinstance(prompt, Mapping)
        or not isinstance(hook, Mapping)
        or not isinstance(trace_data, Mapping)
        or not isinstance(capture_sites, Mapping)
    ):
        raise RuntimeError("capture receipt omits prompt, hook, trace, or site bundle")
    site_summary = _verify_capture_site_bundle(root, value, model, prompt)
    if value.get("capture_summary") != site_summary:
        raise RuntimeError("capture summary is not a faithful site-bundle reduction")
    directory = root / "native-capture"
    off_descriptor = value.get("capture_off")
    on_descriptor = value.get("capture_on")
    hidden_descriptor = value.get("hidden_state")
    if not isinstance(off_descriptor, Mapping) or not isinstance(on_descriptor, Mapping) or not isinstance(hidden_descriptor, Mapping):
        raise RuntimeError("capture receipt omits raw capture descriptors")

    def linked(descriptor: Mapping[str, Any]) -> Path:
        path = _safe(root, f"native-capture/{descriptor['path']}")
        if path.parent != directory.resolve():
            raise RuntimeError("capture descriptor does not link a flat native-capture artifact")
        return path

    off_path = linked(off_descriptor)
    on_path = linked(on_descriptor)
    hidden_path = linked(hidden_descriptor)
    off = _read_f32(off_path, off_descriptor)
    on = _read_f32(on_path, on_descriptor)
    hidden = _read_f32(hidden_path, hidden_descriptor)
    if off.size != on.size or off.size <= 1:
        raise RuntimeError("capture logits widths are invalid")
    if hidden.size != model.embedding_width or hidden_descriptor.get("shape") != [model.embedding_width]:
        raise RuntimeError("final hidden-state capture shape is invalid")
    head_output_rows = capture_sites.get("head_output")
    layer_input_rows = capture_sites.get("layer_input")
    if not isinstance(head_output_rows, list) or not isinstance(layer_input_rows, list) or len(head_output_rows) != 1:
        raise RuntimeError("capture site bundle has invalid global or layer-input rows")
    head_output_descriptor = head_output_rows[0]
    if not isinstance(head_output_descriptor, Mapping):
        raise RuntimeError("head-output capture descriptor is malformed")
    head_output = _read_f32(
        linked(head_output_descriptor),
        head_output_descriptor,
    )
    if not np.array_equal(head_output, on):
        raise RuntimeError("head-output site does not reproduce the public logits")
    layer_index = int(trace_data["layer"])
    layer_descriptor = next(
        (row for row in layer_input_rows if isinstance(row, Mapping) and row.get("layer") == layer_index),
        None,
    )
    if not isinstance(layer_descriptor, Mapping):
        raise RuntimeError("trace layer is absent from the layer-input bundle")
    layer_values = _read_f32(linked(layer_descriptor), layer_descriptor)
    token_count = int(prompt["token_count"])
    offset = (token_count - 1) * model.embedding_width
    if not np.array_equal(layer_values[offset : offset + model.embedding_width], hidden):
        raise RuntimeError("final hidden-state artifact is not the selected layer-input row")
    trace = ActivationTrace(
        model=model,
        site=str(trace_data["site"]),
        layer=layer_index,
        sequence_id=str(trace_data["sequence_id"]),
        position=int(trace_data["position"]),
        values=hidden,
        token_id=trace_data.get("token_id"),
        expected_token_id=trace_data.get("expected_token_id"),
        logits=on,
        adapter_key=trace_data.get("adapter_key"),
        prompt_sha256=prompt.get("sha256"),
        capture_sha256=hidden_descriptor.get("sha256"),
        source_id=str(hidden_path),
        native_role=trace_data.get("native_role"),
        role_attestation=trace_data.get("role_attestation"),
    )
    if trace.native_role is None or trace.role_attestation is None:
        raise RuntimeError("native capture omits its role attestation")
    if trace.role_attestation != trace.role_attestation_for(trace.native_role):
        raise RuntimeError("native capture role attestation mismatch")
    if trace.trace_sha256 != trace_data.get("trace_sha256"):
        raise RuntimeError("capture trace digest mismatch")
    if str(prompt.get("sha256")) != _sha_bytes(str(prompt["utf8"]).encode("utf-8")):
        raise RuntimeError("prompt digest mismatch")
    if int(prompt["final_token_index"]) != int(hook["token_row"]) or int(prompt["final_token_index"]) != token_count - 1:
        raise RuntimeError("capture token-row provenance mismatch")
    max_delta = float(np.max(np.abs(on.astype(np.float64) - off.astype(np.float64))))
    order_off = np.argsort(off)[::-1][:16].tolist()
    order_on = np.argsort(on)[::-1][:16].tolist()
    parity = value.get("parity")
    if not isinstance(parity, Mapping):
        raise RuntimeError("capture parity control is missing")
    if max_delta != float(parity["max_abs_logit_difference"]):
        raise RuntimeError("capture parity delta was not recomputed faithfully")
    if max_delta > float(parity["max_abs_logit_difference_bound"]):
        raise RuntimeError("capture parity exceeds its declared bound")
    if order_off != order_on or int(np.argmax(off)) != int(np.argmax(on)) or parity.get("pass") is not True:
        raise RuntimeError("capture parity control failed")
    return {
        "model_fingerprint": model.fingerprint,
        "trace_sha256": trace.trace_sha256,
        "hidden_sha256": hidden_descriptor["sha256"],
        "logits_sha256": on_descriptor["sha256"],
        "prompt_sha256": prompt["sha256"],
        "adapter_key": trace.adapter_key,
        "native_role": trace.native_role,
        "role_attestation": trace.role_attestation,
        "top_token_id": int(np.argmax(on)),
        "max_abs_logit_difference": max_delta,
        "site_summary": site_summary,
    }
def _verify_trial(root: Path, relative_receipt: str) -> tuple[dict[str, Any], OutputSnapshot]:
    receipt_path = _safe(root, relative_receipt)
    value = json.loads(receipt_path.read_text(encoding="utf-8"))
    if value.get("schema") != GRAPH_SCHEMA or value.get("verdict") != "PASS":
        raise RuntimeError(f"graph trial is not passing: {relative_receipt}")
    model = _model(value["model"])
    if value.get("model_fingerprint") != model.fingerprint:
        raise RuntimeError(f"graph model fingerprint mismatch: {relative_receipt}")
    directory = receipt_path.parent
    predecessor = value.get("state_predecessor")
    configuration = value.get("configuration")
    graph = value.get("graph")
    snapshot_data = value.get("output_snapshot")
    steps = value.get("logit_steps")
    if (
        not isinstance(predecessor, Mapping)
        or not isinstance(configuration, Mapping)
        or not isinstance(graph, Mapping)
        or not isinstance(snapshot_data, Mapping)
        or not isinstance(steps, list)
        or not steps
    ):
        raise RuntimeError(f"graph trial omits its execution ledger: {relative_receipt}")
    predecessor_path = (directory / str(predecessor["path"])).resolve()
    try:
        predecessor_relative = predecessor_path.relative_to(root.resolve())
    except ValueError as error:
        raise RuntimeError(f"graph predecessor escapes the run root: {relative_receipt}") from error
    _read_f32(_safe(root, str(predecessor_relative)), predecessor)
    continuation = configuration.get("continuation_tokens")
    if not isinstance(continuation, list):
        raise RuntimeError(f"graph continuation ledger is malformed: {relative_receipt}")
    decode_steps = 1 + len(continuation)
    if int(configuration.get("decode_steps", -1)) != decode_steps or len(steps) != decode_steps:
        raise RuntimeError(f"graph continuation step count is inconsistent: {relative_receipt}")
    if graph.get("executed") is not True or snapshot_data.get("executed") is not True or snapshot_data.get("route") != "graph-native":
        raise RuntimeError(f"graph trial is not graph-native: {relative_receipt}")
    if int(graph.get("decode_steps", -1)) != decode_steps or int(graph.get("qwen_forward_passes", -1)) != decode_steps:
        raise RuntimeError(f"graph forward count is not the decoded-step count: {relative_receipt}")
    prompt_tokens = int(configuration["prompt_tokens"])
    final_values: np.ndarray | None = None
    for step, descriptor in enumerate(steps):
        if not isinstance(descriptor, Mapping):
            raise RuntimeError(f"graph step descriptor is malformed: {relative_receipt}")
        if int(descriptor.get("step", -1)) != step:
            raise RuntimeError(f"graph step index is not contiguous: {relative_receipt}")
        if int(descriptor.get("position", -1)) != prompt_tokens - 1 + step:
            raise RuntimeError(f"graph step position is inconsistent: {relative_receipt}")
        if step > 0 and int(descriptor.get("input_token_id", -1)) != int(continuation[step - 1]):
            raise RuntimeError(f"graph continuation token provenance is inconsistent: {relative_receipt}")
        linked = (directory / str(descriptor["path"])).resolve()
        try:
            linked.relative_to(directory.resolve())
        except ValueError as error:
            raise RuntimeError(f"graph step escapes its receipt directory: {relative_receipt}") from error
        values = _read_f32(linked, descriptor)
        if int(np.argmax(values)) != int(descriptor["top_token_id"]):
            raise RuntimeError(f"graph step top token mismatch: {relative_receipt}")
        if step == len(steps) - 1:
            final_values = values
    logits_descriptor = value.get("logits")
    if not isinstance(logits_descriptor, Mapping) or final_values is None:
        raise RuntimeError(f"graph trial omits final logits: {relative_receipt}")
    logits_path = (directory / str(logits_descriptor["path"])).resolve()
    logits = _read_f32(logits_path, logits_descriptor)
    if (
        _sha_bytes(logits_path.read_bytes()) != logits_descriptor.get("sha256")
        or not np.array_equal(logits, final_values)
    ):
        raise RuntimeError(f"graph final logits do not match the step ledger: {relative_receipt}")
    state_descriptor = value.get("state_successor")
    if not isinstance(state_descriptor, Mapping):
        raise RuntimeError(f"graph trial omits state successor: {relative_receipt}")
    state_path = (directory / str(state_descriptor["path"])).resolve()
    state = _read_f32(state_path, state_descriptor)
    if _sha_bytes(state_path.read_bytes()) != state_descriptor.get("sha256"):
        raise RuntimeError(f"graph state successor digest mismatch: {relative_receipt}")
    if state.nbytes > MAX_STATE_BYTES or logits.size <= 1:
        raise RuntimeError(f"graph raw bounds are invalid: {relative_receipt}")
    if int(np.argmax(logits)) != int(logits_descriptor["top_token_id"]):
        raise RuntimeError(f"graph top token mismatch: {relative_receipt}")
    displacement = int(configuration["displacement"])
    substitute = float(configuration["substitute"])
    expected_model_reads = 0 if displacement >= 6 else decode_steps
    expected_field_reads = decode_steps if displacement >= 6 else 0
    expected_lm_computed = 0 if displacement >= 6 else decode_steps
    expected_lm_skipped = decode_steps if displacement >= 6 else 0
    if (
        int(graph["model_logits_read"]) != expected_model_reads
        or int(graph["field_logits_read"]) != expected_field_reads
        or int(graph["lm_head_rows_computed"]) != expected_lm_computed
        or int(graph["lm_head_rows_skipped"]) != expected_lm_skipped
    ):
        raise RuntimeError(f"graph ownership counters do not match its displacement: {relative_receipt}")
    field_width = int(graph.get("qi_state_field_width", -1))
    row_width = int(graph.get("qi_state_row_width", -1))
    if field_width < 0 or row_width < 0 or field_width > row_width:
        raise RuntimeError(f"graph Qi ownership widths are invalid: {relative_receipt}")
    if int(graph.get("qi_state_field_bytes", -1)) != field_width * 4:
        raise RuntimeError(f"graph field ownership bytes are inconsistent: {relative_receipt}")
    if int(graph.get("qi_state_remaining_model_bytes", -1)) != (row_width - field_width) * 4:
        raise RuntimeError(f"graph remaining ownership bytes are inconsistent: {relative_receipt}")
    expected_write_owner = (
        "field"
        if field_width > 0
        else "suppressed-model"
        if displacement >= 3
        else "model"
    )
    if graph.get("qi_state_write_owner") != expected_write_owner:
        raise RuntimeError(f"graph state-write owner is inconsistent: {relative_receipt}")
    expected_tail_owner = "model" if 0 < field_width < row_width else "none"
    if graph.get("qi_state_tail_owner") != expected_tail_owner:
        raise RuntimeError(f"graph state-tail owner is inconsistent: {relative_receipt}")
    if displacement >= 3 and substitute > 0.0 and (field_width <= 0 or row_width <= 0):
        raise RuntimeError(f"graph field substitution did not report owned state channels: {relative_receipt}")
    output_position = int(configuration.get("output_position", prompt_tokens - 1 + len(continuation)))
    snapshot = OutputSnapshot(
        model=model,
        site=str(configuration["site"]),
        layer=int(configuration["layer"]),
        sequence_id=str(configuration["sequence_id"]),
        position=output_position,
        prompt_sha256=str(configuration["prompt_sha256"]),
        logits=logits,
        route="graph-native",
        executed=True,
        capture_id=str(snapshot_data["capture_id"]),
    )
    if snapshot.as_dict() != snapshot_data:
        raise RuntimeError(f"graph output snapshot mismatch: {relative_receipt}")
    return value, snapshot


def _verify_native_field(root: Path, relative_result: str) -> dict[str, Any]:
    path = _safe(root, relative_result)
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("status") != "staged" or value.get("receipt", {}).get("verdict") != "PASS":
        raise RuntimeError(f"field-only result is not passing: {relative_result}")
    ownership = value.get("ownership")
    if not isinstance(ownership, Mapping):
        raise RuntimeError("field-only result omits ownership")
    if ownership.get("output_owner") != "field" or ownership.get("sampler_owner") != "field" or ownership.get("logit_owner") != "field":
        raise RuntimeError("field-only result does not report field ownership")
    if ownership.get("qwen_forward_passes") != 0 or ownership.get("model_logits_read") != 0 or ownership.get("silent_native_fallback") is not False:
        raise RuntimeError("field-only result reports native work or fallback")
    successor = value.get("state_successor")
    if not isinstance(successor, Mapping):
        raise RuntimeError("field-only result omits state successor")
    state_path = Path(str(successor["path"])).resolve()
    try:
        state_path.relative_to(root.resolve())
    except ValueError as error:
        raise RuntimeError("field-only state successor escapes run root") from error
    raw = state_path.read_bytes()
    if len(raw) != int(successor["bytes"]) or _sha_bytes(raw) != successor.get("sha256"):
        raise RuntimeError("field-only state successor digest mismatch")
    return {
        "mode": value.get("mode"),
        "output_owner": ownership.get("output_owner"),
        "sampler_owner": ownership.get("sampler_owner"),
        "logit_owner": ownership.get("logit_owner"),
        "qwen_forward_passes": ownership.get("qwen_forward_passes"),
        "state_sha256": successor.get("sha256"),
        "output_sha256": _sha_bytes(str(value.get("output", "")).encode("utf-8")),
    }

def _verify_native_behavior_probe_artifact(
    root: Path,
    behavior_probe: Mapping[str, Any],
    source_probe: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        behavior_probe.get("schema") != "cassi.native-role-behavior-probe.v2"
        or behavior_probe.get("probe_id") != source_probe["probe_id"]
        or behavior_probe.get("prompt_sha256") != _sha_bytes(str(source_probe["prompt"]).encode("utf-8"))
        or behavior_probe.get("expected_label") != source_probe["expected_label"]
        or behavior_probe.get("contrast_label") != source_probe["contrast_label"]
        or behavior_probe.get("expected_outcome") != source_probe["expected_outcome"]
    ):
        raise RuntimeError("native role behavior probe source binding mismatch")
    probe_path = _safe(root, str(behavior_probe["path"]))
    probe_raw = probe_path.read_bytes()
    if (
        len(probe_raw) != int(behavior_probe["bytes"])
        or _sha_bytes(probe_raw) != behavior_probe["sha256"]
        or len(probe_raw) % 4 != 0
        or int(behavior_probe["elements"]) != len(probe_raw) // 4
    ):
        raise RuntimeError("native role behavior probe artifact digest mismatch")
    probe_values = np.frombuffer(probe_raw, dtype="<f4")
    expected_token_id = behavior_probe.get("expected_token_id")
    contrast_token_id = behavior_probe.get("contrast_token_id")
    if (
        isinstance(expected_token_id, bool)
        or not isinstance(expected_token_id, int)
        or isinstance(contrast_token_id, bool)
        or not isinstance(contrast_token_id, int)
        or expected_token_id == contrast_token_id
        or not 0 <= expected_token_id < len(probe_values)
        or not 0 <= contrast_token_id < len(probe_values)
    ):
        raise RuntimeError("native role behavior probe token IDs are invalid")
    expected_logit = float(probe_values[expected_token_id])
    contrast_logit = float(probe_values[contrast_token_id])
    margin = expected_logit - contrast_logit
    expected_label_won = bool(expected_logit > contrast_logit)
    expected_rank = int(np.count_nonzero(probe_values > expected_logit)) + 1
    control_passed = expected_label_won == (source_probe["expected_outcome"] == "pass")
    if (
        not math.isclose(expected_logit, float(behavior_probe["expected_logit"]), rel_tol=0.0, abs_tol=1.0e-7)
        or not math.isclose(contrast_logit, float(behavior_probe["contrast_logit"]), rel_tol=0.0, abs_tol=1.0e-7)
        or not math.isclose(margin, float(behavior_probe["margin"]), rel_tol=0.0, abs_tol=1.0e-7)
        or int(behavior_probe["top_token_id"]) != int(np.argmax(probe_values))
        or int(behavior_probe["expected_rank"]) != expected_rank
        or behavior_probe.get("expected_label_won") is not expected_label_won
        or behavior_probe.get("control_passed") is not True
        or not control_passed
    ):
        raise RuntimeError("native role behavior probe did not satisfy its outcome contract")
    return {
        "probe_id": str(behavior_probe["probe_id"]),
        "margin": margin,
        "expected_rank": expected_rank,
        "expected_label_won": expected_label_won,
        "control_passed": True,
    }


def _verify_native_behavior_probe_matrix(
    root: Path,
    behavior_probes: Mapping[str, Any],
    task_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if behavior_probes.get("schema") != "cassi.native-role-behavior-probe-matrix.v1":
        raise RuntimeError("native role behavior probe matrix schema mismatch")
    required_ids = list(task_manifest["probe_contract"]["required_probe_ids"])
    negative_ids = list(task_manifest["probe_contract"]["negative_control_ids"])
    if (
        behavior_probes.get("probe_ids") != required_ids
        or behavior_probes.get("negative_control_ids") != negative_ids
        or not isinstance(behavior_probes.get("probes"), list)
    ):
        raise RuntimeError("native role behavior probe matrix contract mismatch")
    source_probes = {
        probe["probe_id"]: probe
        for probe in task_manifest["entry"]["behavior_probes"]
    }
    recorded_probes = behavior_probes["probes"]
    if len(recorded_probes) != len(required_ids):
        raise RuntimeError("native role behavior probe matrix count mismatch")
    verified: list[dict[str, Any]] = []
    for probe_id, recorded in zip(required_ids, recorded_probes):
        if not isinstance(recorded, Mapping) or probe_id not in source_probes:
            raise RuntimeError("native role behavior probe matrix row mismatch")
        verified.append(
            _verify_native_behavior_probe_artifact(
                root,
                recorded,
                source_probes[probe_id],
            )
        )
    if (
        _sha_bytes(_canonical(recorded_probes)) != behavior_probes.get("result_sha256")
        or behavior_probes.get("all_controls_passed") is not True
        or not all(item["control_passed"] for item in verified)
    ):
        raise RuntimeError("native role behavior probe matrix digest or control mismatch")
    negative_verified = [
        item for item in verified if item["probe_id"] in negative_ids
    ]
    if not negative_verified or not all(
        item["expected_label_won"] is False for item in negative_verified
    ):
        raise RuntimeError("native role negative control did not lose as designed")
    return {
        "result_sha256": str(behavior_probes["result_sha256"]),
        "probe_ids": required_ids,
        "negative_control_ids": negative_ids,
        "all_controls_passed": True,
        "negative_control_fired": True,
        "probes": verified,
    }


def verify(run_dir: Path) -> dict[str, Any]:
    root = Path(run_dir).resolve()
    receipt_path = root / "native-program-receipt.json"
    body = json.loads(receipt_path.read_text(encoding="utf-8"))
    if body.get("schema") != "cassi.universal-llm-interpreter-native-program.v2" or body.get("status") != "PASS":
        raise RuntimeError("top-level native program receipt schema or status is invalid")
    expected_digest = body.get("content_sha256")
    digest_body = dict(body)
    digest_body.pop("content_sha256", None)
    if _sha_bytes(_canonical(digest_body)) != expected_digest:
        raise RuntimeError("top-level content digest mismatch")
    capture = _verify_capture(root, body["native_capture"])
    role_authentication = body.get("role_authentication")
    prompt_data = body.get("prompt")
    capture_receipt = body.get("native_capture")
    if (
        not isinstance(role_authentication, Mapping)
        or not isinstance(prompt_data, Mapping)
        or not isinstance(capture_receipt, Mapping)
        or not isinstance(capture_receipt.get("trace"), Mapping)
    ):
        raise RuntimeError("top-level receipt omits native role authentication")
    if role_authentication.get("schema") != "cassi.native-role-authentication.v1":
        raise RuntimeError("native role authentication schema mismatch")
    if role_authentication.get("semantic_source") != NATIVE_ROLE_SEMANTIC_SOURCE:
        raise RuntimeError("native role semantic source mismatch")
    prompt_text = prompt_data.get("utf8")
    if not isinstance(prompt_text, str):
        raise RuntimeError("native prompt text is missing")
    native_task_manifest = _resolve_native_task_manifest(prompt_text)
    derived_native_role = native_task_manifest["derived_native_role"]
    role_prompt = role_authentication.get("prompt")
    if (
        not isinstance(role_prompt, Mapping)
        or role_prompt.get("sha256") != prompt_data.get("sha256")
        or role_prompt.get("derived_native_role") != derived_native_role
    ):
        raise RuntimeError("native role prompt derivation mismatch")
    if capture["prompt_sha256"] != prompt_data.get("sha256"):
        raise RuntimeError("native role prompt digest is not capture-bound")
    if capture["native_role"] != derived_native_role:
        raise RuntimeError("native role claim does not match native prompt semantics")
    if role_authentication.get("task_manifest") != native_task_manifest:
        raise RuntimeError("native task manifest receipt is not source-bound")
    if role_authentication.get("declared_native_role") != derived_native_role:
        raise RuntimeError("native role declaration does not match native prompt semantics")
    behavior_probes = role_authentication.get("behavior_probes")
    if not isinstance(behavior_probes, Mapping):
        raise RuntimeError("native role behavior probe matrix is missing")
    probe_result = _verify_native_behavior_probe_matrix(
        root,
        behavior_probes,
        native_task_manifest,
    )
    manifest_rows = role_authentication.get("native_role_manifest")
    if not isinstance(manifest_rows, list) or not manifest_rows:
        raise RuntimeError("native role manifest is missing")
    if any(not isinstance(row, Mapping) for row in manifest_rows):
        raise RuntimeError("native role manifest rows are malformed")
    normalized_manifest = _normalize_role_manifest(manifest_rows)
    manifest_digest = _sha_bytes(_canonical(normalized_manifest))
    expected_manifest_row = {
        "model_fingerprint": capture["model_fingerprint"],
        "prompt_sha256": capture["prompt_sha256"],
        "capture_sha256": capture["hidden_sha256"],
        "native_role": derived_native_role,
        "semantic_source": NATIVE_ROLE_SEMANTIC_SOURCE,
        "task_manifest_id": native_task_manifest["entry"]["task_id"],
        "task_manifest_sha256": native_task_manifest["manifest_sha256"],
        "task_manifest_source": native_task_manifest["semantic_source"],
        "behavior_probe_matrix_sha256": probe_result["result_sha256"],
        "behavior_probe_ids": probe_result["probe_ids"],
        "behavior_probe_negative_control_ids": probe_result["negative_control_ids"],
    }
    if list(normalized_manifest.values()) != [expected_manifest_row]:
        raise RuntimeError("native role manifest does not describe the captured native task")
    state_role_gate = role_authentication.get("state_role_gate")
    if (
        not isinstance(state_role_gate, Mapping)
        or state_role_gate.get("native_role_manifest_sha256") != manifest_digest
        or state_role_gate.get("native_role_manifest_entry_count") != 1
    ):
        raise RuntimeError("native role manifest digest is not recorded by the field gate")
    registry = role_authentication.get("role_registry")
    if not isinstance(registry, Mapping):
        raise RuntimeError("native role registry is missing")
    descriptor = registry.get(capture["adapter_key"])
    if (
        not isinstance(descriptor, Mapping)
        or descriptor.get("semantic_role") != derived_native_role
        or descriptor.get("model_fingerprint") != capture["model_fingerprint"]
    ):
        raise RuntimeError("native role registry does not bind the captured coordinate")
    tamper_checks = role_authentication.get("tamper_checks")
    semantic_tamper = (
        tamper_checks.get("semantic_misbinding")
        if isinstance(tamper_checks, Mapping)
        else None
    )
    unregistered_tamper = (
        tamper_checks.get("unregistered_evidence")
        if isinstance(tamper_checks, Mapping)
        else None
    )
    if (
        not isinstance(semantic_tamper, Mapping)
        or semantic_tamper.get("error") != "native role evidence mismatch"
        or not isinstance(unregistered_tamper, Mapping)
        or unregistered_tamper.get("error") != "unregistered native role evidence"
        or not isinstance(tamper_checks, Mapping)
        or any(
            not isinstance(row, Mapping)
            or row.get("rejected") is not True
            or row.get("state_unchanged") is not True
            for row in tamper_checks.values()
        )
    ):
        raise RuntimeError("native role tamper controls did not fire")
    field_seed = _verify_native_field(root, "field-seed/result.json")
    field_output = _verify_native_field(root, "field-owned-emission/result.json")
    graph_native = body.get("graph_native")
    if not isinstance(graph_native, Mapping):
        raise RuntimeError("top-level receipt omits graph-native evidence")
    paths = graph_native["receipt_paths"]
    trial_names = (
        "baseline_field_output",
        "lesion_field_state",
        "donor_baseline_state",
        "recurrent_model",
        "recurrent_suppressed",
        "recurrent_field",
    )
    trials: dict[str, tuple[dict[str, Any], OutputSnapshot]] = {
        name: _verify_trial(root, str(paths[name])) for name in trial_names
    }
    base_value, base_snapshot = trials["baseline_field_output"]
    lesion_value, lesion_snapshot = trials["lesion_field_state"]
    donor_value, donor_snapshot = trials["donor_baseline_state"]
    recurrent_model_value, recurrent_model_snapshot = trials["recurrent_model"]
    recurrent_suppressed_value, recurrent_suppressed_snapshot = trials["recurrent_suppressed"]
    recurrent_field_value, recurrent_field_snapshot = trials["recurrent_field"]
    field_pair = CausalPair(
        baseline=base_snapshot,
        lesion=lesion_snapshot,
        donor=donor_snapshot,
        intervention_kind="field-owned-lm-head-state",
    ).assess()
    recurrent_pair = CausalPair(
        baseline=recurrent_model_snapshot,
        lesion=recurrent_field_snapshot,
        intervention_kind="field-owned-recurrent-state-replacement",
    ).assess()
    recurrent_control_pair = CausalPair(
        baseline=recurrent_suppressed_snapshot,
        lesion=recurrent_field_snapshot,
        intervention_kind="suppressed-model-vs-field-recurrent-state",
    ).assess()

    def compare_recorded(actual: Mapping[str, Any], recorded: Mapping[str, Any], label: str) -> None:
        for key in ("status", "graph_native_executed", "decision_flip", "donor_restores_baseline_decision", "changed_beyond_tolerance"):
            if key in recorded and actual.get(key) != recorded[key]:
                raise RuntimeError(f"{label} causal pair field {key} mismatch")

    compare_recorded(field_pair, graph_native["field_owned_pair"], "field")
    compare_recorded(recurrent_pair, graph_native["recurrent_pair"], "recurrent")
    compare_recorded(recurrent_control_pair, graph_native["recurrent_control_pair"], "recurrent-control")
    base_graph = base_value["graph"]
    lesion_graph = lesion_value["graph"]
    donor_graph = donor_value["graph"]
    decode_steps = int(base_graph["decode_steps"])
    if not (
        base_graph["lm_head_owner"] == "field"
        and base_graph["model_logits_read"] == 0
        and base_graph["field_logits_read"] == decode_steps
        and base_graph["lm_head_rows_skipped"] == decode_steps
        and lesion_graph["lm_head_owner"] == "field"
        and donor_graph["lm_head_owner"] == "field"
    ):
        raise RuntimeError("graph field-owned output counters are inconsistent")
    if (
        recurrent_model_value["configuration"]["displacement"] != 0
        or recurrent_suppressed_value["configuration"]["displacement"] != 3
        or recurrent_field_value["configuration"]["displacement"] != 3
        or recurrent_suppressed_value["configuration"]["substitute"] != 0.0
        or recurrent_field_value["configuration"]["substitute"] <= 0.0
    ):
        raise RuntimeError("recurrent ownership arm labels are inconsistent")
    recurrent_model_graph = recurrent_model_value["graph"]
    recurrent_suppressed_graph = recurrent_suppressed_value["graph"]
    recurrent_field_graph = recurrent_field_value["graph"]
    if not (
        recurrent_model_graph["qi_state_write_owner"] == "model"
        and recurrent_suppressed_graph["qi_state_write_owner"] == "suppressed-model"
        and recurrent_field_graph["qi_state_write_owner"] == "field"
        and recurrent_field_graph["qi_state_field_width"] > 0
        and recurrent_field_graph["qi_state_field_bytes"] > 0
        and recurrent_field_graph["qi_state_remaining_model_bytes"] >= 0
    ):
        raise RuntimeError("recurrent Qi state ownership counters are inconsistent")
    if graph_native.get("continuation_tokens") != recurrent_field_value["configuration"]["continuation_tokens"]:
        raise RuntimeError("top-level continuation ledger does not match recurrent trial")
    interpreter = body["interpreter"]
    if interpreter["query"]["status"] != "field-owned" or interpreter["restart_query"]["status"] != "field-owned":
        raise RuntimeError("interpreter did not deliver a field-owned query")
    if interpreter["query"]["native_fallback"] is not False or interpreter["restart_query"]["native_fallback"] is not False:
        raise RuntimeError("interpreter query reports fallback")
    if interpreter["state"]["after_learning"] != interpreter["state"]["restarted"]:
        raise RuntimeError("interpreter restart fingerprint changed")
    checks = {
        "top_digest": True,
        "native_role_semantics_recomputed": True,
        "native_task_manifest_source_bound": True,
        "native_role_behavior_probes_recomputed": probe_result["all_controls_passed"],
        "native_role_negative_control_recomputed": probe_result["negative_control_fired"],
        "capture_rehashed": True,
        "capture_parity": capture["max_abs_logit_difference"] <= 1.0e-6,
        "field_seed_rehashed": True,
        "field_emission_rehashed": True,
        "field_emission_ownership": field_output["output_owner"] == "field" and field_output["sampler_owner"] == "field",
        "graph_field_pair_recomputed": field_pair["status"] == "causal-effect" and field_pair["graph_native_executed"] is True,
        "graph_donor_recomputed": field_pair["donor_restores_baseline_decision"] is True,
        "graph_recurrent_pair_recomputed": recurrent_pair["status"] == "causal-effect" and recurrent_pair["graph_native_executed"] is True,
        "graph_recurrent_control_recomputed": recurrent_control_pair["status"] == "causal-effect" and recurrent_control_pair["graph_native_executed"] is True,
        "graph_recurrent_ownership_recomputed": recurrent_field_graph["qi_state_write_owner"] == "field" and recurrent_suppressed_graph["qi_state_write_owner"] == "suppressed-model",
        "interpreter_restart_recomputed": interpreter["state"]["after_learning"] == interpreter["state"]["restarted"],
    }
    if not all(checks.values()):
        raise RuntimeError(f"independent checks failed: {checks}")
    return {
        "schema": "cassi.universal-llm-interpreter-native-verification.v2",
        "status": "PASS",
        "run_dir": root.name,
        "model_fingerprint": capture["model_fingerprint"],
        "native_role_authentication": {
            "semantic_source": NATIVE_ROLE_SEMANTIC_SOURCE,
            "derived_native_role": derived_native_role,
            "manifest_sha256": manifest_digest,
            "behavior_probes": probe_result,
            "task_manifest_source": native_task_manifest["semantic_source"],
            "task_manifest_sha256": native_task_manifest["manifest_sha256"],
            "tamper_controls": {
                name: dict(value)
                for name, value in tamper_checks.items()
            },
        },
        "capture": capture,
        "field_seed": field_seed,
        "field_emission": field_output,
        "field_pair": {
            "status": field_pair["status"],
            "max_abs_logit_delta": field_pair["max_abs_logit_delta"],
            "l2_logit_delta": field_pair["l2_logit_delta"],
            "decision_flip": field_pair["decision_flip"],
            "donor_restores_baseline_decision": field_pair["donor_restores_baseline_decision"],
        },
        "recurrent_pair": {
            "status": recurrent_pair["status"],
            "max_abs_logit_delta": recurrent_pair["max_abs_logit_delta"],
            "l2_logit_delta": recurrent_pair["l2_logit_delta"],
            "decision_flip": recurrent_pair["decision_flip"],
        },
        "recurrent_control_pair": {
            "status": recurrent_control_pair["status"],
            "max_abs_logit_delta": recurrent_control_pair["max_abs_logit_delta"],
            "l2_logit_delta": recurrent_control_pair["l2_logit_delta"],
            "decision_flip": recurrent_control_pair["decision_flip"],
        },
        "recurrent_ownership": {
            "model_write_owner": recurrent_model_graph["qi_state_write_owner"],
            "suppressed_write_owner": recurrent_suppressed_graph["qi_state_write_owner"],
            "field_write_owner": recurrent_field_graph["qi_state_write_owner"],
            "field_width": recurrent_field_graph["qi_state_field_width"],
            "row_width": recurrent_field_graph["qi_state_row_width"],
            "field_bytes": recurrent_field_graph["qi_state_field_bytes"],
            "remaining_model_bytes": recurrent_field_graph["qi_state_remaining_model_bytes"],
        },
        "checks": checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = verify(args.run_dir)
    except Exception as error:
        print(f"independent verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
