"""Frozen deterministic Blind Labyrinth protocol helpers.

The runner and verifier share only schedule/payload primitives; replies are
never used to construct the oracle expectations.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR
from cassi_grounded_language import CassiGroundedLanguageError, GROUND_ACTIONS, make_grounded_action_command, observe_colored_objects, observe_proprioception, spatial_relation_from_observation
from cassi_qi_world import DeterministicQiWorld
from cassi_temporal_language import change_from_coordinates, decode_proprioception

PROTOCOL = "cassi.blind-labyrinth.v1"
SEED = 20260829
WORLD_SEED = 731
SESSION_ID = "blind-labyrinth.20260829"
CONFIG_PATH = CONFIG_DIR / "cassi-qi-corpus-language.json"
CHECKPOINT_PATH = ARTIFACT_DIR / "cassi-qi-discourse-language" / "field-state.pt"
RUN_ROOT = Path(__file__).resolve().parent / "_diag" / "blind-labyrinth"
STATE_DIR = RUN_ROOT / "session"

OPERATION_NAMES = (
    "binding", "binding-correction", "action-prediction", "action-execution",
    "generic-relation", "named-relation", "pronoun-relation", "temporal-prediction",
    "temporal-observed-change", "temporal-cause", "temporal-order",
    "temporal-interference", "delayed-reference", "delayed-prediction",
    "ambiguity-abstention", "neutral-field-inference",
)
PHASE_VECTORS = (
    (6, 0, 2, 2, 5, 5, 3, 4, 3, 3, 3, 3, 3, 3, 1, 4),
    (0, 0, 2, 2, 5, 5, 3, 4, 3, 3, 3, 3, 3, 3, 1, 10),
    (0, 2, 6, 6, 5, 5, 3, 4, 3, 3, 3, 3, 3, 3, 1, 0),
    (0, 2, 6, 6, 5, 5, 3, 4, 3, 3, 3, 3, 3, 3, 1, 0),
    (0, 2, 4, 4, 5, 5, 3, 4, 3, 3, 3, 3, 3, 3, 1, 4),
    (0, 0, 4, 4, 5, 5, 3, 4, 3, 3, 3, 3, 3, 3, 0, 7),
)
HELDOUT_NAMES = ("Juniper", "Kestrel", "Lumen", "Nix", "Opal", "Quill")
HELDOUT_BINDINGS = dict(zip(HELDOUT_NAMES, ("red", "blue", "green", "red", "blue", "green"), strict=True))
CORRECTED_BINDINGS = dict(zip(HELDOUT_NAMES, ("blue", "green", "red", "green", "red", "blue"), strict=True))
COLORS = ("red", "blue", "green")
FAMILIES = ("horizontal", "vertical", "distance")

ACTION_BANK = {
    **{a: (f"shift your gaze toward the {a.removeprefix('action.gaze-')}", f"direct your eyes to the {a.removeprefix('action.gaze-')} side", f"move your looking direction {a.removeprefix('action.gaze-')}") for a in GROUND_ACTIONS if a != "action.hold"},
    "action.hold": ("keep your gaze exactly where it is", "make no gaze movement", "remain at the current gaze position"),
}
ACTION_PREDICTION_BANK = {
    **{a: (f"without moving, forecast a {a.removeprefix('action.gaze-')} gaze transition", f"predict what follows if the gaze is directed {a.removeprefix('action.gaze-')}", f"state the {a.removeprefix('action.gaze-')}-gaze outcome without acting") for a in GROUND_ACTIONS if a != "action.hold"},
    "action.hold": ("without moving, forecast holding the gaze", "predict what follows if the gaze remains still", "state the no-movement outcome without acting"),
}
RELATION_BANK = {f: (f"determine the {f} relation of red and blue", f"settle the {f} relation for red and blue", f"identify {f} placement of red") for f in FAMILIES}
REFERENCE_BANK = {f: (f"resolve the {f} relation from {{name}} to {{comparison}}", f"which {f} relation involves {{name}} and {{comparison}}", f"settle {f} placement of {{name}} against {{comparison}}") for f in FAMILIES}
TEMPORAL_BANK = {
    "prediction": ("state the change that should follow the action", "what transition is expected next", "identify the next transition"),
    "observed-change": ("state the change just observed", "identify the committed transition", "report the observed change"),
    "cause": ("state the cause of the latest change", "what action caused the transition", "identify the action responsible"),
}
BINDING_BANK = ("record {name} as the name for {color}", "use {name} to mean {color}", "make {name} refer to {color}")
CORRECTION_BANK = ("correct the reference: {name} means {color}", "revise {name} so it denotes {color}", "replace the old reference for {name} with {color}")
NEUTRAL_BANK = ("acknowledge the current field without changing the world", "inspect the present field without an action", "observe without committing")
GOAL_BANK = ("store this deferred mission: {a}, then {b}, then {c}", "remember this three-step order: {a}; {b}; {c}", "defer these actions until after restart: {a}, {b}, {c}")
AMBIGUITIES = (
    ("shift your gaze left or right", "ambiguous_action"),
    ("settle the relation between red and blue", "ambiguous_relation_family"),
    ("which state came first after the gaze was held still", "temporal_states_indistinguishable"),
    ("compare the unnamed object with blue", "missing_referent"),
    ("is it near blue", "missing_active_referent"),
)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def prf(tag: str, *parts: object) -> int:
    payload = "BLIND-LABYRINTH/v1|20260829|" + tag + "|" + "|".join(map(str, parts))
    return int.from_bytes(hashlib.sha256(payload.encode("utf-8")).digest()[:8], "big")


def fisher_yates(items: list[dict[str, Any]], phase: int, nonce: int) -> list[dict[str, Any]]:
    result = list(items)
    for i in range(len(result) - 1, 0, -1):
        j = prf("shuffle", phase, nonce, i) % (i + 1)
        result[i], result[j] = result[j], result[i]
    return result


def _record(kind: str, phase: int, ordinal: int) -> dict[str, Any]:
    return {"operation": kind, "phase": phase, "ordinal": ordinal}


def _arrange_phase(
    shuffled: list[dict[str, Any]],
    pinned: list[dict[str, Any]],
    phase: int,
) -> list[dict[str, Any]]:
    remaining = list(shuffled)
    fixed = list(pinned)
    if phase == 1:
        first_ambiguity = next(
            item for item in remaining if item["operation"] == "ambiguity-abstention"
        )
        remaining.remove(first_ambiguity)
        fixed.append(first_ambiguity)

    delayed = [
        item
        for item in remaining
        if item["operation"] in {"delayed-reference", "delayed-prediction"}
    ]
    predictions = [
        item for item in remaining if item["operation"] == "action-prediction"
    ]
    executions = [
        item for item in remaining if item["operation"] == "action-execution"
    ]
    named = [item for item in remaining if item["operation"] == "named-relation"]
    excluded = {id(item) for item in (*delayed, *predictions, *executions, *named)}
    middle = [item for item in remaining if id(item) not in excluded]

    hold_ambiguity: dict[str, Any] | None = None
    if phase == 4:
        hold_ambiguity = next(
            item for item in middle if item["operation"] == "ambiguity-abstention"
        )
        middle.remove(hold_ambiguity)

    leading_count = 19 - len(fixed) - len(predictions)
    if phase == 1:
        safe_kinds = {
            "generic-relation",
            "neutral-field-inference",
            "temporal-prediction",
        }
        safe = [item for item in middle if item["operation"] in safe_kinds]
        unsafe = [item for item in middle if item["operation"] not in safe_kinds]
        ordered_middle = safe + unsafe
    else:
        ordered_middle = middle
    leading = ordered_middle[:leading_count]
    leading_ids = {id(item) for item in leading}
    tail_middle = [item for item in middle if id(item) not in leading_ids]

    arranged = [
        *fixed,
        *predictions,
        *leading,
        named[0],
        executions[0],
    ]
    if hold_ambiguity is not None:
        arranged.append(hold_ambiguity)
    tail_items = [
        *tail_middle,
        *named[1:],
        *executions[1:],
    ]
    original_rank = {id(item): rank for rank, item in enumerate(shuffled)}
    arranged.extend(sorted(tail_items, key=lambda item: original_rank[id(item)]))
    unrelated_kinds = {
        "generic-relation",
        "named-relation",
        "pronoun-relation",
        "delayed-reference",
        "neutral-field-inference",
    }
    unrelated_since_execution = phase > 1
    index = 0
    while index < 44:
        kind = arranged[index]["operation"]
        if kind == "action-execution":
            unrelated_since_execution = False
        elif kind in unrelated_kinds:
            unrelated_since_execution = True
        elif kind == "temporal-interference" and not unrelated_since_execution:
            source_index = next(
                candidate
                for candidate in range(index + 1, 44)
                if arranged[candidate]["operation"] in unrelated_kinds
            )
            source = arranged.pop(source_index)
            arranged.insert(index, source)
            unrelated_since_execution = True
            index += 1
        index += 1
    arranged.extend(delayed)
    if len(arranged) != 50:
        raise RuntimeError("phase obligation repair changed the phase size")
    if any(
        item["operation"] not in {"delayed-reference", "delayed-prediction"}
        for item in arranged[44:]
    ):
        raise RuntimeError("phase delay obligations are not in the terminal slots")
    return arranged


def _valid_dependencies(rows: list[dict[str, Any]]) -> bool:
    predictions = {row["turn"]: row for row in rows if row["operation"] == "action-prediction"}
    for row in rows:
        if row["operation"] == "action-execution":
            source = predictions.get(row.get("source_prediction_turn"))
            if (
                source is None
                or source["turn"] >= row["turn"]
                or source["action"] != row["action"]
            ):
                return False
        elif row["operation"] in {"delayed-prediction", "delayed-reference"}:
            source_turn = row.get("source_turn")
            source = next((item for item in rows if item["turn"] == source_turn), None)
            expected_kind = (
                "action-execution"
                if row["operation"] == "delayed-prediction"
                else "named-relation"
            )
            if (
                source is None
                or source["operation"] != expected_kind
                or not 15 <= row["turn"] - source["turn"] <= 30
            ):
                return False
    ambiguities = [row for row in rows if row["operation"] == "ambiguity-abstention"]
    if not ambiguities or ambiguities[0]["turn"] != 7:
        return False
    hold_case = next(row for row in ambiguities if row["ambiguity_case"] == 2)
    predecessor = rows[hold_case["turn"] - 2]
    return (
        predecessor["operation"] == "action-execution"
        and predecessor["action"] == "action.hold"
    )


def _resolve_relation_payloads(rows: list[dict[str, Any]]) -> None:
    world = DeterministicQiWorld(seed=WORLD_SEED, session_id=SESSION_ID)
    bindings: dict[str, str] = {}
    active: str | None = None
    relation_kinds = {
        "generic-relation",
        "named-relation",
        "pronoun-relation",
        "delayed-reference",
    }
    for row in rows:
        kind = row["operation"]
        if kind in {"binding", "binding-correction"}:
            reference = f"reference.{row['color']}"
            previous = bindings.get(row["name"])
            bindings[row["name"]] = row["color"]
            if (
                kind == "binding-correction"
                and previous is not None
                and active == f"reference.{previous}"
            ):
                active = reference
            continue
        if kind == "action-execution":
            world.step(
                make_grounded_action_command(
                    world,
                    row["action"],
                    field_state_sha256="0" * 64,
                )
            )
            continue
        if kind not in relation_kinds:
            continue
        if kind == "generic-relation":
            subject = "reference.red"
            comparisons = ("reference.blue",)
        else:
            subject = (
                active
                if kind == "pronoun-relation"
                else f"reference.{bindings[row['name']]}"
            )
            if subject is None:
                raise RuntimeError("pronoun schedule has no active reference")
            start = row["comparison_index"] % len(COLORS)
            colors = COLORS[start:] + COLORS[:start]
            comparisons = tuple(
                f"reference.{color}"
                for color in colors
                if f"reference.{color}" != subject
            )
        family_start = FAMILIES.index(row["family"])
        families = FAMILIES[family_start:] + FAMILIES[:family_start]
        observation = observe_colored_objects(world)
        selected: tuple[str, str] | None = None
        for family in families:
            for comparison in comparisons:
                try:
                    spatial_relation_from_observation(
                        observation,
                        family,
                        subject_reference=subject,
                        comparison_reference=comparison,
                    )
                except CassiGroundedLanguageError:
                    continue
                selected = family, comparison
                break
            if selected is not None:
                break
        if selected is None:
            raise RuntimeError("relation schedule has no sensor-resolvable payload")
        row["family"], comparison_reference = selected
        row["comparison"] = comparison_reference.removeprefix("reference.")
        active = subject


def _generate_schedule_nonce(nonce: int) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    for phase, vector in enumerate(PHASE_VECTORS, 1):
        pinned: list[dict[str, Any]] = []
        if phase == 1:
            pinned = [_record("binding", phase, i) for i in range(6)]
        elif phase in (3, 4, 5):
            start = (phase - 3) * 2
            pinned = [
                _record("binding-correction", phase, start + index)
                for index in range(2)
            ]
        pool: list[dict[str, Any]] = []
        for index, count in enumerate(vector):
            kind = OPERATION_NAMES[index]
            already = sum(item["operation"] == kind for item in pinned)
            pool.extend(
                _record(kind, phase, already + offset)
                for offset in range(count - already)
            )
        phase_rows = _arrange_phase(fisher_yates(pool, phase, nonce), pinned, phase)
        base_turn = len(rows)
        for offset, item in enumerate(phase_rows, 1):
            item["turn"] = base_turn + offset
            item["family"] = FAMILIES[prf("family", item["turn"]) % len(FAMILIES)]
            item["name_index"] = prf("name", item["turn"], 0) % len(HELDOUT_NAMES)
            item["comparison_index"] = prf("comparison", item["turn"]) % len(COLORS)
            item["bank_index"] = (
                prf("bank", item["turn"], item["operation"], 0) % 3
            )
        if phase == 1:
            for index, item in enumerate(phase_rows[:6]):
                item.update(
                    name_index=index,
                    color=HELDOUT_BINDINGS[HELDOUT_NAMES[index]],
                )
        if phase in (3, 4, 5):
            start = (phase - 3) * 2
            for index, item in enumerate(phase_rows[:2]):
                item.update(
                    name_index=start + index,
                    color=CORRECTED_BINDINGS[HELDOUT_NAMES[start + index]],
                )

        predictions = [
            item for item in phase_rows if item["operation"] == "action-prediction"
        ]
        executions = [
            item for item in phase_rows if item["operation"] == "action-execution"
        ]
        for index, prediction in enumerate(predictions):
            prediction["action"] = GROUND_ACTIONS[
                prf("action", prediction["turn"]) % len(GROUND_ACTIONS)
            ]
            if phase == 4 and index == 0:
                prediction["action"] = "action.hold"
        for prediction, execution in zip(predictions, executions, strict=True):
            execution["action"] = prediction["action"]
            execution["source_prediction_turn"] = prediction["turn"]
        for item in phase_rows:
            item.setdefault(
                "action",
                GROUND_ACTIONS[prf("action", item["turn"]) % len(GROUND_ACTIONS)],
            )
        rows.extend(phase_rows)

    for row in rows:
        row.setdefault("color", HELDOUT_BINDINGS[HELDOUT_NAMES[row["name_index"]]])
        subject = COLORS[row["name_index"] % len(COLORS)]
        comparison = COLORS[row["comparison_index"]]
        if comparison == subject:
            comparison = COLORS[(row["comparison_index"] + 1) % len(COLORS)]
        row["comparison"] = comparison
        row["name"] = HELDOUT_NAMES[row["name_index"]]

    ambiguities = [row for row in rows if row["operation"] == "ambiguity-abstention"]
    for index, row in enumerate(ambiguities):
        case = 4 if index == 0 else index - 1
        row["ambiguity_case"] = case
        row["prompt"], row["reason"] = AMBIGUITIES[case]

    for row in rows:
        if row["operation"] == "delayed-prediction":
            candidates = [
                item
                for item in rows
                if item["operation"] == "action-execution"
                and 15 <= row["turn"] - item["turn"] <= 30
            ]
            source = min(
                candidates,
                key=lambda item: (row["turn"] - item["turn"], item["turn"]),
            )
            row.update(source_turn=source["turn"], source_action=source["action"])
        elif row["operation"] == "delayed-reference":
            candidates = [
                item
                for item in rows
                if item["operation"] == "named-relation"
                and 15 <= row["turn"] - item["turn"] <= 30
            ]
            source = min(
                candidates,
                key=lambda item: (row["turn"] - item["turn"], item["turn"]),
            )
            row.update(
                source_turn=source["turn"],
                name_index=source["name_index"],
                name=source["name"],
            )
    _resolve_relation_payloads(rows)
    if not _valid_dependencies(rows):
        raise RuntimeError("deterministic schedule obligation repair failed")
    return rows, nonce


def generate_schedule() -> tuple[list[dict[str, Any]], int]:
    return _generate_schedule_nonce(0)

def render_prompt(row: dict[str, Any], rows: Iterable[dict[str, Any]] = ()) -> str:
    kind = row["operation"]
    t = row["turn"]
    i = row.get("bank_index", prf("bank", t, kind, 0) % 3)
    action = row.get("action", GROUND_ACTIONS[prf("action", t) % 5])
    if kind == "binding":
        return BINDING_BANK[i].format(name=row["name"], color=row["color"])
    if kind == "binding-correction":
        return CORRECTION_BANK[i].format(name=row["name"], color=row["color"])
    if kind == "action-execution":
        return ACTION_BANK[action][i]
    if kind == "action-prediction":
        return ACTION_PREDICTION_BANK[action][i]
    if kind == "delayed-prediction":
        source_action = row.get("source_action", action)
        source_turn = row.get("source_turn", t)
        source_index = (
            prf("bank", source_turn, "action-execution", 0)
            % len(ACTION_BANK[source_action])
        )
        return (
            TEMPORAL_BANK["prediction"][i]
            + " Earlier action: "
            + ACTION_BANK[source_action][source_index]
            + "."
        )
    if kind == "generic-relation":
        return RELATION_BANK[row["family"]][i]
    if kind in {"named-relation", "delayed-reference"}:
        return REFERENCE_BANK[row["family"]][i].format(name=row["name"], comparison=row["comparison"])
    if kind == "pronoun-relation":
        return REFERENCE_BANK[row["family"]][i].format(name="it", comparison=row["comparison"])
    if kind in {"temporal-prediction", "temporal-observed-change", "temporal-cause"}:
        base = TEMPORAL_BANK[kind.removeprefix("temporal-")][i]
        if kind == "temporal-prediction":
            ai = prf("bank", t, "action-execution", 0) % len(ACTION_BANK[action])
            return base + " Candidate action: " + ACTION_BANK[action][ai] + "."
        return base
    if kind == "temporal-order":
        return "which state came first or second. " + _order_descriptor(row)
    if kind == "temporal-interference":
        return TEMPORAL_BANK["observed-change"][i] + "; inspect the present field without an action"
    if kind == "ambiguity-abstention":
        return row["prompt"]
    if kind == "neutral-field-inference":
        return NEUTRAL_BANK[i]
    raise ValueError(f"unknown operation {kind}")


def _order_descriptor(row: dict[str, Any]) -> str:
    # The oracle replaces this with live values; the runner supplies descriptors.
    return "State A=tick=0;x=+0.000000000;y=+0.000000000; State B=tick=0;x=+0.000000000;y=+0.000000000."


def mission_actions() -> tuple[str, str, str]:
    return tuple(GROUND_ACTIONS[prf("mission", i) % len(GROUND_ACTIONS)] for i in range(3))  # type: ignore[return-value]


def world_coordinates(world: DeterministicQiWorld) -> tuple[float, float]:
    return decode_proprioception(observe_proprioception(world))


@dataclass
class BlindLabyrinthOracle:
    world: DeterministicQiWorld
    bindings: dict[str, str]
    active: str | None = None
    transitions: list[dict[str, Any]] = field(default_factory=list)
    goal: tuple[str, ...] | None = None

    @classmethod
    def open(cls) -> "BlindLabyrinthOracle":
        return cls(DeterministicQiWorld(seed=WORLD_SEED, session_id=SESSION_ID), {})

    def expected(self, row: dict[str, Any]) -> dict[str, Any]:
        kind = row["operation"]
        if kind == "ambiguity-abstention":
            return {"route_id": "*", "abstained": True, "reason": row["reason"], "action": None, "relation": None, "reference": None, "temporal": None, "goal": None}
        if kind == "binding" or kind == "binding-correction":
            ref = "reference." + row["color"]
            previous = self.bindings.get(row["name"])
            old_ref = None if previous is None else "reference." + previous
            self.bindings[row["name"]] = row["color"]
            if kind == "binding-correction" and self.active == old_ref:
                self.active = ref
            return {"route_id": "route.binding", "abstained": False, "reason": None, "reference": ref, "action": None, "relation": None, "temporal": None, "goal": None}
        if kind in {"action-prediction", "delayed-prediction"}:
            action = row.get("source_action", row["action"])
            # A unit gaze move maps directly to one of the frozen changes.
            change = dict(zip(GROUND_ACTIONS, ("change.x-decrease", "change.x-increase", "change.y-increase", "change.y-decrease", "change.none"), strict=True))[action]
            return {"route_id": "route.prediction", "abstained": False, "reason": None, "action": action, "relation": None, "reference": None, "temporal": {"predicted_change": change}, "goal": None}
        if kind == "action-execution":
            before_tick = self.world.logical_tick
            before = world_coordinates(self.world)
            command = make_grounded_action_command(self.world, row["action"], field_state_sha256="0" * 64)
            self.world.step(command)
            after_tick = self.world.logical_tick
            after = world_coordinates(self.world)
            change = change_from_coordinates(before, after)
            self.transitions.append({"action": row["action"], "change": change, "before": before, "after": after, "before_tick": before_tick, "after_tick": after_tick})
            return {"route_id": "route.action", "abstained": False, "reason": None, "action": row["action"], "relation": None, "reference": None, "temporal": None, "goal": None}
        if kind in {"generic-relation", "named-relation", "delayed-reference", "pronoun-relation"}:
            if kind == "generic-relation":
                subject_ref, comparison_ref = "reference.red", "reference.blue"
                self.active = subject_ref
            else:
                subject_name = "it" if kind == "pronoun-relation" else row["name"]
                subject_ref = self.active if subject_name == "it" else "reference." + self.bindings[subject_name]
                comparison_ref = "reference." + row["comparison"]
                if subject_ref is None:
                    raise AssertionError("pronoun source is not established")
                self.active = subject_ref
            relation = spatial_relation_from_observation(observe_colored_objects(self.world), row["family"], subject_reference=subject_ref, comparison_reference=comparison_ref)
            return {"route_id": "route.spatial" if kind == "generic-relation" else "route.reference", "abstained": False, "reason": None, "action": None, "relation": relation, "reference": subject_ref, "temporal": None, "goal": None}
        if kind == "pronoun-relation":
            raise AssertionError("unreachable")
        latest = self.transitions[-1] if self.transitions else {"action": "action.hold", "change": "change.none"}
        if kind == "temporal-prediction":
            action = row["action"]
            change = dict(zip(GROUND_ACTIONS, ("change.x-decrease", "change.x-increase", "change.y-increase", "change.y-decrease", "change.none"), strict=True))[action]
            return {"route_id": "route.prediction", "abstained": False, "reason": None, "action": action, "relation": None, "reference": None, "temporal": {"predicted_change": change}, "goal": None}
        if kind in {"temporal-observed-change", "temporal-cause", "temporal-interference"}:
            temporal = {"action": latest["action"], "change": latest["change"], "cause": latest["action"].replace("action.", "cause.")}
            return {"route_id": "route.explanation", "abstained": False, "reason": None, "action": None, "relation": None, "reference": None, "temporal": temporal, "goal": None}
        if kind == "temporal-order":
            return {"route_id": "route.ordering", "abstained": False, "reason": None, "action": None, "relation": None, "reference": None, "temporal": {"target": "time.before", "position": "position.first"}, "goal": None}
        if kind == "neutral-field-inference":
            return {"route_id": "route.neutral", "abstained": False, "reason": None, "action": None, "relation": None, "reference": None, "temporal": None, "goal": None}
        raise ValueError(kind)


def expected_projection(receipt: dict[str, Any]) -> dict[str, Any]:
    return {key: receipt.get(key) for key in ("route_id", "abstained", "reason", "action", "relation", "reference", "temporal", "goal")}


__all__ = ["PROTOCOL", "PHASE_VECTORS", "HELDOUT_NAMES", "HELDOUT_BINDINGS", "CORRECTED_BINDINGS", "ACTION_BANK", "ACTION_PREDICTION_BANK", "RELATION_BANK", "REFERENCE_BANK", "TEMPORAL_BANK", "BINDING_BANK", "CORRECTION_BANK", "NEUTRAL_BANK", "GOAL_BANK", "AMBIGUITIES", "prf", "generate_schedule", "render_prompt", "mission_actions", "BlindLabyrinthOracle", "expected_projection", "canonical", "file_sha256", "CONFIG_PATH", "CHECKPOINT_PATH", "RUN_ROOT", "STATE_DIR", "SESSION_ID", "WORLD_SEED"]
