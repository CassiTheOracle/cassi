from __future__ import annotations

import base64
import hashlib
import json
import numpy as np
import pytest

from cassi_temporal_field import (
    REGIONAL_KERNEL_NAME,
    REGIONAL_RESULT_SCHEMA,
    REGIONAL_STATE_SCHEMA,
    TemporalField,
    TemporalFieldError,
    regional_kernel,
    regional_state,
)


def revision(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()


def step(action: str, observation: str) -> dict[str, str]:
    return {"action": action, "observation": observation}


def test_matched_present_retains_different_observed_histories() -> None:
    field = TemporalField.initial("memory", action_ids=("cue", "idle", "query"),
                                  observation_ids=("x", "y", "quiet", "p", "q"), max_states=16)
    episodes = [[step("cue", cue), *([step("idle", "quiet")] * length), step("query", answer)]
                for cue, answer in (("x", "p"), ("y", "q")) for length in (1, 2, 3)]
    learned, _ = field.learn(episodes, source_revision_ids=(revision("histories"),))
    predictions = []
    for cue in ("x", "y"):
        current, _ = learned.consume("cue", cue)
        for _ in range(19):
            current, _ = current.consume("idle", "quiet")
        predictions.append(current.predict("query")["probabilities"])
        assert current.memory_sha256 == learned.memory_sha256
        assert current.reset().state_sha256 == learned.state_sha256
    assert predictions == [{"p": 1.0}, {"q": 1.0}]
    assert not field.predict("query")["supported"]


def test_skills_make_progress_and_remain_independently_addressable() -> None:
    field = TemporalField.initial("skills", action_ids=("idle", "go", "finish", "divert"),
                                  observation_ids=("quiet", "start", "goal", "other"), max_states=16)
    episodes = [[*([step("idle", "quiet")] * length), step("go", "start"), step("finish", "goal")]
                for length in (0, 1, 2)]
    episodes.append([step("divert", "other")])
    learned, _ = field.learn(episodes, source_revision_ids=(revision("skills"),))
    first, _ = learned.condense_skill("finish-job", goal_observations=("goal",))
    assert first.skill_action("finish-job")["action"] == "go"
    assert first.skill_action("finish-job")["remaining_steps"] == 2
    both, _ = first.condense_skill("different-job", goal_observations=("other",))
    assert both.skill_action("finish-job")["action"] == "go"
    assert both.skill_action("different-job")["action"] == "divert"
    current, _ = both.consume("go", "start")
    assert current.skill_action("finish-job")["action"] == "finish"
    assert current.skill_action("finish-job")["remaining_steps"] == 1
    done, _ = current.consume("finish", "goal")
    assert done.skill_action("finish-job")["status"] == "complete"
    assert done.reset().skill_action("different-job")["action"] == "divert"
    assert done.memory_sha256 == learned.memory_sha256
    restored = TemporalField.from_dict(done.as_dict())
    assert restored.as_dict() == done.as_dict()


def test_skill_pool_signal_is_a_fixed_readout_of_safe_temporal_rank() -> None:
    field = TemporalField.initial(
        "pool-signal",
        action_ids=("prime", "align", "open"),
        observation_ids=("primed", "aligned", "opened"),
        max_states=8,
    )
    pending, _ = field.condense_skill(
        "release",
        goal_observations=("opened",),
    )
    assert pending.skill_pool_signal("release") == {
        "schema": "cassifi.temporal-skill-pool-signal.v1",
        "skill_id": "release",
        "status": "pending",
        "mapping": "safe-reachability-rank-linear-seven-pool-v1",
        "supported_states": 0,
        "maximum_rank": 0,
        "pool_signal": [0.0] * 7,
    }
    learned, receipt = pending.learn(
        [[
            step("prime", "primed"),
            step("align", "aligned"),
            step("open", "opened"),
        ]],
        source_revision_ids=(revision("pool-signal"),),
    )
    expected = 1.0 / np.sqrt(3.0)
    assert receipt["formed_skills"] == ["release"]
    assert learned.skill_pool_signal("release") == {
        "schema": "cassifi.temporal-skill-pool-signal.v1",
        "skill_id": "release",
        "status": "formed",
        "mapping": "safe-reachability-rank-linear-seven-pool-v1",
        "supported_states": 3,
        "maximum_rank": 3,
        "pool_signal": [expected, 0.0, 0.0, expected, 0.0, 0.0, expected],
    }
    assert TemporalField.from_dict(learned.as_dict()).skill_pool_signal(
        "release"
    ) == learned.skill_pool_signal("release")



def test_unknown_outcome_keeps_sensing_until_evidence_repairs_context() -> None:
    field = TemporalField.initial("unknown", action_ids=("go", "finish"),
                                  observation_ids=("start", "goal", "bad"), max_states=8)
    base = [step("go", "start"), step("finish", "goal")]
    learned, _ = field.learn([base], source_revision_ids=(revision("unknown"),))
    skill, _ = learned.condense_skill("job", goal_observations=("goal",))
    unknown, _ = skill.consume("go", "bad")
    assert unknown.skill_action("job")["status"] == "unresolved"
    later, receipt = unknown.consume("go", "start")
    assert not receipt["supported"]
    assert not receipt["halted"]
    assert later.history() == (step("go", "bad"), step("go", "start"))
    assert later.memory_sha256 == learned.memory_sha256
    assert later.predict("finish")["support"]["unknown_successor"]
    repaired, _ = later.learn([base, [*later.history(), step("finish", "goal")]],
                               source_revision_ids=(revision("unknown"), revision("repair")))
    assert repaired.history() == later.history()
    assert repaired.skill_action("job")["action"] == "finish"


def test_supported_step_recovers_active_context_without_erasing_prior_gap() -> None:
    field = TemporalField.initial(
        "recovery",
        action_ids=("open", "inspect", "idle", "read", "release"),
        observation_ids=("ready", "closed", "quiet", "pulse-a", "pulse-b", "requested"),
        max_states=24,
    )
    episodes = [
        [
            step("open", "ready"),
            step("inspect", "closed"),
            step("idle", "quiet"),
            step("read", pulse),
            step("release", "requested"),
        ]
        for pulse in ("pulse-a", "pulse-b")
    ]
    learned, _ = field.learn(episodes, source_revision_ids=(revision("recovery"),))
    skilled, _ = learned.condense_skill("release", goal_observations=("requested",))

    unresolved, first = skilled.reset(known_start=False).consume("inspect", "closed")
    assert first["context"]["status"] == "unresolved"
    assert first["context"]["uncovered_history"] is True
    assert unresolved.skill_action("release")["status"] == "unresolved"

    recovered, second = unresolved.consume("idle", "quiet")
    assert second["supported"] is True
    assert second["context"] == {
        "status": "recovered",
        "candidate_states": [3],
        "uncovered_history": True,
        "unknown_start": True,
    }
    assert recovered.skill_action("release")["action"] == "read"
    assert recovered.predict("read")["support"]["context"] == second["context"]
    restored = TemporalField.from_dict(recovered.as_dict())
    assert restored.as_dict() == recovered.as_dict()
    assert restored.context_status() == second["context"]


def test_context_discovery_preserves_conflicting_continuations_and_rebuild_counts() -> None:
    field = TemporalField.initial("contexts", action_ids=("cue", "query"), observation_ids=("a", "b", "yes", "no"), max_states=8)
    normal = [step("cue", "a"), step("query", "yes")]
    exception = [step("cue", "b"), step("query", "no")]
    normal_revision, exception_revision = revision("normal"), revision("exception")
    first, _ = field.learn([normal], source_revision_ids=(normal_revision,))
    assert not first.consume("cue", "b")[0].predict("query")["supported"]
    final, _ = first.learn([normal, exception], source_revision_ids=(normal_revision, exception_revision))
    assert final.predict("cue")["probabilities"] == {"a": .5, "b": .5}
    assert final.consume("cue", "a")[0].predict("query")["probabilities"] == {"yes": 1.0}
    assert final.consume("cue", "b")[0].predict("query")["probabilities"] == {"no": 1.0}
    assert first.predict("cue")["probabilities"] == {"a": 1.0}
    with pytest.raises(TemporalFieldError):
        TemporalField.initial("bounded", action_ids=field.action_ids, observation_ids=field.observation_ids, max_states=1).learn(
            [normal, exception], source_revision_ids=(normal_revision, exception_revision))


def test_numeric_and_metadata_corruption_cannot_enter_canonical_state() -> None:
    field = TemporalField.initial("restart", action_ids=("a",), observation_ids=("x",), max_states=8, context={"nested": {"id": "x"}})
    learned, _ = field.learn([[step("a", "x")]], source_revision_ids=(revision("restart"),))
    assert TemporalField.from_dict(learned.as_dict()).as_dict() == learned.as_dict()
    with pytest.raises(TypeError):
        field.context["nested"]["id"] = "mutated"
    for coordinates in ((0, 3 * field.max_states, 0), (0, 8 * field.max_states, 0)):
        altered = learned.field
        altered[coordinates] = 1.5
        payload = dict(learned.as_dict())
        payload["field_b64"] = base64.b64encode(altered.tobytes()).decode("ascii")
        payload["state_sha256"] = hashlib.sha256(altered.tobytes()).hexdigest()
        with pytest.raises(TemporalFieldError):
            TemporalField.from_dict(payload)
    with pytest.raises(TemporalFieldError):
        TemporalField.initial("invalid-codec", action_ids=(["unhashable"],), observation_ids=("x",))
    with pytest.raises(TemporalFieldError):
        learned.learn([[step("unknown", "x")]], source_revision_ids=(revision("invalid"),))


def test_codec_relabel_cannot_reinterpret_serialized_transitions() -> None:
    field = TemporalField.initial("codec", action_ids=("a", "b"), observation_ids=("x", "y"), max_states=8)
    learned, _ = field.learn([[step("a", "x")]], source_revision_ids=(revision("codec"),))
    payload = dict(learned.as_dict())
    payload["action_ids"] = ["b", "a"]
    with pytest.raises(TemporalFieldError):
        TemporalField.from_dict(payload)


def test_equal_outcome_sets_do_not_erase_distinct_observed_frequencies() -> None:
    field = TemporalField.initial("frequencies", action_ids=("cue", "query"), observation_ids=("x", "y", "a", "b"), max_states=8)
    episodes = [[step("cue", cue), step("query", outcome)]
                for cue, outcomes in (("x", ["a"]*9+["b"]), ("y", ["a"]+["b"]*9))
                for outcome in outcomes]
    learned, _ = field.learn(episodes, source_revision_ids=(revision("frequencies"),))
    assert learned.consume("cue", "x")[0].predict("query")["probabilities"] == {"a": .9, "b": .1}
    assert learned.consume("cue", "y")[0].predict("query")["probabilities"] == {"a": .1, "b": .9}


def test_partial_action_coverage_preserves_recurrent_history() -> None:
    field = TemporalField.initial("partial", action_ids=("cue", "idle", "query"),
                                  observation_ids=("signal", "quiet", "blocked"), max_states=8)
    learned, _ = field.learn(
        [[step("cue", "signal"), step("idle", "quiet"), step("idle", "quiet"), step("query", "blocked")]],
        source_revision_ids=(revision("partial"),),
    )
    current, _ = learned.consume("cue", "signal")
    for _ in range(11):
        current, _ = current.consume("idle", "quiet")
    assert current.predict("query")["probabilities"] == {"blocked": 1.0}


def test_participant_bindings_keep_independent_numeric_working_coordinates() -> None:
    field = TemporalField.initial("participants", action_ids=("cue", "query"),
                                  observation_ids=("a", "b", "yes", "no"), max_states=8)
    learned, _ = field.learn(
        [[step("cue", "a"), step("query", "yes")], [step("cue", "b"), step("query", "no")]],
        source_revision_ids=(revision("participants"),))
    both = learned.bind("A").bind("B")
    advanced, _ = both.consume("cue", "a", participant_id="A")
    assert advanced.history(participant_id="A") == ({"action": "cue", "observation": "a"},)
    assert advanced.history(participant_id="B") == ()
    assert advanced.predict("query", participant_id="A")["probabilities"] == {"yes": 1.0}
    assert not advanced.predict("query", participant_id="B")["supported"]


def test_learning_replays_retained_events_after_state_number_remapping() -> None:
    field = TemporalField.initial("remap", action_ids=("cue", "query"),
                                  observation_ids=("a", "b", "yes", "no"), max_states=8)
    first, _ = field.learn([[step("cue", "a"), step("query", "yes")]],
                           source_revision_ids=(revision("remap-1"),))
    active, _ = first.consume("cue", "a")
    revised, receipt = active.learn(
        [[step("cue", "a"), step("query", "yes")], [step("cue", "b"), step("query", "no")]],
        source_revision_ids=(revision("remap-1"), revision("remap-2")))
    assert receipt["status"] == "resolved"
    assert revised.history() == active.history()
    assert revised.predict("query")["probabilities"] == {"yes": 1.0}


def test_unknown_reset_false_exposes_all_candidates_without_hidden_state() -> None:
    field = TemporalField.initial("belief", action_ids=("cue", "query"),
                                  observation_ids=("a", "b", "yes", "no"), max_states=8)
    learned, _ = field.learn(
        [[step("cue", "a"), step("query", "yes")], [step("cue", "b"), step("query", "no")]],
        source_revision_ids=(revision("belief"),))
    uncertain = learned.reset(known_start=False)
    assert uncertain.candidate_states() == tuple(range(uncertain.state_count))
    assert not uncertain.skill_ids


def test_numeric_history_and_participants_survive_exact_reload() -> None:
    field = TemporalField.initial("reload", action_ids=("cue", "query"),
                                  observation_ids=("a", "yes"), max_states=8)
    learned, _ = field.learn([[step("cue", "a"), step("query", "yes")]],
                             source_revision_ids=(revision("reload"),))
    current, _ = learned.bind("participant").consume("cue", "a", participant_id="participant")
    restored = TemporalField.from_dict(current.as_dict())
    assert restored.as_dict() == current.as_dict()
    assert restored.history(participant_id="participant") == current.history(participant_id="participant")


def test_learning_revalidates_skill_identity_and_safe_action() -> None:
    field = TemporalField.initial("skill-revalidate", action_ids=("go", "finish"),
                                  observation_ids=("start", "goal", "bad"), max_states=8)
    learned, _ = field.learn([[step("go", "start"), step("finish", "goal")]],
                             source_revision_ids=(revision("skill-base"),))
    skilled, _ = learned.condense_skill("job", goal_observations=("goal",), forbidden_observations=("bad",))
    active, _ = skilled.consume("go", "start")
    revised, receipt = active.learn(
        [[step("go", "start"), step("finish", "goal")], [step("go", "start"), step("finish", "bad")]],
        source_revision_ids=(revision("skill-base"), revision("skill-unsafe")))
    assert revised.skill_ids == ("job",)
    assert revised.formed_skill_ids == ()
    assert revised.pending_skill_ids == ("job",)
    assert receipt["status"] == "resolved"
    assert receipt["formed_skills"] == []
    assert receipt["withdrawn_skills"] == ["job"]
    assert receipt["available_skills"] == []
    assert receipt["pending_skills"] == ["job"]
    assert revised.skill_action("job")["status"] == "unresolved"



def test_registered_skill_forms_only_after_a_supported_safe_root_path_exists() -> None:
    field = TemporalField.initial(
        "skill-emergence",
        action_ids=("start", "finish"),
        observation_ids=("ready", "done", "fault"),
        max_states=8,
    )
    pending, registration = field.condense_skill(
        "job",
        goal_observations=("done",),
        forbidden_observations=("fault",),
    )
    assert registration["status"] == "pending"
    assert registration["start_state_supported"] is False
    assert pending.skill_ids == ("job",)
    assert pending.formed_skill_ids == ()
    assert pending.pending_skill_ids == ("job",)
    assert pending.skill_action("job")["status"] == "unresolved"

    partial, partial_receipt = pending.learn(
        [[step("start", "ready")]],
        source_revision_ids=(revision("skill-partial"),),
    )
    assert partial_receipt["formed_skills"] == []
    assert partial_receipt["available_skills"] == []
    assert partial_receipt["pending_skills"] == ["job"]

    formed, formation = partial.learn(
        [[step("start", "ready"), step("finish", "done")]],
        source_revision_ids=(revision("skill-complete"),),
    )
    assert formation["formed_skills"] == ["job"]
    assert formation["withdrawn_skills"] == []
    assert formation["available_skills"] == ["job"]
    assert formation["pending_skills"] == []
    assert formed.formed_skill_ids == ("job",)
    assert formed.skill_action("job")["action"] == "start"

    withdrawn, withdrawal = formed.learn(
        [
            [step("start", "ready"), step("finish", "done")],
            [step("start", "ready"), step("finish", "fault")],
        ],
        source_revision_ids=(
            revision("skill-complete"),
            revision("skill-hazard"),
        ),
    )
    assert withdrawal["formed_skills"] == []
    assert withdrawal["withdrawn_skills"] == ["job"]
    assert withdrawal["available_skills"] == []
    assert withdrawal["pending_skills"] == ["job"]
    assert withdrawn.skill_action("job")["status"] == "unresolved"


def test_history_overflow_is_reported_unresolved_on_learning() -> None:
    field = TemporalField.initial("overflow", action_ids=("go",), observation_ids=("ok",), max_states=2)
    learned, _ = field.learn([[step("go", "ok")]], source_revision_ids=(revision("overflow"),))
    active, _ = learned.consume("go", "ok")
    assert active.history() == ()
    revised, receipt = active.learn([[step("go", "ok")]], source_revision_ids=(revision("overflow"),))
    assert receipt["status"] == "unresolved"
    assert revised.predict("go")["supported"] is False


def test_at_state_is_ephemeral_and_cannot_consume() -> None:
    field = TemporalField.initial("projection", action_ids=("go",), observation_ids=("ok",), max_states=4)
    learned, _ = field.learn([[step("go", "ok")]], source_revision_ids=(revision("projection"),))
    projection = learned.at_state(0)
    assert projection.predict("go")["supported"]
    assert projection.as_dict() == learned.as_dict()
    with pytest.raises(TemporalFieldError):
        projection.consume("go", "ok")


def test_unknown_start_history_replays_without_inventing_root_context() -> None:
    field = TemporalField.initial("unknown-start", action_ids=("sense", "inspect", "finish"),
                                  observation_ids=("a", "b", "quiet", "yes", "no"), max_states=16)
    episodes = [[step("sense", cue), step("inspect", "quiet"), step("finish", outcome)]
                for cue, outcome in (("a", "yes"), ("b", "no"))]
    learned, _ = field.learn(episodes, source_revision_ids=(revision("unknown-start"),))
    active, _ = learned.reset(known_start=False).consume("inspect", "quiet")
    prediction = active.predict("finish")
    assert not prediction["supported"]
    assert prediction["probabilities"] == {}
    assert prediction["support"]["unknown_successor"]
    assert {row["observation"] for row in prediction["support"]["outcomes"]} == {"yes", "no"}
    revised, _ = active.learn(episodes, source_revision_ids=(revision("unknown-start"),))
    assert revised.predict("finish") == active.predict("finish")
    assert revised.history() == active.history()
    assert len(revised.candidate_states()) == 2


def test_learning_preserves_observed_completion_but_projection_cannot_claim_it() -> None:
    field = TemporalField.initial("observed-goal", action_ids=("start", "finish"),
                                  observation_ids=("pending", "done"), max_states=8)
    episodes = [[step("start", "pending"), step("finish", "done")]]
    learned, _ = field.learn(episodes, source_revision_ids=(revision("observed-goal"),))
    skilled, _ = learned.condense_skill("job", goal_observations=("done",))
    active, _ = skilled.consume("start", "pending")
    done, _ = active.consume("finish", "done")
    revised, _ = done.learn(episodes, source_revision_ids=(revision("observed-goal"),))
    assert revised.skill_action("job")["status"] == "complete"
    assert revised.at_state(0).skill_action("job")["action"] == "start"
    assert revised.skill_action("job")["status"] == "complete"


def test_participant_relabel_cannot_reinterpret_serialized_working_memory() -> None:
    field = TemporalField.initial("identities", action_ids=("sense",), observation_ids=("seen",), max_states=8)
    payload = dict(field.bind("a").bind("b").as_dict())
    payload["participant_ids"] = ["b", "a"]
    with pytest.raises(TemporalFieldError):
        TemporalField.from_dict(payload)


def test_missing_probe_does_not_erase_a_hazard_bearing_alternative() -> None:
    field = TemporalField.initial("gap", action_ids=("cue", "probe", "other", "finish"),
                                  observation_ids=("a", "b", "seen", "quiet", "done", "fault"), max_states=16)
    episodes = [
        [step("cue", "a"), step("probe", "seen"), step("finish", "done")],
        [step("cue", "b"), step("other", "quiet"), step("finish", "fault")],
    ]
    learned, _ = field.learn(episodes, source_revision_ids=(revision("gap"),))
    skilled, _ = learned.condense_skill("job", goal_observations=("done",), forbidden_observations=("fault",))
    active, receipt = skilled.reset(known_start=False).consume("probe", "seen")
    assert receipt["unknown_successor"]
    assert not receipt["supported"]
    assert not active.predict("finish")["supported"]
    assert active.predict("finish")["probabilities"] == {}
    assert active.skill_action("job")["status"] == "unresolved"
    assert active.memory_sha256 == skilled.memory_sha256
    restored = TemporalField.from_dict(active.as_dict())
    assert restored.predict("finish") == active.predict("finish")
    rebuilt, _ = restored.learn(episodes, source_revision_ids=(revision("gap"),))
    assert rebuilt.predict("finish") == active.predict("finish")


def test_forbidden_outcomes_refine_recursively_merged_successor_contexts() -> None:
    field = TemporalField.initial(
        "recursive-evidence",
        action_ids=("cue", "sync", "go", "wait"),
        observation_ids=("a", "b", "quiet", "done", "fault"),
        max_states=16,
    )
    episodes = [
        [step("cue", "a"), step("sync", "quiet"), step("go", "done")],
        [step("cue", "b"), step("sync", "quiet"), step("wait", "fault")],
    ]
    learned, _ = field.learn(
        episodes,
        source_revision_ids=(revision("recursive-evidence"),),
    )
    skilled, _ = learned.condense_skill(
        "job", goal_observations=("done",), forbidden_observations=("fault",),
    )
    refined, _ = skilled.learn(
        episodes,
        source_revision_ids=(revision("recursive-evidence"),),
    )

    safe, _ = refined.reset(known_start=False).consume("cue", "a")
    safe, _ = safe.consume("sync", "quiet")
    hazardous, _ = refined.reset(known_start=False).consume("cue", "b")
    hazardous, _ = hazardous.consume("sync", "quiet")

    assert safe.context_status()["status"] == "recovered"
    assert safe.skill_action("job")["action"] == "go"
    assert hazardous.context_status()["status"] == "recovered"
    assert hazardous.skill_action("job")["status"] == "unresolved"


def test_supported_effects_transfer_orders_and_long_delays_without_losing_context() -> None:
    field = TemporalField.initial("effects", action_ids=("cue", "a", "b", "query"),
                                  observation_ids=("x", "y", "u", "v", "yes", "no"), max_states=32)
    episodes = [
        [step("cue", cue), *[step(action, {"a": "u", "b": "v"}[action]) for action in order],
         step("query", answer)]
        for cue, answer in (("x", "yes"), ("y", "no"))
        for order in (("a",), ("b",), ("a", "b"), ("b", "a"), ("a", "a"), ("b", "b"))
    ]
    learned, _ = field.learn(episodes, source_revision_ids=(revision("effects"),))
    for cue, answer in (("x", "yes"), ("y", "no")):
        active, _ = learned.consume("cue", cue)
        for action in ("b", "a", "b", *(["a"] * 19), "b"):
            active, _ = active.consume(action, {"a": "u", "b": "v"}[action])
        assert active.predict("query")["probabilities"] == {answer: 1.0}
        assert active.memory_sha256 == learned.memory_sha256
        revised, _ = active.learn([*episodes, episodes[0]], source_revision_ids=(revision("effects"), revision("additional-observation")))
        assert revised.predict("query")["probabilities"] == {answer: 1.0}
        assert revised.history() == active.history()


def test_small_sampling_difference_does_not_split_equivalent_stochastic_contexts() -> None:
    field = TemporalField.initial("sampling", action_ids=("cue", "query"),
                                  observation_ids=("x", "y", "a", "b"), max_states=16)
    episodes = [[step("cue", cue), step("query", outcome)]
                for cue, outcomes in (("x", ("a", "b")), ("y", ("a", "b", "a")))
                for outcome in outcomes]
    learned, _ = field.learn(episodes, source_revision_ids=(revision("sampling"),))
    for cue in ("x", "y"):
        active, _ = learned.consume("cue", cue)
        assert active.predict("query")["probabilities"] == {"a": .6, "b": .4}
    assert int(learned.field[0, :learned.max_states, :].sum()) == 10


def test_first_codec_action_can_be_condensed_and_executed() -> None:
    field = TemporalField.initial("first-action", action_ids=("open", "close"),
                                  observation_ids=("ready", "closed"), max_states=8)
    field, _ = field.learn([[step("open", "ready")]],
                           source_revision_ids=(revision("first-action"),))
    skilled, receipt = field.condense_skill("prepare", goal_observations=("ready",))
    assert receipt["status"] == "formed"
    assert receipt["start_state_supported"] is True
    assert receipt["supported_states"] == 1
    assert skilled.skill_action("prepare")["action"] == "open"
    completed, _ = skilled.consume("open", "ready")
    assert completed.skill_action("prepare")["status"] == "complete"


def _drain_regional_temporal(state: dict, arguments: dict, *, quantum: int = 1) -> tuple[dict, dict]:
    current = state
    while True:
        transition = regional_kernel(current, arguments, quantum)
        if transition.status != "yield":
            return transition.state, transition.output
        current = transition.state


def test_regional_temporal_pause_replay_participants_and_unknown_support() -> None:
    episodes = [[step("open", "ready"), step("close", "done")]]
    arguments = {
        "operation": "induce",
        "episodes": episodes,
        "source_revision_ids": [revision("regional-temporal")],
    }
    initial = regional_state(
        "regional-temporal",
        action_ids=("open", "close"),
        observation_ids=("ready", "done", "fault"),
        max_states=8,
    )
    first = regional_kernel(initial, arguments, 1)
    assert REGIONAL_KERNEL_NAME == "temporal-memory"
    assert first.status == "yield"
    checkpoint = json.loads(json.dumps(first.state, sort_keys=True))
    resumed_a = regional_kernel(first.state, arguments, 1)
    resumed_b = regional_kernel(checkpoint, arguments, 1)
    assert resumed_a.state == resumed_b.state
    learned, induction_receipt = _drain_regional_temporal(resumed_a.state, arguments)
    assert induction_receipt["schema"] == REGIONAL_RESULT_SCHEMA
    assert learned["schema"] == REGIONAL_STATE_SCHEMA

    skill_arguments = {
        "operation": "skill",
        "skill_id": "finish",
        "goal_observations": ["done"],
    }
    skill_first = regional_kernel(learned, skill_arguments, 1)
    assert skill_first.status == "yield"
    skill_checkpoint = json.loads(json.dumps(skill_first.state, sort_keys=True))
    skill_a = regional_kernel(skill_first.state, skill_arguments, 1)
    skill_b = regional_kernel(skill_checkpoint, skill_arguments, 1)
    assert skill_a.state == skill_b.state
    skilled, skill_receipt = _drain_regional_temporal(skill_a.state, skill_arguments)
    assert skill_receipt["status"] == "formed"
    selected = regional_kernel(
        skilled, {"operation": "select", "skill_id": "finish"}, 1
    )
    assert selected.output["status"] == "proposed"
    assert selected.output["action"] == "open"

    bound_b = regional_kernel(
        skilled,
        {"operation": "consume", "action": "open", "observation": "ready", "participant_id": "B"},
        1,
    ).state
    participant_a = regional_kernel(
        bound_b,
        {"operation": "consume", "action": "open", "observation": "ready", "participant_id": "A"},
        1,
    ).state
    assert participant_a["participants"]["B"] == bound_b["participants"]["B"]
    assert participant_a["participants"]["A"]["history"] == [
        {"action": "open", "observation": "ready"}
    ]
    assert participant_a["participants"][""]["history"] == []

    replayed, replay_receipt = _drain_regional_temporal(skilled, arguments)
    assert replay_receipt["status"] == "replayed"
    assert replayed["model"]["exposures"] == skilled["model"]["exposures"]
    assert replayed["model"]["sources"] == skilled["model"]["sources"]
    unsupported = regional_kernel(
        skilled,
        {"operation": "consume", "action": "close", "observation": "done"},
        1,
    )
    assert unsupported.output["status"] == "unknown-support"
    refused = regional_kernel(
        unsupported.state, {"operation": "select", "skill_id": "finish"}, 1
    )
    assert refused.output["status"] == "unresolved"
