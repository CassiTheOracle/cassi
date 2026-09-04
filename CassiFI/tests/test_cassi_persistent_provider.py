from __future__ import annotations

import base64
import hashlib
from dataclasses import replace
from collections.abc import Mapping
import http.server
import json
from pathlib import Path
import threading
import urllib.error
import urllib.request
from typing import Any, cast

import pytest
import torch

import cassi_persistent_provider as provider_module
from cassi_persistent_provider import (
    CONTEXT_STREAM_METADATA_KEY,
    DEFAULT_INGRESS_MAX_BYTES,
    DEFAULT_HOST,
    DEFAULT_MAX_OUTPUT_SYMBOLS,
    DEFAULT_PORT,
    EMPTY_CONTEXT_EVENT_ID,
    LAST_COMPLETION_METADATA_KEY,
    MODEL_NAME,
    PHI_PROVIDER_CONFIG_SCHEMA,
    PROTOCOL,
    VERSION,
    PersistentFieldProvider,
    ProviderConfig,
    ProviderError,
    build_parser,
    _Handler,
    _canonical as provider_canonical,
)
from cassi_mnemic_condensation import mnemic_field_address
from cassi_phi_harmonic_language import (
    PhiHarmonicLanguageConfig,
    PhiHarmonicLanguageController,
)
from cassi_universal_data import CODEC_OPAQUE, CODEC_TEXT, ZERO_SHA256


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

def _start_http_provider(
    provider: PersistentFieldProvider,
    *,
    world_token: str | None = None,
) -> tuple[http.server.ThreadingHTTPServer, threading.Thread]:
    class Handler(_Handler):
        pass

    Handler.provider = provider
    Handler.world_token = world_token
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        cast(Any, Handler),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _stop_http_provider(
    server: http.server.ThreadingHTTPServer,
    thread: threading.Thread,
) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5.0)


def _post_provider(
    server: http.server.ThreadingHTTPServer,
    path: str,
    body: Mapping[str, Any],
    *,
    token: str | None = None,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_port}{path}",
        data=_canonical(body),
        headers=headers,
        method="POST",
    )
    try:
        response = urllib.request.urlopen(request, timeout=30.0)
    except urllib.error.HTTPError as error:
        raise AssertionError(error.read().decode("utf-8")) from error
    with response:
        decoded = json.loads(response.read())
    if not isinstance(decoded, dict):
        raise AssertionError("provider response must be an object")
    return decoded


def _post_provider_error(
    server: http.server.ThreadingHTTPServer,
    path: str,
    body: Mapping[str, Any],
    *,
    token: str | None = None,
    expected_status: int = 400,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_port}{path}",
        data=_canonical(body),
        headers=headers,
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(request, timeout=30.0)
    assert caught.value.code == expected_status
    decoded = json.loads(caught.value.read())
    if not isinstance(decoded, dict):
        raise AssertionError("provider error response must be an object")
    return decoded


def test_cross_language_canonical_wire_fixtures() -> None:
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "mnemic_canonical_wire_v1.json")
        .read_text(encoding="utf-8")
    )
    assert fixture["schema"] == "cassicore.mnemic.field-canonical-fixtures.v1"
    for item in fixture["cases"]:
        canonical = provider_canonical(item["value"])
        assert canonical.decode("utf-8") == item["canonical"]
        assert hashlib.sha256(canonical).hexdigest() == item["sha256"]
    for item in fixture["noncanonical"]:
        assert provider_canonical(json.loads(item["wire"])).decode("utf-8") == item["canonical"]
        assert item["wire"] != item["canonical"]


def _revision(record_id: str, text: str) -> str:
    return hashlib.sha256(f"{record_id}\0{text}".encode()).hexdigest()

def _field_address(
    record_id: str,
    text: str,
    revision: str,
    *,
    semantic_kind: str = "fact",
) -> str:
    return mnemic_field_address(
        record_id=record_id,
        revision=revision,
        start_byte=0,
        end_byte=len(text.encode("utf-8")),
        semantic_kind=semantic_kind,
    ).hex()


def _event(
    *,
    user: str,
    stream_id: str,
    sequence: int,
    previous_event_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    event_id = hashlib.sha256(
        _canonical(
            {
                "stream_id": stream_id,
                "sequence": sequence,
                "previous_event_id": previous_event_id,
                "payload": payload,
            }
        )
    ).hexdigest()
    return {
        "user": user,
        "stream_id": stream_id,
        "sequence": sequence,
        "previous_event_id": previous_event_id,
        "event_id": event_id,
        "payload": payload,
    }


def _memory_payload(
    operation: str, record_id: str, text: str, revision: str
) -> dict[str, Any]:
    return {
        "kind": "memory",
        "context_session_id": "context",
        "operation": operation,
        "record": {
            "id": record_id,
            "content": text,
            "node_type": "fact",
            "revision": revision,
            "field_address": _field_address(record_id, text, revision),
        },
    }


def _feedback_payload(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    turn_id: int = 1,
    outcome: str = "completed",
    tool_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "kind": "feedback",
        "context_session_id": "context",
        "turn_id": turn_id,
        "query": query,
        "candidates": candidates,
        "outcome": outcome,
    }
    if tool_result is not None:
        payload["tool_result"] = tool_result
    return payload


def _candidate(
    record_id: str,
    text: str,
    revision: str,
    *,
    candidate_id: str | None = None,
    start_byte: int = 0,
) -> dict[str, Any]:
    return {
        "id": record_id if candidate_id is None else candidate_id,
        "record_id": record_id,
        "revision": revision,
        "start_byte": start_byte,
        "end_byte": start_byte + len(text.encode("utf-8")),
        "text": text,
        "field_address": _field_address(
            record_id,
            text,
            revision,
        ),
    }


def _provider_config(
    root: Path,
    *,
    extra_exchanges: tuple[tuple[bytes, bytes], ...] = (),
) -> ProviderConfig:
    phi_config = PhiHarmonicLanguageConfig(mode_count=640)
    config_path = root / "phi-config.json"
    config_path.write_text(
        json.dumps(
            {"schema": PHI_PROVIDER_CONFIG_SCHEMA, **phi_config.to_dict()},
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    controller = PhiHarmonicLanguageController(phi_config)
    learned = controller.learn_exchanges(
        controller.new_state(batch_size=1, dtype=torch.float32),
        (
            (b"hello", "café".encode("utf-8")),
            (b"status", b"ready"),
            *extra_exchanges,
        ),
    )
    checkpoint_path = root / "field-state.pt"
    checkpoint_path.write_bytes(controller.dump_state_bytes(learned))
    return ProviderConfig(
        phi_config_path=config_path,
        corpus_checkpoint_path=checkpoint_path,
        state_dir=root / "sessions",
        max_output_symbols=16,
    )


def _start(
    root: Path,
    *,
    extra_exchanges: tuple[tuple[bytes, bytes], ...] = (),
) -> PersistentFieldProvider:
    provider = PersistentFieldProvider(
        _provider_config(root, extra_exchanges=extra_exchanges)
    )
    provider.start()
    return provider


def _completion(
    prompt: str,
    *,
    user: str,
    max_tokens: int = 16,
) -> dict[str, Any]:
    return {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "user": user,
    }

def _ingress_request(
    *,
    codec_id: str,
    payload: bytes,
    head_sha256: str,
    sequence: int,
) -> dict[str, Any]:
    instant = {"numerator": sequence, "denominator": 1}
    return {
        "codec_id": codec_id,
        "packet": {
            "run_id": "provider-ingress-run",
            "episode_id": f"provider-ingress-episode-{sequence}",
            "world_id": "provider-ingress-world",
            "session_id": "provider-ingress-session",
            "profile_sha256": "1" * 64,
            "clock_sha256": "2" * 64,
            "request_id": f"provider-ingress-{sequence}",
            "logical_tick": sequence,
            "logical_time": instant,
            "capture_start": instant,
            "capture_end": instant,
            "source_epoch": "provider-ingress-v1",
            "source_stream_id": "provider-ingress-stream",
            "source_sequence": sequence,
            "ingress_journal_sha256": head_sha256,
            "body_frame_id": "provider-ingress-frame",
            "payload_shape": [len(payload)],
            "payload_dtype": "uint8",
            "valid": True,
        },
        "payload_base64": base64.b64encode(payload).decode("ascii"),
    }




def test_provider_identity_and_cli_defaults() -> None:
    args = build_parser().parse_args([])
    assert args.host == DEFAULT_HOST
    assert args.port == DEFAULT_PORT
    assert args.max_output_symbols == DEFAULT_MAX_OUTPUT_SYMBOLS
    assert args.ingress_max_bytes == DEFAULT_INGRESS_MAX_BYTES
    assert args.phi_config.name == "cassi-phi-harmonic-language.json"
    assert MODEL_NAME == "cassi-phi-harmonic-language-v1"
    assert PROTOCOL == "Cassi Phi-harmonic field provider"
    assert VERSION == 8


def test_startup_builds_one_shared_tensor_with_mnemic_view(tmp_path: Path) -> None:
    provider = _start(tmp_path)
    try:
        assert provider.store is not None
        assert provider.initial_state is not None
        assert provider.mnemic_controller is not None
        shared = provider.store.initial(provider.initial_state)
        provider.store.layout.validate(shared)
        mnemic = provider.store.layout.mnemic(shared)
        assert mnemic.field.untyped_storage().data_ptr() == shared.field.untyped_storage().data_ptr()
        assert provider.mnemic_controller.state_sha256(mnemic) == (
            provider.mnemic_controller.state_sha256(
                provider.store.initial_mnemic_state
            )
        )
    finally:
        provider.close()

def test_legacy_two_band_checkpoint_upgrades_on_live_observation_and_replays(
    tmp_path: Path,
) -> None:
    provider = _start(tmp_path)
    try:
        assert provider.store is not None
        assert provider.initial_state is not None
        store = provider.store
        legacy = store.layout.legacy_join(
            provider.initial_state,
            store.initial_counterflow_state,
        )
        owned = legacy.field.detach().cpu().contiguous()
        field_payload = owned.numpy().tobytes(order="C")
        metadata_payload = provider_module._canonical(
            {CONTEXT_STREAM_METADATA_KEY: {}}
        )
        header = {
            "schema": provider_module.LEGACY_SHARED_FIELD_SESSION_SCHEMA,
            "session_id": "legacy",
            "provider_fingerprint": store.legacy_provider_fingerprint,
            "config_fingerprint": store.controller.config_fingerprint,
            "codebook_fingerprint": store.controller.codebook_fingerprint,
            "counterflow_config_fingerprint": (
                store.counterflow_runtime.config_fingerprint
            ),
            "layout_fingerprint": store.layout.legacy_fingerprint,
            "field_shape": list(store.layout.legacy_shared_shape),
            "field_dtype": str(owned.dtype),
            "field_bytes": len(field_payload),
            "field_payload_sha256": hashlib.sha256(field_payload).hexdigest(),
            "shared_state_sha256": store.layout.legacy_state_sha256(legacy),
            "phi_state_sha256": store.controller.state_sha256(
                store.layout.legacy_phi(legacy)
            ),
            "counterflow_state_sha256": store.counterflow_runtime.state_sha256(
                store.layout.legacy_counterflow(legacy)
            ),
            "metadata_bytes": len(metadata_payload),
            "metadata_sha256": hashlib.sha256(metadata_payload).hexdigest(),
        }
        def encode_frame(
            frame_header: Mapping[str, Any],
            frame_metadata: bytes,
        ) -> bytes:
            header_payload = provider_module._canonical(frame_header)
            body = (
                provider_module._SESSION_MAGIC
                + len(header_payload).to_bytes(8, "big")
                + header_payload
                + field_payload
                + frame_metadata
            )
            return body + hashlib.sha256(body).digest()

        raw = encode_frame(header, metadata_payload)
        path = store.path_for("legacy")
        invalid_metadata = provider_module._canonical(
            {
                CONTEXT_STREAM_METADATA_KEY: {},
                "legacy_context_associations": {},
            }
        )
        invalid_header = {
            **header,
            "metadata_bytes": len(invalid_metadata),
            "metadata_sha256": hashlib.sha256(invalid_metadata).hexdigest(),
        }
        path.write_bytes(encode_frame(invalid_header, invalid_metadata))
        with pytest.raises(
            ProviderError,
            match="session metadata contains unsupported keys",
        ):
            store.load("legacy")

        path.write_bytes(raw)

        status = provider.context_status(
            {"user": "legacy", "stream_id": "legacy-stream"}
        )
        assert status["checkpoint"]["status"] == "compatible"
        assert path.read_bytes() == raw
        loaded = store.load("legacy")
        assert loaded is not None
        migrated, _metadata, _, _ = loaded
        store.layout.validate(migrated)
        assert store.controller.state_sha256(store.layout.phi(migrated)) == (
            header["phi_state_sha256"]
        )
        assert store.counterflow_runtime.state_sha256(
            store.layout.counterflow(migrated)
        ) == header["counterflow_state_sha256"]
        assert provider.mnemic_controller is not None
        assert provider.mnemic_controller.state_sha256(
            store.layout.mnemic(migrated)
        ) == provider.mnemic_controller.state_sha256(
            store.initial_mnemic_state
        )
        assert path.read_bytes() == raw

        text = "legacy checkpoint live migration memory"
        revision = _revision("legacy-record", text)
        event = _event(
            user="legacy",
            stream_id="legacy-stream",
            sequence=1,
            previous_event_id=EMPTY_CONTEXT_EVENT_ID,
            payload=_memory_payload("store", "legacy-record", text, revision),
        )
        observed = provider.observe_context(event)
        assert observed["duplicate"] is False
        upgraded_raw = path.read_bytes()
        upgraded_header, _, _ = store._decode_frame(upgraded_raw)
        assert upgraded_header["schema"] == provider_module.SHARED_FIELD_SESSION_SCHEMA
        assert upgraded_header["provider_fingerprint"] == store.provider_fingerprint
        assert upgraded_header["phi_state_sha256"] == header["phi_state_sha256"]
        assert upgraded_header["counterflow_state_sha256"] == (
            header["counterflow_state_sha256"]
        )
        assert "mnemic_state_sha256" in upgraded_header

        replayed = provider.observe_context(event)
        assert replayed["duplicate"] is True
        assert replayed["state_in_sha256"] == observed["state_out_sha256"]
        assert replayed["state_out_sha256"] == observed["state_out_sha256"]
        assert replayed["checkpoint_sha256"] == observed["checkpoint_sha256"]
        assert path.read_bytes() == upgraded_raw
    finally:
        provider.close()


def test_authenticated_particle_world_turn_and_result_are_idempotent(
    tmp_path: Path,
) -> None:
    token = "cassi-world-test-token"
    message = "Arrange the selected particles into a ring around the cursor radius 2"
    outcome = {
        "schema": "cassi.particle-result.v1",
        "status": "applied",
        "affected_count": 96,
        "post_state_digest": "a" * 64,
    }
    provider = _start(tmp_path)
    server, thread = _start_http_provider(provider, world_token=token)
    turn_request = {
        "user": "particle-world-test",
        "world_id": "cosmos-main",
        "request_id": "turn-0001",
        "message": message,
        "context": {
            "cursor": [0.0, 0.0, 0.0],
            "selection": {"type": "all"},
            "particle_count": 96,
            "constraints": {
                "maximum_particles": 96,
                "maximum_displacement": 20.0,
                "maximum_speed": 4.0,
            },
        },
        "max_tokens": 8,
    }
    try:
        unauthorized = _post_provider_error(
            server,
            "/v1/world/turn",
            turn_request,
            expected_status=401,
        )
        assert unauthorized["error"]["type"] == "authentication_error"

        turn = _post_provider(
            server, "/v1/world/turn", turn_request, token=token
        )
        assert turn["schema"] == "cassi.world-turn.v1"
        assert turn["request_id"] == "turn-0001"
        assert turn["planner"] == "deterministic"
        assert turn["staged_program"]["schema"] == "cassi.particle-program.v1"
        assert turn["staged_program"]["target"]["type"] == "ring"
        assert len(turn["program_digest"]) == 64
        assert turn["assistant"].startswith("Staged a ring arrangement")
        assert turn["field_receipt"]["schema"] == "cassi.world-field-observation.v1"
        assert (
            turn["field_receipt"]["state_in_sha256"]
            != turn["field_receipt"]["state_out_sha256"]
        )
        duplicate_turn = _post_provider(
            server, "/v1/world/turn", turn_request, token=token
        )
        assert duplicate_turn == turn

        conflict = dict(turn_request)
        conflict["message"] = "Arrange all particles into a line"
        conflict_error = _post_provider_error(
            server,
            "/v1/world/turn",
            conflict,
            token=token,
        )
        assert "request_id conflict" in conflict_error["error"]["message"]

        result_request = {
            "user": "particle-world-test",
            "world_id": "cosmos-main",
            "request_id": "turn-0001",
            "program_digest": turn["program_digest"],
            "outcome": outcome,
        }
        result = _post_provider(
            server, "/v1/world/result", result_request, token=token
        )
        assert result["schema"] == "cassi.world-result.v1"
        assert result["observed_once"] is True
        assert result["status"] == "applied"
        assert result["assistant"].startswith("Observed the applied result")
        assert (
            result["field_receipt"]["state_in_sha256"]
            != result["field_receipt"]["state_out_sha256"]
        )
        duplicate_result = _post_provider(
            server, "/v1/world/result", result_request, token=token
        )
        assert duplicate_result == result

        conflicting_result = dict(result_request)
        conflicting_result["outcome"] = {
            **result_request["outcome"],
            "affected_count": 95,
        }
        result_error = _post_provider_error(
            server,
            "/v1/world/result",
            conflicting_result,
            token=token,
        )
        assert "request_id conflict" in result_error["error"]["message"]
    finally:
        _stop_http_provider(server, thread)
        provider.close()

def test_exact_ingress_http_round_trips_replays_and_abstains(
    tmp_path: Path,
) -> None:
    config = _provider_config(tmp_path)
    provider = PersistentFieldProvider(config)
    provider.start()
    server, thread = _start_http_provider(provider)
    payload = b"\x00\xffCassi\x80\x00"
    append_request = _ingress_request(
        codec_id=CODEC_OPAQUE,
        payload=payload,
        head_sha256=ZERO_SHA256,
        sequence=1,
    )
    try:
        assert provider.controller is not None
        assert provider.initial_state is not None
        state_sha256 = provider.controller.state_sha256(provider.initial_state)
        noncanonical = _ingress_request(
            codec_id=CODEC_OPAQUE,
            payload=b"f",
            head_sha256=ZERO_SHA256,
            sequence=1,
        )
        noncanonical["payload_base64"] = "Zh=="
        with pytest.raises(ProviderError, match="canonical base64"):
            provider.append_ingress(noncanonical)
        assert provider.ingress_journal is not None
        assert provider.ingress_journal.head_sha256 == ZERO_SHA256

        appended = _post_provider(
            server, "/v1/ingress/append", append_request
        )
        assert appended["schema"] == "cassi.provider.ingress-receipt.v1"
        assert appended["operation"] == "append"
        assert appended["adapter"] == {
            "status": "selected",
            "reason": None,
            "view_sha256": appended["adapter"]["view_sha256"],
            "modality": "opaque",
            "root_constructor": "Atom",
        }
        assert len(appended["adapter"]["view_sha256"]) == 64
        assert appended["packet"]["payload_sha256"] == hashlib.sha256(
            payload
        ).hexdigest()
        assert appended["semantic_status"] == "unsupported"
        assert appended["semantic_reason"] == "no_semantic_task"
        assert appended["thalamus_admission"] == "policy_required"
        assert appended["adaptive_state_changed"] is False
        assert appended["mnemic_observation_input"] == {
            "contextSessionId": "provider-ingress-session",
            "recordId": appended["packet"]["event_id"],
            "packetSha256": appended["journal"]["packet_sha256"],
            "packetObjectSha256": appended["journal"][
                "packet_object_sha256"
            ],
            "payloadManifestSha256": appended["journal"][
                "payload_manifest_sha256"
            ],
            "journalHeadSha256": appended["journal"]["journal_head_sha256"],
            "viewSha256": appended["adapter"]["view_sha256"],
            "codecId": CODEC_OPAQUE,
            "sourceStreamId": "provider-ingress-stream",
            "sourceSequence": 1,
            "sourcePath": [],
            "sourceSpan": [0, len(payload)],
        }

        duplicate = _post_provider(
            server, "/v1/ingress/append", append_request
        )
        assert duplicate["journal"] == appended["journal"]
        assert duplicate["packet"] == appended["packet"]

        read_back = _post_provider(
            server,
            "/v1/ingress/read",
            {
                "codec_id": CODEC_OPAQUE,
                "reference": appended["journal"],
            },
        )
        assert read_back["operation"] == "read"
        assert base64.b64decode(read_back["payload_base64"], validate=True) == payload
        assert read_back["adapter"]["view_sha256"] == appended["adapter"][
            "view_sha256"
        ]

        malformed = _post_provider(
            server,
            "/v1/ingress/append",
            _ingress_request(
                codec_id=CODEC_TEXT,
                payload=b"\xff",
                head_sha256=appended["journal"]["journal_head_sha256"],
                sequence=2,
            ),
        )
        assert malformed["adapter"] == {
            "status": "unsupported",
            "reason": "malformed_input",
            "view_sha256": None,
            "modality": None,
            "root_constructor": None,
        }
        assert malformed["mnemic_observation_input"] is None
        assert malformed["semantic_status"] == "unsupported"
        assert malformed["semantic_reason"] == "no_semantic_task"
        assert malformed["adaptive_state_changed"] is False

        replay = _post_provider(
            server, "/v1/ingress/replay", {"limit": 1}
        )
        assert replay["head_sha256"] == malformed["journal"][
            "journal_head_sha256"
        ]
        assert replay["total_entries"] == 2
        assert replay["returned_entries"] == 1
        assert replay["truncated"] is True
        assert replay["entries"][0]["adapter"]["status"] == "unsupported"
        assert provider.controller.state_sha256(provider.initial_state) == state_sha256
    finally:
        _stop_http_provider(server, thread)
        provider.close()

    restarted = PersistentFieldProvider(config)
    restarted.start()
    restarted_server, restarted_thread = _start_http_provider(restarted)
    try:
        replayed = _post_provider(
            restarted_server, "/v1/ingress/replay", {"limit": 8}
        )
        assert replayed["total_entries"] == 2
        assert replayed["returned_entries"] == 2
        assert replayed["truncated"] is False
        assert [row["adapter"]["status"] for row in replayed["entries"]] == [
            "selected",
            "unsupported",
        ]
        reread = _post_provider(
            restarted_server,
            "/v1/ingress/read",
            {
                "codec_id": CODEC_OPAQUE,
                "reference": appended["journal"],
            },
        )
        assert base64.b64decode(reread["payload_base64"], validate=True) == payload
        assert reread["packet"] == appended["packet"]
    finally:
        _stop_http_provider(restarted_server, restarted_thread)
        restarted.close()


def test_ingress_http_enforces_configured_body_and_journal_capacity(
    tmp_path: Path,
) -> None:
    config = replace(_provider_config(tmp_path), ingress_max_bytes=1024)
    provider = PersistentFieldProvider(config)
    provider.start()
    server, thread = _start_http_provider(provider)
    try:
        oversized = _post_provider_error(
            server,
            "/v1/ingress/append",
            _ingress_request(
                codec_id=CODEC_OPAQUE,
                payload=b"x" * (100 * 1024),
                head_sha256=ZERO_SHA256,
                sequence=1,
            ),
        )
        assert oversized["error"]["message"] == (
            "request body is missing or exceeds the route limit"
        )
        assert provider.ingress_journal is not None
        assert provider.ingress_journal.head_sha256 == ZERO_SHA256

        capacity = _post_provider_error(
            server,
            "/v1/ingress/append",
            _ingress_request(
                codec_id=CODEC_OPAQUE,
                payload=b"x" * config.ingress_max_bytes,
                head_sha256=ZERO_SHA256,
                sequence=1,
            ),
        )
        assert "capacity" in capacity["error"]["message"]
        assert provider.ingress_journal.head_sha256 == ZERO_SHA256
        assert not tuple(provider.ingress_journal.objects.iterdir())
        assert not tuple(provider.ingress_journal.blobs.iterdir())
    finally:
        _stop_http_provider(server, thread)
        provider.close()


def test_completion_max_tokens_one_commits_utf8_safe_partial(tmp_path: Path) -> None:
    provider = _start(tmp_path)
    try:
        response = provider.complete(
            _completion("hello", user="partial", max_tokens=1)
        )
        assert response["choices"] == [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "c"},
                "finish_reason": "length",
            }
        ]
        assert response["usage"]["completion_tokens"] == 1
        cassi = response["cassi"]
        assert cassi["stop_reason"] == "max_output_symbols"
        assert cassi["reply_kind"] == "field"
        assert cassi["trained_tape_preserved"] is True
        assert cassi["field_text_receipt"]["output_symbols"] == [ord("c")]
        assert "displacement_receipt" not in cassi
        assert "corpus_memory_sha256" not in cassi
        assert Path(cassi["checkpoint"]).is_file()
        assert len(cassi["checkpoint_sha256"]) == 64

        assert provider.store is not None
        loaded = provider.store.load("partial")
        assert loaded is not None
        _, metadata, _, checkpoint_sha256 = loaded
        assert checkpoint_sha256 == cassi["checkpoint_sha256"]
        assert set(metadata) == {
            CONTEXT_STREAM_METADATA_KEY,
            LAST_COMPLETION_METADATA_KEY,
        }
        assert metadata[CONTEXT_STREAM_METADATA_KEY] == {}
    finally:
        provider.close()


def test_restart_continues_successor_and_failure_retains_checkpoint(
    tmp_path: Path,
) -> None:
    config = _provider_config(tmp_path)
    first_provider = PersistentFieldProvider(config)
    first_provider.start()
    first = first_provider.complete(_completion("hello", user="restart"))
    checkpoint = Path(first["cassi"]["checkpoint"])
    first_provider.close()

    second_provider = PersistentFieldProvider(config)
    second_provider.start()
    try:
        second = second_provider.complete(_completion("status", user="restart"))
        assert second["choices"][0]["message"]["content"] == "ready"
        assert (
            second["cassi"]["state_in_sha256"]
            == first["cassi"]["state_out_sha256"]
        )
        committed = checkpoint.read_bytes()
        with pytest.raises(
            ProviderError, match="prior checkpoint retained"
        ):
            second_provider.complete(_completion("unlearned", user="restart"))
        assert checkpoint.read_bytes() == committed
    finally:
        second_provider.close()


def test_context_store_condenses_recall_and_restart_preserve_one_shared_field(
    tmp_path: Path,
) -> None:
    config = _provider_config(tmp_path)
    provider = PersistentFieldProvider(config)
    provider.start()
    user = "cassicore-context"
    stream = "mnemic-store"
    text = "golden lattice memory binds the quiet river"
    revision = _revision("record-a", text)
    address = _field_address("record-a", text, revision)
    request = {
        "user": user,
        "context_session_id": "context-a",
        "query": text,
        "addresses": [address],
    }
    try:
        assert provider.recall_context(request)["address"] is None
        stored = _event(
            user=user,
            stream_id=stream,
            sequence=1,
            previous_event_id=EMPTY_CONTEXT_EVENT_ID,
            payload=_memory_payload("store", "record-a", text, revision),
        )
        receipt = provider.observe_context(stored)
        assert receipt["condensed"] is True
        assert receipt["transitions"][0]["operation"] == "condense"
        checkpoint = Path(receipt["checkpoint"])
        committed = checkpoint.read_bytes()

        recalled = provider.recall_context(request)
        assert recalled["address"] == address
        assert recalled["signal"] > 0.0
        assert recalled["availability"] > 0.0
        assert checkpoint.read_bytes() == committed

        duplicate = provider.observe_context(stored)
        assert duplicate["duplicate"] is True
        assert checkpoint.read_bytes() == committed
    finally:
        provider.close()

    restarted = PersistentFieldProvider(config)
    restarted.start()
    try:
        checkpoint = restarted.store.path_for(user) if restarted.store else None
        assert checkpoint is not None
        before_recall = checkpoint.read_bytes()
        assert restarted.recall_context(request)["address"] == address
        assert checkpoint.read_bytes() == before_recall
        assert restarted.store is not None
        loaded = restarted.store.load(user)
        assert loaded is not None
        shared = loaded[0]
        mnemic = restarted.store.layout.mnemic(shared)
        assert mnemic.field.untyped_storage().data_ptr() == (
            shared.field.untyped_storage().data_ptr()
        )
    finally:
        restarted.close()


def test_context_feedback_condenses_query_to_exact_manifest_address(
    tmp_path: Path,
) -> None:
    provider = _start(tmp_path)
    user = "cassicore-context"
    stream = "mnemic-feedback"
    text = "alpha retained memory"
    revision = _revision("record-a", text)
    address = _field_address("record-a", text, revision)
    query = "saffron portal"
    recall_request = {
        "user": user,
        "context_session_id": "context",
        "query": query,
        "addresses": [address],
    }
    try:
        stored = _event(
            user=user,
            stream_id=stream,
            sequence=1,
            previous_event_id=EMPTY_CONTEXT_EVENT_ID,
            payload=_memory_payload("store", "record-a", text, revision),
        )
        provider.observe_context(stored)
        assert provider.recall_context(recall_request)["address"] is None

        feedback = _event(
            user=user,
            stream_id=stream,
            sequence=2,
            previous_event_id=stored["event_id"],
            payload=_feedback_payload(
                query,
                [_candidate("record-a", text, revision)],
            ),
        )
        learned = provider.observe_context(feedback)
        assert learned["condensed"] is True
        assert learned["selected_ids"] == ["record-a"]
        recalled = provider.recall_context(recall_request)
        assert recalled["address"] == address
        assert recalled["selection_margin"] > 0.0
    finally:
        provider.close()


def test_context_update_and_delete_inhibit_obsolete_field_cues(
    tmp_path: Path,
) -> None:
    provider = _start(tmp_path)
    user = "cassicore-context"
    stream = "mnemic-update-delete"
    old_text = "old violet river memory"
    new_text = "new copper mountain memory"
    old_revision = _revision("record", old_text)
    new_revision = _revision("record", new_text)
    old_address = _field_address("record", old_text, old_revision)
    new_address = _field_address("record", new_text, new_revision)
    try:
        stored = _event(
            user=user,
            stream_id=stream,
            sequence=1,
            previous_event_id=EMPTY_CONTEXT_EVENT_ID,
            payload=_memory_payload(
                "store", "record", old_text, old_revision
            ),
        )
        provider.observe_context(stored)
        update_payload = _memory_payload(
            "update", "record", new_text, new_revision
        )
        update_payload["previous_record"] = _memory_payload(
            "store", "record", old_text, old_revision
        )["record"]
        updated = _event(
            user=user,
            stream_id=stream,
            sequence=2,
            previous_event_id=stored["event_id"],
            payload=update_payload,
        )
        update_receipt = provider.observe_context(updated)
        assert [item["operation"] for item in update_receipt["transitions"]] == [
            "inhibit",
            "condense",
        ]
        assert provider.recall_context(
            {
                "user": user,
                "context_session_id": "context",
                "query": new_text,
                "addresses": [new_address],
            }
        )["address"] == new_address
        assert provider.recall_context(
            {
                "user": user,
                "context_session_id": "context",
                "query": old_text,
                "addresses": [old_address],
            }
        )["address"] is None

        deleted = _event(
            user=user,
            stream_id=stream,
            sequence=3,
            previous_event_id=updated["event_id"],
            payload=_memory_payload(
                "delete", "record", new_text, new_revision
            ),
        )
        delete_receipt = provider.observe_context(deleted)
        assert delete_receipt["condensed"] is False
        assert delete_receipt["transitions"] == [
            {"operation": "inhibit", "address": new_address}
        ]
        assert provider.recall_context(
            {
                "user": user,
                "context_session_id": "context",
                "query": new_text,
                "addresses": [new_address],
            }
        )["address"] is None
    finally:
        provider.close()


def test_context_delete_inhibits_only_the_address_being_deleted(
    tmp_path: Path,
) -> None:
    provider = _start(tmp_path)
    user = "cassicore-address-specific-delete"
    stream = "mnemic-address-specific-delete"
    first_text = "shared cobalt crossing alpha memory"
    second_text = "shared cobalt crossing beta memory"
    first_revision = _revision("record-a", first_text)
    second_revision = _revision("record-b", second_text)
    first_address = _field_address("record-a", first_text, first_revision)
    second_address = _field_address("record-b", second_text, second_revision)
    try:
        first = _event(
            user=user,
            stream_id=stream,
            sequence=1,
            previous_event_id=EMPTY_CONTEXT_EVENT_ID,
            payload=_memory_payload(
                "store", "record-a", first_text, first_revision
            ),
        )
        provider.observe_context(first)
        second = _event(
            user=user,
            stream_id=stream,
            sequence=2,
            previous_event_id=first["event_id"],
            payload=_memory_payload(
                "store", "record-b", second_text, second_revision
            ),
        )
        provider.observe_context(second)
        assert provider.recall_context(
            {
                "user": user,
                "context_session_id": "context",
                "query": second_text,
                "addresses": [first_address, second_address],
            }
        )["address"] == second_address
        for context_session_id in ("context-a", "context-b"):
            manifest_bound = provider.recall_context(
                {
                    "user": user,
                    "context_session_id": context_session_id,
                    "query": second_text,
                    "addresses": [first_address],
                }
            )
            assert manifest_bound["address"] in {None, first_address}
            assert manifest_bound["address"] != second_address

        deleted = _event(
            user=user,
            stream_id=stream,
            sequence=3,
            previous_event_id=second["event_id"],
            payload=_memory_payload(
                "delete", "record-a", first_text, first_revision
            ),
        )
        provider.observe_context(deleted)
        assert provider.recall_context(
            {
                "user": user,
                "context_session_id": "context",
                "query": first_text,
                "addresses": [first_address],
            }
        )["address"] is None
        assert provider.recall_context(
            {
                "user": user,
                "context_session_id": "context",
                "query": first_text,
                "addresses": [first_address, second_address],
            }
        )["address"] != first_address
        assert provider.recall_context(
            {
                "user": user,
                "context_session_id": "context",
                "query": second_text,
                "addresses": [first_address, second_address],
            }
        )["address"] == second_address
    finally:
        provider.close()


def test_context_recall_rejects_malformed_addresses_without_mutation(
    tmp_path: Path,
) -> None:
    provider = _start(tmp_path)
    user = "cassicore-context"
    text = "address validation memory"
    revision = _revision("record", text)
    stored = _event(
        user=user,
        stream_id="mnemic-address-validation",
        sequence=1,
        previous_event_id=EMPTY_CONTEXT_EVENT_ID,
        payload=_memory_payload("store", "record", text, revision),
    )
    try:
        receipt = provider.observe_context(stored)
        checkpoint = Path(receipt["checkpoint"])
        committed = checkpoint.read_bytes()
        with pytest.raises(ProviderError, match="field address 0"):
            provider.recall_context(
                {
                    "user": user,
                    "context_session_id": "context",
                    "query": text,
                    "addresses": ["not-an-address"],
                }
            )
        assert checkpoint.read_bytes() == committed
    finally:
        provider.close()











def test_empty_memory_record_advances_stream_and_updates_to_content(
    tmp_path: Path,
) -> None:
    provider = _start(tmp_path)
    user = "empty-memory"
    stream_id = "empty-stream"
    empty_revision = _revision("record", "")
    filled_revision = _revision("record", "filled")
    try:
        stored = provider.observe_context(
            _event(
                user=user,
                stream_id=stream_id,
                sequence=1,
                previous_event_id=EMPTY_CONTEXT_EVENT_ID,
                payload=_memory_payload("store", "record", "", empty_revision),
            )
        )
        assert stored["stream"]["sequence"] == 1
        assert stored["condensed"] is False

        update_payload = _memory_payload(
            "update", "record", "filled", filled_revision
        )
        update_payload["previous_record"] = {
            "id": "record",
            "content": "",
            "node_type": "fact",
            "revision": empty_revision,
        }
        updated = provider.observe_context(
            _event(
                user=user,
                stream_id=stream_id,
                sequence=2,
                previous_event_id=stored["stream"]["event_id"],
                payload=update_payload,
            )
        )
        assert updated["stream"]["sequence"] == 2
        assert updated["condensed"] is True
    finally:
        provider.close()

def test_context_accepts_exact_text_free_action_start_and_outcome(
    tmp_path: Path,
) -> None:
    provider = _start(tmp_path)
    user = "exact-actions"
    stream_id = "action-stream"
    record_id = "action:record"
    pending_revision = _revision(record_id, "")
    completed_revision = _revision(record_id, "completed")
    action = {
        "episode_id": "call-1",
        "action_id": "tool:signature",
        "kind": "tool:read",
        "stage": "start",
        "required_authority": 1,
        "reversible": False,
        "authorization_path": ["thalamus:plan:plan-1", "omp:tool-call:call-1"],
    }
    try:
        start_payload = _memory_payload(
            "store", record_id, "", pending_revision
        )
        start_payload["record"]["node_type"] = "action"
        start_payload["record"].pop("field_address")
        start_payload["action"] = action
        started = provider.observe_context(
            _event(
                user=user,
                stream_id=stream_id,
                sequence=1,
                previous_event_id=EMPTY_CONTEXT_EVENT_ID,
                payload=start_payload,
            )
        )
        assert started["stream"]["sequence"] == 1

        outcome_payload = _memory_payload(
            "update", record_id, "completed", completed_revision
        )
        outcome_payload["record"]["node_type"] = "action"
        outcome_payload["record"].pop("field_address")
        outcome_payload["previous_record"] = {
            "id": record_id,
            "content": "",
            "node_type": "action",
            "revision": pending_revision,
        }
        outcome_payload["action"] = {
            **action,
            "stage": "outcome",
            "outcome": "completed",
            "effects": [
                {
                    "record_id": "memory-effect",
                    "before_revision": pending_revision,
                    "after_revision": completed_revision,
                    "semantic_kind": "mnemic:update",
                    "start_byte": 0,
                    "end_byte": len("completed".encode("utf-8")),
                }
            ],
        }
        completed = provider.observe_context(
            _event(
                user=user,
                stream_id=stream_id,
                sequence=2,
                previous_event_id=started["stream"]["event_id"],
                payload=outcome_payload,
            )
        )
        assert completed["stream"]["sequence"] == 2

        invalid = dict(start_payload)
        invalid["action"] = outcome_payload["action"]
        with pytest.raises(ProviderError, match="action outcomes"):
            provider.observe_context(
                _event(
                    user=user,
                    stream_id=stream_id,
                    sequence=3,
                    previous_event_id=completed["stream"]["event_id"],
                    payload=invalid,
                )
            )
    finally:
        provider.close()


def test_context_rejects_previous_record_outside_same_record_update(
    tmp_path: Path,
) -> None:
    provider = _start(tmp_path)
    try:
        assert provider.store is not None
        for operation, previous_id in (("store", "record"), ("update", "other")):
            payload = _memory_payload(
                operation, "record", "new value", _revision("record", "new value")
            )
            payload["previous_record"] = {
                "id": previous_id,
                "content": "old value",
                "node_type": "fact",
                "revision": _revision(previous_id, "old value"),
            }
            with pytest.raises(ProviderError, match="previous_record"):
                provider.observe_context(
                    _event(
                        user="invalid-previous-record",
                        stream_id="invalid",
                        sequence=1,
                        previous_event_id=EMPTY_CONTEXT_EVENT_ID,
                        payload=payload,
                    )
                )
        assert provider.store.load("invalid-previous-record") is None
    finally:
        provider.close()




@pytest.mark.parametrize(
    "metadata",
    (
        {
            "context_journal_v1": [{}],
            CONTEXT_STREAM_METADATA_KEY: {},
        },
        {
            CONTEXT_STREAM_METADATA_KEY: {
                "stream": {
                    "sequence": 0,
                    "event_id": EMPTY_CONTEXT_EVENT_ID,
                }
            },
        },
        {
            CONTEXT_STREAM_METADATA_KEY: {},
            LAST_COMPLETION_METADATA_KEY: {"schema": "wrong"},
        },
    ),
)
def test_session_metadata_rejects_malformed_bounded_records(
    tmp_path: Path, metadata: dict[str, Any]
) -> None:
    provider = _start(tmp_path)
    try:
        assert provider.store is not None
        assert provider.initial_state is not None
        with pytest.raises(ProviderError, match="stored|metadata"):
            provider.store.save(
                "malformed",
                provider.store.initial(provider.initial_state),
                metadata,
            )
        assert not provider.store.path_for("malformed").exists()
    finally:
        provider.close()


def test_incompatible_checkpoint_status_and_guarded_reset(tmp_path: Path) -> None:
    provider = _start(tmp_path)
    user = "cassicore-context"
    stream = "reset-stream"
    assert provider.store is not None
    path = provider.store.path_for(user)
    assert provider.initial_state is not None
    actual_fingerprint = provider.store.provider_fingerprint
    provider.store.provider_fingerprint = "0" * 64
    provider.store.save(
        user,
        provider.store.initial(provider.initial_state),
        {},
    )
    provider.store.provider_fingerprint = actual_fingerprint

    try:
        status = provider.context_status({"user": user, "stream_id": stream})
        assert status["checkpoint"]["status"] == "incompatible"
        assert status["checkpoint"]["engine_fingerprint"] == "0" * 64
        reset = provider.reset_context(
            {
                "user": user,
                "stream_id": stream,
                "checkpoint_sha256": status["checkpoint"]["sha256"],
                "checkpoint_engine_fingerprint": status["checkpoint"][
                    "engine_fingerprint"
                ],
            }
        )
        assert reset["checkpoint"]["status"] == "missing"
        assert Path(reset["checkpoint"]["archived"]).is_file()
        assert not path.exists()

        replay = _event(
            user=user,
            stream_id=stream,
            sequence=1,
            previous_event_id=EMPTY_CONTEXT_EVENT_ID,
            payload=_memory_payload(
                "store", "replayed", "replayed memory", _revision("replayed", "replayed memory")
            ),
        )
        provider.observe_context(replay)
        compatible = provider.context_status(
            {"user": user, "stream_id": stream}
        )
        assert compatible["checkpoint"]["status"] == "compatible"
        assert compatible["stream"]["event_id"] == replay["event_id"]
    finally:
        provider.close()


def test_counterflow_observed_commit_is_persistent_idempotent_and_plan_is_frozen(
    tmp_path: Path,
) -> None:
    provider = _start(tmp_path)
    server, thread = _start_http_provider(provider)
    try:
        assert provider.controller is not None
        assert provider.initial_state is not None
        assert provider.store is not None
        primary_sha256 = provider.controller.state_sha256(provider.initial_state)
        assert not provider.store.path_for("counterflow").exists()

        def exact_identity(
            record_id: str,
            revision: str,
            start: int,
            end: int,
        ) -> dict[str, Any]:
            semantic_kind = "field-transition"
            encoded = json.dumps(
                [
                    "cassicore.mnemic.counterflow-address.v1",
                    record_id,
                    revision,
                    start,
                    end,
                    semantic_kind,
                ],
                separators=(",", ":"),
            ).encode()
            return {
                "record_id": record_id,
                "address": hashlib.sha256(encoded).digest()[:16].hex(),
                "revision": revision,
                "start_byte": start,
                "end_byte": end,
                "semantic_kind": semantic_kind,
            }

        before = exact_identity("before-record", "01" * 32, 0, 4)
        after = exact_identity("after-record", "02" * 32, 4, 8)
        observation = {
            "id": "ab" * 32,
            "before": before,
            "after": after,
            "symbol": "advance",
            "outcome": "completed",
            "action": {
                "id": "advance-field",
                "kind": "field-transition",
                "required_authority": 1.0,
                "reversible": True,
            },
        }
        plan_request = {
            "user": "counterflow",
            "session_id": "transport-only",
            "mode": "plan",
            "observations": [observation],
            "trajectory": [
                {
                    **identity,
                    "mask": [1.0, 1.0, 1.0, 1.0],
                    "authority": 1.0,
                    "required": True,
                }
                for identity in (before, after)
            ],
            "policy": {
                "eligible_observation_ids": [observation["id"]],
                "permitted_action_kinds": ["field-transition"],
                "authority": 1.0,
                "authorization_path": ["thalamus:reasoning"],
            },
        }
        commit_request = {
            "user": "counterflow",
            "session_id": "transport-only",
            "observation": observation,
            "acknowledgment": {
                "stream_id": "counterflow-stream",
                "sequence": 5,
                "event_id": observation["id"],
                "status": "completed",
                "before_revision": before["revision"],
                "after_revision": after["revision"],
                "authorization_path": ["world:execution-ack"],
            },
        }
        mismatched_identity = {
            **commit_request,
            "acknowledgment": {
                **commit_request["acknowledgment"],
                "event_id": "cd" * 32,
            },
        }
        with pytest.raises(ProviderError, match="event identity"):
            provider.commit_counterflow(mismatched_identity)
        assert not provider.store.path_for("counterflow").exists()


        committed = _post_provider(server, "/v1/counterflow/commit", commit_request)
        assert committed["consolidated"] is True
        assert committed["state_sha256"] == primary_sha256
        assert (
            committed["counterflow_state_out_sha256"]
            != committed["counterflow_state_in_sha256"]
        )
        checkpoint = Path(committed["checkpoint"])
        committed_bytes = checkpoint.read_bytes()
        loaded = provider.store.load("counterflow")
        assert loaded is not None
        shared = loaded[0]
        provider.store.layout.validate(shared)
        phi = provider.store.layout.phi(shared)
        counterflow = provider.store.layout.counterflow(shared)
        mnemic = provider.store.layout.mnemic(shared)
        assert (
            shared.field.untyped_storage().data_ptr()
            == phi.field.untyped_storage().data_ptr()
            == counterflow.field.untyped_storage().data_ptr()
            == mnemic.field.untyped_storage().data_ptr()
        )
        assert provider.controller.state_sha256(phi) == primary_sha256
        assert (
            provider.counterflow_runtime is not None
            and provider.counterflow_runtime.state_sha256(counterflow)
            == committed["counterflow_state_out_sha256"]
        )
        header, field_payload, _ = provider.store._decode_frame(committed_bytes)
        assert header["schema"] == "cassi.shared-field-provider-session.v4"
        assert header["field_bytes"] == len(field_payload)
        assert "phi_payload_sha256" not in header
        assert "counterflow_payload_sha256" not in header
        assert header["mnemic_state_sha256"] == (
            provider.mnemic_controller.state_sha256(mnemic)
            if provider.mnemic_controller is not None
            else None
        )
        duplicate = _post_provider(server, "/v1/counterflow/commit", commit_request)
        assert duplicate["status"] == "duplicate"
        assert duplicate["consolidated"] is False
        assert checkpoint.read_bytes() == committed_bytes
        stale_observation = {**observation, "id": "cd" * 32}
        stale_commit = {
            **commit_request,
            "observation": stale_observation,
            "acknowledgment": {
                **commit_request["acknowledgment"],
                "sequence": 4,
                "event_id": stale_observation["id"],
            },
        }
        with pytest.raises(ProviderError, match="stale or conflicting"):
            provider.commit_counterflow(stale_commit)

        response = _post_provider(server, "/v1/counterflow/plan", plan_request)
        assert response["session_id"] == "counterflow"
        assert response["state_sha256"] == primary_sha256
        assert response["status"] == "settled"
        assert response["persistent_state"] is False
        assert response["inference_memory_frozen"] is True
        assert response["symbolic"]["symbols"] == ["advance"]
        assert response["action_proposal"]["action_ids"] == ["advance-field"]
        assert response["action_proposal"]["inert"] is True
        assert checkpoint.read_bytes() == committed_bytes
        assert provider.controller.state_sha256(provider.initial_state) == primary_sha256
        counterflow_sha256 = response["counterflow_state_sha256"]
    finally:
        _stop_http_provider(server, thread)
        provider.close()

    restarted = _start(tmp_path)
    restarted_server, restarted_thread = _start_http_provider(restarted)
    try:
        replayed_commit = _post_provider(
            restarted_server,
            "/v1/counterflow/commit",
            commit_request,
        )
        assert replayed_commit["status"] == "duplicate"
        assert replayed_commit["counterflow_state_out_sha256"] == counterflow_sha256
        replay = _post_provider(
            restarted_server,
            "/v1/counterflow/plan",
            plan_request,
        )
        assert replay["status"] == "settled"
        assert replay["counterflow_state_sha256"] == counterflow_sha256
        assert replay["action_proposal"]["action_ids"] == ["advance-field"]
    finally:
        _stop_http_provider(restarted_server, restarted_thread)
        restarted.close()
