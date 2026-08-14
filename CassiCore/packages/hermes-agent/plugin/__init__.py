"""
CassiCore lifecycle hooks for Hermes Agent.

Fires session/turn lifecycle events into CassiCore's event system so
the cognitive modules (Reverie, Thinker, Thalamus, MnemicField) can
track Hermes activity alongside Claude Code and OpenCode sessions.

Three hooks:
  on_session_start -- creates CassiCore session, seeds Aurora
  on_session_end   -- emits session:end event
  post_tool_call   -- emits tool:round-complete event
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
from http.client import HTTPConnection
from typing import Any

logger = logging.getLogger("hermes.plugin.cassicore")

CASSICORE_URL = os.environ.get("CASSICORE_URL", "http://localhost:7433")
_SESSION_SEEN: set[str] = set()


def _api(method: str, path: str, body: dict | None = None, timeout: float = 2.0) -> Any | None:
    """Fire-and-forget HTTP call to the CassiCore admin API."""
    parsed = urllib.parse.urlparse(CASSICORE_URL)
    if parsed.scheme != "http":
        return None
    conn: HTTPConnection | None = None
    try:
        conn = HTTPConnection(parsed.hostname, parsed.port or 7433, timeout=timeout)
        payload = json.dumps(body).encode() if body else b""
        headers = {"Content-Type": "application/json"} if body else {}
        conn.request(method, path, body=payload, headers=headers)
        resp = conn.getresponse()
        data = resp.read().decode()
        return json.loads(data) if data else None
    except Exception:
        logger.debug("CassiCore API call failed (non-fatal)", exc_info=True)
        return None
    finally:
        if conn:
            conn.close()


def _ensure_cassicore_session(session_id: str) -> str:
    """Create or retrieve the CassiCore session ID for this Hermes session.

    Only emits session:created once per Hermes session ID.
    """
    cid = f"hermes:{session_id}"
    if cid in _SESSION_SEEN:
        return cid
    _SESSION_SEEN.add(cid)

    _api("POST", "/events/ingest", {
        "sessionId": cid,
        "events": [{
            "type": "session:created",
            "sessionId": cid,
            "channelId": "channel:hermes",
            "source": "hermes",
            "timestamp": int(time.time() * 1000),
        }],
    })
    return cid


def _on_session_start(session_id: str, **kwargs: Any) -> None:
    cid = _ensure_cassicore_session(session_id)
    platform = kwargs.get("platform", "cli")
    model = kwargs.get("model", "")
    logger.info("CassiCore session started: %s (Hermes: %s)", cid, session_id)

    _api("POST", "/cortex/signal", {
        "sessionId": cid, "type": "perception", "region": "sensory",
        "content": f"Hermes session started ({platform}, model: {model})",
        "tags": ["hermes", "session-start", platform], "author": "hermes-plugin", "salience": 0.6,
    })

    _api("POST", "/lamina/create", {
        "label": "session-decisions", "content": "",
        "description": "Key decisions made during this Hermes session",
        "owner": "hermes", "scope": {"kind": "session", "sessionId": cid},
        "tags": ["hermes", "session"], "charLimit": 4000,
    })

    _api("POST", "/intelligence/aurora/observe", {
        "text": f"Hermes session started. Platform: {platform}. Awaiting user prompt.",
    }, timeout=1.0)


def _on_session_end(session_id: str, messages: list[dict] | None = None) -> None:
    cid = f"hermes:{session_id}"
    logger.info("CassiCore session ended: %s", cid)

    _api("POST", "/events/ingest", {
        "sessionId": cid,
        "events": [{"type": "session:end", "sessionId": cid, "source": "hermes", "timestamp": int(time.time() * 1000)}],
    })
    _api("POST", "/cortex/signal", {
        "sessionId": cid, "type": "decision", "region": "executive",
        "content": "Hermes session ended", "tags": ["hermes", "session-end"],
        "author": "hermes-plugin", "salience": 0.7,
    })
    _SESSION_SEEN.discard(cid)


def _on_post_tool_call(
    tool_name: str,
    tool_args: dict | None = None,
    result: str | None = None,
    is_error: bool = False,
    session_id: str | None = None,
    **kwargs: Any,
) -> None:
    if not session_id:
        return
    _api("POST", "/events/ingest", {
        "sessionId": f"hermes:{session_id}",
        "events": [{
            "type": "tool:round-complete", "toolName": tool_name,
            "isError": is_error, "resultPreview": (result or "")[:500],
            "source": "hermes", "timestamp": int(time.time() * 1000),
        }],
    })


def register(ctx: Any) -> None:
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    logger.info("CassiCore lifecycle hooks registered")
