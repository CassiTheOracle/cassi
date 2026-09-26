"""Measure whether admitted outcomes continuously change resonant action choice.

Each run first acquires two safe categorical skills.  The online and control
conditions then begin with the same temporal candidate records and the same
seven-pool workspace.  Four additional successful staged-release episodes are
admitted through the ordinary owner transaction.  The online condition uses
the resulting outcome impulses; the matched control scores the exact same
post-admission candidates against the frozen pre-feedback workspace.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import random
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_resonant_field import ResonantWorkspace, score_pool_probes
from run_temporal_learning_scenario import Session

SCHEMA = "cassifi.online-resonant-learning.v1"
MEMORY = "matched-release-choice"
FAST_SKILL = "fast-release"
STAGED_SKILL = "staged-release"
SKILLS = (FAST_SKILL, STAGED_SKILL)
ACTIONS = ("short", "long", "continue")
OBSERVATIONS = ("done-fast", "stage", "done-staged", "jammed")
PATHS: Mapping[str, tuple[Mapping[str, str], ...]] = {
    FAST_SKILL: ({"action": "short", "observation": "done-fast"},),
    STAGED_SKILL: (
        {"action": "long", "observation": "stage"},
        {"action": "continue", "observation": "done-staged"},
    ),
}
GOALS: Mapping[str, tuple[str, ...]] = {
    FAST_SKILL: ("done-fast",),
    STAGED_SKILL: ("done-staged",),
}
CONTEXT = {
    "mechanism": "matched-release-choice",
    "task": "release-under-held-out-load",
    "measurement": "continuous-field-owned-outcome-learning",
}
SEEDS = (101, 202, 303)
FEEDBACK_ROUNDS = 4
MINIMUM_MARGIN = 1e-9


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def operations(seed: int) -> tuple[Mapping[str, Any], ...]:
    rows = [
        {
            "action": action,
            "authorized": True,
            "feasible": True,
            "represented_forbidden": False,
        }
        for action in ("short", "long")
    ]
    random.Random(seed).shuffle(rows)
    return tuple(rows)


def workspace_evidence(workspace: ResonantWorkspace) -> Mapping[str, Any]:
    payload = workspace.as_dict()
    payload.pop("field")
    raw = base64.b64decode(payload["field_b64"], validate=True)
    require(digest_bytes(raw) == digest_bytes(workspace.page_bytes), "workspace page encoding changed")
    return payload


def _plain_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in candidate.items()
        if key != "resonant_score"
    }


def score_control(
    candidates: Sequence[Mapping[str, Any]],
    workspace: ResonantWorkspace,
) -> Mapping[str, Any]:
    """Apply the production scorer to current candidates and a held workspace."""
    plain = [_plain_candidate(candidate) for candidate in candidates]
    scoring = score_pool_probes(
        workspace,
        {
            str(candidate["candidate_sha256"]): candidate["pool_signal"]
            for candidate in plain
        },
    )
    score_by_probe = {
        row["probe_id"]: row for row in scoring["scores"]
    }
    scored = [
        {
            **candidate,
            "resonant_score": dict(score_by_probe[candidate["candidate_sha256"]]),
        }
        for candidate in plain
    ]
    ranked = sorted(
        scored,
        key=lambda candidate: -float(candidate["resonant_score"]["compatibility"]),
    )
    margin = float(
        ranked[0]["resonant_score"]["compatibility"]
        - ranked[1]["resonant_score"]["compatibility"]
    )
    selected = None
    status = "unresolved"
    reason = "insufficient-resonant-margin"
    if margin > MINIMUM_MARGIN:
        status = "selected"
        reason = "resonant-compatibility"
        selected = {
            "action": ranked[0]["action"],
            "candidate_sha256": ranked[0]["candidate_sha256"],
            "skill_id": ranked[0]["skill_id"],
            "supporting_skill_ids": [ranked[0]["skill_id"]],
        }
    return {
        "schema": "cassifi.matched-no-outcome-wave-control.v1",
        "status": status,
        "reason": reason,
        "selected": selected,
        "selection_margin": margin,
        "candidates": scored,
        "candidate_set_sha256": digest_bytes(canonical_bytes(sorted(
            candidate["candidate_sha256"] for candidate in plain
        ))),
        "resonant_scoring": scoring,
        "resonant_workspace_state_sha256": workspace.state_sha256,
        "workspace_held_constant": True,
    }


class HeldOutRelease:
    """The fast shortcut jams; the staged route remains successful."""

    def __init__(self) -> None:
        self.staged = False
        self.completed = False

    def step(self, action: str) -> str:
        if action == "short":
            return "jammed"
        if action == "long":
            self.staged = True
            return "stage"
        if action == "continue":
            if self.staged:
                self.completed = True
                return "done-staged"
            return "jammed"
        raise ValueError(f"unknown action: {action}")


def execute_skill(
    session: Session,
    *,
    participant_id: str,
    skill_id: str,
) -> Mapping[str, Any]:
    started = time.perf_counter()
    session.mutate(
        "bind_temporal",
        memory_id=MEMORY,
        participant_id=participant_id,
        known_start=True,
    )
    world = HeldOutRelease()
    records: list[Mapping[str, Any]] = []
    for tick in range(4):
        readout = session.owner.state.temporal(MEMORY).skill_action(
            skill_id,
            participant_id=participant_id,
        )
        action = readout.get("action")
        if not isinstance(action, str):
            break
        observation = world.step(action)
        records.append({
            "tick": tick,
            "action": action,
            "observation": observation,
            "readout": dict(readout),
        })
        session.mutate(
            "advance_temporal",
            memory_id=MEMORY,
            participant_id=participant_id,
            action=action,
            observation=observation,
        )
        if world.completed or observation == "jammed":
            break
    return {
        "skill_id": skill_id,
        "completed": world.completed,
        "unsafe_observations": sum(
            row["observation"] == "jammed" for row in records
        ),
        "action_steps": len(records),
        "actions": [row["action"] for row in records],
        "observations": [row["observation"] for row in records],
        "records": records,
        "elapsed_seconds": time.perf_counter() - started,
    }


def candidate_semantics(selection: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return sorted(
        (
            {
                "skill_id": candidate["skill_id"],
                "action": candidate["action"],
                "pool_signal": candidate["pool_signal"],
                "status": candidate["status"],
            }
            for candidate in selection["candidates"]
        ),
        key=lambda row: str(row["skill_id"]),
    )


def run_seed(home: Path, seed: int) -> Mapping[str, Any]:
    started = time.perf_counter()
    session = Session(
        home,
        seed,
        "online-resonant-learning",
        memory_id=MEMORY,
        action_ids=ACTIONS,
        observation_ids=OBSERVATIONS,
        max_states=16,
        context=CONTEXT,
    )
    try:
        # Acquire both paths before registering their goals.  Skill-free
        # evidence cannot initialize or steer the resonant workspace.
        for skill_id in SKILLS:
            learned = session.learn(
                f"acquire-{skill_id}",
                PATHS[skill_id],
            )
            require(
                learned["receipt"]["resonance_coupling"]["applied"] is False,
                "skill-free acquisition changed the wave",
            )
        require(
            session.owner.state.resonant_workspace is None,
            "skill-free acquisition initialized the wave",
        )

        registrations = []
        for skill_id in SKILLS:
            registrations.append(session.mutate(
                "condense_temporal_skill",
                memory_id=MEMORY,
                skill_id=skill_id,
                goal_observations=GOALS[skill_id],
            ))
        memory = session.owner.state.temporal(MEMORY)
        require(
            memory.formed_skill_ids == SKILLS,
            "matched candidate skills were not both formed",
        )
        start_workspace = session.owner.state.resonant_workspace
        if start_workspace is None:
            raise RuntimeError("skill formation did not initialize the wave")
        start_workspace_record = workspace_evidence(start_workspace)
        allowed = operations(seed)
        initial_online = session.owner.select_temporal_action(
            MEMORY,
            skill_ids=SKILLS,
            operations=allowed,
            minimum_margin=MINIMUM_MARGIN,
        )
        initial_control = score_control(
            initial_online["candidates"],
            start_workspace,
        )
        require(
            initial_online["selected"] == initial_control["selected"],
            "online and control did not begin at the same decision",
        )
        require(
            initial_online["selected"] is not None
            and initial_online["selected"]["skill_id"] == FAST_SKILL,
            "initial field did not prefer the fast skill",
        )
        initial_semantics = candidate_semantics(initial_online)

        trajectory = []
        previous_workspace_sha256 = start_workspace.state_sha256
        for round_index in range(1, FEEDBACK_ROUNDS + 1):
            admitted = session.learn(
                f"staged-success-{round_index}",
                PATHS[STAGED_SKILL],
            )
            coupling = admitted["receipt"]["resonance_coupling"]
            require(
                coupling["formed_skills"] == []
                and coupling["withdrawn_skills"] == [],
                "feedback changed the categorical candidate set",
            )
            require(
                coupling["start_workspace_state_sha256"]
                == previous_workspace_sha256,
                "feedback did not extend the prior wave",
            )
            online = session.owner.select_temporal_action(
                MEMORY,
                skill_ids=SKILLS,
                operations=allowed,
                minimum_margin=MINIMUM_MARGIN,
            )
            control = score_control(online["candidates"], start_workspace)
            require(
                candidate_semantics(online) == initial_semantics,
                "feedback changed candidate semantics",
            )
            require(
                candidate_semantics(control) == initial_semantics,
                "control and online candidates differ",
            )
            current_workspace = session.owner.state.resonant_workspace
            if current_workspace is None:
                raise RuntimeError("online feedback lost the wave")
            current_record = workspace_evidence(current_workspace)
            require(
                coupling["end_workspace_state_sha256"]
                == current_workspace.state_sha256,
                "coupling receipt and committed workspace differ",
            )
            trajectory.append({
                "round": round_index,
                "source_revision_id": admitted["receipt"]["source_revision_id"],
                "resonance_coupling": dict(coupling),
                "online": dict(online),
                "no_outcome_wave_control": dict(control),
                "online_workspace": current_record,
            })
            previous_workspace_sha256 = current_workspace.state_sha256

        require(
            all(
                row["no_outcome_wave_control"]["selected"]["skill_id"]
                == FAST_SKILL
                for row in trajectory
            ),
            "held-wave control changed preference",
        )
        crossover_rounds = [
            row["round"]
            for row in trajectory
            if row["online"]["selected"] is not None
            and row["online"]["selected"]["skill_id"] == STAGED_SKILL
        ]
        require(bool(crossover_rounds), "online outcomes did not change preference")
        require(
            all(
                row["online"]["selected"]["skill_id"] == STAGED_SKILL
                for row in trajectory[crossover_rounds[0] - 1:]
            ),
            "online preference did not remain changed",
        )

        final_online = trajectory[-1]["online"]
        final_control = trajectory[-1]["no_outcome_wave_control"]
        online_trial = execute_skill(
            session,
            participant_id=f"online-trial-{seed}",
            skill_id=final_online["selected"]["skill_id"],
        )
        control_trial = execute_skill(
            session,
            participant_id=f"control-trial-{seed}",
            skill_id=final_control["selected"]["skill_id"],
        )
        require(online_trial["completed"] is True, "online trial did not complete")
        require(control_trial["completed"] is False, "held-wave control unexpectedly completed")
        require(control_trial["unsafe_observations"] == 1, "held-wave control did not expose the unsafe shortcut")

        before_restart_bundle = digest_bytes(session.owner.state.encode_bundle())
        before_restart_workspace = session.owner.state.resonant_workspace
        if before_restart_workspace is None:
            raise RuntimeError("wave missing before restart")
        before_restart_workspace_sha256 = before_restart_workspace.state_sha256
        restart = session.restart()
        after_restart_bundle = digest_bytes(session.owner.state.encode_bundle())
        after_restart_workspace = session.owner.state.resonant_workspace
        if after_restart_workspace is None:
            raise RuntimeError("wave missing after restart")
        post_restart_selection = session.owner.select_temporal_action(
            MEMORY,
            skill_ids=SKILLS,
            operations=allowed,
            minimum_margin=MINIMUM_MARGIN,
        )
        require(
            before_restart_bundle == after_restart_bundle
            and before_restart_workspace_sha256 == after_restart_workspace.state_sha256,
            "restart changed the learned closure",
        )
        require(
            post_restart_selection["selected"] is not None
            and post_restart_selection["selected"]["skill_id"] == STAGED_SKILL,
            "restart lost the online preference",
        )

        final_memory = session.owner.state.temporal(MEMORY)
        final_workspace = session.owner.state.resonant_workspace
        if final_workspace is None:
            raise RuntimeError("final resonant workspace is absent")
        return {
            "seed": seed,
            "operations": list(allowed),
            "registrations": [result["receipt"] for result in registrations],
            "candidate_start": {
                "online": initial_online,
                "no_outcome_wave_control": initial_control,
                "workspace": start_workspace_record,
                "candidate_semantics": initial_semantics,
            },
            "feedback_target_skill": STAGED_SKILL,
            "trajectory": trajectory,
            "crossover_round": crossover_rounds[0],
            "held_out": {
                "online": online_trial,
                "no_outcome_wave_control": control_trial,
            },
            "restart": {
                **dict(restart),
                "before_bundle_sha256": before_restart_bundle,
                "after_bundle_sha256": after_restart_bundle,
                "before_workspace_state_sha256": before_restart_workspace_sha256,
                "after_workspace_state_sha256": after_restart_workspace.state_sha256,
                "selection": post_restart_selection,
            },
            "sources": list(session.sources),
            "costs": dict(session.costs),
            "field": {
                "state_sha256": session.owner.state.state_sha256,
                "memory_sha256": final_memory.memory_sha256,
                "categorical_state_sha256": final_memory.state_sha256,
                "formed_skill_ids": list(final_memory.formed_skill_ids),
                "resonant_workspace_state_sha256": final_workspace.state_sha256,
                "resonant_field_bytes": len(final_workspace.page_bytes),
                "ledger": dict(final_workspace.ledger),
            },
            "elapsed_seconds": time.perf_counter() - started,
            "live_model_calls": 0,
        }
    finally:
        session.owner.close()


def aggregate(runs: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    return {
        "runs": len(runs),
        "online_crossovers": sum(run["crossover_round"] <= FEEDBACK_ROUNDS for run in runs),
        "crossover_rounds": [run["crossover_round"] for run in runs],
        "online_completed": sum(run["held_out"]["online"]["completed"] is True for run in runs),
        "control_completed": sum(run["held_out"]["no_outcome_wave_control"]["completed"] is True for run in runs),
        "online_action_steps": sum(run["held_out"]["online"]["action_steps"] for run in runs),
        "control_action_steps": sum(run["held_out"]["no_outcome_wave_control"]["action_steps"] for run in runs),
        "online_unsafe_observations": sum(run["held_out"]["online"]["unsafe_observations"] for run in runs),
        "control_unsafe_observations": sum(run["held_out"]["no_outcome_wave_control"]["unsafe_observations"] for run in runs),
        "outcome_feedback_work": sum(
            row["resonance_coupling"]["total_applied_work"]
            for run in runs
            for row in run["trajectory"]
        ),
        "field_only_counterfactuals": sum(
            run["trajectory"][-1]["online"]["selected"]["skill_id"]
            != run["trajectory"][-1]["no_outcome_wave_control"]["selected"]["skill_id"]
            for run in runs
        ),
        "exact_restarts": sum(
            run["restart"]["before_bundle_sha256"]
            == run["restart"]["after_bundle_sha256"]
            for run in runs
        ),
        "live_model_calls": sum(run["live_model_calls"] for run in runs),
        "total_elapsed_seconds": sum(run["elapsed_seconds"] for run in runs),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-home", type=Path, required=True)
    args = parser.parse_args()
    if not args.seeds or len(args.seeds) != len(set(args.seeds)):
        parser.error("seeds must be a nonempty unique list")
    if args.data_home.exists():
        parser.error("data-home must not already exist")

    runs = [
        run_seed(args.data_home / "owners" / f"seed-{seed}", seed)
        for seed in args.seeds
    ]
    report = {
        "schema": SCHEMA,
        "source_sha256": digest_bytes(Path(__file__).read_bytes()),
        "configuration": {
            "seeds": list(args.seeds),
            "memory_id": MEMORY,
            "skills": list(SKILLS),
            "actions": list(ACTIONS),
            "observations": list(OBSERVATIONS),
            "paths": {key: list(value) for key, value in PATHS.items()},
            "goals": {key: list(value) for key, value in GOALS.items()},
            "feedback_rounds": FEEDBACK_ROUNDS,
            "feedback_target_skill": STAGED_SKILL,
            "outcome_work_budget_per_admission": 1e-3,
            "minimum_selection_margin": MINIMUM_MARGIN,
            "control": "same current categorical candidates scored against the exact pre-feedback workspace",
            "held_out_world": "fast shortcut jams; staged release completes",
        },
        "runs": runs,
        "aggregate": aggregate(runs),
        "claim_boundary": [
            "This measures a causal field-only preference crossover under repeated admitted outcomes: current categorical candidates are identical within each online/control comparison, and only the online score sees post-start resonant outcome work.",
            "The held-wave control is a counterfactual scorer over the online learner's current candidate records, not a second independently persisted owner.",
            "The fixed two-skill vocabulary, registered goals, authorization, feasibility, and held-out simulator are supplied; this does not establish open-vocabulary invention, calibrated uncertainty, broad generalization, or subjective experience.",
            "The three seeds permute operation presentation and source identities but repeat one deterministic controlled world.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
