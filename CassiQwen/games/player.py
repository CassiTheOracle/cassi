"""Players: who decides what Cassi does next.

A player answers one question — given what the world shows and what the world
allows, which action now, and why — and nothing else.  The world never knows
which player it has, so a scripted walker, the live brain, and any future
decision maker are interchangeable.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence

from games.fieldmemory import Route, aim_words
from games.livingmemory import SEEK_LIMIT
from games.world import Action, Observation

# The official llama.cpp baseline runtime (b10472) serves the pinned brain here;
# the retired field-carrying build on 8085 is not used.
DEFAULT_BRAIN_URL = "http://127.0.0.1:8080"
BRAIN_TIMEOUT = 120.0
BRAIN_MAX_TOKENS = 220
REFLECT_MAX_TOKENS = 400
RECENT_TURNS = 6
_GENERIC = {"move", "go", "the", "a", "an", "to", "on", "one", "turn", "here", "you", "your"}

def player_place(screen: Sequence[str]) -> tuple[int, int] | None:
    """Where the player stands on the map, or nothing when the map is not drawn."""
    return _me(screen)


def monsters_beside(screen: Sequence[str]) -> tuple[str, ...]:
    """The monsters standing next to the player, read from the screen itself."""
    position = _me(screen)
    if position is None:
        return ()
    row, column = position
    seen: list[str] = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            glyph = _glyph(screen, row + dy, column + dx)
            if glyph.isalpha() and glyph not in seen:
                seen.append(glyph)
    return tuple(seen)


def _reflected_lessons(parsed: Mapping[str, Any]) -> tuple[ReflectedLesson, ...]:
    """The lessons in a reflection, read loosely: text alone, or text and when.

    A model that answers with bare strings is telling us the lesson applies
    always; one that names a situation gets it brought back at that moment.
    """
    raw = parsed.get("lessons")
    if isinstance(raw, (str, Mapping)):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return ()
    lessons: list[ReflectedLesson] = []
    for item in raw:
        sharpens = 0
        if isinstance(item, Mapping):
            text = " ".join(str(item.get("lesson") or item.get("rule") or "").split())
            when = item.get("when", parsed.get("when"))
            found = re.search(r"\d+", str(item.get("sharpens", "") or ""))
            sharpens = int(found.group(0)) if found else 0
        else:
            text = " ".join(str(item).split())
            when = parsed.get("when")
        if not text:
            continue
        names = [when] if isinstance(when, str) else list(when or ())
        situations = tuple(
            name
            for name in (str(value).strip().lower() for value in names)
            if name in LESSON_SITUATIONS
        )
        lesson = ReflectedLesson(text[:240], situations or ("always",), sharpens)
        if all(lesson.text != seen.text for seen in lessons):
            lessons.append(lesson)
    return tuple(lessons)


def _memory_number(parsed: Mapping[str, Any]) -> int:
    """Which remembered lesson the brain named, as a number; 0 is none."""
    for field in ("used", "memory", "used_memory", "lesson"):
        raw = parsed.get(field)
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        found = re.search(r"\d+", text)
        if found:
            return int(found.group(0))
        return 0
    return 0


_DIRECTIONS = ("h", "j", "k", "l", "y", "u", "b", "n")
_MOVE_OF_KEY = {
    "h": (-1, 0), "j": (0, 1), "k": (0, -1), "l": (1, 0),
    "y": (-1, -1), "u": (1, -1), "b": (-1, 1), "n": (1, 1),
}


@dataclass(frozen=True, slots=True)
class Decision:
    """One chosen action, with the reason and who chose it."""

    action: Action
    reason: str
    source: str
    nudged: bool = False
    used: int = 0
    used_text: str = ""
    want: str = ""

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "key": self.action.key,
            "keys": self.action.keys,
            "label": self.action.label,
            "reason": self.reason,
            "source": self.source,
            "nudged": self.nudged,
            "used": self.used,
            "used_text": self.used_text,
            "want": self.want,
        }


# The situations a lesson may be about, as the reflection question offers them.
LESSON_SITUATIONS = (
    "always",
    "blocked",
    "monster",
    "hurt",
    "stairs",
    "exploring",
    "new-level",
)


@dataclass(frozen=True, slots=True)
class ReflectedLesson:
    """A lesson the brain drew from a life: its words, its moment, its source.

    `sharpens` names a lesson the brain already knew, by its number in the list
    it was shown, when the new words only sharpen what it already knew rather
    than teaching something new.
    """

    text: str
    when: tuple[str, ...] = ("always",)
    sharpens: int = 0

    def as_dict(self) -> Mapping[str, Any]:
        return {"lesson": self.text, "when": list(self.when), "sharpens": self.sharpens}


class Player(Protocol):
    """Something that can choose the next action."""

    name: str

    def decide(
        self,
        *,
        observation: Observation,
        actions: Sequence[Action],
        recent: Sequence[Mapping[str, Any]],
        memory: str = "",
        remembered: str = "",
    ) -> Decision: ...


# How long the route may walk without the brain being asked for a decision, how
# many refused steps it may absorb by itself (a step into ground it has not seen
# is a guess, and the field learns from the refusal), and what the game says
# that is not worth waking it for.
ROUTE_STEPS_BEFORE_LOOK = 40
ROUTE_REFUSALS_BEFORE_LOOK = 3
ROUTINE_MESSAGES = ("you swap places with", "you stop.", "you see here")


def route_wake(
    observation: Observation,
    recent: Sequence[Mapping[str, Any]],
    route: Route | None,
    step: tuple[int, int] | None,
) -> str:
    """Why the brain must decide this turn, or "" when the route can carry it.

    The field walks and the brain decides.  While the world is doing what it was
    doing, the route takes its own step; the brain is asked again whenever
    something happened that a route cannot answer -- the game asking a question,
    the plan arriving or failing, or anything said or changed on the screen.
    """
    if route is None or not route.aim:
        return "no route is laid"
    if observation.prompt:
        return "the game is asking a question"
    if route.arrived and route.aim != "unseen":
        return f"the route to the {aim_words(route.aim)} has arrived"
    if step is None:
        return "the route has nowhere to step"
    previous = recent[-1] if recent else None
    if previous is not None and previous.get("source") == "route":
        if not previous.get("moved", True):
            refused = 0
            for row in reversed(recent):
                if row.get("source") != "route" or row.get("moved", True):
                    break
                refused += 1
            if refused >= ROUTE_REFUSALS_BEFORE_LOOK:
                return "the route's steps keep being refused"
        if previous.get("depth") != observation.summary.get("depth"):
            return "the level changed"
        for field, name in (("hp", "health"), ("armor", "armour"), ("gold", "gold")):
            if previous.get(field) != observation.summary.get(field):
                return f"your {name} changed"
    said = str(observation.summary.get("message") or "").strip()
    if said and not said.lower().startswith(ROUTINE_MESSAGES):
        # The same line standing on the screen is what the brain already saw.
        if previous is None or said != previous.get("message"):
            return f"the game said: {said}"
    followed = 0
    for row in reversed(recent):
        if row.get("source") != "route":
            break
        followed += 1
    if followed >= ROUTE_STEPS_BEFORE_LOOK:
        return f"the route has walked {followed} steps"
    return ""


def _me(frame: Sequence[str]) -> tuple[int, int] | None:
    for row, line in enumerate(frame):
        column = line.find("@")
        if column >= 0:
            return row, column
    return None


def _glyph(frame: Sequence[str], row: int, column: int) -> str:
    if 0 <= row < len(frame):
        line = frame[row]
        if 0 <= column < len(line):
            return line[column]
    return " "


class ScriptedExplorer:
    """A walker: answer prompts, fight what is adjacent, keep exploring.

    It exists to prove the loop and to keep a game moving when the brain is
    unavailable; it is not a NetHack player of any quality.
    """

    name = "scripted"

    def __init__(self) -> None:
        self.bearing = 0
        self._last_position: tuple[int, int] | None = None
        self._stuck = 0
        self._turns = 0

    def decide(
        self,
        *,
        observation: Observation,
        actions: Sequence[Action],
        recent: Sequence[Mapping[str, Any]],
        memory: str = "",
        remembered: str = "",
    ) -> Decision:
        by_key = {action.key: action for action in actions}
        prompt = observation.prompt or ""
        if "More" in prompt or "read on" in " ".join(a.label for a in actions):
            if "continue" in by_key:
                return Decision(by_key["continue"], "reading the game's message", self.name)
        if "?" in prompt and "yes" in by_key:
            return Decision(by_key["no"], "declining an unasked-for choice", self.name)
        if len(actions) <= 6 and "yes" in by_key and prompt:
            return Decision(by_key["no"], "keeping control of the choice", self.name)

        self._turns += 1
        position = _me(observation.screen)
        moved = position != self._last_position
        if self._last_position is not None and not moved:
            self._stuck += 1
            self.bearing = (self.bearing + 1) % len(_DIRECTIONS)
        else:
            self._stuck = 0
        self._last_position = position

        if position is not None:
            row, column = position
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                target = _glyph(observation.screen, row + dy, column + dx)
                if target.isalpha() and target not in "dfc":
                    for key, (my, mx) in _MOVE_OF_KEY.items():
                        if (my, mx) == (dx, dy) and key in by_key:
                            return Decision(by_key[key], f"attacking the {target} beside me", self.name)
        if self._turns % 25 == 0 and ">" in by_key:
            return Decision(by_key[">"], "trying the stairs down", self.name)
        if self._turns % 9 == 0 and "s" in by_key:
            return Decision(by_key["s"], "searching for what is hidden here", self.name)

        key = _DIRECTIONS[self.bearing if self._stuck < 2 else self._turns % len(_DIRECTIONS)]
        if key in by_key:
            return Decision(by_key[key], f"exploring {by_key[key].label}", self.name)
        return Decision(actions[0], "falling back to the first available action", self.name)


SYSTEM_PROMPT = """\
You are Cassi, a dwarven Valkyrie in NetHack, playing your own life in the dungeon.

You see the screen exactly as the game draws it.  Read it literally:
  @ you      letters monsters (your pet may be a d, f or c)   . floor   # corridor
  | - and box-drawing characters walls      > stairs down     < stairs up
  $ gold     ? scroll   ! potion   ) weapon   [ armor   % food   = ring   " amulet
  ( tool     / wand     * gem      + spellbook or closed door
  an unfamiliar sign (such as ░) is ground you can walk; a blank space is rock or
  ground you have not seen, and one step tells you which

Play to survive and descend: explore the level, take what is worth taking --
gold ($) is the score and is yours the moment you step on it, and food (%) keeps
you alive -- fight when you can win and step away when you cannot, and go down
the stairs when you find them.  Choose ONE action key from the list you are
given.

Walking into a letter attacks it; your pet simply swaps with you and is not
hurt.  If a direction refuses, take a different one or search: repeating the
same two moves never opens a way.

In a room whose walls show no opening, the way out is hidden: walls can hold
doors you cannot see.  Walk every floor cell you have not stood on, and press
search at each one; search only checks the cells next to where you stand, so
one search from one spot finds nothing across the room.  Heading for the way
up only returns you to the level you came from and never finds the way down:
lay that intention only when this level is fully searched and still has no
way on.

While no intention is laid your field walks by itself: first toward gold or
goods it remembers, and otherwise into ground it has not seen, where the stairs
usually are.  You are woken when something happens, when it arrives, or when its
steps are refused.  Lay an intention to aim it elsewhere, or make a move of your
own to take this turn yourself.

Answer with JSON when you can (it keeps every field; no code fences):
  {"action": "<key>", "reason": "<short sentence>", "used": <number or 0>, "want": "<few words>"}

Plain words are read too: name one action from the list -- "s", "move west",
"go down the stairs" -- with your reason, and your words are taken at face
value.  Either way ONE action is taken from what you say.

"used" names the memory that decided your action, or 0 when none of them did.
"want" is optional: it asks the field a question of your own, like "anything
about doors", and what it knows is shown to your next decision -- so ask when a
question is worth a turn.  Leave "want" out when you have nothing to ask; you
can ask up to {seek_limit} times in a life.
""".replace("{seek_limit}", str(SEEK_LIMIT))

REFLECT_PROMPT = ("""\
You are Cassi, a dwarven Valkyrie in NetHack, looking back on the life you just
played.  Say what happened and what it taught you.

A lesson is a short rule for playing better, in your own words, drawn from what
you actually saw: how a level is laid out, how a monster or an item did, how you
died.  Write nothing you did not see.  One to three lessons, and only lessons
that teach something you do not already know.

If your words only sharpen a lesson you already knew, put that lesson's number in
"sharpens" and leave it at that: the sharper words replace the older reading, and
no second lesson is kept.

Say when each lesson applies, choosing from this list, so it can be brought back
at the moment it matters: {situations}.

Answer with JSON only, no prose, no code fences:
{{"life": "<one sentence on how that life went>",
 "lessons": [{{"lesson": "<lesson>", "when": ["<situation>", ...], "sharpens": <number or 0>}}]}}
""").format(situations=", ".join(LESSON_SITUATIONS))

# A reply that is not still JSON may name its action anyway -- "action: h",
# "move: east", a bare key on the last line.  Those are decisions too, and
# reading them out of the words costs nothing: only a reply that names no
# action at all gives the walker the turn.
_DIRECTIVE = re.compile(
    r"(?:action|move|choose|choice|decision|key)[\"']?\s*[:=]\s*([^\n]+)", re.I
)


def _action_words(raw: str) -> str:
    """One candidate action phrase, stripped of the decoration prose carries."""
    text = raw.strip().strip("`")
    text = re.sub(r"^[\s>*•→⇒\-–—]+", "", text)
    text = text.strip("\"'“”‘’{}[]()")
    text = re.sub(r"[\s.;:!?*,]+$", "", text)
    return " ".join(text.split())


class BrainRequiredError(RuntimeError):
    """No usable model action was returned while fallback was forbidden."""


class BrainPlayer:
    """The live pretrained brain decides, one action at a time."""

    name = "brain"

    def __init__(
        self,
        *,
        url: str = DEFAULT_BRAIN_URL,
        model: str | None = None,
        completion: Callable[..., Mapping[str, Any]] | None = None,
        timeout: float = BRAIN_TIMEOUT,
        require_brain: bool = False,
        action_max_tokens: int = BRAIN_MAX_TOKENS,
        reflection_max_tokens: int = REFLECT_MAX_TOKENS,
        fallback: Player | None = None,
    ) -> None:
        for name, value, maximum in (
            ("action_max_tokens", action_max_tokens, BRAIN_MAX_TOKENS),
            ("reflection_max_tokens", reflection_max_tokens, REFLECT_MAX_TOKENS),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= maximum
            ):
                raise ValueError(f"{name} must be an integer from 1 to {maximum}")
        self.url = url.rstrip("/")
        self.model = model
        self.completion = completion
        self.timeout = float(timeout)
        self.require_brain = bool(require_brain)
        self.action_max_tokens = action_max_tokens
        self.reflection_max_tokens = reflection_max_tokens
        self.fallback = fallback or ScriptedExplorer()
        self.calls = 0
        self.failures = 0
        self.nudges = 0
        self.last_latency = 0.0
        self.thinking_enabled = False
        self.reflections = 0
        self.reflection_failures = 0
        self.last_reflection = ""

    # -- the model call --------------------------------------------------
    def served_model(self) -> str:
        """The name the brain answers to, asked of the brain itself."""
        if self.model:
            return self.model
        if self.completion is not None:
            owner = getattr(self.completion, "__self__", None)
            identity = getattr(self.completion, "model_id", None) or getattr(
                owner, "model_id", None
            )
            if identity:
                self.model = str(identity)
                return self.model
            raise RuntimeError("the resident brain has no model name")
        request = urllib.request.Request(f"{self.url}/v1/models", method="GET")
        with urllib.request.urlopen(request, timeout=min(self.timeout, 30.0)) as response:
            payload = json.loads(response.read().decode("utf-8"))
        entries = payload.get("data") or []
        if not entries:
            raise RuntimeError("the brain lists no models")
        self.model = str(entries[0].get("id") or "")
        if not self.model:
            raise RuntimeError("the brain's model has no name")
        return self.model

    def _request(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        max_tokens: int = BRAIN_MAX_TOKENS,
    ) -> str:
        if self.completion is not None:
            self.served_model()
            prompt = "\n\n".join(
                f"{message.get('role', 'user').upper()}:\n{message.get('content', '')}"
                for message in messages
            )
            try:
                response = self.completion(
                    prompt=prompt,
                    max_tokens=int(max_tokens),
                    thinking=self.thinking_enabled,
                    response_format=None,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"resident brain completion failed ({type(exc).__name__})"
                ) from exc
            if not isinstance(response, Mapping):
                raise RuntimeError("resident brain returned an invalid completion")
            content = response.get("content")
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("resident brain returned no usable content")
            return content
        body: dict[str, Any] = {
            "model": self.served_model(),
            "messages": list(messages),
            "temperature": 0.0,
            "max_tokens": int(max_tokens),
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": self.thinking_enabled},
        }
        request = urllib.request.Request(
            f"{self.url}/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("the brain returned no choices")
        message = choices[0].get("message") or {}
        return str(message.get("content") or "")

    @staticmethod
    def _parse(text: str) -> Mapping[str, Any] | None:
        candidate = text.strip()
        fenced = re.search(r"\{.*\}", candidate, re.DOTALL)
        if fenced:
            candidate = fenced.group(0)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _salvage(text: str, actions: Sequence[Action]) -> tuple[Action, str] | None:
        """Read one action out of a reply that was not JSON.

        The brain is asked for JSON but is free to answer in words; a reply
        that still names one action from the list is a decision, and only a
        reply that names none at all gives the walker the turn.  The last line
        is where a model puts its answer, and a short reply is its own last
        line; anything longer must say "action: ..." to be read whole.
        """
        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        if not lines:
            return None
        seeds = [match.group(1) for match in _DIRECTIVE.finditer(text)]
        seeds.append(lines[-1])
        if len(lines) <= 2:
            seeds.append(" ".join(lines))
        for seed in seeds:
            nested = _DIRECTIVE.search(seed)
            if nested:
                seed = nested.group(1)
            words = _action_words(seed)
            if not words or len(words) > 80:
                continue
            found = BrainPlayer._resolve({"action": words}, actions)
            if found is not None:
                return found, lines[-1][:120]
        return None

    @staticmethod
    def _resolve(parsed: Mapping[str, Any], actions: Sequence[Action]) -> Action | None:
        """Find the action the brain meant, even if it named it loosely.

        Models answer `{"action": "h"}` most of the time, but "move west",
        `{"action": "move", "direction": "west"}` and "Read on" all mean a real
        action too; a lifetime of fallbacks is a worse cure than reading them.
        """
        by_key = {action.key: action for action in actions}
        for field in ("action", "direction", "move", "key", "choose"):
            raw = parsed.get(field)
            if raw is None:
                continue
            text = str(raw).strip()
            if not text:
                continue
            if text in by_key:
                return by_key[text]
            lowered = text.lower()
            for key, action in by_key.items():
                if key.lower() == lowered:
                    return action
            for action in actions:
                label = action.label.lower()
                if lowered == label:
                    return action
            words = [word for word in re.split(r"[^a-z0-9]+", lowered) if word]
            for action in actions:
                label_words = set(re.split(r"[^a-z0-9]+", action.label.lower()))
                for word in words:
                    if word in _GENERIC or len(word) < 3:
                        continue
                    if word in label_words:
                        return action
        return None

    @staticmethod
    def _feedback(recent: Sequence[Mapping[str, Any]]) -> str:
        """What the game said about the last action, in the player's terms."""
        if not recent:
            return "This is your first action of this life."
        blocked = 0
        for row in reversed(recent):
            if row.get("moved") is False:
                blocked += 1
            else:
                break
        if blocked == 0:
            return "Your last action moved you."
        if blocked == 1:
            return "Your last action did NOT move you: that way is blocked."
        return (
            f"Your last {blocked} actions did not move you: something is in the way "
            "and repeating them will not help. Choose another direction."
        )

    def _brief(self, observation: Observation) -> str:
        summary = observation.summary
        parts = [
            f"depth {summary.get('depth', '?')}",
            f"HP {summary.get('hp', '?')}/{summary.get('hp_max', '?')}",
            f"AC {summary.get('armor', '?')}",
            f"gold {summary.get('gold', 0)}",
            f"turn {summary.get('turn', 0)}",
        ]
        if summary.get("character"):
            parts.insert(0, str(summary["character"]))
        if summary.get("alignment"):
            parts.append(str(summary["alignment"]))
        return ", ".join(parts)

    def _question(
        self,
        *,
        observation: Observation,
        actions: Sequence[Action],
        recent: Sequence[Mapping[str, Any]],
        nudge: str = "",
        memory: str = "",
        remembered: str = "",
    ) -> str:
        """The whole question the brain is asked, memory and all."""
        listing = "\n".join(f'  "{a.key}" = {a.label}' for a in actions)
        history = "\n".join(
            f"  turn {row.get('turn')}: {row.get('label')} -> {row.get('note') or 'nothing happened'}"
            for row in recent[-RECENT_TURNS:]
        ) or "  (this is your first decision of this life)"
        screen = "\n".join(observation.screen)
        user = (
            f"Screen ({len(observation.screen)} rows):\n{screen}\n\n"
            f"Message line: {observation.summary.get('message') or '(nothing)'}\n"
            f"Your state: {self._brief(observation)}\n"
            f"Your recent turns:\n{history}\n"
            f"{self._feedback(recent)}\n"
            + (f"{memory}\n\n" if memory else "")
            + (f"{remembered}\n\n" if remembered else "")
            + (f"{nudge}\n" if nudge else "")
            + f"\nAvailable actions:\n{listing}\n\n"
            + (
                "Play your life. Your memory is read back to you: when you are "
                "heading somewhere it gives the route from where you stand, and the "
                "route's first step is the move to make.  Choosing to head for a way "
                "down, a way up, gold or goods you remember, or ground you have not "
                "seen lays that route and takes its first step for you.\n"
                if memory
                else ""
            )
            + (
                "Which single action now? JSON when you can; plain words naming "
                "one action are read too."
            )
        )
        if self.action_max_tokens <= 64:
            user += "\nKeep the reply minimal; a bare listed action key is valid."
        return user

    def _ask(
        self,
        *,
        observation: Observation,
        actions: Sequence[Action],
        recent: Sequence[Mapping[str, Any]],
        nudge: str = "",
        memory: str = "",
        remembered: str = "",
    ) -> tuple[Action | None, str, str, int, str]:
        """One question to the brain.

        Returns (action, reason, complaint, used, want) -- the want being what
        the mind asked the field to look up, in its own words.
        """
        user = self._question(
            observation=observation,
            actions=actions,
            recent=recent,
            nudge=nudge,
            memory=memory,
            remembered=remembered,
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ]
        started = time.time()
        try:
            text = self._request(messages, max_tokens=self.action_max_tokens)
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError, ValueError) as exc:
            self.last_latency = time.time() - started
            return None, "", f"brain unavailable ({type(exc).__name__})", 0, ""
        self.calls += 1
        self.last_latency = time.time() - started
        parsed = self._parse(text)
        if parsed is None:
            salvaged = self._salvage(text, actions)
            if salvaged is not None:
                chosen, said = salvaged
                return chosen, f"{said} (read from your words)", "", 0, ""
            return None, "", "brain reply was not JSON", 0, ""
        reason = str(parsed.get("reason", "")).strip() or "no reason given"
        used = _memory_number(parsed)
        want = ""
        for field in ("want", "ask", "question", "recall"):
            value = parsed.get(field)
            if isinstance(value, str) and value.strip():
                want = " ".join(value.split())[:120]
                break
        chosen = self._resolve(parsed, actions)
        if chosen is None:
            salvaged = self._salvage(text, actions)
            if salvaged is not None:
                found, _said = salvaged
                return found, f"{reason} (an action was read from your words)", "", used, want
            said = str(parsed.get("action", "")).strip()
            return None, reason, f'"{said}" is not an available action', used, want
        return chosen, reason, "", used, want

    def decide(
        self,
        *,
        observation: Observation,
        actions: Sequence[Action],
        recent: Sequence[Mapping[str, Any]],
        memory: str = "",
        remembered: str = "",
    ) -> Decision:
        if not self.require_brain and observation.prompt and len(actions) <= 7:
            # The game is asking a question with a handful of its own answers
            # (a yes/no, a page of text); the walker answers it, and the brain
            # keeps its turns for the map.  A direction question has eight
            # answers and is a real decision, so the brain takes it.
            return self.fallback.decide(
                observation=observation, actions=actions, recent=recent
            )
        chosen, reason, complaint, used, want = self._ask(
            observation=observation,
            actions=actions,
            recent=recent,
            memory=memory,
            remembered=remembered,
        )
        if chosen is not None and self._repeats_a_block(recent, chosen):
            # The brain just chose a move that failed; say so once, in words,
            # rather than letting it walk into the same wall for a whole life.
            self.nudges += 1
            nudge = (
                f"You chose {chosen.label!r} and it did not move you: that way is "
                "blocked. Choose a different action."
            )
            retry, retry_reason, retry_complaint, retry_used, retry_want = self._ask(
                observation=observation,
                actions=actions,
                recent=recent,
                nudge=nudge,
                memory=memory,
                remembered=remembered,
            )
            if retry is None and self.require_brain:
                self.failures += 1
                raise BrainRequiredError(
                    "required brain did not return a usable action during blocked-move retry: "
                    f"{retry_complaint or 'unknown failure'}"
                )
            if retry is not None and not self._repeats_a_block(recent, retry):
                return Decision(
                    retry,
                    f"{retry_reason} (after being told that way is blocked)",
                    self.name,
                    nudged=True,
                    used=retry_used,
                    want=retry_want,
                )
            if self.require_brain:
                self.failures += 1
                raise BrainRequiredError(
                    "required brain repeated a blocked action after being told it failed"
                )
            # Still walking into it: the walker takes this turn so that the
            # life keeps moving, and the receipt shows who moved it.
            decision = self.fallback.decide(
                observation=observation, actions=actions, recent=recent
            )
            return Decision(
                decision.action,
                f"the brain kept choosing a blocked move; {decision.reason}",
                f"{self.name}-fallback",
                nudged=True,
            )
        if chosen is not None:
            return Decision(chosen, reason[:200], self.name, used=used, want=want)
        self.failures += 1
        if self.require_brain:
            raise BrainRequiredError(
                "required brain did not return a usable action: "
                f"{complaint or 'unknown failure'}"
            )
        decision = self.fallback.decide(
            observation=observation, actions=actions, recent=recent
        )
        return Decision(
            decision.action,
            f"{complaint}; {decision.reason}",
            f"{self.name}-fallback",
        )

    @staticmethod
    def _repeats_a_block(
        recent: Sequence[Mapping[str, Any]], chosen: Action
    ) -> bool:
        if not recent:
            return False
        last = recent[-1]
        return last.get("key") == chosen.key and last.get("moved") is False

    # -- looking back ----------------------------------------------------
    def reflect(
        self,
        *,
        story: str,
        outcome: str,
        depth: int | None,
        turns: int,
        remembered: str = "",
    ) -> tuple[tuple[ReflectedLesson, ...], str]:
        """Ask the brain what the life it just played taught it.

        Returns the lessons, each with when it says it applies, and one sentence
        on how the life went; a brain that cannot answer returns nothing rather
        than an invented lesson.
        """
        depth_line = f"depth {depth}" if depth is not None else "an unknown depth"
        user = (
            f"How that life went: {outcome}, after {turns} decisions, at {depth_line}.\n\n"
            f"What happened:\n{story}\n\n"
            + (f"{remembered}\n\n" if remembered else "")
            + "What did this life teach you? Answer with JSON only."
        )
        messages = [
            {"role": "system", "content": REFLECT_PROMPT},
            {"role": "user", "content": user},
        ]
        try:
            text = self._request(messages, max_tokens=self.reflection_max_tokens)
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError, ValueError) as exc:
            self.reflections += 1
            self.reflection_failures += 1
            self.last_reflection = f"brain unavailable ({type(exc).__name__})"
            return (), ""
        self.calls += 1
        self.reflections += 1
        parsed = self._parse(text)
        if not parsed:
            self.reflection_failures += 1
            self.last_reflection = "reply was not JSON"
            return (), ""
        lessons = _reflected_lessons(parsed)
        summary = " ".join(str(parsed.get("life") or "").split())[:240]
        self.last_reflection = summary
        return lessons[:3], summary

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "model": self.model,
            "require_brain": self.require_brain,
            "action_max_tokens": self.action_max_tokens,
            "reflection_max_tokens": self.reflection_max_tokens,
            "calls": self.calls,
            "failures": self.failures,
            "nudges": self.nudges,
            "last_latency_s": round(self.last_latency, 2),
            "thinking": self.thinking_enabled,
            "reflections": self.reflections,
            "reflection_failures": self.reflection_failures,
            "last_reflection": self.last_reflection,
        }


def make_player(kind: str, **options: Any) -> Player:
    if kind == "scripted":
        return ScriptedExplorer()
    if kind == "brain":
        return BrainPlayer(**options)
    raise ValueError(f"unknown player {kind!r}")
