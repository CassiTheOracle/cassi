from __future__ import annotations

from pathlib import Path

import pytest

from cassi_field_atlas import AtlasState, canonical_json_bytes, sha256_value
from cassi_field_owner import AuthorityGrant, FieldIntelligenceError, FieldIntelligenceOwner, SourceInput
from cassi_temporal_field import (
    REGIONAL_RESULT_SCHEMA,
    TemporalField,
    regional_kernel,
    regional_state,
)


ACTIONS = ("start", "finish", "inspect")
OBSERVATIONS = ("pending", "done", "quiet", "fault")


def source(name: str, steps: list[dict[str, str]]) -> SourceInput:
    return SourceInput(source_id=name, content=canonical_json_bytes({
        "schema": "cassifi.temporal-episode.v1", "steps": steps,
    }), media_type="application/json", codec="utf-8", observed_timestamp=name,
        scope="task-test", claim_category="simulated-observation", fidelity="exact-record", labels=("test",))

def revised(source_input: SourceInput, steps: list[dict[str, str]]) -> SourceInput:
    return SourceInput(
        source_id=source_input.source_id,
        content=canonical_json_bytes({
            "schema": "cassifi.temporal-episode.v1", "steps": steps,
        }),
        media_type=source_input.media_type,
        codec=source_input.codec,
        observed_timestamp=source_input.observed_timestamp,
        scope=source_input.scope,
        claim_category=source_input.claim_category,
        fidelity=source_input.fidelity,
        parent_revision_id=source_input.revision_id,
        span=source_input.span,
        labels=source_input.labels,
    )


def setup_owner(home: Path) -> FieldIntelligenceOwner:
    owner = FieldIntelligenceOwner(home, initial_state=AtlasState(resonant_workspace=None))
    owner.configure_temporal("configure", memory_id="shared", action_ids=ACTIONS,
                             observation_ids=OBSERVATIONS, max_states=16)
    owner.learn_temporal("learn", memory_id="shared", source=source("base", [
        {"action": "start", "observation": "pending"},
        {"action": "finish", "observation": "done"},
    ]))
    owner.condense_temporal_skill("skill", memory_id="shared", skill_id="complete",
                                  goal_observations=("done",), forbidden_observations=("fault",))
    for participant in ("a", "b"):
        owner.bind_temporal("bind-" + participant, memory_id="shared", participant_id=participant)
    owner.compose_temporal_task("compose", task_id="pair", steps=[
        {"memory_id": "shared", "participant_id": participant, "skill_id": "complete"}
        for participant in ("a", "b")
    ])
    return owner


def propose(owner: FieldIntelligenceOwner, operation: str) -> dict:
    result = owner.propose_temporal_task(operation, task_id="pair", allowed_actions=[
        {"participant_id": participant, "action": action}
        for participant in ("a", "b") for action in ACTIONS
    ])
    assert result["receipt"]["status"] == "proposed"
    return dict(result["receipt"]["proposal"])


def ack(owner: FieldIntelligenceOwner, operation: str, proposal: dict, observation: str) -> dict:
    return dict(owner.acknowledge_temporal_task(
        operation, task_id="pair", proposal_id=proposal["proposal_id"],
        participant_id=proposal["participant_id"], action=proposal["action"], observation=observation,
    ))


def test_learning_and_restart_preserve_pending_bound_effect(tmp_path: Path) -> None:
    owner = setup_owner(tmp_path)
    try:
        first = propose(owner, "propose-first")
        assert first["participant_id"] == "a" and first["action"] == "start"
        ack(owner, "ack-first", first, "pending")
        pending = propose(owner, "propose-finish")
        assert pending["action"] == "finish"
        before_b = owner.inspect_temporal("shared", participant_id="b", skill_id="complete")["skill"]
        owner.learn_temporal("learn-during-pending", memory_id="shared", source=source("extra", [
            {"action": "inspect", "observation": "quiet"},
            {"action": "start", "observation": "pending"},
            {"action": "finish", "observation": "done"},
        ]))
        assert owner.inspect_temporal("shared", participant_id="a", skill_id="complete")["skill"]["action"] == "finish"
        after_b = owner.inspect_temporal("shared", participant_id="b", skill_id="complete")["skill"]
        assert (after_b["status"], after_b["action"]) == (before_b["status"], before_b["action"])
        frozen = owner.state.encode_bundle()
        owner.close()
        owner = FieldIntelligenceOwner(tmp_path)
        assert owner.state.encode_bundle() == frozen
        assert owner.inspect_temporal_task("pair")["pending_proposal"] == pending
        receipt = ack(owner, "ack-finish", pending, "done")
        identity = owner.state.state_sha256
        replay = ack(owner, "ack-finish", pending, "done")
        assert replay["receipt"] == receipt["receipt"] and replay["checkpoint_receipt"]["replayed"]
        assert owner.state.state_sha256 == identity
        next_proposal = propose(owner, "next-participant")
        assert next_proposal["participant_id"] == "b" and next_proposal["action"] == "start"
    finally:
        owner.close()


def test_foreign_acknowledgment_cannot_complete_another_participant(tmp_path: Path) -> None:
    owner = setup_owner(tmp_path)
    try:
        proposal = propose(owner, "first")
        before = owner.state.state_sha256
        with pytest.raises(FieldIntelligenceError) as denied:
            owner.acknowledge_temporal_task(
                "wrong-participant", task_id="pair", proposal_id=proposal["proposal_id"],
                participant_id="b", action=proposal["action"], observation="done",
            )
        assert denied.value.code == "OPERATION_CONFLICT"
        assert owner.state.state_sha256 == before
        ack(owner, "unknown-outcome", proposal, "fault")
        stopped = owner.propose_temporal_task("after-fault", task_id="pair", allowed_actions=[
            {"participant_id": "a", "action": action} for action in ACTIONS
        ])
        assert stopped["receipt"]["action"] is None
        assert owner.inspect_temporal("shared", participant_id="b", skill_id="complete")["skill"]["action"] == "start"
    finally:
        owner.close()


def test_learning_rebinds_task_evidence_for_later_revocation(tmp_path: Path) -> None:
    owner = setup_owner(tmp_path)
    try:
        extra = source("new-support", [{"action": "start", "observation": "pending"},
                                       {"action": "finish", "observation": "done"}])
        owner.learn_temporal("new-support", memory_id="shared", source=extra)
        plan = next(plan for plan in owner.state.plans if plan.goal_id == "pair")
        assert extra.revision_id in plan.source_revision_ids
        preview = owner.preview_forget((extra.revision_id,))
        owner.forget(operation_id="revoke", preview_id=preview["preview_id"], revision_ids=(extra.revision_id,),
                     grant=AuthorityGrant(grant_id="revoke", issuer="test", generation=owner.authority_generation,
                                          operation="forget", target=sha256_value([extra.revision_id]), scope="task-test"),
                     scope="task-test")
        assert owner.inspect_temporal_task("pair")["status"] == "invalidated"
        result = owner.propose_temporal_task("after-revoke", task_id="pair", allowed_actions=[
            {"participant_id": "a", "action": "start"}
        ])
        assert result["receipt"]["action"] is None
    finally:
        owner.close()


def test_outstanding_effect_blocks_independent_stream_mutations_and_tasks(tmp_path: Path) -> None:
    owner = setup_owner(tmp_path)
    try:
        pending = propose(owner, "pending")
        owner.compose_temporal_task("second-task", task_id="competing", steps=[
            {"memory_id": "shared", "participant_id": "a", "skill_id": "complete"}])
        before = owner.state.state_sha256
        mutations = [
            lambda: owner.advance_temporal("outside-ack", memory_id="shared", participant_id="a",
                                           action="start", observation="pending"),
            lambda: owner.reset_temporal("outside-reset", memory_id="shared", participant_id="a"),
            lambda: owner.bind_temporal("outside-bind", memory_id="shared", participant_id="a", known_start=False),
            lambda: owner.propose_temporal_task("competing-effect", task_id="competing", allowed_actions=[
                {"participant_id": "a", "action": "start"}]),
        ]
        for mutate in mutations:
            with pytest.raises(FieldIntelligenceError) as denied:
                mutate()
            assert denied.value.code == "OPERATION_CONFLICT"
            assert owner.state.state_sha256 == before
            assert owner.inspect_temporal_task("pair")["pending_proposal"] == pending
        ack(owner, "ack-real-effect", pending, "pending")
        assert owner.inspect_temporal("shared", participant_id="a", skill_id="complete")["skill"]["action"] == "finish"
    finally:
        owner.close()
def test_same_source_revision_replaces_prefix_and_keeps_pending_task_effect(tmp_path: Path) -> None:
    owner = setup_owner(tmp_path)
    base = source("base", [
        {"action": "start", "observation": "pending"},
        {"action": "finish", "observation": "done"},
    ])
    try:
        pending = propose(owner, "revision-pending")
        extended = revised(base, [
            {"action": "start", "observation": "pending"},
            {"action": "finish", "observation": "done"},
            {"action": "inspect", "observation": "quiet"},
            {"action": "start", "observation": "pending"},
        ])
        owner.learn_temporal("revision", memory_id="shared", source=extended)
        memory = owner.inspect_temporal("shared", action="start", participant_id="a")
        assert memory["source_revision_ids"] == [extended.revision_id]
        # The four actual observations appear once, including both starts.
        # Merging compatible states may pool them into the same action row.
        row = owner.state.temporal("shared")
        assert int(row.field[0, :row.max_states, :].sum()) == 4
        assert owner.inspect_temporal_task("pair")["pending_proposal"] == pending
    finally:
        owner.close()


def test_independent_identical_episodes_remain_separate_evidence(tmp_path: Path) -> None:
    owner = setup_owner(tmp_path)
    duplicate = source("independent-copy", [
        {"action": "start", "observation": "pending"},
        {"action": "finish", "observation": "done"},
    ])
    try:
        owner.learn_temporal("independent-copy", memory_id="shared", source=duplicate)
        memory = owner.inspect_temporal("shared", action="start")
        assert set(memory["source_revision_ids"]) == {
            source("base", [
                {"action": "start", "observation": "pending"},
                {"action": "finish", "observation": "done"},
            ]).revision_id,
            duplicate.revision_id,
        }
        assert memory["prediction"]["support"]["exposure"] == 2
    finally:
        owner.close()


def test_invalid_revision_is_atomic_and_rejects_foreign_or_forked_parent(tmp_path: Path) -> None:
    owner = setup_owner(tmp_path)
    base = source("base", [
        {"action": "start", "observation": "pending"},
        {"action": "finish", "observation": "done"},
    ])
    foreign = source("foreign", [
        {"action": "start", "observation": "pending"},
        {"action": "finish", "observation": "done"},
    ])
    try:
        owner.configure_temporal("configure-other", memory_id="other", action_ids=ACTIONS,
                                 observation_ids=OBSERVATIONS, max_states=16)
        owner.learn_temporal("learn-foreign", memory_id="other", source=foreign)
        before_state = owner.state.state_sha256
        before_revisions = owner.evidence.all_revision_ids()
        with pytest.raises(FieldIntelligenceError) as no_op:
            owner.learn_temporal("no-op", memory_id="shared", source=revised(base, [
                {"action": "start", "observation": "pending"},
                {"action": "finish", "observation": "done"},
            ]))
        assert no_op.value.code == "INVALID_TEMPORAL_EPISODE"
        with pytest.raises(FieldIntelligenceError) as foreign_parent:
            owner.learn_temporal("foreign-parent", memory_id="shared", source=revised(foreign, [
                {"action": "start", "observation": "pending"},
                {"action": "finish", "observation": "done"},
                {"action": "inspect", "observation": "quiet"},
            ]))
        assert foreign_parent.value.code == "SOURCE_PARENT_CONFLICT"
        assert owner.state.state_sha256 == before_state
        assert owner.evidence.all_revision_ids() == before_revisions
    finally:
        owner.close()


def test_revised_parent_forgetting_cannot_retract_current_episode_or_task(tmp_path: Path) -> None:
    owner = setup_owner(tmp_path)
    base = source("base", [
        {"action": "start", "observation": "pending"},
        {"action": "finish", "observation": "done"},
    ])
    extended = revised(base, [
        {"action": "start", "observation": "pending"},
        {"action": "finish", "observation": "done"},
        {"action": "inspect", "observation": "quiet"},
    ])
    try:
        owner.learn_temporal("revision-forget", memory_id="shared", source=extended)
        preview = owner.preview_forget((base.revision_id,))
        assert preview["binding"]["affected_temporal_ids"] == []
        owner.forget(
            operation_id="forget-parent", preview_id=preview["preview_id"],
            revision_ids=(base.revision_id,),
            grant=AuthorityGrant(
                grant_id="forget-parent", issuer="test",
                generation=owner.authority_generation, operation="forget",
                target=sha256_value([base.revision_id]), scope="task-test",
            ),
            scope="task-test",
        )
        assert owner.inspect_temporal("shared")["source_revision_ids"] == [extended.revision_id]
        assert owner.inspect_temporal_task("pair")["status"] != "invalidated"
    finally:
        owner.close()
def test_revision_restart_and_exact_retry_are_idempotent(tmp_path: Path) -> None:
    owner = setup_owner(tmp_path)
    base = source("base", [
        {"action": "start", "observation": "pending"},
        {"action": "finish", "observation": "done"},
    ])
    extended = revised(base, [
        {"action": "start", "observation": "pending"},
        {"action": "finish", "observation": "done"},
        {"action": "inspect", "observation": "quiet"},
        {"action": "start", "observation": "pending"},
    ])
    try:
        first = owner.learn_temporal("revision-retry", memory_id="shared", source=extended)
        identity = owner.state.state_sha256
        owner.close()
        owner = FieldIntelligenceOwner(tmp_path)
        replay = owner.learn_temporal("revision-retry", memory_id="shared", source=extended)
        assert replay["checkpoint_receipt"]["replayed"]
        assert replay["receipt"] == first["receipt"]
        assert owner.state.state_sha256 == identity
    finally:
        owner.close()


@pytest.mark.parametrize("cutpoint", ["source-stored", "event-appended"])
def test_interrupted_revision_recovers_once_with_outstanding_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cutpoint: str,
) -> None:
    owner = setup_owner(tmp_path)
    base = source("base", [
        {"action": "start", "observation": "pending"},
        {"action": "finish", "observation": "done"},
    ])
    extended = revised(base, [
        {"action": "start", "observation": "pending"},
        {"action": "finish", "observation": "done"},
        {"action": "inspect", "observation": "quiet"},
    ])
    try:
        pending = propose(owner, "before-interruption")
        count = owner.evidence.event_count

        def interrupt(*args: object, **kwargs: object) -> None:
            raise OSError("simulated interrupted admission")

        with monkeypatch.context() as patch:
            target, name = (
                (owner.evidence, "append_event") if cutpoint == "source-stored"
                else (owner, "_publish")
            )
            patch.setattr(target, name, interrupt)
            with pytest.raises(OSError):
                owner.learn_temporal("interrupted-revision", memory_id="shared", source=extended)
        owner.close()
        owner = FieldIntelligenceOwner(tmp_path)
        recovered = owner.state.temporal("shared")
        assert recovered.source_revision_ids == (extended.revision_id,)
        assert int(recovered.field[0, :recovered.max_states, :].sum()) == 3
        assert owner.evidence.event_count == count + 1
        assert owner.inspect_temporal_task("pair")["pending_proposal"] == pending
        identity = owner.state.state_sha256
        replay = owner.learn_temporal("interrupted-revision", memory_id="shared", source=extended)
        assert replay["checkpoint_receipt"]["replayed"]
        assert owner.state.state_sha256 == identity
        assert owner.evidence.event_count == count + 1
        ack(owner, "ack-recovered-effect", pending, "pending")
        assert owner.inspect_temporal("shared", participant_id="a", skill_id="complete")["skill"]["action"] == "finish"
    finally:
        owner.close()


def test_committed_temporal_operation_recovers_after_pending_unlink_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = setup_owner(tmp_path)
    episode = source("committed-before-unlink", [
        {"action": "inspect", "observation": "quiet"},
        {"action": "start", "observation": "pending"},
        {"action": "finish", "observation": "done"},
    ])
    event_count = owner.evidence.event_count
    try:
        def interrupt(_operation_id: str) -> None:
            raise OSError("simulated pending unlink interruption")

        with monkeypatch.context() as patch:
            patch.setattr(owner, "_finish_pending", interrupt)
            with pytest.raises(OSError):
                owner.learn_temporal(
                    "committed-before-unlink",
                    memory_id="shared",
                    source=episode,
                )
        committed_state = owner.state.state_sha256
        committed_manifest = owner.checkpoints.current_manifest_sha256
        assert owner.evidence.event_count == event_count + 1
        assert len(list(owner.pending_path.iterdir())) == 1
        assert owner.checkpoints._operation_path("committed-before-unlink").is_file()
        owner.close()

        owner = FieldIntelligenceOwner(tmp_path)
        assert owner.state.state_sha256 == committed_state
        assert owner.checkpoints.current_manifest_sha256 == committed_manifest
        assert owner.evidence.event_count == event_count + 1
        assert list(owner.pending_path.iterdir()) == []
        replay = owner.learn_temporal(
            "committed-before-unlink",
            memory_id="shared",
            source=episode,
        )
        assert replay["checkpoint_receipt"]["replayed"]
        assert owner.state.state_sha256 == committed_state
        assert owner.evidence.event_count == event_count + 1
    finally:
        owner.close()


def test_uncommitted_temporal_event_cannot_rebase_onto_later_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = setup_owner(tmp_path)
    episode = source("lineage-conflict", [
        {"action": "inspect", "observation": "quiet"},
        {"action": "start", "observation": "pending"},
    ])
    try:
        def interrupt(*_args: object, **_kwargs: object) -> None:
            raise OSError("simulated checkpoint interruption")

        with monkeypatch.context() as patch:
            patch.setattr(owner, "_publish", interrupt)
            with pytest.raises(OSError):
                owner.learn_temporal(
                    "lineage-conflict",
                    memory_id="shared",
                    source=episode,
                )
        pending_path = next(owner.pending_path.iterdir())
        pending_bytes = pending_path.read_bytes()
        evidence_index_bytes = owner.evidence.index_path.read_bytes()
        predecessor_state = owner.state.state_sha256
        successor = owner.state.with_transition(
            "simulated-later-commit",
            {"predecessor_state_sha256": predecessor_state},
            logical_tick=owner.state.logical_tick + 1,
        )
        owner.checkpoints.commit(
            operation_id="simulated-later-commit",
            successor=successor,
            event_id=None,
            transition={
                "kind": "simulated-later-commit",
                "predecessor_state_sha256": predecessor_state,
            },
        )
        owner.close()

        with pytest.raises(FieldIntelligenceError) as conflict:
            FieldIntelligenceOwner(tmp_path)
        assert conflict.value.code == "LINEAGE_CONFLICT"
        assert pending_path.read_bytes() == pending_bytes
        assert owner.evidence.index_path.read_bytes() == evidence_index_bytes
    finally:
        owner.close()


def test_forgetting_current_revision_cannot_revive_superseded_prefix(tmp_path: Path) -> None:
    owner = setup_owner(tmp_path)
    base = source("base", [
        {"action": "start", "observation": "pending"},
        {"action": "finish", "observation": "done"},
    ])
    extended = revised(base, [
        {"action": "start", "observation": "pending"},
        {"action": "finish", "observation": "done"},
        {"action": "inspect", "observation": "quiet"},
    ])
    try:
        owner.learn_temporal("current-revision", memory_id="shared", source=extended)
        prior_manifest = owner.checkpoints.current_manifest_sha256
        preview = owner.preview_forget((extended.revision_id,))
        owner.forget(
            operation_id="forget-current", preview_id=preview["preview_id"],
            revision_ids=(extended.revision_id,),
            grant=AuthorityGrant(
                grant_id="forget-current", issuer="test",
                generation=owner.authority_generation, operation="forget",
                target=sha256_value([extended.revision_id]), scope="task-test",
            ),
            scope="task-test",
        )
        owner.close()
        owner = FieldIntelligenceOwner(tmp_path)
        assert not owner.inspect_temporal("shared", action="start")["prediction"]["supported"]
        assert owner.inspect_temporal_task("pair")["status"] == "invalidated"
        with pytest.raises(FieldIntelligenceError):
            owner.learn_temporal("revive-parent", memory_id="shared", source=base)
        with pytest.raises(FieldIntelligenceError):
            owner.learn_temporal("revive-head", memory_id="shared", source=extended)
        with pytest.raises(FieldIntelligenceError) as stale:
            owner.checkpoints.load_version(prior_manifest)
        assert stale.value.code == "STALE_REVOCATION"
        assert not owner.inspect_temporal("shared", action="start")["prediction"]["supported"]
    finally:
        owner.close()


def test_temporal_replay_rejects_receipt_inconsistent_with_successor(
    tmp_path: Path,
) -> None:
    owner = FieldIntelligenceOwner(
        tmp_path,
        initial_state=AtlasState(resonant_workspace=None),
    )
    try:
        memory = TemporalField.initial(
            "corrupt-replay",
            action_ids=ACTIONS,
            observation_ids=OBSERVATIONS,
            max_states=16,
        )
        request = {
            "action_ids": list(memory.action_ids),
            "context": dict(memory.context),
            "expected_state_sha256": None,
            "kind": "configure-temporal",
            "max_states": memory.max_states,
            "memory_id": memory.memory_id,
            "observation_ids": list(memory.observation_ids),
        }
        successor = owner._temporal_successor(memory, request)
        owner._publish(
            operation_id="configure:corrupt-replay",
            successor=successor,
            event_id=None,
            transition={
                "kind": request["kind"],
                "request": request,
                "request_sha256": sha256_value(request),
                "result": {
                    "receipt": {
                        "memory_id": memory.memory_id,
                        "memory_sha256": "0" * 64,
                        "state_count": memory.state_count,
                    }
                },
            },
        )
        committed = owner.state.state_sha256
        with pytest.raises(FieldIntelligenceError) as corrupt:
            owner.configure_temporal(
                "configure:corrupt-replay",
                memory_id=memory.memory_id,
                action_ids=ACTIONS,
                observation_ids=OBSERVATIONS,
                max_states=16,
            )
        assert corrupt.value.code == "CHECKPOINT_CORRUPT"
        assert owner.state.state_sha256 == committed
    finally:
        owner.close()


def test_regional_temporal_task_state_resumes_reset_and_projects_scope() -> None:
    state = regional_state(
        "regional-task",
        action_ids=("start", "finish"),
        observation_ids=("pending", "done"),
        max_states=8,
        episodes=[[{"action": "start", "observation": "pending"}]],
        source_revision_ids=("a" * 64,),
    )
    while True:
        transition = regional_kernel(state, {}, 1)
        state = transition.state
        if transition.status != "yield":
            assert transition.status == "done"
            assert transition.output["schema"] == REGIONAL_RESULT_SCHEMA
            break
    reset = regional_kernel(
        state,
        {"operation": "reset", "participant_id": "new", "known_start": False},
        1,
    )
    assert reset.output["candidate_states"] == list(range(state["model"]["state_count"]))
    projection = regional_kernel(
        reset.state,
        {"operation": "project", "skill_id": "missing", "scope_id": "scope"},
        1,
    )
    assert projection.output["scope"]["scope_id"] == "scope"
    assert projection.state["projection_scopes"]["scope"]["skill_id"] == "missing"
