"""Execute one repeatable 300-turn Blind Labyrinth iteration."""
from __future__ import annotations

import hashlib
import os
import sys
import shutil
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch

from cassi_blind_labyrinth import (
    CHECKPOINT_PATH, COLORS, CONFIG_PATH, CORRECTED_BINDINGS, HELDOUT_BINDINGS,
    HELDOUT_NAMES, PROTOCOL, RUN_ROOT, SESSION_ID, STATE_DIR,
    BlindLabyrinthOracle, GOAL_BANK, canonical, expected_projection, file_sha256,
    generate_schedule, mission_actions, render_prompt, prf,
)
from cassi_field_agent import CassiFieldAgent
from cassi_field_language import qi_state_sha256
from cassi_grounded_language import make_grounded_action_command, read_active_reference

TRANSCRIPT_PATH = RUN_ROOT / "transcript.txt"
SCHEDULE_PATH = RUN_ROOT / "schedule.json"
ORACLE_PATH = RUN_ROOT / "oracle.json"
RECEIPT_PATH = RUN_ROOT / "receipt.json"

class GateFailure(RuntimeError):
    def __init__(self, classification: str, message: str, turn: int | None = None):
        super().__init__(message)
        self.classification, self.turn = classification, turn


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _seal(body: dict[str, Any]) -> dict[str, Any]:
    result = dict(body)
    result["receipt_sha256"] = hashlib.sha256(canonical(body).encode()).hexdigest()
    return result


def _state(agent: CassiFieldAgent) -> str:
    return qi_state_sha256(agent.controller, agent.state)


def _memory(agent: CassiFieldAgent) -> str:
    return agent.engine.law.memory_sha256(agent.state)


def _world(agent: CassiFieldAgent) -> str:
    return str(agent.world.snapshot()["snapshot_sha256"])


def _active(agent: CassiFieldAgent) -> str | None:
    try:
        return read_active_reference(agent.engine.law, agent.state)
    except Exception:
        return None


def _open(state_dir: Path = STATE_DIR, session_id: str = SESSION_ID) -> CassiFieldAgent:
    return CassiFieldAgent.open(config_path=CONFIG_PATH, checkpoint_path=CHECKPOINT_PATH,
        state_dir=state_dir, session_id=session_id, seed=731, device="cpu")


def _order_prompt(row: dict[str, Any], oracle: BlindLabyrinthOracle) -> str:
    if not oracle.transitions:
        return render_prompt(row)
    transition = oracle.transitions[-1]
    before, after = transition["before"], transition["after"]
    f = lambda value: f"{value:+.9f}"
    before_tick = transition.get("before_tick", row["turn"] - 1)
    after_tick = transition.get("after_tick", row["turn"])
    return ("which state came first or second. "
        f"State A=tick={before_tick};x={f(before[0])};y={f(before[1])}; "
        f"State B=tick={after_tick};x={f(after[0])};y={f(after[1])}.")


def _prompt(row: dict[str, Any], oracle: BlindLabyrinthOracle) -> str:
    return _order_prompt(row, oracle) if row["operation"] == "temporal-order" else render_prompt(row)


def _compare_projection(actual: Any, expected: dict[str, Any], turn: int) -> None:
    projection = expected_projection(actual.receipt_dict())
    mismatches = {
        key: (projection.get(key), value)
        for key, value in expected.items()
        if value != "*" and projection.get(key) != value
    }
    if mismatches:
        raise GateFailure(
            "GROUNDING_FAILURE",
            f"turn {turn}: typed projection mismatch: {mismatches}",
            turn,
        )
    if actual.adaptive_persistent_state != "QiFieldState.field[S,9M,B] only":
        raise GateFailure("MEMORY_OWNERSHIP_FAILURE", f"turn {turn}: adaptive state bound changed", turn)
    if (
        actual.field_ownership.get("route")
        != "QiFieldState.field atomic semantic-frame trajectory"
        or actual.field_ownership.get("slots")
        != "QiFieldState.field autoregressive trajectory work"
        or actual.field_ownership.get("host_router") != "none"
    ):
        raise GateFailure("ROUTING_OWNERSHIP_FAILURE", f"turn {turn}: ownership receipt changed", turn)


def _clone_agent(
    source: CassiFieldAgent,
    state_dir: Path,
    session_id: str,
) -> CassiFieldAgent:
    clone = _open(state_dir, session_id)
    clone.state = type(source.state)(source.state.field.detach().clone())
    clone.world.restore(source.world.snapshot())
    clone.step_count = source.step_count
    clone.query_count = source.query_count
    clone.binding_count = source.binding_count
    return clone


def _controls(agent: CassiFieldAgent, boundary: int) -> dict[str, Any]:
    base = RUN_ROOT / f"control-{boundary}"
    aa_a = _clone_agent(agent, base / "aa-a", f"blind-labyrinth.aa-a.{boundary}")
    aa_b = _clone_agent(agent, base / "aa-b", f"blind-labyrinth.aa-b.{boundary}")
    try:
        prompt = "acknowledge the current field without changing the world"
        left, right = aa_a.turn(prompt), aa_b.turn(prompt)

        def scrub(value: Any) -> Any:
            if isinstance(value, dict):
                return {
                    key: scrub(item)
                    for key, item in value.items()
                    if key != "elapsed_seconds"
                }
            if isinstance(value, (list, tuple)):
                return [scrub(item) for item in value]
            return value

        if scrub(left.receipt_dict()) != scrub(right.receipt_dict()):
            raise GateFailure("CONTROL_FAILURE", f"boundary {boundary}: A/A mismatch")

        bindings = {str(name): str(color) for name, color in HELDOUT_BINDINGS.items()}
        corrected = {
            str(name): str(color) for name, color in CORRECTED_BINDINGS.items()
        }
        corrected_count = max(0, min(6, (boundary // 50 - 2) * 2))
        for name in HELDOUT_NAMES[:corrected_count]:
            bindings[name] = corrected[name]
        start = prf("fork", boundary) % len(HELDOUT_NAMES)
        ordered = HELDOUT_NAMES[start:] + HELDOUT_NAMES[:start]
        first = ordered[0]
        second = next(name for name in ordered[1:] if bindings[name] != bindings[first])
        comparison = next(
            color
            for color in COLORS
            if color not in {bindings[first], bindings[second]}
        )
        aa_a.turn(
            f"resolve the distance relation from {first} to {comparison}"
        )
        aa_b.turn(
            f"resolve the distance relation from {second} to {comparison}"
        )
        query = f"resolve the distance relation from it to {comparison}"
        left, right = aa_a.turn(query), aa_b.turn(query)
        expected_left = f"reference.{bindings[first]}"
        expected_right = f"reference.{bindings[second]}"
        if (
            left.abstained
            or right.abstained
            or left.reference != expected_left
            or right.reference != expected_right
        ):
            raise GateFailure(
                "CONTROL_FAILURE",
                f"boundary {boundary}: A/B active reference mismatch",
            )
        return {
            "boundary": boundary,
            "aa": True,
            "ab": True,
            "names": [first, second],
            "references": [expected_left, expected_right],
        }
    finally:
        aa_a.close()
        aa_b.close()


def main() -> int:
    if RUN_ROOT.exists():
        shutil.rmtree(RUN_ROOT)
    transcript: list[str] = []
    turns: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []
    agent: CassiFieldAgent | None = None
    active_turn: int | None = None
    try:
        torch.set_num_threads(1)
        RUN_ROOT.mkdir(parents=True, exist_ok=True)
        schedule, nonce = generate_schedule()
        schedule_body = {"protocol": PROTOCOL, "seed": 20260829, "nonce": nonce, "operations": schedule}
        schedule_body["schedule_sha256"] = hashlib.sha256(canonical(schedule_body).encode()).hexdigest()
        _atomic(SCHEDULE_PATH, canonical(schedule_body) + "\n")
        oracle = BlindLabyrinthOracle.open()
        expected_rows: list[dict[str, Any]] = []
        agent = _open()
        for row in schedule:
            turn = int(row["turn"])
            active_turn = turn
            prompt = _prompt(row, oracle)
            state_before, memory_before, world_before = _state(agent), _memory(agent), _world(agent)
            expected = oracle.expected(row)
            result = agent.turn(prompt)
            if result.text != prompt:
                raise GateFailure("API_FAILURE", f"turn {turn}: raw text receipt mismatch", turn)
            _compare_projection(result, expected, turn)
            if result.state_before_sha256 != state_before or result.memory_before_sha256 != memory_before or result.world_before_sha256 != world_before:
                raise GateFailure("API_FAILURE", f"turn {turn}: before hash mismatch", turn)
            state_after, memory_after, world_after = _state(agent), _memory(agent), _world(agent)
            if (result.state_after_sha256 != state_after or result.memory_after_sha256 != memory_after or result.world_after_sha256 != world_after):
                raise GateFailure("API_FAILURE", f"turn {turn}: after hash mismatch", turn)
            if not bool(torch.isfinite(agent.state.field).all()) or float(agent.state.field.detach().abs().max()) > 8.0:
                raise GateFailure("STATE_BOUND_FAILURE", f"turn {turn}: field invalid or out of bounds", turn)
            if row["operation"] not in {"binding", "binding-correction"} and memory_after != memory_before:
                raise GateFailure("MEMORY_OWNERSHIP_FAILURE", f"turn {turn}: ordinary turn consolidated", turn)
            if row["operation"] in {"generic-relation", "named-relation", "pronoun-relation", "temporal-prediction", "temporal-observed-change", "temporal-cause", "temporal-order", "temporal-interference", "neutral-field-inference", "ambiguity-abstention", "action-prediction"} and world_after != world_before:
                raise GateFailure("WORLD_INVARIANT_FAILURE", f"turn {turn}: inference changed world", turn)
            expected_rows.append({"turn": turn, "prompt": prompt, "expected": expected})
            turns.append({"turn": turn, "prompt": prompt, "receipt": result.receipt_dict()})
            transcript.append(f"{turn:03d}\t{prompt}\t{canonical(expected)}")
            if turn in (50, 100, 150, 200, 250, 300):
                snapshot = agent.world.snapshot()
                boundary = {"turn": turn, "state_sha256": _state(agent), "memory_sha256": _memory(agent), "world_sha256": _world(agent), "world_snapshot": snapshot, "counters": [agent.step_count, agent.query_count, agent.binding_count], "active_reference": _active(agent), "checkpoint_sha256": file_sha256(CHECKPOINT_PATH), "config_sha256": file_sha256(CONFIG_PATH)}
                field = agent.state.field.detach().cpu().clone()
                agent.close(); agent = _open()
                if not torch.equal(field, agent.state.field.cpu()) or boundary["world_snapshot"] != agent.world.snapshot() or boundary["state_sha256"] != _state(agent) or tuple(boundary["counters"]) != (agent.step_count, agent.query_count, agent.binding_count) or boundary["active_reference"] != _active(agent):
                    raise GateFailure("PERSISTENCE_FAILURE", f"boundary {turn}: reopen mismatch", turn)
                boundary["reopened"] = True
                boundary["controls"] = _controls(agent, turn)
                boundaries.append(boundary)
        _atomic(ORACLE_PATH, canonical({"protocol": PROTOCOL, "rows": expected_rows, "oracle_sha256": hashlib.sha256(canonical(expected_rows).encode()).hexdigest()}) + "\n")
        actions = mission_actions()
        setup = GOAL_BANK[prf("bank", 301, "goal", 0) % 3].format(
            **dict(
                zip(
                    ("a", "b", "c"),
                    (
                        render_prompt({"operation": "action-execution", "turn": 301, "action": actions[0], "bank_index": 0}),
                        render_prompt({"operation": "action-execution", "turn": 302, "action": actions[1], "bank_index": 0}),
                        render_prompt({"operation": "action-execution", "turn": 303, "action": actions[2], "bank_index": 0}),
                    ),
                    strict=True,
                )
            )
        )
        setup_result = agent.turn(setup)
        if setup_result.goal is None or tuple(setup_result.goal.get("actions", ())) != actions:
            raise GateFailure("GROUNDING_FAILURE", "mission setup did not commit three field-owned actions")
        setup_memory = setup_result.memory_after_sha256
        step_before_mission = agent.step_count
        agent.close()
        agent = _open()
        completed = agent.turn("begin")
        for action in actions:
            oracle.world.step(
                make_grounded_action_command(
                    oracle.world,
                    action,
                    field_state_sha256="0" * 64,
                )
            )
        if (
            completed.goal is None
            or completed.goal.get("status") != "completed"
            or completed.goal.get("step_count") != 3
            or agent.step_count != step_before_mission + 3
            or completed.memory_after_sha256 != setup_memory
            or agent.world.state_sha256 != oracle.world.state_sha256
        ):
            raise GateFailure("GROUNDING_FAILURE", "mission trigger did not complete exactly three transactional actions")
        mission_world_state_sha256 = agent.world.state_sha256
        agent.close()
        agent = None
        _atomic(TRANSCRIPT_PATH, "\n".join(transcript) + "\n")
        body = {"protocol": PROTOCOL, "verdict": "PASS", "C": 1.0, "main_turns": 300, "turns": turns, "boundaries": boundaries, "mission": {"actions": list(actions), "completed": True, "step_count": 3, "memory_sha256": completed.memory_after_sha256, "world_sha256": completed.world_after_sha256, "world_state_sha256": mission_world_state_sha256}, "checkpoint_sha256": file_sha256(CHECKPOINT_PATH), "config_sha256": file_sha256(CONFIG_PATH), "schedule_sha256": schedule_body["schedule_sha256"], "oracle_sha256": hashlib.sha256(canonical(expected_rows).encode()).hexdigest()}
        _atomic(RECEIPT_PATH, canonical(_seal(body)) + "\n")
        print("PASS")
        return 0
    except Exception as error:
        if agent is not None:
            try: agent.close()
            except Exception: pass
        failure = (
            error
            if isinstance(error, GateFailure)
            else GateFailure(
                "API_FAILURE" if active_turn is not None else "ENVIRONMENT_FAILURE",
                str(error),
                active_turn,
            )
        )
        transcript.append(f"FAIL\t{failure.classification}\t{failure}")
        _atomic(TRANSCRIPT_PATH, "\n".join(transcript) + "\n")
        body = {"protocol": PROTOCOL, "verdict": "FAIL", "first_failure": {"classification": failure.classification, "message": str(failure), "turn": failure.turn}, "main_turns_completed": len(turns), "turns": turns, "boundaries": boundaries, "traceback": traceback.format_exc()}
        _atomic(RECEIPT_PATH, canonical(_seal(body)) + "\n")
        print(f"FAIL: {failure.classification}: {failure}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
