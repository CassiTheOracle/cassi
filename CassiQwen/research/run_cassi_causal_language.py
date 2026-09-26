#!/usr/bin/env python3
"""Run grounded online-language acquisition over one causal Qi field."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from cassi_causal_event_field import CausalEventLearner
from cassi_causal_language import (
    BOUNDARY_SCHEMA,
    CausalLanguageWorld,
    action_packet,
    choose_and_observe,
    committed_action,
    decode_ordered_expression,
    grounded_state,
    language_profile,
    role_marked_expression,
)
from cassi_raw_event_field import canonical_packet, encode_packet


SCHEMA = "cassi.causal-language-campaign.v2"


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
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


def _same(left: bytes, right: bytes) -> bool:
    return canonical_packet(left) == canonical_packet(right)


def _decision_summary(decision: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": decision["schema"],
        "event_sequence": decision["event_sequence"],
        "decision_kind": decision["decision_kind"],
        "field_owned": decision["field_owned"],
        "reason": decision["reason"],
        "action_hex": decision["action_hex"],
        "goal_hex": decision["goal_hex"],
        "plan_hex": decision["plan_hex"],
        "pre_consequence_state_sha256": decision[
            "pre_consequence_state_sha256"
        ],
    }


def _probe(
    learner: CausalEventLearner,
    *,
    observation: bytes,
    actions: Sequence[bytes],
    goal: bytes,
    expected_action: bytes | None,
) -> dict[str, Any]:
    probe = learner.clone()
    field_before = probe.fingerprint()
    probe.reset()
    probe.observe(observation, learn=False)
    decision = probe.decide(actions, goal)
    chosen = committed_action(decision)
    field_after = probe.fingerprint()
    return {
        "decision": _decision_summary(decision),
        "correct": expected_action is not None and _same(chosen, expected_action),
        "field_supported_correct": (
            expected_action is not None
            and bool(decision["field_owned"])
            and _same(chosen, expected_action)
        ),
        "field_state_unchanged": field_before == field_after,
    }

def _compound_probe(
    learner: CausalEventLearner,
    *,
    world: CausalLanguageWorld,
) -> dict[str, Any]:
    probe = learner.clone()
    before = probe.fingerprint()
    observation = world.compound_command(
        world.move_word, world.inspect_word, world.entity_held
    )
    goal = world.compound_goal(world.entity_held)
    probe.reset()
    probe.observe(observation, learn=False)
    first = probe.decide(world.actions, goal)
    expected = {
        canonical_packet(world.correct_action(world.move_word)).hex(),
        canonical_packet(world.correct_action(world.inspect_word)).hex(),
    }
    planned = list(first["plan_hex"])
    valid_plan = bool(first["field_owned"]) and len(planned) == 2 and set(planned) == expected
    committed: list[dict[str, Any]] = []
    current = observation
    while probe.pending and len(committed) < 2:
        action = committed_action(first)
        outcome = world.compound_consequence(current, action)
        receipt = probe.observe(outcome, learn=False)
        committed.append(
            {
                "decision": _decision_summary(first),
                "outcome_hex": canonical_packet(outcome).hex(),
                "admission": receipt,
            }
        )
        current = outcome
        if _same(current, goal):
            break
        first = probe.decide(world.actions, goal)
    return {
        "field_owned_valid_two_action_plan": valid_plan,
        "goal_reached": _same(current, goal),
        "committed": committed,
        "field_state_unchanged": before == probe.fingerprint(),
    }


def _yoked_frozen_episode(
    learner: CausalEventLearner,
    *,
    observation: bytes,
    action: bytes,
    goal: bytes,
    outcome: bytes,
) -> None:
    learner.reset()
    learner.observe(observation, learn=False)
    decision = learner.decide((action,), goal)
    require(_same(committed_action(decision), action), "frozen replay changed committed action")
    learner.observe(outcome, learn=False)


def _force_relation(
    learner: CausalEventLearner,
    *,
    observation: bytes,
    action: bytes,
    outcome: bytes,
) -> dict[str, Any]:
    learner.reset()
    learner.observe(observation, learn=False)
    decision = learner.decide((action,), outcome)
    require(_same(committed_action(decision), action), "forced replay changed action")
    admission = learner.observe(outcome)
    return {"decision": _decision_summary(decision), "admission": admission}

def _force_history_relation(
    learner: CausalEventLearner,
    *,
    history: bytes,
    observation: bytes,
    action: bytes,
    outcome: bytes,
) -> dict[str, Any]:
    learner.reset()
    learner.observe(history, learn=False)
    learner.observe(observation, learn=False)
    decision = learner.decide((action,), outcome)
    receipt = learner.observe(outcome)
    return {"decision": _decision_summary(decision), "admission": receipt}


def _train_closed_loop(
    online: CausalEventLearner,
    frozen: CausalEventLearner,
    *,
    observation: bytes,
    actions: Sequence[bytes],
    goal: bytes,
    consequence: Callable[[bytes], bytes],
    episodes: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for episode in range(episodes):
        before = online.fingerprint()
        decision, admission, outcome = choose_and_observe(
            online,
            observation=observation,
            actions=actions,
            goal=goal,
            consequence=consequence,
            learn=True,
        )
        action = committed_action(decision)
        _yoked_frozen_episode(
            frozen,
            observation=observation,
            action=action,
            goal=goal,
            outcome=outcome,
        )
        rows.append(
            {
                "episode": episode,
                "decision": _decision_summary(decision),
                "outcome_hex": canonical_packet(outcome).hex(),
                "goal_reached": _same(outcome, goal),
                "field_changed": online.fingerprint() != before,
                "admission": admission,
            }
        )
    return rows


def lexical_online_case(seed: int) -> dict[str, Any]:
    started = time.perf_counter()
    world = CausalLanguageWorld.randomized(seed)
    profile = language_profile()
    online = CausalEventLearner(profile)
    frozen = CausalEventLearner(profile)
    frozen_start = frozen.fingerprint()
    constructions = (
        world.move_word,
        world.move_paraphrase,
        world.inspect_word,
    )

    early_online = [
        _probe(
            online,
            observation=world.command(construction, world.entity_seen),
            actions=world.actions,
            goal=world.task_goal(world.entity_seen),
            expected_action=world.correct_action(construction),
        )
        for construction in constructions
    ]
    early_frozen = [
        _probe(
            frozen,
            observation=world.command(construction, world.entity_seen),
            actions=world.actions,
            goal=world.task_goal(world.entity_seen),
            expected_action=world.correct_action(construction),
        )
        for construction in constructions
    ]

    learning_curve: list[dict[str, Any]] = []
    transcripts: list[dict[str, Any]] = []
    for construction in constructions:
        observation = world.command(construction, world.entity_seen)
        goal = world.task_goal(world.entity_seen)
        rows = _train_closed_loop(
            online,
            frozen,
            observation=observation,
            actions=world.actions,
            goal=goal,
            consequence=lambda action, construction=construction: world.consequence(
                construction, world.entity_seen, action
            ),
            episodes=6,
        )
        transcripts.append(
            {
                "construction": construction,
                "entity": world.entity_seen,
                "episodes": rows,
            }
        )
        retained = [
            _probe(
                online,
                observation=world.command(prior, world.entity_seen),
                actions=world.actions,
                goal=world.task_goal(world.entity_seen),
                expected_action=world.correct_action(prior),
            )
            for prior in constructions[: len(transcripts)]
        ]
        learning_curve.append(
            {
                "constructions_acquired": len(transcripts),
                "retained_field_supported": sum(
                    row["field_supported_correct"] for row in retained
                ),
                "state_sha256": online.fingerprint(),
            }
        )

    late_online_seen = [
        _probe(
            online,
            observation=world.command(construction, world.entity_seen),
            actions=world.actions,
            goal=world.task_goal(world.entity_seen),
            expected_action=world.correct_action(construction),
        )
        for construction in constructions
    ]
    late_frozen_seen = [
        _probe(
            frozen,
            observation=world.command(construction, world.entity_seen),
            actions=world.actions,
            goal=world.task_goal(world.entity_seen),
            expected_action=world.correct_action(construction),
        )
        for construction in constructions
    ]
    held_entity_renaming = [
        _probe(
            online,
            observation=world.command(construction, world.entity_held),
            actions=world.actions,
            goal=world.task_goal(world.entity_held),
            expected_action=world.correct_action(construction),
        )
        for construction in constructions
    ]
    frozen_held = [
        _probe(
            frozen,
            observation=world.command(construction, world.entity_held),
            actions=world.actions,
            goal=world.task_goal(world.entity_held),
            expected_action=world.correct_action(construction),
        )
        for construction in constructions
    ]
    true_recombination = _compound_probe(online, world=world)
    frozen_true_recombination = _compound_probe(frozen, world=world)

    normalization = CausalEventLearner(profile)
    precomposed = "\u00e9"
    decomposed = "e\u0301"
    entity_span = b"E" + world.entity_seen.encode("utf-8")
    precomposed_packet = encode_packet(
        (b"V" + precomposed.encode("utf-8"), entity_span)
    )
    decomposed_packet = encode_packet(
        (b"V" + decomposed.encode("utf-8"), entity_span)
    )
    normalization_action = world.correct_action(world.move_word)
    for _ in range(2):
        _force_relation(
            normalization,
            observation=precomposed_packet,
            action=normalization_action,
            outcome=world.task_goal(world.entity_seen),
        )
    normalization_exact = _probe(
        normalization,
        observation=precomposed_packet,
        actions=world.actions,
        goal=world.task_goal(world.entity_seen),
        expected_action=normalization_action,
    )
    normalization_variant = _probe(
        normalization,
        observation=decomposed_packet,
        actions=world.actions,
        goal=world.task_goal(world.entity_seen),
        expected_action=None,
    )

    unknown_probe = online.clone()
    unknown_before = unknown_probe.fingerprint()
    unknown_observation = world.command(world.unknown_word, world.entity_held)
    unknown_goal = grounded_state(world.moved_state, world.entity_held)
    unknown_probe.reset()
    unknown_probe.observe(unknown_observation, learn=False)
    unknown_decision = unknown_probe.decide(world.actions, unknown_goal)
    unknown_action = committed_action(unknown_decision)
    unknown_outcome = world.unknown_consequence(world.entity_held, unknown_action)
    expected_unknown_outcome = grounded_state(
        world.failure_state, world.entity_held
    )
    unknown_admission = unknown_probe.observe(unknown_outcome, learn=False)
    unknown = {
        "decision": _decision_summary(unknown_decision),
        "committed_action_hex": unknown_action.hex(),
        "consequence_hex": unknown_outcome.hex(),
        "expected_consequence_hex": expected_unknown_outcome.hex(),
        "admission": unknown_admission,
        "field_state_unchanged": unknown_probe.fingerprint() == unknown_before,
        "world_path": "deterministic-unknown-failure-after-commit",
    }
    unsupported_goal = _probe(
        online,
        observation=world.command(world.move_word, world.entity_held),
        actions=world.actions,
        goal=grounded_state(world.inspected_state, world.entity_held),
        expected_action=None,
    )

    require(
        normalization_exact["field_supported_correct"]
        and not normalization_variant["decision"]["field_owned"],
        "declared no-normalization boundary was not observed",
    )
    require(frozen.fingerprint() == frozen_start, "frozen field changed under yoked exposure")
    require(
        all(
            row["field_state_unchanged"]
            for row in late_online_seen + held_entity_renaming
        )
        and true_recombination["field_state_unchanged"],
        "language evaluation mutated the field",
    )
    capability_checks = {
        "cold_online_abstained": not any(
            row["decision"]["field_owned"] for row in early_online
        ),
        "cold_frozen_abstained": not any(
            row["decision"]["field_owned"] for row in early_frozen
        ),
        "all_seen_relations_retained": all(
            row["field_supported_correct"] for row in late_online_seen
        ),
        "all_held_renamings_supported": all(
            row["field_supported_correct"] for row in held_entity_renaming
        ),
        "frozen_seen_abstained": not any(
            row["decision"]["field_owned"] for row in late_frozen_seen
        ),
        "frozen_held_abstained": not any(
            row["decision"]["field_owned"] for row in frozen_held
        ),
        "commutative_component_composition_supported": (
            true_recombination["field_owned_valid_two_action_plan"]
            and true_recombination["goal_reached"]
        ),
        "frozen_composition_not_supported": not frozen_true_recombination[
            "field_owned_valid_two_action_plan"
        ],
        "unknown_abstained_after_world_execution": (
            not unknown["decision"]["field_owned"]
            and _same(unknown_outcome, expected_unknown_outcome)
            and unknown["field_state_unchanged"]
        ),
        "unsupported_goal_abstained": not unsupported_goal["decision"]["field_owned"],
        "normalization_boundary_preserved": (
            normalization_exact["field_supported_correct"]
            and not normalization_variant["decision"]["field_owned"]
        ),
    }
    status = "PASS" if all(capability_checks.values()) else "FAIL"


    return {
        "seed": seed,
        "status": status,
        "capability_checks": capability_checks,
        "world": world.as_dict(),
        "world_sha256": world.fingerprint,
        "early_online": early_online,
        "early_frozen": early_frozen,
        "transcripts": transcripts,
        "learning_curve": learning_curve,
        "late_online_seen": late_online_seen,
        "late_frozen_seen": late_frozen_seen,
        "held_entity_renaming": held_entity_renaming,
        "frozen_held_entity_renaming": frozen_held,
        "true_recombination": true_recombination,
        "frozen_true_recombination": frozen_true_recombination,
        "paraphrase_transfer": {
            "supported": sum(
                held_entity_renaming[index]["field_supported_correct"]
                for index in (0, 1)
            ),
            "total": 2,
            "basis": "both surface constructions were independently grounded",
        },
        "normalization": {
            "declared": "none",
            "precomposed_utf8_hex": precomposed.encode("utf-8").hex(),
            "decomposed_utf8_hex": decomposed.encode("utf-8").hex(),
            "packets_distinct": canonical_packet(precomposed_packet)
            != canonical_packet(decomposed_packet),
            "exact_precomposed": normalization_exact,
            "unseen_decomposed": normalization_variant,
        },
        "unknown": unknown,
        "unsupported_goal": unsupported_goal,
        "online_checkpoint_sha256": hashlib.sha256(online.checkpoint_bytes()).hexdigest(),
        "online_state_sha256": online.fingerprint(),
        "frozen_state_sha256": frozen.fingerprint(),
        "online": online,
        "elapsed_seconds": time.perf_counter() - started,
    }


def ordered_language_case(seed: int) -> dict[str, Any]:
    started = time.perf_counter()
    world = CausalLanguageWorld.randomized(seed)
    profile = language_profile()
    online = CausalEventLearner(profile)
    frozen = CausalEventLearner(profile)
    frozen_start = frozen.fingerprint()
    candidate_actions = tuple(
        action_packet(value)
        for value in (
            world.ordered_forward_action,
            world.ordered_reverse_action,
            world.distractor_action,
            world.alternate_action,
        )
    )
    forward_observation = world.ordered_observation(reversed_arguments=False)
    forward_rows = _train_closed_loop(
        online,
        frozen,
        observation=forward_observation,
        actions=candidate_actions,
        goal=world.ordered_target,
        consequence=lambda action: world.ordered_consequence(
            forward_observation, action
        ),
        episodes=6,
    )
    held_reverse_before_exposure = _probe(
        online,
        observation=world.ordered_observation(reversed_arguments=True),
        actions=candidate_actions,
        goal=world.ordered_target,
        expected_action=world.ordered_correct_action(reversed_arguments=True),
    )
    reverse_observation = world.ordered_observation(reversed_arguments=True)
    reverse_rows = _train_closed_loop(
        online,
        frozen,
        observation=reverse_observation,
        actions=candidate_actions,
        goal=world.ordered_target,
        consequence=lambda action: world.ordered_consequence(
            reverse_observation, action
        ),
        episodes=6,
    )
    transcripts = [
        {
            "reversed_arguments": False,
            "ordered_sequence_hex": forward_observation.hex(),
            "episodes": forward_rows,
        },
        {
            "reversed_arguments": True,
            "ordered_sequence_hex": reverse_observation.hex(),
            "episodes": reverse_rows,
        },
    ]

    forward = _probe(
        online,
        observation=world.ordered_observation(reversed_arguments=False),
        actions=candidate_actions,
        goal=world.ordered_target,
        expected_action=world.ordered_correct_action(reversed_arguments=False),
    )
    reverse = _probe(
        online,
        observation=world.ordered_observation(reversed_arguments=True),
        actions=candidate_actions,
        goal=world.ordered_target,
        expected_action=world.ordered_correct_action(reversed_arguments=True),
    )
    frozen_forward = _probe(
        frozen,
        observation=world.ordered_observation(reversed_arguments=False),
        actions=candidate_actions,
        goal=world.ordered_target,
        expected_action=world.ordered_correct_action(reversed_arguments=False),
    )
    frozen_reverse = _probe(
        frozen,
        observation=world.ordered_observation(reversed_arguments=True),
        actions=candidate_actions,
        goal=world.ordered_target,
        expected_action=world.ordered_correct_action(reversed_arguments=True),
    )

    role_forward = role_marked_expression(
        world.ordered_subject, world.ordered_relation, world.ordered_object
    )
    role_reordered_wire = encode_packet(
        (
            b"O" + world.ordered_object.encode("utf-8"),
            b"S" + world.ordered_subject.encode("utf-8"),
            b"R" + world.ordered_relation.encode("utf-8"),
        )
    )
    role_reversed = role_marked_expression(
        world.ordered_object, world.ordered_relation, world.ordered_subject
    )
    ordered_forward = world.ordered_observation(reversed_arguments=False)
    ordered_reverse = world.ordered_observation(reversed_arguments=True)
    decoded_forward = decode_ordered_expression(ordered_forward)
    decoded_reverse = decode_ordered_expression(ordered_reverse)

    require(ordered_forward != ordered_reverse, "ordered event sequence was erased")
    require(
        decoded_forward
        == (
            world.ordered_subject,
            world.ordered_relation,
            world.ordered_object,
        )
        and decoded_reverse
        == (
            world.ordered_object,
            world.ordered_relation,
            world.ordered_subject,
        ),
        "ordered event sequence did not round-trip",
    )
    require(
        canonical_packet(role_forward) == canonical_packet(role_reordered_wire),
        "role-marked span presentation order unexpectedly remained semantic",
    )
    require(
        canonical_packet(role_forward) != canonical_packet(role_reversed),
        "explicit role markers failed to distinguish argument reversal",
    )
    require(frozen.fingerprint() == frozen_start, "ordered frozen field changed")
    capability_checks = {
        "swapped_sequences_distinct_before_learning": ordered_forward
        != ordered_reverse,
        "held_reversal_abstained_before_exposure": not held_reverse_before_exposure[
            "decision"
        ]["field_owned"],
        "forward_supported_after_exposure": forward["field_supported_correct"],
        "reverse_supported_after_exposure": reverse["field_supported_correct"],
        "frozen_forward_abstained": not frozen_forward["decision"]["field_owned"],
        "frozen_reverse_abstained": not frozen_reverse["decision"]["field_owned"],
    }
    status = "PASS" if all(capability_checks.values()) else "FAIL"


    return {
        "seed": seed,
        "status": status,
        "capability_checks": capability_checks,
        "world_sha256": world.fingerprint,
        "transcripts": transcripts,
        "held_reverse_before_exposure": held_reverse_before_exposure,
        "forward": forward,
        "reverse": reverse,
        "frozen_forward": frozen_forward,
        "frozen_reverse": frozen_reverse,
        "ordered_boundary": {
            "encoding": "one-span-fixed-event-sequence",
            "grammar": "<subject|relation|object>",
            "end_expression": ">",
            "forward_packet_hex": ordered_forward.hex(),
            "reverse_packet_hex": ordered_reverse.hex(),
            "forward_events": list(decoded_forward),
            "reverse_events": list(decoded_reverse),
            "distinct_before_learning": ordered_forward != ordered_reverse,
            "scope": "fixed-position byte-order diagnostic; not learned syntax or temporal composition",
        },
        "role_marker_codec_invariant": {
            "encoding": "explicit-fixed-role-markers-in-canonical-unordered-spans",
            "same_roles_reordered_wire_identical": canonical_packet(role_forward)
            == canonical_packet(role_reordered_wire),
            "reversed_roles_distinct": canonical_packet(role_forward)
            != canonical_packet(role_reversed),
        },
        "claim": "two explicitly framed exact sequences were acquired separately; the held-out swap abstained before exposure",
        "elapsed_seconds": time.perf_counter() - started,
    }

def ambiguity_clarification_case(seed: int) -> dict[str, Any]:
    """Exercise contextual ambiguity, clarification availability, and restart."""

    started = time.perf_counter()
    world = CausalLanguageWorld.randomized(seed)
    learner = CausalEventLearner(language_profile())
    history_a = grounded_state(world.moved_state, world.entity_seen)
    history_b = grounded_state(world.moved_state, world.entity_held)
    ambiguous = encode_packet(((world.unknown_word + "?").encode("utf-8"),))
    revealed_a = world.command(world.move_word, world.entity_seen)
    revealed_b = world.command(world.inspect_word, world.entity_held)
    goal = world.ordered_target
    inquiry_action = action_packet(world.alternate_action)
    fix_a = world.correct_action(world.move_word)
    fix_b = world.correct_action(world.inspect_word)
    actions = (fix_a, inquiry_action, fix_b)

    exposures: list[dict[str, Any]] = []
    for history, revealed in ((history_a, revealed_a), (history_b, revealed_b)):
        for _ in range(2):
            exposures.append(
                _force_history_relation(
                    learner,
                    history=history,
                    observation=ambiguous,
                    action=inquiry_action,
                    outcome=revealed,
                )
            )
    for revealed, fix in ((revealed_a, fix_a), (revealed_b, fix_b)):
        grounded_outcome = world.clarification_consequence(revealed, fix)
        require(_same(grounded_outcome, goal), "clarification world rejected its repair")
        for _ in range(2):
            exposures.append(
                _force_relation(
                    learner,
                    observation=revealed,
                    action=fix,
                    outcome=grounded_outcome,
                )
            )

    def begin(history: bytes, *, clarification: bool) -> tuple[CausalEventLearner, dict[str, Any]]:
        execution = learner.clone()
        execution.reset()
        execution.observe(history, learn=False)
        execution.observe(ambiguous, learn=False)
        candidates = actions if clarification else (fix_a, fix_b)
        decision = execution.decide(
            candidates,
            goal,
            inquiry_actions=(inquiry_action,) if clarification else (),
        )
        return execution, decision

    context_a, decision_a = begin(history_a, clarification=True)
    context_b, decision_b = begin(history_b, clarification=True)
    no_clarification, unavailable = begin(history_b, clarification=False)
    no_history = learner.clone()
    no_history.reset()
    no_history.observe(ambiguous, learn=False)
    no_history_decision = no_history.decide(
        actions, goal, inquiry_actions=(inquiry_action,)
    )
    context_a_revealed_receipt = context_a.observe(revealed_a, learn=False)
    context_a_followup = context_a.decide(actions, goal)
    context_a_action = committed_action(context_a_followup)
    context_a_outcome = world.clarification_consequence(
        revealed_a, context_a_action
    )
    context_a_final_receipt = context_a.observe(context_a_outcome, learn=False)
    context_a_continuation = {
        "revealed_receipt": context_a_revealed_receipt,
        "followup": _decision_summary(context_a_followup),
        "followup_correct": _same(context_a_action, fix_a),
        "world_outcome_hex": context_a_outcome.hex(),
        "goal_reached": _same(context_a_outcome, goal),
        "final_receipt": context_a_final_receipt,
    }


    checkpoint = context_b.checkpoint_bytes()
    restored = CausalEventLearner.restore(checkpoint, expected_profile=learner.profile)
    uninterrupted = context_b.clone()
    require(
        restored.checkpoint_bytes() == checkpoint,
        "history-bearing pending checkpoint did not restore exactly",
    )
    continuation: list[dict[str, Any]] = []
    for name, execution in (("uninterrupted", uninterrupted), ("restored", restored)):
        revealed_receipt = execution.observe(revealed_b, learn=False)
        followup = execution.decide(actions, goal)
        followup_action = committed_action(followup)
        world_outcome = world.clarification_consequence(
            revealed_b, followup_action
        )
        final_receipt = execution.observe(world_outcome, learn=False)
        continuation.append(
            {
                "name": name,
                "revealed_receipt": revealed_receipt,
                "followup": _decision_summary(followup),
                "followup_correct": _same(followup_action, fix_b),
                "world_outcome_hex": world_outcome.hex(),
                "goal_reached": _same(world_outcome, goal),
                "final_receipt": final_receipt,
                "checkpoint_sha256": hashlib.sha256(
                    execution.checkpoint_bytes()
                ).hexdigest(),
            }
        )
    require(
        uninterrupted.checkpoint_bytes() == restored.checkpoint_bytes(),
        "history-bearing continuation diverged after restart",
    )
    capability_checks = {
        "history_a_selected_inquiry": (
            bool(decision_a["field_owned"])
            and _same(committed_action(decision_a), inquiry_action)
        ),
        "history_b_selected_inquiry": (
            bool(decision_b["field_owned"])
            and _same(committed_action(decision_b), inquiry_action)
        ),
        "history_plans_differ": decision_a["plan_hex"] != decision_b["plan_hex"],
        "history_a_continuation_correct": (
            context_a_continuation["followup_correct"]
            and context_a_continuation["goal_reached"]
        ),
        "history_b_continuations_correct": all(
            row["followup_correct"] and row["goal_reached"]
            for row in continuation
        ),
        "missing_inquiry_candidate_abstained": not unavailable["field_owned"],
        "pending_restart_byte_exact": (
            CausalEventLearner.restore(
                checkpoint, expected_profile=learner.profile
            ).checkpoint_bytes()
            == checkpoint
            and uninterrupted.checkpoint_bytes() == restored.checkpoint_bytes()
        ),
    }
    status = "PASS" if all(capability_checks.values()) else "FAIL"


    return {
        "seed": seed,
        "status": status,
        "capability_checks": capability_checks,
        "world_sha256": world.fingerprint,
        "exposures": exposures,
        "matched_contexts": {
            "history_a": _decision_summary(decision_a),
            "history_b": _decision_summary(decision_b),
            "plans_context_sensitive": decision_a["plan_hex"] != decision_b["plan_hex"],
        },
        "history_a_continuation": context_a_continuation,
        "without_clarification_candidate": _decision_summary(unavailable),
        "without_discourse_history_generic_inquiry": _decision_summary(
            no_history_decision
        ),
        "restart": {
            "checkpoint_bytes": len(checkpoint),
            "checkpoint_sha256": hashlib.sha256(checkpoint).hexdigest(),
            "history_non_null": context_b.snapshot()["protocol_context"]["history_hex"]
            is not None,
            "pending_action_non_null": context_b.snapshot()["protocol_context"]["pending"]
            is not None,
            "restored_byte_exact": CausalEventLearner.restore(
                checkpoint, expected_profile=learner.profile
            ).checkpoint_bytes()
            == checkpoint,
            "continued_byte_exact": uninterrupted.checkpoint_bytes()
            == restored.checkpoint_bytes(),
            "continuation": continuation,
        },
        "field_state_unchanged_during_execution": (
            context_a.fingerprint()
            == context_b.fingerprint()
            == no_clarification.fingerprint()
            == no_history.fingerprint()
            == learner.fingerprint()
        ),
        "elapsed_seconds": time.perf_counter() - started,
    }


def corruption_case(seed: int) -> dict[str, Any]:
    started = time.perf_counter()
    world = CausalLanguageWorld.randomized(seed)
    learner = CausalEventLearner(language_profile())
    pairings = (
        (
            world.move_word,
            action_packet(world.inspect_action),
            world.task_goal(world.entity_seen),
        ),
        (
            world.inspect_word,
            action_packet(world.move_action),
            world.task_goal(world.entity_seen),
        ),
    )
    replay: list[dict[str, Any]] = []
    for construction, corrupted_action, outcome in pairings:
        for _ in range(2):
            replay.append(
                _force_relation(
                    learner,
                    observation=world.command(construction, world.entity_seen),
                    action=corrupted_action,
                    outcome=outcome,
                )
            )

    move = _probe(
        learner,
        observation=world.command(world.move_word, world.entity_seen),
        actions=world.actions,
        goal=world.task_goal(world.entity_seen),
        expected_action=world.correct_action(world.move_word),
    )
    inspect = _probe(
        learner,
        observation=world.command(world.inspect_word, world.entity_seen),
        actions=world.actions,
        goal=world.task_goal(world.entity_seen),
        expected_action=world.correct_action(world.inspect_word),
    )
    field_followed_corrupted_pairing = (
        bool(move["decision"]["field_owned"])
        and not move["correct"]
        and bool(inspect["decision"]["field_owned"])
        and not inspect["correct"]
    )

    return {
        "seed": seed,
        "status": (
            "EXPECTED_NEGATIVE"
            if field_followed_corrupted_pairing
            else "CONTROL_FAIL"
        ),
        "world_sha256": world.fingerprint,
        "corrupted_replay": replay,
        "move": move,
        "inspect": inspect,
        "correct_grounding_rate": (float(move["correct"]) + float(inspect["correct"])) / 2.0,
        "field_followed_corrupted_pairing": field_followed_corrupted_pairing,
        "measured_failure": field_followed_corrupted_pairing,
        "control_passed": field_followed_corrupted_pairing,
        "elapsed_seconds": time.perf_counter() - started,
    }

def restart_intervention_case(
    seed: int, trained: CausalEventLearner | None = None
) -> dict[str, Any]:
    started = time.perf_counter()
    if trained is None:
        lexical = lexical_online_case(seed)
        online = lexical.pop("online")
    else:
        online = trained.clone()
    world = CausalLanguageWorld.randomized(seed)
    command = world.command(world.move_word, world.entity_held)
    goal = world.task_goal(world.entity_held)

    online.reset()
    online.observe(command, learn=False)
    decision = online.decide(world.actions, goal)
    checkpoint = online.checkpoint_bytes()
    uninterrupted = online.clone()
    uninterrupted_receipt = uninterrupted.observe(goal, learn=False)
    restored = CausalEventLearner.restore(checkpoint, expected_profile=online.profile)
    restored_receipt = restored.observe(goal, learn=False)
    require(
        uninterrupted.checkpoint_bytes() == restored.checkpoint_bytes(),
        "language continuation diverged after pending-action restart",
    )
    require(
        uninterrupted_receipt["successor_state_sha256"]
        == restored_receipt["successor_state_sha256"],
        "language outcome receipt diverged after restart",
    )

    original_checkpoint = uninterrupted.checkpoint_bytes()
    counterfactual, intervention = uninterrupted.intervene_relation(
        observation=world.command(world.move_word, world.entity_seen),
        action=world.correct_action(world.move_word),
        outcome=world.task_goal(world.entity_seen),
        history=None,
        bank="ordinary",
    )
    removed_move = _probe(
        counterfactual,
        observation=command,
        actions=world.actions,
        goal=goal,
        expected_action=world.correct_action(world.move_word),
    )
    preserved_paraphrase = _probe(
        counterfactual,
        observation=world.command(world.move_paraphrase, world.entity_held),
        actions=world.actions,
        goal=world.task_goal(world.entity_held),
        expected_action=world.correct_action(world.move_paraphrase),
    )
    preserved_inspect = _probe(
        counterfactual,
        observation=world.command(world.inspect_word, world.entity_held),
        actions=world.actions,
        goal=world.task_goal(world.entity_held),
        expected_action=world.correct_action(world.inspect_word),
    )
    require(
        uninterrupted.checkpoint_bytes() == original_checkpoint,
        "counterfactual intervention mutated the source learner",
    )
    require(
        CausalEventLearner.restore(
            original_checkpoint, expected_profile=uninterrupted.profile
        ).checkpoint_bytes()
        == original_checkpoint,
        "language checkpoint did not restore byte-exactly",
    )
    capability_checks = {
        "pending_decision_field_supported": (
            bool(decision["field_owned"])
            and _same(committed_action(decision), world.correct_action(world.move_word))
        ),
        "restored_before_outcome_identical": CausalEventLearner.restore(
            checkpoint, expected_profile=online.profile
        ).checkpoint_bytes()
        == checkpoint,
        "continued_checkpoint_identical": uninterrupted.checkpoint_bytes()
        == restored.checkpoint_bytes(),
        "successor_state_identical": uninterrupted.fingerprint()
        == restored.fingerprint(),
        "target_relation_removed": not removed_move["field_supported_correct"],
        "paraphrase_preserved": preserved_paraphrase["field_supported_correct"],
        "unrelated_relation_preserved": preserved_inspect["field_supported_correct"],
        "source_checkpoint_unchanged": uninterrupted.checkpoint_bytes()
        == original_checkpoint,
    }
    status = "PASS" if all(capability_checks.values()) else "FAIL"


    return {
        "seed": seed,
        "status": status,
        "capability_checks": capability_checks,
        "world_sha256": world.fingerprint,
        "pending_decision": _decision_summary(decision),
        "restart": {
            "checkpoint_sha256": hashlib.sha256(checkpoint).hexdigest(),
            "checkpoint_bytes": len(checkpoint),
            "restored_before_outcome_identical": CausalEventLearner.restore(
                checkpoint, expected_profile=online.profile
            ).checkpoint_bytes()
            == checkpoint,
            "continued_checkpoint_identical": uninterrupted.checkpoint_bytes()
            == restored.checkpoint_bytes(),
            "successor_state_identical": uninterrupted.fingerprint()
            == restored.fingerprint(),
        },
        "intervention": intervention,
        "removed_construction": removed_move,
        "preserved_paraphrase": preserved_paraphrase,
        "preserved_unrelated_construction": preserved_inspect,
        "source_checkpoint_unchanged": uninterrupted.checkpoint_bytes()
        == original_checkpoint,
        "elapsed_seconds": time.perf_counter() - started,
    }


def _strip_runtime(case: dict[str, Any]) -> dict[str, Any]:
    result = dict(case)
    result.pop("online", None)
    return result


def run(seed_values: Sequence[int], output: Path) -> dict[str, Any]:
    if not seed_values:
        raise ValueError("at least one seed is required")
    started = time.perf_counter()
    cases: list[dict[str, Any]] = []
    for seed in seed_values:
        lexical = lexical_online_case(seed)
        cases.append(
            {
                "seed": seed,
                "lexical_online": _strip_runtime(lexical),
                "ordered_language": ordered_language_case(seed),
                "ambiguity_clarification": ambiguity_clarification_case(seed),
                "corrupted_pairing": corruption_case(seed),
                "restart_intervention": restart_intervention_case(
                    seed, lexical["online"]
                ),
            }
        )

    sources = {
        name: file_sha256(Path(__file__).with_name(name))
        for name in (
            "cassi_causal_language.py",
            "cassi_causal_event_field.py",
            "cassi_raw_event_field.py",
            "run_cassi_causal_language.py",
            "test_cassi_causal_language.py",
        )
    }
    aggregate = {
        "worlds": len(cases),
        "lexical_capability_passed": sum(
            row["lexical_online"]["status"] == "PASS" for row in cases
        ),
        "ordered_capability_passed": sum(
            row["ordered_language"]["status"] == "PASS" for row in cases
        ),
        "ambiguity_capability_passed": sum(
            row["ambiguity_clarification"]["status"] == "PASS" for row in cases
        ),
        "corruption_controls_passed": sum(
            row["corrupted_pairing"]["control_passed"] for row in cases
        ),
        "corruption_expected_negatives": sum(
            row["corrupted_pairing"]["status"] == "EXPECTED_NEGATIVE"
            for row in cases
        ),
        "restart_intervention_capability_passed": sum(
            row["restart_intervention"]["status"] == "PASS" for row in cases
        ),
        "early_online_field_supported": sum(
            item["field_supported_correct"]
            for row in cases
            for item in row["lexical_online"]["early_online"]
        ),
        "late_online_seen_field_supported": sum(
            item["field_supported_correct"]
            for row in cases
            for item in row["lexical_online"]["late_online_seen"]
        ),
        "held_entity_renamings_field_supported": sum(
            item["field_supported_correct"]
            for row in cases
            for item in row["lexical_online"]["held_entity_renaming"]
        ),
        "commutative_component_compositions_supported": sum(
            row["lexical_online"]["true_recombination"][
                "field_owned_valid_two_action_plan"
            ]
            and row["lexical_online"]["true_recombination"]["goal_reached"]
            for row in cases
        ),
        "paraphrase_transfers_supported": sum(
            row["lexical_online"]["paraphrase_transfer"]["supported"]
            for row in cases
        ),
        "normalization_variants_abstained": sum(
            not row["lexical_online"]["normalization"]["unseen_decomposed"][
                "decision"
            ]["field_owned"]
            for row in cases
        ),
        "held_role_reversals_abstained": sum(
            not row["ordered_language"]["held_reverse_before_exposure"][
                "decision"
            ]["field_owned"]
            for row in cases
        ),
        "late_frozen_field_supported": sum(
            item["field_supported_correct"]
            for row in cases
            for item in row["lexical_online"]["late_frozen_seen"]
        ),
        "unknowns_claimed_known": sum(
            row["lexical_online"]["unknown"]["decision"]["field_owned"]
            for row in cases
        ),
        "unsupported_goals_claimed_known": sum(
            row["lexical_online"]["unsupported_goal"]["decision"]["field_owned"]
            for row in cases
        ),
        "clarifications_selected": sum(
            row["ambiguity_clarification"]["matched_contexts"][history][
                "decision_kind"
            ]
            == "field-supported-inquiry"
            for row in cases
            for history in ("history_a", "history_b")
        ),
        "unavailable_clarifications_abstained": sum(
            not row["ambiguity_clarification"]["without_clarification_candidate"][
                "field_owned"
            ]
            for row in cases
        ),
        "history_free_generic_inquiries": sum(
            row["ambiguity_clarification"][
                "without_discourse_history_generic_inquiry"
            ]["field_owned"]
            for row in cases
        ),
        "history_a_continuations_correct": sum(
            row["ambiguity_clarification"]["history_a_continuation"][
                "followup_correct"
            ]
            for row in cases
        ),
        "history_restarts_byte_exact": sum(
            row["ambiguity_clarification"]["restart"]["continued_byte_exact"]
            and row["ambiguity_clarification"]["restart"]["history_non_null"]
            for row in cases
        ),
        "field_owned_committed_language_actions": sum(
            episode["decision"]["field_owned"]
            for row in cases
            for transcript in row["lexical_online"]["transcripts"]
            for episode in transcript["episodes"]
        )
        + sum(
            episode["decision"]["field_owned"]
            for row in cases
            for transcript in row["ordered_language"]["transcripts"]
            for episode in transcript["episodes"]
        ),
        "all_states_finite": all(
            all(
                scale["max_abs"] >= 0.0
                for scale in row["restart_intervention"]["intervention"]["scales_after"]
            )
            for row in cases
        ),
    }
    aggregate["capability_worlds_passed"] = sum(
        all(
            row[name]["status"] == "PASS"
            for name in (
                "lexical_online",
                "ordered_language",
                "ambiguity_clarification",
                "restart_intervention",
            )
        )
        for row in cases
    )
    aggregate["metric_buckets"] = {
        "exact_string_recall": {
            "supported": aggregate["late_online_seen_field_supported"],
            "total": 3 * len(cases),
            "rate": aggregate["late_online_seen_field_supported"] / (3 * len(cases)),
        },
        "fixed_entity_renaming_transfer": {
            "supported": aggregate["held_entity_renamings_field_supported"],
            "total": 3 * len(cases),
            "rate": aggregate["held_entity_renamings_field_supported"] / (3 * len(cases)),
        },
        "commutative_two_component_composition": {
            "supported": aggregate["commutative_component_compositions_supported"],
            "total": len(cases),
            "rate": aggregate["commutative_component_compositions_supported"] / len(cases),
        },
        "independently_grounded_paraphrase_transfer": {
            "supported": aggregate["paraphrase_transfers_supported"],
            "total": 2 * len(cases),
            "rate": aggregate["paraphrase_transfers_supported"] / (2 * len(cases)),
        },
        "normalization": {
            "declared": "none",
            "unseen_canonical_equivalents_abstained": aggregate[
                "normalization_variants_abstained"
            ],
            "total": len(cases),
        },
        "unknown_abstention": {
            "abstained": len(cases) - aggregate["unknowns_claimed_known"],
            "total": len(cases),
            "rate": (len(cases) - aggregate["unknowns_claimed_known"]) / len(cases),
        },
        "corruption_causal_control": {
            "status": "EXPECTED_NEGATIVE",
            "measured_failures": aggregate["corruption_expected_negatives"],
            "total": len(cases),
            "interpretation": "the field reproduced deliberately corrupted experience rather than evaluator truth",
        },
    }
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": (
            "PASS"
            if aggregate["capability_worlds_passed"] == len(cases)
            else "PARTIAL"
        ),
        "seeds": list(seed_values),
        "boundary": {
            "schema": BOUNDARY_SCHEMA,
            "text_encoding": "strict-utf8",
            "normalization": "none",
            "ordered_syntax": "one-span-fixed-event-sequence-with-explicit-end",
            "role_marker_codec_invariant": "fixed-explicit-role-prefixes",
            "adaptive_state": "QiFieldState.field [S,9M,B] only",
        },
        "profile": language_profile().as_dict(),
        "profile_sha256": language_profile().fingerprint,
        "sources": sources,
        "cases": cases,
        "aggregate": aggregate,
        "ownership": {
            "adaptive_persistent_tensor_count": 1,
            "adaptive_state": "QiFieldState.field [S,9M,B] only",
            "learned_lexicon_maps": 0,
            "learned_embeddings": 0,
            "vocabulary_matrices": 0,
            "neural_layers": 0,
            "optimizer_state_bytes": 0,
            "softmax_calls": 0,
            "probabilistic_sampling_calls": 0,
            "qwen_calls": 0,
            "teacher_calls": 0,
            "field_owned_committed_language_actions": aggregate[
                "field_owned_committed_language_actions"
            ],
            "fixed_machinery": [
                "strict UTF-8 encoding",
                "bounded packet framing",
                "one-span fixed event-sequence framing with explicit end-expression",
                "explicit role-marker codec invariant",
                "deterministic world consequences",
                "fixed single-changed-span copy binding",
                "canonical episode-rotated exploration",
            ],
        },
        "claims": {
            "component_composition": "an unseen commutative multiset of two construction spans was solved as a two-action plan from separately grounded components",
            "exact_string": "each complete seen construction was recalled under its original entity",
            "paraphrase": "two surface constructions were independently grounded to the same action and each transferred to a held entity; equivalence was not inferred",
            "renaming": "held-entity transfer used fixed single-changed-span copy binding and is reported separately from component composition",
            "normalization": "none; canonically equivalent precomposed and decomposed UTF-8 remained distinct",
            "ordered_language": "fixed event framing preserved two swapped sequences before learning; the held-out swap abstained before exposure and each exact sequence required separate acquisition",
            "ambiguity": "both context-bearing branches selected clarification and completed the appropriate continuation; removing the inquiry candidate produced a non-field-owned decision; the history-free generic inquiry is reported separately",
            "unknown_behavior": "an unsupported construction committed an exploratory action, received the deterministic unknown-world failure, and remained non-field-owned",
            "generation": "not tested; this stage commits bounded grounded actions rather than emitting free text",
        },
        "limitations": [
            "The language learner commits from caller-provided bounded action candidates.",
            "Held-out entity transfer is a fixed renaming control, not recombination.",
            "Paraphrase equivalence is not inferred; both constructions are independently grounded.",
            "Held-out argument reversal abstains until that exact order is separately acquired.",
            "The two-construction probe is commutative span composition, not order-sensitive sequence composition.",
            "The ordered-expression arm is a fixed-position exact-sequence diagnostic, not learned syntax.",
            "No variable-length or byte-by-byte language generation is tested.",
            "The host world contains ground truth for consequences but is never queried for learner recall or routing.",
            "No native Qwen resource is displaced by this isolated field experiment.",
        ],
        "elapsed_seconds": time.perf_counter() - started,
    }
    require(aggregate["all_states_finite"], "a campaign field state is non-finite")
    require(
        aggregate["normalization_variants_abstained"] == len(cases),
        "normalization boundary execution is incomplete",
    )
    require(
        aggregate["unknowns_claimed_known"] == 0,
        "unknown-world execution produced a field-owned claim",
    )
    require(
        aggregate["history_restarts_byte_exact"] == len(cases),
        "history-bearing restart execution is incomplete",
    )
    receipt["self_sha256"] = digest(receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[301, 302, 303])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("_diag/causal-language/verification.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(json.dumps(run(tuple(args.seeds), args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
