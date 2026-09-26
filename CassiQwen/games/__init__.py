"""Games: worlds Cassi can live in, watched live.

Layout
------
`terminal`   ConPTY-backed terminal sessions with a decoded screen (the substrate)
`nethack`    the NetHack world: startup, perception, actions, events
`player`     the decision loop: perception -> memory -> brain -> one action
`view`       the live watch surface: one screen, one panel, one page

A game is a world adapter.  Everything above `terminal`/`world` is written
against the `GameWorld` seam, so a second game is one module plus one
registration, not a second runner.
"""
from __future__ import annotations

from games.world import (
    Action,
    GameWorld,
    Observation,
    StepResult,
    WorldError,
    available_games,
    create_world,
    register_world,
)

# Importing a world module registers it.  This is the only place built-in games
# are wired in: a new game is a module plus one import here.
from games import nethack  # noqa: E402,F401  (registration side effect)

__all__ = [
    "Action",
    "GameWorld",
    "Observation",
    "StepResult",
    "WorldError",
    "available_games",
    "create_world",
    "register_world",
]
