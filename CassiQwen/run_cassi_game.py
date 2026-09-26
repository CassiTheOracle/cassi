"""Run a game Cassi plays, and watch it happen.

    python run_cassi_game.py probe --turns 6
    python run_cassi_game.py play --player scripted --turns 40
    python run_cassi_game.py play --player brain --turns 60 --port 8099

`probe` checks the world alone: does a life start, does the screen read, does a
step land.  `play` runs the full loop with the watch page open, so the game can
be watched while it is being played.  Every run writes a receipt with the whole
journal under `games/runs/<stamp>/`.
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
import time

try:  # a detached campaign only keeps its work if the stop is heard
    import signal as _signal
except ImportError:  # pragma: no cover - every platform Python here has it
    _signal = None
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from games.fieldmemory import (  # noqa: E402
    INTENT_KINDS,
    INTENTS,
    DungeonField,
    Route,
    aim_words,
    field_parameters,
)
from games.livingmemory import (
    STANDING_LIVES,
    SEEK_LIMIT,  # noqa: E402
    Asking,  # noqa: E402
    DEFAULT_HOME,
    NO_MEMORY,
    SITUATION_FIELDS,
    Lesson,
    GameMemory,
    Memories,
    NoMemory,
    Recollection,
    Situation,
    lesson_source_id,
)
from games.player import (  # noqa: E402
    BrainPlayer,
    BrainRequiredError,
    Decision,
    Player,
    ReflectedLesson,
    _glyph,
    make_player,
    monsters_beside,
    player_place,
    route_wake,
)
from games.view import DEFAULT_PORT, WatchView  # noqa: E402
from games.world import Action, Observation, create_world  # noqa: E402

RUNS = HERE / "games" / "runs"


def summarize(observation: Observation) -> Mapping[str, Any]:
    summary = observation.summary
    return {
        "turn": observation.turn,
        "depth": summary.get("depth"),
        "hp": summary.get("hp"),
        "hp_max": summary.get("hp_max"),
        "armor": summary.get("armor"),
        "gold": summary.get("gold"),
        "turns": summary.get("turns"),
        "character": summary.get("character"),
        "moved": summary.get("moved"),
        "message": observation.summary.get("message"),
        "done": observation.done,
    }


def panel(observation: Observation) -> Mapping[str, Any]:
    summary = observation.summary
    stats: dict[str, Any] = {}
    if summary.get("character"):
        stats["playing"] = summary["character"]
    if summary.get("depth") is not None:
        stats["depth"] = summary["depth"]
    if summary.get("hp") is not None:
        stats["health"] = f"{summary.get('hp')}/{summary.get('hp_max', '?')}"
    if summary.get("armor") is not None:
        stats["armour"] = summary["armor"]
    if summary.get("gold") is not None:
        stats["gold"] = summary["gold"]
    if summary.get("turns") is not None:
        stats["game turns"] = summary["turns"]
    stats["decisions"] = observation.summary.get("turn")
    if summary.get("alignment"):
        stats["alignment"] = summary["alignment"]
    return stats


# How often the field is asked what a situation wakes when the situation has
# not changed: often enough that a long stay still hears from its memories,
# rarely enough that a long life does not spend its region on revisions.
MATCH_EVERY = 10

# A condition wakes its lesson once in a while rather than on every event: a
# lesson about being blocked is not news on the fifth blocked turn in a row.
CONDITION_COOLDOWN = 5


def situation_context(
    observation: Observation,
    journal: Sequence[Mapping[str, Any]],
    route: Route | None = None,
) -> tuple[Mapping[str, Any], tuple[str, ...]]:
    """What is true of the player right now, in the words a lesson is filed by.

    Only what a player can see from the keyboard: the last action refused, a
    monster beside it, health below its best, a known way onward being followed,
    and a level it has just arrived on.
    """
    summary = observation.summary
    health, full = summary.get("hp"), summary.get("hp_max")
    hurt = isinstance(health, int) and isinstance(full, int) and health < full
    blocked = bool(journal) and journal[-1].get("moved") is False
    beside = monsters_beside(observation.screen)
    depth = summary.get("depth")
    on_stairs = bool(route is not None and route.aim in ("down", "up"))
    fresh = len([row for row in journal if row.get("depth") == depth]) <= 3
    context: dict[str, Any] = {
        "always": True,
        "blocked": blocked,
        "monster": bool(beside),
        "hurt": hurt,
        "stairs": on_stairs,
        "exploring": not (blocked or beside or hurt or on_stairs),
        "new_level": fresh,
        "depth": depth if isinstance(depth, int) else 0,
        "monsters": list(beside),
    }
    situations = tuple(
        name for name, field in SITUATION_FIELDS.items() if context.get(field)
    )
    return context, situations


def life_outcome(
    observation: Observation | None,
    journal: Sequence[Mapping[str, Any]],
    start_depth: int | None,
) -> tuple[str, int | None, bool, int]:
    """How the life went: what ended it, how deep it got, and whether it moved."""
    depths = [
        row["depth"]
        for row in journal
        if isinstance(row.get("depth"), int)
    ]
    reached = max(depths) if depths else start_depth
    descended = bool(
        isinstance(reached, int) and isinstance(start_depth, int) and reached > start_depth
    )
    if observation is not None and observation.done:
        ending = "the life ended on the game's own terms"
    else:
        ending = "the run stopped before the life did"
    return ending, reached, descended, len(journal)


def life_story(
    journal: Sequence[Mapping[str, Any]],
    levels: Mapping[str, Any],
    *,
    ending: str,
    reached: int | None,
) -> str:
    """What the life actually did, in the game's own terms, for the reflection."""
    lines: list[str] = []
    for depth in sorted(levels, key=lambda value: int(value)):
        state = levels[depth]
        ways = ", ".join(
            f"a way {goal[2]} at {goal[0]},{goal[1]}" for goal in state.get("goals") or ()
        ) or "no way onward found"
        lines.append(
            f"  level {depth}: you saw {state.get('known_cells', 0)} cells, walked "
            f"{state.get('walked_cells', 0)} of them, {ways}; "
            f"{len(state.get('blocked_cells') or ())} cells refused you"
        )
    notable = [
        row
        for row in journal
        if row.get("wake") or row.get("depth") != journal[0].get("depth")
    ][:10]
    for row in notable:
        lines.append(
            f"  turn {row['turn']} at depth {row.get('depth')}: {row['label']} "
            f"({row.get('note') or 'nothing happened'})"
        )
    for row in journal[-8:]:
        lines.append(
            f"  turn {row['turn']} at depth {row.get('depth')}: {row['label']} "
            f"({row.get('note') or 'nothing happened'})"
        )
    lines.append(f"  ending: {ending}, deepest level {reached}")
    return "\n".join(lines)


def hopeless_lessons(
    autobiography: Mapping[str, Any], *, threshold: int = 2
) -> list[str]:
    """Lesson bindings acted on in lives that got nowhere, more than once.

    The evidence is the field's own: the uses it recorded, and the usefulness
    the outcome of each use was assessed at.  One bad life is noise; a lesson
    that was acted on and led nowhere twice has stopped earning its place.
    """
    counts: dict[str, int] = {}
    for view in autobiography.get("episodes") or ():
        if not isinstance(view, Mapping):
            continue
        assessment = ((view.get("assessment") or {}).get("payload") or {})
        use = ((view.get("use") or {}).get("payload") or {})
        usefulness = assessment.get("usefulness")
        if not isinstance(usefulness, (int, float)) or isinstance(usefulness, bool):
            continue
        if float(usefulness) > 0.0:
            continue
        for ref in use.get("selected_refs") or ():
            key = str((ref or {}).get("id") or "")
            if key:
                counts[key] = counts.get(key, 0) + 1
    return sorted(key for key, count in counts.items() if count >= threshold)


def lesson_use(
    journal: Sequence[Mapping[str, Any]],
) -> list[tuple[str, str]]:
    """The remembered lessons the brain said decided its actions, in order.

    A decision cites a memory by the number it was shown at, and the journal
    keeps which memory that was -- whether the field woke it for the moment or
    the mind asked for it.  So the citation is bound by identity, not by a
    number that only meant something while that decision was being made.
    """

    cited: list[tuple[str, str]] = []
    for row in journal:
        if not row.get("used"):
            continue
        key = str(row.get("used_id") or "")
        if key and all(key != seen for seen, _text in cited):
            cited.append((key, str(row.get("used_text") or "")))
    return cited



def ask_the_field(
    question: str,
    *,
    living: Any,
    asked: dict[str, Asking],
    seeks: list[tuple[str, Recollection]],
    refused: list[dict[str, str]],
    label: str,
) -> Asking:
    """The mind asked for something: one look, once, within the life's allowance.

    A question this life has already asked is answered from the reading it has --
    the field is not asked twice for the same thing -- and once the life's
    questions are spent the field says so, and the decision stands on what the
    life already has.
    """
    key = " ".join(question.lower().split())
    earlier = asked.get(key)
    if earlier is not None:
        return replace(earlier, status="repeated")
    if len(seeks) >= SEEK_LIMIT:
        refused.append({"question": question, "why": "asked all it can this life"})
        return Asking(question=question, status="exhausted")
    recollection = living.recall(question, label=label)
    seeks.append((question, recollection))
    asking = Asking(
        question=question,
        lessons=recollection.lessons,
        status=recollection.status,
        episode=recollection.episode,
    )
    asked[key] = asking
    return asking


def close_life(
    *,
    memory: Any,
    recollection: Recollection,
    journal: Sequence[Mapping[str, Any]],
    seeks: Sequence[tuple[str, Recollection]] = (),
    observation: Observation | None,
    dungeon: DungeonField | None,
    player: Any,
    life: str,
    start_depth: int | None,
    situational_lessons: Sequence[Lesson] = (),
    error: str = "",
    briefing: Mapping[str, Any] | None = None,
    refused: Sequence[Mapping[str, str]] = (),
    allow_reflection: bool = True,
) -> Mapping[str, Any]:
    """Settle the recollection, look back on the life, and file what it taught.

    The order is the point: the recollection is bound to the decisions that
    cited it (or settled as unused when none did), the life's outcome settles
    that use, and only then does the brain say what the life taught -- so the
    lesson is written into memory that already knows how the life ended.
    """
    ending, reached, descended, turns = life_outcome(observation, journal, start_depth)
    cited = lesson_use(journal)
    if situational_lessons and not recollection.episode:
        # These were read from field-owned relevance conditions during play.
        # Keep their identity for the life verdict without a second, exhaustive
        # query over every lesson ever filed in this workspace.
        seen: dict[str, Lesson] = {}
        for lesson in situational_lessons:
            if lesson.source_id:
                seen.setdefault(lesson.source_id, lesson)
        recollection = Recollection(
            concern="memories woken during this life",
            status="supported",
            episode={},
            lessons=tuple(seen.values()),
        )
        cited_ids = {key for key, _ in cited}
        if any(lesson.source_id in cited_ids for lesson in seen.values()):
            recollection = memory.recall_woken(
                recollection.lessons, label=f"{life}:woken"
            )
    levels = (dungeon.state().get("levels") or {}) if dungeon is not None else {}
    story = life_story(journal, levels, ending=ending, reached=reached)
    if descended:
        usefulness, why = 1.0, "the life went down a level"
    elif turns >= 5:
        usefulness, why = 0.25, "the life moved but did not descend"
    else:
        usefulness, why = 0.0, "the life barely started"
    consequence: dict[str, Any] = {
        "kind": "life-ended",
        "ending": ending,
        "depth": reached,
        "turns": turns,
        "descended": descended,
        "cells": len({tuple(row["cell"]) for row in journal if row.get("cell")}),
    }
    # A life leans on the recollection it was handed and on whatever it asked
    # the field for.  Each of those is bound and settled on its own, because the
    # field accepts one use per recollection -- and that one use credits every
    # memory it carried, so a life that half worked still says which half.
    times_cited: dict[str, int] = {}
    for key, _text in cited:
        times_cited[key] = times_cited.get(key, 0) + 1
    # What the mind asked for is credited before what it was handed, and a
    # memory is credited once however many readings carried it: a life acted on
    # one thing, and it should not earn twice for it.
    readings: list[tuple[str, Any, str]] = []
    for index, (question, asked) in enumerate(seeks, start=1):
        readings.append((f'you asked: "{question}"', asked, f"{life}:seek{index}"))
    readings.append(("what the life was handed", recollection, f"{life}:use"))
    uses: list[dict[str, Any]] = []
    credited: set[str] = set()
    settled_by: dict[str, bool] = {}
    acted_on: dict[str, Any] = {}
    for what, reading, label in readings:
        carried = [
            lesson
            for lesson in reading.lessons
            if lesson.source_id and lesson.source_id in times_cited
        ]
        lessons_here: list[Any] = []
        for lesson in carried:
            if not lesson.ref or lesson.source_id in credited:
                continue
            if any(seen.source_id == lesson.source_id for seen in lessons_here):
                continue
            lessons_here.append(lesson)
            acted_on.setdefault(lesson.source_id, lesson)
        identifier = {
            lesson.source_id: times_cited.get(lesson.source_id, 0)
            for lesson in lessons_here
        }
        if not lessons_here:
            reason = (
                "no decision cited a memory it carried"
                if not carried
                else "what it carried was credited where the mind asked for it"
            )
            memory.unused(reading, reason=reason, label=f"{label}:unused")
            uses.append(
                {"what": what, "episode_id": "", "lessons": [], "settled": False, "unused": reason}
            )
            continue
        episode = memory.used(
            reading,
            consumer={
                "kind": "nethack-life",
                "life": life,
                "lessons": [lesson.text[:160] for lesson in lessons_here],
            },
            lessons=lessons_here,
            label=label,
        )
        settlement = memory.settle(
            episode=episode,
            outcome_id=f"{label}:outcome",
            consequence={
                **consequence,
                "lessons": [lesson.text[:160] for lesson in lessons_here],
                "cited": identifier,
            },
            usefulness=usefulness,
            renewal={"strength": usefulness, "reason": why},
            label=f"{label}:outcome",
        )
        settled = bool(
            isinstance(settlement, Mapping)
            and (settlement.get("lifecycle") or {}).get("settled")
        )
        for lesson in lessons_here:
            settled_by[lesson.source_id] = settled
            credited.add(lesson.source_id)
        uses.append(
            {
                "what": what,
                "episode_id": str((episode or {}).get("id") or ""),
                "lessons": [lesson.source_id for lesson in lessons_here],
                "cited": identifier,
                "settled": settled,
            }
        )
    # What the field's own lives now say each of them has earned.
    history = memory.autobiography(limit=STANDING_LIVES, label=f"{life}:standing")["episodes"]
    verdicts: list[dict[str, Any]] = []
    for key, text in cited:
        lesson = acted_on.get(key)
        if lesson is None:
            continue
        earned = memory.standing(lesson, episodes=history)
        verdicts.append(
            {
                "lesson": lesson.text[:160],
                "source_id": lesson.source_id,
                "cited": times_cited.get(lesson.source_id, 0),
                "usefulness": usefulness,
                "settled": settled_by.get(lesson.source_id, False),
                "earned": earned["usefulness"],
                "priority": earned["priority"],
                "verdicts": earned["verdicts"],
            }
        )
    standing_filed: dict[str, Any] = {}
    reflection: dict[str, Any] = {"life": "", "lessons": []}
    written: dict[str, Any] = {"lessons": [], "life": None}
    registered: list[Mapping[str, Any]] = []
    sharpened: list[Mapping[str, Any]] = []
    set_aside: list[Mapping[str, Any]] = []
    reflect: Any = getattr(player, "reflect", None) if allow_reflection else None
    if callable(reflect):
        lessons, summary = reflect(
            story=story,
            outcome=f"{ending}; deepest level {reached}",
            depth=reached,
            turns=turns,
            remembered=recollection.prompt(),
        )
        reflection = {"life": summary, "lessons": [lesson.as_dict() for lesson in lessons]}
        written["lessons"] = []
        for lesson in lessons:
            earlier = recollection.cited(lesson.sharpens)
            if earlier is not None and earlier.text != lesson.text:
                # The brain is sharpening a lesson it already knew: the evidence
                # stays as it was learned, the reading of it gets sharper.
                memory.reinterpret(
                    earlier,
                    wording=lesson.text,
                    when=lesson.when,
                    label=f"{life}:means:{lesson.sharpens}",
                )
                sharpened.append(
                    {
                        "was": earlier.text[:160],
                        "now": lesson.text[:160],
                        "when": list(lesson.when),
                    }
                )
                continue
            written["lessons"].append(
                memory.remember_lesson(
                    lesson.text, depth=reached, life=life, labels=("reflection",)
                )
            )
        written["life"] = memory.remember_life(
            summary or f"{ending} at depth {reached} after {turns} decisions",
            life=life,
            depth=reached,
            turns=turns,
        )
        # The field already selected its current bindings. Read their exact
        # sources once to file new lessons, rather than re-querying each one as
        # a fresh workspace-wide recollection after every life.
        inventory = memory.filed_lessons()
        known = {source_id: item[0] for source_id, item in inventory.items()}
        filed_ids: set[str] = set()
        for reflected in lessons:
            filed = known.get(lesson_source_id(reflected.text))
            if filed is None and reflected.sharpens:
                # a sharpening already has a home: the lesson it sharpens
                filed = recollection.cited(reflected.sharpens)
            if filed is None or not filed.ref:
                continue
            earned = memory.standing(filed, episodes=history)
            standing_filed[filed.source_id] = {"lesson": filed.text[:160], **earned}
            memory.register_lesson(
                filed,
                reflected.when,
                wording=reflected.text,
                priority=float(earned["priority"]),
                cooldown=CONDITION_COOLDOWN,
                label=f"{life}:when:{filed.source_id}",
            )
            filed_ids.add(filed.source_id)
            registered.append(
                {"lesson": reflected.text[:160], "when": list(reflected.when)}
            )
        # File lessons learned before situational conditions were available.
        # Existing conditions only need revision when the life actually cited
        # their lesson and its earned standing changed.
        for source_id, (lesson, moments) in inventory.items():
            if source_id in filed_ids or not lesson.ref:
                continue
            earned = memory.standing(lesson, episodes=history)
            standing_filed[source_id] = {"lesson": lesson.text[:160], **earned}
            if moments and source_id not in times_cited:
                continue
            for situation_name, wording in (moments or {"always": ""}).items():
                memory.register_lesson(
                    lesson,
                    (situation_name,),
                    wording=wording,
                    priority=float(earned["priority"]),
                    cooldown=CONDITION_COOLDOWN,
                    label=f"{life}:when-existing:{source_id}",
                )
                registered.append(
                    {"lesson": lesson.text[:160], "when": [situation_name]}
                )
            filed_ids.add(source_id)
        # A lesson that was acted on and led nowhere, twice, stops being offered.
        for ref_id in hopeless_lessons(
            memory.autobiography(limit=64, label=f"{life}:review")
        ):
            lesson = next(
                (row for row in known.values() if row.ref.get("id") == ref_id), None
            )
            if lesson is None or not lesson.ref:
                continue
            memory.demote(
                lesson,
                cue=lesson.text[:160],
                reason="acted on in lives that made no progress",
                label=f"{life}:set-aside:{ref_id}",
            )
            set_aside.append({"lesson": lesson.text[:160], "ref": ref_id})
    return {
        "mode": "none" if isinstance(memory, NoMemory) else "field",
        "home": str(getattr(memory, "home", "")),
        "error": error,
        "recall": recollection.as_dict(),
        "cited": [text for _key, text in cited],
        "uses": uses,
        "seeks": [
            {
                "question": question,
                "status": asked.status,
                "lessons": [lesson.text[:160] for lesson in asked.lessons],
            }
            for question, asked in seeks
        ],
        "refused": [dict(row) for row in refused],
        "outcome": consequence,
        "usefulness": usefulness,
        "reflection": reflection,
        "written": written,
        "conditions_registered": registered,
        "sharpened": sharpened,
        "briefing": dict(briefing or {}),
        "standing": standing_filed,
        "verdicts": verdicts,
        "set_aside": set_aside,
        "autobiography": memory.autobiography(limit=6, label=f"{life}:autobiography"),
        "maintenance": memory.maintain(purpose="after-a-life", label=f"{life}:maintenance"),
        "awareness": memory.awareness(label=f"{life}:awareness"),
        "counters": memory.as_dict(),
    }


CAMPAIGN_TURNS = 600
"""Decisions in one life of a campaign: long enough to explore and descend."""

PLAY_TURNS = 40
"""Decisions in one life of a single run: a bounded look at how it plays."""

DEATH_PAUSE = 3.0
"""Seconds the page holds the last screen of a life before the next one starts."""

MAX_CONSECUTIVE_FAILURES = 3
"""Lives that cannot even start, in a row, before a campaign stops trying."""

ASCENDED = ("You have ascended", "ascend to the status", "Demigod", "Almighty")
"""What the endgame says when the Amulet makes it back up: the goal, reached."""


def open_memory(args: argparse.Namespace) -> tuple[Any, str]:
    """Open the field home the mind lives in, once per process.

    A campaign opens it once and every life writes into the same memory; a home
    that will not open costs the memory, not the game.
    """
    if not args.living:
        return NO_MEMORY, ""
    try:
        return GameMemory(args.memory_home), ""
    except Exception as exc:
        return NO_MEMORY, f"{type(exc).__name__}: {exc}"


# Creating this file in a campaign directory stops the campaign between turns,
# which is the only stop that works on a process nobody is watching: no signal,
# no console, and the life in progress still gets to finish properly.
STOP_FILE = "STOP"


def life_label(campaign: str, index: int, attempt: str = "") -> str:
    """The name of one life in a campaign, unique to the attempt that plays it.

    The field binds every operation to its label and refuses to let a label mean
    two different things, so a life that has to be played again -- a restart, a
    crash, a hand on the keyboard -- gets a label of its own rather than
    inheriting the name of the attempt that did not finish.
    """
    return f"{campaign}-L{index:04d}-{attempt or datetime.now().strftime('%H%M%S')}"


def memory_home_bytes(home: Any) -> int:
    """How much the mind's home weighs on disk, so its growth stays visible."""
    if not home:
        return 0
    root = Path(home)
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def longest_stall(journal: Sequence[Mapping[str, Any]]) -> int:
    """The longest run of decisions after which the character had not moved."""
    run = longest = 0
    for row in journal:
        if row.get("moved") is False:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return longest


def campaign_row(
    receipt: Mapping[str, Any],
    index: int,
    label: str,
    home_bytes: int,
) -> dict[str, Any]:
    """One line of the campaign's record: what this life did and what it left."""
    final = receipt.get("final") or {}
    journal = receipt.get("journal") or []
    depths = [row.get("depth") for row in journal if isinstance(row.get("depth"), int)]
    living = receipt.get("living") or {}
    return {
        "life": index,
        "label": label,
        "started_at": receipt.get("started_at"),
        "wall_seconds": receipt.get("wall_seconds"),
        "turns": len(journal),
        "depth": final.get("depth"),
        "deepest": max(depths) if depths else final.get("depth"),
        "died": bool(final.get("done")),
        "hp": final.get("hp"),
        "hp_max": final.get("hp_max"),
        "message": str(final.get("message") or "")[:160],
        "won": any(
            marker in line
            for line in (final.get("screen_tail") or ())
            for marker in ASCENDED
        ),
        "stall": longest_stall(journal),
        "lessons": [str(row)[:160] for row in (living.get("written") or [])],
        "standing": {
            key: {"verdicts": row.get("verdicts"), "priority": row.get("priority")}
            for key, row in (living.get("standing") or {}).items()
        },
        "verdicts": living.get("verdicts") or [],
        "home_bytes": home_bytes,
        "receipt": str(receipt.get("receipt") or ""),
    }


def campaign_line(row: Mapping[str, Any]) -> str:
    """The campaign's line for one life, as a person reads it."""
    minutes = float(row.get("wall_seconds") or 0.0) / 60.0
    ended = "WON" if row.get("won") else ("died" if row.get("died") else "stopped")
    earners = sum(
        1
        for value in (row.get("standing") or {}).values()
        if isinstance(value, Mapping) and (value.get("verdicts") or 0)
    )
    return (
        f"life {int(row.get('life') or 0):>3}  deepest {row.get('deepest')}  {ended}  "
        f"turns {row.get('turns')}  {minutes:.1f} min  HP {row.get('hp')}/{row.get('hp_max')}  "
        f"lessons {len(row.get('lessons') or [])}  earning {earners}  "
        f"stall {row.get('stall')}  home {((row.get('home_bytes') or 0) / 1e6):.1f} MB"
        + (f"  -- {row['message'][:64]}" if row.get("message") else "")
    )


def publish_frame(
    watch: WatchView,
    world: Any,
    observation: Observation,
    player: Any,
    journal: Sequence[Mapping[str, Any]],
    decision: Any,
    life_number: int,
    *,
    ended: bool = False,
) -> None:
    """Show the page what the life sees, and where the life stands."""
    latency = getattr(player, "last_latency", 0.0)
    watch.publish(
        screen=observation.screen,
        stats=panel(observation),
        message=str(observation.summary.get("message") or ""),
        status=(
            (f"life {life_number} · " if life_number else "")
            + f"{player.name} · decision {observation.turn} · "
            f"depth {observation.summary.get('depth', '?')} · "
            f"HP {observation.summary.get('hp', '?')}"
            + (f" · {latency:.1f}s" if latency else "")
            + (" · the life ended" if ended else "")
        ),
        decision=decision,
        journal=[
            {
                "turn": item["turn"],
                "label": item["label"],
                "reason": item["reason"],
            }
            for item in journal[-14:]
        ],
        title=str(observation.summary.get("character") or world.name),
        prose_rows=getattr(world, "PROSE_ROWS", ()),
    )


def play_life(
    args: argparse.Namespace,
    *,
    living: Any,
    memory_error: str = "",
    watch: WatchView | None = None,
    url: str = "",
    life_label: str = "",
    life_number: int = 0,
    run_dir: Path | None = None,
    stop_file: Path | None = None,
    surface_broker: Any | None = None,
    surface_mission_id: str = "",
    surface_grant_id: Any = None,
    world: Any | None = None,
    surface_backend: Any | None = None,
    player: Player | None = None,
) -> Mapping[str, Any]:
    """Play one bounded life, close it out into the field, and write its receipt.

    A life is the unit the mind learns in: one character, one death or stopping
    point, one recollection bound to the decisions it decided.  What outlives a
    life -- the memory home, the watch page, the campaign's log -- belongs to
    the caller.
    """
    if getattr(args, "surface", False) and surface_broker is None:
        raise RuntimeError("--surface requires an injected live SurfaceBroker")
    if surface_broker is not None and not surface_mission_id:
        raise RuntimeError("Surface mode requires the host mission_id")
    if surface_backend is not None and surface_broker is None:
        raise RuntimeError("a pre-registered Surface backend requires its host broker")
    if surface_broker is not None and world is None:
        raise RuntimeError(
            "hosted Surface play requires an explicitly configured NetHack world"
        )
    if world is None:
        world = create_world(
            "nethack", allow_save=getattr(args, "mode", "play") != "campaign"
        )
    elif getattr(world, "name", None) != "nethack":
        raise RuntimeError("hosted game world must be the NetHack world")
    if surface_broker is not None and (
        not getattr(world, "preserve_existing_state", False)
        or getattr(world, "write_config", True)
        or getattr(world, "allow_save", True)
    ):
        raise RuntimeError(
            "hosted NetHack requires preserve_existing_state, write_config=False, and allow_save=False"
        )
    configured_broker = getattr(world, "_surface_broker", None)
    configured_backend = getattr(world, "_surface_backend", None)
    if surface_broker is not None:
        if configured_broker is not None and configured_broker is not surface_broker:
            raise RuntimeError("game world is already bound to a different SurfaceBroker")
        if (
            surface_backend is not None
            and configured_backend is not None
            and configured_backend is not surface_backend
        ):
            raise RuntimeError("game world is already bound to a different Surface backend")
        if configured_broker is None or (
            surface_backend is not None and configured_backend is None
        ):
            configure = getattr(world, "configure_surface", None)
            if not callable(configure):
                raise RuntimeError(f"world {world.name!r} cannot bind a Surface terminal source")
            if surface_backend is None:
                configure(surface_broker, surface_mission_id, surface_grant_id)
            else:
                configure(
                    surface_broker,
                    surface_mission_id,
                    surface_grant_id,
                    surface_backend=surface_backend,
                )
    elif configured_broker is not None:
        raise RuntimeError("preconfigured Surface world requires its injected broker")
    brain_options: dict[str, Any] = {}
    if player is None:
        if args.player == "brain" and args.brain_url:
            brain_options["url"] = args.brain_url
        player = make_player(args.player, **brain_options)
    dungeon = (
        DungeonField(rows=world.map_rows, cols=world.map_cols, half_life=args.memory_half_life)
        if args.memory == "field"
        else None
    )
    journal: list[dict[str, Any]] = []
    # What the field said the last time it was asked, and when it was asked:
    # the situation that holds is asked about again only when it changes.
    woken_situation: tuple[str, ...] | None = None
    standing: Situation | None = None
    asking: Asking | None = None
    seeks: list[tuple[str, Recollection]] = []
    shown_situational: dict[str, Lesson] = {}
    # One question, one look: a life asks what it asks, but the field is asked
    # each thing once, and only as often as the life is allowed to ask.
    asked_questions: dict[str, Asking] = {}
    refused: list[dict[str, str]] = []
    recollection = Recollection(
        concern="this life", status="awaiting-situation", episode={}, lessons=()
    )
    briefing: Mapping[str, Any] = {}
    life = life_label or datetime.now().strftime("%Y%m%d-%H%M%S")
    interrupted = False
    started = time.time()
    observation: Observation | None = None
    start_depth: int | None = None
    try:
        observation = world.reset()
        print(f"world   : {world.name} — {world.goal}")
        print(f"player  : {player.name}")
        if url:
            print(f"watch   : {url}")
        print(f"screen  : {observation.summary.get('character', '?')} "
              f"depth {observation.summary.get('depth', '?')}")
        if dungeon is not None:
            print(f"memory  : the two-fluid field, {dungeon.rows}x{dungeon.cols} cells per level, "
                  f"half-life {dungeon.half_life:.0f} turns")
        if memory_error:
            print(f"living  : no field memory ({memory_error})")
        elif not isinstance(living, NoMemory):
            print(f"living  : {living.home}; memories wake for each situation")
        start_depth = observation.summary.get("depth")
        for _ in range(1, args.turns + 1):
            if observation.done:
                surface_state = world.surface_receipt() if surface_broker is not None else {}
                wait = surface_state.get("wait") if isinstance(surface_state, Mapping) else None
                if isinstance(wait, Mapping):
                    print(
                        f"surface : waiting for host ({wait.get('kind') or 'review'}): "
                        f"{wait.get('reason') or 'control is fenced'}"
                    )
                else:
                    print("the life ended.")
                break
            if stop_file is not None and stop_file.exists():
                # A campaign outlives the session that started it, so its stop
                # is a file it can hear wherever it is running: the life in
                # progress closes out, keeps its receipt and its lesson, and
                # only then does the campaign end.
                stop_file.unlink(missing_ok=True)
                interrupted = True
                print("stop    : the stop file appeared; closing this life out")
                break
            if dungeon is not None:
                depth = observation.summary.get("depth")
                if isinstance(depth, int):
                    dungeon.visit(depth)
            actions = world.actions()
            if dungeon is not None and not dungeon.route().aim:
                # The field's standing posture: with no intention laid, it
                # walks -- toward remembered gold first, because gold is the
                # score and the dungeon hands it over the moment it is stepped
                # on, and otherwise into ground it has not seen.  The route
                # walks and route_wake wakes the brain when something happens.
                dungeon.aim("value" if dungeon.can_reach("value") else "unseen")
                if dungeon.route().arrived:
                    # The remembered place is underfoot and already taken; a
                    # player must not stand counting a pile it has picked up.
                    dungeon.aim("unseen")
            if dungeon is not None and not observation.prompt:
                # The field's own intentions lead the list: they are read out of
                # the memory the brain was just shown.
                actions = tuple(
                    Action(key=key, keys=key, label=label)
                    for key, label in dungeon.intent_actions()
                ) + actions
            memory = dungeon.block() if dungeon is not None else ""
            route = dungeon.route() if dungeon is not None else None
            step = dungeon.next_step() if route is not None and route.aim else None
            wake = route_wake(observation, journal, route, step)
            memories = Memories(recollection, asking=asking)
            situation: Situation | None = None
            if step is not None and not wake and args.follow:
                # The field walks while nothing needs deciding: the route the
                # player laid takes its own step, and the receipt says so.
                action = world.move_action(step)
                decision = Decision(action, route.step_reason(), "route")
            else:
                if step is not None and wake:
                    memory = (
                        f"You were following the route to the {aim_words(route.aim)} and "
                        f"stopped, because {wake}.\n{memory}"
                    )
                # Ask the field which lessons belong to this moment; their
                # references also travel to the life's eventual verdict.
                context, situations = situation_context(observation, journal, route)
                # Asking the field what a situation wakes revises the conditions
                # it holds, so the question is put when the situation is a new
                # one -- and now and then, so a long stay is not a silence.
                if situations != woken_situation or observation.turn % MATCH_EVERY == 0:
                    woken_situation = situations
                    situation = living.match(
                        context=context,
                        situations=situations,
                        event_id=f"{life}:turn:{observation.turn}",
                        label=f"{life}:turn:{observation.turn}",
                    )
                else:
                    situation = standing
                standing = situation
                if situation is not None:
                    for lesson in situation.lessons:
                        if lesson.source_id:
                            shown_situational.setdefault(lesson.source_id, lesson)
                memories = Memories(recollection, situation, asking=asking)
                decision = player.decide(
                    observation=observation,
                    actions=actions,
                    recent=journal,
                    memory=memory,
                    remembered=memories.prompt(),
                )
            shown_asking, asking = asking, None
            intent = decision.action.key if dungeon is not None and decision.action.key in INTENTS else ""
            action = decision.action
            if intent:
                # The player chose where to head rather than a step; the route
                # field turns that into the step, and the receipt keeps both.
                kind = INTENT_KINDS.get(intent)
                dungeon.aim(kind) if kind else dungeon.aim(None)
                step = dungeon.next_step() if kind else None
                move = world.move_action(step) if step is not None else None
                if move is not None:
                    action = move
                else:
                    if getattr(player, "require_brain", False):
                        raise BrainRequiredError(
                            "the resident brain chose a field aim with no reachable step"
                        )
                    walker = getattr(player, "fallback", None)
                    if walker is not None:
                        action = walker.decide(
                            observation=observation, actions=world.actions(), recent=journal
                        ).action
            elif dungeon is not None and route is not None and route.aim:
                # The player chose a step of its own while the route had nothing
                # left to do; the intention is finished with.
                dungeon.retire_aim()
            result = world.act(action)
            observation = result.observation
            if dungeon is not None:
                refusal = world.blocked_cell(
                    world.position,
                    action,
                    moved=bool(observation.summary.get("moved", True)),
                )
                if refusal is not None:
                    cell = world.map_cell((refusal[0], refusal[1]))
                    refusal = (cell[0], cell[1], refusal[2]) if cell else None
                dungeon.observe(
                    world.level_cells(world.frame()),
                    position=world.map_cell(world.position),
                    blocked=refusal,
                )
            if decision.want and living is not None and not isinstance(living, NoMemory):
                # The mind asked for something: the field looks it up now, and
                # the answer is shown to the next decision it makes.
                asking = ask_the_field(
                    decision.want,
                    living=living,
                    asked=asked_questions,
                    seeks=seeks,
                    refused=refused,
                    label=f"{life}:turn:{observation.turn}:ask",
                )
            row = {
                "turn": observation.turn,
                "key": action.key,
                "label": action.label,
                "reason": decision.reason,
                "source": decision.source,
                "want": decision.want,
                "asked": (shown_asking.question if shown_asking is not None else ""),
                "sought": (
                    [lesson.text[:120] for lesson in shown_asking.lessons]
                    if shown_asking is not None
                    else []
                ),
                "intent": intent or None,
                "wake": wake or None,
                "note": result.note,
                "accepted": result.accepted,
                "nudged": decision.nudged,
                "used": decision.used,
                "used_text": (
                    memories.cited(decision.used).text
                    if memories.cited(decision.used)
                    else ""
                ),
                "used_id": (
                    memories.cited(decision.used).source_id
                    if memories.cited(decision.used)
                    else ""
                ),
                "situation": list(situation.situations) if situation is not None else [],
                "woken": [lesson.text[:120] for lesson in (
                    situation.lessons if situation is not None else ()
                )],
                "cell": list(world.map_cell(world.position)) if world.map_cell(world.position) else None,
                **summarize(observation),
            }
            if dungeon is not None:
                row["memory"] = dungeon.turn_state()
            journal.append(row)
            print(
                f"{observation.turn:4d}  {'route' if decision.source == 'route' else '':<5} "
                f"{action.label:<30.30} {decision.reason[:70]}"
            )
            if watch is not None:
                publish_frame(
                    watch, world, observation, player, journal, decision.as_dict(), life_number,
                    ended=observation.done,
                )
            if args.pace:
                time.sleep(args.pace)
        if watch is not None and observation is not None and observation.done:
            # The end of a life is the part worth seeing: hold the last screen a
            # moment, so a campaign does not blink past it.
            publish_frame(
                watch, world, observation, player, journal,
                decision.as_dict() if decision is not None else {}, life_number, ended=True,
            )
            time.sleep(DEATH_PAUSE)
    except KeyboardInterrupt:
        interrupted = True
        print("\nasked to stop; this life is closed out before the campaign stops.")
    finally:
        if surface_broker is not None:
            world.fence_surface()
        failure = sys.exc_info()[1]
        if observation is None and not journal:
            living_section: Mapping[str, Any] = {
                "mode": "none" if isinstance(living, NoMemory) else "field",
                "home": str(getattr(living, "home", "")),
                "error": "life did not start",
            }
        else:
            try:
                living_section = close_life(
                    memory=living,
                    seeks=seeks,
                    recollection=recollection,
                    journal=journal,
                    observation=observation,
                    dungeon=dungeon,
                    player=player,
                    life=life,
                    start_depth=start_depth,
                    error=memory_error,
                    briefing=briefing,
                    situational_lessons=tuple(shown_situational.values()),
                    refused=refused,
                    allow_reflection=not isinstance(failure, BrainRequiredError),
                )
            except Exception as exc:  # a memory that fails is a fact about the run, not its end
                living_section = {
                    "mode": "field" if not isinstance(living, NoMemory) else "none",
                    "home": str(getattr(living, "home", "")),
                    "error": f"{type(exc).__name__}: {exc}",
                }
        receipt: dict[str, Any] = {
            "game": world.name,
            "goal": world.goal,
            "player": (
                player.as_dict() if isinstance(player, BrainPlayer) else {"name": player.name}
            ),
            "started_at": datetime.fromtimestamp(started, timezone.utc).isoformat(),
            "wall_seconds": round(time.time() - started, 1),
            "turns": len(journal),
            "final": (
                {**summarize(observation), "screen_tail": list(observation.screen[-6:])}
                if observation is not None
                else None
            ),
            "error": f"{type(failure).__name__}: {failure}" if failure else None,
            "memory": (
                {"mode": "none"} if dungeon is None
                else {
                    "mode": "field",
                    "walking": "route follows itself while nothing needs deciding"
                    if args.follow
                    else "the brain is asked every turn",
                    **field_parameters(),
                    "final": dungeon.state(),
                }
            ),
            "living": living_section,
            "journal": journal,
        }
        receipt["interrupted"] = interrupted
        if hasattr(world, "cleared"):
            receipt["cleared_player_files"] = list(world.cleared)
        world.close()
        if surface_broker is not None:
            receipt["surface"] = world.surface_receipt()
        directory = run_dir or RUNS / datetime.now().strftime("%Y%m%d-%H%M%S")
        directory.mkdir(parents=True, exist_ok=True)
        receipt_path = directory / "receipt.json"
        receipt["receipt"] = str(receipt_path)
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        if observation is not None:
            (directory / "screen.txt").write_text(
                "\n".join(observation.screen), encoding="utf-8"
            )
        print(f"receipt : {receipt_path}")
        if observation is not None and observation.done:
            print("the tombstone:")
            for line in observation.screen[-8:]:
                print(f"   {line}")
    return receipt


def run(
    args: argparse.Namespace,
    *,
    surface_broker: Any | None = None,
    surface_mission_id: str = "",
    surface_grant_id: Any = None,
    living: Any | None = None,
) -> int:
    """Play one bounded life, optionally under an injected host broker."""
    if getattr(args, "surface", False) and surface_broker is None:
        raise RuntimeError("--surface requires an injected live SurfaceBroker")
    if surface_broker is not None and (not surface_mission_id or living is None):
        raise RuntimeError("hosted Surface play requires mission_id and caller-owned living memory")
    watch = None if args.no_view else WatchView(port=args.port)
    url = watch.start() if watch is not None else ""
    owns_living = living is None
    if living is None:
        living, memory_error = open_memory(args)
    else:
        memory_error = ""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    directory = Path(args.run_dir) if args.run_dir else RUNS / stamp
    try:
        play_life(
            args,
            living=living,
            memory_error=memory_error,
            watch=watch,
            url=url,
            life_label=stamp,
            life_number=1,
            run_dir=directory,
            surface_broker=surface_broker,
            surface_mission_id=surface_mission_id,
            surface_grant_id=surface_grant_id,
        )
    finally:
        if owns_living:
            living.close()
        if watch is not None:
            if args.linger > 0:
                # The end of a life is the part worth watching; hold the page on
                # the last screen instead of closing it the moment the run stops.
                print(f"the page holds the last screen for {args.linger:.0f}s.")
                try:
                    time.sleep(args.linger)
                except KeyboardInterrupt:
                    pass
            watch.stop()
    return 0


def campaign(
    args: argparse.Namespace,
    *,
    surface_broker: Any | None = None,
    surface_mission_id: str = "",
    surface_grant_id: Any = None,
    living: Any | None = None,
) -> int:
    """Play lives back to back, optionally under an injected host broker."""
    if getattr(args, "surface", False) and surface_broker is None:
        raise RuntimeError("--surface requires an injected live SurfaceBroker")
    if surface_broker is not None and (not surface_mission_id or living is None):
        raise RuntimeError("hosted Surface campaigns require mission_id and caller-owned living memory")
    shared_world = None
    if surface_broker is not None:
        shared_world = create_world("nethack", allow_save=False)
        shared_world.configure_surface(surface_broker, surface_mission_id, surface_grant_id)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    directory = Path(args.campaign) if args.campaign else RUNS / f"campaign-{stamp}"
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "campaign.json"
    if log_path.exists():
        log: dict[str, Any] = json.loads(log_path.read_text(encoding="utf-8"))
        played = len(log.get("lives") or [])
        print(f"campaign: continuing {directory} with {played} lives already played")
    else:
        log = {
            "goal": "beat NetHack",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "home": str(getattr(living, "home", args.memory_home)),
            "brain": args.brain_url or "(the player's default)",
            "turns_per_life": args.turns,
            "lives": [],
        }
        # The log exists from the first minute: a campaign that is still on its
        # first life should still say what it is and where it is writing.
        log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
        print(f"campaign: {directory}")
    watch = None if args.no_view else WatchView(port=args.port)
    url = watch.start() if watch is not None else ""
    if url:
        print(f"watch   : {url}")
    owns_living = living is None
    if living is None:
        living, memory_error = open_memory(args)
    else:
        memory_error = ""
    if memory_error:
        print(f"living  : no field memory ({memory_error})")
    else:
        print(f"living  : {getattr(living, 'home', '')}")
    print(
        "lives   : "
        + (f"{args.lives}" if args.lives else "until stopped")
        + f", at most {args.turns} decisions each"
    )
    print(f"stop    : create {directory / STOP_FILE} (or Ctrl-C) to stop between lives")
    failures = 0
    log.setdefault("failures", [])
    try:
        while not args.lives or len(log["lives"]) < args.lives:
            # A failed attempt is still an attempt: the index moves on with it,
            # so no life is ever played twice under one name.
            index = len(log["lives"]) + len(log["failures"]) + 1
            label = life_label(directory.name, index)
            life_dir = directory / f"life-{index:04d}"
            print(f"\n=== life {index} ===")
            try:
                receipt = play_life(
                    args,
                    living=living,
                    memory_error=memory_error,
                    watch=watch,
                    url=url,
                    life_label=label,
                    life_number=index,
                    stop_file=directory / STOP_FILE,
                    surface_broker=surface_broker,
                    surface_mission_id=surface_mission_id,
                    surface_grant_id=surface_grant_id,
                    world=shared_world,
                )
            except KeyboardInterrupt:
                print("\nasked to stop.")
                break
            except Exception as exc:  # a life that cannot start is one bad life
                failures += 1
                print(f"life {index}: {type(exc).__name__}: {exc}")
                log["failures"].append(
                    {
                        "life": index,
                        "label": label,
                        "error": f"{type(exc).__name__}: {exc}"[:300],
                        "at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                log["updated_at"] = datetime.now(timezone.utc).isoformat()
                log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    print(f"{failures} lives in a row could not start; stopping.")
                    break
                continue
            failures = 0
            row = campaign_row(
                receipt, index, label, memory_home_bytes(getattr(living, "home", ""))
            )
            log["lives"].append(row)
            log["updated_at"] = datetime.now(timezone.utc).isoformat()
            log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
            print(campaign_line(row))
            if receipt.get("interrupted"):
                break
            if args.pace_between_lives:
                time.sleep(args.pace_between_lives)
    finally:
        if owns_living:
            try:
                living.close()
            except Exception:
                pass
        if shared_world is not None:
            shared_world.close()
        if watch is not None:
            if args.linger > 0:
                print(f"the page holds the last screen for {args.linger:.0f}s.")
                try:
                    time.sleep(args.linger)
                except KeyboardInterrupt:
                    pass
            watch.stop()
    best = max((row.get("deepest") or 0 for row in log["lives"]), default=None)
    print(
        f"\ncampaign: {len(log['lives'])} lives, {len(log['failures'])} attempts that "
        f"could not start, deepest {best}, log {log_path}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Play a game as Cassi.")
    parser.add_argument("mode", choices=("probe", "play", "campaign"))
    parser.add_argument("--player", default="scripted", choices=("scripted", "brain"))
    parser.add_argument(
        "--turns", type=int, default=0, help="decisions in one life (0: the mode's default)"
    )
    parser.add_argument(
        "--lives", type=int, default=0, help="lives in a campaign (0: keep going)"
    )
    parser.add_argument(
        "--campaign", default="", help="the campaign directory to start or continue"
    )
    parser.add_argument(
        "--pace-between-lives", type=float, default=0.0, help="seconds to rest between lives"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--brain-url", default="")
    parser.add_argument("--memory", default="field", choices=("field", "none"))
    parser.add_argument(
        "--surface",
        action="store_true",
        help="require a host-injected live SurfaceBroker (unavailable from the standalone CLI)",
    )
    parser.add_argument("--memory-half-life", type=float, default=120.0)
    parser.add_argument(
        "--no-follow",
        dest="follow",
        action="store_false",
        help="ask the brain every turn instead of letting the route field walk",
    )
    parser.add_argument(
        "--living",
        dest="living",
        action="store_true",
        default=True,
        help="remember across lives in the field's living memory (default)",
    )
    parser.add_argument(
        "--no-living",
        dest="living",
        action="store_false",
        help="play without the living memory",
    )
    parser.add_argument(
        "--memory-home",
        default=str(DEFAULT_HOME),
        help="the field home the living memory lives in",
    )
    parser.add_argument("--pace", type=float, default=0.0)
    parser.add_argument(
        "--linger",
        type=float,
        default=None,
        help="seconds to hold the watch page on the last screen (default: 300 once,"
        " none for a campaign, which ends in another life anyway)",
    )
    parser.add_argument("--no-view", action="store_true")
    parser.add_argument("--run-dir", default="")
    return parser


def hear_the_stop() -> None:
    """Turn a stop request into the interrupt the life knows how to finish on.

    A campaign runs for hours or days on its own; when it is asked to stop, the
    life being played has to close out first -- recollection bound, lesson filed
    -- or the stop costs the mind the whole life it was in the middle of.
    """

    def stop(signum: int, frame: Any) -> None:
        raise KeyboardInterrupt(f"signal {signum}")

    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        number = getattr(signal, name, None)
        if number is None:
            continue
        try:
            signal.signal(number, stop)
        except (ValueError, OSError):  # not the main thread, or the platform says no
            continue


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.surface:
        parser.error("--surface requires an injected live SurfaceBroker; standalone CLI cannot create one")
    hear_the_stop()
    if args.mode == "probe":
        args.living = False
        args.no_view = True
        args.turns = min(args.turns or 8, 8)
        return run(args)
    if args.mode == "campaign":
        args.turns = args.turns or CAMPAIGN_TURNS
        args.linger = args.linger or 0.0
        return campaign(args)
    args.turns = args.turns or PLAY_TURNS
    args.linger = args.linger if args.linger is not None else 300.0
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
