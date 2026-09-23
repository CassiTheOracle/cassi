"""Semantic event bridge from the hive to CassiCore and CassiCosmos.

The bridge transports bounded, provenance-carrying events only.  It never sends
adaptive field tensors or silently mutates a remote process.  Network delivery
is opt-in; callers can use the deterministic wire payloads with an existing
loopback channel or inject a test sink.
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from cassi_field_atlas import canonical_json_bytes, sha256_value


BRIDGE_SCHEMA = "cassifi.hive.semantic-bridge.v1"


class SemanticBridgeError(RuntimeError):
    """Raised when a semantic bridge event cannot be encoded or delivered."""


def _text(value: Any, label: str, limit: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > limit or any(ord(char) < 32 for char in value):
        raise SemanticBridgeError(f"{label} must be bounded nonempty text")
    return value


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SemanticBridgeError(f"{label} must be a mapping")
    try:
        normalized = json.loads(canonical_json_bytes(value).decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise SemanticBridgeError(f"{label} must be canonical JSON") from exc
    if not isinstance(normalized, dict):
        raise SemanticBridgeError(f"{label} must encode an object")
    return normalized


@dataclass(frozen=True, slots=True)
class SemanticEvent:
    event_id: str
    source_instance_id: str
    event_type: str
    payload: Mapping[str, Any]
    causality_ids: tuple[str, ...] = ()
    session_id: str | None = None
    created_ns: int = 0

    def __post_init__(self) -> None:
        _text(self.event_id, "event_id")
        _text(self.source_instance_id, "source_instance_id")
        _text(self.event_type, "event_type")
        object.__setattr__(self, "payload", _mapping(self.payload, "payload"))
        if isinstance(self.causality_ids, (str, bytes)):
            raise SemanticBridgeError("causality_ids must be a sequence")
        object.__setattr__(self, "causality_ids", tuple(_text(item, "causality id") for item in self.causality_ids))
        if self.session_id is not None:
            _text(self.session_id, "session_id")
        if isinstance(self.created_ns, bool) or not isinstance(self.created_ns, int) or self.created_ns < 0:
            raise SemanticBridgeError("created_ns must be a nonnegative integer")

    @classmethod
    def create(
        cls,
        *,
        source_instance_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        causality_ids: tuple[str, ...] = (),
        session_id: str | None = None,
    ) -> "SemanticEvent":
        created_ns = time.time_ns()
        event_id = sha256_value(
            {
                "created_ns": created_ns,
                "event_type": event_type,
                "payload": payload,
                "source_instance_id": source_instance_id,
            }
        )
        return cls(
            event_id=event_id,
            source_instance_id=source_instance_id,
            event_type=event_type,
            payload=payload,
            causality_ids=causality_ids,
            session_id=session_id,
            created_ns=created_ns,
        )

    @property
    def content(self) -> Mapping[str, Any]:
        return {
            "causality_ids": list(self.causality_ids),
            "created_ns": self.created_ns,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": dict(self.payload),
            "schema": BRIDGE_SCHEMA,
            "session_id": self.session_id,
            "source_instance_id": self.source_instance_id,
        }

    @property
    def content_sha256(self) -> str:
        return sha256_value(self.content)

    def as_dict(self) -> Mapping[str, Any]:
        return {"content": self.content, "content_sha256": self.content_sha256, "event_id": self.event_id, "schema": BRIDGE_SCHEMA}

    def cassicore_payload(self) -> Mapping[str, Any]:
        """Payload accepted by CassiCore `/v1/events/push`."""
        return {
            "type": "cassi.hive." + self.event_type,
            "payload": self.as_dict(),
            "sessionId": self.session_id,
        }

    def cosmos_payload(self) -> Mapping[str, Any]:
        """Read-only semantic command envelope for the 7599 bridge.

        CassiCosmos intentionally accepts only its physics commands.  This
        envelope therefore uses a ``snapshot`` label and is suitable for a
        caller that has mapped the event to a physical deposit; it never
        guesses coordinates or injects a field mutation itself.
        """
        return {
            "cmd": "snapshot",
            "label": f"hive-{self.event_type}-{self.event_id[:16]}",
            "hive_event_id": self.event_id,
            "hive_payload_sha256": self.content_sha256,
        }


class SemanticEventBridge:
    """Fan-out bridge with deterministic payloads and injectable sinks."""

    def __init__(self, sinks: tuple[Callable[[SemanticEvent], Any], ...] = ()) -> None:
        self.sinks = tuple(sinks)
        self.events: list[SemanticEvent] = []

    def emit(self, event: SemanticEvent) -> SemanticEvent:
        if not isinstance(event, SemanticEvent):
            raise SemanticBridgeError("emit requires a SemanticEvent")
        for sink in self.sinks:
            sink(event)
        self.events.append(event)
        return event

    def emit_outcome(
        self,
        *,
        source_instance_id: str,
        bundle_id: str,
        outcome: Mapping[str, Any],
        causality_ids: tuple[str, ...] = (),
        session_id: str | None = None,
    ) -> SemanticEvent:
        return self.emit(
            SemanticEvent.create(
                source_instance_id=source_instance_id,
                event_type="adoption-outcome",
                payload={"bundle_id": bundle_id, "outcome": dict(outcome)},
                causality_ids=causality_ids,
                session_id=session_id,
            )
        )
    def emit_population(
        self,
        *,
        source_instance_id: str,
        bundle_id: str,
        ledger: Mapping[str, Any],
        causality_ids: tuple[str, ...] = (),
        session_id: str | None = None,
    ) -> SemanticEvent:
        return self.emit(
            SemanticEvent.create(
                source_instance_id=source_instance_id,
                event_type="population-outcome",
                payload={"bundle_id": bundle_id, "ledger": dict(ledger)},
                causality_ids=causality_ids,
                session_id=session_id,
            )
        )


class CassiCoreEventBridge:
    """Opt-in HTTP client for the existing CassiCore loopback event seam."""

    def __init__(self, endpoint: str = "http://127.0.0.1:7273/v1/events/push", token: str | None = None, timeout: float = 5.0) -> None:
        self.endpoint = _text(endpoint, "endpoint")
        self.token = token
        if timeout <= 0:
            raise SemanticBridgeError("timeout must be positive")
        self.timeout = float(timeout)

    def __call__(self, event: SemanticEvent) -> Mapping[str, Any]:
        body = json.dumps(event.cassicore_payload(), separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(self.endpoint, data=body, method="POST", headers={"Content-Type": "application/json"})
        if self.token:
            request.add_header("Authorization", "Bearer " + self.token)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise SemanticBridgeError("CassiCore event delivery failed") from exc


class CassiCosmosEventBridge:
    """Opt-in loopback client for a read-only Cosmos snapshot marker."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7599, timeout: float = 5.0) -> None:
        self.host = _text(host, "host")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise SemanticBridgeError("port is invalid")
        self.port = port
        if timeout <= 0:
            raise SemanticBridgeError("timeout must be positive")
        self.timeout = float(timeout)

    def __call__(self, event: SemanticEvent) -> Mapping[str, Any]:
        payload = (json.dumps(event.cosmos_payload(), separators=(",", ":")) + "\n").encode("utf-8")
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as connection:
                connection.sendall(payload)
                data = connection.recv(1024 * 1024)
            result = json.loads(data.decode("utf-8").strip())
        except (OSError, json.JSONDecodeError) as exc:
            raise SemanticBridgeError("CassiCosmos event delivery failed") from exc
        if not isinstance(result, Mapping):
            raise SemanticBridgeError("CassiCosmos returned a non-object response")
        return result


__all__ = [
    "BRIDGE_SCHEMA",
    "CassiCoreEventBridge",
    "CassiCosmosEventBridge",
    "SemanticBridgeError",
    "SemanticEvent",
    "SemanticEventBridge",
]
