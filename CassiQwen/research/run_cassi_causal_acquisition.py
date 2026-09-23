#!/usr/bin/env python3
"""Run randomized, closed-loop causal-acquisition worlds for the Qi field."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import struct
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import cassi_causal_event_field as _causal
from cassi_causal_event_field import CausalEventLearner, CausalProfile
from cassi_raw_event_field import (
    AcquisitionProfile,
    CapacityError,
    CheckpointError,
    atom_packet,
    canonical_packet,
    encode_packet,
)


SCHEMA = "cassi.causal-acquisition-campaign.v2"


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def same(left: bytes, right_hex: str | None) -> bool:
    return (
        right_hex is not None
        and canonical_packet(left) == canonical_packet(bytes.fromhex(right_hex))
    )


def randomized_symbols(seed: int, count: int) -> tuple[bytes, ...]:
    rng = random.Random(seed ^ 0xC4551)
    values = rng.sample(range(1, 256), count)
    return tuple(atom_packet(value) for value in values)


def high_capacity_profile(
    *,
    policy: str = "mismatch-gated",
    max_depth: int = 3,
    max_expansions: int = 64,
    key_channels: int = 8,
) -> CausalProfile:
    return CausalProfile(
        acquisition=AcquisitionProfile(
            wave_width=4096,
            payload_limit=8,
        ),
        policy=policy,
        key_channels=key_channels,
        max_depth=max_depth,
        max_expansions=max_expansions,
    )


def summarize_decision(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_sequence": receipt["event_sequence"],
        "episode_index": receipt["episode_index"],
        "decision_kind": receipt["decision_kind"],
        "field_owned": receipt["field_owned"],
        "reason": receipt["reason"],
        "observation_hex": receipt["observation_hex"],
        "history_hex": receipt["history_hex"],
        "goal_hex": receipt["goal_hex"],
        "candidate_order_sha256": receipt["candidate_order_sha256"],
        "action_hex": receipt["action_hex"],
        "plan_hex": receipt["plan_hex"],
        "route": receipt["route"],
        "actual_outcome_available_at_commit": receipt[
            "actual_outcome_available_at_commit"
        ],
        "pre_consequence_state_sha256": receipt[
            "pre_consequence_state_sha256"
        ],
    }


def summarize_outcome(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: receipt[key]
        for key in (
            "decision_event_sequence",
            "outcome_event_sequence",
            "decision_kind",
            "field_owned_decision",
            "actual_outcome_hex",
            "ordinary_prediction_correct",
            "conditional_prediction_correct",
            "effective_prediction_correct",
            "mismatch",
            "mismatch_source",
            "history_eligible",
            "mismatch_gate_passed",
            "admission_kind",
            "admission_scale",
            "learned",
            "promoted",
            "promotion_operation",
            "reason",
            "confirmation_from_new_reset_bounded_episode",
            "confirmation_episode_index",
            "provisional_witness_bank",
            "provisional_witness_state_sha256",
            "provisional_present_at_confirmation_episode_entry",
            "pre_consequence_state_sha256",
            "predecessor_state_sha256",
            "successor_state_sha256",
        )
    }


def expose(
    learner: CausalEventLearner,
    *,
    observation: bytes,
    action: bytes,
    outcome: bytes,
    history: bytes | None = None,
    learn: bool = True,
    allow_promotion: bool = True,
) -> dict[str, Any]:
    learner.reset()
    if history is not None:
        learner.observe(history, learn=False)
    learner.observe(observation, learn=False)
    decision = learner.decide((action,), outcome)
    require(decision["action_hex"] is not None, "fixed exposure did not commit its action")
    admission = learner.observe(
        outcome,
        learn=learn,
        allow_promotion=allow_promotion,
    )
    return {
        "decision": summarize_decision(decision),
        "admission": summarize_outcome(admission),
    }




def closed_loop_case(seed: int, episodes: int = 18) -> dict[str, Any]:
    started = time.perf_counter()
    start, goal, dead_a, dead_b, *actions = randomized_symbols(seed, 7)
    action_set = tuple(actions)
    canonical_actions = tuple(sorted(canonical_packet(action) for action in action_set))
    # The successful opaque action is randomized between the second and third
    # canonical probe positions, so no fresh field begins with a lucky success.
    offset = 1 + random.Random(seed ^ 0x0A11).randrange(2)
    successful_action = canonical_actions[offset]
    dead_iter = iter((dead_a, dead_b))
    outcomes: dict[bytes, bytes] = {}
    for action in canonical_actions:
        outcomes[action] = goal if action == successful_action else next(dead_iter)
    mechanics_hash = digest(
        {
            "start": start.hex(),
            "goal": goal.hex(),
            "action_outcomes": {
                action.hex(): outcomes[action].hex() for action in canonical_actions
            },
        }
    )

    def run_arm(learn: bool) -> dict[str, Any]:
        learner = CausalEventLearner()
        rows: list[dict[str, Any]] = []
        for episode in range(episodes):
            learner.reset()
            learner.observe(start, learn=False)
            presentation = list(action_set)
            random.Random((seed << 16) ^ episode).shuffle(presentation)
            before = learner.fingerprint()
            decision = learner.decide(tuple(presentation), goal)
            action_hex = decision["action_hex"]
            require(action_hex is not None, "closed-loop learner did not commit an action")
            action = canonical_packet(bytes.fromhex(action_hex))
            outcome = outcomes[action]
            admission = learner.observe(outcome, learn=learn)
            rows.append(
                {
                    "episode": episode,
                    "goal_completed": canonical_packet(outcome) == canonical_packet(goal),
                    "selected_action_hex": action.hex(),
                    "actual_outcome_hex": outcome.hex(),
                    "field_state_before_decision": before,
                    "field_state_after_decision": decision[
                        "pre_consequence_state_sha256"
                    ],
                    "field_state_after_outcome": learner.fingerprint(),
                    "decision_kind": decision["decision_kind"],
                    "field_owned": decision["field_owned"],
                    "prediction_correct": admission["effective_prediction_correct"],
                    "admission_kind": admission["admission_kind"],
                }
            )
        window = episodes // 3
        return {
            "learn": learn,
            "episodes": rows,
            "first_window_goal_rate": sum(
                row["goal_completed"] for row in rows[:window]
            ) / window,
            "last_window_goal_rate": sum(
                row["goal_completed"] for row in rows[-window:]
            ) / window,
            "overall_goal_rate": sum(row["goal_completed"] for row in rows)
            / episodes,
            "field_owned_decisions": sum(row["field_owned"] for row in rows),
            "field_mutations_during_decision": sum(
                row["field_state_before_decision"]
                != row["field_state_after_decision"]
                for row in rows
            ),
            "final_state_sha256": learner.fingerprint(),
            "all_finite": learner.snapshot()["field"]["all_finite"],
        }

    online = run_arm(True)
    frozen = run_arm(False)
    require(online["field_mutations_during_decision"] == 0, "decision mutated online field")
    require(frozen["field_mutations_during_decision"] == 0, "decision mutated frozen field")
    require(
        online["last_window_goal_rate"] > online["first_window_goal_rate"],
        "online field did not improve within the session",
    )
    require(
        online["last_window_goal_rate"] > frozen["last_window_goal_rate"],
        "online field did not outperform the matched frozen control late",
    )
    require(online["field_owned_decisions"] > 0, "online learner made no field-owned decisions")
    require(frozen["final_state_sha256"] == CausalEventLearner().fingerprint(), "frozen field changed")
    return {
        "seed": seed,
        "status": "PASS",
        "world_mechanics_sha256": mechanics_hash,
        "randomized_action_semantics": True,
        "successful_action_hex": successful_action.hex(),
        "online": online,
        "frozen": frozen,
        "late_goal_rate_delta": online["last_window_goal_rate"]
        - frozen["last_window_goal_rate"],
        "within_online_goal_rate_delta": online["last_window_goal_rate"]
        - online["first_window_goal_rate"],
        "elapsed_seconds": time.perf_counter() - started,
    }


def policy_comparison_case(seed: int) -> dict[str, Any]:
    started = time.perf_counter()
    history_a, history_b, history_c, history_d, observation, action, outcome_a, outcome_b = randomized_symbols(
        seed ^ 0xA011, 8
    )
    stream = [
        (history_a, outcome_a),
        (history_a, outcome_a),
        (history_b, outcome_b),
        (history_b, outcome_b),
        (history_a, outcome_a),
        (history_c, outcome_a),
        (history_d, outcome_a),
    ]
    arms: dict[str, Any] = {}
    for policy in ("mismatch-gated", "always-conditional", "unconditional-only"):
        learner = CausalEventLearner(high_capacity_profile(policy=policy))
        rows: list[dict[str, Any]] = []
        for index, (history, outcome) in enumerate(stream):
            row = expose(
                learner,
                observation=observation,
                action=action,
                outcome=outcome,
                history=history,
            )
            rows.append(
                {
                    "index": index,
                    "history_hex": history.hex(),
                    "outcome_hex": outcome.hex(),
                    "admission_kind": row["admission"]["admission_kind"],
                    "admission_scale": row["admission"]["admission_scale"],
                    "mismatch_gate_passed": row["admission"]["mismatch_gate_passed"],
                    "learned": row["admission"]["learned"],
                    "state_sha256": learner.fingerprint(),
                }
            )
        prediction_a = learner.predict(action, observation=observation, history=history_a)
        prediction_b = learner.predict(action, observation=observation, history=history_b)
        arms[policy] = {
            "rows": rows,
            "conditional_writes": sum(
                row["admission_scale"] in (2, 3) for row in rows
            ),
            "total_writes": sum(row["learned"] for row in rows),
            "branch_a_correct": same(
                outcome_a, prediction_a["effective"]["payload_hex"]
            ),
            "branch_b_correct": same(
                outcome_b, prediction_b["effective"]["payload_hex"]
            ),
            "branch_a": prediction_a["effective_branch"],
            "branch_b": prediction_b["effective_branch"],
            "scale_receipts": learner.snapshot()["scales"],
            "final_state_sha256": learner.fingerprint(),
        }
    gated = arms["mismatch-gated"]
    always = arms["always-conditional"]
    unconditional = arms["unconditional-only"]
    require(gated["branch_a_correct"] and gated["branch_b_correct"], "gated policy failed branching")
    require(always["branch_a_correct"] and always["branch_b_correct"], "always policy failed branching")
    require(
        gated["conditional_writes"] < always["conditional_writes"],
        "mismatch gate did not reduce conditional writes",
    )
    require(
        unconditional["conditional_writes"] == 0,
        "disabled conditional gate still changed conditional memory",
    )

    # A second identical event may confirm only when explicitly allowed.  With
    # promotion disabled, it cannot compound the first conditional write.
    exact_once = CausalEventLearner(high_capacity_profile())
    expose(
        exact_once,
        observation=observation,
        action=action,
        outcome=outcome_a,
        history=history_a,
    )
    expose(
        exact_once,
        observation=observation,
        action=action,
        outcome=outcome_a,
        history=history_a,
    )
    first_mismatch = expose(
        exact_once,
        observation=observation,
        action=action,
        outcome=outcome_b,
        history=history_b,
        allow_promotion=False,
    )
    after_first = exact_once.fingerprint()
    retry = expose(
        exact_once,
        observation=observation,
        action=action,
        outcome=outcome_b,
        history=history_b,
        allow_promotion=False,
    )
    require(first_mismatch["admission"]["admission_scale"] == 2, "first mismatch did not write once")
    require(not retry["admission"]["learned"], "identical retry compounded conditional memory")
    require(exact_once.fingerprint() == after_first, "identical retry changed the field")
    return {
        "seed": seed,
        "status": "PASS",
        "identical_exposure_sha256": digest(
            [(history.hex(), outcome.hex()) for history, outcome in stream]
        ),
        "arms": arms,
        "exact_once": {
            "first_admission": first_mismatch["admission"],
            "retry_admission": retry["admission"],
            "state_after_first_and_retry_sha256": after_first,
        },
        "elapsed_seconds": time.perf_counter() - started,
    }


def corrupted_pairing_case(seed: int) -> dict[str, Any]:
    started = time.perf_counter()
    observation, *rest = randomized_symbols(seed ^ 0xC077, 5)
    actions = tuple(rest[:2])
    outcomes = tuple(rest[2:])
    require(len(outcomes) == 2, "corrupted-pairing fixture is malformed")
    profile = CausalProfile(policy="unconditional-only")
    true_learner = CausalEventLearner(profile)
    corrupt_learner = CausalEventLearner(profile)
    rows: list[dict[str, Any]] = []
    for repeat in range(2):
        for index, action in enumerate(actions):
            true_outcome = outcomes[index]
            corrupt_outcome = outcomes[(index + 1) % len(outcomes)]
            true_row = expose(
                true_learner,
                observation=observation,
                action=action,
                outcome=true_outcome,
            )
            corrupt_row = expose(
                corrupt_learner,
                observation=observation,
                action=action,
                outcome=corrupt_outcome,
            )
            rows.append(
                {
                    "repeat": repeat,
                    "action_hex": action.hex(),
                    "true_outcome_hex": true_outcome.hex(),
                    "corrupt_outcome_hex": corrupt_outcome.hex(),
                    "true_admission": true_row["admission"]["admission_kind"],
                    "corrupt_admission": corrupt_row["admission"]["admission_kind"],
                }
            )
    true_predictions = [
        true_learner.predict(action, observation=observation, history=None)["effective"]
        for action in actions
    ]
    corrupt_predictions = [
        corrupt_learner.predict(action, observation=observation, history=None)["effective"]
        for action in actions
    ]
    true_accuracy = sum(
        same(outcome, prediction["payload_hex"])
        for outcome, prediction in zip(outcomes, true_predictions)
    ) / len(actions)
    corrupt_accuracy = sum(
        same(outcome, prediction["payload_hex"])
        for outcome, prediction in zip(outcomes, corrupt_predictions)
    ) / len(actions)
    require(true_accuracy == 1.0, "correctly paired replay did not recover all relations")
    require(corrupt_accuracy < true_accuracy, "corrupted pairing did not degrade original-world accuracy")
    return {
        "seed": seed,
        "status": "PASS",
        "rows": rows,
        "true_world_accuracy": true_accuracy,
        "corrupted_pairing_accuracy_against_true_world": corrupt_accuracy,
        "true_state_sha256": true_learner.fingerprint(),
        "corrupt_state_sha256": corrupt_learner.fingerprint(),
        "pairing_changed_only": True,
        "elapsed_seconds": time.perf_counter() - started,
    }


def collision_and_intervention_case(seed: int) -> dict[str, Any]:
    started = time.perf_counter()
    (
        history_a,
        history_b,
        history_c,
        observation,
        action_target,
        action_control,
        outcome_a,
        outcome_b,
        outcome_control_base,
        outcome_control_branch,
    ) = randomized_symbols(seed ^ 0xB1F0, 10)
    learner = CausalEventLearner(high_capacity_profile())
    for _ in range(2):
        expose(
            learner,
            observation=observation,
            action=action_target,
            outcome=outcome_a,
        )
    before_a = learner.predict(
        action_target, observation=observation, history=history_a
    )
    before_b = learner.predict(
        action_target, observation=observation, history=history_b
    )
    pre_split_collision = (
        same(outcome_a, before_a["effective"]["payload_hex"])
        and same(outcome_a, before_b["effective"]["payload_hex"])
    )
    branch_rows = [
        expose(
            learner,
            observation=observation,
            action=action_target,
            outcome=outcome_b,
            history=history_b,
        )
        for _ in range(2)
    ]
    # Separately acquire a comparably structured control relation.
    for _ in range(2):
        expose(
            learner,
            observation=observation,
            action=action_control,
            outcome=outcome_control_base,
        )
    for _ in range(2):
        expose(
            learner,
            observation=observation,
            action=action_control,
            outcome=outcome_control_branch,
            history=history_c,
        )
    after_a = learner.predict(
        action_target, observation=observation, history=history_a
    )
    after_b = learner.predict(
        action_target, observation=observation, history=history_b
    )
    require(pre_split_collision, "fixture did not begin with a field-representational collision")
    require(same(outcome_a, after_a["effective"]["payload_hex"]), "branch A was lost")
    require(same(outcome_b, after_b["effective"]["payload_hex"]), "branch B was not acquired")

    checkpoint = learner.checkpoint_bytes()
    target_cut, target_receipt = learner.intervene_relation(
        observation=observation,
        action=action_target,
        outcome=outcome_b,
        history=history_b,
        bank="conditional",
    )
    control_cut, control_receipt = learner.intervene_relation(
        observation=observation,
        action=action_control,
        outcome=outcome_control_branch,
        history=history_c,
        bank="conditional",
    )
    target_after_target_cut = target_cut.predict(
        action_target, observation=observation, history=history_b
    )
    branch_a_after_target_cut = target_cut.predict(
        action_target, observation=observation, history=history_a
    )
    target_after_control_cut = control_cut.predict(
        action_target, observation=observation, history=history_b
    )
    restored = CausalEventLearner.restore(checkpoint)
    restored_target = restored.predict(
        action_target, observation=observation, history=history_b
    )
    require(
        not same(outcome_b, target_after_target_cut["effective"]["payload_hex"]),
        "targeted relation intervention did not change the target decision",
    )
    require(
        same(outcome_a, branch_a_after_target_cut["effective"]["payload_hex"]),
        "targeted relation intervention damaged branch A",
    )
    require(
        same(outcome_b, target_after_control_cut["effective"]["payload_hex"]),
        "unrelated relation intervention collapsed the target decision",
    )
    require(restored.fingerprint() == learner.fingerprint(), "restored field identity differs")
    require(restored.checkpoint_bytes() == checkpoint, "restored execution checkpoint differs")
    require(same(outcome_b, restored_target["effective"]["payload_hex"]), "restoration lost target")
    return {
        "seed": seed,
        "status": "PASS",
        "pre_split_collision": pre_split_collision,
        "branch_admissions": [row["admission"] for row in branch_rows],
        "post_split": {
            "branch_a_correct": same(outcome_a, after_a["effective"]["payload_hex"]),
            "branch_b_correct": same(outcome_b, after_b["effective"]["payload_hex"]),
            "branch_a_effective_bank": after_a["effective_branch"],
            "branch_b_effective_bank": after_b["effective_branch"],
        },
        "target_intervention": {
            "receipt": target_receipt,
            "target_lost": not same(
                outcome_b, target_after_target_cut["effective"]["payload_hex"]
            ),
            "branch_a_retained": same(
                outcome_a, branch_a_after_target_cut["effective"]["payload_hex"]
            ),
        },
        "unrelated_intervention": {
            "receipt": control_receipt,
            "target_retained": same(
                outcome_b, target_after_control_cut["effective"]["payload_hex"]
            ),
        },
        "exact_restoration": {
            "field_identity": restored.fingerprint() == learner.fingerprint(),
            "execution_checkpoint_bytes": restored.checkpoint_bytes() == checkpoint,
            "decision_restored": same(
                outcome_b, restored_target["effective"]["payload_hex"]
            ),
        },
        "elapsed_seconds": time.perf_counter() - started,
    }


def composition_and_transfer_case(seed: int) -> dict[str, Any]:
    started = time.perf_counter()
    state_0, state_1, state_2, goal, action_0, action_1, action_2, alias_action = randomized_symbols(
        seed ^ 0xC0A0, 8
    )
    learner = CausalEventLearner(high_capacity_profile())
    relations = (
        (state_0, action_0, state_1),
        (state_1, action_1, state_2),
        (state_2, action_2, goal),
    )
    for observation, action, outcome in relations:
        for _ in range(2):
            expose(
                learner,
                observation=observation,
                action=action,
                outcome=outcome,
            )
    probe = learner.clone()
    probe.reset()
    probe.observe(state_0, learn=False)
    decision = probe.decide((action_2, action_0, action_1), goal)
    expected_plan = [
        canonical_packet(action_0).hex(),
        canonical_packet(action_1).hex(),
        canonical_packet(action_2).hex(),
    ]
    require(decision["plan_hex"] == expected_plan, "three-step field route was not composed")
    reordered = learner.clone()
    reordered.reset()
    reordered.observe(state_1, learn=False)
    reordered_decision = reordered.decide((action_2, action_0, action_1), goal)
    require(
        reordered_decision["plan_hex"] == expected_plan[1:],
        "withheld reordered subtask did not reuse the learned route",
    )

    entity_train = bytes([random.Random(seed ^ 0xE171).randrange(1, 256)])
    entity_held = bytes([random.Random(seed ^ 0xE172).randrange(1, 256)])
    while entity_held == entity_train:
        entity_held = bytes([(entity_held[0] % 255) + 1])
    cold = bytes([random.Random(seed ^ 0xE173).randrange(1, 256)])
    ready = bytes([random.Random(seed ^ 0xE174).randrange(1, 256)])
    done = bytes([random.Random(seed ^ 0xE175).randrange(1, 256)])
    while len({entity_train, entity_held, cold, ready, done}) < 5:
        done = bytes([(done[0] % 255) + 1])
    prep, finish = randomized_symbols(seed ^ 0xE176, 2)
    transfer = CausalEventLearner(
        high_capacity_profile(max_depth=2, max_expansions=32)
    )
    train_cold = encode_packet((entity_train, cold))
    train_ready = encode_packet((entity_train, ready))
    train_done = encode_packet((entity_train, done))
    held_cold = encode_packet((entity_held, cold))
    held_done = encode_packet((entity_held, done))
    for observation, action, outcome in (
        (train_cold, prep, train_ready),
        (train_ready, finish, train_done),
    ):
        for _ in range(2):
            expose(
                transfer,
                observation=observation,
                action=action,
                outcome=outcome,
            )
    transfer_probe = transfer.clone()
    transfer_probe.reset()
    transfer_probe.observe(held_cold, learn=False)
    transfer_decision = transfer_probe.decide((finish, prep), held_done)
    alias_prediction = transfer.predict(
        alias_action, observation=held_cold, history=None
    )
    require(
        transfer_decision["plan_hex"]
        == [canonical_packet(prep).hex(), canonical_packet(finish).hex()],
        "renamed entity did not receive the learned transformations",
    )
    require(
        alias_prediction["effective"]["status"] == "unresolved",
        "arbitrarily renamed action inherited unsupported semantics",
    )
    return {
        "seed": seed,
        "status": "PASS",
        "three_step_plan": summarize_decision(decision),
        "withheld_reordered_subtask": summarize_decision(reordered_decision),
        "renamed_entity_transfer": summarize_decision(transfer_decision),
        "renamed_action_without_grounding": alias_prediction["effective"],
        "fixed_operator": "single-changed-span-copy-binding",
        "elapsed_seconds": time.perf_counter() - started,
    }


def inquiry_case(seed: int) -> dict[str, Any]:
    started = time.perf_counter()
    (
        history_a,
        history_b,
        neutral,
        revealed_a,
        revealed_b,
        goal,
        inspect_action,
        fix_a,
        fix_b,
    ) = randomized_symbols(seed ^ 0x1A91, 9)
    learner = CausalEventLearner(
        high_capacity_profile(max_depth=2, max_expansions=32)
    )
    for _ in range(2):
        expose(
            learner,
            observation=neutral,
            action=inspect_action,
            outcome=revealed_a,
            history=history_a,
        )
    for _ in range(2):
        expose(
            learner,
            observation=neutral,
            action=inspect_action,
            outcome=revealed_b,
            history=history_b,
        )
    for observation, action in ((revealed_a, fix_a), (revealed_b, fix_b)):
        for _ in range(2):
            expose(
                learner,
                observation=observation,
                action=action,
                outcome=goal,
            )

    execution = learner.clone()
    execution.reset()
    execution.observe(history_b, learn=False)
    execution.observe(neutral, learn=False)
    first = execution.decide(
        (fix_a, inspect_action, fix_b),
        goal,
        inquiry_actions=(inspect_action,),
    )
    require(first["action_hex"] == canonical_packet(inspect_action).hex(), "field did not seek information")
    require(first["decision_kind"] == "field-supported-inquiry", "inquiry was not field-supported")
    execution.observe(revealed_b, learn=False)
    second = execution.decide((fix_a, inspect_action, fix_b), goal)
    require(second["action_hex"] == canonical_packet(fix_b).hex(), "revealed branch did not select its fix")
    execution.observe(goal, learn=False)

    no_inquiry = learner.clone()
    no_inquiry.reset()
    no_inquiry.observe(history_b, learn=False)
    no_inquiry.observe(neutral, learn=False)
    no_inquiry_decision = no_inquiry.decide((fix_a, fix_b), goal)
    require(not no_inquiry_decision["field_owned"], "non-inquiry actions unexpectedly solved hidden state")
    return {
        "seed": seed,
        "status": "PASS",
        "inquiry_decision": summarize_decision(first),
        "post_inquiry_decision": summarize_decision(second),
        "goal_completed": canonical_packet(execution.current_observation or b"")
        == canonical_packet(goal),
        "without_inquiry": summarize_decision(no_inquiry_decision),
        "field_state_unchanged_during_execution": (
            execution.fingerprint() == learner.fingerprint()
        ),
        "elapsed_seconds": time.perf_counter() - started,
    }


def continual_restart_capacity_case(seed: int) -> dict[str, Any]:
    started = time.perf_counter()
    packets = randomized_symbols(seed ^ 0xC017, 28)
    observations = packets[:8]
    actions = packets[8:16]
    outcomes = packets[16:24]
    change_history, corrected_outcome, pending_observation, pending_action = packets[24:]
    learner = CausalEventLearner(high_capacity_profile())
    retention_curve: list[dict[str, Any]] = []
    for index, (observation, action, outcome) in enumerate(
        zip(observations, actions, outcomes)
    ):
        for _ in range(2):
            expose(
                learner,
                observation=observation,
                action=action,
                outcome=outcome,
            )
        correct = sum(
            same(
                prior_outcome,
                learner.predict(
                    prior_action,
                    observation=prior_observation,
                    history=None,
                )["effective"]["payload_hex"],
            )
            for prior_observation, prior_action, prior_outcome in zip(
                observations[: index + 1],
                actions[: index + 1],
                outcomes[: index + 1],
            )
        )
        retention_curve.append(
            {
                "relations_acquired": index + 1,
                "relations_retained": correct,
                "state_sha256": learner.fingerprint(),
            }
        )
    require(
        retention_curve[-1]["relations_retained"] == len(observations),
        "continual acquisition lost a prior relation",
    )
    correction_first = expose(
        learner,
        observation=observations[0],
        action=actions[0],
        outcome=corrected_outcome,
        history=change_history,
    )
    correction_second = expose(
        learner,
        observation=observations[0],
        action=actions[0],
        outcome=corrected_outcome,
        history=change_history,
    )
    corrected = learner.predict(
        actions[0], observation=observations[0], history=change_history
    )
    original = learner.predict(actions[0], observation=observations[0], history=None)
    require(same(corrected_outcome, corrected["effective"]["payload_hex"]), "conditional correction failed")
    require(same(outcomes[0], original["effective"]["payload_hex"]), "correction erased baseline")
    require(
        all(
            same(
                outcome,
                learner.predict(action, observation=observation, history=None)[
                    "effective"
                ]["payload_hex"],
            )
            for observation, action, outcome in zip(
                observations[1:], actions[1:], outcomes[1:]
            )
        ),
        "conditional correction damaged unrelated memories",
    )

    # Stop exactly after committing an action, restore, then consume the same
    # consequence in both branches.  Protocol context and field must converge.
    pending_outcome = atom_packet((seed % 251) + 1)
    while pending_outcome in packets:
        pending_outcome = atom_packet((pending_outcome[-1] % 255) + 1)
    learner.reset()
    learner.observe(pending_observation, learn=False)
    pending_decision = learner.decide((pending_action,), pending_outcome)
    checkpoint = learner.checkpoint_bytes()
    uninterrupted = learner.clone()
    uninterrupted_receipt = uninterrupted.observe(pending_outcome)
    restored = CausalEventLearner.restore(
        checkpoint, expected_profile=learner.profile
    )
    restored_receipt = restored.observe(pending_outcome)
    require(
        uninterrupted.fingerprint() == restored.fingerprint(),
        "mid-action restart changed the learned successor",
    )
    require(
        uninterrupted_receipt["successor_state_sha256"]
        == restored_receipt["successor_state_sha256"],
        "mid-action outcome receipt diverged",
    )
    tampered = bytearray(checkpoint)
    tampered[-1] ^= 0x01
    payload_tamper_rejected = False
    try:
        CausalEventLearner.restore(tampered)
    except CheckpointError:
        payload_tamper_rejected = True
    require(payload_tamper_rejected, "tampered field payload was accepted")

    magic_size = len(_causal._CHECKPOINT_MAGIC)
    header_size = struct.unpack(
        ">Q", checkpoint[magic_size : magic_size + 8]
    )[0]
    header_start = magic_size + 8
    header_end = header_start + header_size
    header = json.loads(checkpoint[header_start:header_end])
    header["protocol_context_adaptive"] = True
    encoded_header = canonical(header)
    header_tampered = (
        checkpoint[:magic_size]
        + struct.pack(">Q", len(encoded_header))
        + encoded_header
        + checkpoint[header_end:]
    )
    header_tamper_rejected = False
    try:
        CausalEventLearner.restore(header_tampered)
    except CheckpointError:
        header_tamper_rejected = True
    require(header_tamper_rejected, "tampered causal header was accepted")

    profile_mismatch_rejected = False
    try:
        CausalEventLearner.restore(
            checkpoint,
            expected_profile=high_capacity_profile(
                policy="always-conditional"
            ),
        )
    except CheckpointError:
        profile_mismatch_rejected = True
    require(
        profile_mismatch_rejected,
        "checkpoint restored under a different expected policy",
    )

    mismatched_header = json.loads(checkpoint[header_start:header_end])
    mismatched_header["profile"]["acquisition"][
        "minimum_score"
    ] = 0.57
    mismatched_header["profile_sha256"] = digest(
        mismatched_header["profile"]
    )
    mismatched_header.pop("header_sha256")
    mismatched_header["header_sha256"] = digest(mismatched_header)
    encoded_mismatch = canonical(mismatched_header)
    cross_layer_mismatch = (
        checkpoint[:magic_size]
        + struct.pack(">Q", len(encoded_mismatch))
        + encoded_mismatch
        + checkpoint[header_end:]
    )
    cross_layer_profile_mismatch_rejected = False
    try:
        CausalEventLearner.restore(cross_layer_mismatch)
    except CheckpointError:
        cross_layer_profile_mismatch_rejected = True
    require(
        cross_layer_profile_mismatch_rejected,
        "causal header profile diverged from raw-field profile",
    )

    inference_start = uninterrupted.fingerprint()
    for index in range(256):
        relation = index % len(observations)
        prediction = uninterrupted.predict(
            actions[relation], observation=observations[relation], history=None
        )
        require(
            same(outcomes[relation], prediction["effective"]["payload_hex"]),
            "long-horizon inference lost an acquired relation",
        )
    require(uninterrupted.fingerprint() == inference_start, "inference horizon mutated field")

    constrained_profile = CausalProfile(
        acquisition=AcquisitionProfile(energy_limit=1.0e-9)
    )
    constrained = CausalEventLearner(constrained_profile)
    constrained.reset()
    constrained.observe(observations[0], learn=False)
    constrained.decide((actions[0],), outcomes[0])
    predecessor = constrained.fingerprint()
    predecessor_checkpoint = constrained.checkpoint_bytes()
    capacity_rejected = False
    try:
        constrained.observe(outcomes[0])
    except CapacityError:
        capacity_rejected = True
    require(capacity_rejected, "bounded field did not reject over-capacity admission")
    require(constrained.fingerprint() == predecessor, "capacity rejection changed predecessor field")
    require(
        constrained.checkpoint_bytes() == predecessor_checkpoint,
        "capacity rejection changed checkpointed process state",
    )
    return {
        "seed": seed,
        "status": "PASS",
        "retention_curve": retention_curve,
        "correction": {
            "first": correction_first["admission"],
            "confirmation": correction_second["admission"],
            "corrected_branch": corrected["effective"],
            "original_branch": original["effective"],
        },
        "restart": {
            "pending_decision": summarize_decision(pending_decision),
            "checkpoint_sha256": hashlib.sha256(checkpoint).hexdigest(),
            "checkpoint_bytes": len(checkpoint),
            "restored_before_outcome_identical": (
                CausalEventLearner.restore(
                    checkpoint, expected_profile=learner.profile
                ).checkpoint_bytes()
                == checkpoint
            ),
            "successor_identical": uninterrupted.fingerprint()
            == restored.fingerprint(),
            "payload_tamper_rejected": payload_tamper_rejected,
            "header_tamper_rejected": header_tamper_rejected,
            "profile_mismatch_rejected": profile_mismatch_rejected,
            "cross_layer_profile_mismatch_rejected": (
                cross_layer_profile_mismatch_rejected
            ),
            "tamper_rejected": (
                payload_tamper_rejected
                and header_tamper_rejected
                and cross_layer_profile_mismatch_rejected
            ),
        },
        "inference_queries": 256,
        "inference_preserved_state": uninterrupted.fingerprint() == inference_start,
        "capacity": {
            "rejected": capacity_rejected,
            "predecessor_preserved": constrained.fingerprint() == predecessor,
            "pending_action_retained_for_explicit_recovery": constrained.pending,
            "checkpoint_atomic": (
                constrained.checkpoint_bytes() == predecessor_checkpoint
            ),
        },
        "snapshot": uninterrupted.snapshot(),
        "elapsed_seconds": time.perf_counter() - started,
    }


def capacity_profile_sweep(seed_values: Sequence[int]) -> dict[str, Any]:
    """Calibrate fixed field geometry against continual relation retention."""

    started = time.perf_counter()
    relation_count = 12
    configurations = (
        ("narrow-512-c2", 512, 2),
        ("medium-1024-c4", 1024, 4),
        ("wide-2048-c8", 2048, 8),
        ("selected-4096-c8", 4096, 8),
    )
    profiles: list[dict[str, Any]] = []
    for name, wave_width, key_channels in configurations:
        profile_started = time.perf_counter()
        profile = CausalProfile(
            acquisition=AcquisitionProfile(
                wave_width=wave_width,
                payload_limit=8,
            ),
            key_channels=key_channels,
        )
        all_steps_seed_count = 0
        final_exact = 0
        final_unresolved = 0
        final_wrong_supported = 0
        loss_checks = 0
        failed_seeds: list[int] = []
        correct_scores: list[float] = []
        correct_margins: list[float] = []
        maximum_field_coordinate = 0.0
        for seed in seed_values:
            symbols = randomized_symbols(seed ^ 0xBADA, relation_count * 3)
            observations = symbols[:relation_count]
            actions = symbols[relation_count : relation_count * 2]
            outcomes = symbols[relation_count * 2 :]
            learner = CausalEventLearner(profile)
            seed_retained_every_step = True
            for acquired, (observation, action, outcome) in enumerate(
                zip(observations, actions, outcomes),
                start=1,
            ):
                expose(
                    learner,
                    observation=observation,
                    action=action,
                    outcome=outcome,
                )
                expose(
                    learner,
                    observation=observation,
                    action=action,
                    outcome=outcome,
                )
                for prior in range(acquired):
                    prediction = learner.predict(
                        actions[prior],
                        observation=observations[prior],
                        history=None,
                    )["effective"]
                    if not same(outcomes[prior], prediction["payload_hex"]):
                        seed_retained_every_step = False
                        loss_checks += 1
            if seed_retained_every_step:
                all_steps_seed_count += 1
            else:
                failed_seeds.append(seed)
            for observation, action, outcome in zip(
                observations, actions, outcomes
            ):
                prediction = learner.predict(
                    action, observation=observation, history=None
                )["effective"]
                if same(outcome, prediction["payload_hex"]):
                    final_exact += 1
                    correct_scores.append(float(prediction["score"]))
                    correct_margins.append(float(prediction["margin"]))
                elif prediction["status"] == "unresolved":
                    final_unresolved += 1
                else:
                    final_wrong_supported += 1
            maximum_field_coordinate = max(
                maximum_field_coordinate,
                float(learner.snapshot()["field"]["max_abs"]),
            )
            require(
                bool(learner.snapshot()["field"]["all_finite"]),
                "capacity sweep produced a non-finite field",
            )
        selected = name == "selected-4096-c8"
        row = {
            "name": name,
            "selected": selected,
            "wave_width": wave_width,
            "mode_count": profile.acquisition.mode_count,
            "key_channels": key_channels,
            "field_bytes": (
                4
                * 9
                * profile.acquisition.mode_count
                * 8
            ),
            "relations_per_seed": relation_count,
            "all_steps_seed_count": all_steps_seed_count,
            "seed_count": len(seed_values),
            "loss_checks": loss_checks,
            "final_exact": final_exact,
            "final_total": len(seed_values) * relation_count,
            "final_unresolved": final_unresolved,
            "final_wrong_supported": final_wrong_supported,
            "minimum_correct_score": (
                min(correct_scores) if correct_scores else None
            ),
            "minimum_correct_margin": (
                min(correct_margins) if correct_margins else None
            ),
            "maximum_field_coordinate": maximum_field_coordinate,
            "failed_seeds": failed_seeds,
            "profile_sha256": profile.fingerprint,
            "elapsed_seconds": time.perf_counter() - profile_started,
        }
        profiles.append(row)
        if selected:
            require(
                all_steps_seed_count == len(seed_values),
                "selected capacity profile lost a relation during acquisition",
            )
            require(
                final_exact == len(seed_values) * relation_count,
                "selected capacity profile lost a final relation",
            )
            require(
                final_wrong_supported == 0,
                "selected capacity profile emitted a wrong supported relation",
            )
    return {
        "schema": "cassi.causal-capacity-profile-sweep.v1",
        "status": "PASS",
        "seed_count": len(seed_values),
        "relation_count": relation_count,
        "selected_profile": "selected-4096-c8",
        "profiles": profiles,
        "elapsed_seconds": time.perf_counter() - started,
    }


def run(seed_values: Sequence[int], output: Path) -> dict[str, Any]:
    started = time.perf_counter()
    cases: list[dict[str, Any]] = []
    for seed in seed_values:
        cases.append(
            {
                "seed": seed,
                "closed_loop": closed_loop_case(seed),
                "policy_comparison": policy_comparison_case(seed),
                "corrupted_pairing": corrupted_pairing_case(seed),
                "collision_intervention": collision_and_intervention_case(seed),
                "composition_transfer": composition_and_transfer_case(seed),
                "inquiry": inquiry_case(seed),
                "continual_restart_capacity": continual_restart_capacity_case(seed),
            }
        )
    capacity_sweep = capacity_profile_sweep(seed_values)
    selected_capacity = next(
        row for row in capacity_sweep["profiles"] if row["selected"]
    )
    sources = {
        name: file_sha256(Path(__file__).with_name(name))
        for name in (
            "cassi_causal_event_field.py",
            "cassi_raw_event_field.py",
            "run_cassi_causal_acquisition.py",
            "test_cassi_causal_acquisition.py",
        )
    }
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "PASS",
        "seeds": list(seed_values),
        "profiles": {
            "default": CausalProfile().as_dict(),
            "high_capacity": high_capacity_profile().as_dict(),
        },
        "profile_sha256": {
            "default": CausalProfile().fingerprint,
            "high_capacity": high_capacity_profile().fingerprint,
        },
        "sources": sources,
        "cases": cases,
        "capacity_profile_sweep": capacity_sweep,
        "aggregate": {
            "closed_loop_passed": sum(
                row["closed_loop"]["status"] == "PASS" for row in cases
            ),
            "policy_comparisons_passed": sum(
                row["policy_comparison"]["status"] == "PASS" for row in cases
            ),
            "corrupted_pairing_controls_passed": sum(
                row["corrupted_pairing"]["status"] == "PASS" for row in cases
            ),
            "collision_interventions_passed": sum(
                row["collision_intervention"]["status"] == "PASS" for row in cases
            ),
            "composition_transfer_passed": sum(
                row["composition_transfer"]["status"] == "PASS" for row in cases
            ),
            "inquiry_passed": sum(
                row["inquiry"]["status"] == "PASS" for row in cases
            ),
            "continual_restart_capacity_passed": sum(
                row["continual_restart_capacity"]["status"] == "PASS"
                for row in cases
            ),
            "selected_capacity_all_steps_seeds": selected_capacity[
                "all_steps_seed_count"
            ],
            "selected_capacity_final_exact": selected_capacity["final_exact"],
            "mean_online_late_goal_rate": sum(
                row["closed_loop"]["online"]["last_window_goal_rate"]
                for row in cases
            )
            / len(cases),
            "mean_online_early_goal_rate": sum(
                row["closed_loop"]["online"]["first_window_goal_rate"]
                for row in cases
            )
            / len(cases),
            "mean_frozen_late_goal_rate": sum(
                row["closed_loop"]["frozen"]["last_window_goal_rate"]
                for row in cases
            )
            / len(cases),
            "field_owned_closed_loop_decisions": sum(
                row["closed_loop"]["online"]["field_owned_decisions"]
                for row in cases
            ),
            "all_states_finite": all(
                row["closed_loop"]["online"]["all_finite"]
                and row["continual_restart_capacity"]["snapshot"]["field"][
                    "all_finite"
                ]
                for row in cases
            ),
        },
        "ownership": {
            "adaptive_state": "QiFieldState.field [S,9M,B] only",
            "field_owned_decisions": "supported bounded route first actions",
            "field_owned_updates": "ordinary/conditional provisional and consolidated relation waves",
            "field_owned_closed_loop_decision_count": sum(
                row["closed_loop"]["online"]["field_owned_decisions"]
                for row in cases
            ),
            "adaptive_field_bytes_per_selected_learner": selected_capacity[
                "field_bytes"
            ],
            "measured_relations_retained_per_selected_field": selected_capacity[
                "relations_per_seed"
            ],
            "fixed_machinery": [
                "opaque packet framing",
                "fixed Qi chirp codebook",
                "fixed keyed sparse relation mask",
                "single-changed-span copy binding",
                "bounded breadth-first route search",
                "canonical episode-rotated exploration",
                "exact packet comparison",
                "checkpoint protocol framing",
            ],
            "learned_sidecars": 0,
            "transition_tables_in_learner": 0,
            "action_value_tables_in_learner": 0,
            "qwen_calls": 0,
            "teacher_calls": 0,
            "native_state_bytes_removed": 0,
            "native_ops_skipped": 0,
            "native_layers_skipped": 0,
            "native_output_rows_skipped": 0,
            "qwen_weight_bytes_touched_per_token": 0,
            "native_displacement_claim": "none; isolated field laboratory",
        },
        "limitations": [
            "The field starts with a fixed single-changed-span copy-binding operator; it does not invent arbitrary operators.",
            "Packets contain at most three spans of at most eight bytes each and at most sixteen encoded bytes total.",
            "The selected 2,359,296-byte field retained twelve ordinary relations in this campaign; this is a measured bound, not an open-ended capacity claim.",
            "Route search is bounded by profile depth, expansion, and action limits.",
            "One immediately preceding reset-bounded observation is eligible conditional context; arbitrary history selection is not learned.",
            "Exploration is fixed canonical episode rotation rather than a learned information-value policy.",
            "The experiment establishes bounded causal acquisition over opaque packets, not open-vocabulary language understanding.",
            "No native Qwen resource is displaced by this isolated field experiment.",
        ],
        "elapsed_seconds": time.perf_counter() - started,
    }
    receipt["self_sha256"] = digest(receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("_diag/causal-acquisition/verification.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = run(tuple(args.seeds), args.output)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
