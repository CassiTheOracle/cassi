import hashlib
import json
from types import SimpleNamespace

from cassi_entity_activities import TradingActivity


def _receipt(processed_bars=1):
    event_id = "market-event-42"
    canonical_event = {
        "event_id": event_id,
        "source_id": "exchange-feed",
        "source_revision": "revision-42",
        "observed_at": "2026-09-23T12:00:00Z",
        "available_at": "2026-09-23T12:00:01Z",
        "payload": {
            "timestamp": "2026-09-23T12:00:00Z",
            "symbol": "BTC-USD",
            "open": 100.0,
            "high": 108.0,
            "low": 99.0,
            "close": 106.0,
            "volume": 12.5,
        },
    }
    canonical_sha = hashlib.sha256(json.dumps(
        canonical_event, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    latest = {
        "canonical_event_id": event_id,
        "canonical_event_sha256": canonical_sha,
        "canonical_event": canonical_event,
        "field_decision_event_id": "decision-42",
        "field_decision": {
            "state": {"return_1": 0.125, "volatility": 0.08, "momentum": -0.02},
            "selection_source": "root-method",
        },
        "target_application": {
            "requested_target": 0.5,
            "applied_target": 0.25,
        },
        "disposition": "paper-filled",
        "execution_model": "causal-next-bar-v1",
        "fill": {"price": 106.0, "quantity": 0.25, "side": "buy"},
        "settlement": {
            "status": "filled",
            "signal_event_id": "market-event-41",
            "field_decision_event_id": "decision-41",
            "execution_event_id": event_id,
            "signal_reference_price": 104.0,
            "execution_reference_price": 106.0,
            "signal_to_execution_seconds": 3600.0,
            "execution_price": 106.0,
            "pending_order": {
                "signal_event_id": "market-event-41",
                "signal_canonical_event_sha256": "a" * 64,
            },
        },
        "account": {"equity": 1000.0, "position": 0.25},
        "data_health": {"state": "GREEN"},
        "field_internal_modeled_outcomes": {"decision-42": {"modeled_return": 0.03}},
        "ledger_event_id": "paper-ledger-event-42",
        "content_sha256": "p" * 64,
    }
    return {
        "status": "PASS",
        "processed_bars": processed_bars,
        "source": {"accepted_event_root_sha256": "r" * 64},
        "paper_status": {
            "last_receipt": latest,
            "source": {
                "canonical_event_id": event_id,
                "canonical_event_sha256": canonical_sha,
                "source_id": "exchange-feed",
                "source_revision": "revision-42",
                "observed_at": "2026-09-23T12:00:00Z",
                "available_at": "2026-09-23T12:00:01Z",
            },
            "last_event": {
                "canonical_event_id": event_id,
                "paper_receipt_event_id": "paper-ledger-event-42",
                "paper_receipt_sha256": "p" * 64,
            },
            "health": {"state": "GREEN"},
        },
    }


def _run_from_existing_receipt(tmp_path, monkeypatch, receipt, operation_id):
    data_home = tmp_path / "member"
    entity = SimpleNamespace(
        config=SimpleNamespace(data_home=data_home, entity_id="member-1"),
    )
    activity = TradingActivity(
        data_home=tmp_path / "market", ingestion_db=tmp_path / "market.sqlite",
        paper_program_id="program-1",
    )
    activity.attach(entity)
    activity.ingestion_db.touch()
    receipt_path = data_home / "activities" / "trading" / hashlib.sha256(
        operation_id.encode("utf-8")
    ).hexdigest() / "receipt.json"
    receipt_path.parent.mkdir(parents=True)
    body = json.dumps(receipt, separators=(",", ":")).encode("utf-8")
    receipt_path.write_bytes(body)
    monkeypatch.setattr("cassi_entity_activities._current_program", lambda *args: {"program_id": "program-1"})
    monkeypatch.setattr("cassi_entity_activities._admit_intent", lambda *args: False)
    monkeypatch.setattr("cassi_entity_activities._field_result", lambda *args: None)
    result = activity.run(
        "paper-step", {}, program={"program_id": "program-1"}, operation_id=operation_id,
    )
    return result, body


def test_paper_observation_preserves_causal_market_and_actual_account_evidence(tmp_path, monkeypatch):
    result, raw_receipt = _run_from_existing_receipt(
        tmp_path, monkeypatch, _receipt(), "paper-observation",
    )

    observation = result["mathematical_observation"]
    assert result["artifact"]["sha256"] == hashlib.sha256(raw_receipt).hexdigest()
    assert result["artifact"]["metadata"]["source_path"].endswith("receipt.json")
    assert result["artifact"]["metadata"]["source_revision_sha256"] == result["artifact"]["sha256"]
    assert result["source_refs"] == [
        result["artifact"]["sha256"], observation["source"]["canonical_event_sha256"],
        "a" * 64,
    ]
    assert observation["source"]["observed_at"] == "2026-09-23T12:00:00Z"
    assert observation["source"]["available_at"] == "2026-09-23T12:00:01Z"
    assert observation["market"] == {
        "symbol": "BTC-USD", "open": 100.0, "high": 108.0, "low": 99.0,
        "close": 106.0, "volume": 12.5,
    }
    assert observation["paper"]["fill"] == {"price": 106.0, "quantity": 0.25, "side": "buy"}
    assert observation["paper"]["account"]["position"] == 0.25
    assert observation["paper"]["feed_health"] == {"state": "GREEN"}
    assert observation["paper"]["disposition"] == "paper-filled"
    assert observation["paper"]["settlement"]["signal_event_id"] == "market-event-41"
    assert observation["paper"]["settlement"]["signal_reference_price"] == 104.0
    assert observation["paper"]["settlement"]["execution_event_id"] == "market-event-42"
    assert observation["paper"]["settlement"]["signal_canonical_event_sha256"] == "a" * 64
    assert observation["paper"]["pending_intent"] is None
    assert observation["decision"]["state"] == {
        "return_1": 0.125, "volatility": 0.08, "momentum": -0.02,
    }
    assert observation["decision"]["requested_target"] == 0.5
    assert observation["decision"]["applied_target"] == 0.25
    assert observation["modeled_field_outcomes"] == {"decision-42": {"modeled_return": 0.03}}


def test_no_new_paper_bar_does_not_republish_stale_observation(tmp_path, monkeypatch):
    receipt = _receipt(processed_bars=0)
    result, raw_receipt = _run_from_existing_receipt(
        tmp_path, monkeypatch, receipt, "paper-no-new-bar",
    )

    assert "mathematical_observation" not in result
    assert result["artifact"]["sha256"] == hashlib.sha256(raw_receipt).hexdigest()
