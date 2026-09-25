from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

import pytest

import cassi_trader_application as application_module
from cassi_trader_application import (
    EntityProgramInactive,
    EntityProgramVerifier,
    TradingApplicationStateError,
    TradingPaperApplication,
)


def _application(
    home: Path,
    database: Path,
    paper_state: Path,
    *,
    member_id: str | None = None,
    mission_id: str | None = None,
) -> TradingPaperApplication:
    return TradingPaperApplication(
        data_home=home,
        ingestion_db=database,
        symbol="BTC-USD",
        consumer_id="paper-member-btc",
        paper_state_path=paper_state,
        member_id=member_id,
        mission_id=mission_id,
    )



@pytest.fixture
def entity_program_api(tmp_path: Path):
    home = tmp_path / "member-home"
    database_dir = tmp_path / "ingestion"
    home.mkdir()
    database_dir.mkdir()
    database = database_dir / "market.sqlite3"
    token = "local-entity-test-token"
    state = {
        "http_status": 200,
        "redirect_location": None,
        "raw_body": None,
        "document": {
            "program_id": "entity-program-7",
            "status": "active",
            "created_at": "2026-09-22T12:00:00Z",
            "mission": "Study BTC/USD hourly paper trading with no exchange orders.",
            "allowed_roots": [str(home), str(database_dir)],
            "project_id": "project-3",
        },
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            if self.path != "/v1/programs/entity-program-7":
                self.send_response(404)
                self.end_headers()
                return
            if self.headers.get("Authorization") != f"Bearer {token}":
                self.send_response(401)
                self.end_headers()
                return
            self.send_response(state["http_status"])
            if state["redirect_location"] is not None:
                self.send_header("Location", state["redirect_location"])
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            body = state["raw_body"]
            if body is None:
                body = json.dumps(state["document"]).encode("utf-8")
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {
        "url": f"http://127.0.0.1:{server.server_port}",
        "token": token,
        "state": state,
        "home": home,
        "database": database,
    }
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def _verifier(
    api: dict[str, Any],
    *,
    program_id: str = "entity-program-7",
) -> EntityProgramVerifier:
    return EntityProgramVerifier(
        str(api["url"]),
        program_id,
        token_env="ENTITY_PROGRAM_TEST_TOKEN",
        data_home=api["home"],
        ingestion_db=api["database"],
        timeout_seconds=1,
    )


def test_durable_binding_precedes_paper_state_and_cannot_change_on_reopen(tmp_path: Path) -> None:
    home = tmp_path / "member-home"
    database = tmp_path / "market.sqlite3"
    paper_state = home / "trading-paper-state.json"

    first = _application(
        home,
        database,
        paper_state,
        member_id="member-7",
        mission_id="mission-original-19",
    )

    resumed = _application(home, database, paper_state)
    assert resumed.binding == first.binding
    with pytest.raises(TradingApplicationStateError, match="durable binding"):
        _application(
            home,
            database,
            paper_state,
            member_id="member-7",
            mission_id="different-mission",
        )

    orphan_home = tmp_path / "unbound-home"
    orphan_state = orphan_home / "trading-paper-state.json"
    orphan_home.mkdir()
    orphan_state.touch()
    with pytest.raises(TradingApplicationStateError, match="original durable application binding"):
        _application(
            orphan_home,
            database,
            orphan_state,
            member_id="member-8",
            mission_id="mission-original-20",
        )


def test_entity_program_verifier_requires_active_identity_and_both_scopes(
    entity_program_api: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = entity_program_api
    monkeypatch.setenv("ENTITY_PROGRAM_TEST_TOKEN", api["token"])

    verified = _verifier(api).verify()
    assert verified["program_id"] == "entity-program-7"
    assert verified["status"] == "active"
    assert verified["scopes"] == {"member_home": True, "ingestion_database": True}
    assert len(verified["mission_sha256"]) == 64
    assert api["token"] not in repr(verified)

    api["state"]["document"]["allowed_roots"] = [str(api["home"])]
    with pytest.raises(TradingApplicationStateError, match="workspace scopes") as scope_error:
        _verifier(api).verify()
    assert api["token"] not in str(scope_error.value)
    api["state"]["document"]["allowed_roots"] = [str(api["home"]), str(api["database"].parent)]
    api["state"]["document"]["mission"] = {"objective": "wrong program schema"}
    with pytest.raises(TradingApplicationStateError, match="mission"):
        _verifier(api).verify()


def test_entity_program_verifier_distinguishes_inactive_missing_auth_and_identity_mismatch(
    entity_program_api: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = entity_program_api
    monkeypatch.setenv("ENTITY_PROGRAM_TEST_TOKEN", api["token"])
    api["state"]["document"]["status"] = "paused"
    with pytest.raises(EntityProgramInactive) as inactive:
        _verifier(api).verify()
    assert inactive.value.status == "paused"
    assert api["token"] not in str(inactive.value)

    api["state"]["document"]["status"] = "active"
    api["state"]["document"]["program_id"] = "different-program"
    with pytest.raises(TradingApplicationStateError, match="identity"):
        _verifier(api).verify()

    api["state"]["document"]["program_id"] = "entity-program-7"
    api["state"]["http_status"] = 404
    with pytest.raises(TradingApplicationStateError, match="HTTP 404") as missing:
        _verifier(api).verify()
    assert api["token"] not in str(missing.value)

    api["state"]["http_status"] = 200
    monkeypatch.setenv("ENTITY_PROGRAM_TEST_TOKEN", "wrong-token")
    with pytest.raises(TradingApplicationStateError, match="HTTP 401") as denied:
        _verifier(api).verify()
    assert "wrong-token" not in str(denied.value)


def test_verified_program_attestation_pins_independent_host_and_entity_ids(
    entity_program_api: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = entity_program_api
    monkeypatch.setenv("ENTITY_PROGRAM_TEST_TOKEN", api["token"])
    home = api["home"]
    database = api["database"]
    paper_state = home / "paper.json"
    application = _application(
        home,
        database,
        paper_state,
        member_id="member-7",
        mission_id="host-mission-7",
    )

    verified = _verifier(api).verify()
    application.bind_verified_program(verified)
    binding_document = json.loads((home / "trading-paper-application-binding.json").read_text())
    assert binding_document["binding"]["original_mission_id"] == "host-mission-7"
    assert binding_document["entity_program_attestation"]["program_id"] == "entity-program-7"
    assert api["token"] not in json.dumps(binding_document)

    resumed = _application(home, database, paper_state)
    api["state"]["document"]["created_at"] = "2026-09-22T13:00:00Z"
    changed_creation = _verifier(api).verify()
    with pytest.raises(TradingApplicationStateError, match="durable attestation"):
        resumed.bind_verified_program(changed_creation)
    api["state"]["document"]["created_at"] = "2026-09-22T12:00:00Z"
    api["state"]["document"]["mission"] = "Changed research objective"
    changed_mission = _verifier(api).verify()
    with pytest.raises(TradingApplicationStateError, match="durable attestation"):
        resumed.bind_verified_program(changed_mission)


def test_verified_program_binding_rejects_name_only_and_wrong_workspace_scope(
    tmp_path: Path,
    entity_program_api: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = entity_program_api
    monkeypatch.setenv("ENTITY_PROGRAM_TEST_TOKEN", api["token"])
    application = _application(
        api["home"],
        api["database"],
        api["home"] / "paper.json",
        member_id="member-8",
        mission_id="host-mission-8",
    )
    with pytest.raises(TradingApplicationStateError, match="verification record"):
        application.bind_verified_program({"program_id": "entity-program-7"})

    verified = dict(_verifier(api).verify())
    verified["member_home"] = str(tmp_path / "other-member")
    with pytest.raises(TradingApplicationStateError, match="does not cover"):
        application.bind_verified_program(verified)


def test_action_view_projects_causal_order_and_execution_without_turning_inspection_into_permission(
    entity_program_api: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = entity_program_api
    monkeypatch.setenv("ENTITY_PROGRAM_TEST_TOKEN", api["token"])
    application = _application(
        api["home"],
        api["database"],
        api["home"] / "paper.json",
        member_id="member-9",
        mission_id="host-mission-9",
    )
    application.bind_verified_program(_verifier(api).verify())

    class Store:
        def latest_accepted_bar(self, symbol: str):
            return None

        def latest_accepted_market_event(self, symbol: str):
            return None

    class Field:
        ledger = {
            "decision-11": {
                "kind": "decision",
                "event_id": "decision-11",
                "payload": {
                    "decision_event_id": "decision-11",
                    "target": 0.25,
                    "risk_drawdown": 0.08,
                    "uncertainty_state": "elevated",
                },
            }
        }

        def status(self):
            return {"bar_count": 2, "decision_count": 1}

    class Consumer:
        def paper_status(self):
            return {
                "consumer_id": "paper-member-btc",
                "symbol": "BTC-USD",
                "processed": 2,
                "fill_count": 2,
                "fills": [{}, {}, {}],
                "legacy_fill_count": 1,
                "causal_fill_count": 1,
                "latest_fill": {"event_id": "latest-fill", "price": 40_125.5},
                "latest_legacy_fill": {"event_id": "legacy-fill", "price": 39_900.0},
                "latest_causal_fill": {"event_id": "bar-execution-10", "price": 40_125.5},
                "last_event": {
                    "canonical_event_id": "bar-signal-10",
                    "disposition": "pending-next-bar",
                    "execution_model": "next-bar-close-causal",
                },
                "execution_model": {
                    "paper_account": "next-bar-close-causal",
                    "signal_to_fill_lag_bars": 1,
                    "field_internal_model": "signal-close-modeled",
                },
                "last_expiry": {
                    "kind": "cancelled",
                    "reason": "operator-stop",
                    "pending_order": {"signal_event_id": "bar-signal-8"},
                },
                "field_target": {"decision_event_id": "decision-11", "target": 0.25},
                "pending_order": {
                    "signal_event_id": "bar-signal-10",
                    "signal_available_at": "2026-09-22T12:00:00Z",
                    "signal_created_at": "2026-09-22T12:00:01Z",
                    "field_decision_event_id": "decision-11",
                    "target_exposure": 0.25,
                },
                "last_execution": {
                    "signal_event_id": "bar-signal-9",
                    "field_decision_event_id": "decision-10",
                    "execution_event_id": "bar-execution-10",
                    "execution_available_at": "2026-09-22T11:59:00Z",
                    "price": 40_125.5,
                    "fill": {"side": "buy", "price": 40_125.5, "quantity": 0.25},
                },
            }

    health = {
        "schema": "cassi.trading-health.v1",
        "state": "GREEN",
        "evaluated_at": "2026-09-22T12:00:02Z",
        "can_open_exposure": True,
        "metrics": {},
        "reasons": [],
    }
    view = application.record_action(
        store=Store(),
        field=Field(),
        consumer=Consumer(),
        health=health,
        drain={"status": "processed"},
    )
    assert view["paper"]["pending_order"]["decision_event_id"] == "decision-11"
    assert view["paper"]["last_execution"]["execution_event_id"] == "bar-execution-10"
    assert view["paper"]["last_execution"]["price"] == 40_125.5
    assert view["paper"]["fill_count"] == 2
    assert view["paper"]["legacy_fill_count"] == 1
    assert view["paper"]["causal_fill_count"] == 1
    assert view["paper"]["latest_causal_fill"]["event_id"] == "bar-execution-10"
    assert view["paper"]["execution_model"]["signal_to_fill_lag_bars"] == 1
    assert view["paper"]["last_event"]["disposition"] == "pending-next-bar"
    assert view["paper"]["last_expiry"]["reason"] == "operator-stop"
    assert view["paper"]["last_expiry"]["pending_order"]["signal_canonical_event_id"] == "bar-signal-8"
    assert view["field"]["risk"]["risk_drawdown"] == 0.08
    assert view["field"]["uncertainty"]["uncertainty_state"] == "elevated"
    assert api["token"] not in json.dumps(view)

    inspected = TradingPaperApplication.inspect(
        data_home=api["home"],
        ingestion_db=api["database"],
    )
    assert inspected["entity_program"]["verification_at_action_time"]["status"] == "active"
    assert inspected["inspection"]["entity_program_verification_is_current"] is False
    assert inspected["inspection"]["entity_program_current_permission"] is False


def test_entity_program_verifier_rejects_malformed_and_oversized_json(
    entity_program_api: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = entity_program_api
    monkeypatch.setenv("ENTITY_PROGRAM_TEST_TOKEN", api["token"])
    api["state"]["raw_body"] = b"<html>not json</html>"
    with pytest.raises(TradingApplicationStateError, match="valid bounded JSON"):
        _verifier(api).verify()

    monkeypatch.setattr(application_module, "ENTITY_PROGRAM_RESPONSE_MAX_BYTES", 1024)
    api["state"]["raw_body"] = b" " * 1025
    with pytest.raises(TradingApplicationStateError, match="size limit"):
        _verifier(api).verify()


def test_entity_program_verifier_does_not_follow_redirects(
    entity_program_api: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = entity_program_api
    monkeypatch.setenv("ENTITY_PROGRAM_TEST_TOKEN", api["token"])
    api["state"]["http_status"] = 302
    api["state"]["redirect_location"] = "http://127.0.0.1:9/v1/programs/other"
    with pytest.raises(TradingApplicationStateError, match="HTTP 302"):
        _verifier(api).verify()


@pytest.mark.parametrize(
    "url",
    (
        "http://user:password@127.0.0.1:8080",
        "https://127.0.0.1:8080",
        "http://example.invalid:8080",
        "http://127.0.0.1:8080/api",
    ),
)
def test_entity_program_verifier_rejects_non_loopback_or_credentialed_urls(
    url: str,
    tmp_path: Path,
) -> None:
    with pytest.raises(TradingApplicationStateError, match="loopback HTTP"):
        EntityProgramVerifier(
            url,
            "entity-program-7",
            token_env="ENTITY_PROGRAM_TEST_TOKEN",
            data_home=tmp_path / "member-home",
            ingestion_db=tmp_path / "market.sqlite3",
        )
