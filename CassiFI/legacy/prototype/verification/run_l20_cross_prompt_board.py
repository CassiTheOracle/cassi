"""Freeze and summarize the L20 cross-prompt experimental board.

This board utility never loads the model or starts Godot.  It emits the exact
serial arm commands for the pinned L18 runner and summarizes receipts after the
separate windowed lab runs complete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))
from cassi_fi_paths import ARTIFACT_DIR


DEFAULT_OUTPUT = _CASSI_FI_ROOT / "_diag" / "l20-cross-prompt"
MODEL_NAME = "Qwen3.8-27B-Q4_K_M.gguf"
MODEL_SHA = "7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169"
PROTOCOL = "CassiQwen L20 cross-prompt field-output test"
VERSION = 1
PROMPTS = (
    ("rain", "short creative completion", "Write one short sentence about a rainy morning."),
    ("python", "code completion", "Complete this Python expression in one line: total = 2 +"),
    ("primes", "factual continuation", "The first three prime numbers are"),
    ("door", "narrative continuation", "A patient explorer opens a door and sees"),
)
MODES = ("baseline", "residual")
COUPLING = 0.15
MAX_TOKENS = 4


class BoardError(ValueError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise BoardError(message)


def obj(value: Any, label: str) -> Mapping[str, Any]:
    need(isinstance(value, Mapping), f"{label} must be an object")
    return value


def sha(value: Any, label: str) -> str:
    need(isinstance(value, str) and len(value) == 64, f"{label} must be SHA-256")
    value = value.lower()
    need(all(char in "0123456789abcdef" for char in value), f"{label} is malformed")
    return value


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise BoardError(f"could not read finite UTF-8 JSON {path}: {error}") from error


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


def arm_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for prompt_id, shape, prompt in PROMPTS:
        for mode in MODES:
            rows.append(
                {
                    "arm_id": f"{prompt_id}-{mode}",
                    "run_id": f"l20-{prompt_id}-{mode}",
                    "prompt_id": prompt_id,
                    "shape": shape,
                    "prompt": prompt,
                    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "output_mode": mode,
                    "coupling": COUPLING,
                    "max_tokens": MAX_TOKENS,
                }
            )
    return rows


def manifest(output: Path) -> dict[str, Any]:
    return {
        "protocol": PROTOCOL,
        "version": VERSION,
        "status": "FROZEN BEFORE MODEL RUNS",
        "model": {"name": MODEL_NAME, "sha256": MODEL_SHA},
        "board_order": [prompt_id for prompt_id, _, _ in PROMPTS],
        "prompt_count": len(PROMPTS),
        "arm_count": len(arm_rows()),
        "runner": {
            "script": "run_l18_field_output_loop.py",
            "field_lab_port": 7601,
            "context_size": 128,
            "n_batch": 64,
            "n_ubatch": 64,
            "gpu_layers": 99,
            "field_grid_n": 32,
            "field_dimension": 5120,
            "field_retained_weight": 0.9,
            "field_steps_per_layer": 4,
        },
        "decision": {
            "primary_statistic": "number of baseline/residual prompt pairs with committed-token divergence within four output tokens",
            "emerges_minimum": 2,
            "inconclusive_max_comparable_pairs": 1,
        },
        "arms": arm_rows(),
    }


def command(row: Mapping[str, Any], output: Path) -> str:
    prompt = json.dumps(str(row["prompt"]), ensure_ascii=False)
    return (
        f"python run_l18_field_output_loop.py --prompt {prompt} "
        f"--output-mode {row['output_mode']} --coupling {row['coupling']:.17g} "
        f"--max-tokens {row['max_tokens']} --output-dir {output} --run-id {row['run_id']}"
    )


def summarize(directory: Path, manifest_value: Mapping[str, Any]) -> dict[str, Any]:
    arms = [obj(row, "arm") for row in manifest_value["arms"]]
    records: dict[str, dict[str, Any]] = {}
    for row in arms:
        receipt_path = directory / f"{row['run_id']}.receipt.json"
        receipt = obj(load_json(receipt_path), f"{row['arm_id']} receipt")
        need(receipt.get("verdict") == "PASS", f"{row['arm_id']} is not PASS")
        need(receipt.get("run_id") == row["run_id"], f"{row['arm_id']} run ID mismatch")
        config = obj(receipt.get("config"), f"{row['arm_id']} config")
        need(config.get("output_mode") == row["output_mode"], f"{row['arm_id']} mode mismatch")
        need(math.isclose(float(config.get("coupling")), float(row["coupling"]), rel_tol=0.0, abs_tol=0.0), f"{row['arm_id']} coupling mismatch")
        prompt = obj(receipt.get("prompt"), f"{row['arm_id']} prompt")
        need(prompt.get("text") == row["prompt"], f"{row['arm_id']} prompt mismatch")
        generated = obj(receipt.get("generated"), f"{row['arm_id']} generated")
        token_ids = generated.get("token_ids")
        pieces = generated.get("pieces")
        need(isinstance(token_ids, list) and isinstance(pieces, list) and len(token_ids) == len(pieces), f"{row['arm_id']} generated arrays mismatch")
        event_path = Path(obj(receipt.get("event_log"), f"{row['arm_id']} event log")["path"])
        event_hash = sha(obj(receipt.get("event_log"), "event log").get("sha256"), "event log SHA")
        need(hashlib.sha256(event_path.read_bytes()).hexdigest() == event_hash, f"{row['arm_id']} event log hash mismatch")
        records[row["arm_id"]] = {
            "arm_id": row["arm_id"],
            "prompt_id": row["prompt_id"],
            "mode": row["output_mode"],
            "receipt": str(receipt_path),
            "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
            "event_log": str(event_path),
            "event_log_sha256": event_hash,
            "prompt_token_ids": prompt.get("token_ids"),
            "token_ids": token_ids,
            "pieces": pieces,
            "text": generated.get("text"),
        }
    pairs: list[dict[str, Any]] = []
    for prompt_id, _, _ in PROMPTS:
        baseline = records[f"{prompt_id}-baseline"]
        residual = records[f"{prompt_id}-residual"]
        need(baseline["prompt_token_ids"] == residual["prompt_token_ids"], f"{prompt_id} prompt tokenization differs")
        first_divergence = next(
            (index for index, (left, right) in enumerate(zip(baseline["token_ids"], residual["token_ids"])) if left != right),
            None,
        )
        pairs.append(
            {
                "prompt_id": prompt_id,
                "prompt": baseline["text"],
                "prompt_token_ids": baseline["prompt_token_ids"],
                "baseline": baseline,
                "residual": residual,
                "first_divergence": first_divergence,
                "comparable": True,
            }
        )
    divergence_count = sum(pair["first_divergence"] is not None for pair in pairs)
    return {
        "protocol": PROTOCOL,
        "version": VERSION,
        "verdict": "EMERGES" if divergence_count >= 2 else "DOES NOT EMERGE",
        "manifest_sha256": hashlib.sha256((directory / "l20-manifest.json").read_bytes()).hexdigest(),
        "divergence_count": divergence_count,
        "pair_count": len(pairs),
        "pairs": pairs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--commands", action="store_true")
    parser.add_argument("--summarize", action="store_true")
    args = parser.parse_args(argv)
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "l20-manifest.json"
    try:
        if args.freeze or not manifest_path.exists():
            atomic_json(manifest_path, manifest(directory))
            print(f"FROZEN {manifest_path}")
        frozen = obj(load_json(manifest_path), "manifest")
        if args.commands:
            for row in frozen["arms"]:
                print(f"[{row['arm_id']}] {command(row, directory)}")
        if args.summarize:
            result = summarize(directory, frozen)
            atomic_json(directory / "l20-summary.json", result)
            print(json.dumps({"l20": result["verdict"], "divergence_count": result["divergence_count"], "summary": str(directory / 'l20-summary.json')}, ensure_ascii=False))
    except (OSError, BoardError, KeyError, TypeError) as error:
        print(f"L20 board failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
