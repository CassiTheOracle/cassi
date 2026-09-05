from __future__ import annotations

"""Run one sustained, field-only cognition and agency episode."""

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

from cassi_field_atlas import (
    FieldIntelligenceError,
    FieldProgram,
    PrimitiveStep,
    RelationChart,
    VariableSpec,
    canonical_json_bytes,
    sha256_value,
)
from cassi_field_cognition import ActionReadout, InquiryOperation, Survivor
from cassi_field_owner import (
    AuthorityGrant,
    DeterministicWorldAdapter,
    FieldIntelligenceOwner,
    SourceInput,
    WorldAcknowledgment,
)


def _source(
    source_id: str,
    payload: Mapping[str, Any] | str,
    *,
    sequence: int,
    labels: Sequence[str] = ("scenario",),
) -> SourceInput:
    if isinstance(payload, str):
        content = payload.encode("utf-8")
        media_type = "text/plain"
    else:
        content = canonical_json_bytes(dict(payload))
        media_type = "application/json"
    return SourceInput(
        source_id=source_id,
        content=content,
        media_type=media_type,
        codec="utf-8",
        observed_timestamp=f"logical:{sequence:06d}",
        scope="scenario",
        claim_category="controlled-observation",
        fidelity="exact-record",
        labels=tuple(labels),
    )


def _values(source: float, destination: float) -> Mapping[str, float]:
    displacement = destination - source
    return {
        "bias": 1.0,
        "destination": destination,
        "displacement": displacement,
        "left_score": -displacement,
        "right_score": displacement,
        "source": source,
    }


def _configure(owner: FieldIntelligenceOwner) -> None:
    variables = (
        VariableSpec("bias", kind="constant", constant=1.0, lower=1.0, upper=1.0),
        VariableSpec("source", unit="m", lower=-20.0, upper=20.0),
        VariableSpec("destination", unit="m", lower=-20.0, upper=20.0),
        VariableSpec("displacement", unit="m", lower=-40.0, upper=40.0),
        VariableSpec("left_score", lower=-40.0, upper=40.0),
        VariableSpec("right_score", lower=-40.0, upper=40.0),
    )
    for index, variable in enumerate(variables):
        owner.configure_variable(f"configure:variable:{index}", variable)
    owner.configure_chart(
        "configure:chart:geometry",
        RelationChart.empty(
            chart_id="geometry.relative-position",
            scope=("bias", "source", "destination", "displacement"),
            ridge=1e-5,
            observation_norm_bound=64.0,
            prior_mass=1e-3,
        ),
    )
    owner.configure_chart(
        "configure:chart:action",
        RelationChart.empty(
            chart_id="policy.direction",
            scope=("bias", "displacement", "left_score", "right_score"),
            ridge=1e-5,
            observation_norm_bound=96.0,
            prior_mass=1e-3,
        ),
    )
    language_program = FieldProgram(
        program_id="language.relocation.roles",
        version=1,
        roles=("destination", "source"),
        steps=(
            PrimitiveStep("identity", "destination_value", ("destination",)),
            PrimitiveStep("identity", "source_value", ("source",)),
        ),
        outputs=("source_value", "destination_value"),
        prefix_code_bits=8,
        status="promoted",
    )
    owner.configure_program("configure:program:language", language_program)


def _admit_pair(
    owner: FieldIntelligenceOwner,
    *,
    operation_id: str,
    source_position: float,
    destination_position: float,
    sequence: int,
    text: str | None = None,
) -> Mapping[str, Any]:
    payload: Mapping[str, Any] | str
    payload = (
        text
        if text is not None
        else {
            "destination": destination_position,
            "source": source_position,
        }
    )
    return owner.admit_observation(
        operation_id=operation_id,
        source=_source(f"episode:{operation_id}", payload, sequence=sequence),
        values=_values(source_position, destination_position),
        context={"domain": "line", "quality": "controlled"},
    )


def run_scenario(data_home: Path, *, horizon_episodes: int = 24) -> Mapping[str, Any]:
    owner = FieldIntelligenceOwner(data_home)
    _configure(owner)

    baseline_pairs = (
        (-4.0, -1.0),
        (-3.0, 2.0),
        (-2.0, -5.0),
        (-1.0, 4.0),
        (0.0, 3.0),
        (1.0, -3.0),
        (2.0, 5.0),
        (3.0, 0.0),
    )
    baseline_events: list[str] = []
    baseline_revisions: list[str] = []
    sequence = 0
    for index, (source_position, destination_position) in enumerate(baseline_pairs):
        sequence += 1
        admitted = _admit_pair(
            owner,
            operation_id=f"learn:baseline:{index}",
            source_position=source_position,
            destination_position=destination_position,
            sequence=sequence,
        )
        baseline_events.append(admitted["event"]["event_id"])
        baseline_revisions.append(admitted["source"]["revision_id"])

    candidates = owner.propose_relational_structure(
        operation_id="structure:propose:relative-position",
        problem_id="relative-position",
        input_roles=("source", "destination"),
        output_role="displacement",
        support_event_ids=baseline_events[:2],
        max_candidates=9,
    )["candidate_ids"]

    future_pairs = ((1.0, 4.0), (2.0, 6.0), (-2.0, 3.0))
    for episode_index, (source_position, destination_position) in enumerate(future_pairs):
        frozen: dict[str, str] = {}
        for candidate_index, candidate_id in enumerate(candidates):
            begun = owner.begin_program_assessment(
                operation_id=f"structure:begin:{episode_index}:{candidate_index}",
                program_id=candidate_id,
                bindings={
                    "destination": destination_position,
                    "source": source_position,
                },
            )
            frozen[candidate_id] = begun["prediction"]["prediction_id"]
        sequence += 1
        admitted = _admit_pair(
            owner,
            operation_id=f"learn:future:{episode_index}",
            source_position=source_position,
            destination_position=destination_position,
            sequence=sequence,
        )
        for candidate_index, candidate_id in enumerate(candidates):
            owner.resolve_program_assessment(
                operation_id=f"structure:resolve:{episode_index}:{candidate_index}",
                program_id=candidate_id,
                prediction_id=frozen[candidate_id],
                outcome={"displacement": destination_position - source_position},
                event_id=admitted["event"]["event_id"],
                loss_scale=10.0,
            )
    promoted = owner.promote_program(
        operation_id="structure:promote:relative-position",
        candidate_ids=candidates,
        minimum_assessments=3,
        maximum_average_loss=1e-12,
        bit_penalty=1e-6,
    )["program"]

    language_examples: list[Mapping[str, Any]] = []
    for index, (source_position, destination_position) in enumerate(((1.0, 5.0), (2.0, 7.0))):
        sequence += 1
        text = f"move from {int(source_position)} to {int(destination_position)}."
        admitted = _admit_pair(
            owner,
            operation_id=f"language:example:{index}",
            source_position=source_position,
            destination_position=destination_position,
            sequence=sequence,
            text=text,
        )
        language_examples.append(
            {
                "event_id": admitted["event"]["event_id"],
                "roles": {
                    "destination": str(int(destination_position)),
                    "source": str(int(source_position)),
                },
                "text": text,
            }
        )
    owner.propose_language_construction(
        operation_id="language:propose:relocation",
        construction_id="construction.relocation",
        examples=language_examples,
        semantic_program_id="language.relocation.roles",
    )
    sequence += 1
    assessment_text = "move from 3 to 9."
    assessment_episode = _admit_pair(
        owner,
        operation_id="language:assessment:episode",
        source_position=3.0,
        destination_position=9.0,
        sequence=sequence,
        text=assessment_text,
    )
    owner.assess_language_construction(
        operation_id="language:assessment:resolve",
        construction_id="construction.relocation",
        text=assessment_text,
        expected_roles={"destination": "9", "source": "3"},
        event_id=assessment_episode["event"]["event_id"],
    )
    owner.promote_language_construction(
        operation_id="language:promote:relocation",
        construction_id="construction.relocation",
    )
    interpreted = owner.interpret(text="move from 8 to 13.")
    expressed = owner.express(
        semantic_program_id="language.relocation.roles",
        bindings={"destination": "13", "source": "8"},
    )

    for index in range(horizon_episodes):
        source_position = float((index % 9) - 4)
        displacement = float(((index * 5) % 11) - 5)
        destination_position = source_position + displacement
        sequence += 1
        _admit_pair(
            owner,
            operation_id=f"learn:horizon:{index}",
            source_position=source_position,
            destination_position=destination_position,
            sequence=sequence,
        )

    query_before = owner.query(
        observed={"destination": 6.0, "source": 2.0},
        requested=("displacement", "left_score", "right_score"),
        context={"domain": "line"},
        method="direct",
    )
    if query_before["status"] != "supported":
        raise RuntimeError(f"field query did not settle: {query_before['status']}")

    readout = ActionReadout(
        readout_id="direction-choice",
        version=1,
        labels=("left", "right"),
        coefficients=(
            {"left_score": 1.0},
            {"right_score": 1.0},
        ),
        observed_error_radius=0.01,
    )
    decision = owner.action_decision(
        observed={"destination": 6.0, "source": 2.0},
        readout=readout,
        context={"domain": "line"},
        authority_current=True,
    )
    if decision.committed_action != "right":
        raise RuntimeError("learned field did not certify the rightward action")

    counterfactual = owner.counterfactual_without_chart(
        chart_id="geometry.relative-position",
        observed={"destination": 6.0, "source": 2.0},
        requested=("displacement", "left_score", "right_score"),
        context={"domain": "line"},
    )
    owner.derive_exact_reduction(
        operation_id="macro:derive:direction",
        macro_id="macro.direction",
        boundary=("bias", "source", "destination", "left_score", "right_score"),
        interior=("displacement",),
        context={"domain": "line"},
    )

    inquiry = owner.choose_inquiry(
        (
            Survivor(
                "mode:left",
                ("left",),
                {"sense-displacement": ((-10.0, -0.01),)},
            ),
            Survivor(
                "mode:right",
                ("right",),
                {"sense-displacement": ((0.01, 10.0),)},
            ),
        ),
        (
            InquiryOperation(
                "sense-displacement", cost=1.0, risk=0.0, authorized=True, feasible=True
            ),
        ),
    )

    proposal = owner.propose_effect(
        operation_id="world:move:001",
        observed={"destination": 6.0, "source": 2.0},
        readout=readout,
        target="controlled-cart",
        scope="scenario",
        payload={"steps": 1},
        context={"domain": "line"},
        goal_id="goal:reach-destination",
    )
    if proposal["status"] != "proposed":
        raise RuntimeError("stable field action was not proposed")

    def transition(
        action: str, target: str, payload: Mapping[str, Any]
    ) -> WorldAcknowledgment:
        content = canonical_json_bytes(
            {"action": action, "payload": dict(payload), "target": target}
        )
        return WorldAcknowledgment(
            acknowledgment_id="controlled-world:ack:001",
            operation_id="world:move:001",
            status="succeeded",
            observed_values={"destination": 6.0, "displacement": 4.0, "source": 2.0},
            context={"domain": "line", "world": "controlled"},
            source_content=content,
        )

    adapter = DeterministicWorldAdapter(transition)
    action_grant = AuthorityGrant(
        grant_id="grant:effect:001",
        issuer="scenario-host",
        generation=owner.authority_generation,
        operation="effect",
        target="controlled-cart",
        scope="scenario",
    )
    dispatched = owner.dispatch_effect(
        prediction_id=proposal["prediction"]["prediction_id"],
        grant=action_grant,
        adapter=adapter,
    )
    if adapter.execute_count != 1 or dispatched["status"] != "acknowledged":
        raise RuntimeError("world effect lifecycle did not close exactly once")

    decision_after = owner.action_decision(
        observed={"destination": 6.0, "source": 2.0},
        readout=readout,
        context={"domain": "line"},
        authority_current=True,
    )
    plan = owner.create_plan(
        operation_id="plan:goal:001",
        goal_id="goal:reach-destination",
        goal={"destination": 6.0},
        assumptions={"source": 2.0},
        action_decision=decision_after,
        inquiry=inquiry,
        future_macros=("macro.direction",),
    )
    explanation = owner.explain_query(
        observed={"destination": 6.0, "source": 2.0},
        requested=("displacement", "left_score", "right_score"),
        context={"domain": "line"},
        allowed_labels=frozenset({"scenario"}),
    )
    owner.record_computation(
        operation_id="computation:query:001",
        operation="condition-and-certify",
        inputs={"charts": 2, "variables": 6},
        outcome="supported",
        elapsed_ns=1000,
        work_units=6,
        residual_before=1.0,
        residual_after=query_before["branches"][0]["residual_norm"],
    )

    recalled = owner.exact_recall(
        revision_id=baseline_revisions[0],
        allowed_labels=frozenset({"scenario"}),
    )
    before_restart = owner.state.encode()
    manifest_before_forget = owner.checkpoints.current_manifest_sha256
    owner.close()
    restarted = FieldIntelligenceOwner(data_home)
    exact_restart = restarted.state.encode() == before_restart
    replay = restarted.dispatch_effect(
        prediction_id=proposal["prediction"]["prediction_id"],
        grant=AuthorityGrant(
            grant_id="grant:effect:replay",
            issuer="scenario-host",
            generation=restarted.authority_generation,
            operation="effect",
            target="controlled-cart",
            scope="scenario",
        ),
        adapter=adapter,
    )
    if adapter.execute_count != 1 or replay["status"] != "already-acknowledged":
        raise RuntimeError("recovery attempted to repeat an acknowledged effect")

    preview = restarted.preview_forget((baseline_revisions[0],))
    forget_grant = AuthorityGrant(
        grant_id="grant:forget:001",
        issuer="scenario-host",
        generation=restarted.authority_generation,
        operation="forget",
        target=sha256_value(sorted((baseline_revisions[0],))),
        scope="scenario",
    )
    forgotten = restarted.forget(
        operation_id="forget:baseline:000",
        preview_id=preview["preview_id"],
        revision_ids=(baseline_revisions[0],),
        grant=forget_grant,
        scope="scenario",
    )
    rollback_rejected = False
    try:
        restarted.checkpoints.load_version(manifest_before_forget)
    except FieldIntelligenceError as exc:
        rollback_rejected = exc.code == "STALE_REVOCATION"
    if not rollback_rejected:
        raise RuntimeError("revocation fence accepted an older learned state")

    query_after_forget = restarted.query(
        observed={"destination": 6.0, "source": 2.0},
        requested=("displacement", "left_score", "right_score"),
        context={"domain": "line"},
    )
    maximum_field_value = max(
        float(torch.max(torch.abs(chart.numeric_field)))
        for chart in restarted.state.charts
    )
    inspection = restarted.inspect()
    result = {
        "action": decision.committed_action,
        "action_margin": min(decision.certificates[0].combined_worst_margins),
        "adaptive_counterfactual_changed": (
            counterfactual["control"]["status"]
            != counterfactual["counterfactual"]["status"]
            or counterfactual["control"]["branches"]
            != counterfactual["counterfactual"]["branches"]
        ),
        "atlas_generation": inspection["field_generation"],
        "bounded_field_max_abs": maximum_field_value,
        "exact_restart": exact_restart,
        "exact_source_sha256": recalled["content_sha256"],
        "explanation_branch_count": len(explanation["branches"]),
        "forgotten": forgotten["adaptive_forgetting"],
        "inquiry_status": inquiry.status,
        "interpretation_status": interpreted["status"],
        "learned_program": promoted["program_id"],
        "memory_unchanged_during_query": query_before["memory_unchanged"],
        "one_world_execution": adapter.execute_count == 1,
        "plan_status": plan["plan"]["status"],
        "productive_expression": expressed["text"],
        "query_after_forget": query_after_forget["status"],
        "query_status": query_before["status"],
        "revocation_rollback_rejected": rollback_rejected,
        "source_event_count": restarted.evidence.event_count,
        "state_sha256": restarted.state.state_sha256,
        "zero_model_calls": True,
    }
    restarted.close()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-home", type=Path)
    parser.add_argument("--horizon-episodes", type=int, default=24)
    args = parser.parse_args()
    if args.data_home is None:
        with tempfile.TemporaryDirectory(prefix="cassifi-field-scenario-") as directory:
            result = run_scenario(
                Path(directory), horizon_episodes=args.horizon_episodes
            )
    else:
        result = run_scenario(
            args.data_home, horizon_episodes=args.horizon_episodes
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
