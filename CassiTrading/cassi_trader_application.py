"""Host-owned paper application view for the persistent Cassi trading field.

This module projects the existing field, canonical source health, and paper
consumer into a durable read-only application boundary. It has no exchange or
Surface backend capability.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from http.client import HTTPException
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


APPLICATION_VIEW_SCHEMA = "cassi.trading-paper-application.v1"
APPLICATION_VIEW_FILENAME = "trading-paper-application.json"
APPLICATION_BINDING_SCHEMA = "cassi.trading-paper-application-binding.v1"
APPLICATION_BINDING_FILENAME = "trading-paper-application-binding.json"
ENTITY_PROGRAM_VERIFICATION_SCHEMA = "cassi.trading-entity-program-verification.v1"
ENTITY_PROGRAM_ATTESTATION_SCHEMA = "cassi.trading-entity-program-attestation.v1"
ENTITY_PROGRAM_RESPONSE_MAX_BYTES = 8 * 1024 * 1024
_ENTITY_PROGRAM_MAX_ROOTS = 64
_HEALTH_METRICS = (
    "heartbeat_at",
    "heartbeat_age_seconds",
    "market_at",
    "market_age_seconds",
    "reconcile_at",
    "reconcile_age_seconds",
    "latest_market_event_type",
    "latest_market_observed_at",
    "latest_market_received_at",
    "exchange_to_receipt_wall_delta_seconds",
    "exchange_clock_lead_lower_bound_seconds",
    "latest_bar_available_at",
    "candle_close_to_receipt_wall_delta_seconds",
    "latest_bar_start",
    "bar_gap_count",
    "unresolved_conflicts",
    "consumer_backlog",
    "disk_free_bytes",
)
_AGE_METRICS = (
    "heartbeat_age_seconds",
    "market_age_seconds",
    "reconcile_age_seconds",
)
_REASON_DETAILS = ("age_seconds", "count", "free_bytes", "wall_delta_seconds")
_EVENT_FIELDS = (
    "canonical_event_id",
    "event_id",
    "source_id",
    "source_revision",
    "event_type",
    "subject_id",
    "observed_at",
    "available_at",
    "payload_sha256",
    "trading_bar_event_id",
    "bar_event_id",
    "decision_event_id",
    "field_decision_event_id",
    "paper_receipt_event_id",
    "disposition",
    "execution_model",
    "content_sha256",
)
_DECISION_FIELDS = (
    "symbol",
    "bar_event_id",
    "timestamp",
    "target",
    "value",
    "requested",
    "applied",
    "baseline_target",
    "selection_source",
    "risk_drawdown",
    "risk_state",
    "risk_reason",
    "uncertainty",
    "uncertainty_state",
    "uncertainty_reason",
    "hard_stop_bar_index",
    "recovery_reentry_until",
)
_FILL_FIELDS = (
    "operation_id",
    "event_id",
    "symbol",
    "side",
    "quantity",
    "price",
    "notional",
    "fee",
    "timestamp",
    "position_after",
    "cash_after",
    "equity_after",
)
_RECEIPT_FIELDS = (
    "canonical_event_id",
    "event_id",
    "trading_bar_event_id",
    "decision_event_id",
    "field_decision_event_id",
    "receipt_id",
    "paper_receipt_event_id",
    "content_sha256",
    "receipt_sha256",
)


class TradingApplicationStateError(ValueError):
    """The host application binding or its persisted view is invalid."""


def _digest(value: Any) -> str:
    blob = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class EntityProgramInactive(TradingApplicationStateError):
    """An authenticated exact program exists but is not active."""

    def __init__(self, status: str) -> None:
        normalized = status.strip().lower() if isinstance(status, str) else ""
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", normalized) or normalized == "active":
            raise ValueError("inactive program status is invalid")
        self.status = normalized
        super().__init__(f"entity program is not active (status={normalized})")


def _timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise TradingApplicationStateError("entity program timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
    except (OverflowError, TypeError, ValueError):
        raise TradingApplicationStateError("entity program timestamp is invalid") from None
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError("non-finite JSON number")


def _absolute_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value or len(value) > 4096:
        return None
    try:
        path = Path(value).expanduser()
        if not path.is_absolute():
            return None
        return path.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return None


def _path_is_within(root: Path, target: Path) -> bool:
    try:
        common = os.path.commonpath((str(root), str(target)))
    except (OSError, ValueError):
        return False
    return os.path.normcase(common) == os.path.normcase(str(root))


class _NoEntityRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def validate_entity_program_payload(
    payload: Any,
    *,
    program_id: str,
    data_home: Path,
    ingestion_db: Path,
) -> Mapping[str, Any]:
    """Validate the entity's current programme document and both paper scopes."""
    if not isinstance(program_id, str) or not program_id.strip() or len(program_id) > 512:
        raise TradingApplicationStateError("entity program id is invalid")
    if not isinstance(payload, Mapping):
        raise TradingApplicationStateError("entity program response is not an object")
    if payload.get("program_id") != program_id:
        raise TradingApplicationStateError("entity program response identity does not match the requested id")
    status = payload.get("status")
    if not isinstance(status, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", status):
        raise TradingApplicationStateError("entity program status is invalid")
    if status != "active":
        raise EntityProgramInactive(status)
    created_at = _timestamp(payload.get("created_at"))
    mission = payload.get("mission")
    if not isinstance(mission, str) or not mission.strip():
        raise TradingApplicationStateError("entity program mission is missing or invalid")
    try:
        mission_sha256 = _digest(mission)
    except (TypeError, ValueError, RecursionError):
        raise TradingApplicationStateError("entity program mission cannot be digested") from None
    roots = payload.get("allowed_roots")
    if not isinstance(roots, list) or not roots or len(roots) > _ENTITY_PROGRAM_MAX_ROOTS:
        raise TradingApplicationStateError("entity program workspace scopes are missing or invalid")
    resolved_roots = [_absolute_path(root) for root in roots]
    if any(root is None for root in resolved_roots):
        raise TradingApplicationStateError("entity program workspace scopes are invalid")
    member_home = Path(data_home).expanduser().resolve()
    ingestion_database = Path(ingestion_db).expanduser().resolve()
    member_scope = any(
        _path_is_within(root, member_home) for root in resolved_roots if root is not None
    )
    database_scope = any(
        _path_is_within(root, ingestion_database)
        for root in resolved_roots
        if root is not None
    )
    if not member_scope or not database_scope:
        raise TradingApplicationStateError("entity program workspace scopes do not cover this paper member")
    return {
        "schema": ENTITY_PROGRAM_VERIFICATION_SCHEMA,
        "program_id": program_id,
        "status": "active",
        "created_at": created_at,
        "mission_sha256": mission_sha256,
        "verified_at": _now(),
        "member_home": str(member_home),
        "ingestion_database": str(ingestion_database),
        "scopes": {
            "member_home": True,
            "ingestion_database": True,
        },
    }


class EntityProgramVerifier:
    """Read and validate one authenticated loopback entity program record."""

    def __init__(
        self,
        base_url: str,
        program_id: str,
        *,
        token_env: str,
        data_home: Path,
        ingestion_db: Path,
        timeout_seconds: float = 5,
    ) -> None:
        if not isinstance(base_url, str) or not base_url or len(base_url) > 2048:
            raise TradingApplicationStateError("entity program URL is invalid")
        try:
            parsed = urlsplit(base_url)
            port = parsed.port
            host = parsed.hostname
        except ValueError:
            raise TradingApplicationStateError("entity program URL is invalid") from None
        loopback = False
        if host is not None:
            try:
                loopback = ipaddress.ip_address(host).is_loopback
            except ValueError:
                loopback = host.lower() == "localhost"
        if (
            parsed.scheme.lower() != "http"
            or not loopback
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or (port is not None and not 1 <= port <= 65535)
        ):
            raise TradingApplicationStateError("entity program URL must be exact loopback HTTP without credentials")
        if not isinstance(program_id, str) or not program_id.strip() or len(program_id) > 512:
            raise TradingApplicationStateError("entity program id is invalid")
        if (
            not isinstance(token_env, str)
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token_env)
        ):
            raise TradingApplicationStateError("entity program token environment name is invalid")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not 0 < timeout_seconds <= 30
        ):
            raise TradingApplicationStateError("entity program timeout is outside the supported bound")
        self.base_url = base_url.rstrip("/")
        self.program_id = program_id
        self.token_env = token_env
        self.data_home = Path(data_home).expanduser().resolve()
        self.ingestion_db = Path(ingestion_db).expanduser().resolve()
        self.timeout_seconds = float(timeout_seconds)
        self._opener = build_opener(_NoEntityRedirect(), ProxyHandler({}))

    def verify(self) -> Mapping[str, Any]:
        token = os.environ.get(self.token_env)
        if not isinstance(token, str) or not token or len(token) > 4096 or not re.fullmatch(r"[!-~]+", token):
            raise TradingApplicationStateError("entity program token is unavailable or invalid")
        endpoint = f"{self.base_url}/v1/programs/{quote(self.program_id, safe='')}"
        request = Request(
            endpoint,
            headers={
                "Authorization": f"Bearer {token}",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
            method="GET",
        )
        try:
            response = self._opener.open(request, timeout=self.timeout_seconds)
        except HTTPError as exc:
            status_code = exc.code
            exc.close()
            raise TradingApplicationStateError(
                f"authenticated entity program lookup failed (HTTP {status_code})"
            ) from None
        except (HTTPException, URLError, TimeoutError, OSError):
            raise TradingApplicationStateError("authenticated entity program lookup is unavailable") from None
        try:
            with response:
                if response.getcode() != 200:
                    raise TradingApplicationStateError("authenticated entity program lookup returned an unexpected status")
                if response.headers.get_content_type() != "application/json":
                    raise TradingApplicationStateError("entity program response is not JSON")
                body = response.read(ENTITY_PROGRAM_RESPONSE_MAX_BYTES + 1)
        except TradingApplicationStateError:
            raise
        except (HTTPException, OSError, ValueError):
            raise TradingApplicationStateError("entity program response could not be read") from None
        if len(body) > ENTITY_PROGRAM_RESPONSE_MAX_BYTES:
            raise TradingApplicationStateError("entity program response exceeds the size limit")
        try:
            payload = json.loads(
                body.decode("utf-8"),
                object_pairs_hook=_strict_json_object,
                parse_constant=_reject_json_constant,
            )
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise TradingApplicationStateError("entity program response is not valid bounded JSON") from None
        return validate_entity_program_payload(
            payload,
            program_id=self.program_id,
            data_home=self.data_home,
            ingestion_db=self.ingestion_db,
        )


def _project(value: Any, fields: tuple[str, ...]) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return {name: value[name] for name in fields if name in value}


def _event_identity(value: Any) -> dict[str, Any] | None:
    return _project(value, _EVENT_FIELDS)


def _decision_summary(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        summary = _safe_scalars(value, _DECISION_FIELDS)
        if "target" not in summary:
            for name in ("applied", "value", "requested"):
                if name in summary:
                    summary["target"] = summary[name]
                    break
        decision_id = value.get("decision_event_id", value.get("event_id"))
        if (
            isinstance(decision_id, str)
            and 0 < len(decision_id) <= 4096
        ) or (
            isinstance(decision_id, int)
            and not isinstance(decision_id, bool)
        ):
            summary["decision_event_id"] = decision_id
        return summary
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return {"target": float(value)}
    return None
def _field_decision(field: Any, paper_status: Mapping[str, Any]) -> dict[str, Any] | None:
    target = _decision_summary(paper_status.get("field_target"))
    requested_id = None if target is None else target.get("decision_event_id")
    if requested_id is None:
        last_event = _event_identity(paper_status.get("last_event"))
        requested_id = None if last_event is None else last_event.get("field_decision_event_id")
    if requested_id is None:
        return None
    row = field.ledger.get(str(requested_id))
    if not isinstance(row, Mapping) or row.get("kind") != "decision":
        return None
    payload = row.get("payload", {})
    summary = _decision_summary(payload) or {}
    summary["decision_event_id"] = row.get("event_id")
    summary["bar_event_id"] = payload.get("bar_event_id")
    return summary


def _health_summary(health: Mapping[str, Any]) -> dict[str, Any]:
    metrics = health.get("metrics", {})
    reasons = health.get("reasons", ())
    bounded_reasons: list[dict[str, Any]] = []
    if isinstance(reasons, (list, tuple)):
        for row in reasons[:16]:
            if not isinstance(row, Mapping):
                continue
            reason = {key: row[key] for key in ("severity", "code") if key in row}
            reason.update({key: row[key] for key in _REASON_DETAILS if key in row})
            bounded_reasons.append(reason)
    bounded_metrics = (
        {key: metrics[key] for key in _HEALTH_METRICS if key in metrics}
        if isinstance(metrics, Mapping)
        else {}
    )
    return {
        "schema": health.get("schema"),
        "state": health.get("state"),
        "evaluated_at": health.get("evaluated_at"),
        "reasons": bounded_reasons,
        "metrics": bounded_metrics,
        "can_observe": health.get("can_observe") is True,
        "can_open_exposure": health.get("can_open_exposure") is True,
        "content_sha256": health.get("content_sha256"),
    }



def _latest_fill(paper_status: Mapping[str, Any]) -> dict[str, Any] | None:
    for name in ("latest_fill", "latest_causal_fill", "latest_legacy_fill"):
        latest = paper_status.get(name)
        if isinstance(latest, Mapping):
            return _project(latest, _FILL_FIELDS)
    fills = paper_status.get("fills")
    if isinstance(fills, (list, tuple)) and fills and isinstance(fills[-1], Mapping):
        return _project(fills[-1], _FILL_FIELDS)
    if isinstance(fills, Mapping) and any(key in fills for key in ("side", "quantity", "operation_id")):
        return _project(fills, _FILL_FIELDS)
    return None


def _receipt_identity(paper_status: Mapping[str, Any], drain: Mapping[str, Any]) -> dict[str, Any] | None:
    receipt = paper_status.get("last_receipt", paper_status.get("latest_receipt"))
    summary = _project(receipt, _RECEIPT_FIELDS)
    if summary is None:
        summary = {}
    for key in _RECEIPT_FIELDS:
        if key not in summary and key in paper_status:
            summary[key] = paper_status[key]
    if "content_sha256" not in summary and drain.get("latest_receipt_sha256") is not None:
        summary["content_sha256"] = drain["latest_receipt_sha256"]
    return summary or None
def _count_value(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _fill_count(paper_status: Mapping[str, Any]) -> int | None:
    count = _count_value(paper_status.get("fill_count"))
    if count is not None:
        return count
    fills = paper_status.get("fills")
    if isinstance(fills, (list, tuple)):
        return len(fills)
    if isinstance(fills, int) and not isinstance(fills, bool):
        return _count_value(fills)
    return None


def _activation_boundary(paper_status: Mapping[str, Any]) -> Any:
    boundary = paper_status.get("activation_boundary")
    if isinstance(boundary, Mapping):
        return _project(
            boundary,
            (
                "event_id",
                "canonical_event_id",
                "source_id",
                "timestamp",
                "observed_at",
                "bar_index",
                "paper_only",
            ),
        )
    return boundary if isinstance(boundary, (str, int, float, bool)) or boundary is None else None


_PAPER_PENDING_FIELDS = (
    "signal_event_id",
    "signal_source_id",
    "signal_source_revision",
    "signal_observed_at",
    "signal_available_at",
    "signal_created_at",
    "signal_reference_price",
    "field_decision_event_id",
    "field_decision_sha256",
    "target_exposure",
    "expected_execution_observed_at",
    "order_sha256",
    "status",
    "expiry_reason",
)
_PAPER_EXECUTION_FIELDS = (
    "signal_event_id",
    "field_decision_event_id",
    "execution_event_id",
    "execution_source_id",
    "execution_source_revision",
    "execution_observed_at",
    "execution_available_at",
    "signal_reference_price",
    "execution_reference_price",
    "execution_price",
    "signal_to_execution_seconds",
    "price",
    "settlement_health",
    "status",
)
_PAPER_MODEL_FIELDS = (
    "paper_account",
    "signal_to_fill_lag_bars",
    "timeframe_seconds",
    "maximum_wait_bars",
    "legacy_receipts",
    "field_internal_model",
    "cutover_event_id",
)
_PAPER_EXPIRY_FIELDS = (
    "kind",
    "reason",
    "cancelled_at",
    "expired_at",
    "event_id",
    "source_id",
)
_ORDER_RISK_FIELDS = (
    "risk_drawdown",
    "risk_state",
    "risk_reason",
    "hard_stop_bar_index",
    "recovery_reentry_until",
)
_ORDER_UNCERTAINTY_FIELDS = (
    "uncertainty",
    "uncertainty_state",
    "uncertainty_reason",
    "uncertainty_code",
)


def _safe_scalars(value: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in keys:
        if key not in value:
            continue
        item = value[key]
        if item is None or isinstance(item, (bool, int)):
            result[key] = item
        elif isinstance(item, str) and len(item) <= 4096:
            result[key] = item
        elif isinstance(item, float) and item == item and abs(item) != float("inf"):
            result[key] = item
    return result


def _pending_order(paper_status: Mapping[str, Any]) -> dict[str, Any] | None:
    pending = paper_status.get("pending_order")
    if not isinstance(pending, Mapping):
        return None
    result = _safe_scalars(pending, _PAPER_PENDING_FIELDS)
    if "signal_event_id" in result:
        result["signal_canonical_event_id"] = result["signal_event_id"]
    identity = _decision_summary(
        pending.get("source_decision_identity", pending.get("source_decision"))
    )
    decision_id = pending.get(
        "field_decision_event_id",
        pending.get("decision_event_id", pending.get("source_decision_event_id")),
    )
    if decision_id is None and identity is not None:
        decision_id = identity.get("decision_event_id")
    if decision_id is not None and (
        not isinstance(decision_id, (str, int)) or isinstance(decision_id, bool)
    ):
        decision_id = None
    if decision_id is not None:
        result["decision_event_id"] = decision_id
        result["field_decision_event_id"] = decision_id
    if "target_exposure" in result:
        result["desired_target"] = result["target_exposure"]
    risk = _safe_scalars(pending, _ORDER_RISK_FIELDS)
    uncertainty = _safe_scalars(pending, _ORDER_UNCERTAINTY_FIELDS)
    if identity is not None:
        risk.update(_safe_scalars(identity, _ORDER_RISK_FIELDS))
        uncertainty.update(_safe_scalars(identity, _ORDER_UNCERTAINTY_FIELDS))
    if risk:
        result["risk"] = risk
    if uncertainty:
        result["uncertainty"] = uncertainty
    return result


def _last_execution(paper_status: Mapping[str, Any]) -> dict[str, Any] | None:
    execution = paper_status.get("last_execution")
    if not isinstance(execution, Mapping):
        return None
    result = _safe_scalars(execution, _PAPER_EXECUTION_FIELDS)
    if "signal_event_id" in result:
        result["signal_canonical_event_id"] = result["signal_event_id"]
    fill = execution.get("fill")
    if isinstance(fill, Mapping):
        fill_identity = _project(fill, _FILL_FIELDS)
        if fill_identity:
            result["fill"] = fill_identity
    settlement_health = execution.get("settlement_health")
    if isinstance(settlement_health, Mapping):
        result["settlement_health"] = _health_summary(settlement_health)
    decision = execution.get("source_decision_identity")
    if isinstance(decision, Mapping):
        summary = _decision_summary(decision)
        if summary:
            result["source_decision_identity"] = summary
            if "decision_event_id" not in result and summary.get("decision_event_id") is not None:
                result["decision_event_id"] = summary["decision_event_id"]
            risk = _safe_scalars(summary, _ORDER_RISK_FIELDS)
            uncertainty = _safe_scalars(summary, _ORDER_UNCERTAINTY_FIELDS)
            if risk:
                result["risk"] = risk
            if uncertainty:
                result["uncertainty"] = uncertainty
    risk = _safe_scalars(execution, _ORDER_RISK_FIELDS)
    uncertainty = _safe_scalars(execution, _ORDER_UNCERTAINTY_FIELDS)
    if risk:
        result["risk"] = risk
    if uncertainty:
        result["uncertainty"] = uncertainty
    return result


def _drain_summary(drain: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "schema",
        "status",
        "processed",
        "admitted_bars",
        "replayed_bars",
        "pending_before",
        "pending_after",
        "last_source_event_id",
        "latest_receipt_sha256",
        "health_state",
    )
    return {key: drain[key] for key in fields if key in drain}


def _source_event(event: Any) -> dict[str, Any] | None:
    if event is None:
        return None
    payload = getattr(event, "payload", {})
    result = {
        "event_id": getattr(event, "event_id", None),
        "source_id": getattr(event, "source_id", None),
        "source_revision": getattr(event, "source_revision", None),
        "event_type": getattr(event, "event_type", None),
        "observed_at": getattr(event, "observed_at", None),
        "available_at": getattr(event, "available_at", None),
        "payload_sha256": _digest(payload),
    }
    subjects = getattr(event, "subject_ids", ())
    if subjects:
        result["subject_id"] = subjects[0]
    return result


class TradingPaperApplication:
    """Stable host/member binding and bounded generic view for one paper member."""

    def __init__(
        self,
        *,
        data_home: Path,
        ingestion_db: Path,
        symbol: str,
        consumer_id: str,
        paper_state_path: Path,
        member_id: str | None,
        mission_id: str | None,
    ) -> None:
        self.data_home = Path(data_home).expanduser().resolve()
        self.ingestion_db = Path(ingestion_db).expanduser().resolve()
        self.paper_state_path = Path(paper_state_path).expanduser().resolve()
        self.view_path = self.data_home / APPLICATION_VIEW_FILENAME
        self.binding_path = self.data_home / APPLICATION_BINDING_FILENAME
        self._previous = self._load_view(missing_ok=True)
        view_binding = {} if self._previous is None else self._previous.get("binding", {})
        if not isinstance(view_binding, Mapping):
            raise TradingApplicationStateError("paper application binding is invalid")
        persisted_binding = self._load_binding(self.binding_path, missing_ok=True)
        self._entity_program_attestation = self._load_entity_attestation(
            self.binding_path,
            missing_ok=True,
        )
        self._current_entity_program_verification: dict[str, Any] | None = None
        previous_binding = persisted_binding or view_binding
        member_id = previous_binding.get("member_id") if member_id is None else member_id
        mission_id = (
            previous_binding.get("original_mission_id")
            if mission_id is None
            else mission_id
        )
        if not isinstance(member_id, str) or not member_id.strip():
            raise TradingApplicationStateError("a host member_id is required for a new paper application")
        if not isinstance(mission_id, str) or not mission_id.strip():
            raise TradingApplicationStateError("the original host mission_id is required for a new paper application")
        if not isinstance(symbol, str) or not symbol.strip():
            raise TradingApplicationStateError("paper application symbol must be nonempty")
        if not isinstance(consumer_id, str) or not consumer_id.strip():
            raise TradingApplicationStateError("paper consumer_id must be nonempty")
        self.binding = {
            "member_id": member_id,
            "member_home": str(self.data_home),
            "original_mission_id": mission_id,
            "symbol": symbol,
            "ingestion_database": str(self.ingestion_db),
            "consumer_id": consumer_id,
            "paper_state_path": str(self.paper_state_path),
        }
        if (
            self._entity_program_attestation is not None
            and self._entity_program_attestation["original_mission_id"] != mission_id
        ):
            raise TradingApplicationStateError(
                "original host mission differs from the durable entity program attestation"
            )
        if self._previous is not None and view_binding != self.binding:
            raise TradingApplicationStateError(
                "paper application identity/source binding differs from the persisted view"
            )
        if persisted_binding is None:
            if self.paper_state_path.exists() or self.view_path.exists():
                raise TradingApplicationStateError(
                    "existing paper state requires its original durable application binding"
                )
            self._write_document(
                self.binding_path,
                {"schema": APPLICATION_BINDING_SCHEMA, "binding": self.binding},
            )
        elif persisted_binding != self.binding:
            raise TradingApplicationStateError(
                "paper application identity/source binding differs from the durable binding"
            )


    def bind_verified_program(self, verified: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(verified, Mapping) or verified.get("schema") != ENTITY_PROGRAM_VERIFICATION_SCHEMA:
            raise TradingApplicationStateError("entity program verification record is missing or invalid")
        program_id = verified.get("program_id")
        mission_sha256 = verified.get("mission_sha256")
        if (
            not isinstance(program_id, str)
            or not program_id.strip()
            or len(program_id) > 512
            or verified.get("status") != "active"
            or not isinstance(mission_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", mission_sha256)
        ):
            raise TradingApplicationStateError("entity program verification identity is invalid")
        created_at = _timestamp(verified.get("created_at"))
        verified_at = _timestamp(verified.get("verified_at"))
        member_home = _absolute_path(verified.get("member_home"))
        ingestion_database = _absolute_path(verified.get("ingestion_database"))
        scopes = verified.get("scopes")
        if (
            member_home != self.data_home
            or ingestion_database != self.ingestion_db
            or not isinstance(scopes, Mapping)
            or scopes.get("member_home") is not True
            or scopes.get("ingestion_database") is not True
        ):
            raise TradingApplicationStateError("entity program verification does not cover this paper member")
        attestation = {
            "schema": ENTITY_PROGRAM_ATTESTATION_SCHEMA,
            "program_id": program_id,
            "created_at": created_at,
            "mission_sha256": mission_sha256,
            "original_mission_id": self.binding["original_mission_id"],
        }
        if self._entity_program_attestation is None:
            document = self._load_binding_document(self.binding_path, missing_ok=False)
            if document is None or document.get("binding") != self.binding:
                raise TradingApplicationStateError("durable application binding changed before program attestation")
            body = {
                "schema": APPLICATION_BINDING_SCHEMA,
                "binding": dict(self.binding),
                "entity_program_attestation": attestation,
            }
            self._write_document(self.binding_path, body)
            self._entity_program_attestation = attestation
        elif self._entity_program_attestation != attestation:
            raise TradingApplicationStateError("entity program identity differs from its durable attestation")
        current: dict[str, Any] = {
            "schema": ENTITY_PROGRAM_VERIFICATION_SCHEMA,
            "program_id": program_id,
            "status": "active",
            "created_at": created_at,
            "mission_sha256": mission_sha256,
            "verified_at": verified_at,
            "member_home": str(self.data_home),
            "ingestion_database": str(self.ingestion_db),
            "scopes": {
                "member_home": True,
                "ingestion_database": True,
            },
        }
        self._current_entity_program_verification = current
        return {**current, "scopes": dict(current["scopes"])}

    def _load_view(self, *, missing_ok: bool = False) -> dict[str, Any] | None:
        if not self.view_path.exists():
            if missing_ok:
                return None
            raise TradingApplicationStateError("paper application state does not exist in this member home")
        try:
            document = json.loads(self.view_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TradingApplicationStateError("paper application state is unreadable") from exc
        if not isinstance(document, Mapping):
            raise TradingApplicationStateError("paper application state is not an object")
        body = dict(document)
        stated = body.pop("content_sha256", None)
        if document.get("schema") != APPLICATION_VIEW_SCHEMA or stated != _digest(body):
            raise TradingApplicationStateError("paper application state schema or digest mismatch")
        if document.get("paper_only") is not True or document.get("external_effect") != "none":
            raise TradingApplicationStateError("persisted application state is not paper-only")
        if not isinstance(document.get("binding"), Mapping):
            raise TradingApplicationStateError("paper application identity binding is missing")
        return dict(document)

    @staticmethod
    def _load_binding_document(path: Path, *, missing_ok: bool) -> dict[str, Any] | None:
        if not path.exists():
            if missing_ok:
                return None
            raise TradingApplicationStateError("durable paper application binding is missing")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise TradingApplicationStateError("durable paper application binding is unreadable") from None
        if not isinstance(document, Mapping):
            raise TradingApplicationStateError("durable paper application binding is not an object")
        body = dict(document)
        stated = body.pop("content_sha256", None)
        if document.get("schema") != APPLICATION_BINDING_SCHEMA or stated != _digest(body):
            raise TradingApplicationStateError("durable paper application binding schema or digest mismatch")
        if not isinstance(document.get("binding"), Mapping):
            raise TradingApplicationStateError("durable paper application identity is missing")
        return dict(document)

    @staticmethod
    def _load_binding(path: Path, *, missing_ok: bool) -> dict[str, Any] | None:
        document = TradingPaperApplication._load_binding_document(path, missing_ok=missing_ok)
        return None if document is None else dict(document["binding"])

    @staticmethod
    def _load_entity_attestation(path: Path, *, missing_ok: bool) -> dict[str, Any] | None:
        document = TradingPaperApplication._load_binding_document(path, missing_ok=missing_ok)
        if document is None:
            return None
        value = document.get("entity_program_attestation")
        if value is None:
            return None
        if (
            not isinstance(value, Mapping)
            or value.get("schema") != ENTITY_PROGRAM_ATTESTATION_SCHEMA
            or not isinstance(value.get("program_id"), str)
            or not value.get("program_id").strip()
            or len(value.get("program_id")) > 512
            or not isinstance(value.get("original_mission_id"), str)
            or not value.get("original_mission_id").strip()
            or not isinstance(value.get("mission_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", value.get("mission_sha256"))
        ):
            raise TradingApplicationStateError("durable entity program attestation is invalid")
        return {
            "schema": ENTITY_PROGRAM_ATTESTATION_SCHEMA,
            "program_id": value["program_id"],
            "created_at": _timestamp(value.get("created_at")),
            "mission_sha256": value["mission_sha256"],
            "original_mission_id": value["original_mission_id"],
        }

    @staticmethod
    def _write_document(path: Path, body: Mapping[str, Any]) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        document = {**body, "content_sha256": _digest(body)}
        payload = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ) + "\n"
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
        return document

    def record_action(
        self,
        *,
        store: Any,
        field: Any,
        consumer: Any,
        health: Mapping[str, Any],
        drain: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        paper_status = consumer.paper_status()
        field_status = field.status()
        latest_bar = store.latest_accepted_bar(self.binding["symbol"])
        latest_market = store.latest_accepted_market_event(self.binding["symbol"])
        health_view = _health_summary(health)
        health_reason_codes = [
            str(row["code"])
            for row in health_view["reasons"]
            if row.get("code") is not None
        ]
        latest_event_value = paper_status.get("last_event")
        latest_event = _event_identity(latest_event_value)
        latest_receipt = _receipt_identity(paper_status, drain)
        source_bar_event = None if latest_bar is None else latest_bar[0]
        field_target = _field_decision(field, paper_status)
        decision_id = None if field_target is None else field_target.get("decision_event_id")
        if decision_id is None and latest_event is not None:
            decision_id = latest_event.get("field_decision_event_id")
        decision_count = field_status.get("decision_count")
        source_codes = [
            "CANONICAL_ACCEPTANCE_IS_NOT_EXCHANGE_TRUTH",
            "PAPER_EXECUTION_HAS_NO_EXTERNAL_ORDER_EFFECT",
            "EXPOSURE_PERMISSION_IS_SCOPED_TO_THE_ACTION_TIME_HEALTH_SAMPLE",
        ]
        if not latest_event:
            source_codes.append("NO_PAPER_EVENT_HAS_BEEN_PROCESSED")
        if field_target is None:
            source_codes.append("NO_FIELD_TARGET_IS_YET_AVAILABLE_FOR_THE_PAPER_CONSUMER")
        source_codes.extend(f"SOURCE_HEALTH_{code.upper().replace('-', '_')}" for code in health_reason_codes)
        body = {
            "schema": APPLICATION_VIEW_SCHEMA,
            "written_at": _now(),
            "binding": dict(self.binding),
            "entity_program": {
                "pinned_attestation": (
                    dict(self._entity_program_attestation)
                    if self._entity_program_attestation is not None
                    else None
                ),
                "verification_at_action_time": (
                    dict(self._current_entity_program_verification)
                    if self._current_entity_program_verification is not None
                    else None
                ),
            },
            "paper_only": True,
            "external_effect": "none",
            "control": {
                "mode": "paper-only",
                "external_order_path": False,
                "external_order_permission": False,
                "permission_scope": "simulated-paper-account-only",
                "health_evaluated_at_action_time": health_view["evaluated_at"],
                "paper_exposure_permitted_at_action_time": health_view["can_open_exposure"],
                "paper_exposure_permission_requires_green": True,
                "heartbeat_required": True,
                "account_reconciliation_required": False,
            },
            "source": {
                "kind": "canonical-market-ingestion",
                "database": str(self.ingestion_db),
                "source_id": None if source_bar_event is None else source_bar_event.source_id,
                "latest_accepted_bar": _source_event(source_bar_event),
                "latest_accepted_market_event": _source_event(latest_market),
                "health_at_action_time": health_view,
                "uncertainty_codes": source_codes,
            },
            "field": {
                "symbol": self.binding["symbol"],
                "bar_count": field_status.get("bar_count"),
                "decision_count": decision_count,
                "field_state_sha256": field_status.get("field_state_sha256"),
                "field_manifest_sha256": field_status.get("field_manifest_sha256"),
                "ledger_head_sha256": field_status.get("ledger_head_sha256"),
                "target": field_target,
                "risk": _safe_scalars(field_target or {}, _ORDER_RISK_FIELDS),
                "uncertainty": _safe_scalars(field_target or {}, _ORDER_UNCERTAINTY_FIELDS),
                "decision_event_id": decision_id,
            },
            "paper": {
                "consumer_id": paper_status.get("consumer_id", self.binding["consumer_id"]),
                "latest_fill": _latest_fill(paper_status),
                "symbol": paper_status.get("symbol", self.binding["symbol"]),
                "processed": paper_status.get("processed"),
                "latest_legacy_fill": _project(paper_status.get("latest_legacy_fill"), _FILL_FIELDS),
                "latest_causal_fill": _project(paper_status.get("latest_causal_fill"), _FILL_FIELDS),
                "pending_order": _pending_order(paper_status),
                "last_execution": _last_execution(paper_status),
                "execution_model": _project(paper_status.get("execution_model"), _PAPER_MODEL_FIELDS),
                "last_expiry": (
                    {
                        **_safe_scalars(paper_status["last_expiry"], _PAPER_EXPIRY_FIELDS),
                        "pending_order": _pending_order({
                            "pending_order": paper_status["last_expiry"].get("pending_order")
                        }),
                    }
                    if isinstance(paper_status.get("last_expiry"), Mapping)
                    else None
                ),
                "fill_count": _fill_count(paper_status),
                "legacy_fill_count": _count_value(paper_status.get("legacy_fill_count")),
                "causal_fill_count": _count_value(paper_status.get("causal_fill_count")),
                "activation_boundary": _activation_boundary(paper_status),
                "last_event": latest_event,
                "last_receipt": latest_receipt,
                "account": paper_status.get("account"),
                "health": (
                    _health_summary(paper_status["health"])
                    if isinstance(paper_status.get("health"), Mapping)
                    else paper_status.get("health")
                ),
                "recovery": paper_status.get("recovery"),
                "paper_only": True,
                "external_effect": "none",
            },
            "drain": _drain_summary(drain),
        }
        document = self._write_document(self.view_path, body)
        self._previous = document
        return document

    @classmethod
    def inspect(
        cls,
        *,
        data_home: Path,
        ingestion_db: Path,
        member_id: str | None = None,
        mission_id: str | None = None,
    ) -> Mapping[str, Any]:
        home = Path(data_home).expanduser().resolve()
        database = Path(ingestion_db).expanduser().resolve()
        path = home / APPLICATION_VIEW_FILENAME
        if not path.exists():
            raise TradingApplicationStateError("paper application state does not exist in this member home")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TradingApplicationStateError("paper application state is unreadable") from exc
        if not isinstance(document, Mapping):
            raise TradingApplicationStateError("paper application state is not an object")
        body = dict(document)
        stated = body.pop("content_sha256", None)
        binding = document.get("binding")
        if document.get("schema") != APPLICATION_VIEW_SCHEMA or stated != _digest(body):
            raise TradingApplicationStateError("paper application state schema or digest mismatch")
        if document.get("paper_only") is not True or document.get("external_effect") != "none":
            raise TradingApplicationStateError("persisted application state is not paper-only")
        if not isinstance(binding, Mapping):
            raise TradingApplicationStateError("paper application identity binding is missing")
        persisted_binding = cls._load_binding(
            home / APPLICATION_BINDING_FILENAME,
            missing_ok=False,
        )
        entity_attestation = cls._load_entity_attestation(
            home / APPLICATION_BINDING_FILENAME,
            missing_ok=False,
        )
        entity_view = document.get("entity_program")
        if isinstance(entity_view, Mapping):
            view_attestation = entity_view.get("pinned_attestation")
            if view_attestation is not None and view_attestation != entity_attestation:
                raise TradingApplicationStateError("application view and durable entity attestation disagree")
        if persisted_binding != dict(binding):
            raise TradingApplicationStateError("application view and durable identity binding disagree")
        if binding.get("member_home") != str(home):
            raise TradingApplicationStateError("paper application state belongs to a different member home")
        if binding.get("ingestion_database") != str(database):
            raise TradingApplicationStateError("--ingestion-db differs from the persisted paper application source")
        if member_id is not None and member_id != binding.get("member_id"):
            raise TradingApplicationStateError("--member-id differs from the persisted paper application binding")
        if mission_id is not None and mission_id != binding.get("original_mission_id"):
            raise TradingApplicationStateError("--mission-id differs from the persisted original mission identity")

        inspected_at = datetime.now(timezone.utc)
        try:
            written_at = datetime.fromisoformat(str(document["written_at"]).replace("Z", "+00:00"))
            if written_at.tzinfo is None:
                raise ValueError("timestamp has no timezone")
        except (KeyError, TypeError, ValueError) as exc:
            raise TradingApplicationStateError("paper application state timestamp is invalid") from exc
        elapsed = max(
            0.0,
            (inspected_at - written_at.astimezone(timezone.utc)).total_seconds(),
        )
        source = document.get("source", {})
        health = source.get("health_at_action_time", {}) if isinstance(source, Mapping) else {}
        metrics = health.get("metrics", {}) if isinstance(health, Mapping) else {}
        estimated_ages = {
            key: (metrics[key] + elapsed if isinstance(metrics.get(key), (int, float)) else None)
            for key in _AGE_METRICS
        }
        entity_verification = (
            entity_view.get("verification_at_action_time")
            if isinstance(entity_view, Mapping)
            else None
        )
        return {
            **dict(document),
            "inspection": {
                "read_only": True,
                "inspected_at": inspected_at.isoformat().replace("+00:00", "Z"),
                "seconds_since_action_view": elapsed,
                "source_age_seconds_estimate": estimated_ages,
                "ingestion_database_present": database.exists(),
                "current_action_time_permission": False,
                "entity_program_attestation": entity_attestation,
                "entity_program_verification_is_current": False,
                "entity_program_current_permission": False,
                "entity_program_status_at_action_time": (
                    entity_verification.get("status")
                    if isinstance(entity_verification, Mapping)
                    else None
                ),
                "entity_program_verified_at_action_time": (
                    entity_verification.get("verified_at")
                    if isinstance(entity_verification, Mapping)
                    else None
                ),
                "permission_reason": "read-only inspection does not re-evaluate heartbeat or authorize a new paper action",
                "paper_permission_at_last_action": bool(
                    isinstance(health, Mapping) and health.get("can_open_exposure") is True
                ),
            },
        }


__all__ = [
    "APPLICATION_BINDING_FILENAME",
    "APPLICATION_BINDING_SCHEMA",
    "APPLICATION_VIEW_FILENAME",
    "APPLICATION_VIEW_SCHEMA",
    "ENTITY_PROGRAM_ATTESTATION_SCHEMA",
    "ENTITY_PROGRAM_VERIFICATION_SCHEMA",
    "EntityProgramInactive",
    "EntityProgramVerifier",
    "validate_entity_program_payload",
    "TradingApplicationStateError",
    "TradingPaperApplication",
]
