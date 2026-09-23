"""A world that changes mid-shift.

The Level-2 stations test whether a law can be recovered from observations.
This module tests something a single mission cannot: whether the recovered law
keeps being re-tested.  A shift is a sequence of rounds, each round one
Level-2 mission on a world whose hidden law may have changed since the previous
round.  Nothing in a round announces a change; the only signal is that the
observations no longer match the law the reader carried in.

Two quantities come out of a shift:

``detection``
    The first round after the switch in which the reader named the new law,
    and the latency in rounds.  A reader that freezes its first answer never
    detects anything.

``carry``
    How well the previous round's measured value predicts the current round's
    truth.  Carrying an answer is free while the world is still, and visibly
    wrong once it has moved, so the two regimes are separated by the plan's own
    controls rather than by the reader's prose.

The shift keeps the same resumable state file as the night shift: a restart
continues at the first unsettled round and the analysis is recomputed from the
rounds that were actually recorded.
"""
from __future__ import annotations

import json
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from laboratory import hidden as hidden_module
from laboratory import stations as stations_module
from laboratory.course import Agent, Course, ScriptedAgent, _load_receipt, _utc_now, receipt_digest, write_receipt
from laboratory.hidden import HiddenWorld
from laboratory.stations import LaboratoryError, Station

SHIFT_SCHEMA = "cassi.laboratory.shift.v1"
SHIFT_CANARY_SCHEMA = "cassi.laboratory.shift-canary.v1"

DEFAULT_SEQUENCE: tuple[str, ...] = (
    "L1-native-w25", "L1-native-w25", "L1-native-w25",
    "L4-equal-w81", "L4-equal-w81", "L4-equal-w81",
)
DEFAULT_SWITCH_ROUND = 3
CARRY_FLOOR = 0.05


@dataclass(frozen=True, slots=True)
class ShiftPlan:
    """The sequence of hidden laws and the round at which the first switch lands."""

    law_ids: tuple[str, ...]
    switch_round: int
    variant: str = "shift"

    def __post_init__(self) -> None:
        if len(self.law_ids) < 2:
            raise LaboratoryError("a shift needs at least two rounds")
        if not 1 <= self.switch_round < len(self.law_ids):
            raise LaboratoryError("the switch must land inside the shift, after round zero")

    def document(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "rounds": len(self.law_ids),
            "switch_round": self.switch_round,
            "law_ids": list(self.law_ids),
        }

    def worlds(self, **kwargs: Any) -> tuple[HiddenWorld, ...]:
        return hidden_module.hidden_worlds_for_laws(
            self.law_ids, variant_prefix=self.variant, **kwargs
        )


def _claim(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """What the reader said in one round, as the shift records it."""

    evidence = (receipt.get("agent") or {}).get("evidence") or {}
    identification = evidence.get("identification")
    identification = identification if isinstance(identification, Mapping) else {}
    measured = identification.get("measured")
    measured = measured if isinstance(measured, Mapping) else {}
    retention = evidence.get("retention")
    retention = retention if isinstance(retention, Mapping) else {}
    return {
        "claimed_law": str(identification.get("law_id", "")),
        "claimed_measured": measured.get("value"),
        "claimed_longest": str(retention.get("longest", "")),
    }


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


@dataclass
class ShiftingShift:
    """One bounded shift of rounds over a moving world."""

    plan: ShiftPlan
    state_path: str | Path
    receipt_dir: str | Path
    minutes: float | None = None
    worlds: tuple[HiddenWorld, ...] | None = None

    def _worlds(self) -> tuple[HiddenWorld, ...]:
        return self.worlds if self.worlds is not None else self.plan.worlds()

    def state(self) -> dict[str, Any]:
        loaded = _load_receipt(self.state_path) or {}
        loaded.setdefault("schema", SHIFT_SCHEMA)
        loaded.setdefault("rounds", {})
        return loaded

    # ------------------------------------------------------------------ run
    def run(
        self, agent_factory: Callable[[int], Agent], *, deadline_s: float = 900.0
    ) -> dict[str, Any]:
        started = time.monotonic()
        state = self.state()
        worlds = self._worlds()
        declared_plan = self.plan.document()
        if state.get("plan") not in (None, declared_plan):
            raise LaboratoryError(
                "this state file belongs to another shift plan; a shift cannot change its "
                "sequence or its switch round mid-flight"
            )
        state["plan"] = declared_plan
        previous_reader = str(state.get("agent_kind") or "")
        probe = agent_factory(0)
        reader = str(getattr(probe, "kind", type(probe).__name__))
        probe.close()
        if previous_reader and reader != previous_reader:
            raise LaboratoryError(
                f"this state file was written by {previous_reader!r}, not {reader!r}; a reader "
                "with memory of its own cannot be swapped in mid-shift"
            )
        previous_reader = state["agent_kind"] = reader
        settled_before = sorted(
            int(key) for key, item in state["rounds"].items() if item.get("verdict") == "pass"
        )
        state["resumed_from"] = settled_before or None
        for index, world in enumerate(worlds):
            key = str(index)
            if state["rounds"].get(key, {}).get("verdict") == "pass":
                continue
            if self.minutes is not None and (time.monotonic() - started) / 60.0 >= self.minutes:
                state["stopped_at_round"] = index
                state["reason"] = "shift ended"
                break
            course = Course(
                world,
                world.stations(),
                level="hidden",
                world_block=world.declared_world(),
                title=world.title(),
            )
            agent = agent_factory(index)
            round_reader = str(getattr(agent, "kind", type(agent).__name__))
            if round_reader != previous_reader:
                agent.close()
                raise LaboratoryError(
                    f"round {index} would be answered by {round_reader!r} while the shift is "
                    f"running {previous_reader!r}"
                )
            receipt_path = Path(self.receipt_dir) / f"round-{index:03d}.json"
            receipt = course.run(agent, receipt_path=receipt_path, deadline_s=deadline_s)
            agent.close()
            claim = _claim(receipt)
            state["rounds"][key] = {
                "index": index,
                "mission_id": receipt["identity"]["mission_id"],
                "fixture_id": receipt["identity"]["fixture_id"],
                "law_id": str(world.true_law_id),
                "verdict": receipt["verdict"],
                "station_verdicts": receipt["station_verdicts"],
                "receipt": receipt_path.name,
                "digest": receipt["digest"],
                **claim,
            }
            state["digest_strip"] = ["digest", "clock", "resumed_from"]
            state["updated_at"] = _utc_now()
            state["digest"] = receipt_digest(state)
            write_receipt(state, self.state_path)
        return self.analyse(state, seconds=time.monotonic() - started, worlds=worlds)

    # -------------------------------------------------------------- analysis
    def analyse(
        self,
        state: Mapping[str, Any],
        *,
        seconds: float | None = None,
        worlds: Sequence[HiddenWorld] | None = None,
    ) -> dict[str, Any]:
        """Recompute the shift's numbers from the rounds that were recorded."""

        declared_worlds = tuple(worlds) if worlds is not None else self._worlds()
        rounds = state.get("rounds") or {}
        ordered = [rounds[key] for key in sorted(rounds, key=lambda item: int(item))]
        truth_omega = {
            str(world.true_law_id): world.probe_omega(world.true_law) for world in declared_worlds
        }
        by_index = {int(item["index"]): item for item in ordered}

        def truth_of(index: int) -> float | None:
            item = by_index.get(index)
            return None if item is None else truth_omega.get(str(item["law_id"]))

        carry_by_round: dict[str, Any] = {}
        for index in range(1, len(declared_worlds)):
            previous, current = by_index.get(index - 1), by_index.get(index)
            if previous is None or current is None:
                carry_by_round[str(index)] = None
                continue
            claimed = _number(previous.get("claimed_measured"))
            truth = truth_of(index)
            if claimed is None or truth in (None, 0.0):
                carry_by_round[str(index)] = None
                continue
            carry_by_round[str(index)] = abs(claimed - float(truth)) / abs(float(truth))

        switch = self.plan.switch_round
        before = [carry_by_round[str(index)] for index in range(1, switch)]
        after = [carry_by_round[str(index)] for index in range(switch + 1, len(declared_worlds))]
        at_switch = carry_by_round.get(str(switch))

        detection_rounds = [
            int(item["index"])
            for item in ordered
            if int(item["index"]) >= switch and str(item.get("claimed_law", "")) == str(item.get("law_id", ""))
        ]
        first_correct = min(detection_rounds) if detection_rounds else None
        passes_after_switch = sum(
            1
            for item in ordered
            if int(item["index"]) >= switch and item.get("verdict") == "pass"
        )
        stale_after_switch = sum(
            1
            for index in range(switch + 1, len(declared_worlds))
            if (carry_by_round.get(str(index)) or 0.0) >= CARRY_FLOOR
        )

        sequence_laws = [str(world.true_law_id) for world in declared_worlds]
        predicted = {
            law_id: declared_worlds[0].probe_omega(hidden_module.law_by_id(declared_worlds[0].laws, law_id))
            for law_id in sorted(set(sequence_laws))
        }
        pairs: dict[str, Any] = {}
        for position, left_id in enumerate(sorted(predicted)):
            for right_id in sorted(predicted)[position + 1:]:
                pairs[f"{left_id}|{right_id}"] = abs(predicted[left_id] - predicted[right_id]) / max(
                    abs(predicted[left_id]), abs(predicted[right_id])
                )
        worst_pair = min(pairs.values()) if pairs else None
        previous_law = sequence_laws[switch - 1]
        current_law = sequence_laws[switch]
        switch_moves = abs(predicted[previous_law] - predicted[current_law]) / max(
            abs(predicted[previous_law]), abs(predicted[current_law])
        )
        constant_before = len(set(sequence_laws[:switch])) == 1

        controls = [
            {
                "name": "every law in the sequence is separated from the others",
                "ok": worst_pair is not None and worst_pair >= CARRY_FLOOR,
                "detail": (
                    "the declared measurement of the laws this shift visits differs by at least "
                    f"{worst_pair!r}; a tighter sequence would make a change unmeasurable"
                ),
                "numbers": {"worst_pairwise": worst_pair, "floor": CARRY_FLOOR, "pairs": pairs},
            },
            {
                "name": "the switch moves the measured quantity",
                "ok": switch_moves >= CARRY_FLOOR,
                "detail": (
                    f"round {switch} changes the measured value by {switch_moves:.4f} relative, so "
                    "a reader that carries its answer forward is visibly wrong"
                ),
                "numbers": {
                    "previous_law": previous_law,
                    "current_law": current_law,
                    "relative_move": switch_moves,
                    "floor": CARRY_FLOOR,
                },
            },
            {
                "name": "the world is still before the switch",
                "ok": constant_before,
                "detail": (
                    "rounds before the switch share one law, so any carry error there is the "
                    "reader's, not the world's"
                ),
                "numbers": {"laws_before_switch": sequence_laws[:switch]},
            },
        ]

        every_round_pass = bool(ordered) and len(ordered) == len(declared_worlds) and all(
            item.get("verdict") == "pass" for item in ordered
        )
        verdict = "pass" if every_round_pass and all(item["ok"] for item in controls) else "fail"

        receipt = {
            "schema": SHIFT_SCHEMA,
            "plan": self.plan.document(),
            "level": "hidden",
            "identity": {
                "variant": self.plan.variant,
                "world_ids": [world.fixture_id() for world in declared_worlds],
                "agent_kind": str((state.get("agent_kind") or "")),
            },
            "verdict": verdict,
            "rounds": [
                {
                    "index": int(item["index"]),
                    "law_id": str(item["law_id"]),
                    "claimed_law": str(item.get("claimed_law", "")),
                    "claimed_measured": item.get("claimed_measured"),
                    "claimed_longest": item.get("claimed_longest"),
                    "verdict": item.get("verdict"),
                    "station_verdicts": item.get("station_verdicts"),
                    "receipt": item.get("receipt"),
                    "digest": item.get("digest"),
                }
                for item in ordered
            ],
            "detection": {
                "switch_round": switch,
                "rounds_after_switch": len(declared_worlds) - switch,
                "first_correct_after_switch": first_correct,
                "latency": None if first_correct is None else first_correct - switch,
                "correct_rounds": detection_rounds,
                "passes_after_switch": passes_after_switch,
                "stale_rounds_after_switch": stale_after_switch,
                "detected": first_correct is not None,
            },
            "carry": {
                "definition": (
                    "the previous round's measured value, read as a prediction of this round's "
                    "true measured value, as a relative error; a round after the switch counts as "
                    f"stale when that error is at least {CARRY_FLOOR}"
                ),
                "by_round": carry_by_round,
                "max_before_switch": max([value for value in before if value is not None], default=0.0),
                "at_switch": at_switch,
                "max_after_switch": max([value for value in after if value is not None], default=0.0),
            },
            "controls": controls,
            "settled": sum(1 for item in ordered if item.get("verdict") == "pass"),
            "attempted": len(ordered),
            "resumed_from": state.get("resumed_from"),
            "declared_rounds": len(declared_worlds),
            "clock": {
                "finished_at": _utc_now(),
                "shift_seconds": None if seconds is None else round(seconds, 3),
            },
            "digest_strip": ["digest", "clock", "resumed_from"],
        }
        receipt["digest"] = receipt_digest(receipt)
        return receipt


# --------------------------------------------------------------------------- #
# scripted readers
# --------------------------------------------------------------------------- #


def tracking_answerer() -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    """Re-identifies the law in every round; the canary for a live reader."""

    return hidden_module.competent_agent()


def static_answerer() -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    """Identifies once, then carries that whole answer for the rest of the shift.

    The frozen reader keeps its law, its reading and its separation claim; the
    forecast and the lifetimes follow the law it named, so the only thing it
    never does again is look at the world.
    """

    memory: dict[str, Any] = {}

    def answer(exchange: Mapping[str, Any]) -> dict[str, Any]:
        brief, station = hidden_module._brief(exchange)
        if "evidence" not in memory:
            first = hidden_module._identify(brief)
            memory["evidence"] = {
                "law_id": str(first["law_id"]),
                "measured": dict(first["measured"]),
                "separation": dict(first["separation"]),
            }
        frozen = memory["evidence"]
        if station == "identification":
            return hidden_module.identify_as(
                brief,
                frozen["law_id"],
                measured=frozen["measured"],
                separation=frozen["separation"],
            )
        if station == "retention":
            return hidden_module._retention_answer(brief, frozen["law_id"])
        raise ValueError(f"unknown station {station!r}")

    return answer


def shortcut_answerer() -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    """Guesses without running anything, exactly like the other levels' control."""

    return hidden_module.shortcut_agent()


SHIFT_READERS: tuple[str, ...] = ("tracking", "static", "shortcut")


def reader_answerer(name: str) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    if name == "tracking":
        return tracking_answerer()
    if name == "static":
        return static_answerer()
    if name == "shortcut":
        return shortcut_answerer()
    raise LaboratoryError(f"unknown shift reader {name!r}")


def scripted_factory(name: str) -> Callable[[int], Agent]:
    """One agent factory per named reader, with the reader's own memory kept across rounds."""

    answerer = reader_answerer(name)

    def factory(_index: int) -> Agent:
        return ScriptedAgent(answerer=answerer, kind=f"shift-{name}")

    return factory


def shift_canary_report(
    plan: ShiftPlan | None = None,
    *,
    receipt_dir: str | None = None,
    deadline_s: float = 900.0,
) -> dict[str, Any]:
    """Run the three scripted readers through a real shift and compare them."""

    declared = plan or ShiftPlan(DEFAULT_SEQUENCE, DEFAULT_SWITCH_ROUND)
    worlds = declared.worlds()
    root = Path(receipt_dir) if receipt_dir is not None else Path(tempfile.mkdtemp(prefix="cassi-shift-canary-"))
    runs: dict[str, Any] = {}
    for name in SHIFT_READERS:
        shift = ShiftingShift(
            declared,
            state_path=root / f"shift-{name}-state.json",
            receipt_dir=root,
            worlds=worlds,
        )
        receipt = shift.run(scripted_factory(name), deadline_s=deadline_s)
        runs[name] = {
            "verdict": receipt["verdict"],
            "detection": receipt["detection"],
            "carry": receipt["carry"],
            "rounds": [
                {
                    "index": item["index"],
                    "law_id": item["law_id"],
                    "claimed_law": item["claimed_law"],
                    "verdict": item["verdict"],
                }
                for item in receipt["rounds"]
            ],
            "controls": receipt["controls"],
            "digest": receipt["digest"],
        }
    controls_ok = all(item["ok"] for item in runs["tracking"]["controls"])
    return {
        "schema": SHIFT_CANARY_SCHEMA,
        "plan": declared.document(),
        "receipt_dir": str(root),
        "readers": runs,
        "discriminates": bool(
            runs["tracking"]["verdict"] == "pass"
            and runs["tracking"]["detection"]["latency"] == 0
            and runs["static"]["detection"]["latency"] is None
            and runs["static"]["verdict"] != "pass"
            and runs["shortcut"]["verdict"] != "pass"
            and controls_ok
        ),
    }


__all__ = [
    "SHIFT_SCHEMA",
    "SHIFT_CANARY_SCHEMA",
    "DEFAULT_SEQUENCE",
    "DEFAULT_SWITCH_ROUND",
    "CARRY_FLOOR",
    "ShiftPlan",
    "ShiftingShift",
    "tracking_answerer",
    "static_answerer",
    "shortcut_answerer",
    "SHIFT_READERS",
    "reader_answerer",
    "scripted_factory",
    "shift_canary_report",
]
