"""Regressions for temporal error, evidence ownership, and assembly boundaries."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
import torch

from cassi_field_atlas import (
    AtlasState, FieldAtlas, FieldIntelligenceError, Guard, RelationChart,
    VariableSpec, canonical_json_bytes, sha256_value,
)
from cassi_field_transceiver import advance_transceiver, inspect_transceiver, reset_transceiver
from cassi_resonant_field import ResonantNumericalError, ResonantProfile, initial_workspace


@pytest.fixture(scope="module")
def field():
    torch.set_num_threads(1)
    atlas = FieldAtlas()
    state = AtlasState(resonant_workspace=initial_workspace(ResonantProfile(beta=0.0, damping=0.5)))
    for prefix in ("a", "b"):
        for name in ("input", "output"):
            state = atlas.add_variable(state, VariableSpec(f"{prefix}:{name}", lower=-20.0, upper=20.0))
        state = atlas.add_chart(state, RelationChart.empty(
            chart_id=prefix, scope=(f"{prefix}:input", f"{prefix}:output"),
            ridge=0.05, observation_norm_bound=20.0, prior_mass=1e-4,
            guards=(Guard("mode", "eq", "connected"),),
        ))
        for index, value in enumerate((-2.0, -1.0, 1.0, 2.0)):
            state, _ = atlas.admit_observation(
                state, event_id=sha256_value([prefix, index, "event"]),
                source_revision_id=sha256_value([prefix, index, "source"]),
                values={f"{prefix}:input": value, f"{prefix}:output": 2.0 * value},
                context={"mode": "connected"}, target_chart_ids=(prefix,),
            )
        state, _ = atlas.condense_transceiver(
            state, transceiver_id=prefix, chart_ids=(prefix,),
            input_ids=(f"{prefix}:input",), output_ids=(f"{prefix}:output",),
            context={"mode": "connected"}, rank=16, error_allowance=1e-3,
            input_bound=4.0, horizon_ticks=32,
        )
    return atlas, state


def test_input_uncertainty_survives_silence_and_full_expansion(field):
    _, state = field
    kernel = state.transceiver("a").kernel
    uncertain = reset_transceiver(kernel)
    actual = reset_transceiver(kernel)
    for tick in range(8):
        uncertain, receipt = advance_transceiver(
            kernel, uncertain, inputs={"a:input": 0.0},
            input_errors={"a:input": 0.01 if tick == 0 else 0.0}, force_full=tick >= 1,
        )
        actual, actual_receipt = advance_transceiver(
            kernel, actual, inputs={"a:input": 0.01 if tick == 0 else 0.0}, force_full=True,
        )
        error = abs(actual_receipt["values"]["a:output"] - receipt["values"]["a:output"])
        assert error <= receipt["error_bound"] + actual_receipt["error_bound"] + 1e-9
        if tick == 1:
            assert error > 1e-8
            assert inspect_transceiver(kernel, uncertain)["error_bound"] >= error



def test_coordinate_transport_is_retained_and_corruption_refused(field):
    _, state = field
    kernel = state.transceiver("a").kernel
    working, receipt = advance_transceiver(
        kernel, reset_transceiver(kernel), inputs={"a:input": 0.0},
        input_errors={"a:input": 1e-6},
    )
    assert working["mode"] == "reduced"
    assert any(value > 0.0 for value in working["transport_error"])
    assert inspect_transceiver(kernel, working)["error_bound"] == pytest.approx(receipt["error_bound"])

    corrupted = dict(working)
    corrupted["state_error"] = float(working["state_error"]) + 1.0
    with pytest.raises(ResonantNumericalError):
        inspect_transceiver(kernel, corrupted)

def test_long_trajectory_remains_enclosed_after_declared_horizon(field):
    _, state = field
    kernel = state.transceiver("a").kernel
    reduced, full = reset_transceiver(kernel), reset_transceiver(kernel)
    reduced_steps = 0
    for tick in range(64):
        signal = 0.7 * np.sin(tick * 0.23)
        reduced, receipt = advance_transceiver(kernel, reduced, inputs={"a:input": float(signal)})
        full, reference = advance_transceiver(kernel, full, inputs={"a:input": float(signal)}, force_full=True)
        reduced_steps += receipt["counts"]["reduced_steps"]
        assert abs(receipt["values"]["a:output"] - reference["values"]["a:output"]) <= receipt["error_bound"] + reference["error_bound"] + 1e-8
    assert reduced_steps > 0
    assert reduced["mode"] == "full"


def test_changing_parent_removes_only_dependent_realization(field):
    atlas, state = field
    a = state.chart("a")
    changed = atlas.replace_chart(state, replace(a, factor_weight=0.5, version=a.version + 1))
    assert changed.transceiver("a").status == "stale"
    assert changed.transceiver("a").kernel is None
    assert changed.transceiver("a").working_state is None
    assert changed.transceiver("b") is state.transceiver("b")
    with pytest.raises(FieldIntelligenceError, match="stale"):
        atlas.reset_transceiver(changed, transceiver_id="a")
    assert AtlasState.decode_bundle(changed.encode_bundle()).state_sha256 == changed.state_sha256


def test_guard_and_conflicting_drivers_are_atomic(field):
    atlas, state = field
    identity = state.state_sha256
    with pytest.raises(FieldIntelligenceError) as rejected:
        atlas.advance_transceivers(state, stimuli={"a": {"a:input": 1.0}}, context={"mode": "disconnected"})
    assert rejected.value.code == "TRANSCEIVER_INAPPLICABLE"
    link = {"source": "a", "output": "a:output", "target": "b", "input": "b:input"}
    with pytest.raises(FieldIntelligenceError) as ambiguous:
        atlas.advance_transceivers(state, stimuli={"b": {"b:input": 1.0}}, context={"mode": "connected"}, connections=(link,))
    assert ambiguous.value.code == "AMBIGUOUS_TRANSCEIVER"
    assert state.state_sha256 == identity


def test_connection_uses_previous_state_not_iteration_order(field):
    atlas, state = field
    link = {"source": "a", "output": "a:output", "target": "b", "input": "b:input"}
    first, _ = atlas.advance_transceivers(state, stimuli={"a": {"a:input": 1.0}, "b": {}}, context={"mode": "connected"}, connections=(link,))
    swapped, _ = atlas.advance_transceivers(state, stimuli={"b": {}, "a": {"a:input": 1.0}}, context={"mode": "connected"}, connections=(link,))
    assert first.state_sha256 == swapped.state_sha256
    previous = inspect_transceiver(state.transceiver("a").kernel, state.transceiver("a").working_state)
    working, _ = advance_transceiver(state.transceiver("b").kernel, state.transceiver("b").working_state,
        inputs={"b:input": previous["values"]["a:output"]}, input_errors={"b:input": previous["error_bound"]})
    assert canonical_json_bytes(first.transceiver("b").working_state) == canonical_json_bytes(working)


def test_empty_extension_preserves_existing_v2_descriptor_shape():
    state = AtlasState()
    # Old checkpoints need not be migrated just to open an unused capability.
    descriptor = __import__("json").loads(state.encode())
    assert "transceivers" not in descriptor["pages"]
    assert AtlasState.decode(state.encode(), state.object_pages()).state_sha256 == state.state_sha256


def test_revocation_blocks_replaying_transceiver_results(tmp_path):
    from cassi_field_owner import AuthorityGrant, FieldIntelligenceOwner, SourceInput

    with FieldIntelligenceOwner(tmp_path / "owner") as owner:
        for name in ("input", "output"):
            owner.configure_variable(f"variable:{name}", VariableSpec(name))
        owner.configure_chart("chart", RelationChart.empty(
            chart_id="relation", scope=("input", "output"),
            ridge=0.05, observation_norm_bound=20.0, prior_mass=1e-4,
        ))
        revisions = []
        for index, value in enumerate((-2.0, -1.0, 1.0, 2.0)):
            values = {"input": value, "output": 2.0 * value}
            result = owner.admit_observation(
                operation_id=f"observation:{index}",
                source=SourceInput(
                    source_id=f"measurement:{index}", content=canonical_json_bytes(values),
                    media_type="application/json", codec="utf-8", observed_timestamp=str(index),
                    scope="test", claim_category="controlled-measurement", fidelity="exact-record",
                    labels=("test",),
                ),
                values=values, context={}, target_chart_ids=("relation",),
            )
            revisions.append(result["source"]["revision_id"])
        operations = (
            lambda: owner.condense_transceiver(
                "condense", transceiver_id="unit", chart_ids=("relation",),
                input_ids=("input",), output_ids=("output",), context={},
            ),
            lambda: owner.advance_transceivers(
                "transmit", stimuli={"unit": {"input": 0.5}}, context={},
            ),
            lambda: owner.reset_transceiver("reset", transceiver_id="unit"),
        )
        results = [operation() for operation in operations]
        before = owner.state.state_sha256
        for operation, original in zip(operations, results, strict=True):
            assert canonical_json_bytes(operation()["receipt"]) == canonical_json_bytes(original["receipt"])
        assert owner.state.state_sha256 == before

        preview = owner.preview_forget((revisions[0],))
        owner.forget(
            operation_id="forget", preview_id=preview["preview_id"],
            revision_ids=(revisions[0],), scope="test",
            grant=AuthorityGrant(
                grant_id="forget-grant", issuer="test", generation=owner.authority_generation,
                operation="forget", target=sha256_value([revisions[0]]), scope="test",
            ),
        )
        after = owner.state.state_sha256
        for operation in operations:
            with pytest.raises(FieldIntelligenceError) as rejected:
                operation()
            assert rejected.value.code == "STALE_REVOCATION"
        assert owner.state.state_sha256 == after


def test_multivariate_realization_uses_field_capacity_and_survives_restart(tmp_path):
    from cassi_field_owner import FieldIntelligenceOwner, SourceInput

    inputs = tuple(f"x{index}" for index in range(5))
    initial = AtlasState(resonant_workspace=initial_workspace(ResonantProfile(beta=0.0, damping=0.5)))
    with FieldIntelligenceOwner(tmp_path, initial_state=initial) as owner:
        owner.configure_variable("bias", VariableSpec("bias", kind="constant", constant=1.0))
        for name in (*inputs, "output"):
            owner.configure_variable(f"variable:{name}", VariableSpec(name))
        owner.configure_chart("chart", RelationChart.empty(
            chart_id="history", scope=("bias", *inputs, "output"),
            ridge=0.01, observation_norm_bound=100.0, prior_mass=1e-4,
        ))
        for index, values in enumerate(np.random.default_rng(17).uniform(-1, 1, size=(16, 5))):
            observation = {"bias": 1.0, **dict(zip(inputs, values)),
                           "output": float(values @ np.array([.62, .18, -.11, .56, .14]))}
            owner.admit_observation(
                operation_id=f"observation:{index}",
                source=SourceInput(
                    source_id=f"measurement:{index}", content=canonical_json_bytes(observation),
                    media_type="application/json", codec="utf-8", observed_timestamp=str(index),
                    scope="test", claim_category="controlled-measurement", fidelity="exact-record",
                ), values=observation, context={}, target_chart_ids=("history",),
            )
        committed, manifest = owner.state.state_sha256, owner.checkpoints.current_manifest_sha256
        bounded_limits = replace(
            owner.limits, max_workspace_bytes=owner.state.workspace_usage()["workspace_bytes"],
        )
    with FieldIntelligenceOwner(tmp_path, limits=bounded_limits) as bounded:
        with pytest.raises(FieldIntelligenceError) as rejected:
            bounded.condense_transceiver(
                "condense", transceiver_id="temporal", chart_ids=("history",),
                input_ids=inputs, output_ids=("output",), context={},
            )
        assert rejected.value.code == "FIELD_CAPACITY"
        assert bounded.state.state_sha256 == committed
        assert bounded.checkpoints.current_manifest_sha256 == manifest
    stimuli = {"temporal": dict(zip(inputs, (.2, -.3, .5, -.7, .1)))}
    with FieldIntelligenceOwner(tmp_path) as owner:
        owner.condense_transceiver(
            "condense", transceiver_id="temporal", chart_ids=("history",),
            input_ids=inputs, output_ids=("output",), context={},
        )
        replayed_condense = owner.condense_transceiver(
            "condense",
            transceiver_id="temporal",
            chart_ids=("history",),
            input_ids=inputs,
            output_ids=("output",),
            context={},
        )
        assert replayed_condense["checkpoint_receipt"]["replayed"] is True
        result = owner.advance_transceivers("drive", stimuli=stimuli, context={}, ticks=4)
        expected = result["receipt"]["transceivers"]["temporal"]["values"]
        committed = owner.state.state_sha256
        assert AtlasState.decode_bundle(owner.state.encode_bundle()).state_sha256 == committed
    with FieldIntelligenceOwner(tmp_path) as restarted:
        assert restarted.state.state_sha256 == committed
        restarted.reset_transceiver("reset-after-restart", transceiver_id="temporal")
        result = restarted.advance_transceivers("drive-after-restart", stimuli=stimuli, context={}, ticks=4)
        assert result["receipt"]["transceivers"]["temporal"]["values"] == expected


def test_owner_rejects_transceiver_receipts_that_disagree_with_committed_state(
    tmp_path,
):
    from cassi_field_owner import FieldIntelligenceOwner, SourceInput

    initial = AtlasState(
        resonant_workspace=initial_workspace(
            ResonantProfile(beta=0.0, damping=0.5)
        )
    )
    with FieldIntelligenceOwner(tmp_path, initial_state=initial) as owner:
        for name in ("input", "output"):
            owner.configure_variable(
                f"variable:{name}",
                VariableSpec(name, lower=-20.0, upper=20.0),
            )
        owner.configure_chart(
            "chart",
            RelationChart.empty(
                chart_id="relation",
                scope=("input", "output"),
                ridge=0.05,
                observation_norm_bound=20.0,
                prior_mass=1e-4,
            ),
        )
        for index, value in enumerate((-2.0, -1.0, 1.0, 2.0)):
            values = {"input": value, "output": 2.0 * value}
            owner.admit_observation(
                operation_id=f"observation:{index}",
                source=SourceInput(
                    source_id=f"measurement:{index}",
                    content=canonical_json_bytes(values),
                    media_type="application/json",
                    codec="utf-8",
                    observed_timestamp=str(index),
                    scope="test",
                    claim_category="controlled-measurement",
                    fidelity="exact-record",
                ),
                values=values,
                context={},
                target_chart_ids=("relation",),
            )

        condense_request = {
            **owner._transceiver_request(
                transceiver_id="temporal",
                chart_ids=("relation",),
                input_ids=("input",),
                output_ids=("output",),
                context={},
            ),
            "expected_state_sha256": None,
        }
        successor, receipt = owner.atlas.condense_transceiver(
            owner.state,
            transceiver_id="temporal",
            chart_ids=("relation",),
            input_ids=("input",),
            output_ids=("output",),
            context={},
        )
        corrupt_condense = dict(receipt)
        corrupt_condense["transceiver_id"] = "forged"
        owner._publish(
            operation_id="condense:corrupt-receipt",
            successor=successor,
            event_id=None,
            transition={
                "kind": "condense-transceiver",
                "request": condense_request,
                "request_sha256": sha256_value(condense_request),
                "result": {"receipt": corrupt_condense},
            },
        )
        committed = owner.state.state_sha256
        with pytest.raises(FieldIntelligenceError) as rejected_condense:
            owner.condense_transceiver(
                "condense:corrupt-receipt",
                transceiver_id="temporal",
                chart_ids=("relation",),
                input_ids=("input",),
                output_ids=("output",),
                context={},
            )
        assert rejected_condense.value.code == "CHECKPOINT_CORRUPT"
        assert owner.state.state_sha256 == committed

        advance_request = {
            "stimuli": {"temporal": {"input": 0.3}},
            "context": {},
            "ticks": 2,
            "connections": [],
            "force_full": False,
            "expected_state_sha256": None,
        }
        successor, receipt = owner.atlas.advance_transceivers(
            owner.state,
            stimuli=advance_request["stimuli"],
            context={},
            ticks=2,
        )
        corrupt_advance = dict(receipt)
        steps = [dict(step) for step in receipt["steps"]]
        first_step = dict(steps[0])
        values = dict(first_step["values"])
        values["output"] += 1.0
        first_step["values"] = values
        steps[0] = first_step
        corrupt_advance["steps"] = steps
        owner._publish(
            operation_id="advance:corrupt-receipt",
            successor=successor,
            event_id=None,
            transition={
                "kind": "advance-transceivers",
                "request": advance_request,
                "request_sha256": sha256_value(advance_request),
                "result": {"receipt": corrupt_advance},
            },
        )
        committed = owner.state.state_sha256
        with pytest.raises(FieldIntelligenceError) as rejected_advance:
            owner.advance_transceivers(
                "advance:corrupt-receipt",
                stimuli={"temporal": {"input": 0.3}},
                context={},
                ticks=2,
            )
        assert rejected_advance.value.code == "CHECKPOINT_CORRUPT"
        assert owner.state.state_sha256 == committed

        reset_request = {
            "transceiver_id": "temporal",
            "expected_state_sha256": None,
        }
        successor, receipt = owner.atlas.reset_transceiver(
            owner.state,
            transceiver_id="temporal",
        )
        corrupt_reset = dict(receipt)
        corrupt_reset["transceiver_id"] = "forged"
        owner._publish(
            operation_id="reset:corrupt-receipt",
            successor=successor,
            event_id=None,
            transition={
                "kind": "reset-transceiver",
                "request": reset_request,
                "request_sha256": sha256_value(reset_request),
                "result": {"receipt": corrupt_reset},
            },
        )
        committed = owner.state.state_sha256
        with pytest.raises(FieldIntelligenceError) as rejected_reset:
            owner.reset_transceiver(
                "reset:corrupt-receipt",
                transceiver_id="temporal",
            )
        assert rejected_reset.value.code == "CHECKPOINT_CORRUPT"
        assert owner.state.state_sha256 == committed
