from __future__ import annotations

import hashlib
import json

import pytest

from cassi_temporal_field import TemporalField
from cassi_temporal_inquiry import (
    REGIONAL_KERNEL_MAX_WORK,
    REGIONAL_KERNEL_NAME,
    REGIONAL_STATE_SCHEMA,
    TemporalInquiryError,
    choose_temporal_inquiry,
    regional_kernel,
    regional_state,
)


def revision(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()


def step(action: str, observation: str) -> dict[str, str]:
    return {"action": action, "observation": observation}


def make_field(episodes: list[list[dict[str, str]]]) -> TemporalField:
    field = TemporalField.initial(
        "inquiry",
        action_ids=("sense", "pulse", "reveal", "unique_a", "unique_b"),
        observation_ids=("a", "b", "ready", "hold", "left", "right", "oa", "ob"),
        max_states=32,
    )
    # Observe pulse from every phase, including a recurrent terminal phase.
    # Only the two pre-reveal contexts produce ready; no missing row is
    # silently used to eliminate an alternative.
    episodes = [
        *episodes,
        *[episode[:length] + [step("pulse", "oa")] * 2
          for episode in episodes for length in range(len(episode) + 1)
          if length != 1],
    ]
    learned, _ = field.learn(episodes, source_revision_ids=(revision("inquiry"),))
    unknown = learned.reset(known_start=False)
    filtered, receipt = unknown.consume("pulse", "ready")
    assert receipt["supported"]
    assert len(filtered.candidate_states()) == 2
    return filtered


def operation(
    action: str,
    *,
    authorized: bool = True,
    feasible: bool = True,
    acquisition_allowed: bool = False,
    cost: float = 1.0,
) -> dict[str, object]:
    return {
        "action": action,
        "cost": cost,
        "risk": 0.0,
        "authorized": authorized,
        "feasible": feasible,
        "acquisition_allowed": acquisition_allowed,
    }


def two_step_field() -> TemporalField:
    return make_field([
        [
            step("sense", "a"),
            step("pulse", "ready"),
            step("reveal", "hold"),
            step("reveal", "left"),
        ],
        [
            step("sense", "b"),
            step("pulse", "ready"),
            step("reveal", "hold"),
            step("reveal", "right"),
        ],
    ])


def test_two_step_observation_policy_resolves_when_no_one_step_test_does() -> None:
    field = two_step_field()
    one_step = choose_temporal_inquiry(
        field,
        operations=(operation("reveal"),),
        horizon=1,
    )
    assert one_step["action"] is None
    assert one_step["reason"] == "horizon-exhausted"

    result = choose_temporal_inquiry(
        field,
        operations=(operation("reveal"),),
        horizon=2,
    )
    assert result["status"] == "resolving"
    assert result["action"] == "reveal"
    assert result["candidate_states"] == list(field.candidate_states())
    assert result["policy"]["action"] == "reveal"
    first_branch = result["policy"]["branches"]["hold"]
    assert first_branch["candidate_states"] == list(field.candidate_states())
    assert first_branch["policy"]["action"] == "reveal"
    assert set(first_branch["policy"]["branches"]) == {"left", "right"}
    assert all(
        branch["candidate_states"] and branch["status"] == "resolved"
        for branch in first_branch["policy"]["branches"].values()
    )


def test_unauthorized_or_infeasible_operations_are_refused() -> None:
    field = two_step_field()
    unauthorized = choose_temporal_inquiry(
        field,
        operations=(operation("reveal", authorized=False),),
    )
    assert unauthorized["status"] == "unresolved"
    assert unauthorized["action"] is None
    assert unauthorized["reason"] == "authority"

    infeasible = choose_temporal_inquiry(
        field,
        operations=(operation("reveal", feasible=False),),
    )
    assert infeasible["status"] == "unresolved"
    assert infeasible["action"] is None
    assert infeasible["reason"] == "feasibility"


def test_forbidden_or_missing_support_cannot_be_certified() -> None:
    field = two_step_field()
    forbidden = choose_temporal_inquiry(
        field,
        operations=(operation("reveal"),),
        forbidden_observations=("hold",),
    )
    assert forbidden["status"] == "unresolved"
    assert forbidden["action"] is None
    assert forbidden["reason"] == "forbidden-observation"

    missing = choose_temporal_inquiry(
        field,
        operations=(operation("unique_b"),),
    )
    assert missing["status"] == "unresolved"
    assert missing["action"] is None
    assert missing["reason"] == "unsupported-action"


def test_repeated_noninformative_observations_remain_unresolved() -> None:
    field = make_field([
        [
            step("sense", "a"),
            step("pulse", "ready"),
            step("reveal", "hold"),
            step("reveal", "hold"),
            step("unique_a", "oa"),
        ],
        [
            step("sense", "b"),
            step("pulse", "ready"),
            step("reveal", "hold"),
            step("reveal", "hold"),
            step("unique_a", "ob"),
        ],
    ])
    result = choose_temporal_inquiry(
        field,
        operations=(operation("reveal"),),
        horizon=3,
    )
    assert result["status"] == "unresolved"
    assert result["action"] is None
    assert result["candidate_states"] == list(field.candidate_states())


def test_input_schema_and_budget_are_bounded() -> None:
    field = two_step_field()
    with pytest.raises(TemporalInquiryError):
        choose_temporal_inquiry(field, operations=(), horizon=1)
    with pytest.raises(TemporalInquiryError):
        choose_temporal_inquiry(field, operations=(operation("reveal"),), max_nodes=0)
    with pytest.raises(TemporalInquiryError):
        choose_temporal_inquiry(
            field,
            operations=({**operation("reveal"), "extra": True},),
        )

def test_permitted_missing_support_is_acquisition_not_resolution() -> None:
    field = two_step_field()
    result = choose_temporal_inquiry(
        field,
        operations=(operation("unique_a", acquisition_allowed=True),),
    )
    assert result["status"] == "acquiring"
    assert result["action"] == "unique_a"
    assert result["reason"] == "acquisition-permitted"
    assert result["acquisition"]["host_permitted"] is True
    assert result["acquisition"]["decision_resolved"] is False
    assert result["policy"]["kind"] == "acquisition"
    assert result["policy"]["missing_states"]


def test_acquisition_prefers_observed_information_over_name_and_cost() -> None:
    field = make_field([
        [step("sense", "a"), step("pulse", "ready"), step("reveal", "hold"), step("reveal", "left")],
        [step("sense", "b"), step("pulse", "ready"), step("reveal", "hold"), step("reveal", "right")],
        [step("sense", "a"), step("pulse", "ready"), step("unique_a", "oa")],
    ])
    result = choose_temporal_inquiry(
        field,
        operations=(
            operation("unique_b", acquisition_allowed=True),
            operation("unique_a", acquisition_allowed=True, cost=9.0),
        ),
    )
    assert result["status"] == "acquiring"
    assert result["action"] == "unique_a"
    assert result["acquisition"]["actual_exposure"] is True



def test_singleton_gap_can_request_bounded_acquisition() -> None:
    field = two_step_field()
    field, first = field.consume("reveal", "hold")
    assert first["supported"]
    field, second = field.consume("reveal", "left")
    assert second["supported"]
    assert len(field.candidate_states()) == 1
    result = choose_temporal_inquiry(
        field,
        operations=(operation("unique_a", acquisition_allowed=True),),
    )
    assert result["status"] == "acquiring"
    assert result["acquisition"]["decision_resolved"] is False



def test_no_candidate_gap_can_request_bounded_acquisition() -> None:
    field = two_step_field()
    field, receipt = field.consume("unique_b", "ob")
    assert receipt["supported"] is False
    assert field.candidate_states() == ()
    result = choose_temporal_inquiry(
        field,
        operations=(operation("unique_a", acquisition_allowed=True),),
    )
    assert result["status"] == "acquiring"
    assert result["candidate_states"] == []
    assert result["acquisition"]["decision_resolved"] is False


def test_acquisition_rotates_from_a_repeated_gap_to_untried_support() -> None:
    field = TemporalField.initial(
        "rotating-acquisition",
        action_ids=("a", "b", "unknown"),
        observation_ids=("x", "y"),
        max_states=8,
    )
    learned, _ = field.learn(
        [
            [step("a", "x"), step("a", "x")],
            [step("b", "y")],
        ],
        source_revision_ids=(revision("rotation-a"), revision("rotation-b")),
    )
    active, receipt = learned.reset(known_start=False).consume("unknown", "x")
    assert receipt["supported"] is False
    assert active.candidate_states() == ()
    first = choose_temporal_inquiry(
        active,
        operations=(
            operation("a", acquisition_allowed=True),
            operation("b", acquisition_allowed=True),
        ),
    )
    assert first["action"] == "a"
    repeated, _ = active.consume("a", "x")
    second = choose_temporal_inquiry(
        repeated,
        operations=(
            operation("a", acquisition_allowed=True),
            operation("b", acquisition_allowed=True),
        ),
    )
    assert second["action"] == "b"


def test_missing_support_without_permission_remains_refused() -> None:
    field = two_step_field()
    result = choose_temporal_inquiry(field, operations=(operation("unique_a"),))
    assert result["action"] is None
    assert result["status"] == "unresolved"
    assert result["acquisition"]["host_permitted"] is False
    assert result["reason"] == "unsupported-action"
@pytest.mark.parametrize(
    "authorized, feasible, reason",
    [
        (False, True, "authority"),
        (True, False, "feasibility"),
    ],
)
def test_acquisition_requires_authority_and_feasibility(
    authorized: bool, feasible: bool, reason: str,
) -> None:
    field = two_step_field()
    result = choose_temporal_inquiry(
        field,
        operations=(
            operation(
                "unique_a",
                authorized=authorized,
                feasible=feasible,
                acquisition_allowed=True,
            ),
        ),
    )
    assert result["action"] is None
    assert result["reason"] == reason

def test_known_forbidden_outcome_blocks_acquisition() -> None:
    field = two_step_field()
    result = choose_temporal_inquiry(
        field,
        operations=(operation("pulse", acquisition_allowed=True),),
        forbidden_observations=("oa",),
    )
    assert result["action"] is None
    assert result["reason"] == "forbidden-observation"


def test_supported_observation_discrimination_precedes_acquisition() -> None:
    field = two_step_field()
    result = choose_temporal_inquiry(
        field,
        operations=(
            operation("reveal", acquisition_allowed=True),
            operation("unique_a", acquisition_allowed=True, cost=9.0),
        ),
        horizon=2,
    )
    assert result["status"] == "resolving"
    assert result["action"] == "reveal"
    assert result["acquisition"]["host_permitted"] is False


def test_transient_goal_policy_acts_without_persisting_a_skill() -> None:
    field = TemporalField.initial(
        "transient-goal",
        action_ids=("start", "finish"),
        observation_ids=("ready", "done", "fault"),
        max_states=8,
    )
    learned, _ = field.learn(
        [[step("start", "ready"), step("finish", "done")]],
        source_revision_ids=(revision("transient-goal"),),
    )
    identity = learned.state_sha256
    first = choose_temporal_inquiry(
        learned,
        operations=(operation("start"), operation("finish")),
        goal_observations=("done",),
        forbidden_observations=("fault",),
    )
    assert first["status"] == "resolving"
    assert first["action"] == "start"
    assert first["policy"]["kind"] == "transient-goal"
    assert learned.skill_ids == ()
    assert learned.state_sha256 == identity

    active, _ = learned.consume("start", "ready")
    second = choose_temporal_inquiry(
        active,
        operations=(operation("start"), operation("finish")),
        goal_observations=("done",),
        forbidden_observations=("fault",),
    )
    assert second["action"] == "finish"
    assert active.skill_ids == ()
    with pytest.raises(TemporalInquiryError):
        choose_temporal_inquiry(
            learned,
            operations=(operation("start"),),
            skill_id="missing",
            goal_observations=("done",),
        )


def test_carried_unknown_branch_cannot_certify_apparent_discrimination() -> None:
    field = TemporalField.initial(
        "incomplete", action_ids=("sense", "pulse", "reveal"),
        observation_ids=("a", "b", "ready", "hold", "left", "right"), max_states=16,
    )
    episodes = [[step("sense", cue), step("pulse", "ready"),
                 step("reveal", "hold"), step("reveal", outcome)]
                for cue, outcome in (("a", "left"), ("b", "right"))]
    learned, _ = field.learn(episodes, source_revision_ids=(revision("incomplete"),))
    active, receipt = learned.reset(known_start=False).consume("pulse", "ready")
    assert receipt["unknown_successor"]
    assert len(active.candidate_states()) == 2
    result = choose_temporal_inquiry(active, operations=(operation("reveal"),), horizon=2)
    assert result["status"] == "unresolved"
    assert result["action"] is None
    acquired = choose_temporal_inquiry(
        active, operations=(operation("reveal", acquisition_allowed=True),), horizon=2,
    )
    assert acquired["status"] == "acquiring"
    assert not acquired["decision_resolved"]
    assert acquired["acquisition"]["unknown_successor"]


def test_carried_unknown_uses_supported_recovery_sequence_before_gap_fallback() -> None:
    field = TemporalField.initial(
        "recovery-inquiry",
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
    learned, _ = field.learn(episodes, source_revision_ids=(revision("recovery-inquiry"),))
    skilled, _ = learned.condense_skill("release", goal_observations=("requested",))
    active, receipt = skilled.reset(known_start=False).consume("inspect", "closed")
    assert receipt["unknown_successor"] is True

    result = choose_temporal_inquiry(
        active,
        operations=(
            operation("read", acquisition_allowed=True),
            operation("idle", acquisition_allowed=True),
            operation("inspect", acquisition_allowed=True),
        ),
        skill_id="release",
        horizon=3,
    )
    assert result["status"] == "acquiring"
    assert result["action"] == "idle"
    assert result["reason"] == "context-recovery-sequence"
    assert result["decision_resolved"] is False
    assert result["policy"]["kind"] == "context-recovery"
    assert result["policy"]["branches"]["quiet"]["status"] == "resolved"
    assert result["acquisition"]["strategy"] == "bounded-sequence"


def test_regional_inquiry_pause_resume_preserves_policy_and_logical_work() -> None:
    field = two_step_field()
    state = regional_state(
        field,
        operations=(operation("reveal"),),
        horizon=2,
    )
    assert REGIONAL_KERNEL_NAME == "inquiry.temporal"
    assert REGIONAL_KERNEL_MAX_WORK > 0
    assert state["schema"] == REGIONAL_STATE_SCHEMA
    assert {
        "survivors",
        "policy_tree",
        "candidate_cursor",
        "numeric_cursor",
        "proof_cursor",
        "assumptions",
        "unresolved_obligations",
        "limits",
        "work",
    } <= set(state)

    uninterrupted = regional_kernel(
        json.loads(json.dumps(state, sort_keys=True)),
        {},
        REGIONAL_KERNEL_MAX_WORK,
    )
    resumed = regional_kernel(
        json.loads(json.dumps(state, sort_keys=True)),
        {},
        1,
    )
    while resumed.status != "done":
        resumed = regional_kernel(
            json.loads(json.dumps(resumed.state, sort_keys=True)),
            {},
            1,
        )
    assert uninterrupted.status == "done"
    assert resumed.output == uninterrupted.output
    assert resumed.output["policy"] == uninterrupted.output["policy"]
    assert resumed.output["costs"] == uninterrupted.output["costs"]
    assert resumed.output["work"] == uninterrupted.output["work"]


def test_regional_inquiry_failed_assumption_is_explicit_and_non_authoritative() -> None:
    state = regional_state(
        two_step_field(),
        operations=(operation("reveal"),),
        assumptions=(
            {
                "name": "fixed-observation-model",
                "status": "failed",
                "kind": "model-bound",
                "model_conditional": True,
            },
        ),
    )
    result = regional_kernel(state, {}, 1)
    assert result.status == "done"
    assert result.output["action"] is None
    assert result.output["decision_resolved"] is False
    assert result.output["reason"] == "failed-assumption"
    assert result.state["unresolved_obligations"] == ["fixed-observation-model"]
