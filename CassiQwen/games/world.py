"""The world seam: what a game must expose to be one Cassi can live in.

A world answers four questions and nothing else:

    reset()             put the world at its beginning, reproducibly
    observe()           what the player can see right now
    actions()           what the player may do right now
    act(action)         do one of those things and report what happened

Everything else — how the world is rendered, how it is driven, how the player
decides — belongs to the layers above.  A terminal game, an API game, and a
physics sandbox all satisfy this seam; the runner and the watch surface are
written against it once.

Worlds register by name, so adding a game is one module with one decorator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, runtime_checkable


class WorldError(RuntimeError):
    """A world was addressed in a way it cannot honour."""


@dataclass(frozen=True, slots=True)
class Action:
    """One thing a player may do, in the world's own vocabulary."""

    key: str
    keys: str
    label: str

    def __post_init__(self) -> None:
        if not self.key:
            raise WorldError("action key must be non-empty")
        if not self.keys:
            raise WorldError("action keys must be non-empty")

    def as_dict(self) -> Mapping[str, str]:
        return {"key": self.key, "keys": self.keys, "label": self.label}


@dataclass(frozen=True, slots=True)
class Observation:
    """What the world shows the player at one moment.

    `screen` is the world's own view — for a text world it is the literal screen,
    for a rendered game it is a faithful text rendering.  `summary` is optional
    structured state a world can offer without the player parsing text.
    """

    screen: tuple[str, ...]
    summary: Mapping[str, Any] = field(default_factory=dict)
    events: tuple[str, ...] = ()
    prompt: str | None = None
    done: bool = False
    score: float = 0.0
    turn: int = 0

    @property
    def text(self) -> str:
        return "\n".join(self.screen)

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "screen": list(self.screen),
            "summary": dict(self.summary),
            "events": list(self.events),
            "prompt": self.prompt,
            "done": self.done,
            "score": self.score,
            "turn": self.turn,
        }


@dataclass(frozen=True, slots=True)
class StepResult:
    """One action taken, and the world's answer to it."""

    observation: Observation
    accepted: bool = True
    note: str = ""

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "observation": self.observation.as_dict(),
            "accepted": self.accepted,
            "note": self.note,
        }


@runtime_checkable
class GameWorld(Protocol):
    """The seam.  A world is state, a view, a vocabulary, and a step."""

    name: str
    goal: str

    def reset(self) -> Observation: ...

    def observe(self) -> Observation: ...

    def actions(self) -> tuple[Action, ...]: ...

    def act(self, action: Action) -> StepResult: ...

    def close(self) -> None: ...


_REGISTRY: dict[str, Callable[..., GameWorld]] = {}


def register_world(name: str):
    """Register a world factory under `name` (used as a decorator)."""

    def decorate(factory: Callable[..., GameWorld]) -> Callable[..., GameWorld]:
        key = str(name).strip().lower()
        if not key:
            raise WorldError("world name must be non-empty")
        if key in _REGISTRY and _REGISTRY[key] is not factory:
            raise WorldError(f"world {key!r} is already registered")
        _REGISTRY[key] = factory
        return factory

    return decorate


def available_games() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def create_world(name: str, **options: Any) -> GameWorld:
    key = str(name).strip().lower()
    factory = _REGISTRY.get(key)
    if factory is None:
        known = ", ".join(available_games()) or "none"
        raise WorldError(f"unknown world {key!r}; registered worlds: {known}")
    return factory(**options)
