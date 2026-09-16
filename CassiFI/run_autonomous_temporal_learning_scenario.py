"""Measure field-selected acquisition, episode-boundary learning, and transfer.

The learner starts without jammed-mechanism episodes.  Its first bounded
acquisition segment is selected by the temporal field rather than an action
teacher.  Actual observations are admitted only when that segment closes, so
the next segment can measure a causal learning effect without making the
currently open endpoint a learned predictive leaf.  Oracle and frozen controls
replay the exact field-selected acquisition traces.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

from run_temporal_learning_scenario import (
    MEMORY,
    SKILL,
    TRANSFER_MODES,
    Mechanism,
    Session,
    bootstrap,
    make_source,
    run_trial,
)

ARMS = ("online", "oracle", "frozen")
ACQUISITION_EPISODES = 3
ACQUISITION_HORIZON = 4
ACQUISITION_ACTIONS = ("probe", "read", "inspect", "idle", "clear", "wait")
REFERENCE_MEMORY = "retained-reference"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def field_sha256(session: Session) -> str:
    """Hash only the shared learned numeric slice, not working participants."""
    return hashlib.sha256(
        session.owner.state.temporal(MEMORY).field[0].tobytes(order="C")
    ).hexdigest()


def acquisition_operations() -> list[dict[str, Any]]:
    """Return the explicitly authorized reversible/passive acquisition surface."""
    return [
        {
            "action": action,
            "cost": 1.0,
            "risk": 0.0,
            "authorized": True,
            "feasible": True,
            "acquisition_allowed": True,
        }
        for action in ACQUISITION_ACTIONS
    ]


def participant_ids() -> tuple[str, ...]:
    acquisition = tuple(f"acquire-{index}" for index in range(ACQUISITION_EPISODES))
    transfer = tuple(
        f"transfer-{trial}-{side}"
        for trial in range(len(TRANSFER_MODES))
        for side in ("left", "right")
    )
    return (*acquisition, "acquisition-counterfactual", *transfer)


def setup_session(home: Path, seed: int, arm: str) -> tuple[Session, Mapping[str, Any]]:
    session = Session(home, seed, arm)
    normal = [
        episode for episode in bootstrap(seed)
        if episode[0]["observation"] == "pulse-a"
    ]
    require(len(normal) == 6, "normal bootstrap count changed")
    for index, episode in enumerate(normal):
        session.learn(f"bootstrap-normal-{index}", episode)

    reference_steps = [
        {"action": "start", "observation": "ready"},
        {"action": "finish", "observation": "done"},
    ]
    session.mutate(
        "configure_temporal",
        memory_id=REFERENCE_MEMORY,
        action_ids=("start", "finish"),
        observation_ids=("ready", "done"),
    )
    session.mutate(
        "learn_temporal",
        memory_id=REFERENCE_MEMORY,
        source=make_source(seed, arm, "retained-reference", reference_steps),
    )
    retained = session.owner.state.temporal(REFERENCE_MEMORY).as_dict()
    session.mutate(
        "condense_temporal_skill",
        memory_id=MEMORY,
        skill_id=SKILL,
        goal_observations=("released",),
        forbidden_observations=("fault", "blocked"),
    )
    for participant in participant_ids():
        session.mutate(
            "bind_temporal",
            memory_id=MEMORY,
            participant_id=participant,
            known_start=False,
        )
    return session, retained


def autonomous_segment(
    session: Session,
    episode: int,
    budget: int,
) -> dict[str, Any]:
    participant = f"acquire-{episode}"
    row = dict(run_trial(
        session,
        episode,
        (True,),
        budget,
        learning_enabled=False,
        participant_ids=(participant,),
        inquiry_operations=acquisition_operations(),
        inquiry_horizon=ACQUISITION_HORIZON,
    ))
    steps = list(row["source_episodes"][participant])
    require(len(steps) >= 2, "autonomous acquisition produced no usable trajectory")
    require(row["unsafe_observations"] == 0, "autonomous acquisition reached an unsafe outcome")
    for record in row["records"]:
        action = record.get("action")
        if action is None:
            continue
        require(
            record["kind"] == "skill" or action in ACQUISITION_ACTIONS,
            "autonomous inquiry escaped the authorized acquisition surface",
        )
    memory_before = session.owner.state.temporal(MEMORY).memory_sha256
    learning = session.learn(
        f"autonomous-{episode}",
        steps,
        source_id=f"active:{session.seed}:{session.arm}:autonomous-{episode}",
    )
    require(
        session.owner.state.temporal(MEMORY).memory_sha256 != memory_before,
        "autonomous segment did not change learned memory",
    )
    return {
        "episode": episode,
        "participant_id": participant,
        "field_selected": True,
        "steps": steps,
        "records": row["records"],
        "completed": row["completed"],
        "interactions": row["interactions"],
        "diagnostic_interactions": row["diagnostic_interactions"],
        "support_gap_observations": row["support_gap_observations"],
        "unsafe_observations": row["unsafe_observations"],
        "external_effect_count": row["external_effect_count"],
        "learning": learning["receipt"],
        "state_count_after_admission": session.owner.state.temporal(MEMORY).state_count,
    }


def replay_segment(
    session: Session,
    episode: int,
    expected_steps: Sequence[Mapping[str, str]],
    *,
    learn: bool,
) -> dict[str, Any]:
    participant = f"acquire-{episode}"
    session.mutate(
        "reset_temporal",
        memory_id=MEMORY,
        participant_id=participant,
        known_start=False,
    )
    mechanism = Mechanism(jammed=True)
    records: list[dict[str, Any]] = []
    memory_before = session.owner.state.temporal(MEMORY).memory_sha256
    for tick, expected in enumerate(expected_steps):
        prediction = session.owner.inspect_temporal(
            MEMORY,
            participant_id=participant,
            action=expected["action"],
        )["prediction"]
        observation = mechanism.step(expected["action"])
        require(observation == expected["observation"], "acquisition replay diverged")
        result = session.mutate(
            "advance_temporal",
            memory_id=MEMORY,
            participant_id=participant,
            action=expected["action"],
            observation=observation,
        )
        records.append({
            "tick": tick,
            "action": expected["action"],
            "observation": observation,
            "prediction": prediction,
            "receipt": result["receipt"],
        })
    require(
        session.owner.state.temporal(MEMORY).memory_sha256 == memory_before,
        "acquisition replay mutated learned memory before admission",
    )
    learning = None
    if learn:
        learning = session.learn(
            f"autonomous-{episode}",
            expected_steps,
            source_id=f"active:{session.seed}:{session.arm}:autonomous-{episode}",
        )["receipt"]
    return {
        "episode": episode,
        "participant_id": participant,
        "field_selected": False,
        "steps": list(expected_steps),
        "records": records,
        "completed": not mechanism.latched,
        "interactions": len(expected_steps),
        "unsafe_observations": sum(
            step["observation"] in {"fault", "blocked"} for step in expected_steps
        ),
        "learning": learning,
        "state_count_after_admission": session.owner.state.temporal(MEMORY).state_count,
    }


def acquisition_counterfactual(session: Session, budget: int) -> Mapping[str, Any]:
    """Re-run one matched selection after the first trace, without admission."""
    return run_trial(
        session,
        50,
        (True,),
        budget,
        learning_enabled=False,
        participant_ids=("acquisition-counterfactual",),
        inquiry_operations=acquisition_operations(),
        inquiry_horizon=ACQUISITION_HORIZON,
    )


def transfer_trials(session: Session, budget: int) -> list[Mapping[str, Any]]:
    rows = []
    for trial, modes in enumerate(TRANSFER_MODES):
        participants = (f"transfer-{trial}-left", f"transfer-{trial}-right")
        rows.append(run_trial(
            session,
            100 + trial,
            modes,
            budget,
            learning_enabled=False,
            participant_ids=participants,
            inquiry_operations=acquisition_operations(),
            inquiry_horizon=ACQUISITION_HORIZON,
        ))
    return rows


def run_arm(
    home: Path,
    seed: int,
    arm: str,
    budget: int,
    reference_traces: Sequence[Sequence[Mapping[str, str]]] | None,
) -> dict[str, Any]:
    session, retained = setup_session(home, seed, arm)
    started = time.perf_counter()
    try:
        initial = session.owner.state.temporal(MEMORY).as_dict()
        initial_numeric_sha256 = field_sha256(session)
        initial_state_count = session.owner.state.temporal(MEMORY).state_count
        acquisitions: list[dict[str, Any]] = []
        counterfactual: Mapping[str, Any] | None = None
        if arm == "online":
            require(reference_traces is None, "online arm received replay traces")
            for episode in range(ACQUISITION_EPISODES):
                acquisitions.append(autonomous_segment(session, episode, budget))
                if episode == 0:
                    session.restart()
                    counterfactual = acquisition_counterfactual(session, budget)
        else:
            if reference_traces is None:
                raise RuntimeError("control arm lacks replay traces")
            require(len(reference_traces) == ACQUISITION_EPISODES, "replay trace count mismatch")
            for episode, steps in enumerate(reference_traces):
                acquisitions.append(replay_segment(
                    session,
                    episode,
                    steps,
                    learn=arm == "oracle",
                ))
                if episode == 0:
                    session.restart()
                    counterfactual = acquisition_counterfactual(session, budget)

        if counterfactual is None:
            raise RuntimeError("acquisition counterfactual was not run")
        require(
            bool(counterfactual["completed"]) is (arm != "frozen"),
            "matched post-admission acquisition counterfactual changed",
        )
        acquisition_curve = [bool(row["completed"]) for row in acquisitions]
        require(acquisition_curve == [False, True, True], "autonomous learning curve changed")
        require(
            all(row["unsafe_observations"] == 0 for row in acquisitions),
            "acquisition trace contains unsafe observations",
        )
        trained = session.owner.state.temporal(MEMORY).as_dict()
        trained_numeric_sha256 = field_sha256(session)
        learned = trained["memory_sha256"] != initial["memory_sha256"]
        require(learned is (arm != "frozen"), "arm learning state mismatch")

        memory_before_transfer = trained["memory_sha256"]
        trials = transfer_trials(session, budget)
        require(
            session.owner.state.temporal(MEMORY).memory_sha256 == memory_before_transfer,
            "transfer scoring changed learned memory",
        )
        completed = sum(bool(row["completed"]) for row in trials)
        require(completed == (0 if arm == "frozen" else len(trials)), "transfer outcome mismatch")
        final = session.owner.state.temporal(MEMORY).as_dict()
        require(final["memory_sha256"] == memory_before_transfer, "final learned memory drifted")
        require(
            session.owner.state.temporal(REFERENCE_MEMORY).as_dict() == retained,
            "autonomous learning changed unrelated memory",
        )
        predictions = [
            record
            for trial in trials
            for record in trial["records"]
            if "prediction" in record
        ]
        answered = [record for record in predictions if record["prediction"]["supported"]]
        correct = sum(
            max(
                record["prediction"]["probabilities"],
                key=record["prediction"]["probabilities"].get,
            ) == record["observation"]
            for record in answered
        )
        restart = session.restart()
        storage = {
            "temporal_field_bytes": session.owner.state.temporal(MEMORY).nbytes,
            "active_closure_bytes": session.owner.state.closure_bytes,
            "evidence_bytes": session.owner.evidence.physical_bytes(),
            "data_home_bytes": sum(
                path.stat().st_size for path in home.rglob("*") if path.is_file()
            ),
        }
        elapsed = time.perf_counter() - started
        autonomous_sources = [
            source for source in session.sources if ":autonomous-" in source["source_id"]
        ]
        autonomous_heads = [
            source_id for source_id in session.source_heads if ":autonomous-" in source_id
        ]
        metrics = {
            "acquisition_segments": len(acquisitions),
            "acquisition_curve": acquisition_curve,
            "acquisition_interactions": sum(row["interactions"] for row in acquisitions),
            "autonomous_source_revisions": len(autonomous_sources),
            "autonomous_source_heads": len(autonomous_heads),
            "post_admission_counterfactual_completed": bool(counterfactual["completed"]),
            "post_admission_counterfactual_interactions": counterfactual["interactions"],
            "learned_from_autonomous_use": learned,
            "initial_state_count": initial_state_count,
            "trained_state_count": session.owner.state.temporal(MEMORY).state_count,
            "initial_numeric_sha256": initial_numeric_sha256,
            "trained_numeric_sha256": trained_numeric_sha256,
            "completed": completed,
            "total": len(trials),
            "interactions": sum(row["interactions"] for row in trials),
            "diagnostic_interactions": sum(row["diagnostic_interactions"] for row in trials),
            "support_gap_observations": sum(row["support_gap_observations"] for row in trials),
            "predictions": len(predictions),
            "answered": len(answered),
            "correct": correct,
            "unsafe_observations": sum(row["unsafe_observations"] for row in trials),
            "context_recoveries": sum(row["context_recoveries"] for row in trials),
            "recovery_sequences": sum(row["recovery_sequences"] for row in trials),
            "elapsed_seconds": elapsed,
        }
        return {
            "seed": seed,
            "arm": arm,
            "acquisitions": acquisitions,
            "acquisition_counterfactual": counterfactual,
            "transfer_trials": trials,
            "initial_field": initial,
            "trained_field": trained,
            "final_field": final,
            "sources": session.sources,
            "source_heads": dict(session.source_heads),
            "source_prefixes": {
                source_id: list(prefix)
                for source_id, prefix in session.source_prefixes.items()
            },
            "costs": session.costs,
            "storage": storage,
            "retention": {
                "unrelated_field": retained,
                "unrelated_exact": True,
                "memory_stable_during_transfer": True,
            },
            "restart": restart,
            "metrics": metrics,
            "live_model_calls": 0,
        }
    finally:
        session.owner.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-home", type=Path, required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    parser.add_argument("--budget", type=int, default=32)
    args = parser.parse_args()
    if not 8 <= args.budget <= 128 or not 1 <= len(args.seeds) <= 16:
        parser.error("scenario bounds exceeded")
    if args.data_home.exists() or args.output.exists():
        parser.error("output and data-home must be unused paths")
    torch.set_num_threads(1)

    runs: list[dict[str, Any]] = []
    for seed in args.seeds:
        seed_runs: dict[str, dict[str, Any]] = {}
        online = run_arm(
            args.data_home / f"seed-{seed}" / "online",
            seed,
            "online",
            args.budget,
            None,
        )
        traces = [row["steps"] for row in online["acquisitions"]]
        seed_runs["online"] = online
        runs.append(online)
        print(json.dumps({"seed": seed, "arm": "online", **online["metrics"]}), flush=True)
        for arm in ("oracle", "frozen"):
            run = run_arm(
                args.data_home / f"seed-{seed}" / arm,
                seed,
                arm,
                args.budget,
                traces,
            )
            seed_runs[arm] = run
            runs.append(run)
            print(json.dumps({"seed": seed, "arm": arm, **run["metrics"]}), flush=True)

        require(
            len({row["metrics"]["initial_numeric_sha256"] for row in seed_runs.values()}) == 1,
            "matched arms did not start from one numeric field",
        )
        require(
            len({
                json.dumps([row["steps"] for row in run["acquisitions"]], sort_keys=True)
                for run in seed_runs.values()
            }) == 1,
            "control arms did not replay the autonomous acquisition traces",
        )
        require(
            seed_runs["online"]["metrics"]["trained_numeric_sha256"]
            == seed_runs["oracle"]["metrics"]["trained_numeric_sha256"],
            "autonomous and replay-oracle learned fields differ",
        )
        require(
            seed_runs["frozen"]["metrics"]["trained_numeric_sha256"]
            == seed_runs["frozen"]["metrics"]["initial_numeric_sha256"],
            "frozen replay changed learned field",
        )

    report = {
        "schema": "cassifi.temporal-autonomous-learning.v1",
        "configuration": {
            "seeds": args.seeds,
            "decision_budget_per_segment": args.budget,
            "normal_bootstrap_episodes_per_arm": 6,
            "acquisition_segments_per_arm": ACQUISITION_EPISODES,
            "acquisition_mechanism": "jammed",
            "acquisition_horizon": ACQUISITION_HORIZON,
            "acquisition_actions": list(ACQUISITION_ACTIONS),
            "transfer_modes": [list(modes) for modes in TRANSFER_MODES],
            "transfer_admission_enabled": False,
            "arms": list(ARMS),
            "online_arm": "field selects each acquisition action; each bounded observed segment is admitted at its endpoint",
            "oracle_arm": "replays the exact online acquisition traces and admits each bounded segment",
            "frozen_control": "replays the exact online acquisition traces without admission",
            "scope": "closed-vocabulary simulator with supplied goals, reversible acquisition permissions, and reusable skill",
        },
        "runs": runs,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "limitations": [
            "Empirical categorical support is not calibrated probability.",
            "The action and observation vocabulary, goal, reusable skill, and reversible acquisition surface are supplied.",
            "Learning occurs at explicit bounded segment endpoints, not after every open-stream observation.",
            "The oracle and frozen controls replay the online field's actions rather than selecting their own acquisition curricula.",
            "The result concerns one controlled mechanism and two transfer arrangements, not broad generalization.",
            "Exactly-once external effects require an idempotent adapter; the simulator implements that contract.",
            "The seven-pool continuous wave law is unchanged.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
