"""Independently verify the frozen L20 cross-prompt receipts.

The verifier reads only UTF-8 JSON receipts and linked JSONL/raw float32 payloads;
it never imports the model runner, starts Godot, or contacts a service.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_DIR = HERE / "_diag" / "l20-cross-prompt"
PROTOCOL = "CassiQwen L18 field-output loop"
L20_PROTOCOL = "CassiQwen L20 cross-prompt field-output test"
VERSION = 1
MODEL_NAME = "Qwen3.8-27B-Q4_K_M.gguf"
MODEL_SHA = "7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169"
LAYERS = 64
D = 5120
N = 32
CELLS = N**3
STEPS_PER_LAYER = 4
STEPS_PER_TOKEN = LAYERS * STEPS_PER_LAYER
DT = 0.005
TOP_K = 16
DTYPE = "float32-le"
LAYOUT = "x + N*(y + N*z)"
PROMPT_ORDER = ("rain", "python", "primes", "door")
PROMPTS = {
    "rain": "Write one short sentence about a rainy morning.",
    "python": "Complete this Python expression in one line: total = 2 +",
    "primes": "The first three prime numbers are",
    "door": "A patient explorer opens a door and sees",
}
MODES = ("baseline", "residual")


class VerifyError(RuntimeError):
    def __init__(self, gate: str, message: str) -> None:
        super().__init__(f"{gate}: {message}")
        self.gate = gate
        self.message = message


def need(condition: bool, gate: str, message: str) -> None:
    if not condition:
        raise VerifyError(gate, message)


def obj(value: Any, gate: str, label: str) -> Mapping[str, Any]:
    need(isinstance(value, Mapping), gate, f"{label} must be an object")
    return value


def arr(value: Any, gate: str, label: str) -> list[Any]:
    need(isinstance(value, list), gate, f"{label} must be an array")
    return value


def integer(value: Any, gate: str, label: str) -> int:
    need(isinstance(value, int) and not isinstance(value, bool), gate, f"{label} must be an integer")
    return int(value)


def number(value: Any, gate: str, label: str) -> float:
    need(isinstance(value, (int, float)) and not isinstance(value, bool), gate, f"{label} must be numeric")
    value = float(value)
    need(math.isfinite(value), gate, f"{label} must be finite")
    return value


def text(value: Any, gate: str, label: str) -> str:
    need(isinstance(value, str), gate, f"{label} must be text")
    return value


def sha(value: Any, gate: str, label: str) -> str:
    value = text(value, gate, label).lower()
    need(len(value) == 64 and all(char in "0123456789abcdef" for char in value), gate, f"{label} is not SHA-256")
    return value


def load_json(raw: bytes, gate: str, label: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise VerifyError(gate, f"{label} is not finite UTF-8 JSON: {error}") from error


def b64(value: Any, gate: str, label: str) -> bytes:
    encoded = text(value, gate, f"{label} base64")
    try:
        raw = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as error:
        raise VerifyError(gate, f"{label} base64 invalid: {error}") from error
    need(base64.b64encode(raw).decode("ascii") == encoded, gate, f"{label} base64 noncanonical")
    return raw


def decode_array(meta: Any, gate: str, label: str, expected_shape: tuple[int, ...] | None = None) -> np.ndarray:
    item = obj(meta, gate, label)
    raw = b64(item.get("raw_f32_b64"), gate, label)
    shape = tuple(integer(axis, gate, f"{label} shape") for axis in arr(item.get("shape"), gate, f"{label} shape"))
    if expected_shape is not None:
        need(shape == expected_shape, gate, f"{label} shape mismatch")
    need(len(raw) == math.prod(shape) * 4, gate, f"{label} byte count mismatch")
    need(item.get("dtype") in ("float32", DTYPE), gate, f"{label} dtype mismatch")
    expected_sha = sha(item.get("sha256"), gate, f"{label} SHA")
    need(hashlib.sha256(raw).hexdigest() == expected_sha, gate, f"{label} SHA mismatch")
    values = np.frombuffer(raw, dtype="<f4").copy().reshape(shape)
    need(bool(np.isfinite(values).all()), gate, f"{label} non-finite")
    if "bytes" in item:
        need(integer(item["bytes"], gate, f"{label} bytes") == len(raw), gate, f"{label} bytes mismatch")
    return np.ascontiguousarray(values)


def field_channels(meta: Any, gate: str, label: str) -> tuple[np.ndarray, np.ndarray, str]:
    field = obj(meta, gate, label)
    need(field.get("grid_n") == N and field.get("shape") == [CELLS] and field.get("dtype") == DTYPE and field.get("layout") == LAYOUT, gate, f"{label} schema mismatch")
    ey_raw, ei_raw = b64(field.get("ey_b64"), gate, f"{label} EY"), b64(field.get("ei_b64"), gate, f"{label} EI")
    need(len(ey_raw) == len(ei_raw) == CELLS * 4, gate, f"{label} channel bytes mismatch")
    ey, ei = np.frombuffer(ey_raw, dtype="<f4").copy(), np.frombuffer(ei_raw, dtype="<f4").copy()
    need(bool(np.isfinite(ey).all()) and bool(np.isfinite(ei).all()), gate, f"{label} channels non-finite")
    ey_hash, ei_hash = hashlib.sha256(ey.astype("<f4").tobytes()).hexdigest(), hashlib.sha256(ei.astype("<f4").tobytes()).hexdigest()
    need(sha(field.get("ey_sha256"), gate, f"{label} EY SHA") == ey_hash and sha(field.get("ei_sha256"), gate, f"{label} EI SHA") == ei_hash, gate, f"{label} channel hash mismatch")
    combined = hashlib.sha256(ey.astype("<f4").tobytes() + ei.astype("<f4").tobytes()).hexdigest()
    need(sha(field.get("sha256"), gate, f"{label} combined SHA") == combined, gate, f"{label} combined hash mismatch")
    need(integer(field.get("bytes"), gate, f"{label} bytes") == CELLS * 8, gate, f"{label} field bytes mismatch")
    return ey, ei, combined


def event_link(meta: Any, raw: bytes, index: int, event_path: Path, gate: str, label: str) -> None:
    item = obj(meta, gate, label)
    need(integer(item.get("event_index"), gate, f"{label} index") == index, gate, f"{label} index mismatch")
    need(integer(item.get("bytes"), gate, f"{label} bytes") == len(raw), gate, f"{label} bytes mismatch")
    need(sha(item.get("sha256"), gate, f"{label} SHA") == hashlib.sha256(raw).hexdigest(), gate, f"{label} SHA mismatch")
    need(text(item.get("path"), gate, f"{label} path") == str(event_path), gate, f"{label} path mismatch")


def top_ids(meta: Any, gate: str, label: str) -> list[int]:
    rows = arr(meta, gate, label)
    need(len(rows) == TOP_K, gate, f"{label} count mismatch")
    result: list[int] = []
    for rank, row in enumerate(rows, start=1):
        item = obj(row, gate, f"{label}[{rank - 1}]")
        if "rank" in item:
            need(integer(item["rank"], gate, f"{label} rank") == rank, gate, f"{label} rank mismatch")
        result.append(integer(item.get("token_id"), gate, f"{label} token"))
        number(item.get("logit"), gate, f"{label} logit")
    return result


def source_record(value: Any, event_index: int, prompt_ids: list[int], gate: str) -> dict[str, Any]:
    source = obj(value, gate, "field source")
    source_index = -1 if event_index == 0 else event_index - 1
    expected_mode = "initial_tokens" if event_index == 0 else "token"
    need(source.get("mode") == expected_mode and integer(source.get("source_token_index"), gate, "source token index") == source_index and integer(source.get("decode_index"), gate, "decode index") == event_index, gate, "source identity mismatch")
    ids = [integer(token, gate, "source token") for token in arr(source.get("token_ids"), gate, "source token IDs")]
    positions = [integer(position, gate, "source position") for position in arr(source.get("token_positions"), gate, "source positions")]
    pieces = [text(piece, gate, "source piece") for piece in arr(source.get("token_pieces"), gate, "source pieces")]
    need(len(ids) == len(positions) == len(pieces) > 0, gate, "source token arrays mismatch")
    if event_index == 0:
        need(ids == prompt_ids, gate, "initial source tokens differ from prompt")
    trunk = arr(source.get("trunk"), gate, "trunk captures")
    need(len(trunk) == LAYERS and source.get("trunk_layer_indices", list(range(LAYERS))) == list(range(LAYERS)), gate, "trunk capture count/order mismatch")
    vectors: list[np.ndarray] = []
    for layer, item_value in enumerate(trunk):
        item = obj(item_value, gate, f"trunk {layer}")
        need(item.get("role") == "field_trunk" and integer(item.get("layer_index"), gate, "trunk layer") == layer and integer(item.get("token_index"), gate, "trunk token") == source_index and integer(item.get("token_position"), gate, "trunk position") == positions[-1], gate, f"trunk {layer} identity mismatch")
        vector = decode_array(item, gate, f"trunk {layer}", (D,))
        vectors.append(vector)
    head = obj(source.get("head_output_reference"), gate, "head output reference")
    need(head.get("role") == "head_output_reference" and integer(head.get("layer_index"), gate, "head layer") == 64 and integer(head.get("token_index"), gate, "head token") == source_index and integer(head.get("token_position"), gate, "head position") == positions[-1], gate, "head identity mismatch")
    head_vector = decode_array(head, gate, "head output reference", (D,))
    ordinary = decode_array(source.get("ordinary_logits"), gate, "ordinary logits")
    need(ordinary.ndim == 1 and ordinary.size >= TOP_K, gate, "ordinary logits shape mismatch")
    ordinary_ids = top_ids(source.get("ordinary_top_k"), gate, "ordinary top-k")
    return {"ids": ids, "positions": positions, "pieces": pieces, "trunk": trunk, "vectors": vectors, "head": head_vector, "ordinary": ordinary, "ordinary_ids": ordinary_ids, "source_field_sha": None}


def verify_updates(event: Mapping[str, Any], source: Mapping[str, Any], event_index: int, gate: str) -> None:
    rows = arr(event.get("field_layer_updates"), gate, "field updates")
    need(len(rows) == LAYERS, gate, "field update count mismatch")
    for layer, value in enumerate(rows):
        row = obj(value, gate, f"field update {layer}")
        need(row.get("finite") is True and integer(row.get("layer_index"), gate, "update layer") == layer, gate, f"field update {layer} identity mismatch")
        need(sha(row.get("source_vector_sha256"), gate, "source vector SHA") == sha(source["trunk"][layer].get("sha256"), gate, "trunk SHA"), gate, f"field update {layer} source mismatch")
        field_input = obj(row.get("field_input"), gate, f"field input {layer}")
        need(field_input.get("grid_n") == N and field_input.get("shape") == [CELLS] and field_input.get("dtype") == DTYPE and field_input.get("layout") == LAYOUT, gate, f"field input {layer} schema mismatch")
        for key in ("ey_sha256", "ei_sha256", "combined_sha256"):
            sha(field_input.get(key), gate, f"field input {layer} {key}")
        state = obj(row.get("state"), gate, f"field update {layer} state")
        expected_step = (event_index * LAYERS + layer + 1) * STEPS_PER_LAYER
        need(integer(state.get("step"), gate, "update step") == expected_step and integer(state.get("token_index"), gate, "update token") == event_index and integer(state.get("layer_index"), gate, "update layer") == layer, gate, f"field update {layer} clock mismatch")
        need(math.isclose(number(state.get("t"), gate, "update t"), expected_step * DT, rel_tol=0.0, abs_tol=2e-6), gate, f"field update {layer} time mismatch")
        output = obj(row.get("field_output"), gate, f"field output {layer}")
        for key in ("ey_sha256", "ei_sha256", "sha256"):
            sha(output.get(key), gate, f"field output {layer} {key}")


def verify_event(event: Mapping[str, Any], mode: str, event_index: int, prompt_ids: list[int], previous_commit: list[int] | None, run_id: str) -> dict[str, Any]:
    gate = f"{run_id} event {event_index}"
    need(event.get("protocol") == PROTOCOL and integer(event.get("version"), gate, "version") == VERSION and event.get("run_id") == run_id and event.get("event_kind") == "output" and integer(event.get("token_index"), gate, "token index") == event_index and event.get("finite") is True, gate, "event identity/finiteness mismatch")
    source = source_record(event.get("field_source"), event_index, prompt_ids, gate)
    if previous_commit is not None:
        need(source["ids"] == previous_commit, gate, "source does not continue previous commit")
    verify_updates(event, source, event_index, gate)
    readout = obj(event.get("field_readout"), gate, "field readout")
    state = obj(readout.get("state"), gate, "field state")
    expected_step = (event_index + 1) * STEPS_PER_TOKEN
    need(integer(state.get("step"), gate, "readout step") == expected_step and integer(state.get("token_index"), gate, "readout token") == event_index and integer(state.get("layer_index"), gate, "readout layer") == LAYERS - 1 and math.isclose(number(state.get("t"), gate, "readout t"), expected_step * DT, rel_tol=0.0, abs_tol=2e-6), gate, "readout clock mismatch")
    ey, ei, field_sha = field_channels(readout.get("field"), gate, "readout field")
    for key, expected in (("ey", ey), ("ei", ei)):
        actual = decode_array(readout.get(key), gate, f"readout {key}", (CELLS,))
        need(actual.tobytes() == expected.astype("<f4").tobytes(), gate, f"readout {key} linkage mismatch")
    metrics = obj(readout.get("metrics"), gate, "field metrics")
    need(metrics.get("finite") is True, gate, "field metrics finite flag false")
    need(float(metrics.get("max_abs", 0.0)) <= 10.0, gate, "field bound exceeded")
    updates = arr(event.get("field_layer_updates"), gate, "updates")
    last = obj(updates[-1].get("field_output"), gate, "last field output")
    for key in ("ey_sha256", "ei_sha256", "sha256"):
        need(sha(last.get(key), gate, f"last output {key}") == sha(obj(readout.get("field"), gate, "readout field").get(key), gate, f"readout {key}"), gate, f"last update/readout {key} mismatch")
    output = obj(event.get("output"), gate, "output")
    expected_detail = "ordinary_qwen" if mode == "baseline" else "field_augmented_output_features"
    need(output.get("mode") == mode and output.get("mode_detail") == expected_detail and math.isclose(number(output.get("coupling"), gate, "coupling"), 0.15, rel_tol=0.0, abs_tol=0.0), gate, "output mode/coupling mismatch")
    direction = decode_array(output.get("field_direction"), gate, "field direction", (D,))
    features = decode_array(output.get("field_output_features"), gate, "field output features", (D,))
    augmented_features = decode_array(output.get("field_augmented_output_features"), gate, "augmented features", (D,))
    need(bool(np.isfinite(direction).all()) and bool(np.isfinite(features).all()) and bool(np.isfinite(augmented_features).all()), gate, "output feature non-finite")
    field_logits = decode_array(output.get("field_only_logits"), gate, "field logits")
    augmented_logits = decode_array(output.get("field_augmented_logits"), gate, "augmented logits")
    selected_logits = decode_array(output.get("selected_logits"), gate, "selected logits")
    need(field_logits.shape == augmented_logits.shape == selected_logits.shape and field_logits.ndim == 1 and field_logits.size >= TOP_K, gate, "output logits shape mismatch")
    selected_ids = top_ids(output.get("selected_top_k"), gate, "selected top-k")
    need(selected_ids[0] == integer(event.get("selected_token_id"), gate, "selected token"), gate, "selected token is not selected top-one")
    expected_enabled = mode == "residual"
    plan = obj(event.get("plan"), gate, "plan")
    need(plan.get("field_enabled") is expected_enabled and plan.get("external_actions") == [] and plan.get("actions") == [] and plan.get("finite") is True, gate, "planner field/action contract mismatch")
    need(integer(plan.get("selected_token_id"), gate, "plan selected") == selected_ids[0], gate, "plan selected token mismatch")
    candidates = arr(event.get("candidates"), gate, "candidates")
    need(len(candidates) == TOP_K and candidates == plan.get("ranked_candidates") == plan.get("candidates"), gate, "candidate aliases/count mismatch")
    need(integer(obj(candidates[0], gate, "candidate").get("token_id"), gate, "candidate token") == selected_ids[0], gate, "candidate top-one mismatch")
    commit = obj(event.get("committed_decode"), gate, "commit")
    commit_ids = [integer(token, gate, "commit token") for token in arr(commit.get("token_ids"), gate, "commit IDs")]
    commit_positions = [integer(position, gate, "commit position") for position in arr(commit.get("token_positions"), gate, "commit positions")]
    positions = source["positions"]
    need(commit_ids == [selected_ids[0]] and len(commit_positions) == 1 and commit_positions[0] == positions[-1] + 1, gate, "commit linkage mismatch")
    return {"token_ids": commit_ids, "field_sha": field_sha, "direction": direction, "selected_token": selected_ids[0], "selected_piece": text(event.get("selected_piece"), gate, "selected piece")}


def event_path(receipt: Mapping[str, Any], receipt_path: Path, gate: str) -> Path:
    meta = obj(receipt.get("event_log"), gate, "event log")
    candidate = Path(text(meta.get("path"), gate, "event path"))
    path = candidate if candidate.is_absolute() else receipt_path.parent / candidate
    raw = path.read_bytes()
    need(sha(meta.get("sha256"), gate, "event log SHA") == hashlib.sha256(raw).hexdigest(), gate, "event log SHA mismatch")
    return path


def verify_arm(directory: Path, arm: Mapping[str, Any]) -> dict[str, Any]:
    arm_id = text(arm.get("arm_id"), "header", "arm ID")
    gate = arm_id
    receipt_path = directory / f"{arm['run_id']}.receipt.json"
    receipt_raw = receipt_path.read_bytes()
    receipt = obj(load_json(receipt_raw, gate, "receipt"), gate, "receipt")
    need(receipt.get("protocol") == PROTOCOL and integer(receipt.get("version"), gate, "version") == VERSION and receipt.get("run_id") == arm["run_id"] and receipt.get("verdict") == "PASS" and receipt.get("finite") is True, gate, "receipt identity/verdict mismatch")
    config = obj(receipt.get("config"), gate, "config")
    need(config.get("output_mode") == arm["output_mode"] and math.isclose(number(config.get("coupling"), gate, "coupling"), 0.15, rel_tol=0.0, abs_tol=0.0) and integer(config.get("max_tokens"), gate, "max tokens") == 4 and config.get("prompt") == arm["prompt"], gate, "frozen config mismatch")
    need(Path(text(config.get("model"), gate, "model")).name == MODEL_NAME and sha(config.get("model_sha256"), gate, "model SHA") == MODEL_SHA, gate, "model identity mismatch")
    field = obj(config.get("field"), gate, "field config")
    need(field.get("grid_n") == N and field.get("dimension") == D and field.get("dtype") == DTYPE and field.get("layout") == LAYOUT and field.get("retained_weight") == 0.9 and integer(field.get("steps_per_layer"), gate, "steps") == STEPS_PER_LAYER, gate, "field config mismatch")
    lab = obj(config.get("lab"), gate, "lab config")
    need(lab.get("host") == "127.0.0.1" and integer(lab.get("port"), gate, "port") == 7601, gate, "lab boundary mismatch")
    prompt = obj(receipt.get("prompt"), gate, "prompt")
    prompt_ids = [integer(token, gate, "prompt token") for token in arr(prompt.get("token_ids"), gate, "prompt IDs")]
    need(prompt.get("text") == arm["prompt"] and integer(prompt.get("token_count"), gate, "prompt count") == len(prompt_ids) > 0, gate, "prompt mismatch")
    parity = obj(obj(receipt.get("head"), gate, "head").get("head_parity"), gate, "head parity")
    need(parity.get("finite") is True and parity.get("argmax_match") is True and 0.0 <= number(parity.get("max_abs_logit_delta"), gate, "head delta") < 1.0, gate, "head parity mismatch")
    path = event_path(receipt, receipt_path, gate)
    lines = path.read_bytes().splitlines(keepends=True)
    need(len(lines) == 5 and all(line.endswith(b"\n") for line in lines), gate, "event log count/termination mismatch")
    event_meta = arr(receipt.get("events"), gate, "receipt events")
    need(len(event_meta) == 4, gate, "receipt event count mismatch")
    events: list[Mapping[str, Any]] = []
    for index, raw in enumerate(lines[:-1]):
        event_link(event_meta[index], raw, index, path, gate, f"event {index}")
        events.append(obj(load_json(raw[:-1], gate, f"event {index}"), gate, f"event {index}"))
    terminal_raw = lines[-1]
    event_link(receipt.get("terminal_event"), terminal_raw, 4, path, gate, "terminal")
    terminal = obj(load_json(terminal_raw[:-1], gate, "terminal"), gate, "terminal")
    need(terminal.get("protocol") == PROTOCOL and terminal.get("event_kind") == "terminal_field_update" and integer(terminal.get("token_index"), gate, "terminal index") == 4 and terminal.get("finite") is True, gate, "terminal identity mismatch")
    summaries: list[dict[str, Any]] = []
    prior: list[int] | None = None
    for index, event in enumerate(events):
        summary = verify_event(event, arm["output_mode"], index, prompt_ids, prior, arm["run_id"])
        summaries.append(summary)
        prior = summary["token_ids"]
    terminal_state = obj(obj(terminal.get("field_readout"), gate, "terminal readout").get("state"), gate, "terminal state")
    need(integer(terminal_state.get("step"), gate, "terminal step") == 5 * STEPS_PER_TOKEN and integer(terminal_state.get("token_index"), gate, "terminal token") == 4, gate, "terminal clock mismatch")
    terminal_field = obj(terminal.get("field_readout"), gate, "terminal readout").get("field")
    _, _, terminal_sha = field_channels(terminal_field, gate, "terminal field")
    final = obj(receipt.get("final_field"), gate, "final field")
    _, _, final_sha = field_channels(final.get("field"), gate, "final field payload")
    need(terminal_sha == final_sha and obj(final.get("state"), gate, "final state") == terminal_state, gate, "terminal/final field mismatch")
    generated = obj(receipt.get("generated"), gate, "generated")
    generated_ids = [integer(token, gate, "generated token") for token in arr(generated.get("token_ids"), gate, "generated IDs")]
    generated_pieces = [text(piece, gate, "generated piece") for piece in arr(generated.get("pieces"), gate, "generated pieces")]
    need(generated_ids == [summary["selected_token"] for summary in summaries] and generated_pieces == [summary["selected_piece"] for summary in summaries] and generated.get("text") == "".join(generated_pieces), gate, "generated sequence mismatch")
    return {"arm_id": arm_id, "mode": arm["output_mode"], "prompt_id": arm["prompt_id"], "prompt_token_ids": prompt_ids, "token_ids": generated_ids, "pieces": generated_pieces, "text": generated["text"], "field_shas": [summary["field_sha"] for summary in summaries] + [final_sha], "receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(), "event_log_sha256": sha(obj(receipt.get("event_log"), gate, "event log").get("sha256"), gate, "event log SHA")}


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)
    try:
        directory = args.directory.resolve()
        manifest_raw = (directory / "l20-manifest.json").read_bytes()
        manifest = obj(load_json(manifest_raw, "manifest", "manifest"), "manifest", "manifest")
        need(manifest.get("protocol") == L20_PROTOCOL and integer(manifest.get("version"), "manifest", "version") == VERSION and manifest.get("status") == "FROZEN BEFORE MODEL RUNS", "manifest", "manifest identity mismatch")
        arms = arr(manifest.get("arms"), "manifest", "arms")
        need(len(arms) == 8, "manifest", "arm count mismatch")
        results = [verify_arm(directory, obj(arm, "manifest", "arm")) for arm in arms]
        by_id = {result["arm_id"]: result for result in results}
        pairs: list[dict[str, Any]] = []
        for prompt_id in PROMPT_ORDER:
            baseline, residual = by_id[f"{prompt_id}-baseline"], by_id[f"{prompt_id}-residual"]
            need(baseline["prompt_token_ids"] == residual["prompt_token_ids"], "pair", f"{prompt_id} prompt tokenization mismatch")
            divergence = next((index for index, (left, right) in enumerate(zip(baseline["token_ids"], residual["token_ids"])) if left != right), None)
            comparable_field = baseline["field_shas"][0] == residual["field_shas"][0]
            need(comparable_field, "pair", f"{prompt_id} initial field mismatch")
            post_field_difference = None
            if divergence is not None:
                post_index = divergence + 1
                if post_index < len(baseline["field_shas"]):
                    post_field_difference = baseline["field_shas"][post_index] != residual["field_shas"][post_index]
                    need(post_field_difference, "pair", f"{prompt_id} field did not separate after token divergence")
            pairs.append({"prompt_id": prompt_id, "baseline": baseline, "residual": residual, "first_divergence": divergence, "initial_field_match": comparable_field, "post_divergence_field_difference": post_field_difference})
        divergence_count = sum(pair["first_divergence"] is not None for pair in pairs)
        verdict = "EMERGES" if divergence_count >= 2 else "DOES NOT EMERGE"
        result = {"protocol": L20_PROTOCOL, "version": VERSION, "verdict": verdict, "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(), "pair_count": 4, "divergence_count": divergence_count, "pairs": pairs}
        atomic_json(directory / "l20-verification.json", result)
    except (OSError, VerifyError, KeyError, TypeError) as error:
        print(f"FAIL {error}")
        return 1
    print(json.dumps({"l20": verdict, "divergence_count": divergence_count, "verification": str(directory / 'l20-verification.json')}, ensure_ascii=False))
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
