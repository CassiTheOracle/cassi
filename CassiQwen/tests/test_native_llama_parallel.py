"""Small loopback concurrency gate for the native llama-server surface."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any


DEFAULT_MODEL = os.path.abspath(os.path.join(os.path.dirname(__file__), "Qwen3.8-27B-Q4_K_M.gguf"))


def complete(base_url: str, model: str, index: int) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": f"Reply with exactly: CASSI_PARALLEL_{index}"}],
        "temperature": 0,
        "max_tokens": 4,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    request = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("choices"):
        raise RuntimeError(f"request {index} returned no choices: {result}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--requests", type=int, default=2)
    args = parser.parse_args()
    if args.requests < 2:
        raise ValueError("--requests must be at least 2")
    base_url = args.base_url.rstrip("/")
    models_request = urllib.request.Request(f"{base_url}/v1/models")
    with urllib.request.urlopen(models_request, timeout=30) as response:
        models = json.loads(response.read().decode("utf-8"))
    ids = {str(item.get("id")) for item in models.get("data", [])}
    model = args.model if args.model in ids else next(iter(ids), args.model)
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.requests) as pool:
        results = list(pool.map(lambda index: complete(base_url, model, index), range(args.requests)))
    elapsed = time.perf_counter() - started
    print(json.dumps({"requests": args.requests, "elapsed_seconds": elapsed, "responses": len(results), "model": model}, sort_keys=True))
    print("native llama concurrency PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
