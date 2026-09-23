from __future__ import annotations

import copy

import pytest

from cassi_autonomous_physics_residency import (
    AutonomousPhysicsResidency,
    AutonomousPhysicsResidencyError,
    EXPERIMENT_CONSTRUCTOR_ID,
    EXPERIMENT_LANGUAGE_GENERATION_1_ID,
    EXPERIMENT_LANGUAGE_GENERATION_2_ID,
    EXPERIMENT_LANGUAGE_GENERATION_3_ID,
    DISTRIBUTED_PHASE_EXPERIMENT_ID,
    MECHANISM_EXPERIMENT_ID,
    PHASE_CURRENT_TOPOLOGY_EXPERIMENT_ID,
    RESEARCH_PROGRAM_ID,
    RESEARCH_STAGE_GENERATION_3_ID,
    build_autonomous_physics_curriculum,
    build_autonomous_physics_manifest,
    build_experiment_primitive_grammar,
)
from cassi_field_atlas import FieldIntelligenceError, canonical_json_bytes, sha256_value


def test_periodic_topology_separates_compression_and_rotation() -> None:
    from cassi_field_cognition import _phase_topology_pair_metrics

    wave = (0.0, 1.0, 0.0, -1.0)
    control = {
        f"h1_phase_topology_{component}_b{index:02d}": 0.0
        for component in ("q", "jx", "jy", "jz")
        for index in range(64)
    }
    for axis, component in enumerate(("jx", "jy", "jz")):
        trial = dict(control)
        for x in range(4):
            for y in range(4):
                for z in range(4):
                    index = (x * 4 + y) * 4 + z
                    trial[f"h1_phase_topology_{component}_b{index:02d}"] = (
                        wave[(x, y, z)[axis]]
                    )
        sample = _phase_topology_pair_metrics(
            trial, control, [1], 0.0
        )["samples"][0]
        assert sample["divergence_l1"] == 32.0
        assert sample["divergence_sum"] == 0.0
        assert sample["divergence_min"] == -1.0
        assert sample["divergence_max"] == 1.0
        assert sample["curl_l1"] == 0.0

    rotation = dict(control)
    for x in range(4):
        for y in range(4):
            for z in range(4):
                index = (x * 4 + y) * 4 + z
                rotation[f"h1_phase_topology_jx_b{index:02d}"] = -wave[y]
                rotation[f"h1_phase_topology_jy_b{index:02d}"] = wave[x]
    sample = _phase_topology_pair_metrics(
        rotation, control, [1], 0.0
    )["samples"][0]
    assert sample["divergence_l1"] == 0.0
    assert sample["curl_l1"] == 48.0


def test_autonomous_physics_curriculum_is_deterministic_bounded_and_sealed() -> None:
    first = build_autonomous_physics_curriculum()
    second = build_autonomous_physics_curriculum()
    first_manifest = build_autonomous_physics_manifest(first)
    second_manifest = build_autonomous_physics_manifest(second)

    assert canonical_json_bytes(first_manifest) == canonical_json_bytes(second_manifest)
    assert first_manifest["sealed_sha256"] == sha256_value(first_manifest["sealed"])
    assert first_manifest["learning_boundary"] == {
        "adaptive_state": "QiFieldState.field",
        "candidate_families_supplied": False,
        "external_model": False,
        "field_composes_multi_experiment_research_programs": True,
        "field_originates_bounded_authority_requests": True,
        "field_designs_matched_mechanism_controls": True,
        "field_resolves_research_mechanism_from_raw_observations": True,
        "field_continues_into_distributed_flow_worldlines": True,
        "field_continues_into_3d_phase_current_topology": True,
        "field_originates_experiment_language_candidates": True,
        "field_revises_experiment_constructor": True,
        "field_originates_observables_and_distinctions": True,
        "field_originates_typed_representation_candidates": True,
        "field_revises_same_representation_identity": True,
        "owner_supplies_only_safe_experiment_primitives": True,
        "owner_grants_no_implicit_experiment_authority": True,
        "resident_profile": {
            "default_value_words": 4_096,
            "mode_count": 1_572_864,
        },
        "resident_capacity_bytes": {
            "state": 256 * 1024 * 1024,
            "workspace": 128 * 1024 * 1024,
        },
        "sidecar_learned_state": False,
    }
    assert "candidate_families" not in first_manifest
    assert (
        first_manifest["sealed"]["experiment_primitive_grammar"]
        == build_experiment_primitive_grammar()
    )
    assert first_manifest["engine"]["maximum_horizon"] == 128

    identities = [world.world_id for world in first.all_worlds]
    assert len(identities) == len(set(identities)) == 36
    assert len(first.composition_training) == 4
    assert len(first.composition_holdout) == 2
    assert len(first.composition_transfer) == 2
    assert len(first.collision_training) == 4
    assert len(first.collision_holdout) == 2
    assert len(first.collision_transfer) == 2
    assert len(first.delayed_training) == 4
    assert len(first.delayed_holdout) == 2
    assert len(first.delayed_transfer) == 2
    assert len(first.clamp_training) == 4
    assert len(first.clamp_holdout) == 2
    assert len(first.clamp_transfer) == 2
    assert all(
        world.horizons == tuple(sorted(set(world.horizons)))
        and world.horizons[-1] <= 128
        for world in first.all_worlds
    )

    mutated = copy.deepcopy(first_manifest["sealed"])
    mutated["world_groups"]["composition_transfer"][0]["segments"][1][
        "deposits"
    ][0]["cy"] += 0.25
    assert sha256_value(mutated) != first_manifest["sealed_sha256"]


def test_resident_originates_and_revises_compositional_representation(tmp_path) -> None:
    campaign = AutonomousPhysicsResidency(tmp_path / "run", run_id="representation-test")
    resident = campaign._open_resident()
    try:
        training = [
            {
                "example_id": "train-positive-a",
                "features": {"first_charge": 4.0, "second_charge": 2.0},
                "outcome": "positive",
            },
            {
                "example_id": "train-positive-b",
                "features": {"first_charge": 2.0, "second_charge": 4.0},
                "outcome": "positive",
            },
            {
                "example_id": "train-negative-a",
                "features": {"first_charge": -4.0, "second_charge": -2.0},
                "outcome": "negative",
            },
            {
                "example_id": "train-negative-b",
                "features": {"first_charge": -2.0, "second_charge": -4.0},
                "outcome": "negative",
            },
        ]
        holdout = [
            {
                "example_id": "holdout-positive",
                "features": {"first_charge": 1.0, "second_charge": 5.0},
                "outcome": "positive",
            },
            {
                "example_id": "holdout-negative",
                "features": {"first_charge": -1.0, "second_charge": -5.0},
                "outcome": "negative",
            },
        ]
        first = campaign._learn_representation(
            resident,
            operation_name="test-composition-v1",
            representation_id="test:composition",
            target="pulse-sign",
            training=training,
            holdout=holdout,
        )
        assert first["selected_candidate"].startswith(("auto:sum:", "auto:scale-sum:"))
        assert first["representation"]["content_version"] == 1

        transfer = campaign._query_representation(
            resident,
            operation_name="test-composition-transfer",
            representation_id="test:composition",
            features={"first_charge": 3.0, "second_charge": 3.0},
        )
        assert transfer["answer"] == "positive"

        revised = campaign._learn_representation(
            resident,
            operation_name="test-composition-v2",
            representation_id="test:composition",
            target="pulse-sign",
            training=[
                *training,
                {
                    "example_id": "train-positive-c",
                    "features": {"first_charge": 5.5, "second_charge": 0.5},
                    "outcome": "positive",
                },
            ],
            holdout=holdout,
        )
        assert revised["representation"]["content_version"] == 2
        assert revised["selected_candidate"].startswith("auto:")
    finally:
        resident.close()


def test_field_revises_constructor_and_originates_novel_second_generation(
    tmp_path,
) -> None:
    campaign = AutonomousPhysicsResidency(
        tmp_path / "run",
        run_id="recursive-experiment-language-test",
    )
    resident = campaign._open_resident()
    proposals: dict[str, dict] = {}
    try:
        campaign._learn_representation(
            resident,
            operation_name="collision-language-support",
            representation_id="physics:spatiotemporal-dominance",
            target="spatiotemporal-dominance",
            training=[
                {
                    "example_id": "resident-a",
                    "features": {
                        "delay_steps": 64.0,
                        "incoming_peak_q": 8.0,
                        "left_strength": 8.0,
                        "resident_peak_q": 24.0,
                        "right_strength": 4.0,
                    },
                    "outcome": "left",
                },
                {
                    "example_id": "incoming-a",
                    "features": {
                        "delay_steps": 32.0,
                        "incoming_peak_q": 24.0,
                        "left_strength": 4.0,
                        "resident_peak_q": 8.0,
                        "right_strength": 8.0,
                    },
                    "outcome": "right",
                },
                {
                    "example_id": "resident-b",
                    "features": {
                        "delay_steps": 96.0,
                        "incoming_peak_q": 12.0,
                        "left_strength": 12.0,
                        "resident_peak_q": 30.0,
                        "right_strength": 5.0,
                    },
                    "outcome": "left",
                },
                {
                    "example_id": "incoming-b",
                    "features": {
                        "delay_steps": 16.0,
                        "incoming_peak_q": 30.0,
                        "left_strength": 5.0,
                        "resident_peak_q": 12.0,
                        "right_strength": 12.0,
                    },
                    "outcome": "right",
                },
            ],
            holdout=[
                {
                    "example_id": "holdout-left",
                    "features": {
                        "delay_steps": 48.0,
                        "incoming_peak_q": 10.0,
                        "left_strength": 7.0,
                        "resident_peak_q": 20.0,
                        "right_strength": 5.0,
                    },
                    "outcome": "left",
                },
                {
                    "example_id": "holdout-right",
                    "features": {
                        "delay_steps": 48.0,
                        "incoming_peak_q": 20.0,
                        "left_strength": 5.0,
                        "resident_peak_q": 10.0,
                        "right_strength": 7.0,
                    },
                    "outcome": "right",
                },
            ],
        )

        def synthesize(
            *,
            language_id: str,
            generation: int,
            parent_language_id: str | None = None,
            research_program_id: str | None = None,
            research_stage_id: str | None = None,
        ) -> dict:
            request = {
                "operation": "synthesize-experiment-language",
                "operation_id": (
                    f"recursive-experiment-language-test:synthesize:{generation}"
                ),
                "constructor_id": EXPERIMENT_CONSTRUCTOR_ID,
                "grammar": campaign.experiment_grammar,
                "language_id": language_id,
                "representation_id": "physics:spatiotemporal-dominance",
            }
            if parent_language_id is not None:
                request["parent_language_id"] = parent_language_id
            if research_program_id is not None:
                request["research_program_id"] = research_program_id
            if research_stage_id is not None:
                request["research_stage_id"] = research_stage_id
            return resident.semantic(request)

        source_x = {
            row["source_id"]: row["x"]
            for row in campaign.experiment_grammar["sources"]
        }

        def observations(world: dict, path: list[str]) -> dict:
            values = {}
            peaks = (12.0, 10.0, 9.0)
            for index, row in enumerate(world["observations"]):
                horizon = row["horizon"]
                for field in row["fields"]:
                    if field == "top_x":
                        values[f"h{horizon}_{field}"] = source_x[path[index]]
                    elif field == "top_q":
                        values[f"h{horizon}_{field}"] = peaks[index]
                    else:
                        raise AssertionError(field)
            return values

        def assess(
            *,
            language_id: str,
            proposal: dict,
            safety: dict,
            variant: str,
        ) -> dict:
            world = proposal[f"{variant}_world"]
            path = world["expected"]["zone_path"]
            observed = observations(world, path)
            root = campaign._archive(
                resident,
                source_id=f"synthetic-{language_id}-{variant}",
                content=canonical_json_bytes({"observations": observed}),
                category="synthetic-generated-experiment",
                context={"purpose": "focused recursive constructor test"},
            )
            return resident.semantic(
                {
                    "operation": "assess-experiment-language",
                    "operation_id": (
                        f"recursive-experiment-language-test:"
                        f"assess:{language_id}:{variant}"
                    ),
                    "language_id": language_id,
                    "observations": observed,
                    "safety_receipt": safety,
                    "source_revision_id": root,
                    "variant": variant,
                }
            )

        first = synthesize(
            language_id=EXPERIMENT_LANGUAGE_GENERATION_1_ID,
            generation=1,
        )
        assert first["status"] == "supported"
        assert first["candidate_families_supplied"] is False
        assert first["constructor"]["content_version"] == 1
        first_proposal = first["proposal"]
        proposals["generation_1"] = first_proposal
        assert first_proposal["candidate_origin"] == "field-generated"
        assert first_proposal["construction"] == {
            **first_proposal["construction"],
            "constructor_id": EXPERIMENT_CONSTRUCTOR_ID,
            "constructor_version": 1,
            "generation": 1,
            "parent_language_id": None,
            "research_program_id": None,
            "research_stage_id": None,
            "route_shape": "returning",
            "step_profile": "settle-then-react",
            "strength_profile": "steady",
            "topology": "restoration",
        }
        assert first_proposal["trial_world"]["expected"]["zone_path"] == [
            "left",
            "right",
            "left",
        ]
        assert len(first["candidates"]) == 8
        assert len(
            {
                row["construction"]["schedule_fingerprint"]
                for row in first["candidates"]
            }
        ) == len(first["candidates"])

        first_safety = campaign._authorize_generated_experiment(
            first_proposal
        )
        assert first_safety["authorized"] is True
        assert all(first_safety["checks"].values())
        mutated = copy.deepcopy(first_proposal)
        mutated["trial_world"]["segments"][0]["pulses"][0][
            "strength"
        ] = 9.0
        denied = campaign._authorize_generated_experiment(mutated)
        assert denied["authorized"] is False
        with pytest.raises(
            FieldIntelligenceError,
            match="owner safety boundary",
        ):
            observed = observations(
                first_proposal["trial_world"],
                first_proposal["trial_world"]["expected"]["zone_path"],
            )
            root = campaign._archive(
                resident,
                source_id="synthetic-denied-trial",
                content=canonical_json_bytes({"observations": observed}),
                category="synthetic-generated-experiment",
                context={"purpose": "unsafe mutation rejection"},
            )
            resident.semantic(
                {
                    "operation": "assess-experiment-language",
                    "operation_id": (
                        "recursive-experiment-language-test:"
                        "assess-denied-trial"
                    ),
                    "language_id": EXPERIMENT_LANGUAGE_GENERATION_1_ID,
                    "observations": observed,
                    "safety_receipt": denied,
                    "source_revision_id": root,
                    "variant": "trial",
                }
            )

        assert assess(
            language_id=EXPERIMENT_LANGUAGE_GENERATION_1_ID,
            proposal=first_proposal,
            safety=first_safety,
            variant="trial",
        )["earned"] is True
        assert assess(
            language_id=EXPERIMENT_LANGUAGE_GENERATION_1_ID,
            proposal=first_proposal,
            safety=first_safety,
            variant="transfer",
        )["correct"] is True

        revision = campaign._revise_experiment_constructor(
            resident,
            language_id=EXPERIMENT_LANGUAGE_GENERATION_1_ID,
        )
        assert revision["constructor"]["content_version"] == 2
        assert revision["generation"] == 2
        assert revision["strategy"]["preferred_topology"] == (
            "directed-traversal"
        )
        first_fingerprint = first_proposal["construction"][
            "schedule_fingerprint"
        ]
        assert revision["tested_schedule_fingerprints"] == [
            first_fingerprint
        ]

        second = synthesize(
            language_id=EXPERIMENT_LANGUAGE_GENERATION_2_ID,
            generation=2,
            parent_language_id=EXPERIMENT_LANGUAGE_GENERATION_1_ID,
        )
        assert second["constructor"]["content_version"] == 2
        second_proposal = second["proposal"]
        proposals["generation_2"] = second_proposal
        assert second_proposal["construction"]["generation"] == 2
        assert second_proposal["construction"]["parent_language_id"] == (
            EXPERIMENT_LANGUAGE_GENERATION_1_ID
        )
        assert second_proposal["construction"]["topology"] == (
            "directed-traversal"
        )
        assert second_proposal["construction"]["strength_profile"] == "rising"
        assert second_proposal["trial_world"]["expected"]["zone_path"] == [
            "left",
            "center",
            "right",
        ]
        assert (
            second_proposal["construction"]["schedule_fingerprint"]
            != first_fingerprint
        )
        assert second_proposal["trial_world"]["distinction"][
            "expected_class"
        ] == "directed-spatial-traversal"

        second_safety = campaign._authorize_generated_experiment(
            second_proposal
        )
        assert second_safety["authorized"] is True
        assert assess(
            language_id=EXPERIMENT_LANGUAGE_GENERATION_2_ID,
            proposal=second_proposal,
            safety=second_safety,
            variant="trial",
        )["earned"] is True
        assert assess(
            language_id=EXPERIMENT_LANGUAGE_GENERATION_2_ID,
            proposal=second_proposal,
            safety=second_safety,
            variant="transfer",
        )["correct"] is True
        second_fingerprint = second_proposal["construction"][
            "schedule_fingerprint"
        ]
        revision_two = campaign._revise_experiment_constructor(
            resident,
            language_id=EXPERIMENT_LANGUAGE_GENERATION_2_ID,
        )
        assert revision_two["constructor"]["content_version"] == 3
        assert revision_two["generation"] == 3
        assert len(revision_two["successful_distinctions"]) == 2
        assert revision_two["strategy"]["preferred_route_shape"] == (
            "nonmonotone"
        )

        research = campaign._synthesize_research_program(resident)
        assert len(research["discovery_history"]) == 2
        assert research["uncertainty"]["uncertainty_id"] == (
            "trajectory-transport-mechanism"
        )
        assert research["next_stage"]["stage_id"] == (
            RESEARCH_STAGE_GENERATION_3_ID
        )
        assert research["next_stage"]["constraints"] == {
            "route_shape": "nonmonotone",
            "strength_profile": "rising",
            "topology": "directed-traversal",
        }
        authority_review = campaign._review_research_authority_request(
            research
        )
        assert authority_review["authorized"] is True
        assert authority_review["decision"] == "authorized-existing-primitive"
        assert authority_review["grant"] == {
            "field": "top_phase_current_x",
            "scope": "top-coherence-cell",
        }
        assert authority_review["checks"] == {
            "available_primitive": True,
            "bounded_scope": True,
            "grammar_unchanged": True,
            "no_implicit_grant": True,
            "request_shape": True,
        }
        forged_review = copy.deepcopy(authority_review)
        forged_review["authorized"] = False
        forged_review["decision"] = "deferred-unavailable"
        forged_review["grant"] = None
        with pytest.raises(
            FieldIntelligenceError,
            match="authority decision",
        ):
            campaign._record_research_authority(
                resident, forged_review
            )
        authority_assessment = campaign._record_research_authority(
            resident, authority_review
        )
        assert authority_assessment["status"] == "supported"
        assert authority_assessment["authority_state"] == "authorized"

        third = synthesize(
            language_id=EXPERIMENT_LANGUAGE_GENERATION_3_ID,
            generation=3,
            parent_language_id=EXPERIMENT_LANGUAGE_GENERATION_2_ID,
            research_program_id=RESEARCH_PROGRAM_ID,
            research_stage_id=RESEARCH_STAGE_GENERATION_3_ID,
        )
        third_proposal = third["proposal"]
        proposals["generation_3"] = third_proposal
        third_construction = third_proposal["construction"]
        assert third_construction["generation"] == 3
        assert third_construction["parent_language_id"] == (
            EXPERIMENT_LANGUAGE_GENERATION_2_ID
        )
        assert third_construction["research_program_id"] == (
            RESEARCH_PROGRAM_ID
        )
        assert third_construction["research_stage_id"] == (
            RESEARCH_STAGE_GENERATION_3_ID
        )
        assert third_construction["route_shape"] == "nonmonotone"
        assert third_construction["schedule_fingerprint"] not in {
            first_fingerprint,
            second_fingerprint,
        }
        assert len(set(third_proposal["trial_world"]["expected"]["zone_path"])) == 3
        third_safety = campaign._authorize_generated_experiment(
            third_proposal
        )
        assert third_safety["authorized"] is True
        assert assess(
            language_id=EXPERIMENT_LANGUAGE_GENERATION_3_ID,
            proposal=third_proposal,
            safety=third_safety,
            variant="trial",
        )["earned"] is True
        assert assess(
            language_id=EXPERIMENT_LANGUAGE_GENERATION_3_ID,
            proposal=third_proposal,
            safety=third_safety,
            variant="transfer",
        )["correct"] is True
        revision_three = campaign._revise_experiment_constructor(
            resident,
            language_id=EXPERIMENT_LANGUAGE_GENERATION_3_ID,
        )
        assert revision_three["constructor"]["content_version"] == 4
        assert revision_three["generation"] == 4
        assert len(revision_three["successful_distinctions"]) == 3
        advanced = campaign._advance_research_program(resident)
        assert advanced["program"]["content_version"] == 3
        assert advanced["program_state"] == "active"
        assert len(advanced["discovery_history"]) == 3
        assert advanced["frontier_stage"]["status"] == "planned-authority"

        mechanism_design = campaign._design_mechanism_experiment(resident)
        mechanism_proposal = mechanism_design["proposal"]
        assert mechanism_design["candidate_families_supplied"] is False
        assert mechanism_design["selected_candidate"].startswith(
            "auto:mechanism-experiment:"
        )
        assert mechanism_design["experiment"]["id"] == MECHANISM_EXPERIMENT_ID
        assert mechanism_proposal["selection"]["target_source_id"] == "center"
        mechanism_safety = campaign._authorize_mechanism_experiment(
            mechanism_proposal
        )
        assert mechanism_safety["authorized"] is True
        assert all(mechanism_safety["checks"].values())

        unsafe_proposal = copy.deepcopy(mechanism_proposal)
        unsafe_proposal["trial_world"]["segments"][0]["pulses"][0][
            "strength"
        ] = 13.0
        denied_mechanism = campaign._authorize_mechanism_experiment(
            unsafe_proposal
        )
        assert denied_mechanism["authorized"] is False

        target_x = mechanism_proposal["selection"]["target_source_x"]
        mechanism_observations: dict[str, dict[str, float]] = {}
        mechanism_roots: dict[str, str] = {}
        for variant in ("control", "trial", "mirror_trial"):
            world = mechanism_proposal[f"{variant}_world"]
            final_horizon = sum(
                segment["steps"] for segment in world["segments"]
            )
            values: dict[str, float] = {}
            for row in world["observations"]:
                horizon = row["horizon"]
                for field in row["fields"]:
                    if field == "top_phase_current_x":
                        value = 0.25
                        if horizon == final_horizon and variant == "trial":
                            value = 0.251
                        elif (
                            horizon == final_horizon
                            and variant == "mirror_trial"
                        ):
                            value = 0.249
                    elif field == "top_q":
                        value = 3.0
                    elif field == "top_x":
                        value = target_x
                    else:
                        raise AssertionError(field)
                    values[f"h{horizon}_{field}"] = value
            mechanism_observations[variant] = values
            mechanism_roots[variant] = campaign._archive(
                resident,
                source_id=f"synthetic-mechanism-{variant}",
                content=canonical_json_bytes({"observations": values}),
                category="synthetic-mechanism-experiment",
                context={"variant": variant},
            )
        with pytest.raises(
            FieldIntelligenceError,
            match="fixed safety boundary",
        ):
            resident.semantic(
                {
                    "operation": "assess-mechanism-experiment",
                    "operation_id": (
                        "recursive-experiment-language-test:"
                        "assess-denied-mechanism"
                    ),
                    "experiment_id": MECHANISM_EXPERIMENT_ID,
                    "observations": mechanism_observations,
                    "safety_receipt": denied_mechanism,
                    "evidence_sources": mechanism_roots,
                }
            )
        mechanism_assessment = resident.semantic(
            {
                "operation": "assess-mechanism-experiment",
                "operation_id": (
                    "recursive-experiment-language-test:"
                    "assess-mechanism"
                ),
                "experiment_id": MECHANISM_EXPERIMENT_ID,
                "observations": mechanism_observations,
                "safety_receipt": mechanism_safety,
                "evidence_sources": mechanism_roots,
            }
        )
        assert mechanism_assessment["status"] == "supported"
        assert mechanism_assessment["verdict"] == (
            "transport-coupled-at-peak"
        )
        assert mechanism_assessment["program_state"] == "resolved"
        continuation = campaign._continue_distributed_phase_flow(resident)
        assert continuation["status"] == "supported"
        assert continuation["prior_resolution"]["verdict"] == (
            "transport-coupled-at-peak"
        )
        distributed_authority = campaign._review_research_authority_request(
            continuation
        )
        assert distributed_authority["authorized"] is True
        assert distributed_authority["grant"] == {
            "field": "phase_profile_x_16",
            "scope": "sixteen-x-slabs-full-yz",
        }
        campaign._record_research_authority(
            resident,
            distributed_authority,
            operation_name="focused-distributed",
        )
        distributed_design = campaign._design_distributed_phase_flow(
            resident
        )
        distributed_proposal = distributed_design["proposal"]
        assert distributed_design["candidate_families_supplied"] is False
        assert distributed_design["experiment"]["id"] == (
            DISTRIBUTED_PHASE_EXPERIMENT_ID
        )
        distributed_safety = campaign._authorize_distributed_phase_flow(
            distributed_proposal
        )
        assert distributed_safety["authorized"] is True
        assert all(distributed_safety["checks"].values())

        distributed_observations: dict[str, dict[str, float]] = {}
        distributed_roots: dict[str, str] = {}
        for variant in ("control", "trial", "mirror_trial"):
            world = distributed_proposal[f"{variant}_world"]
            values = {}
            response_index = 0
            for row in world["observations"]:
                horizon = int(row["horizon"])
                q = [0.0] * 16
                if variant == "control":
                    q[8] = 4.0
                    top_x_value = 0.0
                    top_q_value = 4.0
                elif horizon <= 64:
                    source_bin = 3 if variant == "trial" else 12
                    q[source_bin] = 8.0
                    top_x_value = -0.55 if variant == "trial" else 0.55
                    top_q_value = 8.0
                else:
                    q[8] = 4.0
                    path = (
                        [4, 5, 6, 6]
                        if variant == "trial"
                        else [11, 10, 9, 9]
                    )
                    q[path[response_index]] = 3.0
                    response_index += 1
                    top_x_value = 0.0
                    top_q_value = 4.0
                for field in row["fields"]:
                    key = f"h{horizon}_{field}"
                    if field == "top_q":
                        values[key] = top_q_value
                    elif field == "top_x":
                        values[key] = top_x_value
                    elif field.startswith("phase_q_x"):
                        values[key] = q[int(field[-2:])]
                    elif field.startswith(("phase_jx_x", "phase_abs_jx_x")):
                        values[key] = 0.0
                    else:
                        raise AssertionError(field)
            root = campaign._archive(
                resident,
                source_id=f"synthetic-distributed-{variant}",
                content=canonical_json_bytes({"observations": values}),
                category="synthetic-distributed-phase-flow",
                context={"variant": variant},
            )
            distributed_observations[variant] = values
            distributed_roots[variant] = root
        distributed_assessment = resident.semantic(
            {
                "operation": "assess-distributed-phase-flow",
                "operation_id": (
                    "recursive-experiment-language-test:"
                    "assess-distributed-phase-flow"
                ),
                "experiment_id": DISTRIBUTED_PHASE_EXPERIMENT_ID,
                "observations": distributed_observations,
                "safety_receipt": distributed_safety,
                "evidence_sources": distributed_roots,
            }
        )
        assert distributed_assessment["status"] == "supported"
        assert distributed_assessment["verdict"] == "advective-transport"
        assert distributed_assessment["metrics"]["primary_mechanism"] == (
            "advective-transport"
        )
        assert distributed_assessment["program_state"] == "resolved"
        topology_continuation = campaign._continue_phase_current_topology(
            resident
        )
        assert topology_continuation["status"] == "supported"
        assert topology_continuation["prior_resolution"]["verdict"] == (
            "advective-transport"
        )
        topology_authority = campaign._review_research_authority_request(
            topology_continuation
        )
        assert topology_authority["authorized"] is True
        assert topology_authority["grant"] == {
            "field": "phase_winding_native_3x3",
            "scope": (
                "four-cubed-periodic-phase-current-lattice-plus-"
                "native-closed-loops"
            ),
        }
        campaign._record_research_authority(
            resident,
            topology_authority,
            operation_name="focused-topology",
        )
        topology_design = campaign._design_phase_current_topology(resident)
        topology_proposal = topology_design["proposal"]
        assert topology_design["candidate_families_supplied"] is False
        assert topology_design["experiment"]["id"] == (
            PHASE_CURRENT_TOPOLOGY_EXPERIMENT_ID
        )
        topology_safety = campaign._authorize_phase_current_topology(
            topology_proposal
        )
        assert topology_safety["authorized"] is True
        assert all(topology_safety["checks"].values())

        topology_observations: dict[str, dict[str, float]] = {}
        topology_roots: dict[str, str] = {}
        for variant in (
            "left_control",
            "left_trial",
            "right_control",
            "right_trial",
        ):
            world = topology_proposal[f"{variant}_world"]
            values = {}
            is_trial = variant.endswith("_trial")
            is_right = variant.startswith("right_")
            for row in world["observations"]:
                horizon = int(row["horizon"])
                active = is_trial and horizon > 32
                q = [0.0] * 64
                prior_x = 3 if is_right else 0
                q[(prior_x * 4 + 2) * 4 + 1] = 2.0
                if active:
                    q[(2 * 4 + 2) * 4 + 1] += 4.0
                jx = [0.0] * 64
                jy = [0.0] * 64
                jz = [0.0] * 64
                if active:
                    for bin_x in range(4):
                        for bin_y in range(4):
                            for bin_z in range(4):
                                index = (bin_x * 4 + bin_y) * 4 + bin_z
                                source_x = 3 - bin_x if is_right else bin_x
                                dx = source_x - 2
                                dy = bin_y - 2
                                left_jx = -float(dy)
                                left_jy = float(dx)
                                jx[index] = -left_jx if is_right else left_jx
                                jy[index] = left_jy
                prefix = f"h{horizon}"
                values[f"{prefix}_top_q"] = 4.0 if active else 2.0
                values[f"{prefix}_top_x"] = (
                    0.0 if active else (0.55 if is_right else -0.55)
                )
                for index in range(64):
                    values[f"{prefix}_phase_topology_q_b{index:02d}"] = q[index]
                    values[f"{prefix}_phase_topology_jx_b{index:02d}"] = jx[index]
                    values[f"{prefix}_phase_topology_jy_b{index:02d}"] = jy[index]
                    values[f"{prefix}_phase_topology_jz_b{index:02d}"] = jz[index]
                for plane in ("xy", "xz", "yz"):
                    for radius in (2, 4, 8):
                        values[
                            f"{prefix}_phase_winding_{plane}_r{radius:02d}"
                        ] = 1.0 if active and plane == "xy" else 0.0
                        values[
                            f"{prefix}_phase_winding_circ_{plane}_r{radius:02d}"
                        ] = 0.5 if active else 0.0
                        values[
                            f"{prefix}_phase_winding_current_{plane}_r{radius:02d}"
                        ] = 0.25 if active else 0.0
                        values[
                            f"{prefix}_phase_winding_qmin_{plane}_r{radius:02d}"
                        ] = 1.0
            root = campaign._archive(
                resident,
                source_id=f"synthetic-topology-{variant}",
                content=canonical_json_bytes({"observations": values}),
                category="synthetic-phase-current-topology",
                context={"variant": variant},
            )
            topology_observations[variant] = values
            topology_roots[variant] = root
        topology_assessment = resident.semantic(
            {
                "operation": "assess-phase-current-topology",
                "operation_id": (
                    "recursive-experiment-language-test:"
                    "assess-phase-current-topology"
                ),
                "experiment_id": PHASE_CURRENT_TOPOLOGY_EXPERIMENT_ID,
                "observations": topology_observations,
                "safety_receipt": topology_safety,
                "evidence_sources": topology_roots,
            }
        )
        assert topology_assessment["status"] == "supported"
        assert topology_assessment["verdict"] == "vortical-circulation"
        assert topology_assessment["metrics"]["material_current"] is True
        assert topology_assessment["metrics"]["normalized_curl"] >= 0.25
        assert topology_assessment["metrics"]["max_divergence_l1"] == 0.0
        assert topology_assessment["metrics"]["native_winding_detected"] is True
        assert topology_assessment["metrics"]["native_flow_detected"] is True
        assert topology_assessment["metrics"]["native_verdict"] == (
            "native-winding-detected"
        )
        assert topology_assessment["program_state"] == "resolved"
        program_query = campaign._query_research_program(
            resident,
            operation_name="focused-before-restart",
        )
        assert program_query["status"] == "supported"
        assert program_query["research"]["state"] == "resolved"
        assert program_query["research"]["uncertainty"]["resolution"][
            "verdict"
        ] == "vortical-circulation"
        assert program_query["research"]["prior_resolutions"][-1][
            "resolution"
        ]["verdict"] == "advective-transport"
        assert program_query["research"]["prior_resolutions"][-2][
            "resolution"
        ]["verdict"] == "transport-coupled-at-peak"
        field_sha256 = resident.inspect()["field_state_sha256"]
    finally:
        resident.close()

    reopened = campaign._open_resident()
    try:
        assert reopened.inspect()["field_state_sha256"] == field_sha256
        for generation, language_id in (
            ("generation_1", EXPERIMENT_LANGUAGE_GENERATION_1_ID),
            ("generation_2", EXPERIMENT_LANGUAGE_GENERATION_2_ID),
            ("generation_3", EXPERIMENT_LANGUAGE_GENERATION_3_ID),
        ):
            restarted = reopened.semantic(
                {
                    "operation": "invoke-experiment-language",
                    "operation_id": (
                        "recursive-experiment-language-test:"
                        f"invoke-restarted:{generation}"
                    ),
                    "language_id": language_id,
                    "variant": "transfer",
                }
            )
            assert restarted["status"] == "supported"
            assert restarted["world"] == proposals[generation][
                "transfer_world"
            ]
        restarted_program = campaign._query_research_program(
            reopened,
            operation_name="focused-after-restart",
        )
        assert restarted_program["status"] == "supported"
        assert restarted_program["research"] == program_query["research"]
    finally:
        reopened.close()

    lesion = campaign._lesion_probe()
    assert lesion["experiment_languages_available"] == {
        "generation_1": False,
        "generation_2": False,
        "generation_3": False,
    }
    assert lesion["experiment_language_statuses"] == {
        "generation_1": "support-gap",
        "generation_2": "support-gap",
        "generation_3": "support-gap",
    }
    assert lesion["research_program_available"] is False
    assert lesion["research_program_status"] == "support-gap"


def test_existing_receipt_cannot_cross_autonomous_physics_contract(tmp_path) -> None:
    campaign = AutonomousPhysicsResidency(tmp_path / "run", run_id="receipt-contract")
    wrong_receipt = {
        "schema": "cassifi.autonomous-physics-residency-receipt.v5",
        "run_id": "receipt-contract",
        "manifest_sha256": "0" * 64,
        "sealed_sha256": campaign.manifest["sealed_sha256"],
    }
    wrong_receipt["body_sha256"] = sha256_value(wrong_receipt)
    campaign.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    campaign.receipt_path.write_bytes(canonical_json_bytes(wrong_receipt))

    with pytest.raises(
        AutonomousPhysicsResidencyError,
        match="different autonomous physics contract",
    ):
        campaign.run()
