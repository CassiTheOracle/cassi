"""Run the frozen 100-turn CassiFI interleaved-discourse board."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch

from cassi_field_agent import CassiFieldAgent
from cassi_field_language import qi_state_sha256
from cassi_grounded_language import (
    CassiGroundedLanguageError,
    GROUND_ACTIONS,
    GROUND_CAUSES,
    GROUND_HELDOUT_UTTERANCES,
    GROUND_PREDICTION_HELDOUT_QUESTION,
    GROUND_REFERENCE_HELDOUT_BINDINGS,
    GROUND_REFERENCE_HELDOUT_QUESTIONS,
    GROUND_SPATIAL_HELDOUT_QUESTIONS,
    GROUND_TIME_HELDOUT_QUESTIONS,
    observe_colored_objects,
    observe_proprioception,
    read_active_reference,
    spatial_relation_from_observation,
)
from cassi_temporal_language import change_from_coordinates, decode_proprioception

PREREG_PATH = ROOT / "designs" / "MULTI-TURN-DISCOURSE-PREREG.md"
CONFIG_PATH = ROOT / "configs" / "cassi-qi-corpus-language.json"
CHECKPOINT_PATH = ROOT / "artifacts" / "cassi-qi-temporal-language" / "field-state.pt"
RUN_ROOT = ROOT / "_diag" / "cassi-qi-multiturn-discourse-v2"
STATE_DIR = RUN_ROOT / "session"
TRANSCRIPT_PATH = RUN_ROOT / "transcript.txt"
RECEIPT_PATH = RUN_ROOT / "receipt.json"
SESSION_ID = "multiturn.159.v2"
SEED = 159
BOUNDARIES = {
    25: (3, 19, 3),
    50: (6, 41, 3),
    75: (6, 66, 3),
    100: (6, 91, 3),
}

A_LEFT, A_RIGHT, A_UP, A_DOWN, A_HOLD = GROUND_ACTIONS
REFERENCE_BINDINGS = {
    name: (statement, reference_id)
    for name, statement, reference_id in GROUND_REFERENCE_HELDOUT_BINDINGS
}
CAUSE_BY_ACTION: dict[str, str] = dict(
    zip(GROUND_ACTIONS, GROUND_CAUSES, strict=True)
)


def _schedule() -> list[tuple[str, ...]]:
    b = lambda name: ("bind", name)
    p = lambda action: ("predict", action)
    e = lambda action: ("step", action)
    q = lambda family: ("query", family)
    r = lambda subject, comparison, family, expected: (
        "reference",
        subject,
        comparison,
        family,
        expected,
    )
    x = ("explain",)
    o = lambda target, presentation: ("order", target, presentation)
    return [
        b("Mira"),
        b("Sable"),
        b("Orin"),
        r("Sable", "red", "horizontal", "reference.blue"),
        q("horizontal"),
        p(A_LEFT),
        e(A_LEFT),
        x,
        o("time.before", "forward"),
        o("time.after", "reverse"),
        r("it", "blue", "horizontal", "reference.red"),
        q("vertical"),
        p(A_RIGHT),
        x,
        e(A_RIGHT),
        o("time.before", "reverse"),
        r("Mira", "blue", "distance", "reference.red"),
        q("distance"),
        p(A_UP),
        e(A_UP),
        x,
        o("time.after", "forward"),
        r("Mira", "blue", "vertical", "reference.red"),
        q("horizontal"),
        q("distance"),
        r("Orin", "blue", "horizontal", "reference.green"),
        p(A_DOWN),
        e(A_DOWN),
        x,
        o("time.before", "forward"),
        o("time.after", "reverse"),
        r("it", "blue", "horizontal", "reference.green"),
        q("vertical"),
        p(A_HOLD),
        e(A_HOLD),
        x,
        p(A_RIGHT),
        e(A_RIGHT),
        q("distance"),
        x,
        o("time.before", "reverse"),
        r("Mira", "blue", "horizontal", "reference.red"),
        q("horizontal"),
        o("time.after", "forward"),
        r("Orin", "blue", "distance", "reference.green"),
        q("vertical"),
        x,
        o("time.after", "reverse"),
        q("distance"),
        r("Sable", "red", "distance", "reference.blue"),
        r("Sable", "red", "distance", "reference.blue"),
        q("horizontal"),
        x,
        o("time.before", "forward"),
        q("vertical"),
        r("Mira", "blue", "distance", "reference.red"),
        o("time.before", "reverse"),
        q("distance"),
        x,
        o("time.after", "forward"),
        r("Orin", "blue", "vertical", "reference.green"),
        q("horizontal"),
        o("time.after", "reverse"),
        x,
        r("it", "blue", "distance", "reference.red"),
        q("vertical"),
        o("time.before", "forward"),
        r("Sable", "red", "horizontal", "reference.blue"),
        x,
        o("time.after", "reverse"),
        q("distance"),
        r("Mira", "blue", "vertical", "reference.red"),
        x,
        o("time.before", "forward"),
        o("time.after", "reverse"),
        r("Orin", "blue", "distance", "reference.green"),
        x,
        o("time.after", "forward"),
        o("time.before", "reverse"),
        r("it", "blue", "distance", "reference.green"),
        q("horizontal"),
        x,
        r("Sable", "red", "vertical", "reference.blue"),
        o("time.before", "forward"),
        q("distance"),
        o("time.after", "reverse"),
        r("Mira", "blue", "horizontal", "reference.red"),
        x,
        q("vertical"),
        o("time.after", "forward"),
        r("Orin", "blue", "horizontal", "reference.green"),
        o("time.before", "reverse"),
        r("it", "blue", "horizontal", "reference.green"),
        q("distance"),
        x,
        r("Sable", "red", "distance", "reference.blue"),
        o("time.before", "forward"),
        q("horizontal"),
        o("time.after", "reverse"),
        x,
    ]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _seal(body: dict[str, Any]) -> dict[str, Any]:
    receipt = dict(body)
    receipt["receipt_sha256"] = hashlib.sha256(
        _canonical_json(body).encode("utf-8")
    ).hexdigest()
    return receipt


def _active_reference(agent: CassiFieldAgent) -> str | None:
    try:
        return read_active_reference(agent.engine.law, agent.state)
    except CassiGroundedLanguageError:
        return None


def _world_snapshot(agent: CassiFieldAgent) -> dict[str, Any]:
    return agent.world.snapshot()


def _world_sha256(agent: CassiFieldAgent) -> str:
    return str(_world_snapshot(agent)["snapshot_sha256"])


def _memory_sha256(agent: CassiFieldAgent) -> str:
    return agent.engine.law.memory_sha256(agent.state)


def _state_sha256(agent: CassiFieldAgent) -> str:
    return qi_state_sha256(agent.controller, agent.state)


def _coordinates(agent: CassiFieldAgent) -> tuple[float, float]:
    return decode_proprioception(observe_proprioception(agent.world))


def _open_agent() -> CassiFieldAgent:
    return CassiFieldAgent.open(
        config_path=CONFIG_PATH,
        checkpoint_path=CHECKPOINT_PATH,
        state_dir=STATE_DIR,
        session_id=SESSION_ID,
        seed=SEED,
        device="cpu",
    )


def _same_coordinates(
    actual: tuple[float, float], expected: tuple[float, float]
) -> bool:
    return all(abs(left - right) <= 1.0e-6 for left, right in zip(actual, expected))


def _check_state(
    agent: CassiFieldAgent,
    *,
    turn: int,
    expected_steps: int,
    expected_queries: int,
    expected_bindings: int,
) -> float:
    agent.state.validate(agent.controller.config)
    _require(
        bool(torch.isfinite(agent.state.field).all().item()),
        f"turn {turn}: field became nonfinite",
    )
    maximum = float(agent.state.field.abs().max().item())
    bound = float(agent.controller.config.physics.max_mode_amplitude)
    _require(maximum <= bound + 1.0e-6, f"turn {turn}: field bound {maximum} > {bound}")
    actual = (agent.step_count, agent.query_count, agent.binding_count)
    expected = (expected_steps, expected_queries, expected_bindings)
    _require(actual == expected, f"turn {turn}: counters {actual} != {expected}")
    _require(
        agent.world.logical_tick == expected_steps,
        f"turn {turn}: world tick does not equal committed steps",
    )
    _require(sum(actual) == turn, f"turn {turn}: counters do not cover every turn")
    return maximum


def _check_receipt_hashes(
    receipt: dict[str, Any],
    *,
    turn: int,
    state_before: str,
    state_after: str,
    memory_before: str,
    memory_after: str,
    world_before: str,
    world_after: str,
) -> None:
    expected = {
        "state_before_sha256": state_before,
        "state_after_sha256": state_after,
        "memory_before_sha256": memory_before,
        "memory_after_sha256": memory_after,
        "world_before_sha256": world_before,
        "world_after_sha256": world_after,
    }
    for key, value in expected.items():
        if key in receipt:
            _require(receipt[key] == value, f"turn {turn}: receipt {key} mismatch")


def _reopen(
    agent: CassiFieldAgent,
    *,
    turn: int,
    active_reference: str | None,
) -> tuple[CassiFieldAgent, dict[str, Any]]:
    field = agent.state.field.detach().cpu().clone()
    state_sha256 = _state_sha256(agent)
    memory_sha256 = _memory_sha256(agent)
    world = _world_snapshot(agent)
    counters = (agent.step_count, agent.query_count, agent.binding_count)
    agent.close()
    reopened = _open_agent()
    _require(torch.equal(reopened.state.field.cpu(), field), f"turn {turn}: field reload changed")
    _require(_state_sha256(reopened) == state_sha256, f"turn {turn}: state hash reload changed")
    _require(
        _memory_sha256(reopened) == memory_sha256,
        f"turn {turn}: memory reload changed",
    )
    _require(_world_snapshot(reopened) == world, f"turn {turn}: world reload changed")
    _require(
        (reopened.step_count, reopened.query_count, reopened.binding_count) == counters,
        f"turn {turn}: counter reload changed",
    )
    _require(
        _active_reference(reopened) == active_reference,
        f"turn {turn}: active reference reload changed",
    )
    return reopened, {
        "turn": turn,
        "state_sha256": state_sha256,
        "memory_sha256": memory_sha256,
        "world_sha256": str(world["snapshot_sha256"]),
        "counters": list(counters),
        "active_reference": active_reference,
        "exact": True,
    }


def _write_result(
    *,
    body: dict[str, Any],
    transcript: list[str],
) -> dict[str, Any]:
    receipt = _seal(body)
    _atomic_text(TRANSCRIPT_PATH, "\n".join(transcript) + "\n")
    _atomic_text(RECEIPT_PATH, _canonical_json(receipt) + "\n")
    return receipt


def main() -> int:
    started = time.perf_counter()
    transcript: list[str] = []
    turn_records: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []
    agent: CassiFieldAgent | None = None
    checkpoint_sha256 = ""
    prereg_sha256 = ""
    run_root_created = False

    def say(line: str) -> None:
        transcript.append(line)
        print(line, flush=True)

    try:
        RUN_ROOT.mkdir(parents=True, exist_ok=False)
        run_root_created = True
        prereg = PREREG_PATH.read_text(encoding="utf-8")
        _require(
            "V2 AMENDMENT FROZEN BEFORE RUN" in prereg,
            "V2 preregistration amendment is not frozen",
        )
        _require(CONFIG_PATH.is_file(), "frozen configuration is missing")
        _require(CHECKPOINT_PATH.is_file(), "canonical temporal checkpoint is missing")
        prereg_sha256 = _file_sha256(PREREG_PATH)
        config_sha256 = _file_sha256(CONFIG_PATH)
        checkpoint_sha256 = _file_sha256(CHECKPOINT_PATH)
        operations = _schedule()
        _require(len(operations) == 100, f"schedule has {len(operations)} turns")
        _require(
            sum(operation[0] == "bind" for operation in operations) == 3,
            "schedule binding count changed",
        )
        _require(
            sum(operation[0] == "predict" for operation in operations) == 6,
            "schedule prediction count changed",
        )
        _require(
            sum(operation[0] == "step" for operation in operations) == 6,
            "schedule execution count changed",
        )
        torch.set_num_threads(1)
        agent = _open_agent()
        initial_state_sha256 = _state_sha256(agent)
        initial_memory_sha256 = _memory_sha256(agent)
        initial_world_sha256 = _world_sha256(agent)
        expected_steps = expected_queries = expected_bindings = 0
        active_expected: str | None = None
        post_binding_memory_sha256: str | None = None
        pending_predictions: dict[str, str] = {}
        predicted_actions: set[str] = set()
        executed_actions: set[str] = set()
        last_transition: tuple[
            str, str, tuple[float, float], tuple[float, float]
        ] | None = None

        say("CassiFI 100-turn interleaved discourse board")
        for turn, operation in enumerate(operations, 1):
            kind = operation[0]
            state_before = _state_sha256(agent)
            memory_before = _memory_sha256(agent)
            world_before = _world_sha256(agent)
            active_before = _active_reference(agent)
            _require(
                active_before == active_expected,
                f"turn {turn}: active reference before call changed",
            )
            expected: dict[str, Any] = {}

            if kind == "bind":
                name = operation[1]
                statement, expected_reference = REFERENCE_BINDINGS[name]
                prompt = statement
                result = agent.bind_reference(name, statement)
                expected_bindings += 1
                _require(
                    result.reference_id == expected_reference,
                    f"turn {turn}: binding selected {result.reference_id}",
                )
                _require(
                    result.active_reference == expected_reference,
                    f"turn {turn}: binding did not set active reference",
                )
                active_expected = expected_reference
                response = f"{name} refers to {expected_reference.removeprefix('reference.')}"
                expected = {"reference_id": expected_reference}
            elif kind == "predict":
                action_id = operation[1]
                instruction = GROUND_HELDOUT_UTTERANCES[action_id]
                prompt = f"{instruction}; {GROUND_PREDICTION_HELDOUT_QUESTION}"
                result = agent.predict_action(
                    instruction, question=GROUND_PREDICTION_HELDOUT_QUESTION
                )
                expected_queries += 1
                _require(result.action_id == action_id, f"turn {turn}: wrong predicted action")
                _require(result.world_unchanged, f"turn {turn}: prediction changed world")
                _require(result.memory_unchanged, f"turn {turn}: prediction changed memory")
                _require(action_id not in pending_predictions, f"turn {turn}: duplicate prediction")
                pending_predictions[action_id] = result.predicted_change
                predicted_actions.add(action_id)
                response = (
                    f"{action_id.removeprefix('action.')} predicts "
                    f"{result.predicted_change.removeprefix('change.')}"
                )
                expected = {"action_id": action_id}
            elif kind == "step":
                action_id = operation[1]
                instruction = GROUND_HELDOUT_UTTERANCES[action_id]
                prompt = instruction
                before_coordinates = _coordinates(agent)
                result = agent.step(instruction, consolidate=False)
                after_coordinates = _coordinates(agent)
                expected_steps += 1
                actual_change = change_from_coordinates(
                    before_coordinates, after_coordinates
                )
                _require(result.action_id == action_id, f"turn {turn}: wrong action committed")
                _require(not result.consolidated, f"turn {turn}: inference retrained memory")
                expected_status = "hold" if action_id == A_HOLD else "applied"
                _require(
                    result.acknowledgment_status == expected_status,
                    f"turn {turn}: wrong acknowledgment status",
                )
                _require(
                    pending_predictions.pop(action_id, None) == actual_change,
                    f"turn {turn}: prediction did not match measured change",
                )
                executed_actions.add(action_id)
                last_transition = (
                    action_id,
                    actual_change,
                    before_coordinates,
                    after_coordinates,
                )
                response = (
                    f"{action_id.removeprefix('action.')} committed; "
                    f"{actual_change.removeprefix('change.')}"
                )
                expected = {"action_id": action_id, "change_id": actual_change}
            elif kind == "query":
                family = operation[1]
                prompt = GROUND_SPATIAL_HELDOUT_QUESTIONS[family]
                observation = observe_colored_objects(agent.world)
                expected_relation = spatial_relation_from_observation(observation, family)
                result = agent.query(prompt)
                expected_queries += 1
                _require(result.family_id == family, f"turn {turn}: wrong spatial family")
                _require(
                    result.relation_id == expected_relation,
                    f"turn {turn}: wrong spatial relation",
                )
                active_expected = "reference.red"
                response = f"red is {result.answer} relative to blue"
                expected = {"family": family, "relation_id": expected_relation}
            elif kind == "reference":
                subject, comparison, family, expected_subject = operation[1:]
                prompt = (
                    f"{subject} versus {comparison}: "
                    f"{GROUND_REFERENCE_HELDOUT_QUESTIONS[family]}"
                )
                comparison_reference = f"reference.{comparison.casefold()}"
                observation = observe_colored_objects(agent.world)
                expected_relation = spatial_relation_from_observation(
                    observation,
                    family,
                    subject_reference=expected_subject,
                    comparison_reference=comparison_reference,
                )
                result = agent.query_reference(
                    subject,
                    comparison,
                    GROUND_REFERENCE_HELDOUT_QUESTIONS[family],
                )
                expected_queries += 1
                _require(
                    result.active_reference_before == active_before,
                    f"turn {turn}: receipt lost prior active reference",
                )
                _require(
                    result.subject_reference == expected_subject,
                    f"turn {turn}: wrong subject reference",
                )
                _require(
                    result.comparison_reference == comparison_reference,
                    f"turn {turn}: wrong comparison reference",
                )
                _require(
                    result.subject_used_active_register == (subject.casefold() == "it"),
                    f"turn {turn}: pronoun register usage mismatch",
                )
                _require(result.family_id == family, f"turn {turn}: wrong reference family")
                _require(
                    result.relation_id == expected_relation,
                    f"turn {turn}: wrong named/pronoun relation",
                )
                active_expected = expected_subject
                response = f"{subject} is {result.answer} relative to {comparison}"
                expected = {
                    "subject_reference": expected_subject,
                    "comparison_reference": comparison_reference,
                    "relation_id": expected_relation,
                }
            elif kind == "explain":
                if last_transition is None:
                    raise AssertionError(f"turn {turn}: no transition to explain")
                action_id, change_id, before_coordinates, after_coordinates = last_transition
                prompt = "what caused the last change?"
                result = agent.explain_last_transition()
                expected_queries += 1
                _require(result.action_id == action_id, f"turn {turn}: wrong explained action")
                _require(result.change_id == change_id, f"turn {turn}: wrong explained change")
                _require(
                    result.cause_id == CAUSE_BY_ACTION[action_id],
                    f"turn {turn}: wrong explained cause",
                )
                _require(
                    _same_coordinates(result.before, before_coordinates)
                    and _same_coordinates(result.after, after_coordinates),
                    f"turn {turn}: explanation transition changed",
                )
                _require(result.memory_unchanged, f"turn {turn}: explanation changed memory")
                response = result.explanation
                expected = {"action_id": action_id, "change_id": change_id}
            elif kind == "order":
                if last_transition is None:
                    raise AssertionError(f"turn {turn}: no transition to order")
                target, presentation = operation[1:]
                _, _, before_coordinates, after_coordinates = last_transition
                prompt = GROUND_TIME_HELDOUT_QUESTIONS[target]
                result = agent.order_last_transition(prompt, presentation=presentation)
                expected_queries += 1
                expected_position = {
                    ("time.before", "forward"): "position.first",
                    ("time.after", "forward"): "position.second",
                    ("time.before", "reverse"): "position.second",
                    ("time.after", "reverse"): "position.first",
                }[(target, presentation)]
                expected_first, expected_second = (
                    (before_coordinates, after_coordinates)
                    if presentation == "forward"
                    else (after_coordinates, before_coordinates)
                )
                _require(result.target_id == target, f"turn {turn}: wrong time target")
                _require(
                    result.position_id == expected_position,
                    f"turn {turn}: wrong presented position",
                )
                _require(
                    _same_coordinates(result.first_state, expected_first)
                    and _same_coordinates(result.second_state, expected_second),
                    f"turn {turn}: ordered states changed",
                )
                _require(result.memory_unchanged, f"turn {turn}: ordering changed memory")
                response = (
                    f"{target.removeprefix('time.')} is "
                    f"{result.position_id.removeprefix('position.')}"
                )
                expected = {"target_id": target, "position_id": expected_position}
            else:
                raise AssertionError(f"turn {turn}: unknown operation {kind}")

            state_after = _state_sha256(agent)
            memory_after = _memory_sha256(agent)
            world_after = _world_sha256(agent)
            receipt = result.receipt_dict()
            _check_receipt_hashes(
                receipt,
                turn=turn,
                state_before=state_before,
                state_after=state_after,
                memory_before=memory_before,
                memory_after=memory_after,
                world_before=world_before,
                world_after=world_after,
            )
            if kind == "bind":
                _require(memory_after != memory_before, f"turn {turn}: binding changed no memory")
            else:
                _require(world_after == world_before or kind == "step", f"turn {turn}: query changed world")
            if turn == 3:
                post_binding_memory_sha256 = memory_after
            if turn >= 3:
                _require(
                    memory_after == post_binding_memory_sha256,
                    f"turn {turn}: post-binding trained memory changed",
                )
            _require(
                _active_reference(agent) == active_expected,
                f"turn {turn}: active reference after call changed",
            )
            maximum = _check_state(
                agent,
                turn=turn,
                expected_steps=expected_steps,
                expected_queries=expected_queries,
                expected_bindings=expected_bindings,
            )
            turn_record = {
                "turn": turn,
                "kind": kind,
                "prompt": prompt,
                "response": response,
                "expected": expected,
                "active_reference_before": active_before,
                "active_reference_after": active_expected,
                "field_max_abs": maximum,
                "state_sha256": state_after,
                "memory_sha256": memory_after,
                "world_sha256": world_after,
                "counters": [expected_steps, expected_queries, expected_bindings],
                "receipt": receipt,
            }
            turn_records.append(turn_record)
            say(f"{turn:03d} you> {prompt}")
            say(f"    cassi> {response}")

            if turn in BOUNDARIES:
                _require(
                    (expected_steps, expected_queries, expected_bindings)
                    == BOUNDARIES[turn],
                    f"turn {turn}: frozen boundary counters changed",
                )
                agent, boundary = _reopen(
                    agent,
                    turn=turn,
                    active_reference=active_expected,
                )
                boundaries.append(boundary)
                say(f"    [exact close/reopen at turn {turn}]")

        _require(predicted_actions == set(GROUND_ACTIONS), "not all actions were predicted")
        _require(executed_actions == set(GROUND_ACTIONS), "not all actions were executed")
        _require(not pending_predictions, "an action prediction was not executed")
        _require(post_binding_memory_sha256 is not None, "post-binding memory was not frozen")
        _require(_file_sha256(CHECKPOINT_PATH) == checkpoint_sha256, "checkpoint changed")
        _require(_file_sha256(CONFIG_PATH) == config_sha256, "configuration changed")
        final_state_sha256 = _state_sha256(agent)
        final_world_sha256 = _world_sha256(agent)
        agent.close()
        agent = None
        elapsed = time.perf_counter() - started
        say(
            "PASS: 100/100 turns; all five action categories, three spatial "
            "families, references, pronouns, explanations, ordering, and four "
            "exact reopens passed"
        )
        body = {
            "schema": "cassi.qi-multiturn-discourse.v2",
            "status": "PASS",
            "completion_rate": 1.0,
            "turns_correct": 100,
            "turns_total": 100,
            "seed": SEED,
            "session_id": SESSION_ID,
            "preregistration_path": str(PREREG_PATH),
            "preregistration_sha256": prereg_sha256,
            "config_path": str(CONFIG_PATH),
            "config_sha256": config_sha256,
            "checkpoint_path": str(CHECKPOINT_PATH),
            "checkpoint_sha256": checkpoint_sha256,
            "initial_state_sha256": initial_state_sha256,
            "initial_memory_sha256": initial_memory_sha256,
            "initial_world_sha256": initial_world_sha256,
            "post_binding_memory_sha256": post_binding_memory_sha256,
            "final_state_sha256": final_state_sha256,
            "final_world_sha256": final_world_sha256,
            "final_counters": [expected_steps, expected_queries, expected_bindings],
            "boundaries": boundaries,
            "turns": turn_records,
            "elapsed_seconds": elapsed,
        }
        receipt = _write_result(body=body, transcript=transcript)
        print(f"receipt={RECEIPT_PATH}", flush=True)
        print(f"receipt_sha256={receipt['receipt_sha256']}", flush=True)
        return 0
    except Exception as error:
        if agent is not None:
            agent.close()
            agent = None
        elapsed = time.perf_counter() - started
        failure = f"FAIL after {len(turn_records)}/100 turns: {error}"
        say(failure)
        say(traceback.format_exc().rstrip())
        if run_root_created:
            body = {
                "schema": "cassi.qi-multiturn-discourse.v2",
                "status": "FAIL",
                "completion_rate": len(turn_records) / 100.0,
                "turns_correct": len(turn_records),
                "turns_total": 100,
                "seed": SEED,
                "session_id": SESSION_ID,
                "preregistration_sha256": prereg_sha256,
                "checkpoint_sha256": checkpoint_sha256,
                "error": str(error),
                "traceback": traceback.format_exc(),
                "turns": turn_records,
                "boundaries": boundaries,
                "elapsed_seconds": elapsed,
            }
            try:
                _write_result(body=body, transcript=transcript)
            except Exception as write_error:
                print(f"FAIL writing failure receipt: {write_error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
