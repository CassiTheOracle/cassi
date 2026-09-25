"""Scoped smoke: device identity carry + two-key wrong-device refusal (no native exe)."""
from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import cassi_field_runtime as runtime_module
import cassi_field_runtime_native as native_module


def digest_of(value) -> str:
    return hashlib.sha256(
        runtime_module._canonical(value)
    ).hexdigest()


class FakePipe:
    value = 1

    def close(self) -> None:
        pass


class StubNativeClient:
    """Duck-typed native client with a mutable device report."""

    def __init__(self, index: int | None, identity: str | None, kind: str | None = "device-uuid-stable") -> None:
        self.instance_id = "stub"
        self.launch_nonce = "nonce"
        self.service_generation = 7
        self.device_index = index
        self._report = native_module._device_report(
            device_index=index,
            device_identity=identity,
            device_identity_kind=kind,
            heap_total=16 << 30 if identity is not None else None,
            heap_budget=None,
            heap_usage=None,
            memory_state="heap-total-only" if identity is not None else None,
            note="stub",
        )
        self.begin_calls: list[str] = []
        self.verify_calls: list[str] = []

    def device_report(self, *, refresh: bool = False) -> dict:
        return dict(self._report)

    def status(self) -> dict:
        return {
            "status": "ready",
            "service_generation": 7,
            "attachments": 0,
            "candidates": 0,
            "vulkan": "ready",
            "vulkan_device": "AMD",
            "vulkan_reason": "ready",
            "model_runtime": "ready",
            "loaded_models": 0,
            "model_tasks": 0,
            "model_runtime_reason": "",
            "execution_profile": "default",
            "device": dict(self._report),
        }

    def verify_device(self, operation: str):
        index = self._report["device_index"]
        if self.device_index is not None and isinstance(index, int) and index != self.device_index:
            raise native_module.NativeFieldRuntimeError(
                f"native field-runtime reported device index {index} for {operation} but launch requested device {self.device_index}"
            )
        return self._report

    def attach_packed(self, owner_id, shape, packed_words, **kwargs) -> dict:
        self.verify_device("attach")
        return {"status": "attached", "owner_id": owner_id, "word_count": len(packed_words) // 4, "packed_sha256": hashlib.sha256(packed_words).hexdigest()}

    def begin_candidate(self, owner_id, predecessor_state_sha256, *, fence, lease_id, placement) -> str:
        self.verify_device("begin_candidate")
        self.begin_calls.append(owner_id)
        return "candidate:1"

    def candidate_placement(self, candidate_id: str) -> str:
        return "native-cpu"

    def apply_word_operations(self, candidate_id, operations) -> dict:
        return {"status": "candidate-advanced", "logical_operations": 1, "canonical_bytes_sha256": "a" * 64, "placement": "native-cpu"}

    def apply_candidate_page(self, candidate_id, page_index, predecessor_page_sha256, packed_words) -> dict:
        return {"status": "candidate-page-accepted", "logical_operations": 1, "placement": "native-cpu"}

    def export_candidate(self, candidate_id, shape):
        payload_words = np.prod(shape, dtype=np.int64)
        return np.zeros(tuple(int(s) for s in shape), dtype=np.float64), {
            "status": "candidate-exported",
            "predecessor_state_sha256": "b" * 64,
            "logical_operations": 1,
            "payload_sha256": hashlib.sha256(b"\x00" * int(payload_words) * 4).hexdigest(),
        }

    def reduce_candidate(self, candidate_id, first_word, count) -> dict:
        return {
            "status": "reduced",
            "sum": 0,
            "count": count,
            "first_word": first_word,
            "placement": "native-cpu",
            "fence": 0,
            "predecessor_state_sha256": "b" * 64,
        }

    def confirm_cache(self, candidate_id, predecessor_state_sha256, successor_state_sha256, *, fence, lease_id) -> dict:
        return {"status": "cache-confirmed", "owner_id": "owner-1", "state_sha256": successor_state_sha256, "fence": fence + 1}

    def discard_candidate(self, candidate_id) -> dict:
        return {"status": "discarded", "candidate_id": candidate_id}

    def detach(self, owner_id) -> dict:
        return {"status": "detached", "owner_id": owner_id}

    def shutdown(self) -> None:
        pass

    def close(self) -> None:
        pass


def packed_image(state: str) -> runtime_module.PackedFieldImage:
    return runtime_module.PackedFieldImage(
        profile_sha256=hashlib.sha256(b"profile").hexdigest(),
        state_sha256=hashlib.sha256(state.encode()).hexdigest(),
        catalog_sha256=hashlib.sha256(b"catalog").hexdigest(),
        shape=(4,),
        payload=b"\x01\x00\x00\x00" * 4,
    )


def make_client_response(fields: dict[int, tuple[int, int, bytes]]) -> dict[int, tuple[int, bytes]]:
    return {tag: (wire, value) for tag, wire, value in fields}


def check_native_status_parsing() -> None:
    print("== native client status/probe parsing ==")
    client = object.__new__(native_module.NativeFieldRuntimeClient)
    client.device_index = 1
    client._device_report = None

    u64 = lambda v: (native_module.WIRE_U64, int(v).to_bytes(8, "little"))
    txt = lambda s: (native_module.WIRE_UTF8, s.encode())
    full = {
        1: txt("ready"), 2: u64(3), 3: u64(0), 4: u64(0), 5: txt("ready"),
        6: txt("AMD"), 7: txt("ready"), 8: txt("ready"), 9: u64(0), 10: u64(0),
        11: txt(""), 12: txt("default"),
        13: u64(1), 14: txt("ab" * 32), 15: txt("device-uuid-stable"),
        16: u64(16 << 30), 17: u64(12 << 30), 18: u64(2 << 30),
        19: txt("measured"), 20: txt("VK_EXT_memory_budget"),
    }
    client._request = lambda kind, fields: dict(full)
    status = client.status()
    assert status["device"]["device_index"] == 1
    assert status["device"]["device_identity"] == "ab" * 32
    assert status["device"]["device_identity_kind"] == "device-uuid-stable"
    assert status["device"]["heap_total_bytes"] == 16 << 30
    assert status["device"]["heap_budget_bytes"] == 12 << 30
    assert status["device"]["heap_usage_bytes"] == 2 << 30
    assert status["device"]["memory_state"] == "measured"

    heap_only = dict(full)
    heap_only[17] = u64(0)
    heap_only[18] = u64(0)
    heap_only[19] = txt("heap-total-only")
    heap_only[20] = txt("VK_EXT_memory_budget present but driver reported no budget data")
    client._request = lambda kind, fields: dict(heap_only)
    status = client.status()
    assert status["device"]["heap_total_bytes"] == 16 << 30
    assert status["device"]["heap_budget_bytes"] is None, "budget must stay unknown without measured state"
    assert status["device"]["heap_usage_bytes"] is None

    legacy = {tag: full[tag] for tag in range(1, 13)}
    client._request = lambda kind, fields: dict(legacy)
    status = client.status()
    assert status["device"] == {
        "device_index": None, "device_identity": None, "device_identity_kind": None,
        "heap_total_bytes": None, "heap_budget_bytes": None, "heap_usage_bytes": None,
        "memory_state": None, "note": None,
    }, "older native build must yield explicit unknowns"

    unavailable = dict(legacy)
    unavailable[13] = u64(0)
    unavailable[14] = txt("unavailable")
    unavailable[15] = txt("unavailable")
    unavailable[16] = u64(0)
    unavailable[19] = txt("unavailable")
    client._request = lambda kind, fields: dict(unavailable)
    status = client.status()
    assert status["device"]["device_identity"] is None
    assert status["device"]["device_identity_kind"] is None
    assert status["device"]["heap_total_bytes"] is None, "heap total must be unknown when state is unavailable"

    probe_u64 = lambda v: (native_module.WIRE_U64, int(v).to_bytes(8, "little"))
    probe_full = {
        1: txt("ready"), 2: txt("AMD"), 3: txt("ready"), 4: txt("exact-word-operation-groups"),
        5: probe_u64(1), 6: txt("ab" * 32), 7: txt("device-uuid-stable"),
        8: probe_u64(16 << 30), 9: probe_u64(12 << 30), 10: probe_u64(2 << 30),
        11: txt("measured"), 12: txt("VK_EXT_memory_budget"),
    }
    probe_legacy = {tag: probe_full[tag] for tag in range(1, 5)}
    client._request = lambda kind, fields: dict(probe_full)
    probe = client.probe_vulkan()
    assert probe["device_report"]["device_index"] == 1
    assert probe["device_report"]["memory_state"] == "measured"
    client._request = lambda kind, fields: dict(probe_legacy)
    probe = client.probe_vulkan()
    assert probe["device_report"] == {
        "device_index": None, "device_identity": None, "device_identity_kind": None,
        "heap_total_bytes": None, "heap_budget_bytes": None, "heap_usage_bytes": None,
        "memory_state": None, "note": None,
    }

    client._request = lambda kind, fields: dict(probe_full)
    client.probe_vulkan()
    assert client._device_report["device_index"] == 1

    mismatch = object.__new__(native_module.NativeFieldRuntimeClient)
    mismatch.device_index = 2
    mismatch._device_report = None
    mismatch._request = lambda kind, fields: dict(full)
    try:
        mismatch.status()
        index_error = None
    except native_module.NativeFieldRuntimeError as exc:
        index_error = exc
    assert index_error is None  # status itself only reports, never refuses
    try:
        mismatch.verify_device("attach")
        raise AssertionError("mismatched device index must refuse")
    except native_module.NativeFieldRuntimeError as exc:
        assert "reported device index 1" in str(exc) and "requested device 2" in str(exc)
    print("status/probe parsing + verify_device: OK")

    matching = object.__new__(native_module.NativeFieldRuntimeClient)
    matching.device_index = 1
    matching._device_report = None
    matching._request = lambda kind, fields: dict(full)
    matching.verify_device("begin_candidate")
    print("matching index accepted: OK")


def check_two_key_refusal() -> None:
    print("== runtime two-key wrong-device refusal ==")
    stub = StubNativeClient(index=0, identity="gpu-a")
    rt = runtime_module.ResidentFieldRuntime(native_client=stub)
    assert rt.service_generation == 7
    image = packed_image("state-0")
    attachment = runtime_module.ResidentAttachment(
        owner_id="owner-1",
        service_generation=7,
        fence=0,
        image=image,
        placement="vulkan",
        device_index=0,
        device_identity="gpu-a",
    )
    rt._attachments["owner-1"] = attachment
    descriptor = attachment.descriptor()
    assert descriptor["device_index"] == 0 and descriptor["device_identity"] == "gpu-a"

    candidate_id = rt.begin_candidate(
        "owner-1",
        predecessor_state_sha256=image.state_sha256,
        fence=0,
        lease_id="lease-1",
        placement="vulkan",
    )
    assert rt.device_report()["device_index"] == 0

    # wrong device index continuation (identity still matches)
    stub._report = native_module._device_report(
        device_index=1, device_identity="gpu-a", device_identity_kind="device-uuid-stable",
        heap_total=16 << 30, heap_budget=None, heap_usage=None,
        memory_state="heap-total-only", note="stub",
    )
    try:
        rt.compute_words(candidate_id, ())
        raise AssertionError("wrong-device-index continuation must be refused")
    except runtime_module.FieldRuntimeError as exc:
        assert "wrong-device" in str(exc), exc

    # wrong identity continuation (index matches again)
    stub._report = native_module._device_report(
        device_index=0, device_identity="gpu-b", device_identity_kind="device-uuid-stable",
        heap_total=16 << 30, heap_budget=None, heap_usage=None,
        memory_state="heap-total-only", note="stub",
    )
    try:
        rt.compute_words(candidate_id, ())
        raise AssertionError("wrong-device-identity continuation must be refused")
    except runtime_module.FieldRuntimeError as exc:
        assert "wrong-device" in str(exc), exc
    try:
        rt.reduce_candidate(candidate_id, 0, 4, owner_id="owner-1", fence=0, lease_id="lease-1")
        raise AssertionError("wrong-device reduction must be refused")
    except runtime_module.FieldRuntimeError as exc:
        assert "wrong-device" in str(exc), exc

    # matching again -> continuation works; settle carries device identity
    stub._report = native_module._device_report(
        device_index=0, device_identity="gpu-a", device_identity_kind="device-uuid-stable",
        heap_total=16 << 30, heap_budget=None, heap_usage=None,
        memory_state="heap-total-only", note="stub",
    )
    result = rt.compute_words(candidate_id, [])
    assert result["placement"] == "native-cpu"
    successor = packed_image("state-1")
    epoch = rt.settle_candidate(
        candidate_id,
        None,
        state_sha256=successor.state_sha256,
        catalog_sha256=successor.catalog_sha256,
        logical_transitions=1,
        dispatches=1,
    ) if False else None
    # settle needs a ComputerState; drive _settle_native_image path via a direct epoch build instead
    print("compute/reduce wrong-device refusals: OK")

    # publication refusal: settled epoch on device gpu-a, service now reports gpu-b
    epoch = runtime_module.CandidateEpoch(
        candidate_id=candidate_id,
        owner_id="owner-1",
        service_generation=7,
        fence=0,
        lease_id="lease-1",
        predecessor_state_sha256=image.state_sha256,
        image=successor,
        logical_transitions=1,
        dispatches=1,
        events=(),
        errors=(),
        placement="native-cpu",
        result_sha256="c" * 64,
        device_index=0,
        device_identity="gpu-a",
    )
    rt._settled[candidate_id] = epoch
    stub._report = native_module._device_report(
        device_index=0, device_identity="gpu-b", device_identity_kind="device-uuid-stable",
        heap_total=16 << 30, heap_budget=None, heap_usage=None,
        memory_state="heap-total-only", note="stub",
    )
    try:
        rt.validate_for_publication(
            candidate_id,
            owner_state_sha256=image.state_sha256,
            fence=0,
            lease_id="lease-1",
        )
        raise AssertionError("wrong-device publication must be refused")
    except runtime_module.FieldRuntimeError as exc:
        assert "wrong-device" in str(exc), exc
    stub._report = native_module._device_report(
        device_index=0, device_identity="gpu-a", device_identity_kind="device-uuid-stable",
        heap_total=16 << 30, heap_budget=None, heap_usage=None,
        memory_state="heap-total-only", note="stub",
    )
    validated = rt.validate_for_publication(
        candidate_id,
        owner_state_sha256=image.state_sha256,
        fence=0,
        lease_id="lease-1",
    )
    assert validated.device_identity == "gpu-a"
    print("publication wrong-device refusal + acceptance: OK")


def check_device_accounting_selection() -> None:
    print("== admission device selection ==")
    rt_none = runtime_module.ResidentFieldRuntime(native_client=None)
    assert rt_none.device_report() is None

    class FakeAdmission:
        def __init__(self, devices) -> None:
            self.owner_id = "owner"
            self.manager = type("M", (), {"_vram_devices": devices, "limits": type("L", (), {"cpu_cache_bytes": 1 << 20})()})()

    pick = runtime_module.ResidentFieldRuntime.__name__  # noqa: F841
    swarm_module = __import__("cassi_programmable_swarm")
    pick = swarm_module.ProgrammableSwarm._resident_vram_device

    assert pick(rt_none, FakeAdmission({})) is None, "no declaration -> legacy default accounting"
    assert pick(rt_none, FakeAdmission({"0": {}})) == "0", "single registered device is the default"
    try:
        pick(rt_none, FakeAdmission({"0": {}, "1": {}}))
        raise AssertionError("multiple devices without index must refuse")
    except Exception as exc:
        assert "cannot select" in str(exc), exc

    stub = StubNativeClient(index=1, identity="gpu-a")
    rt1 = runtime_module.ResidentFieldRuntime(native_client=stub)
    assert pick(rt1, FakeAdmission({"1": {}})) == "1"
    try:
        pick(rt1, FakeAdmission({"0": {}}))
        raise AssertionError("mismatched registration must refuse")
    except Exception as exc:
        assert "not declared" in str(exc), exc
    print("admission device selection: OK")


def check_runtime_status_device() -> None:
    print("== runtime status device report ==")
    stub = StubNativeClient(index=1, identity="gpu-a")
    rt = runtime_module.ResidentFieldRuntime(native_client=stub)
    status = rt.status()
    assert status["device"]["device_index"] == 1
    assert status["device"]["memory_state"] == "heap-total-only"
    assert status["device"]["heap_budget_bytes"] is None
    assert status["native_service"]["device"]["device_index"] == 1
    print("runtime status device: OK")


def check_group_wire() -> None:
    print("== group client wire ==")
    client = object.__new__(native_module.NativeFieldRuntimeClient)
    client.device_index = None
    client._device_report = None

    source = hashlib.sha256(b"model").hexdigest()
    requests: list[tuple[int, dict[int, tuple[int, bytes]]]] = []

    rows = [
        native_module.NativeGroupRow(
            tokens=(1, 2, 3),
            next_token=4,
            accept_sampled=False,
            sampler_mode="greedy",
            temperature=0.8,
            top_k=40,
            draw=0.0,
        ),
        native_module.NativeGroupRow(
            tokens=(),
            next_token=0,
            accept_sampled=True,
            sampler_mode="categorical",
            temperature=1.0,
            top_k=0,
            draw=0.5,
        ),
        native_module.NativeGroupRow(
            tokens=(9,) * 5,
            next_token=10,
            accept_sampled=False,
            sampler_mode="greedy",
            temperature=0.5,
            top_k=1,
            draw=0.0,
        ),
    ]
    rows_blob = b"".join(row.encode() for row in rows)

    def encode_group_result_row(
        token: int, eog: int, sampled: int, token_count: int
    ) -> bytes:
        replay = hashlib.sha256(f"replay{token}".encode()).hexdigest().encode("ascii")
        trace = hashlib.sha256(f"trace{token}".encode()).hexdigest().encode("ascii")
        return b"".join(
            (
                struct.pack("<iBi", token, eog, sampled),
                struct.pack("<I", 64), replay,
                struct.pack("<Q", token_count),
                struct.pack("<I", 64), trace,
                struct.pack("<7Q", 1, 2, 3, 4, 5, 6, 7),
            )
        )

    client._request = _create_request(requests, source, 3)
    created = client.create_group(source, 3)
    assert created == {"status": "group-created", "group_id": 5, "capacity": 3, "group_count": 1}

    client._request = _step_request(requests, rows_blob, 5, 3, encode_group_result_row)
    advanced = client.step_group(5, rows)
    assert advanced["status"] == "group-advanced"
    assert advanced["native_graph_candidate"] == "unavailable_native_group_candidate"
    assert advanced["group_id"] == 5 and advanced["row_count"] == 3
    assert [row["token"] for row in advanced["rows"]] == [0, 1, 2]
    assert advanced["rows"][1]["sampled_token"] == 101
    assert advanced["rows"][2]["end_of_generation"] is False
    assert advanced["rows"][0]["replay_sha256"] == hashlib.sha256(b"replay0").hexdigest()
    assert advanced["rows"][0]["token_count"] == 7
    assert advanced["rows"][1]["ggml_nodes"] == 6
    assert advanced["rows"][2]["logical_weight_bytes"] == 7

    client._request = _drop_request(requests, 5)
    dropped = client.drop_group(5)
    assert dropped == {"status": "group-dropped", "group_id": 5, "group_count": 0}

    # validation errors
    for bad in (1, 9, True, 2.0):
        try:
            client.create_group(source, bad)
            raise AssertionError(f"capacity {bad} must be refused")
        except native_module.NativeFieldRuntimeError:
            pass
    try:
        client.step_group(0, rows)
        raise AssertionError("group id 0 must be refused")
    except native_module.NativeFieldRuntimeError:
        pass
    bad_row = native_module.NativeGroupRow(
        tokens=(-1,), next_token=0, accept_sampled=False,
        sampler_mode="greedy", temperature=1.0, top_k=0, draw=0.0,
    )
    try:
        client.step_group(5, (rows[0], bad_row))
        raise AssertionError("negative token must be refused")
    except native_module.NativeFieldRuntimeError:
        pass

    # truncated result blob is rejected
    def truncated_request(kind, fields):
        row = {tag: (wire, value) for tag, wire, value in fields}
        requests.append((kind, row))
        body = native_module._body(
            (
                native_module._utf8(1, "group-advanced"),
                native_module._u64(2, 5),
                native_module._bytes(21, encode_group_result_row(0, 0, 0, 1)[:-4]),
                native_module._u64(22, 3),
                native_module._utf8(23, "unavailable_native_group_candidate"),
            )
        )
        return native_module._decode_body(body)

    client._request = truncated_request
    try:
        client.step_group(5, rows)
        raise AssertionError("truncated group result must be refused")
    except native_module.NativeFieldRuntimeError as exc:
        assert "truncated" in str(exc), exc

    # trailing bytes are rejected
    def trailing_request(kind, fields):
        body = native_module._body(
            (
                native_module._utf8(1, "group-advanced"),
                native_module._u64(2, 5),
                native_module._bytes(21, encode_group_result_row(0, 0, 0, 0) * 3 + b"\x00"),
                native_module._u64(22, 3),
                native_module._utf8(23, "unavailable_native_group_candidate"),
            )
        )
        return native_module._decode_body(body)

    client._request = trailing_request
    try:
        client.step_group(5, rows)
        raise AssertionError("trailing group result bytes must be refused")
    except native_module.NativeFieldRuntimeError as exc:
        assert "trailing" in str(exc), exc
    print("group wire: OK")


def _capture_request(requests):
    def request(kind, fields):
        requests.append((kind, {tag: (wire, value) for tag, wire, value in fields}))
        raise AssertionError("unexpected kind in this phase")
    return request


def _step_request(requests, rows_blob, group_id, capacity, encode_row):
    def request(kind, fields):
        requests.append((kind, {tag: (wire, value) for tag, wire, value in fields}))
        if kind != native_module.STEP_GROUP:
            raise AssertionError(f"expected STEP_GROUP, got {kind}")
        row = {tag: (wire, value) for tag, wire, value in fields}
        assert native_module._field_u64(row, 21) == group_id
        blob = native_module._field_bytes(row, 22)
        assert blob == rows_blob, "encoded rows must match the contract layout byte for byte"
        body = native_module._body(
            (
                native_module._utf8(1, "group-advanced"),
                native_module._u64(2, group_id),
                native_module._bytes(21, b"".join(
                    encode_row(index, 0, index + 100, index + 7) for index in range(capacity)
                )),
                native_module._u64(22, capacity),
                native_module._utf8(23, "unavailable_native_group_candidate"),
            )
        )
        return native_module._decode_body(body)
    return request


def _drop_request(requests, group_id):
    def request(kind, fields):
        requests.append((kind, {tag: (wire, value) for tag, wire, value in fields}))
        row = {tag: (wire, value) for tag, wire, value in fields}
        assert native_module._field_u64(row, 21) == group_id
        body = native_module._body(
            (
                native_module._utf8(1, "group-dropped"),
                native_module._u64(2, group_id),
                native_module._u64(21, 0),
            )
        )
        return native_module._decode_body(body)
    return request


def _create_request(requests, source, capacity):
    def request(kind, fields):
        requests.append((kind, {tag: (wire, value) for tag, wire, value in fields}))
        row = {tag: (wire, value) for tag, wire, value in fields}
        assert native_module._field_text(row, 21) == source
        assert native_module._field_u64(row, 22) == capacity
        body = native_module._body(
            (
                native_module._utf8(1, "group-created"),
                native_module._u64(2, 5),
                native_module._u64(21, capacity),
                native_module._u64(22, 1),
            )
        )
        return native_module._decode_body(body)
    return request


if __name__ == "__main__":
    check_native_status_parsing()
    check_two_key_refusal()
    check_device_accounting_selection()
    check_runtime_status_device()
    check_group_wire()
    print("SMOKE_OK")
