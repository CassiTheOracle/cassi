from __future__ import annotations

import shutil

import pytest

from cassi_field_atlas import FieldIntelligenceError
from run_temporal_materialized_composition import (
    MEMORY_ID,
    PARTICIPANT_ID,
    setup,
)


def test_state_conditioned_materialization_changes_field_and_consumes_observation() -> None:
    owner, home, _ = setup("tmat-test-success-")
    try:
        owner.advance_temporal("test:left", memory_id=MEMORY_ID, participant_id=PARTICIPANT_ID, action="left-step", observation="left-goal")
        proposal = owner.synthesize_temporal_transition(memory_id=MEMORY_ID, skill_id="right-skill", participant_id=PARTICIPANT_ID)
        before = owner.inspect_temporal(MEMORY_ID, action="right-step", participant_id=PARTICIPANT_ID)
        committed = owner.materialize_temporal_transition(
            "test:commit", memory_id=MEMORY_ID, skill_id="right-skill", participant_id=PARTICIPANT_ID,
            action="right-step", observation="right-goal", hypothesis_sha256=proposal["hypothesis_sha256"],
            expected_state_sha256=owner.state.state_sha256,
        )
        after = owner.inspect_temporal(MEMORY_ID, participant_id=PARTICIPANT_ID)
        assert before["prediction"]["supported"] is False
        assert committed["receipt"]["observed_outcome"] is True
        assert committed["receipt"]["training_source_admitted"] is False
        assert committed["receipt"]["previous_state_sha256"] != committed["receipt"]["state_sha256"]
        assert before["state_sha256"] != after["state_sha256"]
        assert after["candidate_states"] == [1]
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)

def test_mismatch_fails_closed_without_field_mutation() -> None:
    owner, home, _ = setup("tmat-test-mismatch-")
    try:
        owner.advance_temporal("test:left", memory_id=MEMORY_ID, participant_id=PARTICIPANT_ID, action="left-step", observation="left-goal")
        proposal = owner.synthesize_temporal_transition(memory_id=MEMORY_ID, skill_id="right-skill", participant_id=PARTICIPANT_ID)
        atlas_before = owner.state.state_sha256
        before = owner.inspect_temporal(MEMORY_ID, participant_id=PARTICIPANT_ID)
        with pytest.raises(FieldIntelligenceError):
            owner.materialize_temporal_transition(
                "test:mismatch", memory_id=MEMORY_ID, skill_id="right-skill", participant_id=PARTICIPANT_ID,
                action="right-step", observation="wrong-goal", hypothesis_sha256=proposal["hypothesis_sha256"],
                expected_state_sha256=atlas_before,
            )
        after = owner.inspect_temporal(MEMORY_ID, participant_id=PARTICIPANT_ID)
        assert owner.state.state_sha256 == atlas_before
        assert before["state_sha256"] == after["state_sha256"]
        assert before["memory_sha256"] == after["memory_sha256"]
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)

def test_wrong_expected_state_is_rejected_without_owner_mutation() -> None:
    owner, home, _ = setup("tmat-test-state-guard-")
    try:
        owner.advance_temporal("test:left", memory_id=MEMORY_ID, participant_id=PARTICIPANT_ID, action="left-step", observation="left-goal")
        proposal = owner.synthesize_temporal_transition(memory_id=MEMORY_ID, skill_id="right-skill", participant_id=PARTICIPANT_ID)
        before = owner.inspect_temporal(MEMORY_ID, participant_id=PARTICIPANT_ID)
        atlas_before = owner.state.state_sha256
        with pytest.raises(FieldIntelligenceError):
            owner.materialize_temporal_transition(
                "test:wrong-state", memory_id=MEMORY_ID, skill_id="right-skill", participant_id=PARTICIPANT_ID,
                action="right-step", observation="right-goal", hypothesis_sha256=proposal["hypothesis_sha256"],
                expected_state_sha256="0" * 64,
            )
        after = owner.inspect_temporal(MEMORY_ID, participant_id=PARTICIPANT_ID)
        assert owner.state.state_sha256 == atlas_before
        assert before["state_sha256"] == after["state_sha256"]
        assert before["memory_sha256"] == after["memory_sha256"]
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)
