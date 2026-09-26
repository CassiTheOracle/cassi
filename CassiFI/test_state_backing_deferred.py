import json

import numpy as np

from programs.model import state_backing
from programs.model.state_backing import SnapshotStore


def _store(path):
    return SnapshotStore(path, chunk_bytes=1 << 20, chunk_threshold_bytes=1 << 20)


def _frozen(array):
    """Match the executor's publication contract: arrays are read-only."""
    frozen = np.array(array, copy=True, order="C")
    frozen.setflags(write=False)
    return frozen


def test_deferred_publication_writes_one_set_of_bytes_and_reopens_them(tmp_path):
    root = tmp_path / "state"
    store = _store(root)
    key = _frozen(np.arange(512, dtype=np.float32).reshape(16, 32))
    value = _frozen(np.arange(256, dtype=np.uint16))
    metadata = {"token": 7, "stage": "decode"}

    # Stage 1: the manifest and both arrays stay in memory.
    first = store.save(
        {"key": key, "value": value},
        metadata,
        reuse_immutable_arrays=True,
        durable=False,
        defer_publication=True,
    )
    assert set(first) == {"manifest", "schema", "snapshot_sha256"}
    assert not (root / first["manifest"]).exists()
    assert not list((root / "blobs").glob("*.bin"))
    assert store.counters["manifest_writes"] == 0
    assert store.counters["blob_writes"] == 0
    assert store.counters["deferred_snapshots"] == 1
    assert store.counters["deferred_arrays"] == 2

    # The deferred snapshot loads from its pending bytes, bit for bit.
    pending, pending_metadata = store.load(first)
    assert pending_metadata == metadata
    assert pending["key"].tobytes() == key.tobytes()
    assert pending["value"].tobytes() == value.tobytes()

    # Stage 2: the writer reuses both arrays unchanged, so the new
    # descriptor names the same content and still publishes nothing.
    second = store.save(
        pending,
        {"token": 8, "stage": "decode"},
        reuse_immutable_arrays=True,
        durable=False,
        defer_publication=True,
    )
    assert second["snapshot_sha256"] != first["snapshot_sha256"]
    assert not (root / second["manifest"]).exists()
    assert store.counters["manifest_writes"] == 0
    assert store.counters["blob_writes"] == 0

    # Sealing writes exactly the arrays and manifest the descriptor names.
    sealed = store.make_durable(second)
    assert sealed["snapshot_sha256"] == second["snapshot_sha256"]
    assert (root / sealed["manifest"]).exists()
    assert store.counters["manifest_writes"] == 1
    assert store.counters["blob_writes"] == 2
    assert json.loads((root / "CURRENT").read_text("utf-8")) == sealed

    # A fresh process reads the sealed snapshot from the file system.
    reopened = _store(root)
    restored, restored_metadata = reopened.load(sealed)
    assert restored_metadata == {"token": 8, "stage": "decode"}
    assert restored["key"].tobytes() == key.tobytes()
    assert restored["value"].tobytes() == value.tobytes()

    # Re-materializing the same bytes rewrites nothing and keeps the digest.
    third = reopened.save(
        restored,
        restored_metadata,
        reuse_immutable_arrays=True,
        durable=False,
        defer_publication=True,
    )
    reopened.make_durable(third)
    assert third == sealed
    assert reopened.counters["blob_writes"] == 0
    assert reopened.counters["manifest_reuses"] == 1


def test_mutation_between_stages_republishes_only_the_changed_array(tmp_path):
    root = tmp_path / "state"
    store = _store(root)
    key = _frozen(np.zeros((8, 8), dtype=np.float32))
    value = _frozen(np.ones(64, dtype=np.float32))
    first = store.save(
        {"key": key, "value": value},
        {"step": 1},
        reuse_immutable_arrays=True,
        durable=False,
        defer_publication=True,
    )
    store.make_durable(first)
    loaded, loaded_metadata = store.load(first)

    changed = np.array(loaded["key"], copy=True)
    changed[0, 0] = 5.0
    changed.setflags(write=False)
    writes_before = store.counters["blob_writes"]
    second = store.save(
        {"key": changed, "value": loaded["value"]},
        {"step": 2},
        reuse_immutable_arrays=True,
        durable=False,
        defer_publication=True,
    )
    # The unchanged array still resolves through the known-durable path.
    assert store.counters["blob_writes"] == writes_before
    store.make_durable(second)
    assert store.counters["blob_writes"] == writes_before + 1

    restored, restored_metadata = _store(root).load(second)
    assert restored_metadata == {"step": 2}
    assert restored["key"].tobytes() == changed.tobytes()
    assert restored["value"].tobytes() == value.tobytes()


def test_unsealed_deferred_snapshot_yields_to_discard(tmp_path):
    root = tmp_path / "state"
    store = _store(root)
    array = _frozen(np.arange(32, dtype=np.float32))
    descriptor = store.save(
        {"layer": array},
        {"step": 1},
        reuse_immutable_arrays=True,
        durable=False,
        defer_publication=True,
    )
    store.discard_deferred()
    assert not (root / descriptor["manifest"]).exists()
    try:
        store.load(descriptor)
    except state_backing.SnapshotCorruptionError:
        pass
    else:
        raise AssertionError("a discarded deferred snapshot must not load")
