"""Independently verify sealed Blind Labyrinth artifacts."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from cassi_blind_labyrinth import (
    CHECKPOINT_PATH, CONFIG_PATH, PROTOCOL, RUN_ROOT, canonical,
    expected_projection, file_sha256, generate_schedule, mission_actions,
    render_prompt,
)
from cassi_grounded_language import GROUND_ACTIONS, make_grounded_action_command, observe_colored_objects, observe_proprioception, spatial_relation_from_observation
from cassi_qi_world import DeterministicQiWorld
from cassi_temporal_language import change_from_coordinates

SCHEDULE_PATH = RUN_ROOT / "schedule.json"
ORACLE_PATH = RUN_ROOT / "oracle.json"
RECEIPT_PATH = RUN_ROOT / "receipt.json"
TRANSCRIPT_PATH = RUN_ROOT / "transcript.txt"


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def sealed(value: dict[str, Any]) -> bool:
    digest = value.get("receipt_sha256")
    if not isinstance(digest, str):
        return False
    body = {key: item for key, item in value.items() if key != "receipt_sha256"}
    return digest == hashlib.sha256(canonical(body).encode()).hexdigest()

class IndependentOracle:
    """Separate verifier state machine; it never reads runner oracle rows."""
    def __init__(self) -> None:
        self.world = DeterministicQiWorld(seed=731, session_id="blind-labyrinth.20260829")
        self.bindings: dict[str, str] = {}
        self.active: str | None = None
        self.transitions: list[dict[str, Any]] = []

    def expected(self, row: dict[str, Any]) -> dict[str, Any]:
        kind = row["operation"]
        if kind == "ambiguity-abstention":
            return {"route_id": "*", "abstained": True, "reason": row["reason"], "action": None, "relation": None, "reference": None, "temporal": None, "goal": None}
        if kind in {"binding", "binding-correction"}:
            reference = "reference." + row["color"]
            previous = self.bindings.get(row["name"])
            old_reference = None if previous is None else "reference." + previous
            self.bindings[row["name"]] = row["color"]
            if kind == "binding-correction" and self.active == old_reference:
                self.active = reference
            return {"route_id": "route.binding", "abstained": False, "reason": None, "action": None, "relation": None, "reference": reference, "temporal": None, "goal": None}
        if kind in {"action-prediction", "delayed-prediction"}:
            action = row.get("source_action", row["action"])
            change = dict(zip(GROUND_ACTIONS, ("change.x-decrease", "change.x-increase", "change.y-increase", "change.y-decrease", "change.none"), strict=True))[action]
            return {"route_id": "route.prediction", "abstained": False, "reason": None, "action": action, "relation": None, "reference": None, "temporal": {"predicted_change": change}, "goal": None}
        if kind == "action-execution":
            before_tick = self.world.logical_tick
            before = decode_coordinates(self.world)
            self.world.step(make_grounded_action_command(self.world, row["action"], field_state_sha256="0" * 64))
            after_tick = self.world.logical_tick
            after = decode_coordinates(self.world)
            self.transitions.append({"action": row["action"], "change": change_from_coordinates(before, after), "before": before, "after": after, "before_tick": before_tick, "after_tick": after_tick})
            return {"route_id": "route.action", "abstained": False, "reason": None, "action": row["action"], "relation": None, "reference": None, "temporal": None, "goal": None}
        if kind in {"generic-relation", "named-relation", "delayed-reference", "pronoun-relation"}:
            if kind == "generic-relation":
                subject, comparison, route = "reference.red", "reference.blue", "route.spatial"
                self.active = subject
            else:
                subject = self.active if kind == "pronoun-relation" else "reference." + self.bindings[row["name"]]
                if subject is None:
                    raise ValueError("pronoun has no active reference")
                comparison, route = "reference." + row["comparison"], "route.reference"
                self.active = subject
            relation = spatial_relation_from_observation(observe_colored_objects(self.world), row["family"], subject_reference=subject, comparison_reference=comparison)
            return {"route_id": route, "abstained": False, "reason": None, "action": None, "relation": relation, "reference": subject, "temporal": None, "goal": None}
        latest = self.transitions[-1] if self.transitions else {"action": "action.hold", "change": "change.none"}
        if kind == "temporal-prediction":
            action = row["action"]
            change = dict(zip(GROUND_ACTIONS, ("change.x-decrease", "change.x-increase", "change.y-increase", "change.y-decrease", "change.none"), strict=True))[action]
            temporal = {"predicted_change": change}
            return {"route_id": "route.prediction", "abstained": False, "reason": None, "action": action, "relation": None, "reference": None, "temporal": temporal, "goal": None}
        if kind in {"temporal-observed-change", "temporal-cause", "temporal-interference"}:
            temporal = {"action": latest["action"], "change": latest["change"], "cause": latest["action"].replace("action.", "cause.")}
            return {"route_id": "route.explanation", "abstained": False, "reason": None, "action": None, "relation": None, "reference": None, "temporal": temporal, "goal": None}
        if kind == "temporal-order":
            return {"route_id": "route.ordering", "abstained": False, "reason": None, "action": None, "relation": None, "reference": None, "temporal": {"target": "time.before", "position": "position.first"}, "goal": None}
        if kind == "neutral-field-inference":
            return {"route_id": "route.neutral", "abstained": False, "reason": None, "action": None, "relation": None, "reference": None, "temporal": None, "goal": None}
        raise ValueError(kind)
def decode_coordinates(world: DeterministicQiWorld) -> tuple[float, float]:
    return __import__("cassi_temporal_language", fromlist=["decode_proprioception"]).decode_proprioception(observe_proprioception(world))


def prompt_for(row: dict[str, Any], oracle: IndependentOracle) -> str:
    if row["operation"] != "temporal-order" or not oracle.transitions:
        return render_prompt(row)
    transition = oracle.transitions[-1]
    before, after = transition["before"], transition["after"]
    f = lambda value: f"{value:+.9f}"
    before_tick = transition.get("before_tick", row["turn"] - 1)
    after_tick = transition.get("after_tick", row["turn"])
    return ("which state came first or second. "
        f"State A=tick={before_tick};x={f(before[0])};y={f(before[1])}; "
        f"State B=tick={after_tick};x={f(after[0])};y={f(after[1])}.")


def main() -> int:
    try:
        base_paths = (
            SCHEDULE_PATH,
            RECEIPT_PATH,
            TRANSCRIPT_PATH,
            CONFIG_PATH,
            CHECKPOINT_PATH,
        )
        if any(not path.is_file() for path in base_paths):
            return fail("missing artifact or frozen input")
        schedule_doc = json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        verdict = receipt.get("verdict")
        if verdict not in {"PASS", "FAIL"}:
            return fail("unknown receipt verdict")
        oracle_doc: dict[str, Any] | None = None
        if verdict == "PASS":
            if not ORACLE_PATH.is_file():
                return fail("missing oracle artifact")
            oracle_doc = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))
        documents = (schedule_doc, receipt) + (
            (oracle_doc,) if oracle_doc is not None else ()
        )
        if any(doc.get("protocol") != PROTOCOL for doc in documents):
            return fail("protocol mismatch")
        if not sealed(receipt):
            return fail("receipt seal mismatch")
        schedule, nonce = generate_schedule()
        if schedule_doc.get("nonce") != nonce or schedule_doc.get("operations") != schedule:
            return fail("schedule regeneration mismatch")
        schedule_body = {key: value for key, value in schedule_doc.items() if key != "schedule_sha256"}
        schedule_hash = hashlib.sha256(canonical(schedule_body).encode()).hexdigest()
        if (
            schedule_doc.get("schedule_sha256") != schedule_hash
            or (
                verdict == "PASS"
                and receipt.get("schedule_sha256") != schedule_hash
            )
        ):
            return fail("schedule hash mismatch")
        turn_records = receipt.get("turns")
        if not isinstance(turn_records, list):
            return fail("turn records missing")
        if verdict == "PASS":
            if receipt.get("main_turns") != 300 or len(turn_records) != 300:
                return fail("main turn count mismatch")
            expected_turn_count = 300
        else:
            expected_turn_count = receipt.get("main_turns_completed")
            if (
                not isinstance(expected_turn_count, int)
                or not 0 <= expected_turn_count < 300
                or len(turn_records) != expected_turn_count
            ):
                return fail("failed-run turn count mismatch")
        if len(schedule) != 300:
            return fail("generated schedule count mismatch")
        if sum(row["operation"] == "ambiguity-abstention" for row in schedule) != 5:
            return fail("abstention count mismatch")
        oracle_rows: list[Any] | None = None
        if oracle_doc is not None:
            candidate_rows = oracle_doc.get("rows")
            if (
                not isinstance(candidate_rows, list)
                or len(candidate_rows) != 300
                or oracle_doc.get("oracle_sha256")
                != hashlib.sha256(canonical(candidate_rows).encode()).hexdigest()
            ):
                return fail("oracle artifact seal/count mismatch")
            oracle_rows = candidate_rows
        oracle = IndependentOracle()
        for row, turn_record in zip(
            schedule[:expected_turn_count],
            turn_records,
            strict=True,
        ):
            turn = row["turn"]
            if turn_record.get("turn") != turn:
                return fail(f"turn {turn}: numbering mismatch")
            prompt = prompt_for(row, oracle)
            if turn_record.get("prompt") != prompt:
                return fail(f"turn {turn}: prompt mismatch")
            expected = oracle.expected(row)
            derived = {"turn": turn, "prompt": prompt, "expected": expected}
            if oracle_rows is not None and oracle_rows[turn - 1] != derived:
                return fail(
                    f"turn {turn}: oracle artifact differs from independent derivation"
                )
            actual = turn_record.get("receipt")
            if not isinstance(actual, dict):
                return fail(f"turn {turn}: receipt is missing")
            projection = expected_projection(actual)
            if any(
                projection.get(key) != value
                for key, value in expected.items()
                if value != "*"
            ):
                return fail(f"turn {turn}: oracle typed output mismatch")
            if actual.get("text") != prompt or actual.get("schema") != "cassi.grounded-field-agent.v6":
                return fail(f"turn {turn}: raw/schema mismatch")
            for key in ("state_before_sha256", "state_after_sha256", "memory_before_sha256", "memory_after_sha256", "world_before_sha256", "world_after_sha256"):
                if not isinstance(actual.get(key), str) or len(actual[key]) != 64:
                    return fail(f"turn {turn}: missing hash {key}")
            if actual.get("adaptive_persistent_state") != "QiFieldState.field[S,9M,B] only":
                return fail(f"turn {turn}: state ownership mismatch")
            ownership = actual.get("field_ownership")
            if (
                not isinstance(ownership, dict)
                or ownership.get("route")
                != "QiFieldState.field atomic semantic-frame trajectory"
                or ownership.get("slots")
                != "QiFieldState.field autoregressive trajectory work"
                or ownership.get("host_router") != "none"
            ):
                return fail(f"turn {turn}: route ownership mismatch")
            should_consolidate = row["operation"] in {"binding", "binding-correction"}
            if actual.get("effective_consolidate") is not should_consolidate:
                return fail(f"turn {turn}: consolidation mismatch")
        if verdict == "FAIL":
            first_failure = receipt.get("first_failure")
            if (
                not isinstance(first_failure, dict)
                or not isinstance(first_failure.get("classification"), str)
                or not first_failure["classification"]
                or not isinstance(first_failure.get("message"), str)
            ):
                return fail("failure classification missing")
            boundaries = receipt.get("boundaries")
            if (
                not isinstance(boundaries, list)
                or any(
                    not isinstance(item, dict)
                    or not isinstance(item.get("turn"), int)
                    or item["turn"] > expected_turn_count
                    for item in boundaries
                )
            ):
                return fail("failed-run boundary mismatch")
            transcript_lines = TRANSCRIPT_PATH.read_text(
                encoding="utf-8"
            ).splitlines()
            if (
                len(transcript_lines) != expected_turn_count + 1
                or not transcript_lines[-1].startswith("FAIL\t")
            ):
                return fail("failed-run transcript mismatch")
            print(
                "VERIFIED FAIL: "
                f"{first_failure['classification']} after "
                f"{expected_turn_count} completed turns"
            )
            return 1

        boundaries = receipt.get("boundaries")
        if not isinstance(boundaries, list) or [item.get("turn") for item in boundaries] != [50, 100, 150, 200, 250, 300]:
            return fail("boundary set mismatch")
        if any(not item.get("reopened") for item in boundaries):
            return fail("reopen gate failed")
        if any(not item.get("controls", {}).get("aa") or not item.get("controls", {}).get("ab") for item in boundaries):
            return fail("control gate failed")
        if any(
            item.get("checkpoint_sha256") != file_sha256(CHECKPOINT_PATH)
            or item.get("config_sha256") != file_sha256(CONFIG_PATH)
            for item in boundaries
        ):
            return fail("boundary frozen-input digest mismatch")
        mission = receipt.get("mission")
        if (
            not isinstance(mission, dict)
            or mission.get("completed") is not True
            or mission.get("actions") != list(mission_actions())
            or mission.get("step_count") != 3
            or not isinstance(mission.get("memory_sha256"), str)
            or not isinstance(mission.get("world_sha256"), str)
            or not isinstance(mission.get("world_state_sha256"), str)
        ):
            return fail("mission gate failed")
        for action in mission_actions():
            oracle.world.step(
                make_grounded_action_command(
                    oracle.world,
                    action,
                    field_state_sha256="0" * 64,
                )
            )
        if mission["world_state_sha256"] != oracle.world.state_sha256:
            return fail("mission physical world mismatch")
        if receipt.get("checkpoint_sha256") != file_sha256(CHECKPOINT_PATH) or receipt.get("config_sha256") != file_sha256(CONFIG_PATH):
            return fail("frozen input digest mismatch")
        if len(TRANSCRIPT_PATH.read_text(encoding="utf-8").splitlines()) != 300:
            return fail("transcript count mismatch")
        if receipt.get("verdict") != "PASS" or receipt.get("C") != 1.0:
            return fail("verdict is not PASS")
        print("PASS")
        return 0
    except Exception as error:
        return fail(f"uninterpretable artifact: {error}")


if __name__ == "__main__":
    raise SystemExit(main())
