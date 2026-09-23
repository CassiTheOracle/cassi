#!/usr/bin/env python3
"""Exercise the loopback-only native Cassi apprentice HTTP surface."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import http.client
import json
import socket
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

NATIVE_ZERO_KEYS = (
    "native_service_calls", "full_teacher_queries", "teacher_failures",
    "teacher_audits", "audit_mismatches", "native_prefill_tokens",
    "native_context_creations", "native_logits_reads", "native_replay_tokens",
    "native_decode_tokens", "native_ggml_nodes_executed",
    "native_output_rows_computed", "logical_weight_bytes",
    "loaded_model_tensor_bytes", "native_cache_bytes_peak",
    "native_cache_bytes_remaining",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class Client:
    def __init__(self, base_url: str) -> None:
        parsed = urlparse(base_url)
        require(parsed.scheme == "http", "the native apprentice client requires http")
        require(parsed.hostname in ("127.0.0.1", "localhost"), "the native apprentice client is loopback-only")
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 80
        self.prefix = parsed.path.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        timeout: float = 600.0,
    ) -> tuple[int, dict[str, Any], str]:
        connection = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {} if payload is None else {"content-type": "application/json; charset=utf-8"}
        connection.request(method, self.prefix + path, body=payload, headers=headers)
        response = connection.getresponse()
        raw = response.read().decode("utf-8")
        status = response.status
        connection.close()
        parsed: dict[str, Any]
        try:
            value = json.loads(raw)
            parsed = value if isinstance(value, dict) else {"value": value}
        except json.JSONDecodeError:
            parsed = {}
        return status, parsed, raw

    def stream(self, path: str, body: dict[str, Any], timeout: float = 600.0) -> dict[str, Any]:
        connection = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        connection.request("POST", self.prefix + path, body=payload, headers={
            "content-type": "application/json; charset=utf-8",
            "accept": "text/event-stream",
        })
        response = connection.getresponse()
        raw_lines: list[str] = []
        events: list[dict[str, Any]] = []
        done = False
        while True:
            line_bytes = response.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8").rstrip("\r\n")
            raw_lines.append(line)
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                done = True
                continue
            value = json.loads(data)
            require(isinstance(value, dict), "stream event is not an object")
            events.append(value)
        status = response.status
        connection.close()
        require(status == 200, f"stream request returned HTTP {status}")
        require(done, "stream ended without [DONE]")
        receipts = [event["cassi"] for event in events if isinstance(event.get("cassi"), dict)]
        require(receipts, "stream has no final Cassi receipt before [DONE]")
        return {
            "events": events,
            "raw_lines": raw_lines,
            "receipt": receipts[-1],
        }

    def disconnect_after_delta(self, prompt: str) -> None:
        connection = http.client.HTTPConnection(self.host, self.port, timeout=600.0)
        payload = json.dumps({
            "prompt": prompt,
            "n_predict": 32,
            "temperature": 0,
            "stream": True,
        }).encode("utf-8")
        connection.request("POST", self.prefix + "/completion", body=payload, headers={
            "content-type": "application/json",
            "accept": "text/event-stream",
        })
        response = connection.getresponse()
        require(response.status == 200, f"disconnect probe returned HTTP {response.status}")
        saw_delta = False
        for _ in range(128):
            line = response.readline()
            if not line:
                break
            if line.startswith(b"data: {") and b'"content"' in line:
                saw_delta = True
                break
        require(saw_delta, "disconnect probe produced no streamed delta")
        try:
            connection.sock.shutdown(socket.SHUT_RDWR) if connection.sock is not None else None
        except OSError:
            pass
        connection.close()


def receipt_from_response(body: dict[str, Any]) -> dict[str, Any]:
    receipt = body.get("cassi")
    require(isinstance(receipt, dict), "response has no Cassi receipt")
    return receipt


def assert_receipt(receipt: dict[str, Any], expected_teacher: str, model_sha256: str) -> None:
    require(receipt.get("schema") == "cassi.apprentice.receipt.v1", "receipt schema mismatch")
    require(receipt.get("model_sha256") == model_sha256, "receipt model identity mismatch")
    native_backends = receipt.get("native_backends")
    require(isinstance(native_backends, list) and native_backends == sorted(native_backends),
        "receipt native backends are not a known sorted list")
    require(receipt.get("status") == "complete", f"request receipt is not complete: {receipt.get('error_code')}")
    stats = receipt.get("stats", {})
    require(len(receipt.get("tokens", [])) == int(stats.get("committed_tokens", -1)), "receipt token count mismatch")
    categories = sum(int(stats.get(key, 0)) for key in (
        "field_exact_tokens", "field_interpolated_tokens", "teacher_guided_tokens"))
    require(categories == int(stats.get("committed_tokens", -1)), "receipt ownership categories do not partition tokens")
    if expected_teacher == "always":
        require(int(stats.get("full_teacher_queries", 0)) > 0, "teacher=always request did not query Qwen")
        require(int(stats.get("teacher_guided_tokens", 0)) == int(stats.get("committed_tokens", -1)),
            "teacher=always request was not teacher-guided")
    elif expected_teacher == "never":
        nonzero = {key: stats.get(key) for key in NATIVE_ZERO_KEYS if int(stats.get(key, 0)) != 0}
        require(not nonzero, f"teacher=never request performed native work: {nonzero}")
        require(int(stats.get("field_observations", 0)) == 0, "teacher=never request learned")


def chat_body(model_id: str, prompt: str, tokens: int, stream: bool = False) -> dict[str, Any]:
    return {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": tokens,
        "temperature": 0,
        "stream": stream,
    }


def chat(
    client: Client,
    model_id: str,
    model_sha256: str,
    prompt: str,
    tokens: int,
    expected_teacher: str,
) -> dict[str, Any]:
    status, body, raw = client.request("POST", "/v1/chat/completions", chat_body(model_id, prompt, tokens))
    require(status == 200, f"chat returned HTTP {status}: {raw}")
    receipt = receipt_from_response(body)
    assert_receipt(receipt, expected_teacher, model_sha256)
    choice = body.get("choices", [{}])[0]
    content = choice.get("message", {}).get("content", "")
    require(isinstance(content, str), "chat response content is not text")
    return {"content": content, "receipt": receipt, "body": body}


def native_completion(
    client: Client,
    model_sha256: str,
    prompt: str,
    tokens: int,
    expected_teacher: str,
    stop: str | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "prompt": prompt,
        "n_predict": tokens,
        "temperature": 0,
        "stream": False,
    }
    if stop is not None:
        request["stop"] = [stop]
    status, body, raw = client.request("POST", "/completion", request)
    require(status == 200, f"native completion returned HTTP {status}: {raw}")
    receipt = receipt_from_response(body)
    assert_receipt(receipt, expected_teacher, model_sha256)
    require(isinstance(body.get("content", ""), str), "native completion content is not text")
    return {"content": body.get("content", ""), "receipt": receipt, "body": body}


def slot_snapshot(client: Client) -> dict[str, Any] | None:
    status, body, raw = client.request("GET", "/slots")
    require(status == 200, f"slot snapshot returned HTTP {status}: {raw}")
    values = body.get("value")
    require(isinstance(values, list) and len(values) == 1, "apprentice server does not expose one slot")
    receipt = values[0].get("cassi")
    return receipt if isinstance(receipt, dict) else None


def assert_invalid_requests(client: Client, model_id: str) -> list[dict[str, Any]]:
    before = slot_snapshot(client)
    probes = [
        ("temperature", "/v1/chat/completions", {**chat_body(model_id, "x", 1), "temperature": 0.7}),
        ("logprobs", "/v1/chat/completions", {**chat_body(model_id, "x", 1), "logprobs": True}),
        ("n", "/v1/chat/completions", {**chat_body(model_id, "x", 1), "n": 2}),
        ("tools", "/v1/chat/completions", {**chat_body(model_id, "x", 1), "tools": []}),
        ("grammar", "/completion", {"prompt": "x", "n_predict": 1, "temperature": 0, "grammar": ""}),
        ("embeddings", "/v1/embeddings", {"model": model_id, "input": "x"}),
    ]
    rows: list[dict[str, Any]] = []
    for name, path, request in probes:
        status, body, raw = client.request("POST", path, request)
        require(status == 400, f"invalid {name} request returned HTTP {status}: {raw}")
        error = body.get("error", {})
        require(error.get("error_code") in ("apprentice_request_unsupported", "apprentice_endpoint_unsupported"),
            f"invalid {name} response lacks stable capability error: {raw}")
        rows.append({"case": name, "status": status, "error_code": error["error_code"]})
    after = slot_snapshot(client)
    require(before == after, "rejected requests changed the last completed field receipt")
    return rows


def wait_for_idle(client: Client, timeout: float = 120.0) -> dict[str, Any] | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, body, _ = client.request("GET", "/slots", timeout=30.0)
        if status == 200:
            values = body.get("value", [])
            if len(values) == 1 and not values[0].get("is_processing", True):
                receipt = values[0].get("cassi")
                return receipt if isinstance(receipt, dict) else None
        time.sleep(0.1)
    raise RuntimeError("server did not return to idle after disconnect")


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_path = Path(args.out).resolve()
    prior: dict[str, Any] | None = None
    if args.expect_teacher == "never":
        prior_path = Path(args.prior).resolve() if args.prior else output_path
        require(prior_path.is_file(), "teacher=never verification requires the prior teacher client receipt")
        loaded = json.loads(prior_path.read_text(encoding="utf-8"))
        require(isinstance(loaded, dict), "prior client receipt is malformed")
        prior = loaded

    model_path = Path(args.model).resolve()
    require(model_path.is_file(), f"expected model artifact does not exist: {model_path}")
    model_sha256 = sha256_path(model_path)
    client = Client(args.base_url)
    status, health, raw = client.request("GET", "/health", timeout=30.0)
    require(status == 200 and health.get("status") in ("ok", "no slot available"), f"health check failed: {raw}")
    status, models, raw = client.request("GET", "/v1/models", timeout=30.0)
    entries = models.get("data", [])
    require(status == 200 and isinstance(entries, list) and len(entries) == 1, f"model discovery failed: {raw}")
    model_id = entries[0].get("id")
    require(isinstance(model_id, str) and model_id, "served model identifier is missing")
    require(Path(model_id).name == model_path.name, "served model identifier does not match the expected artifact")
    if prior is not None:
        require(prior.get("served_model") == model_id, "served model identifier changed before teacher-free replay")
        require(prior.get("model_sha256") == model_sha256, "local model identity changed before teacher-free replay")

    prompts = {
        "nonstream": "Native apprentice nonstream probe.",
        "stream": "Native apprentice stream probe.",
        "utf8": "Café 雪 — reply briefly.",
        "concurrent_a": "Concurrent field request A.",
        "concurrent_b": "Concurrent field request B.",
        "stop": "Native apprentice stop-string probe.",
    }
    learned: dict[str, Any] = {}

    rounds = 2 if args.expect_teacher == "always" else 1
    for _ in range(rounds):
        nonstream = chat(client, model_id, model_sha256, prompts["nonstream"], 1, args.expect_teacher)
        streamed = client.stream(
            "/v1/chat/completions",
            chat_body(model_id, prompts["stream"], 2, stream=True),
        )
        assert_receipt(streamed["receipt"], args.expect_teacher, model_sha256)
        utf8 = chat(client, model_id, model_sha256, prompts["utf8"], 1, args.expect_teacher)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                name: executor.submit(
                    chat, client, model_id, model_sha256, prompts[name], 1, args.expect_teacher)
                for name in ("concurrent_a", "concurrent_b")
            }
            concurrent_rows = {name: future.result() for name, future in futures.items()}
        stop_baseline = native_completion(
            client, model_sha256, prompts["stop"], 4, args.expect_teacher)
        learned = {
            "nonstream": nonstream,
            "stream": streamed,
            "utf8": utf8,
            "concurrent_a": concurrent_rows["concurrent_a"],
            "concurrent_b": concurrent_rows["concurrent_b"],
            "stop": stop_baseline,
        }

    require(len(learned["nonstream"]["receipt"]["tokens"]) <= 1, "one-token limit was exceeded")
    require("Café" in prompts["utf8"] and prompts["utf8"].encode("utf-8").decode("utf-8") == prompts["utf8"],
        "UTF-8 probe did not round-trip locally")

    stop_content = learned["stop"]["content"]
    stop_string = next((character for character in stop_content if character), None)
    stop_result: dict[str, Any]
    if stop_string is not None:
        stopped = native_completion(
            client, model_sha256, prompts["stop"], 4, args.expect_teacher, stop=stop_string)
        require(stop_string not in stopped["content"], "stop string leaked into completion content")
        stop_result = {"stop": stop_string, "response": stopped}
    else:
        stop_result = {"stop": None, "response": learned["stop"], "note": "generated text was empty"}

    invalid = assert_invalid_requests(client, model_id)

    if prior is not None:
        prior_learned = prior.get("learned", {})
        for name in ("nonstream", "stream", "utf8", "concurrent_a", "concurrent_b", "stop"):
            expected_tokens = prior_learned.get(name, {}).get("receipt", {}).get("tokens")
            actual_tokens = learned[name]["receipt"]["tokens"]
            require(expected_tokens == actual_tokens, f"teacher-free retained trajectory changed for {name}")

    cancellation: dict[str, Any] | None = None
    if args.expect_teacher == "always":
        client.disconnect_after_delta("Cassi apprentice cancellation probe with enough continuation.")
        cancelled = wait_for_idle(client)
        require(isinstance(cancelled, dict) and cancelled.get("status") == "cancelled",
            "disconnect did not produce a copied cancelled receipt")
        require(cancelled.get("durable") is True, "cancelled request did not publish accepted observations")
        require(cancelled.get("model_sha256") == model_sha256, "cancelled receipt model identity mismatch")
        cancellation = cancelled

    result = {
        "schema": "cassi.apprentice.server-client.v1",
        "verdict": "PASS",
        "base_url": args.base_url,
        "model": str(model_path),
        "served_model": model_id,
        "model_sha256": model_sha256,
        "expect_teacher": args.expect_teacher,
        "learned": learned,
        "stop": stop_result,
        "invalid_requests": invalid,
        "cancellation": cancellation,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--prior")
    parser.add_argument("--expect-teacher", choices=("always", "never"), default="always")
    return parser.parse_args()


def main() -> int:
    try:
        result = run(parse_args())
        print(json.dumps({
            "schema": result["schema"],
            "verdict": result["verdict"],
            "expect_teacher": result["expect_teacher"],
            "invalid_requests": len(result["invalid_requests"]),
            "cancelled": result["cancellation"] is not None,
        }, separators=(",", ":")))
        return 0
    except (OSError, ValueError, RuntimeError, http.client.HTTPException) as error:
        print(json.dumps({
            "schema": "cassi.apprentice.server-client.v1",
            "verdict": "FAIL",
            "error": str(error),
        }, separators=(",", ":")), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
