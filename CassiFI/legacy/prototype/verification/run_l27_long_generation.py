"""Run the preregistered L27 16-token baseline/residual pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
import urllib.request
from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))

from cassi_fi_paths import ARTIFACT_DIR
from typing import Any


MODEL_NAME = "Qwen3.8-27B-Q4_K_M.gguf"
MODEL_SHA256 = "7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169"
PROTOCOL = "CassiQwen L27 longer-generation field-output comparison"
VERSION = 1
DEFAULT_PROMPT = "A patient explorer opens a door and sees"
DEFAULT_MAX_TOKENS = 16


class L27RunnerError(RuntimeError):
    """Runner or provider response failure."""


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


def post(url: str, *, prompt: str, mode: str, session_id: str, max_tokens: int) -> dict[str, Any]:
    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "user": session_id,
        "cassi_output_mode": mode,
        "cassi_student_mode": "off",
        "cassi_teacher_policy": "always",
        "stream": False,
    }
    request = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            value = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise L27RunnerError(f"{mode} provider request failed: {error}") from error
    if not isinstance(value, dict) or not isinstance(value.get("choices"), list) or not value["choices"]:
        raise L27RunnerError(f"{mode} response lacks choices")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8081/v1/chat/completions")
    parser.add_argument("--output-dir", type=Path, default=_CASSI_FI_ROOT / "_diag" / "l27-long-generation")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--session-prefix", default="l27-long")
    args = parser.parse_args()
    if not 1 <= args.max_tokens <= 64:
        raise SystemExit("--max-tokens must be in [1, 64]")
    output_dir = args.output_dir.resolve()
    prompt_sha256 = hashlib.sha256(args.prompt.encode("utf-8")).hexdigest()
    arms: dict[str, dict[str, Any]] = {}
    for mode in ("baseline", "residual"):
        session_id = f"{args.session_prefix}-{mode}"
        response = post(args.url, prompt=args.prompt, mode=mode, session_id=session_id, max_tokens=args.max_tokens)
        response_path = output_dir / f"{mode}.response.json"
        atomic_json(response_path, response)
        arms[mode] = {
            "mode": mode,
            "session_id": session_id,
            "response_path": str(response_path),
            "response_sha256": hashlib.sha256(response_path.read_bytes()).hexdigest(),
        }
    board = {
        "protocol": PROTOCOL,
        "version": VERSION,
        "created_at": time.time(),
        "model": {"name": MODEL_NAME, "sha256": MODEL_SHA256},
        "provider_url": args.url,
        "prompt": args.prompt,
        "prompt_sha256": prompt_sha256,
        "max_tokens": args.max_tokens,
        "coupling": 0.15,
        "arms": arms,
    }
    board_path = output_dir / "l27-board.json"
    atomic_json(board_path, board)
    print(json.dumps({"board": str(board_path), "baseline": arms["baseline"], "residual": arms["residual"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
