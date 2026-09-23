"""Read-only Surface projection of a canonical Cassi trading paper view."""

from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .records import (
    MAX_ACCESSIBILITY_BYTES,
    SurfaceCapabilityError,
    SurfaceConflictError,
    SurfaceValidationError,
    canonical_json,
)


APPLICATION_VIEW_FILENAME = "trading-paper-application.json"
APPLICATION_BINDING_FILENAME = "trading-paper-application-binding.json"
APPLICATION_VIEW_SCHEMA = "cassi.trading-paper-application.v1"
APPLICATION_BINDING_SCHEMA = "cassi.trading-paper-application-binding.v1"
ENTITY_PROGRAM_ATTESTATION_SCHEMA = "cassi.trading-entity-program-attestation.v1"
ENTITY_PROGRAM_VERIFICATION_SCHEMA = "cassi.trading-entity-program-verification.v1"
_MAX_APPLICATION_BYTES = 4 << 20
_SOURCE_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_:-]{0,95}$")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _read_document(path: Path, schema: str) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise SurfaceValidationError("paper application document is unavailable") from exc
    if len(payload) > _MAX_APPLICATION_BYTES:
        raise SurfaceValidationError("paper application document exceeds its size limit")
    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise SurfaceValidationError("paper application document is not valid JSON") from exc
    if not isinstance(document, Mapping):
        raise SurfaceValidationError("paper application document must be an object")
    body = dict(document)
    stated = body.pop("content_sha256", None)
    if document.get("schema") != schema or stated != _digest(body):
        raise SurfaceValidationError("paper application document schema or digest mismatch")
    return dict(document)


def _timestamp_ns(value: Any) -> int:
    if not isinstance(value, str) or len(value) > 128:
        raise SurfaceValidationError("paper application timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone is required")
        parsed = parsed.astimezone(timezone.utc)
    except (OverflowError, TypeError, ValueError) as exc:
        raise SurfaceValidationError("paper application timestamp is invalid") from exc
    delta = parsed - datetime(1970, 1, 1, tzinfo=timezone.utc)
    result = ((delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds) * 1_000
    if not 0 < result <= (1 << 63) - 1:
        raise SurfaceValidationError("paper application timestamp is outside the supported range")
    return result


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SurfaceValidationError(f"paper application {label} is missing")
    return value


def _plain_text(value: Any, *, limit: int = 256) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(value, ".8g") if math.isfinite(value) else "Unavailable"
    if isinstance(value, str):
        text = " ".join(value.split())
        return text[:limit] if text else "Unavailable"
    return "Unavailable"


def _text_node(name: str, value: Any) -> dict[str, Any]:
    return {"role": "text", "name": name, "value": _plain_text(value)}


def _group(name: str, children: list[dict[str, Any]]) -> dict[str, Any]:
    return {"role": "group", "name": name, "children": children}


def _reason_codes(value: Any) -> str:
    if not isinstance(value, (list, tuple)):
        return "None reported"
    codes: list[str] = []
    for row in value[:16]:
        code = row.get("code") if isinstance(row, Mapping) else row
        if isinstance(code, str) and _SOURCE_CODE.fullmatch(code):
            codes.append(code)
    return ", ".join(codes)[:512] if codes else "None reported"


class TradingPaperSurfaceBackend:
    """Expose one digest-verified paper member as bounded accessibility only."""

    backend_id = "trading-paper"
    source_id = "paper-account"

    def __init__(self, view_path: Path) -> None:
        path = Path(view_path).expanduser().resolve()
        if path.name != APPLICATION_VIEW_FILENAME:
            raise SurfaceValidationError(
                f"paper view must be named {APPLICATION_VIEW_FILENAME}"
            )
        self.view_path = path
        self.binding_path = path.with_name(APPLICATION_BINDING_FILENAME)
        self._lock = threading.RLock()
        self._closed = False
        initial = self._read_snapshot()
        identity = canonical_json(
            {"binding": initial["binding"], "attestation": initial["attestation"]}
        )
        self._identity_digest = hashlib.sha256(identity).hexdigest()
        self._source_instance = hashlib.sha256(
            b"trading-paper-source\0" + identity
        ).hexdigest()[:32]
        self._environment_incarnation = hashlib.sha256(
            b"trading-paper-environment\0" + identity
        ).hexdigest()[:32]

    def _read_snapshot(self) -> dict[str, Any]:
        view = _read_document(self.view_path, APPLICATION_VIEW_SCHEMA)
        binding_document = _read_document(
            self.binding_path, APPLICATION_BINDING_SCHEMA
        )
        binding = _mapping(view.get("binding"), "identity binding")
        durable_binding = _mapping(binding_document.get("binding"), "durable binding")
        if dict(binding) != dict(durable_binding):
            raise SurfaceValidationError("paper view and durable member binding disagree")
        for key in (
            "consumer_id",
            "ingestion_database",
            "member_home",
            "member_id",
            "original_mission_id",
            "paper_state_path",
            "symbol",
        ):
            value = binding.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > 1024:
                raise SurfaceValidationError("paper member binding is incomplete")

        attestation = _mapping(
            binding_document.get("entity_program_attestation"),
            "entity program attestation",
        )
        if (
            attestation.get("schema") != ENTITY_PROGRAM_ATTESTATION_SCHEMA
            or not isinstance(attestation.get("program_id"), str)
            or not attestation.get("program_id").strip()
            or len(attestation.get("program_id")) > 512
            or attestation.get("original_mission_id") != binding.get("original_mission_id")
            or not isinstance(attestation.get("mission_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", attestation.get("mission_sha256"))
        ):
            raise SurfaceValidationError("durable entity program attestation is invalid")
        entity_program = _mapping(view.get("entity_program"), "entity program")
        if entity_program.get("pinned_attestation") != dict(attestation):
            raise SurfaceValidationError("paper view and durable entity attestation disagree")
        verification = _mapping(
            entity_program.get("verification_at_action_time"),
            "entity program verification",
        )
        scopes = _mapping(verification.get("scopes"), "entity program scopes")
        if (
            verification.get("schema") != ENTITY_PROGRAM_VERIFICATION_SCHEMA
            or verification.get("program_id") != attestation.get("program_id")
            or verification.get("mission_sha256") != attestation.get("mission_sha256")
            or verification.get("member_home") != binding.get("member_home")
            or verification.get("ingestion_database") != binding.get("ingestion_database")
            or scopes.get("member_home") is not True
            or scopes.get("ingestion_database") is not True
            or not isinstance(verification.get("status"), str)
        ):
            raise SurfaceValidationError("paper view entity verification does not match its member")

        control = _mapping(view.get("control"), "control boundary")
        paper = _mapping(view.get("paper"), "paper account")
        source = _mapping(view.get("source"), "market source")
        field = _mapping(view.get("field"), "field status")
        _mapping(paper.get("account"), "paper account balance")
        if (
            view.get("paper_only") is not True
            or view.get("external_effect") != "none"
            or control.get("mode") != "paper-only"
            or control.get("permission_scope") != "simulated-paper-account-only"
            or control.get("external_order_path") is not False
            or control.get("external_order_permission") is not False
            or paper.get("paper_only") is not True
            or paper.get("external_effect") != "none"
            or paper.get("consumer_id") != binding.get("consumer_id")
            or paper.get("symbol") != binding.get("symbol")
            or field.get("symbol") != binding.get("symbol")
            or source.get("kind") != "canonical-market-ingestion"
            or source.get("database") != binding.get("ingestion_database")
        ):
            raise SurfaceValidationError("paper view does not satisfy the paper-only member contract")

        sample_time_ns = _timestamp_ns(view.get("written_at"))
        identity = canonical_json(
            {"binding": dict(binding), "attestation": dict(attestation)}
        )
        return {
            "view": view,
            "binding": dict(binding),
            "attestation": dict(attestation),
            "identity_digest": hashlib.sha256(identity).hexdigest(),
            "content_sha256": view["content_sha256"],
            "sample_time_ns": sample_time_ns,
        }

    def _snapshot(self) -> dict[str, Any]:
        if self._closed:
            raise SurfaceCapabilityError("paper Surface source is closed")
        snapshot = self._read_snapshot()
        if snapshot["identity_digest"] != self._identity_digest:
            raise SurfaceConflictError("paper member identity changed; register its view again")
        return snapshot

    def _binding(self) -> dict[str, Any]:
        self._snapshot()
        return {
            "backend_id": self.backend_id,
            "source_id": self.source_id,
            "source_instance": self._source_instance,
            "source_epoch": 1,
            "environment_incarnation": self._environment_incarnation,
            "geometry_revision": 0,
            "width": 0,
            "height": 0,
            "operations": [],
            "modalities": ["accessibility"],
            "capture_modalities": ["accessibility"],
            "capture_state": "live",
            "input_state": "unavailable",
            "backend_version": "cassi.trading-paper-surface.v1",
        }

    def describe(self) -> dict[str, Any]:
        with self._lock:
            binding = self._binding()
            return {
                "backend_id": self.backend_id,
                "environment_incarnation": self._environment_incarnation,
                "source": binding,
                "capabilities": {
                    "accessibility": {"status": "supported", "format": "bounded-json-utf8"},
                    "visual": {"status": "unavailable", "reason": "paper view publishes no pixels"},
                    "controls": {"status": "unavailable", "operations": []},
                },
            }

    def sources(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._binding()]

    def bind(self, source_id: str) -> dict[str, Any]:
        with self._lock:
            if source_id != self.source_id:
                raise SurfaceCapabilityError("paper Surface source is unavailable")
            return self._binding()

    def revalidate(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            current = self._binding()
            valid = isinstance(binding, Mapping) and all(
                binding.get(key) == current[key]
                for key in (
                    "source_id",
                    "source_instance",
                    "source_epoch",
                    "environment_incarnation",
                    "geometry_revision",
                )
            )
            return {
                "supported": True,
                "valid": valid,
                "reason": None if valid else "paper source identity changed",
                **current,
            }

    def capture(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            snapshot = self._snapshot()
            current = self._binding()
            if not isinstance(binding, Mapping) or any(
                binding.get(key) != current[key]
                for key in (
                    "source_id",
                    "source_instance",
                    "source_epoch",
                    "environment_incarnation",
                    "geometry_revision",
                )
            ):
                raise SurfaceConflictError("paper Surface binding is stale")
            requested = binding.get("_surface_requested_modalities", ("accessibility",))
            if set(requested) != {"accessibility"}:
                raise SurfaceCapabilityError("paper Surface source supports accessibility only")
            accessibility = self._accessibility(snapshot)
            if len(canonical_json(accessibility)) > MAX_ACCESSIBILITY_BYTES:
                raise SurfaceValidationError("paper accessibility view exceeds its size limit")
            return {
                "source_id": self.source_id,
                "source_instance": self._source_instance,
                "source_epoch": 1,
                "environment_incarnation": self._environment_incarnation,
                "geometry_revision": 0,
                "sequence": snapshot["sample_time_ns"],
                "width": 0,
                "height": 0,
                "pixel_format": "none",
                "sample_time_ns": snapshot["sample_time_ns"],
                "sample_clock_domain": "utc-wall",
                "sample_time_uncertainty_ns": 1_000,
                "accessibility_sample_time_ns": snapshot["sample_time_ns"],
                "receipt_time_ns": time.monotonic_ns(),
                "receipt_clock_domain": "host-monotonic",
                "coverage": {"complete": True},
                "provenance": f"paper-application-sha256:{snapshot['content_sha256']}",
                "accessibility": accessibility,
            }

    @staticmethod
    def _accessibility(snapshot: Mapping[str, Any]) -> dict[str, Any]:
        view = snapshot["view"]
        source = view["source"]
        source_health = source.get("health_at_action_time")
        source_health = source_health if isinstance(source_health, Mapping) else {}
        field = view["field"]
        paper = view["paper"]
        account = paper["account"]
        paper_health = paper.get("health")
        paper_health = paper_health if isinstance(paper_health, Mapping) else {}
        entity_program = view["entity_program"]
        verification = entity_program["verification_at_action_time"]
        control = view["control"]
        accepted_bar = source.get("latest_accepted_bar")
        accepted_bar = accepted_bar if isinstance(accepted_bar, Mapping) else {}
        positions = account.get("positions")
        position_count = len(positions) if isinstance(positions, Mapping) else "Unavailable"
        pending = paper.get("pending_order")
        pending_state = (
            "None"
            if pending is None
            else _plain_text(pending.get("status", pending.get("side", "Pending")))
            if isinstance(pending, Mapping)
            else "Pending"
        )
        target = field.get("target")
        target = target if isinstance(target, Mapping) else {}
        risk = field.get("risk")
        risk = risk if isinstance(risk, Mapping) else {}
        uncertainty = field.get("uncertainty")
        uncertainty = uncertainty if isinstance(uncertainty, Mapping) else {}
        last_event = paper.get("last_event")
        last_event = last_event if isinstance(last_event, Mapping) else {}
        children = [
            _group(
                "Market data",
                [
                    _text_node("Symbol", snapshot["binding"]["symbol"]),
                    _text_node("Feed health at last action", source_health.get("state")),
                    _text_node("Feed warnings", _reason_codes(source_health.get("reasons"))),
                    _text_node("Latest accepted candle", accepted_bar.get("observed_at")),
                ],
            ),
            _group(
                "Field decision",
                [
                    _text_node("Bars processed", field.get("bar_count")),
                    _text_node("Decisions made", field.get("decision_count")),
                    _text_node("Requested exposure", target.get("requested")),
                    _text_node("Applied exposure", target.get("applied")),
                    _text_node("Risk state", risk.get("risk_state", target.get("risk_state"))),
                    _text_node(
                        "Uncertainty state",
                        uncertainty.get("uncertainty_state", target.get("uncertainty_state")),
                    ),
                ],
            ),
            _group(
                "Simulated paper account",
                [
                    _text_node("Account equity", account.get("equity")),
                    _text_node("Cash", account.get("cash")),
                    _text_node("Open positions", position_count),
                    _text_node("Causal fills", paper.get("causal_fill_count")),
                    _text_node("Pending paper intent", pending_state),
                    _text_node("Latest event", last_event.get("disposition")),
                    _text_node("Paper health", paper_health.get("state")),
                ],
            ),
            _group(
                "Safety and provenance",
                [
                    _text_node("Entity program", snapshot["attestation"]["program_id"]),
                    _text_node("Program status at last action", verification.get("status")),
                    _text_node(
                        "Paper exposure permitted at last action",
                        control.get("paper_exposure_permitted_at_action_time"),
                    ),
                    _text_node("External orders", "Disabled"),
                    _text_node("View updated", view.get("written_at")),
                    _text_node("Application view SHA-256", snapshot["content_sha256"]),
                ],
            ),
        ]
        return {"role": "application", "name": "Cassi trading paper account", "children": children}

    def dispatch(self, _binding: Mapping[str, Any], _action: Mapping[str, Any]) -> dict[str, Any]:
        raise SurfaceCapabilityError("trading paper Surface is read-only")

    @staticmethod
    def neutralize(_binding: Mapping[str, Any]) -> dict[str, Any]:
        return {"confirmed": True, "detail": "paper source has no control channel"}

    def close(self) -> None:
        with self._lock:
            self._closed = True
