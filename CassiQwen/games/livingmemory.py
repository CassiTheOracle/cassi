"""What the player remembers between lives: Cassi's own living memory.

`games.fieldmemory` is where the player is *now* -- the map, the route, the
frontier of one level.  This is what the player has *learned about playing*:
lessons the brain wrote after earlier lives, recalled for the concern at hand,
bound to the decision that used them, and settled with what actually happened.

The field owns every part of it.  A recollection is an episode with a lifecycle:
it is delivered, it may be used by a named consumer, and it is settled with the
outcome of that use.  A recollection nobody used is settled as unused rather
than praised for being read, and one that helped is renewed.  Nothing here
invents an outcome, and reading memory never changes it.

Without a field the game still plays: `NO_MEMORY` answers every call with
nothing and remembers nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

# The contexts are the keys the field files memory under, and a recall asks for
# a context exactly.  Lessons are filed by kind, so every lesson answers every
# concern; the lesson's own words say where it was learned.
# What the games home is allowed to hold.  A life revises a condition and wakes
# a memory on many decisions, so this is sized for a long history of play rather
# than for one work session.
GAME_WORKSPACE_BYTES = 1024 * 1024 * 1024  # growth recovery needs room above the seated state
GAME_MODES = 786_432

LESSON_CONTEXT: Mapping[str, str] = {"adapter": "cassi-nethack", "kind": "lesson"}
LIFE_CONTEXT: Mapping[str, str] = {"adapter": "cassi-nethack", "kind": "life"}
DEFAULT_HOME = Path(__file__).resolve().parent / "field-home"

# What the field says about a memory decides how loud it is: a lesson with no
# verdict yet is heard at the middle, one that has only led nowhere sinks, and
# one that has served rises.  The band keeps a single verdict from shouting.
DEFAULT_PRIORITY = 0.5
STANDING_FLOOR = 0.1
STANDING_CEILING = 0.9
STANDING_HISTORY = 8
STANDING_LIVES = 24
# How many memories a decision is shown.  Judgement only selects if the list is
# shorter than what the field can wake.
OFFER_LIMIT = 4

# What a lesson can be about.  The brain chooses from this list when it writes
# the lesson; the player reports which of them hold, decision by decision, and
# the field decides which memories that wakes.  "always" holds every turn.
SITUATIONS: tuple[str, ...] = (
    "always",
    "blocked",
    "monster",
    "hurt",
    "stairs",
    "exploring",
    "new-level",
)
SITUATION_FIELDS: Mapping[str, str] = {
    "always": "always",
    "blocked": "blocked",
    "monster": "monster",
    "hurt": "hurt",
    "stairs": "stairs",
    "exploring": "exploring",
    "new-level": "new_level",
}


def _lesson_text(payload: Mapping[str, Any]) -> tuple[str, bool]:
    """The words of a memory record: its lesson, or its cue once set aside."""

    lesson = str(payload.get("lesson") or "").strip()
    if lesson:
        return lesson, False
    summary = payload.get("memory_summary")
    if isinstance(summary, Mapping):
        cue = str(summary.get("cue") or "").strip()
        if cue:
            return cue, True
    return "", False


def memory_identity(ref: Mapping[str, Any] | str) -> str:
    """The lesson a memory reference names, however the field spells the binding.

    A lesson is filed under its own identity and bound to the field under a
    binding whose id carries that identity -- `field-qwen:binding:games:nethack:
    lesson:...` -- so both spellings have to name the same memory when a verdict
    is counted.  A reference that is already the identity is returned as it is.
    """

    text = ref if isinstance(ref, str) else str((ref or {}).get("id") or "")
    marker = ":binding:"
    return text.split(marker, 1)[1] if marker in text else text


def standing_of(
    identity: str,
    episodes: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """How loud a memory has earned the right to be, from the field's own lives.

    A verdict lives on the life that earned it: the field records which memories
    a use selected, and how the outcome of that use was assessed.  A memory that
    was never acted on is heard at the middle; every verdict it has earned moves
    it, so what actually happened decides which memories come first.
    """

    if isinstance(episodes, Mapping):
        # the whole view is accepted as readily as its episode list: reading the
        # wrong one has to be impossible, not silently empty
        episodes = episodes.get("episodes") or ()
    verdicts: list[float] = []
    for view in episodes:
        if not isinstance(view, Mapping):
            continue
        use = ((view.get("use") or {}).get("payload") or {})
        selected = use.get("selected_refs") or ()
        # whether the caller names the lesson or the binding it is filed under,
        # the verdict is the same memory's
        if not any(memory_identity(ref) == memory_identity(identity) for ref in selected):
            continue
        assessment = ((view.get("assessment") or {}).get("payload") or {})
        value = assessment.get("usefulness")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            verdicts.append(float(value))
    verdicts = verdicts[-STANDING_HISTORY:]
    if not verdicts:
        return {"verdicts": 0, "usefulness": None, "priority": DEFAULT_PRIORITY}
    earned = sum(verdicts) / len(verdicts)
    return {
        "verdicts": len(verdicts),
        "usefulness": round(earned, 4),
        "priority": round(
            STANDING_FLOOR + (STANDING_CEILING - STANDING_FLOOR) * earned, 4
        ),
    }


def briefing_prompt(briefing: Mapping[str, Any] | None) -> str:
    """The field's account of the lives before this one, as the brain reads it."""

    if not briefing:
        return ""
    lines: list[str] = []
    played = int(briefing.get("lives") or 0)
    if played:
        deepest = briefing.get("deepest")
        where = f"; your deepest was level {deepest}" if deepest else ""
        lines.append(
            f"This is your life number {played + 1}. You have played {played} "
            f"before{where}, and you hold {int(briefing.get('lessons') or 0)} "
            "lessons about playing."
        )
    for summary in briefing.get("recent") or ():
        lines.append(f"  - {summary}")
    return "\n".join(lines)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True, slots=True)
class Lesson:
    """One thing Cassi remembers about playing, and the record that binds it.

    A lesson that has been set aside comes back as its cue rather than its
    words, and says so: the field keeps the memory usable without keeping its
    detail resident.
    """

    source_id: str
    text: str
    ref: Mapping[str, Any]
    revision_id: str = ""
    cue: bool = False


@dataclass(frozen=True, slots=True)
class Recollection:
    """One recall episode: what came back for a concern, and how it is bound."""

    concern: str
    status: str
    episode: Mapping[str, Any]
    lessons: tuple[Lesson, ...]
    gaps: tuple[Any, ...] = ()
    query_id: str = ""

    def prompt(self) -> str:
        """The numbered list the brain reads, in the order it may cite it."""
        if not self.lessons:
            return ""
        lines = [
            "What you remember about playing, from your own earlier lives:",
        ]
        for index, lesson in enumerate(self.lessons, start=1):
            lines.append(f"  {index}. {lesson.text}")
        lines.append(
            "If one of these decided your action, say which by number in \"used\"; "
            "otherwise use 0."
        )
        return "\n".join(lines)

    def cited(self, number: int) -> Lesson | None:
        """The lesson the brain named, or nothing when it named none."""
        if 1 <= number <= len(self.lessons):
            return self.lessons[number - 1]
        return None

    def refs(self, lessons: Sequence[Lesson] | None = None) -> tuple[Mapping[str, Any], ...]:
        chosen = self.lessons if lessons is None else tuple(lessons)
        return tuple(lesson.ref for lesson in chosen if lesson.ref)

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "concern": self.concern,
            "status": self.status,
            "query_id": self.query_id,
            "episode_id": str(self.episode.get("id") or ""),
            "lessons": [
                {
                    "source_id": lesson.source_id,
                    "text": lesson.text,
                    "revision_id": lesson.revision_id,
                }
                for lesson in self.lessons
            ],
            "gaps": [str(gap) for gap in self.gaps],
        }


@dataclass(frozen=True, slots=True)
class Situation:
    """The memories the field says apply to the situation the player is in now."""

    situations: tuple[str, ...]
    lessons: tuple[Lesson, ...]
    status: str
    unknown: tuple[Any, ...] = ()
    searched: int = 0
    candidates: int = 0

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "situations": list(self.situations),
            "status": self.status,
            "lessons": [
                {"source_id": lesson.source_id, "text": lesson.text}
                for lesson in self.lessons
            ],
            "unknown_conditions": len(self.unknown),
            "conditions_searched": self.searched,
            "conditions_held": self.candidates,
        }


SEEK_LIMIT = 3
"""How many times one life may ask the field something it wants to know.

The mind asks in its own words and the field answers; a life is bounded, so the
asking is too.  A question asked twice in one life is answered once -- the same
reading serves both -- and once the limit is spent the field says so and the
decision is made from what the life already has.
"""


@dataclass(frozen=True, slots=True)
class Asking:
    """A memory the mind asked the field for, and what the field answered.

    The mind reaches for memory as well as being handed it: a decision may ask
    for anything it wants to know, in its own words, and the field answers for
    that concern.  What comes back is shown to the next decision, first in the
    list, because a question the mind asked itself is the most specific thing it
    knows about what it needs.
    """

    question: str
    lessons: tuple[Lesson, ...] = ()
    status: str = ""
    episode: Mapping[str, Any] = field(default_factory=dict)

    def exhausted(self) -> bool:
        """Whether the life has spent its questions, so this one is not looked up."""

        return self.status == "exhausted"

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "question": self.question,
            "status": self.status,
            "lessons": [
                {"source_id": lesson.source_id, "text": lesson.text}
                for lesson in self.lessons
            ],
        }


@dataclass(frozen=True, slots=True)
class Memories:
    """What Cassi remembers for this decision, in one list.

    What the mind asked for leads the list, then the situation's: the field was
    asked what applies to what is happening now, and answered in the order it
    judges -- the memories that have earned their place first.  Only when
    neither the mind's own question nor the moment answered does the life's
    recollection stand in, because a memory that cannot be matched is still
    better than silence.
    """

    recollection: Recollection
    situation: Situation | None = None
    asking: Asking | None = None
    limit: int = OFFER_LIMIT

    def lessons(self) -> tuple[Lesson, ...]:
        waking = self.situation.lessons if self.situation is not None else ()
        asked = self.asking.lessons if self.asking is not None else ()
        offered = (asked + waking) if (asked or waking) else self.recollection.lessons
        ordered: list[Lesson] = []
        for lesson in offered:
            if lesson.source_id and all(
                lesson.source_id != seen.source_id for seen in ordered
            ):
                ordered.append(lesson)
            if len(ordered) >= max(1, int(self.limit)):
                break
        return tuple(ordered)

    def woken(self) -> int:
        """How many memories the field woke, whether or not they were shown."""

        return len(self.situation.lessons) if self.situation is not None else 0

    def sought(self) -> int:
        """How many memories came back to the mind's own question."""

        return len(self.asking.lessons) if self.asking is not None else 0

    def prompt(self) -> str:
        lessons = self.lessons()
        if not lessons and self.asking is None:
            return ""
        asked = self.sought()
        asked_here = bool(self.asking is not None and asked)
        situational = bool(self.situation is not None and self.situation.lessons)
        lines: list[str] = []
        if self.asking is not None:
            said = f'"{self.asking.question}"'
            if self.asking.exhausted():
                lines.append(
                    "You have asked the field all you can in this life; decide from "
                    "what you have."
                )
            elif self.asking.status == "repeated":
                lines.append(
                    f"You asked the field that already: {said}. "
                    + (
                        f"Its answer is the first {asked} "
                        f"{'memory' if asked == 1 else 'memories'} below."
                        if asked
                        else "It had nothing about that."
                    )
                )
            elif asked:
                lines.append(
                    f"You asked the field: {said}. Its answer is the first {asked} "
                    f"{'memory' if asked == 1 else 'memories'} below."
                )
            else:
                lines.append(f"You asked the field: {said}. It had nothing about that.")
        if lessons:
            lines.append(
                "What you remember for this decision, most earned first:"
                if asked_here
                else (
                    "What you remember that bears on what is happening right now, "
                    "most earned first:"
                )
                if situational
                else "What you remember about playing, from your own earlier lives:"
            )
        for index, lesson in enumerate(lessons, start=1):
            mark = " (set aside earlier, kept as a cue)" if lesson.cue else ""
            lines.append(f"  {index}. {lesson.text}{mark}")
        lines.append(
            "If one of these decided your action, say which by number in \"used\"; "
            "otherwise use 0."
        )
        return "\n".join(lines)

    def cited(self, number: int) -> Lesson | None:
        lessons = self.lessons()
        if 1 <= number <= len(lessons):
            return lessons[number - 1]
        return None

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "recall": self.recollection.as_dict(),
            "situation": self.situation.as_dict() if self.situation is not None else None,
            "asking": self.asking.as_dict() if self.asking is not None else None,
            "woken": self.woken(),
            "sought": self.sought(),
            "shown": [
                {
                    "source_id": lesson.source_id,
                    "text": lesson.text,
                    "cue": lesson.cue,
                }
                for lesson in self.lessons()
            ],
        }


class GameMemory:
    """The living memory as the game uses it, over a field home on disk."""

    def __init__(
        self,
        home: Path | str = DEFAULT_HOME,
        *,
        workspace_bytes: int = GAME_WORKSPACE_BYTES,
        modes: int = GAME_MODES,
    ) -> None:
        from cassi_field_qwen_workbench import (  # local: the game plays without it
            CassiFieldWorkMemory,
        )
        from cassi_field_owner import CapacityLimits

        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        # A life writes memory on every decision it acts on and every situation
        # it wakes, so the games home is given a region with room for a long
        # history rather than the workbench's default.
        self._memory = CassiFieldWorkMemory(
            self.home,
            limits=CapacityLimits(
                max_state_bytes=max(workspace_bytes * 2, 128 * 1024 * 1024),
                max_workspace_bytes=workspace_bytes,
            ),
            profile_overrides={"mode_count": modes},
        )
        self.recalls = 0
        self.uses = 0
        self.cancels = 0
        self.settlements = 0
        self.lessons_written = 0
        self.lives_written = 0
        self.conditions = 0
        self.matches = 0
        self.woken = 0
        self.demotions = 0
        self.reinterpretations = 0
        self.maintenances = 0
        self.closed = False
        self._known: dict[str, Lesson] = {}

    # -- remembering -----------------------------------------------------
    def recall(self, concern: str, *, label: str = "") -> Recollection:
        """Ask the field what it knows, for the concern the player is in now."""

        answer = self._memory.recall(dict(LESSON_CONTEXT), operation_label=label or concern)
        self.recalls += 1
        return self._recollection(answer, concern)

    def recall_woken(
        self, lessons: Sequence[Lesson], *, label: str, concern: str = "this life"
    ) -> Recollection:
        """Bind the lessons the field actually woke to one settleable life episode.

        A situational match already selected these field references. Repeating a
        workspace-wide source query for every lesson would replay the whole
        history before the player could act.
        """
        import hashlib

        selected = tuple(lesson for lesson in lessons if lesson.ref)
        answer = self._memory.semantic(
            {
                "operation": "recall-request",
                "operation_id": self._memory._semantic_operation_id("recall-request", label),
                "episode_id": hashlib.sha256(label.encode("utf-8")).hexdigest(),
                "question": {"kind": "nethack-situational-recall", "life": label},
                "context": dict(LESSON_CONTEXT),
                "intended_use": {"kind": "nethack-life", "life": label},
                "fidelity": {"requested": "field-woken", "delivered": "field-woken"},
                "allowance": {"woken": len(selected)},
                "selected_refs": [dict(self.current_ref(lesson.ref)) for lesson in selected],
                "search": {"kind": "match-relevance", "woken": len(selected)},
            },
            operation_label=label,
        )
        self.recalls += 1
        result = answer.get("result") or {}
        return Recollection(
            concern=concern,
            status=str(result.get("status") or ""),
            episode=result.get("episode") or {},
            lessons=selected,
        )

    def _recollection(self, answer: Mapping[str, Any], concern: str) -> Recollection:
        """One answer from the field, as the list the brain reads and cites."""

        lessons: list[Lesson] = []
        # A record carries what was said; the binding ref -- the identity a use
        # is bound to -- rides alongside it, one per record, in the same order.
        refs = list(answer.get("selected_semantic_records") or ())
        for row in answer.get("records") or ():
            if not isinstance(row, Mapping):
                continue
            payload = row.get("payload")
            text, cue = "", False
            if isinstance(payload, Mapping):
                text, cue = _lesson_text(payload)
            if not text:
                continue
            ref: Mapping[str, Any] = {}
            index = len(lessons)
            if index < len(refs) and isinstance(refs[index], Mapping):
                candidate = refs[index].get("ref")
                if isinstance(candidate, Mapping):
                    ref = candidate
            lesson = Lesson(
                source_id=str(row.get("source_id") or ""),
                text=text,
                ref=ref,
                revision_id=str(row.get("source_revision_id") or ""),
                cue=cue,
            )
            lessons.append(lesson)
            if ref:
                self._known[str(ref.get("id") or "")] = lesson
        living = answer.get("living_memory")
        episode: Mapping[str, Any] = {}
        if isinstance(living, Mapping) and isinstance(living.get("episode"), Mapping):
            episode = living["episode"]
        return Recollection(
            concern=concern,
            status=str(answer.get("status") or ""),
            episode=episode,
            lessons=tuple(lessons),
            gaps=tuple(answer.get("gaps") or ()),
            query_id=str(answer.get("query_id") or ""),
        )

    def _lesson_from_binding(self, binding: Mapping[str, Any]) -> Lesson | None:
        """Resolve a field binding to its exact, eligible source revision."""
        scope = binding.get("scope") or {}
        if binding.get("kind") != "Binding" or scope.get("context") != dict(LESSON_CONTEXT):
            return None
        revision = (binding.get("payload") or {}).get("source_revision_id")
        if not isinstance(revision, str):
            return None
        document = self._memory._document_for_revision(revision)
        if not isinstance(document, Mapping) or document.get("context") != dict(LESSON_CONTEXT):
            return None
        eligibility = self._memory._publication_eligibility(document)
        if eligibility is not None and not eligibility["eligible"]:
            return None
        words, cue = _lesson_text(document.get("payload") or {})
        source_id = str(document.get("source_id") or "")
        if not source_id or not words:
            return None
        return Lesson(
            source_id=source_id,
            text=words,
            ref={key: binding[key] for key in ("id", "kind", "content_version")},
            revision_id=revision,
            cue=cue,
        )

    def filed_lessons(self) -> dict[str, tuple[Lesson, dict[str, str]]]:
        """Read active lesson bindings and their filed moments from the field.

        This is an exact-source read of the current field-selected bindings,
        used at life close to file new lessons. It creates no recall episode:
        the life did not act on this inventory.
        """
        inspected = self._memory._computer_inspect()
        task = inspected.get("task") or {}
        current = task.get("current") or {}
        records = task.get("records") or {}
        conditions: dict[str, dict[str, str]] = {}
        for ref in (current.get("Program") or {}).values():
            history = records.get(ref.get("id"))
            version = ref.get("content_version")
            if not isinstance(history, list) or not isinstance(version, int) or not 1 <= version <= len(history):
                continue
            record = history[version - 1]
            if not isinstance(record, Mapping) or record.get("status") != "active":
                continue
            payload = record.get("payload") or {}
            reason = payload.get("reason") or {}
            if payload.get("memory_role") != "relevance-condition" or reason.get("kind") != "nethack-situation":
                continue
            situation = reason.get("situation")
            if situation not in SITUATIONS:
                continue
            for target in payload.get("target_refs") or ():
                if isinstance(target, Mapping):
                    conditions.setdefault(str(target.get("id") or ""), {})[situation] = str(
                        reason.get("lesson") or ""
                    )

        found: dict[str, tuple[Lesson, dict[str, str]]] = {}
        for binding in self._memory._current_bindings(inspected):
            lesson = self._lesson_from_binding(binding)
            if lesson is None:
                continue
            self._known[str(lesson.ref["id"])] = lesson
            found[lesson.source_id] = (lesson, conditions.get(str(lesson.ref["id"]), {}))
        return found


    def remember_lesson(
        self,
        text: str,
        *,
        depth: int | None = None,
        life: str = "",
        labels: Sequence[str] = (),
    ) -> str | None:
        """File one lesson, from the life that taught it.

        The same words always land on the same record, so a lesson learned
        twice is one memory revised rather than two memories.
        """
        from cassi_field_qwen_workbench import WorkMemoryRecord

        lesson = " ".join(str(text).split())
        if not lesson:
            return None
        source_id = lesson_source_id(lesson)
        payload: dict[str, Any] = {"kind": "lesson", "lesson": lesson}
        if depth is not None:
            payload["learned_at_depth"] = int(depth)
        if life:
            payload["from_life"] = life
        result = self._memory.learn(
            WorkMemoryRecord(
                source_id=source_id,
                context=dict(LESSON_CONTEXT),
                payload=payload,
                observed_timestamp=_now(),
                labels=("nethack", "lesson", *(str(label) for label in labels)),
            )
        )
        self.lessons_written += 1
        return str(result.get("binding_id") or source_id)

    def remember_life(
        self,
        summary: str,
        *,
        life: str,
        depth: int | None = None,
        turns: int = 0,
        labels: Sequence[str] = (),
    ) -> str | None:
        """File what a life came to, so later recall has experience behind it."""
        from cassi_field_qwen_workbench import WorkMemoryRecord

        text = " ".join(str(summary).split())
        if not text:
            return None
        source_id = f"games:nethack:life:{life}"
        payload: dict[str, Any] = {"kind": "life", "life": life, "summary": text, "turns": int(turns)}
        if depth is not None:
            payload["depth"] = int(depth)
        result = self._memory.learn(
            WorkMemoryRecord(
                source_id=source_id,
                context=dict(LIFE_CONTEXT),
                payload=payload,
                observed_timestamp=_now(),
                labels=("nethack", "life", *(str(label) for label in labels)),
            )
        )
        self.lives_written += 1
        return str(result.get("binding_id") or source_id)

    # -- using it --------------------------------------------------------
    def used(
        self,
        recollection: Recollection,
        *,
        consumer: Mapping[str, Any],
        lessons: Sequence[Lesson] | None = None,
        label: str = "",
    ) -> Mapping[str, Any] | None:
        """Bind a recollection to the consumer that acted on it.

        The episode that comes back is the one to settle later: it is no longer
        the recall, it is the use.
        """
        if not recollection.episode:
            return None
        answer = self._memory.use_recall(
            # Every use is its own revision of the recollection, so the second
            # lesson a life acted on is bound at the version the field holds
            # now, not the one read before the first use.
            episode_ref=dict(self.current_ref(recollection.episode)),
            selected_refs=list(recollection.refs(lessons)),
            consumer=dict(consumer),
            operation_label=label or recollection.concern,
        )
        self.uses += 1
        return _episode_of(answer)

    def unused(self, recollection: Recollection, *, reason: str, label: str = "") -> None:
        """Settle a recollection nothing acted on, without inventing usefulness."""
        if not recollection.episode:
            return
        self._memory.cancel_recall(
            episode_ref=dict(self.current_ref(recollection.episode)),
            reason={"kind": "unused", "reason": reason},
            operation_label=label or recollection.concern,
        )
        self.cancels += 1

    def settle(
        self,
        *,
        episode: Mapping[str, Any] | None,
        outcome_id: str,
        consequence: Mapping[str, Any],
        usefulness: float,
        renewal: Mapping[str, Any] | None = None,
        label: str = "",
    ) -> Mapping[str, Any] | None:
        """Settle a use with what actually happened, and renew what helped."""
        if not episode:
            return None
        answer = self._memory.assess_recall(
            # Each use revised the recollection, so the verdict is written
            # against the version the field holds when the life ends.
            episode_ref=dict(self.current_ref(episode)),
            outcome_id=outcome_id,
            consequence=dict(consequence),
            usefulness=float(usefulness),
            renewal=dict(renewal) if renewal else None,
            operation_label=label or outcome_id,
        )
        self.settlements += 1
        return answer.get("result") if isinstance(answer, Mapping) else None

    # -- reading it back -------------------------------------------------
    def autobiography(self, *, limit: int = 8, label: str = "autobiography") -> Mapping[str, Any]:
        """The field's own account of the lives and recollections it holds."""
        answer = self._memory.autobiography(operation_label=label)
        result = answer.get("result") if isinstance(answer, Mapping) else None
        if not isinstance(result, Mapping):
            return {"episodes": [], "unresolved": 0}
        episodes = list(result.get("episodes") or ())[: max(0, int(limit))]
        return {"episodes": episodes, "unresolved": int(result.get("unresolved") or 0)}

    # -- what applies right now ------------------------------------------
    def register_lesson(
        self,
        lesson: Lesson,
        situations: Sequence[str],
        *,
        wording: str = "",
        priority: float = 0.5,
        cooldown: int = 0,
        label: str = "",
    ) -> int:
        """File when a lesson applies: the field wakes it when that holds.

        One condition per situation, because the field's clauses all have to
        hold at once -- a lesson about being blocked and a lesson about a
        monster are two conditions, not one with two clauses.
        """
        wanted = [name for name in situations if name in SITUATION_FIELDS] or ["always"]
        filed = 0
        for name in wanted:
            self._memory.register_relevance(
                condition_id=f"games.nethack.when.{_digest(lesson.source_id + ':' + name)}",
                condition={
                    "clauses": [
                        {
                            "field": SITUATION_FIELDS[name],
                            "operator": "equals",
                            "value": True,
                        }
                    ]
                },
                target_refs=[dict(self.current_ref(lesson.ref))],
                reason={
                    "kind": "nethack-situation",
                    "situation": name,
                    "lesson": (wording or lesson.text)[:240],
                },
                priority=float(priority),
                cooldown_events=int(cooldown),
                # The field holds a label to its content, so a label names one
                # request.  Each situation is its own request, so each situation
                # gets its own label; repeating a registration is the same
                # request again, which the field accepts.
                operation_label=(
                    f"{label}:{name}:{_digest(wording)}"
                    if label
                    else f"{lesson.source_id}:when:{name}:{_digest(wording)}"
                ),
            )
            self.conditions += 1
            filed += 1
        return filed

    def match(
        self,
        *,
        context: Mapping[str, Any],
        situations: Sequence[str],
        event_id: str,
        label: str = "",
    ) -> Situation:
        """Ask the field which memories this situation wakes."""
        answer = self._memory.match_relevance(
            event_id=event_id,
            context=dict(context),
            maximum=64,
            operation_label=label or event_id,
        )
        self.matches += 1
        result = answer.get("result") if isinstance(answer, Mapping) else None
        wakeups = list((result or {}).get("wakeups") or ()) if isinstance(result, Mapping) else []
        # A wakeup is an event the field wrote; what it wakes is in its payload.
        refs: list[tuple[Mapping[str, Any], str]] = []
        for wake in wakeups:
            if not isinstance(wake, Mapping):
                continue
            try:
                record = self._memory._semantic_record(wake)
            except Exception:
                continue
            payload = record.get("payload") if isinstance(record, Mapping) else None
            if not isinstance(payload, Mapping):
                continue
            reason = payload.get("reason")
            wording = ""
            if isinstance(reason, Mapping):
                wording = str(reason.get("lesson") or "")
            for ref in payload.get("target_refs") or ():
                if isinstance(ref, Mapping):
                    refs.append((dict(ref), wording))
        lessons: list[Lesson] = []
        for ref, wording in refs:
            key = str(ref.get("id") or "")
            lesson = self._known.get(key)
            if lesson is None:
                # Wakeups carry a field binding; its lesson text lives in the
                # exact source revision, not in the binding's metadata.
                lesson = self._lesson_from_binding(self._record_of(ref))
                if lesson is None:
                    continue
                self._known[key] = lesson
            if any(lesson.source_id == seen.source_id for seen in lessons):
                continue
            if wording and wording != lesson.text:
                # what wakes is the field's sharpest reading of this memory
                lesson = Lesson(
                    source_id=lesson.source_id,
                    text=wording,
                    ref=lesson.ref,
                    revision_id=lesson.revision_id,
                    cue=lesson.cue,
                )
            lessons.append(lesson)
        self.woken += len(lessons)
        return Situation(
            situations=tuple(situations),
            lessons=tuple(lessons),
            status=str((result or {}).get("status") or "") if isinstance(result, Mapping) else "",
            unknown=tuple((result or {}).get("unknown") or ()) if isinstance(result, Mapping) else (),
            searched=int((result or {}).get("searched") or 0) if isinstance(result, Mapping) else 0,
            candidates=int((result or {}).get("candidate_count") or 0) if isinstance(result, Mapping) else 0,
        )

    def _record_of(self, ref: Mapping[str, Any]) -> Mapping[str, Any]:
        """One record of the field's own memory, read by reference."""

        try:
            return self._memory._semantic_record(ref, require_current=False) or {}
        except Exception:
            return {}

    def current_ref(self, ref: Mapping[str, Any]) -> Mapping[str, Any]:
        """The newest version of a record the field already holds.

        A memory keeps its identity when it is revised -- a verdict written onto
        it, or a reading sharpened -- and gains a version.  A reference read
        before that revision names the past, so anything handed back to the
        field is read at the version the field is holding now.
        """

        identity = str((ref or {}).get("id") or "")
        if not identity:
            return dict(ref or {})
        try:
            task = self._memory._computer_inspect().get("task")
            history = task.get("records", {}).get(identity) if isinstance(task, Mapping) else None
        except Exception:
            history = None
        if not isinstance(history, Sequence) or isinstance(history, (str, bytes, bytearray)):
            return dict(ref)
        if not history:
            return dict(ref)
        return {**dict(ref), "content_version": len(history)}

    def standing(
        self,
        lesson: Lesson,
        *,
        episodes: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """What the field's own lives say this lesson has earned.

        Standing is read from the verdicts the field recorded against the lives
        that acted on the lesson -- never invented here -- and it is what
        decides how loud the memory is when its moment comes.  A caller reading
        several lessons passes the same history in, so the field is asked once.
        """

        if not lesson.ref:
            return standing_of("", ())
        if episodes is None:
            episodes = self.autobiography(limit=STANDING_LIVES, label="standing")["episodes"]
        return standing_of(str(lesson.ref.get("id") or ""), episodes)

    def briefing(self, *, limit: int = 4, label: str = "") -> dict[str, Any]:
        """The field's own account of the lives it has played, in one line."""

        answer = self._memory.recall(
            dict(LIFE_CONTEXT), operation_label=label or "the lives so far"
        )
        self.recalls += 1
        # The look at the lives is read to say where this one stands, not acted
        # on: settle it, because an unsettled recollection is work the mind
        # carries for the rest of its life.
        self.unused(
            self._recollection(answer, "the lives so far"),
            reason="read to say where this life stands",
            label=(label or "briefing") + ":lives-read",
        )
        lives: list[dict[str, Any]] = []
        for row in answer.get("records") or ():
            payload = row.get("payload") if isinstance(row, Mapping) else None
            if not isinstance(payload, Mapping):
                continue
            lives.append(
                {
                    "life": str(payload.get("life") or ""),
                    "summary": str(payload.get("summary") or ""),
                    "depth": payload.get("depth"),
                    "turns": payload.get("turns"),
                }
            )
        depths = [int(row["depth"]) for row in lives if isinstance(row.get("depth"), int)]
        lessons = self.recall("the lessons so far", label=(label or "briefing") + ":lessons")
        self.unused(lessons, reason="counted for the briefing, not acted on", label=(label or "briefing") + ":lessons-read")
        return {
            "lives": len(lives),
            "deepest": max(depths) if depths else None,
            "lessons": len(lessons.lessons),
            "recent": [row["summary"] for row in lives[-limit:] if row["summary"]],
        }

    def prompt(self, briefing: Mapping[str, Any] | None = None) -> str:
        """What the brain is told before the life starts."""

        return briefing_prompt(briefing)

    # -- memory about the memory -----------------------------------------
    def demote(
        self, lesson: Lesson, *, cue: str, reason: str, label: str = ""
    ) -> Mapping[str, Any] | None:
        """Put a lesson that has not been earning its place aside, as a cue."""
        if not lesson.ref:
            return None
        answer = self._memory.demote_memory(
            memory_ref=dict(self.current_ref(lesson.ref)),
            summary={"cue": cue, "kind": "nethack-lesson-set-aside", "reason": reason},
            reason=reason,
            operation_label=label or f"{lesson.source_id}:set-aside",
        )
        self.demotions += 1
        return answer.get("result") if isinstance(answer, Mapping) else None

    def reinterpret(
        self,
        lesson: Lesson,
        *,
        wording: str,
        when: Sequence[str] = ("always",),
        label: str = "",
    ) -> Mapping[str, Any] | None:
        """Keep the evidence, replace the reading: sharper words for a lesson.

        The lesson's own words stay exactly as they were learned; what changes is
        the field's interpretation of them, which is what a later life reads.
        """
        if not lesson.ref:
            return None
        sharper = " ".join(str(wording).split())
        if not sharper:
            return None
        answer = self._memory.reinterpret_memory(
            interpretation_id="games.nethack.means." + _digest(lesson.source_id + "|" + sharper),
            source_refs=[dict(self.current_ref(lesson.ref))],
            interpretation={"lesson": sharper[:240], "when": list(when)},
            applicability={"scope": "games:nethack", "situations": list(when)},
            operation_label=label or f"{lesson.source_id}:means:{_digest(sharper)}",
        )
        self.reinterpretations += 1
        return answer.get("result") if isinstance(answer, Mapping) else None

    def expand(self, lesson: Lesson, *, reason: str, label: str = "") -> Mapping[str, Any] | None:
        """Read a set-aside lesson's exact words back, from its own evidence."""
        if not lesson.ref:
            return None
        answer = self._memory.expand_memory(
            memory_ref=dict(self.current_ref(lesson.ref)),
            reason=reason,
            operation_label=label or f"{lesson.source_id}:expand",
        )
        return answer.get("result") if isinstance(answer, Mapping) else None

    def maintain(self, *, purpose: str, label: str = "maintenance") -> Mapping[str, Any]:
        """Have the field assess its own resident memory work."""
        answer = self._memory.maintain_memory(
            purpose={"kind": purpose, "scope": "games:nethack"},
            allowance={"scope": "games:nethack", "maximum_objects": 64},
            operation_label=label,
        )
        self.maintenances += 1
        result = answer.get("result") if isinstance(answer, Mapping) else None
        return result if isinstance(result, Mapping) else {}

    def awareness(self, *, label: str = "awareness") -> Mapping[str, Any]:
        """Whether the exact words behind a memory are still recoverable."""
        answer = self._memory.memory_awareness(operation_label=label)
        result = answer.get("result") if isinstance(answer, Mapping) else None
        return result if isinstance(result, Mapping) else {}

    def close(self) -> None:
        if not self.closed:
            self._memory.close()
            self.closed = True

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "home": str(self.home),
            "recalls": self.recalls,
            "uses": self.uses,
            "cancels": self.cancels,
            "settlements": self.settlements,
            "lessons_written": self.lessons_written,
            "lives_written": self.lives_written,
            "conditions": self.conditions,
            "situation_matches": self.matches,
            "memories_woken": self.woken,
            "demotions": self.demotions,
            "reinterpretations": self.reinterpretations,
            "maintenances": self.maintenances,
        }


class NoMemory:
    """No field, no memory: the same calls, none of the remembering."""

    def recall(self, concern: str, *, label: str = "") -> Recollection:
        return Recollection(concern=concern, status="no-memory", episode={}, lessons=())

    def remember_lesson(self, text: str, **_: Any) -> str | None:
        return None

    def remember_life(self, summary: str, **_: Any) -> str | None:
        return None

    def used(self, recollection: Recollection, **_: Any) -> Mapping[str, Any] | None:
        return None

    def unused(self, recollection: Recollection, **_: Any) -> None:
        return None

    def settle(self, **_: Any) -> Mapping[str, Any] | None:
        return None

    def register_lesson(self, lesson: Lesson, situations: Sequence[str], **_: Any) -> int:
        return 0

    def match(
        self, *, context: Mapping[str, Any], situations: Sequence[str], event_id: str, label: str = ""
    ) -> Situation:
        return Situation(situations=tuple(situations), lessons=(), status="no-memory")

    def demote(self, lesson: Lesson, **_: Any) -> Mapping[str, Any] | None:
        return None

    def reinterpret(self, lesson: Lesson, **_: Any) -> Mapping[str, Any] | None:
        return None

    def expand(self, lesson: Lesson, **_: Any) -> Mapping[str, Any] | None:
        return None

    def maintain(self, *, purpose: str, label: str = "") -> Mapping[str, Any]:
        return {}

    def awareness(self, *, label: str = "") -> Mapping[str, Any]:
        return {}

    def autobiography(self, *, limit: int = 8, label: str = "") -> Mapping[str, Any]:
        return {"episodes": [], "unresolved": 0}

    def close(self) -> None:
        return None

    def as_dict(self) -> Mapping[str, Any]:
        return {"home": "", "enabled": False}

    def filed_lessons(self) -> dict[str, tuple[Lesson, dict[str, str]]]:
        return {}


NO_MEMORY = NoMemory()


def _episode_of(answer: Mapping[str, Any]) -> Mapping[str, Any] | None:
    result = answer.get("result") if isinstance(answer, Mapping) else None
    if isinstance(result, Mapping) and isinstance(result.get("episode"), Mapping):
        return result["episode"]
    return None


def lesson_source_id(text: str) -> str:
    """The identity a lesson's words always land on."""
    return "games:nethack:lesson:" + _digest(" ".join(str(text).split()))


def _digest(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
