from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from surface.core import SurfaceBroker, SurfaceConflictError
from surface.field_native import FieldNativeBackend
from surface.trading_paper import TradingPaperSurfaceBackend
from cassi_field_brain_entity import EntityConfig, FieldBrainEntity
from cassi_field_brain_server import EntityHTTPServer
from cassi_field_program import (
    SEMANTIC_PROGRAM_SCHEMA,
    SURFACE_PROCEDURE_SCHEMA,
    canonical_semantic_program_payload,
)


def _paper_surface_document_digest(value) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _write_paper_surface_document(path: Path, body: dict) -> dict:
    document = {**body, "content_sha256": _paper_surface_document_digest(body)}
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return document


def test_trading_paper_view_is_authenticated_scoped_and_read_only(tmp_path: Path) -> None:
    member_home = tmp_path / "member"
    member_home.mkdir()
    view_path = member_home / "trading-paper-application.json"
    ingestion_db = tmp_path / "market.sqlite3"
    binding = {
        "consumer_id": "canonical-trading-paper:BTC-USD:fixture",
        "ingestion_database": str(ingestion_db),
        "member_home": str(member_home),
        "member_id": "paper-member",
        "original_mission_id": "paper-mission",
        "paper_state_path": str(member_home / "trading-paper-state.json"),
        "symbol": "BTC-USD",
    }
    attestation = {
        "schema": "cassi.trading-entity-program-attestation.v1",
        "program_id": "paper-view-program",
        "created_at": "2026-09-22T12:00:00.000000Z",
        "mission_sha256": "a" * 64,
        "original_mission_id": "paper-mission",
    }
    binding_document = {
        "schema": "cassi.trading-paper-application-binding.v1",
        "binding": binding,
        "entity_program_attestation": attestation,
    }
    _write_paper_surface_document(
        member_home / "trading-paper-application-binding.json",
        binding_document,
    )
    verification = {
        "schema": "cassi.trading-entity-program-verification.v1",
        "program_id": attestation["program_id"],
        "status": "active",
        "mission_sha256": attestation["mission_sha256"],
        "member_home": binding["member_home"],
        "ingestion_database": binding["ingestion_database"],
        "scopes": {"member_home": True, "ingestion_database": True},
    }
    view_body = {
        "schema": "cassi.trading-paper-application.v1",
        "written_at": "2026-09-22T12:00:00.000000Z",
        "binding": binding,
        "entity_program": {
            "pinned_attestation": attestation,
            "verification_at_action_time": verification,
        },
        "paper_only": True,
        "external_effect": "none",
        "control": {
            "mode": "paper-only",
            "permission_scope": "simulated-paper-account-only",
            "external_order_path": False,
            "external_order_permission": False,
            "paper_exposure_permitted_at_action_time": True,
        },
        "source": {
            "kind": "canonical-market-ingestion",
            "database": binding["ingestion_database"],
            "health_at_action_time": {
                "state": "GREEN",
                "reasons": [],
                "can_open_exposure": True,
            },
            "latest_accepted_bar": {"observed_at": "2026-09-22T11:00:00Z"},
        },
        "field": {
            "symbol": "BTC-USD",
            "bar_count": 12,
            "decision_count": 1,
            "target": {"requested": 0.5, "applied": 0.25, "risk_state": "clear"},
            "risk": {"risk_state": "clear"},
            "uncertainty": {"uncertainty_state": "bounded"},
        },
        "paper": {
            "consumer_id": binding["consumer_id"],
            "symbol": "BTC-USD",
            "paper_only": True,
            "external_effect": "none",
            "account": {"cash": 9_500.0, "equity": 10_000.0, "positions": {}},
            "causal_fill_count": 1,
            "pending_order": None,
            "last_event": {"disposition": "filled"},
            "health": {"state": "GREEN", "can_open_exposure": True},
        },
    }
    _write_paper_surface_document(view_path, view_body)
    backend = TradingPaperSurfaceBackend(view_path)

    class NoBrain:
        def complete(self, *_args, **_kwargs):
            raise AssertionError("Surface capture must not call the brain")

    entity = FieldBrainEntity(
        EntityConfig(
            data_home=tmp_path / "entity",
            capability_root=Path(__file__).resolve().parents[2],
            research_home=tmp_path / "research",
            research_roots=(tmp_path,),
            research_resident_enabled=False,
            program_native_enabled=False,
        ),
        brain=NoBrain(),
        surface_backends=(backend,),
    )
    api_token = "paper-surface-test-token-0123456789"
    server = EntityHTTPServer(("127.0.0.1", 0), entity, api_token=api_token)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    try:
        program = entity.researcher.create_program(
            request_id="create-paper-view-program",
            program_id="paper-view-program",
            project_id="paper-view",
            title="Inspect the trading paper view",
            mission="Observe the digest-bound simulated paper account without control.",
            initial_question="What does the current paper application report?",
            observed_at="2026-09-22T12:00:00Z",
            cycle_limit=3,
            allowed_roots=[str(tmp_path)],
            allowed_tools=["surface_bind"],
            surface_scope={
                "sources": [{
                    "backend_id": "trading-paper",
                    "source_id": "paper-account",
                    "observation": ["accessibility"],
                    "operations": [],
                }]
            },
        )
        assert program["program_id"] == "paper-view-program"
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"

        def request(method: str, path: str, *, body=None, token: str = api_token):
            encoded = None if body is None else json.dumps(body).encode("utf-8")
            headers = {"Authorization": f"Bearer {token}"}
            if encoded is not None:
                headers["content-type"] = "application/json"
            req = Request(
                base_url + path,
                data=encoded,
                headers=headers,
                method=method,
            )
            try:
                with urlopen(req, timeout=5) as response:
                    return response.status, json.loads(response.read())
            except HTTPError as exc:
                return exc.code, json.loads(exc.read())

        source_path = (
            "/v1/surface/sources?backend_id=trading-paper"
            "&program_id=paper-view-program"
        )
        status, _ = request("GET", source_path, token="")
        assert status == 401

        status, source_response = request("GET", source_path)
        assert status == 200
        source = source_response["sources"][0]
        assert source["operations"] == []
        assert source["modalities"] == ["accessibility"]

        status, binding_response = request(
            "POST",
            "/v1/surface/bind",
            body={
                "program_id": "paper-view-program",
                "backend_id": "trading-paper",
                "source_id": "paper-account",
            },
        )
        assert status == 201
        binding_id = binding_response["binding_id"]
        capture_path = (
            f"/v1/surface/bindings/{binding_id}/capture"
            "?program_id=paper-view-program"
        )
        status, first = request("GET", capture_path)
        assert status == 200
        assert first["modalities"] == ["accessibility"]
        assert first["visual_available"] is False
        assert first["structure"]["byte_length"] > 0
        assert "member_home" not in json.dumps(first)

        view_body["paper"]["account"]["equity"] = 10_100.0
        view_body["written_at"] = "2026-09-22T12:00:01.000000Z"
        _write_paper_surface_document(view_path, view_body)
        status, second = request("GET", capture_path)
        assert status == 200
        assert second["generation"] > first["generation"]
        assert second["structure"]["sha256"] != first["structure"]["sha256"]

        tampered = json.loads(view_path.read_text(encoding="utf-8"))
        tampered["paper"]["account"]["equity"] = 99_999.0
        view_path.write_text(json.dumps(tampered), encoding="utf-8")
        status, _ = request("GET", capture_path)
        assert status == 503
    finally:
        if thread.is_alive():
            server.shutdown()
            thread.join(timeout=5)
        server.server_close()
        entity.close()


class _GenerationOwner:
    def __init__(self) -> None:
        self.generation = 0

    def admit_surface_publication(self, metadata, pixels):
        if pixels is not None:
            self.generation += 1
            return {"generation": self.generation}
        return {"generation": metadata["generation"]}

    def release_surface_publication(self, *_args):
        return True


def test_repeated_multimodal_capture_reuses_one_field_generation(tmp_path: Path) -> None:
    owner = _GenerationOwner()
    source = FieldNativeBackend("canvas")
    source.publish(
        bytes((1, 2, 3, 255)) * 4,
        width=2,
        height=2,
        accessibility={"role": "application", "name": "demo"},
    )
    broker = SurfaceBroker(tmp_path, owner)
    try:
        broker.register_backend(source)
        binding = broker.bind("field-native", "canvas")["binding_id"]
        first = broker.capture(binding)
        assert broker.capture(binding) == first
        assert owner.generation == 1
        assert first["structure"]["byte_length"] > 0

        with pytest.raises(SurfaceConflictError):
            broker.capture(binding, channels=["pixels"])

        source.publish(
            bytes((9, 8, 7, 255)) * 4,
            width=2,
            height=2,
            accessibility={"role": "application", "name": "next"},
        )
        later = broker.capture(binding)
        assert later["generation"] == 2
        assert later["sha256"] != first["sha256"]
    finally:
        broker.close()


class _LostAcknowledgmentSource(FieldNativeBackend):
    def __init__(self) -> None:
        super().__init__("canvas")
        self.dispatch_count = 0

    def dispatch(self, binding, action):
        self.dispatch_count += 1
        super().dispatch(binding, action)
        raise ConnectionError("acknowledgment lost after synthetic delivery")


def test_unknown_input_is_not_replayed_and_survives_restart(tmp_path: Path) -> None:
    source = _LostAcknowledgmentSource()
    source.publish(bytes((1, 2, 3, 255)) * 4, width=2, height=2)
    broker = SurfaceBroker(tmp_path, _GenerationOwner(), authorizer=lambda _proposal: True)
    try:
        broker.register_backend(source)
        binding = broker.bind("field-native", "canvas")["binding_id"]
        observation = broker.capture(binding)
        grant = broker.grant(
            "mission-a", binding, ["keyboard.text"],
            time.monotonic_ns() + 60_000_000_000, {"max_updates": 1},
        )
        intent = {
            "operation_id": "ambiguous-effect",
            "mission_id": "mission-a",
            "binding_id": binding,
            "grant_id": grant["grant_id"],
            "operation": "keyboard.text",
            "payload": {"text": "x"},
            "expected_source_epoch": observation["source_epoch"],
            "expected_geometry_revision": observation["geometry_revision"],
            "dependency_versions": {"publication_generation": observation["generation"]},
        }
        unknown = broker.submit_intent(intent)
        assert unknown["disposition"] == "unknown"
        assert broker.submit_intent(intent) == unknown
        assert source.dispatch_count == 1
    finally:
        broker.close()

    reopened = SurfaceBroker(tmp_path)
    try:
        assert reopened.inspect("ambiguous-effect")["disposition"] == "unknown"
        result = reopened.reconcile(
            "ambiguous-effect",
            {"status": "observed-success", "observation": "synthetic delivery witnessed"},
        )
        assert result["state"] == "reconciled"
        assert result["reconciliation"]["status"] == "observed-success"
    finally:
        reopened.close()


@pytest.mark.parametrize("with_audio", [False, True])
def test_field_procedure_delivers_once_then_observes_application(
    tmp_path: Path, with_audio: bool,
) -> None:
    """The resident field, not a host-side macro, emits and completes the action."""
    application = FieldNativeBackend("canvas")

    def publish(name: str) -> None:
        application.publish(
            bytes((20, 50, 130, 255)) * 4,
            width=2,
            height=2,
            sample_time_ns=time.monotonic_ns(),
            sample_clock_domain="host-monotonic",
            accessibility={"role": "window", "name": name},
        )

    class NoBrain:
        def complete(self, *_args, **_kwargs):
            raise AssertionError("the resident procedure must not call the brain")

    publish("before")
    if with_audio:
        application.publish_audio(
            b"\x00\x00" * 16,
            sample_rate=8_000,
            channels=1,
            sample_time_ns=time.monotonic_ns(),
            sample_clock_domain="host-monotonic",
        )
    entity = FieldBrainEntity(
        EntityConfig(
            data_home=tmp_path / "entity",
            capability_root=Path(__file__).resolve().parents[2],
            research_home=tmp_path / "research",
            research_roots=(tmp_path,),
            research_resident_enabled=False,
            program_native_enabled=False,
        ),
        brain=NoBrain(),
        surface_backends=(application,),
        surface_authorizer=lambda proposal: proposal.get("source_id") == "canvas",
    )
    try:
        director = entity.researcher
        program = director.create_program(
            request_id="create-canvas",
            program_id="canvas-mission",
            project_id="canvas",
            title="Work with the canvas",
            mission="Issue one text event and inspect the changed canvas.",
            initial_question="What is on the canvas?",
            observed_at="2026-09-22T00:00:00Z",
            cycle_limit=3,
            allowed_roots=[str(tmp_path)],
            allowed_tools=[
                "surface_bind", "surface_grant",
                "surface_advance_procedure", "surface_inspect_effect",
            ],
            surface_scope={"sources": [{
                "backend_id": "field-native",
                "source_id": "canvas",
                "observation": ["pixels", "accessibility"] + (["audio"] if with_audio else []),
                "operations": ["keyboard.text"] + (["audio.capture"] if with_audio else []),
            }]},
        )
        capabilities = director.capabilities
        binding = capabilities.execute(
            "surface_bind", {"backend_id": "field-native", "source_id": "canvas"},
            program=program, operation_id="bind-canvas",
        )["result"]["binding"]
        granted = capabilities.execute(
            "surface_grant",
            {
                "binding_id": binding["binding_id"],
                "expected_source_epoch": binding["source_epoch"],
                "expected_geometry_revision": binding["geometry_revision"],
                "operations": ["keyboard.text"] + (["audio.capture"] if with_audio else []),
                "duration_seconds": 60,
            },
            program=program, operation_id="grant-canvas",
        )["result"]
        assert "grant_id" not in granted
        contract = {
            "schema": SURFACE_PROCEDURE_SCHEMA,
            "purpose": "type-once",
            "target": {"kind": "field-native", "identity": "canvas"},
            "dependencies": [
                {"path": "context.surface.capture.generation", "role": "observed-version", "type": "integer"},
                {"path": "context.surface.binding.source_epoch", "role": "observed-version", "type": "integer"},
                {"path": "context.surface.binding.geometry_revision", "role": "observed-version", "type": "integer"},
                {"path": "context.surface.binding.source_id", "role": "target", "type": "string"},
            ],
            "capability_requirements": ["keyboard.text"],
            "expected_effect": {"context.after": "done"},
            "applicability": [],
            "stop_conditions": [],
            "known_exceptions": [],
            "experience": [],
            "max_duration_ns": 30_000_000_000,
            "max_intentions": 1,
            "maximum_observation_age_ns": 30_000_000_000,
            "control_flow": {"op": "sequence", "steps": [
                {"op": "intent", "operation": "keyboard.text",
                 "payload": {"text": "h"}, "expected_effect": {"context.after": "done"}},
                {"op": "complete"},
            ]},
            "recovery_choices": [],
        }
        if with_audio:
            contract["dependencies"].append({
                "path": "context.surface.capture.audio.sample_count",
                "role": "source",
                "type": "integer",
            })
        payload = canonical_semantic_program_payload({
            "schema": SEMANTIC_PROGRAM_SCHEMA,
            "program_kind": "procedure",
            "arguments": {},
            "effects": {"emits": [], "reads": [], "writes": []},
            "guards": [],
            "bounds": {"max_branches": 2, "max_horizon": 4, "max_work": 16},
            "body": {"surface_contract": contract},
            "applicability": {},
        })
        registration = entity.memory.semantic({
            "operation": "register",
            "operation_id": "register-canvas-procedure",
            "kind": "Program",
            "record_id": "procedure:canvas-once",
            "payload": {"program_role": "procedure", "program": payload},
        })
        request = {
            "binding_id": binding["binding_id"],
            "expected_source_epoch": binding["source_epoch"],
            "expected_geometry_revision": binding["geometry_revision"],
            "grant_ref": granted["grant_ref"],
            "procedure_ref": registration["result"]["record"],
            "run_id": "canvas-once",
            "context": {"after": "not-yet"},
        }
        first = capabilities.execute(
            "surface_advance_procedure", request,
            program=program, operation_id="advance-canvas-first",
        )["result"]
        assert first["run_status"] == "intent-pending"
        assert first["effect"]["disposition"] == "delivered"
        assert first["effect"]["ack_strength"] == "queued-only"
        effect_id = first["effect"]["surface_effect_id"]
        effect = capabilities.execute(
            "surface_inspect_effect", {"surface_effect_id": effect_id},
            program=program, operation_id="inspect-canvas-effect",
        )["result"]
        assert effect["disposition"] == "delivered"
        publish("after")
        continuation = capabilities.execute(
            "surface_advance_procedure",
            {
                **request,
                "checkpoint_ref": first["checkpoint"],
                "surface_effect_id": effect_id,
                "context": {"after": "done"},
            },
            program=program, operation_id="advance-canvas-second",
        )["result"]
        assert continuation["run_status"] == "completed"
        event = application.next_input()
        assert event is not None
        assert event["operation"] == "keyboard.text"
        assert event["arguments"] == {"text": "h"}
        assert application.next_input() is None
        assert "grant_id" not in first and "grant_id" not in continuation
    finally:
        entity.close()
