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
