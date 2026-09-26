"""Independently verify and classify the L27 paired generation board."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import struct
import tempfile
from pathlib import Path
from typing import Any, Mapping


MODEL_NAME = "Qwen3.8-27B-Q4_K_M.gguf"
MODEL_SHA256 = "7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169"
PROTOCOL = "CassiQwen L27 longer-generation field-output comparison"
VERSION = 1
FIELD_STEPS_PER_EVENT = 256


class L27VerificationError(RuntimeError):
    """A mechanical L27 receipt or comparison failure."""


def need(condition: bool, message: str) -> None:
    if not condition:
        raise L27VerificationError(message)


def obj(value: Any, label: str) -> Mapping[str, Any]:
    need(isinstance(value, Mapping), f"{label} must be an object")
    return value


def finite_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise L27VerificationError(f"cannot read finite JSON {path}: {error}") from error


def sha(value: Any, label: str) -> str:
    need(isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdefABCDEF" for char in value), f"{label} is not SHA-256")
    return value.lower()


def verify_sketch(value: Any, label: str) -> None:
    need(isinstance(value, str), f"{label} is not base64 text")
    try:
        raw = base64.b64decode(value.encode("ascii"), validate=True)
        floats = struct.unpack("<128f", raw)
    except (ValueError, UnicodeEncodeError, struct.error) as error:
        raise L27VerificationError(f"{label} is not a 128-value float32 sketch") from error
    need(base64.b64encode(raw).decode("ascii") == value, f"{label} is not canonical base64")
    need(all(math.isfinite(number) for number in floats), f"{label} contains non-finite values")


def verify_arm(board: Mapping[str, Any], mode: str) -> dict[str, Any]:
    arms = obj(board.get("arms"), "board arms")
    arm = obj(arms.get(mode), f"{mode} arm")
    response_path = Path(str(arm.get("response_path")))
    need(response_path.is_file(), f"{mode} response is missing: {response_path}")
    need(hashlib.sha256(response_path.read_bytes()).hexdigest() == arm.get("response_sha256"), f"{mode} response hash mismatch")
    response = obj(finite_json(response_path), f"{mode} response")
    need(response.get("model") == MODEL_NAME, f"{mode} model mismatch")
    cassi = obj(response.get("cassi"), f"{mode} Cassi receipt")
    need(cassi.get("protocol") == "CassiQwen persistent field provider" and cassi.get("version") == 1, f"{mode} provider protocol mismatch")
    need(cassi.get("output_mode") == mode, f"{mode} output mode mismatch")
    need(cassi.get("teacher_call") is True, f"{mode} arm did not call native teacher")
    need(obj(cassi.get("head_parity"), f"{mode} head parity").get("argmax_match") is True, f"{mode} head parity failed")
    need(cassi.get("session_id") == arm.get("session_id"), f"{mode} session ID mismatch")
    choices = response.get("choices")
    need(isinstance(choices, list) and choices and isinstance(choices[0], Mapping), f"{mode} choices missing")
    usage = obj(response.get("usage"), f"{mode} usage")
    need(isinstance(usage.get("prompt_tokens"), int) and usage.get("prompt_tokens") > 0, f"{mode} prompt usage missing")
    events = cassi.get("events")
    need(isinstance(events, list) and events, f"{mode} events missing")
    token_ids: list[int] = []
    pieces: list[str] = []
    field_hashes: list[str] = []
    for index, event_value in enumerate(events):
        event = obj(event_value, f"{mode} event {index}")
        need(event.get("token_index") == index, f"{mode} token index is not sequential")
        need(event.get("field_step") == (index + 1) * FIELD_STEPS_PER_EVENT, f"{mode} field clock mismatch at event {index}")
        field_hashes.append(sha(event.get("field_sha256"), f"{mode} event field hash"))
        verify_sketch(event.get("field_sketch_f32_b64"), f"{mode} event sketch")
        token_id = event.get("selected_token_id")
        piece = event.get("selected_piece")
        need(isinstance(token_id, int) and token_id >= 0 and isinstance(piece, str), f"{mode} selected token is malformed")
        token_ids.append(token_id)
        pieces.append(piece)
        need(isinstance(event.get("teacher_top_k"), list) and event.get("teacher_top_k"), f"{mode} teacher top-k missing")
    trace_ids = cassi.get("trace_record_ids")
    need(isinstance(trace_ids, list) and len(trace_ids) == len(events) and len(set(trace_ids)) == len(trace_ids), f"{mode} trace linkage mismatch")
    for trace_id in trace_ids:
        sha(trace_id, f"{mode} trace ID")
    trace_stats = obj(cassi.get("trace_stats"), f"{mode} trace stats")
    need(int(trace_stats.get("records", 0)) >= len(events), f"{mode} trace store count is too small")
    terminal_step = cassi.get("field_step")
    need(terminal_step == (len(events) + 1) * FIELD_STEPS_PER_EVENT, f"{mode} terminal field clock mismatch")
    terminal_hash = sha(cassi.get("field_sha256"), f"{mode} terminal field hash")
    return {
        "mode": mode,
        "session_id": arm.get("session_id"),
        "response_path": str(response_path),
        "response_sha256": hashlib.sha256(response_path.read_bytes()).hexdigest(),
        "prompt_tokens": usage.get("prompt_tokens"),
        "token_ids": token_ids,
        "pieces": pieces,
        "text": choices[0].get("message", {}).get("content"),
        "event_count": len(events),
        "field_hashes": field_hashes,
        "terminal_field_step": terminal_step,
        "terminal_field_sha256": terminal_hash,
        "trace_record_ids": trace_ids,
    }


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n").encode("utf-8")
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


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, default=Path("_diag/l27-long-generation/l27-board.json"))
    args = parser.parse_args()
    board = obj(finite_json(args.board), "L27 board")
    need(board.get("protocol") == PROTOCOL and board.get("version") == VERSION, "L27 board protocol mismatch")
    model = obj(board.get("model"), "L27 model")
    need(model.get("name") == MODEL_NAME and model.get("sha256") == MODEL_SHA256, "L27 model identity mismatch")
    need(isinstance(board.get("prompt"), str) and hashlib.sha256(board["prompt"].encode("utf-8")).hexdigest() == board.get("prompt_sha256"), "L27 prompt hash mismatch")
    need(isinstance(board.get("max_tokens"), int) and 1 <= board["max_tokens"] <= 64, "L27 horizon is malformed")
    baseline = verify_arm(board, "baseline")
    residual = verify_arm(board, "residual")
    need(baseline["prompt_tokens"] == residual["prompt_tokens"], "paired prompt token counts differ")
    max_length = max(len(baseline["token_ids"]), len(residual["token_ids"]))
    first_divergence = next((index for index in range(max_length) if (baseline["token_ids"] + [None] * max_length)[index] != (residual["token_ids"] + [None] * max_length)[index]), None)
    differing_positions = [index for index in range(max_length) if (baseline["token_ids"] + [None] * max_length)[index] != (residual["token_ids"] + [None] * max_length)[index]]
    terminal_field_separated = baseline["terminal_field_sha256"] != residual["terminal_field_sha256"]
    verdict = "EMERGES" if first_divergence is not None and terminal_field_separated else "DOES NOT EMERGE"
    result = {
        "protocol": PROTOCOL,
        "version": VERSION,
        "verdict": verdict,
        "board": str(args.board.resolve()),
        "prompt": board["prompt"],
        "max_tokens": board["max_tokens"],
        "baseline": baseline,
        "residual": residual,
        "first_divergence": first_divergence,
        "common_prefix_length": first_divergence if first_divergence is not None else min(len(baseline["token_ids"]), len(residual["token_ids"])),
        "differing_positions": differing_positions,
        "differing_position_count": len(differing_positions),
        "terminal_field_separated": terminal_field_separated,
    }
    output_path = args.board.with_name("l27-verification.json")
    atomic_json(output_path, result)
    print(json.dumps({"verdict": verdict, "first_divergence": first_divergence, "differing_positions": differing_positions, "terminal_field_separated": terminal_field_separated, "verification": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, L27VerificationError, KeyError, TypeError, ValueError) as error:
        print(f"L27 verification failed: {error}")
        raise SystemExit(1)
