"""Measure field-owned discovery, automatic formation, transfer, and restart.

The scenario registers a prospective skill goal before discovery, but supplies
neither a successful action sequence nor a policy. During the discovery
encounter, every observation is admitted as an append-only source revision.
The registered skill remains pending until the learned numeric field contains
a supported safe path from its root, at which point learning itself forms the
policy. Transfer encounters receive only the formed skill identifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_temporal_field import TemporalField
from cassi_resonant_field import (
    ResonantWorkspace,
    advance_workspace,
    inspect_workspace,
)
from run_temporal_learning_scenario import Session

SCHEMA = "cassifi.temporal-autonomous-skill-formation.v3"
MEMORY = "three-stage-release"
SKILL = "release-three-stage-latch"
ACTIONS = ("prime", "align", "open")
OBSERVATIONS = ("primed", "aligned", "opened", "blocked", "misaligned")
GOALS = ("opened",)
FORBIDDEN = ("blocked", "misaligned")
CONTEXT = {
    "mechanism": "three-stage-latch",
    "task": "release",
    "measurement": "field-owned-autonomous-skill-formation",
}
SEEDS = (101, 202, 303)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def transition_sha256(memory: TemporalField) -> str:
    """Hash shared transition, state-count, and action-coverage coordinates."""
    m = memory.max_states
    planes = np.ascontiguousarray(memory.field[0, : 4 * m, :], dtype=np.float64)
    return sha256_bytes(planes.tobytes(order="C"))


def resonance_summary(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    pools = snapshot["pool_sample"]
    return {
        "workspace_state_sha256": snapshot.get(
            "workspace_state_sha256",
            snapshot["state_sha256"],
        ),
        "energy": snapshot["energy"],
        "field_ticks": snapshot["field_ticks"],
        "evidence_tick": snapshot["evidence_tick"],
        "heartbeat_phase": snapshot["heartbeat_phase"],
        "heartbeat_cycles": snapshot["heartbeat_cycles"],
        "breath_phase": snapshot["breath_phase"],
        "breath_cycles": snapshot["breath_cycles"],
        "activity": snapshot["activity"],
        "pool_power": [row["power"] for row in pools],
        "pool_amplitude": [row["amplitude"] for row in pools],
        "common_rail_power": snapshot["common_rail_power"],
        "counterflow_rail_power": snapshot["counterflow_rail_power"],
        "ledger": dict(snapshot["ledger"]),
    }


def operation(action: str) -> dict[str, Any]:
    return {
        "action": action,
        "cost": 1.0,
        "risk": 0.0,
        "authorized": True,
        "feasible": True,
        "acquisition_allowed": True,
    }


def operations(seed: int) -> tuple[Mapping[str, Any], ...]:
    rows = [operation(action) for action in ACTIONS]
    random.Random(seed).shuffle(rows)
    return tuple(rows)


class ThreeStageLatch:
    """Small deterministic environment with two observed unsafe shortcuts."""

    def __init__(self) -> None:
        self.primed = False
        self.aligned = False
        self.opened = False

    def step(self, action: str) -> str:
        if action == "prime":
            self.primed = True
            return "primed"
        if action == "align":
            if self.primed:
                self.aligned = True
                return "aligned"
            return "misaligned"
        if action == "open":
            if self.aligned:
                self.opened = True
                return "opened"
            return "blocked"
        raise ValueError(f"unknown action: {action}")


def execute_condensed_skill(
    session: Session,
    participant_id: str,
) -> Mapping[str, Any]:
    """Apply only the persisted skill readout to a fresh environment."""
    session.mutate(
        "bind_temporal",
        memory_id=MEMORY,
        participant_id=participant_id,
        known_start=True,
    )
    mechanism = ThreeStageLatch()
    records: list[dict[str, Any]] = []
    for tick in range(6):
        before = session.owner.inspect_temporal(
            MEMORY,
            participant_id=participant_id,
            skill_id=SKILL,
        )
        decision = dict(before["skill"])
        action = decision.get("action")
        records.append({
            "tick": tick,
            "decision": decision,
            "goal_observations_supplied": False,
        })
        if not isinstance(action, str):
            break
        observed = mechanism.step(action)
        records[-1]["observation"] = observed
        session.mutate(
            "advance_temporal",
            memory_id=MEMORY,
            participant_id=participant_id,
            action=action,
            observation=observed,
        )
        if observed in GOALS:
            break
    return {
        "participant_id": participant_id,
        "completed": mechanism.opened,
        "actions": [row["decision"].get("action") for row in records if row["decision"].get("action") is not None],
        "observations": [row["observation"] for row in records if "observation" in row],
        "unsafe_observations": sum(row.get("observation") in FORBIDDEN for row in records),
        "records": records,
    }


def run_seed(home: Path, seed: int) -> Mapping[str, Any]:
    started = time.perf_counter()
    session = Session(
        home,
        seed,
        "skill-formation",
        memory_id=MEMORY,
        action_ids=ACTIONS,
        observation_ids=OBSERVATIONS,
        max_states=16,
        context=CONTEXT,
    )
    try:
        # These establish only that the two shortcuts are unsafe. Neither
        # source contains a successful transition or any part of its prefix.
        background = (
            ("failed-open", ({"action": "open", "observation": "blocked"},)),
            ("failed-align", ({"action": "align", "observation": "misaligned"},)),
        )
        for label, steps in background:
            session.learn(label, steps)
        require(
            session.owner.state.resonant_workspace is None,
            "skill-free evidence initialized the resonant workspace",
        )

        before_registration = session.owner.state.temporal(MEMORY)
        pre_registration_transition_sha256 = transition_sha256(before_registration)
        pre_registration_memory_sha256 = before_registration.memory_sha256
        pre_registration_state_sha256 = before_registration.state_sha256
        registration = session.mutate(
            "condense_temporal_skill",
            memory_id=MEMORY,
            skill_id=SKILL,
            goal_observations=GOALS,
            forbidden_observations=FORBIDDEN,
        )
        pending = session.owner.state.temporal(MEMORY)
        require(registration["receipt"]["status"] == "pending", "skill formed before successful evidence")
        require(registration["receipt"]["start_state_supported"] is False, "unsupported root was marked ready")
        require(pending.skill_ids == (SKILL,), "prospective skill registration was not retained")
        require(pending.formed_skill_ids == (), "prospective skill unexpectedly formed")
        require(pending.pending_skill_ids == (SKILL,), "prospective skill is not pending")
        require(
            registration["receipt"]["resonance_coupling"]["applied"] is False,
            "pending registration emitted resonant work",
        )
        require(
            session.owner.state.resonant_workspace is None,
            "pending registration initialized the resonant workspace",
        )
        require(
            pre_registration_transition_sha256 == transition_sha256(pending),
            "skill registration changed learned transitions",
        )
        require(
            pre_registration_memory_sha256 == pending.memory_sha256,
            "skill registration changed learned memory",
        )
        pending_readout = pending.skill_action(SKILL)
        require(
            pending_readout.get("status") == "unresolved"
            and pending_readout.get("action") is None,
            "pending skill exposed an executable action",
        )

        participant_id = f"discovery-{seed}"
        session.mutate(
            "bind_temporal",
            memory_id=MEMORY,
            participant_id=participant_id,
            known_start=True,
        )
        mechanism = ThreeStageLatch()
        trace: list[dict[str, str]] = []
        decisions: list[dict[str, Any]] = []
        formation_events: list[dict[str, Any]] = []
        discovery_source_id = f"active:{seed}:skill-formation:discovery"
        allowed = operations(seed)
        for tick in range(6):
            inquiry_started = time.perf_counter()
            inquiry = session.owner.inquire_temporal(
                MEMORY,
                participant_id=participant_id,
                operations=allowed,
                goal_observations=GOALS,
                horizon=4,
                max_nodes=4096,
                forbidden_observations=FORBIDDEN,
            )
            session.costs["inquiry_seconds"] += time.perf_counter() - inquiry_started
            action = inquiry.get("action")
            if not isinstance(action, str):
                raise RuntimeError("autonomous discovery stopped before reaching the goal")
            observed = mechanism.step(action)
            trace.append({"action": action, "observation": observed})
            session.mutate(
                "advance_temporal",
                memory_id=MEMORY,
                participant_id=participant_id,
                action=action,
                observation=observed,
            )
            learning = session.learn(
                f"discovery-{tick}",
                trace,
                source_id=discovery_source_id,
            )
            learning_receipt = dict(learning["receipt"])
            current = session.owner.state.temporal(MEMORY)
            formation_events.append({
                "tick": tick,
                "formed_skills": list(learning_receipt["formed_skills"]),
                "withdrawn_skills": list(learning_receipt["withdrawn_skills"]),
                "available_skills": list(learning_receipt["available_skills"]),
                "pending_skills": list(learning_receipt["pending_skills"]),
                "memory_sha256": current.memory_sha256,
                "state_sha256": current.state_sha256,
                "transition_sha256": transition_sha256(current),
                "readout": dict(current.skill_action(SKILL, participant_id=participant_id)),
                "resonance_coupling": dict(learning_receipt["resonance_coupling"]),
            })
            decisions.append({
                "tick": tick,
                "action": action,
                "observation": observed,
                "status": inquiry.get("status"),
                "reason": inquiry.get("reason"),
                "decision_resolved": inquiry.get("decision_resolved"),
                "candidate_states": inquiry.get("candidate_states"),
                "work": inquiry.get("work"),
                "acquisition": inquiry.get("acquisition"),
            })
            if observed in GOALS:
                break

        require(mechanism.opened, "field-selected discovery did not release the latch")
        formed = session.owner.state.temporal(MEMORY)
        formed_transition_sha256 = transition_sha256(formed)
        require(formed.formed_skill_ids == (SKILL,), "successful evidence did not form the skill")
        require(formed.pending_skill_ids == (), "formed skill remained pending")
        require(
            [row["tick"] for row in formation_events if row["formed_skills"] == [SKILL]] == [2],
            "skill did not form exactly at the successful evidence boundary",
        )
        require(
            all(not row["formed_skills"] for row in formation_events[:2]),
            "skill formed before the complete path was supported",
        )
        require(
            all(
                row["resonance_coupling"]["applied"] is False
                for row in formation_events[:2]
            ),
            "partial evidence emitted resonant work before skill formation",
        )
        formation_coupling = formation_events[2]["resonance_coupling"]
        require(
            formation_coupling["applied"] is True
            and tuple(formation_coupling["formed_skills"]) == (SKILL,)
            and tuple(formation_coupling["withdrawn_skills"]) == (),
            "successful evidence did not emit exactly one formation coupling",
        )
        require(
            abs(formation_coupling["total_applied_work"] - 1e-3) <= 1e-12,
            "formation coupling violated its work budget",
        )
        formed_workspace = session.owner.state.resonant_workspace
        if formed_workspace is None:
            raise RuntimeError("formation did not initialize the wave field")
        immediate_resonance = resonance_summary(session.owner.inspect_resonance())
        require(
            [power > 0.0 for power in immediate_resonance["pool_power"]]
            == [True, False, False, True, False, False, True],
            "formation impulse did not encode the three temporal ranks",
        )

        propagation_ticks = 8
        control_workspace = ResonantWorkspace(
            profile=formed_workspace.profile,
            evidence_tick=formed_workspace.evidence_tick,
        )
        control_workspace, control_advance = advance_workspace(
            control_workspace,
            ticks=propagation_ticks,
            source_enabled=False,
        )
        propagation = session.mutate(
            "advance",
            ticks=propagation_ticks,
            source_enabled=False,
        )
        propagated_resonance = resonance_summary(session.owner.inspect_resonance())
        control_resonance = resonance_summary(inspect_workspace(control_workspace))
        require(
            all(power > 0.0 for power in propagated_resonance["pool_power"]),
            "formation signal did not propagate through all seven pools",
        )
        require(
            all(power == 0.0 for power in control_resonance["pool_power"]),
            "matched no-impulse control acquired wave power",
        )
        require(
            propagated_resonance["workspace_state_sha256"]
            != control_resonance["workspace_state_sha256"],
            "formation impulse did not change the committed wave result",
        )
        require(
            propagated_resonance["field_ticks"] == control_resonance["field_ticks"]
            and propagated_resonance["heartbeat_phase"] == control_resonance["heartbeat_phase"]
            and propagated_resonance["breath_phase"] == control_resonance["breath_phase"]
            and propagated_resonance["activity"] == control_resonance["activity"],
            "coupled and control wave clocks are not matched",
        )
        require(
            abs(propagation["resonance_receipt"]["balance_defect"]) <= 1e-12
            and abs(control_advance["balance_defect"]) <= 1e-12,
            "wave propagation violated discrete work balance",
        )

        control, _ = TemporalField.initial(
            MEMORY,
            action_ids=ACTIONS,
            observation_ids=OBSERVATIONS,
            max_states=16,
            context=CONTEXT,
        ).learn(
            [
                [dict(step) for step in background[0][1]],
                [dict(step) for step in background[1][1]],
                trace,
            ],
            source_revision_ids=formed.source_revision_ids,
        )
        require(
            transition_sha256(control) == formed_transition_sha256,
            "registered-skill learning changed the matched transition field",
        )
        require(
            control.memory_sha256 == formed.memory_sha256,
            "registered-skill learning changed matched learned memory",
        )
        require(control.skill_ids == (), "unregistered causal control contains a skill")

        transfer = execute_condensed_skill(session, f"fresh-{seed}")
        require(transfer["completed"] is True, "fresh participant did not complete the skill")
        require(transfer["unsafe_observations"] == 0, "fresh participant reached an unsafe outcome")

        before_restart_bundle_sha256 = sha256_bytes(session.owner.state.encode_bundle())
        before_restart_workspace_sha256 = (
            session.owner.state.resonant_workspace.state_sha256
            if session.owner.state.resonant_workspace is not None
            else None
        )
        restart = session.restart()
        after_restart_bundle_sha256 = sha256_bytes(session.owner.state.encode_bundle())
        after_restart_workspace_sha256 = (
            session.owner.state.resonant_workspace.state_sha256
            if session.owner.state.resonant_workspace is not None
            else None
        )
        require(before_restart_bundle_sha256 == after_restart_bundle_sha256, "restart changed persisted closure")
        require(
            before_restart_workspace_sha256 == after_restart_workspace_sha256,
            "restart changed the coupled resonant workspace",
        )
        restarted = session.owner.state.temporal(MEMORY)
        require(SKILL in restarted.formed_skill_ids, "restart lost the formed skill")
        restart_transfer = execute_condensed_skill(session, f"restart-fresh-{seed}")
        require(restart_transfer["completed"] is True, "restarted owner did not reuse the skill")
        require(restart_transfer["unsafe_observations"] == 0, "restarted skill reached an unsafe outcome")

        discovery_sources = [row for row in session.sources if row["source_id"] == discovery_source_id]
        return {
            "seed": seed,
            "discovery": {
                "completed": mechanism.opened,
                "actions": [row["action"] for row in trace],
                "observations": [row["observation"] for row in trace],
                "unsafe_observations": sum(row["observation"] in FORBIDDEN for row in trace),
                "decisions": decisions,
                "source_id": discovery_source_id,
                "source_revisions": len(discovery_sources),
                "source_chain": discovery_sources,
            },
            "registration": {
                "receipt": registration["receipt"],
                "pre_memory_sha256": pre_registration_memory_sha256,
                "post_memory_sha256": pending.memory_sha256,
                "pre_state_sha256": pre_registration_state_sha256,
                "post_state_sha256": pending.state_sha256,
                "pre_transition_sha256": pre_registration_transition_sha256,
                "post_transition_sha256": transition_sha256(pending),
                "skill_ids": list(pending.skill_ids),
                "formed_skill_ids": list(pending.formed_skill_ids),
                "pending_skill_ids": list(pending.pending_skill_ids),
                "readout": dict(pending_readout),
            },
            "formation": {
                "events": formation_events,
                "trigger_tick": 2,
                "memory_sha256": formed.memory_sha256,
                "state_sha256": formed.state_sha256,
                "transition_sha256": formed_transition_sha256,
                "matched_unregistered_memory_sha256": control.memory_sha256,
                "matched_unregistered_transition_sha256": transition_sha256(control),
                "skill_ids": list(formed.skill_ids),
                "formed_skill_ids": list(formed.formed_skill_ids),
                "pending_skill_ids": list(formed.pending_skill_ids),
            },
            "resonance": {
                "formation_coupling": formation_coupling,
                "immediate": immediate_resonance,
                "propagation_ticks": propagation_ticks,
                "propagation_receipt": propagation["resonance_receipt"],
                "coupled_after_propagation": propagated_resonance,
                "uncoupled_control_after_propagation": control_resonance,
                "uncoupled_control_receipt": control_advance,
                "source_enabled": False,
                "same_profile_and_clocks": True,
                "categorical_policy_wave_gated": False,
            },
            "transfer": transfer,
            "restart": {
                **dict(restart),
                "before_bundle_sha256": before_restart_bundle_sha256,
                "after_bundle_sha256": after_restart_bundle_sha256,
                "before_workspace_state_sha256": before_restart_workspace_sha256,
                "after_workspace_state_sha256": after_restart_workspace_sha256,
                "skill_ids": list(restarted.skill_ids),
                "transfer": restart_transfer,
            },
            "field": {
                "state_count": restarted.state_count,
                "field_bytes": restarted.nbytes,
                "state_sha256": session.owner.state.state_sha256,
                "bundle_sha256": sha256_bytes(session.owner.state.encode_bundle()),
                "resonant_workspace_state_sha256": (
                    None
                    if session.owner.state.resonant_workspace is None
                    else session.owner.state.resonant_workspace.state_sha256
                ),
                "resonant_field_bytes": (
                    0
                    if session.owner.state.resonant_workspace is None
                    else len(session.owner.state.resonant_workspace.page_bytes)
                ),
            },
            "sources": list(session.sources),
            "costs": dict(session.costs),
            "elapsed_seconds": time.perf_counter() - started,
            "live_model_calls": 0,
        }
    finally:
        session.owner.close()


def aggregate(runs: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    expected = ["prime", "align", "open"]
    return {
        "runs": len(runs),
        "discovery_completed": sum(run["discovery"]["completed"] is True for run in runs),
        "transfer_completed": sum(run["transfer"]["completed"] is True for run in runs),
        "restart_transfer_completed": sum(run["restart"]["transfer"]["completed"] is True for run in runs),
        "initial_skill_pending": sum(run["registration"]["pending_skill_ids"] == [SKILL] for run in runs),
        "evidence_triggered_formations": sum(run["formation"]["formed_skill_ids"] == [SKILL] for run in runs),
        "formation_trigger_matches": sum(run["formation"]["trigger_tick"] == 2 for run in runs),
        "matched_unregistered_transitions": sum(
            run["formation"]["transition_sha256"]
            == run["formation"]["matched_unregistered_transition_sha256"]
            for run in runs
        ),
        "formation_wave_couplings": sum(
            run["resonance"]["formation_coupling"]["applied"] is True
            for run in runs
        ),
        "formation_wave_work": sum(
            run["resonance"]["formation_coupling"]["total_applied_work"]
            for run in runs
        ),
        "all_pool_propagations": sum(
            all(power > 0.0 for power in run["resonance"]["coupled_after_propagation"]["pool_power"])
            for run in runs
        ),
        "uncoupled_controls_quiet": sum(
            all(
                power == 0.0
                for power in run["resonance"]["uncoupled_control_after_propagation"]["pool_power"]
            )
            for run in runs
        ),
        "wave_counterfactuals_changed": sum(
            run["resonance"]["coupled_after_propagation"]["workspace_state_sha256"]
            != run["resonance"]["uncoupled_control_after_propagation"]["workspace_state_sha256"]
            for run in runs
        ),
        "wave_clock_matches": sum(
            run["resonance"]["same_profile_and_clocks"] is True
            for run in runs
        ),
        "exact_wave_restarts": sum(
            run["restart"]["before_workspace_state_sha256"]
            == run["restart"]["after_workspace_state_sha256"]
            and run["restart"]["before_workspace_state_sha256"] is not None
            for run in runs
        ),
        "discovery_sequence_matches": sum(run["discovery"]["actions"] == expected for run in runs),
        "transfer_sequence_matches": sum(run["transfer"]["actions"] == expected for run in runs),
        "restart_sequence_matches": sum(run["restart"]["transfer"]["actions"] == expected for run in runs),
        "unsafe_observations": sum(run["discovery"]["unsafe_observations"] + run["transfer"]["unsafe_observations"] + run["restart"]["transfer"]["unsafe_observations"] for run in runs),
        "live_model_calls": sum(run["live_model_calls"] for run in runs),
        "exact_restarts": sum(run["restart"]["exact_closure"] is True for run in runs),
        "total_elapsed_seconds": sum(run["elapsed_seconds"] for run in runs),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-home", type=Path, required=True)
    args = parser.parse_args()
    if not args.seeds or len(set(args.seeds)) != len(args.seeds):
        parser.error("seeds must be a nonempty unique list")
    if args.data_home.exists():
        parser.error("data-home must not already exist")

    runs = []
    for seed in args.seeds:
        runs.append(run_seed(args.data_home / "owners" / f"seed-{seed}", seed))
    report = {
        "schema": SCHEMA,
        "source_sha256": sha256_bytes(Path(__file__).read_bytes()),
        "configuration": {
            "seeds": list(args.seeds),
            "memory_id": MEMORY,
            "skill_id": SKILL,
            "actions": list(ACTIONS),
            "observations": list(OBSERVATIONS),
            "goal_observations": list(GOALS),
            "forbidden_observations": list(FORBIDDEN),
            "background_sources": [
                [{"action": "open", "observation": "blocked"}],
                [{"action": "align", "observation": "misaligned"}],
            ],
            "successful_sequence_supplied": False,
            "transfer_goal_observations_supplied": False,
            "prospective_skill_goal_registered_before_discovery": True,
            "post_experience_condensation_called": False,
            "resonant_coupling": {
                "formation_work_budget": 1e-3,
                "withdrawal_work_budget": 1e-3,
                "propagation_ticks": 8,
                "propagation_source_enabled": False,
                "control": "same profile, evidence clock, and propagation clocks; no skill impulse",
                "categorical_policy_wave_gated": False,
            },
        },
        "runs": runs,
        "aggregate": aggregate(runs),
        "claim_boundary": [
            "This measures automatic evidence-triggered formation of a registered prospective skill inside a fixed supplied vocabulary and goal.",
            "It does not establish autonomous skill naming, goal invention, action invention, open-vocabulary acquisition, or broad task generalization.",
            "The formation event is physically coupled into the continuous seven-pool field and propagates under the measured wave law; categorical action selection is not yet wave-gated.",
            "The three seeds permute operation presentation but are reproducibility repeats of one deterministic environment, not independent worlds.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
