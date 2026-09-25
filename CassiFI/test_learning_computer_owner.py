"""Behavioral boundaries of computer execution in the canonical owner."""
from __future__ import annotations

import copy
import json
from dataclasses import replace
import threading
import time
from typing import Mapping
from unittest import mock

import pytest

from cassi_field_atlas import (
    AtlasState,
    FieldIntelligenceError,
    canonical_json_bytes,
)
from cassi_field_owner import (
    CapacityLimits,
    DeterministicWorldAdapter,
    FieldIntelligenceOwner,
    FieldIntelligenceSurface,
    RPC_SCHEMA,
    SourceInput,
    WorldAcknowledgment,
    _assessed_research_progress,
)
from cassi_field_program import (
    SCHEMA as STRUCTURED_SCHEMA,
    compile_structured_program,
    regional_scalar_state,
    semantic_program_payload,
)
from run_cassi_computer import main as computer_cli, program_arguments
from cassi_field_computer import ComputerProfile, FieldComputer
import cassi_field_regions as regions
from cassi_field_regions import RegionalFieldError, RegionalProfile, from_chunked_descriptor
from cassi_field_residency import ResourceLimits, ResidencyManager, ResourceWait
from cassi_learning_computer import LearningComputer, LearningComputerError
from cassi_regional_catalog import STANDARD_KERNEL_CATALOG
from programs.model.kernel import regional_kernel as model_kernel
from programs.model.records import build_model_package
from programs.model.runtime import RESIDENT_STAGE_RESULT_SCHEMA, advance as advance_model, initial_state as initial_model_state
from programs.runtime.kernel import regional_kernel as program_kernel, regional_state as initial_program_state


def call(owner, op, action, **arguments):
    return FieldIntelligenceSurface(owner).handle({
        "schema": RPC_SCHEMA, "request_id": op, "operation": "computer",
        "params": {"operation_id": op, "computer_id": "main", "action": action, "arguments": arguments},
    })["result"]

def computer_task(owner):
    return owner.state.computers[0].inspect()["task"]


def computer_policy_sha256(owner):
    return owner.state.computers[0].inspect()["policy_state_sha256"]


def test_existing_computer_adopts_paging_without_losing_work_or_replay(tmp_path):
    root = tmp_path / "field"
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "paging-configure", "configure", profile={
            "mode_count": 16_384, "max_steps": 128, "max_events": 256,
        })
        call(owner, "paging-load", "load", program=[[0, 0, 0, 0, 0]])
        task = computer_task(owner)
        dense_state = owner.state.computers[0].state_sha256
        migrated = call(owner, "paging-adopt", "adopt-paged", resident_pages=96)
        assert migrated["receipt"]["paged"] is True
        assert migrated["receipt"]["previous_state_sha256"] == dense_state
        assert computer_task(owner) == task
        state = owner.state.state_sha256
        replay = call(owner, "paging-adopt", "adopt-paged", resident_pages=96)
        assert replay["checkpoint_receipt"]["replayed"] is True
        assert owner.state.state_sha256 == state

    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.state_sha256 == state
        assert owner.state.computers[0].is_paged
        assert computer_task(owner) == task
        replay = call(owner, "paging-adopt", "adopt-paged", resident_pages=96)
        assert replay["checkpoint_receipt"]["replayed"] is True
        call(owner, "paging-advance", "advance", steps=1)
        assert computer_task(owner)["status"] == "halted"


def test_paged_computer_can_advance_with_physical_room_below_logical_size(tmp_path):
    class BoundedAdmission:
        def get_activity_status(self, _activity_id):
            return {"status": "not-admitted"}

        def acquire(self, _activity_id, *, resources, **_kwargs):
            if resources["peak_bytes"] > 12 * 1024 * 1024:
                raise ResourceWait(
                    "peak_bytes", resources["peak_bytes"], 12 * 1024 * 1024,
                    reason="successor-capacity",
                )
            return self

        def retire(self, _status):
            pass

    with FieldIntelligenceOwner(tmp_path / "field") as owner:
        call(owner, "bounded-configure", "configure", profile={
            "mode_count": 262_144, "max_steps": 128, "max_events": 256,
        })
        call(owner, "bounded-load", "load", program=[[0, 0, 0, 0, 0]])
        admission = BoundedAdmission()
        owner.set_physical_admission(admission)
        with pytest.raises(ResourceWait, match="peak_bytes"):
            owner.operate_computer(
                "bounded-dense-advance", computer_id="main",
                action="advance", arguments={"steps": 1},
            )
        owner.set_physical_admission(None)
        call(owner, "bounded-adopt", "adopt-paged", resident_pages=96)
        assert owner.state.computers[0].nbytes > 12 * 1024 * 1024
        owner.set_physical_admission(admission)
        owner.operate_computer(
            "bounded-paged-advance", computer_id="main",
            action="advance", arguments={"steps": 1},
        )
        assert computer_task(owner)["status"] == "halted"


@pytest.mark.parametrize("paged", [False, True])
def test_catalog_revision_recovers_dense_and_paged_work_with_original_audit(
    monkeypatch, paged: bool
) -> None:
    # The retained catalog predates RECEIVE; its profile and state identities
    # must be checked as a pair before the field can adopt the current catalog.
    try:
        with monkeypatch.context() as previous:
            previous.setattr(
                regions, "_CATALOG_OPERATIONS", regions._CATALOG_OPERATIONS[:-1]
            )
            RegionalProfile._catalog_sha256.cache_clear()
            RegionalProfile._fingerprint.cache_clear()
            regions._CATALOG_FINGERPRINT_CACHE.clear()
            profile = RegionalProfile(
                mode_count=16_384,
                max_steps=128,
                max_events=256,
                kernel_names=STANDARD_KERNEL_CATALOG.names,
            )
            machine = FieldComputer.regional(profile, catalog=STANDARD_KERNEL_CATALOG)
            dense = machine.initial(
                (
                    {"op": "COPY", "source": "input", "target": "output", "next": 1},
                    {"op": "HALT"},
                ),
                values={"input": {"token": 17}, "output": None},
            )
            field = machine.paged_state(dense, resident_limit=96)[0] if paged else dense
            record, objects = LearningComputer(
                "catalog-history", profile, field
            ).persistence_dict()
    finally:
        RegionalProfile._catalog_sha256.cache_clear()
        RegionalProfile._fingerprint.cache_clear()
        regions._CATALOG_FINGERPRINT_CACHE.clear()

    with pytest.raises(LearningComputerError):
        LearningComputer.from_persistence_dict(record, objects)
    corrupt = dict(objects)
    address = record["field"]["chunks"][0]["object_sha256"]
    corrupt[address] = bytes([corrupt[address][0] ^ 1]) + corrupt[address][1:]
    with pytest.raises(LearningComputerError):
        LearningComputer.from_persistence_dict(
            record, corrupt, accept_recorded_catalog=True
        )
    restored = LearningComputer.from_persistence_dict(
        record, objects, accept_recorded_catalog=True
    )
    assert restored.is_paged is paged
    values = (
        regions.named_values_paged(restored.field.image, ["input", "output"])
        if paged
        else regions.named_values(
            restored.field._field, restored.profile, STANDARD_KERNEL_CATALOG,
            ["input", "output"],
        )
    )
    assert values == {"input": {"token": 17}, "output": None}
    retained, _ = restored.persistence_dict()
    assert retained["field"]["catalog_sha256"] == STANDARD_KERNEL_CATALOG.fingerprint
    assert retained["field"]["profile_sha256"] == restored.profile.fingerprint

    altered = copy.deepcopy(record)
    altered["field"]["catalog_sha256"] = STANDARD_KERNEL_CATALOG.fingerprint
    altered["field"]["profile_sha256"] = "0" * 64
    with pytest.raises(LearningComputerError):
        LearningComputer.from_persistence_dict(
            altered, objects, accept_recorded_catalog=True
        )

def test_adoption_grows_for_page_count_not_large_logical_page_indexes(tmp_path):
    limits = CapacityLimits(
        max_workspace_bytes=128 * 1024 * 1024,
        max_state_bytes=128 * 1024 * 1024,
    )
    with FieldIntelligenceOwner(tmp_path / "field", limits=limits) as owner:
        call(owner, "wide-configure", "configure", profile={"mode_count": 1_000_000})
        row = owner.state.computers[0]
        task = {**row.inspect()["task"], "context": "x" * 2_000_000}
        field, _ = row._write_named_value("task", task)
        owner.state = replace(owner.state, computers=(replace(row, field=field),))

        migrated = call(owner, "wide-adopt", "adopt-paged", resident_pages=96)
        resident_limit = migrated["receipt"]["resident_limit"]
        assert 128 <= resident_limit <= 512
        assert computer_task(owner) == task

    with FieldIntelligenceOwner(tmp_path / "field", limits=limits) as owner:
        row = owner.state.computers[0]
        assert row.resident_limit == resident_limit
        assert computer_task(owner) == task


def test_a_resource_wait_while_validating_is_a_wait_not_an_invalid_image() -> None:
    """A read that cannot reserve must not be read as a corrupt image.

    The membrane finish publishes its successor through the constructor that
    validates it, and validating reads pages.  ResourceWait is a ValueError
    subclass, so the constructor's shape conversion reported the wait as an
    invalid regional computer image; the owner relabelled that as
    INVALID_COMPUTER and the entity above it reported an unavailable brain for a
    condition the request can simply wait out.
    """

    profile = RegionalProfile(
        mode_count=16_384,
        max_steps=128,
        max_events=256,
        kernel_names=STANDARD_KERNEL_CATALOG.names,
    )
    machine = FieldComputer.regional(profile, catalog=STANDARD_KERNEL_CATALOG)
    program = tuple(
        {"op": "COPY", "source": "input", "target": "output", "next": index + 1}
        for index in range(4)
    ) + ({"op": "HALT"},)
    dense = machine.initial(program, values={"input": {"token": 17}, "output": None})
    paged, _record = machine.paged_state(dense, resident_limit=4)
    computer = LearningComputer(computer_id="wait-image", profile=profile, field=paged)

    wait = ResourceWait("ram", 32_768, 0, kind="resident", reason="capacity")
    with mock.patch.object(FieldComputer, "validate_paged", side_effect=wait):
        with pytest.raises(ResourceWait) as raised:
            replace(computer, field=paged)
    assert raised.value is wait

    # The companion case: a shape failure is still an invalid image, so the
    # wait passthrough discriminates rather than disabling the conversion.
    with mock.patch.object(
        FieldComputer, "validate_paged", side_effect=TypeError("bad shape")
    ):
        with pytest.raises(LearningComputerError):
            replace(computer, field=paged)


def test_paged_resource_wait_releases_staged_pages_for_retry() -> None:
    profile = RegionalProfile(
        mode_count=16_384,
        max_steps=128,
        max_events=256,
        kernel_names=STANDARD_KERNEL_CATALOG.names,
    )
    machine = FieldComputer.regional(profile, catalog=STANDARD_KERNEL_CATALOG)
    dense = machine.initial(
        ({"op": "COPY", "source": "input", "target": "output", "next": 1}, {"op": "HALT"}),
        values={"input": {"token": 17}, "output": None},
    )
    paged, _ = machine.paged_state(dense, resident_limit=4)
    manager = ResidencyManager(ResourceLimits(auto_grow=False))
    image = paged.image.with_resource_manager(manager)
    root = image.root_sha256
    reserve = manager.reserve
    scratch_calls = 0

    def refuse_second_scratch(tier, byte_count, *, kind="resident", **kwargs):
        nonlocal scratch_calls
        if kind == "scratch":
            scratch_calls += 1
            if scratch_calls >= 2:
                raise ResourceWait(tier, byte_count, 0, kind=kind, reason="capacity")
        return reserve(tier, byte_count, kind=kind, **kwargs)

    with mock.patch.object(manager, "reserve", side_effect=refuse_second_scratch):
        with pytest.raises(ResourceWait):
            regions.step_paged_image(image)
    assert scratch_calls >= 2
    assert image.root_sha256 == root
    image.release_resident()
    assert manager.report()["used_bytes"]["ram"] == 0

    successor, receipt = regions.step_paged_image(image)
    assert receipt["kind"] == "regional-transition"
    assert successor.root_sha256 != root
    successor.release_resident()
    assert manager.report()["used_bytes"]["ram"] == 0


def test_resident_model_fused_resume_preserves_next_stage_and_token() -> None:
    source_sha = "a" * 64
    package = build_model_package(
        program_id="fused-model-token",
        architecture="qwen35moe",
        graph=[
            {"op": stage, "stage": stage, "parameters": {"source_sha256": source_sha}}
            for stage in ("qwen-embedding", "qwen-head")
        ],
        tensors={},
        tokenizer={"vocab_size": 32},
    )
    state = initial_model_state(
        package, prompt_tokens=[7], owner_id="main", member_id="member",
        lineage_id="lineage", operation_id="token", max_new_tokens=1,
        backend_policy="logical-cpu",
    )
    model_before = copy.deepcopy(state)
    direct = model_kernel(state, {}, 1)
    assert state == model_before
    scheduler = initial_program_state(
        owner_id="main", member_id="member", runtime_id="model-scheduler",
        imported_task=state, imported_kind="model", imported_task_id="task",
    )
    scheduler_before = copy.deepcopy(scheduler)
    scheduled = program_kernel(
        scheduler, {"operation": "advance-task", "task_id": "task", "quantum": 1}, 1
    )
    assert scheduler == scheduler_before
    # The scheduler publishes the model task with the graph-site policy
    # detached to the owner-held `model_policies` store (the block a later
    # dispatch re-attaches before the kernel runs), so the published state
    # matches the direct kernel result exactly except for that one block,
    # and the retained pointer must carry the same sites the direct state
    # shows.
    published = scheduled.state["tasks"]["task"]["state"]
    retained_sites = scheduled.state["model_policies"][source_sha]["graph_sites"]
    assert retained_sites == direct.state["resident_model"]["graph_sites"]
    # The published state is the direct kernel result with exactly the
    # detached graph-site block excised; the retained store above carries it.
    expected_resident = {
        key: value
        for key, value in direct.state["resident_model"].items()
        if key != "graph_sites"
    }
    assert published == {**direct.state, "resident_model": expected_resident}

    waiting, *_ = advance_model(state, {}, 1)
    for stage in ("qwen-embedding", "qwen-head"):
        operation_id = waiting["await_target"]
        request = waiting["operations"][operation_id]["request"]
        assert request["stage"] == stage
        result = {
            key: request[key]
            for key in ("operation_id", "source_sha256", "stage", "layer", "position", "request_sha256")
        }
        result.update(schema=RESIDENT_STAGE_RESULT_SCHEMA, snapshot={})
        if stage == "qwen-head":
            result.update(token=17, eog=False)

        resumed, _, resume_work, _, _ = advance_model(
            waiting,
            {"operation": "resume-resident-model", "operation_id": operation_id, "result": result},
            1,
        )
        if resumed["phase"] == "running":
            sequential, _, next_work, _, _ = advance_model(resumed, {}, 1)
        else:
            sequential, next_work = resumed, 0
        fused, _, fused_work, _, _ = advance_model(
            waiting,
            {
                "operation": "resume-resident-model-and-advance",
                "operation_id": operation_id,
                "result": result,
            },
            2,
        )
        assert fused == sequential
        assert fused_work == resume_work + next_work
        assert waiting["phase"] == "waiting"
        waiting = fused
    assert waiting["phase"] == "completed"
    assert waiting["generated_tokens"] == [17]


def test_resident_model_cycle_commits_exact_scheduler_result_once() -> None:
    source_sha = "b" * 64
    package = build_model_package(
        program_id="resident-cycle-equivalence",
        architecture="qwen35moe",
        graph=[
            {"op": stage, "stage": stage, "parameters": {"source_sha256": source_sha}}
            for stage in ("qwen-embedding", "qwen-head")
        ],
        tensors={},
        tokenizer={"vocab_size": 32},
    )
    model = initial_model_state(
        package, prompt_tokens=[7], owner_id="main", member_id="member",
        lineage_id="lineage", operation_id="token", max_new_tokens=1,
        backend_policy="logical-cpu",
    )
    task = initial_program_state(
        owner_id="main", member_id="member", runtime_id="model-scheduler",
        imported_task=model, imported_kind="model", imported_task_id="task",
    )
    row, _ = LearningComputer.initial("main").submit(
        kernel="field-program-runtime", state=task,
        arguments={"operation": "advance-task", "task_id": "task", "quantum": 1},
    )
    original = row.named_value("task")
    hot_cycle = row.begin_model_cycle("task")
    cold = row
    for stage in ("qwen-embedding", "qwen-head"):
        waiting = hot_cycle.runtime_state["tasks"]["task"]["state"]
        operation_id = waiting["await_target"]
        request = waiting["operations"][operation_id]["request"]
        assert request["stage"] == stage
        result = {
            key: request[key]
            for key in ("operation_id", "source_sha256", "stage", "layer", "position", "request_sha256")
        }
        result.update(schema=RESIDENT_STAGE_RESULT_SCHEMA, snapshot={})
        if stage == "qwen-head":
            result.update(token=17, eog=True)
        arguments = {
            "operation": "resume-resident-model-and-advance",
            "operation_id": operation_id,
            "result": result,
        }
        hot_cycle.advance(arguments=arguments, quantum=2)
        cold, _ = cold.invoke(
            arguments={
                "operation": "advance-task", "task_id": "task",
                "quantum": 2, "arguments": arguments,
            },
        )
    assert row.named_value("task") == original
    hot, receipt = hot_cycle.finish()
    assert hot.named_value("task") == cold.named_value("task")
    assert receipt["run"]["status"] == "completed"
    assert hot.named_value("task")["tasks"]["task"]["state"]["generated_tokens"] == [17]
    with pytest.raises(LearningComputerError):
        hot_cycle.finish()


def test_a_resource_wait_reaches_the_caller_as_a_wait(tmp_path):
    """Physical room is a wait, not an invalid request.

    The owner reports request-shape failures as INVALID_COMPUTER, and a
    ResourceWait is a ValueError subclass, so the conversion used to swallow
    it: a caller that only needed to wait was told its computer request was
    invalid, and the entity above it reported an unavailable brain for a
    condition the request can simply wait out.  A wait must also commit
    nothing, so the same operation can be dispatched again later.
    """

    root = tmp_path / "field"
    with FieldIntelligenceOwner(root) as owner:
        call(
            owner,
            "wait-configure",
            "configure",
            profile={"program_capacity": 16, "stack_capacity": 2, "max_steps": 100},
        )
        call(
            owner,
            "wait-load",
            "load",
            program=[[1, 0, 7, 1, 0], [0, 0, 0, 0, 0]],
        )
        before = owner.state.state_sha256
        row = owner.state.computers[0]
        wait = ResourceWait("ram", 32768, 19456, reason="capacity")
        with mock.patch.object(type(row), "invoke", side_effect=wait):
            with pytest.raises(ResourceWait) as raised:
                owner.operate_computer(
                    "wait-invoke",
                    computer_id="main",
                    action="invoke",
                    arguments={"arguments": {"operation": "consume"}, "steps": 1},
                )
        assert raised.value is wait
        assert owner.state.state_sha256 == before

        # The companion case: a request-shape failure is still reported as an
        # invalid computer, so the wait passthrough above discriminates rather
        # than disabling the conversion.
        with mock.patch.object(type(row), "invoke", side_effect=TypeError("bad shape")):
            with pytest.raises(FieldIntelligenceError) as invalid:
                owner.operate_computer(
                    "shape-invoke",
                    computer_id="main",
                    action="invoke",
                    arguments={"arguments": {"operation": "consume"}, "steps": 1},
                )
        assert invalid.value.code == "INVALID_COMPUTER"
        assert owner.state.state_sha256 == before


def test_owner_exhaustion_growth_restart_and_replay(tmp_path):
    root = tmp_path / "field"
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "configure", "configure", profile={"program_capacity": 16, "stack_capacity": 2, "max_steps": 100})
        call(owner, "load", "load", program=[[1, 0, 7, 1, 0], [1, 0, 7, 2, 0], [1, 0, 7, 3, 0], [0, 0, 0, 0, 0]])
        first = call(owner, "advance", "advance", steps=20)
        state = owner.state.computers[0].inspect()
        assert state["task"]["status"] == "exhausted"
        assert state["task"]["left"] == [7, 7]
        digest = owner.state.state_sha256
        policy = computer_policy_sha256(owner)
        replay = call(owner, "advance", "advance", steps=20)
        assert replay["receipt"] == first["receipt"]
        assert replay["checkpoint_receipt"] == {**first["checkpoint_receipt"], "replayed": True}
        assert owner.state.state_sha256 == digest
    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.state_sha256 == digest
        call(owner, "grow", "grow", stack_capacity=4)
        call(owner, "finish", "advance", steps=20)
        state = owner.state.computers[0].inspect()
        assert state["task"]["status"] == "halted"
        assert state["task"]["left"] == [7, 7, 7]
        assert computer_policy_sha256(owner) == policy
        restored = AtlasState.decode_bundle(owner.state.encode_bundle())
        assert restored.state_sha256 == owner.state.state_sha256
        assert restored.computers[0].inspect() == state


def test_computer_checkpoint_uses_verified_independent_chunks(tmp_path):
    root = tmp_path / "field"
    with FieldIntelligenceOwner(root) as owner:
        call(
            owner,
            "chunk-configure",
            "configure",
            profile={
                "program_capacity": 128,
                "stack_capacity": 128,
                "max_steps": 256,
            },
        )
        call(
            owner,
            "chunk-load",
            "load",
            program=[
                [1, 0, 7, 1, 0],
                [1, 0, 7, 2, 0],
                [0, 0, 0, 0, 0],
            ],
        )
        call(owner, "chunk-advance", "advance", steps=16)
        computer = owner.state.computers[0]
        descriptor, objects = computer.persistence_dict()
        field_descriptor = descriptor["field"]
        assert field_descriptor["schema"] == "cassifi.regional-page-chunks.v1"
        assert objects
        assert all(
            row["object_sha256"] in objects
            for row in field_descriptor["chunks"]
        )
        page_index = field_descriptor["chunks"][0]["index"]
        profile, pages = from_chunked_descriptor(
            field_descriptor,
            objects,
            STANDARD_KERNEL_CATALOG,
            page_indices=[page_index],
        )
        assert profile.fingerprint == computer.profile.fingerprint
        assert pages.shape[0] == 1
        assert pages.any()
        persisted_page, page_receipt = owner.read_computer_page(
            computer_id="main",
            page_index=page_index,
        )
        chunk_record = field_descriptor["chunks"][0]
        assert page_receipt["decoded_sha256"] == chunk_record["decoded_sha256"]
        assert page_receipt["object_sha256"] == chunk_record["object_sha256"]
        assert page_receipt["objects_read"] == 1
        assert page_receipt["physical_bytes_read"] == chunk_record["object_bytes"]
        assert len(persisted_page) == chunk_record["decoded_bytes"]

        occupied = {row["index"] for row in field_descriptor["chunks"]}
        page_count = (
            computer.profile.total_words + field_descriptor["page_words"] - 1
        ) // field_descriptor["page_words"]
        zero_page_index = next(index for index in range(page_count) if index not in occupied)
        zero_page, zero_receipt = owner.read_computer_page(
            computer_id="main",
            page_index=zero_page_index,
        )
        assert zero_receipt["zero_page"] is True
        assert zero_receipt["objects_read"] == 0
        assert not any(zero_page)
        storage = owner.memory_storage_diagnostics()
        assert storage["logical_computer_bytes"] == computer.profile.state_bytes
        assert storage["resident_regional_bytes"] == computer.profile.state_bytes
        assert storage["unique_physical_bytes"] > 0
        assert storage["checkpoint_growth_bytes"] > 0
        assert storage["shared_objects_with_predecessor"] > 0
        assert storage["recovery"] == {
            "protected_objects": storage["recovery"]["protected_objects"],
            "present_objects": storage["recovery"]["protected_objects"],
            "missing_objects": [],
            "current_owner_validated": True,
        }
        scrub_cursor = 0
        scrubbed = 0
        while True:
            scrub = owner.scrub_memory_storage(
                cursor=scrub_cursor,
                maximum=2,
            )
            assert scrub["status"] == "supported"
            assert scrub["failures"] == []
            scrubbed += scrub["checked_objects"]
            if scrub["next_cursor"] is None:
                break
            scrub_cursor = scrub["next_cursor"]
        assert scrubbed == storage["recovery"]["protected_objects"]

        corrupt = dict(objects)
        object_sha256 = field_descriptor["chunks"][0]["object_sha256"]
        corrupt[object_sha256] = bytes(
            [corrupt[object_sha256][0] ^ 1, *corrupt[object_sha256][1:]]
        )
        with pytest.raises(RegionalFieldError, match="missing or corrupt"):
            from_chunked_descriptor(
                field_descriptor,
                corrupt,
                STANDARD_KERNEL_CATALOG,
            )

        restored = AtlasState.decode_bundle(owner.state.encode_bundle())
        assert restored.state_sha256 == owner.state.state_sha256
        assert restored.computers[0].inspect() == computer.inspect()


def test_learning_is_persistent_exactly_once_and_frozen_on_request(tmp_path):
    source = {"kind": "circuit", "source": {
        "inputs": ["x"], "gates": [], "assertions": [["x", 1]], "relations": [], "clauses": [],
    }}
    root = tmp_path / "field"
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "configure", "configure", profile={"program_capacity": 16, "stack_capacity": 16, "max_steps": 100})
        initial = computer_policy_sha256(owner)
        result = call(owner, "solve", "solve", source=source, budget=300, method="conflict")
        assert result["receipt"]["status"] == "sat"
        learned = computer_policy_sha256(owner)
        assert learned != initial
        generation = owner.state.generation
        replay = call(owner, "solve", "solve", source=source, budget=300, method="conflict")
        assert replay["receipt"] == result["receipt"]
        assert replay["checkpoint_receipt"] == {**result["checkpoint_receipt"], "replayed": True}
        assert owner.state.generation == generation
        assert computer_policy_sha256(owner) == learned
    with FieldIntelligenceOwner(root) as owner:
        assert computer_policy_sha256(owner) == learned
        frozen = call(owner, "frozen", "solve", source=source, budget=300, learn=False)
        assert frozen["receipt"]["status"] == "sat"
        assert computer_policy_sha256(owner) == learned

def test_policy_explanation_is_field_derived_and_does_not_publish(tmp_path):
    source = {
        "kind": "circuit",
        "source": {
            "inputs": ["x"],
            "gates": [],
            "assertions": [["x", 1]],
            "relations": [],
            "clauses": [],
        },
    }
    root = tmp_path / "field"
    with FieldIntelligenceOwner(root) as owner:
        call(
            owner,
            "configure",
            "configure",
            profile={
                "program_capacity": 16,
                "stack_capacity": 16,
                "max_steps": 100,
            },
        )
        before = owner.state.state_sha256
        generation = owner.state.generation
        result = FieldIntelligenceSurface(owner).handle(
            {
                "schema": RPC_SCHEMA,
                "request_id": "explain",
                "operation": "inspect_computer_policy",
                "params": {
                    "computer_id": "main",
                    "source": source,
                    "budget": 16,
                },
            }
        )["result"]
        assert result["read_only"] is True
        assert result["inspection"]["selected_method"] == "conflict"
        assert result["inspection"]["selection"]["phase"] == "cold-start"
        assert result["state_sha256"] == before
        assert owner.state.state_sha256 == before
        assert owner.state.generation == generation

def test_structured_program_restart_reuses_field_heat_and_replays_exactly(tmp_path):
    document = {
        "schema": STRUCTURED_SCHEMA,
        "main": [
            {"op": "set_acc", "value": 0},
            {
                "op": "while_acc",
                "condition": {"not_equals": 3},
                "body": [{"op": "add_acc", "value": 1}],
            },
            {"op": "push_acc", "stack": "left"},
        ],
    }
    compiled = program_arguments(document)
    root = tmp_path / "field"
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "configure", "configure", profile={
            "program_capacity": len(compiled["program"]) + 4,
            "stack_capacity": 8,
            "max_steps": 1000,
        })
        call(owner, "load", "load", **compiled)
        last_run = None
        for cycle in range(9):
            last_run = call(owner, f"run-{cycle}", "advance", steps=1000)
            task = computer_task(owner)
            assert task["status"] == "halted"
            assert task["left"] == [3]
            if cycle < 8:
                call(owner, f"restart-{cycle}", "restart")
        assert last_run is not None
        specialization = last_run["receipt"]["specialization"]
        assert specialization["enabled"] is True
        assert specialization["derived_blocks"] >= 1
        assert specialization["block_invocations"] >= 1
        assert specialization["block_transitions"] >= 2
        assert specialization["derivation_deferred"] is False
        assert specialization["reason"] == "field-procedure-promoted"
        observations = sum(computer_task(owner)["pc_observations"])
        restart = call(owner, "restart-final", "restart", left=[9])
        assert sum(computer_task(owner)["pc_observations"]) == observations
        digest = owner.state.state_sha256
        replay = call(owner, "restart-final", "restart", left=[9])
        assert replay["receipt"] == restart["receipt"]
        assert replay["checkpoint_receipt"] == {**restart["checkpoint_receipt"], "replayed": True}
        assert owner.state.state_sha256 == digest
    with FieldIntelligenceOwner(root) as owner:
        task = computer_task(owner)
        assert task["status"] == "running"
        assert task["left"] == [9]
        assert sum(task["pc_observations"]) == observations

def test_parameterized_scalar_procedure_transfers_with_exact_equivalence(
    tmp_path,
) -> None:
    def document(limit: int) -> dict[str, object]:
        return {
            "schema": STRUCTURED_SCHEMA,
            "main": [
                {"op": "set_acc", "value": 0},
                {
                    "op": "while_acc",
                    "condition": {"not_equals": limit},
                    "body": [{"op": "add_acc", "value": 1}],
                },
                {"op": "push_acc", "stack": "left"},
            ],
        }

    learned_program = program_arguments(document(3))
    held_out_program = program_arguments(document(5))
    root = tmp_path / "learned"
    with FieldIntelligenceOwner(root) as owner:
        call(
            owner,
            "transfer-configure",
            "configure",
            profile={
                "program_capacity": len(learned_program["program"]) + 4,
                "stack_capacity": 8,
                "max_steps": 1000,
            },
        )
        call(owner, "transfer-load-training", "load", **learned_program)
        for cycle in range(9):
            call(owner, f"transfer-train-{cycle}", "advance", steps=1000)
            if cycle < 8:
                call(owner, f"transfer-restart-{cycle}", "restart")
        library = computer_task(owner)["procedure_learning"]["transferable"]
        assert library
        call(owner, "transfer-load-held-out", "load", **held_out_program)
        assert computer_task(owner)["procedure_learning"]["transferable"] == library
        call(owner, "transfer-run-held-out", "advance", steps=1000)
        transferred = owner.state.computers[0].inspect()["outcome"]
        assert transferred["left"] == [5]
        assert transferred["specialization"]["transferable_procedures"] >= 1
        assert transferred["specialization"]["block_invocations"] >= 1
        assert transferred["specialization"]["scheduler_dispatches_saved"] >= 1
        transferred_digest = owner.state.computers[0].inspect()[
            "task_state_sha256"
        ]

    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.computers[0].inspect()[
            "task_state_sha256"
        ] == transferred_digest
        assert (
            owner.state.computers[0].inspect()["outcome"]["left"]
            == [5]
        )

    baseline_root = tmp_path / "baseline"
    with FieldIntelligenceOwner(baseline_root) as owner:
        call(
            owner,
            "baseline-configure",
            "configure",
            profile={
                "program_capacity": len(held_out_program["program"]) + 4,
                "stack_capacity": 8,
                "max_steps": 1000,
            },
        )
        call(owner, "baseline-load", "load", **held_out_program)
        call(owner, "baseline-run", "advance", steps=1000)
        baseline = owner.state.computers[0].inspect()["outcome"]
        for name in (
            "status",
            "reason",
            "pc",
            "accumulator",
            "left",
            "right",
            "transitions",
            "stack_reads",
            "stack_writes",
        ):
            assert transferred.get(name, transferred["resource_ledger"].get(name)) == (
                baseline.get(name, baseline["resource_ledger"].get(name))
            )
        assert baseline["specialization"]["block_invocations"] == 0

    with FieldIntelligenceOwner(root) as owner:
        call(
            owner,
            "transfer-load-non-equivalent",
            "load",
            program=[[0, 0, 0, 0, 0]],
            left=[],
            right=[],
            entry=0,
        )
        call(owner, "transfer-run-non-equivalent", "advance", steps=32)
        unrelated = owner.state.computers[0].inspect()["outcome"]
        assert unrelated["status"] == "halted"
        assert unrelated["specialization"]["block_invocations"] == 0



def test_revision_assigns_credit_selectively_and_survives_reload(
    tmp_path,
) -> None:
    from cassi_field_cognition import regional_revision_state

    root = tmp_path / "selective-revision"
    records = (
        {
            "record_id": "direct-record",
            "kind": "answer",
            "status": "supported",
            "dependency_ids": ["premise-a"],
        },
        {
            "record_id": "version-record",
            "kind": "plan",
            "status": "active",
            "dependency_versions": [["chart-a", 1]],
        },
        {
            "record_id": "retained-record",
            "kind": "knowledge",
            "status": "retained",
            "dependency_ids": ["premise-z"],
            "payload": {"value": 7},
        },
    )
    task = regional_revision_state(
        records,
        changed_premise_ids=("premise-a",),
        changed_dependency_versions={"chart-a": 2},
    )
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "revision-configure", "configure")
        call(
            owner,
            "revision-start",
            "submit",
            kernel="cognition.field",
            state=task,
            steps=1,
        )
        assert owner.state.computers[0].inspect()["status"] == "running"

    with FieldIntelligenceOwner(root) as owner:
        call(owner, "revision-finish", "advance", steps=64)
        result = owner.state.computers[0].inspect()["consumed_result"]
        assert result["stale_ids"] == ["direct-record", "version-record"]
        assert result["unaffected_record_ids"] == ["retained-record"]
        assert [row["record_id"] for row in result["credit_assignments"]] == [
            "direct-record",
            "version-record",
        ]
        assert result["credit_assignments"][0]["credit"] == [
            {
                "dependency_id": "premise-a",
                "numerator": 1,
                "denominator": 1,
            }
        ]
        assert result["credit_assignments"][1]["credit"] == [
            {
                "dependency_id": "chart-a",
                "numerator": 1,
                "denominator": 1,
            }
        ]
        retained = next(
            row
            for row in result["records"]
            if row["record_id"] == "retained-record"
        )
        assert retained == records[2]
        final_sha256 = owner.state.computers[0].state_sha256

    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.computers[0].state_sha256 == final_sha256
        assert (
            owner.state.computers[0].inspect()["consumed_result"]
            == result
        )


def test_invalid_or_overcapacity_operations_do_not_publish(tmp_path):
    limits = CapacityLimits(max_workspace_bytes=200000)
    with FieldIntelligenceOwner(tmp_path / "field", limits=limits) as owner:
        before = owner.state.state_sha256
        with pytest.raises(FieldIntelligenceError) as error:
            call(owner, "huge", "configure", profile={"program_capacity": 16, "stack_capacity": 1000000, "max_steps": 100})
        assert error.value.code == "WORK_CAPACITY"
        assert owner.state.state_sha256 == before
        call(owner, "configure", "configure", profile={"program_capacity": 16, "stack_capacity": 16, "max_steps": 100})
        before = owner.state.state_sha256
        with pytest.raises(FieldIntelligenceError):
            call(owner, "invalid", "load", program=[[5, 99, 0, 0, 0]])
        assert owner.state.state_sha256 == before
        with pytest.raises(FieldIntelligenceError):
            call(owner, "unloaded", "advance", steps=1)
        assert owner.state.state_sha256 == before
        with pytest.raises(FieldIntelligenceError):
            call(
                owner,
                "invalid-regional",
                "submit",
                kernel="learning.atlas",
                state={"schema": "invalid"},
            )
        assert owner.state.state_sha256 == before
        with pytest.raises(FieldIntelligenceError):
            call(owner, "configure", "configure", profile={"program_capacity": 17, "stack_capacity": 16, "max_steps": 100})
        assert owner.state.state_sha256 == before


def test_optional_computer_page_does_not_change_empty_atlas_encoding():
    state = AtlasState()
    bundle = json.loads(state.encode_bundle())
    assert "computers" not in bundle["descriptor"]["pages"]
    assert AtlasState.decode_bundle(state.encode_bundle()).state_sha256 == state.state_sha256
    malformed = copy.deepcopy(bundle)
    malformed["descriptor"]["pages"]["computers"] = {"schema": "bad"}
    with pytest.raises(FieldIntelligenceError):
        AtlasState.decode_bundle(canonical_json_bytes(malformed))


def test_solver_continuation_persists_and_advances_exactly_once(
    tmp_path,
) -> None:
    source = {
        "kind": "circuit",
        "source": {
            "inputs": ["a", "b", "c", "d", "e", "f"],
            "gates": [],
            "assertions": [],
            "relations": [
                {
                    "kind": "xor",
                    "args": ["a", "b", "c", "d", "e", "f"],
                    "rhs": 1,
                }
            ],
            "clauses": [],
        },
    }
    root = tmp_path / "field"
    with FieldIntelligenceOwner(root) as owner:
        call(
            owner,
            "configure-continuation",
            "configure",
            profile={
                "program_capacity": 16,
                "stack_capacity": 16,
                "max_steps": 100,
            },
        )
        initial_policy = computer_policy_sha256(owner)
        initial_tick = owner.state.logical_tick
        paused = call(
            owner,
            "start-continuation",
            "solve",
            source=source,
            budget=1,
            method="conflict",
        )
        assert paused["receipt"]["status"] == "running"
        assert paused["receipt"]["continuation"] is not None
        assert computer_policy_sha256(owner) == initial_policy
        assert owner.state.logical_tick == initial_tick
        retained_state = owner.state.computers[0].inspect()[
            "task_state_sha256"
        ]
    with FieldIntelligenceOwner(root) as owner:
        inspection = owner.state.computers[0].inspect()
        assert inspection["task_state_sha256"] == retained_state
        before_wrong_source = owner.state.state_sha256
        with pytest.raises(
            FieldIntelligenceError, match="source differs"
        ):
            call(
                owner,
                "wrong-continuation-source",
                "continue-solve",
                source={
                    "kind": "circuit",
                    "source": {
                        "inputs": ["x"],
                        "gates": [],
                        "assertions": [["x", 1]],
                        "relations": [],
                        "clauses": [],
                    },
                },
                budget=63,
            )
        assert owner.state.state_sha256 == before_wrong_source

        completed = call(
            owner,
            "finish-continuation",
            "continue-solve",
            source=source,
            budget=63,
        )
        assert completed["receipt"]["status"] == "sat"
        assert completed["receipt"]["continuation"] is None
        assert owner.state.computers[0].inspect()["session"]["status"] == "terminal"
        learned_policy = computer_policy_sha256(owner)
        assert learned_policy != initial_policy
        assert owner.state.logical_tick == initial_tick + 1
        generation = owner.state.generation
        replay = call(
            owner,
            "finish-continuation",
            "continue-solve",
            source=source,
            budget=63,
        )
        assert replay["receipt"] == completed["receipt"]
        assert replay["checkpoint_receipt"] == {
            **completed["checkpoint_receipt"],
            "replayed": True,
        }
        assert owner.state.generation == generation
        assert owner.state.logical_tick == initial_tick + 1
        assert computer_policy_sha256(owner) == learned_policy
        before_second = owner.state.state_sha256
        with pytest.raises(
            FieldIntelligenceError,
            match="no solver continuation",
        ):
            call(
                owner,
                "continue-after-final",
                "continue-solve",
                source=source,
                budget=1,
            )
        assert owner.state.state_sha256 == before_second

        atomic_pause = call(
            owner,
            "atomic-controller-start",
            "solve",
            source=source,
            budget=2,
            method="algebraic-1-controller",
        )
        assert atomic_pause["receipt"]["run"]["transitions_executed"] <= 2
        if atomic_pause["receipt"]["continuation"] is not None:
            before_one = owner.state.computers[0].inspect()[
                "task_state_sha256"
            ]
            one = call(
                owner,
                "atomic-controller-one-work",
                "continue-solve",
                source=source,
                budget=1,
            )
            assert one["receipt"]["run"]["transitions_executed"] <= 1
            assert owner.state.computers[0].inspect()[
                "task_state_sha256"
            ] != before_one


def test_fixed_catalog_tasks_submit_pause_recover_and_finish(tmp_path) -> None:
    import hashlib

    import torch

    from cassi_field_atlas import FieldProgram, PrimitiveStep, VariableSpec
    from cassi_field_atlas import regional_state as atlas_regional_state
    from cassi_field_cognition import (
        regional_program_state as cognition_regional_state,
    )
    from cassi_field_transceiver import (
        regional_state as transceiver_regional_state,
    )
    from cassi_resonant_field import (
        initial_workspace,
        regional_state as resonant_regional_state,
    )
    from cassi_temporal_field import TemporalField
    from cassi_temporal_field import regional_state as temporal_regional_state
    from cassi_temporal_inquiry import (
        regional_state as inquiry_regional_state,
    )
    from cassi_variational_field import VariationalField
    from cassi_variational_field import (
        regional_state as variational_regional_state,
    )

    revision = hashlib.sha256(b"regional-owner").hexdigest()
    program = FieldProgram(
        program_id="regional-identity",
        version=1,
        roles=("value",),
        steps=(
            PrimitiveStep("identity", "once", ("value",)),
            PrimitiveStep("identity", "twice", ("once",)),
        ),
        outputs=("twice",),
    )
    torch.set_num_threads(1)
    variational = VariationalField(3, ((0, 1), (1, 2)))
    variational_field = variational.observe(
        variational.initial_state(),
        0,
        [0.8, -0.45],
        exposure=1.0,
    )
    memory = TemporalField.initial(
        "owner-inquiry",
        action_ids=("sense", "move"),
        observation_ids=("ready", "done"),
        max_states=8,
    )
    memory, _ = memory.learn(
        (
            (
                {"action": "sense", "observation": "ready"},
                {"action": "move", "observation": "done"},
            ),
        ),
        source_revision_ids=(revision,),
    )
    transceiver_source = {
        "metadata": {
            "input_ids": ["input"],
            "output_ids": ["output"],
            "horizon_ticks": 1,
        },
        "full_words": {
            "base_state": [0.0],
            "input_lift": [[1.0]],
            "output_rows": [[1.0]],
            "initial_state": [0.0],
        },
    }
    tasks = (
        (
            "learning.atlas",
            atlas_regional_state(
                (
                    VariableSpec("x", lower=-1.0, upper=1.0),
                    VariableSpec("y", lower=-1.0, upper=1.0),
                )
            ),
        ),
        (
            "cognition.field",
            cognition_regional_state(program, {"value": 7}),
        ),
        (
            "numerical.variational",
            variational_regional_state(
                variational,
                variational_field,
                (0,),
                (0.8,),
                panel_size=1,
                max_iterations=128,
                allowance=1e-10,
            ),
        ),
        (
            "temporal-memory",
            temporal_regional_state(
                "owner-temporal",
                action_ids=("sense", "move"),
                observation_ids=("ready", "done"),
                episodes=(
                    (
                        {"action": "sense", "observation": "ready"},
                        {"action": "move", "observation": "done"},
                    ),
                ),
                source_revision_ids=(revision,),
            ),
        ),
        (
            "inquiry.temporal",
            inquiry_regional_state(
                memory,
                operations=(
                    {
                        "action": "move",
                        "cost": 1.0,
                        "risk": 0.0,
                        "authorized": True,
                        "feasible": True,
                        "acquisition_allowed": False,
                    },
                ),
                goal_observations=("done",),
                horizon=2,
            ),
        ),
        (
            "numerical.resonant",
            resonant_regional_state(
                initial_workspace(),
                ticks=2,
                demand=0.2,
            ),
        ),
        (
            "numerical.transceiver",
            transceiver_regional_state(
                transceiver_source,
                panel_size=1,
            ),
        ),
    )

    root = tmp_path / "field"
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "regional-configure", "configure")

    for index, (kernel, state) in enumerate(tasks):
        with FieldIntelligenceOwner(root) as owner:
            submitted = call(
                owner,
                f"regional-submit-{index}",
                "submit",
                kernel=kernel,
                state=state,
                steps=1,
            )
            assert submitted["receipt"]["run"][
                "transitions_executed"
            ] == 1
            submitted_digest = owner.state.state_sha256
            task_digest = owner.state.computers[0].inspect()[
                "task_state_sha256"
            ]

        with FieldIntelligenceOwner(root) as owner:
            assert owner.state.state_sha256 == submitted_digest
            assert owner.state.computers[0].inspect()[
                "task_state_sha256"
            ] == task_digest
            for episode in range(128):
                if owner.state.computers[0].inspect()["status"] == "halted":
                    break
                advanced = call(
                    owner,
                    f"regional-advance-{index}-{episode}",
                    "advance",
                    steps=64,
                )
                assert advanced["receipt"]["transitions_executed"] <= 64
            else:
                pytest.fail(f"{kernel} did not halt within its declared work")
            inspection = owner.state.computers[0].inspect()
            assert inspection["status"] == "halted"
            assert inspection["session"]["kernel"] == kernel
            assert inspection["session"]["status"] == "halted"
            assert inspection["outcome"]["family"] == kernel


def test_shared_representation_learning_restarts_and_retains_identity(
    tmp_path,
) -> None:
    import hashlib

    from cassi_field_cognition import (
        regional_language_state,
        regional_representation_state,
    )

    observed = hashlib.sha256(b"instrument observation").hexdigest()
    corroborated = hashlib.sha256(b"instrument corroboration").hexdigest()
    located = hashlib.sha256(b"instrument location").hexdigest()
    root = tmp_path / "field"
    task = regional_representation_state(
        (
            {
                "mention_id": "instrument-observation",
                "aliases": ["sensor"],
                "features": {"kind": "instrument", "port": 7},
                "support_event_ids": [observed],
            },
            {
                "mention_id": "instrument-corroboration",
                "aliases": ["detector"],
                "features": {"kind": "instrument", "port": 7},
                "support_event_ids": [corroborated],
            },
            {
                "mention_id": "location-observation",
                "aliases": ["bay"],
                "features": {"kind": "location"},
                "support_event_ids": [located],
            },
        ),
        same_entity=(("instrument-observation", "instrument-corroboration"),),
        distinct_entity=(("instrument-observation", "location-observation"),),
        relations=(
            {
                "subject_mention": "instrument-observation",
                "predicate": "located-at",
                "object_mention": "location-observation",
                "support_event_ids": [located],
            },
        ),
    )
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "representation-configure", "configure")
        call(
            owner,
            "representation-start",
            "submit",
            kernel="cognition.field",
            state=task,
            steps=2,
        )
        assert owner.state.computers[0].inspect()["status"] == "running"
        paused_sha256 = owner.state.computers[0].inspect()["task_state_sha256"]

    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.computers[0].inspect()["task_state_sha256"] == paused_sha256
        call(owner, "representation-finish", "advance", steps=64)
        outcome = owner.state.computers[0].inspect()["consumed_result"]
        assert outcome["status"] == "learned"
        registry = outcome["registry"]
        assert outcome["entity_count"] == 2
        assert outcome["relation_count"] == 1
        instrument = next(
            row for row in registry["entities"] if "sensor" in row["aliases"]
        )
        instrument_id = instrument["entity_id"]
        assert instrument["aliases"] == ["detector", "sensor"]
        assert instrument["feature_candidates"]["port"] == [7]

        extension = regional_representation_state(
            (
                {
                    "mention_id": "instrument-dialogue",
                    "aliases": ["scope"],
                    "features": {"kind": "instrument", "port": 7},
                    "support_event_ids": [corroborated],
                },
            ),
            same_entity=(("instrument-observation", "instrument-dialogue"),),
            registry=registry,
        )
        call(
            owner,
            "representation-extend",
            "submit",
            kernel="cognition.field",
            state=extension,
            steps=64,
        )
        extended = owner.state.computers[0].inspect()["consumed_result"]["registry"]
        instrument = next(
            row for row in extended["entities"] if row["entity_id"] == instrument_id
        )
        assert instrument["aliases"] == ["detector", "scope", "sensor"]
        assert instrument["mention_ids"] == [
            "instrument-corroboration",
            "instrument-dialogue",
            "instrument-observation",
        ]
        construction = {
            "construction_id": "instrument-request",
            "version": 1,
            "pattern": ["use", "{instrument}"],
            "roles": ["instrument"],
            "semantic_program_id": "use-instrument",
            "support_event_ids": [observed],
            "status": "promoted",
        }
        interpretation = regional_language_state(
            (construction,),
            mode="interpret",
            text="use detector",
            representation_registry=extended,
        )
        call(
            owner,
            "representation-interpret",
            "submit",
            kernel="cognition.field",
            state=interpretation,
            steps=64,
        )
        understood = owner.state.computers[0].inspect()["consumed_result"]
        assert understood["status"] == "understood"
        assert understood["branches"][0]["bindings"] == {
            "instrument": instrument_id
        }

        expression = regional_language_state(
            (construction,),
            mode="express",
            bindings={"instrument": instrument_id},
            semantic_program_id="use-instrument",
            representation_registry=extended,
        )
        call(
            owner,
            "representation-express",
            "submit",
            kernel="cognition.field",
            state=expression,
            steps=64,
        )
        expressed = owner.state.computers[0].inspect()["consumed_result"]
        assert expressed["status"] == "expressed"
        assert expressed["text"] == "use detector"


def test_learned_variable_span_language_composes_after_reload_and_ablates(
    tmp_path,
) -> None:
    import hashlib

    from cassi_field_cognition import (
        regional_construction_learning_state,
        regional_language_state,
        regional_representation_state,
    )

    def event(label: str) -> str:
        return hashlib.sha256(label.encode("utf-8")).hexdigest()

    mentions = tuple(
        {
            "mention_id": label.replace(" ", "-"),
            "aliases": [label],
            "features": {"kind": kind},
            "support_event_ids": [event(label)],
        }
        for label, kind in (
            ("red sensor", "instrument"),
            ("blue probe", "instrument"),
            ("amber meter", "instrument"),
            ("north cabinet", "location"),
            ("south drawer", "location"),
            ("west locker", "location"),
        )
    )
    root = tmp_path / "field"
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "composition-configure", "configure")
        call(
            owner,
            "composition-representations",
            "submit",
            kernel="cognition.field",
            state=regional_representation_state(mentions),
            steps=64,
        )
        registry = owner.state.computers[0].inspect()["consumed_result"]["registry"]
        learning = regional_construction_learning_state(
            (
                {
                    "event_id": event("acquire-red-north"),
                    "roles": {
                        "instrument": "red sensor",
                        "destination": "north cabinet",
                    },
                    "text": "place red sensor in north cabinet",
                },
                {
                    "event_id": event("acquire-blue-south"),
                    "roles": {
                        "instrument": "blue probe",
                        "destination": "south drawer",
                    },
                    "text": "place blue probe in south drawer",
                },
            ),
            (
                {
                    "event_id": event("holdout-amber-west"),
                    "roles": {
                        "instrument": "amber meter",
                        "destination": "west locker",
                    },
                    "text": "place amber meter in west locker",
                },
            ),
            construction_id="learned-placement",
            semantic_program_id="place-instrument",
        )
        call(
            owner,
            "composition-learn",
            "submit",
            kernel="cognition.field",
            state=learning,
            steps=2,
        )
        assert owner.state.computers[0].inspect()["status"] == "running"
        paused = owner.state.computers[0].inspect()["task_state_sha256"]

    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.computers[0].inspect()["task_state_sha256"] == paused
        call(owner, "composition-learn-finish", "advance", steps=64)
        learned = owner.state.computers[0].inspect()["consumed_result"]
        assert learned["status"] == "learned"
        assert learned["held_out_validated"] is True
        construction = learned["construction"]
        assert construction["pattern"] == [
            "place",
            "{instrument}",
            "in",
            "{destination}",
        ]
        assert construction["variable_spans"] is True

        entities = {
            alias: row["entity_id"]
            for row in registry["entities"]
            for alias in row["aliases"]
        }
        interpretation = regional_language_state(
            (construction,),
            mode="interpret",
            text="place amber meter in north cabinet",
            representation_registry=registry,
        )
        call(
            owner,
            "composition-interpret",
            "submit",
            kernel="cognition.field",
            state=interpretation,
            steps=64,
        )
        understood = owner.state.computers[0].inspect()["consumed_result"]
        assert understood["status"] == "understood"
        assert understood["branches"][0]["bindings"] == {
            "instrument": entities["amber meter"],
            "destination": entities["north cabinet"],
        }

        expression = regional_language_state(
            (construction,),
            mode="express",
            bindings={
                "instrument": entities["amber meter"],
                "destination": entities["north cabinet"],
            },
            semantic_program_id="place-instrument",
            representation_registry=registry,
        )
        call(
            owner,
            "composition-express",
            "submit",
            kernel="cognition.field",
            state=expression,
            steps=64,
        )
        assert owner.state.computers[0].inspect()["consumed_result"]["text"] == (
            "place amber meter in north cabinet"
        )

        ablated = regional_language_state(
            (),
            mode="interpret",
            text="place amber meter in north cabinet",
            representation_registry=registry,
        )
        call(
            owner,
            "composition-ablate",
            "submit",
            kernel="cognition.field",
            state=ablated,
            steps=64,
        )
        absent = owner.state.computers[0].inspect()["consumed_result"]
        assert absent["status"] == "representation-insufficient"
        assert absent["unsupported"] is True


def test_regional_invocation_arguments_resume_resident_temporal_state(
    tmp_path,
) -> None:
    from cassi_temporal_field import regional_state as temporal_regional_state

    source = SourceInput(
        source_id="temporal-invocation-source",
        content=canonical_json_bytes({"episode": "temporal invocation"}),
        media_type="application/json",
        codec="utf-8",
        observed_timestamp="temporal-invocation-time",
        scope="test",
        claim_category="controlled-observation",
        fidelity="exact-record",
        labels=("test",),
    )
    revision = source.revision_id
    root = tmp_path / "field"
    task = temporal_regional_state(
        "shared-temporal",
        action_ids=("sense", "move"),
        observation_ids=("ready", "done"),
        max_states=8,
    )
    induction = {
        "operation": "induce",
        "episodes": [
            [
                {"action": "sense", "observation": "ready"},
                {"action": "move", "observation": "done"},
            ]
        ],
        "source_revision_ids": [revision],
    }
    with FieldIntelligenceOwner(root) as owner:
        owner.evidence.store_source(source)
        call(owner, "temporal-configure-computer", "configure")
        call(
            owner,
            "temporal-induce-start",
            "submit",
            kernel="temporal-memory",
            state=task,
            arguments=induction,
            steps=1,
        )
        partial = computer_task(owner)
        assert partial["continuation"]["phase"] == "running"
        assert partial["continuation"]["operation"] == "induce"
        partial_sha256 = owner.state.computers[0].inspect()["task_state_sha256"]

    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.computers[0].inspect()["task_state_sha256"] == partial_sha256
        call(owner, "temporal-induce-finish", "advance", steps=64)
        learned = computer_task(owner)
        assert learned["continuation"]["phase"] == "ready"
        assert learned["model"]["state_count"] >= 2

        call(
            owner,
            "temporal-consume",
            "invoke",
            arguments={
                "operation": "consume",
                "action": "sense",
                "observation": "ready",
            },
            steps=64,
        )
        consumed = owner.state.computers[0].inspect()["consumed_result"]
        assert consumed["operation"] == "consume"
        assert consumed["action"] == "sense"
        assert consumed["observation"] == "ready"
        assert computer_task(owner)["model"] == learned["model"]


def test_sustained_machine_episode_crosses_evidence_language_revision_action_and_revocation(
    tmp_path,
    monkeypatch,
) -> None:

    from cassi_field_atlas import FieldProgram, RelationChart, VariableSpec, sha256_value
    from cassi_field_cognition import (
        ActionReadout,
        regional_language_state,
        regional_plan_state,
        regional_query_state,
        regional_representation_state,
        regional_revision_state,
    )
    from cassi_field_owner import (
        AuthorityGrant,
        DeterministicWorldAdapter,
        SourceInput,
        WorldAcknowledgment,
    )

    root = tmp_path / "field"
    source = SourceInput(
        source_id="episode-source",
        content=canonical_json_bytes({"bias": 1.0, "x": 1.0, "y": 1.0}),
        media_type="application/json",
        codec="utf-8",
        observed_timestamp="episode-time",
        scope="test",
        claim_category="controlled-observation",
        fidelity="exact-record",
        labels=("test",),
    )
    construction = {
        "construction_id": "episode-request",
        "version": 1,
        "pattern": ["use", "{instrument}"],
        "roles": ["instrument"],
        "semantic_program_id": "use-instrument",
        "support_event_ids": [],
        "status": "promoted",
    }
    computer_digests: list[str] = []

    with FieldIntelligenceOwner(root) as owner:
        for index, variable in enumerate(
            (
                VariableSpec("bias", kind="constant", constant=1.0),
                VariableSpec("x", lower=-10.0, upper=10.0),
                VariableSpec("y", lower=-10.0, upper=10.0),
            )
        ):
            owner.configure_variable(f"episode-variable:{index}", variable)
        owner.configure_chart(
            "episode-chart",
            RelationChart.empty(
                chart_id="episode-xy",
                scope=("bias", "x", "y"),
                ridge=1e-5,
                observation_norm_bound=20.0,
                prior_mass=1e-3,
            ),
        )
        revisions: list[str] = []
        for index, x in enumerate((-3.0, -1.0, 1.0, 3.0)):
            admitted = owner.admit_observation(
                operation_id=f"episode-observe:{index}",
                source=source if index == 2 else SourceInput(
                    source_id=f"episode-source:{index}",
                    content=canonical_json_bytes(
                        {"bias": 1.0, "x": x, "y": x}
                    ),
                    media_type="application/json",
                    codec="utf-8",
                    observed_timestamp=f"episode-time:{index}",
                    scope="test",
                    claim_category="controlled-observation",
                    fidelity="exact-record",
                    labels=("test",),
                ),
                values={"bias": 1.0, "x": x, "y": x},
                context={},
            )
            revisions.append(admitted["source"]["revision_id"])
        revision_id = revisions[2]
        construction["support_event_ids"] = [revision_id]
        call(owner, "episode-configure", "configure")

        def legacy_execute(*_args, **_kwargs):
            raise AssertionError("legacy FieldProgram evaluator was reached")

        with monkeypatch.context() as disabled:
            disabled.setattr(FieldProgram, "execute", legacy_execute)
            representation = regional_representation_state(
                (
                    {
                        "mention_id": "episode-instrument",
                        "aliases": ["sensor"],
                        "features": {"kind": "instrument"},
                        "support_event_ids": [revision_id],
                    },
                )
            )
            call(
                owner,
                "episode-representation",
                "submit",
                kernel="cognition.field",
                state=representation,
                steps=64,
            )
            registry = computer_task(owner)["result"]["registry"]
            instrument_id = registry["entities"][0]["entity_id"]
            computer_digests.append(owner.state.computers[0].state_sha256)

            interpretation = regional_language_state(
                (construction,),
                mode="interpret",
                text="use sensor",
                representation_registry=registry,
            )
            call(
                owner,
                "episode-interpret",
                "submit",
                kernel="cognition.field",
                state=interpretation,
                steps=64,
            )
            understood = computer_task(owner)["result"]
            assert understood["branches"][0]["bindings"]["instrument"] == instrument_id
            computer_digests.append(owner.state.computers[0].state_sha256)

    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.computers[0].state_sha256 == computer_digests[-1]
        plan = {
            "plan_id": "episode-plan",
            "goal_id": "use-instrument",
            "goal": {"instrument": instrument_id},
            "assumptions": {"source": revision_id},
            "segments": [
                {
                    "segment_id": "episode-plan:0",
                    "level": "task",
                    "kind": "request",
                    "payload": {"instrument": instrument_id},
                    "status": "ready",
                    "dependency_versions": [revision_id],
                    "source_revision_ids": [revision_id],
                }
            ],
            "source_revision_ids": [revision_id],
            "status": "ready",
        }
        call(
            owner,
            "episode-plan",
            "submit",
            kernel="cognition.field",
            state=regional_plan_state(plan),
            steps=64,
        )
        planned = computer_task(owner)["result"]
        assert planned["segments"][0]["payload"]["instrument"] == instrument_id
        computer_digests.append(owner.state.computers[0].state_sha256)

        query = {
            "query_id": "episode-query",
            "field_generation": owner.state.generation,
            "requested": ["instrument"],
            "observed": {"alias": "sensor"},
            "branches": [
                {
                    "branch_id": "episode-query:0",
                    "status": "supported",
                    "values": {"instrument": instrument_id},
                    "active_chart_versions": [revision_id],
                    "source_revision_ids": [revision_id],
                    "obligations": [],
                }
            ],
            "status": "supported",
            "state_sha256": owner.state.state_sha256,
        }
        call(
            owner,
            "episode-query",
            "submit",
            kernel="cognition.field",
            state=regional_query_state(query),
            steps=64,
        )
        queried = computer_task(owner)["result"]
        assert queried["branches"][0]["values"]["instrument"] == instrument_id
        computer_digests.append(owner.state.computers[0].state_sha256)

        records = (
            {
                "record_id": "episode-plan",
                "kind": "plan",
                "status": "active",
                "dependency_ids": [revision_id],
            },
            {
                "record_id": "episode-query",
                "kind": "query",
                "status": "supported",
                "dependency_ids": [revision_id],
            },
        )
        call(
            owner,
            "episode-revision",
            "submit",
            kernel="cognition.field",
            state=regional_revision_state(
                records,
                changed_premise_ids=(revision_id,),
            ),
            steps=64,
        )
        revised = computer_task(owner)["result"]
        assert {
            row["status"] for row in revised["records"]
        } == {"stale"}
        computer_digests.append(owner.state.computers[0].state_sha256)

        expression = regional_language_state(
            (construction,),
            mode="express",
            bindings={"instrument": instrument_id},
            semantic_program_id="use-instrument",
            representation_registry=registry,
        )
        call(
            owner,
            "episode-expression",
            "submit",
            kernel="cognition.field",
            state=expression,
            steps=64,
        )
        assert computer_task(owner)["result"]["text"] == "use sensor"
        computer_digests.append(owner.state.computers[0].state_sha256)
        assert len(set(computer_digests)) == len(computer_digests)

        prepared = owner.think(
            operation_id="episode-think",
            observed={"x": 2.0},
            requested=("y",),
        )
        assert prepared["status"] == "supported"
        readout = ActionReadout(
            readout_id="episode-sign",
            version=1,
            labels=("negative", "positive"),
            coefficients=({"y": -1.0}, {"y": 1.0}),
            observed_error_radius=0.01,
        )
        proposal = owner.propose_effect(
            operation_id="episode-effect",
            observed={"x": 2.0},
            readout=readout,
            target="episode-world",
            scope="test",
            payload={"instrument": instrument_id},
        )

        def transition(
            action: str,
            target: str,
            payload: Mapping[str, object],
        ) -> WorldAcknowledgment:
            return WorldAcknowledgment(
                acknowledgment_id="episode-ack",
                operation_id="episode-effect",
                status="succeeded",
                observed_values={"x": 2.0, "y": 2.0},
                context={"instrument": payload["instrument"]},
                source_content=canonical_json_bytes(
                    {"action": action, "payload": dict(payload), "target": target}
                ),
            )

        dispatched = owner.dispatch_effect(
            prediction_id=proposal["prediction"]["prediction_id"],
            grant=AuthorityGrant(
                grant_id="episode-effect-grant",
                issuer="test-host",
                generation=0,
                operation="effect",
                target="episode-world",
                scope="test",
            ),
            adapter=DeterministicWorldAdapter(transition),
        )
        assert dispatched["status"] == "acknowledged"

        old_manifest = owner.checkpoints.current_manifest_sha256
        preview = owner.preview_forget((revision_id,))
        owner.forget(
            operation_id="episode-forget",
            preview_id=preview["preview_id"],
            revision_ids=(revision_id,),
            grant=AuthorityGrant(
                grant_id="episode-forget-grant",
                issuer="test-host",
                generation=0,
                operation="forget",
                target=sha256_value([revision_id]),
                scope="test",
            ),
            scope="test",
        )
        with pytest.raises(FieldIntelligenceError) as stale:
            owner.checkpoints.load_version(old_manifest)
        assert stale.value.code == "STALE_REVOCATION"


def test_strict_sustained_episode_stays_in_one_machine_and_checks_authority(
    tmp_path,
    monkeypatch,
) -> None:
    import hashlib

    from cassi_field_atlas import FieldProgram, RelationChart, VariableSpec, sha256_value
    from cassi_field_cognition import regional_state
    from cassi_field_owner import AuthorityGrant, SourceInput

    root = tmp_path / "strict-episode"
    source = SourceInput(
        source_id="strict-episode-source",
        content=canonical_json_bytes(
            {"instrument": "sensor", "location": "bay", "access": False}
        ),
        media_type="application/json",
        codec="utf-8",
        observed_timestamp="strict-episode-time",
        scope="test",
        claim_category="controlled-observation",
        fidelity="exact-record",
        labels=("test",),
    )
    with FieldIntelligenceOwner(root) as owner:
        owner.configure_variable(
            "strict-episode-access-variable",
            VariableSpec("access", lower=0.0, upper=1.0),
        )
        owner.configure_chart(
            "strict-episode-access-chart",
            RelationChart.empty(
                chart_id="strict-episode-access",
                scope=("access",),
                ridge=1e-5,
                observation_norm_bound=2.0,
                prior_mass=1e-3,
            ),
        )
        admitted = owner.admit_observation(
            operation_id="strict-episode-observation",
            source=source,
            values={"access": 0.0},
            context={},
        )
        revision_id = admitted["source"]["revision_id"]
        call(owner, "strict-episode-configure", "configure")
        task = regional_state(
            {
                "instrument_alias": "sensor",
                "location_alias": "bay",
                "access_allowed": False,
                "source_revision_id": revision_id,
                "action_target": "episode-world",
                "action_scope": "test",
                "numeric_work": [0.25, 0.5, 0.75],
            },
            operation="sustained-episode",
        )
        started = call(
            owner,
            "strict-episode-start",
            "submit",
            kernel="cognition.field",
            state=task,
            steps=128,
        )
        assert started["receipt"]["run"]["status"] == "waiting"
        assert computer_task(owner)["continuation"]["stage"] == "await-premise"
        paused_sha256 = owner.state.computers[0].state_sha256
        old_manifest = owner.checkpoints.current_manifest_sha256

    def unavailable(*_args, **_kwargs):
        raise AssertionError("legacy cognition evaluator was reached")

    with monkeypatch.context() as disabled:
        disabled.setattr(FieldProgram, "execute", unavailable)
        with FieldIntelligenceOwner(root) as owner:
            assert owner.state.computers[0].state_sha256 == paused_sha256
            revised = call(
                owner,
                "strict-episode-premise-change",
                "invoke",
                arguments={
                    "operation": "premise-change",
                    "event_id": hashlib.sha256(b"access-granted").hexdigest(),
                    "source_revision_id": revision_id,
                    "access_allowed": True,
                },
                steps=128,
            )
            assert revised["receipt"]["run"]["status"] == "waiting"
            continuation = computer_task(owner)["continuation"]
            assert continuation["stage"] == "await-authorization"
            assert continuation["plan"]["status"] == "ready"
            proposal_id = continuation["proposal"]["proposal_id"]

            unauthorized_state = owner.state.state_sha256
            with pytest.raises(FieldIntelligenceError) as unauthorized:
                call(
                    owner,
                    "strict-episode-unauthorized",
                    "invoke",
                    arguments={
                        "operation": "authorize-action",
                        "proposal_id": proposal_id,
                    },
                    steps=128,
                )
            assert unauthorized.value.code == "AUTHORITY_REQUIRED"
            assert owner.state.state_sha256 == unauthorized_state

            grant = AuthorityGrant(
                grant_id="strict-episode-grant",
                issuer="test-host",
                generation=0,
                operation="computer-effect",
                target="episode-world",
                scope="test",
                one_use=False,
            )
            authorized = call(
                owner,
                "strict-episode-authorize",
                "authorized-invoke",
                arguments={
                    "operation": "authorize-action",
                    "proposal_id": proposal_id,
                },
                grant=grant.as_dict(),
                target="episode-world",
                scope="test",
                steps=128,
            )
            assert authorized["receipt"]["run"]["status"] == "waiting"
            assert computer_task(owner)["continuation"]["stage"] == (
                "await-dispatch"
            )
            dispatched = call(
                owner,
                "strict-episode-dispatch",
                "authorized-invoke",
                arguments={
                    "operation": "dispatch-action",
                    "adapter_id": "strict-test-adapter",
                    "dispatch_id": "strict-episode-dispatch",
                    "idempotency": "guaranteed",
                    "idempotency_key": "strict-episode-use-instrument",
                    "proposal_id": proposal_id,
                },
                grant=grant.as_dict(),
                target="episode-world",
                scope="test",
                steps=128,
            )
            assert dispatched["receipt"]["run"]["status"] == "waiting"
            assert computer_task(owner)["continuation"]["stage"] == (
                "await-acknowledgment"
            )
            acknowledged = call(
                owner,
                "strict-episode-acknowledgment",
                "invoke",
                arguments={
                    "operation": "acknowledgment",
                    "event_id": hashlib.sha256(b"verified-ack").hexdigest(),
                    "proposal_id": proposal_id,
                    "status": "succeeded",
                },
                steps=128,
            )
            assert acknowledged["receipt"]["run"]["status"] == "waiting"
            assert computer_task(owner)["continuation"]["stage"] == "await-revocation"
            assert computer_task(owner)["continuation"]["assessment_updates"] == 1
            generation = owner.state.generation
            replay = call(
                owner,
                "strict-episode-acknowledgment",
                "invoke",
                arguments={
                    "operation": "acknowledgment",
                    "event_id": hashlib.sha256(b"verified-ack").hexdigest(),
                    "proposal_id": proposal_id,
                    "status": "succeeded",
                },
                steps=128,
            )
            assert replay["receipt"] == acknowledged["receipt"]
            assert owner.state.generation == generation
            assert computer_task(owner)["continuation"]["assessment_updates"] == 1

            preview = owner.preview_forget((revision_id,))
            owner.forget(
                operation_id="strict-episode-forget",
                preview_id=preview["preview_id"],
                revision_ids=(revision_id,),
                grant=AuthorityGrant(
                    grant_id="strict-episode-forget-grant",
                    issuer="test-host",
                    generation=0,
                    operation="forget",
                    target=sha256_value([revision_id]),
                    scope="test",
                ),
                scope="test",
            )
            revoked = call(
                owner,
                "strict-episode-revocation",
                "invoke",
                arguments={
                    "operation": "revocation",
                    "event_id": hashlib.sha256(b"source-revoked").hexdigest(),
                    "source_revision_id": revision_id,
                },
                steps=128,
            )
            assert revoked["receipt"]["run"]["status"] == "halted"
            result = owner.state.computers[0].inspect()["consumed_result"]
            assert result["status"] == "complete"
            assert result["query"]["status"] == "unsupported"
            assert result["plan"]["status"] == "acknowledged"
            assert result["acknowledgment"]["status"] == "succeeded"
            assert result["assessment_updates"] == 1
            assert result["numerical_total"] == 1.5
            assert result["unaffected_knowledge"]["value"] == "retained"
            assert result["work"] > 3
            assert all(
                revision_id not in row["support_event_ids"]
                for row in result["registry"]["entities"]
            )
            with pytest.raises(FieldIntelligenceError) as stale:
                owner.checkpoints.load_version(old_manifest)
            assert stale.value.code == "STALE_REVOCATION"


def test_cli_submits_and_invokes_resident_regional_task(tmp_path, capsys) -> None:
    from cassi_temporal_field import regional_state as temporal_regional_state

    data_home = tmp_path / "cli-owner"
    task_path = tmp_path / "task.json"
    induction_path = tmp_path / "induction.json"
    consume_path = tmp_path / "consume.json"
    source = SourceInput(
        source_id="cli-temporal-source",
        content=canonical_json_bytes({"episode": "cli temporal"}),
        media_type="application/json",
        codec="utf-8",
        observed_timestamp="cli-temporal-time",
        scope="test",
        claim_category="controlled-observation",
        fidelity="exact-record",
        labels=("test",),
    )
    revision = source.revision_id
    task_path.write_text(
        json.dumps(
            temporal_regional_state(
                "cli-temporal",
                action_ids=("sense", "move"),
                observation_ids=("ready", "done"),
                max_states=8,
            )
        ),
        encoding="utf-8",
    )
    induction_path.write_text(
        json.dumps(
            {
                "operation": "induce",
                "episodes": [
                    [
                        {"action": "sense", "observation": "ready"},
                        {"action": "move", "observation": "done"},
                    ]
                ],
                "source_revision_ids": [revision],
            }
        ),
        encoding="utf-8",
    )
    consume_path.write_text(
        json.dumps(
            {
                "operation": "consume",
                "action": "sense",
                "observation": "ready",
            }
        ),
        encoding="utf-8",
    )
    with FieldIntelligenceOwner(data_home) as owner:
        owner.evidence.store_source(source)
    prefix = ["--data-home", str(data_home)]
    assert computer_cli([*prefix, "configure"]) == 0
    capsys.readouterr()
    assert computer_cli(
        [
            *prefix,
            "submit",
            "temporal-memory",
            str(task_path),
            "--arguments",
            str(induction_path),
            "--steps",
            "64",
        ]
    ) == 0
    submitted = json.loads(capsys.readouterr().out)
    assert submitted["response"]["result"]["receipt"]["kernel"] == "temporal-memory"
    assert computer_cli(
        [
            *prefix,
            "invoke",
            str(consume_path),
            "--steps",
            "64",
        ]
    ) == 0
    invoked = json.loads(capsys.readouterr().out)
    invoked_receipt = invoked["response"]["result"]["receipt"]
    assert invoked_receipt["run"]["status"] == "halted"
    assert computer_cli([*prefix, "inspect"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    consumed = inspected["response"]["result"]["computers"][0][
        "consumed_result"
    ]
    assert consumed["action"] == "sense"
    assert consumed["observation"] == "ready"


def _semantic_step(semantic_state, **request):
    from cassi_field_cognition import semantic_cognition_kernel

    transition = semantic_cognition_kernel(semantic_state, request, 4096)
    assert transition.status == "done"
    return transition.state, transition.output


def test_semantic_observation_keeps_joint_history_and_revises_one_shared_binding(
    tmp_path,
) -> None:
    from cassi_field_cognition import semantic_cognition_state
    from cassi_field_program import semantic_program_payload

    state = semantic_cognition_state(
        scope={"world": "joint-test"},
        frame={"coordinate_system": "sensor"},
    )
    state, registered_codec = _semantic_step(
        state,
        operation="register",
        operation_id="register-packed-observation-codec",
        kind="Program",
        record_id="codec:packed-observation-v1",
        payload={
            "program": semantic_program_payload(
                program_kind="measurement",
                body={
                    "transform": "identified-deterministic",
                    "information_loss": "none",
                },
                max_work=1,
            )
        },
    )
    measurement_program = registered_codec["record"]
    public_initial = copy.deepcopy(state)
    observation = {
        "operation": "observe",
        "operation_id": "joint-observation",
        "delivery_id": "delivery:joint",
        "event_id": "event:joint",
        "stream_id": "camera",
        "chunk_index": 0,
        "time": {"start": 2.0, "end": 3.0},
        "world_clock": {"clock_domain": "sim", "uncertainty": 0.25},
        "receipt": {
            "clock_domain": "adapter",
            "time": 8.0,
            "uncertainty": 0.5,
        },
        "measurement": {
            "availability": "partial",
            "observed_mask": ["x", "y"],
            "precision": {"x": 0.1, "y": 0.1},
            "selection": {"visible": True},
            "smoothing": False,
        },
        "joint_id": "joint:crossing",
        "joint_semantics": "constraint-set",
        "joint_alternatives": [
            {"assignment": {"x": 0, "y": 0}},
            {"assignment": {"x": 1, "y": 1}},
        ],
        "measurement_program": measurement_program,
        "packed_observations": {
            "columns": [
                "binding_id",
                "subject",
                "attribute",
                "value",
                "measurement",
            ],
            "rows": [
                [
                    "binding:x",
                    "pair",
                    "x",
                    {"x": 0, "y": 0},
                    {"availability": "partial"},
                ],
                [
                    "binding:unrelated",
                    "clock",
                    "phase",
                    "quiet",
                    {"availability": "observed"},
                ],
            ],
        },
    }
    state, admitted = _semantic_step(state, **observation)
    event_ref = admitted["event"]
    assert state["records"][event_ref["id"]][-1]["epistemic_kind"] == "observed"
    assert state["records"][event_ref["id"]][-1]["payload"][
        "measurement_program"
    ] == observation["measurement_program"]
    assert set(state["current"]["Binding"]) >= {
        "binding:x",
        "binding:unrelated",
    }
    assert state["time"]["now"] == 3.0
    state, joint = _semantic_step(
        state,
        operation="query",
        operation_id="query-joint",
        query={"kind": "joint", "joint_id": "joint:crossing"},
    )
    assert joint["status"] == "alternatives"
    assert joint["belief_semantics"] == "constraint-set"
    assert joint["probability_model"] is None
    assert {tuple(sorted(row["assignment"].items())) for row in joint["alternatives"]} == {
        (("x", 0), ("y", 0)),
        (("x", 1), ("y", 1)),
    }
    record_count = sum(len(history) for history in state["records"].values())
    state, replay = _semantic_step(
        state,
        **{**observation, "operation_id": "joint-observation-retransmitted"},
    )
    assert replay["replayed"] is True
    assert sum(len(history) for history in state["records"].values()) == record_count

    state, _ = _semantic_step(
        state,
        operation="advance-time",
        operation_id="advance-world",
        event_id="event:advance",
        now=10.0,
    )
    old_binding = state["current"]["Binding"]["binding:x"]
    unrelated = state["current"]["Binding"]["binding:unrelated"]
    state, revised = _semantic_step(
        state,
        operation="correct",
        operation_id="correct-identity",
        correction_id="crossing-resolved",
        target=old_binding,
        replacement={"value": {"x": 1, "y": 1}, "alternatives": []},
        reason="late identification",
    )
    assert revised["current"]["content_version"] == old_binding["content_version"] + 1
    assert state["current"]["Binding"]["binding:unrelated"] == unrelated
    state, stale = _semantic_step(
        state,
        operation="query",
        operation_id="query-prior-binding",
        query={"kind": "record", "reference": old_binding},
    )
    assert stale["status"] == "support-gap"
    assert stale["current"] == revised["current"]

    root = tmp_path / "semantic-roundtrip"
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "semantic-roundtrip-configure", "configure")
        submitted = call(
            owner,
            "semantic-roundtrip-submit",
            "submit",
            kernel="cognition.field",
            state=public_initial,
            arguments=observation,
            steps=1,
        )
        assert submitted["receipt"]["run"]["status"] == "running"
        paused_digest = owner.state.computers[0].state_sha256
        paused_generation = owner.state.generation
    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.computers[0].state_sha256 == paused_digest
        replayed = call(
            owner,
            "semantic-roundtrip-submit",
            "submit",
            kernel="cognition.field",
            state=public_initial,
            arguments=observation,
            steps=1,
        )
        assert replayed["receipt"] == submitted["receipt"]
        assert replayed["checkpoint_receipt"]["replayed"] is True
        assert owner.state.generation == paused_generation
        call(owner, "semantic-roundtrip-advance", "advance", steps=64)
        inspection = owner.state.computers[0].inspect()
        assert inspection["status"] == "halted"
        assert inspection["consumed_result"]["joint_belief"]["id"] == (
            "joint:crossing"
        )
        public_task = inspection["task"]
        assert list(public_task["indexes"]["deliveries"]) == ["delivery:joint"]
        assert list(public_task["indexes"]["events"]) == ["event:joint"]
        assert len(public_task["ledger"]["operation_receipts"]) == 2
        assert public_task["records"]["event:joint"][-1]["payload"][
            "measurement_program"
        ] == measurement_program
        final_digest = owner.state.state_sha256
        final_task = copy.deepcopy(public_task)
        assert inspection["resource_ledger"]["dispatches"] > 0
        assert inspection["field_bytes"] > 0
    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.state_sha256 == final_digest
        assert computer_task(owner) == final_task


def test_semantic_mechanism_coverage_causal_meanings_and_planner_contract() -> None:
    from cassi_field_cognition import semantic_cognition_state
    from cassi_field_program import semantic_program_payload

    state = semantic_cognition_state()
    episodes = [
        {
            "episode_id": f"episode:{action}",
            "state": {},
            "action": {"u": action},
            "context": {"site": "bench"},
            "interval": {"duration": 1.0},
            "next": {"y": action},
            "intervention": True,
            "collection": {
                "available_actions": [{"u": 0}, {"u": 1}],
                "policy_version": "policy:1",
                "selected_action": {"u": action},
                "selection_assumptions": [],
                "selection_mode": "deterministic",
            },
        }
        for action in (0, 1)
    ]
    state, learned = _semantic_step(
        state,
        operation="learn-mechanism",
        operation_id="learn-action-law",
        mechanism_id="action-law",
        episodes=episodes,
        identification={
            "assumptions": ["controlled bench"],
            "controlled_variables": ["u"],
            "design": "controlled-intervention",
        },
    )
    assert learned["status"] == "supported"
    assert learned["causal_authority"] is True
    population = state["records"]["action-law"][-1]["payload"][
        "outcome_population"
    ]
    assert population == {
        "attempt_count": 2,
        "holdout_attempt_count": 0,
        "observed_and_scored_count": 2,
        "outcome_status_counts": {"observed-and-scored": 2},
        "policy_versions": ["policy:1"],
        "training_attempt_count": 2,
        "unknown_selection_count": 0,
        "unresolved_count": 0,
    }
    state, prediction = _semantic_step(
        state,
        operation="predict",
        operation_id="predict-action",
        prediction_id="prediction:action",
        mechanism_id="action-law",
        state={},
        action={"u": 1},
        context={"site": "bench"},
        interval={"duration": 1.0},
    )
    assert prediction["status"] == "supported"
    assert prediction["alternatives"][0]["values"] == {"y": 1}
    frozen_prediction = prediction["prediction"]
    state, intervention = _semantic_step(
        state,
        operation="query",
        operation_id="causal-action",
        query={
            "kind": "causal",
            "meaning": "intervention",
            "mechanism_id": "action-law",
            "action": {"u": 1},
            "context": {"site": "bench"},
            "interval": {"duration": 1.0},
        },
    )
    assert intervention["status"] == "supported"
    assert intervention["causal_authority"] is True

    unchanged = copy.deepcopy(state)
    with pytest.raises(FieldIntelligenceError) as invalid_plan:
        _semantic_step(
            state,
            operation="plan",
            operation_id="plan-without-world-model",
            plan_id="plan:invalid",
            goal={"y": 1},
            target="synthetic",
            scope="test",
            candidates=[{"action": {"u": 1}}],
        )
    assert invalid_plan.value.code == "INVALID_PLAN"
    assert state == unchanged

    with pytest.raises(FieldIntelligenceError) as invalid_policy:
        _semantic_step(
            state,
            operation="learn-mechanism",
            operation_id="bad-randomization",
            mechanism_id="bad-randomization",
            episodes=[
                {
                    "state": {},
                    "action": {"u": 0},
                    "next": {"y": 0},
                    "collection": {
                        "selection_mode": "randomized",
                        "selected_action": {"u": 0},
                    },
                }
            ],
            candidates=[
                {
                    "candidate_id": "identity",
                    "program": semantic_program_payload(
                        program_kind="identity", body={}
                    ),
                }
            ],
        )
    assert invalid_policy.value.code == "INVALID_MECHANISM_EVIDENCE"
    assert state == unchanged
    assert (
        state["records"][frozen_prediction["id"]][
            frozen_prediction["content_version"] - 1
        ]["status"]
        == "active"
    )
    confounded_episodes = [
        {
            "state": {},
            "action": {"u": action},
            "context": {"site": f"site-{action}"},
            "interval": {},
            "next": {"y": action},
            "intervention": True,
            "collection": {
                "available_actions": [{"u": 0}, {"u": 1}],
                "policy_version": "policy:confounded",
                "selected_action": {"u": action},
                "selection_mode": "deterministic",
            },
        }
        for action in (0, 1)
    ]
    state, confounded = _semantic_step(
        state,
        operation="learn-mechanism",
        operation_id="learn-confounded-law",
        mechanism_id="confounded-law",
        episodes=confounded_episodes,
        identification={
            "assumptions": [],
            "controlled_variables": ["u"],
            "design": "controlled-intervention",
        },
    )
    assert confounded["causal_authority"] is False
    assert (
        "no-action-overlap-within-context"
        in confounded["identification_limitations"]
    )
    state, unsupported_intervention = _semantic_step(
        state,
        operation="query",
        operation_id="query-confounded-intervention",
        query={
            "kind": "causal",
            "meaning": "intervention",
            "mechanism_id": "confounded-law",
            "action": {"u": 1},
            "context": {"site": "site-1"},
            "interval": {},
        },
    )
    assert unsupported_intervention["status"] == "non-identifiable"
    assert unsupported_intervention["causal_authority"] is False


def test_semantic_prediction_preserves_set_probability_and_model_family() -> None:
    from cassi_field_cognition import semantic_cognition_state
    from cassi_field_program import semantic_program_payload

    state = semantic_cognition_state()
    joint_cases = {
        "set": {
            "joint_semantics": "constraint-set",
            "joint_alternatives": [
                {"assignment": {"x": 0}},
                {"assignment": {"x": 1}},
            ],
        },
        "probability": {
            "joint_semantics": "probability",
            "joint_model": {
                "model_id": "coin:model:1",
                "observation_law": "direct-x",
                "prior_or_frequency_basis": "coin-prior:1",
                "reference_population": "coin-trials:1",
            },
            "joint_alternatives": [
                {"assignment": {"x": 0}, "weight": 0.7},
                {"assignment": {"x": 1}, "weight": 0.3},
            ],
        },
        "family": {
            "joint_semantics": "model-family",
            "joint_alternatives": [
                {"assignment": {"x": 0}, "model": "model:low"},
                {"assignment": {"x": 1}, "model": "model:high"},
            ],
        },
    }
    for name, joint in joint_cases.items():
        state, _ = _semantic_step(
            state,
            operation="observe",
            operation_id=f"observe-{name}-joint",
            delivery_id=f"delivery:{name}",
            event_id=f"event:{name}",
            joint_id=f"joint:{name}",
            **joint,
        )
    state, learned = _semantic_step(
        state,
        operation="learn-mechanism",
        operation_id="learn-identity-law",
        mechanism_id="identity-law",
        episodes=[
            {
                "state": {},
                "action": {},
                "context": {},
                "interval": {},
                "next": {},
                "collection": {"selection_mode": "unknown"},
            }
        ],
        candidates=[
            {
                "candidate_id": "identity",
                "program": semantic_program_payload(
                    program_kind="identity", body={}
                ),
            }
        ],
    )
    assert learned["status"] == "supported"

    predictions = {}
    for name in joint_cases:
        state, predicted = _semantic_step(
            state,
            operation="predict",
            operation_id=f"predict-{name}",
            prediction_id=f"prediction:{name}",
            mechanism_id="identity-law",
            joint_id=f"joint:{name}",
            state={},
            action={},
            context={},
            interval={},
        )
        predictions[name] = predicted
    set_prediction = predictions["set"]
    assert set_prediction["prediction_semantics"] == "constraint-set"
    assert all("weight" not in row for row in set_prediction["alternatives"])
    assert {row["values"]["x"] for row in set_prediction["alternatives"]} == {
        0,
        1,
    }
    probability_prediction = predictions["probability"]
    assert probability_prediction["prediction_semantics"] == "probability"
    assert [
        row["weight"] for row in probability_prediction["alternatives"]
    ] == [0.7, 0.3]
    family_prediction = predictions["family"]
    assert family_prediction["prediction_semantics"] == "model-family"
    assert {
        row["model_path"][0]["model_ids"][0]
        for row in family_prediction["alternatives"]
    } == {"model:low", "model:high"}
    assert all(
        "weight" not in row for row in family_prediction["alternatives"]
    )

    assessments = {}
    for name in joint_cases:
        state, assessed = _semantic_step(
            state,
            operation="assess-prediction",
            operation_id=f"assess-{name}",
            prediction_id=f"prediction:{name}",
            event_id="event:set",
            actual={"x": 0},
        )
        assessments[name] = assessed["assessment_metrics"]
    assert assessments["set"]["scoring_rule"] == "set-coverage"
    assert assessments["set"]["set_size"] == 2
    assert assessments["set"]["coverage"] is True
    assert assessments["probability"]["loss"] == pytest.approx(0.3)
    assert (
        assessments["probability"]["probability_score_status"]
        == "proper-score-unavailable-without-observation-density"
    )
    assert (
        assessments["family"]["scoring_rule"]
        == "model-family-unaggregated"
    )
    assert len(assessments["family"]["model_conditional_losses"]) == 2
def test_semantic_predictive_state_freezes_signature_and_first_split() -> None:
    from cassi_field_cognition import semantic_cognition_state
    from cassi_field_program import execute_semantic_program

    state = semantic_cognition_state()
    signature = {
        "clock_boundary": {
            "decision_clock": "world",
            "outcome_clock": "world",
        },
        "collection_boundary": {
            "availability": "all-attempts",
            "policy_version": "policy:predictive:1",
        },
        "comparison_metric": "exact-equality",
        "horizon": 1,
        "interval": {"duration": 1.0},
        "output_measure": {"coordinates": ["y"], "kind": "json"},
        "prediction_semantics": "constraint-set",
        "probability_model": None,
        "tolerance": 0.0,
        "units": {"y": "unitless"},
    }
    state, learned = _semantic_step(
        state,
        operation="learn-predictive-state",
        operation_id="learn-predictive-split",
        representation_id="predictive:split",
        signature=signature,
        window=1,
        examples=[
            {
                "history": ["left"],
                "future": {"y": 0},
                "question": "next",
            },
            {
                "history": ["right"],
                "future": {"y": 1},
                "question": "next",
            },
        ],
    )
    assert learned["status"] == "supported"
    assert learned["prediction_semantics"] == "constraint-set"
    assert len(learned["splits"]) == 1
    split = learned["splits"][0]
    assert split["first_separating_test"] == {
        "action": {},
        "context": {},
        "question": "next",
    }
    assert split["split_mapping"]["left"] != split["split_mapping"]["right"]
    state, queried = _semantic_step(
        state,
        operation="query",
        operation_id="query-predictive-left",
        query={
            "kind": "predictive-state",
            "representation_id": "predictive:split",
            "history": ["left"],
            "question": "next",
            "signature": signature,
        },
    )
    assert queried["status"] == "supported"
    assert queried["prediction_semantics"] == "constraint-set"
    assert queried["answer"] == {"y": 0}
    assert "weight" not in queried["alternatives"][0]

    representation = state["records"]["predictive:split"][-1]
    execution = execute_semantic_program(
        representation["payload"]["program"],
        {
            "history": ["left"],
            "question": "next",
            "signature": signature,
        },
        action={},
        context={},
    )
    assert execution["status"] == "supported"
    assert execution["values"] == {"y": 0}
    assert execution["uncertainty_semantics"] == "constraint-set"

    mismatched_signature = {**signature, "horizon": 2}
    state, mismatch = _semantic_step(
        state,
        operation="query",
        operation_id="query-predictive-wrong-horizon",
        query={
            "kind": "predictive-state",
            "representation_id": "predictive:split",
            "history": ["left"],
            "question": "next",
            "signature": mismatched_signature,
        },
    )
    assert mismatch["status"] == "support-gap"
    assert mismatch["limitations"] == ["predictive-signature-mismatch"]




def test_semantic_weighted_mechanism_requires_named_probability_model() -> None:
    from cassi_field_cognition import semantic_cognition_state
    from cassi_field_program import semantic_program_payload

    state = semantic_cognition_state()
    identity = semantic_program_payload(program_kind="identity", body={})
    hybrid = semantic_program_payload(
        program_kind="hybrid",
        body={
            "mode_key": "mode",
            "modes": {"high": identity, "low": identity},
            "mode_weights": {"high": 0.75, "low": 0.25},
            "transitions": [],
        },
    )
    candidate = {
        "candidate_id": "weighted-hybrid",
        "latent_prior": {"high": 0.75, "low": 0.25},
        "program": hybrid,
    }
    episode = {
        "state": {"mode": "high"},
        "action": {},
        "context": {},
        "interval": {},
        "next": {"mode": "high"},
        "collection": {"selection_mode": "unknown"},
    }
    unchanged = copy.deepcopy(state)
    with pytest.raises(FieldIntelligenceError) as missing_model:
        _semantic_step(
            state,
            operation="learn-mechanism",
            operation_id="learn-weighted-without-model",
            mechanism_id="weighted-law",
            episodes=[episode],
            candidates=[candidate],
        )
    assert missing_model.value.code == "INVALID_PROBABILITY_MODEL"
    assert state == unchanged

    probability_model = {
        "model_id": "regime-mixture:1",
        "observation_law": "mode-observed-without-error",
        "prior_or_frequency_basis": "declared-regime-prior:1",
        "reference_population": "weighted-law-deployments:1",
    }
    state, learned = _semantic_step(
        state,
        operation="learn-mechanism",
        operation_id="learn-weighted-with-model",
        mechanism_id="weighted-law",
        episodes=[episode],
        candidates=[{**candidate, "probability_model": probability_model}],
    )
    assert learned["status"] == "supported"
    assert learned["probability_model"] == probability_model
    state, predicted = _semantic_step(
        state,
        operation="predict",
        operation_id="predict-weighted-law",
        prediction_id="prediction:weighted-law",
        mechanism_id="weighted-law",
        state={},
        action={},
        context={},
        interval={},
    )
    assert predicted["status"] == "alternatives"
    assert predicted["prediction_semantics"] == "probability"
    weighted = {
        row["values"]["mode"]: row["weight"]
        for row in predicted["alternatives"]
    }
    assert weighted == {"high": 0.75, "low": 0.25}
    assert predicted["probability_models"] == [
        {
            "model": probability_model,
            "source": learned["mechanism"],
        }
    ]


def test_semantic_owner_pause_authority_assessment_and_exact_reopen(
    tmp_path,
) -> None:
    from cassi_field_cognition import semantic_cognition_state
    from cassi_field_owner import AuthorityGrant

    root = tmp_path / "semantic-owner"
    observe = {
        "operation": "observe",
        "operation_id": "observe-start",
        "delivery_id": "delivery:start",
        "event_id": "event:start",
        "time": {"start": 1.0, "end": 1.0},
        "observations": [
            {
                "binding_id": "binding:x",
                "subject": "world",
                "attribute": "x",
                "value": 0,
            },
            {
                "binding_id": "binding:y",
                "subject": "world",
                "attribute": "y",
                "value": 0,
            },
        ],
    }
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "semantic-owner-configure", "configure")
        started = call(
            owner,
            "semantic-owner-submit",
            "submit",
            kernel="cognition.field",
            state=semantic_cognition_state(),
            arguments=observe,
            steps=1,
        )
        assert started["receipt"]["run"]["status"] == "running"
        paused = owner.state.computers[0].state_sha256

    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.computers[0].state_sha256 == paused
        call(owner, "semantic-owner-observe-finish", "advance", steps=16)
        episodes = [
            {
                "state": {},
                "action": {"u": action},
                "next": {"y": action},
                "intervention": True,
                "collection": {
                    "available_actions": [{"u": 0}, {"u": 1}],
                    "policy_version": "policy:owner",
                    "selected_action": {"u": action},
                    "selection_mode": "deterministic",
                },
            }
            for action in (0, 1)
        ]
        call(
            owner,
            "semantic-owner-learn",
            "invoke",
            arguments={
                "operation": "learn-mechanism",
                "operation_id": "owner-learn",
                "mechanism_id": "owner-law",
                "episodes": episodes,
                "identification": {
                    "assumptions": [],
                    "controlled_variables": ["u"],
                    "design": "controlled-intervention",
                },
            },
            steps=64,
        )
        affordance_payload = {
            "program_role": "affordance",
            "program": semantic_program_payload(
                program_kind="procedure",
                body={"steps": [{"kind": "set-u"}]},
                max_work=1,
            ),
            "argument_roles": [
                {
                    "name": "u",
                    "value_type": "integer",
                    "units": "flag",
                    "bounds": {"min": 0, "max": 1},
                    "binding_constraints": {},
                    "required": True,
                }
            ],
            "preconditions": {
                "observable": [],
                "latent": [],
                "semantics": "set",
                "probability_model": None,
            },
            "execution": {
                "duration": {"lower": 0.0, "upper": 1.0, "units": "step"},
                "termination_conditions": [],
                "concurrency": {"mode": "exclusive"},
                "resource_occupancy": [],
            },
            "effects": {
                "intended": {"y": 1},
                "possible_side_effects": [],
                "expected_observations": ["y"],
                "failure_modes": [],
            },
            "action_context_support": [],
            "reversibility": {"mode": "reversible", "compensation": None},
            "risk": {
                "minimum": 0.0,
                "units": "risk-score",
                "possible_harms": [],
            },
            "obligations": {
                "disclosure": [],
                "source_access": [],
                "authority": ["test"],
            },
        }
        call(
            owner,
            "semantic-owner-affordance",
            "invoke",
            arguments={
                "operation": "register",
                "operation_id": "owner-register-affordance",
                "kind": "Program",
                "record_id": "affordance:set-u",
                "payload": affordance_payload,
            },
            steps=64,
        )
        call(
            owner,
            "semantic-owner-plan",
            "invoke",
            arguments={
                "operation": "plan",
                "operation_id": "owner-plan",
                "plan_id": "plan:owner",
                "goal": {"y": 1},
                "target": "synthetic-world",
                "scope": "test",
                "causal_required": True,
                "state": {},
                "candidates": [
                    {
                        "action": {"u": 0},
                        "affordance_id": "affordance:set-u",
                        "mechanism_id": "owner-law",
                    },
                    {
                        "action": {"u": 1},
                        "affordance_id": "affordance:set-u",
                        "mechanism_id": "owner-law",
                    },
                ],
            },
            steps=64,
        )
        proposal = owner.state.computers[0].inspect()["consumed_result"][
            "proposal"
        ]
        assert proposal["status"] == "proposed"
        assert proposal["operation_id"] == proposal["proposal_id"]
        assert proposal["episode_id"] == proposal["proposal_id"]
        assert proposal["model"]["id"] == "owner-law"
        assert proposal["affordance"]["id"] == "affordance:set-u"
        assert proposal["expected_observation_window"] == {
            "start": 2.0,
            "end": 2.0,
        }
        assert [row["phase"] for row in proposal["phases"]] == ["proposed"]

        authorize_arguments = {
            "operation": "authorize-action",
            "operation_id": "owner-authorize",
            "proposal_id": proposal["proposal_id"],
        }
        before_unauthorized = owner.state.state_sha256
        with pytest.raises(FieldIntelligenceError) as unauthorized:
            call(
                owner,
                "semantic-owner-unauthorized",
                "invoke",
                arguments=authorize_arguments,
                steps=64,
            )
        assert unauthorized.value.code == "AUTHORITY_REQUIRED"
        assert owner.state.state_sha256 == before_unauthorized

        grant = AuthorityGrant(
            grant_id="semantic-owner-grant",
            issuer="test-host",
            generation=0,
            operation="computer-effect",
            target="synthetic-world",
            scope="test",
            one_use=True,
        )
        call(
            owner,
            "semantic-owner-authorize",
            "authorized-invoke",
            arguments=authorize_arguments,
            grant=grant.as_dict(),
            target="synthetic-world",
            scope="test",
            steps=64,
        )
        authorized = owner.state.computers[0].inspect()["consumed_result"]
        assert authorized["proposal"]["status"] == "authorized"
        assert authorized["proposal"]["authorization"]["grant_id"] == (
            grant.grant_id
        )

        dispatch_arguments = {
            "operation": "dispatch-action",
            "operation_id": "owner-dispatch",
            "proposal_id": proposal["proposal_id"],
            "adapter_id": "test-adapter",
            "dispatch_id": "dispatch:owner",
            "idempotency": "unknown",
            "idempotency_key": "effect:owner",
        }
        before_unprivileged_dispatch = owner.state.state_sha256
        with pytest.raises(FieldIntelligenceError) as unprivileged_dispatch:
            call(
                owner,
                "semantic-owner-unprivileged-dispatch",
                "invoke",
                arguments=dispatch_arguments,
                steps=64,
            )
        assert unprivileged_dispatch.value.code == "AUTHORITY_REQUIRED"
        assert owner.state.state_sha256 == before_unprivileged_dispatch

        dispatched = call(
            owner,
            "semantic-owner-dispatch",
            "authorized-invoke",
            arguments=dispatch_arguments,
            grant=grant.as_dict(),
            target="synthetic-world",
            scope="test",
            steps=64,
        )
        dispatch_result = owner.state.computers[0].inspect()[
            "consumed_result"
        ]
        assert dispatch_result["proposal"]["status"] == "dispatch-uncertain"
        assert dispatch_result["blind_retry_permitted"] is False
        assert dispatch_result["reconciliation_required"] is True
        dispatch_generation = owner.state.generation
        dispatch_replay = call(
            owner,
            "semantic-owner-dispatch",
            "authorized-invoke",
            arguments=dispatch_arguments,
            grant=grant.as_dict(),
            target="synthetic-world",
            scope="test",
            steps=64,
        )
        assert dispatch_replay["receipt"] == dispatched["receipt"]
        assert owner.state.generation == dispatch_generation

        call(
            owner,
            "semantic-owner-track",
            "invoke",
            arguments={
                "operation": "track-action",
                "operation_id": "owner-track",
                "proposal_id": proposal["proposal_id"],
                "tracking_id": "track:owner",
                "status": "unknown",
                "adapter_receipt": {"poll": "no-definitive-result"},
                "progress": {"completed": 0, "total": 1},
                "effect_count": {"lower": 0, "upper": 1},
            },
            steps=64,
        )
        call(
            owner,
            "semantic-owner-cancel",
            "invoke",
            arguments={
                "operation": "cancel-action",
                "operation_id": "owner-cancel",
                "proposal_id": proposal["proposal_id"],
                "cancellation_id": "cancel:owner",
                "reason": "test interruption",
            },
            steps=64,
        )
        cancelled = owner.state.computers[0].inspect()["consumed_result"]
        assert cancelled["proposal"]["status"] == "cancel-requested"
        assert cancelled["effect_prevention_confirmed"] is False
        assert cancelled["obligation"]["status"] == "active"
        assert cancelled["phase"]["effect_count"] == {"lower": 0, "upper": 1}

        call(
            owner,
            "semantic-owner-acknowledgment",
            "invoke",
            arguments={
                "operation": "acknowledgment",
                "operation_id": "owner-acknowledgment",
                "event_id": "event:owner-outcome",
                "proposal_id": proposal["proposal_id"],
                "status": "succeeded",
                "observation": {"y": 1},
                "observation_verified": True,
                "transport_receipt": {"adapter_status": "delivered"},
            },
            steps=64,
        )
        acknowledged = owner.state.computers[0].inspect()[
            "consumed_result"
        ]
        assert acknowledged["proposal"]["status"] == "acknowledged"
        assert acknowledged["assessment_required"] is True
        assert acknowledged["transport_is_world_observation"] is True
        assert acknowledged["proposal"]["assessment"] is None
        assert acknowledged["obligation"]["status"] == "active"

        assessment_arguments = {
            "operation": "assess-prediction",
            "operation_id": "owner-assessment",
            "event_id": "event:owner-outcome",
            "prediction_id": proposal["prediction"]["id"],
            "actual": {"y": 1},
            "source": "verified-action-outcome",
        }
        assessed = call(
            owner,
            "semantic-owner-assessment",
            "invoke",
            arguments=assessment_arguments,
            steps=64,
        )
        result = owner.state.computers[0].inspect()["consumed_result"]
        assert result["loss"] == 0.0
        assert result["action_proposal"]["status"] == "assessed"
        assert result["prediction"]["content_version"] == 2
        assert result["obligation"]["status"] == "resolved"
        phases = result["action_proposal"]["phases"]
        assert [row["phase"] for row in phases] == [
            "proposed",
            "authorized",
            "dispatch-uncertain",
            "tracked",
            "cancel-requested",
            "acknowledged",
            "assessed",
        ]
        assert all(
            row["operation_id"] == proposal["proposal_id"] for row in phases
        )
        assert all(row["receipt_rho"] for row in phases)
        generation = owner.state.generation
        replay = call(
            owner,
            "semantic-owner-assessment",
            "invoke",
            arguments=assessment_arguments,
            steps=64,
        )
        assert replay["receipt"] == assessed["receipt"]
        assert owner.state.generation == generation
        final_digest = owner.state.state_sha256
        final_task = copy.deepcopy(computer_task(owner))
    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.state_sha256 == final_digest
        assert computer_task(owner) == final_task


def test_semantic_owner_forms_curiosity_goal_from_observation(tmp_path):
    from cassi_field_cognition import semantic_cognition_state

    root = tmp_path / "semantic-curiosity-owner"
    observe = {
        "operation": "observe",
        "operation_id": "owner-curiosity-observe",
        "delivery_id": "delivery:owner-curiosity",
        "event_id": "event:owner-curiosity",
        "time": {"start": 1.0, "end": 1.0},
        "observations": [{
            "binding_id": "binding:temperature",
            "subject": "world",
            "attribute": "temperature",
            "value": 21.0,
        }],
    }
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "curiosity-owner-configure", "configure")
        call(
            owner,
            "curiosity-owner-submit",
            "submit",
            kernel="cognition.field",
            state=semantic_cognition_state(),
            arguments=observe,
            steps=1,
        )
        call(owner, "curiosity-owner-observe", "advance", steps=16)
        call(
            owner,
            "curiosity-owner-agenda",
            "invoke",
            arguments={
                "operation": "autonomous-agenda",
                "operation_id": "owner-curiosity-agenda",
                "max_items": 1,
                "observation_channels": [
                    {
                        "channel_id": "owner:generic",
                        "provides": ["shape"],
                        "cost": 5.0,
                        "reliability": 0.1,
                        "request": {"adapter": "generic"},
                    },
                    {
                        "channel_id": "owner:temperature",
                        "provides": ["temperature"],
                        "cost": 0.1,
                        "reliability": 0.9,
                        "request": {"adapter": "thermometer", "scope": "ambient"},
                    },
                ],
            },
            steps=128,
        )
        result = owner.state.computers[0].inspect()["consumed_result"]
        assert result["status"] == "supported"
        assert result["curiosity_goal_count"] >= 1
        assert result["selected"]["kind"] == "active-perception"
        assert result["selected"]["request"]["channel_id"] == "owner:temperature"
        assert result["perception_event"]["kind"] == "Event"


def test_owner_executes_active_perception_through_world_adapter(tmp_path):
    from cassi_field_cognition import semantic_cognition_state

    root = tmp_path / "active-perception-world-loop"
    channels = [
        {
            "channel_id": "owner:temperature",
            "provides": ["temperature"],
            "cost": 0.1,
            "reliability": 0.9,
            "request": {"adapter": "thermometer", "scope": "ambient"},
        },
        {
            "channel_id": "owner:generic",
            "provides": ["shape"],
            "cost": 5.0,
            "reliability": 0.1,
            "request": {"adapter": "generic"},
        },
    ]
    transition_calls = []

    def transition(action, target, payload):
        transition_calls.append({"action": action, "target": target, "payload": dict(payload)})
        return WorldAcknowledgment(
            acknowledgment_id="ack:owner-active-perception",
            operation_id="owner-active-perception:adapter",
            status="succeeded",
            observed_values={"temperature": 22.53},
            context={"instrument": "thermometer", "scope": "ambient"},
            source_content=canonical_json_bytes({
                "channel_id": target,
                "observed_values": {"temperature": 22.53},
            }),
        )

    def run(owner, adapter):
        call(owner, "world-loop-configure", "configure")
        call(
            owner,
            "world-loop-seed",
            "submit",
            kernel="cognition.field",
            state=semantic_cognition_state(),
            arguments={
                "operation": "observe",
                "operation_id": "world-loop-seed",
                "delivery_id": "delivery:world-loop-seed",
                "event_id": "event:world-loop-seed",
                "observations": [{
                    "binding_id": "binding:temperature",
                    "subject": "world",
                    "attribute": "temperature",
                    "value": 21.0,
                }],
            },
            steps=1,
        )
        call(owner, "world-loop-seed-advance", "advance", steps=16)
        call(
            owner,
            "world-loop-agenda",
            "invoke",
            arguments={
                "operation": "autonomous-agenda",
                "operation_id": "world-loop-agenda",
                "max_items": 1,
                "observation_channels": channels,
            },
            steps=128,
        )
        agenda = owner.state.computers[0].inspect()["consumed_result"]
        selected = agenda["selected"]["request"]
        result = owner.execute_observation_request(
            operation_id="owner-active-perception",
            observation_request=selected,
            adapter=adapter,
            observation_channels=channels,
            expected_state_sha256=owner.state.state_sha256,
        )
        return result, selected

    adapter = DeterministicWorldAdapter(transition, adapter_id="owner-world")
    with FieldIntelligenceOwner(root) as owner:
        first, selected = run(owner, adapter)
        assert first["status"] == "supported"
        assert selected["channel_id"] == "owner:temperature"
        assert first["observation"]["status"] == "supported"
        assert first["evidence"]["source"]["status"] == "active"
        assert transition_calls[0]["action"] == "observe"
        assert transition_calls[0]["target"] == "owner:temperature"
        assert adapter.execute_count == 1
        assert len(transition_calls) == 1
        digest = owner.state.state_sha256
        replay = owner.execute_observation_request(
            operation_id="owner-active-perception",
            observation_request=selected,
            adapter=adapter,
            observation_channels=channels,
            expected_state_sha256=digest,
        )
        assert replay["replayed"] is True
        assert adapter.execute_count == 1
        assert len(transition_calls) == 1
        assert owner.state.state_sha256 == digest

    reopened_adapter = DeterministicWorldAdapter(transition, adapter_id="owner-world")
    with FieldIntelligenceOwner(root) as owner:
        replay = owner.execute_observation_request(
            operation_id="owner-active-perception",
            observation_request=selected,
            adapter=reopened_adapter,
            observation_channels=channels,
            expected_state_sha256=owner.state.state_sha256,
        )
        assert replay["replayed"] is True
        assert reopened_adapter.execute_count == 0
        assert len(transition_calls) == 1


def test_owner_calibrates_noise_verdict_boundaries(
    tmp_path,
) -> None:
    root = tmp_path / "noise-boundary-owner"
    from cassi_field_cognition import semantic_cognition_state

    offsets = [0.05, 0.5, 1.0, 2.0, 4.0]
    trajectory = [1.0, 2.1, 4.0, 8.1, *[16.2 + offset for offset in offsets]]
    calls: list[dict[str, object]] = []

    def transition(action, target, payload):
        index = len(calls)
        value = trajectory[index]
        calls.append(
            {"action": action, "target": target, "payload": dict(payload)}
        )
        return WorldAcknowledgment(
            acknowledgment_id=f"ack:noise-boundary:{index}",
            operation_id=f"noise-boundary-frame-{index}:adapter",
            status="succeeded",
            observed_values={"x": value},
            context={"source": "noise-boundary-sweep"},
            source_content=canonical_json_bytes(
                {"frame": index, "observed_values": {"x": value}}
            ),
        )

    adapter = DeterministicWorldAdapter(
        transition,
        adapter_id="noise-boundary-world",
    )
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "noise-boundary-configure", "configure")
        call(
            owner,
            "noise-boundary-seed",
            "submit",
            kernel="cognition.field",
            state=semantic_cognition_state(),
            arguments={
                "operation": "observe",
                "operation_id": "noise-boundary-seed",
                "delivery_id": "delivery:noise-boundary-seed",
                "event_id": "event:noise-boundary-seed",
                "observations": [
                    {
                        "binding_id": "binding:noise-boundary-seed",
                        "subject": "world",
                        "attribute": "x",
                        "value": 1.0,
                    }
                ],
            },
            steps=1,
        )
        call(
            owner,
            "noise-boundary-seed-advance",
            "advance",
            steps=16,
        )

        frames = [
            owner.execute_observation_request(
                operation_id=f"noise-boundary-frame-{index}",
                observation_request={
                    "channel_id": f"world:x:noise-boundary:{index}",
                    "goal": {"kind": "one-step-transition"},
                    "provides": ["x"],
                    "request": {"instrument": "deterministic"},
                },
                adapter=adapter,
                expected_state_sha256=owner.state.state_sha256,
            )
            for index in range(len(trajectory))
        ]
        learned = owner.learn_observed_transition(
            operation_id="noise-boundary-fit",
            observations=frames[:4],
            variables=["x"],
            expected_state_sha256=owner.state.state_sha256,
        )
        results = [
            owner.score_observed_transition(
                operation_id=f"noise-boundary-score-{index}",
                learned=learned,
                predecessor=frames[3],
                outcome=frames[4 + index],
                expected_state_sha256=owner.state.state_sha256,
                retain_ratio=2.0,
                reject_ratio=4.0,
            )
            for index in range(len(offsets))
        ]
        statuses = [result["status"] for result in results]
        ratios = [result["model"]["ratio"] for result in results]
        normalized_errors = [
            result["model"]["normalized_error"] for result in results
        ]
        assert statuses == ["retain", "refine", "reject", "reject", "reject"]
        assert ratios == sorted(ratios)
        assert normalized_errors == sorted(normalized_errors)
        assert ratios[0] < 2.0 <= ratios[1] < 4.0 <= ratios[2]
        assert all(
            result["assessment"]["status"] == "supported"
            for result in results
        )
        assert len(calls) == len(trajectory)

def test_owner_calibrates_coupled_coordinate_noise(
    tmp_path,
) -> None:
    root = tmp_path / "coupled-noise-boundary-owner"
    from cassi_field_cognition import semantic_cognition_state

    candidates = [
        ("x-small", (32.55, 34.45)),
        ("x-refine", (32.8, 34.45)),
        ("x-reject", (33.0, 34.45)),
        ("y-refine", (32.55, 34.65)),
        ("xy-refine", (32.8, 34.65)),
    ]
    trajectory = [
        (1.0, 3.0),
        (2.05, 4.05),
        (4.0, 6.2),
        (8.1, 10.1),
        (16.25, 18.2),
        *(values for _, values in candidates),
    ]
    calls: list[dict[str, object]] = []

    def transition(action, target, payload):
        index = len(calls)
        x, y = trajectory[index]
        calls.append(
            {"action": action, "target": target, "payload": dict(payload)}
        )
        return WorldAcknowledgment(
            acknowledgment_id=f"ack:coupled-noise:{index}",
            operation_id=f"coupled-noise-frame-{index}:adapter",
            status="succeeded",
            observed_values={"x": x, "y": y},
            context={"source": "coupled-coordinate-noise"},
            source_content=canonical_json_bytes(
                {
                    "frame": index,
                    "observed_values": {"x": x, "y": y},
                }
            ),
        )

    adapter = DeterministicWorldAdapter(
        transition,
        adapter_id="coupled-coordinate-noise-world",
    )
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "coupled-noise-configure", "configure")
        call(
            owner,
            "coupled-noise-seed",
            "submit",
            kernel="cognition.field",
            state=semantic_cognition_state(),
            arguments={
                "operation": "observe",
                "operation_id": "coupled-noise-seed",
                "delivery_id": "delivery:coupled-noise-seed",
                "event_id": "event:coupled-noise-seed",
                "observations": [
                    {
                        "binding_id": "binding:coupled-noise-seed:x",
                        "subject": "world",
                        "attribute": "x",
                        "value": 1.0,
                    },
                    {
                        "binding_id": "binding:coupled-noise-seed:y",
                        "subject": "world",
                        "attribute": "y",
                        "value": 3.0,
                    },
                ],
            },
            steps=1,
        )
        call(owner, "coupled-noise-seed-advance", "advance", steps=16)
        frames = [
            owner.execute_observation_request(
                operation_id=f"coupled-noise-frame-{index}",
                observation_request={
                    "channel_id": f"world:xy:coupled-noise:{index}",
                    "goal": {"kind": "one-step-transition"},
                    "provides": ["x", "y"],
                    "request": {"instrument": "deterministic"},
                },
                adapter=adapter,
                expected_state_sha256=owner.state.state_sha256,
            )
            for index in range(len(trajectory))
        ]
        learned = owner.learn_observed_transition(
            operation_id="coupled-noise-fit",
            observations=frames[:5],
            variables=["x", "y"],
            expected_state_sha256=owner.state.state_sha256,
        )
        results = [
            owner.score_observed_transition(
                operation_id=f"coupled-noise-score-{index}",
                learned=learned,
                predecessor=frames[4],
                outcome=frames[5 + index],
                expected_state_sha256=owner.state.state_sha256,
                retain_ratio=2.0,
                reject_ratio=4.0,
            )
            for index in range(len(candidates))
        ]
        robust_result = owner.score_observed_transition(
            operation_id="coupled-noise-score-robust",
            learned=learned,
            predecessor=frames[4],
            outcome=frames[5],
            expected_state_sha256=owner.state.state_sha256,
            retain_ratio=2.0,
            reject_ratio=4.0,
            residual_envelope="median_mad",
        )
        assert results[0]["model"]["residual_envelope"] == "maximum"
        assert robust_result["model"]["residual_envelope"] == "median_mad"
        assert robust_result["model"]["predicted"] == results[0]["model"][
            "predicted"
        ]
        assert robust_result["model"]["actual"] == results[0]["model"]["actual"]
        assert robust_result["model"]["prediction_id"] != results[0]["model"][
            "prediction_id"
        ]
        robust_assessment_id = robust_result["assessment"]["prediction"]["id"]
        robust_assessment_record = owner.state.computers[0].inspect()["task"][
            "records"
        ][robust_assessment_id][-1]
        robust_source = robust_assessment_record["derivation"]["source"]
        assert robust_source["residual_envelope"] == "median_mad"
        assert robust_source["training_residual_envelope"] == pytest.approx(
            robust_result["model"]["training_residual_envelope"]
        )
        assert [result["status"] for result in results] == [
            "retain",
            "refine",
            "reject",
            "refine",
            "refine",
        ]
        x_small_errors = results[0]["model"]["normalized_errors"]
        x_refine_errors = results[1]["model"]["normalized_errors"]
        y_refine_errors = results[3]["model"]["normalized_errors"]
        xy_refine_errors = results[4]["model"]["normalized_errors"]
        assert x_refine_errors["x"] > x_small_errors["x"]
        assert x_refine_errors["y"] == pytest.approx(x_small_errors["y"])
        assert y_refine_errors["y"] > x_small_errors["y"]
        assert y_refine_errors["x"] == pytest.approx(x_small_errors["x"])
        assert xy_refine_errors["x"] > x_small_errors["x"]
        assert xy_refine_errors["y"] > x_small_errors["y"]
        assert all(
            result["assessment"]["status"] == "supported"
            for result in results
        )
        assert len(calls) == len(trajectory)

def test_owner_auto_selects_residual_envelope_from_tail_diagnostic(
    tmp_path,
) -> None:
    from cassi_field_cognition import semantic_cognition_state

    def run_case(name: str, trajectory: list[float]):
        root = tmp_path / f"auto-envelope-{name}"
        calls: list[dict[str, object]] = []

        def transition(action, target, payload):
            index = len(calls)
            value = trajectory[index]
            calls.append(
                {"action": action, "target": target, "payload": dict(payload)}
            )
            return WorldAcknowledgment(
                acknowledgment_id=f"ack:auto-envelope:{name}:{index}",
                operation_id=f"auto-envelope-{name}-frame-{index}:adapter",
                status="succeeded",
                observed_values={"x": value},
                context={"source": "auto-envelope-tail-diagnostic"},
                source_content=canonical_json_bytes(
                    {"frame": index, "observed_values": {"x": value}}
                ),
            )

        adapter = DeterministicWorldAdapter(
            transition,
            adapter_id=f"auto-envelope-{name}-world",
        )
        with FieldIntelligenceOwner(root) as owner:
            call(owner, f"auto-envelope-{name}-configure", "configure")
            call(
                owner,
                f"auto-envelope-{name}-seed",
                "submit",
                kernel="cognition.field",
                state=semantic_cognition_state(),
                arguments={
                    "operation": "observe",
                    "operation_id": f"auto-envelope-{name}-seed",
                    "delivery_id": f"delivery:auto-envelope-{name}-seed",
                    "event_id": f"event:auto-envelope-{name}-seed",
                    "observations": [
                        {
                            "binding_id": f"binding:auto-envelope-{name}:x",
                            "subject": "world",
                            "attribute": "x",
                            "value": trajectory[0],
                        }
                    ],
                },
                steps=1,
            )
            call(
                owner,
                f"auto-envelope-{name}-seed-advance",
                "advance",
                steps=16,
            )
            frames = [
                owner.execute_observation_request(
                    operation_id=f"auto-envelope-{name}-frame-{index}",
                    observation_request={
                        "channel_id": f"world:x:auto-envelope:{name}:{index}",
                        "goal": {"kind": "one-step-transition"},
                        "provides": ["x"],
                        "request": {"instrument": "deterministic"},
                    },
                    adapter=adapter,
                    expected_state_sha256=owner.state.state_sha256,
                )
                for index in range(len(trajectory))
            ]
            learned = owner.learn_observed_transition(
                operation_id=f"auto-envelope-{name}-fit",
                observations=frames[:6],
                variables=["x"],
                include_intercept=False,
                expected_state_sha256=owner.state.state_sha256,
            )
            result = owner.score_observed_transition(
                operation_id=f"auto-envelope-{name}-score",
                learned=learned,
                predecessor=frames[5],
                outcome=frames[6],
                expected_state_sha256=owner.state.state_sha256,
                residual_envelope="auto",
            )
            assessment_id = result["assessment"]["prediction"]["id"]
            assessment_record = owner.state.computers[0].inspect()["task"][
                "records"
            ][assessment_id][-1]
            return result, assessment_record["derivation"]["source"]


    ordinary, ordinary_source = run_case(
        "ordinary",
        [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0],
    )
    heavy, heavy_source = run_case(
        "heavy",
        [1.0, 2.0, 4.0, 8.0, 40.0, 16.0, 32.0],
    )

    assert ordinary["model"]["residual_envelope"] == "maximum"
    assert ordinary["model"]["residual_envelope_request"] == "auto"
    assert ordinary["model"]["tail_diagnostic"]["heavy_tail"] is False
    assert heavy["model"]["residual_envelope"] == "median_mad"
    assert heavy["model"]["residual_envelope_request"] == "auto"
    assert heavy["model"]["tail_diagnostic"]["heavy_tail"] is True
    assert heavy["model"]["tail_diagnostic"]["sample_count"] == 5
    assert heavy_source["residual_envelope"] == "median_mad"
    assert heavy_source["residual_envelope_request"] == "auto"
    assert heavy_source["tail_diagnostic"] == heavy["model"]["tail_diagnostic"]
    assert ordinary["assessment"]["status"] == "supported"
    assert heavy["assessment"]["status"] == "supported"


def test_owner_stabilizes_verdicts_across_bounded_noise_shapes(
    tmp_path,
) -> None:
    from cassi_field_cognition import semantic_cognition_state

    shapes = [
        ("x+", (1.0, 0.0)),
        ("x-", (-1.0, 0.0)),
        ("y+", (0.0, 1.0)),
        ("y-", (0.0, -1.0)),
        ("both+", (1.0, 1.0)),
        ("cross+", (1.0, -1.0)),
        ("cross-", (-1.0, 1.0)),
        ("both-", (-1.0, -1.0)),
    ]
    expected_statuses = {
        0.05: ["retain"] * len(shapes),
        0.2: [
            "retain",
            "refine",
            "refine",
            "retain",
            "refine",
            "retain",
            "refine",
            "refine",
        ],
        0.5: ["reject"] * len(shapes),
    }

    def run_amplitude(amplitude: float):
        tag = str(amplitude).replace(".", "_")
        candidates = [
            (32.5 + amplitude * x, 34.45 + amplitude * y)
            for _, (x, y) in shapes
        ]
        trajectory = [
            (1.0, 3.0),
            (2.05, 4.05),
            (4.0, 6.2),
            (8.1, 10.1),
            (16.25, 18.2),
            *candidates,
        ]
        calls: list[dict[str, object]] = []

        def transition(action, target, payload):
            index = len(calls)
            x, y = trajectory[index]
            calls.append(
                {
                    "action": action,
                    "target": target,
                    "payload": dict(payload),
                }
            )
            return WorldAcknowledgment(
                acknowledgment_id=f"ack:bounded-noise:{tag}:{index}",
                operation_id=f"bounded-noise-{tag}-frame-{index}:adapter",
                status="succeeded",
                observed_values={"x": x, "y": y},
                context={"source": "bounded-noise-realization"},
                source_content=canonical_json_bytes(
                    {
                        "frame": index,
                        "observed_values": {"x": x, "y": y},
                    }
                ),
            )

        adapter = DeterministicWorldAdapter(
            transition,
            adapter_id=f"bounded-noise-world-{tag}",
        )
        with FieldIntelligenceOwner(tmp_path / f"amplitude-{tag}") as owner:
            call(owner, f"bounded-noise-{tag}-configure", "configure")
            call(
                owner,
                f"bounded-noise-{tag}-seed",
                "submit",
                kernel="cognition.field",
                state=semantic_cognition_state(),
                arguments={
                    "operation": "observe",
                    "operation_id": f"bounded-noise-{tag}-seed",
                    "delivery_id": f"delivery:bounded-noise:{tag}",
                    "event_id": f"event:bounded-noise:{tag}",
                    "observations": [
                        {
                            "binding_id": f"binding:bounded-noise:{tag}:x",
                            "subject": "world",
                            "attribute": "x",
                            "value": 1.0,
                        },
                        {
                            "binding_id": f"binding:bounded-noise:{tag}:y",
                            "subject": "world",
                            "attribute": "y",
                            "value": 3.0,
                        },
                    ],
                },
                steps=1,
            )
            call(
                owner,
                f"bounded-noise-{tag}-advance",
                "advance",
                steps=16,
            )
            frames = [
                owner.execute_observation_request(
                    operation_id=f"bounded-noise-{tag}-frame-{index}",
                    observation_request={
                        "channel_id": f"world:xy:bounded-noise:{tag}:{index}",
                        "goal": {"kind": "one-step-transition"},
                        "provides": ["x", "y"],
                        "request": {"instrument": "deterministic"},
                    },
                    adapter=adapter,
                    expected_state_sha256=owner.state.state_sha256,
                )
                for index in range(len(trajectory))
            ]
            learned = owner.learn_observed_transition(
                operation_id=f"bounded-noise-{tag}-fit",
                observations=frames[:5],
                variables=["x", "y"],
                expected_state_sha256=owner.state.state_sha256,
            )
            results = [
                owner.score_observed_transition(
                    operation_id=f"bounded-noise-{tag}-score-{index}",
                    learned=learned,
                    predecessor=frames[4],
                    outcome=frames[5 + index],
                    expected_state_sha256=owner.state.state_sha256,
                    retain_ratio=2.0,
                    reject_ratio=4.0,
                )
                for index in range(len(shapes))
            ]
            assert len(calls) == len(trajectory)
            return results

    for amplitude, expected in expected_statuses.items():
        results = run_amplitude(amplitude)
        assert [result["status"] for result in results] == expected
        ratios = [result["model"]["ratio"] for result in results]
        assert min(ratios) >= 0.0
        assert all(
            result["assessment"]["status"] == "supported"
            for result in results
        )


def test_owner_estimates_seeded_bounded_noise_frequencies(
    tmp_path,
) -> None:
    import random

    from cassi_field_cognition import semantic_cognition_state

    amplitudes = [0.05, 0.2, 0.5]
    expected_counts = {
        0.05: {"retain": 8, "refine": 0, "reject": 0},
        0.2: {"retain": 3, "refine": 5, "reject": 0},
        0.5: {"retain": 0, "refine": 3, "reject": 5},
    }
    rng = random.Random(20260918)
    shapes = [
        (rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0))
        for _ in range(8)
    ]

    def run_amplitude(amplitude: float):
        tag = str(amplitude).replace(".", "_")
        candidates = [
            (32.5 + amplitude * x, 34.45 + amplitude * y)
            for x, y in shapes
        ]
        trajectory = [
            (1.0, 3.0),
            (2.05, 4.05),
            (4.0, 6.2),
            (8.1, 10.1),
            (16.25, 18.2),
            *candidates,
        ]
        calls: list[dict[str, object]] = []

        def transition(action, target, payload):
            index = len(calls)
            x, y = trajectory[index]
            calls.append(
                {
                    "action": action,
                    "target": target,
                    "payload": dict(payload),
                }
            )
            return WorldAcknowledgment(
                acknowledgment_id=f"ack:seeded-ensemble:{tag}:{index}",
                operation_id=f"seeded-ensemble-{tag}-frame-{index}:adapter",
                status="succeeded",
                observed_values={"x": x, "y": y},
                context={"source": "seeded-bounded-noise"},
                source_content=canonical_json_bytes(
                    {
                        "frame": index,
                        "observed_values": {"x": x, "y": y},
                    }
                ),
            )

        adapter = DeterministicWorldAdapter(
            transition,
            adapter_id=f"seeded-ensemble-world-{tag}",
        )
        with FieldIntelligenceOwner(tmp_path / f"ensemble-{tag}") as owner:
            call(owner, f"seeded-ensemble-{tag}-configure", "configure")
            call(
                owner,
                f"seeded-ensemble-{tag}-seed",
                "submit",
                kernel="cognition.field",
                state=semantic_cognition_state(),
                arguments={
                    "operation": "observe",
                    "operation_id": f"seeded-ensemble-{tag}-seed",
                    "delivery_id": f"delivery:seeded-ensemble:{tag}",
                    "event_id": f"event:seeded-ensemble:{tag}",
                    "observations": [
                        {
                            "binding_id": f"binding:seeded-ensemble:{tag}:x",
                            "subject": "world",
                            "attribute": "x",
                            "value": 1.0,
                        },
                        {
                            "binding_id": f"binding:seeded-ensemble:{tag}:y",
                            "subject": "world",
                            "attribute": "y",
                            "value": 3.0,
                        },
                    ],
                },
                steps=1,
            )
            call(
                owner,
                f"seeded-ensemble-{tag}-advance",
                "advance",
                steps=16,
            )
            frames = [
                owner.execute_observation_request(
                    operation_id=f"seeded-ensemble-{tag}-frame-{index}",
                    observation_request={
                        "channel_id": f"world:xy:seeded-ensemble:{tag}:{index}",
                        "goal": {"kind": "one-step-transition"},
                        "provides": ["x", "y"],
                        "request": {"instrument": "deterministic"},
                    },
                    adapter=adapter,
                    expected_state_sha256=owner.state.state_sha256,
                )
                for index in range(len(trajectory))
            ]
            learned = owner.learn_observed_transition(
                operation_id=f"seeded-ensemble-{tag}-fit",
                observations=frames[:5],
                variables=["x", "y"],
                expected_state_sha256=owner.state.state_sha256,
            )
            results = [
                owner.score_observed_transition(
                    operation_id=f"seeded-ensemble-{tag}-score-{index}",
                    learned=learned,
                    predecessor=frames[4],
                    outcome=frames[5 + index],
                    expected_state_sha256=owner.state.state_sha256,
                    retain_ratio=2.0,
                    reject_ratio=4.0,
                )
                for index in range(len(shapes))
            ]
            assert len(calls) == len(trajectory)
            return results

    for amplitude in amplitudes:
        results = run_amplitude(amplitude)
        statuses = [result["status"] for result in results]
        counts = {
            status: statuses.count(status)
            for status in ("retain", "refine", "reject")
        }
        assert counts == expected_counts[amplitude]
        assert all(
            result["assessment"]["status"] == "supported"
            for result in results
        )

def test_owner_estimates_noise_frequencies_across_independent_seeds(
    tmp_path,
) -> None:
    import math
    import random

    from cassi_field_cognition import semantic_cognition_state

    seeds = [20260918, 20260919, 20260920]
    amplitudes = [0.05, 0.2, 0.5]
    expected_counts = {
        20260918: {
            0.05: {"retain": 8, "refine": 0, "reject": 0},
            0.2: {"retain": 3, "refine": 5, "reject": 0},
            0.5: {"retain": 0, "refine": 3, "reject": 5},
        },
        20260919: {
            0.05: {"retain": 8, "refine": 0, "reject": 0},
            0.2: {"retain": 3, "refine": 5, "reject": 0},
            0.5: {"retain": 0, "refine": 2, "reject": 6},
        },
        20260920: {
            0.05: {"retain": 8, "refine": 0, "reject": 0},
            0.2: {"retain": 5, "refine": 3, "reject": 0},
            0.5: {"retain": 1, "refine": 3, "reject": 4},
        },
    }
    shapes_by_seed = {}
    for seed in seeds:
        rng = random.Random(seed)
        shapes_by_seed[seed] = [
            (rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0))
            for _ in range(8)
        ]

    def wilson_interval(successes: int, total: int) -> tuple[float, float]:
        z = 1.96
        proportion = successes / total
        denominator = 1.0 + z * z / total
        center = (
            proportion + z * z / (2.0 * total)
        ) / denominator
        half_width = (
            z
            * math.sqrt(
                proportion * (1.0 - proportion) / total
                + z * z / (4.0 * total * total)
            )
            / denominator
        )
        return center - half_width, center + half_width

    def run_case(seed: int, amplitude: float):
        tag = f"{seed}-{str(amplitude).replace('.', '_')}"
        shapes = shapes_by_seed[seed]
        candidates = [
            (32.5 + amplitude * x, 34.45 + amplitude * y)
            for x, y in shapes
        ]
        trajectory = [
            (1.0, 3.0),
            (2.05, 4.05),
            (4.0, 6.2),
            (8.1, 10.1),
            (16.25, 18.2),
            *candidates,
        ]
        calls: list[dict[str, object]] = []

        def transition(action, target, payload):
            index = len(calls)
            x, y = trajectory[index]
            calls.append(
                {
                    "action": action,
                    "target": target,
                    "payload": dict(payload),
                }
            )
            return WorldAcknowledgment(
                acknowledgment_id=f"ack:seed-confidence:{tag}:{index}",
                operation_id=f"seed-confidence-{tag}-frame-{index}:adapter",
                status="succeeded",
                observed_values={"x": x, "y": y},
                context={"source": "seed-confidence-ensemble"},
                source_content=canonical_json_bytes(
                    {
                        "frame": index,
                        "observed_values": {"x": x, "y": y},
                    }
                ),
            )

        adapter = DeterministicWorldAdapter(
            transition,
            adapter_id=f"seed-confidence-world-{tag}",
        )
        with FieldIntelligenceOwner(tmp_path / f"confidence-{tag}") as owner:
            call(owner, f"seed-confidence-{tag}-configure", "configure")
            call(
                owner,
                f"seed-confidence-{tag}-seed",
                "submit",
                kernel="cognition.field",
                state=semantic_cognition_state(),
                arguments={
                    "operation": "observe",
                    "operation_id": f"seed-confidence-{tag}-seed",
                    "delivery_id": f"delivery:seed-confidence:{tag}",
                    "event_id": f"event:seed-confidence:{tag}",
                    "observations": [
                        {
                            "binding_id": f"binding:seed-confidence:{tag}:x",
                            "subject": "world",
                            "attribute": "x",
                            "value": 1.0,
                        },
                        {
                            "binding_id": f"binding:seed-confidence:{tag}:y",
                            "subject": "world",
                            "attribute": "y",
                            "value": 3.0,
                        },
                    ],
                },
                steps=1,
            )
            call(
                owner,
                f"seed-confidence-{tag}-advance",
                "advance",
                steps=16,
            )
            frames = [
                owner.execute_observation_request(
                    operation_id=f"seed-confidence-{tag}-frame-{index}",
                    observation_request={
                        "channel_id": f"world:xy:seed-confidence:{tag}:{index}",
                        "goal": {"kind": "one-step-transition"},
                        "provides": ["x", "y"],
                        "request": {"instrument": "deterministic"},
                    },
                    adapter=adapter,
                    expected_state_sha256=owner.state.state_sha256,
                )
                for index in range(len(trajectory))
            ]
            learned = owner.learn_observed_transition(
                operation_id=f"seed-confidence-{tag}-fit",
                observations=frames[:5],
                variables=["x", "y"],
                expected_state_sha256=owner.state.state_sha256,
            )
            results = [
                owner.score_observed_transition(
                    operation_id=f"seed-confidence-{tag}-score-{index}",
                    learned=learned,
                    predecessor=frames[4],
                    outcome=frames[5 + index],
                    expected_state_sha256=owner.state.state_sha256,
                    retain_ratio=2.0,
                    reject_ratio=4.0,
                )
                for index in range(len(shapes))
            ]
            assert len(calls) == len(trajectory)
            return results

    aggregate = {
        amplitude: {"retain": 0, "refine": 0, "reject": 0}
        for amplitude in amplitudes
    }
    for seed in seeds:
        for amplitude in amplitudes:
            results = run_case(seed, amplitude)
            statuses = [result["status"] for result in results]
            counts = {
                status: statuses.count(status)
                for status in ("retain", "refine", "reject")
            }
            assert counts == expected_counts[seed][amplitude]
            for status, count in counts.items():
                aggregate[amplitude][status] += count
            assert all(
                result["assessment"]["status"] == "supported"
                for result in results
            )

    assert aggregate == {
        0.05: {"retain": 24, "refine": 0, "reject": 0},
        0.2: {"retain": 11, "refine": 13, "reject": 0},
        0.5: {"retain": 1, "refine": 8, "reject": 15},
    }
    intervals = {
        amplitude: {
            status: wilson_interval(count, 24)
            for status, count in counts.items()
        }
        for amplitude, counts in aggregate.items()
    }
    assert intervals[0.05]["retain"][0] > 0.8
    assert intervals[0.2]["refine"][0] > 0.3
    assert intervals[0.5]["reject"][0] > 0.4

def test_owner_detects_heavy_tail_noise_across_independent_seeds(
    tmp_path,
) -> None:
    import math
    import random

    from cassi_field_cognition import semantic_cognition_state

    seeds = [20260918, 20260919, 20260920, 20260921, 20260922]
    amplitudes = [0.2, 0.5]
    expected_counts = {
        20260918: {
            0.2: {"retain": 0, "refine": 1, "reject": 7},
            0.5: {"retain": 0, "refine": 0, "reject": 8},
        },
        20260919: {
            0.2: {"retain": 1, "refine": 1, "reject": 6},
            0.5: {"retain": 0, "refine": 1, "reject": 7},
        },
        20260920: {
            0.2: {"retain": 2, "refine": 1, "reject": 5},
            0.5: {"retain": 0, "refine": 1, "reject": 7},
        },
        20260921: {
            0.2: {"retain": 2, "refine": 0, "reject": 6},
            0.5: {"retain": 0, "refine": 2, "reject": 6},
        },
        20260922: {
            0.2: {"retain": 2, "refine": 2, "reject": 4},
            0.5: {"retain": 1, "refine": 1, "reject": 6},
        },
    }

    robust_expected_counts = {
        20260918: {
            0.2: {"retain": 1, "refine": 4, "reject": 3},
            0.5: {"retain": 0, "refine": 0, "reject": 8},
        },
        20260919: {
            0.2: {"retain": 1, "refine": 2, "reject": 5},
            0.5: {"retain": 1, "refine": 0, "reject": 7},
        },
        20260920: {
            0.2: {"retain": 3, "refine": 2, "reject": 3},
            0.5: {"retain": 0, "refine": 3, "reject": 5},
        },
        20260921: {
            0.2: {"retain": 2, "refine": 2, "reject": 4},
            0.5: {"retain": 1, "refine": 1, "reject": 6},
        },
        20260922: {
            0.2: {"retain": 3, "refine": 2, "reject": 3},
            0.5: {"retain": 1, "refine": 2, "reject": 5},
        },
    }

    def clipped_cauchy(rng: random.Random) -> float:
        value = math.tan(math.pi * (rng.random() - 0.5))
        return max(-4.0, min(4.0, value))

    shapes_by_seed = {}
    for seed in seeds:
        rng = random.Random(seed)
        shapes_by_seed[seed] = [
            (clipped_cauchy(rng), clipped_cauchy(rng))
            for _ in range(8)
        ]

    def run_case(seed: int, amplitude: float):
        tag = f"{seed}-{str(amplitude).replace('.', '_')}"
        candidates = [
            (32.5 + amplitude * x, 34.45 + amplitude * y)
            for x, y in shapes_by_seed[seed]
        ]
        trajectory = [
            (1.0, 3.0),
            (2.05, 4.05),
            (4.0, 6.2),
            (8.1, 10.1),
            (16.25, 18.2),
            *candidates,
        ]
        calls: list[dict[str, object]] = []

        def transition(action, target, payload):
            index = len(calls)
            x, y = trajectory[index]
            calls.append(
                {
                    "action": action,
                    "target": target,
                    "payload": dict(payload),
                }
            )
            return WorldAcknowledgment(
                acknowledgment_id=f"ack:heavy-tail:{tag}:{index}",
                operation_id=f"heavy-tail-{tag}-frame-{index}:adapter",
                status="succeeded",
                observed_values={"x": x, "y": y},
                context={"source": "clipped-cauchy-noise"},
                source_content=canonical_json_bytes(
                    {
                        "frame": index,
                        "observed_values": {"x": x, "y": y},
                    }
                ),
            )

        adapter = DeterministicWorldAdapter(
            transition,
            adapter_id=f"heavy-tail-world-{tag}",
        )
        with FieldIntelligenceOwner(tmp_path / f"heavy-tail-{tag}") as owner:
            call(owner, f"heavy-tail-{tag}-configure", "configure")
            call(
                owner,
                f"heavy-tail-{tag}-seed",
                "submit",
                kernel="cognition.field",
                state=semantic_cognition_state(),
                arguments={
                    "operation": "observe",
                    "operation_id": f"heavy-tail-{tag}-seed",
                    "delivery_id": f"delivery:heavy-tail:{tag}",
                    "event_id": f"event:heavy-tail:{tag}",
                    "observations": [
                        {
                            "binding_id": f"binding:heavy-tail:{tag}:x",
                            "subject": "world",
                            "attribute": "x",
                            "value": 1.0,
                        },
                        {
                            "binding_id": f"binding:heavy-tail:{tag}:y",
                            "subject": "world",
                            "attribute": "y",
                            "value": 3.0,
                        },
                    ],
                },
                steps=1,
            )
            call(
                owner,
                f"heavy-tail-{tag}-advance",
                "advance",
                steps=16,
            )
            frames = [
                owner.execute_observation_request(
                    operation_id=f"heavy-tail-{tag}-frame-{index}",
                    observation_request={
                        "channel_id": f"world:xy:heavy-tail:{tag}:{index}",
                        "goal": {"kind": "one-step-transition"},
                        "provides": ["x", "y"],
                        "request": {"instrument": "deterministic"},
                    },
                    adapter=adapter,
                    expected_state_sha256=owner.state.state_sha256,
                )
                for index in range(len(trajectory))
            ]
            learned = owner.learn_observed_transition(
                operation_id=f"heavy-tail-{tag}-fit",
                observations=frames[:5],
                variables=["x", "y"],
                expected_state_sha256=owner.state.state_sha256,
            )
            results = []
            robust_results = []
            for index in range(8):
                score = owner.score_observed_transition(
                    operation_id=f"heavy-tail-{tag}-score-{index}",
                    learned=learned,
                    predecessor=frames[4],
                    outcome=frames[5 + index],
                    expected_state_sha256=owner.state.state_sha256,
                    retain_ratio=2.0,
                    reject_ratio=4.0,
                )
                robust_score = owner.score_observed_transition(
                    operation_id=f"heavy-tail-{tag}-robust-score-{index}",
                    learned=learned,
                    predecessor=frames[4],
                    outcome=frames[5 + index],
                    expected_state_sha256=owner.state.state_sha256,
                    retain_ratio=2.0,
                    reject_ratio=4.0,
                    residual_envelope="median_mad",
                )
                assert robust_score["model"]["residual_envelope"] == (
                    "median_mad"
                )
                results.append(score)
                robust_results.append(robust_score)
            assert len(calls) == len(trajectory)
            return results, robust_results

    aggregate = {
        amplitude: {"retain": 0, "refine": 0, "reject": 0}
        for amplitude in amplitudes
    }
    robust_aggregate = {
        amplitude: {"retain": 0, "refine": 0, "reject": 0}
        for amplitude in amplitudes
    }
    for seed in seeds:
        for amplitude in amplitudes:
            results, robust_results = run_case(seed, amplitude)
            statuses = [result["status"] for result in results]
            counts = {
                status: statuses.count(status)
                for status in ("retain", "refine", "reject")
            }
            robust_statuses = [
                result["status"] for result in robust_results
            ]
            robust_counts = {
                status: robust_statuses.count(status)
                for status in ("retain", "refine", "reject")
            }
            assert counts == expected_counts[seed][amplitude]
            assert robust_counts == robust_expected_counts[seed][amplitude]
            for status, count in counts.items():
                aggregate[amplitude][status] += count
            for status, count in robust_counts.items():
                robust_aggregate[amplitude][status] += count
            assert all(
                result["assessment"]["status"] == "supported"
                for result in robust_results
            )
            assert all(
                result["assessment"]["status"] == "supported"
                for result in results
            )

    assert aggregate == {
        0.2: {"retain": 7, "refine": 5, "reject": 28},
        0.5: {"retain": 1, "refine": 5, "reject": 34},
    }
    assert robust_aggregate == {
        0.2: {"retain": 10, "refine": 12, "reject": 18},
        0.5: {"retain": 3, "refine": 6, "reject": 31},
    }
    assert aggregate[0.2]["reject"] > robust_aggregate[0.2]["reject"]
    assert aggregate[0.5]["reject"] > robust_aggregate[0.5]["reject"]
    assert robust_aggregate[0.2]["refine"] > aggregate[0.2]["refine"]
def _semantic_parameter_fixture(event_count: int = 6):
    from cassi_field_cognition import semantic_cognition_state
    from cassi_field_program import semantic_program_payload

    state = semantic_cognition_state()
    state, _ = _semantic_step(
        state,
        operation="learn-mechanism",
        operation_id="parameter-fixture-mechanism",
        mechanism_id="parameter-law",
        episodes=[
            {
                "state": {},
                "action": {},
                "context": {},
                "interval": {},
                "next": {},
                "collection": {"selection_mode": "unknown"},
            }
        ],
        candidates=[
            {
                "candidate_id": "identity",
                "program": semantic_program_payload(
                    program_kind="identity", body={}
                ),
            }
        ],
    )
    events = []
    for index in range(event_count):
        state, admitted = _semantic_step(
            state,
            operation="observe",
            operation_id=f"parameter-fixture-observe-{index}",
            delivery_id=f"parameter-delivery:{index}",
            event_id=f"parameter-event:{index}",
            observations=[
                {
                    "binding_id": f"binding:parameter:{index}",
                    "subject": "parameter-fixture",
                    "attribute": f"sample-{index}",
                    "value": index,
                }
            ],
        )
        events.append(admitted["event"])
    return state, events


def test_semantic_parameter_statistics_analytic_family_and_deduplication() -> None:
    state, events = _semantic_parameter_fixture()
    probability_model = {
        "model_id": "parameter-family:1",
        "observation_law": "declared-marginal-likelihood",
        "prior_or_frequency_basis": "declared-equal-prior",
        "reference_population": "parameter-fixture-events",
    }
    interpretation = {
        "assumptions": ["fully-observed"],
        "likelihood_or_compatibility": "linear-sufficient-statistics",
        "probability_model": None,
        "semantics": "compatibility",
    }
    contributions = [
        {
            "contribution_id": "linear-row:1",
            "evidence": events[0],
            "values": {
                "x": 1.0,
                "y": 2.0,
                "candidate_likelihoods": {
                    "constant": 0.2,
                    "linear": 0.8,
                },
            },
        },
        {
            "contribution_id": "linear-row:2",
            "evidence": events[1],
            "values": {
                "x": 2.0,
                "y": 4.0,
                "candidate_likelihoods": {
                    "constant": 0.1,
                    "linear": 0.9,
                },
            },
        },
    ]
    activation_transition = state["ledger"]["transitions"] + 1
    request = {
        "operation": "learn-parameters",
        "operation_id": "learn-linear-parameters",
        "mechanism_id": "parameter-law",
        "parameter_set_id": "linear-parameters",
        "parameter_path": "observed-sufficient-statistics",
        "variables": ["x", "y"],
        "design_variables": ["x"],
        "target_variables": ["y"],
        "interpretation": interpretation,
        "evidence_prefix": events[:2],
        "contributions": contributions,
        "family_update": {
            "activation_transition": activation_transition,
            "candidate_family_version": "family:linear:1",
            "candidates": [
                {"candidate_id": "constant", "prior_mass": 0.5},
                {"candidate_id": "linear", "prior_mass": 0.5},
            ],
            "probability_model": probability_model,
            "update_semantics": "fixed-family",
        },
    }
    state, learned = _semantic_step(state, **request)
    parameter_state = learned["parameter_set"]["state"]
    assert parameter_state["count"] == 2
    assert parameter_state["parameters"] == {"y": {"x": 2.0}}
    assert parameter_state["identified"] is True
    family = learned["candidate_family"]
    masses = {
        row["candidate_id"]: row["mass"] for row in family["candidates"]
    }
    assert masses["linear"] == pytest.approx(0.72 / 0.74)
    assert masses["constant"] == pytest.approx(0.02 / 0.74)
    mechanism_version = learned["mechanism"]["content_version"]
    record_count = sum(len(history) for history in state["records"].values())

    replay_request = {
        **request,
        "operation_id": "learn-linear-parameters-reprocessed",
        "family_update": {
            **request["family_update"],
            "candidates": [
                {
                    "candidate_id": candidate_id,
                    "prior_mass": masses[candidate_id],
                }
                for candidate_id in ("constant", "linear")
            ],
        },
    }
    state, replayed = _semantic_step(state, **replay_request)
    assert replayed["reused_evidence"] is True
    assert replayed["assessment"] is None
    assert replayed["mechanism"]["content_version"] == mechanism_version
    assert sum(len(history) for history in state["records"].values()) == record_count

    state, rank_deficient = _semantic_step(
        state,
        operation="learn-parameters",
        operation_id="learn-rank-deficient",
        mechanism_id="parameter-law",
        parameter_set_id="rank-deficient",
        parameter_path="observed-sufficient-statistics",
        variables=["x", "y"],
        design_variables=["x"],
        target_variables=["y"],
        interpretation=interpretation,
        evidence_prefix=[events[2]],
        contributions=[
            {
                "contribution_id": "zero-input",
                "evidence": events[2],
                "values": {"x": 0.0, "y": 7.0},
            }
        ],
    )
    assert rank_deficient["parameter_set"]["state"]["identified"] is False
    assert rank_deficient["limitations"] == ["rank-deficient-design"]
    assert rank_deficient["parameter_set"]["state"]["parameters"] == {}

    state, analytic = _semantic_step(
        state,
        operation="learn-parameters",
        operation_id="learn-beta-bernoulli",
        mechanism_id="parameter-law",
        parameter_set_id="coin-rate",
        parameter_path="analytic-local",
        analytic_rule={
            "assumptions": ["conditionally-independent-bernoulli"],
            "family": "beta-bernoulli",
            "outcome_key": "success",
            "prior": {"alpha": 1.0, "beta": 1.0},
        },
        evidence_prefix=events[3:6],
        contributions=[
            {
                "contribution_id": f"coin-row:{index}",
                "evidence": events[index + 3],
                "values": {"success": outcome},
            }
            for index, outcome in enumerate((1, 0, 1))
        ],
    )
    posterior = analytic["parameter_set"]["state"]["posterior"]
    assert posterior == {"alpha": 3.0, "beta": 2.0, "mean": 0.6}

    current_binding = state["current"]["Program"]["parameter-law"]
    with pytest.raises(FieldIntelligenceError) as wrong_kind:
        _semantic_step(
            state,
            operation="learn-parameters",
            operation_id="parameter-non-event-lineage",
            mechanism_id="parameter-law",
            parameter_set_id="invalid-lineage",
            parameter_path="analytic-local",
            analytic_rule={
                "assumptions": ["conditionally-independent-bernoulli"],
                "family": "beta-bernoulli",
                "outcome_key": "success",
                "prior": {"alpha": 1.0, "beta": 1.0},
            },
            evidence_prefix=[current_binding],
            contributions=[],
        )
    assert wrong_kind.value.code == "INVALID_SEMANTIC_REFERENCE"


def test_semantic_parameter_refinement_conserves_current_mass_and_zero_support() -> None:
    state, events = _semantic_parameter_fixture()
    finite_initial = {
        "operation": "learn-parameters",
        "operation_id": "finite-initial",
        "mechanism_id": "parameter-law",
        "parameter_set_id": "finite-theta",
        "parameter_path": "finite-alternatives",
        "alternative_semantics": "probability",
        "alternatives": [
            {
                "alternative_id": "a",
                "parameters": {"theta": 0},
                "prior_mass": 0.5,
            },
            {
                "alternative_id": "b",
                "parameters": {"theta": 1},
                "prior_mass": 0.5,
            },
        ],
        "evidence_prefix": [events[0]],
        "contributions": [
            {
                "contribution_id": "finite-row:1",
                "evidence": events[0],
                "values": {"likelihoods": {"a": 0.8, "b": 0.2}},
            }
        ],
    }
    state, finite = _semantic_step(state, **finite_initial)
    initial_rows = {
        row["alternative_id"]: row
        for row in finite["parameter_set"]["state"]["alternatives"]
    }
    assert initial_rows["a"]["mass"] == pytest.approx(0.8)
    assert initial_rows["b"]["mass"] == pytest.approx(0.2)

    state, refined = _semantic_step(
        state,
        operation="learn-parameters",
        operation_id="finite-refinement",
        mechanism_id="parameter-law",
        parameter_set_id="finite-theta",
        parameter_path="finite-alternatives",
        alternative_semantics="probability",
        alternatives=[
            {
                "alternative_id": "a-low",
                "parent_id": "a",
                "parameters": {"theta": -0.25},
                "prior_mass": 0.3,
            },
            {
                "alternative_id": "a-high",
                "parent_id": "a",
                "parameters": {"theta": 0.25},
                "prior_mass": 0.5,
            },
            {
                "alternative_id": "b",
                "parameters": {"theta": 1},
                "prior_mass": 0.2,
            },
        ],
        evidence_prefix=events[:2],
        contributions=[
            {
                "contribution_id": "finite-row:2",
                "evidence": events[1],
                "values": {
                    "likelihoods": {
                        "a-high": 1.0,
                        "a-low": 1.0,
                        "b": 1.0,
                    }
                },
            }
        ],
    )
    refined_rows = {
        row["alternative_id"]: row
        for row in refined["parameter_set"]["state"]["alternatives"]
    }
    assert refined_rows["a-low"]["mass"] == pytest.approx(0.3)
    assert refined_rows["a-high"]["mass"] == pytest.approx(0.5)
    assert refined_rows["b"]["mass"] == pytest.approx(0.2)
    assert len(refined["parameter_set"]["state"]["contribution_scores"]) == 2

    state, contradicted = _semantic_step(
        state,
        operation="learn-parameters",
        operation_id="finite-zero-support",
        mechanism_id="parameter-law",
        parameter_set_id="finite-theta",
        parameter_path="finite-alternatives",
        alternative_semantics="probability",
        alternatives=[
            {
                "alternative_id": candidate,
                "parameters": refined_rows[candidate]["parameters"],
                "prior_mass": refined_rows[candidate]["mass"],
            }
            for candidate in ("a-high", "a-low", "b")
        ],
        evidence_prefix=events[:3],
        contributions=[
            {
                "contribution_id": "finite-row:3",
                "evidence": events[2],
                "values": {
                    "likelihoods": {
                        "a-high": 0.0,
                        "a-low": 0.0,
                        "b": 0.0,
                    }
                },
            }
        ],
    )
    assert contradicted["status"] == "support-gap"
    assert contradicted["model_inadequacy"]["kind"] == "Obligation"
    assert all(
        row["mass"] is None
        for row in contradicted["parameter_set"]["state"]["alternatives"]
    )

    integration = {
        "error_rule": {"absolute": 0.0},
        "method": "exact-box-partition",
        "reference_measure": "lebesgue-theta",
        "semantics": "exact-partition",
    }
    state, continuous = _semantic_step(
        state,
        operation="learn-parameters",
        operation_id="continuous-initial",
        mechanism_id="parameter-law",
        parameter_set_id="continuous-theta",
        parameter_path="continuous-cells",
        cell_semantics="probability-measure",
        integration=integration,
        cells=[
            {
                "cell_id": "low",
                "bounds": {"theta": [0.0, 1.0]},
                "prior_mass": 0.5,
            },
            {
                "cell_id": "high",
                "bounds": {"theta": [1.0, 2.0]},
                "prior_mass": 0.5,
            },
        ],
        evidence_prefix=[events[3]],
        contributions=[
            {
                "contribution_id": "continuous-row:1",
                "evidence": events[3],
                "values": {"likelihoods": {"low": 1.0, "high": 3.0}},
            }
        ],
    )
    first_cells = {
        row["cell_id"]: row
        for row in continuous["parameter_set"]["state"]["cells"]
    }
    assert first_cells["low"]["mass"] == pytest.approx(0.25)
    assert first_cells["high"]["mass"] == pytest.approx(0.75)

    state, split = _semantic_step(
        state,
        operation="learn-parameters",
        operation_id="continuous-split",
        mechanism_id="parameter-law",
        parameter_set_id="continuous-theta",
        parameter_path="continuous-cells",
        cell_semantics="probability-measure",
        integration=integration,
        cells=[
            {
                "cell_id": "low",
                "bounds": {"theta": [0.0, 1.0]},
                "prior_mass": 0.25,
            },
            {
                "cell_id": "high-left",
                "parent_id": "high",
                "bounds": {"theta": [1.0, 1.5]},
                "prior_mass": 0.375,
            },
            {
                "cell_id": "high-right",
                "parent_id": "high",
                "bounds": {"theta": [1.5, 2.0]},
                "prior_mass": 0.375,
            },
        ],
        evidence_prefix=events[3:5],
        contributions=[
            {
                "contribution_id": "continuous-row:2",
                "evidence": events[4],
                "values": {
                    "likelihoods": {
                        "low": [0.9, 1.1],
                        "high-left": [0.9, 1.1],
                        "high-right": [0.9, 1.1],
                    }
                },
            }
        ],
    )
    split_state = split["parameter_set"]["state"]
    assert split_state["ordering"] == "unresolved"
    assert split_state["computational_uncertainty"] == [
        "likelihood-enclosure"
    ]
    assert split_state["frozen_preupdate_mass"] == {
        "high-left": 0.375,
        "high-right": 0.375,
        "low": 0.25,
    }
    assert len(split_state["contribution_likelihoods"]) == 2


def test_semantic_candidate_activation_freezes_boundary_before_new_evidence() -> None:
    state, events = _semantic_parameter_fixture(3)
    probability_model = {
        "model_id": "prospective-family:1",
        "observation_law": "declared-marginal-likelihood",
        "prior_or_frequency_basis": "explicit-family-prior",
        "reference_population": "parameter-fixture-events",
    }
    common = {
        "operation": "learn-parameters",
        "mechanism_id": "parameter-law",
        "parameter_set_id": "prospective-family",
        "parameter_path": "observed-sufficient-statistics",
        "variables": ["x", "y"],
        "design_variables": ["x"],
        "target_variables": ["y"],
        "interpretation": {
            "assumptions": ["fully-observed"],
            "likelihood_or_compatibility": "linear-sufficient-statistics",
            "probability_model": None,
            "semantics": "compatibility",
        },
    }
    state, initial = _semantic_step(
        state,
        **common,
        operation_id="prospective-family-initial",
        evidence_prefix=[events[0]],
        contributions=[
            {
                "contribution_id": "prospective-row:0",
                "evidence": events[0],
                "values": {
                    "x": 1.0,
                    "y": 2.0,
                    "candidate_likelihoods": {
                        "constant": 0.25,
                        "linear": 0.75,
                    },
                },
            }
        ],
        family_update={
            "activation_transition": state["ledger"]["transitions"] + 1,
            "candidate_family_version": "prospective-family:v1",
            "candidates": [
                {"candidate_id": "constant", "prior_mass": 0.5},
                {"candidate_id": "linear", "prior_mass": 0.5},
            ],
            "probability_model": probability_model,
            "update_semantics": "fixed-family",
        },
    )
    initial_mass = {
        row["candidate_id"]: row["mass"]
        for row in initial["candidate_family"]["candidates"]
    }
    state, activated = _semantic_step(
        state,
        **common,
        operation_id="prospective-family-activate",
        evidence_prefix=[events[0]],
        contributions=[],
        family_update={
            "activation_basis": {
                "kind": "bounded-structural-proposal",
                "source": "retained-frontier",
            },
            "activation_mass": 0.1,
            "activation_transition": state["ledger"]["transitions"] + 1,
            "candidate_family_version": "prospective-family:v2",
            "candidates": [
                {
                    "candidate_id": "constant",
                    "prior_mass": initial_mass["constant"] * 0.9,
                },
                {
                    "candidate_id": "linear",
                    "prior_mass": initial_mass["linear"] * 0.9,
                },
                {"candidate_id": "quadratic", "prior_mass": 0.1},
            ],
            "previous_family_version": "prospective-family:v1",
            "probability_model": probability_model,
            "update_semantics": "prospective-activation",
        },
    )
    family = activated["candidate_family"]
    activated_mass = {
        row["candidate_id"]: row["mass"] for row in family["candidates"]
    }
    assert activated_mass == pytest.approx(
        {
            "constant": initial_mass["constant"] * 0.9,
            "linear": initial_mass["linear"] * 0.9,
            "quadratic": 0.1,
        }
    )
    assert family["activation"] == {
        "basis": {
            "kind": "bounded-structural-proposal",
            "source": "retained-frontier",
        },
        "evidence_count_before_activation": 1,
        "mass": 0.1,
        "new_candidate_id": "quadratic",
    }
    assert family["contribution_scores"] == []
    assert next(
        row
        for row in family["candidates"]
        if row["candidate_id"] == "quadratic"
    )["likelihood_bounds"] == [1.0, 1.0]

    with pytest.raises(FieldIntelligenceError) as invented_mass:
        _semantic_step(
            state,
            **common,
            operation_id="prospective-family-invalid-alpha",
            evidence_prefix=[events[0]],
            contributions=[],
            family_update={
                "activation_basis": {"kind": "unsupported-reweighting"},
                "activation_mass": 0.2,
                "activation_transition": state["ledger"]["transitions"] + 1,
                "candidate_family_version": "prospective-family:v3",
                "candidates": [
                    {
                        "candidate_id": "constant",
                        "prior_mass": activated_mass["constant"],
                    },
                    {
                        "candidate_id": "linear",
                        "prior_mass": activated_mass["linear"],
                    },
                    {
                        "candidate_id": "quadratic",
                        "prior_mass": activated_mass["quadratic"],
                    },
                    {"candidate_id": "cubic", "prior_mass": 0.2},
                ],
                "previous_family_version": "prospective-family:v2",
                "probability_model": probability_model,
                "update_semantics": "prospective-activation",
            },
        )
    assert invented_mass.value.code == "INVALID_PARAMETER_UPDATE"


def test_semantic_representation_uses_training_fit_after_equal_holdout() -> None:
    from cassi_field_cognition import semantic_cognition_state

    examples = [
        {
            "example_id": "train-left-1",
            "features": {"bias": 0.0, "x": 3.0, "y": 1.0},
            "outcome": "left",
        },
        {
            "example_id": "train-right-1",
            "features": {"bias": 0.0, "x": 1.0, "y": 3.0},
            "outcome": "right",
        },
        {
            "example_id": "train-left-2",
            "features": {"bias": 0.0, "x": 4.0, "y": 2.0},
            "outcome": "left",
        },
        {
            "example_id": "train-right-2",
            "features": {"bias": 0.0, "x": 2.0, "y": 4.0},
            "outcome": "right",
        },
        {
            "example_id": "train-left-3",
            "features": {"bias": 0.0, "x": 5.0, "y": 1.0},
            "outcome": "left",
        },
    ]
    holdout = [
        {
            "example_id": "holdout-left-1",
            "features": {"bias": 0.0, "x": 6.0, "y": 2.0},
            "outcome": "left",
            "rare_case": True,
        },
        {
            "example_id": "holdout-left-2",
            "features": {"bias": 0.0, "x": 7.0, "y": 3.0},
            "outcome": "left",
            "rare_case": True,
        },
    ]
    candidates = [
        {
            "candidate_id": "constant-holdout-fit",
            "edits": [],
            "output_roles": ["bias"],
            "exceptions": [],
            "frontier": {"remaining": [], "status": "evaluated"},
            "measured_cost": {},
            "parameter_initialization": {},
            "parent_refs": [],
            "proposal_history": [],
            "prospective_predictions": [],
        },
        {
            "candidate_id": "ordered-perfect-fit",
            "edits": [
                {
                    "family": "relational-variable",
                    "guard": None,
                    "relation": "order",
                    "sources": ["x", "y"],
                    "target": "ordering",
                    "tolerance": 0.0,
                    "units": "unitless",
                }
            ],
            "output_roles": ["ordering"],
            "exceptions": [],
            "frontier": {"remaining": [], "status": "evaluated"},
            "measured_cost": {},
            "parameter_initialization": {},
            "parent_refs": [],
            "proposal_history": [],
            "prospective_predictions": [],
        },
    ]

    _, learned = _semantic_step(
        semantic_cognition_state(),
        operation="learn-representation",
        operation_id="learn-equal-holdout-different-training-fit",
        representation_id="equal-holdout-different-training-fit",
        question={"target": "dominance"},
        information_boundary={"available": ["features"]},
        examples=examples,
        holdout=holdout,
        candidates=candidates,
        support_roots=["equal-holdout-training-evidence"],
    )

    by_id = {row["candidate_id"]: row for row in learned["candidates"]}
    assert learned["status"] == "supported"
    assert learned["selected_candidate"] == "ordered-perfect-fit"
    assert by_id["constant-holdout-fit"]["holdout"]["errors"] == 0
    assert by_id["constant-holdout-fit"]["training"]["errors"] == 2
    assert by_id["ordered-perfect-fit"]["training"]["errors"] == 0


def test_semantic_discovery_transfers_into_ordinary_query_and_language() -> None:
    from cassi_field_cognition import semantic_cognition_state
    from cassi_field_program import execute_semantic_program
    from cassi_field_regions import resolve_semantic_record

    state = semantic_cognition_state()
    difference = {
        "family": "relational-variable",
        "guard": None,
        "relation": "difference",
        "sources": ["x", "y"],
        "target": "delta",
        "tolerance": 0.0,
        "units": "unitless",
    }
    examples = [
        {
            "example_id": "difference:0",
            "features": {"x": 5.0, "y": 2.0},
            "outcome": "ahead",
        },
        {
            "example_id": "difference:1",
            "features": {"x": 8.0, "y": 5.0},
            "outcome": "ahead",
        },
    ]
    state, learned_representation = _semantic_step(
        state,
        operation="learn-representation",
        operation_id="learn-relative-position",
        representation_id="relative-position",
        question={"target": "relative-position"},
        information_boundary={"available": ["features"]},
        examples=examples,
        holdout=[
            {
                "example_id": "difference:holdout",
                "features": {"x": 11.0, "y": 8.0},
                "outcome": "ahead",
                "rare_case": True,
            }
        ],
        candidates=[
            {
                "candidate_id": "difference-role",
                "edits": [difference],
                "output_roles": ["delta"],
                "exceptions": [],
                "frontier": {"remaining": [], "status": "evaluated"},
                "measured_cost": {"field_steps": 1},
                "parameter_initialization": {},
                "parent_refs": [],
                "proposal_history": [
                    {"source": "repeated-equal-difference"}
                ],
                "prospective_predictions": [],
            }
        ],
        support_roots=["difference-observation"],
    )
    assert learned_representation["status"] == "supported"
    state, ordinary_use = _semantic_step(
        state,
        operation="query",
        operation_id="query-relative-position",
        query={
            "kind": "representation",
            "representation_id": "relative-position",
            "features": {"x": 20.0, "y": 17.0},
        },
    )
    assert ordinary_use["status"] == "supported"
    assert ordinary_use["answer"] == "ahead"
    assert ordinary_use["representation_output"]["encoded"]["delta"] == 3.0
    state, packet = _semantic_step(
        state,
        operation="observe",
        operation_id="observe-relative-position-packet",
        delivery_id="delivery:relative-position-packet",
        event_id="event:relative-position-packet",
        time={"start": 1.0, "end": 1.0},
        observations=[
            {
                "attribute": "x",
                "binding_id": "binding:relative-x",
                "frame": "shared-frame",
                "subject": "relative-pair",
                "units": "unitless",
                "value": 20.0,
            },
            {
                "attribute": "y",
                "binding_id": "binding:relative-y",
                "frame": "shared-frame",
                "subject": "relative-pair",
                "units": "unitless",
                "value": 17.0,
            },
        ],
    )
    packet_bindings = {
        reference["id"]: reference for reference in packet["bindings"]
    }
    state, binding_use = _semantic_step(
        state,
        operation="query",
        operation_id="query-relative-position-bindings",
        query={
            "kind": "representation",
            "representation_id": "relative-position",
            "inputs": {
                "x": {"binding": packet_bindings["binding:relative-x"]},
                "y": {"binding": packet_bindings["binding:relative-y"]},
            },
        },
    )
    assert binding_use["status"] == "supported"
    assert binding_use["answer"] == "ahead"
    assert binding_use["representation_output"]["encoded"]["delta"] == 3.0
    assert {
        row["role"]: row["binding"]
        for row in binding_use["representation_output"]["source_refs"]
    } == {
        "x": packet_bindings["binding:relative-x"],
        "y": packet_bindings["binding:relative-y"],
    }
    assert {
        row["value"]["kind"]
        for row in binding_use["representation_output"]["source_refs"]
    } == {"Value"}


    trace = lambda item, place: [
        {"op": "open", "item": item},
        {"op": "move", "item": item, "to": place},
        {"op": "check", "item": item},
        {"op": "close", "item": item},
    ]
    state, learned_procedure = _semantic_step(
        state,
        operation="learn-procedure",
        operation_id="learn-move-cycle",
        procedure_id="move-cycle",
        traces=[trace("a", "left"), trace("b", "right")],
        holdout=[trace("novel", "center")],
    )
    assert learned_procedure["status"] == "supported"
    winner = learned_procedure["candidates"][0]
    assert winner["measured_cost"]["net_saved_steps"] > 0
    procedure_record = resolve_semantic_record(
        state["records"], learned_procedure["procedure"]
    )
    transferred = execute_semantic_program(
        procedure_record["payload"]["program"],
        {},
        action={"role_0": "unseen-item", "role_1": "unseen-place"},
    )
    assert transferred["status"] == "supported"
    assert transferred["proposed_actions"] == trace(
        "unseen-item", "unseen-place"
    )
    invalid_roles = execute_semantic_program(
        procedure_record["payload"]["program"],
        {},
        action={"role_0": 7, "role_1": "unseen-place"},
    )
    assert invalid_roles["status"] == "support-gap"
    assert invalid_roles["limitations"] == ["argument-type:role_0:string"]

    construction_examples = [
        {
            "text": "the key is in the drawer",
            "bindings": {"item": "key", "place": "drawer"},
        },
        {
            "text": "the cup is in the box",
            "bindings": {"item": "cup", "place": "box"},
        },
    ]
    state, construction = _semantic_step(
        state,
        operation="learn-construction",
        operation_id="learn-location-assertion",
        construction_id="location-assertion",
        examples=construction_examples,
        meaning={
            "object": {"$role": "place"},
            "relation": "located-in",
            "subject": {"$role": "item"},
        },
        speech_act="assertion",
    )
    assert construction["status"] == "supported"
    state, interpreted = _semantic_step(
        state,
        operation="interpret",
        operation_id="interpret-novel-location",
        text="the coin is in the chest",
        speaker="bob",
        discourse_id="location-discourse",
    )
    assert interpreted["interpretation"]["content"] == {
        "object": "chest",
        "relation": "located-in",
        "subject": "coin",
    }
    assert interpreted["interpretation"]["content_status"] == (
        "speaker-attributed"
    )
    assert interpreted["interpretation"]["authority_granted"] is False
    state, perspective = _semantic_step(
        state,
        operation="update-perspective",
        operation_id="record-bob-false-belief",
        agent_id="bob",
        perspective_path=["alice", "bob"],
        updates={
            "beliefs": {"key_location": "drawer"},
            "information_access": {"move-event": False},
        },
    )
    assert perspective["world_fact_promoted"] is False
    state, attributed = _semantic_step(
        state,
        operation="query",
        operation_id="query-bob-false-belief",
        query={
            "kind": "perspective",
            "agent_id": "bob",
            "perspective_path": ["alice", "bob"],
            "category": "beliefs",
            "name": "key_location",
        },
    )
    assert attributed["answer"] == "drawer"
    assert attributed["world_fact"] is False

    state, _ = _semantic_step(
        state,
        operation="learn-construction",
        operation_id="learn-location-question",
        construction_id="location-question",
        examples=construction_examples,
        meaning={
            "object": {"$role": "place"},
            "relation": "ask-location",
            "subject": {"$role": "item"},
        },
        speech_act="question",
    )
    state, ambiguous = _semantic_step(
        state,
        operation="interpret",
        operation_id="interpret-ambiguous-location",
        text="the token is in the bin",
        speaker="bob",
        discourse_id="ambiguous-discourse",
    )
    assert ambiguous["status"] == "alternatives"
    assert ambiguous["interpretation"] is None
    assert ambiguous["separating_question"]["target"] == (
        "intended-construction"
    )


def test_semantic_affine_representation_reads_exact_binding_packet_transiently() -> None:
    from cassi_field_cognition import semantic_cognition_state
    from cassi_field_regions import resolve_semantic_record

    shared_frame = {"coordinate_system": "shared"}
    observed_temperature = {
        "availability": "partial",
        "observed_mask": ["temperature"],
        "precision": {"temperature": 0.0},
    }
    unspecified = object()

    def observation(
        identity,
        value,
        *,
        frame=unspecified,
        units=unspecified,
        measurement=unspecified,
        status="active",
    ):
        row = {
            "attribute": identity,
            "binding_id": f"binding:{identity}",
            "frame": shared_frame if frame is unspecified else frame,
            "measurement": (
                observed_temperature
                if measurement is unspecified
                else measurement
            ),
            "status": status,
            "subject": "two-view",
            "value": value,
        }
        selected_units = (
            {"temperature": "arb"} if units is unspecified else units
        )
        if selected_units is not None:
            row["units"] = selected_units
        return row

    state = semantic_cognition_state()
    state, packet = _semantic_step(
        state,
        operation="observe",
        operation_id="observe-two-view-packet",
        delivery_id="delivery:two-view-packet",
        event_id="event:two-view-packet",
        time={"start": 1.0, "end": 1.0},
        observations=[
            observation("yin", {"temperature": 3.0}),
            observation("yang", {"temperature": 1.0}),
            observation(
                "imprecise",
                {"temperature": 3.0},
                measurement={
                    "availability": "partial",
                    "observed_mask": ["temperature"],
                    "precision": {"temperature": 0.25},
                },
            ),
            observation(
                "whole-precision",
                {"temperature": 3.0},
                measurement={
                    "availability": "partial",
                    "observed_mask": ["temperature"],
                    "precision": 0.25,
                },
            ),
            observation(
                "scalar-yin",
                3.0,
                measurement={"availability": "observed", "precision": 0.25},
                units="arb",
            ),
            observation(
                "scalar-yang",
                1.0,
                measurement={"availability": "observed", "precision": 0.0},
                units="arb",
            ),
            observation(
                "no-precision",
                {"temperature": 3.0},
                measurement={
                    "availability": "partial",
                    "observed_mask": ["temperature"],
                },
            ),
            observation(
                "censored",
                {"temperature": 3.0},
                measurement={
                    "availability": "observed",
                    "censoring": {"temperature": [2.0, 4.0]},
                    "observed_mask": ["temperature"],
                    "precision": {"temperature": 0.0},
                },
            ),
            observation(
                "whole-censored",
                {"temperature": 3.0},
                measurement={
                    "availability": "observed",
                    "censoring": {"value": [2.0, 4.0]},
                    "observed_mask": ["temperature"],
                    "precision": {"temperature": 0.0},
                },
            ),
            observation(
                "unrelated-censored",
                {"hidden": 9.0, "temperature": 3.0},
                measurement={
                    "availability": "partial",
                    "censoring": {"hidden": [8.0, 10.0]},
                    "observed_mask": ["temperature"],
                    "precision": {"temperature": 0.25},
                },
            ),
            observation(
                "masked",
                {"hidden": 9.0, "temperature": 1.0},
            ),
            observation(
                "other-units",
                {"temperature": 1.0},
                units={"temperature": "other"},
            ),
            observation(
                "other-frame",
                {"temperature": 1.0},
                frame={"coordinate_system": "other"},
            ),
            observation(
                "no-units",
                {"temperature": 1.0},
                units=None,
            ),
            observation(
                "no-frame",
                {"temperature": 1.0},
                frame=None,
            ),
            observation(
                "inactive",
                {"temperature": 1.0},
                status="invalidated",
            ),
            observation("negative", {"temperature": -3.0}),
        ],
    )
    bindings = {reference["id"]: reference for reference in packet["bindings"]}
    coefficient = 1.0 / (2.0**0.5)

    def expression(yang_coefficient, *, shifted=False):
        return {
            "action_terms": {"shift": 1.0} if shifted else {},
            "bias": 0.0,
            "error": 0.1,
            "terms": {
                "features.yang": yang_coefficient * coefficient,
                "features.yin": coefficient,
            },
        }

    affine = semantic_program_payload(
        program_kind="affine",
        body={
            "clamp": {"clamped": [2.7, 2.9]},
            "outputs": {
                "clamped": expression(1.0),
                "common": expression(1.0),
                "difference": expression(-1.0),
                "outcome": expression(1.0, shifted=True),
            },
        },
        guards=[
            {
                "left": "input_metadata.yin.observed",
                "op": "eq",
                "right": True,
            },
            {
                "left": "input_metadata.yang.observed",
                "op": "eq",
                "right": True,
            },
            {
                "left": "input_metadata.yin.frame",
                "op": "eq",
                "right": shared_frame,
            },
            {
                "left": "input_metadata.yang.frame",
                "op": "eq",
                "right": shared_frame,
            },
            {
                "left": "input_metadata.yin.units",
                "op": "eq",
                "right": "arb",
            },
            {
                "left": "input_metadata.yang.units",
                "op": "eq",
                "right": "arb",
            },
            {"left": "context.mode", "op": "eq", "right": "packet"},
            {"left": "features.yin", "op": "gt", "right": 0.0},
        ],
        reads=[
            "context.mode",
            "features.yang",
            "features.yin",
            "input_metadata.yang.frame",
            "input_metadata.yang.observed",
            "input_metadata.yang.units",
            "input_metadata.yin.frame",
            "input_metadata.yin.observed",
            "input_metadata.yin.units",
        ],
        writes=["clamped", "common", "difference", "outcome"],
        max_work=4,
        applicability={
            "frame": shared_frame,
            "input_roles": ["yang", "yin"],
            "units": "arb",
        },
    )
    state, registered = _semantic_step(
        state,
        operation="register",
        operation_id="register-two-view-affine",
        kind="Program",
        record_id="representation:two-view-affine",
        payload={
            "program": affine,
            "program_role": "representation",
        },
    )
    assert state["libraries"]["representations"][
        "representation:two-view-affine"
    ] == registered["record"]

    def packet_query(
        operation_id,
        yin,
        yang,
        *,
        yin_coordinate: str | None = "temperature",
        yang_coordinate: str | None = "temperature",
    ):
        inputs = {}
        for role, binding, coordinate in (
            ("yin", yin, yin_coordinate),
            ("yang", yang, yang_coordinate),
        ):
            inputs[role] = {"binding": binding}
            if coordinate is not None:
                inputs[role]["coordinate"] = coordinate
        return {
            "operation": "query",
            "operation_id": operation_id,
            "query": {
                "action": {"shift": 0.0},
                "context": {"mode": "packet"},
                "inputs": inputs,
                "kind": "representation",
                "representation_id": "representation:two-view-affine",
            },
        }

    def domain_snapshot(current):
        return {
            "beliefs": copy.deepcopy(current["beliefs"]),
            "current": copy.deepcopy(current["current"]),
            "indexes": {
                name: copy.deepcopy(rows)
                for name, rows in current["indexes"].items()
                if name != "operations"
            },
            "libraries": copy.deepcopy(current["libraries"]),
            "records": copy.deepcopy(current["records"]),
            "time": copy.deepcopy(current["time"]),
        }

    domain_before = domain_snapshot(state)
    state, represented = _semantic_step(
        state,
        **packet_query(
            "query-two-view-affine",
            bindings["binding:yin"],
            bindings["binding:yang"],
        ),
    )
    expected = {
        "clamped": 2.0 * (2.0**0.5),
        "common": 2.0 * (2.0**0.5),
        "difference": 2.0**0.5,
        "outcome": 2.0 * (2.0**0.5),
    }
    assert represented["status"] == "supported"
    assert represented["answer"] == pytest.approx(expected["outcome"])
    output = represented["representation_output"]
    assert output["values"] == pytest.approx(expected)
    assert set(output["uncertainty"]) == set(output["values"])
    for name in ("common", "difference", "outcome"):
        assert output["uncertainty"][name] == pytest.approx(
            [expected[name] - 0.1, expected[name] + 0.1]
        )
    assert output["uncertainty"]["clamped"] == pytest.approx(
        [expected["clamped"] - 0.1, 2.9]
    )
    assert [row["role"] for row in output["source_refs"]] == ["yang", "yin"]
    for row in output["source_refs"]:
        binding_record = resolve_semantic_record(
            state["records"], row["binding"], require_current=True
        )
        assert row["value"] == binding_record["payload"]["value_ref"]
        assert resolve_semantic_record(
            state["records"], row["value"], require_current=True
        )["payload"]["value"] == binding_record["payload"]["value"]
    assert output["input_metadata"]["yin"]["measurement"][
        "observed_mask"
    ] == ["temperature"]
    assert output["input_metadata"]["yin"]["units"] == "arb"
    assert output["input_metadata"]["yin"]["precision"] == 0.0
    assert output["uncertainty_semantics"] == (
        "clamped-program-error-plus-absolute-affine-input-precision"
    )
    assert domain_snapshot(state) == domain_before
    state, imprecise_view = _semantic_step(
        state,
        **packet_query(
            "query-two-view-imprecise",
            bindings["binding:imprecise"],
            bindings["binding:yang"],
        ),
    )
    propagated_radius = 0.1 + 0.25 / (2.0**0.5)
    assert imprecise_view["status"] == "supported"
    for name in ("common", "difference", "outcome"):
        assert imprecise_view["representation_output"]["uncertainty"][
            name
        ] == pytest.approx(
            [expected[name] - propagated_radius, expected[name] + propagated_radius]
        )
    assert imprecise_view["representation_output"]["uncertainty"][
        "clamped"
    ] == pytest.approx([2.7, 2.9])
    for operation_id, yin, yin_coordinate in (
        (
            "query-two-view-whole-precision",
            bindings["binding:whole-precision"],
            "temperature",
        ),
        ("query-two-view-scalar", bindings["binding:scalar-yin"], None),
    ):
        yang = (
            bindings["binding:scalar-yang"]
            if yin_coordinate is None
            else bindings["binding:yang"]
        )
        state, scalar_precision_view = _semantic_step(
            state,
            **packet_query(
                operation_id,
                yin,
                yang,
                yin_coordinate=yin_coordinate,
                yang_coordinate=yin_coordinate,
            ),
        )
        assert scalar_precision_view["status"] == "supported"
        assert scalar_precision_view["representation_output"]["input_metadata"][
            "yin"
        ]["precision"] == 0.25
        assert scalar_precision_view["representation_output"]["uncertainty"][
            "outcome"
        ] == pytest.approx(
            [
                expected["outcome"] - propagated_radius,
                expected["outcome"] + propagated_radius,
            ]
        )

    state, unrelated_censoring_view = _semantic_step(
        state,
        **packet_query(
            "query-two-view-unrelated-censoring",
            bindings["binding:unrelated-censored"],
            bindings["binding:yang"],
        ),
    )
    assert unrelated_censoring_view["status"] == "supported"
    assert unrelated_censoring_view["limitations"] == []
    assert unrelated_censoring_view["representation_output"]["uncertainty"][
        "outcome"
    ] == pytest.approx(
        [
            expected["outcome"] - propagated_radius,
            expected["outcome"] + propagated_radius,
        ]
    )

    cases = [
        (
            "query-two-view-masked",
            bindings["binding:yin"],
            bindings["binding:masked"],
            "temperature",
            "hidden",
            ["representation-coordinate-unobserved:yang:hidden"],
        ),
        (
            "query-two-view-units",
            bindings["binding:yin"],
            bindings["binding:other-units"],
            "temperature",
            "temperature",
            ["representation-units-incompatible"],
        ),
        (
            "query-two-view-frame",
            bindings["binding:yin"],
            bindings["binding:other-frame"],
            "temperature",
            "temperature",
            ["representation-frames-incompatible"],
        ),
        (
            "query-two-view-missing-units",
            bindings["binding:yin"],
            bindings["binding:no-units"],
            "temperature",
            "temperature",
            ["representation-units-missing:yang"],
        ),
        (
            "query-two-view-missing-frame",
            bindings["binding:yin"],
            bindings["binding:no-frame"],
            "temperature",
            "temperature",
            ["representation-frame-missing:yang"],
        ),
        (
            "query-two-view-inactive",
            bindings["binding:yin"],
            bindings["binding:inactive"],
            "temperature",
            "temperature",
            ["representation-binding-invalidated:yang"],
        ),
        (
            "query-two-view-guard",
            bindings["binding:negative"],
            bindings["binding:yang"],
            "temperature",
            "temperature",
            ["guard-false"],
        ),
        (
            "query-two-view-precision",
            bindings["binding:no-precision"],
            bindings["binding:yang"],
            "temperature",
            "temperature",
            ["representation-precision-missing:yin"],
        ),
        (
            "query-two-view-censored",
            bindings["binding:censored"],
            bindings["binding:yang"],
            "temperature",
            "temperature",
            ["representation-binding-censored:yin"],
        ),
        (
            "query-two-view-whole-censored",
            bindings["binding:whole-censored"],
            bindings["binding:yang"],
            "temperature",
            "temperature",
            ["representation-binding-censored:yin"],
        ),
    ]
    for (
        operation_id,
        yin,
        yang,
        yin_coordinate,
        yang_coordinate,
        limitations,
    ) in cases:
        state, refused = _semantic_step(
            state,
            **packet_query(
                operation_id,
                yin,
                yang,
                yin_coordinate=yin_coordinate,
                yang_coordinate=yang_coordinate,
            ),
        )
        assert refused["status"] == "support-gap"
        assert refused["answer"] is None
        assert refused["representation_output"] is None
        assert refused["limitations"] == limitations
    too_many_inputs = {
        f"role-{index}": {"binding": bindings["binding:yin"]}
        for index in range(state["bounds"]["max_observations"] + 1)
    }
    with pytest.raises(
        FieldIntelligenceError,
        match="representation Binding inputs must be a bounded nonempty mapping",
    ) as over_limit:
        _semantic_step(
            state,
            operation="query",
            operation_id="query-two-view-over-limit",
            query={
                "inputs": too_many_inputs,
                "kind": "representation",
                "representation_id": "representation:two-view-affine",
            },
        )
    assert over_limit.value.code == "INVALID_QUERY"

    state, corrected = _semantic_step(
        state,
        operation="correct",
        operation_id="correct-two-view-yin",
        correction_id="two-view-yin",
        target=bindings["binding:yin"],
        replacement={"value": {"temperature": 5.0}},
    )
    state, stale = _semantic_step(
        state,
        **packet_query(
            "query-two-view-stale",
            bindings["binding:yin"],
            bindings["binding:yang"],
        ),
    )
    assert stale["status"] == "support-gap"
    assert stale["limitations"] == ["representation-binding-unavailable:yin"]
    state, corrected_view = _semantic_step(
        state,
        **packet_query(
            "query-two-view-corrected",
            corrected["current"],
            bindings["binding:yang"],
        ),
    )
    assert corrected_view["status"] == "supported"
    assert corrected_view["representation_output"]["values"] == pytest.approx(
        {
            "clamped": 2.9,
            "common": 3.0 * (2.0**0.5),
            "difference": 2.0 * (2.0**0.5),
            "outcome": 3.0 * (2.0**0.5),
        }
    )
    assert corrected_view["representation_output"]["uncertainty"][
        "clamped"
    ] == pytest.approx([2.8, 2.9])
    assert corrected_view["representation_output"]["input_metadata"]["yin"][
        "binding_epistemic_kind"
    ] == "corrected"
    assert corrected_view["representation_output"]["input_metadata"]["yin"][
        "value_epistemic_kind"
    ] == "corrected"


def test_semantic_migration_consolidation_recovery_and_revocation() -> None:
    from cassi_field_cognition import semantic_cognition_state
    from cassi_field_regions import resolve_semantic_record

    state = semantic_cognition_state()
    state, registered = _semantic_step(
        state,
        operation="register",
        operation_id="register-coarse-schema",
        kind="Value",
        record_id="representation-state",
        payload={"schema": "representation.v1", "state": "coarse"},
        support_roots=["observation:coarse"],
    )
    migration = {
        "operation": "migrate",
        "migration_id": "representation-v2-migration",
        "target": registered["record"],
        "replacement_payload": {
            "schema": "representation.v2",
            "states": ["fine-a", "fine-b"],
        },
        "old_schema": "representation.v1",
        "new_schema": "representation.v2",
        "mapping": [
            {
                "old": "coarse",
                "new": ["fine-a", "fine-b"],
                "semantics": "set-valued",
            }
        ],
        "affected_bindings": [],
        "preservation": {
            "exact_queries": ["is-fine-family"],
            "approximate_queries": [],
            "lost_distinctions": [],
        },
        "resource_bounds": {
            "max_work": 64,
            "max_output_bytes": 4096,
        },
        "recovery": {
            "available": True,
            "requires_authorization": False,
            "route": "regional immutable history",
        },
    }
    state, waiting = _semantic_step(
        state,
        **migration,
        operation_id="migration-await-source",
        source_access={
            "required": ["regional-history:representation-state"],
            "available": [],
        },
    )
    assert waiting["status"] == "support-gap"
    assert waiting["obligation"]["kind"] == "Obligation"
    assert waiting["progress"]["completed"] == 0
    state, migrated = _semantic_step(
        state,
        **migration,
        operation_id="migration-with-source",
        source_access={
            "required": ["regional-history:representation-state"],
            "available": ["regional-history:representation-state"],
        },
    )
    assert migrated["status"] == "supported"
    assert migrated["progress"]["completed"] == migrated["progress"]["required"]
    resolved_obligation = resolve_semantic_record(
        state["records"], migrated["resolved_obligation"]
    )
    assert resolved_obligation["payload"]["state"] == "resolved"

    state, consolidated = _semantic_step(
        state,
        operation="consolidate",
        operation_id="consolidate-fine-state",
        record_id="representation-summary",
        references=[migrated["migrated"]],
        summary={"family": "fine", "member_count": 2},
        retention={
            "recoverable_details": ["states"],
            "sufficient_summaries": ["member_count"],
            "lost_details": [],
            "rare_exceptions": ["fine-b"],
            "rare_exceptions_preserved": True,
        },
        questions={
            "preserved": ["is-fine-family"],
            "unavailable": [],
        },
        reconstruction={
            "strategy": "inseparable-invalidates",
            "authorized_inputs": [],
            "contribution_partitions": [],
            "initialization_lineage": [],
        },
        measured_cost={"field_steps": 1},
    )
    assert consolidated["status"] == "supported"
    assert consolidated["semantic_loss"] is False
    assert consolidated["support_root_count"] == 1

    state, revision = _semantic_step(
        state,
        operation="register",
        operation_id="correct-migrated-state",
        kind="Value",
        record_id="representation-state",
        payload={
            "schema": "representation.v2",
            "states": ["fine-corrected"],
        },
        support_roots=["observation:correction"],
    )
    summary = resolve_semantic_record(
        state["records"], state["current"]["Value"]["representation-summary"]
    )
    assert summary["status"] == "invalidated"
    assert any(
        reference["id"] == consolidated["summary"]["id"]
        for reference in revision["invalidation_frontier"]
    )

    bounded_state = semantic_cognition_state()
    bounded_state, bounded_record = _semantic_step(
        bounded_state,
        operation="register",
        operation_id="register-bounded-source",
        kind="Value",
        record_id="bounded-source",
        payload={"schema": "representation.v1", "state": "coarse"},
    )
    bounded_request = {
        **migration,
        "operation_id": "migration-resource-exhaustion",
        "migration_id": "bounded-migration",
        "target": bounded_record["record"],
        "resource_bounds": {"max_work": 1, "max_output_bytes": 4096},
        "source_access": {"required": [], "available": []},
    }
    bounded_state, exhausted = _semantic_step(
        bounded_state, **bounded_request
    )
    assert exhausted["status"] == "resource-exhausted"
    assert exhausted["migration"] is None
    assert bounded_state["current"]["Value"]["bounded-source"] == (
        bounded_record["record"]
    )


def test_autonomous_learning_selects_and_executes_field_owned_opportunity() -> None:
    from cassi_field_cognition import semantic_cognition_state

    state = semantic_cognition_state()
    common_request = {
        "examples": [
            {
                "text": "the key is in the drawer",
                "bindings": {"item": "key", "place": "drawer"},
            },
            {
                "text": "the cup is in the box",
                "bindings": {"item": "cup", "place": "box"},
            },
        ],
        "meaning": {
            "object": {"$role": "place"},
            "relation": "located-in",
            "subject": {"$role": "item"},
        },
        "speech_act": "assertion",
    }
    state, selected = _semantic_step(
        state,
        operation="autonomous-learn",
        operation_id="autonomous-location-learning",
        goal="acquire a reusable location relation",
        opportunities=[
            {
                "candidate_id": "location-construction",
                "learning_kind": "construction",
                "expected_gain": 8.0,
                "urgency": 1.0,
                "novelty": 1.0,
                "cost": 0.25,
                "request": {
                    **common_request,
                    "construction_id": "location-assertion",
                },
            },
            {
                "candidate_id": "lower-value-location-construction",
                "learning_kind": "construction",
                "expected_gain": 1.0,
                "request": {
                    **common_request,
                    "construction_id": "unused-location-assertion",
                },
            },
        ],
    )
    assert selected["status"] == "supported"
    assert selected["selected"]["candidate_id"] == "location-construction"
    assert selected["selected"]["learning_kind"] == "construction"
    assert selected["selected"]["score"] > 9.25
    assert selected["selected"]["experience_adjustment"] > 0.0
    assert selected["learning"]["learning_kind"] == "construction"
    selection_record = state["records"][selected["event"]["id"]][-1]
    assert (
        selection_record["payload"]["autonomous_learning"][
            "selected_candidate_id"
        ]
        == "location-construction"
    )

    state, interpreted = _semantic_step(
        state,
        operation="interpret",
        operation_id="interpret-autonomously-learned-location",
        text="the coin is in the chest",
        speaker="alice",
        discourse_id="autonomous-location-discourse",
    )
    assert interpreted["status"] == "supported"
    assert interpreted["interpretation"]["content"] == {
        "object": "chest",
        "relation": "located-in",
        "subject": "coin",
    }

def test_regional_program_resolution_floor_blocks_subprecision_promotion() -> None:

    import hashlib
    import math

    from cassi_field_cognition import (
        regional_kernel,
        regional_program_promotion_state,
        regional_program_state,
    )

    program = {
        "program_id": "regional-resolution-control",
        "version": 1,
        "roles": ["x"],
        "steps": [
            {"operation": "identity", "output": "y", "inputs": ["x"]},
        ],
        "outputs": ["y"],
        "status": "candidate",
        "assessments": [],
        "support_event_ids": [],
        "dependencies": [],
        "guards": [],
        "prefix_code_bits": 1,
    }
    event_id = hashlib.sha256(b"regional-resolution-control").hexdigest()
    state = regional_program_state(
        program,
        {"x": 1000.0},
        outcome={"y": math.nextafter(1000.0, math.inf)},
        event_id=event_id,
        loss_scale=1.0,
    )
    response = regional_kernel(state, {}, 64)
    assert response.status == "done"
    assessment = response.output
    assert assessment["resolution_status"] == "unresolved"
    assert assessment["resolution_floor"] > 0.0
    assert assessment["normalized_loss"] > 0.0
    candidate = dict(program)
    candidate["assessments"] = [
        {
            key: assessment[key]
            for key in (
                "assessment_id",
                "event_id",
                "prediction_id",
                "prediction",
                "outcome",
                "normalized_loss",
                "resolution_floor",
                "resolution_status",
                "sequence",
                "support_event_ids",
                "dependency_ids",
            )
        }
    ]
    promotion = regional_program_promotion_state(
        (candidate,),
        ("regional-resolution-control",),
        minimum_assessments=1,
        maximum_average_loss=1.0,
    )
    promotion_response = regional_kernel(promotion, {}, 64)
    assert promotion_response.status == "done"
    assert promotion_response.output["status"] == "refused"
    evaluated = promotion_response.output["evaluated"][0]
    assert evaluated["unresolved_assessment_count"] == 1
    assert evaluated["resolution_statuses"] == ["unresolved"]
    assert evaluated["resolution_floors"] == [assessment["resolution_floor"]]


def test_field_ngram_readout_distinguishes_table_rows_after_restart(tmp_path):
    import numpy as np

    from programs.model.ngram_learning import readout

    root = tmp_path / "field"
    table = np.linspace(-1.0, 1.0, 2560, dtype=np.float32)
    hidden = np.linspace(-0.5, 0.5, 2048, dtype=np.float32)
    feedback = {
        "schema": "cassifi.qwen-ngram-next-token-feedback.v1",
        "id": "observed-next-token",
        "model_id": "a" * 64,
        "table_id": "b" * 64,
        "context_sha256": "c" * 64,
        "next_token_id": 17,
        "probability_token_id": 17,
        "competitor_token_id": 18,
        "target_direction": [1.0] + [0.0] * 2047,
        "advantage": -2.0,
    }
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "ngram-configure", "configure", profile={
            "mode_count": 65_536, "max_steps": 256, "max_events": 256,
        })
        call(owner, "ngram-enable", "enable-ngram", model_id="a" * 64, table_id="b" * 64)
        call(
            owner, "ngram-learn", "learn-ngram",
            table_vector=table.tolist(), hidden=hidden.tolist(), feedback=feedback,
        )
        state = owner.state.computers[0].ngram_readout_state()
        real = readout(state, table, hidden)
        swapped = readout(state, table[::-1].copy(), hidden)
        assert state["revision"] == 1
        assert np.linalg.norm(real - swapped) > 1e-4
        digest = owner.state.state_sha256

    with FieldIntelligenceOwner(root) as reopened:
        assert reopened.state.state_sha256 == digest
        restored = reopened.state.computers[0].ngram_readout_state()
        assert restored["revision"] == 1
        np.testing.assert_array_equal(readout(restored, table, hidden), real)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"status": "supported", "result_status": "observed"}, 1.0),
        ({"status": "supported", "result_status": "supported"}, 1.0),
        ({"status": "failed", "result_status": "support-gap"}, -1.0),
        ({"status": "failed", "result_status": "rejected"}, -1.0),
        ({"status": "failed", "result_status": "blocked"}, 0.0),
        ({"status": "supported", "result_status": "support-gap"}, 0.0),
        ({"status": "unassessed", "result_status": "rejected"}, 0.0),
        ({"status": "supported", "result_status": []}, 0.0),
        ({"status": "failed", "result_status": {"status": "failed"}}, 0.0),
    ],
    ids=[
        "observed-success",
        "supported-success",
        "support-gap-obstruction",
        "rejected-obstruction",
        "generic-failure-is-neutral",
        "inconsistent-result-is-neutral",
        "unassessed-is-neutral",
        "malformed-list-is-neutral",
        "malformed-object-is-neutral",
    ],
)
def test_research_progress_requires_an_explicit_assessed_outcome(payload, expected):
    assert _assessed_research_progress(payload) == expected


def test_embodied_snapshot_publishes_generation_bound_read_only_roles(tmp_path):
    with FieldIntelligenceOwner(
        tmp_path / "field", initial_state=AtlasState(resonant_workspace=None)
    ) as owner:
        prior_digest = owner.state.state_sha256
        prior_generation = owner.state.generation
        snapshot = owner.inspect_embodied_field()

        assert snapshot["schema"] == "cassifi.embodied-field.v1"
        assert snapshot["read_only"] is True
        assert snapshot["state_sha256"] == prior_digest
        assert snapshot["generation"] == prior_generation
        assert snapshot["orientation"]["schema"] == "cassifi.embodied-orientation.v1"
        assert snapshot["orientation"]["state_generation"] == prior_generation
        roles = snapshot["roles"]
        assert roles["schema"] == "cassifi.embodied-role-bindings.v1"
        assert roles["state_generation"] == prior_generation
        assert roles["state_sha256"] == prior_digest
        for name in ("core", "mantle", "fringe"):
            binding = roles[name]
            assert binding["schema"] == "cassifi.embodied-role-binding.v1"
            assert binding["role"] == name
            assert binding["state_generation"] == prior_generation
            assert binding["state_sha256"] == prior_digest
            assert binding["status"] == "unavailable"
            assert binding["region_ids"] == []

        assert owner.state.state_sha256 == prior_digest
        assert owner.state.generation == prior_generation

def test_embodied_snapshot_binds_current_resonant_core_layout(tmp_path):
    with FieldIntelligenceOwner(tmp_path / "field") as owner:
        workspace = owner.state.resonant_workspace
        assert workspace is not None
        profile = workspace.profile
        prior_digest = owner.state.state_sha256
        snapshot = owner.inspect_embodied_field()
        core = snapshot["roles"]["core"]

        assert core["state_generation"] == snapshot["generation"]
        assert core["state_sha256"] == prior_digest
        assert core["region_ids"] == ["owner:owner-resonance"]
        layout = core["layout"][0]
        assert layout["region_id"] == "owner:owner-resonance"
        assert layout["source_region_id"] == "owner-resonance"
        assert layout["layout_identity"] == profile.layout_identity
        operator = core["operator"][0]
        assert operator["basis"] == "owner-resonant-workspace-profile"
        assert operator["layout_identity"] == profile.layout_identity
        assert operator["pools"] == profile.pools
        assert operator["ports_per_pool"] == profile.ports_per_pool
        assert owner.state.state_sha256 == prior_digest



def test_affect_concern_binding_uses_only_unique_current_assessment_experience(
    tmp_path,
):
    from cassi_field_cognition import semantic_cognition_state

    assessment_id = "research:outcome:concern-binding"
    assessment_payload = {
        "memory_role": "recall-assessment",
        "episode_ref": {
            "id": "memory:episode:concern-binding",
            "kind": "Event",
            "content_version": 1,
        },
        "use_ref": {
            "id": "memory:use:concern-binding",
            "kind": "Event",
            "content_version": 1,
        },
        "outcome_ref": {
            "id": "memory:outcome:concern-binding",
            "kind": "Event",
            "content_version": 1,
        },
        "usefulness": 0.5,
    }
    semantic_state = semantic_cognition_state()
    semantic_state, registered = _semantic_step(
        semantic_state,
        operation="register",
        operation_id="register:concern-binding",
        kind="Assessment",
        record_id=assessment_id,
        payload=assessment_payload,
        status="active",
        epistemic_kind="assessed",
    )
    assessment_ref = registered["record"]
    semantic_state, _ = _semantic_step(
        semantic_state,
        operation="appraise-experience",
        operation_id="appraise:concern-binding:project-a",
        evidence=assessment_ref,
        project_id="project-a",
    )

    with FieldIntelligenceOwner(tmp_path / "field") as owner:
        concern_ref = owner._embodied_affect_concern_for_experience(
            semantic_state, assessment_ref
        )
        assert concern_ref is not None
        assert concern_ref["project_id"] == "project-a"
        assert concern_ref["question_ref"] is None
        assert concern_ref["object_refs"] == []
        assert concern_ref["goal_ref"] is None
        stale_ref = {**assessment_ref, "content_version": assessment_ref["content_version"] + 1}
        assert owner._embodied_affect_concern_for_experience(
            semantic_state, stale_ref
        ) is None

        semantic_state, _ = _semantic_step(
            semantic_state,
            operation="appraise-experience",
            operation_id="appraise:concern-binding:project-b",
            evidence=assessment_ref,
            project_id="project-b",
        )
        assert owner._embodied_affect_concern_for_experience(
            semantic_state, assessment_ref
        ) is None


def test_embodied_orientation_limits_current_pending_obligations_not_retired_history(
    tmp_path,
):
    from pathlib import Path
    from cassi_research_residency import open_research_residency

    work = [
        {
            "id": item_id,
            "summary": f"Study {item_id}",
            "request": {"kind": "self-study", "source_paths": ["CassiFI/cassi_field_owner.py"]},
        }
        for item_id in ("alpha", "beta")
    ]
    with open_research_residency(tmp_path / "residency") as residency:
        residency.initialize(
            workspace=Path(__file__).resolve().parents[1],
            work=work,
            profile={"mode_count": 65_536, "default_value_words": 512},
        )
        residency.advance()  # seed both real pending obligations
        owner = residency.owner
        before = owner._embodied_orientation(owner.state, limit=1)
        assert before["truncated"] is True
        assert before["current_concerns"][0]["question_id"] == "alpha"

        first = residency._required_record("research:work:00000000:alpha")
        residency._register(
            "orientation:resolve-alpha",
            first["id"],
            "Obligation",
            first["payload"],
            status="resolved",
            epistemic_kind="asserted",
        )
        after = owner._embodied_orientation(owner.state, limit=1)
        assert after["status"] == "partial"
        assert after["truncated"] is False
        assert [row["question_id"] for row in after["current_concerns"]] == ["beta"]
        assert [row["question_id"] for row in after["continuations"]] == ["beta"]
        assert after["unknowns"] == []


def _numerical_scalar_state(value: int) -> dict:
    compiled = compile_structured_program({
        "schema": STRUCTURED_SCHEMA,
        "main": [
            {"op": "set_acc", "value": value},
            {"op": "push_acc", "stack": "left"},
        ],
    })
    profile = ComputerProfile(
        program_capacity=len(compiled.program) + 2,
        stack_capacity=8,
        max_steps=64,
    )
    return regional_scalar_state(compiled, profile)


def _collect_numerical_result(owner, work_id: str, operation_id: str):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        result = owner.collect_numerical_work(work_id, operation_id=operation_id)
        if result["status"] != "pending":
            return result
        time.sleep(0.02)
    pytest.fail(f"numerical work {work_id} did not settle")


def _pause_numerical_submit(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original_submit = LearningComputer.submit

    def paused_submit(self, *args, **kwargs):
        entered.set()
        assert release.wait(30)
        return original_submit(self, *args, **kwargs)

    monkeypatch.setattr(LearningComputer, "submit", paused_submit)
    return entered, release


def test_numerical_work_executes_on_distinct_computers_in_parallel(tmp_path, monkeypatch):
    barrier = threading.Barrier(3)
    original_submit = LearningComputer.submit

    def synchronized_submit(self, *args, **kwargs):
        barrier.wait(timeout=15)
        return original_submit(self, *args, **kwargs)

    with FieldIntelligenceOwner(tmp_path / "field") as owner:
        for computer_id in ("first", "second"):
            owner.operate_computer(
                f"configure-{computer_id}",
                computer_id=computer_id,
                action="configure",
            )
        monkeypatch.setattr(LearningComputer, "submit", synchronized_submit)
        first = owner.submit_numerical_work(
            "parallel-first", computer_id="first",
            kernel="scalar-computer", state=_numerical_scalar_state(7), steps=64,
        )
        second = owner.submit_numerical_work(
            "parallel-second", computer_id="second",
            kernel="scalar-computer", state=_numerical_scalar_state(11), steps=64,
        )
        assert first["status"] == second["status"] == "pending"
        barrier.wait(timeout=15)  # Both real submissions have entered before either can finish.
        results = (
            _collect_numerical_result(owner, "parallel-first", "admit-first"),
            _collect_numerical_result(owner, "parallel-second", "admit-second"),
        )
        assert [result["status"] for result in results] == ["admitted", "admitted"]
        for computer_id, value, result in zip(
            ("first", "second"), (7, 11), results
        ):
            row = next(
                row for row in owner.state.computers
                if row.computer_id == computer_id
            )
            assert row.inspect()["outcome"]["left"] == [value]
            assert result["artifact"]["computer_state_sha256"] == row.state_sha256
            assert result["artifact"]["receipt"]["run"]["status"] == "halted"
            assert result["checkpoint_receipt"]["operation_id"] == f"admit-{computer_id}"


def test_numerical_work_rejects_changed_relevant_computer(tmp_path, monkeypatch):
    entered, release = _pause_numerical_submit(monkeypatch)
    root = tmp_path / "field"

    with FieldIntelligenceOwner(root) as owner:
        owner.operate_computer("configure", computer_id="main", action="configure")
        assert owner.state.computers[0].inspect()["outcome"] is None
        try:
            pending = owner.submit_numerical_work(
                "stale-computer", computer_id="main",
                kernel="scalar-computer", state=_numerical_scalar_state(7), steps=64,
            )
            assert pending["status"] == "pending"
            assert entered.wait(15)
            owner.operate_computer(
                "change-computer", computer_id="main", action="load",
                arguments={"program": [[0, 0, 0, 0, 0]]},
            )
            changed = owner.state.computers[0].state_sha256
        finally:
            release.set()
        result = _collect_numerical_result(owner, "stale-computer", "admit-stale")
        assert result["status"] == "obsolete"
        assert owner.state.computers[0].state_sha256 == changed
        assert owner.state.computers[0].inspect()["task"]["status"] != "halted"
    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.computers[0].state_sha256 == changed
        assert owner.state.computers[0].inspect()["outcome"] is None


def test_numerical_work_rejects_superseded_source_revision(tmp_path, monkeypatch):
    entered, release = _pause_numerical_submit(monkeypatch)
    source = SourceInput(
        source_id="numerical-observation",
        content=canonical_json_bytes({"reading": 7}),
        media_type="application/json",
        codec="utf-8",
        observed_timestamp="numerical-time",
        scope="test",
        claim_category="controlled-observation",
        fidelity="exact-record",
    )
    with FieldIntelligenceOwner(tmp_path / "field") as owner:
        owner.operate_computer("configure", computer_id="main", action="configure")
        owner.evidence.store_source(source)
        computer_sha256 = owner.state.computers[0].state_sha256
        try:
            pending = owner.submit_numerical_work(
                "stale-source", computer_id="main",
                kernel="scalar-computer", state=_numerical_scalar_state(13),
                source_revision_ids=(source.revision_id,), steps=64,
            )
            assert pending["status"] == "pending"
            assert pending["dependencies"]["source_revision_ids"] == [source.revision_id]
            assert entered.wait(15)
            owner.evidence.store_source(
                replace(
                    source,
                    parent_revision_id=source.revision_id,
                    content=canonical_json_bytes({"reading": 8}),
                )
            )
        finally:
            release.set()
        result = _collect_numerical_result(owner, "stale-source", "admit-stale-source")
        assert result["status"] == "obsolete"
        assert owner.state.computers[0].state_sha256 == computer_sha256
        assert owner.evidence.source(source.revision_id).status == "superseded"


def test_numerical_work_admits_after_unrelated_owner_change(tmp_path, monkeypatch):
    entered, release = _pause_numerical_submit(monkeypatch)

    with FieldIntelligenceOwner(tmp_path / "field") as owner:
        owner.operate_computer("configure-main", computer_id="main", action="configure")
        original_computer = owner.state.computers[0].state_sha256
        try:
            pending = owner.submit_numerical_work(
                "unrelated-change", computer_id="main",
                kernel="scalar-computer", state=_numerical_scalar_state(19), steps=64,
            )
            assert pending["status"] == "pending"
            assert entered.wait(15)
            owner.operate_computer(
                "configure-other", computer_id="other", action="configure",
            )
            assert next(
                row for row in owner.state.computers if row.computer_id == "main"
            ).state_sha256 == original_computer
        finally:
            release.set()
        result = _collect_numerical_result(owner, "unrelated-change", "admit-unrelated")
        assert result["status"] == "admitted"
        assert next(
            row for row in owner.state.computers if row.computer_id == "main"
        ).inspect()["outcome"]["left"] == [19]
        assert {row.computer_id for row in owner.state.computers} == {"main", "other"}


def test_cancelled_numerical_work_cannot_publish_after_worker_finishes(tmp_path, monkeypatch):
    entered, release = _pause_numerical_submit(monkeypatch)

    with FieldIntelligenceOwner(tmp_path / "field") as owner:
        owner.operate_computer("configure", computer_id="main", action="configure")
        before = owner.state.computers[0].state_sha256
        try:
            assert owner.submit_numerical_work(
                "cancelled-work", computer_id="main",
                kernel="scalar-computer", state=_numerical_scalar_state(23), steps=64,
            )["status"] == "pending"
            assert entered.wait(15)
            assert owner.cancel_numerical_work("cancelled-work")["status"] == "cancelled"
        finally:
            release.set()
        assert _collect_numerical_result(
            owner, "cancelled-work", "collect-cancelled"
        )["status"] == "cancelled"
        assert owner.state.computers[0].state_sha256 == before
    with FieldIntelligenceOwner(tmp_path / "field") as owner:
        assert owner.collect_numerical_work(
            "cancelled-work", operation_id="collect-cancelled-restarted"
        )["status"] == "cancelled"
        assert owner.state.computers[0].state_sha256 == before


def test_pending_numerical_work_recovers_after_owner_restart(tmp_path, monkeypatch):
    root = tmp_path / "field"
    finished = threading.Event()
    original_submit = LearningComputer.submit

    def completed_submit(self, *args, **kwargs):
        result = original_submit(self, *args, **kwargs)
        finished.set()
        return result

    with FieldIntelligenceOwner(root) as owner:
        owner.operate_computer("configure", computer_id="main", action="configure")
        monkeypatch.setattr(LearningComputer, "submit", completed_submit)
        assert owner.submit_numerical_work(
            "recover-pending", computer_id="main",
            kernel="scalar-computer", state=_numerical_scalar_state(29), steps=64,
        )["status"] == "pending"
        assert finished.wait(30)
        assert owner.state.computers[0].inspect()["outcome"] is None
    with FieldIntelligenceOwner(root) as owner:
        result = _collect_numerical_result(owner, "recover-pending", "admit-recovered")
        assert result["status"] == "admitted"
        assert owner.state.computers[0].inspect()["outcome"]["left"] == [29]
        assert result["artifact"]["computer_state_sha256"] == owner.state.computers[0].state_sha256
        assert result["checkpoint_receipt"]["operation_id"] == "admit-recovered"


def test_numerical_queue_ignores_crashed_atomic_write_temporary(tmp_path):
    with FieldIntelligenceOwner(tmp_path / "field") as owner:
        owner.operate_computer("configure", computer_id="main", action="configure")
        owner.limits = replace(owner.limits, max_pending_operations=1)
        record_path = owner._numerical_record_path("interrupted")
        record_path.with_name(f".{record_path.name}.123.456.tmp").write_bytes(b"incomplete")
        pending = owner.submit_numerical_work(
            "after-interruption", computer_id="main",
            kernel="scalar-computer", state=_numerical_scalar_state(31), steps=64,
        )
        assert pending["status"] == "pending"
        assert _collect_numerical_result(
            owner, "after-interruption", "admit-after-interruption"
        )["status"] == "admitted"


def test_numerical_submission_rejects_permanently_impossible_reservation(tmp_path):
    with FieldIntelligenceOwner(tmp_path / "field") as owner:
        owner.operate_computer("configure", computer_id="main", action="configure")
        owner.limits = replace(
            owner.limits, max_workspace_bytes=2 * owner.state.computers[0].nbytes - 1
        )
        with pytest.raises(FieldIntelligenceError) as rejected:
            owner.submit_numerical_work(
                "impossible", computer_id="main",
                kernel="scalar-computer", state=_numerical_scalar_state(37), steps=64,
            )
        assert rejected.value.code == "WORK_CAPACITY"
        assert not owner._numerical_record_path("impossible").exists()


def test_numerical_submission_queues_while_other_reservation_is_inflight(
    tmp_path, monkeypatch,
):
    entered, release = _pause_numerical_submit(monkeypatch)
    with FieldIntelligenceOwner(tmp_path / "field") as owner:
        for computer_id in ("first", "second"):
            owner.operate_computer(
                f"configure-{computer_id}", computer_id=computer_id, action="configure",
            )
        row_bytes = owner.state.computers[0].nbytes
        owner.limits = replace(owner.limits, max_workspace_bytes=2 * row_bytes)
        try:
            owner.submit_numerical_work(
                "reserved", computer_id="first",
                kernel="scalar-computer", state=_numerical_scalar_state(39), steps=64,
            )
            assert entered.wait(15)
            queued = owner.submit_numerical_work(
                "queued", computer_id="second",
                kernel="scalar-computer", state=_numerical_scalar_state(40), steps=64,
            )
            assert queued["status"] == "pending"
            assert owner._numerical_record_path("queued").is_file()
            assert "queued" not in owner._numerical_futures
        finally:
            release.set()
        assert _collect_numerical_result(owner, "reserved", "admit-reserved")["status"] == "admitted"
        assert _collect_numerical_result(owner, "queued", "admit-queued")["status"] == "admitted"
        second = next(row for row in owner.state.computers if row.computer_id == "second")
        assert second.inspect()["outcome"]["left"] == [40]

@pytest.mark.parametrize("recovery", ("cancel", "retry_after_restart"))
def test_numerical_committed_effect_survives_descriptor_write_failure(
    tmp_path, monkeypatch, recovery,
):
    root = tmp_path / "field"
    with FieldIntelligenceOwner(root) as owner:
        owner.operate_computer("configure", computer_id="main", action="configure")
        owner.submit_numerical_work(
            "committed-before-record", computer_id="main",
            kernel="scalar-computer", state=_numerical_scalar_state(41), steps=64,
        )
        original_save = owner._save_numerical_record

        def fail_final_save(record):
            if record["status"] == "admitted":
                raise OSError("interrupted descriptor update")
            return original_save(record)

        with monkeypatch.context() as patch:
            patch.setattr(owner, "_save_numerical_record", fail_final_save)
            with pytest.raises(OSError, match="interrupted descriptor update"):
                _collect_numerical_result(owner, "committed-before-record", "admit-before-record")
        assert owner._numerical_record("committed-before-record")["status"] == "pending"
        assert owner.state.computers[0].inspect()["outcome"]["left"] == [41]
        if recovery == "cancel":
            result = owner.cancel_numerical_work("committed-before-record")
            assert result["status"] == "admitted"
            assert result["checkpoint_receipt"]["operation_id"] == "admit-before-record"
            assert owner.collect_numerical_work(
                "committed-before-record", operation_id="admit-before-record"
            )["artifact"] == result["artifact"]
    if recovery == "retry_after_restart":
        with FieldIntelligenceOwner(root) as owner:
            result = owner.collect_numerical_work(
                "committed-before-record", operation_id="admit-before-record"
            )
            assert result["status"] == "admitted"
            assert result["checkpoint_receipt"]["operation_id"] == "admit-before-record"
            assert owner.cancel_numerical_work("committed-before-record")["status"] == "admitted"
            assert owner.state.computers[0].inspect()["outcome"]["left"] == [41]


@pytest.mark.parametrize("rejection", ("state_capacity", "replay_floor"))
def test_numerical_prepublication_rejection_allows_new_operation_id(
    tmp_path, rejection,
):
    with FieldIntelligenceOwner(tmp_path / "field") as owner:
        owner.operate_computer("configure", computer_id="main", action="configure")
        owner.submit_numerical_work(
            "retry-publication", computer_id="main",
            kernel="scalar-computer", state=_numerical_scalar_state(43), steps=64,
        )
        # Wait for computation to finish without publishing it.
        owner._numerical_futures["retry-publication"].result(timeout=30)
        if rejection == "state_capacity":
            original_limits = owner.limits
            workspace = owner.state.workspace_usage()["workspace_bytes"]
            owner.limits = replace(
                owner.limits, max_workspace_bytes=workspace, max_state_bytes=workspace,
            )
            bad_id, code = "capacity-rejected", "FIELD_CAPACITY"
        else:
            bad_id, code = "historical:1", "REPLAY_FLOOR"
            floor_path = owner.checkpoints.history_floor_path
            floor = owner.checkpoints._history_floor()
            floor_path.write_bytes(canonical_json_bytes({
                **floor, "discarded_operation_ids": [bad_id],
            }))
        with pytest.raises(FieldIntelligenceError) as rejected:
            owner.collect_numerical_work("retry-publication", operation_id=bad_id)
        assert rejected.value.code == code
        assert owner._numerical_record("retry-publication")["status"] == "pending"
        assert "operation_id" not in owner._numerical_record("retry-publication")
        if rejection == "state_capacity":
            owner.limits = original_limits
        result = owner.collect_numerical_work(
            "retry-publication", operation_id="admit-after-rejection"
        )
        assert result["status"] == "admitted"
        assert result["checkpoint_receipt"]["operation_id"] == "admit-after-rejection"
        assert owner.state.computers[0].inspect()["outcome"]["left"] == [43]
