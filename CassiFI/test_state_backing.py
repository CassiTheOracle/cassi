import json

import numpy as np
import pytest

from programs.model.state_backing import (
    SnapshotCorruptionError,
    SnapshotStore,
)


def test_prune_retains_generation_window_and_reclaims_exclusive_backings(tmp_path):
    store = SnapshotStore(tmp_path / "state", retain_generations=3, retain_bytes=1 << 30)
    descriptors = []
    for step in range(6):
        array = np.full(256, step, dtype=np.uint8)
        descriptors.append(store.save({"stage": array}, {"step": step}))

    # The newest 3 generations, and CURRENT, still resolve bit-for-bit.
    for step, descriptor in zip(range(3, 6), descriptors[3:]):
        restored, metadata = store.load(descriptor)
        assert metadata == {"step": step}
        assert restored["stage"].tobytes() == bytes([step]) * 256
    assert json.loads(store.current.read_text("utf-8")) == descriptors[-1]
    assert len(list(store.snapshots.glob("*.json"))) == 3
    assert len(list(store.blobs.glob("*.bin"))) == 3

    # Superseded manifests and their exclusive backings are gone.
    for descriptor in descriptors[:3]:
        assert not (store.root / descriptor["manifest"]).exists()
        with pytest.raises(SnapshotCorruptionError):
            store.load(descriptor)


def test_prune_keeps_a_backing_shared_between_a_retained_and_a_removed_snapshot(tmp_path):
    store = SnapshotStore(tmp_path / "state", retain_generations=2, retain_bytes=1 << 30)
    shared = np.arange(128, dtype=np.uint8)
    first = store.save({"shared": shared, "tag": np.array([0], dtype=np.uint8)}, {"step": 0})
    for step in range(1, 3):
        latest = store.save({"shared": shared, "tag": np.array([step], dtype=np.uint8)}, {"step": step})

    # The snapshot that first published the shared blob is outside the window...
    with pytest.raises(SnapshotCorruptionError):
        store.load(first)
    # ...but the blob it shares with a retained snapshot was not reclaimed.
    manifest = json.loads((store.root / latest["manifest"]).read_text("utf-8"))
    shared_blob = store.root / manifest["arrays"]["shared"]["blob"]
    assert shared_blob.exists()
    restored, metadata = store.load(latest)
    assert metadata == {"step": 2}
    assert restored["shared"].tobytes() == shared.tobytes()


def test_prune_keep_protects_a_snapshot_outside_the_window(tmp_path):
    store = SnapshotStore(tmp_path / "state", retain_generations=64, retain_bytes=1 << 30)
    protected = store.save({"stage": np.zeros(64, dtype=np.uint8)}, {"step": 0})
    for step in range(1, 4):
        store.save({"stage": np.full(64, step, dtype=np.uint8)}, {"step": step})

    result = store.prune(keep=(protected["snapshot_sha256"],), generations=2, max_bytes=1 << 30)

    assert protected["snapshot_sha256"] in result["kept"]
    restored, metadata = store.load(protected)
    assert metadata == {"step": 0}
    assert restored["stage"].tobytes() == bytes(64)


def test_prune_reports_freed_bytes_and_ran_backing_gc(tmp_path):
    store = SnapshotStore(tmp_path / "state", retain_generations=2, retain_bytes=1 << 30)
    for step in range(5):
        # ``durable=False`` skips the automatic prune call inside ``save`` so
        # every superseded manifest and blob is still present for one
        # explicit ``prune`` call to reclaim in a single measured pass.
        store.save({"stage": np.full(4096, step, dtype=np.uint8)}, {"step": step}, durable=False)
    writes_before = store.counters["snapshots_pruned"]

    result = store.prune()

    assert result["backing_gc"] == "ran"
    assert result["freed_bytes"] > 0
    assert result["removed_backings"] > 0
    assert len(result["removed_manifests"]) == 3
    assert store.counters["snapshots_pruned"] == writes_before + 3
    assert store.counters["backings_pruned"] == result["removed_backings"]
    assert store.counters["bytes_pruned"] == result["freed_bytes"]


def test_prune_reclaims_a_blob_a_retained_read_only_page_still_holds(tmp_path):
    """Reclaiming a page's backing makes the next save republish, not fail."""

    store = SnapshotStore(tmp_path / "state", retain_generations=1, retain_bytes=1 << 30)
    page = np.arange(512, dtype=np.uint8)
    page.setflags(write=False)
    first = store.save({"page": page}, {"step": 0}, reuse_immutable_arrays=True)
    manifest = json.loads((store.root / first["manifest"]).read_text("utf-8"))
    blob = store.root / manifest["arrays"]["page"]["blob"]
    assert blob.exists()

    for step in range(1, 4):
        store.save({"page": np.full(512, step, dtype=np.uint8)}, {"step": step})
    assert not blob.exists()

    syncs_before = store.counters["durability_syncs"]
    descriptor = store.save({"page": page}, {"step": 4}, reuse_immutable_arrays=True)

    # The rewritten page and its manifest are both flushed before the pointer
    # that names them.
    assert store.counters["durability_syncs"] >= syncs_before + 2
    restored, metadata = store.load(descriptor)
    assert metadata == {"step": 4}
    assert restored["page"].tobytes() == page.tobytes()


def test_prune_defers_a_backing_a_live_mapping_still_holds(tmp_path):
    """A reader's open mapping never turns a prune into a failed save."""

    store = SnapshotStore(tmp_path / "state", retain_generations=1, retain_bytes=1 << 30)
    page = np.arange(512, dtype=np.uint8)
    first = store.save({"page": page}, {"step": 0})
    manifest = json.loads((store.root / first["manifest"]).read_text("utf-8"))
    blob = store.root / manifest["arrays"]["page"]["blob"]
    mapped, _metadata = store.load(first)
    live = mapped["page"]

    for step in range(1, 4):
        store.save({"page": np.full(512, step, dtype=np.uint8)}, {"step": step})

    # Windows refuses to unlink a mapped file; the sweep reports it busy and
    # leaves the bytes for a later pass instead of failing the save.
    assert live.tobytes() == page.tobytes()
    if store.counters.get("backings_busy", 0):
        assert blob.exists()

    del live
    mapped.pop("page")
    store.prune()
    assert not blob.exists()
