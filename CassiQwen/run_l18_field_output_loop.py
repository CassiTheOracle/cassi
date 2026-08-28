"""Run the experimental CassiQwen L18 field-to-output loop.

This is a lab-only integration runner.  It keeps one local Qwen context and one
windowed Godot field lab alive, captures every normal generated-token residual
trajectory, evolves the persistent field, evaluates Qwen's frozen output head
on field-augmented final-output features, and commits the resulting token back
into the ordinary Qwen context.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import socket
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from l18_field_language_head import FieldLanguageHead, GGUFError
from l18_field_output_systems import (
    DIMENSION,
    DTYPE,
    GRID_N,
    LAYOUT,
    PROTOCOL,
    VERSION,
    DecodedFieldMemory,
    JsonlEventWriter,
    L18Error,
    TokenLevelPlanner,
    base64_float32,
    decode_direction_field,
    encode_direction_field,
    field_raw_metadata,
    float32_bytes,
    select_field_language_candidates,
    sha256_bytes,
)
from l18_generated_token_trajectory import (
    EXPECTED_MODEL_SHA256,
    DecodeRecord,
    L18GeneratedTokenTrajectory,
    RuntimeConfig,
    TrajectoryError,
)


HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = HERE / "_diag" / "l18-field-output-loop"
DEFAULT_PROMPT = (
    "CassiQwen field output lab. Continue this thought in a short, imaginative sentence: "
    "The field remembers"
)
DEFAULT_LAB_HOST = "127.0.0.1"
DEFAULT_LAB_PORT = 7601
DEFAULT_FIELD_RETAINED_WEIGHT = 0.9
DEFAULT_FIELD_STEPS_PER_LAYER = 4
DEFAULT_COUPLING = 0.15
DEFAULT_MAX_TOKENS = 4
TOP_K = 16


class L18RunnerError(RuntimeError):
    """Raised when the model, field transport, or output seam is malformed."""


@dataclass(frozen=True)
class LabReadout:
    state: dict[str, Any]
    metrics: dict[str, Any]
    field: dict[str, Any]
    ey: np.ndarray
    ei: np.ndarray


class FieldLabClient:
    """Small strict JSON-lines client for the isolated windowed L18 field lab."""

    def __init__(self, host: str, port: int, *, timeout_seconds: float) -> None:
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds
        self._socket: socket.socket | None = None
        self._reader: Any | None = None
        self._writer: Any | None = None

    def connect(self) -> dict[str, Any]:
        if self._socket is not None:
            raise L18RunnerError("field lab client is already connected")
        try:
            self._socket = socket.create_connection((self.host, self.port), timeout=self.timeout_seconds)
            self._socket.settimeout(self.timeout_seconds)
            self._reader = self._socket.makefile("rb")
            self._writer = self._socket.makefile("wb")
            hello = self.request({"cmd": "hello"})
        except OSError as error:
            self.close()
            raise L18RunnerError(
                f"could not connect to L18 field lab at {self.host}:{self.port}; "
                "start the windowed CassiCosmos laboratory scene first"
            ) from error
        field = hello.get("field")
        engine = hello.get("engine")
        if not isinstance(field, Mapping) or not isinstance(engine, Mapping):
            raise L18RunnerError("field lab hello response lacks field/engine schema")
        if int(field.get("grid_n", -1)) != GRID_N or field.get("dtype") != DTYPE or field.get("layout") != LAYOUT:
            raise L18RunnerError(f"field lab schema mismatch: {field!r}")
        if bool(engine.get("serve_bridge", True)) or bool(engine.get("auto_step", True)):
            raise L18RunnerError("L18 field lab must keep the production bridge and auto-step disabled")
        return hello

    def request(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if self._reader is None or self._writer is None:
            raise L18RunnerError("field lab client is not connected")
        try:
            encoded = json.dumps(dict(payload), allow_nan=False, separators=(",", ":")).encode("utf-8") + b"\n"
            self._writer.write(encoded)
            self._writer.flush()
            line = self._reader.readline()
        except OSError as error:
            raise L18RunnerError(f"field lab transport failed for {payload.get('cmd')!r}") from error
        if not line:
            raise L18RunnerError(f"field lab closed while handling {payload.get('cmd')!r}")
        try:
            response = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise L18RunnerError("field lab returned invalid JSON") from error
        if not isinstance(response, dict):
            raise L18RunnerError("field lab response is not an object")
        if response.get("protocol") != PROTOCOL or int(response.get("version", -1)) != VERSION:
            raise L18RunnerError(f"field lab protocol mismatch: {response!r}")
        if response.get("ok") is not True:
            raise L18RunnerError(f"field lab {payload.get('cmd')!r} rejected: {response.get('error')!r}")
        if response.get("finite") is False:
            raise L18RunnerError(f"field lab {payload.get('cmd')!r} returned a non-finite state")
        return response

    def reset(self) -> dict[str, Any]:
        return self.request({"cmd": "reset"})

    def snapshot(self) -> dict[str, Any]:
        """Capture raw EY/EI channels and the exact field clock."""

        return self.request({"cmd": "snapshot"})

    def restore(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        """Restore a snapshot returned by :meth:`snapshot`."""

        state = snapshot.get("state")
        if not isinstance(state, Mapping):
            raise L18RunnerError("field snapshot lacks state metadata")
        ey_b64 = snapshot.get("ey_b64")
        ei_b64 = snapshot.get("ei_b64")
        if not isinstance(ey_b64, str) or not isinstance(ei_b64, str):
            raise L18RunnerError("field snapshot lacks raw EY/EI channels")
        payload = {
            "cmd": "restore",
            "ey_b64": ey_b64,
            "ei_b64": ei_b64,
            "step": int(state.get("step", -1)),
            "t": float(state.get("t", -1.0)),
            "token_index": int(state.get("token_index", -2)),
            "layer_index": int(state.get("layer_index", -2)),
            "event_count": int(snapshot.get("event_count", 0)),
        }
        response = self.request(payload)
        if response.get("state") != state:
            raise L18RunnerError("field restore state differs from snapshot")
        restored_field = response.get("field")
        snapshot_field = snapshot.get("field")
        if not isinstance(restored_field, Mapping) or not isinstance(snapshot_field, Mapping):
            raise L18RunnerError("field restore lacks field metadata")
        if restored_field.get("sha256") != snapshot_field.get("sha256"):
            raise L18RunnerError("field restore SHA-256 differs from snapshot")
        return response

    def blend(
        self,
        *,
        token_index: int,
        layer_index: int,
        ey: np.ndarray,
        ei: np.ndarray,
        retained_weight: float = DEFAULT_FIELD_RETAINED_WEIGHT,
        steps_per_layer: int = DEFAULT_FIELD_STEPS_PER_LAYER,
    ) -> dict[str, Any]:
        metadata = field_raw_metadata(ey, ei)
        response = self.request(
            {
                "cmd": "blend",
                "token_index": token_index,
                "layer_index": layer_index,
                "ey_b64": metadata["ey_b64"],
                "ei_b64": metadata["ei_b64"],
                "retained_weight": retained_weight,
                "steps_per_layer": steps_per_layer,
            }
        )
        response["input_field"] = {
            key: metadata[key]
            for key in ("grid_n", "dtype", "shape", "layout", "ey_sha256", "ei_sha256", "combined_sha256")
        }
        return response

    def readout(self) -> LabReadout:
        response = self.request({"cmd": "readout"})
        field = response.get("field")
        if not isinstance(field, dict):
            raise L18RunnerError("field lab readout lacks field descriptor")
        try:
            ey = base64_float32(str(response["ey_b64"]), expected_shape=(GRID_N**3,), label="field lab EY")
            ei = base64_float32(str(response["ei_b64"]), expected_shape=(GRID_N**3,), label="field lab EI")
        except (KeyError, L18Error) as error:
            raise L18RunnerError("field lab readout has malformed raw channels") from error
        expected = sha256_bytes(float32_bytes(ey, label="field lab EY") + float32_bytes(ei, label="field lab EI"))
        if field.get("sha256") != expected:
            raise L18RunnerError("field lab readout combined SHA-256 mismatch")
        state = response.get("state")
        metrics = response.get("metrics")
        if not isinstance(state, dict) or not isinstance(metrics, dict):
            raise L18RunnerError("field lab readout lacks state or metrics")
        return LabReadout(dict(state), dict(metrics), field, ey, ei)

    def shutdown(self) -> dict[str, Any] | None:
        if self._socket is None:
            return None
        try:
            return self.request({"cmd": "shutdown"})
        except L18RunnerError:
            return None
        finally:
            self.close()

    def close(self) -> None:
        for handle in (self._reader, self._writer):
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
        self._reader = None
        self._writer = None
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
        self._socket = None


def _finite_direction(values: Any, label: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float32)
    if array.shape != (DIMENSION,) or not np.isfinite(array).all():
        raise L18RunnerError(f"{label} must be finite float32 shape ({DIMENSION},)")
    norm = float(np.linalg.norm(array.astype(np.float64, copy=False)))
    if not math.isfinite(norm) or norm <= 0.0:
        raise L18RunnerError(f"{label} has a zero or non-finite L2 norm")
    return np.ascontiguousarray(array / np.float32(norm))


def _array_receipt(values: Any, label: str, *, include_b64: bool = True) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.float32)
    if not np.isfinite(array).all():
        raise L18RunnerError(f"{label} contains non-finite values")
    raw = float32_bytes(array, label=label)
    result = {
        "label": label,
        "dtype": DTYPE,
        "shape": list(array.shape),
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "l2_norm": float(np.linalg.norm(array.astype(np.float64, copy=False))),
        "max_abs": float(np.max(np.abs(array))) if array.size else 0.0,
    }
    if include_b64:
        result["raw_f32_b64"] = base64.b64encode(raw).decode("ascii")
    return result


def _capture_receipt(record: DecodeRecord) -> dict[str, Any]:
    return {
        "decode_index": record.decode_index,
        "source_token_index": record.token_index,
        "mode": record.mode,
        "token_ids": list(record.token_ids),
        "token_positions": list(record.token_positions),
        "token_pieces": list(record.token_pieces),
        "trunk": [capture.as_dict(include_values=False, include_base64=True) for capture in record.trunk],
        "head_output_reference": record.head_output_reference.as_dict(include_values=False, include_base64=True),
        "ordinary_logits": _array_receipt(record.ordinary_logits, "ordinary logits"),
        "ordinary_top_k": [dict(row) for row in record.ordinary_top_k],
    }


def _top_k_with_pieces(runtime: L18GeneratedTokenTrajectory, logits: np.ndarray) -> list[dict[str, Any]]:
    return [dict(row) for row in runtime.top_k_with_pieces(logits, TOP_K)]


def _decorate_candidates(runtime: L18GeneratedTokenTrajectory, rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    decorated: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        token_id = int(item["token_id"])
        item["piece"] = runtime.token_piece(token_id)
        item["is_eog"] = runtime.token_is_eog(token_id)
        decorated.append(item)
    return decorated


def _top_ids(logits: np.ndarray, count: int = TOP_K) -> list[int]:
    ids = np.arange(logits.size, dtype=np.int64)
    order = np.lexsort((ids, -logits.astype(np.float64, copy=False)))[:count]
    return [int(index) for index in order]


def _head_parity(
    runtime: L18GeneratedTokenTrajectory,
    head: FieldLanguageHead,
    record: DecodeRecord,
) -> dict[str, Any]:
    reconstructed = head.logits_from_output_features(record.head_output_vector)
    ordinary = record.ordinary_logits
    delta = np.abs(reconstructed.astype(np.float64) - ordinary.astype(np.float64))
    field_ids = _top_ids(reconstructed)
    ordinary_ids = _top_ids(ordinary)
    return {
        "head_output_sha256": sha256_bytes(record.head_output_raw),
        "ordinary_logits_sha256": sha256_bytes(float32_bytes(ordinary, label="ordinary logits")),
        "reconstructed_logits_sha256": sha256_bytes(float32_bytes(reconstructed, label="reconstructed logits")),
        "max_abs_logit_delta": float(np.max(delta)),
        "argmax_match": int(np.argmax(reconstructed)) == int(np.argmax(ordinary)),
        "top16_ids": {"ordinary": ordinary_ids, "reconstructed": field_ids},
        "top16_match": ordinary_ids == field_ids,
        "finite": bool(np.isfinite(reconstructed).all()),
    }


def _load_external_memory(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    if not path.is_file():
        raise L18RunnerError(f"external memory file is missing: {path}")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise L18RunnerError(f"external memory JSONL line {line_number} is invalid") from error
        if not isinstance(value, dict):
            raise L18RunnerError(f"external memory JSONL line {line_number} is not an object")
        records.append(value)
    return records


def _read_field_vector(lab: FieldLabClient) -> tuple[LabReadout, np.ndarray]:
    readout = lab.readout()
    try:
        decoded = decode_direction_field(readout.ey, readout.ei)
    except L18Error as error:
        raise L18RunnerError("could not decode field readout") from error
    return readout, _finite_direction(decoded, "decoded field direction")


def _process_field_trajectory(
    lab: FieldLabClient,
    record: DecodeRecord,
    *,
    field_token_index: int,
    expected_step_base: int = 0,
) -> tuple[list[dict[str, Any]], LabReadout, np.ndarray]:
    layer_updates: list[dict[str, Any]] = []
    for capture in record.trunk:
        encoded = encode_direction_field(capture.values)
        response = lab.blend(
            token_index=field_token_index,
            layer_index=capture.layer_index,
            ey=encoded.ey,
            ei=encoded.ei,
        )
        layer_updates.append(
            {
                "layer_index": capture.layer_index,
                "source_vector_sha256": sha256_bytes(capture.raw_bytes),
                "source_vector_l2_norm": capture.l2_norm,
                "field_input": response.pop("input_field"),
                "field_output": response.get("field", {}),
                "state": response.get("state", {}),
                "metrics": response.get("metrics", {}),
                "finite": bool(response.get("finite", False)),
            }
        )
    readout, decoded = _read_field_vector(lab)
    expected_step = expected_step_base + (field_token_index + 1) * 64 * DEFAULT_FIELD_STEPS_PER_LAYER
    if int(readout.state.get("step", -1)) != expected_step:
        raise L18RunnerError(
            f"field step mismatch after token {field_token_index}: "
            f"{readout.state.get('step')} != {expected_step}"
        )
    return layer_updates, readout, decoded


def _select_output(
    *,
    runtime: L18GeneratedTokenTrajectory,
    head: FieldLanguageHead,
    planner: TokenLevelPlanner,
    record: DecodeRecord,
    decoded_direction: np.ndarray,
    coupling: float,
    output_mode: str,
    next_position: int,
    field_token_index: int,
    external_memory: list[dict[str, Any]],
) -> tuple[int, str, dict[str, Any], dict[str, Any], int]:
    output_reference_norm = record.head_output_norm
    if not math.isfinite(output_reference_norm) or output_reference_norm <= 0.0:
        raise L18RunnerError("head-output reference has invalid norm")
    field_features = head.output_features(decoded_direction)
    field_only_logits = head.logits_from_output_features(field_features)
    augmented_features = np.ascontiguousarray(
        record.head_output_vector + np.float32(coupling) * field_features
    )
    if not np.isfinite(augmented_features).all():
        raise L18RunnerError("field-augmented output features are non-finite")
    residual_logits = head.logits_from_output_features(augmented_features)
    virtual_record: DecodeRecord | None = None
    planner.gamma = 1.0
    planner.enabled = True
    if output_mode == "residual":
        chosen_logits = residual_logits
        mode_detail = "field_augmented_output_features"
    elif output_mode == "field":
        chosen_logits = field_only_logits
        mode_detail = "field_only_output_features"
    elif output_mode == "blend":
        chosen_logits = field_only_logits
        planner.gamma = coupling
        mode_detail = "ordinary_field_logit_blend"
    elif output_mode == "baseline":
        chosen_logits = record.ordinary_logits
        planner.gamma = 0.0
        planner.enabled = False
        mode_detail = "ordinary_qwen"
    elif output_mode == "virtual":
        virtual_vector = np.ascontiguousarray(
            np.float32(coupling * output_reference_norm) * decoded_direction
        )
        virtual_record = runtime.decode_embedding(virtual_vector, next_position)
        chosen_logits = virtual_record.ordinary_logits
        mode_detail = "field_virtual_embedding"
        next_position += 1
    else:
        raise L18RunnerError(f"unknown output mode: {output_mode!r}")
    preliminary = select_field_language_candidates(
        record.ordinary_logits,
        chosen_logits,
        gamma=planner.gamma,
        top_k=planner.top_k,
        enabled=planner.enabled,
    )
    if not preliminary["top_k"]:
        raise L18RunnerError("candidate selector returned no vocabulary rows")
    selected_token_id = int(preliminary["top_k"][0]["token_id"])
    selected_piece = runtime.token_piece(selected_token_id)
    plan = planner.plan(
        field_token_index,
        record.ordinary_logits,
        chosen_logits,
        decoded_vector=decoded_direction,
        position=next_position,
        external_records=external_memory,
        selected_token_id=selected_token_id,
        selected_piece=selected_piece,
    )
    plan["ranked_candidates"] = _decorate_candidates(runtime, plan["ranked_candidates"])
    plan["candidates"] = list(plan["ranked_candidates"])
    plan["selected_is_eog"] = runtime.token_is_eog(selected_token_id)
    mode_receipt = {
        "mode": output_mode,
        "mode_detail": mode_detail,
        "coupling": coupling,
        "head_output_reference_norm": output_reference_norm,
        "field_direction": _array_receipt(decoded_direction, "decoded field direction"),
        "field_output_features": _array_receipt(field_features, "field output features"),
        "field_augmented_output_features": _array_receipt(
            augmented_features,
            "field-augmented output features",
        ),
        "field_only_logits": _array_receipt(field_only_logits, "field-only logits"),
        "field_only_top_k": _top_k_with_pieces(runtime, field_only_logits),
        "field_augmented_logits": _array_receipt(residual_logits, "field-augmented logits"),
        "field_augmented_top_k": _top_k_with_pieces(runtime, residual_logits),
        "selected_logits": _array_receipt(chosen_logits, "selected output logits"),
        "selected_top_k": _top_k_with_pieces(runtime, chosen_logits),
    }
    if virtual_record is not None:
        mode_receipt["virtual_decode"] = _capture_receipt(virtual_record)
    return selected_token_id, selected_piece, plan, mode_receipt, next_position


def _write_failure(writer: JsonlEventWriter, *, run_id: str, config: Mapping[str, Any], error: BaseException) -> dict[str, Any]:
    receipt = {
        "protocol": PROTOCOL,
        "version": VERSION,
        "run_id": run_id,
        "config": dict(config),
        "verdict": "FAIL",
        "error_type": type(error).__name__,
        "error": str(error),
        "finite": False,
    }
    writer.write_receipt(receipt)
    return receipt


def run_l18(args: argparse.Namespace) -> dict[str, Any]:
    output_root = Path(args.output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id or f"l18-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    event_path = output_root / f"{run_id}.events.jsonl"
    receipt_path = output_root / f"{run_id}.receipt.json"
    writer = JsonlEventWriter(event_path, receipt_path=receipt_path)
    config = {
        "prompt": args.prompt,
        "max_tokens": args.max_tokens,
        "coupling": args.coupling,
        "output_mode": args.output_mode,
        "field": {
            "grid_n": GRID_N,
            "dimension": DIMENSION,
            "dtype": DTYPE,
            "layout": LAYOUT,
            "retained_weight": DEFAULT_FIELD_RETAINED_WEIGHT,
            "steps_per_layer": DEFAULT_FIELD_STEPS_PER_LAYER,
        },
        "lab": {"host": args.lab_host, "port": args.lab_port},
        "model": str(Path(args.model_path).resolve()),
        "model_sha256": EXPECTED_MODEL_SHA256,
    }
    if not 1 <= args.max_tokens <= 64:
        raise L18RunnerError("max_tokens must be in [1, 64]")
    if not math.isfinite(args.coupling) or args.coupling < 0.0:
        raise L18RunnerError("coupling must be finite and non-negative")

    lab = FieldLabClient(args.lab_host, args.lab_port, timeout_seconds=args.timeout)
    runtime: L18GeneratedTokenTrajectory | None = None
    head: FieldLanguageHead | None = None
    shutdown_receipt: dict[str, Any] | None = None
    try:
        lab_hello = lab.connect()
        lab.reset()
        runtime_config = RuntimeConfig(
            model_path=Path(args.model_path),
            dll_dir=Path(args.dll_dir),
            context_size=args.context_size,
            n_batch=args.n_batch,
            n_ubatch=args.n_ubatch,
            gpu_layers=args.gpu_layers,
            expected_model_sha256=EXPECTED_MODEL_SHA256,
        )
        runtime = L18GeneratedTokenTrajectory(runtime_config)
        head = FieldLanguageHead(Path(args.model_path), dll_path=Path(args.dll_dir) / "ggml-base.dll", enabled=True)
        prompt_ids = runtime.tokenize(args.prompt)
        initial = runtime.decode_initial(prompt_ids)
        head_parity = _head_parity(runtime, head, initial)
        if not head_parity["argmax_match"]:
            raise L18RunnerError(
                "frozen GGUF output head does not reproduce the native final-output argmax; "
                "refuse to generate through a mismatched output seam"
            )

        external_memory = _load_external_memory(Path(args.external_memory) if args.external_memory else None)
        memory = DecodedFieldMemory()
        planner = TokenLevelPlanner(memory, gamma=1.0, top_k=TOP_K, retrieval_k=args.retrieval_k, enabled=True)
        events: list[dict[str, Any]] = []
        emitted_ids: list[int] = []
        emitted_pieces: list[str] = []
        current_record = initial
        current_position = initial.final_position

        # The prompt-final residual seeds the first output.  Each committed token
        # is decoded normally, becomes the source for the next output, and is
        # finally pushed through the field once more after the requested sequence.
        for output_index in range(args.max_tokens):
            layer_updates, field_readout, decoded_direction = _process_field_trajectory(
                lab,
                current_record,
                field_token_index=output_index,
            )
            selected_id, selected_piece, plan, output_receipt, token_position = _select_output(
                runtime=runtime,
                head=head,
                planner=planner,
                record=current_record,
                decoded_direction=decoded_direction,
                coupling=args.coupling,
                output_mode=args.output_mode,
                next_position=current_position + 1,
                field_token_index=output_index,
                external_memory=external_memory,
            )
            committed_record = runtime.decode_token(selected_id, token_position)
            event = {
                "protocol": PROTOCOL,
                "version": VERSION,
                "run_id": run_id,
                "event_kind": "output",
                "token_index": output_index,
                "field_source": _capture_receipt(current_record),
                "field_layer_updates": layer_updates,
                "field_readout": {
                    "state": field_readout.state,
                    "metrics": field_readout.metrics,
                    "field": field_readout.field,
                    "ey": _array_receipt(field_readout.ey, "field EY"),
                    "ei": _array_receipt(field_readout.ei, "field EI"),
                },
                "output": output_receipt,
                "candidates": plan["ranked_candidates"],
                "memory": plan["retrieved_memory"],
                "plan": plan,
                "selected_token_id": selected_id,
                "selected_piece": selected_piece,
                "selected_is_eog": runtime.token_is_eog(selected_id),
                "committed_decode": _capture_receipt(committed_record),
                "finite": True,
            }
            event_receipt = writer.write_event(event)
            event["event_receipt"] = event_receipt
            events.append(event)
            emitted_ids.append(selected_id)
            emitted_pieces.append(selected_piece)
            print(
                json.dumps(
                    {
                        "l18": "output",
                        "token_index": output_index,
                        "token_id": selected_id,
                        "piece": selected_piece,
                        "mode": args.output_mode,
                        "field_step": field_readout.state.get("step"),
                        "field_max_abs": field_readout.metrics.get("max_abs"),
                        "retrieved_memory": len(plan["retrieved_memory"]),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            current_record = committed_record
            current_position = token_position
            if runtime.token_is_eog(selected_id):
                break

        # Ensure the final committed generated token traverses all 64 layers in
        # the persistent field even when it is not used to select another token.
        terminal_index = len(emitted_ids)
        terminal_updates, terminal_readout, terminal_direction = _process_field_trajectory(
            lab,
            current_record,
            field_token_index=terminal_index,
        )
        memory.add(
            terminal_direction,
            token_index=terminal_index,
            token_id=current_record.final_token_id,
            piece=current_record.token_pieces[-1] if current_record.token_pieces else None,
            source="terminal_committed_token",
        )
        terminal_event = {
            "protocol": PROTOCOL,
            "version": VERSION,
            "run_id": run_id,
            "event_kind": "terminal_field_update",
            "token_index": terminal_index,
            "field_source": _capture_receipt(current_record),
            "field_layer_updates": terminal_updates,
            "field_readout": {
                "state": terminal_readout.state,
                "metrics": terminal_readout.metrics,
                "field": terminal_readout.field,
                "ey": _array_receipt(terminal_readout.ey, "terminal field EY"),
                "ei": _array_receipt(terminal_readout.ei, "terminal field EI"),
            },
            "decoded_field_direction": _array_receipt(terminal_direction, "terminal decoded field direction"),
            "finite": True,
        }
        terminal_event_receipt = writer.write_event(terminal_event)

        final_readout = lab.readout()
        receipt = {
            "protocol": PROTOCOL,
            "version": VERSION,
            "run_id": run_id,
            "config": config,
            "lab_hello": lab_hello,
            "head": {
                "architecture": head.architecture,
                "rms_epsilon": head.rms_epsilon,
                "metadata": head.metadata,
                "head_parity": head_parity,
            },
            "prompt": {"text": args.prompt, "token_ids": list(prompt_ids), "token_count": len(prompt_ids)},
            "generated": {
                "token_ids": emitted_ids,
                "pieces": emitted_pieces,
                "text": "".join(emitted_pieces),
                "count": len(emitted_ids),
            },
            "events": [event["event_receipt"] for event in events],
            "terminal_event": terminal_event_receipt,
            "event_log": {"path": str(event_path), "sha256": hashlib.sha256(event_path.read_bytes()).hexdigest()},
            "memory": [record.to_dict() for record in memory.records],
            "final_field": {
                "state": final_readout.state,
                "metrics": final_readout.metrics,
                "field": final_readout.field,
                "ey": _array_receipt(final_readout.ey, "final field EY"),
                "ei": _array_receipt(final_readout.ei, "final field EI"),
            },
            "finite": True,
            "verdict": "PASS",
        }
        writer.write_receipt(receipt)
        print(json.dumps({"l18": "PASS", "receipt": str(receipt_path), "events": len(events)}, ensure_ascii=False), flush=True)
        return receipt
    except BaseException as error:
        _write_failure(writer, run_id=run_id, config=config, error=error)
        print(json.dumps({"l18": "FAIL", "receipt": str(receipt_path), "error": str(error)}), file=sys.stderr, flush=True)
        raise
    finally:
        try:
            shutdown_receipt = lab.shutdown()
        finally:
            if head is not None:
                head.close(unload_dll=False)
            if runtime is not None:
                runtime.close(suppress=True)
        if shutdown_receipt is not None:
            print(json.dumps({"l18": "field_lab_shutdown", "receipt": shutdown_receipt}), flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--coupling", type=float, default=DEFAULT_COUPLING)
    parser.add_argument("--output-mode", choices=("residual", "field", "blend", "virtual", "baseline"), default="residual")
    parser.add_argument("--model-path", default=str(HERE / "Qwen3.8-27B-Q4_K_M.gguf"))
    parser.add_argument("--dll-dir", default=str(HERE))
    parser.add_argument("--context-size", type=int, default=128)
    parser.add_argument("--n-batch", type=int, default=64)
    parser.add_argument("--n-ubatch", type=int, default=64)
    parser.add_argument("--gpu-layers", type=int, default=99)
    parser.add_argument("--lab-host", default=DEFAULT_LAB_HOST)
    parser.add_argument("--lab-port", type=int, default=DEFAULT_LAB_PORT)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--retrieval-k", type=int, default=4)
    parser.add_argument("--external-memory", default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--run-id", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run_l18(args)
    except (L18RunnerError, L18Error, TrajectoryError, GGUFError, OSError, ValueError) as error:
        print(f"L18 field-output loop failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
