import json

import numpy as np
import pytest

from programs.model import state_backing
from programs.model.state_backing import (
    SNAPSHOT_MANIFEST_CHUNKED_SCHEMA,
    SNAPSHOT_MANIFEST_SCHEMA,
    SnapshotCorruptionError,
    SnapshotStore,
    SnapshotStoreError,
)


def _chunked_store(path):
    return SnapshotStore(path, chunk_bytes=256, chunk_threshold_bytes=128)


def _manifest(store, descriptor):
    return json.loads((store.root / descriptor["manifest"]).read_text("utf-8"))


def test_chunked_snapshot_reuses_clean_regions_and_reopens_exact_bytes(tmp_path):
    store = _chunked_store(tmp_path / "state")
    kv = np.arange(1024, dtype=np.uint8)
    recurrent = np.arange(768, dtype=np.uint16)
    metadata = {"step": 1, "model": "qwen-test"}

    first = store.save({"kv": kv, "recurrent": recurrent}, metadata)
    first_manifest = _manifest(store, first)
    assert first_manifest["schema"] == SNAPSHOT_MANIFEST_CHUNKED_SCHEMA
    loaded, loaded_metadata = store.load(first)
    assert loaded_metadata == metadata

    changed_kv = np.array(loaded["kv"], copy=True)
    changed_kv[300:310] = 0
    writes_before = store.counters["chunk_writes"]
    candidate = store.save(
        {"kv": changed_kv, "recurrent": loaded["recurrent"]},
        {"step": 2, "model": "qwen-test"},
        reuse_immutable_arrays=True,
    )
    second_manifest = _manifest(store, candidate)
    old_kv_chunks = first_manifest["arrays"]["kv"]["chunks"]
    new_kv_chunks = second_manifest["arrays"]["kv"]["chunks"]
    assert new_kv_chunks[1]["sha256"] != old_kv_chunks[1]["sha256"]
    for index in (0, 2, 3):
        assert new_kv_chunks[index]["sha256"] == old_kv_chunks[index]["sha256"]
    assert [chunk["sha256"] for chunk in second_manifest["arrays"]["recurrent"]["chunks"]] == [
        chunk["sha256"] for chunk in first_manifest["arrays"]["recurrent"]["chunks"]
    ]
    assert store.counters["chunk_writes"] == writes_before + 1
    reopened = _chunked_store(tmp_path / "state")
    restored, restored_metadata = reopened.load(candidate)
    assert restored_metadata == {"step": 2, "model": "qwen-test"}
    assert restored["kv"].tobytes() == changed_kv.tobytes()
    assert restored["recurrent"].tobytes() == recurrent.tobytes()
    chunk_writes_before = reopened.counters["chunk_writes"]
    immutable_reuses_before = reopened.counters["immutable_array_reuses"]
    assert reopened.save(
        restored,
        restored_metadata,
        reuse_immutable_arrays=True,
    ) == candidate
    assert reopened.counters["chunk_writes"] == chunk_writes_before
    assert reopened.counters["immutable_array_reuses"] == immutable_reuses_before + 2
    assert not restored["kv"].flags.writeable
    assert json.loads(reopened.current.read_text("utf-8")) == candidate


def test_chunked_noncontiguous_array_restores_c_order_bytes(tmp_path):
    store = SnapshotStore(tmp_path / "state", chunk_bytes=64, chunk_threshold_bytes=32)
    source = np.arange(40 * 30, dtype=">i4").reshape(40, 30)[::3, 1::4]
    assert not source.flags.c_contiguous

    descriptor = store.save({"slice": source}, {"layout": "strided"})
    restored, metadata = SnapshotStore(tmp_path / "state").load(descriptor)

    assert metadata == {"layout": "strided"}
    assert restored["slice"].shape == source.shape
    assert restored["slice"].dtype == source.dtype
    assert restored["slice"].tobytes() == source.tobytes(order="C")


def test_failed_current_publication_keeps_predecessor_recoverable(tmp_path, monkeypatch):
    store = _chunked_store(tmp_path / "state")
    original = np.arange(512, dtype=np.uint8)
    predecessor = store.save({"kv": original}, {"step": 1})
    current_before = store.current.read_bytes()
    original_atomic = state_backing._atomic_bytes

    def interrupt_current(path, payload):
        if path == store.current:
            raise OSError("simulated interruption before CURRENT replace")
        original_atomic(path, payload)

    monkeypatch.setattr(state_backing, "_atomic_bytes", interrupt_current)
    with pytest.raises(SnapshotStoreError, match="CURRENT"):
        store.save({"kv": original + 1}, {"step": 2})

    assert store.current.read_bytes() == current_before
    recovered, metadata = _chunked_store(tmp_path / "state").load(predecessor)
    assert metadata == {"step": 1}
    assert recovered["kv"].tobytes() == original.tobytes()


def test_missing_or_tampered_chunk_is_rejected(tmp_path):
    store = _chunked_store(tmp_path / "state")
    array = np.arange(768, dtype=np.uint8)
    descriptor = store.save({"kv": array}, {"step": 1})
    chunks = _manifest(store, descriptor)["arrays"]["kv"]["chunks"]
    first_path = store.root / chunks[0]["blob"]
    first_bytes = first_path.read_bytes()

    first_path.write_bytes(bytes(len(first_bytes)))
    with pytest.raises(SnapshotCorruptionError):
        _chunked_store(tmp_path / "state").load(descriptor)

    first_path.write_bytes(first_bytes)
    (store.root / chunks[1]["blob"]).unlink()
    with pytest.raises(SnapshotCorruptionError):
        _chunked_store(tmp_path / "state").load(descriptor)


def test_small_arrays_keep_legacy_manifest_and_restore(tmp_path):
    store = SnapshotStore(tmp_path / "state", chunk_threshold_bytes=4096)
    array = np.arange(32, dtype=np.int16)
    descriptor = store.save({"small": array}, {"legacy": True})
    manifest = _manifest(store, descriptor)

    assert manifest["schema"] == SNAPSHOT_MANIFEST_SCHEMA
    assert "blob" in manifest["arrays"]["small"]
    restored, metadata = SnapshotStore(tmp_path / "state").load(descriptor)
    assert metadata == {"legacy": True}
    assert restored["small"].tobytes() == array.tobytes()


def test_deferred_save_moves_current_only_after_make_durable(tmp_path):
    store = _chunked_store(tmp_path / "state")
    base = store.save({"kv": np.arange(1024, dtype=np.uint8)}, {"step": 1})
    staged = np.arange(1024, dtype=np.uint8)
    staged[:300] = 7

    candidate = store.save({"kv": staged}, {"step": 2}, durable=False)
    assert json.loads(store.current.read_text("utf-8")) == base
    restored, _ = _chunked_store(tmp_path / "state").load(candidate)
    assert restored["kv"].tobytes() == staged.tobytes()

    syncs_before = store.counters["durability_syncs"]
    assert store.make_durable(candidate) == candidate
    assert json.loads(store.current.read_text("utf-8")) == candidate
    referenced = len(_manifest(store, candidate)["arrays"]["kv"]["chunks"]) + 1
    assert store.counters["durability_syncs"] - syncs_before <= referenced
    syncs_sealed = store.counters["durability_syncs"]
    assert store.save({"kv": staged}, {"step": 2}) == candidate
    assert store.counters["durability_syncs"] == syncs_sealed


def test_torn_backing_is_republished_from_exact_bytes(tmp_path):
    store = _chunked_store(tmp_path / "state")
    array = np.arange(768, dtype=np.uint8)
    descriptor = store.save({"kv": array}, {"step": 1}, durable=False)
    chunk_path = store.root / _manifest(store, descriptor)["arrays"]["kv"]["chunks"][0]["blob"]
    manifest_path = store.root / descriptor["manifest"]
    chunk_path.write_bytes(bytes(chunk_path.stat().st_size))
    manifest_path.write_bytes(b"{")

    reopened = _chunked_store(tmp_path / "state")
    assert reopened.save({"kv": array}, {"step": 1}) == descriptor
    assert reopened.counters["backing_repairs"] == 2
    restored, metadata = _chunked_store(tmp_path / "state").load(descriptor)
    assert metadata == {"step": 1}
    assert restored["kv"].tobytes() == array.tobytes()


def test_prune_reclaims_exclusive_chunks_and_keeps_shared_ones(tmp_path):
    store = SnapshotStore(
        tmp_path / "state",
        chunk_bytes=256,
        chunk_threshold_bytes=128,
        retain_generations=2,
    )
    shared = np.arange(768, dtype=np.uint8)
    descriptors = []
    for step in range(4):
        changing = np.full(768, step, dtype=np.uint8)
        descriptors.append(store.save({"shared": shared, "changing": changing}, {"step": step}))

    assert len(list(store.snapshots.glob("*.json"))) == 2
    with pytest.raises(SnapshotCorruptionError):
        store.load(descriptors[0])

    restored, metadata = store.load(descriptors[-1])
    assert metadata == {"step": 3}
    assert restored["shared"].tobytes() == shared.tobytes()
    assert restored["changing"].tobytes() == np.full(768, 3, dtype=np.uint8).tobytes()

    # The chunks two retained manifests share must survive exactly once,
    # and no chunk that only a removed manifest referenced remains.
    remaining_chunks = {path.name for path in store.chunks.glob("*.bin")}
    expected_chunks = {
        chunk["sha256"] + ".bin"
        for descriptor in descriptors[-2:]
        for array in _manifest(store, descriptor)["arrays"].values()
        for chunk in array["chunks"]
    }
    assert remaining_chunks == expected_chunks


def test_prune_reclaims_chunks_a_loaded_page_still_holds(tmp_path):
    """A loaded page whose chunks prune emptied is rewritten, not called corrupt."""

    store = SnapshotStore(
        tmp_path / "state",
        chunk_bytes=256,
        chunk_threshold_bytes=128,
        retain_generations=1,
    )
    page = np.arange(1024, dtype=np.uint8)
    first = store.save({"page": page}, {"step": 0})
    held, _metadata = store.load(first)
    retired = _manifest(store, first)["arrays"]["page"]["chunks"]

    for step in range(1, 4):
        store.save({"page": np.full(1024, step, dtype=np.uint8)}, {"step": step})
    for chunk in retired:
        assert not (store.root / chunk["blob"]).exists()

    descriptor = store.save({"page": held["page"]}, {"step": 4}, reuse_immutable_arrays=True)

    restored, metadata = store.load(descriptor)
    assert metadata == {"step": 4}
    assert restored["page"].tobytes() == page.tobytes()


def test_deferred_eviction_publishes_bytes_a_sealed_snapshot_still_names(tmp_path, monkeypatch):
    """A deferred snapshot seals even when its arrays outlive the in-memory cap."""

    monkeypatch.setattr(state_backing, "_DEFERRED_ARRAY_LIMIT", 2)
    store = SnapshotStore(tmp_path / "state", retain_generations=4)
    arrays: dict[str, np.ndarray] = {}
    for step in range(6):
        array = np.full(64, step + 1, dtype=np.uint8)
        array.setflags(write=False)
        arrays[f"layer.{step}"] = array
        store.save(dict(arrays), {"step": step}, reuse_immutable_arrays=True,
                   durable=False, defer_publication=True)

    sealed = store.save(dict(arrays), {"step": 6}, reuse_immutable_arrays=True,
                        durable=False, defer_publication=True)
    assert store.counters["deferred_evictions"] > 0
    assert store.make_durable(sealed) == sealed

    restored, metadata = SnapshotStore(tmp_path / "state").load(sealed)
    assert metadata == {"step": 6}
    for name, array in arrays.items():
        assert restored[name].tobytes() == array.tobytes()


def test_pruned_blob_is_republished_when_a_later_deferred_snapshot_names_it(tmp_path):
    """A swept backing stops counting as published, so the next seal rewrites it."""

    store = SnapshotStore(tmp_path / "state", retain_generations=1)
    page = np.arange(64, dtype=np.uint8)
    page.setflags(write=False)
    first = store.save({"page": page}, {"step": 0})
    blob = store.root / _manifest(store, first)["arrays"]["page"]["blob"]
    assert blob.exists()

    store.save({"other": np.full(64, 9, dtype=np.uint8)}, {"step": 1})
    assert not blob.exists()

    sealed = store.save({"page": page}, {"step": 2}, reuse_immutable_arrays=True,
                        durable=False, defer_publication=True)
    assert not blob.exists()
    assert store.make_durable(sealed) == sealed
    assert blob.exists()

    restored, metadata = SnapshotStore(tmp_path / "state").load(sealed)
    assert metadata == {"step": 2}
    assert restored["page"].tobytes() == page.tobytes()


def test_deferred_save_reuses_the_digest_of_an_unchanged_read_only_array(tmp_path):
    """A later deferred save of the same read-only array skips rehashing it."""

    store = SnapshotStore(tmp_path / "state", retain_generations=4)
    state = np.arange(64, dtype=np.uint8)
    state.setflags(write=False)
    step = np.arange(64, dtype=np.uint8)
    step.setflags(write=False)

    first = store.save({"state": state, "step": step}, {"step": 0}, durable=False,
                       defer_publication=True)
    changed = np.full(64, 5, dtype=np.uint8)
    changed.setflags(write=False)
    second = store.save({"state": state, "step": changed}, {"step": 1}, durable=False,
                        defer_publication=True)

    assert store.counters["deferred_digest_reuses"] == 1
    assert store.make_durable(second) == second
    restored, metadata = SnapshotStore(tmp_path / "state").load(second)
    assert metadata == {"step": 1}
    assert restored["state"].tobytes() == state.tobytes()
    assert restored["step"].tobytes() == changed.tobytes()
    assert first["snapshot_sha256"] != second["snapshot_sha256"]
