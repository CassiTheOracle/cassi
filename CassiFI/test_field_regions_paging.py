"""Paged regional execution: parity, bounds, waits, and identity.

These checks fix the Section 18 (directed circulation and demand-paged
execution) contract for the regional machine: a transition over bounded
pages must produce the same committed image as the dense machine, a
predecessor must survive any abandoned transition, a residency miss must be
a typed resumable wait rather than a silent allocation, and page identity
must be verifiable without reconstructing the whole image.
"""

from __future__ import annotations

import numpy as np
import pytest

import cassi_field_regions as regions
from cassi_field_storage import ObjectOverlay, ObjectSubset
from cassi_page_tier_store import PageTierStore
from cassi_field_regions import (
    KernelCatalog,
    KernelResult,
    PageUnavailable,
    PagedFieldImage,
    RegionalFieldError,
    RegionalProfile,
    ResidencyWait,
    initial_field,
    inspect_paged_image,
    migrate_flat_to_paged,
    migrate_paged_layout,
    named_values_paged,
    run_paged_image,
    state_sha256,
    step_field,
    step_paged_image,
    validate_paged_delta,
    validate_paged_image,
)

FAULT_KERNEL = "paging-probe-fault"


def faulting_kernel(state, arguments, quantum) -> KernelResult:  # noqa: ANN001
    raise RegionalFieldError("probe kernel refused the transition")


COUNTING_KERNEL = "paging-probe-count"


def counting_kernel(state, arguments, quantum) -> KernelResult:  # noqa: ANN001
    value = int(arguments.get("value", 0))
    return KernelResult(
        state={"count": int(state.get("count", 0)) + value},
        output={"count": int(state.get("count", 0)) + value},
        work=1,
    )


def copy_program(length: int = 3):
    """A short program with one yield per instruction and a final halt."""

    rows = [
        {
            "op": "COPY",
            "source": "src",
            "target": "dst",
            "next": index + 1,
        }
        for index in range(length)
    ]
    rows.append({"op": "HALT"})
    return tuple(rows)


def long_program(instructions: int = 600):
    return tuple(
        {"op": "YIELD", "next": index + 1} for index in range(instructions)
    ) + ({"op": "HALT"},)


def seeded(program, **kwargs):
    profile = kwargs.pop("profile", None) or RegionalProfile()
    catalog = kwargs.pop("catalog", None) or regions.EMPTY_KERNEL_CATALOG
    values = kwargs.pop("values", {"src": {"k": 5}, "dst": None})
    capacities = kwargs.pop("value_capacities", {"dst": 32})
    return (
        initial_field(
            profile,
            program,
            catalog=catalog,
            values=values,
            value_capacities=capacities,
        ),
        profile,
        catalog,
    )


def dense_run(field, profile, catalog, steps: int):
    receipts = []
    current = np.array(field, copy=True)
    for _ in range(steps):
        current, receipt = step_field(current, profile, catalog)
        receipts.append(receipt)
    return current, receipts


def paged_run(field, profile, catalog, steps: int, **kwargs):
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    receipts = []
    for _ in range(steps):
        image, receipt = step_paged_image(image, catalog=catalog, **kwargs)
        receipts.append(receipt)
    return image, receipts


def test_paged_transition_matches_the_dense_image_byte_for_byte() -> None:
    field, profile, catalog = seeded(copy_program(5))
    bounded_limit = 8
    dense, dense_receipts = dense_run(field, profile, catalog, 7)
    image, paged_receipts = paged_run(
        field,
        profile,
        catalog,
        7,
        resident_limit=bounded_limit,
        record_audit_digest=True,
    )

    assert np.array_equal(image.materialise(), dense)
    assert image.audited_state_sha256 == state_sha256(dense, profile)
    for dense_receipt, paged_receipt in zip(dense_receipts, paged_receipts):
        assert dense_receipt["kind"] == paged_receipt["kind"]
        assert dense_receipt["status"] == paged_receipt["status"]
        assert dense_receipt.get("logical_transition") == paged_receipt.get(
            "logical_transition"
        )
        assert dense_receipt.get("disposition") == paged_receipt.get("disposition")
    assert paged_receipts[0]["commit"]["changed_pages"]
    assert len(paged_receipts[0]["commit"]["changed_pages"]) < image.page_count
    assert named_values_paged(image, ["dst"]) == {"dst": {"k": 5}}


def test_unverifiable_paged_delta_is_rejected() -> None:
    field, profile, catalog = seeded(copy_program(2))
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    successor, receipt = step_paged_image(image, catalog=catalog)
    validated = validate_paged_delta(
        image, successor, changed_pages=receipt["commit"]["changed_pages"]
    )
    assert validated["changed_pages"] == list(receipt["commit"]["changed_pages"])

    staging = image.stage(stage="overlap-probe")
    view = staging.view()
    first, second = 1, 2
    row_first = regions.HEADER_WORDS + (first - 1) * regions.DIRECTORY_WORDS
    row_second = regions.HEADER_WORDS + (second - 1) * regions.DIRECTORY_WORDS
    base = int(view[row_first + regions.D_BASE])
    capacity = int(view[row_first + regions.D_CAPACITY])
    assert int(view[row_second + regions.D_FLAGS]) & regions.FLAG_LIVE
    view[row_second + regions.D_BASE] = base + capacity - 1
    broken, _record = staging.commit()
    with pytest.raises(RegionalFieldError, match="overlap"):
        validate_paged_delta(image, broken, changed_pages=(0,))


def test_predecessor_survives_a_faulting_transition() -> None:
    catalog = KernelCatalog(
        {FAULT_KERNEL: faulting_kernel}, {FAULT_KERNEL: 8}
    )
    profile = RegionalProfile(kernel_names=catalog.names)
    program = (
        {
            "op": "NATIVE",
            "kernel": FAULT_KERNEL,
            "state": "probe",
            "output": "outcome",
            "next": 1,
        },
        {"op": "HALT"},
    )
    field = initial_field(
        profile,
        program,
        catalog=catalog,
        values={"probe": {"count": 0}, "outcome": None},
        value_capacities={"outcome": 16},
    )
    dense, dense_receipts = dense_run(field, profile, catalog, 2)
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    pre, pre_root = image, image.root_sha256
    frozen = image.materialise()
    paged_receipts = []
    for _ in range(2):
        image, receipt = step_paged_image(image, catalog=catalog)
        paged_receipts.append(receipt)

    assert dense_receipts[0]["kind"] == paged_receipts[0]["kind"]
    assert dense_receipts[0]["status"] == paged_receipts[0]["status"]
    assert np.array_equal(image.materialise(), dense)
    assert image.predecessor["root_sha256"] == pre_root
    assert np.array_equal(pre.materialise(), frozen)


def test_faulted_kernel_leaves_the_predecessor_unchanged() -> None:
    catalog = KernelCatalog({FAULT_KERNEL: faulting_kernel}, {FAULT_KERNEL: 8})
    profile = RegionalProfile(kernel_names=catalog.names)
    program = (
        {
            "op": "NATIVE",
            "kernel": FAULT_KERNEL,
            "state": "probe",
            "output": "outcome",
            "next": 1,
        },
        {"op": "HALT"},
    )
    field = initial_field(
        profile,
        program,
        catalog=catalog,
        values={"probe": {"count": 0}, "outcome": None},
        value_capacities={"outcome": 16},
    )
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    before_fields = list(image.directory.digests(profile))
    before = image.materialise()
    staging_probe = image.stage(stage="probe")
    probe_view = staging_probe.view()
    probe_view[regions.H_CLOCK] = 12345.0
    probe_view[regions.H_CLOCK + 1] = 0.0
    trial = staging_probe.spawn(stage="probe:trial")
    trial_view = trial.view()
    trial_view[regions.H_CLOCK + 1] = 7.0
    trial.discard()
    assert float(probe_view[regions.H_CLOCK + 1]) == 0.0
    staging_probe.discard()
    successor, _receipt = step_paged_image(image, catalog=catalog)
    assert np.array_equal(image.materialise(), before)
    assert list(image.directory.digests(profile)) == before_fields
    assert successor.root_sha256 != image.root_sha256


def test_residency_wait_is_typed_and_resumes_without_replaying_work() -> None:
    field, profile, catalog = seeded(long_program())
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    frozen_root = image.root_sha256
    frozen = image.materialise()

    waited, receipt = step_paged_image(image, catalog=catalog, resident_limit=1)
    assert receipt["kind"] == "residency-wait"
    assert waited is image
    wait = receipt["wait"]
    assert wait["reason"] == "resource"
    assert wait["pages"] and wait["remaining_allowance"] == 1
    continuation = receipt["continuation"]
    assert continuation["root_sha256"] == frozen_root
    assert continuation["kind"] == "paged-continuation"
    assert np.array_equal(image.materialise(), frozen)
    assert image.resident_limit == regions.DEFAULT_RESIDENT_PAGES

    dense, dense_receipts = dense_run(field, profile, catalog, 3)
    resumed, first = step_paged_image(image, catalog=catalog, resident_limit=64)
    assert first["kind"] == dense_receipts[0]["kind"]
    assert first["logical_transition"] == 1
    assert resumed.predecessor["root_sha256"] == frozen_root
    resumed, second = step_paged_image(resumed, catalog=catalog, resident_limit=64)
    assert second["logical_transition"] == 2
    resumed, third = step_paged_image(resumed, catalog=catalog, resident_limit=64)
    assert third["logical_transition"] == 3
    assert np.array_equal(resumed.materialise(), dense)


def test_bounded_run_never_exceeds_its_page_allowance() -> None:
    field, profile, catalog = seeded(long_program())
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    limit = 6
    receipts = []
    for _ in range(4):
        image, receipt = step_paged_image(
            image, catalog=catalog, resident_limit=limit
        )
        receipts.append(receipt)
    report = image.residency_report()
    assert report["resident_limit"] == limit
    assert report["resident_high_water_pages"] <= limit
    assert report["resident_pages"] <= limit
    assert report["implicit_zero_pages"] >= 0
    assert report["committed_pages"] <= report["page_count"]
    assert all(receipt["kind"] == "regional-transition" for receipt in receipts)


def test_segments_cover_used_words_without_reserved_capacity_pages() -> None:
    profile = RegionalProfile(mode_count=65_536)
    field, profile, catalog = seeded(
        copy_program(1),
        profile=profile,
        value_capacities={"dst": 200_000},
    )
    directory_words = regions._directory(field.reshape(-1), profile)
    row = next(
        row
        for row in directory_words
        if int(row[regions.D_KIND]) == regions.KIND_VALUE
        and int(row[regions.D_CAPACITY]) == 200_000
    )
    base = int(row[regions.D_BASE])
    used = int(row[regions.D_USED])
    capacity = int(row[regions.D_CAPACITY])
    assert used < capacity

    image, _record = migrate_flat_to_paged(
        field, profile=profile, catalog=catalog
    )
    value_pages = set(image.segments()["values"])
    first_reserved_page = (base + used + regions.PERSISTENCE_PAGE_WORDS - 1) // (
        regions.PERSISTENCE_PAGE_WORDS
    )
    last_reserved_page = (base + capacity - 1) // regions.PERSISTENCE_PAGE_WORDS
    reserved_page = (first_reserved_page + last_reserved_page) // 2
    assert reserved_page not in value_pages


def test_unchanged_pages_reuse_leaf_records_and_tree_nodes() -> None:
    field, profile, catalog = seeded(copy_program(4))
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    predecessor = image
    changed_roots = 0
    for _ in range(5):
        image, receipt = step_paged_image(image, catalog=catalog)
        commit = receipt["commit"]
        assert commit["tree_nodes_shared"] > 0
        assert image.tree == image.directory.tree(profile)
        assert len(commit["changed_pages"]) < image.page_count
        assert commit["objects_written"] <= len(commit["changed_pages"])
        live_objects = {
            leaf.object_sha256 for leaf in image.directory.leaves if leaf is not None
        }
        assert set(image.objects) == live_objects
        if commit["root_sha256"] != commit["predecessor_root_sha256"]:
            changed_roots += 1
    assert changed_roots >= 1
    assert image.root_sha256 != predecessor.root_sha256

    settled, noop = step_paged_image(image, catalog=catalog)
    assert noop["kind"] == "noop" and noop["state_unchanged"]
    assert settled.root_sha256 == image.root_sha256


def test_page_audit_path_verifies_and_rejects_a_tampered_sibling() -> None:
    field, profile, catalog = seeded(copy_program(3))
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    tree = image.tree
    for index in range(image.page_count):
        path = tree.audit_path(index)
        assert tree.verify_audit_path(index, path)
        tampered = list(path)
        tampered[0] = "0" * 64
        assert not tree.verify_audit_path(index, tuple(tampered))


def test_missing_or_corrupt_page_objects_are_typed_failures() -> None:
    field, profile, catalog = seeded(copy_program(3))
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    descriptor = image.descriptor(semantic={"kind": "paging-probe"})
    store = dict(image.object_store())
    key = next(iter(store))
    assert key in store

    without = {name: value for name, value in store.items() if name != key}
    with pytest.raises(PageUnavailable) as missing:
        torn = PagedFieldImage.from_descriptor(descriptor, without, catalog)
        torn.materialise()
    assert missing.value.kind == "missing"

    corrupted = dict(store)
    corrupted[key] = corrupted[key][:-1] + bytes([corrupted[key][-1] ^ 0x01])
    with pytest.raises(PageUnavailable) as corrupt:
        damaged = PagedFieldImage.from_descriptor(
            descriptor, corrupted, catalog, verify="none"
        )
        damaged.materialise()
    assert corrupt.value.kind == "corrupt"

def test_nvme_page_placement_survives_reopen_and_falls_back_to_canonical(
    tmp_path,
) -> None:
    field, profile, catalog = seeded(copy_program(3))
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    leaf = next(leaf for leaf in image.directory.leaves if leaf is not None)
    index = leaf.index
    tier_root = tmp_path / "nvme"
    store = PageTierStore(
        nvme_root=tier_root,
        limits={"nvme": 16 * 1024 * 1024},
        resource_manager=image.resource_manager,
    )
    original_root = image.root_sha256

    placed = image.place_pages([index], "nvme", tier_store=store, max_pages=1)
    assert placed["root_sha256"] == original_root
    assert placed["moved_pages"] == [index]
    assert placed["bytes"] == leaf.object_bytes
    assert image.resource_manager.report()["used_bytes"]["nvme"] == leaf.object_bytes

    receipt = store.lookup(
        "nvme",
        root_sha256=original_root,
        page_index=index,
        page_version=image.tree.digest(index),
        object_sha256=leaf.object_sha256,
    )
    assert receipt is not None
    assert store.get(receipt) == image.objects[leaf.object_sha256]

    image.release_resident()
    ram_before = image.resource_manager.report()["used_bytes"]["ram"]
    repeated = image.place_pages([index], "nvme", tier_store=store, max_pages=1)
    assert repeated["moved_pages"] == []
    assert repeated["bytes"] == 0
    assert image.resource_manager.report()["used_bytes"]["ram"] == ram_before
    assert image.resource_manager.report()["used_bytes"]["nvme"] == leaf.object_bytes

    image.page(0)
    assert 0 in image._pinned
    cold_leaf = next(
        candidate
        for candidate in image.directory.leaves
        if candidate is not None
        and candidate.index != index
        and candidate.index not in image._pinned
    )
    assert cold_leaf.index not in image._resident
    manager = image.resource_manager
    limits_before = manager.limits.as_dict()
    ram_before = manager.report()["used_bytes"]["ram"]
    full_limits = dict(limits_before)
    full_limits["ram_bytes"] = ram_before
    full_limits["auto_grow"] = False
    nvme_before = store.used_bytes("nvme")
    manager.reconfigure(full_limits)
    cold_placed = image.place_pages(
        [cold_leaf.index], "nvme", tier_store=store, max_pages=1
    )
    assert cold_placed["moved_pages"] == [cold_leaf.index]
    assert cold_placed["bytes"] == store.used_bytes("nvme") - nvme_before
    assert manager.report()["used_bytes"]["ram"] == ram_before
    assert cold_leaf.index not in image._resident
    assert 0 in image._resident
    image.release_resident()
    manager.reconfigure(limits_before)

    hdd_store = PageTierStore(
        hdd_root=tmp_path / "hdd",
        limits={"hdd": 16 * 1024 * 1024},
    )
    hdd_placed = image.place_pages([index], "hdd", tier_store=hdd_store, max_pages=1)
    assert hdd_placed["moved_pages"] == [index]
    assert hdd_placed["bytes"] == leaf.object_bytes
    hdd_receipt = hdd_store.lookup(
        "hdd",
        root_sha256=original_root,
        page_index=index,
        page_version=image.tree.digest(index),
        object_sha256=leaf.object_sha256,
    )
    assert hdd_receipt is not None
    assert hdd_store.get(hdd_receipt) == image.objects[leaf.object_sha256]

    stale_root = "0" * 64 if original_root != "0" * 64 else "1" * 64
    with pytest.raises(RegionalFieldError, match="root is stale"):
        image.place_pages(
            [index], "nvme", root_sha256=stale_root, tier_store=store
        )

    expected_page = image.page(index).copy()
    restarted_store = PageTierStore(
        nvme_root=tier_root,
        limits={"nvme": 16 * 1024 * 1024},
    )
    assert any(
        record.root_sha256 == original_root
        and record.page_index == index
        and record.page_version == image.tree.digest(index)
        and record.object_sha256 == leaf.object_sha256
        for record in restarted_store.recover()
    )
    canonical = dict(image.object_store())
    del canonical[leaf.object_sha256]
    reopened = PagedFieldImage.from_descriptor(
        image.descriptor(),
        canonical,
        catalog,
        verify="none",
        tier_store=restarted_store,
    )
    assert np.array_equal(reopened.page(index), expected_page)
    assert reopened.root_sha256 == original_root

    object_path = (
        restarted_store._object_root("nvme")
        / leaf.object_sha256[:2]
        / leaf.object_sha256
    )
    object_path.write_bytes(b"corrupt tier object")
    canonical_fallback = PagedFieldImage.from_descriptor(
        image.descriptor(),
        dict(image.object_store()),
        catalog,
        verify="none",
        tier_store=restarted_store,
    )
    assert np.array_equal(canonical_fallback.page(index), expected_page)


def test_ram_page_placement_is_resident_idempotent_and_rejects_fake_vram() -> None:
    field, profile, catalog = seeded(copy_program(3))
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    index = image.page_count - 1
    page_bytes = image.directory.page_words(profile.total_words, index) * 8

    with pytest.raises(RegionalFieldError, match="real GPU page executor"):
        image.place_pages([index], "vram")


    image.page(0)
    ram_before = image.resource_manager.report()["used_bytes"]["ram"]
    already_resident = image.place_pages([0], "ram")
    assert already_resident["moved_pages"] == []
    assert already_resident["bytes"] == 0
    assert image.resource_manager.report()["used_bytes"]["ram"] == ram_before
    first = image.place_pages([index], "ram", max_pages=1)
    assert first["moved_pages"] == [index]
    assert first["bytes"] == page_bytes
    used = image.resource_manager.report()["used_bytes"]["ram"]
    assert used >= page_bytes
    repeated = image.place_pages([index], "ram", max_pages=1)
    assert repeated["moved_pages"] == []
    assert repeated["bytes"] == 0
    assert image.resource_manager.report()["used_bytes"]["ram"] == used

    image.release_resident()
    assert image.resource_manager.report()["used_bytes"]["ram"] == 0
    continued = image.place_pages([index, index - 1], "ram", max_pages=1)
    assert continued["remaining_pages"] == [index - 1]
    continuation = continued["continuation"]
    assert continuation["remaining_pages"] == [index - 1]
    assert len(continuation["page_versions"]) == 1
    resumed = image.place_pages([], "ram", max_pages=1, continuation=continuation)
    assert resumed["moved_pages"] == [index - 1]
    assert resumed["remaining_pages"] == []


def test_descriptor_reopen_preserves_identity_and_is_demand_paged() -> None:
    field, profile, catalog = seeded(long_program())
    dense, _receipts = dense_run(field, profile, catalog, 1)
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    image, _receipt = step_paged_image(image, catalog=catalog, record_audit_digest=True)
    descriptor = image.descriptor(
        semantic={"kind": "paging-probe"},
        numerical={"family": "regional"},
    )
    reopened = PagedFieldImage.from_descriptor(
        descriptor, image.object_store(), catalog, resident_limit=4
    )
    assert reopened.root_sha256 == image.root_sha256
    assert reopened.audited_state_sha256 == image.audited_state_sha256
    inspection = inspect_paged_image(reopened)
    assert inspection["clock"] == 1
    assert inspection["residency"]["resident_pages"] <= 4
    assert np.array_equal(reopened.materialise(), dense)
    assert reopened.audited_state_sha256 == state_sha256(dense, profile)
    validate_paged_image(reopened)


def test_run_paged_image_stops_on_halt_and_reports_its_work() -> None:
    field, profile, catalog = seeded(copy_program(3))
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    final, summary = run_paged_image(image, catalog=catalog, steps=8)
    assert summary["stop"] == "settled"
    assert summary["steps"] >= 1
    assert summary["transitions"][-1]["status"] == "halted"
    dense, _receipts = dense_run(field, profile, catalog, summary["steps"])
    assert np.array_equal(final.materialise(), dense)


def test_residency_wait_during_a_run_is_reported_with_a_continuation() -> None:
    field, profile, catalog = seeded(long_program())
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    limited = image.with_resident_limit(1)
    halted, limited_summary = run_paged_image(limited, catalog=catalog, steps=4)
    assert limited_summary["stop"] == "wait"
    assert limited_summary["wait"]["reason"] == "resource"
    assert limited_summary["continuation"]["root_sha256"] == image.root_sha256
    assert halted.root_sha256 == image.root_sha256
    assert halted is limited


def test_staging_spills_within_its_declared_dirty_bound() -> None:
    field, profile, catalog = seeded(copy_program(3))
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    staging = regions.PagedFieldStaging(
        image, stage="spill-probe", dirty_limit=2
    )
    view = staging.view()
    touched = [0, 5, 9, 13, 17]
    for offset, index in enumerate(touched):
        view[index * regions.PERSISTENCE_PAGE_WORDS + 3] = 100 + offset
    assert len(staging.dirty) <= 2
    assert staging.spilled
    assert len(staging.changed_pages()) == len(touched)
    successor, receipt = staging.commit(require_clean=True)
    assert receipt["changed_pages"] == sorted(touched)
    flat = successor.materialise().reshape(-1)
    for offset, index in enumerate(touched):
        assert int(flat[index * regions.PERSISTENCE_PAGE_WORDS + 3]) == 100 + offset

def test_vector_page_writes_preserve_order_for_unsorted_duplicate_offsets() -> None:
    field, profile, catalog = seeded(copy_program(1))
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    staging = image.stage(stage="ordered-vector-write")
    offsets = np.asarray(
        [
            17 * regions.PERSISTENCE_PAGE_WORDS + 3,
            4,
            17 * regions.PERSISTENCE_PAGE_WORDS + 3,
            9 * regions.PERSISTENCE_PAGE_WORDS + 9,
            4,
        ],
        dtype=np.int64,
    )

    staging.stage_words(offsets, [7, 11, 13, 17, 19])
    successor, _receipt = staging.commit(require_clean=True)
    flat = successor.materialise().reshape(-1)
    assert flat[offsets].tolist() == [13, 19, 13, 17, 19]



def test_layout_migration_binds_the_predecessor_identity() -> None:
    field, profile, catalog = seeded(copy_program(3))
    flat_digest = state_sha256(field, profile)
    image, record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    assert record["kind"] == "storage-only"
    assert record["predecessor"]["state_sha256"] == flat_digest
    assert record["successor"]["root_sha256"] == image.root_sha256
    assert record["logical_mapping"]["length"] == profile.total_words
    assert image.predecessor["state_sha256"] == flat_digest
    assert np.array_equal(image.materialise(), field)

    grown_raw = dict(profile.as_dict())
    grown_raw["mode_count"] = profile.mode_count * 2
    grown_profile = RegionalProfile.from_dict(grown_raw)
    assert grown_profile.directory_capacity == profile.directory_capacity
    shrink_raw = dict(profile.as_dict())
    shrink_raw["mode_count"] = 12000
    with pytest.raises(RegionalFieldError, match="cannot discard logical words"):
        migrate_paged_layout(image, RegionalProfile.from_dict(shrink_raw), catalog=catalog)
    grown, growth = migrate_paged_layout(image, grown_profile, catalog=catalog)
    assert growth["predecessor"]["root_sha256"] == image.root_sha256
    assert grown.predecessor["root_sha256"] == image.root_sha256
    assert grown.profile.total_words > image.profile.total_words
    before = image.materialise().reshape(-1)
    after = grown.materialise().reshape(-1)
    # Growth rebinds only the declared identity words; every logical word of
    # the predecessor, from the directory onward, is preserved verbatim.
    assert np.array_equal(
        after[regions.HEADER_WORDS: before.size],
        before[regions.HEADER_WORDS:],
    )
    assert int(after[regions.H_TOTAL_WORDS]) == grown_profile.total_words
    assert int(after[regions.H_DIRECTORY_CAPACITY]) == profile.directory_capacity
    validate_paged_image(grown)


def test_large_paged_successor_switches_to_content_bound_identity() -> None:
    profile = RegionalProfile(mode_count=30_000_000)
    page_count = (
        profile.total_words + regions.PERSISTENCE_PAGE_WORDS - 1
    ) // regions.PERSISTENCE_PAGE_WORDS
    assert page_count > regions.MAX_RESIDENCY_PAGES
    directory = regions.PageDirectory(profile.fingerprint, page_count, ())
    predecessor_digest = "a" * 64
    image = PagedFieldImage(
        profile,
        regions.EMPTY_KERNEL_CATALOG,
        directory,
        {},
        resident_limit=32,
        dirty_limit=8,
        audited_state_sha256=predecessor_digest,
    )

    successor = image.successor(
        directory, {}, transition={"kind": "regional-transition"}
    )
    assert successor.predecessor["state_sha256"] == predecessor_digest
    assert successor.state_sha256_kind == regions.PAGED_STATE_KIND_ROOT
    assert successor.state_identity_sha256() == regions.paged_root_state_sha256(
        profile, successor.root_sha256, page_count
    )


# -- Section 18.5: field-derived activity among eligible work -------------


def _contested_queue():
    """One root event and one admitted event competing for the automaton."""

    field, profile, catalog = seeded(copy_program(2))
    queued, _admission = regions.enqueue_event(
        field, profile, catalog, {"pc": 1, "site": 1}
    )
    return queued, profile, catalog


def _queue_rows(field, profile) -> list[tuple[int, int, int]]:
    queue = regions._read_region(
        field.reshape(-1), profile, regions._queue_ref(field.reshape(-1))
    )
    return sorted(
        (int(event["sequence"]), int(event["event_id"]), int(event["priority"]))
        for event in queue["events"]
    )


def test_activity_reorders_eligible_work_without_touching_eligibility() -> None:
    field, profile, catalog = _contested_queue()
    rows = _queue_rows(field, profile)
    assert [row[2] for row in rows] == [0, 0]
    baseline, baseline_receipt = step_field(field, profile, catalog)
    assert baseline_receipt["event_id"] == rows[0][1]
    assert "activity_modulation" not in baseline_receipt

    # The second candidate carries activity; the drive changes and the
    # automaton selects it.  Eligibility is byte-identical: the modulation
    # cannot make an ineligible candidate eligible.
    raised, raised_receipt = step_field(
        field,
        profile,
        catalog,
        activity={rows[1][0]: 1.0},
        activity_weight=regions.ACTIVITY_UNIT,
    )
    assert raised_receipt["event_id"] == rows[1][1]
    assert raised_receipt["eligibility_sha256"] == baseline_receipt["eligibility_sha256"]
    record = raised_receipt["activity_modulation"]
    assert record["schema"] == regions.ACTIVITY_SCHEMA
    assert record["applied"] == [
        {
            "sequence": rows[1][0],
            "activity": regions.ACTIVITY_UNIT,
            "factor": regions.ACTIVITY_MAX_FACTOR,
            "drive": 2,
        }
    ]
    assert record["unmatched"] == 1
    assert not np.array_equal(raised, baseline)

    # Declared weight zero, or no activity at all, is the existing rule.
    for kwargs in (
        {"activity": {rows[1][0]: 1.0}, "activity_weight": 0},
        {"activity": None, "activity_weight": regions.ACTIVITY_UNIT},
        {"activity": {}, "activity_weight": regions.ACTIVITY_UNIT},
    ):
        unchanged, unchanged_receipt = step_field(field, profile, catalog, **kwargs)
        assert np.array_equal(unchanged, baseline)
        assert unchanged_receipt["event_id"] == baseline_receipt["event_id"]
        assert unchanged_receipt["eligibility_sha256"] == baseline_receipt["eligibility_sha256"]
        assert "activity_modulation" not in unchanged_receipt


def test_activity_modulation_is_bounded_recorded_and_never_removes_drive() -> None:
    field, profile, catalog = seeded(copy_program(2))
    queued, _admission = regions.enqueue_event(
        field, profile, catalog, {"pc": 1, "site": 1, "priority": 3}
    )
    rows = _queue_rows(queued, profile)
    high = max(rows, key=lambda row: row[2])
    damped, receipt = step_field(
        queued,
        profile,
        catalog,
        activity={high[0]: -1.0},
        activity_weight=regions.ACTIVITY_UNIT,
    )
    applied = receipt["activity_modulation"]["applied"]
    assert applied == [
        {
            "sequence": high[0],
            "activity": -regions.ACTIVITY_UNIT,
            "factor": regions.ACTIVITY_MIN_FACTOR,
            "drive": 2,
        }
    ]
    assert applied[0]["drive"] >= 1
    assert receipt["event_id"] == high[1]
    assert not np.array_equal(damped, queued)

    # An out-of-range reading saturates at the declared bound instead of
    # selecting a different rule, and a non-finite reading is refused.
    saturated, saturated_receipt = step_field(
        queued,
        profile,
        catalog,
        activity={high[0]: 4.5},
        activity_weight=regions.ACTIVITY_UNIT,
    )
    assert saturated_receipt["activity_modulation"]["applied"][0]["activity"] == regions.ACTIVITY_UNIT
    assert regions.canonical_activity({high[0]: -9.0}) == {high[0]: -1.0}
    with pytest.raises(RegionalFieldError, match="not finite"):
        regions.canonical_activity({high[0]: float("nan")})
    with pytest.raises(RegionalFieldError, match="not numeric"):
        regions.canonical_activity({high[0]: "high"})
    with pytest.raises(RegionalFieldError, match="must be a mapping"):
        regions.canonical_activity([1, 2, 3])


def test_paged_activity_matches_dense_activity_byte_for_byte() -> None:
    field, profile, catalog = _contested_queue()
    rows = _queue_rows(field, profile)
    kwargs = {"activity": {rows[1][0]: 1.0}, "activity_weight": regions.ACTIVITY_UNIT}
    dense, dense_receipt = step_field(field, profile, catalog, **kwargs)
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    bounded, paged_receipt = step_paged_image(image, catalog=catalog, **kwargs)
    assert paged_receipt["event_id"] == dense_receipt["event_id"]
    assert (
        paged_receipt["activity_modulation"]
        == dense_receipt["activity_modulation"]
    )
    assert np.array_equal(bounded.materialise(), dense)

# -- Closed AWAIT dependencies and bounded prerequisite urgency ------------


def test_foreground_await_lends_to_its_writer_with_flat_paged_parity() -> None:
    profile = RegionalProfile()
    catalog = regions.EMPTY_KERNEL_CATALOG
    program = (
        {"op": "YIELD", "next": 0},
        {"op": "AWAIT", "target": "barrier", "next": 3},
        {"op": "WRITE", "target": "barrier", "value": {"status": "done"}, "next": 3},
        {"op": "HALT"},
    )
    field = initial_field(
        profile, program, catalog=catalog,
        values={"barrier": {"status": "pending"}},
        value_capacities={"barrier": 64},
    )
    field, waiting = regions.enqueue_event(
        field, profile, catalog, {"pc": 1, "site": 1, "priority": 6},
    )
    field, writer = regions.enqueue_event(
        field, profile, catalog, {"pc": 2, "site": 2, "priority": 0},
    )
    dense, receipt = step_field(field, profile, catalog)
    image, _ = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    paged, paged_receipt = step_paged_image(image, catalog=catalog)
    assert receipt["event_id"] == paged_receipt["event_id"] == writer["event_id"]
    assert receipt["await_analysis"]["lent_event_ids"] == [writer["event_id"]]
    assert receipt["await_analysis"]["blocked_event_ids"] == []
    assert waiting["event_id"] != writer["event_id"]
    assert np.array_equal(dense, paged.materialise())


def test_closed_await_cycle_is_reported_without_falsely_running_a_writer() -> None:
    profile = RegionalProfile()
    catalog = regions.EMPTY_KERNEL_CATALOG
    program = (
        {"op": "AWAIT", "target": "b", "next": 1},
        {"op": "WRITE", "target": "a", "value": {"status": "done"}, "next": 4},
        {"op": "AWAIT", "target": "a", "next": 3},
        {"op": "WRITE", "target": "b", "value": {"status": "done"}, "next": 4},
        {"op": "HALT"},
    )
    field = initial_field(
        profile, program, catalog=catalog,
        values={"a": {"status": "pending"}, "b": {"status": "pending"}},
        value_capacities={"a": 64, "b": 64},
    )
    field, second = regions.enqueue_event(
        field, profile, catalog, {"pc": 2, "site": 2, "priority": 3},
    )
    dense, receipt = step_field(field, profile, catalog)
    image, _ = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    paged, paged_receipt = step_paged_image(image, catalog=catalog)
    expected = [1, second["event_id"]]
    assert receipt["status"] == paged_receipt["status"] == "waiting"
    assert receipt["await_analysis"]["blocked_event_ids"] == expected
    assert paged_receipt["await_analysis"]["blocked_event_ids"] == expected
    assert receipt["kind"] == paged_receipt["kind"] == "no-ready-event"
    assert "event_id" not in receipt and "event_id" not in paged_receipt
    assert np.array_equal(dense, paged.materialise())


# -- Section 18.7: a residency wait is a canonical continuation ----------


def test_residency_wait_continuation_is_canonical_and_carries_identity() -> None:
    field, profile, catalog = seeded(long_program())
    image, _record = migrate_flat_to_paged(field, profile=profile, catalog=catalog)
    limited = image.with_resident_limit(1)
    _same, receipt = step_paged_image(limited, catalog=catalog, stage="run")
    assert receipt["kind"] == "residency-wait"
    continuation = regions.read_residency_continuation(receipt["continuation"])
    wait = receipt["wait"]
    assert continuation["stage"] == wait["stage"]
    assert continuation["root_sha256"] == image.root_sha256
    assert continuation["pages"] == wait["pages"]
    assert continuation["page_versions"] == wait["page_versions"]
    assert continuation["segments"] == wait["segments"]
    assert continuation["completed_work"] == wait["completed_work"]
    assert continuation["remaining_allowance"] == wait["remaining_allowance"]
    assert continuation["staging"] == receipt["continuation"]["staging"]
    # Page versions are the committed page identities of the suspended
    # request, and the declared segments name the layout regions it touches.
    assert continuation["page_versions"] == [
        image.tree.digest(index) for index in continuation["pages"]
    ]
    assert continuation["segments"]
    assert set(continuation["segments"]) <= set(regions.PAGE_SEGMENTS)

    # A continuation record is validated on read: tampering is refused.
    with pytest.raises(RegionalFieldError, match="invalid residency continuation keys"):
        regions.read_residency_continuation(
            {**continuation, "extra": 1}
        )
    with pytest.raises(RegionalFieldError, match="version count mismatch"):
        regions.read_residency_continuation(
            {**continuation, "page_versions": []}
        )
    with pytest.raises(RegionalFieldError, match="unsupported residency continuation"):
        regions.read_residency_continuation(
            {**continuation, "kind": "paged-fault"}
        )


def test_a_long_paged_run_holds_only_what_it_is_using() -> None:
    """A transition's pages and overlays leave when the transition ends.

    The manager's account is the memory the machine actually holds, so a run
    of hundreds of states must charge a flat working set: an account that
    climbs with the step count would spend a turn's budget on pages and
    overlays whose holders were dropped many steps earlier, and the field
    would meet a resource wait while its live state is a handful of pages.
    """

    field, profile, catalog = seeded(long_program(instructions=200))
    limit = 8
    image, _record = migrate_flat_to_paged(
        field, profile=profile, catalog=catalog, resident_limit=limit
    )
    manager = image.resource_manager
    page_bytes = int(image.directory.page_words(profile.total_words, 0) * 8)
    allowance = limit * page_bytes
    for _ in range(120):
        image, _receipt = step_paged_image(image, catalog=catalog)
        assert manager.report()["used_bytes"]["ram"] <= allowance
    # The run is real: pages were fetched through the cache it is charged for.
    assert image.counters["page_misses"] > 0


def test_paged_object_history_preserves_live_keys_and_precedence() -> None:
    class CountingStore(dict[str, bytes]):
        reads = 0

        def __getitem__(self, key: str) -> bytes:
            self.reads += 1
            return super().__getitem__(key)

    base = CountingStore(
        {"persistent": b"base", "revoked": b"old", "current": b"start"}
    )
    objects = ObjectSubset(base, set(base))
    for generation in range(24):
        recent = f"piece-{generation}"
        objects = ObjectSubset(
            ObjectOverlay(
                {"current": str(generation).encode(), recent: b"recent"},
                objects,
            ),
            {"persistent", "current", recent},
        )

    # Folding many immutable versions indexes owners; it never loads values.
    assert base.reads == 0
    assert set(objects) == {"persistent", "current", "piece-23"}
    assert len(objects) == 3
    assert objects["current"] == b"23"
    assert objects["persistent"] == b"base"
    assert "revoked" not in objects
    assert "piece-0" not in objects
    assert base.reads == 1

def test_paged_prefetch_is_bounded_reopenable_and_credited_only_on_use() -> None:
    field, profile, catalog = seeded(copy_program(3))
    original, _record = migrate_flat_to_paged(
        field, profile=profile, catalog=catalog
    )
    target = original.directory.leaves[-1].index
    assert original.page_count > 1
    descriptor = original.descriptor()
    objects = original.object_store()
    hint = original.page_read_hint([target])

    full = PagedFieldImage.from_descriptor(
        descriptor, objects, catalog, resident_limit=1, verify="none"
    )
    keep = target - 1 if target else 1
    full.page(keep)
    before_resident = set(full._resident)
    deferred = full.prefetch_pages(hint, max_pages=1)
    assert deferred["status"] == "deferred"
    assert deferred["deferred_pages"] == [
        {"index": target, "reason": "resident-limit"}
    ]
    assert set(full._resident) == before_resident
    assert full.residency_report()["resident_pages"] == 1

    unused = PagedFieldImage.from_descriptor(
        descriptor, objects, catalog, resident_limit=1, verify="none"
    )
    unused_receipt = unused.prefetch_pages(hint, max_pages=1)
    assert unused_receipt["status"] == "staged"
    assert unused.root_sha256 == original.root_sha256
    unused_settlement = unused.settle_prefetch(unused_receipt["prefetch_id"])
    assert unused_settlement["unused_pages"] == [target]
    assert unused.counters["prefetch_hits"] == 0
    assert unused.counters["unused_prefetch_misses"] == 1
    assert unused.residency_report()["pending_prefetches"] == 0

    reopened = PagedFieldImage.from_descriptor(
        descriptor, objects, catalog, resident_limit=1, verify="none"
    )
    staged = reopened.prefetch_pages(hint, max_pages=1)
    assert staged["prefetched_pages"] == [target]
    assert reopened.root_sha256 == original.root_sha256
    decode_count = reopened.counters["page_decodes"]
    view = reopened.view()
    offset = target * regions.PERSISTENCE_PAGE_WORDS
    first = view[offset]
    assert view[offset] == first
    assert reopened.counters["page_decodes"] == decode_count
    settled = reopened.settle_prefetch(staged["prefetch_id"])
    assert settled["used_pages"] == [target]
    assert settled["unused_pages"] == []
    assert reopened.counters["prefetch_hits"] == 1
    assert reopened.residency_report()["resident_pages"] <= 1
    assert reopened.residency_report()["resident_high_water_pages"] <= 1

    successor, _receipt = step_paged_image(original, catalog=catalog)
    stale_before = successor.residency_report()["resident_pages"]
    stale = successor.prefetch_pages(hint, max_pages=1)
    assert stale["status"] == "stale"
    assert stale["reason"] == "state-identity"
    assert stale["prefetched_pages"] == []
    assert successor.root_sha256 != original.root_sha256
    assert successor.residency_report()["resident_pages"] == stale_before


def test_bound_object_prefetch_uses_current_exact_object_pages() -> None:
    field, profile, catalog = seeded(copy_program(3))
    original, _record = migrate_flat_to_paged(
        field, profile=profile, catalog=catalog
    )
    bound, receipt = regions.bind_regional_method_values(
        original,
        profile,
        values={"prefetch_words": list(range(257))},
        u32_words=("prefetch_words",),
    )
    reference = receipt["objects"]["prefetch_words"]
    input_ref = {
        key: reference[key]
        for key in ("object_id", "object_version", "source_sha256")
    }
    first_word = reference["first_word"]
    word_count = reference["word_count"]
    expected_pages = list(
        range(
            first_word // regions.PERSISTENCE_PAGE_WORDS,
            (first_word + word_count - 1) // regions.PERSISTENCE_PAGE_WORDS + 1,
        )
    )
    before_root = bound.root_sha256
    stale_ref = {**input_ref, "object_version": input_ref["object_version"] + 1}
    with pytest.raises(RegionalFieldError, match="bound object version is stale"):
        regions.prefetch_bound_object_refs(bound, profile, [stale_ref], limit=2)
    assert bound.root_sha256 == before_root

    prefetch = regions.prefetch_bound_object_refs(
        bound, profile, [input_ref], limit=2
    )
    assert prefetch["root_sha256"] == before_root
    assert prefetch["bound_object_ids"] == [reference["object_id"]]
    assert prefetch["requested_pages"] == expected_pages[:2]

    flat_before = np.array(field, copy=True)
    with pytest.raises(RegionalFieldError, match="bound prefetch requires a paged image"):
        regions.prefetch_bound_object_refs(field, profile, [input_ref], limit=2)
    assert np.array_equal(field, flat_before)
