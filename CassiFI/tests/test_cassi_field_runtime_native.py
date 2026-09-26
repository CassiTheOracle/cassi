from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from typing import Any
import hashlib
import struct
from pathlib import Path
import sys
import threading

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))

import pytest
import cassi_field_runtime_native as native  # type: ignore[reportMissingImports]


@pytest.mark.skipif(sys.platform != "win32", reason="native field-runtime transport is Windows-only")
def test_native_runtime_serializes_shared_pipe_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    responses: deque[tuple[bytes, bytes]] = deque()
    active: dict[int, tuple[bytes, bytes]] = {}
    transport_lock = threading.Lock()
    first_written = threading.Event()
    second_response_assigned = threading.Event()

    def connect(_client: native.NativeFieldRuntimeClient, _timeout: float) -> object:
        return object()

    def write_all(_client: native.NativeFieldRuntimeClient, packet: bytes) -> None:
        _, version, kind, _, _, request_id, _ = native.FRAME_HEADER.unpack_from(packet)
        if kind == native.HELLO:
            body = native._body((native._utf8(1, "authenticated"), native._u64(2, 1)))
        else:
            body = b""
        header = native.FRAME_HEADER.pack(
            native.FRAME_MAGIC,
            version,
            kind | native.RESPONSE_BIT,
            0,
            len(body),
            request_id,
            hashlib.sha256(body).digest(),
        )
        with transport_lock:
            responses.append((header, body))
        if threading.current_thread().name == "first":
            first_written.set()
            second_response_assigned.wait(timeout=1)

    def read_exact(_client: native.NativeFieldRuntimeClient, size: int) -> bytes:
        thread_id = threading.get_ident()
        if size == native.FRAME_HEADER.size:
            with transport_lock:
                response = responses.popleft()
                active[thread_id] = response
                if threading.current_thread().name == "second":
                    second_response_assigned.set()
            return response[0]
        with transport_lock:
            response = active.pop(thread_id)
        if size != len(response[1]):
            raise AssertionError("native response body length changed")
        return response[1]

    monkeypatch.setattr(native.NativeFieldRuntimeClient, "_connect", connect)
    monkeypatch.setattr(native.NativeFieldRuntimeClient, "_write_all", write_all)
    monkeypatch.setattr(native.NativeFieldRuntimeClient, "_read_exact", read_exact)
    client = native.NativeFieldRuntimeClient("runtime-test", "nonce-test")
    assert client.service_generation == 1

    results: list[dict[int, tuple[int, bytes]]] = []
    failures: list[Exception] = []

    def request_status() -> None:
        try:
            results.append(client._request(native.STATUS, ()))
        except Exception as exc:
            failures.append(exc)

    first = threading.Thread(target=request_status, name="first")
    second = threading.Thread(target=request_status, name="second")
    first.start()
    assert first_written.wait(timeout=1)
    second.start()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert failures == []
    assert results == [{}, {}]


def test_native_chunked_export_rejects_candidate_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native, "MAX_FIELD_BYTES", 8)
    client = object.__new__(native.NativeFieldRuntimeClient)
    expected_digest = hashlib.sha256(b"candidate snapshot").digest()
    requests: list[int] = []

    def request(
        kind: int, fields: tuple[tuple[int, int, bytes], ...]
    ) -> dict[int, tuple[int, bytes]]:
        requests.append(kind)
        if kind == native.EXPORT_CANDIDATE_INFO:
            return {
                1: (native.WIRE_UTF8, b"candidate-export-info"),
                2: (native.WIRE_UTF8, b"candidate-1"),
                3: (native.WIRE_U64, (16).to_bytes(8, "little")),
                4: (native.WIRE_BYTES, expected_digest),
                5: (native.WIRE_UTF8, b"predecessor"),
                6: (native.WIRE_U64, (3).to_bytes(8, "little")),
                7: (native.WIRE_U64, (8).to_bytes(8, "little")),
            }
        assert kind == native.EXPORT_CANDIDATE_CHUNK
        request_fields = {
            tag: (wire, value) for tag, wire, value in fields
        }
        assert native._field_u64(request_fields, 4) == 3
        assert native._field_bytes(request_fields, 5) == expected_digest
        return {
            1: (native.WIRE_UTF8, b"candidate-export-chunk"),
            5: (native.WIRE_U64, (4).to_bytes(8, "little")),
            6: (native.WIRE_BYTES, expected_digest),
        }

    monkeypatch.setattr(client, "_request", request, raising=False)
    with pytest.raises(native.NativeFieldRuntimeError, match="changed during"):
        client.export_candidate("candidate-1", (2,))
    assert requests == [native.EXPORT_CANDIDATE_INFO, native.EXPORT_CANDIDATE_CHUNK]


def test_native_chunked_export_rejects_wrong_complete_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(native, "MAX_FIELD_BYTES", 8)
    client = object.__new__(native.NativeFieldRuntimeClient)
    payload = struct.pack("<dd", 1.0, 2.0)
    expected_digest = hashlib.sha256(b"different candidate bytes").digest()
    staged: dict[int, bytes] = {}

    class Mapping:
        def __init__(self, handle: int) -> None:
            self.handle = handle

        def __enter__(self) -> Mapping:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self, size: int) -> bytes:
            chunk = staged[self.handle]
            assert len(chunk) == size
            return chunk

    def request(
        kind: int, fields: tuple[tuple[int, int, bytes], ...]
    ) -> dict[int, tuple[int, bytes]]:
        if kind == native.EXPORT_CANDIDATE_INFO:
            return {
                1: (native.WIRE_UTF8, b"candidate-export-info"),
                2: (native.WIRE_UTF8, b"candidate-1"),
                3: (native.WIRE_U64, (16).to_bytes(8, "little")),
                4: (native.WIRE_BYTES, expected_digest),
                5: (native.WIRE_UTF8, b"predecessor"),
                6: (native.WIRE_U64, (3).to_bytes(8, "little")),
                7: (native.WIRE_U64, (8).to_bytes(8, "little")),
            }
        assert kind == native.EXPORT_CANDIDATE_CHUNK
        request_fields = {tag: (wire, value) for tag, wire, value in fields}
        offset = native._field_u64(request_fields, 2)
        chunk = payload[offset : offset + native._field_u64(request_fields, 3)]
        handle = offset + 1
        staged[handle] = chunk
        return {
            1: (native.WIRE_UTF8, b"candidate-export-chunk"),
            2: (native.WIRE_U64, handle.to_bytes(8, "little")),
            3: (native.WIRE_U64, len(chunk).to_bytes(8, "little")),
            4: (native.WIRE_BYTES, hashlib.sha256(chunk).digest()),
            5: (native.WIRE_U64, (3).to_bytes(8, "little")),
            6: (native.WIRE_BYTES, expected_digest),
        }

    monkeypatch.setattr(client, "_request", request, raising=False)
    monkeypatch.setattr(native, "_StagingMapping", Mapping)
    with pytest.raises(native.NativeFieldRuntimeError, match="candidate digest mismatch"):
        client.export_candidate("candidate-1", (2,))


def _graph_site_receipt_payload(
    *,
    admitted: bool,
    expected_route: Sequence[int],
    actual_route: Sequence[int],
    refusal: str,
    trace_entries: Sequence[str],
    successor_state_json: str,
) -> bytes:
    """Encode a native graph-site receipt in the field order of protocol.hpp."""
    sampler = {"mode": "greedy", "temperature": 1.0, "top_k": 0, "draw": 0.0}
    _, sampler_sha256 = native._normalized_graph_site_sampler(sampler)

    def digest(label: str) -> str:
        return hashlib.sha256(label.encode("utf-8")).hexdigest()

    def text(value: str) -> bytes:
        encoded = value.encode("utf-8")
        return struct.pack("<I", len(encoded)) + encoded

    def i32_vector(values: Sequence[int]) -> bytes:
        return struct.pack("<I", len(values)) + b"".join(
            struct.pack("<i", value) for value in values
        )

    accepted = 42 if admitted else -1
    token_count = 9 if admitted else 0
    payload = bytearray()
    payload += struct.pack("<I", native.GRAPH_SITE_RECEIPT_WIRE_VERSION)
    payload += text("ticket-1") + text("candidate-1")
    payload += text(digest("ticket")) + text(digest("preflight")) + text(digest("native-preflight"))
    payload += text(digest("source")) + text(digest("model")) + text(digest("tokenizer"))
    payload += text("task-1") + text("sequence-1") + text("operation-1")
    payload += struct.pack("<iii", 0, 7, accepted)
    payload += struct.pack("<Q", 8) + text(digest("input-tokens"))
    payload += text(digest("replay") if admitted else "")
    payload += struct.pack("<Q", token_count)
    payload += text("ffn") + struct.pack("<i", 3) + text("layer3.ffn") + text("qwen3.5-moe")
    payload += text(digest("invocation")) + text(digest("request")) + text(digest("candidate"))
    payload += text('{"guard":true}') + text("expert-affine") + struct.pack("<Q", 0) + text("")
    payload += text(digest("graph-predecessor")) + text(digest("owner-snapshot"))
    payload += text(digest("owner-epoch")) + text(digest("native-epoch")) + text(digest("native-predecessor"))
    payload += text(sampler_sha256) + text(sampler["mode"])
    payload += struct.pack("<d", sampler["temperature"]) + struct.pack("<I", sampler["top_k"])
    payload += struct.pack("<d", sampler["draw"])
    payload += text(digest("input")) + text(digest("output"))
    payload += i32_vector(expected_route) + i32_vector(actual_route)
    payload += struct.pack("<I", len(trace_entries))
    payload += b"".join(text(entry) for entry in trace_entries)
    payload += text(
        native._canonical_json_sha256(list(trace_entries), "trace") if trace_entries else ""
    )
    payload += text(digest("candidate-successor") if admitted else "")
    payload += text(digest("native-successor") if admitted else "")
    payload += text(successor_state_json) + text(refusal)
    payload += bytes((1, 1 if admitted else 0))
    payload += struct.pack("<Q", 0) + struct.pack("<Q", 2) + struct.pack("<Q", 4)
    payload += struct.pack("<Q", 1024) + struct.pack("<Q", 2048)
    payload += struct.pack("<d", 1234.5 if admitted else 0.0)
    return bytes(payload)


def test_graph_site_receipt_decodes_expected_and_actual_expert_routes() -> None:
    receipt = native._decode_graph_site_receipt(
        _graph_site_receipt_payload(
            admitted=True,
            expected_route=[1, 2, 3, 4],
            actual_route=[1, 2, 3, 4],
            refusal="",
            trace_entries=["embed", "attn", "ffn"],
            successor_state_json='{"layer":3}',
        )
    )
    assert receipt["schema"] == "cassifi.native-graph-site-receipt.v1"
    assert receipt["version"] == native.GRAPH_SITE_RECEIPT_WIRE_VERSION
    assert receipt["attempted"] is True and receipt["admitted"] is True
    assert receipt["expected_expert_ids"] == [1, 2, 3, 4]
    assert receipt["actual_expert_ids"] == [1, 2, 3, 4]
    assert receipt["selected_token_id"] == 42 and receipt["token_count"] == 9
    assert receipt["stage_trace"] == ["embed", "attn", "ffn"]
    assert receipt["sampler"] == {"mode": "greedy", "temperature": 1.0, "top_k": 0, "draw": 0.0}


def test_graph_site_receipt_decodes_refusal_without_routes() -> None:
    receipt = native._decode_graph_site_receipt(
        _graph_site_receipt_payload(
            admitted=False,
            expected_route=[],
            actual_route=[],
            refusal="expert_route_mismatch",
            trace_entries=[],
            successor_state_json="",
        )
    )
    assert receipt["schema"] == "cassifi.native-graph-site-receipt.v1"
    assert receipt["attempted"] is True and receipt["admitted"] is False
    assert receipt["refusal"] == "expert_route_mismatch"
    assert receipt["selected_token_id"] == -1 and receipt["token_count"] == 0
    assert receipt["expected_expert_ids"] == [] and receipt["actual_expert_ids"] == []
    assert receipt["successor_state_json"] == ""


@pytest.mark.skipif(sys.platform != "win32", reason="native field-runtime transport is Windows-only")
def test_native_wire_round_trip_records_a_measured_trace_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cassi_work_trace import trace_work

    state: dict[str, Any] = {}

    def connect(_client: native.NativeFieldRuntimeClient, _timeout: float) -> object:
        return object()

    def write_all(_client: native.NativeFieldRuntimeClient, packet: bytes) -> None:
        _, version, kind, _, _, request_id, _ = native.FRAME_HEADER.unpack_from(packet)
        body = (
            native._body((native._utf8(1, "authenticated"), native._u64(2, 1)))
            if kind == native.HELLO
            else b""
        )
        state["written"] = len(packet)
        state["response"] = (
            native.FRAME_HEADER.pack(
                native.FRAME_MAGIC,
                version,
                kind | native.RESPONSE_BIT,
                0,
                len(body),
                request_id,
                hashlib.sha256(body).digest(),
            ),
            body,
        )

    def read_exact(_client: native.NativeFieldRuntimeClient, size: int) -> bytes:
        header, body = state["response"]
        return header if size == native.FRAME_HEADER.size else body

    monkeypatch.setattr(native.NativeFieldRuntimeClient, "_connect", connect)
    monkeypatch.setattr(native.NativeFieldRuntimeClient, "_write_all", write_all)
    monkeypatch.setattr(native.NativeFieldRuntimeClient, "_read_exact", read_exact)

    with trace_work() as trace:
        client = native.NativeFieldRuntimeClient("runtime-trace", "nonce-trace")
        client._request(native.STATUS, ())
        status_written = state["written"]

    rows = [row for row in trace.rows() if row["kind"] == "native"]
    assert [row["name"] for row in rows] == ["kind-1", "status"]
    status_row = rows[-1]
    assert status_row["meta"] == {"kind": native.STATUS}
    assert status_row["items"] == 1
    assert status_row["bytes"] == status_written + native.FRAME_HEADER.size
    assert status_row["wait_ns"] == status_row["duration_ns"]
    assert status_row["duration_ns"] >= 0


@pytest.mark.parametrize(
    "sampler",
    [
        {"mode": "categorical", "temperature": 0.8, "top_k": 40},
        {"mode": "greedy", "temperature": 0.7, "top_k": 5},
    ],
)
def test_native_token_request_records_the_sampler_the_c_api_executes(
    sampler: dict[str, Any],
) -> None:
    # Owner replay compares each retained request sampler byte-for-byte with
    # the sampler the native step echoes, so every run position must record
    # the executed form (canonical greedy, float32 categorical temperature).
    import programs.model.runtime as model_runtime  # type: ignore[reportMissingImports]
    from programs.model.records import build_model_package  # type: ignore[reportMissingImports]

    package = build_model_package(
        program_id="sampler-record",
        architecture="qwen35",
        graph=[
            {
                "operation_id": "native",
                "stage": "model",
                "op": "native-transformer",
                "inputs": [],
                "output": None,
                "parameters": {"source_id": "model", "source_sha256": "a" * 64},
                "state_effects": ["native-model-continuation"],
            }
        ],
        tensors={},
        tokenizer={"vocab_size": 32},
        primitive_contracts=("immutable-gguf-v1", "model-continuation-v1"),
    )
    state = model_runtime.initial_state(
        package,
        prompt_tokens=[1, 2, 3],
        owner_id="owner",
        member_id="member",
        lineage_id="lineage",
        operation_id="operation",
        max_new_tokens=4,
        sampler=sampler,
        rng_seed=7,
        backend_policy="native-cpu",
    )
    state, *_ = model_runtime.advance(state, {}, 1)
    request = state["operations"][state["await_target"]]["request"]
    recorded = request["sampler"]
    draws = request["run"]["draws"]
    assert len(draws) == 4
    for draw in draws:
        executed, _ = native._model_sampler(
            recorded["mode"], recorded["temperature"], recorded["top_k"], draw
        )
        assert {**recorded, "draw": draw} == executed


def _graph_site_text(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<I", len(encoded)) + encoded


def _graph_site_preflight_wire(
    *,
    task_id: str,
    sequence_id: str,
    native_operation_id: str,
    source_sha256: str,
    next_position: int,
    sampler: dict[str, Any],
    sampler_sha256: str,
) -> bytes:
    context_limit = 512
    payload = bytearray()
    payload.extend(struct.pack("<I", native.GRAPH_SITE_WIRE_VERSION))
    payload.extend(struct.pack("<B", 1))
    payload.extend(struct.pack("<i", 3))
    payload.extend(struct.pack("<i", next_position))
    payload.extend(struct.pack("<I", context_limit))
    payload.extend(struct.pack("<I", context_limit - next_position))
    payload.extend(struct.pack("<I", 1024))
    payload.extend(struct.pack("<I", 24))
    for value in (
        task_id,
        sequence_id,
        native_operation_id,
        source_sha256,
        "b" * 64,
        "c" * 64,
        "d" * 64,
        "e" * 64,
        "f" * 64,
        sampler_sha256,
    ):
        payload.extend(_graph_site_text(value))
    payload.extend(_graph_site_text(sampler["mode"]))
    payload.extend(struct.pack("<d", sampler["temperature"]))
    payload.extend(struct.pack("<I", sampler["top_k"]))
    payload.extend(struct.pack("<d", sampler["draw"]))
    payload.extend(_graph_site_text(""))
    payload.extend(struct.pack("<I", 1))
    payload.extend(struct.pack("<I", 2))
    payload.extend(struct.pack("<B", 1))
    payload.extend(struct.pack("<i", 3))
    payload.extend(struct.pack("<I", 1024))
    payload.extend(struct.pack("<I", 1024))
    for value in ("ffn", "recurrent", "recurrent-dynamics", "input", "output", "[]", ""):
        payload.extend(_graph_site_text(value))
    return bytes(payload)


def _preflight_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    prior_tokens: Sequence[int],
    accepted_token: int,
    sampler: dict[str, Any],
    sampler_sha256: str,
    source_sha256: str,
    wire_for: Any,
) -> native.NativeFieldRuntimeClient:
    client = object.__new__(native.NativeFieldRuntimeClient)
    client._pending_graph_site_candidates = {}
    client._graph_site_preflights = {}
    client._model_task_states = {
        "task": {
            "source_sha256": source_sha256,
            "input_tokens": tuple(prior_tokens),
            "accepted_token_id": accepted_token,
            "accepted_steps": [],
            "initialized": True,
            "model_sha256": "b" * 64,
            "tokenizer_sha256": "c" * 64,
        }
    }

    def request(kind: int, fields: Sequence[tuple[int, int, bytes]]) -> dict[int, tuple[int, bytes]]:
        assert kind == native.GRAPH_SITE_PREFLIGHT
        tokens = native._model_token_history(
            _decode_i32_vector(fields[2][2])
        )[0]
        return {
            1: (native.WIRE_UTF8, b"graph-site-preflight"),
            2: (
                native.WIRE_BYTES,
                wire_for(tuple(tokens), len(tuple(tokens)) - 1),
            ),
        }

    monkeypatch.setattr(client, "_request", request)
    return client


def _decode_i32_vector(payload: bytes) -> list[int]:
    return list(struct.unpack(f"<{len(payload) // 4}i", payload))


@pytest.mark.skipif(sys.platform != "win32", reason="native field-runtime transport is Windows-only")
def test_graph_site_preflight_accepts_the_history_that_includes_its_accepted_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The owner submits the next decode boundary as the history that already
    # contains the token its last step accepted, so preflight re-anchors the
    # task to that exact history instead of demanding a longer one.
    sampler = {"mode": "greedy", "temperature": 1.0, "top_k": 0, "draw": 0.0}
    _, sampler_sha256 = native._normalized_graph_site_sampler(sampler)
    source_sha256 = "a" * 64

    def wire_for(tokens: Sequence[int], next_position: int) -> bytes:
        return _graph_site_preflight_wire(
            task_id="task",
            sequence_id="task-seq",
            native_operation_id="operation",
            source_sha256=source_sha256,
            next_position=next_position,
            sampler=sampler,
            sampler_sha256=sampler_sha256,
        )

    accepted = _preflight_client(
        monkeypatch,
        prior_tokens=[1, 2, 3],
        accepted_token=7,
        sampler=sampler,
        sampler_sha256=sampler_sha256,
        source_sha256=source_sha256,
        wire_for=wire_for,
    )
    preflight = accepted.candidate_preflight(
        "task",
        source_sha256,
        [1, 2, 3, 7],
        sequence_id="task-seq",
        sampler=sampler,
        native_operation_id="operation",
    )
    assert preflight["ready"] is True
    assert preflight["input_tokens"] == [1, 2, 3, 7]
    assert preflight["next_position"] == 3
    state = accepted._model_task_states["task"]
    assert list(state["input_tokens"]) == [1, 2, 3, 7]
    assert state["accepted_token_id"] is None
    assert "task" in accepted._graph_site_preflights

    # A step that already ran past the accepted token is the same boundary.
    advanced = _preflight_client(
        monkeypatch,
        prior_tokens=[1, 2, 3],
        accepted_token=7,
        sampler=sampler,
        sampler_sha256=sampler_sha256,
        source_sha256=source_sha256,
        wire_for=wire_for,
    )
    advanced.candidate_preflight(
        "task",
        source_sha256,
        [1, 2, 3, 7, 11],
        sequence_id="task-seq",
        sampler=sampler,
        native_operation_id="operation",
    )
    assert list(advanced._model_task_states["task"]["input_tokens"]) == [1, 2, 3, 7, 11]

    # A history that diverges from the accepted step is still refused.
    divergent = _preflight_client(
        monkeypatch,
        prior_tokens=[1, 2, 3],
        accepted_token=7,
        sampler=sampler,
        sampler_sha256=sampler_sha256,
        source_sha256=source_sha256,
        wire_for=wire_for,
    )
    with pytest.raises(native.NativeFieldRuntimeError, match="not the next accepted step"):
        divergent.candidate_preflight(
            "task",
            source_sha256,
            [1, 2, 3, 9],
            sequence_id="task-seq",
            sampler=sampler,
            native_operation_id="operation",
        )
def _draft_rows_wire(rows: Sequence[dict[str, Any]]) -> bytes:
    payload = bytearray(struct.pack("<I", len(rows)))
    for row in rows:
        payload.extend(struct.pack("<i", int(row["token"])))
        payload.extend(struct.pack("<B", 1 if row["end_of_generation"] else 0))
        payload.extend(_graph_site_text(str(row["replay_sha256"])))
        payload.extend(struct.pack("<Q", int(row["token_count"])))
        payload.extend(_graph_site_text(str(row["stage_trace_sha256"])))
        for key in (
            "exact_stages",
            "embedding_stages",
            "attention_stages",
            "ffn_stages",
            "head_stages",
            "ggml_nodes",
            "logical_weight_bytes",
        ):
            payload.extend(struct.pack("<Q", int(row[key])))
        for key in (
            "sampler_sha256",
            "native_predecessor_sha256",
            "native_successor_sha256",
            "input_tokens_sha256",
            "native_operation_id",
            "sequence_id",
        ):
            payload.extend(_graph_site_text(str(row[key])))
        payload.extend(struct.pack("<Q", int(row["position"])))
        payload.extend(struct.pack("<B", 1 if row["draft_matched"] else 0))
    return bytes(payload)


def _decode_draft_request(payload: bytes) -> dict[str, Any]:
    cursor = 0

    def take(count: int) -> bytes:
        nonlocal cursor
        value = payload[cursor : cursor + count]
        cursor += count
        return value

    def u32() -> int:
        return struct.unpack("<I", take(4))[0]

    def i32() -> int:
        return struct.unpack("<i", take(4))[0]

    def text() -> str:
        return take(u32()).decode("utf-8")

    def i32_vector() -> list[int]:
        return [i32() for _ in range(u32())]

    decoded = {
        "task_id": text(),
        "source_sha256": text(),
        "tokens": i32_vector(),
        "draft_tokens": i32_vector(),
        "sampler_mode": text(),
        "temperature": struct.unpack("<d", take(8))[0],
        "top_k": u32(),
        "draws": [struct.unpack("<d", take(8))[0] for _ in range(u32())],
        "operation_ids": [text() for _ in range(u32())],
        "sequence_id": text(),
    }
    assert cursor == len(payload)
    return decoded


def _draft_round_rows(
    request: dict[str, Any],
    *,
    tokens: Sequence[int],
    matches: Sequence[bool],
) -> list[dict[str, Any]]:
    """Build the rows the native runtime would emit for one round."""

    history = list(request["tokens"])
    rows: list[dict[str, Any]] = []
    for index, token in enumerate(tokens):
        sampler, sampler_sha256 = native._model_sampler(
            request["sampler_mode"],
            request["temperature"],
            request["top_k"],
            request["draws"][index],
        )
        rows.append(
            {
                "token": int(token),
                "end_of_generation": False,
                "replay_sha256": f"{index + 1:064x}",
                "token_count": len(history) + 1,
                "stage_trace_sha256": f"{index + 11:064x}",
                "exact_stages": 50,
                "embedding_stages": 1,
                "attention_stages": 24,
                "ffn_stages": 24,
                "head_stages": 1,
                "ggml_nodes": 1846,
                "logical_weight_bytes": 552075584,
                "sampler_sha256": sampler_sha256,
                "native_predecessor_sha256": "a" * 64 if index == 0 else "",
                "native_successor_sha256": "b" * 64 if index + 1 == len(tokens) else "",
                "input_tokens_sha256": native._model_token_history(history)[2],
                "native_operation_id": request["operation_ids"][index],
                "sequence_id": request["sequence_id"],
                "position": len(history),
                "draft_matched": bool(matches[index]),
            }
        )
        history.append(int(token))
    return rows


def _draft_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    prior_tokens: Sequence[int],
    accepted_token: int | None,
    source_sha256: str,
    rows_for: Any,
) -> tuple[native.NativeFieldRuntimeClient, list[dict[str, Any]]]:
    client = object.__new__(native.NativeFieldRuntimeClient)
    client.service_generation = 4
    client._pending_graph_site_candidates = {}
    client._model_task_states = {
        "task": {
            "source_sha256": source_sha256,
            "input_tokens": tuple(prior_tokens),
            "accepted_token_id": accepted_token,
            "accepted_steps": [],
            "initialized": True,
        }
    }
    captured: list[dict[str, Any]] = []

    def request(kind: int, fields: Sequence[tuple[int, int, bytes]]) -> dict[int, tuple[int, bytes]]:
        assert kind == native.VERIFY_MODEL_DRAFT
        decoded = _decode_draft_request(fields[0][2])
        captured.append(decoded)
        return {
            1: (native.WIRE_UTF8, b"model-draft-rows"),
            2: (native.WIRE_BYTES, _draft_rows_wire(rows_for(decoded))),
        }

    monkeypatch.setattr(client, "_request", request)
    return client, captured


def test_native_draft_round_commits_the_accepted_prefix_and_its_bonus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_sha256 = "d" * 64
    proposal = [220, 16, 15]

    def rows_for(request: dict[str, Any]) -> list[dict[str, Any]]:
        return _draft_round_rows(
            request, tokens=[220, 16, 15, 11], matches=[True, True, True, False]
        )

    client, captured = _draft_client(
        monkeypatch,
        prior_tokens=[9707, 11, 1879, 374],
        accepted_token=283,
        source_sha256=source_sha256,
        rows_for=rows_for,
    )
    result = client.verify_model_draft(
        "task",
        source_sha256,
        [9707, 11, 1879, 374, 283],
        proposal,
        draws=[0.0, 0.25, 0.5, 0.75],
        operation_ids=["op-0", "op-1", "op-2", "op-3"],
        sequence_id="task-seq",
    )
    assert captured[0]["draft_tokens"] == proposal
    assert captured[0]["tokens"] == [9707, 11, 1879, 374, 283]
    assert captured[0]["draws"] == [0.0, 0.25, 0.5, 0.75]
    assert captured[0]["operation_ids"] == ["op-0", "op-1", "op-2", "op-3"]
    assert captured[0]["sequence_id"] == "task-seq"
    assert result["committed"] == 4
    assert [row["token"] for row in result["rows"]] == [220, 16, 15, 11]
    assert [row["draft_matched"] for row in result["rows"]] == [True, True, True, False]
    assert result["rows"][0]["input_tokens"] == [9707, 11, 1879, 374, 283]
    assert result["rows"][3]["input_tokens"] == [9707, 11, 1879, 374, 283, 220, 16, 15]
    assert result["rows"][0]["native_predecessor_sha256"] == "a" * 64
    assert result["rows"][3]["native_successor_sha256"] == "b" * 64
    state = client._model_task_states["task"]
    assert state["input_tokens"] == [9707, 11, 1879, 374, 283, 220, 16, 15]
    assert state["accepted_token_id"] == 11
    assert len(state["accepted_steps"]) == 4
    assert state["accepted_steps"][2]["native_operation_id"] == "op-2"


def test_native_draft_round_rejects_a_row_that_left_its_round(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_sha256 = "d" * 64

    def rows_for(request: dict[str, Any]) -> list[dict[str, Any]]:
        rows = _draft_round_rows(request, tokens=[220, 16], matches=[True, False])
        rows[1]["native_operation_id"] = "op-elsewhere"
        return rows

    client, _ = _draft_client(
        monkeypatch,
        prior_tokens=[1, 2],
        accepted_token=3,
        source_sha256=source_sha256,
        rows_for=rows_for,
    )
    with pytest.raises(native.NativeFieldRuntimeError, match="disagrees with its round"):
        client.verify_model_draft(
            "task",
            source_sha256,
            [1, 2, 3],
            [220, 16],
            draws=[0.0, 0.0, 0.0],
            operation_ids=["op-0", "op-1", "op-2"],
        )


def test_native_draft_round_stops_at_the_owners_stop_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_sha256 = "d" * 64

    def rows_for(request: dict[str, Any]) -> list[dict[str, Any]]:
        return _draft_round_rows(
            request, tokens=[220, 99, 15], matches=[True, True, False]
        )

    client, _ = _draft_client(
        monkeypatch,
        prior_tokens=[1, 2],
        accepted_token=3,
        source_sha256=source_sha256,
        rows_for=rows_for,
    )
    result = client.verify_model_draft(
        "task",
        source_sha256,
        [1, 2, 3],
        [220, 99, 15],
        draws=[0.0, 0.0, 0.0, 0.0],
        operation_ids=["op-0", "op-1", "op-2", "op-3"],
        stop_tokens=[99],
    )
    assert [row["token"] for row in result["rows"]] == [220, 99]
    assert result["committed"] == 2
    state = client._model_task_states["task"]
    assert state["input_tokens"] == [1, 2, 3, 220]
    assert state["accepted_token_id"] == 99
    assert len(state["accepted_steps"]) == 2


def test_native_draft_round_rejects_a_proposal_outside_the_draft_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_sha256 = "d" * 64
    client, _ = _draft_client(
        monkeypatch,
        prior_tokens=[1, 2],
        accepted_token=3,
        source_sha256=source_sha256,
        rows_for=lambda request: [],
    )
    with pytest.raises(native.NativeFieldRuntimeError, match="draws must carry one entry"):
        client.verify_model_draft(
            "task",
            source_sha256,
            [1, 2, 3],
            [220, 16],
            draws=[0.0, 0.0],
            operation_ids=["op-0", "op-1"],
        )
    with pytest.raises(native.NativeFieldRuntimeError, match="unique and match the draws"):
        client.verify_model_draft(
            "task",
            source_sha256,
            [1, 2, 3],
            [220, 16],
            draws=[0.0, 0.0, 0.0],
            operation_ids=["op-0", "op-0", "op-2"],
        )
    with pytest.raises(native.NativeFieldRuntimeError, match="exceeds its bound"):
        client.verify_model_draft(
            "task",
            source_sha256,
            [1, 2, 3],
            list(range(native.MAX_DRAFT_TOKENS + 1)),
            draws=[0.0] * (native.MAX_DRAFT_TOKENS + 2),
            operation_ids=[f"op-{index}" for index in range(native.MAX_DRAFT_TOKENS + 2)],
        )
