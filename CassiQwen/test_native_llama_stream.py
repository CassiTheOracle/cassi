"""Loopback smoke for the pinned native llama-server OpenAI surface."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from typing import Any


DEFAULT_MODEL = os.path.abspath(os.path.join(os.path.dirname(__file__), "Qwen3.8-27B-Q4_K_M.gguf"))


def request_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def stream_completion(base_url: str, model: str) -> tuple[str, int]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: CASSI_NATIVE_READY"}],
        "temperature": 0,
        "max_tokens": 8,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    request = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    chunks: list[str] = []
    events = 0
    saw_done = False
    with urllib.request.urlopen(request, timeout=120) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                saw_done = True
                continue
            event = json.loads(data)
            events += 1
            for choice in event.get("choices", []):
                delta = choice.get("delta", {})
                content = delta.get("content")
                if content:
                    chunks.append(str(content))
    if events == 0 or not saw_done:
        raise RuntimeError(f"stream did not produce SSE events and [DONE] (events={events}, done={saw_done})")
    text = "".join(chunks)
    if not text:
        raise RuntimeError("stream produced no assistant content")
    return text, events


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    expectation = parser.add_mutually_exclusive_group()
    expectation.add_argument(
        "--expect-cassi-enabled",
        action="store_true",
        dest="expect_cassi_enabled",
        help="Expect the default-on Cassi modal metric to be enabled (compatibility spelling).",
    )
    expectation.add_argument(
        "--expect-cassi-disabled",
        action="store_false",
        dest="expect_cassi_enabled",
        help="Expect the launcher to have been started with -NoCassiModal.",
    )
    parser.set_defaults(expect_cassi_enabled=True)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    health = request_json(f"{base_url}/health")
    if health.get("status") != "ok":
        raise RuntimeError(f"unexpected health response: {health}")
    models = request_json(f"{base_url}/v1/models")
    model_ids = {str(item.get("id")) for item in models.get("data", [])}
    model = args.model if args.model in model_ids else next(iter(model_ids), args.model)
    metrics_request = urllib.request.Request(f"{base_url}/metrics")
    with urllib.request.urlopen(metrics_request, timeout=30) as response:
        metrics = response.read().decode("utf-8")
    marker = "llamacpp:cassi_modal_enabled "
    enabled_value = None
    for line in metrics.splitlines():
        if line.startswith(marker):
            enabled_value = float(line[len(marker):].split()[0])
            break
    expected = 1.0 if args.expect_cassi_enabled else 0.0
    if enabled_value != expected:
        raise RuntimeError(f"unexpected Cassi modal metric {enabled_value!r}, expected {expected!r}")
    text, events = stream_completion(base_url, model)
    print(json.dumps({"health": health, "model": model, "events": events, "text": text, "cassi_modal_enabled": enabled_value}, sort_keys=True))
    print("native llama streaming PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"native llama streaming FAIL: {error}", file=sys.stderr)
        raise
