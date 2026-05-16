"""
CassiCore Context Engine for Hermes Agent.

Sends Hermes' message history to CassiCore's Thalamus for scoring,
compression, distillation, and cognitive enrichment before each LLM call.
The Thalamus decides what messages survive, what gets compressed, and
what gets dropped based on 6-axis luminance scoring.

Enable by setting ``context.engine: cassicore`` in Hermes' config.yaml.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
from http.client import HTTPConnection
from typing import Any

from agent.context_engine import ContextEngine

logger = logging.getLogger("hermes.context_engine.cassicore")

CASSICORE_URL = os.environ.get("CASSICORE_URL", "http://localhost:7433")
_SESSION_ID: str | None = None
_MAX_RETRIES = 2
_RETRY_DELAY = 0.5


def _api(method: str, path: str, body: dict | None = None, timeout: float = 10.0) -> Any | None:
    """Call the CassiCore admin API with basic retry."""
    parsed = urllib.parse.urlparse(CASSICORE_URL)
    if parsed.scheme != "http":
        logger.warning("CassiCore URL scheme %s not supported", parsed.scheme)
        return None

    for attempt in range(_MAX_RETRIES):
        conn: HTTPConnection | None = None
        try:
            conn = HTTPConnection(parsed.hostname, parsed.port or 7433, timeout=timeout)
            payload = json.dumps(body).encode() if body else b""
            headers = {"Content-Type": "application/json"} if body else {}
            conn.request(method, path, body=payload, headers=headers)
            resp = conn.getresponse()
            data = resp.read().decode()
            return json.loads(data) if data else None
        except Exception as exc:
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY)
            else:
                logger.debug("CassiCore API call failed: %s", exc)
                return None
        finally:
            if conn:
                conn.close()
    return None


class CassiCoreContextEngine(ContextEngine):
    """Context engine that delegates compression to CassiCore's Thalamus."""

    name = "cassicore"

    threshold_percent = 0.60
    protect_first_n = 3
    protect_last_n = 6

    def __init__(self) -> None:
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_total_tokens = 0
        self.threshold_tokens = 0
        self.context_length = 0
        self.compression_count = 0

    def update_from_response(self, usage: dict[str, Any]) -> None:
        self.last_prompt_tokens = usage.get("prompt_tokens", 0)
        self.last_completion_tokens = usage.get("completion_tokens", 0)
        self.last_total_tokens = self.last_prompt_tokens + self.last_completion_tokens
        self.threshold_tokens = int(self.last_prompt_tokens * self.threshold_percent)
        self.context_length = usage.get("context_length", 200_000)

    def should_compress(self, prompt_tokens: int | None = None) -> bool:
        tokens = prompt_tokens if prompt_tokens is not None else self.last_prompt_tokens
        return tokens > self.threshold_tokens > 0

    def should_compress_preflight(self, messages: list[dict[str, Any]]) -> bool:
        return sum(len(str(m.get("content", ""))) for m in (messages or [])) > 30_000

    def has_content_to_compress(self, messages: list[dict[str, Any]]) -> bool:
        return sum(len(str(m.get("content", ""))) for m in (messages or [])) > 10_000

    def compress(
        self,
        messages: list[dict[str, Any]],
        current_tokens: int | None = None,
        focus_topic: str | None = None,
    ) -> list[dict[str, Any]]:
        if not messages:
            return messages

        session_id = _SESSION_ID or f"hermes-auto-{int(time.time())}"
        body: dict[str, Any] = {"sessionId": session_id, "messages": messages}
        if focus_topic:
            body["config"] = {"focusTopic": focus_topic}

        result = _api("POST", "/context/curate", body, timeout=30.0)
        if result and isinstance(result, dict):
            curated = result.get("messages")
            if curated and isinstance(curated, list) and len(curated) > 0:
                self.compression_count += 1
                original = (result.get("meta") or {}).get("originalChars", 0)
                curated_chars = (result.get("meta") or {}).get("curatedChars", 0)
                if original > 0 and curated_chars > 0:
                    logger.info(
                        "Thalamus curated %d -> %d messages (%.0f%% chars kept)",
                        len(messages), len(curated), curated_chars / original * 100,
                    )
                return curated

        logger.debug("Thalamus curation unavailable, using original messages")
        return messages

    def on_session_start(self, session_id: str, **kwargs: Any) -> None:
        global _SESSION_ID
        _SESSION_ID = f"hermes:{session_id}"

    def on_session_end(self, session_id: str, messages: list[dict[str, Any]] | None = None) -> None:
        global _SESSION_ID
        _SESSION_ID = None


def register(collector: Any) -> None:
    collector.register_context_engine(CassiCoreContextEngine())
