"""Loopback slot save/erase/restore smoke for the native modal context."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from typing import Any


DEFAULT_MODEL = os.path.abspath(os.path.join(os.path.dirname(__file__), "Qwen3.8-27B-Q4_K_M.gguf"))


def post_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"} if body else {})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--filename", default="modal-slot.bin")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    completion = post_json(
        f"{base_url}/v1/chat/completions",
        {
            "model": args.model,
            "messages": [{"role": "user", "content": "Reply with exactly: CASSI_SLOT_READY"}],
            "temperature": 0,
            "max_tokens": 4,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        },
    )
    if not completion.get("choices"):
        raise RuntimeError(f"completion failed: {completion}")
    saved = post_json(f"{base_url}/slots/0?action=save", {"filename": args.filename})
    if int(saved.get("n_written", 0)) <= 0:
        raise RuntimeError(f"slot save wrote no bytes: {saved}")
    erased = post_json(f"{base_url}/slots/0?action=erase")
    if not erased.get("success", True):
        raise RuntimeError(f"slot erase failed: {erased}")
    restored = post_json(f"{base_url}/slots/0?action=restore", {"filename": args.filename})
    if int(restored.get("n_read", 0)) <= 0:
        raise RuntimeError(f"slot restore read no bytes: {restored}")
    print(json.dumps({"saved": saved, "restored": restored}, sort_keys=True))
    print("native modal slot roundtrip PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
